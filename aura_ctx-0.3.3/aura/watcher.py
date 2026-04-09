"""
aura.watcher — File watcher for hot-reloading context packs.

Watches ~/.aura/packs/ for YAML changes and triggers a reload
in the MCP server. Uses watchdog for cross-platform file monitoring.

Falls back to a simple polling watcher if watchdog is not installed.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from aura.pack import get_packs_dir


# ---------------------------------------------------------------------------
# Callback type
# ---------------------------------------------------------------------------
ReloadCallback = Callable[[], None]


# ---------------------------------------------------------------------------
# Polling watcher (zero dependencies)
# ---------------------------------------------------------------------------
class PollingWatcher:
    """Simple polling-based watcher. No external deps required."""

    def __init__(self, watch_dir: Path, callback: ReloadCallback, interval: float = 1.0):
        self.watch_dir = watch_dir
        self.callback = callback
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._snapshots: dict[str, float] = {}

    def _snapshot(self) -> dict[str, float]:
        """Get modification times of all YAML files."""
        snaps = {}
        try:
            for f in self.watch_dir.glob("*.yaml"):
                try:
                    snaps[str(f)] = f.stat().st_mtime
                except OSError:
                    pass
        except OSError:
            pass
        return snaps

    def _poll(self):
        """Polling loop."""
        self._snapshots = self._snapshot()
        while self._running:
            time.sleep(self.interval)
            current = self._snapshot()
            if current != self._snapshots:
                self._snapshots = current
                try:
                    self.callback()
                except Exception as e:
                    print(f"  [watcher] Reload error: {e}")

    def start(self):
        """Start watching in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Watchdog-based watcher (if available)
# ---------------------------------------------------------------------------
def _try_watchdog_watcher(watch_dir: Path, callback: ReloadCallback) -> Optional[object]:
    """Try to create a watchdog-based watcher. Returns None if watchdog not installed."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class YamlHandler(FileSystemEventHandler):
            def __init__(self, cb: ReloadCallback):
                self._callback = cb
                self._debounce_timer: Optional[threading.Timer] = None

            def _debounced_reload(self):
                """Debounce rapid file changes (e.g. editor save)."""
                if self._debounce_timer:
                    self._debounce_timer.cancel()
                self._debounce_timer = threading.Timer(0.5, self._do_reload)
                self._debounce_timer.start()

            def _do_reload(self):
                try:
                    self._callback()
                except Exception as e:
                    print(f"  [watcher] Reload error: {e}")

            def on_modified(self, event):
                if event.src_path.endswith(".yaml"):
                    self._debounced_reload()

            def on_created(self, event):
                if event.src_path.endswith(".yaml"):
                    self._debounced_reload()

            def on_deleted(self, event):
                if event.src_path.endswith(".yaml"):
                    self._debounced_reload()

        observer = Observer()
        observer.schedule(YamlHandler(callback), str(watch_dir), recursive=False)
        observer.daemon = True
        return observer

    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_watcher(callback: ReloadCallback, watch_dir: Optional[Path] = None):
    """Create the best available watcher. Returns (watcher, engine_name)."""
    directory = watch_dir or get_packs_dir()

    # Try watchdog first
    observer = _try_watchdog_watcher(directory, callback)
    if observer is not None:
        return observer, "watchdog"

    # Fall back to polling
    return PollingWatcher(directory, callback), "polling"


def start_watching(callback: ReloadCallback, watch_dir: Optional[Path] = None) -> tuple:
    """Start a file watcher. Returns (watcher, engine_name)."""
    watcher, engine = create_watcher(callback, watch_dir)
    watcher.start()
    return watcher, engine
