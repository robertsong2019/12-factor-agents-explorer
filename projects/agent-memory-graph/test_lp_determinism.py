"""Cycle 470 — deterministic label propagation (community_detect).

Root cause of the ~1/3-run full-suite flake in
``test_community_entropy_profile::TestAlgorithmVariants::test_lp``:

1. ``SELECT id FROM nodes`` scans the PK index → uuid-sorted rows →
   initial labels were random per run (node ids are uuid4).
2. Neighbor-label count ties broke on dict insertion order — the
   order came from the same uuid-sorted UNION query → tie-breaking
   was random per run.

Both fed label propagation with per-run randomness → partitions
varied run-to-run → ``community_entropy_profile(algorithm="lp")``
occasionally collapsed the two-community fixture to one community
and hit its documented ``return None`` (< 2 communities) →
``assert result is not None`` failed.

Fix (same contract as the C411 leiden seed):
* initial labels pinned via ``ORDER BY rowid`` (insertion order);
* count ties break via the SEEDED rng over the value-sorted tied
  labels — the draw sequence depends only on integer label dynamics,
  never on uuid ids, so identical structure + seed ⇒ identical
  partition.

Note: ``min``-label tie-breaking (first attempt) deterministically
collapses the bridged fixture — label 0 leaks through the bridge on
every 1-vs-1 tie. Seeded random choice preserves classic LP clique
cohesion while staying reproducible.
"""
import pytest

from memory_graph import MemoryGraph


def _two_communities() -> MemoryGraph:
    """Same shape as the entropy-profile fixture (clique + cycle + bridge)."""
    mg = MemoryGraph()
    a = [mg.add(f"a{i}", tags=["A"]) for i in range(4)]
    b = [mg.add(f"b{i}", tags=["B"]) for i in range(4)]
    for i in range(4):
        for j in range(i + 1, 4):
            mg.link(a[i].id, a[j].id, "sim")
    for i in range(4):
        mg.link(b[i].id, b[(i + 1) % 4].id, "knows")
    mg.link(a[0].id, b[0].id, "bridge")
    return mg


def _two_disconnected_cliques() -> MemoryGraph:
    mg = MemoryGraph()
    a = [mg.add(f"a{i}") for i in range(4)]
    b = [mg.add(f"b{i}") for i in range(4)]
    for group in (a, b):
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(group[i].id, group[j].id, "rel")
    return mg


class TestLpDeterminism:
    def test_size_signature_identical_across_fresh_graphs(self):
        """25 fresh graphs (fresh uuid4 ids, identical structure) →
        exactly ONE size-signature. Pre-fix: varied every run via
        uuid-sorted initial labels and tie-breaks."""
        sigs = set()
        for _ in range(25):
            comms = _two_communities().community_detect()
            sigs.add(tuple(sorted(len(v) for v in comms.values())))
        assert len(sigs) == 1

    def test_disconnected_cliques_two_communities(self):
        """No-bridge structure: LP must cohere each clique into its
        own community (label dynamics are seed-deterministic)."""
        comms = _two_disconnected_cliques().community_detect()
        assert sorted(len(v) for v in comms.values()) == [4, 4]

    def test_seed_reproducibility(self):
        """Same object + same seed → identical partition; fresh
        object + same seed → identical STRUCTURAL signature
        (membership by node label — ids are fresh uuids so raw
        partition dicts can never match across objects)."""
        mg = _two_communities()
        assert (mg.community_detect(seed=7)
                == mg.community_detect(seed=7))

        def struct_sig(graph, part):
            id2label = {r["id"]: r["label"] for r in
                        graph.conn.execute("SELECT id, label FROM nodes")}
            return frozenset(
                frozenset(id2label[nid] for nid in members)
                for members in part.values())

        sigs = set()
        for _ in range(5):
            g = _two_communities()
            sigs.add(struct_sig(g, g.community_detect(seed=7)))
        assert len(sigs) == 1

    def test_entropy_profile_lp_deterministic_across_runs(self):
        """The exact flake surface: whatever the outcome (2+ comms →
        profile dict, or collapse → None), it must be IDENTICAL
        across 25 fresh graphs — no run-to-run coin flips."""
        outs = set()
        for _ in range(25):
            prof = _two_communities().community_entropy_profile(
                algorithm="lp")
            outs.add("None" if prof is None
                     else (prof["algorithm"],
                           prof["summary"]["num_communities"]))
        assert len(outs) == 1

    def test_leiden_path_unaffected(self):
        part = _two_communities().community_partition(algorithm="leiden")
        assert len(set(part.values())) >= 2

    def test_greedy_path_unaffected(self):
        part = _two_communities().community_partition(algorithm="greedy")
        assert part

    def test_empty_graph_returns_empty(self):
        assert MemoryGraph().community_detect() == {}
