"""Question choice: what to ask next, and how hard.

Each learner has a level per topic and a small box number per fact
(Leitner style). A fact answered wrong goes back to box 0 and comes round
again soon; a fact answered right moves up and comes round less often.
The level goes up after a run of correct answers and down after misses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .numbers import to_english, to_hindi

TOPICS = ("add", "sub", "mul", "mix")
MAX_LEVEL = 4
LEVEL_UP_STREAK = 5
LEVEL_DOWN_MISSES = 3
MAX_BOX = 4
# How many questions between repeats of a fact, per box.
BOX_GAP = (2, 4, 8, 16, 32)


@dataclass(frozen=True)
class Question:
    topic: str            # add | sub | mul
    a: int
    b: int
    level: int

    @property
    def key(self) -> str:
        sym = {"add": "+", "sub": "-", "mul": "x"}[self.topic]
        return f"{self.a}{sym}{self.b}"

    @property
    def answer(self) -> int:
        return {"add": self.a + self.b, "sub": self.a - self.b, "mul": self.a * self.b}[self.topic]

    @property
    def answer_range(self) -> tuple[int, int]:
        """Numbers a child could plausibly say. Wide enough not to give the answer away."""
        hi = {"add": (self.a + self.b), "sub": max(self.a, self.b), "mul": self.a * self.b}[self.topic]
        cap = _cap_for(hi)
        return 0, cap

    def display(self) -> str:
        sym = {"add": "+", "sub": "−", "mul": "×"}[self.topic]
        return f"{self.a} {sym} {self.b}"

    def prompt(self, lang: str) -> str:
        if lang == "hi":
            a, b = to_hindi(self.a), to_hindi(self.b)
            return {
                "add": f"{a} जमा {b}, कितना हुआ?",
                "sub": f"{a} में से {b} घटाओ, कितना बचा?",
                "mul": f"{a} गुणा {b}, कितना हुआ?",
            }[self.topic]
        a, b = to_english(self.a), to_english(self.b)
        return {
            "add": f"{a} plus {b}. What is the answer?",
            "sub": f"{a} minus {b}. What is the answer?",
            "mul": f"{a} times {b}. What is the answer?",
        }[self.topic]


def _cap_for(n: int) -> int:
    """Round the largest possible answer up to a band, so the range is the same for every question in it."""
    for cap in (20, 50, 100, 200, 1000, 9999):
        if n <= cap:
            return cap
    return 9999


def _make(topic: str, level: int, rng: random.Random) -> Question:
    if topic == "add":
        lim = {1: 10, 2: 20, 3: 100, 4: 999}[level]
        if level <= 2:
            a = rng.randint(1, lim - 1)
            b = rng.randint(1, lim - a)
        elif level == 3:
            a, b = rng.randint(10, 80), rng.randint(5, 19)
            if a + b > 100:
                b = 100 - a
        else:
            a, b = rng.randint(100, 700), rng.randint(20, 299)
        return Question("add", a, b, level)
    if topic == "sub":
        lim = {1: 10, 2: 20, 3: 100, 4: 999}[level]
        a = rng.randint(max(2, lim // 2), lim) if level >= 3 else rng.randint(1, lim)
        b = rng.randint(1, a)
        return Question("sub", a, b, level)
    if topic == "mul":
        hi = {1: 5, 2: 10, 3: 12, 4: 15}[level]
        return Question("mul", rng.randint(2, hi), rng.randint(2, hi if level > 1 else 5), level)
    raise ValueError("unknown topic")


class Picker:
    """Chooses the next question for one learner. State is passed in, not held."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def next_question(self, topic: str, level: int, boxes: dict[str, dict], served: int) -> Question:
        """boxes maps fact key -> {"box": int, "last_served": int}; served counts questions so far."""
        if topic not in TOPICS:
            raise ValueError("unknown topic")
        level = max(1, min(MAX_LEVEL, level))
        topics = ("add", "sub", "mul") if topic == "mix" else (topic,)
        due: list[tuple[int, str]] = []
        for key, st in boxes.items():
            if _topic_of(key) in topics and served - st["last_served"] >= BOX_GAP[min(st["box"], MAX_BOX)]:
                due.append((st["box"], key))
        if due and self.rng.random() < 0.45:
            due.sort()
            return _from_key(due[0][1], level)
        for _ in range(30):
            q = _make(self.rng.choice(topics), level, self.rng)
            st = boxes.get(q.key)
            if st is None or served - st["last_served"] >= 2:
                return q
        return q


def _topic_of(key: str) -> str:
    return "add" if "+" in key else "sub" if "-" in key else "mul"


def _from_key(key: str, level: int) -> Question:
    for sym, topic in (("+", "add"), ("-", "sub"), ("x", "mul")):
        if sym in key:
            a, b = key.split(sym)
            return Question(topic, int(a), int(b), level)
    raise ValueError("bad fact key")


def update_box(box: int, correct: bool) -> int:
    return min(MAX_BOX, box + 1) if correct else 0


def update_level(level: int, streak: int, misses: int, correct: bool) -> tuple[int, int, int]:
    """Returns (level, streak, misses_in_a_row)."""
    if correct:
        streak, misses = streak + 1, 0
        if streak >= LEVEL_UP_STREAK and level < MAX_LEVEL:
            return level + 1, 0, 0
        return level, streak, 0
    misses += 1
    if misses >= LEVEL_DOWN_MISSES and level > 1:
        return level - 1, 0, 0
    return level, 0, misses
