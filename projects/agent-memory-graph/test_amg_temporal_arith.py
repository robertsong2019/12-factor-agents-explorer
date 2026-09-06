"""Tests for the Cycle 457 temporal-arithmetic answer path (amg).

LME_s temporal-reasoning questions are duration arithmetic and event
ordering, not when-questions — answered by calendar arithmetic over
session dates (question_date + haystack_dates grounding), zero LLM.
"""

import unittest

from amg_bench_quality import (
    LongMemEvalAdapter,
    parse_lme_date,
    temporal_arith_form,
    duration_units,
    answer_temporal_arith,
    temporal_arith_judge,
    run_eval,
    _anchor_keywords,
    _line_adverbial_date,
)


class TestParseLmeDate(unittest.TestCase):
    def test_slash_with_weekday_suffix(self):
        self.assertEqual(parse_lme_date("2023/02/01 (Wed) 10:20"),
                         "2023-02-01")

    def test_iso(self):
        self.assertEqual(parse_lme_date("2023-2-1"), "2023-02-01")

    def test_garbage(self):
        self.assertEqual(parse_lme_date("May 2023"), "")
        self.assertEqual(parse_lme_date(""), "")


class TestFormParsing(unittest.TestCase):
    def test_between_have(self):
        kind, unit, a, b = temporal_arith_form(
            "How many days have passed between my visit to the MoMA "
            "and the Ancient Civilizations exhibition?")
        self.assertEqual((kind, unit), ("between", "day"))
        self.assertIn("moma", a.lower())
        self.assertIn("ancient", b.lower())

    def test_between_had(self):
        kind, unit, a, b = temporal_arith_form(
            "How many weeks had passed between the bake sale and the "
            "church picnic?")
        self.assertEqual((kind, unit), ("between", "week"))

    def test_ago(self):
        kind, unit, a, b = temporal_arith_form(
            "How many weeks ago did I meet up with my aunt and receive "
            "the crystal chandelier?")
        self.assertEqual((kind, unit, b), ("ago", "week", None))
        self.assertIn("chandelier", a)

    def test_since(self):
        kind, unit, a, b = temporal_arith_form(
            "How many months have passed since I participated in two "
            "charity events in a row?")
        self.assertEqual((kind, unit), ("since", "month"))

    def test_first_retired_classic(self):
        # C493: TA first-kind retired. Full-500 forensics: pairwise
        # (C489) owns the family; TA-first resolved only 3 residual
        # members — 1 correct (redundant with the extractive answer
        # gate) and 2 wrong. Zero-loss A/B (12/30 both arms, zero
        # flips) -> the branch is retired, questions fall through.
        self.assertIsNone(temporal_arith_form(
            "Which event happened first, my cousin's wedding or "
            "Michael's engagement party?"))

    def test_first_retired_who_variant(self):
        self.assertIsNone(temporal_arith_form(
            "Who did I meet first, Mark and Sarah or Tom?"))

    def test_not_temporal(self):
        for q in ("What is my favorite book?",
                  "When did I visit the museum?",
                  "How many books did I read this year?",
                  "Which device did I use most often?"):
            self.assertIsNone(temporal_arith_form(q), q)


class TestDurationUnits(unittest.TestCase):
    def test_days_exact(self):
        self.assertEqual(
            duration_units("2023-05-01", "2023-05-08", "day"), 7)

    def test_weeks_floor(self):
        self.assertEqual(
            duration_units("2023-05-01", "2023-05-15", "week"), 2)

    def test_months_calendar(self):
        # 2022-12-01 → 2023-02-01 = 2 calendar months exactly
        self.assertEqual(
            duration_units("2022-12-01", "2023-02-01", "month"), 2)

    def test_months_half_rounding(self):
        # 2022-12-01 → 2023-01-10: exactly 1 month + 9 days → 1
        self.assertEqual(
            duration_units("2022-12-01", "2023-01-10", "month"), 1)
        # 2022-12-01 → 2023-01-20: 1 month + 19 days → rounds to 2
        self.assertEqual(
            duration_units("2022-12-01", "2023-01-20", "month"), 2)


class TestAnswerTemporalArith(unittest.TestCase):
    LINES = [
        ("[user] I visited the MoMA last weekend, loved the abstract wing",
         "2023-01-15"),
        ("[user] We saw the Ancient Civilizations exhibition today",
         "2023-01-22"),
        ("[assistant] Sounds like a busy week!", "2023-01-22"),
    ]

    def test_between_resolves(self):
        ans, detail = answer_temporal_arith(
            "How many days passed between my visit to the MoMA and the "
            "Ancient Civilizations exhibition?", self.LINES)
        self.assertEqual(ans, "7 days")
        self.assertEqual(detail["form"], "between")

    def test_ago_uses_question_date(self):
        lines = [("I met up with my aunt and received the crystal "
                  "chandelier", "2023-03-04")]
        ans, _ = answer_temporal_arith(
            "How many weeks ago did I meet up with my aunt and receive "
            "the crystal chandelier?", lines, "2023/04/01 (Sat) 08:09")
        self.assertEqual(ans, "4 weeks")

    def test_ago_anchor_after_question_falls_through(self):
        lines = [("I met up with my aunt, crystal chandelier story",
                  "2023-06-01")]
        ans, _ = answer_temporal_arith(
            "How many weeks ago did I meet up with my aunt?",
            lines, "2023/04/01 (Sat) 08:09")
        self.assertIsNone(ans)

    def test_first_falls_through_after_retirement(self):
        # C493: first-family questions are not TA forms anymore —
        # the answer path never sees a resolvable form for them.
        ans, detail = answer_temporal_arith(
            "Which event happened first, the Ancient Civilizations "
            "exhibition or my MoMA visit?", self.LINES)
        self.assertIsNone(ans)
        self.assertEqual(detail, {"form": None})

    def test_unresolved_anchor_returns_none(self):
        lines = [("I visited the MoMA", "2023-01-15")]
        ans, detail = answer_temporal_arith(
            "How many days passed between my MoMA visit and the "
            "Ancient Civilizations exhibition?", lines)
        self.assertIsNone(ans)
        self.assertEqual(detail["anchors"], [True, False])

    def test_same_session_returns_none(self):
        lines = [("MoMA then the Ancient Civilizations exhibition",
                  "2023-01-15")]
        ans, _ = answer_temporal_arith(
            "How many days passed between my MoMA visit and the "
            "Ancient Civilizations exhibition?", lines)
        self.assertIsNone(ans)

    def test_no_form_returns_none(self):
        ans, detail = answer_temporal_arith("What is my name?",
                                            self.LINES)
        self.assertIsNone(ans)
        self.assertEqual(detail, {"form": None})


class TestTemporalArithJudge(unittest.TestCase):
    def test_duration_multi_gold(self):
        q = ("How many days passed between X and Y?")
        self.assertTrue(temporal_arith_judge(
            q, "7 days. 8 days (including the last day) is also "
            "acceptable.", "7 days"))
        self.assertTrue(temporal_arith_judge(
            q, "7 days. 8 days (including the last day) is also "
            "acceptable.", "8 days"))

    def test_duration_wrong_value(self):
        self.assertFalse(temporal_arith_judge(
            "How many days passed between X and Y?", "7 days.", "9 days"))

    def test_first_judge_falls_back_to_exact(self):
        # C493: with the TA first form retired the judge has no
        # special first-kind branch — containment semantics come
        # from exact_judge (normalized truth-in-predicted).
        q = ("Which event happened first, my cousin's wedding or "
             "Michael's engagement party?")
        self.assertTrue(temporal_arith_judge(
            q, "Michael's engagement party",
            "Michael's engagement party"))
        # gold shorter, predicted longer (superset still contains)
        self.assertTrue(temporal_arith_judge(
            q, "engagement party",
            "Michael's engagement party on the beach"))

    def test_first_judge_wrong_event(self):
        q = ("Which event happened first, my cousin's wedding or "
             "Michael's engagement party?")
        self.assertFalse(temporal_arith_judge(
            q, "the skin tag removal", "my cousin's wedding"))

    def test_non_form_delegates_to_exact_judge(self):
        self.assertTrue(temporal_arith_judge(
            "What city?", "Paris", "I lived in Paris for years"))


class TestAdapterTemporalPath(unittest.TestCase):
    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions(
            [{"session_id": "s1", "messages": [
                {"role": "user", "content":
                 "I finally visited the MoMA and saw the abstract wing"}]},
             {"session_id": "s2", "messages": [
                {"role": "user", "content":
                 "The Ancient Civilizations exhibition was fascinating"}]}],
            session_dates={"s1": "2023/01/15 (Sun) 11:00",
                           "s2": "2023/01/22 (Sun) 19:30",
                           "s3": "not a date"})
        return a

    def test_gate_label_and_answer(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "How many days passed between my visit to the MoMA and "
            "the Ancient Civilizations exhibition?")
        self.assertEqual(ans, "7 days")
        self.assertEqual(meta["gate"], "temporal_arith")
        self.assertFalse(meta["abstained"])
        self.assertEqual(meta["temporal"]["value"], 7)

    def test_disabled_reproduces_baseline(self):
        a = self._adapter(temporal_arith=False)
        ans, meta = a.answer_extractive(
            "How many days passed between my visit to the MoMA and "
            "the Ancient Civilizations exhibition?")
        self.assertNotEqual(meta["gate"], "temporal_arith")
        self.assertNotEqual(ans, "7 days")

    def test_no_session_dates_falls_through(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([{"session_id": "s1", "messages": [
            {"role": "user", "content": "MoMA visit"}]}])
        _, meta = a.answer_extractive(
            "How many days passed between my MoMA visit and the "
            "exhibition?")
        self.assertNotEqual(meta["gate"], "temporal_arith")

    def test_evaluate_dispatches_temporal_judge(self):
        a = self._adapter()
        report = a.evaluate([{
            "id": "q1_temporal-reasoning",
            "question": ("How many days passed between my visit to "
                         "the MoMA and the Ancient Civilizations "
                         "exhibition?"),
            "answer": "7 days. 8 days is also acceptable.",
            "question_date": "2023/02/01 (Wed) 10:20"}])
        row = report["results"][0]
        self.assertTrue(row["correct"])
        self.assertEqual(row["predicted_answer"], "7 days")

    def test_ingest_drops_unparseable_dates(self):
        a = self._adapter()
        self.assertEqual(a._session_dates,
                         {"s1": "2023-01-15", "s2": "2023-01-22"})

    def test_anchor_keywords_strip_generic(self):
        ks = _anchor_keywords("the day I visited the museum")
        self.assertNotIn("visited", ks)
        self.assertIn("museum", ks)


class TestRunEvalWiring(unittest.TestCase):
    def test_haystack_dates_positional_map(self):
        item = {
            "id": "q1", "question": "What did I name my cat?",
            "answer": "Whiskers",
            "question_date": "2023/03/01 (Wed) 09:00",
            "haystack_dates": ["2023/01/01 (Sun) 10:00",
                               "2023/02/01 (Wed) 10:00"],
            "haystack_sessions": [
                [{"role": "user", "content": "I adopted a cat"},
                 {"role": "assistant", "content": "Congrats!"}],
                [{"role": "user", "content": "I named him Whiskers"}]],
        }
        report = run_eval([item])
        row = report["results"][0]
        self.assertEqual(row["ground_truth"], "Whiskers")
        # wiring smoke: session dates were ingested (exposed via
        # config + no crash); direct check through the adapter path
        self.assertIn("temporal_arith", report["config"])

    def test_temporal_question_end_to_end(self):
        item = {
            "id": "q2_temporal-reasoning",
            "question": ("How many weeks ago did I adopt my cat?"),
            "answer": "4",
            "question_date": "2023/01/29 (Sun) 12:00",
            "haystack_dates": ["2023/01/01 (Sun) 10:00"],
            "haystack_sessions": [
                [{"role": "user", "content": "I adopted a lovely cat "
                  "from the shelter today"}]],
        }
        report = run_eval([item])
        row = report["results"][0]
        self.assertEqual(row["predicted_answer"], "4 weeks")
        self.assertTrue(row["correct"])

    def test_disabled_flag(self):
        item = {
            "id": "q3", "question": "How many weeks ago did I adopt "
                                    "my cat?",
            "answer": "4",
            "question_date": "2023/01/29 (Sun) 12:00",
            "haystack_dates": ["2023/01/01 (Sun) 10:00"],
            "haystack_sessions": [
                [{"role": "user", "content": "I adopted a lovely cat "
                  "from the shelter today"}]],
        }
        report = run_eval([item], temporal_arith=False)
        row = report["results"][0]
        self.assertNotEqual(row["predicted_answer"], "4 weeks")


class TestSlashAdverbialDate(unittest.TestCase):
    """C554: numeric month/day slash form in _line_adverbial_date.

    The 8c18457d rescue: "graduation gift on the 3/8" kept the bare
    session date (03-29) instead of refining to 03-08, and the
    between-anchor diff came out 14 days vs GT 7.
    """

    def test_on_the_slash(self):
        self.assertEqual(
            _line_adverbial_date(
                "I got a wireless headphone for my brother as a "
                "graduation gift on the 3/8", "2023"),
            "2023-03-08")

    def test_bare_on_slash(self):
        self.assertEqual(
            _line_adverbial_date("we launched it on 3/8 last year", "2023"),
            "2023-03-08")

    def test_two_digit_year(self):
        self.assertEqual(
            _line_adverbial_date("bought the shoes on 1/18/23", ""),
            "2023-01-18")

    def test_no_year_hint(self):
        self.assertIsNone(
            _line_adverbial_date("got it on the 3/8", ""))

    def test_fraction_no_on(self):
        # "on" prefix mandatory — bare fractions/ratios must not match
        self.assertIsNone(
            _line_adverbial_date("use 3/8 of the budget for catering", "2023"))

    def test_month_word_still_wins(self):
        # first adverbial date in the line wins (month-word form here)
        self.assertEqual(
            _line_adverbial_date(
                "hiked on June 14th; gear list finalized on 6/20", "2023"),
            "2023-06-14")

    def test_end_to_end_between_rescue(self):
        # 8c18457d geometry: session dated 03-29 carrying "on the 3/8"
        # vs a 03-15 session; answer must be 7 days, not 14.
        a = LongMemEvalAdapter()
        a.ingest_sessions(
            [{"session_id": "s1", "messages": [
                {"role": "user", "content":
                 "I got a wireless headphone for my brother as a "
                 "graduation gift on the 3/8 and he loved it"}]},
             {"session_id": "s2", "messages": [
                {"role": "user", "content":
                 "I got a silver necklace for my best friend's "
                 "birthday on March 15th"}]}],
            session_dates={"s1": "2023-03-29", "s2": "2023-03-15"})
        dl = [(f"[{a._nodes[n]['role'] or '?'}] {a._nodes[n]['label']}",
               a._session_dates.get(a._nodes[n]['session_id'], ""))
              for n in a._messages]
        ans, det = answer_temporal_arith(
            "How many days had passed between the day I bought a gift "
            "for my brother's graduation ceremony and the day I bought "
            "a birthday gift for my best friend?",
            dl, "2023-03-29")
        self.assertEqual(ans, "7 days")
        self.assertEqual(det["dates"], ["2023-03-08", "2023-03-15"])


if __name__ == "__main__":
    unittest.main()
