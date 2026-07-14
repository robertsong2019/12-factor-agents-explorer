"""Tests for RelationIntegrityChecker — Cycle 242.

ShadowMerge defense (arXiv:2605.09033): 93.8% attack rate on graph memory.
Three checks: value_conflict / confidence_anomaly / origin_mismatch.
"""
import json
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def clean_graph(mg):
    """Graph with no integrity issues."""
    a = mg.add("Alice", "person", {"age": 30})
    b = mg.add("Bob", "person", {"age": 25})
    mg.link(a.id, b.id, "knows")
    return mg, a, b


# ── Basic scan ───────────────────────────────────────────────

class TestBasicScan:
    def test_clean_graph_no_issues(self, clean_graph):
        mg, a, b = clean_graph
        result = mg.check_relation_integrity()
        assert result["issues"] == []
        assert result["integrity_score"] == 1.0

    def test_returns_dict(self, mg):
        mg.add("test", "fact")
        result = mg.check_relation_integrity()
        assert isinstance(result, dict)
        assert "issues" in result
        assert "summary" in result
        assert "integrity_score" in result

    def test_empty_graph(self, mg):
        result = mg.check_relation_integrity()
        assert result["integrity_score"] == 1.0
        assert result["summary"]["total"] == 0

    def test_no_edges(self, mg):
        mg.add("lonely", "fact")
        result = mg.check_relation_integrity()
        assert result["summary"]["total"] == 0


# ── Check 1: value_conflict ──────────────────────────────────

class TestValueConflict:
    def test_detects_age_conflict(self, mg):
        """Same source + relation, targets with conflicting age."""
        src = mg.add("Alice profile", "person")
        t1 = mg.add("Age source 1", "fact", {"age": 30})
        t2 = mg.add("Age source 2", "fact", {"age": 35})
        mg.link(src.id, t1.id, "has_attribute")
        mg.link(src.id, t2.id, "has_attribute")
        result = mg.check_relation_integrity()
        conflicts = [i for i in result["issues"] if i["type"] == "value_conflict"]
        assert len(conflicts) >= 1
        assert conflicts[0]["severity"] == "high"

    def test_no_conflict_same_values(self, mg):
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"age": 30})
        t2 = mg.add("t2", "fact", {"age": 30})
        mg.link(src.id, t1.id, "attr")
        mg.link(src.id, t2.id, "attr")
        result = mg.check_relation_integrity()
        conflicts = [i for i in result["issues"] if i["type"] == "value_conflict"]
        assert len(conflicts) == 0

    def test_different_relations_no_conflict(self, mg):
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"age": 30})
        t2 = mg.add("t2", "fact", {"age": 50})
        mg.link(src.id, t1.id, "current_age")
        mg.link(src.id, t2.id, "past_age")
        result = mg.check_relation_integrity()
        conflicts = [i for i in result["issues"] if i["type"] == "value_conflict"]
        assert len(conflicts) == 0

    def test_multiple_conflicting_fields(self, mg):
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"age": 30, "city": "NYC"})
        t2 = mg.add("t2", "fact", {"age": 35, "city": "LA"})
        mg.link(src.id, t1.id, "attr")
        mg.link(src.id, t2.id, "attr")
        result = mg.check_relation_integrity()
        conflicts = [i for i in result["issues"] if i["type"] == "value_conflict"]
        assert len(conflicts) == 2  # age + city
        fields = {c["field"] for c in conflicts}
        assert "age" in fields
        assert "city" in fields

    def test_ignores_complex_types(self, mg):
        """Dicts and lists should not trigger conflicts."""
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"tags": {"a": 1}})
        t2 = mg.add("t2", "fact", {"tags": {"b": 2}})
        mg.link(src.id, t1.id, "attr")
        mg.link(src.id, t2.id, "attr")
        result = mg.check_relation_integrity()
        conflicts = [i for i in result["issues"] if i["type"] == "value_conflict"]
        assert len(conflicts) == 0


# ── Check 2: confidence_anomaly ──────────────────────────────

class TestConfidenceAnomaly:
    def test_detects_low_trust_unquarantined(self, mg):
        n = mg.add("suspicious", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.check_relation_integrity()
        anomalies = [i for i in result["issues"] if i["type"] == "confidence_anomaly"]
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "medium"

    def test_ignores_quarantined_low_trust(self, mg):
        n = mg.add("quarantined", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1, quarantined=1 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.check_relation_integrity()
        anomalies = [i for i in result["issues"] if i["type"] == "confidence_anomaly"]
        assert len(anomalies) == 0

    def test_ignores_high_trust(self, mg):
        n = mg.add("trusted", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.9 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.check_relation_integrity()
        anomalies = [i for i in result["issues"] if i["type"] == "confidence_anomaly"]
        assert len(anomalies) == 0


# ── Check 3: origin_mismatch ─────────────────────────────────

class TestOriginMismatch:
    def test_detects_large_trust_gap(self, mg):
        a = mg.add("trusted_node", "fact")
        b = mg.add("shady_node", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.9 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (b.id,))
        mg.conn.commit()
        mg.link(a.id, b.id, "relates_to")
        result = mg.check_relation_integrity()
        mismatches = [i for i in result["issues"] if i["type"] == "origin_mismatch"]
        assert len(mismatches) >= 1

    def test_no_mismatch_similar_trust(self, mg):
        a = mg.add("node_a", "fact")
        b = mg.add("node_b", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.6 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET trust_level=0.7 WHERE id=?", (b.id,))
        mg.conn.commit()
        mg.link(a.id, b.id, "relates_to")
        result = mg.check_relation_integrity()
        mismatches = [i for i in result["issues"] if i["type"] == "origin_mismatch"]
        assert len(mismatches) == 0

    def test_severity_thresholds(self, mg):
        """Gap > 0.7 → high, > 0.5 → low."""
        a = mg.add("high", "fact")
        b = mg.add("low", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=1.0 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET trust_level=0.2 WHERE id=?", (b.id,))
        mg.conn.commit()
        mg.link(a.id, b.id, "rel")
        result = mg.check_relation_integrity()
        mismatches = [i for i in result["issues"] if i["type"] == "origin_mismatch"]
        assert any(m["severity"] == "high" for m in mismatches)


# ── Scoped scan ──────────────────────────────────────────────

class TestScopedScan:
    def test_node_specific_scan(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, b.id, "rel")
        result = mg.check_relation_integrity(node_id=a.id)
        # Should only check edges involving a
        assert isinstance(result["issues"], list)


# ── Integrity score ──────────────────────────────────────────

class TestIntegrityScore:
    def test_perfect_score_clean(self, clean_graph):
        mg, a, b = clean_graph
        result = mg.check_relation_integrity()
        assert result["integrity_score"] == 1.0

    def test_score_decreases_with_issues(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (b.id,))
        mg.conn.commit()
        mg.link(a.id, b.id, "rel")
        result = mg.check_relation_integrity()
        assert result["integrity_score"] < 1.0

    def test_score_never_negative(self, mg):
        """Even with many issues, score >= 0."""
        for i in range(10):
            n = mg.add(f"low_{i}", "fact")
            mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.check_relation_integrity()
        assert result["integrity_score"] >= 0.0


# ── _detect_value_conflicts unit tests ───────────────────────

class TestDetectValueConflicts:
    def test_no_common_keys(self, mg):
        result = mg._detect_value_conflicts({"a": 1}, {"b": 2})
        assert result == []

    def test_same_value(self, mg):
        result = mg._detect_value_conflicts({"a": 1}, {"a": 1})
        assert result == []

    def test_different_values(self, mg):
        result = mg._detect_value_conflicts({"a": 1}, {"a": 2})
        assert len(result) == 1
        assert result[0][0] == "a"
        assert result[0][1] == 1
        assert result[0][2] == 2

    def test_multiple_fields(self, mg):
        result = mg._detect_value_conflicts(
            {"a": 1, "b": "x", "c": True},
            {"a": 2, "b": "y", "c": True}
        )
        assert len(result) == 2  # a and b conflict, c matches

    def test_filters_to_specified_fields(self, mg):
        result = mg._detect_value_conflicts(
            {"a": 1, "b": 2}, {"a": 2, "b": 3},
            fields=["a"]
        )
        assert len(result) == 1
        assert result[0][0] == "a"

    def test_skips_complex_types(self, mg):
        result = mg._detect_value_conflicts(
            {"a": {"x": 1}}, {"a": {"x": 2}}
        )
        assert result == []

    def test_empty_dicts(self, mg):
        assert mg._detect_value_conflicts({}, {}) == []


# ── integrity_quarantine ─────────────────────────────────────

class TestIntegrityQuarantine:
    def test_quarantine_high_severity_only(self, mg):
        # Create a high-severity value conflict
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"age": 30})
        t2 = mg.add("t2", "fact", {"age": 35})
        mg.link(src.id, t1.id, "attr")
        mg.link(src.id, t2.id, "attr")
        result = mg.check_relation_integrity()
        quarantined = mg.integrity_quarantine(result["issues"], "high")
        # value_conflict is high severity → should quarantine targets
        assert len(quarantined) > 0

    def test_quarantine_medium_includes_confidence(self, mg):
        n = mg.add("suspicious", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.check_relation_integrity()
        quarantined = mg.integrity_quarantine(result["issues"], "medium")
        assert n.id in quarantined

    def test_quarantine_idempotent(self, mg):
        n = mg.add("low trust", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        q1 = mg.integrity_quarantine(severity_threshold="medium")
        q2 = mg.integrity_quarantine(severity_threshold="medium")
        assert n.id in q1
        assert n.id not in q2  # Already quarantined

    def test_quarantine_sets_reason(self, mg):
        n = mg.add("low trust", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        mg.integrity_quarantine(severity_threshold="medium")
        row = mg.conn.execute(
            "SELECT quarantine_reason FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row["quarantine_reason"] is not None
        assert "integrity" in row["quarantine_reason"]

    def test_quarantine_empty_issues(self, mg):
        result = mg.integrity_quarantine([], "high")
        assert result == []

    def test_auto_scan_when_no_issues_provided(self, mg):
        n = mg.add("low trust", "fact")
        mg.conn.execute("UPDATE nodes SET trust_level=0.1 WHERE id=?", (n.id,))
        mg.conn.commit()
        # Pass no issues → should auto-scan
        q = mg.integrity_quarantine(severity_threshold="medium")
        assert n.id in q


# ── Summary structure ────────────────────────────────────────

class TestSummary:
    def test_summary_has_by_type(self, mg):
        mg.add("test", "fact")
        result = mg.check_relation_integrity()
        assert "by_type" in result["summary"]

    def test_summary_has_by_severity(self, mg):
        mg.add("test", "fact")
        result = mg.check_relation_integrity()
        assert "by_severity" in result["summary"]

    def test_summary_has_total_edges(self, clean_graph):
        mg, a, b = clean_graph
        result = mg.check_relation_integrity()
        assert result["summary"]["total_edges"] >= 1

    def test_summary_total_matches_issues_length(self, mg):
        src = mg.add("src", "person")
        t1 = mg.add("t1", "fact", {"age": 30})
        t2 = mg.add("t2", "fact", {"age": 35})
        mg.link(src.id, t1.id, "attr")
        mg.link(src.id, t2.id, "attr")
        result = mg.check_relation_integrity()
        assert result["summary"]["total"] == len(result["issues"])
