"""Cycle 468 — speaker-recall answer path.

You-addressed recall ("remind me what you recommended", "did you
suggest…", "your advice on…") targets the ASSISTANT's own prior
statements. Assistant answers are multi-paragraph and the specific
fact sits mid-body, so message-level ranking surfaces generic
openers ("Sure, here are a few…"); the speaker-recall path scores
assistant SENTENCES and returns the best (form-triggered, zero LLM,
falls through to the gate chain when unresolved).
"""

import unittest

from amg_bench_quality import (
    ABSTAIN_ANSWER,
    LongMemEvalAdapter,
    _split_sentences,
    answer_speaker_recall,
    recall_form,
)


class TestRecallForm(unittest.TestCase):
    """Form classification: you-addressed recall vs everything else."""

    def test_fires_on_remind_me_you_recommended(self):
        q = ("Can you remind me of the name of the romantic Italian "
             "restaurant in Rome you recommended for our anniversary?")
        self.assertEqual(recall_form(q), "assistant")

    def test_fires_on_did_you_suggest(self):
        self.assertEqual(
            recall_form("Did you suggest any stretch for knee pain?"),
            "assistant")

    def test_fires_on_your_advice(self):
        self.assertEqual(
            recall_form("What was your advice on money management?"),
            "assistant")

    def test_fires_on_you_told_me(self):
        self.assertEqual(
            recall_form("You told me about a budgeting app earlier."),
            "assistant")

    def test_plain_question_does_not_fire(self):
        self.assertIsNone(recall_form("What is my favorite color?"))

    def test_user_source_guard_blocks_firing(self):
        # "remind me" alone is ambiguous — with a first-person source
        # ("what I told you") it is USER-side recall and must not
        # restrict answers to assistant sentences.
        self.assertIsNone(
            recall_form("Remind me what I told you about my new job."))

    def test_we_source_guard(self):
        self.assertIsNone(
            recall_form("Remind me what we mentioned in the meeting."))

    def test_empty_question(self):
        self.assertIsNone(recall_form(""))
        self.assertIsNone(recall_form(None))


class TestSplitSentences(unittest.TestCase):

    def test_sentence_and_newline_split(self):
        parts = _split_sentences(
            "Sure, here are options! Roscioli serves great pasta.\n"
            "By the way, enjoy Rome.")
        self.assertEqual(parts, ["Sure, here are options!",
                                 "Roscioli serves great pasta.",
                                 "By the way, enjoy Rome."])

    def test_short_fragments_dropped(self):
        self.assertEqual(_split_sentences("Hi. Ok. a. Sure thing here."),
                         ["Sure thing here."])


def _nodes_fixture():
    """Assistant reply with the fact buried mid-body + decoys."""
    return {
        "n1": {"label": "Can you recommend some authentic Italian "
                        "restaurants in Rome?",
               "role": "user", "session_id": "s1"},
        "n2": {"label": "Sure! There are many wonderful places to eat "
                        "in Rome.\nBy the way, Roscioli is a romantic "
                        "Italian restaurant near Campo de' Fiori, "
                        "perfect for an anniversary dinner. "
                        "Also, try the carbonara at Da Danilo for a "
                        "more casual night.",
               "role": "assistant", "session_id": "s1"},
        "n3": {"label": "Sure! Here are some budget tips for "
                        "backpackers traveling on a dime.",
               "role": "assistant", "session_id": "s2"},
    }


class TestAnswerSpeakerRecall(unittest.TestCase):

    QUESTION = ("Can you remind me of the name of the romantic "
                "Italian restaurant in Rome you recommended for our "
                "anniversary dinner?")

    def test_returns_fact_sentence_not_generic_opener(self):
        # Default mode is distinctive (Cycle 475) — the Roscioli
        # sentence still beats the "Sure!" opener, now via w^2
        # weights + preface penalty instead of raw counting.
        ans, detail = answer_speaker_recall(
            self.QUESTION, _nodes_fixture())
        self.assertIsNotNone(ans)
        self.assertIn("Roscioli", ans)
        self.assertNotIn("Sure", ans)
        self.assertGreaterEqual(detail["best_score"], 5)
        self.assertEqual(detail["session_id"], "s1")
        self.assertGreaterEqual(
            detail.get("pool", detail.get("sentences_scanned", 0)), 3)

    def test_below_threshold_falls_through(self):
        ans, detail = answer_speaker_recall(
            self.QUESTION, _nodes_fixture(), min_score=99, mode="raw")
        self.assertIsNone(ans)
        # detail still reports the best score for diagnostics
        self.assertGreaterEqual(detail["best_score"], 5)

    def test_user_nodes_ignored(self):
        nodes = {"n1": _nodes_fixture()["n1"]}  # user node only
        ans, _ = answer_speaker_recall(self.QUESTION, nodes)
        self.assertIsNone(ans)

    def test_empty_nodes(self):
        self.assertIsNone(answer_speaker_recall(self.QUESTION, {})[0])


class TestAdapterIntegration(unittest.TestCase):
    """End-to-end: ingest → answer_extractive fires speaker_recall."""

    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user",
                 "content": "Can you recommend some authentic Italian "
                            "restaurants in Rome?"},
                {"role": "assistant",
                 "content": "Sure! There are many wonderful places to "
                            "eat in Rome.\nBy the way, Roscioli is a "
                            "romantic Italian restaurant near Campo "
                            "de' Fiori, perfect for an anniversary "
                            "dinner."},
            ]}, {
            "session_id": "s2",
            "messages": [
                {"role": "user", "content": "Any budget travel tips?"},
                {"role": "assistant",
                 "content": "Sure! Here are some budget tips for "
                            "backpackers traveling on a dime."},
            ]}])
        return a

    QUESTION = ("Can you remind me of the name of the romantic "
                "Italian restaurant in Rome you recommended for our "
                "anniversary dinner?")

    def test_gate_speaker_recall_and_fact_answer(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertEqual(meta["gate"], "speaker_recall")
        self.assertFalse(meta["abstained"])
        self.assertIn("Roscioli", ans)
        self.assertIn("speaker_recall", meta)
        self.assertEqual(meta["speaker_recall"]["session_id"], "s1")

    def test_disabled_falls_back_to_extractive_path(self):
        a = self._adapter(assistant_recall=False)
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertNotEqual(meta["gate"], "speaker_recall")
        self.assertNotIn("speaker_recall", meta)

    def test_unresolved_form_falls_through_to_gates(self):
        # Question fires the form but no assistant sentence can score:
        # fall through untouched (gate chain owns abstention).
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "Remind me what you recommended about quantum "
            "chromodynamics gauge theory symmetry breaking?")
        self.assertIn(meta["gate"], {"answer", "score", "entropy",
                                     "temporal_arith", "empty"})
        self.assertNotEqual(meta["gate"], "speaker_recall")
        if meta["gate"] != "answer":
            self.assertEqual(ans, ABSTAIN_ANSWER)

    def test_user_source_question_skips_path(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "Remind me what I told you about my trip to Rome with "
            "grandma for our anniversary dinner party.")
        self.assertNotEqual(meta["gate"], "speaker_recall")


class TestEvalWiring(unittest.TestCase):

    def test_run_eval_passes_flag(self):
        import inspect
        from amg_bench_quality import run_eval
        sig = inspect.signature(run_eval)
        self.assertIn("assistant_recall", sig.parameters)
        self.assertIs(sig.parameters["assistant_recall"].default, True)
        sig_a = inspect.signature(LongMemEvalAdapter.__init__)
        self.assertIs(sig_a.parameters["assistant_recall"].default, True)


if __name__ == "__main__":
    unittest.main()
