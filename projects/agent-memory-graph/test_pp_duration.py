"""Cycle 486: past-perfect duration forms — #077 production port.

"How long had I been <state> when/before <event>?" answered by
anchoring every duration expression ("N units ago" / "for N units
now") to the absolute date of its containing session, then calendar
subtraction. Prototype 7/7 on the full-500 population (baseline
0/7); strict form gate zero-hijack by census (#077).
"""

import unittest

from amg_bench_quality import (
    ABSTAIN_ANSWER, LongMemEvalAdapter, answer_pp_duration,
    pp_duration_form, pp_duration_judge, _pp_dur_exprs, _pp_render,
)

# ── fixture: two-anchor ago arithmetic (Book Lovers shape) ────────
BOOK_Q = ("How long had I been a member of Book Lovers Unite "
          "when the first meetup happened?")
BOOK_SESSIONS = [
    ("2023-05-28", [
        {"role": "user", "content": (
            "I joined Book Lovers Unite three weeks ago. Excited "
            "to finally be a member!")},
        {"role": "assistant", "content": (
            "Welcome! How did you hear about the club?")},
        {"role": "user", "content": (
            "The first meetup happened last week and it was "
            "wonderful.")},
    ]),
]

# ── fixture: now-type state + ago event (guitar/amp shape) ────────
GUITAR_Q = ("How long have I been taking guitar lessons "
            "when I bought the amp?")
GUITAR_SESSIONS = [
    ("2023-05-25", [
        {"role": "user", "content": (
            "I have been taking guitar lessons for six weeks now. "
            "Loving every minute of it.")},
        {"role": "user", "content": (
            "I bought the amp two weeks ago for my birthday.")},
    ]),
]

# ── fixture: cross-exclusion (shared phrase on one line) ──────────
BIRD_Q = "How long had I been bird watching when the workshop took place?"
BIRD_SESSIONS = [
    ("2023-05-21", [
        {"role": "user", "content": (
            "The bird watching workshop took place a month ago.")},
    ]),
    ("2023-05-22", [
        {"role": "user", "content": (
            "I have been bird watching for about three months now.")},
    ]),
]

# ── fixture: nested tenure (before-current-job shape) ─────────────
NOVATECH_Q = ("How long had I been working before I started my "
              "current job at NovaTech?")
TENURE_SESSIONS = [
    ("2023-05-25", [
        {"role": "user", "content": (
            "I have been working professionally for 9 years now.")},
    ]),
    ("2023-05-26", [
        {"role": "user", "content": (
            "I have been working at my job at NovaTech for "
            "4 years and 3 months now.")},
    ]),
]
GOOGLE_Q = ("How long had I been working before I started my "
            "current job at Google?")


class TestPPDurationFormDetector(unittest.TestCase):
    def test_had_when(self):
        self.assertTrue(pp_duration_form(BOOK_Q))

    def test_have_when(self):
        self.assertTrue(pp_duration_form(GUITAR_Q))

    def test_did_before(self):
        self.assertTrue(pp_duration_form(
            "How long did I use the binoculars before "
            "I switched to the telescope?"))

    def test_pure_tenure_rejected(self):
        # no when/before clause — v2 tenure route territory (#077)
        self.assertFalse(pp_duration_form(
            "How long have I been using my Fitbit?"))

    def test_event_duration_rejected(self):
        # "how long did it take" carries no when/before clause
        self.assertFalse(pp_duration_form(
            "How long did it take you to finish the book?"))

    def test_how_many_rejected(self):
        self.assertFalse(pp_duration_form(
            "How many days did I spend in Japan?"))

    def test_plain_question_rejected(self):
        self.assertFalse(pp_duration_form(
            "What is the name of my favorite author?"))


class TestPPDurExprs(unittest.TestCase):
    def _one(self, line):
        exprs = list(_pp_dur_exprs(line))
        self.assertEqual(len(exprs), 1, exprs)
        return exprs[0]

    def test_numeric_ago(self):
        self.assertEqual(self._one("joined three weeks ago"),
                         ("ago", 3, "week", "three weeks ago"))

    def test_word_article_ago(self):
        self.assertEqual(self._one("got it a month ago")[1:3],
                         (1, "month"))

    def test_about_hedge(self):
        self.assertEqual(self._one("about 3 months ago")[1:3],
                         (3, "month"))

    def test_last_month(self):
        self.assertEqual(self._one("we met last month")[1:3],
                         (1, "month"))

    def test_now_type(self):
        self.assertEqual(
            self._one("I have been playing for six weeks now")[1:3],
            (6, "week"))

    def test_mixed_line_yields_multiple(self):
        exprs = list(_pp_dur_exprs(
            "I moved three weeks ago and started yoga "
            "for two months now."))
        self.assertEqual([(e[0], e[1], e[2]) for e in exprs],
                         [("ago", 3, "week"), ("now", 2, "month")])


class TestAnswerPPDuration(unittest.TestCase):
    def test_ago_minus_ago(self):
        ans, detail = answer_pp_duration(BOOK_Q, BOOK_SESSIONS)
        self.assertEqual(ans, "2 weeks")
        self.assertEqual(detail["route"], "ago_arith")

    def test_now_type_minus_ago(self):
        ans, _ = answer_pp_duration(GUITAR_Q, GUITAR_SESSIONS)
        # 6-week tenure − 2-week-ago amp = 28 days = 4 weeks
        self.assertEqual(ans, "4 weeks")

    def test_cross_exclusion_shared_phrase(self):
        # The workshop line ALSO contains "bird watching" (state
        # keywords) — a single-phase picker would double-capture it
        # and produce 0 days. Cross-exclusion must send the state
        # anchor to the tenure line in the other session.
        ans, detail = answer_pp_duration(BIRD_Q, BIRD_SESSIONS)
        self.assertEqual(ans, "2 months")
        self.assertNotEqual(detail.get("days"), 0)

    def test_nested_tenure_subtraction(self):
        ans, detail = answer_pp_duration(NOVATECH_Q, TENURE_SESSIONS)
        # 108 months total − 51 months tenure = 4 years and 9 months
        self.assertEqual(ans, "4 years and 9 months")
        self.assertEqual(detail["route"], "before_job")
        self.assertEqual((detail["total_m"], detail["tenure_m"]),
                         (108, 51))

    def test_nested_tenure_negative_existence_abstains(self):
        # No tenure line for Google anywhere → negative existence
        ans, detail = answer_pp_duration(GOOGLE_Q, TENURE_SESSIONS)
        self.assertEqual(ans, ABSTAIN_ANSWER)
        self.assertIn("no tenure line", detail["abstain"])

    def test_unresolved_evidence_falls_through(self):
        ans, detail = answer_pp_duration(BOOK_Q, [
            ("2023-05-28", [{"role": "user",
                             "content": "Lovely weather today."}])])
        self.assertIsNone(ans)
        self.assertIn("missing", detail)

    def test_unparsable_dates_skipped(self):
        ans, _ = answer_pp_duration(BOOK_Q, [
            ("", BOOK_SESSIONS[0][1])])
        self.assertIsNone(ans)

    def test_three_letter_keywords_survive(self):
        # "rug"/"amp" are 3-letter content nouns (#077 v2 lesson)
        q = ("How long had I been using the area rug "
             "when I rearranged the furniture?")
        ans, _ = answer_pp_duration(q, [
            ("2023-05-26", [
                {"role": "user", "content": (
                    "I got the area rug a month ago and love it.")},
                {"role": "user", "content": (
                    "I rearranged the furniture three weeks ago.")},
            ])])
        # rug: 04-26 … furniture: 05-05 → ~9-10 days → 1 week
        self.assertEqual(ans, "1 week")


class TestPPRender(unittest.TestCase):
    def test_nonzero_guard_months(self):
        # 10 days must NOT render as "0 months"
        self.assertEqual(_pp_render(10, ["month"]), "10 days")

    def test_week_hint(self):
        self.assertEqual(_pp_render(14, ["week", "week"]), "2 weeks")

    def test_month_hint(self):
        self.assertEqual(_pp_render(60, ["month", "month"]), "2 months")

    def test_zero(self):
        self.assertEqual(_pp_render(0, ["week"]), "0 days")


class TestPPDurationJudge(unittest.TestCase):
    def test_word_number_normalization(self):
        self.assertTrue(pp_duration_judge(
            BOOK_Q, "Two weeks", "2 weeks"))

    def test_exact_compound(self):
        self.assertTrue(pp_duration_judge(
            NOVATECH_Q, "4 years and 9 months",
            "4 years and 9 months"))

    def test_day_range_accepted(self):
        gt = ("One week. Answers ranging from 7 to 10 days "
              "are also acceptable")
        self.assertTrue(pp_duration_judge(BOOK_Q, gt, "1 week"))
        self.assertTrue(pp_duration_judge(BOOK_Q, gt, "8 days"))

    def test_day_range_out_of_band_rejected(self):
        gt = ("One week. Answers ranging from 7 to 10 days "
              "are also acceptable")
        self.assertFalse(pp_duration_judge(BOOK_Q, gt, "3 weeks"))

    def test_wrong_value_rejected(self):
        self.assertFalse(pp_duration_judge(
            GUITAR_Q, "Four weeks", "6 weeks"))

    def test_singular_plural_tolerance(self):
        self.assertTrue(pp_duration_judge(
            GUITAR_Q, "4 week", "4 weeks"))

    def test_abstain_vs_not_enough(self):
        self.assertTrue(pp_duration_judge(
            GOOGLE_Q, "Not enough information", ABSTAIN_ANSWER))
        self.assertFalse(pp_duration_judge(
            GOOGLE_Q, "Not enough information", "2 years"))


class TestAdapterIntegration(unittest.TestCase):
    def _adapter(self, **kw):
        adapter = LongMemEvalAdapter(
            abstain_entropy=None, pp_duration=kw.pop(
                "pp_duration", True), **kw)
        sessions = [
            {"session_id": "s1", "messages": [
                {"role": "user", "content": (
                    "I joined Book Lovers Unite three weeks ago. "
                    "Excited to finally be a member!")},
                {"role": "assistant", "content": (
                    "Welcome! How did you hear about the club?")},
                {"role": "user", "content": (
                    "The first meetup happened last week and it "
                    "was wonderful.")},
            ]},
        ]
        adapter.ingest_sessions(
            sessions, session_dates={"s1": "2023/05/28 (Sun) 21:02"})
        return adapter

    def test_e2e_gate_and_correct(self):
        adapter = self._adapter()
        report = adapter.evaluate([{
            "question_id": "pp_e2e_1",
            "question_type": "temporal-reasoning",
            "question": BOOK_Q,
            "answer": "Two weeks",
        }])
        res = report["results"][0]
        self.assertEqual(res["predicted_answer"], "2 weeks")
        self.assertFalse(res["abstained"])
        self.assertTrue(res["correct"])
        self.assertEqual(res["retrieval"]["gate"], "pp_duration")

    def test_flag_off_falls_through(self):
        adapter = self._adapter(pp_duration=False)
        report = adapter.evaluate([{
            "question_id": "pp_e2e_2",
            "question_type": "temporal-reasoning",
            "question": BOOK_Q,
            "answer": "Two weeks",
        }])
        res = report["results"][0]
        self.assertNotEqual(res["retrieval"]["gate"], "pp_duration")
        self.assertNotEqual(res["predicted_answer"], "2 weeks")

    def test_e2e_abstain_scores_abs_question(self):
        adapter = self._adapter()
        report = adapter.evaluate([{
            "question_id": "pp_e2e_abs",
            "question_type": "temporal-reasoning",
            "question": GOOGLE_Q,
            "answer": "Not enough information",
        }])
        res = report["results"][0]
        # negative existence → abstain → _abs protocol scores it
        self.assertTrue(res["abstained"])
        self.assertTrue(res["correct"])
        self.assertEqual(res["retrieval"]["gate"], "pp_duration")


if __name__ == "__main__":
    unittest.main()
