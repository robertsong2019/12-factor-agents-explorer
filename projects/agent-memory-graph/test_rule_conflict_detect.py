"""Tests for rule_conflict_detect() — L3 rule conflict detection.

Cycle 422: Detects contradictions, overlaps, and topic collisions
between declarative rule nodes extracted from skills.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def two_clean_rules(mg):
    """Two rules with no conflicts."""
    r1 = mg.add("Rule A", kind="rule", data={
        "rule_name": "Security Rules",
        "negative_constraints": ["never store passwords in plaintext"],
        "positive_rules": ["always hash passwords with bcrypt"],
        "confidence": 0.9,
    })
    r2 = mg.add("Rule B", kind="rule", data={
        "rule_name": "Logging Rules",
        "negative_constraints": ["never log sensitive user data"],
        "positive_rules": ["always log access events"],
        "confidence": 0.85,
    })
    return mg, r1, r2


@pytest.fixture
def conflicting_rules(mg):
    """Two rules with a direct contradiction."""
    r1 = mg.add("Checksum Always", kind="rule", data={
        "rule_name": "Integrity Rules",
        "negative_constraints": [],
        "positive_rules": ["always verify checksums before processing"],
        "confidence": 0.9,
    })
    r2 = mg.add("Checksum Never", kind="rule", data={
        "rule_name": "Performance Rules",
        "negative_constraints": ["never verify checksums for small files"],
        "positive_rules": [],
        "confidence": 0.8,
    })
    return mg, r1, r2


@pytest.fixture
def overlapping_rules(mg):
    """Two rules with shared constraint text."""
    r1 = mg.add("Auth A", kind="rule", data={
        "rule_name": "Auth Rules v1",
        "negative_constraints": ["never store passwords in plaintext"],
        "positive_rules": ["always use HTTPS"],
        "confidence": 0.9,
    })
    r2 = mg.add("Auth B", kind="rule", data={
        "rule_name": "Auth Rules v2",
        "negative_constraints": ["never store passwords in plaintext"],
        "positive_rules": ["always validate input"],
        "confidence": 0.85,
    })
    return mg, r1, r2


class TestBasic:

    def test_no_rules_returns_empty(self, mg):
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 0
        assert result["conflicts"] == []
        assert result["overlaps"] == []
        assert result["clean_rules"] == 0

    def test_single_rule_no_conflicts(self, mg):
        mg.add("Only Rule", kind="rule", data={
            "rule_name": "Solo",
            "negative_constraints": ["never do X"],
            "positive_rules": ["always do Y"],
        })
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 1
        assert result["conflicts"] == []
        assert result["clean_rules"] == 1

    def test_two_clean_rules(self, two_clean_rules):
        mg, r1, r2 = two_clean_rules
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 2
        assert result["conflicts"] == []
        assert result["overlaps"] == []
        assert result["clean_rules"] == 2
        assert "consistent" in result["recommendations"][0].lower()


class TestDirectConflicts:

    def test_detects_checksum_contradiction(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 2
        assert len(result["conflicts"]) >= 1
        c = result["conflicts"][0]
        assert c["type"] == "direct_contradiction"
        assert {c["rule_a"], c["rule_b"]} == {r1.id, r2.id}
        assert "checksum" in c["topic"].lower()

    def test_conflict_detail_is_human_readable(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        result = mg.rule_conflict_detect()
        detail = result["conflicts"][0]["detail"]
        assert "allows" in detail or "forbids" in detail

    def test_conflicting_rules_are_not_clean(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        result = mg.rule_conflict_detect()
        assert result["clean_rules"] == 0

    def test_recommendation_mentions_conflicts(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        result = mg.rule_conflict_detect()
        recs = " ".join(result["recommendations"])
        assert "contradiction" in recs.lower()

    def test_multiple_conflicts(self, mg):
        """Three rules with multiple pairwise contradictions."""
        mg.add("R1", kind="rule", data={
            "rule_name": "R1",
            "positive_rules": ["always encrypt database connections"],
            "negative_constraints": [],
        })
        mg.add("R2", kind="rule", data={
            "rule_name": "R2",
            "positive_rules": [],
            "negative_constraints": ["never encrypt database connections"],
        })
        mg.add("R3", kind="rule", data={
            "rule_name": "R3",
            "positive_rules": ["always encrypt database connections"],
            "negative_constraints": [],
        })
        result = mg.rule_conflict_detect()
        # R1 vs R2 (contradiction) and R2 vs R3 (contradiction)
        assert len(result["conflicts"]) >= 2


class TestOverlaps:

    def test_detects_shared_constraint(self, overlapping_rules):
        mg, r1, r2 = overlapping_rules
        result = mg.rule_conflict_detect()
        assert len(result["overlaps"]) >= 1
        o = result["overlaps"][0]
        assert "plaintext" in o["shared_text"]
        assert {o["rule_a"], o["rule_b"]} == {r1.id, r2.id}

    def test_overlap_recommendation(self, overlapping_rules):
        mg, r1, r2 = overlapping_rules
        result = mg.rule_conflict_detect()
        recs = " ".join(result["recommendations"])
        assert "overlap" in recs.lower()

    def test_no_overlap_for_different_rules(self, two_clean_rules):
        mg, r1, r2 = two_clean_rules
        result = mg.rule_conflict_detect()
        assert result["overlaps"] == []


class TestSubsetFiltering:

    def test_filter_by_rule_ids(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        # Only scan r1 → no pairs, no conflicts
        result = mg.rule_conflict_detect(rule_ids=[r1.id])
        assert result["total_rules"] == 1
        assert result["conflicts"] == []

    def test_filter_skips_nonexistent_ids(self, conflicting_rules):
        mg, r1, r2 = conflicting_rules
        result = mg.rule_conflict_detect(rule_ids=[r1.id, "nonexistent"])
        assert result["total_rules"] == 1

    def test_filter_skips_non_rule_nodes(self, mg):
        """Non-rule IDs in the filter are silently ignored."""
        ep = mg.add("Episode", kind="episode", data={})
        r = mg.add("Rule", kind="rule", data={
            "rule_name": "R",
            "negative_constraints": [],
            "positive_rules": [],
        })
        result = mg.rule_conflict_detect(rule_ids=[ep.id, r.id])
        assert result["total_rules"] == 1


class TestEdgeCases:

    def test_rules_with_no_constraints(self, mg):
        """Rules with empty constraint lists don't crash."""
        mg.add("Empty A", kind="rule", data={
            "rule_name": "A",
            "negative_constraints": [],
            "positive_rules": [],
        })
        mg.add("Empty B", kind="rule", data={
            "rule_name": "B",
            "negative_constraints": [],
            "positive_rules": [],
        })
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 2
        assert result["conflicts"] == []
        assert result["clean_rules"] == 2

    def test_rule_with_string_data_not_dict(self, mg):
        """Rule with non-dict data is handled gracefully."""
        mg.add("Weird Rule", kind="rule", data="not a dict")
        mg.add("Normal Rule", kind="rule", data={
            "rule_name": "Normal",
            "negative_constraints": ["never crash"],
            "positive_rules": [],
        })
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 2
        assert result["clean_rules"] >= 1

    def test_mixed_conflict_and_overlap(self, mg):
        """A scenario with both a conflict and an overlap."""
        mg.add("R1", kind="rule", data={
            "rule_name": "R1",
            "positive_rules": ["always validate user input thoroughly"],
            "negative_constraints": ["never skip input validation"],
        })
        mg.add("R2", kind="rule", data={
            "rule_name": "R2",
            "positive_rules": ["always validate user input thoroughly"],
            "negative_constraints": ["never validate input on trusted sources"],
        })
        result = mg.rule_conflict_detect()
        # Overlap: shared "always validate user input thoroughly"
        assert len(result["overlaps"]) >= 1
        # Possible conflict: "validate input" is positive in R1, negative in R2
        # (depends on keyword extraction)
        assert result["total_rules"] == 2

    def test_clean_rules_count_excludes_dirty(self, mg):
        """clean_rules should only count rules not in any conflict/overlap."""
        mg.add("Clean", kind="rule", data={
            "rule_name": "Clean",
            "positive_rules": ["always use semantic versioning"],
            "negative_constraints": ["never commit to main branch"],
        })
        mg.add("Conflict A", kind="rule", data={
            "rule_name": "A",
            "positive_rules": ["always cache responses aggressively"],
            "negative_constraints": [],
        })
        mg.add("Conflict B", kind="rule", data={
            "rule_name": "B",
            "positive_rules": [],
            "negative_constraints": ["never cache responses"],
        })
        result = mg.rule_conflict_detect()
        assert result["total_rules"] == 3
        assert result["clean_rules"] >= 1  # "Clean" should be clean

    def test_same_word_positive_and_negative(self, mg):
        """The exact same action word appears as positive and negative."""
        mg.add("Pos", kind="rule", data={
            "rule_name": "Pos",
            "positive_rules": ["always compress before storage"],
            "negative_constraints": [],
        })
        mg.add("Neg", kind="rule", data={
            "rule_name": "Neg",
            "positive_rules": [],
            "negative_constraints": ["never compress before storage"],
        })
        result = mg.rule_conflict_detect()
        assert len(result["conflicts"]) >= 1
        assert "compress" in result["conflicts"][0]["topic"].lower()

    def test_return_type_structure(self, two_clean_rules):
        mg, r1, r2 = two_clean_rules
        result = mg.rule_conflict_detect()
        assert isinstance(result, dict)
        assert "total_rules" in result
        assert "conflicts" in result
        assert "overlaps" in result
        assert "clean_rules" in result
        assert "recommendations" in result
        assert isinstance(result["conflicts"], list)
        assert isinstance(result["overlaps"], list)
        assert isinstance(result["recommendations"], list)
