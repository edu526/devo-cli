"""Describe DynamoDB table command."""

import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli_tool.core.utils.aws import create_aws_client

console = Console()

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S UTC"
_INDEX_NAME_COL = "Index Name"


def _kv_table() -> Table:
    """Create a two-column key/value table with no header."""
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Property", style="cyan")
    t.add_column("Value", style="white")
    return t


def _panel(content, title: str) -> Panel:
    return Panel(content, title=f"[bold]{title}[/bold]", border_style="blue")


def _print_basic_info(table_info: dict) -> None:
    status = table_info["TableStatus"]
    status_color = "green" if status == "ACTIVE" else "yellow"
    t = _kv_table()
    t.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
    t.add_row("ARN", table_info["TableArn"])
    t.add_row("Table ID", table_info["TableId"])
    t.add_row("Created", table_info["CreationDateTime"].strftime(_DATETIME_FMT))
    console.print(_panel(t, "Basic Information"))


def _print_storage(table_info: dict) -> None:
    item_count = table_info.get("ItemCount", 0)
    size_bytes = table_info.get("TableSizeBytes", 0)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb < 1:
        size_str = f"{size_bytes / 1024:.2f} KB"
    elif size_mb < 1024:
        size_str = f"{size_mb:.2f} MB"
    else:
        size_str = f"{size_mb / 1024:.2f} GB"
    t = _kv_table()
    t.add_row("Item Count", f"{item_count:,}")
    t.add_row("Table Size", size_str)
    console.print(_panel(t, "Storage"))


def _print_key_schema(table_info: dict) -> None:
    t = Table(show_header=True, box=None)
    t.add_column("Attribute Name", style="cyan")
    t.add_column("Key Type", style="yellow")
    t.add_column("Data Type", style="green")
    attr_map = {a["AttributeName"]: a["AttributeType"] for a in table_info["AttributeDefinitions"]}
    for key in table_info["KeySchema"]:
        key_type = "Partition Key" if key["KeyType"] == "HASH" else "Sort Key"
        t.add_row(key["AttributeName"], key_type, attr_map.get(key["AttributeName"], "Unknown"))
    console.print(_panel(t, "Key Schema"))


def _print_billing(table_info: dict) -> None:
    billing_mode = table_info.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
    t = _kv_table()
    t.add_row("Billing Mode", billing_mode)
    if billing_mode == "PROVISIONED":
        provisioned = table_info.get("ProvisionedThroughput", {})
        t.add_row("Read Capacity Units", str(provisioned.get("ReadCapacityUnits", 0)))
        t.add_row("Write Capacity Units", str(provisioned.get("WriteCapacityUnits", 0)))
    console.print(_panel(t, "Billing"))


def _format_projection(projection_data: dict) -> str:
    projection = projection_data["ProjectionType"]
    if projection == "INCLUDE":
        included = projection_data.get("NonKeyAttributes", [])
        projection = f"INCLUDE: {', '.join(included[:3])}" + ("..." if len(included) > 3 else "")
    return projection


def _format_index_keys(key_schema: list) -> str:
    parts = []
    for key in key_schema:
        key_type = "PK" if key["KeyType"] == "HASH" else "SK"
        parts.append(f"{key['AttributeName']} ({key_type})")
    return ", ".join(parts)


def _print_gsi(table_info: dict) -> None:
    gsi_list = table_info.get("GlobalSecondaryIndexes", [])
    if not gsi_list:
        return
    t = Table(show_header=True, box=None)
    t.add_column(_INDEX_NAME_COL, style="cyan")
    t.add_column("Status", style="green")
    t.add_column("Keys", style="yellow")
    t.add_column("Projection", style="magenta")
    for gsi in gsi_list:
        t.add_row(gsi["IndexName"], gsi["IndexStatus"], _format_index_keys(gsi["KeySchema"]), _format_projection(gsi["Projection"]))
    console.print(_panel(t, "Global Secondary Indexes"))


def _print_lsi(table_info: dict) -> None:
    lsi_list = table_info.get("LocalSecondaryIndexes", [])
    t = Table(show_header=True, box=None)
    t.add_column(_INDEX_NAME_COL, style="cyan")
    t.add_column("Keys", style="yellow")
    t.add_column("Projection", style="magenta")
    if lsi_list:
        for lsi in lsi_list:
            t.add_row(lsi["IndexName"], _format_index_keys(lsi["KeySchema"]), _format_projection(lsi["Projection"]))
    else:
        t.add_row("[dim]No LSI configured[/dim]", "", "")
    console.print(_panel(t, "Local Secondary Indexes"))


def _print_streams(table_info: dict) -> None:
    stream_spec = table_info.get("StreamSpecification")
    t = _kv_table()
    if stream_spec and stream_spec.get("StreamEnabled"):
        t.add_row("Stream Enabled", "[green]Yes[/green]")
        t.add_row("Stream View Type", stream_spec.get("StreamViewType", "N/A"))
        if "LatestStreamArn" in table_info:
            t.add_row("Stream ARN", table_info["LatestStreamArn"])
    else:
        t.add_row("Stream Enabled", "[yellow]No[/yellow]")
    console.print(_panel(t, "Streams"))


def _print_encryption(table_info: dict) -> None:
    sse = table_info.get("SSEDescription")
    t = _kv_table()
    if sse:
        status = sse.get("Status", "N/A")
        status_color = "green" if status == "ENABLED" else "yellow"
        t.add_row("Status", f"[{status_color}]{status}[/{status_color}]")
        t.add_row("Type", sse.get("SSEType", "N/A"))
        if "KMSMasterKeyArn" in sse:
            t.add_row("KMS Key", sse["KMSMasterKeyArn"])
    else:
        t.add_row("Status", "[yellow]Not Enabled[/yellow]")
        t.add_row("Type", "AWS Owned Key (Default)")
    console.print(_panel(t, "Encryption"))


def _print_pitr(dynamodb_client, table_name: str) -> None:
    t = _kv_table()
    try:
        pitr_response = dynamodb_client.describe_continuous_backups(TableName=table_name)
        pitr_desc = pitr_response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]
        pitr_enabled = pitr_desc["PointInTimeRecoveryStatus"] == "ENABLED"
        t.add_row("Point-in-time Recovery", "[green]Enabled[/green]" if pitr_enabled else "[yellow]Disabled[/yellow]")
        if pitr_enabled:
            earliest = pitr_desc.get("EarliestRestorableDateTime")
            latest = pitr_desc.get("LatestRestorableDateTime")
            if earliest:
                t.add_row("Earliest Restore", earliest.strftime(_DATETIME_FMT))
            if latest:
                t.add_row("Latest Restore", latest.strftime(_DATETIME_FMT))
    except Exception:
        t.add_row("Point-in-time Recovery", "[yellow]Unknown[/yellow]")
    console.print(_panel(t, "Backup"))


def _print_tags(dynamodb_client, table_arn: str) -> None:
    t = Table(show_header=True, box=None)
    t.add_column("Key", style="cyan")
    t.add_column("Value", style="white")
    try:
        tags = dynamodb_client.list_tags_of_resource(ResourceArn=table_arn).get("Tags", [])
        if tags:
            for tag in tags:
                t.add_row(tag["Key"], tag["Value"])
        else:
            t.add_row("[dim]No tags[/dim]", "")
    except Exception:
        t.add_row("[dim]Unable to fetch tags[/dim]", "")
    console.print(_panel(t, "Tags"))


def describe_table_command(profile: Optional[str], table_name: str, region: str) -> None:
    """Show detailed information about a table."""
    try:
        dynamodb_client = create_aws_client("dynamodb", profile_name=profile, region_name=region)
        table_info = dynamodb_client.describe_table(TableName=table_name)["Table"]

        console.print(f"\n[bold cyan]Table: {table_name}[/bold cyan]\n")
        _print_basic_info(table_info)
        _print_storage(table_info)
        _print_key_schema(table_info)
        _print_billing(table_info)
        _print_gsi(table_info)
        _print_lsi(table_info)
        _print_streams(table_info)
        _print_encryption(table_info)
        _print_pitr(dynamodb_client, table_name)
        _print_tags(dynamodb_client, table_info["TableArn"])
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error describing table: {e}[/red]")
        sys.exit(1)
