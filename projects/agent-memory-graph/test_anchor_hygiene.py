"""Tests for Cycle 471 anchor-hygiene set (Research #072).

Fixes the deterministic failure buckets found by fired-but-wrong
forensics on the temporal-arithmetic path:
  ① quote stripping + possessive token hygiene (a shared-prefix
     stem for submitted/submission was tried and REVERTED — no
     prefix length separates that pair from instacart/instagram)
  ② deterministic tie ladder: distinctive hits > generic hits >
     user-role > past aspect > later date (replaces silent
     first-max = list-position tie-break)
  ③ week unit round-half-up (annotator "about N weeks" semantics)
"""

import unittest

from amg_bench_quality import (
    duration_units,
    answer_temporal_arith,
    _anchor_keywords,
    _keywords,
    _keyword_hits,
)


class TestQuoteHygiene(unittest.TestCase):
    """① — quoted anchor keywords never matched anything."""

    def test_anchor_keywords_strip_quotes(self):
        ks = _anchor_keywords("the app 'ibotta' I told you about")
        self.assertIn("ibotta", ks)
        self.assertNotIn("'ibotta'", ks)

    def test_line_hits_match_quoted_anchor(self):
        ks = _anchor_keywords("using 'ibotta'")
        self.assertGreater(
            _keyword_hits("[user] I have been using ibotta for "
                          "cashback rebates", ks), 0)

    def test_keywords_strip_quotes(self):
        self.assertIn("ibotta", _keywords("tell me about 'ibotta'"))
        self.assertNotIn("'ibotta'", _keywords("tell me about 'ibotta'"))

    def test_line_possessive_token_normalized(self):
        # "master's" on the line must match keyword "master"
        self.assertGreater(
            _keyword_hits("I finished my master's thesis",
                          ["master"]), 0)

    def test_no_insta_collision(self):
        # 1916e0ea: a shared-5 brand prefix must never match —
        # the shipped matcher stays strictly inflectional
        self.assertEqual(
            _keyword_hits("decrease in Instagram usage",
                          ["instacart"]), 0)

    def test_strict_matcher_unchanged_for_shared_prefixes(self):
        # derivational pairs stay unmatched (C447 strictness): the
        # Cycle 471 prefix-stem experiment was reverted — no prefix
        # length separates submitted/submission from insta-
        self.assertEqual(
            _keyword_hits("my thesis submission was accepted",
                          ["submitted"]), 0)
        self.assertEqual(
            _keyword_hits("consider the options", ["consist"]), 0)


class TestWeekCeil(unittest.TestCase):
    """③ — annotator semantics are "about N weeks" (round).

    A/B evidence: 13d→2w, 20d→3w, 23d→3w, 30d→4w — floor fails
    two, ceil fails two, round fits all seven fired week questions.
    """

    def test_thirteen_days_is_two_weeks(self):
        self.assertEqual(
            duration_units("2023-03-01", "2023-03-14", "week"), 2)

    def test_twenty_days_is_three_weeks(self):
        self.assertEqual(
            duration_units("2023-03-01", "2023-03-21", "week"), 3)

    def test_twentythree_days_is_three_weeks(self):
        # 61e13b3c: ceil(23/7)=4 would fire wrong
        self.assertEqual(
            duration_units("2023-02-03", "2023-02-26", "week"), 3)

    def test_thirty_days_is_four_weeks(self):
        # bcbe585f: ceil(30/7)=5 regressed a correct answer
        self.assertEqual(
            duration_units("2023-04-01", "2023-05-01", "week"), 4)

    def test_exact_multiple_unchanged(self):
        self.assertEqual(
            duration_units("2023-05-01", "2023-05-15", "week"), 2)
        self.assertEqual(
            duration_units("2023-01-01", "2023-01-29", "week"), 4)

    def test_days_unit_unchanged(self):
        self.assertEqual(
            duration_units("2023-03-01", "2023-03-14", "day"), 13)


class TestTieLadder(unittest.TestCase):
    """② — explicit adjudication replaces first-position wins."""

    def _between(self, lines):
        return answer_temporal_arith(
            "How many days passed between the charity 5K run and the "
            "bake sale?", lines)

    def test_user_role_beats_assistant(self):
        # equal hits, same aspect: [user] line must win the tie
        lines = [
            ("[assistant] The 5K run charity event was discussed "
             "earlier", "2023-03-05"),
            ("[user] The 5K run charity event was exhausting",
             "2023-03-19"),
            ("[user] the bake sale happened", "2023-03-25"),
        ]
        ans, detail = self._between(lines)
        # user-line win → 03-19 ↔ 03-25 = 6 days; assistant-line
        # (list-position first) would give 03-05 ↔ 03-25 = 20 days
        self.assertEqual(ans, "6 days")
        self.assertEqual(detail["dates"], ["2023-03-19", "2023-03-25"])

    def test_later_date_beats_list_position(self):
        # no aspect markers: pure recency tie-break (first-position
        # win would give 03-10 ↔ 03-25 = 15 days)
        lines = [
            ("[user] 5K charity event recap", "2023-03-10"),
            ("[user] 5K charity event photos posted", "2023-03-19"),
            ("[user] the bake sale happened", "2023-03-25"),
        ]
        ans, detail = self._between(lines)
        self.assertEqual(ans, "6 days")
        self.assertEqual(detail["dates"], ["2023-03-19", "2023-03-25"])

    def test_past_aspect_beats_future_marker(self):
        # planning mention is LATER: aspect must override recency
        # (future-line win would pick 03-22 → 12 days)
        lines = [
            ("[user] I attended the bake sale, sold out of cookies",
             "2023-03-18"),
            ("[user] I am planning to attend the bake sale next week",
             "2023-03-22"),
            ("[user] my 5K run recap", "2023-03-10"),
        ]
        ans, detail = self._between(lines)
        # bake sale resolves via past aspect → 03-18 ↔ 03-10 = 8 days
        self.assertEqual(ans, "8 days")

    def test_generic_hits_only_break_ties(self):
        # equal distinctive hits: generic-word-rich line wins the tie
        lines = [
            ("[user] I visited the MoMA yesterday, so crowded",
             "2023-01-10"),
            ("[user] the MoMA trip", "2023-01-15"),
            ("[user] the Ancient Civilizations exhibition opened",
             "2023-01-22"),
        ]
        # anchor "my visit to the MoMA": distinctive kw = moma.
        # line 2 has same distinctive hits but no generic "visit" →
        # line 1 wins the generic tie-break (01-10 vs 01-22 = 12 days;
        # if line 2 won, same-session None or different value)
        ans, detail = answer_temporal_arith(
            "How many days passed between my visit to the MoMA and "
            "the Ancient Civilizations exhibition?", lines)
        self.assertEqual(ans, "12 days")

    def test_distinctive_hits_dominate_generic(self):
        # anchor resolves only from a line with distinctive hits
        # (generic words are excluded from anchor keywords, so a
        # generic-rich line cannot carry an anchor by itself)
        lines = [
            ("[user] bake sale prep, sold cookies and cakes",
             "2023-03-25"),
            ("[user] the 5K run and the bake sale both happened",
             "2023-03-10"),
        ]
        # anchor A "the charity 5K run": line 2 has distinctive 5K hit
        # and run hit; line 1 has none → date must come from line 2
        ans, detail = self._between(lines)
        self.assertEqual(detail["dates"][0], "2023-03-10")

    def test_missing_date_loses_tie(self):
        lines = [
            ("[user] 5K run charity recap", ""),
            ("[user] 5K run charity recap", "2023-03-19"),
            ("[user] bake sale happened", "2023-03-25"),
        ]
        ans, detail = self._between(lines)
        self.assertEqual(ans, "6 days")


class TestAnchorHygieneE2E(unittest.TestCase):
    """Forensics buckets composed end-to-end."""

    def test_quoted_anchor_plus_junk_ties(self):
        # e072b769 shape: junk line is LATER-dated, so without the
        # quote fix (tie 1-1 → later date) the junk line would win
        # and answer 11 days
        lines = [
            ("[user] Started using ibotta for grocery cashback "
             "today", "2023-03-15"),
            ("[user] I love using this cashback app for shopping",
             "2023-04-20"),
            ("[user] the wedding expo happened", "2023-05-01"),
        ]
        ans, detail = answer_temporal_arith(
            "How many days passed between when I started using "
            "'ibotta' and the wedding expo?", lines)
        self.assertEqual(ans, "47 days")
        self.assertEqual(detail["dates"], ["2023-03-15", "2023-05-01"])

    def test_same_session_still_unresolved(self):
        lines = [
            ("[user] 5K run and bake sale same day", "2023-03-10"),
        ]
        ans, detail = answer_temporal_arith(
            "How many days passed between the 5K run and the bake "
            "sale?", lines)
        self.assertIsNone(ans)
        self.assertEqual(detail["anchors"], [True, True])


if __name__ == "__main__":
    unittest.main()
