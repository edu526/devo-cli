"""
Tests for config utilities and credentials writing.

Covers:
- remove_section_from_file (generic)
- remove_profile_section
- write_default_credentials
- configure_sso_profile 'default' name guard
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli_tool.commands.aws_login.core.config import remove_profile_section, remove_section_from_file

# ---------------------------------------------------------------------------
# remove_section_from_file
# ---------------------------------------------------------------------------


def test_remove_section_removes_target(tmp_path):
    """Target section and its keys are removed; other sections survive."""
    cfg = tmp_path / "config"
    cfg.write_text("[profile foo]\nregion = us-east-1\n" + "\n[profile bar]\nregion = eu-west-1\n")

    remove_section_from_file(cfg, "[profile foo]")

    content = cfg.read_text()
    assert "[profile foo]" not in content
    assert "us-east-1" not in content
    assert "[profile bar]" in content
    assert "eu-west-1" in content


def test_remove_section_nonexistent_section_leaves_file_unchanged(tmp_path):
    """Removing a section that does not exist leaves the file intact."""
    original = "[profile foo]\nregion = us-east-1\n"
    cfg = tmp_path / "config"
    cfg.write_text(original)

    remove_section_from_file(cfg, "[profile ghost]")

    assert cfg.read_text() == original


def test_remove_section_missing_file_is_noop(tmp_path):
    """Calling on a non-existent file does not raise."""
    remove_section_from_file(tmp_path / "nonexistent", "[default]")  # should not raise


def test_remove_section_last_section_in_file(tmp_path):
    """Removing the last section in the file leaves the rest intact."""
    cfg = tmp_path / "config"
    cfg.write_text("[profile first]\nkey = val\n" + "\n[profile last]\nkey = other\n")

    remove_section_from_file(cfg, "[profile last]")

    content = cfg.read_text()
    assert "[profile last]" not in content
    assert "[profile first]" in content


def test_remove_section_default_header(tmp_path):
    """[default] header is matched literally."""
    cfg = tmp_path / "credentials"
    cfg.write_text("[default]\naws_access_key_id = AKIA\naws_secret_access_key = SECRET\n" + "\n[other]\naws_access_key_id = OTHER\n")

    remove_section_from_file(cfg, "[default]")

    content = cfg.read_text()
    assert "[default]" not in content
    assert "AKIA" not in content
    assert "[other]" in content


# ---------------------------------------------------------------------------
# remove_profile_section
# ---------------------------------------------------------------------------


def test_remove_profile_section_named(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    cfg = aws_dir / "config"
    cfg.write_text("[profile dev]\nregion = us-east-1\n\n[profile prod]\nregion = eu-west-1\n")

    remove_profile_section("dev")

    content = cfg.read_text()
    assert "[profile dev]" not in content
    assert "[profile prod]" in content


def test_remove_profile_section_default(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    cfg = aws_dir / "config"
    cfg.write_text("[default]\nregion = us-east-1\n\n[profile other]\nregion = sa-east-1\n")

    remove_profile_section("default")

    content = cfg.read_text()
    assert "[default]" not in content
    assert "[profile other]" in content


# ---------------------------------------------------------------------------
# write_default_credentials
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_aws_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    return aws_dir


def _make_export_creds_result(access_key="AKIATEST", secret="SECRET", token="TOKEN", expiration="2099-01-01T00:00:00+00:00", region=None):
    payload = {
        "AccessKeyId": access_key,
        "SecretAccessKey": secret,
        "SessionToken": token,
        "Expiration": expiration,
    }
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = json.dumps(payload)
    return mock


@pytest.mark.integration
def test_write_default_credentials_creates_file(mock_aws_home, mocker):
    """write_default_credentials creates ~/.aws/credentials with [default]."""
    from cli_tool.commands.aws_login.core.credentials import write_default_credentials

    mocker.patch("subprocess.run", return_value=_make_export_creds_result())
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"region": "us-east-1"},
    )

    result = write_default_credentials("my-profile")

    assert result is not None
    assert result["expiration"] == "2099-01-01T00:00:00+00:00"

    content = (mock_aws_home / "credentials").read_text()
    assert "[default]" in content
    assert "aws_access_key_id = AKIATEST" in content
    assert "aws_secret_access_key = SECRET" in content
    assert "aws_session_token = TOKEN" in content
    assert "region = us-east-1" in content


@pytest.mark.integration
def test_write_default_credentials_replaces_existing(mock_aws_home, mocker):
    """Existing [default] section is replaced, not duplicated."""
    from cli_tool.commands.aws_login.core.credentials import write_default_credentials

    creds_file = mock_aws_home / "credentials"
    creds_file.write_text(
        "[default]\naws_access_key_id = OLD_KEY\naws_secret_access_key = OLD_SECRET\n" + "\n[other-profile]\naws_access_key_id = OTHER\n"
    )

    mocker.patch("subprocess.run", return_value=_make_export_creds_result(access_key="NEW_KEY", secret="NEW_SECRET", token=None))
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"region": "us-west-2"},
    )

    write_default_credentials("my-profile")

    content = creds_file.read_text()
    assert content.count("[default]") == 1
    assert "NEW_KEY" in content
    assert "OLD_KEY" not in content
    assert "[other-profile]" in content


@pytest.mark.integration
def test_write_default_credentials_no_session_token(mock_aws_home, mocker):
    """aws_session_token line is omitted when token is absent."""
    from cli_tool.commands.aws_login.core.credentials import write_default_credentials

    mocker.patch("subprocess.run", return_value=_make_export_creds_result(token=None))
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={},
    )

    # Patch json.loads to drop SessionToken
    original_loads = json.loads

    def patched_loads(s):
        d = original_loads(s)
        d.pop("SessionToken", None)
        return d

    mocker.patch("cli_tool.commands.aws_login.core.credentials.json.loads", side_effect=patched_loads)

    write_default_credentials("my-profile")

    content = (mock_aws_home / "credentials").read_text()
    assert "aws_session_token" not in content


@pytest.mark.integration
def test_write_default_credentials_export_fails_returns_none(mock_aws_home, mocker):
    """Returns None when aws configure export-credentials fails."""
    from cli_tool.commands.aws_login.core.credentials import write_default_credentials

    failed = MagicMock()
    failed.returncode = 1
    failed.stderr = "NoCredentialProviders"
    mocker.patch("subprocess.run", return_value=failed)

    result = write_default_credentials("bad-profile")

    assert result is None


# ---------------------------------------------------------------------------
# configure_sso_profile — 'default' name guard
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_configure_sso_profile_rejects_default_name(mocker):
    """configure_sso_profile returns None immediately when profile name is 'default'."""
    from cli_tool.commands.aws_login.commands.setup import configure_sso_profile

    result = configure_sso_profile("default")

    assert result is None


@pytest.mark.integration
def test_configure_sso_profile_rejects_default_name_case_insensitive(mocker):
    """configure_sso_profile rejects 'DEFAULT', 'Default', etc."""
    from cli_tool.commands.aws_login.commands.setup import configure_sso_profile

    for name in ("DEFAULT", "Default", "DeFaUlT"):
        result = configure_sso_profile(name)
        assert result is None, f"Expected None for profile name '{name}'"
