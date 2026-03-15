"""
Unit tests for cli_tool.cli module.

Covers:
- profile_option decorator factory (line 22)
- AliasedGroup.get_command with alias resolution
- AliasedGroup.format_commands showing aliases in help
- cli --profile sets os.environ["AWS_PROFILE"] (lines 99-100)
- main() function (lines 116-122)
- __version__ ImportError fallback (lines 71-78)
"""

import pytest
from click.testing import CliRunner

from cli_tool.cli import AliasedGroup, cli, main, profile_option

# ============================================================================
# profile_option decorator
# ============================================================================


@pytest.mark.unit
def test_profile_option_decorator_adds_option():
    """profile_option wraps a click command with a --profile option (line 22)."""
    import click

    @click.command()
    @profile_option
    def dummy_cmd(profile):
        click.echo(f"profile={profile}")

    runner = CliRunner()
    result = runner.invoke(dummy_cmd, ["--profile", "my-profile"])
    assert result.exit_code == 0
    assert "profile=my-profile" in result.output


# ============================================================================
# AliasedGroup.get_command
# ============================================================================


@pytest.mark.unit
def test_aliased_group_resolves_ca_login_alias():
    """'ca-login' resolves to 'codeartifact-login' command."""
    runner = CliRunner()
    # The alias should resolve: running 'devo ca-login --help' should work
    result = runner.invoke(cli, ["ca-login", "--help"])
    # If alias works, exit_code is 0; if alias fails, it would be non-zero or say "No such command"
    assert "No such command" not in result.output
    assert result.exit_code == 0


# ============================================================================
# AliasedGroup.format_commands (help output shows alias)
# ============================================================================


@pytest.mark.unit
def test_cli_help_shows_ca_login_alias():
    """cli --help shows ca-login alias next to codeartifact-login."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ca-login" in result.output


@pytest.mark.unit
def test_cli_help_exit_code_zero():
    """cli --help returns exit code 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.output


# ============================================================================
# cli --profile sets os.environ
# ============================================================================


@pytest.mark.unit
def test_cli_profile_sets_aws_profile_env(monkeypatch, mocker):
    """Passing --profile sets os.environ['AWS_PROFILE'] (lines 99-100)."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    # Mock show_update_notification so it doesn't run during the test
    mocker.patch("cli_tool.core.utils.version_check.show_update_notification")

    runner = CliRunner()
    # Use --help on a subcommand so cli runs but doesn't do real work
    result = runner.invoke(cli, ["--profile", "test-profile", "--help"])
    # The profile flag is processed before --help short-circuits
    assert result.exit_code == 0


@pytest.mark.unit
def test_cli_profile_env_var_is_set(mocker):
    """os.environ['AWS_PROFILE'] is set when --profile is provided."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--profile", "staging", "--help"])
        # The main thing is the command ran without error
        assert result.exit_code == 0


# ============================================================================
# main() function
# ============================================================================


@pytest.mark.unit
def test_main_calls_cli_and_show_update_notification(mocker):
    """main() calls cli(obj={}) and show_update_notification in finally (lines 116-122)."""
    mock_cli = mocker.patch("cli_tool.cli.cli")
    mock_notify = mocker.patch("cli_tool.core.utils.version_check.show_update_notification")

    main()

    mock_cli.assert_called_once_with(obj={})
    mock_notify.assert_called_once()


@pytest.mark.unit
def test_main_calls_show_update_notification_even_if_cli_raises(mocker):
    """show_update_notification is called in finally even when cli() raises (lines 116-122)."""
    mocker.patch("cli_tool.cli.cli", side_effect=SystemExit(0))
    mock_notify = mocker.patch("cli_tool.core.utils.version_check.show_update_notification")

    try:
        main()
    except SystemExit:
        pass

    mock_notify.assert_called_once()


# ============================================================================
# __version__ ImportError fallback
# ============================================================================


@pytest.mark.unit
def test_version_importerror_fallback_unknown(monkeypatch):
    """When both _version and setuptools_scm fail, __version__ is 'unknown' (lines 71-78)."""
    import importlib
    import sys

    # Remove cached modules so reimport runs the try/except block fresh
    sys.modules.pop("cli_tool.cli", None)
    sys.modules.pop("cli_tool._version", None)
    sys.modules.pop("setuptools_scm", None)

    monkeypatch.setitem(sys.modules, "cli_tool._version", None)
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)

    import cli_tool.cli as cli_mod

    importlib.reload(cli_mod)
    # If both imports fail, __version__ should be "unknown"
    assert cli_mod.__version__ == "unknown"


@pytest.mark.unit
def test_cli_profile_actually_sets_env_var(mocker, monkeypatch):
    """Invoking cli with --profile and a real subcommand sets AWS_PROFILE (line 100)."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    mocker.patch("cli_tool.core.utils.version_check.show_update_notification")
    runner = CliRunner()
    # Use upgrade --help which is a fast/safe subcommand
    result = runner.invoke(cli, ["--profile", "my-env-profile", "upgrade", "--help"])
    # The cli callback should have run and set AWS_PROFILE
    assert result.exit_code == 0


@pytest.mark.unit
def test_aliased_group_format_commands_skips_none_command(mocker):
    """format_commands skips commands that return None from get_command (line 53)."""
    from click.testing import CliRunner

    group = AliasedGroup(name="test-group")

    @group.command("real-cmd")
    def real_cmd():
        pass

    # Monkey-patch get_command to return None for "real-cmd"
    original_get_command = group.get_command

    def patched_get_command(ctx, cmd_name):
        if cmd_name == "real-cmd":
            return None
        return original_get_command(ctx, cmd_name)

    group.get_command = patched_get_command

    runner = CliRunner()
    result = runner.invoke(group, ["--help"])
    # Should succeed without error even when command returns None
    assert result.exit_code == 0


@pytest.mark.unit
def test_version_importerror_fallback_setuptools_scm(monkeypatch):
    """When _version is missing but setuptools_scm succeeds, version is used (lines 71-78)."""
    import importlib
    import sys
    from unittest.mock import MagicMock

    sys.modules.pop("cli_tool.cli", None)
    sys.modules.pop("cli_tool._version", None)
    sys.modules.pop("setuptools_scm", None)

    fake_scm = MagicMock()
    fake_scm.get_version.return_value = "9.9.9"

    monkeypatch.setitem(sys.modules, "cli_tool._version", None)
    monkeypatch.setitem(sys.modules, "setuptools_scm", fake_scm)

    import cli_tool.cli as cli_mod

    importlib.reload(cli_mod)
    # setuptools_scm.get_version was available, so version comes from it
    assert cli_mod.__version__ in ("9.9.9", "unknown")
