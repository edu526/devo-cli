"""Unit tests for cli_tool.commands.aws_login.commands.setup module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli_tool.commands.aws_login.commands.setup import (
    _prompt_manual_account_role_region,
    _read_sso_session_config,
    _resolve_account_role_region,
    _select_account_from_list,
    _write_profile_config,
    configure_profile_with_existing_session,
    configure_sso_profile,
)

# ---------------------------------------------------------------------------
# _read_sso_session_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_sso_session_config_returns_values(tmp_path):
    """Reads sso_start_url and sso_region from a named sso-session section."""
    config = tmp_path / "config"
    config.write_text(
        "[sso-session my-org]\n" "sso_start_url = https://org.awsapps.com/start\n" "sso_region = us-east-1\n" "[profile dev]\n" "region = us-east-1\n"
    )

    url, region = _read_sso_session_config(config, "my-org")

    assert url == "https://org.awsapps.com/start"
    assert region == "us-east-1"


@pytest.mark.unit
def test_read_sso_session_config_returns_none_when_not_found(tmp_path):
    """Returns (None, None) when session name does not exist."""
    config = tmp_path / "config"
    config.write_text("[sso-session other]\nsso_start_url = https://other.com/start\n")

    url, region = _read_sso_session_config(config, "missing")

    assert url is None
    assert region is None


@pytest.mark.unit
def test_read_sso_session_config_returns_none_on_exception(tmp_path):
    """Returns (None, None) when file cannot be read."""
    non_existent = tmp_path / "does_not_exist"

    url, region = _read_sso_session_config(non_existent, "any-session")

    assert url is None
    assert region is None


@pytest.mark.unit
def test_read_sso_session_config_stops_at_next_section(tmp_path):
    """Stops reading at the next section header and does not bleed into next section."""
    config = tmp_path / "config"
    config.write_text(
        "[sso-session my-org]\n"
        "sso_start_url = https://org.awsapps.com/start\n"
        "[profile dev]\n"
        "sso_start_url = https://wrong.awsapps.com/start\n"
    )

    url, region = _read_sso_session_config(config, "my-org")

    assert url == "https://org.awsapps.com/start"
    assert region is None


@pytest.mark.unit
def test_read_sso_session_config_only_url_no_region(tmp_path):
    """Returns url and None when only sso_start_url is present."""
    config = tmp_path / "config"
    config.write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\n")

    url, region = _read_sso_session_config(config, "my-org")

    assert url == "https://org.awsapps.com/start"
    assert region is None


# ---------------------------------------------------------------------------
# _prompt_manual_account_role_region
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prompt_manual_account_role_region_returns_tuple(mocker):
    """Returns (account_id, role_name, region) from prompts."""
    mocker.patch("click.prompt", side_effect=["123456789012", "MyRole", "us-west-2"])

    account_id, role_name, region = _prompt_manual_account_role_region()

    assert account_id == "123456789012"
    assert role_name == "MyRole"
    assert region == "us-west-2"


# ---------------------------------------------------------------------------
# _select_account_from_list
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_account_from_list_valid_selection(mocker):
    """Selects an account and fetches roles successfully."""
    accounts = [
        {"accountId": "111111111111", "accountName": "Dev Account"},
        {"accountId": "222222222222", "accountName": "Prod Account"},
    ]
    mocker.patch("click.prompt", side_effect=[1, 1, "us-east-1"])
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"roleList": [{"roleName": "DevRole"}]}'),
    )

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "fake-token")

    assert account_id == "111111111111"
    assert role_name == "DevRole"
    assert region == "us-east-1"


@pytest.mark.unit
def test_select_account_from_list_invalid_account_choice(mocker):
    """Returns (None, None, None) when account selection is out of range."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", return_value=99)

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert account_id is None
    assert role_name is None
    assert region is None


@pytest.mark.unit
def test_select_account_from_list_invalid_account_choice_zero(mocker):
    """Returns (None, None, None) when account selection is 0 (below range)."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", return_value=0)

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert account_id is None
    assert role_name is None
    assert region is None


@pytest.mark.unit
def test_select_account_from_list_no_roles_prompts_manually(mocker):
    """When no roles returned, prompts for role name manually."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", side_effect=[1, "ManualRole", "us-east-1"])
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"roleList": []}'),
    )

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert account_id == "111111111111"
    assert role_name == "ManualRole"


@pytest.mark.unit
def test_select_account_from_list_role_fetch_fails_prompts_manually(mocker):
    """When role fetch fails, prompts for role name manually."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", side_effect=[1, "FallbackRole", "eu-west-1"])
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="error"),
    )

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert account_id == "111111111111"
    assert role_name == "FallbackRole"
    assert region == "eu-west-1"


@pytest.mark.unit
def test_select_account_from_list_role_choice_out_of_range_falls_back_to_first(mocker):
    """When role choice is out of range, falls back to first role."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", side_effect=[1, 99, "us-east-1"])
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout='{"roleList": [{"roleName": "AdminRole"}, {"roleName": "ReadRole"}]}',
        ),
    )

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert role_name == "AdminRole"


@pytest.mark.unit
def test_select_account_from_list_uses_default_region_when_sso_region_none(mocker):
    """Uses us-east-1 when sso_region is None."""
    accounts = [{"accountId": "111111111111", "accountName": "Dev"}]
    mocker.patch("click.prompt", side_effect=[1, 1, "us-east-1"])
    mock_run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"roleList": [{"roleName": "Role"}]}'),
    )

    _select_account_from_list(accounts, None, "token")

    cmd = mock_run.call_args[0][0]
    assert "us-east-1" in cmd


@pytest.mark.unit
def test_select_account_from_list_second_account_selected(mocker):
    """Selecting second account returns correct accountId."""
    accounts = [
        {"accountId": "111111111111", "accountName": "Dev"},
        {"accountId": "222222222222", "accountName": "Prod"},
    ]
    mocker.patch("click.prompt", side_effect=[2, 1, "us-east-1"])
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"roleList": [{"roleName": "ProdRole"}]}'),
    )

    account_id, role_name, region = _select_account_from_list(accounts, "us-east-1", "token")

    assert account_id == "222222222222"
    assert role_name == "ProdRole"


# ---------------------------------------------------------------------------
# _resolve_account_role_region
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_account_role_region_success(mocker):
    """Returns account/role/region from SSO API when accounts are found."""
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout='{"accountList": [{"accountId": "111111111111", "accountName": "Dev"}]}',
        ),
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._select_account_from_list",
        return_value=("111111111111", "DevRole", "us-east-1"),
    )

    account_id, role_name, region = _resolve_account_role_region("token", "us-east-1")

    assert account_id == "111111111111"
    assert role_name == "DevRole"
    assert region == "us-east-1"


@pytest.mark.unit
def test_resolve_account_role_region_no_accounts_falls_back_to_manual(mocker):
    """Falls back to manual entry when no accounts found."""
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"accountList": []}'),
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("999999999999", "ManualRole", "ap-southeast-1"),
    )

    account_id, role_name, region = _resolve_account_role_region("token", "us-east-1")

    assert account_id == "999999999999"
    assert role_name == "ManualRole"


@pytest.mark.unit
def test_resolve_account_role_region_list_command_fails_falls_back(mocker):
    """Falls back to manual entry when list-accounts command fails."""
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stderr="AccessDenied", stdout=""),
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("888888888888", "AnotherRole", "eu-central-1"),
    )

    account_id, role_name, region = _resolve_account_role_region("token", "us-east-1")

    assert account_id == "888888888888"


@pytest.mark.unit
def test_resolve_account_role_region_exception_falls_back(mocker):
    """Falls back to manual entry when an exception occurs."""
    mocker.patch("subprocess.run", side_effect=Exception("connection refused"))
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("777777777777", "ExRole", "us-west-1"),
    )

    account_id, role_name, region = _resolve_account_role_region("token", "us-east-1")

    assert account_id == "777777777777"


@pytest.mark.unit
def test_resolve_account_role_region_uses_default_region_when_sso_region_none(mocker):
    """Uses us-east-1 as default region when sso_region is None."""
    mock_run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"accountList": []}'),
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("111", "Role", "us-east-1"),
    )

    _resolve_account_role_region("token", None)

    cmd = mock_run.call_args[0][0]
    assert "us-east-1" in cmd


# ---------------------------------------------------------------------------
# _write_profile_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_profile_config_creates_named_profile(tmp_path, monkeypatch):
    """Writes [profile <name>] section to config file."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("")

    _write_profile_config("dev", "my-org", "123456789012", "DevRole", "us-east-1")

    content = (aws_dir / "config").read_text()
    assert "[profile dev]" in content
    assert "sso_session = my-org" in content
    assert "sso_account_id = 123456789012" in content
    assert "sso_role_name = DevRole" in content
    assert "region = us-east-1" in content
    assert "output = json" in content


@pytest.mark.unit
def test_write_profile_config_creates_default_profile(tmp_path, monkeypatch):
    """Writes [default] section when profile_name is 'default'."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("")

    _write_profile_config("default", "my-org", "123456789012", "DevRole", "us-east-1")

    content = (aws_dir / "config").read_text()
    assert "[default]" in content
    assert "[profile default]" not in content


@pytest.mark.unit
def test_write_profile_config_creates_aws_dir_if_missing(tmp_path, monkeypatch):
    """Creates ~/.aws directory if it does not exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    _write_profile_config("myprofile", "my-org", "111111111111", "MyRole", "us-east-1")

    assert (tmp_path / ".aws" / "config").exists()


@pytest.mark.unit
def test_write_profile_config_removes_existing_section_first(tmp_path, monkeypatch, mocker):
    """Calls remove_profile_section before writing new config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("")

    mock_remove = mocker.patch("cli_tool.commands.aws_login.commands.setup.remove_profile_section")

    _write_profile_config("dev", "my-org", "123456789012", "DevRole", "us-east-1")

    mock_remove.assert_called_once_with("dev")


# ---------------------------------------------------------------------------
# configure_profile_with_existing_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_profile_with_existing_session_success(tmp_path, monkeypatch, mocker):
    """Successfully configures a profile with an existing SSO session."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\nsso_region = us-east-1\n")

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_sso_cache_token", return_value="valid-token")
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._resolve_account_role_region",
        return_value=("123456789012", "DevRole", "us-east-1"),
    )
    mocker.patch("cli_tool.commands.aws_login.commands.setup._write_profile_config")

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result == "dev"


@pytest.mark.unit
def test_configure_profile_with_existing_session_login_fails(mocker):
    """Returns None when aws sso login fails."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result is None


@pytest.mark.unit
def test_configure_profile_with_existing_session_login_timeout(mocker):
    """Returns None when aws sso login times out."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 120))

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result is None


@pytest.mark.unit
def test_configure_profile_with_existing_session_keyboard_interrupt(mocker):
    """Returns None when user cancels with Ctrl+C during sso login."""
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt())

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result is None


@pytest.mark.unit
def test_configure_profile_with_existing_session_no_sso_url_falls_back_to_manual(tmp_path, monkeypatch, mocker):
    """Falls back to manual entry when sso_start_url not found in config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("")  # Empty config — no SSO session block

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("111111111111", "ManualRole", "us-west-2"),
    )
    mocker.patch("cli_tool.commands.aws_login.commands.setup._write_profile_config")

    result = configure_profile_with_existing_session("dev", "missing-session")

    assert result == "dev"


@pytest.mark.unit
def test_configure_profile_with_existing_session_no_access_token_falls_back(tmp_path, monkeypatch, mocker):
    """Falls back to manual entry when access token not in SSO cache."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\nsso_region = us-east-1\n")

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_sso_cache_token", return_value=None)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._prompt_manual_account_role_region",
        return_value=("222222222222", "CacheRole", "ap-east-1"),
    )
    mocker.patch("cli_tool.commands.aws_login.commands.setup._write_profile_config")

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result == "dev"


@pytest.mark.unit
def test_configure_profile_with_existing_session_resolve_returns_none_account(tmp_path, monkeypatch, mocker):
    """Returns None when _resolve_account_role_region returns None for account_id."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\nsso_region = us-east-1\n")

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_sso_cache_token", return_value="valid-token")
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup._resolve_account_role_region",
        return_value=(None, None, None),
    )

    result = configure_profile_with_existing_session("dev", "my-org")

    assert result is None


# ---------------------------------------------------------------------------
# configure_sso_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_sso_profile_rejects_default_name():
    """Returns None when profile name is 'default'."""
    result = configure_sso_profile("default")
    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_rejects_default_name_case_insensitive():
    """Returns None when profile name is 'DEFAULT' (case-insensitive check)."""
    result = configure_sso_profile("DEFAULT")
    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_prompts_for_name_when_none_given(mocker):
    """Prompts for profile name when none is provided."""
    mocker.patch("click.prompt", return_value="my-profile")
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    result = configure_sso_profile()

    assert result == "my-profile"


@pytest.mark.unit
def test_configure_sso_profile_new_profile_no_sessions_runs_aws_configure_sso(mocker):
    """Runs 'aws configure sso' when no existing sessions found."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    result = configure_sso_profile("new-profile")

    assert result == "new-profile"
    cmd = mock_run.call_args[0][0]
    assert "aws" in cmd
    assert "configure" in cmd
    assert "sso" in cmd
    assert "--profile" in cmd
    assert "new-profile" in cmd


@pytest.mark.unit
def test_configure_sso_profile_aws_configure_sso_fails_returns_none(mocker):
    """Returns None when 'aws configure sso' returns non-zero exit code."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = configure_sso_profile("new-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_keyboard_interrupt_returns_none(mocker):
    """Returns None when user hits Ctrl+C during 'aws configure sso'."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt())

    result = configure_sso_profile("new-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_os_exception_returns_none(mocker):
    """Returns None when an OS exception occurs during 'aws configure sso'."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", side_effect=OSError("aws not found"))

    result = configure_sso_profile("new-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_existing_sso_profile_keep_choice_returns_name(mocker):
    """Returns profile name when user chooses option 1 (keep) on SSO profile."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_session": "my-org", "region": "us-east-1"},
    )
    mocker.patch("click.prompt", return_value=1)

    result = configure_sso_profile("existing-sso-profile")

    assert result == "existing-sso-profile"


@pytest.mark.unit
def test_configure_sso_profile_existing_non_sso_keep_choice_returns_none(mocker):
    """Returns None when user chooses keep (1) on a non-SSO profile."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"region": "us-east-1"},  # No SSO keys
    )
    mocker.patch("click.prompt", return_value=1)

    result = configure_sso_profile("static-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_reconfigure_confirmed_proceeds(mocker):
    """Proceeds with reconfiguration when user confirms overwrite (choice 2)."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_start_url": "https://old.com/start"},
    )
    mocker.patch("click.prompt", return_value=2)
    mocker.patch("click.confirm", return_value=True)
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    result = configure_sso_profile("my-profile")

    assert result == "my-profile"


@pytest.mark.unit
def test_configure_sso_profile_reconfigure_cancelled_returns_none(mocker):
    """Returns None when user cancels overwrite confirmation."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_start_url": "https://old.com/start"},
    )
    mocker.patch("click.prompt", return_value=2)
    mocker.patch("click.confirm", return_value=False)

    result = configure_sso_profile("my-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_choose_new_name_success(mocker):
    """Creates profile under a new name when user chooses option 3."""

    def mock_get_profile_config(name):
        if name == "existing-profile":
            return {"sso_start_url": "https://old.com/start"}
        return None

    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", side_effect=mock_get_profile_config)
    mocker.patch("click.prompt", side_effect=[3, "brand-new-profile"])
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value={})
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    result = configure_sso_profile("existing-profile")

    assert result == "brand-new-profile"


@pytest.mark.unit
def test_configure_sso_profile_new_name_is_default_rejected(mocker):
    """Returns None when user enters 'default' as the new profile name."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_start_url": "https://old.com/start"},
    )
    mocker.patch("click.prompt", side_effect=[3, "default"])

    result = configure_sso_profile("existing-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_new_name_already_exists_returns_none(mocker):
    """Returns None when the chosen new name already exists as a profile."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_start_url": "https://old.com/start"},
    )
    mocker.patch("click.prompt", side_effect=[3, "also-existing"])

    result = configure_sso_profile("existing-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_cancel_choice_returns_none(mocker):
    """Returns None when user chooses option 4 (cancel)."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={"sso_session": "my-org"},
    )
    mocker.patch("click.prompt", return_value=4)

    result = configure_sso_profile("my-profile")

    assert result is None


@pytest.mark.unit
def test_configure_sso_profile_existing_sessions_select_first(mocker):
    """Selects existing SSO session and delegates to configure_profile_with_existing_session."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions",
        return_value={"my-org": {"sso_start_url": "https://org.awsapps.com/start"}},
    )
    mocker.patch("click.prompt", return_value=1)
    mock_configure = mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.configure_profile_with_existing_session",
        return_value="new-profile",
    )

    result = configure_sso_profile("new-profile")

    assert result == "new-profile"
    mock_configure.assert_called_once_with("new-profile", "my-org")


@pytest.mark.unit
def test_configure_sso_profile_existing_sessions_select_create_new(mocker):
    """Selecting 'create new session' falls through to aws configure sso."""
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_profile_config", return_value=None)
    sessions = {"my-org": {"sso_start_url": "https://org.awsapps.com/start"}}
    mocker.patch("cli_tool.commands.aws_login.commands.setup.get_existing_sso_sessions", return_value=sessions)
    # len(sessions)+1 = 2 means "create new"
    mocker.patch("click.prompt", return_value=2)
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    result = configure_sso_profile("new-profile")

    assert result == "new-profile"


@pytest.mark.unit
def test_configure_sso_profile_shows_account_role_url_from_existing_profile(mocker):
    """Display branch for sso_account_id, sso_role_name, sso_start_url runs without error."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.setup.get_profile_config",
        return_value={
            "sso_account_id": "123456789012",
            "sso_role_name": "DevRole",
            "sso_start_url": "https://org.awsapps.com/start",
        },
    )
    mocker.patch("click.prompt", return_value=4)  # Cancel

    result = configure_sso_profile("my-profile")

    assert result is None
