"""DynamoDB CLI command group."""

import click

from cli_tool.commands.dynamodb.commands import (
    describe_table_command,
    export_table_command,
    list_tables_command,
    list_templates_command,
)


@click.group(name="dynamodb")
@click.pass_context
def dynamodb(ctx):
    """DynamoDB utilities for table management and data export."""
    pass


@dynamodb.command(name="list")
@click.option(
    "--region",
    "-r",
    default="us-east-1",
    help="AWS region (default: us-east-1)",
)
@click.pass_context
def list_tables(ctx, region: str):
    """List all DynamoDB tables in the region."""
    from cli_tool.core.utils.aws import select_profile

    profile = select_profile(ctx.obj.get("profile"))
    list_tables_command(profile, region)


@dynamodb.command(name="describe")
@click.argument("table_name")
@click.option(
    "--region",
    "-r",
    default="us-east-1",
    help="AWS region (default: us-east-1)",
)
@click.pass_context
def describe_table(ctx, table_name: str, region: str):
    """Show detailed information about a table."""
    from cli_tool.core.utils.aws import select_profile

    profile = select_profile(ctx.obj.get("profile"))
    describe_table_command(profile, table_name, region)


@dynamodb.command(name="export")
@click.argument("table_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: <table_name>_<timestamp>.csv)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["csv", "json", "jsonl", "tsv"], case_sensitive=False),
    default="csv",
    help="Output format (default: csv)",
)
@click.option(
    "--region",
    "-r",
    default="us-east-1",
    help="AWS region (default: us-east-1)",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    help="Maximum number of items to export",
)
@click.option(
    "--attributes",
    "-a",
    help="Comma-separated list of attributes to export (ProjectionExpression)",
)
@click.option(
    "--filter",
    help="Filter expression for scan/query (auto-detects indexes for optimization)",
)
@click.option(
    "--filter-values",
    help='[Advanced] Expression attribute values as JSON in DynamoDB typed format (e.g., \'{":val": {"S": "active"}}\')',
)
@click.option(
    "--filter-names",
    help='[Advanced] Expression attribute names as JSON (e.g., \'{"#status": "status"}\')',
)
@click.option(
    "--key-condition",
    help="[Advanced] Manual key condition expression (auto-detected from --filter in most cases)",
)
@click.option(
    "--index",
    help="[Advanced] Force specific GSI/LSI (auto-selected from --filter in most cases)",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["strings", "flatten", "normalize"], case_sensitive=False),
    default="strings",
    help="Export mode: strings (serialize as JSON), flatten (flatten nested), normalize (expand lists to rows)",
)
@click.option(
    "--null-value",
    default="",
    help="Value to use for NULL fields in CSV (default: empty string)",
)
@click.option(
    "--delimiter",
    default=",",
    help="CSV delimiter (default: comma)",
)
@click.option(
    "--encoding",
    default="utf-8",
    help="File encoding (default: utf-8)",
)
@click.option(
    "--bool-format",
    type=click.Choice(["lowercase", "uppercase", "numeric", "letter"], case_sensitive=False),
    default="lowercase",
    help="Boolean format: lowercase (true/false), uppercase (True/False), numeric (1/0), letter (t/f) - default: lowercase",
)
@click.option(
    "--compress",
    type=click.Choice(["gzip", "zip"], case_sensitive=False),
    help="Compress output file",
)
@click.option(
    "--metadata",
    is_flag=True,
    help="Include metadata header in CSV output",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Pretty print JSON output (ignored for JSONL)",
)
@click.option(
    "--parallel-scan",
    is_flag=True,
    help="Use parallel scan for faster export (experimental)",
)
@click.option(
    "--segments",
    type=int,
    default=4,
    help="Number of parallel scan segments (default: 4)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be exported without actually exporting",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.option(
    "--save-template",
    help="Save current configuration as a template",
)
@click.option(
    "--use-template",
    help="Use saved template configuration",
)
@click.pass_context
def export_table(ctx, **kwargs):  # noqa: PLR0913
    """
    Export DynamoDB table to CSV, JSON, or JSONL format.

    Examples:

      # Export entire table to CSV
      devo dynamodb export my-table

      # Export with filter (auto-detects indexes and optimizes query)
      devo dynamodb export my-table --filter "userId = user123"

      # Export with specific attributes
      devo dynamodb export my-table -a "id,name,email" --filter "status = active"

      # Export to JSON with compression
      devo dynamodb export my-table -f json --compress gzip

      # Advanced: Manual key condition (rarely needed, auto-detected from --filter)
      devo dynamodb export my-table --key-condition "userId = :uid" --filter-values '{":uid": {"S": "user123"}}'
    """
    from cli_tool.commands.dynamodb.commands.export_table import ExportParams
    from cli_tool.core.utils.aws import select_profile

    profile = select_profile(ctx.obj.get("profile"))
    params = ExportParams(
        profile=profile,
        table_name=kwargs["table_name"],
        output=kwargs.get("output"),
        fmt=kwargs["format"],
        region=kwargs["region"],
        limit=kwargs.get("limit"),
        attributes=kwargs.get("attributes"),
        filter_expr=kwargs.get("filter"),
        filter_values=kwargs.get("filter_values"),
        filter_names=kwargs.get("filter_names"),
        key_condition=kwargs.get("key_condition"),
        index=kwargs.get("index"),
        mode=kwargs["mode"],
        null_value=kwargs["null_value"],
        delimiter=kwargs["delimiter"],
        encoding=kwargs["encoding"],
        bool_format=kwargs["bool_format"],
        compress=kwargs.get("compress"),
        metadata=kwargs["metadata"],
        pretty=kwargs["pretty"],
        parallel_scan=kwargs["parallel_scan"],
        segments=kwargs["segments"],
        dry_run=kwargs["dry_run"],
        yes=kwargs["yes"],
        save_template=kwargs.get("save_template"),
    )
    export_table_command(params, kwargs.get("use_template"))


@dynamodb.command(name="list-templates")
@click.pass_context
def list_templates_cmd(ctx):
    """List all saved export templates."""
    list_templates_command()
