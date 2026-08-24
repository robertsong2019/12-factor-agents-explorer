"""delta-family — two-anchor numeric aggregation (Cycle 509, #086).

The question names BOTH sides of a numeric comparison; each side
binds independently over the full haystack, then the operator
family runs (diff / sum2 / minmax / rate / count_ratio / pct_price
/ save / cmp_pct / t_diff). Ported from r086_proto7.py with
oracle parity 16/21 (fired-precision 100% on the research corpus).
"""

import unittest

import amg_bench_quality as abq
from amg_bench_quality import (LongMemEvalAdapter, answer_delta,
                               delta_form)


def sess(*turn_pairs):
    """One session from (role, content) pairs."""
    return {"session_id": "s1",
            "turns": [{"role": r, "content": c}
                      for r, c in turn_pairs]}


class TestGate(unittest.TestCase):
    """STRICT form gate — census over 500: 18 fires, all were-wrong."""

    def test_gate_positive_forms(self):
        pos = {
            "diff": "How much more expensive were the boots compared to "
                    "the gloves?",
            "save": "How much did I save by taking the train instead of "
                    "the taxi?",
            "sum2": "How much did I spend on the car wash and the "
                    "parking ticket?",
            "minmax": "What is the minimum amount I spent on tools and "
                      "on books?",
            "rate": "How much cashback did I earn?",
            "count_ratio": "What percentage of packed shoes did I wear "
                           "on my last trip?",
            "cmp_pct": "Did I get a better percentage discount at "
                       "Hobby Lobby compared to Michaels?",
            "pct_price": "What percentage discount did I get on my "
                         "favorite jacket?",
            "t_diff": "How many more miles per gallon was my car "
                      "getting last year?",
            "after_init": "What is the difference in price after the "
                          "initial quote was corrected?",
        }
        for kind, q in pos.items():
            got = delta_form(q)
            self.assertIsNotNone(got, q)
            if kind != "after_init":
                self.assertEqual(got, kind, q)

    def test_gate_negative_other_families(self):
        neg = [
            # temporal-arithmetic calendar distance
            "How many days passed between my trip and my return?",
            # counting total_sum (single-direction sum)
            "How much did I spend in total on groceries?",
            # counting number_total
            "What is the total number of books I own?",
            # ECM who-first
            "Who did I meet first, Rachel or Emily?",
            # pairwise which-first
            "Which did I finish first, the report or the slides?",
            # preference abstention
            "What kind of movies would I prefer this weekend?",
            # plain extractive fact
            "What color did I repaint my bedroom walls?",
            # single-entity how-much (no second side)
            "How much did I pay for the mixer?",
        ]
        for q in neg:
            self.assertIsNone(delta_form(q), q)


class TestOperators(unittest.TestCase):
    def test_diff_two_sides(self):
        s = [sess(("user", "I finally bought the boots for $800"),
                  ("user", "the gloves were only $50 at the market"),
                  ("assistant", "Great choice!"))]
        ans, det = answer_delta(
            "How much more did the boots cost compared to the gloves?",
            s)
        self.assertEqual(ans, "$750")
        self.assertEqual(det["op"], "diff")

    def test_save_instead_of(self):
        s = [sess(("user", "the taxi would have been $60"),
                  ("user", "I took the train for $10"))]
        ans, det = answer_delta(
            "How much did I save by taking the train instead of the "
            "taxi?", s)
        self.assertEqual(ans, "$50")
        self.assertEqual(det["op"], "save-instead")

    def test_sum2_two_entities(self):
        s = [sess(("user", "car wash set me back $15"),
                  ("user", "and the parking ticket was $50"))]
        ans, det = answer_delta(
            "How much did I spend on the car wash and the parking "
            "ticket?", s)
        self.assertEqual(ans, "$65")
        self.assertEqual(det["op"], "sum2")

    def test_minmax_sum(self):
        s = [sess(("user", "laptop sold: I listed at $900 but sold "
                          "for $600"),
                  ("user", "the bike sold for $400, listed $500"))]
        ans, det = answer_delta(
            "What is the minimum amount I sold the laptop and the "
            "bike for?", s)
        self.assertEqual(ans, "$1,000")
        self.assertEqual(det["op"], "minmax")

    def test_rate_cashback(self):
        s = [sess(("user", "My Bank of America card gives 1% cashback"),
                  ("user", "I bought $75 of groceries with my Bank "
                           "of America card"))]
        ans, det = answer_delta(
            "How much cashback did I get with my Bank of America "
            "card?", s)
        self.assertEqual(ans, "$0.75")
        self.assertEqual(det["op"], "rate")

    def test_count_ratio(self):
        s = [sess(("user", "I packed 5 pairs of shoes for the trip"),
                  ("user", "I ended up wearing two pairs of shoes"))]
        ans, det = answer_delta(
            "What percentage of packed shoes did I wear on my last "
            "trip?", s)
        self.assertEqual(ans, "40%")
        self.assertEqual(det["op"], "ratio")

    def test_pct_price_requires_originally(self):
        s = [sess(("user", "The jacket was originally $30"),
                  ("user", "I haggled the jacket down and paid $24"))]
        ans, det = answer_delta(
            "What percentage discount did I get on the jacket?", s)
        self.assertEqual(ans, "20%")
        self.assertEqual(det["op"], "pct-price")

    def test_t_diff_mpg(self):
        s = [sess(("user", "My car was getting 30 miles per gallon a "
                           "few months ago"),
                  ("user", "now it only does 28 miles per gallon"))]
        ans, det = answer_delta(
            "How much more miles per gallon was my car getting a few "
            "months ago compared to now?", s)
        self.assertEqual(ans, "2")
        self.assertEqual(det["op"], "t_diff")

    def test_t_diff_requires_user_role_both_sides(self):
        s = [sess(("user", "I ran the 5K in 45 minutes last year"),
                  ("assistant", "Your pace now suggests about 35 "
                                "minutes"))]
        ans, _ = answer_delta(
            "How much faster did I finish the 5K run this year?", s)
        # assistant-side new value → no answer, honest fall-through
        self.assertIsNone(ans)

    def test_cmp_pct_yes_no(self):
        s = [sess(("user", "Hobby Lobby coupon was 40% off"),
                  ("user", "Michaels only gave 20% off"))]
        ans, det = answer_delta(
            "Did I get a better percentage discount at Hobby Lobby "
            "compared to Michaels?", s)
        self.assertEqual(ans, "Yes.")
        self.assertEqual(det["op"], "cmp-pct")


class TestPickDiscipline(unittest.TestCase):
    """Every constraint in _dl_pick is load-bearing (#086 arc)."""

    def test_range_lines_skipped(self):
        s = [sess(("user", "I want to spend $50 to $200 on a gift"),
                  ("user", "the scarf cost $60"))]
        ans, _ = answer_delta(
            "How much did I spend on the scarf?", s)
        # single-entity how-much is not a delta form at all
        self.assertIsNone(ans)

    def test_unit_ctx_per_night(self):
        s = [sess(("user", "The Maui resort quoted $300 per night"),
                  ("user", "my Tokyo hostel was $30 per night"),
                  ("user", "Tokyo food budget around $500 total"))]
        ans, det = answer_delta(
            "How much more per night was the Maui resort compared to "
            "my Tokyo hostel?", s)
        self.assertEqual(ans, "$270")
        self.assertEqual(det["op"], "diff")

    def test_cross_side_strict_majority(self):
        # strict > (not >=): a line mentioning both sides ONCE each
        # is a legitimate transition narrative — kept, decided by
        # distance; a line where the OTHER side dominates (2 vs 1)
        # is skipped
        cands = [(12.0, 0, "user",
                  "I missed my train so took a taxi for $12", "$12"),
                 (6.0, 0, "user",
                  "the train ticket would have been $6", "$6")]
        # taxi side: transition line kept (train count 1 !> taxi 1)
        got = abq._dl_pick(cands, ["taxi"], exclude=["train"])
        self.assertEqual(got[0], 12.0)
        # ...but a line dominated by the other side is excluded
        biased = [(6.0, 0, "user",
                   "the train fare and train schedule said $6",
                   "$6")]
        self.assertIsNone(abq._dl_pick(biased, ["taxi"],
                                        exclude=["train"]))

    def test_hawaii_lexicon_side_expansion(self):
        s = [sess(("user", "The hotel in Maui was $300 per night"),
                  ("user", "my Tokyo stay was $30 per night"))]
        ans, _ = answer_delta(
            "How much more per night was Hawaii compared to Tokyo?",
            s)
        self.assertEqual(ans, "$270")

    def test_user_role_beats_assistant(self):
        s = [sess(("assistant", "Tokyo hostels typically run $120 per "
                                "night"),
                  ("user", "my Tokyo hostel was $30 per night"),
                  ("user", "The Maui resort quoted $300 per night"))]
        ans, _ = answer_delta(
            "How much more per night was the Maui resort compared to "
            "my Tokyo hostel?", s)
        self.assertEqual(ans, "$270")


class TestPipeline(unittest.TestCase):
    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "the boots were $800"},
                {"role": "user", "content": "gloves only $50"}]}])
        return a

    def test_gate_label_delta_agg(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "How much more did the boots cost compared to the "
            "gloves?", "")
        self.assertEqual(ans, "$750")
        self.assertEqual(meta["gate"], "delta_agg")
        self.assertFalse(meta["abstained"])
        self.assertEqual(meta["delta"]["op"], "diff")

    def test_no_delta_flag_isolates(self):
        a = self._adapter(delta_agg=False)
        ans, meta = a.answer_extractive(
            "How much more did the boots cost compared to the "
            "gloves?", "")
        self.assertNotEqual(meta["gate"], "delta_agg")

    def test_miss_falls_through_not_abstain(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "we talked about food"}]}])
        ans, meta = a.answer_extractive(
            "How much more did the boots cost compared to the "
            "gloves?", "")
        # unresolved delta → fall-through, gates own abstention —
        # the answer must NOT be a delta IDK
        self.assertNotEqual(meta["gate"], "delta_agg")


if __name__ == "__main__":
    unittest.main()
