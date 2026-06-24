"""Unit tests for cli_tool.commands.doctor.commands.doctor module."""

import pytest
from click.testing import CliRunner

from cli_tool.commands.doctor.commands.doctor import doctor


@pytest.mark.unit
def test_doctor_renders_table_and_exits_zero_when_all_ok(mocker):
    """All ok checks: exit 0, summary shows 'N ok'."""
    mocker.patch(
        "cli_tool.commands.doctor.commands.doctor.run_checks",
        return_value=[
            {"name": "Python version", "status": "ok", "detail": "3.12.0"},
            {"name": "Git", "status": "ok", "detail": "/usr/bin/git"},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(doctor, [])

    assert result.exit_code == 0
    assert "Python version" in result.output
    assert "Git" in result.output
    assert "2 ok" in result.output


@pytest.mark.unit
def test_doctor_exits_one_when_any_check_fails(mocker):
    """Any 'error' status causes non-zero exit (CI-friendly)."""
    mocker.patch(
        "cli_tool.commands.doctor.commands.doctor.run_checks",
        return_value=[
            {"name": "AWS CLI", "status": "ok", "detail": "/usr/bin/aws"},
            {"name": "Bedrock config", "status": "error", "detail": "missing model_id"},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(doctor, [])

    assert result.exit_code == 1
    assert "1 failure" in result.output


@pytest.mark.unit
def test_doctor_warns_counted_in_summary(mocker):
    """Warnings appear in the summary line alongside ok count."""
    mocker.patch(
        "cli_tool.commands.doctor.commands.doctor.run_checks",
        return_value=[
            {"name": "Python version", "status": "ok", "detail": "3.12.0"},
            {"name": "Git", "status": "warn", "detail": "not installed"},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(doctor, [])

    assert result.exit_code == 0
    assert "1 warning" in result.output
