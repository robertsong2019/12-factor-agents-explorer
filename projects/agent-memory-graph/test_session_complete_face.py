"""Cycle 526: session-completion face rescue.

Census (C526 /tmp/c526, 225 answer-gate questions replayed on HEAD,
C525 included): the token budget is NOT the window-composition
bottleneck — only 5 wrongs have a GT-bearing line beyond the window
in the candidate list (all hits=1), while 105 wrongs never see the
GT line as a candidate at all. Rescue surface: same-session lines
the seed phase missed. Rule: scan face-session messages NOT in the
retrieval window; if one out-hits the face (margin 1, floor 2),
re-face to it (max hits, ties -> latest seq, C437/C447).

Census: +3/−0 over the full population (caf9ead2, c4a1ceb8 new
wins; 6a27ffc2 idempotent on the C525 fix), zero correct touches.
Session-locality is the separator — the same rule unscoped nets
+7/−3 with ALL 3 hijacks cross-session.

The win-scenario tests simulate the census-proven seed-miss state
(an out-hitting same-session line that never became a candidate) by
filtering it from the retrieval window; the block must treat the
remaining window exactly as production does. Negative tests run the
real pipeline end-to-end.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amg_bench_quality import LongMemEvalAdapter


def turn(role, content):
    return {"role": role, "content": content}


Q = ("How many marathons have I finished since joining the "
     "running club last spring?")
FACE = ("I completed another marathon this week and the pacing "
        "felt good.")
PICK = "The spring trail last month was absolutely beautiful."
OTHER = "Club membership has been a wonderful experience for me."


def build(**kw):
    a = LongMemEvalAdapter(**kw)
    a.ingest_sessions([
        {"session_id": "s2", "messages": [
            turn("assistant", OTHER)]},
        {"session_id": "s1", "messages": [
            turn("user", FACE),
            turn("user", PICK)]},
    ])
    return a


def drop_from_window(adapter, body):
    """Simulate the census-proven seed-miss: the line exists in the
    graph but never became a retrieval candidate."""
    real = adapter.retrieve_context

    def patched(question, question_date=""):
        context, meta = real(question, question_date)
        ids = meta.get("retrieved_ids") or []
        keep = [n for n in ids
                if adapter._messages[n]["label"] != body]
        meta["retrieved_ids"] = keep
        lines = [ln for ln in context.split("\n")
                 if ln.split("] ", 1)[-1] != body]
        return "\n".join(lines), meta

    adapter.retrieve_context = patched
    return adapter


class TestSessionCompleteFace(unittest.TestCase):
    def test_same_session_rescue_fires(self):
        a = drop_from_window(build(), PICK)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, PICK)
        scf = meta["session_complete_face"]
        self.assertTrue(scf["override"])
        self.assertEqual(scf["face_session"], "s1")
        self.assertGreaterEqual(scf["candidate_hits"], 2)

    def test_switch_off_leaves_answer(self):
        a = drop_from_window(build(session_complete_face=False), PICK)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, FACE)
        self.assertNotIn("session_complete_face", meta)

    def test_cross_session_line_never_rescues(self):
        # PICK lives in s2 (cross-session), out-hits the face AND is
        # out-of-window (seed-miss): it must NOT be pulled in — the
        # a9f6b44c hijack family guard. Only SAME-session completion
        # is in scope.
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s2", "messages": [
                turn("assistant", OTHER),
                turn("assistant", PICK)]},
            {"session_id": "s1", "messages": [
                turn("user", FACE)]},
        ])
        drop_from_window(a, PICK)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, FACE)
        scf = meta["session_complete_face"]
        self.assertFalse(scf["override"])

    def test_equal_hits_tie_does_not_fire(self):
        # Same-session out-of-window line with hits == face hits:
        # below the margin (needs face_hits + 1) — the answer stays
        # untouched. STRONG (h=2) is the face; tie (h=1) is out-of-
        # window same-session — far below the margin 3.
        strong = ("The marathon club means a lot to my weekly "
                  "routine.")
        tie = "Marathon training continues for me personally."
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s2", "messages": [
                turn("assistant", OTHER)]},
            {"session_id": "s1", "messages": [
                turn("user", FACE),
                turn("user", strong),
                turn("user", tie)]},
        ])
        drop_from_window(a, tie)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, strong)
        scf = meta["session_complete_face"]
        self.assertFalse(scf["override"])
        self.assertEqual(scf["candidate_hits"], 0)

    def test_fall_through_no_same_session_candidate(self):
        # All window lines in one session, no out-of-window
        # same-session lines: block records no-override and the
        # answer is untouched (C488 fall-through).
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("user", FACE),
                turn("user", "I ran the club race last weekend and "
                             "enjoyed it with many friends.")]},
        ])
        ans, meta = a.answer_extractive(Q, "")
        scf = meta["session_complete_face"]
        self.assertFalse(scf["override"])
        self.assertEqual(scf["candidate_hits"], 0)


if __name__ == "__main__":
    unittest.main()
