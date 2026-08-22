"""C500: enumerated-item money aggregation (item_total form)."""
import unittest

from amg_bench_quality import (
    answer_counting, counting_form, counting_judge,
    _cnt_item_list,
)


def sess(sid, turns):
    return {"session_id": sid, "turns": turns}


def u(text):
    return {"role": "user", "content": text}


class ItemTotalFormTests(unittest.TestCase):

    def test_form_gating(self):
        # money totals route to item_total
        self.assertEqual(
            counting_form("What is the total amount I spent on "
                          "the designer handbag and high-end "
                          "skincare products?"),
            "item_total")
        self.assertEqual(
            counting_form("What was the total cost of the car "
                          "cover and detailing spray I purchased?"),
            "item_total")
        # number/distance/time totals stay on their forms
        self.assertEqual(
            counting_form("What is the total number of siblings "
                          "I have?"),
            "number_total")
        self.assertEqual(
            counting_form("How many hours in total did I spend "
                          "gaming?"),
            "unit_sum")

    def test_item_enumeration(self):
        self.assertEqual(
            _cnt_item_list("What is the total cost of the car "
                           "cover and detailing spray I "
                           "purchased?"),
            [{"car", "cover"}, {"detailing", "spray"}])
        # comma list with final and
        self.assertEqual(
            _cnt_item_list("What is the total amount of the food "
                           "bowl, measuring cup, and flea and tick "
                           "collar?"),
            [{"bowl", "food"}, {"cup", "measuring"},
             {"collar", "flea", "tick"}])
        # possessive normalization
        self.assertEqual(
            _cnt_item_list("What is the total cost of Lola's vet "
                           "visit and flea medication?"),
            [{"lola", "vet", "visit"}, {"flea", "medication"}])
        # container nouns dropped
        self.assertEqual(
            _cnt_item_list("What is the total amount I spent on "
                           "the designer handbag and high-end "
                           "skincare products?"),
            [{"handbag"}, {"skincare"}])

    def test_t1_same_clause_binding(self):
        # real surface form (85fa3a3f): comma-joined purchases
        s = [sess("s1", [u(
            "I just got him a new stainless steel food bowl "
            "from Amazon for $15, and a measuring cup from the "
            "pet store down the street for $5.")])]
        ans, _ = answer_counting(
            "What is the total amount of the food bowl and "
            "measuring cup?", s)
        self.assertEqual(ans, "$20")

    def test_single_clause_two_items_abstains(self):
        # no comma: both items live in ONE clause — per-item
        # attribution is impossible, so the handler abstains
        # rather than guess
        s = [sess("s1", [u(
            "I just got him a food bowl for $15 and a "
            "measuring cup for $5.")])]
        ans, _ = answer_counting(
            "What is the total amount of the food bowl and "
            "measuring cup?", s)
        self.assertIsNone(ans)

    def test_t2_same_sentence_anaphora(self):
        s = [sess("s1", [u(
            "By the way, I also got her flea and tick prevention "
            "medication, it was $25 for a 3-month supply.")])]
        ans, _ = answer_counting(
            "What is the total cost of the flea medication?", s)
        self.assertEqual(ans, "$25")

    def test_t3_adjacent_sentence_strong_face(self):
        s = [sess("s1", [u(
            "Do you know if I can claim the cost of the "
            "waterproof car cover on my car insurance? "
            "I remember it cost me $120, and it's been working "
            "great.")])]
        ans, _ = answer_counting(
            "What is the total cost of the car cover?", s)
        self.assertEqual(ans, "$120")

    def test_t3_weak_face_interrogative_anchor_refused(self):
        s = [sess("s1", [u(
            "Do you know if I can claim the cost of the "
            "waterproof car cover on my car insurance? "
            "It was $120 for the basic version, I think.")])]
        ans, _ = answer_counting(
            "What is the total cost of the car cover?", s)
        self.assertIsNone(ans)

    def test_t4_turn_unique(self):
        s = [sess("s1", [u(
            "I just took Lola to the vet last week and got a "
            "discounted consultation fee of $50.")])]
        ans, _ = answer_counting(
            "What is the total cost of Lola's vet visit?", s)
        self.assertEqual(ans, "$50")

    def test_t4_session_unique_cross_turn(self):
        s = [sess("s1", [
            u("I'm looking for some advice on skincare routines."),
            u("I've recently invested $500 in some high-end "
              "products during the sale, and I want to make sure "
              "I'm using them correctly.")])]
        ans, _ = answer_counting(
            "What is the total amount I spent on the high-end "
            "skincare products?", s)
        self.assertEqual(ans, "$500")

    def test_range_not_a_price(self):
        s = [sess("s1", [u(
            "The flea medication costs $150 to $200 depending on "
            "the dog's weight.")])]
        ans, _ = answer_counting(
            "What is the total cost of the flea medication?", s)
        self.assertIsNone(ans)

    def test_summary_totals_not_per_item_prices(self):
        s = [sess("s1", [u(
            "I bought the handbag and it was great. The total "
            "of $800 covered everything, including the "
            "accessories.")])]
        ans, _ = answer_counting(
            "What is the total cost of the handbag?", s)
        self.assertIsNone(ans)

    def test_recurring_cost_not_counted(self):
        s = [sess("s1", [u(
            "The grain-free kibble is about $50 a month for "
            "Max.")])]
        ans, _ = answer_counting(
            "What is the total cost of the grain-free kibble?",
            s)
        self.assertIsNone(ans)

    def test_unresolvable_item_abstains(self):
        s = [sess("s1", [u(
            "I bought a food bowl for $15 and thought about a "
            "measuring cup but never got one.")])]
        ans, _ = answer_counting(
            "What is the total amount of the food bowl and "
            "measuring cup?", s)
        self.assertIsNone(ans)

    def test_multi_item_sum_with_mixed_tiers(self):
        s = [
            sess("s1", [u(
                "I did get my brother a graduation gift - a $100 "
                "gift card in May.")]),
            sess("s2", [u(
                "My coworker and I exchanged gifts after the baby "
                "shower. The presents were nice, totaling $100.")]),
        ]
        ans, _ = answer_counting(
            "What is the total amount I spent on gifts for my "
            "coworker and brother?", s)
        self.assertEqual(ans, "$200")

    def test_judge_numeric_equivalence(self):
        self.assertTrue(counting_judge(
            "What is the total amount I spent?",
            "$1,300", "$1300"))
        self.assertFalse(counting_judge(
            "What is the total amount I spent?",
            "$1,300", "$800"))


if __name__ == "__main__":
    unittest.main()
