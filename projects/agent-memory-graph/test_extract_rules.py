"""Tests for extract_rules() — L2→L3 declarative rule extraction.

Implements the upward compression from the Experience Compression Spectrum
(Zhang et al., arXiv:2604.15877): L2 (procedural skill) → L3 (declarative rule).

RuleShaping finding (Research #060): negative constraints (+7-14pp) outperform
positive directives, so we separate them explicitly.
"""

import pytest
import memory_graph as mg


class TestExtractRulesBasic:
    """Basic extraction from single and multiple skills."""

    def test_single_skill_extracts_constraints(self):
        """A skill with constraints should produce a rule node carrying them."""
        g = mg.MemoryGraph()
        ep = g.add("ep1", kind="episode", data={"task": "SQL query", "outcome": "success"})
        skill = g.compress_to_skill(
            [ep.id], "SQL Skill",
            description="Standard SQL workflow",
            confidence=0.8,
        )
        # Manually enrich with constraints via evolve
        g.evolve_skill(
            skill.id,
            new_constraints=["Never execute DROP without confirmation", "Always validate schema first"],
            new_steps=["Check schema", "Write query", "Validate result"],
        )
        rule = g.extract_rules([skill.id], name="SQL Safety Rules")
        assert rule is not None
        assert rule.kind == "rule"
        assert rule.data["rule_name"] == "SQL Safety Rules"
        assert "Never execute DROP without confirmation" in rule.data["negative_constraints"]
        assert "Always validate schema first" in rule.data["positive_rules"]

    def test_multiple_skills_merges_constraints(self):
        """Rules from multiple skills should merge constraints."""
        g = mg.MemoryGraph()

        # Skill 1
        ep1 = g.add("ep1", kind="episode", data={"task": "data cleaning"})
        s1 = g.compress_to_skill([ep1.id], "Cleaning Skill", confidence=0.7)
        g.evolve_skill(s1.id, new_constraints=["Never drop rows without counting"])

        # Skill 2
        ep2 = g.add("ep2", kind="episode", data={"task": "data validation"})
        s2 = g.compress_to_skill([ep2.id], "Validation Skill", confidence=0.7)
        g.evolve_skill(s2.id, new_constraints=["Never trust null counts", "Always check data types"])

        rule = g.extract_rules([s1.id, s2.id], name="Data Safety Rules")
        assert rule is not None
        assert len(rule.data["negative_constraints"]) >= 2
        assert len(rule.data["positive_rules"]) >= 1

    def test_empty_skill_list_returns_none(self):
        """No skills → no rule."""
        g = mg.MemoryGraph()
        rule = g.extract_rules([], name="Empty")
        assert rule is None

    def test_nonexistent_skill_id_raises(self):
        """Invalid skill ID should raise ValueError."""
        g = mg.MemoryGraph()
        with pytest.raises(ValueError):
            g.extract_rules(["nonexistent-id"])

    def test_non_skill_node_raises(self):
        """Non-skill node should raise ValueError."""
        g = mg.MemoryGraph()
        n = g.add("plain", kind="fact", data={"text": "hello"})
        with pytest.raises(ValueError, match="kind='skill'"):
            g.extract_rules([n.id])


class TestExtractRulesCrossSkill:
    """Cross-skill pattern detection."""

    def test_repeated_constraint_becomes_high_confidence(self):
        """A constraint appearing in multiple skills should boost confidence."""
        g = mg.MemoryGraph()

        ep1 = g.add("ep1", kind="episode", data={"task": "task A"})
        s1 = g.compress_to_skill([ep1.id], "Skill A", confidence=0.8)
        g.evolve_skill(s1.id, new_constraints=["Always verify output before returning"])

        ep2 = g.add("ep2", kind="episode", data={"task": "task B"})
        s2 = g.compress_to_skill([ep2.id], "Skill B", confidence=0.8)
        g.evolve_skill(s2.id, new_constraints=["Always verify output before returning"])

        rule = g.extract_rules([s1.id, s2.id], name="Verification Rule")
        # Cross-skill pattern → higher confidence
        assert rule.data["confidence"] > 0.8  # boosted above individual skills
        assert len(rule.data["cross_skill_patterns"]) >= 1

    def test_cross_skill_patterns_listed(self):
        """Patterns shared across skills are listed with occurrence count."""
        g = mg.MemoryGraph()

        ep1 = g.add("ep1", kind="episode")
        s1 = g.compress_to_skill([ep1.id], "S1", confidence=0.7)
        g.evolve_skill(s1.id, new_constraints=["never skip tests", "always log errors"])

        ep2 = g.add("ep2", kind="episode")
        s2 = g.compress_to_skill([ep2.id], "S2", confidence=0.7)
        g.evolve_skill(s2.id, new_constraints=["never skip tests"])

        rule = g.extract_rules([s1.id, s2.id])
        patterns = rule.data["cross_skill_patterns"]
        # "never skip tests" appears in both → should be in patterns
        found = any("never skip tests" in p.get("constraint", "") for p in patterns)
        assert found

    def test_no_overlap_still_produces_rule(self):
        """Skills with no shared constraints still produce a valid rule."""
        g = mg.MemoryGraph()

        ep1 = g.add("ep1", kind="episode")
        s1 = g.compress_to_skill([ep1.id], "S1", confidence=0.6)
        g.evolve_skill(s1.id, new_constraints=["never do X"])

        ep2 = g.add("ep2", kind="episode")
        s2 = g.compress_to_skill([ep2.id], "S2", confidence=0.6)
        g.evolve_skill(s2.id, new_constraints=["always do Y"])

        rule = g.extract_rules([s1.id, s2.id], name="Union Rule")
        assert rule is not None
        assert len(rule.data["cross_skill_patterns"]) == 0
        # Still has all constraints
        assert len(rule.data["negative_constraints"]) >= 1
        assert len(rule.data["positive_rules"]) >= 1


class TestExtractRulesStructure:
    """Structural correctness of the rule node."""

    def test_rule_node_kind(self):
        """Output node must have kind='rule'."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S", confidence=0.5)
        g.evolve_skill(s.id, new_constraints=["never rush"])
        rule = g.extract_rules([s.id])
        assert rule.kind == "rule"

    def test_rule_has_source_skills(self):
        """Rule node tracks which skills it was derived from."""
        g = mg.MemoryGraph()
        ep1 = g.add("ep1", kind="episode")
        ep2 = g.add("ep2", kind="episode")
        s1 = g.compress_to_skill([ep1.id], "S1")
        s2 = g.compress_to_skill([ep2.id], "S2")
        rule = g.extract_rules([s1.id, s2.id], name="Derived")
        assert set(rule.data["source_skills"]) == {s1.id, s2.id}
        assert rule.data["source_count"] == 2

    def test_rule_has_compression_type(self):
        """Rule records its compression level."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S")
        rule = g.extract_rules([s.id])
        assert rule.data["compression_type"] == "L2→L3"

    def test_rule_has_version(self):
        """Rules start at version 1.0.0 (stable declarative)."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S")
        rule = g.extract_rules([s.id])
        assert rule.data["version"] == "1.0.0"

    def test_rule_has_created_at(self):
        """Rule node has creation timestamp."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S")
        rule = g.extract_rules([s.id])
        assert "created_at" in rule.data
        assert isinstance(rule.data["created_at"], (int, float))

    def test_rule_has_compression_ratio(self):
        """Rule reports estimated compression ratio vs raw skills."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S", confidence=0.7)
        g.evolve_skill(s.id, new_constraints=["c1", "c2", "c3"], new_steps=["s1", "s2", "s3"])
        rule = g.extract_rules([s.id])
        assert "compression_ratio" in rule.data
        assert rule.data["compression_ratio"] >= 1.0


class TestExtractRulesConfidence:
    """Confidence calculation and thresholds."""

    def test_min_confidence_filters_low_skills(self):
        """Skills below min_confidence are excluded."""
        g = mg.MemoryGraph()
        ep1 = g.add("ep1", kind="episode")
        s1 = g.compress_to_skill([ep1.id], "Low Conf", confidence=0.3)
        g.evolve_skill(s1.id, new_constraints=["never skip validation"])

        ep2 = g.add("ep2", kind="episode")
        s2 = g.compress_to_skill([ep2.id], "High Conf", confidence=0.9)
        g.evolve_skill(s2.id, new_constraints=["never trust unverified data"])

        rule = g.extract_rules([s1.id, s2.id], min_confidence=0.5)
        assert rule is not None
        # Only high-conf skill's constraints should appear
        assert "never trust unverified data" in rule.data["negative_constraints"]
        assert "never skip validation" not in rule.data["negative_constraints"]

    def test_confidence_averages_source_skills(self):
        """Rule confidence should be influenced by source skill confidence."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S", confidence=0.8)
        g.evolve_skill(s.id, new_constraints=["c1"])
        rule = g.extract_rules([s.id])
        # Base confidence from skill, possibly boosted by cross-skill patterns
        assert rule.data["confidence"] >= 0.5

    def test_rule_name_default(self):
        """If no name given, auto-generate from skills."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "My Skill")
        rule = g.extract_rules([s.id])
        assert rule.data["rule_name"]  # non-empty auto-generated name

    def test_rule_edges_to_source_skills(self):
        """Rule node should have derived_from edges to source skills."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "S")
        rule = g.extract_rules([s.id])
        # Check edge exists via is_linked
        assert g.is_linked(rule.id, s.id)

    def test_skill_with_no_constraints_still_works(self):
        """A skill with no constraints still produces a rule (possibly empty)."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode")
        s = g.compress_to_skill([ep.id], "Empty Skill", confidence=0.6)
        rule = g.extract_rules([s.id], name="Empty Rule")
        assert rule is not None
        assert rule.data["negative_constraints"] == []
        assert rule.data["positive_rules"] == []
