"""Cycle 515: age_diff — self-age-anchored year arithmetic (12th
counting form). Census 3 fires (ms133+full500 identical), oracle
3/3, zero hijack. Ambiguity discipline: every anchor must be
unique-valued or the form falls through untouched.
"""

import unittest

from amg_bench_quality import (
    counting_form, _cnt_age_diff, _age_form_gate,
)


def sess(*turn_lists):
    """turn_lists: one list of user-turn strings per session."""
    return [{"session_id": f"s{i}", "turns": [
        {"role": "user", "content": t} for t in ts]}
        for i, ts in enumerate(turn_lists)]


class TestAgeDiffGate(unittest.TestCase):
    def test_other_form(self):
        self.assertEqual(
            counting_form("How many years older is my grandma than me?"),
            "age_diff")

    def test_then_form(self):
        self.assertEqual(
            counting_form(
                "How many years older am I than when I graduated "
                "from college?"),
            "age_diff")

    def test_until_form(self):
        self.assertEqual(
            counting_form(
                "How many years will I be when my friend Rachel "
                "gets married?"),
            "age_diff")

    def test_twin_how_old_rachel_not_claimed(self):
        # abs twin: starts "How old will Rachel…" — not our gate
        self.assertIsNone(counting_form(
            "How old will Rachel be when I get married?"))

    def test_unit_sum_total_not_stolen(self):
        # unit_sum owns how-many-years-total; age gate must not
        self.assertEqual(
            counting_form(
                "How many years in total did I spend in formal "
                "education?"),
            "unit_sum")

    def test_plain_years_question_not_claimed(self):
        self.assertIsNone(counting_form(
            "How many years did I work at TechSavvy Inc.?"))


class TestAgeDiffMechanism(unittest.TestCase):
    def test_other_ordinal_birthday(self):
        sessions = sess(
            ["My grandma's 75th birthday celebration was great.",
             "I'm 32, so I'm in my 30s."])
        self.assertEqual(
            _cnt_age_diff("How many years older is my grandma than me?",
                          sessions), "43")

    def test_other_years_old_grammar(self):
        sessions = sess(
            ["Do you think 32 is considered young or old?",
             "my mom is 60 years old and still running"])
        self.assertEqual(
            _cnt_age_diff("How many years older is my mom than me?",
                          sessions), "28")

    def test_then_completed_at_age(self):
        sessions = sess(
            ["As a 32-year-old Digital Marketing Specialist at "
             "TechSavvy Inc., I'm pursuing the CDMP certification.",
             "I have a Bachelor's degree from UC Berkeley, which "
             "I completed at the age of 25."])
        self.assertEqual(
            _cnt_age_diff(
                "How many years older am I than when I graduated "
                "from college?", sessions), "7")

    def test_until_married_next_year(self):
        sessions = sess(
            ["I'm 32 now and thinking about my skin.",
             "My friend Rachel's getting married next year!"])
        self.assertEqual(
            _cnt_age_diff(
                "How many years will I be when my friend Rachel "
                "gets married?", sessions), "33")

    def test_self_age_grammar_as_someone(self):
        sessions = sess(
            ["As someone who's 32, I want career advice.",
             "I moved to the city at the age of 24."])
        self.assertEqual(
            _cnt_age_diff(
                "How many years older am I than when I moved?",
            sessions), "8")

    def test_ambiguous_self_age_falls_through(self):
        sessions = sess(
            ["I'm 32.",
             "Do you think 45 is considered young or old?"])  # 2 vals
        self.assertIsNone(_cnt_age_diff(
            "How many years older is my grandma than me?", sessions))

    def test_missing_relative_age_falls_through(self):
        sessions = sess(["I'm 32.", "Grandma is coming to visit."])
        self.assertIsNone(_cnt_age_diff(
            "How many years older is my grandma than me?", sessions))

    def test_ambiguous_relative_age_falls_through(self):
        sessions = sess(
            ["I'm 32.",
             "Grandma's 75th birthday was fun.",
             "my grandma is 76 years old now"])  # 75 vs 76
        self.assertIsNone(_cnt_age_diff(
            "How many years older is my grandma than me?", sessions))

    def test_nonpositive_diff_is_grammar_miss(self):
        sessions = sess(
            ["I'm 32.", "My sister is 25 years old"])
        # sister younger -> question "older is my sister" is a
        # presupposition failure, not an answer
        self.assertIsNone(_cnt_age_diff(
            "How many years older is my sister than me?", sessions))

    def test_until_without_married_word_falls_through(self):
        sessions = sess(
            ["I'm 32.", "My friend is graduating next year."])
        self.assertIsNone(_cnt_age_diff(
            "How many years will I be when my friend graduates?",
            sessions))

    def test_assistant_text_never_counts(self):
        sessions = [{"session_id": "s1", "turns": [
            {"role": "user", "content": "I'm 32 now."},
            {"role": "assistant",
             "content": "Your grandma is 75 years old, right?"}]}]
        self.assertIsNone(_cnt_age_diff(
            "How many years older is my grandma than me?", sessions))

    def test_gate_helper_lowercase(self):
        self.assertEqual(
            _age_form_gate(
                "how many years older is my grandpa than me"),
            "other")
        self.assertIsNone(_age_form_gate("how many pets do i have"))


if __name__ == '__main__':
    unittest.main()
