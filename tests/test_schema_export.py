"""Tests for aura.schema_export — JSON Schema generation and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura.schema_export import (
    CONTEXT_PACK_SCHEMA,
    generate_schema,
    schema_to_json,
    validate_pack_data,
    write_schema_file,
    _validate_fact,
    _validate_rule,
)


# ---------------------------------------------------------------------------
# generate_schema
# ---------------------------------------------------------------------------
class TestGenerateSchema:
    def test_returns_dict(self):
        schema = generate_schema()
        assert isinstance(schema, dict)

    def test_has_required_top_level_keys(self):
        schema = generate_schema()
        assert "$schema" in schema
        assert "title" in schema
        assert "type" in schema
        assert "properties" in schema
        assert "$defs" in schema

    def test_title_is_context_pack(self):
        assert generate_schema()["title"] == "ContextPack"

    def test_type_is_object(self):
        assert generate_schema()["type"] == "object"

    def test_required_fields_present(self):
        schema = generate_schema()
        assert "name" in schema["required"]
        assert "scope" in schema["required"]

    def test_properties_cover_all_fields(self):
        props = generate_schema()["properties"]
        assert "name" in props
        assert "scope" in props
        assert "facts" in props
        assert "rules" in props
        assert "meta" in props

    def test_fact_def_has_required_fields(self):
        fact_def = generate_schema()["$defs"]["Fact"]
        assert "key" in fact_def["required"]
        assert "value" in fact_def["required"]

    def test_fact_type_enum(self):
        fact_def = generate_schema()["$defs"]["Fact"]
        type_enum = fact_def["properties"]["type"]["enum"]
        assert "skill" in type_enum
        assert "preference" in type_enum
        assert "identity" in type_enum
        assert "style" in type_enum
        assert "constraint" in type_enum
        assert "context" in type_enum

    def test_fact_confidence_enum(self):
        fact_def = generate_schema()["$defs"]["Fact"]
        conf_enum = fact_def["properties"]["confidence"]["enum"]
        assert "high" in conf_enum
        assert "medium" in conf_enum
        assert "low" in conf_enum

    def test_rule_def_has_instruction(self):
        rule_def = generate_schema()["$defs"]["Rule"]
        assert "instruction" in rule_def["required"]
        assert "priority" in rule_def["properties"]

    def test_rule_priority_range(self):
        rule_def = generate_schema()["$defs"]["Rule"]
        priority = rule_def["properties"]["priority"]
        assert priority["minimum"] == 0
        assert priority["maximum"] == 10


# ---------------------------------------------------------------------------
# schema_to_json
# ---------------------------------------------------------------------------
class TestSchemaToJson:
    def test_returns_valid_json(self):
        raw = schema_to_json()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_default_indent(self):
        raw = schema_to_json()
        assert "\n" in raw  # indented

    def test_custom_indent(self):
        raw = schema_to_json(indent=4)
        assert "    " in raw


# ---------------------------------------------------------------------------
# write_schema_file
# ---------------------------------------------------------------------------
class TestWriteSchemaFile:
    def test_writes_file(self, tmp_path):
        out = tmp_path / "schema.json"
        result = write_schema_file(out)
        assert result == out
        assert out.exists()

    def test_content_is_valid_json(self, tmp_path):
        out = tmp_path / "schema.json"
        write_schema_file(out)
        parsed = json.loads(out.read_text())
        assert parsed["title"] == "ContextPack"

    def test_default_path_is_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = write_schema_file()
        assert result.name == "context-pack.schema.json"
        assert result.exists()


# ---------------------------------------------------------------------------
# validate_pack_data — valid packs
# ---------------------------------------------------------------------------
class TestValidatePackDataValid:
    def test_minimal_valid_pack(self):
        data = {"name": "dev", "scope": "development"}
        assert validate_pack_data(data) == []

    def test_pack_with_facts_and_rules(self):
        data = {
            "name": "developer",
            "scope": "development",
            "facts": [
                {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill"},
                {"key": "editor", "value": "Cursor", "confidence": "high"},
            ],
            "rules": [
                {"instruction": "Use strict TypeScript", "priority": 8},
                {"instruction": "No magic numbers"},
            ],
        }
        assert validate_pack_data(data) == []

    def test_fact_with_string_value(self):
        data = {
            "name": "writer",
            "scope": "writing",
            "facts": [{"key": "tone", "value": "direct and concise"}],
        }
        assert validate_pack_data(data) == []

    def test_fact_with_all_types(self):
        for ftype in ["preference", "identity", "skill", "style", "constraint", "context"]:
            data = {
                "name": "test",
                "scope": "test",
                "facts": [{"key": "k", "value": "v", "type": ftype}],
            }
            assert validate_pack_data(data) == [], f"Type {ftype!r} should be valid"

    def test_fact_with_all_confidences(self):
        for conf in ["high", "medium", "low"]:
            data = {
                "name": "test",
                "scope": "test",
                "facts": [{"key": "k", "value": "v", "confidence": conf}],
            }
            assert validate_pack_data(data) == [], f"Confidence {conf!r} should be valid"

    def test_rule_priority_boundaries(self):
        for priority in [0, 1, 5, 9, 10]:
            data = {
                "name": "test",
                "scope": "test",
                "rules": [{"instruction": "Do X", "priority": priority}],
            }
            assert validate_pack_data(data) == [], f"Priority {priority} should be valid"

    def test_name_with_hyphens_and_underscores(self):
        for name in ["my-pack", "my_pack", "pack123", "a"]:
            data = {"name": name, "scope": "test"}
            assert validate_pack_data(data) == [], f"Name {name!r} should be valid"


# ---------------------------------------------------------------------------
# validate_pack_data — invalid packs
# ---------------------------------------------------------------------------
class TestValidatePackDataInvalid:
    def test_missing_name(self):
        errors = validate_pack_data({"scope": "development"})
        assert any("name" in e for e in errors)

    def test_missing_scope(self):
        errors = validate_pack_data({"name": "dev"})
        assert any("scope" in e for e in errors)

    def test_name_starts_with_uppercase(self):
        errors = validate_pack_data({"name": "Developer", "scope": "dev"})
        assert any("name" in e for e in errors)

    def test_name_starts_with_digit(self):
        errors = validate_pack_data({"name": "1pack", "scope": "dev"})
        assert any("name" in e for e in errors)

    def test_name_with_spaces(self):
        errors = validate_pack_data({"name": "my pack", "scope": "dev"})
        assert any("name" in e for e in errors)

    def test_invalid_fact_type(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"key": "k", "value": "v", "type": "invalid_type"}],
        }
        errors = validate_pack_data(data)
        assert any("type" in e for e in errors)

    def test_invalid_confidence(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"key": "k", "value": "v", "confidence": "very_high"}],
        }
        errors = validate_pack_data(data)
        assert any("confidence" in e for e in errors)

    def test_fact_missing_key(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"value": "Python"}],
        }
        errors = validate_pack_data(data)
        assert any("key" in e for e in errors)

    def test_fact_missing_value(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"key": "lang"}],
        }
        errors = validate_pack_data(data)
        assert any("value" in e for e in errors)

    def test_fact_value_wrong_type(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"key": "k", "value": 42}],
        }
        errors = validate_pack_data(data)
        assert any("value" in e for e in errors)

    def test_rule_missing_instruction(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "rules": [{"priority": 5}],
        }
        errors = validate_pack_data(data)
        assert any("instruction" in e for e in errors)

    def test_rule_priority_out_of_range_high(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "rules": [{"instruction": "Do X", "priority": 11}],
        }
        errors = validate_pack_data(data)
        assert any("priority" in e for e in errors)

    def test_rule_priority_out_of_range_low(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "rules": [{"instruction": "Do X", "priority": -1}],
        }
        errors = validate_pack_data(data)
        assert any("priority" in e for e in errors)

    def test_not_a_dict(self):
        errors = validate_pack_data("not a dict")  # type: ignore[arg-type]
        assert len(errors) > 0

    def test_empty_list_value(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [{"key": "k", "value": []}],
        }
        errors = validate_pack_data(data)
        assert any("value" in e for e in errors)

    def test_multiple_errors_reported(self):
        data = {
            "name": "dev",
            "scope": "dev",
            "facts": [
                {"value": "Python"},           # missing key
                {"key": "k", "value": []},     # empty list
                {"key": "k2", "value": "v", "type": "bad"},  # invalid type
            ],
        }
        errors = validate_pack_data(data)
        assert len(errors) >= 3


# ---------------------------------------------------------------------------
# _validate_fact and _validate_rule (internal helpers)
# ---------------------------------------------------------------------------
class TestValidateFactHelper:
    def test_valid_fact(self):
        assert _validate_fact({"key": "lang", "value": "Python"}, 0) == []

    def test_fact_not_dict(self):
        errors = _validate_fact("not a dict", 0)
        assert len(errors) == 1

    def test_list_value_with_non_string_item(self):
        errors = _validate_fact({"key": "k", "value": ["good", 42]}, 0)
        assert any("list items must be strings" in e for e in errors)


class TestValidateRuleHelper:
    def test_valid_rule(self):
        assert _validate_rule({"instruction": "Do X", "priority": 5}, 0) == []

    def test_rule_not_dict(self):
        errors = _validate_rule(42, 0)
        assert len(errors) == 1

    def test_priority_not_int(self):
        errors = _validate_rule({"instruction": "Do X", "priority": "high"}, 0)
        assert any("integer" in e for e in errors)
