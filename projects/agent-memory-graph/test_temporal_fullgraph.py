"""Cycle 551 — temporal full-graph-first anchor resolution.

Census /tmp/c551 (2026-09-06, 46-row temporal population):
window-first loses 4 rows to distractor-corpus crowding — noise lines
(Tribunal-style lexically-mirroring text) outrank the true event line
inside the retrieval top-k, while the unchanged C471 tie ladder picks
the true lines when given the FULL candidate set. Production A/B:
+4 RESCUE (0db4c65d 26→18d, gpt4_21adecb5 1→6mo, 08f4fc43 49→30d,
a3045048 23→7d) / 0 KILL / 42 rows byte-identical; flag-off arm
reproduced stored preds with 0 drift. Ladder variants (gen-ascending,
role-early) were censused at +0/−0 — the ladder is NOT the problem,
candidate availability is.

The pins below cover the wiring contract (what the flag controls)
and a pure-function miniature of the crowding mechanism.
"""
from unittest.mock import patch

import amg_bench_quality as Q
from amg_bench_quality import LongMemEvalAdapter, answer_temporal_arith

QUESTION = "How many days ago did I adopt the labrador puppy?"
QDATE = "2023/06/10 (Sat) 09:00"


def build_adapter(flag):
    ad = LongMemEvalAdapter(temporal_fullgraph=flag)
    sessions = [
        {"session_id": "s_junk",
         "messages": [{"role": "assistant",
                       "content": "Adopting a labrador puppy requires "
                                  "preparation and patience."}]},
        {"session_id": "s_true",
         "messages": [{"role": "user",
                       "content": "I adopted the labrador puppy today "
                                  "and he already loves the yard."}]},
    ]
    ad.ingest_sessions(sessions, session_dates={"s_junk": "2023-06-10",
                                                "s_true": "2023-06-03"})
    return ad


# --------------------------------------------------- wiring contract

def test_default_fullgraph_single_call_on_full_messages():
    """Default flag-on: exactly ONE resolution call, fed the FULL
    message set (not the retrieval window); telemetry marks it."""
    ad = build_adapter(True)
    calls = []
    real = Q.answer_temporal_arith

    def spy(question, dated, qdate=""):
        calls.append([ln for ln, _ in dated])
        return ("9 days", {"form": "ago", "value": 9})

    with patch.object(Q, "answer_temporal_arith", spy):
        ans, meta = ad.answer_extractive(QUESTION, QDATE)
    assert ans == "9 days"
    assert meta["gate"] == "temporal_arith"
    assert meta["temporal"]["fallback"] == "fullgraph_first"
    assert len(calls) == 1
    # full graph = both sessions' messages, junk included
    assert len(calls[0]) == 2


def test_flagoff_window_first_then_c472_fallback():
    """Flag-off restores the legacy two-step path: window lines first,
    and only when the window cannot resolve, the full-graph retry."""
    ad = build_adapter(False)
    seen = []

    def fake(question, dated, qdate=""):
        seen.append([ln for ln, _ in dated])
        if len(seen) == 1:
            return None, {"form": "ago"}          # window cannot resolve
        return ("3 days", {"form": "ago", "value": 3})

    with patch.object(Q, "answer_temporal_arith", fake):
        ans, meta = ad.answer_extractive(QUESTION, QDATE)
    assert ans == "3 days"
    assert meta["gate"] == "temporal_arith"
    assert meta["temporal"]["fallback"] == "full_graph"
    assert len(seen) == 2
    # first call = window (subset), second = full graph
    assert len(seen[0]) <= len(seen[1])


def test_flagoff_window_resolved_no_retry():
    """Flag-off: a window-resolved answer is never second-guessed
    (C472 window-first preserved on the legacy path)."""
    ad = build_adapter(False)
    calls = []

    def fake(question, dated, qdate=""):
        calls.append(1)
        return ("5 days", {"form": "ago", "value": 5})

    with patch.object(Q, "answer_temporal_arith", fake):
        ans, meta = ad.answer_extractive(QUESTION, QDATE)
    assert ans == "5 days"
    assert "fallback" not in meta.get("temporal", {})
    assert len(calls) == 1


# ----------------------------------- mechanism miniature (pure fn)

def test_full_candidate_set_un_drowns_true_event_line():
    """The census mechanism in miniature: given ONLY the crowding
    junk line the ladder must answer from it ('0 days' — wrong);
    given the full candidate set the SAME ladder picks the true
    user event line (7 days). Candidate availability, not ladder
    ordering, is what the flag changes."""
    junk = ("[assistant] Adopting a labrador puppy requires "
            "preparation and patience.", "2023-06-10")
    true = ("[user] I adopted the labrador puppy today and he "
            "already loves the yard.", "2023-06-03")
    ans_win, _ = answer_temporal_arith(QUESTION, [junk], QDATE)
    ans_full, _ = answer_temporal_arith(QUESTION, [junk, true], QDATE)
    assert ans_win == "0 days"          # junk-only window: wrong
    assert ans_full == "7 days"         # full set: true line wins


def test_window_missing_anchor_falls_through_untouched():
    """No candidate for the anchor anywhere → None on both paths;
    the gate chain owns abstention (no fabrication)."""
    ans, detail = answer_temporal_arith(
        QUESTION, [("[user] The weather was lovely last week.",
                    "2023-06-01")], QDATE)
    assert ans is None
    assert detail["form"] == "ago"
