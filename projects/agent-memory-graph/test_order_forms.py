"""Cycle 488: order-family N-anchor sorting — #078 production port.

"What is the order of X, Y, Z from first to last?" answered by
anchoring every item to its earliest FRESH report (fresh >
vague-recall > planning tiers) and sorting by session date.
Prototype 9/9 on the full-500 family (baseline 0/9); strict form
gate zero-hijack by census (#078). Oracle parity: the production
answer_order reproduces the prototype's 9/9 on the real dataset
slice.
"""

import unittest

from amg_bench_quality import (
    LongMemEvalAdapter, answer_order, order_form, order_judge,
    _ord_canon_label, _ord_merge_items, _ord_scan_anchor,
    _ord_segments, _ord_window, _ord_lines,
)


def turn(role, content):
    return {"role": role, "content": content}


# ── fixtures ──────────────────────────────────────────────────────

# fresh-priority: the earliest FRESH report beats an earlier vague
# recall (the MoCA shape — "recently" [vague] vs "just" [fresh])
FRESH_Q = ("What is the order of the two museums I visited "
           "from earliest to latest?")
FRESH_DATED = [
    ("2023-03-04", [turn("user", "I recently visited the Met "
                             "Museum, it was lovely."),
                    turn("assistant", "The Met is a classic! "
                         "Another favorite is the History Museum.")]),
    ("2023-03-25", [turn("user", "I just got back from the Science "
                             "Museum today, amazing exhibits.")]),
]

# clause-level planning: one line plans one event and freshly
# reports another — line-level planning filters would kill the
# valid anchor (the NFL shape)
CLAUSE_DATED = [
    ("2023-01-05", [turn("user", "I'm thinking of ordering food "
                             "for the next game, I'm still on a "
                             "high from watching the NFL playoffs")]),
]

# relative-clause window: item mention and eventive predicate
# straddle a comma (the Alex-graduation shape)
RELCLAUSE_DATED = [
    ("2023-07-15", [turn("user", "Any gift ideas for my cousin "
                            "Alex, who graduated from college two "
                            "weeks ago?")]),
]

# planning-only mention never anchors (fall-through)
PLAN_DATED = [
    ("2023-05-01", [turn("user", "I'm planning a trip to Yosemite "
                            "next month, so excited.")]),
    ("2023-06-20", [turn("user", "Just got back from my solo "
                            "camping trip to Yosemite National "
                            "Park today!")]),
]

TRIP_Q = ("What is the order of the trips I took in the past "
          "month, from first to last?")

# window discipline: the old mention is outside "past month"
WINDOW_DATED = [
    ("2023-04-01", [turn("user", "I went on a road trip to Big "
                            "Sur with friends, stunning views.")]),
    ("2023-05-10", [turn("user", "Started my day hike to Muir "
                            "Woods today!")]),
]

# assistant recommendations never anchor (role discipline)
ROLE_DATED = [
    ("2023-03-01", [turn("assistant", "You should visit the "
                            "Science Museum, the History Museum "
                            "and the Modern Art Museum!")]),
    ("2023-03-20", [turn("user", "I visited the Science Museum "
                             "today."),
                     turn("user", "Yesterday I visited the History "
                            "Museum.")]),
]

# yesterday resolves one day earlier (tie-break within answers)
MUSEUM_Q = ("What is the order of the museums I visited from "
            "earliest to latest?")


class TestOrderFormGate(unittest.TestCase):
    def test_order_of(self):
        self.assertTrue(order_form(
            "What is the order of the six museums I visited "
            "from earliest to latest?"))

    def test_from_first_to_last(self):
        self.assertTrue(order_form(
            "Which three events happened in the order from first "
            "to last: A, B, C?"))

    def test_who_first_second(self):
        self.assertTrue(order_form(
            "Who graduated first, second and third among Emma, "
            "Rachel and Alex?"))

    def test_pairwise_which_first_excluded(self):
        self.assertFalse(order_form(
            "Which event happened first, the concert or the "
            "trip?"))

    def test_pairwise_who_or_excluded(self):
        self.assertFalse(order_form(
            "Who graduated first, Emma or Rachel?"))

    def test_bare_earliest_latest_excluded(self):
        # no "from ... to ..." frame and no "order of" — pairwise
        # sibling phrasing stays OUT of the strict gate
        self.assertFalse(order_form(
            "What is the earliest to latest timeline of events?"))


class TestFreshPriority(unittest.TestCase):
    def test_fresh_beats_earlier_vague(self):
        # fresh-priority is PER ITEM: Met has only a vague recall
        # (anchors to it, 03-04); Science has a fresh report
        # (03-25) — order = Met, Science. The tier decides WHICH
        # mention anchors an item, not the global order.
        pred, detail = answer_order(FRESH_Q, FRESH_DATED,
                                    "2023-04-01")
        self.assertEqual(detail["mode"], "museum")
        self.assertEqual(detail["n"], 2)
        self.assertIn("Science Museum", pred)
        self.assertLess(pred.index("Met"), pred.index("Science"))

    def test_fresh_report_wins_over_earlier_vague_same_item(self):
        # the decisive fresh-priority case: the SAME item has an
        # earlier vague mention and a later fresh one — the fresh
        # report is the birth certificate, the vague recall lags
        dated = [
            ("2023-03-04", [turn("user", "I recently visited "
                                    "the Met Museum.")]),
            ("2023-03-25", [turn("user", "Just got back from "
                                    "the Met Museum today!")]),
            ("2023-03-15", [turn("user", "I visited the Science "
                                    "Museum today.")]),
        ]
        pred, detail = answer_order(MUSEUM_Q, dated, "2023-04-01")
        # Met anchors to 03-25 (fresh), Science 03-15 → Science
        # sorts BEFORE Met despite Met's earlier vague mention
        self.assertLess(pred.index("Science"), pred.index("Met"))

    def test_yesterday_resolves_one_day_earlier(self):
        pred, _ = answer_order(MUSEUM_Q, ROLE_DATED, "2023-04-01")
        self.assertLess(pred.index("History"),
                        pred.index("Science"))


class TestClauseGranularity(unittest.TestCase):
    def test_clause_level_planning_filter(self):
        # the NFL clause is clean evidence despite the planning
        # clause sharing the line
        kws = {"nfl", "playoffs"}
        a = _ord_scan_anchor(kws, _ord_lines(CLAUSE_DATED))
        self.assertIsNotNone(a)

    def test_planning_only_clause_never_anchors(self):
        a = _ord_scan_anchor({"food", "game"}, _ord_lines(
            CLAUSE_DATED))
        self.assertIsNone(a)

    def test_relative_clause_window(self):
        # "Alex, who graduated ..." — predicate in next clause
        a = _ord_scan_anchor({"alex"}, _ord_lines(RELCLAUSE_DATED),
                             ctx=None)
        # plain {alex} has no graduation ctx here; with ctx it
        # resolves (below); without eventive-clean it may be None
        # — the assertion is that the ctx route anchors
        import re as _re
        a2 = _ord_scan_anchor(
            {"alex"}, _ord_lines(RELCLAUSE_DATED),
            ctx=_re.compile(r"graduat", _re.I))
        self.assertIsNotNone(a2)


class TestWindow(unittest.TestCase):
    def test_past_month_excludes_old_mention(self):
        pred, detail = answer_order(TRIP_Q, WINDOW_DATED,
                                    "2023-05-15")
        self.assertEqual(detail["mode"], "trip")
        self.assertEqual(detail["n"], 1)
        self.assertIn("Muir Woods", pred)

    def test_window_unresolvable_without_question_date(self):
        pred, detail = answer_order(TRIP_Q, WINDOW_DATED, "")
        self.assertIsNone(pred)
        self.assertEqual(detail["mode"], "window-unresolvable")

    def test_no_window_phrase_needs_no_date(self):
        pred, detail = answer_order(MUSEUM_Q, ROLE_DATED, "")
        self.assertEqual(detail["mode"], "museum")
        self.assertIsNotNone(pred)

    def test_named_month_window(self):
        q = ("What is the order of the sports events I watched "
             "in January?")
        dated = [
            ("2022-12-20", [turn("user", "Watched an NBA game "
                                    "yesterday, what a match!")]),
            ("2023-01-14", [turn("user", "I watched the College "
                                    "Football championship game "
                                    "today.")]),
        ]
        pred, detail = answer_order(q, dated, "2023-01-28")
        self.assertEqual(detail["n"], 1)   # December NBA excluded


class TestLabelCanonicalization(unittest.TestCase):
    def test_possessive_strip(self):
        self.assertEqual(_ord_canon_label("the Art's Studio"),
                         "Art's Studio".replace("'s", ""))

    def test_verb_prefix_strip(self):
        self.assertEqual(_ord_canon_label("finished a 5K run"),
                         "5K run")

    def test_substring_merge_absorbs(self):
        anchored = [("2023-06-10", 2, "Midsummer 5K Run"),
                    ("2023-06-10", 2, "5K run")]
        merged = _ord_merge_items(anchored)
        self.assertEqual(len(merged), 1)

    def test_kw_subset_not_merged(self):
        # "Museum of History" is a kw-subset of "Natural History
        # Museum" but a different museum — substring containment
        # correctly keeps both
        anchored = [("2023-03-04", 1, "Museum of History"),
                    ("2023-05-15", 2, "Natural History Museum")]
        merged = _ord_merge_items(anchored)
        self.assertEqual(len(merged), 2)


class TestRoleDiscipline(unittest.TestCase):
    def test_assistant_recommendations_never_anchor(self):
        pred, detail = answer_order(MUSEUM_Q, ROLE_DATED,
                                    "2023-04-01")
        self.assertEqual(detail["n"], 2)   # not the 3 recommended


class TestCategoryRoutes(unittest.TestCase):
    def test_airline_flight_context(self):
        q = ("What is the order of airlines I flew with from "
             "earliest to latest?")
        dated = [
            ("2023-01-28", [turn("user", "Flew Delta today, the "
                                    "flight was delayed."),
                            turn("user", "Bought Delta stock, "
                                    "thinking it's undervalued.")]),
            ("2023-02-15", [turn("user", "Flew JetBlue to visit "
                                    "mom, smooth flight.")]),
        ]
        pred, detail = answer_order(q, dated, "2023-03-01")
        self.assertEqual(detail["mode"], "airline")
        self.assertEqual(detail["n"], 2)
        # Delta flew 01-28, JetBlue 02-15 (fixture order)
        self.assertLess(pred.index("Delta"), pred.index("JetBlue"))

    def test_concert_session_scope(self):
        q = ("What is the order of the concerts I attended in the "
             "past month, starting from the earliest?")
        # item mention has NO eventive verb; the fresh marker
        # lives on an adjacent line of the SAME session
        dated = [
            ("2023-04-01", [
                turn("user", "The crowd at the Billie Eilish "
                     "concert was incredible!"),
                turn("user", "Today's concert was worth every "
                     "penny.")]),
        ]
        pred, detail = answer_order(q, dated, "2023-04-20")
        self.assertEqual(detail["mode"], "concert")
        self.assertIn("Billie Eilish", pred)

    def test_graduation_among_names(self):
        q = ("Who graduated first, second and third among Emma, "
             "Rachel and Alex?")
        dated = [
            ("2023-05-27", [turn("user", "My friend Rachel "
                                    "graduated last week, so "
                                    "proud of her!")]),
            ("2023-07-15", [turn("user", "Gift ideas for my cousin "
                                    "Alex, who graduated two "
                                    "weeks ago?")]),
            ("2023-06-21", [turn("user", "Emma graduated today, "
                                    "we are so proud.")]),
        ]
        pred, detail = answer_order(q, dated, "2023-08-01")
        self.assertEqual(detail["mode"], "closed")
        self.assertEqual(detail["n"], 3)
        self.assertLess(pred.index("Rachel"), pred.index("Emma"))
        self.assertLess(pred.index("Emma"), pred.index("Alex"))

    def test_closed_quoted_items(self):
        q = ("What is the order of the three events: 'I signed up "
             "for the rewards program at ShopRite', 'I redeemed "
             "cashback from Ibotta', and 'I used a coupon at "
             "Walmart'?")
        dated = [
            ("2023-04-01", [turn("user", "I used a coupon at "
                                    "Walmart today.")]),
            ("2023-04-15", [turn("user", "Just signed up for the "
                                    "rewards program at "
                                    "ShopRite!")]),
            ("2023-04-10", [turn("user", "Redeemed cashback from "
                                    "Ibotta this morning.")]),
        ]
        pred, detail = answer_order(q, dated, "2023-05-01")
        self.assertEqual(detail["mode"], "closed")
        self.assertLess(pred.index("coupon at Walmart"),
                        pred.index("Ibotta"))
        self.assertLess(pred.index("Ibotta"),
                        pred.index("ShopRite"))


class TestRender(unittest.TestCase):
    def test_three_connective(self):
        from amg_bench_quality import _ord_render
        self.assertEqual(
            _ord_render(["A", "B", "C"]),
            "First A, then B, finally C")

    def test_four_numbered(self):
        from amg_bench_quality import _ord_render
        self.assertEqual(
            _ord_render(["JetBlue", "Delta", "United",
                         "American Airlines"]),
            "1. JetBlue, 2. Delta, 3. United, "
            "4. American Airlines")


class TestOrderJudge(unittest.TestCase):
    Q = ("What is the order of the trips from first to last?")

    def test_sequence_match(self):
        self.assertTrue(order_judge(
            self.Q,
            "First, I went on my hiking trip, then I went on "
            "the camping trip, and finally my coast trip.",
            "First hiking trip, then camping trip, finally "
            "coast trip"))

    def test_reorder_fails(self):
        self.assertFalse(order_judge(
            self.Q,
            "First hiking trip, then camping trip, finally "
            "fishing trip",
            "First camping trip, then hiking trip, finally "
            "fishing trip"))

    def test_single_shared_generic_word_not_a_match(self):
        # "game" alone must not match across sports items — a
        # reordered sports answer would otherwise pass
        self.assertFalse(order_judge(
            self.Q, "NBA game, then championship game",
            "championship game, then NBA game"))

    def test_length_mismatch_fails(self):
        self.assertFalse(order_judge(
            self.Q, "First A, then B, finally C",
            "First A, then B"))

    def test_bare_comma_list(self):
        self.assertTrue(order_judge(
            self.Q, "JetBlue, Delta, United, American Airlines",
            "1. JetBlue, 2. Delta, 3. United, "
            "4. American Airlines"))

    def test_numbered_truth(self):
        self.assertTrue(order_judge(
            self.Q,
            "The order of the concerts I attended is: "
            "1. Billie Eilish concert at the Wells Fargo Center, "
            "2. jazz night at a local bar",
            "1. Billie Eilish concert at the Wells Fargo Center, "
            "2. jazz night at a local bar"))

    def test_followed_by(self):
        self.assertTrue(order_judge(
            self.Q,
            "Emma graduated first, followed by Rachel and then "
            "Alex.",
            "First Emma, then Rachel, finally Alex"))

    def test_non_order_form_falls_back(self):
        # judge guards the form itself (foreign questions fall
        # back to containment)
        self.assertTrue(order_judge(
            "What color is the sky?",
            "blue", "the sky is blue"))


class TestAdapterRoute(unittest.TestCase):
    def _adapter(self, **kw):
        return LongMemEvalAdapter(**kw)

    def test_route_fires_with_gate_metadata(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I visited the Science Museum "
                     "today."),
                turn("user", "Yesterday I visited the History "
                     "Museum.")]},
             {"session_id": "s2", "messages": [
                turn("assistant", "You should visit the Modern "
                     "Art Museum!")],
              }],
            session_dates={"s1": "2023-03-20",
                           "s2": "2023-03-01"})
        ans, meta = ad.answer_extractive(MUSEUM_Q, "2023-04-01")
        self.assertEqual(meta.get("gate"), "order")
        self.assertFalse(meta["abstained"])
        self.assertIn("History", ans)
        self.assertLess(ans.index("History"), ans.index("Science"))

    def test_unresolved_falls_through(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "Random chatter about nothing "
                     "relevant here.")]}],
            session_dates={"s1": "2023-03-20"})
        ans, meta = ad.answer_extractive(MUSEUM_Q, "2023-04-01")
        self.assertNotEqual(meta.get("gate"), "order")

    def test_pairwise_sibling_never_routes(self):
        ad = self._adapter()
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I watched the NFL playoffs "
                     "today.")]}],
            session_dates={"s1": "2023-01-22"})
        ans, meta = ad.answer_extractive(
            "Which event happened first, the concert or the "
            "trip?", "2023-02-01")
        self.assertNotEqual(meta.get("gate"), "order")

    def test_disable_flag(self):
        ad = self._adapter(order_sort=False)
        ad.ingest_sessions(
            [{"session_id": "s1", "messages": [
                turn("user", "I visited the Science Museum "
                     "today.")]}],
            session_dates={"s1": "2023-03-20"})
        ans, meta = ad.answer_extractive(MUSEUM_Q, "2023-04-01")
        self.assertNotEqual(meta.get("gate"), "order")


if __name__ == "__main__":
    unittest.main()
