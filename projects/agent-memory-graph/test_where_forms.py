"""Cycle 508: where-form locative extraction (Research #084).

Contracts under test (mini.json sim, 3 hash seeds stable):
- where_form: strict start-with-where gate, 19/500 census, zero
  collisions with other families
- answer_where: locative sentence selection — user-role + window +
  rank priors; whole-sentence return (containment judging)
- adapter wiring: gate="where" fires for where-questions with a
  locative candidate; fall-through otherwise (no hijack)
"""
import unittest

import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, where_form, answer_where)


def turn(role, content):
    return {"role": role, "content": content}


class TestWhereForm(unittest.TestCase):
    def test_positive_start(self):
        self.assertTrue(where_form("Where did I meet Sophia?"))
        self.assertTrue(where_form(
            "Where did I get my guitar serviced?"))

    def test_lowercase_start(self):
        self.assertTrue(where_form("where did I park?"))

    def test_mid_question_negative(self):
        self.assertFalse(where_form(
            "Do you remember where I put my keys?"))
        self.assertFalse(where_form(
            "I'm going somewhere; anywhere warm — any tips?"))

    def test_other_families_negative(self):
        self.assertFalse(where_form("What should I do this weekend?"))
        self.assertFalse(where_form(
            "Which happened first, gym or yoga?"))
        self.assertFalse(where_form("How long had I been at Acme?"))
        self.assertFalse(where_form("Who did I meet first, Al or Bo?"))
        self.assertFalse(where_form("What do you remind me I said?"))


class TestLocCandidates(unittest.TestCase):
    def test_proper_run(self):
        sent = "I've been using the Cartwheel app from Target a lot."
        cands = m._where_loc_candidates(sent)
        self.assertIn(("Target", 2), cands)

    def test_multi_token_proper_strength3(self):
        cands = m._where_loc_candidates(
            "I'm planning to stay on Oahu this time.")
        self.assertIn(("Oahu", 2), cands)

    def test_trailing_time_trim(self):
        cands = m._where_loc_candidates(
            "We dined in Little Italy last Sunday.")
        self.assertIn(("Little Italy", 3), cands)

    def test_lowercase_verb_junk_excluded(self):
        # re.I would match "mix up my routine" — case-sensitive
        # proper branch must NOT (Denver regression, sim v2).
        cands = m._where_loc_candidates(
            "I'm thinking of trying spinning to mix up my routine.")
        self.assertEqual(
            [c for c in cands if "routine" in c[0]], [])

    def test_common_noun(self):
        cands = m._where_loc_candidates(
            "My friend Rachel moved back to the suburbs again.")
        self.assertIn(("suburbs", 1), cands)

    def test_singular_place_nouns(self):
        # C533: "cities" was listed but "city" was not — the GT
        # sentence of 3d86fd0a ("For Sophia, it was a coffee shop
        # in the city.") never entered the candidate set.
        cands = m._where_loc_candidates(
            "For Sophia, it was a coffee shop in the city.")
        self.assertIn(("city", 1), cands)
        cands2 = m._where_loc_candidates(
            "We stayed in a town outside the valley.")
        self.assertIn(("town", 1), cands2)


class TestAnswerWhere(unittest.TestCase):
    def _sessions(self):
        return [
            {"session_id": "s1", "turns": [
                turn("assistant",
                     "Sure! What kind of coffee creamer do you like?"),
                turn("user",
                     "I actually redeemed a $5 coupon on coffee "
                     "creamer last Sunday, which was a nice surprise."),
                turn("user",
                     "I've been using the Cartwheel app from Target "
                     "and it's been really helpful."),
            ]},
            {"session_id": "s2", "turns": [
                turn("user", "The weather is nice today."),
            ]},
        ]

    def test_picks_locative_sentence(self):
        ans, detail = answer_where(
            "Where did I redeem a $5 coupon on coffee creamer?",
            self._sessions(), ["n1"], {"n1": {"session_id": "s1"}},
            "[user] I've been using the Cartwheel app from Target "
            "and it's been really helpful.")
        self.assertIsNotNone(ans)
        self.assertIn("Target", ans)

    def test_no_candidates_fallthrough(self):
        ans, detail = answer_where(
            "Where did I park?",
            [{"session_id": "s1", "turns": [
                turn("user", "I like walks.")]}],
            ["n1"], {"n1": {"session_id": "s1"}}, "")
        self.assertIsNone(ans)
        self.assertEqual(detail["cands"], 0)

    def test_unretrieved_session_not_scanned(self):
        # answer lives in s2 but only s1 retrieved -> fall-through
        # (the C472 full-graph lesson does NOT apply — sim v4 A/B)
        ans, _ = answer_where(
            "Where is my guitar?",
            [{"session_id": "s1", "turns": [turn("user", "Hi.")]},
             {"session_id": "s2", "turns": [
                 turn("user", "I got it serviced in Denver.")]},
             ],
            ["n1"], {"n1": {"session_id": "s1"}}, "")
        self.assertIsNone(ans)

    def test_relevance_floor_zero_echo_loses(self):
        # C533: kh=0 locative-dense winner must lose to the best
        # kh>=1 candidate when one exists — the question is the
        # join condition (#086). Replicates 3d86fd0a's shape: the
        # GT-bearing sentence echoes "sophia" but carries a weaker
        # locative than the kh=0 gym-bag distractor.
        sessions = [
            {"session_id": "s1", "turns": [
                turn("user",
                     "I also need to organize my gym bag, which I "
                     "took with me to the gym last week."),
                turn("user",
                     "For Sophia, it was a coffee shop in the city."),
            ]},
        ]
        ans, detail = answer_where(
            "Where did I meet Sophia?", sessions,
            ["n1"], {"n1": {"session_id": "s1"}}, "")
        self.assertIsNotNone(ans)
        self.assertIn("Sophia", ans)
        self.assertTrue(detail["relevance_floor"])

    def test_relevance_floor_no_candidate_untouched(self):
        # kh=0 winner with NO kh>=1 candidate anywhere stays
        # locative-best (the question's vocabulary never recurs).
        sessions = [
            {"session_id": "s1", "turns": [
                turn("user",
                     "I need to organize my gym bag, which I took "
                     "to the gym last week."),
            ]},
        ]
        ans, detail = answer_where(
            "Where did I meet Sophia?", sessions,
            ["n1"], {"n1": {"session_id": "s1"}}, "")
        self.assertIsNotNone(ans)
        self.assertIn("gym", ans)
        self.assertFalse(detail["relevance_floor"])


class TestAdapterGate(unittest.TestCase):
    def _adapter(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([{"session_id": "s1", "messages": [
            {"role": "user",
             "content": "I've been using the Cartwheel app from "
                        "Target and it's been really helpful."},
            {"role": "assistant",
             "content": "That sounds like a great way to save."},
        ]}], session_dates={"s1": "2026-01-10T10:00:00"})
        return a

    def test_gate_fires(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "Where have I been shopping?", "2026-01-15T00:00:00")
        self.assertEqual(meta.get("gate"), "where")
        self.assertIn("Target", ans)

    def test_flag_off_fallthrough(self):
        a = LongMemEvalAdapter(where_loc=False)
        a.ingest_sessions([{"session_id": "s1", "messages": [
            {"role": "user",
             "content": "I've been using the Cartwheel app from "
                        "Target and it's been really helpful."},
        ]}], session_dates={"s1": "2026-01-10T10:00:00"})
        ans, meta = a.answer_extractive(
            "Where have I been shopping?", "2026-01-15T00:00:00")
        self.assertNotEqual(meta.get("gate"), "where")


if __name__ == "__main__":
    unittest.main()
