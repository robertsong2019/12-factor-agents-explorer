"""Tests for prospective memory — PM-Bench-inspired delayed intentions.

PM-Bench (arXiv:2607.12385, COLM 2026): GPT-5.4 only 65.1% F1 on
prospective memory tasks. Tests add_intention, check_prospective_cues,
fulfill_intention, and pending_intentions.
"""

import pytest
import json
import time as _time
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


# ─── add_intention ──────────────────────────────────────────────────────

class TestAddIntention:
    """Tests for add_intention()."""

    def test_creates_intention_node(self, mg):
        n = mg.add_intention("Remind about deploy", trigger="deploying",
                              action="check configs")
        assert n.kind == "intention"
        assert n.data["trigger"] == "deploying"
        assert n.data["action"] == "check configs"
        assert n.data["status"] == "pending"

    def test_default_status_pending(self, mg):
        n = mg.add_intention("Test intention")
        assert n.data["status"] == "pending"

    def test_priority_stored(self, mg):
        n = mg.add_intention("Urgent task", priority="high")
        assert n.data["priority"] == "high"

    def test_default_priority_normal(self, mg):
        n = mg.add_intention("Normal task")
        assert n.data["priority"] == "normal"

    def test_deadline_stored(self, mg):
        deadline = _time.time() + 3600
        n = mg.add_intention("Time-limited", deadline=deadline)
        assert n.data["deadline"] == deadline

    def test_tags_include_prospective(self, mg):
        n = mg.add_intention("Test")
        row = mg.conn.execute("SELECT tags FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert "prospective" in json.loads(row["tags"])

    def test_data_preserved(self, mg):
        n = mg.add_intention("Custom", data={"custom_key": "val"},
                              trigger="go")
        assert n.data["custom_key"] == "val"
        assert n.data["trigger"] == "go"

    def test_minimal_args(self, mg):
        """Only label required."""
        n = mg.add_intention("Simple")
        assert n is not None
        assert n.label == "Simple"

    def test_trigger_action_in_data(self, mg):
        n = mg.add_intention("Deploy check", trigger="production deploy",
                              action="run smoke tests")
        assert "trigger" in n.data
        assert "action" in n.data


# ─── check_prospective_cues ────────────────────────────────────────────

class TestCheckProspectiveCues:
    """Tests for check_prospective_cues()."""

    def test_match_found(self, mg):
        mg.add_intention("Deploy reminder", trigger="deploying to production",
                         action="check configs")
        results = mg.check_prospective_cues("starting deploying to production now")
        assert len(results) >= 1
        assert results[0]["score"] > 0

    def test_no_match(self, mg):
        mg.add_intention("Deploy reminder", trigger="deploying to production")
        results = mg.check_prospective_cues("making pasta for dinner")
        assert len(results) == 0

    def test_no_pending(self, mg):
        """No intentions → empty list."""
        assert mg.check_prospective_cues("anything") == []

    def test_multiple_matches_sorted(self, mg):
        mg.add_intention("A", trigger="python coding")
        mg.add_intention("B", trigger="python rust java")
        results = mg.check_prospective_cues("python coding session")
        # Both should match; higher overlap scores first
        assert len(results) >= 1
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_deadline_urgent(self, mg):
        """Deadline within 1 hour → urgent status."""
        now = _time.time()
        mg.add_intention("Urgent task", trigger="unrelated_trigger_xyz",
                         deadline=now + 1800)  # 30 min
        results = mg.check_prospective_cues("checking stuff", now=now)
        assert any(r["deadline_status"] == "urgent" for r in results)

    def test_deadline_expired(self, mg):
        """Past deadline → expired + status set to missed."""
        past = _time.time() - 100
        mg.add_intention("Past task", trigger="something_unique_xyz",
                         deadline=past)
        results = mg.check_prospective_cues("something_unique_xyz")
        assert any(r["deadline_status"] == "expired" for r in results)
        # Verify status changed to missed in DB
        row = mg.conn.execute(
            "SELECT data FROM nodes WHERE kind='intention'"
        ).fetchone()
        assert json.loads(row["data"])["status"] == "missed"

    def test_deadline_soon(self, mg):
        """Deadline within 24h → soon status."""
        now = _time.time()
        mg.add_intention("Soon task", trigger="trigger_soon_test",
                         deadline=now + 7200)  # 2 hours
        results = mg.check_prospective_cues("trigger_soon_test", now=now)
        assert any(r["deadline_status"] == "soon" for r in results)

    def test_deadline_future(self, mg):
        """Deadline far away → future status."""
        now = _time.time()
        mg.add_intention("Future task", trigger="trigger_future_test",
                         deadline=now + 86400 * 7)  # 1 week
        results = mg.check_prospective_cues("trigger_future_test", now=now)
        assert any(r["deadline_status"] == "future" for r in results)

    def test_priority_sorting(self, mg):
        """When scores equal, high priority first."""
        mg.add_intention("Low", trigger="shared trigger word",
                        priority="low")
        mg.add_intention("High", trigger="shared trigger word",
                        priority="high")
        results = mg.check_prospective_cues("shared trigger word")
        if len(results) >= 2 and results[0]["score"] == results[1]["score"]:
            assert results[0]["priority"] == "high"

    def test_result_fields(self, mg):
        mg.add_intention("Test", trigger="meeting", action="take notes")
        results = mg.check_prospective_cues("starting meeting now")
        assert len(results) >= 1
        r = results[0]
        assert "node_id" in r
        assert "label" in r
        assert "trigger" in r
        assert "action" in r
        assert "score" in r
        assert "priority" in r
        assert "deadline_status" in r

    def test_no_trigger_keyword(self, mg):
        """Intention without trigger → no keyword match."""
        mg.add_intention("No trigger intention")
        results = mg.check_prospective_cues("anything at all")
        # No trigger → score 0 and no deadline → not included
        assert len(results) == 0

    def test_fulfilled_not_returned(self, mg):
        """Fulfilled intentions should not be returned."""
        n = mg.add_intention("Done task", trigger="completed_trigger")
        mg.fulfill_intention(n.id)
        results = mg.check_prospective_cues("completed_trigger")
        assert len(results) == 0

    def test_now_override(self, mg):
        """now parameter controls deadline evaluation."""
        now = _time.time()
        mg.add_intention("Future", trigger="unique_future_trigger",
                        deadline=now + 100000)
        results = mg.check_prospective_cues("unique_future_trigger", now=now)
        assert any(r["deadline_status"] == "future" for r in results)


# ─── fulfill_intention ─────────────────────────────────────────────────

class TestFulfillIntention:
    """Tests for fulfill_intention()."""

    def test_fulfill_changes_status(self, mg):
        n = mg.add_intention("Test task")
        assert mg.fulfill_intention(n.id) is True
        node = mg.get_node(n.id)
        assert node.data["status"] == "fulfilled"

    def test_fulfill_sets_timestamp(self, mg):
        n = mg.add_intention("Test task")
        mg.fulfill_intention(n.id)
        node = mg.get_node(n.id)
        assert "fulfilled_at" in node.data

    def test_fulfill_nonexistent(self, mg):
        assert mg.fulfill_intention("nonexistent") is False

    def test_fulfill_non_intention(self, mg):
        """Fulfilling a non-intention node → False."""
        n = mg.add("Regular node", "fact")
        assert mg.fulfill_intention(n.id) is False

    def test_fulfill_twice_idempotent(self, mg):
        """Double fulfillment → still returns True (already fulfilled)."""
        n = mg.add_intention("Test")
        assert mg.fulfill_intention(n.id) is True
        assert mg.fulfill_intention(n.id) is True
        node = mg.get_node(n.id)
        assert node.data["status"] == "fulfilled"


# ─── pending_intentions ────────────────────────────────────────────────

class TestPendingIntentions:
    """Tests for pending_intentions()."""

    def test_empty(self, mg):
        assert mg.pending_intentions() == []

    def test_lists_pending(self, mg):
        n1 = mg.add_intention("Task 1", trigger="t1")
        n2 = mg.add_intention("Task 2", trigger="t2")
        pending = mg.pending_intentions()
        assert len(pending) == 2

    def test_excludes_fulfilled(self, mg):
        n1 = mg.add_intention("Task 1")
        mg.add_intention("Task 2")
        mg.fulfill_intention(n1.id)
        pending = mg.pending_intentions()
        assert len(pending) == 1
        assert pending[0]["label"] == "Task 2"

    def test_include_expired(self, mg):
        """include_expired=True includes missed."""
        past = _time.time() - 100
        n = mg.add_intention("Expired", trigger="trigger_expired_test",
                             deadline=past)
        mg.check_prospective_cues("trigger_expired_test")  # marks as missed
        pending = mg.pending_intentions(include_expired=True)
        assert len(pending) >= 1
        statuses = [p["status"] for p in pending]
        assert "missed" in statuses

    def test_exclude_expired_by_default(self, mg):
        """Default excludes missed."""
        past = _time.time() - 100
        n = mg.add_intention("Expired", trigger="trigger_exclude_test",
                             deadline=past)
        mg.check_prospective_cues("trigger_exclude_test")
        pending = mg.pending_intentions()
        assert len(pending) == 0

    def test_result_fields(self, mg):
        mg.add_intention("Task", trigger="t", action="a", priority="high")
        pending = mg.pending_intentions()
        p = pending[0]
        assert "node_id" in p
        assert "label" in p
        assert "trigger" in p
        assert "action" in p
        assert "priority" in p
        assert "status" in p

    def test_sorted_by_created_desc(self, mg):
        """Most recent first."""
        mg.add_intention("Old")
        _time.sleep(0.01)
        mg.add_intention("New")
        pending = mg.pending_intentions()
        labels = [p["label"] for p in pending]
        assert labels.index("New") < labels.index("Old")


# ─── Integration ────────────────────────────────────────────────────────

class TestProspectiveIntegration:
    """Integration tests for the full prospective memory flow."""

    def test_full_lifecycle(self, mg):
        """Add → check → fulfill → verify excluded."""
        # 1. Add intention (far deadline so it doesn't trigger on urgency)
        n = mg.add_intention("Deploy check", trigger="production deploy",
                              action="verify configs",
                              deadline=_time.time() + 86400 * 7)
        assert n.data["status"] == "pending"

        # 2. Check with non-matching context
        results = mg.check_prospective_cues("making dinner")
        assert len(results) == 0

        # 3. Check with matching context
        results = mg.check_prospective_cues("starting production deploy now")
        assert len(results) == 1
        assert results[0]["label"] == "Deploy check"

        # 4. Fulfill
        assert mg.fulfill_intention(n.id) is True

        # 5. Verify excluded from pending
        assert mg.pending_intentions() == []

    def test_multiple_intentions_different_triggers(self, mg):
        mg.add_intention("Code review", trigger="pull request merge")
        mg.add_intention("Deploy", trigger="production deploy")
        mg.add_intention("Dinner", trigger="cooking recipe")

        # Only deploy matches
        results = mg.check_prospective_cues("running production deploy")
        labels = [r["label"] for r in results]
        assert "Deploy" in labels
        assert "Code review" not in labels
        assert "Dinner" not in labels

    def test_intention_with_governance_check(self, mg):
        """Intentions can be governance-checked like any node."""
        n = mg.add_intention("Deploy task", trigger="deploy signal")
        # Benign rename (no sycophantic pattern)
        gov = mg.write_governance_check(
            n.id, new_label="Deploy task with signal")
        assert gov["verdict"] == "safe"

    def test_intention_retrieval_via_recall(self, mg):
        """Intentions are retrievable via recall()."""
        mg.add_intention("Important deploy task", trigger="deploy")
        results = mg.recall("deploy")
        assert any("deploy" in r.label.lower() for r in results)
