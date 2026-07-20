"""F31: Export formats — export_markdown() + export_csv()"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry


@pytest.fixture
def mem():
    m = Memory()
    m.add("Hello world", tags=["greeting"], importance=0.8)
    m.add("Goodbye world", tags=["farewell"], importance=0.3)
    m.add("Hello again", tags=["greeting"], importance=0.6)
    return m


# --- export_markdown ---

def test_markdown_basic(mem):
    md = mem.export_markdown()
    assert "# Memory Export" in md
    assert "Hello world" in md
    assert "Goodbye world" in md


def test_markdown_has_toc(mem):
    md = mem.export_markdown()
    assert "## Table of Contents" in md


def test_markdown_has_metadata(mem):
    m = Memory()
    m.add("test", metadata={"key": "value"}, tags=["a"])
    md = m.export_markdown()
    assert "**Metadata:**" in md
    assert '"key": "value"' in md


def test_markdown_has_importance(mem):
    md = mem.export_markdown()
    assert "**Importance:**" in md
    assert "0.80" in md


def test_markdown_has_timestamp(mem):
    md = mem.export_markdown()
    assert "**Timestamp:**" in md


def test_markdown_has_tags(mem):
    md = mem.export_markdown()
    assert "**Tags:**" in md
    assert "greeting" in md


def test_markdown_has_separator(mem):
    md = mem.export_markdown()
    assert "---" in md


def test_markdown_has_entry_count(mem):
    md = mem.export_markdown()
    assert "3 entries" in md


def test_markdown_filter_by_tags(mem):
    md = mem.export_markdown(tags=["greeting"])
    assert "Hello world" in md
    assert "Hello again" in md
    assert "Goodbye world" not in md


def test_markdown_filter_by_nonexistent_tag(mem):
    md = mem.export_markdown(tags=["nonexistent"])
    assert "_No entries._" in md


def test_markdown_entries_section(mem):
    md = mem.export_markdown()
    assert "## Entries" in md


def test_markdown_exported_timestamp(mem):
    md = mem.export_markdown()
    assert "exported" in md


def test_markdown_empty_memory():
    m = Memory()
    md = m.export_markdown()
    assert "_No entries._" in md


def test_markdown_content_multiline():
    m = Memory()
    m.add("Line 1\nLine 2\nLine 3")
    md = m.export_markdown()
    assert "Line 1" in md
    assert "Line 2" in md
    assert "Line 3" in md


# --- export_csv ---

def test_csv_basic(mem):
    csv = mem.export_csv()
    assert "index,timestamp,importance,tags,content,metadata" in csv


def test_csv_row_count(mem):
    csv = mem.export_csv()
    lines = csv.strip().split("\n")
    assert len(lines) == 4  # header + 3 entries


def test_csv_content_escaped():
    m = Memory()
    m.add('He said "hello" to her')
    csv = m.export_csv()
    assert '""hello""' in csv  # Double-escaped


def test_csv_tags_semicolon_separated(mem):
    m = Memory()
    m.add("entry", tags=["a", "b", "c"])
    csv = m.export_csv()
    assert "a;b;c" in csv


def test_csv_no_tags_empty(mem):
    m = Memory()
    m.add("no tags")
    csv = m.export_csv()
    lines = csv.strip().split("\n")
    # tags field should be empty between commas
    assert ',"",' in lines[1] or ',,' in lines[1]


def test_csv_filter_by_tags(mem):
    csv = mem.export_csv(tags=["greeting"])
    lines = csv.strip().split("\n")
    assert len(lines) == 3  # header + 2 greeting entries


def test_csv_metadata_present():
    m = Memory()
    m.add("test", metadata={"score": 42})
    csv = m.export_csv()
    # CSV escaping: " -> ""
    assert 'score' in csv and '42' in csv


def test_csv_index_sequential(mem):
    csv = mem.export_csv()
    lines = csv.strip().split("\n")
    for i, line in enumerate(lines[1:]):
        assert line.startswith(f"{i},")


def test_csv_empty_memory():
    m = Memory()
    csv = m.export_csv()
    assert "index,timestamp,importance,tags,content,metadata" in csv
    assert csv.strip().split("\n") == ["index,timestamp,importance,tags,content,metadata"]


def test_csv_importance_format():
    m = Memory()
    m.add("test", importance=0.5)
    csv = m.export_csv()
    assert "0.5000" in csv


# --- _filter_by_tags internal ---

def test_filter_by_tags_single(mem):
    result = mem._filter_by_tags(["greeting"])
    assert len(result) == 2


def test_filter_by_tags_multiple_or(mem):
    result = mem._filter_by_tags(["greeting", "farewell"])
    assert len(result) == 3  # OR semantics
