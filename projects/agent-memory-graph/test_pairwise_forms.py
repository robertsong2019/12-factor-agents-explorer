"""Cycle 489: pairwise "which happened first, X or Y?" gate.

Tests the form detector, the minute-granularity line extraction,
the decision matrix (both-anchored / negative-existence abstain /
sub-24h fall-through), verb congruence, clause-gated relative
durations, and end-to-end wiring through answer_extractive
(gate=pairwise, abstained semantics, judge).
"""
import unittest

import amg_bench_quality as m
from amg_bench_quality import (
    LongMemEvalAdapter, pw_form, _pw_kws, _pw_line_match,
    _pw_qverbs, _pw_lines, _pw_rel_dt, _pw_line_dt, answer_pairwise,
    pairwise_judge, ABSTAIN_ANSWER)
from datetime import datetime, timedelta


def turn(role, content):
    return {"role": role, "content": content}


def dated(*sessions):
    """[(date_str, [turns])] helper — raw LME-style date strings."""
    return sessions


class TestPwForm(unittest.TestCase):
    def test_positive_disjunction(self):
        self.assertEqual(
            pw_form("Which event did I attend first, the jazz "
                    "concert or the art exhibition?"),
            ("the jazz concert", "the art exhibition"))

    def test_happened_first(self):
        c = pw_form("Which happened first, my trip to Rome or my "
                    "move to Berlin?")
        self.assertEqual(c, ("my trip to Rome", "my move to Berlin"))

    def test_negative_order_family(self):
        # order-of phrasings route to order_form (C488)
        self.assertIsNone(pw_form(
            "What was the order of the events from first to last?"))

    def test_negative_no_first(self):
        self.assertIsNone(pw_form(
            "Which did I enjoy more, Rome or Berlin?"))

    def test_negative_no_disjunction(self):
        self.assertIsNone(pw_form(
            "Which event did I attend first in March?"))

    def test_negative_not_which_lead(self):
        self.assertIsNone(pw_form(
            "Tell me which one came first, Rome or Berlin."))

    def test_negative_short_candidate(self):
        self.assertIsNone(pw_form(
            "Which did I do first, a or b?"))


class TestKws(unittest.TestCase):
    def test_frame_stop_and_articles(self):
        # "the"/"my"/"did"/"first" stripped; nouns survive
        kws = _pw_kws("the charity bake sale")
        self.assertEqual([k for grp in kws for k in grp],
                         ['charity', 'bake', 'sale'])

    def test_stem_variants(self):
        kws = _pw_kws("the tomato plants")
        # 'plants' → {plant, plants}
        flat = [v for grp in kws for v in grp]
        self.assertIn('plant', flat)

    def test_line_match_requires_all(self):
        kws = _pw_kws("charity bake sale")
        self.assertTrue(_pw_line_match(kws, "I ran a charity bake "
                                           "sale last weekend"))
        self.assertFalse(_pw_line_match(kws, "the charity event"))


class TestQVerbs(unittest.TestCase):
    def test_finish(self):
        qv = _pw_qverbs("Which book did I finish first, X or Y?")
        self.assertIn('finish', qv)

    def test_join(self):
        qv = _pw_qverbs("Which group did I join first, X or Y?")
        self.assertIn('sign up', qv)

    def test_no_verb(self):
        self.assertIsNone(_pw_qverbs(
            "Which happened first, X or Y?"))


class TestPwLinesMinuteGranularity(unittest.TestCase):
    def test_minute_times_kept(self):
        d = dated(
            ("2023/05/30 (Tue) 07:08",
             [turn("user", "I just finished reading three novels.")]),
            ("2023/05/30 (Tue) 12:42",
             [turn("user", "I just finished The Hate U Give.")]))
        lines = _pw_lines(d)
        self.assertEqual(len(lines), 2)
        self.assertNotEqual(lines[0][0], lines[1][0])
        self.assertLess(lines[0][0], lines[1][0])

    def test_bare_date_falls_back(self):
        lines = _pw_lines(dated(
            ("2023/05/30",
             [turn("user", "hello there")]),
            (None, [turn("user", "no date")]),
            ("garbage", [turn("user", "bad date")])))
        self.assertEqual(len(lines), 1)

    def test_assistant_lines_excluded(self):
        lines = _pw_lines(dated(
            ("2023/05/30 (Tue) 07:08",
             [turn("assistant", "You mentioned the charity bake "
                                "sale."),
              turn("user", "Different topic entirely.")])))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][2], "Different topic entirely")


class TestRelDtClauseGate(unittest.TestCase):
    DT = datetime(2023, 5, 29, 19, 46)

    def test_kw_shares_clause_overrides(self):
        # "started it about three weeks ago" — 'it' anaphora does
        # NOT carry the Zero keyword → stays on session clock
        line = ("I'm working on a Ferrari 288 GTO, started it "
                "about three weeks ago")
        kws = _pw_kws("the Japanese Zero fighter plane")
        self.assertEqual(
            _pw_rel_dt(self.DT, line, kws), self.DT)

    def test_kw_in_clause_overrides(self):
        # explicit noun + relative duration in same clause → pull
        line = "I planted the tomato seedlings three weeks ago"
        kws = _pw_kws("the tomato seedlings")
        got = _pw_rel_dt(self.DT, line, kws)
        self.assertEqual(got, self.DT - timedelta(days=21))

    def test_last_month(self):
        line = "I set up the smart thermostat last month"
        kws = _pw_kws("the smart thermostat")
        self.assertEqual(
            _pw_rel_dt(self.DT, line, kws),
            self.DT - timedelta(days=30))


class TestLineDt(unittest.TestCase):
    def test_since_date(self):
        dt = _pw_line_dt(datetime(2023, 4, 15, 10, 0),
                         "My tomatoes have been thriving since "
                         "February 20", _pw_kws("my tomatoes"))
        self.assertEqual(dt, datetime(2023, 2, 20))

    def test_future_in_text_date_distrusted(self):
        # in-text date > session+14d is a distractor
        dt = _pw_line_dt(datetime(2023, 4, 15, 10, 0),
                         "I planted them since March 5 and will "
                         "harvest June 1", None)
        self.assertEqual(dt, datetime(2023, 3, 5))


class TestAnswerPairwise(unittest.TestCase):
    def test_both_anchored_earlier_wins(self):
        d = dated(
            ("2023/03/01 (Wed) 09:00",
             [turn("user", "I just adopted a golden retriever "
                           "puppy today.")]),
            ("2023/03/20 (Mon) 14:00",
             [turn("user", "I just got a new router for the "
                           "office.")]))
        ans, detail = answer_pairwise(
            "Which did I get first, the puppy or the router?", d)
        self.assertEqual(ans, "the puppy")
        self.assertEqual(detail["mode"], "both")

    def test_same_day_minutes_disambiguate(self):
        d = dated(
            ("2023/05/30 (Tue) 07:08",
             [turn("user", "I just finished reading three fiction "
                           "novels yesterday.")]),
            ("2023/05/30 (Tue) 12:42",
             [turn("user", "I just finished The Hate U Give "
                           "today.")]))
        ans, detail = answer_pairwise(
            "Which book did I finish first, the novels or The "
            "Hate U Give?", d)
        # 07:08 vs 12:42 → resolvable, no sub-24h tie… (fresh tier:
        # yesterday−1d = 05-29 07:08 < 05-30 12:42)
        self.assertEqual(detail["mode"], "both")
        self.assertEqual(ans, "the novels")

    def test_sub24h_tie_falls_through(self):
        # both anchored via FRESH tier hours apart on the SAME day
        # (no date signal to order them beyond time-of-day → the
        # recommendation-echo hazard) → unresolvable. Mirrors the
        # real 2d58bcd6 / 483dd43c pattern ("just thinking about X" /
        # "just finished Y" same day).
        d = dated(
            ("2023/05/22 (Mon) 00:37",
             [turn("user", "I've been to the Grand Canyon with my "
                           "family before.")]),
            ("2023/05/22 (Mon) 11:56",
             [turn("user", "I was just thinking about my solo trip "
                           "to Europe again.")]))
        # C494: 'last summer' (the original fixture wording) now
        # calendar-pulls the Europe anchor to 2022-07-01 and
        # correctly RESOLVES the pair — replaced with a duration-
        # free echo line so the tie semantics stays covered.
        ans, detail = answer_pairwise(
            "Which happened first, my solo trip to Europe or the "
            "Grand Canyon with my family?", d)
        # Europe line fresh-anchors ("just") on the same day as the
        # Canyon vague anchor → gap 11h → tie
        self.assertIsNone(ans)
        self.assertEqual(detail["mode"], "sub-24h-tie")

    def test_negative_existence_abstain(self):
        d = dated(
            ("2023/03/10 (Fri) 10:00",
             [turn("user", "I participated in the charity bake "
                           "sale today.")]))
        ans, detail = answer_pairwise(
            "Which event did I attend first, the bake sale or the "
            "silent auction?", d)
        self.assertEqual(ans, ABSTAIN_ANSWER)
        self.assertEqual(detail["mode"], "neg-exist-B")

    def test_unanchored_but_mentioned_falls_through(self):
        d = dated(
            ("2023/03/10 (Fri) 10:00",
             [turn("user", "I'm thinking of visiting Rome someday, "
                           "and I went to Paris last week.")]))
        # Paris (B) anchored (eventive clause); Rome (A) mentioned
        # but planning-only → partial → fall through (no abstain:
        # Rome IS mentioned)
        ans, detail = answer_pairwise(
            "Which city did I visit first, Rome or Paris?", d)
        self.assertIsNone(ans)
        self.assertIn(detail["mode"], ("A-unanchored", "B-unanchored",
                                       "neither"))

    def test_verb_congruence_blocks_wrong_verb(self):
        # question asks "finish"; evidence only MENTIONS the book
        # (bought it — eventive but wrong verb) — the vague tier's
        # verb filter blocks the anchor
        d = dated(
            ("2023/05/01 (Mon) 09:00",
             [turn("user", "I bought Game of Thrones at the "
                           "bookstore.")]))
        ans, detail = answer_pairwise(
            "Which book did I finish first, Game of Thrones or "
            "Dune?", d)
        self.assertIsNone(ans)
        self.assertIn(detail["mode"], ("neither", "A-unanchored"))

    def test_window_unresolvable(self):
        ans, detail = answer_pairwise(
            "Which did I attend first in the past month, the "
            "recital or the gala?",
            dated(("2023/03/01 (Wed) 09:00",
                   [turn("user", "went to the recital")])))
        self.assertIsNone(ans)
        self.assertEqual(detail["mode"], "window-unresolvable")


class TestJudge(unittest.TestCase):
    def test_containment_truth_sentence(self):
        self.assertTrue(pairwise_judge(
            "Which event did I attend first, A or B?",
            "I participated in the charity bake sale first.",
            "the charity bake sale"))

    def test_two_shared_words(self):
        self.assertTrue(pairwise_judge(
            "Which happened first, A or B?",
            "the family road trip across the American Southwest",
            "the road trip across the American Southwest"))

    def test_wrong_candidate_fails(self):
        self.assertFalse(pairwise_judge(
            "Which happened first, A or B?",
            "I got the bike first.", "the car"))


class TestEndToEnd(unittest.TestCase):
    def _adapter(self, **kw):
        return LongMemEvalAdapter(use_ppr=False, **kw)

    def test_gate_fires_and_answers(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I just adopted the golden retriever "
                     "puppy today.")]}],
            session_dates={"s1": "2023/03/01 (Wed) 09:00"})
        ad.ingest_sessions(
            [{"session_id": "s2", "messages": [
                turn("user", "I finally got the new router set "
                     "up.")]}],
            session_dates={"s2": "2023/03/20 (Mon) 14:00"})
        ans, meta = ad.answer_extractive(
            "Which did I get first, the puppy or the router?", "")
        self.assertEqual(meta.get("gate"), "pairwise")
        self.assertEqual(ans, "the puppy")
        self.assertFalse(meta["abstained"])

    def test_abstention_semantics(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I joined the Page Turners book club "
                     "yesterday.")]}],
            session_dates={"s1": "2023/05/25 (Thu) 01:50"})
        ans, meta = ad.answer_extractive(
            "Which did I join first, the book club or the running "
            "club?", "")
        self.assertEqual(meta.get("gate"), "pairwise")
        self.assertTrue(meta["abstained"])
        self.assertEqual(ans, ABSTAIN_ANSWER)

    def test_disable_flag(self):
        ad = self._adapter(pairwise_sort=False)
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I just adopted the golden retriever "
                     "puppy today.")]}],
            session_dates={"s1": "2023/03/01 (Wed) 09:00"})
        ad.ingest_sessions(
            [{"session_id": "s2", "messages": [
                turn("user", "I finally got the new router set "
                     "up.")]}],
            session_dates={"s2": "2023/03/20 (Mon) 14:00"})
        _, meta = ad.answer_extractive(
            "Which did I get first, the puppy or the router?", "")
        self.assertNotEqual(meta.get("gate"), "pairwise")

    def test_raw_dates_stashed(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "hello")]}],
            session_dates={"s1": "2023/03/01 (Wed) 09:00"})
        self.assertEqual(ad._session_dates_raw.get("s1"),
                         "2023/03/01 (Wed) 09:00")
        self.assertEqual(ad._session_dates.get("s1"), "2023-03-01")


if __name__ == "__main__":
    unittest.main()
