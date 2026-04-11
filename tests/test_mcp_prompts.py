"""
Tests for MCP prompt templates — Mécanisme 1.

Tests that the aura_identity prompt template is correctly exposed via
the JSON-RPC prompts/list and prompts/get methods.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect aura home to a temp dir so tests don't touch ~/.aura."""
    import aura.pack as pack_mod
    monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
    monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: tmp_path / "packs")
    (tmp_path / "packs").mkdir()
    import aura.permissions as perm_mod
    monkeypatch.setattr(perm_mod, "_get_config_path", lambda: tmp_path / "config.yaml")


def _jsonrpc(method: str, params: dict = None):
    from aura.mcp_server import handle_jsonrpc
    return handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    })


# ---------------------------------------------------------------------------
# prompts/list
# ---------------------------------------------------------------------------
class TestPromptsList:
    def test_returns_list(self):
        r = _jsonrpc("prompts/list")
        assert "result" in r
        assert "prompts" in r["result"]
        assert isinstance(r["result"]["prompts"], list)

    def test_aura_identity_present(self):
        r = _jsonrpc("prompts/list")
        names = [p["name"] for p in r["result"]["prompts"]]
        assert "aura_identity" in names

    def test_aura_identity_has_description(self):
        r = _jsonrpc("prompts/list")
        prompt = next(p for p in r["result"]["prompts"] if p["name"] == "aura_identity")
        assert "description" in prompt
        assert len(prompt["description"]) > 0

    def test_existing_prompts_still_present(self):
        r = _jsonrpc("prompts/list")
        names = [p["name"] for p in r["result"]["prompts"]]
        assert "with_full_context" in names
        assert "with_scope" in names

    def test_three_prompts_total(self):
        r = _jsonrpc("prompts/list")
        assert len(r["result"]["prompts"]) == 3

    def test_aura_identity_has_no_required_arguments(self):
        r = _jsonrpc("prompts/list")
        prompt = next(p for p in r["result"]["prompts"] if p["name"] == "aura_identity")
        assert prompt.get("arguments", []) == []


# ---------------------------------------------------------------------------
# prompts/get — aura_identity
# ---------------------------------------------------------------------------
class TestPromptsGetAuraIdentity:
    def test_returns_messages_list(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        assert "result" in r
        assert "messages" in r["result"]
        assert isinstance(r["result"]["messages"], list)
        assert len(r["result"]["messages"]) == 1

    def test_message_role_is_user(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        msg = r["result"]["messages"][0]
        assert msg["role"] == "user"

    def test_message_has_text_content(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        content = r["result"]["messages"][0]["content"]
        assert content["type"] == "text"
        assert isinstance(content["text"], str)
        assert len(content["text"]) > 0

    def test_message_mentions_get_identity_card(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "get_identity_card" in text

    def test_message_says_automatically(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "automatically" in text.lower()

    def test_message_mentions_get_user_profile(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "get_user_profile" in text

    def test_message_mentions_get_all_context(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "get_all_context" in text

    def test_result_has_description(self):
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        assert "description" in r["result"]
        assert len(r["result"]["description"]) > 0

    def test_do_not_wait_instruction(self):
        """Prompt must tell the AI not to wait for user to ask."""
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "do not wait" in text.lower() or "don't wait" in text.lower()

    def test_every_conversation_instruction(self):
        """Prompt must instruct AI to load context at start of EVERY conversation."""
        r = _jsonrpc("prompts/get", {"name": "aura_identity", "arguments": {}})
        text = r["result"]["messages"][0]["content"]["text"]
        assert "every conversation" in text.lower() or "each conversation" in text.lower()


# ---------------------------------------------------------------------------
# prompts/get — unknown prompt
# ---------------------------------------------------------------------------
class TestPromptsGetUnknown:
    def test_unknown_prompt_returns_empty_messages(self):
        r = _jsonrpc("prompts/get", {"name": "nonexistent_prompt", "arguments": {}})
        assert "result" in r
        # Should return empty messages, not an error
        assert r["result"]["messages"] == []

    def test_unknown_prompt_returns_description(self):
        r = _jsonrpc("prompts/get", {"name": "nonexistent_prompt", "arguments": {}})
        assert "description" in r["result"]


# ---------------------------------------------------------------------------
# Existing prompts — backwards compat
# ---------------------------------------------------------------------------
class TestExistingPromptsUnchanged:
    def test_with_full_context_still_works(self):
        r = _jsonrpc("prompts/get", {"name": "with_full_context", "arguments": {}})
        assert "result" in r
        assert "messages" in r["result"]

    def test_with_scope_still_works(self):
        r = _jsonrpc("prompts/get", {"name": "with_scope", "arguments": {"scope": "development"}})
        assert "result" in r
        assert "messages" in r["result"]
