"""
aura.schema — The Context Pack Specification

A context pack is a scoped, portable unit of personal AI context.
Each pack describes who you are in a specific domain (dev, writing, work, etc.)
and can be exported to any AI tool's native format.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Schema version — bump on breaking changes
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Scope(str, Enum):
    """Pre-defined scopes. Users can also use custom strings."""
    DEVELOPMENT = "development"
    WRITING = "writing"
    WORK = "work"
    RESEARCH = "research"
    PERSONAL = "personal"
    CREATIVE = "creative"
    FINANCE = "finance"
    HEALTH = "health"
    EDUCATION = "education"


class FactType(str, Enum):
    PREFERENCE = "preference"
    IDENTITY = "identity"
    SKILL = "skill"
    STYLE = "style"
    CONSTRAINT = "constraint"
    CONTEXT = "context"


class Confidence(str, Enum):
    HIGH = "high"        # Explicitly stated by user
    MEDIUM = "medium"    # Inferred with good evidence
    LOW = "low"          # Guessed or tentative


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------
class Fact(BaseModel):
    """A single piece of context knowledge."""
    key: str = Field(
        ...,
        description="Dot-separated key, e.g. 'languages.primary' or 'tone'",
        examples=["languages.primary", "frameworks", "tone", "role"],
    )
    value: str | list[str] = Field(
        ...,
        description="The fact value — a string or list of strings",
    )
    type: FactType = Field(
        default=FactType.CONTEXT,
        description="Category of this fact",
    )
    confidence: Confidence = Field(
        default=Confidence.HIGH,
        description="How confident we are in this fact",
    )
    source: Optional[str] = Field(
        default=None,
        description="Where this fact came from: 'manual', 'chatgpt-import', 'claude-import', etc.",
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        description="When this fact was last updated",
    )


class Rule(BaseModel):
    """An explicit instruction for AI behavior in this scope."""
    instruction: str = Field(
        ...,
        description="A clear directive, e.g. 'Never suggest jQuery'",
        examples=[
            "Always use TypeScript strict mode",
            "Write in active voice",
            "Keep paragraphs under 4 sentences",
        ],
    )
    priority: int = Field(
        default=0,
        description="Higher = more important. Range 0-10.",
        ge=0,
        le=10,
    )


class PackMeta(BaseModel):
    """Metadata about the context pack itself."""
    schema_version: str = Field(default=SCHEMA_VERSION)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this context pack",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Freeform tags for organization",
    )


class ContextPack(BaseModel):
    """
    The root model — a complete, scoped context pack.

    A context pack = facts + rules + metadata, scoped to a domain.
    This is the unit of portability in aura.
    """
    name: str = Field(
        ...,
        description="Unique identifier for this pack, e.g. 'developer', 'writer'",
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    scope: str = Field(
        ...,
        description="Domain scope — use a Scope enum value or a custom string",
    )
    facts: list[Fact] = Field(
        default_factory=list,
        description="Known facts about the user in this scope",
    )
    rules: list[Rule] = Field(
        default_factory=list,
        description="Explicit behavioral instructions for AI in this scope",
    )
    meta: PackMeta = Field(
        default_factory=PackMeta,
        description="Pack metadata",
    )

    def to_system_prompt(self) -> str:
        """Render this pack as a plain-text system prompt fragment."""
        lines: list[str] = []
        lines.append(f"## Context: {self.name} ({self.scope})")
        if self.meta.description:
            lines.append(f"\n{self.meta.description}\n")

        if self.facts:
            lines.append("\n### Known facts")
            for fact in sorted(self.facts, key=lambda f: f.key):
                val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                lines.append(f"- **{fact.key}**: {val}")

        if self.rules:
            lines.append("\n### Rules & preferences")
            for rule in sorted(self.rules, key=lambda r: -r.priority):
                prefix = f"[P{rule.priority}] " if rule.priority > 0 else ""
                lines.append(f"- {prefix}{rule.instruction}")

        return "\n".join(lines)

    def to_cursorrules(self) -> str:
        """Render as a .cursorrules file."""
        lines: list[str] = []
        lines.append(f"# Aura Context: {self.name}")
        lines.append(f"# Scope: {self.scope}")
        lines.append(f"# Generated by aura v{SCHEMA_VERSION}")
        lines.append("")

        if self.facts:
            lines.append("## User Context")
            for fact in self.facts:
                val = fact.value if isinstance(fact.value, str) else ", ".join(fact.value)
                lines.append(f"- {fact.key}: {val}")
            lines.append("")

        if self.rules:
            lines.append("## Rules")
            for rule in sorted(self.rules, key=lambda r: -r.priority):
                lines.append(f"- {rule.instruction}")
            lines.append("")

        return "\n".join(lines)
