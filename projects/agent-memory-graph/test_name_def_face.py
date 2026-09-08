#!/usr/bin/env python3
"""C559 face test: name-demand definitional-anaphora face
(answer_speaker_recall, C534-style exemption shape).

Live fixture from the C559 census (routing ∩ demand population over
the full-500 = 8 rows, exactly one change):
- c4f10528: '...the name of that restaurant in Cihampelas Walk that
  serves a great Nasi Goreng?' — cross-sentence evidence. The GT
  bearer 'Miss Bee Providore: This restaurant serves a mix of
  western and Indonesian cuisine...' carries raw=2 only (the
  locator 'Cihampelas Walk' sits in the INTRO sentence), so the
  distinctive floors hid it and the impostor list item 'Take a
  cooking class: Bandung is famous... nasi goreng...' (raw=3)
  parasitized the overlap instead. The face promotes the sentence
  that DEFINES the entity under the asked name:
  '<ProperName>: this <question-head-noun> ...'.

Structural exclusions, all pinned below:
- verb-phrase colon prefix ('Take a cooking class: ...') is not a
  name bearer — every colon-prefix word must be capitalized
- locator-sibling definition ('Cihampelas Walk: ... this shopping
  center ...') is a bearer but its anaphor noun fails the question
  head-noun match -> never promoted (head-mismatch-only pools
  leave the incumbent untouched)
- non name-demand questions untouched (regex gate)
- raw=1 bearer below the exemption floor; weighted_floor kept;
  best=None (no passers) falls through untouched

The tier branch (bearer among passers) shares the bearer predicate
and is verified end-to-end by the production replay (expect exactly
c4f10528); census found zero tier fires on the 8-row population.
"""
import sys, unittest

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q

QUESTION = ("I'm planning to visit Bandung again and I was wondering if "
            "you could remind me of the name of that restaurant in "
            "Cihampelas Walk that serves a great Nasi Goreng?")

IMPOSTOR = ("Take a cooking class: Bandung is famous for its cuisine, "
            "and you can take a cooking class to learn how to make "
            "traditional Indonesian dishes such as nasi goreng, sate, "
            "and rendang.")
INTRO = ("There are many good restaurants and cafes in the Cihampelas "
         "Walk area.")
BEARER = ("Miss Bee Providore: This restaurant serves a mix of western "
          "and Indonesian cuisine and has a cozy and stylish interior.")
SIBLING_ANAPHOR = ("Cihampelas Walk: Also known as Ciwalk, this shopping "
                   "center is famous for its denim street.")
SIBLING_NO_ANAPHOR = ("Bakery & Co: A great place to relax and enjoy a "
                      "cup of coffee and a pastry.")


def _nodes(*labels):
    return {f"n{i}": {"role": "assistant", "label": s, "session_id": "s1"}
            for i, s in enumerate(labels)}


class TestNameDefFace(unittest.TestCase):
    def test_c4f10528_exemption_rescue(self):
        """Impostor (raw=3) loses to the raw=2 definitional bearer."""
        nodes = _nodes(INTRO + " Here are a few options: 1. " + BEARER
                       + " 2. " + SIBLING_NO_ANAPHOR, IMPOSTOR)
        ans, det = Q.answer_speaker_recall(QUESTION, nodes)
        self.assertIsNotNone(ans)
        self.assertEqual(det.get("name_def_face"), "exemption")
        self.assertTrue(ans.startswith("Miss Bee Providore"), ans)

    def test_verb_prefix_colon_not_a_bearer(self):
        """'Take a cooking class: ...' — lowercase word in the colon
        prefix -> not a name, never enters tier/exemption."""
        self.assertFalse(Q._name_def_bearer(
            IMPOSTOR, Q._name_def_head(QUESTION)))

    def test_locator_sibling_head_mismatch_stays_unpromoted(self):
        """'Cihampelas Walk: ... this shopping center ...' — bearer
        shape, wrong anaphor noun; the exemption must pick the TRUE
        bearer, never the sibling. (Keyword-free fillers raise the
        pool N so the raw=2 bearer clears the weighted_floor — in the
        real corpus N=4480 makes that automatic.)"""
        filler = ("The weather is lovely and the cafe downstairs has "
                  "great pastries.")
        nodes = _nodes(BEARER, IMPOSTOR, SIBLING_ANAPHOR,
                       *([filler] * 6))
        ans, det = Q.answer_speaker_recall(QUESTION, nodes)
        self.assertEqual(det.get("name_def_face"), "exemption")
        self.assertTrue(ans.startswith("Miss Bee Providore"), ans)

    def test_head_mismatch_only_bearer_falls_through(self):
        """When the ONLY raw>=2 bearer is the wrong-head sibling, the
        face must not fire — incumbent best stands."""
        q_loc = ("I'm planning to visit Bandung again and I was "
                 "wondering if you could remind me of the name of that "
                 "restaurant near Cihampelas Walk?")
        nodes = _nodes(SIBLING_ANAPHOR, IMPOSTOR)
        ans, det = Q.answer_speaker_recall(q_loc, nodes)
        self.assertNotIn("name_def_face", det)

    def test_no_name_demand_untouched(self):
        """Regex gate: questions without 'name of that/the ...' never
        fire the face."""
        q_plain = ("I'm planning to visit Bandung again — what dishes "
                   "should I try there?")
        nodes = _nodes(BEARER, IMPOSTOR)
        Q.answer_speaker_recall(q_plain, nodes)  # must not raise either
        ans, det = Q.answer_speaker_recall(q_plain, nodes)
        self.assertNotIn("name_def_face", det)

    def test_raw_one_bearer_never_exempted(self):
        """Exemption floor: a bearer with raw<2 stays hidden."""
        bare = ("Miss Bee Providore: This restaurant has a cozy and "
                "stylish interior.")  # matches only 'restaurant'
        nodes = _nodes(bare, IMPOSTOR)
        ans, det = Q.answer_speaker_recall(QUESTION, nodes)
        self.assertNotIn("name_def_face", det)

    def test_weighted_floor_kept_in_exemption(self):
        """Exemption keeps the weighted_floor: a bearer whose raw=2
        score collapses (all matched kws maximally frequent) stays
        hidden even in bearer shape."""
        filler = ("Let me remind you of the name of the restaurant: "
                  "the restaurant serves plates.")  # pumps df of both kws
        nodes = _nodes(*([BEARER] + [filler] * 6 + [IMPOSTOR]))
        ans, det = Q.answer_speaker_recall(QUESTION, nodes)
        self.assertNotIn("name_def_face", det)

    def test_no_passers_falls_through(self):
        """best=None (nothing passes the distinctive floors): face
        does not fire, caller falls through — censused behavior."""
        q_known = ("Could you remind me of the name of that restaurant "
                   "in Cihampelas Walk?")
        nodes = _nodes(BEARER)
        ans, det = Q.answer_speaker_recall(q_known, nodes)
        self.assertIsNone(ans)
        self.assertNotIn("name_def_face", det)

    def test_official_fixture(self):
        """End-to-end against the real c4f10528 row: impostor out,
        GT bearer in."""
        import json
        item = None
        for it in json.load(
                open("/root/lme_data/longmemeval_s_cleaned.json")):
            if it["question_id"] == "c4f10528":
                item = it
                break
        ad = Q.LongMemEvalAdapter()
        hay = item.get("haystack_sessions") or []
        sessions = [{"session_id": f"session_{j+1}", "messages": s}
                    for j, s in enumerate(hay)]
        hd = item.get("haystack_dates") or []
        sd = {f"session_{j+1}": dt
              for j, dt in enumerate(hd) if j < len(sessions)}
        ad.ingest_sessions(sessions, session_dates=sd)
        ans, det = Q.answer_speaker_recall(item["question"], ad._nodes)
        self.assertEqual(det.get("name_def_face"), "exemption")
        self.assertIn("Miss Bee Providore", ans)
        self.assertNotIn("cooking class", ans)


if __name__ == "__main__":
    unittest.main(verbosity=2)
