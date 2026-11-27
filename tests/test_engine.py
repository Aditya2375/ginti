from app.engine import (BOX_GAP, MAX_LEVEL, Picker, Question, _from_key, update_box, update_level)


def test_answers_and_keys():
    assert Question("add", 7, 8, 1).answer == 15
    assert Question("sub", 9, 4, 1).answer == 5
    assert Question("mul", 7, 8, 2).answer == 56
    assert Question("mul", 7, 8, 2).key == "7x8"
    assert _from_key("7x8", 2) == Question("mul", 7, 8, 2)
    assert _from_key("12-5", 3).answer == 7


def test_prompts_in_both_languages():
    q = Question("add", 7, 8, 1)
    assert q.prompt("hi") == "सात जमा आठ, कितना हुआ?"
    assert q.prompt("en") == "seven plus eight. What is the answer?"
    assert Question("sub", 20, 5, 2).prompt("hi").startswith("बीस में से पाँच घटाओ")
    assert Question("mul", 6, 7, 2).display() == "6 × 7"


def test_answer_range_never_hides_the_answer_and_is_banded():
    p = Picker(seed=1)
    for topic in ("add", "sub", "mul", "mix"):
        for level in range(1, MAX_LEVEL + 1):
            for _ in range(200):
                q = p.next_question(topic, level, {}, 0)
                lo, hi = q.answer_range
                assert lo <= q.answer <= hi
                assert hi in (20, 50, 100, 200, 1000, 9999)
                assert q.answer >= 0


def test_questions_stay_in_level_bounds():
    p = Picker(seed=2)
    for _ in range(300):
        q = p.next_question("add", 1, {}, 0)
        assert q.answer <= 10 and q.a >= 1 and q.b >= 1
        q = p.next_question("add", 3, {}, 0)
        assert q.answer <= 100
        q = p.next_question("mul", 2, {}, 0)
        assert 2 <= q.a <= 10 and 2 <= q.b <= 10


def test_missed_fact_comes_back_when_due():
    p = Picker(seed=3)
    boxes = {"7x8": {"box": 0, "last_served": 0}}
    seen = sum(p.next_question("mul", 2, boxes, BOX_GAP[0] + 5).key == "7x8" for _ in range(300))
    assert seen > 60          # about 45% of picks are for due facts
    nothing_due = sum(p.next_question("mul", 2, {"7x8": {"box": 4, "last_served": 90}}, 91).key == "7x8" for _ in range(300))
    assert nothing_due < 30


def test_box_and_level_rules():
    assert update_box(0, True) == 1 and update_box(4, True) == 4 and update_box(3, False) == 0
    level, streak, misses = 1, 0, 0
    for _ in range(5):
        level, streak, misses = update_level(level, streak, misses, True)
    assert level == 2 and streak == 0
    for _ in range(3):
        level, streak, misses = update_level(level, streak, misses, False)
    assert level == 1
    assert update_level(1, 0, 2, False) == (1, 0, 3)     # never below level 1
    assert update_level(MAX_LEVEL, 4, 0, True)[0] == MAX_LEVEL
