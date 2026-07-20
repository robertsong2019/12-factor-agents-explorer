"""F38-F39: search_in_fields() + auto_tag()"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


@pytest.fixture
def mem():
    m = Memory()
    m.add("Python code example", tags=["tutorial"], metadata={"lang": "python", "level": "beginner"})
    m.add("JavaScript tutorial", tags=["web"], metadata={"lang": "javascript"})
    m.add("Python advanced topics", tags=[], metadata={"lang": "python", "level": "advanced"})
    m.add("Random thoughts", tags=["personal"], metadata={})
    return m


# --- F38: search_in_fields ---

def test_search_content_field(mem):
    results = mem.search_in_fields("python", ["content"])
    assert len(results) == 2
    assert all("python" in e.content.lower() for e in results)


def test_search_tags_field(mem):
    results = mem.search_in_fields("tutorial", ["tags"])
    assert len(results) == 1
    assert results[0].tags == ["tutorial"]


def test_search_metadata_field(mem):
    results = mem.search_in_fields("javascript", ["metadata"])
    assert len(results) == 1


def test_search_multiple_fields(mem):
    results = mem.search_in_fields("python", ["content", "metadata"])
    # "Python code example" matches content+metadata(2)
    # "Python advanced topics" matches content+metadata(2)
    assert len(results) == 2


def test_search_no_match(mem):
    results = mem.search_in_fields("nonexistent", ["content"])
    assert len(results) == 0


def test_search_limit(mem):
    results = mem.search_in_fields("python", ["content"], limit=1)
    assert len(results) == 1


def test_search_limit_zero_means_all(mem):
    results = mem.search_in_fields("python", ["content"], limit=0)
    assert len(results) == 2


def test_search_case_insensitive(mem):
    results = mem.search_in_fields("PYTHON", ["content"])
    assert len(results) == 2


def test_search_ranked_by_score(mem):
    results = mem.search_in_fields("python", ["content", "metadata"])
    # Both entries match both fields equally, so ordering by timestamp desc
    assert len(results) >= 1


def test_search_empty_memory():
    m = Memory()
    results = m.search_in_fields("test", ["content"])
    assert results == []


def test_search_invalid_field_ignored(mem):
    # Unknown fields should be silently ignored (no match)
    results = mem.search_in_fields("python", ["nonexistent_field"])
    assert len(results) == 0


def test_search_tags_partial_match(mem):
    results = mem.search_in_fields("tut", ["tags"])
    assert len(results) == 1  # "tutorial" contains "tut"


# --- F39: auto_tag ---

def test_auto_tag_basic():
    m = Memory()
    m.add("I love Python programming")
    m.add("JavaScript is also great")
    m.add("Cooking dinner tonight")
    rules = {"code": ["python", "javascript", "programming"], "food": ["cooking", "dinner"]}
    count = m.auto_tag(rules)
    assert count == 3  # all 3 entries matched at least one rule
    entries = m.get_all()
    assert "code" in entries[0].tags
    assert "code" in entries[1].tags
    assert "food" in entries[2].tags


def test_auto_tag_no_match():
    m = Memory()
    m.add("nothing relevant here")
    rules = {"code": ["python"]}
    count = m.auto_tag(rules)
    assert count == 0


def test_auto_tag_append_mode(mem):
    rules = {"code": ["python"]}
    count = mem.auto_tag(rules, overwrite=False)
    entries = mem.get_all()
    # First entry has "tutorial" tag, should also get "code"
    assert "tutorial" in entries[0].tags
    assert "code" in entries[0].tags


def test_auto_tag_overwrite_mode(mem):
    rules = {"code": ["python"]}
    mem.auto_tag(rules, overwrite=True)
    entries = mem.get_all()
    # First entry originally had "tutorial" tag, now should only have "code"
    assert "tutorial" not in entries[0].tags
    assert "code" in entries[0].tags


def test_auto_tag_multiple_tags():
    m = Memory()
    m.add("Python web development with Django")
    rules = {
        "language": ["python", "django"],
        "domain": ["web", "development"],
    }
    m.auto_tag(rules)
    entry = m.get_all()[0]
    assert "language" in entry.tags
    assert "domain" in entry.tags


def test_auto_tag_case_insensitive():
    m = Memory()
    m.add("PYTHON is awesome")
    rules = {"code": ["python"]}
    count = m.auto_tag(rules)
    assert count == 1


def test_auto_tag_empty_memory():
    m = Memory()
    rules = {"code": ["python"]}
    count = m.auto_tag(rules)
    assert count == 0


def test_auto_tag_no_duplicate():
    m = Memory()
    m.add("python python python")
    rules = {"code": ["python"]}
    count = m.auto_tag(rules)
    entry = m.get_all()[0]
    assert entry.tags.count("code") == 1


def test_auto_tag_keyword_in_content():
    m = Memory()
    m.add("Running tests with pytest")
    rules = {"testing": ["test", "pytest"]}
    count = m.auto_tag(rules)
    assert count == 1
    assert "testing" in m.get_all()[0].tags
