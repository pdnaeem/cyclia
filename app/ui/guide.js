/* In-app user guide: renders guide.md (a copy of docs/USER_GUIDE.md made by the build) with a small,
   safe Markdown reader: headings, paragraphs, lists, tables, rules, bold, italic, code and links. */
"use strict";

const GUIDE_ANCHOR = { setup: "step-1-project-and-data", scope: "step-2-goal-and-scope", inventory: "step-3-inventory",
  impact: "step-4-impact-assessment", results: "step-5-interpretation", report: "step-6-report", tools: "toolbox" };
let guideLoaded = false;

const slug = (t) => t.toLowerCase().replace(/<[^>]+>/g, "").replace(/[^a-z0-9 -]/g, "").trim().replace(/\s+/g, "-");

function mdInline(t) {
  let s = esc(t);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, txt, url) => url.startsWith("#")
    ? `<a href="${url}" data-gjump="${url.slice(1)}">${txt}</a>`
    : `<a href="${url}" target="_blank" rel="noopener">${txt}</a>`);
  s = s.replace(/(^|[\s(])(https:\/\/[^\s<)]+[^\s<).,])/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  return s;
}

function mdRender(src) {
  const lines = src.replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  const isTable = (l) => /^\s*\|.*\|\s*$/.test(l);
  const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    let m;
    if ((m = /^(#{1,4})\s+(.*)$/.exec(l))) {
      const n = m[1].length, txt = m[2];
      out.push(`<h${n + 1} id="g-${slug(txt)}">${mdInline(txt)}</h${n + 1}>`);
      i++; continue;
    }
    if (/^---+\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (isTable(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
      const head = cells(l);
      i += 2;
      const rows = [];
      while (i < lines.length && isTable(lines[i])) rows.push(cells(lines[i++]));
      out.push(`<div class="table-wrap"><table><thead><tr>${head.map((h) => `<th>${mdInline(h)}</th>`).join("")}</tr></thead><tbody>` +
        rows.map((r) => `<tr>${r.map((c) => `<td>${mdInline(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>");
      continue;
    }
    if ((m = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(l))) {
      const ordered = /\d/.test(m[2]);
      const start = ordered ? parseInt(m[2], 10) : 1;
      const items = [];
      while (i < lines.length) {
        const mm = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(lines[i]);
        if (mm && /\d/.test(mm[2]) === ordered && mm[1].length < 2) { items.push(mm[3]); i++; continue; }
        if (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length) { items[items.length - 1] += " " + lines[i].trim(); i++; continue; }
        break;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}${ordered && start !== 1 ? ` start="${start}"` : ""}>${items.map((x) => `<li>${mdInline(x)}</li>`).join("")}</${tag}>`);
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|---+\s*$|\s*([-*]|\d+\.)\s)/.test(lines[i]) && !isTable(lines[i])) para.push(lines[i++].trim());
    out.push(`<p>${mdInline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

async function loadGuide() {
  if (guideLoaded) return;
  const box = $("#guideDoc");
  try {
    const r = await fetch("guide.md", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    box.innerHTML = mdRender(await r.text());
    guideLoaded = true;
  } catch (e) {
    box.innerHTML = '<p class="hint">The guide could not be opened. It is also online at https://github.com/pdnaeem/cyclia/blob/main/docs/USER_GUIDE.md</p>';
  }
}

window.openGuide = async function (anchor) {
  openHelp("manual");
  await loadGuide();
  const el = anchor && document.getElementById("g-" + anchor);
  const pane = $("#help");
  if (el) {
    pane.scrollTop = el.offsetTop - 70;
    el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600);
  } else pane.scrollTop = 0;
};
window.guideAnchorFor = (step) => GUIDE_ANCHOR[step] || "";

document.addEventListener("click", (e) => {
  const j = e.target.closest("[data-gjump]");
  if (j) { e.preventDefault(); window.openGuide(j.dataset.gjump); return; }
  const g = e.target.closest("[data-guide]");
  if (g) { e.preventDefault(); e.stopPropagation(); window.openGuide(g.dataset.guide); }
});
$("#guideSearch").addEventListener("input", () => {
  const q = $("#guideSearch").value.trim().toLowerCase();
  $$("#guideDoc > *").forEach((el) => { el.hidden = !!q && !el.textContent.toLowerCase().includes(q) && !/^H[2-5]$/.test(el.tagName); });
});
