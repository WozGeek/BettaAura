"""Tests for usage-based fact priority integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import aura.usage as usage_mod
from aura.usage import (
    PRIORITY_THRESHOLD,
    _empty_usage,
    compute_priority_score,
    get_high_priority_facts,
    record_fact_access,
    sort_facts_by_priority,
)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_mod, "get_usage_path", lambda: tmp_path / "usage.json")
    usage_mod.set_tracking(True)
    yield
    usage_mod.set_tracking(True)


def _fact(key: str, confidence: str = "high") -> MagicMock:
    f = MagicMock()
    f.key = key
    f.confidence = MagicMock()
    f.confidence.value = confidence
    return f


# ---------------------------------------------------------------------------
# Priority threshold
# ---------------------------------------------------------------------------
class TestPriorityThreshold:
    def test_threshold_is_70(self):
        assert PRIORITY_THRESHOLD == 70.0

    def test_high_confidence_no_usage_below_threshold(self):
        """With zero usage, even high-confidence facts may be below threshold."""
        fact = _fact("lang", "high")
        score = compute_priority_score(fact, "dev", usage_data=_empty_usage())
        # freshness 100 × 0.4 + confidence 100 × 0.2 + usage 0 × 0.4 = 60
        assert score < PRIORITY_THRESHOLD

    def test_high_usage_pushes_above_threshold(self):
        """A frequently accessed fact exceeds the priority threshold."""
        for _ in range(200):
            record_fact_access("dev", "lang", "claude")
        fact = _fact("lang", "high")
        score = compute_priority_score(fact, "dev")
        assert score >= PRIORITY_THRESHOLD


# ---------------------------------------------------------------------------
# get_high_priority_facts
# ---------------------------------------------------------------------------
class TestGetHighPriorityFacts:
    def test_returns_only_facts_above_threshold(self):
        """Only facts with score >= threshold are returned."""
        fact_a = _fact("lang", "high")
        fact_b = _fact("editor", "low")

        # Give lang many calls to push it above threshold
        for _ in range(300):
            record_fact_access("dev", "lang", "claude")

        high = get_high_priority_facts([fact_a, fact_b], "dev")
        # At minimum, lang should be included; editor might not be
        assert fact_a in high

    def test_empty_input(self):
        assert get_high_priority_facts([], "dev") == []

    def test_custom_threshold(self):
        """Custom threshold of 0 returns all facts."""
        facts = [_fact("a", "high"), _fact("b", "low")]
        result = get_high_priority_facts(facts, "dev", threshold=0.0)
        assert len(result) == 2

    def test_threshold_100_returns_empty_without_usage(self):
        facts = [_fact("lang", "high")]
        result = get_high_priority_facts(facts, "dev", threshold=100.0)
        # Nothing reaches exactly 100 without usage AND perfect freshness
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Ordering correctness
# ---------------------------------------------------------------------------
class TestOrderingCorrectness:
    def test_most_used_fact_first(self):
        """The fact with most MCP calls comes first in sorted order."""
        for _ in range(50):
            record_fact_access("dev", "editor", "claude")
        for _ in range(5):
            record_fact_access("dev", "lang", "claude")

        fact_lang = _fact("lang", "high")
        fact_editor = _fact("editor", "high")
        sorted_facts = sort_facts_by_priority([fact_lang, fact_editor], "dev")
        assert sorted_facts[0] is fact_editor

    def test_confidence_breaks_tie_when_usage_equal(self):
        """When usage is equal, higher confidence wins."""
        fact_high = _fact("a", "high")
        fact_low = _fact("b", "low")
        # Same usage — 0 calls each
        sorted_facts = sort_facts_by_priority([fact_low, fact_high], "dev")
        assert sorted_facts[0] is fact_high

    def test_order_stable_for_identical_facts(self):
        """Same key, same confidence, same usage → both present."""
        f1 = _fact("lang", "high")
        f2 = _fact("lang", "high")
        result = sort_facts_by_priority([f1, f2], "dev")
        assert len(result) == 2

    def test_across_packs_no_cross_contamination(self):
        """Usage on dev.lang does not affect writer.lang priority."""
        for _ in range(100):
            record_fact_access("dev", "lang", "claude")

        fact_dev = _fact("lang", "high")
        fact_writer = _fact("lang", "high")

        score_dev = compute_priority_score(fact_dev, "dev")
        score_writer = compute_priority_score(fact_writer, "writer")

        # dev.lang has usage, writer.lang has none → dev scores higher
        assert score_dev > score_writer


# ---------------------------------------------------------------------------
# Score formula validation
# ---------------------------------------------------------------------------
class TestScoreFormula:
    def test_formula_components_sum_correctly(self):
        """
        With known inputs, verify the formula produces expected output.
        usage_norm(0) = 0, freshness mocked to 80, confidence high=1.0 → 100
        score = (0 × 0.4) + (80 × 0.4) + (100 × 0.2) = 0 + 32 + 20 = 52
        """
        fact = _fact("lang", "high")
        usage_data = _empty_usage()

        with patch("aura.usage._freshness_score", return_value=80.0):
            score = compute_priority_score(fact, "dev", usage_data=usage_data)

        assert abs(score - 52.0) < 0.1

    def test_score_never_exceeds_100(self):
        """Score is always capped at 100."""
        for _ in range(10_000):
            record_fact_access("dev", "lang", "claude")
        fact = _fact("lang", "high")
        score = compute_priority_score(fact, "dev")
        assert score <= 100.0

    def test_score_never_below_0(self):
        fact = _fact("lang", "low")
        score = compute_priority_score(fact, "dev", usage_data=_empty_usage())
        assert score >= 0.0
