"""Dynamic material flow analysis and circularity indicators (Cyclia 1.3.5).

A dedicated MFA workspace, separate from the LCA model:

- a system of processes, in-use stocks and final sinks, connected by flows with transfer coefficients;
- external inflows per year (interpolated linearly between the given years, constant after the last one);
- in-use stocks with a lifetime distribution (fixed, normal or Weibull): what enters a stock in year t leaves it
  in the following years by the discrete retirement curve (no retirement in the year of entry);
- loops inside a year (e.g. recycling back to production) are solved as a linear system;
- results per year: throughput of every process, stock levels, inflows and outflows, losses to sinks, recycled
  flows, the mass balance, and circularity indicators.

Indicators: end-of-life recycling rate (end-of-life outflow that reaches recycling x recycling efficiency, over the
end-of-life outflow), collection rate, recycling efficiency, recycled content (recycled input to the production
process / total input to it), and, in the spirit of ISO 59020:2024, the share of recirculated
inflow and the share of outflow that is recirculated. The Material Circularity Indicator of the Ellen MacArthur
Foundation (2015) is available for a product from its recycled content, collection and efficiencies.
"""
import math

import numpy as np


def _interp(values, years):
    """Linear interpolation between the given years, constant before the first and after the last one."""
    pts = sorted((int(k), float(v)) for k, v in (values or {}).items())
    if not pts:
        return np.zeros(len(years))
    return np.interp(years, [p[0] for p in pts], [p[1] for p in pts])


def retirement(lifetime, n):
    """Share of an inflow that leaves the stock at age a = 1..n-1 (index a); index 0 is 0."""
    t = (lifetime or {}).get("type", "fixed")
    out = np.zeros(n)
    if t == "fixed":
        L = int(round(float(lifetime.get("mean", 1))))
        if L < 1:
            raise ValueError("A fixed lifetime must be at least one year.")
        if L < n:
            out[L] = 1.0
        return out
    if t == "normal":
        mu, sd = float(lifetime["mean"]), float(lifetime["sd"])
        if sd <= 0:
            raise ValueError("The standard deviation of a normal lifetime must be positive.")
        cdf = lambda x: 0.5 * (1 + math.erf((x - mu) / (sd * math.sqrt(2))))
        # nothing retires in the year of entry: whatever the distribution puts at ages below 1.5 retires at age 1
        for a in range(1, n):
            out[a] = cdf(1.5) if a == 1 else cdf(a + 0.5) - cdf(a - 0.5)
        return out
    if t == "weibull":
        k, lam = float(lifetime["shape"]), float(lifetime["scale"])
        if k <= 0 or lam <= 0:
            raise ValueError("Weibull shape and scale must be positive.")
        cdf = lambda x: 1 - math.exp(-((max(x, 0.0) / lam) ** k))
        for a in range(1, n):
            out[a] = cdf(a) - cdf(a - 1) if a > 1 else cdf(1)
        return out
    raise ValueError("Lifetime type must be fixed, normal or weibull.")


def validate(defn):
    procs = defn.get("processes") or []
    if not procs:
        raise ValueError("Define at least one process.")
    ids = [p.get("id") for p in procs]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("Every process needs a unique id.")
    pid = set(ids)
    for f in defn.get("flows") or []:
        if f.get("from") not in pid or f.get("to") not in pid:
            raise ValueError(f"Flow {f.get('from')} -> {f.get('to')}: both ends must be defined processes.")
        if not 0 <= float(f.get("share", -1)) <= 1:
            raise ValueError(f"Flow {f['from']} -> {f['to']}: the transfer coefficient must be between 0 and 1.")
    for p in procs:
        if p.get("sink"):
            if any(f["from"] == p["id"] for f in defn.get("flows") or []):
                raise ValueError(f"'{p['id']}' is a final sink and cannot have outgoing flows.")
            continue
        tot = sum(float(f["share"]) for f in defn.get("flows") or [] if f["from"] == p["id"])
        if abs(tot - 1) > 1e-6:
            raise ValueError(f"The transfer coefficients leaving '{p['id']}' add up to {tot:g}; they must add up to 1 "
                             "(send losses to a sink).")
        if p.get("stock") and not p.get("lifetime"):
            raise ValueError(f"The stock '{p['id']}' needs a lifetime.")
    for e in defn.get("inflows") or []:
        if e.get("to") not in pid:
            raise ValueError("Every external inflow must go to a defined process.")
    y = defn.get("years") or []
    if len(y) != 2 or int(y[1]) < int(y[0]):
        raise ValueError("Give the first and last year, e.g. [2020, 2050].")
    return True


def run(defn):
    validate(defn)
    years = list(range(int(defn["years"][0]), int(defn["years"][1]) + 1))
    ny = len(years)
    procs = defn["processes"]
    ids = [p["id"] for p in procs]
    ix = {k: i for i, k in enumerate(ids)}
    stock = [i for i, p in enumerate(procs) if p.get("stock")]
    sink = [i for i, p in enumerate(procs) if p.get("sink")]
    flowp = [i for i, p in enumerate(procs) if not p.get("stock") and not p.get("sink")]
    n = len(procs)
    T = np.zeros((n, n))
    for f in defn.get("flows") or []:
        T[ix[f["from"]], ix[f["to"]]] += float(f["share"])
    ext = np.zeros((ny, n))
    for e in defn.get("inflows") or []:
        ext[:, ix[e["to"]]] += _interp(e.get("values"), years)
    rcurve = {i: retirement(procs[i]["lifetime"], ny + 1) for i in stock}
    Tnn = T[np.ix_(flowp, flowp)]
    Msys = np.eye(len(flowp)) - Tnn.T
    try:
        Minv = np.linalg.inv(Msys) if flowp else np.zeros((0, 0))
    except np.linalg.LinAlgError:
        raise ValueError("A loop of flows has no loss and never leaves the system. Send part of it to a sink or a stock.")
    if flowp and np.linalg.cond(Msys) > 1e12:
        raise ValueError("A loop of flows has no loss and never leaves the system. Send part of it to a sink or a stock.")
    thr = np.zeros((ny, n))         # throughput of flow processes; inflow of stocks and sinks
    s_in, s_out = np.zeros((ny, n)), np.zeros((ny, n))
    level = np.zeros((ny, n))
    F = np.zeros((ny, n, n))        # flows from i to j in year t
    for t in range(ny):
        for s in stock:
            s_out[t, s] = sum(s_in[t0, s] * rcurve[s][t - t0] for t0 in range(t))
        b = ext[t].copy()
        for s in stock:
            b += s_out[t, s] * T[s]
        x = Minv @ b[flowp] if flowp else np.zeros(0)
        out_np = np.zeros(n)
        out_np[flowp] = x
        thr[t, flowp] = x
        for i in flowp:
            F[t, i] = out_np[i] * T[i]
        for s in stock:
            F[t, s] = s_out[t, s] * T[s]
        inc = F[t].sum(axis=0) + ext[t]
        for s in stock:
            s_in[t, s] = inc[s]
            level[t, s] = (level[t - 1, s] if t else 0.0) + s_in[t, s] - s_out[t, s]
            thr[t, s] = s_in[t, s]
        for k in sink:
            level[t, k] = (level[t - 1, k] if t else 0.0) + inc[k]
            thr[t, k] = inc[k]
    rec = [ix[r] for r in defn.get("recycling_processes") or [] if r in ix]
    prod = ix.get(defn.get("production_process") or "", None)
    # share of the material leaving each process that reaches a recycling process within the year (before a stock
    # or a sink): r = 1 at recycling, 0 at stocks and sinks, r_i = sum_j T_ij r_j at the other processes
    reach = np.zeros(n)
    if rec:
        reach[rec] = 1.0
        other = [i for i in flowp if i not in rec]
        if other:
            A_ = np.eye(len(other)) - T[np.ix_(other, other)]
            b_ = T[np.ix_(other, rec)].sum(axis=1)
            reach[other] = np.linalg.solve(A_, b_)
    rows = []
    for t, y in enumerate(years):
        eol = float(sum(s_out[t, s] for s in stock))
        recycled_out = float(sum(F[t, i, j] for i in rec for j in range(n) if j not in rec and not procs[j].get("sink")))
        rc_in = float(sum(F[t, i, prod] for i in rec)) if prod is not None else None
        prod_in = float(F[t, :, prod].sum() + ext[t, prod]) if prod is not None else None
        # input of the recycling processes from outside the recycling chain (collected end-of-life and scrap)
        eol_to_rec = float(sum(F[t, i, r] for r in rec for i in range(n) if i not in rec) + sum(ext[t, r] for r in rec)) \
            if rec else 0.0
        # end-of-life material that reaches recycling: what leaves the stocks, traced through collection and
        # sorting (production scrap and imported scrap are not end-of-life material)
        eol_collected = float(sum(s_out[t, s] * float(T[s] @ reach) for s in stock)) if rec else 0.0
        ec = (recycled_out / eol_to_rec) if eol_to_rec > 1e-12 else None
        loss = float(sum(F[t, :, k].sum() + ext[t, k] for k in sink))
        tot_in = float(ext[t].sum())
        d_stock = float(sum(level[t, s] - (level[t - 1, s] if t else 0.0) for s in stock))
        rows.append({"year": y, "external_inflow": tot_in, "stock": float(sum(level[t, s] for s in stock)),
                     "stock_inflow": float(sum(s_in[t, s] for s in stock)), "end_of_life_outflow": eol,
                     "recycled": recycled_out, "losses": loss,
                     # end-of-life recycling rate: end-of-life material collected for recycling x recycling efficiency,
                     # over the end-of-life outflow (scrap from production or imports is not counted)
                     "recycling_rate": (eol_collected * ec / eol) if eol > 1e-12 and rec and ec is not None else None,
                     "collection_rate": (eol_collected / eol) if eol > 1e-12 and rec else None,
                     "recycling_efficiency": ec,
                     "recycled_content": (rc_in / prod_in) if prod is not None and prod_in and prod_in > 1e-12 else None,
                     # boundary: the production process. Share of its total input that is recirculated (from the
                     # recycling processes); 1.3.5 divided by all external inflows of the system instead
                     "recirculated_inflow_share": (rc_in / prod_in) if prod is not None and prod_in and prod_in > 1e-12 else None,
                     "virgin_inflow_to_production": (prod_in - rc_in) if prod is not None else None,
                     "outflow_recirculated_share": (recycled_out / (recycled_out + loss)) if (recycled_out + loss) > 1e-12 else None,
                     "balance_error": tot_in - d_stock - loss})
        r_ = rows[-1]
        # MCI of the material in that year from the MFA itself: F_R = recycled content, C_R = share of the
        # end-of-life outflow sent to recycling, E_C = share of that recycling input that is recycled
        fr = r_["recycled_content"]
        cr = r_["collection_rate"]
        r_["mci"] = mci(Fr=min(max(fr, 0.0), 1.0), Cr=min(max(cr, 0.0), 1.0), Ec=min(max(ec, 1e-9), 1.0))["MCI"] \
            if None not in (fr, cr, ec) else None
    worst = max(abs(r["balance_error"]) / max(1.0, abs(r["external_inflow"])) for r in rows)
    return {"years": years, "rows": rows,
            "processes": [{"id": p["id"], "name": p.get("name", p["id"]), "kind": "stock" if p.get("stock") else
                           "sink" if p.get("sink") else "process",
                           "throughput": thr[:, i].tolist(), "level": level[:, i].tolist()} for i, p in enumerate(procs)],
            "mass_balance_ok": worst < 1e-9, "max_balance_error": worst,
            "note": "Inflows interpolated linearly between the given years. Stocks retire their inflow by the lifetime "
                    "distribution, starting the year after entry; the stock is zero at the start. Loops within a year "
                    "are solved exactly. Mass balance: external inflow = change of stocks + flows to sinks, every year. "
                    "Recycled content and recirculated inflow share: recycled input / total input of the production "
                    "process. End-of-life recycling rate: end-of-life outflow that reaches recycling (traced through "
                    "collection and sorting) x recycling efficiency, over the end-of-life outflow; production and "
                    "imported scrap are not counted. MCI per year from the MFA: recycled content (F_R), collection rate "
                    "of the end-of-life outflow (C_R) and recycling efficiency (E_C = recycled output / input of the "
                    "recycling processes); reuse, lifetime and intensity ratios are taken as 1. These "
                    "are indicators in the spirit of ISO 59020:2024, not a complete ISO 59020 assessment."}


def mci(Fr=0.0, Fu=0.0, Cr=0.0, Cu=0.0, Ec=1.0, Ef=1.0, L_ratio=1.0, U_ratio=1.0, M=1.0):
    """Material Circularity Indicator (Ellen MacArthur Foundation and Granta Design, 2015), technical cycle only.
    Fr, Fu: fractions of feedstock from recycled and reused sources; Cr, Cu: fractions collected for recycling and
    reuse at end of use; Ec: efficiency of the recycling process; Ef: efficiency of producing the recycled feedstock;
    L_ratio, U_ratio: lifetime and intensity of use against the industry average."""
    for k, v in (("Fr", Fr), ("Fu", Fu), ("Cr", Cr), ("Cu", Cu)):
        if not 0 <= v <= 1:
            raise ValueError(f"{k} must be between 0 and 1.")
    if Fr + Fu > 1 + 1e-9 or Cr + Cu > 1 + 1e-9:
        raise ValueError("Recycled and reused fractions cannot add up to more than 1.")
    if not (0 < Ec <= 1 and 0 < Ef <= 1):
        raise ValueError("Efficiencies must be above 0 and at most 1.")
    if L_ratio <= 0 or U_ratio <= 0:
        raise ValueError("Lifetime and use ratios must be positive.")
    V = M * (1 - Fr - Fu)
    W0 = M * (1 - Cr - Cu)
    Wc = M * (1 - Ec) * Cr
    Wf = M * (1 - Ef) * Fr / Ef
    W = W0 + (Wf + Wc) / 2
    LFI = (V + W) / (2 * M + (Wf - Wc) / 2)
    X = L_ratio * U_ratio
    F = 0.9 / X
    return {"MCI": max(0.0, 1 - LFI * F), "LFI": LFI, "utility": X, "V": V, "W": W,
            "note": "Ellen MacArthur Foundation (2015) Circularity Indicators methodology, technical cycle; MCI is 0.1 "
                    "for a fully linear product with average utility and 1 for a fully circular one."}


EXAMPLE = {
    "name": "Aluminium in buildings (example, invented numbers)", "years": [2020, 2060],
    "production_process": "prod", "recycling_processes": ["rec"],
    "processes": [
        {"id": "prod", "name": "Semi-finished production"},
        {"id": "use", "name": "Buildings in use", "stock": True, "lifetime": {"type": "normal", "mean": 40, "sd": 10}},
        {"id": "eol", "name": "Demolition and collection"},
        {"id": "rec", "name": "Recycling (remelting)"},
        {"id": "loss", "name": "Losses and landfill", "sink": True},
    ],
    "inflows": [{"to": "prod", "values": {"2020": 100, "2040": 130, "2060": 130}}],
    "flows": [
        {"from": "prod", "to": "use", "share": 0.97}, {"from": "prod", "to": "loss", "share": 0.03},
        {"from": "use", "to": "eol", "share": 1.0},
        {"from": "eol", "to": "rec", "share": 0.85}, {"from": "eol", "to": "loss", "share": 0.15},
        {"from": "rec", "to": "prod", "share": 0.95}, {"from": "rec", "to": "loss", "share": 0.05},
    ],
}


# ---------------------------------------------------------------------------------------------- MFA linked to LCA
def lca(store, defn, method_ids, links):
    """Environmental impacts of the material system year by year.

    links: {mfa process id: {"kind": "activity" | "model", "id": dataset or model id, "factor": amount of the linked
    reference product per unit of MFA throughput (e.g. 1 when both are in kg; 0.001 when the MFA is in kg and the
    dataset in t)}}. Impact of a process in year t = throughput_t x factor x impact per unit of the linked dataset
    (whole supply chain, from the engine) or model (per unit of its functional unit). Throughput of a stock is its
    inflow, of a sink what it receives. Returns per year and category the total and the share of every process."""
    import calc
    res = run(defn)
    method_ids = [int(m) for m in method_ids or []]
    if not method_ids:
        raise ValueError("Pick impact categories in step 4 first.")
    if not links:
        raise ValueError("Link at least one MFA process to a dataset or a model.")
    ids = [p["id"] for p in defn["processes"]]
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, method_ids)
    unit = {}
    for pid, ln in links.items():
        if pid not in ids:
            raise ValueError(f"'{pid}' is not a process of the MFA system.")
        kind, ref = ln.get("kind", "activity"), int(ln["id"])
        f = float(ln.get("factor", 1.0))
        if kind == "activity":
            if ref not in mc.act_index:
                raise ValueError(f"Dataset {ref} is not in the library.")
            h, _, _ = calc.impacts(mc, M, {ref: 1.0}, {}, [])
            unit[pid] = np.asarray(h, dtype=float) * f
        elif kind == "model":
            m = store.model(ref)
            if not m:
                raise ValueError(f"Model {ref} does not exist.")
            r = calc.run(store, ref, method_ids)
            unit[pid] = np.array([x["total"] for x in r["results"]]) / (m["amount"] or 1.0) * f
        else:
            raise ValueError("A link is to an 'activity' or a 'model'.")
    thr = {p["id"]: p["throughput"] for p in res["processes"]}
    cats = [{k: x[k] for k in ("id", "family", "category", "unit")} for x in M.rows]
    years = res["years"]
    per_year, by_proc = [], {pid: np.zeros(len(cats)) for pid in unit}
    for t, y in enumerate(years):
        tot = np.zeros(len(cats))
        parts = {}
        for pid, u in unit.items():
            v = thr[pid][t] * u
            tot += v
            parts[pid] = v.tolist()
            by_proc[pid] += v
        per_year.append({"year": y, "total": tot.tolist(), "by_process": parts})
    cum = sum((np.array(r["total"]) for r in per_year), np.zeros(len(cats)))
    return {"categories": cats, "years": years, "rows": per_year, "cumulative": cum.tolist(),
            "cumulative_by_process": {k: v.tolist() for k, v in by_proc.items()},
            "linked": {pid: {"kind": l.get("kind", "activity"), "id": int(l["id"]), "factor": float(l.get("factor", 1.0))}
                       for pid, l in links.items()},
            "unlinked_processes": [p for p in ids if p not in unit],
            "mfa": {"mass_balance_ok": res["mass_balance_ok"]},
            "note": "Impact of a process in a year = its throughput x the factor x the impact per unit of the linked dataset "
                    "(cradle-to-gate of that dataset, with today's background data) or model. Processes without a link add "
                    "nothing. Background data do not change over the years unless a prospective background scenario is "
                    "used for the calculation."}
