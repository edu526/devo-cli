"""Tests for HostsManager — /etc/hosts management for SSM connections."""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.ssm.utils.hosts_manager import HostsManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MARKER_START = HostsManager.MARKER_START
MARKER_END = HostsManager.MARKER_END


def _hosts_with_entries(*entries):
    """Build a fake /etc/hosts content with managed entries."""
    lines = [MARKER_START]
    for ip, host in entries:
        lines.append(f"{ip} {host}")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# get_hosts_file_path
# ---------------------------------------------------------------------------


def test_get_hosts_file_path_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert HostsManager.get_hosts_file_path() == pytest.importorskip("pathlib").Path("/etc/hosts")


def test_get_hosts_file_path_windows(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr("platform.system", lambda: "Windows")
    path = HostsManager.get_hosts_file_path()
    assert "Windows" in str(path) or "drivers" in str(path)


def test_get_hosts_file_path_macos(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert HostsManager.get_hosts_file_path() == Path("/etc/hosts")


# ---------------------------------------------------------------------------
# _validate_ip
# ---------------------------------------------------------------------------


def test_validate_ip_valid_ipv4():
    HostsManager._validate_ip("192.168.1.1")  # should not raise


def test_validate_ip_valid_ipv6():
    HostsManager._validate_ip("::1")


def test_validate_ip_valid_loopback():
    HostsManager._validate_ip("127.0.0.2")


def test_validate_ip_invalid_raises():
    with pytest.raises(ValueError, match="Invalid IP"):
        HostsManager._validate_ip("not-an-ip")


def test_validate_ip_empty_raises():
    with pytest.raises(ValueError):
        HostsManager._validate_ip("")


# ---------------------------------------------------------------------------
# _validate_hostname
# ---------------------------------------------------------------------------


def test_validate_hostname_valid():
    HostsManager._validate_hostname("myhost.example.com")


def test_validate_hostname_simple():
    HostsManager._validate_hostname("myhost")


def test_validate_hostname_with_numbers():
    HostsManager._validate_hostname("host123")


def test_validate_hostname_invalid_path_traversal():
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        HostsManager._validate_hostname("../etc/passwd")


def test_validate_hostname_with_space():
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        HostsManager._validate_hostname("my host")


def test_validate_hostname_empty():
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        HostsManager._validate_hostname("")


def test_validate_hostname_with_slash():
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        HostsManager._validate_hostname("host/name")


# ---------------------------------------------------------------------------
# get_managed_entries
# ---------------------------------------------------------------------------


def test_get_managed_entries_no_section(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = "127.0.0.1 localhost\n"
    entries = manager.get_managed_entries()
    assert entries == []


def test_get_managed_entries_with_entries(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = _hosts_with_entries(
        ("127.0.0.2", "db.local"),
        ("127.0.0.3", "api.local"),
    )
    entries = manager.get_managed_entries()
    assert ("127.0.0.2", "db.local") in entries
    assert ("127.0.0.3", "api.local") in entries


def test_get_managed_entries_file_not_exists(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = False
    assert manager.get_managed_entries() == []


def test_get_managed_entries_ignores_comments():
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    content = f"{MARKER_START}\n# this is a comment\n127.0.0.2 db.local\n{MARKER_END}\n"
    manager.HOSTS_FILE.read_text.return_value = content
    entries = manager.get_managed_entries()
    assert len(entries) == 1
    assert ("127.0.0.2", "db.local") in entries


# ---------------------------------------------------------------------------
# _filter_hostname_from_lines
# ---------------------------------------------------------------------------


def test_filter_hostname_removes_matching_line():
    manager = HostsManager.__new__(HostsManager)
    lines = [
        MARKER_START,
        "127.0.0.2 db.local",
        "127.0.0.3 api.local",
        MARKER_END,
    ]
    filtered, removed = manager._filter_hostname_from_lines(lines, "db.local")
    assert "127.0.0.2 db.local" not in filtered
    assert any("api.local" in line for line in filtered)
    assert "127.0.0.2" in removed


def test_filter_hostname_no_match_keeps_all():
    manager = HostsManager.__new__(HostsManager)
    lines = [MARKER_START, "127.0.0.2 db.local", MARKER_END]
    filtered, removed = manager._filter_hostname_from_lines(lines, "nonexistent.local")
    assert filtered == lines
    assert removed == []


def test_filter_hostname_outside_managed_section_not_removed():
    manager = HostsManager.__new__(HostsManager)
    lines = ["127.0.0.2 db.local", MARKER_START, "127.0.0.3 api.local", MARKER_END]
    filtered, removed = manager._filter_hostname_from_lines(lines, "db.local")
    # Line outside managed section should be preserved
    assert "127.0.0.2 db.local" in filtered


# ---------------------------------------------------------------------------
# get_next_loopback_ip
# ---------------------------------------------------------------------------


def test_get_next_loopback_ip_empty_entries():
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = _hosts_with_entries()
    ip = manager.get_next_loopback_ip()
    assert ip == "127.0.0.2"


def test_get_next_loopback_ip_skips_used():
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = _hosts_with_entries(
        ("127.0.0.2", "a.local"),
        ("127.0.0.3", "b.local"),
    )
    ip = manager.get_next_loopback_ip()
    assert ip == "127.0.0.4"


def test_get_next_loopback_ip_raises_when_exhausted():
    manager = HostsManager.__new__(HostsManager)
    # Mock all IPs 127.0.0.2-254 as used
    all_entries = [(f"127.0.0.{i}", f"host{i}.local") for i in range(2, 255)]
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = _hosts_with_entries(*all_entries)
    with pytest.raises(RuntimeError, match="No available loopback IPs"):
        manager.get_next_loopback_ip()


# ---------------------------------------------------------------------------
# add_entry
# ---------------------------------------------------------------------------


def test_add_entry_new_creates_section_and_adds(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = False
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: "127.0.0.1 localhost\n")
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    monkeypatch.setattr("platform.system", lambda: "Linux")

    manager.add_entry("127.0.0.2", "db.local")

    assert written
    assert "db.local" in written[-1]
    assert "127.0.0.2" in written[-1]


def test_add_entry_already_exists_correct_ip(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.2", "db.local"))
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content
    monkeypatch.setattr("platform.system", lambda: "Linux")

    manager.add_entry("127.0.0.2", "db.local")
    # No write should have occurred since entry is already correct
    assert not written


def test_add_entry_invalid_ip_raises():
    manager = HostsManager.__new__(HostsManager)
    with pytest.raises(ValueError, match="Invalid IP"):
        manager.add_entry("not-an-ip", "db.local")


def test_add_entry_invalid_hostname_raises():
    manager = HostsManager.__new__(HostsManager)
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        manager.add_entry("127.0.0.2", "../etc/passwd")


# ---------------------------------------------------------------------------
# remove_entry
# ---------------------------------------------------------------------------


def test_remove_entry_removes_existing(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.2", "db.local"), ("127.0.0.3", "api.local"))
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    monkeypatch.setattr("platform.system", lambda: "Linux")

    manager.remove_entry("db.local")

    assert written
    assert "db.local" not in written[-1]
    assert "api.local" in written[-1]


def test_remove_entry_no_managed_section_is_noop(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: "127.0.0.1 localhost\n")
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))

    manager.remove_entry("db.local")
    assert not written


def test_remove_entry_invalid_hostname_raises():
    manager = HostsManager.__new__(HostsManager)
    with pytest.raises(ValueError, match="Invalid or unsafe hostname"):
        manager.remove_entry("bad/host")


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------


def test_clear_all_removes_managed_section(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = "127.0.0.1 localhost\n" + _hosts_with_entries(("127.0.0.2", "db.local"))
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content
    monkeypatch.setattr("platform.system", lambda: "Linux")

    manager.clear_all()

    assert written
    assert MARKER_START not in written[-1]
    assert "localhost" in written[-1]


def test_clear_all_no_section_is_noop(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: "127.0.0.1 localhost\n")
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))

    manager.clear_all()
    assert not written


# ---------------------------------------------------------------------------
# _update_existing_entry
# ---------------------------------------------------------------------------


def test_update_existing_entry_correct_ip_returns_true(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.2", "db.local"))
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content

    result = manager._update_existing_entry("127.0.0.2", "db.local")
    assert result is True


def test_update_existing_entry_wrong_ip_removes_and_returns_false(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.2", "db.local"))
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content
    removed = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: removed.append(c))
    monkeypatch.setattr("platform.system", lambda: "Linux")

    result = manager._update_existing_entry("127.0.0.5", "db.local")
    assert result is False
    assert removed  # remove_entry was called


def test_update_existing_entry_not_found_returns_false(monkeypatch):
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.2", "db.local"))
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content

    result = manager._update_existing_entry("127.0.0.9", "nonexistent.local")
    assert result is False


# ---------------------------------------------------------------------------
# get_managed_entries — missing markers returns [] (line 51)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_managed_entries_marker_start_present_but_end_missing():
    """Returns [] when MARKER_START is present but MARKER_END is absent (line 51)."""
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    # Content contains MARKER_START but not MARKER_END
    # NOTE: get_managed_entries uses HOSTS_FILE.read_text() directly (not _read_hosts())
    content = f"{MARKER_START}\n127.0.0.2 db.local\n"
    manager.HOSTS_FILE.read_text.return_value = content

    entries = manager.get_managed_entries()

    assert entries == []


# ---------------------------------------------------------------------------
# add_entry — macOS loopback alias configuration (line 97)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_add_entry_darwin_loopback_calls_configure_alias(monkeypatch):
    """add_entry calls _configure_loopback_alias_macos on Darwin for loopback IPs != 127.0.0.1 (line 97)."""
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = False
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: "127.0.0.1 localhost\n")
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    configure_calls = []
    monkeypatch.setattr(manager, "_configure_loopback_alias_macos", lambda ip: configure_calls.append(ip))

    manager.add_entry("127.0.0.5", "myhost.local")

    assert "127.0.0.5" in configure_calls


@pytest.mark.unit
def test_add_entry_darwin_standard_localhost_no_alias(monkeypatch):
    """add_entry does NOT call _configure_loopback_alias_macos for 127.0.0.1 on Darwin."""
    manager = HostsManager.__new__(HostsManager)
    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = False
    written = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: "127.0.0.1 localhost\n")
    monkeypatch.setattr(manager, "_write_hosts", lambda c: written.append(c))
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    configure_calls = []
    monkeypatch.setattr(manager, "_configure_loopback_alias_macos", lambda ip: configure_calls.append(ip))

    manager.add_entry("127.0.0.1", "localhost")

    assert configure_calls == []


# ---------------------------------------------------------------------------
# remove_entry — macOS loopback alias removal (lines 154-156)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_remove_entry_darwin_calls_remove_loopback_alias(monkeypatch):
    """remove_entry calls _remove_loopback_alias_macos for loopback IPs on Darwin (lines 154-156)."""
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.5", "myhost.local"))
    removed_ips = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: None)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(manager, "_remove_loopback_alias_macos", lambda ip: removed_ips.append(ip))

    manager.remove_entry("myhost.local")

    assert "127.0.0.5" in removed_ips


@pytest.mark.unit
def test_remove_entry_darwin_skips_standard_localhost(monkeypatch):
    """remove_entry does not call _remove_loopback_alias_macos for 127.0.0.1 on Darwin."""
    manager = HostsManager.__new__(HostsManager)
    content = _hosts_with_entries(("127.0.0.1", "localhost"))
    removed_ips = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: None)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(manager, "_remove_loopback_alias_macos", lambda ip: removed_ips.append(ip))

    manager.remove_entry("localhost")

    assert removed_ips == []


# ---------------------------------------------------------------------------
# clear_all — macOS loopback alias removal (lines 180-182)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_clear_all_darwin_removes_loopback_aliases(monkeypatch):
    """clear_all calls _remove_loopback_alias_macos for loopback IPs on Darwin (lines 180-182)."""
    manager = HostsManager.__new__(HostsManager)
    content = "127.0.0.1 localhost\n" + _hosts_with_entries(
        ("127.0.0.2", "db.local"),
        ("127.0.0.3", "api.local"),
    )

    manager.HOSTS_FILE = MagicMock()
    manager.HOSTS_FILE.exists.return_value = True
    manager.HOSTS_FILE.read_text.return_value = content

    removed_ips = []

    monkeypatch.setattr(manager, "_read_hosts", lambda: content)
    monkeypatch.setattr(manager, "_write_hosts", lambda c: None)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(manager, "_remove_loopback_alias_macos", lambda ip: removed_ips.append(ip))

    manager.clear_all()

    assert "127.0.0.2" in removed_ips
    assert "127.0.0.3" in removed_ips


# ---------------------------------------------------------------------------
# _write_hosts — Windows path (lines 197-209)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_hosts_windows_writes_file(monkeypatch, tmp_path):
    """_write_hosts writes directly to the hosts file on Windows (lines 197-209)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    fake_hosts = tmp_path / "hosts"
    fake_hosts.write_text("original content")

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("cli_tool.commands.ssm.utils.hosts_manager.HostsManager.WINDOWS_HOSTS_FILE", str(fake_hosts))

    manager._write_hosts("new content")

    assert fake_hosts.read_text() == "new content"


@pytest.mark.unit
def test_write_hosts_windows_raises_permission_error(monkeypatch, tmp_path):
    """_write_hosts re-raises PermissionError with instructions on Windows (lines 203-209)."""
    from pathlib import Path

    manager = HostsManager.__new__(HostsManager)

    monkeypatch.setattr("platform.system", lambda: "Windows")

    mock_path_cls = MagicMock()
    mock_path_instance = MagicMock()
    mock_path_instance.write_text.side_effect = PermissionError("Access denied")
    mock_path_cls.return_value = mock_path_instance

    with patch("cli_tool.commands.ssm.utils.hosts_manager.Path", mock_path_cls):
        with pytest.raises(PermissionError, match="Permission denied"):
            manager._write_hosts("content")


# ---------------------------------------------------------------------------
# _write_hosts — Unix path (lines 210-222)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_hosts_unix_uses_sudo_tee(monkeypatch):
    """_write_hosts uses sudo tee on Linux/macOS (lines 210-222)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")

    with patch("cli_tool.commands.ssm.utils.hosts_manager.subprocess.Popen", return_value=mock_process) as mock_popen:
        manager._write_hosts("new content")

    cmd = mock_popen.call_args[0][0]
    assert "sudo" in cmd
    assert "tee" in cmd
    mock_process.communicate.assert_called_once_with(input=b"new content")


@pytest.mark.unit
def test_write_hosts_unix_raises_on_nonzero_return(monkeypatch):
    """_write_hosts raises OSError when sudo tee exits non-zero (lines 221-222)."""
    manager = HostsManager.__new__(HostsManager)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (b"", b"tee: permission denied")

    with patch("cli_tool.commands.ssm.utils.hosts_manager.subprocess.Popen", return_value=mock_process):
        with pytest.raises(OSError, match="Failed to write hosts file"):
            manager._write_hosts("new content")


# ---------------------------------------------------------------------------
# _configure_loopback_alias_macos (lines 239-261)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_loopback_alias_macos_already_configured(monkeypatch):
    """_configure_loopback_alias_macos returns early when alias already exists (lines 248-251)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    mock_result = MagicMock()
    mock_result.stdout = "inet 127.0.0.5 netmask 0xff000000"

    with patch("rich.console.Console"):
        with patch("cli_tool.commands.ssm.utils.hosts_manager.subprocess.run", return_value=mock_result) as mock_run:
            manager._configure_loopback_alias_macos("127.0.0.5")

    # Only the check call; no alias-add call
    assert mock_run.call_count == 1


@pytest.mark.unit
def test_configure_loopback_alias_macos_adds_new_alias(monkeypatch):
    """_configure_loopback_alias_macos runs sudo ifconfig alias when not yet configured (lines 255-258)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    mock_check = MagicMock()
    mock_check.stdout = "inet 127.0.0.1 netmask 0xff000000"  # 127.0.0.5 not present
    mock_add = MagicMock()

    with patch("rich.console.Console"):
        with patch(
            "cli_tool.commands.ssm.utils.hosts_manager.subprocess.run",
            side_effect=[mock_check, mock_add],
        ) as mock_run:
            manager._configure_loopback_alias_macos("127.0.0.5")

    assert mock_run.call_count == 2
    add_cmd = mock_run.call_args_list[1][0][0]
    assert "alias" in add_cmd


@pytest.mark.unit
def test_configure_loopback_alias_macos_raises_on_add_failure():
    """_configure_loopback_alias_macos raises OSError when sudo ifconfig fails (lines 259-261)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    mock_check = MagicMock()
    mock_check.stdout = "inet 127.0.0.1 netmask 0xff000000"

    add_error = subprocess.CalledProcessError(1, "sudo")
    add_error.stderr = "Operation not permitted"

    with patch("rich.console.Console"):
        with patch(
            "cli_tool.commands.ssm.utils.hosts_manager.subprocess.run",
            side_effect=[mock_check, add_error],
        ):
            with pytest.raises(OSError, match="Failed to configure loopback alias"):
                manager._configure_loopback_alias_macos("127.0.0.5")


@pytest.mark.unit
def test_configure_loopback_alias_macos_invalid_ip_raises():
    """_configure_loopback_alias_macos raises ValueError for non-loopback IP (lines 242-243)."""
    manager = HostsManager.__new__(HostsManager)

    with patch("rich.console.Console"):
        with pytest.raises(ValueError, match="Invalid loopback IP address"):
            manager._configure_loopback_alias_macos("192.168.1.1")


@pytest.mark.unit
def test_configure_loopback_alias_macos_check_raises_continues_to_add():
    """CalledProcessError during ifconfig check is swallowed and alias-add still proceeds (lines 252-253)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    check_error = subprocess.CalledProcessError(1, "ifconfig")
    add_success = MagicMock()

    with patch("rich.console.Console"):
        with patch(
            "cli_tool.commands.ssm.utils.hosts_manager.subprocess.run",
            side_effect=[check_error, add_success],
        ) as mock_run:
            manager._configure_loopback_alias_macos("127.0.0.5")

    assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# _remove_loopback_alias_macos (lines 265-275)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_remove_loopback_alias_macos_ip_not_configured_returns_early():
    """_remove_loopback_alias_macos returns without action when IP not in lo0 (lines 268-269)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    mock_result = MagicMock()
    mock_result.stdout = "inet 127.0.0.1 netmask 0xff000000"  # 127.0.0.5 NOT present

    with patch("cli_tool.commands.ssm.utils.hosts_manager.subprocess.run", return_value=mock_result) as mock_run:
        manager._remove_loopback_alias_macos("127.0.0.5")

    # Only the check call; no remove call
    assert mock_run.call_count == 1


@pytest.mark.unit
def test_remove_loopback_alias_macos_removes_existing_alias():
    """_remove_loopback_alias_macos calls sudo ifconfig -alias when IP is configured (lines 271-272)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    mock_check = MagicMock()
    mock_check.stdout = "inet 127.0.0.5 netmask 0xff000000"
    mock_remove = MagicMock()

    with patch(
        "cli_tool.commands.ssm.utils.hosts_manager.subprocess.run",
        side_effect=[mock_check, mock_remove],
    ) as mock_run:
        manager._remove_loopback_alias_macos("127.0.0.5")

    assert mock_run.call_count == 2
    remove_cmd = mock_run.call_args_list[1][0][0]
    assert "-alias" in remove_cmd


@pytest.mark.unit
def test_remove_loopback_alias_macos_ignores_errors():
    """_remove_loopback_alias_macos silently ignores CalledProcessError (lines 273-275)."""
    import subprocess

    manager = HostsManager.__new__(HostsManager)
    error = subprocess.CalledProcessError(1, "ifconfig")

    with patch("cli_tool.commands.ssm.utils.hosts_manager.subprocess.run", side_effect=error):
        # Should not raise
        manager._remove_loopback_alias_macos("127.0.0.5")


@pytest.mark.unit
def test_read_hosts_returns_empty_when_file_missing(tmp_path):
    """_read_hosts returns '' when hosts file does not exist (lines 186-188)."""
    manager = HostsManager.__new__(HostsManager)
    missing_path = tmp_path / "hosts"
    manager.get_hosts_file_path = lambda: missing_path

    result = manager._read_hosts()

    assert result == ""


@pytest.mark.unit
def test_read_hosts_returns_content_when_file_exists(tmp_path):
    """_read_hosts returns file content when hosts file exists (lines 186-189)."""
    manager = HostsManager.__new__(HostsManager)
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("127.0.0.1 localhost\n::1 localhost\n")
    manager.get_hosts_file_path = lambda: hosts_file

    result = manager._read_hosts()

    assert "127.0.0.1 localhost" in result
