"""Utility functions for DynamoDB operations."""

from botocore.exceptions import ClientError
from rich.console import Console

console = Console()


def validate_table_exists(dynamodb_client, table_name: str) -> bool:
    """Validate that the table exists and is accessible."""
    try:
        response = dynamodb_client.describe_table(TableName=table_name)
        status = response["Table"]["TableStatus"]
        if status != "ACTIVE":
            console.print(f"[yellow]⚠ Table '{table_name}' is in {status} state[/yellow]")
            return False
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            console.print(f"[red]✗ Table '{table_name}' not found[/red]")
            return False
        console.print(f"[red]✗ Error accessing table: {e}[/red]")
        return False


def estimate_export_size(exporter) -> None:
    """Estimate export size and time."""
    try:
        info = exporter.get_table_info()
        item_count = info["item_count"]
        size_bytes = info["size_bytes"]
        size_mb = size_bytes / (1024 * 1024)

        console.print("\n[bold]Table Information:[/bold]")
        console.print(f"[cyan]Status:[/cyan] {info['status']}")
        console.print(f"[cyan]Estimated items:[/cyan] {item_count:,}")
        console.print(f"[cyan]Estimated size:[/cyan] {size_mb:.2f} MB")

        # Rough time estimate (assuming ~1000 items/sec)
        if item_count > 0:
            estimated_seconds = item_count / 1000
            console.print(f"[cyan]Estimated time:[/cyan] ~{estimated_seconds:.0f}s")

        if item_count > 100000:
            console.print("\n[yellow]⚠ Large table detected. Consider using --parallel-scan for faster export[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Error getting table info: {e}[/red]")
