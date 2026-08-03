"""Tests for what_changed_since() API."""

import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


class TestWhatChangedSince:
    def test_empty_graph(self, mg):
        result = mg.what_changed_since(time.time() - 100)
        assert result["summary"]["total_changes"] == 0

    def test_detects_new_nodes(self, mg):
        t0 = time.time()
        time.sleep(0.01)
        a = mg.add("A")
        b = mg.add("B")
        result = mg.what_changed_since(t0)
        assert result["summary"]["added"] == 2
        labels = [n["label"] for n in result["nodes_added"]]
        assert "A" in labels
        assert "B" in labels

    def test_kind_filter(self, mg):
        t0 = time.time()
        time.sleep(0.01)
        mg.add("fact1", kind="fact")
        mg.add("event1", kind="event")
        result = mg.what_changed_since(t0, kind="fact")
        assert result["summary"]["added"] == 1
        assert result["nodes_added"][0]["kind"] == "fact"

    def test_detects_superseded(self, mg):
        n1 = mg.add("v1", kind="fact")
        time.sleep(0.01)
        t0 = time.time()
        time.sleep(0.01)
        mg.supersede(n1.id, "v2")
        result = mg.what_changed_since(t0)
        assert result["summary"]["superseded"] >= 1

    def test_node_id_filter(self, mg):
        t0 = time.time()
        time.sleep(0.01)
        a = mg.add("A")
        b = mg.add("B")  # not a neighbor of A
        result = mg.what_changed_since(t0, node_id=a.id)
        # B is not in A's neighborhood
        labels = [n["label"] for n in result["nodes_added"]]
        assert "A" in labels  # A was just created, might be included
        assert "B" not in labels

    def test_no_changes_since_now(self, mg):
        mg.add("A")
        result = mg.what_changed_since(time.time())
        assert result["summary"]["total_changes"] == 0

    def test_summary_structure(self, mg):
        t0 = time.time()
        mg.add("A")
        result = mg.what_changed_since(t0)
        assert "total_changes" in result["summary"]
        assert "added" in result["summary"]
        assert "modified" in result["summary"]
        assert "superseded" in result["summary"]
        assert "edges" in result["summary"]

    def test_result_structure(self, mg):
        t0 = time.time()
        mg.add("A")
        result = mg.what_changed_since(t0)
        assert "since" in result
        assert "now" in result
        assert "nodes_added" in result
        assert "nodes_modified" in result
        assert "nodes_superseded" in result
        assert "edges_added" in result
        assert "summary" in result

    def test_code_node_changes(self, mg):
        t0 = time.time()
        time.sleep(0.01)
        fn = mg.add_code_node("login()", "function")
        result = mg.what_changed_since(t0, kind="function")
        assert result["summary"]["added"] == 1
        assert result["nodes_added"][0]["label"] == "login()"

    def test_incremental_changes(self, mg):
        """Multiple calls show only delta."""
        t0 = time.time()
        mg.add("A")
        t1 = time.time()
        result1 = mg.what_changed_since(t0)
        assert result1["summary"]["added"] == 1

        mg.add("B")
        result2 = mg.what_changed_since(t1)
        assert result2["summary"]["added"] == 1
        assert result2["nodes_added"][0]["label"] == "B"

    def test_code_decision_changes(self, mg):
        """Track code decision additions."""
        fn = mg.add_code_node("foo()", "function")
        t0 = time.time()
        time.sleep(0.01)
        mg.record_code_decision([fn.id], "Use bcrypt")
        result = mg.what_changed_since(t0)
        # The decision node should appear as added
        decision_labels = [
            n["label"] for n in result["nodes_added"]
            if n["kind"] == "decision"
        ]
        assert "Use bcrypt" in decision_labels
