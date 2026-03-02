"""DynamoDB core functionality."""

from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter
from cli_tool.commands.dynamodb.core.multi_query_executor import execute_multi_query
from cli_tool.commands.dynamodb.core.parallel_scanner import ParallelScanner
from cli_tool.commands.dynamodb.core.query_optimizer import detect_usable_index, should_use_parallel_scan

__all__ = [
    "DynamoDBExporter",
    "ParallelScanner",
    "detect_usable_index",
    "execute_multi_query",
    "should_use_parallel_scan",
]
