#!/usr/bin/env python3
"""C547 face test: affirm-elaboration reference face
(_sem_affirm_elaboration_face).

Live fixture from the C547 census (affirmation-led GT population across
the full-500 = 6 rows, only one carries an elaboration rest):
- 89941a94: GT 'Yes. (You have a road bike too.)' vs an answer naming
  the road bike among its bikes -> CORRECT. The question's auxiliary
  clause sits behind a preamble ('Before I purchased the gravel bike,
  do I have ...?'), so the C545 bare-affirm face (aux-INITIAL, bare-GT)
  cannot reach it and the C544 paren-complement face excludes it
  (thin head). This face is the complement of both.

Trap rows, all correctly excluded:
- bare-rest GTs ('Yes'/'Yes.') -> bare-affirm's territory, not double-
  handled
- d7c942c3-shape: pred contradicts GT (coverage gate)
- negative elaboration (polarity gate) -> stays NEEDS_JUDGE
- wh-question without a yes/no aux+I clause (question-form gate)
- answer missing a fact token (coverage gate)
- negation window / interrogative echo gates

The face is NEEDS_JUDGE-zone only: number/currency guards and the
subset veto return WRONG before the face line, so it can never flip
WRONG -> CORRECT and never mask a numeric conflict.
"""
import sys, unittest

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q

Q_BIKES = ("Before I purchased the gravel bike, do I have other bikes in "
           "addition to my mountain bike and my commuter bike?")
A_BIKES = ("That sounds like an amazing itinerary! I'm really excited "
           "about the scenic routes and bike-friendly stops. Since I'll "
           "have four bikes with me, I'll make sure to book the "
           "accommodations with bike storage in advance to ensure they can "
           "accommodate all my bikes. By the way, speaking of bikes, I "
           "just got a new one recently, so I'll actually have four bikes "
           "with me on this trip - my road bike, mountain bike, commuter "
           "bike, and a new hybrid bike I just purchased.")
GT_BIKES = "Yes. (You have a road bike too.)"


class TestAffirmElaborationFace(unittest.TestCase):
    def test_live_fixture_89941a94(self):
        # aux-behind-preamble question + elaborated affirmation GT
        self.assertTrue(Q._sem_affirm_elaboration_face(
            Q_BIKES, A_BIKES, GT_BIKES))
        self.assertEqual(Q.judge_semantic(Q_BIKES, A_BIKES, GT_BIKES),
                         "CORRECT")

    def test_bare_affirm_cannot_reach_fixture(self):
        # the new face extends bare-affirm (not duplicates it)
        self.assertFalse(Q._sem_bare_affirm_face(Q_BIKES, A_BIKES, GT_BIKES))

    def test_bare_rest_stays_with_bare_affirm(self):
        q = "Do I have a spare screwdriver for opening up my laptop?"
        self.assertFalse(Q._sem_affirm_elaboration_face(q, "I think so.",
                                                        "Yes"))
        self.assertFalse(Q._sem_affirm_elaboration_face(q, "I think so.",
                                                        "Yes."))

    def test_contradiction_coverage_excluded(self):
        # d7c942c3 shape: GT affirms mom uses the method; pred says
        # she doesn't — fact tokens (method) absent -> coverage gate
        q = "Is my mom using the same grocery list method as me?"
        ans = ("I've been trying to get my mom to use it too, but she's "
               "still stuck on her old paper list.")
        self.assertFalse(Q._sem_affirm_elaboration_face(
            q, ans, "Yes. (Your mom uses the same grocery list method.)"))

    def test_negative_elaboration_polarity_gate(self):
        # a negated elaboration asserts a negated fact; dropping the
        # negator would let a contradicting answer fire -> abstain
        q = "Did I sell my old record player at the flea market?"
        self.assertFalse(Q._sem_affirm_elaboration_face(
            q, "I did sell it at the flea market last spring.",
            "Yes. (You did not sell it.)"))

    def test_wh_question_form_excluded(self):
        # no yes/no aux+I clause anywhere -> question-form gate
        q = "What other bikes do I have in addition to my mountain bike?"
        self.assertFalse(Q._sem_affirm_elaboration_face(
            q, A_BIKES, GT_BIKES))

    def test_non_interrogative_excluded(self):
        q = ("Before I purchased the gravel bike, I wondered about other "
             "bikes in addition to my mountain bike and my commuter bike")
        self.assertFalse(Q._sem_affirm_elaboration_face(
            q, A_BIKES, GT_BIKES))

    def test_missing_fact_token_excluded(self):
        # answer never names the elaboration's fact token 'road'
        ans = ("Since I'll have four bikes with me, I'll make sure to book "
               "the accommodations with bike storage in advance.")
        self.assertFalse(Q._sem_affirm_elaboration_face(
            Q_BIKES, ans, GT_BIKES))

    def test_negation_window_excluded(self):
        ans = ("Since I'll have four bikes with me on this trip - my "
               "mountain bike, commuter bike, and a hybrid - I really "
               "don't have a road bike, so we should plan shorter rides.")
        self.assertFalse(Q._sem_affirm_elaboration_face(
            Q_BIKES, ans, GT_BIKES))

    def test_interrogative_echo_excluded(self):
        ans = ("Sounds fun! Do I actually have a road bike among my bikes? "
               "I only remember the mountain, commuter and hybrid ones.")
        self.assertFalse(Q._sem_affirm_elaboration_face(
            Q_BIKES, ans, GT_BIKES))

    def test_number_guard_precedence(self):
        # numeric conflict returns WRONG before the NEEDS_JUDGE face
        # zone: the face can never mask it
        q = "Do I have two bikes in addition to my mountain bike?"
        ans = "I actually own five bikes these days."
        self.assertEqual(Q.judge_semantic(
            q, ans, "Yes. (You have two other bikes.)"), "WRONG")


if __name__ == "__main__":
    unittest.main()
