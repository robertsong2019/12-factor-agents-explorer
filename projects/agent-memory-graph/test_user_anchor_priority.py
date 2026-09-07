"""Cycle 555 — user-anchor priority in the temporal tie ladder.

C554's queue suspected a plan-line beats a realization line on hits;
census (/tmp/c555) found the actual mechanism: the generic-keyword
tie-break is ASSISTANT-BIASED. Generic anchor words are the question's
own scaffolding verbs ("participate in the 5K charity run"), and
assistant replies systematically echo them back ("encourage them to
participate in your event") — so gen-hits promoted a marketing
tangent over the asker's own event report at a later date.

Fix: user-role moves ahead of the generic-keyword tie-break
(distinctive hits stays first). Full census of the 45-row
gate-routing set: mirror 45/45 chain-identical, exactly 1 designed
rescue (gpt4_b0863698 '16 days'->'7 days'), 0 kills; production
replay at wired HEAD 44/45 byte-identical + the rescue; full-500
live re-run 283->284 with zero drift.

The pins below are pure-function miniatures: the assistant-tangent
echo must lose to the user's own report (same distinctive hits),
while distinctive-hit advantage still dominates user-role, and the
C471 future-marker demotion still fires within a role.
"""
from amg_bench_quality import answer_temporal_arith


def _answer(question, lines, qdate):
    ans, _ = answer_temporal_arith(question, list(lines), qdate)
    return ans


def test_user_report_outranks_assistant_verb_echo():
    """Assistant tangent echoing the question verb ('participate in
    your charity event') must NOT outrank the user's own event report
    at a later date when distinctive hits tie."""
    q = "How many days ago did I participate in the 5K charity run?"
    lines = [
        ("[assistant] Great idea! When marketing, encourage people to "
         "participate in your charity event and share the run details.",
         "2023-03-10"),
        ("[user] Update: I joined a charity run this morning and it felt "
         "amazing to finally do it.",
         "2023-03-19"),
    ]
    # both lines carry 'charity' + 'run' (distinctive hits tie at 2);
    # the assistant line carries the generic 'participate'. Under the
    # C471 order the echo won -> 16 days; user-first anchors 03-19.
    assert _answer(q, lines, "2023/03/26 (Sun) 04:13") == "7 days"


def test_distinctive_hits_still_dominates_user_role():
    """The reorder only affects the tie-break tier: a multi-hit
    assistant line still outranks a single-hit user line."""
    q = "How many days ago did I visit the botanical garden?"
    lines = [
        ("[assistant] The botanical garden opens at nine; the botanical "
         "garden shop closes at five, and the garden cafe at four.",
         "2023-04-01"),
        ("[user] I finally got to the garden last week and loved it.",
         "2023-04-08"),
    ]
    # assistant: 'botanical' x2 + 'garden' x3 = 5 hits; user: 1 hit.
    # Hits dominate -> anchor 2023-04-01 -> 14 days, regardless of role.
    assert _answer(q, lines, "2023/04/15 (Sat) 10:00") == "14 days"


def test_future_marker_still_demotes_plan_lines_within_a_role():
    """C471 invariant preserved: between two user lines with equal
    distinctive hits, the plan-shaped line loses to the realized one
    (future-marker key still consulted after user-role)."""
    q = "How many days ago did I participate in the 5K charity run?"
    lines = [
        ("[user] I'm planning to run a charity event soon and want to "
         "invite all my friends and family to join me.",
         "2023-03-10"),
        ("[user] The charity run I did this morning was exhausting but "
         "so rewarding, great atmosphere too.",
         "2023-03-19"),
    ]
    # same role, same distinctive hits -> future-marker demotes the
    # plan line ('planning to') -> realized line anchors 03-19.
    assert _answer(q, lines, "2023/03/26 (Sun) 04:13") == "7 days"
