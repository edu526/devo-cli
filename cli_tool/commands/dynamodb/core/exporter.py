"""DynamoDB table exporter with multiple format support."""

import csv
import gzip
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from boto3.dynamodb.types import TypeDeserializer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

_PROGRESS_DESCRIPTION_COL = "[progress.description]{task.description}"

console = Console()


class DynamoDBExporter:
    """Export DynamoDB tables to various formats."""

    def __init__(
        self,
        table_name: str,
        dynamodb_client,
        region: str,
        profile: Optional[str] = None,
    ):
        self.table_name = table_name
        self.dynamodb = dynamodb_client
        self.region = region
        self.profile = profile
        self.deserializer = TypeDeserializer()
        self.stats = {
            "total_items": 0,
            "start_time": None,
            "end_time": None,
            "file_size": 0,
            "consumed_capacity": 0.0,
            "scanned_count": 0,
        }

    def _convert_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item to plain Python dict."""
        result = {}
        for key, value in item.items():
            # Use boto3's TypeDeserializer to convert DynamoDB format to Python types
            result[key] = self.deserializer.deserialize(value)
        return result

    def _convert_value(self, value: Any) -> Any:
        """Convert DynamoDB value types to Python types."""
        if isinstance(value, Decimal):
            # Convert Decimal to int or float
            if value % 1 == 0:
                return int(value)
            return float(value)
        elif isinstance(value, dict):
            return {k: self._convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._convert_value(v) for v in value]
        elif isinstance(value, set):
            return list(value)
        return value

    def _flatten_dict(
        self,
        data: Dict[str, Any],
        parent_key: str = "",
        separator: str = ".",
        list_separator: str = "|",
    ) -> Dict[str, Any]:
        """Flatten nested dictionaries and join lists with separator."""
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(self._flatten_dict(value, new_key, separator, list_separator).items())
            elif isinstance(value, list):
                # Join list items with separator
                if all(isinstance(item, (str, int, float, bool, type(None), Decimal)) for item in value):
                    # Convert Decimals in the list
                    converted_items = [self._convert_value(v) for v in value]
                    items.append((new_key, list_separator.join(str(v) for v in converted_items)))
                else:
                    # Complex list items, convert then serialize to JSON
                    converted_value = self._convert_value(value)
                    items.append((new_key, json.dumps(converted_value)))
            else:
                items.append((new_key, value))
        return dict(items)

    def _serialize_as_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize complex types (lists, dicts) as JSON strings."""
        result = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                # Convert value first (handles Decimal), then serialize to JSON
                converted_value = self._convert_value(value)
                result[key] = json.dumps(converted_value)
            else:
                result[key] = value
        return result

    def _normalize_lists(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Expand lists into multiple rows (normalization)."""
        # Find all list fields
        list_fields = {k: v for k, v in data.items() if isinstance(v, list)}

        if not list_fields:
            # No lists to normalize, return single row
            return [data]

        # Find the list with most items to use as base
        max_list_key = max(list_fields.keys(), key=lambda k: len(list_fields[k]))
        max_list = list_fields[max_list_key]

        # Create one row per item in the longest list
        rows = []
        for i, item in enumerate(max_list):
            row = {}
            for key, value in data.items():
                if isinstance(value, list):
                    # Use item at index if available, otherwise use last item or None
                    if i < len(value):
                        row[key] = value[i]
                    elif value:
                        row[key] = value[-1]  # Repeat last value
                    else:
                        row[key] = None
                else:
                    # Non-list values are repeated in all rows
                    row[key] = value
            rows.append(row)

        return rows

    def _format_bool_for_csv(self, value: bool, bool_format: str) -> str:
        """Format a boolean value for CSV output according to bool_format style."""
        _BOOL_FORMATS = {
            "lowercase": ("true", "false"),
            "uppercase": ("True", "False"),
            "numeric": ("1", "0"),
            "letter": ("t", "f"),
        }
        true_val, false_val = _BOOL_FORMATS.get(bool_format, (str(value).lower(), str(value).lower()))
        return true_val if value else false_val

    def _format_value_for_csv(self, value: Any, null_value: str = "", bool_format: str = "lowercase") -> str:
        """Format value for CSV output.

        Args:
          bool_format: 'lowercase' (true/false), 'uppercase' (True/False), 'numeric' (1/0), 'letter' (t/f)
        """
        if value is None:
            return null_value
        if isinstance(value, bool):
            return self._format_bool_for_csv(value, bool_format)
        if isinstance(value, Decimal):
            # Convert Decimal to int or float
            if value % 1 == 0:
                return str(int(value))
            return str(float(value))
        if isinstance(value, (list, dict)):
            # Convert first to handle Decimals, then serialize
            converted = self._convert_value(value)
            return json.dumps(converted)
        if isinstance(value, str):
            # Normalize whitespace: replace multiple spaces/newlines with single space
            # This prevents CSV parsing issues with multiline text
            normalized = " ".join(value.split())
            return normalized
        return str(value)

    def scan_table(
        self,
        limit: Optional[int] = None,
        filter_expression: Optional[str] = None,
        projection_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        parallel_scan: bool = False,
        segment: Optional[int] = None,
        total_segments: Optional[int] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Scan DynamoDB table with optional filters."""
        items = []
        scan_kwargs = {"TableName": self.table_name}

        if filter_expression:
            scan_kwargs["FilterExpression"] = filter_expression
        if projection_expression:
            scan_kwargs["ProjectionExpression"] = projection_expression
        if index_name:
            scan_kwargs["IndexName"] = index_name
        if parallel_scan and segment is not None and total_segments is not None:
            scan_kwargs["Segment"] = segment
            scan_kwargs["TotalSegments"] = total_segments
        if expression_attribute_values:
            scan_kwargs["ExpressionAttributeValues"] = expression_attribute_values
        if expression_attribute_names:
            scan_kwargs["ExpressionAttributeNames"] = expression_attribute_names

        with Progress(
            SpinnerColumn(),
            TextColumn(_PROGRESS_DESCRIPTION_COL),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Scanning {self.table_name}...",
                total=None,
            )

            while True:
                response = self.dynamodb.scan(**scan_kwargs)
                batch_items = response.get("Items", [])
                items.extend(batch_items)

                progress.update(task, advance=len(batch_items))

                if limit and len(items) >= limit:
                    items = items[:limit]
                    break

                if "LastEvaluatedKey" not in response:
                    break

                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            progress.update(task, description=f"[green]✓ Scanned {len(items)} items")

        return items

    def query_table(
        self,
        key_condition_expression: str,
        filter_expression: Optional[str] = None,
        projection_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query DynamoDB table."""
        items = []
        query_kwargs = {
            "TableName": self.table_name,
            "KeyConditionExpression": key_condition_expression,
        }

        if filter_expression:
            query_kwargs["FilterExpression"] = filter_expression
        if projection_expression:
            query_kwargs["ProjectionExpression"] = projection_expression
        if index_name:
            query_kwargs["IndexName"] = index_name
        if expression_attribute_values:
            query_kwargs["ExpressionAttributeValues"] = expression_attribute_values
        if expression_attribute_names:
            query_kwargs["ExpressionAttributeNames"] = expression_attribute_names

        with Progress(
            SpinnerColumn(),
            TextColumn(_PROGRESS_DESCRIPTION_COL),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Querying {self.table_name}...")

            while True:
                response = self.dynamodb.query(**query_kwargs)
                batch_items = response.get("Items", [])
                items.extend(batch_items)

                if limit and len(items) >= limit:
                    items = items[:limit]
                    break

                if "LastEvaluatedKey" not in response:
                    break

                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            progress.update(task, description=f"[green]✓ Queried {len(items)} items")

        return items

    def _open_csv_file_handle(self, output_file: Path, compress: Optional[str], encoding: str):
        """Open the appropriate file handle for CSV writing based on compression type.

        Returns (actual_output_file, file_handle, zip_file_or_None).
        """
        actual_output_file = output_file
        zip_file = None

        if compress == "gzip":
            actual_output_file = output_file.with_suffix(output_file.suffix + ".gz")
            file_handle = gzip.open(actual_output_file, "wt", encoding=encoding, newline="")
        elif compress == "zip":
            import io

            actual_output_file = output_file.with_suffix(".zip")
            zip_file = zipfile.ZipFile(actual_output_file, "w", zipfile.ZIP_DEFLATED)
            file_handle = zip_file.open(output_file.name, "w")
            file_handle = io.TextIOWrapper(file_handle, encoding=encoding, newline="")
        else:
            file_handle = actual_output_file.open("w", encoding=encoding, newline="")

        return actual_output_file, file_handle, zip_file

    def _write_csv_metadata(self, file_handle, actual_output_file: Path, compress: Optional[str], total_items: int, mode: str) -> None:
        """Write export metadata either as a sidecar .meta file (compressed) or as comment lines."""
        if compress:
            meta_file = actual_output_file.with_suffix(".meta")
            with meta_file.open("w", encoding="utf-8") as mf:
                mf.write(f"Export Date: {datetime.now().isoformat()}\n")
                mf.write(f"Table: {self.table_name}\n")
                mf.write(f"Region: {self.region}\n")
                if self.profile:
                    mf.write(f"Profile: {self.profile}\n")
                mf.write(f"Total Items: {total_items}\n")
                mf.write(f"Mode: {mode}\n")
            console.print(f"[cyan]Metadata written to: {meta_file}[/cyan]")
        else:
            file_handle.write(f"# Export Date: {datetime.now().isoformat()}\n")
            file_handle.write(f"# Table: {self.table_name}\n")
            file_handle.write(f"# Region: {self.region}\n")
            if self.profile:
                file_handle.write(f"# Profile: {self.profile}\n")
            file_handle.write(f"# Total Items: {total_items}\n")
            file_handle.write(f"# Mode: {mode}\n")
            file_handle.write("#\n")

    def _convert_items_for_csv(self, items: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
        """Convert DynamoDB items to plain dicts according to the CSV export mode."""
        converted_items = []
        for item in items:
            converted = self._convert_dynamodb_item(item)
            if mode == "strings":
                converted_items.append(self._serialize_as_json(converted))
            elif mode == "flatten":
                converted_items.append(self._flatten_dict(converted))
            elif mode == "normalize":
                for row in self._normalize_lists(converted):
                    converted_items.append(self._flatten_dict(row))
            else:
                converted_items.append(converted)
        return converted_items

    def _warn_normalize_large_lists(self, items: List[Dict[str, Any]]) -> None:
        """Warn the user when normalize mode may produce a very large number of rows."""
        max_list_size = 0
        total_rows_estimate = 0
        for item in items[:100]:  # Sample first 100 items
            converted = self._convert_dynamodb_item(item)
            normalized = self._normalize_lists(converted)
            max_list_size = max(max_list_size, len(normalized))
            total_rows_estimate += len(normalized)

        if max_list_size > 100:
            console.print(f"[yellow]⚠ Warning: Detected items with large lists (up to {max_list_size} elements)[/yellow]")
            console.print(f"[yellow]  Normalize mode will expand these into {total_rows_estimate:,}+ rows[/yellow]")
            console.print("[yellow]  Consider using 'strings' or 'flatten' mode for better performance[/yellow]")

    def export_to_csv(
        self,
        items: List[Dict[str, Any]],
        output_file: Path,
        mode: str = "strings",
        null_value: str = "",
        delimiter: str = ",",
        encoding: str = "utf-8",
        include_metadata: bool = False,
        compress: Optional[str] = None,
        bool_format: str = "lowercase",
        streaming: bool = False,
    ) -> Path:
        """Export items to CSV format.

        Args:
          mode: 'strings' (serialize as JSON), 'flatten' (flatten nested), 'normalize' (expand lists to rows)
          bool_format: 'lowercase' (true/false), 'uppercase' (True/False), 'numeric' (1/0), 'letter' (t/f)
          streaming: If True, write items as they're processed (memory efficient)

        Returns:
            Path: The actual output file path (may differ from input if compressed)
        """
        if not items:
            console.print("[yellow]⚠ No items to export[/yellow]")
            return output_file

        self.stats["start_time"] = datetime.now()

        if mode == "normalize":
            self._warn_normalize_large_lists(items)

        # For large datasets, use streaming mode
        if len(items) > 10000 and not streaming:
            console.print(f"[cyan]Using streaming mode for {len(items):,} items (memory efficient)[/cyan]")
            streaming = True

        if streaming:
            return self._export_to_csv_streaming(items, output_file, mode, null_value, delimiter, encoding, include_metadata, compress, bool_format)

        # Non-streaming mode: convert all items first, then write
        converted_items = self._convert_items_for_csv(items, mode)

        # Get all unique keys for CSV headers
        all_keys: set = set()  # noqa: C405
        for item in converted_items:
            all_keys.update(item.keys())
        fieldnames = sorted(all_keys)

        actual_output_file, file_handle, zip_file = self._open_csv_file_handle(output_file, compress, encoding)

        try:
            writer = csv.DictWriter(
                file_handle,
                fieldnames=fieldnames,
                delimiter=delimiter,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
                escapechar=None,
            )

            if include_metadata:
                self._write_csv_metadata(file_handle, actual_output_file, compress, len(converted_items), mode)

            writer.writeheader()

            with Progress(
                SpinnerColumn(),
                TextColumn(_PROGRESS_DESCRIPTION_COL),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "[cyan]Writing CSV...",
                    total=len(converted_items),
                )

                for item in converted_items:
                    formatted_item = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in item.items()}
                    writer.writerow(formatted_item)
                    progress.update(task, advance=1)

        finally:
            file_handle.close()
            if zip_file:
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = len(converted_items)
        self.stats["file_size"] = actual_output_file.stat().st_size

        return actual_output_file

    def _collect_streaming_fieldnames(self, items: List[Dict[str, Any]], mode: str, sample_size: int) -> List[str]:
        """Sample the first items to discover all possible CSV column names."""
        all_keys: set = set()  # noqa: C405
        for item in items[:sample_size]:
            converted = self._convert_dynamodb_item(item)
            if mode == "strings":
                converted = self._serialize_as_json(converted)
                all_keys.update(converted.keys())
            elif mode == "flatten":
                converted = self._flatten_dict(converted)
                all_keys.update(converted.keys())
            elif mode == "normalize":
                for row in self._normalize_lists(converted):
                    all_keys.update(self._flatten_dict(row).keys())
            else:
                all_keys.update(converted.keys())
        return sorted(all_keys)

    def _write_streaming_item(self, writer, converted: Dict[str, Any], mode: str, null_value: str, bool_format: str) -> int:
        """Write a single converted item (or its normalized rows) to the CSV writer.

        Returns the number of rows written.
        """
        rows_written = 0
        if mode == "normalize":
            for row in self._normalize_lists(converted):
                flattened = self._flatten_dict(row)
                formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in flattened.items()}
                writer.writerow(formatted)
                rows_written += 1
        else:
            if mode == "strings":
                converted = self._serialize_as_json(converted)
            elif mode == "flatten":
                converted = self._flatten_dict(converted)
            formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in converted.items()}
            writer.writerow(formatted)
            rows_written = 1
        return rows_written

    def _export_to_csv_streaming(
        self,
        items: List[Dict[str, Any]],
        output_file: Path,
        mode: str,
        null_value: str,
        delimiter: str,
        encoding: str,
        include_metadata: bool,
        compress: Optional[str],
        bool_format: str,
    ) -> Path:
        """Stream items to CSV without loading all in memory.

        Returns:
            Path: The actual output file path (may differ from input if compressed)
        """
        fieldnames = self._collect_streaming_fieldnames(items, mode, min(1000, len(items)))

        actual_output_file, file_handle, zip_file = self._open_csv_file_handle(output_file, compress, encoding)

        try:
            writer = csv.DictWriter(
                file_handle,
                fieldnames=fieldnames,
                delimiter=delimiter,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
                escapechar=None,
            )

            if include_metadata:
                self._write_csv_metadata(file_handle, actual_output_file, compress, len(items), mode)

            writer.writeheader()

            items_written = 0
            with Progress(
                SpinnerColumn(),
                TextColumn(_PROGRESS_DESCRIPTION_COL),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "[cyan]Streaming CSV...",
                    total=len(items),
                )

                for item in items:
                    converted = self._convert_dynamodb_item(item)
                    items_written += self._write_streaming_item(writer, converted, mode, null_value, bool_format)
                    progress.update(task, advance=1)

        finally:
            file_handle.close()
            if zip_file:
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = items_written
        self.stats["file_size"] = actual_output_file.stat().st_size

        return actual_output_file

    def _open_json_file_handle(self, output_file: Path, compress: Optional[str], encoding: str):
        """Open the appropriate file handle for JSON writing based on compression type.

        Returns (actual_output_file, file_handle, zip_file_or_None).
        """
        actual_output_file = output_file
        zip_file = None

        if compress == "gzip":
            # Only add .gz if not already present
            if not str(output_file).endswith(".gz"):
                actual_output_file = output_file.with_suffix(output_file.suffix + ".gz")
            file_handle = gzip.open(actual_output_file, "wt", encoding=encoding)
        elif compress == "zip":
            import io

            # Only add .zip if not already present
            if not str(output_file).endswith(".zip"):
                actual_output_file = output_file.with_suffix(".zip")
            zip_file = zipfile.ZipFile(actual_output_file, "w", zipfile.ZIP_DEFLATED)
            # Use original filename without .zip for the entry inside the zip
            entry_name = output_file.stem + output_file.suffix if not str(output_file).endswith(".zip") else output_file.stem
            file_handle = zip_file.open(entry_name, "w")
            file_handle = io.TextIOWrapper(file_handle, encoding=encoding)
        else:
            file_handle = actual_output_file.open("w", encoding=encoding)

        return actual_output_file, file_handle, zip_file

    def _write_json_items(self, file_handle, converted_items: List[Dict[str, Any]], jsonl: bool, pretty: bool) -> None:
        """Write converted items to file_handle in JSON or JSONL format."""
        if jsonl:
            for item in converted_items:
                json.dump(item, file_handle, default=str)
                file_handle.write("\n")
        elif pretty:
            json.dump(converted_items, file_handle, indent=2, default=str)
        else:
            json.dump(converted_items, file_handle, default=str)

    def export_to_json(
        self,
        items: List[Dict[str, Any]],
        output_file: Path,
        jsonl: bool = False,
        pretty: bool = True,
        encoding: str = "utf-8",
        compress: Optional[str] = None,
    ) -> Path:
        """Export items to JSON or JSONL format.

        Returns:
            Path: The actual output file path (may differ from input if compressed)
        """
        if not items:
            console.print("[yellow]⚠ No items to export[/yellow]")
            return output_file

        self.stats["start_time"] = datetime.now()

        converted_items = [self._convert_dynamodb_item(item) for item in items]

        actual_output_file, file_handle, zip_file = self._open_json_file_handle(output_file, compress, encoding)

        try:
            self._write_json_items(file_handle, converted_items, jsonl, pretty)
        finally:
            file_handle.close()
            if zip_file:
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = len(converted_items)
        self.stats["file_size"] = actual_output_file.stat().st_size

        return actual_output_file

    def get_table_info(self) -> Dict[str, Any]:
        """Get table metadata."""
        response = self.dynamodb.describe_table(TableName=self.table_name)
        table = response["Table"]

        info = {
            "name": table["TableName"],
            "status": table.get("TableStatus", "ACTIVE"),
            "item_count": table.get("ItemCount", 0),
            "size_bytes": table.get("TableSizeBytes", 0),
            "key_schema": table.get("KeySchema", []),
            "attributes": table.get("AttributeDefinitions", []),
            "global_indexes": table.get("GlobalSecondaryIndexes", []),
            "local_indexes": table.get("LocalSecondaryIndexes", []),
        }

        # Add creation date if available
        if "CreationDateTime" in table:
            info["creation_date"] = table["CreationDateTime"].isoformat()

        return info

    def print_stats(self, output_file: Path) -> None:
        """Print export statistics."""
        if not self.stats["start_time"]:
            return

        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        file_size_mb = self.stats["file_size"] / (1024 * 1024)

        console.print("\n[bold green]✓ Export completed successfully![/bold green]\n")
        console.print(f"[cyan]Table:[/cyan] {self.table_name}")
        console.print(f"[cyan]Items exported:[/cyan] {self.stats['total_items']:,}")
        console.print(f"[cyan]Duration:[/cyan] {duration:.2f}s")

        if self.stats["total_items"] > 0 and duration > 0:
            items_per_sec = self.stats["total_items"] / duration
            console.print(f"[cyan]Throughput:[/cyan] {items_per_sec:.0f} items/sec")

        console.print(f"[cyan]File size:[/cyan] {file_size_mb:.2f} MB")

        if self.stats.get("consumed_capacity", 0) > 0:
            console.print(f"[cyan]Consumed capacity:[/cyan] {self.stats['consumed_capacity']:.2f} RCUs")

        if self.stats.get("scanned_count", 0) > 0 and self.stats["scanned_count"] != self.stats["total_items"]:
            console.print(f"[cyan]Items scanned:[/cyan] {self.stats['scanned_count']:,} (filtered to {self.stats['total_items']:,})")
            filter_ratio = (self.stats["total_items"] / self.stats["scanned_count"]) * 100
            console.print(f"[cyan]Filter efficiency:[/cyan] {filter_ratio:.1f}%")

        console.print(f"[cyan]Output:[/cyan] {output_file}")
