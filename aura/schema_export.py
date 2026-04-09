"""
aura.schema_export — JSON Schema Generator & Validator

Generates a formal JSON Schema from the Pydantic models in schema.py.
This schema is the official spec for context packs — it enables validation,
editor auto-complete, and ecosystem interoperability.

Usage:
    from aura.schema_export import generate_schema, validate_pack_data
    schema = generate_schema()
    errors = validate_pack_data(raw_dict)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema definition (kept in sync with schema.py models)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "0.3.4"
SCHEMA_ID = "https://raw.githubusercontent.com/WozGeek/aura-ctx/main/context-pack.schema.json"

CONTEXT_PACK_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": SCHEMA_ID,
    "title": "ContextPack",
    "description": "An aura context pack — a scoped, portable unit of personal AI context.",
    "type": "object",
    "required": ["name", "scope"],
    "additionalProperties": False,
    "properties": {
        "name": {
            "type": "string",
            "description": "Unique identifier for this pack (lowercase alphanumeric, hyphens, underscores).",
            "pattern": "^[a-z][a-z0-9_-]*$",
            "examples": ["developer", "writer", "work"],
        },
        "scope": {
            "type": "string",
            "description": "Domain scope for this context pack.",
            "examples": [
                "development", "writing", "work",
                "research", "personal", "creative",
                "finance", "health", "education",
            ],
        },
        "meta": {
            "type": "object",
            "description": "Metadata about the pack.",
            "additionalProperties": False,
            "properties": {
                "schema_version": {
                    "type": "string",
                    "description": "aura schema version this pack was created with.",
                    "examples": ["0.1.0"],
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "ISO 8601 timestamp of pack creation.",
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "ISO 8601 timestamp of last update.",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of this context pack.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Freeform tags for organization.",
                    "examples": [["template", "developer"]],
                },
            },
        },
        "facts": {
            "type": "array",
            "description": "Known facts about the user in this scope.",
            "items": {
                "$ref": "#/$defs/Fact",
            },
        },
        "rules": {
            "type": "array",
            "description": "Explicit behavioral instructions for AI in this scope.",
            "items": {
                "$ref": "#/$defs/Rule",
            },
        },
    },
    "$defs": {
        "Fact": {
            "title": "Fact",
            "description": "A single piece of context knowledge.",
            "type": "object",
            "required": ["key", "value"],
            "additionalProperties": False,
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Dot-separated key, e.g. 'languages.primary' or 'tone'.",
                    "examples": ["languages.primary", "tone", "role", "frameworks"],
                },
                "value": {
                    "description": "The fact value — a string or list of strings.",
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                    ],
                    "examples": ["Python", ["Python", "TypeScript"]],
                },
                "type": {
                    "type": "string",
                    "description": "Category of this fact.",
                    "enum": ["preference", "identity", "skill", "style", "constraint", "context"],
                    "default": "context",
                },
                "confidence": {
                    "type": "string",
                    "description": "How confident we are in this fact.",
                    "enum": ["high", "medium", "low"],
                    "default": "high",
                },
                "source": {
                    "type": "string",
                    "description": "Where this fact came from.",
                    "examples": ["manual", "chatgpt-import", "claude-import", "scanner", "template"],
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When this fact was last updated.",
                },
            },
        },
        "Rule": {
            "title": "Rule",
            "description": "An explicit instruction for AI behavior in this scope.",
            "type": "object",
            "required": ["instruction"],
            "additionalProperties": False,
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "A clear directive for AI behavior.",
                    "examples": [
                        "Always use TypeScript strict mode",
                        "Write in active voice",
                        "Keep paragraphs under 4 sentences",
                    ],
                },
                "priority": {
                    "type": "integer",
                    "description": "Higher = more important. Range 0-10.",
                    "minimum": 0,
                    "maximum": 10,
                    "default": 0,
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_schema() -> dict[str, Any]:
    """Return the full JSON Schema dict for context packs."""
    return CONTEXT_PACK_SCHEMA


def schema_to_json(indent: int = 2) -> str:
    """Serialize the JSON Schema to a JSON string."""
    return json.dumps(CONTEXT_PACK_SCHEMA, indent=indent)


def validate_pack_data(data: dict[str, Any]) -> list[str]:
    """
    Validate a raw dict against the context pack schema.

    Returns a list of error messages. Empty list = valid.
    Does NOT raise — always returns errors as strings for clear UX.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Root value must be a mapping (dict), got: " + type(data).__name__]

    # Required fields
    for required in ["name", "scope"]:
        if required not in data:
            errors.append(f"Missing required field: '{required}'")

    # name pattern
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str):
            errors.append(f"'name' must be a string, got: {type(name).__name__}")
        elif not name or not name[0].islower():
            errors.append(f"'name' must start with a lowercase letter, got: {name!r}")
        elif not all(c.isalnum() or c in "-_" for c in name):
            errors.append(
                f"'name' must contain only lowercase letters, digits, hyphens, "
                f"or underscores, got: {name!r}"
            )

    # scope
    if "scope" in data and not isinstance(data["scope"], str):
        errors.append(f"'scope' must be a string, got: {type(data['scope']).__name__}")

    # facts
    if "facts" in data:
        facts = data["facts"]
        if not isinstance(facts, list):
            errors.append(f"'facts' must be a list, got: {type(facts).__name__}")
        else:
            for i, fact in enumerate(facts):
                fact_errors = _validate_fact(fact, index=i)
                errors.extend(fact_errors)

    # rules
    if "rules" in data:
        rules = data["rules"]
        if not isinstance(rules, list):
            errors.append(f"'rules' must be a list, got: {type(rules).__name__}")
        else:
            for i, rule in enumerate(rules):
                rule_errors = _validate_rule(rule, index=i)
                errors.extend(rule_errors)

    return errors


def _validate_fact(fact: Any, index: int) -> list[str]:
    """Validate a single fact dict. Returns list of error strings."""
    errors: list[str] = []
    prefix = f"facts[{index}]"

    if not isinstance(fact, dict):
        return [f"{prefix}: must be a mapping, got {type(fact).__name__}"]

    # Required
    for req in ["key", "value"]:
        if req not in fact:
            errors.append(f"{prefix}: missing required field '{req}'")

    # key
    if "key" in fact and not isinstance(fact["key"], str):
        errors.append(f"{prefix}.key: must be a string, got {type(fact['key']).__name__}")

    # value
    if "value" in fact:
        val = fact["value"]
        if not isinstance(val, (str, list)):
            errors.append(
                f"{prefix}.value: must be a string or list of strings, "
                f"got {type(val).__name__}"
            )
        elif isinstance(val, list):
            for j, item in enumerate(val):
                if not isinstance(item, str):
                    errors.append(
                        f"{prefix}.value[{j}]: list items must be strings, "
                        f"got {type(item).__name__}"
                    )
            if len(val) == 0:
                errors.append(f"{prefix}.value: list must have at least 1 item")

    # type enum
    valid_types = {"preference", "identity", "skill", "style", "constraint", "context"}
    if "type" in fact and fact["type"] not in valid_types:
        errors.append(
            f"{prefix}.type: invalid value {fact['type']!r}. "
            f"Must be one of: {', '.join(sorted(valid_types))}"
        )

    # confidence enum
    valid_confidences = {"high", "medium", "low"}
    if "confidence" in fact and fact["confidence"] not in valid_confidences:
        errors.append(
            f"{prefix}.confidence: invalid value {fact['confidence']!r}. "
            f"Must be one of: high, medium, low"
        )

    return errors


def _validate_rule(rule: Any, index: int) -> list[str]:
    """Validate a single rule dict. Returns list of error strings."""
    errors: list[str] = []
    prefix = f"rules[{index}]"

    if not isinstance(rule, dict):
        return [f"{prefix}: must be a mapping, got {type(rule).__name__}"]

    if "instruction" not in rule:
        errors.append(f"{prefix}: missing required field 'instruction'")

    if "instruction" in rule and not isinstance(rule["instruction"], str):
        errors.append(
            f"{prefix}.instruction: must be a string, got {type(rule['instruction']).__name__}"
        )

    if "priority" in rule:
        p = rule["priority"]
        if not isinstance(p, int):
            errors.append(f"{prefix}.priority: must be an integer, got {type(p).__name__}")
        elif not (0 <= p <= 10):
            errors.append(f"{prefix}.priority: must be between 0 and 10, got {p}")

    return errors


def write_schema_file(path: Path | None = None) -> Path:
    """Write context-pack.schema.json to disk. Returns the file path."""
    if path is None:
        path = Path.cwd() / "context-pack.schema.json"
    path.write_text(schema_to_json(), encoding="utf-8")
    return path
