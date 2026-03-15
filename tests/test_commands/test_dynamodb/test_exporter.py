"""Unit tests for DynamoDB exporter module."""

import csv
import gzip
import io
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter


def _make_exporter(table_name="test-table", region="us-east-1", profile=None):
    """Create a DynamoDBExporter with a mock client."""
    mock_client = MagicMock()
    return DynamoDBExporter(
        table_name=table_name,
        dynamodb_client=mock_client,
        region=region,
        profile=profile,
    )


# ---------------------------------------------------------------------------
# _convert_value
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConvertValue:
    def test_decimal_integer(self):
        exporter = _make_exporter()
        result = exporter._convert_value(Decimal("42"))
        assert result == 42
        assert isinstance(result, int)

    def test_decimal_float(self):
        exporter = _make_exporter()
        result = exporter._convert_value(Decimal("3.14"))
        assert abs(result - 3.14) < 1e-9
        assert isinstance(result, float)

    def test_dict_recursion(self):
        exporter = _make_exporter()
        result = exporter._convert_value({"a": Decimal("1"), "b": "hello"})
        assert result == {"a": 1, "b": "hello"}

    def test_list_recursion(self):
        exporter = _make_exporter()
        result = exporter._convert_value([Decimal("2"), Decimal("3.5")])
        assert result == [2, 3.5]

    def test_set_becomes_list(self):
        exporter = _make_exporter()
        result = exporter._convert_value({"x", "y"})
        assert isinstance(result, list)
        assert set(result) == {"x", "y"}

    def test_plain_string_unchanged(self):
        exporter = _make_exporter()
        assert exporter._convert_value("hello") == "hello"

    def test_none_unchanged(self):
        exporter = _make_exporter()
        assert exporter._convert_value(None) is None

    def test_bool_unchanged(self):
        exporter = _make_exporter()
        assert exporter._convert_value(True) is True


# ---------------------------------------------------------------------------
# _flatten_dict
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFlattenDict:
    def test_simple_flat_dict(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"a": 1, "b": "x"})
        assert result == {"a": 1, "b": "x"}

    def test_nested_dict(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"outer": {"inner": "val"}})
        assert result == {"outer.inner": "val"}

    def test_nested_dict_with_parent_key(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"a": {"b": {"c": 99}}})
        assert result == {"a.b.c": 99}

    def test_list_of_primitives_joined(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"tags": ["a", "b", "c"]})
        assert result == {"tags": "a|b|c"}

    def test_list_of_complex_items_json(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"items": [{"key": "v1"}, {"key": "v2"}]})
        parsed = json.loads(result["items"])
        assert parsed == [{"key": "v1"}, {"key": "v2"}]

    def test_list_with_decimal(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"nums": [Decimal("1"), Decimal("2")]})
        assert result == {"nums": "1|2"}

    def test_custom_separator(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"a": {"b": 1}}, separator="/")
        assert "a/b" in result

    def test_custom_list_separator(self):
        exporter = _make_exporter()
        result = exporter._flatten_dict({"x": [1, 2]}, list_separator=",")
        assert result["x"] == "1,2"


# ---------------------------------------------------------------------------
# _serialize_as_json
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSerializeAsJson:
    def test_dict_value_serialized(self):
        exporter = _make_exporter()
        result = exporter._serialize_as_json({"meta": {"k": "v"}})
        assert result["meta"] == '{"k": "v"}'

    def test_list_value_serialized(self):
        exporter = _make_exporter()
        result = exporter._serialize_as_json({"tags": [1, 2]})
        assert result["tags"] == "[1, 2]"

    def test_plain_value_unchanged(self):
        exporter = _make_exporter()
        result = exporter._serialize_as_json({"name": "Alice", "age": 30})
        assert result == {"name": "Alice", "age": 30}

    def test_decimal_in_list_converted(self):
        exporter = _make_exporter()
        result = exporter._serialize_as_json({"nums": [Decimal("10")]})
        assert result["nums"] == "[10]"


# ---------------------------------------------------------------------------
# _normalize_lists
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeLists:
    def test_no_lists_returns_single_row(self):
        exporter = _make_exporter()
        data = {"id": "1", "name": "test"}
        rows = exporter._normalize_lists(data)
        assert rows == [data]

    def test_single_list_expanded(self):
        exporter = _make_exporter()
        data = {"id": "1", "tags": ["a", "b", "c"]}
        rows = exporter._normalize_lists(data)
        assert len(rows) == 3
        assert rows[0]["tags"] == "a"
        assert rows[1]["tags"] == "b"
        assert rows[2]["tags"] == "c"

    def test_non_list_values_repeated(self):
        exporter = _make_exporter()
        data = {"id": "1", "tags": ["a", "b"]}
        rows = exporter._normalize_lists(data)
        for row in rows:
            assert row["id"] == "1"

    def test_shorter_list_uses_last_value(self):
        exporter = _make_exporter()
        data = {"long": [1, 2, 3], "short": [10, 20]}
        rows = exporter._normalize_lists(data)
        assert len(rows) == 3
        assert rows[2]["short"] == 20  # last value repeated

    def test_empty_list_field_becomes_none(self):
        exporter = _make_exporter()
        data = {"long": [1, 2], "empty": []}
        rows = exporter._normalize_lists(data)
        for row in rows:
            assert row["empty"] is None


# ---------------------------------------------------------------------------
# _format_value_for_csv
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatValueForCsv:
    def test_none_returns_null_value(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(None, null_value="NULL") == "NULL"
        assert exporter._format_value_for_csv(None, null_value="") == ""

    def test_bool_lowercase(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(True, bool_format="lowercase") == "true"
        assert exporter._format_value_for_csv(False, bool_format="lowercase") == "false"

    def test_bool_uppercase(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(True, bool_format="uppercase") == "True"
        assert exporter._format_value_for_csv(False, bool_format="uppercase") == "False"

    def test_bool_numeric(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(True, bool_format="numeric") == "1"
        assert exporter._format_value_for_csv(False, bool_format="numeric") == "0"

    def test_bool_letter(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(True, bool_format="letter") == "t"
        assert exporter._format_value_for_csv(False, bool_format="letter") == "f"

    def test_bool_unknown_format(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(True, bool_format="other") == "true"

    def test_decimal_integer(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(Decimal("5")) == "5"

    def test_decimal_float(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(Decimal("5.5")) == "5.5"

    def test_list_serialized_as_json(self):
        exporter = _make_exporter()
        result = exporter._format_value_for_csv([1, 2])
        assert result == "[1, 2]"

    def test_dict_serialized_as_json(self):
        exporter = _make_exporter()
        result = exporter._format_value_for_csv({"k": "v"})
        assert json.loads(result) == {"k": "v"}

    def test_string_whitespace_normalized(self):
        exporter = _make_exporter()
        result = exporter._format_value_for_csv("hello  \n  world")
        assert result == "hello world"

    def test_integer_converted_to_str(self):
        exporter = _make_exporter()
        assert exporter._format_value_for_csv(42) == "42"


# ---------------------------------------------------------------------------
# scan_table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScanTable:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_basic_scan_returns_items(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.return_value = {"Items": [{"id": {"S": "1"}}, {"id": {"S": "2"}}]}

        items = exporter.scan_table()
        assert len(items) == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_scan_with_pagination(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.side_effect = [
            {"Items": [{"id": {"S": "1"}}], "LastEvaluatedKey": {"id": {"S": "1"}}},
            {"Items": [{"id": {"S": "2"}}]},
        ]

        items = exporter.scan_table()
        assert len(items) == 2
        assert exporter.dynamodb.scan.call_count == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_scan_with_limit(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.return_value = {
            "Items": [{"id": {"S": str(i)}} for i in range(10)],
            "LastEvaluatedKey": {"id": {"S": "9"}},
        }

        items = exporter.scan_table(limit=5)
        assert len(items) == 5

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_scan_passes_filter_expression(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.return_value = {"Items": []}

        exporter.scan_table(filter_expression="status = :s")
        call_kwargs = exporter.dynamodb.scan.call_args[1]
        assert call_kwargs.get("FilterExpression") == "status = :s"

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_scan_passes_index_name(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.return_value = {"Items": []}

        exporter.scan_table(index_name="my-index")
        call_kwargs = exporter.dynamodb.scan.call_args[1]
        assert call_kwargs.get("IndexName") == "my-index"

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_scan_parallel_passes_segment_info(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.scan.return_value = {"Items": []}

        exporter.scan_table(parallel_scan=True, segment=0, total_segments=4)
        call_kwargs = exporter.dynamodb.scan.call_args[1]
        assert call_kwargs.get("Segment") == 0
        assert call_kwargs.get("TotalSegments") == 4


# ---------------------------------------------------------------------------
# query_table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryTable:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_basic_query(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.query.return_value = {"Items": [{"id": {"S": "1"}}]}

        items = exporter.query_table(key_condition_expression="id = :id")
        assert len(items) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_query_with_pagination(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.query.side_effect = [
            {"Items": [{"id": {"S": "1"}}], "LastEvaluatedKey": {"id": {"S": "1"}}},
            {"Items": [{"id": {"S": "2"}}]},
        ]

        items = exporter.query_table(key_condition_expression="pk = :pk")
        assert len(items) == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_query_with_limit(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.query.return_value = {
            "Items": [{"id": {"S": str(i)}} for i in range(10)],
            "LastEvaluatedKey": {"id": {"S": "9"}},
        }

        items = exporter.query_table(key_condition_expression="pk = :pk", limit=3)
        assert len(items) == 3

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_query_passes_optional_kwargs(self, mock_progress_cls):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        exporter.dynamodb.query.return_value = {"Items": []}

        exporter.query_table(
            key_condition_expression="pk = :pk",
            filter_expression="sk > :sk",
            projection_expression="pk, sk",
            index_name="gsi-1",
            expression_attribute_values={":pk": {"S": "val"}},
            expression_attribute_names={"#pk": "pk"},
        )

        call_kwargs = exporter.dynamodb.query.call_args[1]
        assert call_kwargs.get("FilterExpression") == "sk > :sk"
        assert call_kwargs.get("ProjectionExpression") == "pk, sk"
        assert call_kwargs.get("IndexName") == "gsi-1"


# ---------------------------------------------------------------------------
# export_to_json
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExportToJson:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_empty_items_returns_early(self, mock_progress_cls, tmp_path):
        exporter = _make_exporter()
        out = tmp_path / "out.json"
        result = exporter.export_to_json([], out)
        assert result == out
        assert not out.exists()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_json_pretty(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}, "name": {"S": "Alice"}}]
        out = tmp_path / "out.json"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "name": "Alice"}):
            result = exporter.export_to_json(items, out, pretty=True)

        assert result.exists()
        data = json.loads(result.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_jsonl(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}, {"id": {"S": "2"}}]
        out = tmp_path / "out.jsonl"

        with patch.object(exporter, "_convert_dynamodb_item", side_effect=lambda x: {"id": x["id"]["S"]}):
            result = exporter.export_to_json(items, out, jsonl=True)

        lines = result.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": "1"}

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_json_not_pretty(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.json"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_json(items, out, pretty=False)

        content = result.read_text()
        assert "\n" not in content.strip()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_json_gzip(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.json"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_json(items, out, compress="gzip")

        assert result.suffix == ".gz"
        with gzip.open(result, "rt") as fh:
            data = json.load(fh)
        assert len(data) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_json_gzip_already_gz(self, mock_progress_cls, tmp_path):
        """When output already ends in .gz, no extra .gz added."""
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.json.gz"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_json(items, out, compress="gzip")

        assert str(result) == str(out)

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_json_zip(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.json"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_json(items, out, compress="zip")

        assert result.suffix == ".zip"
        with zipfile.ZipFile(result) as zf:
            content = zf.read(zf.namelist()[0])
        assert json.loads(content.decode())


# ---------------------------------------------------------------------------
# export_to_csv
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExportToCsv:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_empty_items_returns_early(self, mock_progress_cls, tmp_path):
        exporter = _make_exporter()
        out = tmp_path / "out.csv"
        result = exporter.export_to_csv([], out)
        assert result == out
        assert not out.exists()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_strings_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}, "name": {"S": "Alice"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "name": "Alice"}):
            result = exporter.export_to_csv(items, out, mode="strings")

        assert result.exists()
        with open(result, newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["id"] == "1"

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_flatten_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "meta": {"k": "v"}}):
            result = exporter.export_to_csv(items, out, mode="flatten")

        assert result.exists()
        with open(result, newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert "meta.k" in rows[0]

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_normalize_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "tags": ["a", "b"]}):
            result = exporter.export_to_csv(items, out, mode="normalize")

        assert result.exists()
        with open(result, newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_unknown_mode_passthrough(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_csv(items, out, mode="raw")

        assert result.exists()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_with_metadata_no_compress(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter(profile="my-profile")
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_csv(items, out, include_metadata=True)

        content = result.read_text()
        assert "# Table:" in content
        assert "# Region:" in content
        assert "# Profile:" in content

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_gzip(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter.export_to_csv(items, out, compress="gzip")

        assert result.suffix == ".gz"
        with gzip.open(result, "rt") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_streaming_triggered_for_large_datasets(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        # Create 10001 fake items to trigger streaming
        items = [{"id": {"S": str(i)}} for i in range(10001)]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_export_to_csv_streaming", return_value=out) as mock_streaming:
            exporter.export_to_csv(items, out)
        mock_streaming.assert_called_once()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_export_csv_streaming_explicit(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_export_to_csv_streaming", return_value=out) as mock_streaming:
            exporter.export_to_csv(items, out, streaming=True)
        mock_streaming.assert_called_once()


# ---------------------------------------------------------------------------
# _export_to_csv_streaming
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExportToCsvStreaming:
    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_strings_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "val": "x"}):
            result = exporter._export_to_csv_streaming(
                items,
                out,
                mode="strings",
                null_value="",
                delimiter=",",
                encoding="utf-8",
                include_metadata=False,
                compress=None,
                bool_format="lowercase",
            )

        assert result.exists()
        with open(result, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_flatten_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "meta": {"k": "v"}}):
            result = exporter._export_to_csv_streaming(
                items,
                out,
                mode="flatten",
                null_value="",
                delimiter=",",
                encoding="utf-8",
                include_metadata=False,
                compress=None,
                bool_format="lowercase",
            )

        with open(result, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert "meta.k" in rows[0]

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_normalize_mode(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1", "tags": ["a", "b"]}):
            result = exporter._export_to_csv_streaming(
                items,
                out,
                mode="normalize",
                null_value="",
                delimiter=",",
                encoding="utf-8",
                include_metadata=False,
                compress=None,
                bool_format="lowercase",
            )

        with open(result, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_unknown_mode_passthrough(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter._export_to_csv_streaming(
                items, out, mode="raw", null_value="", delimiter=",", encoding="utf-8", include_metadata=False, compress=None, bool_format="lowercase"
            )

        assert result.exists()

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_with_metadata_no_compress(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter(profile="my-profile")
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter._export_to_csv_streaming(
                items,
                out,
                mode="strings",
                null_value="",
                delimiter=",",
                encoding="utf-8",
                include_metadata=True,
                compress=None,
                bool_format="lowercase",
            )

        content = result.read_text()
        assert "# Table:" in content
        assert "# Profile:" in content

    @patch("cli_tool.commands.dynamodb.core.exporter.Progress")
    def test_streaming_gzip_compression(self, mock_progress_cls, tmp_path):
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        exporter = _make_exporter()
        items = [{"id": {"S": "1"}}]
        out = tmp_path / "out.csv"

        with patch.object(exporter, "_convert_dynamodb_item", return_value={"id": "1"}):
            result = exporter._export_to_csv_streaming(
                items,
                out,
                mode="strings",
                null_value="",
                delimiter=",",
                encoding="utf-8",
                include_metadata=False,
                compress="gzip",
                bool_format="lowercase",
            )

        assert result.suffix == ".gz"


# ---------------------------------------------------------------------------
# get_table_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetTableInfo:
    def test_basic_table_info(self):
        exporter = _make_exporter()
        now = datetime(2024, 1, 1, 12, 0, 0)
        exporter.dynamodb.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableStatus": "ACTIVE",
                "ItemCount": 100,
                "TableSizeBytes": 204800,
                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
                "GlobalSecondaryIndexes": [],
                "LocalSecondaryIndexes": [],
                "CreationDateTime": now,
            }
        }

        info = exporter.get_table_info()
        assert info["name"] == "test-table"
        assert info["status"] == "ACTIVE"
        assert info["item_count"] == 100
        assert info["size_bytes"] == 204800
        assert "creation_date" in info

    def test_table_info_without_creation_date(self):
        exporter = _make_exporter()
        exporter.dynamodb.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableStatus": "ACTIVE",
                "ItemCount": 0,
                "TableSizeBytes": 0,
                "KeySchema": [],
                "AttributeDefinitions": [],
            }
        }

        info = exporter.get_table_info()
        assert "creation_date" not in info

    def test_table_info_defaults(self):
        exporter = _make_exporter()
        exporter.dynamodb.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableStatus": "CREATING",
            }
        }

        info = exporter.get_table_info()
        assert info["item_count"] == 0
        assert info["size_bytes"] == 0
        assert info["global_indexes"] == []
        assert info["local_indexes"] == []


# ---------------------------------------------------------------------------
# print_stats
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintStats:
    def test_print_stats_no_start_time(self):
        """Should return early if start_time is not set."""
        exporter = _make_exporter()
        # Should not raise
        exporter.print_stats(Path("/tmp/out.json"))

    def test_print_stats_with_data(self, tmp_path):
        exporter = _make_exporter()
        tmp_file = tmp_path / "out.json"
        tmp_file.write_text("data")

        exporter.stats["start_time"] = datetime(2024, 1, 1, 12, 0, 0)
        exporter.stats["end_time"] = datetime(2024, 1, 1, 12, 0, 10)
        exporter.stats["total_items"] = 100
        exporter.stats["file_size"] = 1024 * 1024
        exporter.stats["consumed_capacity"] = 50.0
        exporter.stats["scanned_count"] = 200

        # Should not raise
        exporter.print_stats(tmp_file)

    def test_print_stats_zero_duration(self, tmp_path):
        exporter = _make_exporter()
        tmp_file = tmp_path / "out.json"
        tmp_file.write_text("data")

        exporter.stats["start_time"] = datetime(2024, 1, 1, 12, 0, 0)
        exporter.stats["end_time"] = datetime(2024, 1, 1, 12, 0, 0)
        exporter.stats["total_items"] = 0
        exporter.stats["file_size"] = 0

        exporter.print_stats(tmp_file)
