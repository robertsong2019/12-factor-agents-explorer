"""C558: relative-advance composition faces (982b5123 family).

A winning anchor line can date its event only RELATIVE to another
event: "... for my best friend's wedding and had to book three
months in advance" — the booking has no absolute date, so the
recency path collapses to the session date (== ask date → "0
months"). The pivot event (the wedding) is dated by a SECOND line
relative to its own session ("been to SF ... exactly two months
ago ... for my best friend's wedding"). Composition: anchor_date =
pivot_session − rel_ago − in_advance → 5 months before the ask.

Census (500 rows, /tmp/c558): exactly ONE row carries an advance
phrase on its winning anchor line (982b5123); the other three
"in advance" rows carry it on losing assistant-advice lines. Pivot
identity = shared content word with haystack document frequency
≤ 5 (wedding df=6, friend's df=3); noise rel-ago lines share only
thematic common words (francisco df=21, great df=108, trip df=46).
Miniatures here prove mechanism structure/ranking; the census
proves the surface.
"""
import os
import sys
import unittest
from datetime import date

if os.environ.get("PYTHONHASHSEED") != "7":
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "PYTHONHASHSEED": "7"})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amg_bench_quality import (answer_temporal_arith, _shift_months,
                               judge_semantic)


Q = "How many months ago did I book the Airbnb in San Francisco?"
QD = "2023/05/21 (Sun) 10:30"

WINNER = ("[user] I'm planning a trip to San Francisco and was wondering "
          "if you could recommend some good neighborhoods to stay in. By "
          "the way, I've had a great experience with Airbnb in the past, "
          "like when I stayed in Haight-Ashbury for my best friend's "
          "wedding and had to book three months in advance.")
PIVOT = ("[user] I'm planning a trip to San Francisco for next month and "
         "I was wondering if you could recommend some good restaurants in "
         "the Haight-Ashbury neighborhood. By the way, I've been to SF "
         "before, exactly two months ago, for my best friend's wedding - "
         "it was a 5-day trip and I had an amazing time.")
FILLER = "[user] I really enjoy hiking on the weekends when the weather is nice."


def _core_lines(extra=()):
    return [(WINNER, "2023-05-21"), (PIVOT, "2023-05-21"),
            (FILLER, "2023-05-21")] + list(extra)


class TestRelativeAdvanceComposition(unittest.TestCase):
    def test_core_composition_face(self):
        # booking = wedding − 3mo = (session − 2mo) − 3mo = 2022-12-21;
        # ask 2023-05-21 → 5 months. Recency path gave "0 months".
        ans, detail = answer_temporal_arith(Q, _core_lines(), QD)
        self.assertEqual(ans, "5 months")
        self.assertTrue(detail.get("compose"))
        self.assertEqual(detail["dates"], ["2022-12-21", "2023-05-21"])

    def test_noise_pivot_loses_on_shared_count(self):
        # A competing rel-ago line sharing only incident words must
        # not outrank the wedding pivot (16 shared words vs noise).
        noise = ("[user] That's a great list! I've also been doing a "
                 "good job of packing snacks lately, like on my flight "
                 "to San Francisco two weeks ago when I got stuck.")
        ans, detail = answer_temporal_arith(
            Q, _core_lines(extra=[(noise, "2023-05-21")]), QD)
        self.assertEqual(ans, "5 months")
        self.assertTrue(detail.get("compose"))

    def test_no_pivot_falls_back_byte_identical(self):
        # Advance phrase but no rel-ago pivot anywhere → the pre-C558
        # recency behavior ("0 months"), no compose key in detail.
        lines = [(WINNER, "2023-05-21"),
                 ("[user] I had dinner at a nice Thai place last night.",
                  "2023-05-21")]
        ans, detail = answer_temporal_arith(Q, lines, QD)
        self.assertEqual(ans, "0 months")
        self.assertNotIn("compose", detail)

    def test_advance_on_losing_line_ignored(self):
        # The advance phrase sits on a line that does NOT win the
        # anchor (5e1b23de shape): absolute-dated winner keeps the
        # plain C482 path.
        lines = [
            ("[user] I attended the photography workshop today and it "
             "was fantastic.", "2024-02-01"),
            ("[assistant] You should book flights three months in "
             "advance for the best fares.", "2024-02-01"),
        ]
        ans, detail = answer_temporal_arith(
            "How many months ago did I attend the photography workshop?",
            lines, "2024/02/01 (Thu) 09:00")
        self.assertEqual(ans, "0 months")
        self.assertNotIn("compose", detail)

    def test_refined_winner_not_composed(self):
        # Winner carries BOTH an absolute date and an advance phrase:
        # the C482 adverbial date wins; composition must not fire.
        winner = ("[user] I stayed in Haight-Ashbury for my best "
                  "friend's wedding — I booked the Airbnb on January "
                  "10th, three months in advance.")
        lines = [(winner, "2023-05-21"), (PIVOT, "2023-05-21")]
        ans, detail = answer_temporal_arith(Q, lines, QD)
        self.assertEqual(ans, "4 months")    # 01-10 → 05-21, month unit
        self.assertNotIn("compose", detail)

    def test_future_anchor_abstains(self):
        # Pivot session far in the future: composed anchor lands
        # after the ask → honest fallback, never negative "ago".
        future_pivot = PIVOT
        lines = [(WINNER, "2023-05-21"),
                 (future_pivot, "2024-01-10")]
        ans, detail = answer_temporal_arith(Q, lines, QD)
        self.assertEqual(ans, "0 months")
        self.assertNotIn("compose", detail)

    def test_since_kind_never_composes(self):
        # The since path owns its pair/recency semantics; an advance
        # phrase on its winner must not hijack it (b46e15ed guard).
        q = ("How many months have passed since I attended my book "
             "club?")
        lines = [("[user] I attended my book club recently and we "
                  "discussed the ending — I had finished the novel "
                  "two months in advance.", "2023-05-21")]
        ans, detail = answer_temporal_arith(q, lines, QD)
        self.assertEqual(ans, "0 months")
        self.assertNotIn("compose", detail)

    def test_word_and_digit_numbers(self):
        # Digits in the advance phrase, number words in the pivot.
        winner = WINNER.replace("three months in advance",
                                "3 months in advance")
        lines = [(winner, "2023-05-21"), (PIVOT, "2023-05-21")]
        ans, _ = answer_temporal_arith(Q, lines, QD)
        self.assertEqual(ans, "5 months")

    def test_unit_mix_week_day(self):
        # Advance in weeks, pivot rel in days, question in days:
        # anchor = 2023-05-21 − 3d − 14d = 2023-05-04 → 17 days.
        q = "How many days ago did I book the photographer?"
        winner = ("[user] I booked the photographer for the reunion "
                  "two weeks in advance after we picked the venue.")
        pivot = ("[user] We picked the venue three days ago at the "
                 "community hall — great acoustics.")
        lines = [(winner, "2023-05-21"), (pivot, "2023-05-21")]
        ans, detail = answer_temporal_arith(q, lines, QD)
        self.assertEqual(ans, "17 days")
        self.assertEqual(detail["dates"], ["2023-05-04", "2023-05-21"])

    def test_shift_months_clamp(self):
        self.assertEqual(_shift_months(date(2023, 3, 31), -1),
                         date(2023, 2, 28))
        self.assertEqual(_shift_months(date(2024, 3, 31), -1),
                         date(2024, 2, 29))          # leap year
        self.assertEqual(_shift_months(date(2023, 1, 31), -1),
                         date(2022, 12, 31))
        self.assertEqual(_shift_months(date(2023, 3, 21), -3),
                         date(2022, 12, 21))
        self.assertEqual(_shift_months(date(2023, 5, 21), -5),
                         date(2022, 12, 21))

    def test_judge_five_months_face(self):
        # The rescue only banks if the judge folds "5 months" onto
        # the annotator's word-form reference.
        self.assertEqual(judge_semantic(Q, "5 months", "Five months ago"),
                         "CORRECT")
        self.assertEqual(judge_semantic(Q, "0 months", "Five months ago"),
                         "WRONG")


if __name__ == "__main__":
    unittest.main()
