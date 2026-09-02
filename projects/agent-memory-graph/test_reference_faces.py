#!/usr/bin/env python3
"""C541 tests: reference-alias judge faces + where-gate intent guard.

Faces (judge_semantic NEEDS_JUDGE zone): paren-acronym alias +
place-tail complement. Guard (answer_where): did-form questions
demote intention-shaped locative-clause candidates (band-restricted).
"""
import sys

sys.path.insert(0, "/tmp/c541/mod")
import amg_bench_quality as Q


# ---------- paren-acronym face ----------

def test_paren_acronym_face_rescues_ucla_bearer():
    ref = "University of California, Los Angeles (UCLA)"
    ans = ("Also, by the way, I completed my undergrad in CS from UCLA, "
           "which has a great reputation in the industry.")
    assert Q._sem_paren_acronym_face(ref, ans) is True


def test_paren_acronym_face_otp():
    ref = "...one-time passwords (OTP)..."
    ans = ("Two-factor authentication like biometrics or one-time "
           "passwords (OTP) is required.")
    assert Q._sem_paren_acronym_face(ref, ans) is True


def test_paren_acronym_face_absent_token():
    ref = "University of California, Los Angeles (UCLA)"
    assert Q._sem_paren_acronym_face(ref, "I studied at Berkeley.") is False


def test_paren_acronym_face_requires_paren_form():
    ref = "University of California, Los Angeles"
    assert Q._sem_paren_acronym_face(ref, "I studied at UCLA.") is False


def test_paren_acronym_face_not_subset_weakening():
    # number-conflicting pairs return WRONG in guard 1, before the face
    # zone — the face can never rescue them.
    assert Q.judge_semantic("Which room?", "Room 7", "Room 5 (Lab)") == "WRONG"


def test_paren_acronym_face_zone_is_needs_judge_only():
    ref = "University of California, Los Angeles (UCLA)"
    # no acronym token in answer -> no face; pair stays NEEDS_JUDGE
    assert Q.judge_semantic("Where did I study?", "I studied at Berkeley.",
                            ref) == "NEEDS_JUDGE"


# ---------- place-complement face ----------

def test_place_complement_face_rescues_melbourne():
    ref = "University of Melbourne in Australia"
    ans = ("I actually went there on a student exchange program. It was "
           "such an amazing experience being at the University of "
           "Melbourne.")
    assert Q._sem_place_complement_face(ref, ans) is True
    assert Q.judge_semantic(
        "Where did I go on a student exchange program during my studies?",
        ans, ref) == "CORRECT"


def test_place_complement_face_tail_present_no_claim():
    ref = "University of Melbourne in Australia"
    ans = "The University of Melbourne in Australia is famous."
    assert Q._sem_place_complement_face(ref, ans) is False


def test_place_complement_face_head_incomplete():
    ref = "Master of Science in Data Science"
    assert Q._sem_place_complement_face(ref, "I finished my Master's.") is False


def test_place_complement_face_requires_capital_tail():
    ref = "Bachelor degree in computer science"   # lowercase tail: no match
    assert Q._sem_place_complement_face(ref, "I finished my bachelor.") is False


# ---------- where-gate intent guard ----------

def _aw(question, turns, sid="session_1"):
    sessions = [{"session_id": sid, "turns": turns}]
    nodes = {"n1": {"session_id": sid}}
    return Q.answer_where(question, sessions, ["n1"], nodes, "")


UCLA_TURNS = [
    {"role": "user", "content": ("I'm considering pursuing a Master's "
                                 "degree in Data Science and I've narrowed "
                                 "down my options to Stanford, Berkeley, "
                                 "and Carnegie Mellon.")},
    {"role": "assistant", "content": "Those are great schools!"},
    {"role": "user", "content": ("Also, by the way, I completed my "
                                 "undergrad in CS from UCLA, which has a "
                                 "great reputation in the industry.")},
]


def test_guard_demotes_intent_winner_did_form():
    q = "Where did I complete my Bachelor's degree in Computer Science?"
    ans, meta = _aw(q, UCLA_TURNS)
    assert "UCLA" in ans


def test_guard_tangent_clause_marker_not_demoted():
    # marker lives in a NON-locative trailing clause -> untouched
    turns = [{"role": "user", "content": (
        "I was just at my cousin's wedding at the Grand Ballroom last "
        "weekend, and I want to get her something nice for the "
        "housewarming.")}]
    q = "Where did I attend my cousin's wedding?"
    ans, meta = _aw(q, turns)
    assert "Grand Ballroom" in ans


def test_guard_only_fires_on_did_form():
    # present-tense where question: ranking untouched
    q = "Where should I pursue my Master's degree?"
    ans, meta = _aw(q, UCLA_TURNS)
    assert "Stanford" in ans


def test_guard_all_marked_untouched():
    turns = [{"role": "user", "content": (
        "I'm considering relocating my studio to Portland, Oregon next "
        "spring.")}]
    q = "Where did I move my studio?"
    ans, meta = _aw(q, turns)
    assert "Portland" in ans
