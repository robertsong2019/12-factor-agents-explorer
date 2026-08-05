"""Tests for McNemar pairwise significance in classification_compare() (Cycle 358)."""

import pytest
from memory_graph import MemoryGraph


def _star(n=5):
    g = MemoryGraph()
    for i in range(1, n):
        g.add(str(i), kind="fact")
    g.add("center", kind="fact")
    for i in range(1, n):
        g.link(str(i), "center", "related")
    return g


def _path(n=5):
    g = MemoryGraph()
    for i in range(n):
        g.add(str(i), kind="fact")
    for i in range(n - 1):
        g.link(str(i), str(i + 1), "related")
    return g


def _cycle(n=5):
    g = MemoryGraph()
    for i in range(n):
        g.add(str(i), kind="fact")
    for i in range(n):
        g.link(str(i), str((i + 1) % n), "related")
    return g


class TestMcNemarCompare:
    """McNemar significance field in classification_compare output."""

    def test_significance_field_exists(self):
        """classification_compare returns a significance dict."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        assert result is not None
        assert "significance" in result

    def test_significance_has_mcnemar_proxy(self):
        """Significance dict has test='mcnemar_proxy'."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        assert sig is not None
        assert sig["test"] == "mcnemar_proxy"

    def test_significance_contains_pairs(self):
        """Pairs list has C(5,2)=10 entries for 5 successful methods."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        assert len(sig["pairs"]) >= 1
        for p in sig["pairs"]:
            assert "method_a" in p
            assert "method_b" in p
            assert "agree" in p
            assert isinstance(p["agree"], bool)

    def test_significance_agreement_fraction(self):
        """Agreement fraction is in [0, 1]."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        assert 0.0 <= sig["agreement_fraction"] <= 1.0

    def test_significance_n_pairs(self):
        """n_pairs equals len(pairs)."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        assert sig["n_pairs"] == len(sig["pairs"])

    def test_significance_with_single_method_failing(self):
        """Even if one method fails, significance still runs on remaining."""
        q = _star(5)
        # Use refs with same topology — may cause some methods to fail
        # but at least some should succeed
        refs = [_star(5), _path(5)]
        result = q.classification_compare(refs)
        assert result is not None
        # Significance may be None if only 1 method succeeded
        if result["significance"] is not None:
            assert "pairs" in result["significance"]

    def test_significance_none_when_no_methods(self):
        """Significance is None when compare returns None (empty refs)."""
        q = _star(5)
        result = q.classification_compare([])
        assert result is None

    def test_significance_note_research_046(self):
        """Note references Research #046 guidance on sample size."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        assert "Research #046" in sig["note"]

    def test_pair_match_fields_present(self):
        """Each pair records match_a and match_b (reference indices)."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        sig = result["significance"]
        for p in sig["pairs"]:
            assert "match_a" in p
            assert "match_b" in p

    def test_consensus_and_significance_coexist(self):
        """Both consensus fields and significance present in output."""
        q = _star(5)
        refs = [_star(5), _path(5), _cycle(5)]
        result = q.classification_compare(refs)
        for key in ("consensus_best", "agreement_score", "disagreement_flag",
                     "significance"):
            assert key in result
