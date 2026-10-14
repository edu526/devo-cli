"""Pausing hostname forwarding, for every database or for one (CLI side)."""

import pytest

from cli_tool.commands.ssm.core import hostname_forwarding
from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import _build_threads
from cli_tool.commands.ssm.core.hosts_setup import setup_databases
from cli_tool.commands.ssm.utils import HostsFileLocked, HostsManager
from cli_tool.commands.ssm.utils.hosts_manager import describe_hosts_lock
from cli_tool.commands.ssm.utils.security_software import active_antivirus
from cli_tool.core.utils.config_manager import load_config, save_config

MARKER_START = HostsManager.MARKER_START
MARKER_END = HostsManager.MARKER_END


def _db(host, local_address="127.0.0.2", **extra):
    return {"bastion": "i-1", "host": host, "port": 5432, "region": "us-east-1", "local_address": local_address, "local_port": 5432, **extra}


def _hosts(*entries):
    return "\n".join([MARKER_START, *(f"{ip} {host}" for ip, host in entries), MARKER_END]) + "\n"


@pytest.fixture
def hosts_file(tmp_path, mocker):
    path = tmp_path / "hosts"
    path.write_text("127.0.0.1 localhost\n")
    mocker.patch("platform.system", return_value="Linux")  # no macOS loopback aliases unless a test asks
    mocker.patch.object(HostsManager, "get_hosts_file_path", staticmethod(lambda: path))
    mocker.patch.object(HostsManager, "_write_hosts", lambda self, content: path.write_text(content))
    return path


@pytest.mark.unit
class TestSwitches:
    def test_on_by_default(self):
        assert hostname_forwarding.is_enabled({}, {}) is True

    def test_a_database_follows_the_all_databases_setting(self):
        assert hostname_forwarding.is_enabled({"hostname_forwarding": False}, {}) is False

    def test_its_own_exception_wins_either_way(self):
        """With everything paused one can still be forwarded, and the other way around."""
        assert hostname_forwarding.is_enabled({"hostname_forwarding": False}, {"hostname_forwarding": True}) is True
        assert hostname_forwarding.is_enabled({}, {"hostname_forwarding": False}) is False

    def test_setting_one_stores_an_exception_only_when_it_differs(self):
        save_config({"ssm": {"databases": {"a": _db("a.rds")}}})
        cm = SSMConfigManager()

        cm.set_hostname_forwarding(False, "a")
        assert cm.get_database("a")["hostname_forwarding"] is False

        cm.set_hostname_forwarding(True, "a")  # same as for all: no exception
        assert "hostname_forwarding" not in cm.get_database("a")

    def test_setting_all_drops_every_exception(self):
        save_config({"ssm": {"databases": {"a": _db("a.rds", hostname_forwarding=True), "b": _db("b.rds", hostname_forwarding=False)}}})
        cm = SSMConfigManager()

        cm.set_hostname_forwarding(False)
        assert cm.load()["hostname_forwarding"] is False
        assert all("hostname_forwarding" not in db for db in cm.list_databases().values())

        cm.set_hostname_forwarding(True)
        assert "hostname_forwarding" not in load_config()["ssm"]  # on is the default

    def test_unknown_database_raises(self):
        save_config({"ssm": {"databases": {}}})
        with pytest.raises(KeyError):
            SSMConfigManager().set_hostname_forwarding(False, "nope")

    def test_add_database_keeps_an_exception(self):
        """PATCH /databases rebuilds the entry through add_database."""
        save_config({"ssm": {"databases": {}}})
        SSMConfigManager().add_database("a", "i-1", "a.rds", 5432, hostname_forwarding=False)

        assert SSMConfigManager().get_database("a")["hostname_forwarding"] is False


@pytest.mark.unit
class TestSetupSkipsPausedDatabases:
    def test_a_paused_database_gets_no_entry(self, hosts_file):
        save_config({"ssm": {"databases": {"a": _db("a.rds"), "b": _db("b.rds", "127.0.0.3", hostname_forwarding=False)}}})

        succeeded, failed = setup_databases()

        assert [s["name"] for s in succeeded] == ["a"]
        assert failed == []
        assert "b.rds" not in hosts_file.read_text()

    def test_with_everything_paused_only_the_exceptions_get_entries(self, hosts_file):
        save_config(
            {"ssm": {"hostname_forwarding": False, "databases": {"a": _db("a.rds", hostname_forwarding=True), "b": _db("b.rds", "127.0.0.3")}}}
        )

        succeeded, _failed = setup_databases()

        assert [s["name"] for s in succeeded] == ["a"]


@pytest.mark.unit
class TestRemoveEntry:
    def test_removes_only_the_exact_hostname(self, hosts_file):
        """Removing "db.rds" must not take "reader-db.rds" with it."""
        hosts_file.write_text(_hosts(("127.0.0.2", "db.rds"), ("127.0.0.3", "reader-db.rds")))

        HostsManager().remove_entry("db.rds")

        assert HostsManager().get_managed_entries() == [("127.0.0.3", "reader-db.rds")]

    def test_does_not_write_when_the_entry_is_not_there(self, hosts_file, mocker):
        """Writing needs elevation: the retry after an elevated removal must not ask again."""
        hosts_file.write_text(_hosts(("127.0.0.3", "other.rds")))
        write = mocker.patch.object(HostsManager, "_write_hosts")

        HostsManager().remove_entry("db.rds")

        write.assert_not_called()

    def test_macos_keeps_aliases_other_entries_still_use(self, hosts_file, mocker, monkeypatch):
        hosts_file.write_text(_hosts(("127.0.0.7", "a.rds"), ("127.0.0.7", "b.rds"), ("127.0.0.8", "c.rds")))
        mocker.patch("platform.system", return_value="Darwin")
        # the CLI (importing the sidecar's bootstrap sets it for the whole session)
        monkeypatch.delenv("DEVO_SIDECAR", raising=False)
        removed = mocker.patch.object(HostsManager, "_remove_loopback_alias_macos")

        HostsManager().remove_entry("a.rds")
        HostsManager().remove_entry("c.rds")

        assert [c.args[0] for c in removed.call_args_list] == ["127.0.0.8"]


@pytest.mark.unit
class TestMacosSidecarNeedsElevationBeforeWriting:
    """From the sidecar, removing a loopback alias always needs elevation. The
    file must be left untouched, or the elevated retry finds the entries gone
    and never removes the aliases."""

    @pytest.fixture(autouse=True)
    def macos_sidecar(self, hosts_file, mocker, monkeypatch):
        # after hosts_file, which patches Linux
        mocker.patch("platform.system", return_value="Darwin")
        monkeypatch.setenv("DEVO_SIDECAR", "1")

    def test_clear_all(self, hosts_file):
        before = _hosts(("127.0.0.2", "a.rds"))
        hosts_file.write_text(before)

        with pytest.raises(PermissionError):
            HostsManager().clear_all()
        assert hosts_file.read_text() == before

    def test_remove_entry(self, hosts_file):
        before = _hosts(("127.0.0.2", "a.rds"))
        hosts_file.write_text(before)

        with pytest.raises(PermissionError):
            HostsManager().remove_entry("a.rds")
        assert hosts_file.read_text() == before


@pytest.mark.unit
class TestConnectWithPausedForwarding:
    def test_paused_databases_connect_like_no_hosts(self, mocker):
        """Their hostname isn't in the hosts file on purpose: connect them on
        127.0.0.1 instead of skipping them as "Not in /etc/hosts"."""
        mocker.patch("cli_tool.commands.ssm.core.connection_runner._find_free_port", side_effect=lambda port: port)
        thread = mocker.patch("cli_tool.commands.ssm.core.connection_runner.threading.Thread")
        mocker.patch("cli_tool.commands.ssm.core.connection_runner.time.sleep")
        table = mocker.MagicMock()

        threads, _conflicts, missing = _build_threads({"a": _db("a.rds")}, False, set(), table, mocker.MagicMock(), no_hosts_for=frozenset({"a"}))

        assert len(threads) == 1 and missing == 0
        use_hostname_forwarding = thread.call_args.kwargs["args"][3]
        assert use_hostname_forwarding is False

    def test_connect_command_pauses_per_database_and_globally(self, mocker):
        from cli_tool.commands.ssm.commands.database import connect

        save_config({"ssm": {"databases": {"a": _db("a.rds"), "b": _db("b.rds", "127.0.0.3", hostname_forwarding=False)}}})
        mocker.patch.object(connect, "_validate_tokens", return_value=True)
        mocker.patch.object(connect, "HostsManager").return_value.get_managed_entries.return_value = []
        auto_setup = mocker.patch.object(connect, "_maybe_run_auto_setup", side_effect=lambda dbs, hosts, _no: hosts)
        build = mocker.patch.object(connect, "_build_threads", return_value=([], 0, 0))

        connect._connect_databases(SSMConfigManager().list_databases(), no_hosts=False)

        assert list(auto_setup.call_args.args[0]) == ["a"]  # setup is never offered for b
        assert build.call_args.kwargs["no_hosts_for"] == frozenset({"b"})

        SSMConfigManager().set_hostname_forwarding(False)
        connect._connect_databases(SSMConfigManager().list_databases(), no_hosts=False)

        assert build.call_args.kwargs["no_hosts_for"] == frozenset({"a", "b"})


@pytest.mark.unit
class TestElevatedCommandsReportWhy:
    """The desktop runs these elevated in a hidden window: their outcome has to
    reach sidecar.log, and the exit code has to say whether they worked."""

    @pytest.fixture
    def hosts_cli(self):
        import logging

        import click

        from cli_tool.commands.ssm.commands.hosts import register_hosts_commands

        @click.group()
        def ssm():
            pass

        register_hosts_commands(ssm)
        yield ssm
        hosts_logger = logging.getLogger("cli_tool.commands.ssm.commands.hosts")
        for handler in [h for h in hosts_logger.handlers if isinstance(h, logging.FileHandler)]:
            hosts_logger.removeHandler(handler)
            handler.close()

    def test_a_failure_is_logged_to_the_log_file_and_exits_1(self, hosts_cli, tmp_path, mocker):
        from click.testing import CliRunner

        mocker.patch.object(HostsManager, "clear_all", side_effect=PermissionError("locked by antivirus"))
        log_file = tmp_path / "sidecar.log"

        result = CliRunner().invoke(hosts_cli, ["hosts", "--log-file", str(log_file), "clear", "--yes"])

        assert result.exit_code == 1
        assert "locked by antivirus" in log_file.read_text(encoding="utf-8")

    def test_a_success_is_logged_too(self, hosts_cli, tmp_path, mocker):
        from click.testing import CliRunner

        mocker.patch.object(HostsManager, "clear_all")
        log_file = tmp_path / "sidecar.log"

        result = CliRunner().invoke(hosts_cli, ["hosts", "--log-file", str(log_file), "clear", "--yes"])

        assert result.exit_code == 0
        assert "Removed every Devo entry" in log_file.read_text(encoding="utf-8")

    def test_windows_denied_while_admin_is_a_locked_hosts_file(self, mocker):
        """ "Run your terminal as Administrator" is misleading when it already is."""
        mocker.patch("platform.system", return_value="Windows")
        mocker.patch("pathlib.Path.write_text", side_effect=PermissionError("denied"))
        mocker.patch("cli_tool.commands.ssm.utils.hosts_manager._is_windows_admin", return_value=True)
        mocker.patch("cli_tool.commands.ssm.utils.hosts_manager.describe_hosts_lock", return_value="Kaspersky is blocking it")

        with pytest.raises(HostsFileLocked, match="Kaspersky is blocking it"):
            HostsManager()._write_hosts("x")

    def test_a_locked_hosts_file_exits_with_its_own_code(self, hosts_cli, mocker):
        """The desktop only sees the exit code of the elevated command: 3 tells
        it to ask the sidecar why, instead of a generic failure."""
        from click.testing import CliRunner

        mocker.patch.object(HostsManager, "clear_all", side_effect=HostsFileLocked("Kaspersky is blocking it"))

        result = CliRunner().invoke(hosts_cli, ["hosts", "clear", "--yes"])

        assert result.exit_code == HostsFileLocked.exit_code == 3
        assert "Kaspersky is blocking it" in result.output

    def test_setup_exits_with_the_locked_code_and_no_run_as_admin_hint(self, hosts_cli, hosts_file, mocker):
        from click.testing import CliRunner

        save_config({"ssm": {"databases": {"a": _db("a.rds")}}})
        mocker.patch.object(HostsManager, "add_entry", side_effect=HostsFileLocked("Kaspersky is blocking it"))

        result = CliRunner().invoke(hosts_cli, ["hosts", "setup"])

        assert result.exit_code == 3
        assert "Kaspersky is blocking it" in result.output
        assert "run your terminal as Administrator" not in result.output


@pytest.mark.unit
class TestDescribeHostsLock:
    @pytest.fixture(autouse=True)
    def no_read_only_flag(self, mocker):
        self.stat = mocker.patch("cli_tool.commands.ssm.utils.hosts_manager.os.stat")
        self.stat.return_value.st_file_attributes = 0

    def test_names_the_active_antivirus(self, mocker):
        mocker.patch("cli_tool.commands.ssm.utils.security_software.active_antivirus", return_value=["Kaspersky"])

        message = describe_hosts_lock()

        assert message.startswith("Kaspersky is blocking changes to your hosts file")
        assert "Pause its protection" in message

    def test_falls_back_to_a_generic_reason(self, mocker):
        mocker.patch("cli_tool.commands.ssm.utils.security_software.active_antivirus", return_value=[])

        assert "usually an antivirus" in describe_hosts_lock()

    def test_a_read_only_file_says_so(self, mocker):
        import stat

        self.stat.return_value.st_file_attributes = stat.FILE_ATTRIBUTE_READONLY
        antivirus = mocker.patch("cli_tool.commands.ssm.utils.security_software.active_antivirus")

        assert "marked read-only" in describe_hosts_lock()
        antivirus.assert_not_called()


@pytest.mark.unit
class TestActiveAntivirus:
    @pytest.fixture(autouse=True)
    def windows(self, mocker):
        mocker.patch("platform.system", return_value="Windows")

    def _security_center(self, mocker, stdout):
        return mocker.patch(
            "cli_tool.commands.ssm.utils.security_software.subprocess.run",
            return_value=mocker.MagicMock(stdout=stdout),
        )

    def test_lists_only_products_whose_scanner_is_on(self, mocker):
        # Real values from a machine with Kaspersky on and Defender gone passive
        self._security_center(
            mocker,
            '[{"displayName":"Kaspersky","productState":266240},{"displayName":"Windows Defender","productState":393472}]',
        )

        assert active_antivirus() == ["Kaspersky"]

    def test_a_single_product_comes_as_an_object(self, mocker):
        self._security_center(mocker, '{"displayName":"Windows Defender","productState":397568}')

        assert active_antivirus() == ["Windows Defender"]

    def test_nothing_when_it_cannot_be_asked(self, mocker):
        mocker.patch("cli_tool.commands.ssm.utils.security_software.subprocess.run", side_effect=OSError("no powershell"))

        assert active_antivirus() == []

    def test_nothing_off_windows(self, mocker):
        mocker.patch("platform.system", return_value="Linux")
        run = self._security_center(mocker, "[]")

        assert active_antivirus() == []
        run.assert_not_called()


@pytest.mark.unit
class TestLoopbackIpsAreNotShared:
    """Each database gets its own 127.0.0.X. A paused database has no hosts
    entry, but its IP comes back with it: it must not look free."""

    def test_setup_skips_the_ip_of_a_paused_database(self, hosts_file):
        save_config(
            {
                "ssm": {
                    "databases": {
                        "paused": _db("paused.rds", "127.0.0.2", hostname_forwarding=False),
                        "new": _db("new.rds", "127.0.0.1"),  # never set up
                    }
                }
            }
        )

        succeeded, _failed = setup_databases()

        assert [(s["name"], s["ip"]) for s in succeeded] == [("new", "127.0.0.3")]

    def test_two_new_databases_in_one_setup_get_different_ips(self, hosts_file):
        save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.1"), "b": _db("b.rds", "127.0.0.1")}}})

        succeeded, _failed = setup_databases()

        assert sorted(s["ip"] for s in succeeded) == ["127.0.0.2", "127.0.0.3"]

    def test_hosts_add_skips_the_ip_of_a_paused_database(self, hosts_file):
        from click.testing import CliRunner

        from cli_tool.commands.ssm.commands.hosts.add import hosts_add_single

        save_config({"ssm": {"databases": {"paused": _db("paused.rds", "127.0.0.2", hostname_forwarding=False), "new": _db("new.rds", "127.0.0.1")}}})

        result = CliRunner().invoke(hosts_add_single, ["new"])

        assert result.exit_code == 0
        assert SSMConfigManager().get_database("new")["local_address"] == "127.0.0.3"


@pytest.mark.unit
class TestHostsSync:
    """`devo ssm hosts sync`: the hosts file ends up matching the databases."""

    def test_adds_what_is_missing_and_removes_what_no_database_forwards(self, hosts_file):
        from cli_tool.commands.ssm.core.hosts_setup import sync_databases

        save_config(
            {
                "ssm": {
                    "databases": {
                        "kept": _db("kept.rds", "127.0.0.2"),
                        "missing": _db("missing.rds", "127.0.0.3"),
                        "paused": _db("paused.rds", "127.0.0.4", hostname_forwarding=False),
                    }
                }
            }
        )
        hosts_file.write_text(
            "127.0.0.1 localhost\n" + _hosts(("127.0.0.2", "kept.rds"), ("127.0.0.4", "paused.rds"), ("127.0.0.9", "deleted-db.rds"))
        )

        succeeded, failed, removed = sync_databases()

        assert failed == []
        assert removed == ["deleted-db.rds", "paused.rds"]
        assert sorted(HostsManager().get_managed_entries()) == [("127.0.0.2", "kept.rds"), ("127.0.0.3", "missing.rds")]
        assert "127.0.0.1 localhost" in hosts_file.read_text()  # outside Devo's block: untouched
        assert {s["name"] for s in succeeded} == {"kept", "missing"}

    def test_a_database_whose_host_changed_leaves_no_old_entry(self, hosts_file):
        from cli_tool.commands.ssm.core.hosts_setup import sync_databases

        save_config({"ssm": {"databases": {"a": _db("new-host.rds", "127.0.0.2")}}})
        hosts_file.write_text(_hosts(("127.0.0.2", "old-host.rds")))

        sync_databases()

        assert HostsManager().get_managed_entries() == [("127.0.0.2", "new-host.rds")]

    def test_command_exit_codes(self, hosts_file, mocker):
        from click.testing import CliRunner

        from cli_tool.commands.ssm.commands.hosts.sync import hosts_sync

        save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.2")}}})
        hosts_file.write_text(_hosts(("127.0.0.9", "stale.rds")))

        ok = CliRunner().invoke(hosts_sync)
        assert ok.exit_code == 0 and "removed stale stale.rds" in ok.output

        hosts_file.write_text(_hosts(("127.0.0.9", "stale.rds")))
        mocker.patch.object(HostsManager, "remove_entry", side_effect=HostsFileLocked("Kaspersky is blocking it"))
        locked = CliRunner().invoke(hosts_sync)
        assert locked.exit_code == 3 and "Kaspersky is blocking it" in locked.output

        mocker.patch.object(HostsManager, "remove_entry", side_effect=PermissionError("denied"))
        denied = CliRunner().invoke(hosts_sync)
        assert denied.exit_code == 1
