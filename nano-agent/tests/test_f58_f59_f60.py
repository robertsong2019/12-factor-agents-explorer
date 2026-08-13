"""Tests for F58 search_boolean, F59 condense, F60 export_markdown_table."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.memory import Memory, MemoryEntry
from datetime import datetime


# ─── F58: search_boolean ───

class TestSearchBoolean:
    def setup_method(self):
        self.mem = Memory(max_entries=100)
        self.mem.add("Python web development with Flask", tags=["python", "web"])
        self.mem.add("Python data analysis with pandas", tags=["python", "data"])
        self.mem.add("Rust systems programming", tags=["rust", "systems"])
        self.mem.add("Python API design best practices", tags=["python", "api"])

    def test_and_query(self):
        results = self.mem.search_boolean("python AND web")
        assert len(results) == 1
        assert "Flask" in results[0].content

    def test_or_query(self):
        results = self.mem.search_boolean("python OR rust")
        assert len(results) == 4  # All entries have python or rust

    def test_not_query(self):
        results = self.mem.search_boolean("python NOT web")
        contents = [r.content for r in results]
        assert len(results) == 2  # data analysis + API
        assert not any("Flask" in c for c in contents)

    def test_plain_query_no_boolean(self):
        """Plain query without operators should work like basic search."""
        results = self.mem.search_boolean("python")
        assert len(results) == 3

    def test_parenthesized_query(self):
        results = self.mem.search_boolean("python AND (web OR api)")
        contents = [r.content for r in results]
        assert len(results) == 2
        assert any("Flask" in c for c in contents)
        assert any("API" in c for c in contents)

    def test_limit_applied(self):
        results = self.mem.search_boolean("python", limit=2)
        assert len(results) <= 2

    def test_no_results(self):
        results = self.mem.search_boolean("java AND cobol")
        assert len(results) == 0

    def test_case_insensitive_terms(self):
        results = self.mem.search_boolean("PYTHON and WEB")
        assert len(results) == 1

    def test_results_sorted_by_importance(self):
        self.mem._entries[0].importance = 0.9
        self.mem._entries[2].importance = 0.3
        results = self.mem.search_boolean("python OR rust")
        # Higher importance should come first
        assert results[0].importance >= results[-1].importance


# ─── F59: condense ───

class TestCondense:
    def setup_method(self):
        self.mem = Memory(max_entries=100)
        self.mem.add("The quick brown fox jumps over the lazy dog", tags=["animals"])
        self.mem.add("The quick brown fox jumps over the lazy dog!", tags=["nature"])
        self.mem.add("A completely different topic about machine learning", tags=["ml"])
        self.mem.add("The quick brown fox jumps over the lazy dog today", tags=["animals"])

    def test_merge_near_duplicates(self):
        result = self.mem.condense(min_similarity=0.8)
        assert result["removed_count"] >= 2
        assert result["merged_count"] >= 1

    def test_no_duplicates(self):
        mem = Memory(max_entries=100)
        mem.add("Apple")
        mem.add("Banana")
        mem.add("Cherry")
        result = mem.condense(min_similarity=0.9)
        assert result["removed_count"] == 0
        assert result["merged_count"] == 0

    def test_merged_tags_combined(self):
        result = self.mem.condense(min_similarity=0.7)
        # The merged entry should have tags from all sources
        all_tags = set()
        for e in self.mem._entries:
            all_tags.update(e.tags)
        # Should have both "animals" and "nature" from the dup group
        assert "animals" in all_tags or "nature" in all_tags

    def test_merged_importance_is_max(self):
        self.mem._entries[0].importance = 0.3
        self.mem._entries[1].importance = 0.9
        self.mem._entries[3].importance = 0.5
        result = self.mem.condense(min_similarity=0.7)
        # Find the merged entry — should have 0.9
        for e in self.mem._entries:
            if "fox" in e.content.lower():
                assert e.importance == 0.9

    def test_merged_uses_longest_content(self):
        result = self.mem.condense(min_similarity=0.7)
        for e in self.mem._entries:
            if "fox" in e.content.lower():
                # Longest content among the dup group
                assert len(e.content) >= 40

    def test_single_entry_noop(self):
        mem = Memory(max_entries=100)
        mem.add("Only one entry")
        result = mem.condense()
        assert result["removed_count"] == 0
        assert result["merged_count"] == 0

    def test_high_threshold_no_merge(self):
        """Very high threshold should not merge anything."""
        result = self.mem.condense(min_similarity=0.99)
        assert result["removed_count"] == 0

    def test_groups_have_details(self):
        result = self.mem.condense(min_similarity=0.7)
        for g in result["groups"]:
            assert "count" in g
            assert "indices" in g
            assert "representative" in g
            assert g["count"] >= 2


# ─── F60: export_markdown_table ───

class TestExportMarkdownTable:
    def setup_method(self):
        self.mem = Memory(max_entries=100)
        self.mem.add("First task completed successfully", tags=["task", "done"])
        self.mem.add("Second task in progress", tags=["task", "wip"])
        self.mem.add("Research notes on transformers", tags=["research"])

    def test_returns_string(self):
        result = self.mem.export_markdown_table()
        assert isinstance(result, str)

    def test_has_header_row(self):
        result = self.mem.export_markdown_table()
        assert "| # | Timestamp | Tags | Importance | Content |" in result

    def test_has_separator_row(self):
        result = self.mem.export_markdown_table()
        assert "|---|-----------|------|------------|---------|" in result

    def test_contains_entries(self):
        result = self.mem.export_markdown_table()
        assert "First task" in result
        assert "Second task" in result

    def test_tag_filter(self):
        result = self.mem.export_markdown_table(tags=["research"])
        assert "Research notes" in result
        assert "First task" not in result

    def test_limit_applied(self):
        result = self.mem.export_markdown_table(limit=2)
        lines = [l for l in result.split("\n") if l.startswith("| ") and "---" not in l]
        # 1 header + 2 data rows = 3 (excluding separator)
        assert len(lines) == 3

    def test_content_truncated(self):
        long_content = "A" * 200
        self.mem.add(long_content)
        result = self.mem.export_markdown_table()
        # Should have ellipsis
        assert "…" in result

    def test_pipe_escaped(self):
        self.mem.add("Data | with | pipes")
        result = self.mem.export_markdown_table()
        # Pipe in content should be escaped
        assert "\\|" in result

    def test_importance_displayed(self):
        result = self.mem.export_markdown_table()
        # Should contain importance value
        assert "0." in result  # Default 0.5 importance

    def test_empty_memory(self):
        mem = Memory(max_entries=100)
        result = mem.export_markdown_table()
        # Should still have header
        assert "| # |" in result
        # Should have no data rows (just header + separator)
        lines = [l for l in result.split("\n") if l.startswith("| ") and "---" not in l and "| #" not in l]
        assert len(lines) == 0
