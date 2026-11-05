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
import units as unitconv

AWARE = "AWARE"
LANCA = "LANCA"
AWARE_USES = ("agri", "non-agri", "unknown")
AWARE_RANGE = (0.1, 100.0)       # AWARE factors are bounded between 0.1 and 100 m3 world-eq per m3
LANCA_INDICATORS = ("erosion resistance", "mechanical filtration", "physicochemical filtration",
                    "groundwater regeneration", "biotic production", "soil organic carbon", "soil quality index")
LANCA_REF_UNIT = {"occupation": "m2*a", "transformation_to": "m2", "transformation_from": "m2"}


_PER = re.compile(r"(?:/|\bper\s*)\(?\s*(m2\s*[*·.]?\s*(?:a|yr|year)|m2|ha\s*[*·.]?\s*(?:a|yr|year)|ha)\b", re.I)


def _lanca_per(unit):
    """'m2a', 'm2', 'haa' or 'ha': what a LANCA factor unit is per ('kg/(m2*a)', 'per m2', 'cm3/(ha*yr)'), or ''."""
    m = _PER.search(unit or "")
    if not m:
        return ""
    t = re.sub(r"[\s*·.]", "", m.group(1).lower()).replace("year", "a").replace("yr", "a")
    return t


def _lanca_unit_ok(kind, unit):
    """A LANCA factor is per m2*a for occupation and per m2 for transformation; the unit text must say per what
    ('kg/(m2*a)', 'per m2', '.../m2'). Returns (ok, reason). An empty unit is accepted with a warning."""
    if not (unit or "").strip():
        return True, "no unit given"
    per = _lanca_per(unit)
    if not per:
        return False, "the unit must say per what area (e.g. kg/(m2*a) for occupation or kg/m2 for transformation)"
    if kind == "occupation" and per not in ("m2a", "haa"):
        return False, f"an occupation factor must be per m2*a, not per {per}"
    if kind != "occupation" and per not in ("m2", "ha"):
        return False, f"a transformation factor must be per m2, not per {per}"
    return True, ""


LANCA_KINDS = ("occupation", "transformation_to", "transformation_from")
AGRI_WORDS = ("irrigation", "irrigated")
BACKGROUND_USES = ("by process", "unknown")


def _month_profile(v):
    """Share of the model's own water use in each month: a list of 12 numbers (normalised), a month number 1-12, or None."""
    if v in (None, "", []):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
        m = int(v)
        return [1.0 if i == m - 1 else 0.0 for i in range(12)] if 1 <= m <= 12 else None
    if isinstance(v, str):
        v = [x for x in re.split(r"[;,\s]+", v.strip()) if x]
    try:
        vals = [max(0.0, float(x)) for x in v]
    except (TypeError, ValueError):
        return None
    if len(vals) != 12 or not sum(vals):
        return None
    t = sum(vals)
    return [x / t for x in vals]


def _monthly_cf(monthly, use, loc, prof):
    """Profile-weighted monthly factor; every month with use must have a factor (same location fallbacks)."""
    total, hows = 0.0, set()
    for i, sh in enumerate(prof):
        if not sh:
            continue
        cf, how = _lookup(monthly, f"{use}|m{i + 1}", loc)
        if cf is None and use != "unknown":
            cf, how = _lookup(monthly, f"unknown|m{i + 1}", loc)
        if cf is None:
            return None, "none"
        total += sh * cf
        hows.add(how)
    # completeness category: the least specific fallback used by any month
    for h in ("global", "country", "exact"):
        if h in hows:
            return total, h
    return total, "exact"


# ---------------------------------------------------------------------------------------------- GIS (GeoJSON)
def _rings(geom):
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return geom["coordinates"]
    raise ValueError(f"Geometry type {t} is not supported (Polygon or MultiPolygon).")


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-300) + x1:
            inside = not inside
    return inside


def point_in(geom, lon, lat):
    """Even-odd rule per polygon: inside the outer ring and in none of its holes."""
    for poly in _rings(geom):
        if poly and _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
            return True
    return False


def import_geojson(store, method, text, id_property, source="", replace=True):
    """Import watershed (or region) polygons, GeoJSON in WGS84 longitude/latitude, e.g. the AWARE 2.0 basin layer
    converted from its shapefile (QGIS or ogr2ogr). id_property names the property that holds the location code used
    in the factor table. If the features also carry the properties agri, non_agri, unknown, the factors are imported
    with them."""
    import json
    method = method.upper()
    try:
        gj = json.loads(text)
    except ValueError:
        raise ValueError("The file is not valid GeoJSON.")
    feats = gj.get("features") if gj.get("type") == "FeatureCollection" else [gj] if gj.get("type") == "Feature" else None
    if not feats:
        raise ValueError("Expected a GeoJSON FeatureCollection of polygons.")
    shapes, factors, rejected = [], [], []
    for n, f in enumerate(feats):
        props = f.get("properties") or {}
        loc = str(props.get(id_property) or "").strip().upper()
        geom = f.get("geometry") or {}
        if not loc:
            rejected.append({"feature": n, "reason": f"no '{id_property}' property"})
            continue
        try:
            pts = [p for poly in _rings(geom) for ring in poly for p in ring]
        except (ValueError, KeyError, TypeError) as e:
            rejected.append({"feature": n, "reason": str(e)})
            continue
        if not pts or any(not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in pts[:50]):
            rejected.append({"feature": n, "reason": "coordinates must be longitude/latitude (WGS84)"})
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        shapes.append((method, loc, str(props.get("name") or loc), json.dumps(geom), min(xs), min(ys), max(xs), max(ys),
                       source or "imported GeoJSON"))
        if method == AWARE:
            for use in ("agri", "non_agri", "unknown"):
                v = _num(props.get(use))
                if v is not None:
                    if AWARE_RANGE[0] - 1e-9 <= v <= AWARE_RANGE[1] + 1e-9:
                        factors.append((AWARE, "water scarcity", use, loc, v, "m3 world-eq/m3"))
                    else:
                        rejected.append({"feature": n, "reason": f"{use} factor {v:g} outside 0.1 to 100"})
    if not shapes:
        raise ValueError("No usable polygon was found." + (f" {len(rejected)} features were rejected." if rejected else ""))
    with store.lock:
        if replace:
            store.conn.execute("DELETE FROM native_shapes WHERE method=?", (method,))
        store.conn.executemany("INSERT INTO native_shapes(method,location,name,geometry,minx,miny,maxx,maxy,source) "
                               "VALUES(?,?,?,?,?,?,?,?,?)", shapes)
        if factors:
            store.conn.executemany("INSERT INTO native_factors(method,indicator,key,location,value,unit,source) "
                                   "VALUES(?,?,?,?,?,?,?)", [r + (source or "imported GeoJSON",) for r in factors])
        store.conn.commit()
    return {"shapes": len(shapes), "factors": len(factors), "rejected": rejected[:100], "n_rejected": len(rejected)}


def locate(store, method, lat, lon):
    """The imported polygon that contains a point (smallest bounding box first when polygons overlap)."""
    import json
    cands = store.q("SELECT location, name, geometry, (maxx-minx)*(maxy-miny) AS area FROM native_shapes WHERE method=? "
                    "AND minx<=? AND maxx>=? AND miny<=? AND maxy>=? ORDER BY area", (method.upper(), lon, lon, lat, lat))
    for c in cands:
        if point_in(json.loads(c["geometry"]), lon, lat):
            return {"location": c["location"], "name": c["name"], "lat": lat, "lon": lon}
    return None


def _use_key(u):
    u = (u or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    return {"agricultural": "agri", "non_agricultural": "non_agri", "nonagri": "non_agri"}.get(u, u)


def _use_of(process_name, rule="by process"):
    """AWARE type of use of a supply-chain process. 'by process': irrigation processes are agricultural, every other
    process non-agricultural (industry, energy, households). 'unknown': the unspecified factor except for
    irrigation."""
    if any(w in (process_name or "").lower() for w in AGRI_WORDS):
        return "agri"
    return "non_agri" if rule == "by process" else "unknown"

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
    no_unit = 0
    if method == AWARE:
        for need in ("location",):
            if need not in cols:
                raise ValueError("The AWARE table needs a 'location' column and the columns agri, non_agri, unknown.")
        for n, r in enumerate(rdr, 2):
            loc = str(r.get(cols["location"]) or "").strip()
            if not loc:
                continue
            month = ""
            if "month" in cols and str(r.get(cols["month"]) or "").strip():
                try:
                    mo = int(float(str(r.get(cols["month"])).strip()))
                except ValueError:
                    mo = 0
                if not 1 <= mo <= 12:
                    rejected.append({"row": n, "location": loc, "reason": "month must be 1 to 12 (or empty for the annual factor)"})
                    continue
                month = f"|m{mo}"
            for use, col in (("agri", "agri"), ("non_agri", "non_agri"), ("unknown", "unknown")):
                if col not in cols:
                    continue
                v = _num(r.get(cols[col]))
                if v is None:
                    continue
                if not AWARE_RANGE[0] - 1e-9 <= v <= AWARE_RANGE[1] + 1e-9:
                    rejected.append({"row": n, "location": loc, "reason": f"{use} factor {v:g} is outside 0.1 to 100"})
                    continue
                rows.append((AWARE, "water scarcity", use + month, loc.upper(), v, "m3 world-eq/m3"))
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
            okay, why = _lanca_unit_ok(kind, unit)
            if not okay:
                rejected.append({"row": n, "location": loc, "reason": why})
                continue
            if why:
                no_unit += 1
            if _lanca_per(unit) in ("haa", "ha"):
                v = v / 1e4                       # per hectare (year) -> per m2 (year)
                unit = unit + " (converted to per m2)"
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
    warn = []
    if method == LANCA and no_unit:
        warn.append(f"{no_unit} factors have no unit: Cyclia assumes per m2*a (occupation) and per m2 (transformation).")
    if not demo and not source:
        warn.append("No source was given: name the factor set and its version (e.g. 'LANCA 2.5, Fraunhofer IBP, 2023') "
                    "so the results can be traced.")
    return {"method": method, "factors": len(rows), "rejected": rejected[:200], "n_rejected": len(rejected), "source": src,
            "warnings": warn}


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


WATER_KINDS = ("withdrawal", "returned", "evaporated", "to_sea", "to_soil")


def _water_kind(name, context, unit):
    """Classify an elementary water flow for AWARE (WULCA): (kind, sign, factor to m3).

    Consumption = water taken from nature minus water returned to the SAME watershed. So only a release to fresh
    water (surface, ground or unspecified water) at the process location counts as a return (sign -1). Water
    evaporated to air, discharged to the sea or ocean, and water released to soil are consumption: they are not an
    identified return to the watershed and get no credit (sign 0, reported separately)."""
    n = (name or "").lower()
    if not (n == "water" or n.startswith("water,") or n.startswith("water ")):
        return None, 0, 0.0
    u = (unit or "").strip()
    k = 1.0 if u in ("m3", "m³") else 0.001 if u in ("kg", "l", "L") else None
    if k is None:
        return None, 0, 0.0
    c = (context or "").lower()
    if c.startswith("natural resource") or c.startswith("resource"):
        return "withdrawal", 1, k
    if c.startswith("air"):
        return "evaporated", 0, k
    if c.startswith("soil"):
        return "to_soil", 0, k
    if c.startswith("water"):
        if "ocean" in c or "sea" in c:
            return "to_sea", 0, k
        return "returned", -1, k
    return None, 0, 0.0


def _water_flow(name, context, unit):
    """+1 for water taken from nature, -1 for water returned to fresh water, 0 otherwise; with the factor to m3."""
    _, sign, k = _water_kind(name, context, unit)
    return sign, k


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
    # keys stored by 1.3.5 were 'non-agri'; the lookup uses 'non_agri' (before 1.3.6 the non-agricultural factor was
    # never found and the unknown factor was used instead)
    table = {(_use_key(r["key"]), r["location"]): r["value"] for r in rows if "|m" not in r["key"]}
    monthly = {}
    for r in rows:
        if "|m" in r["key"]:
            u, mo = r["key"].split("|m")
            monthly[(_use_key(u) + f"|m{int(mo)}", r["location"])] = r["value"]
    src = rows[0]["source"]
    mc, m, G, direct, has_fixed = _process_inventory(store, model_id)
    info = _flowinfo(store, mc)
    sc = m["scope"] or {}
    site = (sc.get("aware_location") or sc.get("geography") or "").strip().upper()
    gis = None
    monthly_used = False
    if sc.get("aware_lat") not in (None, "") and sc.get("aware_lon") not in (None, ""):
        try:
            gis = locate(store, AWARE, float(sc["aware_lat"]), float(sc["aware_lon"]))
        except (TypeError, ValueError):
            gis = None
        if gis:
            site = gis["location"]
    names = {r["id"]: r["name"] for r in store.q("SELECT id, name FROM activities")}
    wkind = {i: _water_kind(*info[i]) for i in range(len(info))}
    wflow = {i: (sg, k) for i, (kind, sg, k) in wkind.items()}
    widx = [i for i, (kind, sg, k) in wkind.items() if kind]
    balance = dict.fromkeys(WATER_KINDS, 0.0)
    bg_default = sc.get("aware_background_use") or "by process"
    total, cons_total = 0.0, 0.0
    how_share = {"exact": 0.0, "country": 0.0, "global": 0.0, "none": 0.0}
    by_loc, by_use, unmatched = {}, {}, {}
    top = []
    Gw = G[widx, :] if widx else None
    if Gw is not None:
        Gw = Gw.tocsc()
        for p in np.unique(Gw.nonzero()[1]):
            col = Gw[:, p].toarray().ravel()
            for j in range(len(widx)):
                if col[j]:
                    balance[wkind[widx[j]][0]] += col[j] * wkind[widx[j]][2]
            c = float(sum(col[j] * wflow[widx[j]][0] * wflow[widx[j]][1] for j in range(len(widx))))
            if c == 0:
                continue
            loc = mc.act_loc[p] or "GLO"
            nm = names.get(int(mc.act_ids[p]), "")
            use = _use_of(nm, bg_default)
            cf, how = _lookup(table, use, loc)
            fuse = use
            if cf is None and use != "unknown":
                cf, how = _lookup(table, "unknown", loc)
                fuse = "unknown"
            how_share[how] += abs(c)
            cons_total += c
            if cf is None:
                unmatched[loc] = unmatched.get(loc, 0.0) + c
                continue
            imp = c * cf
            total += imp
            by_loc[loc] = by_loc.get(loc, 0.0) + imp
            by_use[use] = by_use.get(use, 0.0) + imp
            top.append({"process": nm, "location": loc, "use": use, "factor_of_use": fuse, "consumption_m3": c,
                        "factor": cf, "how": how, "impact": imp})
    for i in widx:
        if direct[i]:
            balance[wkind[i][0]] += float(direct[i]) * wkind[i][2]
    dc = float(sum(direct[i] * wflow[i][0] * wflow[i][1] for i in widx)) if widx else 0.0
    if dc:
        use = _use_key(sc.get("aware_use") or "unknown")
        cf, how = _lookup(table, use, site or "GLO")
        if cf is None and use != "unknown":
            cf, how = _lookup(table, "unknown", site or "GLO")
        prof = _month_profile(sc.get("aware_months"))
        if prof and monthly:
            mcf, mhow = _monthly_cf(monthly, use, site or "GLO", prof)
            if mcf is not None:
                cf, how = mcf, mhow
                monthly_used = True
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
            "water_balance_m3": balance, "background_use": bg_default,
            "site": site or "GLO", "site_from_gis": gis, "monthly_used": monthly_used,
            "monthly_factors_available": bool(monthly),
            "completeness": {k: v / tot_abs for k, v in how_share.items()},
            "by_location": sorted([{"location": k, "impact": v} for k, v in by_loc.items()], key=lambda x: -abs(x["impact"])),
            "by_use": [{"use": k, "impact": v} for k, v in by_use.items()],
            "unmatched": sorted([{"location": k, "consumption_m3": v} for k, v in unmatched.items()],
                                key=lambda x: -abs(x["consumption_m3"])),
            "top": top[:30], "site": site or "GLO", "has_epd_lines": has_fixed,
            "note": "Water consumption per process = water taken from nature minus water returned to fresh water at the process "
                    "location (m3). Evaporation, discharge to the sea and water released to soil are consumption (no "
                    "credit), as defined by WULCA. Process location for the supply chain; the model's own water flows at "
                    "the AWARE location given for the model (site or watershed), else the study geography. Type of use: "
                    "irrigation processes agricultural; other supply-chain processes non-agricultural (or 'unknown' if "
                    "chosen); the model's own water use as chosen. Fallbacks: country of a sub-national code, then the "
                    "global factor. Monthly factors and GIS watershed lookup are not supported. EPD lines carry no water "
                    "inventory."}


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
        by_kind, by_type, by_loc, missing, bad_unit = {}, {}, {}, {}, {}

        def add(amount, flow_i, loc, proc):
            nonlocal total
            kind, lu, u = land[flow_i]
            conv = unitconv.factor(u, LANCA_REF_UNIT[kind]) if u else 1.0
            if conv is None:                       # e.g. an occupation flow in m2 (no time): not comparable
                bad_unit[f"{kind}: {lu} [{u}]"] = bad_unit.get(f"{kind}: {lu} [{u}]", 0.0) + abs(amount)
                return
            amount = amount * conv
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
                         "without_factor": sorted([{"flow": k, "amount": v} for k, v in missing.items()], key=lambda x: -x["amount"])[:20],
                         "unit_not_convertible": [{"flow": k, "amount": v} for k, v in bad_unit.items()]})
    out_inds.sort(key=lambda x: LANCA_INDICATORS.index(x["indicator"]) if x["indicator"] in LANCA_INDICATORS else 99)
    return {"method": "LANCA", "source": src, "demo": src.startswith("demo"), "indicators": out_inds,
            "n_land_flows": len(lidx), "has_epd_lines": has_fixed,
            "empty": all(x["land_area"] <= 0 for x in out_inds),
            "note": "Occupation (m2*a) and transformation to/from (m2) flows of every process at its own location, and the "
                    "model's own land flows at the study geography, times the LANCA factor of the land use type, kind "
                    "and location. Completeness is the share of land area (occupation and transformation together) "
                    "with an exact, country, global or no factor."}


SQI_INDICATORS = ("erosion resistance", "mechanical filtration", "groundwater regeneration", "biotic production")


def sqi_aggregate(store, normalisation, weights=None, source="", replace=True):
    """Soil quality index factors from the LANCA indicator factors, by linear aggregation as in the EF method
    (De Laurentiis et al. 2019): SQI_CF(kind, land use, location) = sum_i w_i * CF_i / N_i over erosion resistance,
    mechanical filtration, groundwater regeneration and biotic production (physicochemical filtration is left out
    because it correlates with mechanical filtration). N_i (normalisation references) must be given from the method
    version followed; weights default to equal (1/4 each), which is an assumption to state. Only keys (kind, land
    use, location) with all four indicators are aggregated; the others are listed. Where official SQI factors exist
    for the same key, the relative difference to the aggregated factor is reported."""
    norm = {k.strip().lower(): float(v) for k, v in (normalisation or {}).items() if v not in (None, "")}
    miss = [i for i in SQI_INDICATORS if not norm.get(i)]
    if miss:
        raise ValueError("Give the normalisation reference N of every indicator (from the method version you follow): "
                         + ", ".join(miss) + ".")
    w = {i: float((weights or {}).get(i, 0.25)) for i in SQI_INDICATORS}
    if abs(sum(w.values()) - 1) > 1e-6:
        raise ValueError(f"The weights must add up to 1 (they add up to {sum(w.values()):g}).")
    rows = store.q("SELECT indicator, key, location, value FROM native_factors WHERE method=?", (LANCA,))
    by = {}
    for r in rows:
        by.setdefault((r["key"], r["location"]), {})[r["indicator"]] = r["value"]
    out, incomplete, compare = [], [], []
    for (key, loc), d in by.items():
        if not all(i in d for i in SQI_INDICATORS):
            if any(i in d for i in SQI_INDICATORS):
                incomplete.append({"key": key, "location": loc, "missing": [i for i in SQI_INDICATORS if i not in d]})
            continue
        v = sum(w[i] * d[i] / norm[i] for i in SQI_INDICATORS)
        out.append((LANCA, "soil quality index", key, loc, v, "dimensionless (aggregated)"))
        if "soil quality index" in d and d["soil quality index"]:
            o = d["soil quality index"]
            compare.append({"key": key, "location": loc, "official": o, "aggregated": v,
                            "relative_difference": (v - o) / abs(o)})
    if not out:
        raise ValueError("No land use type and location has factors for all four LANCA indicators.")
    src = f"SQI aggregated by Cyclia from LANCA factors ({source or 'normalisation as given'}; weights " + \
          ", ".join(f"{i} {w[i]:g}" for i in SQI_INDICATORS) + ")"
    with store.lock:
        if replace:
            store.conn.execute("DELETE FROM native_factors WHERE method=? AND indicator='soil quality index'", (LANCA,))
        store.conn.executemany("INSERT INTO native_factors(method,indicator,key,location,value,unit,source) "
                               "VALUES(?,?,?,?,?,?,?)", [r + (src,) for r in out])
        store.conn.commit()
    compare.sort(key=lambda x: -abs(x["relative_difference"]))
    return {"factors": len(out), "incomplete": incomplete[:100], "n_incomplete": len(incomplete),
            "compared_with_official": compare[:100], "n_compared": len(compare),
            "max_relative_difference": max((abs(x["relative_difference"]) for x in compare), default=None),
            "source": src, "weights": w, "normalisation": norm}


def demo_factors(store):
    """Illustrative factors to try the workflow. NOT AWARE 2.0 or LANCA values."""
    aw = ("location,agri,non_agri,unknown\nGLO,40,20,40\nFR,8,5,7\nDE,3,2,3\nCN,60,30,55\nRER,10,6,9\n")
    import_factors(store, AWARE, aw, demo=True)
    rows = ["indicator,kind,land_use,location,value,unit"]
    for ind, k in (("erosion resistance", 1.0), ("groundwater regeneration", 0.5), ("biotic production", 2.0)):
        for loc, f in (("GLO", 1.0), ("FR", 0.8)):
            rows.append(f"{ind},occupation,arable land,{loc},{k * f},demo/(m2*a)")
            rows.append(f"{ind},transformation_to,arable land,{loc},{k * f * 20},demo/m2")
            rows.append(f"{ind},transformation_from,forest,{loc},{-k * f * 20},demo/m2")
    import_factors(store, LANCA, "\n".join(rows), demo=True)
    return status(store)
