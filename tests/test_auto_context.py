"""
Tests for MCP resource auto-subscription — Mécanisme 3.

Tests that aura://identity/* URIs are correctly exposed via
resources/list and resources/read, and that the identity card
is marked as required.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect aura home to a temp dir."""
    import aura.pack as pack_mod
    monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
    monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: tmp_path / "packs")
    (tmp_path / "packs").mkdir()
    import aura.permissions as perm_mod
    monkeypatch.setattr(perm_mod, "_get_config_path", lambda: tmp_path / "config.yaml")
    import aura.usage as usage_mod
    monkeypatch.setattr(usage_mod, "get_usage_path", lambda: tmp_path / "usage.json")


@pytest.fixture()
def with_packs(tmp_path, monkeypatch):
    """Create a real pack for content tests."""
    import aura.pack as pack_mod
    from aura.schema import ContextPack, Fact, Rule

    packs_dir = tmp_path / "packs"
    pack = ContextPack(
        name="developer",
        scope="development",
        facts=[
            Fact(key="languages.primary", value=["Python", "TypeScript"], type="skill"),
            Fact(key="editor", value="Cursor", type="preference"),
        ],
        rules=[Rule(instruction="Always use TypeScript strict mode", priority=9)],
    )
    pack_mod.save_pack(pack)
    return pack


def _jsonrpc(method: str, params: dict = None):
    from aura.mcp_server import handle_jsonrpc
    return handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    })


# ---------------------------------------------------------------------------
# resources/list — identity URIs present
# ---------------------------------------------------------------------------
class TestResourcesList:
    def test_returns_resources_list(self):
        r = _jsonrpc("resources/list")
        assert "result" in r
        assert "resources" in r["result"]
        assert isinstance(r["result"]["resources"], list)

    def test_identity_card_present(self):
        r = _jsonrpc("resources/list")
        uris = [res["uri"] for res in r["result"]["resources"]]
        assert "aura://identity/card" in uris

    def test_identity_profile_present(self):
        r = _jsonrpc("resources/list")
        uris = [res["uri"] for res in r["result"]["resources"]]
        assert "aura://identity/profile" in uris

    def test_identity_full_present(self):
        r = _jsonrpc("resources/list")
        uris = [res["uri"] for res in r["result"]["resources"]]
        assert "aura://identity/full" in uris

    def test_identity_card_required_true(self):
        """Identity card must be marked required for auto-subscription."""
        r = _jsonrpc("resources/list")
        card = next(
            res for res in r["result"]["resources"]
            if res["uri"] == "aura://identity/card"
        )
        assert card.get("required") is True

    def test_identity_profile_not_required(self):
        r = _jsonrpc("resources/list")
        profile = next(
            res for res in r["result"]["resources"]
            if res["uri"] == "aura://identity/profile"
        )
        assert profile.get("required") is not True

    def test_identity_full_not_required(self):
        r = _jsonrpc("resources/list")
        full = next(
            res for res in r["result"]["resources"]
            if res["uri"] == "aura://identity/full"
        )
        assert full.get("required") is not True

    def test_identity_card_has_name(self):
        r = _jsonrpc("resources/list")
        card = next(
            res for res in r["result"]["resources"]
            if res["uri"] == "aura://identity/card"
        )
        assert "name" in card
        assert len(card["name"]) > 0

    def test_identity_card_has_description(self):
        r = _jsonrpc("resources/list")
        card = next(
            res for res in r["result"]["resources"]
            if res["uri"] == "aura://identity/card"
        )
        assert "description" in card
        assert "automatically" in card["description"].lower() or "start" in card["description"].lower()

    def test_legacy_context_full_still_present(self):
        """aura://context/full must remain for backwards compat."""
        r = _jsonrpc("resources/list")
        uris = [res["uri"] for res in r["result"]["resources"]]
        assert "aura://context/full" in uris

    def test_at_least_four_resources(self):
        """card + profile + full + context/full = minimum 4."""
        r = _jsonrpc("resources/list")
        assert len(r["result"]["resources"]) >= 4


# ---------------------------------------------------------------------------
# resources/read — aura://identity/card
# ---------------------------------------------------------------------------
class TestReadIdentityCard:
    def test_returns_contents(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        assert "result" in r
        assert "contents" in r["result"]
        assert isinstance(r["result"]["contents"], list)
        assert len(r["result"]["contents"]) == 1

    def test_uri_echoed_back(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        content = r["result"]["contents"][0]
        assert content["uri"] == "aura://identity/card"

    def test_mime_type_is_text(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        content = r["result"]["contents"][0]
        assert "text" in content["mimeType"] or content["mimeType"] == "text/plain"

    def test_text_is_string(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        content = r["result"]["contents"][0]
        assert isinstance(content["text"], str)

    def test_returns_content_with_packs(self, with_packs):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        content = r["result"]["contents"][0]
        # With packs loaded, text should be non-empty
        assert len(content["text"]) > 0

    def test_no_packs_returns_empty_or_placeholder(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        content = r["result"]["contents"][0]
        # Should not error even with no packs
        assert isinstance(content["text"], str)


# ---------------------------------------------------------------------------
# resources/read — aura://identity/profile
# ---------------------------------------------------------------------------
class TestReadIdentityProfile:
    def test_returns_contents(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/profile"})
        assert "result" in r
        assert "contents" in r["result"]

    def test_uri_echoed_back(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/profile"})
        assert r["result"]["contents"][0]["uri"] == "aura://identity/profile"

    def test_text_is_string(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/profile"})
        assert isinstance(r["result"]["contents"][0]["text"], str)

    def test_returns_content_with_packs(self, with_packs):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/profile"})
        content = r["result"]["contents"][0]
        assert len(content["text"]) > 0


# ---------------------------------------------------------------------------
# resources/read — aura://identity/full
# ---------------------------------------------------------------------------
class TestReadIdentityFull:
    def test_returns_contents(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/full"})
        assert "result" in r
        assert "contents" in r["result"]

    def test_uri_echoed_back(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/full"})
        assert r["result"]["contents"][0]["uri"] == "aura://identity/full"

    def test_text_is_string(self):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/full"})
        assert isinstance(r["result"]["contents"][0]["text"], str)

    def test_returns_content_with_packs(self, with_packs):
        r = _jsonrpc("resources/read", {"uri": "aura://identity/full"})
        content = r["result"]["contents"][0]
        assert len(content["text"]) > 0


# ---------------------------------------------------------------------------
# resources/read — unknown URI
# ---------------------------------------------------------------------------
class TestReadUnknownUri:
    def test_unknown_uri_returns_not_found(self):
        r = _jsonrpc("resources/read", {"uri": "aura://does/not/exist"})
        assert "result" in r
        contents = r["result"]["contents"]
        assert len(contents) == 1
        assert "not found" in contents[0]["text"].lower() or "resource" in contents[0]["text"].lower()

    def test_unknown_uri_echoed_back(self):
        r = _jsonrpc("resources/read", {"uri": "aura://unknown/thing"})
        assert r["result"]["contents"][0]["uri"] == "aura://unknown/thing"


# ---------------------------------------------------------------------------
# Backwards compat — legacy URIs still work
# ---------------------------------------------------------------------------
class TestLegacyResourcesUnchanged:
    def test_aura_context_full_still_works(self):
        r = _jsonrpc("resources/read", {"uri": "aura://context/full"})
        assert "result" in r
        assert "contents" in r["result"]
        assert r["result"]["contents"][0]["uri"] == "aura://context/full"

    def test_aura_packs_uri_still_works(self, with_packs):
        r = _jsonrpc("resources/read", {"uri": "aura://packs/developer"})
        assert "result" in r
        content = r["result"]["contents"][0]
        assert content["uri"] == "aura://packs/developer"
        assert "developer" in content["text"].lower()


# ---------------------------------------------------------------------------
# Identity helpers — content consistency
# ---------------------------------------------------------------------------
class TestIdentityHelperConsistency:
    def test_card_content_matches_tool(self, with_packs):
        """aura://identity/card must return same content as get_identity_card tool."""
        from aura.mcp_server import execute_tool

        resource_r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        resource_text = resource_r["result"]["contents"][0]["text"]

        tool_result = execute_tool("get_identity_card", {})
        tool_text = tool_result[0]["text"]

        # Both should contain the same key facts
        assert resource_text == tool_text

    def test_profile_content_is_longer_than_card(self, with_packs):
        """Profile should contain more detail than identity card."""
        card_r = _jsonrpc("resources/read", {"uri": "aura://identity/card"})
        profile_r = _jsonrpc("resources/read", {"uri": "aura://identity/profile"})

        card_text = card_r["result"]["contents"][0]["text"]
        profile_text = profile_r["result"]["contents"][0]["text"]

        # Profile is always >= card in length
        assert len(profile_text) >= len(card_text)


# ---------------------------------------------------------------------------
# Setup — claude_code.py aura_instruction block
# ---------------------------------------------------------------------------
class TestClaudeCodeExporterInstruction:
    def test_aura_instruction_present_in_claude_md(self):
        """export_claude_md must include the <aura_instruction> block."""
        from aura.exporters.claude_code import export_claude_md
        from aura.schema import ContextPack, Fact

        pack = ContextPack(
            name="developer",
            scope="development",
            facts=[Fact(key="lang", value="Python", type="skill")],
            rules=[],
        )
        output = export_claude_md([pack])
        assert "<aura_instruction>" in output
        assert "</aura_instruction>" in output

    def test_aura_instruction_mentions_get_identity_card(self):
        from aura.exporters.claude_code import export_claude_md
        from aura.schema import ContextPack

        pack = ContextPack(name="dev", scope="development", facts=[], rules=[])
        output = export_claude_md([pack])
        assert "get_identity_card" in output

    def test_aura_instruction_tells_not_to_wait(self):
        from aura.exporters.claude_code import export_claude_md
        from aura.schema import ContextPack

        pack = ContextPack(name="dev", scope="development", facts=[], rules=[])
        output = export_claude_md([pack])
        assert "do not wait" in output.lower() or "don't wait" in output.lower()

    def test_mcp_connection_note_still_present(self):
        """Existing MCP connection note must remain."""
        from aura.exporters.claude_code import export_claude_md
        from aura.schema import ContextPack

        pack = ContextPack(name="dev", scope="development", facts=[], rules=[])
        output = export_claude_md([pack])
        assert "localhost:3847" in output

    def test_developer_identity_header_still_present(self):
        from aura.exporters.claude_code import export_claude_md
        from aura.schema import ContextPack

        pack = ContextPack(name="dev", scope="development", facts=[], rules=[])
        output = export_claude_md([pack])
        assert "Developer Identity" in output


# ---------------------------------------------------------------------------
# Setup.py — get_chatgpt_autoload_instruction
# ---------------------------------------------------------------------------
class TestChatGptAutoloadInstruction:
    def test_returns_string(self):
        from aura.setup import get_chatgpt_autoload_instruction
        result = get_chatgpt_autoload_instruction()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_get_identity_card(self):
        from aura.setup import get_chatgpt_autoload_instruction
        assert "get_identity_card" in get_chatgpt_autoload_instruction()

    def test_mentions_aura(self):
        from aura.setup import get_chatgpt_autoload_instruction
        assert "aura" in get_chatgpt_autoload_instruction().lower()

    def test_setup_aura_mcp_config_has_description(self):
        """_aura_mcp_config must include a description for Claude Desktop."""
        from aura.setup import _aura_mcp_config
        config = _aura_mcp_config()
        assert "description" in config
        assert "automatically" in config["description"].lower() or "identity" in config["description"].lower()

    def test_setup_aura_mcp_config_has_url(self):
        from aura.setup import _aura_mcp_config
        config = _aura_mcp_config()
        assert "url" in config
        assert "localhost:3847" in config["url"]
