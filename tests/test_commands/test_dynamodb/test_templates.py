"""Unit tests for DynamoDB templates module."""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.utils.templates import ExportConfigManager, create_template_from_args

# ---------------------------------------------------------------------------
# create_template_from_args
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateTemplateFromArgs:
    def test_basic_template(self):
        result = create_template_from_args(
            table_name="my-table",
            format="csv",
            region="us-east-1",
        )
        assert result["table_name"] == "my-table"
        assert result["format"] == "csv"
        assert result["region"] == "us-east-1"

    def test_none_values_excluded(self):
        result = create_template_from_args(
            table_name="my-table",
            output=None,
            limit=None,
            format="json",
        )
        assert "output" not in result
        assert "limit" not in result
        assert result["format"] == "json"

    def test_ctx_excluded(self):
        result = create_template_from_args(table_name="my-table", ctx=MagicMock())
        assert "ctx" not in result

    def test_dry_run_excluded(self):
        result = create_template_from_args(table_name="my-table", dry_run=True)
        assert "dry_run" not in result

    def test_yes_excluded(self):
        result = create_template_from_args(table_name="my-table", yes=True)
        assert "yes" not in result

    def test_list_tables_excluded(self):
        result = create_template_from_args(table_name="my-table", list_tables=True)
        assert "list_tables" not in result

    def test_all_optional_params(self):
        result = create_template_from_args(
            table_name="my-table",
            output="/tmp/out.csv",
            format="csv",
            region="us-west-2",
            limit=1000,
            attributes="id,name",
            filter="status = active",
            key_condition="pk = :pk",
            index="gsi-1",
            mode="flatten",
            null_value="N/A",
            delimiter="|",
            encoding="utf-8",
            compress="gzip",
            metadata=True,
            pretty=False,
            parallel_scan=True,
            segments=8,
            bool_format="numeric",
        )
        assert result["table_name"] == "my-table"
        assert result["output"] == "/tmp/out.csv"
        assert result["limit"] == 1000
        assert result["compress"] == "gzip"

    def test_empty_kwargs(self):
        result = create_template_from_args()
        assert result == {}


# ---------------------------------------------------------------------------
# ExportConfigManager
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExportConfigManager:
    @patch("cli_tool.commands.dynamodb.utils.templates.save_dynamodb_template")
    def test_save_template(self, mock_save):
        manager = ExportConfigManager()
        manager.save_template("my-template", {"table_name": "test"})
        mock_save.assert_called_once_with("my-template", {"table_name": "test"})

    @patch("cli_tool.commands.dynamodb.utils.templates.get_dynamodb_templates")
    def test_load_templates(self, mock_get):
        mock_get.return_value = {"tmpl": {"table_name": "test"}}
        manager = ExportConfigManager()
        result = manager.load_templates()
        assert result == {"tmpl": {"table_name": "test"}}

    @patch("cli_tool.commands.dynamodb.utils.templates.get_dynamodb_template")
    def test_get_template(self, mock_get):
        mock_get.return_value = {"table_name": "test"}
        manager = ExportConfigManager()
        result = manager.get_template("my-template")
        assert result == {"table_name": "test"}
        mock_get.assert_called_once_with("my-template")

    @patch("cli_tool.commands.dynamodb.utils.templates.delete_dynamodb_template")
    def test_delete_template_found(self, mock_delete):
        mock_delete.return_value = True
        manager = ExportConfigManager()
        result = manager.delete_template("my-template")
        assert result is True
        mock_delete.assert_called_once_with("my-template")

    @patch("cli_tool.commands.dynamodb.utils.templates.delete_dynamodb_template")
    def test_delete_template_not_found(self, mock_delete):
        mock_delete.return_value = False
        manager = ExportConfigManager()
        result = manager.delete_template("missing-template")
        assert result is False

    @patch("cli_tool.commands.dynamodb.utils.templates.get_dynamodb_templates")
    def test_list_templates_empty(self, mock_get):
        mock_get.return_value = {}
        manager = ExportConfigManager()
        # Should not raise
        manager.list_templates()

    @patch("cli_tool.commands.dynamodb.utils.templates.get_dynamodb_templates")
    def test_list_templates_with_data(self, mock_get):
        mock_get.return_value = {
            "tmpl1": {
                "table_name": "table-a",
                "format": "csv",
                "mode": "flatten",
                "compress": "gzip",
                "limit": 1000,
            },
            "tmpl2": {
                "table_name": "table-b",
                "format": "json",
            },
        }
        manager = ExportConfigManager()
        # Should not raise
        manager.list_templates()

    @patch("cli_tool.commands.dynamodb.utils.templates.get_dynamodb_templates")
    def test_list_templates_no_options(self, mock_get):
        mock_get.return_value = {
            "basic": {"table_name": "my-table"},
        }
        manager = ExportConfigManager()
        # Should not raise — template with no mode/compress/limit
        manager.list_templates()
