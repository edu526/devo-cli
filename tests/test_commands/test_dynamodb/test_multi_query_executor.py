"""Unit tests for DynamoDB multi_query_executor module."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cli_tool.commands.dynamodb.core.multi_query_executor import (
    _create_item_key,
    _deduplicate_items,
    _execute_single_query,
    _extract_query_values,
    execute_multi_query,
)

# ---------------------------------------------------------------------------
# _create_item_key
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateItemKey:
    def test_single_pk_attr(self):
        item = {"id": "abc", "name": "Alice"}
        result = _create_item_key(item, ["id"])
        assert "id=" in result
        assert "abc" in result

    def test_composite_key(self):
        item = {"pk": "user-1", "sk": "profile"}
        result = _create_item_key(item, ["pk", "sk"])
        assert "pk=" in result
        assert "sk=" in result
        assert "|" in result

    def test_missing_attr_skipped(self):
        item = {"pk": "val1"}
        result = _create_item_key(item, ["pk", "sk"])
        assert "pk=" in result
        assert "sk=" not in result

    def test_empty_primary_key_attrs(self):
        item = {"id": "abc"}
        result = _create_item_key(item, [])
        assert result == ""

    def test_empty_item(self):
        result = _create_item_key({}, ["pk"])
        assert result == ""

    def test_key_with_complex_value(self):
        item = {"id": {"nested": "value"}}
        result = _create_item_key(item, ["id"])
        assert "id=" in result


# ---------------------------------------------------------------------------
# _extract_query_values
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractQueryValues:
    def test_extracts_matching_placeholder(self):
        values = {":val0": {"S": "test"}, ":val1": {"N": "42"}}
        result = _extract_query_values("pk = :val0", values)
        assert ":val0" in result
        assert ":val1" not in result

    def test_no_expression_attribute_values(self):
        result = _extract_query_values("pk = :val0", None)
        assert result == {}

    def test_placeholder_not_in_values(self):
        values = {":other": {"S": "test"}}
        result = _extract_query_values("pk = :val0", values)
        assert result == {}

    def test_empty_values(self):
        result = _extract_query_values("pk = :val0", {})
        assert result == {}


# ---------------------------------------------------------------------------
# _deduplicate_items
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeduplicateItems:
    def test_adds_new_items(self):
        items = [{"pk": "a"}, {"pk": "b"}]
        all_items = []
        seen = set()
        result = _deduplicate_items(items, all_items, seen, ["pk"], limit=None)
        assert len(all_items) == 2
        assert result is False

    def test_skips_duplicate_items(self):
        seen = {'pk="a"'}
        item_already_seen = {"pk": "a"}
        item_new = {"pk": "b"}
        all_items = []
        seen_keys = set()
        # Pre-populate seen with item_already_seen key
        from cli_tool.commands.dynamodb.core.multi_query_executor import _create_item_key

        seen_keys.add(_create_item_key(item_already_seen, ["pk"]))
        _deduplicate_items([item_already_seen, item_new], all_items, seen_keys, ["pk"], limit=None)
        assert len(all_items) == 1
        assert all_items[0]["pk"] == "b"

    def test_stops_at_limit(self):
        items = [{"pk": str(i)} for i in range(10)]
        all_items = []
        seen = set()
        result = _deduplicate_items(items, all_items, seen, ["pk"], limit=3)
        assert result is True
        assert len(all_items) == 3

    def test_no_limit(self):
        items = [{"pk": str(i)} for i in range(5)]
        all_items = []
        seen = set()
        result = _deduplicate_items(items, all_items, seen, ["pk"], limit=None)
        assert result is False
        assert len(all_items) == 5

    def test_empty_items(self):
        all_items = []
        seen = set()
        result = _deduplicate_items([], all_items, seen, ["pk"], limit=10)
        assert result is False
        assert len(all_items) == 0


# ---------------------------------------------------------------------------
# _execute_single_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteSingleQuery:
    def test_basic_query(self):
        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = [{"id": {"S": "1"}}]

        query_config = {"key_condition": "pk = :val0", "index_name": None}
        result = _execute_single_query(
            mock_exporter,
            query_config,
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "test"}},
            expression_attribute_names=None,
            limit_per_query=None,
        )

        assert len(result) == 1

    def test_retry_on_throttle(self):
        mock_exporter = MagicMock()
        throttle_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Too many requests",
                }
            },
            operation_name="Query",
        )
        mock_exporter.query_table.side_effect = [
            throttle_error,
            [{"id": {"S": "1"}}],
        ]

        query_config = {"key_condition": "pk = :val0", "index_name": None}
        with patch("time.sleep"):
            result = _execute_single_query(
                mock_exporter,
                query_config,
                projection_expression=None,
                expression_attribute_values={":val0": {"S": "test"}},
                expression_attribute_names=None,
                limit_per_query=5,
            )

        assert mock_exporter.query_table.call_count == 2
        assert len(result) == 1

    def test_non_throttle_error_propagates(self):
        mock_exporter = MagicMock()
        error = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            operation_name="Query",
        )
        mock_exporter.query_table.side_effect = error

        query_config = {"key_condition": "pk = :val0", "index_name": None}
        with pytest.raises(ClientError):
            _execute_single_query(
                mock_exporter,
                query_config,
                projection_expression=None,
                expression_attribute_values={":val0": {"S": "test"}},
                expression_attribute_names=None,
                limit_per_query=None,
            )


# ---------------------------------------------------------------------------
# execute_multi_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteMultiQuery:
    def _make_query_configs(self):
        return [
            {"key_condition": "pk = :val0", "index_name": None},
            {"key_condition": "pk = :val1", "index_name": None},
        ]

    def test_combines_results_from_multiple_queries(self):
        mock_exporter = MagicMock()
        mock_exporter.query_table.side_effect = [
            [{"id": {"S": "1"}}],
            [{"id": {"S": "2"}}],
        ]

        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = execute_multi_query(
            mock_exporter,
            self._make_query_configs(),
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "a"}, ":val1": {"S": "b"}},
            expression_attribute_names=None,
            limit=None,
            table_info=table_info,
        )

        assert len(result) == 2

    def test_deduplicates_overlapping_results(self):
        mock_exporter = MagicMock()
        # Both queries return the same item
        duplicate_item = {"id": {"S": "1"}}
        mock_exporter.query_table.side_effect = [
            [duplicate_item],
            [duplicate_item],
        ]

        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = execute_multi_query(
            mock_exporter,
            self._make_query_configs(),
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "a"}, ":val1": {"S": "b"}},
            expression_attribute_names=None,
            limit=None,
            table_info=table_info,
        )

        assert len(result) == 1

    def test_stops_at_limit(self):
        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = [{"id": {"S": str(i)}} for i in range(5)]

        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = execute_multi_query(
            mock_exporter,
            self._make_query_configs(),
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "a"}, ":val1": {"S": "b"}},
            expression_attribute_names=None,
            limit=3,
            table_info=table_info,
        )

        assert len(result) == 3

    def test_applies_final_limit_trim(self):
        mock_exporter = MagicMock()
        # Return items that cumulatively exceed limit
        mock_exporter.query_table.side_effect = [
            [{"id": {"S": str(i)}} for i in range(3)],
            [{"id": {"S": str(i)}} for i in range(10, 13)],
        ]

        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = execute_multi_query(
            mock_exporter,
            self._make_query_configs(),
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "a"}, ":val1": {"S": "b"}},
            expression_attribute_names=None,
            limit=5,
            table_info=table_info,
        )

        assert len(result) <= 5

    def test_with_limit_calculates_per_query_limit(self):
        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = []

        table_info = {"key_schema": [{"AttributeName": "id"}]}
        execute_multi_query(
            mock_exporter,
            self._make_query_configs(),
            projection_expression=None,
            expression_attribute_values=None,
            expression_attribute_names=None,
            limit=100,
            table_info=table_info,
        )

        # Verify per_query_limit was passed (non-None limit argument)
        first_call_kwargs = mock_exporter.query_table.call_args_list[0][1]
        assert first_call_kwargs.get("limit") is not None

    def test_empty_table_info_key_schema(self):
        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = [{"id": {"S": "1"}}]

        result = execute_multi_query(
            mock_exporter,
            [{"key_condition": "pk = :val0", "index_name": None}],
            projection_expression=None,
            expression_attribute_values={":val0": {"S": "a"}},
            expression_attribute_names=None,
            limit=None,
            table_info={},
        )

        # With no key schema, all items have the same empty key, so only 1 unique
        assert len(result) == 1
