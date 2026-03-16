"""
Unit tests for cli_tool.commands.ssm.core.port_forwarder module.

Tests cover PortForwarder class methods on Linux/macOS/Windows with mocked
subprocess calls to avoid any real system commands.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.ssm.core.port_forwarder import PortForwarder

# ============================================================================
# Helpers
# ============================================================================


def _make_forwarder(system="Linux"):
    """Return a PortForwarder with a mocked platform.system."""
    with patch("cli_tool.commands.ssm.core.port_forwarder.platform.system", return_value=system):
        pf = PortForwarder()
    return pf


# ============================================================================
# __init__
# ============================================================================


@pytest.mark.unit
def test_port_forwarder_init_linux():
    """PortForwarder initialises correctly on Linux."""
    pf = _make_forwarder("Linux")
    assert pf.system == "Linux"
    assert pf.processes == {}


@pytest.mark.unit
def test_port_forwarder_init_windows():
    """PortForwarder initialises correctly on Windows."""
    pf = _make_forwarder("Windows")
    assert pf.system == "Windows"


@pytest.mark.unit
def test_port_forwarder_init_darwin():
    """PortForwarder initialises correctly on macOS."""
    pf = _make_forwarder("Darwin")
    assert pf.system == "Darwin"


# ============================================================================
# _is_command_available
# ============================================================================


@pytest.mark.unit
def test_is_command_available_found(mocker):
    """Returns True when the command exists."""
    pf = _make_forwarder("Linux")
    mocker.patch("subprocess.run")  # returncode not checked, just no exception
    result = pf._is_command_available("socat")
    assert result is True


@pytest.mark.unit
def test_is_command_available_not_found(mocker):
    """Returns False when the command is not found (CalledProcessError)."""
    pf = _make_forwarder("Linux")
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "which"))
    result = pf._is_command_available("socat")
    assert result is False


@pytest.mark.unit
def test_is_command_available_file_not_found(mocker):
    """Returns False when which/where itself is not found."""
    pf = _make_forwarder("Linux")
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)
    result = pf._is_command_available("socat")
    assert result is False


@pytest.mark.unit
def test_is_command_available_uses_where_on_windows(mocker):
    """Uses 'where' command on Windows."""
    pf = _make_forwarder("Windows")
    mock_run = mocker.patch("subprocess.run")
    pf._is_command_available("socat")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "where"


# ============================================================================
# start_forward — Unix path
# ============================================================================


@pytest.mark.unit
def test_start_forward_unix_success(mocker):
    """Returns process PID when socat starts successfully on Linux."""
    pf = _make_forwarder("Linux")
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.poll.return_value = None  # Still running
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    mocker.patch("time.sleep")

    pid = pf.start_forward("127.0.0.2", 5432, 15432)

    assert pid == 1234
    assert "127.0.0.2:5432" in pf.processes


@pytest.mark.unit
def test_start_forward_unix_kills_orphaned_socat_before_start(mocker):
    """Calls _kill_orphaned_socat before starting socat to clear stale processes."""
    pf = _make_forwarder("Linux")
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.poll.return_value = None
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mock_kill = mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    mocker.patch("time.sleep")

    pf.start_forward("127.0.0.2", 5432, 15432)

    mock_kill.assert_called_once_with("127.0.0.2", 5432)


@pytest.mark.unit
def test_start_forward_unix_socat_not_installed(mocker):
    """Raises FileNotFoundError when socat is not installed."""
    pf = _make_forwarder("Linux")
    mocker.patch.object(pf, "_is_command_available", return_value=False)
    mocker.patch.object(pf, "_kill_orphaned_socat")

    with pytest.raises(FileNotFoundError, match="socat is not installed"):
        pf.start_forward("127.0.0.2", 5432, 15432)


@pytest.mark.unit
def test_start_forward_unix_socat_dies_immediately(mocker):
    """Raises RuntimeError when socat exits immediately after start."""
    pf = _make_forwarder("Linux")
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Process exited immediately
    mock_proc.communicate.return_value = (b"", b"bind error")
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    mocker.patch("time.sleep")

    with pytest.raises(RuntimeError, match="socat failed to start"):
        pf.start_forward("127.0.0.2", 5432, 15432)


@pytest.mark.unit
def test_start_forward_unix_stops_existing_before_restart(mocker):
    """Stops an existing forward on the same key before starting a new one."""
    pf = _make_forwarder("Linux")
    # Pre-populate with an existing process
    existing_proc = MagicMock()
    pf.processes["127.0.0.2:5432"] = existing_proc

    mock_new_proc = MagicMock()
    mock_new_proc.pid = 9999
    mock_new_proc.poll.return_value = None
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_new_proc)
    mocker.patch("time.sleep")

    pf.start_forward("127.0.0.2", 5432, 15432)

    existing_proc.terminate.assert_called_once()


# ============================================================================
# start_forward — macOS with loopback alias
# ============================================================================


@pytest.mark.unit
def test_start_forward_darwin_ensures_loopback_alias(mocker):
    """On Darwin, calls _ensure_loopback_alias_macos for loopback IPs."""
    pf = _make_forwarder("Darwin")
    mock_proc = MagicMock()
    mock_proc.pid = 5555
    mock_proc.poll.return_value = None
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    mocker.patch("time.sleep")
    mock_alias = mocker.patch.object(pf, "_ensure_loopback_alias_macos")

    pf.start_forward("127.0.0.5", 5432, 15432)

    mock_alias.assert_called_once_with("127.0.0.5")


@pytest.mark.unit
def test_start_forward_darwin_skips_loopback_for_standard_localhost(mocker):
    """On Darwin, does NOT call _ensure_loopback_alias_macos for 127.0.0.1."""
    pf = _make_forwarder("Darwin")
    mock_proc = MagicMock()
    mock_proc.pid = 5555
    mock_proc.poll.return_value = None
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    mocker.patch("time.sleep")
    mock_alias = mocker.patch.object(pf, "_ensure_loopback_alias_macos")

    pf.start_forward("127.0.0.1", 5432, 15432)

    mock_alias.assert_not_called()


# ============================================================================
# start_forward — Windows path
# ============================================================================


@pytest.mark.unit
def test_start_forward_windows_success(mocker):
    """Returns None on Windows (netsh portproxy doesn't return a PID)."""
    pf = _make_forwarder("Windows")
    mocker.patch("subprocess.run")

    result = pf.start_forward("127.0.0.2", 5432, 15432)

    assert result is None
    assert "127.0.0.2:5432" in pf.processes


@pytest.mark.unit
def test_start_forward_windows_permission_error(mocker):
    """Raises PermissionError when netsh returns access denied."""
    pf = _make_forwarder("Windows")
    error = subprocess.CalledProcessError(1, "netsh")
    error.stderr = "Access is denied"
    error.stdout = ""
    mocker.patch("subprocess.run", side_effect=error)

    with pytest.raises(PermissionError, match="Permission denied"):
        pf.start_forward("127.0.0.2", 5432, 15432)


@pytest.mark.unit
def test_start_forward_windows_generic_error(mocker):
    """Raises RuntimeError on other netsh failures."""
    pf = _make_forwarder("Windows")
    error = subprocess.CalledProcessError(1, "netsh")
    error.stderr = "Some other error"
    error.stdout = ""
    mocker.patch("subprocess.run", side_effect=error)

    with pytest.raises(RuntimeError, match="Failed to create port proxy"):
        pf.start_forward("127.0.0.2", 5432, 15432)


# ============================================================================
# stop_forward
# ============================================================================


@pytest.mark.unit
def test_stop_forward_unix_terminates_process(mocker):
    """stop_forward terminates the socat process on Linux."""
    pf = _make_forwarder("Linux")
    mock_proc = MagicMock()
    pf.processes["127.0.0.2:5432"] = mock_proc

    pf.stop_forward("127.0.0.2", 5432)

    mock_proc.terminate.assert_called_once()
    assert "127.0.0.2:5432" not in pf.processes


@pytest.mark.unit
def test_stop_forward_unix_kills_on_timeout(mocker):
    """stop_forward kills the process if terminate times out."""
    pf = _make_forwarder("Linux")
    mock_proc = MagicMock()
    mock_proc.wait.side_effect = subprocess.TimeoutExpired("socat", 5)
    pf.processes["127.0.0.2:5432"] = mock_proc

    pf.stop_forward("127.0.0.2", 5432)

    mock_proc.kill.assert_called_once()
    assert "127.0.0.2:5432" not in pf.processes


@pytest.mark.unit
def test_stop_forward_noop_when_key_not_in_processes():
    """stop_forward does nothing when the key is not registered."""
    pf = _make_forwarder("Linux")
    # Should not raise
    pf.stop_forward("127.0.0.2", 9999)


@pytest.mark.unit
def test_stop_forward_windows_calls_netsh_delete(mocker):
    """stop_forward on Windows calls netsh to delete the portproxy rule."""
    pf = _make_forwarder("Windows")
    pf.processes["127.0.0.2:5432"] = None  # Windows stores None for netsh
    mock_run = mocker.patch("subprocess.run")

    pf.stop_forward("127.0.0.2", 5432)

    cmd = mock_run.call_args[0][0]
    # cmd is a list, check that items contain expected values
    cmd_str = " ".join(cmd)
    assert "delete" in cmd_str
    assert "127.0.0.2" in cmd_str
    assert "127.0.0.2:5432" not in pf.processes


@pytest.mark.unit
def test_stop_forward_windows_ignores_netsh_error(mocker):
    """stop_forward on Windows ignores CalledProcessError during cleanup."""
    pf = _make_forwarder("Windows")
    pf.processes["127.0.0.2:5432"] = None
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "netsh"))

    # Should not raise
    pf.stop_forward("127.0.0.2", 5432)


# ============================================================================
# stop_all
# ============================================================================


@pytest.mark.unit
def test_stop_all_stops_all_processes(mocker):
    """stop_all terminates all registered forwarding processes."""
    pf = _make_forwarder("Linux")
    proc1 = MagicMock()
    proc2 = MagicMock()
    pf.processes["127.0.0.2:5432"] = proc1
    pf.processes["127.0.0.3:3306"] = proc2

    pf.stop_all()

    proc1.terminate.assert_called_once()
    proc2.terminate.assert_called_once()
    assert pf.processes == {}


@pytest.mark.unit
def test_stop_all_empty_processes_is_noop():
    """stop_all does nothing when no processes are registered."""
    pf = _make_forwarder("Linux")
    # Should not raise
    pf.stop_all()


# ============================================================================
# _ensure_loopback_alias_macos
# ============================================================================


@pytest.mark.unit
def test_ensure_loopback_alias_macos_already_configured(mocker):
    """Does not call ifconfig alias when IP is already in lo0 config."""
    pf = _make_forwarder("Darwin")
    mock_result = MagicMock()
    mock_result.stdout = "inet 127.0.0.5 netmask 0xff000000"
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    pf._ensure_loopback_alias_macos("127.0.0.5")

    # Only the ifconfig lo0 check call should be made, not the alias add
    assert mock_run.call_count == 1


@pytest.mark.unit
def test_ensure_loopback_alias_macos_adds_alias(mocker):
    """Calls sudo ifconfig to add alias when IP is not configured."""
    pf = _make_forwarder("Darwin")
    mock_result_check = MagicMock()
    mock_result_check.stdout = "inet 127.0.0.1 netmask 0xff000000"  # 127.0.0.5 NOT present

    # Console is imported lazily inside the method from rich.console — patch it there
    with patch("rich.console.Console"):
        mock_run = mocker.patch("subprocess.run", return_value=mock_result_check)
        pf._ensure_loopback_alias_macos("127.0.0.5")

    # Second call should be the alias add
    assert mock_run.call_count == 2


@pytest.mark.unit
def test_ensure_loopback_alias_macos_raises_on_add_failure(mocker):
    """Raises OSError when sudo ifconfig alias command fails."""
    pf = _make_forwarder("Darwin")
    mock_check_result = MagicMock()
    # stdout must NOT contain the IP for the alias-add branch to execute
    mock_check_result.stdout = "inet 127.0.0.1 netmask 0xff000000 lo0"

    add_error = subprocess.CalledProcessError(1, "sudo")
    add_error.stderr = "Operation not permitted"

    mocker.patch("subprocess.run", side_effect=[mock_check_result, add_error])

    with patch("rich.console.Console"):
        with pytest.raises(OSError, match="Failed to configure loopback alias"):
            pf._ensure_loopback_alias_macos("127.0.0.5")


# ============================================================================
# _start_forward_unix — FileNotFoundError after Popen (line 76)
# ============================================================================


@pytest.mark.unit
def test_start_forward_unix_raises_file_not_found_if_popen_raises(mocker):
    """Raises FileNotFoundError wrapping the unexpected Popen FileNotFoundError (line 76)."""
    pf = _make_forwarder("Linux")
    mocker.patch.object(pf, "_is_command_available", return_value=True)
    mocker.patch.object(pf, "_kill_orphaned_socat")
    # Popen raises FileNotFoundError even though we checked availability — covers line 76
    mocker.patch("subprocess.Popen", side_effect=FileNotFoundError("socat not found"))
    mocker.patch("time.sleep")

    with pytest.raises(FileNotFoundError, match="socat command not found"):
        pf.start_forward("127.0.0.2", 5432, 15432)


# ============================================================================
# _ensure_loopback_alias_macos — CalledProcessError on ifconfig check (lines 193-194)
# ============================================================================


@pytest.mark.unit
def test_ensure_loopback_alias_macos_ifconfig_check_fails_continues(mocker):
    """CalledProcessError on initial ifconfig lo0 check is caught and alias-add proceeds (lines 193-194)."""
    pf = _make_forwarder("Darwin")

    # First call (ifconfig lo0 check) raises CalledProcessError → pass
    # Second call (sudo ifconfig alias add) succeeds
    check_error = subprocess.CalledProcessError(1, "ifconfig")
    add_success = MagicMock()

    with patch("rich.console.Console"):
        mock_run = mocker.patch("subprocess.run", side_effect=[check_error, add_success])
        pf._ensure_loopback_alias_macos("127.0.0.5")

    assert mock_run.call_count == 2
    # Second call should be the alias-add command
    second_call_cmd = mock_run.call_args_list[1][0][0]
    assert "alias" in second_call_cmd


# ============================================================================
# _kill_orphaned_socat
# ============================================================================


@pytest.mark.unit
def test_kill_orphaned_socat_calls_pkill(mocker):
    """Calls pkill with the socat pattern for the given address and port."""
    pf = _make_forwarder("Linux")
    mock_run = mocker.patch("subprocess.run")
    mocker.patch("time.sleep")

    pf._kill_orphaned_socat("127.0.0.2", 5432)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "pkill"
    assert "-f" in cmd
    assert "socat" in cmd[2]
    assert "5432" in cmd[2]
    assert "127.0.0.2" in cmd[2]


@pytest.mark.unit
def test_kill_orphaned_socat_ignores_exception(mocker):
    """Does not raise even if pkill fails (e.g. not installed)."""
    pf = _make_forwarder("Linux")
    mocker.patch("subprocess.run", side_effect=FileNotFoundError("pkill not found"))
    mocker.patch("time.sleep")

    # Should not raise
    pf._kill_orphaned_socat("127.0.0.2", 5432)


@pytest.mark.unit
def test_kill_orphaned_socat_sleeps_after_kill(mocker):
    """Sleeps briefly after pkill to allow the OS to release the port."""
    pf = _make_forwarder("Linux")
    mocker.patch("subprocess.run")
    mock_sleep = mocker.patch("time.sleep")

    pf._kill_orphaned_socat("127.0.0.2", 5432)

    mock_sleep.assert_called_once_with(0.2)


# ============================================================================
# _register_signal_handlers
# ============================================================================


@pytest.mark.unit
def test_register_signal_handlers_skipped_on_windows():
    """Signal handlers are not registered on Windows."""
    import signal as signal_module

    with patch("cli_tool.commands.ssm.core.port_forwarder.platform.system", return_value="Windows"):
        with patch.object(signal_module, "signal") as mock_signal:
            pf = PortForwarder()
            mock_signal.assert_not_called()


@pytest.mark.unit
def test_register_signal_handlers_registered_on_linux(mocker):
    """SIGTERM and SIGHUP handlers are registered on Linux."""
    import signal as signal_module

    mock_signal = mocker.patch("cli_tool.commands.ssm.core.port_forwarder.signal.signal")
    with patch("cli_tool.commands.ssm.core.port_forwarder.platform.system", return_value="Linux"):
        PortForwarder()

    registered_signals = [call[0][0] for call in mock_signal.call_args_list]
    assert signal_module.SIGTERM in registered_signals
    assert signal_module.SIGHUP in registered_signals


@pytest.mark.unit
def test_register_signal_handlers_ignores_oserror(mocker):
    """OSError during signal registration (e.g. non-main thread) is silently ignored."""
    mocker.patch("cli_tool.commands.ssm.core.port_forwarder.signal.signal", side_effect=OSError)
    with patch("cli_tool.commands.ssm.core.port_forwarder.platform.system", return_value="Linux"):
        # Should not raise
        PortForwarder()
