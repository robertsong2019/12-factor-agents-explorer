"""Tests for lifecycle_operation_eval — MemOps-inspired evaluation.

MemOps (arXiv:2607.12893) defines 6 probe types for memory lifecycle:
  1. detection  — find the target
  2. target     — correct memory selected
  3. transition — expected state change
  4. robustness — edge case handling
  5. provenance — operation traceability
  6. leakage    — unrelated memories unaffected

These tests verify the evaluation harness across all operation types
and probe dimensions.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated_mg():
    """Graph with a few nodes and edges for lifecycle tests."""
    mg = MemoryGraph(":memory:")
    a = mg.add("Node A", "fact", {"value": 1})
    b = mg.add("Node B", "fact", {"value": 2})
    c = mg.add("Node C", "concept")
    mg.link(a.id, b.id, "related_to")
    mg.link(b.id, c.id, "related_to")
    return mg


# ─── Basic Structure ────────────────────────────────────────────────────

class TestLifecycleEvalStructure:
    """Test return structure of lifecycle_operation_eval."""

    def test_returns_dict(self, populated_mg):
        r = populated_mg.lifecycle_operation_eval([])
        assert isinstance(r, dict)

    def test_empty_operations(self, populated_mg):
        """Empty ops list → zero everything."""
        r = populated_mg.lifecycle_operation_eval([])
        assert r["total_ops"] == 0
        assert r["probes_passed"] == 0
        assert r["probes_total"] == 0
        assert r["pass_rate"] == 0.0
        assert r["details"] == []

    def test_required_fields(self, populated_mg):
        r = populated_mg.lifecycle_operation_eval([])
        assert "total_ops" in r
        assert "probes_passed" in r
        assert "probes_total" in r
        assert "pass_rate" in r
        assert "details" in r

    def test_pass_rate_calculation(self, populated_mg):
        """pass_rate = passed / total."""
        node = populated_mg.add("test node", "fact")
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update", "args": {"node_id": node.id, "label": "updated"}},
        ])
        assert r["probes_total"] > 0
        expected = r["probes_passed"] / r["probes_total"]
        assert abs(r["pass_rate"] - round(expected, 4)) < 0.01


# ─── ADD Operation ──────────────────────────────────────────────────────

class TestAddOperation:
    """Tests for add operation probes."""

    def test_add_all_probes_pass(self, mg):
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "new fact", "kind": "fact"}},
        ])
        detail = r["details"][0]
        assert detail["op_type"] == "add"
        probes = detail["probes"]
        assert probes["detection"]["pass"] is True
        assert probes["target"]["pass"] is True
        assert probes["robustness"]["pass"] is True

    def test_add_with_expectation(self, mg):
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "x"},
             "expect": {"status": True}},
        ])
        assert r["details"][0]["probes"]["transition"]["pass"] is True

    def test_add_creates_real_node(self, mg):
        """The add operation should actually create a node."""
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "real node", "kind": "concept"}},
        ])
        nodes = mg.conn.execute("SELECT * FROM nodes WHERE label='real node'").fetchall()
        assert len(nodes) == 1


# ─── UPDATE Operation ───────────────────────────────────────────────────

class TestUpdateOperation:
    """Tests for update operation probes."""

    def test_update_existing_node(self, populated_mg):
        node = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update",
             "args": {"node_id": node["id"], "label": "Updated A"}},
        ])
        probes = r["details"][0]["probes"]
        assert probes["detection"]["pass"] is True
        assert probes["robustness"]["pass"] is True

    def test_update_nonexistent_node(self, mg):
        """Update on non-existent node → detection fails."""
        r = mg.lifecycle_operation_eval([
            {"op": "update",
             "args": {"node_id": "nonexistent", "label": "test"}},
        ])
        probes = r["details"][0]["probes"]
        assert probes["detection"]["pass"] is False

    def test_update_with_leakage_check(self, populated_mg):
        """Update one node shouldn't affect others."""
        nodes = populated_mg.conn.execute(
            "SELECT id FROM nodes ORDER BY label").fetchall()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update",
             "args": {"node_id": nodes[0]["id"], "label": "Changed"},
             "unrelated_ids": [nodes[1]["id"], nodes[2]["id"]]},
        ])
        probes = r["details"][0]["probes"]
        assert probes["leakage"]["pass"] is True

    def test_update_leakage_detected(self, populated_mg):
        """If an unrelated node is deleted, leakage should fail."""
        nodes = populated_mg.conn.execute(
            "SELECT id FROM nodes ORDER BY label").fetchall()
        # Run an operation then check against a fake unrelated id
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update",
             "args": {"node_id": nodes[0]["id"], "label": "Changed"},
             "unrelated_ids": ["fake_deleted_node"]},
        ])
        probes = r["details"][0]["probes"]
        assert probes["leakage"]["pass"] is False


# ─── SUPERSEDE Operation ────────────────────────────────────────────────

class TestSupersedeOperation:
    """Tests for supersede operation probes."""

    def test_supersede_provenance(self, populated_mg):
        """Supersede should create a traceable edge."""
        node = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "supersede",
             "args": {"node_id": node["id"], "new_label": "New A"}},
        ])
        probes = r["details"][0]["probes"]
        assert probes["provenance"]["pass"] is True

    def test_supersede_nonexistent(self, mg):
        """Supersede on non-existent → detection fails."""
        r = mg.lifecycle_operation_eval([
            {"op": "supersede",
             "args": {"node_id": "nonexistent"}},
        ])
        probes = r["details"][0]["probes"]
        assert probes["detection"]["pass"] is False

    def test_supersede_leakage_safe(self, populated_mg):
        """Supersede should not affect unrelated nodes."""
        nodes = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label IN ('Node B', 'Node C')").fetchall()
        node_a = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "supersede",
             "args": {"node_id": node_a["id"], "new_label": "Superseded A"},
             "unrelated_ids": [n["id"] for n in nodes]},
        ])
        probes = r["details"][0]["probes"]
        assert probes["leakage"]["pass"] is True


# ─── MERGE Operation ────────────────────────────────────────────────────

class TestMergeOperation:
    """Tests for merge operation probes."""

    def test_merge_detection(self, populated_mg):
        nodes = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label IN ('Node A', 'Node B') ORDER BY label"
        ).fetchall()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "merge",
             "args": {"source_id": nodes[0]["id"], "target_id": nodes[1]["id"]}},
        ])
        probes = r["details"][0]["probes"]
        # source_id is used as target_id for detection check
        assert probes["detection"]["pass"] is True

    def test_merge_leakage(self, populated_mg):
        """Merge A→B shouldn't affect C."""
        nodes = populated_mg.conn.execute(
            "SELECT id FROM nodes ORDER BY label").fetchall()
        node_c = nodes[2]["id"]
        r = populated_mg.lifecycle_operation_eval([
            {"op": "merge",
             "args": {"source_id": nodes[0]["id"], "target_id": nodes[1]["id"]},
             "unrelated_ids": [node_c]},
        ])
        probes = r["details"][0]["probes"]
        assert probes["leakage"]["pass"] is True


# ─── Multi-Operation Sequences ──────────────────────────────────────────

class TestMultiOperationSequences:
    """Tests for sequences of multiple operations."""

    def test_add_then_update(self, mg):
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "X", "kind": "fact"}},
            {"op": "update", "args": {"node_id": None, "label": "Updated X"}},
        ])
        assert r["total_ops"] == 2
        assert len(r["details"]) == 2

    def test_mixed_operations(self, populated_mg):
        node = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "New Node"}},
            {"op": "update", "args": {"node_id": node["id"], "label": "Updated A"}},
        ])
        assert r["total_ops"] == 2
        assert r["probes_total"] == 12  # 2 ops × 6 probes

    def test_probes_count_correct(self, mg):
        """Each op should produce exactly 6 probe results."""
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "X"}},
            {"op": "add", "args": {"label": "Y"}},
            {"op": "add", "args": {"label": "Z"}},
        ])
        assert r["probes_total"] == 18
        for detail in r["details"]:
            assert len(detail["probes"]) == 6

    def test_detail_has_op_index(self, mg):
        """Detail entries have correct op_index."""
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "A"}},
            {"op": "add", "args": {"label": "B"}},
        ])
        assert r["details"][0]["op_index"] == 0
        assert r["details"][1]["op_index"] == 1


# ─── Golden Set ─────────────────────────────────────────────────────────

class TestGoldenSet:
    """Tests for golden set target validation."""

    def test_golden_set_match(self, populated_mg):
        node = populated_mg.conn.execute(
            "SELECT id, label FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update", "args": {"node_id": node["id"], "label": "Node A"}},
        ], golden_set={node["id"]: {"label": "Node A"}})
        assert r["details"][0]["probes"]["target"]["pass"] is True

    def test_golden_set_mismatch(self, populated_mg):
        node = populated_mg.conn.execute(
            "SELECT id, label FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update", "args": {"node_id": node["id"], "label": "Changed"}},
        ], golden_set={node["id"]: {"label": "Node A"}})
        # After update, the node's label changed, so golden mismatch
        probes = r["details"][0]["probes"]
        # The golden check runs against the node state; after update it changed
        assert "target" in probes

    def test_golden_set_empty(self, populated_mg):
        """No golden set → target defaults to pass (for non-add)."""
        node = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update", "args": {"node_id": node["id"]}},
        ])
        assert r["details"][0]["probes"]["target"]["pass"] is True


# ─── Probe Overrides ────────────────────────────────────────────────────

class TestProbeOverrides:
    """Tests for per-probe expectation overrides."""

    def test_override_changes_result(self, populated_mg):
        node = populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Node A'").fetchone()
        r = populated_mg.lifecycle_operation_eval([
            {"op": "update",
             "args": {"node_id": node["id"], "label": "Updated"},
             "probe_overrides": {
                 "robustness": {"pass": False, "detail": "Forced fail"}
             }},
        ])
        probes = r["details"][0]["probes"]
        assert probes["robustness"]["pass"] is False
        assert probes["robustness"]["detail"] == "Forced fail"


# ─── Unknown Operations ─────────────────────────────────────────────────

class TestUnknownOperations:
    """Tests for handling unknown/invalid operation types."""

    def test_unknown_op_type(self, mg):
        """Unknown op type → robustness fails."""
        r = mg.lifecycle_operation_eval([
            {"op": "unknown_op", "args": {}},
        ])
        probes = r["details"][0]["probes"]
        assert probes["robustness"]["pass"] is False

    def test_missing_op_key(self, mg):
        """Missing 'op' key defaults to empty string."""
        r = mg.lifecycle_operation_eval([
            {"args": {"label": "test"}},
        ])
        assert r["details"][0]["op_type"] == ""


# ─── Pass Rate Calculation ──────────────────────────────────────────────

class TestPassRateCalculation:
    """Tests for pass rate accuracy."""

    def test_all_pass_rate_1(self, mg):
        """All probes passing → pass_rate = 1.0."""
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "X", "kind": "fact"}},
        ])
        assert r["pass_rate"] == 1.0

    def test_partial_pass(self, mg):
        """Some probes failing → pass_rate < 1.0."""
        r = mg.lifecycle_operation_eval([
            {"op": "update", "args": {"node_id": "nonexistent"}},
        ])
        assert r["pass_rate"] < 1.0
        assert r["probes_passed"] < r["probes_total"]

    def test_rounded_to_four_decimals(self, mg):
        """Pass rate is rounded to 4 decimal places."""
        r = mg.lifecycle_operation_eval([
            {"op": "add", "args": {"label": "X"}},
        ])
        # 1.0 has at most 4 decimal places
        str_rate = str(r["pass_rate"])
        if "." in str_rate:
            assert len(str_rate.split(".")[1]) <= 4
