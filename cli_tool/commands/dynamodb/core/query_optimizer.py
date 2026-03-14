"""Query optimization utilities for DynamoDB exports."""

import re
from typing import Any, Dict, Optional


def detect_usable_index(
    filter_expression: str,
    expression_attribute_names: Optional[Dict[str, str]],
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
    normalized_expr = re.sub(r"[()]", " ", filter_expression)
    normalized_expr = re.sub(r"\s+", " ", normalized_expr)
    has_or = " OR " in normalized_expr.upper()

    if has_or:
        return _detect_or_indexed_attributes(
            filter_expression,
            expression_attribute_names,
            table_info,
        )

    # No OR - proceed with normal detection
    return _detect_single_indexed_attribute(
        filter_expression,
        expression_attribute_names,
        table_info,
    )


def _detect_or_indexed_attributes(
    filter_expression: str,
    expression_attribute_names: Optional[Dict[str, str]],
    table_info: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Detect indexed attributes in OR conditions."""
    equality_pattern = r"(#?\w+)\s*=\s*(:\w+)"
    equality_matches = re.findall(equality_pattern, filter_expression)

    if not equality_matches:
        return None

    indexed_attrs = []

    # Check GSIs
    for gsi in table_info.get("global_indexes", []):
        gsi_status = gsi.get("IndexStatus", "ACTIVE")
        if gsi_status != "ACTIVE":
            continue

        key_schema = gsi.get("KeySchema", [])
        for key in key_schema:
            if key.get("KeyType") == "HASH":
                key_name = key.get("AttributeName")
                for attr, value_placeholder in equality_matches:
                    resolved_attr = _resolve_attribute_name(attr, expression_attribute_names)
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
                resolved_attr = _resolve_attribute_name(attr, expression_attribute_names)
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
        return {
            "has_or": True,
            "indexed_attributes": indexed_attrs,
            "filter_expression": filter_expression,
        }

    return None


def _detect_single_indexed_attribute(
    filter_expression: str,
    expression_attribute_names: Optional[Dict[str, str]],
    table_info: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Detect single indexed attribute with equality condition."""
    equality_pattern = r"(#?\w+)\s*=\s*(:\w+)"
    equality_matches = re.findall(equality_pattern, filter_expression)

    if not equality_matches:
        return None

    # Build map of attribute -> value placeholder
    equality_conditions = {}
    for attr, value_placeholder in equality_matches:
        resolved_attr = _resolve_attribute_name(attr, expression_attribute_names)
        equality_conditions[resolved_attr] = {
            "attr_ref": attr,
            "value_ref": value_placeholder,
        }

    # Check GSIs first (usually more specific)
    for gsi in table_info.get("global_indexes", []):
        gsi_status = gsi.get("IndexStatus", "ACTIVE")
        if gsi_status != "ACTIVE":
            continue

        gsi_name = gsi.get("IndexName")
        key_schema = gsi.get("KeySchema", [])

        for key in key_schema:
            if key.get("KeyType") == "HASH":
                key_name = key.get("AttributeName")
                if key_name in equality_conditions:
                    condition_info = equality_conditions[key_name]
                    key_condition = f"{condition_info['attr_ref']} = {condition_info['value_ref']}"
                    remaining_filter = _remove_condition_from_filter(
                        filter_expression,
                        condition_info["attr_ref"],
                        condition_info["value_ref"],
                    )

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
                remaining_filter = _remove_condition_from_filter(
                    filter_expression,
                    condition_info["attr_ref"],
                    condition_info["value_ref"],
                )

                return {
                    "has_or": False,
                    "index_name": None,
                    "key_condition": key_condition,
                    "remaining_filter": remaining_filter,
                    "key_attribute": key_name,
                }

    return None


def _resolve_attribute_name(
    attr: str,
    expression_attribute_names: Optional[Dict[str, str]],
) -> str:
    """Resolve attribute name if it's an alias."""
    if attr.startswith("#") and expression_attribute_names:
        return expression_attribute_names.get(attr, attr)
    return attr


def _remove_condition_from_filter(
    filter_expression: str,
    attr_ref: str,
    value_ref: str,
) -> Optional[str]:
    """Remove a condition from filter expression."""
    condition_pattern = rf"\s*(?:AND|OR)?\s*{re.escape(attr_ref)}\s*=\s*{re.escape(value_ref)}\s*(?:AND|OR)?"
    remaining_filter = re.sub(condition_pattern, " ", filter_expression).strip()

    # Clean up extra AND/OR at start/end
    remaining_filter = re.sub(r"^\s*(?:AND|OR)\s+", "", remaining_filter)
    remaining_filter = re.sub(r"\s+(?:AND|OR)\s*$", "", remaining_filter)
    remaining_filter = remaining_filter.strip()

    if not remaining_filter or remaining_filter in ("()", ""):
        return None

    return remaining_filter


def should_use_parallel_scan(item_count: int, use_parallel: bool) -> tuple[bool, int]:
    """
    Determine if parallel scan should be used and how many segments.

    Args:
      item_count: Number of items in the table
      use_parallel: User's preference for parallel scan

    Returns:
      Tuple of (should_use_parallel, segments)
    """
    if use_parallel:
        # User explicitly requested — auto-tune segments based on table size
        if item_count > 1000000:
            return True, 16
        if item_count > 500000:
            return True, 12
        if item_count > 100000:
            return True, 8
        return True, 4

    # Auto-enable for large tables
    if item_count > 1000000:
        return True, 16
    if item_count > 500000:
        return True, 12
    if item_count > 100000:
        return True, 8

    return False, 4
