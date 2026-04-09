"""
aura.audit — Secret & sensitive data detection.

Scans context packs for accidentally leaked credentials, API keys,
tokens, emails, IPs, and other sensitive patterns that should NEVER
be served to an LLM.

Usage:
    aura audit           # Check all packs
    aura audit --fix     # Auto-redact found secrets
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    CRITICAL = "critical"  # API keys, tokens, passwords
    WARNING = "warning"    # Emails, IPs, private paths
    INFO = "info"          # Potential PII, nothing confirmed


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    severity: Severity
    pack: str
    fact_key: str
    pattern_name: str
    matched_value: str  # Redacted preview
    suggestion: str


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def is_clean(self) -> bool:
        return self.critical_count == 0

    @property
    def total(self) -> int:
        return len(self.findings)


# ---------------------------------------------------------------------------
# Secret patterns
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, str, Severity, str]] = [
    # (name, regex, severity, suggestion)

    # AWS
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}", Severity.CRITICAL,
     "Remove AWS key. Use environment variables or AWS profiles instead."),
    ("AWS Secret Key", r"(?:aws_secret_access_key|secret_key)\s*[=:]\s*[A-Za-z0-9/+=]{40}", Severity.CRITICAL,
     "Remove AWS secret. Never store credentials in context packs."),

    # GitHub
    ("GitHub Token (ghp)", r"ghp_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove GitHub token. Regenerate it — this one may be compromised."),
    ("GitHub Token (gho)", r"gho_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove GitHub OAuth token."),
    ("GitHub Token (ghu)", r"ghu_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove GitHub user-to-server token."),
    ("GitHub Token (ghs)", r"ghs_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove GitHub server-to-server token."),
    ("GitHub Token (ghr)", r"ghr_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove GitHub refresh token."),
    ("GitHub PAT (fine-grained)", r"github_pat_[A-Za-z0-9_]{82}", Severity.CRITICAL,
     "Remove GitHub fine-grained personal access token."),

    # OpenAI / Anthropic / AI providers
    ("OpenAI API Key", r"sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}", Severity.CRITICAL,
     "Remove OpenAI API key."),
    ("OpenAI Key (proj)", r"sk-proj-[A-Za-z0-9_-]{40,}", Severity.CRITICAL,
     "Remove OpenAI project API key."),
    ("Anthropic API Key", r"sk-ant-[A-Za-z0-9_-]{40,}", Severity.CRITICAL,
     "Remove Anthropic API key."),

    # Slack
    ("Slack Bot Token", r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24}", Severity.CRITICAL,
     "Remove Slack bot token."),
    ("Slack User Token", r"xoxp-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,32}", Severity.CRITICAL,
     "Remove Slack user token."),
    ("Slack Webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+", Severity.CRITICAL,
     "Remove Slack webhook URL."),

    # Google
    ("Google API Key", r"AIza[0-9A-Za-z_-]{35}", Severity.CRITICAL,
     "Remove Google API key."),

    # Stripe
    ("Stripe Secret Key", r"sk_live_[0-9a-zA-Z]{24,}", Severity.CRITICAL,
     "Remove Stripe secret key."),
    ("Stripe Publishable", r"pk_live_[0-9a-zA-Z]{24,}", Severity.WARNING,
     "Publishable key is less sensitive, but still consider removing."),

    # Generic patterns
    ("Private Key Block", r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", Severity.CRITICAL,
     "Remove private key. Never store cryptographic keys in context."),
    ("Generic Secret Assignment", r"(?:password|secret|token|api_key|apikey)\s*[=:]\s*['\"][^'\"]{8,}['\"]", Severity.CRITICAL,
     "Remove hardcoded credential."),
    ("Bearer Token", r"Bearer\s+[A-Za-z0-9_-]{20,}", Severity.CRITICAL,
     "Remove bearer token."),

    # PII / sensitive data
    ("Email Address", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", Severity.WARNING,
     "Consider removing email — LLMs may leak it in responses."),
    ("Private IPv4", r"(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}", Severity.WARNING,
     "Private IP detected. Consider removing internal network details."),
    ("SSH Connection", r"ssh\s+\S+@\S+", Severity.WARNING,
     "SSH connection string detected. Remove server access details."),

    # Database connection strings
    ("Database URL", r"(?:postgres|mysql|mongodb|redis)://[^\s]+", Severity.CRITICAL,
     "Remove database connection string."),

    # npm tokens
    ("npm Token", r"npm_[A-Za-z0-9]{36}", Severity.CRITICAL,
     "Remove npm authentication token."),

    # PyPI tokens
    ("PyPI Token", r"pypi-[A-Za-z0-9_-]{50,}", Severity.CRITICAL,
     "Remove PyPI API token."),

    # Heroku
    ("Heroku API Key", r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", Severity.INFO,
     "UUID detected — verify it's not a Heroku or service API key."),
]

# Compile patterns for performance
_COMPILED_PATTERNS: list[tuple[str, re.Pattern, Severity, str]] = [
    (name, re.compile(pattern), severity, suggestion)
    for name, pattern, severity, suggestion in SECRET_PATTERNS
]


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------
def _redact(value: str, keep_chars: int = 4) -> str:
    """Redact a matched value, keeping only the first few chars for identification."""
    if len(value) <= keep_chars + 3:
        return "***REDACTED***"
    return value[:keep_chars] + "..." + "*" * 8


def _redact_in_text(text: str, pattern: re.Pattern) -> str:
    """Replace all matches of a pattern in text with redacted versions."""
    def replacer(match):
        return _redact(match.group(0))
    return pattern.sub(replacer, text)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
def scan_value(value: str | list[str], pack_name: str, fact_key: str) -> list[Finding]:
    """Scan a single fact value for secrets."""
    findings: list[Finding] = []
    text = value if isinstance(value, str) else " ".join(value)

    for name, pattern, severity, suggestion in _COMPILED_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # Skip false positives: UUIDs in non-sensitive contexts
            if name == "Heroku API Key" and fact_key in (
                "meta.schema_version", "meta.created_at", "meta.updated_at"
            ):
                continue

            findings.append(Finding(
                severity=severity,
                pack=pack_name,
                fact_key=fact_key,
                pattern_name=name,
                matched_value=_redact(match),
                suggestion=suggestion,
            ))

    return findings


def audit_packs(packs: list) -> AuditReport:
    """Run secret detection on all context packs."""
    report = AuditReport()

    for pack in packs:
        # Scan facts
        for fact in pack.facts:
            findings = scan_value(fact.value, pack.name, fact.key)
            report.findings.extend(findings)

        # Scan rules
        for rule in pack.rules:
            findings = scan_value(rule.instruction, pack.name, f"rule:{rule.instruction[:30]}")
            report.findings.extend(findings)

        # Scan meta description
        if pack.meta.description:
            findings = scan_value(pack.meta.description, pack.name, "meta.description")
            report.findings.extend(findings)

    return report


def redact_packs(packs: list) -> tuple[list, int]:
    """Auto-redact secrets in packs. Returns (modified_packs, redaction_count)."""
    count = 0

    for pack in packs:
        for fact in pack.facts:
            for _, pattern, severity, _ in _COMPILED_PATTERNS:
                if severity != Severity.CRITICAL:
                    continue
                text = fact.value if isinstance(fact.value, str) else " ".join(fact.value)
                if pattern.search(text):
                    if isinstance(fact.value, str):
                        new_val = _redact_in_text(fact.value, pattern)
                        if new_val != fact.value:
                            fact.value = new_val
                            count += 1
                    elif isinstance(fact.value, list):
                        new_list = [_redact_in_text(v, pattern) for v in fact.value]
                        if new_list != fact.value:
                            fact.value = new_list
                            count += 1

    return packs, count


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------
def format_audit_report(report: AuditReport) -> str:
    """Format an audit report for terminal display."""
    lines: list[str] = []

    if report.is_clean and report.warning_count == 0:
        lines.append("  [bold green]✦ All clean — no secrets detected.[/bold green]")
        if report.findings:
            lines.append(f"\n  [dim]({len(report.findings)} low-severity info items)[/dim]")
        return "\n".join(lines)

    if report.critical_count:
        lines.append(f"  [bold red]🚨 {report.critical_count} CRITICAL finding(s)[/bold red]")
        lines.append("  [red]These MUST be removed before serving to any LLM.[/red]\n")
        for f in report.findings:
            if f.severity == Severity.CRITICAL:
                lines.append(f"    [red]✗[/red] [{f.pack}] {f.fact_key}")
                lines.append(f"      {f.pattern_name}: {f.matched_value}")
                lines.append(f"      [dim]{f.suggestion}[/dim]\n")

    if report.warning_count:
        lines.append(f"\n  [yellow]⚡ {report.warning_count} warning(s)[/yellow]\n")
        for f in report.findings:
            if f.severity == Severity.WARNING:
                lines.append(f"    [yellow]![/yellow] [{f.pack}] {f.fact_key}")
                lines.append(f"      {f.pattern_name}: {f.matched_value}")
                lines.append(f"      [dim]{f.suggestion}[/dim]")

    info_count = sum(1 for f in report.findings if f.severity == Severity.INFO)
    if info_count:
        lines.append(f"\n  [dim]{info_count} info-level item(s) — review with aura audit --verbose[/dim]")

    if report.critical_count:
        lines.append("\n  [bold]Fix:[/bold] Run [cyan]aura audit --fix[/cyan] to auto-redact critical secrets.")

    return "\n".join(lines)
