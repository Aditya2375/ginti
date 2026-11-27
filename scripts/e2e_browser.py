"""Drive the real page in Chrome. Voice clips are played into the page's microphone path.

Usage: python scripts/e2e_browser.py CLIP_DIR [shots_dir]
Needs playwright and Google Chrome. The server must be running on :8000.
CLIP_DIR holds WAV files named <number>.wav (16 kHz mono) in the learner's language.
This checks the whole browser path (microphone stream, worklet, websocket, recogniser,
scoring, feedback). The clips are prerecorded, not live speech.
"""

import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

CLIPS = sys.argv[1]
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
LANG = os.environ.get("LANG_UNDER_TEST", "en")
LISTEN = {"en": "Listening", "hi": "सुन"}[LANG]

INIT = """
(() => {
  const ctx = new AudioContext();
  const dest = ctx.createMediaStreamDestination();
  window.__say = async (url) => {
    await ctx.resume();
    const buf = await ctx.decodeAudioData(await (await fetch(url)).arrayBuffer());
    const s = ctx.createBufferSource(); s.buffer = buf; s.connect(dest); s.start();
  };
  navigator.mediaDevices.getUserMedia = async () => dest.stream.clone();
})();
"""


def until(fn, timeout=30.0, what="condition"):
    """Poll with plain locator calls (the page's CSP forbids wait_for_function)."""
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return
        time.sleep(0.1)
    raise TimeoutError(what)


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required", "--no-sandbox"])
        ctx = b.new_context(viewport={"width": 900, "height": 800})
        page = ctx.new_page()
        page.add_init_script(INIT)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.route("**/clips/*.wav", lambda r: r.fulfill(
            path=os.path.join(CLIPS, os.path.basename(r.request.url)), content_type="audio/wav",
            headers={"Access-Control-Allow-Origin": "*"}))
        page.goto("http://localhost:8000/")
        page.fill("#nick", "E2E" + str(int(time.time()) % 10000))
        page.check(f"input[name=lang][value={LANG}]")
        page.click(".topic[data-topic=add]")
        right = wrong = 0
        for i in range(10):
            until(lambda: page.inner_text("#expr").strip() and page.inner_text("#status").startswith(LISTEN), what="question and mic")
            expr = page.inner_text("#expr")
            a, _, c = expr.split()
            want = int(a) + int(c)
            time.sleep(0.4)
            page.evaluate(f"window.__say('/clips/{want}.wav')")
            page.wait_for_selector("#feedback:not(.hidden)", timeout=30000)
            fb = page.inner_text("#feedback")
            ok = "ok" in page.get_attribute("#feedback", "class")
            right += ok
            wrong += not ok
            if SHOTS and i == 1:
                page.screenshot(path=os.path.join(SHOTS, "ask.png"))
            print(i, expr, "->", fb)
            until(lambda: "hidden" in page.get_attribute("#feedback", "class") or "hidden" not in page.get_attribute("#screen-done", "class"), what="next question")
        page.wait_for_selector("#screen-done:not(.hidden)", timeout=30000)
        print("round done:", page.inner_text("#done-body"), "| right", right, "wrong", wrong)
        if SHOTS:
            page.screenshot(path=os.path.join(SHOTS, "done.png"))
        print("page errors:", errors)
        b.close()


if __name__ == "__main__":
    main()
