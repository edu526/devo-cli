"""Export DynamoDB table command."""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

from cli_tool.commands.dynamodb.core import DynamoDBExporter, ParallelScanner, detect_usable_index
from cli_tool.commands.dynamodb.utils import (
    ExportConfigManager,
    FilterBuilder,
    create_template_from_args,
    estimate_export_size,
    validate_table_exists,
)

console = Console()

_RESERVED_KEYWORDS = {
    "name",
    "status",
    "type",
    "value",
    "data",
    "timestamp",
    "date",
    "time",
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
    "order",
    "group",
    "size",
    "key",
    "index",
    "count",
    "range",
    "hash",
    "table",
    "column",
    "attribute",
    "attributes",
    "connection",
    "percent",
    "values",
    "format",
}


def _apply_template(template: dict, args: dict) -> dict:
    """Merge template values into args dict (CLI args take precedence)."""
    defaults = {
        "output": None,
        "format": "csv",
        "region": "us-east-1",
        "mode": "strings",
        "bool_format": "lowercase",
    }
    for key, default in defaults.items():
        if args.get(key) == default or not args.get(key):
            args[key] = template.get(key, default)

    for key in ("limit", "attributes", "filter", "filter_values", "filter_names", "key_condition", "index", "compress"):
        if not args.get(key):
            args[key] = template.get(key)

    return args


def _build_projection_expression(attributes: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Build projection expression, escaping DynamoDB reserved keywords.

    Returns (projection_expression, expression_attribute_names).
    """
    attr_list = [a.strip() for a in attributes.split(",")]
    needs_escaping = any(a.lower() in _RESERVED_KEYWORDS for a in attr_list)

    if not needs_escaping:
        return attributes.replace(",", ", "), None

    expression_attribute_names: Dict[str, str] = {}
    escaped_attrs = []
    for attr in attr_list:
        if attr.lower() in _RESERVED_KEYWORDS:
            placeholder = f"#{attr}"
            expression_attribute_names[placeholder] = attr
            escaped_attrs.append(placeholder)
        else:
            escaped_attrs.append(attr)

    return ", ".join(escaped_attrs), expression_attribute_names


def _parse_filter_expressions(
    filter_expr: Optional[str],
    filter_values: Optional[str],
    filter_names: Optional[str],
    expression_attribute_names: Optional[Dict[str, str]],
) -> Tuple[Optional[str], Optional[Dict], Optional[Dict]]:
    """Parse filter, filter_values, filter_names into DynamoDB expression components.

    Returns (filter_expression, expression_attribute_values, expression_attribute_names).
    """
    expression_attribute_values = None

    if filter_expr and not filter_values:
        filter_builder = FilterBuilder()
        try:
            filter_expr, expression_attribute_values, expression_attribute_names = filter_builder.build_filter(filter_expr)
        except Exception as e:
            console.print(f"[red]✗ Invalid filter syntax: {e}[/red]")
            sys.exit(1)
    elif filter_values:
        from boto3.dynamodb.types import TypeSerializer

        try:
            parsed_values = json.loads(filter_values)
            # Convert Python values to DynamoDB typed format
            serializer = TypeSerializer()
            expression_attribute_values = {}
            for key, value in parsed_values.items():
                # If value is already in DynamoDB format (has type keys like 'S', 'N', 'BOOL'), keep it
                if isinstance(value, dict) and len(value) == 1 and list(value.keys())[0] in ("S", "N", "BOOL", "NULL", "M", "L", "SS", "NS", "BS"):
                    expression_attribute_values[key] = value
                else:
                    # Otherwise, serialize Python value to DynamoDB format
                    expression_attribute_values[key] = serializer.serialize(value)
        except json.JSONDecodeError as e:
            console.print(f"[red]✗ Invalid filter-values JSON: {e}[/red]")
            sys.exit(1)

    if filter_names and not expression_attribute_names:
        try:
            expression_attribute_names = json.loads(filter_names)
        except json.JSONDecodeError as e:
            console.print(f"[red]✗ Invalid filter-names JSON: {e}[/red]")
            sys.exit(1)

    return filter_expr, expression_attribute_values, expression_attribute_names


def _build_item_key(item: Dict[str, Any], primary_key_attrs: List[str]) -> str:
    """Create a unique string key from an item's primary key attributes."""
    parts = [f"{k}={json.dumps(item[k], sort_keys=True, default=str)}" for k in primary_key_attrs if k in item]
    return "|".join(parts)


def _collect_names_from_expr(expr: Optional[str], expression_attribute_names: Dict[str, str]) -> Dict[str, str]:
    """Return subset of expression_attribute_names whose keys appear in expr."""
    if not expr:
        return {}
    return {k: v for k, v in expression_attribute_names.items() if k in expr}


def _collect_query_names(
    query_config: Dict[str, Any],
    expression_attribute_names: Optional[Dict[str, str]],
    projection_expression: Optional[str],
) -> Dict[str, str]:
    """Build expression_attribute_names dict for a single query."""
    if not expression_attribute_names:
        return {}

    query_names: Dict[str, str] = {}
    name_placeholder = query_config["key_condition"].split("=")[0].strip()

    if name_placeholder in expression_attribute_names:
        query_names[name_placeholder] = expression_attribute_names[name_placeholder]

    query_names.update(_collect_names_from_expr(query_config.get("filter_expression"), expression_attribute_names))
    query_names.update(_collect_names_from_expr(projection_expression, expression_attribute_names))

    return query_names


def _collect_query_values(
    query_config: Dict[str, Any],
    expression_attribute_values: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build expression_attribute_values dict for a single query."""
    if not expression_attribute_values:
        return {}

    query_values: Dict[str, Any] = {}
    value_placeholder = query_config["key_condition"].split("=")[1].strip()

    if value_placeholder in expression_attribute_values:
        query_values[value_placeholder] = expression_attribute_values[value_placeholder]

    if query_config.get("filter_expression"):
        filter_expr = query_config["filter_expression"]
        for val_key, val in expression_attribute_values.items():
            if val_key in filter_expr:
                query_values[val_key] = val

    return query_values


def _execute_query_with_retry(
    exporter, query_config, projection_expression, expression_attribute_values, expression_attribute_names, limit_per_query
):
    """Execute a single query, retrying once on throughput exceeded."""
    query_values = _collect_query_values(query_config, expression_attribute_values)
    query_names = _collect_query_names(query_config, expression_attribute_names, projection_expression)

    kwargs = {
        "key_condition_expression": query_config["key_condition"],
        "filter_expression": query_config.get("filter_expression"),
        "projection_expression": projection_expression,
        "index_name": query_config.get("index_name"),
        "limit": limit_per_query,
        "expression_attribute_values": query_values or None,
        "expression_attribute_names": query_names or None,
    }

    try:
        return exporter.query_table(**kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
            console.print("[yellow]⚠ Rate limit exceeded, waiting 1 second...[/yellow]")
            import time

            time.sleep(1)
            return exporter.query_table(**kwargs)
        raise


def _append_unique_items(all_items, seen_keys, query_items, primary_key_attrs, limit):
    """Append deduplicated items; returns True if limit was reached."""
    for item in query_items:
        item_key = _build_item_key(item, primary_key_attrs)
        if item_key not in seen_keys:
            seen_keys.add(item_key)
            all_items.append(item)
            if limit and len(all_items) >= limit:
                console.print(f"[cyan]Reached limit of {limit} items, stopping remaining queries[/cyan]")
                return True
    return False


def _execute_multi_query(exporter, query_configs, projection_expression, expression_attribute_values, expression_attribute_names, limit, table_info):
    """Execute multiple queries and combine results with deduplication."""
    limit_per_query = None
    if limit:
        limit_per_query = int(limit * 1.5 / len(query_configs)) + 100
        console.print(f"[cyan]  Limit per query: ~{limit_per_query} items (total limit: {limit})[/cyan]")

    all_items: List[Dict[str, Any]] = []
    seen_keys: set = set()  # noqa: C405
    primary_key_attrs = [key["AttributeName"] for key in table_info.get("key_schema", [])]

    for idx, query_config in enumerate(query_configs, 1):
        console.print(f"\n[cyan]Executing query {idx}/{len(query_configs)}...[/cyan]")
        query_items = _execute_query_with_retry(
            exporter,
            query_config,
            projection_expression,
            expression_attribute_values,
            expression_attribute_names,
            limit_per_query,
        )
        if _append_unique_items(all_items, seen_keys, query_items, primary_key_attrs, limit):
            break

    console.print(f"\n[green]✓ Combined {len(all_items)} unique items from {len(query_configs)} queries[/green]")

    if limit and len(all_items) > limit:
        all_items = all_items[:limit]
        console.print(f"[cyan]Applied final limit: {limit} items[/cyan]")

    return all_items


def _auto_detect_query_strategy(exporter, filter_expr, index, key_condition, expression_attribute_names, expression_attribute_values):
    """Auto-detect whether to use query, multi-query, or scan.

    Returns (use_query, key_condition, filter_expr, index, multi_query_mode, query_configs).
    """
    use_query = key_condition is not None
    multi_query_mode = False
    query_configs = []

    if use_query or not filter_expr or index:
        return use_query, key_condition, filter_expr, index, multi_query_mode, query_configs

    table_info = exporter.get_table_info()
    auto_detected_index = detect_usable_index(filter_expr, expression_attribute_names, table_info)

    if not auto_detected_index:
        return use_query, key_condition, filter_expr, index, multi_query_mode, query_configs

    if auto_detected_index.get("has_or"):
        use_query, multi_query_mode, query_configs = _handle_or_detection(
            auto_detected_index, filter_expr, expression_attribute_names, expression_attribute_values
        )
    else:
        console.print(f"[green]✓ Auto-detected indexed attribute '{auto_detected_index['key_attribute']}' with equality filter[/green]")
        console.print("[cyan]  Switching to Query for optimal performance[/cyan]")

        if auto_detected_index.get("index_name"):
            console.print(f"[cyan]  Using GSI: {auto_detected_index['index_name']}[/cyan]")
            index = auto_detected_index["index_name"]

        key_condition = auto_detected_index["key_condition"]
        use_query = True
        filter_expr = auto_detected_index["remaining_filter"]

        if filter_expr:
            console.print(f"[cyan]  Additional filter: {filter_expr}[/cyan]")
        else:
            console.print("[cyan]  No additional filters needed[/cyan]")

    return use_query, key_condition, filter_expr, index, multi_query_mode, query_configs


def _build_query_configs(indexed_attrs: list, remaining_filter: Optional[str]) -> list:
    """Build query config list from indexed attributes."""
    query_configs = []
    for attr_info in indexed_attrs:
        query_config = {
            "key_condition": f"{attr_info['attr_ref']} = {attr_info['value_ref']}",
            "index_name": attr_info.get("index_name"),
            "key_attribute": attr_info["key_attribute"],
            "filter_expression": remaining_filter,
        }
        query_configs.append(query_config)
        index_display = f"GSI: {query_config['index_name']}" if query_config["index_name"] else "main table"
        console.print(f"[cyan]    Query {len(query_configs)}: {attr_info['key_attribute']} ({index_display})[/cyan]")
    return query_configs


def _extract_remaining_filter(
    filter_expr: str, expression_attribute_values: Optional[Dict], expression_attribute_names: Optional[Dict]
) -> Optional[str]:
    """Extract the AND portion of a parsed filter expression."""
    if not (filter_expr and expression_attribute_values and expression_attribute_names):
        return None
    and_match = re.search(r"\)\s+AND\s+([^)]+)\)$", filter_expr, re.IGNORECASE)
    if and_match:
        remaining = and_match.group(1).strip()
        console.print(f"[cyan]  Additional filter: {remaining}[/cyan]")
        return remaining
    return None


def _handle_or_detection(auto_detected_index, filter_expr, expression_attribute_names, expression_attribute_values):
    """Handle OR condition detection and build multi-query configs."""
    indexed_attrs = auto_detected_index.get("indexed_attributes", [])
    or_parts = re.split(r"\s+(?:OR|or)\s+", filter_expr)
    can_multi_query = len(or_parts) == len(indexed_attrs) and len(or_parts) <= 5

    if not (can_multi_query and len(indexed_attrs) >= 2):
        _print_or_scan_warning(indexed_attrs)
        return False, False, []

    console.print(f"[green]✓ Detected OR condition with {len(indexed_attrs)} indexed attributes[/green]")
    console.print("[cyan]  Using multiple queries for optimal performance[/cyan]")

    remaining_filter = _extract_remaining_filter(filter_expr, expression_attribute_values, expression_attribute_names)
    query_configs = _build_query_configs(indexed_attrs, remaining_filter)
    return True, True, query_configs


def _print_or_scan_warning(indexed_attrs):
    """Print warning when OR condition cannot be optimized."""
    console.print("[yellow]ℹ Filter contains OR condition with indexed attributes[/yellow]")
    if indexed_attrs:
        attr_names = ", ".join(a["key_attribute"] for a in indexed_attrs)
        console.print(f"[yellow]  Detected indexed attributes: {attr_names}[/yellow]")
        console.print("[yellow]  Tip: For better performance, run separate queries:[/yellow]")
        for attr_info in indexed_attrs[:2]:
            example_cmd = f"devo dynamodb export <table> --key-condition \"{attr_info['key_attribute']} = <value>\""
            if attr_info.get("index_name"):
                example_cmd += f" --index \"{attr_info['index_name']}\""
            console.print(f"[yellow]    {example_cmd}[/yellow]")
    console.print("[yellow]  Using Scan with full filter[/yellow]")


def _auto_tune_parallel_scan(exporter, use_query, dry_run, use_parallel, segments):
    """Auto-enable parallel scan for large tables. Returns (use_parallel, segments)."""
    if use_query or dry_run or use_parallel:
        return use_parallel, segments

    table_info = exporter.get_table_info()
    item_count = table_info.get("item_count", 0)

    if item_count <= 100000:
        return use_parallel, segments

    console.print(f"[yellow]ℹ Table has {item_count:,} items. Auto-enabling parallel scan for better performance.[/yellow]")
    if segments == 4:
        if item_count > 1000000:
            segments = 16
        elif item_count > 500000:
            segments = 12
        else:
            segments = 8
        console.print(f"[yellow]ℹ Using {segments} parallel segments.[/yellow]")

    return True, segments


class _ScanContext:
    """Groups all parameters needed to fetch items from DynamoDB."""

    __slots__ = (
        "exporter",
        "dynamodb_client",
        "table_name",
        "use_query",
        "use_parallel",
        "multi_query_mode",
        "query_configs",
        "key_condition",
        "filter_expr",
        "projection_expression",
        "index",
        "limit",
        "segments",
        "expression_attribute_values",
        "expression_attribute_names",
        "table_info",
        "dry_run",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _fetch_items(ctx: "_ScanContext") -> list:
    """Fetch items using the appropriate strategy."""
    if ctx.multi_query_mode:
        console.print(f"[cyan]Using Multiple Queries ({len(ctx.query_configs)} queries for OR optimization)[/cyan]")
        return _execute_multi_query(
            ctx.exporter,
            ctx.query_configs,
            ctx.projection_expression,
            ctx.expression_attribute_values,
            ctx.expression_attribute_names,
            ctx.limit,
            ctx.table_info,
        )

    if ctx.use_query:
        console.print("[cyan]Using Query (efficient partition key lookup)[/cyan]")
        return ctx.exporter.query_table(
            key_condition_expression=ctx.key_condition,
            filter_expression=ctx.filter_expr,
            projection_expression=ctx.projection_expression,
            index_name=ctx.index,
            limit=ctx.limit,
            expression_attribute_values=ctx.expression_attribute_values,
            expression_attribute_names=ctx.expression_attribute_names,
        )

    if ctx.use_parallel and not ctx.dry_run:
        console.print(f"[cyan]Using Parallel Scan ({ctx.segments} segments for faster export)[/cyan]")
        scanner = ParallelScanner(dynamodb_client=ctx.dynamodb_client, table_name=ctx.table_name, total_segments=ctx.segments)
        return scanner.parallel_scan(
            filter_expression=ctx.filter_expr,
            projection_expression=ctx.projection_expression,
            index_name=ctx.index,
            limit=ctx.limit,
            expression_attribute_values=ctx.expression_attribute_values,
            expression_attribute_names=ctx.expression_attribute_names,
        )

    console.print("[cyan]Using Regular Scan (reading entire table)[/cyan]")
    return ctx.exporter.scan_table(
        limit=ctx.limit,
        filter_expression=ctx.filter_expr,
        projection_expression=ctx.projection_expression,
        index_name=ctx.index,
        expression_attribute_values=ctx.expression_attribute_values,
        expression_attribute_names=ctx.expression_attribute_names,
    )


def _print_dry_run_summary(multi_query_mode, query_configs, use_query, key_condition, filter, use_parallel, segments, format, mode, compress, limit):
    """Print dry-run summary."""
    console.print("\n[bold green]Dry run completed[/bold green]")

    if multi_query_mode:
        console.print(f"[cyan]Export strategy:[/cyan] Multiple Queries ({len(query_configs)} queries)")
        for idx, qc in enumerate(query_configs, 1):
            index_info = f"GSI: {qc['index_name']}" if qc.get("index_name") else "main table"
            console.print(f"[cyan]  Query {idx}:[/cyan] {qc['key_attribute']} ({index_info})")
    elif use_query:
        console.print("[cyan]Export strategy:[/cyan] Query")
        console.print(f"[cyan]  Key condition:[/cyan] {key_condition}")
        if filter:
            console.print(f"[cyan]  Filter:[/cyan] {filter}")
    elif use_parallel:
        console.print(f"[cyan]Export strategy:[/cyan] Parallel Scan ({segments} segments)")
    else:
        console.print("[cyan]Export strategy:[/cyan] Regular Scan")

    console.print(f"[cyan]Format:[/cyan] {format.upper()}")
    console.print(f"[cyan]Mode:[/cyan] {mode}")
    if compress:
        console.print(f"[cyan]Compression:[/cyan] {compress}")
    if limit:
        console.print(f"[cyan]Limit:[/cyan] {limit:,} items")


def _resolve_output_path(output: Optional[str], table_name: str, format: str) -> Path:
    """Determine the output file path."""
    if output:
        return Path(output)

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext_map = {"csv": "csv", "tsv": "tsv", "jsonl": "jsonl", "json": "json"}
    extension = ext_map.get(format, "json")
    return Path.cwd() / f"{table_name}_{timestamp}.{extension}"


def _validate_write_permissions(output_path: Path) -> None:
    """Check that the output directory is writable."""
    try:
        test_file = output_path.parent / f".{output_path.name}.test"
        test_file.touch()
        test_file.unlink()
    except OSError as e:
        console.print(f"[red]✗ Cannot write to {output_path}: {e}[/red]")
        console.print("[yellow]Check directory permissions or choose a different output path[/yellow]")
        sys.exit(1)


def _warn_large_export(exporter, yes: bool, dry_run: bool, limit: Optional[int]) -> bool:
    """Warn user about very large exports. Returns False if user cancels."""
    if yes or dry_run or limit:
        return True

    table_info = exporter.get_table_info()
    item_count = table_info.get("item_count", 0)

    if item_count <= 1000000:
        return True

    estimated_minutes = item_count / 10000
    console.print(f"[yellow]⚠ Warning: Exporting {item_count:,} items may take ~{estimated_minutes:.0f} minutes[/yellow]")
    console.print("[yellow]  Consider using --limit to export a subset first[/yellow]")
    return click.confirm("Continue with full export?", default=False)


def _do_export(exporter, items, fmt, output_path, mode, null_value, delimiter, encoding, metadata, compress, pretty, bool_format):
    """Write items to the output file in the requested format."""
    if fmt in ("csv", "tsv"):
        csv_delimiter = "\t" if fmt == "tsv" else delimiter
        return exporter.export_to_csv(
            items=items,
            output_file=output_path,
            mode=mode,
            null_value=null_value,
            delimiter=csv_delimiter,
            encoding=encoding,
            include_metadata=metadata,
            compress=compress,
            bool_format=bool_format,
        )

    return exporter.export_to_json(
        items=items,
        output_file=output_path,
        jsonl=(fmt == "jsonl"),
        pretty=pretty,
        encoding=encoding,
        compress=compress,
    )


@dataclass
class ExportParams:
    """Groups all export parameters to avoid long function signatures."""

    profile: Optional[str]
    table_name: str
    output: Optional[str]
    fmt: str
    region: str
    limit: Optional[int]
    attributes: Optional[str]
    filter_expr: Optional[str]
    filter_values: Optional[str]
    filter_names: Optional[str]
    key_condition: Optional[str]
    index: Optional[str]
    mode: str
    null_value: str
    delimiter: str
    encoding: str
    compress: Optional[str]
    metadata: bool
    pretty: bool
    parallel_scan: bool
    segments: int
    dry_run: bool
    yes: bool
    save_template: Optional[str]
    bool_format: str


def _run_export_core(p: ExportParams, config_manager: ExportConfigManager) -> None:
    """Core export logic after template resolution."""
    from cli_tool.core.utils.aws import create_aws_client

    dynamodb_client = create_aws_client("dynamodb", profile_name=p.profile, region_name=p.region)

    if not validate_table_exists(dynamodb_client, p.table_name):
        sys.exit(1)

    exporter = DynamoDBExporter(table_name=p.table_name, dynamodb_client=dynamodb_client, region=p.region, profile=p.profile)

    if not p.yes and not p.dry_run:
        estimate_export_size(exporter)

    projection_expression, expression_attribute_names = None, None
    if p.attributes:
        projection_expression, expression_attribute_names = _build_projection_expression(p.attributes)

    filter_expr, expression_attribute_values, expression_attribute_names = _parse_filter_expressions(
        p.filter_expr, p.filter_values, p.filter_names, expression_attribute_names
    )

    use_query, key_condition, filter_expr, index, multi_query_mode, query_configs = _auto_detect_query_strategy(
        exporter, filter_expr, p.index, p.key_condition, expression_attribute_names, expression_attribute_values
    )

    use_parallel, segments = _auto_tune_parallel_scan(exporter, use_query, p.dry_run, p.parallel_scan, p.segments)

    console.print(f"\n[bold]Starting export of table '{p.table_name}'...[/bold]\n")

    table_info = exporter.get_table_info()
    ctx = _ScanContext(
        exporter=exporter,
        dynamodb_client=dynamodb_client,
        table_name=p.table_name,
        use_query=use_query,
        use_parallel=use_parallel,
        multi_query_mode=multi_query_mode,
        query_configs=query_configs,
        key_condition=key_condition,
        filter_expr=filter_expr,
        projection_expression=projection_expression,
        index=index,
        limit=p.limit,
        segments=segments,
        expression_attribute_values=expression_attribute_values,
        expression_attribute_names=expression_attribute_names,
        table_info=table_info,
        dry_run=p.dry_run,
    )
    items = _fetch_items(ctx)

    if not items:
        console.print("[yellow]⚠ No items found matching criteria[/yellow]")
        return

    if p.dry_run:
        _print_dry_run_summary(
            multi_query_mode, query_configs, use_query, key_condition, filter_expr, use_parallel, segments, p.fmt, p.mode, p.compress, p.limit
        )
        return

    if not p.yes and len(items) > 10000:
        if not click.confirm(f"\n⚠ About to export {len(items):,} items. Continue?", default=True):
            console.print("[yellow]Export cancelled[/yellow]")
            return

    output_path = _resolve_output_path(p.output, p.table_name, p.fmt)
    _validate_write_permissions(output_path)

    if not _warn_large_export(exporter, p.yes, p.dry_run, p.limit):
        console.print("[yellow]Export cancelled[/yellow]")
        return

    actual_output_path = _do_export(
        exporter, items, p.fmt, output_path, p.mode, p.null_value, p.delimiter, p.encoding, p.metadata, p.compress, p.pretty, p.bool_format
    )
    exporter.print_stats(actual_output_path)

    if p.save_template:
        template_config = create_template_from_args(
            table_name=p.table_name,
            output=p.output,
            format=p.fmt,
            region=p.region,
            limit=p.limit,
            attributes=p.attributes,
            filter=filter_expr,
            key_condition=key_condition,
            index=index,
            mode=p.mode,
            null_value=p.null_value,
            delimiter=p.delimiter,
            encoding=p.encoding,
            compress=p.compress,
            metadata=p.metadata,
            pretty=p.pretty,
            parallel_scan=p.parallel_scan,
            segments=segments,
            bool_format=p.bool_format,
        )
        config_manager.save_template(p.save_template, template_config)


def export_table_command(params: ExportParams, use_template: Optional[str]) -> None:  # noqa: PLR0913
    """Export DynamoDB table to CSV, JSON, or JSONL format."""
    config_manager = ExportConfigManager()

    if use_template:
        template = config_manager.get_template(use_template)
        if not template:
            console.print(f"[red]✗ Template '{use_template}' not found[/red]")
            sys.exit(1)
        args = _apply_template(
            template,
            {
                "output": params.output,
                "format": params.fmt,
                "region": params.region,
                "limit": params.limit,
                "attributes": params.attributes,
                "filter": params.filter_expr,
                "filter_values": params.filter_values,
                "filter_names": params.filter_names,
                "key_condition": params.key_condition,
                "index": params.index,
                "mode": params.mode,
                "compress": params.compress,
                "bool_format": params.bool_format,
            },
        )
        from dataclasses import replace

        params = replace(
            params,
            output=args["output"],
            fmt=args["format"],
            region=args["region"],
            limit=args["limit"],
            attributes=args["attributes"],
            filter_expr=args["filter"],
            filter_values=args["filter_values"],
            filter_names=args["filter_names"],
            key_condition=args["key_condition"],
            index=args["index"],
            mode=args["mode"],
            compress=args["compress"],
            bool_format=args["bool_format"],
        )
        console.print(f"[green]✓ Using template '{use_template}'[/green]\n")

    try:
        _run_export_core(params, config_manager)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        console.print(f"[red]✗ AWS Error ({error_code}): {error_message}[/red]")
        sys.exit(1)
    except BotoCoreError as e:
        console.print(f"[red]✗ AWS Connection Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)
