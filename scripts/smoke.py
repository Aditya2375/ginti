"""Check a running Ginti: health, one spoken answer in each language, one teacher call.

Usage: python scripts/smoke.py [BASE_URL]
Standard library only, so it runs on a bare CI machine.
"""

import json
import os
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FX = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")


def call(path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


health = call("/api/health")
assert health["ok"] and health["speech"] == {"hi": True, "en": True}, health
manifest = json.load(open(os.path.join(FX, "manifest.json"), encoding="utf-8"))
for lang, want in (("en", 58), ("hi", 55)):
    m = next(x for x in manifest if x["lang"] == lang and x["value"] == want)
    got = call(f"/api/recognise?lang={lang}&lo=0&hi=100", open(os.path.join(FX, m["file"]), "rb").read(),
               {"Content-Type": "audio/wav"})
    assert got["value"] == want, (lang, got)
    print(lang, "heard", got["text"], "->", got["value"])
learner = call("/api/learners", json.dumps({"nickname": "smoke", "lang": "en"}).encode(), {"Content-Type": "application/json"})
q = call("/api/question", json.dumps({"learner_id": learner["id"], "topic": "add"}).encode(), {"Content-Type": "application/json"})
assert q["display"] and q["prompt"] and "answer" not in q
print("question:", q["display"], "|", q["prompt"])
print("smoke ok")
