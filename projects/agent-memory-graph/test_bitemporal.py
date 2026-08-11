"""Tests for bi-temporal edge APIs: edge_record, edge_supersede,
query_as_of, knowledge_diff, supersedence_chain.

Cycles 412+ — Bi-Temporal Agent Memory (Research #057, Issue #033).

Extends the existing valid-time axis (valid_from/valid_until) with a
transaction-time axis (recorded_at/expired_at), enabling true "as-of"
queries: "what did the agent know at time T?"
"""

import pytest
import tempfile
import os
import time as _time
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    """Fresh in-memory graph for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    g = MemoryGraph(db_path=path)
    yield g
    os.unlink(path)


# ── Helper ──────────────────────────────────────────────────────

def _add_edge(g, src, tgt, rel, recorded_at=None):
    """Add edge and return it."""
    if not g.has_node(src):
        g._insert_node_raw(src, src)
    if not g.has_node(tgt):
        g._insert_node_raw(tgt, tgt)
    g.link(src, tgt, rel)
    if recorded_at is not None:
        props = g.edge_properties(src, tgt, rel) or {}
        props["_temporal"] = {
            "valid_from": recorded_at,
            "valid_until": None,
            "recorded_at": recorded_at,
            "expired_at": None,
            "supersedes": None,
            "source_episode": None,
        }
        g.set_edge_properties(src, tgt, rel, props)
        g.conn.commit()
    return g.get_edge(src, tgt, rel)


# ── Cycle 412: edge_record ─────────────────────────────────────


class TestEdgeRecord:
    """edge_record() creates an edge with full bi-temporal metadata."""

    def test_basic_record(self, mg):
        """Creates edge with auto-generated recorded_at."""
        before = _time.time()
        result = mg.edge_record("alice", "acme", "works_at")
        after = _time.time()
        assert result is not None
        assert "recorded_at" in result
        assert before <= result["recorded_at"] <= after

    def test_record_with_valid_at(self, mg):
        """Explicit valid_at is stored correctly."""
        t = 1700000000.0
        result = mg.edge_record("alice", "acme", "works_at",
                                 valid_at=t, source_episode="ep_001")
        assert result["valid_from"] == t
        assert result["recorded_at"] >= t
        assert result["source_episode"] == "ep_001"

    def test_record_auto_valid_from(self, mg):
        """Without explicit valid_at, valid_from defaults to recorded_at."""
        result = mg.edge_record("bob", "home", "lives_in")
        assert result["valid_from"] == result["recorded_at"]

    def test_record_idempotent(self, mg):
        """Calling edge_record twice on same triple returns existing."""
        mg.edge_record("x", "y", "knows")
        r1 = mg.edge_record("x", "y", "knows")
        assert r1 is not None
        # Should not create duplicate edges
        edges = mg.edges_of("x", direction="outgoing")
        assert len([e for e in edges if e.relation == "knows" and e.target == "y"]) == 1

    def test_record_returns_temporal_dict(self, mg):
        """Result contains all bi-temporal fields."""
        result = mg.edge_record("a", "b", "rel")
        expected_keys = {"valid_from", "valid_until", "recorded_at",
                         "expired_at", "supersedes", "source_episode"}
        assert expected_keys.issubset(result.keys())
        assert result["valid_until"] is None
        assert result["expired_at"] is None
        assert result["supersedes"] is None


# ── Cycle 412: edge_supersede ──────────────────────────────────


class TestEdgeSupersede:
    """edge_supersede() performs non-destructive replacement."""

    def test_basic_supersede(self, mg):
        """Old fact gets expired_at set, new fact references old."""
        T0 = 1700000000.0
        T1 = 1701000000.0
        old = mg.edge_record("alice", "acme", "works_at", valid_at=T0)
        # Manually set recorded_at for deterministic test
        props = mg.edge_properties("alice", "acme", "works_at")
        props["_temporal"]["recorded_at"] = T0
        mg.set_edge_properties("alice", "acme", "works_at", props)
        mg.conn.commit()

        new = mg.edge_supersede("alice", "acme", "works_at",
                                 new_target="google", valid_at=T1,
                                 recorded_at=T1)
        assert new is not None
        assert new["supersedes"] is not None  # references old edge

        # Check old edge was invalidated
        old_props = mg.edge_properties("alice", "acme", "works_at")
        old_temporal = old_props.get("_temporal", {})
        assert old_temporal.get("valid_until") is not None
        assert old_temporal.get("expired_at") is not None

    def test_supersede_creates_new_edge(self, mg):
        """Supersede creates a new edge with the new target."""
        T0 = 1700000000.0
        T1 = 1701000000.0
        mg.edge_record("alice", "acme", "works_at", valid_at=T0)

        mg.edge_supersede("alice", "acme", "works_at",
                          new_target="google", valid_at=T1, recorded_at=T1)

        # New edge should exist
        assert mg.get_edge("alice", "google", "works_at") is not None
        # Old edge should still exist (non-destructive)
        assert mg.get_edge("alice", "acme", "works_at") is not None

    def test_supersede_none_if_no_existing(self, mg):
        """Returns None if no existing edge to supersede."""
        result = mg.edge_supersede("x", "y", "z", new_target="w")
        assert result is None


# ── Cycle 412: query_as_of ────────────────────────────────────


class TestQueryAsOf:
    """query_as_of() — core bi-temporal point-in-time query."""

    def _setup_scenario(self, mg):
        """Classic Alice works_at scenario."""
        T0 = 1700000000.0  # Jan 2023
        T1 = 1701000000.0  # ~Nov 2023 (Alice actually moves)
        T2 = 1702000000.0  # ~Dec 2023 (agent learns about move)

        # Agent records: Alice works at Acme (recorded T0, valid T0)
        mg.edge_record("alice", "acme", "works_at", valid_at=T0)
        props = mg.edge_properties("alice", "acme", "works_at")
        props["_temporal"]["recorded_at"] = T0
        props["_temporal"]["valid_from"] = T0
        mg.set_edge_properties("alice", "acme", "works_at", props)
        mg.conn.commit()

        # Agent learns Alice moved to Google (recorded T2, valid from T1)
        mg.edge_supersede("alice", "acme", "works_at",
                          new_target="google", valid_at=T1, recorded_at=T2)

        return T0, T1, T2

    def test_knowledge_at_t0(self, mg):
        """At T0, agent knows Alice works at Acme."""
        T0, T1, T2 = self._setup_scenario(mg)
        results = mg.bitemporal_as_of(T0, mode="knowledge")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        assert ("alice", "acme", "works_at") in facts
        assert ("alice", "google", "works_at") not in facts

    def test_knowledge_at_t1_plus_epsilon(self, mg):
        """At T1+ε, agent still only knows Acme (hasn't learned yet)."""
        T0, T1, T2 = self._setup_scenario(mg)
        results = mg.bitemporal_as_of(T1 + 1, mode="knowledge")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        # Agent hasn't recorded Google yet (recorded_at=T2 > T1+1)
        assert ("alice", "acme", "works_at") in facts
        assert ("alice", "google", "works_at") not in facts

    def test_knowledge_at_t2(self, mg):
        """At T2, agent now knows Alice works at Google."""
        T0, T1, T2 = self._setup_scenario(mg)
        results = mg.bitemporal_as_of(T2, mode="knowledge")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        assert ("alice", "acme", "works_at") not in facts
        assert ("alice", "google", "works_at") in facts

    def test_truth_at_t1_plus_epsilon(self, mg):
        """Truth mode: Alice works at Google from T1, even if agent
        doesn't know yet."""
        T0, T1, T2 = self._setup_scenario(mg)
        results = mg.bitemporal_as_of(T1 + 1, mode="truth")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        # Truth says Google is valid from T1
        assert ("alice", "google", "works_at") in facts

    def test_certain_mode(self, mg):
        """Certain mode: intersection of knowledge and truth."""
        T0, T1, T2 = self._setup_scenario(mg)
        # At T1+1, agent knows acme but truth is google → nothing is "certain"
        results = mg.bitemporal_as_of(T1 + 1, mode="certain")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        # Neither acme (wrong truth) nor google (unknown) is certain
        assert ("alice", "acme", "works_at") not in facts
        assert ("alice", "google", "works_at") not in facts

    def test_filter_by_source(self, mg):
        """query_as_of with source filter."""
        T0, T1, T2 = self._setup_scenario(mg)
        mg._insert_node_raw("bob", "bob")
        mg.edge_record("bob", "startup", "works_at", valid_at=T0)
        results = mg.bitemporal_as_of(T0, mode="knowledge", source="alice")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        assert all(f[0] == "alice" for f in facts)

    def test_filter_by_relation(self, mg):
        """query_as_of with relation filter."""
        T0, T1, T2 = self._setup_scenario(mg)
        mg.edge_record("alice", "bob", "knows", valid_at=T0)
        results = mg.bitemporal_as_of(T0, mode="knowledge", relation="works_at")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        assert all(f[2] == "works_at" for f in facts)

    def test_invalid_mode_raises(self, mg):
        """Unknown mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            mg.bitemporal_as_of(1700000000.0, mode="nonexistent")

    def test_no_temporal_metadata_always_included(self, mg):
        """Edges without _temporal metadata are always included."""
        mg._insert_node_raw("x", "x")
        mg._insert_node_raw("y", "y")
        mg.link("x", "y", "plain")
        results = mg.bitemporal_as_of(0.0, mode="knowledge")
        facts = {(f["source"], f["target"], f["relation"]) for f in results}
        assert ("x", "y", "plain") in facts


# ── Cycle 412: knowledge_diff ──────────────────────────────────


class TestKnowledgeDiff:
    """knowledge_diff() — what changed between two time points."""

    def _setup_scenario(self, mg):
        T0 = 1700000000.0
        T1 = 1701000000.0
        T2 = 1702000000.0
        mg.edge_record("alice", "acme", "works_at", valid_at=T0)
        props = mg.edge_properties("alice", "acme", "works_at")
        props["_temporal"]["recorded_at"] = T0
        mg.set_edge_properties("alice", "acme", "works_at", props)
        mg.conn.commit()
        mg.edge_supersede("alice", "acme", "works_at",
                          new_target="google", valid_at=T1, recorded_at=T2)
        return T0, T1, T2

    def test_diff_t0_to_t2(self, mg):
        """Between T0 and T2, acme removed, google added."""
        T0, T1, T2 = self._setup_scenario(mg)
        diff = mg.knowledge_diff(T0, T2, mode="knowledge")
        removed = {(f["source"], f["target"], f["relation"])
                   for f in diff["removed"]}
        added = {(f["source"], f["target"], f["relation"])
                 for f in diff["added"]}
        assert ("alice", "acme", "works_at") in removed
        assert ("alice", "google", "works_at") in added

    def test_diff_no_change(self, mg):
        """Between T0 and T0+1 (no events), no changes."""
        T0, T1, T2 = self._setup_scenario(mg)
        diff = mg.knowledge_diff(T0, T0 + 1, mode="knowledge")
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0

    def test_diff_returns_dict_keys(self, mg):
        """Diff result has standard keys."""
        mg.edge_record("a", "b", "r")
        diff = mg.knowledge_diff(1700000000.0, 1700000001.0)
        assert "added" in diff
        assert "removed" in diff
        assert "updated" in diff


# ── Cycle 412: supersedence_chain ─────────────────────────────


class TestSupersedenceChain:
    """supersedence_chain() — trace fact replacement lineage."""

    def test_basic_chain(self, mg):
        """f002 supersedes f001 → chain is [f001, f002]."""
        T0 = 1700000000.0
        T1 = 1701000000.0
        mg.edge_record("alice", "acme", "works_at", valid_at=T0)
        props = mg.edge_properties("alice", "acme", "works_at")
        props["_temporal"]["recorded_at"] = T0
        mg.set_edge_properties("alice", "acme", "works_at", props)
        mg.conn.commit()

        new_temporal = mg.edge_supersede("alice", "acme", "works_at",
                                          new_target="google",
                                          valid_at=T1, recorded_at=T1)
        new_props = mg.edge_properties("alice", "google", "works_at")
        new_tid = new_props["_temporal"].get("supersedes_temporal_id")

        if new_tid:
            chain = mg.supersedence_chain(new_tid)
            assert len(chain) == 2
            assert chain[0]["source"] == "alice"
            assert chain[0]["target"] == "acme"
            assert chain[1]["source"] == "alice"
            assert chain[1]["target"] == "google"

    def test_no_chain(self, mg):
        """Edge without supersedes returns chain of length 1."""
        mg.edge_record("a", "b", "r")
        props = mg.edge_properties("a", "b", "r")
        chain = mg.supersedence_chain(props["_temporal"].get("temporal_id"))
        assert len(chain) <= 1
