"""Tests for MemoryGraph.detect_skill_candidates() — Cycle 275.

Detects repeated action patterns in episodic memories that are
candidates for promotion to skill type.
"""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph(":memory:")


class TestDetectSkillCandidates:
    """Core functionality tests."""

    def test_empty_graph_returns_empty(self, g):
        result = g.detect_skill_candidates()
        assert result == []

    def test_no_episodic_returns_empty(self, g):
        g.add("Python is great", kind="fact")
        g.add("FastAPI framework", kind="fact")
        result = g.detect_skill_candidates()
        assert result == []

    def test_single_event_returns_empty(self, g):
        g.add("created module", kind="event")
        result = g.detect_skill_candidates()
        assert result == []  # need at least min_frequency=2

    def test_repeated_action_detected(self, g):
        """Same action verb appearing multiple times should be detected."""
        g.add("created user module", kind="event")
        g.add("created auth module", kind="event")
        g.add("created API module", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        assert len(result) >= 1
        # The "created" pattern should appear
        names = [c["action"] for c in result]
        assert any("created" in n for n in names)

    def test_min_frequency_filter(self, g):
        """Patterns below min_frequency are excluded."""
        g.add("created module", kind="event")
        g.add("created auth", kind="event")
        g.add("tested module", kind="event")  # only once
        result = g.detect_skill_candidates(min_frequency=2)
        actions = [c["action"] for c in result]
        assert any("created" in a for a in actions)
        assert not any("tested" in a for a in actions)

    def test_intention_kind_also_mined(self, g):
        """Intentions are episodic too."""
        g.add("created module", kind="event")
        g.add("created another module", kind="intention")
        result = g.detect_skill_candidates(min_frequency=2)
        assert len(result) >= 1

    def test_skill_kind_excluded_from_mining(self, g):
        """Existing skills should not be mined as candidates."""
        g.add("created module", kind="event")
        g.add("created another module", kind="skill")
        result = g.detect_skill_candidates(min_frequency=2)
        # Only 1 event, so no candidates
        assert result == []

    def test_confidence_score(self, g):
        """Confidence increases with frequency."""
        for i in range(5):
            g.add(f"created module number {i}", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        assert len(result) >= 1
        candidate = result[0]
        assert 0 < candidate["confidence"] <= 1.0

    def test_confidence_saturates(self, g):
        """Confidence should approach 1.0 with many repetitions."""
        for i in range(10):
            g.add(f"created module {i}", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        candidate = [c for c in result if "created" in c["action"]][0]
        assert candidate["confidence"] >= 0.9

    def test_memory_ids_returned(self, g):
        """Each candidate includes source memory IDs."""
        g.add("created module", kind="event")
        g.add("created another", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        candidate = result[0]
        assert "memory_ids" in candidate
        assert len(candidate["memory_ids"]) >= 2

    def test_frequency_count(self, g):
        g.add("created module a", kind="event")
        g.add("created module b", kind="event")
        g.add("created module c", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        candidate = [c for c in result if "created" in c["action"]][0]
        assert candidate["frequency"] == 3

    def test_suggested_compression(self, g):
        """Each candidate includes a human-readable suggestion."""
        g.add("created module", kind="event")
        g.add("created another", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        candidate = result[0]
        assert "suggested_compression" in candidate
        assert len(candidate["suggested_compression"]) > 0


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_min_frequency_too_high(self, g):
        g.add("created module", kind="event")
        g.add("created another", kind="event")
        result = g.detect_skill_candidates(min_frequency=10)
        assert result == []

    def test_different_actions_no_candidates(self, g):
        g.add("created module", kind="event")
        g.add("tested module", kind="event")
        g.add("deployed module", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        assert result == []

    def test_mixed_kinds_only_epi_mined(self, g):
        """Facts mixed with events should not create false candidates."""
        g.add("created module", kind="event")
        g.add("created another", kind="fact")  # not episodic
        result = g.detect_skill_candidates(min_frequency=2)
        assert result == []

    def test_returns_list_type(self, g):
        g.add("something", kind="event")
        result = g.detect_skill_candidates()
        assert isinstance(result, list)

    def test_candidate_dict_keys(self, g):
        g.add("created a", kind="event")
        g.add("created b", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        candidate = result[0]
        expected_keys = {"action", "frequency", "confidence",
                         "memory_ids", "suggested_compression"}
        assert expected_keys.issubset(set(candidate.keys()))


class TestMultiplePatterns:
    """Multiple distinct patterns in the same graph."""

    def test_two_distinct_patterns(self, g):
        for i in range(3):
            g.add(f"created module {i}", kind="event")
        for i in range(3):
            g.add(f"tested endpoint {i}", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        actions = [c["action"] for c in result]
        assert any("created" in a for a in actions)
        assert any("tested" in a for a in actions)

    def test_dedup_overlapping(self, g):
        """Overlapping patterns should be deduplicated."""
        for i in range(4):
            g.add(f"created and tested module {i}", kind="event")
        result = g.detect_skill_candidates(min_frequency=2)
        # Should not have excessive duplicates
        assert len(result) <= 3
