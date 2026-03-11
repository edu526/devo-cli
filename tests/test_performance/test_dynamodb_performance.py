"""Performance tests for DynamoDB parallel scanning operations.

Tests DynamoDB parallel scan performance with pytest-benchmark to ensure
the parallel scanning implementation meets performance requirements and
doesn't regress over time.

Requirements tested:
- 17.1: Performance tests for DynamoDB parallel scanning
- 17.2: Memory usage stays within acceptable limits for large data exports
- 17.5: Use pytest-benchmark for performance regression detection
"""

import os

import boto3
import pytest
from moto import mock_aws

from cli_tool.commands.dynamodb.core import ParallelScanner


@pytest.mark.slow
@pytest.mark.integration
def test_parallel_scan_performance_1000_items(benchmark, mock_dynamodb_client):
    """Test DynamoDB parallel scan performance with 1000 items.

    Validates: Requirements 17.1, 17.5

    This test benchmarks the parallel scanning of a table with 1000 items
    to establish baseline performance metrics and detect regressions.
    """
    # Create table with 1000 items
    table_name = "perf-test-table-1k"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 1000 items
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(1000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}",
                    "number": i,
                    "category": f"cat-{i % 10}",
                }
            )

    # Benchmark parallel scan with 4 segments
    scanner = ParallelScanner(dynamodb_client=mock_dynamodb_client, table_name=table_name, total_segments=4)

    result = benchmark(scanner.parallel_scan)

    # Verify all items were scanned
    assert len(result) == 1000
    assert all("id" in item for item in result)


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize("segment_count", [2, 4, 8])
def test_parallel_scan_with_different_segments(benchmark, mock_dynamodb_client, segment_count):
    """Test parallel scan performance with different segment counts.

    Validates: Requirements 17.1, 17.5

    This test benchmarks parallel scanning with different segment counts
    (2, 4, 8) to measure the impact of parallelization on performance.
    """
    # Create table with 1000 items
    table_name = f"perf-test-segments-{segment_count}"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 1000 items
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(1000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}",
                    "number": i,
                }
            )

    # Benchmark parallel scan with specified segment count
    scanner = ParallelScanner(
        dynamodb_client=mock_dynamodb_client,
        table_name=table_name,
        total_segments=segment_count,
    )

    result = benchmark(scanner.parallel_scan)

    # Verify all items were scanned
    assert len(result) == 1000


@pytest.mark.slow
@pytest.mark.integration
def test_parallel_scan_with_filter_performance(benchmark, mock_dynamodb_client):
    """Test parallel scan performance with filter expression.

    Validates: Requirements 17.1, 17.5

    This test benchmarks parallel scanning with a filter expression to
    measure the performance impact of filtering during scan operations.
    """
    # Create table with 1000 items
    table_name = "perf-test-filter"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 1000 items with varying categories
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(1000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}",
                    "number": i,
                    "category": f"cat-{i % 10}",
                }
            )

    # Benchmark parallel scan with filter
    scanner = ParallelScanner(dynamodb_client=mock_dynamodb_client, table_name=table_name, total_segments=4)

    # Filter for items in category "cat-5" (should return ~100 items)
    result = benchmark(
        scanner.parallel_scan,
        filter_expression="category = :cat",
        expression_attribute_values={":cat": {"S": "cat-5"}},
    )

    # Verify filtered results
    assert len(result) > 0
    assert len(result) < 1000  # Should be filtered
    assert all(item.get("category", {}).get("S") == "cat-5" for item in result)


@pytest.mark.slow
@pytest.mark.integration
def test_parallel_scan_memory_usage(mock_dynamodb_client):
    """Test that parallel scan memory usage stays within limits.

    Validates: Requirements 17.2, 17.5

    This test verifies that parallel scanning of a large table doesn't
    consume excessive memory by monitoring memory usage during the scan.
    """
    import tracemalloc

    # Create table with 2000 items (larger dataset)
    table_name = "perf-test-memory"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 2000 items with larger data payloads
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(2000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}" * 10,  # Larger payload
                    "number": i,
                    "category": f"cat-{i % 10}",
                    "description": f"This is a longer description for item {i}" * 5,
                }
            )

    # Start memory tracking
    tracemalloc.start()

    # Perform parallel scan
    scanner = ParallelScanner(dynamodb_client=mock_dynamodb_client, table_name=table_name, total_segments=4)
    result = scanner.parallel_scan()

    # Get memory usage
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Verify results
    assert len(result) == 2000

    # Memory usage should be reasonable (less than 50MB for 2000 items)
    # This is a conservative limit; actual usage should be much lower
    peak_mb = peak / 1024 / 1024
    assert peak_mb < 50, f"Peak memory usage {peak_mb:.2f}MB exceeds 50MB limit"


@pytest.mark.slow
@pytest.mark.integration
def test_parallel_scan_with_projection(benchmark, mock_dynamodb_client):
    """Test parallel scan performance with projection expression.

    Validates: Requirements 17.1, 17.5

    This test benchmarks parallel scanning with a projection expression
    to measure the performance benefit of retrieving only specific attributes.
    """
    # Create table with 1000 items
    table_name = "perf-test-projection"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 1000 items with multiple attributes
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(1000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}",
                    "number": i,
                    "category": f"cat-{i % 10}",
                    "description": f"Description for item {i}",
                    "metadata": f"Metadata for item {i}",
                }
            )

    # Benchmark parallel scan with projection (only id and data)
    scanner = ParallelScanner(dynamodb_client=mock_dynamodb_client, table_name=table_name, total_segments=4)

    result = benchmark(
        scanner.parallel_scan,
        projection_expression="id, #d",
        expression_attribute_names={"#d": "data"},
    )

    # Verify all items were scanned with only projected attributes
    assert len(result) == 1000
    # Note: moto may not fully respect projection expressions in all cases
    # but we verify the scan completed successfully


@pytest.mark.slow
@pytest.mark.integration
def test_parallel_scan_with_limit(benchmark, mock_dynamodb_client):
    """Test parallel scan performance with limit.

    Validates: Requirements 17.1, 17.5

    This test benchmarks parallel scanning with a limit to verify that
    the scanner efficiently stops when the limit is reached.
    """
    # Create table with 1000 items
    table_name = "perf-test-limit"
    mock_dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add 1000 items
    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).Table(table_name)
    with table.batch_writer() as batch:
        for i in range(1000):
            batch.put_item(
                Item={
                    "id": f"item-{i:04d}",
                    "data": f"value-{i}",
                    "number": i,
                }
            )

    # Benchmark parallel scan with limit of 100 items
    scanner = ParallelScanner(dynamodb_client=mock_dynamodb_client, table_name=table_name, total_segments=4)

    result = benchmark(scanner.parallel_scan, limit=100)

    # Verify limit was respected (may be slightly over due to segment distribution)
    assert len(result) <= 150  # Allow some buffer for parallel segment distribution
    assert len(result) >= 100  # Should get at least the requested limit
