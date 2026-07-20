"""F34-F35: histogram() + correlation_stats()"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


@pytest.fixture
def mem():
    m = Memory()
    m.add("low importance entry", importance=0.1)
    m.add("medium entry", importance=0.5)
    m.add("high importance entry", importance=0.9)
    m.add("another medium", importance=0.4, tags=["work"])
    m.add("also high", importance=0.8, tags=["work"])
    return m


# --- F34: histogram ---

def test_histogram_basic(mem):
    h = mem.histogram(bins=10)
    assert "bin_edges" in h
    assert "counts" in h
    assert len(h["counts"]) == 10


def test_histogram_bin_edges(mem):
    h = mem.histogram(bins=5)
    assert h["bin_edges"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def test_histogram_counts_sum(mem):
    h = mem.histogram(bins=5)
    assert sum(h["counts"]) == 5


def test_histogram_max_bin(mem):
    h = mem.histogram(bins=5)
    assert h["max_bin"] is not None
    assert "-" in h["max_bin"]


def test_histogram_labels(mem):
    h = mem.histogram(bins=5)
    assert len(h["labels"]) == 5
    assert h["labels"][0] == "0.0-0.2"


def test_histogram_min_max_importance(mem):
    h = mem.histogram(bins=5)
    assert h["min_importance"] == 0.1
    assert h["max_importance"] == 0.9


def test_histogram_empty():
    m = Memory()
    h = m.histogram()
    assert h["counts"] == []
    assert h["max_bin"] is None


def test_histogram_custom_bins(mem):
    h = mem.histogram(bins=2)
    assert len(h["counts"]) == 2
    assert h["bin_edges"] == [0.0, 0.5, 1.0]


def test_histogram_all_same_importance():
    m = Memory()
    for _ in range(5):
        m.add("entry", importance=0.5)
    h = m.histogram(bins=5)
    # All in middle bin
    assert sum(h["counts"]) == 5


def test_histogram_counts_correct(mem):
    h = mem.histogram(bins=5)
    # 0.1 -> bin 0, 0.5 -> bin 2, 0.9 -> bin 4, 0.4 -> bin 1, 0.8 -> bin 3
    # Actually: 0.1/0.2=0 -> bin 0, 0.5/0.2=2 -> bin 2, 0.9/0.2=4 -> bin 4
    # 0.4/0.2=2 -> bin 2 (0.4 is exactly on edge -> bin 2), wait no
    # edges: 0, 0.2, 0.4, 0.6, 0.8, 1.0
    # 0.1 -> (0.1-0)/0.2 = 0.5 -> int = 0 -> bin 0
    # 0.5 -> 2.5 -> 2 -> bin 2
    # 0.9 -> 4.5 -> 4 -> bin 4
    # 0.4 -> 2.0 -> 2 -> bin 2
    # 0.8 -> 4.0 -> 4 -> bin 4
    assert h["counts"][0] == 1  # 0.1
    assert h["counts"][2] >= 1  # 0.5 or 0.4
    assert h["counts"][4] >= 1  # 0.9 or 0.8


# --- F35: correlation_stats ---

def test_correlation_basic(mem):
    c = mem.correlation_stats()
    assert "importance_length_r" in c
    assert "tag_count" in c
    assert "avg_importance_per_tag" in c


def test_correlation_r_in_range(mem):
    c = mem.correlation_stats()
    assert -1.0 <= c["importance_length_r"] <= 1.0


def test_correlation_tag_count(mem):
    c = mem.correlation_stats()
    assert c["tag_count"] == 1  # only "work" tag


def test_correlation_avg_per_tag(mem):
    c = mem.correlation_stats()
    assert "work" in c["avg_importance_per_tag"]
    avg = c["avg_importance_per_tag"]["work"]
    assert 0.5 < avg < 1.0  # (0.4 + 0.8) / 2 = 0.6


def test_correlation_empty():
    m = Memory()
    c = m.correlation_stats()
    assert c["importance_length_r"] is None
    assert c["tag_count"] == 0
    assert c["total_chars"] == 0


def test_correlation_total_chars(mem):
    c = mem.correlation_stats()
    assert c["total_chars"] > 0


def test_correlation_positive_relationship():
    m = Memory()
    m.add("short", importance=0.1)
    m.add("a bit longer text", importance=0.5)
    m.add("this is the longest text by far", importance=0.9)
    c = m.correlation_stats()
    assert c["importance_length_r"] > 0  # positive correlation


def test_correlation_no_tags():
    m = Memory()
    m.add("no tags here", importance=0.5)
    c = m.correlation_stats()
    assert c["tag_count"] == 0
    assert c["avg_importance_per_tag"] == {}


def test_correlation_multiple_tags():
    m = Memory()
    m.add("a", importance=0.3, tags=["x"])
    m.add("b", importance=0.7, tags=["x", "y"])
    m.add("c", importance=0.5, tags=["y"])
    c = m.correlation_stats()
    assert c["tag_count"] == 2
    assert "x" in c["avg_importance_per_tag"]
    assert "y" in c["avg_importance_per_tag"]
