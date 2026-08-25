"""Cycle 514 — museum_count: venue visitation with a month
window. The 11th counting form. "How many different museums or
galleries did I visit …" — identity lives in venue proper names
(Natural History Museum, "The Art Cube"), realization in past
visit verbs, and the question's month window is load-bearing
(it excludes the January Modern-Art-Museum workshop visit while
keeping 2/8 and 15th February). Census discipline: exactly 2
fires on the 500-question suite, both previously wrong — zero
hijack surface by construction. Oracle parity: 2/2 (February=2,
December twin=0).
"""
import pytest

from amg_bench_quality import (
    ABSTAIN_ANSWER, answer_counting, counting_form,
    _cnt_museum_count)


def sess(*lines, sid="s0"):
    """One user session from plain line strings."""
    return {"session_id": sid,
            "turns": [{"role": "user", "content": ln}
                      for ln in lines]}


Q_FEB = ("How many different museums or galleries did I visit "
         "in the month of February?")
Q_DEC = "How many different museums or galleries did I visit in December?"
Q_NOWIN = "How many museums did I visit?"


# ------------------------------------------------------------- gate

def test_form_gate_claims_museum_visitation():
    assert counting_form(Q_FEB) == "museum_count"
    assert counting_form(Q_DEC) == "museum_count"
    assert counting_form(Q_NOWIN) == "museum_count"
    assert counting_form(
        "How many galleries did I visit last year?") \
        == "museum_count"


def test_form_gate_rivals_keep_their_claims():
    # temporal-arithmetic / ordering / recency are NOT this form
    assert counting_form(
        "How many days passed between my visit to the Museum "
        "of Modern Art (MoMA) and the next one?") is None
    assert counting_form(
        "How many months have passed since I last visited a "
        "museum with a friend?") is None
    assert counting_form(
        "What is the order of the six museums I visited from "
        "earliest to latest?") is None
    # other how-many families unchanged
    assert counting_form(
        "How many model kits have I worked on or bought?") \
        == "inventory_count"
    assert counting_form(
        "How many weddings have I attended in this year?") \
        == "enum_count"


# ------------------------------------------------ month window logic

def test_february_window_counts_two_dated_venues():
    s = sess(
        "I'm looking for some art supply stores in the city. "
        "By the way, I took my niece to the Natural History "
        "Museum on 2/8 and she loved the dinosaur exhibit!",
        "I actually met the curator, Rachel Lee, at the "
        "opening night of The Art Cube on 15th February, and "
        "she mentioned some upcoming exhibitions.",
        "Can you suggest any local art museums or galleries "
        "that offer workshops or classes? By the way, I "
        "recently got back into art after attending a guided "
        "workshop at the Modern Art Museum in January.")
    assert answer_counting(Q_FEB, [s]) == ("2", {"form": "museum_count"})


def test_december_twin_abstains():
    # negative-existence twin: memory never mentions a December
    # museum visit — silence is a presupposition failure, the
    # honest protocol answer is abstention, not a fabricated 0
    s = sess(
        "I took my niece to the Natural History Museum on 2/8 "
        "and she loved the dinosaur exhibit!",
        "Since I met the curator, Rachel Lee, at the opening "
        "night of The Art Cube on 15th February, I must have "
        "gotten the information from her.")
    assert answer_counting(Q_DEC, [s]) \
        == (ABSTAIN_ANSWER, {"form": "museum_count"})


def test_out_of_window_visit_excluded():
    s = sess("I attended a workshop at the Modern Art Museum "
             "in January.")
    assert _cnt_museum_count(Q_FEB, [s]) == ABSTAIN_ANSWER


def test_no_window_counts_undated_realized_visits():
    s = sess("I visited the Natural History Museum with my "
             "niece and it was wonderful.")
    assert _cnt_museum_count(Q_NOWIN, [s]) == "1"


def test_undated_visit_does_not_fabricate_window_membership():
    s = sess("I visited the Natural History Museum with my "
             "niece and it was wonderful.")
    assert _cnt_museum_count(Q_FEB, [s]) == ABSTAIN_ANSWER


# ------------------------------------------------ realization wall

def test_future_mentions_excluded():
    s = sess("I'll definitely check out the National "
             "Waterfront Museum and see what exhibits they "
             "have on display.")
    assert _cnt_museum_count(Q_FEB, [s]) == ABSTAIN_ANSWER
    assert _cnt_museum_count(Q_NOWIN, [s]) == ABSTAIN_ANSWER


def test_speculative_remention_excluded():
    s = sess("I might actually attend another event at "
             "\"The Art Cube\" soon, it was great last time.")
    assert _cnt_museum_count(Q_NOWIN, [s]) == ABSTAIN_ANSWER


def test_question_clauses_and_assistant_turns_ignored():
    s = sess("Do you know if there are any art galleries or "
             "museums that feature abstract art?")
    s2 = {"session_id": "s1", "turns": [
        {"role": "assistant",
         "content": "You visited the Natural History Museum on "
                    "2/8 and the Modern Art Museum in January."},
        {"role": "user", "content": "thanks!"}]}
    assert _cnt_museum_count(Q_FEB, [s, s2]) == ABSTAIN_ANSWER


# ------------------------------------------------ identity grammar

def test_rementions_dedupe_by_normalized_name():
    s = sess(
        "I took my niece to the Natural History Museum on 2/8!",
        "I recently visited the Natural History Museum with my "
        "niece, and we had a great time.",
        "I remember my recent visit to the Natural History "
        "Museum with my niece.")
    assert _cnt_museum_count(Q_FEB, [s]) == "1"


def test_venue_level_date_inheritance():
    # undated realized clause + dated realized clause for the
    # same venue -> venue inherits the in-window date once
    s = sess(
        "I actually met the curator at the opening night of "
        "The Art Cube on 15th February.",
        "By the way, I recently met a curator at the opening "
        "night of The Art Cube, a new contemporary art "
        "gallery.")
    assert _cnt_museum_count(Q_FEB, [s]) == "1"


def test_quoted_title_and_bare_title_are_one_venue():
    s = sess(
        "I actually met a curator at the opening night of "
        "\"The Art Cube\" on 15th February.",
        "I was at the opening of The Art Cube again last "
        "weekend, what a gallery.")
    assert _cnt_museum_count(Q_FEB, [s]) == "1"


def test_generic_event_np_rejected():
    # "opening night" is an event, not a venue (grammar guard)
    s = sess("I was at the opening night on 15th February and "
             "it was lovely.")
    assert _cnt_museum_count(Q_FEB, [s]) == ABSTAIN_ANSWER


def test_person_after_comma_not_a_venue():
    # "Rachel Lee" follows a comma, no visit-prep anchor
    s = sess("I met the curator, Rachel Lee, at the opening "
             "on 15th February. I also visited the Natural "
             "History Museum on 2/8.")
    assert _cnt_museum_count(Q_FEB, [s]) == "1"


def test_museum_of_form_supported():
    s = sess("Last winter I toured the Museum of Modern Art "
             "in February.")
    assert _cnt_museum_count(Q_FEB, [s]) == "1"


def test_turn_candidacy_requires_context_word():
    # a turn with no museum/gallery/exhibit/curator token is
    # never scanned (same candidacy unit as enum_count)
    s = sess("I visited the Golden Gate Bridge on 2/8.")
    assert _cnt_museum_count(Q_FEB, [s]) == ABSTAIN_ANSWER


# ---------------------------------------------------- date formats

@pytest.mark.parametrize("line,q,want", [
    ("I visited the City Museum on 2/8.", Q_FEB, "1"),      # M/D
    ("I visited the City Museum on 15th February.", Q_FEB, "1"),
    ("I visited the City Museum on February 15.", Q_FEB, "1"),
    ("I visited the City Museum during February.", Q_FEB, "1"),
    ("I visited the City Museum in March.", Q_FEB, ABSTAIN_ANSWER),
])
def test_date_format_matrix(line, q, want):
    assert _cnt_museum_count(q, [sess(line)]) == want


def test_empty_window_abstains_not_zero():
    # this family owns its silence: the question fired the
    # gate, zero qualifying venues is a presupposition failure
    # -> honest abstention (negative-existence twins score
    # via meta["abstained"], C514)
    assert _cnt_museum_count(Q_DEC, [sess("nothing here")]) \
        == ABSTAIN_ANSWER
