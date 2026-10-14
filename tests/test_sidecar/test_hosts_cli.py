"""Frozen-sidecar `-m cli_tool.cli` routing used by desktop UAC elevation."""

from unittest.mock import patch

import pytest

from cli_tool.sidecar import hosts_cli


def test_is_cli_invocation():
    assert hosts_cli.is_cli_invocation(["-m", "cli_tool.cli", "ssm", "hosts", "setup"])
    assert not hosts_cli.is_cli_invocation(["--port", "0"])
    assert not hosts_cli.is_cli_invocation([])


def _run_setup(argv):
    with (
        patch("cli_tool.commands.ssm.commands.hosts.setup.SSMConfigManager") as cfg,
        patch("cli_tool.commands.ssm.commands.hosts.setup._run_setup", return_value=([], [])) as setup,
    ):
        cfg.return_value.list_databases.return_value = {"db1": {}}
        cfg.return_value.load.return_value = {}
        with pytest.raises(SystemExit) as exc:
            hosts_cli.run(argv)
    return exc.value.code, setup


def test_run_dispatches_setup_with_db_names():
    code, setup = _run_setup(["-m", "cli_tool.cli", "ssm", "hosts", "setup", "db1"])

    assert code == 0
    setup.assert_called_once_with(["db1"])


def test_run_accepts_the_log_file_the_desktop_passes(tmp_path):
    """What the installed app runs elevated (hosts_command.rs):
    `devo-sidecar -m cli_tool.cli ssm hosts --log-file … setup -- <db names>`."""
    import logging

    log_file = tmp_path / "sidecar.log"
    try:
        code, setup = _run_setup(["-m", "cli_tool.cli", "ssm", "hosts", "--log-file", str(log_file), "setup", "--", "db1"])
    finally:
        hosts_logger = logging.getLogger("cli_tool.commands.ssm.commands.hosts")
        for handler in [h for h in hosts_logger.handlers if isinstance(h, logging.FileHandler)]:
            hosts_logger.removeHandler(handler)
            handler.close()

    assert code == 0
    setup.assert_called_once_with(["db1"])
