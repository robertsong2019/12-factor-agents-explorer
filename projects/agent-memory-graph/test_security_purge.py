"""Tests for security_purge() — FSFM Category 3 safety-triggered deletion.

Research #030: FSFM (arXiv:2604.20300) safety-triggered forgetting.
Unlike soft_forget (reversible), security_purge is IRREVERSIBLE.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    g = MemoryGraph(":memory:")
    yield g


@pytest.fixture
def sensitive_graph():
    """Graph with sensitive and normal nodes."""
    g = MemoryGraph(":memory:")
    # Sensitive by kind
    g.add("auth token data", "token")
    g.add("user passwords list", "credential")
    g.add("malware signature", "malicious")

    # Sensitive by label pattern
    g.add("API_KEY=sk-abc123", "fact")
    g.add("ssh-rsa AAAAB3Nza...", "fact")
    g.add("Bearer eyJhbGc...", "fact")

    # Normal nodes
    g.add("Meeting notes", "event")
    g.add("Project plan", "concept")
    g.add("User profile", "person")

    yield g


# ── Basic functionality ────────────────────────────────────────

class TestSecurityPurgeBasic:
    def test_returns_summary_dict(self, mg):
        mg.add("Normal", "fact")
        result = mg.security_purge(dry_run=True)
        assert "purged" in result
        assert "scanned" in result
        assert "details" in result
        assert "dry_run" in result

    def test_empty_graph_returns_zeros(self, mg):
        result = mg.security_purge(dry_run=True)
        assert result["purged"] == 0
        assert result["scanned"] == 0

    def test_dry_run_does_not_delete(self, sensitive_graph):
        before = sensitive_graph.conn.execute(
            "SELECT COUNT(*) as c FROM nodes"
        ).fetchone()["c"]
        sensitive_graph.security_purge(dry_run=True)
        after = sensitive_graph.conn.execute(
            "SELECT COUNT(*) as c FROM nodes"
        ).fetchone()["c"]
        assert before == after


# ── Kind-based detection ───────────────────────────────────────

class TestSecurityPurgeKinds:
    def test_purges_token_kind(self, sensitive_graph):
        result = sensitive_graph.security_purge(
            scan_labels=False, dry_run=True)
        # token, credential, malicious kinds
        assert result["purged"] >= 3

    def test_custom_kinds_added(self, mg):
        mg.add("Custom sensitive", "custom_secret")
        result = mg.security_purge(
            kinds=["custom_secret"], scan_labels=False, dry_run=True)
        assert result["purged"] >= 1

    def test_normal_kinds_not_purged(self, sensitive_graph):
        result = sensitive_graph.security_purge(
            scan_labels=False, dry_run=True)
        labels = [d["label"] for d in result["details"]]
        assert "Meeting notes" not in labels
        assert "Project plan" not in labels


# ── Label pattern detection ────────────────────────────────────

class TestSecurityPurgeLabels:
    def test_detects_api_key_in_label(self, mg):
        mg.add("contains API key for production", "fact")
        result = mg.security_purge(
            scan_labels=True, dry_run=True)
        assert result["purged"] >= 1

    def test_detects_password_in_label(self, mg):
        mg.add("admin password here", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] >= 1

    def test_detects_secret_in_label(self, mg):
        mg.add("client secret value", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] >= 1

    def test_detects_bearer_token(self, mg):
        mg.add("Bearer jwt_token_here", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] >= 1

    def test_detects_ssh_key(self, mg):
        mg.add("ssh key for production", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] >= 1

    def test_case_insensitive_label_match(self, mg):
        mg.add("MY API KEY IS HERE", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] >= 1

    def test_disable_label_scan(self, mg):
        """With scan_labels=False, only kind matches count."""
        mg.add("contains API key text", "fact")  # fact kind, but sensitive label
        result = mg.security_purge(scan_labels=False, dry_run=True)
        assert result["purged"] == 0


# ── Explicit node_ids ──────────────────────────────────────────

class TestSecurityPurgeExplicitIds:
    def test_purge_explicit_ids(self, mg):
        n1 = mg.add("Normal 1", "fact")
        n2 = mg.add("Normal 2", "fact")
        result = mg.security_purge(
            node_ids=[n1.id], scan_labels=False, dry_run=True)
        assert result["purged"] == 1
        assert result["details"][0]["id"] == n1.id

    def test_explicit_ids_plus_kinds(self, mg):
        n1 = mg.add("Explicit target", "fact")
        s1 = mg.add("Token", "token")
        result = mg.security_purge(
            node_ids=[n1.id], scan_labels=False, dry_run=True)
        assert result["purged"] >= 2  # explicit + token kind


# ── Real deletion ──────────────────────────────────────────────

class TestSecurityPurgeReal:
    def test_actually_deletes_nodes(self, sensitive_graph):
        before = sensitive_graph.conn.execute(
            "SELECT COUNT(*) as c FROM nodes"
        ).fetchone()["c"]
        result = sensitive_graph.security_purge(dry_run=False)
        after = sensitive_graph.conn.execute(
            "SELECT COUNT(*) as c FROM nodes"
        ).fetchone()["c"]
        assert after < before
        assert after == before - result["purged"]

    def test_deleted_nodes_gone(self, mg):
        n = mg.add("api_key=abc123", "fact")
        mg.security_purge(dry_run=False)
        exists = mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert exists is None

    def test_edges_removed_with_node(self, mg):
        sensitive = mg.add("api_key=secret", "fact")
        normal = mg.add("Normal node", "concept")
        mg.link(sensitive.id, normal.id, "relates")
        mg.security_purge(dry_run=False)
        # Normal node should still exist
        assert mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (normal.id,)
        ).fetchone() is not None
        # No dangling edges
        edges = mg.conn.execute(
            "SELECT COUNT(*) as c FROM edges WHERE source=? OR target=?",
            (sensitive.id, sensitive.id)
        ).fetchone()
        assert edges["c"] == 0


# ── Details format ─────────────────────────────────────────────

class TestSecurityPurgeDetails:
    def test_details_contain_metadata(self, sensitive_graph):
        result = sensitive_graph.security_purge(dry_run=True)
        for d in result["details"]:
            assert "id" in d
            assert "label" in d
            assert "kind" in d
            assert "weight" in d

    def test_details_capped_at_50(self, mg):
        for i in range(60):
            mg.add(f"api_key_{i}", "fact")
        result = mg.security_purge(dry_run=True)
        assert len(result["details"]) <= 50

    def test_purged_count_uncapped(self, mg):
        for i in range(60):
            mg.add(f"api_key_{i}", "fact")
        result = mg.security_purge(dry_run=True)
        assert result["purged"] == 60
