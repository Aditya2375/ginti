"""Measure recognition on a folder made by make_fixtures.py (synthetic voices).

Usage: python scripts/bench_asr.py FIXTURE_DIR MODEL_DIR

Each clip is decoded once for every grammar band the app can use for that answer.
"""

import json
import os
import sys
import time
import wave
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import random  # noqa: E402

from app.engine import TOPICS, _make  # noqa: E402
from app.numbers import parse_number  # noqa: E402
from app.speech import Engine  # noqa: E402


def app_bands() -> dict[int, set[int]]:
    """For each answer the app can ask for, every grammar band (upper limit) it really uses.

    Built by generating questions the way the app does and reading Question.answer_range,
    so the benchmark limits the recogniser exactly as the live app does, not by the answer."""
    rng = random.Random(1)
    out: dict[int, set[int]] = defaultdict(set)
    for topic in [t for t in TOPICS if t != "mix"]:
        for level in (1, 2, 3, 4):
            for _ in range(4000):
                q = _make(topic, level, rng)
                out[q.answer].add(q.answer_range[1])
    return out


def main(fx: str, models: str) -> None:
    eng = Engine(models)
    manifest = json.load(open(os.path.join(fx, "manifest.json"), encoding="utf-8"))
    tally = defaultdict(lambda: [0, 0])
    misses = []
    t0 = time.time()
    audio_s = 0.0
    decoded_s = 0.0
    bands = app_bands()
    for m in manifest:
        with wave.open(os.path.join(fx, m["file"])) as w:
            pcm = w.readframes(w.getnframes())
            audio_s += w.getnframes() / 16000
        v = m["value"]
        if m["command"]:
            caps = {20, 100, 1000}               # commands can come in any band
        else:
            caps = bands.get(v) or ({100} if v < 100 else {1000})
        for cap in sorted(caps):
            h = eng.recognise_pcm(pcm, m["lang"], 0, cap)
            # same path as the app: the server parses h.text again when the browser sends it back
            ok = (h.command == m["command"]) if m["command"] else (h.value == v and parse_number(h.text, m["lang"]) == v)
            decoded_s += len(pcm) / 2 / 16000
            kind = "command" if m["command"] else ("1-3 digits" if v >= 100 else "0-99")
            tally[(m["lang"], kind)][0] += ok
            tally[(m["lang"], kind)][1] += 1
            if not ok:
                misses.append((m["file"], f"{m['text']} [band 0..{cap}]", h.text))
    for (lang, kind), (ok, n) in sorted(tally.items()):
        print(f"{lang} {kind:11s} {ok:3d}/{n:3d}  {100 * ok / n:5.1f}%")
    total_ok = sum(v[0] for v in tally.values()); total = sum(v[1] for v in tally.values())
    print(f"all {total_ok}/{total}  ({100 * total_ok / total:.1f}%)   {total} decodes, {decoded_s:.0f} s of audio, in {time.time() - t0:.1f} s ({decoded_s / (time.time() - t0):.0f}x real time on this machine)")
    for f, t, h in misses:
        print("  miss", f, repr(t), "->", repr(h))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
