# Ginti · गिनती

Maths practice you do by talking. The app reads a sum aloud, the child says the answer in Hindi or English, and the app says whether it was right. The child speaks the answer; typing is only a fallback. There is no password and no account.

Meant for children who can say an answer before they can type it, on whatever device a classroom has. Not yet tried on one.

```
docker compose up
```

Then open http://localhost:8000. No API keys and no `.env` file are needed, and nothing is sent to an outside service. The port is bound to this machine only; to use it from other devices see [SECURITY.md](SECURITY.md).

## What it does

- **Say the answer.** Tap the microphone, say "पचपन" or "fifty five". The app shows what it heard for two and a half seconds so the child can say "नहीं, फिर से बोलो" before it counts.
- **Hindi or English.** Hindi number words from 1 to 99 are mostly irregular ("उनहत्तर", "अट्ठासी"), so the app uses a written-out table for them instead of a rule.
- **Adaptive.** Addition, subtraction and times tables, four levels each. A fact answered wrong comes back soon; one answered right comes back later. Five right in a row moves up a level, three misses in a row move down.
- **Spoken commands.** "दोबारा" / "repeat" hears the question again. "छोड़ो" / "skip" moves on.
- **Teacher view** at `/teacher`: for each learner, recent accuracy, median time on right answers, level per topic, and the facts they keep missing (for example "7x8, missed 3 of 4"). CSV export, and a delete button per learner.
- **Typing still works** for a child who is somewhere noisy.

## How it works

1. The browser captures the microphone, turns it into 16 kHz mono audio and streams it over a WebSocket.
2. The server decodes it with [Vosk](https://alphacephei.com/vosk/), an open-source offline speech recogniser, using its small Hindi and Indian-English models.
3. For each question the recogniser is **limited to the words needed to say a plausible answer**, plus the two commands. For "3 + 4" it can only hear numbers up to 20, so "सात" cannot turn into "साठ" (60). This is what lets a small model do well on short answers.
4. What it heard goes through a number parser (Devanagari, Roman Hindi, English words, digits). Input that is not a clean number, like "seven eight", or that has an unrecognised sound in the middle, is treated as not heard. The recogniser can still mishear a clean word as another valid number, and the app cannot tell. That is why the heard number is shown first.
5. The server holds the correct answer and does the scoring, so the browser cannot mark itself right. A skipped question does reveal its answer, on purpose.

Audio is kept in memory for one answer and then dropped. The database holds a nickname, answers and timings, nothing else.

## How well does it hear? (measured, and what that does not tell you)

`scripts/bench_asr.py` runs 508 clips made with neural text-to-speech voices (two voices per language): numbers 0 to 99, every 37th number from 100 to 999, and the two commands. Each clip is decoded under every answer band the app can really assign to a question with that answer. Bands come from the app's own question generator, not from the answer, so a clip such as "सात" is also tested in the wide 0 to 100 and 0 to 1000 bands. That gives 1,208 clip and band results:

| | 0 to 99 | 100 to 999 | commands |
|---|---|---|---|
| Hindi | 532 / 536 | 52 / 56 | 12 / 12 |
| English | 533 / 536 | 56 / 56 | 12 / 12 |

Total 1,197 of 1,208 (99.1%). Speed, one measured run on a single decoding process: 1,208 decodes, 2,337 seconds of audio, 33.7 seconds, about 69 times faster than real time.

What this does not tell you:

- The voices are synthetic: clean, even and adult. Nothing here has been tested with a child, a phone microphone, a classroom or background noise. It checks that the number tables, the answer-range limit and the audio path work.
- `scripts/stress_asr.py` re-runs the 33 repo fixture clips (80 clip and band results) with a crude pitch rise and added noise. Clean 77/80, pitch +40% 65/80, noise at 10 dB 73/80, noise at 0 dB 56/80. Real children and rooms will be harder than this, not easier to predict.
- Hindi is weaker in the wide bands. "सात" (7) is heard as "साठ" (60) when the band is 0 to 100 or wider, in both Hindi voices. That is real: a subtraction like 98 - 91 gets that wide band. The recogniser also sometimes drops "सौ" ("पाँच सौ चौवालीस" heard as "पाँच चौवालीस").
- If the recogniser cuts an answer short, for example "sixty four" heard as "sixty", the result is still a valid number and the app marks it by what it got.

## Limits you should know about

- Chrome and Edge need `localhost` or HTTPS for the microphone. On a school network that means putting a TLS proxy in front. See [SECURITY.md](SECURITY.md).
- Reading the question aloud uses the device's own text-to-speech voice. If a phone has no Hindi voice, the question is only on the screen. This has not been checked on real phones.
- No real accounts. A nickname is the login, so anyone can practise as someone else's nickname. The teacher page has a PIN.
- Answers are whole numbers up to 9,999. Addition, subtraction and multiplication only. No division, fractions or word problems.
- One server process. At most 8 microphone sessions at once, 3 per address, 15 seconds each, SQLite on a Docker volume, no backup. Behind a reverse proxy every device looks like one address unless you set `GINTI_TRUSTED_PROXY=1` and have the proxy set `X-Forwarded-For`; see [SECURITY.md](SECURITY.md).
- The audio can be wrong. A child can be marked wrong because the app misheard. That is why the heard number is shown first and the redo button exists.

## Run the tests

```
pip install -r requirements-dev.txt
python scripts/fetch_models.py models
GINTI_MODEL_DIR=models python -m pytest -q tests
```

88 tests: number round trips for 0 to 9,999 in both languages, the question engine, the database, every API route including bad input and the PIN lockout, and recognition of recorded fixtures. Tests that need the speech models skip themselves if the models are missing.

`scripts/e2e_browser.py` drives the real page in Chrome and plays prerecorded clips into its microphone path, so the whole chain (stream, worklet, WebSocket, recogniser, scoring, feedback) is exercised. One 10-question round with synthetic English clips scored 10 of 10 in the last run. Those clips are recorded, not live speech.

CI runs `docker compose up --build --wait` and then `scripts/smoke.py` against the running container.

## Layout

```
app/numbers.py   Hindi, Roman Hindi and English numbers in both directions
app/speech.py    Vosk wrapper, per-question grammar, spoken commands
app/engine.py    question choice, difficulty, spaced repetition
app/store.py     SQLite: learners, attempts, boxes, levels
app/main.py      HTTP API, WebSocket, security headers, teacher routes
app/static/      the pages (plain HTML, CSS and JavaScript, no build step)
scripts/         model download, test-audio maker, benchmark, stress check, smoke test, browser run, demo recorder
```

## How it was built

Written from scratch on 27 November 2026 for this hackathon, by one person. The repository started private, so the first public history is short: the first commit holds most of the app (server, speech, engine, pages) and the following commits are fixes made after review rounds: front end races, security limits, honest benchmark, docs and the deck. The commit times are the real times. Models are third party (Vosk, Apache 2.0) and are downloaded at build time, not part of the code.

## Licence

MIT, see [LICENSE](LICENSE). The two speech models are Apache 2.0, from the Vosk project: https://alphacephei.com/vosk/models
