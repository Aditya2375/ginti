"""Ginti web app: HTTP API, a speech WebSocket, and the static pages."""

from __future__ import annotations

import asyncio
import csv
import hmac
import io
import json
import logging
import os
import secrets
import time
import wave
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .engine import TOPICS, Picker, Question
from .numbers import parse_number
from .speech import MAX_UTTERANCE_SECONDS, SAMPLE_RATE, Engine, ModelMissing
from .store import BadNickname, Store

log = logging.getLogger("ginti")
STATIC = Path(__file__).parent / "static"
MAX_SOCKETS = 8
PENDING_TTL = 30 * 60
PENDING_MAX = 5000
FRAME_MAX = 64 * 1024
WAV_MAX = 2 * 1024 * 1024


class Settings:
    def __init__(self) -> None:
        self.db_path = os.environ.get("GINTI_DB", "/data/ginti.db")
        self.model_dir = os.environ.get("GINTI_MODEL_DIR", "/models")
        pin = os.environ.get("TEACHER_PIN", "").strip()
        self.pin_generated = not pin
        self.teacher_pin = pin or f"{secrets.randbelow(10**6):06d}"


class Learner(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)
    lang: str = Field(pattern="^(hi|en)$")


class QuestionReq(BaseModel):
    learner_id: int
    topic: str


class AnswerReq(BaseModel):
    learner_id: int
    qid: str = Field(min_length=4, max_length=32)
    text: str = Field(default="", max_length=80)
    ms: int | None = Field(default=None, ge=0, le=600000)
    mode: str = Field(default="voice", pattern="^(voice|typed)$")


class SkipReq(BaseModel):
    learner_id: int
    qid: str = Field(min_length=4, max_length=32)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    cfg = settings or Settings()
    app = FastAPI(title="Ginti", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    store = Store(cfg.db_path)
    speech = engine or Engine(cfg.model_dir)
    picker = Picker()
    pending: "OrderedDict[str, tuple[int, Question, float, float]]" = OrderedDict()
    fails: dict[str, deque] = defaultdict(deque)
    sockets = {"n": 0}

    if cfg.pin_generated:
        log.warning("TEACHER_PIN not set. Teacher PIN for this run: %s", cfg.teacher_pin)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; media-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------------------------------------------------------------- basics
    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__,
                "speech": {"hi": speech.available("hi"), "en": speech.available("en")}}

    @app.post("/api/learners")
    def learners(body: Learner):
        try:
            l = store.learner(body.nickname, body.lang)
        except BadNickname as e:
            raise HTTPException(422, str(e))
        return {"id": l["id"], "nickname": l["nickname"], "lang": l["lang"],
                "levels": {t: store.progress(l["id"], t)["level"] for t in TOPICS}}

    # -------------------------------------------------------------- practice
    def _learner(lid: int) -> dict:
        l = store.get_learner(lid)
        if l is None:
            raise HTTPException(404, "unknown learner")
        return l

    def _prune() -> None:
        now = time.time()
        while pending and (len(pending) > PENDING_MAX or next(iter(pending.values()))[2] < now - PENDING_TTL):
            pending.popitem(last=False)

    @app.post("/api/question")
    def question(body: QuestionReq):
        if body.topic not in TOPICS:
            raise HTTPException(422, "unknown topic")
        l = _learner(body.learner_id)
        p = store.progress(l["id"], body.topic)
        q = picker.next_question(body.topic, p["level"], store.boxes(l["id"]), p["served"])
        qid = secrets.token_urlsafe(9)
        _prune()
        pending[qid] = (l["id"], q, time.time(), 0.0)
        lo, hi = q.answer_range
        return {"qid": qid, "topic": q.topic, "display": q.display(), "prompt": q.prompt(l["lang"]),
                "lang": l["lang"], "lo": lo, "hi": hi, "level": q.level, "served": p["served"]}

    def _take(lid: int, qid: str) -> Question:
        item = pending.pop(qid, None)
        if item is None or item[0] != lid:
            raise HTTPException(404, "that question is no longer open")
        return item[1]

    @app.post("/api/answer")
    def answer(body: AnswerReq):
        l = _learner(body.learner_id)
        q = _take(l["id"], body.qid)
        heard = parse_number(body.text, l["lang"])
        correct = heard == q.answer
        res = store.record(l["id"], q.topic, q.key, q.answer, heard, correct, body.ms, body.mode)
        return {"correct": correct, "heard": heard, "expected": q.answer, **res}

    @app.post("/api/skip")
    def skip(body: SkipReq):
        l = _learner(body.learner_id)
        q = _take(l["id"], body.qid)
        res = store.record(l["id"], q.topic, q.key, q.answer, None, False, None, "voice", skipped=True)
        return {"expected": q.answer, **res}

    # ---------------------------------------------------------------- speech
    def _range(lo: int, hi: int) -> tuple[int, int]:
        if not (0 <= lo <= hi <= 9999):
            raise HTTPException(422, "bad answer range")
        return lo, hi

    @app.post("/api/recognise")
    async def recognise(request: Request, lang: str = "hi", lo: int = 0, hi: int = 100):
        """One short WAV (16 kHz, mono, 16-bit) in, one heard answer out."""
        if lang not in ("hi", "en"):
            raise HTTPException(422, "lang must be hi or en")
        lo, hi = _range(lo, hi)
        raw = await request.body()
        if len(raw) > WAV_MAX:
            raise HTTPException(413, "audio too large")
        try:
            with wave.open(io.BytesIO(raw)) as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
                    raise HTTPException(415, "send 16 kHz mono 16-bit WAV")
                if w.getnframes() > MAX_UTTERANCE_SECONDS * SAMPLE_RATE:
                    raise HTTPException(413, "audio too long")
                pcm = w.readframes(w.getnframes())
        except (wave.Error, EOFError):
            raise HTTPException(415, "not a WAV file")
        try:
            h = await run_in_threadpool(speech.recognise_pcm, pcm, lang, lo, hi)
        except ModelMissing:
            raise HTTPException(503, "speech model not installed")
        return {"text": h.text, "value": h.value, "command": h.command}

    @app.websocket("/ws/listen")
    async def listen(ws: WebSocket):
        if ws.headers.get("origin") and not _same_origin(ws):
            await ws.close(code=1008)
            return
        if sockets["n"] >= MAX_SOCKETS:
            await ws.close(code=1013)
            return
        await ws.accept()
        sockets["n"] += 1
        session = None
        try:
            cfgmsg = json.loads(await asyncio.wait_for(ws.receive_text(), 10))
            lang = cfgmsg.get("lang")
            lo, hi = int(cfgmsg.get("lo", 0)), int(cfgmsg.get("hi", 100))
            if lang not in ("hi", "en") or not (0 <= lo <= hi <= 9999):
                await ws.send_json({"type": "error", "message": "bad settings"})
                return
            try:
                session = await run_in_threadpool(speech.session, lang, lo, hi)
            except ModelMissing:
                await ws.send_json({"type": "error", "message": "speech model not installed"})
                return
            await ws.send_json({"type": "ready"})
            while True:
                msg = await asyncio.wait_for(ws.receive(), 20)
                if msg["type"] == "websocket.disconnect":
                    return
                if msg.get("bytes") is not None:
                    data = msg["bytes"]
                    if len(data) > FRAME_MAX or len(data) % 2:
                        await ws.send_json({"type": "error", "message": "bad audio frame"})
                        return
                    out = await run_in_threadpool(session.feed, data)
                    if out:
                        await ws.send_json(out)
                        if out["type"] == "final":
                            return
                elif msg.get("text") is not None:
                    if json.loads(msg["text"]).get("type") == "stop":
                        h = await run_in_threadpool(session.finish)
                        await ws.send_json({"type": "final", "text": h.text, "value": h.value, "command": h.command})
                        return
        except (WebSocketDisconnect, asyncio.TimeoutError, json.JSONDecodeError, ValueError, TypeError):
            pass
        except RuntimeError:
            pass
        finally:
            sockets["n"] -= 1
            try:
                await ws.close()
            except Exception:
                pass

    def _same_origin(ws: WebSocket) -> bool:
        origin = ws.headers.get("origin", "")
        host = ws.headers.get("host", "")
        return origin.split("://", 1)[-1] == host

    # --------------------------------------------------------------- teacher
    def _check_pin(request: Request) -> None:
        ip = request.client.host if request.client else "?"
        q = fails[ip]
        now = time.time()
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= 8:
            raise HTTPException(429, "too many wrong PINs, wait a minute")
        given = request.headers.get("x-teacher-pin", "")
        if not hmac.compare_digest(given.encode(), cfg.teacher_pin.encode()):
            q.append(now)
            raise HTTPException(401, "wrong PIN")

    @app.get("/api/teacher/summary")
    def teacher_summary(request: Request):
        _check_pin(request)
        return {"learners": store.teacher_summary()}

    @app.get("/api/teacher/export.csv")
    def teacher_export(request: Request):
        _check_pin(request)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["nickname", "time_unix", "topic", "fact", "expected", "heard", "correct", "ms", "mode", "skipped"])
        for r in store.export_rows():
            w.writerow([_csv_safe(r["nickname"]), round(r["ts"]), r["topic"], r["fact"], r["expected"],
                        "" if r["heard"] is None else r["heard"], r["correct"],
                        "" if r["ms"] is None else r["ms"], r["mode"], r["skipped"]])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=ginti-attempts.csv"})

    @app.delete("/api/teacher/learner/{nickname}")
    def teacher_delete(nickname: str, request: Request):
        _check_pin(request)
        if not store.delete_learner(nickname):
            raise HTTPException(404, "no such learner")
        return {"deleted": True}

    # ---------------------------------------------------------------- pages
    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/teacher")
    def teacher_page():
        return FileResponse(STATIC / "teacher.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.state.settings, app.state.store, app.state.speech = cfg, store, speech
    return app


def _csv_safe(s: str) -> str:
    """Stop a nickname like =1+1 turning into a spreadsheet formula."""
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def app_factory() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    return create_app()
