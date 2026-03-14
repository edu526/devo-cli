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
