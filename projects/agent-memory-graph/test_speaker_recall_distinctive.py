"""Cycle 475 — speaker-recall distinctive mode (Research #074 v5).

Double-regime reversal: in dialogue recall, word overlap is a NEGATIVE
discriminator for prefaces (the preface directly answers the question,
so it necessarily overlaps). The v5 mechanism validates on ssa-56:
exact 15→16 zero-regression, judge-corrected 15→18.

Distinctive mode scores assistant sentences with squared distinctive
weights ``w(kw)^2``, ``w = 1 + log(N/df)``:
  * raw floor 3 (below the legacy 5 — the v3 zero-flip lesson:
    parasitism is FLOOR-level; answer sentences with distinctive-but-
    few hits never clear raw>=5)
  * necessary condition: >=1 matched keyword with df <= 8
  * preface x0.25 penalty (rank-level multipliers lose, v2 -3)
  * '?' sentences skipped, weighted floor 10.0
"""
import unittest

from amg_bench_quality import (
    LongMemEvalAdapter, answer_speaker_recall, _RECALL_PREAMBLE_RE)


def _node(label, role="assistant", session="s1"):
    return {"label": label, "role": role, "session_id": session}


FILLER = [
    "The lake was calm that morning.",
    "We walked around the lake after breakfast.",
    "Her house sits near the lake.",
] * 8  # df(lake) = 24 -> generic

# Question kws: paddle, board, brand, lake ("which/did/you/for/the"
# are stopwords).
Q_BOARD = ("Which paddle board brand did you suggest for the lake?")


class TestDistinctiveMode(unittest.TestCase):
    """Distinctive w^2 scoring vs legacy raw counting."""

    def _nodes(self):
        nodes = {
            "p": _node("Sure, here are the paddle board options I "
                       "mentioned for the lake.", session="s1"),
            "a": _node("The Bluefin Cruise 12' paddle board is the "
                       "brand I would pick for beginners.",
                       session="s2"),
        }
        nodes.update({f"f{i}": _node(t, session="s1")
                      for i, t in enumerate(FILLER)})
        return nodes

    def test_distinctive_beats_preamble(self):
        """Preamble wins raw counting yet loses w^2 scoring.

        The preamble overlaps paddle+board+lake (parasitism); the
        answer carries paddle+board+brand — the same raw count, but
        every hit distinctive (df=2/2/1 vs lake df=25) and no preface
        penalty. Exactly the double regime from Research #074.
        """
        ans, detail = answer_speaker_recall(Q_BOARD, self._nodes())
        self.assertIsNotNone(ans)
        self.assertIn("Bluefin", ans)
        self.assertEqual(detail["mode"], "distinctive")
        self.assertEqual(detail["session_id"], "s2")

    def test_raw_mode_returns_legacy_preamble(self):
        """mode='raw' preserves the Cycle 468 counting behavior."""
        ans, detail = answer_speaker_recall(Q_BOARD, self._nodes(),
                                            min_score=3, mode="raw")
        self.assertIsNotNone(ans)
        self.assertTrue(ans.startswith("Sure"))
        self.assertEqual(detail["mode"], "raw")

    def test_preamble_penalty_prefers_plain_twin(self):
        """Identical hit profiles: the preface twin loses 4x."""
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "p": _node("Sure, here are the cork yoga mat options.",
                       session="s1"),
            "a": _node("The Gaiam cork yoga mat at 5mm is my top pick.",
                       session="s2"),
        }
        # pad the pool so w = 1+log(40/2) clears the weighted floor
        nodes.update({f"f{i}": _node(
            f"We talked about wallpaper colors on day {i}.",
            session="s3") for i in range(38)})
        ans, _ = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("Gaiam", ans)

    def test_question_sentences_skipped(self):
        """A '?' sentence never becomes the answer."""
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "a": _node("Would the Gaiam cork yoga mat suit your "
                       "practice?", session="s1"),
        }
        ans, detail = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)
        self.assertEqual(detail["questions_skipped"], 1)

    def test_no_distinctive_hit_unresolved(self):
        """All matched keywords generic (df > 8): not an answer row."""
        q = "What lake canoe paddle gear did you mention?"
        nodes = {f"n{i}": _node(
            f"Trip {i}: we took the lake canoe paddle gear route "
            f"again.", session="s1") for i in range(30)}
        from amg_bench_quality import _keyword_hits
        for kw in ("lake", "canoe", "paddle", "gear"):
            self.assertGreater(
                sum(1 for n in nodes.values()
                    if _keyword_hits(n["label"], [kw])), 8)
        ans, detail = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)
        self.assertEqual(detail.get("best_score"), 0)

    def test_raw_floor_three(self):
        """Two distinctive hits never clear the raw floor."""
        nodes = {
            "a": _node("The Bluefin Cruise 12' paddle board.",
                       session="s1"),
        }
        ans, _ = answer_speaker_recall(Q_BOARD, nodes)
        self.assertIsNone(ans)

    def test_weighted_floor(self):
        """Distinctive-but-shallow weights stay under the floor.

        8 sentences each containing all three kws: df=8 (distinctive
        boundary), N=8 -> w = 1+log(1) = 1.0 per kw, score = 3 < 10.
        """
        q = "What lake canoe paddle did you mention?"
        nodes = {f"n{i}": _node(
            f"We took the lake canoe paddle out on trip {i}.",
            session="s1") for i in range(8)}
        ans, _ = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)

    def test_empty_pool(self):
        ans, detail = answer_speaker_recall(
            "Which paddle board?", {"u1": _node("hi", role="user")})
        self.assertIsNone(ans)

    def test_detail_reports_df(self):
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "a": _node("The Gaiam cork yoga mat at 5mm is my top pick.",
                       session="s1"),
        }
        _, detail = answer_speaker_recall(q, nodes)
        self.assertEqual(detail["df"]["cork"], 1)


class TestPrefaceRegex(unittest.TestCase):
    """Research #074 forensics: three preamble variants slipped v5."""

    def test_variants_match(self):
        for s in ("Here's a quick summary of my thoughts.",
                  "Thank you for providing the details.",
                  "I hope these help you decide!",
                  "Sure, here are the options.",
                  "Hope that helps!",
                  "Absolutely, here is the plan."):
            self.assertIsNotNone(_RECALL_PREAMBLE_RE.match(s), msg=s)

    def test_answers_do_not_match(self):
        for s in ("The Gaiam cork yoga mat at 5mm is my top pick.",
                  "Hereford cattle graze the north field.",
                  "I suggest the 3-day Kyoto itinerary."):
            self.assertIsNone(_RECALL_PREAMBLE_RE.match(s), msg=s)


class TestAdapterWiring(unittest.TestCase):
    """recall_mode config flows through the adapter call site."""

    QUESTION = ("Can you remind me of the paddle board brand you "
                "suggested for the lake?")

    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user",
                 "content": "Any paddle board advice?"},
                {"role": "assistant",
                 "content": "Sure, here are the paddle board options I "
                            "mentioned for the lake."},
            ] + [{"role": "assistant",
                  "content": t} for t in FILLER],
        }, {
            "session_id": "s2",
            "messages": [
                {"role": "user", "content": "Follow up on boards?"},
                {"role": "assistant",
                 "content": "The Bluefin Cruise 12' paddle board is "
                            "the brand I would pick for beginners."},
            ]}])
        return a

    def test_default_mode_is_distinctive(self):
        a = self._adapter()
        self.assertEqual(a.recall_mode, "distinctive")
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertEqual(meta["gate"], "speaker_recall")
        self.assertIn("Bluefin", ans)

    def test_raw_mode_config(self):
        a = self._adapter(recall_mode="raw", recall_min_score=3)
        self.assertEqual(a.recall_mode, "raw")
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertEqual(meta["gate"], "speaker_recall")
        self.assertTrue(ans.startswith("Sure"))


if __name__ == "__main__":
    unittest.main()
