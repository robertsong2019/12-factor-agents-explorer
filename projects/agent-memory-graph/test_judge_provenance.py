"""Cycle 560 tests — judge provenance fingerprint (judge_prompt_sha12 + judge_model).

C530 fingerprinted the judge BACKEND (mock vs ollama vs unconsulted),
but two provenance dimensions stayed invisible in the report:

- JUDGE_PROMPT can drift silently: a prompt edit changes verdicts on
  identical code, and no report field distinguishes the two runs.
- judge_ollama's model is a parameter with default "qwen2.5:7b" — an
  ollama-resolved run never says WHICH model issued the verdicts.

Both fields make judge-resolved lineages auditable (same spirit as the
C527 data_sha256_12 fingerprint that caught the oracle/s_cleaned mixup).
"""

import hashlib
import unittest
from unittest.mock import patch

import amg_bench_quality as abq

HAY = [{"session_id": "s1", "messages": [
    {"role": "user", "content": "My favorite color is teal."},
    {"role": "assistant", "content": "Noted, teal is a great color."},
]}]
Q = {"id": "q1", "question": "What is my favorite color?",
     "answer": "teal", "haystack_sessions": HAY}


def _reset_judge_globals(fn):
    def wrapper(self):
        try:
            fn(self)
        finally:
            abq._JUDGE_MODE = None
            abq._JUDGE_MODEL = None
    return wrapper


class TestJudgePromptSha(unittest.TestCase):

    def test_recorded_in_dual_mode(self):
        rep = abq.run_eval([Q], judge_mode="dual")
        want = hashlib.sha256(
            abq.JUDGE_PROMPT.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(rep["config"]["judge_prompt_sha12"], want)

    def test_recorded_in_semantic_mode(self):
        rep = abq.run_eval([Q], judge_mode="semantic")
        self.assertIn("judge_prompt_sha12", rep["config"])

    def test_follows_live_prompt_constant(self):
        """Wiring proof: mutating JUDGE_PROMPT must change the hash —
        a stale literal would fingerprint nothing."""
        original = abq.JUDGE_PROMPT
        try:
            abq.JUDGE_PROMPT = original + "\nExtra rule."
            rep = abq.run_eval([Q], judge_mode="dual")
            want = hashlib.sha256(
                abq.JUDGE_PROMPT.encode("utf-8")).hexdigest()[:12]
            self.assertEqual(rep["config"]["judge_prompt_sha12"], want)
            self.assertNotEqual(
                rep["config"]["judge_prompt_sha12"], hashlib.sha256(
                    original.encode("utf-8")).hexdigest()[:12])
        finally:
            abq.JUDGE_PROMPT = original

    def test_absent_in_exact_mode(self):
        """Backward compat: exact mode has no semantic judge — no key."""
        rep = abq.run_eval([Q])
        self.assertNotIn("judge_prompt_sha12", rep["config"])


class TestJudgeModel(unittest.TestCase):

    @_reset_judge_globals
    def test_recorded_when_ollama_resolved(self):
        abq._JUDGE_MODE = "ollama"
        abq._JUDGE_MODEL = "qwen2.5:7b"
        rep = abq.run_eval([Q], judge_mode="dual")
        self.assertEqual(rep["config"]["judge_model"], "qwen2.5:7b")
        self.assertEqual(rep["config"]["judge_llm_backend"], "ollama")

    @_reset_judge_globals
    def test_absent_when_mock(self):
        """Honest absence: mock has no model identity; the backend
        field already says 'mock'."""
        abq._JUDGE_MODE = "mock"
        rep = abq.run_eval([Q], judge_mode="dual")
        self.assertNotIn("judge_model", rep["config"])
        self.assertEqual(rep["config"]["judge_llm_backend"], "mock")

    @_reset_judge_globals
    def test_absent_when_no_live_ollama(self):
        """Honest absence: without a live ollama verdict (probe degrades
        to mock, or nothing consulted) no model identity may appear."""
        rep = abq.run_eval([Q], judge_mode="dual")
        self.assertNotIn("judge_model", rep["config"])
        self.assertNotEqual(rep["config"]["judge_llm_backend"], "ollama")

    @_reset_judge_globals
    def test_sticky_set_by_successful_verdict(self):
        """judge_ollama itself records the model that produced a
        verdict — the report field reads lived evidence, not config."""
        resp = {"choices": [{"message": {"content": "CORRECT"}}]}
        with patch("urllib.request.urlopen") as mock_ur:
            mock_ur.return_value.__enter__.return_value.read = \
                lambda: b'{"choices":[{"message":{"content":"CORRECT"}}]}'
            v = abq.judge_ollama("q?", "teal", "teal",
                                 model="llama3:8b")
        self.assertEqual(v, "CORRECT")
        self.assertEqual(abq._JUDGE_MODEL, "llama3:8b")

    @_reset_judge_globals
    def test_error_verdict_leaves_model_unknown(self):
        """ERROR = network/model failure = no verdict issued, so the
        sticky must not claim this model judged anything."""
        with patch("urllib.request.urlopen",
                   side_effect=OSError("down")):
            v = abq.judge_ollama("q?", "teal", "teal",
                                 model="llama3:8b")
        self.assertEqual(v, "ERROR")
        self.assertIsNone(abq._JUDGE_MODEL)


if __name__ == "__main__":
    unittest.main()
