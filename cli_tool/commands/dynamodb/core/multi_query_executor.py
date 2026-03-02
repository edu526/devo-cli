"""Multi-query execution for OR-optimized DynamoDB queries."""

import json
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from rich.console import Console

console = Console()


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

    # Calculate limit per query
    limit_per_query = None
    if limit:
        limit_per_query = int(limit * 1.5 / len(query_configs)) + 100
        console.print(f"[cyan]  Limit per query: ~{limit_per_query} items (total limit: {limit})[/cyan]")

    all_items = []
    seen_keys = set()

    # Get primary key attributes for deduplication
    primary_key_attrs = [key["AttributeName"] for key in table_info.get("key_schema", [])]

    for idx, query_config in enumerate(query_configs, 1):
        console.print(f"\n[cyan]Executing query {idx}/{len(query_configs)}...[/cyan]")

        # Extract values for this specific query
        query_values = _extract_query_values(
            query_config["key_condition"],
            expression_attribute_values,
        )

        try:
            query_items = exporter.query_table(
                key_condition_expression=query_config["key_condition"],
                filter_expression=None,
                projection_expression=projection_expression,
                index_name=query_config.get("index_name"),
                limit=limit_per_query,
                expression_attribute_values=query_values,
                expression_attribute_names=expression_attribute_names,
            )

            # Deduplicate items
            for item in query_items:
                item_key = _create_item_key(item, primary_key_attrs)

                if item_key not in seen_keys:
                    seen_keys.add(item_key)
                    all_items.append(item)

                    if limit and len(all_items) >= limit:
                        break

            # Stop if we've reached the limit
            if limit and len(all_items) >= limit:
                console.print(f"[cyan]Reached limit of {limit} items, stopping remaining queries[/cyan]")
                break

        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                console.print(f"[yellow]⚠ Rate limit exceeded on query {idx}, waiting 1 second...[/yellow]")
                import time

                time.sleep(1)

                # Retry
                query_items = exporter.query_table(
                    key_condition_expression=query_config["key_condition"],
                    filter_expression=None,
                    projection_expression=projection_expression,
                    index_name=query_config.get("index_name"),
                    limit=limit_per_query,
                    expression_attribute_values=query_values,
                    expression_attribute_names=expression_attribute_names,
                )

                # Deduplicate retry results
                for item in query_items:
                    item_key = _create_item_key(item, primary_key_attrs)
                    if item_key not in seen_keys:
                        seen_keys.add(item_key)
                        all_items.append(item)
                        if limit and len(all_items) >= limit:
                            break
            else:
                raise

    console.print(f"\n[green]✓ Combined {len(all_items)} unique items from {len(query_configs)} queries[/green]")

    # Apply final limit
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
