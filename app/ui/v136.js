/* Cyclia 1.3.6: database explorer. */
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
  async function search() {
    const qs = new URLSearchParams({ q: $("#exQ").value.trim(), db: $("#exDb").value, unresolved: $("#exUnres").checked ? "1" : "" });
    const { results } = await api("GET", "/api/explore?" + qs.toString());
    $("#exResults").innerHTML = results.length ? results.map((r) => `<li><button data-ex="${r.id}"><span class="rname">${esc(r.name)}</span><span class="loc">${esc(r.location || "")}</span><span class="rmeta">${esc(r.product || "")}, ${esc(r.unit || "")}, ${esc(r.db || "")}</span></button></li>`).join("")
      : '<li class="empty">No dataset found.</li>';
  }
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
  $("#btnExSearch").addEventListener("click", (e) => guard(e.target, search));
  $("#exQ").addEventListener("keydown", (e) => { if (e.key === "Enter") guard($("#btnExSearch"), search); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ex]");
    if (b && b.closest("#tt-explore")) guard(b, () => show(Number(b.dataset.ex)));
  });
})();
