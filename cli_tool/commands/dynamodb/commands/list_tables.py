"""List DynamoDB tables command."""

import sys
from typing import Optional, Tuple

from rich.console import Console
from rich.table import Table

from cli_tool.core.utils.aws import create_aws_client

console = Console()


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    size_mb = size_bytes / (1024 * 1024)
    if size_mb < 1:
        return f"{size_bytes / 1024:.1f} KB"
    if size_mb < 1024:
        return f"{size_mb:.1f} MB"
    return f"{size_mb / 1024:.1f} GB"


def _describe_single_table(dynamodb_client, table_name: str) -> Tuple[str, int, int]:
    """Return (status, item_count, size_bytes) for a table, or raise on error."""
    desc = dynamodb_client.describe_table(TableName=table_name)
    info = desc["Table"]
    return info["TableStatus"], info.get("ItemCount", 0), info.get("TableSizeBytes", 0)


def list_tables_command(profile: Optional[str], region: str) -> None:
    """List all DynamoDB tables in the region."""
    try:
        dynamodb_client = create_aws_client("dynamodb", profile_name=profile, region_name=region)

        tables = []
        last_evaluated_table_name = None
        console.print("[cyan]Fetching tables...[/cyan]")

        while True:
            kwargs = {}
            if last_evaluated_table_name:
                kwargs["ExclusiveStartTableName"] = last_evaluated_table_name
            response = dynamodb_client.list_tables(**kwargs)
            tables.extend(response.get("TableNames", []))
            last_evaluated_table_name = response.get("LastEvaluatedTableName")
            if not last_evaluated_table_name:
                break

        if not tables:
            console.print(f"[yellow]No tables found in region {region}[/yellow]")
            return

        console.print(f"[green]Found {len(tables)} tables[/green]\n")

        table = Table(title=f"DynamoDB Tables in {region}")
        table.add_column("Table Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Items", style="yellow", justify="right")
        table.add_column("Size", style="magenta", justify="right")

        total_items = 0
        total_size = 0
        active_count = 0

        for table_name in sorted(tables):
            try:
                status, item_count, size_bytes = _describe_single_table(dynamodb_client, table_name)
                table.add_row(table_name, status, f"{item_count:,}", _format_size(size_bytes))
                if status == "ACTIVE":
                    active_count += 1
                    total_items += item_count
                    total_size += size_bytes
            except Exception:
                table.add_row(table_name, "ERROR", "-", "-")

        console.print(table)

        console.print("\n[bold]Summary:[/bold]")
        console.print(f"[cyan]Total tables:[/cyan] {len(tables)}")
        console.print(f"[cyan]Active tables:[/cyan] {active_count}")
        console.print(f"[cyan]Total items:[/cyan] {total_items:,}")
        console.print(f"[cyan]Total size:[/cyan] {_format_size(total_size)}")

    except Exception as e:
        console.print(f"[red]✗ Error listing tables: {e}[/red]")
        sys.exit(1)
