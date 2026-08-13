"""Tests for F49: tag_summary() and F50: export_tsv()."""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry


class TestTagSummary:
    """F49: Per-tag analytics."""

    def _make_memory(self):
        m = Memory(max_entries=50)
        m.add("Learned Python basics", tags=["python", "learning"], importance=0.8)
        m.add("Fixed bug in CLI", tags=["python", "debugging"], importance=0.6)
        m.add("Read AI paper", tags=["research"], importance=0.9)
        m.add("Wrote tests for module", tags=["python", "testing"], importance=0.7)
        m.add("Reviewed PR #42", tags=["review", "python"], importance=0.5)
        return m

    def test_basic_tag_summary(self):
        m = self._make_memory()
        result = m.tag_summary()
        assert "python" in result
        assert "research" in result
        assert "review" in result
        assert "learning" in result
        assert result["python"]["count"] == 4
        assert result["research"]["count"] == 1

    def test_avg_importance(self):
        m = self._make_memory()
        result = m.tag_summary()
        # python: 0.8, 0.6, 0.7, 0.5 = avg 0.65
        assert abs(result["python"]["avg_importance"] - 0.65) < 0.01
        assert result["research"]["avg_importance"] == 0.9

    def test_latest_timestamp(self):
        m = self._make_memory()
        result = m.tag_summary()
        assert "latest" in result["python"]
        datetime.fromisoformat(result["python"]["latest"])

    def test_representative_content(self):
        m = self._make_memory()
        result = m.tag_summary()
        assert "representative" in result["python"]
        assert len(result["python"]["representative"]) <= 100

    def test_min_count_filter(self):
        m = self._make_memory()
        result = m.tag_summary(min_count=2)
        assert "python" in result
        assert "research" not in result
        assert "review" not in result

    def test_empty_memory(self):
        m = Memory()
        assert m.tag_summary() == {}

    def test_no_tags(self):
        m = Memory()
        m.add("untagged entry")
        m.add("another untagged")
        assert m.tag_summary() == {}

    def test_single_tag_multiple_entries(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}", tags=["same-tag"], importance=0.5 + i * 0.1)
        result = m.tag_summary()
        assert result["same-tag"]["count"] == 5
        assert abs(result["same-tag"]["avg_importance"] - 0.7) < 0.01

    def test_sorted_by_tag_name(self):
        m = self._make_memory()
        result = m.tag_summary()
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_tags_are_strings(self):
        m = self._make_memory()
        result = m.tag_summary()
        for tag in result:
            assert isinstance(tag, str)


class TestExportTsv:
    """F50: TSV export."""

    def _make_memory(self):
        m = Memory(max_entries=50)
        m.add("Hello world", tags=["greeting"], importance=0.8)
        m.add("Fix tab bug newline", tags=["debug"], importance=0.5)
        m.add("Research paper", tags=["research"], importance=0.9,
              metadata={"key": "value"})
        return m

    def test_has_header(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        lines = tsv.split("\n")
        assert lines[0] == "index\ttimestamp\tcontent\timportance\ttags\tmetadata"

    def test_row_count(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        lines = tsv.split("\n")
        assert len(lines) == 4  # header + 3 entries

    def test_exact_column_count(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        for line in tsv.split("\n")[1:]:
            if line.strip():
                assert line.count("\t") == 5

    def test_tag_filter(self):
        m = self._make_memory()
        tsv = m.export_tsv(tags=["greeting"])
        lines = tsv.split("\n")
        assert len(lines) == 2  # header + 1 entry

    def test_empty_memory(self):
        m = Memory()
        tsv = m.export_tsv()
        lines = tsv.split("\n")
        assert lines[0] == "index\ttimestamp\tcontent\timportance\ttags\tmetadata"
        assert len(lines) == 1

    def test_metadata_json(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        found = False
        for line in tsv.split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 6:
                try:
                    meta = json.loads(parts[5])
                    if "key" in meta and meta["key"] == "value":
                        found = True
                except json.JSONDecodeError:
                    pass
        assert found, "Metadata JSON not found in TSV output"

    def test_importance_preserved(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        importances = set()
        for line in tsv.split("\n")[1:]:
            if line.strip():
                parts = line.split("\t")
                importances.add(float(parts[3]))
        assert 0.8 in importances
        assert 0.5 in importances

    def test_tsv_parseable(self):
        m = self._make_memory()
        tsv = m.export_tsv()
        lines = tsv.split("\n")
        assert lines[0].split("\t") == ["index", "timestamp", "content",
                                         "importance", "tags", "metadata"]
        for line in lines[1:]:
            if line.strip():
                assert len(line.split("\t")) == 6
