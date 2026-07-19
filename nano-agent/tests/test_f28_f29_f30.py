"""Tests for F28 (intersect), F29 (sample), F30 (timeline)."""

import pytest
from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry


@pytest.fixture
def mem_a():
    m = Memory(max_entries=100)
    m.add("hello world", tags=["greeting"])
    m.add("python code", tags=["tech"])
    m.add("goodbye sky", tags=["farewell"])
    return m


@pytest.fixture
def mem_b():
    m = Memory(max_entries=100)
    m.add("hello world", tags=["greeting"])
    m.add("rust code", tags=["tech"])
    m.add("goodbye sky", tags=["farewell"])
    return m


# ─── F28: intersect ───

class TestIntersect:
    def test_basic_intersect(self, mem_a, mem_b):
        """Common entries returned."""
        result = mem_a.intersect(mem_b)
        contents = [e.content for e in result]
        assert "hello world" in contents
        assert "goodbye sky" in contents

    def test_intersect_excludes_unique(self, mem_a, mem_b):
        """Entries only in A are not included."""
        result = mem_a.intersect(mem_b)
        contents = [e.content for e in result]
        assert "python code" not in contents
        assert "rust code" not in contents

    def test_intersect_count(self, mem_a, mem_b):
        """2 common entries."""
        assert len(mem_a.intersect(mem_b)) == 2

    def test_intersect_empty_other(self, mem_a):
        """Empty other → empty result."""
        empty = Memory()
        assert mem_a.intersect(empty) == []

    def test_intersect_self(self, mem_a):
        """Intersect with self → all entries."""
        result = mem_a.intersect(mem_a)
        assert len(result) == len(mem_a.get_all())

    def test_intersect_no_common(self):
        """Completely disjoint memories."""
        m1 = Memory()
        m1.add("aaa")
        m2 = Memory()
        m2.add("bbb")
        assert m1.intersect(m2) == []

    def test_intersect_preserves_self_metadata(self):
        """Returned entries are from self (not other)."""
        m1 = Memory()
        m1.add("shared", importance=0.9, tags=["x"])
        m2 = Memory()
        m2.add("shared", importance=0.1, tags=["y"])
        result = m1.intersect(m2)
        assert len(result) == 1
        assert result[0].importance == 0.9
        assert result[0].tags == ["x"]

    def test_intersect_symmetric_count(self, mem_a, mem_b):
        """intersect(A,B) and intersect(B,A) return same count."""
        assert len(mem_a.intersect(mem_b)) == len(mem_b.intersect(mem_a))


# ─── F29: sample ───

class TestSample:
    def test_sample_basic(self, mem_a):
        """Returns requested count."""
        result = mem_a.sample(n=2)
        assert len(result) == 2

    def test_sample_all(self, mem_a):
        """n >= total returns all entries."""
        result = mem_a.sample(n=100)
        assert len(result) == 3

    def test_sample_zero(self, mem_a):
        """n=0 returns empty."""
        assert mem_a.sample(n=0) == []

    def test_sample_empty_memory(self):
        """Empty memory → empty list."""
        m = Memory()
        assert m.sample(n=5) == []

    def test_sample_unweighted(self, mem_a):
        """Unweighted sample returns correct count."""
        result = mem_a.sample(n=2, weighted=False)
        assert len(result) == 2

    def test_sample_n_equals_total(self, mem_a):
        """n == total returns shuffled all."""
        result = mem_a.sample(n=3)
        assert len(result) == 3

    def test_sample_returns_memory_entries(self, mem_a):
        """All returned items are MemoryEntry."""
        result = mem_a.sample(n=2)
        assert all(isinstance(e, MemoryEntry) for e in result)

    def test_sample_weighted_distribution(self):
        """High-importance entries sampled more often (probabilistic)."""
        m = Memory(max_entries=100)
        for _ in range(50):
            m.add("low", importance=0.01)
        for _ in range(50):
            m.add("high", importance=0.99)
        # Sample 200 times, count how often "high" appears
        from collections import Counter
        all_samples = []
        for _ in range(100):
            all_samples.extend(m.sample(n=10, weighted=True))
        contents = Counter(e.content for e in all_samples)
        # "high" should be significantly more frequent
        assert contents["high"] > contents["low"]


# ─── F30: timeline ───

class TestTimeline:
    def test_empty_memory(self):
        """Empty memory → empty dict."""
        m = Memory()
        assert m.timeline() == {}

    def test_day_bucket(self):
        """Day bucket groups by date."""
        m = Memory(max_entries=100)
        base = datetime(2026, 7, 1, 10, 0)
        for i in range(3):
            entry = MemoryEntry(content=f"msg {i}", timestamp=base + timedelta(days=i))
            m._entries.append(entry)
        result = m.timeline(bucket="day")
        assert "2026-07-01" in result
        assert "2026-07-02" in result
        assert "2026-07-03" in result
        assert all(v == 1 for v in result.values())

    def test_hour_bucket(self):
        """Hour bucket groups by hour."""
        m = Memory(max_entries=100)
        t1 = datetime(2026, 7, 1, 10, 30)
        t2 = datetime(2026, 7, 1, 10, 45)
        t3 = datetime(2026, 7, 1, 11, 0)
        m._entries.append(MemoryEntry(content="a", timestamp=t1))
        m._entries.append(MemoryEntry(content="b", timestamp=t2))
        m._entries.append(MemoryEntry(content="c", timestamp=t3))
        result = m.timeline(bucket="hour")
        assert result["2026-07-01 10:00"] == 2
        assert result["2026-07-01 11:00"] == 1

    def test_month_bucket(self):
        """Month bucket groups by year-month."""
        m = Memory(max_entries=100)
        m._entries.append(MemoryEntry(content="a", timestamp=datetime(2026, 1, 15)))
        m._entries.append(MemoryEntry(content="b", timestamp=datetime(2026, 1, 20)))
        m._entries.append(MemoryEntry(content="c", timestamp=datetime(2026, 2, 5)))
        result = m.timeline(bucket="month")
        assert result["2026-01"] == 2
        assert result["2026-02"] == 1

    def test_invalid_bucket_defaults_to_day(self):
        """Invalid bucket → day format."""
        m = Memory(max_entries=100)
        m._entries.append(MemoryEntry(content="x", timestamp=datetime(2026, 7, 1)))
        result = m.timeline(bucket="century")
        assert "2026-07-01" in result

    def test_sorted_chronologically(self):
        """Keys are in chronological order."""
        m = Memory(max_entries=100)
        dates = [datetime(2026, 7, 3), datetime(2026, 7, 1), datetime(2026, 7, 2)]
        for d in dates:
            m._entries.append(MemoryEntry(content="x", timestamp=d))
        result = m.timeline(bucket="day")
        keys = list(result.keys())
        assert keys == ["2026-07-01", "2026-07-02", "2026-07-03"]

    def test_week_bucket(self):
        """Week bucket uses %Y-W%W format."""
        m = Memory(max_entries=100)
        m._entries.append(MemoryEntry(content="a", timestamp=datetime(2026, 1, 1)))  # Week 0
        m._entries.append(MemoryEntry(content="b", timestamp=datetime(2026, 1, 8)))  # Week 1
        result = m.timeline(bucket="week")
        assert len(result) == 2
        assert all(k.startswith("2026-W") for k in result.keys())

    def test_same_day_multiple_entries(self):
        """Multiple entries same day counted together."""
        m = Memory(max_entries=100)
        d = datetime(2026, 7, 1)
        for i in range(5):
            m._entries.append(MemoryEntry(content=f"msg{i}", timestamp=d + timedelta(hours=i)))
        result = m.timeline(bucket="day")
        assert result["2026-07-01"] == 5
