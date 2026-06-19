"""Watchdog observer — emits config.changed when ~/.devo/config.json is modified."""

import threading

from cli_tool.core.utils.config_manager import get_config_file
from cli_tool.sidecar.state import EventHub


class _ConfigHandler:
    def __init__(self, path: str, hub: EventHub) -> None:
        self._path = path
        self._hub = hub

    def dispatch(self, event) -> None:
        if getattr(event, "src_path", None) == self._path:
            self._hub.publish("config.changed", {})


def start_config_watcher(hub: EventHub) -> threading.Thread:
    """Start a watchdog Observer in a daemon thread. Returns the thread."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        config_path = get_config_file()
        watch_dir = str(config_path.parent)
        config_str = str(config_path)

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path == config_str:
                    hub.publish("config.changed", {})

        observer = Observer()
        observer.schedule(_Handler(), watch_dir, recursive=False)
        observer.daemon = True
        observer.start()
        return observer
    except ImportError:
        # watchdog not installed — config live-reload disabled
        return None
