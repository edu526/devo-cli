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


def _match_equality_to_key(
    key_name: str,
    equality_matches: list,
    expression_attribute_names: Optional[Dict[str, str]],
    index_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Return an indexed-attribute entry if any equality match resolves to key_name, else None."""
    for attr, value_placeholder in equality_matches:
        resolved_attr = _resolve_attribute_name(attr, expression_attribute_names)
        if resolved_attr == key_name:
            return {
                "key_attribute": key_name,
                "index_name": index_name,
                "attr_ref": attr,
                "value_ref": value_placeholder,
            }
    return None


def _collect_gsi_indexed_attrs(
    table_info: Dict[str, Any],
    equality_matches: list,
    expression_attribute_names: Optional[Dict[str, str]],
) -> list:
    """Collect indexed attribute entries from active GSIs matching any equality condition."""
    indexed_attrs = []
    for gsi in table_info.get("global_indexes", []):
        if gsi.get("IndexStatus", "ACTIVE") != "ACTIVE":
            continue
        for key in gsi.get("KeySchema", []):
            if key.get("KeyType") == "HASH":
                entry = _match_equality_to_key(key.get("AttributeName"), equality_matches, expression_attribute_names, gsi.get("IndexName"))
                if entry:
                    indexed_attrs.append(entry)
    return indexed_attrs


def _collect_main_table_indexed_attrs(
    table_info: Dict[str, Any],
    equality_matches: list,
    expression_attribute_names: Optional[Dict[str, str]],
) -> list:
    """Collect indexed attribute entries from the main table partition key matching any equality condition."""
    indexed_attrs = []
    for key in table_info.get("key_schema", []):
        if key.get("KeyType") == "HASH":
            entry = _match_equality_to_key(key.get("AttributeName"), equality_matches, expression_attribute_names, None)
            if entry:
                indexed_attrs.append(entry)
    return indexed_attrs


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

    indexed_attrs = _collect_gsi_indexed_attrs(table_info, equality_matches, expression_attribute_names)
    indexed_attrs.extend(_collect_main_table_indexed_attrs(table_info, equality_matches, expression_attribute_names))

    if indexed_attrs:
        return {
            "has_or": True,
            "indexed_attributes": indexed_attrs,
            "filter_expression": filter_expression,
        }

    return None


def _build_equality_conditions(
    equality_matches: list,
    expression_attribute_names: Optional[Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    """Build a map of resolved attribute name -> {attr_ref, value_ref} from equality matches."""
    conditions = {}
    for attr, value_placeholder in equality_matches:
        resolved_attr = _resolve_attribute_name(attr, expression_attribute_names)
        conditions[resolved_attr] = {"attr_ref": attr, "value_ref": value_placeholder}
    return conditions


def _build_index_result(key_name: str, condition_info: dict, filter_expression: str, index_name: Optional[str]) -> Dict[str, Any]:
    """Build the result dict for a matched indexed attribute."""
    key_condition = f"{condition_info['attr_ref']} = {condition_info['value_ref']}"
    remaining_filter = _remove_condition_from_filter(filter_expression, condition_info["attr_ref"], condition_info["value_ref"])
    return {
        "has_or": False,
        "index_name": index_name,
        "key_condition": key_condition,
        "remaining_filter": remaining_filter,
        "key_attribute": key_name,
    }


def _find_gsi_match(
    table_info: Dict[str, Any],
    equality_conditions: Dict[str, Dict[str, str]],
    filter_expression: str,
) -> Optional[Dict[str, Any]]:
    """Check GSIs for a matching hash key in equality_conditions. Returns result dict or None."""
    for gsi in table_info.get("global_indexes", []):
        if gsi.get("IndexStatus", "ACTIVE") != "ACTIVE":
            continue
        for key in gsi.get("KeySchema", []):
            if key.get("KeyType") == "HASH":
                key_name = key.get("AttributeName")
                if key_name in equality_conditions:
                    return _build_index_result(key_name, equality_conditions[key_name], filter_expression, gsi.get("IndexName"))
    return None


def _find_main_table_match(
    table_info: Dict[str, Any],
    equality_conditions: Dict[str, Dict[str, str]],
    filter_expression: str,
) -> Optional[Dict[str, Any]]:
    """Check main table key schema for a matching hash key in equality_conditions. Returns result dict or None."""
    for key in table_info.get("key_schema", []):
        if key.get("KeyType") == "HASH":
            key_name = key.get("AttributeName")
            if key_name in equality_conditions:
                return _build_index_result(key_name, equality_conditions[key_name], filter_expression, None)
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

    equality_conditions = _build_equality_conditions(equality_matches, expression_attribute_names)

    # Check GSIs first (usually more specific)
    gsi_result = _find_gsi_match(table_info, equality_conditions, filter_expression)
    if gsi_result:
        return gsi_result

    # Check table's main partition key
    return _find_main_table_match(table_info, equality_conditions, filter_expression)


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
