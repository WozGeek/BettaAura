"""
aura.version_check — Check for newer versions on PyPI.

Checks once per day (cached in ~/.aura/.version_cache).
Never blocks, never crashes — silently returns None on any error.

Usage:
    from aura.version_check import check_for_update
    msg = check_for_update()  # returns str or None
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from aura import __version__

_CACHE_FILE = Path.home() / ".aura" / ".version_cache"
_CACHE_TTL = 86400  # 24 hours
_PYPI_URL = "https://pypi.org/pypi/aura-ctx/json"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse '0.3.2' into (0, 3, 2) for comparison."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _read_cache() -> Optional[dict]:
    """Read cached version info. Returns None if stale or missing."""
    try:
        if not _CACHE_FILE.exists():
            return None
        data = json.loads(_CACHE_FILE.read_text())
        if time.time() - data.get("checked_at", 0) > _CACHE_TTL:
            return None
        return data
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def _write_cache(latest: str) -> None:
    """Write version cache."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({
            "latest": latest,
            "checked_at": time.time(),
        }))
    except IOError:
        pass


def _fetch_latest() -> Optional[str]:
    """Fetch latest version from PyPI. Returns None on any error."""
    try:
        from urllib.request import urlopen, Request
        req = Request(_PYPI_URL, headers={"Accept": "application/json"})
        with urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("info", {}).get("version")
    except Exception:
        return None


def get_latest_version() -> Optional[str]:
    """Get latest version from cache or PyPI (cached for 24h)."""
    cached = _read_cache()
    if cached:
        return cached.get("latest")

    latest = _fetch_latest()
    if latest:
        _write_cache(latest)
    return latest


def check_for_update() -> Optional[str]:
    """
    Check if a newer version exists. Returns a warning message or None.

    Safe to call anywhere — never raises, never blocks for more than 3s.
    """
    try:
        latest = get_latest_version()
        if not latest:
            return None

        if _parse_version(latest) > _parse_version(__version__):
            return (
                f"[yellow]⚠ New version available: {latest} "
                f"(you have {__version__})[/yellow]\n"
                f"  Run: [bold]aura update[/bold]"
            )
        return None
    except Exception:
        return None


def run_update() -> int:
    """
    Run pip install --upgrade aura-ctx.

    Returns the pip exit code (0 = success).
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "aura-ctx"],
        capture_output=False,
    )

    # Clear cache so next check picks up the new version
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except IOError:
        pass

    return result.returncode
