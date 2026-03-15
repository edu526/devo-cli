"""Unit tests for DynamoDB utils module."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cli_tool.commands.dynamodb.utils.utils import estimate_export_size, validate_table_exists

# ---------------------------------------------------------------------------
# validate_table_exists
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateTableExists:
    def test_active_table_returns_true(self):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {"Table": {"TableStatus": "ACTIVE"}}
        result = validate_table_exists(mock_client, "my-table")
        assert result is True

    def test_non_active_status_returns_false(self):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {"Table": {"TableStatus": "CREATING"}}
        result = validate_table_exists(mock_client, "my-table")
        assert result is False

    def test_resource_not_found_returns_false(self):
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            operation_name="DescribeTable",
        )
        result = validate_table_exists(mock_client, "missing-table")
        assert result is False

    def test_other_client_error_returns_false(self):
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            operation_name="DescribeTable",
        )
        result = validate_table_exists(mock_client, "my-table")
        assert result is False

    def test_table_name_passed_to_client(self):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {"Table": {"TableStatus": "ACTIVE"}}
        validate_table_exists(mock_client, "specific-table")
        mock_client.describe_table.assert_called_once_with(TableName="specific-table")


# ---------------------------------------------------------------------------
# estimate_export_size
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEstimateExportSize:
    def test_basic_estimate(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {
            "status": "ACTIVE",
            "item_count": 1000,
            "size_bytes": 1024 * 1024,
        }
        # Should not raise
        estimate_export_size(mock_exporter)

    def test_zero_items(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {
            "status": "ACTIVE",
            "item_count": 0,
            "size_bytes": 0,
        }
        # No estimated_seconds printed when count == 0
        estimate_export_size(mock_exporter)

    def test_large_table_warning(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.return_value = {
            "status": "ACTIVE",
            "item_count": 200000,
            "size_bytes": 200 * 1024 * 1024,
        }
        # Should not raise - warning about parallel-scan is printed
        estimate_export_size(mock_exporter)

    def test_exception_handled_gracefully(self):
        mock_exporter = MagicMock()
        mock_exporter.get_table_info.side_effect = Exception("AWS Error")
        # Should not raise; error is caught and printed
        estimate_export_size(mock_exporter)
