#!/usr/bin/env python3
"""C543 tests: kh-floor absence is load-bearing (census-negative pin).

Census (C543 /tmp/c543, 216 answer-gate rows replayed at HEAD on the
C542 authoritative live500 baseline, byte-identical replay): of the
53 answer-gate WRONGs only 15 have a containment-caliber GT line in
the window at all, and exactly ONE has a winner out-hit by it — the
C523-documented containment-accident row a9f6b44c (a "2" inside a
bike-shops listing). Meanwhile 14/72 CORRECT answer-gate rows have a
window line with STRICTLY higher keyword hits than the winner: the
ranker's non-kh scoring (recency, role, session signals) is right
far more often than raw kh-max would be. A "demote the winner to a
higher-kh window line" floor would net ~1 accident-grade rescue vs
~14 kills — NET-NEGATIVE, falsified pre-wiring (C524/C536
census-first precedent).

These tests pin the ABSENCE of such a floor: when the retrieval
context hands the answer gate a lower-kh ranking winner with a
higher-kh line elsewhere in the window, the winner must survive the
full face chain untouched. If a future cycle wires a kh-floor, these
fail — and the census says it should not be wired.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amg_bench_quality import (LongMemEvalAdapter, _keyword_hits,
                               _keywords)


def turn(role, content):
    return {"role": role, "content": content}


Q = "How many bikes did I service or plan to service in March?"

# Ranking winner: kh=2 (date digits make it quant-safe: C523/C524
# top-with-number guard leaves it untouched — also pinned here).
WINNER = ("I remember that I got my Toyota Camry serviced at the "
          "Toyota dealership on January 10th, 2023, and they replaced "
          "the air filter and changed the oil.")
# Higher-kh window sibling: assistant advice line, topic-saturated,
# carries stray digits ("2 shops") — the a9f6b44c decoy shape.
DECOY = ("Along the Route 1: Marin Headlands and Highway 1, there "
         "are a few bike shops and repair services where you can "
         "stop for assistance if needed: 2 shops in Sausalito and 3 "
         "in Mill Valley for service and repair of bikes.")
FILLER = ("The weather this week has been lovely, perfect for "
          "working in the garden and reading on the porch.")


def build():
    a = LongMemEvalAdapter()
    a.ingest_sessions([
        {"session_id": "s1", "messages": [
            turn("user", "I'm planning some cycling trips. "
                         "Any route advice?"),
            turn("assistant", DECOY)]},
        {"session_id": "s2", "messages": [
            turn("user", FILLER),
            turn("user", WINNER)]},
    ])
    return a


def reorder_context(adapter, first_bodies):
    """Deterministically produce the census state: the ranker's top
    line is NOT the window kh-max (real instances: a9f6b44c and 14/72
    correct answer-gate rows). The higher-kh line STAYS in the window
    — a kh-floor would see and steal it."""
    real = adapter.retrieve_context

    def patched(question, question_date=""):
        context, meta = real(question, question_date)
        lines = context.split("\n")
        body = lambda ln: ln.split("] ", 1)[-1]  # noqa: E731
        picked = [ln for b in first_bodies
                  for ln in lines if body(ln) == b]
        rest = [ln for ln in lines if body(ln) not in first_bodies]
        return "\n".join(picked + rest), meta

    adapter.retrieve_context = patched
    return adapter


class TestKhFloorAbsence(unittest.TestCase):
    def test_higher_kh_window_line_does_not_steal_face(self):
        a = reorder_context(build(), [WINNER, DECOY])
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(meta["gate"], "answer")
        self.assertEqual(ans, WINNER)
        # census-state precondition: the decoy really sits in the
        # window with STRICTLY more keyword hits than the winner
        kws = meta.get("keywords") or _keywords(Q)
        win_kh = _keyword_hits(WINNER, kws)
        decoy_kh = _keyword_hits(DECOY, kws)
        self.assertGreater(decoy_kh, win_kh)

    def test_quant_top_with_number_guard_holds(self):
        a = reorder_context(build(), [WINNER, DECOY])
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(ans, WINNER)
        # winner carries digits (the January 10th, 2023 date) -> the
        # C523 quant_rerank block never runs (top-with-number
        # untouched is load-bearing, C524): no override key, decoy's
        # stray digits never hijack the face
        self.assertNotIn("quant_rerank", meta)

    def test_unpatched_ranking_baseline(self):
        # no reorder: the real ranker hands the gate its own top
        # line; the gate must answer with SOME window line and stay
        # on the answer gate (guards against fixture drift where the
        # abstain gates would swallow the scenario)
        a = build()
        ans, meta = a.answer_extractive(Q, "")
        self.assertEqual(meta["gate"], "answer")
        self.assertTrue(ans)
        self.assertNotEqual(ans, "IDK")


if __name__ == "__main__":
    unittest.main()
