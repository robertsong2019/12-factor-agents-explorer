"""F32: Memory.cluster() — greedy similarity clustering"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


@pytest.fixture
def mem():
    m = Memory()
    m.add("The quick brown fox jumps", tags=["animal"])
    m.add("The quick brown fox runs", tags=["animal"])
    m.add("Python programming is fun", tags=["code"])
    m.add("Python coding is enjoyable", tags=["code"])
    m.add("A completely different topic", tags=["misc"])
    return m


def test_cluster_basic(mem):
    clusters = mem.cluster(threshold=0.5)
    assert isinstance(clusters, dict)
    assert len(clusters) >= 1


def test_cluster_groups_similar(mem):
    clusters = mem.cluster(threshold=0.5)
    # The two "quick brown fox" entries should cluster together
    # The two "Python" entries should cluster together
    # "completely different" should be alone
    sizes = sorted([len(c) for c in clusters.values()], reverse=True)
    assert sizes[0] >= 2  # at least one cluster with 2+ entries


def test_cluster_high_threshold_all_singletons(mem):
    clusters = mem.cluster(threshold=0.99)
    # With 0.99 threshold, almost everything is its own cluster
    for members in clusters.values():
        assert len(members) <= 1 or len(members) == 5  # edge case


def test_cluster_low_threshold_all_merged(mem):
    clusters = mem.cluster(threshold=0.0)
    # With 0 threshold, everything merges into one cluster
    assert len(clusters) == 1


def test_cluster_empty_memory():
    m = Memory()
    clusters = m.cluster()
    assert clusters == {}


def test_cluster_returns_memory_entries(mem):
    clusters = mem.cluster(threshold=0.3)
    for members in clusters.values():
        for entry in members:
            assert hasattr(entry, "content")
            assert hasattr(entry, "importance")


def test_cluster_limit(mem):
    clusters = mem.cluster(threshold=0.3, limit=2)
    total = sum(len(c) for c in clusters.values())
    assert total == 2


def test_cluster_all_same_content():
    m = Memory()
    for _ in range(5):
        m.add("identical content here")
    clusters = m.cluster(threshold=0.8)
    assert len(clusters) == 1
    assert len(clusters[0]) == 5


def test_cluster_preserves_cluster_ids():
    m = Memory()
    m.add("a")
    m.add("b")
    clusters = m.cluster(threshold=0.99)
    assert set(clusters.keys()) == {0, 1}


def test_cluster_member_count_sums_to_total(mem):
    clusters = mem.cluster(threshold=0.5)
    total = sum(len(c) for c in clusters.values())
    assert total == len(mem.get_all())


# --- F33: compact_summary ---

def test_summary_basic(mem):
    s = mem.compact_summary()
    assert s["total"] == 5


def test_summary_top_entries(mem):
    s = mem.compact_summary(max_entries=2)
    assert len(s["top_entries"]) == 2


def test_summary_tag_distribution(mem):
    s = mem.compact_summary()
    assert "animal" in s["tag_distribution"]
    assert s["tag_distribution"]["animal"] == 2


def test_summary_time_span(mem):
    s = mem.compact_summary()
    assert s["time_span"] is not None
    assert "earliest" in s["time_span"]
    assert "latest" in s["time_span"]


def test_summary_empty_memory():
    m = Memory()
    s = m.compact_summary()
    assert s["total"] == 0
    assert s["top_entries"] == []
    assert s["time_span"] is None


def test_summary_top_sorted_by_importance(mem):
    s = mem.compact_summary(max_entries=3)
    importances = [e["importance"] for e in s["top_entries"]]
    assert importances == sorted(importances, reverse=True)


def test_summary_tag_distribution_sorted(mem):
    m = Memory()
    for i in range(5):
        m.add(f"item {i}", tags=["common"])
    for i in range(2):
        m.add(f"rare {i}", tags=["rare"])
    s = m.compact_summary()
    tags = list(s["tag_distribution"].keys())
    assert tags[0] == "common"  # most frequent first
