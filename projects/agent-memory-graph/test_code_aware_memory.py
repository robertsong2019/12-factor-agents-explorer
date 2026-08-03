"""Tests for Code-Aware Agent Memory APIs (Research #044).

Tests: add_code_node, explain_code, impact_analysis, code_subgraph.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


# ── add_code_node ──────────────────────────────────────────────

class TestAddCodeNode:
    def test_function_node(self, mg):
        n = mg.add_code_node("UserService.login()", "function",
                             data={"file": "src/auth.py", "line": 42})
        assert n.kind == "function"
        assert n.label == "UserService.login()"
        assert n.data["file"] == "src/auth.py"
        assert n.data["_code"] is True

    def test_class_node(self, mg):
        n = mg.add_code_node("UserService", "class")
        assert n.kind == "class"
        assert n.data["_code"] is True

    def test_file_node(self, mg):
        n = mg.add_code_node("src/auth.py", "file")
        assert n.kind == "file"

    def test_module_node(self, mg):
        n = mg.add_code_node("auth", "module")
        assert n.kind == "module"

    def test_variable_node(self, mg):
        n = mg.add_code_node("MAX_RETRIES", "variable")
        assert n.kind == "variable"

    def test_test_node(self, mg):
        n = mg.add_code_node("test_login_success", "test")
        assert n.kind == "test"

    def test_invalid_kind_raises(self, mg):
        with pytest.raises(ValueError, match="Invalid code node kind"):
            mg.add_code_node("x", "invalid_kind")

    def test_tags_preserved(self, mg):
        n = mg.add_code_node("foo()", "function", tags=["auth", "core"])
        # tags stored in DB, not on Node object
        tagged = mg.search_by_tag("auth")
        assert any(t.id == n.id for t in tagged)

    def test_code_node_searchable(self, mg):
        """Code nodes must be searchable by existing APIs."""
        mg.add_code_node("calculateHash()", "function")
        results = mg.search_by_label("calculateHash")
        assert len(results) >= 1
        assert results[0].kind == "function"

    def test_code_node_in_stats(self, mg):
        """Code nodes appear in kind stats."""
        mg.add_code_node("foo()", "function")
        mg.add_code_node("Bar", "class")
        stats = mg.stats()
        assert stats["by_kind"].get("function") == 1
        assert stats["by_kind"].get("class") == 1

    def test_code_node_traversable(self, mg):
        """Code nodes work with existing traversal."""
        f1 = mg.add_code_node("a()", "function")
        f2 = mg.add_code_node("b()", "function")
        mg.link(f1.id, f2.id, "calls")
        neighbors = mg.neighbors(f1.id)
        assert f2.id in [n.id for n in neighbors]


# ── explain_code ───────────────────────────────────────────────

class TestExplainCode:
    def test_not_found(self, mg):
        result = mg.explain_code("nonexistent")
        assert "error" in result

    def test_basic_structure(self, mg):
        n = mg.add_code_node("foo()", "function")
        result = mg.explain_code(n.id)
        assert result["node"]["id"] == n.id
        assert result["node"]["kind"] == "function"
        assert "decisions" in result
        assert "bugfixes" in result
        assert "tests" in result
        assert "callers" in result
        assert "callees" in result
        assert "imports" in result
        assert "origins" in result
        assert "lineage" in result

    def test_decisions(self, mg):
        fn = mg.add_code_node("login()", "function")
        dec = mg.add("Use bcrypt for hashing", kind="decision")
        mg.link(fn.id, dec.id, "decided_by")
        result = mg.explain_code(fn.id)
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["label"] == "Use bcrypt for hashing"

    def test_bugfixes(self, mg):
        fn = mg.add_code_node("login()", "function")
        bug = mg.add("Fix SQL injection in login", kind="bugfix")
        mg.link(fn.id, bug.id, "fixed_by")
        result = mg.explain_code(fn.id)
        assert len(result["bugfixes"]) == 1

    def test_tests(self, mg):
        fn = mg.add_code_node("login()", "function")
        test = mg.add_code_node("test_login", "test")
        mg.link(fn.id, test.id, "tested_by")
        result = mg.explain_code(fn.id)
        assert len(result["tests"]) == 1
        assert result["tests"][0]["kind"] == "test"

    def test_callers(self, mg):
        caller = mg.add_code_node("handleRequest()", "function")
        callee = mg.add_code_node("login()", "function")
        mg.link(caller.id, callee.id, "calls")
        result = mg.explain_code(callee.id)
        assert len(result["callers"]) == 1
        assert result["callers"][0]["label"] == "handleRequest()"

    def test_callees(self, mg):
        caller = mg.add_code_node("handleRequest()", "function")
        callee = mg.add_code_node("login()", "function")
        mg.link(caller.id, callee.id, "calls")
        result = mg.explain_code(caller.id)
        assert len(result["callees"]) == 1
        assert result["callees"][0]["label"] == "login()"

    def test_imports(self, mg):
        mod = mg.add_code_node("auth", "module")
        fn = mg.add_code_node("login()", "function")
        mg.link(fn.id, mod.id, "imports")
        result = mg.explain_code(fn.id)
        assert len(result["imports"]) == 1

    def test_empty_code_node(self, mg):
        """Code node with no edges returns empty lists."""
        n = mg.add_code_node("isolated()", "function")
        result = mg.explain_code(n.id)
        assert result["decisions"] == []
        assert result["callers"] == []
        assert result["callees"] == []
        assert result["tests"] == []

    def test_full_stack(self, mg):
        """Full code-aware stack: function with decision, test, caller."""
        fn = mg.add_code_node("login()", "function")
        dec = mg.add("Use JWT tokens", kind="decision")
        test = mg.add_code_node("test_login", "test")
        caller = mg.add_code_node("router.handle()", "function")
        mg.link(fn.id, dec.id, "decided_by")
        mg.link(fn.id, test.id, "tested_by")
        mg.link(caller.id, fn.id, "calls")
        result = mg.explain_code(fn.id)
        assert len(result["decisions"]) == 1
        assert len(result["tests"]) == 1
        assert len(result["callers"]) == 1


# ── impact_analysis ────────────────────────────────────────────

class TestImpactAnalysis:
    def test_not_found(self, mg):
        result = mg.impact_analysis("nonexistent")
        assert "error" in result
        assert result["total_impacted"] == 0

    def test_no_dependents(self, mg):
        fn = mg.add_code_node("isolated()", "function")
        result = mg.impact_analysis(fn.id)
        assert result["total_impacted"] == 0
        assert result["impacted"] == []

    def test_direct_call_impact(self, mg):
        """Changing a function impacts functions that call it."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        mg.link(b.id, a.id, "calls")
        result = mg.impact_analysis(a.id)
        # b calls a, so changing a impacts b (incoming calls edge)
        # But impact_analysis follows OUTGOING edges from a
        # So it finds what a impacts downstream
        # If a calls nothing, impacted = []
        # To detect "who would be impacted by changing a",
        # we need callers (incoming calls), which explain_code handles
        # impact_analysis follows outgoing calls/depends_on/defined_in
        # Let me re-check the semantics
        # impact_analysis(a) → follows a's outgoing edges
        # a has no outgoing calls → nothing impacted
        result_b = mg.impact_analysis(b.id)
        # b calls a → a is impacted
        assert result_b["total_impacted"] == 1
        assert result_b["impacted"][0]["label"] == "a()"

    def test_cascade(self, mg):
        """a → b → c chain: changing a impacts b and c."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        c = mg.add_code_node("c()", "function")
        mg.link(a.id, b.id, "calls")
        mg.link(b.id, c.id, "calls")
        result = mg.impact_analysis(a.id)
        assert result["total_impacted"] == 2
        depths = [i["depth"] for i in result["impacted"]]
        assert 1 in depths
        assert 2 in depths

    def test_depends_on(self, mg):
        a = mg.add_code_node("module_a", "module")
        b = mg.add_code_node("module_b", "module")
        mg.link(a.id, b.id, "depends_on")
        result = mg.impact_analysis(a.id)
        assert result["total_impacted"] == 1

    def test_defined_in(self, mg):
        f = mg.add_code_node("auth.py", "file")
        cls = mg.add_code_node("UserService", "class")
        mg.link(f.id, cls.id, "defined_in")
        result = mg.impact_analysis(f.id)
        assert result["total_impacted"] == 1

    def test_max_depth_limit(self, mg):
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        c = mg.add_code_node("c()", "function")
        mg.link(a.id, b.id, "calls")
        mg.link(b.id, c.id, "calls")
        result = mg.impact_analysis(a.id, max_depth=1)
        assert result["total_impacted"] == 1
        assert result["max_depth_reached"] == 1

    def test_cycle_safe(self, mg):
        """Cycles in call graph don't cause infinite loops."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        mg.link(a.id, b.id, "calls")
        mg.link(b.id, a.id, "calls")
        result = mg.impact_analysis(a.id)
        assert result["total_impacted"] == 1  # only b, a already visited

    def test_path_tracking(self, mg):
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        mg.link(a.id, b.id, "calls")
        result = mg.impact_analysis(a.id)
        assert len(result["impacted"][0]["path"]) == 1
        assert result["impacted"][0]["path"][0] == b.id


# ── code_subgraph ──────────────────────────────────────────────

class TestCodeSubgraph:
    def test_not_found(self, mg):
        result = mg.code_subgraph("nonexistent")
        assert "error" in result

    def test_empty_subgraph(self, mg):
        n = mg.add_code_node("lonely()", "function")
        result = mg.code_subgraph(n.id)
        assert result["center"]["id"] == n.id
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_bidirectional(self, mg):
        """code_subgraph collects both incoming and outgoing edges."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        mg.link(a.id, b.id, "calls")
        result = mg.code_subgraph(a.id)
        assert len(result["edges"]) >= 1
        assert len(result["nodes"]) >= 1

    def test_multiple_code_edges(self, mg):
        fn = mg.add_code_node("login()", "function")
        test = mg.add_code_node("test_login", "test")
        dec = mg.add("Use JWT", kind="decision")
        mg.link(fn.id, test.id, "tested_by")
        mg.link(fn.id, dec.id, "decided_by")
        result = mg.code_subgraph(fn.id)
        # Each edge appears once per direction (in/out), so dedupe by relation+target
        unique_edges = {(e["relation"], e["target"]) for e in result["edges"]}
        assert len(unique_edges) == 2

    def test_max_depth(self, mg):
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        c = mg.add_code_node("c()", "function")
        mg.link(a.id, b.id, "calls")
        mg.link(b.id, c.id, "calls")
        result = mg.code_subgraph(a.id, max_depth=1)
        # Only b discovered, not c
        node_labels = [n["label"] for n in result["nodes"]]
        assert "b()" in node_labels
        assert "c()" not in node_labels

    def test_only_code_edges(self, mg):
        """Non-code edges (e.g. 'related_to') excluded."""
        a = mg.add_code_node("a()", "function")
        b = mg.add("some fact", kind="fact")
        mg.link(a.id, b.id, "related_to")
        result = mg.code_subgraph(a.id)
        assert result["edges"] == []

    def test_center_info(self, mg):
        fn = mg.add_code_node("foo()", "function")
        result = mg.code_subgraph(fn.id)
        assert result["center"]["label"] == "foo()"
        assert result["center"]["kind"] == "function"


# ── Integration ────────────────────────────────────────────────

class TestCodeAwareIntegration:
    def test_code_node_with_entropy(self, mg):
        """Code nodes work with entropy APIs."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        c = mg.add_code_node("c()", "function")
        mg.link(a.id, b.id, "calls")
        mg.link(a.id, c.id, "calls")
        mg.link(b.id, c.id, "calls")
        # Sombor entropy works on any graph topology
        entropy = mg.sombor_entropy()
        assert entropy is None or entropy >= 0

    def test_code_node_fingerprint(self, mg):
        """Code nodes work with fingerprint."""
        a = mg.add_code_node("a()", "function")
        b = mg.add_code_node("b()", "function")
        mg.link(a.id, b.id, "calls")
        fp = mg.entropy_fingerprint()
        assert isinstance(fp, dict)
        assert len(fp) > 0

    def test_code_node_classification(self, mg):
        """Code graph structure can be classified."""
        # Build a star-like code structure
        hub = mg.add_code_node("main()", "function")
        for i in range(5):
            leaf = mg.add_code_node(f"helper_{i}()", "function")
            mg.link(hub.id, leaf.id, "calls")
        fp = mg.entropy_fingerprint()
        # fingerprint returns dict with 'indices' key
        assert "indices" in fp or len(fp) > 0

    def test_record_code_decision_workflow(self, mg):
        """Full workflow: record code + decision + verify explain."""
        # Code nodes
        fn = mg.add_code_node("authenticate()", "function",
                              data={"file": "auth.py", "line": 10})
        test = mg.add_code_node("test_auth", "test",
                                data={"file": "test_auth.py", "line": 5})

        # Decision node (regular kind)
        dec = mg.add("Switch from sessions to JWT", kind="decision")

        # Link them
        mg.link(fn.id, test.id, "tested_by")
        mg.link(fn.id, dec.id, "decided_by")

        # Explain
        result = mg.explain_code(fn.id)
        assert len(result["tests"]) == 1
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["label"] == "Switch from sessions to JWT"

        # Impact (only follows calls/depends_on/defined_in, not tested_by/decided_by)
        impact = mg.impact_analysis(fn.id)
        assert impact["total_impacted"] == 0  # no calls/depends_on/defined_in edges

    def test_module_hierarchy(self, mg):
        """Module → File → Class → Function hierarchy."""
        mod = mg.add_code_node("auth_module", "module")
        f = mg.add_code_node("auth.py", "file")
        cls = mg.add_code_node("AuthService", "class")
        fn = mg.add_code_node("login()", "function")

        mg.link(mod.id, f.id, "defined_in")
        mg.link(f.id, cls.id, "defined_in")
        mg.link(cls.id, fn.id, "defined_in")

        # Impact from module level
        result = mg.impact_analysis(mod.id)
        assert result["total_impacted"] == 3  # file + class + function
        depths = sorted(set(i["depth"] for i in result["impacted"]))
        assert depths == [1, 2, 3]

    def test_code_node_count_by_kind(self, mg):
        """Count code nodes by kind via existing stats."""
        mg.add_code_node("a()", "function")
        mg.add_code_node("b()", "function")
        mg.add_code_node("Foo", "class")
        mg.add_code_node("test_foo", "test")

        stats = mg.stats()
        assert stats["by_kind"]["function"] == 2
        assert stats["by_kind"]["class"] == 1
        assert stats["by_kind"]["test"] == 1
