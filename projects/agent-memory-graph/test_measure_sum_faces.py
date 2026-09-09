"""C561: measurement-unit sum faces (total distance/weight/time family).

counting_form() claimed only money totals ("total amount/cost/price"
→ item_total, C500) — "What is the total distance/weight/time ..."
fell through the gate chain to losing lines. Census (500 rows,
/tmp/c561/census1.py): the widened form claims exactly 4 rows, all
currently WRONG, zero banked overlap:

  d3ab962e  distance  '8 miles'          3-mile loop + 5-mile hike
  6c49646a  distance  '3,000 miles'      1,800 + 1,200 (both "total
                                       of"; decoy "300 miles on the
                                       first day" must NOT sum)
  bc149d6b  weight    '70 pounds'        50-pound batch + 20 pounds
  1192316e  time      'an hour and a     takes-anchored an hour +
                      half'              commute 30 minutes; the
                                         get-ready sentence's inner
                                         20/30-minute items must NOT
                                         sum; "4.5-hour drive away"
                                         has no takes anchor

Miniatures here prove mechanism structure/ranking; the census proves
the surface.
"""
import os
import sys
import unittest

if os.environ.get("PYTHONHASHSEED") != "7":
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "PYTHONHASHSEED": "7"})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amg_bench_quality import (answer_counting, counting_form,
                               _cnt_measure_sum)


def sess(*turns):
    """(*turns) → one evidence session; each turn is (role, content)."""
    return [{"session_id": "s0",
             "turns": [{"role": r, "content": c} for r, c in turns]}]


Q_DIST_MARKED = "What is the total distance of the four road trips?"
Q_DIST_UNMARKED = "What is the total distance of the hikes I did on two consecutive weekends?"
Q_WEIGHT = "What is the total weight of the chicken feed I bought?"
Q_TIME = "What is the total time it takes I to get ready and commute to work?"


class TestMeasureSumForm(unittest.TestCase):
    def test_form_claims_measures(self):
        self.assertEqual(counting_form(Q_DIST_MARKED), "measure_sum")
        self.assertEqual(counting_form(Q_DIST_UNMARKED), "measure_sum")
        self.assertEqual(counting_form(Q_WEIGHT), "measure_sum")
        self.assertEqual(counting_form(Q_TIME), "measure_sum")

    def test_form_leaves_money_and_number_forms_untouched(self):
        # regression: existing forms keep their owners
        self.assertEqual(
            counting_form("What is the total amount I spent on X?"),
            "item_total")
        self.assertEqual(
            counting_form("What is the total cost of A and B?"),
            "item_total")
        self.assertEqual(
            counting_form("What is the total number of books I own?"),
            "number_total")


class TestMeasureSumWeight(unittest.TestCase):
    def test_weight_sum_70_pounds(self):
        # bc149d6b: hyphen-adjective + postunit quantities
        out = _cnt_measure_sum(Q_WEIGHT, sess(
            ("user", "I finally got a 50-pound batch of layer feed "
                     "for the hens."),
            ("assistant", "A hen eats 1-1.5 pounds of feed per day."),
            ("user", "I also bought 20 pounds of organic scratch "
                     "grains.")))
        self.assertEqual(out, "70 pounds")

    def test_weight_intent_line_excluded(self):
        out = _cnt_measure_sum(Q_WEIGHT, sess(
            ("user", "I'm thinking of getting 30 pounds next month "
                     "if the hens keep laying.")))
        self.assertIsNone(out)


class TestMeasureSumDistance(unittest.TestCase):
    def test_distance_marked_tier_sums_only_total_of_lines(self):
        # 6c49646a: two "total of" lines + user decoy without 'total'
        out = _cnt_measure_sum(Q_DIST_MARKED, sess(
            ("user", "Since I've covered a total of 1,800 miles on my "
                     "recent three road trips, I'm comfortable with "
                     "the drive."),
            ("user", "We drove around 300 miles on the first day to "
                     "reach Jackson."),
            ("user", "I just got back from a 4-day trip to Yellowstone "
                     "where we covered a total of 1,200 miles.")))
        self.assertEqual(out, "3,000 miles")

    def test_distance_unmarked_tier_sums_all_user_quantities(self):
        # d3ab962e: hyphen-adjective miles on user lines
        out = _cnt_measure_sum(Q_DIST_UNMARKED, sess(
            ("user", "I just did a 3-mile loop trail at Valley of Fire "
                     "last weekend."),
            ("assistant", "The scenic drive spans 655 miles from "
                          "Leggett to San Diego."),
            ("user", "I just got back from an amazing 5-mile hike at "
                     "Red Rock Canyon.")))
        self.assertEqual(out, "8 miles")

    def test_distance_range_is_not_a_quantity(self):
        out = _cnt_measure_sum(Q_DIST_UNMARKED, sess(
            ("user", "An e-bike battery lasts 20-40 miles per charge "
                     "on flat terrain.")))
        self.assertIsNone(out)

    def test_distance_assistant_noise_excluded(self):
        out = _cnt_measure_sum(Q_DIST_UNMARKED, sess(
            ("assistant", "You could drive 100 miles or take the "
                          "17-mile loop road.")))
        self.assertIsNone(out)


class TestMeasureSumTime(unittest.TestCase):
    def test_time_takes_anchored_sum(self):
        # 1192316e: get-ready sentence's inner 20/30-minute items are
        # NOT takes-anchored — must not inflate the sum
        out = _cnt_measure_sum(Q_TIME, sess(
            ("user", "My daily commute to work takes about 30 "
                     "minutes, so I want to make the most of that "
                     "time."),
            ("user", "I wake up at 6:30 AM and it takes me about an "
                     "hour to get ready, which includes a 20-minute "
                     "meditation session, a 30-minute workout, and a "
                     "quick breakfast."),
            ("user", "My parents live in a 4.5-hour drive away town.")))
        self.assertEqual(out, "an hour and a half")

    def test_time_hour_render(self):
        out = _cnt_measure_sum(Q_TIME, sess(
            ("user", "The commute takes 60 minutes each way.")))
        self.assertEqual(out, "an hour")

    def test_time_no_takes_anchor_no_answer(self):
        out = _cnt_measure_sum(Q_TIME, sess(
            ("user", "The trail is a 3-hour drive away from home.")))
        self.assertIsNone(out)


class TestMeasureSumDispatch(unittest.TestCase):
    def test_answer_counting_dispatch_and_fallback(self):
        ans, detail = answer_counting(
            Q_WEIGHT, sess(
                ("user", "I got a 50-pound batch."),
                ("user", "I bought 20 pounds of scratch grains.")))
        self.assertEqual(ans, "70 pounds")
        self.assertEqual(detail.get("form"), "measure_sum")
        ans2, detail2 = answer_counting(Q_WEIGHT, sess())
        self.assertIsNone(ans2)

    def test_judge_semantic_credits_exact_renders(self):
        from amg_bench_quality import judge_semantic
        self.assertEqual(judge_semantic(Q_WEIGHT, "70 pounds",
                                        "70 pounds"), "CORRECT")
        self.assertEqual(judge_semantic(Q_DIST_MARKED, "3,000 miles",
                                        "3,000 miles"), "CORRECT")
        self.assertEqual(judge_semantic(Q_TIME, "an hour and a half",
                                        "an hour and a half"),
                         "CORRECT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
