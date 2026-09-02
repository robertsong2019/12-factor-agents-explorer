#!/usr/bin/env python3
"""C542 tests: quoted-core reference-wrap judge face.

_sem_quoted_core_face: a reference that wraps its asserted fact in
quotation marks (frame + quoted core) — a candidate equal to the
quoted core (normalized) is the complete fact, not a weaker subset.
Live case: 8752c811 (GT "The 27th parameter was 'Sound effects
(e.g., ambient, diegetic, non-diegetic, etc.)'." vs the byte-identical
bare answer — subset veto mis-read frame tokens as missing content).
"""
import sys

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as Q


# ---------- face unit ----------

def test_quoted_core_face_rescues_8752c811():
    ref = ("The 27th parameter was 'Sound effects (e.g., ambient, "
           "diegetic, non-diegetic, etc.)'.")
    ans = "Sound effects (e.g., ambient, diegetic, non-diegetic, etc.)"
    assert Q._sem_quoted_core_face(ref, ans) is True


def test_quoted_core_face_double_quotes():
    ref = 'She said "Paris is wonderful in spring" during the trip.'
    ans = "Paris is wonderful in spring"
    assert Q._sem_quoted_core_face(ref, ans) is True


def test_quoted_core_face_curly_quotes():
    ref = "The winner was \u201cAbsinthe\u201d, chosen by the panel."
    ans = "Absinthe"
    assert Q._sem_quoted_core_face(ref, ans) is True


def test_quoted_core_face_negative_no_wrap_match():
    ref = "The 27th parameter was 'Sound effects (e.g., ambient, diegetic)'."
    ans = "Sound effects and music"
    assert Q._sem_quoted_core_face(ref, ans) is False


def test_quoted_core_face_negative_unquoted_frame():
    ref = "The 27th parameter was Sound effects and similar audio options."
    ans = "Sound effects"
    # no quotes in reference at all -> face never fires (subset veto stands)
    assert Q._sem_quoted_core_face(ref, ans) is False


def test_quoted_core_face_apostrophe_does_not_open_span():
    ref = "It's true the code name was 'Zephyr' all along."
    # lookbehind must block the mid-word apostrophe in "It's" from
    # opening a span ("s true the code name was" is NOT a quote)
    assert Q._sem_quoted_core_face(ref, "s true the code name was") is False
    assert Q._sem_quoted_core_face(ref, "Zephyr") is True


def test_quoted_core_face_negative_partial_quote():
    ref = "The 27th parameter was 'Sound effects (e.g., ambient)'."
    ans = "Sound effects"
    assert Q._sem_quoted_core_face(ref, ans) is False


# ---------- judge_semantic integration ----------

def test_judge_8752c811_wrapped_gt_bare_answer():
    ref = ("The 27th parameter was 'Sound effects (e.g., ambient, "
           "diegetic, non-diegetic, etc.)'.")
    ans = "Sound effects (e.g., ambient, diegetic, non-diegetic, etc.)"
    assert Q.judge_semantic("What was the 27th parameter?", ans, ref) == "CORRECT"


def test_judge_stays_wrong_without_face():
    # subset veto still stands when the candidate is a proper
    # fragment of the quoted core (face requires full equality)
    ref = "The 27th parameter was 'Sound effects (e.g., ambient)'."
    ans = "ambient"
    assert Q.judge_semantic("What was the 27th parameter?", ans, ref) == "WRONG"


def test_judge_quoted_core_wrong_number_still_vetoed_upstream():
    # a candidate equal to the quoted core can never carry a foreign
    # number (core is a reference substring) — guards 1-2 stay intact
    ref = "The total was '$120' at checkout, not more."
    assert Q.judge_semantic("What was the total?", "$120", ref) == "CORRECT"
    assert Q.judge_semantic("What was the total?", "$95", ref) == "WRONG"


def test_two_char_core_via_face_and_one_char_floor():
    # frame carries a content token ("chosen") so the strict-subset
    # branch is reached; a 2-char quoted core fires the face ...
    ref = "The chosen codename was 'XY' for the project."
    assert Q.judge_semantic("What was the codename?", "XY", ref) == "CORRECT"
    # ... while a 1-char quoted core stays vetoed (documented
    # conservatism: spans need >=2 chars so stray marks never open one)
    ref1 = "The chosen letter was 'x' on the form."
    assert Q.judge_semantic("What was the letter?", "x", ref1) == "WRONG"
