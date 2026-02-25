"""Export DynamoDB table command."""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import click
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

from cli_tool.dynamodb.core import DynamoDBExporter, ParallelScanner
from cli_tool.dynamodb.utils import ExportConfigManager, FilterBuilder, create_template_from_args, estimate_export_size, validate_table_exists

console = Console()


def _detect_usable_index(
    filter_expression: str,
    expression_attribute_names: Optional[Dict[str, str]],
    expression_attribute_values: Optional[Dict[str, Any]],
    table_info: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Detect if filter uses an indexed attribute with equality that could be queried.

    Returns dict with:
      - index_name: Name of GSI or None for main table
      - key_condition: KeyConditionExpression to use
      - remaining_filter: FilterExpression for remaining conditions (or None)
      - key_attribute: Name of the indexed attribute
      - has_or: True if filter contains OR (cannot auto-optimize)
    """
    if not filter_expression:
        return None

    # Check for OR conditions - cannot auto-optimize with Query
    # Normalize the expression by removing parentheses and extra spaces for OR detection
    normalized_expr = re.sub(r"[()]", " ", filter_expression)
    normalized_expr = re.sub(r"\s+", " ", normalized_expr)
    has_or = " OR " in normalized_expr.upper()
    if has_or:
        # Still detect indexed attributes for suggestions, but don't auto-optimize
        equality_pattern = r"(#?\w+)\s*=\s*(:\w+)"
        equality_matches = re.findall(equality_pattern, filter_expression)

        if not equality_matches:
            return None

        # Find indexed attributes
        indexed_attrs = []

        # Check GSIs
        for gsi in table_info.get("global_indexes", []):
            # Validate GSI is active
            gsi_status = gsi.get("IndexStatus", "ACTIVE")
            if gsi_status != "ACTIVE":
                continue  # Skip non-active indexes

            key_schema = gsi.get("KeySchema", [])
            for key in key_schema:
                if key.get("KeyType") == "HASH":
                    key_name = key.get("AttributeName")
                    # Check if this key is in the filter
                    for attr, value_placeholder in equality_matches:
                        resolved_attr = attr
                        if attr.startswith("#") and expression_attribute_names:
                            resolved_attr = expression_attribute_names.get(attr, attr)
                        if resolved_attr == key_name:
                            indexed_attrs.append(
                                {
                                    "key_attribute": key_name,
                                    "index_name": gsi.get("IndexName"),
                                    "attr_ref": attr,
                                    "value_ref": value_placeholder,
                                }
                            )

        # Check main table key
        for key in table_info.get("key_schema", []):
            if key.get("KeyType") == "HASH":
                key_name = key.get("AttributeName")
                for attr, value_placeholder in equality_matches:
                    resolved_attr = attr
                    if attr.startswith("#") and expression_attribute_names:
                        resolved_attr = expression_attribute_names.get(attr, attr)
                    if resolved_attr == key_name:
                        indexed_attrs.append(
                            {
                                "key_attribute": key_name,
                                "index_name": None,
                                "attr_ref": attr,
                                "value_ref": value_placeholder,
                            }
                        )

        if indexed_attrs:
            # Return info but mark as having OR
            return {
                "has_or": True,
                "indexed_attributes": indexed_attrs,
                "filter_expression": filter_expression,
            }

        return None

    # No OR - proceed with normal detection
    # Extract equality conditions: "attributeName = :value" or "#attr = :value"
    equality_pattern = r"(#?\w+)\s*=\s*(:\w+)"
    equality_matches = re.findall(equality_pattern, filter_expression)

    if not equality_matches:
        return None

    # Build map of attribute -> value placeholder
    equality_conditions = {}
    for attr, value_placeholder in equality_matches:
        # Resolve attribute name if it's an alias
        resolved_attr = attr
        if attr.startswith("#") and expression_attribute_names:
            resolved_attr = expression_attribute_names.get(attr, attr)

        equality_conditions[resolved_attr] = {
            "attr_ref": attr,  # Original reference (might be #attr)
            "value_ref": value_placeholder,
        }

    # Check GSIs first (usually more specific)
    for gsi in table_info.get("global_indexes", []):
        # Validate GSI is active
        gsi_status = gsi.get("IndexStatus", "ACTIVE")
        if gsi_status != "ACTIVE":
            continue  # Skip non-active indexes

        gsi_name = gsi.get("IndexName")
        key_schema = gsi.get("KeySchema", [])

        for key in key_schema:
            if key.get("KeyType") == "HASH":  # Partition key
                key_name = key.get("AttributeName")
                if key_name in equality_conditions:
                    # Found indexed attribute with equality condition
                    condition_info = equality_conditions[key_name]

                    # Build KeyConditionExpression
                    key_condition = f"{condition_info['attr_ref']} = {condition_info['value_ref']}"

                    # Remove this condition from filter to get remaining filter
                    remaining_filter = filter_expression
                    # Remove the key condition from filter (handle AND/OR)
                    condition_pattern = (
                        rf'\s*(?:AND|OR)?\s*{re.escape(condition_info["attr_ref"])}\s*=\s*{re.escape(condition_info["value_ref"])}\s*(?:AND|OR)?'
                    )
                    remaining_filter = re.sub(condition_pattern, " ", remaining_filter).strip()

                    # Clean up extra AND/OR at start/end
                    remaining_filter = re.sub(r"^\s*(?:AND|OR)\s+", "", remaining_filter)
                    remaining_filter = re.sub(r"\s+(?:AND|OR)\s*$", "", remaining_filter)
                    remaining_filter = remaining_filter.strip()

                    if not remaining_filter or remaining_filter in ("()", ""):
                        remaining_filter = None

                    return {
                        "has_or": False,
                        "index_name": gsi_name,
                        "key_condition": key_condition,
                        "remaining_filter": remaining_filter,
                        "key_attribute": key_name,
                    }

    # Check table's main partition key
    for key in table_info.get("key_schema", []):
        if key.get("KeyType") == "HASH":
            key_name = key.get("AttributeName")
            if key_name in equality_conditions:
                condition_info = equality_conditions[key_name]

                key_condition = f"{condition_info['attr_ref']} = {condition_info['value_ref']}"

                # Remove this condition from filter
                remaining_filter = filter_expression
                condition_pattern = (
                    rf'\s*(?:AND|OR)?\s*{re.escape(condition_info["attr_ref"])}\s*=\s*{re.escape(condition_info["value_ref"])}\s*(?:AND|OR)?'
                )
                remaining_filter = re.sub(condition_pattern, " ", remaining_filter).strip()
                remaining_filter = re.sub(r"^\s*(?:AND|OR)\s+", "", remaining_filter)
                remaining_filter = re.sub(r"\s+(?:AND|OR)\s*$", "", remaining_filter)
                remaining_filter = remaining_filter.strip()

                if not remaining_filter or remaining_filter in ("()", ""):
                    remaining_filter = None

                return {
                    "has_or": False,
                    "index_name": None,  # Use main table
                    "key_condition": key_condition,
                    "remaining_filter": remaining_filter,
                    "key_attribute": key_name,
                }

    return None


def export_table_command(
    profile: Optional[str],
    table_name: str,
    output: Optional[str],
    format: str,
    region: str,
    limit: Optional[int],
    attributes: Optional[str],
    filter: Optional[str],
    filter_values: Optional[str],
    filter_names: Optional[str],
    key_condition: Optional[str],
    index: Optional[str],
    mode: str,
    null_value: str,
    delimiter: str,
    encoding: str,
    compress: Optional[str],
    metadata: bool,
    pretty: bool,
    parallel_scan: bool,
    segments: int,
    dry_run: bool,
    yes: bool,
    save_template: Optional[str],
    use_template: Optional[str],
    bool_format: str,
) -> None:
    """Export DynamoDB table to CSV, JSON, or JSONL format."""
    # Handle template operations
    config_manager = ExportConfigManager()

    # Load template if specified
    if use_template:
        template = config_manager.get_template(use_template)
        if not template:
            console.print(f"[red]✗ Template '{use_template}' not found[/red]")
            sys.exit(1)

        # Apply template values (command line args override template)
        if not output:
            output = template.get("output")
        if format == "csv":  # default value
            format = template.get("format", "csv")
        if region == "us-east-1":  # default value
            region = template.get("region", "us-east-1")
        if not limit:
            limit = template.get("limit")
        if not attributes:
            attributes = template.get("attributes")
        if not filter:
            filter = template.get("filter")
        if not filter_values:
            filter_values = template.get("filter_values")
        if not filter_names:
            filter_names = template.get("filter_names")
        if not key_condition:
            key_condition = template.get("key_condition")
        if not index:
            index = template.get("index")
        if mode == "strings":  # default value
            mode = template.get("mode", "strings")
        if not compress:
            compress = template.get("compress")
        if bool_format == "lowercase":  # default value
            bool_format = template.get("bool_format", "lowercase")

        console.print(f"[green]✓ Using template '{use_template}'[/green]\n")

    try:
        # Initialize AWS session
        session = boto3.Session(profile_name=profile, region_name=region)
        dynamodb_client = session.client("dynamodb")

        # Validate table exists
        if not validate_table_exists(dynamodb_client, table_name):
            sys.exit(1)

        # Initialize exporter
        exporter = DynamoDBExporter(
            table_name=table_name,
            dynamodb_client=dynamodb_client,
            region=region,
            profile=profile,
        )

        # Show table info before export
        if not yes and not dry_run:
            estimate_export_size(exporter)

        # Prepare projection expression
        projection_expression = None
        if attributes:
            projection_expression = attributes.replace(",", ", ")

        # Parse filter values and names
        expression_attribute_values = None
        expression_attribute_names = None

        # Use FilterBuilder if simple filter syntax is provided
        if filter and not filter_values:
            filter_builder = FilterBuilder()
            try:
                filter, expression_attribute_values, expression_attribute_names = filter_builder.build_filter(filter)
            except Exception as e:
                console.print(f"[red]✗ Invalid filter syntax: {e}[/red]")
                sys.exit(1)
        elif filter_values:
            # Manual mode: user provides filter-values
            try:
                expression_attribute_values = json.loads(filter_values)
            except json.JSONDecodeError as e:
                console.print(f"[red]✗ Invalid filter-values JSON: {e}[/red]")
                sys.exit(1)

        if filter_names and not expression_attribute_names:
            try:
                expression_attribute_names = json.loads(filter_names)
            except json.JSONDecodeError as e:
                console.print(f"[red]✗ Invalid filter-names JSON: {e}[/red]")
                sys.exit(1)

        # Smart detection: Auto-detect if we should use query or scan
        use_query = key_condition is not None
        use_parallel = parallel_scan
        auto_detected_index = None
        multi_query_mode = False
        query_configs = []

        # Auto-detect index if filtering by indexed attribute with equality
        if not use_query and filter and not index:
            table_info = exporter.get_table_info()

            # Try to detect if filter uses an indexed attribute with equality
            auto_detected_index = _detect_usable_index(filter, expression_attribute_names, expression_attribute_values, table_info)

            if auto_detected_index:
                if auto_detected_index.get("has_or"):
                    # Filter contains OR - check if we can do multiple queries
                    indexed_attrs = auto_detected_index.get("indexed_attributes", [])

                    # Check if it's a simple OR with only equality conditions on indexed attributes
                    # Pattern: "attr1 = val1 OR attr2 = val2"
                    or_parts = re.split(r"\s+(?:OR|or)\s+", filter)
                    can_multi_query = len(or_parts) == len(indexed_attrs) and len(or_parts) <= 5  # Max 5 queries

                    if can_multi_query and len(indexed_attrs) >= 2:
                        # We can do multiple queries!
                        console.print(f"[green]✓ Detected OR condition with {len(indexed_attrs)} indexed attributes[/green]")
                        console.print("[cyan]  Using multiple queries for optimal performance[/cyan]")

                        # Build query configs for each indexed attribute
                        for attr_info in indexed_attrs:
                            query_config = {
                                "key_condition": f"{attr_info['attr_ref']} = {attr_info['value_ref']}",
                                "index_name": attr_info.get("index_name"),
                                "key_attribute": attr_info["key_attribute"],
                            }
                            query_configs.append(query_config)
                            index_display = f"GSI: {query_config['index_name']}" if query_config["index_name"] else "main table"
                            console.print(f"[cyan]    Query {len(query_configs)}: {attr_info['key_attribute']} ({index_display})[/cyan]")

                        multi_query_mode = True
                        use_query = True
                    else:
                        # Cannot optimize - use scan
                        console.print("[yellow]ℹ Filter contains OR condition with indexed attributes[/yellow]")
                        if indexed_attrs:
                            console.print(f"[yellow]  Detected indexed attributes: {', '.join([a['key_attribute'] for a in indexed_attrs])}[/yellow]")
                            console.print("[yellow]  Tip: For better performance, run separate queries:[/yellow]")
                            for attr_info in indexed_attrs[:2]:  # Show max 2 examples
                                example_cmd = f"devo dynamodb export {table_name} --key-condition \"{attr_info['key_attribute']} = <value>\""
                                if attr_info.get("index_name"):
                                    example_cmd += f" --index \"{attr_info['index_name']}\""
                                console.print(f"[yellow]    {example_cmd}[/yellow]")
                        console.print("[yellow]  Using Scan with full filter[/yellow]")
                else:
                    # No OR - can auto-optimize
                    console.print(f"[green]✓ Auto-detected indexed attribute '{auto_detected_index['key_attribute']}' with equality filter[/green]")
                    console.print("[cyan]  Switching to Query for optimal performance[/cyan]")

                    if auto_detected_index.get("index_name"):
                        console.print(f"[cyan]  Using GSI: {auto_detected_index['index_name']}[/cyan]")
                        index = auto_detected_index["index_name"]

                    # Use the detected key condition
                    key_condition = auto_detected_index["key_condition"]
                    use_query = True

                    # Update filter to only remaining conditions
                    if auto_detected_index["remaining_filter"]:
                        filter = auto_detected_index["remaining_filter"]
                        console.print(f"[cyan]  Additional filter: {filter}[/cyan]")
                    else:
                        filter = None
                        console.print("[cyan]  No additional filters needed[/cyan]")
        # Auto-enable parallel scan for large tables (>100k items) if not using query
        if not use_query and not dry_run:
            table_info = exporter.get_table_info()
            item_count = table_info.get("item_count", 0)

            if item_count > 100000 and not use_parallel:
                console.print(f"[yellow]ℹ Table has {item_count:,} items. Auto-enabling parallel scan for better performance.[/yellow]")
                use_parallel = True
                if segments == 4:  # default value
                    # Auto-adjust segments based on table size
                    if item_count > 1000000:
                        segments = 16
                    elif item_count > 500000:
                        segments = 12
                    else:
                        segments = 8
                    console.print(f"[yellow]ℹ Using {segments} parallel segments.[/yellow]")

        # Scan or query table
        console.print(f"\n[bold]Starting export of table '{table_name}'...[/bold]\n")

        if multi_query_mode:
            # Execute multiple queries and combine results
            console.print(f"[cyan]Using Multiple Queries ({len(query_configs)} queries for OR optimization)[/cyan]")

            # Calculate limit per query to avoid reading too much data
            limit_per_query = None
            if limit:
                # Distribute limit across queries with some buffer for deduplication
                limit_per_query = int(limit * 1.5 / len(query_configs)) + 100
                console.print(f"[cyan]  Limit per query: ~{limit_per_query} items (total limit: {limit})[/cyan]")

            all_items = []
            seen_keys = set()  # Track unique items to avoid duplicates

            # Get table's primary key attributes for deduplication
            table_info = exporter.get_table_info()
            primary_key_attrs = [key["AttributeName"] for key in table_info.get("key_schema", [])]

            for idx, query_config in enumerate(query_configs, 1):
                console.print(f"\n[cyan]Executing query {idx}/{len(query_configs)}...[/cyan]")

                # Extract only the values needed for this specific query
                query_values = {}
                if expression_attribute_values:
                    # Find which value placeholder is used in this key condition
                    value_placeholder = query_config["key_condition"].split("=")[1].strip()
                    if value_placeholder in expression_attribute_values:
                        query_values[value_placeholder] = expression_attribute_values[value_placeholder]

                try:
                    query_items = exporter.query_table(
                        key_condition_expression=query_config["key_condition"],
                        filter_expression=None,  # OR conditions don't have additional filters
                        projection_expression=projection_expression,
                        index_name=query_config.get("index_name"),
                        limit=limit_per_query,  # Apply per-query limit
                        expression_attribute_values=query_values,
                        expression_attribute_names=expression_attribute_names,
                    )

                    # Deduplicate items using primary key attributes
                    for item in query_items:
                        # Create unique key from primary key attributes only
                        key_parts = []
                        for pk_attr in primary_key_attrs:
                            if pk_attr in item:
                                key_parts.append(f"{pk_attr}={json.dumps(item[pk_attr], sort_keys=True, default=str)}")
                        item_key = "|".join(key_parts)

                        if item_key not in seen_keys:
                            seen_keys.add(item_key)
                            all_items.append(item)

                            # Stop if we've reached the total limit
                            if limit and len(all_items) >= limit:
                                break

                    # Stop querying if we've reached the limit
                    if limit and len(all_items) >= limit:
                        console.print(f"[cyan]Reached limit of {limit} items, stopping remaining queries[/cyan]")
                        break

                except ClientError as e:
                    error_code = e.response["Error"]["Code"]
                    if error_code == "ProvisionedThroughputExceededException":
                        console.print(f"[yellow]⚠ Rate limit exceeded on query {idx}, waiting 1 second...[/yellow]")
                        import time

                        time.sleep(1)
                        # Retry this query
                        query_items = exporter.query_table(
                            key_condition_expression=query_config["key_condition"],
                            filter_expression=None,
                            projection_expression=projection_expression,
                            index_name=query_config.get("index_name"),
                            limit=limit_per_query,
                            expression_attribute_values=query_values,
                            expression_attribute_names=expression_attribute_names,
                        )
                        # Process items (same deduplication logic)
                        for item in query_items:
                            key_parts = []
                            for pk_attr in primary_key_attrs:
                                if pk_attr in item:
                                    key_parts.append(f"{pk_attr}={json.dumps(item[pk_attr], sort_keys=True, default=str)}")
                            item_key = "|".join(key_parts)
                            if item_key not in seen_keys:
                                seen_keys.add(item_key)
                                all_items.append(item)
                                if limit and len(all_items) >= limit:
                                    break
                    else:
                        raise

            console.print(f"\n[green]✓ Combined {len(all_items)} unique items from {len(query_configs)} queries[/green]")

            # Apply final limit if needed
            if limit and len(all_items) > limit:
                all_items = all_items[:limit]
                console.print(f"[cyan]Applied final limit: {limit} items[/cyan]")

            items = all_items

        elif use_query:
            # Use query
            console.print("[cyan]Using Query (efficient partition key lookup)[/cyan]")
            items = exporter.query_table(
                key_condition_expression=key_condition,
                filter_expression=filter,
                projection_expression=projection_expression,
                index_name=index,
                limit=limit,
                expression_attribute_values=expression_attribute_values,
                expression_attribute_names=expression_attribute_names,
            )
        elif use_parallel and not dry_run:
            # Parallel scan
            console.print(f"[cyan]Using Parallel Scan ({segments} segments for faster export)[/cyan]")
            scanner = ParallelScanner(
                dynamodb_client=dynamodb_client,
                table_name=table_name,
                total_segments=segments,
            )
            items = scanner.parallel_scan(
                filter_expression=filter,
                projection_expression=projection_expression,
                index_name=index,
                limit=limit,
                expression_attribute_values=expression_attribute_values,
                expression_attribute_names=expression_attribute_names,
            )
        else:
            # Regular scan
            console.print("[cyan]Using Regular Scan (reading entire table)[/cyan]")
            items = exporter.scan_table(
                limit=limit,
                filter_expression=filter,
                projection_expression=projection_expression,
                index_name=index,
                expression_attribute_values=expression_attribute_values,
                expression_attribute_names=expression_attribute_names,
            )

        if not items:
            console.print("[yellow]⚠ No items found matching criteria[/yellow]")
            return

        # Dry run - show what would be exported
        if dry_run:
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
            return

        # Confirm for large exports
        if not yes and len(items) > 10000:
            if not click.confirm(
                f"\n⚠ About to export {len(items):,} items. Continue?",
                default=True,
            ):
                console.print("[yellow]Export cancelled[/yellow]")
                return

        # Determine output file
        if not output:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = "csv" if format == "csv" else "tsv" if format == "tsv" else "jsonl" if format == "jsonl" else "json"
            output = f"{table_name}_{timestamp}.{extension}"

        output_path = Path(output)

        # Validate write permissions before starting export
        try:
            # Try to create/open the file to check permissions
            test_file = output_path.parent / f".{output_path.name}.test"
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            console.print(f"[red]✗ Cannot write to {output_path}: {e}[/red]")
            console.print("[yellow]Check directory permissions or choose a different output path[/yellow]")
            sys.exit(1)

        # Warn about long-running exports
        if not yes and not dry_run and not limit:
            table_info = exporter.get_table_info()
            item_count = table_info.get("item_count", 0)
            if item_count > 1000000:
                estimated_minutes = item_count / 10000  # Rough estimate: 10k items/minute
                console.print(f"[yellow]⚠ Warning: Exporting {item_count:,} items may take ~{estimated_minutes:.0f} minutes[/yellow]")
                console.print("[yellow]  Consider using --limit to export a subset first[/yellow]")
                if not click.confirm("Continue with full export?", default=False):
                    console.print("[yellow]Export cancelled[/yellow]")
                    return

        # Export based on format
        if format in ["csv", "tsv"]:
            csv_delimiter = "\t" if format == "tsv" else delimiter

            exporter.export_to_csv(
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
        else:
            # JSON or JSONL
            exporter.export_to_json(
                items=items,
                output_file=output_path,
                jsonl=(format == "jsonl"),
                pretty=pretty,
                encoding=encoding,
                compress=compress,
            )

        # Print statistics
        exporter.print_stats(output_path)

        # Save template if requested
        if save_template:
            template_config = create_template_from_args(
                table_name=table_name,
                output=output,
                format=format,
                region=region,
                limit=limit,
                attributes=attributes,
                filter=filter,
                key_condition=key_condition,
                index=index,
                mode=mode,
                null_value=null_value,
                delimiter=delimiter,
                encoding=encoding,
                compress=compress,
                metadata=metadata,
                pretty=pretty,
                parallel_scan=parallel_scan,
                segments=segments,
                bool_format=bool_format,
            )
            config_manager.save_template(save_template, template_config)

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
