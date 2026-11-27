"""Recogniser tests against synthetic fixture audio. Needs the real models."""

import json
import os
import wave

import pytest

from app.speech import Engine, build_grammar, interpret
from conftest import MODELS, needs_models

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_grammar_limits_the_words():
    g = json.loads(build_grammar("en", 0, 20))
    assert "twenty" in g and "thirty" not in g and "hundred" not in g and "repeat" in g and "[unk]" in g
    h = json.loads(build_grammar("hi", 0, 20))
    assert "साठ" not in h and "सात" in h and "दोबारा" in h
    with pytest.raises(ValueError):
        build_grammar("hi", 5, 3)
    with pytest.raises(ValueError):
        build_grammar("fr", 0, 5)


def test_interpret():
    assert interpret("पचपन", "hi").value == 55
    assert interpret("दोबारा", "hi").command == "repeat"
    assert interpret("skip", "en").command == "skip"
    assert interpret("[unk]", "en").value is None
    assert interpret("five [unk]", "en").value is None      # something unheard in the middle: do not guess
    assert interpret("", "hi").value is None
    assert interpret("seven eight", "en").value is None


def _pcm(name):
    with wave.open(os.path.join(FIX, name)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        return w.readframes(w.getnframes())


@needs_models
def test_fixture_audio_is_recognised():
    eng = Engine(MODELS)
    manifest = json.load(open(os.path.join(FIX, "manifest.json"), encoding="utf-8"))
    wrong = []
    for m in manifest:
        hi = 999 if (m["value"] or 0) > 99 else 100
        h = eng.recognise_pcm(_pcm(m["file"]), m["lang"], 0, hi)
        ok = h.command == m["command"] if m["command"] else h.value == m["value"]
        if not ok:
            wrong.append((m["file"], m["text"], h.text))
    # synthetic voices; a few misses are expected, a collapse is not
    assert len(wrong) <= 3, wrong


@needs_models
def test_narrow_range_removes_the_seven_sixty_mixup():
    eng = Engine(MODELS)
    m = next(x for x in json.load(open(os.path.join(FIX, "manifest.json"), encoding="utf-8"))
             if x["lang"] == "hi" and x["value"] == 7)
    assert eng.recognise_pcm(_pcm(m["file"]), "hi", 0, 20).value == 7


@needs_models
def test_silence_is_not_an_answer():
    eng = Engine(MODELS)
    h = eng.recognise_pcm(b"\0" * 32000, "en", 0, 100)
    assert h.value is None and h.command is None
