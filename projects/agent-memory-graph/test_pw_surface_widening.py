"""Cycle 494: pairwise anchor-surface widening (29-family residual).

Forensics on the 14 wrong members of the first-family 30q slice
(/tmp/c494/diag.out): 8 one-side-unanchored + 1 sub-24h tie trace
to three deterministic surface gaps — progressive gerunds missing
from the eventive tier, ordinal suffixes breaking _PW_SINCE_RE,
and coarse relative durations ('last summer', 'a few years ago',
'for the past N units') unparseable. Each gap fixed here with a
named regression test mirroring the exact production line.
"""
import unittest

from amg_bench_quality import (
    _pw_kws, _pw_lines, _pw_line_dt, _pw_rel_dt, _pw_scan_anchor,
    answer_pairwise)
from datetime import datetime, timedelta


def turn(role, content):
    return {"role": role, "content": content}


class TestSinceOrdinal(unittest.TestCase):
    """'since February 20th' — ordinal suffix broke the bare
    \\d{1,2}\\b (word char 'th' after digits). gpt4_385a5000."""

    def test_ordinal_suffix_parsed(self):
        dt = _pw_line_dt(datetime(2023, 3, 10, 17, 13),
                         "I've been starting seeds indoors under "
                         "grow lights since February 20th - "
                         "tomatoes are doing well",
                         _pw_kws("the tomatoes"))
        self.assertEqual(dt, datetime(2023, 2, 20))

    def test_plain_day_still_works(self):
        dt = _pw_line_dt(datetime(2023, 4, 15, 10, 0),
                         "thriving since February 20", None)
        self.assertEqual(dt, datetime(2023, 2, 20))


class TestCoarseRelDurations(unittest.TestCase):
    """'last summer' / 'a few years ago' / 'for the past N units'.
    gpt4_d31cdae3 (sub-24h tie on session clocks) + gpt4_5438fa52
    (state-start pull)."""

    DT = datetime(2023, 5, 22, 11, 56)

    def test_last_summer_calendar_anchor(self):
        got = _pw_rel_dt(self.DT,
                         "I was just thinking about my solo trip "
                         "to Europe last summer",
                         _pw_kws("the solo trip to Europe"))
        self.assertEqual(got, datetime(2022, 7, 1))

    def test_a_few_years_ago(self):
        got = _pw_rel_dt(
            datetime(2023, 5, 22, 0, 37),
            "I've been to the Grand Canyon with my family on a "
            "road trip across the American Southwest a few years "
            "ago",
            _pw_kws("the family road trip"))
        self.assertEqual(got, datetime(2023, 5, 22, 0, 37)
                         - timedelta(days=3 * 365))

    def test_for_the_past_months_state_start(self):
        got = _pw_rel_dt(
            datetime(2023, 5, 27, 14, 8),
            "Since I've been taking Spanish classes for the past "
            "three months, I'm curious about cognates",
            _pw_kws("my Spanish classes"))
        self.assertEqual(got, datetime(2023, 5, 27, 14, 8)
                         - timedelta(days=3 * 30))

    def test_for_the_past_numeric(self):
        got = _pw_rel_dt(datetime(2023, 6, 1, 9, 0),
                         "I've been taking piano lessons for the "
                         "past 6 weeks",
                         _pw_kws("the piano lessons"))
        self.assertEqual(got, datetime(2023, 6, 1, 9, 0)
                         - timedelta(days=42))

    def test_clause_gate_still_blocks_anaphora(self):
        # 'a few years ago' in a kw-less clause does not pull
        got = _pw_rel_dt(self.DT,
                         "I started it a few years ago",
                         _pw_kws("the Japanese Zero plane"))
        self.assertEqual(got, self.DT)


class TestProgressiveGerunds(unittest.TestCase):
    """attending/starting/taking are ongoing-PAST reports, not
    plans. gpt4_2487a7cb ('I've been attending workshops') +
    gpt4_5438fa52 ('taking Spanish classes')."""

    def test_attending_anchors_vague_tier(self):
        lines = _pw_lines([
            ("2023/05/24 (Wed) 16:55",
             [turn("user", "I've been attending various workshops "
                           "and lectures, like the workshop on "
                           "'Effective Time Management' last "
                           "Saturday")])])
        kws = _pw_kws("the 'Effective Time Management' workshop")
        a = _pw_scan_anchor(kws, lines, None,
                            ('attend', 'went to', 'participate'))
        self.assertIsNotNone(a)
        self.assertEqual(a[0], datetime(2023, 5, 24, 16, 55))

    def test_taking_with_past_pull_beats_session_clock(self):
        lines = _pw_lines([
            ("2023/05/27 (Sat) 14:08",
             [turn("user", "Since I've been taking Spanish classes "
                           "for the past three months, any tips?")])])
        kws = _pw_kws("my Spanish classes")
        a = _pw_scan_anchor(kws, lines, None, None)
        self.assertIsNotNone(a)
        self.assertEqual(a[0], datetime(2023, 5, 27, 14, 8)
                         - timedelta(days=90))

    def test_planning_progressive_still_vetoed(self):
        lines = _pw_lines([
            ("2023/05/27 (Sat) 14:08",
             [turn("user", "I'm thinking of taking Spanish classes "
                           "next semester")])])
        kws = _pw_kws("my Spanish classes")
        self.assertIsNone(_pw_scan_anchor(kws, lines, None, None))


class TestE2EResidualMembers(unittest.TestCase):
    """End-to-end: the four named residual members resolve."""

    def _dated(self):
        return [
            ("2023/03/25 (Sat) 01:32",
             [turn("user", "I'm familiar with these resources, I "
                           "participated in a webinar on data "
                           "analysis using Python")]),
            ("2023/05/24 (Wed) 16:55",
             [turn("user", "I've been attending various workshops "
                           "and lectures, like the workshop on "
                           "'Effective Time Management' last "
                           "Saturday")]),
        ]

    def test_workshop_vs_webinar(self):
        ans, detail = answer_pairwise(
            "Which event did I attend first, the 'Effective Time "
            "Management' workshop or the 'Data Analysis using "
            "Python' webinar?", self._dated())
        self.assertEqual(ans, "the 'Data Analysis using Python' "
                              "webinar")
        self.assertEqual(detail["mode"], "both")

    def test_summer_vs_few_years_breaks_tie(self):
        d = [
            ("2023/05/22 (Mon) 00:37",
             [turn("user", "I've been to the Grand Canyon with my "
                           "family on a road trip across the "
                           "American Southwest a few years ago")]),
            ("2023/05/22 (Mon) 11:56",
             [turn("user", "I was just thinking about my solo trip "
                           "to Europe last summer")]),
        ]
        ans, detail = answer_pairwise(
            "Which trip did the narrator take first, the solo "
            "trip to Europe or the family road trip across the "
            "American Southwest?", d)
        self.assertEqual(ans, "the family road trip across the "
                              "American Southwest")
        self.assertEqual(detail["mode"], "both")


if __name__ == "__main__":
    unittest.main()
