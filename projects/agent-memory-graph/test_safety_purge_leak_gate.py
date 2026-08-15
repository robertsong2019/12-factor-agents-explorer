"""Tests for safety_purge × cross-modal leak gate — Cycle 444.

forget_policy("safety_purge") must not silently purge sensitive nodes
whose derivatives (image captions, summaries, inferences) still carry
their sensitive tokens — those nodes are blocked and reported as
``blocked_by_leak`` so derivatives can be scrubbed first.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def purge_graph():
    """Two sensitive nodes: one leaky (derivative), one clean."""
    g = MemoryGraph()
    import time
    old = time.time() - 90 * 86400  # 90 days stale → low activation
    leaky = g.add("SSN record 123-4567 for Alice",
                  kind="sensitive", data={"note": "ssn 123-4567"})
    clean = g.add("expired api key", kind="sensitive")
    deriv = g.add("screenshot caption: SSN record 123-4567",
                  kind="image")
    g.link(leaky.id, deriv.id, "image_derived")
    for nid in (leaky.id, clean.id):
        g.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                       (old, nid))
    g.conn.commit()
    g._ids = {"leaky": leaky.id, "clean": clean.id, "deriv": deriv.id}
    return g


# ── leak gate behavior ──

class TestSafetyPurgeLeakGate:

    def test_leaky_sensitive_node_blocked(self, purge_graph):
        result = purge_graph.forget_policy("safety_purge")
        assert result.get("blocked_by_leak"), "leaky node must be blocked"
        blocked_ids = {b["id"] for b in result["blocked_by_leak"]}
        assert purge_graph._ids["leaky"] in blocked_ids

    def test_blocked_node_survives(self, purge_graph):
        purge_graph.forget_policy("safety_purge")
        assert purge_graph.get_node(purge_graph._ids["leaky"]) is not None

    def test_clean_sensitive_node_purged(self, purge_graph):
        result = purge_graph.forget_policy("safety_purge")
        assert purge_graph.get_node(purge_graph._ids["clean"]) is None

    def test_blocked_report_includes_derivatives(self, purge_graph):
        result = purge_graph.forget_policy("safety_purge")
        entry = result["blocked_by_leak"][0]
        assert entry["derivatives"], "must list leaky derivatives"
        assert entry["derivatives"][0]["derived_id"] == purge_graph._ids["deriv"]

    def test_blocked_report_includes_token_count(self, purge_graph):
        result = purge_graph.forget_policy("safety_purge")
        entry = result["blocked_by_leak"][0]
        assert entry["leak_token_count"] >= 1

    def test_after_scrubbing_derivative_purge_completes(self, purge_graph):
        """Scrub derivative → purge no longer blocked."""
        purge_graph.update_node(purge_graph._ids["deriv"],
                                label="screenshot [redacted]",
                                data={"caption": "[redacted]"})
        result = purge_graph.forget_policy("safety_purge")
        assert not result.get("blocked_by_leak")
        assert purge_graph.get_node(purge_graph._ids["leaky"]) is None

    def test_dry_run_skips_gate(self, purge_graph):
        """dry_run must not mutate anything nor report blocks."""
        result = purge_graph.forget_policy("safety_purge", dry_run=True)
        assert "blocked_by_leak" not in result
        assert purge_graph.get_node(purge_graph._ids["leaky"]) is not None
        assert purge_graph.get_node(purge_graph._ids["clean"]) is not None


# ── other policies unaffected ──

class TestOtherPoliciesUnaffected:

    def test_passive_decay_no_gate(self):
        g = MemoryGraph()
        import time
        old = time.time() - 90 * 86400
        n = g.add("SSN 999-8888 record", kind="sensitive")
        d = g.add("caption: SSN 999-8888", kind="image")
        g.link(n.id, d.id, "image_derived")
        g.conn.execute("UPDATE nodes SET created=? WHERE id=?", (old, n.id))
        g.conn.commit()
        result = g.forget_policy("passive_decay")
        assert "blocked_by_leak" not in result  # gate is safety_purge-only

    def test_active_deletion_no_gate(self, purge_graph):
        result = purge_graph.forget_policy("active_deletion")
        assert "blocked_by_leak" not in result


# ── apply_decay exclude_ids ──

class TestApplyDecayExcludeIds:

    def test_exclude_ids_skips_nodes(self, purge_graph):
        result = purge_graph.apply_decay(
            half_life_days=1.0, kinds=["sensitive"], dry_run=True,
            delete_threshold=0.5, archive_threshold=0.7,
            exclude_ids=[purge_graph._ids["leaky"]])
        # leaky skipped: scanned must be 1 (only clean)
        assert result["scanned"] == 1

    def test_exclude_accepts_list_or_set(self, purge_graph):
        r1 = purge_graph.apply_decay(
            kinds=["sensitive"], dry_run=True, delete_threshold=0.5,
            archive_threshold=0.7,
            exclude_ids=[purge_graph._ids["leaky"]])
        r2 = purge_graph.apply_decay(
            kinds=["sensitive"], dry_run=True, delete_threshold=0.5,
            archive_threshold=0.7,
            exclude_ids={purge_graph._ids["leaky"]})
        assert r1["scanned"] == r2["scanned"] == 1

    def test_exclude_none_scans_all(self, purge_graph):
        result = purge_graph.apply_decay(
            kinds=["sensitive"], dry_run=True, delete_threshold=0.5,
            archive_threshold=0.7, exclude_ids=None)
        assert result["scanned"] == 2

    def test_excluded_node_untouched_in_real_run(self, purge_graph):
        purge_graph.apply_decay(
            half_life_days=1.0, kinds=["sensitive"], dry_run=False,
            delete_threshold=0.5, archive_threshold=0.7,
            exclude_ids=[purge_graph._ids["leaky"]])
        assert purge_graph.get_node(purge_graph._ids["leaky"]) is not None
        assert purge_graph.get_node(purge_graph._ids["clean"]) is None


# ── gate internals ──

class TestGateInternals:

    def test_preview_runs_before_real_purge(self, purge_graph):
        """Gate must not delete blocked nodes during preview phase."""
        result = purge_graph.forget_policy("safety_purge")
        # leaky survived the whole pipeline
        assert purge_graph.get_node(purge_graph._ids["leaky"]) is not None
        # and clean was deleted in the real run
        assert result["deleted"] >= 1

    def test_multiple_blocked_nodes(self):
        import time
        g = MemoryGraph()
        old = time.time() - 90 * 86400
        ids = []
        for i in range(3):
            n = g.add(f"SSN record 555-000{i} Alice", kind="sensitive")
            d = g.add(f"caption: SSN record 555-000{i}", kind="image")
            g.link(n.id, d.id, "image_derived")
            g.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                           (old, n.id))
            ids.append(n.id)
        g.conn.commit()
        result = g.forget_policy("safety_purge")
        blocked = {b["id"] for b in result.get("blocked_by_leak", [])}
        assert blocked == set(ids)

    def test_no_sensitive_kinds_no_gate_trigger(self):
        g = MemoryGraph()
        result = g.forget_policy("safety_purge")
        assert not result.get("blocked_by_leak")
