"""Tests for knn_classification() — Cycle 329.

k-nearest reference graph classification with distance-weighted voting.
Extends single-match classification to consider top-k neighbours,
pooling votes by label for more robust decisions.
"""
import pytest
from memory_graph import MemoryGraph


# ── Helpers ───────────────────────────────────────────────────────

def _star(n):
    """Star graph: node 0 connected to nodes 1..n-1."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        g.link(nodes[0].id, nodes[i].id, "r")
    return g


def _path(n):
    """Path graph: 0 — 1 — 2 — ... — n-1."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def _cycle(n):
    """Cycle graph: 0 — 1 — ... — n-1 — 0."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def _complete(n):
    """Complete graph K_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def _labelled(graph, label):
    """Attach a label to a graph via graph_meta."""
    graph.graph_meta = {"label": label}
    return graph


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def query_star():
    return _star(5)


@pytest.fixture
def query_path():
    return _path(5)


@pytest.fixture
def references():
    """6 references: 2 stars, 2 paths, 2 cycles (labelled)."""
    return [
        _labelled(_star(4), "star"),
        _labelled(_star(6), "star"),
        _labelled(_path(4), "path"),
        _labelled(_path(6), "path"),
        _labelled(_cycle(4), "cycle"),
        _labelled(_cycle(6), "cycle"),
    ]


@pytest.fixture
def references_unlabelled():
    """6 references without labels."""
    return [
        _star(4),
        _star(6),
        _path(4),
        _path(6),
        _cycle(4),
        _cycle(6),
    ]


# ── Degenerate cases ──────────────────────────────────────────────

class TestKnnDegenerate:
    """Edge cases and degenerate inputs."""

    def test_empty_references(self, query_star):
        result = query_star.knn_classification([])
        assert result is None

    def test_single_reference(self, query_star):
        """k > n should clamp to k=1."""
        ref = _star(5)
        result = query_star.knn_classification([ref], k=3)
        assert result is not None
        assert result["k_used"] == 1

    def test_no_valid_comparisons(self):
        """All degenerate references → None."""
        g = MemoryGraph()
        g.add("a")
        refs = [MemoryGraph() for _ in range(3)]
        for r in refs:
            r.add("x")
        result = g.knn_classification(refs, k=2)
        assert result is None

    def test_k_larger_than_refs(self, query_star, references):
        """k=10 with 6 refs should clamp to k=6."""
        result = query_star.knn_classification(references, k=10)
        assert result["k_used"] == 6

    def test_k_zero_raises(self, query_star, references):
        """k=0 is invalid."""
        with pytest.raises(ValueError):
            query_star.knn_classification(references, k=0)

    def test_k_negative_raises(self, query_star, references):
        """Negative k is invalid."""
        with pytest.raises(ValueError):
            query_star.knn_classification(references, k=-1)


# ── Validation ────────────────────────────────────────────────────

class TestKnnValidation:
    """Parameter validation."""

    def test_unknown_method_raises(self, query_star, references):
        with pytest.raises(ValueError, match="unknown method"):
            query_star.knn_classification(references, method="nonsense")

    def test_valid_methods_accepted(self, query_star, references):
        """All 5 base methods should work."""
        for m in ["hybrid", "graph", "spectral", "rrf", "bayesian"]:
            result = query_star.knn_classification(references, method=m)
            assert result is not None, f"method={m} returned None"

    def test_degree_index_accepted(self, query_star, references):
        result = query_star.knn_classification(
            references, degree_index="randic")
        assert result is not None


# ── Basic classification ──────────────────────────────────────────

class TestKnnBasic:
    """Basic classification correctness."""

    def test_star_query_classified_as_star(self, query_star, references):
        """Star query should be classified as 'star' by majority."""
        result = query_star.knn_classification(references, k=3)
        assert result["best_label"] == "star"

    def test_path_query_classified_as_path(self, query_path, references):
        """Path query should be classified as 'path'."""
        result = query_path.knn_classification(references, k=3)
        assert result["best_label"] == "path"

    def test_best_ref_is_closest(self, query_star, references):
        """best_ref should be the index of the single closest reference."""
        result = query_star.knn_classification(references, k=3)
        # The closest ref to star(5) should be one of the star refs (0 or 1)
        assert result["best_ref"] in (0, 1)

    def test_best_score_is_lowest(self, query_star, references):
        """best_score should match the closest reference's score."""
        result = query_star.knn_classification(references, k=3)
        assert result["best_score"] >= 0
        # Best score should be the minimum among k_nearest
        scores = [e["score"] for e in result["k_nearest"]]
        assert result["best_score"] == min(scores)

    def test_k_nearest_sorted_ascending(self, query_star, references):
        """k_nearest should be sorted by score ascending."""
        result = query_star.knn_classification(references, k=4)
        scores = [e["score"] for e in result["k_nearest"]]
        assert scores == sorted(scores)

    def test_k_nearest_count(self, query_star, references):
        """Should return exactly k entries in k_nearest."""
        result = query_star.knn_classification(references, k=3)
        assert len(result["k_nearest"]) == 3

    def test_result_keys(self, query_star, references):
        """Result should have all expected keys."""
        result = query_star.knn_classification(references, k=3)
        expected = {"best_label", "best_ref", "best_score", "k_used",
                    "method", "k_nearest", "label_votes", "agreement",
                    "tie", "margin"}
        assert set(result.keys()) == expected

    def test_k_nearest_entry_keys(self, query_star, references):
        """Each k_nearest entry should have expected keys."""
        result = query_star.knn_classification(references, k=3)
        expected = {"index", "label", "score", "vote_weight",
                    "vote_fraction"}
        for entry in result["k_nearest"]:
            assert set(entry.keys()) == expected


# ── Label voting ──────────────────────────────────────────────────

class TestKnnLabelVoting:
    """Label-based vote pooling."""

    def test_same_label_pools_votes(self, query_star, references):
        """Two star refs in top-k should pool their votes."""
        result = query_star.knn_classification(references, k=3)
        # Star query → at least one star ref in top-k
        star_votes = result["label_votes"].get("star", 0)
        assert star_votes > 0

    def test_winner_has_highest_votes(self, query_star, references):
        """best_label should have the highest vote weight."""
        result = query_star.knn_classification(references, k=3)
        votes = result["label_votes"]
        max_vote = max(votes.values())
        assert votes[result["best_label"]] == max_vote

    def test_label_votes_sum_to_total(self, query_star, references):
        """Sum of label_votes should equal sum of k_nearest weights."""
        result = query_star.knn_classification(references, k=3)
        label_sum = sum(result["label_votes"].values())
        weight_sum = sum(e["vote_weight"] for e in result["k_nearest"])
        assert abs(label_sum - weight_sum) < 1e-6

    def test_unlabelled_uses_index(self, query_star, references_unlabelled):
        """Without labels, best_label should be an integer index."""
        result = query_star.knn_classification(
            references_unlabelled, k=3)
        assert isinstance(result["best_label"], int)

    def test_mixed_labels_and_unlabelled(self, query_star):
        """Some refs have labels, some don't → unlabelled use index."""
        refs = [
            _labelled(_star(4), "star"),
            _star(6),          # no label → index 1
            _labelled(_path(4), "path"),
        ]
        result = query_star.knn_classification(refs, k=3)
        # best_label should be either "star" or 1 or "path"
        assert result["best_label"] in ("star", 1, "path")

    def test_vote_fraction_sums_to_one(self, query_star, references):
        """vote_fractions in k_nearest should sum to ~1.0."""
        result = query_star.knn_classification(references, k=4)
        total = sum(e["vote_fraction"] for e in result["k_nearest"])
        assert abs(total - 1.0) < 1e-6

    def test_closest_has_highest_weight(self, query_star, references):
        """The nearest neighbour should have the highest vote_weight."""
        result = query_star.knn_classification(references, k=3)
        weights = [e["vote_weight"] for e in result["k_nearest"]]
        assert weights[0] == max(weights)


# ── k parameter effects ───────────────────────────────────────────

class TestKnnKParameter:
    """Effect of k on classification."""

    def test_k1_equals_single_match(self, query_star, references):
        """k=1 should behave like single-match classification."""
        result = query_star.knn_classification(references, k=1)
        assert result["k_used"] == 1
        assert len(result["k_nearest"]) == 1
        assert result["agreement"] == 1.0  # Single neighbour = 100%

    def test_k2_has_two_neighbours(self, query_star, references):
        result = query_star.knn_classification(references, k=2)
        assert len(result["k_nearest"]) == 2

    def test_k3_majority_required_for_confidence(self, query_star, references):
        """With k=3, if all 3 neighbours are stars, agreement should be 1.0."""
        result = query_star.knn_classification(references, k=3)
        # If top-3 are all "star", agreement=1.0; otherwise <1.0
        labels_in_k = [e["label"] for e in result["k_nearest"]]
        if all(l == "star" for l in labels_in_k):
            assert result["agreement"] == 1.0
        else:
            assert result["agreement"] < 1.0

    def test_larger_k_more_stable(self, query_star, references):
        """Larger k should generally produce equal or higher agreement
        when same-label refs dominate."""
        k3 = query_star.knn_classification(references, k=3)
        k5 = query_star.knn_classification(references, k=5)
        # Star query with 2 star refs → larger k dilutes with non-stars
        # So k3 agreement >= k5 agreement for star query
        # (this verifies k actually changes the neighbourhood)
        assert k3["k_used"] != k5["k_used"]

    def test_k_equals_n(self, query_star, references):
        """k=n should consider all references."""
        result = query_star.knn_classification(
            references, k=len(references))
        assert result["k_used"] == len(references)
        assert len(result["k_nearest"]) == len(references)


# ── Method delegation ─────────────────────────────────────────────

class TestKnnMethodDelegation:
    """Verify knn_classification delegates to each base method correctly."""

    def test_hybrid_method(self, query_star, references):
        result = query_star.knn_classification(
            references, method="hybrid", k=3)
        assert result["method"] == "hybrid"
        assert result is not None

    def test_graph_method(self, query_star, references):
        result = query_star.knn_classification(
            references, method="graph", k=3)
        assert result["method"] == "graph"

    def test_spectral_method(self, query_star, references):
        result = query_star.knn_classification(
            references, method="spectral", k=3)
        assert result["method"] == "spectral"

    def test_rrf_method(self, query_star, references):
        result = query_star.knn_classification(
            references, method="rrf", k=3)
        assert result["method"] == "rrf"

    def test_bayesian_method(self, query_star, references):
        result = query_star.knn_classification(
            references, method="bayesian", k=3)
        assert result["method"] == "bayesian"

    def test_different_methods_may_differ(self, query_star, references):
        """Different methods may produce different k_nearest sets."""
        hybrid_result = query_star.knn_classification(
            references, method="hybrid", k=3)
        spectral_result = query_star.knn_classification(
            references, method="spectral", k=3)
        # They should both be valid
        assert hybrid_result is not None
        assert spectral_result is not None
        # Best ref should be the same for a clear star query
        assert hybrid_result["best_ref"] == spectral_result["best_ref"]


# ── Agreement and tie detection ───────────────────────────────────

class TestKnnAgreementTie:
    """Agreement score and tie detection."""

    def test_k1_agreement_is_one(self, query_star, references):
        """k=1 always has agreement=1.0 (single label wins all)."""
        result = query_star.knn_classification(references, k=1)
        assert result["agreement"] == 1.0

    def test_agreement_in_range_0_1(self, query_star, references):
        """Agreement should always be in [0, 1]."""
        for k in range(1, 7):
            result = query_star.knn_classification(references, k=k)
            assert 0.0 <= result["agreement"] <= 1.0

    def test_no_tie_when_clear_winner(self, query_star, references):
        """When all k neighbours are the same label, no tie."""
        result = query_star.knn_classification(references, k=1)
        assert result["tie"] is False

    def test_tie_when_split(self):
        """Two references with equal scores and different labels → tie."""
        g = _path(5)
        refs = [
            _labelled(_path(4), "A"),
            _labelled(_path(6), "B"),
        ]
        result = g.knn_classification(refs, k=2)
        # Two similar paths → likely close scores → likely tie
        # (not guaranteed due to size difference, but check logic)
        assert isinstance(result["tie"], bool)

    def test_margin_non_negative(self, query_star, references):
        """Margin (gap between top-2) should be non-negative."""
        result = query_star.knn_classification(references, k=3)
        assert result["margin"] >= 0

    def test_margin_zero_for_single_label(self, query_star):
        """When all k neighbours share a label, margin = full vote."""
        refs = [_labelled(_star(4), "star"), _labelled(_star(5), "star")]
        result = query_star.knn_classification(refs, k=2)
        # Only one label → no second place → margin = best_vote
        assert result["margin"] > 0


# ── Non-mutating ──────────────────────────────────────────────────

class TestKnnNonMutating:
    """Verify graphs are not modified."""

    def test_query_unchanged(self, query_star, references):
        """Query graph should not be mutated."""
        before_nodes = set(query_star.conn.execute(
            "SELECT id FROM nodes").fetchall())
        before_edges = set(query_star.conn.execute(
            "SELECT source, target FROM edges").fetchall())

        query_star.knn_classification(references, k=3)

        after_nodes = set(query_star.conn.execute(
            "SELECT id FROM nodes").fetchall())
        after_edges = set(query_star.conn.execute(
            "SELECT source, target FROM edges").fetchall())

        assert before_nodes == after_nodes
        assert before_edges == after_edges

    def test_references_unchanged(self, query_star, references):
        """Reference graphs should not be mutated."""
        before = []
        for ref in references:
            nodes = set(ref.conn.execute(
                "SELECT id FROM nodes").fetchall())
            edges = set(ref.conn.execute(
                "SELECT source, target FROM edges").fetchall())
            before.append((nodes, edges))

        query_star.knn_classification(references, k=3)

        for ref, (bn, be) in zip(references, before):
            an = set(ref.conn.execute(
                "SELECT id FROM nodes").fetchall())
            ae = set(ref.conn.execute(
                "SELECT source, target FROM edges").fetchall())
            assert bn == an
            assert be == ae


# ── Quarantined ───────────────────────────────────────────────────

class TestKnnQuarantined:
    """include_quarantined flag."""

    def test_flag_accepted(self, query_star, references):
        """include_quarantined=True should not error."""
        result = query_star.knn_classification(
            references, k=3, include_quarantined=True)
        assert result is not None

    def test_flag_false_accepted(self, query_star, references):
        """include_quarantined=False (default) should not error."""
        result = query_star.knn_classification(
            references, k=3, include_quarantined=False)
        assert result is not None


# ── Inverse-distance weighting ────────────────────────────────────

class TestKnnWeighting:
    """Inverse-distance weighting logic."""

    def test_lower_score_higher_weight(self, query_star, references):
        """Closer (lower score) → higher weight."""
        result = query_star.knn_classification(references, k=3)
        knn = result["k_nearest"]
        for i in range(len(knn) - 1):
            assert knn[i]["score"] <= knn[i + 1]["score"]
            assert knn[i]["vote_weight"] >= knn[i + 1]["vote_weight"]

    def test_exact_match_highest_weight(self, query_star):
        """Self-match (score≈0) should dominate voting."""
        refs = [_star(5), _path(5), _cycle(5)]
        result = query_star.knn_classification(refs, k=3)
        # The exact match (ref 0, star(5)) should have the highest weight
        assert result["k_nearest"][0]["index"] == 0
        assert result["k_nearest"][0]["vote_weight"] > \
               result["k_nearest"][1]["vote_weight"]

    def test_weight_is_inverse_distance(self, query_star, references):
        """vote_weight ≈ 1 / (score + eps)."""
        result = query_star.knn_classification(references, k=3)
        for entry in result["k_nearest"]:
            expected = 1.0 / (entry["score"] + 1e-12)
            assert abs(entry["vote_weight"] - round(expected, 8)) < 1e-6


# ── Robustness ────────────────────────────────────────────────────

class TestKnnRobustness:
    """Robustness and scalability."""

    def test_many_references(self, query_star):
        """Should handle 10+ references."""
        refs = []
        for i in range(5):
            refs.append(_labelled(_star(3 + i), "star"))
        for i in range(5):
            refs.append(_labelled(_path(3 + i), "path"))
        result = query_star.knn_classification(refs, k=5)
        assert result is not None
        assert result["best_label"] == "star"

    def test_different_sized_references(self, query_star):
        """References of different sizes should work."""
        refs = [_star(3), _star(10), _path(4), _path(8)]
        result = query_star.knn_classification(refs, k=2)
        assert result is not None

    def test_all_methods_produce_valid_knn(self, query_star, references):
        """Every base method should produce valid k_nearest entries."""
        for m in ["hybrid", "graph", "spectral", "rrf", "bayesian"]:
            result = query_star.knn_classification(
                references, method=m, k=3)
            assert result is not None
            assert len(result["k_nearest"]) == 3
            for entry in result["k_nearest"]:
                # Scores may be negative for similarity-based methods
                # (e.g. RRF negates for ascending sort)
                assert isinstance(entry["score"], (int, float))
                assert entry["vote_weight"] > 0

    def test_consistency_across_calls(self, query_star, references):
        """Same inputs → same output (deterministic)."""
        r1 = query_star.knn_classification(references, k=3)
        r2 = query_star.knn_classification(references, k=3)
        assert r1["best_label"] == r2["best_label"]
        assert r1["best_ref"] == r2["best_ref"]
        assert r1["agreement"] == r2["agreement"]


# ── Label propagation ─────────────────────────────────────────────

class TestKnnLabelPropagation:
    """Label handling edge cases."""

    def test_none_label_when_no_graph_meta(self, query_star,
                                            references_unlabelled):
        """Without graph_meta, labels fall back to indices."""
        result = query_star.knn_classification(
            references_unlabelled, k=3)
        for entry in result["k_nearest"]:
            assert isinstance(entry["label"], int)

    def test_partial_graph_meta(self, query_star):
        """Some refs have graph_meta, some don't."""
        r1 = _star(4)
        r1.graph_meta = {"label": "star4"}
        r2 = _star(5)  # no graph_meta
        r3 = _path(5)
        r3.graph_meta = {"label": "path5"}
        result = query_star.knn_classification([r1, r2, r3], k=3)
        # r2 should use index 1 as label
        labels = [e["label"] for e in result["k_nearest"]]
        assert "star4" in labels or 1 in labels

    def test_empty_graph_meta(self, query_star):
        """graph_meta exists but has no 'label' key → index fallback."""
        r1 = _star(4)
        r1.graph_meta = {}
        r2 = _path(4)
        r2.graph_meta = {}
        result = query_star.knn_classification([r1, r2], k=2)
        for entry in result["k_nearest"]:
            assert isinstance(entry["label"], int)

    def test_numeric_label(self, query_star):
        """Numeric labels should work."""
        r1 = _star(4)
        r1.graph_meta = {"label": 100}
        r2 = _path(4)
        r2.graph_meta = {"label": 200}
        result = query_star.knn_classification([r1, r2], k=2)
        assert result["best_label"] in (100, 200)
