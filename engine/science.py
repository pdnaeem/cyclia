"""Scientific extensions of the matrix model.

1. Background scenarios: rule-based changes to the database before calculation.
   * prospective LCA: scale emissions or inputs towards a target year, swap supplier mixes (in the spirit of
     premise, Sacchi et al. 2022), with linear interpolation between the base year and the given target years;
   * consequential LCA: replace the suppliers of a market by its marginal supplier(s) (Weidema et al. 2009).
2. Toxicity screening factors: Mackay EQC Level III multimedia fate model (Mackay et al. 1996) combined with
   USEtox-style exposure and effect factors (Rosenbaum et al. 2008). For chemicals without official USEtox factors.
3. Emissions from an external model (time series per compartment) as inventory lines.
4. Coordinates of location codes for the map of results by location.
"""
import copy
import csv
import io
import math
import re
import uuid

import numpy as np

from canon import canon

RULE_TYPES = {
    "scale_emission": "Scale an elementary flow of selected datasets (e.g. CO2 of electricity production x 0.4)",
    "scale_input": "Scale an input of selected datasets (e.g. electricity use of cement production x 0.8)",
    "swap": "Replace the suppliers of a product in selected datasets by a new mix (prospective mix or marginal supplier)",
    "set_exchanges": "Set exchange amounts from a scenario file (premise or Activity Browser scenario difference file)",
}


# ============================================================================ background rules
def _factor(value, base_year, year):
    """A number, or {year: factor} interpolated linearly from factor 1 at the base year."""
    if isinstance(value, (int, float)):
        return float(value)
    pts = sorted((float(k), float(v)) for k, v in dict(value).items())
    if not pts:
        return 1.0
    if year is None:
        return pts[-1][1]
    pts = [(float(base_year), 1.0)] + [p for p in pts if p[0] > base_year]
    if year <= pts[0][0]:
        return 1.0
    for (y0, f0), (y1, f1) in zip(pts, pts[1:]):
        if y0 <= year <= y1:
            return f0 + (f1 - f0) * (year - y0) / (y1 - y0)
    return pts[-1][1]


def validate_rules(rules):
    for i, r in enumerate(rules, 1):
        t = r.get("type")
        if t not in RULE_TYPES:
            raise ValueError(f"Rule {i}: unknown type '{t}'.")
        if t == "set_exchanges":
            if not (r.get("tech") or r.get("bio")):
                raise ValueError(f"Rule {i}: the scenario file gave no exchanges.")
            continue
        if not (r.get("activity") or r.get("activity_ids")):
            raise ValueError(f"Rule {i}: say which datasets it applies to (name contains ..., or chosen datasets).")
        if t == "scale_emission" and not r.get("flow"):
            raise ValueError(f"Rule {i}: give the elementary flow name, e.g. carbon dioxide, fossil.")
        if t == "scale_input" and not r.get("input"):
            raise ValueError(f"Rule {i}: give the input (name or product contains ...).")
        if t in ("scale_emission", "scale_input"):
            f = r.get("factor")
            try:
                vals = [float(f)] if not isinstance(f, dict) else [float(v) for v in f.values()]
                if isinstance(f, dict):
                    [float(k) for k in f]
            except (TypeError, ValueError):
                raise ValueError(f"Rule {i}: the factor must be a number or year: number pairs.")
            if not vals or any(v < 0 for v in vals):
                raise ValueError(f"Rule {i}: factors must be zero or positive.")
        if t == "swap":
            if not r.get("product"):
                raise ValueError(f"Rule {i}: give the product whose suppliers are replaced.")
            to = r.get("to") or []
            if not to:
                raise ValueError(f"Rule {i}: choose at least one new supplier.")
            tot = sum(float(x.get("share") or 0) for x in to)
            if abs(tot - 1) > 1e-6:
                raise ValueError(f"Rule {i}: supplier shares must add up to 1 (now {tot:g}).")


def _select(acts, rule):
    """Indices of datasets matched by a rule: explicit ids, or name contains a text (and optional location)."""
    if rule.get("activity_ids"):
        ids = {int(x) for x in rule["activity_ids"]}
        return np.array([i for i, a in enumerate(acts) if a["id"] in ids], dtype=np.int64)
    pat = str(rule.get("activity") or "").lower().strip()
    loc = str(rule.get("location") or "").upper().strip()
    return np.array([i for i, a in enumerate(acts) if pat in (a["name"] or "").lower()
                     and (not loc or (a["location"] or "").upper() == loc)], dtype=np.int64)


def apply_rules(store, base, rules, base_year=2020, year=None):
    """Return a copy of the matrix cache with the rules applied to its exchanges, refactorised."""
    import calc
    acts = store.q("SELECT id, name, product, location FROM activities ORDER BY id")
    if len(acts) != base.n:
        raise ValueError("The library changed; calculate again.")
    v = copy.copy(base)
    t_rows, t_cols, t_amt = base.t_rows.copy(), base.t_cols.copy(), base.t_amt.copy()
    t_unc = {k: a.copy() for k, a in base.t_unc.items()}
    b_amt = base.b_amt.copy()
    report = []
    names = [(a["name"] or "").lower() for a in acts]
    prods = [(a["product"] or "").lower() for a in acts]
    keymap = None
    for n, r in enumerate(rules, 1):
        if r["type"] == "set_exchanges":
            if keymap is None:
                keymap = {(row["db"], row["key"]): base.act_index.get(row["id"]) for row in store.q(
                    "SELECT a.id, a.key, d.name AS db FROM activities a JOIN databases d ON d.id=a.db_id")}
                flowmap = {row["uuid"]: base.flow_index.get(row["id"]) for row in store.q("SELECT id, uuid FROM flows")}
            t_rows, t_cols, t_amt, t_unc, b_amt, msg = _set_exchanges(base, r, keymap, flowmap, t_rows, t_cols, t_amt,
                                                                      t_unc, b_amt)
            report.append(f"Rule {n}: {msg}")
            continue
        sel = _select(acts, r)
        if not len(sel):
            raise ValueError(f"rule {n} matches no dataset ('{r.get('activity') or r.get('activity_ids')}').")
        mask_cons = np.zeros(base.n, dtype=bool)
        mask_cons[sel] = True
        if r["type"] == "scale_emission":
            f = _factor(r["factor"], base_year, year)
            pat = canon(str(r["flow"]), "", "")[0]
            fmask = np.array([pat in cn for cn, _ in base.flow_cname], dtype=bool)
            m = mask_cons[base.b_cols] & fmask[base.b_rows]
            b_amt[m] *= f
            report.append(f"Rule {n}: '{r['flow']}' x {f:.4g} in {len(sel)} dataset(s), {int(m.sum())} exchanges")
        elif r["type"] == "scale_input":
            f = _factor(r["factor"], base_year, year)
            pat = str(r["input"]).lower()
            imask = np.array([pat in nm or pat in pr for nm, pr in zip(names, prods)], dtype=bool)
            m = mask_cons[t_cols] & imask[t_rows] & (t_rows != t_cols)
            t_amt[m] *= f
            report.append(f"Rule {n}: input '{r['input']}' x {f:.4g} in {len(sel)} dataset(s), {int(m.sum())} exchanges")
        else:
            pat = str(r["product"]).lower()
            pmask = np.array([pat in pr for pr in prods], dtype=bool)
            m = mask_cons[t_cols] & pmask[t_rows] & (t_rows != t_cols)
            targets = []
            for x in r["to"]:
                j = base.act_index.get(int(x["id"]))
                if j is None:
                    raise ValueError(f"rule {n}: a chosen supplier is no longer in the library.")
                targets.append((j, float(x["share"])))
            add_r, add_c, add_a = [], [], []
            n_cons = len(np.unique(t_cols[m]))
            for c in np.unique(t_cols[m]):
                sel_c = m & (t_cols == c)
                tot = float(t_amt[sel_c].sum())
                t_amt[sel_c] = 0.0
                for j, sh in targets:
                    if j == c:
                        continue
                    add_r.append(j)
                    add_c.append(int(c))
                    add_a.append(tot * sh)
            if add_r:
                t_rows = np.concatenate([t_rows, np.array(add_r, dtype=np.int64)])
                t_cols = np.concatenate([t_cols, np.array(add_c, dtype=np.int64)])
                t_amt = np.concatenate([t_amt, np.array(add_a)])
                for k in ("p1", "p2", "p3"):
                    t_unc[k] = np.concatenate([t_unc[k], np.full(len(add_r), np.nan)])
                t_unc["type"] = np.concatenate([t_unc["type"], np.zeros(len(add_r), dtype=np.int8)])
            report.append(f"Rule {n}: suppliers of '{r['product']}' replaced in {n_cons} dataset(s) by "
                          + ", ".join(f"{acts[j]['name']} [{acts[j]['location']}] {sh:.0%}" for j, sh in targets))
    new_b = [x for r in rules for x in r.pop("_new_bio", [])]
    if new_b:
        v.b_rows = np.concatenate([base.b_rows, np.array([x[0] for x in new_b], dtype=np.int64)])
        v.b_cols = np.concatenate([base.b_cols, np.array([x[1] for x in new_b], dtype=np.int64)])
        b_amt = np.concatenate([b_amt, np.array([x[2] for x in new_b])])
        v.b_unc = {k: np.concatenate([a, np.zeros(len(new_b), dtype=np.int8) if k == "type" else np.full(len(new_b), np.nan)])
                   for k, a in base.b_unc.items()}
    v.t_rows, v.t_cols, v.t_amt, v.t_unc, v.b_amt = t_rows, t_cols, t_amt, t_unc, b_amt
    v.A = v.build_A(t_amt)
    v.B = v.build_B(b_amt)
    v.lu = calc.factorise(v.A)
    v.unit_cache = {}
    v.bg_report = report
    return v


def _set_exchanges(base, r, keymap, flowmap, t_rows, t_cols, t_amt, t_unc, b_amt):
    """Exchanges given as [consumer db, consumer key, supplier db, supplier key, amount] (technosphere) and
    [db, key, flow uuid, amount] (biosphere). Existing exchanges are set to the amount (duplicates to zero);
    missing technosphere exchanges are added. New biosphere exchanges are added to the matrix as well."""
    n = base.n
    pos = {}
    for i, (a, b) in enumerate(zip(t_rows.tolist(), t_cols.tolist())):
        pos.setdefault(a * n + b, []).append(i)
    add_r, add_c, add_a = [], [], []
    done = missing = 0
    for out_db, out_key, in_db, in_key, amt in r.get("tech") or []:
        o, i = keymap.get((out_db, out_key)), keymap.get((in_db, in_key))
        if o is None or i is None:
            missing += 1
            continue
        hit = pos.get(i * n + o)
        if hit:
            t_amt[hit[0]] = float(amt)
            for extra in hit[1:]:
                t_amt[extra] = 0.0
        elif o != i:
            add_r.append(i)
            add_c.append(o)
            add_a.append(float(amt))
        done += 1
    if add_r:
        t_rows = np.concatenate([t_rows, np.array(add_r, dtype=np.int64)])
        t_cols = np.concatenate([t_cols, np.array(add_c, dtype=np.int64)])
        t_amt = np.concatenate([t_amt, np.array(add_a)])
        for k in ("p1", "p2", "p3"):
            t_unc[k] = np.concatenate([t_unc[k], np.full(len(add_r), np.nan)])
        t_unc["type"] = np.concatenate([t_unc["type"], np.zeros(len(add_r), dtype=np.int8)])
    bpos = {}
    for i, (f, a) in enumerate(zip(base.b_rows.tolist(), base.b_cols.tolist())):
        bpos.setdefault((f, a), []).append(i)
    bdone = bmissing = 0
    new_b = []
    for db, key, fu, amt in r.get("bio") or []:
        a, f = keymap.get((db, key)), flowmap.get(fu)
        if a is None or f is None:
            bmissing += 1
            continue
        hit = bpos.get((f, a))
        if hit:
            b_amt[hit[0]] = float(amt)
            for extra in hit[1:]:
                b_amt[extra] = 0.0
        else:
            new_b.append((f, a, float(amt)))
        bdone += 1
    r["_new_bio"] = new_b  # applied by apply_rules after all rules
    msg = (f"{done:,} technosphere and {bdone:,} biosphere exchanges set from '{r.get('source', 'scenario file')}'"
           + (f"; {missing + bmissing:,} could not be found in this library" if missing + bmissing else ""))
    return t_rows, t_cols, t_amt, t_unc, b_amt, msg


def markets(store, model_id, max_nodes=6000, limit=40):
    """Datasets in the supply chain of a model that buy one product from several suppliers (markets): the
    candidates for a consequential (marginal supplier) rule, with their current suppliers and the alternatives."""
    m = store.model(model_id)
    if not m:
        raise ValueError("Model not found.")
    start = [i["ref_id"] for i in m["inputs"] if i["kind"] == "activity" and i["ref_id"]]
    seen, queue, found = set(start), list(start), []
    while queue and len(seen) < max_nodes:
        aid = queue.pop(0)
        ins = store.q("SELECT t.input_id, SUM(t.amount) AS amount FROM tech t WHERE t.output_id=? AND t.input_id!=? "
                      "GROUP BY t.input_id", (aid, aid))
        for r in ins:
            if r["input_id"] not in seen:
                seen.add(r["input_id"])
                queue.append(r["input_id"])
        if len(ins) >= 2:
            found.append(aid)
    out = []
    for aid in found:
        a = store.one("SELECT id, name, product, location, unit FROM activities WHERE id=?", (aid,))
        root = (a["product"] or "").split(",")[0].strip().lower()
        sup = store.q("SELECT i.id, i.name, i.location, i.product, SUM(t.amount) AS amount FROM tech t JOIN activities i "
                      "ON i.id=t.input_id WHERE t.output_id=? AND t.input_id!=? AND lower(i.product) LIKE ? "
                      "GROUP BY i.id ORDER BY amount DESC", (aid, aid, root + "%"))
        if len(sup) < 2:
            continue
        tot = sum(abs(s["amount"]) for s in sup) or 1
        for s in sup:
            s["share"] = abs(s["amount"]) / tot
        out.append({"market": a, "product_root": root, "suppliers": sup,
                    "alternatives": store.q("SELECT id, name, location FROM activities WHERE lower(product) LIKE ? "
                                            "AND id!=? AND lower(name) NOT LIKE 'market%' ORDER BY name LIMIT 80",
                                            (root + "%", aid))})
    out.sort(key=lambda x: (not x["market"]["name"].lower().startswith("market"), x["market"]["name"]))
    return out[:limit]


SDF_FIELDS = {"from activity name", "from reference product", "from location", "from categories", "from database",
              "from key", "to activity name", "to reference product", "to location", "to categories", "to database",
              "to key", "flow type", "from unit", "to unit", "from categories", "unit"}


def _parse_categories(v):
    t = str(v or "").strip().strip("()[]")
    parts = [p.strip().strip("'\"") for p in re.split(r"::|,|/", t) if p.strip().strip("'\"")]
    return (parts[0] if parts else ""), ("/".join(parts[1:]) if len(parts) > 1 else "")


def read_scenario_file(store, path, progress=lambda *a: None):
    """Read a scenario difference file (Activity Browser superstructure format, also written by premise):
    one row per exchange with 'from ...' (supplier or elementary flow), 'to ...' (consumer), 'flow type' and one
    column of amounts per scenario. Returns one rule set per scenario column."""
    low = path.lower()
    if low.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip() for h in next(it)]
        rows = (dict(zip(head, r)) for r in it)
    else:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rd = csv.DictReader(io.StringIO(text), dialect=dialect)
        head = [h.strip() for h in rd.fieldnames or []]
        rows = ({(k or "").strip(): v for k, v in r.items()} for r in rd)
    lhead = {h.lower(): h for h in head}
    need = ("from activity name", "to activity name", "flow type")
    if not all(n in lhead for n in need):
        raise ValueError("Not a scenario difference file: the columns 'from activity name', 'to activity name' and "
                         "'flow type' are needed (Activity Browser or premise superstructure export).")
    scen_cols = [h for h in head if h.lower() not in SDF_FIELDS and h]
    if not scen_cols:
        raise ValueError("No scenario columns found (one column of amounts per scenario after 'flow type').")
    g = lambda r, k: r.get(lhead.get(k, ""), "") or ""
    acts = store.q("SELECT a.key, a.name, a.product, a.location, d.name AS db FROM activities a JOIN databases d ON d.id=a.db_id")
    full, part = {}, {}
    for a in acts:
        full.setdefault(((a["name"] or "").lower(), (a["product"] or "").lower(), (a["location"] or "").lower()), (a["db"], a["key"]))
        part.setdefault(((a["name"] or "").lower(), (a["location"] or "").lower()), (a["db"], a["key"]))
    flows = {}
    for f in store.q("SELECT uuid, c_name, c_comp, c_sub FROM flows"):
        flows.setdefault((f["c_name"], f["c_comp"], f["c_sub"]), f["uuid"])
        flows.setdefault((f["c_name"], f["c_comp"], ""), f["uuid"])

    def act(r, side):
        k = (str(g(r, f"{side} activity name")).lower(), str(g(r, f"{side} reference product")).lower(),
             str(g(r, f"{side} location")).lower())
        return full.get(k) or part.get((k[0], k[2]))
    out = {c: {"tech": [], "bio": []} for c in scen_cols}
    stats = {"rows": 0, "unmatched": 0, "production": 0}
    for n, r in enumerate(rows):
        ft = str(g(r, "flow type")).strip().lower()
        if not ft:
            continue
        stats["rows"] += 1
        to = act(r, "to")
        if ft == "production":
            stats["production"] += 1
            continue
        if ft == "biosphere":
            from canon import canon
            comp, sub = _parse_categories(g(r, "from categories"))
            cn = canon(str(g(r, "from activity name")), comp, sub)
            fu = flows.get(cn) or flows.get((cn[0], cn[1], ""))
            if not (to and fu):
                stats["unmatched"] += 1
                continue
            for c in scen_cols:
                v = r.get(c)
                if v not in (None, ""):
                    out[c]["bio"].append([to[0], to[1], fu, float(str(v).replace(",", "."))])
        else:
            fr = act(r, "from")
            if not (to and fr):
                stats["unmatched"] += 1
                continue
            sign = -1.0 if ft == "substitution" else 1.0
            for c in scen_cols:
                v = r.get(c)
                if v not in (None, ""):
                    out[c]["tech"].append([to[0], to[1], fr[0], fr[1], sign * float(str(v).replace(",", "."))])
        if n % 20000 == 0:
            progress(min(90, 5 + n // 5000), f"Reading the scenario file ({n:,} rows)")
    return out, stats


def import_scenario_file(store, path, prefix="", progress=lambda *a: None):
    import os
    sets, stats = read_scenario_file(store, path, progress)
    if not any(v["tech"] or v["bio"] for v in sets.values()):
        raise ValueError(f"None of the {stats['rows']:,} exchanges matched datasets in this library. Import the same "
                         "database version the scenario file was made for.")
    ids = []
    for col, ex in sets.items():
        if not (ex["tech"] or ex["bio"]):
            continue
        name = (prefix + " " if prefix else "") + col
        rule = {"type": "set_exchanges", "source": os.path.basename(path), "tech": ex["tech"], "bio": ex["bio"]}
        old = store.one("SELECT id FROM main.bg_scenarios WHERE name=?", (name,))
        ids.append(store.save_bg_scenario({"id": old["id"] if old else None, "name": name, "kind": "prospective",
                                           "description": f"From scenario file {os.path.basename(path)}", "rules": [rule]}))
    return {"scenarios": len(ids), "rows": stats["rows"], "unmatched": stats["unmatched"],
            "warnings": [f"{stats['unmatched']:,} of {stats['rows']:,} exchanges refer to datasets or flows that are not "
                         "in this library and were skipped."] if stats["unmatched"] else []}


# ============================================================================ toxicity screening model
R_GAS = 8.314
T_K = 298.15
EQC = {  # Mackay et al. (1996) EQC standard environment, Level III
    "area_air": 1e11, "h_air": 1000.0, "area_water": 1e10, "h_water": 20.0, "area_soil": 9e10, "h_soil": 0.1,
    "h_sed": 0.01, "res_air_h": 100.0, "res_water_h": 1000.0, "vf_aerosol": 2e-11, "vf_ss": 5e-6, "foc_ss": 0.2,
    "soil_air": 0.2, "soil_water": 0.3, "soil_solid": 0.5, "foc_soil": 0.02, "sed_water": 0.8, "sed_solid": 0.2,
    "foc_sed": 0.04, "rho_solid": 2400.0, "k_air_side": 5.0, "k_water_side": 0.05, "rain": 9.7e-5,
    "scavenging": 2e5, "dry_dep": 10.8, "soil_air_diff": 0.02, "soil_water_diff": 1e-5, "soil_bl": 5.0,
    "sed_mtc": 1e-4, "sed_dep": 4.6e-8, "sed_resus": 1.1e-8, "sed_burial": 3.4e-8, "runoff_water": 3.9e-5,
    "runoff_solid": 2.3e-8, "doc": 5e-6, "population_density": 100.0,
}
EXPOSURE = {"inhalation_m3_d": 13.0, "drinking_water_m3_d": 0.002, "fish_kg_d": 0.03, "body_weight": 70.0,
            "lifetime_y": 70.0}
CHEM_FIELDS = {
    "mw": ("Molar mass", "g/mol", True), "log_kow": ("log Kow", "-", True),
    "henry": ("Henry's law constant", "Pa m3/mol", True), "koc": ("Koc (empty: 0.41 x Kow)", "L/kg", False),
    "vp": ("Vapour pressure (for particle binding)", "Pa", False),
    "hl_air": ("Half-life in air", "days", True), "hl_water": ("Half-life in water", "days", True),
    "hl_soil": ("Half-life in soil", "days", True), "hl_sed": ("Half-life in sediment (empty: 9 x water)", "days", False),
    "bcf": ("Bioconcentration factor fish (empty: from Kow)", "L/kg", False),
    "hc50": ("Ecotoxicity HC50 (average EC50, freshwater)", "mg/L", False),
    "ed50_cancer": ("Human ED50, cancer (oral)", "mg/kg/day", False),
    "ed50_noncancer": ("Human ED50, non-cancer (oral)", "mg/kg/day", False),
}


def _f(props, k, default=None):
    v = props.get(k)
    if v in (None, ""):
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{CHEM_FIELDS[k][0]} must be a number.")
    if not math.isfinite(x):
        raise ValueError(f"{CHEM_FIELDS[k][0]} must be finite.")
    return x


def fate_model(props, env=None):
    """Steady-state Level III fate. Returns fate factors FF[i][j] (days): mass in compartment j per unit emission
    flux (kg/day) into compartment i, for i, j in (air, water, soil, sediment)."""
    e = dict(EQC, **(env or {}))
    for k, (label, _, req) in CHEM_FIELDS.items():
        if req and props.get(k) in (None, ""):
            raise ValueError(f"{label} is needed.")
    mw = _f(props, "mw")
    kow = 10 ** _f(props, "log_kow")
    H = max(_f(props, "henry"), 1e-12)
    koc = _f(props, "koc", 0.41 * kow)
    if mw <= 0 or koc < 0:
        raise ValueError("Molar mass must be positive and Koc zero or positive.")
    hl = {c: _f(props, "hl_" + c) for c in ("air", "water", "soil")}
    hl["sed"] = _f(props, "hl_sed", 9 * hl["water"])
    if any(v is None or v <= 0 for v in hl.values()):
        raise ValueError("Half-lives must be positive.")
    k_deg = {c: math.log(2) / (v * 24.0) for c, v in hl.items()}  # 1/h
    vp = _f(props, "vp")
    Za, Zw = 1.0 / (R_GAS * T_K), 1.0 / H
    Zq = (6e6 / vp) * Za if vp and vp > 0 else 0.0
    Zs = koc * e["foc_soil"] * e["rho_solid"] * Zw / 1000.0
    Zsed = koc * e["foc_sed"] * e["rho_solid"] * Zw / 1000.0
    Zss = koc * e["foc_ss"] * e["rho_solid"] * Zw / 1000.0
    V = {"air": e["area_air"] * e["h_air"], "water": e["area_water"] * e["h_water"],
         "soil": e["area_soil"] * e["h_soil"], "sed": e["area_water"] * e["h_sed"]}
    Zb = {"air": Za + e["vf_aerosol"] * Zq, "water": Zw + e["vf_ss"] * Zss,
          "soil": e["soil_air"] * Za + e["soil_water"] * Zw + e["soil_solid"] * Zs,
          "sed": e["sed_water"] * Zw + e["sed_solid"] * Zsed}
    Aw, As = e["area_water"], e["area_soil"]
    # air - water
    Dvw = 1.0 / (1.0 / (e["k_air_side"] * Aw * Za) + 1.0 / (e["k_water_side"] * Aw * Zw))
    Daw = Dvw + Aw * e["rain"] * Zw + Aw * e["rain"] * e["scavenging"] * e["vf_aerosol"] * Zq + \
        Aw * e["dry_dep"] * e["vf_aerosol"] * Zq
    Dwa = Dvw
    # air - soil
    De = e["soil_bl"] * As * Za
    Dsoil = As * (e["soil_air_diff"] * Za + e["soil_water_diff"] * Zw)
    Dvs = 1.0 / (1.0 / De + 1.0 / Dsoil)
    Das = Dvs + As * e["rain"] * Zw + As * e["rain"] * e["scavenging"] * e["vf_aerosol"] * Zq + \
        As * e["dry_dep"] * e["vf_aerosol"] * Zq
    Dsa = Dvs
    # soil -> water (runoff), water <-> sediment
    Dsw = As * (e["runoff_water"] * Zw + e["runoff_solid"] * Zs)
    Dt = Aw * e["sed_mtc"] * Zw
    Dws = Dt + Aw * e["sed_dep"] * Zss
    Dsedw = Dt + Aw * e["sed_resus"] * Zsed
    Dburial = Aw * e["sed_burial"] * Zsed
    Dr = {c: V[c] * Zb[c] * k_deg[c] for c in V}
    Dadv = {"air": V["air"] * Zb["air"] / e["res_air_h"], "water": V["water"] * Zb["water"] / e["res_water_h"],
            "soil": 0.0, "sed": Dburial}
    comps = ["air", "water", "soil", "sed"]
    T = {("air", "water"): Daw, ("air", "soil"): Das, ("water", "air"): Dwa, ("soil", "air"): Dsa,
         ("soil", "water"): Dsw, ("water", "sed"): Dws, ("sed", "water"): Dsedw}
    K = np.zeros((4, 4))
    for i, ci in enumerate(comps):
        K[i, i] = Dr[ci] + Dadv[ci] + sum(v for (a, _), v in T.items() if a == ci)
        for j, cj in enumerate(comps):
            if (cj, ci) in T:
                K[i, j] -= T[(cj, ci)]
    FF, balance = {}, 0.0
    for i, ci in enumerate(comps):
        E = np.zeros(4)
        E[i] = 1.0 / (mw / 1000.0) / 24.0  # 1 kg/day in mol/h
        f = np.linalg.solve(K, E)
        mass_kg = {cj: float(f[j] * V[cj] * Zb[cj] * mw / 1000.0) for j, cj in enumerate(comps)}
        FF[ci] = mass_kg  # kg in compartment per kg/day emitted = days
        removed = sum(f[j] * (Dr[cj] + Dadv[cj]) for j, cj in enumerate(comps))
        balance = max(balance, abs(removed / E[i] - 1.0))
    persistence = {ci: sum(FF[ci].values()) for ci in comps}
    return {"FF": FF, "persistence_days": persistence, "volumes": V, "mass_balance_error": float(balance),
            "dissolved_fraction_water": float(Zw / Zb["water"]) / (1 + e["doc"] * 0.08 * kow),
            "fraction_aerosol": float(e["vf_aerosol"] * Zq / Zb["air"]) if Zb["air"] else 0.0}


def toxicity_factors(props, env=None, exposure=None):
    """Screening characterisation factors for emissions to air, freshwater and soil.
    Freshwater ecotoxicity (CTUe = PAF m3 day/kg): FF x XF x EF with EF = 0.5/HC50.
    Human toxicity (CTUh = cases/kg): intake fraction (inhalation, drinking water, fish) x EF, EF = 0.5/ED50 lifetime."""
    fate = fate_model(props, env)
    e = dict(EQC, **(env or {}))
    x = dict(EXPOSURE, **(exposure or {}))
    kow = 10 ** _f(props, "log_kow")
    bcf = _f(props, "bcf", 10 ** (0.85 * math.log10(kow) - 0.70) if kow > 0 else 1.0)  # Veith et al. (1979)
    xf = fate["dissolved_fraction_water"]
    hc50 = _f(props, "hc50")
    ef_eco = 0.5 / (hc50 / 1000.0) if hc50 and hc50 > 0 else None  # mg/L -> kg/m3
    pop = e["population_density"] * (e["area_soil"] + e["area_water"]) / 1e6
    out = {"fate": fate, "bcf": bcf, "population": pop, "factors": {}}
    lifetime_intake = x["body_weight"] * x["lifetime_y"] * 365.0  # kg body weight x days
    efs = {}
    for k in ("ed50_cancer", "ed50_noncancer"):
        v = _f(props, k)
        efs[k] = 0.5 / (v * 1e-6 * lifetime_intake) if v and v > 0 else None
    for src, label in (("air", "air"), ("water", "water"), ("soil", "soil")):
        ff = fate["FF"][src]
        c_air = ff["air"] / fate["volumes"]["air"]  # kg/m3 per kg/day
        c_w = ff["water"] / fate["volumes"]["water"] * xf
        intake = pop * (x["inhalation_m3_d"] * c_air + x["drinking_water_m3_d"] * c_w + x["fish_kg_d"] * bcf * c_w / 1000.0)
        f = {"freshwater ecotoxicity": ff["water"] * xf * ef_eco if ef_eco else None,
             "intake_fraction": intake}
        f["human toxicity, cancer"] = intake * efs["ed50_cancer"] if efs["ed50_cancer"] else None
        f["human toxicity, non-cancer"] = intake * efs["ed50_noncancer"] if efs["ed50_noncancer"] else None
        out["factors"][label] = f
    return out


SCREEN_FAMILY = "Cyclia screening toxicity (own chemicals)"
SCREEN_CATS = {"freshwater ecotoxicity": "CTUe", "human toxicity, cancer": "CTUh", "human toxicity, non-cancer": "CTUh"}
NS_CHEM = uuid.UUID("2b9e8a1c-6d1f-4f0a-9e77-0c3a1f5d2e44")


def install_chemical(store, name, cas, props):
    """Compute screening factors, store them as a method family and make sure the chemical exists as elementary
    flows (air, water, soil) so it can be used as a direct emission."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Give the chemical a name.")
    res = toxicity_factors(props)
    from importers import lcia
    with store.lock:
        flows = {}
        for comp, sub in (("air", "unspecified"), ("water", "surface water"), ("soil", "unspecified")):
            hit = store.one("SELECT uuid FROM flows WHERE lower(name)=lower(?) AND lower(compartment)=?", (name, comp))
            if not hit:
                u = str(uuid.uuid5(NS_CHEM, f"{name.lower()}|{comp}"))
                store.add_flow(u, name, comp, sub, "kg", cas or "")
            flows[comp] = True
        store.conn.commit()
    store.save_chemical(name, cas, props, {k: v for k, v in res.items() if k != "fate"} |
                        {"persistence_days": res["fate"]["persistence_days"]})
    mids = []
    for cat, unit in SCREEN_CATS.items():
        mid = store.get_or_create_method(SCREEN_FAMILY, cat, cat, unit, "Cyclia screening model",
                                         "Screening factors from a Level III fate model (Mackay et al. 1996) with "
                                         "USEtox-style exposure and effect factors. Not official USEtox factors.")
        store.x("DELETE FROM cf_raw WHERE method_id=? AND c_name=?", (mid, canon(name, "air", "")[0]))
        rows = []
        for comp in ("air", "water", "soil"):
            v = res["factors"][comp][cat]
            if v is not None:
                rows.append((name, comp, "", "", None, v))
        if rows:
            lcia.store_raw(store, mid, rows)
        mids.append(mid)
    store.x("DELETE FROM cfs WHERE method_id IN (%s)" % ",".join("?" * len(mids)), mids)
    lcia.rematch(store, mids)
    return res


# ============================================================================ external model emissions
EXT_TEMPLATE = ("year,flow,compartment,subcompartment,amount,unit\n"
                "1,\"Copper, ion\",water,surface water,0.0021,kg\n"
                "2,\"Copper, ion\",water,surface water,0.0019,kg\n"
                "1,\"Copper, ion\",soil,unspecified,0.0008,kg\n")


def read_external(path_or_text):
    text = path_or_text
    if "\n" not in str(path_or_text):
        with open(path_or_text, newline="", encoding="utf-8-sig") as fh:
            text = fh.read()
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(io.StringIO(text), dialect=dialect)]
    if not rows or not {"flow", "compartment", "amount"} <= set(rows[0]):
        raise ValueError("The file needs the columns: " + EXT_TEMPLATE.splitlines()[0])
    return rows


def import_external(store, model_id, rows, scale=1.0, aggregate=False, stage="", source="external model",
                    create_missing=False):
    """Add emissions computed by another model (e.g. leaching, runoff, field emissions) as direct flows.
    One line per flow and year (the year feeds the dynamic climate analysis), or one line per flow when aggregated."""
    import units
    problems, prepared = [], []
    for n, r in enumerate(rows, 2):
        try:
            amt = float(str(r["amount"]).replace(",", ".")) * float(scale)
        except ValueError:
            problems.append(f"Row {n}: amount '{r['amount']}' is not a number.")
            continue
        if amt == 0:
            continue
        cn = canon(r["flow"], r["compartment"], r.get("subcompartment", ""))
        f = store.one("SELECT id, uuid, unit FROM flows WHERE c_name=? AND c_comp=? AND c_sub=?", cn) or \
            store.one("SELECT id, uuid, unit FROM flows WHERE c_name=? AND c_comp=? ORDER BY c_sub='unspecified' DESC", cn[:2])
        if not f and create_missing:
            with store.lock:
                fid = store.add_flow(str(uuid.uuid5(NS_CHEM, "|".join(cn))), r["flow"], r["compartment"],
                                     r.get("subcompartment", "") or "unspecified", r.get("unit") or "kg")
                store.conn.commit()
            f = store.one("SELECT id, uuid, unit FROM flows WHERE id=?", (fid,))
        if not f:
            problems.append(f"Row {n}: no elementary flow '{r['flow']}' in {r['compartment']} in the library "
                            "(tick 'create missing flows' to add it).")
            continue
        unit = r.get("unit") or f["unit"]
        fac = units.factor(unit, f["unit"])
        if fac is None:
            problems.append(f"Row {n}: unit '{unit}' cannot be converted to '{f['unit']}'.")
            continue
        yr = float(r.get("year") or 0) if str(r.get("year") or "").strip() else 0.0
        prepared.append((f, amt * fac, amt, unit, yr, r))
    if problems:
        return {"added": 0, "problems": problems[:50]}
    groups = {}
    for f, conv, amt, unit, yr, r in prepared:
        key = (f["id"], None if aggregate else yr)
        g = groups.setdefault(key, {"flow": f, "conv": 0.0, "years": [], "name": r["flow"], "unit": f["unit"]})
        g["conv"] += conv
        g["years"].append(yr)
    added = 0
    for (fid, yr), g in groups.items():
        avoided = g["conv"] < 0
        label = g["name"] + (f" (year {yr:g})" if yr is not None and not aggregate else "")
        store.add_input(model_id, "flow", fid, abs(g["conv"]), label=label,
                        comment=f"{source}" + (f", years {min(g['years']):g}-{max(g['years']):g}" if aggregate else ""),
                        stage=stage, input_amount=abs(g["conv"]), input_unit=g["unit"], avoided=avoided,
                        pedigree=[2, 3, 2, 2, 3], year=(yr or 0.0) if not aggregate else 0.0)
        added += 1
    return {"added": added, "problems": []}


# ============================================================================ location coordinates (map)
# Approximate centroids (lat, lon) of countries and ecoinvent regions; for the schematic map only.
COORDS = {
    "GLO": (5, -30), "ROW": (-5, 160), "RER": (50, 15), "EUROPE WITHOUT SWITZERLAND": (50, 12), "RNA": (45, -100),
    "RLA": (-15, -60), "RAS": (30, 95), "RAF": (5, 20), "RME": (28, 45), "OCE": (-25, 140), "UN-OCEANIA": (-25, 140),
    "WEU": (48, 2), "WECC": (40, -115), "NPCC": (45, -72), "RFC": (40, -83), "SERC": (34, -86), "MRO": (44, -96),
    "TRE": (31, -99), "ENTSO-E": (48, 10), "UCTE": (48, 10), "NORDEL": (62, 15), "CENTREL": (50, 18),
    "AT": (47.5, 14.5), "BE": (50.6, 4.6), "BG": (42.7, 25.3), "CH": (46.8, 8.2), "CY": (35, 33), "CZ": (49.8, 15.5),
    "DE": (51.2, 10.4), "DK": (56, 10), "EE": (58.7, 25.5), "ES": (40.2, -3.6), "FI": (64, 26), "FR": (46.5, 2.5),
    "GB": (54, -2.5), "UK": (54, -2.5), "GR": (39, 22), "HR": (45.1, 15.5), "HU": (47.2, 19.4), "IE": (53.2, -8),
    "IS": (64.9, -18.6), "IT": (42.8, 12.5), "LT": (55.2, 23.9), "LU": (49.8, 6.1), "LV": (56.9, 24.6),
    "MT": (35.9, 14.4), "NL": (52.2, 5.5), "NO": (61, 9), "PL": (52, 19.4), "PT": (39.6, -8), "RO": (45.9, 24.9),
    "SE": (62, 15), "SI": (46.1, 14.8), "SK": (48.7, 19.7), "RS": (44, 20.9), "BA": (44.2, 17.8), "MK": (41.6, 21.7),
    "AL": (41.1, 20), "ME": (42.7, 19.3), "UA": (49, 31.4), "BY": (53.7, 28), "MD": (47.2, 28.5), "RU": (60, 90),
    "TR": (39, 35.2), "GE": (42.3, 43.4), "AM": (40.1, 45), "AZ": (40.3, 47.6), "KZ": (48, 67), "UZ": (41.4, 64.6),
    "US": (39.8, -98.6), "CA": (57, -101), "MX": (23.6, -102.5), "BR": (-10.8, -52.9), "AR": (-35.4, -65.2),
    "CL": (-35.7, -71.5), "CO": (4.6, -74.1), "PE": (-9.2, -75), "VE": (7, -66), "EC": (-1.8, -78.2),
    "BO": (-16.3, -63.6), "PY": (-23.4, -58.4), "UY": (-32.5, -55.8), "CU": (21.5, -79.5), "CR": (9.7, -84),
    "CN": (35.9, 104.2), "IN": (21, 78.9), "JP": (36.2, 138.3), "KR": (36.5, 127.9), "TW": (23.7, 121),
    "ID": (-2.5, 118), "MY": (4.2, 102), "TH": (15.9, 101), "VN": (16, 107.8), "PH": (12.9, 121.8),
    "PK": (30.4, 69.3), "BD": (23.7, 90.4), "LK": (7.9, 80.8), "NP": (28.4, 84.1), "MM": (21.9, 95.9),
    "SG": (1.35, 103.8), "HK": (22.3, 114.2), "IR": (32.4, 53.7), "IQ": (33.2, 43.7), "SA": (23.9, 45.1),
    "AE": (23.4, 53.8), "IL": (31, 34.9), "JO": (30.6, 36.2), "KW": (29.3, 47.5), "QA": (25.4, 51.2),
    "OM": (21.5, 55.9), "EG": (26.8, 30.8), "MA": (31.8, -7.1), "DZ": (28, 1.7), "TN": (33.9, 9.5),
    "LY": (26.3, 17.2), "NG": (9.1, 8.7), "ZA": (-30.6, 22.9), "KE": (-0.02, 37.9), "ET": (9.1, 40.5),
    "GH": (7.9, -1), "CI": (7.5, -5.5), "SN": (14.5, -14.5), "TZ": (-6.4, 34.9), "CM": (7.4, 12.4),
    "CD": (-4, 21.8), "AO": (-11.2, 17.9), "MZ": (-18.7, 35.5), "ZM": (-13.1, 27.8), "ZW": (-19, 29.2),
    "AU": (-25.3, 133.8), "NZ": (-40.9, 174.9), "CN-SGCC": (35, 110), "CN-CSG": (23, 110), "IN-WR": (21, 73),
    "BR-SOUTH-EASTERN GRID": (-21, -46), "US-WECC": (40, -115), "CA-QC": (52, -72), "CA-ON": (50, -85),
}
CONTINENTS = {  # schematic outlines (lon, lat) for the map background
    "North America": [(-168, 66), (-140, 70), (-95, 75), (-62, 60), (-55, 47), (-80, 25), (-97, 18), (-87, 13),
                      (-105, 21), (-117, 32), (-125, 42), (-125, 50), (-150, 59), (-168, 66)],
    "South America": [(-80, 9), (-60, 11), (-35, -6), (-40, -22), (-58, -38), (-68, -55), (-75, -50), (-71, -20),
                      (-81, -5), (-80, 9)],
    "Europe": [(-10, 36), (-9, 43), (-2, 49), (5, 53), (8, 58), (5, 62), (15, 69), (30, 71), (40, 67), (45, 55),
               (40, 45), (28, 41), (24, 36), (15, 38), (9, 44), (3, 42), (-5, 36), (-10, 36)],
    "Africa": [(-17, 15), (-10, 31), (0, 36), (11, 37), (32, 31), (43, 12), (51, 11), (40, -5), (40, -15),
               (33, -26), (20, -35), (12, -18), (9, 4), (-8, 5), (-17, 15)],
    "Asia": [(27, 41), (36, 37), (35, 30), (43, 13), (60, 22), (68, 24), (72, 20), (77, 8), (88, 22), (94, 16),
             (99, 8), (104, 1), (109, 12), (108, 21), (122, 30), (122, 40), (130, 43), (141, 52), (162, 59),
             (180, 66), (180, 71), (140, 73), (110, 77), (70, 73), (55, 68), (45, 55), (40, 45), (27, 41)],
    "Australia": [(114, -22), (129, -15), (136, -12), (142, -11), (146, -19), (153, -26), (150, -37),
                  (141, -38), (131, -31), (115, -34), (114, -22)],
}


def coordinates(code):
    c = str(code or "").upper().strip()
    if c in COORDS:
        return COORDS[c]
    head = re.split(r"[-_ ]", c)[0]
    return COORDS.get(head)
