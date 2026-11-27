"""Download the two speech models and check them against pinned hashes.

Usage: python scripts/fetch_models.py DEST_DIR

Both models are Apache 2.0, from https://alphacephei.com/vosk/models.
"""

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile

BASE = "https://alphacephei.com/vosk/models/"
MODELS = {
    "vosk-model-small-hi-0.22": "7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48",
    "vosk-model-small-en-in-0.4": "20663dcac4d5cb783a579c54d98339344a688e4ec6e1b4a4b059fd1235454cc7",
}


def fetch(name: str, sha256: str, dest: str) -> None:
    target = os.path.join(dest, name)
    if os.path.isdir(target):
        print(f"{name}: already there")
        return
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        path = tmp.name
    try:
        urllib.request.urlretrieve(BASE + name + ".zip", path)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest() != sha256:
            raise SystemExit(f"{name}: hash mismatch, refusing to use it")
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if member.startswith("/") or ".." in member.split("/"):
                    raise SystemExit(f"{name}: unsafe path in archive")
            z.extractall(dest)
    finally:
        os.unlink(path)
    print(f"{name}: installed")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "models"
    os.makedirs(out, exist_ok=True)
    for n, s in MODELS.items():
        fetch(n, s, out)
