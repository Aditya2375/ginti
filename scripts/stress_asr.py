"""Rough robustness check: the small fixture set with a raised pitch and with added noise.

Usage: python scripts/stress_asr.py FIXTURE_DIR MODEL_DIR     (needs numpy and ffmpeg)
Same synthetic clips as bench_asr.py, so this still says nothing about children.
"""

import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from bench_asr import app_bands  # noqa: E402

from app.speech import Engine  # noqa: E402


def load(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)


def pitch_up(x, factor):
    """Raise pitch (and speed) by resampling, then pad back; a crude stand-in for a child's voice."""
    idx = np.arange(0, len(x), factor)
    return np.interp(idx, np.arange(len(x)), x)


def noise(x, snr_db, rng):
    p = np.mean(x ** 2) + 1e-9
    n = rng.normal(0, np.sqrt(p / 10 ** (snr_db / 10)), len(x))
    return x + n


def main(fx, models):
    eng = Engine(models)
    bands = app_bands()
    manifest = json.load(open(os.path.join(fx, "manifest.json"), encoding="utf-8"))
    rng = np.random.default_rng(0)
    for name, fn in [("clean", lambda x: x), ("pitch +40%", lambda x: pitch_up(x, 1.4)), ("noise 10 dB", lambda x: noise(x, 10, rng)), ("noise 0 dB", lambda x: noise(x, 0, rng))]:
        ok = n = 0
        for m in manifest:
            x = np.clip(fn(load(os.path.join(fx, m["file"]))), -32768, 32767).astype(np.int16).tobytes()
            v = m["value"]
            for cap in sorted({20, 100} if m["command"] else (bands.get(v) or ({100} if v < 100 else {1000}))):
                h = eng.recognise_pcm(x, m["lang"], 0, cap)
                ok += (h.command == m["command"]) if m["command"] else (h.value == v)
                n += 1
        print(f"{name:12s} {ok}/{n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
