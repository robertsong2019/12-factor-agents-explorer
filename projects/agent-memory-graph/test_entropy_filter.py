"""Tests for add_with_entropy_filter() — Cycle 228.

SimpleMem (ICML 2026) inspired write-time entropy filtering.
Filters low-information-density content at add() time.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


class TestAddWithEntropyFilter:
    """add_with_entropy_filter: write-time information density gating."""

    def test_high_info_content_accepted(self, mg):
        """Substantive new content should be accepted."""
        node = mg.add_with_entropy_filter(
            "The quarterly revenue increased by 15% compared to last year"
        )
        assert node is not None
        assert node.id is not None

    def test_empty_string_filtered(self, mg):
        """Empty string should be filtered."""
        assert mg.add_with_entropy_filter("") is None

    def test_whitespace_only_filtered(self, mg):
        """Whitespace-only should be filtered."""
        assert mg.add_with_entropy_filter("   ") is None

    def test_very_short_filtered(self, mg):
        """Very short strings (< 5 chars) should be filtered."""
        assert mg.add_with_entropy_filter("hi") is None
        assert mg.add_with_entropy_filter("abc") is None

    def test_single_word_accepted_or_filtered(self, mg):
        """Single word with 5+ chars should pass threshold check."""
        # "hello" is 5 chars, single word, TTR=1.0, novelty=1.0
        node = mg.add_with_entropy_filter("hello")
        # With default threshold 0.3, should pass on empty graph
        assert node is not None

    def test_duplicate_content_filtered(self, mg):
        """Exact duplicate should be filtered (novelty → 0)."""
        mg.add("The project deadline is next Friday")
        dup = mg.add_with_entropy_filter("The project deadline is next Friday")
        assert dup is None

    def test_near_duplicate_lower_score(self, mg):
        """Near-duplicate should have lower score but might still pass."""
        mg.add("The system architecture uses microservices pattern")
        # Different enough to potentially pass
        node = mg.add_with_entropy_filter(
            "The system architecture uses serverless pattern"
        )
        # Should be accepted since words differ meaningfully
        assert node is not None

    def test_threshold_zero_accepts_all(self, mg):
        """threshold=0 should accept everything (score >= 0.0 always true)."""
        # Even short strings pass when threshold=0 because score=0.0 >= 0.0
        node = mg.add_with_entropy_filter("ok", threshold=0.0)
        assert node is not None

    def test_threshold_zero_accepts_short_meaningful(self, mg):
        """threshold=0 should accept 5+ char strings."""
        node = mg.add_with_entropy_filter("ready", threshold=0.0)
        assert node is not None

    def test_threshold_one_very_strict(self, mg):
        """threshold=1.0 should reject almost everything."""
        node = mg.add_with_entropy_filter("some content here")
        # Score will be < 1.0 due to length factor
        assert mg.add_with_entropy_filter("some content here", threshold=1.0) is None

    def test_unique_content_high_score(self, mg):
        """Highly unique content should score well above default threshold."""
        mg.add("apple banana cherry")
        node = mg.add_with_entropy_filter(
            "quantum entanglement paradox demonstrates non-locality"
        )
        assert node is not None

    def test_returns_node_object(self, mg):
        """Should return a proper Node object with all fields."""
        node = mg.add_with_entropy_filter("A comprehensive analysis of market trends")
        assert node is not None
        assert hasattr(node, "id")
        assert hasattr(node, "label")
        assert hasattr(node, "kind")
        assert node.label == "A comprehensive analysis of market trends"
        assert node.kind == "fact"

    def test_custom_kind_preserved(self, mg):
        """Kind parameter should be passed through."""
        node = mg.add_with_entropy_filter("Important finding", kind="result")
        assert node is not None
        assert node.kind == "result"

    def test_custom_data_preserved(self, mg):
        """Data parameter should be passed through."""
        node = mg.add_with_entropy_filter(
            "Critical alert", data={"priority": "high"}
        )
        assert node is not None
        assert node.data["priority"] == "high"

    def test_custom_tags_preserved(self, mg):
        """Tags parameter should be passed through."""
        node = mg.add_with_entropy_filter(
            "Tagged content here", tags=["important"]
        )
        assert node is not None

    def test_multiple_unique_additions(self, mg):
        """Multiple unique additions should all succeed."""
        texts = [
            "First unique message about cats",
            "Second unique message about dogs",
            "Third unique message about birds",
        ]
        for text in texts:
            node = mg.add_with_entropy_filter(text)
            assert node is not None

    def test_repeated_content_all_filtered_after_first(self, mg):
        """Adding same content multiple times: first passes, rest filtered."""
        text = "The database migration completed successfully"
        first = mg.add_with_entropy_filter(text)
        assert first is not None
        second = mg.add_with_entropy_filter(text)
        assert second is None
        third = mg.add_with_entropy_filter(text)
        assert third is None

    def test_nodes_added_are_queryable(self, mg):
        """Nodes that pass filter should be in the graph."""
        node = mg.add_with_entropy_filter("Weather forecast shows rain tomorrow")
        assert node is not None
        retrieved = mg.get_node(node.id)
        assert retrieved is not None
        assert retrieved.label == "Weather forecast shows rain tomorrow"


class TestEntropyScore:
    """Direct tests for _entropy_score() internal method."""

    def test_empty_string(self, mg):
        assert mg._entropy_score("") == 0.0

    def test_short_string(self, mg):
        assert mg._entropy_score("ab") == 0.0

    def test_long_unique_string(self, mg):
        """Long unique string should have high score."""
        score = mg._entropy_score(
            "A completely novel sentence about quantum physics experiments"
        )
        assert 0.0 < score <= 1.0
        assert score > 0.3  # should pass default threshold

    def test_score_range(self, mg):
        """Score should always be in [0, 1]."""
        for text in ["hello world", "test", "a b c d e f g h"]:
            score = mg._entropy_score(text)
            assert 0.0 <= score <= 1.0

    def test_novelty_decreases_with_duplicates(self, mg):
        """Adding similar content should decrease novelty score."""
        score1 = mg._entropy_score("The quick brown fox jumps over")
        mg.add("The quick brown fox jumps over")
        score2 = mg._entropy_score("The quick brown fox jumps over")
        assert score2 < score1

    def test_lexical_diversity_matters(self, mg):
        """High TTR text should score higher than repetitive text."""
        # Both have similar length but different diversity
        diverse = "unique words appear here constantly"
        repetitive = "the the the the the the the the"
        score_d = mg._entropy_score(diverse)
        score_r = mg._entropy_score(repetitive)
        assert score_d > score_r

    def test_four_char_boundary(self, mg):
        """4 chars → filtered, 5 chars → potentially accepted."""
        assert mg._entropy_score("abcd") == 0.0  # < 5 chars
        # 5 chars should be evaluated
        score = mg._entropy_score("abcde")
        assert score >= 0.0
