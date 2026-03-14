"""Multi-query execution for OR-optimized DynamoDB queries."""

import json
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from rich.console import Console

console = Console()


def _execute_single_query(
    exporter,
    query_config: Dict[str, Any],
    projection_expression: Optional[str],
    expression_attribute_values: Optional[Dict[str, Any]],
    expression_attribute_names: Optional[Dict[str, str]],
    limit_per_query: Optional[int],
) -> List[Dict[str, Any]]:
    """Execute a single query with retry on throttling."""
    query_values = _extract_query_values(query_config["key_condition"], expression_attribute_values)

    kwargs = dict(
        key_condition_expression=query_config["key_condition"],
        filter_expression=None,
        projection_expression=projection_expression,
        index_name=query_config.get("index_name"),
        limit=limit_per_query,
        expression_attribute_values=query_values,
        expression_attribute_names=expression_attribute_names,
    )

    try:
        return exporter.query_table(**kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
            console.print("[yellow]⚠ Rate limit exceeded, waiting 1 second...[/yellow]")
            import time

            time.sleep(1)
            return exporter.query_table(**kwargs)
        raise


def _deduplicate_items(
    new_items: List[Dict[str, Any]],
    all_items: List[Dict[str, Any]],
    seen_keys: set,
    primary_key_attrs: List[str],
    limit: Optional[int],
) -> bool:
    """Add new items to all_items with deduplication. Returns True if limit reached."""
    for item in new_items:
        item_key = _create_item_key(item, primary_key_attrs)
        if item_key not in seen_keys:
            seen_keys.add(item_key)
            all_items.append(item)
            if limit and len(all_items) >= limit:
                return True
    return False


def execute_multi_query(
    exporter,
    query_configs: List[Dict[str, Any]],
    projection_expression: Optional[str],
    expression_attribute_values: Optional[Dict[str, Any]],
    expression_attribute_names: Optional[Dict[str, str]],
    limit: Optional[int],
    table_info: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Execute multiple queries and combine results with deduplication.

    Args:
      exporter: DynamoDBExporter instance
      query_configs: List of query configurations
      projection_expression: Attributes to project
      expression_attribute_values: Expression attribute values
      expression_attribute_names: Expression attribute names
      limit: Maximum total items to return
      table_info: Table information for deduplication

    Returns:
      List of deduplicated items
    """
    console.print(f"[cyan]Using Multiple Queries ({len(query_configs)} queries for OR optimization)[/cyan]")

    limit_per_query = None
    if limit:
        limit_per_query = int(limit * 1.5 / len(query_configs)) + 100
        console.print(f"[cyan]  Limit per query: ~{limit_per_query} items (total limit: {limit})[/cyan]")

    all_items: List[Dict[str, Any]] = []
    seen_keys: set = set()
    primary_key_attrs = [key["AttributeName"] for key in table_info.get("key_schema", [])]

    for idx, query_config in enumerate(query_configs, 1):
        console.print(f"\n[cyan]Executing query {idx}/{len(query_configs)}...[/cyan]")

        query_items = _execute_single_query(
            exporter,
            query_config,
            projection_expression,
            expression_attribute_values,
            expression_attribute_names,
            limit_per_query,
        )

        limit_reached = _deduplicate_items(query_items, all_items, seen_keys, primary_key_attrs, limit)
        if limit_reached:
            console.print(f"[cyan]Reached limit of {limit} items, stopping remaining queries[/cyan]")
            break

    console.print(f"\n[green]✓ Combined {len(all_items)} unique items from {len(query_configs)} queries[/green]")

    if limit and len(all_items) > limit:
        all_items = all_items[:limit]
        console.print(f"[cyan]Applied final limit: {limit} items[/cyan]")

    return all_items


def _extract_query_values(
    key_condition: str,
    expression_attribute_values: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract only the values needed for a specific query."""
    if not expression_attribute_values:
        return {}

    # Find which value placeholder is used in this key condition
    value_placeholder = key_condition.split("=")[1].strip()

    query_values = {}
    if value_placeholder in expression_attribute_values:
        query_values[value_placeholder] = expression_attribute_values[value_placeholder]

    return query_values


def _create_item_key(item: Dict[str, Any], primary_key_attrs: List[str]) -> str:
    """Create unique key from primary key attributes."""
    key_parts = []
    for pk_attr in primary_key_attrs:
        if pk_attr in item:
            key_parts.append(f"{pk_attr}={json.dumps(item[pk_attr], sort_keys=True, default=str)}")
    return "|".join(key_parts)
