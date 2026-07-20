"""
Tests for F40 (export_jsonl), F41 (normalize_tags), F42 (entropy)
"""

import json
import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry


# ========== F40: export_jsonl ==========

class TestExportJsonl:
    def test_empty_memory(self):
        m = Memory()
        assert m.export_jsonl() == ""

    def test_single_entry(self):
        m = Memory()
        m.add("hello world", tags=["greeting"])
        result = m.export_jsonl()
        lines = result.strip().split("\n")
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["content"] == "hello world"
        assert obj["tags"] == ["greeting"]

    def test_multiple_entries(self):
        m = Memory()
        m.add("first")
        m.add("second")
        m.add("third")
        result = m.export_jsonl()
        lines = result.strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert "content" in obj
            assert "timestamp" in obj

    def test_no_trailing_newline(self):
        m = Memory()
        m.add("test")
        result = m.export_jsonl()
        assert not result.endswith("\n")

    def test_with_tag_filter(self):
        m = Memory()
        m.add("important thing", tags=["important"])
        m.add("normal thing", tags=["normal"])
        m.add("another important", tags=["important"])
        result = m.export_jsonl(tags=["important"])
        lines = result.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "important" in obj["tags"]

    def test_jsonl_vs_json_export(self):
        m = Memory()
        m.add("entry one", importance=0.8)
        m.add("entry two", importance=0.3)
        jsonl_result = m.export_jsonl()
        json_result = m.export_json()
        # JSONL should NOT be a JSON array, JSON should be
        assert not jsonl_result.strip().startswith("[")
        assert json_result.strip().startswith("[")

    def test_unicode_content(self):
        m = Memory()
        m.add("你好世界", tags=["中文"])
        result = m.export_jsonl()
        obj = json.loads(result)
        assert obj["content"] == "你好世界"
        assert obj["tags"] == ["中文"]

    def test_metadata_preserved(self):
        m = Memory()
        m.add("data", metadata={"source": "test", "score": 42})
        result = m.export_jsonl()
        obj = json.loads(result)
        assert obj["metadata"]["source"] == "test"
        assert obj["metadata"]["score"] == 42

    def test_importance_preserved(self):
        m = Memory()
        m.add("critical", importance=0.95)
        result = m.export_jsonl()
        obj = json.loads(result)
        assert obj["importance"] == 0.95


# ========== F41: normalize_tags ==========

class TestNormalizeTags:
    def test_empty_mapping(self):
        m = Memory()
        m.add("test", tags=["a", "b"])
        assert m.normalize_tags({}) == 0
        assert m.get_all()[0].tags == ["a", "b"]

    def test_simple_rename(self):
        m = Memory()
        m.add("entry1", tags=["bug"])
        m.add("entry2", tags=["bug", "feature"])
        changed = m.normalize_tags({"bug": "issue"})
        assert changed == 2
        assert m.get_all()[0].tags == ["issue"]
        assert m.get_all()[1].tags == ["issue", "feature"]

    def test_merge_multiple_variants(self):
        m = Memory()
        m.add("e1", tags=["bug"])
        m.add("e2", tags=["bugs"])
        m.add("e3", tags=["defect"])
        changed = m.normalize_tags({"bug": "issue", "bugs": "issue", "defect": "issue"})
        assert changed == 3
        for entry in m.get_all():
            assert entry.tags == ["issue"]

    def test_dedup_after_merge(self):
        """When two tags map to the same new tag, result should not have duplicates."""
        m = Memory()
        m.add("entry", tags=["bug", "defect"])
        changed = m.normalize_tags({"bug": "issue", "defect": "issue"})
        assert changed == 1
        assert m.get_all()[0].tags == ["issue"]

    def test_no_change_when_tags_not_in_mapping(self):
        m = Memory()
        m.add("entry", tags=["feature", "ui"])
        changed = m.normalize_tags({"bug": "issue"})
        assert changed == 0
        assert m.get_all()[0].tags == ["feature", "ui"]

    def test_partial_mapping(self):
        m = Memory()
        m.add("e1", tags=["bug", "feature"])
        m.add("e2", tags=["feature", "ui"])
        changed = m.normalize_tags({"bug": "issue"})
        assert changed == 1
        assert m.get_all()[0].tags == ["issue", "feature"]
        assert m.get_all()[1].tags == ["feature", "ui"]

    def test_preserves_order(self):
        m = Memory()
        m.add("entry", tags=["zebra", "alpha", "bug"])
        m.normalize_tags({"bug": "alpha"})  # bug -> alpha, which already exists
        tags = m.get_all()[0].tags
        assert tags == ["zebra", "alpha"]  # alpha stays in its original position, bug removed

    def test_empty_memory(self):
        m = Memory()
        assert m.normalize_tags({"a": "b"}) == 0

    def test_entries_without_tags_unaffected(self):
        m = Memory()
        m.add("no tags")
        m.add("has tag", tags=["bug"])
        changed = m.normalize_tags({"bug": "issue"})
        assert changed == 1
        assert m.get_all()[0].tags == []
        assert m.get_all()[1].tags == ["issue"]

    def test_idempotent(self):
        m = Memory()
        m.add("entry", tags=["bug"])
        first = m.normalize_tags({"bug": "issue"})
        second = m.normalize_tags({"bug": "issue"})
        assert first == 1
        assert second == 0  # Already renamed


# ========== F42: entropy ==========

class TestEntropy:
    def test_empty_memory(self):
        m = Memory()
        result = m.entropy()
        assert result["content_entropy"] == 0.0
        assert result["tag_entropy"] == 0.0
        assert result["unique_contents"] == 0
        assert result["unique_tags"] == 0
        assert result["total_entries"] == 0

    def test_single_entry(self):
        m = Memory()
        m.add("only one")
        result = m.entropy()
        assert result["content_entropy"] == 0.0  # log2(1) = 0
        assert result["unique_contents"] == 1
        assert result["total_entries"] == 1

    def test_all_identical_content(self):
        m = Memory()
        m.add("same")
        m.add("same")
        m.add("same")
        result = m.entropy()
        assert result["content_entropy"] == 0.0  # No diversity
        assert result["unique_contents"] == 1
        assert result["total_entries"] == 3

    def test_all_unique_content(self):
        m = Memory()
        m.add("alpha")
        m.add("beta")
        m.add("gamma")
        m.add("delta")
        result = m.entropy()
        # 4 unique items, uniform distribution: entropy = log2(4) = 2.0
        assert result["content_entropy"] == 2.0
        assert result["unique_contents"] == 4

    def test_mixed_content(self):
        m = Memory()
        m.add("alpha")
        m.add("alpha")
        m.add("beta")
        # P(alpha) = 2/3, P(beta) = 1/3
        # H = -(2/3 * log2(2/3) + 1/3 * log2(1/3))
        expected = -(2/3 * math.log2(2/3) + 1/3 * math.log2(1/3))
        result = m.entropy()
        assert abs(result["content_entropy"] - round(expected, 4)) < 0.01

    def test_tag_entropy(self):
        m = Memory()
        m.add("e1", tags=["a"])
        m.add("e2", tags=["a"])
        m.add("e3", tags=["b"])
        # Tags: a(2), b(1) → total_tags=3, P(a)=2/3, P(b)=1/3
        result = m.entropy()
        expected = -(2/3 * math.log2(2/3) + 1/3 * math.log2(1/3))
        assert abs(result["tag_entropy"] - round(expected, 4)) < 0.01
        assert result["unique_tags"] == 2

    def test_no_tags(self):
        m = Memory()
        m.add("e1")
        m.add("e2")
        result = m.entropy()
        assert result["tag_entropy"] == 0.0
        assert result["unique_tags"] == 0

    def test_max_entropy_uniform(self):
        """8 unique entries → entropy = log2(8) = 3.0"""
        m = Memory()
        for i in range(8):
            m.add(f"unique_{i}")
        result = m.entropy()
        assert result["content_entropy"] == 3.0

    def test_returns_all_fields(self):
        m = Memory()
        m.add("test", tags=["x"])
        result = m.entropy()
        assert "content_entropy" in result
        assert "tag_entropy" in result
        assert "unique_contents" in result
        assert "unique_tags" in result
        assert "total_entries" in result
