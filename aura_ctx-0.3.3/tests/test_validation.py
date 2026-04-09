"""Tests for schema validation integrated into pack.py load/save pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from aura.schema_export import validate_pack_data
from aura.schema import ContextPack, Fact, Rule, PackMeta


# ---------------------------------------------------------------------------
# Round-trip: save → load validates correctly
# ---------------------------------------------------------------------------
class TestPackRoundTripValidation:
    def test_valid_pack_saves_and_loads(self, tmp_path, monkeypatch):
        """A valid pack written by save_pack passes validation on load."""
        import aura.pack as pack_mod

        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: tmp_path / "packs")
        (tmp_path / "packs").mkdir()

        from aura.schema import ContextPack, Fact, Rule, PackMeta

        pack = ContextPack(
            name="testpack",
            scope="development",
            facts=[Fact(key="lang", value="Python", type="skill")],
            rules=[Rule(instruction="Use types", priority=7)],
        )
        pack_mod.save_pack(pack)
        loaded = pack_mod.load_pack("testpack")
        assert loaded.name == "testpack"
        assert len(loaded.facts) == 1
        assert loaded.facts[0].key == "lang"

    def test_malformed_yaml_raises_on_load(self, tmp_path, monkeypatch):
        """A YAML pack with invalid schema raises ValueError on load."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        # Write a pack missing 'scope'
        bad_yaml = "name: bad-pack\nfacts: []\n"
        (packs_dir / "bad-pack.yaml").write_text(bad_yaml)

        with pytest.raises(ValueError, match="schema validation"):
            pack_mod.load_pack("bad-pack")

    def test_invalid_fact_type_raises_on_load(self, tmp_path, monkeypatch):
        """A pack with invalid fact type raises ValueError on load."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        bad_yaml = (
            "name: broken\n"
            "scope: dev\n"
            "facts:\n"
            "  - key: lang\n"
            "    value: Python\n"
            "    type: totally_invalid\n"
        )
        (packs_dir / "broken.yaml").write_text(bad_yaml)

        with pytest.raises(ValueError, match="schema validation"):
            pack_mod.load_pack("broken")

    def test_invalid_rule_priority_raises_on_load(self, tmp_path, monkeypatch):
        """A pack with out-of-range priority raises ValueError on load."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        bad_yaml = (
            "name: broken\n"
            "scope: dev\n"
            "rules:\n"
            "  - instruction: Do something\n"
            "    priority: 999\n"
        )
        (packs_dir / "broken.yaml").write_text(bad_yaml)

        with pytest.raises(ValueError, match="schema validation"):
            pack_mod.load_pack("broken")

    def test_error_message_contains_field_name(self, tmp_path, monkeypatch):
        """Validation error message names the problematic field."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        bad_yaml = "name: mypack\n"  # missing scope
        (packs_dir / "mypack.yaml").write_text(bad_yaml)

        with pytest.raises(ValueError) as exc_info:
            pack_mod.load_pack("mypack")
        assert "scope" in str(exc_info.value)


# ---------------------------------------------------------------------------
# v0.3.3 backwards compatibility — existing packs must still load
# ---------------------------------------------------------------------------
class TestBackwardsCompatibility:
    """Ensure v0.3.3 YAML format is accepted without modification."""

    def _write_pack(self, packs_dir: Path, name: str, content: str):
        (packs_dir / f"{name}.yaml").write_text(content)

    def test_v033_style_pack_loads_ok(self, tmp_path, monkeypatch):
        """A real v0.3.3-format YAML pack passes validation."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        v033_yaml = """name: developer
scope: development
meta:
  schema_version: '0.1.0'
  created_at: '2026-03-01T10:00:00'
  updated_at: '2026-03-15T12:00:00'
  description: Developer context pack
  tags:
    - developer
    - template
facts:
  - key: languages.primary
    value:
      - Python
      - TypeScript
    type: skill
  - key: editor
    value: Cursor
    confidence: high
  - key: style.comments
    value: Minimal
    type: style
    confidence: medium
    source: manual
rules:
  - instruction: Always use strict TypeScript
    priority: 8
  - instruction: Prefer functional patterns
"""
        self._write_pack(packs_dir, "developer", v033_yaml)
        pack = pack_mod.load_pack("developer")
        assert pack.name == "developer"
        assert pack.scope == "development"
        assert len(pack.facts) == 3
        assert len(pack.rules) == 2

    def test_pack_without_optional_fields_loads_ok(self, tmp_path, monkeypatch):
        """A minimal pack (name + scope only) loads without errors."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        minimal = "name: minimal\nscope: personal\n"
        self._write_pack(packs_dir, "minimal", minimal)
        pack = pack_mod.load_pack("minimal")
        assert pack.name == "minimal"
        assert pack.facts == []
        assert pack.rules == []

    def test_pack_with_list_value_loads_ok(self, tmp_path, monkeypatch):
        """Packs with list values for facts load correctly."""
        import aura.pack as pack_mod

        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()
        monkeypatch.setattr(pack_mod, "get_aura_home", lambda: tmp_path)
        monkeypatch.setattr(pack_mod, "get_packs_dir", lambda: packs_dir)

        yaml_content = (
            "name: writer\nscope: writing\n"
            "facts:\n"
            "  - key: languages\n"
            "    value:\n"
            "      - English\n"
            "      - French\n"
        )
        self._write_pack(packs_dir, "writer", yaml_content)
        pack = pack_mod.load_pack("writer")
        assert pack.facts[0].value == ["English", "French"]


# ---------------------------------------------------------------------------
# validate_pack_data integration with real ContextPack serialization
# ---------------------------------------------------------------------------
class TestValidatePackDataIntegration:
    def test_all_builtin_templates_are_valid(self):
        """All 14 built-in templates must pass schema validation."""
        from aura.pack import TEMPLATES, create_from_template
        from aura.schema_export import validate_pack_data
        from ruamel.yaml import YAML as _YAML
        import io

        _yaml = _YAML()

        for template_name in TEMPLATES:
            pack = create_from_template(template_name)

            # Simulate what save_pack produces
            from datetime import datetime
            data = {
                "name": pack.name,
                "scope": pack.scope,
                "meta": {
                    "schema_version": pack.meta.schema_version,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                "facts": [
                    {
                        "key": f.key,
                        "value": f.value,
                        "type": f.type.value,
                        "confidence": f.confidence.value,
                    }
                    for f in pack.facts
                ],
                "rules": [
                    {
                        "instruction": r.instruction,
                        "priority": r.priority,
                    }
                    for r in pack.rules
                ],
            }

            errors = validate_pack_data(data)
            assert errors == [], (
                f"Template '{template_name}' has schema errors: {errors}"
            )
