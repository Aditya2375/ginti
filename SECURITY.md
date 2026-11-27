# Security

Ginti is a prototype. It has no accounts, no passwords and no third-party calls, but it has not had an outside review.

What it does to stay safe:

- Speech is decoded on the server. Audio is held in memory for one utterance (12 seconds at most) and never written to disk or sent anywhere else. A microphone socket lives at most 15 seconds, with at most 8 in total and 3 per address.
- The database stores a nickname, answers and timings. No audio, no real names, no contact details.
- The teacher page and CSV export need a PIN. Wrong PINs are rate limited per address (8 a minute). A random PIN is made at startup if `TEACHER_PIN` is empty.
- All SQL is parameterised. CSV export defuses spreadsheet formulas in nicknames.
- Nicknames, answers, audio size and answer ranges are validated. WebSocket input is size and time limited, and browser pages from other origins are refused.
- Strict content security policy (own origin only, no inline scripts, no framing, own-origin forms). The API docs endpoints are switched off.
- Per-address rate limits (a minute): 200 new learners, 600 questions, 600 answers or skips, 60 uploads to `/api/recognise`. Each learner has at most 3 open questions, so one child cannot push out the others.
- The container runs as a non-root user. Speech models are downloaded at build time and checked against pinned SHA-256 hashes.

What it does not do, and what to put in front of it for real use:

- No TLS. Browsers only allow the microphone on `localhost` or HTTPS, so on a school network put it behind a reverse proxy with a certificate. The teacher PIN travels in a header, so use HTTPS there too.
- Nicknames are not authenticated. Anyone who knows a nickname can practise as that learner.
- The rate limits are in memory and per address. They do not survive a restart and do not stop many addresses guessing a PIN together.
- PIN lockout is per address. On a school network where devices share one address, a child who types wrong PINs can lock the teacher out for up to a minute. We kept that, because letting the right PIN through during a lockout would remove the limit on guessing.
- Behind a reverse proxy all devices share the proxy address, so these limits and the PIN lockout become one bucket for the whole room. Set `GINTI_TRUSTED_PROXY=1` only when a proxy you control sets `X-Forwarded-For` (the last entry is used); then limits are per device. Do not set it when the port is reachable directly, because clients could then forge the header.
- The compose file publishes the port on `127.0.0.1` only. To serve other devices, change it to `8000:8000` and put a TLS proxy in front. The proxy must forward the `Host` header (or set `X-Forwarded-Host`), or the WebSocket origin check refuses connections.
- With no `TEACHER_PIN`, the generated PIN is printed in the server log, which anyone with access to `docker compose logs` can read.

Report problems by opening an issue on the repository.
