"""Tests for aura.permissions — per-agent pack visibility."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import aura.permissions as perm_mod
from aura.permissions import (
    filter_packs_for_agent,
    get_allowed_packs,
    identify_agent,
    is_pack_allowed_for_agent,
    list_permissions,
    reset_permissions,
    set_agent_all,
    set_agent_permissions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect config to a temp directory so tests never touch ~/.aura."""
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(perm_mod, "_get_config_path", lambda: config_path)
    yield
    # cleanup is automatic — tmp_path is removed by pytest


def _make_pack(name: str) -> MagicMock:
    p = MagicMock()
    p.name = name
    return p


# ---------------------------------------------------------------------------
# identify_agent
# ---------------------------------------------------------------------------
class TestIdentifyAgent:
    def test_unknown_when_no_input(self):
        assert identify_agent() == "unknown"

    def test_claude_from_agent_id(self):
        assert identify_agent(agent_id="claude") == "claude"

    def test_cursor_from_agent_id(self):
        assert identify_agent(agent_id="cursor") == "cursor"

    def test_chatgpt_from_agent_id(self):
        assert identify_agent(agent_id="chatgpt") == "chatgpt"

    def test_openai_alias_maps_to_chatgpt(self):
        assert identify_agent(agent_id="openai-desktop") == "chatgpt"

    def test_gemini_from_user_agent(self):
        assert identify_agent(user_agent="gemini/1.0") == "gemini"

    def test_cursor_from_user_agent(self):
        assert identify_agent(user_agent="cursor/0.42.0 VSCode/1.87") == "cursor"

    def test_agent_id_takes_priority_over_user_agent(self):
        result = identify_agent(agent_id="claude", user_agent="cursor/1.0")
        assert result == "claude"

    def test_unknown_user_agent_returns_first_word(self):
        result = identify_agent(user_agent="myapp/2.0")
        assert result == "myapp"

    def test_case_insensitive(self):
        assert identify_agent(agent_id="CLAUDE") == "claude"

    def test_windsurf_from_agent_id(self):
        assert identify_agent(agent_id="windsurf") == "windsurf"

    def test_copilot_from_agent_id(self):
        assert identify_agent(agent_id="copilot") == "copilot"


# ---------------------------------------------------------------------------
# get_allowed_packs — no config
# ---------------------------------------------------------------------------
class TestGetAllowedPacksNoConfig:
    def test_no_config_returns_none(self):
        """When config doesn't exist, all packs are allowed (None = unrestricted)."""
        assert get_allowed_packs("claude") is None

    def test_any_agent_returns_none_without_config(self):
        assert get_allowed_packs("cursor") is None
        assert get_allowed_packs("unknown") is None


# ---------------------------------------------------------------------------
# get_allowed_packs — with config
# ---------------------------------------------------------------------------
class TestGetAllowedPacksWithConfig:
    def test_default_all_returns_none(self):
        set_agent_permissions("claude", ["developer", "writer"])
        # default is still "all" implicitly
        assert get_allowed_packs("gemini") is None

    def test_specific_agent_returns_list(self):
        set_agent_permissions("cursor", ["developer"])
        result = get_allowed_packs("cursor")
        assert result == ["developer"]

    def test_multiple_packs(self):
        set_agent_permissions("claude", ["developer", "writer", "work"])
        result = get_allowed_packs("claude")
        assert set(result) == {"developer", "writer", "work"}

    def test_agent_set_to_all_returns_none(self):
        set_agent_all("cursor")
        assert get_allowed_packs("cursor") is None

    def test_unknown_agent_falls_back_to_default(self):
        set_agent_permissions("claude", ["developer"])
        # "newagent" not configured → uses default → all
        assert get_allowed_packs("newagent") is None

    def test_absent_agent_permissions_key_returns_none(self):
        """If agent_permissions is absent from config, all packs visible."""
        # Write a config without agent_permissions
        from ruamel.yaml import YAML as _YAML
        _yaml = _YAML()
        cfg_path = perm_mod._get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w") as f:
            _yaml.dump({"aura": {"version": "0.1.0"}}, f)
        assert get_allowed_packs("claude") is None


# ---------------------------------------------------------------------------
# is_pack_allowed_for_agent
# ---------------------------------------------------------------------------
class TestIsPackAllowedForAgent:
    def test_allowed_when_no_config(self):
        assert is_pack_allowed_for_agent("developer", "claude") is True

    def test_pack_in_list_is_allowed(self):
        set_agent_permissions("claude", ["developer", "writer"])
        assert is_pack_allowed_for_agent("developer", "claude") is True

    def test_pack_not_in_list_is_blocked(self):
        set_agent_permissions("claude", ["developer"])
        assert is_pack_allowed_for_agent("writer", "claude") is False

    def test_all_packs_allowed_when_agent_set_to_all(self):
        set_agent_all("cursor")
        assert is_pack_allowed_for_agent("writer", "cursor") is True
        assert is_pack_allowed_for_agent("developer", "cursor") is True

    def test_unknown_agent_sees_all(self):
        set_agent_permissions("claude", ["developer"])
        # unknown not configured → default=all
        assert is_pack_allowed_for_agent("writer", "unknown") is True

    def test_blocked_pack_returns_false(self):
        set_agent_permissions("cursor", ["developer"])
        assert is_pack_allowed_for_agent("work", "cursor") is False


# ---------------------------------------------------------------------------
# filter_packs_for_agent
# ---------------------------------------------------------------------------
class TestFilterPacksForAgent:
    def test_no_config_returns_all_packs(self):
        packs = [_make_pack("developer"), _make_pack("writer"), _make_pack("work")]
        result = filter_packs_for_agent(packs, "claude")
        assert len(result) == 3

    def test_filters_to_allowed_packs_only(self):
        set_agent_permissions("cursor", ["developer"])
        packs = [_make_pack("developer"), _make_pack("writer"), _make_pack("work")]
        result = filter_packs_for_agent(packs, "cursor")
        assert len(result) == 1
        assert result[0].name == "developer"

    def test_agent_set_to_all_returns_all(self):
        set_agent_all("claude")
        packs = [_make_pack("developer"), _make_pack("writer")]
        result = filter_packs_for_agent(packs, "claude")
        assert len(result) == 2

    def test_empty_pack_list(self):
        set_agent_permissions("claude", ["developer"])
        assert filter_packs_for_agent([], "claude") == []

    def test_no_allowed_packs_installed(self):
        set_agent_permissions("cursor", ["nonexistent"])
        packs = [_make_pack("developer"), _make_pack("writer")]
        result = filter_packs_for_agent(packs, "cursor")
        assert result == []

    def test_multiple_agents_isolated(self):
        set_agent_permissions("claude", ["writer"])
        set_agent_permissions("cursor", ["developer"])
        packs = [_make_pack("developer"), _make_pack("writer")]

        claude_packs = filter_packs_for_agent(packs, "claude")
        cursor_packs = filter_packs_for_agent(packs, "cursor")

        assert [p.name for p in claude_packs] == ["writer"]
        assert [p.name for p in cursor_packs] == ["developer"]


# ---------------------------------------------------------------------------
# set_agent_permissions / set_agent_all
# ---------------------------------------------------------------------------
class TestSetPermissions:
    def test_set_creates_config_entry(self):
        set_agent_permissions("claude", ["developer", "writer"])
        perms = list_permissions()
        assert "claude" in perms
        assert perms["claude"] == ["developer", "writer"]

    def test_set_overwrites_existing(self):
        set_agent_permissions("claude", ["developer"])
        set_agent_permissions("claude", ["writer", "work"])
        perms = list_permissions()
        assert perms["claude"] == ["writer", "work"]

    def test_set_all_stores_all_string(self):
        set_agent_all("gemini")
        perms = list_permissions()
        assert perms["gemini"] == "all"

    def test_multiple_agents_stored_independently(self):
        set_agent_permissions("claude", ["developer"])
        set_agent_permissions("cursor", ["writer"])
        perms = list_permissions()
        assert perms["claude"] == ["developer"]
        assert perms["cursor"] == ["writer"]

    def test_default_key_preserved(self):
        set_agent_permissions("claude", ["developer"])
        perms = list_permissions()
        assert "default" in perms
        assert perms["default"] == "all"


# ---------------------------------------------------------------------------
# reset_permissions
# ---------------------------------------------------------------------------
class TestResetPermissions:
    def test_reset_removes_agent_permissions_key(self):
        set_agent_permissions("claude", ["developer"])
        reset_permissions()
        perms = list_permissions()
        assert perms == {}

    def test_reset_when_no_config(self):
        # Should not raise even when nothing is configured
        reset_permissions()
        assert list_permissions() == {}

    def test_after_reset_all_packs_visible(self):
        set_agent_permissions("cursor", ["developer"])
        reset_permissions()
        assert get_allowed_packs("cursor") is None

    def test_reset_does_not_remove_other_config_keys(self):
        """reset_permissions only removes agent_permissions, not other config."""
        from ruamel.yaml import YAML as _YAML
        _yaml = _YAML()
        _yaml.default_flow_style = False
        cfg_path = perm_mod._get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w") as f:
            _yaml.dump({
                "aura": {"version": "0.1.0"},
                "agent_permissions": {"claude": ["developer"]},
            }, f)

        reset_permissions()

        with open(cfg_path) as f:
            cfg = _yaml.load(f) or {}
        assert "aura" in cfg
        assert "agent_permissions" not in cfg


# ---------------------------------------------------------------------------
# list_permissions
# ---------------------------------------------------------------------------
class TestListPermissions:
    def test_empty_when_no_config(self):
        assert list_permissions() == {}

    def test_returns_all_configured_agents(self):
        set_agent_permissions("claude", ["developer"])
        set_agent_all("cursor")
        perms = list_permissions()
        assert "claude" in perms
        assert "cursor" in perms

    def test_returns_dict(self):
        assert isinstance(list_permissions(), dict)


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------
class TestBackwardsCompatibility:
    def test_no_agent_permissions_in_config_allows_all(self):
        """v0.3.3 config without agent_permissions → all packs visible."""
        from ruamel.yaml import YAML as _YAML
        _yaml = _YAML()
        _yaml.default_flow_style = False
        cfg_path = perm_mod._get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w") as f:
            _yaml.dump({"aura": {"version": "0.1.0"}}, f)

        packs = [_make_pack("developer"), _make_pack("writer"), _make_pack("work")]
        result = filter_packs_for_agent(packs, "claude")
        assert len(result) == 3

    def test_corrupted_config_returns_empty_permissions(self):
        cfg_path = perm_mod._get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text("{{{{not yaml}}}}")
        assert list_permissions() == {}
        assert get_allowed_packs("claude") is None
