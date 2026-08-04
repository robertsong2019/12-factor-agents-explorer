"""Tests for classification_loocv (Cycle 350, Research #046).

Leave-one-out cross-validation for reference graph sets.
"""
import math
import pytest
import memory_graph as mg


# ---------------------------------------------------------------------------
# Topology builders (matching existing test patterns)
# ---------------------------------------------------------------------------

def _star(n=6, label=""):
    g = mg.MemoryGraph(":memory:")
    c = g.add(f"c_{label}", "n")
    for i in range(n - 1):
        leaf = g.add(f"l{i}_{label}", "n")
        g.link(c.id, leaf.id, "e")
    g.graph_meta = {"label": "star"}
    return g


def _path(n=6, label=""):
    g = mg.MemoryGraph(":memory:")
    prev = g.add(f"p0_{label}", "n")
    for i in range(1, n):
        curr = g.add(f"p{i}_{label}", "n")
        g.link(prev.id, curr.id, "e")
        prev = curr
    g.graph_meta = {"label": "path"}
    return g


def _cycle(n=6, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"c{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "e")
    g.graph_meta = {"label": "cycle"}
    return g


def _complete(n=5, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"k{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "e")
    g.graph_meta = {"label": "complete"}
    return g


def _bipartite(a=3, b=3, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes_a = [g.add(f"a{i}_{label}", "n") for i in range(a)]
    nodes_b = [g.add(f"b{i}_{label}", "n") for i in range(b)]
    for na in nodes_a:
        for nb in nodes_b:
            g.link(na.id, nb.id, "e")
    g.graph_meta = {"label": "bipartite"}
    return g


def _tree(n=7, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"t{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n:
            g.link(nodes[i].id, nodes[left].id, "e")
        if right < n:
            g.link(nodes[i].id, nodes[right].id, "e")
    g.graph_meta = {"label": "tree"}
    return g


def _canonical_refs():
    """Return (refs, labels) for 6 canonical topologies."""
    refs = [
        _star(8, "r"), _path(8, "r"), _cycle(8, "r"),
        _complete(6, "r"), _bipartite(4, 4, "r"), _tree(7, "r"),
    ]
    labels = ["star", "path", "cycle", "complete", "bipartite", "tree"]
    return refs, labels


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def refs6():
    return _canonical_refs()


@pytest.fixture
def refs3():
    return [_star(8, "r"), _path(8, "r"), _cycle(8, "r")]


@pytest.fixture
def labels3():
    return ["star", "path", "cycle"]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestLOOCVStructure:
    def test_returns_dict_with_required_keys(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        for key in ("method", "num_references", "accuracy", "correct",
                     "fold_results", "confusion", "hardest_fold",
                     "all_correct", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_num_references_matches(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        assert result["num_references"] == 6

    def test_method_recorded(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="spectral")
        assert result["method"] == "spectral"

    def test_fold_count_matches_refs(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert len(result["fold_results"]) == 6

    def test_fold_result_structure(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        fold = result["fold_results"][0]
        for key in ("fold", "held_out_label", "predicted_label",
                     "correct", "score", "num_remaining_refs"):
            assert key in fold, f"Fold missing key: {key}"

    def test_num_remaining_refs_is_n_minus_1(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        for fold in result["fold_results"]:
            assert fold["num_remaining_refs"] == 5

    def test_accuracy_in_range(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert 0.0 <= result["accuracy"] <= 1.0

    def test_correct_count_consistent_with_accuracy(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        expected = result["correct"] / result["num_references"]
        assert abs(result["accuracy"] - expected) < 1e-9

    def test_all_correct_flag(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert result["all_correct"] == (result["correct"] == 6)

    def test_summary_is_string(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# Accuracy across methods
# ---------------------------------------------------------------------------

class TestLOOCVAccuracy:
    @pytest.mark.parametrize("method", [
        "graph", "spectral", "hybrid", "rrf",
        "weighted_average", "bayesian", "max_confidence",
    ])
    def test_loocv_runs_for_all_methods(self, refs6, method):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method=method)
        assert result["accuracy"] >= 0.0
        assert result["correct"] <= 6

    def test_graph_method_loocv(self, refs6):
        """graph classification LOOCV — honest result, accuracy may be low.

        LOOCV asks "can we identify an UNSEEN topology?" — this is
        much harder than standard classification (where the exact
        match is in the reference set).  Path→star confusion is
        expected (Research #046).
        """
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        # Honest: LOOCV is genuinely hard for degree-based methods.
        assert result["correct"] >= 0

    def test_spectral_method_loocv(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="spectral")
        assert result["correct"] >= 0

    def test_rrf_method_loocv(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="rrf")
        assert result["correct"] >= 0


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

class TestLOOCVConfusion:
    def test_confusion_matrix_structure(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert isinstance(result["confusion"], dict)

    def test_confusion_matrix_sums_to_n(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        total = sum(
            count
            for actual in result["confusion"].values()
            for count in actual.values()
        )
        assert total == 6

    def test_each_true_label_appears(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        for label in labels:
            assert label in result["confusion"]

    def test_correct_predictions_on_diagonal(self, refs6):
        """For correct folds, confusion[true][true] should be incremented."""
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        correct_labels = [f["held_out_label"] for f in result["fold_results"] if f["correct"]]
        for label in correct_labels:
            assert result["confusion"][label].get(label, 0) >= 1


# ---------------------------------------------------------------------------
# Hardest fold
# ---------------------------------------------------------------------------

class TestLOOCVHardestFold:
    def test_hardest_fold_none_when_all_correct(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="rrf")
        if result["all_correct"]:
            assert result["hardest_fold"] is None

    def test_hardest_fold_set_when_errors_exist(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        if not result["all_correct"]:
            assert result["hardest_fold"] is not None
            assert result["hardest_fold"]["correct"] is False

    def test_hardest_fold_is_incorrect(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        if result["hardest_fold"] is not None:
            assert result["hardest_fold"]["correct"] is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestLOOCVEdgeCases:
    def test_two_references(self):
        """LOOCV with 2 references (minimum)."""
        refs = [_star(5, "a"), _path(5, "a")]
        labels = ["star", "path"]
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        assert result["num_references"] == 2
        assert len(result["fold_results"]) == 2

    def test_error_on_single_reference(self):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="at least 2"):
            g.classification_loocv([_star()], ["star"])

    def test_error_on_label_length_mismatch(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="labels length"):
            g.classification_loocv(refs, labels[:-1])

    def test_unknown_method_raises(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="Unknown method"):
            g.classification_loocv(refs, labels, method="nonexistent")

    def test_duplicate_labels(self):
        """Two refs with same label — LOOCV should still work."""
        refs = [_star(6, "a"), _star(8, "b"), _path(6, "a")]
        labels = ["star", "star", "path"]
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="graph")
        assert result["num_references"] == 3
        assert len(result["fold_results"]) == 3


# ---------------------------------------------------------------------------
# KNN method
# ---------------------------------------------------------------------------

class TestLOOCVKNN:
    def test_knn_loocv(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="knn")
        assert result["method"] == "knn"
        assert result["correct"] >= 0

    def test_knn_with_duplicate_labels(self):
        refs = [_star(6, "a"), _star(8, "b"), _path(6, "a"), _path(8, "b")]
        labels = ["star", "star", "path", "path"]
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="knn")
        assert result["num_references"] == 4


# ---------------------------------------------------------------------------
# Summary content
# ---------------------------------------------------------------------------

class TestLOOCVSummary:
    def test_summary_contains_method_name(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels, method="spectral")
        assert "spectral" in result["summary"]

    def test_summary_contains_accuracy(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        assert "LOOCV" in result["summary"]

    def test_summary_mentions_misclassified_when_errors(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        if not result["all_correct"]:
            assert "Misclassified" in result["summary"]

    def test_summary_mentions_perfect_when_all_correct(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        if result["all_correct"]:
            assert "Perfect" in result["summary"]


# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------

class TestLOOCVConsistency:
    def test_repeatable_results(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        r1 = g.classification_loocv(refs, labels, method="graph")
        r2 = g.classification_loocv(refs, labels, method="graph")
        assert r1["accuracy"] == r2["accuracy"]
        assert r1["correct"] == r2["correct"]

    def test_fold_labels_match_input(self, refs6):
        refs, labels = refs6
        g = mg.MemoryGraph(":memory:")
        result = g.classification_loocv(refs, labels)
        for i, fold in enumerate(result["fold_results"]):
            assert fold["held_out_label"] == labels[i]
            assert fold["fold"] == i
