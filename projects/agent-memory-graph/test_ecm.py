"""Cycle 497: neither-family Event-Centric Comparison Matcher (ECM).

Tests the STRICT form gate (zero-hijack census contract: exactly the
4/500 family members), the vague-duration ordinal scalar track, the
calendar track, descriptive-NP evidence (verb-face exemption), name
entities with the verb face (same-name decoy blocking), the
cross-turn anaphora join, the negative-existence abstain twin, and
end-to-end wiring through answer_extractive (gate=ecm, ecm=False
switch, fall-through on unresolved forms).
"""
import unittest
from datetime import date

import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, ecm_form, answer_ecm, _ecm_resolve_days,
    _ecm_is_name_entity, _ecm_content_words, _ecm_build_recs,
    _ecm_window_text, _ecm_anaphora_join, ABSTAIN_ANSWER)


def turn(role, content):
    return {"role": role, "content": content}


class TestEcmForm(unittest.TestCase):
    def test_meet_form(self):
        self.assertEqual(
            ecm_form("Who did I meet first, Tom or Mark?"),
            ("meet", "Tom", "Mark"))

    def test_get_to_know_form(self):
        self.assertEqual(
            ecm_form("Who did I get to know first, Sarah or Emma?"),
            ("get to know", "Sarah", "Emma"))

    def test_became_parent_form(self):
        self.assertEqual(
            ecm_form("Who became a parent first, Rachel or Alex?"),
            ("became a parent", "Rachel", "Alex"))

    def test_negative_which_first_is_pairwise(self):
        # "which … first" belongs to C489 pairwise — forms mutually
        # exclusive (census contract)
        self.assertIsNone(ecm_form(
            "Which did I finish first, the report or the slides?"))

    def test_negative_order_family(self):
        self.assertIsNone(ecm_form(
            "What was the order of events from first to last?"))

    def test_negative_no_disjunction(self):
        self.assertIsNone(ecm_form("Who did I meet first?"))

    def test_negative_who_did_i_see(self):
        # verb outside the VERBMAP family — gate stays STRICT
        self.assertIsNone(ecm_form(
            "Who did I see first, Tom or Mark?"))


class TestEcmResolveDays(unittest.TestCase):
    A = date(2023, 5, 30)

    def test_few_months(self):
        self.assertEqual(
            _ecm_resolve_days("a few months ago I met Tom", self.A), 90)

    def test_about_a_month(self):
        self.assertEqual(
            _ecm_resolve_days("about a month ago", self.A), 30)

    def test_weeks_scalar(self):
        self.assertEqual(
            _ecm_resolve_days("two weeks ago", self.A), 14)
        self.assertEqual(
            _ecm_resolve_days("a few weeks ago", self.A), 21)

    def test_last_thursday_calendar_backfill(self):
        # 2023-05-30 is Tuesday → last Thursday = 2023-05-25 = 5d
        self.assertEqual(
            _ecm_resolve_days("last Thursday", self.A), 5)

    def test_calendar_date_track(self):
        self.assertEqual(
            _ecm_resolve_days("born on February 12th", self.A), 107)

    def test_month_midpoint(self):
        self.assertEqual(
            _ecm_resolve_days("in January", self.A), 135)

    def test_unresolvable(self):
        self.assertIsNone(_ecm_resolve_days("no time here", self.A))


class TestEcmEntities(unittest.TestCase):
    def test_name_entity(self):
        # single capitalized tokens are names; a conjoined NP like
        # "Mark and Sarah" carries the lowercase "and" → routes to
        # the descriptive track (content words {mark, sarah}), which
        # is exactly how the 88806d6e oracle case resolves
        self.assertTrue(_ecm_is_name_entity("Tom"))
        self.assertTrue(_ecm_is_name_entity("Rachel"))
        self.assertFalse(_ecm_is_name_entity("Mark and Sarah"))

    def test_descriptive_np(self):
        self.assertFalse(_ecm_is_name_entity(
            "the woman selling jam at the farmer's market"))

    def test_content_words_strip_frame(self):
        cw = _ecm_content_words(
            "the woman selling jam at the farmer's market")
        self.assertIn("jam", cw)
        self.assertIn("farmer", cw)
        self.assertNotIn("the", cw)
        self.assertNotIn("woman", cw)  # in STOP (frame noun)


class TestAnswerEcm(unittest.TestCase):
    def test_meet_vague_duration_compare(self):
        # W4: 90d (a few months) vs 30d (about a month) — ordinal
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "I met a guy named Tom a few months ago. "
                             "He was nice."),
                turn("assistant", "That's great!"),
                turn("user", "I also met Mark and Sarah about a month "
                             "ago at the park."),
            ]),
        ]
        ans, det = answer_ecm(
            "Who did I meet first, Mark and Sarah or Tom?", dated)
        self.assertEqual(ans, "Tom")
        self.assertEqual(det["mode"], "compare")
        # e1 "Mark and Sarah" rides the descriptive track (30d);
        # e2 "Tom" rides the name track (90d) — larger = earlier
        self.assertEqual(det["a_days"], 30)
        self.assertEqual(det["b_days"], 90)

    def test_descriptive_np_verb_face_exempt(self):
        # W1+W2: evidence says "had a conversation with a jam maker"
        # — no "met" token; ≥2 content-word overlap is the gate
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "I had a lovely conversation with a jam "
                             "maker at the farmer's market two weeks "
                             "ago."),
                turn("user", "I also chatted with a tourist from "
                             "Australia last Thursday."),
            ]),
        ]
        ans, det = answer_ecm(
            "Who did I meet first, the woman selling jam at the "
            "farmer's market or the tourist from Australia?", dated)
        self.assertEqual(ans,
                         "the woman selling jam at the farmer's market")
        self.assertEqual(det["a_days"], 14)
        self.assertEqual(det["b_days"], 5)

    def test_name_entity_decoy_blocked_by_verb_face(self):
        # W5: an unrelated same-name "Alex and Ryan" sentence carries
        # no event verb → cannot hijack; real evidence wins
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "My friends Alex and Ryan love hiking."),
                turn("user", "Alex adopted a baby girl in January."),
                turn("user", "Rachel's twins were born on February "
                             "12th."),
            ]),
        ]
        ans, det = answer_ecm(
            "Who became a parent first, Rachel or Alex?", dated)
        self.assertEqual(ans, "Alex")

    def test_anaphora_join_cross_turn(self):
        # W3: name sentence has no date; the date sentence sits in a
        # different turn but shares the relation NP + proper nouns
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "My sister-in-law's twins, Jackson and "
                             "Julia, who were born on February 12th, "
                             "are adorable."),
                turn("assistant", "How lovely!"),
                turn("user", "My sister-in-law, Rachel, is doing "
                             "great with the twins, Jackson and "
                             "Julia."),
            ]),
        ]
        recs = _ecm_build_recs(dated)
        vp = m._ECM_VERBMAP["became a parent"]
        got = _ecm_anaphora_join("Rachel", recs, vp)
        self.assertIsNotNone(got)
        self.assertEqual(got[0], 107)  # Feb 12 vs May 30

    def test_negative_existence_abstain_twin(self):
        # W5: candidate never mentioned → ABSTAIN (GT = not-enough)
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "Alex adopted a baby girl in January."),
            ]),
        ]
        ans, det = answer_ecm(
            "Who became a parent first, Tom or Alex?", dated)
        self.assertEqual(ans, ABSTAIN_ANSWER)
        self.assertEqual(det["mode"], "neg-exist")
        self.assertEqual(det["missing"], "Tom")

    def test_no_time_evidence_abstains(self):
        # both sides mentioned but neither carries a resolvable
        # time → no comparable evidence = negative existence under
        # the ECM contract (C489's partial-mention fall-through is a
        # PAIRWISE semantic; ECM abstains — #082 oracle behavior)
        dated = [
            ("2023/05/30 (Tue) 10:00", [
                turn("user", "I met Tom once. I met Mark too."),
            ]),
        ]
        ans, det = answer_ecm(
            "Who did I meet first, Mark or Tom?", dated)
        self.assertEqual(ans, ABSTAIN_ANSWER)
        self.assertEqual(det["mode"], "neg-exist")

    def test_form_miss_returns_none(self):
        ans, det = answer_ecm("What is my favorite color?", [])
        self.assertIsNone(ans)
        self.assertEqual(det["mode"], "no-form")


class TestAdapterWiring(unittest.TestCase):
    def _ingest(self, adapter):
        sessions = [
            {"session_id": "s1", "messages": [
                turn("user", "I met a guy named Tom a few months ago."),
                turn("assistant", "Nice!"),
            ]},
            {"session_id": "s2", "messages": [
                turn("user", "I also met Mark and Sarah about a month "
                             "ago at the park."),
            ]},
        ]
        adapter.ingest_sessions(
            sessions, session_dates={"s1": "2023/05/20 (Sat) 09:00",
                                     "s2": "2023/05/30 (Tue) 10:00"})

    def test_gate_ecm_end_to_end(self):
        adapter = LongMemEvalAdapter()
        self._ingest(adapter)
        ans, meta = adapter.answer_extractive(
            "Who did I meet first, Mark and Sarah or Tom?",
            question_date="2023/06/01 (Thu)")
        self.assertEqual(ans, "Tom")
        self.assertEqual(meta["gate"], "ecm")
        self.assertFalse(meta["abstained"])
        self.assertEqual(meta["ecm"]["mode"], "compare")

    def test_ecm_disable_switch(self):
        adapter = LongMemEvalAdapter(ecm=False)
        self._ingest(adapter)
        ans, meta = adapter.answer_extractive(
            "Who did I meet first, Mark and Sarah or Tom?",
            question_date="2023/06/01 (Thu)")
        self.assertNotEqual(meta.get("gate"), "ecm")

    def test_run_eval_config_carries_ecm(self):
        import inspect
        self.assertIn("ecm", inspect.signature(m.run_eval).parameters)
        self.assertIn("ecm", inspect.signature(
            LongMemEvalAdapter.__init__).parameters)


if __name__ == "__main__":
    unittest.main()
