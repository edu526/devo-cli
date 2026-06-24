"""Unit tests for cli_tool.commands.doctor.core.checks module."""

from unittest.mock import patch

import pytest

from cli_tool.commands.doctor.core.checks import (
    _check_aws_cli,
    _check_bedrock_config,
    _check_config,
    _check_devo_version,
    _check_git,
    _check_python,
    _check_releases_endpoint,
    run_checks,
)


@pytest.mark.unit
def test_check_python_ok():
    """Current Python (>= 3.12) is reported as ok."""
    result = _check_python()
    assert result["status"] == "ok"
    assert result["name"] == "Python version"


@pytest.mark.unit
def test_check_python_too_old():
    """Old Python versions produce error status with version detail."""
    with patch("cli_tool.commands.doctor.core.checks.sys") as mock_sys:
        mock_sys.version_info = type("V", (), {"major": 3, "minor": 8, "micro": 0})()
        result = _check_python()
    assert result["status"] == "error"
    assert "3.8.0" in result["detail"]


@pytest.mark.unit
def test_check_devo_version_ok():
    """Returns ok with v-prefixed detail when version is known."""
    with patch("cli_tool.commands.doctor.core.checks.get_current_version", return_value="3.11.0"):
        result = _check_devo_version()
    assert result["status"] == "ok"
    assert result["detail"] == "v3.11.0"


@pytest.mark.unit
def test_check_devo_version_unknown_is_warn():
    """An 'unknown' version produces a warning, not an error."""
    with patch("cli_tool.commands.doctor.core.checks.get_current_version", return_value="unknown"):
        result = _check_devo_version()
    assert result["status"] == "warn"


@pytest.mark.unit
def test_check_releases_endpoint_ok():
    """When API returns a version, status is ok with that version in the detail."""
    with patch("cli_tool.commands.doctor.core.checks.get_latest_version", return_value="3.11.0"):
        result = _check_releases_endpoint()
    assert result["status"] == "ok"
    assert "3.11.0" in result["detail"]


@pytest.mark.unit
def test_check_releases_endpoint_unreachable_is_warn():
    """API returning None produces a warn (network may be transient)."""
    with patch("cli_tool.commands.doctor.core.checks.get_latest_version", return_value=None):
        result = _check_releases_endpoint()
    assert result["status"] == "warn"


@pytest.mark.unit
def test_check_config_missing(tmp_path, mocker):
    """Missing config file is a warn (gets created on first run), not an error."""
    mocker.patch(
        "cli_tool.commands.doctor.core.checks.get_config_file",
        return_value=tmp_path / "does-not-exist.json",
    )
    result = _check_config()
    assert result["status"] == "warn"
    assert "missing" in result["detail"]


@pytest.mark.unit
def test_check_config_invalid_json(tmp_path, mocker):
    """Corrupted JSON in config is an error."""
    bad = tmp_path / "config.json"
    bad.write_text("{not valid json", encoding="utf-8")
    mocker.patch("cli_tool.commands.doctor.core.checks.get_config_file", return_value=bad)
    result = _check_config()
    assert result["status"] == "error"
    assert "invalid JSON" in result["detail"]


@pytest.mark.unit
def test_check_aws_cli_present(mocker):
    """When aws is on PATH, status is ok and detail is the path."""
    mocker.patch("cli_tool.commands.doctor.core.checks.shutil.which", return_value="/usr/bin/aws")
    result = _check_aws_cli()
    assert result["status"] == "ok"
    assert result["detail"] == "/usr/bin/aws"


@pytest.mark.unit
def test_check_aws_cli_missing(mocker):
    """When aws is not on PATH, status is warn with a hint about which commands need it."""
    mocker.patch("cli_tool.commands.doctor.core.checks.shutil.which", return_value=None)
    result = _check_aws_cli()
    assert result["status"] == "warn"
    assert "aws-login" in result["detail"]


@pytest.mark.unit
def test_check_git_present(mocker):
    """When git is on PATH, status is ok."""
    mocker.patch("cli_tool.commands.doctor.core.checks.shutil.which", return_value="/usr/bin/git")
    result = _check_git()
    assert result["status"] == "ok"


@pytest.mark.unit
def test_check_bedrock_config_ok(mocker):
    """Configured bedrock model_id and region produce ok status with both shown."""
    mocker.patch(
        "cli_tool.commands.doctor.core.checks.load_config",
        return_value={"bedrock": {"model_id": "anthropic.sonnet", "region": "us-east-1"}},
    )
    result = _check_bedrock_config()
    assert result["status"] == "ok"
    assert "anthropic.sonnet" in result["detail"]
    assert "us-east-1" in result["detail"]


@pytest.mark.unit
def test_check_bedrock_config_missing_region_is_error(mocker):
    """Missing region produces error (would break every Bedrock call)."""
    mocker.patch(
        "cli_tool.commands.doctor.core.checks.load_config",
        return_value={"bedrock": {"model_id": "anthropic.sonnet", "region": None}},
    )
    result = _check_bedrock_config()
    assert result["status"] == "error"


@pytest.mark.unit
def test_run_checks_returns_one_result_per_check():
    """run_checks returns a result per registered check; one bad check does not break the rest."""
    with patch(
        "cli_tool.commands.doctor.core.checks._check_python",
        return_value={"name": "Python version", "status": "ok", "detail": "3.12.0"},
    ):
        with patch(
            "cli_tool.commands.doctor.core.checks._check_devo_version",
            side_effect=RuntimeError("boom"),
        ):
            results = run_checks()
    assert len(results) >= 2
    py_result = next(r for r in results if r["name"] == "Python version")
    assert py_result["status"] == "ok"
    failed = next(r for r in results if r["status"] == "error")
    assert "boom" in failed["detail"]
