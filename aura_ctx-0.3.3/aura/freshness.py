"""
aura.freshness — Staleness scoring for facts and packs.

Computes a freshness score (0–100) for each fact based on:
  - Time since last update (updated_at or pack meta updated_at)
  - Fact type (identity facts stay fresh forever, context decays)
  - Confidence level (high confidence stays fresh longer)

The score is visible in `aura show` and exposed in MCP responses
so users can see how current their context is.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from aura.schema import ContextPack, Fact

# ---------------------------------------------------------------------------
# TTL config per fact type (days)
# ---------------------------------------------------------------------------
TYPE_TTL: dict[str, int] = {
    "identity": 999999,   # Never stale
    "skill": 365,         # Skills change slowly
    "preference": 180,    # Preferences shift
    "style": 180,         # Style evolves
    "constraint": 120,    # Constraints change with projects
    "context": 90,        # Context is most volatile
}

CONFIDENCE_MULTIPLIER: dict[str, float] = {
    "high": 1.0,
    "medium": 0.66,
    "low": 0.33,
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def fact_freshness(fact: Fact, pack_updated_at: Optional[str] = None) -> int:
    """
    Compute freshness score for a single fact (0–100).

    100 = just updated / identity fact (always fresh)
    0   = expired beyond TTL

    Uses fact.updated_at if available, otherwise falls back to
    pack_updated_at (the pack's meta.updated_at).
    """
    # Identity facts are always fresh
    if fact.type.value == "identity":
        return 100

    # Determine the reference timestamp
    ref_time = None
    if fact.updated_at:
        try:
            ref_time = datetime.fromisoformat(fact.updated_at)
        except (ValueError, TypeError):
            pass
    if ref_time is None and pack_updated_at:
        try:
            ref_time = datetime.fromisoformat(pack_updated_at)
        except (ValueError, TypeError):
            pass
    if ref_time is None:
        return 50  # Unknown age — middle ground

    # Calculate days old
    now = datetime.now()
    days_old = max(0, (now - ref_time).days)

    # Get TTL for this fact type
    ttl = TYPE_TTL.get(fact.type.value, 90)

    # Apply confidence multiplier
    conf_mult = CONFIDENCE_MULTIPLIER.get(fact.confidence.value, 1.0)
    effective_ttl = ttl * conf_mult

    if effective_ttl <= 0:
        return 0

    # Score: 100 at day 0, linearly decaying to 0 at TTL
    score = max(0, min(100, int(100 * (1 - days_old / effective_ttl))))
    return score


def fact_freshness_label(score: int) -> str:
    """Human-readable label for a freshness score."""
    if score >= 90:
        return "fresh"
    elif score >= 60:
        return "current"
    elif score >= 30:
        return "aging"
    elif score > 0:
        return "stale"
    else:
        return "expired"


def fact_freshness_color(score: int) -> str:
    """Rich color name for a freshness score."""
    if score >= 90:
        return "green"
    elif score >= 60:
        return "cyan"
    elif score >= 30:
        return "yellow"
    elif score > 0:
        return "red"
    else:
        return "dim"


def pack_freshness(pack: ContextPack) -> int:
    """Average freshness score across all facts in a pack."""
    if not pack.facts:
        return 100

    pack_updated = None
    if pack.meta.updated_at:
        # Handle both datetime objects and ISO strings
        if hasattr(pack.meta.updated_at, 'isoformat'):
            pack_updated = pack.meta.updated_at.isoformat()
        else:
            pack_updated = str(pack.meta.updated_at)

    scores = [fact_freshness(f, pack_updated) for f in pack.facts]
    return int(sum(scores) / len(scores))


def pack_freshness_summary(pack: ContextPack) -> dict:
    """Detailed freshness summary for a pack."""
    if not pack.facts:
        return {"score": 100, "fresh": 0, "current": 0, "aging": 0, "stale": 0, "total": 0}

    pack_updated = None
    if pack.meta.updated_at:
        if hasattr(pack.meta.updated_at, 'isoformat'):
            pack_updated = pack.meta.updated_at.isoformat()
        else:
            pack_updated = str(pack.meta.updated_at)

    scores = [fact_freshness(f, pack_updated) for f in pack.facts]

    return {
        "score": int(sum(scores) / len(scores)),
        "fresh": sum(1 for s in scores if s >= 90),
        "current": sum(1 for s in scores if 60 <= s < 90),
        "aging": sum(1 for s in scores if 30 <= s < 60),
        "stale": sum(1 for s in scores if 0 < s < 30),
        "total": len(scores),
    }
