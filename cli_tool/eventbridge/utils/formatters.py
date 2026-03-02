"""Output formatting utilities for EventBridge rules."""

import json
from typing import Dict, List

from rich.console import Console
from rich.table import Table

console = Console()

# Common environment names for extraction
COMMON_ENVS = [
    "dev",
    "develop",
    "development",
    "staging",
    "stage",
    "stg",
    "prod",
    "production",
    "test",
    "qa",
    "uat",
    "demo",
]


def format_json_output(filtered_rules: List[Dict]):
    """Format rules as JSON output.

    Args:
      filtered_rules: List of filtered rule dictionaries
    """
    output_data = []

    for item in filtered_rules:
        rule = item["rule"]
        targets = item["targets"]
        tags = item["tags"]

        output_data.append(
            {
                "name": rule["Name"],
                "arn": rule["Arn"],
                "state": rule["State"],
                "schedule": rule.get("ScheduleExpression", "N/A"),
                "description": rule.get("Description", ""),
                "targets": [
                    {
                        "id": t.get("Id"),
                        "arn": t.get("Arn"),
                        "input": t.get("Input", t.get("InputPath", "")),
                    }
                    for t in targets
                ],
                "tags": tags,
            }
        )

    console.print(json.dumps(output_data, indent=2))


def format_table_output(filtered_rules: List[Dict], env: str = None):
    """Format rules as table output.

    Args:
      filtered_rules: List of filtered rule dictionaries
      env: Environment filter (for title)
    """
    table = Table(
        title=f"EventBridge Scheduled Rules{' - ' + env.upper() if env else ''}",
        show_lines=True,
    )
    table.add_column("Rule Name", style="cyan", no_wrap=False, width=50)
    table.add_column("Status", style="magenta", width=12)
    table.add_column("Schedule", style="green", no_wrap=False, width=30)
    table.add_column("Targets", style="yellow", no_wrap=False, width=40)
    table.add_column("Env", style="blue", width=10)

    for item in filtered_rules:
        rule = item["rule"]
        targets = item["targets"]
        tags = item["tags"]

        rule_name = rule["Name"]
        state = rule["State"]
        schedule = rule.get("ScheduleExpression", "N/A")

        # Format status with emoji
        status_display = "✅ ENABLED" if state == "ENABLED" else "❌ DISABLED"

        # Format targets
        targets_display = _format_targets(targets)

        # Get environment
        env_tag = _extract_environment(targets, tags)

        table.add_row(rule_name, status_display, schedule, targets_display, env_tag or "N/A")

    console.print(table)

    # Print summary
    _print_summary(filtered_rules)


def _format_targets(targets: List[Dict]) -> str:
    """Format target list for display.

    Args:
      targets: List of target dictionaries

    Returns:
      Formatted target string
    """
    target_list = []

    for target in targets:
        target_arn = target.get("Arn", "")

        # Extract Lambda function name from ARN
        if ":function:" in target_arn:
            func_name = target_arn.split(":function:")[-1].split(":")[0]
            target_list.append(func_name)
        elif target_arn:
            # For other services, show the last part of ARN
            target_list.append(target_arn.split(":")[-1][:30])

    if not target_list:
        return "No targets"

    # Show max 2 targets
    result = "\n".join(target_list[:2])
    if len(target_list) > 2:
        result += f"\n+{len(target_list) - 2} more"

    return result


def _extract_environment(targets: List[Dict], tags: Dict[str, str]) -> str:
    """Extract environment from tags or target names.

    Args:
      targets: List of target dictionaries
      tags: Rule tags

    Returns:
      Environment name or empty string
    """
    # Check tags first
    env_tag = tags.get("Env", tags.get("Environment", ""))
    if env_tag:
        return env_tag

    # Try to extract from target names
    for target in targets:
        target_arn = target.get("Arn", "")

        # Extract from Lambda function name pattern
        if ":function:" in target_arn:
            func_name = target_arn.split(":function:")[-1].split(":")[0]
            parts = func_name.split("-")

            for part in parts:
                if part.lower() in COMMON_ENVS:
                    return part

    return ""


def _print_summary(filtered_rules: List[Dict]):
    """Print summary statistics.

    Args:
      filtered_rules: List of filtered rule dictionaries
    """
    total = len(filtered_rules)
    enabled = sum(1 for item in filtered_rules if item["rule"]["State"] == "ENABLED")
    disabled = total - enabled

    console.print(f"\n[green]Total rules: {total}[/green]")
    console.print(f"[green]Enabled: {enabled}[/green] | [red]Disabled: {disabled}[/red]\n")
