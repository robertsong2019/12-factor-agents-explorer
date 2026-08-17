"""Tests for graph_changelog() — Cycle 460."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from memory_graph import MemoryGraph


class TestGraphChangelog:
    """Cycle 460: graph_changelog — readable evolution log."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.graph_changelog() == []

    def test_returns_list(self):
        mg = MemoryGraph()
        r = mg.graph_changelog()
        assert isinstance(r, list)

    def test_after_label_change(self):
        mg = MemoryGraph()
        n = mg.add("original")
        mg.update_node(n.id, label="updated")
        log = mg.graph_changelog()
        assert len(log) >= 1
        assert log[0]['change_type'] == 'label'
        assert log[0]['old_value'] == 'original'
        assert log[0]['new_value'] == 'updated'

    def test_after_kind_change(self):
        mg = MemoryGraph()
        n = mg.add("test", kind="fact")
        mg.update_node(n.id, kind="concept")
        log = mg.graph_changelog()
        assert any(e['change_type'] == 'kind' for e in log)

    def test_filter_by_node_id(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.update_node(a.id, label="A2")
        mg.update_node(b.id, label="B2")
        log = mg.graph_changelog(node_id=a.id)
        assert all(e['node_id'] == a.id for e in log)
        assert len(log) >= 1

    def test_limit(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"n{j}") for j in range(5)]
        for j, nd in enumerate(nodes):
            mg.update_node(nd.id, label=f"n{j}_v2")
        log = mg.graph_changelog(limit=3)
        assert len(log) <= 3

    def test_timestamp_is_string(self):
        mg = MemoryGraph()
        n = mg.add("test")
        mg.update_node(n.id, label="test2")
        log = mg.graph_changelog()
        if log:
            assert isinstance(log[0]['timestamp'], str)

    def test_dict_keys(self):
        mg = MemoryGraph()
        n = mg.add("test")
        mg.update_node(n.id, label="test2")
        log = mg.graph_changelog()
        if log:
            expected = {'id', 'node_id', 'change_type', 'old_value', 'new_value', 'timestamp'}
            assert expected.issubset(set(log[0].keys()))

    def test_no_duplicate_entries(self):
        mg = MemoryGraph()
        n = mg.add("test")
        mg.update_node(n.id, label="test2")
        log = mg.graph_changelog()
        # Should only have one label change entry for this update
        label_entries = [e for e in log if e['change_type'] == 'label'
                          and e['old_value'] == 'test']
        assert len(label_entries) == 1

    def test_multiple_changes_ordered(self):
        mg = MemoryGraph()
        n = mg.add("first")
        mg.update_node(n.id, label="second")
        mg.update_node(n.id, label="third")
        log = mg.graph_changelog()
        labels = [e['new_value'] for e in log if e['change_type'] == 'label']
        # Most recent first
        if len(labels) >= 2:
            assert labels[0] == 'third'
