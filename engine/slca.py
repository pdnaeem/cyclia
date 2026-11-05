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
            rejected.append({"row": n, "reason": "match is empty"})
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
    s = mc.solve(f) if f.any() else np.zeros(mc.n)
    output = s * mc.diag                       # amount of reference product of each process per functional unit
    idx = [int(i) for i in np.nonzero(np.abs(output) > 1e-15 * (np.abs(output).max() or 1))[0]]
    acts = store.q(f"SELECT id, key, name, location FROM activities WHERE id IN ({','.join(str(int(mc.act_ids[i])) for i in idx) or '0'})")
    byid = {a["id"]: a for a in acts}
    assign = _assign(acts, data)
    hours_total, hours_cov = 0.0, 0.0
    ind = {}
    proc = []
    no_data = []
    for i in idx:
        aid = int(mc.act_ids[i])
        a = byid.get(aid)
        rows = assign.get(aid)
        if not rows:
            no_data.append({"process": a["name"] if a else str(aid), "location": a["location"] if a else "",
                            "output": float(output[i])})
            continue
        wh = rows[0]["worker_hours"]
        h = float(abs(output[i]) * wh)
        hours_total += h
        hours_cov += h
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
    for x in ind.values():
        x["by_process"].sort(key=lambda y: -y["risk_hours"])
        x["by_process"] = x["by_process"][:10]
        x["coverage"] = x["hours_with_data"] / hours_total if hours_total else 0.0
    proc.sort(key=lambda y: -y["risk_hours"])
    no_data.sort(key=lambda y: -abs(y["output"]))
    src = sorted({r["source"] for r in data})
    return {"worker_hours": hours_total, "indicators": sorted(ind.values(), key=lambda x: (STAKEHOLDERS.index(x["stakeholder"]), x["indicator"])),
            "hotspots": proc[:20], "processes_without_data": no_data[:30], "n_without_data": len(no_data),
            "n_processes": len(idx), "risk_factors": rf, "sources": src, "demo": any(x.startswith("demo") for x in src),
            "has_epd_lines": bool(fixed),
            "note": "Worker hours per functional unit = output of each process x its worker hours per unit. Risk hours = "
                    "hours x the factor of the risk level (medium-risk-hour equivalents). A screening of social risk "
                    "hotspots (UNEP 2020, ISO 14075:2024 stakeholder categories), not a measurement of social "
                    "performance. Processes without data are not counted: see the list and the coverage per indicator."}


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
