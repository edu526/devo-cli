"""Unit tests for cli_tool.commands.aws_login.core.credentials module."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli_tool.commands.aws_login.core.credentials import (
    check_profile_credentials_available,
    check_profile_needs_refresh,
    get_profile_credentials_expiration,
    get_sso_cache_token,
    get_sso_token_expiration,
    verify_credentials,
    write_default_credentials,
)

# ---------------------------------------------------------------------------
# get_sso_cache_token
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_sso_cache_token_returns_none_when_no_cache_dir(tmp_path, monkeypatch):
    """Returns None when ~/.aws/sso/cache does not exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result is None


@pytest.mark.unit
def test_get_sso_cache_token_returns_token_when_valid(tmp_path, monkeypatch):
    """Returns access token when valid cache file exists."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)

    future_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_data = {
        "startUrl": "https://example.awsapps.com/start",
        "expiresAt": future_time,
        "accessToken": "my-access-token",
    }
    (cache_dir / "abc123.json").write_text(json.dumps(cache_data))

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result == "my-access-token"


@pytest.mark.unit
def test_get_sso_cache_token_returns_none_when_expired(tmp_path, monkeypatch):
    """Returns None when cache token is expired."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)

    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_data = {
        "startUrl": "https://example.awsapps.com/start",
        "expiresAt": past_time,
        "accessToken": "expired-token",
    }
    (cache_dir / "abc123.json").write_text(json.dumps(cache_data))

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result is None


@pytest.mark.unit
def test_get_sso_cache_token_returns_none_when_url_mismatch(tmp_path, monkeypatch):
    """Returns None when no cache file matches the requested URL."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)

    future_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_data = {
        "startUrl": "https://other.awsapps.com/start",
        "expiresAt": future_time,
        "accessToken": "token",
    }
    (cache_dir / "abc123.json").write_text(json.dumps(cache_data))

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result is None


@pytest.mark.unit
def test_get_sso_cache_token_handles_corrupt_json(tmp_path, monkeypatch):
    """Returns None when cache file contains invalid JSON."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bad.json").write_text("not valid json")

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result is None


# ---------------------------------------------------------------------------
# get_sso_token_expiration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_sso_token_expiration_returns_datetime(tmp_path, monkeypatch):
    """Returns expiration datetime when cache file has a matching URL."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)

    future = datetime.now(timezone.utc) + timedelta(hours=4)
    future_str = future.strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_data = {
        "startUrl": "https://example.awsapps.com/start",
        "expiresAt": future_str,
    }
    (cache_dir / "abc123.json").write_text(json.dumps(cache_data))

    result = get_sso_token_expiration("https://example.awsapps.com/start")

    assert result is not None
    assert isinstance(result, datetime)


@pytest.mark.unit
def test_get_sso_token_expiration_returns_none_when_no_dir(tmp_path, monkeypatch):
    """Returns None when sso cache directory doesn't exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_sso_token_expiration("https://example.awsapps.com/start")

    assert result is None


# ---------------------------------------------------------------------------
# get_profile_credentials_expiration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_profile_credentials_expiration_returns_datetime(mocker):
    """Returns expiration datetime when CLI command succeeds."""
    creds = {
        "AccessKeyId": "AKIA",
        "SecretAccessKey": "SECRET",
        "SessionToken": "TOKEN",
        "Expiration": "2099-12-31T23:59:59+00:00",
    }
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))

    result = get_profile_credentials_expiration("dev")

    assert result is not None
    assert isinstance(result, datetime)
    assert result.year == 2099


@pytest.mark.unit
def test_get_profile_credentials_expiration_returns_none_when_no_expiration(mocker):
    """Returns None when credentials have no expiration."""
    creds = {"AccessKeyId": "AKIA", "SecretAccessKey": "SECRET"}
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))

    result = get_profile_credentials_expiration("dev")

    assert result is None


@pytest.mark.unit
def test_get_profile_credentials_expiration_returns_none_on_failure(mocker):
    """Returns None when CLI command fails."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = get_profile_credentials_expiration("dev")

    assert result is None


@pytest.mark.unit
def test_get_profile_credentials_expiration_returns_none_on_exception(mocker):
    """Returns None when subprocess raises."""
    mocker.patch("subprocess.run", side_effect=Exception("error"))

    result = get_profile_credentials_expiration("dev")

    assert result is None


# ---------------------------------------------------------------------------
# check_profile_credentials_available
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_profile_credentials_available_returns_true(mocker):
    """Returns (True, None) when credentials export succeeds."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))

    available, error = check_profile_credentials_available("dev")

    assert available is True
    assert error is None


@pytest.mark.unit
def test_check_profile_credentials_available_returns_false_with_error(mocker):
    """Returns (False, error_message) when credentials export fails."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="NoCredentialProviders"))

    available, error = check_profile_credentials_available("dev")

    assert available is False
    assert "NoCredentialProviders" in error


@pytest.mark.unit
def test_check_profile_credentials_available_returns_false_on_timeout(mocker):
    """Returns (False, timeout message) on subprocess timeout."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 10))

    available, error = check_profile_credentials_available("dev")

    assert available is False
    assert "Timed out" in error


@pytest.mark.unit
def test_check_profile_credentials_available_returns_false_on_exception(mocker):
    """Returns (False, str(exception)) on general exception."""
    mocker.patch("subprocess.run", side_effect=Exception("some error"))

    available, error = check_profile_credentials_available("dev")

    assert available is False
    assert "some error" in error


@pytest.mark.unit
def test_check_profile_credentials_available_default_error_message(mocker):
    """When returncode is nonzero and stderr is empty, returns default message."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stderr=""))

    available, error = check_profile_credentials_available("dev")

    assert available is False
    assert error == "Could not export credentials"


# ---------------------------------------------------------------------------
# check_profile_needs_refresh
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_profile_needs_refresh_returns_false_when_not_sso(mocker):
    """Non-SSO profiles (no sso_session/sso_start_url) don't need refresh."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"region": "us-east-1"},
    )

    needs_refresh, expiration, reason = check_profile_needs_refresh("dev")

    assert needs_refresh is False
    assert "Not an SSO profile" in reason


@pytest.mark.unit
def test_check_profile_needs_refresh_returns_false_when_no_config(mocker):
    """Returns (False, None, 'Profile not found') when config is None."""
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config", return_value=None)

    needs_refresh, expiration, reason = check_profile_needs_refresh("nonexistent")

    assert needs_refresh is False
    assert "not found" in reason.lower()


@pytest.mark.unit
def test_check_profile_needs_refresh_needs_refresh_when_no_credentials(mocker):
    """Returns (True, None, 'No valid credentials found') when no expiration."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"sso_session": "my-session"},
    )
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration", return_value=None)

    needs_refresh, expiration, reason = check_profile_needs_refresh("dev")

    assert needs_refresh is True
    assert expiration is None


@pytest.mark.unit
def test_check_profile_needs_refresh_valid_credentials(mocker):
    """Returns (False, expiration, 'Valid') for credentials with plenty of time left."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"sso_start_url": "https://example.awsapps.com/start"},
    )
    future = datetime.now(timezone.utc) + timedelta(hours=8)
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration", return_value=future)

    needs_refresh, expiration, reason = check_profile_needs_refresh("dev")

    assert needs_refresh is False
    assert expiration == future
    assert reason == "Valid"


@pytest.mark.unit
def test_check_profile_needs_refresh_expired(mocker):
    """Returns (True, expiration, 'Expired') for expired credentials."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"sso_session": "my-session"},
    )
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration", return_value=past)

    needs_refresh, expiration, reason = check_profile_needs_refresh("dev")

    assert needs_refresh is True
    assert expiration == past
    assert reason == "Expired"


@pytest.mark.unit
def test_check_profile_needs_refresh_expiring_soon(mocker):
    """Returns (True, expiration, 'Expiring in N minutes') for soon-to-expire credentials."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"sso_session": "my-session"},
    )
    # 5 minutes left (below default threshold of 10 minutes)
    soon = datetime.now(timezone.utc) + timedelta(minutes=5)
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration", return_value=soon)

    needs_refresh, expiration, reason = check_profile_needs_refresh("dev")

    assert needs_refresh is True
    assert "Expiring in" in reason


# ---------------------------------------------------------------------------
# verify_credentials
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_credentials_returns_identity_dict(mocker):
    """Returns identity dict on successful sts get-caller-identity."""
    identity = {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:role/Dev", "UserId": "AROATEST"}
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(identity)))

    result = verify_credentials("dev")

    assert result is not None
    assert result["account"] == "123456789012"
    assert result["arn"] == "arn:aws:iam::123456789012:role/Dev"
    assert result["user_id"] == "AROATEST"


@pytest.mark.unit
def test_verify_credentials_returns_none_on_failure(mocker):
    """Returns None when sts call fails."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = verify_credentials("dev")

    assert result is None


@pytest.mark.unit
def test_verify_credentials_returns_none_on_exception(mocker):
    """Returns None when subprocess raises."""
    mocker.patch("subprocess.run", side_effect=Exception("network error"))

    result = verify_credentials("dev")

    assert result is None


@pytest.mark.unit
def test_verify_credentials_passes_profile_to_command(mocker):
    """The profile name is passed to aws sts get-caller-identity."""
    identity = {"Account": "123", "Arn": "arn:...", "UserId": "user"}
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(identity)))

    verify_credentials("my-profile")

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args
    assert "my-profile" in call_args


# ---------------------------------------------------------------------------
# write_default_credentials (unit tests - mocked subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_default_credentials_returns_none_on_export_failure(mocker):
    """Returns None when aws configure export-credentials fails."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="error"))

    result = write_default_credentials("bad-profile")

    assert result is None


@pytest.mark.unit
def test_write_default_credentials_returns_none_on_timeout(mocker):
    """Returns None on subprocess timeout."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 15))

    result = write_default_credentials("dev")

    assert result is None


@pytest.mark.unit
def test_write_default_credentials_returns_none_when_missing_keys(mocker):
    """Returns None when credentials response is missing AccessKeyId."""
    creds = {"SecretAccessKey": "SECRET"}
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))

    result = write_default_credentials("dev")

    assert result is None


@pytest.mark.unit
def test_write_default_credentials_returns_none_on_exception(mocker):
    """Returns None on general exception."""
    mocker.patch("subprocess.run", side_effect=Exception("unexpected"))

    result = write_default_credentials("dev")

    assert result is None


@pytest.mark.unit
def test_write_default_credentials_success(tmp_path, mocker, monkeypatch):
    """Returns dict with expiration on success and writes credentials file."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()

    creds = {
        "AccessKeyId": "AKIATEST",
        "SecretAccessKey": "SECRET",
        "SessionToken": "TOKEN",
        "Expiration": "2099-01-01T00:00:00+00:00",
    }
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"region": "us-east-1"},
    )

    result = write_default_credentials("dev")

    assert result is not None
    assert result["expiration"] == "2099-01-01T00:00:00+00:00"

    credentials_file = aws_dir / "credentials"
    assert credentials_file.exists()
    content = credentials_file.read_text()
    assert "[default]" in content
    assert "aws_access_key_id = AKIATEST" in content


@pytest.mark.unit
def test_write_default_credentials_without_session_token(tmp_path, mocker, monkeypatch):
    """Writes credentials file without aws_session_token when SessionToken is absent."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()

    creds = {
        "AccessKeyId": "AKIATEST2",
        "SecretAccessKey": "SECRET2",
        "Expiration": "2099-06-01T00:00:00+00:00",
    }
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config", return_value={"region": "us-east-1"})

    result = write_default_credentials("dev")

    assert result is not None
    content = (aws_dir / "credentials").read_text()
    assert "aws_session_token" not in content
    assert "aws_access_key_id = AKIATEST2" in content


@pytest.mark.unit
def test_write_default_credentials_without_region(tmp_path, mocker, monkeypatch):
    """Writes credentials file without region line when profile config has none."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()

    creds = {"AccessKeyId": "AKIATEST3", "SecretAccessKey": "SECRET3", "SessionToken": "TOK"}
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config", return_value=None)

    result = write_default_credentials("dev")

    assert result is not None
    content = (aws_dir / "credentials").read_text()
    assert "region" not in content
    assert "aws_access_key_id = AKIATEST3" in content


@pytest.mark.unit
def test_write_default_credentials_replaces_existing_default(tmp_path, mocker, monkeypatch):
    """Replaces an existing [default] section with fresh credentials."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "credentials").write_text("[default]\naws_access_key_id = OLD_KEY\n")

    creds = {"AccessKeyId": "NEW_KEY", "SecretAccessKey": "NEW_SECRET"}
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds)))
    mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config", return_value=None)

    result = write_default_credentials("dev")

    assert result is not None
    content = (aws_dir / "credentials").read_text()
    assert "OLD_KEY" not in content
    assert "NEW_KEY" in content


# ---------------------------------------------------------------------------
# get_sso_token_expiration — additional branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_sso_token_expiration_returns_none_on_url_mismatch(tmp_path, monkeypatch):
    """Returns None when no cache file matches the requested URL."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)

    from datetime import timedelta

    future = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_data = {"startUrl": "https://other.awsapps.com/start", "expiresAt": future}
    (cache_dir / "abc.json").write_text(json.dumps(cache_data))

    result = get_sso_token_expiration("https://example.awsapps.com/start")

    assert result is None


@pytest.mark.unit
def test_get_sso_token_expiration_returns_none_on_corrupt_json(tmp_path, monkeypatch):
    """Returns None when cache file contains invalid JSON."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "bad.json").write_text("not json at all")

    result = get_sso_token_expiration("https://example.awsapps.com/start")

    assert result is None


@pytest.mark.unit
def test_get_sso_token_expiration_returns_none_when_no_expires_at(tmp_path, monkeypatch):
    """Returns None when matching file has no expiresAt field."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)
    cache_data = {"startUrl": "https://example.awsapps.com/start"}
    (cache_dir / "abc.json").write_text(json.dumps(cache_data))

    result = get_sso_token_expiration("https://example.awsapps.com/start")

    assert result is None


# ---------------------------------------------------------------------------
# get_sso_cache_token — no expiresAt field branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_sso_cache_token_returns_none_when_no_expires_at(tmp_path, monkeypatch):
    """Returns None when matching file has no expiresAt field."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache_dir = tmp_path / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True)
    cache_data = {"startUrl": "https://example.awsapps.com/start", "accessToken": "tok"}
    (cache_dir / "abc.json").write_text(json.dumps(cache_data))

    result = get_sso_cache_token("https://example.awsapps.com/start")

    assert result is None


# ---------------------------------------------------------------------------
# write_default_credentials — error writing file (lines 127-129)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_default_credentials_returns_none_on_write_error(tmp_path, mocker, monkeypatch):
    """Returns None when an exception occurs while writing the credentials file (lines 127-129)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()

    creds = {
        "AccessKeyId": "AKIATEST",
        "SecretAccessKey": "SECRET",
        "SessionToken": "TOKEN",
        "Expiration": "2099-01-01T00:00:00+00:00",
    }
    mocker.patch("subprocess.run", return_value=mocker.MagicMock(returncode=0, stdout=json.dumps(creds)))
    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.get_profile_config",
        return_value={"region": "us-east-1"},
    )
    # Make the credentials file unwritable by patching open to raise on "a" mode
    original_open = open

    def patched_open(path, mode="r", **kwargs):
        if mode == "a":
            raise OSError("disk full")
        return original_open(path, mode, **kwargs)

    mocker.patch("builtins.open", side_effect=patched_open)

    result = write_default_credentials("dev")

    assert result is None
