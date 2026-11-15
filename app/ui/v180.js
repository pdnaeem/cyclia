/* Cyclia 1.8.0: collaborative critical review (step 6). */
(function () {
  const v = (id) => ($("#" + id).value || "").trim();
  let items = null;
  const role = () => $("#rvRole").value;
  try { const r = localStorage.getItem("cyclia.reviewRole"); if (r) $("#rvRole").value = r; } catch (e) { /* storage may be blocked */ }
  async function checklistItems() {
    if (items) return items;
    const b = looseBody(); delete b.method_ids;
    items = (await api("POST", "/api/review", b)).items;
    return items;
  }
  async function fillTargets() {
    const its = await checklistItems();
    const lines = (S.model && S.model.inputs) || [];
    $("#rvTarget").innerHTML = '<option value="general">The study as a whole</option>' +
      (lines.length ? '<optgroup label="Inventory line">' + lines.map((l) => `<option value="line:${l.id}">${esc(l.label || (l.target && l.target.name) || "line " + l.id)}</option>`).join("") + "</optgroup>" : "") +
      '<optgroup label="ISO 14044 checklist item">' + its.map((i) => `<option value="item:${i.key}">${esc(i.clause + " " + i.text.slice(0, 70))}</option>`).join("") + "</optgroup>";
  }
  const SEV = { critical: "danger", major: "warn", minor: "", editorial: "hint" };
  async function load() {
    if (!S.model) { $("#rvList").innerHTML = '<p class="hint">Choose a model first.</p>'; return; }
    const r = await api("GET", `/api/models/${S.model.id}/review-comments`);
    const isRev = role() === "reviewer";
    $("#rvNew").hidden = $("#rvNew2").hidden = !isRev;
    $("#rvCloseRow").hidden = !isRev && !r.closure;
    $("#btnRvClose").hidden = !isRev || !!r.closure;
    $("#rvStatement").hidden = !isRev || !!r.closure;
    $("#btnRvReopen").hidden = !isRev || !r.closure;
    const open = r.threads.filter((t) => t.status === "open" || t.status === "answered").length;
    $("#rvSummary").textContent = r.threads.length ? `${r.threads.length} comment(s), ${open} not resolved, ${r.blocking} critical or major not resolved.` : "No review comments yet.";
    $("#rvClosure").innerHTML = r.closure ? `<b>Review closed</b> on ${esc(r.closure.date)} by ${esc(r.closure.reviewer)}: ${esc(r.closure.statement)}` +
      (r.closure_current ? "" : ' <span class="warn">The model has changed since then; the statement refers to an earlier state.</span>') : "";
    $("#rvList").innerHTML = r.threads.length ? r.threads.map((t) => `<div class="rv-thread" data-uid="${t.uid}">
        <div class="row"><span class="pill ${SEV[t.severity]}">${esc(t.severity)}</span><b class="grow">${esc(t.target_label)}</b><span class="pill">${esc(t.status)}</span></div>
        <p>${esc(t.text)} <span class="meta">${esc(t.author)}, ${esc((t.created || "").slice(0, 10))}</span></p>
        ${t.replies.map((x) => `<p class="rv-reply">${esc(x.text)} <span class="meta">${esc(x.author)} (${esc(x.role)}), ${esc((x.created || "").slice(0, 10))}</span></p>`).join("")}
        <div class="row"><input class="grow rv-ans" placeholder="${isRev ? "Reply" : "Answer"}" aria-label="Reply"><button data-rvreply>${isRev ? "Reply" : "Answer"}</button>
          ${isRev ? `<button class="ghost" data-rvst="resolved">Resolve</button><button class="ghost" data-rvst="open">Keep open</button><button class="ghost" data-rvst="withdrawn">Withdraw</button>` : ""}</div></div>`).join("")
      : "";
  }
  $("#rvRole").addEventListener("change", () => { try { localStorage.setItem("cyclia.reviewRole", role()); } catch (e) { /* ignore */ } guard(null, load); });
  $("#btnRvAdd").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    if (!v("rvText")) throw new Error("Write the comment first.");
    await api("POST", `/api/models/${S.model.id}/review-comments`, { role: role(), severity: $("#rvSev").value, target: $("#rvTarget").value, text: v("rvText") });
    $("#rvText").value = "";
    await load();
  }));
  $("#rvList").addEventListener("click", (e) => {
    const th = e.target.closest(".rv-thread"); if (!th) return;
    const uid = th.dataset.uid;
    if (e.target.closest("[data-rvreply]")) {
      const text = $(".rv-ans", th).value.trim();
      guard(e.target, async () => {
        if (!text) throw new Error("Write the answer first.");
        await api("POST", `/api/models/${S.model.id}/review-comments`, { role: role(), parent: uid, text });
        await load();
      });
    }
    const st = e.target.closest("[data-rvst]");
    if (st) guard(st, async () => { await api("POST", `/api/review-comments/${uid}/status`, { status: st.dataset.rvst, role: role() }); await load(); });
  });
  $("#btnRvClose").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    if (!v("rvStatement")) throw new Error("Write the review statement first.");
    await api("POST", `/api/models/${S.model.id}/review/close`, { statement: v("rvStatement") });
    toast("Review closed. The statement is in the Word report.");
    await load();
  }));
  $("#btnRvReopen").addEventListener("click", (e) => guard(e.target, async () => { await api("POST", `/api/models/${S.model.id}/review/reopen`, {}); await load(); }));
  $("#btnRvExport").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    await exportTo(`/api/models/${S.model.id}/review/export`, `${safeName(S.model.name)} review.json`, "json");
  }));
  $("#btnRvImport").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    if (!v("rvPath")) throw new Error("Choose the review file you received.");
    const r = await api("POST", `/api/models/${S.model.id}/review/import`, { path: v("rvPath") });
    toast(`Merged: ${r.added} new, ${r.updated} updated, ${r.unchanged} unchanged` + (r.kept_local ? `, ${r.kept_local} kept (yours is newer)` : "") + (r.skipped ? `, ${r.skipped} skipped` : "") + ".");
    if (!r.same_model) toast("The other side's model differs from yours (inputs, parameters or scope). Check that you both review the same version.", true);
    S.model = (await api("GET", "/api/models/" + S.model.id)).model;
    await load();
  }));
  const _go = go;
  go = function (step) {
    _go.apply(this, arguments);
    if (step === "report" && S.model) guard(null, async () => { items = null; await fillTargets(); await load(); });
  };
})();

/* Cyclia 1.8.0: optimise choices (Toolbox). */
(function () {
  const O = { slots: [], lims: [], last: null };
  const num = (x) => (x === "" || x === null || x === undefined ? null : Number(x));
  const mlabel = (id) => { const m = S.methods.find((x) => x.id === id); return m ? m.category + (m.indicator ? " (" + m.indicator + ")" : "") + " [" + m.unit + "]" : "category " + id; };
  function fillLines() {
    const lines = (S.model && S.model.inputs) || [];
    $("#chLine").innerHTML = lines.filter((l) => l.kind === "activity" || l.kind === "model")
      .map((l) => `<option value="${l.id}">${esc(l.label || l.target.name)} (${fmt(l.input_amount)} ${esc(l.input_unit || "")})</option>`).join("") || '<option value="">No dataset lines in the open model</option>';
    const sel = [...S.selectedMethods];
    const opts = sel.map((id) => `<option value="m${id}">${esc(mlabel(id))}</option>`).join("") + '<option value="cost">purchase cost</option>';
    const keep = $("#chObj").value;
    $("#chObj").innerHTML = opts;
    if (keep) $("#chObj").value = keep;
    renderLims(opts);
  }
  function renderSlots() {
    $("#chSlots").innerHTML = O.slots.map((s, i) => `<div class="rv-thread" data-slot="${i}">
      <div class="row"><b class="grow">${esc(s.name)}</b><span class="hint">now ${fmt(s.amount)} ${esc(s.unit)}${s.unit_cost !== null && s.unit_cost !== undefined ? ", cost " + fmt(s.unit_cost) + " per unit" : ", no cost"}</span><button class="ghost" data-optrm="${i}">Remove</button></div>
      <div class="table-wrap"><table><thead><tr><th>Alternative</th><th class="num">Amount</th><th>Unit</th><th class="num">Cost per unit</th><th></th></tr></thead><tbody>
      ${s.options.map((o, j) => `<tr data-opt="${j}"><td>${esc(o.label)}</td><td><input type="number" step="any" class="oa" value="${o.amount ?? ""}" size="8" aria-label="Amount"></td><td><input class="ou" value="${esc(o.unit || "")}" size="6" aria-label="Unit"></td><td><input type="number" step="any" class="oc" value="${o.unit_cost ?? ""}" size="7" aria-label="Cost per unit"></td><td><button class="ghost" data-optdel="${j}">Remove</button></td></tr>`).join("") || '<tr><td colspan="5" class="hint">Add alternatives: search the library or choose a model.</td></tr>'}
      </tbody></table></div>
      <div class="row"><input class="grow os" placeholder="Search the library for an alternative" aria-label="Search"><select class="om" aria-label="Or a model"><option value="">or a model of this project</option>${S.models.filter((m) => !S.model || m.id !== S.model.id).map((m) => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}</select></div>
      <ul class="results or"></ul></div>`).join("");
  }
  function renderLims(opts) {
    opts = opts || $("#chObj").innerHTML;
    $("#chLims").innerHTML = O.lims.map((l, i) => `<div class="row" data-lim="${i}"><span class="hint">Limit</span><select class="ld">${opts}</select><select class="lt"><option value="pct">no more than now plus %</option><option value="max">at most</option></select><input type="number" step="any" class="lv" value="${l.v ?? 0}" size="8" aria-label="Value"><button class="ghost" data-limrm="${i}">Remove</button></div>`).join("");
    O.lims.forEach((l, i) => { const r = $(`[data-lim="${i}"]`); if (l.d) $(".ld", r).value = l.d; $(".lt", r).value = l.t || "pct"; });
  }
  function readForm() {
    $$("#chSlots [data-slot]").forEach((d) => {
      const s = O.slots[Number(d.dataset.slot)];
      $$("tr[data-opt]", d).forEach((tr) => { const o = s.options[Number(tr.dataset.opt)]; o.amount = num($(".oa", tr).value); o.unit = $(".ou", tr).value.trim(); o.unit_cost = num($(".oc", tr).value); });
    });
    $$("#chLims [data-lim]").forEach((r) => { const l = O.lims[Number(r.dataset.lim)]; l.d = $(".ld", r).value; l.t = $(".lt", r).value; l.v = num($(".lv", r).value); });
  }
  const spec = (d) => (d === "cost" ? { cost: true } : { method_id: Number(d.slice(1)) });
  function body() {
    readForm();
    if (!S.model) throw new Error("Open a model first (step 2).");
    if (!S.selectedMethods.size) throw new Error("Pick the impact categories in step 4 first.");
    if (!O.slots.length) throw new Error("Add at least one line as a choice.");
    return { model_id: S.model.id, method_ids: [...S.selectedMethods], scenario: $("#scenarioSel").value || null, ...bgBody(),
      slots: O.slots.map((s) => ({ input_id: s.input_id, options: s.options.map((o) => ({ kind: o.kind, ref_id: o.ref_id, amount: o.amount, unit: o.unit, unit_cost: o.unit_cost, label: o.label })) })),
      objective: spec($("#chObj").value),
      constraints: O.lims.map((l) => ({ ...spec(l.d), ...(l.t === "max" ? { max: l.v } : { max_change_pct: l.v }) })) };
  }
  $("#btnChAddLine").addEventListener("click", (e) => guard(e.target, async () => {
    needModel();
    const id = Number($("#chLine").value);
    const l = S.model.inputs.find((x) => x.id === id);
    if (!l) throw new Error("Choose a line.");
    if (O.slots.some((s) => s.input_id === id)) throw new Error("This line is already a choice.");
    readForm();
    O.slots.push({ input_id: id, name: l.label || l.target.name, amount: l.input_amount, unit: l.input_unit || l.target.unit, unit_cost: l.unit_cost, options: [] });
    renderSlots();
  }));
  $("#btnChAddLim").addEventListener("click", () => { readForm(); O.lims.push({ d: "", t: "pct", v: 0 }); renderLims(); });
  $("#chLims").addEventListener("click", (e) => { const b = e.target.closest("[data-limrm]"); if (!b) return; readForm(); O.lims.splice(Number(b.dataset.limrm), 1); renderLims(); });
  let timer = null;
  $("#chSlots").addEventListener("input", (e) => {
    const inp = e.target.closest(".os"); if (!inp) return;
    const d = inp.closest("[data-slot]");
    clearTimeout(timer);
    timer = setTimeout(() => guard(null, async () => {
      if (inp.value.trim().length < 2) { $(".or", d).innerHTML = ""; return; }
      const { results } = await api("GET", "/api/search?q=" + encodeURIComponent(inp.value.trim()));
      $(".or", d).innerHTML = results.slice(0, 10).map((r) => `<li><button data-optpick="${r.id}" data-u="${esc(r.unit)}" data-n="${esc(r.name + " [" + r.location + "]")}"><span class="rname">${esc(r.name)}</span><span class="loc">${esc(r.location)}</span><span class="rmeta">${esc(r.product)}, ${esc(r.unit)}, ${esc(r.db)}</span></button></li>`).join("");
    }), 250);
  });
  $("#chSlots").addEventListener("change", (e) => {
    const sel = e.target.closest(".om"); if (!sel || !sel.value) return;
    const d = sel.closest("[data-slot]"); const s = O.slots[Number(d.dataset.slot)];
    const m = S.models.find((x) => x.id === Number(sel.value));
    readForm();
    s.options.push({ kind: "model", ref_id: m.id, label: m.name, amount: s.amount, unit: m.unit, unit_cost: null });
    renderSlots();
  });
  $("#chSlots").addEventListener("click", (e) => {
    const d = e.target.closest("[data-slot]"); if (!d) return;
    const s = O.slots[Number(d.dataset.slot)];
    const pick = e.target.closest("[data-optpick]");
    if (pick) { readForm(); s.options.push({ kind: "activity", ref_id: Number(pick.dataset.optpick), label: pick.dataset.n, amount: pick.dataset.u === s.unit ? s.amount : null, unit: pick.dataset.u, unit_cost: null }); renderSlots(); return; }
    const del = e.target.closest("[data-optdel]");
    if (del) { readForm(); s.options.splice(Number(del.dataset.optdel), 1); renderSlots(); return; }
    if (e.target.closest("[data-optrm]")) { readForm(); O.slots.splice(Number(d.dataset.slot), 1); renderSlots(); }
  });
  function row(c, r) {
    return `<tr><td>${c.choices.map((x) => esc(x.current ? "current" : x.choice)).join("<br>")}</td>${c.totals.map((t, k) => `<td class="num">${fmt(t)} <span class="meta">${esc(r.units[k])}</span></td>`).join("")}${r.has_cost ? `<td class="num">${fmt(c.cost)}</td>` : ""}`;
  }
  function render(r) {
    O.last = r;
    const head = `<tr><th>Choices (${r.lines.map((l) => esc(l.name)).join(" / ")})</th>${r.categories.map((c) => `<th class="num">${esc(c)}</th>`).join("")}${r.has_cost ? '<th class="num">Purchase cost</th>' : ""}<th></th></tr>`;
    const base = `<tr class="meta"><td>current model</td>${r.baseline.totals.map((t, k) => `<td class="num">${fmt(t)} <span class="meta">${esc(r.units[k])}</span></td>`).join("")}${r.has_cost ? `<td class="num">${fmt(r.baseline.cost)}</td>` : ""}<td></td></tr>`;
    $("#chOut").innerHTML = `<p class="hint">${r.combinations.toLocaleString()} combinations evaluated, ${r.feasible.toLocaleString()} within the limits. ${esc(r.note)}</p>` + (r.warnings || []).map((w) => `<p class="warn">${esc(w)}</p>`).join("") +
      (r.best ? `<h3>Best combination${r.ties ? ` (${r.ties} other combination(s) equal in the goal)` : ""}</h3><div class="table-wrap"><table><thead>${head}</thead><tbody>${base}${row(r.best, r)}<td><button data-optsave="best">Save as a model</button></td></tr></tbody></table></div>`
        : '<p class="warn">No combination meets every limit. Relax a limit or add alternatives.</p>') +
      `<h3>Pareto set (${r.pareto_size} combination(s)${r.pareto_size > r.pareto.length ? ", first " + r.pareto.length + " shown" : ""})</h3><div class="table-wrap"><table><thead>${head}</thead><tbody>${r.pareto.map((p, i) => row(p, r) + `<td>${p.feasible ? "" : '<span class="hint">outside a limit</span> '}<button class="ghost" data-optsave="${i}">Save as a model</button></td></tr>`).join("")}</tbody></table></div>`;
  }
  $("#btnChRun").addEventListener("click", (e) => guard(e.target, async () => { render(await api("POST", "/api/choices/optimise", body())); }));
  $("#chOut").addEventListener("click", (e) => {
    const b = e.target.closest("[data-optsave]"); if (!b || !O.last) return;
    const c = b.dataset.optsave === "best" ? O.last.best : O.last.pareto[Number(b.dataset.optsave)];
    guard(b, async () => {
      const choice = {}; c.choices.forEach((x) => (choice[x.input_id] = x.option));
      const r = await api("POST", "/api/choices/apply", { ...body(), choice });
      S.models = (await api("GET", "/api/models")).models;
      if (typeof renderModelSelect === "function") renderModelSelect();
      toast(`Saved as a new model (id ${r.model_id}). Compare it with the original in step 5 (comparative Monte Carlo).`);
    });
  });
  const _show = showToolTab;
  showToolTab = function (t) { _show.apply(this, arguments); if (t === "choices") { fillLines(); renderSlots(); } };
})();
