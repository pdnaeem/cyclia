/* Cyclia 1.3.6: database explorer (1.3.8: filters in the query, paging, export of selected datasets). */
(function () {
  const _show = showToolTab;
  showToolTab = function (t) {
    _show.apply(this, arguments);
    if (t === "explore") {
      const dbs = (S.status && S.status.databases) || [];
      $("#exDb").innerHTML = '<option value="">All databases</option>' + dbs.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
    }
  };
  const unc = (x) => (x.uncertainty && x.uncertainty !== "none" ? `<span class="hint">${esc(x.uncertainty)}</span>` : "");
  const PAGE = 50;
  let offset = 0, total = 0;
  const picked = new Set();
  async function search(keep) {
    if (!keep) offset = 0;
    const qs = new URLSearchParams({ q: $("#exQ").value.trim(), db: $("#exDb").value, unresolved: $("#exUnres").checked ? "1" : "",
      location: $("#exLoc").value.trim(), system_model: $("#exSys").value.trim(), version: $("#exVer").value.trim(),
      flow: $("#exFlow").value.trim(), offset: String(offset), limit: String(PAGE) });
    const r = await api("GET", "/api/explore?" + qs.toString());
    total = r.total;
    $("#exResults").innerHTML = r.results.length ? r.results.map((x) => `<li><label class="inline"><input type="checkbox" data-pick="${x.id}"${picked.has(x.id) ? " checked" : ""}></label><button data-ex="${x.id}"><span class="rname">${esc(x.name)}</span><span class="loc">${esc(x.location || "")}</span><span class="rmeta">${esc(x.product || "")}, ${esc(x.unit || "")}, ${esc(x.db || "")}${x.version ? " v" + esc(x.version) : ""}${x.unresolved ? `, <span class="warn">${x.unresolved} unresolved</span>` : ""}</span></button></li>`).join("")
      : '<li class="empty">No dataset found.</li>';
    $("#exCount").textContent = total ? `${offset + 1} to ${offset + r.results.length} of ${total} datasets, ${picked.size} selected` : `0 datasets, ${picked.size} selected`;
    $("#btnExPrev").disabled = offset === 0;
    $("#btnExNext").disabled = offset + PAGE >= total;
  }
  const count = () => { $("#exCount").textContent = $("#exCount").textContent.replace(/\d+ selected$/, picked.size + " selected"); };
  $("#btnExPrev").addEventListener("click", (e) => guard(e.target, () => { offset = Math.max(0, offset - PAGE); return search(true); }));
  $("#btnExNext").addEventListener("click", (e) => guard(e.target, () => { offset += PAGE; return search(true); }));
  $("#btnExAll").addEventListener("click", () => { $$("#exResults [data-pick]").forEach((c) => { c.checked = true; picked.add(Number(c.dataset.pick)); }); count(); });
  $("#exResults").addEventListener("change", (e) => {
    const c = e.target.closest("[data-pick]");
    if (!c) return;
    const id = Number(c.dataset.pick);
    if (c.checked) picked.add(id); else picked.delete(id);
    count();
  });
  $("#btnExExport").addEventListener("click", (e) => guard(e.target, async () => {
    if (!picked.size) { toast("Tick the datasets to export first."); return; }
    await exportTo("/api/explore/export", "Cyclia_datasets.xlsx", "xlsx", { ids: [...picked] });
  }));
  ["#exLoc", "#exSys", "#exVer", "#exFlow"].forEach((s) => $(s).addEventListener("keydown", (e) => { if (e.key === "Enter") guard($("#btnExSearch"), () => search()); }));
  async function show(id) {
    const { activity: a } = await api("GET", "/api/explore/" + id);
    const dq = a.data_quality;
    $("#exDetail").innerHTML = `<h3>${esc(a.name)} <span class="hint">[${esc(a.location || "")}]</span></h3>
      <table><tbody>
        <tr><td>Reference product</td><td>${esc(a.product || "")} (${fmt(a.production)} ${esc(a.unit || "")})</td></tr>
        <tr><td>Database</td><td>${esc(a.db)}${a.db_version ? ", v" + esc(a.db_version) : ""}${a.system_model ? ", " + esc(a.system_model) : ""}</td></tr>
        <tr><td>Dataset key / UUID</td><td><code>${esc(a.key)}</code>${a.product_uuid ? ` <span class="hint">product ${esc(a.product_uuid)}</span>` : ""}</td></tr>
        <tr><td>Exchanges</td><td>${a.n_inputs} inputs, ${a.n_emissions} elementary flows, used by ${a.n_used_by} datasets</td></tr>
        ${dq ? `<tr><td>Data quality (1 very good to 5 very poor)</td><td>TeR ${dq.ter ?? "-"}, GeR ${dq.ger ?? "-"}, TiR ${dq.tir ?? "-"}, P ${dq.p ?? "-"}${dq.overall ? ", " + esc(dq.overall) : ""}</td></tr>` : ""}
      </tbody></table>
      ${a.comment ? `<p class="hint">${esc(a.comment.slice(0, 600))}</p>` : ""}
      ${a.unresolved.length ? `<h3>Inputs without a single supplier</h3><table><thead><tr><th>Product</th><th>Location</th><th class="num">Amount</th><th>Why</th><th>Status</th></tr></thead><tbody>${a.unresolved.map((u) => `<tr><td>${esc(u.product)}</td><td>${esc(u.location || "")}</td><td class="num">${fmt(u.amount)} ${esc(u.unit || "")}</td><td>${esc(u.reason || "no producer")}</td><td>${u.linked_to ? '<span class="ok">linked</span>' : '<span class="warn">open</span>'}</td></tr>`).join("")}</tbody></table>` : ""}
      <h3>Inputs (suppliers)</h3>${a.inputs.length ? `<table><thead><tr><th>Supplier</th><th>Location</th><th class="num">Amount</th><th>Uncertainty</th><th>Database</th></tr></thead><tbody>${a.inputs.map((x) => `<tr><td><button class="link" data-ex="${x.id}">${esc(x.name)}</button>${x.src_unlinked ? ' <span class="hint">(linked by you)</span>' : ""}</td><td>${esc(x.location || "")}</td><td class="num">${fmt(x.amount)} ${esc(x.unit || "")}</td><td>${unc(x)}</td><td>${esc(x.db)}</td></tr>`).join("")}</tbody></table>` : '<p class="empty">No technosphere inputs.</p>'}
      <h3>Used by</h3>${a.used_by.length ? `<table><tbody>${a.used_by.map((x) => `<tr><td><button class="link" data-ex="${x.id}">${esc(x.name)}</button></td><td>${esc(x.location || "")}</td><td class="num">${fmt(x.amount)}</td><td>${esc(x.db)}</td></tr>`).join("")}</tbody></table>${a.n_used_by > a.used_by.length ? `<p class="hint">${a.n_used_by - a.used_by.length} more not shown.</p>` : ""}` : '<p class="empty">No dataset uses it.</p>'}
      <h3>Elementary flows</h3>${a.emissions.length ? `<table><thead><tr><th>Flow</th><th>Compartment</th><th class="num">Amount</th><th>Uncertainty</th><th>UUID</th></tr></thead><tbody>${a.emissions.map((x) => `<tr><td>${esc(x.name)}${x.cas ? ` <span class="hint">CAS ${esc(x.cas)}</span>` : ""}</td><td>${esc([x.compartment, x.subcompartment].filter(Boolean).join("/"))}</td><td class="num">${fmt(x.amount)} ${esc(x.unit || "")}</td><td>${unc(x)}</td><td><code>${esc((x.uuid || "").slice(0, 36))}</code></td></tr>`).join("")}</tbody></table>` : '<p class="empty">No elementary flows.</p>'}`;
  }
  $("#btnExSearch").addEventListener("click", (e) => guard(e.target, () => search()));
  $("#exQ").addEventListener("keydown", (e) => { if (e.key === "Enter") guard($("#btnExSearch"), () => search()); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ex]");
    if (b && b.closest("#tt-explore")) guard(b, () => show(Number(b.dataset.ex)));
  });
})();
