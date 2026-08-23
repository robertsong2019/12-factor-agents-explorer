"""C505 (#085): duration-family M1-M4 unit tests.

Oracle parity verified separately on /tmp/dur_oracle2.json
(7/7 incl. controls aae3761f=15, 2788b940 unclaimed). These
tests pin the mechanisms on minimal fixtures.
"""
import sys
import unittest

sys.path.insert(0, '.')
from amg_bench_quality import (answer_counting, counting_form,
                               _cnt_duration_family)


def sess(*user_turns, sid="s1"):
    return {"session_id": sid,
            "turns": [{"role": "user", "content": c}
                      for c in user_turns]}


class TestGates(unittest.TestCase):
    def test_forms_claimed(self):
        self.assertEqual(counting_form(
            "How many weeks did it take me to watch all the "
            "Marvel movies?"), "duration_family")
        self.assertEqual(counting_form(
            "How many hours do I spend driving to my favorite "
            "destinations?"), "duration_family")
        self.assertEqual(counting_form(
            "How many hours did I spend exercising last week?"),
            "duration_family")
        self.assertEqual(counting_form(
            "How many days did it take for my order to arrive "
            "after I bought it?"), "duration_family")

    def test_disjointness(self):
        # item-count watch questions are NOT duration_family
        self.assertNotEqual(counting_form(
            "How many movies did I watch this month?"),
            "duration_family")
        # plain duration stays with duration_sum
        self.assertEqual(counting_form(
            "How many days did I spend in Japan?"), "duration_sum")
        # "ago"/"between" interval forms are NOT claimed by
        # duration_family (they stay with duration_sum/temporal)
        self.assertNotEqual(counting_form(
            "How many weeks passed between my two Japan trips?"),
            "duration_family")
        # per-typical-week frequency is NOT claimed here
        self.assertIsNone(counting_form(
            "How many fitness classes do I take per typical week?"))

    def test_m3_excludes_total_forms(self):
        self.assertNotEqual(counting_form(
            "How many hours did I spend exercising in total?"),
            "duration_family")


class TestM1BingeDedup(unittest.TestCase):
    def test_franchise_remention_counts_once(self):
        s = [sess(
            "I watched all 22 Marvel Cinematic Universe movies "
            "in two weeks!",
            "Then I finished the main Star Wars films in a week "
            "and a half.",
            "My friends couldn't believe I watched all the Marvel "
            "movies in two weeks.")]
        ans = _cnt_duration_family(
            "How many weeks did it take me to watch all those "
            "movies?", s)
        self.assertEqual(ans, "3.5 weeks")   # naive re-mention: 5.5

    def test_drive_destination_dedup(self):
        s = [sess(
            "The trip to Chicago took about five hours each way.",
            "Driving to Chicago again last month was only four "
            "hours.",
            "My drive to Milwaukee took two hours."),
            sess("It took three hours to get to Detroit.",
                 sid="s2")]
        ans = _cnt_duration_family(
            "How many hours did I spend driving to each of my "
            "destinations?", s)
        self.assertEqual(ans, "10")   # 5 (Chicago once) + 2 + 3


class TestM2ScheduleContext(unittest.TestCase):
    def test_unrelated_weekday_sentence_pollutes_no_more(self):
        s = [sess(
            "I attend Zumba classes on Tuesdays and Thursdays.",
            "I also play tennis on Sundays with my neighbor.")]
        ans, _ = answer_counting(
            "How many days a week do I attend fitness classes?", s)
        self.assertEqual(ans, "2")   # tennis Sunday doesn't count


class TestM3PlanFactWall(unittest.TestCase):
    def test_habitual_yoga_excluded_realized_jog_counted(self):
        s = [sess(
            "I used to do yoga for an hour every morning.",
            "I'm trying to get back into it, I'll schedule my "
            "sessions soon.",
            "I went for a 30-minute jog on Saturday.")]
        ans = _cnt_duration_family(
            "How many hours of jogging did I do last week?", s)
        self.assertEqual(ans, "0.5 hours")

    def test_activity_filter(self):
        s = [sess("I took a two-hour pottery class on Monday.",
                  "I did a one-hour yoga session on Tuesday.")]
        ans = _cnt_duration_family(
            "How many hours did I spend on yoga?", s)
        self.assertEqual(ans, "1 hours")


class TestM4DeliveryInterval(unittest.TestCase):
    def test_month_name_dates(self):
        s = [sess(
            "I ordered my new coffee machine on February 5th.",
            "It arrived on February 10th and I love it.")]
        ans = _cnt_duration_family(
            "How many days did it take for me to receive the "
            "coffee machine after I ordered it?", s)
        self.assertEqual(ans, "5 days")

    def test_slash_dates_anaphoric_product(self):
        s = [sess(
            "I finally got my new laptop backpack last month.",
            "I bought it from Amazon on 1/15.",
            "It arrived on 1/20, only five days.")]
        ans = _cnt_duration_family(
            "How many days did it take for my laptop backpack to "
            "arrive after I bought it?", s)
        self.assertEqual(ans, "5 days")

    def test_wrong_product_abstains(self):
        s = [sess(
            "I finally got my new laptop backpack last month.",
            "I bought it from Amazon on 1/15.",
            "It arrived on 1/20.")]
        ans = _cnt_duration_family(
            "How many days did it take for my iPad case to arrive "
            "after I bought it?", s)
        self.assertIsNone(ans)   # evidence is the backpack's, not asked


if __name__ == "__main__":
    unittest.main()
