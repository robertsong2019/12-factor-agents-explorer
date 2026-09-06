"""Cycle 553 — duration-family faces: M1 unit discipline + M3 topic-
anchored recency for object-NP questions.

Census /tmp/c553 (2026-09-07, 66-row gate=counting production replay):
2 RESCUE (e831120c 3→3.5 weeks franchise sum, 71315a70 '0.5'→'10-12
hours topic recency) / 0 KILL / 64 byte-identical. Poison pins below:
unit-less binge captures ("read the subreddit for like a") poisoned the
starwars franchise key and starved the real 1.5-week marathon; the
realized-activity regex ("went for a 30-minute walk") fired for an
object-NP sculpture question it cannot answer.
"""
import pytest

from amg_bench_quality import _dur_m1, _dur_m3


def sess(*lines):
    return {"session_id": "s0",
            "turns": [{"role": "user", "content": ln}
                      for ln in lines]}


def multi_sess(*sessions):
    return [{"session_id": f"s{j}", "turns": [{"role": "user",
                                               "content": ln}]}
            for j, ln in enumerate(sessions)]


# ------------------------------------------------------- M1 unit face

def test_m1_franchise_half_sum():
    """e831120c: MCU 'two weeks' + Star Wars 'a week and a half'
    = 3.5 weeks (was 3: the 1.5 was starved by a unit-less
    starwars-keyed garbage match)."""
    s = multi_sess(
        "I've had some crazy movie binges lately, like when I watched "
        "all 22 Marvel Cinematic Universe movies in two weeks.",
        "I read the subreddit for like a month or two like nobody's "
        "business, it was a Star Wars phase.",
        "I just finished a Star Wars marathon, watched all the main "
        "films in a week and a half, it was a wild ride!")
    got = _dur_m1(
        "How many weeks did it take me to watch all the Marvel "
        "Cinematic Universe movies and the main Star Wars films?", s)
    assert got == "3.5 weeks"


def test_m1_unitless_capture_not_duration():
    """A unit-less capture ('for like a') contributes nothing —
    output unit is weeks, 'a' is not duration evidence."""
    s = [sess("I read the subreddit for like a or two, all about "
              "Star Wars lore.")]
    got = _dur_m1(
        "How many weeks did it take me to watch all the Star Wars "
        "films?", s)
    assert got is None


def test_m1_franchise_dedup_preserved():
    """Re-mention of the same franchise adds nothing (C505 M1
    e831120c 4.5→3.5 lesson still holds)."""
    s = multi_sess(
        "I watched all 22 Marvel Cinematic Universe movies in two "
        "weeks last month.",
        "Like I said, I binged the Marvel Cinematic Universe movies "
        "in two weeks, unforgettable.")
    got = _dur_m1(
        "How many weeks did it take me to watch all the Marvel "
        "Cinematic Universe movies?", s)
    assert got == "2 weeks"


# ------------------------------------------------------- M3 topic face

def test_m3_topic_recency_latest_wins():
    """71315a70: 5-6 hours early, 10-12 hours latest session →
    '10-12 hours' (knowledge-update; was 0.5 from a walk regex)."""
    s = multi_sess(
        "I've been working on an abstract ocean sculpture at home, "
        "and I've spent around 5-6 hours on it so far.",
        "I've been spending a lot of time on my abstract ocean "
        "sculpture lately - I've already put in 10-12 hours, and "
        "it's still a work in progress.")
    got = _dur_m3(
        "How many hours have I spent on my abstract ocean sculpture?",
        s)
    assert got == "10-12 hours"


def test_m3_topic_range_format_preserved():
    """The exact-match contract needs the range string verbatim."""
    s = [sess("My abstract ocean sculpture has taken 10-12 hours of "
              "my weekends so far.")]
    got = _dur_m3(
        "How many hours have I spent on my abstract ocean sculpture?",
        s)
    assert got == "10-12 hours"


def test_m3_activity_question_keeps_realized_path():
    """7024f17c anchor: activity-word questions keep the realized-
    activity regex path (walk-or-jog → 0.5 hours; plan wall holds)."""
    s = [sess("This week I went for a 30-minute walk or jog on "
              "Saturday. I keep planning to jog daily next week.")]
    got = _dur_m3("How many hours of jogging and yoga did I do last "
                  "week?", s)
    assert got == "0.5 hours"


def test_m3_object_np_no_anchored_evidence_abstains():
    """Object-NP form but no topic-anchored hour mention → no
    fabricated answer from unrelated activity durations."""
    s = [sess("I went for a 30-minute walk this morning near the "
              "studio where my abstract ocean sculpture is drying.")]
    got = _dur_m3(
        "How many hours have I spent on my abstract ocean sculpture?",
        s)
    assert got is None


def test_m3_topic_ignores_plan_mood_and_other_topics():
    """Habitual/planned durations and off-topic hour mentions never
    vote; only anchored, stated quantities do."""
    s = multi_sess(
        "I'd love to spend 40 hours on a bronze statue someday.",
        "I've spent 6 hours on my abstract ocean sculpture today.")
    got = _dur_m3(
        "How many hours have I spent on my abstract ocean sculpture?",
        s)
    assert got == "6 hours"


def test_m3_half_hour_word_form():
    """'half an hour' anchored on the topic resolves to 0.5 hours."""
    s = [sess("So far my abstract ocean sculpture has taken half an "
              "hour of actual work, honestly.")]
    got = _dur_m3(
        "How many hours have I spent on my abstract ocean sculpture?",
        s)
    assert got == "0.5 hours"


def test_m3_gate_still_blocks_non_m3_forms():
    """Questions without did i/have i/do i never reach the face."""
    s = [sess("I spent 10-12 hours on my abstract ocean sculpture.")]
    got = _dur_m3("How many hours did my sister spend on her abstract "
                  "ocean sculpture?", s)
    assert got is None
