"""Tests for MemoryGraph.rule_explain() — per-rule match diagnostics.

Diagnostic companion to rule_apply(). Rule introspection lifecycle:
extract_rules → rule_conflict_detect → rule_apply → rule_explain.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def graph_with_rules():
    """Graph with L3 rule nodes."""
    g = MemoryGraph(":memory:")

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


def _find_rule_id(g, label):
    """Helper to get node ID by label."""
    row = g.conn.execute(
        "SELECT id FROM nodes WHERE label=?", (label,)
    ).fetchone()
    return row["id"]


# ── Error Cases ──────────────────────────────────────────────

class TestRuleExplainErrors:
    def test_nonexistent_rule_id(self, empty_graph):
        result = empty_graph.rule_explain("nonexistent", "test query")
        assert "error" in result
        assert "not a rule node" in result["error"]
        assert result["rule_id"] == "nonexistent"

    def test_non_rule_node(self, graph_with_rules):
        """A node that exists but isn't kind='rule'."""
        graph_with_rules.add("Some Skill", kind="skill", data={})
        skill_id = _find_rule_id(graph_with_rules, "Some Skill")
        result = graph_with_rules.rule_explain(skill_id, "test")
        assert "error" in result

    def test_empty_graph(self, empty_graph):
        result = empty_graph.rule_explain("any-id", "anything")
        assert "error" in result


# ── Basic Matching ───────────────────────────────────────────

class TestRuleExplainBasic:
    def test_matched_rule(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify authentication checksums")
        assert result["matched"] is True
        assert result["relevance"] > 0

    def test_unmatched_rule(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "cache optimization performance")
        assert result["matched"] is False
        assert result["relevance"] == 0.0

    def test_relevance_matches_jaccard(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        result = graph_with_rules.rule_explain(rid, "write tests functions")
        # Manually compute expected Jaccard
        # query tokens: write, tests, functions (3)
        # rule tokens: testing, write, unit, tests, for, all, functions, not, test, implementation, details
        # intersection: write, tests, functions (3)
        # union: testing, write, unit, tests, for, all, functions, not, test, implementation, details (11)
        assert result["jaccard_numerator"] == result["jaccard_denominator"] - 8

    def test_relevance_zero_for_disjoint(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        result = graph_with_rules.rule_explain(rid, "cache performance data")
        assert result["relevance"] == 0.0
        assert result["matched"] is False

    def test_rule_name_echoed(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "security")
        assert result["rule_name"] == "Security"

    def test_query_echoed(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "security check")
        assert result["query"] == "security check"


# ── Keyword Breakdown ────────────────────────────────────────

class TestRuleExplainKeywords:
    def test_query_keywords_present(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "verify" in result["query_keywords"]
        assert "checksums" in result["query_keywords"]

    def test_rule_keywords_present(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "security" in result["rule_keywords"]
        assert "verify" in result["rule_keywords"]
        assert "checksums" in result["rule_keywords"]

    def test_intersection_correct(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert set(result["intersection"]) == {"verify", "checksums"}

    def test_union_correct(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        # union = query ∪ rule keywords
        assert "verify" in result["union"]
        assert "checksums" in result["union"]
        assert "security" in result["union"]
        assert "authentication" in result["union"]

    def test_query_only_correct(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums deploy")
        assert "deploy" in result["query_only"]
        assert "verify" not in result["query_only"]

    def test_rule_only_correct(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "security" in result["rule_only"]
        assert "authentication" in result["rule_only"]
        assert "verify" not in result["rule_only"]

    def test_empty_query_keywords(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "")
        assert result["query_keywords"] == []
        assert result["matched"] is False

    def test_stopwords_filtered(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "the and for are but not")
        assert result["query_keywords"] == []


# ── Jaccard Math ─────────────────────────────────────────────

class TestRuleExplainJaccard:
    def test_numerator_equals_intersection_size(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert result["jaccard_numerator"] == len(result["intersection"])

    def test_denominator_equals_union_size(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert result["jaccard_denominator"] == len(result["union"])

    def test_relevance_equals_numerator_over_denominator(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        result = graph_with_rules.rule_explain(rid, "write tests")
        expected = result["jaccard_numerator"] / result["jaccard_denominator"]
        assert result["relevance"] == round(expected, 4)

    def test_relevance_range(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert 0.0 <= result["relevance"] <= 1.0

    def test_contribution_scores_sum_to_relevance(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        total = sum(result["contribution_scores"].values())
        assert abs(total - result["relevance"]) < 0.01

    def test_contribution_scores_keys_are_intersection(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert set(result["contribution_scores"].keys()) == set(result["intersection"])

    def test_zero_relevance_has_empty_contribution(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        result = graph_with_rules.rule_explain(rid, "cache performance")
        assert result["contribution_scores"] == {}


# ── Explanation Text ─────────────────────────────────────────

class TestRuleExplainText:
    def test_explanation_is_string(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 0

    def test_explanation_contains_rule_name(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "Security" in result["explanation"]

    def test_explanation_contains_relevance(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "Relevance:" in result["explanation"]

    def test_explanation_contains_intersection(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "Intersection" in result["explanation"]

    def test_explanation_contains_query_only(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums deploy")
        assert "Query-only" in result["explanation"]

    def test_explanation_contains_rule_only(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert "Rule-only" in result["explanation"]


# ── Suggestions ──────────────────────────────────────────────

class TestRuleExplainSuggestions:
    def test_suggestions_present_by_default(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        assert isinstance(result["suggestions"], list)
        assert len(result["suggestions"]) > 0

    def test_suggestions_disabled(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(
            rid, "verify checksums", include_suggestions=False
        )
        assert "suggestions" not in result or result["suggestions"] == []

    def test_zero_overlap_suggests_keywords(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        result = graph_with_rules.rule_explain(rid, "cache performance data")
        text = " ".join(result["suggestions"]).lower()
        assert "overlap" in text or "keyword" in text

    def test_high_relevance_suggestion(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "security verify checksums authentication")
        text = " ".join(result["suggestions"]).lower()
        assert "high relevance" in text

    def test_uncovered_intent_suggestion(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums deploy monitor")
        text = " ".join(result["suggestions"]).lower()
        assert "uncovered" in text or "intent" in text

    def test_rule_scope_suggestion(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        text = " ".join(result["suggestions"]).lower()
        assert "rule scope" in text or "triggered" in text

    def test_empty_query_suggestion(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "")
        text = " ".join(result["suggestions"]).lower()
        assert "no extractable" in text or "keywords" in text


# ── Positive/Negative Rules ──────────────────────────────────

class TestRuleExplainGuidance:
    def test_positive_rules_returned(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify")
        assert "always verify checksums" in result["positive_rules"]

    def test_negative_constraints_returned(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify")
        assert "never skip authentication" in result["negative_constraints"]

    def test_positive_rules_empty_for_minimal_rule(self, empty_graph):
        g = empty_graph
        g.add("Minimal Rule", kind="rule", data={
            "rule_name": "Minimal",
        })
        rid = _find_rule_id(g, "Minimal Rule")
        result = g.rule_explain(rid, "minimal")
        assert result["positive_rules"] == []
        assert result["negative_constraints"] == []


# ── Edge Cases ───────────────────────────────────────────────

class TestRuleExplainEdgeCases:
    def test_rule_with_none_data(self, empty_graph):
        g = empty_graph
        g.add("Bad Rule", kind="rule", data=None)
        rid = _find_rule_id(g, "Bad Rule")
        result = g.rule_explain(rid, "anything")
        assert "error" not in result
        assert result["relevance"] == 0.0

    def test_rule_with_string_data(self, empty_graph):
        g = empty_graph
        g.add("Str Rule", kind="rule", data="not valid json")
        rid = _find_rule_id(g, "Str Rule")
        result = g.rule_explain(rid, "anything")
        assert "error" not in result
        assert result["relevance"] == 0.0

    def test_rule_with_empty_data(self, empty_graph):
        g = empty_graph
        g.add("Empty Rule", kind="rule", data={})
        rid = _find_rule_id(g, "Empty Rule")
        result = g.rule_explain(rid, "anything")
        assert "error" not in result
        assert result["relevance"] == 0.0
        assert result["rule_name"] == "Empty Rule"  # falls back to label

    def test_numbers_and_symbols_query(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "123 456 !!! @#$")
        assert result["query_keywords"] == []
        assert result["matched"] is False

    def test_case_insensitive(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result_lower = graph_with_rules.rule_explain(rid, "verify checksums")
        result_upper = graph_with_rules.rule_explain(rid, "VERIFY CHECKSUMS")
        assert result_lower["relevance"] == result_upper["relevance"]

    def test_single_char_query(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "x")
        assert result["query_keywords"] == []

    def test_query_matches_all_keywords(self, graph_with_rules):
        """Perfect overlap: query contains all rule keywords."""
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        # rule keywords: security, always, verify, checksums, never, skip, authentication
        result = graph_with_rules.rule_explain(
            rid, "security always verify checksums never skip authentication"
        )
        assert result["relevance"] > 0.5
        assert len(result["query_only"]) == 0


# ── Non-Mutating ─────────────────────────────────────────────

class TestRuleExplainNonMutating:
    def test_graph_unchanged(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        before = graph_with_rules.stats()
        graph_with_rules.rule_explain(rid, "verify checksums")
        after = graph_with_rules.stats()
        assert before == after

    def test_rule_data_unchanged(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        row_before = graph_with_rules.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (rid,)
        ).fetchone()
        graph_with_rules.rule_explain(rid, "verify checksums")
        row_after = graph_with_rules.conn.execute(
            "SELECT data FROM nodes WHERE id=?", (rid,)
        ).fetchone()
        assert row_before["data"] == row_after["data"]

    def test_idempotent(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        r1 = graph_with_rules.rule_explain(rid, "verify checksums")
        r2 = graph_with_rules.rule_explain(rid, "verify checksums")
        assert r1 == r2


# ── Consistency with rule_apply ──────────────────────────────

class TestRuleExplainConsistency:
    def test_explain_matches_apply_relevance(self, graph_with_rules):
        """rule_explain relevance should match rule_apply relevance."""
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        query = "verify checksums"

        apply_result = graph_with_rules.rule_apply(query)
        explain_result = graph_with_rules.rule_explain(rid, query)

        # Find this rule in apply results
        apply_match = None
        for m in apply_result["matches"]:
            if m["rule_id"] == rid:
                apply_match = m
                break

        if apply_match:
            assert abs(apply_match["relevance"] - explain_result["relevance"]) < 0.01
        else:
            # If not in apply results, relevance should be 0
            assert explain_result["relevance"] == 0.0

    def test_matched_in_explain_implies_matched_in_apply(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        query = "write tests"

        explain_result = graph_with_rules.rule_explain(rid, query)
        apply_result = graph_with_rules.rule_apply(query)

        if explain_result["matched"]:
            rule_ids = {m["rule_id"] for m in apply_result["matches"]}
            assert rid in rule_ids

    def test_unmatched_in_explain_implies_absent_from_apply(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Testing Rule")
        query = "cache performance optimization"

        explain_result = graph_with_rules.rule_explain(rid, query)
        apply_result = graph_with_rules.rule_apply(query)

        if not explain_result["matched"]:
            rule_ids = {m["rule_id"] for m in apply_result["matches"]}
            assert rid not in rule_ids


# ── Return Structure ─────────────────────────────────────────

class TestRuleExplainStructure:
    def test_result_has_all_keys(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        expected_keys = {
            "rule_id", "rule_name", "query", "matched", "relevance",
            "query_keywords", "rule_keywords", "intersection", "union",
            "query_only", "rule_only", "jaccard_numerator",
            "jaccard_denominator", "contribution_scores",
            "positive_rules", "negative_constraints",
            "explanation", "suggestions",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_keywords_are_sorted_lists(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums")
        for key in ("query_keywords", "rule_keywords", "intersection",
                     "union", "query_only", "rule_only"):
            val = result[key]
            assert isinstance(val, list)
            assert val == sorted(val)

    def test_intersection_is_subset_of_union(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums deploy")
        assert set(result["intersection"]).issubset(set(result["union"]))

    def test_query_only_disjoint_from_rule_only(self, graph_with_rules):
        rid = _find_rule_id(graph_with_rules, "Security Rule")
        result = graph_with_rules.rule_explain(rid, "verify checksums deploy")
        assert set(result["query_only"]).isdisjoint(set(result["rule_only"]))
