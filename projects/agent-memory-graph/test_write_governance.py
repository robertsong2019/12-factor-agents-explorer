"""Tests for write_governance_check — PASB-inspired commit boundary protection.

PASB (arXiv:2607.10526) identifies three sycophantic failure modes
when agents persist memory across session boundaries:
  1. Status promotion — hedged → definitive
  2. Attribution removal — source qualifiers stripped
  3. Scope broadening — specific → universal

These tests verify detection of each pattern, safe writes, the
safe_supersede wrapper, and the governance_audit trail.
"""

import pytest
from memory_graph import MemoryGraph


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


# ─── Status Promotion Detection ────────────────────────────────────────

class TestStatusPromotion:
    """Tests for _detect_status_promotion and status_promotion checks."""

    def test_hedge_removed_detected(self, mg):
        """Removing 'maybe' should trigger status promotion."""
        r = mg._detect_status_promotion(
            "user maybe likes Italian food", "user likes Italian food"
        )
        assert r["triggered"] is True
        assert r["score"] >= 0.3
        assert "maybe" in r["old_hedges"]

    def test_certainty_added_detected(self, mg):
        """Adding 'definitely' should trigger."""
        r = mg._detect_status_promotion(
            "user likes Italian food", "user definitely likes Italian food"
        )
        assert r["triggered"] is True
        assert "definitely" in r["new_certainty"]

    def test_both_hedge_removed_and_certainty_added(self, mg):
        """Double signal: remove hedge + add certainty."""
        r = mg._detect_status_promotion(
            "user might like Italian", "user definitely likes Italian"
        )
        assert r["triggered"] is True
        assert r["score"] >= 0.7

    def test_no_change_safe(self, mg):
        """Identical labels → no promotion."""
        r = mg._detect_status_promotion(
            "user likes Italian food", "user likes Italian food"
        )
        assert r["triggered"] is False

    def test_hedge_added_reverse_safe(self, mg):
        """Adding a hedge (reverse) → safe."""
        r = mg._detect_status_promotion(
            "user likes Italian food", "user maybe likes Italian food"
        )
        assert r["triggered"] is False

    def test_multiple_hedges_removed(self, mg):
        """Multiple hedges removed → higher score."""
        r = mg._detect_status_promotion(
            "user perhaps possibly likes Italian", "user likes Italian"
        )
        assert r["triggered"] is True
        assert r["score"] >= 0.5

    def test_hedge_to_hedge_safe(self, mg):
        """Replacing one hedge with another → safe."""
        r = mg._detect_status_promotion(
            "user maybe likes Italian", "user perhaps likes Italian"
        )
        assert r["triggered"] is False

    def test_empty_labels(self, mg):
        """Empty strings → safe."""
        r = mg._detect_status_promotion("", "")
        assert r["triggered"] is False
        assert r["score"] == 0.0

    def test_score_capped_at_1(self, mg):
        """Extreme case → score capped at 1.0."""
        r = mg._detect_status_promotion(
            "maybe perhaps possibly supposedly allegedly user likes Italian",
            "user is definitely absolutely certainly undoubtedly confirmed likes Italian"
        )
        assert r["score"] <= 1.0

    def test_certainty_replaced_not_added(self, mg):
        """If old already has certainty word → not triggered by new."""
        r = mg._detect_status_promotion(
            "user confirmed likes Italian", "user verified likes Italian"
        )
        assert r["triggered"] is False


# ─── Attribution Removal Detection ─────────────────────────────────────

class TestAttributionRemoval:
    """Tests for _detect_attribution_removal."""

    def test_source_removed(self, mg):
        """Removing 'source' key → triggered."""
        r = mg._detect_attribution_removal(
            {"source": "survey", "value": 42}, {"value": 42}
        )
        assert r["triggered"] is True
        assert "source" in r["removed_keys"]

    def test_cited_from_removed(self, mg):
        """Removing 'cited_from' → triggered."""
        r = mg._detect_attribution_removal(
            {"cited_from": "paper_X"}, {}
        )
        assert r["triggered"] is True
        assert "cited_from" in r["removed_keys"]

    def test_multiple_attribution_keys_removed(self, mg):
        """Multiple source keys removed → higher score."""
        r = mg._detect_attribution_removal(
            {"source": "A", "evidence": "B", "reference": "C", "value": 1},
            {"value": 1},
        )
        assert r["triggered"] is True
        assert r["score"] >= 0.6

    def test_no_attribution_change(self, mg):
        """No attribution keys changed → safe."""
        r = mg._detect_attribution_removal(
            {"source": "A", "value": 1}, {"source": "A", "value": 2}
        )
        assert r["triggered"] is False

    def test_confidence_level_inflated(self, mg):
        """confidence_level going up → triggered."""
        r = mg._detect_attribution_removal(
            {"confidence_level": 0.5}, {"confidence_level": 0.95}
        )
        assert r["triggered"] is True
        assert r["confidence_dropped"] is True

    def test_confidence_level_removed(self, mg):
        """confidence_level key removed → triggered."""
        r = mg._detect_attribution_removal(
            {"confidence_level": 0.7, "value": 1}, {"value": 1}
        )
        assert r["triggered"] is True

    def test_confidence_level_lowered_safe(self, mg):
        """confidence_level going down → safe (more conservative)."""
        r = mg._detect_attribution_removal(
            {"confidence_level": 0.9}, {"confidence_level": 0.5}
        )
        assert r["triggered"] is False

    def test_empty_data_both(self, mg):
        """Both empty → safe."""
        r = mg._detect_attribution_removal({}, {})
        assert r["triggered"] is False

    def test_none_data_handled(self, mg):
        """None inputs → safe."""
        r = mg._detect_attribution_removal(None, None)
        assert r["triggered"] is False

    def test_evidence_key_removed(self, mg):
        """Removing 'evidence' → triggered."""
        r = mg._detect_attribution_removal(
            {"evidence": "log_entry_42", "val": True}, {"val": True}
        )
        assert r["triggered"] is True

    def test_provenance_removed(self, mg):
        """Removing 'provenance' → triggered."""
        r = mg._detect_attribution_removal(
            {"provenance": "agent_A", "data": "x"}, {"data": "x"}
        )
        assert r["triggered"] is True

    def test_non_attribution_key_removed_safe(self, mg):
        """Removing a non-attribution key → safe."""
        r = mg._detect_attribution_removal(
            {"color": "red"}, {"color": "blue"}
        )
        assert r["triggered"] is False

    def test_score_capped(self, mg):
        """Many attribution keys removed → capped at 1.0."""
        old = {k: "val" for k in ["source", "evidence", "reference",
                                   "citation", "provenance", "reported_by",
                                   "verified_by", "attributed_to"]}
        r = mg._detect_attribution_removal(old, {})
        assert r["score"] <= 1.0


# ─── Scope Broadening Detection ────────────────────────────────────────

class TestScopeBroadening:
    """Tests for _detect_scope_broadening."""

    def test_all_added(self, mg):
        """Adding 'all' → triggered."""
        r = mg._detect_scope_broadening(
            "user likes restaurant A", "user likes all restaurants"
        )
        assert r["triggered"] is True
        assert "all" in r["added_broadeners"]

    def test_every_added(self, mg):
        """Adding 'every' → triggered."""
        r = mg._detect_scope_broadening(
            "user likes restaurant A", "user likes every restaurant"
        )
        assert r["triggered"] is True

    def test_always_added(self, mg):
        """Adding 'always' → triggered."""
        r = mg._detect_scope_broadening(
            "user sometimes eats Italian", "user always eats Italian"
        )
        assert r["triggered"] is True

    def test_no_broadener_safe(self, mg):
        """No broadener added → safe."""
        r = mg._detect_scope_broadening(
            "user likes Italian", "user likes Italian and French"
        )
        assert r["triggered"] is False

    def test_broadener_removed_reverse_safe(self, mg):
        """Removing a broadener → safe."""
        r = mg._detect_scope_broadening(
            "user likes all restaurants", "user likes restaurant A"
        )
        assert r["triggered"] is False

    def test_specific_to_broad_with_quantifier(self, mg):
        """Specific → universal with quantifier → higher score."""
        r = mg._detect_scope_broadening(
            "user likes restaurant A on 5th Ave",
            "user likes all types of restaurants everywhere"
        )
        assert r["triggered"] is True
        assert r["score"] >= 0.5

    def test_never_added(self, mg):
        """Adding 'never' → triggered."""
        r = mg._detect_scope_broadening(
            "user does not like restaurant A", "user never likes any restaurant"
        )
        assert r["triggered"] is True

    def test_empty_labels(self, mg):
        """Empty → safe."""
        r = mg._detect_scope_broadening("", "")
        assert r["triggered"] is False

    def test_only_added_without_removal(self, mg):
        """Adding 'only' without removing specifics → triggered."""
        r = mg._detect_scope_broadening(
            "user likes Italian", "user only likes Italian"
        )
        assert r["triggered"] is True

    def test_score_capped(self, mg):
        """Multiple broadeners → capped."""
        r = mg._detect_scope_broadening(
            "user likes A",
            "user universally likes all every always everything"
        )
        assert r["score"] <= 1.0


# ─── write_governance_check Integration ────────────────────────────────

class TestWriteGovernanceCheck:
    """Integration tests for write_governance_check on real nodes."""

    def test_safe_write(self, mg):
        """Benign update → safe."""
        n = mg.add("user likes Italian food", "fact")
        r = mg.write_governance_check(n.id, new_label="user likes Italian food and pizza")
        assert r["verdict"] == "safe"
        assert r["overall_score"] < 0.3

    def test_status_promotion_flagged(self, mg):
        """Hedge removal → flagged."""
        n = mg.add("user maybe likes hiking", "fact")
        r = mg.write_governance_check(n.id, new_label="user likes hiking")
        assert r["verdict"] in ("flag", "reject")
        assert any(c["type"] == "status_promotion" and c["triggered"]
                    for c in r["checks"])

    def test_attribution_removal_flagged(self, mg):
        """Source key removed → flagged."""
        n = mg.add("user preference", "fact",
                    data={"source": "survey", "preference": "Italian"})
        r = mg.write_governance_check(n.id,
                                      new_data={"preference": "Italian"})
        assert r["verdict"] in ("flag", "reject")
        assert any(c["type"] == "attribution_removal" and c["triggered"]
                    for c in r["checks"])

    def test_scope_broadening_flagged(self, mg):
        """Universal quantifier added → flagged."""
        n = mg.add("user likes restaurant A", "fact")
        r = mg.write_governance_check(n.id,
                                      new_label="user likes all restaurants")
        assert r["verdict"] in ("flag", "reject")
        assert any(c["type"] == "scope_broadening" and c["triggered"]
                    for c in r["checks"])

    def test_reject_verdict_high_score(self, mg):
        """Multiple patterns → reject."""
        n = mg.add("user maybe likes restaurant A",
                    "fact",
                    data={"source": "survey", "evidence": "E1"})
        r = mg.write_governance_check(
            n.id,
            new_label="user definitely likes all restaurants",
            new_data={},
        )
        assert r["verdict"] == "reject"
        assert r["overall_score"] >= 0.6

    def test_node_not_found(self, mg):
        """Non-existent node → error."""
        r = mg.write_governance_check("nonexistent")
        assert r["verdict"] == "error"

    def test_no_changes_safe(self, mg):
        """No changes → safe."""
        n = mg.add("user likes Italian", "fact")
        r = mg.write_governance_check(n.id)
        assert r["verdict"] == "safe"

    def test_only_label_change(self, mg):
        """Only label provided, data unchanged."""
        n = mg.add("user might like Italian", "fact",
                    data={"source": "survey"})
        r = mg.write_governance_check(n.id,
                                      new_label="user likes Italian")
        # Status promotion detected, but attribution untouched
        types_triggered = {c["type"] for c in r["checks"] if c["triggered"]}
        assert "status_promotion" in types_triggered
        assert "attribution_removal" not in types_triggered

    def test_only_data_change(self, mg):
        """Only data provided, label unchanged."""
        n = mg.add("user preference", "fact",
                    data={"source": "survey", "value": 1})
        r = mg.write_governance_check(n.id,
                                      new_data={"value": 1})
        assert any(c["type"] == "attribution_removal" and c["triggered"]
                    for c in r["checks"])

    def test_recommendation_text_safe(self, mg):
        """Safe verdict has helpful recommendation."""
        n = mg.add("user likes Italian", "fact")
        r = mg.write_governance_check(n.id, new_label="user likes Italian food")
        assert "safe" in r["recommendation"].lower()

    def test_recommendation_text_reject(self, mg):
        """Reject verdict has warning text."""
        n = mg.add("user maybe likes A", "fact",
                    data={"source": "S", "evidence": "E"})
        r = mg.write_governance_check(
            n.id,
            new_label="user definitely likes all everything",
            new_data={},
        )
        assert r["verdict"] == "reject"
        assert "rejected" in r["recommendation"].lower()

    def test_checks_always_three(self, mg):
        """Always returns exactly 3 checks."""
        n = mg.add("test", "fact")
        r = mg.write_governance_check(n.id, new_label="test updated")
        assert len(r["checks"]) == 3

    def test_overall_score_is_max(self, mg):
        """Overall score should be the max of individual scores."""
        n = mg.add("user maybe likes A", "fact")
        r = mg.write_governance_check(n.id, new_label="user likes A")
        scores = [c["score"] for c in r["checks"]]
        assert r["overall_score"] == max(scores)


# ─── safe_supersede ───────────────────────────────────────────────────

class TestSafeSupersede:
    """Tests for safe_supersede wrapper."""

    def test_safe_supersede_proceeds(self, mg):
        """Safe write → supersede happens."""
        n = mg.add("user likes Italian", "fact")
        r = mg.safe_supersede(n.id, new_label="user likes Italian food")
        assert r["new_id"] is not None
        assert r["governance"]["verdict"] == "safe"

    def test_rejected_supersede_blocked(self, mg):
        """Reject verdict → supersede blocked."""
        n = mg.add("user maybe likes A", "fact",
                    data={"source": "S", "evidence": "E"})
        r = mg.safe_supersede(
            n.id,
            new_label="user definitely likes all everything",
            new_data={},
        )
        assert r["new_id"] is None
        assert r["governance"]["verdict"] == "reject"

    def test_flagged_supersede_proceeds(self, mg):
        """Flag verdict → supersede proceeds (with warning)."""
        n = mg.add("user maybe likes hiking", "fact")
        r = mg.safe_supersede(n.id, new_label="user likes hiking")
        assert r["new_id"] is not None
        assert r["governance"]["verdict"] == "flag"

    def test_flagged_with_certainty(self, mg):
        """Hedge removed + certainty added → stronger signal."""
        n = mg.add("user might like hiking", "fact")
        r = mg.safe_supersede(n.id, new_label="user definitely likes hiking")
        # Two signals (hedge removed + certainty added) → reject
        assert r["governance"]["verdict"] == "reject"

    def test_new_node_created_on_safe(self, mg):
        """Verify the new node actually exists after safe_supersede."""
        n = mg.add("user likes Italian", "fact")
        r = mg.safe_supersede(n.id, new_label="user likes Italian and French")
        assert r["new_id"] is not None
        new_node = mg.get_node(r["new_id"])
        assert new_node is not None
        assert "French" in new_node.label

    def test_old_node_valid_to_set(self, mg):
        """Old node's valid_to should be set after safe_supersede."""
        n = mg.add("user likes Italian", "fact")
        r = mg.safe_supersede(n.id, new_label="user likes Italian and French")
        row = mg.conn.execute(
            "SELECT valid_to FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row["valid_to"] is not None

    def test_superseded_by_edge_exists(self, mg):
        """superseded_by edge should exist after safe_supersede."""
        n = mg.add("user likes Italian", "fact")
        r = mg.safe_supersede(n.id, new_label="user likes Italian food")
        row = mg.conn.execute(
            "SELECT COUNT(*) as cnt FROM edges "
            "WHERE source=? AND target=? AND relation='superseded_by'",
            (n.id, r["new_id"])
        ).fetchone()
        assert row["cnt"] >= 1

    def test_nonexistent_node(self, mg):
        """Non-existent node → governance error, new_id None."""
        r = mg.safe_supersede("nonexistent", new_label="test")
        assert r["new_id"] is None
        assert r["governance"]["verdict"] == "error"


# ─── governance_audit ─────────────────────────────────────────────────

class TestGovernanceAudit:
    """Tests for governance_audit trail."""

    def test_audit_empty_graph(self, mg):
        """No supersede chains → empty audit."""
        r = mg.governance_audit()
        assert r["total_chains"] == 0
        assert r["audited"] == 0

    def test_audit_single_safe_chain(self, mg):
        """One safe supersede → audited as safe."""
        n = mg.add("user likes Italian", "fact")
        mg.safe_supersede(n.id, new_label="user likes Italian and pizza")
        r = mg.governance_audit()
        assert r["audited"] >= 1
        assert r["safe"] >= 1
        assert r["rejected"] == 0

    def test_audit_finds_flagged_chain(self, mg):
        """Flagged supersede → shows in audit."""
        n = mg.add("user maybe likes hiking", "fact")
        mg.safe_supersede(n.id, new_label="user likes hiking")
        r = mg.governance_audit()
        assert r["flagged"] >= 1

    def test_audit_specific_node(self, mg):
        """Audit a specific node chain."""
        n1 = mg.add("user likes A", "fact")
        n2 = mg.add("user maybe likes B", "fact")
        mg.safe_supersede(n1.id, new_label="user likes A and B")
        mg.safe_supersede(n2.id, new_label="user likes B")
        r = mg.governance_audit(node_id=n2.id)
        assert r["total_chains"] == 1
        assert r["audited"] == 1

    def test_audit_detail_fields(self, mg):
        """Detail entries have required fields."""
        n = mg.add("user likes Italian", "fact")
        mg.safe_supersede(n.id, new_label="user likes Italian food")
        r = mg.governance_audit()
        if r["details"]:
            d = r["details"][0]
            assert "old_id" in d
            assert "new_id" in d
            assert "verdict" in d
            assert "score" in d

    def test_audit_limit_respected(self, mg):
        """Limit parameter caps number of chains."""
        for i in range(5):
            n = mg.add(f"fact_{i}", "fact")
            mg.safe_supersede(n.id, new_label=f"fact_{i}_updated")
        r = mg.governance_audit(limit=3)
        assert r["total_chains"] <= 3

    def test_audit_counts_consistent(self, mg):
        """safe + flagged + rejected == audited."""
        n1 = mg.add("user likes A", "fact")
        n2 = mg.add("user maybe likes B", "fact")
        mg.safe_supersede(n1.id, new_label="user likes A and B")
        mg.safe_supersede(n2.id, new_label="user likes B")
        r = mg.governance_audit()
        assert r["safe"] + r["flagged"] + r["rejected"] == r["audited"]


# ─── Edge Cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_none_new_label_uses_old(self, mg):
        """None new_label → compares old to old → safe."""
        n = mg.add("user likes Italian", "fact")
        r = mg.write_governance_check(n.id, new_label=None)
        assert r["verdict"] == "safe"

    def test_none_new_data_uses_old(self, mg):
        """None new_data → compares old to old → safe."""
        n = mg.add("test", data={"source": "A"})
        r = mg.write_governance_check(n.id, new_data=None)
        assert r["verdict"] == "safe"

    def test_unicode_labels(self, mg):
        """Unicode labels handled correctly."""
        n = mg.add("用户可能喜欢意大利菜", "fact")
        r = mg.write_governance_check(n.id, new_label="用户喜欢意大利菜")
        assert r["verdict"] == "safe"  # Chinese text doesn't trigger English heuristics

    def test_special_characters(self, mg):
        """Labels with special characters."""
        n = mg.add("user likes Italian food", "fact")
        r = mg.write_governance_check(n.id,
                                      new_label="user likes Italian food!!!")
        assert r["verdict"] == "safe"

    def test_very_long_label(self, mg):
        """Very long labels don't crash."""
        old_label = "user " + " ".join(["maybe"] * 50) + " likes X"
        new_label = "user likes X"
        n = mg.add(old_label, "fact")
        r = mg.write_governance_check(n.id, new_label=new_label)
        assert r["verdict"] in ("flag", "reject")

    def test_tokenize_gov(self, mg):
        """Tokenizer produces clean lowercase tokens."""
        tokens = mg._tokenize_gov("Hello WORLD it's Me")
        assert "hello" in tokens
        assert "world" in tokens
        assert "it's" in tokens
        assert "me" in tokens

    def test_tokenize_empty(self, mg):
        """Empty string → empty tokens."""
        assert mg._tokenize_gov("") == []

    def test_governance_with_kind_change(self, mg):
        """Kind change alone → safe (governance checks content only)."""
        n = mg.add("user likes Italian", "fact")
        r = mg.write_governance_check(n.id, new_label="user likes Italian")
        assert r["verdict"] == "safe"

    def test_repeated_calls_idempotent(self, mg):
        """Multiple governance checks on same content → same result."""
        n = mg.add("user maybe likes X", "fact",
                    data={"source": "S"})
        r1 = mg.write_governance_check(n.id, new_label="user likes X")
        r2 = mg.write_governance_check(n.id, new_label="user likes X")
        assert r1["verdict"] == r2["verdict"]
        assert r1["overall_score"] == r2["overall_score"]
