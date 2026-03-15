"""Unit tests for DynamoDB export_table command module."""

import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.commands.export_table import (
    ExportParams,
    _append_unique_items,
    _apply_template,
    _auto_detect_query_strategy,
    _auto_tune_parallel_scan,
    _build_item_key,
    _build_projection_expression,
    _build_query_configs,
    _collect_names_from_expr,
    _collect_query_names,
    _collect_query_values,
    _do_export,
    _execute_multi_query,
    _execute_query_with_retry,
    _extract_remaining_filter,
    _fetch_items,
    _handle_or_detection,
    _parse_filter_expressions,
    _print_dry_run_summary,
    _print_or_scan_warning,
    _resolve_output_path,
    _ScanContext,
    _validate_write_permissions,
    _warn_large_export,
    export_table_command,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_export_params(**overrides):
    """Return a minimal ExportParams instance with safe defaults."""
    defaults = dict(
        profile=None,
        table_name="my-table",
        output=None,
        fmt="json",
        region="us-east-1",
        limit=None,
        attributes=None,
        filter_expr=None,
        filter_values=None,
        filter_names=None,
        key_condition=None,
        index=None,
        mode="strings",
        null_value="",
        delimiter=",",
        encoding="utf-8",
        compress=None,
        metadata=False,
        pretty=True,
        parallel_scan=False,
        segments=4,
        dry_run=False,
        yes=True,
        save_template=None,
        bool_format="lowercase",
    )
    defaults.update(overrides)
    return ExportParams(**defaults)


# ---------------------------------------------------------------------------
# _apply_template
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApplyTemplate:
    def test_template_fills_missing_args(self):
        template = {"format": "csv", "region": "eu-west-1", "limit": 100}
        args = {"output": None, "format": "csv", "region": "us-east-1", "mode": "strings", "bool_format": "lowercase"}
        result = _apply_template(template, args)
        assert result["limit"] == 100

    def test_cli_args_take_precedence_over_template(self):
        template = {"format": "csv"}
        args = {"output": "my.csv", "format": "json", "region": "us-east-1", "mode": "strings", "bool_format": "lowercase"}
        result = _apply_template(template, args)
        # output is not a default so it should stay
        assert result["output"] == "my.csv"

    def test_template_provides_compress(self):
        template = {"compress": "gzip"}
        args = {"output": None, "format": "csv", "region": "us-east-1", "mode": "strings", "bool_format": "lowercase"}
        result = _apply_template(template, args)
        assert result["compress"] == "gzip"

    def test_empty_template_keeps_defaults(self):
        template = {}
        args = {"output": None, "format": "csv", "region": "us-east-1", "mode": "strings", "bool_format": "lowercase"}
        result = _apply_template(template, args)
        assert result["format"] == "csv"


# ---------------------------------------------------------------------------
# _build_projection_expression
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildProjectionExpression:
    def test_no_reserved_keywords_returns_unescaped(self):
        expr, names = _build_projection_expression("pk, sk, email")
        assert "pk" in expr
        assert names is None

    def test_reserved_keyword_escaped(self):
        expr, names = _build_projection_expression("name")
        assert "#name" in expr
        assert names == {"#name": "name"}

    def test_mixed_attributes(self):
        expr, names = _build_projection_expression("pk,name,email")
        assert "#name" in expr
        assert "pk" in expr
        assert names is not None
        assert "#name" in names

    def test_multiple_reserved_keywords(self):
        expr, names = _build_projection_expression("name,status,pk")
        assert names is not None
        assert len(names) >= 2


# ---------------------------------------------------------------------------
# _parse_filter_expressions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseFilterExpressions:
    def test_no_filter_returns_none(self):
        fe, vals, names = _parse_filter_expressions(None, None, None, None)
        assert fe is None
        assert vals is None

    def test_filter_values_json_parsed(self):
        fe, vals, names = _parse_filter_expressions(
            "status = :s",
            '{":s": "active"}',
            None,
            None,
        )
        assert vals is not None
        assert ":s" in vals

    def test_filter_values_already_dynamodb_format(self):
        fe, vals, names = _parse_filter_expressions(
            "status = :s",
            '{":s": {"S": "active"}}',
            None,
            None,
        )
        assert vals[":s"] == {"S": "active"}

    def test_filter_names_json_parsed(self):
        fe, vals, names = _parse_filter_expressions(
            "#n = :v",
            None,
            '{"#n": "name"}',
            None,
        )
        assert names == {"#n": "name"}

    def test_filter_names_applied_only_when_not_already_set(self):
        # When expression_attribute_names is None, filter_names JSON is applied
        fe, vals, names = _parse_filter_expressions(
            None,
            None,
            '{"#n": "name"}',
            None,
        )
        # expression_attribute_names was None, so filter_names is applied
        assert names == {"#n": "name"}

    def test_invalid_filter_values_json_exits(self):
        with pytest.raises(SystemExit):
            _parse_filter_expressions("s = :s", "not-json", None, None)

    def test_invalid_filter_names_json_exits(self):
        with pytest.raises(SystemExit):
            _parse_filter_expressions(None, None, "not-json", None)

    def test_filter_expression_without_values_uses_filter_builder(self):
        with patch("cli_tool.commands.dynamodb.commands.export_table.FilterBuilder") as mock_fb_cls:
            mock_fb = MagicMock()
            mock_fb.build_filter.return_value = ("built_expr", {":v": {"S": "x"}}, None)
            mock_fb_cls.return_value = mock_fb
            fe, vals, names = _parse_filter_expressions("status = active", None, None, None)
        assert fe == "built_expr"

    def test_filter_builder_exception_exits(self):
        with patch("cli_tool.commands.dynamodb.commands.export_table.FilterBuilder") as mock_fb_cls:
            mock_fb = MagicMock()
            mock_fb.build_filter.side_effect = ValueError("bad filter")
            mock_fb_cls.return_value = mock_fb
            with pytest.raises(SystemExit):
                _parse_filter_expressions("bad filter", None, None, None)


# ---------------------------------------------------------------------------
# _build_item_key
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildItemKey:
    def test_single_key_attribute(self):
        item = {"pk": "val1", "sk": "val2"}
        key = _build_item_key(item, ["pk"])
        assert "pk" in key
        assert "val1" in key

    def test_composite_key(self):
        item = {"pk": "A", "sk": "B"}
        key = _build_item_key(item, ["pk", "sk"])
        assert "|" in key

    def test_missing_key_attribute_ignored(self):
        item = {"pk": "A"}
        key = _build_item_key(item, ["pk", "missing"])
        assert "pk" in key
        assert "missing" not in key


# ---------------------------------------------------------------------------
# _collect_names_from_expr
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectNamesFromExpr:
    def test_returns_matching_names(self):
        result = _collect_names_from_expr("#n = :v", {"#n": "name", "#s": "status"})
        assert result == {"#n": "name"}

    def test_empty_expr_returns_empty(self):
        result = _collect_names_from_expr(None, {"#n": "name"})
        assert result == {}

    def test_no_matching_names_returns_empty(self):
        result = _collect_names_from_expr("a = b", {"#n": "name"})
        assert result == {}


# ---------------------------------------------------------------------------
# _collect_query_names and _collect_query_values
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectQueryNamesAndValues:
    def test_collect_query_names_no_names(self):
        qc = {"key_condition": "#pk = :pk"}
        result = _collect_query_names(qc, None, None)
        assert result == {}

    def test_collect_query_names_with_matching(self):
        qc = {"key_condition": "#pk = :pk"}
        result = _collect_query_names(qc, {"#pk": "pk", "#sk": "sk"}, None)
        assert "#pk" in result

    def test_collect_query_values_no_values(self):
        qc = {"key_condition": "pk = :pk"}
        result = _collect_query_values(qc, None)
        assert result == {}

    def test_collect_query_values_with_matching(self):
        qc = {"key_condition": "pk = :pk"}
        result = _collect_query_values(qc, {":pk": {"S": "val"}, ":other": {"S": "x"}})
        assert ":pk" in result

    def test_collect_query_values_with_filter_expression(self):
        qc = {"key_condition": "pk = :pk", "filter_expression": "sk > :sk"}
        result = _collect_query_values(qc, {":pk": {"S": "val"}, ":sk": {"N": "5"}})
        assert ":sk" in result


# ---------------------------------------------------------------------------
# _execute_query_with_retry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteQueryWithRetry:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_successful_query(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

        mock_client = MagicMock()
        mock_client.query.return_value = {"Items": [{"id": {"S": "1"}}]}
        exporter = DynamoDBExporter("tbl", mock_client, "us-east-1")

        qc = {"key_condition": "pk = :pk"}
        result = _execute_query_with_retry(exporter, qc, None, None, None, None)
        assert len(result) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_retry_on_throughput_exceeded(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from botocore.exceptions import ClientError

        from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

        mock_client = MagicMock()
        throttle_error = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "throttled"}},
            "Query",
        )
        mock_client.query.side_effect = [throttle_error, {"Items": [{"id": {"S": "2"}}]}]
        exporter = DynamoDBExporter("tbl", mock_client, "us-east-1")

        with patch("time.sleep"):
            qc = {"key_condition": "pk = :pk"}
            result = _execute_query_with_retry(exporter, qc, None, None, None, None)
        assert len(result) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_non_throughput_error_raises(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from botocore.exceptions import ClientError

        from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

        mock_client = MagicMock()
        error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "Query")
        mock_client.query.side_effect = error
        exporter = DynamoDBExporter("tbl", mock_client, "us-east-1")

        qc = {"key_condition": "pk = :pk"}
        with pytest.raises(ClientError):
            _execute_query_with_retry(exporter, qc, None, None, None, None)


# ---------------------------------------------------------------------------
# _append_unique_items
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAppendUniqueItems:
    def test_appends_new_items(self):
        all_items = []
        seen_keys = set()
        query_items = [{"pk": "A"}, {"pk": "B"}]
        limit_reached = _append_unique_items(all_items, seen_keys, query_items, ["pk"], None)
        assert len(all_items) == 2
        assert not limit_reached

    def test_deduplicates_items(self):
        all_items = []
        seen_keys = set()
        query_items = [{"pk": "A"}, {"pk": "A"}, {"pk": "B"}]
        _append_unique_items(all_items, seen_keys, query_items, ["pk"], None)
        assert len(all_items) == 2

    def test_returns_true_when_limit_reached(self):
        all_items = []
        seen_keys = set()
        query_items = [{"pk": str(i)} for i in range(10)]
        limit_reached = _append_unique_items(all_items, seen_keys, query_items, ["pk"], 5)
        assert limit_reached
        assert len(all_items) == 5


# ---------------------------------------------------------------------------
# _execute_multi_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExecuteMultiQuery:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_combines_results_from_multiple_queries(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

        mock_client = MagicMock()
        mock_client.query.side_effect = [
            {"Items": [{"id": {"S": "1"}}]},
            {"Items": [{"id": {"S": "2"}}]},
        ]
        exporter = DynamoDBExporter("tbl", mock_client, "us-east-1")

        query_configs = [
            {"key_condition": "pk = :pk1"},
            {"key_condition": "pk = :pk2"},
        ]
        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = _execute_multi_query(exporter, query_configs, None, None, None, None, table_info)
        assert len(result) == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_applies_limit_after_combine(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

        mock_client = MagicMock()
        mock_client.query.side_effect = [
            {"Items": [{"id": {"S": str(i)}} for i in range(5)]},
            {"Items": [{"id": {"S": str(i)}} for i in range(5, 10)]},
        ]
        exporter = DynamoDBExporter("tbl", mock_client, "us-east-1")

        query_configs = [
            {"key_condition": "pk = :pk1"},
            {"key_condition": "pk = :pk2"},
        ]
        table_info = {"key_schema": [{"AttributeName": "id"}]}
        result = _execute_multi_query(exporter, query_configs, None, None, None, 3, table_info)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# _auto_detect_query_strategy
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutoDetectQueryStrategy:
    def test_key_condition_uses_query(self):
        mock_exporter = MagicMock()
        use_query, kc, fe, idx, mq, qc = _auto_detect_query_strategy(mock_exporter, None, None, "pk = :pk", None, None)
        assert use_query is True
        assert not mq

    def test_no_filter_returns_scan(self):
        mock_exporter = MagicMock()
        use_query, kc, fe, idx, mq, qc = _auto_detect_query_strategy(mock_exporter, None, None, None, None, None)
        assert use_query is False

    def test_with_index_skips_auto_detection(self):
        mock_exporter = MagicMock()
        use_query, kc, fe, idx, mq, qc = _auto_detect_query_strategy(mock_exporter, "status = :s", "my-index", None, None, None)
        assert use_query is False

    def test_auto_detects_index_for_filter(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {
            "key_schema": [{"AttributeName": "pk", "KeyType": "HASH"}],
            "global_indexes": [],
        }
        with patch("cli_tool.commands.dynamodb.commands.export_table.detect_usable_index") as mock_detect:
            mock_detect.return_value = None
            use_query, kc, fe, idx, mq, qc = _auto_detect_query_strategy(mock_exporter, "status = :s", None, None, None, None)
        assert use_query is False

    def test_auto_detects_non_or_index(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {}
        with patch("cli_tool.commands.dynamodb.commands.export_table.detect_usable_index") as mock_detect:
            mock_detect.return_value = {
                "has_or": False,
                "key_attribute": "status",
                "key_condition": "status = :s",
                "remaining_filter": None,
                "index_name": "status-index",
            }
            use_query, kc, fe, idx, mq, qc = _auto_detect_query_strategy(mock_exporter, "status = :s", None, None, None, None)
        assert use_query is True
        assert idx == "status-index"

    def test_auto_detects_or_condition(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {}
        with patch("cli_tool.commands.dynamodb.commands.export_table.detect_usable_index") as mock_detect:
            mock_detect.return_value = {
                "has_or": True,
                "indexed_attributes": [
                    {"attr_ref": "#s", "value_ref": ":s1", "key_attribute": "status", "index_name": "idx"},
                    {"attr_ref": "#s", "value_ref": ":s2", "key_attribute": "status", "index_name": "idx"},
                ],
            }
            with patch("cli_tool.commands.dynamodb.commands.export_table._handle_or_detection") as mock_handle:
                mock_handle.return_value = (True, True, [{"key_condition": "q1"}, {"key_condition": "q2"}])
                use_query, kc, fe, idx, mq, qcs = _auto_detect_query_strategy(mock_exporter, "a = :a OR b = :b", None, None, None, None)
        assert mq is True


# ---------------------------------------------------------------------------
# _auto_tune_parallel_scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutoTuneParallelScan:
    def test_query_mode_skips_tuning(self):
        mock_exporter = MagicMock()
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, True, False, False, 4)
        assert use_p is False
        assert segs == 4
        mock_exporter.get_table_info.assert_not_called()

    def test_dry_run_skips_tuning(self):
        mock_exporter = MagicMock()
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, True, False, 4)
        assert use_p is False
        mock_exporter.get_table_info.assert_not_called()

    def test_already_parallel_skips_tuning(self):
        mock_exporter = MagicMock()
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, False, True, 8)
        assert use_p is True
        mock_exporter.get_table_info.assert_not_called()

    def test_small_table_no_parallel(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 1000}
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, False, False, 4)
        assert use_p is False

    def test_large_table_enables_parallel_with_500k(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 600000}
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, False, False, 4)
        assert use_p is True
        assert segs == 12

    def test_large_table_enables_parallel_with_1m(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 1500000}
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, False, False, 4)
        assert use_p is True
        assert segs == 16

    def test_large_table_enables_parallel_100k_500k(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 200000}
        use_p, segs = _auto_tune_parallel_scan(mock_exporter, False, False, False, 4)
        assert use_p is True
        assert segs == 8


# ---------------------------------------------------------------------------
# _fetch_items
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFetchItems:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_multi_query_mode(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = [{"id": {"S": "1"}}]

        ctx = _ScanContext(
            exporter=mock_exporter,
            dynamodb_client=MagicMock(),
            table_name="tbl",
            use_query=False,
            use_parallel=False,
            multi_query_mode=True,
            query_configs=[{"key_condition": "pk = :pk"}],
            key_condition=None,
            filter_expr=None,
            projection_expression=None,
            index=None,
            limit=None,
            segments=4,
            expression_attribute_values=None,
            expression_attribute_names=None,
            table_info={"key_schema": []},
            dry_run=False,
        )

        with patch("cli_tool.commands.dynamodb.commands.export_table._execute_multi_query") as mock_mq:
            mock_mq.return_value = [{"id": "1"}]
            result = _fetch_items(ctx)
        assert result == [{"id": "1"}]
        mock_mq.assert_called_once()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_query_mode(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        mock_exporter = MagicMock()
        mock_exporter.query_table.return_value = [{"id": {"S": "1"}}]

        ctx = _ScanContext(
            exporter=mock_exporter,
            dynamodb_client=MagicMock(),
            table_name="tbl",
            use_query=True,
            use_parallel=False,
            multi_query_mode=False,
            query_configs=[],
            key_condition="pk = :pk",
            filter_expr=None,
            projection_expression=None,
            index=None,
            limit=None,
            segments=4,
            expression_attribute_values=None,
            expression_attribute_names=None,
            table_info={},
            dry_run=False,
        )
        result = _fetch_items(ctx)
        mock_exporter.query_table.assert_called_once()
        assert result == [{"id": {"S": "1"}}]

    def test_parallel_scan_mode(self):
        mock_exporter = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.parallel_scan.return_value = [{"id": {"S": "1"}}]

        ctx = _ScanContext(
            exporter=mock_exporter,
            dynamodb_client=MagicMock(),
            table_name="tbl",
            use_query=False,
            use_parallel=True,
            multi_query_mode=False,
            query_configs=[],
            key_condition=None,
            filter_expr=None,
            projection_expression=None,
            index=None,
            limit=None,
            segments=4,
            expression_attribute_values=None,
            expression_attribute_names=None,
            table_info={},
            dry_run=False,
        )
        with patch("cli_tool.commands.dynamodb.commands.export_table.ParallelScanner") as mock_scanner_cls:
            mock_scanner_cls.return_value = mock_scanner
            result = _fetch_items(ctx)
        assert result == [{"id": {"S": "1"}}]

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_regular_scan_mode(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        mock_exporter = MagicMock()
        mock_exporter.scan_table.return_value = [{"id": {"S": "1"}}]

        ctx = _ScanContext(
            exporter=mock_exporter,
            dynamodb_client=MagicMock(),
            table_name="tbl",
            use_query=False,
            use_parallel=False,
            multi_query_mode=False,
            query_configs=[],
            key_condition=None,
            filter_expr=None,
            projection_expression=None,
            index=None,
            limit=None,
            segments=4,
            expression_attribute_values=None,
            expression_attribute_names=None,
            table_info={},
            dry_run=False,
        )
        result = _fetch_items(ctx)
        mock_exporter.scan_table.assert_called_once()
        assert result == [{"id": {"S": "1"}}]


# ---------------------------------------------------------------------------
# _print_dry_run_summary
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintDryRunSummary:
    def test_multi_query_summary(self):
        qc = [{"key_attribute": "pk", "index_name": None}]
        # Should not raise
        _print_dry_run_summary(True, qc, False, None, None, False, 4, "json", "strings", None, None)

    def test_use_query_summary(self):
        _print_dry_run_summary(False, [], True, "pk = :pk", "status = :s", False, 4, "csv", "flatten", "gzip", 100)

    def test_parallel_scan_summary(self):
        _print_dry_run_summary(False, [], False, None, None, True, 8, "jsonl", "strings", None, None)

    def test_regular_scan_summary(self):
        _print_dry_run_summary(False, [], False, None, None, False, 4, "tsv", "strings", None, 50)


# ---------------------------------------------------------------------------
# _resolve_output_path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResolveOutputPath:
    def test_explicit_output(self):
        result = _resolve_output_path("my_file.csv", "table", "csv")
        assert result == Path("my_file.csv")

    def test_auto_generated_csv(self):
        result = _resolve_output_path(None, "my-table", "csv")
        assert result.suffix == ".csv"
        assert "my-table" in result.name

    def test_auto_generated_json(self):
        result = _resolve_output_path(None, "my-table", "json")
        assert result.suffix == ".json"

    def test_auto_generated_jsonl(self):
        result = _resolve_output_path(None, "my-table", "jsonl")
        assert result.suffix == ".jsonl"

    def test_auto_generated_tsv(self):
        result = _resolve_output_path(None, "my-table", "tsv")
        assert result.suffix == ".tsv"

    def test_unknown_format_defaults_to_json(self):
        result = _resolve_output_path(None, "my-table", "unknown")
        assert result.suffix == ".json"


# ---------------------------------------------------------------------------
# _validate_write_permissions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateWritePermissions:
    def test_writable_directory(self, tmp_path):
        out = tmp_path / "output.csv"
        # Should not raise
        _validate_write_permissions(out)

    def test_nonwritable_directory_exits(self, tmp_path):
        out = tmp_path / "nonexistent_dir" / "output.csv"
        with pytest.raises(SystemExit):
            _validate_write_permissions(out)


# ---------------------------------------------------------------------------
# _warn_large_export
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWarnLargeExport:
    def test_yes_flag_skips_warning(self):
        mock_exporter = MagicMock()
        result = _warn_large_export(mock_exporter, yes=True, dry_run=False, limit=None)
        assert result is True
        mock_exporter.get_table_info.assert_not_called()

    def test_dry_run_skips_warning(self):
        mock_exporter = MagicMock()
        result = _warn_large_export(mock_exporter, yes=False, dry_run=True, limit=None)
        assert result is True
        mock_exporter.get_table_info.assert_not_called()

    def test_limit_skips_warning(self):
        mock_exporter = MagicMock()
        result = _warn_large_export(mock_exporter, yes=False, dry_run=False, limit=100)
        assert result is True
        mock_exporter.get_table_info.assert_not_called()

    def test_small_table_no_prompt(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 500000}
        result = _warn_large_export(mock_exporter, yes=False, dry_run=False, limit=None)
        assert result is True

    def test_large_table_user_confirms(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 2000000}
        with patch("cli_tool.commands.dynamodb.commands.export_table.click.confirm", return_value=True):
            result = _warn_large_export(mock_exporter, yes=False, dry_run=False, limit=None)
        assert result is True

    def test_large_table_user_cancels(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {"item_count": 2000000}
        with patch("cli_tool.commands.dynamodb.commands.export_table.click.confirm", return_value=False):
            result = _warn_large_export(mock_exporter, yes=False, dry_run=False, limit=None)
        assert result is False


# ---------------------------------------------------------------------------
# _do_export
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDoExport:
    def test_csv_format_calls_export_to_csv(self, tmp_path):
        mock_exporter = MagicMock()
        out = tmp_path / "out.csv"
        mock_exporter.export_to_csv.return_value = out
        result = _do_export(mock_exporter, [{"id": "1"}], "csv", out, "strings", "", ",", "utf-8", False, None, True, "lowercase")
        mock_exporter.export_to_csv.assert_called_once()
        assert result == out

    def test_tsv_format_uses_tab_delimiter(self, tmp_path):
        mock_exporter = MagicMock()
        out = tmp_path / "out.tsv"
        mock_exporter.export_to_csv.return_value = out
        _do_export(mock_exporter, [], "tsv", out, "strings", "", ",", "utf-8", False, None, True, "lowercase")
        call_kwargs = mock_exporter.export_to_csv.call_args[1]
        assert call_kwargs["delimiter"] == "\t"

    def test_json_format_calls_export_to_json(self, tmp_path):
        mock_exporter = MagicMock()
        out = tmp_path / "out.json"
        mock_exporter.export_to_json.return_value = out
        result = _do_export(mock_exporter, [], "json", out, "strings", "", ",", "utf-8", False, None, True, "lowercase")
        mock_exporter.export_to_json.assert_called_once()

    def test_jsonl_format_passes_jsonl_true(self, tmp_path):
        mock_exporter = MagicMock()
        out = tmp_path / "out.jsonl"
        mock_exporter.export_to_json.return_value = out
        _do_export(mock_exporter, [], "jsonl", out, "strings", "", ",", "utf-8", False, None, True, "lowercase")
        call_kwargs = mock_exporter.export_to_json.call_args[1]
        assert call_kwargs["jsonl"] is True


# ---------------------------------------------------------------------------
# _build_query_configs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildQueryConfigs:
    def test_builds_config_for_each_attr(self):
        indexed_attrs = [
            {"attr_ref": "#s", "value_ref": ":s1", "key_attribute": "status", "index_name": "idx"},
            {"attr_ref": "#s", "value_ref": ":s2", "key_attribute": "status", "index_name": None},
        ]
        configs = _build_query_configs(indexed_attrs, None)
        assert len(configs) == 2
        assert configs[0]["index_name"] == "idx"
        assert configs[1]["index_name"] is None

    def test_includes_remaining_filter(self):
        indexed_attrs = [
            {"attr_ref": "#s", "value_ref": ":s1", "key_attribute": "status", "index_name": None},
        ]
        configs = _build_query_configs(indexed_attrs, "age > :age")
        assert configs[0]["filter_expression"] == "age > :age"


# ---------------------------------------------------------------------------
# _extract_remaining_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractRemainingFilter:
    def test_extracts_and_portion(self):
        result = _extract_remaining_filter(
            "(status = :s) AND (age > :a)",
            {":s": {"S": "x"}, ":a": {"N": "5"}},
            {"#s": "status"},
        )
        assert result is not None

    def test_returns_none_for_no_and(self):
        result = _extract_remaining_filter("status = :s", {":s": {"S": "x"}}, {"#s": "status"})
        assert result is None

    def test_returns_none_when_no_values(self):
        result = _extract_remaining_filter("status = :s", None, None)
        assert result is None


# ---------------------------------------------------------------------------
# _handle_or_detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleOrDetection:
    def test_insufficient_indexed_attrs_falls_back_to_scan(self):
        auto_detected = {"indexed_attributes": []}
        use_q, mq, qc = _handle_or_detection(auto_detected, "a OR b", {}, {})
        assert use_q is False
        assert mq is False

    def test_parts_mismatch_falls_back_to_scan(self):
        auto_detected = {
            "indexed_attributes": [
                {"attr_ref": "#a", "value_ref": ":a", "key_attribute": "a", "index_name": None},
            ]
        }
        use_q, mq, qc = _handle_or_detection(auto_detected, "a OR b OR c", {}, {})
        assert use_q is False

    def test_valid_or_creates_multi_query(self):
        auto_detected = {
            "indexed_attributes": [
                {"attr_ref": "#a", "value_ref": ":a", "key_attribute": "a", "index_name": None},
                {"attr_ref": "#b", "value_ref": ":b", "key_attribute": "b", "index_name": None},
            ]
        }
        use_q, mq, qc = _handle_or_detection(auto_detected, "a = :a OR b = :b", None, None)
        assert use_q is True
        assert mq is True
        assert len(qc) == 2


# ---------------------------------------------------------------------------
# _print_or_scan_warning
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintOrScanWarning:
    def test_empty_indexed_attrs(self):
        # Should not raise
        _print_or_scan_warning([])

    def test_with_indexed_attrs(self):
        indexed_attrs = [
            {"key_attribute": "status", "index_name": "status-idx"},
            {"key_attribute": "type", "index_name": None},
        ]
        _print_or_scan_warning(indexed_attrs)


# ---------------------------------------------------------------------------
# export_table_command – top-level tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExportTableCommand:
    def test_template_not_found_exits(self):
        mock_config_manager = MagicMock()
        mock_config_manager.get_template.return_value = None
        params = _make_export_params()
        with patch("cli_tool.commands.dynamodb.commands.export_table.ExportConfigManager", return_value=mock_config_manager):
            with pytest.raises(SystemExit):
                export_table_command(params, use_template="missing-template")

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_client_error_exits(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from botocore.exceptions import ClientError

        params = _make_export_params()
        mock_config = MagicMock()
        with patch("cli_tool.commands.dynamodb.commands.export_table.ExportConfigManager", return_value=mock_config):
            with patch("cli_tool.commands.dynamodb.commands.export_table._run_export_core") as mock_run:
                mock_run.side_effect = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "table not found"}}, "Scan")
                with pytest.raises(SystemExit):
                    export_table_command(params, use_template=None)

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_botocore_error_exits(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from botocore.exceptions import BotoCoreError

        params = _make_export_params()
        mock_config = MagicMock()
        with patch("cli_tool.commands.dynamodb.commands.export_table.ExportConfigManager", return_value=mock_config):
            with patch("cli_tool.commands.dynamodb.commands.export_table._run_export_core") as mock_run:
                mock_run.side_effect = BotoCoreError()
                with pytest.raises(SystemExit):
                    export_table_command(params, use_template=None)

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_unexpected_error_exits(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        params = _make_export_params()
        mock_config = MagicMock()
        with patch("cli_tool.commands.dynamodb.commands.export_table.ExportConfigManager", return_value=mock_config):
            with patch("cli_tool.commands.dynamodb.commands.export_table._run_export_core") as mock_run:
                mock_run.side_effect = RuntimeError("something went wrong")
                with pytest.raises(SystemExit):
                    export_table_command(params, use_template=None)

    def test_with_valid_template_applies_it(self):
        params = _make_export_params()
        mock_config = MagicMock()
        mock_config.get_template.return_value = {"format": "csv", "region": "eu-west-1"}

        with patch("cli_tool.commands.dynamodb.commands.export_table.ExportConfigManager", return_value=mock_config):
            with patch("cli_tool.commands.dynamodb.commands.export_table._run_export_core") as mock_run:
                mock_run.return_value = None
                export_table_command(params, use_template="my-template")
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# _run_export_core – unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunExportCore:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_table_not_found_exits(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.commands.export_table import _run_export_core
        from cli_tool.core.utils import aws as aws_utils

        params = _make_export_params()
        mock_config_manager = MagicMock()

        with patch.object(aws_utils, "create_aws_client", return_value=MagicMock()):
            with patch("cli_tool.commands.dynamodb.commands.export_table.validate_table_exists", return_value=False):
                with pytest.raises(SystemExit):
                    _run_export_core(params, mock_config_manager)

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_no_items_found_returns(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.commands.export_table import _run_export_core
        from cli_tool.core.utils import aws as aws_utils

        params = _make_export_params()
        mock_config_manager = MagicMock()

        with patch.object(aws_utils, "create_aws_client", return_value=MagicMock()):
            with patch("cli_tool.commands.dynamodb.commands.export_table.validate_table_exists", return_value=True):
                with patch("cli_tool.commands.dynamodb.commands.export_table.DynamoDBExporter") as mock_exp_cls:
                    mock_exp = MagicMock()
                    mock_exp.get_table_info.return_value = {"key_schema": [], "item_count": 0}
                    mock_exp_cls.return_value = mock_exp
                    with patch("cli_tool.commands.dynamodb.commands.export_table.estimate_export_size"):
                        with patch("cli_tool.commands.dynamodb.commands.export_table._fetch_items", return_value=[]):
                            with patch(
                                "cli_tool.commands.dynamodb.commands.export_table._auto_detect_query_strategy",
                                return_value=(False, None, None, None, False, []),
                            ):
                                with patch("cli_tool.commands.dynamodb.commands.export_table._auto_tune_parallel_scan", return_value=(False, 4)):
                                    # Should return without error (no items path)
                                    _run_export_core(params, mock_config_manager)

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_dry_run_path(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        from cli_tool.commands.dynamodb.commands.export_table import _run_export_core
        from cli_tool.core.utils import aws as aws_utils

        params = _make_export_params(dry_run=True)
        mock_config_manager = MagicMock()

        with patch.object(aws_utils, "create_aws_client", return_value=MagicMock()):
            with patch("cli_tool.commands.dynamodb.commands.export_table.validate_table_exists", return_value=True):
                with patch("cli_tool.commands.dynamodb.commands.export_table.DynamoDBExporter") as mock_exp_cls:
                    mock_exp = MagicMock()
                    mock_exp.get_table_info.return_value = {"key_schema": [], "item_count": 0}
                    mock_exp_cls.return_value = mock_exp
                    with patch("cli_tool.commands.dynamodb.commands.export_table._fetch_items", return_value=[{"id": "1"}]):
                        with patch(
                            "cli_tool.commands.dynamodb.commands.export_table._auto_detect_query_strategy",
                            return_value=(False, None, None, None, False, []),
                        ):
                            with patch("cli_tool.commands.dynamodb.commands.export_table._auto_tune_parallel_scan", return_value=(False, 4)):
                                with patch("cli_tool.commands.dynamodb.commands.export_table._print_dry_run_summary"):
                                    _run_export_core(params, mock_config_manager)
