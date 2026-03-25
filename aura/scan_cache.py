"""
aura.scan_cache — Content hashing for incremental scanning.

Stores SHA-256 hashes of scanned sources (git config, shell rc, IDE settings,
package files). On subsequent scans, only re-processes sources whose content
has actually changed.

Cache stored in ~/.aura/scan_cache.json
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def _cache_path() -> Path:
    """Return the path to the scan cache file."""
    return Path.home() / ".aura" / "scan_cache.json"


def _load_cache() -> dict:
    """Load the scan cache from disk."""
    path = _cache_path()
    if not path.exists():
        return {"version": 1, "entries": {}, "last_full_scan": None}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": 1, "entries": {}, "last_full_scan": None}


def _save_cache(cache: dict):
    """Save the scan cache to disk."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def hash_content(content: str) -> str:
    """Generate SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hash_file(path: Path) -> Optional[str]:
    """Generate SHA-256 hash of a file's contents. Returns None if file unreadable."""
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except (IOError, OSError, PermissionError):
        return None


def has_changed(source_key: str, current_hash: str) -> bool:
    """Check if a source has changed since last scan."""
    cache = _load_cache()
    cached_hash = cache.get("entries", {}).get(source_key, {}).get("hash")
    return cached_hash != current_hash


def update_entry(source_key: str, content_hash: str):
    """Update a single cache entry after successful scan."""
    cache = _load_cache()
    cache["entries"][source_key] = {
        "hash": content_hash,
        "scanned_at": datetime.now().isoformat(),
    }
    _save_cache(cache)


def update_cache(entries: dict[str, str]):
    """Batch update cache entries. entries = {source_key: content_hash}."""
    cache = _load_cache()
    for key, content_hash in entries.items():
        cache["entries"][key] = {
            "hash": content_hash,
            "scanned_at": datetime.now().isoformat(),
        }
    cache["last_full_scan"] = datetime.now().isoformat()
    _save_cache(cache)


def get_changed_sources(sources: dict[str, str]) -> dict[str, str]:
    """Given {source_key: current_hash}, return only the ones that changed."""
    cache = _load_cache()
    cached_entries = cache.get("entries", {})

    changed = {}
    for key, current_hash in sources.items():
        cached = cached_entries.get(key, {})
        if cached.get("hash") != current_hash:
            changed[key] = current_hash

    return changed


def get_cache_stats() -> dict:
    """Return cache statistics."""
    cache = _load_cache()
    entries = cache.get("entries", {})
    return {
        "total_entries": len(entries),
        "last_full_scan": cache.get("last_full_scan"),
        "cache_path": str(_cache_path()),
    }


def clear_cache():
    """Clear the scan cache entirely."""
    path = _cache_path()
    if path.exists():
        path.unlink()
