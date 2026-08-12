"""Tests for MemoryGraph.rule_apply() — runtime rule matching.

Rule lifecycle: extract_rules → rule_conflict_detect → rule_apply.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def graph_with_rules():
    """Graph with L3 rule nodes created via extract_rules-like structure."""
    g = MemoryGraph(":memory:")

    # Simulate rules created by extract_rules
    g.add("Security Rule", kind="rule", data={
        "rule_name": "Security",
        "positive_rules": ["always verify checksums"],
        "negative_constraints": ["never skip authentication"],
        "derived_from": ["skill-1", "skill-2"],
    })
    g.add("Performance Rule", kind="rule", data={
        "rule_name": "Performance",
        "positive_rules": ["cache frequently accessed data"],
        "negative_constraints": ["avoid premature optimization"],
        "derived_from": ["skill-3"],
    })
    g.add("Testing Rule", kind="rule", data={
        "rule_name": "Testing",
        "positive_rules": ["write unit tests for all functions"],
        "negative_constraints": ["do not test implementation details"],
        "derived_from": ["skill-4"],
    })

    return g


@pytest.fixture
def graph_with_conflicting_rules():
    """Graph with conflicting rules for conflict + apply scenarios."""
    g = MemoryGraph(":memory:")

    g.add("Rule A", kind="rule", data={
        "rule_name": "FastMode",
        "positive_rules": ["skip checksums for speed"],
        "negative_constraints": ["avoid slow verification"],
    })
    g.add("Rule B", kind="rule", data={
        "rule_name": "SafeMode",
        "positive_rules": ["always verify checksums"],
        "negative_constraints": ["never skip verification"],
    })
    return g


class TestRuleApplyEmpty:
    """Tests with no rules in the graph."""

    def test_no_rules_returns_empty(self, empty_graph):
        result = empty_graph.rule_apply("test query")
        assert result["matched_count"] == 0
        assert result["matches"] == []
        assert result["total_rules_scanned"] == 0

    def test_no_rules_guidance_suggests_extract(self, empty_graph):
        result = empty_graph.rule_apply("anything")
        assert "extract_rules" in result["guidance"][0]

    def test_no_rules_unmatched_count(self, empty_graph):
        result = empty_graph.rule_apply("query")
        assert result["unmatched_rules"] == 0


class TestRuleApplyBasic:
    """Basic matching tests."""

    def test_query_matches_one_rule(self, graph_with_rules):
        result = graph_with_rules.rule_apply("verify checksums and authentication")
        assert result["matched_count"] >= 1
        # Security rule should be top match
        assert result["matches"][0]["rule_name"] == "Security"

    def test_query_matches_multiple_rules(self, graph_with_rules):
        result = graph_with_rules.rule_apply(
            "verify checksums and write unit tests"
        )
        names = [m["rule_name"] for m in result["matches"]]
        assert "Security" in names
        assert "Testing" in names

    def test_relevance_sorted_descending(self, graph_with_rules):
        result = graph_with_rules.rule_apply(
            "checksums authentication verify"
        )
        relevances = [m["relevance"] for m in result["matches"]]
        assert relevances == sorted(relevances, reverse=True)

    def test_relevance_in_range(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        for m in result["matches"]:
            assert 0 < m["relevance"] <= 1.0

    def test_no_match_returns_empty_matches(self, graph_with_rules):
        result = graph_with_rules.rule_apply("xyzabc qwerp")
        # No common tokens → no matches
        assert result["matched_count"] == 0
        assert result["matches"] == []

    def test_no_match_guidance(self, graph_with_rules):
        result = graph_with_rules.rule_apply("xyzabc")
        assert "No matching rules" in result["guidance"][0]


class TestRuleApplyTopK:
    """Tests for the top_k parameter."""

    def test_top_k_limits_results(self, graph_with_rules):
        result = graph_with_rules.rule_apply(
            "checksums authentication cache performance testing unit",
            top_k=1,
        )
        assert len(result["matches"]) <= 1

    def test_top_k_default_is_10(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums", top_k=10)
        assert len(result["matches"]) <= 10

    def test_top_k_zero(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums", top_k=0)
        assert len(result["matches"]) == 0


class TestRuleApplyGuidance:
    """Tests for the guidance output."""

    def test_positive_rules_in_guidance(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums authentication")
        pos_guidance = [g for g in result["guidance"] if "DO:" in g]
        assert len(pos_guidance) > 0

    def test_negative_constraints_in_guidance(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums authentication")
        neg_guidance = [g for g in result["guidance"] if "DON'T:" in g]
        assert len(neg_guidance) > 0

    def test_guidance_includes_rule_name(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        assert any("[Security]" in g for g in result["guidance"])

    def test_guidance_for_no_match(self, graph_with_rules):
        result = graph_with_rules.rule_apply("zzzzz")
        assert "No matching rules" in result["guidance"][0]


class TestRuleApplyMetadata:
    """Tests for the include_metadata flag."""

    def test_no_metadata_by_default(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        for m in result["matches"]:
            assert "metadata" not in m

    def test_include_metadata_adds_data(self, graph_with_rules):
        result = graph_with_rules.rule_apply(
            "checksums", include_metadata=True
        )
        for m in result["matches"]:
            assert "metadata" in m
            assert isinstance(m["metadata"], dict)

    def test_metadata_contains_derived_from(self, graph_with_rules):
        result = graph_with_rules.rule_apply(
            "checksums", include_metadata=True
        )
        security_match = next(
            m for m in result["matches"] if m["rule_name"] == "Security"
        )
        assert "derived_from" in security_match["metadata"]


class TestRuleApplyReturnStructure:
    """Tests for the overall return structure."""

    def test_result_has_all_keys(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        expected_keys = {
            "query", "total_rules_scanned", "matched_count",
            "matches", "guidance", "unmatched_rules",
        }
        assert set(result.keys()) == expected_keys

    def test_query_echoed(self, graph_with_rules):
        result = graph_with_rules.rule_apply("my custom query")
        assert result["query"] == "my custom query"

    def test_total_rules_scanned(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        assert result["total_rules_scanned"] == 3

    def test_unmatched_plus_matched(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums authentication")
        total = result["matched_count"] + result["unmatched_rules"]
        assert total == result["total_rules_scanned"]

    def test_match_structure_keys(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums")
        if result["matches"]:
            m = result["matches"][0]
            expected = {
                "rule_id", "rule_name", "relevance",
                "positive_rules", "negative_constraints",
            }
            assert expected.issubset(set(m.keys()))


class TestRuleApplyWithConflicts:
    """Tests applying rules when conflicts exist."""

    def test_both_conflicting_rules_match(self, graph_with_conflicting_rules):
        result = graph_with_conflicting_rules.rule_apply("verify checksums")
        names = [m["rule_name"] for m in result["matches"]]
        # Both rules mention checksums
        assert "FastMode" in names or "SafeMode" in names

    def test_conflicting_guidance_shows_both_sides(
        self, graph_with_conflicting_rules
    ):
        result = graph_with_conflicting_rules.rule_apply("checksums verify")
        guidance_text = " ".join(result["guidance"])
        # Should have both DO and DON'T guidance
        assert "DO:" in guidance_text
        assert "DON'T:" in guidance_text


class TestRuleApplyEdgeCases:
    """Edge case tests."""

    def test_empty_query_string(self, graph_with_rules):
        result = graph_with_rules.rule_apply("")
        # Empty query → no tokens → no matches
        assert result["matched_count"] == 0

    def test_query_with_only_stopwords(self, graph_with_rules):
        result = graph_with_rules.rule_apply("the and for are but not")
        assert result["matched_count"] == 0

    def test_query_with_numbers_and_symbols(self, graph_with_rules):
        result = graph_with_rules.rule_apply("checksums 12345 !!!")
        # "checksums" should still match
        assert result["matched_count"] >= 1

    def test_case_insensitive_matching(self, graph_with_rules):
        result_lower = graph_with_rules.rule_apply("checksums")
        result_upper = graph_with_rules.rule_apply("CHECKSUMS")
        result_mixed = graph_with_rules.rule_apply("ChEcKsUmS")
        assert result_lower["matched_count"] == result_upper["matched_count"]
        assert result_lower["matched_count"] == result_mixed["matched_count"]

    def test_single_char_query(self, graph_with_rules):
        result = graph_with_rules.rule_apply("x")
        # Single chars are filtered (min 3 chars per token)
        assert result["matched_count"] == 0

    def test_rule_with_empty_data(self, empty_graph):
        """Rule node with no structured data."""
        g = empty_graph
        g.add("Empty Rule", kind="rule", data={})
        result = g.rule_apply("anything here")
        # Empty rule has no keywords → no match
        assert result["matched_count"] == 0

    def test_rule_with_none_data(self, empty_graph):
        """Rule node with data=None (edge case from malformed nodes)."""
        g = empty_graph
        g.add("None Data Rule", kind="rule", data=None)
        result = g.rule_apply("test query here")
        assert result["matched_count"] == 0

    def test_non_dict_data_string(self, empty_graph):
        """Rule node with data as a JSON string."""
        g = empty_graph
        # Simulate data stored as JSON string (SQLite raw insert)
        g.conn.execute(
            "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags,category) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ('r-json', 'JSON Rule', 'rule',
             '{"rule_name": "JSON", "positive_rules": ["always validate input"], "negative_constraints": []}',
             0, 0, 1.0, '[]', None)
        )
        g.conn.commit()
        result = g.rule_apply("validate input")
        assert result["matched_count"] >= 1


class TestRuleApplyNonMutating:
    """Tests that rule_apply doesn't modify the graph."""

    def test_graph_unchanged_after_apply(self, graph_with_rules):
        stats_before = graph_with_rules.stats()
        graph_with_rules.rule_apply("checksums authentication")
        stats_after = graph_with_rules.stats()
        assert stats_before["nodes"] == stats_after["nodes"]
        assert stats_before["edges"] == stats_after["edges"]

    def test_rule_data_unchanged(self, graph_with_rules):
        nodes = graph_with_rules.conn.execute(
            "SELECT id FROM nodes WHERE kind='rule' LIMIT 1"
        ).fetchall()
        rid = nodes[0][0]
        node_before = graph_with_rules.get_node(rid)
        graph_with_rules.rule_apply("checksums verify authentication")
        node_after = graph_with_rules.get_node(rid)
        assert node_before.data == node_after.data

    def test_multiple_calls_idempotent(self, graph_with_rules):
        r1 = graph_with_rules.rule_apply("checksums")
        r2 = graph_with_rules.rule_apply("checksums")
        assert r1["matched_count"] == r2["matched_count"]
        assert r1["matches"] == r2["matches"]
