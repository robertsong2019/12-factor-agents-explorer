"""Cycle 482 tests: in-text adverbial dates + before/since-when forms.

Forensics on the 63 form-missed temporal questions found the two
largest coherent families are calendar-distance forms in disguise:

* ``before`` — "How many days before X did I Y?" (5q) and
  ``since-when`` — "How many days had passed since A when B?" (4q)
  are ``between`` arithmetic with new surface forms;
* the true event lines STATE their dates in text ("attended the
  workshop on January 10th") while the SESSION dates collapse
  both anchors onto one day — day-level truth lives in the line.

Dated NOUNS ("the March 15th issue of The New Yorker") must NOT
engage the in-text date: the issue's date is an entity name, not
the reading event's time (regression guard for the currently-
correct issue-reading question).
"""
import unittest

from amg_bench_quality import (
    LongMemEvalAdapter, _line_adverbial_date, temporal_arith_form)


class TestLineAdverbialDate(unittest.TestCase):
    def test_on_month_day(self):
        self.assertEqual(_line_adverbial_date(
            "I attended the workshop on January 10th, it was great",
            "2023"), "2023-01-10")

    def test_on_abbrev_month_no_ordinal(self):
        self.assertEqual(_line_adverbial_date(
            "we met on Jun 14 for the event", "2023"), "2023-06-14")

    def test_on_the_nth_of_month(self):
        self.assertEqual(_line_adverbial_date(
            "the party is on the 3rd of March", "2023"), "2023-03-03")

    def test_explicit_year_overrides_hint(self):
        self.assertEqual(_line_adverbial_date(
            "I flew out on March 5, 2022 for the trip", "2023"),
            "2022-03-05")

    def test_dated_noun_ignored(self):
        # entity-named date: no preposition "on" directly before it
        self.assertIsNone(_line_adverbial_date(
            "I read the March 15th issue of The New Yorker", "2023"))

    def test_month_year_without_day_ignored(self):
        self.assertIsNone(_line_adverbial_date(
            "since May 2023 I have been running", "2023"))

    def test_no_year_no_hint_returns_none(self):
        self.assertIsNone(_line_adverbial_date(
            "I went on January 10th", ""))

    def test_first_match_wins(self):
        # line mentions two dated events; the FIRST adverbial date
        # is the one adjacent to this line's own event
        self.assertEqual(_line_adverbial_date(
            "on January 10th I started, and I finished on May 2nd",
            "2023"), "2023-01-10")


class TestBeforeSinceWhenForms(unittest.TestCase):
    def test_before_form_is_between(self):
        self.assertEqual(
            temporal_arith_form(
                "How many days before the 'Rack Fest' did I "
                "participate in the 'Turbocharged Tuesdays' event?"),
            ("between", "day",
             "participate in the 'Turbocharged Tuesdays' event",
             "the 'Rack Fest'"))

    def test_before_form_third_person(self):
        self.assertEqual(
            temporal_arith_form(
                "How many months before my anniversary did Rachel "
                "get engaged?")[0:2], ("between", "month"))

    def test_since_when_form(self):
        f = temporal_arith_form(
            "How many days had passed since I finished reading "
            "'The Seven Husbands of Evelyn Hugo' when I attended "
            "the book club meetup?")
        self.assertEqual(f[0:2], ("between", "day"))
        self.assertIn("finished reading", f[2])
        self.assertIn("book club meetup", f[3])

    def test_plain_since_untouched(self):
        f = temporal_arith_form(
            "How many days have passed since I adopted the cat?")
        self.assertEqual(f[0], "since")

    def test_plain_between_untouched(self):
        f = temporal_arith_form(
            "How many days passed between my trip and my return?")
        self.assertEqual(f[0], "between")


class TestInTextDateRescue(unittest.TestCase):
    """Same-session collapses rescued by adverbial dates.

    Mirrors the real 0bb5a684 forensics: workshop (Jan 10) and
    team-meeting prep (Jan 17) both live in the Jan 13 session —
    session dates collapse; the lines' own dates separate them.
    """

    def _adapter(self, sessions, dates, **kw):
        kw.setdefault("max_context_tokens", 4000)
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions(
            [{"session_id": sid, "messages": msgs}
             for sid, msgs in sessions],
            session_dates=dates)
        return a

    def test_same_session_rescued_by_intext_dates(self):
        a = self._adapter(
            [("s1", [
                {"role": "assistant", "content":
                 "Congratulations on taking the initiative! Attending "
                 "the workshop on Effective Communication in the "
                 "Workplace sounds like a great investment."},
                {"role": "user", "content":
                 "I'm glad I attended the workshop on 'Effective "
                 "Communication in the Workplace' on January 10th, "
                 "it really helped my team."},
                {"role": "user", "content":
                 "I'm preparing for the upcoming team meeting on "
                 "January 17th and want to communicate effectively."},
             ])],
            {"s1": "2023/01/13 (Fri) 12:00"})
        ans, meta = a.answer_extractive(
            "How many days before the team meeting I was preparing "
            "for did I attend the workshop on 'Effective "
            "Communication in the Workplace'?", "")
        self.assertEqual(ans, "7 days")
        self.assertEqual(meta["gate"], "temporal_arith")

    def test_first_form_same_session_rescue(self):
        a = self._adapter(
            [("s1", [
                {"role": "user", "content":
                 "I watched the movie Parasite on March 3rd and "
                 "loved it."},
                {"role": "user", "content":
                 "Then I watched Dune on March 9th with my sister."},
             ])],
            {"s1": "2023/03/10 (Fri) 10:00"})
        ans, meta = a.answer_extractive(
            "Which movie did I watch first, Parasite or Dune?", "")
        self.assertIn("Parasite", ans)
        self.assertEqual(meta["gate"], "temporal_arith")

    def test_same_session_no_dates_still_collapses(self):
        # no adverbial dates → day-granularity wall persists →
        # fall-through (C472 semantics preserved)
        a = self._adapter(
            [("s1", [
                {"role": "user", "content":
                 "I watched the movie Parasite and loved it."},
                {"role": "user", "content":
                 "Then I watched Dune with my sister."},
             ])],
            {"s1": "2023/03/10 (Fri) 10:00"})
        ans, meta = a.answer_extractive(
            "Which movie did I watch first, Parasite or Dune?", "")
        self.assertNotEqual(meta.get("gate"), "temporal_arith")

    def test_dated_noun_keeps_session_arithmetic(self):
        # "the March 15th issue" is an entity name — the reading
        # event keeps its session date (no in-text engagement)
        a = self._adapter(
            [("s1", [
                {"role": "user", "content":
                 "I finally read the March 15th issue of The New "
                 "Yorker cover to cover."},
             ])],
            {"s1": "2023/04/01 (Sat) 09:00"})
        ans, meta = a.answer_extractive(
            "How many days ago did I read the March 15th issue of "
            "The New Yorker?", "2023/04/13 (Fri) 12:00")
        self.assertEqual(ans, "12 days")
        self.assertEqual(meta["gate"], "temporal_arith")

    def test_far_future_reminder_line_does_not_hijack_anchor(self):
        # C482 A/B loss gpt4_7a0daae1: a reminder line in a March
        # session mentions "graduation on June 1st" — 76 days out.
        # The far-future in-text date must NOT engage (closeness
        # gate): without the gate the dated line's explicit-date
        # preference wins the anchor and the distance becomes
        # 03-10→06-01 = 12 weeks; with it, the line keeps its
        # March session date and the answer stays 1 week.
        a = self._adapter(
            [("s1", [
                {"role": "assistant", "content":
                 "Congratulations on your new tennis racket! I'm "
                 "sure you'll have a great time trying it out."},
             ]),
             ("s2", [
                {"role": "assistant", "content":
                 "Sure — I'll set up a reminder for Alex's "
                 "graduation on June 1st. Your graduation gift "
                 "delivery is being prepared as well."},
                {"role": "user", "content":
                 "The delivery finally arrived today!"},
             ])],
            {"s1": "2023/03/10 (Fri) 12:00",
             "s2": "2023/03/17 (Fri) 12:00"})
        ans, meta = a.answer_extractive(
            "How many weeks passed between the day I bought my "
            "new tennis racket and the day I received my "
            "graduation delivery?", "")
        self.assertEqual(ans, "1 week")
        self.assertEqual(meta["gate"], "temporal_arith")

    def test_past_recall_date_engages_across_sessions(self):
        # Holi-family (2a1811e2): the festival happened weeks
        # BEFORE the session that recalls it — a past in-text
        # date is later recall and must engage, unlike a future
        # plan. Without past-recall engagement the two anchors
        # collapse onto the recall session's date.
        a = self._adapter(
            [("s1", [
                {"role": "user", "content":
                 "I took some beautiful photos during the Hindu "
                 "festival of Holi on March 7th."},
                {"role": "user", "content":
                 "Then on March 21st, at the Sunday marathon, I "
                 "finally broke 4 hours — so proud of that finish."},
             ])],
            {"s1": "2023/03/28 (Tue) 09:00"})
        ans, meta = a.answer_extractive(
            "How many days had passed between the Hindu festival "
            "of Holi and the Sunday marathon?", "")
        self.assertEqual(ans, "14 days")
        self.assertEqual(meta["gate"], "temporal_arith")


if __name__ == "__main__":
    unittest.main()
