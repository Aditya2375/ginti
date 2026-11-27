"""SQLite storage. Nicknames and answers only: no audio, no names, no contacts."""

from __future__ import annotations

import re
import sqlite3
import threading
import time

from .engine import MAX_LEVEL, TOPICS, update_box, update_level

NICK_RE = re.compile(r"^[\w\u0900-\u097F][\w\u0900-\u097F .'-]{0,23}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS learners(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname TEXT NOT NULL UNIQUE COLLATE NOCASE,
  lang TEXT NOT NULL CHECK(lang IN ('hi','en')),
  created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS progress(
  learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
  topic TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
  streak INTEGER NOT NULL DEFAULT 0, misses INTEGER NOT NULL DEFAULT 0,
  served INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(learner_id, topic));
CREATE TABLE IF NOT EXISTS boxes(
  learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
  fact TEXT NOT NULL, box INTEGER NOT NULL, last_served INTEGER NOT NULL,
  PRIMARY KEY(learner_id, fact));
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
  ts REAL NOT NULL, topic TEXT NOT NULL, fact TEXT NOT NULL,
  expected INTEGER NOT NULL, heard INTEGER, correct INTEGER NOT NULL,
  ms INTEGER, mode TEXT NOT NULL, skipped INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS attempts_learner ON attempts(learner_id, ts);
"""


class BadNickname(ValueError):
    pass


class Store:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.execute("PRAGMA foreign_keys=ON")
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def learner(self, nickname: str, lang: str) -> dict:
        nick = nickname.strip()
        if not NICK_RE.match(nick):
            raise BadNickname("nickname must be 1 to 24 letters, digits, spaces, dots, dashes or apostrophes")
        if lang not in ("hi", "en"):
            raise ValueError("lang must be hi or en")
        with self._lock:
            row = self._db.execute("SELECT * FROM learners WHERE nickname=?", (nick,)).fetchone()
            if row is None:
                cur = self._db.execute(
                    "INSERT INTO learners(nickname,lang,created) VALUES(?,?,?)", (nick, lang, time.time()))
                lid = cur.lastrowid
                for t in TOPICS:
                    self._db.execute("INSERT INTO progress(learner_id,topic) VALUES(?,?)", (lid, t))
                row = self._db.execute("SELECT * FROM learners WHERE id=?", (lid,)).fetchone()
            return dict(row)

    def get_learner(self, lid: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM learners WHERE id=?", (lid,)).fetchone()
            return dict(row) if row else None

    def progress(self, lid: int, topic: str) -> dict:
        """For mix, uses the lowest level of the three real topics."""
        with self._lock:
            if topic == "mix":
                rows = self._db.execute(
                    "SELECT * FROM progress WHERE learner_id=? AND topic IN ('add','sub','mul')", (lid,)).fetchall()
                return {"level": min(r["level"] for r in rows), "streak": 0, "misses": 0,
                        "served": self._served_total(lid)}
            d = dict(self._db.execute(
                "SELECT level,streak,misses,served FROM progress WHERE learner_id=? AND topic=?",
                (lid, topic)).fetchone())
            d["served"] = self._served_total(lid)       # one counter for every topic, so mix and single topics agree
            return d

    def _served_total(self, lid: int) -> int:
        return self._db.execute("SELECT COALESCE(SUM(served),0) FROM progress WHERE learner_id=?", (lid,)).fetchone()[0]

    def boxes(self, lid: int) -> dict[str, dict]:
        with self._lock:
            rows = self._db.execute("SELECT fact,box,last_served FROM boxes WHERE learner_id=?", (lid,)).fetchall()
            return {r["fact"]: {"box": r["box"], "last_served": r["last_served"]} for r in rows}

    def record(self, lid: int, topic: str, fact: str, expected: int, heard: int | None,
               correct: bool, ms: int | None, mode: str, skipped: bool = False) -> dict:
        """Store one attempt and move the learner's box and level. Returns the new level."""
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._db.execute(
                    "INSERT INTO attempts(learner_id,ts,topic,fact,expected,heard,correct,ms,mode,skipped)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (lid, time.time(), topic, fact, expected, heard, int(correct), ms, mode, int(skipped)))
                p = self._db.execute("SELECT * FROM progress WHERE learner_id=? AND topic=?", (lid, topic)).fetchone()
                served = p["served"] + 1
                total = self._served_total(lid) + 1          # box timing uses the all-topic counter
                b = self._db.execute("SELECT box FROM boxes WHERE learner_id=? AND fact=?", (lid, fact)).fetchone()
                self._db.execute(
                    "INSERT INTO boxes(learner_id,fact,box,last_served) VALUES(?,?,?,?)"
                    " ON CONFLICT(learner_id,fact) DO UPDATE SET box=excluded.box,last_served=excluded.last_served",
                    (lid, fact, update_box(b["box"] if b else 0, correct), total))
                if skipped:
                    level, streak, misses = p["level"], 0, p["misses"]   # a skip does not lower the level
                else:
                    level, streak, misses = update_level(p["level"], p["streak"], p["misses"], correct)
                self._db.execute(
                    "UPDATE progress SET level=?,streak=?,misses=?,served=? WHERE learner_id=? AND topic=?",
                    (level, streak, misses, served, lid, topic))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return {"level": level, "leveled_up": level > p["level"], "leveled_down": level < p["level"],
                    "served": served, "streak": streak, "max_level": MAX_LEVEL}

    def teacher_summary(self) -> list[dict]:
        with self._lock:
            out = []
            for l in self._db.execute("SELECT * FROM learners ORDER BY nickname").fetchall():
                lid = l["id"]
                att = self._db.execute(
                    "SELECT correct,ms,skipped FROM attempts WHERE learner_id=? ORDER BY id DESC LIMIT 20", (lid,)).fetchall()
                total = self._db.execute(
                    "SELECT count(*) c, sum(correct) k, max(ts) last FROM attempts WHERE learner_id=?", (lid,)).fetchone()
                times = [a["ms"] for a in att if a["ms"] is not None and a["correct"]]
                weak = self._db.execute(
                    "SELECT fact, count(*) tries, sum(1-correct) misses FROM attempts WHERE learner_id=? AND skipped=0"
                    " GROUP BY fact HAVING misses>0 ORDER BY misses DESC, tries ASC, fact LIMIT 5", (lid,)).fetchall()
                lv = {r["topic"]: r["level"] for r in self._db.execute(
                    "SELECT topic,level FROM progress WHERE learner_id=?", (lid,)).fetchall()}
                recent_ok = sum(a["correct"] for a in att)
                out.append({
                    "nickname": l["nickname"], "lang": l["lang"], "attempts": total["c"],
                    "correct": total["k"] or 0, "last_seen": total["last"],
                    "recent_accuracy": round(recent_ok / len(att), 2) if att else None,
                    "median_ms_correct": sorted(times)[len(times) // 2] if times else None,
                    "levels": lv,
                    "weak_facts": [{"fact": w["fact"], "tries": w["tries"], "misses": w["misses"]} for w in weak],
                })
            return out

    def export_rows(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT l.nickname, a.ts, a.topic, a.fact, a.expected, a.heard, a.correct, a.ms, a.mode, a.skipped"
                " FROM attempts a JOIN learners l ON l.id=a.learner_id ORDER BY a.id").fetchall()
            return [dict(r) for r in rows]

    def delete_learner(self, nickname: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM learners WHERE nickname=?", (nickname.strip(),))
            return cur.rowcount > 0
