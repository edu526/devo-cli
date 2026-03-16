"""Tests for SSM instance sub-commands: list, shell, add, remove."""

import pytest
from click.testing import CliRunner

from cli_tool.commands.ssm.commands.instance.add import add_instance
from cli_tool.commands.ssm.commands.instance.list import list_instances
from cli_tool.commands.ssm.commands.instance.remove import remove_instance
from cli_tool.commands.ssm.commands.instance.shell import connect_instance

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_ssm_config(mocker, temp_config_dir):
    """Patch load_config / save_config used by SSMConfigManager."""
    mock_config = {"ssm": {"databases": {}, "instances": {}}}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=mock_config)
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")
    return mock_config


@pytest.fixture
def sample_instance():
    return {
        "instance_id": "i-0abc1234def56789",
        "region": "us-east-1",
        "profile": "dev-profile",
    }


# ---------------------------------------------------------------------------
# list_instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_instances_empty(runner, mock_ssm_config):
    """When no instances are configured, a hint message is shown."""
    result = runner.invoke(list_instances, [])

    assert result.exit_code == 0
    assert "No instances configured" in result.output
    assert "devo ssm instance add" in result.output


@pytest.mark.unit
def test_list_instances_with_entries(runner, mock_ssm_config, sample_instance):
    """Configured instances are rendered in a table."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance

    result = runner.invoke(list_instances, [])

    assert result.exit_code == 0
    assert "bastion-dev" in result.output
    assert "i-0abc1234def56789" in result.output
    assert "us-east-1" in result.output
    assert "dev-profile" in result.output


@pytest.mark.unit
def test_list_instances_no_profile_shows_dash(runner, mock_ssm_config):
    """An instance without a profile shows '-' in the table."""
    mock_ssm_config["ssm"]["instances"]["bastion-prod"] = {
        "instance_id": "i-111222333",
        "region": "eu-west-1",
        "profile": None,
    }

    result = runner.invoke(list_instances, [])

    assert result.exit_code == 0
    assert "bastion-prod" in result.output
    assert "-" in result.output


# ---------------------------------------------------------------------------
# connect_instance (shell)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_connect_instance_not_found(runner, mock_ssm_config, sample_instance):
    """When the instance is not in config, an error and available list are shown."""
    mock_ssm_config["ssm"]["instances"]["other-instance"] = sample_instance

    result = runner.invoke(connect_instance, ["missing-instance"])

    assert result.exit_code == 0
    assert "missing-instance" in result.output
    assert "not found" in result.output
    assert "other-instance" in result.output


@pytest.mark.unit
def test_connect_instance_not_found_no_instances(runner, mock_ssm_config):
    """When no instances exist at all the error is shown with an empty list."""
    result = runner.invoke(connect_instance, ["missing"])

    assert result.exit_code == 0
    assert "missing" in result.output
    assert "not found" in result.output


@pytest.mark.unit
def test_connect_instance_expired_tokens_aborts_before_session(runner, mock_ssm_config, sample_instance, mocker):
    """Pre-check: expired tokens abort before starting the session."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    mock_session._is_token_expired.return_value = True

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "expired" in result.output.lower()
    mock_session.start_session.assert_not_called()


@pytest.mark.unit
def test_connect_instance_success(runner, mock_ssm_config, sample_instance, mocker):
    """A successful connection (returncode 0) exits cleanly without reconnecting."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    mock_session._is_token_expired.return_value = False
    mock_session.start_session.return_value = 0

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "Connecting to bastion-dev" in result.output
    mock_session.start_session.assert_called_once_with(
        instance_id="i-0abc1234def56789",
        region="us-east-1",
        profile="dev-profile",
    )


@pytest.mark.unit
def test_connect_instance_keyboard_interrupt(runner, mock_ssm_config, sample_instance, mocker):
    """A KeyboardInterrupt during the session is caught and 'Session closed' shown."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    mock_session._is_token_expired.return_value = False
    mock_session.start_session.side_effect = KeyboardInterrupt()

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "Session closed" in result.output


@pytest.mark.unit
def test_connect_instance_expired_tokens_shows_error(runner, mock_ssm_config, sample_instance, mocker):
    """When the session drops and tokens are expired, an error is shown and no reconnect happens."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    mock_session.start_session.return_value = 1
    # pre-check passes, post-drop check detects expiry
    mock_session._is_token_expired.side_effect = [False, True]

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "tokens are expired" in result.output.lower()
    assert "devo aws-login" in result.output
    mock_session.start_session.assert_called_once()


@pytest.mark.unit
def test_connect_instance_reconnects_when_tokens_valid(runner, mock_ssm_config, sample_instance, mocker):
    """When the session drops and tokens are valid, a reconnect is attempted."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    # First call drops with error; second call exits cleanly
    mock_session.start_session.side_effect = [1, 0]
    mock_session._is_token_expired.return_value = False
    mocker.patch("cli_tool.commands.ssm.commands.instance.shell.time.sleep")

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "Reconnecting" in result.output
    assert mock_session.start_session.call_count == 2


@pytest.mark.unit
def test_connect_instance_ctrl_c_during_reconnect_delay(runner, mock_ssm_config, sample_instance, mocker):
    """Ctrl+C during the reconnect countdown cancels the reconnect."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance
    mock_session = mocker.patch("cli_tool.commands.ssm.commands.instance.shell.SSMSession")
    mock_session.start_session.return_value = 1
    mock_session._is_token_expired.return_value = False
    mocker.patch("cli_tool.commands.ssm.commands.instance.shell.time.sleep", side_effect=KeyboardInterrupt)

    result = runner.invoke(connect_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "Connection closed" in result.output
    mock_session.start_session.assert_called_once()


# ---------------------------------------------------------------------------
# add_instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_add_instance_success(runner, mock_ssm_config):
    """A valid invocation adds the instance and prints confirmation."""
    result = runner.invoke(
        add_instance,
        [
            "--name",
            "bastion-dev",
            "--instance-id",
            "i-0abc1234def56789",
            "--region",
            "us-east-1",
            "--profile",
            "dev-profile",
        ],
    )

    assert result.exit_code == 0
    assert "bastion-dev" in result.output
    assert "added successfully" in result.output
    assert "devo ssm shell bastion-dev" in result.output


@pytest.mark.unit
def test_add_instance_default_region(runner, mock_ssm_config):
    """When --region is omitted it defaults to us-east-1."""
    result = runner.invoke(
        add_instance,
        [
            "--name",
            "bastion-dev",
            "--instance-id",
            "i-0abc1234def56789",
        ],
    )

    assert result.exit_code == 0
    assert "bastion-dev" in result.output


@pytest.mark.unit
def test_add_instance_missing_required_option(runner, mock_ssm_config):
    """Omitting a required option causes a non-zero exit."""
    result = runner.invoke(add_instance, ["--name", "bastion-dev"])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# remove_instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_remove_instance_success(runner, mock_ssm_config, sample_instance):
    """Removing an existing instance prints confirmation."""
    mock_ssm_config["ssm"]["instances"]["bastion-dev"] = sample_instance

    result = runner.invoke(remove_instance, ["bastion-dev"])

    assert result.exit_code == 0
    assert "bastion-dev" in result.output
    assert "removed" in result.output


@pytest.mark.unit
def test_remove_instance_not_found(runner, mock_ssm_config):
    """Removing a non-existent instance prints 'not found'."""
    result = runner.invoke(remove_instance, ["nonexistent"])

    assert result.exit_code == 0
    assert "nonexistent" in result.output
    assert "not found" in result.output
