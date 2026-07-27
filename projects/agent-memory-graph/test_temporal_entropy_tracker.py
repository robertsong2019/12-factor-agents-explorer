"""Tests for TemporalEntropyTracker — phase transition detection (Cycle 293).

Based on Research #031: Track spectral entropy over time to detect
growth / consolidation / forgetting / transition phases.
"""
import pytest, math
from memory_graph import MemoryGraph, TemporalEntropyTracker

# ─── Helpers ────────────────────────────────────────────────────────────

def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes

def build_star(g, k):
    hub = g.add('h')
    leaves = [g.add(str(i)) for i in range(k)]
    for l in leaves:
        g.link(hub.id, l.id, 'r')
    return hub, leaves


# ═══════════════════════════════════════════════════════════════════════
# Basic tracker functionality
# ═══════════════════════════════════════════════════════════════════════

class TestTrackerBasic:
    def test_create_tracker(self):
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        assert tracker.graph is mg
        assert tracker.snapshots == []

    def test_snapshot_returns_dict(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        snap = tracker.snapshot()
        assert isinstance(snap, dict)
        assert "entropy" in snap
        assert "node_count" in snap
        assert "edge_count" in snap
        assert "seq" in snap
        assert snap["seq"] == 0

    def test_multiple_snapshots_increment_seq(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        s0 = tracker.snapshot()
        s1 = tracker.snapshot()
        s2 = tracker.snapshot()
        assert s0["seq"] == 0
        assert s1["seq"] == 1
        assert s2["seq"] == 2

    def test_snapshot_with_label(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        snap = tracker.snapshot(label="initial")
        assert snap["label"] == "initial"

    def test_snapshot_records_correct_stats(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        snap = tracker.snapshot()
        assert snap["node_count"] == 4
        assert snap["edge_count"] == 3


# ═══════════════════════════════════════════════════════════════════════
# Phase detection
# ═══════════════════════════════════════════════════════════════════════

class TestPhaseDetection:
    def test_insufficient_with_no_snapshots(self):
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        assert tracker.phase() == "insufficient"

    def test_insufficient_with_one_snapshot(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        assert tracker.phase() == "insufficient"

    def test_growth_phase(self):
        """Adding nodes/edges → entropy increases → growth."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        build_path(mg, 3)
        tracker.snapshot(label="t0")
        # Add more nodes
        n3, n4 = mg.add('3'), mg.add('4')
        mg.link(n3.id, n4.id, 'r')
        mg.link(mg.conn.execute("SELECT id FROM nodes LIMIT 1 OFFSET 2").fetchone()["id"], n3.id, 'r')
        tracker.snapshot(label="t1")
        assert tracker.phase() == "growth"

    def test_consolidation_phase(self):
        """No changes → entropy stable → consolidation."""
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot(label="t0")
        tracker.snapshot(label="t1")  # same graph
        assert tracker.phase() == "consolidation"

    def test_forgetting_phase(self):
        """Removing nodes → entropy decreases → forgetting."""
        mg = MemoryGraph(':memory:')
        nodes = build_complete(mg, 5)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot(label="full")
        # Remove edges to decrease entropy
        mg.conn.execute("DELETE FROM edges WHERE rowid IN (SELECT rowid FROM edges LIMIT 6)")
        mg.conn.commit()
        tracker.snapshot(label="pruned")
        phase = tracker.phase()
        assert phase in ("forgetting", "transition")


# ═══════════════════════════════════════════════════════════════════════
# Derivatives
# ═══════════════════════════════════════════════════════════════════════

class TestDerivatives:
    def test_first_derivative_none_with_one_snapshot(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        assert tracker.first_derivative() is None

    def test_first_derivative_length_n_minus_1(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        for _ in range(5):
            tracker.snapshot()
        d1 = tracker.first_derivative()
        assert len(d1) == 4

    def test_first_derivative_flat_graph_zero(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        tracker.snapshot()
        d1 = tracker.first_derivative()
        assert abs(d1[0]) < 1e-9

    def test_first_derivative_positive_on_growth(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot(label="small")
        # Expand
        for i in range(3, 8):
            n = mg.add(str(i))
            prev = mg.conn.execute("SELECT id FROM nodes WHERE label = ?", (str(i - 1),)).fetchone()
            if prev:
                mg.link(prev["id"], n.id, 'r')
        tracker.snapshot(label="expanded")
        d1 = tracker.first_derivative()
        assert d1[-1] > 0

    def test_second_derivative_none_with_two_snapshots(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        tracker.snapshot()
        # second derivative needs >= 3 snapshots
        assert tracker.second_derivative() is None

    def test_second_derivative_length_n_minus_2(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        for _ in range(5):
            tracker.snapshot()
        d2 = tracker.second_derivative()
        assert len(d2) == 3

    def test_second_derivative_flat_zero(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        for _ in range(4):
            tracker.snapshot()
        d2 = tracker.second_derivative()
        assert all(abs(d) < 1e-9 for d in d2)


# ═══════════════════════════════════════════════════════════════════════
# Report generation
# ═══════════════════════════════════════════════════════════════════════

class TestReport:
    def test_report_keys(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        tracker.snapshot()
        report = tracker.report()
        required = {
            "snapshots", "index", "entropy_values", "entropy_normalized",
            "node_counts", "edge_counts", "first_derivative",
            "second_derivative", "current_phase", "mean_rate",
            "volatility", "labels",
        }
        assert required.issubset(report.keys())

    def test_report_snapshot_count(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        for _ in range(3):
            tracker.snapshot()
        report = tracker.report()
        assert report["snapshots"] == 3
        assert len(report["entropy_values"]) == 3

    def test_report_mean_rate(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        tracker.snapshot()
        report = tracker.report()
        assert report["mean_rate"] == 0.0  # no change

    def test_report_volatility_non_negative(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot()
        build_complete(mg, 5)  # big change
        tracker.snapshot()
        report = tracker.report()
        assert report["volatility"] >= 0

    def test_report_labels(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot(label="alpha")
        tracker.snapshot(label="beta")
        tracker.snapshot(label="gamma")
        report = tracker.report()
        assert report["labels"] == ["alpha", "beta", "gamma"]

    def test_report_index(self):
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg, index="sombor")
        assert tracker.index == "sombor"
        build_path(mg, 3)
        tracker.snapshot()
        report = tracker.report()
        assert report["index"] == "sombor"


# ═══════════════════════════════════════════════════════════════════════
# Different entropy indices
# ═══════════════════════════════════════════════════════════════════════

class TestMultipleIndices:
    def test_sombor_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="sombor")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_randic_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="randic")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_tsallis_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="tsallis")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_renyi_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="renyi")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_augmented_zagreb_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="augmented_zagreb")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_edge_betweenness_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        tracker = TemporalEntropyTracker(mg, index="edge_betweenness")
        snap = tracker.snapshot()
        assert snap["entropy"] > 0

    def test_invalid_index_raises(self):
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg, index="nonexistent")
        with pytest.raises(ValueError, match="Unknown entropy index"):
            tracker.snapshot()


# ═══════════════════════════════════════════════════════════════════════
# Transition detection
# ═══════════════════════════════════════════════════════════════════════

class TestTransitionDetection:
    def test_growth_then_consolidation_possible_transition(self):
        """Grow then stop → possible transition at inflection point."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        # Phase 1: rapid growth
        build_complete(mg, 3)
        tracker.snapshot(label="p1")
        # Phase 2: more growth
        n3 = mg.add('3')
        for nid in mg.conn.execute("SELECT id FROM nodes WHERE label != '3'").fetchall():
            mg.link(nid["id"], nid["id"], 'r')  # not useful but adds edges
        tracker.snapshot(label="p2")
        # Phase 3: stop growing
        tracker.snapshot(label="p3")
        report = tracker.report()
        # With 3 snapshots, phase should be classifiable
        assert report["current_phase"] in ("growth", "consolidation", "transition", "forgetting")

    def test_rapid_expansion_then_shrink(self):
        """Expand then shrink → should show transition or forgetting."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        # Grow
        build_complete(mg, 5)
        tracker.snapshot(label="big")
        # Shrink (remove half the edges)
        mg.conn.execute("DELETE FROM edges WHERE rowid IN (SELECT rowid FROM edges LIMIT 5)")
        mg.conn.commit()
        tracker.snapshot(label="smaller")
        # Shrink more
        mg.conn.execute("DELETE FROM edges WHERE rowid IN (SELECT rowid FROM edges LIMIT 3)")
        mg.conn.commit()
        tracker.snapshot(label="smallest")
        phase = tracker.phase()
        assert phase in ("forgetting", "transition")


# ═══════════════════════════════════════════════════════════════════════
# Realistic agent memory lifecycle
# ═══════════════════════════════════════════════════════════════════════

class TestAgentLifecycle:
    def test_learning_session_simulation(self):
        """Simulate: learn → consolidate → learn more → forget."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)

        # t0: start
        a = mg.add("Python")
        tracker.snapshot(label="start")

        # t1: learn facts
        for topic in ["async", "typing", "decorators", "generators"]:
            n = mg.add(topic)
            mg.link(a.id, n.id, "knows")
        tracker.snapshot(label="learned")

        # t2: more connections
        for topic in ["async", "typing"]:
            for extra in ["advanced", "best_practices"]:
                n = mg.add(f"{topic}_{extra}")
        tracker.snapshot(label="expanded")

        report = tracker.report()
        assert report["snapshots"] == 3
        assert len(report["entropy_values"]) == 3
        # Entropy should have changed
        assert report["entropy_values"][0] != report["entropy_values"][-1]

    def test_empty_graph_snapshots(self):
        """Tracker on empty graph should still work."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        tracker.snapshot(label="empty")
        tracker.snapshot(label="still_empty")
        report = tracker.report()
        assert report["current_phase"] == "consolidation"  # no change
        assert report["entropy_values"] == [0.0, 0.0]

    def test_snapshots_track_node_count(self):
        """Node count in snapshots should match graph state at each point."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        build_path(mg, 3)
        tracker.snapshot(label="3nodes")
        assert tracker.snapshots[-1]["node_count"] == 3

        n3 = mg.add('extra')
        tracker.snapshot(label="4nodes")
        assert tracker.snapshots[-1]["node_count"] == 4

    def test_snapshots_track_edge_count(self):
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        a, b = mg.add('a'), mg.add('b')
        mg.link(a.id, b.id, 'r')
        tracker.snapshot(label="1edge")
        assert tracker.snapshots[-1]["edge_count"] == 1

        c = mg.add('c')
        mg.link(b.id, c.id, 'r')
        tracker.snapshot(label="2edges")
        assert tracker.snapshots[-1]["edge_count"] == 2

    def test_entropy_increases_monotonically_with_complete_growth(self):
        """Building up K_n → entropy should trend upward."""
        mg = MemoryGraph(':memory:')
        tracker = TemporalEntropyTracker(mg)
        for n_total in range(3, 8):
            n = mg.add(str(n_total))
            for existing in mg.conn.execute(
                "SELECT id FROM nodes WHERE id != ?", (n.id,)
            ).fetchall():
                mg.link(n.id, existing["id"], 'r')
            tracker.snapshot()
        ents = [s["entropy"] for s in tracker.snapshots]
        for i in range(len(ents) - 1):
            assert ents[i] <= ents[i + 1] + 1e-9
