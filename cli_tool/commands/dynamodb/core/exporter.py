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

    def _format_value_for_csv(self, value: Any, null_value: str = "", bool_format: str = "lowercase") -> str:
        """Format value for CSV output.

        Args:
          bool_format: 'lowercase' (true/false), 'uppercase' (True/False), 'numeric' (1/0), 'letter' (t/f)
        """
        if value is None:
            return null_value
        if isinstance(value, bool):
            if bool_format == "lowercase":
                return "true" if value else "false"
            elif bool_format == "uppercase":
                return "True" if value else "False"
            elif bool_format == "numeric":
                return "1" if value else "0"
            elif bool_format == "letter":
                return "t" if value else "f"
            else:
                return str(value).lower()
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
            TextColumn("[progress.description]{task.description}"),
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
            TextColumn("[progress.description]{task.description}"),
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
    ) -> None:
        """Export items to CSV format.

        Args:
          mode: 'strings' (serialize as JSON), 'flatten' (flatten nested), 'normalize' (expand lists to rows)
          bool_format: 'lowercase' (true/false), 'uppercase' (True/False), 'numeric' (1/0), 'letter' (t/f)
          streaming: If True, write items as they're processed (memory efficient)
        """
        if not items:
            console.print("[yellow]⚠ No items to export[/yellow]")
            return

        self.stats["start_time"] = datetime.now()

        # Warn about normalize mode with large lists
        if mode == "normalize":
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

        # For large datasets, use streaming mode
        if len(items) > 10000 and not streaming:
            console.print(f"[cyan]Using streaming mode for {len(items):,} items (memory efficient)[/cyan]")
            streaming = True

        if streaming:
            self._export_to_csv_streaming(items, output_file, mode, null_value, delimiter, encoding, include_metadata, compress, bool_format)
            return

        # Non-streaming mode (original implementation)
        # Convert items based on export mode
        converted_items = []
        for item in items:
            converted = self._convert_dynamodb_item(item)

            if mode == "strings":
                converted = self._serialize_as_json(converted)
                converted_items.append(converted)
            elif mode == "flatten":
                converted = self._flatten_dict(converted)
                converted_items.append(converted)
            elif mode == "normalize":
                normalized_rows = self._normalize_lists(converted)
                for row in normalized_rows:
                    flattened_row = self._flatten_dict(row)
                    converted_items.append(flattened_row)
            else:
                converted_items.append(converted)

        # Get all unique keys for CSV headers
        all_keys = set()
        for item in converted_items:
            all_keys.update(item.keys())
        fieldnames = sorted(all_keys)

        # Determine output file with compression
        if compress == "gzip":
            output_file = output_file.with_suffix(output_file.suffix + ".gz")
            file_handle = gzip.open(output_file, "wt", encoding=encoding, newline="")
        elif compress == "zip":
            zip_path = output_file.with_suffix(".zip")
            zip_file = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
            file_handle = zip_file.open(output_file.name, "w")
            import io

            file_handle = io.TextIOWrapper(file_handle, encoding=encoding, newline="")
        else:
            file_handle = open(output_file, "w", encoding=encoding, newline="")

        try:
            writer = csv.DictWriter(
                file_handle,
                fieldnames=fieldnames,
                delimiter=delimiter,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
                escapechar=None,
            )

            # Write metadata
            if include_metadata:
                if compress:
                    meta_file = output_file.with_suffix(".meta")
                    with open(meta_file, "w", encoding="utf-8") as mf:
                        mf.write(f"Export Date: {datetime.now().isoformat()}\n")
                        mf.write(f"Table: {self.table_name}\n")
                        mf.write(f"Region: {self.region}\n")
                        if self.profile:
                            mf.write(f"Profile: {self.profile}\n")
                        mf.write(f"Total Items: {len(converted_items)}\n")
                        mf.write(f"Mode: {mode}\n")
                    console.print(f"[cyan]Metadata written to: {meta_file}[/cyan]")
                else:
                    file_handle.write(f"# Export Date: {datetime.now().isoformat()}\n")
                    file_handle.write(f"# Table: {self.table_name}\n")
                    file_handle.write(f"# Region: {self.region}\n")
                    if self.profile:
                        file_handle.write(f"# Profile: {self.profile}\n")
                    file_handle.write(f"# Total Items: {len(converted_items)}\n")
                    file_handle.write(f"# Mode: {mode}\n")
                    file_handle.write("#\n")

            writer.writeheader()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
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
            if compress == "zip":
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = len(converted_items)
        self.stats["file_size"] = output_file.stat().st_size if compress != "zip" else zip_path.stat().st_size

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
    ) -> None:
        """Stream items to CSV without loading all in memory."""
        # First pass: collect all possible fieldnames
        all_keys = set()
        sample_size = min(1000, len(items))
        for item in items[:sample_size]:
            converted = self._convert_dynamodb_item(item)
            if mode == "strings":
                converted = self._serialize_as_json(converted)
            elif mode == "flatten":
                converted = self._flatten_dict(converted)
            elif mode == "normalize":
                normalized = self._normalize_lists(converted)
                for row in normalized:
                    all_keys.update(self._flatten_dict(row).keys())
                continue
            all_keys.update(converted.keys())

        fieldnames = sorted(all_keys)

        # Open file for writing
        if compress == "gzip":
            output_file = output_file.with_suffix(output_file.suffix + ".gz")
            file_handle = gzip.open(output_file, "wt", encoding=encoding, newline="")
        elif compress == "zip":
            zip_path = output_file.with_suffix(".zip")
            zip_file = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
            file_handle = zip_file.open(output_file.name, "w")
            import io

            file_handle = io.TextIOWrapper(file_handle, encoding=encoding, newline="")
        else:
            file_handle = open(output_file, "w", encoding=encoding, newline="")

        try:
            writer = csv.DictWriter(
                file_handle,
                fieldnames=fieldnames,
                delimiter=delimiter,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
                escapechar=None,
            )

            # Write metadata
            if include_metadata:
                if compress:
                    meta_file = output_file.with_suffix(".meta")
                    with open(meta_file, "w", encoding="utf-8") as mf:
                        mf.write(f"Export Date: {datetime.now().isoformat()}\n")
                        mf.write(f"Table: {self.table_name}\n")
                        mf.write(f"Region: {self.region}\n")
                        if self.profile:
                            mf.write(f"Profile: {self.profile}\n")
                        mf.write(f"Total Items: {len(items)}\n")
                        mf.write(f"Mode: {mode}\n")
                else:
                    file_handle.write(f"# Export Date: {datetime.now().isoformat()}\n")
                    file_handle.write(f"# Table: {self.table_name}\n")
                    file_handle.write(f"# Region: {self.region}\n")
                    if self.profile:
                        file_handle.write(f"# Profile: {self.profile}\n")
                    file_handle.write(f"# Total Items: {len(items)}\n")
                    file_handle.write(f"# Mode: {mode}\n")
                    file_handle.write("#\n")

            writer.writeheader()

            # Stream items
            items_written = 0
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
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

                    if mode == "strings":
                        converted = self._serialize_as_json(converted)
                        formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in converted.items()}
                        writer.writerow(formatted)
                        items_written += 1
                    elif mode == "flatten":
                        converted = self._flatten_dict(converted)
                        formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in converted.items()}
                        writer.writerow(formatted)
                        items_written += 1
                    elif mode == "normalize":
                        normalized = self._normalize_lists(converted)
                        for row in normalized:
                            flattened = self._flatten_dict(row)
                            formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in flattened.items()}
                            writer.writerow(formatted)
                            items_written += 1
                    else:
                        formatted = {k: self._format_value_for_csv(v, null_value, bool_format) for k, v in converted.items()}
                        writer.writerow(formatted)
                        items_written += 1

                    progress.update(task, advance=1)

        finally:
            file_handle.close()
            if compress == "zip":
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = items_written
        self.stats["file_size"] = output_file.stat().st_size if compress != "zip" else zip_path.stat().st_size

    def export_to_json(
        self,
        items: List[Dict[str, Any]],
        output_file: Path,
        jsonl: bool = False,
        pretty: bool = True,
        encoding: str = "utf-8",
        compress: Optional[str] = None,
    ) -> None:
        """Export items to JSON or JSONL format."""
        if not items:
            console.print("[yellow]⚠ No items to export[/yellow]")
            return

        self.stats["start_time"] = datetime.now()

        # Convert items
        converted_items = [self._convert_dynamodb_item(item) for item in items]

        # Determine output file with compression
        if compress == "gzip":
            output_file = output_file.with_suffix(output_file.suffix + ".gz")
            file_handle = gzip.open(output_file, "wt", encoding=encoding)
        elif compress == "zip":
            zip_path = output_file.with_suffix(".zip")
            zip_file = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
            file_handle = zip_file.open(output_file.name, "w")
            import io

            file_handle = io.TextIOWrapper(file_handle, encoding=encoding)
        else:
            file_handle = open(output_file, "w", encoding=encoding)

        try:
            if jsonl:
                # JSON Lines format
                for item in converted_items:
                    json.dump(item, file_handle, default=str)
                    file_handle.write("\n")
            else:
                # Standard JSON array
                if pretty:
                    json.dump(converted_items, file_handle, indent=2, default=str)
                else:
                    json.dump(converted_items, file_handle, default=str)

        finally:
            file_handle.close()
            if compress == "zip":
                zip_file.close()

        self.stats["end_time"] = datetime.now()
        self.stats["total_items"] = len(converted_items)
        self.stats["file_size"] = output_file.stat().st_size if compress != "zip" else zip_path.stat().st_size

    def get_table_info(self) -> Dict[str, Any]:
        """Get table metadata."""
        response = self.dynamodb.describe_table(TableName=self.table_name)
        table = response["Table"]

        return {
            "name": table["TableName"],
            "status": table["TableStatus"],
            "item_count": table.get("ItemCount", 0),
            "size_bytes": table.get("TableSizeBytes", 0),
            "creation_date": table["CreationDateTime"].isoformat(),
            "key_schema": table["KeySchema"],
            "attributes": table["AttributeDefinitions"],
            "global_indexes": table.get("GlobalSecondaryIndexes", []),
            "local_indexes": table.get("LocalSecondaryIndexes", []),
        }

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
