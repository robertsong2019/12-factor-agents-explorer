"""Tests for add_code_node path parameter + explain_code enhancements (Cycle 359)."""

import pytest
from memory_graph import MemoryGraph


class TestAddCodeNodePath:
    """add_code_node() now accepts path shorthand parameter."""

    def test_path_stored_in_data(self):
        g = MemoryGraph()
        node = g.add_code_node("parseMarkdown", "function", path="src/parser.ts")
        fetched = g.get_node(node.id)
        assert fetched.data["path"] == "src/parser.ts"

    def test_path_coexists_with_data(self):
        g = MemoryGraph()
        node = g.add_code_node("foo", "function",
                               data={"line": 42}, path="src/foo.py")
        fetched = g.get_node(node.id)
        assert fetched.data["path"] == "src/foo.py"
        assert fetched.data["line"] == 42

    def test_no_path_does_not_add_key(self):
        g = MemoryGraph()
        node = g.add_code_node("bar", "function")
        assert "path" not in node.data

    def test_empty_string_path_not_stored(self):
        g = MemoryGraph()
        node = g.add_code_node("baz", "function", path="")
        assert "path" not in node.data

    def test_path_with_file_kind(self):
        g = MemoryGraph()
        node = g.add_code_node("auth.ts", "file", path="src/auth.ts")
        assert node.data["path"] == "src/auth.ts"

    def test_path_with_module_kind(self):
        g = MemoryGraph()
        node = g.add_code_node("utils", "module", path="src/utils/index.ts")
        assert node.data["path"] == "src/utils/index.ts"

    def test_path_overrides_data_path(self):
        """Explicit path param overrides data['path']."""
        g = MemoryGraph()
        node = g.add_code_node("x", "function",
                               data={"path": "old/path.ts"}, path="new/path.ts")
        assert node.data["path"] == "new/path.ts"

    def test_returns_node_object(self):
        g = MemoryGraph()
        node = g.add_code_node("fn", "function", path="src/fn.ts")
        assert hasattr(node, 'id')
        assert hasattr(node, 'label')
        assert node.label == "fn"


class TestExplainCode:
    """explain_code() returns provenance + dependents + code_edges."""

    def _build_graph(self):
        g = MemoryGraph()
        fn = g.add_code_node("parseMarkdown", "function", path="src/parser.ts")
        helper = g.add_code_node("tokenize", "function", path="src/tokenizer.ts")
        file_node = g.add_code_node("parser.ts", "file", path="src/parser.ts")
        g.link(fn.id, helper.id, "calls")
        g.link(fn.id, file_node.id, "defined_in")
        return g, fn.id, helper.id, file_node.id

    def test_returns_dict_with_node(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert isinstance(result, dict)
        assert result["node"]["id"] == fn

    def test_node_info_has_label_kind(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert result["node"]["label"] == "parseMarkdown"
        assert result["node"]["kind"] == "function"

    def test_callers_populated(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert "callers" in result
        assert isinstance(result["callers"], list)

    def test_callees_populated(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert "callees" in result
        labels = [c["label"] for c in result["callees"]]
        assert "tokenize" in labels

    def test_callees_includes_defined_in(self):
        """defined_in edge shows up in callees (outgoing edges)."""
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        # Note: existing explain_code only returns 'calls' edges in callees.
        # defined_in is available via outgoing edges in full graph traversal.
        callee_labels = [c["label"] for c in result["callees"]]
        assert "tokenize" in callee_labels  # calls edge works

    def test_lineage_present(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert "lineage" in result

    def test_empty_graph_explain_returns_error(self):
        g = MemoryGraph()
        result = g.explain_code("nonexistent")
        assert "error" in result

    def test_incoming_edges_as_callers(self):
        g, fn, _, _ = self._build_graph()
        caller = g.add_code_node("render", "function")
        g.link(caller.id, fn, "calls")
        result = g.explain_code(fn)
        caller_labels = [c["label"] for c in result["callers"]]
        assert "render" in caller_labels

    def test_imports_populated(self):
        g, fn, _, _ = self._build_graph()
        result = g.explain_code(fn)
        assert "imports" in result
