/* Cyclia desktop UI. Plain JavaScript; talks to the local engine over HTTP. */
"use strict";

const TOKEN = document.querySelector('meta[name="api-token"]').content;
const desktop = window.cyclia || null; // native helpers from the Electron preload
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const S = {
  status: null, models: [], model: null, methods: [], selectedMethods: new Set(), result: null, params: null,
  cat: 0, src: "activity", step: "setup", rt: "summary", replaceLine: null, linkDb: null,
  comments: [], commentLine: null, tt: "valid", bgRules: [], bgEdit: null, lit: null, coords: null,
};

/* ---------------- helpers ---------------- */
async function api(method, path, body) {
  let r;
  try {
    r = await fetch(path, { method, headers: { "Content-Type": "application/json", "X-Token": TOKEN },
      body: body ? JSON.stringify(body) : undefined });
  } catch (e) { throw new Error("The calculation engine is not responding. Restart Cyclia."); }
  let data = {};
  try { data = await r.json(); } catch (e) { /* empty body */ }
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "show" + (err ? " err" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = ""), err ? 8000 : 2800);
}
async function guard(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { toast(e.message, true); return undefined; } finally { if (btn) btn.disabled = false; }
}
function fmt(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "-";
  if (x === 0) return "0";
  const a = Math.abs(x);
  if (a >= 1e5 || a < 0.001) return x.toExponential(3).replace("e+", "e");
  return Number(x.toPrecision(4)).toLocaleString("en-US", { maximumFractionDigits: 6 });
}
const pct = (part, total) => (total ? (100 * part) / total : 0);
const ls = { get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } } };
const projKey = (k) => `cyclia.${k}.${S.status && S.status.project}`;

/* ---------------- navigation ---------------- */
function go(step) {
  S.step = step;
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + step));
  $$("#steps button, #navTools").forEach((b) => { if (b.dataset.step === step) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current"); });
  if (step === "scope") { fillScope(); loadParams(); renderScenarios(); loadVersions(); }
  if (step === "inventory") { renderInventory(); updateSearchUI(); loadComments(); }
  if (step === "impact") { renderMethodPicker(); renderScenarioSelect(); renderBgSelect(); }
  if (step === "results") { renderResults(); renderCompareModels(); }
  if (step === "report") { fillConclusions(); fillEpdForm(); renderShareModels(); }
  if (step === "tools") showToolTab(S.tt);
  renderLockBanners();
  window.scrollTo(0, 0);
  renderGuide();
  if (window.renderCoach) window.renderCoach();
}
$$("#steps button, #navTools").forEach((b) => b.addEventListener("click", () => go(b.dataset.step)));

function markSteps() {
  const st = S.status || {};
  const m = S.model;
  const errors = S.result ? S.result.checks.filter((c) => c.level === "error").length : 0;
  const done = {
    setup: !!(st.project && st.databases && st.databases.length && st.n_methods),
    scope: !!(m && m.unit && m.product && m.scope && m.scope.goal && m.scope.boundary),
    inventory: !!(m && m.inputs && m.inputs.length && !m.inputs.some((i) => i.missing)),
    impact: S.selectedMethods.size > 0,
    results: !!S.result && !errors,
    report: !!(m && m.scope && m.scope.conclusions),
  };
  $$("#steps li").forEach((li) => li.classList.toggle("done", !!done[$("button", li).dataset.step]));
  $$(".needs-model").forEach((el) => el.classList.toggle("locked", !S.model));
  renderSentence();
  renderGuide();
  if (window.renderCoach) window.renderCoach();
}
function renderSentence() {
  const st = S.status || {};
  const m = S.model;
  const slot = (v, ph) => (v ? `<span class="slot">${esc(v)}</span>` : `<span class="slot missing">${esc(ph)}</span>`);
  if (!st.project) { $("#studySentence").textContent = "Start by creating or opening a project."; return; }
  const used = m ? [...new Set(m.inputs.filter((i) => i.kind === "activity").map((i) => i.target.db))] : [];
  const dbs = (used.length ? used : (st.databases || []).map((d) => d.name)).join(" and ");
  const sc = (m && m.scope) || {};
  const fu = m && m.unit && m.product ? `${fmt(m.amount)} ${m.unit} of ${m.product}` : "";
  const fams = [...new Set(S.methods.filter((x) => S.selectedMethods.has(x.id)).map((x) => x.family))].join(", ");
  $("#studySentence").title = "";
  $("#studySentence").innerHTML = `Assessing ${slot(fu, "a functional unit")}, ${slot(sc.boundary || "", "system boundary")}, ` +
    `with ${slot(dbs, "a background database")}, using ${slot(fams, "an impact method")}.`;
  $("#studySentence").title = $("#studySentence").textContent;
}

/* ---------------- status & projects ---------------- */
async function refreshStatus() {
  S.status = await api("GET", "/api/status");
  $("#versionTag").textContent = `${S.status.app} ${S.status.version}`;
  $("#projectBadge").innerHTML = S.status.project ? `Project: <b>${esc(S.status.project)}</b>` : "No project open";
  $$(".needs-project").forEach((el) => el.classList.toggle("locked", !S.status.project));
  $("#eiMissing").hidden = !!S.status.ecoinvent_interface;
  $("#authorName").value = (S.status.settings || {}).author || "";
  fillStageSystems();
  if (S.status.project) {
    const mres = await api("GET", "/api/methods");
    S.methods = mres.methods;
    loadMethodSel();
    $("#nwSet").innerHTML = '<option value="">Not used</option>' + mres.nw_sets.map((n) => `<option>${esc(n)}</option>`).join("");
    const nw = ls.get(projKey("nw"), "");
    $("#nwSet").value = mres.nw_sets.includes(nw) ? nw : "";
    renderDbs(); renderMethodFamilies(); await refreshModels();
  } else {
    S.methods = []; S.models = []; S.model = null; renderModelSelect(); fillScope();
    $("#dbList").innerHTML = ""; $("#methodFamilies").innerHTML = "";
  }
  await renderProjects();
  markSteps();
}
async function renderProjects() {
  const { projects, current } = await api("GET", "/api/projects");
  $("#projectList").innerHTML = projects.length ? projects.map((p) => `
    <li class="${p.name === current ? "current" : ""}"><b class="grow">${esc(p.name)}</b><span class="meta">${p.size_mb} MB</span>
      ${p.name === current ? '<span class="meta">open</span>' : `<button data-open="${esc(p.name)}">Open</button>`}
      <button class="ghost danger" data-del="${esc(p.name)}">Delete</button></li>`).join("")
    : '<li class="empty">No projects yet. Name one above to begin.</li>';
}
$("#projectList").addEventListener("click", (e) => {
  const o = e.target.closest("[data-open]"), d = e.target.closest("[data-del]");
  if (o) guard(o, async () => { await api("POST", "/api/projects/open", { name: o.dataset.open }); S.result = null; await refreshStatus(); });
  if (d && confirm(`Delete project "${d.dataset.del}"? Its models are removed; the shared databases stay in the library. This cannot be undone.`))
    guard(d, async () => { await api("POST", "/api/projects/delete", { name: d.dataset.del }); S.result = null; await refreshStatus(); });
});
$("#btnCreateProject").addEventListener("click", (e) => guard(e.target, async () => {
  const name = $("#newProjectName").value.trim();
  if (!name) throw new Error("Type a project name first.");
  await api("POST", "/api/projects", { name });
  $("#newProjectName").value = ""; S.result = null;
  await refreshStatus();
  toast(S.status.databases.length ? "Project created. Next: goal & scope." : "Project created. Now connect a database.");
}));
$("#newProjectName").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btnCreateProject").click(); });
async function openProjectFile(path, btn) {
  return guard(btn, async () => {
    const r = await api("POST", "/api/projects/import", { path });
    S.result = null; await refreshStatus();
    if (r.missing_databases.length) toast(`Opened. These databases are not in your library yet: ${r.missing_databases.join(", ")}. Import them in step 1 and the lines link themselves.`, true);
    else toast("Project opened.");
  });
}
$("#btnImportProject").addEventListener("click", async (e) => {
  if (desktop) { const p = await desktop.pickFile("lca"); if (p) openProjectFile(p, e.target); }
  else $("#importProjectRow").hidden = !$("#importProjectRow").hidden;
});
$("#btnImportProjectGo").addEventListener("click", (e) => openProjectFile($("#importProjectPath").value, e.target));

/* ---------------- library: databases, linking, validation ---------------- */
function renderDbs() {
  const dbs = S.status.databases;
  $("#dbList").innerHTML = dbs.length ? dbs.map((d) => `
    <li><span class="grow"><b>${esc(d.name)}</b><br><span class="meta">${esc(d.source)}${d.version ? ", v" + esc(d.version) : ""}${d.system_model ? ", " + esc(d.system_model) : ""}, ${d.n_activities.toLocaleString("en-US")} datasets${d.has_uncertainty ? ", with uncertainty data" : ""}</span>
    ${d.n_unlinked ? `<br><span class="meta warn">${d.n_unlinked} product(s) without a supplier</span>` : ""}
    ${d.note ? `<br><span class="meta">${esc(d.note)}</span>` : ""}</span>
    ${d.n_unlinked ? `<button data-link="${d.id}">Link missing suppliers</button>` : ""}
    <button class="ghost" data-dbmeta="${d.id}">Details</button>
    <button class="ghost" data-validate="${d.id}">Check</button>
    <button class="ghost danger" data-deldb="${d.id}">Remove</button></li>`).join("")
    : '<li class="empty">No database yet. Pick one of the options below.</li>';
  $("#searchDb").innerHTML = '<option value="">All databases</option>' + dbs.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
}
$("#dbList").addEventListener("click", (e) => {
  const del = e.target.closest("[data-deldb]"), lk = e.target.closest("[data-link]"), va = e.target.closest("[data-validate]");
  if (del && confirm("Remove this database from the library? Every project on this computer uses the same library."))
    guard(del, async () => { await api("DELETE", "/api/databases/" + del.dataset.deldb); S.result = null; await refreshStatus(); });
  if (lk) guard(lk, () => openLinkPanel(Number(lk.dataset.link)));
  const dm = e.target.closest("[data-dbmeta]");
  if (dm) guard(dm, async () => {
    const d = S.status.databases.find((x) => x.id === Number(dm.dataset.dbmeta));
    const p = $("#validatePanel");
    const F = [["original_name", "Original name"], ["version", "Version"], ["system_model", "System model"], ["source", "Source / format"],
      ["release_date", "Release date (YYYY-MM-DD)"], ["geography", "Geography"], ["technology", "Technology"], ["licence", "Licence"],
      ["reference_period", "Reference period"], ["data_reference", "Data reference (citation or DOI)"]];
    p.hidden = false;
    p.innerHTML = `<div class="row"><h3 class="grow">Database details: ${esc(d.name)}</h3><button class="ghost" data-close>Close</button></div>
      <p class="hint">Recorded for reproducibility and printed in reports. The fingerprint, importer version and import report are set by Cyclia.</p>
      <form id="dbMetaForm" class="form-grid">${F.map(([k, l]) => `<label>${l}<input name="${k}" value="${esc(d[k] || "")}"></label>`).join("")}</form>
      <table><tbody><tr><td>Imported</td><td>${esc(d.imported_at || "")}</td></tr><tr><td>Importer</td><td>${esc(d.importer_version || "not recorded")}</td></tr>
      <tr><td>Source file</td><td>${esc(d.source_path || "")}</td></tr><tr><td>SHA-256</td><td><code>${esc(d.source_sha256 || "not recorded")}</code></td></tr></tbody></table>
      <div class="row"><button class="primary" data-savemeta="${d.id}">Save details</button></div>`;
  });
  if (va) guard(va, async () => {
    const p = $("#validatePanel");
    p.hidden = false; p.innerHTML = '<p class="hint">Checking the matrix...</p>';
    const v = await api("POST", "/api/validate", { db_id: Number(va.dataset.validate) });
    p.innerHTML = `<div class="row"><h3 class="grow">Database check</h3><button class="ghost" data-close>Close</button></div><p><b>${esc(v.verdict)}</b></p>
      ${(v.statuses || []).length ? `<table><thead><tr><th>Check</th><th>Status</th><th>Result</th></tr></thead><tbody>${v.statuses.map((x) => `<tr><td>${esc(x.label)}</td><td><span class="${x.level === "ok" ? "ok" : x.level === "error" ? "danger" : "warn"}">${esc(x.level)}</span></td><td>${esc(x.message)}</td></tr>`).join("")}</tbody></table><h3>Numbers</h3>` : ""}
      <table><tbody>${[["Datasets in the library", v.datasets], ["Technosphere exchanges", v.exchanges], ["Elementary exchanges", v.elementary_exchanges],
        ["Random solves checked", v.sampled], ["Largest relative residual", v.max_relative_residual.toExponential(1)], ["Datasets with zero production", v.zero_production],
        ["Inputs without supplier", v.unlinked_inputs], ["Elementary flows used", v.flows_used], ["...of which without any factor", v.flows_without_any_factor]]
        .map(([k, x]) => `<tr><td>${k}</td><td class="num">${esc(x)}</td></tr>`).join("")}</tbody></table>${v.note ? `<p class="hint">${esc(v.note)}</p>` : ""}`;
  });
});
$("#validatePanel").addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) $("#validatePanel").hidden = true;
  const sv = e.target.closest("[data-savemeta]");
  if (sv) guard(sv, async () => {
    const body = {};
    $$("#dbMetaForm input").forEach((i) => (body[i.name] = i.value.trim()));
    await api("PATCH", "/api/databases/" + sv.dataset.savemeta, body);
    toast("Database details saved."); await refreshStatus();
  });
});

async function openLinkPanel(dbId) {
  S.linkDb = dbId;
  const db = S.status.databases.find((d) => d.id === dbId);
  const { groups } = await api("GET", `/api/databases/${dbId}/unlinked`);
  const p = $("#linkPanel");
  p.hidden = false;
  p.innerHTML = `<div class="row"><h3 class="grow">Link missing suppliers of ${esc(db ? db.name : "")}</h3>
      <button data-autolink>Link exact matches automatically</button><button class="ghost" data-close>Close</button></div>
    <p class="hint">Each row is a product used by datasets in this database without a single supplier: produced in no dataset of the import, produced by several (Cyclia does not guess), or without a supplier link in the dataset. Each location is a separate row, so every location gets its own supplier. Units are converted. "Link automatically" only links rows with exactly one supplier at the same location (or one global market for inputs without a location).</p>
    <table class="link-table"><thead><tr><th>Product</th><th>Location</th><th>Unit</th><th class="num">Uses</th><th>Why unlinked</th><th>Status</th><th></th></tr></thead><tbody>
    ${groups.map((g, i) => `<tr data-i="${i}"><td>${esc(g.product)}</td><td>${esc(g.location || "-")}</td><td>${esc(g.unit)}</td><td class="num">${g.uses}</td>
      <td>${esc(g.reasons || "no producer")}${g.candidates && g.candidates.length ? ` <span class="hint">(${g.candidates.length} candidates)</span>` : ""}</td>
      <td>${g.linked ? '<span class="ok">linked</span>' : '<span class="warn">missing</span>'}</td>
      <td>${g.linked ? `<button class="ghost" data-unlink="${i}">Unlink</button>` : `<button data-suggest="${i}">Find supplier</button>`}</td></tr>
      <tr class="sugg" id="sugg-${i}" hidden><td colspan="7"></td></tr>`).join("")}</tbody></table>`;
  p._groups = groups;
}
$("#linkPanel").addEventListener("click", (e) => {
  const p = $("#linkPanel"), groups = p._groups || [];
  if (e.target.closest("[data-close]")) { p.hidden = true; return; }
  const auto = e.target.closest("[data-autolink]");
  if (auto) guard(auto, async () => {
    const r = await api("POST", `/api/databases/${S.linkDb}/autolink`, {});
    toast(`${r.auto_linked} product(s) linked automatically` + (r.left_for_review ? `; ${r.left_for_review} need your choice (several or no suppliers at their location).` : "."), false); S.result = null;
    await refreshStatus(); await openLinkPanel(S.linkDb);
  });
  const sg = e.target.closest("[data-suggest]");
  if (sg) guard(sg, async () => {
    const g = groups[Number(sg.dataset.suggest)];
    const row = $(`#sugg-${sg.dataset.suggest}`);
    const { suggestions } = await api("POST", `/api/databases/${S.linkDb}/suggest`, { product: g.product, unit: g.unit, location: g.location || "" });
    row.hidden = false;
    row.firstElementChild.innerHTML = (suggestions.length ? `<ul class="results">${suggestions.map((s) => `<li><button data-linkto="${s.id}" data-g="${sg.dataset.suggest}">
      <span class="rname">${esc(s.name)}</span><span class="loc">${esc(s.location)}</span><span class="rmeta">${esc(s.product)}, ${esc(s.unit)}, ${esc(s.db)}${s.factor !== 1 ? `, x ${fmt(s.factor)}` : ""}${s.recorded_candidate ? ", producer in this import" : ""}${g.location && !s.same_location ? ", other location" : ""}</span></button></li>`).join("")}</ul>`
      : '<p class="hint">No dataset with a matching name and unit. Search below.</p>') +
      `<div class="row"><input class="grow" data-linksearch="${sg.dataset.suggest}" placeholder="Search another name"></div><ul class="results" data-linkres="${sg.dataset.suggest}"></ul>`;
  });
  const lt = e.target.closest("[data-linkto]");
  if (lt) guard(lt, async () => {
    const g = groups[Number(lt.dataset.g)];
    const r = await api("POST", `/api/databases/${S.linkDb}/link`, { product: g.product, unit: g.unit, location: g.location || "", target_id: Number(lt.dataset.linkto) });
    toast(`Linked ${r.linked} input(s).`); S.result = null;
    await refreshStatus(); await openLinkPanel(S.linkDb);
  });
  const ul = e.target.closest("[data-unlink]");
  if (ul) guard(ul, async () => {
    const g = groups[Number(ul.dataset.unlink)];
    await api("POST", `/api/databases/${S.linkDb}/unlink`, { product: g.product, unit: g.unit, location: g.location || "" });
    S.result = null; await refreshStatus(); await openLinkPanel(S.linkDb);
  });
});
$("#linkPanel").addEventListener("input", async (e) => {
  const inp = e.target.closest("[data-linksearch]");
  if (!inp || inp.value.trim().length < 2) return;
  const i = inp.dataset.linksearch;
  const { results } = await api("GET", "/api/search?q=" + encodeURIComponent(inp.value.trim()));
  $(`[data-linkres="${i}"]`).innerHTML = results.slice(0, 12).map((s) => `<li><button data-linkto="${s.id}" data-g="${i}">
    <span class="rname">${esc(s.name)}</span><span class="loc">${esc(s.location)}</span><span class="rmeta">${esc(s.product)}, ${esc(s.unit)}, ${esc(s.db)}</span></button></li>`).join("");
});

function renderMethodFamilies() {
  const fams = {};
  S.methods.forEach((m) => (fams[m.family] = fams[m.family] || []).push(m));
  const names = Object.keys(fams);
  $("#methodFamilies").innerHTML = names.length ? names.map((f) => {
    const sets = [...new Set(fams[f].flatMap((m) => m.nw_sets))];
    const matched = fams[f].reduce((a, m) => a + m.n_cfs, 0);
    const note = fams[f][0].note;
    return `<li><span class="grow"><b>${esc(f)}</b><br><span class="meta">${fams[f].length} categor${fams[f].length === 1 ? "y" : "ies"}, ${matched.toLocaleString("en-US")} factors matched to library flows${sets.length ? ", normalisation: " + sets.map(esc).join(", ") : ""}</span>
      ${note ? `<br><span class="meta">${esc(note)}</span>` : ""}</span>
    <button class="ghost danger" data-delfam="${esc(f)}">Remove</button></li>`;
  }).join("") : '<li class="empty">No impact methods yet.</li>';
}
$("#methodFamilies").addEventListener("click", (e) => {
  const b = e.target.closest("[data-delfam]");
  if (b && confirm(`Remove method "${b.dataset.delfam}" from the library?`))
    guard(b, async () => { await api("POST", "/api/methods/delete", { family: b.dataset.delfam }); S.result = null; await refreshStatus(); });
});

/* ---------------- background jobs ---------------- */
function watchJob(job, { onDone, quiet } = {}) {
  const box = $("#jobBox");
  box.hidden = false; box.className = "job";
  return new Promise((resolve) => {
    const tick = async () => {
      let j;
      try { j = (await api("GET", "/api/jobs/" + job.id)).job; } catch (e) { setTimeout(tick, 1500); return; }
      box.innerHTML = `<b>${esc(j.label)}</b><br>${esc(j.message)}<progress max="100" value="${j.progress}"></progress>
        ${j.status === "running" ? `<button class="ghost" data-cancel="${j.id}">Cancel</button>` : ""}`;
      if (j.status === "running") { setTimeout(tick, 700); return; }
      if (j.status === "error") {
        box.className = "job err"; box.innerHTML = `<b>${esc(j.label)}: stopped</b><br>${esc(j.error)}`;
        toast(j.error, true);
      } else if (j.status === "cancelled") {
        box.innerHTML = `<b>${esc(j.label)}</b><br>Cancelled.`; setTimeout(() => (box.hidden = true), 4000);
      } else {
        const r = j.result || {};
        const warn = (r.warnings || []).join(" ");
        const parts = [];
        if (typeof r.activities === "number" && r.activities) parts.push(`${r.activities.toLocaleString("en-US")} datasets`);
        if (typeof r.methods === "number" && r.methods) parts.push(`${r.methods} impact categories`);
        if (typeof r.factors === "number") parts.push(`${r.factors} factors`);
        if (typeof r.mappings === "number") parts.push(`${r.mappings} mappings, ${r.factors_added} factors added`);
        const ir = r.integrity_report;
        const irHtml = ir ? `<details><summary>Import integrity report: ${esc(ir.result || "")}</summary><table><tbody>${Object.entries(ir.contents || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${Number(v).toLocaleString("en-US")}</td></tr>`).join("")}<tr><td>Largest matrix residual</td><td class="num">${ir.matrix_residual != null ? Number(ir.matrix_residual).toExponential(1) : "-"}</td></tr></tbody></table><p class="hint">Checked: ${esc((ir.checks || []).join("; "))}.</p></details>` : "";
        box.innerHTML = `<b>${esc(j.label)}</b><br>Done${parts.length ? ": " + parts.join(", ") : ""}.${warn ? "<br>" + esc(warn) : ""}${irHtml}`;
        if (!quiet) toast(`${j.label}: done`);
        setTimeout(() => (box.hidden = true), ir ? 60000 : warn ? 30000 : 6000);
        if (onDone) await onDone(j);
      }
      resolve(j);
    };
    tick();
  });
}
$("#jobBox").addEventListener("click", (e) => {
  const b = e.target.closest("[data-cancel]");
  if (b) guard(b, () => api("POST", `/api/jobs/${b.dataset.cancel}/cancel`));
});
async function runImport(btn, path, body) {
  return guard(btn, async () => {
    const { job } = await api("POST", path, body);
    await watchJob(job, { onDone: async () => { S.result = null; await refreshStatus(); } });
  });
}
$("#btnTutorial").addEventListener("click", (e) => runImport(e.target, "/api/import/tutorial"));
$("#btnEsImport").addEventListener("click", (e) => runImport(e.target, "/api/import/ecospold", {
  folder: $("#esFolder").value, name: $("#esName").value.trim() || "ecoinvent", version: $("#esVersion").value.trim(), system_model: $("#esModel").value }));
$("#btnOfImport").addEventListener("click", (e) => {
  const fmtSel = $("#ofFormat").value;
  const body = { path: $("#ofPath").value, name: $("#ofName").value.trim() || $("#ofFormat").selectedOptions[0].textContent.split(" (")[0] };
  if (fmtSel === "ecospold1" || fmtSel === "jsonld") body.path = $("#ofPath").value;
  runImport(e.target, `/api/import/${fmtSel}`, body);
});
$("#btnLcImport").addEventListener("click", (e) => runImport(e.target, "/api/import/lcia-xlsx", { path: $("#lcPath").value }));
$("#btnCsvImport").addEventListener("click", (e) => runImport(e.target, "/api/import/cf-csv", { path: $("#csvPath").value }));
$("#btnNwImport").addEventListener("click", (e) => runImport(e.target, "/api/import/nw-csv", { path: $("#nwPath").value }));
$("#btnMapImport").addEventListener("click", (e) => runImport(e.target, "/api/import/mapping", { path: $("#mapPath").value }));
$("#btnBenchmark").addEventListener("click", (e) => guard(e.target, async () => {
  const { job } = await api("POST", "/api/benchmark", { path: $("#bmPath").value });
  await watchJob(job, { quiet: true, onDone: async (j) => {
    const r = j.result;
    $("#bmOut").innerHTML = `<p><b>${r.compared} results compared.</b> Median deviation ${r.median_abs_deviation_percent == null ? "-" : r.median_abs_deviation_percent.toFixed(3) + " %"},
      largest ${r.max_abs_deviation_percent == null ? "-" : r.max_abs_deviation_percent.toFixed(3) + " %"}; ${r.within_0_1_percent} within 0.1 %, ${r.within_1_percent} within 1 %.
      ${r.n_missing ? `${r.n_missing} rows could not be matched (first: ${esc(r.missing[0])}).` : ""}</p>
      <div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Category</th><th class="num">Reference</th><th class="num">Cyclia</th><th class="num">Deviation</th></tr></thead><tbody>
      ${r.rows.slice().sort((a, b) => Math.abs(b.deviation_percent || 0) - Math.abs(a.deviation_percent || 0)).slice(0, 40).map((x) => `<tr><td>${esc(x.activity)} [${esc(x.location)}]</td><td>${esc(x.category)}</td>
      <td class="num">${fmt(x.reference)}</td><td class="num">${fmt(x.cyclia)}</td><td class="num">${x.deviation_percent == null ? "-" : x.deviation_percent.toFixed(3) + " %"}</td></tr>`).join("")}</tbody></table></div>`;
  } });
}));
$$("[data-template]").forEach((b) => b.addEventListener("click", () => guard(b, async () => {
  const t = await api("GET", "/api/templates");
  const pre = $(`[data-template-out="${b.dataset.template}"]`);
  const notes = { cf_csv: "\nEmpty subcompartment = every subcompartment. flow_uuid and location are optional.",
    nw_csv: "\nnormalised = result / normalisation; weighted = normalised x weighting.",
    mapping_csv: "\nThe FEDEFL/GLAD mapping format (SourceFlowName, SourceFlowContext, TargetFlowName, ...) is read as it is.",
    benchmark_csv: "\nOne row per dataset and category. Export reference values from openLCA, Brightway or ecoinvent's LCIA results." };
  pre.textContent = t[b.dataset.template] + (notes[b.dataset.template] || "");
  pre.hidden = !pre.hidden;
})));

let eiReleases = [];
$("#btnEiList").addEventListener("click", (e) => guard(e.target, async () => {
  $("#eiHint").textContent = "Connecting to ecoinvent...";
  try { eiReleases = (await api("POST", "/api/ecoinvent/releases", { username: $("#eiUser").value, password: $("#eiPass").value })).releases; }
  finally { $("#eiHint").textContent = ""; }
  if (!eiReleases.length) throw new Error("Your ecoinvent account has no releases available.");
  $("#eiVersion").innerHTML = eiReleases.map((r) => `<option>${esc(r.version)}</option>`).join("");
  fillEiModels();
  $("#eiPick").hidden = false; $("#eiInstallRow").hidden = false;
}));
function fillEiModels() {
  const r = eiReleases.find((x) => x.version === $("#eiVersion").value);
  $("#eiModel").innerHTML = (r ? r.system_models : []).map((m) => `<option>${esc(m)}</option>`).join("");
}
$("#eiVersion").addEventListener("change", fillEiModels);
$("#btnEiInstall").addEventListener("click", (e) => guard(e.target, async () => {
  const validate = $("#eiValidate").checked;
  const { job } = await api("POST", "/api/ecoinvent/install", { username: $("#eiUser").value, password: $("#eiPass").value,
    version: $("#eiVersion").value, system_model: $("#eiModel").value, validate, sample: Number($("#eiSample").value), inventories: $("#eiInventories").checked, all_methods: $("#eiAllMethods").checked });
  await watchJob(job, { onDone: async (j) => {
    S.result = null; await refreshStatus();
    const b = j.result && j.result.benchmark;
    if (b) renderBench(b, $("#eiValOut"));
  } });
}));
$("#btnEiValidate").addEventListener("click", (e) => guard(e.target, async () => {
  const { job } = await api("POST", "/api/ecoinvent/validate", { username: $("#eiUser").value, password: $("#eiPass").value,
    version: $("#eiVersion").value, system_model: $("#eiModel").value, sample: Number($("#eiSample").value), inventories: $("#eiInventories").checked, all_methods: $("#eiAllMethods").checked });
  $("#eiValOut").innerHTML = '<p class="hint">Downloading ecoinvent\'s results and comparing; progress is shown at the bottom left.</p>';
  const fin = await watchJob(job, { quiet: true, onDone: async (j) => renderBench(j.result, $("#eiValOut")) });
  if (fin && fin.status === "error") $("#eiValOut").innerHTML = `<p class="danger">${esc(fin.error)}</p>`;
}));

document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-pick]");
  if (!b) return;
  e.preventDefault();
  if (!desktop) { toast("Type or paste the full path. File browsing works in the desktop app."); $("#" + b.dataset.target).focus(); return; }
  const p = b.dataset.pick === "folder" ? await desktop.pickFolder() : await desktop.pickFile(b.dataset.ext);
  if (!p) return;
  $("#" + b.dataset.target).value = p;
  const base = p.split(/[\\/]/).pop();
  if (b.dataset.target === "esFolder" && !$("#esName").value) {
    const v = base.match(/3\.\d+/);
    $("#esName").value = base.replace(/_ecoSpold02/i, "").replace(/_/g, " ");
    if (v) $("#esVersion").value = v[0];
    if (/apos/i.test(base)) $("#esModel").value = "APOS"; else if (/conseq/i.test(base)) $("#esModel").value = "consequential";
  }
  if (b.dataset.target === "ofPath" && !$("#ofName").value) $("#ofName").value = base.replace(/\.(zip|csv|xml)$/i, "");
});

/* ---------------- models & scope ---------------- */
const SCOPE_FIELDS = ["fu_description", "goal", "reasons", "application", "audience", "comparative", "author", "boundary",
  "stage_system", "geography", "period", "allocation", "alloc_share", "alloc_basis", "main_mass", "cutoff", "assumptions", "dq_requirements", "horizon",
  "approach", "technology", "lcc_currency", "lcc_rate", "alloc_property", "lcc_period"];
const CONC_FIELDS = ["conclusions", "limitations", "recommendations", "review", "review_status"];

function fillStageSystems() {
  const sel = $("#scopeForm").stage_system;
  const presets = (S.status && S.status.stage_presets) || {};
  if (sel.options.length !== Object.keys(presets).length + 1)
    sel.innerHTML = '<option value="">Free text</option>' + Object.keys(presets).map((k) => `<option>${esc(k)}</option>`).join("");
}
function stageOptions() {
  const sys = S.model && S.model.scope && S.model.scope.stage_system;
  const presets = (S.status && S.status.stage_presets) || {};
  const used = S.model ? S.model.inputs.map((i) => i.stage).filter(Boolean) : [];
  return [...new Set([...(presets[sys] || presets.General || []), ...used])];
}
async function refreshModels(selectId) {
  S.models = (await api("GET", "/api/models")).models;
  const keep = selectId || (S.model && S.model.id) || ls.get(projKey("model"), null);
  renderModelSelect();
  if (keep && S.models.some((m) => m.id === keep)) await loadModel(keep);
  else if (S.models[0]) await loadModel(S.models[0].id);
  else { S.model = null; fillScope(); }
}
function renderModelSelect() {
  $("#modelSelect").innerHTML = S.models.length
    ? S.models.map((m) => `<option value="${m.id}">${esc(m.name)}${m.scope.kind === "process" ? " (process)" : ""}</option>`).join("")
    : "<option value=''>No models yet</option>";
  if (S.model) $("#modelSelect").value = S.model.id;
}
async function loadModel(id) {
  S.model = (await api("GET", "/api/models/" + id)).model;
  ls.set(projKey("model"), id);
  $("#modelSelect").value = id;
  if (S.step === "scope") { fillScope(); loadParams(); }
  if (S.step === "inventory") { renderInventory(); loadComments(); }
  if (S.step === "scope") loadVersions();
  renderLockBanners();
  markSteps();
}
$("#modelSelect").addEventListener("change", (e) => {
  if (!e.target.value) return;
  S.result = null;
  guard(null, async () => { await loadModel(Number(e.target.value)); go(S.step); });
});
function fillScope() {
  const f = $("#scopeForm");
  const m = S.model || { name: "", product: "", unit: "", amount: 1, scope: {} };
  f.name.value = m.name || ""; f.product.value = m.product || ""; f.unit.value = m.unit || ""; f.amount.value = m.amount ?? 1;
  const sc = m.scope || {};
  SCOPE_FIELDS.forEach((k) => { if (f[k]) f[k].value = sc[k] ?? (f[k].tagName === "SELECT" ? f[k].options[0].value : (k === "horizon" ? 100 : "")); });
  f.dynamic.checked = !!sc.dynamic;
  f.main_value.value = sc.alloc_basis ? (sc["main_" + sc.alloc_basis] ?? "") : "";
  renderCoproducts(sc.coproducts || []);
  toggleAlloc();
  $("#btnDeleteModel").hidden = $("#btnDuplicateModel").hidden = !S.model;
  $("#processNote").hidden = !(sc.kind === "process");
  $("#processNote").textContent = sc.kind === "process" ? `Editable process copied from ${sc.copied_from || "a database dataset"}. Change its lines in step 3, then use it in other models from "My models & processes".` : "";
}
function renderCoproducts(cps) {
  $("#cpRows").innerHTML = cps.map((c) => `<tr><td><input data-cp="name" value="${esc(c.name || "")}"></td>
    <td><input data-cp="mass" type="number" step="any" min="0" value="${esc(c.mass ?? "")}"></td>
    <td><input data-cp="price" type="number" step="any" min="0" value="${esc(c.price ?? "")}"></td>
    <td><input data-cp="energy" type="number" step="any" min="0" value="${esc(c.energy ?? "")}"></td>
    <td><input data-cp="physical" type="number" step="any" min="0" value="${esc(c.physical ?? "")}"></td>
    <td><button type="button" class="ghost danger" data-cprm>Remove</button></td></tr>`).join("");
  updateAllocShare();
}
function readCoproducts() {
  return $$("#cpRows tr").map((tr) => {
    const o = {};
    $$("[data-cp]", tr).forEach((i) => (o[i.dataset.cp] = i.type === "number" ? (i.value === "" ? "" : Number(i.value)) : i.value.trim()));
    return o;
  }).filter((c) => c.name || c.mass !== "" || c.price !== "" || c.energy !== "" || c.physical !== "");
}
function toggleAlloc() {
  const basis = $("#scopeForm").alloc_basis.value;
  $$(".alloc-manual").forEach((el) => (el.hidden = !!basis));
  $$(".alloc-cp").forEach((el) => (el.hidden = !basis));
  $$(".alloc-phys").forEach((el) => (el.hidden = basis !== "physical"));
  updateAllocShare();
}
function updateAllocShare() {
  const f = $("#scopeForm");
  const basis = f.alloc_basis.value;
  if (!basis) return;
  const main = Number(f.main_value.value) || 0;
  const others = readCoproducts().reduce((a, c) => a + (Number(c[basis]) || 0), 0);
  $("#allocShare").textContent = main > 0 ? `Share for this product: ${(100 * main / (main + others)).toFixed(2)} %` : "Enter this product's value to compute the share.";
}
$("#scopeForm").alloc_basis.addEventListener("change", toggleAlloc);
$("#scopeForm").addEventListener("input", (e) => { if (e.target.closest(".alloc-cp") || e.target.name === "main_value") updateAllocShare(); });
$("#btnAddCp").addEventListener("click", () => { renderCoproducts([...readCoproducts(), { name: "" }]); });
$("#cpRows").addEventListener("click", (e) => { if (e.target.closest("[data-cprm]")) { e.target.closest("tr").remove(); updateAllocShare(); } });

async function saveModelScope(extra = {}) {
  if (!S.status.project) throw new Error("Open a project first (step 1).");
  const f = $("#scopeForm");
  const scope = { ...((S.model && S.model.scope) || {}) };
  SCOPE_FIELDS.forEach((k) => (scope[k] = f[k].value.trim()));
  scope.dynamic = f.dynamic.checked;
  scope.coproducts = readCoproducts();
  ["main_mass", "main_price", "main_energy", "main_physical"].forEach((k) => { if (k !== "main_mass") delete scope[k]; });
  if (scope.alloc_basis) scope["main_" + scope.alloc_basis] = f.main_value.value;
  if (scope.alloc_basis === "mass" && !f.main_value.value) scope.main_mass = f.main_mass.value;
  Object.assign(scope, extra);
  if (!f.name.value.trim()) throw new Error("Give the model a name.");
  if (!(Number(f.amount.value) > 0)) throw new Error("The functional unit amount must be greater than zero.");
  const { model } = await api("POST", "/api/models", { id: S.model ? S.model.id : undefined, name: f.name.value.trim(),
    product: f.product.value.trim(), unit: f.unit.value.trim(), amount: Number(f.amount.value), scope });
  S.model = model;
  await refreshModels(model.id);
  return model;
}
$("#scopeForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button[type=submit]", e.target), async () => {
    await saveModelScope(); S.result = null;
    $("#scopeSaved").textContent = "Saved."; setTimeout(() => ($("#scopeSaved").textContent = ""), 2500);
    toast("Goal & scope saved. Next: the inventory.");
    loadParams();
  });
});
$("#btnNewModel").addEventListener("click", () => {
  S.model = null; S.result = null; fillScope(); renderModelSelect(); loadParams();
  $("#modelSelect").value = ""; $("#scopeForm").name.focus(); markSteps();
});
$("#btnDuplicateModel").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.model) return;
  const name = prompt("Name of the copy:", S.model.name + " (alternative)");
  if (!name) return;
  const { model } = await api("POST", `/api/models/${S.model.id}/duplicate`, { name });
  S.result = null; await refreshModels(model.id); go("scope");
  toast("Copy created. Change it to build the alternative.");
}));
$("#btnDeleteModel").addEventListener("click", (e) => {
  if (!S.model || !confirm(`Delete model "${S.model.name}" and its inventory?`)) return;
  guard(e.target, async () => { await api("DELETE", "/api/models/" + S.model.id); S.model = null; S.result = null; await refreshModels(); go("scope"); });
});

/* ---------------- parameters & scenarios ---------------- */
const DIST = ["", "lognormal, GSD", "normal, SD", "triangular", "uniform"];
async function loadParams() {
  if (!S.status || !S.status.project) return;
  S.params = await api("GET", "/api/parameters" + (S.model ? `?model_id=${S.model.id}` : ""));
  const rows = [...S.params.project.map((p) => ({ ...p, where: "project" })), ...(S.params.model || []).map((p) => ({ ...p, where: "model" }))];
  const vals = S.params.values || {};
  $("#paramRows").innerHTML = rows.length ? rows.map((p) => `<tr><td>${p.where === "project" ? "Project" : "This model"}</td><td><code>${esc(p.name)}</code></td>
    <td>${p.formula ? `<code>${esc(p.formula)}</code>` : fmt(p.value)}</td><td>${esc(p.unit || "")}</td>
    <td>${p.utype ? `${DIST[p.utype]}: ${[p.p1, p.p2, p.p3].filter((x) => x !== null).map(fmt).join(", ")}` : "-"}</td>
    <td class="num">${vals[p.name] !== undefined ? fmt(vals[p.name]) : "-"}</td>
    <td><button class="ghost danger" data-delparam="${p.id}">Remove</button></td></tr>`).join("")
    : '<tr><td colspan="7" class="empty">No parameters yet.</td></tr>';
  if (S.params.error) toast(S.params.error, true);
}
$("#paramForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button", e.target), async () => {
    const f = e.target;
    const raw = f.value.value.trim();
    const isNum = raw !== "" && !Number.isNaN(Number(raw));
    if (f.scope.value === "model" && !S.model) throw new Error("Save the model first, or choose 'Whole project'.");
    await api("POST", "/api/parameters", { model_id: f.scope.value === "model" ? S.model.id : null, name: f.name.value.trim(),
      value: isNum ? Number(raw) : 0, formula: isNum ? "" : raw, unit: f.unit.value.trim(), utype: Number(f.utype.value),
      p1: f.p1.value, p2: f.p2.value, p3: f.p3.value });
    f.reset(); S.result = null; await loadParams(); toast("Parameter saved.");
  });
});
$("#paramRows").addEventListener("click", (e) => {
  const b = e.target.closest("[data-delparam]");
  if (b) guard(b, async () => { await api("DELETE", "/api/parameters/" + b.dataset.delparam); S.result = null; await loadParams(); });
});
async function renderScenarios() {
  if (!S.status || !S.status.project) return;
  const { scenarios } = await api("GET", "/api/scenarios");
  S.status.scenarios = scenarios;
  $("#scenarioList").innerHTML = scenarios.length ? scenarios.map((s) => `<li><span class="grow"><b>${esc(s.name)}</b><br>
    <span class="meta">${Object.entries(s.overrides).map(([k, v]) => `${esc(k)} = ${fmt(v)}`).join(", ") || "no values"}</span></span>
    <button class="ghost danger" data-delscen="${s.id}">Remove</button></li>`).join("") : '<li class="empty">No scenarios yet.</li>';
}
$("#scenarioForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button", e.target), async () => {
    const f = e.target;
    const overrides = {};
    for (const part of f.overrides.value.split(/[,;\n]/)) {
      if (!part.trim()) continue;
      const [k, v] = part.split("=").map((x) => x && x.trim());
      if (!k || v === undefined || v === "" || Number.isNaN(Number(v))) throw new Error(`Write values as name=number, e.g. thickness=0.3 (problem: "${part.trim()}").`);
      overrides[k] = Number(v);
    }
    await api("POST", "/api/scenarios", { name: f.name.value.trim(), overrides });
    f.reset(); await renderScenarios(); toast("Scenario saved.");
  });
});
$("#scenarioList").addEventListener("click", (e) => {
  const b = e.target.closest("[data-delscen]");
  if (b) guard(b, async () => { await api("DELETE", "/api/scenarios/" + b.dataset.delscen); await renderScenarios(); });
});
function renderScenarioSelect() {
  const prev = $("#scenarioSel").value;
  $("#scenarioSel").innerHTML = '<option value="">Base values</option>' + (S.status.scenarios || []).map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  $("#scenarioSel").value = (S.status.scenarios || []).some((s) => String(s.id) === prev) ? prev : "";
}

/* ---------------- inventory ---------------- */
function updateSearchUI() {
  const hints = {
    activity: 'Pick "market for" datasets unless you know the supplier; they include transport and losses. Select a dataset to add it, to replace a line with it, or to copy it as an editable process.',
    flow: "Emissions and resources that happen inside your own system, e.g. CO2 from on-site combustion or N2O from a field. Pick the right compartment.",
    model: "Use another model or an editable process as a component, e.g. a wall inside a building.",
    fixed: "",
  };
  $("#searchHint").textContent = hints[S.src];
  $("#searchRow").hidden = S.src === "fixed";
  $("#searchResults").hidden = S.src === "fixed";
  $("#epdForm").hidden = S.src !== "fixed";
  $("#searchDb").hidden = $("#searchLoc").hidden = S.src !== "activity";
  if (S.src === "fixed") renderEpdForm();
  $("#replaceBanner").hidden = !S.replaceLine;
  if (S.replaceLine) {
    const l = S.model && S.model.inputs.find((i) => i.id === S.replaceLine);
    $("#replaceBanner").innerHTML = `Replacing <b>${esc(l ? l.target.name : "")}</b>: select the new dataset below. <button class="ghost" data-cancelreplace>Cancel</button>`;
  }
}
$("#replaceBanner").addEventListener("click", (e) => { if (e.target.closest("[data-cancelreplace]")) { S.replaceLine = null; updateSearchUI(); closeDetail(); } });
$$(".finder .tabs button").forEach((b) => b.addEventListener("click", () => {
  $$(".finder .tabs button").forEach((x) => x.classList.toggle("on", x === b));
  S.src = b.dataset.src;
  $("#searchBox").placeholder = S.src === "flow" ? "Search, e.g. methane, carbon dioxide, water" : S.src === "model" ? "Filter your models" : "Search, e.g. cement, electricity France, lorry";
  updateSearchUI(); closeDetail(); doSearch();
}));
let searchTimer, searchSeq = 0;
["#searchBox", "#searchLoc", "#searchDb"].forEach((s) => $(s).addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(doSearch, 250); }));

async function doSearch() {
  const q = $("#searchBox").value.trim();
  const ul = $("#searchResults");
  const seq = ++searchSeq;
  if (S.src === "fixed") return;
  if (S.src === "model") {
    const list = S.models.filter((m) => !S.model || m.id !== S.model.id).filter((m) => !q || m.name.toLowerCase().includes(q.toLowerCase()));
    ul.innerHTML = list.length ? list.map((m) => `<li><button data-kind="model" data-id="${m.id}"><span class="rname">${esc(m.name)}</span>
      <span class="rmeta">${m.scope.kind === "process" ? '<span class="tag">process</span>' : ""}${fmt(m.amount)} ${esc(m.unit)} of ${esc(m.product)}, ${m.n_inputs} lines</span></button></li>`).join("")
      : '<li class="empty">No other models in this project yet.</li>';
    return;
  }
  if (q.length < 2) { ul.innerHTML = ""; return; }
  try {
    if (S.src === "flow") {
      const { results } = await api("GET", "/api/flows?q=" + encodeURIComponent(q));
      if (seq !== searchSeq) return;
      ul.innerHTML = results.length ? results.map((f) => `<li><button data-kind="flow" data-id="${f.id}" data-unit="${esc(f.unit)}">
        <span class="rname">${esc(f.name)}</span><span class="rmeta">${esc(f.compartment)}${f.subcompartment ? " / " + esc(f.subcompartment) : ""}, ${esc(f.unit)}</span></button></li>`).join("")
        : '<li class="empty">No elementary flow matches. Try one shorter word.</li>';
    } else {
      const { results } = await api("GET", `/api/search?q=${encodeURIComponent(q)}&db=${$("#searchDb").value}&loc=${encodeURIComponent($("#searchLoc").value.trim())}`);
      if (seq !== searchSeq) return;
      ul.innerHTML = results.length ? results.map((a) => `<li><button data-kind="activity" data-id="${a.id}">
        <span class="rname">${esc(a.name)}</span><span class="loc">${esc(a.location)}</span>
        <span class="rmeta"><span class="tag ${a.kind}">${a.kind}</span>${esc(a.product)}, ${esc(a.unit)}, ${esc(a.db)}</span></button></li>`).join("")
        : '<li class="empty">Nothing found. Try fewer or more general words, e.g. "cement" instead of "Portland cement CEM I".</li>';
    }
  } catch (e) { toast(e.message, true); }
}
$("#searchResults").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-kind]");
  if (!b) return;
  $$("#searchResults button").forEach((x) => x.classList.toggle("sel", x === b));
  guard(null, () => openDetail(b.dataset.kind, Number(b.dataset.id), b));
});

async function openDetail(kind, id, btn) {
  const d = $("#detail");
  let title, sub, unitList, body = "", extra = "";
  if (kind === "activity") {
    const { activity: a } = await api("GET", "/api/activity/" + id);
    title = a.name; unitList = a.units;
    sub = `${esc(a.product)}, ${esc(a.location)}, ${esc(a.db)}`;
    body = (a.inputs.length ? `<h4>Main inputs per 1 ${esc(a.unit)}</h4><table>${a.inputs.slice(0, 8).map((i) =>
      `<tr><td>${esc(i.name)} <span class="hint">[${esc(i.location)}]</span></td><td class="num">${fmt(i.amount)} ${esc(i.unit)}</td></tr>`).join("")}</table>` : "") +
      (a.emissions.length ? `<h4>Direct emissions per 1 ${esc(a.unit)}</h4><table>${a.emissions.slice(0, 6).map((f) =>
      `<tr><td>${esc(f.name)} <span class="hint">${esc(f.compartment)}</span></td><td class="num">${fmt(f.amount)} ${esc(f.unit)}</td></tr>`).join("")}</table>` : "") +
      (a.comment ? `<details><summary>Dataset description</summary><p class="hint">${esc(a.comment)}</p></details>` : "");
    if (a.production < 0) body = `<p class="banner">This is a <b>waste treatment</b> dataset. Enter the amount of waste you send to it as a positive number; Cyclia counts its burdens. To model avoided treatment, tick "Avoided product".</p>` + body;
    extra = `<div class="row">${S.replaceLine ? `<button class="primary" data-doreplace="${id}">Replace the line with this dataset</button>` : ""}
      <button class="ghost" data-copyproc="${id}">Copy as editable process</button></div>`;
  } else if (kind === "flow") {
    title = $(".rname", btn).textContent; sub = esc($(".rmeta", btn).textContent);
    unitList = (await api("GET", "/api/units?unit=" + encodeURIComponent(btn.dataset.unit))).units;
    body = '<p class="hint">Enter the amount emitted, or the resource taken, per functional unit.</p>';
  } else {
    const m = S.models.find((x) => x.id === id);
    title = m.name; unitList = [m.unit]; sub = `${fmt(m.amount)} ${esc(m.unit)} of ${esc(m.product)}`;
    body = `<p class="hint">Its results are scaled per ${esc(m.unit)} of that model.</p>`;
  }
  const dyn = S.model && S.model.scope && S.model.scope.dynamic;
  d.innerHTML = `<button class="ghost close" aria-label="Close">Close</button><h3>${esc(title)}</h3><p class="hint">${sub}</p>${extra}
    <form class="add" novalidate>
      <label>Amount per functional unit, or formula<input name="amount" required placeholder="e.g. 12 or thickness * 1800"></label>
      <label>Unit<select name="unit">${unitList.map((u) => `<option>${esc(u)}</option>`).join("")}</select></label>
      ${unitList.includes("t*km") ? `<div class="full tkm"><span class="hint">Transport helper:</span>
        <input type="number" min="0" step="any" data-tkm="kg" placeholder="mass, kg" aria-label="Mass carried in kg">
        <span class="hint">kg carried</span><input type="number" min="0" step="any" data-tkm="km" placeholder="distance, km" aria-label="Distance in km">
        <span class="hint">km</span></div>` : ""}
      <label class="full">Life cycle stage<input name="stage" list="stageList" value="${esc(ls.get("cyclia.lastStage", ""))}" placeholder="e.g. A1 Raw material supply"></label>
      <label class="full">Data source<input name="comment" placeholder="e.g. supplier EPD, own measurement, literature"></label>
      ${dyn ? '<label>Year of emission<input name="year" type="number" min="0" step="any" value="0"></label>' : ""}
      <label class="check"><input type="checkbox" name="avoided"> Avoided product (credit from system expansion)</label>
      <button class="primary" type="submit">Add to model</button>
    </form>${body}`;
  refreshStageList();
  d.hidden = false;
  $(".inv").classList.add("with-detail");
  $(".close", d).addEventListener("click", closeDetail);
  const rep = $("[data-doreplace]", d);
  if (rep) rep.addEventListener("click", () => guard(rep, async () => {
    const { model } = await api("POST", `/api/inputs/${S.replaceLine}/replace`, { ref_id: id });
    S.model = model; S.replaceLine = null; S.result = null; updateSearchUI(); closeDetail(); renderInventory(); markSteps();
    toast("Line replaced. Undo is available.");
  }));
  const cp = $("[data-copyproc]", d);
  if (cp) cp.addEventListener("click", () => guard(cp, async () => {
    const { model } = await api("POST", `/api/activity/${id}/copy`, {});
    await refreshModels(S.model ? S.model.id : model.id);
    toast(`"${model.name}" created. Open it from the Model menu to edit its inputs.`);
  }));
  $("form", d).addEventListener("submit", (ev) => {
    ev.preventDefault();
    guard($("button[type=submit]", d), async () => {
      if (!S.model) throw new Error("Create the model in step 2 first.");
      const f = ev.target;
      const raw = f.amount.value.trim();
      if (!raw) throw new Error("Enter an amount or a formula.");
      const isNum = !Number.isNaN(Number(raw));
      const { model } = await api("POST", `/api/models/${S.model.id}/inputs`, {
        kind, ref_id: id, amount: isNum ? Number(raw) : undefined, formula: isNum ? undefined : raw, unit: f.unit.value,
        stage: f.stage.value.trim(), comment: f.comment.value.trim(), avoided: f.avoided.checked,
        year: f.year ? Number(f.year.value) || 0 : 0, label: kind === "activity" ? "" : title });
      ls.set("cyclia.lastStage", f.stage.value.trim());
      S.model = model; S.result = null;
      renderInventory(); markSteps();
      toast(`Added: ${title}`);
      f.amount.value = ""; f.comment.value = ""; f.avoided.checked = false; f.amount.focus();
    });
  });
  $$("[data-tkm]", d).forEach((x) => x.addEventListener("input", () => {
    const kg = Number($("[data-tkm=kg]", d).value), km = Number($("[data-tkm=km]", d).value);
    if (kg > 0 && km > 0) { $("input[name=amount]", d).value = String(Number((kg / 1000 * km).toPrecision(6))); $("select[name=unit]", d).value = "t*km"; }
  }));
  $("input[name=amount]", d).focus();
}
function closeDetail() { $("#detail").hidden = true; $(".inv").classList.remove("with-detail"); $$("#searchResults button").forEach((x) => x.classList.remove("sel")); }
function refreshStageList() { $("#stageList").innerHTML = stageOptions().map((s) => `<option value="${esc(s)}">`).join(""); }

function renderEpdForm() {
  const sel = S.methods.filter((m) => S.selectedMethods.has(m.id));
  const list = sel.length ? sel : S.methods;
  $("#epdValues").innerHTML = `<p class="hint">${sel.length ? "Categories selected in step 4." : "All categories; select some in step 4 to shorten this list."} Leave a value empty if the EPD does not declare it.</p>
    <div class="table-wrap"><table><thead><tr><th>Category</th><th>Value per declared unit</th></tr></thead><tbody>
    ${list.map((m) => `<tr><td>${esc(m.family)}: ${esc(m.category)} <span class="hint">${esc(m.unit)}</span></td><td><input type="number" step="any" data-epd="${m.id}"></td></tr>`).join("")}
    </tbody></table></div>
    <div class="form-grid"><label>Amount per functional unit<input name="amount" type="number" step="any" min="0"></label>
    <label>Life cycle stage<input name="stage" list="stageList" placeholder="A1-A3"></label></div>
    <button class="primary" type="submit">Add EPD line</button>`;
  refreshStageList();
}
$("#epdForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button[type=submit]", e.target), async () => {
    if (!S.model) throw new Error("Create the model in step 2 first.");
    const f = e.target;
    const impacts = $$("[data-epd]", f).filter((i) => i.value !== "").map((i) => {
      const m = S.methods.find((x) => x.id === Number(i.dataset.epd));
      return { family: m.family, category: m.category, indicator: m.indicator, value: Number(i.value) };
    });
    if (!f.name.value.trim()) throw new Error("Give the EPD product a name.");
    if (!f.unit.value.trim()) throw new Error("Give the declared unit.");
    const { model } = await api("POST", `/api/models/${S.model.id}/inputs`, { kind: "fixed", amount: Number(f.amount.value),
      unit: f.unit.value.trim(), stage: f.stage.value.trim(), comment: f.source.value.trim(), label: f.name.value.trim(),
      fixed: { name: f.name.value.trim(), unit: f.unit.value.trim(), location: f.location.value.trim(), source: f.source.value.trim(), impacts } });
    S.model = model; S.result = null; renderInventory(); markSteps(); f.reset(); renderEpdForm();
    toast("EPD line added.");
  });
});

const PED = ["Reliability", "Completeness", "Temporal correlation", "Geographical correlation", "Technological correlation"];
const PED_HELP = ["1 verified measurement ... 5 non-qualified estimate", "1 representative of all sites ... 5 unknown",
  "1 under 3 years old ... 5 over 15 years or unknown", "1 from the study area ... 5 unknown or very different area",
  "1 same technology ... 5 related process on lab scale"];
const unitCache = {};
async function unitsFor(u) {
  if (!unitCache[u]) unitCache[u] = (await api("GET", "/api/units?unit=" + encodeURIComponent(u))).units;
  return unitCache[u];
}
async function renderInventory() {
  const m = S.model;
  $("#invLead").textContent = m ? `Everything needed for ${fmt(m.amount)} ${m.unit} of ${m.product || m.name}.` : "Create a model in step 2 first.";
  const rows = m ? m.inputs : [];
  const dyn = !!(m && m.scope && (m.scope.dynamic || Number(m.scope.lcc_rate) > 0));
  $$(".col-year").forEach((el) => (el.hidden = !dyn));
  $("#invCount").textContent = rows.length ? `(${rows.length})` : "";
  $("#invEmpty").hidden = rows.length > 0;
  $("#btnUndo").disabled = !(m && m.history && m.history.length);
  $("#btnUndo").title = m && m.history && m.history.length ? `Undo: ${m.history[0].label}` : "Nothing to undo";
  refreshStageList();
  const unitLists = await Promise.all(rows.map((r) => (r.kind === "fixed" ? Promise.resolve([r.input_unit]) : unitsFor(r.target.unit || ""))));
  $("#invRows").innerHTML = rows.map((r, k) => {
    const opts = [...new Set([r.input_unit, ...unitLists[k]])].filter(Boolean);
    const conv = r.input_unit !== r.target.unit && r.target.unit && r.kind !== "fixed" ? `<span class="conv">= ${fmt(r.amount)} ${esc(r.target.unit)}</span>` : "";
    const amountCell = r.formula
      ? `<input class="formula" value="${esc(r.formula)}" aria-label="Formula" title="Formula">`
      : `<input class="amt" type="number" step="any" min="0" value="${r.input_amount}" aria-label="Amount">`;
    return `<tr data-id="${r.id}" class="${r.avoided ? "credit" : ""} ${r.missing ? "missing" : ""}">
      <td><input class="stage" list="stageList" value="${esc(r.stage)}" placeholder="stage" aria-label="Stage"></td>
      <td><div class="tname">${esc(r.label || r.target.name)}</div><div class="tsub">${esc([r.kind === "flow" ? "elementary flow" : r.kind === "model" ? "model" : r.kind === "fixed" ? "EPD values" : "", r.target.location, r.kind === "fixed" ? "" : r.target.db].filter(Boolean).join(", "))}</div></td>
      <td><div class="amt-cell">${amountCell}<select class="unit" aria-label="Unit" ${r.kind === "fixed" ? "disabled" : ""}>${opts.map((u) => `<option ${u === r.input_unit ? "selected" : ""}>${esc(u)}</option>`).join("")}</select>
        <button class="ghost fx" data-fx title="${r.formula ? "Use a fixed number" : "Use a formula of parameters"}">${r.formula ? "123" : "f(x)"}</button></div>${conv}</td>
      <td><input type="checkbox" class="avoided" ${r.avoided ? "checked" : ""} aria-label="Avoided product"></td>
      <td class="col-year" ${dyn ? "" : "hidden"}><input class="year" type="number" min="0" step="any" value="${r.year || 0}" aria-label="Year"></td>
      <td><div class="ped">${r.pedigree.map((v, i) => `<select class="s${v}" title="${PED[i]}: ${PED_HELP[i]}" aria-label="${PED[i]}" data-i="${i}">${[1, 2, 3, 4, 5].map((n) => `<option ${n === v ? "selected" : ""}>${n}</option>`).join("")}</select>`).join("")}</div></td>
      <td><select class="dtype" aria-label="Data type" title="Primary: measured or from the supplier. Secondary: database or literature. Estimate: your own assumption.">${[["", "type?"], ["primary", "primary"], ["secondary", "secondary"], ["estimate", "estimate"]].map(([v, t]) => `<option value="${v}" ${v === (r.data_type || "") ? "selected" : ""}>${t}</option>`).join("")}</select><input class="note" value="${esc(r.comment || "")}" placeholder="source" aria-label="Data source">${(() => { const n = S.comments.filter((c) => c.input_id === r.id && !c.resolved).length; return `<button class="ghost cbadge${n ? " has" : ""}" data-cline="${r.id}" title="Comments on this line">${n ? n + " note" + (n > 1 ? "s" : "") : "note"}</button>`; })()}</td>
      <td class="actions"><button class="ghost${r.source_ref || r.data_year || r.supplier || r.unit_cost != null ? " has-prov" : ""}" data-prov="${r.id}" title="Reference, year, supplier, verification and price">Details</button>${r.kind === "activity" ? `<button class="ghost" data-replace="${r.id}" title="Swap the dataset, keep the amount">Replace</button>` : ""}<button class="ghost danger" data-rm="${r.id}">Remove</button></td></tr>`;
  }).join("");
  if (!$("#diagram").hidden) renderDiagram();
}
async function patchLine(id, patch, rerender) {
  S.result = null;
  await api("PATCH", "/api/inputs/" + id, patch);
  S.model = (await api("GET", "/api/models/" + S.model.id)).model;
  if (rerender) renderInventory(); else $("#btnUndo").disabled = false;
  markSteps();
}
$("#invRows").addEventListener("change", (e) => {
  const tr = e.target.closest("tr");
  if (!tr) return;
  const id = Number(tr.dataset.id);
  const row = S.model.inputs.find((r) => r.id === id);
  const t = e.target;
  if (t.classList.contains("amt") || t.classList.contains("unit")) {
    if (row.formula && t.classList.contains("unit")) { guard(null, () => patchLine(id, { formula: row.formula, input_unit: t.value }, true)); return; }
    const amt = Number($(".amt", tr).value);
    if ($(".amt", tr).value === "" || !(amt >= 0)) { toast("Enter a positive amount.", true); $(".amt", tr).value = row.input_amount; return; }
    guard(null, () => patchLine(id, { input_amount: amt, input_unit: $(".unit", tr).value }, true));
  } else if (t.classList.contains("formula")) guard(null, () => patchLine(id, { formula: t.value.trim(), input_unit: $(".unit", tr).value }, true));
  else if (t.classList.contains("note")) guard(null, () => patchLine(id, { comment: t.value }));
  else if (t.classList.contains("dtype")) guard(null, () => patchLine(id, { data_type: t.value }));
  else if (t.classList.contains("stage")) guard(null, () => patchLine(id, { stage: t.value.trim() }));
  else if (t.classList.contains("year")) guard(null, () => patchLine(id, { year: Number(t.value) || 0 }));
  else if (t.classList.contains("avoided")) { tr.classList.toggle("credit", t.checked); guard(null, () => patchLine(id, { avoided: t.checked })); }
  else if (t.tagName === "SELECT" && t.dataset.i !== undefined) {
    const ped = [...row.pedigree]; ped[Number(t.dataset.i)] = Number(t.value); t.className = "s" + t.value;
    guard(null, () => patchLine(id, { pedigree: ped }));
  }
});
$("#invRows").addEventListener("click", (e) => {
  const cl = e.target.closest("[data-cline]");
  if (cl) { S.commentLine = Number(cl.dataset.cline); renderComments(); $("#commentForm").text.focus(); $("#commentsBlock").scrollIntoView({ block: "center" }); return; }
  const rm = e.target.closest("[data-rm]"), rp = e.target.closest("[data-replace]"), fx = e.target.closest("[data-fx]");
  if (rm) guard(rm, async () => { await api("DELETE", "/api/inputs/" + rm.dataset.rm); await loadModel(S.model.id); S.result = null; renderInventory(); });
  if (rp) {
    S.replaceLine = Number(rp.dataset.replace);
    $$(".finder .tabs button").forEach((x) => x.classList.toggle("on", x.dataset.src === "activity"));
    S.src = "activity"; updateSearchUI();
    const row = S.model.inputs.find((i) => i.id === S.replaceLine);
    $("#searchBox").value = (row.target.product || row.target.name || "").split(",")[0];
    doSearch(); $("#searchBox").focus(); window.scrollTo(0, 0);
  }
  if (fx) {
    const tr = fx.closest("tr");
    const row = S.model.inputs.find((r) => r.id === Number(tr.dataset.id));
    if (row.formula) guard(fx, () => patchLine(row.id, { formula: "", input_amount: row.input_amount, input_unit: row.input_unit }, true));
    else {
      const f = prompt("Formula of parameters for this amount (in " + row.input_unit + "), e.g. thickness * area * 1800:", String(row.input_amount));
      if (f) guard(fx, () => patchLine(row.id, { formula: f.trim(), input_unit: row.input_unit }, true));
    }
  }
});
$("#btnUndo").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.model) return;
  const r = await api("POST", `/api/models/${S.model.id}/undo`, {});
  S.model = (await api("GET", "/api/models/" + S.model.id)).model; S.result = null;
  renderInventory(); markSteps(); toast(`Undone: ${r.undone}`);
}));

/* flow diagram: stages as columns flowing into the product */
$("#btnDiagram").addEventListener("click", () => { $("#diagram").hidden = !$("#diagram").hidden; if (!$("#diagram").hidden) renderDiagram(); });
function renderDiagram() {
  const m = S.model;
  if (!m || !m.inputs.length) { $("#diagram").innerHTML = '<p class="hint">Add lines to see the diagram.</p>'; return; }
  const groups = {};
  m.inputs.forEach((i) => (groups[i.stage || "No stage"] = groups[i.stage || "No stage"] || []).push(i));
  const names = Object.keys(groups).sort((a, b) => (a.toUpperCase().startsWith("D") - b.toUpperCase().startsWith("D")) || a.localeCompare(b));
  const colW = 210, boxH = 30, gap = 8, top = 34;
  const H = Math.max(...names.map((n) => groups[n].length)) * (boxH + gap) + top + 20;
  const W = names.length * (colW + 30) + 220;
  const prodY = H / 2 - 30;
  let svg = `<svg viewBox="0 0 ${W} ${Math.max(H, 120)}" width="100%" role="img" aria-label="Flow diagram of the model">`;
  names.forEach((n, c) => {
    const x = c * (colW + 30);
    svg += `<text x="${x}" y="18" font-size="12" font-weight="600" fill="var(--ink)">${esc(n.length > 30 ? n.slice(0, 29) + "…" : n)}</text>`;
    groups[n].forEach((i, r) => {
      const y = top + r * (boxH + gap);
      const credit = i.avoided;
      svg += `<rect x="${x}" y="${y}" width="${colW}" height="${boxH}" rx="4" fill="var(--panel)" stroke="${i.missing ? "var(--danger)" : credit ? "var(--neg)" : "var(--rule)"}"/>
        <text x="${x + 8}" y="${y + 19}" font-size="11" fill="var(--ink)">${esc(((i.label || i.target.name) + "").slice(0, 30))}</text>
        <path d="M${x + colW} ${y + boxH / 2} C ${W - 200} ${y + boxH / 2}, ${W - 230} ${prodY + 30}, ${W - 190} ${prodY + 30}" fill="none" stroke="${credit ? "var(--neg)" : "var(--spruce)"}" stroke-width="1" opacity=".45" ${credit ? 'stroke-dasharray="4 3"' : ""}/>`;
    });
  });
  svg += `<rect x="${W - 190}" y="${prodY}" width="185" height="60" rx="6" fill="var(--spruce)"/>
    <text x="${W - 180}" y="${prodY + 25}" font-size="12" font-weight="600" fill="var(--panel)">${esc(m.name.slice(0, 26))}</text>
    <text x="${W - 180}" y="${prodY + 44}" font-size="11" fill="var(--panel)">${esc(`${fmt(m.amount)} ${m.unit}`)}</text></svg>
    <p class="hint">Dashed blue lines are credits (avoided products). Red boxes point to missing datasets.</p>`;
  $("#diagram").innerHTML = svg;
}

async function exportTo(path, defaultName, ext, body = {}) {
  if (desktop) { const p = await desktop.saveFile(defaultName, ext); if (!p) return null; body.path = p; }
  const r = await api("POST", path, body);
  addExport(r);
  return r;
}
function addExport(r) {
  const li = document.createElement("li");
  li.innerHTML = `<span class="grow"><b>${esc(r.file)}</b><br><span class="meta">${esc(r.path)}</span></span>` +
    (desktop ? '<button data-open>Open</button><button class="ghost" data-show>Show in folder</button>'
      : `<a href="/api/download/${encodeURIComponent(r.file)}?token=${TOKEN}" download>Download</a>`);
  if (desktop) { $("[data-open]", li).addEventListener("click", () => desktop.openPath(r.path)); $("[data-show]", li).addEventListener("click", () => desktop.showInFolder(r.path)); }
  $("#exports").prepend(li);
  toast(`Saved ${r.file}` + (S.step !== "report" ? " (listed in step 6)" : ""));
  if (desktop && S.step !== "report") desktop.showInFolder(r.path);
}
$("#btnInvTemplate").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.model) throw new Error("Create a model first.");
  await exportTo(`/api/models/${S.model.id}/inventory-template`, "Cyclia inventory template.xlsx", "xlsx");
}));
$("#btnInvExport").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.model) throw new Error("Create a model first.");
  await exportTo(`/api/models/${S.model.id}/inventory-export`, `${S.model.name.replace(/[^\w\- ]+/g, "")} inventory.xlsx`, "xlsx");
}));
async function importInventory(path, btn) {
  return guard(btn, async () => {
    if (!S.model) throw new Error("Create a model first.");
    const res = await api("POST", `/api/models/${S.model.id}/inventory-import`, { path });
    const box = $("#invProblems");
    if (res.problems.length) {
      box.hidden = false;
      box.innerHTML = `<b>Nothing was imported. Fix these rows and import again:</b><ul>${res.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`;
      return;
    }
    box.hidden = true;
    S.model = (await api("GET", "/api/models/" + S.model.id)).model; S.result = null; renderInventory(); markSteps();
    toast(`${res.added} lines imported.`);
  });
}
$("#btnInvImport").addEventListener("click", async (e) => {
  if (desktop) { const p = await desktop.pickFile("xlsx"); if (p) importInventory(p, e.target); }
  else $("#invImportRow").hidden = !$("#invImportRow").hidden;
});
$("#btnInvImportGo").addEventListener("click", (e) => importInventory($("#invImportPath").value, e.target));

/* ---------------- impact assessment ---------------- */
function renderMethodPicker() {
  const fams = {};
  S.methods.forEach((m) => (fams[m.family] = fams[m.family] || []).push(m));
  // main indicators first (e.g. "climate change: total" before its biogenic and fossil parts)
  const part = (m) => /(biogenic|fossil|land use and land use change|organics|inorganics)/i.test(`${m.category} ${m.indicator}`) &&
    !/total/i.test(m.indicator) ? 1 : 0;
  Object.values(fams).forEach((l) => l.sort((a, b) => part(a) - part(b) || a.category.localeCompare(b.category)));
  const names = Object.keys(fams);
  $("#noMethods").hidden = names.length > 0;
  const starter = !S.selectedMethods.size && names.length ? `<div class="starter"><div class="grow"><b>Not sure where to start?</b>
    <span class="hint">Climate change is the usual first indicator. Add more categories when your goal needs them.</span></div>
    <button class="primary" data-starter>Select climate change</button></div>` : "";
  $("#methodPicker").innerHTML = starter + names.map((f) => {
    const list = fams[f];
    const on = list.filter((m) => S.selectedMethods.has(m.id)).length;
    const cats = list.map((m) => `<label><input type="checkbox" data-mid="${m.id}" ${S.selectedMethods.has(m.id) ? "checked" : ""}>
      <span style="color:var(--ink)">${esc(m.category)}${m.indicator && m.indicator !== m.category ? ": " + esc(m.indicator) : ""}</span> <span>${esc(m.unit)}${m.n_regional ? ", regional" : ""}${m.n_cfs ? "" : ", no matching factors"}</span></label>`).join("");
    return `<div class="fam"><header><b>${esc(f)}</b><span class="hint">${on} of ${list.length} selected</span>
      <button class="ghost" data-all="${esc(f)}">${on === list.length ? "Clear" : "Select all"}</button></header>
      ${list.length > 8 ? `<details ${on ? "open" : ""}><summary>Show ${list.length} categories</summary><div class="cats">${cats}</div></details>` : `<div class="cats">${cats}</div>`}</div>`;
  }).join("");
  $("#calcHint").textContent = S.model ? `Model: ${S.model.name} (${S.model.inputs.length} lines)` : "Create a model first.";
}
$("#methodPicker").addEventListener("change", (e) => {
  const id = Number(e.target.dataset.mid);
  if (!id) return;
  if (e.target.checked) S.selectedMethods.add(id); else S.selectedMethods.delete(id);
  saveMethodSel(); renderMethodPicker(); markSteps();
});
$("#methodPicker").addEventListener("click", (e) => {
  if (e.target.closest("[data-starter]")) {
    const cc = S.methods.filter((m) => /climate change/i.test(m.category) && m.n_cfs);
    const rank = (m) => (/EF v?3\.1/i.test(m.family) ? 0 : /built-in/i.test(m.family) ? 1 : 2) * 10 +
      (/total/i.test(m.indicator) || !/(biogenic|fossil|land use)/i.test(`${m.category} ${m.indicator}`) ? 0 : 5);
    const pick = cc.sort((a, b) => rank(a) - rank(b))[0];
    if (!pick) { toast("No climate change category with factors in the library. Import a method in step 1.", true); return; }
    S.selectedMethods.add(pick.id); saveMethodSel(); renderMethodPicker(); markSteps();
    toast(`Selected: ${pick.family}, ${pick.category}. Now press Calculate.`);
    return;
  }
  const b = e.target.closest("[data-all]");
  if (!b) return;
  const list = S.methods.filter((m) => m.family === b.dataset.all);
  const allOn = list.every((m) => S.selectedMethods.has(m.id));
  list.forEach((m) => (allOn ? S.selectedMethods.delete(m.id) : S.selectedMethods.add(m.id)));
  saveMethodSel(); renderMethodPicker(); markSteps();
});
function saveMethodSel() { ls.set(projKey("methods"), [...S.selectedMethods]); }
function loadMethodSel() {
  const v = ls.get(projKey("methods"), []);
  S.selectedMethods = new Set((Array.isArray(v) ? v : []).filter((id) => S.methods.some((m) => m.id === id)));
}
$("#nwSet").addEventListener("change", (e) => ls.set(projKey("nw"), e.target.value));

function calcBody() {
  if (!S.model) throw new Error("Create a model in step 2 first.");
  if (!S.selectedMethods.size) throw new Error("Pick at least one impact category in step 4.");
  const unc = $("input[name=unc]:checked").value;
  const sens = Number($("#sensPct").value);
  if (!(sens > 0 && sens <= 100)) throw new Error("The sensitivity range must be between 1 and 100 %.");
  return { model_id: S.model.id, method_ids: [...S.selectedMethods], nw_set: $("#nwSet").value || null, sensitivity_pct: sens,
    scenario: $("#scenarioSel").value || null, horizon: Number((S.model.scope || {}).horizon) || 100,
    mc_iterations: unc === "foreground" ? Math.max(100, Number($("#mcN").value) || 1000) : 0, ...bgBody() };
}
function bgBody() {
  const id = $("#bgSel").value;
  if (!id) return {};
  const sc = (S.status.bg_scenarios || []).find((b) => String(b.id) === id);
  return { bg_id: Number(id), bg_year: sc && sc.kind === "prospective" ? Number($("#bgYear").value) || null : null };
}
$("#btnCalc").addEventListener("click", (e) => guard(e.target, async () => {
  const body = calcBody();
  const unc = $("input[name=unc]:checked").value;
  const iters = Number($("#mcN").value);
  if (unc !== "none" && !(iters >= 20 && iters <= 5000)) throw new Error("Iterations must be between 20 and 5000.");
  $("#calcHint").textContent = "Calculating...";
  try { S.result = await api("POST", "/api/calculate", body); } finally { $("#calcHint").textContent = ""; }
  S.result.seconds < 1 ? toast("Calculated.") : toast(`Calculated in ${S.result.seconds} s.`);
  S.cat = Math.min(S.cat, S.result.results.length - 1);
  S.tree = null;
  markSteps(); go("results");
  if (unc === "full") {
    const { job } = await api("POST", "/api/uncertainty", { model_ids: [S.model.id], method_ids: body.method_ids, iterations: iters, scenario: body.scenario, ...bgBody() });
    showTab("unc");
    const modelId = S.model.id;
    watchJob(job, { quiet: true, onDone: async (j) => {
      if (S.result && S.result.model.id === modelId) {
        const m = j.result.models[0];
        S.result.uncertainty = { mode: j.result.mode, iterations: j.result.iterations, methods: m.methods, note: j.result.note };
        renderResults(); toast("Monte Carlo finished.");
      }
    } });
  }
}));

/* ---------------- results ---------------- */
function bars(items, total, opts = {}) {
  if (!items.length) return '<p class="empty">Nothing to show.</p>';
  const max = Math.max(...items.map((i) => Math.abs(i.impact))) || 1;
  const hasNeg = items.some((i) => i.impact < 0);
  return `<div class="bars">${items.map((i, k) => {
    const w = (100 * Math.abs(i.impact)) / max;
    const p = pct(i.impact, total);
    const left = hasNeg ? (i.impact < 0 ? 50 - w / 2 : 50) : 0;
    const width = hasNeg ? w / 2 : w;
    const cls = i.impact < 0 ? "neg" : opts.hot && k === 0 ? "hot" : i.module_d ? "alt" : "";
    return `<div class="bar" title="${esc(i.name)}: ${fmt(i.impact)}"><span class="lbl">${esc(i.name)}${i.module_d ? " (module D)" : ""}</span>
      <span class="track"><span class="fill ${cls}" style="left:${left}%;width:${Math.max(width, 0.6)}%"></span></span>
      <span class="pct">${opts.abs || !total ? fmt(i.impact) : p.toFixed(Math.abs(p) < 10 ? 1 : 0) + "%"}</span></div>`;
  }).join("")}</div>`;
}
function showTab(rt) {
  S.rt = rt;
  $$("#resTabs button").forEach((x) => x.classList.toggle("on", x.dataset.rt === rt));
  $$(".rt").forEach((el) => (el.hidden = el.id !== "rt-" + rt));
  $("#catRow").hidden = ["summary", "checks", "compare", "stages", "dyn", "lci", "explore", "pef"].includes(rt);
  if (rt === "compare") renderCompareModels();
  if (rt === "tree") renderTree();
  if (rt === "map") renderMap();
  if (rt === "pef") renderPef();
}
$$("#resTabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.rt)));

function renderResults() {
  const r = S.result;
  $("#noResults").hidden = !!r; $("#resultsBody").hidden = !r;
  if (!r) return;
  const unc = r.uncertainty, nw = !!r.nw_set, d = r.has_module_d;
  $("#resultMeta").textContent = [r.scenario_name ? `Scenario: ${r.scenario_name}` : "Base parameter values",
    r.background ? `Background: ${r.background.name}` : "", (r.site_factors || []).length ? "Site-specific factors applied" : "",
    r.allocation_share < 1 ? `${(r.allocation_share * 100).toFixed(2)} % allocated to this product` : "",
    d ? "Total excludes module D" : "", r.regional_factors_used ? "Regional factors applied" : ""].filter(Boolean).join(". ") + ".";
  $("#totals").innerHTML = `<thead><tr><th>Method</th><th>Impact category</th><th class="num">${d ? "Total A-C" : "Result"}</th>${d ? '<th class="num">Module D</th>' : ""}<th>Unit</th>${unc ? '<th class="num">95% interval</th>' : ""}${nw ? '<th class="num">Normalised</th><th class="num">Weighted</th>' : ""}</tr></thead><tbody>` +
    r.results.map((x, k) => `<tr data-k="${k}" class="${k === S.cat ? "sel" : ""}"><td>${esc(x.family)}</td><td>${esc(x.category)}${x.indicator !== x.category ? `<br><span class="hint">${esc(x.indicator)}</span>` : ""}
    ${x.cfs_matched === 0 ? '<br><span class="danger hint">No factor matches your flows</span>' : ""}</td>
    <td class="num total">${fmt(x.total)}</td>${d ? `<td class="num">${fmt(x.module_d)}</td>` : ""}<td>${esc(x.unit)}</td>
    ${unc ? `<td class="num">${fmt(unc.methods[k].p2_5)} to ${fmt(unc.methods[k].p97_5)}</td>` : ""}
    ${nw ? `<td class="num">${fmt(x.normalised)}</td><td class="num">${fmt(x.weighted)}</td>` : ""}</tr>`).join("") + "</tbody>";
  $("#singleScore").textContent = nw ? (r.single_score != null ? `Single score (${r.nw_set}): ${fmt(r.single_score)}` : `Factor set ${r.nw_set}: some categories have no factor (${(r.nw_missing || []).join(", ")}).`) : "";
  $("#catSelect").innerHTML = r.results.map((x, k) => `<option value="${k}">${esc(x.category)} (${esc(x.unit)})</option>`).join("");
  $("#catSelect").value = S.cat;
  const errs = r.checks.filter((c) => c.level === "error").length;
  $("#checkCount").textContent = errs ? `(${errs})` : `(${r.checks.length})`;
  $("#checkCount").style.color = errs ? "" : "var(--ink-soft)";
  $("#tabDyn").hidden = !r.dynamic_gwp;
  if (S.rt === "dyn" && !r.dynamic_gwp) S.rt = "contrib";
  renderSummary(); renderCat(); renderStages(); renderChecks(); renderLci(); renderDyn(); renderTox(); prepareExplore();
  showTab(S.rt);
}
const FINDING_ICON = { priority: "Focus", result: "Result", hotspots: "Hotspots", improve: "Improve", credit: "Credit", data: "Data", quality: "Quality", cost: "Cost", error: "Fix" };
function renderSummary() {
  const r = S.result, f = r.findings || [], dq = r.data_quality || {};
  $("#summaryFindings").innerHTML = f.length ? f.map((x) => `<article class="finding k-${esc(x.kind)}"><span class="ftag">${FINDING_ICON[x.kind] || ""}</span><div><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p></div></article>`).join("")
    : '<p class="empty">No findings yet. Add inputs with an impact and calculate again.</p>';
  const cats = dq.by_category || [];
  const share = (v) => (100 * v).toFixed(0) + "%";
  $("#summaryDq").innerHTML = cats.length ? `<div class="table-wrap"><table><thead><tr><th>Impact category</th><th class="num">Pedigree indicator</th><th class="num">PEF DQR</th><th class="num">Primary</th><th class="num">Secondary</th><th class="num">Estimate</th><th class="num">Not stated</th></tr></thead><tbody>` +
    cats.map((c) => `<tr><td>${esc(c.category)}</td><td class="num">${c.dqr.toFixed(2)} <span class="dq-pill dq-${esc(c.rating.replace(" ", "-"))}">${esc(c.rating)}</span></td><td class="num">${c.pef_dqr != null ? `${c.pef_dqr.toFixed(2)} <span class="dq-pill dq-${esc(c.pef_rating.replace(" ", "-"))}">${esc(c.pef_rating)}</span><br><span class="hint">covers ${share(c.pef_coverage)}</span>` : '<span class="hint">enter PEF scores</span>'}</td><td class="num">${share(c.primary_share)}</td><td class="num">${share(c.secondary_share)}</td><td class="num">${share(c.estimate_share)}</td><td class="num">${share(c.unstated_share)}</td></tr>`).join("") +
    `</tbody></table></div><p class="hint">${esc(dq.note || "")}${dq.default_lines ? ` ${dq.default_lines} line${dq.default_lines > 1 ? "s still have" : " still has"} the default pedigree (3,3,3,3,3): rate them in step 3.` : ""}</p>` +
    ((dq.priority || []).length ? `<h3>Improve these data first</h3><ul class="dq-list">${dq.priority.map((x) => `<li><b>${esc(x.name)}</b> <span class="hint">${esc(x.stage)}</span>: up to ${share(x.max_share)} of a category, pedigree (${x.pedigree.join(",")}), ${esc(x.data_type || "type not stated")}${x.default ? ", default scores" : ""}</li>`).join("")}</ul>` : "")
    : '<p class="empty">No data quality to show.</p>';
}
function renderCat() {
  const r = S.result, x = r.results[S.cat];
  $$("#totals tbody tr").forEach((tr) => tr.classList.toggle("sel", Number(tr.dataset.k) === S.cat));
  const byInput = [...x.by_input].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
  $("#chartInputs").innerHTML = bars(byInput, x.total, { hot: true });
  $("#chartProcs").innerHTML = bars(x.processes, x.total, { hot: true });
  $("#chartFlows").innerHTML = bars(x.flows, x.total);
  const sp = r.sensitivity_pct;
  const items = x.sensitivity.filter((s) => s.high !== 0).slice(0, 12);
  const max = Math.max(...items.map((s) => Math.max(Math.abs(s.ped_low), Math.abs(s.ped_high), Math.abs(s.high)))) || 1;
  $("#sensNote").textContent = `Change in ${x.category} when one input changes. Green: ±${sp}% change of the input. Ochre: the 95% range implied by its data-quality score.`;
  $("#chartSens").innerHTML = items.length ? `<div class="legend-row"><span><i style="background:var(--spruce)"></i>±${sp}% input</span><span><i style="background:var(--ochre);opacity:.55"></i>data-quality range</span></div><div class="bars tornado">` +
    items.map((s) => {
      const seg = (a, b, cls) => { const lo = Math.min(a, b), hi = Math.max(a, b);
        return `<span class="fill ${cls}" style="left:${50 + (50 * lo) / max}%;width:${Math.max(0.6, (50 * (hi - lo)) / max)}%"></span>`; };
      return `<div class="bar" title="${esc(s.name)}"><span class="lbl">${esc(s.name)}</span><span class="track">${seg(s.ped_low, s.ped_high, "alt")}${seg(s.low, s.high, "")}</span>
        <span class="pct">±${Math.abs(pct(s.high, x.total)).toFixed(1)}%</span></div>`;
    }).join("") + "</div>" : '<p class="empty">No input changes this category.</p>';
  const ps = r.parameter_sensitivity || [];
  $("#paramSens").innerHTML = ps.length ? `<table><thead><tr><th>Parameter</th><th class="num">Value</th><th class="num">-${sp}%</th><th class="num">+${sp}%</th></tr></thead><tbody>` +
    ps.map((p) => `<tr><td><code>${esc(p.name)}</code></td><td class="num">${fmt(p.value)}</td><td class="num">${p.low ? pct(p.low[S.cat], x.total).toFixed(2) + " %" : "-"}</td><td class="num">${p.high ? pct(p.high[S.cat], x.total).toFixed(2) + " %" : "-"}</td></tr>`).join("") + "</tbody></table>"
    : '<p class="hint">No free parameters in this model.</p>';
  const u = r.uncertainty;
  $("#uncNone").hidden = !!u; $("#uncBody").hidden = !u;
  if (u) {
    const m = u.methods[S.cat];
    const hmax = Math.max(...m.histogram) || 1;
    const W = 520, H = 140, bw = W / m.histogram.length;
    const lo = m.bins[0], hi = m.bins[m.bins.length - 1];
    const xp = (v) => ((v - lo) / (hi - lo || 1)) * W;
    $("#chartMc").innerHTML = `<svg viewBox="0 0 ${W} ${H + 24}" width="100%" style="max-width:640px" role="img" aria-label="Histogram of Monte Carlo results">
      ${m.histogram.map((c, i) => `<rect x="${i * bw + 0.5}" y="${H - (H * c) / hmax}" width="${Math.max(bw - 1, 0.5)}" height="${(H * c) / hmax}" fill="var(--spruce)" opacity=".75"/>`).join("")}
      <line x1="${xp(m.p2_5)}" x2="${xp(m.p2_5)}" y1="0" y2="${H}" stroke="var(--ochre)" stroke-width="2"/>
      <line x1="${xp(m.p97_5)}" x2="${xp(m.p97_5)}" y1="0" y2="${H}" stroke="var(--ochre)" stroke-width="2"/>
      <line x1="${xp(x.total)}" x2="${xp(x.total)}" y1="0" y2="${H}" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 3"/>
      <text x="0" y="${H + 17}" font-size="11" fill="var(--ink-soft)">${fmt(lo)}</text>
      <text x="${W}" y="${H + 17}" font-size="11" fill="var(--ink-soft)" text-anchor="end">${fmt(hi)}</text></svg>`;
    $("#mcNote").textContent = `${x.category}: median ${fmt(m.median)}, 95% interval ${fmt(m.p2_5)} to ${fmt(m.p97_5)} ${x.unit}, CV ${m.cv_percent != null ? m.cv_percent.toFixed(1) : "-"}%. ${m.converged === true ? `Converged (standard error of the mean ${m.se_width_percent.toFixed(2)} % of the interval width; interval stable within ${m.interval_drift_percent.toFixed(0)} %).` : m.converged === false ? `Not converged yet (standard error of the mean ${m.se_width_percent != null ? m.se_width_percent.toFixed(2) : "-"} % of the interval width, interval moved ${m.interval_drift_percent != null ? m.interval_drift_percent.toFixed(0) : "-"} % between the first half and all runs; aim for below 1 % and 10 %): use more iterations.` : ""} Dashed line: deterministic result. ${u.note}`;
  }
  if (S.rt === "tree") renderTree();
  if (S.rt === "map") renderMap();
}
function renderStages() {
  const r = S.result;
  $("#chartStages").innerHTML = (r.stages.length > 1 ? "" : '<p class="hint">Assign life cycle stages to inventory lines in step 3 to see results per stage.</p>') +
    r.results.map((x) => `<h3 class="hint" style="margin:14px 0 6px">${esc(x.category)} (${esc(x.unit)})</h3>` + bars(x.by_stage, x.total)).join("");
  $("#stageTable").innerHTML = `<thead><tr><th>Stage</th>${r.results.map((x) => `<th class="num">${esc(x.category)}<br><span class="hint">${esc(x.unit)}</span></th>`).join("")}</tr></thead><tbody>` +
    r.stages.map((s) => `<tr><td>${esc(s)}</td>${r.results.map((x) => `<td class="num">${fmt((x.by_stage.find((b) => b.name === s) || {}).impact)}</td>`).join("")}</tr>`).join("") + "</tbody>";
}
function renderChecks() {
  const steps = { scope: "Goal & scope", inventory: "Inventory", impact: "Impact assessment", interpretation: "Interpretation", report: "Report" };
  const go2 = { scope: "scope", inventory: "inventory", impact: "impact", report: "report" };
  $("#checksList").innerHTML = S.result.checks.length ? S.result.checks.map((c) => `<li><span class="lvl ${c.level}">${c.level}</span><span>${esc(c.message)}</span>
    ${go2[c.step] ? `<button class="ghost go" data-go="${go2[c.step]}">${steps[c.step]}</button>` : `<span class="hint">${steps[c.step] || ""}</span>`}</li>`).join("")
    : '<li><span class="lvl info">ok</span><span>No issues found.</span><span></span></li>';
}
$("#checksList").addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });
function renderForeground() {
  const r = S.result, all = ($("input[name=fgScope]:checked") || {}).value === "all";
  const rows = (r.foreground || []).filter((x) => all || x.depth === 0);
  $("#fgTable").innerHTML = `<thead><tr>${all ? "<th>Model</th>" : ""}<th>Line</th><th class="num">Per unit</th><th class="num">Per FU</th><th>Data type</th><th class="num">Year</th><th>Supplier / site</th><th>Reference</th><th>Verified</th><th>Pedigree</th></tr></thead><tbody>` +
    rows.map((x) => `<tr>${all ? `<td>${esc(x.model)}</td>` : ""}<td>${"&nbsp;&nbsp;".repeat(all ? x.depth : 0)}${esc(x.name)}${x.avoided ? ' <span class="hint">(credit)</span>' : ""}</td><td class="num">${fmt(x.amount)} ${esc(x.unit || "")}</td><td class="num">${fmt(x.per_fu)} ${esc(x.per_fu_unit || "")}</td><td>${esc(x.data_type || "-")}</td><td class="num">${x.data_year ? Math.round(x.data_year) : "-"}</td><td>${esc(x.supplier || "-")}</td><td>${esc((x.reference || "-").slice(0, 60))}</td><td>${x.verified ? "yes" : "-"}</td><td>${x.pedigree.join(",")}</td></tr>`).join("") + "</tbody>";
}
$$("input[name=fgScope]").forEach((i) => i.addEventListener("change", () => S.result && renderForeground()));
function renderLci() {
  const r = S.result;
  renderForeground();
  $("#uncharOut").innerHTML = r.uncharacterised.length ? `<table><thead><tr><th>Flow</th><th>Compartment</th><th class="num">Amount</th><th>Note</th></tr></thead><tbody>
    ${r.uncharacterised.slice(0, 25).map((u) => `<tr><td>${esc(u.name)}</td><td>${esc(u.context)}</td><td class="num">${fmt(u.amount)} ${esc(u.unit)}</td><td>${u.mapping_issue ? '<span class="warn">The method has this flow under another name or compartment: import a flow mapping.</span>' : ""}</td></tr>`).join("")}</tbody></table>`
    : '<p class="hint">Every inventory flow has a factor in at least one selected category.</p>';
  $("#lciNote").textContent = `${r.lci_total || r.lci.length} elementary flows in total; the Excel export has all of them.`;
  $("#lciTable").innerHTML = `<thead><tr><th>Elementary flow</th><th>Compartment</th><th class="num">Amount</th><th>Unit</th></tr></thead><tbody>` +
    r.lci.slice(0, 120).map((x) => `<tr><td>${esc(x.name)}</td><td>${esc(x.context)}</td><td class="num">${fmt(x.amount)}</td><td>${esc(x.unit)}</td></tr>`).join("") + "</tbody>";
}
function renderDyn() {
  const d = S.result.dynamic_gwp;
  if (!d) { $("#dynOut").innerHTML = ""; return; }
  $("#dynOut").innerHTML = `<p><b>Dynamic GWP over ${d.horizon} years: ${fmt(d.dynamic)} kg CO2-eq</b>, against ${fmt(d.static)} kg CO2-eq when every emission counts as if it happened in year 0.</p>
    <table><thead><tr><th>Line</th><th class="num">Year</th><th class="num">Static</th><th class="num">Dynamic</th></tr></thead><tbody>
    ${d.by_line.map((l) => `<tr><td>${esc(l.name)}</td><td class="num">${fmt(l.year)}</td><td class="num">${fmt(l.static)}</td><td class="num">${fmt(l.dynamic)}</td></tr>`).join("")}</tbody></table>
    <p class="hint">${esc(d.note)} Set the year of each line in step 3.</p>`;
}
$("#catSelect").addEventListener("change", (e) => { S.cat = Number(e.target.value); renderCat(); });
$("#totals").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-k]"); if (tr) { S.cat = Number(tr.dataset.k); $("#catSelect").value = S.cat; renderCat(); } });

/* supply chain tree and Sankey */
async function renderTree() {
  const r = S.result;
  if (!r) return;
  const mid = r.results[S.cat].method_id;
  const box = $("#treeBox");
  box.innerHTML = '<p class="hint">Loading...</p>';
  try {
    const scen = r.scenario ? `&scenario=${r.scenario}` : "";
    const root = await api("GET", `/api/tree?model_id=${r.model.id}&method_id=${mid}${scen}`);
    box.innerHTML = `<ul class="tree-root">${root.children.map((c) => treeNode(c, root.total, mid)).join("")}</ul>`;
    renderSankey(root, r.results[S.cat]);
  } catch (e) { box.innerHTML = `<p class="danger">${esc(e.message)}</p>`; }
}
function treeNode(c, total, mid) {
  const share = pct(c.impact, total);
  return `<li><div class="tnode">${c.node ? `<button class="ghost tog" data-node="${c.node}" data-amount="${c.amount}" data-mid="${mid}" data-total="${total}" aria-expanded="false">+</button>` : '<span class="tog-sp"></span>'}
    <span class="tname">${esc(c.name)} <span class="hint">[${esc(c.location || "")}] ${fmt(c.amount)} ${esc(c.unit || "")}</span></span>
    <span class="tbar"><span class="fill ${c.impact < 0 ? "neg" : ""}" style="width:${Math.min(100, Math.abs(share))}%"></span></span>
    <span class="num">${fmt(c.impact)}</span><span class="num hint">${share.toFixed(1)}%</span></div></li>`;
}
$("#treeBox").addEventListener("click", (e) => {
  const b = e.target.closest("[data-node]");
  if (!b) return;
  const li = b.closest("li");
  const open = b.getAttribute("aria-expanded") === "true";
  if (open) { li.querySelector(":scope > ul")?.remove(); b.setAttribute("aria-expanded", "false"); b.textContent = "+"; return; }
  guard(b, async () => {
    const t = await api("GET", `/api/tree?model_id=${S.result.model.id}&method_id=${b.dataset.mid}&node=${b.dataset.node}&amount=${b.dataset.amount}`);
    const total = Number(b.dataset.total);
    const ul = document.createElement("ul");
    ul.innerHTML = (t.direct ? `<li><div class="tnode"><span class="tog-sp"></span><span class="tname">Direct emissions of this process</span><span class="tbar"><span class="fill alt" style="width:${Math.min(100, Math.abs(pct(t.direct, total)))}%"></span></span><span class="num">${fmt(t.direct)}</span><span class="num hint">${pct(t.direct, total).toFixed(1)}%</span></div></li>` : "") +
      t.children.map((c) => treeNode(c, total, b.dataset.mid)).join("") +
      (t.hidden ? `<li><div class="tnode"><span class="tog-sp"></span><span class="tname hint">${t.hidden} smaller inputs</span><span></span><span class="num">${fmt(t.rest)}</span><span class="num hint">${pct(t.rest, total).toFixed(1)}%</span></div></li>` : "");
    li.appendChild(ul);
    b.setAttribute("aria-expanded", "true"); b.textContent = "-";
  });
});
function renderSankey(root, res) {
  const kids = root.children.filter((c) => c.impact > 0).slice(0, 8);
  const total = kids.reduce((a, c) => a + c.impact, 0);
  if (!kids.length || !total) { $("#sankey").innerHTML = ""; return; }
  const W = 640, H = 220, x1 = 250, x2 = W - 150;
  let y = 10, svg = `<svg viewBox="0 0 ${W} ${H + 20}" width="100%" style="max-width:760px" role="img" aria-label="Flow of ${esc(res.category)} from inputs to the product">`;
  const scale = (H - 10 - kids.length * 4) / total;
  let ty = H / 2 - (total * scale) / 2;
  kids.forEach((c, i) => {
    const h = Math.max(2, c.impact * scale);
    svg += `<path d="M${x1} ${y} C ${(x1 + x2) / 2} ${y}, ${(x1 + x2) / 2} ${ty}, ${x2} ${ty} L ${x2} ${ty + h} C ${(x1 + x2) / 2} ${ty + h}, ${(x1 + x2) / 2} ${y + h}, ${x1} ${y + h} Z" fill="${i === 0 ? "var(--ochre)" : "var(--spruce)"}" opacity="${i === 0 ? 0.55 : 0.35}"/>
      <text x="${x1 - 8}" y="${y + h / 2 + 4}" font-size="11" text-anchor="end" fill="var(--ink)">${esc(c.name.slice(0, 34))} (${pct(c.impact, res.total).toFixed(0)}%)</text>`;
    y += h + 4; ty += h;
  });
  svg += `<rect x="${x2}" y="${H / 2 - (total * scale) / 2}" width="10" height="${total * scale}" fill="var(--spruce)"/>
    <text x="${x2 + 16}" y="${H / 2 + 4}" font-size="12" font-weight="600" fill="var(--ink)">${esc(fmt(res.total))} ${esc(res.unit)}</text></svg>`;
  $("#sankey").innerHTML = svg;
}

$("#btnSobol").addEventListener("click", (e) => guard(e.target, async () => {
  const r = S.result;
  const { job } = await api("POST", "/api/sobol", { model_id: r.model.id, method_ids: r.results.map((x) => x.method_id), n: Number($("#sobolN").value) || 512, scenario: r.scenario, ...bgBody() });
  $("#sobolOut").innerHTML = '<p class="hint">Running; progress is shown at the bottom left.</p>';
  watchJob(job, { quiet: true, onDone: async (j) => {
    const s = j.result;
    const k = Math.min(S.cat, s.methods.length - 1);
    const order = s.factors.map((f, i) => i).sort((a, b) => s.ST[b][k] - s.ST[a][k]).slice(0, 15);
    $("#sobolOut").innerHTML = `<p class="hint">${esc(s.note)}</p><table><thead><tr><th>Uncertain input</th><th class="num">First order S1</th><th class="num">Total ST</th></tr></thead><tbody>
      ${order.map((i) => `<tr><td>${esc(s.factors[i])}</td><td class="num">${s.S1[i][k].toFixed(3)}</td><td class="num">${s.ST[i][k].toFixed(3)}</td></tr>`).join("")}</tbody></table>
      <p class="hint">Category: ${esc(s.methods[k].category)}. Inputs with a high total index deserve better data.</p>`;
  } });
}));

/* compare */
function renderCompareModels() {
  const prev = new Set($$("#compareModels input:checked").map((i) => Number(i.value)));
  $("#compareModels").innerHTML = S.models.map((m) => `<label><input type="checkbox" value="${m.id}" ${(prev.size ? prev.has(m.id) : S.model && m.id === S.model.id) ? "checked" : ""}> ${esc(m.name)} <span class="hint">(${fmt(m.amount)} ${esc(m.unit)})</span></label>`).join("") || '<p class="empty">No models yet.</p>';
  const sc = (S.status && S.status.scenarios) || [];
  $("#compareScen").innerHTML = sc.length ? sc.map((s) => `<label><input type="checkbox" value="${s.id}" checked> ${esc(s.name)}</label>`).join("") : '<p class="hint">No scenarios yet. Create them in step 2.</p>';
}
const CMP_COLORS = ["var(--spruce)", "var(--ochre)", "var(--neg)", "#8a6fb0", "#b0556f", "#5f8f3a"];
function compareIds() {
  const ids = $$("#compareModels input:checked").map((i) => Number(i.value));
  if (ids.length < 2) throw new Error("Tick at least two models.");
  if (!S.selectedMethods.size) throw new Error("Pick impact categories in step 4 first.");
  return ids;
}
function compareNotes(res) {
  // Which alternative has the lower result per category. Whether a difference is real is judged with the
  // comparative Monte Carlo, not with a fixed threshold.
  const names = res.models.map((m) => m.model.name);
  const best = {};
  res.methods.forEach((meth, k) => {
    const vals = res.models.map((m) => m.totals[k]);
    const i = vals.indexOf(Math.min(...vals));
    (best[names[i]] = best[names[i]] || []).push(meth.category);
  });
  const winners = Object.keys(best);
  const lines = [];
  if (winners.length > 1) lines.push(`<p><b>No alternative has the lowest result in every category.</b> ${winners.map((n) => `${esc(n)}: lowest in ${best[n].map(esc).join(", ")}`).join("; ")}. Choosing one moves burdens to other categories (burden shifting, ISO 14044 4.5); report all categories.</p>`);
  else if (winners.length === 1 && res.methods.length > 1) lines.push(`<p><b>${esc(winners[0])} has the lowest result in every selected category.</b></p>`);
  lines.push('<p class="hint">Run the comparative Monte Carlo below to see whether each difference is larger than the uncertainty.</p>');
  return `<div class="cmp-notes">${lines.join("")}</div>`;
}
function groupedBars(names, methods, values) {
  return `<div class="cmp-legend">${names.map((n, i) => `<span><i style="background:${CMP_COLORS[i % 6]}"></i>${esc(n)}</span>`).join("")}</div>` +
    methods.map((meth, k) => {
      const vals = values.map((v) => v[k]);
      const max = Math.max(...vals.map(Math.abs)) || 1;
      return `<div class="cmp-cat"><div class="lbl">${esc(meth.category)}<small>${esc(meth.family)}, ${esc(meth.unit)}</small></div><div class="bars">` +
        names.map((n, i) => `<div class="bar"><span class="lbl">${esc(n)}</span><span class="track"><span class="fill${vals[i] < 0 ? " neg" : ""}" style="left:0;width:${Math.max(0.6, (100 * Math.abs(vals[i])) / max)}%;${vals[i] < 0 ? "" : "background:" + CMP_COLORS[i % 6]}"></span></span><span class="pct">${fmt(vals[i])}</span></div>`).join("") + "</div></div>";
    }).join("");
}
$("#btnCompare").addEventListener("click", (e) => guard(e.target, async () => {
  const res = await api("POST", "/api/compare", { model_ids: compareIds(), method_ids: [...S.selectedMethods], scenario: $("#scenarioSel").value || null,
    equivalence: $("#compareEquiv").value.trim(), ...bgBody() });
  const out = $("#compareOut");
  out.hidden = false;
  S.compareStatus = res.status;
  const head = { valid: "Comparison checks passed", screening: "Screening comparison, not a comparative assertion", blocked: "These models cannot be compared yet" }[res.status];
  out.innerHTML = `<div class="cmp-gate g-${res.status}"><h3>${head}</h3><p>${esc(res.note)}</p>` +
    (res.blocking.length ? `<ul>${res.blocking.map((w) => `<li class="danger">${esc(w)}</li>`).join("")}</ul>` : "") +
    (res.issues.length ? `<p><b>Differences to resolve or justify:</b></p><ul>${res.issues.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : "") +
    (!res.blocking.length && !res.equivalence ? '<p class="hint">Add a functional equivalence statement above and compare again.</p>' : "") + "</div>" +
    (res.status === "blocked" ? "" : compareNotes(res) + groupedBars(res.models.map((m) => m.model.name), res.methods, res.models.map((m) => m.totals)));
}));
$("#btnCompareMc").addEventListener("click", (e) => guard(e.target, async () => {
  const ids = compareIds();
  const iters = Math.min(5000, Math.max(20, Number($("#mcN").value) || 500));
  const { job } = await api("POST", "/api/uncertainty", { model_ids: ids, method_ids: [...S.selectedMethods], iterations: iters, confidence: Number($("#cmpConf").value), scenario: $("#scenarioSel").value || null, ...bgBody() });
  const out = $("#compareMcOut");
  out.hidden = false; out.innerHTML = '<p class="hint">Running the comparative Monte Carlo; progress is shown at the bottom left.</p>';
  watchJob(job, { quiet: true, onDone: async (j) => {
    const r = j.result;
    const pc = (x) => (100 * x).toFixed(1) + " %";
    const verdict = (c, a, b) => {
      if (c.result === "no_difference") return "no difference";
      const p = `P = ${pc(c.p_a_lower)}<br><span class="hint">${pc(c.interval[0])} to ${pc(c.interval[1])}</span>`;
      const head = { a_lower: `<b>${esc(a)} lower</b>`, b_lower: `<b>${esc(b)} lower</b>`, more_iterations: '<span class="warn">run more iterations</span>', not_distinguishable: "not distinguishable" }[c.result];
      return `${head}<br>${p}`;
    };
    const conv = r.models.every((m) => m.methods.every((x) => x.converged));
    out.innerHTML = `<h2>Comparative Monte Carlo (${r.iterations} iterations)</h2><p class="hint">${esc(r.note)}</p>
      ${S.compareStatus && S.compareStatus !== "valid" ? '<p class="danger">The comparison checks did not pass (see above): treat these probabilities as a screening result.</p>' : ""}
      ${conv ? "" : '<p class="danger">Not all results have converged: run more iterations before drawing conclusions.</p>'}
      <div class="table-wrap"><table class="prob-table"><thead><tr><th>Comparison</th>${r.methods.map((m) => `<th class="num">${esc(m.category)}</th>`).join("")}</tr></thead><tbody>` +
      r.pairs.map((p) => `<tr><td>${esc(p.a)} vs ${esc(p.b)}<br><span class="hint">probability that ${esc(p.a)} is lower</span></td>${p.p_a_lower.map((v, k) => `<td class="num" title="${esc(p.conclusions[k].text.replace(/\bA\b/g, p.a).replace(/\bB\b/g, p.b))}">${verdict(p.conclusions[k], p.a, p.b)}</td>`).join("")}</tr>` +
        `<tr><td class="hint">95 % interval of the difference ${esc(p.a)} minus ${esc(p.b)}</td>${p.diff_p2_5.map((lo, k) => `<td class="num hint">${fmt(lo)} to ${fmt(p.diff_p97_5[k])}</td>`).join("")}</tr>`).join("") +
      `</tbody></table></div><p class="hint">P is the share of the ${r.iterations} paired runs in which the first alternative is lower, with the 95 % interval of that estimate. An alternative is called lower when the whole interval lies at or above the chosen confidence (${pc(r.confidence)}); when only the estimate does, more iterations are needed. The conclusion uses each category's own uncertainty, not a fixed percentage difference.</p>` +
      `<div class="table-wrap"><table><thead><tr><th>Model</th>${r.methods.map((m) => `<th class="num">${esc(m.category)} 95% interval</th>`).join("")}</tr></thead><tbody>` +
      r.models.map((m) => `<tr><td>${esc(m.name)}</td>${m.methods.map((s) => `<td class="num">${fmt(s.p2_5)} to ${fmt(s.p97_5)}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>";
    toast("Comparative Monte Carlo finished.");
  } });
}));
$("#btnCompareScen").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.model) throw new Error("Choose a model.");
  if (!S.selectedMethods.size) throw new Error("Pick impact categories in step 4 first.");
  const ids = $$("#compareScen input:checked").map((i) => Number(i.value));
  if (!ids.length) throw new Error("Tick at least one scenario.");
  const res = await api("POST", "/api/compare-scenarios", { model_id: S.model.id, method_ids: [...S.selectedMethods], scenario_ids: ids, ...bgBody() });
  const base = res.scenarios[0];
  const shifts = res.scenarios.slice(1).map((sc) => {
    const up = [], down = [];
    res.methods.forEach((m, k) => { const d = sc.totals[k] - base.totals[k], rel = Math.abs(base.totals[k]) > 0 ? d / Math.abs(base.totals[k]) : 0;
      if (d > 0 && Math.abs(rel) > 1e-9) up.push(`${esc(m.category)} +${(100 * rel).toFixed(1)} %`); else if (d < 0 && Math.abs(rel) > 1e-9) down.push(`${esc(m.category)} ${(100 * rel).toFixed(1)} %`); });
    return `<li><b>${esc(sc.scenario)}</b> against base values: ${down.length ? "lower in " + down.join(", ") : "no category lower"}${up.length ? `; <span class="danger">higher in ${up.join(", ")}</span>${down.length ? " (burden shifting)" : ""}` : ""}.</li>`;
  });
  $("#compareScenOut").innerHTML = (shifts.length ? `<ul class="cmp-notes">${shifts.join("")}</ul>` : "") + groupedBars(res.scenarios.map((s) => s.scenario), res.methods, res.scenarios.map((s) => s.totals));
}));

/* ---------------- report ---------------- */
function fillConclusions() {
  const f = $("#concForm");
  const sc = (S.model && S.model.scope) || {};
  CONC_FIELDS.forEach((k) => (f[k].value = sc[k] || ""));
}
$("#concForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button[type=submit]", e.target), async () => {
    if (!S.model) throw new Error("Create a model first.");
    const extra = {};
    CONC_FIELDS.forEach((k) => (extra[k] = e.target[k].value.trim()));
    fillScope();
    await saveModelScope(extra);
    $("#concSaved").textContent = "Saved."; setTimeout(() => ($("#concSaved").textContent = ""), 2500);
    markSteps();
  });
});
async function exportReport(kind, btn) {
  return guard(btn, async () => {
    const body = calcBody();
    const ext = kind === "word" ? "docx" : "xlsx";
    await exportTo("/api/export/" + kind, `${S.model.name.replace(/[^\w\- ]+/g, "")}.${ext}`, ext, body);
  });
}
$("#btnWord").addEventListener("click", (e) => exportReport("word", e.target));
$("#btnExcel").addEventListener("click", (e) => exportReport("excel", e.target));
$("#btnMethodsText").addEventListener("click", (e) => guard(e.target, async () => {
  const { text } = await api("POST", "/api/methods-text", calcBody());
  $("#methodsText").textContent = text; $("#methodsTextBox").hidden = false;
}));
$("#btnCopy").addEventListener("click", () => navigator.clipboard.writeText($("#methodsText").textContent).then(() => toast("Copied."), () => toast("Copy failed; select the text and copy it.", true)));
$("#btnBackup").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.status.project) throw new Error("Open a project first.");
  const r = await exportTo("/api/projects/export", `${S.status.project}.lca`, "lca");
  if (r && r.databases.length) toast(`Saved. Whoever opens it needs these databases in their library: ${r.databases.join(", ")}.`);
}));

/* ---------------- help, guide, licence ---------------- */
function openHelp(tab, term) {
  $("#help").hidden = false;
  showHelpTab(tab || "manual");
  if (term) {
    $("#glossSearch").value = "";
    renderGlossary();
    const el = document.getElementById("g-" + term.replace(/\W+/g, "-"));
    if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600); }
  }
}
function showHelpTab(t) {
  $("#help").classList.toggle("wide", t === "manual");
  if (t === "manual" && window.openGuide && !$("#guideDoc").dataset.ready) { $("#guideDoc").dataset.ready = "1"; setTimeout(() => window.openGuide(""), 0); }
  $$("#helpTabs button").forEach((b) => b.classList.toggle("on", b.dataset.ht === t));
  $$("[data-hp]").forEach((p) => (p.hidden = p.dataset.hp !== t));
  if (t === "glossary") renderGlossary();
  if (t === "about") renderAbout();
  if (t === "guide") renderGuide();
  if (t === "tour") renderTour();
}
$("#btnHelp").addEventListener("click", () => ($("#help").hidden ? openHelp("manual") : ($("#help").hidden = true)));
$("#btnHelpClose").addEventListener("click", () => ($("#help").hidden = true));
$$("#helpTabs button").forEach((b) => b.addEventListener("click", () => showHelpTab(b.dataset.ht)));
document.addEventListener("click", (e) => { const q = e.target.closest("[data-help]"); if (q) { e.preventDefault(); openHelp("glossary", q.dataset.help); } });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#help").hidden) $("#help").hidden = true; });
function renderGlossary() {
  const q = $("#glossSearch").value.trim().toLowerCase();
  const g = window.GLOSSARY || {};
  $("#glossary").innerHTML = Object.keys(g).sort((a, b) => a.localeCompare(b)).filter((k) => !q || k.toLowerCase().includes(q) || g[k].toLowerCase().includes(q))
    .map((k) => `<dt id="g-${k.replace(/\W+/g, "-")}">${esc(k)}</dt><dd>${esc(g[k])}</dd>`).join("");
}
$("#glossSearch").addEventListener("input", renderGlossary);
function renderGuide() {
  const st = S.status || {};
  const m = S.model;
  const tasks = [
    ["Create a project", !!st.project, "setup"],
    ["Add the tutorial database (step 1)", (st.databases || []).length > 0, "setup"],
    ["Define a model with functional unit, goal and boundary (step 2)", !!(m && m.unit && m.product && m.scope.goal && m.scope.boundary), "scope"],
    ["Add at least three inventory lines with stages (step 3)", !!(m && m.inputs.length >= 3 && m.inputs.every((i) => i.stage)), "inventory"],
    ["Rate the data quality of one line (step 3)", !!(m && m.inputs.some((i) => i.pedigree.join() !== "3,3,3,3,3")), "inventory"],
    ["Select climate change categories (step 4)", S.selectedMethods.size > 0, "impact"],
    ["Calculate and open the Checks tab (step 5)", !!S.result, "results"],
    ["Write a conclusion and create the Word report (step 6)", !!(m && m.scope.conclusions) && $("#exports").children.length > 0, "report"],
  ];
  $("#guideList").innerHTML = tasks.map(([t, done, step]) => `<li class="${done ? "done" : ""}"><button class="ghost" data-goguide="${step}">${esc(t)}</button></li>`).join("");
}
$("#guideList").addEventListener("click", (e) => { const b = e.target.closest("[data-goguide]"); if (b) go(b.dataset.goguide); });
function renderAbout() {
  const st = S.status || {};
  $("#aboutText").innerHTML = `${esc(st.app)} ${esc(st.version)}, MIT licence. Your data folder: <code>${esc(st.data_dir)}</code>.`;
  if (window.renderAuthorCard) window.renderAuthorCard();
}
$("#btnDiag").addEventListener("click", (e) => guard(e.target, async () => {
  const appLog = desktop && desktop.appLogPath ? await desktop.appLogPath() : null;
  const r = await api("POST", "/api/diagnostics", { app_log: appLog });
  addExport(r);
}));

/* ---------------- start ---------------- */
(async () => {
  try {
    await refreshStatus();
    go(S.status.project && S.status.databases.length ? (S.model ? "inventory" : "scope") : "setup");
    if (window.maybeWelcome) window.maybeWelcome();
  } catch (e) { toast("Cannot reach the calculation engine: " + e.message, true); }
})();
