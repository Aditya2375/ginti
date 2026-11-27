"use strict";
// Ginti front end. No framework, no build step.

const ROUND = 10;                // questions per round
const LISTEN_MS = 8000;          // longest we listen for one answer
const CONFIRM_MS = 2500;         // time to say "that is not what I said"

const T = {
  hi: {
    hear: "फिर सुनो", speak: "बोलो", listening: "सुन रहा हूँ…", heard: "तुमने कहा",
    redo: "नहीं, फिर से बोलो", right: "सही! 🎉", wrong: n => `ठीक नहीं। जवाब ${n} था।`,
    nohear: "सुनाई नहीं दिया। फिर से बोलो।", nomic: "माइक नहीं चला। नीचे टाइप कर सकते हो।",
    typed: "या यहाँ लिखो", level: l => `स्तर ${l}`, skipped: n => `जवाब ${n} था।`,
    doneTitle: "शाबाश!", doneBody: (c, n) => `${n} में से ${c} सही।`,
    again: "फिर खेलो", miss: "इन पर फिर मेहनत करो:", lang: "hi-IN",
    nospeech: "इस फ़ोन में आवाज़ नहीं है, सवाल स्क्रीन पर पढ़ो।",
    retry: "फिर कोशिश करो", busy: "अभी बहुत लोग हैं। थोड़ी देर बाद कोशिश करो।", sameName: l => `यह नाम पहले से ${l} में है।`,
  },
  en: {
    hear: "Hear again", speak: "Speak", listening: "Listening…", heard: "You said",
    redo: "No, say it again", right: "Right! 🎉", wrong: n => `Not quite. The answer was ${n}.`,
    nohear: "I did not catch that. Say it again.", nomic: "The microphone did not start. You can type below.",
    typed: "Or type it", level: l => `Level ${l}`, skipped: n => `The answer was ${n}.`,
    doneTitle: "Well done!", doneBody: (c, n) => `${c} right out of ${n}.`,
    again: "Play again", miss: "Practise these again:", lang: "en-IN",
    nospeech: "This device has no voice, read the question on the screen.",
    retry: "Try again", busy: "Too many people right now. Try again in a moment.", sameName: l => `This name already uses ${l}.`,
  },
};

const $ = id => document.getElementById(id);
const state = { learner: null, topic: null, q: null, round: [], busy: false, t0: 0, ws: null, audio: null, token: 0, confirm: null, listenTimer: null };
const S = () => T[state.learner.lang];

function show(id) {
  for (const s of ["screen-start", "screen-ask", "screen-done"]) $(s).classList.toggle("hidden", s !== id);
}

async function api(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
  return data;
}

// A failed call (busy server, network blip) must not strand the child: show why and a button.
function failed(e) {
  state.busy = false;
  $("status").textContent = e && e.message ? e.message : "…";
  $("btn-retry").textContent = S().retry;
  $("btn-retry").classList.remove("hidden");
}
$("btn-retry").addEventListener("click", () => { $("btn-retry").classList.add("hidden"); state.busy = false; nextQuestion(); });

// ------------------------------------------------------------------ speaking
function speak(text) {
  return new Promise(resolve => {
    const synth = window.speechSynthesis;
    if (!synth) return resolve(false);
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = S().lang;
    u.rate = 0.9;
    const voice = synth.getVoices().find(v => v.lang.replace("_", "-").startsWith(S().lang.slice(0, 2)));
    if (voice) u.voice = voice;
    u.onend = () => resolve(true);
    u.onerror = () => resolve(false);
    setTimeout(() => resolve(false), 12000);
    synth.speak(u);
  });
}

// ----------------------------------------------------------------- start
document.querySelectorAll(".topic").forEach(b => b.addEventListener("click", async () => {
  const nick = $("nick").value.trim();
  const lang = document.querySelector("input[name=lang]:checked").value;
  $("start-error").textContent = "";
  if (!nick) { $("start-error").textContent = "Type a nickname first · पहले उपनाम लिखो"; $("nick").focus(); return; }
  try {
    state.learner = await api("/api/learners", { nickname: nick, lang });
  } catch (e) { $("start-error").textContent = e.message; return; }
  if (state.learner.lang !== lang) {
    // a nickname keeps the language it was first used with; say so instead of switching silently
    $("start-error").textContent = T[state.learner.lang].sameName(state.learner.lang === "hi" ? "हिन्दी" : "English");
  }
  state.topic = b.dataset.topic;
  state.round = [];
  $("t-hear").textContent = S().hear; $("t-speak").textContent = S().speak; $("t-typed").textContent = S().typed;
  $("btn-redo").textContent = S().redo;
  show("screen-ask");
  nextQuestion();
}));

// -------------------------------------------------------------- questions
async function nextQuestion() {
  clearTimeout(state.confirm);
  if (state.round.length >= ROUND) return finish();
  $("feedback").classList.add("hidden");
  $("heard-box").classList.add("hidden");
  $("status").textContent = "";
  $("typed-in").value = "";
  $("meter-fill").style.width = `${(state.round.length / ROUND) * 100}%`;
  $("btn-retry").classList.add("hidden");
  try {
    state.q = await api("/api/question", { learner_id: state.learner.id, topic: state.topic });
  } catch (e) { failed(e); return; }
  $("expr").textContent = state.q.display;
  $("prompt").textContent = state.q.prompt;
  $("level").textContent = S().level(state.q.level);
  state.busy = false;
  await readAloud();
  startListening();
}

async function readAloud() {
  const ok = await speak(state.q.prompt);
  if (!ok && !window.speechSynthesis) $("status").textContent = S().nospeech;
}

$("btn-hear").addEventListener("click", async () => {
  clearTimeout(state.confirm); $("heard-box").classList.add("hidden");   // do not score an answer while the question replays
  stopListening(); await readAloud();
});
$("btn-mic").addEventListener("click", () => { if (state.ws) stopListening(); else startListening(); });
$("btn-redo").addEventListener("click", () => {
  clearTimeout(state.confirm); $("heard-box").classList.add("hidden"); startListening();
});
$("typed").addEventListener("submit", ev => {
  ev.preventDefault();
  const v = $("typed-in").value.trim();
  if (v && state.q && !state.busy) submit(v, "typed");
});

// ------------------------------------------------------------- listening
function stopListening() {
  state.token++;                            // cancels a start that is still waiting on the mic
  if (state.audio) { state.audio.stream.getTracks().forEach(t => t.stop()); state.audio.ctx.close().catch(() => {}); state.audio = null; }
  if (state.ws) { try { state.ws.close(); } catch (_) {} state.ws = null; }
  clearTimeout(state.listenTimer);
  $("btn-mic").classList.remove("live");
  $("t-speak").textContent = S().speak;
}

async function startListening() {
  if (state.busy || !state.q) return;
  clearTimeout(state.confirm);
  stopListening();
  const token = state.token;
  const q = state.q;
  $("status").textContent = "…";
  $("btn-mic").classList.add("live");
  $("t-speak").textContent = "■";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const release = c => { stream.getTracks().forEach(t => t.stop()); if (c) c.close().catch(() => {}); };
    if (token !== state.token) { release(null); return; }     // a newer start or a stop came first
    const ctx = new AudioContext();
    try {
      await ctx.resume();                                      // iOS Safari starts contexts suspended
      await ctx.audioWorklet.addModule("/static/pcm-worklet.js");
    } catch (e) { release(ctx); throw e; }
    if (token !== state.token) { release(ctx); return; }
    const src = ctx.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(ctx, "pcm-worklet");
    src.connect(node);
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws/listen`);
    ws.binaryType = "arraybuffer";
    state.ws = ws; state.audio = { stream, ctx };
    let ready = false;
    const queued = [];                       // keep the first words if the socket is a moment slow
    node.port.onmessage = e => {
      if (ready && ws.readyState === 1) ws.send(e.data);
      else if (queued.length < 30) queued.push(e.data);
    };
    ws.onopen = () => {
      ws.send(JSON.stringify({ lang: q.lang, lo: q.lo, hi: q.hi }));
      state.listenTimer = setTimeout(() => { if (state.ws === ws) { stopListening(); $("status").textContent = S().nohear; } }, LISTEN_MS + 4000);
    };
    ws.onclose = ev => {
      // the server closes on its own deadline, on a restart, or when it is full (1013)
      if (state.ws === ws) { stopListening(); $("status").textContent = ev.code === 1013 ? S().busy : S().nohear; }
    };
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.type === "ready") {
        state.t0 = performance.now();
        ready = true;
        $("status").textContent = S().listening;
        for (const chunk of queued.splice(0)) ws.send(chunk);
        clearTimeout(state.listenTimer);
        state.listenTimer = setTimeout(() => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: "stop" })); }, LISTEN_MS);
      } else if (m.type === "partial") {
        $("status").textContent = `${S().listening} ${m.text}`;
      } else if (m.type === "final") {
        const ms = Math.round(performance.now() - state.t0);
        stopListening();
        onHeard(m, ms);
      } else if (m.type === "error") {
        stopListening(); $("status").textContent = S().nomic;
      }
    };
    ws.onerror = () => { stopListening(); $("status").textContent = S().nomic; };
  } catch (e) {
    stopListening();
    $("status").textContent = S().nomic;
  }
}

function onHeard(m, ms) {
  if (m.command === "repeat") { $("status").textContent = ""; readAloud().then(startListening); return; }
  if (m.command === "skip") { skipQuestion(); return; }
  if (m.value === null || m.value === undefined) { $("status").textContent = S().nohear; return; }
  $("status").textContent = "";
  $("heard-text").textContent = `${S().heard}: ${m.value}`;
  $("heard-box").classList.remove("hidden");
  state.confirm = setTimeout(() => { $("heard-box").classList.add("hidden"); submit(String(m.value), "voice", ms); }, CONFIRM_MS);
}

// --------------------------------------------------------------- answers
async function submit(text, mode, ms) {
  if (state.busy) return;
  clearTimeout(state.confirm);
  state.busy = true; stopListening();
  let r;
  try {
    r = await api("/api/answer", { learner_id: state.learner.id, qid: state.q.qid, text, ms: ms ?? null, mode });
  } catch (e) {
    if (/no longer open/.test(e.message)) { state.busy = false; nextQuestion(); return; }   // question expired: get a fresh one
    state.busy = false; $("status").textContent = e.message; return;
  }
  state.round.push({ display: state.q.display, ok: r.correct, expected: r.expected });
  const fb = $("feedback");
  fb.className = `feedback ${r.correct ? "ok" : "no"}`;
  fb.textContent = r.correct ? S().right : S().wrong(r.expected);
  await speak(r.correct ? S().right.replace(/[^\p{L}! ]/gu, "") : S().wrong(r.expected));
  setTimeout(nextQuestion, 900);
}

async function skipQuestion() {
  if (state.busy) return;
  clearTimeout(state.confirm);
  state.busy = true; stopListening();
  try {
    const r = await api("/api/skip", { learner_id: state.learner.id, qid: state.q.qid });
    state.round.push({ display: state.q.display, ok: false, expected: r.expected });
    const fb = $("feedback"); fb.className = "feedback no"; fb.textContent = S().skipped(r.expected);
    await speak(S().skipped(r.expected));
  } catch (e) { failed(e); return; }
  setTimeout(nextQuestion, 900);
}

// ----------------------------------------------------------------- finish
function finish() {
  stopListening();
  const ok = state.round.filter(r => r.ok).length;
  $("done-title").textContent = S().doneTitle;
  $("done-body").textContent = S().doneBody(ok, state.round.length);
  const ul = $("done-miss"); ul.textContent = "";
  const misses = state.round.filter(r => !r.ok);
  if (misses.length) {
    const li0 = document.createElement("li"); li0.textContent = S().miss; li0.style.listStyle = "none"; ul.append(li0);
    for (const r of misses) { const li = document.createElement("li"); li.textContent = `${r.display} = ${r.expected}`; ul.append(li); }
  }
  $("btn-again").textContent = S().again;
  show("screen-done");
  speak($("done-title").textContent + " " + $("done-body").textContent);
}
$("btn-again").addEventListener("click", () => { state.round = []; show("screen-ask"); nextQuestion(); });
if (window.speechSynthesis) window.speechSynthesis.getVoices();
