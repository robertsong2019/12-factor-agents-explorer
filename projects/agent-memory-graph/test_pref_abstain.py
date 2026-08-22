"""Cycle 498: preference honest abstention (Research #080 candidate A).

single-session-preference questions are generation-native: the GT is
a synthesized meta-description ("The user would prefer…"), the
category-entity vocabulary gap makes the retrieval bridge lexically
unreachable (unique-lexical-best 4/30, arm F), and the echo protocol
answers with suggestion text ≠ user profile — a category error, not a
near-miss (correct_llm 1/30 = judge leniency). A zero-LLM pipeline
cannot compose a personalized response → honest abstention instead of
a fabricated echo (C448 entropy-gate abstention推广, third instance).

Census contract (full-500): the gate fires exactly 29/30 preference
questions and ZERO of the other 470 (zero hijack). The one uncovered
question (1d4e3b97, "Could there be a reason for…") is a causal-form
surface — left to the echo path, no regression.
"""
import unittest

import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, pref_form, ABSTAIN_ANSWER)


def turn(role, content):
    return {"role": role, "content": content}


class TestPrefForm(unittest.TestCase):
    def test_recommendation_plural(self):
        self.assertTrue(pref_form(
            "I've got some free time tonight, any documentary recommendations?"))

    def test_suggestion_plural(self):
        self.assertTrue(pref_form(
            "I'm planning a trip to Denver soon. Any suggestions on what to do there?"))

    def test_tips(self):
        self.assertTrue(pref_form(
            "I'm a bit anxious about getting around Tokyo. "
            "Do you have any helpful tips?"))

    def test_what_should(self):
        self.assertTrue(pref_form("What should I do this weekend?"))

    def test_do_you_think(self):
        self.assertTrue(pref_form(
            "I'm trying to decide whether to buy a NAS device now or wait. "
            "What do you think?"))

    def test_advice(self):
        self.assertTrue(pref_form("Do you have any advice on meal prep?"))

    def test_any_ideas(self):
        self.assertTrue(pref_form("Any ideas for the party?"))

    def test_negative_ecm_form(self):
        # "who … first" belongs to C497 ECM — forms mutually exclusive
        self.assertFalse(pref_form(
            "Who did I meet first, Mark and Sarah or Tom?"))

    def test_negative_pairwise_form(self):
        self.assertFalse(pref_form(
            "Which did I finish first, the report or the slides?"))

    def test_negative_factual(self):
        # factual questions must never fire the gate (zero-hijack)
        self.assertFalse(pref_form("Where did I park my car?"))
        self.assertFalse(pref_form(
            "How long did I work at Instacart?"))

    def test_negative_bare_recommendation_in_evidence_form(self):
        # asking ABOUT a recommendation that was MADE is factual recall,
        # not an advice request — phrasing "did you recommend" ≠ request.
        # (No such surface in the 500-question census; documented guard.)
        self.assertFalse(pref_form("What documentary did you recommend last week?"))


class TestAdapterWiring(unittest.TestCase):
    def _ingest(self, adapter):
        sessions = [
            {"session_id": "s1", "messages": [
                turn("user", "I've been thinking about a new documentary "
                             "to watch tonight."),
                turn("assistant", "How about the one about cheese making?"),
            ]},
        ]
        adapter.ingest_sessions(
            sessions, session_dates={"s1": "2023/05/20 (Sat) 09:00"})

    def test_pref_gate_abstains(self):
        adapter = LongMemEvalAdapter()
        self._ingest(adapter)
        ans, meta = adapter.answer_extractive(
            "Any documentary recommendations?",
            question_date="2023/05/21 (Sun) 10:00")
        self.assertEqual(ans, ABSTAIN_ANSWER)
        self.assertEqual(meta["gate"], "pref")
        self.assertTrue(meta["abstained"])
        # retrieval still ran — abstention and retrieval quality are
        # independent axes (C447 design): context is stashable
        self.assertIn("context", meta)

    def test_pref_disable_switch(self):
        adapter = LongMemEvalAdapter(pref_abstain=False)
        self._ingest(adapter)
        ans, meta = adapter.answer_extractive(
            "Any documentary recommendations?",
            question_date="2023/05/21 (Sun) 10:00")
        self.assertNotEqual(meta.get("gate"), "pref")
        self.assertNotEqual(ans, ABSTAIN_ANSWER)

    def test_non_pref_question_untouched(self):
        adapter = LongMemEvalAdapter()
        self._ingest(adapter)
        _, meta = adapter.answer_extractive(
            "What documentary was I thinking about watching?",
            question_date="2023/05/21 (Sun) 10:00")
        self.assertNotEqual(meta.get("gate"), "pref")


class TestRunEvalConfig(unittest.TestCase):
    def test_config_carries_pref_abstain(self):
        import inspect
        self.assertIn("pref_abstain", inspect.signature(m.run_eval).parameters)
        self.assertIn("pref_abstain", inspect.signature(
            LongMemEvalAdapter.__init__).parameters)


if __name__ == "__main__":
    unittest.main()
