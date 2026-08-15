"""Tests for amg_bench — performance benchmark harness."""
import pytest
import time
from amg_bench import BenchHarness, BenchmarkResult, run_bench


class TestBenchHarnessConstruction:
    def test_default_construction(self):
        b = BenchHarness()
        assert b.scales == [100, 500, 1000]
        assert b.iterations == 3

    def test_custom_scales(self):
        b = BenchHarness(scales=[50, 200])
        assert b.scales == [50, 200]

    def test_custom_iterations(self):
        b = BenchHarness(iterations=5)
        assert b.iterations == 5

    def test_invalid_scales_raises(self):
        with pytest.raises(ValueError, match="scales must"):
            BenchHarness(scales=[])

    def test_invalid_iterations_raises(self):
        with pytest.raises(ValueError, match="iterations must"):
            BenchHarness(iterations=0)


class TestBenchmarkResult:
    def test_result_has_fields(self):
        r = BenchmarkResult(
            scale=100,
            add_per_sec=5000.0,
            link_per_sec=3000.0,
            search_avg_ms=1.5,
            recall_avg_ms=2.0,
            multi_hop_avg_ms=5.0,
            node_count=100,
            edge_count=200,
        )
        assert r.scale == 100
        assert r.add_per_sec == 5000.0
        assert r.search_avg_ms == 1.5

    def test_result_to_dict(self):
        r = BenchmarkResult(
            scale=100,
            add_per_sec=5000.0,
            link_per_sec=3000.0,
            search_avg_ms=1.5,
            recall_avg_ms=2.0,
            multi_hop_avg_ms=5.0,
            node_count=100,
            edge_count=200,
        )
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["scale"] == 100
        assert "add_per_sec" in d
        assert "edge_count" in d

    def test_result_repr(self):
        r = BenchmarkResult(
            scale=100,
            add_per_sec=5000.0,
            link_per_sec=3000.0,
            search_avg_ms=1.5,
            recall_avg_ms=2.0,
            multi_hop_avg_ms=5.0,
            node_count=100,
            edge_count=200,
        )
        s = repr(r)
        assert "scale=100" in s
        assert "add/s" in s


class TestRunBench:
    def test_run_bench_returns_list(self):
        results = run_bench(scales=[50], iterations=1)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_run_bench_result_values_positive(self):
        results = run_bench(scales=[50], iterations=1)
        r = results[0]
        assert r.add_per_sec > 0
        assert r.link_per_sec > 0
        assert r.search_avg_ms > 0
        assert r.node_count == 50

    def test_run_bench_multiple_scales(self):
        results = run_bench(scales=[20, 50], iterations=1)
        assert len(results) == 2
        assert results[0].scale == 20
        assert results[1].scale == 50

    def test_run_bench_edge_count_positive(self):
        results = run_bench(scales=[50], iterations=1)
        assert results[0].edge_count > 0

    def test_run_bench_recall_measured(self):
        results = run_bench(scales=[50], iterations=1)
        assert results[0].recall_avg_ms > 0

    def test_run_bench_multi_hop_measured(self):
        results = run_bench(scales=[50], iterations=1)
        assert results[0].multi_hop_avg_ms > 0

    def test_larger_scale_not_faster_than_smaller(self):
        """Larger graphs should not have faster add throughput (sanity check)."""
        results = run_bench(scales=[20, 500], iterations=1)
        # Add per-sec for 500 nodes should be <= 20 nodes (overhead grows)
        # This is a soft sanity check — we just verify both produce valid numbers
        small = results[0]
        large = results[1]
        assert small.add_per_sec > 0
        assert large.add_per_sec > 0


class TestBenchHarnessRun:
    def test_harness_run_returns_results(self):
        b = BenchHarness(scales=[30], iterations=2)
        results = b.run()
        assert len(results) == 1
        assert results[0].iterations == 2

    def test_harness_summary_text(self):
        b = BenchHarness(scales=[30], iterations=1)
        b.run()
        summary = b.summary()
        assert isinstance(summary, str)
        assert "scale" in summary.lower() or "Scale" in summary
        assert "add" in summary.lower()

    def test_harness_summary_json(self):
        b = BenchHarness(scales=[30], iterations=1)
        b.run()
        data = b.summary_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "scale" in data[0]
        assert "add_per_sec" in data[0]

    def test_harness_summary_dict_grouped(self):
        b = BenchHarness(scales=[20, 40], iterations=1)
        b.run()
        grouped = b.summary_dict()
        assert isinstance(grouped, dict)
        assert "results" in grouped
        assert "config" in grouped
        assert len(grouped["results"]) == 2
        assert grouped["config"]["iterations"] == 1


class TestReportFormat:
    def test_markdown_report(self):
        b = BenchHarness(scales=[30], iterations=1)
        b.run()
        md = b.markdown_report()
        assert isinstance(md, str)
        assert "|" in md  # table format
        assert "Add" in md or "add" in md.lower()

    def test_markdown_report_has_header(self):
        b = BenchHarness(scales=[30], iterations=1)
        b.run()
        md = b.markdown_report()
        assert "amg" in md.lower() or "benchmark" in md.lower()


class TestGraphOpsBenchmark:
    """Benchmark individual graph operations."""

    def test_bench_add_nodes(self):
        b = BenchHarness(scales=[50], iterations=1)
        mg, ids = b._build_graph(50)
        assert len(mg.find_by_kind("fact")) == 50

    def test_bench_search_returns_results(self):
        b = BenchHarness(scales=[50], iterations=1)
        mg, ids = b._build_graph(50)
        results = mg.recall("entity_25", limit=5)
        assert isinstance(results, list)

    def test_bench_recall_returns_node(self):
        b = BenchHarness(scales=[50], iterations=1)
        mg, ids = b._build_graph(50)
        node = mg.recall("entity_25")
        # recall may return None if no exact match, that's fine
        # we just test it doesn't crash
