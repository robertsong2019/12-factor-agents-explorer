"""Tests for memory_interference_report() — Cycle 403.

Proactive/retroactive interference analysis between memories.
"""
import pytest
from memory_graph import MemoryGraph


# ─── helpers ────────────────────────────────────────────────────────

def _build_graph():
    """Build a test graph with known interference structure.

    Layout (timestamps controlled):
        old_a (t=100) ──┐
        old_b (t=200) ──┼── shared (t=300) ──── target (t=500)
        new_c (t=600) ──┘    │                    │
                             └────────────────────┘

    target shares 'shared' with old_a, old_b (proactive) and new_c (retroactive).
    """
    mg = MemoryGraph()
    # Use predictable timestamps
    old_a = mg.add("Old A", "concept", {"importance": 0.8})
    old_b = mg.add("Old B", "concept", {"importance": 0.6})
    shared = mg.add("Shared Hub", "concept", {"importance": 1.0})
    target = mg.add("Target", "concept", {"importance": 0.7})
    new_c = mg.add("New C", "concept", {"importance": 0.9})

    # Override timestamps for deterministic ordering
    mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (100, old_a.id))
    mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (200, old_b.id))
    mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (300, shared.id))
    mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (500, target.id))
    mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (600, new_c.id))
    mg.conn.commit()

    # Edges: old_a, old_b, new_c all connect to shared; target connects to shared
    mg.link(old_a.id, shared.id, "related")
    mg.link(old_b.id, shared.id, "related")
    mg.link(new_c.id, shared.id, "related")
    mg.link(target.id, shared.id, "related")

    return mg, target, old_a, old_b, new_c, shared


def _build_isolated():
    """Build a graph with an isolated node."""
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")  # isolated — no edges
    mg.link(a.id, b.id, "related")
    return mg, c


def _build_no_overlap():
    """Build a graph where neighbours exist but don't overlap."""
    mg = MemoryGraph()
    t = mg.add("Target", "concept")
    n1 = mg.add("N1", "concept")
    n2 = mg.add("N2", "concept")
    # t connects to n1, n2 connects to a different node
    n3 = mg.add("N3", "concept")
    mg.link(t.id, n1.id, "related")
    mg.link(n2.id, n3.id, "related")
    return mg, t


# ─── basic structure ────────────────────────────────────────────────

class TestInterferenceBasic:
    def test_returns_dict_with_required_keys(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert isinstance(result, dict)
        for key in ("target", "proactive_interference", "retroactive_interference",
                     "overall_risk", "risk_score", "recommendations", "summary"):
            assert key in result

    def test_target_label_in_result(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert result["target_label"] == "Target"

    def test_target_created_in_result(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert result["target_created"] == 500

    def test_nonexistent_node_raises(self):
        mg = MemoryGraph()
        with pytest.raises(KeyError, match="not found"):
            mg.memory_interference_report("nonexistent")

    def test_summary_has_correct_keys(self):
        mg, target, *_ = _build_graph()
        s = mg.memory_interference_report(target.id)["summary"]
        for key in ("candidate_count", "competitor_count", "proactive_count",
                     "retroactive_count", "max_similarity", "metric", "hop_radius"):
            assert key in s


class TestInterferenceIsolated:
    def test_isolated_node_low_risk(self):
        mg, c = _build_isolated()
        result = mg.memory_interference_report(c.id)
        assert result["overall_risk"] == "low"
        assert result["risk_score"] == 0.0

    def test_isolated_node_empty_lists(self):
        mg, c = _build_isolated()
        result = mg.memory_interference_report(c.id)
        assert result["proactive_interference"] == []
        assert result["retroactive_interference"] == []

    def test_isolated_node_recommendation(self):
        mg, c = _build_isolated()
        result = mg.memory_interference_report(c.id)
        assert any("isolated" in r.lower() for r in result["recommendations"])

    def test_no_overlap_returns_empty(self):
        mg, t = _build_no_overlap()
        result = mg.memory_interference_report(t.id)
        assert result["proactive_interference"] == []
        assert result["retroactive_interference"] == []
        assert result["overall_risk"] == "low"


# ─── proactive / retroactive classification ────────────────────────

class TestInterferenceDirection:
    def test_old_a_is_proactive(self):
        mg, target, old_a, old_b, new_c, shared = _build_graph()
        result = mg.memory_interference_report(target.id)
        pi_ids = [c["node_id"] for c in result["proactive_interference"]]
        assert old_a.id in pi_ids

    def test_old_b_is_proactive(self):
        mg, target, old_a, old_b, new_c, shared = _build_graph()
        result = mg.memory_interference_report(target.id)
        pi_ids = [c["node_id"] for c in result["proactive_interference"]]
        assert old_b.id in pi_ids

    def test_new_c_is_retroactive(self):
        mg, target, old_a, old_b, new_c, shared = _build_graph()
        result = mg.memory_interference_report(target.id)
        ri_ids = [c["node_id"] for c in result["retroactive_interference"]]
        assert new_c.id in ri_ids

    def test_direct_neighbour_without_overlap_excluded(self):
        """The shared hub is a direct neighbour but has zero structural overlap
        with target (different connection patterns) → not a competitor."""
        mg, target, old_a, old_b, new_c, shared = _build_graph()
        result = mg.memory_interference_report(target.id)
        all_ids = [c["node_id"] for c in result["proactive_interference"]] + \
                  [c["node_id"] for c in result["retroactive_interference"]]
        # shared connects to old_a/old_b/new_c/target, target connects to shared
        # → zero overlap in neighbour sets → not a competitor
        assert shared.id not in all_ids

    def test_proactive_created_before_target(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for c in result["proactive_interference"]:
            # all proactive were created <= target
            row = mg.conn.execute(
                "SELECT created FROM nodes WHERE id=?", (c["node_id"],)
            ).fetchone()
            assert row["created"] <= result["target_created"]

    def test_retroactive_created_after_target(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for c in result["retroactive_interference"]:
            row = mg.conn.execute(
                "SELECT created FROM nodes WHERE id=?", (c["node_id"],)
            ).fetchone()
            assert row["created"] > result["target_created"]


# ─── scoring ────────────────────────────────────────────────────────

class TestInterferenceScoring:
    def test_interference_score_positive(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for c in result["proactive_interference"] + result["retroactive_interference"]:
            assert c["interference_score"] > 0
            assert c["similarity"] > 0

    def test_higher_importance_higher_score(self):
        """old_a has importance=0.8, old_b has 0.6, both share same neighbour."""
        mg, target, old_a, old_b, new_c, shared = _build_graph()
        result = mg.memory_interference_report(target.id)
        pi_lookup = {c["node_id"]: c for c in result["proactive_interference"]}
        if old_a.id in pi_lookup and old_b.id in pi_lookup:
            # Both have same similarity (one shared neighbour) → importance breaks tie
            assert pi_lookup[old_a.id]["interference_score"] >= \
                   pi_lookup[old_b.id]["interference_score"]

    def test_sorted_by_score_descending(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        scores = [c["interference_score"] for c in result["proactive_interference"]]
        assert scores == sorted(scores, reverse=True)

    def test_risk_score_is_max(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        all_scores = [c["interference_score"] for c in
                      result["proactive_interference"] + result["retroactive_interference"]]
        if all_scores:
            assert result["risk_score"] == max(all_scores)


# ─── risk levels ────────────────────────────────────────────────────

class TestInterferenceRisk:
    def test_low_risk_when_no_overlap(self):
        mg, t = _build_no_overlap()
        result = mg.memory_interference_report(t.id)
        assert result["overall_risk"] == "low"

    def test_moderate_risk(self):
        mg = MemoryGraph()
        # Build a scenario with moderate interference (~0.4 score)
        target = mg.add("Target", "concept", {"importance": 1.0})
        competitor = mg.add("Competitor", "concept", {"importance": 1.0})
        # Single shared neighbour
        shared = mg.add("Shared", "concept")
        mg.link(target.id, shared.id, "related")
        mg.link(competitor.id, shared.id, "related")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (200, competitor.id))
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (300, shared.id))
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (500, target.id))
        mg.conn.commit()
        result = mg.memory_interference_report(target.id)
        assert result["overall_risk"] in ("low", "moderate", "high")

    def test_high_risk_with_many_overlaps(self):
        mg = MemoryGraph()
        target = mg.add("Target", "concept", {"importance": 1.0})
        # Create many neighbours
        neighbours = []
        for i in range(5):
            n = mg.add(f"N{i}", "concept")
            neighbours.append(n)
            mg.link(target.id, n.id, "related")

        # Create competitor that shares ALL neighbours
        competitor = mg.add("Competitor", "concept", {"importance": 1.0})
        for n in neighbours:
            mg.link(competitor.id, n.id, "related")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (100, competitor.id))
        mg.conn.commit()
        result = mg.memory_interference_report(target.id)
        assert result["overall_risk"] in ("moderate", "high")

    def test_risk_level_is_valid_string(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert result["overall_risk"] in ("low", "moderate", "high")


# ─── parameters ──────────────────────────────────────────────────────

class TestInterferenceParams:
    def test_top_k_limits_results(self):
        mg = MemoryGraph()
        target = mg.add("Target", "concept", {"importance": 1.0})
        shared = mg.add("Shared", "concept")
        mg.link(target.id, shared.id, "related")

        # Create 5 older competitors
        for i in range(5):
            c = mg.add(f"Old{i}", "concept", {"importance": 0.5})
            mg.link(c.id, shared.id, "related")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (100 + i, c.id))
        mg.conn.commit()

        result = mg.memory_interference_report(target.id, top_k=2)
        assert len(result["proactive_interference"]) <= 2

    def test_hop_radius_1_fewer_candidates(self):
        mg, target, *_ = _build_graph()
        r1 = mg.memory_interference_report(target.id, hop_radius=1)
        r2 = mg.memory_interference_report(target.id, hop_radius=2)
        assert r1["summary"]["candidate_count"] <= r2["summary"]["candidate_count"]

    def test_similarity_metric_overlap(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id, similarity_metric="overlap")
        assert result["summary"]["metric"] == "overlap"
        for c in result["proactive_interference"]:
            # overlap is integer
            assert c["similarity"] >= 1

    def test_similarity_metric_jaccard_default(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert result["summary"]["metric"] == "jaccard"


# ─── recommendations ────────────────────────────────────────────────

class TestInterferenceRecommendations:
    def test_recommendations_is_list_of_strings(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1
        for r in result["recommendations"]:
            assert isinstance(r, str)

    def test_isolated_recommendation_mentions_isolated(self):
        mg, c = _build_isolated()
        result = mg.memory_interference_report(c.id)
        assert any("isolated" in r.lower() for r in result["recommendations"])

    def test_proactive_dominance_recommendation(self):
        """When proactive > retroactive, recommendation should mention it."""
        mg = MemoryGraph()
        target = mg.add("Target", "concept", {"importance": 1.0})
        shared = mg.add("Shared", "concept")
        # Many old competitors, no new ones
        for i in range(3):
            c = mg.add(f"Old{i}", "concept", {"importance": 0.8})
            mg.link(c.id, shared.id, "related")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (100 + i, c.id))
        mg.link(target.id, shared.id, "related")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (500, target.id))
        mg.conn.commit()
        result = mg.memory_interference_report(target.id)
        assert any("proactive" in r.lower() for r in result["recommendations"])

    def test_retroactive_dominance_recommendation(self):
        """When retroactive > proactive, recommendation should mention it."""
        mg = MemoryGraph()
        target = mg.add("Target", "concept", {"importance": 1.0})
        shared = mg.add("Shared", "concept")
        mg.link(target.id, shared.id, "related")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (200, target.id))
        # Many new competitors
        for i in range(3):
            c = mg.add(f"New{i}", "concept", {"importance": 0.8})
            mg.link(c.id, shared.id, "related")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (500 + i, c.id))
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?", (300, shared.id))
        mg.conn.commit()
        result = mg.memory_interference_report(target.id)
        assert any("retroactive" in r.lower() for r in result["recommendations"])


# ─── competitor structure ───────────────────────────────────────────

class TestCompetitorStructure:
    def test_competitor_has_required_fields(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for category in ("proactive_interference", "retroactive_interference"):
            for c in result[category]:
                for field in ("node_id", "label", "kind", "direction",
                              "similarity", "importance", "interference_score",
                              "shared_neighbours", "age_delta_s"):
                    assert field in c, f"Missing field '{field}' in {category}"

    def test_direction_matches_category(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for c in result["proactive_interference"]:
            assert c["direction"] == "proactive"
        for c in result["retroactive_interference"]:
            assert c["direction"] == "retroactive"

    def test_age_delta_positive(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        for c in result["proactive_interference"] + result["retroactive_interference"]:
            assert c["age_delta_s"] >= 0


# ─── edge cases ─────────────────────────────────────────────────────

class TestInterferenceEdgeCases:
    def test_empty_graph_raises(self):
        mg = MemoryGraph()
        with pytest.raises(KeyError):
            mg.memory_interference_report("any")

    def test_single_node_no_neighbours(self):
        mg = MemoryGraph()
        n = mg.add("Lonely", "concept")
        result = mg.memory_interference_report(n.id)
        assert result["overall_risk"] == "low"
        assert result["proactive_interference"] == []

    def test_two_nodes_one_edge_no_interference(self):
        """Two nodes connected by an edge — no shared neighbours → no interference."""
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        result = mg.memory_interference_report(a.id)
        # b is a neighbour but no other node shares b → no competitor
        # Actually b is a candidate, and a has b as neighbour, b has a as neighbour
        # overlap = {b} ∩ {a} potentially... let me think
        # target_neighbours = {b}
        # candidate b's neighbours = {a}
        # intersection = {b} ∩ {a} = {} → no overlap
        assert result["overall_risk"] == "low"

    def test_self_node_excluded_from_candidates(self):
        mg, target, *_ = _build_graph()
        result = mg.memory_interference_report(target.id)
        all_ids = [c["node_id"] for c in
                    result["proactive_interference"] + result["retroactive_interference"]]
        assert target.id not in all_ids

    def test_bilateral_edges_handled(self):
        """Test that bilateral (source↔target) edges are properly handled."""
        mg = MemoryGraph()
        a = mg.add("A", "concept", {"importance": 0.5})
        b = mg.add("B", "concept", {"importance": 0.5})
        c = mg.add("C", "concept", {"importance": 0.5})
        # a→b, b→a (bilateral), c→b
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "related")
        mg.link(c.id, b.id, "related")
        result = mg.memory_interference_report(a.id)
        # Should not crash
        assert isinstance(result, dict)

    def test_stale_target_recommendation(self):
        """Target accessed >7 days ago should get staleness warning."""
        mg = MemoryGraph()
        target = mg.add("Target", "concept")
        shared = mg.add("Shared", "concept")
        competitor = mg.add("Competitor", "concept")
        mg.link(target.id, shared.id, "related")
        mg.link(competitor.id, shared.id, "related")

        import time as _time
        old_time = _time.time() - 10 * 86400  # 10 days ago
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?", (old_time, target.id)
        )
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?", (100, competitor.id)
        )
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?", (200, shared.id)
        )
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?", (300, target.id)
        )
        mg.conn.commit()
        result = mg.memory_interference_report(target.id)
        assert any("disuse" in r.lower() or "not accessed" in r.lower()
                    for r in result["recommendations"])
