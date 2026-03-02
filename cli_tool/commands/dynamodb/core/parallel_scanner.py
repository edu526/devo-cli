"""Parallel scan implementation for large DynamoDB tables."""

import concurrent.futures
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

console = Console()


class ParallelScanner:
    """Perform parallel scans on DynamoDB tables."""

    def __init__(self, dynamodb_client, table_name: str, total_segments: int = 4):
        self.dynamodb = dynamodb_client
        self.table_name = table_name
        self.total_segments = total_segments

    def _scan_segment(
        self,
        segment: int,
        filter_expression: Optional[str] = None,
        projection_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Scan a single segment."""
        items = []
        scan_kwargs = {
            "TableName": self.table_name,
            "Segment": segment,
            "TotalSegments": self.total_segments,
        }

        if filter_expression:
            scan_kwargs["FilterExpression"] = filter_expression
        if projection_expression:
            scan_kwargs["ProjectionExpression"] = projection_expression
        if index_name:
            scan_kwargs["IndexName"] = index_name
        if expression_attribute_values:
            scan_kwargs["ExpressionAttributeValues"] = expression_attribute_values
        if expression_attribute_names:
            scan_kwargs["ExpressionAttributeNames"] = expression_attribute_names

        while True:
            response = self.dynamodb.scan(**scan_kwargs)
            batch_items = response.get("Items", [])
            items.extend(batch_items)

            if limit and len(items) >= limit:
                items = items[:limit]
                break

            if "LastEvaluatedKey" not in response:
                break

            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        return items

    def parallel_scan(
        self,
        filter_expression: Optional[str] = None,
        projection_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        max_workers: Optional[int] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform parallel scan across multiple segments."""
        all_items = []

        if max_workers is None:
            max_workers = min(self.total_segments, 10)

        # Distribute limit across segments
        limit_per_segment = None
        if limit:
            # Add buffer for filtering and distribute
            limit_per_segment = int(limit * 1.5 / self.total_segments) + 50

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Parallel scanning {self.table_name} ({self.total_segments} segments)...",
                total=self.total_segments,
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all segment scans
                futures = {
                    executor.submit(
                        self._scan_segment,
                        segment,
                        filter_expression,
                        projection_expression,
                        index_name,
                        limit_per_segment,
                        expression_attribute_values,
                        expression_attribute_names,
                    ): segment
                    for segment in range(self.total_segments)
                }

                # Collect results as they complete
                failed_segments = []
                for future in concurrent.futures.as_completed(futures):
                    segment = futures[future]
                    try:
                        items = future.result()
                        all_items.extend(items)
                        progress.update(task, advance=1)

                        # Stop early if we've reached the limit
                        if limit and len(all_items) >= limit:
                            console.print(f"[cyan]Reached limit of {limit} items, cancelling remaining segments[/cyan]")
                            # Cancel remaining futures
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break

                    except Exception as e:
                        failed_segments.append(segment)
                        console.print(f"[red]✗ Error scanning segment {segment}: {e}[/red]")
                        # Don't continue if too many segments fail
                        if len(failed_segments) > self.total_segments / 2:
                            console.print(f"[red]✗ Too many segment failures ({len(failed_segments)}), aborting[/red]")
                            raise RuntimeError(f"Parallel scan failed: {len(failed_segments)} segments failed")

            if failed_segments:
                console.print(f"[yellow]⚠ Warning: {len(failed_segments)} segment(s) failed, data may be incomplete[/yellow]")

            progress.update(
                task,
                description=f"[green]✓ Scanned {len(all_items)} items from {self.total_segments} segments",
            )

        # Apply global limit if specified
        if limit and len(all_items) > limit:
            all_items = all_items[:limit]

        return all_items
