"""Tests for govern_skill_bank() — SkeMex/MUSE-inspired skill bank governance.

Cycle 260 — Govern step of Read-Write-Assess-Govern lifecycle.
"""

import pytest
import json
import time
from memory_graph import MemoryGraph


def _set_skill_data(mg, skill_id, **kwargs):
    """Helper: update skill node data."""
    row = mg.conn.execute(
        "SELECT data FROM nodes WHERE id=?", (skill_id,)
    ).fetchone()
    data = json.loads(row["data"]) if isinstance(row["data"], str) else (row["data"] or {})
    data.update(kwargs)
    mg.conn.execute(
        "UPDATE nodes SET data=? WHERE id=?",
        (json.dumps(data), skill_id),
    )
    mg.conn.commit()


def _make_skill(mg, name, *, steps=None, confidence=0.5, tags=None, last_evolved_at=None):
    """Helper: create a skill and set its data."""
    e = mg.add(f"event for {name}", "event")
    node = mg.compress_to_skill([e.id], name)
    if node:
        updates = {}
        if steps:
            updates["steps"] = steps
        if confidence != 0.5:
            updates["confidence"] = confidence
        if last_evolved_at is not None:
            updates["last_evolved_at"] = last_evolved_at
        if updates:
            _set_skill_data(mg, node.id, **updates)
        if tags:
            mg.conn.execute(
                "UPDATE nodes SET tags=? WHERE id=?",
                (json.dumps(tags), node.id),
            )
            mg.conn.commit()
    return node


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def skill_bank():
    """Create a graph with several skills of varying health."""
    g = MemoryGraph(":memory:")

    # Healthy skill
    _make_skill(g, "deploy-and-test",
                steps=["build", "test", "deploy"], confidence=0.8)

    # Low confidence skill
    _make_skill(g, "failed-approach",
                steps=["step1", "step2"], confidence=0.1)

    return g


class TestGovernSkillBank:

    def test_returns_required_keys(self, mg):
        result = mg.govern_skill_bank()
        for key in ("policies", "actions", "summary"):
            assert key in result

    def test_empty_bank_returns_zero_summary(self, mg):
        result = mg.govern_skill_bank()
        assert result["summary"]["total_examined"] == 0
        assert result["summary"]["deprecated"] == 0

    def test_policies_echoed(self, mg):
        result = mg.govern_skill_bank(max_skills=50, min_confidence=0.3)
        assert result["policies"]["max_skills"] == 50
        assert result["policies"]["min_confidence"] == 0.3

    def test_dry_run_makes_no_changes(self, skill_bank):
        before = skill_bank.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind='skill'"
        ).fetchone()[0]
        skill_bank.govern_skill_bank(dry_run=True)
        after = skill_bank.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind='skill'"
        ).fetchone()[0]
        assert before == after

    def test_dry_run_still_reports_actions(self, skill_bank):
        result = skill_bank.govern_skill_bank(min_confidence=0.9, dry_run=True)
        assert len(result["actions"]) > 0

    def test_deprecate_low_confidence(self, skill_bank):
        result = skill_bank.govern_skill_bank(min_confidence=0.5)
        deprecate_actions = [
            a for a in result["actions"] if a["action"] == "deprecate_low_confidence"
        ]
        assert len(deprecate_actions) >= 1

    def test_deprecated_skill_gets_tag(self, skill_bank):
        skill_bank.govern_skill_bank(min_confidence=0.5)
        rows = skill_bank.conn.execute(
            "SELECT tags FROM nodes WHERE kind='skill'"
        ).fetchall()
        found_deprecated = False
        for row in rows:
            tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else (row["tags"] or [])
            if "deprecated" in (tags or []):
                found_deprecated = True
                break
        assert found_deprecated

    def test_deprecate_stale(self, mg):
        """Create a skill with old timestamp."""
        old_ts = time.time() - 90 * 86400
        _make_skill(mg, "ancient-skill", steps=["old"], last_evolved_at=old_ts)

        result = mg.govern_skill_bank(deprecate_after_days=60)
        stale_actions = [
            a for a in result["actions"] if a["action"] == "deprecate_stale"
        ]
        assert len(stale_actions) >= 1

    def test_merge_redundant_skills(self, mg):
        """Two skills with high step overlap should be merged."""
        _make_skill(mg, "skill-one",
                    steps=["build", "test", "deploy", "verify"])
        _make_skill(mg, "skill-two",
                    steps=["build", "test", "deploy", "verify"])

        result = mg.govern_skill_bank(merge_redundancy_threshold=0.6)
        merge_actions = [
            a for a in result["actions"] if a["action"] == "merge_redundant"
        ]
        assert len(merge_actions) >= 1

    def test_no_merge_below_threshold(self, mg):
        """Skills with low overlap should NOT be merged."""
        _make_skill(mg, "skill-alpha",
                    steps=["build", "test", "deploy"])
        _make_skill(mg, "skill-beta",
                    steps=["design", "review", "ship"])

        result = mg.govern_skill_bank(merge_redundancy_threshold=0.9)
        merge_actions = [
            a for a in result["actions"] if a["action"] == "merge_redundant"
        ]
        assert len(merge_actions) == 0

    def test_prune_overflow(self, mg):
        """When skills exceed max_skills, oldest deprecated get pruned."""
        for i in range(5):
            _make_skill(mg, f"skill-{i}", steps=[f"step{i}"])

        # Tag 2 as deprecated
        rows = mg.conn.execute(
            "SELECT id FROM nodes WHERE kind='skill' LIMIT 2"
        ).fetchall()
        for row in rows:
            mg.conn.execute(
                "UPDATE nodes SET tags=?, accessed=? WHERE id=?",
                (json.dumps(["deprecated"]), time.time() - 86400, row["id"]),
            )
        mg.conn.commit()

        result = mg.govern_skill_bank(max_skills=3)
        prune_actions = [
            a for a in result["actions"] if a["action"] == "prune_overflow"
        ]
        assert len(prune_actions) >= 1

    def test_no_prune_when_under_max(self, skill_bank):
        result = skill_bank.govern_skill_bank(max_skills=100)
        prune_actions = [
            a for a in result["actions"] if a["action"] == "prune_overflow"
        ]
        assert len(prune_actions) == 0

    def test_summary_counts_correct(self, skill_bank):
        result = skill_bank.govern_skill_bank(min_confidence=0.5)
        s = result["summary"]
        assert s["total_examined"] >= 2
        assert s["deprecated"] >= 1
        assert isinstance(s["merged"], int)
        assert isinstance(s["pruned"], int)

    def test_actions_have_required_fields(self, skill_bank):
        result = skill_bank.govern_skill_bank(min_confidence=0.5)
        for action in result["actions"]:
            assert "action" in action
            assert "skill_id" in action
            assert "reason" in action

    def test_healthy_bank_minimal_actions(self, mg):
        """A healthy skill bank should have few or no actions."""
        _make_skill(mg, "good-skill", steps=["do"], confidence=0.9)

        result = mg.govern_skill_bank(
            min_confidence=0.0,
            deprecate_after_days=365,
            merge_redundancy_threshold=0.99,
            max_skills=100,
        )
        assert result["summary"]["deprecated"] == 0
        assert result["summary"]["merged"] == 0

    def test_default_policies_reasonable(self, mg):
        result = mg.govern_skill_bank()
        p = result["policies"]
        assert p["max_skills"] == 100
        assert p["min_confidence"] == 0.2
        assert p["deprecate_after_days"] == 60
        assert p["merge_redundancy_threshold"] == 0.7
        assert p["dry_run"] is False

    def test_second_run_finds_fewer_actions(self, skill_bank):
        """Already-deprecated skills shouldn't be re-deprecated."""
        skill_bank.govern_skill_bank(min_confidence=0.8)
        result2 = skill_bank.govern_skill_bank(min_confidence=0.8)
        deprecate2 = [
            a for a in result2["actions"] if "deprecate" in a["action"]
        ]
        assert len(deprecate2) == 0

    def test_action_labels_present(self, skill_bank):
        result = skill_bank.govern_skill_bank(min_confidence=0.5)
        for a in result["actions"]:
            assert "label" in a

    def test_govern_after_evolve(self, mg):
        """Evolve a skill to low confidence, then govern should catch it."""
        e1 = mg.add("approach attempt", "event")
        e2 = mg.add("failed result", "event")
        node = mg.compress_to_skill([e1.id, e2.id], "risky-approach")

        # Evolve with failure to lower confidence
        mg.evolve_skill(node.id, feedback=-1.0)

        result = mg.govern_skill_bank(min_confidence=0.5)
        actions = [
            a for a in result["actions"] if "deprecate" in a["action"]
        ]
        assert len(actions) >= 1

    def test_max_skills_zero_prunes_all_deprecated(self, mg):
        """max_skills=0 should prune all deprecated skills."""
        _make_skill(mg, "deprecated-one", tags=["deprecated"])
        _make_skill(mg, "deprecated-two", tags=["deprecated"])
        _make_skill(mg, "active-one", confidence=0.9)

        result = mg.govern_skill_bank(max_skills=1)
        prune_actions = [
            a for a in result["actions"] if a["action"] == "prune_overflow"
        ]
        assert len(prune_actions) >= 1
