"""
aura.usage — Local MCP Usage Tracker

Tracks which facts and packs are accessed via MCP, entirely on-device.
Opt-out via config: `track_usage: false` in ~/.aura/config.yaml
or via CLI: `aura serve --no-track`

Storage: ~/.aura/usage.json
Format: version-tagged JSON, human-readable.

Priority formula (score 0-100):
    score = (usage_norm × 0.4) + (freshness × 0.4) + (confidence_weight × 0.2)

Facts with score > 70 are promoted to level-1 (identity card).
"""

from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USAGE_VERSION = "1"
USAGE_FILE_NAME = "usage.json"

_W_USAGE = 0.4
_W_FRESHNESS = 0.4
_W_CONFIDENCE = 0.2

_CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.66, "low": 0.33}

PRIORITY_THRESHOLD = 70.0

_lock = threading.Lock()
_tracking_enabled: bool = True


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def get_usage_path() -> Path:
    from aura.pack import get_aura_home
    return get_aura_home() / USAGE_FILE_NAME


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------
def set_tracking(enabled: bool) -> None:
    global _tracking_enabled
    _tracking_enabled = enabled


def is_tracking_enabled() -> bool:
    if not _tracking_enabled:
        return False
    try:
        from aura.pack import get_config_path
        from ruamel.yaml import YAML as _YAML
        _yaml = _YAML()
        cfg_path = get_config_path()
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = _yaml.load(f) or {}
            if cfg.get("track_usage") is False:
                return False
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def _load_usage() -> dict:
    path = get_usage_path()
    if not path.exists():
        return _empty_usage()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != USAGE_VERSION:
            return _empty_usage()
        return data
    except Exception:
        return _empty_usage()


def _save_usage(data: dict) -> None:
    path = get_usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _empty_usage() -> dict:
    return {"version": USAGE_VERSION, "facts": {}, "packs": {}}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------
def record_pack_access(pack_name: str, agent: str = "unknown") -> None:
    if not is_tracking_enabled():
        return
    with _lock:
        data = _load_usage()
        entry = data["packs"].setdefault(
            pack_name, {"calls": 0, "last_called": None, "agents": {}}
        )
        entry["calls"] = entry.get("calls", 0) + 1
        entry["last_called"] = _now_iso()
        entry.setdefault("agents", {})[agent] = (
            entry["agents"].get(agent, 0) + 1
        )
        _save_usage(data)


def record_fact_access(pack_name: str, fact_key: str, agent: str = "unknown") -> None:
    if not is_tracking_enabled():
        return
    with _lock:
        data = _load_usage()
        composite_key = f"{pack_name}.{fact_key}"
        entry = data["facts"].setdefault(
            composite_key, {"calls": 0, "last_called": None, "tools": {}}
        )
        entry["calls"] = entry.get("calls", 0) + 1
        entry["last_called"] = _now_iso()
        entry.setdefault("tools", {})[agent] = (
            entry["tools"].get(agent, 0) + 1
        )
        _save_usage(data)


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------
def _freshness_score(fact) -> float:
    try:
        from aura.freshness import compute_freshness
        return float(compute_freshness(fact))
    except Exception:
        return 100.0


def _usage_norm(calls: int) -> float:
    """Normalise call count to 0-100 using log scale (1000 calls → 100)."""
    if calls <= 0:
        return 0.0
    return min(100.0, (math.log10(calls + 1) / math.log10(1001)) * 100.0)


def compute_priority_score(
    fact,
    pack_name: str,
    usage_data: Optional[dict] = None,
) -> float:
    """
    Compute priority score 0-100 for a Fact.

    score = (usage_norm × 0.4) + (freshness × 0.4) + (confidence_weight × 0.2)
    """
    if usage_data is None:
        usage_data = _load_usage()

    composite_key = f"{pack_name}.{fact.key}"
    calls = usage_data.get("facts", {}).get(composite_key, {}).get("calls", 0)
    usage_component = _usage_norm(calls) * 100.0  # already 0-100
    usage_component = _usage_norm(calls)

    freshness_component = _freshness_score(fact)

    conf_val = fact.confidence.value if hasattr(fact.confidence, "value") else str(fact.confidence)
    conf_weight = _CONFIDENCE_WEIGHTS.get(conf_val, 1.0)
    confidence_component = conf_weight * 100.0

    score = (
        usage_component * _W_USAGE
        + freshness_component * _W_FRESHNESS
        + confidence_component * _W_CONFIDENCE
    )
    return round(min(100.0, max(0.0, score)), 2)


def sort_facts_by_priority(facts, pack_name: str) -> list:
    """Return facts sorted by priority score descending."""
    usage_data = _load_usage()
    return sorted(
        facts,
        key=lambda f: compute_priority_score(f, pack_name, usage_data),
        reverse=True,
    )


def get_high_priority_facts(facts, pack_name: str, threshold: float = PRIORITY_THRESHOLD) -> list:
    """Return only facts whose priority score >= threshold."""
    usage_data = _load_usage()
    return [
        f for f in facts
        if compute_priority_score(f, pack_name, usage_data) >= threshold
    ]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def get_stats(pack_filter: Optional[str] = None) -> dict:
    """
    Return aggregated usage stats.

    Returns:
        {
          "facts": [ {key, pack, calls, last_called, tools} … ],
          "packs": [ {name, calls, last_called, agents} … ],
        }
    Sorted by calls descending.
    """
    data = _load_usage()

    facts_out = []
    for composite_key, entry in data.get("facts", {}).items():
        parts = composite_key.split(".", 1)
        pack_name = parts[0] if len(parts) == 2 else "unknown"
        fact_key = parts[1] if len(parts) == 2 else composite_key
        if pack_filter and pack_name != pack_filter:
            continue
        facts_out.append({
            "key": fact_key,
            "pack": pack_name,
            "composite_key": composite_key,
            "calls": entry.get("calls", 0),
            "last_called": entry.get("last_called"),
            "tools": entry.get("tools", {}),
        })
    facts_out.sort(key=lambda x: x["calls"], reverse=True)

    packs_out = []
    for pack_name, entry in data.get("packs", {}).items():
        if pack_filter and pack_name != pack_filter:
            continue
        packs_out.append({
            "name": pack_name,
            "calls": entry.get("calls", 0),
            "last_called": entry.get("last_called"),
            "agents": entry.get("agents", {}),
        })
    packs_out.sort(key=lambda x: x["calls"], reverse=True)

    return {"facts": facts_out, "packs": packs_out}


def reset_stats(pack_filter: Optional[str] = None) -> int:
    """
    Reset usage counters.
    If pack_filter given, reset only that pack's data.
    Returns number of entries cleared.
    """
    with _lock:
        data = _load_usage()
        cleared = 0
        if pack_filter:
            new_facts = {}
            for k, v in data.get("facts", {}).items():
                if k.startswith(f"{pack_filter}."):
                    cleared += 1
                else:
                    new_facts[k] = v
            data["facts"] = new_facts
            if pack_filter in data.get("packs", {}):
                del data["packs"][pack_filter]
                cleared += 1
        else:
            cleared = len(data.get("facts", {})) + len(data.get("packs", {}))
            data = _empty_usage()
        _save_usage(data)
        return cleared
