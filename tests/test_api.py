import io
import json
import os
import wave

import pytest
from fastapi.testclient import TestClient

from app.main import Settings, create_app
from app.speech import Heard
from conftest import MODELS, needs_models


class FakeEngine:
    def available(self, lang):
        return True

    def recognise_pcm(self, pcm, lang, lo, hi):
        return Heard("fifty five", 55, None)

    def session(self, lang, lo, hi):

        class S:
            def feed(self, b):
                return {"type": "final", "text": "fifty five", "value": 55, "command": None} if len(b) >= 3200 else None

            def finish(self):
                return Heard("", None, None)
        return S()


@pytest.fixture
def client(tmp_path):
    s = Settings()
    s.db_path = str(tmp_path / "t.db")
    s.teacher_pin = "424242"
    return TestClient(create_app(s, FakeEngine()))


def make(client, nick="Asha", lang="en"):
    r = client.post("/api/learners", json={"nickname": nick, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert client.get("/").status_code == 200 and client.get("/teacher").status_code == 200
    assert client.get("/openapi.json").status_code == 404 and client.get("/docs").status_code == 404


def test_full_question_cycle_and_answer_is_not_leaked(client):
    l = make(client)
    q = client.post("/api/question", json={"learner_id": l["id"], "topic": "add"}).json()
    assert "answer" not in q and "expected" not in q and q["lo"] == 0 and q["hi"] in (20, 50, 100)
    a, op, b = q["display"].split()
    want = int(a) + int(b)
    r = client.post("/api/answer", json={"learner_id": l["id"], "qid": q["qid"], "text": str(want), "ms": 1500, "mode": "typed"}).json()
    assert r["correct"] and r["expected"] == want and r["served"] == 1
    again = client.post("/api/answer", json={"learner_id": l["id"], "qid": q["qid"], "text": str(want)})
    assert again.status_code == 404          # a question can be answered once


def test_wrong_and_unparsed_answers_are_wrong(client):
    l = make(client)
    q = client.post("/api/question", json={"learner_id": l["id"], "topic": "mul"}).json()
    r = client.post("/api/answer", json={"learner_id": l["id"], "qid": q["qid"], "text": "banana"}).json()
    assert r["correct"] is False and r["heard"] is None


def test_cannot_answer_for_someone_else(client):
    a, b = make(client, "Asha"), make(client, "Ravi")
    q = client.post("/api/question", json={"learner_id": a["id"], "topic": "add"}).json()
    r = client.post("/api/answer", json={"learner_id": b["id"], "qid": q["qid"], "text": "1"})
    assert r.status_code == 404


def test_skip(client):
    l = make(client)
    q = client.post("/api/question", json={"learner_id": l["id"], "topic": "sub"}).json()
    r = client.post("/api/skip", json={"learner_id": l["id"], "qid": q["qid"]}).json()
    assert "expected" in r and r["served"] == 1


@pytest.mark.parametrize("bad", [{"nickname": "", "lang": "hi"}, {"nickname": "a<b", "lang": "hi"},
                                 {"nickname": "ok", "lang": "fr"}, {"nickname": "x" * 30, "lang": "en"}, {}])
def test_bad_learner_input(client, bad):
    assert client.post("/api/learners", json=bad).status_code == 422


def test_bad_question_and_answer_input(client):
    l = make(client)
    assert client.post("/api/question", json={"learner_id": l["id"], "topic": "pow"}).status_code == 422
    assert client.post("/api/question", json={"learner_id": 9999, "topic": "add"}).status_code == 404
    assert client.post("/api/answer", json={"learner_id": l["id"], "qid": "zzzz"}).status_code == 404
    assert client.post("/api/answer", json={"learner_id": l["id"], "qid": "zzzz", "text": "x" * 500}).status_code == 422
    assert client.post("/api/answer", json={"learner_id": l["id"], "qid": "zzzz", "ms": -5}).status_code == 422


def wav_bytes(seconds=1.0, rate=16000, ch=1):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * seconds) * ch)
    return b.getvalue()


def test_recognise_upload_checks_input(client):
    ok = client.post("/api/recognise?lang=en&lo=0&hi=100", content=wav_bytes())
    assert ok.status_code == 200 and ok.json()["value"] == 55
    assert client.post("/api/recognise?lang=fr", content=wav_bytes()).status_code == 422
    assert client.post("/api/recognise?lang=en&lo=50&hi=5", content=wav_bytes()).status_code == 422
    assert client.post("/api/recognise?lang=en", content=b"not a wav").status_code == 415
    assert client.post("/api/recognise?lang=en", content=wav_bytes(rate=44100)).status_code == 415
    assert client.post("/api/recognise?lang=en", content=wav_bytes(ch=2)).status_code == 415
    assert client.post("/api/recognise?lang=en", content=wav_bytes(seconds=13)).status_code == 413
    assert client.post("/api/recognise?lang=en", content=b"0" * (3 * 1024 * 1024)).status_code == 413


def test_websocket_flow_and_limits(client):
    with client.websocket_connect("/ws/listen") as ws:
        ws.send_json({"lang": "en", "lo": 0, "hi": 100})
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(b"\0" * 3200)
        m = ws.receive_json()
        assert m["type"] == "final" and m["value"] == 55
    with client.websocket_connect("/ws/listen") as ws:
        ws.send_json({"lang": "xx", "lo": 0, "hi": 100})
        assert ws.receive_json()["type"] == "error"
    with client.websocket_connect("/ws/listen") as ws:
        ws.send_json({"lang": "en", "lo": 0, "hi": 100})
        ws.receive_json()
        ws.send_bytes(b"\0" * 3)            # odd byte count is not 16-bit audio
        assert ws.receive_json()["type"] == "error"
    with client.websocket_connect("/ws/listen") as ws:
        ws.send_json({"lang": "en", "lo": 0, "hi": 100})
        ws.receive_json()
        ws.send_json({"type": "stop"})
        assert ws.receive_json()["type"] == "final"


def test_websocket_refuses_other_origins(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/listen", headers={"origin": "http://evil.example"}) as ws:
            ws.send_json({"lang": "en", "lo": 0, "hi": 100})
            ws.receive_json()


def test_teacher_needs_pin_and_locks_out(client):
    l = make(client, "Meena")
    q = client.post("/api/question", json={"learner_id": l["id"], "topic": "add"}).json()
    client.post("/api/answer", json={"learner_id": l["id"], "qid": q["qid"], "text": "0"})
    assert client.get("/api/teacher/summary").status_code == 401
    ok = client.get("/api/teacher/summary", headers={"X-Teacher-Pin": "424242"})
    assert ok.status_code == 200 and ok.json()["learners"][0]["nickname"] == "Meena"
    csvr = client.get("/api/teacher/export.csv", headers={"X-Teacher-Pin": "424242"})
    assert csvr.headers["content-type"].startswith("text/csv") and "Meena" in csvr.text
    for _ in range(9):
        client.get("/api/teacher/summary", headers={"X-Teacher-Pin": "nope"})
    assert client.get("/api/teacher/summary", headers={"X-Teacher-Pin": "424242"}).status_code == 429


def test_teacher_delete(client):
    make(client, "Gone")
    h = {"X-Teacher-Pin": "424242"}
    assert client.delete("/api/teacher/learner/Gone").status_code == 401
    assert client.delete("/api/teacher/learner/Gone", headers=h).status_code == 200
    assert client.delete("/api/teacher/learner/Gone", headers=h).status_code == 404


def test_csv_does_not_turn_a_name_into_a_formula():
    from app.main import _csv_safe
    assert _csv_safe("=1+1") == "'=1+1" and _csv_safe("Asha") == "Asha" and _csv_safe("@x") == "'@x"


def test_generated_pin_when_unset(monkeypatch):
    monkeypatch.delenv("TEACHER_PIN", raising=False)
    s = Settings()
    assert s.pin_generated and len(s.teacher_pin) == 6
    monkeypatch.setenv("TEACHER_PIN", "777")
    assert not Settings().pin_generated


@needs_models
def test_real_model_over_http_and_websocket(tmp_path):
    s = Settings()
    s.db_path = str(tmp_path / "r.db"); s.model_dir = MODELS; s.teacher_pin = "1"
    c = TestClient(create_app(s))
    assert c.get("/api/health").json()["speech"] == {"hi": True, "en": True}
    fx = os.path.join(os.path.dirname(__file__), "fixtures")
    manifest = json.load(open(os.path.join(fx, "manifest.json"), encoding="utf-8"))
    m = next(x for x in manifest if x["lang"] == "en" and x["value"] == 58)
    raw = open(os.path.join(fx, m["file"]), "rb").read()
    r = c.post("/api/recognise?lang=en&lo=0&hi=100", content=raw)
    assert r.status_code == 200 and r.json()["value"] == 58
    with wave.open(os.path.join(fx, m["file"])) as w:
        pcm = w.readframes(w.getnframes())
    with c.websocket_connect("/ws/listen") as ws:
        ws.send_json({"lang": "en", "lo": 0, "hi": 100})
        assert ws.receive_json()["type"] == "ready"
        got = None
        for i in range(0, len(pcm), 3200):
            ws.send_bytes(pcm[i:i + 3200])
        ws.send_bytes(b"\0" * 32000)
        while got is None:
            msg = ws.receive_json()
            if msg["type"] == "final":
                got = msg
        assert got["value"] == 58


def test_one_learner_cannot_crowd_out_others(client):
    a, b = make(client, "Asha"), make(client, "Binu")
    first_b = client.post("/api/question", json={"learner_id": b["id"], "topic": "add"}).json()
    for _ in range(10):
        client.post("/api/question", json={"learner_id": a["id"], "topic": "add"})
    r = client.post("/api/answer", json={"learner_id": b["id"], "qid": first_b["qid"], "text": "5"})
    assert r.status_code == 200, "Binu's open question must survive Asha asking many"


def test_question_and_learner_rate_limits(client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "RATE", {**m.RATE, "question": 40, "learners": 10})
    l = make(client)
    codes = [client.post("/api/question", json={"learner_id": l["id"], "topic": "add"}).status_code for _ in range(60)]
    assert codes.count(429) >= 1 and codes[0] == 200
    codes = [client.post("/api/learners", json={"nickname": f"kid{i}", "lang": "en"}).status_code for i in range(20)]
    assert 429 in codes


def test_a_shared_proxy_address_is_split_by_forwarded_for(tmp_path, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "TRUSTED_PROXY", True)
    monkeypatch.setattr(m, "RATE", {**m.RATE, "learners": 3})
    s = Settings(); s.db_path = str(tmp_path / "p.db"); s.teacher_pin = "1"
    c = TestClient(create_app(s, FakeEngine()))
    for i in range(6):   # six different clients behind one proxy, each within its own limit
        r = c.post("/api/learners", json={"nickname": f"k{i}", "lang": "en"}, headers={"x-forwarded-for": f"10.0.0.{i}"})
        assert r.status_code == 200


def test_bad_websocket_settings_close_cleanly(client):
    for bad in ("null", "5", "[1]", '{"lang":"en","lo":1e999}', '{"lang":"en","lo":true,"hi":5}'):
        with client.websocket_connect("/ws/listen") as w:
            w.send_text(bad)
            assert w.receive_json()["type"] == "error"


def test_language_is_not_changed_by_a_later_login(client):
    make(client, "Asha", "hi")
    assert make(client, "Asha", "en")["lang"] == "hi"


def test_websocket_cap_per_address(client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "MAX_SOCKETS_PER_IP", 2)
    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect("/ws/listen") as w1, client.websocket_connect("/ws/listen") as w2:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/listen") as w3:
                w3.receive_text()


def test_oversized_audio_is_refused_from_the_header(client):
    r = client.post("/api/recognise?lang=en", content=b"\0" * (2 * 1024 * 1024 + 10))
    assert r.status_code == 413
