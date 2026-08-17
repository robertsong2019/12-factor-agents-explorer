"""calibration_by_category — category-wise exact-vs-LLM divergence.

Cycle 465: ``calibration_summary`` is global-only; a full-run
divergence verdict must trace to the categories driving it
(kupdate llm-rescues vs adversarial false-passes diverge in
opposite directions). Duck-typed input — QuestionResult attrs or
report dict rows — same protocol as ``calibration_summary``.
"""

import json
import unittest

import amg_bench_quality as abq
from locomo_bench_quality import run_locomo
from test_locomo_bench_quality import make_sample, make_sample2, fresh_adapter


def _res(exact, llm, category="cat"):
    r = abq.QuestionResult(
        question_id="q", category=category, question="?",
        ground_truth="t", predicted_answer="p")
    r.correct_exact = exact
    r.correct_llm = llm
    return r


class TestGrouping(unittest.TestCase):
    """Pure function: group + per-group calibration_summary."""

    def test_groups_by_category_attrs(self):
        s = abq.calibration_by_category([
            _res(True, True, "a"), _res(False, False, "a"),
            _res(True, True, "b"),
        ])
        self.assertEqual(set(s), {"a", "b"})
        self.assertEqual(s["a"]["scored"], 2)
        self.assertEqual(s["b"]["scored"], 1)

    def test_groups_by_category_dicts(self):
        s = abq.calibration_by_category([
            {"category": "x", "correct_exact": True, "correct_llm": False},
            {"category": "x", "correct_exact": True, "correct_llm": True},
            {"category": "y", "correct_exact": False, "correct_llm": False},
        ])
        self.assertEqual(s["x"]["llm_only_wrong"], 1)
        self.assertEqual(s["y"]["agree"], 1)

    def test_per_category_matches_summary(self):
        rows = [_res(True, True, "a"), _res(False, True, "a"),
                _res(True, False, "b")]
        s = abq.calibration_by_category(rows)
        self.assertEqual(s["a"], abq.calibration_summary(rows[:2]))
        self.assertEqual(s["b"], abq.calibration_summary(rows[2:]))

    def test_missing_category_bucketed_unknown(self):
        r = abq.QuestionResult(
            question_id="q", category=None, question="?",
            ground_truth="t", predicted_answer="p")
        r.correct_exact = r.correct_llm = True
        s = abq.calibration_by_category([r])
        self.assertEqual(set(s), {"unknown"})

    def test_keys_sorted_deterministic(self):
        s = abq.calibration_by_category([
            _res(True, True, "zeta"), _res(True, True, "alpha")])
        self.assertEqual(list(s), ["alpha", "zeta"])

    def test_empty_results(self):
        self.assertEqual(abq.calibration_by_category([]), {})

    def test_undual_rows_skipped_per_category(self):
        s = abq.calibration_by_category([
            _res(None, None, "a"), _res(True, True, "a")])
        self.assertEqual(s["a"]["scored"], 1)
        # a category with only undual rows still lists (scored=0)
        s2 = abq.calibration_by_category([_res(None, None, "b")])
        self.assertEqual(s2["b"]["scored"], 0)


class TestEvaluateDualBreakdown(unittest.TestCase):
    """E2E: LME evaluate(judge_mode='dual') carries the breakdown."""

    def _dataset(self):
        return [
            {"id": "q1", "question": "Where does Janet prefer to work?",
             "answer": "coffee shops",
             "haystack": [[{"role": "user",
                            "content": "I love working from coffee shops."}]]},
            {"id": "q2", "question": "What is Janet's favorite cuisine?",
             "answer": "Italian",
             "haystack": [[{"role": "user",
                            "content": "I really enjoy Italian pasta."}]]},
        ]

    def _eval(self, judge_mode):
        abq._JUDGE_MODE = "mock"
        try:
            adapter = abq.LongMemEvalAdapter(use_ppr=False)
            sessions = [
                {"session_id": f"s{i}", "messages": item["haystack"][0],
                 "date": f"2026-01-0{i + 1}"}
                for i, item in enumerate(self._dataset())
            ]
            adapter.ingest_sessions(sessions)
            return adapter.evaluate(self._dataset(), judge_mode=judge_mode)
        finally:
            abq._JUDGE_MODE = None

    def test_evaluate_dual_includes_breakdown(self):
        r = self._eval("dual")
        self.assertIn("calibration_by_category", r)
        self.assertEqual(set(r["calibration_by_category"]),
                         set(r["categories"]))
        total = sum(v["scored"]
                    for v in r["calibration_by_category"].values())
        self.assertEqual(total, r["calibration"]["scored"])

    def test_run_eval_dual_includes_breakdown(self):
        ds = [
            {"id": "q1", "question": "Where does Janet prefer to work?",
             "answer": "coffee shops",
             "haystack_sessions": [[{"role": "user",
                                     "content": "I love working from coffee shops."}]]},
            {"id": "q2", "question": "What is Janet's favorite cuisine?",
             "answer": "Italian",
             "haystack_sessions": [[{"role": "user",
                                     "content": "I really enjoy Italian pasta."}]]},
        ]
        abq._JUDGE_MODE = "mock"
        try:
            r = abq.run_eval(ds, judge_mode="dual")
        finally:
            abq._JUDGE_MODE = None
        self.assertIn("calibration_by_category", r)
        self.assertEqual(set(r["calibration_by_category"]),
                         set(r["categories"]))

    def test_exact_mode_no_breakdown(self):
        r = self._eval("exact")
        self.assertNotIn("calibration_by_category", r)


class TestLoCoMoDualBreakdown(unittest.TestCase):
    """E2E: LoCoMo evaluate_sample / run_locomo carry the breakdown."""

    def test_evaluate_sample_dual_breakdown(self):
        s = make_sample()
        ad = fresh_adapter()
        ad.ingest_sample(s)
        abq._JUDGE_MODE = "mock"
        try:
            r = ad.evaluate_sample(s["qa"], judge_mode="dual")
        finally:
            abq._JUDGE_MODE = None
        self.assertIn("calibration_by_category", r)
        self.assertEqual(
            set(r["calibration_by_category"]), set(r["categories"]))
        total = sum(v["scored"]
                    for v in r["calibration_by_category"].values())
        self.assertEqual(total, r["calibration"]["scored"])

    def test_run_locomo_dual_breakdown(self):
        import os, tempfile
        path = os.path.join(tempfile.mkdtemp(), "locomo_mini.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([make_sample(), make_sample2()], f)
        abq._JUDGE_MODE = "mock"
        try:
            r = run_locomo(path, use_ppr=False, judge_mode="dual")
        finally:
            abq._JUDGE_MODE = None
        self.assertIn("calibration_by_category", r)
        total = sum(v["scored"]
                    for v in r["calibration_by_category"].values())
        self.assertEqual(total, r["calibration"]["scored"])


if __name__ == "__main__":
    unittest.main()
