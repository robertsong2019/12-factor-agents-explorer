"""Cycle 477: multi-session counting forms — layered integration.

#075 i3 spec: ONLY precision-≥0.5 mechanisms enter the pipeline
(duration_sum / total_sum / number_total / argmax); entity_count
stays prototype-level. Form-triggered like C456/C457/C473; calendar
distance questions are owned by the temporal path, unresolved forms
fall through to the gate chain untouched.
"""

import unittest

from amg_bench_quality import (
    LongMemEvalAdapter, answer_counting, counting_form, counting_judge,
)

SESSIONS = [
    {"session_id": "s1", "turns": [
        {"role": "user",
         "content": ("I finally took that 7-day trip to Japan. The "
                     "ryokan in Kyoto was wonderful.")},
        {"role": "assistant",
         "content": "That sounds like a great trip! How was Kyoto?"}]},
    {"session_id": "s2", "turns": [
        {"role": "user",
         "content": ("Back from Japan. I also visited the Ueno "
                     "zoo from April 10th to 22nd with my niece.")}]},
    {"session_id": "s3", "turns": [
        {"role": "user",
         "content": "I'm thinking of planning a 30-day trek next year."},
        {"role": "user",
         "content": ("I paid $300 at Sakura Air for the plane "
                     "ticket. The stay cost $1,200 at Ryokan "
                     "Ginji.")}]},
]


class TestCountingFormDetector(unittest.TestCase):
    def test_duration_sum_days(self):
        self.assertEqual(
            counting_form("How many days did I spend in Japan?"),
            "duration_sum")

    def test_duration_sum_total_number_of_days(self):
        self.assertEqual(
            counting_form(
                "What is the total number of days I spent hiking?"),
            "duration_sum")

    def test_total_sum_money(self):
        self.assertEqual(
            counting_form(
                "How much money did I spend in total on the trip?"),
            "total_sum")

    def test_number_total(self):
        self.assertEqual(
            counting_form(
                "What is the total number of instruments I own?"),
            "number_total")

    def test_argmax(self):
        self.assertEqual(
            counting_form(
                "Which store did I spend the most money at?"),
            "argmax")

    def test_calendar_distance_is_temporal_not_counting(self):
        # "how many days between X and Y" is C457 territory
        self.assertIsNone(counting_form(
            "How many days passed between my MoMA visit and the "
            "Ancient Civilizations exhibition?"))

    def test_plain_entity_count_now_enum_form(self):
        # C503 (#084): the entity-count wall was four walls —
        # named/role/size enumeration carries built-in dedup
        # keys and IS layered (enum_count, oracle prec 1.00);
        # signature-less counts fall through (honest abstention,
        # covered in test_enum_count.py). C511: kit/instrument/
        # property heads moved up to inventory_count (brand/
        # scale/descriptor identity — test_inventory_count.py).
        self.assertEqual(counting_form(
            "How many model kits do I have?"),
            "inventory_count")


class TestMechanisms(unittest.TestCase):
    def test_duration_sum_days_with_daterange(self):
        ans, detail = answer_counting(
            "How many days did I spend in Japan?", SESSIONS)
        # 7-day trip + April 10→22 (=12) = 19; the 30-day trek is
        # intent (unrealized) and must NOT count; equal durations
        # with signature overlap would dedup — these differ.
        self.assertEqual(ans, "19 days")
        self.assertEqual(detail["form"], "duration_sum")

    def test_duration_sum_weeks_unit(self):
        ans, _ = answer_counting(
            "How many weeks did I spend in Japan?", SESSIONS)
        self.assertEqual(ans, "2.71 weeks")

    def test_duration_sum_equal_values_dedup_across_sessions(self):
        # same duration + signature overlap = same event retold
        sessions = [
            {"session_id": "s1", "turns": [
                {"role": "user",
                 "content": "Our Kyoto trip was 5 days."}]},
            {"session_id": "s2", "turns": [
                {"role": "user",
                 "content": "Back from Kyoto, the 5-day trip was "
                            "perfect."}]}]
        ans, _ = answer_counting(
            "How many days did I spend in Kyoto?", sessions)
        self.assertEqual(ans, "5 days")

    def test_duration_sum_conjunct_missing_abstains(self):
        # "Hawaii and Seattle" — Seattle has no event → fall through
        sessions = [
            {"session_id": "s1", "turns": [
                {"role": "user",
                 "content": "My Hawaii vacation was a 5-day trip."}]}]
        ans, detail = answer_counting(
            "How many days did I spend in Hawaii and Seattle?",
            sessions)
        self.assertIsNone(ans)
        self.assertEqual(detail["form"], "duration_sum")

    def test_duration_sum_intent_excluded(self):
        sessions = [
            {"session_id": "s1", "turns": [
                {"role": "user",
                 "content": "I'm planning a 30-day trek to Patagonia."}]}]
        ans, _ = answer_counting(
            "How many days did I spend trekking?", sessions)
        self.assertIsNone(ans)

    def test_total_sum_money(self):
        ans, detail = answer_counting(
            "How much money did I spend in total on the trip?",
            SESSIONS)
        self.assertEqual(ans, "$1500")
        self.assertEqual(detail["form"], "total_sum")

    def test_number_total_family(self):
        sessions = [
            {"session_id": "s1", "turns": [
                {"role": "user",
                 "content": "I own two guitars."}]},
            {"session_id": "s2", "turns": [
                {"role": "user",
                 "content": "I sold one guitar last month."}]}]
        ans, _ = answer_counting(
            "What is the total number of guitars I have owned?",
            sessions)
        # 2 + 1 = 3 (SUM of distinct evidence counts)
        self.assertEqual(ans, "3")

    def test_number_total_unit_blacklist(self):
        # "3 gallons of paint" is a measurement, not 3 instances
        sessions = [
            {"session_id": "s1", "turns": [
                {"role": "user",
                 "content": "I bought 3 gallons of paint for the "
                            "renovation."}]}]
        ans, _ = answer_counting(
            "What is the total number of paint buckets do I have?",
            sessions)
        self.assertIsNone(ans)

    def test_argmax_money(self):
        ans, _ = answer_counting(
            "Which place did I spend the most money at?", SESSIONS)
        self.assertEqual(ans, "Ryokan Ginji")


class TestCountingJudge(unittest.TestCase):
    def test_numeric_equality_with_unit(self):
        self.assertTrue(counting_judge(
            "How many days did I spend in Japan?", "14",
            "14 days"))

    def test_word_number_vs_digit(self):
        self.assertTrue(counting_judge(
            "How many cats do I have in total?", "three", "3"))

    def test_money_format(self):
        self.assertTrue(counting_judge(
            "How much money did I spend in total?", "1500",
            "$1500"))

    def test_sentence_style_truth_first_number(self):
        self.assertTrue(counting_judge(
            "How many days did I spend in Japan?",
            "I have worked on five model kits", "five days"))

    def test_entity_containment(self):
        self.assertTrue(counting_judge(
            "Which store did I spend the most money at?",
            "the ryokan stay in Kyoto", "Ryokan"))

    def test_wrong_number(self):
        self.assertFalse(counting_judge(
            "How many days did I spend in Japan?", "14", "12 days"))

    def test_none_predicted(self):
        self.assertFalse(counting_judge(
            "How many days did I spend in Japan?", "14", ""))


class TestAdapterCountingPath(unittest.TestCase):
    def _adapter(self, **kw):
        a = LongMemEvalAdapter(**kw)
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                {"role": "user",
                 "content": "I paid $300 for the plane ticket."}]},
            {"session_id": "s2", "messages": [
                {"role": "user",
                 "content": "The ryokan stay cost $1,200."}]}])
        return a

    def test_gate_label_and_answer(self):
        a = self._adapter()
        ans, meta = a.answer_extractive(
            "How much money did I spend in total on the trip?")
        self.assertEqual(ans, "$1500")
        self.assertEqual(meta["gate"], "counting")
        self.assertFalse(meta["abstained"])
        self.assertEqual(meta["counting"]["form"], "total_sum")

    def test_disabled_reproduces_baseline(self):
        a = self._adapter(counting=False)
        ans, meta = a.answer_extractive(
            "How much money did I spend in total on the trip?")
        self.assertNotEqual(meta["gate"], "counting")
        self.assertNotEqual(ans, "$1500")

    def test_unresolved_form_falls_through(self):
        # form matches but no money evidence → normal path
        a = LongMemEvalAdapter()
        a.ingest_sessions([{"session_id": "s1", "messages": [
            {"role": "user", "content": "Just chatting about films."}]}])
        _, meta = a.answer_extractive(
            "How much money did I spend in total?")
        self.assertNotEqual(meta["gate"], "counting")
        self.assertIn(meta["counting"]["form"], ("total_sum",))

    def test_counting_sessions_shape(self):
        a = self._adapter()
        sess = a._counting_sessions()
        self.assertEqual(len(sess), 2)
        self.assertEqual(sess[0]["session_id"], "s1")
        self.assertEqual(
            sess[0]["turns"][0]["content"],
            "I paid $300 for the plane ticket.")

    def test_evaluate_dispatches_counting_judge(self):
        a = self._adapter()
        report = a.evaluate([{
            "id": "q1",
            "question": ("How much money did I spend in total on "
                         "the trip?"),
            "answer": "$1,500",
            "question_date": ""}])
        row = report["results"][0]
        self.assertTrue(row["correct"])
        self.assertEqual(row["predicted_answer"], "$1500")


if __name__ == "__main__":
    unittest.main()


class TestCycle483UnitDiscipline(unittest.TestCase):
    """C483: unit discipline + title guard + freq days + species sum."""

    def test_hours_question_not_money(self):
        # hours/years/months route to unit_sum, never total_sum ($)
        self.assertEqual(
            counting_form("How many hours have I spent playing "
                          "games in total?"), "unit_sum")
        self.assertEqual(
            counting_form("How many years in total did I spend "
                          "in school?"), "unit_sum")
        self.assertEqual(
            counting_form("How much money did I spend in total "
                          "on food?"), "total_sum")
        # count-noun "in total" → number_total
        self.assertEqual(
            counting_form("How many fish are there in total in "
                          "both aquariums?"), "number_total")

    def test_freq_days_form(self):
        self.assertEqual(
            counting_form("How many days a week do I attend "
                          "fitness classes?"), "freq_days")

    def test_unit_sum_dedup_and_question_clause(self):
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I spent around 70 hours playing Assassin's "
                    "Creed Odyssey.")},
                {"role": "assistant", "content": "Nice!"}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I beat The Last of Us Part II, which took me "
                    "30 hours to finish.")},
                {"role": "user", "content": (
                    "The Last of Us Part II took me 30 hours on "
                    "hard.")},   # duplicate → counts once
                {"role": "user", "content": (
                    "Can you recommend games similar to Celeste, "
                    "which took me 10 hours to complete?")}]}]
        ans, _ = answer_counting(
            "How many hours have I spent playing games in total?",
            sess)
        self.assertEqual(ans, "110")   # 70 + 30 + 10

    def test_unit_sum_strips_money_and_ranges(self):
        sess = [{"session_id": "s1", "turns": [
            {"role": "user", "content": (
                "The $40 game took me 12 hours, plus a 2-3 hour "
                "demo and 5 hours of extras.")}]}]
        ans, _ = answer_counting(
            "How many hours did I spend gaming in total?", sess)
        self.assertEqual(ans, "17")   # 12 + 5; range dropped

    def test_total_sum_money_gate(self):
        sess = [{"session_id": "s1", "turns": [
            {"role": "user", "content": (
                "I have 10 neon tetras, 5 gouramis, and a pleco "
                "catfish.")}]}]
        # hours/fish questions never sum $ even if money nearby
        ans, _ = answer_counting(
            "How many fish are there in total in both tanks?", sess)
        self.assertEqual(ans, "16")

    def test_duration_title_guard(self):
        sess = [{"session_id": "s1", "turns": [
            {"role": "user", "content": (
                'I think "Matthew: A 12-Week Study" by Jen Wilkin '
                "would fit my faith group.")},
            {"role": "user", "content": (
                "I did a 3-day faith retreat last month.")}]}]
        ans, _ = answer_counting(
            "How many days did I spend on faith activities in "
            "total?", sess)
        self.assertEqual(ans, "3 days")

    def test_freq_days_distinct_weekdays(self):
        sess = [{"session_id": "s1", "turns": [
            {"role": "user", "content": (
                "I attend Zumba classes on Tuesdays and Thursdays "
                "at 6:30 pm.")},
            {"role": "user", "content": (
                "I started a yoga class on Wednesdays, and "
                "weightlifting on Saturdays.")}]}]
        ans, _ = answer_counting(
            "How many days a week do I attend fitness classes?",
            sess)
        self.assertEqual(ans, "4")

    def test_species_sum_singular_and_adjacent(self):
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "My 20-gallon tank currently has 10 neon "
                    "tetras, 5 golden honey gouramis, and a small "
                    "pleco catfish.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I have one betta in my old tank.")}]}]
        ans, _ = answer_counting(
            "How many fish are there in total in both of my "
            "aquariums?", sess)
        self.assertEqual(ans, "17")   # 10+5+1 + 1


class TestCycle490UnitAnchorHygiene(unittest.TestCase):
    """C490 (#079 F1+F2): the question's own unit word must not
    qualify as a topical anchor — 'days' is topic-uniform and
    admits legal/congressional noise sessions through the gate."""

    def test_unit_word_admits_no_noise_sessions(self):
        # #079 social-media scenario: real events 10+7=17; legal
        # session mentions '28 days'/'14 days' — pre-C490 every
        # sentence containing 'days' passed the anchor gate.
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I took a 10-day break from social media in "
                    "mid-February.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I also had a week-long break from social "
                    "media back in mid-January.")}]},
            {"session_id": "s3", "turns": [
                {"role": "user", "content": (
                    "My lawyer says I must lodge the Notice of "
                    "Appeal form within 28 days. The timeframe "
                    "is 14 days instead of 28 days for small "
                    "claims.")}]}]
        ans, _ = answer_counting(
            "How many days did I take social media breaks in "
            "total?", sess)
        self.assertEqual(ans, "17 days")   # not 59

    def test_unit_anchor_stripped_before_gate(self):
        from amg_bench_quality import _cnt_question_anchors
        from amg_bench_quality import _CNT_UNIT_ANCHOR_STOP
        raw = _cnt_question_anchors(
            "How many days did I take social media breaks in "
            "total?")
        self.assertIn("days", raw)          # raw anchors carry it
        stripped = {a for a in raw
                    if a.rstrip("s") not in _CNT_UNIT_ANCHOR_STOP}
        self.assertNotIn("days", stripped)  # gate never sees it
        self.assertIn("social", stripped)   # topical anchors stay

    def test_real_anchor_still_gates_duration_events(self):
        # hygiene must not over-prune: 'japan' anchors the events
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I finally took that 7-day trip to Japan.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "The contractor said the job takes 30 days "
                    "of work.")}]}]
        ans, _ = answer_counting(
            "How many days did I spend in Japan?", sess)
        self.assertEqual(ans, "7 days")      # 30-day noise out

    def test_generic_geo_head_cannot_propagate_anchor_ok(self):
        # F2 hardening: 'city' from 'New York City' must not mark
        # a session anchor_ok and admit its unrelated durations
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I spent 5 days in New York City last "
                    "spring.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "The city council meeting ran 21 days of "
                    "hearings this year.")}]}]
        ans, _ = answer_counting(
            "How many days did I spend in New York City?", sess)
        self.assertEqual(ans, "5 days")      # not 26


class TestCycle491MoneyAnchorDiscipline(unittest.TestCase):
    """C491 (#079 residual bucket 1): total_sum anchor transplant.

    The old gateless sum admitted every $ in the haystack — income
    statements, visa-fee legal text, watch purchases. Anchors now
    gate sentences (session-propagated), money-unit words carry
    no topical signal, price ranges are budgets not spends."""

    def test_income_and_fares_excluded(self):
        # $56355 vs GT $5850 was a $50k income line + rail fares
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I recently participated in a charity walk "
                    "and managed to raise $250 through "
                    "sponsors.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "They are likely to have a stable income of "
                    "over $50,000 per year and at least some "
                    "disposable income.")}]},
            {"session_id": "s3", "turns": [
                {"role": "user", "content": (
                    "A single train ticket costs $5, and I "
                    "usually buy a monthly pass for $100.")}]}]
        ans, _ = answer_counting(
            "How much money did I raise in total through all "
            "the charity events I participated in?", sess)
        self.assertEqual(ans, "$250")       # not $50355

    def test_legal_fee_text_excluded(self):
        # $8940 vs GT $720 included L-visa statutory fee text
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "It was a two-day workshop, and I paid $200 "
                    "to attend.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "NOTE: A petitioner that seeks initial "
                    "approval must submit an additional fee of "
                    "$4,500. This $4,500 fee is mandated by "
                    "Public Law 114-113.")}]}]
        ans, _ = answer_counting(
            "How much total money did I spend on attending "
            "workshops in the last four months?", sess)
        self.assertEqual(ans, "$200")        # not $4700

    def test_session_propagation_admits_anchorless_sibling(self):
        # the $25 chain sentence has no 'bike' — its sibling does
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "The mechanic told me to replace the chain, "
                    "which cost me $25.")},
                {"role": "user", "content": (
                    "I also got a new set of bike lights "
                    "installed, which were $40.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I saw a business class ticket for $3,300, "
                    "but I'm hoping to find something cheaper.")
                }]}]
        ans, _ = answer_counting(
            "How much total money have I spent on bike-related "
            "expenses since the start of the year?", sess)
        self.assertEqual(ans, "$65")         # 25+40, not 3365

    def test_intent_sentence_cannot_light_session(self):
        # planning mention must not propagate to real amounts
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I'm planning to buy a racing bike next "
                    "year.")},
                {"role": "user", "content": (
                    "The hotel in Tokyo cost me around $2,000 "
                    "for the week.")}]}]
        ans, _ = answer_counting(
            "How much total money have I spent on bike-related "
            "expenses since the start of the year?", sess)
        self.assertIsNone(ans)                # no anchored amounts

    def test_price_range_pair_skipped(self):
        # "$50 to $200" is a budget range, not two spends
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "Speaking of my bike, I've been spending "
                    "around $50 to $200 on gear each season, "
                    "but last month's repair was $30.")}]}]
        ans, _ = answer_counting(
            "How much total money have I spent on bike-related "
            "expenses since the start of the year?", sess)
        self.assertEqual(ans, "$30")         # not $280

    def test_hyphen_and_plural_anchor_forms(self):
        # 'bike-related' anchors 'bike'; 'workshops' anchors
        # singular 'workshop' mentions
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "The workshop fee was $500 and well worth "
                    "it.")}]}]
        ans, _ = answer_counting(
            "How much total money did I spend on attending "
            "workshops?", sess)
        self.assertEqual(ans, "$500")


class TestCycle497WindowEntityPairDedup(unittest.TestCase):
    """C497b: (n, entity)-pair dedup with ±1-sentence window.

    The old whole-sentence signature split one statement into
    (4, ∅) vs (4, {outer, banks}) when the proper noun sat in a
    NEIGHBOURING sentence (pronoun cataphora) and double-counted
    it (driving aae3761f: 19 vs GT 15). Any shared (n, entity)
    pair now deduplicates; nounless repeats keep the legacy key.
    """

    def test_cataphora_neighbor_noun_dedups(self):
        # "my recent trip to Outer Banks … it only took me four
        # hours" + "My last trip to Outer Banks only took about
        # four hours" — one trip, two sentences, noun one hop away
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "I've had some great experiences with coastal "
                    "trips, like my recent trip to Outer Banks in "
                    "North Carolina - it only took me four hours to "
                    "drive there from my place.")},
                {"role": "user", "content": (
                    "My last trip to Outer Banks only took about "
                    "four hours, so I can handle the drive.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I drove for five hours to get to the mountains "
                    "in Tennessee on my camping trip.")}]},
        ]
        ans, _ = answer_counting(
            "How many hours in total did I spend driving?", sess)
        self.assertEqual(ans, "9")  # 4 (deduped) + 5

    def test_same_sentence_dedup_still_works(self):
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "It took me 30 hours to finish The Last of Us "
                    "Part 2.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "I mentioned before that The Last of Us Part 2 "
                    "took me about 30 hours.")}]},
        ]
        ans, _ = answer_counting(
            "How many hours in total did I spend gaming?", sess)
        self.assertEqual(ans, "30")

    def test_same_number_different_entities_both_count(self):
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "The drive to Asheville took four hours.")}]},
            {"session_id": "s2", "turns": [
                {"role": "user", "content": (
                    "The drive to Savannah also took four hours.")}]},
        ]
        ans, _ = answer_counting(
            "How many hours in total did I spend driving?", sess)
        self.assertEqual(ans, "8")

    def test_nounless_repeat_legacy_key(self):
        sess = [
            {"session_id": "s1", "turns": [
                {"role": "user", "content": (
                    "It took four hours.")},
                {"role": "user", "content": (
                    "Yeah, it took four hours total.")}]},
        ]
        ans, _ = answer_counting(
            "How many hours in total did it take?", sess)
        self.assertEqual(ans, "4")
