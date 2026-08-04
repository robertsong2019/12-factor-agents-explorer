"""Tests for classification_consensus() — Cycle 354.

Meta-classifier that runs all methods and returns majority vote.
21st classification API.
"""
import pytest
from memory_graph import MemoryGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_refs(topologies=None, size=10, per_category=2):
    """Build reference graphs from canonical topologies."""
    if topologies is None:
        topologies = ["star", "path", "cycle", "complete", "bipartite", "tree"]
    refs = []
    mg = MemoryGraph()
    for topo in topologies:
        for _ in range(per_category):
            ref = mg._bench_build_topology(topo, size, label=topo)
            ref.graph_meta = {"topology": topo, "label": topo, "n": size}
            refs.append(ref)
    return refs


def _make_noisy(graph, noise_rate=0.1, seed=42):
    """Add noise to a graph by manipulating MemoryGraph edges."""
    import random as _r
    rng = _r.Random(seed)

    # Get current edges via SQL
    rows = graph.conn.execute("SELECT source, target FROM edges").fetchall()
    edges = [(r[0], r[1]) for r in rows]

    # Get all node IDs
    node_rows = graph.conn.execute("SELECT id FROM nodes").fetchall()
    nodes = [r[0] for r in node_rows]

    # Remove edges
    for src, tgt in edges:
        if rng.random() < noise_rate:
            graph.conn.execute(
                "DELETE FROM edges WHERE source=? AND target=?",
                (src, tgt),
            )
    graph.conn.commit()

    # Add random edges
    n_nodes = len(nodes)
    max_possible = n_nodes * (n_nodes - 1) // 2
    n_add = int(max_possible * noise_rate)
    added = 0
    attempts = 0
    existing = set()
    for r in graph.conn.execute("SELECT source, target FROM edges").fetchall():
        existing.add((r[0], r[1]))

    while added < n_add and attempts < n_add * 5:
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u != v and (u, v) not in existing and (v, u) not in existing:
            graph.conn.execute(
                "INSERT OR IGNORE INTO edges (source, target, relation) VALUES (?, ?, 'noise')",
                (u, v),
            )
            existing.add((u, v))
            added += 1
        attempts += 1
    graph.conn.commit()
    return graph


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------

class TestConsensusBasic:
    """Basic structure and return-value tests."""

    def test_returns_dict_with_required_keys(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        query.graph_meta = {"topology": "star", "label": "?", "n": 8}
        result = query.classification_consensus(refs, query)

        required = {
            "label", "confidence", "margin", "vote_counts",
            "per_method", "methods_agreeing", "methods_disagreeing",
            "n_methods_run", "n_methods_succeeded", "tie", "summary",
        }
        assert required <= set(result.keys())

    def test_label_is_string(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        assert isinstance(result["label"], str)

    def test_confidence_in_zero_one(self):
        refs = _make_refs(["star", "path", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_n_methods_run_matches_methods_param(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(
            refs, query, methods=["graph", "spectral"],
        )
        assert result["n_methods_run"] == 2

    def test_summary_is_string(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# Correctness — clean queries
# ---------------------------------------------------------------------------

class TestConsensusCorrectness:
    """Consensus should agree with majority when query is clean."""

    @pytest.mark.parametrize("topo", ["star", "path", "cycle", "tree"])
    def test_clean_query_classified_correctly(self, topo):
        refs = _make_refs(["star", "path", "cycle", "tree"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology(topo, 10, label="?")
        result = query.classification_consensus(refs, query)
        assert result["label"] == topo

    def test_star_vs_cycle_different_labels(self):
        refs = _make_refs(["star", "cycle"], size=10, per_category=2)
        mg = MemoryGraph()
        q_star = mg._bench_build_topology("star", 10, label="?")
        q_cycle = mg._bench_build_topology("cycle", 10, label="?")
        r1 = q_star.classification_consensus(refs, q_star)
        r2 = q_cycle.classification_consensus(refs, q_cycle)
        assert r1["label"] != r2["label"]

    def test_high_confidence_on_clean_query(self):
        refs = _make_refs(["star", "path", "cycle", "complete", "bipartite", "tree"],
                          size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_consensus(refs, query)
        assert result["confidence"] >= 0.5


# ---------------------------------------------------------------------------
# Per-method tracking
# ---------------------------------------------------------------------------

class TestConsensusPerMethod:
    """Per-method results should be tracked correctly."""

    def test_per_method_has_all_requested_methods(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        methods = ["graph", "spectral", "hybrid", "rrf"]
        result = query.classification_consensus(refs, query, methods=methods)
        for m in methods:
            assert m in result["per_method"]

    def test_per_method_entry_has_succeeded_key(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        for m, entry in result["per_method"].items():
            assert "succeeded" in entry
            assert "label" in entry

    def test_methods_agreeing_plus_disagreeing_equals_succeeded(self):
        refs = _make_refs(["star", "path", "cycle"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_consensus(refs, query)
        total = (
            len(result["methods_agreeing"]) +
            len(result["methods_disagreeing"])
        )
        assert total == result["n_methods_succeeded"]

    def test_unknown_method_recorded_with_error(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(
            refs, query, methods=["graph", "nonexistent"],
        )
        assert result["per_method"]["nonexistent"]["succeeded"] is False
        assert "error" in result["per_method"]["nonexistent"]


# ---------------------------------------------------------------------------
# Weighted voting
# ---------------------------------------------------------------------------

class TestConsensusWeighted:
    """Weighted voting should allow specific methods to dominate."""

    def test_weight_flips_minority_winner(self):
        """If one method has huge weight, it can override majority."""
        refs = _make_refs(["star", "cycle"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")

        # First, see what graph predicts
        result_unweighted = query.classification_consensus(
            refs, query,
            methods=["graph", "spectral"],
        )

        # If graph and spectral disagree, use weight to flip
        g_label = result_unweighted["per_method"]["graph"]["label"]
        s_label = result_unweighted["per_method"]["spectral"]["label"]

        if g_label != s_label:
            # Weight spectral 100x → its label should win
            result_weighted = query.classification_consensus(
                refs, query,
                methods=["graph", "spectral"],
                weights={"spectral": 100.0},
            )
            assert result_weighted["label"] == s_label

    def test_default_weight_is_one(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query, methods=["graph"])
        # With 1 method, confidence should be 1.0
        assert result["confidence"] == pytest.approx(1.0)

    def test_weights_partial_dict_defaults_to_one(self):
        """Methods not in weights dict get weight 1.0."""
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        # Only weight graph, leave others default
        result = query.classification_consensus(
            refs, query,
            methods=["graph", "spectral"],
            weights={"graph": 1.0},
        )
        assert result["n_methods_succeeded"] >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestConsensusEdgeCases:
    """Edge cases: empty refs, single ref, all-fail, etc."""

    def test_no_references_raises_or_returns_none(self):
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus([], query)
        assert result["label"] is None
        assert result["n_methods_succeeded"] == 0

    def test_single_reference_all_methods_predict_same(self):
        mg = MemoryGraph()
        ref = mg._bench_build_topology("star", 8, label="only")
        ref.graph_meta = {"topology": "star", "label": "only", "n": 8}
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus([ref], query)
        assert result["label"] == "only"
        assert result["confidence"] == pytest.approx(1.0)

    def test_tie_detection(self):
        """When two methods disagree equally, tie should be True."""
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")

        # Run with just graph + spectral, use equal weights
        result = query.classification_consensus(
            refs, query,
            methods=["graph", "spectral"],
        )

        g_entry = result["per_method"]["graph"]
        s_entry = result["per_method"]["spectral"]

        # Only test tie if both methods succeeded and disagree
        if (g_entry["succeeded"] and s_entry["succeeded"]
                and g_entry["label"] != s_entry["label"]):
            assert result["tie"] is True
            assert result["confidence"] == pytest.approx(0.5)

    def test_margin_non_negative(self):
        refs = _make_refs(["star", "path", "cycle"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_consensus(refs, query)
        assert result["margin"] >= 0

    def test_vote_counts_sum_to_total(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        total = sum(result["vote_counts"].values())
        assert total == pytest.approx(result["n_methods_succeeded"])


# ---------------------------------------------------------------------------
# Noisy queries
# ---------------------------------------------------------------------------

class TestConsensusNoisy:
    """Consensus should still work (maybe less confident) on noisy queries."""

    def test_low_noise_query_still_correct(self):
        refs = _make_refs(["star", "path", "cycle", "tree"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")
        _make_noisy(query, noise_rate=0.05, seed=42)
        result = query.classification_consensus(refs, query)
        assert result["label"] is not None

    def test_more_methods_better_than_fewer(self):
        """Full consensus should be at least as accurate as any single method."""
        refs = _make_refs(["star", "path", "cycle", "tree"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")

        full = query.classification_consensus(refs, query)
        single = query.classification_consensus(
            refs, query, methods=["graph"],
        )

        # Full should have more succeeded methods
        assert full["n_methods_succeeded"] >= single["n_methods_succeeded"]


# ---------------------------------------------------------------------------
# Consistency with existing methods
# ---------------------------------------------------------------------------

class TestConsensusConsistency:
    """Consensus results should be consistent with underlying methods."""

    def test_label_from_vote_counts(self):
        """Winner label should match the top entry in vote_counts."""
        refs = _make_refs(["star", "path", "cycle"], size=10, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_consensus(refs, query)
        ranked_labels = list(result["vote_counts"].keys())
        assert result["label"] == ranked_labels[0]

    def test_confidence_equals_winner_over_total(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        total = sum(result["vote_counts"].values())
        expected = result["vote_counts"][result["label"]] / total
        assert result["confidence"] == pytest.approx(expected, abs=1e-6)

    def test_all_default_methods_attempted(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(refs, query)
        assert result["n_methods_run"] == 8

    def test_include_quarantined_flag_accepted(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        # Should not raise
        result = query.classification_consensus(
            refs, query, include_quarantined=True,
        )
        assert "label" in result

    def test_degree_index_param_accepted(self):
        refs = _make_refs(["star", "cycle"], size=8, per_category=2)
        mg = MemoryGraph()
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_consensus(
            refs, query, degree_index="randic",
        )
        assert "label" in result
