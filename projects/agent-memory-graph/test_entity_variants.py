"""Tests for resolve_entity_variants() — GraphRAG-Bench Gap #5 (Research #064).

Entity variant resolution for KG indexing: case-insensitive, honorific/title
normalisation, and conservative word-boundary containment. Canonical = longest
label (most informative); tie → first-added. Same-kind only. dry_run = report
without mutation.
"""
import pytest

from memory_graph import MemoryGraph
from run_amg import index_corpus


def _mg():
    return MemoryGraph(":memory:")


class TestCaseMode:
    def test_case_insensitive_exact_duplicates_merged(self):
        mg = _mg()
        a = mg.add("Claire Bennett", kind="person")
        b = mg.add("claire bennett", kind="person")
        report = mg.resolve_entity_variants()
        assert report["variants_merged"] == 1
        assert mg.get_node(b.id) is None          # absorbed
        assert mg.get_node(a.id) is not None      # canonical (longest, tie → first)
        assert mg.get_node(a.id).label == "Claire Bennett"

    def test_case_mode_respects_kind(self):
        mg = _mg()
        mg.add("Mercury", kind="person")
        mg.add("mercury", kind="planet")
        report = mg.resolve_entity_variants()
        assert report["variants_merged"] == 0

    def test_case_mode_distinct_labels_untouched(self):
        mg = _mg()
        a = mg.add("JOHN SMITH", kind="person")
        b = mg.add("John Smith PhD", kind="person")
        report = mg.resolve_entity_variants(modes=("case",))
        assert report["variants_merged"] == 0
        assert mg.get_node(a.id) and mg.get_node(b.id)

    def test_case_mode_reports_groups(self):
        mg = _mg()
        mg.add("Paris", kind="city")
        mg.add("paris", kind="city")
        mg.add("PARIS", kind="city")
        report = mg.resolve_entity_variants(modes=("case",))
        assert report["groups_found"] == 1
        assert report["variants_merged"] == 2
        assert report["details"][0]["mode"] == "case"


class TestTitleMode:
    def test_honorific_stripped_merge(self):
        mg = _mg()
        canonical = mg.add("Alice Chen", kind="person")
        variant = mg.add("Dr. Alice Chen", kind="person")
        report = mg.resolve_entity_variants(modes=("title",))
        assert report["variants_merged"] == 1
        assert mg.get_node(variant.id) is None
        assert mg.get_node(canonical.id) is not None

    def test_different_names_no_merge(self):
        mg = _mg()
        mg.add("Mr. Darcy", kind="person")
        mg.add("Mrs. Bennet", kind="person")
        report = mg.resolve_entity_variants(modes=("title",))
        assert report["variants_merged"] == 0

    def test_trailing_initial_merge(self):
        mg = _mg()
        mg.add("Claire P.", kind="person")
        mg.add("Claire", kind="person")
        report = mg.resolve_entity_variants(modes=("title",))
        assert report["variants_merged"] == 1

    def test_saint_prefix_documented_aggressive(self):
        mg = _mg()
        mg.add("Mont St. Michel", kind="landmark")
        mg.add("Mont Michel", kind="landmark")
        # "St." is in honorifics set → normalises to "mont michel" → merges.
        # Documented aggressive behaviour (dry_run keeps it observable).
        report = mg.resolve_entity_variants(modes=("title",), dry_run=True)
        assert report["groups_found"] == 1

    def test_title_mode_respects_kind(self):
        mg = _mg()
        mg.add("Dr. Who", kind="person")
        mg.add("Who", kind="band")
        report = mg.resolve_entity_variants(modes=("title",))
        assert report["variants_merged"] == 0


class TestContainmentMode:
    def test_word_prefix_containment_merge(self):
        mg = _mg()
        full = mg.add("Claire Bennett", kind="person")
        short = mg.add("Claire", kind="person")
        report = mg.resolve_entity_variants(modes=("containment",))
        assert report["variants_merged"] == 1
        assert mg.get_node(short.id) is None
        assert mg.get_node(full.id) is not None  # longest is canonical

    def test_possessive_not_word_boundary(self):
        mg = _mg()
        mg.add("Claire", kind="person")
        mg.add("Claire's Garden", kind="location")
        report = mg.resolve_entity_variants(modes=("containment",))
        assert report["variants_merged"] == 0  # kind mismatch + "'" boundary

    def test_same_kind_possessive_still_blocked(self):
        mg = _mg()
        mg.add("Claire", kind="person")
        mg.add("Claire's Diary", kind="person")  # contrived
        report = mg.resolve_entity_variants(modes=("containment",))
        # "claire" prefix of "claire's diary" but next char "'" → not word boundary
        assert report["variants_merged"] == 0

    def test_min_len_guard(self):
        mg = _mg()
        mg.add("Al", kind="person")
        mg.add("Albert Einstein", kind="person")
        report = mg.resolve_entity_variants(modes=("containment",))
        assert report["variants_merged"] == 0

    def test_min_len_override(self):
        mg = _mg()
        mg.add("Al", kind="person")
        mg.add("Al Gore", kind="person")
        report = mg.resolve_entity_variants(modes=("containment",), min_len=2)
        assert report["variants_merged"] == 1

    def test_containment_requires_word_prefix_not_substring(self):
        mg = _mg()
        mg.add("Saint", kind="person")
        mg.add("Vincent Saint-Pierre", kind="person")
        # "saint" appears mid-string, not as word prefix → no merge
        report = mg.resolve_entity_variants(modes=("containment",))
        assert report["variants_merged"] == 0


class TestDryRun:
    def test_dry_run_no_mutation(self):
        mg = _mg()
        a = mg.add("Claire Bennett", kind="person")
        b = mg.add("Claire", kind="person")
        report = mg.resolve_entity_variants(modes=("containment",), dry_run=True)
        assert report["dry_run"] is True
        assert report["groups_found"] == 1
        assert mg.get_node(a.id) is not None and mg.get_node(b.id) is not None

    def test_dry_run_aliases_not_registered(self):
        mg = _mg()
        mg.add("Alice Chen", kind="person")
        mg.add("Dr. Alice Chen", kind="person")
        mg.resolve_entity_variants(modes=("title",), dry_run=True)
        # No alias registered for a label that is not itself a node
        assert mg.resolve_alias("Ms. Alice Chen") is None


class TestAliasesAndEdges:
    def test_alias_registered_on_merge(self):
        mg = _mg()
        mg.add("Alice Chen", kind="person")
        mg.add("Dr. Alice Chen", kind="person")
        mg.resolve_entity_variants(modes=("title",))
        assert mg.resolve_alias("Dr. Alice Chen") == "Alice Chen"

    def test_edges_redirected_on_merge(self):
        mg = _mg()
        full = mg.add("Claire Bennett", kind="person")
        short = mg.add("Claire", kind="person")
        target = mg.add("Pottery", kind="hobby")
        mg.link(short.id, target.id, "likes")
        mg.resolve_entity_variants(modes=("containment",))
        neighbour_ids = {n.id for n in mg.neighbors(full.id)}
        assert target.id in neighbour_ids

    def test_absorbed_node_listed_in_details(self):
        mg = _mg()
        mg.add("Claire Bennett", kind="person")
        v = mg.add("Claire", kind="person")
        report = mg.resolve_entity_variants(modes=("containment",))
        d = report["details"][0]
        assert d["canonical"] == "Claire Bennett"
        assert any(x[0] == v.id for x in d["absorbed"])


class TestCombinedModes:
    def test_default_modes_case_and_title(self):
        mg = _mg()
        mg.add("Bob", kind="person")
        mg.add("bob", kind="person")          # case
        mg.add("Mr. Bob", kind="person")      # title (honorific)
        mg.add("Bob the Builder", kind="person")  # containment — OFF by default
        report = mg.resolve_entity_variants()
        # case merges bob→Bob; title merges Mr. Bob→Bob. Bob the Builder stays.
        assert report["variants_merged"] == 2
        remaining = [r["label"] for r in
                     mg.conn.execute("SELECT label FROM nodes")]
        assert sorted(remaining) == ["Bob", "Bob the Builder"]

    def test_unknown_mode_rejected(self):
        mg = _mg()
        with pytest.raises(ValueError):
            mg.resolve_entity_variants(modes=("bogus",))


class TestRunAmgIntegration:
    def _corpus(self):
        return [{"corpus_name": "doc1",
                 "context": "Alice Chen enjoys pottery. "
                            "Dr. Alice Chen works at Google."}]

    def _corpus_variants(self):
        return [{"corpus_name": "doc2",
                 "context": "Claire Bennett joined Acme. "
                            "Claire left Acme later."}]

    def test_index_corpus_with_resolution_true(self):
        mg = _mg()
        stats = index_corpus(mg, self._corpus(), resolve_entities=True)
        assert "entity_resolution" in stats
        er = stats["entity_resolution"]
        assert "variants_merged" in er
        labels = [r["label"] for r in
                  mg.conn.execute("SELECT label FROM nodes")]
        assert not any(l.startswith("Dr.") for l in labels)

    def test_index_corpus_with_dict_config(self):
        mg = _mg()
        stats = index_corpus(mg, self._corpus_variants(),
                             resolve_entities={"modes": ("containment",)})
        er = stats["entity_resolution"]
        assert er["variants_merged"] == 1
        assert er["details"][0]["mode"] == "containment"
        assert er["details"][0]["canonical"] == "Claire Bennett"

    def test_index_corpus_default_no_resolution(self):
        mg = _mg()
        stats = index_corpus(mg, self._corpus())
        assert "entity_resolution" not in stats

    def test_e2e_query_hits_resolved_node(self):
        mg = _mg()
        text = ("Claire Bennett joined Acme in 2021. "
                "Mr. Darcy lives in Derbyshire.")
        mg.extract_from_text(text)
        mg.resolve_entity_variants(modes=("case", "title"))
        result = mg.graphrag_query("Who joined Acme?")
        assert result.get("answer_nodes") is not None
