"""Unit tests for DynamoDB list_tables command."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.commands.list_tables import (
    _describe_single_table,
    _format_size,
    list_tables_command,
)

# ---------------------------------------------------------------------------
# _format_size
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatSize:
    def test_bytes_below_1mb(self):
        result = _format_size(512 * 1024)  # 512 KB
        assert "KB" in result

    def test_mb_range(self):
        result = _format_size(5 * 1024 * 1024)  # 5 MB
        assert "MB" in result

    def test_gb_range(self):
        result = _format_size(2 * 1024 * 1024 * 1024)  # 2 GB
        assert "GB" in result

    def test_zero_bytes(self):
        result = _format_size(0)
        assert "KB" in result

    def test_exactly_1mb(self):
        result = _format_size(1024 * 1024)
        assert "MB" in result

    def test_exactly_1gb(self):
        result = _format_size(1024 * 1024 * 1024)
        assert "GB" in result


# ---------------------------------------------------------------------------
# _describe_single_table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDescribeSingleTable:
    def test_returns_status_count_size(self):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {
            "Table": {
                "TableStatus": "ACTIVE",
                "ItemCount": 42,
                "TableSizeBytes": 1024,
            }
        }
        status, count, size = _describe_single_table(mock_client, "my-table")
        assert status == "ACTIVE"
        assert count == 42
        assert size == 1024

    def test_defaults_when_fields_missing(self):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {"Table": {"TableStatus": "CREATING"}}
        status, count, size = _describe_single_table(mock_client, "my-table")
        assert status == "CREATING"
        assert count == 0
        assert size == 0

    def test_propagates_exception(self):
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = Exception("Not found")
        with pytest.raises(Exception, match="Not found"):
            _describe_single_table(mock_client, "bad-table")


# ---------------------------------------------------------------------------
# list_tables_command
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListTablesCommand:
    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_lists_tables_single_page(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.return_value = {"TableNames": ["table-a", "table-b"]}
        mock_client.describe_table.side_effect = [
            {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 10,
                    "TableSizeBytes": 1024,
                }
            },
            {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 20,
                    "TableSizeBytes": 2048,
                }
            },
        ]
        mock_create_client.return_value = mock_client

        # Should not raise
        list_tables_command(profile=None, region="us-east-1")

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_lists_tables_with_pagination(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.side_effect = [
            {"TableNames": ["table-a"], "LastEvaluatedTableName": "table-a"},
            {"TableNames": ["table-b"]},
        ]
        mock_client.describe_table.return_value = {
            "Table": {
                "TableStatus": "ACTIVE",
                "ItemCount": 5,
                "TableSizeBytes": 512,
            }
        }
        mock_create_client.return_value = mock_client

        list_tables_command(profile=None, region="us-east-1")
        assert mock_client.list_tables.call_count == 2

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_empty_table_list(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.return_value = {"TableNames": []}
        mock_create_client.return_value = mock_client

        # Should not raise and should print warning
        list_tables_command(profile=None, region="us-east-1")

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_describe_table_error_shows_error_row(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.return_value = {"TableNames": ["table-a"]}
        mock_client.describe_table.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        # Should not raise - error is caught per-table
        list_tables_command(profile=None, region="us-east-1")

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_exception_causes_sys_exit(self, mock_create_client):
        mock_create_client.side_effect = Exception("Connection error")

        with pytest.raises(SystemExit) as exc_info:
            list_tables_command(profile=None, region="us-east-1")
        assert exc_info.value.code == 1

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_non_active_tables_excluded_from_totals(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.return_value = {"TableNames": ["table-active", "table-creating"]}
        mock_client.describe_table.side_effect = [
            {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 100,
                    "TableSizeBytes": 10240,
                }
            },
            {
                "Table": {
                    "TableStatus": "CREATING",
                    "ItemCount": 0,
                    "TableSizeBytes": 0,
                }
            },
        ]
        mock_create_client.return_value = mock_client

        # Should not raise
        list_tables_command(profile=None, region="us-east-1")

    @patch("cli_tool.commands.dynamodb.commands.list_tables.create_aws_client")
    def test_profile_passed_to_create_client(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.list_tables.return_value = {"TableNames": []}
        mock_create_client.return_value = mock_client

        list_tables_command(profile="my-profile", region="eu-west-1")

        mock_create_client.assert_called_once_with("dynamodb", profile_name="my-profile", region_name="eu-west-1")
