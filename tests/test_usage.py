"""Tests for aura.usage — local MCP usage tracking."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import aura.usage as usage_mod
from aura.usage import (
    _empty_usage,
    _load_usage,
    _save_usage,
    _usage_norm,
    compute_priority_score,
    get_stats,
    get_usage_path,
    is_tracking_enabled,
    record_fact_access,
    record_pack_access,
    reset_stats,
    set_tracking,
    sort_facts_by_priority,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_usage(tmp_path, monkeypatch):
    """Redirect usage.json to a temp dir and reset tracking flag."""
    monkeypatch.setattr(usage_mod, "get_usage_path", lambda: tmp_path / "usage.json")
    usage_mod.set_tracking(True)
    yield
    usage_mod.set_tracking(True)


def _make_fact(key="lang", confidence="high"):
    f = MagicMock()
    f.key = key
    f.confidence = MagicMock()
    f.confidence.value = confidence
    return f


# ---------------------------------------------------------------------------
# _usage_norm
# ---------------------------------------------------------------------------
class TestUsageNorm:
    def test_zero_calls(self):
        assert _usage_norm(0) == 0.0

    def test_negative_calls(self):
        assert _usage_norm(-5) == 0.0

    def test_one_call(self):
        score = _usage_norm(1)
        assert 0 < score < 100

    def test_many_calls_capped(self):
        assert _usage_norm(10_000) == 100.0

    def test_monotonically_increasing(self):
        scores = [_usage_norm(n) for n in [0, 1, 10, 100, 1000]]
        assert scores == sorted(scores)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
class TestStorage:
    def test_empty_usage_structure(self):
        data = _empty_usage()
        assert data["version"] == "1"
        assert data["facts"] == {}
        assert data["packs"] == {}

    def test_load_missing_file_returns_empty(self):
        data = _load_usage()
        assert data == _empty_usage()

    def test_save_and_load_roundtrip(self, tmp_path):
        original = {"version": "1", "facts": {"dev.lang": {"calls": 5}}, "packs": {}}
        _save_usage(original)
        loaded = _load_usage()
        assert loaded["facts"]["dev.lang"]["calls"] == 5

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        path = get_usage_path()
        path.write_text("not valid json {{{{")
        data = _load_usage()
        assert data == _empty_usage()

    def test_load_wrong_version_returns_empty(self, tmp_path):
        _save_usage({"version": "99", "facts": {}, "packs": {}})
        assert _load_usage() == _empty_usage()


# ---------------------------------------------------------------------------
# Tracking enable/disable
# ---------------------------------------------------------------------------
class TestTrackingFlag:
    def test_tracking_on_by_default(self):
        assert is_tracking_enabled() is True

    def test_set_tracking_false(self):
        set_tracking(False)
        assert is_tracking_enabled() is False

    def test_set_tracking_back_to_true(self):
        set_tracking(False)
        set_tracking(True)
        assert is_tracking_enabled() is True

    def test_record_skipped_when_disabled(self):
        set_tracking(False)
        record_pack_access("dev", "claude")
        assert _load_usage() == _empty_usage()

    def test_record_fact_skipped_when_disabled(self):
        set_tracking(False)
        record_fact_access("dev", "lang", "claude")
        assert _load_usage() == _empty_usage()


# ---------------------------------------------------------------------------
# record_pack_access
# ---------------------------------------------------------------------------
class TestRecordPackAccess:
    def test_first_access_creates_entry(self):
        record_pack_access("developer", "claude")
        data = _load_usage()
        assert "developer" in data["packs"]
        assert data["packs"]["developer"]["calls"] == 1

    def test_multiple_accesses_accumulate(self):
        for _ in range(5):
            record_pack_access("developer", "claude")
        assert _load_usage()["packs"]["developer"]["calls"] == 5

    def test_agent_tracked(self):
        record_pack_access("developer", "claude")
        record_pack_access("developer", "cursor")
        agents = _load_usage()["packs"]["developer"]["agents"]
        assert agents["claude"] == 1
        assert agents["cursor"] == 1

    def test_last_called_set(self):
        record_pack_access("developer", "claude")
        data = _load_usage()
        assert data["packs"]["developer"]["last_called"] is not None


# ---------------------------------------------------------------------------
# record_fact_access
# ---------------------------------------------------------------------------
class TestRecordFactAccess:
    def test_first_fact_access(self):
        record_fact_access("developer", "lang", "claude")
        data = _load_usage()
        assert "developer.lang" in data["facts"]
        assert data["facts"]["developer.lang"]["calls"] == 1

    def test_multiple_fact_accesses(self):
        for _ in range(3):
            record_fact_access("developer", "lang", "claude")
        assert _load_usage()["facts"]["developer.lang"]["calls"] == 3

    def test_tool_tracked(self):
        record_fact_access("developer", "lang", "claude")
        record_fact_access("developer", "lang", "cursor")
        tools = _load_usage()["facts"]["developer.lang"]["tools"]
        assert tools["claude"] == 1
        assert tools["cursor"] == 1

    def test_composite_key_format(self):
        record_fact_access("writer", "tone", "claude")
        assert "writer.tone" in _load_usage()["facts"]


# ---------------------------------------------------------------------------
# compute_priority_score
# ---------------------------------------------------------------------------
class TestComputePriorityScore:
    def test_returns_float(self):
        fact = _make_fact("lang", "high")
        score = compute_priority_score(fact, "dev")
        assert isinstance(score, float)

    def test_score_in_range(self):
        fact = _make_fact("lang", "high")
        score = compute_priority_score(fact, "dev")
        assert 0.0 <= score <= 100.0

    def test_high_confidence_beats_low(self):
        fact_high = _make_fact("lang", "high")
        fact_low = _make_fact("lang", "low")
        score_high = compute_priority_score(fact_high, "dev", usage_data=_empty_usage())
        score_low = compute_priority_score(fact_low, "dev", usage_data=_empty_usage())
        assert score_high > score_low

    def test_usage_increases_score(self):
        fact = _make_fact("lang", "high")
        no_usage = _empty_usage()
        with_usage = _empty_usage()
        with_usage["facts"]["dev.lang"] = {"calls": 100, "last_called": None, "tools": {}}
        score_no = compute_priority_score(fact, "dev", usage_data=no_usage)
        score_with = compute_priority_score(fact, "dev", usage_data=with_usage)
        assert score_with > score_no

    def test_accepts_preloaded_usage_data(self):
        fact = _make_fact("lang", "medium")
        data = _empty_usage()
        score = compute_priority_score(fact, "dev", usage_data=data)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# sort_facts_by_priority
# ---------------------------------------------------------------------------
class TestSortFactsByPriority:
    def test_returns_list(self):
        facts = [_make_fact("a", "high"), _make_fact("b", "low")]
        result = sort_facts_by_priority(facts, "dev")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_higher_confidence_first_with_no_usage(self):
        high = _make_fact("a", "high")
        low = _make_fact("b", "low")
        result = sort_facts_by_priority([low, high], "dev")
        assert result[0] is high

    def test_empty_list(self):
        assert sort_facts_by_priority([], "dev") == []

    def test_single_fact(self):
        fact = _make_fact("lang", "high")
        result = sort_facts_by_priority([fact], "dev")
        assert result == [fact]


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------
class TestGetStats:
    def test_empty_stats(self):
        data = get_stats()
        assert data == {"facts": [], "packs": []}

    def test_stats_after_access(self):
        record_pack_access("developer", "claude")
        record_fact_access("developer", "lang", "claude")
        data = get_stats()
        assert len(data["packs"]) == 1
        assert len(data["facts"]) == 1

    def test_pack_filter(self):
        record_pack_access("developer", "claude")
        record_pack_access("writer", "claude")
        data = get_stats(pack_filter="developer")
        assert all(p["name"] == "developer" for p in data["packs"])

    def test_facts_sorted_by_calls(self):
        for _ in range(5):
            record_fact_access("dev", "lang", "claude")
        for _ in range(2):
            record_fact_access("dev", "editor", "claude")
        data = get_stats()
        calls = [f["calls"] for f in data["facts"]]
        assert calls == sorted(calls, reverse=True)

    def test_fact_filter_by_pack(self):
        record_fact_access("developer", "lang", "claude")
        record_fact_access("writer", "tone", "claude")
        data = get_stats(pack_filter="developer")
        assert all(f["pack"] == "developer" for f in data["facts"])


# ---------------------------------------------------------------------------
# reset_stats
# ---------------------------------------------------------------------------
class TestResetStats:
    def test_reset_all(self):
        record_pack_access("developer", "claude")
        record_fact_access("developer", "lang", "claude")
        cleared = reset_stats()
        assert cleared == 2
        assert _load_usage() == _empty_usage()

    def test_reset_specific_pack(self):
        record_pack_access("developer", "claude")
        record_pack_access("writer", "claude")
        record_fact_access("developer", "lang", "claude")
        reset_stats(pack_filter="developer")
        data = _load_usage()
        assert "writer" in data["packs"]
        assert "developer" not in data["packs"]
        assert "developer.lang" not in data["facts"]

    def test_reset_empty_returns_zero(self):
        assert reset_stats() == 0

    def test_reset_nonexistent_pack(self):
        record_pack_access("developer", "claude")
        cleared = reset_stats(pack_filter="nonexistent")
        assert cleared == 0
        assert _load_usage()["packs"]["developer"]["calls"] == 1
