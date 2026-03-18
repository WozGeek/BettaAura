"""
aura.pack — Context Pack Manager

Handles creating, reading, writing, listing, and validating context packs
on the local filesystem. Packs are stored as YAML files in ~/.aura/packs/.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from aura.schema import ContextPack, Fact, PackMeta, Rule

yaml = YAML()
yaml.default_flow_style = False
yaml.allow_unicode = True


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def get_aura_home() -> Path:
    """Return the aura home directory (~/.aura)."""
    home = Path.home() / ".aura"
    return home


def get_packs_dir() -> Path:
    """Return the packs directory (~/.aura/packs)."""
    return get_aura_home() / "packs"


def get_config_path() -> Path:
    """Return the global config file path."""
    return get_aura_home() / "config.yaml"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def init_aura() -> Path:
    """Initialize the aura directory structure. Returns aura home path."""
    home = get_aura_home()
    packs_dir = get_packs_dir()

    home.mkdir(parents=True, exist_ok=True)
    packs_dir.mkdir(parents=True, exist_ok=True)

    # Create default config if missing
    config_path = get_config_path()
    if not config_path.exists():
        config = {
            "aura": {
                "version": "0.1.0",
                "default_export_format": "system-prompt",
                "editor": None,  # Will use $EDITOR
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config, f)

    return home


def is_initialized() -> bool:
    """Check if aura has been initialized."""
    return get_aura_home().exists() and get_packs_dir().exists()


# ---------------------------------------------------------------------------
# Pack CRUD
# ---------------------------------------------------------------------------
def _pack_path(name: str) -> Path:
    """Get the file path for a named pack."""
    return get_packs_dir() / f"{name}.yaml"


def pack_exists(name: str) -> bool:
    """Check if a pack with this name exists."""
    return _pack_path(name).exists()


def save_pack(pack: ContextPack) -> Path:
    """Save a context pack to disk as YAML. Returns the file path."""
    path = _pack_path(pack.name)

    # Convert to dict for YAML serialization
    data = {
        "name": pack.name,
        "scope": pack.scope,
        "meta": {
            "schema_version": pack.meta.schema_version,
            "created_at": pack.meta.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    }

    if pack.meta.description:
        data["meta"]["description"] = pack.meta.description

    if pack.meta.tags:
        data["meta"]["tags"] = pack.meta.tags

    if pack.facts:
        data["facts"] = []
        for fact in pack.facts:
            fact_data: dict = {
                "key": fact.key,
                "value": fact.value,
            }
            if fact.type.value != "context":
                fact_data["type"] = fact.type.value
            if fact.confidence.value != "high":
                fact_data["confidence"] = fact.confidence.value
            if fact.source:
                fact_data["source"] = fact.source
            data["facts"].append(fact_data)

    if pack.rules:
        data["rules"] = []
        for rule in pack.rules:
            rule_data: dict = {"instruction": rule.instruction}
            if rule.priority > 0:
                rule_data["priority"] = rule.priority
            data["rules"].append(rule_data)

    with open(path, "w") as f:
        yaml.dump(data, f)

    return path


def load_pack(name: str) -> ContextPack:
    """Load a context pack from disk."""
    path = _pack_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Pack '{name}' not found at {path}")

    with open(path) as f:
        data = yaml.load(f)

    # Parse facts
    facts = []
    for f_data in data.get("facts", []):
        facts.append(Fact(
            key=f_data["key"],
            value=f_data["value"],
            type=f_data.get("type", "context"),
            confidence=f_data.get("confidence", "high"),
            source=f_data.get("source"),
        ))

    # Parse rules
    rules = []
    for r_data in data.get("rules", []):
        rules.append(Rule(
            instruction=r_data["instruction"],
            priority=r_data.get("priority", 0),
        ))

    # Parse meta
    meta_data = data.get("meta", {})
    meta = PackMeta(
        schema_version=meta_data.get("schema_version", "0.1.0"),
        created_at=datetime.fromisoformat(meta_data["created_at"]) if "created_at" in meta_data else datetime.now(),
        updated_at=datetime.fromisoformat(meta_data["updated_at"]) if "updated_at" in meta_data else datetime.now(),
        description=meta_data.get("description"),
        tags=meta_data.get("tags", []),
    )

    return ContextPack(
        name=data["name"],
        scope=data["scope"],
        facts=facts,
        rules=rules,
        meta=meta,
    )


def list_packs() -> list[ContextPack]:
    """List all available context packs."""
    packs_dir = get_packs_dir()
    if not packs_dir.exists():
        return []

    packs = []
    for path in sorted(packs_dir.glob("*.yaml")):
        try:
            pack = load_pack(path.stem)
            packs.append(pack)
        except Exception:
            continue  # Skip malformed packs
    return packs


def delete_pack(name: str) -> bool:
    """Delete a context pack. Returns True if deleted."""
    path = _pack_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES: dict[str, dict] = {
    "developer": {
        "scope": "development",
        "description": "Your development context — languages, frameworks, coding style.",
        "facts": [
            {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill"},
            {"key": "languages.learning", "value": ["Rust"], "type": "skill"},
            {"key": "frameworks", "value": ["Next.js", "FastAPI"], "type": "skill"},
            {"key": "editor", "value": "VS Code / Cursor", "type": "preference"},
            {"key": "style.comments", "value": "Minimal — only for non-obvious logic", "type": "style"},
            {"key": "style.formatting", "value": "Prefer explicit types over inference", "type": "style"},
            {"key": "testing", "value": "Integration tests over unit tests when possible", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always use strict TypeScript (no 'any')", "priority": 8},
            {"instruction": "Prefer functional patterns over OOP where reasonable", "priority": 5},
            {"instruction": "Use descriptive variable names — no single letters except in loops", "priority": 6},
            {"instruction": "Add error handling with specific error types, not generic catches", "priority": 7},
        ],
    },
    "writer": {
        "scope": "writing",
        "description": "Your writing style and content preferences.",
        "facts": [
            {"key": "tone", "value": "Direct, no fluff, occasional sharp humor", "type": "style"},
            {"key": "audience", "value": "Technical professionals", "type": "context"},
            {"key": "formatting", "value": "Short paragraphs, concrete examples, minimal headers", "type": "style"},
            {"key": "languages", "value": ["English", "French"], "type": "skill"},
        ],
        "rules": [
            {"instruction": "Avoid corporate jargon and buzzwords", "priority": 8},
            {"instruction": "Use active voice", "priority": 6},
            {"instruction": "Lead with the conclusion, then explain", "priority": 7},
            {"instruction": "Keep paragraphs under 4 sentences", "priority": 5},
        ],
    },
    "researcher": {
        "scope": "research",
        "description": "Your research interests and methodology preferences.",
        "facts": [
            {"key": "domains", "value": ["AI/ML", "distributed systems"], "type": "context"},
            {"key": "methodology", "value": "Evidence-based, prefer primary sources", "type": "style"},
            {"key": "citation_style", "value": "Inline with links", "type": "preference"},
        ],
        "rules": [
            {"instruction": "Always cite sources with links when available", "priority": 8},
            {"instruction": "Distinguish between established facts and speculation", "priority": 9},
            {"instruction": "Present contrarian viewpoints alongside mainstream ones", "priority": 6},
        ],
    },
    "work": {
        "scope": "work",
        "description": "Your professional context — role, company, communication style.",
        "facts": [
            {"key": "role", "value": "Software Engineer", "type": "identity"},
            {"key": "company", "value": "Acme Corp", "type": "identity"},
            {"key": "team", "value": "Platform team", "type": "context"},
            {"key": "communication.style", "value": "Concise, data-driven", "type": "style"},
        ],
        "rules": [
            {"instruction": "Frame recommendations with business impact", "priority": 7},
            {"instruction": "Include time estimates for technical suggestions", "priority": 5},
        ],
    },
}


def create_from_template(template_name: str, pack_name: Optional[str] = None) -> ContextPack:
    """Create a new context pack from a built-in template."""
    if template_name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

    template = TEMPLATES[template_name]
    name = pack_name or template_name

    facts = [Fact(**f, source="template") for f in template["facts"]]
    rules = [Rule(**r) for r in template["rules"]]

    return ContextPack(
        name=name,
        scope=template["scope"],
        facts=facts,
        rules=rules,
        meta=PackMeta(
            description=template["description"],
            tags=[template_name, "template"],
        ),
    )
