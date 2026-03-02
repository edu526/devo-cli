"""
Integration tests for DynamoDB export command.

Tests the complete DynamoDB export workflow including:
- Table export with mocked DynamoDB table
- Export with different formats (JSON, CSV, JSONL, TSV)
- Export with filter expressions
- Export with parallel scanning
- Export with compression
- Error handling for non-existent tables
"""

import gzip
import json
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from click.testing import CliRunner  # noqa: F401

from cli_tool.commands.dynamodb.commands.cli import export_table


@pytest.fixture(autouse=True)
def mock_select_profile(mocker):
    """Mock select_profile to return None for all tests."""
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)


@pytest.fixture
def mock_dynamodb_table(mock_dynamodb_client):
    """Create a mock DynamoDB table with test data."""
    # Create table
    mock_dynamodb_client.create_table(
        TableName="test-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
        GlobalSecondaryIndexes=[
            {
                "IndexName": "status-index",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    # Add test items
    test_items = [
        {"id": {"S": "item-1"}, "name": {"S": "Test Item 1"}, "status": {"S": "active"}, "count": {"N": "10"}},
        {"id": {"S": "item-2"}, "name": {"S": "Test Item 2"}, "status": {"S": "inactive"}, "count": {"N": "20"}},
        {"id": {"S": "item-3"}, "name": {"S": "Test Item 3"}, "status": {"S": "active"}, "count": {"N": "30"}},
        {"id": {"S": "item-4"}, "name": {"S": "Test Item 4"}, "status": {"S": "pending"}, "count": {"N": "40"}},
        {"id": {"S": "item-5"}, "name": {"S": "Test Item 5"}, "status": {"S": "active"}, "count": {"N": "50"}},
    ]

    for item in test_items:
        mock_dynamodb_client.put_item(TableName="test-table", Item=item)

    return mock_dynamodb_client


@pytest.fixture
def mock_aws_client(mocker, mock_dynamodb_table):
    """Mock create_aws_client to return mocked DynamoDB client."""
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_dynamodb_table)
    return mock_dynamodb_table


@pytest.mark.integration
def test_export_table_json_format(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in JSON format."""
    output_file = tmp_path / "export.json"

    # Run export command with obj context
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Print output for debugging
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            print(f"Exception: {result.exception}")
            import traceback

            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    # Verify success
    assert result.exit_code == 0
    assert "Starting export of table" in result.output
    assert output_file.exists()

    # Verify exported data
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5
    assert data[0]["id"] == "item-1"
    assert data[0]["name"] == "Test Item 1"
    assert data[0]["status"] == "active"
    assert data[0]["count"] == "10"


@pytest.mark.integration
def test_export_table_csv_format(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in CSV format."""
    output_file = tmp_path / "export.csv"

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "csv",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify CSV content
    with open(output_file) as f:
        lines = f.readlines()

    # Check header
    assert "id" in lines[0]
    assert "name" in lines[0]
    assert "status" in lines[0]
    assert "count" in lines[0]

    # Check data rows (5 items + 1 header)
    assert len(lines) == 6


@pytest.mark.integration
def test_export_table_jsonl_format(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in JSONL format."""
    output_file = tmp_path / "export.jsonl"

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "jsonl",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify JSONL content (one JSON object per line)
    with open(output_file) as f:
        lines = f.readlines()

    assert len(lines) == 5

    # Parse first line
    first_item = json.loads(lines[0])
    assert first_item["id"] == "item-1"
    assert first_item["name"] == "Test Item 1"


@pytest.mark.integration
def test_export_table_tsv_format(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in TSV format."""
    output_file = tmp_path / "export.tsv"

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "tsv",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify TSV content (tab-separated)
    with open(output_file) as f:
        lines = f.readlines()

    # Check that tabs are used as delimiters
    assert "\t" in lines[0]
    assert len(lines) == 6  # 5 items + 1 header


@pytest.mark.integration
def test_export_table_with_filter(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with filter expression."""
    output_file = tmp_path / "export.json"

    # Run export command with filter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "status = active",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data (only active items)
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 3  # Only 3 active items
    for item in data:
        assert item["status"] == "active"


@pytest.mark.integration
def test_export_table_with_parallel_scan(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with parallel scanning."""
    output_file = tmp_path / "export.json"

    # Run export command with parallel scan
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--parallel-scan",
            "--segments",
            "2",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert "Parallel Scan" in result.output
    assert output_file.exists()

    # Verify all data is exported
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5


@pytest.mark.integration
def test_export_table_with_compression(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with gzip compression."""
    output_file = tmp_path / "export.json.gz"

    # Run export command with compression
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--compress",
            "gzip",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify compressed data can be read
    with gzip.open(output_file, "rt") as f:
        data = json.load(f)

    assert len(data) == 5
    assert data[0]["id"] == "item-1"


@pytest.mark.integration
def test_export_table_with_limit(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with item limit."""
    output_file = tmp_path / "export.json"

    # Run export command with limit
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--limit",
            "3",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify limited data
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 3


@pytest.mark.integration
def test_export_table_with_attributes(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with specific attributes."""
    output_file = tmp_path / "export.json"

    # Run export command with attribute projection
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--attributes",
            "id,name",
            "--yes",
        ],
        obj={},
    )

    # Debug output
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            import traceback

            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify only specified attributes are exported
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 5
    assert "id" in data[0]
    assert "name" in data[0]
    # status and count should not be present
    assert "status" not in data[0]
    assert "count" not in data[0]


@pytest.mark.integration
def test_export_nonexistent_table_returns_error(cli_runner, mock_aws_client, tmp_path):
    """Test export with non-existent table returns error."""
    output_file = tmp_path / "export.json"

    # Run export command with non-existent table
    result = cli_runner.invoke(
        export_table,
        [
            "nonexistent-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify error
    assert result.exit_code == 1
    assert not output_file.exists()


@pytest.mark.integration
def test_export_table_with_dry_run(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with dry-run flag."""
    output_file = tmp_path / "export.json"

    # Run export command with dry-run
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--dry-run",
        ],
        obj={},
    )

    # Verify success but no file created
    assert result.exit_code == 0
    assert "Dry run completed" in result.output
    assert not output_file.exists()


@pytest.mark.integration
def test_export_table_default_output_filename(cli_runner, mock_aws_client, tmp_path, mocker):
    """Test DynamoDB table export with default output filename."""
    # Change to tmp directory
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)

    # Run export command without output file (should generate default name)
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Check that a file was created with default naming pattern
    json_files = list(tmp_path.glob("test-table_*.json"))
    assert len(json_files) == 1

    # Verify exported data
    with open(json_files[0]) as f:
        data = json.load(f)

    assert len(data) == 5


@pytest.mark.integration
def test_export_table_with_multiple_filters(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with multiple filter conditions."""
    output_file = tmp_path / "export.json"

    # Run export command with complex filter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "status = active AND count > 20",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    # Should only have items with status=active AND count>20
    assert len(data) == 2  # item-3 (count=30) and item-5 (count=50)
    for item in data:
        assert item["status"] == "active"
        assert int(item["count"]) > 20


@pytest.mark.integration
def test_export_table_csv_with_custom_delimiter(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in CSV format with custom delimiter."""
    output_file = tmp_path / "export.csv"

    # Run export command with custom delimiter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "csv",
            "--delimiter",
            "|",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify custom delimiter is used
    with open(output_file) as f:
        lines = f.readlines()

    assert "|" in lines[0]  # Header should use custom delimiter
    assert "|" in lines[1]  # Data rows should use custom delimiter


@pytest.mark.integration
def test_export_table_with_metadata(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with metadata included."""
    output_file = tmp_path / "export.csv"

    # Run export command with metadata
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "csv",
            "--metadata",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify metadata is included in output
    with open(output_file) as f:
        content = f.read()

    # Metadata should be in comments at the top
    assert "# Table:" in content or "test-table" in content


@pytest.mark.integration
def test_export_table_json_pretty_format(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export in pretty-printed JSON format."""
    output_file = tmp_path / "export.json"

    # Run export command with pretty printing
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--pretty",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify pretty-printed format (should have indentation)
    with open(output_file) as f:
        content = f.read()

    # Pretty-printed JSON should have newlines and indentation
    assert "\n" in content
    assert "  " in content  # Indentation


@pytest.mark.integration
def test_export_empty_table(cli_runner, mock_dynamodb_client, tmp_path, mocker):
    """Test export of empty DynamoDB table."""
    # Create empty table
    mock_dynamodb_client.create_table(
        TableName="empty-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Mock create_aws_client
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_dynamodb_client)

    output_file = tmp_path / "export.json"

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "empty-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify warning about no items
    assert result.exit_code == 0
    assert "exported 0 items" in result.output.lower() or "no items" in result.output.lower()
    # File may or may not be created for empty results - implementation dependent


@pytest.mark.integration
def test_export_large_table_with_pagination(cli_runner, mock_dynamodb_client, tmp_path, mocker):
    """Test export of large DynamoDB table with pagination (100+ items)."""
    # Create table
    mock_dynamodb_client.create_table(
        TableName="large-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 150 items to test pagination
    for i in range(150):
        mock_dynamodb_client.put_item(
            TableName="large-table",
            Item={
                "id": {"S": f"item-{i:03d}"},
                "name": {"S": f"Test Item {i}"},
                "value": {"N": str(i * 10)},
            },
        )

    # Mock create_aws_client
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_dynamodb_client)

    output_file = tmp_path / "export.json"

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "large-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify all items were exported (pagination handled correctly)
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 150
    # Verify first and last items
    item_ids = [item["id"] for item in data]
    assert "item-000" in item_ids
    assert "item-149" in item_ids


@pytest.mark.integration
def test_export_with_complex_filter_expressions(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with complex filter expressions."""
    output_file = tmp_path / "export.json"

    # Test complex filter with OR, AND, and comparison operators
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "(status = active OR status = pending) AND count >= 30",
            "--yes",
        ],
        obj={},
    )

    # Debug output
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            import traceback

            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    # Should have items matching: (active OR pending) AND count >= 30
    # item-3: active, count=30 ✓
    # item-4: pending, count=40 ✓
    # item-5: active, count=50 ✓
    assert len(data) == 3
    for item in data:
        assert item["status"] in ["active", "pending"]
        assert int(item["count"]) >= 30


@pytest.mark.integration
def test_export_with_between_filter(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with BETWEEN filter expression."""
    output_file = tmp_path / "export.json"

    # Test BETWEEN filter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "count BETWEEN 20 AND 40",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    # Should have items with count between 20 and 40 (inclusive)
    assert len(data) == 3  # item-2 (20), item-3 (30), item-4 (40)
    for item in data:
        assert 20 <= int(item["count"]) <= 40


@pytest.mark.integration
def test_export_with_in_filter(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with IN filter expression."""
    output_file = tmp_path / "export.json"

    # Test IN filter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "status IN (active, pending)",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    # Should have items with status in [active, pending]
    assert len(data) == 4  # 3 active + 1 pending
    for item in data:
        assert item["status"] in ["active", "pending"]


@pytest.mark.integration
def test_export_with_contains_filter(cli_runner, mock_aws_client, tmp_path):
    """Test DynamoDB table export with CONTAINS filter expression."""
    output_file = tmp_path / "export.json"

    # Test CONTAINS filter
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            'contains(name, "Item 1")',
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    # Should have item-1 (Test Item 1)
    assert len(data) == 1
    assert data[0]["id"] == "item-1"
    assert "Item 1" in data[0]["name"]


@pytest.mark.integration
def test_export_with_network_timeout(cli_runner, mock_aws_client, tmp_path, mocker):
    """Test DynamoDB table export with network timeout."""
    output_file = tmp_path / "export.json"

    # Mock scan to raise timeout exception
    from botocore.exceptions import ReadTimeoutError
    from urllib3.exceptions import ReadTimeoutError as UrllibReadTimeoutError

    mock_scan = mocker.patch.object(mock_aws_client, "scan")
    mock_scan.side_effect = ReadTimeoutError(
        endpoint_url="https://dynamodb.us-east-1.amazonaws.com", error=UrllibReadTimeoutError(None, None, "Read timed out")
    )

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify error handling
    assert result.exit_code == 1
    assert "timeout" in result.output.lower() or "error" in result.output.lower()
    assert not output_file.exists()


@pytest.mark.integration
def test_export_with_connection_error(cli_runner, mock_aws_client, tmp_path, mocker):
    """Test DynamoDB table export with connection error."""
    output_file = tmp_path / "export.json"

    # Mock scan to raise connection error
    from botocore.exceptions import EndpointConnectionError

    mock_scan = mocker.patch.object(mock_aws_client, "scan")
    mock_scan.side_effect = EndpointConnectionError(endpoint_url="https://dynamodb.us-east-1.amazonaws.com")

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify error handling
    assert result.exit_code == 1
    assert "connection" in result.output.lower() or "error" in result.output.lower()
    assert not output_file.exists()


@pytest.mark.integration
def test_export_with_throttling_error(cli_runner, mock_aws_client, tmp_path, mocker):
    """Test DynamoDB table export with throttling error."""
    output_file = tmp_path / "export.json"

    # Mock scan to raise throttling exception
    from botocore.exceptions import ClientError

    mock_scan = mocker.patch.object(mock_aws_client, "scan")
    mock_scan.side_effect = ClientError(
        error_response={"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Rate of requests exceeds the allowed throughput"}},
        operation_name="Scan",
    )

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify error handling
    assert result.exit_code == 1
    assert "throughput" in result.output.lower() or "error" in result.output.lower()
    assert not output_file.exists()


@pytest.mark.integration
def test_export_with_access_denied_error(cli_runner, mock_aws_client, tmp_path, mocker):
    """Test DynamoDB table export with access denied error."""
    output_file = tmp_path / "export.json"

    # Mock scan to raise access denied exception
    from botocore.exceptions import ClientError

    mock_scan = mocker.patch.object(mock_aws_client, "scan")
    mock_scan.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException", "Message": "User is not authorized to perform: dynamodb:Scan"}},
        operation_name="Scan",
    )

    # Run export command
    result = cli_runner.invoke(
        export_table,
        [
            "test-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--yes",
        ],
        obj={},
    )

    # Verify error handling
    assert result.exit_code == 1
    assert "access" in result.output.lower() or "authorized" in result.output.lower() or "error" in result.output.lower()
    assert not output_file.exists()


@pytest.mark.integration
def test_export_large_table_with_parallel_scan(cli_runner, mock_dynamodb_client, tmp_path, mocker):
    """Test export of large table with parallel scanning for better performance."""
    # Create table
    mock_dynamodb_client.create_table(
        TableName="large-parallel-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 200 items
    for i in range(200):
        mock_dynamodb_client.put_item(
            TableName="large-parallel-table",
            Item={
                "id": {"S": f"item-{i:03d}"},
                "data": {"S": f"Data {i}"},
            },
        )

    # Mock create_aws_client
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_dynamodb_client)

    output_file = tmp_path / "export.json"

    # Run export command with parallel scan
    result = cli_runner.invoke(
        export_table,
        [
            "large-parallel-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--parallel-scan",
            "--segments",
            "4",
            "--yes",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0
    assert "Parallel Scan" in result.output
    assert output_file.exists()

    # Verify all items were exported
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 200


@pytest.mark.integration
def test_export_with_nested_attribute_filter(cli_runner, mock_dynamodb_client, tmp_path, mocker):
    """Test DynamoDB table export with filter on nested attributes."""
    # Create table with nested attributes
    mock_dynamodb_client.create_table(
        TableName="nested-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add items with nested attributes
    mock_dynamodb_client.put_item(
        TableName="nested-table", Item={"id": {"S": "item-1"}, "metadata": {"M": {"status": {"S": "active"}, "priority": {"N": "1"}}}}
    )
    mock_dynamodb_client.put_item(
        TableName="nested-table", Item={"id": {"S": "item-2"}, "metadata": {"M": {"status": {"S": "inactive"}, "priority": {"N": "2"}}}}
    )

    # Mock create_aws_client
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_dynamodb_client)

    output_file = tmp_path / "export.json"

    # Run export command with nested attribute filter
    result = cli_runner.invoke(
        export_table,
        [
            "nested-table",
            "--output",
            str(output_file),
            "--format",
            "json",
            "--filter",
            "metadata.status = active",
            "--yes",
        ],
        obj={},
    )

    # Debug output
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            import traceback

            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    # Verify success
    assert result.exit_code == 0
    assert output_file.exists()

    # Verify filtered data
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["id"] == "item-1"
    assert data[0]["metadata"]["status"] == "active"
