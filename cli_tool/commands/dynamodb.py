"""DynamoDB commands."""

from typing import Optional

import click

from cli_tool.dynamodb.commands import (
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
    profile = ctx.obj.get("profile")
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
    profile = ctx.obj.get("profile")
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
    help="Filter expression for scan/query",
)
@click.option(
    "--filter-values",
    help='Expression attribute values as JSON (e.g., \'{":val": "active"}\')',
)
@click.option(
    "--filter-names",
    help='Expression attribute names as JSON (e.g., \'{"#status": "status"}\')',
)
@click.option(
    "--key-condition",
    help="Key condition expression for query (requires partition key)",
)
@click.option(
    "--index",
    help="Global or Local Secondary Index name to use",
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
def export_table(
    ctx,
    table_name: str,
    output: Optional[str],
    format: str,
    region: str,
    limit: Optional[int],
    attributes: Optional[str],
    filter: Optional[str],
    filter_values: Optional[str],
    filter_names: Optional[str],
    key_condition: Optional[str],
    index: Optional[str],
    mode: str,
    null_value: str,
    delimiter: str,
    encoding: str,
    bool_format: str,
    compress: Optional[str],
    metadata: bool,
    pretty: bool,
    parallel_scan: bool,
    segments: int,
    dry_run: bool,
    yes: bool,
    save_template: Optional[str],
    use_template: Optional[str],
):
    """
    Export DynamoDB table to CSV, JSON, or JSONL format.

    Examples:

      # Export entire table to CSV
      devo dynamodb export my-table

      # Export with specific attributes
      devo dynamodb export my-table -a "id,name,email"

      # Export to JSON with compression
      devo dynamodb export my-table -f json --compress gzip

      # Query with key condition
      devo dynamodb export my-table --key-condition "userId = :uid"
    """
    profile = ctx.obj.get("profile")
    export_table_command(
        profile=profile,
        table_name=table_name,
        output=output,
        format=format,
        region=region,
        limit=limit,
        attributes=attributes,
        filter=filter,
        filter_values=filter_values,
        filter_names=filter_names,
        key_condition=key_condition,
        index=index,
        mode=mode,
        null_value=null_value,
        delimiter=delimiter,
        encoding=encoding,
        bool_format=bool_format,
        compress=compress,
        metadata=metadata,
        pretty=pretty,
        parallel_scan=parallel_scan,
        segments=segments,
        dry_run=dry_run,
        yes=yes,
        save_template=save_template,
        use_template=use_template,
    )


@dynamodb.command(name="list-templates")
@click.pass_context
def list_templates_cmd(ctx):
    """List all saved export templates."""
    list_templates_command()
