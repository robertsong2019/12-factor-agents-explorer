"""C562: category-sum face — "total spent on luxury items" family.

counting_form() routes "What is the total amount I spent on ..."
to item_total (C500), but the enumerated-item machinery dies at
the first guard: _cnt_item_list("luxury items") is EMPTY — a
category is not an item list — so the row fell through to the
gate chain's answer path (36b9f61e, GT $2,500 = 800 + 1,200 + 500,
verdict WRONG). Census (500 rows, /tmp/c562/step1_census.py):
exactly 8 rows route to item_total — 6 banked via T1-T4b, this
row unbanked with empty items, and the two other unbanked rows
(2b8f3739 earnings qty*price, e5ba910e_abs enumerated-abstention)
are structurally OUTSIDE this face.

Evidence verified from raw haystack, user-role only
(/tmp/c562/step2_evidence.py) — three splurge anchors, each
carrying exactly one price:
  s13  "...splurge on luxury items...bought a luxury evening gown
        for a wedding." → NEXT user sentence "It was a big
        purchase, $800, ..." (same-turn anaphora)
  s15  "...splurge on luxury items...designer handbag I just got
        from Gucci for $1,200..." (same-sentence)
  s32  "...made some luxury purchases, like a pair of leather
        boots from a high-end Italian designer that I got for
        $500." (same-sentence; no splurge verb needed)
Excluded by construction: assistant lifestyle math (even a
literal $2,500 discretionary-income example), non-category
purchases (H&M $20 graphic tees), intent planning lines, ranges,
multi-price ambiguous anchors.
"""
import os
import sys
import unittest

if os.environ.get("PYTHONHASHSEED") != "7":
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "PYTHONHASHSEED": "7"})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amg_bench_quality import (answer_counting, counting_form,
                               _cnt_item_list, _cnt_item_total)


def sess(*turns):
    """(*turns) → one evidence session; each turn is (role, content)."""
    return [{"session_id": "s0",
             "turns": [{"role": r, "content": c} for r, c in turns]}]


def multi(*sessions):
    """each arg is a sess() output; concatenate."""
    out = []
    for s in sessions:
        out.extend(s)
    return out


Q_LUX = ("What is the total amount I spent on luxury items in the "
         "past few months?")
Q_EARN = ("What is the total amount of money I earned from selling "
          "my products at the markets?")
Q_IPAD = "What is the total cost of my recently purchased headphones and the iPad?"
Q_LOLA = "What is the total cost of Lola's vet visit and flea medication?"


class TestCategorySumGate(unittest.TestCase):
    def test_form_routes_as_item_total_unchanged(self):
        # routing was never broken — the face is inside the lane
        self.assertEqual(counting_form(Q_LUX), "item_total")

    def test_item_list_empty_on_category_question(self):
        # the root cause: 'luxury items' is a category, not items
        self.assertEqual(_cnt_item_list(Q_LUX), [])

    def test_gate_requires_category_and_spend(self):
        # earnings/other empty-list questions stay None
        self.assertIsNone(_cnt_item_total(
            Q_EARN,
            sess(("user", "I sold 15 jars of honey at the market "
                          "for $12 each."))))


class TestCategorySumSameSentence(unittest.TestCase):
    def test_handbag_1200_s15_verbatim(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I've been noticing that I tend to splurge on "
                     "luxury items every now and then, like that "
                     "designer handbag I just got from Gucci for "
                     "$1,200, but I also try to balance it out with "
                     "more budget-friendly options.")))
        self.assertEqual(out, "$1200")

    def test_boots_500_no_splurge_verb_s32_verbatim(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "But I've also made some luxury purchases, "
                     "like a pair of leather boots from a high-end "
                     "Italian designer that I got for $500.")))
        self.assertEqual(out, "$500")

    def test_multi_price_anchor_skipped_not_guessed(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I made some luxury purchases lately, like "
                     "boots for $500 and a belt for $200.")))
        self.assertIsNone(out)


class TestCategorySumNextSentence(unittest.TestCase):
    def test_gown_800_same_turn_anaphora_s13_verbatim(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I've been noticing that I tend to splurge on "
                     "luxury items when I'm feeling stressed or "
                     "celebratory, like when I recently bought a "
                     "luxury evening gown for a wedding."),
            ("user", "It was a big purchase, $800, but I felt like "
                     "I needed to make a good impression.")))
        self.assertEqual(out, "$800")

    def test_next_sentence_requires_cost_face(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I splurge on luxury items sometimes, like the "
                     "silk scarf I mentioned."),
            ("user", "It was lovely at the party.")))
        self.assertIsNone(out)


class TestCategorySumSum(unittest.TestCase):
    def test_three_sessions_full_2500_end_to_end(self):
        ans, detail = answer_counting(Q_LUX, multi(
            sess(
                ("user", "I've been noticing that I tend to splurge "
                         "on luxury items when I'm feeling stressed "
                         "or celebratory, like when I recently "
                         "bought a luxury evening gown for a "
                         "wedding."),
                ("user", "It was a big purchase, $800, but I felt "
                         "like I needed to make a good "
                         "impression.")),
            sess(
                ("user", "I've been noticing that I tend to splurge "
                         "on luxury items every now and then, like "
                         "that designer handbag I just got from "
                         "Gucci for $1,200, but I also try to "
                         "balance it out with more budget-friendly "
                         "options.")),
            sess(
                ("user", "But I've also made some luxury purchases, "
                         "like a pair of leather boots from a "
                         "high-end Italian designer that I got for "
                         "$500."))))
        self.assertEqual(ans, "$2500")
        self.assertEqual(detail.get("form"), "item_total")


class TestCategorySumExclusions(unittest.TestCase):
    def test_assistant_lifestyle_math_ignored(self):
        # s15 assistant even contains a literal $2,500 — but the
        # discipline is user-role evidence only
        out = _cnt_item_total(Q_LUX, sess(
            ("assistant", "Your discretionary income would be $1,500 "
                          "($4,000 - $2,500)."),
            ("assistant", "If you allocate 15%, that would be $225 "
                          "per month.")))
        self.assertIsNone(out)

    def test_non_luxury_purchase_ignored(self):
        # s32 H&M tees — bought, but not the question's category
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "For instance, I recently bought a pack of "
                     "graphic tees from H&M for $20, which is a "
                     "steal.")))
        self.assertIsNone(out)

    def test_intent_planning_lines_poisoned(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I'm thinking of buying a luxury watch for "
                     "$2,000 next month.")))
        self.assertIsNone(out)
        out2 = _cnt_item_total(Q_LUX, sess(
            ("user", "I'm considering splurging on a high-end "
                     "desk chair.")))
        self.assertIsNone(out2)

    def test_range_only_anchor_yields_nothing(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "I splurged on luxury items worth $500-$700 "
                     "last quarter.")))
        self.assertIsNone(out)

    def test_no_anchors_falls_through_untouched(self):
        out = _cnt_item_total(Q_LUX, sess(
            ("user", "Been busy with work lately."),
            ("assistant", "That sounds demanding — remember to "
                          "rest.")))
        self.assertIsNone(out)


class TestCategorySumLaneSafety(unittest.TestCase):
    def test_enumerated_row_still_binds(self):
        # C500 T1/T3 lane on a real banked shape (Lola's vet)
        out = _cnt_item_total(Q_LOLA, sess(
            ("user", "I took Lola for her vet visit yesterday."),
            ("user", "The vet visit was $50, and the flea "
                     "medication was $25.")))
        self.assertEqual(out, "$75")

    def test_enumerated_abstention_row_untouched(self):
        # e5ba910e_abs verbatim shape: headphones bind (T1 $378),
        # but iPad is NEVER mentioned in user text (that's why the
        # GT abstains) — no kw predicate anywhere, so the question
        # must keep falling through (abstention lane preserved)
        out = _cnt_item_total(Q_IPAD, sess(
            ("user", "By the way, I recently got a new pair of "
                     "Sony WH-1000XM4 headphones that I use for my "
                     "daily commute."),
            ("user", "The headphones costed me $378, but they've "
                     "been a game-changer."),
            ("user", "By the way, I just got a new phone case for "
                     "my Samsung Galaxy S22 from Case-Mate for "
                     "$30, and it's been working out great.")))
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
