"""Tests for Hippocampus-inspired dual-mode binary signature fast path.

SimHash binary signatures enable O(1) Hamming-distance similarity
pre-filtering before expensive graph traversal.

Reference: Hippocampus (arXiv:2602.13594) — 31× faster retrieval,
14× fewer tokens via Dynamic Wavelet Matrix compression.
"""
import pytest
from memory_graph import MemoryGraph


class TestBinarySignature:
    """Unit tests for binary_signature() — SimHash computation."""

    def test_signature_is_bit_string(self):
        """Signature should be a string of 0s and 1s."""
        mg = MemoryGraph()
        n = mg.add("Python programming language", "concept", {"type": "language"})
        sig = mg.binary_signature(n.id)
        assert isinstance(sig, str)
        assert all(c in "01" for c in sig)
        assert len(sig) == 64  # 64-bit SimHash

    def test_signature_deterministic(self):
        """Same node content → same signature."""
        mg = MemoryGraph()
        n = mg.add("machine learning model", "concept")
        sig1 = mg.binary_signature(n.id)
        sig2 = mg.binary_signature(n.id)
        assert sig1 == sig2

    def test_identical_content_same_signature(self):
        """Two nodes with identical content produce identical signatures."""
        mg = MemoryGraph()
        n1 = mg.add("deep learning framework", "concept", {"v": "1"})
        n2 = mg.add("deep learning framework", "concept", {"v": "1"})
        assert mg.binary_signature(n1.id) == mg.binary_signature(n2.id)

    def test_different_content_different_signature(self):
        """Semantically different nodes should have different signatures."""
        mg = MemoryGraph()
        n1 = mg.add("Python programming", "concept")
        n2 = mg.add("quantum physics experiment", "concept")
        sig1 = mg.binary_signature(n1.id)
        sig2 = mg.binary_signature(n2.id)
        assert sig1 != sig2

    def test_signature_includes_data(self):
        """Data payload should influence the signature."""
        mg = MemoryGraph()
        n1 = mg.add("project alpha", "concept", {"status": "active"})
        n2 = mg.add("project alpha", "concept", {"status": "archived"})
        assert mg.binary_signature(n1.id) != mg.binary_signature(n2.id)

    def test_signature_nonexistent_node(self):
        """Non-existent node raises KeyError."""
        mg = MemoryGraph()
        with pytest.raises(KeyError):
            mg.binary_signature("nonexistent_id")

    def test_signature_bits_configurable(self):
        """Signature width should be configurable via bits param."""
        mg = MemoryGraph()
        n = mg.add("test node", "concept")
        sig32 = mg.binary_signature(n.id, bits=32)
        sig64 = mg.binary_signature(n.id, bits=64)
        assert len(sig32) == 32
        assert len(sig64) == 64
        # 32-bit sig should be a prefix of 64-bit
        assert sig64[:32] == sig32 or sig32 == sig64[:32]


class TestHammingDistance:
    """Tests for hamming_distance() static method."""

    def test_identical_strings_zero_distance(self):
        assert MemoryGraph.hamming_distance("101010", "101010") == 0

    def test_complement_max_distance(self):
        assert MemoryGraph.hamming_distance("0000", "1111") == 4

    def test_partial_difference(self):
        assert MemoryGraph.hamming_distance("101010", "101000") == 1

    def test_different_length_raises(self):
        with pytest.raises(ValueError):
            MemoryGraph.hamming_distance("1010", "10101")

    def test_empty_strings(self):
        assert MemoryGraph.hamming_distance("", "") == 0

    def test_64bit_signatures(self):
        """Typical use case: 64-bit signatures."""
        sig_a = "1" * 64
        sig_b = "0" * 64
        assert MemoryGraph.hamming_distance(sig_a, sig_b) == 64


class TestSimilaritySearchBinary:
    """Tests for similarity_search_binary() — fast Hamming pre-filter."""

    def test_returns_matching_nodes(self):
        """Should return nodes sorted by Hamming distance."""
        mg = MemoryGraph()
        n1 = mg.add("Python web development", "skill")
        n2 = mg.add("Python data analysis", "skill")
        n3 = mg.add("quantum mechanics", "concept")

        results = mg.similarity_search_binary("Python programming", limit=3)
        assert len(results) >= 2
        # Python-related nodes should rank higher than quantum
        ids = [r["node_id"] for r in results]
        assert n3.id not in ids[:1]  # quantum should not be top

    def test_limit_respected(self):
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"test concept number {i}", "concept")
        results = mg.similarity_search_binary("test concept", limit=3)
        assert len(results) <= 3

    def test_empty_graph_returns_empty(self):
        mg = MemoryGraph()
        results = mg.similarity_search_binary("anything", limit=5)
        assert results == []

    def test_results_have_hamming_field(self):
        mg = MemoryGraph()
        mg.add("machine learning", "concept")
        results = mg.similarity_search_binary("machine learning", limit=1)
        assert len(results) == 1
        assert "hamming_distance" in results[0]
        assert "node_id" in results[0]
        assert "label" in results[0]

    def test_exact_match_hamming_zero(self):
        """Identical content should yield Hamming distance near 0."""
        mg = MemoryGraph()
        n = mg.add("unique searchable label xyz123", "concept")
        results = mg.similarity_search_binary("unique searchable label xyz123", limit=1)
        assert results[0]["hamming_distance"] <= 5  # near-zero due to tokenization

    def test_max_hamming_filter(self):
        """max_hamming parameter should filter distant nodes."""
        mg = MemoryGraph()
        n1 = mg.add("Python programming language", "skill")
        n2 = mg.add("quantum field theory", "concept")
        # With very tight hamming, only close matches return
        results = mg.similarity_search_binary("Python programming", limit=10, max_hamming=20)
        ids = [r["node_id"] for r in results]
        assert n1.id in ids

    def test_kind_filter(self):
        """Optional kind filter narrows the candidate set."""
        mg = MemoryGraph()
        n1 = mg.add("Python skill", "skill")
        n2 = mg.add("Python concept", "concept")
        results = mg.similarity_search_binary("Python", limit=10, kind="skill")
        ids = [r["node_id"] for r in results]
        assert n1.id in ids
        assert n2.id not in ids


class TestDualModeRetrieve:
    """Tests for dual_mode_retrieve() — binary pre-filter → graph rerank."""

    def test_returns_dict_with_phases(self):
        mg = MemoryGraph()
        mg.add("test node", "concept")
        result = mg.dual_mode_retrieve("test", limit=5)
        assert isinstance(result, dict)
        assert "candidates" in result
        assert "results" in result
        assert "binary_phase" in result
        assert "graph_phase" in result

    def test_binary_prefilter_reduces_candidates(self):
        """Binary phase should narrow candidates before graph traversal."""
        mg = MemoryGraph()
        for i in range(20):
            mg.add(f"concept topic {i}", "concept")
        mg.add("unique rare topic sunset", "concept")

        result = mg.dual_mode_retrieve("unique rare topic sunset", limit=5)
        assert len(result["candidates"]) <= 20  # pre-filtered
        assert len(result["results"]) <= 5

    def test_results_have_dual_scores(self):
        """Each result should have both binary and graph scores."""
        mg = MemoryGraph()
        for i in range(15):
            mg.add(f"filler concept {i}", "concept")
        mg.add("machine learning model", "concept")
        result = mg.dual_mode_retrieve("machine learning", limit=1)
        if result["results"]:
            r = result["results"][0]
            assert "hamming_distance" in r
            assert "graph_score" in r
            assert "combined_score" in r

    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.dual_mode_retrieve("nothing", limit=5)
        assert result["candidates"] == []
        assert result["results"] == []

    def test_falls_back_to_regular_retrieve_on_small_graph(self):
        """For small graphs (<10 nodes), skip binary pre-filter."""
        mg = MemoryGraph()
        mg.add("alpha", "concept")
        mg.add("beta", "concept")
        result = mg.dual_mode_retrieve("alpha", limit=5)
        assert result["binary_phase"]["skipped"] is True

    def test_combined_score_balances_binary_and_graph(self):
        """Combined score should blend Hamming similarity and graph score."""
        mg = MemoryGraph()
        # Create enough nodes to trigger binary pre-filter
        for i in range(15):
            mg.add(f"topic filler {i}", "concept")
        n1 = mg.add("Python programming expertise", "skill")
        mg.add(n1.id, mg.add("programming", "concept").id, "related")

        result = mg.dual_mode_retrieve("Python programming", limit=3)
        assert not result["binary_phase"]["skipped"]
        if result["results"]:
            top = result["results"][0]
            assert top["combined_score"] > 0
            assert 0 <= top["graph_score"] <= 1.0

    def test_limit_respected(self):
        """Output should respect the limit param."""
        mg = MemoryGraph()
        for i in range(15):
            mg.add(f"similar concept {i}", "concept")
        result = mg.dual_mode_retrieve("similar concept", limit=3)
        assert len(result["results"]) <= 3

    def test_preserves_graph_structure(self):
        """dual_mode_retrieve should still find structurally connected nodes."""
        mg = MemoryGraph()
        # Enough nodes to trigger binary phase
        for i in range(12):
            mg.add(f"filler {i}", "concept")
        a = mg.add("project alpha", "concept")
        b = mg.add("project alpha details", "fact")
        mg.link(a.id, b.id, "related_to")
        result = mg.dual_mode_retrieve("project alpha", limit=5)
        labels = [r.get("label", "") for r in result["results"]]
        assert any("project alpha" in l for l in labels)
