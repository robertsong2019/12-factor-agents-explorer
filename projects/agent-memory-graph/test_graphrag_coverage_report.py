"""Tests for graphrag_coverage_report() — global KG retrieval health diagnostic.

Cycle 431: Companion to graphrag_query/explain. While graphrag_explain
diagnoses a single query, coverage_report provides KG-wide health metrics.
"""

import json
import pytest
from memory_graph import MemoryGraph


class TestEmptyGraph:
    """Empty graph edge cases."""

    def test_empty_graph_returns_zeroes(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["total_nodes"] == 0
        assert r["total_edges"] == 0
        assert r["health_score"] == 0.0
        assert r["keyword_count"] == 0

    def test_empty_graph_suggestions_mention_extract(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert any("extract_from_text" in s for s in r["suggestions"])

    def test_empty_graph_top_keywords_empty(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["top_keywords"] == []


class TestLabelCoverage:
    """Label coverage metrics."""

    def test_all_nodes_have_labels(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        r = mg.graphrag_coverage_report()
        assert r["label_coverage"] == 1.0

    def test_partial_label_coverage(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        # Add node then blank its label
        n = mg.add("temp", "skill")
        mg.conn.execute("UPDATE nodes SET label='' WHERE id=?", (n.id,))
        mg.conn.commit()
        r = mg.graphrag_coverage_report()
        assert r["label_coverage"] == pytest.approx(2/3, abs=0.01)


class TestTagCoverage:
    """Tag coverage metrics."""

    def test_no_tags(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        r = mg.graphrag_coverage_report()
        assert r["tag_coverage"] == 0.0
        assert r["avg_tags_per_node"] == 0.0

    def test_partial_tag_coverage(self):
        mg = MemoryGraph()
        mg.add("Python", "skill", tags=["lang", "dynamic"])
        mg.add("Rust", "skill", tags=["lang"])
        mg.add("C", "skill")
        r = mg.graphrag_coverage_report()
        assert r["tag_coverage"] == pytest.approx(2/3, abs=0.01)
        assert r["avg_tags_per_node"] == pytest.approx(1.0, abs=0.01)

    def test_full_tag_coverage(self):
        mg = MemoryGraph()
        mg.add("Python", "skill", tags=["lang"])
        mg.add("Rust", "skill", tags=["lang"])
        r = mg.graphrag_coverage_report()
        assert r["tag_coverage"] == 1.0


class TestKeywordIndex:
    """Keyword extraction from labels and tags."""

    def test_keyword_count_unique(self):
        mg = MemoryGraph()
        mg.add("Python Programming", "skill")
        mg.add("Rust Programming", "skill")
        # "programming" appears twice, "python" and "rust" once each
        r = mg.graphrag_coverage_report()
        assert r["keyword_count"] >= 3  # python, rust, programming

    def test_top_keywords_sorted_desc(self):
        mg = MemoryGraph()
        mg.add("Python Programming Language", "skill")
        mg.add("Rust Programming", "skill")
        mg.add("Go Programming", "skill")
        r = mg.graphrag_coverage_report()
        kws = [k for k, _ in r["top_keywords"]]
        freqs = [f for _, f in r["top_keywords"]]
        assert "programming" in kws
        assert freqs == sorted(freqs, reverse=True)

    def test_stopwords_excluded(self):
        mg = MemoryGraph()
        mg.add("The Python", "skill")  # "the" should be excluded
        r = mg.graphrag_coverage_report()
        kws = dict(r["top_keywords"])
        assert "the" not in kws
        assert "python" in kws

    def test_tags_contribute_to_keywords(self):
        mg = MemoryGraph()
        mg.add("X", "skill", tags=["machine_learning"])
        mg.add("Y", "skill", tags=["machine_learning", "deep_learning"])
        r = mg.graphrag_coverage_report()
        kws = dict(r["top_keywords"])
        assert "machine_learning" in kws
        assert kws["machine_learning"] == 2

    def test_top_keywords_limited_to_15(self):
        mg = MemoryGraph()
        for i in range(20):
            mg.add(f"UniqueKeyword{i}", "skill")
        r = mg.graphrag_coverage_report()
        assert len(r["top_keywords"]) <= 15

    def test_short_keywords_excluded(self):
        mg = MemoryGraph()
        mg.add("A", "skill")  # single char → no keyword
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        kws = dict(r["top_keywords"])
        # Single-char labels may not produce keywords (len > 1 filter)
        assert "python" in kws


class TestOrphanRate:
    """Orphan node detection (degree=0)."""

    def test_all_orphans(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        mg.add("B", "skill")
        r = mg.graphrag_coverage_report()
        assert r["orphan_count"] == 2
        assert r["orphan_rate"] == 1.0

    def test_no_orphans(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        mg.link(a.id, b.id, "related")
        r = mg.graphrag_coverage_report()
        assert r["orphan_count"] == 0
        assert r["orphan_rate"] == 0.0

    def test_partial_orphan_rate(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        mg.add("C", "skill")  # orphan
        mg.link(a.id, b.id, "related")
        r = mg.graphrag_coverage_report()
        assert r["orphan_count"] == 1
        assert r["orphan_rate"] == pytest.approx(1/3, abs=0.01)


class TestDegreeStats:
    """Degree distribution statistics."""

    def test_min_degree(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        c = mg.add("C", "skill")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        r = mg.graphrag_coverage_report()
        assert r["degree_stats"]["min"] == 1  # b and c have degree 1

    def test_max_degree(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        c = mg.add("C", "skill")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        r = mg.graphrag_coverage_report()
        assert r["degree_stats"]["max"] == 2  # a has out-degree 2

    def test_mean_degree(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        mg.link(a.id, b.id, "r")
        r = mg.graphrag_coverage_report()
        # a has degree 1, b has degree 1 → mean = 1.0
        assert r["degree_stats"]["mean"] == pytest.approx(1.0, abs=0.01)

    def test_median_degree(self):
        mg = MemoryGraph()
        a = mg.add("Hub", "skill")
        for label in ["B", "C", "D", "E"]:
            n = mg.add(label, "skill")
            mg.link(a.id, n.id, "r")
        r = mg.graphrag_coverage_report()
        assert r["degree_stats"]["median"] >= 1


class TestKindDistribution:
    """Kind distribution breakdown."""

    def test_single_kind(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        mg.add("B", "skill")
        r = mg.graphrag_coverage_report()
        assert r["kind_distribution"] == {"skill": 2}

    def test_multiple_kinds(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        mg.add("B", "concept")
        mg.add("C", "person")
        r = mg.graphrag_coverage_report()
        assert r["kind_distribution"]["skill"] == 1
        assert r["kind_distribution"]["concept"] == 1
        assert r["kind_distribution"]["person"] == 1

    def test_none_kind_labeled_unknown(self):
        mg = MemoryGraph()
        mg.add("A")  # no kind specified, defaults to 'fact'
        r = mg.graphrag_coverage_report()
        # Default kind is 'fact' when none specified
        assert sum(r["kind_distribution"].values()) == 1
        assert len(r["kind_distribution"]) == 1


class TestMatchability:
    """Matchability tier classification."""

    def test_high_tier_well_connected_and_tagged(self):
        mg = MemoryGraph()
        a = mg.add("Python Language", "skill", tags=["programming"])
        b = mg.add("Rust Language", "skill", tags=["programming"])
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "related")
        r = mg.graphrag_coverage_report()
        assert r["matchability"]["high"] >= 2

    def test_medium_tier_connected_but_no_tags(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")  # short label, no tags
        b = mg.add("B", "skill")
        mg.link(a.id, b.id, "r")
        r = mg.graphrag_coverage_report()
        assert r["matchability"]["medium"] >= 2

    def test_low_tier_orphans(self):
        mg = MemoryGraph()
        mg.add("X", "skill")  # orphan, no tags
        r = mg.graphrag_coverage_report()
        assert r["matchability"]["low"] >= 1

    def test_tiers_sum_to_total(self):
        mg = MemoryGraph()
        a = mg.add("Python Language", "skill", tags=["prog"])
        b = mg.add("Rust Language", "skill", tags=["prog"])
        c = mg.add("Go", "skill")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")
        mg.link(a.id, c.id, "r")
        r = mg.graphrag_coverage_report()
        m = r["matchability"]
        assert m["high"] + m["medium"] + m["low"] == r["total_nodes"]


class TestSparseNodes:
    """Sparse node detection."""

    def test_sparse_nodes_found(self):
        mg = MemoryGraph()
        a = mg.add("A", "skill")
        b = mg.add("B", "skill")
        mg.link(a.id, b.id, "r")
        mg.add("C", "skill")  # degree 0, no tags → sparse
        r = mg.graphrag_coverage_report()
        # C is sparse
        assert len(r["sparse_nodes"]) >= 1

    def test_no_sparse_nodes(self):
        mg = MemoryGraph()
        a = mg.add("Python Language", "skill", tags=["prog"])
        b = mg.add("Rust Language", "skill", tags=["prog"])
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")
        r = mg.graphrag_coverage_report()
        assert len(r["sparse_nodes"]) == 0

    def test_sparse_capped_at_50(self):
        mg = MemoryGraph()
        for i in range(60):
            mg.add(f"Node{i}", "skill")  # all orphans → all sparse
        r = mg.graphrag_coverage_report()
        assert len(r["sparse_nodes"]) <= 50


class TestHealthScore:
    """Composite health score."""

    def test_health_score_range(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        assert 0.0 <= r["health_score"] <= 1.0

    def test_perfect_health_score(self):
        mg = MemoryGraph()
        a = mg.add("Python Language", "skill", tags=["programming", "dynamic"])
        b = mg.add("Rust Language", "skill", tags=["programming", "static"])
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "related")
        r = mg.graphrag_coverage_report()
        assert r["health_score"] > 0.6

    def test_poor_health_score(self):
        mg = MemoryGraph()
        mg.add("X", "skill")  # orphan, no tags, short label
        r = mg.graphrag_coverage_report()
        assert r["health_score"] < 0.5

    def test_empty_graph_zero_health(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["health_score"] == 0.0


class TestSuggestions:
    """Context-aware suggestions."""

    def test_empty_graph_suggestion(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert any("extract_from_text" in s for s in r["suggestions"])

    def test_low_tag_coverage_suggestion(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        r = mg.graphrag_coverage_report()
        assert any("tag" in s.lower() for s in r["suggestions"])

    def test_high_orphan_rate_suggestion(self):
        mg = MemoryGraph()
        for _ in range(5):
            mg.add("Node", "skill")
        r = mg.graphrag_coverage_report()
        assert any("orphan" in s.lower() for s in r["suggestions"])

    def test_healthy_graph_suggestion(self):
        mg = MemoryGraph()
        a = mg.add("Python Language", "skill", tags=["programming", "dynamic"])
        b = mg.add("Rust Language", "skill", tags=["programming", "static"])
        c = mg.add("Go Language", "skill", tags=["programming", "static"])
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "related")
        mg.link(a.id, c.id, "related")
        mg.link(c.id, a.id, "related")
        mg.link(b.id, c.id, "related")
        mg.link(c.id, b.id, "related")
        r = mg.graphrag_coverage_report()
        assert any("good" in s.lower() for s in r["suggestions"])

    def test_sparse_nodes_suggestion(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        assert any("sparse" in s.lower() for s in r["suggestions"])


class TestReturnStructure:
    """Return dict structure completeness."""

    def test_all_keys_present(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        expected_keys = {
            "total_nodes", "total_edges", "label_coverage",
            "tag_coverage", "avg_tags_per_node", "keyword_count",
            "top_keywords", "orphan_count", "orphan_rate",
            "degree_stats", "kind_distribution", "matchability",
            "sparse_nodes", "health_score", "suggestions",
        }
        assert expected_keys.issubset(r.keys())

    def test_top_keywords_is_list_of_tuples(self):
        mg = MemoryGraph()
        mg.add("Python Programming", "skill")
        r = mg.graphrag_coverage_report()
        for item in r["top_keywords"]:
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], int)

    def test_degree_stats_has_all_fields(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        r = mg.graphrag_coverage_report()
        assert "min" in r["degree_stats"]
        assert "max" in r["degree_stats"]
        assert "mean" in r["degree_stats"]
        assert "median" in r["degree_stats"]

    def test_matchability_has_all_tiers(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        r = mg.graphrag_coverage_report()
        assert "high" in r["matchability"]
        assert "medium" in r["matchability"]
        assert "low" in r["matchability"]

    def test_kind_distribution_is_dict(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        r = mg.graphrag_coverage_report()
        assert isinstance(r["kind_distribution"], dict)

    def test_health_score_is_float(self):
        mg = MemoryGraph()
        mg.add("A", "skill")
        r = mg.graphrag_coverage_report()
        assert isinstance(r["health_score"], float)


class TestNonMutation:
    """Verify graph is not modified."""

    def test_graph_unchanged(self):
        mg = MemoryGraph()
        a = mg.add("Python", "skill", tags=["lang"])
        b = mg.add("Rust", "skill", tags=["lang"])
        mg.link(a.id, b.id, "related")
        before = mg.stats()
        mg.graphrag_coverage_report()
        after = mg.stats()
        assert before == after

    def test_idempotent(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r1 = mg.graphrag_coverage_report()
        r2 = mg.graphrag_coverage_report()
        assert r1 == r2

    def test_node_data_unchanged(self):
        mg = MemoryGraph()
        mg.add("Python", "skill", tags=["lang"], data={"level": "expert"})
        mg.graphrag_coverage_report()
        node = mg.conn.execute("SELECT label, kind, tags FROM nodes WHERE label='Python'").fetchone()
        assert node is not None


class TestRealisticGraph:
    """Integration test with a realistic KG."""

    def test_realistic_kg_health(self):
        mg = MemoryGraph()
        # Build a small KG mimicking extract_from_text output
        entities = [
            ("Python", "language", ["programming", "dynamic"]),
            ("Guido van Rossum", "person", ["creator"]),
            ("CPython", "implementation", ["reference"]),
            ("NumPy", "library", ["array", "scientific"]),
            ("Pandas", "library", ["data", "analysis"]),
            ("FastAPI", "framework", ["web", "async"]),
        ]
        nodes = {}
        for label, kind, tags in entities:
            nodes[label] = mg.add(label, kind, tags=tags)

        # Build relationships
        mg.link(nodes["Python"].id, nodes["Guido van Rossum"].id, "created_by")
        mg.link(nodes["Python"].id, nodes["CPython"].id, "has_implementation")
        mg.link(nodes["Python"].id, nodes["NumPy"].id, "has_library")
        mg.link(nodes["Python"].id, nodes["Pandas"].id, "has_library")
        mg.link(nodes["Python"].id, nodes["FastAPI"].id, "has_framework")
        mg.link(nodes["NumPy"].id, nodes["Pandas"].id, "used_by")
        mg.link(nodes["FastAPI"].id, nodes["NumPy"].id, "depends_on")

        r = mg.graphrag_coverage_report()

        # Sanity checks
        assert r["total_nodes"] == 6
        assert r["total_edges"] >= 7
        assert r["label_coverage"] == 1.0
        assert r["tag_coverage"] == 1.0
        assert r["orphan_count"] == 0
        assert r["health_score"] > 0.5
        assert r["keyword_count"] >= 5  # python, guido, numpy, pandas, fastapi, ...

        # Python should be a top keyword (appears in labels + is well-tagged)
        kws = dict(r["top_keywords"])
        assert "python" in kws

    def test_kg_with_extracted_text(self):
        """Test with nodes mimicking extract_from_text output format."""
        mg = MemoryGraph()
        # Simulate extract_from_text results
        mg.add("Alice", "Person", tags=["engineer", "python"])
        mg.add("Bob", "Person", tags=["engineer", "rust"])
        mg.add("Project Alpha", "Project", tags=["web", "api"])
        mg.add("TechCorp", "Organization", tags=["company"])

        a = mg.conn.execute("SELECT id FROM nodes WHERE label='Alice'").fetchone()
        p = mg.conn.execute("SELECT id FROM nodes WHERE label='Project Alpha'").fetchone()
        o = mg.conn.execute("SELECT id FROM nodes WHERE label='TechCorp'").fetchone()

        mg.link(a["id"], p["id"], "works_on")
        mg.link(p["id"], o["id"], "owned_by")

        r = mg.graphrag_coverage_report()
        assert r["total_nodes"] == 4
        assert r["tag_coverage"] == 1.0
        assert r["orphan_count"] == 1  # Bob has no edges
        assert r["health_score"] > 0.3
