"""C557: multi-date proximity + consecutive-pair anchor faces.

Two anchor-selection repairs on the temporal span/since paths:
1. A retrieved line can carry TWO in-text dates (one per event it
   narrates); leftmost resolution dates the anchor to the WRONG
   event. The gated candidate nearest the anchor's keyword cluster
   wins (dcfa8644: "sneakers ... on February 1st ... shoelaces on
   my old Converse sneakers had broken on January 24th" — the
   realized-shoelaces anchor must date 01-24; leftmost gave 02-01
   → span 22 vs GT 14).
2. A "since" anchor describing two events "in a row, on
   consecutive days" asserts a temporal RELATION — the anchor is
   the pair's completion date, not the most recent lone event
   (b46e15ed: pair = 02-14 ride + 02-15 book drive; the recency
   ladder anchored the 03-19 walk → '1 month' vs GT 2).
"""
import os
import sys
import unittest

if os.environ.get("PYTHONHASHSEED") != "7":
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "PYTHONHASHSEED": "7"})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amg_bench_quality import (answer_temporal_arith, _line_eff_date,
                               temporal_arith_form)


class TestMultiDateProximity(unittest.TestCase):
    Q = ("How many days had passed since I bought my Adidas running "
         "shoes when I realized one of the shoelaces on my old "
         "Converse sneakers had broken?")

    LINES = [
        ("[user] I'm looking for some shoe cleaning tips. I've got a "
         "pair of sneakers that I wore to play basketball on February "
         "1st and they got pretty dirty. By the way, speaking of "
         "shoes, I realized that one of the shoelaces on my old "
         "Converse sneakers had broken on January 24th, so I had to "
         "replace it.", "2023-02-03"),
        ("[user] I recently got a new pair of Adidas running shoes on "
         "January 10th, and I want to make sure I take good care of "
         "them.", "2023-02-03"),
        ("[user] My sister and I had a great time at the outlet mall "
         "on January 10th when I bought my new Adidas running shoes.",
         "2023-02-03"),
    ]

    def test_span_dates_second_event(self):
        # GT 14 = 01-24 (Converse realization) minus 01-10 (purchase);
        # leftmost in-text resolution anchored 02-01 → 22.
        ans, detail = answer_temporal_arith(self.Q, self.LINES,
                                            "2023/02/03 (Fri) 17:43")
        self.assertEqual(ans, "14 days")
        self.assertEqual(detail["dates"], ["2023-01-10", "2023-01-24"])

    def test_helper_single_date_is_leftmost(self):
        line = ("[user] I got a new pair of Adidas running shoes on "
                "January 10th and love them")
        self.assertEqual(_line_eff_date(line, "2023-02-03", ""),
                         "2023-01-10")

    def test_helper_tie_without_keywords_is_leftmost(self):
        line = ("[user] I visited the store on March 4th and returned "
                "on March 9th")
        self.assertEqual(_line_eff_date(line, "2023-03-10", ""),
                         "2023-03-04")

    def test_gate_excludes_far_future_second_date(self):
        # The second in-text date is a far-future plan relative to
        # its session → C482 gate excludes it even though the anchor
        # keywords sit right next to it.
        line = ("[user] I bought my running shoes on January 10th and "
                "I keep planning my marathon trip on June 1st for the "
                "shoes")
        self.assertEqual(_line_eff_date(line, "2023-02-03", "",
                                        ["shoes", "bought"]),
                         "2023-01-10")

    def test_single_date_lines_byte_identical(self):
        # Miniature with only single-date lines: the C557 path must
        # reproduce the plain C482 resolution.
        q = ("How many days had passed since I bought my desk when I "
             "repainted my office?")
        lines = [
            ("[user] I bought my desk on January 5th", "2023-02-03"),
            ("[user] I repainted my office on January 20th",
             "2023-02-03"),
        ]
        ans, _ = answer_temporal_arith(q, lines, "2023/02/03 (Fri) 10:00")
        self.assertEqual(ans, "15 days")


class TestConsecutivePairAnchor(unittest.TestCase):
    Q = ("How many months have passed since I participated in two "
         "charity events in a row, on consecutive days?")

    LINES = [
        ("[user] I attended a charity gala organized by the Cancer "
         "Research Foundation today", "2023-01-30"),
        ("[user] I'm feeling a bit tired today, just got back from "
         "the '24-Hour Bike Ride' charity event", "2023-02-14"),
        ("[user] I volunteered at the 'Books for Kids' charity book "
         "drive event today", "2023-02-15"),
        ("[user] I watched the awards from the front row of the "
         "'Walk for Hunger' charity event today. I've been doing a "
         "lot of charity events lately", "2023-03-19"),
    ]

    def test_pair_completion_is_anchor(self):
        # Pair = 02-14 + 02-15 (adjacent days); the walk (03-19) is
        # the lexically dominant single event (front row / charity
        # events -> 3 distinctive hits, see test_ago_kind_not_refined)
        # but NOT part of a pair. Without the refinement this anchor
        # would answer '1 month' (same as the ago face below).
        ans, detail = answer_temporal_arith(self.Q, self.LINES,
                                            "2023/04/18 (Tue) 03:31")
        self.assertEqual(ans, "2 months")
        self.assertEqual(detail["dates"][0], "2023-02-15")

    def test_consecutive_marker_alone_triggers(self):
        q = ("How many months have passed since I participated in "
             "two charity events on consecutive days?")
        ans, detail = answer_temporal_arith(q, self.LINES,
                                            "2023/04/18 (Tue) 03:31")
        self.assertEqual(ans, "2 months")
        self.assertEqual(detail["dates"][0], "2023-02-15")

    def test_no_pair_falls_back_to_recency(self):
        # Remove the 02-15 line: no Δ1 pair exists → the pre-C557
        # recency anchor (03-19) stays (graceful degradation).
        lines = [l for l in self.LINES if "Books for Kids" not in l[0]]
        ans, detail = answer_temporal_arith(self.Q, lines,
                                            "2023/04/18 (Tue) 03:31")
        self.assertEqual(ans, "1 month")
        self.assertEqual(detail["dates"][0], "2023-03-19")

    def test_pair_end_after_ask_falls_back_then_abstains(self):
        # The pair completes AFTER the ask → refinement declines;
        # the retained recency anchor (03-19) then exceeds the ask
        # date and the honesty guard abstains.
        ans, _ = answer_temporal_arith(self.Q, self.LINES,
                                       "2023/02/14 (Tue) 08:00")
        self.assertIsNone(ans)

    def test_ago_kind_not_refined(self):
        q = ("How many months ago did I participate in charity "
             "events in a row?")
        ans, detail = answer_temporal_arith(q, self.LINES,
                                            "2023/04/18 (Tue) 03:31")
        self.assertEqual(ans, "1 month")
        self.assertEqual(detail["dates"][0], "2023-03-19")


if __name__ == "__main__":
    unittest.main()
