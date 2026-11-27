"""Record the demo video's screen and audio timeline. Usage: python scripts/demo_record.py WORKDIR

WORKDIR/hi/<number>.wav  Hindi answer clips (SYNTHETIC voice, 16 kHz mono)
WORKDIR/nar/N<k>.mp3     narration clips; WORKDIR/nar/durations.json maps name -> seconds
Server must be running on :8000 with TEACHER_PIN=2468.
Writes WORKDIR/raw/*.webm and WORKDIR/cues.json (start time of each narration/answer clip).
The child's voice in the video is synthetic and the video says so on screen.
"""

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

W = sys.argv[1]
DUR = json.load(open(f"{W}/nar/durations.json"))
INIT = open(os.path.join(os.path.dirname(__file__), "e2e_browser.py")).read().split('INIT = """')[1].split('"""')[0]
CAPTION_JS = """
(t) => {
  if (!document.getElementById('__tag')) {
    let b = document.createElement('div'); b.id='__tag';
    Object.assign(b.style,{position:'fixed',top:'8px',left:'50%',transform:'translateX(-50%)',padding:'4px 10px',background:'#b3261e',color:'#fff',
      font:'600 14px system-ui,sans-serif',borderRadius:'6px',zIndex:99999});
    b.textContent='Synthetic voice. Not a real child.'; document.body.appendChild(b); }
}
"""
cues, t0, last_end = [], [0.0], [0.0]
CAPTIONS = {}


def now():
    return time.time() - t0[0]


def narrate(page, name, caption, block=False):
    """Narration is mixed in afterwards, so it need not pause the app (which stops listening
    after a few seconds). Cues never overlap each other."""
    t = max(now(), last_end[0] + 0.4)
    last_end[0] = t + DUR[name]
    cues.append({"kind": "nar", "name": name, "t": round(t, 2), "caption": caption})
    if block:
        time.sleep(max(0, last_end[0] - now()) + 0.3)


def say(page, n):
    cues.append({"kind": "ans", "name": f"{n}", "t": round(now(), 2)})
    page.evaluate(f"window.__say('/clips/{n}.wav')")


def main():
    os.makedirs(f"{W}/raw", exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required", "--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=f"{W}/raw",
                            record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page(); t0[0] = time.time()
        page.add_init_script(INIT)
        # The recording machine has no emoji font, so they would show as empty boxes. Swap them for plain marks.
        page.add_init_script("""
          new MutationObserver(() => { const w = document.createTreeWalker(document.body || document, NodeFilter.SHOW_TEXT);
            let n; while ((n = w.nextNode())) { const t = n.nodeValue.replace('\\u{1F3A4}', '\\u25CF').replace('\\u{1F389}', '').replace('\\u{1F50A}', '\\u25B6');
              if (t !== n.nodeValue) n.nodeValue = t; } }).observe(document, {subtree: true, childList: true, characterData: true});
        """)
        page.route("**/clips/*.wav", lambda r: r.fulfill(path=f"{W}/hi/{os.path.basename(r.request.url)}",
                                                          content_type="audio/wav", headers={"Access-Control-Allow-Origin": "*"}))
        page.goto("http://localhost:8000/"); page.evaluate(CAPTION_JS, ""); time.sleep(1)
        narrate(page, "N1", "Ginti: maths practice you answer out loud, in Hindi or English. Typing is only a fallback. Each sum is shown and read aloud, and the microphone is already listening. These voices are synthetic.")
        time.sleep(3)
        page.fill("#nick", "Asha")
        page.check("input[name=lang][value=hi]")
        time.sleep(1.5)
        page.click(".topic[data-topic=add]")
        for i in range(5):
            for _ in range(300):
                if page.inner_text("#expr").strip() and "सुन" in page.inner_text("#status"):
                    break
                time.sleep(0.1)
            a, _, c = page.inner_text("#expr").split()
            want = int(a) + int(c)
            print("q", i, a, c, page.inner_text("#status"), flush=True)
            if i == 1:
                narrate(page, "N3", "Offline speech recognition (Vosk) listens only for answer words that fit this sum.")
            if i == 3:
                narrate(page, "N4", "A wrong answer shows the right one. That fact comes back sooner.")
            time.sleep(0.6)
            say(page, want + 1 if i == 3 else want)
            page.wait_for_selector("#feedback:not(.hidden)", timeout=30000)
            time.sleep(2.8)
            for _ in range(100):
                if "hidden" in page.get_attribute("#feedback", "class"):
                    break
                time.sleep(0.1)
        page.goto("http://localhost:8000/teacher"); page.evaluate(CAPTION_JS, ""); time.sleep(1)
        narrate(page, "N6", "The teacher page needs a PIN.")
        page.fill("#pin", "2468"); page.keyboard.press("Enter")
        page.wait_for_selector("#board:not(.hidden)", timeout=10000)
        narrate(page, "N7", "It shows accuracy, speed, level and the facts a child keeps missing. CSV export is built in.", block=True)
        end = now()
        ctx.close(); b.close()
    json.dump({"cues": cues, "end": end}, open(f"{W}/cues.json", "w"), indent=1)
    print("cues", len(cues), "end", end)


if __name__ == "__main__":
    main()
