"""Tests for trace_decision_chain() — Cycle 227.

TokenMizer-inspired decision chain tracking: for each supersession hop,
report trigger, reason, evidence, and timestamp.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


class TestTraceDecisionChain:
    """trace_decision_chain: traverse supersede chain with trigger/reason/evidence."""

    def test_empty_graph(self, mg):
        assert mg.trace_decision_chain(topic="anything") == []

    def test_no_match(self, mg):
        mg.add("A", "fact")
        assert mg.trace_decision_chain(topic="nonexistent") == []

    def test_single_node_no_chain(self, mg):
        """A single node with no supersessions has no decision chain."""
        mg.add("Python is great", "fact")
        result = mg.trace_decision_chain(topic="Python")
        assert result == []

    def test_simple_supersession(self, mg):
        """One supersede: A → B. Should produce 1 hop."""
        a = mg.add("v1: answer is 42", "fact")
        b_id = mg.supersede(a.id, "v2: answer is 43")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 1
        hop = result[0]
        assert hop["from_label"] == "v1: answer is 42"
        assert hop["to_label"] == "v2: answer is 43"
        assert hop["trigger"] == "supersede"
        assert hop["from_node"] == a.id
        assert hop["to_node"] == b_id

    def test_three_hop_chain(self, mg):
        """A → B → C. Should produce 2 hops."""
        a = mg.add("v1", "fact")
        b_id = mg.supersede(a.id, "v2")
        c_id = mg.supersede(b_id, "v3")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 2
        assert result[0]["from_label"] == "v1"
        assert result[0]["to_label"] == "v2"
        assert result[1]["from_label"] == "v2"
        assert result[1]["to_label"] == "v3"

    def test_trace_by_topic(self, mg):
        """Trace by topic substring should find the oldest matching node."""
        a = mg.add("project status: planning phase", "fact")
        b_id = mg.supersede(a.id, "project status: development phase")
        result = mg.trace_decision_chain(topic="project status")
        assert len(result) == 1
        assert result[0]["from_label"] == "project status: planning phase"
        assert result[0]["to_label"] == "project status: development phase"

    def test_trace_by_topic_finds_oldest(self, mg):
        """When multiple nodes match topic, start from oldest."""
        a = mg.add("config: version 1", "fact")
        b_id = mg.supersede(a.id, "config: version 2")
        mg.add("config: unrelated entry", "fact")
        result = mg.trace_decision_chain(topic="config")
        # Should trace the chain with supersessions, not the unrelated node
        assert len(result) == 1
        assert result[0]["from_label"] == "config: version 1"

    def test_evidence_collected(self, mg):
        """Evidence edges pointing to the new node should be collected."""
        a = mg.add("claim A", "fact")
        b_id = mg.supersede(a.id, "claim B")
        # Add evidence supporting B
        ev = mg.add("supporting data", "evidence")
        mg.link(ev.id, b_id, "evidence")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 1
        assert ev.id in result[0]["evidence"]

    def test_no_evidence_empty_list(self, mg):
        """Without evidence edges, evidence list is empty."""
        a = mg.add("v1", "fact")
        mg.supersede(a.id, "v2")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 1
        assert result[0]["evidence"] == []

    def test_timestamp_recorded(self, mg):
        """Each hop should have a timestamp (valid_to of from_node)."""
        a = mg.add("v1", "fact")
        mg.supersede(a.id, "v2")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 1
        assert result[0]["timestamp"] is not None

    def test_middle_of_chain(self, mg):
        """Tracing from the middle node should include full history
        (get_history walks backward to find the oldest ancestor)."""
        a = mg.add("v1", "fact")
        b_id = mg.supersede(a.id, "v2")
        c_id = mg.supersede(b_id, "v3")
        # Trace from middle
        result = mg.trace_decision_chain(node_id=b_id)
        # get_history traces both directions, so we get the full chain
        assert len(result) == 2

    def test_no_topic_no_node(self, mg):
        """Both topic and node_id None → empty list."""
        mg.add("something", "fact")
        assert mg.trace_decision_chain() == []

    def test_nonexistent_node_id(self, mg):
        """Non-existent node_id → empty list."""
        mg.add("A", "fact")
        assert mg.trace_decision_chain(node_id="nonexistent_id") == []

    def test_both_topic_and_node_id(self, mg):
        """node_id takes precedence over topic."""
        a = mg.add("topic A", "fact")
        b_id = mg.supersede(a.id, "topic B")
        # If both given, node_id should be used
        result = mg.trace_decision_chain(topic="nothing_matches", node_id=a.id)
        assert len(result) == 1

    def test_chain_with_isolated_supersede(self, mg):
        """Supersede creates proper chain even with other unrelated nodes."""
        a = mg.add("main fact", "fact")
        b_id = mg.supersede(a.id, "updated fact")
        # Add unrelated node
        mg.add("unrelated", "note")
        result = mg.trace_decision_chain(topic="main fact")
        assert len(result) == 1
        assert result[0]["to_node"] == b_id

    def test_supports_relation_as_evidence(self, mg):
        """'supports' relation should also count as evidence."""
        a = mg.add("hypothesis v1", "fact")
        b_id = mg.supersede(a.id, "hypothesis v2")
        sup = mg.add("supporting proof", "evidence")
        mg.link(sup.id, b_id, "supports")
        result = mg.trace_decision_chain(node_id=a.id)
        assert sup.id in result[0]["evidence"]

    def test_proves_relation_as_evidence(self, mg):
        """'proves' relation should also count as evidence."""
        a = mg.add("theorem v1", "fact")
        b_id = mg.supersede(a.id, "theorem v2")
        proof = mg.add("QED proof", "evidence")
        mg.link(proof.id, b_id, "proves")
        result = mg.trace_decision_chain(node_id=a.id)
        assert proof.id in result[0]["evidence"]

    def test_long_chain_five_hops(self, mg):
        """A → B → C → D → E. Should produce 4 hops."""
        a = mg.add("v1", "fact")
        b = mg.supersede(a.id, "v2")
        c = mg.supersede(b, "v3")
        d = mg.supersede(c, "v4")
        e = mg.supersede(d, "v5")
        result = mg.trace_decision_chain(node_id=a.id)
        assert len(result) == 4
        labels = [h["from_label"] for h in result]
        assert labels == ["v1", "v2", "v3", "v4"]

    def test_trigger_is_supersede_for_normal_chain(self, mg):
        """Normal supersession should have trigger='supersede'."""
        a = mg.add("old", "fact")
        mg.supersede(a.id, "new")
        result = mg.trace_decision_chain(node_id=a.id)
        assert result[0]["trigger"] == "supersede"

    def test_reason_empty_without_conflict_log(self, mg):
        """Without conflict log, reason should be empty string."""
        a = mg.add("old", "fact")
        mg.supersede(a.id, "new")
        result = mg.trace_decision_chain(node_id=a.id)
        assert result[0]["reason"] == ""

    def test_topic_case_insensitive(self, mg):
        """Topic search should be case-insensitive."""
        a = mg.add("Important Fact", "fact")
        mg.supersede(a.id, "Important Fact Updated")
        result = mg.trace_decision_chain(topic="important fact")
        assert len(result) == 1
