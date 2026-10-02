"""Frozen-sidecar `-m cli_tool.cli` routing used by desktop UAC elevation."""

from unittest.mock import patch

import pytest

from cli_tool.sidecar import hosts_cli


def test_is_cli_invocation():
    assert hosts_cli.is_cli_invocation(["-m", "cli_tool.cli", "ssm", "hosts", "setup"])
    assert not hosts_cli.is_cli_invocation(["--port", "0"])
    assert not hosts_cli.is_cli_invocation([])


def test_run_dispatches_setup_with_db_names():
    with (
        patch("cli_tool.commands.ssm.commands.hosts.setup.SSMConfigManager") as cfg,
        patch("cli_tool.commands.ssm.commands.hosts.setup.setup_databases", return_value=(["db1"], [])) as setup,
    ):
        cfg.return_value.list_databases.return_value = {"db1": {}}
        with pytest.raises(SystemExit) as exc:
            hosts_cli.run(["-m", "cli_tool.cli", "ssm", "hosts", "setup", "db1"])
    assert exc.value.code == 0
    setup.assert_called_once_with(["db1"])
