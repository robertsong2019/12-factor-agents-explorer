"""Tests for seven_intent_taxonomy — temporal_reasoning + constraint_validation.

Cycle 261 — MemFlow 7-intent expansion (arXiv:2605.03312).
Extends query() from 5 modes to 7: basic/global/local/drift/hybrid
+ temporal + constraint.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated():
    g = MemoryGraph(":memory:")
    alice = g.add("Alice", "person", {"role": "engineer"})
    bob = g.add("Bob", "person", {"role": "manager"})
    project = g.add("Project Alpha", "project")
    rule = g.add("Must deploy before Friday", "rule")
    policy = g.add("Code review required", "policy")
    g.link(alice.id, bob.id, "reports_to")
    g.link(alice.id, project.id, "works_on")
    g.link(bob.id, project.id, "manages")
    return g


class TestTemporalRouting:

    def test_when_routes_temporal(self, populated):
        result = populated.query("when was Alice created?")
        assert result["mode"] == "temporal"

    def test_before_routes_temporal(self, populated):
        result = populated.query("what happened before Alice?")
        assert result["mode"] == "temporal"

    def test_after_routes_temporal(self, populated):
        result = populated.query("what changed after the project started?")
        assert result["mode"] == "temporal"

    def test_timeline_routes_temporal(self, populated):
        result = populated.query("show me the timeline of events")
        assert result["mode"] == "temporal"

    def test_history_routes_temporal(self, populated):
        result = populated.query("history of Alice")
        assert result["mode"] == "temporal"

    def test_previously_routes_temporal(self, populated):
        result = populated.query("what was previously the case?")
        assert result["mode"] == "temporal"

    def test_temporal_results_returned(self, populated):
        result = populated.query("when was Alice created?")
        assert len(result["results"]) > 0
        assert "score" in result["results"][0]
        assert "created" in result["results"][0]


class TestConstraintRouting:

    def test_must_routes_constraint(self, populated):
        result = populated.query("what must be done?")
        assert result["mode"] == "constraint"

    def test_required_routes_constraint(self, populated):
        result = populated.query("what is required for deployment?")
        assert result["mode"] == "constraint"

    def test_allowed_routes_constraint(self, populated):
        result = populated.query("is this allowed?")
        assert result["mode"] == "constraint"

    def test_valid_routes_constraint(self, populated):
        result = populated.query("is this valid?")
        assert result["mode"] == "constraint"

    def test_policy_routes_constraint(self, populated):
        result = populated.query("what is the policy on reviews?")
        assert result["mode"] == "constraint"

    def test_rule_routes_constraint(self, populated):
        result = populated.query("what rule applies here?")
        assert result["mode"] == "constraint"

    def test_constraint_results_returned(self, populated):
        result = populated.query("what rule applies here?")


class TestExplicitModes:

    def test_explicit_temporal_mode(self, populated):
        result = populated.query("anything", mode="temporal")
        assert result["mode"] == "temporal"
        assert len(result["results"]) > 0

    def test_explicit_constraint_mode(self, populated):
        result = populated.query("anything", mode="constraint")
        assert result["mode"] == "constraint"

    def test_unknown_mode_raises(self, populated):
        with pytest.raises(ValueError, match="Unknown mode"):
            populated.query("test", mode="nonexistent")


class TestTemporalSearchInternal:

    def test_temporal_search_returns_list(self, populated):
        results = populated._temporal_search("test", limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_temporal_results_have_temporal_fields(self, populated):
        results = populated._temporal_search("test", limit=5)
        for r in results:
            assert "created" in r
            assert "accessed" in r
            assert "superseded" in r

    def test_temporal_scores_nonneg(self, populated):
        results = populated._temporal_search("test", limit=5)
        for r in results:
            assert r["score"] >= 0.0

    def test_temporal_sorted_desc(self, populated):
        results = populated._temporal_search("test", limit=10)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestConstraintSearchInternal:

    def test_constraint_search_finds_rules(self, populated):
        results = populated._constraint_search("deploy", limit=10)
        labels = [r["label"] for r in results]
        assert any("deploy" in l.lower() or "Friday" in l for l in labels)

    def test_constraint_search_finds_policy(self, populated):
        results = populated._constraint_search("review", limit=10)
        labels = [r["label"] for r in results]
        assert any("review" in l.lower() or "policy" in l.lower() for l in labels)

    def test_constraint_search_returns_list(self, populated):
        results = populated._constraint_search("test", limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_constraint_results_have_match_type(self, populated):
        results = populated._constraint_search("deploy", limit=10)
        for r in results:
            assert "match_type" in r

    def test_constraint_search_empty_graph(self, mg):
        results = mg._constraint_search("nothing", limit=5)
        assert isinstance(results, list)


class TestExistingModesUnchanged:

    def test_basic_still_works(self, populated):
        result = populated.query("Alice")
        assert result["mode"] == "basic"

    def test_global_still_works(self, populated):
        result = populated.query("overview of all themes")
        assert result["mode"] == "global"

    def test_drift_still_works(self, populated):
        result = populated.query("how does Alice connect to Bob and what is the project?")
        assert result["mode"] == "drift"

    def test_hybrid_still_works(self, populated):
        # Need >10 nodes for hybrid
        g = MemoryGraph(":memory:")
        for i in range(15):
            g.add(f"node-{i}", "item")
        result = g.query("general search for items")
        assert result["mode"] == "hybrid"


class TestStatsIncludeNewModes:

    def test_query_returns_stats(self, populated):
        result = populated.query("when was Alice created?")
        assert "stats" in result
        assert "node_count" in result["stats"]

    def test_temporal_elapsed_tracked(self, populated):
        result = populated.query("when was Alice created?")
        assert "elapsed_ms" in result["stats"]
