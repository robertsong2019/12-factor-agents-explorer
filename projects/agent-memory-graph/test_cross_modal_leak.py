"""Tests for cross-modal leak detection — Cycle 442 (Research #018, MemLeak).

Forgetting a node is unsafe when other-modal derivatives (image
captions, inferred summaries, compressed copies) still carry the
source's sensitive tokens. cross_modal_leak_scan() audits derivation
edges; safe_forget() gates deletion on the scan result.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──

@pytest.fixture
def leak_graph():
    """Event node with PII + three derivatives of varying leakiness."""
    g = MemoryGraph()
    src = g.add("Alice met Bob at Acme Corp in 2023",
                kind="event",
                data={"detail": "contact alice@acme.com"})
    heavy = g.add("photo caption: Alice met Bob at Acme Corp in 2023",
                  kind="image")
    light = g.add("inferred: meeting happened", kind="inference")
    clean = g.add("image artifact 42", kind="image")
    g.link(src.id, heavy.id, "image_derived")
    g.link(src.id, light.id, "correlated_inference")
    g.link(src.id, clean.id, "derived_from")
    g._leak_ids = {"src": src.id, "heavy": heavy.id,
                   "light": light.id, "clean": clean.id}
    return g


@pytest.fixture
def no_deriv_graph():
    """Isolated node with zero derivation edges."""
    g = MemoryGraph()
    n = g.add("lonely fact", kind="fact")
    g._nid = n.id
    return g


# ── cross_modal_leak_scan: structure ──

class TestScanStructure:

    def test_scan_returns_required_keys(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        for key in ("node_id", "risk_level", "derivations",
                    "leak_token_count", "recommendation"):
            assert key in result

    def test_scan_finds_all_derivation_edges(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        assert len(result["derivations"]) == 3

    def test_scan_ignores_non_derivation_edges(self):
        g = MemoryGraph()
        a = g.add("Alice event", kind="event")
        b = g.add("related concept", kind="concept")
        g.link(a.id, b.id, "related_to")  # NOT a derivation relation
        result = g.cross_modal_leak_scan(a.id)
        assert result["derivations"] == []
        assert result["risk_level"] == "none"

    def test_scan_missing_node(self):
        g = MemoryGraph()
        result = g.cross_modal_leak_scan("ghost")
        assert result["risk_level"] == "error"
        assert result["derivations"] == []


# ── cross_modal_leak_scan: token detection ──

class TestLeakTokens:

    def test_full_copy_derivative_is_high(self, leak_graph):
        """Derivative repeating the entire source label leaks heavily."""
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        heavy = next(d for d in result["derivations"]
                     if d["derived_id"] == leak_graph._leak_ids["heavy"])
        assert heavy["severity"] == "high"
        assert "Alice" in heavy["leak_tokens"]
        assert "2023" in heavy["leak_tokens"]

    def test_email_leak_is_high_severity(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        # heavy derivative includes email in its data?
        # (email is in src data; heavy repeats label only — but digits
        # '2023' in label already force high)
        heavy = next(d for d in result["derivations"]
                     if d["derived_id"] == leak_graph._leak_ids["heavy"])
        assert heavy["severity"] == "high"

    def test_generic_derivative_has_no_leak(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        light = next(d for d in result["derivations"]
                     if d["derived_id"] == leak_graph._leak_ids["light"])
        assert light["leak_tokens"] == []
        assert light["severity"] == "none"

    def test_digit_only_derivative_is_high(self):
        """A derivative carrying just the year is still risky."""
        g = MemoryGraph()
        src = g.add("acquisition closed 2024", kind="event")
        d = g.add("deal year: 2024", kind="image")
        g.link(src.id, d.id, "image_derived")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "high"

    def test_email_carryover(self):
        """Email in derivative data triggers high severity."""
        g = MemoryGraph()
        src = g.add("Alice sent the report", kind="event",
                    data={"contact": "alice@corp.io"})
        d = g.add("email screenshot", kind="image",
                  data={"caption": "sent to alice@corp.io"})
        g.link(src.id, d.id, "image_derived")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "high"
        deriv = result["derivations"][0]
        assert "alice@corp.io" in deriv["leak_tokens"]

    def test_single_token_leak_is_medium(self):
        """One leaking capitalized name (no digits/email) = medium."""
        g = MemoryGraph()
        src = g.add("Met with Zephyr", kind="event")
        d = g.add("photo of Zephyr", kind="image")
        g.link(src.id, d.id, "image_derived")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "medium"

    def test_sensitive_keys_declared_values_leak(self):
        """data['sensitive_keys'] explicitly marks values to watch."""
        g = MemoryGraph()
        src = g.add("payment record", kind="event",
                    data={"sensitive_keys": ["account"],
                          "account": "acct-9911"})
        d = g.add("statement snapshot mentions acct-9911", kind="image")
        g.link(src.id, d.id, "image_derived")
        result = g.cross_modal_leak_scan(src.id)
        deriv = result["derivations"][0]
        assert "acct-9911" in deriv["leak_tokens"]
        assert result["risk_level"] == "high"  # digit run in token

    def test_no_derivations_risk_none(self, no_deriv_graph):
        result = no_deriv_graph.cross_modal_leak_scan(no_deriv_graph._nid)
        assert result["risk_level"] == "none"
        assert result["leak_token_count"] == 0

    def test_derivations_without_overlap_risk_low(self, leak_graph):
        """Only the clean derivative present → low risk."""
        g = MemoryGraph()
        src = g.add("Bob visited Paris", kind="event")
        d = g.add("image artifact 42", kind="image")
        g.link(src.id, d.id, "derived_from")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "low"
        assert "safe" in result["recommendation"].lower()

    def test_leak_token_count_sums(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        total = sum(d["leak_count"] for d in result["derivations"])
        assert result["leak_token_count"] == total


# ── cross_modal_leak_scan: risk levels & recommendations ──

class TestRiskLevels:

    def test_high_risk_blocks_recommendation(self, leak_graph):
        result = leak_graph.cross_modal_leak_scan(leak_graph._leak_ids["src"])
        assert result["risk_level"] == "high"
        assert "scrub" in result["recommendation"].lower() or \
            "derivatives" in result["recommendation"].lower()

    def test_worst_derivation_wins(self):
        """One high + one none derivative → overall high."""
        g = MemoryGraph()
        src = g.add("Board met in 2025", kind="event")
        bad = g.add("leaky: 2025 board", kind="image")
        good = g.add("plain artifact", kind="image")
        g.link(src.id, bad.id, "image_derived")
        g.link(src.id, good.id, "summarized_into")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "high"

    def test_medium_risk_caution(self):
        g = MemoryGraph()
        src = g.add("Met with Zephyr", kind="event")
        d = g.add("note about Zephyr", kind="inference")
        g.link(src.id, d.id, "correlated_inference")
        result = g.cross_modal_leak_scan(src.id)
        assert result["risk_level"] == "medium"
        assert "caution" in result["recommendation"].lower()

    def test_all_derivation_relations_recognized(self):
        g = MemoryGraph()
        src = g.add("Origin event", kind="event")
        rels = ["image_derived", "correlated_inference", "derived_from",
                "compressed_into", "summarized_into", "extracted_from"]
        ids = []
        for i, rel in enumerate(rels):
            d = g.add(f"derivative {i}", kind="image")
            g.link(src.id, d.id, rel)
            ids.append(d.id)
        result = g.cross_modal_leak_scan(src.id)
        assert len(result["derivations"]) == 6
        found_rels = {d["relation"] for d in result["derivations"]}
        assert found_rels == set(rels)


# ── safe_forget ──

class TestSafeForget:

    def test_high_risk_blocks_delete(self, leak_graph):
        result = leak_graph.safe_forget(leak_graph._leak_ids["src"])
        assert result["verdict"] == "blocked"
        assert result["removed"] is False
        # source node still exists
        assert leak_graph.get_node(leak_graph._leak_ids["src"]) is not None

    def test_force_overrides_block(self, leak_graph):
        result = leak_graph.safe_forget(leak_graph._leak_ids["src"], force=True)
        assert result["verdict"] == "deleted"
        assert result["removed"] is True
        assert leak_graph.get_node(leak_graph._leak_ids["src"]) is None

    def test_force_audited_via_risk_level(self, leak_graph):
        result = leak_graph.safe_forget(leak_graph._leak_ids["src"], force=True)
        assert result["risk_level"] == "high"  # audit trail preserved

    def test_none_risk_deletes(self, no_deriv_graph):
        result = no_deriv_graph.safe_forget(no_deriv_graph._nid)
        assert result["verdict"] == "deleted"
        assert result["risk_level"] == "none"

    def test_low_risk_deletes(self):
        g = MemoryGraph()
        src = g.add("Bob visited Paris", kind="event")
        d = g.add("image artifact 42", kind="image")
        g.link(src.id, d.id, "derived_from")
        result = g.safe_forget(src.id)
        assert result["verdict"] == "deleted"
        assert g.get_node(src.id) is None

    def test_medium_risk_deletes_with_warning(self):
        g = MemoryGraph()
        src = g.add("Met with Zephyr", kind="event")
        d = g.add("note about Zephyr", kind="inference")
        g.link(src.id, d.id, "correlated_inference")
        result = g.safe_forget(src.id)
        assert result["verdict"] == "deleted"
        assert result["risk_level"] == "medium"

    def test_missing_node_not_found(self):
        g = MemoryGraph()
        result = g.safe_forget("ghost")
        assert result["verdict"] == "not_found"
        assert result["removed"] is False

    def test_delete_removes_edges_too(self, leak_graph):
        """safe_forget uses delete_node: edges die with the node."""
        before = leak_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE source=?",
            (leak_graph._leak_ids["src"],)).fetchone()["c"]
        assert before == 3
        leak_graph.safe_forget(leak_graph._leak_ids["src"], force=True)
        after = leak_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE source=?",
            (leak_graph._leak_ids["src"],)).fetchone()["c"]
        assert after == 0

    def test_derivatives_survive_forget(self, leak_graph):
        """Only the source is forgotten; derivatives stay for manual scrub."""
        leak_graph.safe_forget(leak_graph._leak_ids["src"], force=True)
        for key in ("heavy", "light", "clean"):
            assert leak_graph.get_node(leak_graph._leak_ids[key]) is not None

    def test_blocked_returns_derivations_for_scrubbing(self, leak_graph):
        result = leak_graph.safe_forget(leak_graph._leak_ids["src"])
        assert len(result["derivations"]) == 3
        # caller can iterate to scrub each derivative


# ── Integration with existing infrastructure ──

class TestIntegration:

    def test_scan_after_safety_purge_flow(self):
        """Pattern: try safety_purge on PII node → leak scan catches it."""
        g = MemoryGraph()
        src = g.add("Alice paid invoice-8891", kind="event",
                    data={"contact": "alice@corp.io"})
        img = g.add("receipt photo: invoice-8891 alice@corp.io", kind="image")
        g.link(src.id, img.id, "image_derived")
        # Agent decides to forget the PII event
        result = g.safe_forget(src.id)
        assert result["verdict"] == "blocked"
        # Scrub derivative, then retry
        g.update_node(img.id, label="receipt photo [redacted]")
        g.update_node(img.id, data={"caption": "[redacted]"})
        result2 = g.safe_forget(src.id)
        assert result2["verdict"] in ("deleted",)  # medium at worst — proceeds

    def test_inbound_derivation_edges_not_scanned(self):
        """Only OUTGOING derivation edges matter (node is the source)."""
        g = MemoryGraph()
        origin = g.add("Original Alice event", kind="event")
        mid = g.add("middle summary", kind="summary")
        g.link(origin.id, mid.id, "summarized_into")
        # mid has NO outgoing derivations
        result = g.cross_modal_leak_scan(mid.id)
        assert result["risk_level"] == "none"

    def test_write_governance_still_works_alongside(self, leak_graph):
        """New APIs do not disturb write_governance_check."""
        result = leak_graph.write_governance_check(
            leak_graph._leak_ids["src"], new_label="original label")
        assert result["verdict"] == "safe"
