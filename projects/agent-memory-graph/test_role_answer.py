"""Cycle 501: role-aware answer face (echo pathology fix).

User-fact questions ("What color did I repaint my bedroom?",
"How much did I spend on a designer handbag?") are answered by the
best-ranked context line — but assistant advice messages out-hit the
terse user fact statements (they discuss the topic extensively), so
the answer gate echoes advice text ("Mint is a fantastic app…")
while the GT lives in a user line ("I spent $800 on a designer
handbag"). C499 forensics: 257/302 answer-gate questions wrong;
112/116 multi wrongs and 55/56 kupdate wrongs have
answer_session_hit=True — retrieval finds the session, extraction
picks the wrong speaker.

Fix: when the question is a first-person fact question (NOT
you-addressed recall — C468 owns that; NOT advice-request — C498
abstains those) and the top line is an assistant line, re-select the
best USER line when it is keyword-competitive (hits >= top - margin,
floor 2). ssa recall questions, pairwise/ECM/counting/temporal_arith
families are claimed earlier in the chain — untouched by
construction. Gate ORDER is a correctness face (C482/C488).
"""
import unittest

import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, _user_fact_form, exact_judge)


def turn(role, content):
    return {"role": role, "content": content}


HAY = [{
    "session_id": "s1",
    "messages": [
        turn("user", "I just bought a designer handbag for $800 "
                     "from the boutique downtown."),
        turn("assistant", "A designer handbag is a wonderful treat! "
                          "For handbag care, stuff the handbag with "
                          "tissue paper and store the handbag in its "
                          "dust bag to keep the leather supple."),
    ]}]

Q = "How much did I spend on a designer handbag?"


class TestUserFactForm(unittest.TestCase):
    def test_first_person_fact(self):
        self.assertTrue(_user_fact_form(
            "What color did I repaint my bedroom walls?"))

    def test_our_form(self):
        self.assertTrue(_user_fact_form(
            "Where did we go on our most recent family trip?"))

    def test_recall_form_excluded(self):
        # you-addressed recall → C468 speaker-recall path owns it
        self.assertFalse(_user_fact_form(
            "Can you remind me of the name of that restaurant "
            "you recommended in Bandung?"))

    def test_pref_form_excluded(self):
        self.assertFalse(_user_fact_form(
            "I've got some free time tonight, any documentary "
            "recommendations?"))

    def test_no_first_person(self):
        self.assertFalse(_user_fact_form(
            "What is the capital of Australia?"))


class TestRoleAnswerSelection(unittest.TestCase):
    def _answer(self, **kw):
        a = LongMemEvalAdapter(role_answer=True, **kw)
        a.ingest_sessions(HAY)
        return a, a.answer_extractive(Q)

    def test_override_picks_user_fact_line(self):
        _, (ans, meta) = self._answer()
        self.assertEqual(meta["gate"], "answer")
        self.assertIn("$800", ans)
        self.assertTrue(meta.get("role_answer", {}).get("override"))

    def test_switch_off_keeps_assistant_echo(self):
        # quant_rerank=False too: C523 legitimately supersedes this
        # scenario for quantity-form questions (the $800 fact line
        # gets re-ranked in even with role_answer off); isolating
        # C501 requires both flags off
        a = LongMemEvalAdapter(role_answer=False, quant_rerank=False)
        a.ingest_sessions(HAY)
        ans, meta = a.answer_extractive(Q)
        self.assertNotIn("$800", ans)

    def test_no_recall_hijack(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions(HAY)
        q = ("Can you remind me what you said about handbag care "
             "for my designer handbag?")
        ans, meta = a.answer_extractive(q)
        # recall-form questions must never be user-line overridden
        if meta["gate"] == "answer":
            self.assertIsNone(meta.get("role_answer", {}).get("override"))

    def test_floor_blocks_lone_keyword(self):
        # user line shares only ONE keyword with the question and the
        # assistant line discusses the topic heavily → floor 2 keeps
        # the assistant line (no weak-line hijack)
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "My dog ate my homework yesterday."),
                turn("assistant", "Raising a puppy is a joy! For puppy "
                                  "training, use puppy pads and reward "
                                  "the puppy with puppy treats."),
            ]}]
        a = LongMemEvalAdapter()
        a.ingest_sessions(hay)
        ans, meta = a.answer_extractive("How is my puppy doing?")
        self.assertFalse(meta.get("role_answer", {}).get("override", True))

    def test_user_line_outranking_assistant_wins_directly(self):
        # user line has MORE hits than advice → it is already the
        # top line; the rule must not disturb anything
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "I painted my bedroom walls sage green."),
                turn("assistant", "Sage green is calming! It pairs "
                                  "well with wood tones and plants."),
            ]}]
        a = LongMemEvalAdapter(role_margin=0)
        a.ingest_sessions(hay)
        ans, meta = a.answer_extractive(
            "What color did I paint my bedroom walls?")
        self.assertIn("sage green", ans)
        # top line is the user line — no override branch taken
        self.assertNotIn("role_answer", meta)


if __name__ == "__main__":
    unittest.main()
