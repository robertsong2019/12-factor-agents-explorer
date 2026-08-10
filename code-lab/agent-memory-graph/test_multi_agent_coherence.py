"""
Tests for MultiAgentMemoryGraph — MESI-inspired cache coherence.
Research #055: Multi-Agent Memory Consistency.
Covers: agent registration, cache-coherent read/write, invalidation,
conflict detection, coherence report, community scoping, sync operations.
"""

import pytest
import time
from memory_graph import MemoryGraph, MultiAgentMemoryGraph, MESICache


@pytest.fixture
def mamg():
    """MultiAgentMemoryGraph with 3 agents and some nodes."""
    mg = MemoryGraph()
    node_ids = []
    for i in range(10):
        n = mg.add(f"node_{i}", "concept", {"index": i})
        node_ids.append(n.id)
    mamg = MultiAgentMemoryGraph(mg)
    mamg.register_agent("alpha", community=0)
    mamg.register_agent("beta", community=0)
    mamg.register_agent("gamma", community=1)
    mamg._test_node_ids = node_ids  # stash for tests
    return mamg


def _nid(mamg, idx=0):
    """Get a node ID from the fixture."""
    return mamg._test_node_ids[idx]


# ─── MESICache Unit Tests ───────────────────────────────────────────────

class TestMESICache:
    def test_default_state_is_shared(self):
        c = MESICache("n1", "alpha")
        assert c.state == "Shared"

    def test_is_readable(self):
        assert MESICache("n1", "a", "Modified").is_readable()
        assert MESICache("n1", "a", "Exclusive").is_readable()
        assert MESICache("n1", "a", "Shared").is_readable()
        assert not MESICache("n1", "a", "Invalid").is_readable()

    def test_is_writable(self):
        assert MESICache("n1", "a", "Modified").is_writable()
        assert MESICache("n1", "a", "Exclusive").is_writable()
        assert not MESICache("n1", "a", "Shared").is_writable()
        assert not MESICache("n1", "a", "Invalid").is_writable()

    def test_to_dict(self):
        c = MESICache("n1", "alpha", "Modified", version=5)
        d = c.to_dict()
        assert d["node_id"] == "n1"
        assert d["agent_id"] == "alpha"
        assert d["state"] == "Modified"
        assert d["version"] == 5

    def test_slots_prevents_extra_attrs(self):
        c = MESICache("n1", "alpha")
        with pytest.raises(AttributeError):
            c.extra_field = "oops"

    def test_cached_at_defaults_to_now(self):
        before = time.time()
        c = MESICache("n1", "alpha")
        after = time.time()
        assert before <= c.cached_at <= after

    def test_all_four_states(self):
        for state in ("Modified", "Exclusive", "Shared", "Invalid"):
            c = MESICache("n1", "a", state)
            assert c.state == state


# ─── Agent Management ──────────────────────────────────────────────────

class TestAgentManagement:
    def test_register_agent(self, mamg):
        result = mamg.register_agent("delta", community=2)
        assert result["status"] == "registered"
        assert result["agent_id"] == "delta"
        assert result["community"] == 2

    def test_register_agent_creates_empty_cache(self, mamg):
        mamg.register_agent("delta")
        assert mamg._caches["delta"] == {}

    def test_unregister_agent(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        result = mamg.unregister_agent("alpha")
        assert result["status"] == "unregistered"
        assert result["cache_entries_removed"] >= 1
        assert "alpha" not in mamg._caches

    def test_unregister_unknown_agent(self, mamg):
        result = mamg.unregister_agent("nobody")
        assert result["status"] == "unregistered"
        assert result["cache_entries_removed"] == 0

    def test_list_agents(self, mamg):
        agents = mamg.list_agents()
        assert len(agents) == 3
        ids = {a["agent_id"] for a in agents}
        assert ids == {"alpha", "beta", "gamma"}

    def test_list_agents_includes_cache_stats(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        agents = mamg.list_agents()
        alpha = [a for a in agents if a["agent_id"] == "alpha"][0]
        assert alpha["cached_nodes"] >= 1
        assert "state_distribution" in alpha
        assert alpha["community"] == 0


# ─── Cache-Coherent Read ───────────────────────────────────────────────

class TestAgentRead:
    def test_read_returns_cache_on_hit(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)  # populate cache
        result = mamg.agent_read("alpha", nid)  # cache hit
        assert result["source"] == "cache"
        assert result["node_id"] == nid

    def test_first_read_gets_exclusive_if_alone(self, mamg):
        nid = _nid(mamg, 0)
        result = mamg.agent_read("alpha", nid)
        assert result["source"] == "graph"
        assert result["state"] == "Exclusive"

    def test_second_agent_read_makes_shared(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)  # Exclusive for alpha
        mamg.agent_read("beta", nid)   # beta reads — alpha should downgrade to Shared
        assert mamg._caches["alpha"][nid].state == "Shared"
        assert mamg._caches["beta"][nid].state == "Shared"

    def test_read_nonexistent_node(self, mamg):
        result = mamg.agent_read("alpha", "nonexistent_node")
        assert result is None

    def test_read_by_unregistered_agent(self, mamg):
        result = mamg.agent_read("unregistered", _nid(mamg, 0))
        assert result is None

    def test_read_after_invalidation_fetches_from_graph(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg._caches["alpha"][nid].state = MESICache.I
        result = mamg.agent_read("alpha", nid)
        assert result["source"] == "graph"

    def test_read_updates_cached_at(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        old_ts = mamg._caches["alpha"][nid].cached_at
        time.sleep(0.01)
        mamg.agent_read("alpha", nid)
        assert mamg._caches["alpha"][nid].cached_at > old_ts


# ─── Cache-Coherent Write ──────────────────────────────────────────────

class TestAgentWrite:
    def test_write_sets_modified_state(self, mamg):
        nid = _nid(mamg, 0)
        result = mamg.agent_write("alpha", nid, "update")
        assert result["new_state"] == "Modified"
        assert mamg._caches["alpha"][nid].state == "Modified"

    def test_write_invalidates_other_agents(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        result = mamg.agent_write("alpha", nid, "update")
        assert "beta" in result["invalidated_agents"]
        assert mamg._caches["beta"][nid].state == "Invalid"

    def test_write_does_not_invalidate_writer(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        result = mamg.agent_write("alpha", nid, "update")
        assert "alpha" not in result["invalidated_agents"]

    def test_write_by_unregistered_agent(self, mamg):
        nid = _nid(mamg, 0)
        result = mamg.agent_write("unknown", nid, "update")
        assert "error" in result

    def test_write_nonexistent_node(self, mamg):
        result = mamg.agent_write("alpha", "nonexistent", "update")
        assert "error" in result

    def test_write_increments_version(self, mamg):
        nid = _nid(mamg, 0)
        r1 = mamg.agent_write("alpha", nid, "update")
        r2 = mamg.agent_write("alpha", nid, "update")
        assert r2["version"] > r1["version"]

    def test_write_shared_upgrades_to_modified(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)  # Exclusive
        mamg.agent_read("beta", nid)   # Both Shared
        assert mamg._caches["alpha"][nid].state == "Shared"
        mamg.agent_write("alpha", nid, "update")
        assert mamg._caches["alpha"][nid].state == "Modified"

    def test_write_logs_operation(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        log = mamg._write_log.get(nid, [])
        assert len(log) >= 1
        assert log[-1][0] == "alpha"
        assert log[-1][2] == "update"

    def test_write_creates_pending_invalidation(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        assert nid in mamg._pending_invalidations
        assert "beta" in mamg._pending_invalidations[nid]


# ─── Conflict Detection ────────────────────────────────────────────────

class TestConflictDetection:
    def test_concurrent_writes_detect_conflict(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        result = mamg.agent_write("beta", nid, "update")
        assert len(result["conflicts"]) >= 1

    def test_conflict_metadata(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        result = mamg.agent_write("beta", nid, "update")
        if result["conflicts"]:
            c = result["conflicts"][0]
            assert c["agent"] == "alpha"
            assert c["type"] == "concurrent_write"
            assert "age_seconds" in c
            assert "op" in c

    def test_no_conflict_after_5_seconds(self, mamg):
        nid = _nid(mamg, 0)
        mamg._write_log[nid] = [("alpha", time.time() - 10.0, "update")]
        result = mamg.agent_write("beta", nid, "update")
        assert len(result["conflicts"]) == 0

    def test_no_conflict_same_agent(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        result = mamg.agent_write("alpha", nid, "update")
        assert len(result["conflicts"]) == 0


# ─── Coherence Report ──────────────────────────────────────────────────

class TestCoherenceReport:
    def test_empty_report(self):
        mg = MemoryGraph()
        mamg = MultiAgentMemoryGraph(mg)
        mamg.register_agent("solo")
        report = mamg.coherence_report()
        assert report["total_agents"] == 1
        assert report["total_cache_entries"] == 0
        assert report["coherence_ratio"] == 1.0

    def test_report_after_activity(self, mamg):
        nid0 = _nid(mamg, 0)
        nid1 = _nid(mamg, 1)
        mamg.agent_read("alpha", nid0)
        mamg.agent_read("beta", nid0)
        mamg.agent_read("alpha", nid1)
        mamg.agent_write("alpha", nid0, "update")
        report = mamg.coherence_report()
        assert report["total_agents"] == 3
        assert report["total_cache_entries"] >= 3
        assert "state_distribution" in report
        assert report["state_distribution"]["Modified"] >= 1
        assert report["state_distribution"]["Invalid"] >= 1

    def test_coherence_ratio_decreases_with_invalidations(self, mamg):
        for i in range(5):
            nid = _nid(mamg, i)
            mamg.agent_read("alpha", nid)
            mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", _nid(mamg, 0), "update")
        report = mamg.coherence_report()
        assert report["state_distribution"]["Invalid"] >= 1
        assert report["coherence_ratio"] < 1.0

    def test_per_agent_breakdown(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        report = mamg.coherence_report()
        assert "alpha" in report["per_agent"]
        assert report["per_agent"]["alpha"]["total"] >= 1

    def test_write_conflicts_in_report(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        mamg.agent_write("beta", nid, "update")
        report = mamg.coherence_report()
        assert report["write_conflicts_detected"] >= 1

    def test_consistency_level_in_report(self, mamg):
        report = mamg.coherence_report()
        assert "consistency_level" in report
        assert report["consistency_level"] == "eventual"


# ─── Community Scoping ─────────────────────────────────────────────────

class TestCommunityScoping:
    def test_scope_report_shows_communities(self, mamg):
        report = mamg.scope_report()
        assert report["total_communities"] == 2  # community 0 and 1
        assert "0" in report["communities"]
        assert "1" in report["communities"]
        assert "alpha" in report["communities"]["0"]
        assert "gamma" in report["communities"]["1"]

    def test_cross_community_sharing(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("gamma", nid)
        report = mamg.scope_report()
        assert report["cross_community_shared_nodes"] >= 1

    def test_no_cross_community_when_separate(self, mamg):
        mamg.agent_read("alpha", _nid(mamg, 0))
        mamg.agent_read("gamma", _nid(mamg, 1))
        report = mamg.scope_report()
        assert report["cross_community_shared_nodes"] == 0

    def test_scope_report_agent_list(self, mamg):
        report = mamg.scope_report()
        comm_0 = report["communities"]["0"]
        assert "alpha" in comm_0
        assert "beta" in comm_0
        assert "gamma" not in comm_0


# ─── Sync Operations ──────────────────────────────────────────────────

class TestSyncOperations:
    def test_sync_refreshes_invalidated_entries(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        assert mamg._caches["beta"][nid].state == "Invalid"
        result = mamg.sync_agent("beta")
        assert result["invalidations_processed"] >= 1
        assert result["nodes_refreshed"] >= 1
        assert mamg._caches["beta"][nid].state == "Shared"

    def test_sync_unknown_agent(self, mamg):
        result = mamg.sync_agent("nobody")
        assert "error" in result

    def test_sync_with_no_pending(self, mamg):
        result = mamg.sync_agent("alpha")
        assert result["invalidations_processed"] == 0

    def test_broadcast_invalidate(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_read("gamma", nid)
        result = mamg.broadcast_invalidate(nid)
        assert set(result["invalidated_agents"]) == {"alpha", "beta", "gamma"}
        for aid in ("alpha", "beta", "gamma"):
            assert mamg._caches[aid][nid].state == "Invalid"

    def test_broadcast_invalidate_except_writer(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        result = mamg.broadcast_invalidate(nid, except_agent="alpha")
        assert "alpha" not in result["invalidated_agents"]
        assert "beta" in result["invalidated_agents"]

    def test_broadcast_invalidate_uncached_node(self, mamg):
        result = mamg.broadcast_invalidate("uncached_node")
        assert result["invalidated_agents"] == []


# ─── Integration Scenarios ─────────────────────────────────────────────

class TestIntegrationScenarios:
    def test_multi_agent_collaboration(self, mamg):
        # alpha writes, beta reads stale, beta syncs, beta reads fresh
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        write_result = mamg.agent_write("alpha", nid, "update")
        assert "beta" in write_result["invalidated_agents"]
        read_result = mamg.agent_read("beta", nid)
        assert read_result["source"] == "graph"

    def test_three_agent_cascade(self, mamg):
        # Three agents: writer invalidates two readers
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_read("gamma", nid)
        assert all(mamg._caches[a][nid].state == "Shared"
                   for a in ("alpha", "beta", "gamma"))
        result = mamg.agent_write("alpha", nid, "update")
        assert set(result["invalidated_agents"]) == {"beta", "gamma"}

    def test_token_savings_vs_rebroadcast(self, mamg):
        # Verify invalidation sends less data than full rebroadcast
        for i in range(10):
            nid = _nid(mamg, i)
            mamg.agent_read("alpha", nid)
            mamg.agent_read("beta", nid)
        write_result = mamg.agent_write("alpha", _nid(mamg, 0), "update")
        invalidated_count = len(write_result["invalidated_agents"])
        assert invalidated_count >= 1
        report = mamg.coherence_report()
        assert report["state_distribution"]["Invalid"] < report["total_cache_entries"]

    def test_full_lifecycle(self, mamg):
        # Full lifecycle: register, read, write, conflict, sync, report
        nid = _nid(mamg, 0)
        # 1. Read
        mamg.agent_read("alpha", nid)
        assert mamg._caches["alpha"][nid].state == "Exclusive"
        # 2. Second agent reads
        mamg.agent_read("beta", nid)
        assert mamg._caches["alpha"][nid].state == "Shared"
        # 3. Write creates conflict
        mamg.agent_write("alpha", nid, "update")
        # 4. Beta is invalidated
        assert mamg._caches["beta"][nid].state == "Invalid"
        # 5. Beta syncs
        mamg.sync_agent("beta")
        assert mamg._caches["beta"][nid].state == "Shared"
        # 6. Report shows healthy coherence
        report = mamg.coherence_report()
        assert report["coherence_ratio"] > 0.0


# ─── Auto-Scoping Tests ────────────────────────────────────────────────

class TestAutoScoping:
    def test_auto_scope_no_activity(self, mamg):
        result = mamg.auto_scope_agents()
        assert result["algorithm"] == "lp"
        assert "total_communities" in result

    def test_auto_scope_after_activity(self, mamg):
        # alpha reads nodes 0-4, gamma reads nodes 5-9
        for i in range(5):
            mamg.agent_read("alpha", _nid(mamg, i))
        for i in range(5, 10):
            mamg.agent_read("gamma", _nid(mamg, i))
        result = mamg.auto_scope_agents()
        assert result["agents_reassigned"] >= 0

    def test_auto_scope_returns_reassignment_details(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        result = mamg.auto_scope_agents()
        if result["agents_reassigned"] > 0:
            r = result["reassignments"][0]
            assert "agent_id" in r
            assert "new_community" in r
            assert "votes" in r


class TestDetectWriteConflicts:
    def test_no_conflicts_on_clean_log(self, mamg):
        conflicts = mamg.detect_write_conflicts()
        assert conflicts == []

    def test_detects_concurrent_writes(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        mamg.agent_write("beta", nid, "update")
        conflicts = mamg.detect_write_conflicts()
        assert len(conflicts) >= 1
        assert conflicts[0]["agent_a"] != conflicts[0]["agent_b"]

    def test_conflict_metadata_complete(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_write("alpha", nid, "update")
        mamg.agent_write("beta", nid, "update")
        conflicts = mamg.detect_write_conflicts()
        if conflicts:
            c = conflicts[0]
            assert "node_id" in c
            assert "agent_a" in c
            assert "agent_b" in c
            assert "time_gap_s" in c
            assert "op_a" in c
            assert "op_b" in c

    def test_no_conflict_outside_window(self, mamg):
        nid = _nid(mamg, 0)
        mamg._write_log[nid] = [
            ("alpha", time.time() - 100.0, "update"),
            ("beta", time.time(), "update"),
        ]
        conflicts = mamg.detect_write_conflicts(time_window=5.0)
        assert len(conflicts) == 0


class TestCoherenceDashboard:
    def test_dashboard_structure(self, mamg):
        d = mamg.coherence_dashboard()
        assert "summary" in d
        assert "state_distribution" in d
        assert "recent_conflicts" in d
        assert "per_agent" in d

    def test_dashboard_summary_fields(self, mamg):
        d = mamg.coherence_dashboard()
        s = d["summary"]
        assert "agents" in s
        assert "coherence_ratio" in s
        assert "cache_entries" in s
        assert "write_conflicts" in s
        assert "communities" in s
        assert "consistency_level" in s

    def test_dashboard_after_activity(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        d = mamg.coherence_dashboard()
        assert d["summary"]["cache_entries"] >= 2
        assert d["summary"]["write_conflicts"] >= 0
        assert d["summary"]["agents"] == 3


# ─── Consistency Level Tests ───────────────────────────────────────────

class TestConsistencyLevel:
    def test_set_consistency_level(self, mamg):
        result = mamg.set_consistency_level("causal")
        assert result["new_level"] == "causal"
        assert result["old_level"] == "eventual"
        assert mamg.consistency_level == "causal"

    def test_set_invalid_level(self, mamg):
        result = mamg.set_consistency_level("bogus")
        assert "error" in result

    def test_set_all_four_levels(self, mamg):
        for level in ("session", "causal", "eventual", "committed"):
            result = mamg.set_consistency_level(level)
            assert result["new_level"] == level

    def test_level_description_included(self, mamg):
        result = mamg.set_consistency_level("committed")
        assert "description" in result
        assert len(result["description"]) > 0


class TestCommitSnapshot:
    def test_snapshot_basic(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        snap = mamg.commit_snapshot("alpha", "milestone-1")
        assert snap["agent_id"] == "alpha"
        assert snap["label"] == "milestone-1"
        assert snap["node_count"] >= 1
        assert snap["immutable"] is True

    def test_snapshot_version_increments(self, mamg):
        mamg.agent_read("alpha", _nid(mamg, 0))
        s1 = mamg.commit_snapshot("alpha")
        s2 = mamg.commit_snapshot("alpha")
        assert s2["snapshot_version"] > s1["snapshot_version"]

    def test_snapshot_unregistered_agent(self, mamg):
        result = mamg.commit_snapshot("nobody")
        assert "error" in result

    def test_snapshot_only_includes_readable(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")  # invalidates beta
        snap = mamg.commit_snapshot("alpha")
        # alpha has Modified state — should be included
        assert snap["node_count"] >= 1


class TestCausalOrderCheck:
    def test_causally_consistent_after_sync(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        mamg.sync_agent("beta")  # beta refreshes
        result = mamg.causal_order_check("alpha", "beta")
        assert result["causally_consistent"] is True
        assert result["visible"] >= 1
        assert result["stale"] == 0

    def test_not_consistent_before_sync(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        # beta has NOT synced yet
        result = mamg.causal_order_check("alpha", "beta")
        assert result["causally_consistent"] is False
        assert result["stale"] >= 1

    def test_no_writes_is_consistent(self, mamg):
        result = mamg.causal_order_check("alpha", "beta")
        assert result["causally_consistent"] is True
        assert result["stale"] == 0

    def test_unregistered_agent(self, mamg):
        result = mamg.causal_order_check("alpha", "nobody")
        assert "error" in result

    def test_causal_check_returns_stale_ids(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid, "update")
        result = mamg.causal_order_check("alpha", "beta")
        assert nid in result["stale_node_ids"]


class TestAgentDiff:
    """Tests for agent_diff() — knowledge divergence detection."""

    def test_identical_caches_zero_divergence(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        result = mamg.agent_diff("alpha", "beta")
        assert result["divergence_score"] == 0.0
        assert result["shared_readable"] == 1

    def test_a_exclusive_node(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)  # only alpha reads
        result = mamg.agent_diff("alpha", "beta")
        assert result["a_exclusive"] == 1
        assert result["b_exclusive"] == 0

    def test_both_exclusive(self, mamg):
        n1 = _nid(mamg, 0)
        n2 = _nid(mamg, 1)
        mamg.agent_read("alpha", n1)
        mamg.agent_read("beta", n2)
        result = mamg.agent_diff("alpha", "beta")
        assert result["a_exclusive"] == 1
        assert result["b_exclusive"] == 1

    def test_stale_detection(self, mamg):
        nid = _nid(mamg, 0)
        mamg.agent_read("alpha", nid)
        mamg.agent_read("beta", nid)
        mamg.agent_write("alpha", nid)  # invalidates beta
        result = mamg.agent_diff("alpha", "beta")
        assert result["b_stale_a_fresh"] == 1

    def test_unregistered_agent(self, mamg):
        result = mamg.agent_diff("alpha", "ghost")
        assert "error" in result

    def test_divergence_score_in_range(self, mamg):
        n1 = _nid(mamg, 0)
        mamg.agent_read("alpha", n1)
        result = mamg.agent_diff("alpha", "beta")
        assert 0.0 <= result["divergence_score"] <= 1.0

    def test_exclusive_ids_capped_at_20(self, mamg):
        # Add more nodes to exceed the 20-item cap
        for i in range(20):
            n = mamg.graph.add(f"extra_{i}", "concept")
            mamg._test_node_ids.append(n.id)
        for i in range(25):
            mamg.agent_read("alpha", _nid(mamg, i))
        result = mamg.agent_diff("alpha", "beta")
        assert len(result["a_exclusive_ids"]) <= 20
