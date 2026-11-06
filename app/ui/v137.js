/* Cyclia 1.3.7: ILCD+EPD export, PSILCA/SOCA import, AWARE monthly and GIS, SQI aggregation, MFA builder and MFA-LCA link,
   staging import, comparison kit. */
(function () {
  $("#btnEpdIlcd").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await exportTo("/api/export/ilcd-epd", `${S.model ? S.model.name : "EPD"} ILCD+EPD.zip`, "zip", calcBody());
    if (!r) return;
    $("#epdIlcdOut").innerHTML = `Schema check passed. ${r.indicators.length} indicators in modules ${esc(r.modules.join(", "))}.` +
      (r.warnings.length ? ` <span class="warn">${r.warnings.map(esc).join(" ")}</span>` : "") +
      " Open the zip in the EPD Editor to add contacts and the review before upload.";
  }));
})();

/* ---------------- MFA builder ---------------- */
(function () {
  let D = null;           // the definition being edited
  const kindOf = (p) => (p.stock ? "stock" : p.sink ? "sink" : "process");
  function read() {
    try { D = JSON.parse($("#mfaDef").value || "{}"); } catch (e) { throw new Error("The JSON definition is not valid: " + e.message); }
    D.processes = D.processes || []; D.flows = D.flows || []; D.inflows = D.inflows || []; D.years = D.years || [2020, 2050];
    D.layout = D.layout || {};
    autoLayout();
  }
  function write() { $("#mfaDef").value = JSON.stringify(D, null, 2); }
  function autoLayout() {
    const ids = D.processes.map((p) => p.id);
    const depth = {}; ids.forEach((i) => (depth[i] = 0));
    for (let k = 0; k < ids.length; k++) D.flows.forEach((f) => { if (depth[f.to] !== undefined && depth[f.from] !== undefined && depth[f.to] < depth[f.from] + 1 && depth[f.from] + 1 < ids.length) depth[f.to] = depth[f.from] + 1; });
    const perCol = {};
    D.processes.forEach((p) => {
      if (D.layout[p.id]) return;
      const c = depth[p.id] || 0; perCol[c] = (perCol[c] || 0) + 1;
      D.layout[p.id] = [40 + c * 170, 30 + (perCol[c] - 1) * 90];
    });
  }
  function draw() {
    const svg = $("#mfaCanvas");
    const pos = (id) => D.layout[id] || [20, 20];
    const W = 130, H = 46;
    let s = '<defs><marker id="mfaArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="var(--ink-soft, #555)"/></marker></defs>';
    D.flows.forEach((f) => {
      const [x1, y1] = pos(f.from), [x2, y2] = pos(f.to);
      const ax = x1 + W, ay = y1 + H / 2, bx = x2, by = y2 + H / 2;
      const back = bx <= ax;
      const d = back ? `M${ax},${ay} C${ax + 60},${ay + 80} ${bx - 60},${by + 80} ${bx},${by}` : `M${ax},${ay} C${(ax + bx) / 2},${ay} ${(ax + bx) / 2},${by} ${bx},${by}`;
      s += `<path d="${d}" fill="none" stroke="${back ? "var(--spruce, #2f6b4f)" : "var(--ink-soft, #555)"}" stroke-width="${1 + 3 * Number(f.share || 0)}" marker-end="url(#mfaArrow)" opacity="0.8"/>`;
      s += `<text x="${(ax + bx) / 2}" y="${(ay + by) / 2 + (back ? 48 : -4)}" font-size="11" text-anchor="middle" fill="var(--ink-soft, #555)">${(100 * Number(f.share || 0)).toFixed(0)} %</text>`;
    });
    D.inflows.forEach((e) => { const [x, y] = pos(e.to); s += `<path d="M${x - 34},${y + H / 2} L${x},${y + H / 2}" stroke="var(--amber, #b7791f)" stroke-width="3" marker-end="url(#mfaArrow)"/>`; });
    D.processes.forEach((p) => {
      const [x, y] = pos(p.id), k = kindOf(p);
      const fill = k === "stock" ? "var(--spruce-soft, #dcebe3)" : k === "sink" ? "var(--panel-2, #eee)" : "var(--panel, #fff)";
      s += `<g class="mfa-node" data-node="${esc(p.id)}" transform="translate(${x},${y})" style="cursor:grab"><rect width="${W}" height="${H}" rx="${k === "sink" ? 2 : 8}" fill="${fill}" stroke="var(--rule-strong, #999)"/>
        <text x="8" y="18" font-size="12" font-weight="600" fill="var(--ink, #222)">${esc((p.name || p.id).slice(0, 18))}</text>
        <text x="8" y="35" font-size="10" fill="var(--ink-soft, #555)">${k}${k === "stock" && p.lifetime ? `, ${esc(p.lifetime.type)} ${esc(p.lifetime.mean ?? p.lifetime.scale ?? "")} a` : ""}</text></g>`;
    });
    const xs = D.processes.map((p) => pos(p.id)[0]), ys = D.processes.map((p) => pos(p.id)[1]);
    svg.setAttribute("viewBox", `-50 -10 ${Math.max(900, Math.max(0, ...xs) + 200)} ${Math.max(300, Math.max(0, ...ys) + 140)}`);
    svg.innerHTML = s;
  }
  function tables() {
    $("#mfaY0").value = D.years[0]; $("#mfaY1").value = D.years[1];
    const opts = (sel) => D.processes.map((p) => `<option value="${esc(p.id)}" ${p.id === sel ? "selected" : ""}>${esc(p.name || p.id)}</option>`).join("");
    $("#mfaProd").innerHTML = '<option value="">(none)</option>' + opts(D.production_process);
    $("#mfaRec").value = (D.recycling_processes || []).join(", ");
    $("#mfaProcs").innerHTML = D.processes.map((p, i) => { const lt = p.lifetime || {}; const k = kindOf(p);
      return `<tr data-i="${i}"><td><input data-pf="id" value="${esc(p.id)}" size="8"></td><td><input data-pf="name" value="${esc(p.name || "")}"></td>
        <td><select data-pf="kind">${["process", "stock", "sink"].map((x) => `<option ${x === k ? "selected" : ""}>${x}</option>`).join("")}</select></td>
        <td>${k === "stock" ? `<select data-pf="lt">${["fixed", "normal", "weibull"].map((x) => `<option ${x === (lt.type || "fixed") ? "selected" : ""}>${x}</option>`).join("")}</select>` : ""}</td>
        <td>${k === "stock" ? `<input data-pf="a" type="number" step="any" value="${esc(lt.type === "weibull" ? lt.shape ?? "" : lt.mean ?? "")}" size="5">` : ""}</td>
        <td>${k === "stock" && lt.type && lt.type !== "fixed" ? `<input data-pf="b" type="number" step="any" value="${esc(lt.type === "weibull" ? lt.scale ?? "" : lt.sd ?? "")}" size="5">` : ""}</td>
        <td><button class="ghost" data-delproc="${i}">Remove</button></td></tr>`; }).join("");
    $("#mfaFlows").innerHTML = D.flows.map((f, i) => `<tr data-i="${i}"><td><select data-ff="from">${opts(f.from)}</select></td><td><select data-ff="to">${opts(f.to)}</select></td>
      <td class="num"><input data-ff="share" type="number" step="0.01" min="0" max="1" value="${esc(f.share)}" size="5"></td><td><button class="ghost" data-delflow="${i}">Remove</button></td></tr>`).join("");
    $("#mfaInflows").innerHTML = D.inflows.map((e, i) => `<tr data-i="${i}"><td><select data-if="to">${opts(e.to)}</select></td>
      <td><input data-if="values" class="grow" value="${esc(Object.entries(e.values || {}).map(([y, v]) => `${y}: ${v}`).join("; "))}"></td><td><button class="ghost" data-delinflow="${i}">Remove</button></td></tr>`).join("");
    const sums = {}; D.flows.forEach((f) => (sums[f.from] = (sums[f.from] || 0) + Number(f.share || 0)));
    const bad = D.processes.filter((p) => !p.sink && Math.abs((sums[p.id] || 0) - 1) > 1e-6).map((p) => `${p.name || p.id} ${((sums[p.id] || 0) * 100).toFixed(0)} %`);
    $("#mfaShareCheck").innerHTML = bad.length ? `<span class="warn">Outgoing shares must add up to 100 %: ${bad.map(esc).join(", ")}</span>` : '<span class="ok">Every process sends 100 % onwards.</span>';
    links();
  }
  function refresh() { autoLayout(); write(); draw(); tables(); }
  window.mfaBuilderLoad = function () { read(); draw(); tables(); };
  // load the builder when the JSON has been filled (example button, first opening of the tab)
  async function whenFilled(prev) {
    for (let k = 0; k < 50; k++) {
      const v = $("#mfaDef").value.trim();
      if (v && v !== prev) { try { mfaBuilderLoad(); } catch (e) { toast(e.message, true); } return; }
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  $("#btnMfaExample").addEventListener("click", () => whenFilled($("#mfaDef").value.trim()));
  const _show = showToolTab;
  showToolTab = function (t) { _show.apply(this, arguments); if (t === "mfa") whenFilled(D ? "__builder__" : ""); };
  $("#btnMfaFromJson").addEventListener("click", (e) => guard(e.target, () => { D = null; mfaBuilderLoad(); }));
  $("#btnMfaNew").addEventListener("click", () => {
    D = { name: "New material system", years: [2025, 2060], production_process: "prod", recycling_processes: [],
      processes: [{ id: "prod", name: "Production" }, { id: "use", name: "In use", stock: true, lifetime: { type: "fixed", mean: 30 } }, { id: "loss", name: "Landfill", sink: true }],
      inflows: [{ to: "prod", values: { 2025: 100 } }], flows: [{ from: "prod", to: "use", share: 1 }, { from: "use", to: "loss", share: 1 }], layout: {} };
    refresh();
  });
  $("#btnMfaAddProc").addEventListener("click", () => { if (!D) read(); let n = D.processes.length + 1; while (D.processes.some((p) => p.id === "p" + n)) n++; D.processes.push({ id: "p" + n, name: "Process " + n }); refresh(); });
  $("#btnMfaAddFlow").addEventListener("click", () => { if (!D) read(); if (D.processes.length < 2) return toast("Add two processes first.", true); D.flows.push({ from: D.processes[0].id, to: D.processes[1].id, share: 1 }); refresh(); });
  $("#btnMfaAddInflow").addEventListener("click", () => { if (!D) read(); if (!D.processes.length) return; D.inflows.push({ to: D.processes[0].id, values: { [D.years[0]]: 100 } }); refresh(); });
  $("#mfaBuilder").addEventListener("change", (e) => {
    if (!D) read();
    const t = e.target, tr = t.closest("tr");
    if (t.id === "mfaY0" || t.id === "mfaY1") D.years = [Number($("#mfaY0").value), Number($("#mfaY1").value)];
    if (t.id === "mfaProd") D.production_process = t.value || undefined;
    if (t.id === "mfaRec") D.recycling_processes = t.value.split(",").map((x) => x.trim()).filter(Boolean);
    if (t.dataset.pf) {
      const p = D.processes[Number(tr.dataset.i)], k = t.dataset.pf;
      if (k === "id") {
        const old = p.id, nw = t.value.trim();
        if (!nw || D.processes.some((x) => x !== p && x.id === nw)) { toast("Ids must be unique and not empty.", true); return tables(); }
        p.id = nw; D.flows.forEach((f) => { if (f.from === old) f.from = nw; if (f.to === old) f.to = nw; });
        D.inflows.forEach((x) => { if (x.to === old) x.to = nw; }); D.layout[nw] = D.layout[old]; delete D.layout[old];
        if (D.production_process === old) D.production_process = nw;
        D.recycling_processes = (D.recycling_processes || []).map((r) => (r === old ? nw : r));
      } else if (k === "name") p.name = t.value;
      else if (k === "kind") { delete p.stock; delete p.sink; if (t.value === "stock") { p.stock = true; p.lifetime = p.lifetime || { type: "fixed", mean: 30 }; } if (t.value === "sink") { p.sink = true; D.flows = D.flows.filter((f) => f.from !== p.id); } if (t.value !== "stock") delete p.lifetime; }
      else if (k === "lt") p.lifetime = t.value === "weibull" ? { type: "weibull", shape: 2, scale: 30 } : t.value === "normal" ? { type: "normal", mean: 30, sd: 10 } : { type: "fixed", mean: 30 };
      else if (k === "a") { if (p.lifetime.type === "weibull") p.lifetime.shape = Number(t.value); else p.lifetime.mean = Number(t.value); }
      else if (k === "b") { if (p.lifetime.type === "weibull") p.lifetime.scale = Number(t.value); else p.lifetime.sd = Number(t.value); }
    }
    if (t.dataset.ff) { const f = D.flows[Number(tr.dataset.i)]; f[t.dataset.ff] = t.dataset.ff === "share" ? Number(t.value) : t.value; }
    if (t.dataset.if) {
      const x = D.inflows[Number(tr.dataset.i)];
      if (t.dataset.if === "to") x.to = t.value;
      else { const v = {}; t.value.split(";").forEach((pair) => { const [y, a] = pair.split(":").map((z) => z.trim()); if (y && a !== undefined && !isNaN(Number(a))) v[y] = Number(a); }); x.values = v; }
    }
    refresh();
  });
  $("#mfaBuilder").addEventListener("click", (e) => {
    const dp = e.target.closest("[data-delproc]"), df = e.target.closest("[data-delflow]"), di = e.target.closest("[data-delinflow]");
    if (!D || !(dp || df || di)) return;
    if (dp) { const id = D.processes[Number(dp.dataset.delproc)].id; D.processes.splice(Number(dp.dataset.delproc), 1); D.flows = D.flows.filter((f) => f.from !== id && f.to !== id); D.inflows = D.inflows.filter((x) => x.to !== id); delete D.layout[id]; }
    if (df) D.flows.splice(Number(df.dataset.delflow), 1);
    if (di) D.inflows.splice(Number(di.dataset.delinflow), 1);
    refresh();
  });
  // dragging nodes
  let drag = null;
  $("#mfaCanvas").addEventListener("pointerdown", (e) => {
    const g = e.target.closest("[data-node]"); if (!g || !D) return;
    const svg = $("#mfaCanvas"), pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse()), id = g.dataset.node, [x, y] = D.layout[id];
    drag = { id, dx: p.x - x, dy: p.y - y }; svg.setPointerCapture(e.pointerId);
  });
  $("#mfaCanvas").addEventListener("pointermove", (e) => {
    if (!drag) return;
    const svg = $("#mfaCanvas"), pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    D.layout[drag.id] = [Math.round(p.x - drag.dx), Math.round(p.y - drag.dy)]; draw();
  });
  $("#mfaCanvas").addEventListener("pointerup", () => { if (drag) { drag = null; write(); } });

  /* ---------------- links to the LCA ---------------- */
  function links() {
    D.lca_links = D.lca_links || {};
    $("#mfaLinks").innerHTML = D.processes.map((p) => { const l = D.lca_links[p.id];
      return `<tr data-pid="${esc(p.id)}"><td>${esc(p.name || p.id)}</td><td>${l ? `${esc(l.label || (l.kind + " " + l.id))} <button class="ghost" data-unlinkmfa="${esc(p.id)}">Remove</button>` : `<input data-mfasearch placeholder="Search a dataset" size="24"><select data-mfamodel><option value="">or a model...</option>${((S.models || [])).map((m) => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}</select><ul class="results" data-mfares></ul>`}</td>
        <td class="num"><input data-mfafactor type="number" step="any" value="${l ? esc(l.factor) : 1}" size="6"></td><td></td></tr>`; }).join("");
  }
  $("#mfaLinks").addEventListener("input", async (e) => {
    const inp = e.target.closest("[data-mfasearch]"); if (!inp || inp.value.trim().length < 2) return;
    const tr = inp.closest("tr");
    const { results } = await api("GET", "/api/search?q=" + encodeURIComponent(inp.value.trim()));
    $("[data-mfares]", tr).innerHTML = results.slice(0, 8).map((r) => `<li><button data-mfapick="${r.id}" data-label="${esc(r.name)} [${esc(r.location || "")}], ${esc(r.unit || "")}"><span class="rname">${esc(r.name)}</span><span class="loc">${esc(r.location || "")}</span><span class="rmeta">${esc(r.unit || "")}, ${esc(r.db || "")}</span></button></li>`).join("");
  });
  $("#mfaLinks").addEventListener("click", (e) => {
    const pk = e.target.closest("[data-mfapick]"), ul = e.target.closest("[data-unlinkmfa]");
    if (pk) { const tr = pk.closest("tr"); D.lca_links[tr.dataset.pid] = { kind: "activity", id: Number(pk.dataset.mfapick), factor: Number($("[data-mfafactor]", tr).value || 1), label: pk.dataset.label }; refresh(); }
    if (ul) { delete D.lca_links[ul.dataset.unlinkmfa]; refresh(); }
  });
  $("#mfaLinks").addEventListener("change", (e) => {
    const tr = e.target.closest("tr"); if (!tr || !D) return;
    if (e.target.matches("[data-mfamodel]") && e.target.value) { const m = (S.models || []).find((x) => String(x.id) === e.target.value); D.lca_links[tr.dataset.pid] = { kind: "model", id: Number(e.target.value), factor: Number($("[data-mfafactor]", tr).value || 1), label: "model: " + (m ? m.name : e.target.value) }; refresh(); }
    if (e.target.matches("[data-mfafactor]") && D.lca_links[tr.dataset.pid]) { D.lca_links[tr.dataset.pid].factor = Number(e.target.value); write(); }
  });
  $("#btnMfaLca").addEventListener("click", (e) => guard(e.target, async () => {
    if (!D) read();
    const mids = [...(S.selectedMethods || [])];
    if (!mids.length) throw new Error("Choose impact categories in step 4 first.");
    const links = {}; Object.entries(D.lca_links || {}).forEach(([k, l]) => (links[k] = { kind: l.kind, id: l.id, factor: l.factor }));
    const r = await api("POST", "/api/mfa/lca", { definition: D, method_ids: mids, links });
    const step = Math.max(1, Math.ceil(r.rows.length / 12));
    $("#mfaLcaOut").innerHTML = `<p class="hint">${esc(r.note)}${r.unlinked_processes.length ? ` Not linked: ${r.unlinked_processes.map(esc).join(", ")}.` : ""}</p>
      <div class="table-wrap"><table><thead><tr><th>Year</th>${r.categories.map((c) => `<th class="num">${esc(c.category)} <span class="hint">${esc(c.unit)}</span></th>`).join("")}</tr></thead><tbody>
      ${r.rows.filter((_, i) => i % step === 0 || i === r.rows.length - 1).map((x) => `<tr><td>${x.year}</td>${x.total.map((v) => `<td class="num">${fmt(v)}</td>`).join("")}</tr>`).join("")}
      <tr><td><b>Cumulative</b></td>${r.cumulative.map((v) => `<td class="num"><b>${fmt(v)}</b></td>`).join("")}</tr></tbody></table></div>`;
  }));
})();

/* ---------------- AWARE GIS, SQI, PSILCA/SOCA ---------------- */
(function () {
  $("#btnGeoImport").addEventListener("click", (e) => guard(e.target, async () => {
    const path = $("#geoPath").value.trim(); if (!path) throw new Error("Choose the GeoJSON file first.");
    const r = await api("POST", "/api/regional/geojson", { method: $("#regMethod").value, path, id_property: $("#geoId").value.trim() || "id" });
    $("#geoOut").textContent = `${r.shapes} polygons imported${r.factors ? `, with ${r.factors} factors` : ""}${r.n_rejected ? `; ${r.n_rejected} features rejected (${r.rejected.slice(0, 3).map((x) => x.reason).join("; ")})` : ""}.`;
  }));
  $("#btnSqi").addEventListener("click", (e) => guard(e.target, async () => {
    const normalisation = {}, weights = {};
    $$("[data-sqin]").forEach((i) => (normalisation[i.dataset.sqin] = i.value.trim()));
    $$("[data-sqiw]").forEach((i) => (weights[i.dataset.sqiw] = Number(i.value)));
    const r = await api("POST", "/api/regional/sqi", { normalisation, weights, source: $("#sqiSource").value.trim() });
    $("#sqiOut").innerHTML = `<p>${r.factors} SQI factors aggregated.${r.n_incomplete ? ` ${r.n_incomplete} land use types lack one of the four indicators and were skipped.` : ""}</p>` +
      (r.n_compared ? `<p>Compared with the official SQI factors for ${r.n_compared} land use types: largest relative difference ${(100 * r.max_relative_difference).toFixed(2)} %.</p>` : "") +
      `<p class="hint">${esc(r.source)}</p>`;
  }));
  $("#btnOlcaSoc").addEventListener("click", (e) => guard(e.target, async () => {
    const path = $("#olcaSocPath").value.trim(); if (!path) throw new Error("Choose the PSILCA or SOCA export first.");
    const { job } = await api("POST", "/api/slca/import-olca", { path, mapping_path: $("#olcaMapPath").value.trim() || null });
    await watchJob(job, { quiet: true, onDone: (j) => {
      const r = j.result;
      $("#olcaSocOut").textContent = `${r.rows} social data rows from ${r.processes} processes and ${r.indicators} indicators` +
        (r.mapped_rows ? `, ${r.mapped_rows} assigned through the mapping table` : "") +
        (Object.keys(r.skipped_levels).length ? `; not counted as risks: ${Object.entries(r.skipped_levels).map(([k, v]) => `${v} ${k.toLowerCase().replace(/_/g, " ")}`).join(", ")}` : "") + ".";
    } });
  }));
})();

/* ---------------- comparison kit ---------------- */
(function () {
  const _show = showToolTab;
  showToolTab = function (t) {
    _show.apply(this, arguments);
    if (t === "valid") {
      const opts = ((S.status && S.status.databases) || []).map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
      $("#kitDb").innerHTML = opts;
      $("#bwCmpDb").innerHTML = opts;
      api("GET", "/api/brightway/status").then((s) => {
        $("#btnBwCmp").disabled = !s.available;
        $("#bwCmpStatus").textContent = s.available ? `Brightway calculation library: bw2calc ${s.bw2calc}, bw_processing ${s.bw_processing}.`
          : "Brightway's calculation library is not included in this installation. Use the comparison kit below instead.";
      }).catch(() => {});
    }
  };
  $("#btnBwCmp").addEventListener("click", (e) => guard(e.target, async () => {
    const mids = [...(S.selectedMethods || [])];
    if (!mids.length) throw new Error("Choose the impact categories in step 4 first.");
    const { job } = await api("POST", "/api/brightway/compare", { db_id: Number($("#bwCmpDb").value), method_ids: mids, sample: Number($("#bwCmpSample").value) });
    const j = await watchJob(job, { quiet: true });
    if (!j || j.status !== "done" || !j.result) return;
    const r = j.result;
    $("#btnBwCmpExport").disabled = false;
    const e6 = (x) => Number(x).toExponential(1);
    $("#bwCmpOut").innerHTML = `<p class="${r.passed ? "ok" : "danger"}"><b>${esc(r.verdict)}</b></p>
      <p class="hint">${esc(r.database)}${r.database_version ? " " + esc(r.database_version) : ""}${r.system_model ? ", " + esc(r.system_model) : ""}: ${r.datasets.toLocaleString("en-US")} of ${r.datasets_in_database.toLocaleString("en-US")} datasets. ${esc(r.scope)}</p>
      <div class="table-wrap"><table><thead><tr><th>Category</th><th>Unit</th><th class="num">Results</th><th class="num">Agree</th><th class="num">Median difference</th><th class="num">Largest</th></tr></thead><tbody>
      ${r.by_category.map((c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.unit)}</td><td class="num">${c.results}</td><td class="num">${c.agree}</td><td class="num">${e6(c.median)}</td><td class="num">${e6(c.max)}</td></tr>`).join("")}</tbody></table></div>`;
  }));
  $("#btnBwCmpExport").addEventListener("click", (e) => guard(e.target, () => exportTo("/api/export/brightway-check", "Cyclia compared with Brightway.xlsx", "xlsx", {})));
  $("#btnKit").addEventListener("click", (e) => guard(e.target, async () => {
    const mids = [...(S.selectedMethods || [])];
    if (!mids.length) throw new Error("Choose the impact categories in step 4 first.");
    const r = await exportTo("/api/export/compare-kit", "Cyclia comparison kit.zip", "zip", { db_id: Number($("#kitDb").value), method_ids: mids });
    if (r) $("#kitOut").textContent = `${r.datasets} datasets x ${r.categories} categories (${r.results} results). Unzip it and follow README.md.`;
  }));
})();
