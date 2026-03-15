"""Unit tests for DynamoDB describe_table command."""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.commands.describe_table import (
    _format_index_keys,
    _format_projection,
    _kv_table,
    _panel,
    _print_basic_info,
    _print_billing,
    _print_encryption,
    _print_gsi,
    _print_key_schema,
    _print_lsi,
    _print_pitr,
    _print_storage,
    _print_streams,
    _print_tags,
    describe_table_command,
)

# ---------------------------------------------------------------------------
# _kv_table and _panel helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_kv_table_returns_rich_table():
    table = _kv_table()
    assert table is not None
    assert table.show_header is False


@pytest.mark.unit
def test_panel_returns_panel_with_title():
    import rich.panel

    content = _kv_table()
    p = _panel(content, "My Title")
    assert isinstance(p, rich.panel.Panel)


# ---------------------------------------------------------------------------
# _format_projection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatProjection:
    def test_all_projection(self):
        data = {"ProjectionType": "ALL"}
        result = _format_projection(data)
        assert result == "ALL"

    def test_keys_only_projection(self):
        data = {"ProjectionType": "KEYS_ONLY"}
        result = _format_projection(data)
        assert result == "KEYS_ONLY"

    def test_include_projection_few_attrs(self):
        data = {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["attr1", "attr2"]}
        result = _format_projection(data)
        assert "INCLUDE" in result
        assert "attr1" in result

    def test_include_projection_many_attrs_truncated(self):
        data = {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["a", "b", "c", "d", "e"]}
        result = _format_projection(data)
        assert "..." in result

    def test_include_projection_no_attrs(self):
        data = {"ProjectionType": "INCLUDE"}
        result = _format_projection(data)
        assert "INCLUDE" in result


# ---------------------------------------------------------------------------
# _format_index_keys
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatIndexKeys:
    def test_hash_key_only(self):
        key_schema = [{"AttributeName": "pk", "KeyType": "HASH"}]
        result = _format_index_keys(key_schema)
        assert "pk" in result
        assert "PK" in result

    def test_hash_and_sort_keys(self):
        key_schema = [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ]
        result = _format_index_keys(key_schema)
        assert "pk" in result
        assert "sk" in result
        assert "SK" in result

    def test_empty_key_schema(self):
        result = _format_index_keys([])
        assert result == ""


# ---------------------------------------------------------------------------
# _print_basic_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintBasicInfo:
    def test_active_status(self):
        table_info = {
            "TableStatus": "ACTIVE",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test",
            "TableId": "abc-123",
            "CreationDateTime": datetime(2024, 1, 1, 0, 0, 0),
        }
        # Should not raise
        _print_basic_info(table_info)

    def test_creating_status(self):
        table_info = {
            "TableStatus": "CREATING",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test",
            "TableId": "abc-123",
            "CreationDateTime": datetime(2024, 1, 1, 0, 0, 0),
        }
        _print_basic_info(table_info)


# ---------------------------------------------------------------------------
# _print_storage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintStorage:
    def test_size_in_kb(self):
        table_info = {"ItemCount": 10, "TableSizeBytes": 512}
        _print_storage(table_info)

    def test_size_in_mb(self):
        table_info = {"ItemCount": 1000, "TableSizeBytes": 2 * 1024 * 1024}
        _print_storage(table_info)

    def test_size_in_gb(self):
        table_info = {"ItemCount": 1000000, "TableSizeBytes": 2 * 1024 * 1024 * 1024}
        _print_storage(table_info)

    def test_defaults_when_missing(self):
        table_info = {}
        _print_storage(table_info)


# ---------------------------------------------------------------------------
# _print_key_schema
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintKeySchema:
    def test_hash_only(self):
        table_info = {
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
        }
        _print_key_schema(table_info)

    def test_hash_and_range(self):
        table_info = {
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "N"},
            ],
        }
        _print_key_schema(table_info)

    def test_unknown_attribute_type(self):
        table_info = {
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [],
        }
        _print_key_schema(table_info)


# ---------------------------------------------------------------------------
# _print_billing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintBilling:
    def test_provisioned_billing(self):
        table_info = {
            "BillingModeSummary": {"BillingMode": "PROVISIONED"},
            "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        }
        _print_billing(table_info)

    def test_pay_per_request_billing(self):
        table_info = {
            "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
        }
        _print_billing(table_info)

    def test_default_billing_mode(self):
        table_info = {}
        _print_billing(table_info)


# ---------------------------------------------------------------------------
# _print_gsi
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintGsi:
    def test_no_gsi(self):
        table_info = {}
        _print_gsi(table_info)

    def test_empty_gsi_list(self):
        table_info = {"GlobalSecondaryIndexes": []}
        _print_gsi(table_info)

    def test_with_gsi(self):
        table_info = {
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "gsi-1",
                    "IndexStatus": "ACTIVE",
                    "KeySchema": [{"AttributeName": "sk", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ]
        }
        _print_gsi(table_info)


# ---------------------------------------------------------------------------
# _print_lsi
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintLsi:
    def test_no_lsi(self):
        table_info = {}
        _print_lsi(table_info)

    def test_empty_lsi_list(self):
        table_info = {"LocalSecondaryIndexes": []}
        _print_lsi(table_info)

    def test_with_lsi(self):
        table_info = {
            "LocalSecondaryIndexes": [
                {
                    "IndexName": "lsi-1",
                    "KeySchema": [{"AttributeName": "sk2", "KeyType": "RANGE"}],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                }
            ]
        }
        _print_lsi(table_info)


# ---------------------------------------------------------------------------
# _print_streams
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintStreams:
    def test_no_stream_spec(self):
        table_info = {}
        _print_streams(table_info)

    def test_stream_disabled(self):
        table_info = {"StreamSpecification": {"StreamEnabled": False}}
        _print_streams(table_info)

    def test_stream_enabled_with_arn(self):
        table_info = {
            "StreamSpecification": {"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"},
            "LatestStreamArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test/stream/2024",
        }
        _print_streams(table_info)

    def test_stream_enabled_without_arn(self):
        table_info = {
            "StreamSpecification": {"StreamEnabled": True, "StreamViewType": "KEYS_ONLY"},
        }
        _print_streams(table_info)


# ---------------------------------------------------------------------------
# _print_encryption
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintEncryption:
    def test_no_sse(self):
        table_info = {}
        _print_encryption(table_info)

    def test_sse_enabled_with_kms(self):
        table_info = {
            "SSEDescription": {
                "Status": "ENABLED",
                "SSEType": "KMS",
                "KMSMasterKeyArn": "arn:aws:kms:us-east-1:123456789012:key/abc",
            }
        }
        _print_encryption(table_info)

    def test_sse_enabled_without_kms(self):
        table_info = {"SSEDescription": {"Status": "ENABLED", "SSEType": "AES256"}}
        _print_encryption(table_info)

    def test_sse_disabled_status(self):
        table_info = {"SSEDescription": {"Status": "DISABLED"}}
        _print_encryption(table_info)


# ---------------------------------------------------------------------------
# _print_pitr
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintPitr:
    def test_pitr_enabled_with_dates(self):
        mock_client = MagicMock()
        earliest = datetime(2024, 1, 1, 0, 0, 0)
        latest = datetime(2024, 1, 10, 0, 0, 0)
        mock_client.describe_continuous_backups.return_value = {
            "ContinuousBackupsDescription": {
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": "ENABLED",
                    "EarliestRestorableDateTime": earliest,
                    "LatestRestorableDateTime": latest,
                }
            }
        }
        _print_pitr(mock_client, "test-table")

    def test_pitr_disabled(self):
        mock_client = MagicMock()
        mock_client.describe_continuous_backups.return_value = {
            "ContinuousBackupsDescription": {
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": "DISABLED",
                }
            }
        }
        _print_pitr(mock_client, "test-table")

    def test_pitr_exception_handled(self):
        mock_client = MagicMock()
        mock_client.describe_continuous_backups.side_effect = Exception("Access denied")
        # Should not raise
        _print_pitr(mock_client, "test-table")

    def test_pitr_enabled_without_dates(self):
        mock_client = MagicMock()
        mock_client.describe_continuous_backups.return_value = {
            "ContinuousBackupsDescription": {
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": "ENABLED",
                }
            }
        }
        _print_pitr(mock_client, "test-table")


# ---------------------------------------------------------------------------
# _print_tags
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintTags:
    def test_tags_present(self):
        mock_client = MagicMock()
        mock_client.list_tags_of_resource.return_value = {"Tags": [{"Key": "Env", "Value": "prod"}, {"Key": "Team", "Value": "backend"}]}
        _print_tags(mock_client, "arn:aws:dynamodb:us-east-1:123456789012:table/test")

    def test_no_tags(self):
        mock_client = MagicMock()
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        _print_tags(mock_client, "arn:aws:dynamodb:us-east-1:123456789012:table/test")

    def test_tags_exception_handled(self):
        mock_client = MagicMock()
        mock_client.list_tags_of_resource.side_effect = Exception("Access denied")
        # Should not raise
        _print_tags(mock_client, "arn:aws:dynamodb:us-east-1:123456789012:table/test")


# ---------------------------------------------------------------------------
# describe_table_command
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDescribeTableCommand:
    def _make_table_response(self):
        return {
            "Table": {
                "TableName": "test-table",
                "TableStatus": "ACTIVE",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "TableId": "abc-123",
                "CreationDateTime": datetime(2024, 1, 1, 0, 0, 0),
                "ItemCount": 100,
                "TableSizeBytes": 1024,
                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            }
        }

    @patch("cli_tool.commands.dynamodb.commands.describe_table.create_aws_client")
    def test_success(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.describe_table.return_value = self._make_table_response()
        mock_client.describe_continuous_backups.return_value = {
            "ContinuousBackupsDescription": {"PointInTimeRecoveryDescription": {"PointInTimeRecoveryStatus": "DISABLED"}}
        }
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        describe_table_command(profile=None, table_name="test-table", region="us-east-1")

    @patch("cli_tool.commands.dynamodb.commands.describe_table.create_aws_client")
    def test_exception_causes_sys_exit(self, mock_create_client):
        mock_create_client.side_effect = Exception("Connection error")

        with pytest.raises(SystemExit) as exc_info:
            describe_table_command(profile=None, table_name="test-table", region="us-east-1")
        assert exc_info.value.code == 1
