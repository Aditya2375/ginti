"""Make the narration clips: python scripts/demo_narrate.py WORKDIR   (needs edge-tts and network)."""
import asyncio
import os
import sys

import edge_tts

sys.path.insert(0, os.path.dirname(__file__))
from demo_texts import TEXTS  # noqa: E402

W = sys.argv[1]
os.makedirs(f"{W}/nar", exist_ok=True)


async def go():
    for k, (spoken, _) in TEXTS.items():
        for _ in range(4):
            try:
                await edge_tts.Communicate(spoken, "en-IN-NeerjaNeural").save(f"{W}/nar/{k}.mp3")
                break
            except Exception:
                await asyncio.sleep(1)
        print(k, os.path.getsize(f"{W}/nar/{k}.mp3"))


asyncio.run(go())
