/* Cyclia 1.2 features: demo, templates, versions and lock, comments, literature and external-model import,
   background scenarios, map, parameter exploration, PEF, standards outputs, critical review, sharing, toolbox. */
"use strict";

const DEMO_NW = "Demo normalisation and weighting (illustrative)";
let EXAMPLES = null;
async function examples() { if (!EXAMPLES) EXAMPLES = await api("GET", "/api/examples"); return EXAMPLES; }
const when = (ts) => new Date(ts * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
function needModel() { if (!S.model) throw new Error("Choose or create a model first (step 2)."); }
function looseBody() {
  needModel();
  return { model_id: S.model.id, method_ids: [...S.selectedMethods], nw_set: $("#nwSet").value || null,
    sensitivity_pct: Number($("#sensPct").value) || 10, scenario: $("#scenarioSel").value || null,
    horizon: Number((S.model.scope || {}).horizon) || 100,
    mc_iterations: $("input[name=unc]:checked").value === "foreground" ? Math.max(100, Number($("#mcN").value) || 1000) : 0, ...bgBody() };
}
const safeName = (s) => String(s || "model").replace(/[^\w\- ]+/g, "").trim() || "model";

/* ---------------- demo ---------------- */
$("#btnDemo").addEventListener("click", (e) => guard(e.target, async () => {
  if (!confirm("Create the project 'Cyclia feature demo' with illustrative data? Your other projects are not changed.")) return;
  const { job } = await api("POST", "/api/demo");
  await watchJob(job, { quiet: true, onDone: async (j) => {
    S.result = null; S.model = null;
    await refreshStatus();
    S.selectedMethods = new Set(j.result.methods); saveMethodSel();
    ls.set(projKey("nw"), DEMO_NW);
    if ([...$("#nwSet").options].some((o) => o.value === DEMO_NW)) $("#nwSet").value = DEMO_NW;
    const wall = S.models.find((m) => m.name === "Concrete wall (demo)");
    if (wall) await loadModel(wall.id);
    go("scope");
    toast("Demo loaded. Help > Feature tour takes you to every feature.");
    openHelp("tour");
  } });
}));

/* ---------------- lock banners ---------------- */
function renderLockBanners() {
  const lk = S.model && S.model.scope && S.model.scope.locked;
  $$("[data-lockbanner]").forEach((b) => {
    b.hidden = !lk;
    if (lk) b.textContent = `This model is locked${lk.by ? " by " + lk.by : ""}${lk.reason ? ": " + lk.reason : ""}. Unlock it under "Versions and lock" in step 2 before editing.`;
  });
}

/* ---------------- templates ---------------- */
function tplCards(list, opts = {}) {
  if (!list.length) return '<p class="empty">No templates.</p>';
  const cats = {};
  list.forEach((t) => (cats[t.category || "Other"] = cats[t.category || "Other"] || []).push(t));
  return Object.entries(cats).map(([c, ts]) => `<h3>${esc(c)}</h3><div class="cards">${ts.map((t) => `<div class="card">
    <b>${esc(t.name)}</b><span class="hint">${esc(t.standard || (t.builtin ? "" : "Your template"))}</span>
    <p>${esc(t.description || "")}</p>
    <span class="meta">${(t.lines || []).length} lines, ${(t.parameters || []).length} parameters, ${esc(t.amount ?? 1)} ${esc(t.unit || "")}</span>
    <div class="row"><input data-tplname="${esc(t.id)}" class="grow" value="${esc(t.name)}" aria-label="Name of the new model">
      <button class="primary" data-tpluse="${esc(t.id)}">Use</button>${!t.builtin && opts.remove ? `<button class="ghost danger" data-tplrm="${t.db_id}">Remove</button>` : ""}</div></div>`).join("")}</div>`).join("");
}
async function useTemplate(btn, root) {
  return guard(btn, async () => {
    if (!S.status.project) throw new Error("Open a project first.");
    const name = $(`[data-tplname="${CSS.escape(btn.dataset.tpluse)}"]`, root).value.trim();
    const r = await api("POST", "/api/model-templates/apply", { id: btn.dataset.tpluse, name, location: ((S.model && S.model.scope) || {}).geography || "" });
    S.result = null; await refreshModels(r.model_id); go("scope");
    toast(r.missing.length ? `Model created. No dataset found for: ${r.missing.join(", ")}. Add those lines in step 3.` : `Model created with ${r.linked.length} linked lines. Check each dataset choice in step 3.`, !!r.missing.length);
  });
}
$("#btnTemplates").addEventListener("click", (e) => guard(e.target, async () => {
  const p = $("#tplPanel");
  if (!p.hidden) { p.hidden = true; return; }
  const { templates } = await api("GET", "/api/model-templates");
  p.hidden = false;
  p.innerHTML = `<div class="row"><h3 class="grow">Start from a template</h3><button class="ghost" data-close>Close</button></div>${tplCards(templates)}
    ${S.model ? `<h3>Save "${esc(S.model.name)}" as your own template</h3><div class="row"><input id="tplSaveName" class="grow" placeholder="Template name" value="${esc(S.model.name)}"><input id="tplSaveCat" placeholder="Category" value="My templates"><button id="btnTplSave">Save as template</button></div>` : ""}`;
}));
$("#tplPanel").addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) { $("#tplPanel").hidden = true; return; }
  const u = e.target.closest("[data-tpluse]");
  if (u) useTemplate(u, $("#tplPanel"));
  if (e.target.id === "btnTplSave") guard(e.target, async () => {
    await api("POST", "/api/model-templates/save", { model_id: S.model.id, name: $("#tplSaveName").value.trim(), category: $("#tplSaveCat").value.trim() });
    toast("Template saved in the library; every project can use it.");
  });
});

/* ---------------- versions and lock ---------------- */
async function loadVersions() {
  if (!S.model) { $("#versionList").innerHTML = ""; $("#diffOut").innerHTML = ""; return; }
  const { versions, lock } = await api("GET", `/api/models/${S.model.id}/versions`);
  $("#versionList").innerHTML = versions.length ? versions.map((v) => `<li><span class="grow"><b>${esc(v.name)}</b><br><span class="meta">${when(v.ts)}${v.author ? ", " + esc(v.author) : ""}</span></span>
    <button class="ghost" data-vdiff="${v.id}">Compare with current</button><button class="ghost" data-vrestore="${v.id}">Restore</button></li>`).join("")
    : '<li class="empty">No saved versions yet.</li>';
  const opts = `<option value="current">Current model</option>` + versions.map((v) => `<option value="${v.id}">${esc(v.name)}</option>`).join("");
  $("#diffA").innerHTML = opts; $("#diffB").innerHTML = opts;
  if (versions.length) $("#diffA").value = String(versions[0].id);
  $("#lockState").textContent = lock ? `Locked${lock.by ? " by " + lock.by : ""} on ${when(lock.ts)}${lock.reason ? ": " + lock.reason : ""}.` : "Not locked: anyone can edit this model.";
  $("#btnLock").textContent = lock ? "Unlock model" : "Lock model";
  $("#lockReason").hidden = !!lock;
}
$("#btnSaveVersion").addEventListener("click", (e) => guard(e.target, async () => {
  needModel();
  await api("POST", `/api/models/${S.model.id}/versions`, { name: $("#versionName").value.trim() });
  $("#versionName").value = ""; await loadVersions(); toast("Version saved.");
}));
function renderDiff(d) {
  if (d.identical) return `<p class="ok">${esc(d.a)} and ${esc(d.b)} are identical.</p>`;
  const v = (x) => (x === null || x === undefined ? "-" : typeof x === "object" ? esc(JSON.stringify(x)) : esc(x));
  let h = `<p class="hint">From <b>${esc(d.a)}</b> to <b>${esc(d.b)}</b>.</p>`;
  if (d.added.length) h += `<h4>Added lines</h4><ul>${d.added.map((l) => `<li class="ok">${esc(l.name)}: ${v(l.amount)} ${esc(l.unit)}${l.stage ? ", " + esc(l.stage) : ""}</li>`).join("")}</ul>`;
  if (d.removed.length) h += `<h4>Removed lines</h4><ul>${d.removed.map((l) => `<li class="danger">${esc(l.name)}: ${v(l.amount)} ${esc(l.unit)}</li>`).join("")}</ul>`;
  if (d.changed.length) h += `<h4>Changed lines</h4><table><thead><tr><th>Line</th><th>Field</th><th>Before</th><th>After</th></tr></thead><tbody>${d.changed.map((c) => `<tr><td>${esc(c.line)}</td><td>${esc(c.field)}</td><td>${v(c.a)}</td><td>${v(c.b)}</td></tr>`).join("")}</tbody></table>`;
  if (d.parameters.length) h += `<h4>Parameters</h4><table><tbody>${d.parameters.map((p) => `<tr><td><code>${esc(p.name)}</code></td><td>${v(p.a)}</td><td>${v(p.b)}</td></tr>`).join("")}</tbody></table>`;
  if (d.scope.length) h += `<h4>Goal, scope and functional unit</h4><table><tbody>${d.scope.map((p) => `<tr><td>${esc(p.field)}</td><td>${v(p.a)}</td><td>${v(p.b)}</td></tr>`).join("")}</tbody></table>`;
  return h;
}
async function showDiff(a, b) {
  const d = await api("GET", `/api/versions/diff?model_id=${S.model.id}&a=${a}&b=${b}`);
  $("#diffOut").innerHTML = renderDiff(d);
}
$("#btnDiff").addEventListener("click", (e) => guard(e.target, () => showDiff($("#diffA").value, $("#diffB").value)));
$("#versionList").addEventListener("click", (e) => {
  const d = e.target.closest("[data-vdiff]"), r = e.target.closest("[data-vrestore]");
  if (d) guard(d, () => showDiff(d.dataset.vdiff, "current"));
  if (r && confirm("Restore this version? The current state is saved as a version first, so nothing is lost.")) guard(r, async () => {
    const { model } = await api("POST", `/api/versions/${r.dataset.vrestore}/restore`, {});
    S.model = model; S.result = null; fillScope(); loadParams(); await loadVersions(); markSteps(); toast("Version restored.");
  });
});
$("#btnLock").addEventListener("click", (e) => guard(e.target, async () => {
  needModel();
  const locked = !(S.model.scope && S.model.scope.locked);
  const { model } = await api("POST", `/api/models/${S.model.id}/lock`, { locked, reason: $("#lockReason").value.trim() });
  S.model = model; $("#lockReason").value = ""; renderLockBanners(); await loadVersions();
  toast(locked ? "Model locked." : "Model unlocked.");
}));

/* ---------------- comments ---------------- */
async function loadComments() {
  if (!S.model || !S.status.project) { S.comments = []; renderComments(); return; }
  S.comments = (await api("GET", `/api/models/${S.model.id}/comments`)).comments;
  renderComments();
  if (S.step === "inventory") renderInventory();
}
function renderComments() {
  const show = $("#showResolved").checked;
  let list = S.comments.filter((c) => show || !c.resolved);
  const line = S.commentLine && S.model ? S.model.inputs.find((i) => i.id === S.commentLine) : null;
  if (line) list = list.filter((c) => c.input_id === line.id);
  $("#commentFilter").hidden = !line;
  if (line) $("#commentFilter").innerHTML = `Notes on <b>${esc(line.label || line.target.name)}</b>. <button class="ghost" data-allcomments>Show all notes</button>`;
  const open = S.comments.filter((c) => !c.resolved).length;
  $("#commentCount").textContent = open ? `(${open} open)` : "";
  const lineName = (id) => { const l = S.model && S.model.inputs.find((i) => i.id === id); return l ? (l.label || l.target.name) : "removed line"; };
  $("#commentList").innerHTML = list.length ? list.map((c) => `<li class="${c.resolved ? "resolved" : ""}"><div class="grow"><b>${esc(c.author || "Anonymous")}</b> <span class="meta">${when(c.ts)}${c.input_id ? ", on " + esc(lineName(c.input_id)) : ""}</span><br>${esc(c.text)}</div>
    <button class="ghost" data-cresolve="${c.id}" data-r="${c.resolved ? 0 : 1}">${c.resolved ? "Reopen" : "Resolve"}</button><button class="ghost danger" data-cdel="${c.id}">Delete</button></li>`).join("")
    : '<li class="empty">No comments.</li>';
}
$("#showResolved").addEventListener("change", renderComments);
$("#commentsBlock").addEventListener("click", (e) => {
  if (e.target.closest("[data-allcomments]")) { S.commentLine = null; renderComments(); return; }
  const r = e.target.closest("[data-cresolve]"), d = e.target.closest("[data-cdel]");
  if (r) guard(r, async () => { await api("PATCH", `/api/comments/${r.dataset.cresolve}`, { resolved: r.dataset.r === "1" }); await loadComments(); });
  if (d && confirm("Delete this comment?")) guard(d, async () => { await api("DELETE", `/api/comments/${d.dataset.cdel}`); await loadComments(); });
});
$("#commentForm").addEventListener("submit", (e) => {
  e.preventDefault();
  guard($("button", e.target), async () => {
    needModel();
    await api("POST", `/api/models/${S.model.id}/comments`, { text: e.target.text.value, input_id: S.commentLine });
    e.target.reset(); await loadComments();
  });
});

/* ---------------- literature import ---------------- */
$("#btnLit").addEventListener("click", () => { $("#litPanel").hidden = !$("#litPanel").hidden; $("#extPanel").hidden = true; });
$("#btnExt").addEventListener("click", () => { $("#extPanel").hidden = !$("#extPanel").hidden; $("#litPanel").hidden = true; });
$$("#litPanel [data-close], #extPanel [data-close]").forEach((b) => b.addEventListener("click", () => (b.closest(".subpanel").hidden = true)));
$("#btnLitExample").addEventListener("click", (e) => guard(e.target, async () => { $("#litText").value = (await examples()).literature; $("#litSource").value = "Example et al. (illustrative)"; }));
async function litParse(body, btn) {
  return guard(btn, async () => {
    needModel();
    const r = await api("POST", "/api/literature/parse", { ...body, location: $("#litLoc").value.trim() });
    S.lit = r.rows;
    $("#litOut").innerHTML = `<p class="hint">${r.rows.length} rows found${r.skipped.length ? `, ${r.skipped.length} lines skipped (captions or lines without a name and a number)` : ""}. Check every match; untick rows you do not want.</p>
      <div class="table-wrap"><table class="lit-table"><thead><tr><th></th><th>From the table</th><th>Amount</th><th>Unit</th><th>Stage</th><th>Dataset or flow</th><th>Credit</th></tr></thead><tbody>
      ${r.rows.map((x, i) => `<tr data-i="${i}"><td><input type="checkbox" class="inc" ${x.candidates.length ? "checked" : ""} aria-label="Include"></td>
        <td>${esc(x.name)}<br><span class="hint">${esc(x.source_line)}</span></td>
        <td><input class="amt" type="number" step="any" value="${x.amount}"></td><td><input class="unit" size="6" value="${esc(x.unit || (x.candidates[0] || {}).unit || "")}"></td>
        <td><input class="stage" size="8" list="stageList" value="${esc(x.stage || "")}"></td>
        <td><select class="cand">${x.candidates.map((c, k) => `<option value="${k}">${esc(c.name)} [${esc(c.location)}], ${esc(c.unit)}, ${esc(c.db)}</option>`).join("")}<option value="">(none: skip)</option></select></td>
        <td><input type="checkbox" class="avoid" aria-label="Avoided product"></td></tr>`).join("")}</tbody></table></div>
      <div class="row"><button class="primary" id="btnLitAdd">Add ticked rows to the model</button></div>`;
  });
}
$("#btnLitParse").addEventListener("click", (e) => litParse({ text: $("#litText").value }, e.target));
$("#btnLitFile").addEventListener("click", async (e) => {
  if (desktop) { const p = await desktop.pickFile(); if (p) litParse({ path: p }, e.target); }
  else $("#litPathRow").hidden = !$("#litPathRow").hidden;
});
$("#btnLitPath").addEventListener("click", (e) => litParse({ path: $("#litPath").value }, e.target));
$("#litOut").addEventListener("click", (e) => {
  if (e.target.id !== "btnLitAdd") return;
  guard(e.target, async () => {
    const rows = $$("#litOut tbody tr").filter((tr) => $(".inc", tr).checked).map((tr) => {
      const x = S.lit[Number(tr.dataset.i)], k = $(".cand", tr).value;
      if (k === "") return null;
      const c = x.candidates[Number(k)];
      return { kind: c.kind, ref_id: c.id, amount: Number($(".amt", tr).value), unit: $(".unit", tr).value.trim() || c.unit,
        stage: $(".stage", tr).value.trim(), avoided: $(".avoid", tr).checked, name: x.name, source_line: x.source_line };
    }).filter(Boolean);
    if (!rows.length) throw new Error("Tick at least one row with a dataset.");
    const r = await api("POST", `/api/models/${S.model.id}/literature`, { rows, source: $("#litSource").value.trim() });
    if (r.problems.length) { $("#litOut").insertAdjacentHTML("afterbegin", `<div class="problems"><b>Nothing was added:</b><ul>${r.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`); return; }
    S.model = r.model; S.result = null; renderInventory(); markSteps(); $("#litPanel").hidden = true; $("#litOut").innerHTML = "";
    toast(`${r.added} lines added. Rate their data quality in the table.`);
  });
});

/* ---------------- external model emissions ---------------- */
$("#btnExtExample").addEventListener("click", (e) => guard(e.target, async () => {
  $("#extText").value = (await examples()).external; $("#extStage").value = "B1 Use"; $("#extSource").value = "Leaching model (example)";
}));
async function extImport(body, btn) {
  return guard(btn, async () => {
    needModel();
    const r = await api("POST", `/api/models/${S.model.id}/external`, { ...body, stage: $("#extStage").value.trim(), scale: Number($("#extScale").value) || 1,
      aggregate: $("#extAgg").checked, create_missing: $("#extCreate").checked, source: $("#extSource").value.trim() });
    if (r.problems.length) { $("#extOut").innerHTML = `<div class="problems"><b>Nothing was imported:</b><ul>${r.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`; return; }
    S.model = r.model; S.result = null; renderInventory(); markSteps(); $("#extOut").innerHTML = "";
    toast(`${r.added} emission lines added.`);
  });
}
$("#btnExtImport").addEventListener("click", (e) => extImport({ text: $("#extText").value }, e.target));
$("#btnExtFile").addEventListener("click", async (e) => {
  if (desktop) { const p = await desktop.pickFile("csv"); if (p) extImport({ path: p }, e.target); }
  else toast("Paste the CSV text into the box. Choosing files works in the desktop app.");
});

/* ---------------- background scenario selection (step 4) ---------------- */
function renderBgSelect() {
  const list = (S.status && S.status.bg_scenarios) || [];
  const prev = $("#bgSel").value || ls.get(projKey("bg"), "");
  $("#bgSel").innerHTML = '<option value="">As imported (attributional)</option>' +
    ["prospective", "consequential"].map((k) => { const l = list.filter((b) => b.kind === k); return l.length ? `<optgroup label="${k === "prospective" ? "Prospective" : "Consequential"}">${l.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("")}</optgroup>` : ""; }).join("");
  $("#bgSel").value = list.some((b) => String(b.id) === String(prev)) ? String(prev) : "";
  bgYearVis();
}
function bgYearVis() {
  const sc = ((S.status && S.status.bg_scenarios) || []).find((b) => String(b.id) === $("#bgSel").value);
  $("#bgYearLabel").hidden = !(sc && sc.kind === "prospective");
}
$("#bgSel").addEventListener("change", () => { ls.set(projKey("bg"), $("#bgSel").value); bgYearVis(); });

/* ---------------- map of results by location ---------------- */
async function renderMap() {
  const r = S.result;
  if (!r) return;
  if (!S.coords) S.coords = await api("GET", "/api/coords");
  if (S.world === undefined) { try { const r = await fetch("world.json"); S.world = r.ok ? await r.json() : null; } catch (e) { S.world = null; } }
  const x = r.results[S.cat];
  const W = 720, H = 360, px = (lon) => ((lon + 180) / 360) * W, py = (lat) => ((90 - lat) / 180) * H;
  const locs = x.by_location || [];
  const max = Math.max(...locs.map((l) => Math.abs(l.impact)), 1e-300);
  const total = locs.reduce((a, l) => a + Math.abs(l.impact), 0) || 1;
  const coord = (code) => { const c = String(code || "").toUpperCase(); return S.coords.coords[c] || S.coords.coords[c.split(/[-_ ]/)[0]]; };
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" class="map" role="img" aria-label="Map of ${esc(x.category)} by location">
    <rect width="${W}" height="${H}" fill="var(--paper)"/>`;
  for (let lon = -150; lon <= 150; lon += 30) svg += `<line x1="${px(lon)}" x2="${px(lon)}" y1="0" y2="${H}" stroke="var(--rule)" stroke-width=".5"/>`;
  for (let lat = -60; lat <= 60; lat += 30) svg += `<line x1="0" x2="${W}" y1="${py(lat)}" y2="${py(lat)}" stroke="var(--rule)" stroke-width=".5"/>`;
  const byCode = {};
  locs.forEach((l) => (byCode[String(l.location).toUpperCase()] = l));
  const shaded = new Set();
  if (S.world) {
    const posMax = Math.max(...locs.map((l) => (l.impact > 0 ? l.impact : 0)), 1e-300);
    S.world.countries.forEach((c) => {
      const l = byCode[c.code];
      let fill = "var(--spruce-weak)";
      if (l) { shaded.add(c.code); const t = Math.sqrt(Math.abs(l.impact) / (l.impact > 0 ? posMax : max)); fill = `color-mix(in srgb, ${l.impact < 0 ? "var(--neg)" : "var(--ochre)"} ${Math.round(25 + 75 * t)}%, var(--panel))`; }
      svg += `<path d="${c.rings.map((r) => "M" + r.map(([lo, la]) => `${px(lo).toFixed(1)},${py(la).toFixed(1)}`).join("L") + "Z").join("")}" fill="${fill}" stroke="var(--panel)" stroke-width=".5">${l ? `<title>${esc(c.name)}: ${fmt(l.impact)} ${esc(x.unit)}</title>` : `<title>${esc(c.name)}</title>`}</path>`;
    });
  } else {
    Object.values(S.coords.continents).forEach((pts) => { svg += `<polygon points="${pts.map(([lo, la]) => `${px(lo).toFixed(1)},${py(la).toFixed(1)}`).join(" ")}" fill="var(--spruce-weak)" stroke="var(--rule)"/>`; });
  }
  const placed = locs.map((l) => ({ ...l, c: coord(l.location) })).filter((l) => l.c && !shaded.has(String(l.location).toUpperCase())).sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
  const labels = [];
  placed.forEach((l, i) => {
    const rad = 4 + 30 * Math.sqrt(Math.abs(l.impact) / max), cx = px(l.c[1]), cy = py(l.c[0]);
    svg += `<circle cx="${cx}" cy="${cy}" r="${rad.toFixed(1)}" fill="${l.impact < 0 ? "var(--neg)" : i === 0 ? "var(--ochre)" : "var(--spruce)"}" fill-opacity=".55" stroke="var(--panel)"><title>${esc(l.location)}: ${fmt(l.impact)} ${esc(x.unit)}</title></circle>`;
    if (i >= 12) return;
    let ly = cy - rad - 3;  // above the bubble, moved down a line while it would overlap an earlier label
    while (labels.some((q) => Math.abs(q[0] - cx) < 34 && Math.abs(q[1] - ly) < 12)) ly += 12;
    labels.push([cx, ly]);
    svg += `<text x="${cx}" y="${ly}" font-size="10.5" text-anchor="middle" fill="var(--ink)" stroke="var(--paper)" stroke-width="3" paint-order="stroke">${esc(l.location)}</text>`;
  });
  svg += "</svg>";
  const unplaced = locs.filter((l) => !coord(l.location));
  const note = S.world ? "Countries are shaded by their impact (darker = larger; blue = credits); regions such as GLO, RER or RoW are drawn as bubbles. Natural Earth outlines." : "Schematic outline; the installer adds real country outlines when it is built with an internet connection.";
  $("#mapOut").innerHTML = svg + `<p class="hint">${note}</p>` + (unplaced.length ? `<p class="hint">Without coordinates (not drawn): ${unplaced.map((l) => esc(l.location)).join(", ")}.</p>` : "");
  $("#locTable").innerHTML = `<thead><tr><th>Location</th><th class="num">${esc(x.category)} (${esc(x.unit)})</th><th class="num">Share</th></tr></thead><tbody>` +
    locs.map((l) => `<tr><td>${esc(l.location)}</td><td class="num">${fmt(l.impact)}</td><td class="num">${(100 * Math.abs(l.impact) / total).toFixed(1)}%</td></tr>`).join("") + "</tbody>";
}

/* ---------------- toxicity coverage ---------------- */
function renderTox() {
  const t = S.result.toxicity_coverage || [];
  const site = S.result.site_factors || [];
  $("#toxCov").innerHTML = (t.length ? t.map((c) => `<p><b>${esc(c.category)}</b> (${esc(c.family)}): ${c.n_missing ? `<span class="warn">${c.n_missing} of ${c.n_emitted} emitted substances have no factor</span>; the result is a lower bound.` : `<span class="ok">all ${c.n_emitted} emitted substances have a factor.</span>`}</p>
    ${c.missing.length ? `<table><thead><tr><th>Substance</th><th>Compartment</th><th class="num">Amount</th></tr></thead><tbody>${c.missing.map((m) => `<tr><td>${esc(m.name)}</td><td>${esc(m.context)}</td><td class="num">${fmt(m.amount)} ${esc(m.unit)}</td></tr>`).join("")}</tbody></table>` : ""}`).join("")
    : '<p class="hint">No toxicity category selected. Greenhouse gases, acidifying and eutrophying substances and particles are left to their own categories.</p>') +
    (site.length ? `<h3>Site-specific factors used</h3><table><thead><tr><th>Category</th><th>Flow</th><th class="num">Generic</th><th class="num">Site</th><th>Justification</th></tr></thead><tbody>${site.map((s) => `<tr><td>${esc(s.category)}</td><td>${esc(s.flow)}</td><td class="num">${fmt(s.generic)}</td><td class="num">${fmt(s.site)}</td><td>${esc(s.note || "")}</td></tr>`).join("")}</tbody></table>` : "");
}

/* ---------------- explore parameters: sweep, optimisation ---------------- */
async function prepareExplore() {
  const r = S.result;
  if (!r) return;
  const p = await api("GET", `/api/parameters?model_id=${r.model.id}`);
  const free = [...p.project, ...(p.model || [])].filter((x) => !x.formula);
  const byName = {};
  free.forEach((x) => (byName[x.name] = x));
  const list = Object.values(byName);
  $("#sweepParams").innerHTML = list.length ? `<table class="sweep-table"><thead><tr><th>Use</th><th>Parameter</th><th class="num">Value</th><th>From</th><th>To</th><th>Steps</th></tr></thead><tbody>${list.map((x, i) => {
    const v = (p.values || {})[x.name] ?? x.value;
    const lo = x.utype === 3 || x.utype === 4 ? x.p1 : v * 0.7, hi = x.utype === 3 ? x.p3 : x.utype === 4 ? x.p2 : v * 1.3;
    return `<tr data-p="${esc(x.name)}"><td><input type="checkbox" class="use" ${i < 1 ? "checked" : ""} aria-label="Use"></td><td><code>${esc(x.name)}</code></td><td class="num">${fmt(v)}</td>
      <td><input class="lo" type="number" step="any" value="${Number(lo.toPrecision(6))}"></td><td><input class="hi" type="number" step="any" value="${Number(hi.toPrecision(6))}"></td><td><input class="n" type="number" min="2" max="41" value="11"></td></tr>`;
  }).join("")}</tbody></table>` : '<p class="empty">This model has no free parameters. Define parameters in step 2 and use them in formulas.</p>';
  const opts = r.results.map((x, k) => `<option value="${k}">${esc(x.category)} (${esc(x.unit)})</option>`).join("");
  $("#optObj").innerHTML = opts; $("#optObj2").innerHTML = '<option value="">None</option>' + opts; $("#optCon").innerHTML = '<option value="">None</option>' + opts;
  $("#optObj").value = String(S.cat);
}
function chosenParams() {
  const ps = $$("#sweepParams tr[data-p]").filter((tr) => $(".use", tr).checked).map((tr) => ({ name: tr.dataset.p, lo: Number($(".lo", tr).value), hi: Number($(".hi", tr).value), n: Number($(".n", tr).value) || 11 }));
  if (!ps.length) throw new Error("Tick at least one parameter.");
  ps.forEach((p) => { if (!(p.hi > p.lo)) throw new Error(`${p.name}: 'To' must be larger than 'From'.`); });
  return ps;
}
function lineChart(xs, ys, xl, yl) {
  const W = 560, H = 220, L = 60, B = 30, minY = Math.min(...ys), maxY = Math.max(...ys), dx = xs[xs.length - 1] - xs[0] || 1, dy = maxY - minY || Math.abs(maxY) || 1;
  const X = (v) => L + ((v - xs[0]) / dx) * (W - L - 10), Y = (v) => 10 + (1 - (v - minY) / dy) * (H - B - 10);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:640px" role="img" aria-label="${esc(yl)} against ${esc(xl)}">
    <line x1="${L}" x2="${W - 10}" y1="${H - B}" y2="${H - B}" stroke="var(--rule)"/><line x1="${L}" x2="${L}" y1="10" y2="${H - B}" stroke="var(--rule)"/>
    <polyline fill="none" stroke="var(--spruce)" stroke-width="2" points="${xs.map((x, i) => `${X(x).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(" ")}"/>
    ${xs.map((x, i) => `<circle cx="${X(x)}" cy="${Y(ys[i])}" r="2.5" fill="var(--spruce)"><title>${fmt(x)}: ${fmt(ys[i])}</title></circle>`).join("")}
    <text x="${L}" y="${H - 8}" font-size="11" fill="var(--ink-soft)">${fmt(xs[0])}</text><text x="${W - 10}" y="${H - 8}" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(xs[xs.length - 1])}</text>
    <text x="${(L + W) / 2}" y="${H - 8}" font-size="11" text-anchor="middle" fill="var(--ink)">${esc(xl)}</text>
    <text x="${L - 6}" y="16" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(maxY)}</text><text x="${L - 6}" y="${H - B}" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(minY)}</text></svg>`;
}
function heatmap(s, k) {
  const vals = s.grid.flat().map((v) => v[k]), mn = Math.min(...vals), mx = Math.max(...vals);
  const cw = Math.min(46, 520 / s.x.length), ch = Math.min(30, 300 / s.y.length), L = 70, T = 10;
  const col = (v) => { const t = mx > mn ? (v - mn) / (mx - mn) : 0.5; return `color-mix(in srgb, var(--ochre) ${Math.round(t * 100)}%, var(--spruce-weak))`; };
  let svg = `<svg viewBox="0 0 ${L + cw * s.x.length + 10} ${T + ch * s.y.length + 40}" width="100%" style="max-width:640px" role="img" aria-label="Heat map">`;
  s.grid.forEach((row, j) => row.forEach((v, i) => { svg += `<rect x="${L + i * cw}" y="${T + (s.y.length - 1 - j) * ch}" width="${cw}" height="${ch}" fill="${col(v[k])}"><title>${s.params[0]} ${fmt(s.x[i])}, ${s.params[1]} ${fmt(s.y[j])}: ${fmt(v[k])}</title></rect>`; }));
  svg += `<text x="${L}" y="${T + ch * s.y.length + 16}" font-size="11" fill="var(--ink-soft)">${fmt(s.x[0])}</text><text x="${L + cw * s.x.length}" y="${T + ch * s.y.length + 16}" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(s.x[s.x.length - 1])}</text>
    <text x="${L + (cw * s.x.length) / 2}" y="${T + ch * s.y.length + 32}" font-size="11" text-anchor="middle">${esc(s.params[0])}</text>
    <text x="${L - 6}" y="${T + 10}" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(s.y[s.y.length - 1])}</text><text x="${L - 6}" y="${T + ch * s.y.length}" font-size="11" text-anchor="end" fill="var(--ink-soft)">${fmt(s.y[0])}</text>
    <text x="4" y="${T + (ch * s.y.length) / 2}" font-size="11">${esc(s.params[1])}</text></svg>`;
  return svg + `<p class="hint">Lowest ${fmt(mn)}, highest ${fmt(mx)}. Light cells are lower.</p>`;
}
let SWEEP = null;
function drawSweep() {
  const s = SWEEP, k = Number($("#sweepCat").value) || 0, m = s.methods[k];
  $("#sweepChart").innerHTML = s.params.length === 1 ? lineChart(s.x, s.values.map((v) => v[k]), s.params[0], `${m.category} (${m.unit})`) : heatmap(s, k);
}
$("#btnSweep").addEventListener("click", (e) => guard(e.target, async () => {
  const r = S.result, ps = chosenParams().slice(0, 2);
  const s = await api("POST", "/api/sweep", { model_id: r.model.id, method_ids: r.results.map((x) => x.method_id), params: ps, scenario: r.scenario, ...bgBody() });
  SWEEP = s;
  $("#sweepOut").innerHTML = `<div class="row"><label class="inline">Category <select id="sweepCat">${s.methods.map((m, k) => `<option value="${k}" ${k === S.cat ? "selected" : ""}>${esc(m.category)}</option>`).join("")}</select></label><span class="hint">${s.evaluations} calculations${ps.length < chosenParams().length ? "; a sweep uses the first two ticked parameters" : ""}.</span></div><div id="sweepChart"></div>`;
  $("#sweepCat").addEventListener("change", drawSweep);
  drawSweep();
}));
function scatter(p, xl, yl) {
  const W = 560, H = 260, L = 64, B = 34, xs = p.points.map((q) => q[0]), ys = p.points.map((q) => q[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (v) => L + ((v - x0) / (x1 - x0 || 1)) * (W - L - 10), Y = (v) => 10 + (1 - (v - y0) / (y1 - y0 || 1)) * (H - B - 10);
  const f = [...p.front].sort((a, b) => a.x - b.x);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:640px" role="img" aria-label="Pareto front">
    <line x1="${L}" x2="${W - 10}" y1="${H - B}" y2="${H - B}" stroke="var(--rule)"/><line x1="${L}" x2="${L}" y1="10" y2="${H - B}" stroke="var(--rule)"/>
    ${p.points.map((q) => `<circle cx="${X(q[0]).toFixed(1)}" cy="${Y(q[1]).toFixed(1)}" r="2" fill="var(--ink-soft)" opacity=".35"/>`).join("")}
    <polyline fill="none" stroke="var(--ochre)" stroke-width="2" points="${f.map((q) => `${X(q.x).toFixed(1)},${Y(q.y).toFixed(1)}`).join(" ")}"/>
    ${f.map((q) => `<circle cx="${X(q.x)}" cy="${Y(q.y)}" r="4" fill="var(--ochre)"><title>${Object.entries(q.values).map(([k, v]) => `${k} = ${fmt(v)}`).join(", ")}</title></circle>`).join("")}
    <text x="${(L + W) / 2}" y="${H - 8}" font-size="11" text-anchor="middle">${esc(xl)}</text><text x="${L}" y="${H - 20}" font-size="10.5" fill="var(--ink-soft)">${fmt(x0)}</text><text x="${W - 10}" y="${H - 20}" font-size="10.5" text-anchor="end" fill="var(--ink-soft)">${fmt(x1)}</text>
    <text x="8" y="20" font-size="11">${esc(yl)}</text><text x="${L - 6}" y="${H - B}" font-size="10.5" text-anchor="end" fill="var(--ink-soft)">${fmt(y0)}</text><text x="${L - 6}" y="24" font-size="10.5" text-anchor="end" fill="var(--ink-soft)">${fmt(y1)}</text></svg>`;
}
$("#btnOptimise").addEventListener("click", (e) => guard(e.target, async () => {
  const r = S.result, ps = chosenParams().slice(0, 6);
  const con = $("#optCon").value, mx = $("#optConMax").value;
  if (con !== "" && mx === "") throw new Error("Enter the upper limit, or choose 'None'.");
  const { job } = await api("POST", "/api/optimise", { model_id: r.model.id, method_ids: r.results.map((x) => x.method_id), params: ps,
    objective: Number($("#optObj").value), second_objective: $("#optObj2").value === "" ? null : Number($("#optObj2").value),
    constraints: con === "" ? [] : [{ index: Number(con), max: Number(mx) }], scenario: r.scenario, ...bgBody() });
  $("#optOut").innerHTML = '<p class="hint">Optimising; progress is shown at the bottom left.</p>';
  watchJob(job, { quiet: true, onDone: async (j) => {
    const o = j.result, m = o.methods;
    let h = `<p><b>${o.optimum.feasible ? "Optimum found" : "No parameter values meet the limit; the closest values are shown"}.</b> ${esc(m[o.objective].category)}: ${fmt(o.baseline.totals[o.objective])} at the current values, ${fmt(o.optimum.totals[o.objective])} at the optimum${o.improvement_percent != null ? ` (${o.improvement_percent.toFixed(1)} % lower)` : ""}. ${o.evaluations} calculations.</p>
      <table><thead><tr><th>Parameter</th><th class="num">Current</th><th class="num">Optimum</th><th>Bounds</th></tr></thead><tbody>${o.params.map((n, i) => `<tr><td><code>${esc(n)}</code></td><td class="num">${fmt(o.baseline.values[n])}</td><td class="num">${fmt(o.optimum.values[n])}</td><td>${fmt(o.bounds[i][0])} to ${fmt(o.bounds[i][1])}</td></tr>`).join("")}</tbody></table>
      <table><thead><tr><th>Category</th><th class="num">Current</th><th class="num">Optimum</th></tr></thead><tbody>${m.map((x, k) => `<tr><td>${esc(x.category)} (${esc(x.unit)})</td><td class="num">${fmt(o.baseline.totals[k])}</td><td class="num">${fmt(o.optimum.totals[k])}</td></tr>`).join("")}</tbody></table>`;
    if (o.pareto) {
      const px = m[o.pareto.x_index], pyy = m[o.pareto.y_index];
      h += `<h4>Trade-off between ${esc(px.category)} and ${esc(pyy.category)}</h4>${scatter(o.pareto, `${px.category} (${px.unit})`, `${pyy.category} (${pyy.unit})`)}
        <p class="hint">Grey: sampled parameter combinations. Ochre: Pareto front, where one category cannot improve without the other getting worse.</p>
        <table><thead><tr><th class="num">${esc(px.category)}</th><th class="num">${esc(pyy.category)}</th><th>Parameter values</th></tr></thead><tbody>${o.pareto.front.slice(0, 15).map((q) => `<tr><td class="num">${fmt(q.x)}</td><td class="num">${fmt(q.y)}</td><td>${Object.entries(q.values).map(([k, v]) => `${esc(k)} = ${fmt(v)}`).join(", ")}</td></tr>`).join("")}</tbody></table>`;
    }
    $("#optOut").innerHTML = h;
  } });
}));

/* ---------------- PEF ---------------- */
async function renderPef() {
  const r = S.result, out = $("#pefOut");
  if (!r) return;
  if (!r.nw_set) { out.innerHTML = '<p class="hint">The PEF analysis needs normalisation and weighting. Choose a factor set in step 4 (EF 3.1, or the demo set) and calculate again.</p>'; return; }
  if (r._pef) { out.innerHTML = r._pef; return; }
  out.innerHTML = '<p class="hint">Calculating...</p>';
  try {
    const p = await api("POST", "/api/pef", calcBody());
    const share = (x) => `${(100 * x.share).toFixed(1)}%`;
    const list = (items) => items.length ? `<ul>${items.map((i) => `<li>${esc(i.name)} <span class="hint">${share(i)}</span></li>`).join("")}</ul>` : '<p class="hint">-</p>';
    const tot = p.categories.reduce((a, c) => a + Math.abs(c.weighted || 0), 0) || 1;
    const rel = new Set(p.relevant_categories.map((c) => c.category));
    const html = `<h2>Most relevant results (PEF)</h2><p class="hint">${esc(p.note)}</p>
      <p>Single score (${esc(p.nw_set)}): <b>${fmt(p.single_score)}</b>${p.missing.length ? `. No factor for: ${p.missing.map(esc).join(", ")}` : ""}.</p>
      <table><thead><tr><th>Impact category</th><th class="num">Normalised</th><th class="num">Weighted</th><th class="num">Share</th><th>Most relevant</th></tr></thead><tbody>
      ${[...p.categories].sort((a, b) => Math.abs(b.weighted) - Math.abs(a.weighted)).map((c) => `<tr><td>${esc(c.category)}</td><td class="num">${fmt(c.normalised)}</td><td class="num">${fmt(c.weighted)}</td><td class="num">${(100 * Math.abs(c.weighted) / tot).toFixed(1)}%</td><td>${rel.has(c.category) ? '<span class="ok">yes</span>' : ""}</td></tr>`).join("")}</tbody></table>
      ${p.detail.map((d) => `<h3>${esc(d.category)}</h3><div class="pef-grid"><div><h4>Life cycle stages</h4>${list(d.stages)}</div><div><h4>Processes</h4>${list(d.processes)}</div><div><h4>Elementary flows</h4>${list(d.flows)}</div></div>`).join("")}`;
    r._pef = html; out.innerHTML = html;
  } catch (e) { out.innerHTML = `<p class="danger">${esc(e.message)}</p>`; }
}

/* ---------------- standards (step 6) ---------------- */
const EPD_COLUMNS = ["A1-A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "C1", "C2", "C3", "C4", "D"];
function fillEpdForm() {
  const f = $("#epdInfo"), e = (S.model && S.model.scope && S.model.scope.epd) || {};
  ["manufacturer", "site", "programme", "number", "pcr", "rsl", "issued", "valid_until", "verification", "verifier", "biogenic_product", "biogenic_packaging", "description", "specific_months", "pcr_version", "programme_statements"]
    .forEach((k) => (f[k].value = e[k] ?? ""));
  f.audience.value = e.audience || "B2B"; f.prospective.checked = !!e.prospective;
  const dec = new Set(e.declared || []);
  $("#epdModules").innerHTML = EPD_COLUMNS.map((c) => `<label class="inline"><input type="checkbox" value="${c}" ${dec.has(c) ? "checked" : ""}> ${c}</label>`).join("");
}
async function saveEpd() {
  needModel();
  const f = $("#epdInfo"), body = {};
  ["manufacturer", "site", "programme", "number", "pcr", "rsl", "issued", "valid_until", "verification", "verifier", "biogenic_product", "biogenic_packaging", "description", "specific_months", "pcr_version", "programme_statements"]
    .forEach((k) => (body[k] = f[k].value.trim()));
  body.audience = f.audience.value; body.prospective = f.prospective.checked ? "yes" : "";
  body.declared = $$("#epdModules input:checked").map((i) => i.value);
  const { model } = await api("POST", `/api/models/${S.model.id}/epd-info`, body);
  S.model = model;
}
$("#btnEpdSave").addEventListener("click", (e) => guard(e.target, async () => { await saveEpd(); toast("EPD details saved."); }));
$("#btnEpdCheck").addEventListener("click", (e) => guard(e.target, async () => {
  await saveEpd();
  const r = await api("POST", "/api/epd/check", calcBody());
  const c = r.checklist;
  $("#epdOut").innerHTML = `<p><b>${c.passed} of ${c.total} requirements met.</b> ${c.ready ? '<span class="ok">Ready for verification.</span>' : '<span class="danger">Not ready for submission: the draft can be created, but the open items must be solved first.</span>'} Declared modules: ${r.declared.join(", ") || "none"}.</p>
    <ul class="checks-list">${c.items.map((i) => `<li><span class="lvl ${i.ok ? "info" : "warning"}">${i.ok ? "met" : "open"}</span><span>${esc(i.text)}</span><span class="hint">${esc(i.ref)}</span></li>`).join("")}</ul>
    <div class="table-wrap"><table><thead><tr><th>Indicator</th><th>Unit</th>${r.columns.map((x) => `<th class="num">${x}</th>`).join("")}</tr></thead><tbody>
    ${r.modules.map((m) => `<tr><td>${esc(m.category)}</td><td>${esc(m.unit)}</td>${r.columns.map((x) => `<td class="num">${r.declared.includes(x) ? fmt(m.modules[x]) : "ND"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}));
async function stdExport(btn, path, label, ext, body) {
  return guard(btn, async () => { await exportTo(path, `${safeName(S.model && S.model.name)} ${label}.${ext}`, ext, body); });
}
$("#btnEpdWord").addEventListener("click", async (e) => { try { await saveEpd(); } catch (err) { toast(err.message, true); return; } stdExport(e.target, "/api/export/epd", "EPD", "docx", calcBody()); });
$("#btnEpdExcel").addEventListener("click", (e) => { try { stdExport(e.target, "/api/export/epd-excel", "EPD data", "xlsx", calcBody()); } catch (err) { toast(err.message, true); } });
$("#btnIso14067").addEventListener("click", (e) => { try { stdExport(e.target, "/api/export/iso14067", "ISO 14067", "docx", looseBody()); } catch (err) { toast(err.message, true); } });
$("#btnGhg").addEventListener("click", (e) => { try { stdExport(e.target, "/api/export/ghg", "GHG Protocol", "xlsx", looseBody()); } catch (err) { toast(err.message, true); } });

/* critical review */
const REVIEW_STATUS = ["", "accepted", "needs revision", "not applicable"];
$("#btnReviewLoad").addEventListener("click", (e) => guard(e.target, async () => {
  const b = looseBody();
  if (!b.method_ids.length) delete b.method_ids;
  const r = await api("POST", "/api/review", b);
  $("#reviewOut").innerHTML = `<p class="hint">${r.met} of ${r.total} items met by Cyclia's checks${b.method_ids ? "" : " (select categories in step 4 for the result-based items)"}.</p>
    <div class="table-wrap"><table class="review-table"><thead><tr><th>Clause</th><th>Requirement</th><th>Cyclia check</th><th>Evidence</th><th>Reviewer status</th><th>Reviewer comment</th></tr></thead><tbody>
    ${r.items.map((i) => `<tr data-k="${i.key}"><td>${esc(i.clause)}</td><td>${esc(i.text)}</td><td><span class="pill st-${i.auto}">${esc(i.auto)}</span></td><td class="hint">${esc(i.evidence)}</td>
      <td><select class="rs">${REVIEW_STATUS.map((s) => `<option ${s === i.reviewer_status ? "selected" : ""}>${s}</option>`).join("")}</select></td>
      <td><input class="rc" value="${esc(i.reviewer_comment)}" title="${esc(i.reviewer ? "by " + i.reviewer : "")}"></td></tr>`).join("")}</tbody></table></div>`;
}));
$("#btnReviewSave").addEventListener("click", (e) => guard(e.target, async () => {
  needModel();
  const rows = $$("#reviewOut tr[data-k]");
  if (!rows.length) throw new Error("Open the checklist first.");
  const items = {};
  rows.forEach((tr) => { items[tr.dataset.k] = { status: $(".rs", tr).value, comment: $(".rc", tr).value.trim() }; });
  await api("POST", `/api/models/${S.model.id}/review`, { items });
  S.model = (await api("GET", "/api/models/" + S.model.id)).model;
  toast("Reviewer notes saved in the model.");
}));
$("#btnReviewExport").addEventListener("click", (e) => { try { const b = looseBody(); if (!b.method_ids.length) delete b.method_ids; stdExport(e.target, "/api/export/review", "critical review", "xlsx", b); } catch (err) { toast(err.message, true); } });

/* share */
function renderShareModels() {
  $("#shareModels").innerHTML = S.models.map((m) => `<label><input type="checkbox" value="${m.id}" ${S.model && m.id === S.model.id ? "checked" : ""}> ${esc(m.name)}</label>`).join("") || '<p class="empty">No models yet.</p>';
}
function shareIds() { const ids = $$("#shareModels input:checked").map((i) => Number(i.value)); if (!ids.length) throw new Error("Tick at least one model."); return ids; }
$("#btnBundle").addEventListener("click", (e) => guard(e.target, async () => {
  const ids = shareIds(), b = looseBody();
  if (!b.method_ids.length) throw new Error("Pick the impact categories in step 4 first; the bundle stores their results.");
  let path;
  if (desktop) { path = await desktop.saveFile(`${safeName(S.status.project)} reproducibility bundle.zip`, "zip"); if (!path) return; }
  const { job } = await api("POST", "/api/bundle/export", { ...b, model_ids: ids, path });
  await watchJob(job, { quiet: true, onDone: async (j) => { addExport(j.result); toast(`Bundle saved with ${j.result.models} model(s).`); } });
}));
$("#btnBw").addEventListener("click", (e) => guard(e.target, async () => {
  const r = await exportTo("/api/export/brightway", `${safeName(S.status.project)} for Brightway.xlsx`, "xlsx", { model_ids: shareIds() });
  if (r) toast("Saved, with an import script for bw2io next to it.");
}));
$("#btnOlca").addEventListener("click", (e) => guard(e.target, async () => {
  await exportTo("/api/export/openlca", `${safeName(S.status.project)} for openLCA.zip`, "zip", { model_ids: shareIds() });
}));

/* ---------------- toolbox ---------------- */
function showToolTab(t) {
  S.tt = t;
  $$("#toolTabs button").forEach((b) => b.classList.toggle("on", b.dataset.tt === t));
  $$(".tt").forEach((el) => (el.hidden = el.id !== "tt-" + t));
  const needs = { bg: 1, chem: 1, tpl: 1, teach: 1 };
  if (needs[t] && !(S.status && S.status.project)) { toast("Open a project first (step 1).", true); return; }
  if (t === "bg") { loadBg(); if (!S.bgEdit) newBg(); }
  if (t === "chem") { loadChem(); loadSite(); }
  if (t === "tpl") renderToolTemplates();
  if (t === "code") loadCode();
  if (t === "teach") loadTeach();
}
$$("#toolTabs button").forEach((b) => b.addEventListener("click", () => showToolTab(b.dataset.tt)));

/* validation */
$("#btnValidate").addEventListener("click", (e) => guard(e.target, async () => {
  const { job } = await api("POST", "/api/validation-suite");
  $("#validOut").innerHTML = '<p class="hint">Running...</p>';
  await watchJob(job, { quiet: true, onDone: async (j) => {
    const v = j.result, env = v.environment;
    $("#btnValidReport").disabled = false;
    $("#validOut").innerHTML = `<p><b class="${v.passed === v.total ? "ok" : "danger"}">${v.passed} of ${v.total} cases passed.</b> ${esc(v.verdict)}</p>
      <p class="hint">Cyclia ${esc(env.cyclia)}, Python ${esc(env.python)}, NumPy ${esc(env.numpy)}, SciPy ${esc(env.scipy)}, ${esc(env.platform)}.</p>
      <div class="table-wrap"><table><thead><tr><th>Case</th><th>Area</th><th>Test</th><th class="num">Expected</th><th class="num">Cyclia</th><th class="num">Error</th><th></th></tr></thead><tbody>
      ${v.cases.map((c) => `<tr><td>${c.id}</td><td>${esc(c.area)}</td><td>${esc(c.description)}</td><td class="num">${fmt(c.expected)}</td><td class="num">${fmt(c.cyclia)}</td><td class="num">${c.error.toExponential(1)}</td><td class="${c.passed ? "ok" : "danger"}">${c.passed ? "pass" : "FAIL"}</td></tr>`).join("")}</tbody></table></div>`;
  } });
}));
$("#btnValidReport").addEventListener("click", (e) => guard(e.target, () => exportTo("/api/export/validation", "Cyclia validation report.docx", "docx")));
$("#btnVerify").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.status.project) throw new Error("Open any project first; bundles are checked against the shared library.");
  const { job } = await api("POST", "/api/bundle/verify", { path: $("#bundlePath").value });
  await watchJob(job, { quiet: true, onDone: async (j) => {
    const v = j.result, yes = (b) => (b ? '<span class="ok">yes</span>' : '<span class="danger">no</span>');
    $("#verifyOut").innerHTML = `<p><b class="${v.reproduced ? "ok" : "danger"}">${esc(v.verdict)}</b></p><p class="hint">Bundle made ${esc(v.created)} with Cyclia ${esc(v.environment_then.cyclia)} (${esc(v.environment_then.platform)}); checked with Cyclia ${esc(v.environment_now.cyclia)}.</p>
      <table><thead><tr><th>Database</th><th>In this library</th><th>Identical data</th></tr></thead><tbody>${v.databases.map((d) => `<tr><td>${esc(d.name)}</td><td>${yes(d.in_library)}</td><td>${yes(d.identical)}</td></tr>`).join("")}</tbody></table>
      <table><thead><tr><th>Method</th><th>In this library</th><th>Identical factors</th></tr></thead><tbody>${v.methods.map((d) => `<tr><td>${esc(d.name)}</td><td>${yes(d.in_library)}</td><td>${yes(d.identical)}</td></tr>`).join("")}</tbody></table>
      ${v.results.length ? `<table><thead><tr><th>Model</th><th>Category</th><th class="num">Stored</th><th class="num">Recalculated</th><th class="num">Difference</th></tr></thead><tbody>${v.results.map((r) => `<tr><td>${esc(r.model)}</td><td>${esc(r.category)}</td><td class="num">${fmt(r.stored)}</td><td class="num">${fmt(r.recalculated)}</td><td class="num ${r.identical ? "ok" : "danger"}">${r.relative_difference.toExponential(1)}</td></tr>`).join("")}</tbody></table>` : ""}`;
  } });
}));

/* background scenarios */
async function loadBg() {
  const { scenarios } = await api("GET", "/api/bg-scenarios");
  S.status.bg_scenarios = scenarios;
  $("#bgList").innerHTML = scenarios.length ? scenarios.map((b) => `<li><span class="grow"><b>${esc(b.name)}</b> <span class="tag">${b.kind}</span><br><span class="meta">${b.rules.length} rule(s)${b.description ? ", " + esc(b.description) : ""}${b.kind === "prospective" ? ", base year " + b.base_year : ""}</span><div class="bgtest" id="bgt-${b.id}"></div></span>
    <button class="ghost" data-bgtest="${b.id}" data-kind="${b.kind}">Test</button><button class="ghost" data-bgedit="${b.id}">Edit</button><button class="ghost danger" data-bgdel="${b.id}">Delete</button></li>`).join("")
    : '<li class="empty">No background scenarios yet. Create a prospective one below, or a consequential one with the marginal supplier finder.</li>';
}
function ruleRow(r = {}) {
  if (r.type === "set_exchanges") return `<tr data-swap='${esc(JSON.stringify(r))}'><td>Set exchanges</td><td colspan="4" class="hint">${(r.tech || []).length.toLocaleString("en-US")} technosphere and ${(r.bio || []).length.toLocaleString("en-US")} biosphere exchanges from ${esc(r.source || "a scenario file")}</td><td><button class="ghost danger" data-rmrule>Remove</button></td></tr>`;
  if (r.type === "swap") return `<tr data-swap='${esc(JSON.stringify(r))}'><td>Replace suppliers</td><td colspan="4" class="hint">${esc(r.product)}: ${r.to.length} new supplier(s) in ${(r.activity_ids || []).length || esc(r.activity)} dataset(s) (edit with the marginal supplier finder)</td><td><button class="ghost danger" data-rmrule>Remove</button></td></tr>`;
  const f = r.factor === undefined ? "" : typeof r.factor === "object" ? Object.entries(r.factor).map(([y, v]) => `${y}=${v}`).join(", ") : r.factor;
  return `<tr><td><select class="rt-type"><option value="scale_emission" ${r.type === "scale_input" ? "" : "selected"}>Scale an emission</option><option value="scale_input" ${r.type === "scale_input" ? "selected" : ""}>Scale an input</option></select></td>
    <td><input class="rt-act" value="${esc(r.activity || "")}" placeholder="electricity production, hard coal"></td><td><input class="rt-loc" size="5" value="${esc(r.location || "")}"></td>
    <td><input class="rt-what" value="${esc(r.flow || r.input || "")}" placeholder="carbon dioxide, fossil"></td><td><input class="rt-f" value="${esc(f)}" placeholder="2030=0.8, 2050=0.3"></td><td><button class="ghost danger" data-rmrule>Remove</button></td></tr>`;
}
function newBg() { S.bgEdit = null; $("#bgEditTitle").textContent = "New prospective scenario"; $("#bgName").value = ""; $("#bgDesc").value = ""; $("#bgBase").value = 2020; $("#bgRules").innerHTML = ruleRow(); }
$("#btnNewBg").addEventListener("click", newBg);
$("#btnAddRule").addEventListener("click", () => $("#bgRules").insertAdjacentHTML("beforeend", ruleRow()));
$("#bgRules").addEventListener("click", (e) => { if (e.target.closest("[data-rmrule]")) e.target.closest("tr").remove(); });
function readRules() {
  return $$("#bgRules tr").map((tr, i) => {
    if (tr.dataset.swap) return JSON.parse(tr.dataset.swap);
    const type = $(".rt-type", tr).value, fv = $(".rt-f", tr).value.trim();
    let factor;
    if (fv.includes("=")) { factor = {}; fv.split(/[,;]/).forEach((p) => { const [y, v] = p.split("=").map((x) => x && x.trim()); if (!y || v === undefined || Number.isNaN(Number(v)) || Number.isNaN(Number(y))) throw new Error(`Rule ${i + 1}: write factors as year=factor, e.g. 2030=0.8, 2050=0.3.`); factor[y] = Number(v); }); }
    else { factor = Number(fv); if (fv === "" || Number.isNaN(factor)) throw new Error(`Rule ${i + 1}: enter a factor.`); }
    const r = { type, activity: $(".rt-act", tr).value.trim(), location: $(".rt-loc", tr).value.trim(), factor };
    r[type === "scale_input" ? "input" : "flow"] = $(".rt-what", tr).value.trim();
    return r;
  });
}
$("#btnSaveBg").addEventListener("click", (e) => guard(e.target, async () => {
  const rules = readRules();
  const kind = rules.length && rules.every((r) => r.type === "swap") ? "consequential" : (S.bgEdit && S.bgEdit.kind) || "prospective";
  await api("POST", "/api/bg-scenarios", { id: S.bgEdit ? S.bgEdit.id : undefined, name: $("#bgName").value.trim(), description: $("#bgDesc").value.trim(), base_year: Number($("#bgBase").value) || 2020, kind, rules });
  await loadBg(); renderBgSelect(); S.result = null; newBg(); toast("Background scenario saved. Choose it in step 4.");
}));
$("#bgList").addEventListener("click", (e) => {
  const t = e.target.closest("[data-bgtest]"), ed = e.target.closest("[data-bgedit]"), d = e.target.closest("[data-bgdel]");
  if (t) guard(t, async () => {
    const year = t.dataset.kind === "prospective" ? prompt("Target year to test:", "2050") : null;
    if (t.dataset.kind === "prospective" && !year) return;
    const r = await api("POST", `/api/bg-scenarios/${t.dataset.bgtest}/test`, { year });
    $(`#bgt-${t.dataset.bgtest}`).innerHTML = `<ul class="hint">${r.changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>`;
  });
  if (ed) {
    const b = S.status.bg_scenarios.find((x) => String(x.id) === ed.dataset.bgedit);
    S.bgEdit = b; $("#bgEditTitle").textContent = `Edit: ${b.name}`; $("#bgName").value = b.name; $("#bgDesc").value = b.description || ""; $("#bgBase").value = b.base_year;
    $("#bgRules").innerHTML = b.rules.map(ruleRow).join(""); $("#bgName").scrollIntoView({ block: "center" });
  }
  if (d && confirm("Delete this background scenario?")) guard(d, async () => { await api("DELETE", `/api/bg-scenarios/${d.dataset.bgdel}`); await loadBg(); renderBgSelect(); });
});
$("#btnMarkets").addEventListener("click", (e) => guard(e.target, async () => {
  needModel();
  $("#marketOut").innerHTML = '<p class="hint">Searching the supply chain...</p>';
  const { markets } = await api("GET", `/api/models/${S.model.id}/markets`);
  S.markets = markets;
  $("#marketOut").innerHTML = markets.length ? `<p class="hint">${markets.length} market(s) found in the supply chain of ${esc(S.model.name)}. Tick the ones to change and choose their marginal supplier.</p>
    <table class="market-table"><thead><tr><th></th><th>Market</th><th>Current suppliers</th><th>Marginal supplier</th></tr></thead><tbody>
    ${markets.map((m, i) => `<tr data-i="${i}"><td><input type="checkbox" class="use" aria-label="Change this market"></td><td><b>${esc(m.market.name)}</b> [${esc(m.market.location)}]</td>
      <td class="hint">${m.suppliers.slice(0, 6).map((s) => `${esc(s.name)} [${esc(s.location)}] ${(100 * s.share).toFixed(0)}%`).join("<br>")}</td>
      <td><select class="to">${m.alternatives.map((a) => `<option value="${a.id}">${esc(a.name)} [${esc(a.location)}]</option>`).join("")}</select></td></tr>`).join("")}</tbody></table>
    <div class="row"><input id="consName" class="grow" placeholder="Scenario name, e.g. Marginal electricity: wind"><button class="primary" id="btnSaveCons">Save consequential scenario</button></div>`
    : '<p class="empty">No market with several suppliers was found in the supply chain.</p>';
}));
$("#marketOut").addEventListener("click", (e) => {
  if (e.target.id !== "btnSaveCons") return;
  guard(e.target, async () => {
    const rules = $$("#marketOut tr[data-i]").filter((tr) => $(".use", tr).checked).map((tr) => {
      const m = S.markets[Number(tr.dataset.i)];
      return { type: "swap", activity_ids: [m.market.id], product: m.product_root, to: [{ id: Number($(".to", tr).value), share: 1 }] };
    });
    if (!rules.length) throw new Error("Tick at least one market.");
    await api("POST", "/api/bg-scenarios", { name: $("#consName").value.trim(), kind: "consequential", description: "Marginal suppliers chosen with the market finder", rules });
    await loadBg(); renderBgSelect(); toast("Consequential scenario saved. Choose it in step 4.");
  });
});

/* chemicals and site factors */
let CHEM = null;
async function loadChem() {
  CHEM = await api("GET", "/api/chemicals");
  if (!$("#chemFields").children.length)
    $("#chemFields").innerHTML = Object.entries(CHEM.fields).map(([k, f]) => `<label>${esc(f.label)}${f.required ? " *" : ""} <span class="hint">${esc(f.unit)}</span><input data-chem="${k}" type="number" step="any"></label>`).join("");
  $("#chemList").innerHTML = CHEM.chemicals.length ? CHEM.chemicals.map((c) => `<li><span class="grow"><b>${esc(c.name)}</b>${c.cas ? " (" + esc(c.cas) + ")" : ""}<br><span class="meta">Ecotoxicity, emission to water: ${fmt(((c.result.factors || {}).water || {})["freshwater ecotoxicity"])} CTUe/kg; persistence in water ${fmt((c.result.persistence_days || {}).water)} days</span></span>
    <button class="ghost" data-chemload="${c.id}">Load</button><button class="ghost danger" data-chemdel="${c.id}">Remove</button></li>`).join("") : '<li class="empty">No chemicals yet.</li>';
}
function chemProps() { const p = {}; $$("[data-chem]").forEach((i) => { if (i.value !== "") p[i.dataset.chem] = Number(i.value); }); return p; }
function fillChem(props) { $$("[data-chem]").forEach((i) => (i.value = props[i.dataset.chem] ?? "")); }
$("#btnChemExample").addEventListener("click", () => { if (CHEM) { fillChem(CHEM.example); $("#chemName").value = "Substance X (demo)"; $("#chemCas").value = "000-00-0"; } });
function chemResult(r) {
  const C = ["air", "water", "soil", "sed"], N = { air: "Air", water: "Freshwater", soil: "Soil", sed: "Sediment" };
  const f = r.factors || {};
  return `<p class="hint">Mass balance error ${r.fate.mass_balance_error.toExponential(1)}; bioconcentration factor ${fmt(r.bcf)} L/kg; dissolved fraction in water ${fmt(r.fate.dissolved_fraction_water)}; population in the model region ${fmt(r.population)}.</p>
    <h4>Fate: days the chemical stays in each compartment per kg/day emitted</h4>
    <table><thead><tr><th>Emitted to</th>${C.map((c) => `<th class="num">${N[c]}</th>`).join("")}<th class="num">Total persistence</th></tr></thead><tbody>
    ${["air", "water", "soil"].map((s) => `<tr><td>${N[s]}</td>${C.map((c) => `<td class="num">${fmt(r.fate.FF[s][c])}</td>`).join("")}<td class="num">${fmt(r.fate.persistence_days[s])}</td></tr>`).join("")}</tbody></table>
    <h4>Characterisation factors per kg emitted</h4>
    <table><thead><tr><th>Emitted to</th><th class="num">Freshwater ecotoxicity (CTUe)</th><th class="num">Human toxicity, cancer (CTUh)</th><th class="num">Human toxicity, non-cancer (CTUh)</th><th class="num">Intake fraction</th></tr></thead><tbody>
    ${["air", "water", "soil"].map((s) => `<tr><td>${N[s]}</td><td class="num">${fmt(f[s]["freshwater ecotoxicity"])}</td><td class="num">${fmt(f[s]["human toxicity, cancer"])}</td><td class="num">${fmt(f[s]["human toxicity, non-cancer"])}</td><td class="num">${fmt(f[s].intake_fraction)}</td></tr>`).join("")}</tbody></table>
    <p class="hint">"-" means the effect data needed for that factor were not given.</p>`;
}
$("#btnChemPreview").addEventListener("click", (e) => guard(e.target, async () => { $("#chemOut").innerHTML = chemResult(await api("POST", "/api/chemicals/preview", { props: chemProps() })); }));
$("#btnChemSave").addEventListener("click", (e) => guard(e.target, async () => {
  const r = await api("POST", "/api/chemicals", { name: $("#chemName").value.trim(), cas: $("#chemCas").value.trim(), props: chemProps() });
  $("#chemOut").innerHTML = chemResult({ ...r, bcf: null, population: null });
  await loadChem(); await refreshStatus(); toast("Chemical saved: its factors are in the method 'Cyclia screening toxicity (own chemicals)' and it can be added as an emission in step 3.");
}));
$("#chemList").addEventListener("click", (e) => {
  const l = e.target.closest("[data-chemload]"), d = e.target.closest("[data-chemdel]");
  if (l) { const c = CHEM.chemicals.find((x) => String(x.id) === l.dataset.chemload); fillChem(c.props); $("#chemName").value = c.name; $("#chemCas").value = c.cas; }
  if (d && confirm("Remove this chemical and its screening factors? Its elementary flows stay in the library.")) guard(d, async () => { await api("DELETE", `/api/chemicals/${d.dataset.chemdel}`); await loadChem(); });
});
let SITE_FLOW = null;
async function loadSite() {
  const { factors } = await api("GET", "/api/site-cfs");
  $("#siteList").innerHTML = factors.length ? factors.map((f) => `<li><span class="grow"><b>${esc(f.flow_name)}</b> in ${esc(f.category)} (${esc(f.family)}): <b>${fmt(f.value)}</b><br><span class="meta">${esc(f.note || "")}</span></span><button class="ghost danger" data-sitedel="${f.id}">Remove</button></li>`).join("") : '<li class="empty">No site-specific factors.</li>';
  $("#siteMethod").innerHTML = S.methods.map((m) => `<option value="${m.id}">${esc(m.family)}: ${esc(m.category)}</option>`).join("");
}
$("#siteList").addEventListener("click", (e) => { const d = e.target.closest("[data-sitedel]"); if (d) guard(d, async () => { await api("DELETE", `/api/site-cfs/${d.dataset.sitedel}`); S.result = null; await loadSite(); }); });
let siteT;
$("#siteFlowQ").addEventListener("input", () => {
  clearTimeout(siteT);
  siteT = setTimeout(async () => {
    const q = $("#siteFlowQ").value.trim();
    if (q.length < 2) { $("#siteFlowRes").innerHTML = ""; return; }
    const { results } = await api("GET", "/api/flows?q=" + encodeURIComponent(q));
    $("#siteFlowRes").innerHTML = results.slice(0, 12).map((f) => `<li><button data-siteflow="${esc(f.uuid)}" data-label="${esc(f.name + " (" + f.compartment + (f.subcompartment ? "/" + f.subcompartment : "") + ")")}"><span class="rname">${esc(f.name)}</span><span class="rmeta">${esc(f.compartment)}${f.subcompartment ? " / " + esc(f.subcompartment) : ""}</span></button></li>`).join("");
  }, 250);
});
$("#siteFlowRes").addEventListener("click", (e) => { const b = e.target.closest("[data-siteflow]"); if (!b) return; SITE_FLOW = b.dataset.siteflow; $("#siteFlowQ").value = b.dataset.label; $("#siteFlowRes").innerHTML = ""; });
$("#btnSiteSave").addEventListener("click", (e) => guard(e.target, async () => {
  const m = S.methods.find((x) => String(x.id) === $("#siteMethod").value);
  if (!m) throw new Error("Choose the impact category.");
  if (!SITE_FLOW) throw new Error("Search and choose the elementary flow.");
  await api("POST", "/api/site-cfs", { family: m.family, category: m.category, indicator: m.indicator, flow_uuid: SITE_FLOW, value: $("#siteValue").value, note: $("#siteNote").value.trim() });
  S.result = null; SITE_FLOW = null; $("#siteFlowQ").value = ""; $("#siteValue").value = ""; $("#siteNote").value = ""; await loadSite(); toast("Site-specific factor saved.");
}));

/* templates (toolbox) */
async function renderToolTemplates() {
  const { templates } = await api("GET", "/api/model-templates");
  $("#tplList").innerHTML = tplCards(templates, { remove: true });
}
$("#tplList").addEventListener("click", (e) => {
  const u = e.target.closest("[data-tpluse]"), r = e.target.closest("[data-tplrm]");
  if (u) useTemplate(u, $("#tplList"));
  if (r && confirm("Remove this template from the library?")) guard(r, async () => { await api("DELETE", `/api/model-templates/${r.dataset.tplrm}`); await renderToolTemplates(); });
});

/* python, R, brightway import */
async function loadCode() {
  const info = await api("GET", "/api/api-info");
  $("#apiInfo").textContent = info.url ? `The engine runs at ${info.url}; the connection details are in ${info.file} while Cyclia is open.` : "";
  $("#codePy").textContent = `# Python (after "Save the Python and R clients"; needs only the standard library)
from cyclia_client import Cyclia
cy = Cyclia()
cy.open_project("${S.status.project || "Cyclia feature demo"}")
model = [m for m in cy.models() if m["name"] == "${(S.model && S.model.name) || "Concrete wall (demo)"}"][0]
gwp = [m["id"] for m in cy.methods() if m["category"] == "climate change"]
for t in (0.18, 0.20, 0.25):
    cy.set_parameter("thickness", t, model_id=model["id"])
    print(t, cy.calculate(model["id"], gwp)["results"][0]["total"])`;
  $("#codeR").textContent = `# R (install.packages(c("httr", "jsonlite")) once)
source("cyclia.R")
cy <- cyclia_connect()
cyclia_open_project(cy, "${S.status.project || "Cyclia feature demo"}")
m <- cyclia_models(cy)
meth <- cyclia_methods(cy)
res <- cyclia_calculate(cy, m$id[1], meth$id[meth$category == "climate change"])
cyclia_results_table(res)`;
}
$("#btnClients").addEventListener("click", (e) => guard(e.target, async () => { const { files } = await api("POST", "/api/export/clients", {}); files.forEach(addExport); }));
$("#btnBwImport").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.status.project) throw new Error("Open a project first.");
  const r = await api("POST", "/api/import/brightway", { path: $("#bwPath").value });
  $("#bwOut").innerHTML = `<p>${r.models.length} model(s) created.</p>${r.problems.length ? `<div class="problems"><b>Lines that could not be linked:</b><ul>${r.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>` : ""}`;
  await refreshModels(r.models[0]);
}));

/* teaching */
async function loadTeach() {
  const { exercises, demo_ready } = await api("GET", "/api/teaching/exercises");
  let key = {};
  if ($("#teacherMode").checked && demo_ready) (await api("POST", "/api/teaching/key", {})).key.forEach((k) => (key[k.id] = k));
  $("#teachOut").innerHTML = (demo_ready ? "" : '<p class="danger">The exercises use the demo database. Load the demo in step 1 first.</p>') + exercises.map((x) => `<div class="exercise" data-ex="${x.id}">
    <div class="row"><b class="grow">${esc(x.title)}</b><span class="tag">${esc(x.level)}</span></div>
    <p class="hint">${esc(x.goal)}</p><p>${esc(x.task)}</p>
    ${x.options ? `<div class="radios">${x.options.map((o, i) => `<label><input type="radio" name="opt-${x.id}" value="${i}"> ${esc(o)}</label>`).join("")}</div>`
      : `<div class="row"><input class="ans" type="number" step="any" placeholder="Your answer"><span class="hint">${esc(x.unit)}</span></div>`}
    <div class="row"><button data-check="${x.id}">Check</button><details><summary class="hint">Hint</summary><p class="hint">${esc(x.hint || "")}</p></details><span class="res"></span></div>
    ${key[x.id] ? `<p class="key"><b>Answer:</b> ${esc(key[x.id].answer)} ${esc(key[x.id].unit)}. ${esc(key[x.id].how)}</p>` : ""}</div>`).join("");
}
$("#teacherMode").addEventListener("change", () => guard(null, loadTeach));
$("#teachOut").addEventListener("click", (e) => {
  const b = e.target.closest("[data-check]");
  if (!b) return;
  guard(b, async () => {
    const box = b.closest(".exercise");
    const radio = $("input[type=radio]:checked", box), inp = $(".ans", box);
    const answer = radio ? radio.value : inp ? inp.value : "";
    if (answer === "") throw new Error("Give an answer first.");
    const r = await api("POST", "/api/teaching/check", { id: b.dataset.check, answer });
    $(".res", box).innerHTML = r.correct ? `<span class="ok">Correct.</span> ${esc(r.explanation || "")}` : `<span class="${r.close ? "warn" : "danger"}">${esc(r.message || r.explanation)}</span>`;
  });
});
$("#btnAnswerKey").addEventListener("click", (e) => guard(e.target, () => exportTo("/api/export/answer-key", "Cyclia exercises answer key.docx", "docx")));

/* ---------------- author, feature tour ---------------- */
$("#btnAuthor").addEventListener("click", (e) => guard(e.target, async () => { await api("POST", "/api/settings", { author: $("#authorName").value.trim() }); S.status.settings = { author: $("#authorName").value.trim() }; toast("Name saved."); }));
const TOUR = [
  ["Load the full demo project", "setup", null, "Illustrative database, methods and seven models."],
  ["Start a model from a template (building, packaging, food, energy)", "scope", () => $("#btnTemplates").click()],
  ["Parameters with distributions and scenarios", "scope", () => $("#paramRows").scrollIntoView({ block: "center" })],
  ["Versions, differences between versions, and model lock", "scope", () => $("#versionList").scrollIntoView({ block: "center" })],
  ["Inventory from a paper or table (PDF, Word, Excel, pasted text)", "inventory", () => { $("#litPanel").hidden = false; }],
  ["Emissions from an external model (fate, leaching, field emissions)", "inventory", () => { $("#extPanel").hidden = false; }],
  ["Comments for supervisors and co-authors", "inventory", () => $("#commentsBlock").scrollIntoView({ block: "center" })],
  ["Prospective and consequential background scenarios", "impact", () => $("#bgSel").focus()],
  ["Map of impacts by location", "results", () => showTab("map"), "Calculate first."],
  ["Parameter sweep, optimisation and Pareto trade-offs", "results", () => showTab("explore"), "Calculate first."],
  ["PEF most relevant categories, stages, processes and flows", "results", () => showTab("pef"), "Use a normalisation set."],
  ["Toxicity coverage and site-specific factors", "results", () => showTab("lci")],
  ["Supply chain tree, Sobol indices, comparative Monte Carlo", "results", () => showTab("tree")],
  ["EPD (EN 15804+A2) with verification checklist", "report", null],
  ["ISO 14067 carbon footprint report and GHG Protocol workbook", "report", null],
  ["Critical review checklist (ISO 14044)", "report", () => $("#btnReviewLoad").click()],
  ["Reproducibility bundle, Brightway and openLCA export", "report", () => $("#btnBundle").scrollIntoView({ block: "center" })],
  ["Validation suite with exact reference solutions", "tools", () => showToolTab("valid")],
  ["Background scenario editor and marginal supplier finder", "tools", () => showToolTab("bg")],
  ["Screening toxicity factors for your own chemicals", "tools", () => showToolTab("chem")],
  ["Python and R clients, Brightway import", "tools", () => showToolTab("code")],
  ["Teaching mode with exercises and answer key", "tools", () => showToolTab("teach")],
];
function renderTour() {
  $("#tourList").innerHTML = TOUR.map(([t, step, , note], i) => `<li><button class="ghost" data-tour="${i}">${esc(t)}</button>${note ? `<span class="hint"> ${esc(note)}</span>` : ""}</li>`).join("");
}
$("#tourList").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tour]");
  if (!b) return;
  const [, step, fn] = TOUR[Number(b.dataset.tour)];
  $("#help").hidden = true;
  if (step === "results" && !S.result) { go("impact"); toast("Calculate first; then the result tabs open.", true); return; }
  go(step);
  if (fn) setTimeout(fn, 50);
});


/* ---------------- official reference data (step 1) ---------------- */
async function loadEf31() {
  if (!S.status || !S.status.project) return;
  const r = await api("GET", "/api/ef31");
  $("#ef31Source").textContent = r.source;
  $("#ef31Family").innerHTML = r.families.length ? r.families.map((f) => `<option>${esc(f)}</option>`).join("") : '<option value="">No EF method imported yet</option>';
}
$("#ef31Family").closest("details").addEventListener("toggle", (e) => { if (e.target.open) guard(null, loadEf31); });
$("#btnEf31").addEventListener("click", (e) => guard(e.target, async () => {
  const family = $("#ef31Family").value;
  if (!family) throw new Error("Import the EF 3.1 method first (ecoinvent LCIA file, the EF package for openLCA, or a CSV).");
  const r = await api("POST", "/api/ef31/install", { family });
  $("#ef31Out").innerHTML = `<p class="ok">${r.matched.length} of 16 categories received factors (set "${esc(r.set)}").${r.missing.length ? ` <span class="warn">Not found in this method: ${r.missing.map(esc).join(", ")}.</span>` : ""}</p>
    <table><thead><tr><th>EF 3.1 category</th><th>Matched category</th><th class="num">Normalisation per person</th><th class="num">Weight</th></tr></thead><tbody>
    ${r.matched.map((m) => `<tr><td>${esc(m.ef)}</td><td>${esc(m.category)}${m.indicator !== m.category ? `<br><span class="hint">${esc(m.indicator)}</span>` : ""}</td><td class="num">${fmt(m.normalisation)}</td><td class="num">${m.weighting_percent} %</td></tr>`).join("")}</tbody></table>`;
  await refreshStatus(); toast("EF 3.1 normalisation and weighting added. Choose the set in step 4.");
}));

const CAS_CATS = ["freshwater ecotoxicity", "human toxicity, cancer", "human toxicity, non-cancer"];
let CASPREV = null;
function casGuessCat(h) { h = h.toLowerCase(); if (h.includes("eco")) return CAS_CATS[0]; if (h.includes("non") && (h.includes("canc") || h.includes("carc"))) return CAS_CATS[2]; if (h.includes("canc") || h.includes("carc")) return CAS_CATS[1]; return ""; }
function renderCasMap() {
  const p = CASPREV, opt = (sel) => `<option value="">(none)</option>` + p.columns.map((c) => `<option value="${c.index}" ${c.index === sel ? "selected" : ""}>${esc(c.header || "column " + (c.index + 1))}</option>`).join("");
  $("#casMap").innerHTML = `<div class="form-grid">
      ${p.sheets.length ? `<label>Sheet<select id="casSheet">${p.sheets.map((x) => `<option ${x === p.sheet ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label>` : ""}
      <label>Header row<input id="casHeader" type="number" min="1" value="${p.header_row}"></label>
      <label>CAS number column<select id="casCol">${opt(p.cas_col)}</select></label><label>Substance name column<select id="casName">${opt(p.name_col)}</select></label>
      <label class="wide">Method name in the library<input id="casFamily" value="USEtox 2.x (official factors)"></label></div>
    <p class="hint">Tick the columns that hold factors and say what each one is. Compartments were guessed from the column titles.</p>
    <div class="table-wrap"><table class="cas-table"><thead><tr><th></th><th>Column</th><th>Example</th><th>Impact category</th><th>Unit</th><th>Compartment</th><th>Subcompartment</th></tr></thead><tbody>
    ${p.columns.filter((c) => c.numeric && c.index !== p.cas_col).map((c) => { const cat = casGuessCat(c.header); return `<tr data-i="${c.index}"><td><input type="checkbox" class="use" ${cat && c.compartment ? "checked" : ""}></td><td>${esc(c.header)}</td><td class="hint">${c.sample.map(esc).join(", ")}</td>
      <td><input class="cat" list="casCats" value="${esc(cat)}"></td><td><input class="unit" size="6" value="${cat ? (cat.startsWith("fresh") ? "CTUe" : "CTUh") : ""}"></td>
      <td><select class="comp">${["", "air", "water", "soil"].map((x) => `<option ${x === c.compartment ? "selected" : ""}>${x}</option>`).join("")}</select></td><td><input class="sub" value="${esc(c.subcompartment)}"></td></tr>`; }).join("")}</tbody></table></div>
    <datalist id="casCats">${CAS_CATS.map((x) => `<option value="${x}">`).join("")}</datalist>
    <div class="row"><button class="primary" id="btnCasImport">Import factors</button></div>`;
}
async function casRead(btn, sheet) {
  return guard(btn, async () => {
    CASPREV = await api("POST", "/api/cf-table/preview", { path: $("#casPath").value, sheet });
    renderCasMap();
  });
}
$("#btnCasRead").addEventListener("click", (e) => casRead(e.target));
$("#casMap").addEventListener("change", (e) => { if (e.target.id === "casSheet") casRead(null, e.target.value); });
$("#casMap").addEventListener("click", (e) => {
  if (e.target.id !== "btnCasImport") return;
  const columns = $$("#casMap tr[data-i]").filter((tr) => $(".use", tr).checked).map((tr) => ({ index: Number(tr.dataset.i), category: $(".cat", tr).value.trim(),
    indicator: $(".cat", tr).value.trim(), unit: $(".unit", tr).value.trim(), compartment: $(".comp", tr).value, subcompartment: $(".sub", tr).value.trim() }));
  const mapping = { sheet: $("#casSheet") ? $("#casSheet").value : null, header_row: Number($("#casHeader").value) || 1,
    cas_col: $("#casCol").value === "" ? null : Number($("#casCol").value), name_col: $("#casName").value === "" ? null : Number($("#casName").value),
    family: $("#casFamily").value.trim(), columns };
  runImport(e.target, "/api/import/cf-table", { path: $("#casPath").value, mapping });
});

/* scenario files (toolbox) */
$("#btnSdf").addEventListener("click", (e) => guard(e.target, async () => {
  const { job } = await api("POST", "/api/import/scenario-file", { path: $("#sdfPath").value, prefix: $("#sdfPrefix").value.trim() });
  await watchJob(job, { quiet: true, onDone: async (j) => {
    const r = j.result;
    $("#sdfOut").innerHTML = `<p class="ok">${r.scenarios} background scenario(s) created from ${r.rows.toLocaleString("en-US")} exchanges.</p>${r.warnings.map((w) => `<p class="warn">${esc(w)}</p>`).join("")}`;
    await loadBg(); renderBgSelect(); S.result = null;
  } });
}));
TOUR.splice(8, 0, ["Official EF 3.1 normalisation and weighting; USEtox factors by CAS number", "setup", () => $("#btnEf31").closest("details").setAttribute("open", "")],
  ["premise and Activity Browser scenario files", "tools", () => showToolTab("bg")]);


/* ---------------- automatic benchmark against ecoinvent ---------------- */
$("#eiBenchBox").addEventListener("toggle", (e) => {
  if (!e.target.open) return;
  const fams = [...new Set(S.methods.map((m) => m.family))];
  const pref = fams.find((f) => /ef v?3\.1/i.test(f) && !/no lt/i.test(f)) || fams[0];
  $("#ebFamily").innerHTML = '<option value="">Detect from the file (all methods in it)</option>' + fams.map((f) => `<option>${esc(f)}</option>`).join("");
  if (pref && /ef v?3\.1/i.test(pref)) $("#ebFamily").value = pref;
});
$("#btnEiBench").addEventListener("click", (e) => guard(e.target, async () => {
  if (!S.status.project) throw new Error("Open a project first.");
  if (!$("#ebPath").value.trim()) throw new Error("Choose the cumulative LCIA results file first.");
  const { job } = await api("POST", "/api/benchmark-ecoinvent", { path: $("#ebPath").value, family: $("#ebFamily").value, sample: Number($("#ebSample").value) });
  $("#ebOut").innerHTML = '<p class="hint">Running; progress is shown at the bottom left.</p>';
  const fin = await watchJob(job, { quiet: true, onDone: async (j) => renderBench(j.result, $("#ebOut")) });
  if (fin && fin.status === "error") $("#ebOut").innerHTML = `<p class="danger">${esc(fin.error)}</p>`;
}));
$("#btnEiBenchSave").addEventListener("click", (e) => guard(e.target, () => exportTo("/api/export/benchmark", "Cyclia benchmark against ecoinvent.xlsx", "xlsx")));

function renderBench(r, el) {
  if (r && r.error) { el.innerHTML = `<p class="danger">The database is installed, but the automatic validation could not run: ${esc(r.error)}</p><p class="hint">You can run it later with "Validate only", or with a downloaded results file under "Validate against ecoinvent".</p>`; return; }
  const sm = r.summary, pc = (x) => (x == null ? "-" : x.toFixed(x < 1 ? 3 : 1) + " %");
    $$("#btnEiBenchSave, [data-benchsave]").forEach((x) => (x.disabled = false));
    const good = sm.n && sm.within_0_1 >= 95;
    el.innerHTML = `<p><b class="${good ? "ok" : sm.within_1 >= 95 ? "warn" : "danger"}">${esc(r.verdict)}</b></p>
      <p class="hint">${r.datasets} datasets compared (of ${r.datasets_matched.toLocaleString("en-US")} found in your library; ${r.datasets_in_file.toLocaleString("en-US")} in the file), ${r.categories} categories, ${sm.n || 0} results. ${r.unlinked_inputs ? r.unlinked_inputs + " inputs in the library have no supplier." : ""}</p>
      <h4>By category</h4><div class="table-wrap"><table><thead><tr><th>Category</th><th class="num">Median deviation</th><th class="num">Largest</th><th class="num">Within 0.1 %</th><th>What to check</th></tr></thead><tbody>
      ${r.by_category.map((c) => `<tr><td>${esc(c.category)}<br><span class="hint">${esc(c.indicator)}</span></td><td class="num">${pc(c.median)}</td><td class="num">${pc(c.max)}</td><td class="num">${c.within_0_1 == null ? "-" : c.within_0_1.toFixed(0) + " %"}</td><td class="hint">${esc(c.hint)}</td></tr>`).join("")}</tbody></table></div>
      <h4>By group of datasets</h4><table><thead><tr><th>Group</th><th class="num">Results</th><th class="num">Median deviation</th><th class="num">Within 0.1 %</th></tr></thead><tbody>
      ${r.by_group.filter((g) => g.n).map((g) => `<tr><td>${esc(g.group)}</td><td class="num">${g.n}</td><td class="num">${pc(g.median)}</td><td class="num">${g.within_0_1.toFixed(0)} %</td></tr>`).join("")}</tbody></table>
      <h4>Largest deviations</h4><div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Category</th><th class="num">ecoinvent</th><th class="num">Cyclia</th><th class="num">Deviation</th><th></th></tr></thead><tbody>
      ${r.worst.slice(0, 15).map((x) => `<tr><td>${esc(x.activity)} [${esc(x.location)}]</td><td>${esc(x.category)}</td><td class="num">${fmt(x.reference)}</td><td class="num">${fmt(x.cyclia)}</td><td class="num">${x.deviation_percent == null ? "-" : x.deviation_percent.toFixed(3) + " %"}</td><td class="hint">${esc(x.note)}</td></tr>`).join("")}</tbody></table></div>
      ${(r.diagnosis || []).length ? `<h4>Why some results differ</h4><p class="hint">For the datasets with the largest deviation: elementary flows that have no factor in Cyclia although the method has a factor for a flow of the same name. "Explained" compares these missing factors with the gap to ecoinvent.</p>
      ${r.diagnosis.slice(0, 8).map((d) => `<details><summary><b>${esc(d.category)}</b>: ${esc(d.dataset)} [${esc(d.location)}], gap ${fmt(d.gap)}, ${d.explained_percent == null ? "-" : d.explained_percent.toFixed(0) + " % explained"}</summary>
        ${d.flows.length ? `<table><thead><tr><th>Flow without factor</th><th>Its compartment</th><th class="num">Amount</th><th>The method has</th><th class="num">Missing</th></tr></thead><tbody>${d.flows.slice(0, 6).map((f) => `<tr><td>${esc(f.flow)}</td><td>${esc(f.flow_context)}</td><td class="num">${fmt(f.amount)} ${esc(f.unit)}</td><td class="hint">${esc(f.method_has)}</td><td class="num">${fmt(f.missing_contribution)}</td></tr>`).join("")}</tbody></table>` : '<p class="hint">No unmatched factor with the same flow name: the cause is elsewhere (flow names that differ, or the database).</p>'}</details>`).join("")}` : ""}
      ${(r.factor_finder || []).length ? `<h4>Factor finder</h4><p class="hint">Looking at all compared datasets together: which flows, given a different factor, would explain the deviations. "ecoinvent appears to use" is the factor that fits ecoinvent's results best.</p>
      ${r.factor_finder.map((d) => `<details open><summary><b>${esc(d.category)}</b>: ${d.deviating} of ${d.results} results deviate, ${d.explained_percent.toFixed(0)} % of the deviation explained</summary>
        <div class="table-wrap"><table><thead><tr><th>Flow</th><th>Compartment</th><th class="num">Cyclia factor</th><th class="num">ecoinvent appears to use</th><th>Factors in the method file</th></tr></thead><tbody>${d.flows.map((f) => `<tr><td>${esc(f.flow)}</td><td>${esc(f.flow_context)}</td><td class="num">${fmt(f.cyclia_factor)}</td><td class="num">${fmt(f.implied_factor)}</td><td class="hint">${esc(f.method_has)}</td></tr>`).join("")}</tbody></table></div></details>`).join("")}` : ""}
      <p class="hint">Methods compared: ${r.families.map(esc).join(", ")}. Save the Excel report and send it if anything needs explaining; it holds every comparison.</p>
      <div class="row"><button data-benchsave>Save the Excel report</button></div>`;
}
document.addEventListener("click", (e) => { const b = e.target.closest("[data-benchsave]"); if (b) guard(b, () => exportTo("/api/export/benchmark", "Cyclia benchmark against ecoinvent.xlsx", "xlsx")); });
