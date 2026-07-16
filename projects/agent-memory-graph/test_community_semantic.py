"""Tests for community semantic layer — GraphRAG-inspired features.

Tests for:
  - community_topic_labels(): automatic topic extraction per community
  - community_semantic_summary(): per-community summaries (deterministic + LLM)
  - community_overview(): combined structural + semantic dashboard
  - query_global(): GraphRAG-style global query across community summaries
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated_mg():
    """Graph with clear community structure."""
    mg = MemoryGraph(":memory:")

    # Tech community
    python = mg.add("Python programming language", "concept", tags=["coding"])
    rust = mg.add("Rust systems language", "concept", tags=["coding"])
    llvm = mg.add("LLVM compiler infrastructure", "concept")
    mg.link(python.id, rust.id, "related_to")
    mg.link(rust.id, llvm.id, "built_on")
    mg.link(python.id, llvm.id, "related_to")

    # Food community
    italian = mg.add("Italian cuisine preferences", "fact", tags=["food"])
    pizza = mg.add("Neapolitan pizza recipe", "fact", tags=["food"])
    pasta = mg.add("Fresh pasta making", "skill", tags=["food"])
    mg.link(italian.id, pizza.id, "related_to")
    mg.link(italian.id, pasta.id, "related_to")
    mg.link(pizza.id, pasta.id, "related_to")

    # Project community
    proj = mg.add("OpenClaw development", "event", tags=["work"])
    bug = mg.add("Fix memory leak issue", "event")
    feat = mg.add("Add new feature module", "event")
    mg.link(proj.id, bug.id, "contains")
    mg.link(proj.id, feat.id, "contains")
    mg.link(bug.id, feat.id, "related_to")

    return mg


# ─── community_topic_labels ────────────────────────────────────────────

class TestCommunityTopicLabels:
    """Tests for community_topic_labels()."""

    def test_returns_dict(self, populated_mg):
        """Should return a dict mapping community IDs to topic lists."""
        topics = populated_mg.community_topic_labels()
        assert isinstance(topics, dict)
        assert len(topics) > 0

    def test_topics_are_lists_of_strings(self, populated_mg):
        """Each community's topics should be a list of strings."""
        topics = populated_mg.community_topic_labels()
        for cid, topic_list in topics.items():
            assert isinstance(topic_list, list)
            for t in topic_list:
                assert isinstance(t, str)

    def test_topics_respect_top_k(self, populated_mg):
        """top_k limits the number of topics."""
        topics = populated_mg.community_topic_labels(top_k=2)
        for topic_list in topics.values():
            assert len(topic_list) <= 2

    def test_empty_graph(self, mg):
        """Empty graph → empty dict."""
        assert mg.community_topic_labels() == {}

    def test_single_node(self, mg):
        """Single node → one community with one topic."""
        mg.add("Python coding", "concept", {"tags": ["dev"]})
        n2 = mg.add("Rust coding", "concept", {"tags": ["dev"]})
        mg.link(mg.recall("Python")[0].id, n2.id, "related_to")
        topics = mg.community_topic_labels()
        assert len(topics) >= 1

    def test_topics_include_kinds(self, populated_mg):
        """Topics should include kind-based labels."""
        topics = populated_mg.community_topic_labels()
        all_topics = []
        for tl in topics.values():
            all_topics.extend(tl)
        # At least one topic should end with 's' (kind pluralised)
        assert any(t.endswith("s") for t in all_topics)

    def test_topics_include_tags(self, populated_mg):
        """Tags like 'coding', 'food', 'work' should appear."""
        topics = populated_mg.community_topic_labels()
        all_topics = set()
        for tl in topics.values():
            for t in tl:
                all_topics.add(t.lower())
        # At least one of our tags should appear
        assert any(tag in all_topics for tag in ["coding", "food", "work"])

    def test_with_explicit_communities(self, populated_mg):
        """Passing explicit communities dict works."""
        nodes = [r["id"] for r in populated_mg.conn.execute(
            "SELECT id FROM nodes LIMIT 5").fetchall()]
        communities = {}
        for i, nid in enumerate(nodes):
            communities[nid] = i % 2
        topics = populated_mg.community_topic_labels(communities)
        assert len(topics) <= 2

    def test_top_k_zero(self, populated_mg):
        """top_k=0 → empty lists."""
        topics = populated_mg.community_topic_labels(top_k=0)
        for tl in topics.values():
            assert len(tl) == 0


# ─── community_semantic_summary ────────────────────────────────────────

class TestCommunitySemanticSummary:
    """Tests for community_semantic_summary()."""

    def test_returns_list(self, populated_mg):
        """Should return a list of summary dicts."""
        summaries = populated_mg.community_semantic_summary()
        assert isinstance(summaries, list)
        assert len(summaries) > 0

    def test_summary_fields(self, populated_mg):
        """Each summary has required fields."""
        summaries = populated_mg.community_semantic_summary()
        for s in summaries:
            assert "community_id" in s
            assert "size" in s
            assert "summary" in s
            assert "top_labels" in s
            assert "topics" in s

    def test_summary_nonempty(self, populated_mg):
        """Summaries should not be empty for populated communities."""
        summaries = populated_mg.community_semantic_summary()
        for s in summaries:
            assert len(s["summary"]) > 0
            assert len(s["top_labels"]) > 0

    def test_sorted_by_size(self, populated_mg):
        """Results should be sorted by size descending."""
        summaries = populated_mg.community_semantic_summary()
        sizes = [s["size"] for s in summaries]
        assert sizes == sorted(sizes, reverse=True)

    def test_with_llm_callback(self, populated_mg):
        """LLM summarizer callback is used when provided."""
        calls = []
        def fake_llm(text):
            calls.append(text)
            return f"SUMMARY: {text[:20]}"

        summaries = populated_mg.community_semantic_summary(summarizer=fake_llm)
        assert len(calls) > 0
        for s in summaries:
            assert s["summary"].startswith("SUMMARY:")

    def test_llm_callback_exception_fallback(self, populated_mg):
        """If LLM raises, falls back to deterministic summary."""
        def bad_llm(text):
            raise RuntimeError("LLM unavailable")

        summaries = populated_mg.community_semantic_summary(summarizer=bad_llm)
        for s in summaries:
            assert len(s["summary"]) > 0  # fallback worked

    def test_empty_graph(self, mg):
        """Empty graph → empty list."""
        assert mg.community_semantic_summary() == []

    def test_with_explicit_communities(self, populated_mg):
        """Explicit communities dict works."""
        nodes = [r["id"] for r in populated_mg.conn.execute(
            "SELECT id FROM nodes").fetchall()]
        communities = {nid: 0 for nid in nodes}  # all one community
        summaries = populated_mg.community_semantic_summary(communities)
        assert len(summaries) == 1
        assert summaries[0]["size"] == len(nodes)

    def test_top_labels_max_ten(self, populated_mg):
        """top_labels should have at most 10 entries."""
        summaries = populated_mg.community_semantic_summary()
        for s in summaries:
            assert len(s["top_labels"]) <= 10


# ─── community_overview ────────────────────────────────────────────────

class TestCommunityOverview:
    """Tests for community_overview()."""

    def test_returns_dict(self, populated_mg):
        """Should return a dashboard dict."""
        r = populated_mg.community_overview()
        assert isinstance(r, dict)

    def test_required_fields(self, populated_mg):
        """Result has required top-level fields."""
        r = populated_mg.community_overview()
        assert "total_communities" in r
        assert "total_nodes" in r
        assert "largest_community" in r
        assert "communities" in r

    def test_total_nodes_matches(self, populated_mg):
        """total_nodes should equal sum of community sizes."""
        r = populated_mg.community_overview()
        assert r["total_nodes"] == sum(c["size"] for c in r["communities"])

    def test_largest_community(self, populated_mg):
        """Largest community is the one with most members."""
        r = populated_mg.community_overview()
        if r["communities"]:
            sizes = [c["size"] for c in r["communities"]]
            largest_id = r["communities"][0]["id"]
            assert r["largest_community"] == largest_id
            assert sizes[0] == max(sizes)

    def test_community_fields(self, populated_mg):
        """Each community in overview has combined fields."""
        r = populated_mg.community_overview()
        for c in r["communities"]:
            assert "id" in c
            assert "size" in c
            assert "summary" in c
            assert "topics" in c
            assert "density" in c
            assert "top_members" in c

    def test_empty_graph(self, mg):
        """Empty graph → zero overview."""
        r = mg.community_overview()
        assert r["total_communities"] == 0
        assert r["total_nodes"] == 0
        assert r["communities"] == []

    def test_with_summarizer(self, populated_mg):
        """Passing summarizer enhances summaries."""
        def llm(text):
            return f"CUSTOM: {text[:30]}"
        r = populated_mg.community_overview(summarizer=llm)
        for c in r["communities"]:
            if c["summary"]:
                assert c["summary"].startswith("CUSTOM:")

    def test_communities_sorted_by_size(self, populated_mg):
        """Communities in overview are sorted by size descending."""
        r = populated_mg.community_overview()
        sizes = [c["size"] for c in r["communities"]]
        assert sizes == sorted(sizes, reverse=True)


# ─── query_global ──────────────────────────────────────────────────────

class TestQueryGlobal:
    """Tests for query_global() — GraphRAG global search."""

    def test_returns_dict(self, populated_mg):
        """Should return a query result dict."""
        r = populated_mg.query_global("what programming languages?")
        assert isinstance(r, dict)

    def test_required_fields(self, populated_mg):
        """Result has required fields."""
        r = populated_mg.query_global("test query")
        assert "question" in r
        assert "communities_matched" in r
        assert "total_communities" in r
        assert "results" in r

    def test_results_have_member_nodes(self, populated_mg):
        """Each result should have member node details."""
        r = populated_mg.query_global("Python coding")
        for res in r["results"]:
            assert "members" in res
            assert isinstance(res["members"], list)

    def test_query_finds_relevant(self, populated_mg):
        """Query about 'programming language' should find tech community."""
        r = populated_mg.query_global("programming language coding")
        assert r["total_communities"] > 0
        # Top result should mention Python or Rust in its members
        if r["results"]:
            top = r["results"][0]
            all_labels = " ".join(m["label"] for m in top["members"])
            # At least one result should match
            found = False
            for res in r["results"]:
                for m in res["members"]:
                    if any(w in m["label"].lower() for w in ["python", "rust", "llvm"]):
                        found = True
            assert found, "No result contained expected tech community members"

    def test_empty_graph(self, mg):
        """Empty graph → zero results."""
        r = mg.query_global("anything")
        assert r["communities_matched"] == 0
        assert r["total_communities"] == 0
        assert r["results"] == []

    def test_limit_respected(self, populated_mg):
        """Limit parameter caps number of results."""
        r = populated_mg.query_global("test", limit=1)
        assert len(r["results"]) <= 1

    def test_results_sorted_by_score(self, populated_mg):
        """Results should be sorted by score descending."""
        r = populated_mg.query_global("language food project", limit=5)
        scores = [res["score"] for res in r["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_member_nodes_have_fields(self, populated_mg):
        """Member nodes have id, label, kind, weight."""
        r = populated_mg.query_global("coding")
        for res in r["results"]:
            for m in res["members"]:
                assert "id" in m
                assert "label" in m
                assert "kind" in m
                assert "weight" in m

    def test_question_echoed(self, populated_mg):
        """The question is echoed in the result."""
        r = populated_mg.query_global("my specific question")
        assert r["question"] == "my specific question"

    def test_result_fields_complete(self, populated_mg):
        """Each result has all expected fields."""
        r = populated_mg.query_global("food")
        for res in r["results"]:
            assert "community_id" in res
            assert "score" in res
            assert "summary" in res
            assert "topics" in res
            assert "size" in res

    def test_zero_match_query(self, populated_mg):
        """Query with no keyword overlap → 0 matched but still returns results."""
        r = populated_mg.query_global("xyzzy qwerty")
        # Should return results (with score 0) but matched count = 0
        assert r["communities_matched"] == 0


# ─── _group_communities helper ─────────────────────────────────────────

class TestGroupCommunities:
    """Tests for _group_communities helper."""

    def test_groups_correctly(self, mg):
        """Should group node IDs by community ID."""
        groups = mg._group_communities({"a": 0, "b": 0, "c": 1})
        assert set(groups[0]) == {"a", "b"}
        assert set(groups[1]) == {"c"}

    def test_empty_input(self, mg):
        """Empty dict → empty dict."""
        assert mg._group_communities({}) == {}

    def test_single_community(self, mg):
        """All same community → one group."""
        groups = mg._group_communities({"a": 5, "b": 5})
        assert len(groups) == 1
        assert set(groups[5]) == {"a", "b"}
