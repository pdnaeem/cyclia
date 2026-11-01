/* Cyclia guidance: welcome screen, step-by-step coach, progress, author credit and citation.
   Uses the globals of app.js and features.js (S, $, $$, esc, api, go, ls, toast, refreshStatus, ...). */
"use strict";

const CR = window.CREDITS || { display_name: "Naeem Ur Rehman", initials: "NR", year: 2026 };
const ORDER = ["setup", "scope", "inventory", "impact", "results", "report"];
const NAMES = { setup: "Project and data", scope: "Goal and scope", inventory: "Inventory", impact: "Impact assessment",
  results: "Interpretation", report: "Report", tools: "Toolbox" };
const level = () => ls.get("cyclia.level", "new");
const coachOn = () => ls.get("cyclia.coach", true);

/* ---------------- what each step asks of the user ---------------- */
const hasErrors = () => S.result && S.result.checks.some((c) => c.level === "error");
const COACH = {
  setup: {
    iso: "Preparation",
    what: "Every LCA needs three things before you start: a project that stores your work, a background database that says how materials and energy are produced, and an impact method that turns emissions into impacts such as climate change.",
    example: "A thesis comparing cotton and polyester T-shirts: project \"T-shirt study\", database ecoinvent 3.11 cut-off, method EF 3.1.",
    tasks: [
      ["Create or open a project", (st) => !!st.project, "#newProjectName", "Type a name above and press Create project. Projects are saved automatically."],
      ["Add a background database", (st) => (st.databases || []).length > 0, "#btnTutorial", "No ecoinvent licence? Open \"Tutorial database\" and press Add. It is free and built in."],
      ["Check that impact methods are installed", (st) => st.n_methods > 0, "#methodFamilies", "The tutorial database brings its own methods. With ecoinvent, import the LCIA file or use \"EF 3.1 from the JRC\"."],
    ],
    mistakes: ["Mixing system models (cut-off, APOS, consequential) in one study.",
      "Publishing results made with the tutorial or demo data. They are simplified, for learning only."],
  },
  scope: {
    iso: "ISO 14044, 4.2",
    what: "Say what you study and why. The functional unit is the reference of the whole study: every amount in the inventory is given per functional unit, so two products are only comparable if they deliver the same function.",
    example: "Functional unit: 1 kWh of electricity delivered to a household by rooftop solar panels. Boundary: cradle-to-grave. Other examples: 1 kg of bread at the bakery gate, 1 m3 of wastewater treated, 1 m2 of wall over 50 years.",
    tasks: [
      ["Fill in the functional unit: amount, unit and product", () => !!(S.model && S.model.unit && S.model.product), "[name=unit]", "Type in the form below. Nothing is stored until you press Save goal & scope. Or press \"Start from a template\"."],
      ["Write the goal of the study", () => !!(S.model && S.model.scope && S.model.scope.goal), "[name=goal]", "One or two sentences: what question will the study answer?"],
      ["Choose the system boundary", () => !!(S.model && S.model.scope && S.model.scope.boundary), "[name=boundary]", "Cradle-to-gate stops at the factory gate; cradle-to-grave includes use and end of life."],
      ["Save goal and scope", () => !!S.model, "#scopeForm button[type=submit]", "This creates the model. You can change everything later."],
    ],
    mistakes: ["A functional unit without performance, for example \"1 kg of insulation\" when the insulations compared have different thicknesses.",
      "Not stating why the study is done and for whom. Reviewers always ask for it."],
  },
  inventory: {
    needs: () => !S.model && ["This step needs a model. Describe what you study in step 2 first.", "scope"],
    iso: "ISO 14044, 4.3",
    what: "List every input (materials, energy, transport) and every direct output (emissions, waste) needed for one functional unit. Search a dataset, click it, then type the amount.",
    example: "For 1 kg of bread: 0.65 kg wheat flour, 0.4 kg tap water, 2.5 MJ natural gas and 0.3 kWh electricity for baking, transport to the shop.",
    tasks: [
      ["Add the first input: search, click a dataset, type the amount", () => !!(S.model && S.model.inputs.length), "#searchBox", "Try a word like cement, electricity or lorry. The region box prefers local datasets."],
      ["Add every material, energy and transport (at least three lines)", () => !!(S.model && S.model.inputs.length >= 3), "#searchBox", "Think through the life cycle: production, transport, use, end of life."],
      ["Put each line in a life cycle stage", () => !!(S.model && S.model.inputs.length && S.model.inputs.every((i) => i.stage)), "#invRows", "Stages make the results readable, for example A1-A3, A4, CR."],
      ["Resolve lines without a dataset", () => !!(S.model && S.model.inputs.length && !S.model.inputs.some((i) => i.missing)), "#invRows", "A line marked missing has no link to a database. Click Replace on it."],
      ["Rate the data quality of your main lines", () => !!(S.model && S.model.inputs.some((i) => (i.pedigree || []).join() !== "3,3,3,3,3")), "#invRows", "The pedigree scores feed the uncertainty analysis."],
    ],
    mistakes: ["Amounts per kg of product while the functional unit is per m2.",
      "Leaving out transport or end of life without saying so in the scope.",
      "Taking a dataset from another region when a local one exists."],
  },
  impact: {
    needs: () => !S.model ? ["This step needs a model. Describe what you study in step 2 first.", "scope"]
      : !S.model.inputs.length && ["The inventory is empty. Add at least one input in step 3 first.", "inventory"],
    iso: "ISO 14044, 4.4",
    what: "Choose the impact categories, then press Calculate. Cyclia multiplies the full supply chain of your inventory with the characterisation factors of the method.",
    example: "Climate change (kg CO2-eq) is the usual first category. EF 3.1 is the EU reference set; add the categories your goal needs.",
    tasks: [
      ["Pick at least one impact category", () => S.selectedMethods.size > 0, "#methodPicker", "Tick a category; one method family per indicator."],
      ["Press Calculate", () => !!S.result, "#btnCalc", "Takes a second for the tutorial data, longer for ecoinvent the first time."],
    ],
    mistakes: ["Mixing method families for the same indicator.",
      "Reporting only climate change when the goal speaks of \"environmental impact\"."],
  },
  results: {
    needs: () => !S.model ? ["This step needs a model. Describe what you study in step 2 first.", "scope"]
      : !S.result && ["There is nothing to interpret yet. Choose impact categories and press Calculate in step 4.", "impact"],
    iso: "ISO 14044, 4.5",
    what: "Interpretation means finding what drives the result and testing how reliable it is. Read the totals, then the hotspots, then the checks and the sensitivity.",
    example: "\"Nitrogen fertiliser causes most of the climate impact of the wheat; using 10 % less fertiliser lowers the total noticeably, while transport hardly matters.\"",
    tasks: [
      ["Read the totals per functional unit", () => !!S.result, "#totals", "Every number is per functional unit, as defined in step 2."],
      ["Find the largest contributors (hotspots)", () => !!S.result, "[data-rt=contrib]", "The Contributions tab ranks inputs, processes and emissions."],
      ["Open Checks and solve every error", () => !!S.result && !hasErrors() && ls.get("cyclia.seen.checks", false), "[data-rt=checks]", "Checks follow ISO 14044 4.5.3: completeness, consistency, sensitivity."],
      ["Test robustness in Sensitivity", () => !!S.result && ls.get("cyclia.seen.sens", false), "[data-rt=sens]", "Shows which inputs change the result most if they are wrong."],
    ],
    mistakes: ["Treating a 5 % difference as real when the uncertainty is ±20 %.",
      "Accepting a hotspot without asking whether its dataset fits your case."],
  },
  report: {
    needs: () => !S.model && ["This step needs a model. Describe what you study in step 2 first.", "scope"],
    iso: "ISO 14044, 5",
    what: "Write what the results mean, their limits and what you recommend. Cyclia then writes an ISO 14044-structured Word report and a methods paragraph you can paste into your thesis.",
    example: "Limitation: \"Cotton yields come from one growing region and may not represent cotton from elsewhere.\"",
    tasks: [
      ["Write the conclusions", () => !!(S.model && S.model.scope && S.model.scope.conclusions), "[name=conclusions]", "Answer the question you set in the goal."],
      ["Write the limitations", () => !!(S.model && S.model.scope && S.model.scope.limitations), "[name=limitations]", "Data gaps, assumptions, what the boundary leaves out."],
      ["Create the Word report", () => $("#exports").children.length > 0, "#btnWord", "Press Save text first, then Create Word report."],
    ],
    mistakes: ["Conclusions that go beyond the system boundary.",
      "Comparative claims made public without a critical review (ISO 14044 6.3)."],
  },
  tools: {
    iso: "Advanced",
    what: "Extra tools for advanced work: validation against ecoinvent, future background scenarios, your own chemicals and toxicity factors, model templates, Python and R access, and teaching material.",
    tasks: [],
  },
};

/* ---------------- coach card and next bar ---------------- */
function coachSlot(step) {
  const view = $("#view-" + step);
  if (!view) return null;
  let el = $(".coach", view);
  if (!el) {
    el = document.createElement("details");
    el.className = "coach";
    el.addEventListener("toggle", () => {
      ls.set("cyclia.coachOpen", el.open);
      const m = $(".coach-more", el);
      if (m) m.textContent = el.open ? "Hide" : "What to do here";
    });
    const anchor = $(".lead", view) || $("h1", view);
    anchor.insertAdjacentElement("afterend", el);
    const bar = document.createElement("div");
    bar.className = "next-bar";
    view.appendChild(bar);
  }
  return el;
}

function stepProgress(step) {
  const c = COACH[step];
  const st = S.status || {};
  const done = c.tasks.map((t) => { try { return !!t[1](st); } catch (e) { return false; } });
  return { done, n: done.filter(Boolean).length, total: done.length };
}

function renderCoach() {
  const step = S.step;
  const c = COACH[step];
  renderRailProgress();
  if (!c) return;
  const el = coachSlot(step);
  if (!el) return;
  const on = coachOn();
  $("#coachToggle").textContent = on ? "Guidance on" : "Guidance off";
  $("#coachToggle").setAttribute("aria-pressed", String(on));
  el.hidden = !on || step === "tools";
  const { done, n, total } = stepProgress(step);
  const idx = ORDER.indexOf(step);
  const stepLabel = idx >= 0 ? `Step ${idx + 1} of 6` : "Toolbox";
  if (!el.dataset.init) {
    el.open = ls.get("cyclia.coachOpen", level() === "new");
    el.dataset.init = "1";
  }
  const blocked = c.needs ? c.needs() : null;
  const nextTodo = blocked ? -1 : done.indexOf(false);
  el.innerHTML = `
    <summary><span class="coach-step">${stepLabel}</span><b>${esc(NAMES[step])}</b><span class="coach-iso">${esc(c.iso)}</span>
      ${total ? `<span class="coach-count ${n === total ? "ok" : ""}">${n === total ? "All done" : `${n} of ${total} done`}</span>` : ""}
      <a href="#" class="coach-guide" data-guide="${window.guideAnchorFor ? window.guideAnchorFor(step) : ""}" title="Open the user guide at this step">Guide</a>
      <span class="coach-more">${el.open ? "Hide" : "What to do here"}</span></summary>
    <div class="coach-body">
      <div class="coach-main">
        <p class="coach-what">${esc(c.what)}</p>
        ${c.example ? `<p class="coach-ex"><b>Example</b>${esc(c.example)}</p>` : ""}
        ${c.mistakes ? `<details class="coach-mist"><summary>Common mistakes</summary><ul>${c.mistakes.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></details>` : ""}
      </div>
      ${blocked ? `<div class="coach-block"><p>${esc(blocked[0])}</p><button class="primary" type="button" data-goto="${blocked[1]}">Go to step ${ORDER.indexOf(blocked[1]) + 1}: ${esc(NAMES[blocked[1]])}</button></div>` : ""}
      ${total && !blocked ? `<ol class="coach-tasks">${c.tasks.map((t, i) => `
        <li class="${done[i] ? "done" : ""}${i === nextTodo ? " now" : ""}"><button type="button" data-spot="${esc(t[2])}">
          <span class="tick" aria-hidden="true"></span><span><span class="sr">${done[i] ? "Done: " : "To do: "}</span>${esc(t[0])}${i === nextTodo ? `<small>${esc(t[3])}</small>` : ""}</span>
          ${i === nextTodo ? '<span class="show-me">Show me</span>' : ""}</button></li>`).join("")}</ol>` : ""}
    </div>`;
  renderNextBar(step, n, total);
}
window.renderCoach = renderCoach;

function renderNextBar(step, n, total) {
  const bar = $(`#view-${step} .next-bar`);
  if (!bar) return;
  const i = ORDER.indexOf(step);
  if (i < 0) { bar.innerHTML = `<button class="ghost" data-goto="setup">Back to step 1</button>`; return; }
  const prev = ORDER[i - 1], next = ORDER[i + 1];
  const status = total ? (n === total ? "This step is complete." : `${total - n} task${total - n > 1 ? "s" : ""} left in this step. You can go on anyway and come back.`) : "";
  bar.innerHTML = `${prev ? `<button class="ghost" data-goto="${prev}">&larr; ${esc(NAMES[prev])}</button>` : "<span></span>"}
    <span class="grow hint">${esc(status)}</span>
    ${next ? `<button class="${n === total ? "primary" : ""}" data-goto="${next}">Next: ${esc(NAMES[next])} &rarr;</button>`
      : `<span class="finish">${n === total ? `You finished all six steps of an LCA. Well done.${supportLinks() ? ` <span class="finish-support">Cyclia is free and unfunded; if it helped you, ${supportLinks("inline")}</span>` : ""}` : ""}</span>`}`;
}

function renderRailProgress() {
  const n = $$("#steps li.done").length;
  const el = $("#railProgress");
  if (!el) return;
  el.innerHTML = `<div class="pm-bar"><span style="width:${(n / 6) * 100}%"></span></div><span>${n} of 6 steps done</span>`;
}

document.addEventListener("click", (e) => {
  const g = e.target.closest("[data-goto]");
  if (g) { go(g.dataset.goto); return; }
  const sp = e.target.closest("[data-spot]");
  if (sp) spotlight(sp.dataset.spot);
});
$("#coachToggle").addEventListener("click", () => { ls.set("cyclia.coach", !coachOn()); renderCoach(); });
$("#resTabs").addEventListener("click", (e) => {
  const b = e.target.closest("[data-rt]");
  if (b) { ls.set("cyclia.seen." + b.dataset.rt, true); renderCoach(); }
});

/* Scroll to an element, open the panel it sits in, and make it pulse. */
function spotlight(sel) {
  const el = $(`#view-${S.step} ${sel}`) || $(sel);
  if (!el) return;
  for (let p = el.parentElement; p; p = p.parentElement) if (p.tagName === "DETAILS" && !p.classList.contains("coach")) p.open = true;
  if (el.hidden) { toast("This appears after the previous task is done."); return; }
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  if (el.dataset.rt) el.click();
  el.classList.remove("spot");
  void el.offsetWidth;
  el.classList.add("spot");
  setTimeout(() => el.classList.remove("spot"), 2400);
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) setTimeout(() => el.focus({ preventScroll: true }), 350);
}

/* ---------------- welcome ---------------- */
function wPage(n) { $$("#welcome [data-wp]").forEach((p) => (p.hidden = p.dataset.wp !== String(n))); }
function openWelcome() {
  $("#welcome").hidden = false;
  wPage(1);
  setTimeout(() => { const b = $("#welcome [data-level]"); if (b) b.focus(); }, 50);
}
function closeWelcome() { $("#welcome").hidden = true; ls.set("cyclia.welcomed", true); }
window.maybeWelcome = () => { if (!ls.get("cyclia.welcomed", false)) openWelcome(); };

$$("#welcome [data-level]").forEach((b) => b.addEventListener("click", () => {
  ls.set("cyclia.level", b.dataset.level);
  ls.set("cyclia.coach", true);
  ls.set("cyclia.coachOpen", b.dataset.level === "new");
  $$(".coach").forEach((el) => delete el.dataset.init);
  wPage(2);
}));
$("#welcome [data-wback]").addEventListener("click", () => wPage(1));
$("#welcome [data-wskip]").addEventListener("click", () => { closeWelcome(); go("setup"); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#welcome").hidden && $("#welcome [data-wp='3']").hidden) { closeWelcome(); renderCoach(); }
});

async function waitJob(id, label) {
  for (;;) {
    const { job } = await api("GET", "/api/jobs/" + id);
    $("#wBusyText").textContent = job.message || label;
    $("#wBusyBar").value = job.progress || 5;
    if (job.status === "running") { await new Promise((r) => setTimeout(r, 600)); continue; }
    if (job.status !== "done") throw new Error(job.error || `${label} stopped.`);
    return job;
  }
}
async function uniqueName(base) {
  const { projects } = await api("GET", "/api/projects");
  const names = new Set(projects.map((p) => p.name));
  let name = base, i = 2;
  while (names.has(name)) name = `${base} ${i++}`;
  return name;
}

$$("#welcome [data-start]").forEach((b) => b.addEventListener("click", async () => {
  const how = b.dataset.start;
  if (how === "own") {
    closeWelcome(); go("setup");
    setTimeout(() => spotlight("#newProjectName"), 200);
    return;
  }
  wPage(3);
  try {
    if (how === "learn") {
      $("#wBusyTitle").textContent = "Preparing \"My first LCA\"";
      const name = await uniqueName("My first LCA");
      await api("POST", "/api/projects", { name });
      const st = await api("GET", "/api/status");
      if (!(st.databases || []).some((d) => d.name.startsWith("Tutorial database"))) {
        const { job } = await api("POST", "/api/import/tutorial");
        await waitJob(job.id, "Adding the tutorial database");
      }
      S.result = null; S.model = null;
      await refreshStatus();
      closeWelcome();
      go("scope");
      toast("Step 1 is done for you: a project, the tutorial database and its methods. Now describe what you study.");
      setTimeout(() => spotlight("#btnNewModel"), 400);
    } else {
      $("#wBusyTitle").textContent = "Loading the full demo";
      const { job } = await api("POST", "/api/demo");
      const j = await waitJob(job.id, "Loading the demo");
      S.result = null; S.model = null;
      await refreshStatus();
      S.selectedMethods = new Set(j.result.methods); saveMethodSel();
      ls.set(projKey("nw"), DEMO_NW);
      if ([...$("#nwSet").options].some((o) => o.value === DEMO_NW)) $("#nwSet").value = DEMO_NW;
      const wall = S.models.find((m) => m.name === "Concrete wall (demo)");
      if (wall) await loadModel(wall.id);
      closeWelcome();
      go("scope");
      openHelp("tour");
      toast("Demo loaded. The Feature tour on the right takes you to every feature.");
    }
    if (level() === "teach") setTimeout(() => toast("Teaching tools: Toolbox > Teaching (exercises, answer keys)."), 3500);
  } catch (e) {
    wPage(2);
    toast(e.message, true);
  }
}));

/* ---------------- author credit and citation ---------------- */
function avatarHtml() {
  return CR.photo ? `<img src="${esc(CR.photo)}" alt="${esc(CR.display_name)}">` : `<span>${esc(CR.initials || "")}</span>`;
}
function version() { return (S.status && S.status.version) || CR.version || ""; }
function citeLink() {
  if (CR.doi) return "https://doi.org/" + CR.doi.replace(/^https?:\/\/doi\.org\//, "");
  return CR.repository || CR.website || "";
}
function apa() {
  const l = citeLink();
  return `${CR.cite_name} (${CR.year}). <i>${esc(CR.software_title)}</i> (version ${esc(version())}) [Computer software].${l ? " " + esc(l) : ""}`;
}
function bibtex() {
  const l = citeLink();
  return `@software{cyclia_${CR.year},
  author  = {${CR.family_name}, ${CR.given_name}},
  title   = {${CR.software_title}},
  year    = {${CR.year}},
  version = {${version()}},
  license = {MIT}${CR.doi ? `,\n  doi     = {${CR.doi}}` : ""}${l ? `,\n  url     = {${l}}` : ""}
}`;
}
async function copy(text, what) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
    document.execCommand("copy"); t.remove();
  }
  toast(`${what} copied.`);
}

const LINKS = [
  ["website", "Website", (v) => v],
  ["email", "E-mail", (v) => "mailto:" + v],
  ["orcid", "ORCID", (v) => (/^https?:/.test(v) ? v : "https://orcid.org/" + v)],
  ["google_scholar", "Google Scholar", (v) => v],
  ["researchgate", "ResearchGate", (v) => v],
  ["linkedin", "LinkedIn", (v) => v],
  ["github", "GitHub", (v) => (/^https?:/.test(v) ? v : "https://github.com/" + v)],
  ["repository", "Source code", (v) => v],
];
function supportLinks(cls = "") {
  return [["paypal", "Support with PayPal"], ["revolut", "Support with Revolut"]].filter(([k]) => CR[k])
    .map(([k, label]) => `<a class="pay-btn ${cls}" href="${esc(CR[k])}" target="_blank" rel="noopener">${label}</a>`).join("");
}
window.renderAuthorCard = function () {
  const links = LINKS.filter(([k]) => CR[k]).map(([k, label, url]) =>
    `<a href="${esc(url(CR[k]))}" target="_blank" rel="noopener">${esc(label)}</a>`).join("");
  $("#authorCard").innerHTML = `
    <div class="ac-head"><span class="avatar big" data-avatar>${avatarHtml()}</span>
      <div><small>Created by</small><h3>${esc(CR.display_name)}</h3>
        <p>${esc([CR.role, CR.title && CR.role ? CR.title[0].toLowerCase() + CR.title.slice(1) : CR.title].filter(Boolean).join(", "))}</p>
        ${(CR.affiliations || []).map((a) => `<p class="hint">${esc(a)}</p>`).join("")}</div></div>
    ${CR.bio ? `<p>${esc(CR.bio)}</p>` : ""}
    ${links ? `<div class="ac-links">${links}</div>` : ""}
    ${(CR.contributors || []).length ? `<p class="hint">Contributors: ${CR.contributors.map((p) => esc(typeof p === "string" ? p : `${p.given_name || ""} ${p.family_name || ""}`.trim())).join(", ")}</p>` : ""}`;
  $("#citeApa").innerHTML = apa();
  const pay = supportLinks();
  $("#supportBox").hidden = !pay;
  $("#supportNote").textContent = CR.support_note || "";
  $("#supportLinks").innerHTML = pay;
  const ack = [CR.funding, CR.acknowledgements].filter(Boolean).join(" ");
  $("#ackText").hidden = !ack;
  $("#ackText").textContent = ack;
};
$("#btnCopyApa").addEventListener("click", () => copy($("#citeApa").textContent, "Citation"));
$("#btnCopyBib").addEventListener("click", () => copy(bibtex(), "BibTeX"));
$("#btnCopyMethods").addEventListener("click", () => copy(
  `The life cycle assessment was modelled and calculated in Cyclia version ${version()} (${CR.family_name}, ${CR.year}), free and open-source LCA software.`, "Methods sentence"));
$("#btnWelcomeAgain").addEventListener("click", () => { $("#help").hidden = true; openWelcome(); });
$("#creditLink").addEventListener("click", () => openHelp("about"));

function paintCredit() {
  $$("[data-avatar]").forEach((el) => (el.innerHTML = avatarHtml()));
  $$("[data-credit-name]").forEach((el) => (el.textContent = CR.display_name));
  $$("[data-support-mail]").forEach((el) => (el.textContent = CR.support_email || "support@niellosoft.com"));
  const role = [CR.title, (CR.affiliations || [])[0]].filter(Boolean).join(", ");
  $("#wRole").textContent = role;
}
paintCredit();
renderCoach();

/* ---------------- updates ---------------- */
const UPD_MANUAL = { mac: "On macOS, download new versions from the releases page (automatic updates need a signed app).",
  deb: "This copy was installed from the .deb package: download new versions from the releases page.",
  "development build": "Development build: updates are not checked." };
let lastUpd = "";
function paintUpdate(u) {
  if (!u) return;
  const v = u.version ? `Cyclia ${u.version}` : "Cyclia";
  const text = {
    idle: "Updates are checked when Cyclia starts and every few hours.",
    checking: "Checking for a new version...",
    current: "You have the latest version.",
    downloading: `Downloading Cyclia ${u.next || ""}${u.percent ? ` (${u.percent} %)` : ""}. You can keep working.`,
    ready: `Cyclia ${u.next} is ready. Restart to install it, or it installs when you close Cyclia.`,
    manual: UPD_MANUAL[u.reason] || "Download new versions from the releases page.",
    error: `The update check did not work (${u.error || "no connection"}). You can download the latest version from the releases page.`,
  }[u.state] || "";
  $("#updTitle").textContent = v;
  $("#updText").textContent = " " + text;
  $("#btnUpdInstall").hidden = u.state !== "ready";
  $("#btnUpdCheck").textContent = ["manual", "error"].includes(u.state) ? "Open the releases page" : "Check for updates";
  $("#btnUpdCheck").disabled = u.state === "checking" || u.state === "downloading";
  if (u.state !== lastUpd) {
    if (u.state === "downloading" && u.next) toast(`A new version, Cyclia ${u.next}, is downloading in the background.`);
    if (u.state === "ready") toast(`Cyclia ${u.next} is ready to install.`);
    lastUpd = u.state;
  }
}
if (desktop && desktop.onUpdate) {
  desktop.onUpdate(paintUpdate);
  desktop.updateState().then(paintUpdate).catch(() => {});
} else {
  $("#btnUpdCheck").textContent = "Open the releases page";
}
$("#btnUpdCheck").addEventListener("click", async () => {
  const st = $("#btnUpdCheck").textContent;
  if (!desktop || !desktop.checkUpdates || st === "Open the releases page") {
    if (desktop && desktop.openReleases) desktop.openReleases(); else window.open("https://github.com/pdnaeem/cyclia/releases/latest", "_blank");
    return;
  }
  paintUpdate({ state: "checking" });
  paintUpdate(await desktop.checkUpdates());
});
$("#btnUpdInstall").addEventListener("click", () => desktop && desktop.installUpdate && desktop.installUpdate());
