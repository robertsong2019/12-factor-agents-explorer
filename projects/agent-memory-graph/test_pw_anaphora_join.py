"""Cycle 496: anaphora purchase-report join (pairwise F6).

6ed717ea forensics (first-family 30q, C495 residual): B-side
evidence is a three-sentence chain — "I'm thinking of getting
some more supplies for my puppy, Luna. She's still in
potty-training, and I've been using those eco-friendly training
pads from Chewy.com. I got a set of 10 for $25 about a month
ago". The kw sentence has no eventive surface; the event sentence
has no kws — F1 cross-line joins need kw on both sides, so the
anchor never establishes (B-unanchored fallthrough → wrong).

F6 joins the kw-less purchase-report sentence when its object is
a BARE QUANTIFIED NP with numeric of-complement + a price — the
anaphor resumes the pair item. Named regression tests mirror the
production line and the poison shapes that must stay out.
"""
import unittest

from datetime import datetime, timedelta

from amg_bench_quality import (
    _pw_kws, _pw_lines, _pw_scan_anchor, _PW_ANAPHOR_EV_RE,
    answer_pairwise)


def turn(role, content):
    return {"role": role, "content": content}


def dated(msgs, stamp="2023/05/29 (Mon) 19:41"):
    return [(stamp, msgs)]


class TestAnaphorSignature(unittest.TestCase):
    """_PW_ANAPHOR_EV_RE: eventive + bare quantified object
    (numeric of-complement) + price."""

    def test_production_line(self):
        self.assertTrue(_PW_ANAPHOR_EV_RE.search(
            "com I got a set of 10 for $25 about a month ago, "
            "and they've been a lifesaver"))

    def test_bought_pack(self):
        self.assertTrue(_PW_ANAPHOR_EV_RE.search(
            "I bought a box of 12 for $18 last week"))

    def test_new_noun_object_stays_out(self):
        # 'a pack of dental chews' names a NEW item — the
        # of-complement must be numeric only
        self.assertFalse(_PW_ANAPHOR_EV_RE.search(
            "I got a pack of dental chews for $15"))

    def test_no_price_stays_out(self):
        self.assertFalse(_PW_ANAPHOR_EV_RE.search(
            "I got a set of 10 about a month ago"))

    def test_pronoun_object_stays_out(self):
        # c27434e8 discipline: bare pronoun anaphora never pulls
        self.assertFalse(_PW_ANAPHOR_EV_RE.search(
            "started it for $0 about three weeks ago"))


class TestF6ScanAnchor(unittest.TestCase):
    """6ed717ea production shape: kw pair (Luna + pads) with a
    URL-debris fragment ('com') before the purchase-report line.
    qverbs from 'purchase'."""

    QV = ('bought', 'purchas', 'order', 'got')
    KWS = _pw_kws("the training pads for Luna")

    MSGS = [
        turn("user",
             "I'm thinking of getting some more supplies for my "
             "puppy, Luna. She's still in potty-training, and "
             "I've been using those eco-friendly training pads "
             "from Chewy.com. I got a set of 10 for $25 about a "
             "month ago, and they've been a lifesaver."),
        turn("assistant", "Congratulations on the eco-friendly "
                          "route with Luna's potty training!"),
    ]

    def test_anchor_pulled_one_month(self):
        lines = _pw_lines(dated(self.MSGS))
        got = _pw_scan_anchor(self.KWS, lines, None, self.QV)
        self.assertIsNotNone(got)
        self.assertEqual(got[0],
                         datetime(2023, 5, 29, 19, 41)
                         - timedelta(days=30))

    def test_no_fire_without_kw_pair(self):
        # same event sentence, but no Luna/pads lines before it
        msgs = [turn("user",
                     "I'm thinking of getting some more supplies "
                     "for my cat. I got a set of 10 for $25 about "
                     "a month ago.")]
        lines = _pw_lines(dated(msgs))
        self.assertIsNone(_pw_scan_anchor(self.KWS, lines, None,
                                          self.QV))

    def test_no_fire_when_event_line_has_kws(self):
        # kw-bearing purchase lines belong to the in-line branch
        # (F6 requires a kw-LESS event line); the in-line path
        # anchors at the session clock here — the duration
        # clause carries no kw (comma-split from 'training pads')
        msgs = [turn("user",
                     "my puppy Luna loves them. I got the "
                     "training pads, a set of 10, for $25 about a "
                     "month ago.")]
        lines = _pw_lines(dated(msgs))
        got = _pw_scan_anchor(self.KWS, lines, None, self.QV)
        self.assertIsNotNone(got)  # anchored by the in-line path
        self.assertEqual(got[0], datetime(2023, 5, 29, 19, 41))

    def test_no_fire_on_qverb_mismatch(self):
        # signature verb present ('got') but the question's verb
        # class is start — no congruence, no pull
        msgs = [turn("user",
                     "my puppy Luna. those training pads from "
                     "Chewy. I got a set of 10 for $25 about a "
                     "month ago.")]
        lines = _pw_lines(dated(msgs))
        self.assertIsNone(_pw_scan_anchor(
            self.KWS, lines, None, ('start', 'began')))

    def test_no_fire_on_planning_event_line(self):
        msgs = [turn("user",
                     "my puppy Luna. those training pads. I'm "
                     "planning to get a set of 10 for $25 next "
                     "month.")]
        lines = _pw_lines(dated(msgs))
        self.assertIsNone(_pw_scan_anchor(self.KWS, lines, None,
                                          self.QV))


class TestF6EndToEnd(unittest.TestCase):
    """Full pairwise decision on the 6ed717ea shape — B pulls to
    −1 month, A stays at −3 weeks in-clause, B wins."""

    def setUp(self):
        self.dated = [
            ("2023/05/29 (Mon) 21:15", [
                turn("user",
                     "I'm looking for some advice on dog "
                     "arthritis. I recently got a new Orthopedic "
                     "Memory Foam dog bed for my golden retriever, "
                     "Max, about three weeks ago from Petco, and "
                     "it seems to be helping"),
                turn("assistant", "glad to hear"),
            ]),
            ("2023/05/29 (Mon) 19:41", [
                turn("user",
                     "I'm thinking of getting some more supplies "
                     "for my puppy, Luna. She's still in "
                     "potty-training, and I've been using those "
                     "eco-friendly training pads from Chewy.com. "
                     "I got a set of 10 for $25 about a month "
                     "ago, and they've been a lifesaver."),
                turn("assistant", "Congratulations!"),
            ]),
        ]

    def test_training_pads_first(self):
        ans, det = answer_pairwise(
            "Which item did I purchase first, the dog bed for "
            "Max or the training pads for Luna?",
            self.dated, "")
        self.assertEqual(ans, "the training pads for Luna")
        self.assertEqual(det["mode"], "both")


if __name__ == '__main__':
    unittest.main()
