"""
aura.doctor — Pack health checker.

Analyzes your context packs and reports:
  - Bloated packs (too many facts)
  - Stale facts (old, likely outdated)
  - Duplicate or redundant facts across packs
  - Missing recommended fields
  - Empty packs with no value

Keeps your context lean and accurate over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aura.schema import ContextPack

# ---------------------------------------------------------------------------
# Health thresholds
# ---------------------------------------------------------------------------
MAX_FACTS_RECOMMENDED = 40
MAX_RULES_RECOMMENDED = 15
STALE_DAYS = 90  # Facts older than this are flagged


# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    severity: str  # "warning" or "info"
    pack: str
    message: str
    suggestion: str = ""


@dataclass
class HealthReport:
    issues: list[Issue] = field(default_factory=list)
    score: int = 100  # 0-100 health score

    @property
    def is_healthy(self) -> bool:
        return self.score >= 80

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "info"]


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------
def diagnose(packs: list[ContextPack]) -> HealthReport:
    """Run all health checks on a list of context packs."""
    report = HealthReport()

    if not packs:
        report.issues.append(Issue(
            severity="warning",
            pack="(none)",
            message="No context packs found",
            suggestion="Run 'aura scan' or 'aura quickstart' to create your first pack",
        ))
        report.score = 0
        return report

    _check_pack_sizes(packs, report)
    _check_empty_packs(packs, report)
    _check_duplicates_across_packs(packs, report)
    _check_missing_recommended(packs, report)
    _check_stale_facts(packs, report)
    _check_no_rules(packs, report)

    # Calculate score
    warning_count = len(report.warnings)
    info_count = len(report.infos)
    penalty = (warning_count * 10) + (info_count * 3)
    report.score = max(0, 100 - penalty)

    return report


def _check_pack_sizes(packs: list[ContextPack], report: HealthReport):
    """Flag packs that are too large."""
    for pack in packs:
        if len(pack.facts) > MAX_FACTS_RECOMMENDED:
            report.issues.append(Issue(
                severity="warning",
                pack=pack.name,
                message=f"Pack has {len(pack.facts)} facts (recommended max: {MAX_FACTS_RECOMMENDED})",
                suggestion="Remove outdated or redundant facts. Lean packs = better AI responses.",
            ))
        if len(pack.rules) > MAX_RULES_RECOMMENDED:
            report.issues.append(Issue(
                severity="info",
                pack=pack.name,
                message=f"Pack has {len(pack.rules)} rules (recommended max: {MAX_RULES_RECOMMENDED})",
                suggestion="Consolidate similar rules. Too many rules dilute their impact.",
            ))


def _check_empty_packs(packs: list[ContextPack], report: HealthReport):
    """Flag packs with no meaningful content."""
    for pack in packs:
        if not pack.facts and not pack.rules:
            report.issues.append(Issue(
                severity="warning",
                pack=pack.name,
                message="Pack is empty — no facts or rules",
                suggestion=f"Add content: 'aura edit {pack.name}' or delete: 'aura delete {pack.name}'",
            ))


def _check_duplicates_across_packs(packs: list[ContextPack], report: HealthReport):
    """Find facts that appear in multiple packs."""
    fact_locations: dict[str, list[str]] = {}
    for pack in packs:
        for fact in pack.facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(sorted(fact.value))
            key = f"{fact.key}={val}"
            if key not in fact_locations:
                fact_locations[key] = []
            fact_locations[key].append(pack.name)

    for key, locations in fact_locations.items():
        if len(locations) > 1:
            report.issues.append(Issue(
                severity="info",
                pack=", ".join(locations),
                message=f"Duplicate fact across packs: {key.split('=')[0]}",
                suggestion="Keep the fact in the most relevant pack and remove from others.",
            ))


def _check_missing_recommended(packs: list[ContextPack], report: HealthReport):
    """Check for recommended fields that are missing."""
    {p.name for p in packs}

    # Check if user has basic packs
    if not any(p.scope == "development" for p in packs):
        report.issues.append(Issue(
            severity="info",
            pack="(missing)",
            message="No development context pack found",
            suggestion="Run 'aura scan' to auto-generate one from your machine.",
        ))

    # Check if packs have descriptions
    for pack in packs:
        if not pack.meta.description:
            report.issues.append(Issue(
                severity="info",
                pack=pack.name,
                message="Pack has no description",
                suggestion=f"Add a description: 'aura edit {pack.name}'",
            ))


def _check_stale_facts(packs: list[ContextPack], report: HealthReport):
    """Flag facts that haven't been updated in a long time."""
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)

    for pack in packs:
        if pack.meta.updated_at and pack.meta.updated_at < cutoff:
            days_old = (datetime.now() - pack.meta.updated_at).days
            report.issues.append(Issue(
                severity="info",
                pack=pack.name,
                message=f"Pack hasn't been updated in {days_old} days",
                suggestion=f"Review and refresh: 'aura edit {pack.name}' or re-scan: 'aura scan'",
            ))


def _check_no_rules(packs: list[ContextPack], report: HealthReport):
    """Flag packs with facts but no rules."""
    for pack in packs:
        if pack.facts and not pack.rules:
            report.issues.append(Issue(
                severity="info",
                pack=pack.name,
                message="Pack has facts but no rules",
                suggestion="Rules tell AI how to behave. Add some: 'aura edit " + pack.name + "'",
            ))


def format_report(report: HealthReport) -> str:
    """Format a health report as a human-readable string."""
    lines: list[str] = []

    # Score
    if report.score >= 90:
        lines.append(f"  Health score: [bold green]{report.score}/100[/bold green] — excellent")
    elif report.score >= 70:
        lines.append(f"  Health score: [bold yellow]{report.score}/100[/bold yellow] — good, minor issues")
    elif report.score >= 50:
        lines.append(f"  Health score: [bold yellow]{report.score}/100[/bold yellow] — needs attention")
    else:
        lines.append(f"  Health score: [bold red]{report.score}/100[/bold red] — needs work")

    if not report.issues:
        lines.append("\n  [green]✦ All packs are healthy.[/green]")
        return "\n".join(lines)

    if report.warnings:
        lines.append(f"\n  [yellow]Warnings ({len(report.warnings)}):[/yellow]")
        for issue in report.warnings:
            lines.append(f"    [yellow]⚡[/yellow] [{issue.pack}] {issue.message}")
            if issue.suggestion:
                lines.append(f"       [dim]{issue.suggestion}[/dim]")

    if report.infos:
        lines.append(f"\n  [dim]Suggestions ({len(report.infos)}):[/dim]")
        for issue in report.infos:
            lines.append(f"    [dim]○[/dim] [{issue.pack}] {issue.message}")
            if issue.suggestion:
                lines.append(f"       [dim]{issue.suggestion}[/dim]")

    return "\n".join(lines)
