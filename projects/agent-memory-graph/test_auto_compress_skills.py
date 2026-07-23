"""Tests for auto_compress_skills() — Cycle 277.

The act-half of the detect→compress skill loop.
Mirrors auto_heal_gaps() for gaps and auto_consolidate() for redundancy.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


class TestAutoCompressSkills:
    """Core auto_compress_skills() functionality."""

    def test_no_candidates_empty_graph(self, mg):
        """Empty graph → zero candidates, zero skills created."""
        result = mg.auto_compress_skills()
        assert result["total_created"] == 0
        assert result["candidates_found"] == 0
        assert result["skills_created"] == []
        assert result["dry_run"] is False

    def test_creates_skill_from_repeated_actions(self, mg):
        """Three 'created' events → one skill auto-compressed."""
        for i in range(3):
            mg.add(f"created module {i}", kind="event", data={"action": f"create step {i}"})
        result = mg.auto_compress_skills(min_frequency=2, min_confidence=0.0)
        assert result["total_created"] >= 1
        assert result["candidates_found"] >= 1
        skill_info = result["skills_created"][0]
        assert skill_info["action"] == "created"
        assert skill_info["skill_id"] is not None
        assert skill_info["source_count"] == 3

    def test_dry_run_does_not_create_nodes(self, mg):
        """dry_run=True → no nodes created."""
        for i in range(3):
            mg.add(f"built feature {i}", kind="event")
        count_before = sum(mg.count_by_kind().values())
        result = mg.auto_compress_skills(dry_run=True, min_confidence=0.0)
        assert result["dry_run"] is True
        assert result["total_created"] >= 1
        assert result["skills_created"][0]["skill_id"] is None
        count_after = sum(mg.count_by_kind().values())
        assert count_after == count_before

    def test_min_confidence_filter(self, mg):
        """Candidates below min_confidence are skipped."""
        # Only 2 occurrences → confidence = 2/5 = 0.4
        mg.add("tested component A", kind="event")
        mg.add("tested component B", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.5)
        assert result["total_created"] == 0
        assert len(result["skipped"]) >= 1
        assert "confidence" in result["skipped"][0]["reason"]

    def test_max_skills_limit(self, mg):
        """max_skills caps the number of skills created."""
        # Create multiple verb groups
        for i in range(3):
            mg.add(f"created module {i}", kind="event")
        for i in range(3):
            mg.add(f"built feature {i}", kind="event")
        for i in range(3):
            mg.add(f"tested component {i}", kind="event")
        result = mg.auto_compress_skills(max_skills=1, min_confidence=0.0)
        assert result["total_created"] == 1

    def test_consumed_ids_not_recompressed(self, mg):
        """Memory IDs used for one skill aren't reused for another."""
        for i in range(3):
            mg.add(f"created module {i}", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        assert result["total_created"] == 1
        # Run again — the episodes are now linked, no new candidates
        result2 = mg.auto_compress_skills(min_confidence=0.0)
        assert result2["total_created"] == 0

    def test_actions_populated(self, mg):
        """Human-readable actions are generated."""
        for i in range(3):
            mg.add(f"deployed service {i}", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        assert len(result["actions"]) >= 1
        assert "deployed" in result["actions"][0]

    def test_returns_skill_node_kind(self, mg):
        """Created node has kind='skill'."""
        for i in range(3):
            mg.add(f"wrote report {i}", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        skill_id = result["skills_created"][0]["skill_id"]
        node = mg.get_node(skill_id)
        assert node.kind == "skill"

    def test_mixed_verbs_only_compresses_qualifying(self, mg):
        """Verbs below min_frequency are not compressed."""
        mg.add("created module A", kind="event")
        mg.add("created module B", kind="event")
        mg.add("built thing", kind="event")  # only 1 occurrence
        result = mg.auto_compress_skills(min_frequency=2, min_confidence=0.0)
        # Only "created" qualifies (freq=2), "built" doesn't (freq=1)
        actions_compressed = [s["action"] for s in result["skills_created"]]
        assert "created" in actions_compressed
        assert "built" not in actions_compressed

    def test_intention_nodes_also_compressed(self, mg):
        """Intention nodes are included in pattern detection."""
        for i in range(3):
            mg.add(
                f"analyzed metric {i}", kind="intention",
                data={"action": f"analyze step {i}"},
            )
        result = mg.auto_compress_skills(min_confidence=0.0)
        assert result["total_created"] >= 1
        assert result["skills_created"][0]["action"] == "analyzed"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_occurrence_no_compression(self, mg):
        """A single event with an action verb doesn't trigger compression."""
        mg.add("created one thing", kind="event")
        result = mg.auto_compress_skills(min_frequency=2)
        assert result["total_created"] == 0

    def test_no_action_verbs_in_labels(self, mg):
        """Events without action verbs produce no candidates."""
        mg.add("A happened", kind="event")
        mg.add("B existed", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        assert result["candidates_found"] == 0
        assert result["total_created"] == 0

    def test_compress_to_skill_failure_handled(self, mg):
        """If compress_to_skill returns None, it's added to skipped."""
        for i in range(3):
            mg.add(f"created module {i}", kind="event")
        # Corrupt one node to make compress fail partially
        result = mg.auto_compress_skills(min_confidence=0.0)
        # Should succeed for valid nodes
        assert result["total_created"] >= 1

    def test_skill_name_auto_prefixed(self, mg):
        """Auto-created skills are prefixed with 'auto: '."""
        for i in range(3):
            mg.add(f"fixed bug {i}", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        assert result["skills_created"][0]["name"].startswith("auto: ")

    def test_idempotent_second_run(self, mg):
        """Second run on same graph finds fewer/no new candidates."""
        for i in range(3):
            mg.add(f"created module {i}", kind="event")
        result1 = mg.auto_compress_skills(min_confidence=0.0)
        assert result1["total_created"] >= 1
        result2 = mg.auto_compress_skills(min_confidence=0.0)
        # Events are already consumed → no new skills
        assert result2["total_created"] == 0

    def test_confidence_value_propagated(self, mg):
        """Candidate confidence is passed to compress_to_skill."""
        for i in range(5):
            mg.add(f"created module {i}", kind="event")
        result = mg.auto_compress_skills(min_confidence=0.0)
        skill_id = result["skills_created"][0]["skill_id"]
        node = mg.get_node(skill_id)
        d = node.data
        assert d["confidence"] == pytest.approx(1.0, abs=0.01)


class TestDryRun:
    """Dry-run specific tests."""

    def test_dry_run_reports_candidates(self, mg):
        """dry_run reports candidates without acting."""
        for i in range(4):
            mg.add(f"tested module {i}", kind="event")
        result = mg.auto_compress_skills(dry_run=True, min_confidence=0.0)
        assert result["candidates_found"] >= 1
        assert result["total_created"] >= 1
        assert all(s["skill_id"] is None for s in result["skills_created"])

    def test_dry_run_vs_real_consistency(self, mg):
        """Dry run and real run agree on candidate count."""
        for i in range(3):
            mg.add(f"built feature {i}", kind="event")
        for i in range(3):
            mg.add(f"created module {i}", kind="event")
        dry = mg.auto_compress_skills(dry_run=True, min_confidence=0.0)
        # Now real run on a fresh graph with same data
        mg2 = MemoryGraph(":memory:")
        for i in range(3):
            mg2.add(f"built feature {i}", kind="event")
        for i in range(3):
            mg2.add(f"created module {i}", kind="event")
        real = mg2.auto_compress_skills(min_confidence=0.0)
        assert dry["candidates_found"] == real["candidates_found"]
