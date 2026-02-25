"""List DynamoDB tables command."""

import sys
from typing import Optional

import boto3
from rich.console import Console
from rich.table import Table

console = Console()


def list_tables_command(profile: Optional[str], region: str) -> None:
    """List all DynamoDB tables in the region."""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        dynamodb_client = session.client("dynamodb")

        # Get all tables with pagination
        tables = []
        last_evaluated_table_name = None

        console.print("[cyan]Fetching tables...[/cyan]")

        while True:
            if last_evaluated_table_name:
                response = dynamodb_client.list_tables(ExclusiveStartTableName=last_evaluated_table_name)
            else:
                response = dynamodb_client.list_tables()

            tables.extend(response.get("TableNames", []))

            # Check if there are more tables to fetch
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

        # Get status and details for each table
        total_items = 0
        total_size = 0
        active_count = 0

        for table_name in sorted(tables):
            try:
                desc = dynamodb_client.describe_table(TableName=table_name)
                table_info = desc["Table"]
                status = table_info["TableStatus"]
                item_count = table_info.get("ItemCount", 0)
                size_bytes = table_info.get("TableSizeBytes", 0)
                size_mb = size_bytes / (1024 * 1024)

                # Format size
                if size_mb < 1:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                elif size_mb < 1024:
                    size_str = f"{size_mb:.1f} MB"
                else:
                    size_str = f"{size_mb / 1024:.1f} GB"

                table.add_row(
                    table_name,
                    status,
                    f"{item_count:,}",
                    size_str,
                )

                if status == "ACTIVE":
                    active_count += 1
                    total_items += item_count
                    total_size += size_bytes

            except Exception:
                # If we can't describe a table, still show it
                table.add_row(table_name, "ERROR", "-", "-")

        console.print(table)

        # Print summary
        total_size_mb = total_size / (1024 * 1024)
        if total_size_mb < 1024:
            size_display = f"{total_size_mb:.2f} MB"
        else:
            size_display = f"{total_size_mb / 1024:.2f} GB"

        console.print("\n[bold]Summary:[/bold]")
        console.print(f"[cyan]Total tables:[/cyan] {len(tables)}")
        console.print(f"[cyan]Active tables:[/cyan] {active_count}")
        console.print(f"[cyan]Total items:[/cyan] {total_items:,}")
        console.print(f"[cyan]Total size:[/cyan] {size_display}")

    except Exception as e:
        console.print(f"[red]✗ Error listing tables: {e}[/red]")
        sys.exit(1)
