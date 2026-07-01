from unittest.mock import MagicMock


# 1. cli_tool/cli.py (signal handlers & KeyboardInterrupt)
def test_main_fatal_signals(mocker):
    from cli_tool.cli import main

    mock_exit = mocker.patch("cli_tool.cli.sys.exit")
    handlers = {}

    def mock_signal(signum, handler):
        handlers[signum] = handler

    # Mock the globally imported signal module used inside main()
    mock_sig_module = MagicMock()
    mock_sig_module.SIGTERM = 15
    mock_sig_module.SIGHUP = 1
    mock_sig_module.signal = mock_signal
    mocker.patch.dict("sys.modules", {"signal": mock_sig_module})

    # Force an immediate exit of the main try block
    mocker.patch("cli_tool.cli.cli", side_effect=ValueError("stop"))
    try:
        main()
    except ValueError:
        pass

    assert 15 in handlers
    handlers[15](15, None)
    mock_exit.assert_called_with(128 + 15)


def test_main_keyboard_interrupt(mocker):
    from cli_tool.cli import main

    mock_exit = mocker.patch("cli_tool.cli.sys.exit")
    mocker.patch("cli_tool.cli.cli", side_effect=KeyboardInterrupt())
    mock_capture = mocker.patch("cli_tool.core.utils.telemetry.capture_command")

    main()
    mock_exit.assert_called_with(130)
    assert mock_capture.call_count == 1
    assert mock_capture.call_args[1]["success"] is False


# 2. aws_login/commands/refresh.py (--force)
def test_refresh_all_profiles_force(mocker):
    from cli_tool.commands.aws_login.commands.refresh import refresh_all_profiles

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=["prof1", "prof2"])

    # Mock classify to say both are valid
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._classify_profiles", return_value=([], [("prof1", "1h"), ("prof2", "1h")]))
    mock_confirm = mocker.patch("cli_tool.commands.aws_login.commands.refresh._confirm_refresh", return_value=True)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session", return_value={})
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions", return_value=(2, 0, ["prof1", "prof2"]))
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._update_default_credentials_after_refresh")

    # With force=True, valid profiles should be moved to refresh list
    refresh_all_profiles(force=True)
    mock_confirm.assert_called_once()
    assert mock_confirm.call_args[0][0] == [("prof1", "Forced refresh"), ("prof2", "Forced refresh")]


# 3. ssm/commands/database/connect.py (finally block)
def test_connect_databases_finally_cleanup(mocker):
    from cli_tool.commands.ssm.commands.database.connect import _connect_databases

    mock_registry_class = mocker.patch("cli_tool.commands.ssm.commands.database.connect.ForwarderRegistry")
    mock_registry = MagicMock()
    mock_registry_class.return_value = mock_registry

    mocker.patch("cli_tool.commands.ssm.commands.database.connect._validate_tokens", return_value=True)
    mocker.patch("cli_tool.commands.ssm.commands.database.connect._make_connection_table")
    mocker.patch("cli_tool.commands.ssm.commands.database.connect.HostsManager")

    # Fake an exception in the loop
    mocker.patch("time.sleep", side_effect=KeyboardInterrupt())
    mocker.patch("cli_tool.commands.ssm.commands.database.connect.console.print")

    thread_mock = MagicMock()
    thread_mock.is_alive.return_value = True

    mocker.patch("cli_tool.commands.ssm.commands.database.connect._build_threads", return_value=([("db1", thread_mock)], 0, 0))

    _connect_databases({"db1": {}}, no_hosts=True)

    # Should have called registry stop and thread join
    mock_registry.stop_event.set.assert_called_once()
    mock_registry.stop_all.assert_called_once()
    thread_mock.join.assert_called_once_with(timeout=2)


# 4. ssm/core/session.py (_is_token_expired uses AWS CLI cache)
def test_is_token_expired_uses_cli_cache_available(mocker):
    from cli_tool.commands.ssm.core.session import SSMSession

    mocker.patch("cli_tool.commands.aws_login.core.credentials.check_profile_credentials_available", return_value=(True, None))
    assert SSMSession._is_token_expired(profile="prof1") is False


def test_is_token_expired_uses_cli_cache_expired(mocker):
    from cli_tool.commands.ssm.core.session import SSMSession

    mocker.patch(
        "cli_tool.commands.aws_login.core.credentials.check_profile_credentials_available",
        return_value=(False, "The SSO session associated with this profile has expired"),
    )
    assert SSMSession._is_token_expired(profile="prof1") is True


# 5. ssm/core/connection_runner.py (SIGKILL and active poll loop)
def test_run_attempt_cli_mode_kills_on_stop(mocker):
    from cli_tool.commands.ssm.core.connection_runner import _run_attempt

    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.poll.side_effect = [None, None, 0]  # eventually finishes, but wait, we break!
    mock_proc.returncode = 0

    mocker.patch("cli_tool.commands.ssm.core.session.SSMSession.spawn_port_forwarding_to_remote", return_value=mock_proc)

    mock_registry = MagicMock()
    mock_registry.stop_event.is_set.side_effect = [False, True]

    mock_killpg = mocker.patch("os.killpg", create=True)
    mocker.patch("os.getpgid", return_value=5678, create=True)
    mocker.patch("sys.platform", "linux")
    mocker.patch("time.sleep")

    rc = _run_attempt(
        {"host": "foo", "port": 5432, "bastion": "bar", "region": "us-east-1", "profile": "prof"},
        actual_local_port=1234,
        use_hostname_forwarding=False,
        registry=mock_registry,
    )

    assert rc == 0
    mock_killpg.assert_called_once()


def test_run_attempt_cli_mode_kills_on_stop_windows(mocker):
    from cli_tool.commands.ssm.core.connection_runner import _run_attempt

    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.poll.side_effect = [None, None, 0]
    mock_proc.returncode = 0

    mocker.patch("cli_tool.commands.ssm.core.session.SSMSession.spawn_port_forwarding_to_remote", return_value=mock_proc)

    mock_registry = MagicMock()
    mock_registry.stop_event.is_set.side_effect = [False, True]

    mocker.patch("sys.platform", "win32")
    mocker.patch("time.sleep")

    mock_psutil_process_class = mocker.patch("psutil.Process")
    mock_parent = MagicMock()
    mock_child = MagicMock()
    mock_parent.children.return_value = [mock_child]
    mock_psutil_process_class.return_value = mock_parent

    rc = _run_attempt(
        {"host": "foo", "port": 5432, "bastion": "bar", "region": "us-east-1", "profile": "prof"},
        actual_local_port=1234,
        use_hostname_forwarding=False,
        registry=mock_registry,
    )

    assert rc == 0
    mock_child.terminate.assert_called_once()
    mock_parent.terminate.assert_called_once()


# 6. ssm/core/port_forwarder.py (SIGKILL unix)
def test_port_forwarder_stop_unix(mocker):
    from cli_tool.commands.ssm.core.port_forwarder import PortForwarder

    pf = PortForwarder()
    mock_proc = MagicMock()
    mock_proc.pid = 999
    pf.processes["key"] = mock_proc

    mock_killpg = mocker.patch("os.killpg", create=True)
    mocker.patch("os.getpgid", return_value=888, create=True)

    pf._stop_forward_unix("key")

    mock_killpg.assert_called_once()
    assert "key" not in pf.processes


# 7. core/utils/telemetry.py (atexit.unregister)
def test_telemetry_unregisters_atexit(mocker):
    from cli_tool.core.utils.telemetry import _send

    mocker.patch("cli_tool.core.utils.telemetry.is_enabled", return_value=True)

    mock_posthog = mocker.patch("cli_tool.core.utils.telemetry.posthog")
    mock_client = MagicMock()
    mock_posthog.setup.return_value = mock_client

    mock_atexit = mocker.patch("atexit.unregister")

    # Extract the target passed to threading.Thread and execute it synchronously
    def mock_thread_init(*args, **kwargs):
        kwargs["target"]()
        return MagicMock()

    mocker.patch("threading.Thread", side_effect=mock_thread_init)

    _send("test_event", {})

    mock_atexit.assert_called_once_with(mock_client.join)
    mock_posthog.capture.assert_called_once()
    mock_posthog.flush.assert_called_once()
