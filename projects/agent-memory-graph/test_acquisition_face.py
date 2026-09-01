"""Cycle 538: first-person acquisition/conversation statement face.

Answer-gate remainder of the C499 family: message-level ranking
hands the face the top message's FIRST line, which for multi-line
messages is a hand-over opener ("Here's a start - I've bought gifts
for my sister's birthday, my mom…") naming recipients while the
GT acquisition statement ("For my sister's birthday, I got her a
yellow dress…") sits mid-window. Question structure picks the verb
family (what did I buy/complete/get → first-person past acquisition
statements; who did I have a conversation with → "my conversation
with X" statements); tier preference among C501 floor-passers; openers
excluded wherever they sit (C475: prefaces parasitize overlap).
Forensics: /tmp/c538 (66f24dbb, 3f1e9474 — both wrong with openers
as the quoted face, both carry the GT statement in-window).
"""
import unittest

from amg_bench_quality import (
    LongMemEvalAdapter,
    _ACQ_FORM_RE,
    _ACQ_STATEMENT_RE,
    _WHO_CONV_FORM_RE,
    _WHO_CONV_STATEMENT_RE,
    answer_acquisition_face,
)


def turn(role, content):
    return {"role": role, "content": content}


HAY_BUY = [{
    "session_id": "s1",
    "messages": [
        turn("user", "Here's a start - I've bought gifts for my "
                     "sister's birthday, my mom, my neighbor, and "
                     "my brother this year."),
        turn("assistant", "What a thoughtful list! Gift planning "
                          "for family works best when you budget "
                          "per person first."),
        turn("user", "For my sister's birthday, I got her a yellow "
                     "dress and a pair of earrings."),
    ]}]

Q_BUY = "What did I buy for my sister's birthday gift?"

HAY_WHO = [{
    "session_id": "s1",
    "messages": [
        turn("assistant", "The concept of destiny is a popular "
                          "topic. Manifesting destiny through "
                          "positive thinking is widely discussed."),
        turn("user", "I've been thinking about my conversation "
                     "with Sarah, and I wanted to explore the "
                     "concept of destiny a bit more."),
    ]}]

Q_WHO = "Who did I have a conversation with about destiny?"


class TestFormDetection(unittest.TestCase):
    def test_what_buy(self):
        m = _ACQ_FORM_RE.search("What did I buy for my sister's "
                                "birthday gift?")
        self.assertTrue(m and m.group(1).lower() == "buy")

    def test_which_get(self):
        m = _ACQ_FORM_RE.search("Which laptop did I get for "
                                "graduation?")
        self.assertTrue(m and m.group(1).lower() == "get")

    def test_what_complete(self):
        m = _ACQ_FORM_RE.search("What certification did I complete "
                                "last month?")
        self.assertTrue(m and m.group(1).lower() == "complete")

    def test_quantity_form_not_claimed(self):
        self.assertIsNone(_ACQ_FORM_RE.search(
            "How many bikes did I get this year?"))

    def test_non_first_person_not_claimed(self):
        self.assertIsNone(_ACQ_FORM_RE.search(
            "What is the capital of Australia?"))

    def test_who_conversation_form(self):
        self.assertTrue(_WHO_CONV_FORM_RE.search(
            "Who did I have a conversation with about destiny?"))
        self.assertTrue(_WHO_CONV_FORM_RE.search(
            "Who did I talk to about the budget?"))
        self.assertFalse(_WHO_CONV_FORM_RE.search(
            "What did we discuss about destiny?"))


class TestStatementPatterns(unittest.TestCase):
    def test_first_person_past(self):
        for s in ("I got her a yellow dress",
                  "I've bought gifts already",
                  "I completed the course last month",
                  "I have received the package"):
            self.assertTrue(_ACQ_STATEMENT_RE.search(s), s)

    def test_non_past_or_non_first_person(self):
        for s in ("You should get a dress",
                  "I'm getting a dress",
                  "she bought a dress",
                  "Can I get a coffee?"):
            self.assertFalse(_ACQ_STATEMENT_RE.search(s), s)

    def test_who_statement(self):
        self.assertTrue(_WHO_CONV_STATEMENT_RE.search(
            "my conversation with Sarah"))
        self.assertTrue(_WHO_CONV_STATEMENT_RE.search(
            "I talked with Sarah about destiny"))
        self.assertFalse(_WHO_CONV_STATEMENT_RE.search(
            "your conversation with Sarah"))


class TestAcquisitionFace(unittest.TestCase):
    def _answer(self, hay, q, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions(hay)
        return a.answer_extractive(q)

    def test_buy_statement_beats_opener(self):
        ans, meta = self._answer(HAY_BUY, Q_BUY)
        self.assertEqual(meta["gate"], "answer")
        self.assertIn("yellow dress", ans)
        self.assertTrue(meta["acq_face"]["override"])
        self.assertEqual(meta["acq_face"]["kind"], "acq:buy")

    def test_who_conversation_statement(self):
        ans, meta = self._answer(HAY_WHO, Q_WHO)
        self.assertEqual(meta["gate"], "answer")
        self.assertIn("Sarah", ans)
        self.assertTrue(meta["acq_face"]["override"])
        self.assertEqual(meta["acq_face"]["kind"], "who:conversation")

    def test_flag_off_untouched(self):
        ans, meta = self._answer(HAY_BUY, Q_BUY, acq_face=False)
        self.assertNotIn("acq_face", meta)
        self.assertNotIn("yellow dress", ans)

    def test_no_form_no_override(self):
        ans, meta = self._answer(HAY_BUY,
                                 "What is my sister's favorite color?")
        if meta["gate"] == "answer":
            self.assertFalse(meta["acq_face"]["override"])
            self.assertIsNone(meta["acq_face"]["kind"])

    def test_cross_family_statement_excluded(self):
        # complete-question + got-statement: the statement's verb is
        # NOT in the question's family → no tier-1 passer (no
        # cross-family hijack)
        _, detail = answer_acquisition_face(
            "What certification did I complete last month?",
            ["[user] I got her a yellow dress for her birthday "
             "party last weekend"],
            ["certification", "complete", "month"])
        self.assertIsNone(detail.get("override") and True or None)
        self.assertFalse(detail["override"])

    def test_openers_never_picked(self):
        # an opener that matches the statement pattern and clears
        # the floor is still excluded (C475) — no passer → None
        line, detail = answer_acquisition_face(
            "What did I buy for my sister's birthday gift?",
            ["Here's a start - I've bought gifts for my sister's "
             "birthday, my mom, and my brother"],
            ["buy", "sister", "birthday", "gift"])
        self.assertIsNone(line)
        self.assertFalse(detail["override"])

    def test_floor_blocks_lone_keyword_statement(self):
        line, detail = answer_acquisition_face(
            "What did I buy for my sister's birthday gift?",
            ["[user] I got a dress yesterday"],
            ["buy", "sister", "birthday", "gift"])
        self.assertIsNone(line)
        self.assertFalse(detail["override"])


if __name__ == "__main__":
    unittest.main()
