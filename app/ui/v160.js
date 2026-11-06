/* Custom data entry: databases, product and elementary flows, processes, exchanges, factors. */
(function () {
  const C = { meta: null, db: null, data: null, proc: null, found: [] };
  const val = (id) => ($("#" + id).value || "").trim();
  const num = (id) => (val(id) === "" ? null : Number(val(id)));
  const opt = (v, t, sel) => `<option value="${esc(v)}" ${sel ? "selected" : ""}>${esc(t)}</option>`;

  async function loadMeta() {
    C.meta = await api("GET", "/api/custom");
    $("#cdUnits").innerHTML = C.meta.units.map((u) => `<option value="${esc(u)}">`).join("");
    const comps = Object.keys(C.meta.compartments);
    if (!$("#cdEComp").options.length) {
      $("#cdEComp").innerHTML = comps.map((c) => opt(c, c)).join("");
      fillSub();
    }
    const dbs = C.meta.databases;
    $("#cdDb").innerHTML = dbs.length ? dbs.map((d) => opt(d.id, `${d.name} (${d.n_process} processes, ${d.n_product} products)`, d.id === C.db)).join("")
      : '<option value="">No custom database yet: create one below</option>';
    if (!dbs.some((d) => d.id === C.db)) C.db = dbs.length ? dbs[0].id : null;
    $("#cdDb").value = C.db || "";
    renderElems();
    fillMethods();
    await loadDb();
  }
  function fillSub() {
    $("#cdESub").innerHTML = C.meta.compartments[$("#cdEComp").value].map((s) => opt(s, s)).join("");
  }
  async function loadDb() {
    C.data = C.db ? await api("GET", `/api/custom/${C.db}`) : null;
    renderProducts(); renderProcs(); fillTargets();
  }
  async function refreshAll() {
    await loadMeta();
    if (typeof refreshStatus === "function") await refreshStatus();
  }
  function needDb() { if (!C.db) throw new Error("Create or choose a custom database first."); }

  function renderProducts() {
    const ps = C.data ? C.data.products : [];
    $("#cdProducts").innerHTML = ps.length ? `<thead><tr><th>Product</th><th>Unit</th><th>Category</th><th>Source</th><th>Identifier</th><th></th></tr></thead><tbody>` +
      ps.map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.data.unit)}</td><td>${esc(p.data.category || "")}</td><td>${esc(p.source || "")}</td><td class="meta">${esc(p.uuid)}<br>revision ${p.revision}, ${esc((p.modified || "").slice(0, 10))}</td><td><button class="ghost" data-cddel="${esc(p.uuid)}">Delete</button></td></tr>`).join("") + "</tbody>"
      : "<tbody><tr><td class=\"hint\">No product yet.</td></tr></tbody>";
    $("#cdPrProduct").innerHTML = ps.map((p) => opt(p.uuid, `${p.name} (${p.data.unit})`)).join("") || '<option value="">Add a product first</option>';
  }
  function renderElems() {
    const fs = C.meta.elementary_flows;
    $("#cdElems").innerHTML = fs.length ? `<thead><tr><th>Flow</th><th>Compartment</th><th>Unit</th><th>CAS</th><th>Source</th><th>Identifier</th><th></th></tr></thead><tbody>` +
      fs.map((f) => `<tr><td>${esc(f.name)}</td><td>${esc(f.data.compartment)}/${esc(f.data.subcompartment)}</td><td>${esc(f.data.unit)}</td><td>${esc(f.data.cas || "")}</td><td>${esc(f.source || "")}</td><td class="meta">${esc(f.uuid)}</td><td><button class="ghost" data-cddel="${esc(f.uuid)}">Delete</button></td></tr>`).join("") + "</tbody>"
      : "<tbody><tr><td class=\"hint\">No custom elementary flow yet.</td></tr></tbody>";
  }
  function renderProcs() {
    const ps = C.data ? C.data.processes : [];
    if (!ps.some((p) => p.uuid === C.proc)) C.proc = null;
    $("#cdProc").innerHTML = '<option value="">(new process)</option>' + ps.map((p) => opt(p.uuid, `${p.name} [${p.data.location}]`, p.uuid === C.proc)).join("");
    fillProcForm();
  }
  function fillProcForm() {
    const p = C.data && C.data.processes.find((x) => x.uuid === C.proc);
    const d = p ? p.data : { amount: 1, type: "production", location: "GLO", dq: {} };
    $("#cdPrName").value = p ? p.name : "";
    if (p) $("#cdPrProduct").value = d.product;
    $("#cdPrAmount").value = d.amount; $("#cdPrType").value = d.type; $("#cdPrLoc").value = d.location;
    $("#cdPrTech").value = d.technology || ""; $("#cdPrTime").value = d.time_period || ""; $("#cdPrData").value = d.data_type || "";
    $("#cdPrSrc").value = p ? p.source || "" : ""; $("#cdPrComment").value = d.comment || "";
    const dq = d.dq || {};
    $("#cdDqTer").value = dq.ter ?? ""; $("#cdDqGer").value = dq.ger ?? ""; $("#cdDqTir").value = dq.tir ?? ""; $("#cdDqP").value = dq.p ?? "";
    renderExchanges(p);
  }
  function uncText(e) {
    if (e.uncertainty === "pedigree") return `pedigree ${(e.pedigree || []).join(",")}`;
    if (e.uncertainty === "lognormal") return `lognormal, GSD ${fmt(Math.exp(e.p1))}`;
    if (e.uncertainty === "normal") return `normal, SD ${fmt(e.p1)} ${esc(e.ref_unit)}`;
    if (e.uncertainty === "triangular") return `triangular ${fmt(e.p1)} / ${fmt(e.p2)} / ${fmt(e.p3)}`;
    if (e.uncertainty === "uniform") return `uniform ${fmt(e.p1)} to ${fmt(e.p2)}`;
    return "-";
  }
  function renderExchanges(p) {
    const ex = p ? p.exchanges : [];
    $("#cdExchanges").innerHTML = !p ? '<tbody><tr><td class="hint">Save the process first, then add its exchanges.</td></tr></tbody>'
      : ex.length ? `<thead><tr><th>Type</th><th>Flow or supplier</th><th class="num">Entered</th><th class="num">In reference unit</th><th>Uncertainty</th><th>Source</th><th></th></tr></thead><tbody>` +
        ex.map((e) => `<tr><td>${e.kind === "elementary" ? "emission or resource" : e.avoided ? "avoided product" : e.treatment ? "waste to treatment" : "input"}</td><td>${esc(e.label)}</td><td class="num">${fmt(e.amount)} ${esc(e.unit)}</td><td class="num">${fmt(e.amount_ref)} ${esc(e.ref_unit)}</td><td>${uncText(e)}</td><td>${esc(e.source || "")}</td><td><button class="ghost" data-cdxdel="${e.id}">Remove</button></td></tr>`).join("") + "</tbody>"
        : '<tbody><tr><td class="hint">No exchange yet.</td></tr></tbody>';
  }

  function fillTargets() {
    const kind = $("#cdXKind").value, src = $("#cdXSupSrc").value;
    $("#cdXSupSrc").hidden = kind === "elementary";
    const lib = kind === "elementary" || src === "library";
    $("#cdXSearchRow").hidden = !lib;
    $("#cdXSearch").placeholder = kind === "elementary" ? "Search elementary flows of the library (e.g. carbon dioxide)" : "Search datasets of the library";
    let o = "";
    if (kind === "elementary") {
      const custom = C.meta.elementary_flows.map((f) => opt(f.uuid, `${f.name} (${f.data.compartment}/${f.data.subcompartment}, ${f.data.unit}) - custom`));
      o = custom.join("") + C.found.filter((f) => f.uuid).map((f) => opt(f.uuid, `${f.name} (${f.compartment}/${f.subcompartment}, ${f.unit})`)).join("");
    } else if (src === "custom") {
      o = (C.data ? C.data.processes : []).map((p) => opt(p.uuid, `${p.name} [${p.data.location}]${p.data.type === "treatment" ? " - waste treatment" : ""}`)).join("");
    } else {
      o = C.found.filter((a) => a.id).map((a) => opt(a.id, `${a.name} [${a.location}] (${a.unit}, ${a.db})`)).join("");
    }
    $("#cdXTarget").innerHTML = o || '<option value="">(nothing to choose: add or search first)</option>';
    refUnit();
  }
  function refUnit() {
    const kind = $("#cdXKind").value, v = $("#cdXTarget").value;
    let u = "";
    if (kind === "elementary") {
      const f = C.meta.elementary_flows.find((x) => x.uuid === v) || C.found.find((x) => x.uuid === v);
      u = f ? (f.data ? f.data.unit : f.unit) : "";
    } else if ($("#cdXSupSrc").value === "custom") {
      const p = C.data && C.data.processes.find((x) => x.uuid === v);
      const pr = p && C.data.products.find((x) => x.uuid === p.data.product);
      u = pr ? pr.data.unit : "";
    } else {
      const a = C.found.find((x) => String(x.id) === v);
      u = a ? a.unit : "";
    }
    $("#cdXRefUnit").textContent = u ? `reference unit: ${u}` : "";
    if (u && !val("cdXUnit")) $("#cdXUnit").value = u;
  }
  function uncFields() {
    const t = $("#cdXUnc").value;
    const n = (id, ph, size = 6) => `<input id="${id}" type="number" step="any" placeholder="${ph}" size="${size}">`;
    $("#cdXUncFields").innerHTML = t === "pedigree" ? ["reliability", "completeness", "temporal", "geographical", "technological"].map((x, i) => `<input id="cdPed${i}" type="number" min="1" max="5" placeholder="${x}" size="4" title="${x} (1 to 5)">`).join("")
      : t === "lognormal" ? n("cdUG", "GSD (e.g. 1.5)") : t === "normal" ? n("cdUS", "SD")
        : t === "triangular" ? n("cdUMin", "min") + n("cdUMode", "most likely") + n("cdUMax", "max")
          : t === "uniform" ? n("cdUMin", "min") + n("cdUMax", "max") : "";
  }
  function fillMethods() {
    const custom = C.meta.methods.map((m) => m.id);
    const ms = (S.methods || []).slice().sort((a, b) => (custom.includes(b.id) - custom.includes(a.id)) || (a.family + a.category).localeCompare(b.family + b.category));
    const cur = $("#cdFMethod").value;
    $("#cdFMethod").innerHTML = ms.map((m) => opt(m.id, `${m.family} | ${m.category}${m.indicator && m.indicator !== m.category ? " | " + m.indicator : ""} (${m.unit || ""})${custom.includes(m.id) ? " - custom" : ""}`, String(m.id) === cur)).join("") || '<option value="">No method installed: create a custom method</option>';
    fillFlows();
  }
  function fillFlows() {
    const mid = Number($("#cdFMethod").value), custom = C.meta.methods.some((m) => m.id === mid);
    $("#cdFSearchRow").hidden = !custom;
    const lib = custom ? (C.flowFound || []).map((f) => opt(f.uuid, `${f.name} (${f.compartment}/${f.subcompartment}, ${f.unit})`)) : [];
    $("#cdFFlow").innerHTML = C.meta.elementary_flows.map((f) => opt(f.uuid, `${f.name} (${f.data.compartment}/${f.data.subcompartment}, ${f.data.unit}) - custom`)).join("") + lib.join("")
      || '<option value="">No custom flow yet</option>';
    flowUnit();
  }
  function flowUnit() {
    const v = $("#cdFFlow").value;
    const f = C.meta.elementary_flows.find((x) => x.uuid === v) || (C.flowFound || []).find((x) => x.uuid === v);
    $("#cdFUnit").value = f ? (f.data ? f.data.unit : f.unit) : "";
  }

  // ------------------------------------------------------------------ events
  $("#cdDb").addEventListener("change", (e) => guard(null, async () => { C.db = Number(e.target.value) || null; C.proc = null; await loadDb(); }));
  $("#cdEComp").addEventListener("change", fillSub);
  $("#cdProc").addEventListener("change", (e) => { C.proc = e.target.value || null; fillProcForm(); });
  $("#btnCdProcNew").addEventListener("click", () => { C.proc = null; $("#cdProc").value = ""; fillProcForm(); $("#cdPrName").focus(); });
  $("#cdXKind").addEventListener("change", () => { $("#cdXUnit").value = ""; fillTargets(); });
  $("#cdXSupSrc").addEventListener("change", () => { $("#cdXUnit").value = ""; fillTargets(); });
  $("#cdXTarget").addEventListener("change", () => { $("#cdXUnit").value = ""; refUnit(); });
  $("#cdXUnc").addEventListener("change", uncFields);
  $("#cdFMethod").addEventListener("change", fillFlows);
  $("#cdFFlow").addEventListener("change", flowUnit);
  $("#cdFStatus").addEventListener("change", () => {
    const na = $("#cdFStatus").value === "not_applicable";
    $("#cdFValue").disabled = na; $("#cdFUnit").disabled = na;
    $("#cdFSrc").placeholder = na ? "Reason why the category does not apply" : "Source of the factor";
  });

  $("#btnCdNewDb").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/database", { name: val("cdNewName"), description: val("cdNewDesc"), author: val("cdNewAuthor"),
      geography: val("cdNewGeo"), reference_period: val("cdNewPeriod"), licence: val("cdNewLic") });
    C.db = r.db_id; $("#cdNewName").value = "";
    await refreshAll(); toast("Custom database created.");
  }));
  $("#btnCdImport").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/import", { path: val("cdImpPath") });
    C.db = r.db_id; await refreshAll(); toast("Custom data imported.");
  }));
  $("#btnCdExport").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    await exportTo(`/api/custom/${C.db}/export`, `${C.data.database.name} custom data.json`, "json");
  }));
  $("#btnCdCheck").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    const r = await api("GET", `/api/custom/${C.db}/check`);
    const cls = { error: "danger", warning: "warn", info: "hint" };
    $("#cdCheckOut").innerHTML = `<p class="${r.complete ? "ok" : "danger"}">${r.complete ? "The database can be calculated." : `${r.errors || 0} error(s) to correct.`} ${r.processes} process(es), ${r.warnings || 0} warning(s).</p>` +
      (r.findings.length ? "<ul>" + r.findings.map((f) => `<li class="${cls[f.level]}">${esc(f.message)}</li>`).join("") + "</ul>" : "");
  }));
  $("#btnCdProduct").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    await api("POST", `/api/custom/${C.db}/product`, { name: val("cdPName"), unit: val("cdPUnit"), category: val("cdPCat"), source: val("cdPSrc") });
    $("#cdPName").value = ""; await loadMeta(); toast("Product added.");
  }));
  $("#btnCdElem").addEventListener("click", (e) => guard(e.target, async () => {
    await api("POST", "/api/custom/elementary", { name: val("cdEName"), compartment: $("#cdEComp").value, subcompartment: $("#cdESub").value,
      unit: val("cdEUnit"), cas: val("cdECas"), source: val("cdESrc") });
    $("#cdEName").value = ""; $("#cdECas").value = ""; await loadMeta(); toast("Elementary flow added.");
  }));
  $("#btnCdProc").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    const dq = { ter: num("cdDqTer"), ger: num("cdDqGer"), tir: num("cdDqTir"), p: num("cdDqP") };
    Object.keys(dq).forEach((k) => dq[k] === null && delete dq[k]);
    const r = await api("POST", `/api/custom/${C.db}/process`, { uuid: C.proc || undefined, name: val("cdPrName"), product: $("#cdPrProduct").value,
      amount: num("cdPrAmount"), type: $("#cdPrType").value, location: val("cdPrLoc"), technology: val("cdPrTech"), time_period: val("cdPrTime"),
      data_type: $("#cdPrData").value, source: val("cdPrSrc"), comment: val("cdPrComment"), dq });
    C.proc = r.uuid; await refreshAll(); toast("Process saved.");
  }));
  $("#btnCdProcDel").addEventListener("click", (e) => guard(e.target, async () => {
    if (!C.proc) throw new Error("Choose a process first.");
    await api("POST", "/api/custom/delete", { uuid: C.proc });
    C.proc = null; await refreshAll(); toast("Process deleted.");
  }));
  $("#btnCdXSearch").addEventListener("click", (e) => guard(e.target, async () => {
    const q = encodeURIComponent(val("cdXSearch"));
    C.found = $("#cdXKind").value === "elementary" ? (await api("GET", `/api/flows?q=${q}`)).results : (await api("GET", `/api/search?q=${q}`)).results;
    fillTargets();
    if (!C.found.length) toast("Nothing found.", true);
  }));
  $("#btnCdX").addEventListener("click", (e) => guard(e.target, async () => {
    if (!C.proc) throw new Error("Save the process first.");
    const kind = $("#cdXKind").value, t = $("#cdXTarget").value;
    if (!t) throw new Error("Choose the supplier or the flow.");
    const b = { process: C.proc, kind: kind === "elementary" ? "elementary" : "technosphere", avoided: kind === "avoided",
      supplier: t, flow: t, amount: num("cdXAmount"), unit: val("cdXUnit"), uncertainty: $("#cdXUnc").value, source: val("cdXSrc"), comment: val("cdXComment") };
    if (b.uncertainty === "pedigree") b.pedigree = [0, 1, 2, 3, 4].map((i) => num("cdPed" + i));
    if (b.uncertainty === "lognormal") b.gsd = num("cdUG");
    if (b.uncertainty === "normal") b.sd = num("cdUS");
    if (b.uncertainty === "triangular" || b.uncertainty === "uniform") { b.min = num("cdUMin"); b.max = num("cdUMax"); }
    if (b.uncertainty === "triangular") b.mode = num("cdUMode");
    await api("POST", "/api/custom/exchange", b);
    $("#cdXAmount").value = ""; await loadDb(); if (typeof refreshStatus === "function") await refreshStatus(); toast("Exchange added.");
  }));
  $("#cdExchanges").addEventListener("click", (e) => { const b = e.target.closest("[data-cdxdel]"); if (!b) return;
    guard(b, async () => { await api("POST", "/api/custom/exchange/delete", { process: C.proc, id: Number(b.dataset.cdxdel) }); await loadDb(); }); });
  ["#cdProducts", "#cdElems"].forEach((sel) => $(sel).addEventListener("click", (e) => { const b = e.target.closest("[data-cddel]"); if (!b) return;
    guard(b, async () => { await api("POST", "/api/custom/delete", { uuid: b.dataset.cddel }); await loadMeta(); toast("Deleted."); }); }));
  $("#btnCdMethod").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/method", { family: val("cdMFam"), category: val("cdMCat"), indicator: val("cdMInd"), unit: val("cdMUnit"), source: val("cdMSrc") });
    if (typeof refreshStatus === "function") await refreshStatus();
    await loadMeta(); $("#cdFMethod").value = r.method_id; fillFlows(); toast("Impact category created.");
  }));
  $("#btnCdFSearch").addEventListener("click", (e) => guard(e.target, async () => {
    C.flowFound = (await api("GET", `/api/flows?q=${encodeURIComponent(val("cdFSearch"))}`)).results;
    fillFlows();
  }));
  $("#btnCdFactor").addEventListener("click", (e) => guard(e.target, async () => {
    const st = $("#cdFStatus").value;
    await api("POST", "/api/custom/factor", { method_id: Number($("#cdFMethod").value), flow_uuid: $("#cdFFlow").value, status: st,
      value: st === "value" ? num("cdFValue") : null, unit: val("cdFUnit"), source: st === "value" ? val("cdFSrc") : "", comment: st === "value" ? "" : val("cdFSrc") });
    $("#cdFValue").value = ""; toast("Factor saved."); await factorTable();
  }));
  async function factorTable() {
    const mids = [...new Set([...(S.selectedMethods || []), ...C.meta.methods.map((m) => m.id)])];
    if (!mids.length) { $("#cdFactors").innerHTML = '<tbody><tr><td class="hint">Choose impact categories in step 4 or create a custom method.</td></tr></tbody>'; return; }
    const r = await api("POST", "/api/custom/factors", { method_ids: mids });
    const lab = { value: "factor", not_applicable: "does not apply", missing: '<span class="danger">unknown: give a factor or record that it does not apply</span>' };
    $("#cdFactors").innerHTML = r.rows.length ? `<thead><tr><th>Impact category</th><th>Flow</th><th>Status</th><th class="num">Factor</th><th>Source or reason</th></tr></thead><tbody>` +
      r.rows.map((x) => `<tr><td>${esc(x.family)} | ${esc(x.category)}</td><td>${esc(x.flow)} (${esc(x.compartment)})</td><td>${lab[x.status]}</td><td class="num">${x.status === "value" ? `${fmt(x.value)} ${esc(x.method_unit)}/${esc(x.flow_unit)}` : ""}</td><td>${esc(x.source || x.comment || "")}</td></tr>`).join("") + "</tbody>"
      : '<tbody><tr><td class="hint">No custom elementary flow yet.</td></tr></tbody>';
  }
  $("#btnCdFTable").addEventListener("click", (e) => guard(e.target, factorTable));

  uncFields();
  const _show = showToolTab;
  showToolTab = function (t) {
    _show.apply(this, arguments);
    if (t === "custom") {
      if (!(S.status && S.status.project)) { toast("Open a project first (step 1).", true); return; }
      guard(null, loadMeta);
    }
  };
})();
