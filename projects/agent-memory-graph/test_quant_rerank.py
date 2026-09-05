"""Cycle 523: quantity-form answer-face re-rank (#090).

Census (official C522 post_full500.json): 220/500 questions match
^how (many|long|much); 103 reach the answer gate — 81 wrong, 42 with
retrieval_hit AND answer_session_hit True: the GT number IS in the
window but the quoted face is a number-free adjacent message (C499
echo pathology, quantity subtype — c960da58 Spotify "20",
94f70d80 IKEA "4 hours", af8d2e46 "7 shirts", 6b168ec8 "three
bikes").

Fix: quantity-form questions whose TOP line carries NO quantity
token re-rank to the number-bearing USER line with the most keyword
evidence (floor 2, C501 floor). Strict scope: a top line that
already quotes a number is untouched (correct numeric answers keep
their face by construction); no qualifying candidate → fall through
untouched (C488). Line iteration order is (-hits, -seq): strict `>`
on hits keeps the EARLIEST matching entry on ties — the LATEST
message, the knowledge-update recency convention (C437/C447).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, _quantity_form, _QUANTITY_TOKEN_RE)


def turn(role, content):
    return {"role": role, "content": content}


# 94f70d80 shape: advice reuses 3 topic words, the terse fact line 2
# (assemble/bookshelf vs assemble/IKEA/bookshelf) → C501 cannot fire
# (2 < 3 - margin), C523 must.
HAY = [{
    "session_id": "s1",
    "messages": [
        turn("user", "Finally done! It took me about 4 hours to "
                     "assemble the bookshelf."),
        turn("assistant", "Assembling IKEA furniture is easier with "
                          "a plan! When you assemble the bookshelf, "
                          "lay out all parts first. IKEA instructions "
                          "are pictorial, so assemble on a clean floor "
                          "and keep the IKEA manual handy."),
    ]}]

Q = "How long did it take me to assemble the IKEA bookshelf?"


class TestQuantityForm(unittest.TestCase):
    def test_how_many(self):
        self.assertTrue(_quantity_form(
            "How many playlists do I have on Spotify?"))

    def test_how_long(self):
        self.assertTrue(_quantity_form(
            "How long have I been living in my current apartment?"))

    def test_how_much(self):
        self.assertTrue(_quantity_form(
            "How much did I spend on a designer handbag?"))

    def test_not_quantity(self):
        self.assertFalse(_quantity_form(
            "What color did I repaint my bedroom walls?"))
        self.assertFalse(_quantity_form(
            "Where did I buy the bookshelf?"))

    def test_token_regex_cardinals_only(self):
        self.assertTrue(_QUANTITY_TOKEN_RE.search("about 4 hours"))
        self.assertTrue(_QUANTITY_TOKEN_RE.search("three bikes"))
        self.assertTrue(_QUANTITY_TOKEN_RE.search("$800"))
        # advice-frequent non-cardinals must NOT count as quantities
        self.assertFalse(_QUANTITY_TOKEN_RE.search(
            "once you set it up, it doubles in value"))
        self.assertFalse(_QUANTITY_TOKEN_RE.search(
            "a couple of tips, half the work"))


class TestQuantRerank(unittest.TestCase):
    def _answer(self, hay=HAY, q=Q, **kw):
        a = LongMemEvalAdapter(quant_rerank=True, **kw)
        a.ingest_sessions(hay)
        return a.answer_extractive(q)

    def test_reorder_picks_number_bearing_user_line(self):
        ans, meta = self._answer()
        self.assertEqual(meta["gate"], "answer")
        self.assertIn("4 hours", ans)
        self.assertTrue(meta["quant_rerank"]["override"])

    def test_switch_off_keeps_advice_echo(self):
        a = LongMemEvalAdapter(quant_rerank=False)
        a.ingest_sessions(HAY)
        ans, meta = a.answer_extractive(Q)
        self.assertNotIn("4 hours", ans)
        self.assertNotIn("quant_rerank", meta)

    def test_top_with_number_untouched(self):
        # a2f3aa27 shape: the top line already quotes A number —
        # guard must not enter the block at all (latest-number-wins
        # is a different, riskier intervention; out of C523 scope)
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "I have around 20 playlists now."),
                turn("assistant", "Spotify playlists: even 50 "
                                  "playlists won't slow Spotify down; "
                                  "sort your playlists into folders."),
            ]}]
        ans, meta = self._answer(
            hay=hay, counting=False,
            q="How many playlists do I have on Spotify?")
        # C550: counting=False because this question is enum_count-
        # claimable and the user turn carries a digit statement
        # ("around 20 playlists") — at the production default the
        # qty-stated face now answers "20" (user fact over assistant
        # echo; see test_qty_stated_face). counting=False keeps this
        # test pinned to the C523 top-with-number guard no-op.
        self.assertNotIn("quant_rerank", meta)
        self.assertIn("50", ans)

    def test_no_candidate_falls_through(self):
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "The bookshelf took forever, honestly."),
                turn("assistant", "Assembling IKEA furniture is "
                                  "easier with a plan! When you "
                                  "assemble the bookshelf, lay out all "
                                  "parts first. IKEA instructions are "
                                  "pictorial, so assemble on a clean "
                                  "floor and keep the IKEA manual "
                                  "handy."),
            ]}]
        ans, meta = self._answer(hay=hay)
        self.assertFalse(meta["quant_rerank"]["override"])
        self.assertNotIn("4 hours", ans)

    def test_floor_blocks_number_free_line(self):
        # number-bearing candidate shares < 2 keywords with the
        # question → floor keeps the advice face (no weak hijack)
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "I counted 14 red ones yesterday."),
                turn("assistant", "Tomatoes thrive when you harvest "
                                  "them in the morning; garden "
                                  "tomatoes also need consistent "
                                  "watering through summer, and "
                                  "harvest often."),
            ]}]
        ans, meta = self._answer(
            hay=hay,
            q="How many tomatoes did I harvest from my garden?")
        self.assertFalse(meta["quant_rerank"]["override"])
        self.assertIn("Tomatoes", ans)

    def test_non_quantity_question_untouched(self):
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "I painted my kitchen navy blue."),
                turn("assistant", "Navy blue kitchens look great! "
                                  "Navy pairs well with brass "
                                  "hardware in a kitchen."),
            ]}]
        ans, meta = self._answer(
            hay=hay, q="What color did I paint my kitchen?")
        self.assertNotIn("quant_rerank", meta)

    def test_recency_tiebreak_latest_message_wins(self):
        # two number-bearing user lines with equal hits: strict `>`
        # keeps the first in ranked (-hits, -seq) order → the LATEST
        # C550: this question is enum_count-claimable, so at the
        # production default (counting=True) the qty-stated face now
        # answers it at the counting gate with the same recency
        # semantics (test_qty_stated_face.test_recency_latest_wins
        # pins that pathway). counting=False keeps THIS test pinned
        # to the quant_rerank mechanism it exists to test.
        hay = [{
            "session_id": "s1",
            "messages": [
                turn("user", "I hit 1250 followers on Instagram "
                             "for my food posts!"),
                turn("user", "Update: 1300 followers on Instagram "
                             "for my food posts now!"),
                turn("assistant", "Your Instagram food account "
                                  "followers will love consistent "
                                  "posting — Instagram and food "
                                  "content grow the account fast."),
            ]}]
        ans, meta = self._answer(
            hay=hay, counting=False,
            q="How many followers do I have on my Instagram "
              "food account?")
        self.assertTrue(meta["quant_rerank"]["override"])
        self.assertIn("1300", ans)
        self.assertNotIn("1250", ans)


if __name__ == "__main__":
    unittest.main()
