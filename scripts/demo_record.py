"""Record one part of the demo video. Usage: python scripts/demo_record.py WORKDIR A|B

A: a Hindi round (one deliberately wrong answer).  B: an English round with the spoken commands
"repeat" and "skip", the typed fallback, then the teacher page.
WORKDIR/hi/<n>.wav, WORKDIR/en/<n>.wav and en/repeat.wav, en/skip.wav are SYNTHETIC clips (16 kHz mono)
played into the page's microphone path. WORKDIR/nar/*.mp3 are the narration clips.
The server must be running on :8000 with TEACHER_PIN=2468.
Writes WORKDIR/raw_<part>/*.webm and WORKDIR/cues_<part>.json.
"""

import json
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

W, PART = sys.argv[1], sys.argv[2]
LANG = "hi" if PART == "A" else "en"
LISTEN = "सुन" if LANG == "hi" else "Listening"
INIT = open(os.path.join(os.path.dirname(__file__), "e2e_browser.py")).read().split('INIT = """')[1].split('"""')[0]
TAG = """
() => {
  if (document.getElementById('__tag')) return;
  const b = document.createElement('div'); b.id = '__tag';
  Object.assign(b.style, {position:'fixed',top:'8px',left:'50%',transform:'translateX(-50%)',padding:'4px 10px',background:'#b3261e',
    color:'#fff',font:'600 14px system-ui,sans-serif',borderRadius:'6px',zIndex:99999});
  b.textContent = 'Synthetic voice. Not a real child.'; document.body.appendChild(b);
}
"""
# The recording machine has no emoji font, so swap emoji for plain marks.
EMOJI = """
new MutationObserver(() => { const w = document.createTreeWalker(document.body || document, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { const t = n.nodeValue.replace('\\u{1F3A4}', '\\u25CF').replace('\\u{1F389}', '').replace('\\u{1F50A}', '\\u25B6');
    if (t !== n.nodeValue) n.nodeValue = t; } }).observe(document, {subtree: true, childList: true, characterData: true});
"""


def dur(name):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{W}/nar/{name}.mp3"]))


cues, t0, last_end = [], [0.0], [0.0]


def now():
    return time.time() - t0[0]


def narrate(name, block=False):
    """Narration is mixed in afterwards so it need not pause the app. Cues never overlap each other."""
    t = max(now(), last_end[0] + 0.4)
    last_end[0] = t + dur(name)
    cues.append({"kind": "nar", "name": name, "t": round(t, 2)})
    if block:
        time.sleep(max(0, last_end[0] - now()) + 0.3)


def say(page, clip):
    cues.append({"kind": "ans", "name": clip, "t": round(now(), 2), "dir": LANG})
    page.evaluate(f"window.__say('/clips/{clip}.wav')")


def ready(page, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        if page.inner_text("#expr").strip() and LISTEN in page.inner_text("#status"):
            return page.inner_text("#expr").split()
        time.sleep(0.1)
    raise TimeoutError("question and microphone")


def feedback_done(page):
    try:
        page.wait_for_selector("#feedback:not(.hidden)", timeout=30000)
    except Exception:
        print("STUCK", page.inner_text("#status"), page.inner_text("#expr"), cues[-2:]); raise
    time.sleep(2.6)
    for _ in range(100):
        if "hidden" in page.get_attribute("#feedback", "class"):
            break
        time.sleep(0.1)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required", "--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=f"{W}/raw_{PART}",
                            record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page(); t0[0] = time.time()
        page.add_init_script(INIT); page.add_init_script(EMOJI)
        page.route("**/clips/*.wav", lambda r: r.fulfill(path=f"{W}/{LANG}/{os.path.basename(r.request.url)}",
                                                          content_type="audio/wav", headers={"Access-Control-Allow-Origin": "*"}))
        page.goto("http://localhost:8000/"); page.evaluate(TAG)
        if PART == "A":
            narrate("A1"); time.sleep(3)
            page.fill("#nick", "Asha"); page.check("input[name=lang][value=hi]"); time.sleep(1.2)
            page.click(".topic[data-topic=add]")
            for i in range(5):
                a, _, c = ready(page); want = int(a) + int(c)
                if i == 1: narrate("A3")
                if i == 3: narrate("A4")
                time.sleep(0.6)
                say(page, want + 1 if i == 3 else want)
                feedback_done(page)
        else:
            time.sleep(1)
            page.fill("#nick", "Ravi"); page.check("input[name=lang][value=en]"); time.sleep(1)
            page.click(".topic[data-topic=mul]")
            a, op, c = ready(page); narrate("B1"); time.sleep(0.8)
            say(page, "repeat"); time.sleep(2.5)
            a, op, c = ready(page, 45); time.sleep(0.6)
            say(page, int(a) * int(c)); feedback_done(page)
            a, op, c = ready(page); narrate("B2"); time.sleep(0.6)
            say(page, "skip"); feedback_done(page)    # shows the answer and moves on
            a, op, c = ready(page); time.sleep(0.6)
            say(page, int(a) * int(c)); feedback_done(page)
            a, op, c = ready(page); narrate("B3"); time.sleep(1.5)
            page.fill("#typed-in", str(int(a) * int(c))); page.click("#typed button[type=submit]"); feedback_done(page)
            page.goto("http://localhost:8000/teacher"); page.evaluate(TAG)
            narrate("B4", block=True)
            page.fill("#pin", "2468"); page.keyboard.press("Enter")
            page.wait_for_selector("#board:not(.hidden)", timeout=10000)
            time.sleep(4)
        end = now()
        ctx.close(); b.close()
    json.dump({"cues": cues, "end": end}, open(f"{W}/cues_{PART}.json", "w"), indent=1)
    print(PART, "cues", len(cues), "end", round(end, 1))


if __name__ == "__main__":
    main()
