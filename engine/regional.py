"""Native regionalised impact assessment: AWARE water scarcity and LANCA land use (Cyclia 1.3.5).

Unlike the generic factor import, these modules work on the inventory of each process at its own location:

AWARE (Boulay et al. 2018; WULCA): water consumption of every process (water taken from nature minus water
returned to nature, in m3) times the AWARE factor of the process location and type of use (agricultural,
non-agricultural, unknown). The model's own (foreground) water flows can be given a site or a watershed (basin).

LANCA (Bos et al. 2016): land occupation (m2*a) and land transformation to/from (m2) flows of every process,
times the LANCA factor of the land use type, the kind of intervention and the process location, for each of the
LANCA indicators (erosion resistance, mechanical filtration, physicochemical filtration, groundwater
regeneration, biotic production), and the EF soil quality index when its factors are imported.

Factors are not shipped with Cyclia: import the official AWARE 2.0 country and watershed tables and the official
LANCA factors with the templates below (factor values must come from the method owners). A small demonstration
set (clearly labelled "demo") exists only to try the workflow.

Every result reports its completeness: the share of the inventory (water consumption, land area) with a factor for
the exact location, with a fallback (country of a sub-national code, then the global value), or with none.
"""
import csv
import io
import re

import numpy as np
import scipy.sparse as sp

import calc

AWARE = "AWARE"
LANCA = "LANCA"
AWARE_USES = ("agri", "non-agri", "unknown")
AWARE_RANGE = (0.1, 100.0)       # AWARE factors are bounded between 0.1 and 100 m3 world-eq per m3
LANCA_INDICATORS = ("erosion resistance", "mechanical filtration", "physicochemical filtration",
                    "groundwater regeneration", "biotic production", "soil quality index")
LANCA_KINDS = ("occupation", "transformation_to", "transformation_from")
AGRI_WORDS = ("irrigation", "irrigated")

AWARE_TEMPLATE = ("location,agri,non_agri,unknown,level,name\n"
                  "GLO,45.74,20.30,43.10,world,World average (example numbers: replace with the official table)\n")
LANCA_TEMPLATE = ("indicator,kind,land_use,location,value,unit\n"
                  "erosion resistance,occupation,arable land,GLO,0.0,kg/(m2*a) (example row: replace with the official table)\n")


# ---------------------------------------------------------------------------------------------- factor import
def _num(v):
    try:
        return float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def import_factors(store, method, text, source="", replace=True, demo=False):
    """Import a factor table (CSV text) for AWARE or LANCA. Returns counts and the rows rejected with the reason."""
    method = method.upper()
    if method not in (AWARE, LANCA):
        raise ValueError("Method must be AWARE or LANCA.")
    rdr = csv.DictReader(io.StringIO(text))
    cols = {c.strip().lower(): c for c in (rdr.fieldnames or []) if c}
    rows, rejected = [], []
    if method == AWARE:
        for need in ("location",):
            if need not in cols:
                raise ValueError("The AWARE table needs a 'location' column and the columns agri, non_agri, unknown.")
        for n, r in enumerate(rdr, 2):
            loc = str(r.get(cols["location"]) or "").strip()
            if not loc:
                continue
            for use, col in (("agri", "agri"), ("non-agri", "non_agri"), ("unknown", "unknown")):
                if col not in cols:
                    continue
                v = _num(r.get(cols[col]))
                if v is None:
                    continue
                if not AWARE_RANGE[0] - 1e-9 <= v <= AWARE_RANGE[1] + 1e-9:
                    rejected.append({"row": n, "location": loc, "reason": f"{use} factor {v:g} is outside 0.1 to 100"})
                    continue
                rows.append((AWARE, "water scarcity", use, loc.upper(), v, "m3 world-eq/m3"))
    else:
        for need in ("indicator", "kind", "land_use", "location", "value"):
            if need not in cols:
                raise ValueError("The LANCA table needs the columns indicator, kind, land_use, location, value (and unit).")
        for n, r in enumerate(rdr, 2):
            ind = str(r.get(cols["indicator"]) or "").strip().lower()
            kind = str(r.get(cols["kind"]) or "").strip().lower().replace(" ", "_").replace(",", "")
            lu = _norm_land(r.get(cols["land_use"]))
            loc = str(r.get(cols["location"]) or "").strip().upper()
            v = _num(r.get(cols["value"]))
            unit = str(r.get(cols["unit"]) or "").strip() if "unit" in cols else ""
            if ind not in LANCA_INDICATORS:
                rejected.append({"row": n, "location": loc, "reason": f"unknown indicator '{ind}'"})
                continue
            if kind not in LANCA_KINDS:
                rejected.append({"row": n, "location": loc, "reason": f"kind must be one of {', '.join(LANCA_KINDS)}"})
                continue
            if not lu or not loc or v is None:
                rejected.append({"row": n, "location": loc, "reason": "land_use, location and value are needed"})
                continue
            rows.append((LANCA, ind, f"{kind}|{lu}", loc, v, unit))
    if not rows:
        raise ValueError("No valid factor rows were found." + (f" {len(rejected)} rows were rejected." if rejected else ""))
    src = ("demo: illustrative numbers, not the official method" if demo else (source or "imported table"))
    with store.lock:
        if replace:
            store.conn.execute("DELETE FROM native_factors WHERE method=?", (method,))
        store.conn.executemany("INSERT INTO native_factors(method,indicator,key,location,value,unit,source) VALUES(?,?,?,?,?,?,?)",
                               [r + (src,) for r in rows])
        store.conn.commit()
    return {"method": method, "factors": len(rows), "rejected": rejected[:200], "n_rejected": len(rejected), "source": src}


def status(store):
    out = {}
    for m in (AWARE, LANCA):
        r = store.one("SELECT COUNT(*) AS n, COUNT(DISTINCT location) AS locs, MIN(source) AS src FROM native_factors "
                      "WHERE method=?", (m,))
        out[m] = {"factors": r["n"], "locations": r["locs"], "source": r["src"] or "",
                  "demo": (r["src"] or "").startswith("demo")}
    return out


def _norm_land(v):
    t = re.sub(r"\s+", " ", str(v or "").strip().lower())
    return t


def land_flow(name):
    """('occupation' | 'transformation_to' | 'transformation_from', land use type) of an elementary flow name."""
    n = (name or "").strip().lower()
    for prefix, kind in (("occupation, ", "occupation"), ("transformation, to ", "transformation_to"),
                         ("transformation, from ", "transformation_from")):
        if n.startswith(prefix):
            return kind, _norm_land(n[len(prefix):])
    return None, None


def _water_flow(name, context, unit):
    """+1 for water taken from nature, -1 for water returned, 0 otherwise; with the factor to m3."""
    n = (name or "").lower()
    if not (n == "water" or n.startswith("water,") or n.startswith("water ")):
        return 0, 0.0
    u = (unit or "").strip()
    k = 1.0 if u in ("m3", "m³") else 0.001 if u in ("kg", "l", "L") else None
    if k is None:
        return 0, 0.0
    c = (context or "").lower()
    if c.startswith("natural resource") or c.startswith("resource"):
        return 1, k
    if c.startswith("water") or c.startswith("air") or c.startswith("soil"):
        return -1, k
    return 0, 0.0


# ---------------------------------------------------------------------------------------------- inventory by process
def _process_inventory(store, model_id):
    """Elementary flows per process (activity index -> flow index -> amount per functional unit) of a model, plus the
    model's own direct flows. Uses the engine's scaling vector."""
    mc = calc.get_mc(store)
    ctx = calc.Context(store)
    m = store.model(int(model_id))
    if not m or not m["inputs"]:
        raise ValueError("This model has no inputs yet.")
    acts, flows, fixed = {}, {}, []
    calc.expand(ctx, int(model_id), 1.0, acts, flows, fixed, keep=lambda i: not calc.is_module_d(m["scope"], i["stage"]))
    f = calc.demand_vector(mc, acts)
    s = mc.solve(f) if f.any() else np.zeros(mc.n)
    G = sp.csr_matrix(mc.B.multiply(s[np.newaxis, :]))      # flows x processes, per functional unit
    direct = calc.flow_vector(mc, flows)
    return mc, m, G, direct, bool(fixed)


def _flowinfo(store, mc):
    rows = {r["id"]: r for r in store.q("SELECT id, name, compartment, subcompartment, unit FROM flows")}
    info = []
    for fid in mc.flow_ids:
        r = rows.get(int(fid), {})
        info.append((r.get("name", ""), "/".join(x for x in (r.get("compartment"), r.get("subcompartment")) if x), r.get("unit", "")))
    return info


def _lookup(table, key, loc):
    """Factor for a location with fallbacks: exact, country of a sub-national code (e.g. 'CN-HB' -> 'CN'),
    then global. Returns (value, how)."""
    loc = (loc or "").upper()
    if (key, loc) in table:
        return table[(key, loc)], "exact"
    if "-" in loc and (key, loc.split("-")[0]) in table:
        return table[(key, loc.split("-")[0])], "country"
    for g in ("GLO", "WORLD", "GLOBAL"):
        if (key, g) in table:
            return table[(key, g)], "global"
    return None, "none"


# ---------------------------------------------------------------------------------------------- AWARE
def aware(store, model_id):
    rows = store.q("SELECT key, location, value, source FROM native_factors WHERE method=?", (AWARE,))
    if not rows:
        raise ValueError("No AWARE factors in the library. Import the official AWARE 2.0 table (Toolbox > Regional methods).")
    table = {(r["key"], r["location"]): r["value"] for r in rows}
    src = rows[0]["source"]
    mc, m, G, direct, has_fixed = _process_inventory(store, model_id)
    info = _flowinfo(store, mc)
    sc = m["scope"] or {}
    site = (sc.get("aware_location") or sc.get("geography") or "").strip().upper()
    names = {r["id"]: r["name"] for r in store.q("SELECT id, name FROM activities")}
    wflow = {i: _water_flow(*info[i]) for i in range(len(info))}
    widx = [i for i, (sg, k) in wflow.items() if sg]
    total, cons_total = 0.0, 0.0
    how_share = {"exact": 0.0, "country": 0.0, "global": 0.0, "none": 0.0}
    by_loc, by_use, unmatched = {}, {}, {}
    top = []
    Gw = G[widx, :] if widx else None
    if Gw is not None:
        Gw = Gw.tocsc()
        for p in np.unique(Gw.nonzero()[1]):
            col = Gw[:, p].toarray().ravel()
            c = float(sum(col[j] * wflow[widx[j]][0] * wflow[widx[j]][1] for j in range(len(widx))))
            if c == 0:
                continue
            loc = mc.act_loc[p] or "GLO"
            nm = names.get(int(mc.act_ids[p]), "")
            use = "agri" if any(w in nm.lower() for w in AGRI_WORDS) else (sc.get("aware_use") or "unknown")
            cf, how = _lookup(table, use, loc)
            if cf is None and use != "unknown":
                cf, how = _lookup(table, "unknown", loc)
            how_share[how] += abs(c)
            cons_total += c
            if cf is None:
                unmatched[loc] = unmatched.get(loc, 0.0) + c
                continue
            imp = c * cf
            total += imp
            by_loc[loc] = by_loc.get(loc, 0.0) + imp
            by_use[use] = by_use.get(use, 0.0) + imp
            top.append({"process": nm, "location": loc, "use": use, "consumption_m3": c, "factor": cf, "how": how,
                        "impact": imp})
    dc = float(sum(direct[i] * wflow[i][0] * wflow[i][1] for i in widx)) if widx else 0.0
    if dc:
        use = sc.get("aware_use") or "unknown"
        cf, how = _lookup(table, use, site or "GLO")
        how_share[how] += abs(dc)
        cons_total += dc
        if cf is None:
            unmatched[site or "foreground"] = unmatched.get(site or "foreground", 0.0) + dc
        else:
            total += dc * cf
            by_loc[site or "GLO"] = by_loc.get(site or "GLO", 0.0) + dc * cf
            top.append({"process": f"{m['name']} (own water flows)", "location": site or "GLO", "use": use,
                        "consumption_m3": dc, "factor": cf, "how": how, "impact": dc * cf})
    water_abs = sum(how_share.values())
    tot_abs = water_abs or 1.0
    top.sort(key=lambda x: -abs(x["impact"]))
    return {"method": "AWARE", "unit": "m3 world-eq", "source": src, "demo": src.startswith("demo"),
            "total": total, "consumption_m3": cons_total, "water_assessed_m3": water_abs, "empty": water_abs <= 0,
            "completeness": {k: v / tot_abs for k, v in how_share.items()},
            "by_location": sorted([{"location": k, "impact": v} for k, v in by_loc.items()], key=lambda x: -abs(x["impact"])),
            "by_use": [{"use": k, "impact": v} for k, v in by_use.items()],
            "unmatched": sorted([{"location": k, "consumption_m3": v} for k, v in unmatched.items()],
                                key=lambda x: -abs(x["consumption_m3"])),
            "top": top[:30], "site": site or "GLO", "has_epd_lines": has_fixed,
            "note": "Water consumption per process = water taken from nature minus water returned (m3), at the location of "
                    "the process; the model's own water flows at the AWARE location given for the model (site or watershed), "
                    "else at the study geography. Processes whose name mentions irrigation use the agricultural factor; "
                    "the others use the type of use chosen for the model (unknown by default). Fallbacks: country of a "
                    "sub-national code, then the global factor. EPD lines carry no water inventory."}


# ---------------------------------------------------------------------------------------------- LANCA
def lanca(store, model_id):
    rows = store.q("SELECT indicator, key, location, value, unit, source FROM native_factors WHERE method=?", (LANCA,))
    if not rows:
        raise ValueError("No LANCA factors in the library. Import the official LANCA table (Toolbox > Regional methods).")
    src = rows[0]["source"]
    by_ind = {}
    units = {}
    for r in rows:
        by_ind.setdefault(r["indicator"], {})[(r["key"], r["location"])] = r["value"]
        units[r["indicator"]] = r["unit"]
    mc, m, G, direct, has_fixed = _process_inventory(store, model_id)
    info = _flowinfo(store, mc)
    names = {r["id"]: r["name"] for r in store.q("SELECT id, name FROM activities")}
    sc = m["scope"] or {}
    site = (sc.get("geography") or "GLO").strip().upper() or "GLO"
    land = {}
    for i, (n, ctx_, u) in enumerate(info):
        kind, lu = land_flow(n)
        if kind:
            land[i] = (kind, lu, u)
    out_inds = []
    Gl = G[list(land), :].tocsc() if land else None
    lidx = list(land)
    for ind, table in by_ind.items():
        total = 0.0
        how_area = {"exact": 0.0, "country": 0.0, "global": 0.0, "none": 0.0}
        by_kind, by_type, by_loc, missing = {}, {}, {}, {}

        def add(amount, flow_i, loc, proc):
            nonlocal total
            kind, lu, u = land[flow_i]
            cf, how = _lookup(table, f"{kind}|{lu}", loc)
            how_area[how] += abs(amount)
            if cf is None:
                missing[f"{kind}: {lu}"] = missing.get(f"{kind}: {lu}", 0.0) + abs(amount)
                return
            v = amount * cf
            total += v
            by_kind[kind] = by_kind.get(kind, 0.0) + v
            by_type[lu] = by_type.get(lu, 0.0) + v
            by_loc[loc] = by_loc.get(loc, 0.0) + v
        if Gl is not None:
            nz = Gl.nonzero()
            for j, p in zip(*nz):
                add(float(Gl[j, p]), lidx[j], mc.act_loc[p] or "GLO", names.get(int(mc.act_ids[p]), ""))
        for i in lidx:
            if direct[i]:
                add(float(direct[i]), i, site, m["name"])
        area = sum(how_area.values())
        tot_abs = area or 1.0
        out_inds.append({"indicator": ind, "unit": units.get(ind, ""), "total": total, "land_area": area,
                         "completeness": {k: v / tot_abs for k, v in how_area.items()},
                         "by_kind": [{"kind": k, "impact": v} for k, v in by_kind.items()],
                         "by_land_use": sorted([{"land_use": k, "impact": v} for k, v in by_type.items()], key=lambda x: -abs(x["impact"]))[:20],
                         "by_location": sorted([{"location": k, "impact": v} for k, v in by_loc.items()], key=lambda x: -abs(x["impact"]))[:20],
                         "without_factor": sorted([{"flow": k, "amount": v} for k, v in missing.items()], key=lambda x: -x["amount"])[:20]})
    out_inds.sort(key=lambda x: LANCA_INDICATORS.index(x["indicator"]) if x["indicator"] in LANCA_INDICATORS else 99)
    return {"method": "LANCA", "source": src, "demo": src.startswith("demo"), "indicators": out_inds,
            "n_land_flows": len(lidx), "has_epd_lines": has_fixed,
            "empty": all(x["land_area"] <= 0 for x in out_inds),
            "note": "Occupation (m2*a) and transformation to/from (m2) flows of every process at its own location, and the "
                    "model's own land flows at the study geography, times the LANCA factor of the land use type, kind "
                    "and location. Completeness is the share of land area (occupation and transformation together) "
                    "with an exact, country, global or no factor."}


def demo_factors(store):
    """Illustrative factors to try the workflow. NOT AWARE 2.0 or LANCA values."""
    aw = ("location,agri,non_agri,unknown\nGLO,40,20,40\nFR,8,5,7\nDE,3,2,3\nCN,60,30,55\nRER,10,6,9\n")
    import_factors(store, AWARE, aw, demo=True)
    rows = ["indicator,kind,land_use,location,value,unit"]
    for ind, k in (("erosion resistance", 1.0), ("groundwater regeneration", 0.5), ("biotic production", 2.0)):
        for loc, f in (("GLO", 1.0), ("FR", 0.8)):
            rows.append(f"{ind},occupation,arable land,{loc},{k * f},demo unit")
            rows.append(f"{ind},transformation_to,arable land,{loc},{k * f * 20},demo unit")
            rows.append(f"{ind},transformation_from,forest,{loc},{-k * f * 20},demo unit")
    import_factors(store, LANCA, "\n".join(rows), demo=True)
    return status(store)
