"""
aura.permissions — Per-Agent Pack Permissions

Controls which context packs each AI tool can see.
Config lives in ~/.aura/config.yaml under `agent_permissions`.

Structure:
    agent_permissions:
      claude: [developer, writer, work]
      cursor: [developer]
      chatgpt: [writer, work]
      gemini: [developer, writer]
      default: all          # "all" or a list of pack names

If `agent_permissions` key is absent → all agents see all packs (v0.3.3 behaviour).
If an agent is not listed → falls back to `default`.
`default: all` means all packs visible (the safe default).

Agent identification:
    1. `agent_id` field in MCP tool arguments
    2. `User-Agent` HTTP header (lowercased, first word)
    3. Falls back to "unknown" → uses `default` rules
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML as _YAML

_yaml = _YAML()
_yaml.default_flow_style = False

# Known agent name aliases — maps substrings to canonical names
_AGENT_ALIASES: dict[str, str] = {
    "claude": "claude",
    "cursor": "cursor",
    "chatgpt": "chatgpt",
    "openai": "chatgpt",
    "gemini": "gemini",
    "copilot": "copilot",
    "windsurf": "windsurf",
    "codex": "codex",
}

_DEFAULT_CONFIG: dict = {
    "agent_permissions": {
        "default": "all",
    }
}


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------
def _get_config_path() -> Path:
    from aura.pack import get_config_path
    return get_config_path()


def _load_config() -> dict:
    path = _get_config_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = _yaml.load(f) or {}
        return data
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    path = _get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        _yaml.dump(data, f)


# ---------------------------------------------------------------------------
# Agent identification
# ---------------------------------------------------------------------------
def identify_agent(agent_id: Optional[str] = None, user_agent: Optional[str] = None) -> str:
    """
    Return a canonical agent name from agent_id or User-Agent header.
    Falls back to 'unknown'.
    """
    candidates = []
    if agent_id:
        candidates.append(agent_id.lower().strip())
    if user_agent:
        # Take the first word of the User-Agent string
        candidates.append(user_agent.lower().split("/")[0].split(" ")[0].strip())

    for candidate in candidates:
        for alias, canonical in _AGENT_ALIASES.items():
            if alias in candidate:
                return canonical

    # Return raw candidate if present, else unknown
    return candidates[0] if candidates else "unknown"


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------
def get_allowed_packs(agent: str) -> Optional[list[str]]:
    """
    Return the list of packs visible to this agent.
    Returns None if all packs are allowed ("all" / config absent).
    """
    config = _load_config()
    perms = config.get("agent_permissions")

    # If key is absent → full backwards compatibility, all packs visible
    if perms is None:
        return None

    # Look up agent-specific config first, then default
    agent_rule = perms.get(agent) or perms.get("default", "all")

    if agent_rule == "all":
        return None  # All packs allowed

    if isinstance(agent_rule, list):
        return [str(p) for p in agent_rule]

    # Unexpected value → safe default: all packs
    return None


def is_pack_allowed_for_agent(pack_name: str, agent: str) -> bool:
    """Return True if the given agent can access this pack."""
    allowed = get_allowed_packs(agent)
    if allowed is None:
        return True
    return pack_name in allowed


def filter_packs_for_agent(packs: list, agent: str) -> list:
    """Filter a list of ContextPack objects to those the agent may see."""
    allowed = get_allowed_packs(agent)
    if allowed is None:
        return packs
    return [p for p in packs if p.name in allowed]


# ---------------------------------------------------------------------------
# CRUD for permissions
# ---------------------------------------------------------------------------
def set_agent_permissions(agent: str, pack_names: list[str]) -> None:
    """Set the pack list for an agent."""
    config = _load_config()
    if "agent_permissions" not in config:
        config["agent_permissions"] = {"default": "all"}
    config["agent_permissions"][agent] = pack_names
    _save_config(config)


def set_agent_all(agent: str) -> None:
    """Give an agent access to all packs."""
    config = _load_config()
    if "agent_permissions" not in config:
        config["agent_permissions"] = {"default": "all"}
    config["agent_permissions"][agent] = "all"
    _save_config(config)


def reset_permissions() -> None:
    """Remove all agent_permissions config → back to 'all packs' default."""
    config = _load_config()
    config.pop("agent_permissions", None)
    _save_config(config)


def list_permissions() -> dict:
    """
    Return current permissions as a plain dict.
    Keys are agent names, values are lists or "all".
    Returns {} if no permissions configured.
    """
    config = _load_config()
    return dict(config.get("agent_permissions", {}))
