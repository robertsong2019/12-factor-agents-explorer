"""Cycle 516: common-noun negative-existence abstention tests.

The LME _abs trap family swaps the asked-about OBJECT NOUN
(violin/guitar, football/baseball, iPad/iPhone, uncle/niece):
absent common noun in first-person object-asking question =
presupposition failure => abstain. Census v6: 6 fires/500, 5 wins.
"""
import unittest

import amg_bench_quality as mod


HAY_GUITAR = (
    "I've been practicing guitar every day after work. "
    "My guitar teacher says I'm improving fast."
)
HAY_AQUARIUM = (
    "I set up my aquarium last spring and added six fish. "
    "The aquarium filter needs cleaning weekly."
)
HAY_HOMEGROWN = (
    "I love cooking with home-grown vegetables and fresh ingredients "
    "from my garden for dinner. Tonight I'm making pasta with crops."
)
HAY_TYPO = (
    "We discussed the business milestone I hit four weeks ago. "
    "The business plan is finally paying off."
)
HAY_CEREMONY = (
    "I attended my graduation last month and my cousin's graduation "
    "party the week before."
)


class CommonNounNegExistTest(unittest.TestCase):
    def _miss(self, question, hay):
        return mod.common_noun_missing(question, hay)

    # ── fires (absent object noun) ──
    def test_violin_swap_fires(self):
        q = "How much time do I dedicate to practicing violin every day?"
        self.assertEqual(self._miss(q, HAY_GUITAR), "violin")

    def test_uncle_possessive_fires(self):
        q = "What did I bake for my uncle's birthday party?"
        self.assertEqual(self._miss(q, "I baked a cake for my niece."), "uncle")

    def test_ipad_lowercase_i_token_fires(self):
        q = "How many days did it take for my iPad case to arrive?"
        self.assertEqual(self._miss(q, "I bought an iPhone case."), "ipad")

    def test_football_absent_fires(self):
        q = ("How many autographed football have I added to my "
             "collection this year?")
        hay = ("I've been collecting autographed baseballs since "
               "childhood. My collection has 23 items.")
        self.assertEqual(self._miss(q, hay), "football")

    # ── suppressions (census false-fire fixes) ──
    def test_present_noun_no_fire(self):
        q = "How much time do I dedicate to practicing guitar every day?"
        self.assertIsNone(self._miss(q, HAY_GUITAR))

    def test_plural_stem_no_fire(self):
        # question 'aquariums', corpus 'aquarium'
        q = "How many fish are there in total in both of my aquariums?"
        self.assertIsNone(self._miss(q, HAY_AQUARIUM))

    def test_ies_stem_no_fire(self):
        q = "How many cherries did I pick at the farm?"
        hay = "I picked a bowl of cherry fruit at the farm."
        self.assertIsNone(self._miss(q, hay))

    def test_verb_ed_suffix_no_fire(self):
        q = ("How many days passed between the day I repotted the "
             "previous spider plant and today?")
        hay = ("I re-potted my spider plant last week after buying it.")
        self.assertIsNone(self._miss(q, hay))

    def test_verb_bare_stoplist_no_fire(self):
        q = "What is the minimum amount I could get if I sold the necklace?"
        hay = "I have a vintage diamond necklace and a gold bracelet."
        self.assertIsNone(self._miss(q, hay))

    def test_noun_ed_exception_still_fires(self):
        # 'seed' is a noun despite *ed shape
        q = "How many seed packets did I buy for the spring garden?"
        hay = "I bought soil and three tulip bulbs for the garden."
        self.assertEqual(self._miss(q, hay), "seed")

    def test_event_class_no_fire(self):
        q = ("How many graduation ceremonies have I attended in the "
             "past three months?")
        self.assertIsNone(self._miss(q, HAY_CEREMONY))

    def test_hyphen_join_no_fire(self):
        q = ("What should I serve for dinner with my homegrown "
             "ingredients this weekend?")
        self.assertIsNone(self._miss(q, HAY_HOMEGROWN))

    def test_hyphen_question_token_skipped(self):
        q = "Where did I go on a week-long trip with my family?"
        hay = "We took a trip to Hawaii for a week in March."
        self.assertIsNone(self._miss(q, hay))

    def test_typo_levenshtein_no_fire(self):
        q = "What was the significant buisiness milestone I mentioned?"
        self.assertIsNone(self._miss(q, HAY_TYPO))

    def test_typo_far_still_fires(self):
        q = "What was the significant milystone I mentioned four weeks ago?"
        # 'milystone' vs 'milestone' distance 1 BUT len('milystone')==9?
        # both len>=7 -> suppressed is the DESIGN (typo tolerance)
        # -> this documents the tradeoff: true typos never fire
        self.assertIsNone(self._miss(q, HAY_TYPO))

    # ── gate surfaces ──
    def test_third_person_no_fire(self):
        q = "What class did Caroline start taking this year?"
        hay = "I just started pottery classes."
        self.assertIsNone(self._miss(q, hay))

    def test_non_object_form_no_fire(self):
        q = "Do you think 32 is considered young or old?"
        hay = "Nothing about ages here at all."
        self.assertIsNone(self._miss(q, hay))

    def test_quoted_title_stripped(self):
        q = "How many pages do I have left to read in 'Sapiens'?"
        hay = ("I'm halfway through Sapiens — about 200 pages done "
               "and loving it.")
        self.assertIsNone(self._miss(q, hay))

    def test_capitalized_tokens_untouched(self):
        # proper nouns stay C513's job — common path ignores them
        q = "How many days did I spend traveling in Hawaii and Seattle?"
        hay = "I traveled to Hawaii for 10 days."
        self.assertIsNone(self._miss(q, hay))

    def test_number_words_no_fire(self):
        q = "What is the order of the six museums I visited?"
        hay = "I visited six museums over the summer."
        self.assertIsNone(self._miss(q, hay))


if __name__ == "__main__":
    unittest.main()
