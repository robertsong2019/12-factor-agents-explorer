"""
Tests for ResidualExtractor — compression residuals recovery.
Research #045: ProGraph pattern. Disabling residuals costs -8.6pp on LoCoMo.
"""

import pytest
from memory_graph import MemoryGraph, ResidualExtractor


@pytest.fixture
def extractor():
    return ResidualExtractor()


class TestExtractDates:
    def test_iso_date(self, extractor):
        r = extractor.extract("Meeting on 2026-08-09 was great")
        assert any("2026-08-09" in x for x in r)

    def test_slash_date(self, extractor):
        r = extractor.extract("Deadline 2026/08/09")
        assert any("2026/08/09" in x for x in r)

    def test_month_name_date(self, extractor):
        r = extractor.extract("Scheduled for August 9")
        assert any("August 9" in x for x in r)

    def test_relative_date(self, extractor):
        r = extractor.extract("Let's meet tomorrow")
        assert any("tomorrow" in x for x in r)

    def test_no_dates(self, extractor):
        r = extractor.extract("Just a regular sentence")
        assert not any(x.startswith("date:") for x in r)


class TestExtractQuantities:
    test_cases = [
        ("Ran 5km today", "5km"),
        ("Took 300ms", "300ms"),
        ("Score: 85%", "85%"),
        ("Weight 70.5kg", "70.5kg"),
        ("Waited 30min", "30min"),
    ]

    def test_quantities(self, extractor):
        for content, expected in self.test_cases:
            r = extractor.extract(content)
            assert any(expected in x for x in r), f"Expected '{expected}' in {r}"

    def test_no_quantities(self, extractor):
        r = extractor.extract("Hello world")
        assert not any(x.startswith("quantity:") for x in r)


class TestExtractFromData:
    def test_key_value_pairs(self, extractor):
        r = extractor.extract("test", {"priority": "high", "count": 42})
        assert any("priority: high" in x for x in r)
        assert any("count: 42" in x for x in r)

    def test_empty_data(self, extractor):
        r = extractor.extract("test", {})
        assert isinstance(r, list)

    def test_none_data(self, extractor):
        r = extractor.extract("test", None)
        assert isinstance(r, list)


class TestExtractEntities:
    def test_capitalized_names(self, extractor):
        r = extractor.extract("Met John Smith at the park")
        assert any("John Smith" in x for x in r)

    def test_single_capitalized_not_entity(self, extractor):
        # Single capitalized words should not be entities
        r = extractor.extract("The quick")
        assert not any(x.startswith("entity:") for x in r)

    def test_multiple_entities(self, extractor):
        r = extractor.extract("Alice Brown and Bob Jones presented")
        entities = [x for x in r if x.startswith("entity:")]
        assert len(entities) >= 2


class TestExtractURLs:
    def test_http_url(self, extractor):
        r = extractor.extract("See https://example.com/docs")
        assert any("example.com" in x for x in r)

    def test_no_urls(self, extractor):
        r = extractor.extract("No links here")
        assert not any(x.startswith("url:") for x in r)


class TestExtractEmails:
    def test_simple_email(self, extractor):
        r = extractor.extract("Contact alice@example.com")
        assert any("alice@example.com" in x for x in r)

    def test_plus_addressing(self, extractor):
        r = extractor.extract("Send to bob+filter@test.org")
        assert any("bob+filter@test.org" in x for x in r)

    def test_no_emails(self, extractor):
        r = extractor.extract("Just text without emails")
        assert not any(x.startswith("email:") for x in r)


class TestExtractVersions:
    def test_semver(self, extractor):
        r = extractor.extract("Upgraded to v1.2.3")
        assert any("v1.2.3" in x for x in r)

    def test_two_part_version(self, extractor):
        r = extractor.extract("Using library 2.0")
        assert any("2.0" in x for x in r)

    def test_pre_release(self, extractor):
        r = extractor.extract("Released 3.0.0-beta.1")
        assert any("3.0.0-beta.1" in x for x in r)

    def test_date_not_version(self, extractor):
        # Year-like numbers should not be treated as versions
        r = extractor.extract("In 2026.08 we shipped")
        assert not any(x.startswith("version:") for x in r)


class TestExtractPaths:
    def test_src_path(self, extractor):
        r = extractor.extract("Modified src/index.ts today")
        assert any("src/index.ts" in x for x in r)

    def test_test_path(self, extractor):
        r = extractor.extract("Added test/utils.py for coverage")
        assert any("test/utils.py" in x for x in r)

    def test_no_paths(self, extractor):
        r = extractor.extract("No file references")
        assert not any(x.startswith("path:") for x in r)


class TestDeduplication:
    def test_duplicate_dates_deduped(self, extractor):
        r = extractor.extract("2026-08-09 and 2026-08-09")
        date_count = sum(1 for x in r if "2026-08-09" in x)
        assert date_count == 1

    def test_unique_preserved(self, extractor):
        r = extractor.extract("2026-08-09 and 2026-08-10")
        assert len(r) >= 2


class TestExtractFromNode:
    def test_extract_from_graph_node(self, extractor):
        mg = MemoryGraph()
        n = mg.add("Meeting 2026-08-09", "event", {"attendees": 5, "location": "Room A"})
        r = extractor.extract_from_node(mg, n.id)
        assert any("2026-08-09" in x for x in r)
        assert any("attendees: 5" in x for x in r)
        assert any("location: Room A" in x for x in r)

    def test_extract_from_nonexistent_node(self, extractor):
        mg = MemoryGraph()
        r = extractor.extract_from_node(mg, "nonexistent")
        assert r == []


class TestCompressionAudit:
    def test_audit_structure(self, extractor):
        mg = MemoryGraph()
        s1 = mg.add("Meeting on 2026-08-09 with John Smith", "event",
                    {"location": "Room A", "count": 5})
        s2 = mg.add("Workshop on 2026-08-10", "event", {"attendees": 12})
        summary = mg.add("Events summary", "summary", {})
        result = extractor.compression_audit(mg, summary.id, [s1.id, s2.id])
        assert "total_source_residuals" in result
        assert "preserved" in result
        assert "lost" in result
        assert "retention_rate" in result

    def test_perfect_retention(self, extractor):
        mg = MemoryGraph()
        source = mg.add("Meeting 2026-08-09", "event", {})
        summary = mg.add("Meeting 2026-08-09", "summary", {})
        result = extractor.compression_audit(mg, summary.id, [source.id])
        assert result["retention_rate"] == 1.0

    def test_partial_loss(self, extractor):
        mg = MemoryGraph()
        s1 = mg.add("Met on 2026-08-09 with 5kg of materials", "event", {"priority": "high"})
        # Summary drops the date and quantity
        summary = mg.add("Materials meeting", "summary", {"priority": "high"})
        result = extractor.compression_audit(mg, summary.id, [s1.id])
        assert result["retention_rate"] < 1.0
        assert result["lost"] > 0
        assert any("2026-08-09" in x for x in result["lost_residuals"])

    def test_empty_sources(self, extractor):
        mg = MemoryGraph()
        summary = mg.add("Summary", "summary", {})
        result = extractor.compression_audit(mg, summary.id, [])
        assert result["retention_rate"] == 1.0
        assert result["total_source_residuals"] == 0

    def test_multiple_sources(self, extractor):
        mg = MemoryGraph()
        s1 = mg.add("Event on 2026-08-09", "event", {"a": 1})
        s2 = mg.add("Event on 2026-08-10", "event", {"b": 2})
        s3 = mg.add("Event on 2026-08-11", "event", {"c": 3})
        summary = mg.add("Three events", "summary", {})
        result = extractor.compression_audit(mg, summary.id, [s1.id, s2.id, s3.id])
        assert result["source_count"] == 3
        assert result["total_source_residuals"] > 0
        assert result["lost"] > 0  # summary doesn't contain these facts
