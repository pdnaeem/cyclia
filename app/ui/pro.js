/* Cyclia 1.3.2: provenance and prices per line, Circular Footprint Formula, correlated parameters, life cycle
   costing and water in the Summary, report centre, executive summary and figures, database versions, project
   overview. Loaded after app.js, features.js and setup.js; uses their helpers. */
(function () {
  "use strict";
  const money = (v, cur) => `${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${esc(cur)}`;
  const closePanel = (el) => { el.hidden = true; };
  $$("#provPanel [data-close], #cffPanel [data-close]").forEach((b) => b.addEventListener("click", () => closePanel(b.closest(".subpanel"))));

  /* ---------------- line details: provenance and price ---------------- */
  let provLine = null;
  $("#invRows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-prov]");
    if (!b) return;
    const r = S.model.inputs.find((i) => i.id === Number(b.dataset.prov));
    if (!r) return;
    provLine = r.id;
    const f = $("#provForm");
    $("#provName").textContent = r.label || r.target.name;
    $("#provUnit").textContent = r.input_unit || r.target.unit || "unit";
    f.source_ref.value = r.source_ref || r.comment || "";
    f.data_year.value = r.data_year ? Math.round(r.data_year) : "";
    f.supplier.value = r.supplier || "";
    f.unit_cost.value = r.unit_cost ?? "";
    f.verified.checked = !!r.verified;
    f.cost_type.value = r.cost_type || ""; f.replace_every.value = r.replace_every ?? ""; f.cost_gsd.value = r.cost_gsd ?? "";
    [0, 1, 2, 3].forEach((i) => (f["pef" + i].value = r.pef ? String(r.pef[i]) : ""));
    $("#provSaved").textContent = "";
    $("#provPanel").hidden = false;
    $("#provPanel").scrollIntoView({ block: "nearest" });
    f.source_ref.focus();
  });
  $("#provForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    guard($("button[type=submit]", f), async () => {
      if (!provLine) throw new Error("Choose a line first.");
      const y = f.data_year.value.trim();
      if (y && !(Number(y) >= 1900 && Number(y) <= 2100)) throw new Error("Give the year as four digits, e.g. 2024.");
      const pef = [0, 1, 2, 3].map((i) => f["pef" + i].value);
      if (pef.some((v) => v) && !pef.every((v) => v)) throw new Error("Give all four PEF scores, or none.");
      await patchLine(provLine, { source_ref: f.source_ref.value.trim(), data_year: y, supplier: f.supplier.value.trim(),
        unit_cost: f.unit_cost.value.trim(), verified: f.verified.checked, cost_type: f.cost_type.value, replace_every: f.replace_every.value.trim(), cost_gsd: f.cost_gsd.value.trim(), pef: pef.every((v) => v) ? pef.map(Number) : null }, true);
      $("#provSaved").textContent = "Saved.";
    });
  });

  /* ---------------- correlated parameters ---------------- */
  function corrs() { return (S.model && S.model.scope && S.model.scope.correlations) || []; }
  function renderCorr() {
    const box = $("#corrList"), f = $("#corrForm");
    if (!box || !f) return;
    const p = S.params || {};
    const dist = [...(p.project || []), ...(p.model || [])].filter((x) => x.utype && !x.formula).map((x) => x.name);
    const opts = dist.map((n) => `<option>${esc(n)}</option>`).join("");
    f.a.innerHTML = opts; f.b.innerHTML = opts;
    if (dist.length > 1) f.b.selectedIndex = 1;
    f.hidden = dist.length < 2 || !S.model;
    const list = corrs();
    box.innerHTML = list.length ? list.map((c, i) => `<li><span class="grow"><code>${esc(c.a)}</code> and <code>${esc(c.b)}</code>: r = ${Number(c.r).toFixed(2)}</span><button class="ghost danger" data-delcorr="${i}">Remove</button></li>`).join("")
      : `<li class="empty">${dist.length < 2 ? "Give at least two parameters a distribution to correlate them." : "No correlations: parameters are sampled independently."}</li>`;
  }
  const _loadParams = loadParams;
  loadParams = async function () { await _loadParams.apply(this, arguments); renderCorr(); };
  $("#corrForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    guard($("button", f), async () => {
      if (!S.model) throw new Error("Save the goal & scope first.");
      const r = Number(f.r.value);
      if (f.a.value === f.b.value) throw new Error("Choose two different parameters.");
      if (!(r >= -0.99 && r <= 0.99) || f.r.value === "") throw new Error("The correlation must be between -0.99 and 0.99.");
      const list = corrs().filter((c) => !((c.a === f.a.value && c.b === f.b.value) || (c.a === f.b.value && c.b === f.a.value)));
      list.push({ a: f.a.value, b: f.b.value, r });
      await saveModelScope({ correlations: list });
      f.r.value = ""; renderCorr(); toast("Correlation saved. It is used in the next Monte Carlo run.");
    });
  });
  $("#corrList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-delcorr]");
    if (!b) return;
    guard(b, async () => {
      const list = corrs().filter((_, i) => i !== Number(b.dataset.delcorr));
      await saveModelScope({ correlations: list }); renderCorr();
    });
  });

  /* ---------------- Circular Footprint Formula ---------------- */
  const CFF_SEARCH = { virgin: "", recycled: "recycled", recycling_eol: "recycling", avoided_virgin: "", energy_recovery: "incineration",
    avoided_heat: "heat", avoided_electricity: "electricity", disposal: "landfill" };
  const cffChoice = {};
  function cffParams() {
    const p = {};
    $$("#cffPanel [data-cff]").forEach((i) => (p[i.dataset.cff] = i.value === "" ? "" : Number(i.value)));
    return p;
  }
  let cffTimer = null;
  async function cffPreview() {
    try {
      const r = await api("POST", "/api/cff/preview", { params: cffParams() });
      const mass = Number($("#cffMass").value) || 0;
      $("#cffCoef").innerHTML = "Lines per unit of material: " + r.lines.filter((l) => l.coefficient > 1e-12)
        .map((l) => `${esc(l.label)} ${fmt(l.coefficient)}${l.role.startsWith("avoided") ? " (credit)" : ""}${l.unit.startsWith("MJ") ? " MJ/kg" : ""}`).join("; ") +
        (mass ? `. For ${fmt(mass)} ${esc($("#cffUnit").value)} these amounts are multiplied by the mass.` : ".");
      const need = r.lines.filter((l) => l.coefficient > 1e-12).map((l) => l);
      $("#cffDatasets").innerHTML = need.map((l) => `<div class="cff-row" data-role="${l.role}"><span class="cff-lab">${esc(l.label)}${l.role === "avoided_virgin" ? ' <span class="hint">(empty: same as virgin)</span>' : ""}</span>
        <input class="cff-q" placeholder="search dataset" value="${esc((cffChoice[l.role] && cffChoice[l.role].q) || CFF_SEARCH[l.role] || "")}">
        <select class="cff-sel">${cffChoice[l.role] && cffChoice[l.role].opts ? cffChoice[l.role].opts : '<option value="">type to search</option>'}</select></div>`).join("");
      $$("#cffDatasets .cff-row").forEach((row) => { const c = cffChoice[row.dataset.role]; if (c && c.id) $(".cff-sel", row).value = c.id; });
    } catch (e) { $("#cffCoef").innerHTML = `<span class="danger">${esc(e.message)}</span>`; }
  }
  $("#btnCff").addEventListener("click", () => {
    if (!S.model) { toast("Create a model in step 2 first.", true); return; }
    $("#cffPanel").hidden = !$("#cffPanel").hidden;
    if (!$("#cffPanel").hidden) { cffPreview(); $("#cffPanel").scrollIntoView({ block: "nearest" }); }
  });
  $("#cffPanel").addEventListener("input", (e) => {
    if (e.target.matches("[data-cff], #cffMass")) { clearTimeout(cffTimer); cffTimer = setTimeout(cffPreview, 350); return; }
    if (e.target.classList.contains("cff-q")) {
      const row = e.target.closest(".cff-row"), q = e.target.value.trim();
      clearTimeout(row._t);
      row._t = setTimeout(async () => {
        if (q.length < 2) return;
        const { results } = await api("GET", "/api/search?q=" + encodeURIComponent(q));
        const opts = results.slice(0, 25).map((a) => `<option value="${a.id}">${esc(a.name)} [${esc(a.location || "")}] ${esc(a.unit || "")}, ${esc(a.db || "")}</option>`).join("") || '<option value="">no match</option>';
        $(".cff-sel", row).innerHTML = opts;
        cffChoice[row.dataset.role] = { q, opts, id: $(".cff-sel", row).value };
      }, 300);
    }
  });
  $("#cffPanel").addEventListener("change", (e) => {
    if (!e.target.classList.contains("cff-sel")) return;
    const row = e.target.closest(".cff-row");
    cffChoice[row.dataset.role] = { ...(cffChoice[row.dataset.role] || {}), id: e.target.value, opts: e.target.innerHTML };
  });
  $("#btnCffApply").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    const mass = Number($("#cffMass").value);
    if (!(mass > 0)) throw new Error("Give the material mass per functional unit.");
    const datasets = {};
    $$("#cffDatasets .cff-row").forEach((row) => { const v = $(".cff-sel", row).value; if (v) datasets[row.dataset.role] = Number(v); });
    const r = await api("POST", `/api/models/${S.model.id}/cff`, { mass, unit: $("#cffUnit").value, params: cffParams(), datasets,
      stage_production: $("#cffStageP").value.trim(), stage_eol: $("#cffStageE").value.trim() });
    S.model = r.model; S.result = null; renderInventory(); markSteps();
    toast(`${r.added.length} lines added with the Circular Footprint Formula.`);
    $("#cffPanel").hidden = true;
  }));

  /* ---------------- Summary: costs and water ---------------- */
  const _renderSummary = renderSummary;
  renderSummary = function () {
    _renderSummary.apply(this, arguments);
    const r = S.result, lc = r.lcc, w = r.water;
    let h = "";
    if (lc) {
      const types = (lc.by_type || []).filter((t) => t.cost);
      h += `<h2>Life cycle cost <button type="button" class="q" data-help="life cycle costing" aria-label="Help">?</button></h2>
        <p><b>${money(lc.total, lc.currency)}</b> per functional unit${lc.rate_percent ? `; net present cost ${money(lc.total_discounted, lc.currency)} at ${lc.rate_percent}% per year` : ""}${lc.beyond_boundary ? `; beyond the boundary (module D) ${money(lc.beyond_boundary, lc.currency)}` : ""}.${lc.residual_value ? ` Includes a residual value of ${money(lc.residual_value, lc.currency)} at the end of the study period.` : ""}</p>
        ${lc.uncertainty ? `<p class="hint">With the price uncertainty of ${lc.uncertainty.lines} line(s): 95 % of ${lc.uncertainty.iterations.toLocaleString()} Monte Carlo runs give a net present cost between ${money(lc.uncertainty.p2_5, lc.currency)} and ${money(lc.uncertainty.p97_5, lc.currency)} (median ${money(lc.uncertainty.median, lc.currency)}).</p>` : ""}
        ${Object.keys(lc.escalation || {}).length ? `<p class="hint">Real price escalation: ${Object.entries(lc.escalation).map(([k, v]) => `${esc(k)} ${v} % per year`).join(", ")}.</p>` : ""}
        <div class="table-wrap"><table><thead><tr><th>Line</th><th>Stage</th><th class="num">Cost</th>${lc.rate_percent ? '<th class="num">Discounted</th>' : ""}</tr></thead><tbody>` +
        lc.lines.slice(0, 12).map((l) => `<tr><td>${esc(l.name)}${l.source === "sub-model" ? ' <span class="hint">(from its model)</span>' : ""}${l.revenue ? ' <span class="hint">(revenue)</span>' : ""}</td><td>${esc(l.stage)}</td><td class="num">${money(l.cost, lc.currency)}</td>${lc.rate_percent ? `<td class="num">${money(l.discounted, lc.currency)}</td>` : ""}</tr>`).join("") +
        `</tbody></table></div>` + (types.length > 1 || (types[0] && types[0].type !== "not classified") ? `<p>By cost type: ${types.map((t) => `${esc(t.type)} ${money(t.cost, lc.currency)}`).join("; ")}.</p>` : "") +
        `<p class="hint">${esc(lc.note)}${lc.n_uncosted ? ` ${lc.n_uncosted} line(s) have no price.` : ""}</p>`;
    }
    if (w) {
      h += `<h2>Water inventory</h2><p>Withdrawal <b>${fmt(w.withdrawal)} m3</b>${w.withdrawal_turbine ? ` (of which ${fmt(w.withdrawal_turbine)} m3 turbine water)` : ""}, released ${fmt(w.release)} m3, consumption <b>${fmt(w.consumption)} m3</b> per functional unit.</p><p class="hint">${esc(w.note)}</p>`;
    }
    $("#summaryExtra").innerHTML = h;
    $("#summaryExtraBox").hidden = !h;
  };

  /* ---------------- report centre, executive summary, figures ---------------- */
  const RC_ACTION = { word: "#btnWord", excel: "#btnExcel", executive: "#btnExec", figures: "#btnFigures", epd: "#btnEpdWord",
    iso14067: "#btnIso14067", ghg: "#btnGhg", review: "#btnReviewLoad" };
  $("#btnRcCheck").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/report-centre", calcBody());
    $("#rcOut").innerHTML = r.reports.map((x) => {
      const open = x.needs.filter((n) => !n.ok && n.level === "required"), rec = x.needs.filter((n) => !n.ok && n.level === "recommended");
      return `<article class="rc-card${open.length ? "" : " ready"}"><header><h3>${esc(x.title)}</h3><span class="rc-count" title="required items met">${x.met}/${x.total}</span></header>
        <p class="hint">${esc(x.for)}</p>${open.length ? `<p class="rc-sub">Still required:</p><ul>${open.slice(0, 4).map((n) => `<li>${esc(n.text)}</li>`).join("")}${open.length > 4 ? `<li>and ${open.length - 4} more</li>` : ""}</ul>` : '<p class="ok">All required items present.</p>'}
        ${rec.length ? `<details><summary class="hint">${rec.length} recommended item(s) open</summary><ul>${rec.map((n) => `<li>${esc(n.text)}</li>`).join("")}</ul></details>` : ""}
        <button data-rc="${x.id}"${open.length ? "" : ' class="primary"'}>Create</button></article>`;
    }).join("");
  }));
  $("#rcOut").addEventListener("click", (e) => {
    const b = e.target.closest("[data-rc]");
    if (!b) return;
    const target = $(RC_ACTION[b.dataset.rc]);
    if (b.dataset.rc === "epd") { const d = target.closest("details"); if (d) d.open = true; }
    if (b.dataset.rc === "review") { target.scrollIntoView({ block: "center" }); }
    target.click();
  });
  $("#btnExec").addEventListener("click", (e) => guard(e.target, async () => {
    await exportTo("/api/export/executive", `${safeName(S.model && S.model.name)} summary.docx`, "docx", calcBody());
  }));
  $("#btnFigures").addEventListener("click", (e) => guard(e.target, async () => {
    await exportTo("/api/export/figures", `${safeName(S.model && S.model.name)} figures.zip`, "zip", calcBody());
  }));

  /* ---------------- toolbox: database versions and project overview ---------------- */
  function fillDbSelects() {
    const dbs = (S.status && S.status.databases) || [];
    const opts = dbs.map((d) => `<option value="${d.id}">${esc(d.name)}${d.version ? " " + esc(d.version) : ""}</option>`).join("");
    const a = $("#dbcA").value, b = $("#dbcB").value;
    $("#dbcA").innerHTML = opts; $("#dbcB").innerHTML = opts;
    if (a) $("#dbcA").value = a;
    if (b) $("#dbcB").value = b; else if (dbs.length > 1) $("#dbcB").selectedIndex = 1;
  }
  const _showToolTab = showToolTab;
  showToolTab = function (t) {
    _showToolTab.apply(this, arguments);
    if ((t === "dbs" || t === "dash" || t === "alloc") && !(S.status && S.status.project)) { toast("Open a project first (step 1).", true); return; }
    if (t === "dbs") fillDbSelects();
    if (t === "dash") loadDash(false);
    if (t === "alloc") loadAlloc().catch((e) => toast(e.message, true));
  };
  async function loadAlloc() {
    const r = await api("GET", "/api/allocation-overview");
    $("#allocNote").textContent = r.note;
    const v = (x) => (x === "" || x == null ? "-" : fmt(Number(x)));
    $("#allocOut").innerHTML = r.models.length ? `<div class="table-wrap"><table><thead><tr><th>Model</th><th>Rule</th><th class="num">Share for the product</th><th>Co-products</th><th>Avoided products</th><th class="num">Module D lines</th><th>Used in</th><th>To check</th></tr></thead><tbody>` +
      r.models.map((m) => `<tr><td><a href="#" data-openmodel="${m.id}">${esc(m.name)}</a></td><td>${esc(m.rule || "none")}</td><td class="num">${(100 * m.share).toFixed(2)} %</td>
        <td>${m.coproducts.length ? m.coproducts.map((c) => `${esc(c.name || "?")} <span class="hint">(${[["mass", "kg"], ["price", ""], ["energy", "MJ"], ["physical", ""]].filter(([k]) => c[k] !== "" && c[k] != null).map(([k, u]) => `${k} ${v(c[k])}${u ? " " + u : ""}`).join(", ")})</span>`).join("<br>") : "-"}</td>
        <td>${m.avoided.length ? m.avoided.map(esc).join("<br>") : "-"}</td><td class="num">${m.module_d || "-"}</td><td>${m.used_in.length ? m.used_in.map(esc).join(", ") : "-"}</td>
        <td>${m.issues.length ? `<span class="danger">${m.issues.map(esc).join("; ")}</span>` : '<span class="ok">ok</span>'}</td></tr>`).join("") + "</tbody></table></div>"
      : '<p class="empty">No models in this project yet.</p>';
  }
  $("#btnAllocLoad").addEventListener("click", (e) => guard(e.target, loadAlloc));
  $("#allocOut").addEventListener("click", (e) => {
    const a = e.target.closest("[data-openmodel]");
    if (!a) return;
    e.preventDefault();
    guard(null, async () => { await loadModel(Number(a.dataset.openmodel)); renderModelSelect(); go("scope"); });
  });
  $("#btnXc").addEventListener("click", (e) => guard(e.target, async () => {
    if (!S.selectedMethods.size) throw new Error("Pick impact categories in step 4 first.");
    const { job } = await api("POST", "/api/crosscheck", { method_ids: [...S.selectedMethods], sample: Number($("#xcN").value) || 200 });
    $("#xcOut").innerHTML = '<p class="hint">Running; progress is shown at the bottom left.</p>';
    watchJob(job, { quiet: true, onDone: (j) => {
      const r = j.result;
      $("#xcOut").innerHTML = `<p class="${r.passed ? "ok" : "danger"}"><b>${esc(r.verdict)}</b></p><p class="hint">${esc(r.scope)} Solver: ${esc(r.solver)}; library of ${r.n_library.toLocaleString()} datasets.</p>
        <div class="table-wrap"><table><thead><tr><th>Kind</th><th>Name</th><th class="num">Largest relative difference</th></tr></thead><tbody>${r.rows.slice(0, 15).map((x) => `<tr><td>${esc(x.kind)}</td><td>${esc(x.name)}</td><td class="num">${Math.max(...x.relative_difference).toExponential(1)}</td></tr>`).join("")}</tbody></table></div>`;
      $("#btnXcExport").disabled = false;
    } });
  }));
  $("#btnXcExport").addEventListener("click", (e) => guard(e.target, async () => {
    await exportTo("/api/export/crosscheck", "Cyclia independent cross-check.xlsx", "xlsx", {});
  }));
  $("#btnDbc").addEventListener("click", (e) => guard(e.target, async () => {
    if (!S.selectedMethods.size) throw new Error("Pick impact categories in step 4 first.");
    const a = Number($("#dbcA").value), b = Number($("#dbcB").value);
    if (!a || !b || a === b) throw new Error("Choose two different databases.");
    const { job } = await api("POST", "/api/db-compare", { db_a: a, db_b: b, method_ids: [...S.selectedMethods],
      only_project: $("#dbcProject").checked, sample: Number($("#dbcN").value) || 100 });
    $("#dbcOut").innerHTML = '<p class="hint">Calculating; progress is shown at the bottom left.</p>';
    watchJob(job, { quiet: true, onDone: (j) => {
      const r = j.result;
      const pc = (v) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(1)} %`);
      $("#dbcOut").innerHTML = `<p><b>${r.n_compared}</b> of ${r.n_matched} matched datasets compared (${esc(r.db_a)} to ${esc(r.db_b)}); ${r.n_missing} not found in the second database.</p>
        <div class="table-wrap"><table><thead><tr><th>Impact category</th><th class="num">Median change</th><th class="num">Datasets changed by more than 10 %</th></tr></thead><tbody>` +
        r.methods.map((m) => `<tr><td>${esc(m.category)}</td><td class="num">${pc(m.median_change_percent)}</td><td class="num">${m.share_changed_over_10 == null ? "-" : (100 * m.share_changed_over_10).toFixed(0) + " %"}</td></tr>`).join("") +
        `</tbody></table></div><h3>Largest changes</h3><div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Location</th>${r.methods.map((m) => `<th class="num">${esc(m.category)}</th>`).join("")}</tr></thead><tbody>` +
        r.rows.slice(0, 30).map((x) => `<tr><td>${esc(x.name)}</td><td>${esc(x.location || "")}</td>${x.change_percent.map((c) => `<td class="num">${pc(c)}</td>`).join("")}</tr>`).join("") +
        `</tbody></table></div><p class="hint">${esc(r.note)}</p>`;
    } });
  }));
  let relinkReady = false;
  async function relink(apply) {
    needModel();
    const a = Number($("#dbcA").value), b = Number($("#dbcB").value);
    if (!a || !b || a === b) throw new Error("Choose two different databases above (From and To).");
    const r = await api("POST", `/api/models/${S.model.id}/relink`, { db_from: a, db_to: b, apply, method_ids: [...S.selectedMethods] });
    const pc = (v) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(2)} %`);
    $("#relinkOut").innerHTML = r.lines.length ? `<p>${r.applied ? "Switched" : "Can switch"} <b>${r.n_found}</b> of ${r.lines.length} line(s) in ${r.models.length} model(s)${r.n_missing ? `; ${r.n_missing} have no match and stay as they are` : ""}.</p>
      <ul class="list">${r.lines.map((l) => `<li><span class="grow">${esc(l.name)} <span class="hint">in ${esc(l.model)}</span></span><span class="${l.found ? "ok" : "danger"}">${l.found ? "found" : "no match"}</span></li>`).join("")}</ul>` +
      (r.results ? `<h3>Results of ${esc(S.model.name)}</h3><div class="table-wrap"><table><thead><tr><th>Category</th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th></tr></thead><tbody>${r.results.map((x) => `<tr><td>${esc(x.category)} [${esc(x.unit)}]</td><td class="num">${x.before == null ? "-" : fmt(x.before)}</td><td class="num">${fmt(x.after)}</td><td class="num">${pc(x.change_percent)}</td></tr>`).join("")}</tbody></table></div>` : "")
      : `<p class="hint">No line of ${esc(S.model.name)} or its nested models uses the first database.</p>`;
    relinkReady = !r.applied && r.n_found > 0;
    $("#btnRelinkApply").disabled = !relinkReady;
    if (r.applied) { S.model = r.model; S.result = null; S.lastMigration = r.changed_models; $("#btnRelinkUndo").hidden = !r.changed_models.length; markSteps(); toast(`Lines switched in ${r.changed_models.length} model(s).`); }
  }
  $("#btnRelinkPreview").addEventListener("click", (e) => guard(e.target, () => relink(false)));
  $("#btnRelinkApply").addEventListener("click", (e) => guard(e.target, () => relink(true)));
  $("#btnRelinkUndo").addEventListener("click", (e) => guard(e.target, async () => {
    if (!S.lastMigration || !S.lastMigration.length) throw new Error("Nothing to undo.");
    const r = await api("POST", "/api/relink/undo", { model_ids: S.lastMigration });
    S.lastMigration = null; $("#btnRelinkUndo").hidden = true;
    await loadModel(S.model.id); S.result = null; markSteps();
    toast(r.skipped.length ? `Migration undone in ${r.undone.length} model(s); ${r.skipped.length} had later changes and were left as they are.` : `Migration undone in ${r.undone.length} model(s).`);
    $("#relinkOut").innerHTML = "";
  }));
  ["#dbcA", "#dbcB"].forEach((s) => $(s).addEventListener("change", () => { $("#btnRelinkApply").disabled = true; }));

  const REV = { "": "draft", internal: "internal", external: "expert", panel: "panel", verified: "verified" };
  async function loadDash(withCalc) {
    if (withCalc && !S.selectedMethods.size) throw new Error("Pick impact categories in step 4 first.");
    const r = await api("POST", "/api/dashboard", { method_ids: withCalc ? [...S.selectedMethods] : [] });
    const cats = withCalc ? (r.models.find((m) => m.results) || {}).results || [] : [];
    $("#dashOut").innerHTML = r.models.length ? `<div class="table-wrap"><table><thead><tr><th>Model</th><th>Functional unit</th><th class="num">Lines</th><th class="num">Default data quality</th><th class="num">Data type given</th><th>Review</th>${cats.map((c) => `<th class="num">${esc(c.category)} [${esc(c.unit)}]</th>`).join("")}${withCalc ? '<th class="num">Pedigree indicator</th><th class="num">Checks</th>' : ""}</tr></thead><tbody>` +
      r.models.map((m) => `<tr><td><a href="#" data-openmodel="${m.id}">${esc(m.name)}</a>${m.locked ? ' <span class="hint">(locked)</span>' : ""}${m.missing ? ` <span class="danger hint">${m.missing} missing</span>` : ""}</td><td>${esc(m.fu)}</td><td class="num">${m.n_inputs}</td>
        <td class="num">${m.n_inputs ? m.default_pedigree + " of " + m.n_inputs : "-"}</td><td class="num">${m.n_inputs ? m.typed + " (" + m.primary + " primary)" : "-"}</td><td>${REV[m.review_status] || esc(m.review_status)}</td>
        ${withCalc ? (m.results ? m.results.map((x) => `<td class="num">${fmt(x.total)}</td>`).join("") + `<td class="num">${m.dqr.filter((v) => v != null).length ? m.dqr.map((v) => (v == null ? "-" : v.toFixed(1))).join(" / ") : "-"}</td><td class="num">${m.errors ? `<span class="danger">${m.errors} error(s)</span>` : m.warnings + " warning(s)"}</td>` : `<td colspan="${cats.length + 2}" class="hint">${esc(m.error || "no inputs")}</td>`) : ""}</tr>`).join("") + "</tbody></table></div>"
      : '<p class="empty">No models in this project yet.</p>';
  }
  $("#btnDash").addEventListener("click", (e) => guard(e.target, () => loadDash(false)));
  $("#btnDashCalc").addEventListener("click", (e) => guard(e.target, () => loadDash(true)));
  $("#dashOut").addEventListener("click", (e) => {
    const a = e.target.closest("[data-openmodel]");
    if (!a) return;
    e.preventDefault();
    guard(null, async () => { await loadModel(Number(a.dataset.openmodel)); renderModelSelect(); go("scope"); });
  });
})();
