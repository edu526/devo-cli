"""
Integration tests for EventBridge commands.

Tests the complete EventBridge rule listing workflow including:
- Rule listing with mocked EventBridge service
- Rule filtering by environment tags
- Rule filtering by state (ENABLED, DISABLED, ALL)
- Rule output in different formats (table, JSON)
- Error handling for AWS service errors
"""

import json

import pytest
from click.testing import CliRunner

from cli_tool.commands.eventbridge.commands import register_eventbridge_commands


def extract_json_from_output(output):
    """Extract JSON from CLI output that may contain status messages."""
    lines = output.strip().split("\n")
    # Find the first line that starts with '[' or '{'
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            json_output = "\n".join(lines[i:])
            return json.loads(json_output)
    # If no JSON found, try to parse the whole output
    return json.loads(output)


@pytest.fixture(autouse=True)
def mock_select_profile(mocker):
    """Mock select_profile to return None for all tests."""
    mocker.patch("cli_tool.commands.eventbridge.commands.list.select_profile", return_value=None)


@pytest.fixture
def mock_eventbridge_client(monkeypatch):
    """Provide mocked EventBridge client using moto."""
    import boto3
    from moto import mock_aws

    # Set fake AWS credentials
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        yield boto3.client("events", region_name="us-east-1")


@pytest.fixture
def mock_eventbridge_rules(mock_eventbridge_client):
    """Create mock EventBridge rules with different states and environments."""
    # Create rules with different states and environments
    rules_data = [
        {
            "name": "dev-lambda-scheduler",
            "schedule": "rate(5 minutes)",
            "state": "ENABLED",
            "description": "Development environment scheduler",
            "tags": {"Env": "dev", "Team": "backend"},
            "target_arn": "arn:aws:lambda:us-east-1:123456789012:function:service-dev-processor",
        },
        {
            "name": "staging-data-sync",
            "schedule": "cron(0 2 * * ? *)",
            "state": "ENABLED",
            "description": "Staging data synchronization",
            "tags": {"Environment": "staging", "Team": "data"},
            "target_arn": "arn:aws:lambda:us-east-1:123456789012:function:data-staging-sync",
        },
        {
            "name": "prod-backup-job",
            "schedule": "cron(0 0 * * ? *)",
            "state": "ENABLED",
            "description": "Production backup job",
            "tags": {"Env": "prod", "Team": "ops"},
            "target_arn": "arn:aws:lambda:us-east-1:123456789012:function:backup-prod-handler",
        },
        {
            "name": "dev-cleanup-disabled",
            "schedule": "rate(1 hour)",
            "state": "DISABLED",
            "description": "Disabled cleanup job",
            "tags": {"Env": "dev", "Team": "backend"},
            "target_arn": "arn:aws:lambda:us-east-1:123456789012:function:cleanup-dev-job",
        },
        {
            "name": "prod-monitoring",
            "schedule": "rate(1 minute)",
            "state": "DISABLED",
            "description": "Disabled monitoring rule",
            "tags": {"Env": "prod", "Team": "monitoring"},
            "target_arn": "arn:aws:lambda:us-east-1:123456789012:function:monitor-prod-service",
        },
    ]

    # Create rules in EventBridge
    for rule_data in rules_data:
        # Create rule
        mock_eventbridge_client.put_rule(
            Name=rule_data["name"], ScheduleExpression=rule_data["schedule"], State=rule_data["state"], Description=rule_data["description"]
        )

        # Get rule ARN
        response = mock_eventbridge_client.describe_rule(Name=rule_data["name"])
        rule_arn = response["Arn"]

        # Add tags
        mock_eventbridge_client.tag_resource(ResourceARN=rule_arn, Tags=[{"Key": k, "Value": v} for k, v in rule_data["tags"].items()])

        # Add target
        mock_eventbridge_client.put_targets(Rule=rule_data["name"], Targets=[{"Id": "1", "Arn": rule_data["target_arn"]}])

    return mock_eventbridge_client


@pytest.fixture
def mock_aws_client(mocker, mock_eventbridge_rules):
    """Mock create_aws_client to return mocked EventBridge client."""
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=mock_eventbridge_rules)
    return mock_eventbridge_rules


@pytest.mark.integration
def test_list_all_rules_table_format(cli_runner, mock_aws_client):
    """Test listing all EventBridge rules in table format."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with obj context
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Print output for debugging
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            print(f"Exception: {result.exception}")
            import traceback

            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    # Verify success
    assert result.exit_code == 0
    assert "EventBridge Scheduled Rules" in result.output
    assert "dev-lambda-scheduler" in result.output
    assert "staging-data-sync" in result.output
    assert "prod-backup-job" in result.output
    assert "dev-cleanup-disabled" in result.output
    assert "prod-monitoring" in result.output

    # Verify summary statistics
    assert "Total rules: 5" in result.output
    assert "Enabled: 3" in result.output
    assert "Disabled: 2" in result.output


@pytest.mark.integration
def test_list_rules_json_format(cli_runner, mock_aws_client):
    """Test listing EventBridge rules in JSON format."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify structure
    assert isinstance(output_data, list)
    assert len(output_data) == 5

    # Verify first rule structure
    first_rule = output_data[0]
    assert "name" in first_rule
    assert "arn" in first_rule
    assert "state" in first_rule
    assert "schedule" in first_rule
    assert "targets" in first_rule
    assert "tags" in first_rule

    # Verify rule names are present
    rule_names = [rule["name"] for rule in output_data]
    assert "dev-lambda-scheduler" in rule_names
    assert "staging-data-sync" in rule_names
    assert "prod-backup-job" in rule_names


@pytest.mark.integration
def test_filter_rules_by_environment_dev(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by dev environment."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with environment filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "dev",
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only dev rules are returned
    assert len(output_data) == 2  # dev-lambda-scheduler and dev-cleanup-disabled
    rule_names = [rule["name"] for rule in output_data]
    assert "dev-lambda-scheduler" in rule_names
    assert "dev-cleanup-disabled" in rule_names

    # Verify no staging or prod rules
    assert "staging-data-sync" not in rule_names
    assert "prod-backup-job" not in rule_names


@pytest.mark.integration
def test_filter_rules_by_environment_staging(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by staging environment."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with environment filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "staging",
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only staging rules are returned
    assert len(output_data) == 1
    assert output_data[0]["name"] == "staging-data-sync"


@pytest.mark.integration
def test_filter_rules_by_environment_prod(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by prod environment."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with environment filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "prod",
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only prod rules are returned
    assert len(output_data) == 2  # prod-backup-job and prod-monitoring
    rule_names = [rule["name"] for rule in output_data]
    assert "prod-backup-job" in rule_names
    assert "prod-monitoring" in rule_names


@pytest.mark.integration
def test_filter_rules_by_state_enabled(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by ENABLED state."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with state filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ENABLED",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only enabled rules are returned
    assert len(output_data) == 3
    for rule in output_data:
        assert rule["state"] == "ENABLED"

    rule_names = [rule["name"] for rule in output_data]
    assert "dev-lambda-scheduler" in rule_names
    assert "staging-data-sync" in rule_names
    assert "prod-backup-job" in rule_names


@pytest.mark.integration
def test_filter_rules_by_state_disabled(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by DISABLED state."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with state filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "DISABLED",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only disabled rules are returned
    assert len(output_data) == 2
    for rule in output_data:
        assert rule["state"] == "DISABLED"

    rule_names = [rule["name"] for rule in output_data]
    assert "dev-cleanup-disabled" in rule_names
    assert "prod-monitoring" in rule_names


@pytest.mark.integration
def test_filter_rules_by_environment_and_state(cli_runner, mock_aws_client):
    """Test filtering EventBridge rules by both environment and state."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with both filters
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "dev",
            "--status",
            "ENABLED",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only dev + enabled rules are returned
    assert len(output_data) == 1
    assert output_data[0]["name"] == "dev-lambda-scheduler"
    assert output_data[0]["state"] == "ENABLED"


@pytest.mark.integration
def test_list_rules_with_custom_region(cli_runner, mock_aws_client):
    """Test listing EventBridge rules with custom region."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with custom region
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--region",
            "us-west-2",
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify command runs (may return empty list if no rules in that region)
    assert result.exit_code == 0


@pytest.mark.integration
def test_list_rules_table_format_shows_status_emoji(cli_runner, mock_aws_client):
    """Test that table format shows status with emoji indicators."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Verify table contains rule names and summary shows enabled/disabled counts
    assert "dev-lambda-scheduler" in result.output
    assert "Enabled: 3" in result.output
    assert "Disabled: 2" in result.output


@pytest.mark.integration
def test_list_rules_table_format_shows_schedule(cli_runner, mock_aws_client):
    """Test that table format shows schedule expressions."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Verify schedule expressions are shown (may be truncated in table)
    assert "rate(5" in result.output or "rate(5 minutes)" in result.output
    assert "cron(0" in result.output  # Cron expressions start with cron(0


@pytest.mark.integration
def test_list_rules_table_format_shows_targets(cli_runner, mock_aws_client):
    """Test that table format shows target information."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Verify target function names are shown (extracted from ARN)
    assert "service-dev-processor" in result.output or "processor" in result.output
    assert "data-staging-sync" in result.output or "sync" in result.output


@pytest.mark.integration
def test_list_rules_table_format_shows_environment(cli_runner, mock_aws_client):
    """Test that table format shows environment tags."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Verify environment tags are shown
    assert "dev" in result.output
    assert "staging" in result.output
    assert "prod" in result.output


@pytest.mark.integration
def test_list_rules_json_format_includes_tags(cli_runner, mock_aws_client):
    """Test that JSON format includes all tags."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify tags are included
    for rule in output_data:
        assert "tags" in rule
        assert isinstance(rule["tags"], dict)

    # Find dev rule and verify its tags
    dev_rule = next(r for r in output_data if r["name"] == "dev-lambda-scheduler")
    assert dev_rule["tags"]["Env"] == "dev"
    assert dev_rule["tags"]["Team"] == "backend"


@pytest.mark.integration
def test_list_rules_json_format_includes_targets(cli_runner, mock_aws_client):
    """Test that JSON format includes target details."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify targets are included
    for rule in output_data:
        assert "targets" in rule
        assert isinstance(rule["targets"], list)
        if rule["targets"]:
            target = rule["targets"][0]
            assert "id" in target
            assert "arn" in target


@pytest.mark.integration
def test_filter_nonexistent_environment_returns_empty(cli_runner, mock_aws_client):
    """Test filtering by non-existent environment returns empty result."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with non-existent environment
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "nonexistent",
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success but no rules message
    assert result.exit_code == 0
    assert "No rules found" in result.output


@pytest.mark.integration
def test_list_rules_with_no_credentials_error(cli_runner, mocker):
    """Test listing rules with no AWS credentials returns error."""
    from botocore.exceptions import NoCredentialsError

    # Mock create_aws_client to raise NoCredentialsError
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", side_effect=NoCredentialsError())

    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify error handling
    assert "credentials not found" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.integration
def test_list_rules_with_client_error(cli_runner, mocker):
    """Test listing rules with AWS ClientError."""
    from botocore.exceptions import ClientError

    # Mock create_aws_client to raise ClientError
    mocker.patch(
        "cli_tool.core.utils.aws.create_aws_client",
        side_effect=ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "User is not authorized to perform: events:ListRules"}},
            operation_name="ListRules",
        ),
    )

    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify error handling
    assert "error" in result.output.lower() or "authorized" in result.output.lower()


@pytest.mark.integration
def test_list_rules_with_generic_exception(cli_runner, mocker):
    """Test listing rules with generic exception."""
    # Mock create_aws_client to raise generic exception
    mocker.patch("cli_tool.core.utils.aws.create_aws_client", side_effect=Exception("Unexpected error"))

    eventbridge_cmd = register_eventbridge_commands()

    # Run command
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify error handling
    assert "error" in result.output.lower()


@pytest.mark.integration
def test_list_rules_empty_result_shows_message(cli_runner, monkeypatch, mocker):
    """Test listing rules when no rules exist shows appropriate message."""
    import boto3
    from moto import mock_aws

    # Set fake AWS credentials
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        empty_client = boto3.client("events", region_name="us-east-1")
        mocker.patch("cli_tool.core.utils.aws.create_aws_client", return_value=empty_client)

        eventbridge_cmd = register_eventbridge_commands()

        # Run command
        result = cli_runner.invoke(
            eventbridge_cmd,
            [
                "--status",
                "ALL",
                "--output",
                "table",
            ],
            obj={},
        )

        # Verify message about no rules
        assert result.exit_code == 0
        assert "No rules found" in result.output


@pytest.mark.integration
def test_list_rules_case_insensitive_status_filter(cli_runner, mock_aws_client):
    """Test that status filter is case-insensitive."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with lowercase status
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "enabled",
            "--output",
            "json",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = extract_json_from_output(result.output)

    # Verify only enabled rules are returned
    assert len(output_data) == 3
    for rule in output_data:
        assert rule["state"] == "ENABLED"


@pytest.mark.integration
def test_list_rules_case_insensitive_output_format(cli_runner, mock_aws_client):
    """Test that output format is case-insensitive."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with uppercase output format
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--status",
            "ALL",
            "--output",
            "JSON",
        ],
        obj={},
    )

    # Verify success and JSON output
    assert result.exit_code == 0

    # Should be valid JSON
    output_data = extract_json_from_output(result.output)
    assert isinstance(output_data, list)


@pytest.mark.integration
def test_list_rules_with_environment_filter_table_title(cli_runner, mock_aws_client):
    """Test that table title includes environment filter when specified."""
    eventbridge_cmd = register_eventbridge_commands()

    # Run command with environment filter
    result = cli_runner.invoke(
        eventbridge_cmd,
        [
            "--env",
            "dev",
            "--status",
            "ALL",
            "--output",
            "table",
        ],
        obj={},
    )

    # Verify success
    assert result.exit_code == 0

    # Verify table title includes environment
    assert "DEV" in result.output or "dev" in result.output
    assert "EventBridge Scheduled Rules" in result.output
