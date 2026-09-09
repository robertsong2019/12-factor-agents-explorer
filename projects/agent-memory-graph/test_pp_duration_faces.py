"""C563: pp_duration residual faces — same-sentence state binding +
units-progressive head routing + session-span route (d).

Two wrongs, one family:

* gpt4_cd90e484 ("How long did I use my new binoculars before I
  saw the American goldfinches...") — route (b) resolves but the
  state pick ties on single-keyword overlap and Python ``max``
  keeps the FIRST maximal: a cross-sentence tenure mention
  ("...for about a month now" in a sentence without the keyword)
  beat the same-sentence acquisition ("Speaking of my new
  binoculars, I got them exactly three weeks ago"). Fix: among
  state candidates tied on overlap, prefer duration expressions
  whose containing sentence carries a state keyword.

* 6e984301 ("How many weeks have I been taking sculpting classes
  when I invested in my own set of sculpting tools?") — the
  ``how long`` head never matched, so the question fell to the
  counting gate (whose "6 weeks" mirrors the assistant's own
  "6-week experience" hallucination). Evidence is "today"-anchored
  (no ago/now expressions), so route (b) cannot resolve it even
  when routed: both anchors are same-session "today" facts and the
  span is the SESSION-PAIR distance (03-04 − 02-11 = 21 d = 3
  weeks = oracle). Fix: units-progressive head ("how many <unit>s
  have/had I been <verb-ing> … when|before") routes into the gate;
  new route (d) resolves session spans; the judge tolerates the
  oracle's bare-number render ("3") when the question itself
  supplies the unit.
"""

import unittest

from amg_bench_quality import (
    answer_pp_duration,
    pp_duration_form,
    pp_duration_judge,
)

# ── fixture: same-sentence vs cross-sentence state (binoculars) ───
BINO_Q = ("How long did I use my new binoculars before I saw the "
          "American goldfinches returning to the area?")
BINO_SESSIONS = [
    ("2023-05-20", [
        {"role": "user", "content": (
            "I'm looking for some tips on how to improve my bird "
            "identification skills. I've been listening to bird "
            "calls online for about a month now, and it's been "
            "helping. By the way, my new binoculars has made a "
            "huge difference in my birding trips.")},
        {"role": "user", "content": (
            "I've been trying to focus on bird shapes and "
            "silhouettes, as you suggested. I noticed that my new "
            "binoculars have really helped me get a better look "
            "at the birds, especially when they're far away. "
            "Speaking of my new binoculars, I remember that I "
            "got them exactly three weeks ago, after months of "
            "waiting.")},
    ]),
    ("2023-05-20", [
        {"role": "user", "content": (
            "I'm looking for some tips on improving my bird "
            "identification skills. I've been listening to bird "
            "calls online for about a month now, and it's been "
            "helping, but I'm still not confident in my "
            "abilities. By the way, I did manage to sneak in some "
            "birding time a week ago when I took a walk around my "
            "neighborhood after dinner. I saw a few common birds "
            "like robins and sparrows, but nothing too exciting. "
            "Except, I did notice that the American goldfinches "
            "seem to be returning to the area, which is always a "
            "nice sign of spring.")},
    ]),
]

# ── fixture: units-progressive + session-span (sculpting) ─────────
SCULPT_Q = ("How many weeks have I been taking sculpting classes "
            "when I invested in my own set of sculpting tools?")
SCULPT_SESSIONS = [
    ("2023-02-11", [
        {"role": "user", "content": (
            "I'm thinking of entering a local art competition "
            "with a sculpture category. By the way, I just "
            "started taking sculpting classes at a local art "
            "studio today, every Saturday morning from 10 am to "
            "1 pm, and it's been a great experience so far.")},
    ]),
    ("2023-03-04", [
        {"role": "user", "content": (
            "I actually got my own set of sculpting tools today, "
            "including a modeling tool set, a wire cutter, and a "
            "sculpting mat.")},
    ]),
]

# ── fixture: cross-sentence on BOTH state candidates (tie kept) ───
TIE_SESSIONS = [
    ("2023-05-20", [
        {"role": "user", "content": (
            "I've been listening to bird calls online for about "
            "a month now, and it's been helping. By the way, my "
            "new binoculars has made a huge difference.")},
        {"role": "user", "content": (
            "I got them exactly three weeks ago. The waiting "
            "list for the binoculars was long.")},
    ]),
    ("2023-05-20", [
        {"role": "user", "content": (
            "I went for a walk a week ago and noticed the "
            "American goldfinches returning to the area.")},
    ]),
]

# ── fixture: units head, passive participle (must stay counting) ──
PASSIVE_Q = ("How many weeks have I been accepted into the "
             "exchange program when I started attending the "
             "pre-departure orientation?")

# ── fixture: single state candidate (anchor stability guard) ──────
SOLO_SESSIONS = [
    ("2023-05-28", [
        {"role": "user", "content": (
            "I joined Book Lovers Unite three weeks ago. Excited "
            "to finally be a member!")},
        {"role": "user", "content": (
            "The first meetup happened last week and it was "
            "wonderful.")},
    ]),
]
SOLO_Q = ("How long had I been a member of Book Lovers Unite "
          "when the first meetup happened?")


class TestSameSentenceStateBinding(unittest.TestCase):
    def test_same_sentence_acquisition_beats_cross_tenure(self):
        # state tie (s_ov=1 both): the same-sentence acquisition
        # ("binoculars ... three weeks ago" one sentence) must beat
        # the cross-sentence tenure ("a month now" in a sentence
        # without the keyword) -> 05-13 - 04-29 = 14 d = 2 weeks.
        ans, detail = answer_pp_duration(BINO_Q, BINO_SESSIONS)
        self.assertEqual(ans, "2 weeks", detail)
        self.assertEqual(detail.get("route"), "ago_arith")

    def test_ties_without_binding_keep_first(self):
        # both candidates cross-sentence (ss=0): first-maximal is
        # preserved — the month tenure line still wins -> 23 d.
        ans, _ = answer_pp_duration(BINO_Q, TIE_SESSIONS)
        self.assertEqual(ans, "3 weeks")

    def test_single_candidate_stable(self):
        # unique state candidate: reorder-safe pick unchanged.
        ans, _ = answer_pp_duration(SOLO_Q, SOLO_SESSIONS)
        self.assertEqual(ans, "2 weeks")


class TestUnitsProgressiveHead(unittest.TestCase):
    def test_units_progressive_when_routed(self):
        self.assertTrue(pp_duration_form(SCULPT_Q))

    def test_passive_participle_not_matched(self):
        # "have I been accepted" is perfect-passive, not
        # progressive — the counting gate keeps it (banked CORRECT).
        self.assertFalse(pp_duration_form(PASSIVE_Q))

    def test_spend_form_still_rejected(self):
        self.assertFalse(pp_duration_form(
            "How many days did I spend in Japan?"))

    def test_route_d_session_span_resolves(self):
        ans, detail = answer_pp_duration(SCULPT_Q, SCULPT_SESSIONS)
        self.assertEqual(ans, "3 weeks", detail)
        self.assertEqual(detail.get("route"), "session_span")

    def test_route_d_requires_when_clause(self):
        # no when/before: outside the pp gate's ago_arith/session
        # span routes entirely — falls through (None), as today.
        ans, _ = answer_pp_duration(
            "How many weeks have I been taking sculpting classes?",
            SCULPT_SESSIONS)
        self.assertIsNone(ans)

    def test_route_d_abstains_when_anchor_missing(self):
        # honesty contract: form recognized, evidence absent ->
        # None (the gate falls through; no fabricated span).
        ans, _ = answer_pp_duration(
            SCULPT_Q, [SCULPT_SESSIONS[0]])
        self.assertIsNone(ans)

    def test_route_d_same_session_abstains(self):
        # both facts in one session: no measurable span.
        same_date = [
            ("2023-02-11", SCULPT_SESSIONS[0][1]),
            ("2023-02-11", SCULPT_SESSIONS[1][1]),
        ]
        ans, _ = answer_pp_duration(SCULPT_Q, same_date)
        self.assertIsNone(ans)


class TestJudgeBareNumberGT(unittest.TestCase):
    Q = SCULPT_Q

    def test_bare_number_with_question_unit(self):
        self.assertTrue(pp_duration_judge(self.Q, "3", "3 weeks"))
        self.assertTrue(pp_duration_judge(self.Q, "3", "three weeks"))

    def test_bare_number_unit_mismatch_rejected(self):
        self.assertFalse(pp_duration_judge(self.Q, "3", "3 months"))
        self.assertFalse(pp_duration_judge(self.Q, "3", "3 days"))

    def test_word_number_gt_still_folded(self):
        self.assertTrue(pp_duration_judge(
            "How long did I use my new binoculars before I saw "
            "the goldfinches?", "Two weeks", "2 weeks"))

    def test_non_number_gt_untouched(self):
        self.assertFalse(pp_duration_judge(self.Q, "unknown", "3 weeks"))


if __name__ == "__main__":
    unittest.main()
