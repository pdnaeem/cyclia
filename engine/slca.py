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

    Activity level of a process = |s_i x production_i| with s solved for the demand alone; the avoided products
    (negative demand) are solved separately, their hours are reported separately and are NOT netted against or
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
    f = calc.demand_vector(mc, acts_d)
    # the demand and the avoided products (negative demand) are solved separately, so a credit never reduces the
    # worker hours of a process that the product system really uses (e.g. electricity shared by both chains)
    f_pos, f_neg = np.clip(f, 0, None), np.clip(-f, 0, None)
    s_pos = mc.solve(f_pos) if f_pos.any() else np.zeros(mc.n)
    s_neg = mc.solve(f_neg) if f_neg.any() else np.zeros(mc.n)
    lv_pos, lv_neg = np.abs(s_pos * mc.diag), np.abs(s_neg * mc.diag)
    tiny = 1e-15 * (max(lv_pos.max(initial=0), lv_neg.max(initial=0)) or 1)
    idx = [int(i) for i in np.nonzero((lv_pos > tiny) | (lv_neg > tiny))[0]]
    acts = store.q(f"SELECT id, key, name, location FROM activities WHERE id IN ({','.join(str(int(mc.act_ids[i])) for i in idx) or '0'})")
    byid = {a["id"]: a for a in acts}
    default = [r for r in data if r["match"].strip() == "*"]
    assign = _assign(acts, [r for r in data if r["match"].strip() != "*"])
    hours_data, hours_est, hours_avoided = 0.0, 0.0, 0.0
    ind, proc, no_data, avoided = {}, [], [], []
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
            "demo": any(x.startswith("demo") for x in src), "has_epd_lines": bool(fixed),
            "label": "Social LCA risk screening (not a full social LCA)",
            "note": "Worker hours per functional unit = activity level of each process x its worker hours per unit. Risk "
                    "hours = hours x the factor of the risk level (medium-risk-hour equivalents). Processes without data "
                    "are not counted, so the totals are lower bounds; process coverage gives the share of processes with "
                    "data. Worker-hour coverage needs a default row (match '*') to estimate the hours of processes "
                    "without data. Avoided products (credits) are listed separately and not subtracted. A screening of "
                    "social risk hotspots (UNEP 2020, ISO 14075:2024 stakeholder categories), not a full social LCA: "
                    "raw indicator values, reference scales and the PSILCA database format are not supported."}


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
