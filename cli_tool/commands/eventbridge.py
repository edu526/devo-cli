import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
@click.option(
    "--env",
    "-e",
    help="Filter by environment (e.g., dev, staging, prod)",
    required=False,
)
@click.option(
    "--region", "-r", default="us-east-1", help="AWS region (default: us-east-1)"
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(["ENABLED", "DISABLED", "ALL"], case_sensitive=False),
    default="ALL",
    help="Filter by rule status",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--profile",
    envvar="AWS_PROFILE",
    default=None,
    help="AWS profile to use for authentication",
)
@click.pass_context
def eventbridge(ctx, env, region, status, output, profile):
    """Check EventBridge scheduled rules status by environment."""
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    # Use command-level profile if provided, otherwise use context profile
    if not profile:
        profile = ctx.obj.get("profile")

    try:
        # Create EventBridge client
        session = boto3.Session(profile_name=profile, region_name=region)
        events_client = session.client("events")

        console.print(f"\n[blue]Fetching EventBridge rules from {region}...[/blue]\n")

        # List all rules
        paginator = events_client.get_paginator("list_rules")
        all_rules = []

        for page in paginator.paginate():
            all_rules.extend(page["Rules"])

        if not all_rules:
            console.print("[yellow]No EventBridge rules found[/yellow]")
            return

        # Filter rules
        filtered_rules = []
        for rule in all_rules:
            # Filter by status
            if status != "ALL" and rule["State"] != status:
                continue

            # Get rule details including targets and tags
            rule_name = rule["Name"]

            # Get targets
            try:
                targets_response = events_client.list_targets_by_rule(Rule=rule_name)
                targets = targets_response.get("Targets", [])
            except ClientError:
                targets = []

            # Get tags
            try:
                rule_arn = rule["Arn"]
                tags_response = events_client.list_tags_for_resource(
                    ResourceARN=rule_arn
                )
                tags = {
                    tag["Key"]: tag["Value"] for tag in tags_response.get("Tags", [])
                }
            except ClientError:
                tags = {}

            # Filter by environment if specified
            if env:
                env_match = False

                # Check if Env tag matches
                env_from_tag = tags.get("Env", tags.get("Environment", "")).lower()
                if env_from_tag == env.lower():
                    env_match = True

                # If no tag match, extract environment from target names
                if not env_match:
                    for target in targets:
                        target_arn = target.get("Arn", "")

                        # Check simple patterns first
                        if (
                            f"service-{env}-" in target_arn.lower()
                            or f"-{env}-lambda" in target_arn.lower()
                        ):
                            env_match = True
                            break

                        # Extract from Lambda function name pattern: *-env-*
                        if ":function:" in target_arn:
                            func_name = target_arn.split(":function:")[-1].split(":")[0]
                            # Look for pattern like service-dev-lambda or processor-prod-handler
                            parts = func_name.split("-")
                            for part in parts:
                                # Check if this part matches the environment
                                if part.lower() == env.lower():
                                    env_match = True
                                    break
                            if env_match:
                                break

                if not env_match:
                    continue

            # Add to filtered list
            filtered_rules.append({"rule": rule, "targets": targets, "tags": tags})

        if not filtered_rules:
            filter_msg = f" for environment '{env}'" if env else ""
            console.print(f"[yellow]No rules found{filter_msg}[/yellow]")
            return

        # Output as JSON if requested
        if output == "json":
            import json

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
            return

        # Display results in a table
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
            target_list = []
            for target in targets:
                target_arn = target.get("Arn", "")
                # Extract Lambda function name from ARN
                if ":function:" in target_arn:
                    func_name = target_arn.split(":function:")[-1].split(":")[
                        0
                    ]  # Remove version/alias
                    target_list.append(func_name)
                elif target_arn:
                    # For other services, show the last part of ARN
                    target_list.append(target_arn.split(":")[-1][:30])

            targets_display = "\n".join(target_list[:2])  # Show max 2 targets
            if len(target_list) > 2:
                targets_display += f"\n+{len(target_list) - 2} more"
            elif not target_list:
                targets_display = "No targets"

            # Get environment from tags
            env_tag = tags.get("Env", tags.get("Environment", ""))

            # If no env tag, try to extract from target names
            if not env_tag and targets:
                for target in targets:
                    target_arn = target.get("Arn", "")
                    # Extract from Lambda function name pattern: *-env-*
                    if ":function:" in target_arn:
                        func_name = target_arn.split(":function:")[-1].split(":")[0]
                        # Look for pattern like service-dev-lambda or processor-prod-handler
                        parts = func_name.split("-")
                        for i, part in enumerate(parts):
                            # Check if this part looks like an environment (common env names)
                            if part.lower() in [
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
                            ]:
                                env_tag = part
                                break
                        if env_tag:
                            break

            table.add_row(
                rule_name, status_display, schedule, targets_display, env_tag or "N/A"
            )

        console.print(table)
        console.print(f"\n[green]Total rules: {len(filtered_rules)}[/green]")

        # Summary by status
        enabled_count = sum(
            1 for item in filtered_rules if item["rule"]["State"] == "ENABLED"
        )
        disabled_count = len(filtered_rules) - enabled_count
        console.print(
            f"[green]Enabled: {enabled_count}[/green] | [red]Disabled: {disabled_count}[/red]\n"
        )

    except NoCredentialsError:
        console.print("[red]Error: AWS credentials not found[/red]")
        console.print("Please configure your AWS credentials or specify a profile")
    except ClientError as e:
        console.print(f"[red]AWS Error: {e.response['Error']['Message']}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
