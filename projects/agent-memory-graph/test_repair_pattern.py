"""Tests for repair_pattern nodes — Cycle 443 (AgentTether, Research #018).

Prospective repair memory: record_repair() persists (failure → fix)
pairs as kind='repair_pattern' nodes; recall_repairs() retrieves them
by signature overlap with hit tracking; repair_stats() summarizes the
bank. Cross-iteration: iteration N+1 never rediscovers iteration N's
fix.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def fresh():
    return MemoryGraph()


@pytest.fixture
def bank(fresh):
    fresh.record_repair("ImportError optional dependency missing",
                        "pip install the extra")
    fresh.record_repair("ImportError optional dependency missing",
                        "pip install the extra")
    fresh.record_repair("test flaky race condition timeout",
                        "add deterministic seed")
    return fresh


# ── record_repair ──

class TestRecord:

    def test_creates_new_pattern(self, fresh):
        result = fresh.record_repair("ImportError dep missing", "pip install")
        assert result["created_new"] is True
        assert result["occurrences"] == 1
        node = fresh.get_node(result["pattern_id"])
        assert node.kind == "repair_pattern"
        assert node.label == "ImportError dep missing"
        assert node.data["fix"] == "pip install"

    def test_duplicate_signature_dedups(self, bank):
        """Re-recording same signature bumps occurrences, no new node."""
        before = bank.conn.execute(
            "SELECT COUNT(*) c FROM nodes WHERE kind='repair_pattern'"
        ).fetchone()["c"]
        result = bank.record_repair("ImportError optional dependency missing",
                                    "pip install the extra")
        assert result["created_new"] is False
        assert result["occurrences"] == 3  # 2 fixture + 1 now
        after = bank.conn.execute(
            "SELECT COUNT(*) c FROM nodes WHERE kind='repair_pattern'"
        ).fetchone()["c"]
        assert after == before

    def test_duplicate_updates_fix(self, bank):
        result = bank.record_repair("ImportError optional dependency missing",
                                    "better: use extras_require")
        assert result["created_new"] is False
        node = bank.get_node(result["pattern_id"])
        assert node.data["fix"] == "better: use extras_require"

    def test_context_stored(self, fresh):
        fresh.record_repair("sig", "fix", context="only in CI")
        result = fresh.recall_repairs("sig")
        assert result[0]["context"] == "only in CI"

    def test_tags_include_repair(self, fresh):
        result = fresh.record_repair("sig", "fix", tags=["ci"])
        row = fresh.conn.execute(
            "SELECT tags FROM nodes WHERE id=?", (result["pattern_id"],)
        ).fetchone()
        import json
        assert "repair" in json.loads(row["tags"])
        assert "ci" in json.loads(row["tags"])

    def test_data_fields_present(self, fresh):
        result = fresh.record_repair("sig", "fix")
        data = fresh.get_node(result["pattern_id"]).data
        assert data["occurrences"] == 1
        assert data["times_recalled"] == 0
        assert "created" in data
        assert "last_repaired" in data


# ── recall_repairs ──

class TestRecall:

    def test_exact_match_recalled(self, bank):
        results = bank.recall_repairs("ImportError optional dependency missing")
        assert len(results) == 1
        assert results[0]["fix"] == "pip install the extra"
        assert results[0]["match_score"] == 1.0

    def test_partial_match_ranked(self, bank):
        results = bank.recall_repairs("ImportError missing")
        assert len(results) == 1
        assert 0.0 < results[0]["match_score"] < 1.0

    def test_no_match_returns_empty(self, bank):
        assert bank.recall_repairs("completely unrelated thing") == []

    def test_results_sorted_by_score(self, fresh):
        fresh.record_repair("alpha beta gamma", "fix1")
        fresh.record_repair("alpha beta", "fix2")
        fresh.record_repair("alpha zeta", "fix3")
        results = fresh.recall_repairs("alpha beta", limit=5)
        scores = [r["match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        assert results[0]["signature"] == "alpha beta"

    def test_limit_respected(self, fresh):
        for i in range(5):
            fresh.record_repair(f"shared signature {i}", f"fix{i}")
        results = fresh.recall_repairs("shared signature", limit=2)
        assert len(results) == 2

    def test_recall_bumps_times_recalled(self, bank):
        r1 = bank.recall_repairs("ImportError optional dependency missing")
        assert r1[0]["times_recalled"] == 1
        r2 = bank.recall_repairs("ImportError optional dependency missing")
        assert r2[0]["times_recalled"] == 2

    def test_occurrences_tiebreak(self, fresh):
        """Equal scores → more-occurring pattern first."""
        fresh.record_repair("same words here", "fixA")
        fresh.record_repair("other same words", "fixB")
        fresh.record_repair("other same words", "fixB")  # occ=2
        results = fresh.recall_repairs("same words", limit=5)
        # "other same words" has overlap 2/4; "same words here" 2/4 — tie
        # occurrence tiebreak puts the occ=2 pattern first
        assert results[0]["signature"] == "other same words"

    def test_recall_on_empty_bank(self, fresh):
        assert fresh.recall_repairs("anything") == []


# ── repair_stats ──

class TestStats:

    def test_empty_bank_stats(self, fresh):
        stats = fresh.repair_stats()
        assert stats["total_patterns"] == 0
        assert stats["top_pattern"] is None
        assert "record_repair" in stats["recommendation"]

    def test_counts_patterns(self, bank):
        stats = bank.repair_stats()
        assert stats["total_patterns"] == 2
        assert stats["total_occurrences"] == 3  # 2 + 1

    def test_top_pattern_is_most_frequent(self, bank):
        stats = bank.repair_stats()
        assert stats["top_pattern"]["signature"] == \
            "ImportError optional dependency missing"

    def test_never_recalled_count(self, bank):
        stats = bank.repair_stats()
        assert stats["never_recalled"] == 2
        bank.recall_repairs("ImportError optional dependency missing")
        stats2 = bank.repair_stats()
        assert stats2["never_recalled"] == 1

    def test_recalls_tracked(self, bank):
        bank.recall_repairs("ImportError optional dependency missing")
        bank.recall_repairs("test flaky race")
        stats = bank.repair_stats()
        assert stats["total_recalls"] == 2


# ── Integration ──

class TestCrossIterationIntegration:

    def test_iteration_two_never_redisCOVERS(self, bank):
        """Iteration 1 records; iteration 2 recalls instead of debugging."""
        # iteration 2 hits the same wall
        results = bank.recall_repairs(
            "ImportError optional dependency missing again")
        assert len(results) >= 1
        assert "pip install" in results[0]["fix"]

    def test_pattern_becomes_more_authoritative(self, bank):
        """Each recurrence strengthens the pattern (occurrences ↑)."""
        bank.record_repair("ImportError optional dependency missing", "x")
        bank.record_repair("ImportError optional dependency missing", "x")
        stats = bank.repair_stats()
        assert stats["total_occurrences"] == 5  # 2 fixture + 2 + 1

    def test_nodes_are_first_class_graph_citizens(self, fresh):
        """Repair patterns participate in normal graph ops."""
        pid = fresh.record_repair("sig A", "fix A")["pattern_id"]
        other = fresh.add("related failure", kind="event")
        fresh.link(pid, other.id, "related_to")
        neighbors = fresh.search_by_label("sig A")
        assert neighbors[0].kind == "repair_pattern"
        # traversal includes repair node
        found = {n.id for n in fresh.neighbors(pid)}
        assert other.id in found

    def test_persistence_round_trip(self, tmp_path):
        path = str(tmp_path / "rp.db")
        g1 = MemoryGraph(path)
        pid = g1.record_repair("persist sig", "persist fix")["pattern_id"]
        g1.conn.close()
        g2 = MemoryGraph(path)
        results = g2.recall_repairs("persist sig")
        assert len(results) == 1
        assert results[0]["pattern_id"] == pid
        g2.conn.close()

    def test_coexists_with_other_kinds(self, fresh):
        fresh.add("fact node", kind="fact")
        fresh.record_repair("sig", "fix")
        stats = fresh.repair_stats()
        assert stats["total_patterns"] == 1  # fact not counted
        rows = fresh.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert rows == 2

    def test_cross_modal_scan_ignores_repair_nodes(self, fresh):
        """Repair patterns create no derivation edges — scan stays clean."""
        pid = fresh.record_repair("Alice failure 2024", "fix")["pattern_id"]
        scan = fresh.cross_modal_leak_scan(pid)
        assert scan["risk_level"] == "none"
