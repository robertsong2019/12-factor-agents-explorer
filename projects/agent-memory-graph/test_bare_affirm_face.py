#!/usr/bin/env python3
"""C545 face test: bare-affirmation reference face (_sem_bare_affirm_face).

Live fixture from the C545 census (full-500 population, 5 bare-yes rows):
- b01defab: GT 'Yes' vs an answer that affirms the questioned predicate
  narratively ('... which I finished reading recently') -> CORRECT

Trap rows from the same census, all correctly excluded:
- 42ec0761: question-back form (interrogative echo gate)
- d7c942c3: pred contradicts GT (coverage gate: 'same'/'method' absent)
- c4ea545c: unrelated topic (coverage gate: 'gym' absent)
- 0bc8ad93: GT is a 'No, ...' sentence, not a bare affirmation

The face is NEEDS_JUDGE-zone only: number/currency guards and the
subset veto return WRONG before the face line, so it can never flip
WRONG -> CORRECT and never mask a numeric conflict.
"""
import sys, unittest

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q

Q_NIGHT = "Did I finish reading 'The Nightingale' by Kristin Hannah?"
A_NIGHT = ("I'll definitely check out those online communities and book "
           "clubs. I'm excited to connect with more readers who share my "
           "interests. By the way, I was thinking about \"The Nightingale\" "
           "by Kristin Hannah, which I finished reading recently. It was "
           "such a powerful and emotional read.")


class TestBareAffirmFace(unittest.TestCase):
    def test_live_fixture_b01defab(self):
        self.assertTrue(Q._sem_bare_affirm_face(Q_NIGHT, A_NIGHT, "Yes"))
        self.assertEqual(Q.judge_semantic(Q_NIGHT, A_NIGHT, "Yes"), "CORRECT")

    def test_interrogative_echo_excluded(self):
        # 42ec0761: answer asks the question back; its hit-sentence
        # ends with '?' -> echo gate blocks
        q = "Do I have a spare screwdriver for opening up my laptop?"
        ans = ("I think I'll go with Backblaze, thanks for the info. By the "
               "way, I need to open up my laptop to clean the fans soon, do "
               "I have a spare screwdriver for that?")
        self.assertFalse(Q._sem_bare_affirm_face(q, ans, "Yes"))
        self.assertNotEqual(Q.judge_semantic(q, ans, "Yes"), "CORRECT")

    def test_contradiction_coverage_excluded(self):
        # d7c942c3: GT says mom uses the same method; pred says she
        # doesn't ('still stuck on her old paper list') — coverage gate
        # ('same', 'method' absent) blocks before any rescue
        q = "Is my mom using the same grocery list method as me?"
        ans = ("That sounds like a great recipe! I'm definitely going to "
               "give it a try. By the way, I'm glad I'm not the only one "
               "who's a fan of that new grocery list app. I've been trying "
               "to get my mom to use it too, but she's still stuck on her "
               "old paper list.")
        self.assertFalse(Q._sem_bare_affirm_face(q, ans, "Yes."))
        self.assertNotEqual(Q.judge_semantic(q, ans, "Yes."), "CORRECT")

    def test_offtopic_coverage_excluded(self):
        # c4ea545c: gym question answered with aquarium water changes
        q = "Do I go to the gym more frequently than I did previously?"
        ans = ("I've been doing 25% water changes every 2 weeks. Do you "
               "think I should do them more frequently, like once a week?")
        self.assertFalse(Q._sem_bare_affirm_face(q, ans, "Yes"))
        self.assertNotEqual(Q.judge_semantic(q, ans, "Yes"), "CORRECT")

    def test_non_bare_gt_never_fires(self):
        # 0bc8ad93: 'No, ...' sentence reference is out of scope, and a
        # plain narrative reference never fires the bare-affirm gate
        self.assertFalse(Q._sem_bare_affirm_face(
            Q_NIGHT, A_NIGHT, "No, you did not finish it."))
        self.assertFalse(Q._sem_bare_affirm_face(
            Q_NIGHT, A_NIGHT, "You finished it last month."))

    def test_negation_window_blocks(self):
        ans = ("I didn't finish reading The Nightingale by Kristin Hannah, "
               "I abandoned it halfway.")
        self.assertFalse(Q._sem_bare_affirm_face(Q_NIGHT, ans, "Yes"))
        self.assertNotEqual(Q.judge_semantic(Q_NIGHT, ans, "Yes"), "CORRECT")

    def test_non_aux_question_never_fires(self):
        # not an auxiliary-initial yes/no question -> gate 2
        self.assertFalse(Q._sem_bare_affirm_face(
            "Tell me about my reading of The Nightingale by Kristin Hannah.",
            A_NIGHT, "Yes"))

    def test_wrong_path_precedes_face(self):
        # numeric conflict returns WRONG before the face is consulted
        ans = ("I finished reading The Nightingale by Kristin Hannah, and I "
               "read exactly 3 other books that month.")
        self.assertEqual(Q.judge_semantic(Q_NIGHT, ans, "7"), "WRONG")


if __name__ == "__main__":
    unittest.main(verbosity=2)
