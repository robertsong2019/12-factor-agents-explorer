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

C549 absence pins (census /tmp/c549, 0.540 chain, wrong 218 =
131 answer-gate + 87 non-answer-gate): every run-gate relaxation
with rescue upside is NET-NEGATIVE — R-tie (run >= win_run) +8
rescues vs 2 KILLs of 9 triggers, R-norun +15 vs 3 KILLs of 15
(the run-dominance gate IS the kill-blocker); R-f1 is a no-op.
The two live impostors behind every kill (e66b632c, 10e09553)
are run-TIE shapes: run == win_run with kh dominance — exactly
what the strict `run > win_run` comparator excludes. The two
run-tie pins below go red under any such relaxation. The C526
claimed-first pin freezes the e61a7584 contract: a C526-promoted
same-session winner is a NON-window line, so the challenge face
bails (face_found=False) rather than hijacking the repair.
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

    # ── C549 absence pins: run-gate relaxations are NET-NEGATIVE ──

    WINNER2 = ("The size tent you bought for camping trips "
               "sounds perfect.")   # assistant, kh=3, run=2

    def _build_winner2(self, challenger):
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                turn("assistant", self.WINNER2)]},
            {"session_id": "s2", "messages": [
                turn("user", challenger)]},
        ])
        return drop_from_window(a, challenger)

    def test_run_tie_impostor_blocked(self):
        # e66b632c/10e09553 shape (C549 census): user cross-session
        # line outranks via kh-tie + later-seq and carries a 2-run
        # EQUAL to the winner's — the strict `run > win_run`
        # dominance comparator blocks it. RED under any R-tie
        # relaxation (run >= win_run): +8 rescues but 2 KILLs / 9
        # triggers = NET-NEGATIVE, the gate is the result.
        tie = "Yes, the size tent for our camping trip arrived."
        a = self._build_winner2(tie)   # kh=3 tie, run=2 == win_run
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, self.WINNER2)
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_run_tie_kh_strict_blocked(self):
        # strict-tie2 variant (C549 census: +4 rescues, 2 KILLs of 6
        # triggers, 33% impostor rate): kh STRICTLY above the winner
        # must not buy a run tie past the dominance gate either.
        strict = ("What size tent did you buy for camping trips?"
                  )                  # user echo, kh=4, run=2 tie
        a = self._build_winner2(strict)
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, self.WINNER2)
        self.assertFalse(meta["user_challenge_face"]["override"])

    def test_c526_claimed_first_bails_challenge(self):
        # e61a7584 contract (C549 census): when session_complete_face
        # promotes a NON-window same-session line, the challenge face
        # cannot see that winner among retrieved_ids and must BAIL
        # (face_found=False) — same-session repair is C526's
        # territory, claimed first. A cross-session challenger that
        # would outrank the C526 winner must NOT hijack the repair.
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s2", "messages": [
                turn("assistant", OTHER)]},
            {"session_id": "s1", "messages": [
                turn("user", "I completed another marathon this "
                     "week and the pacing felt good."),
                turn("user", "The spring trail last month was "
                     "absolutely beautiful.")]},
            {"session_id": "s3", "messages": [
                turn("user", "I joined the running club last "
                     "spring and love it.")]},
        ])
        drop_from_window(a, "The spring trail last month was "
                            "absolutely beautiful.")
        drop_from_window(a, "I joined the running club last spring "
                            "and love it.")
        ans, meta = a.answer_extractive(
            "How many marathons have I finished since joining the "
            "running club last spring?", "")
        self.assertEqual(
            ans, "The spring trail last month was absolutely "
                 "beautiful.")
        self.assertTrue(meta["session_complete_face"]["override"])
        uc = meta["user_challenge_face"]
        self.assertFalse(uc["face_found"])
        self.assertFalse(uc["override"])


def _kw_phrase_run_guard(label):
    # local import shim kept at bottom so the test docstrings stay
    # the primary documentation surface
    from amg_bench_quality import _kw_phrase_run
    return _kw_phrase_run(label, _keywords(Q))


if __name__ == "__main__":
    unittest.main()
