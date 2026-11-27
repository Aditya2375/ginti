import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODELS = os.environ.get("GINTI_MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "models"))


def models_present() -> bool:
    return all(os.path.isdir(os.path.join(MODELS, n)) for n in ("vosk-model-small-hi-0.22", "vosk-model-small-en-in-0.4"))


needs_models = pytest.mark.skipif(not models_present(), reason="speech models not installed (run scripts/fetch_models.py models)")
