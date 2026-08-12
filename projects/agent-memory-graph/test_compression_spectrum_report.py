"""Tests for compression_spectrum_report() — L0-L3 distribution analysis.

Analyzes the graph's position on the Experience Compression Spectrum
(Research #060) and recommends upward compression actions.
"""

import pytest
import memory_graph as mg


class TestCompressionSpectrumReportBasic:
    """Basic report generation."""

    def test_empty_graph_report(self):
        """Empty graph produces a valid report with zero counts."""
        g = mg.MemoryGraph()
        report = g.compression_spectrum_report()
        assert report["total_nodes"] == 0
        assert report["level_distribution"]["L0_raw"] == 0
        assert report["level_distribution"]["L1_episodic"] == 0
        assert report["level_distribution"]["L2_skill"] == 0
        assert report["level_distribution"]["L3_rule"] == 0

    def test_populated_graph_counts(self):
        """Graph with mixed nodes counts each level correctly."""
        g = mg.MemoryGraph()
        # L0: raw traces
        g.add("t1", kind="trace", data={"event": "click"})
        g.add("t2", kind="trace", data={"event": "scroll"})
        # L1: episodic
        g.add("ep1", kind="episode", data={"task": "analysis"})
        g.add("ep2", kind="episode", data={"task": "report"})
        g.add("ep3", kind="episode", data={"task": "export"})
        # L2: skill
        ep_ids = [n.id for n in [g.add(f"e{i}", kind="episode", data={"task": f"task{i}"}) for i in range(3)]]
        s1 = g.compress_to_skill(ep_ids, "Skill A", confidence=0.7)
        # L3: rule
        g.extract_rules([s1.id], name="Rule A")

        report = g.compression_spectrum_report()
        assert report["total_nodes"] > 0
        assert report["level_distribution"]["L0_raw"] >= 2
        assert report["level_distribution"]["L1_episodic"] >= 3
        assert report["level_distribution"]["L2_skill"] >= 1
        assert report["level_distribution"]["L3_rule"] >= 1

    def test_report_has_level_percentages(self):
        """Report includes percentage breakdown."""
        g = mg.MemoryGraph()
        g.add("ep", kind="episode", data={"task": "x"})
        report = g.compression_spectrum_report()
        assert "level_percentages" in report
        assert isinstance(report["level_percentages"], dict)
        total_pct = sum(report["level_percentages"].values())
        assert abs(total_pct - 100.0) < 0.1 or total_pct == 0

    def test_report_has_compression_ratio(self):
        """Report estimates overall compression ratio."""
        g = mg.MemoryGraph()
        for i in range(5):
            g.add(f"t{i}", kind="trace", data={"i": i})
        report = g.compression_spectrum_report()
        assert "estimated_compression_ratio" in report
        assert report["estimated_compression_ratio"] >= 1.0

    def test_report_has_recommendations(self):
        """Report provides actionable recommendations."""
        g = mg.MemoryGraph()
        for i in range(10):
            g.add(f"t{i}", kind="trace", data={"i": i})
        report = g.compression_spectrum_report()
        assert "recommendations" in report
        assert isinstance(report["recommendations"], list)
        assert len(report["recommendations"]) > 0


class TestCompressionSpectrumReportLevels:
    """Level detection and classification."""

    def test_trace_nodes_classified_as_L0(self):
        """Trace/log nodes are L0."""
        g = mg.MemoryGraph()
        g.add("raw", kind="trace", data={"log": "entry"})
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["L0_raw"] == 1

    def test_event_nodes_classified_as_L0(self):
        """Event/log nodes are L0."""
        g = mg.MemoryGraph()
        g.add("ev", kind="event", data={"action": "click"})
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["L0_raw"] >= 1

    def test_episode_nodes_classified_as_L1(self):
        """Episode/memory nodes are L1."""
        g = mg.MemoryGraph()
        g.add("ep", kind="episode", data={"task": "x"})
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["L1_episodic"] >= 1

    def test_skill_nodes_classified_as_L2(self):
        """Skill nodes are L2."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode", data={"task": "x"})
        g.compress_to_skill([ep.id], "S")
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["L2_skill"] >= 1

    def test_rule_nodes_classified_as_L3(self):
        """Rule nodes are L3."""
        g = mg.MemoryGraph()
        ep = g.add("ep", kind="episode", data={"task": "x"})
        s = g.compress_to_skill([ep.id], "S")
        g.extract_rules([s.id])
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["L3_rule"] >= 1

    def test_unclassified_kinds_counted(self):
        """Non-spectrum kinds are counted separately."""
        g = mg.MemoryGraph()
        g.add("custom", kind="custom_type", data={"text": "custom"})
        report = g.compression_spectrum_report()
        assert report["level_distribution"]["uncategorized"] >= 1


class TestCompressionSpectrumReportInsights:
    """Insight generation and recommendations."""

    def test_high_L0_recommends_compression(self):
        """Too many L0 nodes → recommend episodic compression."""
        g = mg.MemoryGraph()
        for i in range(20):
            g.add(f"t{i}", kind="trace", data={"i": i})
        report = g.compression_spectrum_report()
        recs = " ".join(report["recommendations"]).lower()
        assert any(kw in recs for kw in ["compress", "episode", "L0", "trace"])

    def test_high_L1_no_L2_recommends_skill_extraction(self):
        """Many episodes but no skills → recommend skill extraction."""
        g = mg.MemoryGraph()
        for i in range(15):
            g.add(f"ep{i}", kind="episode", data={"task": f"task{i}"})
        report = g.compression_spectrum_report()
        recs = " ".join(report["recommendations"]).lower()
        assert any(kw in recs for kw in ["skill", "compress", "L1", "episode"])

    def test_high_L2_no_L3_recommends_rule_extraction(self):
        """Skills exist but no rules → recommend rule extraction."""
        g = mg.MemoryGraph()
        for i in range(3):
            ep = g.add(f"ep{i}", kind="episode", data={"task": f"t{i}"})
            g.compress_to_skill([ep.id], f"Skill{i}", confidence=0.7)
        report = g.compression_spectrum_report()
        recs = " ".join(report["recommendations"]).lower()
        assert any(kw in recs for kw in ["rule", "extract", "L3", "declarative"])

    def test_balanced_graph_praised(self):
        """Balanced graph gets positive recommendation."""
        g = mg.MemoryGraph()
        eps = [g.add(f"ep{i}", kind="episode", data={"task": f"t{i}"}) for i in range(3)]
        s = g.compress_to_skill([e.id for e in eps], "Skill", confidence=0.8)
        g.evolve_skill(s.id, new_constraints=["always verify"])
        g.extract_rules([s.id])
        report = g.compression_spectrum_report()
        recs = " ".join(report["recommendations"]).lower()
        assert any(kw in recs for kw in ["healthy", "balanced", "well"])

    def test_report_has_dominant_level(self):
        """Report identifies the dominant compression level."""
        g = mg.MemoryGraph()
        for i in range(10):
            g.add(f"ep{i}", kind="episode", data={"task": f"t{i}"})
        report = g.compression_spectrum_report()
        assert "dominant_level" in report
        assert report["dominant_level"] == "L1_episodic"

    def test_report_has_total_nodes(self):
        """Report includes total node count."""
        g = mg.MemoryGraph()
        g.add("a", kind="episode", data={"x": 1})
        g.add("b", kind="trace", data={"x": 2})
        report = g.compression_spectrum_report()
        assert report["total_nodes"] == 2
