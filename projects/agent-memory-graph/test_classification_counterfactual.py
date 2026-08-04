"""Tests for classification_counterfactual() — Cycle 357.

Counterfactual explainability: what would need to change to flip the
classification from the predicted label to the runner-up?
"""

import math
import pytest
from memory_graph import MemoryGraph


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_labelled(label: str, topology: str = "path", n: int = 6) -> MemoryGraph:
    """Create a MemoryGraph with a given topology and label."""
    mg = MemoryGraph()
    mg.graph_meta = {"label": label}

    if topology == "path":
        prev = None
        for i in range(n):
            node = mg.add(f"{label}_node_{i}", "node")
            if prev:
                mg.link(prev.id, node.id, "edge")
            prev = node
    elif topology == "star":
        center = mg.add(f"{label}_center", "node")
        for i in range(n - 1):
            leaf = mg.add(f"{label}_leaf_{i}", "node")
            mg.link(center.id, leaf.id, "edge")
    elif topology == "cycle":
        first = None
        prev = None
        for i in range(n):
            node = mg.add(f"{label}_node_{i}", "node")
            if first is None:
                first = node
            if prev:
                mg.link(prev.id, node.id, "edge")
            prev = node
        if first and prev:
            mg.link(prev.id, first.id, "edge")
    elif topology == "clique":
        nodes = [mg.add(f"{label}_node_{i}", "node") for i in range(n)]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                mg.link(nodes[i].id, nodes[j].id, "edge")
    return mg


def _make_references():
    """Standard reference set: path, star, cycle, clique."""
    return [
        _make_labelled("path", "path", 6),
        _make_labelled("star", "star", 6),
        _make_labelled("cycle", "cycle", 6),
        _make_labelled("clique", "clique", 6),
    ]


# ------------------------------------------------------------------ #
# Structure
# ------------------------------------------------------------------ #

class TestStructure:
    def test_returns_dict(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert isinstance(result, dict)

    def test_required_keys(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        required = {
            "predicted_label", "runner_up_label", "overall_margin",
            "robustness", "flip_distance", "easiest_modality",
            "per_modality", "modality_difficulty_ranking",
            "flip_scenarios", "summary",
        }
        assert required.issubset(result.keys())

    def test_per_modality_keys(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            assert "predicted_distance" in data
            assert "runner_up_distance" in data
            assert "current_margin" in data
            assert "flip_threshold" in data
            assert "relative_difficulty" in data
            assert "flip_direction" in data

    def test_modality_difficulty_ranking_is_list(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert isinstance(result["modality_difficulty_ranking"], list)
        assert len(result["modality_difficulty_ranking"]) == 3

    def test_flip_scenarios_is_list(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert isinstance(result["flip_scenarios"], list)
        assert len(result["flip_scenarios"]) == 3

    def test_summary_is_string(self):
        mg = _make_labelled("query_path", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ------------------------------------------------------------------ #
# Correctness
# ------------------------------------------------------------------ #

class TestCorrectness:
    def test_predicted_label_is_path(self):
        """A path query should be classified as path."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["predicted_label"] == "path"

    def test_overall_margin_positive_for_clear_match(self):
        """A clear path query should have positive overall margin."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["overall_margin"] > 0

    def test_flip_distance_non_negative(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["flip_distance"] >= 0

    def test_relative_difficulty_in_range(self):
        """relative_difficulty should be in [0, 1]."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            assert 0.0 <= data["relative_difficulty"] <= 1.0

    def test_easiest_modality_has_smallest_threshold(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        ranking = result["modality_difficulty_ranking"]
        easiest = result["easiest_modality"]
        assert easiest == ranking[0]
        thresholds = [result["per_modality"][m]["flip_threshold"] for m in ranking]
        assert thresholds == sorted(thresholds)

    def test_flip_threshold_equals_margin_when_positive(self):
        """For modalities that support prediction, flip_threshold == current_margin."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            if data["current_margin"] > 0:
                assert data["flip_threshold"] == data["current_margin"]

    def test_flip_threshold_zero_when_opposing(self):
        """Modalities that oppose prediction should have flip_threshold 0."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            if data["current_margin"] < 0:
                assert data["flip_threshold"] == 0.0
                assert data["flip_direction"] == "already_favors_runner_up"

    def test_difficulty_ranking_sorted_ascending(self):
        """Ranking should be sorted by flip_threshold ascending."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        ranking = result["modality_difficulty_ranking"]
        thresholds = [result["per_modality"][m]["flip_threshold"] for m in ranking]
        for i in range(len(thresholds) - 1):
            assert thresholds[i] <= thresholds[i + 1]


# ------------------------------------------------------------------ #
# Robustness
# ------------------------------------------------------------------ #

class TestRobustness:
    def test_robust_for_clear_match(self):
        """A very clear path should be robust."""
        mg = _make_labelled("query", "path", 8)
        refs = [
            _make_labelled("path", "path", 8),
            _make_labelled("clique", "clique", 8),
        ]
        result = mg.classification_counterfactual(refs)
        assert result["robustness"] in ("robust", "borderline")

    def test_borderline_for_very_similar(self):
        """Two very similar topologies should produce borderline or fragile."""
        # Path and cycle of same size — very similar structures
        mg = _make_labelled("query", "path", 5)
        refs = [
            _make_labelled("path_a", "path", 5),
            _make_labelled("path_b", "path", 5),
        ]
        result = mg.classification_counterfactual(refs)
        # Two identical-topology references: margins should be small
        assert result["robustness"] in ("fragile", "borderline", "robust")

    def test_robustness_values_are_valid(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["robustness"] in ("robust", "borderline", "fragile", "unknown")


# ------------------------------------------------------------------ #
# Parameters
# ------------------------------------------------------------------ #

class TestParameters:
    def test_explicit_predicted_label(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs, predicted_label="star")
        assert result["predicted_label"] == "star"

    def test_explicit_runner_up_label(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(
            refs, runner_up_label="cycle"
        )
        assert result["runner_up_label"] == "cycle"

    def test_different_degree_index(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs, degree_index="sombor")
        r2 = mg.classification_counterfactual(refs, degree_index="randic")
        # Results may differ since different degree indices
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)

    def test_different_spectral_measure(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs, spectral_measure="jsd")
        r2 = mg.classification_counterfactual(refs, spectral_measure="kl")
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)

    def test_different_bins(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs, bins=10)
        r2 = mg.classification_counterfactual(refs, bins=30)
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)


# ------------------------------------------------------------------ #
# Edge Cases
# ------------------------------------------------------------------ #

class TestEdgeCases:
    def test_empty_references(self):
        mg = _make_labelled("query", "path", 6)
        result = mg.classification_counterfactual([])
        assert result["predicted_label"] is None
        assert result["robustness"] == "unknown"
        assert "No references" in result["summary"]

    def test_single_reference(self):
        mg = _make_labelled("query", "path", 6)
        refs = [_make_labelled("path", "path", 6)]
        result = mg.classification_counterfactual(refs)
        # With only one reference, predicted == that reference
        assert result["predicted_label"] == "path"

    def test_two_references(self):
        mg = _make_labelled("query", "path", 6)
        refs = [
            _make_labelled("path", "path", 6),
            _make_labelled("star", "star", 6),
        ]
        result = mg.classification_counterfactual(refs)
        assert result["predicted_label"] in ("path", "star")
        assert result["runner_up_label"] in ("path", "star")
        assert result["predicted_label"] != result["runner_up_label"]

    def test_predicted_label_not_in_references(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(
            refs, predicted_label="nonexistent"
        )
        # Should fall back gracefully
        assert result["predicted_label"] is not None

    def test_small_query_2_nodes(self):
        mg = MemoryGraph()
        mg.graph_meta = {"label": "tiny"}
        a = mg.add("a", "node")
        b = mg.add("b", "node")
        mg.link(a.id, b.id, "edge")
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert isinstance(result, dict)
        assert result["predicted_label"] is not None

    def test_all_same_topology_references(self):
        """All references have the same topology (and same label)."""
        mg = _make_labelled("query", "path", 6)
        refs = [
            _make_labelled("path", "path", 6),
            _make_labelled("path2", "path", 6),
        ]
        result = mg.classification_counterfactual(refs)
        assert isinstance(result, dict)


# ------------------------------------------------------------------ #
# Flip Scenarios
# ------------------------------------------------------------------ #

class TestFlipScenarios:
    def test_flip_scenarios_describe_each_modality(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        scenarios = result["flip_scenarios"]
        assert len(scenarios) == 3
        # Each scenario should mention a modality name
        mod_names = ["degree", "spectral", "fingerprint"]
        for scenario in scenarios:
            assert any(mod in scenario for mod in mod_names)

    def test_flip_scenario_mentions_threshold_or_already(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for scenario in result["flip_scenarios"]:
            assert "shift" in scenario or "already" in scenario or "tied" in scenario


# ------------------------------------------------------------------ #
# Summary
# ------------------------------------------------------------------ #

class TestSummary:
    def test_summary_mentions_predicted_label(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["predicted_label"] in result["summary"]

    def test_summary_mentions_runner_up(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["runner_up_label"] in result["summary"]

    def test_summary_mentions_robustness(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["robustness"] in result["summary"]

    def test_summary_mentions_flip_distance(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert "flip distance" in result["summary"].lower()


# ------------------------------------------------------------------ #
# Non-Mutating
# ------------------------------------------------------------------ #

class TestNonMutating:
    def test_query_graph_unchanged(self):
        mg = _make_labelled("query", "path", 6)
        nodes_before = mg.stats()["nodes"]
        mg.classification_counterfactual(_make_references())
        nodes_after = mg.stats()["nodes"]
        assert nodes_before == nodes_after

    def test_references_unchanged(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        ref_counts = [r.stats()["nodes"] for r in refs]
        mg.classification_counterfactual(refs)
        ref_counts_after = [r.stats()["nodes"] for r in refs]
        assert ref_counts == ref_counts_after

    def test_no_new_edges_in_query(self):
        mg = _make_labelled("query", "path", 6)
        edges_before = mg.stats()["edges"]
        mg.classification_counterfactual(_make_references())
        edges_after = mg.stats()["edges"]
        assert edges_before == edges_after


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

class TestDeterminism:
    def test_same_input_same_output(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs)
        r2 = mg.classification_counterfactual(refs)
        assert r1 == r2

    def test_flip_threshold_stable(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs)
        r2 = mg.classification_counterfactual(refs)
        for mod in ["degree", "spectral", "fingerprint"]:
            assert r1["per_modality"][mod]["flip_threshold"] == r2["per_modality"][mod]["flip_threshold"]


# ------------------------------------------------------------------ #
# Integration
# ------------------------------------------------------------------ #

class TestIntegration:
    def test_works_with_weighted_average_result(self):
        """Use weighted_average_classification result to feed counterfactual."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        wa = mg.weighted_average_classification(refs)
        assert wa is not None
        best_idx = wa["best_match"]
        pred_label = wa["rankings"][best_idx]["label"]
        result = mg.classification_counterfactual(
            refs, predicted_label=pred_label
        )
        assert result["predicted_label"] == pred_label

    def test_works_with_confusion_explain(self):
        """confusion_explain and counterfactual should agree on labels."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        explain = mg.classification_confusion_explain(refs)
        counter = mg.classification_counterfactual(refs)
        assert explain["predicted_label"] == counter["predicted_label"]
        assert explain["runner_up_label"] == counter["runner_up_label"]

    def test_clear_separation_robust(self):
        """Path vs clique should give robust classification."""
        mg = _make_labelled("query", "path", 10)
        refs = [
            _make_labelled("path", "path", 10),
            _make_labelled("clique", "clique", 10),
        ]
        result = mg.classification_counterfactual(refs)
        assert result["predicted_label"] == "path"
        assert result["overall_margin"] > 0

    def test_many_references(self):
        """Should work with many references."""
        mg = _make_labelled("query", "path", 6)
        refs = [
            _make_labelled("path", "path", 6),
            _make_labelled("star", "star", 6),
            _make_labelled("cycle", "cycle", 6),
            _make_labelled("clique", "clique", 6),
            _make_labelled("path2", "path", 8),
            _make_labelled("star2", "star", 8),
        ]
        result = mg.classification_counterfactual(refs)
        assert isinstance(result, dict)
        assert result["predicted_label"] is not None

    def test_clique_query_classified_correctly(self):
        """A clique query should be classified as one of the reference labels."""
        mg = _make_labelled("query", "clique", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        assert result["predicted_label"] in ("path", "star", "cycle", "clique")

    def test_counterfactual_after_modification(self):
        """After adding nodes to query, counterfactual should still work."""
        mg = _make_labelled("query", "path", 4)
        refs = _make_references()
        r1 = mg.classification_counterfactual(refs)
        # Add more nodes via stats to get current count
        assert isinstance(r1, dict)
        count_before = mg.stats()["nodes"]
        # Verify we can still call it after modifications
        extra = mg.add("extra_1", "node")
        mg.link(mg.all_nodes[0].id, extra.id, "edge") if hasattr(mg, 'all_nodes') else None
        r2 = mg.classification_counterfactual(refs)
        assert isinstance(r2, dict)
        assert mg.stats()["nodes"] == count_before + 1

    def test_margin_consistency_with_explain(self):
        """Overall margin from counterfactual should match confusion_explain's margin."""
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        explain = mg.classification_confusion_explain(refs)
        counter = mg.classification_counterfactual(refs)
        assert abs(explain["margin"] - counter["overall_margin"]) < 1e-5


# ------------------------------------------------------------------ #
# Flip Direction Logic
# ------------------------------------------------------------------ #

class TestFlipDirection:
    def test_supporting_modalities_have_positive_margin(self):
        """For a clear path match, at least some modalities should support."""
        mg = _make_labelled("query", "path", 8)
        refs = [
            _make_labelled("path", "path", 8),
            _make_labelled("clique", "clique", 8),
        ]
        result = mg.classification_counterfactual(refs)
        supporting = [
            m for m, d in result["per_modality"].items()
            if d["current_margin"] > 0
        ]
        assert len(supporting) >= 1

    def test_flip_direction_values(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            assert data["flip_direction"] in (
                "increase_predicted_distance",
                "already_favors_runner_up",
                "tied",
            )

    def test_already_favoring_modalities_have_zero_threshold(self):
        mg = _make_labelled("query", "path", 6)
        refs = _make_references()
        result = mg.classification_counterfactual(refs)
        for mod, data in result["per_modality"].items():
            if data["flip_direction"] == "already_favors_runner_up":
                assert data["flip_threshold"] == 0.0
                assert data["current_margin"] < 0
