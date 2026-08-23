"""Cycle 503 — enum_count: enumeration-signature counting (#084).

The 5th counting form. Entity-count questions whose countable
units carry built-in dedup keys (proper names / role possessives /
N-unit sizes) bypass the predicate-semantics wall. Oracle parity:
Research #084 v5.2 fired 4/133 with precision 1.00 (+4/0).
"""
import os
import pytest

from amg_bench_quality import (
    answer_counting, counting_form, _cnt_enum_count)


def sess(*lines):
    """One user session from plain line strings."""
    return {"session_id": "s0",
            "turns": [{"role": "user", "content": ln}
                      for ln in lines]}


# ------------------------------------------------------------- gate

def test_form_gate_claims_plain_how_many():
    assert counting_form(
        "How many weddings have I attended in this year?") \
        == "enum_count"
    assert counting_form(
        "How many babies were born to friends and family "
        "members this year?") == "enum_count"
    assert counting_form(
        "How many tanks do I currently have, including the "
        "ones in the garage?") == "enum_count"


def test_form_gate_excludes_time_heads_and_rivals():
    # time-unit heads belong to duration/unit forms
    assert counting_form(
        "How many hours did I spend on the project in total?") \
        == "unit_sum"
    assert counting_form(
        "How many days did I spend hiking in total?") \
        == "duration_sum"
    # 'times' / comparisons are not enumerations
    assert counting_form("How many times did I visit Rome?") is None
    assert counting_form(
        "How many years older is Tom than Mark?") is None
    # frequency forms stay with freq_days
    assert counting_form(
        "How many days a week do I run?") == "freq_days"


# ------------------------------------------------- size signatures

def test_sizes_are_dedup_keys():
    s = [sess("I set up a 20-gallon tank in the living room.",
              "The 5-gallon tank is for the betta.",
              "There's also a 1-gallon hospital tank.")]
    ans, meta = answer_counting(
        "How many tanks do I currently have, including the "
        "spare?", s)
    assert ans == "3"
    assert meta["form"] == "enum_count"


def test_repeated_size_dedups():
    s = [sess("My 20-gallon tank is doing great.",
              "I cleaned the 20-gallon tank again.")]
    ans, _ = answer_counting(
        "How many tanks do I currently have?", s)
    assert ans == "1"   # distinct sizes are the dedup keys


# ------------------------------------------------- name signatures

def test_name_possessives_across_sessions_dedup():
    s = [
        {"session_id": "a", "turns": [
            {"role": "user",
             "content": "Last month I went to Emily's wedding."}]},
        {"session_id": "b", "turns": [
            {"role": "user",
             "content": "At Emily's wedding the cake was amazing."}]},
        {"session_id": "c", "turns": [
            {"role": "user",
             "content": "I hear my college roommate's wedding "
                        "was a small affair."}]},
    ]
    ans, _ = answer_counting(
        "How many weddings have I attended this year?", s)
    assert ans == "2"   # Emily (once) + roommate


def test_name_absorbs_role_in_same_clause():
    s = [sess("My cousin Rachel's wedding was beautiful.")]
    ans, _ = answer_counting(
        "How many weddings have I attended?", s)
    assert ans == "1"   # cousin Rachel = ONE instance


def test_named_x_signature():
    s = [sess("We adopted a cat named Jasper.",
              "My neighbor adopted a cat named Max.")]
    ans, _ = answer_counting(
        "How many cats were adopted by people I know?", s)
    assert ans == "2"


def test_twins_appositive_supplies_names():
    # mirrors oracle 2e6d26dc: appositive captures Ava/Lily;
    # the bare-twins +1 arithmetic retires when names are direct
    s = [sess("I'm planning a baby gift for my aunt's twins, "
              "Ava and Lily, who were born in April.",
              "Charlotte's baby girl arrived last week.")]
    ans, _ = answer_counting(
        "How many babies were born to friends and family "
        "members?", s)
    assert ans == "3"   # Ava + Lily (appositive) + Charlotte


def test_bare_twins_without_appositive_adds_one():
    s = [sess("Jasper's baby was born in May.",
              "Max had twins, a baby boy and a baby girl!",
              "Charlotte's baby arrived too.")]
    ans, _ = answer_counting(
        "How many babies were born to friends?", s)
    assert ans == "3"   # Jasper + Charlotte + 1 twins arithmetic


# ------------------------------------------------ exclusion walls

def test_missed_exclusion_verb_voids_signature():
    s = [sess("I missed Jack's graduation ceremony.",
              "Alex's graduation ceremony was lovely.",
              "Emma's ceremony had great speeches.")]
    ans, _ = answer_counting(
        "How many graduation ceremonies have I attended?", s)
    assert ans == "2"   # Jack voided — missed != attended


def test_shower_tail_window_exclusion():
    s = [sess("I hosted Rachel's baby shower on Saturday.",
              "Jasper's baby was born in May.")]
    ans, _ = answer_counting(
        "How many babies were born to friends?", s)
    assert ans == "1"   # shower != birth; same-clause true sig
    # survives because exclusion is window-local (v5.1 lesson)


# --------------------------------------------------- ownership gate

def test_my_inventory_suppresses_name_signatures():
    s = [sess("Billie Eilish's album is fantastic.",
              "I streamed it all weekend.")]
    ans, _ = answer_counting(
        "How many albums do I own?", s)
    assert ans is None   # artist possessive != my inventory


def test_my_inventory_sizes_still_valid():
    s = [sess("I bought a 55-gallon tank last week.")]
    ans, _ = answer_counting(
        "How many tanks have I bought?", s)
    assert ans == "1"


# ------------------------------------------------ honest abstention

def test_no_signature_falls_through():
    s = [sess("I returned the boots and picked up the blazer.")]
    ans, meta = answer_counting(
        "How many clothing items did I deal with?", s)
    assert ans is None   # no names/roles/sizes -> gate owns it


def test_no_candidate_lines_falls_through():
    s = [sess("The weather was lovely all week.")]
    ans, _ = answer_counting(
        "How many weddings have I attended?", s)
    assert ans is None


# ---------------------------------------------------- oracle parity

@pytest.mark.skipif(not os.path.exists("/tmp/lme_s.json"),
                    reason="LongMemEval fixture not on disk")
def test_oracle_parity_four_questions():
    """Production mechanism on the #084 oracle four (evidence =
    answer sessions) must reproduce prototype v5.2 exactly."""
    import json
    data = json.load(open("/tmp/lme_s.json"))
    byid = {d["question_id"]: d for d in data}
    qids = {"46a3abf7": "3",   # tanks (size sigs)
            "gpt4_2f8be40d": "3",   # weddings (Emily+roommate)
            "2e6d26dc": "5",   # babies (Jasper/Max/Charlotte/
                               # Ava/Lily appositive)
            "81507db6": "3"}   # ceremonies (missed Jack excluded)
    for qid, want in qids.items():
        d = byid[qid]
        ans_ids = set(d["answer_session_ids"])
        sesss = [
            {"session_id": sid, "turns": s}
            for s, sid in zip(d["haystack_sessions"],
                              d["haystack_session_ids"])
            if sid in ans_ids]
        got = _cnt_enum_count(d["question"], sesss)
        assert got == want, (qid, got, want)
