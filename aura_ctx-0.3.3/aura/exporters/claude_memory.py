"""
Export context packs as Claude memory edits.

Claude's memory system stores facts as short text statements.
This exporter converts structured context packs into a list
of memory-edit-compatible statements.
"""

from __future__ import annotations

from aura.schema import SCHEMA_VERSION, ContextPack


def export_claude_memory(packs: list[ContextPack]) -> list[str]:
    """
    Export context packs as a list of Claude memory statements.

    Each statement is a concise fact that can be added to Claude's
    memory via the "Remember that..." interface.

    Returns:
        List of memory statement strings
    """
    statements: list[str] = []

    for pack in packs:
        for fact in pack.facts:
            val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
            # Convert key + value into natural language
            statement = _fact_to_statement(fact.key, val, pack.scope)
            statements.append(statement)

        for rule in pack.rules:
            statements.append(f"User preference ({pack.scope}): {rule.instruction}")

    return statements


def export_claude_memory_text(packs: list[ContextPack]) -> str:
    """Export as formatted text with instructions."""
    statements = export_claude_memory(packs)

    lines = [
        f"# Aura → Claude Memory Export (v{SCHEMA_VERSION})",
        "#",
        "# Add these to Claude's memory by telling Claude:",
        '#   "Please remember that [statement]"',
        "# Or use the memory_user_edits tool to add them programmatically.",
        "#",
        f"# Total statements: {len(statements)}",
        "",
    ]

    for i, stmt in enumerate(statements, 1):
        lines.append(f"{i}. {stmt}")

    return "\n".join(lines) + "\n"


def _fact_to_statement(key: str, value: str, scope: str) -> str:
    """Convert a key-value fact into a natural language statement."""
    # Map common keys to natural phrasing
    key_lower = key.lower()

    if "language" in key_lower and "primary" in key_lower:
        return f"User's primary programming languages are: {value}"
    elif "language" in key_lower and "learning" in key_lower:
        return f"User is currently learning: {value}"
    elif "framework" in key_lower:
        return f"User works with these frameworks: {value}"
    elif "editor" in key_lower:
        return f"User's preferred editor is {value}"
    elif "tone" in key_lower:
        return f"User's preferred tone is: {value}"
    elif "role" in key_lower:
        return f"User's role is: {value}"
    elif "company" in key_lower:
        return f"User works at {value}"
    elif "team" in key_lower:
        return f"User is on the {value}"
    elif "style" in key_lower:
        return f"User's {scope} style preference: {value}"
    elif "audience" in key_lower:
        return f"User's target audience: {value}"
    else:
        return f"User {scope} context — {key}: {value}"
