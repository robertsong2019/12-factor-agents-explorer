"""
amg_bench — Performance Benchmark Harness for agent-memory-graph.

Measures throughput (add/link per second) and latency (search, recall,
multi_hop_reason) across configurable scale tiers.

Usage:
    from amg_bench import run_bench
    results = run_bench(scales=[100, 500, 1000])
    for r in results:
        print(r)

    # Or with full harness:
    from amg_bench import BenchHarness
    bh = BenchHarness(scales=[100, 500, 1000], iterations=3)
    bh.run()
    print(bh.summary())
    print(bh.markdown_report())
"""
import time
import statistics
from dataclasses import dataclass, field
from typing import Optional

from memory_graph import MemoryGraph


@dataclass
class BenchmarkResult:
    """Single-scale benchmark result."""
    scale: int
    add_per_sec: float
    link_per_sec: float
    search_avg_ms: float
    recall_avg_ms: float
    multi_hop_avg_ms: float
    node_count: int
    edge_count: int
    iterations: int = 1

    def to_dict(self) -> dict:
        return {
            "scale": self.scale,
            "add_per_sec": round(self.add_per_sec, 1),
            "link_per_sec": round(self.link_per_sec, 1),
            "search_avg_ms": round(self.search_avg_ms, 3),
            "recall_avg_ms": round(self.recall_avg_ms, 3),
            "multi_hop_avg_ms": round(self.multi_hop_avg_ms, 3),
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "iterations": self.iterations,
        }

    def __repr__(self):
        return (
            f"BenchmarkResult(scale={self.scale}, "
            f"add/s={self.add_per_sec:.0f}, "
            f"link/s={self.link_per_sec:.0f}, "
            f"search={self.search_avg_ms:.2f}ms, "
            f"recall={self.recall_avg_ms:.2f}ms, "
            f"multi_hop={self.multi_hop_avg_ms:.2f}ms, "
            f"nodes={self.node_count}, edges={self.edge_count})"
        )


class BenchHarness:
    """Benchmark harness for agent-memory-graph.

    Measures core operations at multiple scale tiers.

    Args:
        scales: List of node counts to benchmark (e.g. [100, 500, 1000]).
        iterations: Number of iterations per scale (results are averaged).
    """

    def __init__(self, scales: list[int] = None, iterations: int = 3):
        if scales is not None and len(scales) == 0:
            raise ValueError("scales must be a non-empty list")
        if iterations < 1:
            raise ValueError("iterations must be >= 1")
        self.scales = scales or [100, 500, 1000]
        self.iterations = iterations
        self._results: list[BenchmarkResult] = []

    def _build_graph(self, n: int) -> MemoryGraph:
        """Build a graph with n nodes and ~2n edges.

        Returns (graph, node_ids) tuple.
        """
        mg = MemoryGraph()
        ids = []
        for i in range(n):
            node = mg.add(f"entity_{i}", kind="fact", data={"index": i, "category": f"cat_{i % 5}"})
            ids.append(node.id)
        # Create edges: chain + some cross-links
        for i in range(n - 1):
            mg.link(ids[i], ids[i + 1], relation="next")
        for i in range(0, n - 5, 5):
            mg.link(ids[i], ids[i + 5], relation="skip")
        return mg, ids

    def _bench_add(self, n: int) -> float:
        """Measure add throughput (nodes/sec)."""
        mg = MemoryGraph()
        t0 = time.perf_counter()
        for i in range(n):
            mg.add(f"bench_node_{i}", kind="fact", data={"idx": i})
        elapsed = time.perf_counter() - t0
        return n / elapsed if elapsed > 0 else float("inf")

    def _bench_link(self, mg: MemoryGraph, node_ids: list[str], n: int) -> float:
        """Measure link throughput (edges/sec)."""
        if len(node_ids) < 2:
            return 0.0
        link_count = min(n, len(node_ids) - 1)
        t0 = time.perf_counter()
        for i in range(link_count):
            mg.link(node_ids[i], node_ids[i + 1], relation="bench_link")
        elapsed = time.perf_counter() - t0
        return link_count / elapsed if elapsed > 0 else float("inf")

    def _bench_search(self, mg: MemoryGraph, queries: list[str]) -> float:
        """Measure average recall/search latency (ms)."""
        latencies = []
        for q in queries:
            t0 = time.perf_counter()
            mg.recall(q, limit=5)
            latencies.append((time.perf_counter() - t0) * 1000)
        return statistics.mean(latencies) if latencies else 0.0

    def _bench_recall(self, mg: MemoryGraph, queries: list[str]) -> float:
        """Measure average recall latency (ms)."""
        latencies = []
        for q in queries:
            t0 = time.perf_counter()
            mg.recall(q)
            latencies.append((time.perf_counter() - t0) * 1000)
        return statistics.mean(latencies) if latencies else 0.0

    def _bench_multi_hop(self, mg: MemoryGraph, seeds: list[str]) -> float:
        """Measure average multi_hop_reason latency (ms)."""
        latencies = []
        for s in seeds[:10]:
            t0 = time.perf_counter()
            try:
                mg.multi_hop_reason([s], max_depth=2)
            except Exception:
                pass
            latencies.append((time.perf_counter() - t0) * 1000)
        return statistics.mean(latencies) if latencies else 0.0

    def _run_single_scale(self, n: int) -> BenchmarkResult:
        """Run one iteration at scale n and return result."""
        # Build graph
        mg, node_ids = self._build_graph(n)

        # Queries for latency measurement (use labels)
        step = max(1, n // 20)
        queries = [f"entity_{i}" for i in range(0, n, step)]
        if not queries:
            queries = ["entity_0"]

        # Measure
        add_ps = self._bench_add(n)
        link_ps = self._bench_link(mg, node_ids, n)
        search_ms = self._bench_search(mg, queries)
        recall_ms = self._bench_recall(mg, queries)
        multi_hop_ms = self._bench_multi_hop(mg, node_ids)

        return BenchmarkResult(
            scale=n,
            add_per_sec=add_ps,
            link_per_sec=link_ps,
            search_avg_ms=search_ms,
            recall_avg_ms=recall_ms,
            multi_hop_avg_ms=multi_hop_ms,
            node_count=len(mg.find_by_kind("fact")),
            edge_count=mg.edge_count(),
        )

    def run(self) -> list[BenchmarkResult]:
        """Run benchmark across all scales."""
        self._results = []
        for scale in self.scales:
            if self.iterations == 1:
                r = self._run_single_scale(scale)
            else:
                # Average across iterations
                runs = [self._run_single_scale(scale) for _ in range(self.iterations)]
                r = BenchmarkResult(
                    scale=scale,
                    add_per_sec=statistics.mean(r.add_per_sec for r in runs),
                    link_per_sec=statistics.mean(r.link_per_sec for r in runs),
                    search_avg_ms=statistics.mean(r.search_avg_ms for r in runs),
                    recall_avg_ms=statistics.mean(r.recall_avg_ms for r in runs),
                    multi_hop_avg_ms=statistics.mean(r.multi_hop_avg_ms for r in runs),
                    node_count=runs[-1].node_count,
                    edge_count=runs[-1].edge_count,
                    iterations=self.iterations,
                )
            self._results.append(r)
        return self._results

    def summary(self) -> str:
        """Human-readable summary."""
        if not self._results:
            return "No results. Call run() first."
        lines = ["AMG Benchmark Results", "=" * 60]
        for r in self._results:
            lines.append(
                f"  Scale {r.scale:>5}: add {r.add_per_sec:>8.0f}/s, "
                f"link {r.link_per_sec:>8.0f}/s, "
                f"search {r.search_avg_ms:>6.2f}ms, "
                f"recall {r.recall_avg_ms:>6.2f}ms, "
                f"multi_hop {r.multi_hop_avg_ms:>6.2f}ms"
            )
        return "\n".join(lines)

    def summary_json(self) -> list[dict]:
        """JSON-serializable results."""
        return [r.to_dict() for r in self._results]

    def summary_dict(self) -> dict:
        """Full structured report."""
        return {
            "config": {
                "scales": self.scales,
                "iterations": self.iterations,
            },
            "results": self.summary_json(),
        }

    def markdown_report(self) -> str:
        """Generate markdown table report."""
        if not self._results:
            return "No results. Call run() first."
        lines = [
            "## AMG Benchmark Results",
            "",
            f"Scales: {', '.join(str(s) for s in self.scales)} | "
            f"Iterations: {self.iterations}",
            "",
            "| Scale | Add/s | Link/s | Search (ms) | Recall (ms) | Multi-hop (ms) | Nodes | Edges |",
            "|------:|------:|-------:|------------:|------------:|---------------:|------:|------:|",
        ]
        for r in self._results:
            lines.append(
                f"| {r.scale} | {r.add_per_sec:.0f} | {r.link_per_sec:.0f} | "
                f"{r.search_avg_ms:.2f} | {r.recall_avg_ms:.2f} | "
                f"{r.multi_hop_avg_ms:.2f} | {r.node_count} | {r.edge_count} |"
            )
        return "\n".join(lines)


def run_bench(
    scales: list[int] = None,
    iterations: int = 1,
) -> list[BenchmarkResult]:
    """Convenience function: run benchmark and return results.

    Args:
        scales: Node counts to test (default: [100, 500, 1000]).
        iterations: Iterations per scale (default: 1).

    Returns:
        List of BenchmarkResult, one per scale.
    """
    bh = BenchHarness(scales=scales or [100, 500, 1000], iterations=iterations)
    return bh.run()
