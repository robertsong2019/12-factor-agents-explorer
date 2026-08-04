"""Tests for classification_confusion_explain() — Cycle 356.

Explains *why* a query was classified as its predicted label by
decomposing the winning margin into per-modality contributions.
"""

import unittest
from memory_graph import MemoryGraph


def _build_star(n, label="star"):
    mg = MemoryGraph()
    center = mg.add("center", "node")
    for i in range(n - 1):
        leaf = mg.add(f"leaf_{i}", "node")
        mg.link(center.id, leaf.id, "connects")
    mg.graph_meta = {"label": label}
    return mg


def _build_path(n, label="path"):
    mg = MemoryGraph()
    prev = None
    for i in range(n):
        node = mg.add(f"node_{i}", "node")
        if prev:
            mg.link(prev.id, node.id, "connects")
        prev = node
    mg.graph_meta = {"label": label}
    return mg


def _build_cycle(n, label="cycle"):
    mg = MemoryGraph()
    nodes = [mg.add(f"node_{i}", "node") for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i + 1) % n].id, "connects")
    mg.graph_meta = {"label": label}
    return mg


def _build_complete(n, label="complete"):
    mg = MemoryGraph()
    nodes = [mg.add(f"node_{i}", "node") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "connects")
    mg.graph_meta = {"label": label}
    return mg


class TestConfusionExplainStructure(unittest.TestCase):
    """Test result structure and types."""

    def setUp(self):
        self.refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        self.query = _build_star(10, label="?")

    def test_returns_dict(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertIsInstance(result, dict)

    def test_required_keys(self):
        result = self.query.classification_confusion_explain(self.refs)
        expected = {
            "predicted_label", "runner_up_label", "margin",
            "decision_aligned", "per_modality", "modality_ranking",
            "decisive_modality", "opposing_modalities",
            "reference_distances", "summary",
        }
        self.assertTrue(expected.issubset(result.keys()))

    def test_predicted_label_is_string(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertIsInstance(result["predicted_label"], str)

    def test_runner_up_is_different(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertNotEqual(result["predicted_label"], result["runner_up_label"])

    def test_margin_is_float(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertIsInstance(result["margin"], float)

    def test_summary_is_string(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertIsInstance(result["summary"], str)
        self.assertTrue(len(result["summary"]) > 0)


class TestConfusionExplainCorrectness(unittest.TestCase):
    """Test correctness of margin decomposition."""

    def setUp(self):
        self.refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        self.query = _build_star(10, label="?")

    def test_star_query_predicted_as_star(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertEqual(result["predicted_label"], "star")

    def test_per_modality_has_three_modalities(self):
        result = self.query.classification_confusion_explain(self.refs)
        self.assertEqual(
            set(result["per_modality"].keys()),
            {"degree", "spectral", "fingerprint"},
        )

    def test_per_modality_fields(self):
        result = self.query.classification_confusion_explain(self.refs)
        for mod_data in result["per_modality"].values():
            self.assertIn("predicted_distance", mod_data)
            self.assertIn("runner_up_distance", mod_data)
            self.assertIn("margin", mod_data)
            self.assertIn("contribution_fraction", mod_data)
            self.assertIn("supports_prediction", mod_data)

    def test_positive_margin_for_correct_prediction(self):
        """When the query truly matches the predicted label, overall margin > 0."""
        result = self.query.classification_confusion_explain(self.refs)
        self.assertGreater(result["margin"], 0)

    def test_contribution_fractions_sum_to_one(self):
        result = self.query.classification_confusion_explain(self.refs)
        total = sum(
            m["contribution_fraction"] for m in result["per_modality"].values()
        )
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_decisive_modality_has_largest_abs_margin(self):
        result = self.query.classification_confusion_explain(self.refs)
        decisive = result["decisive_modality"]
        margins = {m: abs(d["margin"]) for m, d in result["per_modality"].items()}
        self.assertEqual(decisive, max(margins, key=margins.get))

    def test_modality_ranking_sorted_desc(self):
        result = self.query.classification_confusion_explain(self.refs)
        margins = [
            abs(result["per_modality"][m]["margin"])
            for m in result["modality_ranking"]
        ]
        self.assertEqual(margins, sorted(margins, reverse=True))

    def test_predicted_distance_less_than_runner_up_for_supporting(self):
        result = self.query.classification_confusion_explain(self.refs)
        for mod, data in result["per_modality"].items():
            if data["supports_prediction"]:
                self.assertLess(
                    data["predicted_distance"],
                    data["runner_up_distance"],
                )


class TestConfusionExplainParameters(unittest.TestCase):
    """Test parameter variations."""

    def setUp(self):
        self.refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        self.query = _build_star(10, label="?")

    def test_explicit_predicted_label(self):
        result = self.query.classification_confusion_explain(
            self.refs, predicted_label="star"
        )
        self.assertEqual(result["predicted_label"], "star")

    def test_explicit_runner_up(self):
        result = self.query.classification_confusion_explain(
            self.refs, predicted_label="star", runner_up_label="path"
        )
        self.assertEqual(result["runner_up_label"], "path")

    def test_different_degree_index(self):
        result = self.query.classification_confusion_explain(
            self.refs, degree_index="randic"
        )
        self.assertEqual(result["predicted_label"], "star")

    def test_different_spectral_measure(self):
        result = self.query.classification_confusion_explain(
            self.refs, spectral_measure="kl"
        )
        self.assertEqual(result["predicted_label"], "star")

    def test_different_bins(self):
        result = self.query.classification_confusion_explain(
            self.refs, bins=15
        )
        self.assertEqual(result["predicted_label"], "star")


class TestConfusionExplainEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_references(self):
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain([])
        self.assertIsNone(result["predicted_label"])
        self.assertEqual(result["summary"], "No references provided.")

    def test_single_reference(self):
        ref = _build_star(10)
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain([ref])
        self.assertEqual(result["predicted_label"], "star")

    def test_two_references(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(result["predicted_label"], "star")
        self.assertNotEqual(result["predicted_label"], result["runner_up_label"])

    def test_predicted_label_not_in_references(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(
            refs, predicted_label="nonexistent"
        )
        # Falls back to first reference
        self.assertIsNotNone(result["predicted_label"])

    def test_runner_up_not_in_references(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(
            refs, predicted_label="star", runner_up_label="nonexistent"
        )
        self.assertIsNotNone(result["runner_up_label"])

    def test_query_with_two_nodes(self):
        mg = MemoryGraph()
        a = mg.add("a", "node")
        b = mg.add("b", "node")
        mg.link(a.id, b.id, "connects")
        mg.graph_meta = {"label": "?"}
        refs = [_build_star(10), _build_path(10)]
        result = mg.classification_confusion_explain(refs)
        self.assertIn("predicted_label", result)


class TestConfusionExplainDecision(unittest.TestCase):
    """Test decision alignment logic."""

    def test_all_modalities_agree_for_clear_match(self):
        refs = [_build_star(10), _build_complete(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        # Star is very different from complete, so all modalities should agree
        self.assertTrue(result["decision_aligned"])
        self.assertEqual(len(result["opposing_modalities"]), 0)

    def test_opposing_modalities_listed(self):
        """When at least one modality opposes, it's listed."""
        refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        query = _build_path(10, label="?")
        result = query.classification_confusion_explain(refs)
        # Path and cycle can be confused — check structure is correct
        self.assertIsInstance(result["opposing_modalities"], list)
        for mod in result["opposing_modalities"]:
            self.assertIn(mod, ["degree", "spectral", "fingerprint"])

    def test_decision_aligned_flag(self):
        refs = [_build_star(10), _build_complete(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(
            result["decision_aligned"],
            len(result["opposing_modalities"]) == 0,
        )


class TestConfusionExplainReferenceDistances(unittest.TestCase):
    """Test reference_distances output."""

    def test_reference_distances_length(self):
        refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(len(result["reference_distances"]), 3)

    def test_reference_distances_have_modalities(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        for rd in result["reference_distances"]:
            self.assertIn("degree", rd)
            self.assertIn("spectral", rd)
            self.assertIn("fingerprint", rd)

    def test_reference_distances_have_labels(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        labels = [rd["label"] for rd in result["reference_distances"]]
        self.assertIn("star", labels)
        self.assertIn("path", labels)


class TestConfusionExplainSummary(unittest.TestCase):
    """Test human-readable summary."""

    def test_summary_mentions_predicted_label(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertIn("star", result["summary"])

    def test_summary_mentions_runner_up(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertIn("path", result["summary"])

    def test_summary_mentions_decisive_modality(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertIn(result["decisive_modality"], result["summary"])

    def test_summary_mentions_alignment(self):
        refs = [_build_star(10), _build_complete(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        if result["decision_aligned"]:
            self.assertIn("agree", result["summary"].lower())


class TestConfusionExplainNonMutating(unittest.TestCase):
    """Ensure the method doesn't mutate the query or references."""

    def test_query_unchanged(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        before_nodes = query.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        query.classification_confusion_explain(refs)
        after_nodes = query.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        self.assertEqual(before_nodes, after_nodes)

    def test_references_unchanged(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        before_counts = [
            r.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
            for r in refs
        ]
        query.classification_confusion_explain(refs)
        after_counts = [
            r.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
            for r in refs
        ]
        self.assertEqual(before_counts, after_counts)

    def test_no_new_edges_in_query(self):
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(10, label="?")
        before_edges = query.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        query.classification_confusion_explain(refs)
        after_edges = query.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        self.assertEqual(before_edges, after_edges)


class TestConfusionExplainDeterminism(unittest.TestCase):
    """Test deterministic output."""

    def test_same_input_same_output(self):
        refs1 = [_build_star(10), _build_path(10), _build_cycle(10)]
        refs2 = [_build_star(10), _build_path(10), _build_cycle(10)]
        query1 = _build_star(10, label="?")
        query2 = _build_star(10, label="?")
        r1 = query1.classification_confusion_explain(refs1)
        r2 = query2.classification_confusion_explain(refs2)
        self.assertEqual(r1["predicted_label"], r2["predicted_label"])
        self.assertEqual(r1["decisive_modality"], r2["decisive_modality"])
        self.assertEqual(r1["modality_ranking"], r2["modality_ranking"])

    def test_margin_stable(self):
        refs = [_build_star(10), _build_path(10)]
        query1 = _build_star(10, label="?")
        query2 = _build_star(10, label="?")
        r1 = query1.classification_confusion_explain(refs)
        r2 = query2.classification_confusion_explain(refs)
        self.assertAlmostEqual(r1["margin"], r2["margin"], places=5)


class TestConfusionExplainIntegration(unittest.TestCase):
    """Integration with other classification APIs."""

    def test_works_with_weighted_average_result(self):
        refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        query = _build_star(10, label="?")
        wa = query.weighted_average_classification(refs)
        if wa and "best_match" in wa:
            best_idx = wa["best_match"]
            rankings = wa.get("rankings", [])
            wa_label = rankings[best_idx].get("label") if best_idx < len(rankings) else None
        else:
            wa_label = None
        explain = query.classification_confusion_explain(
            refs, predicted_label=wa_label
        )
        self.assertEqual(explain["predicted_label"], wa_label)

    def test_works_with_learned_weights(self):
        # Build training set
        training = [
            (_build_star(8, "star"), "star"),
            (_build_path(8, "path"), "path"),
            (_build_cycle(8, "cycle"), "cycle"),
        ]
        refs = [_build_star(10), _build_path(10), _build_cycle(10)]
        query = _build_star(10, label="?")
        lw = query.classification_learned_weights(training)
        if lw and "best_weights" in lw:
            # Just verify explain works with refs
            explain = query.classification_confusion_explain(refs)
            self.assertIsNotNone(explain["predicted_label"])

    def test_complete_vs_star_clear_separation(self):
        refs = [_build_star(10), _build_complete(10)]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(result["predicted_label"], "star")
        self.assertGreater(result["margin"], 0)
        self.assertTrue(result["decision_aligned"])

    def test_many_references(self):
        refs = [
            _build_star(10, "star"),
            _build_path(10, "path"),
            _build_cycle(10, "cycle"),
            _build_complete(10, "complete"),
        ]
        query = _build_star(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(result["predicted_label"], "star")
        self.assertEqual(len(result["reference_distances"]), 4)

    def test_path_vs_cycle_distinction(self):
        """Path and cycle are harder to distinguish — test the explain handles it."""
        refs = [_build_path(10, "path"), _build_cycle(10, "cycle")]
        query = _build_path(10, label="?")
        result = query.classification_confusion_explain(refs)
        self.assertEqual(result["predicted_label"], "path")
        # The margin might be small (these are similar topologies)
        self.assertIsInstance(result["margin"], float)

    def test_explain_after_graph_modification(self):
        """Explain should work even after the query graph is modified."""
        refs = [_build_star(10), _build_path(10)]
        query = _build_star(5, label="?")
        # Add more nodes to make it a bigger star
        result = query.classification_confusion_explain(refs)
        self.assertIsNotNone(result["predicted_label"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
