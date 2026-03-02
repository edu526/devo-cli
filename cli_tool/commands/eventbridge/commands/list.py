"""List EventBridge rules command."""

from rich.console import Console

from cli_tool.commands.eventbridge.core.rules_manager import RulesManager
from cli_tool.commands.eventbridge.utils.formatters import format_json_output, format_table_output
from cli_tool.core.utils.aws import select_profile

console = Console()


def list_rules(ctx, env, region, status, output):
    """List EventBridge rules with filtering and formatting."""
    from botocore.exceptions import ClientError, NoCredentialsError

    # Get profile from context or prompt user to select
    profile = select_profile(ctx.obj.get("profile"))

    try:
        # Create rules manager
        manager = RulesManager(profile, region)

        console.print(f"\n[blue]Fetching EventBridge rules from {region}...[/blue]\n")

        # Fetch and filter rules
        filtered_rules = manager.get_filtered_rules(env=env, status=status)

        if not filtered_rules:
            filter_msg = f" for environment '{env}'" if env else ""
            console.print(f"[yellow]No rules found{filter_msg}[/yellow]")
            return

        # Output based on format
        if output == "json":
            format_json_output(filtered_rules)
        else:
            format_table_output(filtered_rules, env)

    except NoCredentialsError:
        console.print("[red]Error: AWS credentials not found[/red]")
        console.print("Please configure your AWS credentials or specify a profile")
    except ClientError as e:
        console.print(f"[red]AWS Error: {e.response['Error']['Message']}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
