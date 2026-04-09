"""
aura.diff — Compare context packs.

Compares two context packs or a context pack against a platform's
memory export, showing what's different, missing, or conflicting.

This is how users audit what each AI platform "knows" about them
versus their canonical aura context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aura.schema import ContextPack, Fact


@dataclass
class DiffResult:
    """Result of comparing two context packs."""
    # Facts in source but not in target
    only_in_source: list[Fact] = field(default_factory=list)
    # Facts in target but not in source
    only_in_target: list[Fact] = field(default_factory=list)
    # Facts with same key but different values
    conflicts: list[tuple[Fact, Fact]] = field(default_factory=list)
    # Facts that match
    matching: list[Fact] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.only_in_source or self.only_in_target or self.conflicts)

    @property
    def summary(self) -> str:
        parts = []
        if self.matching:
            parts.append(f"{len(self.matching)} matching")
        if self.only_in_source:
            parts.append(f"{len(self.only_in_source)} only in source")
        if self.only_in_target:
            parts.append(f"{len(self.only_in_target)} only in target")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts")
        return ", ".join(parts)


def diff_packs(
    source: ContextPack,
    target: ContextPack,
) -> DiffResult:
    """
    Compare two context packs fact-by-fact.

    Args:
        source: The "canonical" pack (your local aura context)
        target: The "comparison" pack (e.g. imported from a platform)

    Returns:
        DiffResult with categorized differences
    """
    result = DiffResult()

    source_keys = {f.key: f for f in source.facts}
    target_keys = {f.key: f for f in target.facts}

    all_keys = set(source_keys.keys()) | set(target_keys.keys())

    for key in sorted(all_keys):
        in_source = source_keys.get(key)
        in_target = target_keys.get(key)

        if in_source and not in_target:
            result.only_in_source.append(in_source)
        elif in_target and not in_source:
            result.only_in_target.append(in_target)
        elif in_source and in_target:
            if _values_match(in_source.value, in_target.value):
                result.matching.append(in_source)
            else:
                result.conflicts.append((in_source, in_target))

    return result


def _values_match(a: str | list[str], b: str | list[str]) -> bool:
    """Check if two fact values are equivalent."""
    if isinstance(a, list) and isinstance(b, list):
        return set(a) == set(b)
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    # Type mismatch — try normalizing
    if isinstance(a, list):
        a = ", ".join(sorted(a))
    if isinstance(b, list):
        b = ", ".join(sorted(b))
    return str(a).strip().lower() == str(b).strip().lower()


def format_diff(
    result: DiffResult,
    source_name: str = "local",
    target_name: str = "platform",
) -> str:
    """Format a DiffResult as a human-readable string."""
    lines: list[str] = []
    lines.append(f"Diff: {source_name} ↔ {target_name}")
    lines.append(f"  {result.summary}")
    lines.append("")

    if result.matching:
        lines.append(f"✓ Matching ({len(result.matching)}):")
        for fact in result.matching:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            lines.append(f"    {fact.key}: {val}")
        lines.append("")

    if result.conflicts:
        lines.append(f"⚡ Conflicts ({len(result.conflicts)}):")
        for source_fact, target_fact in result.conflicts:
            s_val = source_fact.value if isinstance(source_fact.value, str) else ", ".join(source_fact.value)
            t_val = target_fact.value if isinstance(target_fact.value, str) else ", ".join(target_fact.value)
            lines.append(f"    {source_fact.key}:")
            lines.append(f"      {source_name}: {s_val}")
            lines.append(f"      {target_name}: {t_val}")
        lines.append("")

    if result.only_in_source:
        lines.append(f"← Only in {source_name} ({len(result.only_in_source)}):")
        for fact in result.only_in_source:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            lines.append(f"    + {fact.key}: {val}")
        lines.append("")

    if result.only_in_target:
        lines.append(f"→ Only in {target_name} ({len(result.only_in_target)}):")
        for fact in result.only_in_target:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            lines.append(f"    + {fact.key}: {val}")
        lines.append("")

    if not result.has_differences:
        lines.append("✦ Packs are in sync.")

    return "\n".join(lines)
