"""Measure recognition on a folder made by make_fixtures.py (synthetic voices).

Usage: python scripts/bench_asr.py FIXTURE_DIR MODEL_DIR
"""

import json
import os
import sys
import time
import wave
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.speech import Engine  # noqa: E402


def main(fx: str, models: str) -> None:
    eng = Engine(models)
    manifest = json.load(open(os.path.join(fx, "manifest.json"), encoding="utf-8"))
    tally = defaultdict(lambda: [0, 0])
    misses = []
    t0 = time.time()
    audio_s = 0.0
    for m in manifest:
        with wave.open(os.path.join(fx, m["file"])) as w:
            pcm = w.readframes(w.getnframes())
            audio_s += w.getnframes() / 16000
        v = m["value"]
        hi = 20 if v is not None and v <= 20 else 100 if v is not None and v < 100 else 999 if v is not None else 100
        h = eng.recognise_pcm(pcm, m["lang"], 0, hi)
        ok = (h.command == m["command"]) if m["command"] else (h.value == v)
        kind = "command" if m["command"] else ("1-3 digits" if v >= 100 else "0-99")
        tally[(m["lang"], kind)][0] += ok
        tally[(m["lang"], kind)][1] += 1
        if not ok:
            misses.append((m["file"], m["text"], h.text))
    for (lang, kind), (ok, n) in sorted(tally.items()):
        print(f"{lang} {kind:11s} {ok:3d}/{n:3d}  {100 * ok / n:5.1f}%")
    total_ok = sum(v[0] for v in tally.values()); total = sum(v[1] for v in tally.values())
    print(f"all {total_ok}/{total}  ({100 * total_ok / total:.1f}%)   decode {time.time() - t0:.1f}s for {audio_s:.0f}s of audio")
    for f, t, h in misses:
        print("  miss", f, repr(t), "->", repr(h))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
