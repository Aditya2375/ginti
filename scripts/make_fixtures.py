"""Make synthetic spoken-number test audio with a neural text-to-speech voice.

Usage: python scripts/make_fixtures.py OUT_DIR [small|full]

Needs `pip install edge-tts` and ffmpeg, and network access. This audio is
SYNTHETIC. It is only a smoke test and a rough benchmark. It says nothing
about how the recogniser does with real children's voices.
"""

import asyncio
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.numbers import to_english, to_hindi  # noqa: E402
from app.speech import COMMAND_WORDS  # noqa: E402

VOICES = {"hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"], "en": ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"]}
SMALL = {
    "hi": [0, 7, 9, 13, 24, 37, 48, 55, 59, 66, 72, 87, 99, 100, 135, 250, 506],
    "en": [3, 15, 29, 46, 58, 64, 77, 90, 100, 105, 142, 360],
}


def items(kind: str):
    for lang in ("hi", "en"):
        nums = SMALL[lang] if kind == "small" else (list(range(0, 100)) + list(range(100, 1000, 37)))
        for n in nums:
            yield lang, (to_hindi if lang == "hi" else to_english)(n), n, None
        for cmd, word in COMMAND_WORDS[lang].items():
            yield lang, word, None, cmd


async def main(out: str, kind: str) -> None:
    os.makedirs(out, exist_ok=True)
    import edge_tts
    manifest = []
    sem = asyncio.Semaphore(6)

    async def one(i, lang, text, value, cmd, voice):
        name = f"{lang}_{voice.split('-')[2][:3].lower()}_{i:03d}"
        async with sem:
            mp3 = os.path.join(out, name + ".mp3")
            await edge_tts.Communicate(text, voice).save(mp3)
        wav = os.path.join(out, name + ".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", wav], check=True)
        os.unlink(mp3)
        manifest.append({"file": name + ".wav", "lang": lang, "text": text, "value": value, "command": cmd})

    jobs = []
    for i, (lang, text, value, cmd) in enumerate(items(kind)):
        voice = VOICES[lang][i % 2] if kind == "small" else None
        for v in ([voice] if voice else VOICES[lang]):
            jobs.append(one(i, lang, text, value, cmd, v))
    await asyncio.gather(*jobs)
    manifest.sort(key=lambda m: m["file"])
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(len(manifest), "files in", out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "small"))
