"""Tests for temporal_score() — Cycle 234.

RoMem-inspired continuous temporal relevance scoring.
Models temporal relevance as a continuous score in [0, 1] instead
of the binary stale/fresh dichotomy of staleness_score().
"""

import time
import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg_with_nodes():
    """Graph with nodes of varying ages."""
    mg = MemoryGraph()
    # Fresh node
    mg.add("Fresh topic", "topic", {"tags": ["new"]})
    # Old node (manually age it)
    mg.add("Old topic", "topic", {"tags": ["legacy"]})
    old_id = mg.recall("Old", limit=1)[0].id
    # Backdate creation and access by 60 days
    sixty_days_ago = time.time() - 60 * 86400
    mg.conn.execute(
        "UPDATE nodes SET created=?, accessed=? WHERE id=?",
        (sixty_days_ago, sixty_days_ago, old_id)
    )
    mg.conn.commit()
    return mg


class TestTemporalScoreBasics:
    """Basic structure and return value tests."""

    def test_returns_dict_with_score(self, mg_with_nodes):
        nodes = mg_with_nodes.recall("topic", limit=10)
        result = mg_with_nodes.temporal_score(nodes[0].id)
        assert "temporal_score" in result
        assert isinstance(result["temporal_score"], float)

    def test_score_in_range(self, mg_with_nodes):
        nodes = mg_with_nodes.recall("topic", limit=10)
        for n in nodes:
            result = mg_with_nodes.temporal_score(n.id)
            assert 0.0 <= result["temporal_score"] <= 1.0

    def test_nonexistent_node(self, mg_with_nodes):
        result = mg_with_nodes.temporal_score("nonexistent_id")
        assert result["temporal_score"] == 0.0
        assert result.get("not_found") is True

    def test_returns_components(self, mg_with_nodes):
        nodes = mg_with_nodes.recall("Fresh", limit=1)
        result = mg_with_nodes.temporal_score(nodes[0].id)
        assert "age_component" in result
        assert "access_component" in result
        assert "validity_component" in result
        assert "alpha" in result
        assert "age_days" in result


class TestFreshVsOld:
    """Fresh nodes should score higher than old nodes."""

    def test_fresh_higher_than_old(self, mg_with_nodes):
        fresh = mg_with_nodes.recall("Fresh", limit=1)[0]
        old_id = mg_with_nodes.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE '%Old%'"
        ).fetchone()["id"]

        fresh_score = mg_with_nodes.temporal_score(fresh.id)["temporal_score"]
        old_score = mg_with_nodes.temporal_score(old_id)["temporal_score"]

        assert fresh_score > old_score

    def test_fresh_node_near_one(self, mg_with_nodes):
        """A node created just now should have a high temporal score."""
        fresh = mg_with_nodes.recall("Fresh", limit=1)[0]
        result = mg_with_nodes.temporal_score(fresh.id)
        assert result["temporal_score"] > 0.9

    def test_old_node_decays(self, mg_with_nodes):
        """A 60-day-old node should have noticeable decay."""
        # Use direct DB query to avoid recall() side-effect updating accessed
        old_id = mg_with_nodes.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE '%Old%'"
        ).fetchone()["id"]
        result = mg_with_nodes.temporal_score(old_id, alpha=0.5)
        assert result["temporal_score"] < 0.5

    def test_age_days_correct(self, mg_with_nodes):
        old_id = mg_with_nodes.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE '%Old%'"
        ).fetchone()["id"]
        result = mg_with_nodes.temporal_score(old_id)
        assert result["age_days"] >= 59  # ~60 days


class TestAlphaParameter:
    """Alpha controls decay sharpness."""

    def test_alpha_zero_no_decay(self, mg_with_nodes):
        """alpha=0 means nearly no decay — score should be ~1.0."""
        old = mg_with_nodes.recall("Old", limit=1)[0]
        result = mg_with_nodes.temporal_score(old.id, alpha=0.0)
        # With alpha=0, exp(0) = 1.0 for all components
        assert result["temporal_score"] > 0.99

    def test_alpha_one_aggressive_decay(self, mg_with_nodes):
        """alpha=1.0 means aggressive decay."""
        old_id = mg_with_nodes.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE '%Old%'"
        ).fetchone()["id"]
        result_low = mg_with_nodes.temporal_score(old_id, alpha=0.1)
        result_high = mg_with_nodes.temporal_score(old_id, alpha=1.0)
        assert result_high["temporal_score"] < result_low["temporal_score"]

    def test_alpha_in_result(self, mg_with_nodes):
        nodes = mg_with_nodes.recall("Fresh", limit=1)
        result = mg_with_nodes.temporal_score(nodes[0].id, alpha=0.7)
        assert result["alpha"] == 0.7


class TestQueryTimeOverride:
    """Custom query_time parameter."""

    def test_future_query_time_lowers_score(self, mg_with_nodes):
        fresh = mg_with_nodes.recall("Fresh", limit=1)[0]
        now_score = mg_with_nodes.temporal_score(fresh.id)["temporal_score"]
        future_score = mg_with_nodes.temporal_score(
            fresh.id, query_time=time.time() + 365 * 86400
        )["temporal_score"]
        assert future_score < now_score

    def test_past_query_time_raises_score_for_old(self, mg_with_nodes):
        """Querying 'in the past' when old node was still fresh."""
        old = mg_with_nodes.recall("Old", limit=1)[0]
        # Query at creation time
        created = mg_with_nodes.conn.execute(
            "SELECT created FROM nodes WHERE id=?", (old.id,)
        ).fetchone()["created"]
        past_score = mg_with_nodes.temporal_score(old.id, query_time=created + 1)
        assert past_score["temporal_score"] > 0.99


class TestHalfLifeParameter:
    """Configurable half-life for age decay."""

    def test_shorter_half_life_more_decay(self, mg_with_nodes):
        old_id = mg_with_nodes.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE '%Old%'"
        ).fetchone()["id"]
        long_hl = mg_with_nodes.temporal_score(old_id, half_life_days=365)
        short_hl = mg_with_nodes.temporal_score(old_id, half_life_days=7)
        assert long_hl["temporal_score"] > short_hl["temporal_score"]

    def test_default_half_life_30_days(self, mg_with_nodes):
        fresh = mg_with_nodes.recall("Fresh", limit=1)[0]
        result = mg_with_nodes.temporal_score(fresh.id)
        # Default should not raise and produce valid score
        assert 0.0 <= result["temporal_score"] <= 1.0


class TestValidityComponent:
    """Bi-temporal validity affects temporal score."""

    def test_expired_node_validity_zero(self):
        mg = MemoryGraph()
        mg.add("Expiring fact", "fact")
        node = mg.recall("Expiring", limit=1)[0]
        # Set valid_to in the past
        mg.conn.execute(
            "UPDATE nodes SET valid_to=? WHERE id=?",
            (time.time() - 86400, node.id)  # expired yesterday
        )
        mg.conn.commit()
        result = mg.temporal_score(node.id)
        assert result["validity_component"] == 0.0
        assert result["temporal_score"] == 0.0  # multiplicative

    def test_future_validity_full_score(self):
        mg = MemoryGraph()
        mg.add("Valid fact", "fact")
        node = mg.recall("Valid", limit=1)[0]
        # valid_to far in the future
        mg.conn.execute(
            "UPDATE nodes SET valid_to=? WHERE id=?",
            (time.time() + 365 * 86400, node.id)
        )
        mg.conn.commit()
        result = mg.temporal_score(node.id)
        assert result["validity_component"] == 1.0

    def test_near_expiry_lowers_validity(self):
        mg = MemoryGraph()
        mg.add("Soon to expire", "fact")
        node = mg.recall("Soon", limit=1)[0]
        # Set valid_to 3 days from now (within 7-day window)
        mg.conn.execute(
            "UPDATE nodes SET valid_to=? WHERE id=?",
            (time.time() + 3 * 86400, node.id)
        )
        mg.conn.commit()
        result = mg.temporal_score(node.id)
        assert 0.0 < result["validity_component"] < 1.0


class TestComponentMath:
    """Verify component arithmetic."""

    def test_components_product_equals_composite(self, mg_with_nodes):
        """temporal_score ≈ age^0.4 * access^0.35 * validity^0.25."""
        fresh = mg_with_nodes.recall("Fresh", limit=1)[0]
        r = mg_with_nodes.temporal_score(fresh.id, alpha=0.5)
        expected = (
            r["age_component"] ** 0.40 *
            r["access_component"] ** 0.35 *
            r["validity_component"] ** 0.25
        )
        assert abs(r["temporal_score"] - round(expected, 4)) < 0.01

    def test_all_components_in_range(self, mg_with_nodes):
        nodes = mg_with_nodes.recall("topic", limit=10)
        for n in nodes:
            r = mg_with_nodes.temporal_score(n.id)
            for key in ("age_component", "access_component", "validity_component"):
                assert 0.0 <= r[key] <= 1.0


class TestDoesNotMutate:
    """temporal_score should not modify the graph."""

    def test_no_mutation(self, mg_with_nodes):
        stats_before = mg_with_nodes.stats()
        nodes = mg_with_nodes.recall("topic", limit=5)
        for n in nodes:
            mg_with_nodes.temporal_score(n.id)
        stats_after = mg_with_nodes.stats()
        assert stats_before["nodes"] == stats_after["nodes"]
        assert stats_before["edges"] == stats_after["edges"]
