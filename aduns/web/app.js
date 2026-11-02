// Aduns Discovery dashboard (vanilla JS, no build step).
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
};
const ago = (t) => { if (!t) return "—"; const s = Date.now() / 1000 - t; return s < 60 ? `${s | 0}s ago` : s < 3600 ? `${(s / 60) | 0}m ago` : s < 86400 ? `${(s / 3600) | 0}h ago` : `${(s / 86400) | 0}d ago`; };
const link = (url, text) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text || url)}</a>` : esc(text || "");

// ---------------------------------------------------------------- tabs
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === name));
  ({ coverage: loadCoverage, overview: loadOverview, hypotheses: loadHypotheses, signals: loadSignals, capabilities: loadCaps, field: loadField, runs: loadRuns }[name] || (() => {}))();
  try { localStorage.setItem("aduns.tab", name); } catch (_) {}
}

// ---------------------------------------------------------------- overview
async function loadOverview() {
  const s = await api("/api/status");
  $("#counts").innerHTML = Object.entries(s.counts).map(([k, v]) => `<div class="kpi"><b>${v.toLocaleString()}</b><span>${k.replace(/_/g, " ")}</span></div>`).join("")
    + `<div class="kpi"><b>${s.llm_enabled ? "on" : "off"}</b><span>LLM enrichment</span></div>`;
  const max = Math.max(1, ...s.layers.map((l) => l.n));
  $("#layers").innerHTML = s.layers.map((l) => `<div class="bar"><span class="lbl">${esc(l.layer)}</span><span class="fill" style="width:${(l.n / max) * 60}%"></span><span class="n">${l.n}</span></div>`).join("") || '<p class="muted">No signals yet — run a discovery.</p>';
  $("#sourcesTbl tbody").innerHTML = s.sources.map((r) => `<tr><td>${esc(r.source)}</td><td class="ok">${r.ok_count}</td><td class="${r.error_count ? "bad" : ""}">${r.error_count}</td><td>${ago(r.last_ok)}</td><td class="muted">${r.last_error ? ago(r.last_error) + " · " + esc((r.last_error_msg || "").slice(0, 90)) : ""}</td></tr>`).join("");
  const hd = $("#hypDomain");
  if (hd.options.length === 1) s.domains.forEach((d) => hd.add(new Option(d, d)));
}
(async () => {
  try { const cs = await api("/api/countries"); $("#countryList").innerHTML = cs.map((c) => `<option value="${esc(c.name)}">`).join(""); } catch (_) {}
})();

$("#discoverForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { focus: f.get("focus"), country: f.get("country") || "", depth: +f.get("depth"), top_n: +f.get("top_n"), create_missions: !!f.get("create_missions") };
  const { job_id } = await api("/api/discover", { method: "POST", body: JSON.stringify(body) });
  pollJob(job_id);
});
async function pollJob(id) {
  const j = await api(`/api/jobs/${id}`);
  $("#jobBox").innerHTML = `<h3>Job ${esc(j.id)} — <span class="${j.status === "error" ? "bad" : j.status === "done" ? "ok" : ""}">${j.status}</span></h3><div class="log">${esc((j.log || []).join("\n"))}${j.error ? "\n" + esc(j.error) : ""}</div>`
    + (j.status === "done" ? `<p>Top hypotheses: ${(j.result.top_hypotheses || []).map((h) => `<a href="#" data-h="${h.id}">#${h.id} ${esc(h.title)}</a>`).join(" · ") || "none (try depth 2 or a broader focus)"}</p>` : "");
  $("#jobBox").querySelectorAll("[data-h]").forEach((a) => a.addEventListener("click", (ev) => { ev.preventDefault(); showTab("hypotheses"); openHyp(+a.dataset.h); }));
  if (j.status === "running") setTimeout(() => pollJob(id), 2500); else loadOverview();
}

// ---------------------------------------------------------------- coverage
async function loadCoverage() {
  const [cov, d] = await Promise.all([api("/api/coverage"), api("/api/daemon")]);
  const st = d.state || {}; const v = (k) => (st[k] || {}).value;
  const lc = v("last_cycle") || {};
  $("#daemonBox").innerHTML = `Status: <b>${esc(v("status") || "never started")}</b> ${d.running_in_this_process ? "(running in this server)" : ""} ·
    cycle ${esc(v("cycle") ?? "—")} · heartbeat ${ago(v("heartbeat"))} · now: ${esc(v("step") || "—")}<br>
    Last cycle swept: ${esc((lc.countries || []).join(", ") || "—")} · fusion: ${esc(JSON.stringify(lc.fusion || {}))}
    ${v("last_error") ? `<div class="bad">Last error: ${esc(String(v("last_error")).slice(0, 300))}</div>` : ""}`;
  try {
    const w = await api("/api/workers");
    $("#daemonBox").innerHTML += `<br>Remote workers: ${w.workers.length ? w.workers.map((x) => `${esc(x.id)} (${x.sweeps} sweeps, ${x.signals} signals, seen ${ago(x.last_seen)})`).join("; ") : "none"} · active leases: ${esc(w.leases.map((l) => l.country).join(", ") || "—")}`;
  } catch (_) {}
  $("#contKpis").innerHTML = Object.entries(cov).map(([c, x]) => `<div class="kpi"><b>${x.signals.toLocaleString()}</b><span>${esc(c)} · ${x.swept}/${x.countries} countries swept</span></div>`).join("");
  $("#contTables").innerHTML = Object.entries(cov).map(([c, x]) => `<div class="card"><h2>${esc(c)}</h2>
    <table class="tbl"><thead><tr><th>Country</th><th>Signals (recent)</th><th>Sources</th><th>Hypotheses</th><th>Last sweep</th><th>Working sources</th><th>Failed</th></tr></thead><tbody>
    ${x.rows.map((r) => `<tr><td>${esc(r.name)}</td><td>${r.signals}</td><td>${r.sources}</td><td>${r.hypotheses}</td><td>${ago(r.last_sweep)}</td><td class="muted">${esc((r.sources_ok || []).join(", "))}</td><td class="bad">${esc((r.sources_failed || []).join(", "))}</td></tr>`).join("")}
    </tbody></table></div>`).join("");
}
$("#dStart").addEventListener("click", async () => { await api("/api/daemon/start", { method: "POST" }); setTimeout(loadCoverage, 1500); });
$("#dStop").addEventListener("click", async () => { await api("/api/daemon/stop", { method: "POST" }); setTimeout(loadCoverage, 1500); });

// ---------------------------------------------------------------- hypotheses
$("#hypDomain").addEventListener("change", loadHypotheses);
$("#hypMin").addEventListener("change", loadHypotheses);
$("#hypEmerging").addEventListener("change", loadHypotheses);
$("#hypCont").addEventListener("change", loadHypotheses);
$("#refuseBtn").addEventListener("click", async () => { const { job_id } = await api("/api/agents/signal-fusion", { method: "POST", body: "{}" }); setTimeout(loadHypotheses, 4000); });
async function loadHypotheses() {
  const rows = await api(`/api/hypotheses?domain=${encodeURIComponent($("#hypDomain").value)}&min_signals=${$("#hypMin").value || 1}&emerging=${$("#hypEmerging").checked}&continent=${encodeURIComponent($("#hypCont").value)}`);
  $("#hypList").innerHTML = rows.map((h) => `<div class="item" data-id="${h.id}"><div class="t">${esc(h.title)}</div>
    <div class="m"><span class="score">${h.score.toFixed(2)}</span> · ${h.signal_count} signals · ${h.source_count} sources · ${h.layer_count} layers
    <span class="chip ev-${h.evidence_level}">${h.evidence_level.replace("_", " ")}</span> <span class="chip">${esc(h.domain || "—")}</span> <span class="chip">${esc(h.scope || "")}</span> <span class="chip">${esc(h.status)}</span>${h.emerging ? ' <span class="chip ev-field_verified">emerging</span>' : ""}</div></div>`).join("")
    || '<p class="muted">No hypotheses yet.</p>';
  $("#hypList").querySelectorAll(".item").forEach((el) => el.addEventListener("click", () => openHyp(+el.dataset.id)));
}
async function openHyp(id) {
  document.querySelectorAll("#hypList .item").forEach((el) => el.classList.toggle("sel", +el.dataset.id === id));
  const h = await api(`/api/hypotheses/${id}`);
  const kv = (o) => Object.entries(o || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<span class="chip">${esc(k)} ${typeof v === "number" ? v : ""}</span>`).join("");
  const llm = h.llm_summary ? `<h3>LLM synthesis (from the evidence below)</h3><p>${esc(h.llm_summary.need_statement)}</p><p class="muted">Who: ${esc(h.llm_summary.who_is_affected)} · Where: ${esc(h.llm_summary.where)} · Why: ${esc(h.llm_summary.why_gap_exists)}</p>` : "";
  $("#hypDetail").innerHTML = `
    <h2>#${h.id} ${esc(h.title)}</h2>
    <p>${esc(h.need_statement)}</p>${llm}
    <div><span class="score">score ${h.score.toFixed(3)}</span> <span class="chip ev-${h.evidence_level}">${h.evidence_level}</span></div>
    <h3>Score breakdown</h3>${kv(Object.fromEntries(Object.entries(h.score_breakdown || {}).map(([k, v]) => [k, +v.toFixed(2)])))}
    <h3>Key terms</h3>${(h.key_terms || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}
    <h3>Geography</h3>${kv(h.countries) || '<span class="muted">none detected</span>'} ${kv(h.continents)}
    <h3>Need types · Gap causes (why the gap exists)</h3>${kv(h.need_types)} ${kv(h.gap_causes)}
    <h3>Falsification tests</h3><ol class="guide">${(h.tests || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ol>
    <div class="toolbar"><b>Review:</b> <button data-rev="confirmed" class="primary">Confirm real need</button><button data-rev="duplicate">Duplicate</button><button data-rev="noise">Noise</button><button data-rev="rejected">Reject</button>
      ${h.momentum ? `<span class="chip">momentum ${(+h.momentum).toFixed(1)}×</span>` : ""}${h.emerging ? '<span class="chip ev-field_verified">EMERGING</span>' : ""}</div>
    <div class="toolbar"><button data-act="cap">Find capabilities</button><button data-act="ana">Find cross-border analogies</button><button data-act="mis">Draft field mission</button><span id="actMsg" class="muted"></span></div>
    <h3>Evidence (${h.signals.length} real signals)</h3>
    ${h.signals.slice(0, 60).map((s) => `<div class="sig layer-${esc(s.layer)}"><div>${esc(s.text.slice(0, 380))}</div>${s.text_en && s.text_en !== s.text ? `<div class="muted">EN: ${esc(s.text_en.slice(0, 260))}</div>` : ""}
      <div class="src">${esc(s.layer)} · ${link(s.url, s.source)} · ${esc((s.published_at || "").slice(0, 10))} · need ${s.need_score} ${(s.need_types || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div></div>`).join("")}
    <h3>Capabilities (${h.capabilities.length})</h3>
    ${h.capabilities.slice(0, 40).map((c) => `<div class="cap"><span class="chip">${esc(c.capability_type)}</span> ${link(c.url, c.title)} <span class="muted">${esc(c.holder || "")} ${c.year || ""}</span>
      <div class="muted">${esc((c.description || "").slice(0, 260))}</div><div class="muted">relevance ${(+c.relevance).toFixed(2)} · ${esc(c.rationale)}</div></div>`).join("") || '<p class="muted">None yet.</p>'}
    <h3>Cross-border analogies (${h.analogies.length})</h3>
    <table class="tbl"><thead><tr><th>Analog</th><th>Measure</th><th>Target pressure</th><th>Analog pressure</th><th>Method</th><th>Same income</th><th>Score</th><th>How they did it (evidence)</th></tr></thead><tbody>
    ${h.analogies.map((a) => `<tr><td>${esc(a.analog_name)}</td><td>${esc(a.indicator_name)}</td><td>${(+a.target_value).toFixed(2)}</td><td>${(+a.analog_value).toFixed(2)}</td><td>${esc(a.method || "")}</td><td>${(+a.income_similarity).toFixed(2)}</td><td>${(+a.deviance_score).toFixed(2)}</td><td>${(a.evidence || []).map((e) => link(e.url, e.title)).join("<br>")}</td></tr>`).join("")}</tbody></table>
    <h3>Field missions</h3>${h.missions.map(missionHtml).join("") || '<p class="muted">None yet.</p>'}`;
  $("#hypDetail").querySelectorAll("[data-rev]").forEach((b) => b.addEventListener("click", async () => {
    const reviewer = prompt("Your name (recorded in the audit log)"); if (!reviewer) return;
    const reason = prompt("Reason (optional)") || "";
    await api(`/api/hypotheses/${id}/review`, { method: "POST", body: JSON.stringify({ verdict: b.dataset.rev, reviewer, reason }) });
    loadHypotheses(); openHyp(id);
  }));
  $("#hypDetail").querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const act = b.dataset.act; $("#actMsg").textContent = "running…";
    try {
      if (act === "mis") await api("/api/agents/offline-scout/missions", { method: "POST", body: JSON.stringify({ hypothesis_id: id }) });
      else {
        const { job_id } = await api(act === "cap" ? "/api/agents/capability-discovery" : "/api/agents/cross-border-analogy", { method: "POST", body: JSON.stringify({ hypothesis_id: id }) });
        for (;;) { await new Promise((r) => setTimeout(r, 2000)); const j = await api(`/api/jobs/${job_id}`); if (j.status !== "running") { if (j.result && j.result.status === "error") throw new Error(j.result.stats.errors.join("; ")); break; } }
      }
      openHyp(id);
    } catch (err) { $("#actMsg").textContent = String(err).slice(0, 300); }
  }));
}
function missionHtml(m) {
  return `<div class="card"><b>${esc(m.code)}</b> — ${esc(m.title)} <span class="chip">${esc(m.status)}</span> <span class="chip">${m.observations} obs / quota ${m.quota}</span>
    <div class="muted">${esc(m.country)} · languages: ${esc((m.languages || []).join(", ") || "—")} · reward/validated: ${m.reward_per_validated}</div>
    <div class="muted">Respondents: ${esc((m.target_respondents || []).join(", "))}</div>
    <details><summary>Locations (${(m.locations || []).length}) &amp; interview guide</summary>
      <ul>${(m.locations || []).map((l) => `<li>${link(l.osm_url, l.name)} <span class="muted">(${l.lat.toFixed(4)}, ${l.lon.toFixed(4)})</span></li>`).join("")}</ul>
      <p><i>${esc(m.consent_script)}</i></p><ol class="guide">${(m.interview_guide || []).map((q) => `<li>${esc(q.q)} <span class="chip">${esc(q.kind)}</span></li>`).join("")}</ol></details></div>`;
}

// ---------------------------------------------------------------- signals
$("#sigGo").addEventListener("click", loadSignals);
async function loadSignals() {
  const p = new URLSearchParams({ q: $("#sigQ").value, layer: $("#sigLayer").value, source: $("#sigSource").value, country: $("#sigCountry").value, limit: 200 });
  const rows = await api(`/api/signals?${p}`);
  $("#sigList").innerHTML = rows.map((s) => `<div class="sig layer-${esc(s.layer)}"><div>${esc(s.text.slice(0, 420))}</div>${s.text_en && s.text_en !== s.text ? `<div class="muted">EN: ${esc(s.text_en.slice(0, 300))}</div>` : ""}
    <div class="src">${esc(s.layer)} · ${link(s.url, s.source)} · ${esc((s.published_at || "").slice(0, 10))} · need ${s.need_score} · intensity ${s.intensity}
    ${(s.need_types || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("")} ${(s.countries || []).map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div></div>`).join("") || '<p class="muted">No signals.</p>';
}

// ---------------------------------------------------------------- capabilities
$("#capGo").addEventListener("click", loadCaps);
async function loadCaps() {
  const rows = await api(`/api/capabilities?capability_type=${$("#capType").value}&q=${encodeURIComponent($("#capQ").value)}`);
  $("#capList").innerHTML = `<div class="card">${rows.map((c) => `<div class="cap"><span class="chip">${esc(c.capability_type)}</span> ${link(c.url, c.title)} <span class="muted">${esc(c.holder || "")} ${c.year || ""} · maturity ${c.maturity}</span>
    <div class="muted">${esc((c.description || "").slice(0, 300))}</div><div>${(c.transferability || []).map((r) => `<span class="chip">${esc(r)}</span>`).join("")}</div></div>`).join("") || '<p class="muted">None yet.</p>'}</div>`;
}

// ---------------------------------------------------------------- field network
async function loadField() {
  const [ms, obs, sc, led] = await Promise.all([api("/api/missions?status="), api("/api/observations"), api("/api/scouts"), api("/api/ledger")]);
  $("#missionList").innerHTML = ms.map(missionHtml).join("") || '<p class="muted">No missions yet.</p>';
  $("#obsList").innerHTML = obs.map((o) => `<div class="sig layer-offline"><div>${esc(o.text)}</div><div class="src">#${o.id} · ${esc(o.mission_code || "no mission")} · scout #${o.scout_id} · ${esc(o.channel)} · <b>${esc(o.status)}</b> ${o.price_observed != null ? `· price ${o.price_observed} ${esc(o.currency)}` : ""}<br>${esc(o.validation_notes || "")}</div>
    ${["submitted", "corroborated"].includes(o.status) ? `<button class="small" data-o="${o.id}" data-d="validated">Validate</button> <button class="small" data-o="${o.id}" data-d="rejected">Reject</button>` : ""}</div>`).join("") || '<p class="muted">No observations yet.</p>';
  $("#obsList").querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", async () => {
    const reviewer = prompt("Reviewer name"); if (!reviewer) return;
    await api(`/api/observations/${b.dataset.o}/review`, { method: "POST", body: JSON.stringify({ decision: b.dataset.d, reviewer }) }); loadField();
  }));
  $("#scoutTbl tbody").innerHTML = sc.map((s) => `<tr><td>${s.id}</td><td>${esc(s.display_name)}</td><td>${esc(s.role)}</td><td>${esc(s.country || "")}</td><td>${s.observations}</td><td>${(+s.earned).toFixed(2)}</td></tr>`).join("");
  $("#ledgerTbl tbody").innerHTML = led.map((l) => `<tr><td>#${l.scout_id}</td><td>${(+l.amount).toFixed(2)} ${esc(l.currency)}</td><td>${esc(l.reason)}</td><td>${esc(l.status)}</td></tr>`).join("");
}

// ---------------------------------------------------------------- runs
async function loadRuns() {
  const [rs, au] = await Promise.all([api("/api/runs"), api("/api/audit")]);
  $("#runsTbl tbody").innerHTML = rs.map((r) => `<tr><td>${r.id}</td><td>${esc(r.agent)}</td><td class="${r.status === "error" ? "bad" : r.status === "ok" ? "ok" : ""}">${esc(r.status)}</td><td><code>${esc(JSON.stringify(r.params)).slice(0, 140)}</code></td><td><code>${esc(JSON.stringify(r.stats)).slice(0, 260)}</code></td><td>${r.finished_at ? ((r.finished_at - r.started_at)).toFixed(0) + "s" : "…"}</td></tr>`).join("");
  $("#auditTbl tbody").innerHTML = au.map((a) => `<tr><td>${ago(a.at)}</td><td>${esc(a.actor)}</td><td>${esc(a.action)}</td><td>${esc(a.object_type || "")} ${a.object_id ?? ""}</td><td><code>${esc((a.detail || "").slice(0, 200))}</code></td></tr>`).join("");
}

let start = "overview";
try { start = localStorage.getItem("aduns.tab") || "overview"; } catch (_) {}
showTab(start);
