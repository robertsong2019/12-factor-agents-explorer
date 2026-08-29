"""Cycle 528: deterministic (readonly) recall — root-cause fix for the
"tie-jitter" family.

C527b diagnosed the family (86f00804 4x official flip, C518 self-heal,
C526 census PA mismatch, C522-era replay -2) as "unseeded RNG". The
C528 audit falsifies that: ZERO unseeded ``random.`` call sites are
reachable from the bench retrieval path (all memory_graph random uses
are seeded or in unreachable analytics). The real mechanism is
wall-clock weight coupling in ``MemoryGraph.recall``: every call
re-writes ``weight``/``accessed`` with ``time.time()``-based decay plus
ACCESS_BOOST. Ingest stamps every node weight=1.0, so ``ORDER BY
weight DESC`` near-ties are resolved by ingest-then-eval elapsed-time
float noise — and the eval harness builds a FRESH graph per question,
so every question replay re-rolls the dice. PYTHONHASHSEED cannot pin
this; no RNG is involved.

Fix: ``recall(readonly=True)`` is a pure read (no decay, no boost, no
writes, rowid tie-break) and the adapter uses it by default
(``deterministic_recall=True``; ``--wallclock-recall`` restores legacy
behavior). Retrieval becomes a pure function of the ingested graph —
bitwise replayable.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_graph as mg_mod
from memory_graph import MemoryGraph
from amg_bench_quality import LongMemEvalAdapter, run_eval


def turn(role, content):
    return {"role": role, "content": content}


SMALL_HAY = [[
    turn("user", "I finished the Chicago marathon last October and it "
                 "was my third marathon overall."),
    turn("assistant", "That's a fantastic milestone — three marathons!"),
    turn("user", "My favorite book is The Seven Husbands of Evelyn Hugo "
                 "and I reread it every summer."),
    turn("assistant", "Great choice, that novel has such a twist."),
]] * 1


class ReadOnlyRecallTest(unittest.TestCase):
    def setUp(self):
        self.mg = MemoryGraph(":memory:")
        for label in ("apple juice bottle", "banana split",
                      "apple pie recipe", "apple cider vinegar"):
            self.mg.add(label, kind="fact")
        # Uniform weight + ancient accessed: ordering must not depend
        # on either.
        self.mg.conn.execute(
            "UPDATE nodes SET weight=1.0, accessed=1.0")
        self.mg.conn.commit()

    def _weights(self):
        return dict(self.mg.conn.execute(
            "SELECT id, weight FROM nodes").fetchall())

    def _accessed(self):
        return dict(self.mg.conn.execute(
            "SELECT id, accessed FROM nodes").fetchall())

    def test_readonly_is_time_immune(self):
        """Decay is computed from a frozen snapshot: advancing the
        wall clock (here: accessed vs time.time() gap) must not change
        the result — the legacy path's flips came exactly from this."""
        r1 = [n.label for n in self.mg.recall("apple", limit=3,
                                              readonly=True)]
        # simulate a next-day replay: same query, clock far ahead
        with mock.patch.object(mg_mod.time, "time", return_value=(
                1.0 + 40 * 86400)):
            r2 = [n.label for n in self.mg.recall("apple", limit=3,
                                                  readonly=True)]
        self.assertEqual(r1, r2)

    def test_readonly_does_not_mutate(self):
        w0, a0 = self._weights(), self._accessed()
        self.mg.recall("apple", limit=3, readonly=True)
        self.assertEqual(w0, self._weights())
        self.assertEqual(a0, self._accessed())

    def test_readonly_tie_break_is_rowid(self):
        """Equal weights resolve by insertion (rowid) order —
        deterministic across processes and replays."""
        got = [n.label for n in self.mg.recall("apple", limit=4,
                                               readonly=True)]
        self.assertEqual(got, ["apple juice bottle", "apple pie recipe",
                               "apple cider vinegar"])

    def test_default_recall_still_boosts(self):
        """readonly=False default is byte-identical legacy behavior
        (decay + ACCESS_BOOST + write-back) — production callers
        unaffected."""
        w0 = self._weights()
        self.mg.recall("apple", limit=3)
        w1 = self._weights()
        touched = [k for k in w1 if abs(w1[k] - w0[k]) > 1e-12]
        self.assertTrue(touched, "default recall lost boost behavior")
        self.assertEqual(len(touched), 3)  # exactly the recalled rows


class AdapterDeterminismTest(unittest.TestCase):
    def test_adapter_default_and_flag(self):
        self.assertTrue(LongMemEvalAdapter().deterministic_recall)
        self.assertFalse(LongMemEvalAdapter(
            deterministic_recall=False).deterministic_recall)

    def test_eval_path_pure_function_of_dataset(self):
        """The money property: the SAME haystack ingested under two
        different wall-clock schedules must produce the identical
        context and answer with deterministic_recall (legacy path
        computes decay from real time and is exempt from this
        guarantee by construction)."""
        answers = set()
        contexts = set()
        for drift_days in (0, 3, 45):
            real_time = mg_mod.time.time

            def fake_time(_drift=drift_days, _real=real_time):
                # push 'now' around: decay base moves per schedule
                return _real() + _drift * 86400

            adapter = LongMemEvalAdapter()
            with mock.patch.object(mg_mod.time, "time", fake_time):
                adapter.ingest_sessions(
                    [{"session_id": "session_1",
                      "messages": SMALL_HAY[0]}])
                ctx, meta = adapter.retrieve_context(
                    "Which marathon did I finish last October?")
                ans, _ = adapter.answer_extractive(
                    "Which marathon did I finish last October?")
            answers.add(ans)
            contexts.add(ctx)
        self.assertEqual(len(answers), 1, f"answer drifted: {answers!r}")
        self.assertEqual(len(contexts), 1,
                         f"context drifted: {contexts!r}")

    def test_run_eval_reports_flag(self):
        rep = run_eval([], judge_mode="exact")
        self.assertTrue(rep["config"]["deterministic_recall"])
        rep = run_eval([], judge_mode="exact",
                       deterministic_recall=False)
        self.assertFalse(rep["config"]["deterministic_recall"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
