"""Cycle 472 tests: temporal anchor-targeted full-graph fallback.

Window-first anchoring (C457/471) is preserved; when the window
misses an anchor line that the ingested graph contains, the temporal
path retries against ALL messages and flags ``fallback:
"full_graph"`` for telemetry. Forensics: 6/37 anchor-missed questions
resolve on the full haystack (6/6 correct); the other 31 are a
lexical wall (anchor entities never appear verbatim in the haystack).
"""
import unittest

from amg_bench_quality import LongMemEvalAdapter

# Crowd lines hit NON-anchor question keywords (many/days/passed/
# between/visit) with higher counts than the anchor lines' own
# hits — they outrank anchors, fill the tiny window (~40 tokens ≈
# 2 lines), and contain ZERO anchor tokens so the fallback's
# full-graph search stays unambiguous. This mirrors the real C472
# forensics failure: windows fill with lexically-related lines
# while the anchor events' lines never rank in.
CROWD = [
    {"role": "user", "content":
     f"visit recap {i}: many days passed between visits"}
    for i in range(10)
]
CROWD_AGO = [
    {"role": "user", "content": f"many days ago visit recap log {i}"}
    for i in range(10)
]
CROWD_FIRST = [
    {"role": "user", "content": f"book reading first recap log {i}"}
    for i in range(10)
]


class TestTemporalFullGraphFallback(unittest.TestCase):
    def _adapter(self, sessions, dates, **kw):
        kw.setdefault("max_context_tokens", 40)   # ~2 lines fit
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions(
            [{"session_id": sid, "messages": msgs}
             for sid, msgs in sessions],
            session_dates=dates)
        return a

    def test_between_fallback_fires(self):
        # Crowd lines fill the tiny window; the anchor events live in
        # s20/s21 whose lines never enter — full-graph fallback must
        # rescue with the correct arithmetic.
        a = self._adapter(
            [("s1", CROWD),
             ("s20", [{"role": "user", "content":
                       "I finally visited the astronomy observatory"}]),
             ("s21", [{"role": "user", "content":
                       "The pottery workshop was hands-on and fun"}])],
            {"s1": "2023/01/10 (Tue) 09:00",
             "s20": "2023/01/20 (Fri) 10:00",
             "s21": "2023/02/03 (Fri) 10:00"})
        ans, meta = a.answer_extractive(
            "How many days passed between my visit to the astronomy "
            "observatory and the pottery workshop?")
        self.assertEqual(ans, "14 days")
        self.assertEqual(meta["gate"], "temporal_arith")
        self.assertEqual(meta["temporal"].get("fallback"), "full_graph")

    def test_window_first_no_fallback_flag(self):
        # Big window resolves in-window: no fallback flag, same
        # answer as C457 baseline behavior.
        a = self._adapter(
            [("s1", [{"role": "user", "content":
                      "I finally visited the MoMA and saw the wing"}]),
             ("s2", [{"role": "user", "content":
                      "The Ancient Civilizations exhibition was great"}])],
            {"s1": "2023/01/15 (Sun) 11:00",
             "s2": "2023/01/22 (Sun) 19:30"},
            max_context_tokens=4000)
        ans, meta = a.answer_extractive(
            "How many days passed between my visit to the MoMA and "
            "the Ancient Civilizations exhibition?")
        self.assertEqual(ans, "7 days")
        self.assertEqual(meta["gate"], "temporal_arith")
        self.assertNotIn("fallback", meta["temporal"])

    def test_lexical_wall_falls_through(self):
        # Anchors never appear anywhere (alias wall): no answer from
        # the temporal path, no fallback answer fabricated.
        a = self._adapter(
            [("s1", [{"role": "user", "content":
                      "my new phone takes great pictures"}]),
             ("s2", [{"role": "user", "content":
                      "the new laptop keyboard is lovely"}])],
            {"s1": "2023/01/02 (Mon) 09:00",
             "s2": "2023/01/09 (Mon) 09:00"},
            max_context_tokens=4000)
        _, meta = a.answer_extractive(
            "Which device did I get first, the Samsung Galaxy S22 or "
            "the Dell XPS 13?")
        self.assertNotEqual(meta["gate"], "temporal_arith")

    def test_same_session_wall_persists_on_full_retry(self):
        # Both anchors hit the ONLY session (true geometry wall) —
        # the full-graph retry also sees one session, stays None,
        # and the extractive gates own the answer. No fabrication.
        a = self._adapter(
            [("s1", [{"role": "user", "content":
                      "I visited the MoMA then the Louvre same day"}])],
            {"s1": "2023/01/15 (Sun) 11:00"},
            max_context_tokens=4000)
        _, meta = a.answer_extractive(
            "How many days passed between my visit to the MoMA and "
            "the Louvre?")
        self.assertNotEqual(meta["gate"], "temporal_arith")
        self.assertNotIn("fallback", meta["temporal"])
        self.assertEqual(meta["temporal"]["anchors"], [True, True])

    def test_same_session_collapse_rescued_by_fallback(self):
        # The real C472 failure shape, abstracted: the window's top
        # line lexically mirrors the WHOLE question (a recap/advice
        # line mentioning both anchors), collapsing both anchors
        # onto one session (geometry None); the full graph holds the
        # true event lines in two dated sessions, where user-role +
        # past-aspect beat the mirror and the retry resolves.
        crowd_sessions = [
            (f"s1_{i}", [{"role": "user", "content":
                          f"many days passed between visits log {i}"}])
            for i in range(6)]
        a = self._adapter(
            [("s1", [{"role": "assistant", "content":
                      "MoMA and the Louvre recap of many days passed "
                      "between visits"}])] + crowd_sessions +
            [("s20", [{"role": "user", "content":
                       "I visited the MoMA on friday"}]),
             ("s21", [{"role": "user", "content":
                       "the Louvre was stunning"}])],
            {"s1": "2023/02/10 (Fri) 09:00",
             **{f"s1_{i}": "2023/02/11 (Sat) 09:00" for i in range(6)},
             "s20": "2023/01/15 (Sun) 11:00",
             "s21": "2023/01/22 (Sun) 19:30"})
        ans, meta = a.answer_extractive(
            "How many days passed between my visit to the MoMA and "
            "the Louvre?")
        self.assertEqual(ans, "7 days")
        self.assertEqual(meta["temporal"].get("fallback"), "full_graph")

    def test_ago_form_fallback(self):
        a = self._adapter(
            [("s1", CROWD_AGO),
             ("s20", [{"role": "user", "content":
                       "I ran the lakeside charity 5K this morning"}])],
            {"s1": "2023/01/02 (Mon) 09:00",
             "s20": "2023/01/16 (Mon) 08:00"})
        ans, meta = a.answer_extractive(
            "How many days ago did I run the charity 5K?",
            "2023/01/23 (Mon) 09:00")
        self.assertEqual(ans, "7 days")
        self.assertEqual(meta["gate"], "temporal_arith")
        self.assertEqual(meta["temporal"].get("fallback"), "full_graph")

    def test_first_form_fallback(self):
        a = self._adapter(
            [("s1", CROWD_FIRST),
             ("s20", [{"role": "user", "content":
                       "started reading The Nightingale tonight"}]),
             ("s21", [{"role": "user", "content":
                       "finished The Hate U Give in one sitting"}])],
            {"s1": "2023/01/10 (Tue) 09:00",
             "s20": "2023/01/25 (Wed) 21:00",
             "s21": "2023/02/01 (Wed) 21:00"})
        ans, meta = a.answer_extractive(
            "Which book did I finish reading first, 'The Hate U "
            "Give' or 'The Nightingale'?")
        self.assertIn("nightingale", ans.lower())
        self.assertEqual(meta["gate"], "temporal_arith")
        self.assertEqual(meta["temporal"].get("fallback"), "full_graph")

    def test_disabled_path_untouched(self):
        a = self._adapter(
            [("s1", CROWD),
             ("s20", [{"role": "user", "content":
                       "I finally visited the astronomy observatory"}]),
             ("s21", [{"role": "user", "content":
                       "The pottery workshop was hands-on"}])],
            {"s1": "2023/01/10 (Tue) 09:00",
             "s20": "2023/01/20 (Fri) 10:00",
             "s21": "2023/02/03 (Fri) 10:00"},
            temporal_arith=False, max_context_tokens=4000)
        _, meta = a.answer_extractive(
            "How many days passed between my visit to the astronomy "
            "observatory and the pottery workshop?")
        self.assertNotEqual(meta["gate"], "temporal_arith")

    def test_no_session_dates_skips_path(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([{"session_id": "s1", "messages": [
            {"role": "user", "content": "MoMA visit then workshop"}]}])
        _, meta = a.answer_extractive(
            "How many days passed between my MoMA visit and the "
            "workshop?")
        self.assertNotEqual(meta["gate"], "temporal_arith")
        self.assertNotIn("temporal", meta)   # path never ran


if __name__ == "__main__":
    unittest.main()
