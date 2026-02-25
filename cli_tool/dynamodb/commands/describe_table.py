"""Describe DynamoDB table command."""

import sys
from typing import Optional

import boto3
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def describe_table_command(profile: Optional[str], table_name: str, region: str) -> None:
    """Show detailed information about a table."""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        dynamodb_client = session.client("dynamodb")

        # Get table description
        response = dynamodb_client.describe_table(TableName=table_name)
        table_info = response["Table"]

        # Basic Information
        console.print(f"\n[bold cyan]Table: {table_name}[/bold cyan]\n")

        # Status and Basic Info
        status = table_info["TableStatus"]
        status_color = "green" if status == "ACTIVE" else "yellow"

        basic_info = Table(show_header=False, box=None, padding=(0, 2))
        basic_info.add_column("Property", style="cyan")
        basic_info.add_column("Value", style="white")

        basic_info.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
        basic_info.add_row("ARN", table_info["TableArn"])
        basic_info.add_row("Table ID", table_info["TableId"])

        creation_date = table_info["CreationDateTime"]
        basic_info.add_row("Created", creation_date.strftime("%Y-%m-%d %H:%M:%S UTC"))

        console.print(Panel(basic_info, title="[bold]Basic Information[/bold]", border_style="blue"))

        # Size and Item Count
        item_count = table_info.get("ItemCount", 0)
        size_bytes = table_info.get("TableSizeBytes", 0)
        size_mb = size_bytes / (1024 * 1024)

        if size_mb < 1:
            size_str = f"{size_bytes / 1024:.2f} KB"
        elif size_mb < 1024:
            size_str = f"{size_mb:.2f} MB"
        else:
            size_str = f"{size_mb / 1024:.2f} GB"

        size_info = Table(show_header=False, box=None, padding=(0, 2))
        size_info.add_column("Property", style="cyan")
        size_info.add_column("Value", style="white")

        size_info.add_row("Item Count", f"{item_count:,}")
        size_info.add_row("Table Size", size_str)

        console.print(Panel(size_info, title="[bold]Storage[/bold]", border_style="blue"))

        # Key Schema
        key_schema_table = Table(show_header=True, box=None)
        key_schema_table.add_column("Attribute Name", style="cyan")
        key_schema_table.add_column("Key Type", style="yellow")
        key_schema_table.add_column("Data Type", style="green")

        # Create attribute map
        attr_map = {attr["AttributeName"]: attr["AttributeType"] for attr in table_info["AttributeDefinitions"]}

        for key in table_info["KeySchema"]:
            attr_name = key["AttributeName"]
            key_type = "Partition Key" if key["KeyType"] == "HASH" else "Sort Key"
            data_type = attr_map.get(attr_name, "Unknown")
            key_schema_table.add_row(attr_name, key_type, data_type)

        console.print(Panel(key_schema_table, title="[bold]Key Schema[/bold]", border_style="blue"))

        # Billing Mode
        billing_mode = table_info.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")

        billing_info = Table(show_header=False, box=None, padding=(0, 2))
        billing_info.add_column("Property", style="cyan")
        billing_info.add_column("Value", style="white")

        billing_info.add_row("Billing Mode", billing_mode)

        if billing_mode == "PROVISIONED":
            provisioned = table_info.get("ProvisionedThroughput", {})
            read_capacity = provisioned.get("ReadCapacityUnits", 0)
            write_capacity = provisioned.get("WriteCapacityUnits", 0)
            billing_info.add_row("Read Capacity Units", str(read_capacity))
            billing_info.add_row("Write Capacity Units", str(write_capacity))

        console.print(Panel(billing_info, title="[bold]Billing[/bold]", border_style="blue"))

        # Global Secondary Indexes
        gsi_list = table_info.get("GlobalSecondaryIndexes", [])
        if gsi_list:
            gsi_table = Table(show_header=True, box=None)
            gsi_table.add_column("Index Name", style="cyan")
            gsi_table.add_column("Status", style="green")
            gsi_table.add_column("Keys", style="yellow")
            gsi_table.add_column("Projection", style="magenta")

            for gsi in gsi_list:
                index_name = gsi["IndexName"]
                index_status = gsi["IndexStatus"]

                # Get keys
                keys = []
                for key in gsi["KeySchema"]:
                    key_type = "PK" if key["KeyType"] == "HASH" else "SK"
                    keys.append(f"{key['AttributeName']} ({key_type})")
                keys_str = ", ".join(keys)

                # Projection
                projection = gsi["Projection"]["ProjectionType"]
                if projection == "INCLUDE":
                    included = gsi["Projection"].get("NonKeyAttributes", [])
                    projection = f"INCLUDE: {', '.join(included[:3])}" + ("..." if len(included) > 3 else "")

                gsi_table.add_row(index_name, index_status, keys_str, projection)

            console.print(Panel(gsi_table, title="[bold]Global Secondary Indexes[/bold]", border_style="blue"))

        # Local Secondary Indexes
        lsi_list = table_info.get("LocalSecondaryIndexes", [])
        if lsi_list:
            lsi_table = Table(show_header=True, box=None)
            lsi_table.add_column("Index Name", style="cyan")
            lsi_table.add_column("Keys", style="yellow")
            lsi_table.add_column("Projection", style="magenta")

            for lsi in lsi_list:
                index_name = lsi["IndexName"]

                # Get keys
                keys = []
                for key in lsi["KeySchema"]:
                    key_type = "PK" if key["KeyType"] == "HASH" else "SK"
                    keys.append(f"{key['AttributeName']} ({key_type})")
                keys_str = ", ".join(keys)

                # Projection
                projection = lsi["Projection"]["ProjectionType"]
                if projection == "INCLUDE":
                    included = lsi["Projection"].get("NonKeyAttributes", [])
                    projection = f"INCLUDE: {', '.join(included[:3])}" + ("..." if len(included) > 3 else "")

                lsi_table.add_row(index_name, keys_str, projection)

            console.print(Panel(lsi_table, title="[bold]Local Secondary Indexes[/bold]", border_style="blue"))
        else:
            lsi_table = Table(show_header=True, box=None)
            lsi_table.add_column("Index Name", style="cyan")
            lsi_table.add_column("Keys", style="yellow")
            lsi_table.add_column("Projection", style="magenta")
            lsi_table.add_row("[dim]No LSI configured[/dim]", "", "")
            console.print(Panel(lsi_table, title="[bold]Local Secondary Indexes[/bold]", border_style="blue"))

        # Stream Specification
        stream_spec = table_info.get("StreamSpecification")
        stream_info = Table(show_header=False, box=None, padding=(0, 2))
        stream_info.add_column("Property", style="cyan")
        stream_info.add_column("Value", style="white")

        if stream_spec and stream_spec.get("StreamEnabled"):
            stream_info.add_row("Stream Enabled", "[green]Yes[/green]")
            stream_info.add_row("Stream View Type", stream_spec.get("StreamViewType", "N/A"))
            if "LatestStreamArn" in table_info:
                stream_info.add_row("Stream ARN", table_info["LatestStreamArn"])
        else:
            stream_info.add_row("Stream Enabled", "[yellow]No[/yellow]")

        console.print(Panel(stream_info, title="[bold]Streams[/bold]", border_style="blue"))

        # Encryption
        sse_description = table_info.get("SSEDescription")
        encryption_info = Table(show_header=False, box=None, padding=(0, 2))
        encryption_info.add_column("Property", style="cyan")
        encryption_info.add_column("Value", style="white")

        if sse_description:
            status = sse_description.get("Status", "N/A")
            status_color = "green" if status == "ENABLED" else "yellow"
            encryption_info.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
            encryption_info.add_row("Type", sse_description.get("SSEType", "N/A"))
            if "KMSMasterKeyArn" in sse_description:
                encryption_info.add_row("KMS Key", sse_description["KMSMasterKeyArn"])
        else:
            encryption_info.add_row("Status", "[yellow]Not Enabled[/yellow]")
            encryption_info.add_row("Type", "AWS Owned Key (Default)")

        console.print(Panel(encryption_info, title="[bold]Encryption[/bold]", border_style="blue"))

        # Point-in-time Recovery
        pitr_info = Table(show_header=False, box=None, padding=(0, 2))
        pitr_info.add_column("Property", style="cyan")
        pitr_info.add_column("Value", style="white")

        try:
            pitr_response = dynamodb_client.describe_continuous_backups(TableName=table_name)
            pitr_status = pitr_response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]["PointInTimeRecoveryStatus"]

            pitr_enabled = pitr_status == "ENABLED"
            status_text = "[green]Enabled[/green]" if pitr_enabled else "[yellow]Disabled[/yellow]"
            pitr_info.add_row("Point-in-time Recovery", status_text)

            if pitr_enabled:
                earliest = pitr_response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"].get("EarliestRestorableDateTime")
                latest = pitr_response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"].get("LatestRestorableDateTime")
                if earliest:
                    pitr_info.add_row("Earliest Restore", earliest.strftime("%Y-%m-%d %H:%M:%S UTC"))
                if latest:
                    pitr_info.add_row("Latest Restore", latest.strftime("%Y-%m-%d %H:%M:%S UTC"))
        except Exception:
            # PITR info not available
            pitr_info.add_row("Point-in-time Recovery", "[yellow]Unknown[/yellow]")

        console.print(Panel(pitr_info, title="[bold]Backup[/bold]", border_style="blue"))

        # Tags
        tags_table = Table(show_header=True, box=None)
        tags_table.add_column("Key", style="cyan")
        tags_table.add_column("Value", style="white")

        try:
            tags_response = dynamodb_client.list_tags_of_resource(ResourceArn=table_info["TableArn"])
            tags = tags_response.get("Tags", [])

            if tags:
                for tag in tags:
                    tags_table.add_row(tag["Key"], tag["Value"])
            else:
                tags_table.add_row("[dim]No tags[/dim]", "")
        except Exception:
            tags_table.add_row("[dim]Unable to fetch tags[/dim]", "")

        console.print(Panel(tags_table, title="[bold]Tags[/bold]", border_style="blue"))

        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error describing table: {e}[/red]")
        sys.exit(1)
