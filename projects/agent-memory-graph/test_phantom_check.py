"""
Tests for phantom commit detector — prevents class shadowing & phantom APIs.

Covers:
- AST-based definition extraction
- Shadowing detection (same file, same name)
- Commit message API extraction & verification
- Edge cases (empty files, syntax errors, nested classes)
"""

import ast
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Import the module under test
_project_root = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.join(_project_root, "scripts")
sys.path.insert(0, _scripts_dir)
from phantom_check import (
    find_definitions,
    detect_shadowing,
    extract_api_names_from_commit_msg,
    verify_apis_exist,
    check_files,
    format_report,
)


class TestFindDefinitions(unittest.TestCase):
    """Test AST-based definition extraction."""

    def test_single_class(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class Foo:\n    pass\n")
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertIn("Foo", defs)
        self.assertEqual(len(defs["Foo"]), 1)

    def test_nested_class(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                class Outer:
                    class Inner:
                        pass
                    def method(self):
                        pass
            """))
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertIn("Outer", defs)
        self.assertIn("Outer.Inner", defs)
        self.assertIn("Outer.method", defs)

    def test_multiple_functions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def alpha():\n    pass\ndef beta():\n    pass\n")
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertIn("alpha", defs)
        self.assertIn("beta", defs)

    def test_async_function(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("async def fetch_data():\n    pass\n")
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertIn("fetch_data", defs)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertEqual(defs, {})

    def test_syntax_error_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(:\n    pass\n")
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertEqual(defs, {})

    def test_nonexistent_file(self):
        defs = find_definitions("/nonexistent/path/file.py")
        self.assertEqual(defs, {})

    def test_dataclass_definitions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                from dataclasses import dataclass

                @dataclass
                class Node:
                    id: str
                    label: str
            """))
            f.flush()
            defs = find_definitions(f.name)
        os.unlink(f.name)
        self.assertIn("Node", defs)


class TestDetectShadowing(unittest.TestCase):
    """Test shadowing detection."""

    def test_no_shadowing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class A:\n    pass\nclass B:\n    pass\n")
            f.flush()
            shadows = detect_shadowing(f.name)
        os.unlink(f.name)
        self.assertEqual(shadows, [])

    def test_class_shadowing(self):
        """The exact problem from 07-07: duplicate class definition."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                class MemoryGraph:
                    def real_method(self):
                        return True

                # ... later in file ...
                class MemoryGraph:  # SHADOW! First definition lost
                    def fake_method(self):
                        return False
            """))
            f.flush()
            shadows = detect_shadowing(f.name)
        os.unlink(f.name)
        self.assertEqual(len(shadows), 1)
        self.assertEqual(shadows[0][0], "MemoryGraph")
        self.assertEqual(len(shadows[0][1]), 2)  # defined twice

    def test_function_shadowing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def compute():\n    pass\ndef compute():\n    pass\n")
            f.flush()
            shadows = detect_shadowing(f.name)
        os.unlink(f.name)
        self.assertEqual(len(shadows), 1)
        self.assertEqual(shadows[0][0], "compute")

    def test_nested_no_shadowing(self):
        """Methods with same name in different classes are NOT shadowing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                class A:
                    def method(self): pass
                class B:
                    def method(self): pass
            """))
            f.flush()
            shadows = detect_shadowing(f.name)
        os.unlink(f.name)
        # A.method and B.method are different full names
        self.assertEqual(shadows, [])

    def test_multiple_shadows(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                class Foo: pass
                class Foo: pass
                def bar(): pass
                def bar(): pass
                def bar(): pass
            """))
            f.flush()
            shadows = detect_shadowing(f.name)
        os.unlink(f.name)
        self.assertEqual(len(shadows), 2)
        names = {s[0] for s in shadows}
        self.assertEqual(names, {"Foo", "bar"})
        # bar defined 3 times
        bar_shadow = [s for s in shadows if s[0] == "bar"][0]
        self.assertEqual(len(bar_shadow[1]), 3)


class TestExtractApiNames(unittest.TestCase):
    """Test commit message API extraction."""

    def test_backtick_identifiers(self):
        msg = "Added `retrieve()` and `graph_rerank()` to the pipeline"
        apis = extract_api_names_from_commit_msg(msg)
        self.assertIn("retrieve", apis)
        self.assertIn("graph_rerank", apis)

    def test_snake_case_with_parens(self):
        msg = "Cycle 218: edge_current_flow_betweenness + graph_rerank CF integration"
        apis = extract_api_names_from_commit_msg(msg)
        self.assertIn("edge_current_flow_betweenness", apis)

    def test_camelcase_class_names(self):
        msg = "Added MemoryGraph and Node classes"
        apis = extract_api_names_from_commit_msg(msg)
        self.assertIn("MemoryGraph", apis)
        self.assertIn("Node", apis)

    def test_filters_common_english(self):
        msg = "This Cycle was The best. These changes fix a bug."
        apis = extract_api_names_from_commit_msg(msg)
        # "This", "The", "These" should be filtered
        self.assertNotIn("This", apis)
        self.assertNotIn("The", apis)
        self.assertNotIn("These", apis)

    def test_empty_message(self):
        apis = extract_api_names_from_commit_msg("")
        self.assertEqual(apis, [])

    def test_filters_scholar_names(self):
        msg = "Based on Brandes and Fleischer 2007, Kirchhoff index implementation"
        apis = extract_api_names_from_commit_msg(msg)
        self.assertNotIn("Brandes", apis)
        self.assertNotIn("Fleischer", apis)
        self.assertNotIn("Kirchhoff", apis)

    def test_mixed_patterns(self):
        msg = "Cycle 215: `kirchhoff_index()` + spanning_tree_count() added to MemoryGraph"
        apis = extract_api_names_from_commit_msg(msg)
        self.assertIn("kirchhoff_index", apis)
        self.assertIn("spanning_tree_count", apis)
        self.assertIn("MemoryGraph", apis)


class TestVerifyApisExist(unittest.TestCase):
    """Test API verification against source code."""

    def test_all_apis_exist(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(textwrap.dedent("""
                class MemoryGraph:
                    def retrieve(self): pass
                    def graph_rerank(self): pass
            """))
            f.flush()
            results = verify_apis_exist(
                ["MemoryGraph", "retrieve", "graph_rerank"],
                [f.name]
            )
        os.unlink(f.name)
        missing = [a for a, s in results if s == "missing"]
        self.assertEqual(missing, [])

    def test_phantom_api_detected(self):
        """The key test: API in commit message but NOT in code."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class RealClass:\n    pass\n")
            f.flush()
            results = verify_apis_exist(
                ["RealClass", "PhantomClass", "phantom_method"],
                [f.name]
            )
        os.unlink(f.name)
        statuses = dict(results)
        self.assertEqual(statuses["RealClass"], "found")
        self.assertEqual(statuses["PhantomClass"], "missing")
        self.assertEqual(statuses["phantom_method"], "missing")

    def test_substring_matching(self):
        """Partial name match should count as found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def compute_centrality_betweenness():\n    pass\n")
            f.flush()
            results = verify_apis_exist(
                ["centrality_betweenness"],  # part of the full name
                [f.name]
            )
        os.unlink(f.name)
        statuses = dict(results)
        self.assertEqual(statuses["centrality_betweenness"], "found")

    def test_multiple_source_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f1, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f2:
            f1.write("class Alpha:\n    pass\n")
            f2.write("class Beta:\n    pass\n")
            f1.flush()
            f2.flush()
            results = verify_apis_exist(
                ["Alpha", "Beta"],
                [f1.name, f2.name]
            )
        os.unlink(f1.name)
        os.unlink(f2.name)
        statuses = dict(results)
        self.assertEqual(statuses["Alpha"], "found")
        self.assertEqual(statuses["Beta"], "found")

    def test_empty_source_files(self):
        results = verify_apis_exist(["Anything"], [])
        statuses = dict(results)
        self.assertEqual(statuses["Anything"], "missing")


class TestCheckFiles(unittest.TestCase):
    """Test the combined check_files function."""

    def test_clean_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class Clean:\n    pass\n")
            f.flush()
            report = check_files([f.name])
        os.unlink(f.name)
        self.assertEqual(report["shadowing"], [])
        self.assertEqual(report["files_checked"], 1)
        self.assertGreater(report["total_defs"], 0)

    def test_shadowing_detected(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class Dup:\n    pass\nclass Dup:\n    pass\n")
            f.flush()
            report = check_files([f.name])
        os.unlink(f.name)
        self.assertEqual(len(report["shadowing"]), 1)
        self.assertEqual(report["shadowing"][0]["name"], "Dup")

    def test_non_python_files_skipped(self):
        report = check_files(["readme.md", "data.json"])
        self.assertEqual(report["files_checked"], 0)

    def test_nonexistent_files_skipped(self):
        report = check_files(["/nonexistent/file.py"])
        self.assertEqual(report["files_checked"], 0)

    def test_mixed_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f1, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f2:
            f1.write("class Good:\n    pass\n")
            f2.write("class Bad:\n    pass\nclass Bad:\n    pass\n")
            f1.flush()
            f2.flush()
            report = check_files([f1.name, f2.name])
        os.unlink(f1.name)
        os.unlink(f2.name)
        self.assertEqual(report["files_checked"], 2)
        self.assertEqual(len(report["shadowing"]), 1)


class TestFormatReport(unittest.TestCase):
    """Test report formatting."""

    def test_clean_report(self):
        report = {"shadowing": [], "total_defs": 10, "files_checked": 2}
        text = format_report(report)
        self.assertIn("✅ No shadowing detected", text)
        self.assertIn("Files checked: 2", text)

    def test_shadow_report(self):
        report = {
            "shadowing": [
                {"file": "test.py", "name": "Foo", "lines": [1, 10]}
            ],
            "total_defs": 5,
            "files_checked": 1,
        }
        text = format_report(report)
        self.assertIn("🚨 SHADOWING DETECTED", text)
        self.assertIn("Foo", text)
        self.assertIn("[1, 10]", text)


class TestRealProjectFiles(unittest.TestCase):
    """Integration test: check the actual project source files.

    Note: These tests document the KNOWN technical debt of duplicate method
    definitions in memory_graph.py (historical re-implementations that didn't
    remove the old version). The phantom_check tool correctly detects these.
    """

    def setUp(self):
        self.project_root = Path(__file__).parent
        self.main_file = str(self.project_root / "memory_graph.py")

    # Known shadowing in memory_graph.py (methods re-implemented, old not removed)
    KNOWN_SHADOWING = {
        "MemoryGraph.shortest_path",
        "MemoryGraph.find_roots",
        "MemoryGraph.find_leaves",
        "MemoryGraph.eigenvector_centrality",
        "MemoryGraph.pagerank",
        "MemoryGraph.k_core",
        "MemoryGraph.merge_graph",
        "MemoryGraph.assortativity_degree",
        "MemoryGraph.clustering_coefficient",
        "MemoryGraph.node_similarity",
    }

    def test_shadowing_detected_in_main_source(self):
        """The phantom_check tool should detect known shadowing in memory_graph.py."""
        shadows = detect_shadowing(self.main_file)
        shadow_names = {s[0] for s in shadows}
        # All known shadowing should be detected
        found = shadow_names & self.KNOWN_SHADOWING
        self.assertEqual(found, self.KNOWN_SHADOWING,
            f"Missing known shadowing detection. Got {shadow_names}")

    def test_no_new_shadowing_in_main_source(self):
        """No shadowing beyond the known technical debt should exist."""
        shadows = detect_shadowing(self.main_file)
        shadow_names = {s[0] for s in shadows}
        unknown = shadow_names - self.KNOWN_SHADOWING
        self.assertEqual(unknown, set(),
            f"NEW shadowing detected (not in known list): {unknown}")

    def test_phantom_check_on_project_excludes_venv(self):
        """Running check_files on the project should not scan venv/site-packages."""
        exclude = {"__pycache__", "dist", ".egg-info", ".git", "node_modules",
                   "venv", ".venv", "site-packages", "lib", "env", ".env", ".tox"}
        files = []
        for p in self.project_root.rglob("*.py"):
            if not any(part in exclude for part in p.parts):
                files.append(str(p))

        report = check_files(files)
        # Should only include our project files, not venv
        for s in report["shadowing"]:
            self.assertNotIn("site-packages", s["file"],
                "venv/site-packages file scanned!")
            self.assertNotIn(".venv", s["file"],
                ".venv file scanned!")

    def test_all_definitions_present(self):
        """Verify the source file has substantial definitions (parse succeeded)."""
        defs = find_definitions(self.main_file)
        self.assertGreater(len(defs), 100,
            f"Expected 100+ definitions, got {len(defs)}. AST parse may have failed.")


class TestIntegrationCommitMsgVerification(unittest.TestCase):
    """End-to-end: verify commit message APIs against actual source."""

    def test_real_commit_message_apis_exist(self):
        """APIs from recent commit messages should all exist in the source."""
        project_root = Path(__file__).parent
        main_file = str(project_root / "memory_graph.py")

        # APIs from recent commits (Cycle 215-218)
        recent_apis = [
            "kirchhoff_index",
            "spanning_tree_count",
            "spectral_gap",
            "graph_energy",
            "hyper_wiener_index",
            "balaban_index",
            "edge_current_flow_betweenness",
            "current_flow_betweenness",
            "current_flow_closeness",
            "natural_connectivity",
            "effective_resistance",
            "information_centrality",
        ]

        results = verify_apis_exist(recent_apis, [main_file])
        missing = [(a, s) for a, s in results if s == "missing"]

        # All should be found (not phantom)
        self.assertEqual(missing, [],
            f"Phantom APIs detected (in commit msgs but not in code):\n" +
            "\n".join(f"  {a}" for a, _ in missing))


if __name__ == "__main__":
    unittest.main()
