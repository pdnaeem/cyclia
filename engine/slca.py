"""Social life cycle assessment: worker-hour based social risk screening (Cyclia 1.3.5).

Separate from the environmental LCIA. Follows the structure of the UNEP Guidelines for Social LCA (2020) and
ISO 14075:2024 (stakeholder categories and subcategories), with the activity-variable approach of social risk
databases such as PSILCA and SOCA:

1. every process of the supply chain gets an activity variable, the worker hours needed per unit of its
   reference product, and a risk level per social indicator (from a social database for its country and sector,
   or from your own assessment);
2. the engine's scaling vector gives the output of every process per functional unit, so worker hours per
   functional unit are hours = output x worker hours per unit;
3. risk hours (medium-risk-hour equivalents) = hours x risk factor of the level (by default very low 0.01, low
   0.1, medium 1, high 10, very high 100, no risk 0, as in PSILCA's characterisation; editable).

The result is a screening of where social risks lie in the supply chain (hotspots), not a measurement of social
performance. Cyclia ships no social data: import your licensed PSILCA/SOCA extract or your own data with the
template below. The demo data are invented and only show the workflow.
"""
import csv
import io
import os

import numpy as np

import calc

STAKEHOLDERS = ("workers", "local community", "society", "consumers", "value chain actors", "children")
RISK_FACTORS = {"no risk": 0.0, "very low": 0.01, "low": 0.1, "medium": 1.0, "high": 10.0, "very high": 100.0}
TEMPLATE = ("match,location,worker_hours,stakeholder,indicator,risk,source\n"
            "cement production,CN,0.012,workers,Fair salary,high,(example row: replace with your data)\n")


def import_data(store, text, source="", replace=True, demo=False):
    rdr = csv.DictReader(io.StringIO(text))
    cols = {c.strip().lower(): c for c in (rdr.fieldnames or []) if c}
    for need in ("match", "worker_hours", "stakeholder", "indicator", "risk"):
        if need not in cols:
            raise ValueError("The social data table needs the columns match, location, worker_hours, stakeholder, "
                             "indicator, risk (and source).")
    rows, rejected = [], []
    for n, r in enumerate(rdr, 2):
        match = str(r.get(cols["match"]) or "").strip()
        loc = str(r.get(cols.get("location", "")) or "").strip().upper() if "location" in cols else ""
        try:
            wh = float(str(r.get(cols["worker_hours"]) or "").replace(",", "."))
        except ValueError:
            rejected.append({"row": n, "reason": "worker_hours is not a number"})
            continue
        st = str(r.get(cols["stakeholder"]) or "").strip().lower()
        ind = str(r.get(cols["indicator"]) or "").strip()
        risk = str(r.get(cols["risk"]) or "").strip().lower()
        if not match:
            rejected.append({"row": n, "reason": "match is empty (use * for a default row)"})
            continue
        if wh < 0:
            rejected.append({"row": n, "reason": "worker hours cannot be negative"})
            continue
        if st not in STAKEHOLDERS:
            rejected.append({"row": n, "reason": f"stakeholder must be one of {', '.join(STAKEHOLDERS)}"})
            continue
        if risk not in RISK_FACTORS:
            rejected.append({"row": n, "reason": f"risk must be one of {', '.join(RISK_FACTORS)}"})
            continue
        if not ind:
            rejected.append({"row": n, "reason": "indicator is empty"})
            continue
        src = "demo: invented data, only to show the workflow" if demo else (
            str(r.get(cols["source"]) or "").strip() if "source" in cols else "") or source or "imported"
        rows.append((match, loc, wh, st, ind, risk, src))
    if not rows:
        raise ValueError("No valid rows." + (f" {len(rejected)} rows were rejected." if rejected else ""))
    with store.lock:
        if replace:
            store.conn.execute("DELETE FROM slca_data")
        store.conn.executemany("INSERT INTO slca_data(match,location,worker_hours,stakeholder,indicator,risk,source) "
                               "VALUES(?,?,?,?,?,?,?)", rows)
        store.conn.commit()
    return {"rows": len(rows), "rejected": rejected[:200], "n_rejected": len(rejected)}


def _assign(acts, data):
    """Data rows for each activity: the most specific 'match' (exact key, else the longest name fragment), with a
    location-specific row preferred over one without location."""
    by_match = {}
    for r in data:
        by_match.setdefault((r["match"].lower(), r["location"] or ""), []).append(r)
    keys = sorted(by_match, key=lambda k: (-len(k[0]), k[1] == ""))
    out = {}
    for a in acts:
        name, key, loc = (a["name"] or "").lower(), (a["key"] or "").lower(), (a["location"] or "").upper()
        for m, l in keys:
            if l and l != loc:
                continue
            if m == key or m in name:
                out[a["id"]] = by_match[(m, l)]
                break
    return out


def assess(store, model_id, factors=None):
    """Worker hours and risk hours per functional unit.

    Activity level of a process = |s_i x production_i| (output, or waste treated by a treatment dataset), with s
    solved for the lines used alone; a process runs when s_i > 0 and is avoided when s_i < 0. The avoided products
    (lines marked avoided) are solved separately, their hours are reported separately and are NOT netted against or
    added to the totals.
    Coverage: worker hours are only known for processes with data, so the share of the supply chain's worker hours
    with data cannot be known unless every process has an activity variable. Cyclia therefore reports
    (1) process coverage: processes with data / processes in the supply chain, and (2) if the table has a default
    row (match '*'), worker hours of processes without data ESTIMATED with it, and the worker-hour coverage
    = hours with data / (hours with data + estimated hours). Without a default row no worker-hour coverage is claimed."""
    data = store.q("SELECT * FROM slca_data")
    if not data:
        raise ValueError("No social data in the library. Import a social data table (Toolbox > Social LCA).")
    rf = dict(RISK_FACTORS, **(factors or {}))
    mc = calc.get_mc(store)
    ctx = calc.Context(store)
    m = store.model(int(model_id))
    if not m or not m["inputs"]:
        raise ValueError("This model has no inputs yet.")
    acts_d, flows, fixed = {}, {}, []
    calc.expand(ctx, int(model_id), 1.0, acts_d, flows, fixed, keep=lambda i: not calc.is_module_d(m["scope"], i["stage"]))
    # the lines used and the avoided products (negative line amounts) are solved separately, so a credit never
    # reduces the worker hours of a process that the product system really uses (e.g. electricity shared by both
    # chains). The split is by the sign of the line amount, not of the demand vector: waste sent to treatment is a
    # positive line with a negative demand (the treatment dataset's reference amount is negative).
    f_pos = calc.demand_vector(mc, {a: v for a, v in acts_d.items() if v > 0})
    f_neg = calc.demand_vector(mc, {a: -v for a, v in acts_d.items() if v < 0})
    s_pos = mc.solve(f_pos) if f_pos.any() else np.zeros(mc.n)
    s_neg = mc.solve(f_neg) if f_neg.any() else np.zeros(mc.n)
    # activity level = |scaling x reference amount| (output, or waste treated for a treatment dataset whose reference
    # amount is negative). The sign of the scaling says whether the process runs (positive) or is avoided by a credit
    # inside the supply chain (negative, e.g. recycling with system expansion)
    a_pos, a_neg = np.abs(s_pos * mc.diag), np.abs(s_neg * mc.diag)
    lv_pos = a_pos * (s_pos > 0) + a_neg * (s_neg < 0)
    lv_neg = a_pos * (s_pos < 0) + a_neg * (s_neg > 0)
    tiny = 1e-15 * (max(lv_pos.max(initial=0), lv_neg.max(initial=0)) or 1)
    idx = [int(i) for i in np.nonzero((lv_pos > tiny) | (lv_neg > tiny))[0]]
    acts = store.q(f"SELECT id, key, name, location FROM activities WHERE id IN ({','.join(str(int(mc.act_ids[i])) for i in idx) or '0'})")
    byid = {a["id"]: a for a in acts}
    default = [r for r in data if r["match"].strip() == "*"]
    assign = _assign(acts, [r for r in data if r["match"].strip() != "*"])
    hours_data, hours_est, hours_avoided = 0.0, 0.0, 0.0
    ind, proc, no_data, avoided, inconsistent = {}, [], [], [], []
    n_running = n_with_data = 0
    for i in idx:
        aid = int(mc.act_ids[i])
        a = byid.get(aid) or {"name": str(aid), "location": ""}
        rows = assign.get(aid)
        if rows and lv_neg[i] > tiny:
            ha = float(lv_neg[i] * rows[0]["worker_hours"])
            hours_avoided += ha
            avoided.append({"process": a["name"], "location": a["location"], "hours": ha})
        if lv_pos[i] <= tiny:
            continue
        if not rows:
            n_running += 1
            rec = {"process": a["name"], "location": a["location"], "output": float(lv_pos[i])}
            if default:
                rec["estimated_hours"] = float(lv_pos[i] * default[0]["worker_hours"])
                hours_est += rec["estimated_hours"]
            no_data.append(rec)
            continue
        whs = {float(r["worker_hours"]) for r in rows}
        if len(whs) > 1:
            inconsistent.append({"process": a["name"], "location": a["location"], "worker_hours": sorted(whs)})
        h = float(lv_pos[i] * rows[0]["worker_hours"])
        n_running += 1
        n_with_data += 1
        hours_data += h
        proc_risk = 0.0
        for r in rows:
            k = (r["stakeholder"], r["indicator"])
            x = ind.setdefault(k, {"stakeholder": r["stakeholder"], "indicator": r["indicator"], "risk_hours": 0.0,
                                   "hours_with_data": 0.0, "by_process": []})
            rh = h * rf[r["risk"]]
            x["risk_hours"] += rh
            x["hours_with_data"] += h
            x["by_process"].append({"process": a["name"], "location": a["location"], "risk": r["risk"], "hours": h,
                                    "risk_hours": rh})
            proc_risk += rh
        proc.append({"process": a["name"], "location": a["location"], "hours": h, "risk_hours": proc_risk})
    known_total = hours_data + hours_est if default else None
    for x in ind.values():
        x["by_process"].sort(key=lambda y: -y["risk_hours"])
        x["by_process"] = x["by_process"][:10]
        # share of the (estimated) total worker hours that has data for this indicator; None when it cannot be known
        x["coverage"] = (x["hours_with_data"] / known_total) if known_total else None
        x["coverage_of_hours_with_data"] = x["hours_with_data"] / hours_data if hours_data else 0.0
    proc.sort(key=lambda y: -y["risk_hours"])
    no_data.sort(key=lambda y: -abs(y["output"]))
    src = sorted({r["source"] for r in data})
    process_cov = n_with_data / n_running if n_running else 0.0
    return {"worker_hours": hours_data, "worker_hours_estimated": hours_est if default else None,
            "worker_hours_avoided": hours_avoided, "avoided_processes": avoided[:20],
            "coverage_hours": (hours_data / known_total) if known_total else None,
            "process_coverage": process_cov, "complete": n_with_data == n_running,
            "indicators": sorted(ind.values(), key=lambda x: (STAKEHOLDERS.index(x["stakeholder"]), x["indicator"])),
            "hotspots": proc[:20], "processes_without_data": no_data[:30], "n_without_data": len(no_data),
            "n_processes": n_running, "n_with_data": n_with_data, "risk_factors": rf, "sources": src,
            "inconsistent_activity_variables": inconsistent[:30],
            "demo": any(x.startswith("demo") for x in src), "has_epd_lines": bool(fixed),
            "label": "Social LCA risk screening (not a full social LCA)",
            "note": "Worker hours per functional unit = activity level of each process x its worker hours per unit. Risk "
                    "hours = hours x the factor of the risk level (medium-risk-hour equivalents). Processes without data "
                    "are not counted, so the totals are lower bounds; process coverage gives the share of processes with "
                    "data. Worker-hour coverage needs a default row (match '*') to estimate the hours of processes "
                    "without data. Avoided products (credits) are listed separately and not subtracted. A screening of "
                    "social risk hotspots (UNEP 2020, ISO 14075:2024 stakeholder categories), not a full social LCA: "
                    "raw indicator values, reference scales and the PSILCA database format are not supported."}


# openLCA risk levels (olca-schema RiskLevel) -> Cyclia risk levels; opportunities and missing data are not risks
OLCA_RISK = {"NO_RISK": "no risk", "VERY_LOW_RISK": "very low", "LOW_RISK": "low", "MEDIUM_RISK": "medium",
             "HIGH_RISK": "high", "VERY_HIGH_RISK": "very high"}
OLCA_SKIP = ("NO_DATA", "NOT_APPLICABLE", "NO_OPPORTUNITY", "LOW_OPPORTUNITY", "MEDIUM_OPPORTUNITY", "HIGH_OPPORTUNITY")


def _stakeholder(path):
    p = (path or "").strip().strip("/").split("/")[0].strip().lower()
    for st, words in (("workers", ("worker",)), ("local community", ("local communit", "community")),
                      ("society", ("society",)), ("consumers", ("consumer",)),
                      ("value chain actors", ("value chain", "actors")), ("children", ("child",))):
        if any(w in p for w in words):
            return st
    return None


def import_olca_social(store, path, mapping_text="", replace=True, source=""):
    """Native import of social data in openLCA JSON-LD (zip or folder), as distributed by PSILCA (country-specific
    sectors) and SOCA (ecoinvent processes): social indicators with their activity variable, and the social aspects of
    each process (indicator, activity value, risk level, raw amount, quality).

    - Activity variable: the activity value of the process (worker hours per unit of its reference product when the
      indicator's activity variable is worker hours).
    - Stakeholder category: the first level of the indicator's category path (Workers, Local community, Society,
      Consumers, Value chain actors, Children).
    - Risk level: openLCA levels mapped to Cyclia's; 'no data', 'not applicable' and opportunity levels are not
      counted as risks (reported).
    - Matching: each process is stored with its name and location, so SOCA data matches ecoinvent datasets of the same
      name and location. PSILCA sectors do not have ecoinvent names: give a mapping table (CSV: cyclia_match,
      cyclia_location, source_process, source_location) to assign sectors to the datasets of your library."""
    import json as _json
    from importers.jsonld import _Source
    src = _Source(path)
    locations = {}
    for n in src.folder("locations"):
        loc = src.load(n) or {}
        locations[loc.get("@id")] = loc.get("code") or loc.get("name", "")
    cats = {}
    for n in src.folder("categories"):
        c = src.load(n) or {}
        cats[c.get("@id")] = c
    inds = {}
    for n in src.folder("social_indicators"):
        d = src.load(n) or {}
        cat = d.get("category")
        if isinstance(cat, dict):
            parts, cur = [], cats.get(cat.get("@id"))
            while cur:
                parts.insert(0, cur.get("name", ""))
                cur = cats.get((cur.get("category") or {}).get("@id")) if isinstance(cur.get("category"), dict) else None
            cat = "/".join(parts) or cat.get("name", "")
        inds[d.get("@id")] = {"name": d.get("name", ""), "category": cat or "",
                              "activity_variable": d.get("activityVariable", ""),
                              "activity_unit": (d.get("activityUnit") or {}).get("name", ""),
                              "unit": d.get("unitOfMeasurement", "")}
    rows, skipped, no_stake, n_proc = [], {}, set(), 0
    label = source or os.path.basename(str(path).rstrip("/\\")) or "openLCA social data"
    for n in src.folder("processes"):
        p = src.load(n) or {}
        aspects = p.get("socialAspects") or []
        if not aspects:
            continue
        n_proc += 1
        loc = p.get("location") or {}
        loc = (locations.get(loc.get("@id")) or loc.get("code") or loc.get("name", "")) if isinstance(loc, dict) else str(loc or "")
        name = p.get("name", "")
        for a in aspects:
            ref = a.get("socialIndicator") or {}
            ind = inds.get(ref.get("@id")) or {"name": ref.get("name", ""), "category": ref.get("category", ""),
                                               "activity_variable": "", "activity_unit": "", "unit": ""}
            rl = str(a.get("riskLevel") or "NO_DATA").upper()
            if rl not in OLCA_RISK:
                skipped[rl] = skipped.get(rl, 0) + 1
                continue
            st = _stakeholder(ind["category"]) or _stakeholder(ind["name"])
            if not st:
                no_stake.add(ind["category"] or ind["name"])
                continue
            try:
                av = float(a.get("activityValue") or 0.0)
            except (TypeError, ValueError):
                av = 0.0
            rows.append((name, (loc or "").upper(), av, st, ind["name"], OLCA_RISK[rl], f"{label}",
                         str(a.get("rawAmount") or ""), ind["unit"], str(a.get("quality") or ""), ind["activity_unit"]))
    if not rows:
        raise ValueError("No social aspects with a risk level were found. Is this a PSILCA or SOCA export in openLCA JSON-LD?")
    mapped = 0
    if mapping_text.strip():
        rdr = csv.DictReader(io.StringIO(mapping_text))
        cols = {c.strip().lower(): c for c in (rdr.fieldnames or []) if c}
        for need in ("cyclia_match", "source_process"):
            if need not in cols:
                raise ValueError("The mapping table needs the columns cyclia_match, cyclia_location, source_process, source_location.")
        by_src = {}
        for r in rows:
            by_src.setdefault((r[0].lower(), r[1]), []).append(r)
        extra = []
        for m in rdr:
            sp = str(m.get(cols["source_process"]) or "").strip().lower()
            sl = str(m.get(cols.get("source_location", "")) or "").strip().upper() if "source_location" in cols else ""
            cm = str(m.get(cols["cyclia_match"]) or "").strip()
            cl = str(m.get(cols.get("cyclia_location", "")) or "").strip().upper() if "cyclia_location" in cols else ""
            for r in by_src.get((sp, sl), []):
                extra.append((cm, cl) + r[2:6] + (r[6] + f" (sector: {r[0]} [{r[1]}])",) + r[7:])
                mapped += 1
        rows += extra
    with store.lock:
        if replace:
            store.conn.execute("DELETE FROM slca_data")
        store.conn.executemany("INSERT INTO slca_data(match,location,worker_hours,stakeholder,indicator,risk,source,raw_value,"
                               "raw_unit,quality,activity_unit) VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
        store.conn.commit()
    return {"rows": len(rows), "processes": n_proc, "indicators": len(inds), "skipped_levels": skipped,
            "without_stakeholder": sorted(no_stake)[:20], "mapped_rows": mapped,
            "note": "Risk levels 'no data', 'not applicable' and opportunities are not counted as risks."}


def demo_data(store):
    rows = ["match,location,worker_hours,stakeholder,indicator,risk,source"]
    for match, wh, risks in (("cement production", 0.004, ("medium", "low", "high")),
                             ("electricity production", 0.0008, ("low", "low", "medium")),
                             ("cotton", 0.05, ("very high", "high", "high")),
                             ("transport, freight lorry", 0.002, ("medium", "medium", "low"))):
        for (st, ind), rk in zip((("workers", "Fair salary"), ("workers", "Health and safety"),
                                  ("local community", "Access to material resources")), risks):
            rows.append(f"{match},,{wh},{st},{ind},{rk},")
    return import_data(store, "\n".join(rows), demo=True)
