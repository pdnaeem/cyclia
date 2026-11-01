/* Step 1 layout: the open project at the top, then tabs for projects, databases, methods and checks.
   Replaces the list renderers of app.js with clearer cards; the element ids and data attributes stay the same,
   so all existing handlers keep working. */
"use strict";

const SETUP_TABS = ["projects", "databases", "methods", "validate"];
let setupTab = ls.get("cyclia.setupTab", "projects");
let setupTabChosen = false;
let lastProject;

function showSetupTab(name, chosen = false) {
  if (!SETUP_TABS.includes(name)) name = "projects";
  setupTab = name;
  if (chosen) { setupTabChosen = true; ls.set("cyclia.setupTab", name); }
  $$("#setupTabs [data-setup-tab]").forEach((b) => b.classList.toggle("on", b.dataset.setupTab === name));
  $$("#view-setup [data-setup]").forEach((el) => (el.hidden = el.dataset.setup !== name));
}
window.showSetupTab = showSetupTab;
$("#setupTabs").addEventListener("click", (e) => {
  const b = e.target.closest("[data-setup-tab]");
  if (b) showSetupTab(b.dataset.setupTab, true);
});

/* the most useful tab when step 1 opens: what is still missing, otherwise the last one used */
function autoSetupTab() {
  const st = S.status || {};
  if (!st.project) return showSetupTab("projects");
  if (!(st.databases || []).length) { showSetupTab("databases"); $("#dbConnectors").hidden = false; return; }
  if (!st.n_methods) { showSetupTab("methods"); $("#methodConnectors").hidden = false; return; }
  showSetupTab(setupTabChosen ? setupTab : ls.get("cyclia.setupTab", "projects"));
}

/* "Add a database" / "Add methods" open the list of sources */
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-addtoggle]");
  if (!t) return;
  const p = document.getElementById(t.dataset.addtoggle);
  if (!t.dataset.label) t.dataset.label = t.textContent;
  p.hidden = !p.hidden;
  t.textContent = p.hidden ? t.dataset.label : "Close";
  if (!p.hidden) p.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
$("#btnNewProjectToggle").addEventListener("click", () => {
  $("#newProjectRow").hidden = false;
  $("#newProjectName").focus();
});

const ago = (t) => {
  if (!t) return "";
  const s = (Date.now() / 1000 - t);
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.round(s / 86400)} days ago`;
  return new Date(t * 1000).toLocaleDateString();
};
const initialsOf = (n) => (n.match(/\b\w/g) || ["?"]).slice(0, 2).join("").toUpperCase();

/* ---------------- the open project ---------------- */
function renderCurrentProject(projects) {
  const st = S.status || {};
  const box = $("#curProject");
  if (!st.project) {
    box.className = "cur-project coach-anchor empty-state";
    box.innerHTML = `<div class="cp-icon">+</div><div class="grow"><b>No project is open</b>
      <span class="hint">Create a new project below, or open one of yours. A project holds the models of one study.</span></div>`;
    return;
  }
  const me = (projects || []).find((p) => p.name === st.project) || {};
  const dbs = (st.databases || []).map((d) => d.name);
  box.className = "cur-project coach-anchor";
  box.innerHTML = `<div class="cp-icon">${esc(initialsOf(st.project))}</div>
    <div class="grow"><span class="cp-label"><i class="dot"></i>Open project</span><b class="cp-name">${esc(st.project)}</b>
      <span class="hint">${me.models != null ? `${me.models} model${me.models === 1 ? "" : "s"}` : ""}${me.modified ? ` · saved ${ago(me.modified)}` : ""}${dbs.length ? ` · library: ${dbs.length} database${dbs.length === 1 ? "" : "s"}, ${st.n_methods || 0} impact categories` : " · no database yet"}</span></div>
    <button data-cp="switch">Switch project</button>
    <button class="primary" data-cp="next">${S.models.length ? "Continue" : "Define the study"} &rarr;</button>`;
}
$("#curProject").addEventListener("click", (e) => {
  const b = e.target.closest("[data-cp]");
  if (!b) return;
  if (b.dataset.cp === "next") go(S.models.length ? (S.model && S.model.inputs.length ? "inventory" : "scope") : "scope");
  if (b.dataset.cp === "switch") { showSetupTab("projects", true); $("#projectList").scrollIntoView({ behavior: "smooth", block: "nearest" }); }
  if (b.dataset.cp === "new") { showSetupTab("projects", true); $("#newProjectRow").hidden = false; $("#newProjectName").focus(); }
});

/* ---------------- project cards ---------------- */
renderProjects = async function () {
  const { projects, current } = await api("GET", "/api/projects");
  projects.sort((a, b) => (b.name === current) - (a.name === current) || (b.modified || 0) - (a.modified || 0));
  $("#projectList").innerHTML = projects.length ? projects.map((p) => {
    const on = p.name === current;
    return `<li class="pcard ${on ? "on" : ""}" ${on ? "" : `data-open="${esc(p.name)}" tabindex="0" role="button" aria-label="Open ${esc(p.name)}"`}>
      <div class="pc-icon">${esc(initialsOf(p.name))}</div>
      <div class="grow"><b>${esc(p.name)}</b><span class="hint">${p.models != null ? `${p.models} model${p.models === 1 ? "" : "s"} · ` : ""}${ago(p.modified)}</span></div>
      ${on ? '<span class="pill-open"><i class="dot"></i>Open</span>' : '<span class="pc-open">Open</span>'}
      <button class="icon-btn" data-del="${esc(p.name)}" title="Delete this project" aria-label="Delete ${esc(p.name)}">
        <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M5 4.5l.6 8.5h4.8l.6-8.5"/></svg></button></li>`;
  }).join("") : '<li class="empty">No projects yet. Press "New project" to start.</li>';
  $("#tcProjects").textContent = projects.length || "";
  if (!$("#newProjectName").value) $("#newProjectRow").hidden = !!current;
  renderCurrentProject(projects);
  if (current !== lastProject) {  // a project was just created or opened: show what is still missing
    lastProject = current;
    if (S.step === "setup") autoSetupTab();
  }
};
$("#projectList").addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-open]")) { e.preventDefault(); e.target.click(); }
});

/* ---------------- databases ---------------- */
const dbKind = (d) => /ecoinvent/i.test(d.name + d.source) ? "ei" : /tutorial|demo|illustrative/i.test(d.name) ? "learn" : "db";
renderDbs = function () {
  const dbs = S.status.databases;
  $("#dbList").innerHTML = dbs.length ? dbs.map((d) => `
    <li class="item ${dbKind(d)}"><div class="it-icon">${dbKind(d) === "ei" ? "ei" : dbKind(d) === "learn" ? "T" : "DB"}</div>
      <div class="grow"><b>${esc(d.name)}</b>
        <div class="chips">${d.version ? `<span class="chip">v${esc(d.version)}</span>` : ""}${d.system_model ? `<span class="chip">${esc(d.system_model)}</span>` : ""}
          <span class="chip">${d.n_activities.toLocaleString("en-US")} datasets</span>${d.has_uncertainty ? '<span class="chip">uncertainty</span>' : ""}
          ${dbKind(d) === "learn" ? '<span class="chip warn">for learning only</span>' : ""}${d.n_unlinked ? `<span class="chip warn">${d.n_unlinked} without supplier</span>` : ""}</div></div>
      ${d.n_unlinked ? `<button data-link="${d.id}">Link suppliers</button>` : ""}
      <button class="ghost" data-validate="${d.id}">Check</button>
      <button class="icon-btn" data-deldb="${d.id}" title="Remove from the library" aria-label="Remove ${esc(d.name)}">
        <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M5 4.5l.6 8.5h4.8l.6-8.5"/></svg></button></li>`).join("")
    : '<li class="empty">No database yet. Press "Add a database". No licence? Choose the tutorial database to learn.</li>';
  $("#searchDb").innerHTML = '<option value="">All databases</option>' + dbs.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
  $("#tcDbs").textContent = dbs.length || "";
  if (!dbs.length) $("#dbConnectors").hidden = false;
};

/* ---------------- methods ---------------- */
renderMethodFamilies = function () {
  const fams = {};
  S.methods.forEach((m) => (fams[m.family] = fams[m.family] || []).push(m));
  const names = Object.keys(fams);
  $("#methodFamilies").innerHTML = names.length ? names.map((f) => {
    const sets = [...new Set(fams[f].flatMap((m) => m.nw_sets))];
    const matched = fams[f].reduce((a, m) => a + m.n_cfs, 0);
    const builtin = /built-in/i.test(f), learn = /tutorial|demo|illustrative/i.test(f);
    return `<li class="item"><div class="it-icon m">${builtin ? "C" : learn ? "T" : "M"}</div>
      <div class="grow"><b>${esc(f)}</b>
        <div class="chips"><span class="chip">${fams[f].length} categor${fams[f].length === 1 ? "y" : "ies"}</span>
          <span class="chip ${matched ? "" : "warn"}">${matched ? matched.toLocaleString("en-US") + " factors matched" : "no factors matched"}</span>
          ${sets.length ? `<span class="chip">normalisation: ${sets.map(esc).join(", ")}</span>` : ""}${builtin ? '<span class="chip">built in</span>' : ""}${learn ? '<span class="chip warn">for learning only</span>' : ""}</div></div>
      ${builtin ? "" : `<button class="icon-btn" data-delfam="${esc(f)}" title="Remove from the library" aria-label="Remove ${esc(f)}">
        <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M5 4.5l.6 8.5h4.8l.6-8.5"/></svg></button>`}</li>`;
  }).join("") : '<li class="empty">No impact methods yet. Press "Add methods".</li>';
  $("#tcMethods").textContent = names.length || "";
  if (!names.length) $("#methodConnectors").hidden = false;
};

/* opening step 1 picks the useful tab; "Show me" switches tabs and opens panels when needed */
const _go = go;
go = function (step) {
  _go(step);
  if (step === "setup") autoSetupTab();
};
const _spot = spotlight;
spotlight = function (sel) {
  const el = $(`#view-${S.step} ${sel}`) || $(sel);
  if (el) {
    const sec = el.closest("[data-setup]");
    if (sec && sec.hidden) showSetupTab(sec.dataset.setup);
    for (let p = el.closest("[hidden]"); p && p.id !== "view-setup"; p = p.parentElement.closest("[hidden]")) {
      if (p.matches(".add-panel, #newProjectRow")) p.hidden = false; else break;
    }
  }
  _spot(sel);
};
autoSetupTab();
