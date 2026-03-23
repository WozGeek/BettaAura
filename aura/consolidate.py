"""
aura.consolidate — Context consolidation and memory decay.

Two systems that keep your context packs lean and accurate over time:

1. **Consolidation** — merge duplicate facts, resolve contradictions,
   compress redundant entries across all packs.

2. **Memory decay** — facts have lifespans based on their type.
   Identity facts never expire. Context facts fade after 90 days.
   Imported facts fade after 60 days unless refreshed.

Together, they prevent context bloat — the #1 failure mode
of persistent AI memory systems.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from aura.schema import Confidence, ContextPack, Fact, FactType


# ---------------------------------------------------------------------------
# Decay configuration — TTL in days per fact type
# ---------------------------------------------------------------------------
DECAY_TTL: dict[str, int | None] = {
    # Identity facts never expire
    FactType.IDENTITY: None,
    # Skills decay slowly — you might stop using a language
    FactType.SKILL: 180,
    # Preferences change
    FactType.PREFERENCE: 120,
    # Style is relatively stable
    FactType.STYLE: 150,
    # Constraints can change with projects
    FactType.CONSTRAINT: 90,
    # Context facts are the most volatile
    FactType.CONTEXT: 90,
}

# Facts from imports decay faster (unverified)
IMPORT_DECAY_MULTIPLIER = 0.66  # 66% of normal TTL

# Low-confidence facts decay faster
LOW_CONFIDENCE_MULTIPLIER = 0.5
MEDIUM_CONFIDENCE_MULTIPLIER = 0.75

# Similarity threshold for merging (0.0 = nothing, 1.0 = exact match)
SIMILARITY_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@dataclass
class DecayResult:
    """Result of running memory decay on packs."""
    expired: list[dict] = field(default_factory=list)     # facts removed
    warning: list[dict] = field(default_factory=list)      # facts expiring soon
    preserved: int = 0                                     # facts kept
    total_checked: int = 0


@dataclass
class ConsolidateResult:
    """Result of consolidation across packs."""
    merged: list[dict] = field(default_factory=list)       # duplicate pairs merged
    contradictions: list[dict] = field(default_factory=list)  # conflicts found
    removed: int = 0                                       # total facts removed
    packs_modified: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Memory Decay
# ---------------------------------------------------------------------------
def compute_ttl(fact: Fact) -> int | None:
    """Compute the TTL in days for a specific fact, considering type, confidence, and source."""
    base_ttl = DECAY_TTL.get(fact.type, 90)

    # Identity facts never expire
    if base_ttl is None:
        return None

    ttl = float(base_ttl)

    # Imported facts decay faster
    if fact.source and fact.source.endswith("-import"):
        ttl *= IMPORT_DECAY_MULTIPLIER

    # Low confidence decays faster
    if fact.confidence == Confidence.LOW:
        ttl *= LOW_CONFIDENCE_MULTIPLIER
    elif fact.confidence == Confidence.MEDIUM:
        ttl *= MEDIUM_CONFIDENCE_MULTIPLIER

    return int(ttl)


def check_decay(packs: list[ContextPack], dry_run: bool = True) -> DecayResult:
    """
    Check all facts for expiration based on their TTL.

    Args:
        packs: List of context packs to check
        dry_run: If True, only report — don't modify packs.
                 If False, actually remove expired facts.

    Returns:
        DecayResult with expired, warning, and preserved counts.
    """
    result = DecayResult()
    now = datetime.now()
    warning_window = timedelta(days=14)  # Warn 14 days before expiration

    for pack in packs:
        facts_to_keep = []

        for fact in pack.facts:
            result.total_checked += 1
            ttl = compute_ttl(fact)

            # No TTL = never expires
            if ttl is None:
                facts_to_keep.append(fact)
                result.preserved += 1
                continue

            # Check if fact has an updated_at timestamp
            fact_date = fact.updated_at or (pack.meta.created_at if pack.meta else now)
            age = (now - fact_date).days
            remaining = ttl - age

            if remaining <= 0:
                # Expired
                val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                result.expired.append({
                    "pack": pack.name,
                    "key": fact.key,
                    "value": val,
                    "age_days": age,
                    "ttl_days": ttl,
                    "type": fact.type,
                })
                if dry_run:
                    facts_to_keep.append(fact)  # Keep in dry run
                # In wet run, we simply don't add it to facts_to_keep
            elif remaining <= warning_window.days:
                # Expiring soon
                val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                result.warning.append({
                    "pack": pack.name,
                    "key": fact.key,
                    "value": val,
                    "remaining_days": remaining,
                    "ttl_days": ttl,
                })
                facts_to_keep.append(fact)
                result.preserved += 1
            else:
                facts_to_keep.append(fact)
                result.preserved += 1

        if not dry_run:
            pack.facts = facts_to_keep

    return result


def refresh_fact(pack: ContextPack, key: str) -> bool:
    """
    Refresh a fact's timestamp to prevent decay.
    Returns True if the fact was found and refreshed.
    """
    for fact in pack.facts:
        if fact.key == key:
            fact.updated_at = datetime.now()
            return True
    return False


# ---------------------------------------------------------------------------
# Consolidation
# ---------------------------------------------------------------------------
def _normalize_value(value: str | list[str]) -> str:
    """Normalize a fact value for comparison."""
    if isinstance(value, list):
        return ", ".join(sorted(v.lower().strip() for v in value))
    return value.lower().strip()


def _similarity(a: str, b: str) -> float:
    """Compute string similarity ratio between two values."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def consolidate(packs: list[ContextPack], dry_run: bool = True) -> ConsolidateResult:
    """
    Consolidate facts across all packs.

    Detects:
    1. Exact duplicates (same key + same value in different packs)
    2. Same-key conflicts (same key, different values)
    3. Similar values (fuzzy match on values within same pack)

    Args:
        packs: List of context packs to consolidate
        dry_run: If True, only report. If False, actually merge/remove.

    Returns:
        ConsolidateResult with merged, contradictions, and modification info.
    """
    result = ConsolidateResult()

    # Phase 1: Cross-pack exact duplicates
    _find_cross_pack_duplicates(packs, result, dry_run)

    # Phase 2: Same-key contradictions
    _find_contradictions(packs, result)

    # Phase 3: Within-pack similar facts
    _find_similar_facts(packs, result, dry_run)

    return result


def _find_cross_pack_duplicates(
    packs: list[ContextPack], result: ConsolidateResult, dry_run: bool
):
    """Find and optionally remove exact duplicates across packs."""
    # Map: (key, normalized_value) -> [(pack_index, fact_index)]
    seen: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)

    for pi, pack in enumerate(packs):
        for fi, fact in enumerate(pack.facts):
            norm = _normalize_value(fact.value)
            seen[(fact.key, norm)].append((pi, fi))

    for (key, _), locations in seen.items():
        if len(locations) <= 1:
            continue

        # Keep the one with highest confidence, or the most recently updated
        best_pi, best_fi = locations[0]
        best_fact = packs[best_pi].facts[best_fi]
        for pi, fi in locations[1:]:
            candidate = packs[pi].facts[fi]
            if _is_better_fact(candidate, best_fact):
                best_pi, best_fi = pi, fi
                best_fact = candidate

        # Mark all others as duplicates
        for pi, fi in locations:
            if (pi, fi) == (best_pi, best_fi):
                continue
            dup_fact = packs[pi].facts[fi]
            val = dup_fact.value if isinstance(dup_fact.value, str) else ", ".join(dup_fact.value)
            result.merged.append({
                "key": key,
                "value": val,
                "removed_from": packs[pi].name,
                "kept_in": packs[best_pi].name,
            })

        if not dry_run:
            # Remove duplicates (iterate in reverse to preserve indices)
            to_remove: dict[int, set[int]] = defaultdict(set)
            for pi, fi in locations:
                if (pi, fi) != (best_pi, best_fi):
                    to_remove[pi].add(fi)

            for pi, indices in to_remove.items():
                packs[pi].facts = [
                    f for i, f in enumerate(packs[pi].facts) if i not in indices
                ]
                result.removed += len(indices)
                if packs[pi].name not in result.packs_modified:
                    result.packs_modified.append(packs[pi].name)


def _find_contradictions(packs: list[ContextPack], result: ConsolidateResult):
    """Find facts with the same key but different values across packs."""
    key_values: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for pack in packs:
        for fact in pack.facts:
            norm = _normalize_value(fact.value)
            key_values[fact.key].append((pack.name, norm))

    for key, entries in key_values.items():
        unique_values = set(v for _, v in entries)
        if len(unique_values) > 1:
            packs_involved = [pack_name for pack_name, _ in entries]
            values_involved = [v for _, v in entries]
            result.contradictions.append({
                "key": key,
                "packs": packs_involved,
                "values": values_involved,
            })


def _find_similar_facts(
    packs: list[ContextPack], result: ConsolidateResult, dry_run: bool
):
    """Find facts with similar values within the same pack."""
    for pack in packs:
        to_remove: set[int] = set()

        for i, fact_a in enumerate(pack.facts):
            if i in to_remove:
                continue
            for j, fact_b in enumerate(pack.facts):
                if j <= i or j in to_remove:
                    continue
                # Same key, similar value
                if fact_a.key == fact_b.key:
                    continue  # Already caught by cross-pack check
                # Different keys, but very similar values
                norm_a = _normalize_value(fact_a.value)
                norm_b = _normalize_value(fact_b.value)
                sim = _similarity(norm_a, norm_b)
                if sim >= SIMILARITY_THRESHOLD and fact_a.key != fact_b.key:
                    # Keep the one with higher confidence
                    if _is_better_fact(fact_a, fact_b):
                        to_remove.add(j)
                        removed_fact = fact_b
                        kept_fact = fact_a
                    else:
                        to_remove.add(i)
                        removed_fact = fact_a
                        kept_fact = fact_b

                    val = removed_fact.value if isinstance(removed_fact.value, str) else ", ".join(removed_fact.value)
                    result.merged.append({
                        "key": removed_fact.key,
                        "value": val,
                        "removed_from": pack.name,
                        "kept_in": f"{pack.name} (as {kept_fact.key})",
                        "similarity": f"{sim:.0%}",
                    })

        if not dry_run and to_remove:
            pack.facts = [f for i, f in enumerate(pack.facts) if i not in to_remove]
            result.removed += len(to_remove)
            if pack.name not in result.packs_modified:
                result.packs_modified.append(pack.name)


def _is_better_fact(a: Fact, b: Fact) -> bool:
    """Return True if fact `a` is better quality than fact `b`."""
    # Higher confidence wins
    conf_order = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
    if conf_order.get(a.confidence, 2) != conf_order.get(b.confidence, 2):
        return conf_order.get(a.confidence, 2) < conf_order.get(b.confidence, 2)

    # More recent wins
    a_date = a.updated_at or datetime.min
    b_date = b.updated_at or datetime.min
    return a_date >= b_date


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_decay_report(result: DecayResult) -> str:
    """Format decay results for CLI output."""
    lines: list[str] = []

    lines.append(f"  Checked: {result.total_checked} facts")
    lines.append(f"  Preserved: [green]{result.preserved}[/green]")

    if result.expired:
        lines.append(f"\n  [red]Expired ({len(result.expired)}):[/red]")
        for item in result.expired:
            lines.append(
                f"    [red]✗[/red] [{item['pack']}] {item['key']}: {item['value']}"
                f" — {item['age_days']}d old (TTL: {item['ttl_days']}d)"
            )

    if result.warning:
        lines.append(f"\n  [yellow]Expiring soon ({len(result.warning)}):[/yellow]")
        for item in result.warning:
            lines.append(
                f"    [yellow]⚡[/yellow] [{item['pack']}] {item['key']}: {item['value']}"
                f" — {item['remaining_days']}d remaining"
            )

    if not result.expired and not result.warning:
        lines.append("\n  [green]✦ All facts are fresh.[/green]")

    return "\n".join(lines)


def format_consolidate_report(result: ConsolidateResult) -> str:
    """Format consolidation results for CLI output."""
    lines: list[str] = []

    if result.merged:
        lines.append(f"  [cyan]Duplicates found ({len(result.merged)}):[/cyan]")
        for item in result.merged:
            sim = f" ({item['similarity']})" if "similarity" in item else ""
            lines.append(
                f"    [cyan]↳[/cyan] {item['key']}: {item['value']}"
                f" — remove from [bold]{item['removed_from']}[/bold],"
                f" keep in [bold]{item['kept_in']}[/bold]{sim}"
            )

    if result.contradictions:
        lines.append(f"\n  [yellow]Contradictions ({len(result.contradictions)}):[/yellow]")
        for item in result.contradictions:
            lines.append(f"    [yellow]⚡[/yellow] {item['key']}:")
            for pack_name, value in zip(item["packs"], item["values"]):
                lines.append(f"       [{pack_name}] = {value}")

    if result.removed > 0:
        lines.append(f"\n  [green]Removed {result.removed} redundant facts[/green]")
        lines.append(f"  Modified packs: {', '.join(result.packs_modified)}")

    if not result.merged and not result.contradictions:
        lines.append("  [green]✦ All packs are clean. No duplicates or contradictions.[/green]")

    return "\n".join(lines)
