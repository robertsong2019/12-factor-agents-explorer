"""C556: ago_when span faces — "how many days ago did I X when I Y".

The annotator's value is the X→Y event span, not the ask-to-event
distance (census: the only two ago+when members in the full 500 —
eac54adc 19 = 03-01 contract minus 02-10 launch; 9a707b81 21 =
04-10 cake minus 03-20 class, where the class line says
"yesterday"; qd-anchored arithmetic gives 24/25 and misses both).
"""
import os
import sys
import unittest

if os.environ.get("PYTHONHASHSEED") != "7":
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "PYTHONHASHSEED": "7"})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amg_bench_quality import (answer_temporal_arith, temporal_arith_form,
                               temporal_arith_judge)


class TestAgoWhenForm(unittest.TestCase):
    def test_when_clause_splits(self):
        kind, unit, a, b = temporal_arith_form(
            "How many days ago did I launch my website when I signed "
            "a contract with my first client?")
        self.assertEqual(kind, "ago_when")
        self.assertEqual(unit, "day")
        self.assertEqual(a, "launch my website")
        self.assertEqual(b, "signed a contract with my first client")

    def test_plain_ago_unchanged(self):
        kind, unit, a, b = temporal_arith_form(
            "How many days ago did I visit Paris?")
        self.assertEqual(kind, "ago")
        self.assertIsNone(b)
        self.assertEqual(a, "visit Paris")

    def test_whenever_does_not_split(self):
        # "when" must be whitespace-delimited to split the anchors.
        kind, _, _, _ = temporal_arith_form(
            "How many days ago did I smile whenever I got the package?")
        self.assertEqual(kind, "ago")

    def test_ago_when_two_units(self):
        kind, unit, a, b = temporal_arith_form(
            "How many weeks ago did I adopt the cat when I moved "
            "apartments?")
        self.assertEqual(kind, "ago_when")
        self.assertEqual(unit, "week")


class TestAgoWhenSpan(unittest.TestCase):
    Q = ("How many days ago did I launch my website when I signed "
         "a contract with my first client?")

    LINES = [
        ("[user] I want to make sure my posts look good. By the way, "
         "I just launched my website and created a business plan "
         "outline for my design studio", "2023-02-10"),
        ("[user] Hello, GPT. We are launching a service that lets "
         "people reach us on WhatsApp. The website campaigns have "
         "been more successful so far", "2023-02-20"),
        ("[user] I just signed a contract with my first client today "
         "and want solid templates", "2023-03-01"),
        ("[assistant] Congratulations on landing your first client!",
         "2023-03-01"),
    ]

    def test_span_not_qd_distance(self):
        # ask date 2023-03-25: qd-anchored launch resolution gave
        # 24; the span 03-01 minus 02-10 = 19 is the GT value.
        ans, detail = answer_temporal_arith(self.Q, self.LINES,
                                            "2023/03/25 (Sat) 19:57")
        self.assertEqual(ans, "19 days")
        self.assertEqual(detail["dates"], ["2023-02-10", "2023-03-01"])
        self.assertEqual(detail["value"], 19)
        self.assertTrue(detail["span"])

    def test_possessive_tiebreak_beats_tangent(self):
        # Without the possessive slot the WhatGPT tangent (02-20)
        # wins the future/past keys and the span collapses to 9.
        ans, detail = answer_temporal_arith(self.Q, self.LINES,
                                            "2023/03/25 (Sat) 19:57")
        self.assertEqual(detail["dates"][0], "2023-02-10")

    def test_yesterday_shift(self):
        q = ("How many days ago did I attend a baking class at a "
             "local culinary school when I made my friend's birthday "
             "cake?")
        lines = [
            ("[user] obsessed with strawberries after that amazing "
             "baking class I took at a local culinary school yesterday",
             "2022-03-21"),
            ("[user] I just baked a chocolate cake for my friend's "
             "birthday party today", "2022-04-10"),
        ]
        ans, detail = answer_temporal_arith(
            q, lines, "2022/04/15 (Fri) 18:46")
        self.assertEqual(ans, "21 days")
        self.assertEqual(detail["dates"], ["2022-03-20", "2022-04-10"])

    def test_explicit_date_beats_yesterday_word(self):
        # An explicit adverbial date outranks the relative word.
        q = ("How many days ago did I join the pottery studio when I "
             "bought my wheel?")
        lines = [
            ("[user] I joined the pottery studio on March 5th and "
             "love the classes there", "2023-03-21"),
            ("[user] I bought my wheel yesterday for the studio work",
             "2023-03-20"),
        ]
        ans, _ = answer_temporal_arith(q, lines,
                                       "2023/03/25 (Sat) 10:00")
        # explicit 03-05 join wins on the X anchor; the wheel line's
        # "yesterday" shifts 03-20 → 03-19 → span 14.
        self.assertEqual(ans, "14 days")

    def test_unresolved_when_anchor_abstains(self):
        # Honesty contract: Y clause with no dated evidence →
        # abstain; never fall back to qd-anchored single-anchor.
        lines = [("[user] I just launched my website last month",
                  "2023-02-10")]
        ans, detail = answer_temporal_arith(self.Q, lines,
                                            "2023/03/25 (Sat) 19:57")
        self.assertIsNone(ans)
        self.assertEqual(detail["anchors"], [True, False])

    def test_same_date_abstains(self):
        q = ("How many days ago did I launch my website when I signed "
             "a contract with my first client?")
        lines = [("[user] I launched my website and signed the "
                  "contract the same day", "2023-03-01")]
        ans, _ = answer_temporal_arith(q, lines,
                                       "2023/03/25 (Sat) 19:57")
        self.assertIsNone(ans)


class TestAgoWhenJudge(unittest.TestCase):
    def test_dataset_alt_values_accepted(self):
        gt = ("19 days ago. 20 days (including the last day) is also "
              "acceptable.")
        self.assertTrue(temporal_arith_judge(
            "How many days ago did I launch my website when I signed "
            "a contract with my first client?", gt, "19 days"))
        self.assertTrue(temporal_arith_judge(
            "How many days ago did I launch my website when I signed "
            "a contract with my first client?", gt, "20 days"))
        self.assertFalse(temporal_arith_judge(
            "How many days ago did I launch my website when I signed "
            "a contract with my first client?", gt, "24 days"))


if __name__ == "__main__":
    unittest.main()
