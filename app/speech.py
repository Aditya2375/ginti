"""Offline speech recognition for number answers.

Audio is decoded on this machine by Vosk, an open-source speech recogniser.
For each question the recogniser is limited to the words needed to say the
numbers that could plausibly be the answer, plus two spoken commands. That
limit is what makes a small model dependable on short answers: it cannot
hear "saath" when the answer to 3 + 4 can only be a number under 20.

Nothing is sent to any other server and no audio is written to disk.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass

from .numbers import to_english, to_hindi, parse_number

SAMPLE_RATE = 16000
MAX_UTTERANCE_SECONDS = 12

MODEL_NAMES = {
    "hi": "vosk-model-small-hi-0.22",
    "en": "vosk-model-small-en-in-0.4",
}

# Spoken commands. Each is one word the model already knows.
COMMAND_WORDS = {
    "hi": {"repeat": "दोबारा", "skip": "छोड़ो"},
    "en": {"repeat": "repeat", "skip": "skip"},
}


class ModelMissing(RuntimeError):
    pass


def _grammar_words(lang: str, lo: int, hi: int) -> list[str]:
    to_words = to_hindi if lang == "hi" else to_english
    words: set[str] = set()
    for n in range(lo, hi + 1):
        words.update(to_words(n).split())
    words.update(COMMAND_WORDS[lang].values())
    return sorted(words)


def build_grammar(lang: str, lo: int, hi: int) -> str:
    if lang not in MODEL_NAMES:
        raise ValueError("unsupported language")
    if not (0 <= lo <= hi <= 9999):
        raise ValueError("bad answer range")
    return json.dumps(_grammar_words(lang, lo, hi) + ["[unk]"], ensure_ascii=False)


@dataclass
class Heard:
    text: str
    value: int | None
    command: str | None


def interpret(text: str, lang: str) -> Heard:
    """Turn recogniser text into a number, a command, or neither.

    [unk] means the recogniser heard something outside the allowed words. At the start or
    end of the utterance that is usually a cough or a breath, so it is ignored. In the
    middle it could hide a word, so the answer is rejected rather than guessed."""
    text = text.strip()
    words = text.split()
    while words and words[0] == "[unk]":
        words.pop(0)
    while words and words[-1] == "[unk]":
        words.pop()
    clean = " ".join(words)               # what the app keeps: the browser and server must agree on it
    if not words:
        return Heard(text, None, None)
    for name, word in COMMAND_WORDS[lang].items():
        if words == [word]:
            return Heard(clean, None, name)
    if "[unk]" in words:
        return Heard(text, None, None)
    return Heard(clean, parse_number(clean, lang), None)


class Engine:
    """Loads models on first use and hands out per-connection sessions."""

    def __init__(self, model_dir: str | None = None):
        self.model_dir = model_dir or os.environ.get("GINTI_MODEL_DIR", "/models")
        self._models: dict[str, object] = {}
        self._lock = threading.Lock()

    def available(self, lang: str) -> bool:
        return os.path.isdir(os.path.join(self.model_dir, MODEL_NAMES[lang]))

    def preload(self) -> list[str]:
        """Load every installed model now, so the first child does not wait for it."""
        loaded = []
        for lang in MODEL_NAMES:
            if self.available(lang):
                self._model(lang)
                loaded.append(lang)
        return loaded

    def _model(self, lang: str):
        with self._lock:
            if lang not in self._models:
                path = os.path.join(self.model_dir, MODEL_NAMES[lang])
                if not os.path.isdir(path):
                    raise ModelMissing(f"speech model not found at {path}")
                from vosk import Model, SetLogLevel
                SetLogLevel(-1)
                self._models[lang] = Model(path)
            return self._models[lang]

    def session(self, lang: str, lo: int, hi: int) -> "Session":
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self._model(lang), SAMPLE_RATE, build_grammar(lang, lo, hi))
        return Session(rec, lang)

    def recognise_pcm(self, pcm: bytes, lang: str, lo: int, hi: int) -> Heard:
        """One-shot: all of the audio in, one answer out."""
        s = self.session(lang, lo, hi)
        s.feed(pcm)
        return s.finish()


class Session:
    def __init__(self, recogniser, lang: str):
        self._rec = recogniser
        self.lang = lang
        self._bytes = 0
        self._done: Heard | None = None

    def feed(self, pcm: bytes) -> dict | None:
        """Add audio. Returns a partial or final message when there is one."""
        if not pcm:
            return None
        self._bytes += len(pcm)
        if self._bytes > MAX_UTTERANCE_SECONDS * SAMPLE_RATE * 2:
            raise ValueError("utterance too long")
        if self._rec.AcceptWaveform(pcm):
            msg = self._final(json.loads(self._rec.Result()))
            if self._done is None:
                self._done = Heard(msg["text"], msg["value"], msg["command"])
            return msg
        part = json.loads(self._rec.PartialResult()).get("partial", "")
        return {"type": "partial", "text": part} if part else None

    def finish(self) -> Heard:
        if self._done is not None:       # the recogniser already closed the utterance
            return self._done
        # Trailing silence so a late endpoint still closes the utterance.
        self._rec.AcceptWaveform(b"\0" * SAMPLE_RATE)
        return interpret(json.loads(self._rec.FinalResult()).get("text", ""), self.lang)

    def _final(self, result: dict) -> dict:
        h = interpret(result.get("text", ""), self.lang)
        return {"type": "final", "text": h.text, "value": h.value, "command": h.command}
