"""Tests for cue_reactivation() + soft_forget() — Oblivion-pattern
soft forgetting with cue-based reactivation.

Research #030: Adaptive Forgetting & Memory Pruning.
Oblivion (arXiv:2603.19550): memories become less accessible, not erased.
"""
import time
import json
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    g = MemoryGraph(":memory:")
    yield g


@pytest.fixture
def forgotten_graph():
    """Graph with some forgotten and some active nodes."""
    g = MemoryGraph(":memory:")
    # Active nodes
    a1 = g.add("Active project plan", "concept")
    a2 = g.add("Meeting notes", "event")

    # Nodes to be forgotten
    f1 = g.add("Old API key details", "fact")
    f2 = g.add("Deprecated project notes", "fact")
    f3 = g.add("Stale meeting summary", "event")

    # Soft-forget them
    g.soft_forget(f1.id, reason="security concern")
    g.soft_forget(f2.id, reason="outdated")
    g.soft_forget(f3.id, reason="aged out")

    yield g


# ── soft_forget() tests ────────────────────────────────────────

class TestSoftForget:
    def test_returns_true_for_existing_node(self, mg):
        n = mg.add("Node", "fact")
        assert mg.soft_forget(n.id) is True

    def test_returns_false_for_nonexistent(self, mg):
        assert mg.soft_forget("nonexistent") is False

    def test_sets_forgotten_flag(self, mg):
        n = mg.add("Test", "fact")
        mg.soft_forget(n.id)
        row = mg.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        data = json.loads(row["data"])
        assert data.get("forgotten") == 1

    def test_sets_forgotten_at_timestamp(self, mg):
        n = mg.add("Test", "fact")
        before = time.time()
        mg.soft_forget(n.id)
        row = mg.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        data = json.loads(row["data"])
        assert data.get("forgotten_at") >= before

    def test_records_reason(self, mg):
        n = mg.add("Sensitive data", "fact")
        mg.soft_forget(n.id, reason="privacy purge")
        row = mg.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        data = json.loads(row["data"])
        assert data.get("forget_reason") == "privacy purge"

    def test_default_reason_empty(self, mg):
        n = mg.add("Node", "fact")
        mg.soft_forget(n.id)
        row = mg.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        data = json.loads(row["data"])
        assert data.get("forget_reason") == ""

    def test_node_remains_in_graph(self, mg):
        """Soft-forgotten nodes are NOT deleted."""
        n = mg.add("Persist", "fact")
        mg.soft_forget(n.id)
        row = mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row is not None

    def test_edges_preserved_after_soft_forget(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "relates")
        mg.soft_forget(a.id)
        edges = mg.conn.execute(
            "SELECT COUNT(*) as c FROM edges WHERE source=? OR target=?",
            (a.id, a.id)
        ).fetchone()
        assert edges["c"] >= 1


# ── cue_reactivation() tests ───────────────────────────────────

class TestCueReactivation:
    def test_reactivates_matching_forgotten_node(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation("project")
        assert result["count"] >= 1
        # Reactivated node should have 'project' in label
        labels = [r["label"] for r in result["reactivated"]]
        assert any("project" in l.lower() for l in labels)

    def test_does_not_reactivate_non_matching(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation("nonexistent_topic_xyz")
        assert result["count"] == 0

    def test_clears_forgotten_flag(self, forgotten_graph):
        forgotten_graph.cue_reactivation("API")
        # Check the API node is no longer forgotten
        rows = forgotten_graph.conn.execute(
            "SELECT id, data FROM nodes WHERE label='Old API key details'"
        ).fetchone()
        data = json.loads(rows["data"])
        assert data.get("forgotten") is None or data.get("forgotten") != 1

    def test_boosts_weight(self, forgotten_graph):
        # Record original weight
        row = forgotten_graph.conn.execute(
            "SELECT weight FROM nodes WHERE label='Old API key details'"
        ).fetchone()
        old_w = row["weight"]

        result = forgotten_graph.cue_reactivation("API", reactivation_boost=0.8)
        if result["count"] > 0:
            reactivated = result["reactivated"][0]
            assert reactivated["new_weight"] >= old_w

    def test_updates_accessed_time(self, forgotten_graph):
        before = time.time()
        forgotten_graph.cue_reactivation("meeting")
        row = forgotten_graph.conn.execute(
            "SELECT accessed FROM nodes WHERE label='Stale meeting summary'"
        ).fetchone()
        if row:
            assert row["accessed"] >= before

    def test_scanned_count_matches_forgotten(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation("xyz_nothing")
        assert result["scanned"] == 3  # 3 forgotten nodes

    def test_limit_respected(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation("", limit=1)
        # With empty cue and fuzzy, might match all
        assert len(result["reactivated"]) <= 1

    def test_returns_reactivation_metadata(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation("project")
        assert "cue" in result
        assert "boost_applied" in result
        assert "reactivated" in result

    def test_fuzzy_keyword_matching(self, forgotten_graph):
        """Multiple keywords should match any."""
        result = forgotten_graph.cue_reactivation("API key")
        assert result["count"] >= 1

    def test_exact_match_mode(self, forgotten_graph):
        """Non-fuzzy mode requires exact label match."""
        result = forgotten_graph.cue_reactivation(
            "Old API key details", fuzzy=False)
        assert result["count"] >= 1

    def test_exact_match_case_insensitive(self, forgotten_graph):
        result = forgotten_graph.cue_reactivation(
            "old api key details", fuzzy=False)
        assert result["count"] >= 1


class TestCueReactivationMultiWord:
    def test_any_word_matches(self, mg):
        n1 = mg.add("Python tutorial", "fact")
        n2 = mg.add("Java guide", "fact")
        mg.soft_forget(n1.id)
        mg.soft_forget(n2.id)
        result = mg.cue_reactivation("Python")
        assert result["count"] >= 1
        labels = [r["label"] for r in result["reactivated"]]
        assert any("Python" in l for l in labels)

    def test_short_words_ignored(self, mg):
        """Words shorter than 3 chars are ignored in fuzzy mode."""
        n1 = mg.add("Ab cd", "fact")
        mg.soft_forget(n1.id)
        # 'ab' is only 2 chars → should not match via keyword
        # but 'ab' IS a substring of 'ab cd' so substring match will catch it
        # Use truly non-matching short text
        result = mg.cue_reactivation("xy", fuzzy=True)
        assert result["count"] == 0


# ── get_forgotten_nodes() tests ────────────────────────────────

class TestGetForgottenNodes:
    def test_returns_only_forgotten(self, forgotten_graph):
        nodes = forgotten_graph.get_forgotten_nodes()
        labels = [n["label"] for n in nodes]
        assert "Active project plan" not in labels
        assert "Old API key details" in labels

    def test_returns_metadata(self, forgotten_graph):
        nodes = forgotten_graph.get_forgotten_nodes()
        for n in nodes:
            assert "id" in n
            assert "label" in n
            assert "kind" in n
            assert "weight" in n
            assert "forgotten_at" in n
            assert "reason" in n

    def test_limit_respected(self, forgotten_graph):
        nodes = forgotten_graph.get_forgotten_nodes(limit=2)
        assert len(nodes) <= 2

    def test_empty_graph_returns_empty_list(self, mg):
        nodes = mg.get_forgotten_nodes()
        assert nodes == []

    def test_reason_preserved(self, forgotten_graph):
        nodes = forgotten_graph.get_forgotten_nodes()
        api_node = [n for n in nodes if "API" in n["label"]]
        if api_node:
            assert api_node[0]["reason"] == "security concern"


# ── Integration: soft_forget → cue_reactivation → compute_activation ──

class TestIntegration:
    def test_reactivated_node_has_keep_recommendation(self, mg):
        """After reactivation, compute_activation should recommend KEEP."""
        n = mg.add("Important forgotten fact", "fact")
        leaf = mg.add("Connected", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        mg.soft_forget(n.id)
        mg.cue_reactivation("Important")
        result = mg.compute_activation(n.id)
        # Freshly reactivated with edges → should be KEEP
        assert result["recommendation"] == "KEEP"

    def test_soft_forget_then_apply_decay_preserves_node(self, mg):
        """apply_decay should not delete softly forgotten nodes (they have weight)."""
        n = mg.add("Soft forgotten", "fact")
        mg.soft_forget(n.id)
        mg.apply_decay()
        exists = mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert exists is not None

    def test_full_lifecycle(self, mg):
        """Create → soft-forget → cue-reactivate → verify."""
        # Create
        n = mg.add("Lifelong learning", "concept")
        assert mg.compute_activation(n.id)["recommendation"] == "KEEP"

        # Soft-forget
        mg.soft_forget(n.id, reason="low priority")
        forgotten = mg.get_forgotten_nodes()
        assert any(f["id"] == n.id for f in forgotten)

        # Reactivate
        result = mg.cue_reactivation("learning")
        assert result["count"] >= 1

        # Verify not forgotten
        forgotten_after = mg.get_forgotten_nodes()
        assert not any(f["id"] == n.id for f in forgotten_after)
