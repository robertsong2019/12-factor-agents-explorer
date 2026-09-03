#!/usr/bin/env python3
"""C544 face tests: paren-complement + tense-superset reference faces.

Live fixtures from the C544 census (full-500 population):
- c6853660: GT 'You increased the limit (from one cup to two cups)' vs
  answer 'I have increased the limit to two cups'  -> CORRECT
- 89527b6b: GT 'The Plesiosaur had a blue scaly body.' vs answer
  'The Plesiosaur has a blue scaly body, and its eyes are fixed ...'
  -> CORRECT

Both faces are NEEDS_JUDGE-zone only: all WRONG paths (number/currency
guards, subset veto) return before the face line, so the faces can
never flip WRONG -> CORRECT and never mask a numeric conflict.
"""
import sys, unittest

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q


class TestParenComplementFace(unittest.TestCase):
    def test_live_fixture_c6853660(self):
        gt = "You increased the limit (from one cup to two cups)"
        ans = ("I'm excited to try out the French press method with my darker "
               "roast. Speaking of my morning coffee, I have increased the "
               "limit to two cups, and I'm thinking of experimenting.")
        self.assertTrue(Q._sem_paren_complement_face(gt, ans))
        self.assertEqual(Q.judge_semantic("did I increase or decrease?", ans, gt),
                         "CORRECT")

    def test_thin_head_excluded(self):
        # head keeps <2 content tokens -> never fires (C544 census guard)
        gt = "Yes. (You have a road bike too.)"
        self.assertFalse(Q._sem_paren_complement_face(gt, "yes I do"))

    def test_no_paren_no_fire(self):
        self.assertFalse(Q._sem_paren_complement_face(
            "plain reference without parens", "plain reference without parens ok"))

    def test_head_tokens_missing_no_fire(self):
        gt = "You increased the limit (from one cup to two cups)"
        self.assertFalse(Q._sem_paren_complement_face(gt, "totally unrelated"))

    def test_nested_paren_conservative(self):
        # nested parens bail out -> conservative no-fire
        gt = "The outer (inner (nested) text) form"
        self.assertFalse(Q._sem_paren_complement_face(
            gt, "the outer inner nested text form"))

    def test_deixis_fold_you_vs_i(self):
        # grader-voiced GT vs user-voiced answer: same fact under deixis
        # shift, fires WITHOUT relying on an incidental 'you' elsewhere
        gt = "You increased the limit (from one cup to two cups)"
        ans = "I have increased the limit to two cups"
        self.assertTrue(Q._sem_paren_complement_face(gt, ans))

    def test_deixis_your_vs_my(self):
        gt = "You brought your lunch (a sandwich)"
        ans = "I brought my lunch and an apple"
        self.assertTrue(Q._sem_paren_complement_face(gt, ans))

    def test_wrong_path_unreachable_number_guard(self):
        # number-conflicting pair stays WRONG even with paren GT shape
        gt = "I got 5 books (hardcover editions)"
        self.assertEqual(Q.judge_semantic("how many?", "I got 7 books", gt),
                         "WRONG")


class TestTenseSupersetFace(unittest.TestCase):
    def test_live_fixture_89527b6b(self):
        gt = "The Plesiosaur had a blue scaly body."
        ans = ("The Plesiosaur has a blue scaly body, and its eyes are fixed "
               "on something in the distance.")
        self.assertTrue(Q._sem_tense_superset_face(gt, ans))
        self.assertEqual(Q.judge_semantic("what color was the body?", ans, gt),
                         "CORRECT")

    def test_no_tense_words_no_fire(self):
        self.assertFalse(Q._sem_tense_superset_face(
            "blue body", "blue body and green fins"))

    def test_tense_words_but_not_superset_no_fire(self):
        # fold bridges the tense, but GT tokens missing from answer
        self.assertFalse(Q._sem_tense_superset_face(
            "The Plesiosaur had a blue scaly body.",
            "The Plesiosaur has lovely eyes."))

    def test_equal_after_fold_no_fire(self):
        # tense-identical pairs already return CORRECT earlier; equal sets
        # after fold must not fire (strict superset required)
        self.assertFalse(Q._sem_tense_superset_face(
            "it was good", "it is good"))

    def test_was_is_fold(self):
        self.assertTrue(Q._sem_tense_superset_face(
            "The tool was written in Python.",
            "The tool is written in Python with type hints."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
