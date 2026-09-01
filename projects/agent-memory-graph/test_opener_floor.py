"""Cycle 539: opener demotion floor for the answer gate.

C539 census: 16/16 GT-in-window answer-gate rows had a hand-over/
acknowledgment opener as the quoted winner while the GT-bearing
line sat same-band below (the C475 parasitism at its extreme).
Naive same-kh demotion KILLS 5 banked rows — opener lines there
CONTINUE into the answer (multi-sentence first-line quoting), so
the floor demands a candidate that is strictly richer in question
evidence AND a first-person personal statement. Forensics:
/tmp/c539/floor_sim.json (70 handover winners; strict> subset = 14
replacements, 1 rescue 0 kills; statement guard prunes the two
exact-masked degradations 7527f7e2/7401057b).
"""
import unittest

from amg_bench_quality import (
    _keyword_hits,
    _keywords,
    _OPENER_ASK_RE,
    _OPENER_FLOOR_STMT_RE,
    _OPENER_HANDOVER_RE,
    answer_opener_floor,
)


def L(role, body):
    return f"[{role}] {body}"


KW = _keywords("How much did I pay for the shirt I lost?")

WINNER = L("user", "I'm thinking of expanding my little farm and "
                   "getting a few more chickens. Can you help me "
                   "find some tips for the shirt budget?")
GT_LINE = L("user", "I'll definitely ask Sarah if she's seen the "
                    "shirt, and I'll check my car and bags too. And "
                    "I did pay $120 for it at the outlet store.")
LIST_LINE = L("assistant", "3. **Art Festivals and Fairs:** Attend "
                           "local art festivals and markets to "
                           "discover the shirt styles you want.")
LECTURE_LINE = L("assistant", "The number of free nights you can "
                              "redeem depends on your shirt points "
                              "balance and membership tier.")


class TestHandoverRE(unittest.TestCase):
    def test_ack_shapes(self):
        for s in ("That's great to hear! Two hours a day...",
                  "Sure, here are some popular stores:",
                  "I think there's been a misunderstanding!",
                  "Of course! Let me walk you through it."):
            self.assertTrue(_OPENER_HANDOVER_RE.match(s), s)

    def test_ask_shapes(self):
        for s in ("I'm looking to improve my guitar playing and was "
                  "wondering if you could recommend some resources.",
                  "Can you help me find some budgeting apps?",
                  "Do you have any tips for meal prep?"):
            self.assertTrue(_OPENER_ASK_RE.search(s[:200]), s)

    def test_content_openers_not_matched(self):
        # answer-bearing continuation openers must NOT fire the
        # floor on the winner side (the 5-kill shape family)
        for s in ("I graduated with a degree in Business "
                  "Administration, which helped my career.",
                  "I'm planning a trip to Europe in November and "
                  "considering hotels in Paris with an Eiffel "
                  "Tower view."):
            self.assertFalse(_OPENER_HANDOVER_RE.match(s), s)


class TestStmtGuard(unittest.TestCase):
    def test_personal_statements_pass(self):
        for s in ("I'll definitely ask Sarah if she's seen it.",
                  "I've been reading a lot lately.",
                  "I paid $120 for it.",
                  "By the way, I've been reading that book too."):
            self.assertTrue(_OPENER_FLOOR_STMT_RE.match(s), s)

    def test_meta_and_lists_rejected(self):
        for s in ("3. **Art Festivals and Fairs:** Attend local "
                  "art festivals.",
                  "Now, about that designer handbag... $800 is a "
                  "significant expense.",
                  "The number of free nights you can redeem "
                  "depends on points.",
                  "Using Trello for academic projects can be "
                  "incredibly beneficial."):
            self.assertFalse(_OPENER_FLOOR_STMT_RE.match(s), s)


class TestFloor(unittest.TestCase):
    def test_fires_on_strict_statement(self):
        line, d = answer_opener_floor(
            WINNER, [WINNER, LIST_LINE, GT_LINE], KW)
        self.assertTrue(d["fired"])
        self.assertEqual(line, GT_LINE)
        self.assertGreater(d["rep_kh"], d["win_kh"])

    def test_no_fire_on_content_winner(self):
        content = L("user", "I paid $120 for the shirt at the "
                            "outlet store last weekend.")
        line, d = answer_opener_floor(
            content, [content, GT_LINE], KW)
        self.assertFalse(d["fired"])
        self.assertIsNone(line)

    def test_equal_kh_never_demotes(self):
        # the 5-kill shape: candidate ties the winner on evidence
        eq = L("user", "I was wondering if the shirt is still on "
                       "sale this week at the outlet store.")
        cand = L("user", "I remember the shirt costing quite a bit "
                         "at that store nearby.")
        line, d = answer_opener_floor(eq, [eq, cand], KW)
        self.assertFalse(d["fired"])

    def test_list_and_lecture_candidates_rejected(self):
        line, d = answer_opener_floor(
            WINNER, [WINNER, LIST_LINE, LECTURE_LINE], KW)
        self.assertFalse(d["fired"])

    def test_no_candidates_untouched(self):
        line, d = answer_opener_floor(WINNER, [WINNER], KW)
        self.assertFalse(d["fired"])
        self.assertIsNone(line)

    def test_preamble_candidates_skipped(self):
        pre = L("assistant", "Sure, here are some shirt pricing "
                             "resources you can check out right "
                             "now for your search.")
        line, d = answer_opener_floor(
            WINNER, [WINNER, pre, GT_LINE], KW)
        self.assertTrue(d["fired"])
        self.assertEqual(line, GT_LINE)


if __name__ == "__main__":
    unittest.main()
