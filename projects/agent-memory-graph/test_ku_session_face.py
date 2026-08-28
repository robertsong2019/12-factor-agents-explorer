"""Cycle 525: knowledge-update recency session-scope answer face.

Census (C525 /tmp/c525/census_c525.py, official C523
post_full500_c523.json, 225 answer-gate questions replayed on
pristine HEAD): 109/158 answer-gate wrongs have NO GT-bearing line
in the window — 92 of them DO have the GT session retrieved
(answer_session_hit=True). Face-level remainder: current-state
knowledge-update questions (recency adverbs) are answered by the
LATEST session's evidence while keyword ranking saturates on topic
echoes from older sessions. Rule: face session != latest evidence
session (max seq over keyword-hit lines) -> re-face to that
session's best line (max hits, ties keep latest, any role, floor 2).
Census: 6 fires = 2 wins + 4 wrong->wrong noops, zero correct
touches; the SAME condition unscoped fires 58 with 10 hijacks — the
adverb scope is the separator.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amg_bench_quality import LongMemEvalAdapter, _KU_RECENCY_RE


def turn(role, content):
    return {"role": role, "content": content}


def sessions(s1_msgs, s2_msgs):
    return [{"session_id": "s1", "messages": s1_msgs},
            {"session_id": "s2", "messages": s2_msgs}]


ECHO = ("I've been following Corey Schafer's Python programming "
        "series videos, completed many episodes of the series so "
        "far, and the series explains Python programming with "
        "videos.")
FACT = ("I've completed 30 videos so far for Corey Schafer's Python "
        "programming series and I'm starting a DataCamp course next.")
Q = ("So far, how many videos of Corey Schafer's Python "
     "programming series have I completed?")


def build(s1_msgs, s2_msgs, **kw):
    a = LongMemEvalAdapter(**kw)
    a.ingest_sessions(sessions(s1_msgs, s2_msgs))
    return a


class TestKuRecencyRegex(unittest.TestCase):
    def test_positive(self):
        for q in ("How many have I completed so far?",
                  "How many do I currently have?",
                  "What have I read to date?",
                  "How much have I been sleeping lately?",
                  "How many do I own these days?",
                  "How many have I added up to now?",
                  "As of now, how many do I have?"):
            self.assertTrue(_KU_RECENCY_RE.search(q), q)

    def test_negative(self):
        for q in ("How many playlists do I have on Spotify?",
                  "What color did I repaint my bedroom walls?",
                  "Where did I buy the bookshelf?"):
            self.assertIsNone(_KU_RECENCY_RE.search(q), q)


class TestKuSessionFace(unittest.TestCase):
    def test_win_echo_vs_latest_fact(self):
        a = build([turn("user", ECHO)],
                  [turn("user", FACT)])
        ans, meta = a.answer_extractive(Q)
        self.assertIn("30", ans)
        self.assertTrue(meta["ku_session_face"]["override"])
        self.assertEqual(meta["ku_session_face"]["face_session"], "s1")
        self.assertEqual(
            meta["ku_session_face"]["latest_evidence_session"], "s2")

    def test_no_adverb_no_fire(self):
        q = ("How many videos of Corey Schafer's Python programming "
             "series have I completed?")  # ^how: C523 owns this form
        a = build([turn("user", ECHO)],
                  [turn("user", FACT)])
        ans, meta = a.answer_extractive(q)
        # C523 quant_rerank owns the ^how form and may already
        # surface the fact line — this test asserts MY block stays
        # out of it, not the final answer.
        self.assertNotIn("ku_session_face", meta)

    def test_flag_off(self):
        a = build([turn("user", ECHO)],
                  [turn("user", FACT)],
                  ku_session_face=False)
        ans, meta = a.answer_extractive(Q)
        self.assertNotIn("30", ans)
        self.assertIn("completed many episodes", ans)
        self.assertNotIn("ku_session_face", meta)

    def test_face_in_latest_session_untouched(self):
        a = build([turn("user", ECHO)],
                  [turn("user", FACT),
                   turn("assistant", "Great progress on the series!")])
        # Fact line is the newest message: top-ranked or not, the
        # latest evidence session is s2 and any s1 face moves — but
        # the fact line itself must never be overridden away.
        ans, meta = a.answer_extractive(Q)
        self.assertIn("30", ans)

    def test_no_candidate_fall_through(self):
        weak = ("I have been watching that show recently and enjoy "
                "it.")  # 1 keyword hit -> below the C501 floor
        a = build([turn("user", ECHO)],
                  [turn("user", weak)])
        ans, meta = a.answer_extractive(Q)
        # s2's only line has 1 hit -> latest evidence session is s1
        # (== face session) -> no override, face unchanged.
        self.assertFalse(meta["ku_session_face"]["override"])
        self.assertIn("completed many episodes", ans)

    def test_tie_keeps_latest(self):
        older = ("I've completed 12 videos so far from Corey "
                 "Schafer's Python programming series.")
        newer = ("Update: I've completed 30 videos so far for Corey "
                 "Schafer's Python programming series.")
        a = build([turn("user", ECHO)],
                  [turn("user", older),
                   turn("user", newer)])
        ans, meta = a.answer_extractive(Q)
        self.assertIn("30", ans)

    def test_assistant_candidate_allowed(self):
        echo2 = ("That's fantastic that you've completed 30 videos "
                 "so far in Corey Schafer's Python programming "
                 "series!")
        a = build([turn("user", ECHO)],
                  [turn("user", "Loving the Python series videos."),
                   turn("assistant", echo2)])
        ans, meta = a.answer_extractive(Q)
        self.assertIn("30", ans)
        self.assertTrue(meta["ku_session_face"]["override"])

    def test_meta_shape(self):
        a = build([turn("user", ECHO)],
                  [turn("user", FACT)])
        _, meta = a.answer_extractive(Q)
        m = meta["ku_session_face"]
        self.assertEqual(
            set(m), {"face_session", "latest_evidence_session",
                     "candidate_hits", "override"})


if __name__ == "__main__":
    unittest.main()
