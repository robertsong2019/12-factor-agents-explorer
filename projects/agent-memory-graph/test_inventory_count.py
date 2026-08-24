"""Cycle 511 — inventory_count: distinct-item enumeration.

The 10th counting form. "How many model kits / musical
instruments / properties did I …" — identity lives in scale/
brand/model codes (1/72 B-29, Tamiya Spitfire, Korg B1) and
descriptors (2-bedroom condo, Cedar Creek), invisible to
enum_count's name/role signatures. Census discipline: exactly
3 fires on the 500-question suite, all previously wrong —
zero hijack surface by construction. Oracle parity: 3/3.
"""
import pytest

from amg_bench_quality import (
    answer_counting, counting_form, _cnt_inventory_count)


def sess(*lines, sid="s0"):
    """One user session from plain line strings."""
    return {"session_id": sid,
            "turns": [{"role": "user", "content": ln}
                      for ln in lines]}


# ------------------------------------------------------------- gate

def test_form_gate_claims_inventory_families():
    assert counting_form(
        "How many model kits have I worked on or bought?") \
        == "inventory_count"
    assert counting_form(
        "How many musical instruments do I currently own?") \
        == "inventory_count"
    assert counting_form(
        "How many properties did I view before making an offer "
        "on the townhouse in the Brookside neighborhood?") \
        == "inventory_count"


def test_form_gate_whitelist_only():
    # family heads outside the whitelist stay with enum_count
    assert counting_form(
        "How many tanks do I currently have, including the "
        "ones in the garage?") == "enum_count"
    assert counting_form(
        "How many weddings have I attended this year?") \
        == "enum_count"
    # rival forms keep their claims
    assert counting_form(
        "How many online courses have I completed in total?") \
        == "number_total"
    assert counting_form("How many times did I visit Rome?") \
        is None
    assert counting_form(
        "How many fitness classes do I attend in a typical "
        "week?") is None


# ------------------------------------------------- kits (scale/brand)

def test_kits_scale_and_brand_identity():
    s = [
        sess("I need tips on photo-etching for my new 1/72 "
             "scale B-29 bomber model kit. I just got this kit "
             "and a 1/24 scale '69 Camaro at a model show."),
        sess("I recently finished a simple Revell F-15 Eagle "
             "kit that I picked up on a whim."),
        sess("I also started working on a diorama featuring a "
             "1/16 scale German Tiger I tank."),
        sess("I recently finished a Tamiya 1/48 scale Spitfire "
             "Mk.V and wasn't happy with the finish."),
    ]
    ans, meta = answer_counting(
        "How many model kits have I worked on or bought?", s)
    assert ans == "5"
    assert meta["form"] == "inventory_count"


def test_kits_hypothetical_next_not_counted():
    s = [
        sess("I'm actually thinking of working on a 1/72 scale "
             "B-29 bomber next, and I'd like to try photo-"
             "etching."),
        sess("I'm thinking of trying enamel washes on my next "
             "project, a 1/48 scale Spitfire."),
    ]
    assert _cnt_inventory_count(
        "How many model kits have I worked on or bought?", s) \
        is None


def test_kits_domain_guards():
    s = [
        sess("I just got my first meal kit delivery from Blue "
             "Apron, including salmon with roasted veggies."),
        sess("I'm considering technical indicators to engineer "
             "features for my stock price prediction model."),
    ]
    assert _cnt_inventory_count(
        "How many model kits have I worked on or bought?", s) \
        is None


# ------------------------------------------------- instruments

def test_instruments_brands_dedup_and_exclusions():
    s = [
        sess("I've been playing my black Fender Stratocaster "
             "electric guitar a lot lately."),
        sess("I've had my black Fender Stratocaster electric "
             "guitar for about 5 years now."),
        sess("I'm thinking of selling my old drum set, a "
             "5-piece Pearl Export, which I haven't played."),
        sess("I'm concerned about the maintenance of my "
             "instruments, especially my piano, a Korg B1."),
        sess("By the way, I've had my acoustic guitar, a "
             "Yamaha FG800, for about 8 years."),
    ]
    ans, meta = answer_counting(
        "How many musical instruments do I currently own?", s)
    assert ans == "4"
    assert meta["form"] == "inventory_count"


def test_instruments_hypothetical_and_foreign():
    s = [
        sess("I'm also thinking of buying a new ukulele, and "
             "I've been eyeing a Cordoba ukulele."),
        sess("I'm trying to motivate my niece to practice her "
             "violin. She just got a new student-level violin."),
        sess("I've been playing my black Fender Stratocaster "
             "electric guitar a lot lately."),
    ]
    ans, _ = answer_counting(
        "How many musical instruments do I currently own?", s)
    assert ans == "1"


# ------------------------------------------------- properties

def test_properties_viewed_with_anchor_exclusion():
    s = [
        sess("I saw the 3-bedroom townhouse in the Brookside "
             "neighborhood on February 22nd. I put in an offer "
             "on February 25th."),
        sess("I actually fell in love with a 2-bedroom condo "
             "on February 15th, but my offer got rejected."),
        sess("I viewed a 1-bedroom condo on February 10th, but "
             "the noise from the highway was a deal-breaker."),
        sess("I've seen some properties that didn't fit my "
             "budget, like that one in Cedar Creek."),
        sess("I recently saw a beautiful 3-bedroom bungalow in "
             "the Oakwood neighborhood on January 22nd."),
    ]
    ans, meta = answer_counting(
        "How many properties did I view before making an offer "
        "on the townhouse in the Brookside neighborhood?", s)
    assert ans == "4"
    assert meta["form"] == "inventory_count"


def test_properties_still_shopping_not_viewed():
    s = [
        sess("I'm currently looking at condos in the downtown "
             "area, and I'm considering a few options."),
    ]
    assert _cnt_inventory_count(
        "How many properties did I view before making an "
        "offer?", s) is None


def test_no_evidence_abstains():
    assert _cnt_inventory_count(
        "How many model kits have I worked on or bought?",
        [sess("The weather was lovely today.")]) is None
