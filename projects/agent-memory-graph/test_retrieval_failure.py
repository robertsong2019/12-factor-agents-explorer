"""Tests for retrieval-failure logging (SAGE reader-writer feedback loop).

When retrieval returns poor results, the failure is logged.
analyse_retrieval_failures() identifies patterns and suggests graph improvements.
"""

import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    m = MemoryGraph()
    m.add("Python programming", "skill")
    m.add("Rust systems", "skill")
    m.add("TypeScript web", "skill")
    return m


# =====================================================================
# log_retrieval_failure
# =====================================================================

class TestLogRetrievalFailure:

    def test_log_returns_row_id(self, mg):
        rid = mg.log_retrieval_failure("nonexistent query")
        assert isinstance(rid, int)
        assert rid > 0

    def test_log_stores_all_fields(self, mg):
        mg.log_retrieval_failure("test query", result_count=2, top_score=0.35, stage="ppr")
        failures = mg.get_retrieval_failures()
        assert len(failures) == 1
        f = failures[0]
        assert f["query"] == "test query"
        assert f["result_count"] == 2
        assert abs(f["top_score"] - 0.35) < 0.001
        assert f["stage"] == "ppr"
        assert f["analysed"] == 0

    def test_log_defaults(self, mg):
        mg.log_retrieval_failure("empty results")
        failures = mg.get_retrieval_failures()
        f = failures[0]
        assert f["result_count"] == 0
        assert f["top_score"] == 0.0
        assert f["stage"] == "recall"

    def test_multiple_logs(self, mg):
        for i in range(5):
            mg.log_retrieval_failure(f"query_{i}")
        failures = mg.get_retrieval_failures()
        assert len(failures) == 5


# =====================================================================
# get_retrieval_failures
# =====================================================================

class TestGetRetrievalFailures:

    def test_filter_by_stage(self, mg):
        mg.log_retrieval_failure("q1", stage="recall")
        mg.log_retrieval_failure("q2", stage="ppr")
        mg.log_retrieval_failure("q3", stage="recall")
        recall_only = mg.get_retrieval_failures(stage="recall")
        assert len(recall_only) == 2
        assert all(f["stage"] == "recall" for f in recall_only)

    def test_filter_by_since(self, mg):
        old_ts = time.time() - 7200  # 2 hours ago
        mg.log_retrieval_failure("old_query")
        # Manually update timestamp to simulate old entry
        mg.conn.execute(
            "UPDATE retrieval_failures SET timestamp=? WHERE query=?",
            (old_ts, "old_query"),
        )
        mg.conn.commit()
        mg.log_retrieval_failure("new_query")

        recent = mg.get_retrieval_failures(since=time.time() - 3600)
        assert len(recent) == 1
        assert recent[0]["query"] == "new_query"

    def test_limit_parameter(self, mg):
        for i in range(50):
            mg.log_retrieval_failure(f"query_{i}")
        failures = mg.get_retrieval_failures(limit=10)
        assert len(failures) == 10

    def test_newest_first_ordering(self, mg):
        mg.log_retrieval_failure("first")
        time.sleep(0.01)
        mg.log_retrieval_failure("second")
        failures = mg.get_retrieval_failures()
        assert failures[0]["query"] == "second"
        assert failures[1]["query"] == "first"

    def test_empty_when_no_failures(self):
        mg = MemoryGraph()
        assert mg.get_retrieval_failures() == []


# =====================================================================
# analyse_retrieval_failures
# =====================================================================

class TestAnalyseRetrievalFailures:

    def test_groups_by_query(self, mg):
        for _ in range(5):
            mg.log_retrieval_failure("Python advanced")
        for _ in range(3):
            mg.log_retrieval_failure("Rust embedded")
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        queries = [a["query"] for a in analysis]
        assert "Python advanced" in queries
        assert "Rust embedded" in queries

    def test_filters_below_min_failures(self, mg):
        for _ in range(3):
            mg.log_retrieval_failure("frequent_query")
        mg.log_retrieval_failure("rare_query")
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        queries = [a["query"] for a in analysis]
        assert "frequent_query" in queries
        assert "rare_query" not in queries

    def test_finds_suggested_nodes(self, mg):
        """Failures mentioning 'Python' should suggest the Python node."""
        for _ in range(4):
            mg.log_retrieval_failure("Python asyncio")
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        assert len(analysis) > 0
        a = analysis[0]
        assert a["suggestion_count"] > 0
        assert len(a["suggested_node_ids"]) > 0

    def test_severity_levels(self, mg):
        for _ in range(10):
            mg.log_retrieval_failure("very_frequent")
        for _ in range(3):
            mg.log_retrieval_failure("moderately_frequent")
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        severities = {a["query"]: a["severity"] for a in analysis}
        assert severities["very_frequent"] == "high"
        assert severities["moderately_frequent"] == "medium"

    def test_marks_failures_as_analysed(self, mg):
        for _ in range(4):
            mg.log_retrieval_failure("to_analyse")
        mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        analysed = mg.get_retrieval_failures(analysed_only=True)
        assert all(f["query"] == "to_analyse" for f in analysed)
        assert len(analysed) == 4

    def test_respects_time_window(self, mg):
        old_ts = time.time() - 7200
        for _ in range(5):
            mg.log_retrieval_failure("old_frequent")
        # Manually set old timestamps
        mg.conn.execute(
            "UPDATE retrieval_failures SET timestamp=? WHERE query=?",
            (old_ts, "old_frequent"),
        )
        mg.conn.commit()
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        queries = [a["query"] for a in analysis]
        assert "old_frequent" not in queries

    def test_no_failures_returns_empty(self):
        mg = MemoryGraph()
        assert mg.analyse_retrieval_failures() == []


# =====================================================================
# clear_retrieval_failures
# =====================================================================

class TestClearRetrievalFailures:

    def test_clear_all(self, mg):
        for i in range(5):
            mg.log_retrieval_failure(f"q_{i}")
        deleted = mg.clear_retrieval_failures()
        assert deleted == 5
        assert mg.get_retrieval_failures() == []

    def test_clear_old_only(self, mg):
        mg.log_retrieval_failure("recent")
        mg.conn.execute(
            "INSERT INTO retrieval_failures (query, result_count, top_score, stage, timestamp) "
            "VALUES ('old', 0, 0.0, 'recall', ?)",
            (time.time() - 7200,),
        )
        mg.conn.commit()
        deleted = mg.clear_retrieval_failures(older_than_hours=1)
        assert deleted == 1
        remaining = mg.get_retrieval_failures()
        assert len(remaining) == 1
        assert remaining[0]["query"] == "recent"

    def test_clear_when_empty(self):
        mg = MemoryGraph()
        assert mg.clear_retrieval_failures() == 0


# =====================================================================
# Integration
# =====================================================================

class TestRetrievalFailureIntegration:

    def test_log_after_poor_recall(self, mg):
        """Simulate recall returning no results → log failure."""
        results = mg.recall("nonexistent_xyz")
        if not results:
            mg.log_retrieval_failure("nonexistent_xyz", result_count=0)
        failures = mg.get_retrieval_failures()
        assert len(failures) == 1

    def test_log_after_good_recall_not_needed(self, mg):
        """Good recall should not log failure."""
        results = mg.recall("Python")
        assert len(results) > 0  # should find "Python programming"

    def test_analyse_suggests_missing_edges(self, mg):
        """After repeated failures, analysis suggests nodes that partially match."""
        for _ in range(5):
            mg.log_retrieval_failure("Python concurrent programming")
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        assert len(analysis) == 1
        # Should suggest the Python node (partial match on "Python")
        assert analysis[0]["suggestion_count"] >= 1

    def test_workflow_log_analyse_clear(self, mg):
        """Full workflow: log → analyse → clear."""
        for _ in range(4):
            mg.log_retrieval_failure("missing topic", stage="hybrid")
        # Analyse
        analysis = mg.analyse_retrieval_failures(min_failures=3, since_hours=1)
        assert len(analysis) == 1
        # Clear
        deleted = mg.clear_retrieval_failures()
        assert deleted == 4
        assert mg.get_retrieval_failures() == []
