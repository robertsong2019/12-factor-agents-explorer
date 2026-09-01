"""Cycle 475 — speaker-recall distinctive mode (Research #074 v5).

Double-regime reversal: in dialogue recall, word overlap is a NEGATIVE
discriminator for prefaces (the preface directly answers the question,
so it necessarily overlaps). The v5 mechanism validates on ssa-56:
exact 15→16 zero-regression, judge-corrected 15→18.

Distinctive mode scores assistant sentences with squared distinctive
weights ``w(kw)^2``, ``w = 1 + log(N/df)``:
  * raw floor 3 (below the legacy 5 — the v3 zero-flip lesson:
    parasitism is FLOOR-level; answer sentences with distinctive-but-
    few hits never clear raw>=5)
  * necessary condition: >=1 matched keyword with df <= 8
  * preface x0.25 penalty (rank-level multipliers lose, v2 -3)
  * '?' sentences skipped, weighted floor 10.0
"""
import unittest

from amg_bench_quality import (
    LongMemEvalAdapter, answer_speaker_recall, _RECALL_PREAMBLE_RE,
    _SPEECH_ACT_Q_RE, _speech_act_bearer)


def _node(label, role="assistant", session="s1"):
    return {"label": label, "role": role, "session_id": session}


FILLER = [
    "The lake was calm that morning.",
    "We walked around the lake after breakfast.",
    "Her house sits near the lake.",
] * 8  # df(lake) = 24 -> generic

# Question kws: paddle, board, brand, lake ("which/did/you/for/the"
# are stopwords).
Q_BOARD = ("Which paddle board brand did you suggest for the lake?")


class TestDistinctiveMode(unittest.TestCase):
    """Distinctive w^2 scoring vs legacy raw counting."""

    def _nodes(self):
        nodes = {
            "p": _node("Sure, here are the paddle board options I "
                       "mentioned for the lake.", session="s1"),
            "a": _node("The Bluefin Cruise 12' paddle board is the "
                       "brand I would pick for beginners.",
                       session="s2"),
        }
        nodes.update({f"f{i}": _node(t, session="s1")
                      for i, t in enumerate(FILLER)})
        return nodes

    def test_distinctive_beats_preamble(self):
        """Preamble wins raw counting yet loses w^2 scoring.

        The preamble overlaps paddle+board+lake (parasitism); the
        answer carries paddle+board+brand — the same raw count, but
        every hit distinctive (df=2/2/1 vs lake df=25) and no preface
        penalty. Exactly the double regime from Research #074.
        """
        ans, detail = answer_speaker_recall(Q_BOARD, self._nodes())
        self.assertIsNotNone(ans)
        self.assertIn("Bluefin", ans)
        self.assertEqual(detail["mode"], "distinctive")
        self.assertEqual(detail["session_id"], "s2")

    def test_raw_mode_returns_legacy_preamble(self):
        """mode='raw' preserves the Cycle 468 counting behavior."""
        ans, detail = answer_speaker_recall(Q_BOARD, self._nodes(),
                                            min_score=3, mode="raw")
        self.assertIsNotNone(ans)
        self.assertTrue(ans.startswith("Sure"))
        self.assertEqual(detail["mode"], "raw")

    def test_preamble_penalty_prefers_plain_twin(self):
        """Identical hit profiles: the preface twin loses 4x."""
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "p": _node("Sure, here are the cork yoga mat options.",
                       session="s1"),
            "a": _node("The Gaiam cork yoga mat at 5mm is my top pick.",
                       session="s2"),
        }
        # pad the pool so w = 1+log(40/2) clears the weighted floor
        nodes.update({f"f{i}": _node(
            f"We talked about wallpaper colors on day {i}.",
            session="s3") for i in range(38)})
        ans, _ = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("Gaiam", ans)

    def test_question_sentences_skipped(self):
        """A '?' sentence never becomes the answer."""
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "a": _node("Would the Gaiam cork yoga mat suit your "
                       "practice?", session="s1"),
        }
        ans, detail = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)
        self.assertEqual(detail["questions_skipped"], 1)

    def test_no_distinctive_hit_unresolved(self):
        """All matched keywords generic (df > 8): not an answer row."""
        q = "What lake canoe paddle gear did you mention?"
        nodes = {f"n{i}": _node(
            f"Trip {i}: we took the lake canoe paddle gear route "
            f"again.", session="s1") for i in range(30)}
        from amg_bench_quality import _keyword_hits
        for kw in ("lake", "canoe", "paddle", "gear"):
            self.assertGreater(
                sum(1 for n in nodes.values()
                    if _keyword_hits(n["label"], [kw])), 8)
        ans, detail = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)
        self.assertEqual(detail.get("best_score"), 0)

    def test_raw_floor_three(self):
        """Two distinctive hits never clear the raw floor."""
        nodes = {
            "a": _node("The Bluefin Cruise 12' paddle board.",
                       session="s1"),
        }
        ans, _ = answer_speaker_recall(Q_BOARD, nodes)
        self.assertIsNone(ans)

    def test_weighted_floor(self):
        """Distinctive-but-shallow weights stay under the floor.

        8 sentences each containing all three kws: df=8 (distinctive
        boundary), N=8 -> w = 1+log(1) = 1.0 per kw, score = 3 < 10.
        """
        q = "What lake canoe paddle did you mention?"
        nodes = {f"n{i}": _node(
            f"We took the lake canoe paddle out on trip {i}.",
            session="s1") for i in range(8)}
        ans, _ = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)

    def test_empty_pool(self):
        ans, detail = answer_speaker_recall(
            "Which paddle board?", {"u1": _node("hi", role="user")})
        self.assertIsNone(ans)

    def test_detail_reports_df(self):
        q = "What cork yoga mat did you recommend?"
        nodes = {
            "a": _node("The Gaiam cork yoga mat at 5mm is my top pick.",
                       session="s1"),
        }
        _, detail = answer_speaker_recall(q, nodes)
        self.assertEqual(detail["df"]["cork"], 1)


class TestPrefaceRegex(unittest.TestCase):
    """Research #074 forensics: three preamble variants slipped v5."""

    def test_variants_match(self):
        for s in ("Here's a quick summary of my thoughts.",
                  "Thank you for providing the details.",
                  "I hope these help you decide!",
                  "Sure, here are the options.",
                  "Hope that helps!",
                  "Absolutely, here is the plan."):
            self.assertIsNotNone(_RECALL_PREAMBLE_RE.match(s), msg=s)

    def test_answers_do_not_match(self):
        for s in ("The Gaiam cork yoga mat at 5mm is my top pick.",
                  "Hereford cattle graze the north field.",
                  "I suggest the 3-day Kyoto itinerary."):
            self.assertIsNone(_RECALL_PREAMBLE_RE.match(s), msg=s)


class TestAdapterWiring(unittest.TestCase):
    """recall_mode config flows through the adapter call site."""

    QUESTION = ("Can you remind me of the paddle board brand you "
                "suggested for the lake?")

    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user",
                 "content": "Any paddle board advice?"},
                {"role": "assistant",
                 "content": "Sure, here are the paddle board options I "
                            "mentioned for the lake."},
            ] + [{"role": "assistant",
                  "content": t} for t in FILLER],
        }, {
            "session_id": "s2",
            "messages": [
                {"role": "user", "content": "Follow up on boards?"},
                {"role": "assistant",
                 "content": "The Bluefin Cruise 12' paddle board is "
                            "the brand I would pick for beginners."},
            ]}])
        return a

    def test_default_mode_is_distinctive(self):
        a = self._adapter()
        self.assertEqual(a.recall_mode, "distinctive")
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertEqual(meta["gate"], "speaker_recall")
        self.assertIn("Bluefin", ans)

    def test_raw_mode_config(self):
        a = self._adapter(recall_mode="raw", recall_min_score=3)
        self.assertEqual(a.recall_mode, "raw")
        ans, meta = a.answer_extractive(self.QUESTION)
        self.assertEqual(meta["gate"], "speaker_recall")
        self.assertTrue(ans.startswith("Sure"))



class TestAnswerTypeFace(unittest.TestCase):
    """C534 — answer-type face for fact-type-seeking recall questions.

    A question demanding a fact type ("how much" → currency, "handle"
    → @handle, "what year" → year, "how many" → digit) prefers a
    candidate that BEARS the type: tier preference among
    floor-passers, bounded exemption pass when the distinctive/raw
    floors hid every type-bearing candidate (b759caee handle line,
    7a8d0b71 budget line — both official-run casualties).
    """

    FILLER = [
        "The lake was calm that morning.",
        "We walked around the lake after breakfast.",
    ] * 8

    def _nodes(self, *pairs):
        """pairs of (key, sentence) -> assistant nodes + filler."""
        nodes = {k: _node(s, session="s1") for k, s in pairs}
        nodes.update({f"f{i}": _node(t, session="s1")
                      for i, t in enumerate(self.FILLER)})
        return nodes

    def test_money_tier_prefers_currency_line(self):
        """Type-less top scorer yields to a lower-scoring $-bearer.

        Without the face, the 5-hit line wins; the face restricts the
        winner to type-bearing passers, where only the $2,000 line
        qualifies — the 7a8d0b71 mechanism."""
        q = ("How much of the event budget did you allocate for "
             "influencer outreach?")
        nodes = self._nodes(
            ("a", "The event budget allocated for influencer outreach "
                  "covers venue logistics."),
            ("b", "Influencer outreach: $2,000 from the event budget."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertEqual(det["type_demand"], "money")
        self.assertEqual(det["type_face"], "tier")
        self.assertIn("$2,000", ans)

    def test_handle_exemption_rescues_distinctive_filtered_line(self):
        """@handle line under the raw floor is rescued by exemption.

        The handle header matches only jewellery+designer (raw 2 < 3)
        yet is the only type-bearing candidate — the b759caee
        mechanism."""
        q = ("What is the Instagram handle of the jewellery designer "
             "you mentioned?")
        nodes = self._nodes(
            ("d", "The jewellery designer you mentioned works with "
                  "unusual gemstones."),
            ("h", "Jessica Poole (@jess_poole): Jessica is a UK-based "
                  "jewellery designer."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("@jess_poole", ans)
        self.assertEqual(det["type_demand"], "handle")
        self.assertEqual(det["type_face"], "exemption")

    def test_year_exemption_rescues_year_line(self):
        """Year-bearing line under the raw floor wins a year question."""
        q = "What year did you visit the vineyard for the marathon?"
        nodes = self._nodes(
            ("a", "The vineyard visit was amazing and the marathon "
                  "was unforgettable."),
            ("b", "I visited the vineyard in 2019."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("2019", ans)
        self.assertEqual(det["type_demand"], "year")
        self.assertEqual(det["type_face"], "exemption")

    def test_no_demand_keeps_plain_ranking(self):
        """No fact-type demand -> plain w^2 winner, no face flag."""
        q = "Did the event budget cover influencer outreach?"
        nodes = self._nodes(
            ("a", "The event budget allocated for influencer outreach "
                  "covers venue logistics."),
            ("b", "Influencer outreach: $2,000 from the event budget."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("venue logistics", ans)
        self.assertIsNone(det.get("type_demand"))
        self.assertNotIn("type_face", det)

    def test_digit_junk_never_rescued(self):
        """A digit alone (zero keyword support) is not an answer."""
        q = "How many guests attended the dinner?"
        nodes = self._nodes(
            ("j", "Room 4 is available for the night."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNone(ans)
        self.assertEqual(det["type_demand"], "number")


class TestSpeechActFace(unittest.TestCase):
    """C537 — speech-act face for you-addressed act-reference questions.

    "...the restaurant you recommended" is answered by the sentence
    PERFORMING the act in first person ("I would recommend Roscioli."),
    not by a content-overlapping list row (La Pergola parasite,
    4c36ccef official-run casualty, 150.8 vs 145.5). Tier preference
    among floor-passers; bearers must perform the act ON A CONCRETE
    OBJECT — propositional ("suggest that…"), negated ("you didn't
    mention… I'll provide…") and generic-object ("recommend some
    other bands") sentences are structurally excluded (the C537 A/B
    kills 488d3006/c8f1aeed). Applied BEFORE the C534 type face so a
    type demand still resolves to the type-bearing sentence.
    """

    FILLER = [
        "The lake was calm that morning.",
        "We walked around the lake after breakfast.",
    ] * 8

    def _nodes(self, *pairs):
        nodes = {k: _node(s, session="s1") for k, s in pairs}
        nodes.update({f"f{i}": _node(t, session="s1")
                      for i, t in enumerate(self.FILLER)})
        return nodes

    def test_act_sentence_beats_content_parasite(self):
        """Parasite outranks the act sentence; the face flips to it.

        The 4c36ccef mechanism: the La Pergola line parasitizes
        restaurant/Rome/Italian/romantic/dinner overlap while the
        first-person act sentence carries the answer."""
        q = ("Can you remind me of the name of the romantic Italian "
             "restaurant in Rome you recommended for dinner?")
        nodes = self._nodes(
            ("a", "La Pergola is a fine-dining restaurant above the "
                  "Rome skyline; its romantic terrace serves classic "
                  "Italian dinner courses."),
            ("b", "For a romantic dinner, I would recommend Roscioli."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("Roscioli", ans)
        self.assertEqual(det["speech_act_face"], "tier")

    def test_propositional_clause_not_bearer(self):
        """"I can suggest THAT hiking …" performs no entity act.

        The 488d3006 guard: the plain winner must survive when the
        only act sentence is propositional — no tier, no flip."""
        q = ("What was the name of the hiking trail you suggested "
             "for the Moncayo mountain?")
        nodes = self._nodes(
            ("a", "The GR-90 is the name of the hiking trail with "
                  "the most stunning views in the Moncayo mountain."),
            ("b", "However, I can suggest that hiking is a must-try "
                  "activity in the Moncayo mountain in Aragon."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("GR-90", ans)
        self.assertNotIn("speech_act_face", det)

    def test_negated_and_generic_acts_not_bearers(self):
        """Hedge + off-topic act echoes are not bearers (c8f1aeed).

        "Since you didn't mention … I'll provide some general
        suggestions" (negated act, generic object) and "I can
        recommend some other bands" (generic object, topic
        incoherent) both pass the floors — both must be excluded."""
        q = ("Which state's fracking groundwater rule did you "
             "mention in our Marcellus Shale conversation?")
        nodes = self._nodes(
            ("a", "In our Marcellus Shale conversation I covered "
                  "Pennsylvania: fracking companies there must "
                  "monitor groundwater quality."),
            ("b", "Since you didn't mention which state, I'll provide "
                  "some general suggestions about Marcellus Shale "
                  "fracking rules."),
            ("c", "By the way, since you mentioned the Marcellus "
                  "Shale region, I can recommend some other bands."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("Pennsylvania", ans)
        self.assertNotIn("speech_act_face", det)

    def test_type_demand_overrides_speech_act(self):
        """Composition order: the C534 type face runs after and wins.

        The face first flips to the act sentence (no digit), then the
        number demand exemption-rescues the digit line — a "how many
        did you recommend" question answers with the number."""
        q = ("How many bottles did you recommend for the cocktail "
             "bar?")
        nodes = self._nodes(
            ("p", "The cocktail bar opens this season with the "
                  "recommended brand-new bottle menu."),
            ("act", "For the cocktail bar opening, I would recommend "
                    "the gin trio."),
            ("d", "5 bottles for the bar."),
        )
        ans, det = answer_speaker_recall(q, nodes)
        self.assertIsNotNone(ans)
        self.assertIn("5 bottles", ans)
        self.assertEqual(det["type_demand"], "number")
        self.assertEqual(det["speech_act_face"], "tier")
        self.assertEqual(det["type_face"], "exemption")

    def test_bearer_and_question_detector_units(self):
        """Unit pins for the bearer guards and question detector."""
        # concrete-object acts are bearers
        self.assertTrue(_speech_act_bearer(
            "For a romantic dinner, I would recommend Roscioli."))
        self.assertTrue(_speech_act_bearer(
            "I've suggested the Bluefin board for beginners."))
        self.assertTrue(_speech_act_bearer(
            "I told her the trail name at lunch."))
        # propositional / negated / generic / non-acts are not
        self.assertFalse(_speech_act_bearer(
            "I can suggest that hiking is a must-try activity."))
        self.assertFalse(_speech_act_bearer(
            "Since you didn't mention the city, I'll provide some "
            "general suggestions."))
        self.assertFalse(_speech_act_bearer(
            "I can recommend some other bands."))
        self.assertFalse(_speech_act_bearer(
            "You can visit the official website."))
        self.assertFalse(_speech_act_bearer(
            "Here are some highly recommended spots."))
        # NOTE: preface-prefixed act mentions ("Sure, here are the
        # options I mentioned …") match the bearer regex by design —
        # the call site excludes them (C475 prefaces parasitize
        # you-addressed questions). End-to-end coverage:
        # test_distinctive_beats_preamble + the TestAdapterWiring
        # default-mode fixture.
        # question-side detector: you-addressed act reference fires
        self.assertTrue(_SPEECH_ACT_Q_RE.search(
            "Can you remind me of the restaurant you recommended?"))
        self.assertTrue(_SPEECH_ACT_Q_RE.search(
            "What did you suggest for dinner?"))
        self.assertFalse(_SPEECH_ACT_Q_RE.search(
            "Did the restaurant have a garden?"))
        self.assertFalse(_SPEECH_ACT_Q_RE.search(
            "I recommended it to you."))


if __name__ == "__main__":
    unittest.main()
