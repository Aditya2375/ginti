"use strict";
const $ = id => document.getElementById(id);
let pin = "";
async function get(path) {
  const r = await fetch(path, { headers: { "X-Teacher-Pin": pin } });
  if (!r.ok) throw new Error(r.status === 401 ? "Wrong PIN" : r.status === 429 ? "Too many tries, wait a minute" : `Error ${r.status}`);
  return r;
}
function cell(tr, text) { const td = document.createElement("td"); td.textContent = text; tr.append(td); }
async function load() {
  const data = await (await get("/api/teacher/summary")).json();
  const body = $("rows"); body.textContent = "";
  for (const l of data.learners) {
    const tr = document.createElement("tr");
    cell(tr, l.nickname);
    cell(tr, `${l.correct}/${l.attempts}`);
    cell(tr, l.recent_accuracy === null ? "–" : `${Math.round(l.recent_accuracy * 100)}%`);
    cell(tr, l.median_ms_correct === null ? "–" : `${(l.median_ms_correct / 1000).toFixed(1)} s`);
    cell(tr, ["add", "sub", "mul"].map(t => `${{ add: "+", sub: "−", mul: "×" }[t]}${l.levels[t]}`).join("  "));
    cell(tr, l.weak_facts.map(w => `${w.fact} (${w.misses}/${w.tries})`).join(", ") || "–");
    body.append(tr);
  }
  $("gate").classList.add("hidden"); $("board").classList.remove("hidden");
}
$("pin-form").addEventListener("submit", async ev => {
  ev.preventDefault(); pin = $("pin").value; $("err").textContent = "";
  try { await load(); } catch (e) { $("err").textContent = e.message; }
});
$("csv").addEventListener("click", async () => {
  const blob = await (await get("/api/teacher/export.csv")).blob();
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "ginti-attempts.csv"; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
});
