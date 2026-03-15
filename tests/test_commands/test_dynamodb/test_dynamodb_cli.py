"""Unit tests for DynamoDB CLI command group (cli.py)."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_tool.commands.dynamodb.commands.cli import dynamodb

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# list command — line 33 (list_tables_command called with profile + region)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDynamoDBListCommand:
    def test_list_command_calls_list_tables_command(self):
        """
        Line 33: the 'list' subcommand resolves a profile and delegates to
        list_tables_command with that profile and the region.
        """
        runner = _make_runner()

        with patch("cli_tool.commands.dynamodb.commands.cli.list_tables_command") as mock_list:
            with patch("cli_tool.core.utils.aws.select_profile", return_value="my-profile"):
                result = runner.invoke(dynamodb, ["list", "--region", "eu-west-1"], obj={"profile": "my-profile"})

        mock_list.assert_called_once_with("my-profile", "eu-west-1")

    def test_list_command_default_region(self):
        """Line 33: the default region is us-east-1."""
        runner = _make_runner()

        with patch("cli_tool.commands.dynamodb.commands.cli.list_tables_command") as mock_list:
            with patch("cli_tool.core.utils.aws.select_profile", return_value=None):
                result = runner.invoke(dynamodb, ["list"], obj={})

        mock_list.assert_called_once_with(None, "us-east-1")


# ---------------------------------------------------------------------------
# describe command — lines 47-50 (describe_table_command called)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDynamoDBDescribeCommand:
    def test_describe_command_calls_describe_table_command(self):
        """
        Lines 47-50: the 'describe' subcommand calls describe_table_command
        with the profile, table_name, and region.
        """
        runner = _make_runner()

        with patch("cli_tool.commands.dynamodb.commands.cli.describe_table_command") as mock_describe:
            with patch("cli_tool.core.utils.aws.select_profile", return_value=None):
                result = runner.invoke(dynamodb, ["describe", "my-table", "--region", "us-west-2"], obj={})

        mock_describe.assert_called_once_with(None, "my-table", "us-west-2")

    def test_describe_command_default_region(self):
        """Lines 47-50: default region for describe is us-east-1."""
        runner = _make_runner()

        with patch("cli_tool.commands.dynamodb.commands.cli.describe_table_command") as mock_describe:
            with patch("cli_tool.core.utils.aws.select_profile", return_value=None):
                result = runner.invoke(dynamodb, ["describe", "another-table"], obj={})

        mock_describe.assert_called_once_with(None, "another-table", "us-east-1")


# ---------------------------------------------------------------------------
# list-templates command — line 238 (list_templates_command called)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDynamoDBListTemplatesCommand:
    def test_list_templates_command_is_called(self):
        """
        Line 238: the 'list-templates' subcommand invokes list_templates_command()
        with no arguments.
        """
        runner = _make_runner()

        with patch("cli_tool.commands.dynamodb.commands.cli.list_templates_command") as mock_lt:
            result = runner.invoke(dynamodb, ["list-templates"], obj={})

        mock_lt.assert_called_once_with()

    def test_list_templates_help(self):
        """'list-templates' subcommand is accessible and has a help text."""
        runner = _make_runner()
        result = runner.invoke(dynamodb, ["list-templates", "--help"])
        assert result.exit_code == 0
        assert "template" in result.output.lower()
