# Security

Ginti is a prototype. It has no accounts, no passwords and no third-party calls, but it has not had an outside review.

What it does to stay safe:

- Speech is decoded on the server. Audio is held in memory for one utterance (12 seconds at most) and never written to disk or sent anywhere else.
- The database stores a nickname, answers and timings. No audio, no real names, no contact details.
- The teacher page and CSV export need a PIN. Wrong PINs are rate limited per address (8 a minute). A random PIN is made at startup if `TEACHER_PIN` is empty.
- All SQL is parameterised. CSV export defuses spreadsheet formulas in nicknames.
- Nicknames, answers, audio size and answer ranges are validated. WebSocket input is size and time limited, and browser pages from other origins are refused.
- Strict content security policy, no inline scripts, no framing. The API docs endpoints are switched off.
- The container runs as a non-root user. Speech models are downloaded at build time and checked against pinned SHA-256 hashes.

What it does not do, and what to put in front of it for real use:

- No TLS. Browsers only allow the microphone on `localhost` or HTTPS, so on a school network put it behind a reverse proxy with a certificate. The teacher PIN travels in a header, so use HTTPS there too.
- Nicknames are not authenticated. Anyone who knows a nickname can practise as that learner.
- The rate limit is in memory and per address. It does not survive a restart and does not stop many addresses guessing a PIN together.

Report problems by opening an issue on the repository.
