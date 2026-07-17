"""Tests for query_route_audit() — routing observability.

Cycle 262 — MemFlow-inspired intent routing audit trail.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated():
    g = MemoryGraph(":memory:")
    alice = g.add("Alice", "person", {"role": "engineer"})
    bob = g.add("Bob", "person", {"role": "manager"})
    project = g.add("Project Alpha", "project")
    g.link(alice.id, bob.id, "reports_to")
    g.link(alice.id, project.id, "works_on")
    return g


class TestQueryRouteAudit:

    def test_returns_required_keys(self, mg):
        result = mg.query_route_audit()
        for key in ("audited", "mode_distribution", "summary", "per_question"):
            assert key in result

    def test_default_questions_used(self, mg):
        result = mg.query_route_audit()
        assert result["audited"] > 0
        assert len(result["per_question"]) == result["audited"]

    def test_custom_questions(self, mg):
        questions = ["Alice", "overview", "when?"]
        result = mg.query_route_audit(questions)
        assert result["audited"] == 3
        assert len(result["per_question"]) == 3

    def test_per_question_has_mode(self, mg):
        result = mg.query_route_audit(["test question here"])
        assert "mode" in result["per_question"][0]

    def test_per_question_has_rationale(self, mg):
        result = mg.query_route_audit(["test"])
        assert "rationale" in result["per_question"][0]
        assert len(result["per_question"][0]["rationale"]) > 0

    def test_mode_distribution_sums_correctly(self, mg):
        questions = ["Alice", "Bob", "overview"]
        result = mg.query_route_audit(questions)
        total = sum(result["mode_distribution"].values())
        assert total == 3

    def test_summary_is_string(self, mg):
        result = mg.query_route_audit()
        assert isinstance(result["summary"], str)

    def test_include_results_adds_counts(self, populated):
        result = populated.query_route_audit(
            ["Alice"], include_results=True
        )
        entry = result["per_question"][0]
        assert "result_count" in entry
        assert "elapsed_ms" in entry

    def test_without_results_no_extra_fields(self, populated):
        result = populated.query_route_audit(
            ["Alice"], include_results=False
        )
        entry = result["per_question"][0]
        assert "result_count" not in entry

    def test_all_seven_modes_testable(self, populated):
        """Each mode should be reachable via the right question."""
        test_cases = [
            ("Alice", "basic"),
            ("overview of all themes", "global"),
            ("when was this created?", "temporal"),
            ("is this valid?", "constraint"),
        ]
        for q, expected_mode in test_cases:
            result = populated.query_route_audit([q])
            assert result["per_question"][0]["mode"] == expected_mode, (
                f"Question '{q}' routed to "
                f"{result['per_question'][0]['mode']}, expected {expected_mode}"
            )

    def test_empty_questions_list(self, mg):
        result = mg.query_route_audit([])
        assert result["audited"] == 0
        assert result["mode_distribution"] == {}

    def test_question_echoed(self, mg):
        result = mg.query_route_audit(["unique test query"])
        assert result["per_question"][0]["question"] == "unique test query"

    def test_mode_distribution_is_dict(self, mg):
        result = mg.query_route_audit(["Alice", "overview of themes"])
        assert isinstance(result["mode_distribution"], dict)

    def test_multiple_modes_in_distribution(self, populated):
        questions = [
            "Alice",  # basic
            "overview of all themes",  # global
            "when was this?",  # temporal
            "is this valid?",  # constraint
        ]
        result = populated.query_route_audit(questions)
        assert len(result["mode_distribution"]) >= 3

    def test_audited_count_matches_per_question_len(self, mg):
        questions = [f"question {i}" for i in range(10)]
        result = mg.query_route_audit(questions)
        assert result["audited"] == len(result["per_question"])
