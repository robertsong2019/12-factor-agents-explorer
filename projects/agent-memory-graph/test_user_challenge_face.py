"""Cycle 548: cross-session user-statement challenge face.

Census (/tmp/c548/census_user.py, 187 answer-gate rows: 50
banked-correct seed-7 sample + all 137 banked-wrong at C547 HEAD):
a line OUTSIDE the retrieval window that outranks the stored winner
under production ranking (-hits,-seq) is promoted ONLY when it is
role=user AND cross-session AND phrase-run dominant (run > win_run,
floor 2, C540 primitive). Census verdicts: 5 RESCUE (c8c3f81d,
8ebdbe50, c19f7a0b, gpt4_5dcc0aab, f523d9fe — live fixtures) / 0
KILL / 0 kill-side triggers of 50.

The kill-surface context: C546 censused PLAIN kh-elite admission at
7/30 KILL (14%) — assistant empathy preambles are the impostor
family. First census pass here showed 2/2 kill-side triggers were
assistant lines while all 5 rescues were user lines — the role gate
IS the separator, so every negative test below pins one of the
three gates (role / session / phrase-run) against the exact
hijack shape it excludes.

The multi-line winner test pins the C525 context-split trap: the
window line of a multi-paragraph message is its FIRST line only;
the face must match the winner on the label's first line (live
smoke on c19f7a0b/f523d9fe caught face_found=False before the
fix — this test was red before the first-line fix landed).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amg_bench_quality import (LongMemEvalAdapter, answer_user_challenge,
                               _keyword_hits, _keywords)


def turn(role, content):
    return {"role": role, "content": content}


Q = "What size tent did I buy for camping?"

WINNER = ("A great tent makes camping comfortable, and size "
          "matters a lot.")            # assistant, kh=3, run=0
CHALLENGER = ("The size tent I did buy for camping fits six "
              "people.")               # user, kh=4, run=2
OTHER = "The weather was lovely yesterday."  # kh=0 filler


def build(**kw):
    a = LongMemEvalAdapter(**kw)
    a.ingest_sessions([
        {"session_id": "s1", "messages": [
            turn("assistant", WINNER),
            turn("assistant", OTHER)]},
        {"session_id": "s2", "messages": [
            turn("user", CHALLENGER)]},
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


class TestUserChallengeFace(unittest.TestCase):
    def test_census_shape_rescue_fires(self):
        # The 5-row census rescue shape: user line, other session,
        # outranks the window winner, carries the question's own
        # phrase-run — promoted over the assistant echo.
        a = drop_from_window(build(), CHALLENGER)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, CHALLENGER)
        uc = meta["user_challenge_face"]
        self.assertTrue(uc["override"])
        self.assertTrue(uc["face_found"])
        self.assertEqual(uc["win_kh"], 3)
        self.assertEqual(uc["win_run"], 0)
        self.assertEqual(uc["candidate_run"], 2)

    def test_assistant_challenger_blocked(self):
        # The C546 impostor family (7/30 KILL under plain admission):
        # an assistant line that outranks the winner must NEVER be
        # pulled in — the role gate is the kill-surface separator.
        imposter = ("The size tent I would suggest for camping is "
                    "spacious.")     # assistant, kh=4, run=2
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", WINNER),
                turn("assistant", OTHER)]},
            {"session_id": "s2", "messages": [
                turn("assistant", imposter)]},
        ])
        drop_from_window(a, imposter)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_same_session_blocked(self):
        # Same-session repair is C526's territory. kh-tie + later-seq
        # escapes C526's strictly-higher margin but must stay blocked
        # here (cross-session gate).
        tie = "My size tent plans for camping are on hold."  # kh=3
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", WINNER),
                turn("user", tie)]},   # same session, later seq
            {"session_id": "s2", "messages": [
                turn("assistant", OTHER)]},
        ])
        drop_from_window(a, tie)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        self.assertFalse(meta["session_complete_face"]["override"])
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_kh_tie_later_seq_fires_cross_session(self):
        # Outrank gate second arm: kh == win_kh with later seq ranks
        # above the winner under production (-hits,-seq) — fires when
        # user + cross-session + run-dominant.
        tie = "My size tent plans for camping are on hold."  # kh=3, run 0
        # run-dominant variant (2-run): "size tent" contiguous
        tie_run = "The size tent of our camping club is legendary."
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", WINNER)]},
            {"session_id": "s2", "messages": [
                turn("user", tie)]},   # kh=3 tie, later seq, run 0
            {"session_id": "s3", "messages": [
                turn("user", tie_run)]},  # kh=3 tie, later, run 2
        ])
        drop_from_window(a, tie)
        drop_from_window(a, tie_run)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, tie_run)
        uc = meta["user_challenge_face"]
        self.assertTrue(uc["override"])
        self.assertEqual(uc["win_kh"], 3)
        self.assertEqual(uc["candidate_kh"], 3)

    def test_run_gate_blocks_weak_phrase(self):
        # Outranks (kh tie + later seq) but carries NO 2-run of the
        # question's keyword sequence — bag-of-hits is not phrase
        # evidence (C540 primitive), stays blocked.
        weak = "I bought it for camping and a size was included."
        self.assertEqual(_kw_phrase_run_guard(weak), 0)
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", WINNER)]},
            {"session_id": "s2", "messages": [
                turn("user", weak)]},
        ])
        drop_from_window(a, weak)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_outrank_gate_blocks_weaker_kh(self):
        # Run-dominant but kh BELOW the winner: never outranks under
        # production ranking — the face is a ranker-faithful
        # promotion, not a reranker.
        weaker = "A size tent for six people."   # kh=2, run=2
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", WINNER)]},
            {"session_id": "s2", "messages": [
                turn("user", weaker)]},
        ])
        drop_from_window(a, weaker)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_multiline_winner_rescues(self):
        # C525 context-split trap: a multi-paragraph winner enters
        # the window as its FIRST line only. The face must match the
        # winner on the label's first line (RED before the fix —
        # live smoke c19f7a0b/f523d9fe face_found=False) and rescue.
        multi = (WINNER + "\n\nCampers often forget to plan the "
                 "budget for the trip.")
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", multi)]},
            {"session_id": "s2", "messages": [
                turn("user", CHALLENGER)]},
        ])
        drop_from_window(a, CHALLENGER)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, CHALLENGER)
        uc = meta["user_challenge_face"]
        self.assertTrue(uc["override"])
        self.assertEqual(uc["win_run"], 0)

    def test_flag_off_leaves_answer(self):
        a = drop_from_window(build(user_challenge_face=False),
                             CHALLENGER)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        self.assertNotIn("user_challenge_face", meta)

    def test_face_not_found_bails(self):
        line, detail = answer_user_challenge("[user] no such line",
                                             ["ghost-id"], {}, [])
        self.assertIsNone(line)
        self.assertFalse(detail["face_found"])
        self.assertFalse(detail["override"])

    def test_census_keywords_fixture_sanity(self):
        # The fixture geometry the gates above rely on.
        kws = _keywords(Q)
        self.assertGreaterEqual(len(kws), 3)
        self.assertEqual(_keyword_hits(WINNER, kws), 3)
        self.assertEqual(_keyword_hits(CHALLENGER, kws), 4)


def _kw_phrase_run_guard(label):
    # local import shim kept at bottom so the test docstrings stay
    # the primary documentation surface
    from amg_bench_quality import _kw_phrase_run
    return _kw_phrase_run(label, _keywords(Q))


if __name__ == "__main__":
    unittest.main()
