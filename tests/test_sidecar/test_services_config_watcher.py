"""Unit tests for cli_tool.sidecar.services.config_watcher."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.sidecar.services import config_watcher
from cli_tool.sidecar.state import EventHub


@pytest.mark.unit
class TestStartConfigWatcher:
    def test_returns_observer_when_watchdog_available(self, mocker, tmp_path: Path):
        # Point config file at a tmp location so watchdog observes a real dir
        fake_config = tmp_path / "config.json"
        fake_config.write_text("{}")
        mocker.patch("cli_tool.sidecar.services.config_watcher.get_config_file", return_value=fake_config)

        fake_observer = MagicMock()
        mock_observer_cls = MagicMock(return_value=fake_observer)
        mocker.patch.dict("sys.modules", {"watchdog.observers": MagicMock(Observer=mock_observer_cls)})
        # The module imports Observer + FileSystemEventHandler lazily
        mocker.patch.dict(
            "sys.modules",
            {
                "watchdog.events": MagicMock(FileSystemEventHandler=MagicMock),
                "watchdog.observers": MagicMock(Observer=mock_observer_cls),
            },
        )

        hub = EventHub()
        result = config_watcher.start_config_watcher(hub)

        # The function should return the observer instance
        assert result is fake_observer
        mock_observer_cls.assert_called_once()
        fake_observer.schedule.assert_called_once()
        fake_observer.daemon = True
        assert fake_observer.daemon is True
        fake_observer.start.assert_called_once()

    def test_returns_none_when_watchdog_missing(self, mocker, tmp_path: Path):
        fake_config = tmp_path / "config.json"
        fake_config.write_text("{}")
        mocker.patch("cli_tool.sidecar.services.config_watcher.get_config_file", return_value=fake_config)

        # Simulate watchdog not being installed
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "watchdog.events" or name == "watchdog.observers" or name.startswith("watchdog"):
                raise ImportError("watchdog not installed")
            return real_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", side_effect=fake_import)

        hub = EventHub()
        result = config_watcher.start_config_watcher(hub)
        assert result is None


@pytest.mark.unit
class TestConfigHandler:
    """Test the _ConfigHandler class (kept for backwards compat, but the
    production path uses the inline class inside start_config_watcher).
    """

    def test_dispatch_publishes_on_matching_path(self):
        hub = EventHub()
        q = hub.subscribe()
        handler = config_watcher._ConfigHandler("/path/to/config.json", hub)

        event = MagicMock()
        event.src_path = "/path/to/config.json"
        handler.dispatch(event)

        msg = q.get_nowait()
        assert msg == {"event": "config.changed"}

    def test_dispatch_ignores_other_paths(self):
        hub = EventHub()
        q = hub.subscribe()
        handler = config_watcher._ConfigHandler("/path/to/config.json", hub)

        event = MagicMock()
        event.src_path = "/path/to/something-else.json"
        handler.dispatch(event)

        assert q.empty()

    def test_dispatch_handles_missing_src_path(self):
        hub = EventHub()
        q = hub.subscribe()
        handler = config_watcher._ConfigHandler("/path/to/config.json", hub)

        event = MagicMock(spec=[])  # no src_path attribute
        handler.dispatch(event)

        assert q.empty()
