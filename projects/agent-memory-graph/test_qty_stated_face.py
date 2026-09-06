"""Cycle 550 — qty-stated face: explicit digit-quantity statements
outrank signature counting inside enum_count.

Census /tmp/c550 (2026-09-06, full-500 enum_count population = 10
rows): 3 RESCUE (1cea1afa 500→600 recency, 5831f84d 10→15 recency,
6456829e 3+5 multi-type sum) / 0 KILL / 7 no-fire. Naive
all-numerals version simulated 14 KILLs (a/an/one determiner
poison) and was falsified pre-wiring — the traps below pin the
poison exclusions red-verified during the census.
"""
from amg_bench_quality import _cnt_enum_count


def sess(*lines):
    return {"session_id": "s0",
            "turns": [{"role": "user", "content": ln}
                      for ln in lines]}


def multi_sess(*sessions):
    return [{"session_id": f"s{j}", "turns": [{"role": "user",
                                               "content": ln}]}
            for j, ln in enumerate(sessions)]


# ------------------------------------------------------------- rescues

def test_recency_latest_wins():
    """1cea1afa: 500 last week, 600 now → current state is 600."""
    s = [sess("I just reached 500 followers last week, and I'm hoping "
              "to keep that momentum going.",
              "By the way, I just checked and I'm now at 600 followers, "
              "which is a nice milestone.")]
    got = _cnt_enum_count(
        "How many Instagram followers do I currently have?", s)
    assert got == "600"


def test_recency_multi_word_np():
    """5831f84d: earlier 10, latest 15 crash course videos → 15."""
    s = [sess("I've been keeping track of my educational activities "
              "and noticed I've watched a lot of Crash Course videos "
              "lately - I've already finished 10 videos in the past "
              "few weeks.",
              "I've been on a learning streak lately, having watched "
              "15 Crash Course videos in the past few weeks.")]
    got = _cnt_enum_count(
        "How many Crash Course videos have I watched in the past few "
        "weeks?", s)
    assert got == "15"


def test_multi_type_sum():
    """6456829e: 3 cucumber + 5 tomato plants, 'and' question → 8."""
    s = [sess("I've been growing my own cucumbers in my garden, and "
              "I've got 3 plants that are producing a lot of them.",
              "I planted 5 tomato plants initially, and they've been "
              "producing like crazy.")]
    got = _cnt_enum_count(
        "How many plants did I initially plant for tomatoes and "
        "cucumbers?", s)
    assert got == "8"


def test_non_candidate_turn_head_scan():
    """'600 followers' without the literal 'Instagram' topic word
    is still a quantity statement about followers."""
    s = [sess("By the way, I just checked and I'm now at 600 "
              "followers, which is a nice milestone.")]
    got = _cnt_enum_count(
        "How many Instagram followers do I currently have?", s)
    assert got == "600"


# ------------------------------------------------------------- poison

def test_article_determiners_excluded():
    """'a baby' is an article, not a count — naive all-numerals
    version killed 2e6d26dc (census). Face must abstain (the
    pre-existing names/roles signature still owns the row)."""
    from amg_bench_quality import _cnt_qty_stated
    s = [sess("My cousin Rachel just had a baby boy named Max in "
              "March.",
              "Our friends Mike and Emma welcomed their first baby, "
              "a girl named Charlotte.")]
    got = _cnt_qty_stated(
        "How many babies were born to friends and family members in "
        "the last few months?", s)
    assert got is None


def test_word_one_excluded():
    """'one tank' / 'the one I set up' is determiner usage."""
    s = [sess("I set up one tank for my friend's kid last weekend.")]
    got = _cnt_enum_count(
        "How many tanks do I currently have, including the one I set "
        "up for my friend's kid?", s)
    assert got is None


def test_hyphenated_units_face_no_fire():
    """'a 5-gallon tank' — the face never reads a hyphenated size as
    a count (no whitespace between 5 and tank); the pre-existing
    size-signature branch keeps owning that shape (2 sizes = 2)."""
    s = [sess("Since I've had experience with a 5-gallon tank and "
              "now have a 20-gallon community tank, I'm wondering "
              "about plants.")]
    got = _cnt_enum_count(
        "How many tanks do I currently have?", s)
    assert got == "2"


def test_assistant_turns_ignored():
    """Quantities stated by the assistant are not user facts."""
    s = [{"session_id": "s0", "turns": [
        {"role": "user", "content": "Tell me about my followers."},
        {"role": "assistant",
         "content": "You mentioned having 800 followers last month."}]}]
    got = _cnt_enum_count(
        "How many Instagram followers do I currently have?", s)
    assert got is None


def test_same_turn_ambiguity_abstains():
    """Two distinct values in the SAME latest turn → no claim."""
    s = [sess("Honestly I can't remember if I have 40 or 50 followers "
              "right now on my account.")]
    got = _cnt_enum_count(
        "How many Instagram followers do I currently have?", s)
    assert got is None


# ------------------------------------------------------------- fallback

def test_names_signature_fallback_preserved():
    """No digit statements → names/roles branch unchanged. The value
    below is the HEAD signature output for this fixture (pinned so a
    future face leaking into the fallback turns red)."""
    s = [sess("I attended my cousin Rachel's wedding in June.",
              "Then Emily and Sarah tied the knot in August.",
              "Jen and Tom's wedding closed out the year.")]
    got = _cnt_enum_count(
        "How many weddings have I attended in this year?", s)
    assert got == "2"


def test_answer_counting_wiring():
    """The face is reachable through answer_counting."""
    from amg_bench_quality import answer_counting
    s = [sess("I just reached 500 followers last week.",
              "I'm now at 600 followers, which is a nice milestone.")]
    ans, meta = answer_counting(
        "How many Instagram followers do I currently have?", s)
    assert ans == "600"
    assert meta.get("form") == "enum_count"


# --------------------------------------- C552: qualifier-scoped selection
#
# Census /tmp/c552 (2026-09-06, gate=counting production replay, 66 rows
# byte-identical at HEAD; 22 enum_count rows): the two C550 latent KILLs
# share one shape — the question carries a temporal scope qualifier and
# plain recency overrides it. Gate A: "before the 7/22 trip" → resolve
# among explicitly dated mentions, dropping the excluded date.
# Gate B: "first three months" → resolve among clauses carrying that
# same duration phrase. Both fall through to recency when no qualifier
# match exists (conservative).

def test_before_date_exclusion():
    """10e09553: 7 on 7/10 (early trip), 9 on 7/22 (late) + undated
    anaphoric '9'. Question asks for the trip BEFORE 7/22 → the dated
    mention with a different date wins; the undated echo never votes."""
    s = multi_sess(
        "Oh, and by the way, I caught 7 largemouth bass on my trip to "
        "Lake Michigan with Alex on 7/10 - that was a great day!",
        "By the way, I'm thinking of using spinnerbaits and plastic "
        "worms as lures again, since they worked so well when I was "
        "there with Alex on 7/22 - we caught 9 largemouth bass that day.",
        "Remember that trip when we caught 9 largemouth bass with Alex?")
    got = _cnt_enum_count(
        "How many largemouth bass did I catch with Alex on the earlier "
        "fishing trip to Lake Michigan before the 7/22 trip?", s)
    assert got == "7"


def test_before_date_no_dated_survivor_abstains():
    """Question says 'before 7/22' but no clause carries any M/D date
    → the face cannot honor the scope, and answering via bare
    recency would be the exact failure the gate exists to prevent.
    Honest abstention at the FACE level (downstream then falls
    through to signature counting, which owns the row)."""
    from amg_bench_quality import _cnt_qty_stated
    s = multi_sess(
        "I caught 7 largemouth bass with Alex, great day!",
        "Later we caught 9 largemouth bass with Alex again.")
    got = _cnt_qty_stated(
        "How many largemouth bass did I catch with Alex before the "
        "7/22 trip?", s)
    assert got is None         # abstain — recency would violate scope


def test_first_duration_scope():
    """0ddfec37: '15 ... three months ago' (onset window) vs
    '20 ... past few months' (later window). Question asks about the
    FIRST three months → the clause carrying 'three months' wins."""
    s = multi_sess(
        "I just got a signed baseball of his last week and it's a "
        "great addition to my collection - that's 15 autographed "
        "baseballs since I started collecting three months ago!",
        "I just got back from a weekend trip and had some time to "
        "organize my collection - I've added 20 autographed baseballs "
        "to my collection in the past few months, which is crazy!")
    got = _cnt_enum_count(
        "How many autographed baseballs have I added to my collection "
        "in the first three months of collection?", s)
    assert got == "15"


def test_first_duration_digit_form():
    """'first 3 months' (digit in question) matches 'three months'
    (word in clause) and vice versa."""
    s = multi_sess(
        "That's 15 autographed baseballs since I started collecting "
        "three months ago!",
        "I've added 20 autographed baseballs in the past few months.")
    got = _cnt_enum_count(
        "How many autographed baseballs have I added to my collection "
        "in the first 3 months?", s)
    assert got == "15"


def test_first_duration_no_match_abstains():
    """'first three months' question but clauses only carry 'past few
    months' → no phrase match, honest abstention at the FACE level
    over out-of-scope recency."""
    from amg_bench_quality import _cnt_qty_stated
    s = multi_sess(
        "That's 15 autographed baseballs so far!",
        "I've added 20 autographed baseballs in the past few months.")
    got = _cnt_qty_stated(
        "How many autographed baseballs have I added to my collection "
        "in the first three months of collection?", s)
    assert got is None         # abstain — recency would violate scope
