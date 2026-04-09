"""
Export context packs as ChatGPT Custom Instructions.

ChatGPT has two instruction fields:
1. "What would you like ChatGPT to know about you?"
2. "How would you like ChatGPT to respond?"

This exporter maps facts → field 1, rules → field 2.
"""

from __future__ import annotations

from aura.schema import SCHEMA_VERSION, ContextPack


def export_chatgpt_instructions(packs: list[ContextPack]) -> dict[str, str]:
    """
    Export context packs as ChatGPT Custom Instructions.

    Returns:
        Dict with keys 'about_you' and 'response_style'
    """
    about_lines: list[str] = []
    response_lines: list[str] = []

    for pack in packs:
        if pack.facts:
            about_lines.append(f"[{pack.scope.upper()}]")
            for fact in pack.facts:
                val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                about_lines.append(f"- {fact.key}: {val}")
            about_lines.append("")

        if pack.rules:
            response_lines.append(f"[{pack.scope.upper()}]")
            for rule in sorted(pack.rules, key=lambda r: -r.priority):
                response_lines.append(f"- {rule.instruction}")
            response_lines.append("")

    return {
        "about_you": "\n".join(about_lines).strip(),
        "response_style": "\n".join(response_lines).strip(),
    }


def export_chatgpt_instructions_text(packs: list[ContextPack]) -> str:
    """Export as formatted text for easy copy-paste."""
    result = export_chatgpt_instructions(packs)

    lines = [
        f"# Aura → ChatGPT Custom Instructions (v{SCHEMA_VERSION})",
        "",
        "=" * 60,
        "FIELD 1: What would you like ChatGPT to know about you?",
        "=" * 60,
        "",
        result["about_you"],
        "",
        "=" * 60,
        "FIELD 2: How would you like ChatGPT to respond?",
        "=" * 60,
        "",
        result["response_style"],
        "",
    ]

    return "\n".join(lines)
