/* Your own data (custom data entry): databases, product and elementary flows, processes, exchanges, factors,
   checks, change history and the worked example. Uses the globals of app.js (S, $, $$, api, guard, toast, esc, fmt,
   exportTo, go, refreshStatus, renderInventory, markSteps, showToolTab). */
(function () {
  const C = { meta: null, db: null, data: null, proc: null, found: [], flowFound: [], check: null,
    editP: null, editE: null, editX: null, co: [], prParams: [], alValues: {}, dbParams: [], libPos: {}, connect: null };
  const val = (id) => ($("#" + id).value || "").trim();
  const num = (id) => (val(id) === "" ? null : Number(val(id)));
  const opt = (v, t, sel) => `<option value="${esc(v)}" ${sel ? "selected" : ""}>${esc(t)}</option>`;
  const empty = (cols, text) => `<tbody><tr><td class="hint" colspan="${cols}">${esc(text)}</td></tr></tbody>`;
  const procOf = (uid) => C.data && C.data.processes.find((p) => p.uuid === uid);

  // ------------------------------------------------------------------ loading
  async function loadMeta() {
    C.meta = await api("GET", "/api/custom");
    $("#cdUnits").innerHTML = C.meta.units.map((u) => `<option value="${esc(u)}">`).join("");
    if (!$("#cdEComp").options.length) {
      $("#cdEComp").innerHTML = Object.keys(C.meta.compartments).map((c) => opt(c, c)).join("");
      fillSub();
    }
    const dbs = C.meta.databases;
    if (!dbs.some((d) => d.id === C.db)) C.db = dbs.length ? dbs[0].id : null;
    $("#cdDb").innerHTML = dbs.length ? dbs.map((d) => opt(d.id, `${d.name} (${d.n_process} processes, ${d.n_product} products)`, d.id === C.db)).join("")
      : '<option value="">No custom database yet: create one below or create the worked example</option>';
    $("#cdNewDbBox").open = !dbs.length;
    $("#btnCdExample").hidden = dbs.some((d) => d.name === C.meta.example_name);
    renderElems();
    fillMethods();
    await loadUnits();
    await loadDb();
  }
  async function loadDb() {
    C.data = C.db ? await api("GET", `/api/custom/${C.db}`) : null;
    C.check = C.db ? await api("GET", `/api/custom/${C.db}/check`).catch(() => null) : null;
    renderProducts(); renderProcs(); fillTargets(); renderSteps();
    C.dbParams = C.data ? JSON.parse(JSON.stringify(C.data.database.parameters || [])) : [];
    paramTable("cdDbParams", C.dbParams);
    drawDiagram();
  }
  async function refreshAll() {
    await loadMeta();
    if (typeof refreshStatus === "function") await refreshStatus();
  }
  function needDb() { if (!C.db) throw new Error("Create or choose a custom database first (step 1)."); }

  // ------------------------------------------------------------------ the seven steps
  function renderSteps() {
    const d = C.data, f = (C.check && C.check.findings) || [];
    const procs = d ? d.processes : [];
    const factorsOpen = f.some((x) => /impact categories|Custom method/.test(x.message));
    const steps = [
      ["Database", "cdSec1", !!C.db, false],
      ["Product flows", "cdSec2", !!(d && d.products.length), false],
      ["Elementary flows", "cdSec3", !!(C.meta.elementary_flows.length || procs.some((p) => p.exchanges.some((e) => e.kind === "elementary"))), true],
      ["Processes", "cdSec4", procs.length > 0, false],
      ["Inputs and emissions", "cdSec5", procs.length > 0 && procs.every((p) => p.exchanges.length), false],
      ["Factors", "cdSec6", procs.length > 0 && !!C.check && !factorsOpen, false],
      ["Check and use", "cdSec7", !!(C.check && C.check.complete && procs.length), false],
    ];
    $("#cdSteps").innerHTML = steps.map(([t, sec, done, optional], i) =>
      `<li class="cd-step ${done ? "done" : ""}"><button data-cdgo="${sec}"><span class="cd-n">${done ? "✓" : i + 1}</span><span>${esc(t)}${optional ? '<small>optional</small>' : ""}</span></button></li>`).join("");
  }
  $("#cdSteps").addEventListener("click", (e) => { const b = e.target.closest("[data-cdgo]"); if (b) $("#" + b.dataset.cdgo).scrollIntoView({ behavior: "smooth", block: "start" }); });

  // ------------------------------------------------------------------ products
  function renderProducts() {
    const ps = C.data ? C.data.products : [];
    $("#cdProducts").innerHTML = ps.length ? `<thead><tr><th>Product</th><th>Unit</th><th>Category</th><th>Source</th><th>Identifier and revision</th><th></th></tr></thead><tbody>` +
      ps.map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.data.unit)}</td><td>${esc(p.data.category || "")}</td><td>${esc(p.source || "")}</td><td class="meta">${esc(p.uuid)}<br>revision ${p.revision}, ${esc((p.modified || "").slice(0, 10))}</td>
        <td><button class="ghost" data-cdpedit="${esc(p.uuid)}">Edit</button><button class="ghost" data-cddel="${esc(p.uuid)}">Delete</button></td></tr>`).join("") + "</tbody>"
      : empty(6, "No product yet. Example: bread, kg.");
    $("#cdPrProduct").innerHTML = ps.map((p) => opt(p.uuid, `${p.name} (${p.data.unit})`)).join("") || '<option value="">Add a product in step 2 first</option>';
    const p = procOf(C.proc);
    if (p) $("#cdPrProduct").value = p.data.product;
  }
  function productForm(p) {
    C.editP = p ? p.uuid : null;
    $("#cdPName").value = p ? p.name : ""; $("#cdPUnit").value = p ? p.data.unit : "";
    $("#cdPCat").value = p ? p.data.category || "" : ""; $("#cdPSrc").value = p ? p.source || "" : "";
    $("#btnCdProduct").textContent = p ? "Save changes" : "Add product";
    $("#btnCdPCancel").hidden = !p;
    if (p) $("#cdPName").focus();
  }
  $("#cdProducts").addEventListener("click", (e) => {
    const ed = e.target.closest("[data-cdpedit]");
    if (ed) productForm(C.data.products.find((x) => x.uuid === ed.dataset.cdpedit));
  });
  $("#btnCdPCancel").addEventListener("click", () => productForm(null));
  $("#btnCdProduct").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    await api("POST", `/api/custom/${C.db}/product`, { uuid: C.editP || undefined, name: val("cdPName"), unit: val("cdPUnit"), category: val("cdPCat"), source: val("cdPSrc") });
    toast(C.editP ? "Product saved." : "Product added."); productForm(null); await loadMeta();
  }));

  // ------------------------------------------------------------------ elementary flows
  function fillSub(sel) {
    $("#cdESub").innerHTML = C.meta.compartments[$("#cdEComp").value].map((s) => opt(s, s, s === sel)).join("");
  }
  function renderElems() {
    const fs = C.meta.elementary_flows;
    $("#cdElems").innerHTML = fs.length ? `<thead><tr><th>Flow</th><th>Compartment</th><th>Unit</th><th>CAS</th><th>Source</th><th>Identifier and revision</th><th></th></tr></thead><tbody>` +
      fs.map((f) => `<tr><td>${esc(f.name)}</td><td>${esc(f.data.compartment)}/${esc(f.data.subcompartment)}</td><td>${esc(f.data.unit)}</td><td>${esc(f.data.cas || "")}</td><td>${esc(f.source || "")}</td><td class="meta">${esc(f.uuid)}<br>revision ${f.revision}</td>
        <td><button class="ghost" data-cdeedit="${esc(f.uuid)}">Edit</button><button class="ghost" data-cddel="${esc(f.uuid)}">Delete</button></td></tr>`).join("") + "</tbody>"
      : empty(7, "No flow of your own yet. Most emissions and resources are already in the library.");
  }
  function elemForm(f) {
    C.editE = f ? f.uuid : null;
    $("#cdEName").value = f ? f.name : ""; $("#cdEUnit").value = f ? f.data.unit : ""; $("#cdECas").value = f ? f.data.cas || "" : "";
    $("#cdESrc").value = f ? f.source || "" : "";
    if (f) { $("#cdEComp").value = f.data.compartment; fillSub(f.data.subcompartment); }
    $("#btnCdElem").textContent = f ? "Save changes" : "Add elementary flow";
    $("#btnCdECancel").hidden = !f;
  }
  $("#cdElems").addEventListener("click", (e) => {
    const ed = e.target.closest("[data-cdeedit]");
    if (ed) elemForm(C.meta.elementary_flows.find((x) => x.uuid === ed.dataset.cdeedit));
  });
  $("#btnCdECancel").addEventListener("click", () => elemForm(null));
  $("#cdEComp").addEventListener("change", () => fillSub());
  $("#btnCdElem").addEventListener("click", (e) => guard(e.target, async () => {
    await api("POST", "/api/custom/elementary", { uuid: C.editE || undefined, name: val("cdEName"), compartment: $("#cdEComp").value,
      subcompartment: $("#cdESub").value, unit: val("cdEUnit"), cas: val("cdECas"), source: val("cdESrc") });
    toast(C.editE ? "Flow saved; factors were matched again." : "Elementary flow added."); elemForm(null); await loadMeta();
  }));
  ["#cdProducts", "#cdElems"].forEach((sel) => $(sel).addEventListener("click", (e) => {
    const b = e.target.closest("[data-cddel]"); if (!b) return;
    guard(b, async () => { await api("POST", "/api/custom/delete", { uuid: b.dataset.cddel }); toast("Deleted."); await loadMeta(); });
  }));

  // ------------------------------------------------------------------ parameter tables
  function paramTable(id, list) {
    $("#" + id).innerHTML = (list.length ? `<thead><tr><th>Name</th><th>Value or formula</th><th>Comment</th><th></th></tr></thead>` : "") + "<tbody>" +
      (list.length ? list.map((q, i) => `<tr data-pi="${i}"><td><input data-pf="name" value="${esc(q.name)}" size="12"></td>
        <td><input data-pf="vf" value="${esc(q.formula ? q.formula : q.value ?? "")}" size="22" placeholder="0.8 or dough / (1 - loss)"></td>
        <td><input data-pf="comment" value="${esc(q.comment || "")}" class="grow"></td><td><button class="ghost" data-pdel="${i}">Remove</button></td></tr>`).join("")
        : '<tr><td class="hint">No parameter yet.</td></tr>') + "</tbody>";
    const t = $("#" + id);
    t.oninput = (e) => {
      const r = e.target.closest("[data-pi]"); if (!r) return;
      const q = list[Number(r.dataset.pi)], f = e.target.dataset.pf;
      if (f === "vf") { const v = e.target.value.trim(); if (v !== "" && !Number.isNaN(Number(v))) { q.value = Number(v); q.formula = ""; } else { q.formula = v; q.value = null; } }
      else q[f] = e.target.value;
    };
    t.onclick = (e) => { const b = e.target.closest("[data-pdel]"); if (b) { list.splice(Number(b.dataset.pdel), 1); paramTable(id, list); } };
  }
  $("#btnCdDbParamAdd").addEventListener("click", () => { C.dbParams = C.dbParams || []; C.dbParams.push({ name: "", value: 0, formula: "", comment: "" }); paramTable("cdDbParams", C.dbParams); });
  $("#btnCdDbParamSave").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    await api("POST", `/api/custom/${C.db}/parameters`, { parameters: C.dbParams });
    toast("Parameters saved; every line that uses them was recalculated."); await loadDb();
  }));
  $("#btnCdPrParamAdd").addEventListener("click", () => { C.prParams.push({ name: "", value: 0, formula: "", comment: "" }); paramTable("cdPrParams", C.prParams); });

  // ------------------------------------------------------------------ units of your own
  async function loadUnits() {
    C.units = await api("GET", "/api/custom/units");
    const dims = C.units.dimensions, names = { mass: "mass", energy: "energy", volume: "volume", area: "area", length: "length",
      transport: "transport of goods", ptransport: "transport of persons", vtransport: "vehicle distance", time: "time",
      landocc: "land occupation", voltransport: "transport of volume", count: "count", radioactivity: "radioactivity" };
    const cur = $("#cdUDim").value;
    $("#cdUDim").innerHTML = Object.entries(dims).map(([d, base]) => opt(d, `${names[d] || "your quantity: " + base} (in ${base})`, d === cur)).join("") +
      opt("new", "new kind of quantity (its own base unit)", cur === "new");
    unitDim();
    $("#cdUnitList").innerHTML = C.units.units.length ? `<thead><tr><th>Unit</th><th>Definition</th><th>Source</th><th></th></tr></thead><tbody>` +
      C.units.units.map((u) => `<tr><td>${esc(u.name)}</td><td>${u.dimension === "custom:" + u.name ? "base unit of a new kind of quantity" : `1 ${esc(u.name)} = ${fmt(u.factor)} ${esc(u.base)}`}</td><td>${esc(u.source || "")}</td>
        <td>${u.used ? '<span class="hint">in use</span>' : `<button class="ghost" data-udel="${esc(u.name)}">Delete</button>`}</td></tr>`).join("") + "</tbody>"
      : empty(4, "No unit of your own yet.");
  }
  function unitDim() {
    const d = $("#cdUDim").value, isNew = d === "new";
    $("#cdUFactor").hidden = isNew; $("#cdUEq").hidden = isNew;
    $("#cdUBase").textContent = isNew ? "Then define multiples of it, choosing it as the kind of quantity." : (C.units ? C.units.dimensions[d] || "" : "");
  }
  $("#cdUDim").addEventListener("change", unitDim);
  $("#btnCdUnit").addEventListener("click", (e) => guard(e.target, async () => {
    await api("POST", "/api/custom/units", { name: val("cdUName"), dimension: $("#cdUDim").value, factor: num("cdUFactor"), source: val("cdUSrc") });
    toast(`Unit "${val("cdUName")}" saved.`); $("#cdUName").value = ""; $("#cdUFactor").value = ""; await loadMeta();
  }));
  $("#cdUnitList").addEventListener("click", (e) => { const b = e.target.closest("[data-udel]"); if (!b) return;
    guard(b, async () => { await api("POST", "/api/custom/units/delete", { name: b.dataset.udel }); toast("Unit deleted."); await loadMeta(); }); });

  // ------------------------------------------------------------------ co-products and allocation
  function renderCo() {
    const prods = C.data ? C.data.products : [];
    $("#cdCoRows").innerHTML = C.co.map((c, i) => `<div class="cd-co-row" data-ci="${i}"><span class="hint">Co-product</span><select data-cf="product">${prods.map((p) => opt(p.uuid, `${p.name} (${p.data.unit})`, p.uuid === c.product)).join("")}</select>
      <input data-cf="amount" type="number" step="any" value="${esc(c.amount ?? "")}" size="7" placeholder="amount"><button class="ghost" data-codel="${i}">Remove</button></div>`).join("");
    renderAlValues();
  }
  function renderAlValues() {
    const m = $("#cdAlMethod").value, prods = C.data ? C.data.products : [];
    const outs = [$("#cdPrProduct").value, ...C.co.map((c) => c.product)].filter(Boolean);
    const label = { mass: "kg per unit (only if the unit is not a mass unit)", energy: "MJ per unit (only if the unit is not an energy unit)", economic: "price per unit", manual: "share (0 to 1)" }[m];
    $("#cdAlValues").innerHTML = C.co.length && m ? outs.map((u) => { const p = prods.find((x) => x.uuid === u);
      return `<div class="cd-co-row"><span class="grow">${esc(p ? p.name : "?")} (${esc(p ? p.data.unit : "")})</span><span class="hint">${label}</span><input data-av="${esc(u)}" type="number" step="any" size="8" value="${esc(C.alValues[u] ?? "")}"></div>`; }).join("") : "";
    const sh = procOf(C.proc) && procOf(C.proc).shares;
    $("#cdCoSummary").textContent = C.co.length ? `(${C.co.length} co-product${C.co.length > 1 ? "s" : ""}${sh ? ", shares " + Object.entries(sh).map(([u, f]) => { const p = prods.find((x) => x.uuid === u); return `${p ? p.name : "?"} ${(f * 100).toPrecision(3)} %`; }).join(", ") : ""})` : "";
  }
  $("#cdCoRows").addEventListener("input", (e) => { const r = e.target.closest("[data-ci]"); if (!r) return; const c = C.co[Number(r.dataset.ci)];
    c[e.target.dataset.cf] = e.target.dataset.cf === "amount" ? Number(e.target.value) : e.target.value; renderAlValues(); });
  $("#cdCoRows").addEventListener("change", (e) => { if (e.target.dataset.cf === "product") { C.co[Number(e.target.closest("[data-ci]").dataset.ci)].product = e.target.value; renderAlValues(); } });
  $("#cdCoRows").addEventListener("click", (e) => { const b = e.target.closest("[data-codel]"); if (b) { C.co.splice(Number(b.dataset.codel), 1); renderCo(); } });
  $("#cdAlValues").addEventListener("input", (e) => { if (e.target.dataset.av) C.alValues[e.target.dataset.av] = e.target.value; });
  $("#cdAlMethod").addEventListener("change", renderAlValues);
  $("#cdPrProduct").addEventListener("change", renderAlValues);
  $("#btnCdCoAdd").addEventListener("click", () => {
    const prods = (C.data ? C.data.products : []).filter((p) => p.uuid !== $("#cdPrProduct").value && !C.co.some((c) => c.product === p.uuid));
    if (!prods.length) { toast("Add the co-product as a product flow in step 2 first.", true); return; }
    C.co.push({ product: prods[0].uuid, amount: 1 }); renderCo();
  });

  // ------------------------------------------------------------------ processes
  function renderProcs() {
    const ps = C.data ? C.data.processes : [];
    if (!ps.some((p) => p.uuid === C.proc)) C.proc = ps.length ? ps[ps.length - 1].uuid : null;
    $("#cdProc").innerHTML = '<option value="">(new process)</option>' + ps.map((p) => opt(p.uuid, `${p.name} [${p.data.location}]${p.data.type === "treatment" ? ", waste treatment" : ""}`, p.uuid === C.proc)).join("");
    fillProcForm();
  }
  function fillProcForm() {
    const p = procOf(C.proc);
    const d = p ? p.data : { amount: 1, type: "production", location: "GLO", dq: {} };
    $("#cdPrName").value = p ? p.name : "";
    if (p) $("#cdPrProduct").value = d.product;
    $("#cdPrAmount").value = d.amount; $("#cdPrType").value = d.type; $("#cdPrLoc").value = d.location;
    $("#cdPrTech").value = d.technology || ""; $("#cdPrTime").value = d.time_period || ""; $("#cdPrData").value = d.data_type || "";
    $("#cdPrSrc").value = p ? p.source || "" : ""; $("#cdPrComment").value = d.comment || "";
    const dq = d.dq || {};
    $("#cdDqTer").value = dq.ter ?? ""; $("#cdDqGer").value = dq.ger ?? ""; $("#cdDqTir").value = dq.tir ?? ""; $("#cdDqP").value = dq.p ?? "";
    $("#btnCdProc").textContent = p ? "Save changes" : "Save process";
    C.prParams = JSON.parse(JSON.stringify(d.parameters || []));
    paramTable("cdPrParams", C.prParams);
    $("#cdPrParamBox").open = C.prParams.length > 0;
    C.co = JSON.parse(JSON.stringify(d.coproducts || []));
    C.alValues = { ...((d.allocation || {}).values || {}) };
    $("#cdAlMethod").value = (d.allocation || {}).method || "";
    $("#cdAlSrc").value = (d.allocation || {}).source || "";
    $("#cdCoBox").open = C.co.length > 0;
    renderCo();
    if (p) {
      const pr = C.data.products.find((x) => x.uuid === d.product);
      $("#cdXFor").textContent = `Lines of "${p.name}", per ${fmt(d.amount)} ${pr ? pr.data.unit : ""} of ${pr ? pr.name : "product"}${d.type === "treatment" ? " treated" : ""}.`;
    } else $("#cdXFor").textContent = "Choose or save a process in step 4 first.";
    renderExchanges(p);
    exchangeForm(null);
    $("#cdHistOut").innerHTML = "";
  }
  $("#cdProc").addEventListener("change", (e) => { C.proc = e.target.value || null; fillProcForm(); });
  $("#btnCdProcNew").addEventListener("click", () => { C.proc = null; $("#cdProc").value = ""; fillProcForm(); $("#cdPrName").focus(); });
  $("#btnCdProc").addEventListener("click", (e) => guard(e.target, async () => {
    needDb();
    const dq = { ter: num("cdDqTer"), ger: num("cdDqGer"), tir: num("cdDqTir"), p: num("cdDqP") };
    Object.keys(dq).forEach((k) => dq[k] === null && delete dq[k]);
    const r = await api("POST", `/api/custom/${C.db}/process`, { uuid: C.proc || undefined, name: val("cdPrName"), product: $("#cdPrProduct").value,
      amount: num("cdPrAmount"), type: $("#cdPrType").value, location: val("cdPrLoc"), technology: val("cdPrTech"), time_period: val("cdPrTime"),
      data_type: $("#cdPrData").value, source: val("cdPrSrc"), comment: val("cdPrComment"), dq, parameters: C.prParams,
      coproducts: C.co, allocation: C.co.length ? { method: $("#cdAlMethod").value, values: C.alValues, source: val("cdAlSrc") } : {} });
    toast(C.proc ? "Process saved." : "Process created. Now add its lines in step 5.");
    C.proc = r.uuid; await refreshAll();
    if (!procOf(C.proc).exchanges.length) $("#cdSec5").scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  $("#btnCdProcDel").addEventListener("click", (e) => guard(e.target, async () => {
    if (!C.proc) throw new Error("Choose a process first.");
    await api("POST", "/api/custom/delete", { uuid: C.proc });
    C.proc = null; toast("Process deleted."); await refreshAll();
  }));

  // ------------------------------------------------------------------ exchanges
  function uncText(e) {
    if (e.uncertainty === "pedigree") return `pedigree ${(e.pedigree || []).join(",")}`;
    if (e.uncertainty === "lognormal") return `lognormal, GSD ${fmt(Math.exp(e.p1))}`;
    if (e.uncertainty === "normal") return `normal, SD ${fmt(e.p1)} ${esc(e.ref_unit)}`;
    if (e.uncertainty === "triangular") return `triangular ${fmt(e.p1)} / ${fmt(e.p2)} / ${fmt(e.p3)}`;
    if (e.uncertainty === "uniform") return `uniform ${fmt(e.p1)} to ${fmt(e.p2)}`;
    return "-";
  }
  function exType(e) {
    return e.kind === "elementary" ? "emission or resource" : e.avoided ? "avoided product" : e.treatment ? "waste to treatment" : "input";
  }
  function renderExchanges(p) {
    const ex = p ? p.exchanges : [];
    $("#cdExchanges").innerHTML = !p ? empty(7, "Save the process in step 4 first.")
      : ex.length ? `<thead><tr><th>Type</th><th>Flow or supplier</th><th class="num">Entered</th><th class="num">In reference unit</th><th>Uncertainty</th><th>Source and revision</th><th></th></tr></thead><tbody>` +
        ex.map((e) => `<tr><td>${exType(e)}</td><td>${esc(e.label)}</td><td class="num">${fmt(e.amount)} ${esc(e.unit)}${e.formula ? `<br><span class="meta">= ${esc(e.formula)}</span>` : ""}</td><td class="num">${fmt(e.amount_ref)} ${esc(e.ref_unit)}</td><td>${uncText(e)}</td>
          <td>${esc(e.source || "")}<br><span class="meta">revision ${e.revision || 1}${e.author ? ", " + esc(e.author) : ""}</span></td>
          <td><button class="ghost" data-cdxedit="${e.id}">Edit</button><button class="ghost" data-cdxdel="${e.id}">Remove</button></td></tr>`).join("") + "</tbody>"
        : empty(7, "No line yet. Add inputs, waste, credits, emissions and resources below.");
  }
  function fillTargets(keep) {
    const kind = $("#cdXKind").value, src = $("#cdXSupSrc").value;
    $("#cdXSupSrc").hidden = kind === "elementary";
    const lib = kind === "elementary" || src === "library";
    $("#cdXSearchRow").hidden = !lib;
    $("#cdXSearch").placeholder = kind === "elementary" ? "Search emissions and resources, e.g. carbon dioxide, water, occupation" : "Search datasets of the library, e.g. electricity, lorry";
    let o = "";
    if (kind === "elementary") {
      o = C.meta.elementary_flows.map((f) => opt(f.uuid, `${f.name} (${f.data.compartment}/${f.data.subcompartment}, ${f.data.unit}), yours`)).join("") +
        C.found.filter((f) => f.uuid && !C.meta.elementary_flows.some((x) => x.uuid === f.uuid)).map((f) => opt(f.uuid, `${f.name} (${f.compartment}/${f.subcompartment}, ${f.unit})`)).join("");
    } else if (src === "custom") {
      const pname = (u) => { const x = C.data.products.find((q) => q.uuid === u); return x ? x.name : "?"; };
      o = (C.data ? C.data.processes : []).filter((p) => p.uuid !== C.proc || kind !== "avoided")
        .map((p) => opt(p.uuid, `${p.name} [${p.data.location}]${p.data.type === "treatment" ? ", waste treatment" : ""}${(p.data.coproducts || []).length ? ": " + pname(p.data.product) : ""}`) +
          (p.data.coproducts || []).map((c) => opt(`${p.uuid}/${c.product}`, `${p.name} [${p.data.location}]: ${pname(c.product)} (co-product)`)).join("")).join("");
    } else {
      o = C.found.filter((a) => a.id).map((a) => opt(a.id, `${a.name} [${a.location}] (${a.unit}, ${a.db})`)).join("");
    }
    if (keep && ![...new DOMParser().parseFromString(`<select>${o}</select>`, "text/html").querySelectorAll("option")].some((x) => x.value === keep.value))
      o = opt(keep.value, keep.label) + o;
    $("#cdXTarget").innerHTML = o || '<option value="">(nothing to choose yet: add a process or search the library)</option>';
    if (keep) $("#cdXTarget").value = keep.value;
    refUnit();
  }
  function refUnit() {
    const kind = $("#cdXKind").value, v = $("#cdXTarget").value;
    let u = "";
    if (C.editX && v === String(C.editX.target)) u = C.editX.ref_unit;
    else if (kind === "elementary") {
      const f = C.meta.elementary_flows.find((x) => x.uuid === v) || C.found.find((x) => x.uuid === v);
      u = f ? (f.data ? f.data.unit : f.unit) : "";
    } else if ($("#cdXSupSrc").value === "custom") {
      const [pu, cu] = v.split("/"), p = procOf(pu), pr = p && C.data.products.find((x) => x.uuid === (cu || p.data.product));
      u = pr ? pr.data.unit : "";
    } else {
      const a = C.found.find((x) => String(x.id) === v);
      u = a ? a.unit : "";
    }
    $("#cdXRefUnit").textContent = u ? `reference unit: ${u}` : "";
    if (u && !val("cdXUnit")) $("#cdXUnit").value = u;
  }
  function uncFields(e) {
    const t = $("#cdXUnc").value;
    const n = (id, ph, v) => `<input id="${id}" type="number" step="any" placeholder="${ph}" size="6" value="${v ?? ""}">`;
    const f = e && e.amount_ref ? e.amount / e.amount_ref : 1;   // back to the entered unit
    const ped = (e && e.pedigree) || [];
    $("#cdXUncFields").innerHTML = t === "pedigree" ? ["reliability", "completeness", "time", "geography", "technology"].map((x, i) => `<input id="cdPed${i}" type="number" min="1" max="5" placeholder="${x}" size="5" title="${x}: 1 good to 5 poor" value="${ped[i] ?? ""}">`).join("")
      : t === "lognormal" ? n("cdUG", "GSD, e.g. 1.5", e && e.utype === 1 && !e.pedigree ? +Math.exp(e.p1).toPrecision(6) : "")
        : t === "normal" ? n("cdUS", "SD", e && e.utype === 2 ? +(e.p1 * f).toPrecision(6) : "")
          : t === "triangular" ? n("cdUMin", "min", e && e.utype === 3 ? +(e.p1 * f).toPrecision(6) : "") + n("cdUMode", "most likely", e && e.utype === 3 ? +(e.p2 * f).toPrecision(6) : "") + n("cdUMax", "max", e && e.utype === 3 ? +(e.p3 * f).toPrecision(6) : "")
            : t === "uniform" ? n("cdUMin", "min", e && e.utype === 4 ? +(e.p1 * f).toPrecision(6) : "") + n("cdUMax", "max", e && e.utype === 4 ? +(e.p2 * f).toPrecision(6) : "") : "";
  }
  function exchangeForm(e) {
    C.editX = e || null;
    $("#cdXMode").textContent = e ? `Edit line: ${e.label}` : "Add a line";
    $("#btnCdX").textContent = e ? "Save changes" : "Add";
    $("#btnCdXCancel").hidden = !e;
    if (e) {
      $("#cdXKind").value = e.kind === "elementary" ? "elementary" : e.avoided ? "avoided" : "technosphere";
      $("#cdXSupSrc").value = /^\d+$/.test(String(e.target)) ? "library" : "custom";
      fillTargets({ value: String(e.target), label: e.label });
      $("#cdXAmount").value = e.formula || e.amount; $("#cdXUnit").value = e.unit;
      $("#cdXUnc").value = e.uncertainty || "none";
      $("#cdXSrc").value = e.source || ""; $("#cdXComment").value = e.comment || "";
      uncFields(e);
      $("#cdSec5 .subpanel").scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      $("#cdXAmount").value = ""; $("#cdXSrc").value = ""; $("#cdXComment").value = ""; $("#cdXUnc").value = "none";
      uncFields();
    }
  }
  $("#cdXKind").addEventListener("change", () => { $("#cdXUnit").value = ""; fillTargets(); });
  $("#cdXSupSrc").addEventListener("change", () => { $("#cdXUnit").value = ""; fillTargets(); });
  $("#cdXTarget").addEventListener("change", () => { $("#cdXUnit").value = ""; refUnit(); });
  $("#cdXUnc").addEventListener("change", () => uncFields());
  $("#btnCdXCancel").addEventListener("click", () => exchangeForm(null));
  $("#btnCdXSearch").addEventListener("click", (e) => guard(e.target, async () => {
    const q = encodeURIComponent(val("cdXSearch"));
    C.found = $("#cdXKind").value === "elementary" ? (await api("GET", `/api/flows?q=${q}`)).results : (await api("GET", `/api/search?q=${q}`)).results;
    fillTargets();
    toast(C.found.length ? `${C.found.length} found: choose one in the list.` : "Nothing found. Try a shorter word.", !C.found.length);
  }));
  $("#cdXSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btnCdXSearch").click(); });
  $("#btnCdX").addEventListener("click", (e) => guard(e.target, async () => {
    if (!C.proc) throw new Error("Save the process in step 4 first.");
    const kind = $("#cdXKind").value, t = $("#cdXTarget").value;
    if (!t) throw new Error("Choose the supplier or the flow.");
    const b = { process: C.proc, id: C.editX ? C.editX.id : undefined, kind: kind === "elementary" ? "elementary" : "technosphere",
      avoided: kind === "avoided", supplier: t, flow: t, unit: val("cdXUnit"), uncertainty: $("#cdXUnc").value,
      source: val("cdXSrc"), comment: val("cdXComment"), author: C.data.database.author || "" };
    const amt = val("cdXAmount");
    if (amt !== "" && !Number.isNaN(Number(amt))) b.amount = Number(amt); else b.formula = amt;
    if (b.uncertainty === "pedigree") b.pedigree = [0, 1, 2, 3, 4].map((i) => num("cdPed" + i));
    if (b.uncertainty === "lognormal") b.gsd = num("cdUG");
    if (b.uncertainty === "normal") b.sd = num("cdUS");
    if (b.uncertainty === "triangular" || b.uncertainty === "uniform") { b.min = num("cdUMin"); b.max = num("cdUMax"); }
    if (b.uncertainty === "triangular") b.mode = num("cdUMode");
    await api("POST", "/api/custom/exchange", b);
    toast(C.editX ? "Line saved." : "Line added.");
    await loadDb(); if (typeof refreshStatus === "function") await refreshStatus();
  }));
  $("#cdExchanges").addEventListener("click", (e) => {
    const ed = e.target.closest("[data-cdxedit]");
    if (ed) { exchangeForm(procOf(C.proc).exchanges.find((x) => x.id === Number(ed.dataset.cdxedit))); return; }
    const b = e.target.closest("[data-cdxdel]"); if (!b) return;
    guard(b, async () => { await api("POST", "/api/custom/exchange/delete", { process: C.proc, id: Number(b.dataset.cdxdel) }); toast("Line removed."); await loadDb(); });
  });


  // ------------------------------------------------------------------ supply chain diagram
  const NW = 190, NH = 50;
  function graph() {
    const procs = C.data ? C.data.processes : [];
    const nodes = {}, edges = [];
    procs.forEach((p) => {
      const nem = p.exchanges.filter((e) => e.kind === "elementary").length;
      const pr = C.data.products.find((x) => x.uuid === p.data.product);
      nodes[p.uuid] = { id: p.uuid, label: p.name, sub: `${fmt(p.data.amount)} ${pr ? pr.data.unit : ""} ${pr ? pr.name : ""}${(p.data.coproducts || []).length ? ` + ${p.data.coproducts.length} co-product(s)` : ""}`,
        sub2: `${nem} emission(s) or resource(s)${p.data.type === "treatment" ? ", waste treatment" : ""}`, pos: p.data.layout, custom: true };
    });
    procs.forEach((p) => p.exchanges.filter((e) => e.kind === "technosphere").forEach((e) => {
      const t = String(e.target);
      let from;
      if (/^\d+$/.test(t)) {
        from = "lib:" + t;
        if (!nodes[from]) nodes[from] = { id: from, label: e.label.replace(/\s*\([^)]*\)\s*$/, ""), sub: `library, ${e.ref_unit}`, sub2: "", custom: false, target: t, tlabel: e.label };
      } else from = t.split("/")[0];
      if (nodes[from]) edges.push({ from, to: p.uuid, e });
    }));
    return { nodes, edges };
  }
  function autoPos(g, force) {
    const ids = Object.keys(g.nodes), lvl = {};
    ids.forEach((i) => (lvl[i] = 0));
    for (let k = 0; k < ids.length; k++) g.edges.forEach((ed) => { if (lvl[ed.to] < lvl[ed.from] + 1 && lvl[ed.from] + 1 < ids.length) lvl[ed.to] = lvl[ed.from] + 1; });
    const col = {};
    ids.forEach((i) => {
      const n = g.nodes[i];
      const known = n.custom ? n.pos : C.libPos[i];
      if (known && !force) { n.x = known[0]; n.y = known[1]; return; }
      const c = lvl[i]; col[c] = (col[c] || 0) + 1;
      n.x = 20 + c * (NW + 70); n.y = 20 + (col[c] - 1) * (NH + 30);
      if (!n.custom) C.libPos[i] = [n.x, n.y];
    });
  }
  function edgePath(a, b) {
    const x1 = a.x + NW, y1 = a.y + NH / 2, x2 = b.x, y2 = b.y + NH / 2;
    if (a === b) return `M${a.x + NW - 30},${a.y} C${a.x + NW + 40},${a.y - 50} ${a.x + 30},${a.y - 50} ${a.x + 30},${a.y}`;
    const back = x2 < x1 + 10, dx = Math.max(40, Math.abs(x2 - x1) / 2);
    return back ? `M${x1},${y1} C${x1 + 60},${y1 + 90} ${x2 - 60},${y2 + 90} ${x2},${y2}` : `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
  }
  function drawDiagram(force) {
    const svg = $("#cdCanvas");
    if (!C.data || !C.data.processes.length) { svg.innerHTML = '<text x="20" y="40" class="cd-elab">Your processes appear here once you create them in step 4.</text>'; svg.setAttribute("viewBox", "0 0 800 120"); svg.style.height = "120px"; return; }
    const g = graph(); C.g = g; autoPos(g, force);
    let out = '<defs><marker id="cdArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="var(--ink-soft)"/></marker></defs>';
    g.edges.forEach((ed, i) => {
      const a = g.nodes[ed.from], b = g.nodes[ed.to], e = ed.e;
      const cls = e.avoided ? "credit" : e.treatment ? "waste" : "";
      const d = edgePath(a, b);
      out += `<path class="cd-edge ${cls}" d="${d}" marker-end="url(#cdArrow)" data-edge="${i}"><title>${esc(`${fmt(e.amount)} ${e.unit}${e.formula ? " = " + e.formula : ""}: ${e.label} to ${b.label}. Click to edit.`)}</title></path>`;
      const mx = (a.x + NW + b.x) / 2, my = (a.y + b.y) / 2 + NH / 2 - 6 + (a === b ? -55 : 0);
      out += `<text class="cd-elab" x="${mx}" y="${my}" text-anchor="middle">${esc(`${e.avoided ? "avoided " : ""}${fmt(e.amount)} ${e.unit}`)}</text>`;
    });
    Object.values(g.nodes).forEach((n) => {
      const cls = `cd-node ${n.custom ? "" : "lib"} ${n.id === C.proc ? "sel" : ""} ${C.connect === n.id ? "src" : ""}`;
      out += `<g class="${cls}" data-node="${esc(n.id)}" transform="translate(${n.x},${n.y})" style="cursor:${C.connect ? "crosshair" : "grab"}"><title>${esc(n.label)}</title><rect width="${NW}" height="${NH}" rx="8"/>
        <text x="10" y="17">${esc(n.label.slice(0, 27))}</text><text class="sub" x="10" y="31">${esc(n.sub.slice(0, 34))}</text><text class="sub" x="10" y="43">${esc((n.sub2 || "").slice(0, 34))}</text></g>`;
    });
    svg.innerHTML = out;
    const xs = Object.values(g.nodes).map((n) => n.x), ys = Object.values(g.nodes).map((n) => n.y);
    const W = Math.max(760, Math.max(...xs) + NW + 40), H = Math.max(200, Math.max(...ys) + NH + 80);
    const y0 = Math.min(0, Math.min(...ys) - 60);
    svg.setAttribute("viewBox", `0 ${y0} ${W} ${H - y0}`);
    svg.style.height = Math.min(640, H - y0) + "px"; svg.style.minWidth = W + "px";
  }
  function svgPoint(evt) {
    const svg = $("#cdCanvas"), pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }
  let drag = null;
  $("#cdCanvas").addEventListener("pointerdown", (evt) => {
    const gEl = evt.target.closest("[data-node]"); if (!gEl || !C.g) return;
    const n = C.g.nodes[gEl.dataset.node], p0 = svgPoint(evt);
    drag = { n, dx: p0.x - n.x, dy: p0.y - n.y, moved: false, sx: p0.x, sy: p0.y };
    $("#cdCanvas").setPointerCapture(evt.pointerId);
  });
  $("#cdCanvas").addEventListener("pointermove", (evt) => {
    if (!drag) return;
    const p = svgPoint(evt);
    if (Math.abs(p.x - drag.sx) + Math.abs(p.y - drag.sy) > 4) drag.moved = true;
    if (!drag.moved) return;
    drag.n.x = Math.max(0, p.x - drag.dx); drag.n.y = p.y - drag.dy;
    if (drag.n.custom) { const pr = procOf(drag.n.id); if (pr) pr.data.layout = [drag.n.x, drag.n.y]; } else C.libPos[drag.n.id] = [drag.n.x, drag.n.y];
    if (!drag.raf) drag.raf = requestAnimationFrame(() => { if (drag) { drag.raf = null; drawDiagram(); } });
  });
  $("#cdCanvas").addEventListener("pointerup", (evt) => {
    if (!drag) return;
    const d = drag; drag = null;
    if (d.moved) {
      if (d.n.custom) api("POST", "/api/custom/layout", { uuid: d.n.id, x: Math.round(d.n.x), y: Math.round(d.n.y) }).catch(() => {});
      return;
    }
    nodeClick(d.n);
  });
  function selectProcess(uid) {
    C.proc = uid; $("#cdProc").value = uid; fillProcForm(); drawDiagram();
  }
  function nodeClick(n) {
    if (C.connect === null && $("#btnCdConnect").classList.contains("on")) {
      C.connect = n.id; $("#cdConnectHint").textContent = `Supplier: ${n.label}. Now click the process that uses it.`; drawDiagram(); return;
    }
    if (C.connect) {
      if (!n.custom) { toast("Click one of your processes: library datasets cannot be changed here.", true); return; }
      const src = C.g.nodes[C.connect];
      connectMode(false);
      selectProcess(n.id);
      $("#cdXKind").value = "technosphere";
      if (src.custom) { $("#cdXSupSrc").value = "custom"; fillTargets(); $("#cdXTarget").value = src.id; }
      else { $("#cdXSupSrc").value = "library"; fillTargets({ value: src.target, label: src.tlabel }); }
      $("#cdXUnit").value = ""; refUnit();
      $("#cdXMode").textContent = `New input of "${n.label}" from "${src.label}": enter the amount`;
      $("#cdSec5 .subpanel").scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => $("#cdXAmount").focus(), 300);
      return;
    }
    if (n.custom) { selectProcess(n.id); toast(`Selected: ${n.label}. Its details are in steps 4 and 5.`); }
  }
  function connectMode(on) {
    $("#btnCdConnect").classList.toggle("on", on);
    $("#btnCdConnect").textContent = on ? "Cancel connecting" : "Connect";
    C.connect = null;
    $("#cdConnectHint").textContent = on ? "Click the supplier first (one of your processes or a library dataset)." : "";
    drawDiagram();
  }
  $("#btnCdConnect").addEventListener("click", () => connectMode(!$("#btnCdConnect").classList.contains("on")));
  $("#btnCdAutoLayout").addEventListener("click", () => guard(null, async () => {
    C.libPos = {}; drawDiagram(true);
    await Promise.all(Object.values(C.g.nodes).filter((n) => n.custom).map((n) => {
      const pr = procOf(n.id); if (pr) pr.data.layout = [n.x, n.y];
      return api("POST", "/api/custom/layout", { uuid: n.id, x: Math.round(n.x), y: Math.round(n.y) });
    }));
  }));
  $("#cdCanvas").addEventListener("click", (evt) => {
    const pe = evt.target.closest("[data-edge]"); if (!pe || !C.g) return;
    const ed = C.g.edges[Number(pe.dataset.edge)];
    selectProcess(ed.to);
    exchangeForm(procOf(ed.to).exchanges.find((x) => x.id === ed.e.id));
  });

  // ------------------------------------------------------------------ methods and factors
  const customMethod = (mid) => C.meta.methods.find((m) => m.id === Number(mid));
  function fillMethods() {
    const ms = [...C.meta.methods.map((m) => ({ ...m, mine: true })), ...(S.methods || []).filter((m) => !customMethod(m.id))];
    const cur = $("#cdFMethod").value;
    $("#cdFMethod").innerHTML = ms.map((m) => opt(m.id, `${m.mine ? "Yours: " : ""}${m.family} | ${m.category}${m.indicator && m.indicator !== m.category ? " | " + m.indicator : ""} (${m.unit || ""})`, String(m.id) === cur)).join("")
      || '<option value="">No impact method yet: create one above</option>';
    methodChanged();
  }
  function methodChanged() {
    const m = customMethod($("#cdFMethod").value);
    $("#cdMScopeRow").hidden = !m; $("#cdFSearchRow").hidden = !m;
    if (m) { $("#cdMScopeEdit").value = m.unlisted; $("#cdMReasonEdit").value = m.unlisted_reason || ""; }
    fillFlows();
  }
  function fillFlows(sel) {
    const m = customMethod($("#cdFMethod").value);
    const lib = m ? C.flowFound.filter((f) => !C.meta.elementary_flows.some((x) => x.uuid === f.uuid)).map((f) => opt(f.uuid, `${f.name} (${f.compartment}/${f.subcompartment}, ${f.unit})`)) : [];
    $("#cdFFlow").innerHTML = C.meta.elementary_flows.map((f) => opt(f.uuid, `${f.name} (${f.data.compartment}/${f.data.subcompartment}, ${f.data.unit}), yours`)).join("") + lib.join("")
      || `<option value="">${m ? "Search a library flow below, or create a flow in step 3" : "Create a flow in step 3 first"}</option>`;
    if (sel) $("#cdFFlow").value = sel;
    flowUnit();
  }
  function flowUnit() {
    const v = $("#cdFFlow").value;
    const f = C.meta.elementary_flows.find((x) => x.uuid === v) || C.flowFound.find((x) => x.uuid === v);
    $("#cdFUnit").value = f ? (f.data ? f.data.unit : f.unit) : "";
  }
  $("#cdFMethod").addEventListener("change", methodChanged);
  $("#cdFFlow").addEventListener("change", flowUnit);
  $("#cdFStatus").addEventListener("change", () => {
    const na = $("#cdFStatus").value === "not_applicable";
    $("#cdFValue").disabled = na; $("#cdFUnit").disabled = na;
    $("#cdFSrc").placeholder = na ? "Reason why the category does not apply" : "Source of the factor";
  });
  $("#btnCdMethod").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/method", { family: val("cdMFam"), category: val("cdMCat"), indicator: val("cdMInd"), unit: val("cdMUnit"),
      source: val("cdMSrc"), unlisted: $("#cdMScope").value, unlisted_reason: val("cdMReason") });
    if (typeof refreshStatus === "function") await refreshStatus();
    await loadMeta(); $("#cdFMethod").value = r.method_id; methodChanged(); toast("Impact category created. Now give the factors.");
  }));
  $("#btnCdMScope").addEventListener("click", (e) => guard(e.target, async () => {
    await api("POST", "/api/custom/method/scope", { method_id: Number($("#cdFMethod").value), unlisted: $("#cdMScopeEdit").value, unlisted_reason: val("cdMReasonEdit") });
    toast("Method saved."); await loadMeta();
  }));
  $("#btnCdMDel").addEventListener("click", (e) => guard(e.target, async () => {
    await api("POST", "/api/custom/method/delete", { method_id: Number($("#cdFMethod").value) });
    if (typeof refreshStatus === "function") await refreshStatus();
    toast("Method deleted."); await loadMeta();
  }));
  $("#btnCdFSearch").addEventListener("click", (e) => guard(e.target, async () => {
    C.flowFound = (await api("GET", `/api/flows?q=${encodeURIComponent(val("cdFSearch"))}`)).results;
    fillFlows();
  }));
  $("#btnCdFactor").addEventListener("click", (e) => guard(e.target, async () => {
    const st = $("#cdFStatus").value;
    await api("POST", "/api/custom/factor", { method_id: Number($("#cdFMethod").value), flow_uuid: $("#cdFFlow").value, status: st,
      value: st === "value" ? num("cdFValue") : null, unit: val("cdFUnit"), source: st === "value" ? val("cdFSrc") : "", comment: st === "value" ? "" : val("cdFSrc") });
    $("#cdFValue").value = ""; $("#cdFSrc").value = ""; toast("Factor saved."); await factorTable(); await loadDb();
  }));
  async function factorTable() {
    const mids = [...new Set([...(S.selectedMethods || []), ...C.meta.methods.map((m) => m.id)])];
    if (!mids.length) { $("#cdFactors").innerHTML = empty(6, "Choose impact categories in step 4, or create your own method above."); return; }
    const r = await api("POST", "/api/custom/factors", { method_ids: mids });
    const lab = { value: "factor", not_applicable: "does not apply", outside_scope: "no effect (method scope)",
      missing: '<span class="danger">unknown: give a factor or say why it does not apply</span>' };
    C.ftRows = r.rows;
    $("#cdFactors").innerHTML = r.rows.length ? `<thead><tr><th>Impact category</th><th>Flow</th><th>Status</th><th class="num">Factor</th><th>Source or reason</th><th></th></tr></thead><tbody>` +
      r.rows.map((x, i) => `<tr><td>${esc(x.family)} | ${esc(x.category)}</td><td>${esc(x.flow)} (${esc(x.compartment)})${x.custom_flow ? ", yours" : ""}</td><td>${lab[x.status]}</td>
        <td class="num">${x.status === "value" ? `${fmt(x.value)} ${esc(x.method_unit)}/${esc(x.flow_unit)}` : ""}</td><td>${esc(x.source || x.comment || "")}</td>
        <td>${x.source === "installed method" ? "" : `<button class="ghost" data-cdfedit="${i}">${x.status === "missing" ? "Decide" : "Edit"}</button>`}</td></tr>`).join("") + "</tbody>"
      : empty(6, "No flow of your own yet.");
  }
  $("#cdFactors").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cdfedit]"); if (!b) return;
    const x = C.ftRows[Number(b.dataset.cdfedit)];
    $("#cdFMethod").value = x.method_id; methodChanged();
    if (!x.custom_flow && !C.flowFound.some((f) => f.uuid === x.flow_uuid))
      C.flowFound.push({ uuid: x.flow_uuid, name: x.flow, compartment: x.compartment.split("/")[0], subcompartment: x.compartment.split("/")[1] || "", unit: x.flow_unit });
    fillFlows(x.flow_uuid);
    $("#cdFStatus").value = x.status === "not_applicable" ? "not_applicable" : "value"; $("#cdFStatus").dispatchEvent(new Event("change"));
    $("#cdFValue").value = x.status === "value" ? (x.value_entered ?? x.value ?? "") : "";
    if (x.unit_entered) $("#cdFUnit").value = x.unit_entered;
    $("#cdFSrc").value = x.status === "value" ? x.source || "" : x.comment || "";
    $("#cdFMethod").scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("#btnCdFTable").addEventListener("click", (e) => guard(e.target, factorTable));

  // ------------------------------------------------------------------ database, check, use, history, example
  $("#cdDb").addEventListener("change", (e) => guard(null, async () => { C.db = Number(e.target.value) || null; C.proc = null; await loadDb(); }));
  $("#btnCdNewDb").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/database", { name: val("cdNewName"), description: val("cdNewDesc"), author: val("cdNewAuthor"),
      geography: val("cdNewGeo"), reference_period: val("cdNewPeriod"), licence: val("cdNewLic") });
    C.db = r.db_id; $("#cdNewName").value = ""; toast("Custom database created. Next: its product flows (step 2).");
    await refreshAll(); $("#cdSec2").scrollIntoView({ behavior: "smooth", block: "start" });
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
    C.check = await api("GET", `/api/custom/${C.db}/check`);
    const r = C.check, cls = { error: "danger", warning: "warn", info: "hint" };
    $("#cdCheckOut").innerHTML = `<p class="${r.complete ? "ok" : "danger"}">${r.complete ? "The database can be calculated." : `${r.errors || 0} error(s) to correct.`} ${r.processes} process(es), ${r.warnings || 0} warning(s).</p>` +
      (r.findings.length ? "<ul>" + r.findings.map((f) => `<li class="${cls[f.level]}">${esc(f.message)}</li>`).join("") + "</ul>" : "");
    renderSteps();
  }));
  $("#btnCdUse").addEventListener("click", (e) => guard(e.target, async () => {
    const p = procOf(C.proc);
    if (!p || !p.ref_id) throw new Error("Choose a saved process in step 4 first.");
    if (!S.model) throw new Error("Open or create a model first (step 2).");
    const { model } = await api("POST", `/api/models/${S.model.id}/inputs`, { kind: "activity", ref_id: p.ref_id, amount: p.data.amount, label: "" });
    S.model = model; S.result = null;
    if (typeof markSteps === "function") markSteps();
    toast(`Added "${p.name}" to ${S.model.name}. Set its amount in step 3.`);
    go("inventory");
  }));
  $("#btnCdHist").addEventListener("click", (e) => guard(e.target, async () => {
    if (!C.proc) throw new Error("Choose a process in step 4 first.");
    const h = (await api("GET", `/api/custom/history?item=${encodeURIComponent(C.proc)}`)).history;
    $("#cdHistOut").innerHTML = h.length ? `<table><thead><tr><th>Time (UTC)</th><th>Change</th><th>Author</th><th>Details</th></tr></thead><tbody>` +
      h.map((x) => `<tr><td>${esc((x.time || "").replace("T", " ").slice(0, 19))}</td><td>${esc(x.action)}</td><td>${esc(x.author || "")}</td><td class="meta">${esc(x.data ? Object.entries(x.data).filter(([k, v]) => v !== null && v !== "" && typeof v !== "object").map(([k, v]) => `${k}: ${v}`).join("; ").slice(0, 220) : "")}</td></tr>`).join("") + "</tbody></table>"
      : '<p class="hint">No change recorded yet.</p>';
  }));
  $("#btnCdExample").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/custom/example", {});
    C.db = r.db_id; C.proc = r.process;
    if (typeof refreshStatus === "function") await refreshStatus();
    await loadMeta();
    $("#cdFMethod").value = r.method_id; methodChanged();
    toast("The example is ready: bread made with flour and electricity, its waste sent to landfill. Look through steps 1 to 7.");
    $("#cdSec4").scrollIntoView({ behavior: "smooth", block: "start" });
  }));

  // entry points from other steps
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-gocustom]"); if (!b) return;
    e.preventDefault();
    go("tools"); showToolTab("custom");
  });

  uncFields();
  const _show = showToolTab;
  showToolTab = function (t) {
    _show.apply(this, arguments);
    if (t === "custom") {
      if (!(S.status && S.status.project)) { toast("Open or create a project first (step 1).", true); return; }
      guard(null, loadMeta);
    }
  };
})();
