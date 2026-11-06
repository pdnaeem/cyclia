/* Cyclia 1.3.5: factor matching validation, EPD programme profiles, marginal suppliers, AWARE and LANCA,
   social LCA, material flow analysis. Loaded after app.js, features.js, setup.js and pro.js. */
(function () {
  "use strict";
  const pct = (v) => (v == null ? "-" : `${(100 * v).toFixed(1)} %`);
  const needProject = () => { if (!(S.status && S.status.project)) throw new Error("Open a project first (step 1)."); };

  /* ---------------- toolbox tabs ---------------- */
  const _showToolTab = showToolTab;
  showToolTab = function (t) {
    _showToolTab.apply(this, arguments);
    if (["regional", "social"].includes(t) && !(S.status && S.status.project)) { toast("Open a project first (step 1).", true); return; }
    if (t === "regional") regStatus().catch((e) => toast(e.message, true));
    if (t === "social") slcaStatus().catch((e) => toast(e.message, true));
    if (t === "mfa" && !$("#mfaDef").value.trim()) loadMfaExample().catch(() => {});
  };

  /* ---------------- factor matching validation ---------------- */
  $("#btnFm").addEventListener("click", (e) => guard(e.target, async () => {
    needProject();
    if (!S.selectedMethods.size) throw new Error("Pick the impact categories to compare in step 4 first.");
    const path = $("#fmPath").value.trim();
    if (!path) throw new Error("Choose the file with the other tool's factors.");
    const { job } = await api("POST", "/api/factor-match", { path, results_path: $("#fmResPath").value.trim() || null, method_ids: [...S.selectedMethods] });
    $("#fmOut").innerHTML = '<p class="hint">Comparing; progress is shown at the bottom left.</p>';
    watchJob(job, { quiet: true, onDone: (j) => {
      const r = j.result;
      $("#fmOut").innerHTML = `<p class="${r.passed ? "ok" : "danger"}"><b>${esc(r.passed ? r.verdict : `Not passed: ${(r.open_items || []).length} open item(s).`)}</b></p>
        ${(r.open_items || []).length ? `<ul class="list">${r.open_items.slice(0, 12).map((x) => `<li>${esc(x)}</li>`).join("")}${r.open_items.length > 12 ? `<li>... ${r.open_items.length - 12} more in the Excel report</li>` : ""}</ul>` : ""}
        <p class="hint">Source: ${esc(r.source)}. ${esc(r.scope)}</p>
        <div class="table-wrap"><table><thead><tr><th>Cyclia category</th><th>External category</th><th class="num">Same</th><th class="num">Different</th><th class="num">Only Cyclia</th><th class="num">Only external</th><th class="num">Units not comparable</th><th class="num">External flows not in library</th><th class="num">Several flows matched</th><th class="num">Conflicts</th><th class="num">Largest effect on a model</th></tr></thead><tbody>` +
        r.categories.map((c) => `<tr><td>${esc(c.category)}</td><td>${c.external_category ? esc(c.external_category) : '<span class="danger">no match</span>'}</td><td class="num">${c.same}</td><td class="num">${c.different}</td><td class="num">${c.only_cyclia}</td><td class="num">${c.only_external}</td><td class="num">${c.unit_mismatch || 0}</td><td class="num">${c.unresolved}</td><td class="num">${c.ambiguous}</td><td class="num">${c.external_conflicts}</td>
          <td class="num">${c.models.length ? Math.max(...c.models.map((m) => Math.abs(m.factor_effect_percent || 0))).toFixed(3) + " %" : "-"}</td></tr>`).join("") + "</tbody></table></div>" +
        (r.flows.length ? `<h3>Largest differences</h3><div class="table-wrap"><table><thead><tr><th>Category</th><th>Flow</th><th>Compartment</th><th>Status</th><th class="num">Cyclia</th><th class="num">External</th></tr></thead><tbody>${r.flows.slice(0, 25).map((f) => `<tr><td>${esc(f.category)}</td><td>${esc(f.flow)}</td><td>${esc(f.compartment)}</td><td>${esc(f.status.replace("_", " "))}</td><td class="num">${fmt(f.cyclia)}</td><td class="num">${fmt(f.external)}</td></tr>`).join("")}</tbody></table></div>` : "");
      $("#btnFmExport").disabled = false;
    } });
  }));
  $("#btnFmExport").addEventListener("click", (e) => guard(e.target, () => exportTo("/api/export/factor-match", "Cyclia factor matching validation.xlsx", "xlsx", {})));

  /* ---------------- EPD programme profiles ---------------- */
  let PROFILES = [];
  async function loadProfiles() {
    if (!PROFILES.length) PROFILES = (await api("GET", "/api/epd/profiles")).profiles;
    return PROFILES;
  }
  function profileById(id) { return PROFILES.find((p) => p.id === (id || "generic")) || PROFILES[0]; }
  function renderProfileFields(values) {
    const p = profileById($("#epdProfile").value);
    if (!p) return;
    $("#epdProfileNote").textContent = p.status + (p.based_on && p.based_on.length ? ` Sources: ${p.based_on.join(", ")}` : "");
    $("#epdProfileFields").innerHTML = (p.fields || []).map((f) => {
      const v = values && values[f.key] != null ? values[f.key] : (f.default || "");
      const req = f.required ? ' <span class="danger">*</span>' : "";
      if (f.type === "select") return `<label>${esc(f.label)}${req}<select data-pf="${esc(f.key)}"><option value=""></option>${f.options.map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>`;
      if (f.type === "textarea") return `<label class="wide">${esc(f.label)}${req}<textarea data-pf="${esc(f.key)}" rows="2">${esc(v)}</textarea></label>`;
      return `<label>${esc(f.label)}${req}<input data-pf="${esc(f.key)}" value="${esc(v)}"></label>`;
    }).join("");
  }
  const _fillEpdForm = fillEpdForm;
  fillEpdForm = function () {
    _fillEpdForm.apply(this, arguments);
    const e = (S.model && S.model.scope && S.model.scope.epd) || {};
    $("#epdInfo").statements_override.value = (e.statements_override || []).join("\n");
    loadProfiles().then((ps) => {
      $("#epdProfile").innerHTML = ps.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}${p.custom ? " (custom)" : ""}</option>`).join("");
      $("#epdProfile").value = e.profile || "generic";
      renderProfileFields(e.fields || {});
    }).catch((err) => toast(err.message, true));
  };
  $("#epdProfile").addEventListener("change", () => renderProfileFields(((S.model && S.model.scope && S.model.scope.epd) || {}).fields || {}));
  $("#btnProfileExport").addEventListener("click", (e) => guard(e.target, () => {
    const id = $("#epdProfile").value || "generic";
    return exportTo("/api/export/epd-profile", `EPD profile ${id}.json`, "json", { id });
  }));
  $("#btnProfileLoad").addEventListener("click", (e) => guard(e.target, async () => {
    const path = $("#profilePath").value.trim();
    if (!path) throw new Error("Choose the profile .json file first.");
    const { id } = await api("POST", "/api/epd/profiles", { path });
    PROFILES = [];
    const ps = await loadProfiles();
    $("#epdProfile").innerHTML = ps.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}${p.custom ? " (custom)" : ""}</option>`).join("");
    $("#epdProfile").value = id;
    renderProfileFields({});
    toast(`Profile '${id}' loaded. Save the EPD details to use it for this model.`);
  }));
  const _saveEpd = saveEpd;
  saveEpd = async function () {
    needModel();
    const f = $("#epdInfo"), body = {};
    ["manufacturer", "site", "programme", "number", "pcr", "rsl", "issued", "valid_until", "verification", "verifier", "biogenic_product", "biogenic_packaging", "description", "specific_months", "pcr_version", "programme_statements"]
      .forEach((k) => (body[k] = f[k].value.trim()));
    body.audience = f.audience.value; body.prospective = f.prospective.checked ? "yes" : "";
    body.declared = $$("#epdModules input:checked").map((i) => i.value);
    body.profile = $("#epdProfile").value || "generic";
    body.fields = {};
    $$("#epdProfileFields [data-pf]").forEach((i) => { if (i.value.trim()) body.fields[i.dataset.pf] = i.value.trim(); });
    body.statements_override = f.statements_override.value.split("\n").map((x) => x.trim()).filter(Boolean);
    const { model } = await api("POST", `/api/models/${S.model.id}/epd-info`, body);
    S.model = model;
  };
  void _saveEpd;

  /* ---------------- marginal suppliers ---------------- */
  let MARG = null;
  $("#btnMarginal").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    MARG = await api("GET", `/api/models/${S.model.id}/marginal`);
    $("#marginalNote").textContent = MARG.guidance;
    $("#marginalOut").innerHTML = MARG.markets.length ? MARG.markets.map((m, k) => `<div class="marg"><h3>${esc(m.market.name)} <span class="hint">[${esc(m.market.location || "")}] ${esc(m.product)}</span></h3>
      ${m.all_constrained ? '<p class="danger">Every supplier looks constrained: choose the marginal supplier from market data.</p>' : ""}
      <ul class="list">${m.suppliers.map((sup) => `<li><label class="inline grow"><input type="radio" name="marg${k}" value="${sup.id}" ${m.proposal && m.proposal.id === sup.id ? "checked" : ""} ${sup.constrained ? "" : ""}> ${esc(sup.name)} <span class="hint">[${esc(sup.location || "")}] ${(100 * sup.share).toFixed(0)} % today</span></label>${sup.constrained ? `<span class="warn">${esc(sup.reason)}</span>` : ""}</li>`).join("")}
      <li><label class="inline"><input type="radio" name="marg${k}" value="" ${m.proposal ? "" : "checked"}> keep the current mix</label></li></ul></div>`).join("")
      : '<p class="empty">No market with several suppliers was found in the supply chain of this model.</p>';
    $("#marginalAct").hidden = !MARG.markets.length;
  }));
  $("#btnMarginalSave").addEventListener("click", (e) => guard(e.target, async () => {
    if (!MARG) throw new Error("Find the markets first.");
    const rules = [];
    MARG.markets.forEach((m, k) => {
      const v = ($(`input[name=marg${k}]:checked`) || {}).value;
      if (v) rules.push({ type: "swap", activity_ids: [m.market.id], product: m.product, to: [{ id: Number(v), share: 1 }] });
    });
    if (!rules.length) throw new Error("Choose a marginal supplier for at least one market.");
    await api("POST", "/api/bg-scenarios", { name: $("#marginalName").value.trim() || "Consequential, marginal suppliers", kind: "consequential",
      description: "Marginal suppliers chosen with Cyclia's guidance (constrained suppliers excluded).", base_year: 2020, rules });
    toast("Consequential scenario created. Choose it in step 4 (Background database).");
    if (typeof loadBg === "function") loadBg();
  }));

  /* ---------------- AWARE and LANCA ---------------- */
  async function regStatus() {
    const r = await api("GET", "/api/regional/status");
    S.regTemplates = r.templates;
    $("#regStatus").innerHTML = ["AWARE", "LANCA"].map((m) => { const x = r.status[m];
      return `<p><b>${m}</b>: ${x.factors ? `${x.factors.toLocaleString()} factors for ${x.locations} locations; source: ${esc(x.source)}` : "no factors imported"}${x.demo ? ' <span class="warn">demo values, not the official method</span>' : ""}</p>`; }).join("");
    const sc = (S.model && S.model.scope) || {};
    $("#awareLoc").value = sc.aware_location || ""; $("#awareUse").value = (sc.aware_use || "unknown").replace("-", "_");
    $("#awareBg").value = sc.aware_background_use || "by process";
    $("#awareLat").value = sc.aware_lat ?? ""; $("#awareLon").value = sc.aware_lon ?? ""; $("#awareMonths").value = sc.aware_months ?? "";
  }
  $("#btnRegTemplate").addEventListener("click", () => { $("#regTemplate").hidden = false; $("#regTemplate").textContent = (S.regTemplates || {})[$("#regMethod").value] || ""; });
  $("#btnRegImport").addEventListener("click", (e) => guard(e.target, async () => {
    const path = $("#regPath").value.trim();
    if (!path) throw new Error("Choose the CSV file with the factors.");
    const r = await api("POST", "/api/regional/import", { method: $("#regMethod").value, path });
    toast(`${r.factors} ${r.method} factors imported${r.n_rejected ? `; ${r.n_rejected} rows rejected (${r.rejected.slice(0, 2).map((x) => x.reason).join("; ")})` : ""}.`, !!r.n_rejected);
    regStatus();
  }));
  $("#btnRegDemo").addEventListener("click", (e) => guard(e.target, async () => { await api("POST", "/api/regional/demo"); regStatus(); toast("Demo factors loaded: invented numbers, only to try the workflow."); }));
  async function saveRegScope() {
    needModel();
    const sc = S.model.scope || {};
    const want = { aware_location: $("#awareLoc").value.trim().toUpperCase(), aware_use: $("#awareUse").value, aware_background_use: $("#awareBg").value,
      aware_lat: $("#awareLat").value.trim(), aware_lon: $("#awareLon").value.trim(), aware_months: $("#awareMonths").value.trim() };
    const have = { aware_location: sc.aware_location || "", aware_use: sc.aware_use || "unknown", aware_background_use: sc.aware_background_use || "by process",
      aware_lat: String(sc.aware_lat ?? ""), aware_lon: String(sc.aware_lon ?? ""), aware_months: String(sc.aware_months ?? "") };
    if (Object.keys(want).some((k) => String(want[k]) !== String(have[k]))) {
      fillScope();
      await saveModelScope(want);
    }
  }
  const compl = (c) => `exact ${pct(c.exact)}, country ${pct(c.country)}, global ${pct(c.global)}, <span class="${c.none > 0 ? "danger" : ""}">none ${pct(c.none)}</span>`;
  $("#btnAware").addEventListener("click", (e) => guard(e.target, async () => {
    await saveRegScope();
    const r = await api("POST", "/api/regional/assess", { model_id: S.model.id, method: "AWARE" });
    $("#regOut").innerHTML = `<h3>AWARE water scarcity of ${esc(S.model.name)}</h3>${r.demo ? '<p class="warn">Demo factors: not AWARE 2.0 values.</p>' : ""}
      <p><b>${fmt(r.total)} ${esc(r.unit)}</b> per functional unit, from ${fmt(r.consumption_m3)} m3 of water consumed.</p>
      ${r.empty ? '<p class="warn">The supply chain of this model has no water taken from or returned to nature, so there is nothing to characterise. The result is 0 and completeness does not apply.</p>' : `<p>Completeness (share of the water consumption): ${compl(r.completeness)}.</p>`}
      <p class="hint">Model's own water: ${r.site_from_gis ? `watershed ${esc(r.site_from_gis.location)} (${esc(r.site_from_gis.name)}) found from the coordinates` : `location ${esc(r.site || "GLO")}`}${r.monthly_used ? ", monthly factors weighted by the use profile" : r.monthly_factors_available ? ", annual factor (no monthly profile given)" : ""}. Supply-chain processes use annual factors.</p>
      ${r.unmatched.length ? `<p class="danger">Locations without a factor: ${r.unmatched.slice(0, 8).map((x) => `${esc(x.location)} (${fmt(x.consumption_m3)} m3)`).join(", ")}.</p>` : ""}
      ${r.water_balance_m3 ? `<p class="hint">Water balance per functional unit (m3): withdrawn ${fmt(r.water_balance_m3.withdrawal)}, returned to fresh water ${fmt(r.water_balance_m3.returned)}, evaporated ${fmt(r.water_balance_m3.evaporated)}, to the sea ${fmt(r.water_balance_m3.to_sea)}, to soil ${fmt(r.water_balance_m3.to_soil)}. Only the return to fresh water is subtracted.${r.consumption_from_flows_m3 ? ` Of the consumption (${fmt(r.consumption_from_flows_m3)}), ${fmt(r.consumption_identified_m3)} is reported as evaporation, discharge to the sea or release to soil; ${fmt(r.consumption_not_identified_m3)} has no reported output (water in products or not reported by the data).` : ""}</p>` : ""}
      <div class="table-wrap"><table><thead><tr><th>Process</th><th>Location</th><th>Use</th><th class="num">Consumption m3</th><th class="num">Factor</th><th>Factor found</th><th class="num">Impact</th></tr></thead><tbody>${r.top.slice(0, 15).map((x) => `<tr><td>${esc(x.process)}</td><td>${esc(x.location)}</td><td>${esc(x.use)}${x.factor_of_use && x.factor_of_use !== x.use ? ` <span class="warn">(no ${esc(x.use)} factor: unknown used)</span>` : ""}</td><td class="num">${fmt(x.consumption_m3)}</td><td class="num">${fmt(x.factor)}</td><td>${esc(x.how)}</td><td class="num">${fmt(x.impact)}</td></tr>`).join("")}</tbody></table></div>
      <p class="hint">${esc(r.note)}</p>`;
  }));
  $("#btnLanca").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    const r = await api("POST", "/api/regional/assess", { model_id: S.model.id, method: "LANCA" });
    $("#regOut").innerHTML = `<h3>LANCA land use of ${esc(S.model.name)}</h3>${r.demo ? '<p class="warn">Demo factors: not LANCA values.</p>' : ""}
      ${r.empty ? '<p class="warn">The supply chain of this model has no land occupation or transformation flows, so there is nothing to characterise. The results are 0 and completeness does not apply.</p>' : ""}
      <div class="table-wrap"><table><thead><tr><th>Indicator</th><th class="num">Result</th><th>Unit</th><th>Occupation / transformation</th><th>Completeness (share of land area)</th><th>Land flows without a factor</th></tr></thead><tbody>${r.indicators.map((x) => `<tr><td>${esc(x.indicator)}</td><td class="num">${fmt(x.total)}</td><td>${esc(x.unit)}</td><td>${x.by_kind.map((k) => `${esc(k.kind.replace("_", " "))} ${fmt(k.impact)}`).join("; ")}</td><td>${compl(x.completeness)}</td><td>${x.without_factor.slice(0, 4).map((w) => esc(w.flow)).join("; ") || "-"}</td></tr>`).join("")}</tbody></table></div>
      <p class="hint">${esc(r.note)}</p>`;
  }));

  /* ---------------- social LCA ---------------- */
  async function slcaStatus() {
    const r = await api("GET", "/api/slca/info");
    S.slcaTemplate = r.template;
    $("#slcaStatus").innerHTML = `<p>${r.rows ? `${r.rows.toLocaleString()} rows of social data; source: ${esc(r.source)}${r.source.startsWith("demo") ? ' <span class="warn">invented demo data</span>' : ""}` : "No social data imported."}</p><p class="hint">Risk factors: ${Object.entries(r.risk_factors).map(([k, v]) => `${esc(k)} ${v}`).join(", ")}.</p>`;
  }
  $("#btnSlcaTemplate").addEventListener("click", () => { $("#slcaTemplate").hidden = false; $("#slcaTemplate").textContent = S.slcaTemplate || ""; });
  $("#btnSlcaImport").addEventListener("click", (e) => guard(e.target, async () => {
    const path = $("#slcaPath").value.trim();
    if (!path) throw new Error("Choose the CSV file with the social data.");
    const r = await api("POST", "/api/slca/import", { path });
    toast(`${r.rows} rows imported${r.n_rejected ? `; ${r.n_rejected} rejected (${r.rejected.slice(0, 2).map((x) => x.reason).join("; ")})` : ""}.`, !!r.n_rejected);
    slcaStatus();
  }));
  $("#btnSlcaDemo").addEventListener("click", (e) => guard(e.target, async () => { await api("POST", "/api/slca/demo"); slcaStatus(); toast("Demo social data loaded: invented, only to try the workflow."); }));
  $("#btnSlca").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    const r = await api("POST", "/api/slca/assess", { model_id: S.model.id });
    $("#slcaOut").innerHTML = `${r.demo ? '<p class="warn">Demo data: the results mean nothing.</p>' : ""}${(r.inconsistent_activity_variables || []).length ? `<p class="warn">${r.inconsistent_activity_variables.length} process(es) have different worker hours per unit in different rows of the social data (for example ${esc(r.inconsistent_activity_variables[0].process)}: ${r.inconsistent_activity_variables[0].worker_hours.map(fmt).join(", ")}). The first value is used; give one activity variable per process and location.</p>` : ""}<p class="hint">${esc(r.label || "Social LCA risk screening")}</p><p><b>${fmt(r.worker_hours)} worker hours</b> per functional unit in the processes with data (a lower bound). Process coverage: ${r.n_with_data} of ${r.n_processes} processes (${pct(r.process_coverage)}) have social data${r.complete ? "" : '; <span class="warn">incomplete</span>'}.
      ${r.coverage_hours != null ? ` Worker-hour coverage ${pct(r.coverage_hours)} (${fmt(r.worker_hours_estimated)} hours of processes without data estimated with the default row).` : " Worker-hour coverage cannot be known without a default row (match *) for processes without data."}
      ${r.worker_hours_avoided ? ` Avoided products: ${fmt(r.worker_hours_avoided)} worker hours, listed separately and not subtracted.` : ""}</p>
      <div class="table-wrap"><table><thead><tr><th>Stakeholder</th><th>Indicator</th><th class="num">Risk hours</th><th class="num">Coverage of total hours</th><th>Largest contributors</th></tr></thead><tbody>${r.indicators.map((x) => `<tr><td>${esc(x.stakeholder)}</td><td>${esc(x.indicator)}</td><td class="num">${fmt(x.risk_hours)}</td><td class="num">${x.coverage == null ? "unknown" : pct(x.coverage)}</td><td>${x.by_process.slice(0, 3).map((p) => `${esc(p.process)} (${esc(p.risk)})`).join("; ")}</td></tr>`).join("")}</tbody></table></div>
      ${r.processes_without_data.length ? `<p class="hint">Without data (largest output first): ${r.processes_without_data.slice(0, 8).map((p) => esc(p.process)).join("; ")}.</p>` : ""}
      <p class="hint">${esc(r.note)}</p>`;
  }));

  /* ---------------- material flow analysis ---------------- */
  async function loadMfaExample() { const r = await api("GET", "/api/mfa/example"); $("#mfaDef").value = JSON.stringify(r.definition, null, 2); }
  $("#btnMfaExample").addEventListener("click", (e) => guard(e.target, loadMfaExample));
  function lineChart(series, years) {
    const W = 640, H = 220, P = 36;
    const all = series.flatMap((s) => s.values).filter((v) => v != null);
    const max = Math.max(...all, 1e-12), x = (i) => P + (W - 2 * P) * i / Math.max(1, years.length - 1), y = (v) => H - P - (H - 2 * P) * v / max;
    const colors = ["var(--spruce)", "var(--ochre)", "var(--neg)", "#8a6fb0"];
    return `<svg viewBox="0 0 ${W} ${H}" class="mfa-chart" role="img" aria-label="Material flows over time"><line x1="${P}" y1="${H - P}" x2="${W - P}" y2="${H - P}" stroke="var(--rule-strong)"/>` +
      series.map((s, k) => `<polyline fill="none" stroke="${colors[k % 4]}" stroke-width="2" points="${s.values.map((v, i) => `${x(i).toFixed(1)},${y(v || 0).toFixed(1)}`).join(" ")}"/>`).join("") +
      `<text x="${P}" y="${H - 8}" font-size="11" fill="var(--ink-soft)">${years[0]}</text><text x="${W - P - 28}" y="${H - 8}" font-size="11" fill="var(--ink-soft)">${years[years.length - 1]}</text><text x="4" y="${P - 8}" font-size="11" fill="var(--ink-soft)">${fmt(max)}</text></svg>` +
      `<div class="legend-row">${series.map((s, k) => `<span><i style="background:${colors[k % 4]}"></i>${esc(s.name)}</span>`).join("")}</div>`;
  }
  $("#btnMfaRun").addEventListener("click", (e) => guard(e.target, async () => {
    const r = await api("POST", "/api/mfa/run", { definition: $("#mfaDef").value });
    const rows = r.rows, step = Math.max(1, Math.round(rows.length / 10));
    $("#mfaOut").innerHTML = `<p class="${r.mass_balance_ok ? "ok" : "danger"}">${r.mass_balance_ok ? "Mass balance closed in every year." : `Mass balance error ${r.max_balance_error.toExponential(1)}.`}</p>` +
      lineChart([{ name: "Stock", values: rows.map((x) => x.stock) }, { name: "External inflow", values: rows.map((x) => x.external_inflow) }, { name: "End-of-life outflow", values: rows.map((x) => x.end_of_life_outflow) }, { name: "Recycled", values: rows.map((x) => x.recycled) }], r.years) +
      `<div class="table-wrap"><table><thead><tr><th>Year</th><th class="num">Inflow</th><th class="num">Stock</th><th class="num">End of life</th><th class="num">Recycled</th><th class="num">Losses</th><th class="num">Collection rate (end of life)</th><th class="num">End-of-life recycling rate</th><th class="num">Recycled content (production input)</th><th class="num">MCI from the MFA</th></tr></thead><tbody>` +
      rows.filter((_, i) => i % step === 0 || i === rows.length - 1).map((x) => `<tr><td>${x.year}</td><td class="num">${fmt(x.external_inflow)}</td><td class="num">${fmt(x.stock)}</td><td class="num">${fmt(x.end_of_life_outflow)}</td><td class="num">${fmt(x.recycled)}</td><td class="num">${fmt(x.losses)}</td><td class="num">${pct(x.collection_rate)}</td><td class="num">${pct(x.recycling_rate)}</td><td class="num">${pct(x.recycled_content)}</td><td class="num">${x.mci == null ? "-" : x.mci.toFixed(3)}</td></tr>`).join("") +
      `</tbody></table></div><p class="hint">${esc(r.note)}</p>`;
  }));
  $("#btnMci").addEventListener("click", (e) => guard(e.target, async () => {
    const body = {};
    $$("[data-mci]").forEach((i) => (body[i.dataset.mci] = Number(i.value)));
    const r = await api("POST", "/api/mfa/mci", body);
    $("#mciOut").innerHTML = `<b>MCI ${r.MCI.toFixed(3)}</b> <span class="hint">(linear flow index ${r.LFI.toFixed(3)}, utility ${r.utility.toFixed(2)})</span>`;
  }));
})();
