"""Trust: an automated validation suite with analytic reference solutions, and reproducibility bundles.

The validation suite builds small product systems whose results are known in closed form (chains, loops,
production amounts other than 1, allocation, system expansion, nesting, formulas, unit conversion, regional and
site-specific factors, background scenarios, module D, dynamic GWP, Monte Carlo moments, Sobol indices of an
additive model, fate-model mass balance) and compares Cyclia's numbers with them. It runs in a temporary library,
so the user's data are never touched. The report can be attached to a paper or a software review.
"""
import hashlib
import re
import json
import math
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
import zipfile

import numpy as np

import calc
import units

NS = uuid.UUID("0c4f1a8e-2b7d-4c55-9b21-77e5d0a3f918")


# ============================================================================ validation suite
def _toy(st):
    """Insert the validation database. Returns dict of dataset ids, flow ids and method ids."""
    from importers import lcia
    db = st.create_database("Validation (analytic)", "validation", "1", "")
    flows = {}
    with st.lock:
        for k, (n, comp, unit) in {"co2": ("Carbon dioxide, fossil", "air", "kg"),
                                   "ch4": ("Methane, fossil", "air", "kg"),
                                   "w": ("Water, river", "natural resource", "m3")}.items():
            flows[k] = st.add_flow(str(uuid.uuid5(NS, k)), n, comp, "unspecified" if comp == "air" else "in water", unit)
        acts = {}
        spec = {  # key: (name, product, unit, production, location)
            "E": ("electricity production (validation)", "electricity", "kWh", 1.0, "GLO"),
            "E2": ("electricity production, alternative (validation)", "electricity", "kWh", 1.0, "GLO"),
            "M": ("market for electricity (validation)", "electricity", "kWh", 1.0, "GLO"),
            "S": ("steel production (validation)", "steel", "kg", 1.0, "GLO"),
            "P": ("product with production amount 2 (validation)", "product", "kg", 2.0, "GLO"),
            "L1": ("loop process 1 (validation)", "loop product 1", "kg", 1.0, "GLO"),
            "L2": ("loop process 2 (validation)", "loop product 2", "kg", 1.0, "GLO"),
            "WFR": ("water use (validation)", "water use FR", "m3", 1.0, "FR"),
            "WDE": ("water use (validation)", "water use DE", "m3", 1.0, "DE"),
            "T": ("treatment of waste (validation)", "waste", "kg", -1.0, "GLO"),  # ecoSpold2: treatment produces -1 kg
        }
        for k, (n, prod, u, p, loc) in spec.items():
            acts[k] = st.conn.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) "
                                      "VALUES(?,?,?,?,?,?,?)", (db, k, n, prod, loc, u, p)).lastrowid
        tech = [("M", "E", 1.0), ("S", "E", 2.0), ("P", "S", 1.0), ("L1", "L2", 0.2), ("L2", "L1", 0.5), ("T", "E", 0.1)]
        for o, i, a in tech:
            st.conn.execute("INSERT INTO tech(output_id,input_id,amount) VALUES(?,?,?)", (acts[o], acts[i], a))
        bio = [("E", "co2", 0.5), ("E2", "co2", 0.1), ("S", "co2", 1.0), ("P", "ch4", 0.01), ("L1", "co2", 1.0),
               ("L2", "co2", 2.0), ("WFR", "w", 1.0), ("WDE", "w", 1.0), ("T", "co2", 0.3)]
        for a, f, v in bio:
            st.conn.execute("INSERT INTO bio(activity_id,flow_id,amount) VALUES(?,?,?)", (acts[a], flows[f], v))
        st.conn.commit()
    st.finish_database(db)
    gwp = st.get_or_create_method("VAL", "climate", "GWP", "kg CO2-eq", "validation")
    lcia.store_raw(st, gwp, [("Carbon dioxide, fossil", "air", "", "", None, 1.0),
                             ("Methane, fossil", "air", "", "", None, 30.0)])
    water = st.get_or_create_method("VAL", "water", "scarcity", "m3 eq", "validation")
    lcia.store_raw(st, water, [("Water, river", "natural resource", "", "", None, 1.0),
                               ("Water, river", "natural resource", "", "FR", None, 3.0)])
    lcia.rematch(st, [gwp, water])
    return {"acts": acts, "flows": flows, "gwp": gwp, "water": water}


def _model(st, name, lines, scope=None, amount=1.0, unit="kg"):
    mid = st.save_model({"name": name, "product": name, "unit": unit, "amount": amount, "scope": scope or {}})
    for ln in lines:
        kind, ref, amt = ln[0], ln[1], ln[2]
        opt = ln[3] if len(ln) > 3 else {}
        st.add_input(mid, kind, ref, amt, input_amount=opt.get("input_amount", amt), input_unit=opt.get("unit"),
                     avoided=opt.get("avoided", False), stage=opt.get("stage", ""), formula=opt.get("formula"),
                     pedigree=opt.get("pedigree"))
    return mid


def validation_suite(progress=lambda *a: None):
    tmp = tempfile.mkdtemp(prefix="cyclia-validation-")
    from store import Workspace
    ws = Workspace(tmp)
    cases = []

    def case(cid, area, desc, expected, got, tol=1e-9, kind="rel"):
        if kind == "abs":
            err = abs(got - expected)
        else:
            err = abs(got - expected) / abs(expected) if expected else abs(got)
        cases.append({"id": cid, "area": area, "description": desc, "expected": float(expected), "cyclia": float(got),
                      "error": float(err), "tolerance": tol, "error_kind": "absolute" if kind == "abs" else "relative",
                      "passed": bool(err <= tol)})

    try:
        calc.invalidate()
        st = ws.create("validation")
        t = _toy(st)
        A, F, G, W = t["acts"], t["flows"], t["gwp"], t["water"]
        tot = lambda mid, mids=(G,), **k: calc.run(st, mid, list(mids), **k)["results"]

        progress(5, "Supply chains")
        case("V01", "Matrix solution", "Linear chain: steel uses 2 kWh electricity (0.5 kg CO2/kWh) plus 1 kg CO2 = 2.0",
             2.0, tot(_model(st, "chain", [("activity", A["S"], 1.0)]))[0]["total"])
        case("V02", "Matrix solution", "Production amount 2: (1 kg steel x 2.0 + 0.01 kg CH4 x 30) / 2 = 1.15",
             1.15, tot(_model(st, "production", [("activity", A["P"], 1.0)]))[0]["total"])
        case("V03", "Matrix solution", "Loop: x1 = 1 + 0.5 x2, x2 = 0.2 x1; GWP = x1 + 2 x2 = 1.4/0.9",
             1.4 / 0.9, tot(_model(st, "loop", [("activity", A["L1"], 1.0)]))[0]["total"])
        m4 = _model(st, "two lines", [("activity", A["S"], 10.0), ("activity", A["E"], 5.0)])
        case("V04", "Foreground model", "10 kg steel + 5 kWh = 20 + 2.5", 22.5, tot(m4)[0]["total"])
        case("V35", "Waste treatment", "2 kg of waste sent to a treatment dataset (reference amount -1 kg; 0.3 kg CO2 and "
             "0.1 kWh per kg treated) = 2 x (0.3 + 0.05) = 0.7, not a credit",
             0.7, tot(_model(st, "waste", [("activity", A["T"], 2.0)]))[0]["total"])
        progress(20, "Units, credits, allocation")
        m5 = _model(st, "units", [("activity", A["S"], units.factor("g", "kg") * 500, {"input_amount": 500, "unit": "g"}),
                                  ("activity", A["E"], units.factor("MJ", "kWh") * 3.6, {"input_amount": 3.6, "unit": "MJ"})])
        case("V05", "Units", "500 g steel + 3.6 MJ electricity = 1.0 + 0.5", 1.5, tot(m5)[0]["total"])
        m6 = _model(st, "credit", [("activity", A["S"], 10.0), ("activity", A["S"], 2.0, {"avoided": True})])
        case("V06", "System expansion", "10 kg steel minus 2 kg avoided steel = 20 - 4", 16.0, tot(m6)[0]["total"])
        m7 = _model(st, "allocation", [("activity", A["S"], 10.0), ("activity", A["E"], 5.0)], scope={"alloc_share": 40})
        case("V07", "Allocation", "Manual allocation 40 % of 22.5", 9.0, tot(m7)[0]["total"])
        m7b = _model(st, "allocation by price", [("activity", A["S"], 10.0)],
                     scope={"alloc_basis": "price", "main_price": 3, "coproducts": [{"name": "b", "price": 1}]})
        case("V08", "Allocation", "Economic allocation 3/(3+1) of 20", 15.0, tot(m7b)[0]["total"])
        sub = _model(st, "sub-assembly", [("activity", A["S"], 2.0)], amount=2.0)
        m8 = _model(st, "nested", [("model", sub, 3.0)])
        case("V09", "Nesting", "3 kg of a sub-model defined per 2 kg (4 kg CO2-eq) = 6", 6.0, tot(m8)[0]["total"])
        st.save_parameter({"model_id": None, "name": "t", "value": 0.3})
        m9 = _model(st, "formula", [("activity", A["S"], 3.0, {"formula": "t*10"})])
        case("V10", "Parameters", "Amount from formula t*10 with t = 0.3 gives 3 kg steel = 6", 6.0, tot(m9)[0]["total"])
        r = tot(m9, scenario=None)
        st.save_scenario({"name": "t high", "overrides": {"t": 0.5}})
        sid = st.scenarios()[0]["id"]
        case("V11", "Parameters", "Scenario t = 0.5 gives 5 kg steel = 10", 10.0, tot(m9, scenario=sid)[0]["total"])
        progress(40, "Module D, flows, regional and site factors")
        m10 = _model(st, "module D", [("activity", A["S"], 10.0, {"stage": "A1"}),
                                     ("activity", A["S"], 2.0, {"avoided": True, "stage": "D"})],
                     scope={"stage_system": "EN 15804 (construction products)"})
        r10 = tot(m10)[0]
        case("V12", "EN 15804", "Total A-C excludes module D: 20", 20.0, r10["total"])
        case("V13", "EN 15804", "Module D reported separately: -4", -4.0, r10["module_d"])
        m11 = _model(st, "direct", [("flow", F["ch4"], 0.1)])
        case("V14", "Direct flows", "0.1 kg methane x 30 = 3", 3.0, tot(m11)[0]["total"])
        case("V15", "Regional factors", "1 m3 water in FR with regional factor 3", 3.0,
             tot(_model(st, "water FR", [("activity", A["WFR"], 1.0)]), (W,))[0]["total"])
        case("V16", "Regional factors", "1 m3 water in DE uses the generic factor 1", 1.0,
             tot(_model(st, "water DE", [("activity", A["WDE"], 1.0)]), (W,))[0]["total"])
        st.save_site_cf({"family": "VAL", "category": "climate", "indicator": "GWP",
                         "flow_uuid": str(uuid.uuid5(NS, "ch4")), "value": 10.0})
        case("V17", "Site-specific factors", "Foreground methane with site factor 10: 0.1 x 10", 1.0, tot(m11)[0]["total"])
        mixed = _model(st, "site factor only foreground", [("activity", A["P"], 2.0), ("flow", F["ch4"], 0.1)])
        case("V18", "Site-specific factors", "Background methane keeps the generic factor: 2 x 1.15 + 1.0", 3.3,
             tot(mixed)[0]["total"])
        for x in st.site_cfs():
            st.delete_site_cf(x["id"])
        progress(55, "Background scenarios")
        bid = st.save_bg_scenario({"name": "halve electricity CO2", "kind": "prospective", "base_year": 2020,
                                   "rules": [{"type": "scale_emission", "activity": "electricity production (validation)",
                                              "flow": "carbon dioxide, fossil", "factor": {"2050": 0.5}}]})
        mS = _model(st, "steel for scenarios", [("activity", A["S"], 1.0)])
        case("V19", "Prospective", "Electricity CO2 x 0.5 in 2050: 1 + 2 x 0.25", 1.5,
             tot(mS, bg={"id": bid, "year": 2050})[0]["total"])
        case("V20", "Prospective", "Linear interpolation, 2035 (factor 0.75): 1 + 2 x 0.375", 1.75,
             tot(mS, bg={"id": bid, "year": 2035})[0]["total"])
        cid = st.save_bg_scenario({"name": "marginal electricity", "kind": "consequential",
                                   "rules": [{"type": "swap", "activity_ids": [A["M"]], "product": "electricity",
                                              "to": [{"id": A["E2"], "share": 1.0}]}]})
        mM = _model(st, "market", [("activity", A["M"], 1.0)])
        case("V21", "Consequential", "Market supplied by its marginal supplier (0.1 instead of 0.5)", 0.1,
             tot(mM, bg={"id": cid})[0]["total"])
        case("V22", "Consequential", "Without the scenario the market keeps its average supplier", 0.5, tot(mM)[0]["total"])
        sid2 = st.save_bg_scenario({"name": "scenario file", "kind": "prospective", "rules": [{
            "type": "set_exchanges", "source": "test", "tech": [["Validation (analytic)", "S", "Validation (analytic)", "E", 1.0]],
            "bio": [["Validation (analytic)", "S", str(uuid.uuid5(NS, "ch4")), 0.01]]}]})
        case("V34", "Scenario files", "Exchanges set from a scenario file: steel uses 1 kWh and emits 0.01 kg CH4: "
             "1 + 0.5 + 0.3", 1.8, tot(mS, bg={"id": sid2})[0]["total"])
        progress(65, "Dynamic GWP")
        case("V23", "Dynamic GWP", "CO2 emitted in year 0 weighs 1", 1.0, calc.dynamic_weight("CO2", 0, 100))
        case("V24", "Dynamic GWP", "CO2 emitted at the horizon weighs 0", 0.0, calc.dynamic_weight("CO2", 100, 100), kind="abs")
        case("V25", "Dynamic GWP", "Fossil methane in year 0 equals its GWP100 (29.8)", 29.8, calc.dynamic_weight("CH4f", 0, 100))
        progress(70, "Monte Carlo")
        ped = [5, 5, 5, 5, 5]
        var = calc.basic_variance("activity", "steel") + sum(calc.PEDIGREE_VAR[c][4] for c in range(5))
        mmc = _model(st, "monte carlo", [("activity", A["S"], 10.0, {"pedigree": ped})])
        u = calc.run(st, mmc, [G], mc_iterations=20000, seed=11)["uncertainty"]["methods"][0]
        case("V26", "Monte Carlo", f"Lognormal mean 20 x exp(s2/2), s2 = {var:.4f}", 20 * math.exp(var / 2), u["mean"], tol=0.02)
        case("V27", "Monte Carlo", "Lognormal median equals the deterministic result 20", 20.0, u["median"], tol=0.02)
        progress(80, "Sobol indices")
        msob = _model(st, "sobol", [("activity", A["S"], 10.0, {"pedigree": [5, 5, 5, 5, 5]}),
                                    ("activity", A["E"], 10.0, {"pedigree": [2, 2, 2, 2, 2]})])
        sb = calc.sobol(st, msob, [G], n=4096, seed=5)
        s_a = math.sqrt(var)
        var_b = calc.basic_variance("activity", "electricity") + sum(calc.PEDIGREE_VAR[c][1] for c in range(5))
        vfun = lambda a, s2: a * a * (math.exp(s2) - 1) * math.exp(s2)
        va, vb = vfun(20.0, var), vfun(5.0, var_b)
        case("V28", "Sobol", "Additive model: first-order index of the steel line = Var_a/(Var_a+Var_b)",
             va / (va + vb), sb["S1"][0][0], tol=0.05, kind="abs")
        case("V29", "Sobol", "Additive model: total index equals first-order index", sb["S1"][0][0], sb["ST"][0][0],
             tol=0.05, kind="abs")
        progress(90, "Fate model")
        import science
        chem = {"mw": 200, "log_kow": 3, "henry": 1.0, "hl_air": 2, "hl_water": 20, "hl_soil": 60, "hc50": 1.0}
        fm_ = science.fate_model(chem)
        case("V30", "Fate model", "Steady-state mass balance: removal equals emission", 0.0, fm_["mass_balance_error"],
             tol=1e-9, kind="abs")
        k_air = math.log(2) / 2.0 + 24.0 / 100.0  # degradation + advection (1/day) when nothing leaves air
        inert = science.fate_model({"mw": 100, "log_kow": -5, "henry": 1e9, "hl_air": 2, "hl_water": 1e6,
                                    "hl_soil": 1e6})
        case("V31", "Fate model", "Volatile chemical: residence time in air = 1/(k_deg + k_adv)", 1.0 / k_air,
             inert["FF"]["air"]["air"], tol=0.01)
        case("V32", "Units", "1 kWh = 3.6 MJ", 3.6, units.factor("kWh", "MJ"))
        case("V33", "Units", "1 t*km = 1000 kg*km", 1000.0, units.factor("t*km", "kg*km"))
        progress(100, "Done")
    finally:
        ws.close_all()
        calc.invalidate()
        shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(c["passed"] for c in cases)
    return {"cases": cases, "passed": passed, "total": len(cases), "environment": environment(),
            "verdict": "All validation cases passed." if passed == len(cases) else
            f"{len(cases) - passed} case(s) failed. Do not publish until this is understood."}


APP_VERSION = ""  # set by the server at start


def environment():
    import scipy
    return {"cyclia": APP_VERSION, "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(), "date": time.strftime("%Y-%m-%d %H:%M:%S")}


def validation_report(path, res):
    from docx import Document
    from docx.shared import Pt
    import report
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading("Cyclia validation report", 0)
    env = res["environment"]
    report._note(doc, f"Cyclia {env['cyclia']}, Python {env['python']}, NumPy {env['numpy']}, SciPy {env['scipy']}, "
                      f"{env['platform']}. Run on {env['date']}.")
    doc.add_paragraph(f"{res['passed']} of {res['total']} cases passed. {res['verdict']}")
    report._note(doc, "Each case is a small product system whose result is known in closed form. Relative errors are "
                      "|Cyclia - expected| / |expected|; Monte Carlo and Sobol cases use statistical tolerances.", italic=True)
    report._table(doc, ["Case", "Area", "Test", "Expected", "Cyclia", "Error", "Result"],
                  [[c["id"], c["area"], c["description"], f"{c['expected']:.6g}", f"{c['cyclia']:.6g}",
                    f"{c['error']:.1e} ({c['error_kind'][:3]}.)", "pass" if c["passed"] else "FAIL"] for c in res["cases"]],
                  size=7.5)
    report._footer(doc, APP_VERSION)
    doc.save(path)
    return path


# ============================================================================ reproducibility bundles
def db_fingerprint(store, db_name):
    d = store.one("SELECT id, name, version, system_model, n_activities FROM databases WHERE name=?", (db_name,))
    if not d:
        return None
    h = hashlib.sha256()
    with store.lock:
        cur = store.conn.execute("SELECT a.key, i.key, t.amount FROM tech t JOIN activities a ON a.id=t.output_id "
                                 "JOIN activities i ON i.id=t.input_id WHERE a.db_id=? ORDER BY a.key, i.key, t.amount",
                                 (d["id"],))
        for row in cur:
            h.update(f"{row[0]}|{row[1]}|{row[2]:.12g}\n".encode())
        cur = store.conn.execute("SELECT a.key, f.uuid, b.amount FROM bio b JOIN activities a ON a.id=b.activity_id "
                                 "JOIN flows f ON f.id=b.flow_id WHERE a.db_id=? ORDER BY a.key, f.uuid, b.amount", (d["id"],))
        for row in cur:
            h.update(f"{row[0]}|{row[1]}|{row[2]:.12g}\n".encode())
    return {"name": d["name"], "version": d["version"], "system_model": d["system_model"],
            "datasets": d["n_activities"], "sha256": h.hexdigest()}


def method_fingerprint(store, method_id):
    m = store.one("SELECT family, category, indicator, unit FROM methods WHERE id=?", (method_id,))
    h = hashlib.sha256()
    for r in store.q("SELECT f.uuid, c.value FROM cfs c JOIN flows f ON f.id=c.flow_id WHERE c.method_id=? "
                     "ORDER BY f.uuid", (method_id,)):
        h.update(f"{r['uuid']}|{r['value']:.12g}\n".encode())
    for r in store.q("SELECT f.uuid, c.location, c.value FROM cfs_regional c JOIN flows f ON f.id=c.flow_id "
                     "WHERE c.method_id=? ORDER BY f.uuid, c.location", (method_id,)):
        h.update(f"{r['uuid']}|{r['location']}|{r['value']:.12g}\n".encode())
    return dict(m, sha256=h.hexdigest())


def export_bundle(ws, project, settings, path, progress=lambda *a: None):
    """settings: model_ids, method_ids, scenario, bg, nw_set, mc_iterations, seed."""
    st = ws.open(project)
    model_ids = [int(x) for x in settings["model_ids"]]
    mids = [int(x) for x in settings["method_ids"]]
    results = {}
    dbs = set()
    for n, mid in enumerate(model_ids):
        progress(5 + 40 * n / max(1, len(model_ids)), "Calculating")
        r = calc.run(st, mid, mids, scenario=settings.get("scenario"), bg=settings.get("bg"),
                     nw_set=settings.get("nw_set"), mc_iterations=int(settings.get("mc_iterations") or 0),
                     seed=int(settings.get("seed") or 42))
        results[str(mid)] = {"name": r["model"]["name"], "totals": [x["total"] for x in r["results"]],
                             "module_d": [x["module_d"] for x in r["results"]],
                             "uncertainty": [{k: m[k] for k in ("mean", "p2_5", "p97_5")} for m in r["uncertainty"]["methods"]]
                             if r.get("uncertainty") else None}
        dbs |= {l["db"] for l in r["lines"] if l["kind"] == "activity"}
        dbs |= _sub_dbs(st, mid)
    progress(50, "Fingerprinting databases")
    fps = [db_fingerprint(st, d) for d in sorted(x for x in dbs if x)]
    progress(85, "Writing the bundle")
    tmpdir = tempfile.mkdtemp()
    try:
        proj = os.path.join(tmpdir, "project.lca")
        ws.export(project, proj)
        manifest = {"format": "cyclia-reproducibility-bundle/1", "project": project, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "environment": environment(), "settings": dict(settings, model_ids=model_ids, method_ids=mids),
                    "methods": [method_fingerprint(st, m) for m in mids], "databases": [f for f in fps if f],
                    "results": results}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(proj, "project.lca")
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("README.txt", "Cyclia reproducibility bundle.\n\nOpen Cyclia > Toolbox > Validation > 'Verify a bundle' "
                                     "and choose this file. Cyclia recalculates every model with the stored settings and "
                                     "compares the results and the database and method fingerprints with this manifest.\n")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return {"path": path, "file": os.path.basename(path), "models": len(model_ids), "databases": [f["name"] for f in fps if f]}


def _sub_dbs(st, mid, seen=None):
    seen = seen or set()
    out = set()
    for r in st.q("SELECT kind, ref_id, ref_db FROM main.model_inputs WHERE model_id=?", (mid,)):
        if r["kind"] == "activity" and r["ref_db"]:
            out.add(r["ref_db"])
        elif r["kind"] == "model" and r["ref_id"] not in seen:
            seen.add(r["ref_id"])
            out |= _sub_dbs(st, r["ref_id"], seen)
    return out


def verify_bundle(ws, path, progress=lambda *a: None):
    from store import ProjectStore
    if not zipfile.is_zipfile(path):
        raise ValueError("This is not a Cyclia bundle (.zip).")
    tmpdir = tempfile.mkdtemp()
    st = None
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "manifest.json" not in names or "project.lca" not in names:
                raise ValueError("The bundle has no manifest.json or project.lca.")
            man = json.loads(z.read("manifest.json"))
            z.extract("project.lca", tmpdir)
        st = ProjectStore(os.path.join(tmpdir, "project.lca"), ws.library_path)
        progress(10, "Checking database fingerprints")
        db_rows = []
        for d in man["databases"]:
            local = db_fingerprint(st, d["name"])
            db_rows.append({"name": d["name"], "version": d.get("version"), "in_library": bool(local),
                            "identical": bool(local and local["sha256"] == d["sha256"])})
        meth_map, meth_rows = [], []
        for m in man["methods"]:
            local = st.method_by_key(m["family"], m["category"], m["indicator"])
            fp = method_fingerprint(st, local["id"]) if local else None
            meth_rows.append({"name": f"{m['family']}: {m['category']}", "in_library": bool(local),
                              "identical": bool(fp and fp["sha256"] == m["sha256"])})
            meth_map.append(local["id"] if local else None)
        res_rows = []
        s = man["settings"]
        if all(meth_map) and all(d["in_library"] for d in db_rows):
            for n, (mid, ref) in enumerate(man["results"].items()):
                progress(30 + 60 * n / max(1, len(man["results"])), f"Recalculating {ref['name']}")
                calc.invalidate()
                r = calc.run(st, int(mid), meth_map, scenario=s.get("scenario"), bg=s.get("bg"), nw_set=s.get("nw_set"),
                             mc_iterations=int(s.get("mc_iterations") or 0), seed=int(s.get("seed") or 42))
                for k, x in enumerate(r["results"]):
                    exp = ref["totals"][k]
                    dev = abs(x["total"] - exp) / abs(exp) if exp else abs(x["total"])
                    res_rows.append({"model": ref["name"], "category": x["category"], "stored": exp, "recalculated": x["total"],
                                     "relative_difference": dev, "identical": dev <= 1e-9})
        ok = all(r["identical"] for r in res_rows) and res_rows and all(d["identical"] for d in db_rows) and \
            all(m["identical"] for m in meth_rows)
        missing = [d["name"] for d in db_rows if not d["in_library"]] + [m["name"] for m in meth_rows if not m["in_library"]]
        verdict = ("Reproduced: identical data, identical methods and identical results." if ok else
                   f"Cannot recalculate: missing in this library: {', '.join(missing)}." if missing else
                   "Recalculated, but some data or results differ; see the tables.")
        return {"verdict": verdict, "reproduced": bool(ok), "created": man["created"], "environment_then": man["environment"],
                "environment_now": environment(), "databases": db_rows, "methods": meth_rows, "results": res_rows}
    finally:
        if st:
            st.close()
        calc.invalidate()
        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================ automatic benchmark against ecoinvent
GROUPS = [  # (group, test on lower-case name and product)
    ("Markets", lambda n, p: n.startswith("market")),
    ("Waste treatment", lambda n, p: n.startswith("treatment of") or "waste" in p),
    ("Electricity and heat", lambda n, p: p.startswith("electricity") or p.startswith("heat")),
    ("Metals", lambda n, p: any(w in p for w in ("steel", "iron", "aluminium", "copper", "zinc", "nickel", "lead",
                                                 "chromium", "titanium", "tin", "gold", "silver", "magnesium"))),
    ("Agriculture and food", lambda n, p: any(w in p for w in ("wheat", "maize", "rice", "soybean", "barley", "potato",
                                                               "milk", "cattle", "pig", "chicken", "sugar", "rape",
                                                               "fertiliser", "fertilizer", "grain", "fruit", "vegetable"))),
    ("Chemicals and plastics", lambda n, p: any(w in p for w in ("poly", "acid", "chemical", "ammonia", "methanol",
                                                                 "ethylene", "propylene", "chlorine", "hydroxide"))),
    ("Construction and minerals", lambda n, p: any(w in p for w in ("cement", "concrete", "clinker", "brick", "gravel",
                                                                    "sand", "lime", "glass", "gypsum", "timber", "wood"))),
    ("Transport", lambda n, p: p.startswith("transport")),
    ("Other", lambda n, p: True),
]
ID_HEADS = {"activity uuid_product uuid": "key", "activity uuid & product uuid": "key", "activity name": "name",
            "geography": "location", "reference product name": "product", "reference product": "product",
            "reference product unit": "unit", "unit": "unit", "activity uuid": "act", "product uuid": "prod"}


def _clean(v):
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def _parse_sheet(ws, top, h):
    ids = {}
    for j, c in enumerate(top[h]):
        k = ID_HEADS.get(c.lower())
        if k and k not in ids:
            ids[k] = j
    first = max(ids.values()) + 1
    data_start = next((i for i in range(h + 1, len(top)) if sum(_isnum(c) for c in top[i][first:]) >= 1
                       and any(top[i][j] for j in ids.values() if j < len(top[i]))), len(top))
    width = max(len(r) for r in top)
    block = []
    for i in range(data_start):
        row = (top[i] + [""] * width)[:width]
        last, out = "", []
        for j in range(width):
            if row[j]:
                last = row[j]
            out.append(row[j] or (last if j >= first else ""))
        block.append(out)
    cols = []
    for j in range(first, width):
        parts = [block[i][j] for i in range(data_start) if block[i][j]]
        if parts:
            cols.append({"index": j, "labels": parts + [ws.title], "sheet": ws.title, "id": f"{ws.title}|{j}"})
    return ids, data_start, cols


def read_lcia_results(path, progress=lambda *a: None, family=""):
    """Read ecoinvent's cumulative LCIA results workbook: one row per dataset (activity and product UUID, name,
    geography, reference product) and one column per indicator. The header block above the data may hold the
    method, category, indicator and unit in one or several rows, in any order (merged cells are filled from the
    left), and the methods may be spread over several sheets named after them."""
    from openpyxl import load_workbook
    if not path.lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("Choose the Excel file (.xlsx) with ecoinvent's cumulative LCIA results.")
    wb = load_workbook(path, read_only=True, data_only=True)
    sheets = []
    for ws in wb.worksheets:
        top = [[_clean(v) for v in r] for r in ws.iter_rows(max_row=25, values_only=True)]
        h = next((i for i, r in enumerate(top) if any(c.lower() in ("activity name", "activity uuid_product uuid",
                                                                     "activity uuid") for c in r)), None)
        if h is not None:
            sheets.append((ws, top, h))
    if not sheets:
        raise ValueError("No sheet with an 'Activity Name' or 'Activity UUID_Product UUID' column was found. This does "
                         f"not look like ecoinvent's cumulative LCIA results file. Sheets: {', '.join(wb.sheetnames[:10])}.")
    fam = _norm(family)
    named = [x for x in sheets if fam and (_norm(x[0].title) == fam or fam in _norm(x[0].title))]
    if named:
        exact = [x for x in named if _norm(x[0].title) == fam]
        sheets = exact or named
    all_cols, rows = [], {}
    for si, (ws, top, h) in enumerate(sheets):
        ids, data_start, cols = _parse_sheet(ws, top, h)
        all_cols += cols
        for n, r in enumerate(ws.iter_rows(min_row=data_start + 1, values_only=True)):
            if not r or all(v in (None, "") for v in r):
                continue
            get = lambda k: _clean(r[ids[k]]) if k in ids and ids[k] < len(r) else ""
            key = get("key") or (f"{get('act')}_{get('prod')}" if "act" in ids else "")
            rk = key or f"{get('name')}|{get('location')}|{get('product')}"
            row = rows.get(rk)
            if row is None:
                row = rows[rk] = {"key": key, "name": get("name"), "location": get("location"), "product": get("product"),
                                  "values": {}}
            for c in cols:
                v = r[c["index"]] if c["index"] < len(r) else None
                if isinstance(v, (int, float)):
                    row["values"][c["id"]] = float(v)
                elif _isnum(v):
                    row["values"][c["id"]] = float(str(v).replace(",", "."))
            if n % 5000 == 0:
                progress(min(30, 2 + (si * 30 + n // 1000) // max(1, len(sheets))),
                         f"Reading the results file, sheet {si + 1} of {len(sheets)} ({n:,} datasets)")
    if not rows:
        raise ValueError("The results file has no data rows.")
    return all_cols, list(rows.values())


def _isnum(v):
    try:
        float(str(v).replace(",", "."))
        return str(v).strip() != ""
    except (TypeError, ValueError):
        return False


def _norm(s):
    return " ".join(str(s or "").lower().replace("_", " ").split())


def match_columns(store, cols, family=""):
    """Pair each results column with a library method. The method's family and category must appear in the
    column's header text (labels and sheet name); the indicator too, unless the category has only one indicator.
    When several methods fit (e.g. 'climate change' and 'climate change: biogenic', or 'EF v3.1' and 'EF v3.1 no
    LT'), the most specific one wins."""
    fam = _norm(family)
    meths = [m for m in store.methods() if not fam or _norm(m["family"]) == fam]
    n_ind = {}
    for m in meths:
        n_ind[(m["family"], m["category"])] = n_ind.get((m["family"], m["category"]), 0) + 1
    out = []
    for c in cols:
        labels = [_norm(x) for x in c["labels"]]
        text = " | ".join(labels)
        best, score = None, 0
        for m in meths:
            f, cat, ind = _norm(m["family"]), _norm(m["category"]), _norm(m["indicator"])
            if not _part_of(f, labels, text) or not _part_of(cat, labels, text):
                continue
            has_ind = ind == cat or _part_of(ind, labels, text)
            if not has_ind and n_ind[(m["family"], m["category"])] > 1:
                continue
            sc = len(f) * 1000 + len(cat) * 10 + (len(ind) if has_ind else 0) + (5 if f in labels else 0)
            if sc > score:
                best, score = m, sc
        if best:
            out.append(dict(c, method=best))
    return out


def _part_of(term, labels, text):
    """term equals a header label, or appears in the header text between separators, so that 'climate change' is
    not found inside 'climate change: biogenic'."""
    if term in labels:
        return True
    sep = r"[|;/,\[\]()]"
    return bool(re.search(r"(^|" + sep + r"|\s-\s)\s*" + re.escape(term) + r"\s*($|" + sep + r"|\s-\s)", text))


def header_sample(cols, n=4):
    return "; ".join(" / ".join(c["labels"][:5]) for c in cols[:n])


def benchmark_ecoinvent(store, path, family="", sample=100, seed=11, progress=lambda *a: None, db_name=None):
    """Compare Cyclia with ecoinvent's own cumulative LCIA results for a stratified sample of datasets and every
    category of one method family. Datasets are matched by 'Activity UUID_Product UUID', the key Cyclia stores
    for ecoSpold2 imports, otherwise by name, geography and reference product."""
    cols, rows = read_lcia_results(path, progress, family)
    progress(32, "Matching categories")
    mcols = match_columns(store, cols, family)
    if not mcols and family:
        mcols = match_columns(store, cols, "")  # the chosen family is not in the file: use the ones that are
    if family and mcols and len({c["method"]["family"] for c in mcols}) > 1:
        mcols = [c for c in mcols if c["method"]["family"] == max({c["method"]["family"] for c in mcols},
                                                                   key=lambda f: sum(x["method"]["family"] == f for x in mcols))]
    if not mcols:
        fams = sorted({m["family"] for m in store.methods()})
        log_header = header_sample(cols, 6)
        raise ValueError(f"The columns of the results file could not be paired with the methods in the library. "
                         f"{'The method ' + family + ' is in the library. ' if family in fams else ''}"
                         f"The file has {len(cols):,} result columns; the first ones are labelled: {log_header}. "
                         "Please send this message so the reader can be adjusted.")
    progress(36, "Matching datasets")
    by_key, by_name = {}, {}
    if db_name:
        pool = store.q("SELECT a.id, a.key, a.name, a.location, a.product FROM activities a JOIN databases d ON d.id=a.db_id "
                       "WHERE d.name=?", (db_name,))
        if not pool:
            raise ValueError(f"The database '{db_name}' is not in the library.")
    else:
        pool = store.q("SELECT a.id, a.key, a.name, a.location, a.product FROM activities a JOIN databases d ON d.id=a.db_id "
                       "WHERE d.source='ecoSpold2'") or store.q("SELECT id, key, name, location, product FROM activities")
    for a in pool:
        by_key[a["key"]] = a
        by_name[(_norm(a["name"]), _norm(a["location"]), _norm(a["product"]))] = a
    matched = []
    for r in rows:
        a = by_key.get(r["key"]) or by_name.get((_norm(r["name"]), _norm(r["location"]), _norm(r["product"])))
        if a and r["values"]:
            matched.append((r, a))
    if not matched:
        raise ValueError("No dataset in the results file was found in the library. Use the results file of the same "
                         "ecoinvent version and system model as the imported database.")
    rng = np.random.default_rng(seed)
    groups = {}
    for r, a in matched:
        n, p = (a["name"] or "").lower(), (a["product"] or "").lower()
        g = next(gname for gname, test in GROUPS if test(n, p))
        groups.setdefault(g, []).append((r, a))
    if sample and sample < len(matched):
        per = max(1, sample // len(groups))
        chosen = []
        for g, items in groups.items():
            idx = rng.permutation(len(items))[:per]
            chosen += [(g,) + items[i] for i in idx]
        rest = [(g,) + it for g, items in groups.items() for it in items if (g,) + it not in chosen]
        if len(chosen) < sample and rest:
            extra = rng.permutation(len(rest))[:sample - len(chosen)]
            chosen += [rest[i] for i in extra]
    else:
        chosen = [(g,) + it for g, items in groups.items() for it in items]
    mc = calc._cache.get(store)
    # ecoinvent's cumulative LCIA results are not regionalised: compare with global factors only
    M = calc.Methods(store, mc, [c["method"]["id"] for c in mcols], regional=False)
    G = {}  # elementary flows of each compared dataset, for the factor finder
    scale_of = {}
    for c in mcols:  # typical magnitude per category, to recognise values that are numerically zero
        v = [abs(r["values"][c["id"]]) for _, r, _ in chosen if r["values"].get(c["id"])]
        scale_of[c["id"]] = float(np.median(v)) if v else 0.0
    out = []
    for n, (g, r, a) in enumerate(chosen):
        j = mc.act_index.get(a["id"])
        if j is None:
            continue
        f = np.zeros(mc.n)
        f[j] = 1.0 if mc.diag[j] >= 0 else -1.0  # waste treatment: per unit treated, as ecoinvent reports it
        x_s = mc.solve(f)
        h = M.Q @ x_s
        G[a["id"]] = mc.B @ x_s
        for k, c in enumerate(mcols):
            ref = r["values"].get(c["id"])
            if ref is None:
                continue
            val = float(h[k])
            scale = max(abs(ref), abs(val))
            tiny = 1e-12 * scale_of[c["id"]]
            dev = 0.0 if scale == 0 else (val - ref) / abs(ref) * 100 if ref else None
            note = ""
            if scale <= tiny:
                dev, note = 0.0, "both numerically zero"
            elif ref and abs(val + ref) <= 1e-6 * abs(ref) and abs(ref) > 0:
                note = "opposite sign"
            elif ref and val == 0:
                note = "Cyclia gives zero"
            out.append({"group": g, "activity": a["name"], "location": a["location"], "product": a["product"], "act_id": a["id"],
                        "category": c["method"]["category"], "indicator": c["method"]["indicator"],
                        "reference": ref, "cyclia": val, "deviation_percent": dev, "note": note})
        if n % 10 == 0:
            progress(40 + 55 * n / max(1, len(chosen)), f"Calculating dataset {n + 1} of {len(chosen)}")
    progress(97, "Summarising")
    progress(98, "Summarising")
    res = _bench_summary(store, mc, M, mcols, out, len(chosen), len(rows), len(matched), groups)
    res["database"] = db_name
    progress(99, "Looking for the causes of deviations")
    res["diagnosis"] = diagnose(store, mc, M, mcols, out)
    res["factor_finder"] = factor_finder(store, mc, M, mcols, out, G)
    res["land_use"] = land_use_reconciliation(store, mc, M, mcols, out, G)
    res["cf_conflicts"] = cf_conflicts(store, [c["method"]["id"] for c in mcols])
    return res


LAND_GROUPS = (("occupation", lambda n: n.startswith("occupation")),
               ("transformation, from", lambda n: n.startswith("transformation, from")),
               ("transformation, to", lambda n: n.startswith("transformation, to")))


def _land_group(name):
    n = (name or "").strip().lower()
    return next((g for g, t in LAND_GROUPS if t(n)), None)


def cf_conflicts(store, method_ids):
    """Raw characterisation factors that map to the same flow key (name, compartment, subcompartment, location) with
    different values. Matching keeps the first one, so a conflict can make a category deviate."""
    if not method_ids:
        return []
    rows = store.q(f"SELECT r.method_id, m.category, r.c_name, r.c_comp, r.c_sub, r.location, COUNT(DISTINCT r.value) AS n, "
                   f"MIN(r.value) AS lo, MAX(r.value) AS hi FROM cf_raw r JOIN methods m ON m.id=r.method_id "
                   f"WHERE r.method_id IN ({','.join('?' * len(method_ids))}) "
                   f"GROUP BY r.method_id, r.c_name, r.c_comp, r.c_sub, r.location HAVING COUNT(DISTINCT r.value) > 1",
                   list(method_ids))
    return [{"category": r["category"], "flow": r["c_name"], "compartment": "/".join(x for x in (r["c_comp"], r["c_sub"]) if x),
             "location": r["location"] or "global", "values": r["n"], "min": r["lo"], "max": r["hi"]} for r in rows]


def land_use_reconciliation(store, mc, M, mcols, out, G):
    """For land use categories: split Cyclia's result of every compared dataset into occupation, transformation-from
    and transformation-to contributions, estimate by least squares how much each group would have to change to
    explain the gap to ecoinvent (gap_d = sum_g alpha_g c_dg), and list land flows of the inventories that have no
    factor in Cyclia. This separates a factor problem in one flow group from flows that are not characterised."""
    names = {}

    def fname(i):
        if i not in names:
            r = store.flow(int(mc.flow_ids[i]))
            names[i] = (r["name"] if r else "", "/".join(x for x in ((r or {}).get("compartment"), (r or {}).get("subcompartment")) if x))
        return names[i]
    land_idx = None
    res = []
    for k, c in enumerate(mcols):
        m = c["method"]
        if "land" not in f"{m['category']} {m['indicator']}".lower():
            continue
        if land_idx is None:
            land_idx = [i for i in range(len(mc.flow_ids)) if _land_group(fname(i)[0])]
        items = [x for x in out if x["category"] == m["category"] and x["indicator"] == m["indicator"] and x["reference"]
                 and x["act_id"] in G and x["note"] == ""]
        if len(items) < 3:
            continue
        groups = [g for g, _ in LAND_GROUPS]
        X, y, w = [], [], []
        missing = {}
        for x in items:
            g = G[x["act_id"]]
            row = []
            for gname in groups:
                idx = [i for i in land_idx if _land_group(fname(i)[0]) == gname]
                row.append(float(sum(M.C[k, i] * g[i] for i in idx)))
            X.append(row)
            y.append(x["reference"] - x["cyclia"])
            w.append(1.0 / abs(x["reference"]))
            for i in land_idx:
                if g[i] and M.C[k, i] == 0:
                    key = fname(i)
                    missing[key] = missing.get(key, 0.0) + abs(float(g[i])) / abs(x["reference"])
        X, y, w = np.array(X), np.array(y), np.array(w)
        Xw, yw = X * w[:, None], y * w
        use = [j for j in range(len(groups)) if np.any(np.abs(Xw[:, j]) > 0)]
        alpha = [None] * len(groups)
        explained = None
        if use and np.any(yw):
            sol, *_ = np.linalg.lstsq(Xw[:, use], yw, rcond=None)
            for j, a_ in zip(use, sol):
                alpha[j] = float(a_)
            fit = Xw[:, use] @ sol
            explained = float(1 - np.sum((yw - fit) ** 2) / np.sum(yw ** 2)) if np.sum(yw ** 2) else None
        tot = np.abs(X).sum(axis=0)
        share = (tot / tot.sum()).tolist() if tot.sum() else [0.0] * len(groups)
        res.append({"category": m["category"], "indicator": m["indicator"], "n": len(items),
                    "groups": [{"group": g, "share_of_result": share[j],
                                "factor_change_percent": (alpha[j] * 100) if alpha[j] is not None else None}
                               for j, g in enumerate(groups)],
                    "explained": explained,
                    "uncharacterised_land_flows": [{"flow": n_, "compartment": c_, "weight": v}
                                                   for (n_, c_), v in sorted(missing.items(), key=lambda t: -t[1])[:15]],
                    "note": "factor_change_percent: the uniform change of the factors of that flow group that best explains "
                            "the gap to ecoinvent (e.g. +8 means ecoinvent's factors of that group appear 8 % higher). "
                            "explained: share of the gap variance explained. A high weight for an uncharacterised land "
                            "flow means that flow carries much of the result in ecoinvent but has no factor in Cyclia."})
    return res


def factor_finder(store, mc, M, mcols, out, G, max_flows=6):
    """For categories where many results deviate: which elementary flows, given a different factor, would explain the
    deviations of all compared datasets at once. Greedy sparse least squares (orthogonal matching pursuit) on
    gap_d = sum_f g_df * delta_f, rows weighted by 1/|ecoinvent result|. Reports the factor ecoinvent appears to use."""
    found = []
    for k, c in enumerate(mcols):
        m = c["method"]
        items = [x for x in out if x["category"] == m["category"] and x["indicator"] == m["indicator"]
                 and x["note"] == "" and x["reference"] and x["act_id"] in G]
        bad = [x for x in items if x["deviation_percent"] is not None and abs(x["deviation_percent"]) > 0.1]
        if len(items) < 5 or len(bad) < max(2, 0.05 * len(items)):
            continue
        w = np.array([1.0 / abs(x["reference"]) for x in items])
        y = np.array([x["reference"] - x["cyclia"] for x in items]) * w
        Gm = np.array([G[x["act_id"]] for x in items]) * w[:, None]
        # candidates: flows the method knows by name (a factor that differs, or one that did not match)
        names = {r["c_name"] for r in store.q("SELECT DISTINCT c_name FROM cf_raw WHERE method_id=?", (m["id"],))}
        known = np.array([mc.flow_cname[i][0] in names or M.C[k, i] != 0 for i in range(Gm.shape[1])], dtype=bool)
        cols = np.where((np.abs(Gm).sum(axis=0) > 0) & known)[0]
        if not len(cols):
            continue
        X = Gm[:, cols]
        norms = np.linalg.norm(X, axis=0)
        norms[norms == 0] = 1
        y0 = float(y @ y)
        if y0 == 0:
            continue
        sel, resid, coef = [], y.copy(), np.zeros(0)
        for _ in range(max_flows):
            score = np.abs(X.T @ resid) / norms
            score[sel] = -1
            j = int(np.argmax(score))
            if score[j] <= 0:
                break
            trial = sel + [j]
            cf_, *_ = np.linalg.lstsq(X[:, trial], y, rcond=None)
            r_new = y - X[:, trial] @ cf_
            if float(resid @ resid) - float(r_new @ r_new) < 0.02 * y0:
                break
            sel, coef, resid = trial, cf_, r_new
            if float(resid @ resid) < 1e-4 * y0:
                break
        if not sel:
            continue
        explained = 1 - float(resid @ resid) / y0
        flows = []
        for j, d in zip(sel, coef):
            i = int(cols[j])
            fr = store.one("SELECT name, compartment, subcompartment, unit, c_name FROM flows WHERE id=?", (int(mc.flow_ids[i]),))
            raw = store.q("SELECT c_comp, c_sub, location, value FROM cf_raw WHERE method_id=? AND c_name=? LIMIT 12",
                          (m["id"], fr["c_name"]))
            cy = float(M.C[k, i])
            flows.append({"flow": fr["name"], "flow_context": "/".join(x for x in (fr["compartment"], fr["subcompartment"]) if x),
                          "unit": fr["unit"], "cyclia_factor": cy, "implied_factor": cy + float(d),
                          "method_has": "; ".join(f"{r['c_comp'] or 'any'}/{r['c_sub'] or 'any'}"
                                                  f"{' @' + r['location'] if r['location'] else ''} = {r['value']:.4g}" for r in raw)
                                        or "no factor for this name"})
        found.append({"category": m["category"], "indicator": m["indicator"], "results": len(items), "deviating": len(bad),
                      "explained_percent": 100 * explained, "flows": flows})
    return found


def diagnose(store, mc, M, mcols, out, per_cat=2, top=12):
    """For categories with deviations above 0.1 %: which elementary flows of the worst datasets have no factor in
    Cyclia although the method has a factor for a flow with the same name (in another compartment, or not matched).
    The 'explained' share compares the factors that would be missing with the observed gap."""
    out_diag = []
    raw_cache = {}
    for k, c in enumerate(mcols):
        m = c["method"]
        items = [x for x in out if x["category"] == m["category"] and x["indicator"] == m["indicator"]
                 and x["deviation_percent"] is not None and abs(x["deviation_percent"]) > 0.1 and x["note"] == ""]
        if not items:
            continue
        if m["id"] not in raw_cache:
            raw = {}
            for r in store.q("SELECT c_name, c_comp, c_sub, location, value FROM cf_raw WHERE method_id=?", (m["id"],)):
                raw.setdefault(r["c_name"], []).append(r)
            raw_cache[m["id"]] = raw
        raw = raw_cache[m["id"]]
        for x in sorted(items, key=lambda x: -abs(x["deviation_percent"]))[:per_cat]:
            j = mc.act_index[x["act_id"]]
            f = np.zeros(mc.n)
            f[j] = 1.0 if mc.diag[j] >= 0 else -1.0
            g = mc.B @ mc.solve(f)
            gap = x["reference"] - x["cyclia"]
            flows = []
            for i in np.where((g != 0) & (M.C[k] == 0))[0]:
                name, comp = mc.flow_cname[i]
                cands = raw.get(name)
                if not cands:
                    continue
                fr = store.one("SELECT name, compartment, subcompartment, c_sub, unit FROM flows WHERE id=?",
                               (int(mc.flow_ids[i]),))
                same = [r for r in cands if r["c_comp"] in ("", comp)] or cands
                v = same[0]["value"]
                flows.append({"flow": fr["name"], "flow_context": "/".join(x for x in (fr["compartment"], fr["subcompartment"]) if x),
                              "canonical_sub": fr["c_sub"], "amount": float(g[i]), "unit": fr["unit"],
                              "method_has": "; ".join(f"{r['c_comp'] or 'any'}/{r['c_sub'] or 'any'}"
                                                      f"{' @' + r['location'] if r['location'] else ''} = {r['value']:.4g}"
                                                      for r in (same + [r for r in cands if r not in same])[:8]),
                              "missing_contribution": float(g[i] * v)})
            flows.sort(key=lambda r: -abs(r["missing_contribution"]))
            explained = sum(r["missing_contribution"] for r in flows)
            out_diag.append({"category": m["category"], "indicator": m["indicator"], "dataset": x["activity"],
                             "location": x["location"], "ecoinvent": x["reference"], "cyclia": x["cyclia"], "gap": gap,
                             "explained_by_unmatched_factors": explained,
                             "explained_percent": (100 * explained / gap) if gap else None, "flows": flows[:top]})
    return out_diag



def _bench_summary(store, mc, M, mcols, out, n_datasets, n_file, n_matched, groups):
    def stats(items):
        d = [abs(x["deviation_percent"]) for x in items if x["deviation_percent"] is not None]
        if not d:
            return {"n": 0}
        d = np.array(d)
        return {"n": int(len(d)), "median": float(np.median(d)), "p95": float(np.percentile(d, 95)), "max": float(d.max()),
                "within_0_1": float((d <= 0.1).mean() * 100), "within_1": float((d <= 1).mean() * 100)}
    used = np.unique(mc.b_rows)
    by_cat = []
    for k, c in enumerate(mcols):
        items = [x for x in out if x["category"] == c["method"]["category"] and x["indicator"] == c["method"]["indicator"]]
        s = stats(items)
        no_cf = int(sum(1 for i in used if M.C[k, i] == 0))
        signed = [x["deviation_percent"] for x in items if x["deviation_percent"] is not None]
        bias = float(np.median(signed)) if signed else 0.0
        hint = ""
        if s.get("n") and s["median"] > 0.1:
            if bias < -0.1:
                hint = (f"Cyclia is lower for most datasets: some elementary flows probably have no factor ({no_cf:,} flows "
                        "used by the database have none in this category). Check the flow names or import a mapping.")
            elif bias > 0.1:
                hint = "Cyclia is higher for most datasets: check for duplicated factors (two method versions mixed)."
            else:
                hint = "Deviations in both directions: check regional factors and the datasets with the largest deviation."
        by_cat.append(dict(s, category=c["method"]["category"], indicator=c["method"]["indicator"],
                           family=c["method"]["family"], unit=c["method"]["unit"], flows_without_factor=no_cf,
                           median_signed=bias, hint=hint))
    by_group = [dict(stats([x for x in out if x["group"] == g]), group=g) for g in groups]
    total = stats(out)
    worst = sorted([x for x in out if x["deviation_percent"] is not None], key=lambda x: -abs(x["deviation_percent"]))[:40]
    unlinked = store.one("SELECT COUNT(*) AS n FROM unlinked WHERE linked_to IS NULL")["n"]
    if total.get("n") and total["within_0_1"] >= 95:
        verdict = (f"Validated: {total['within_0_1']:.1f} % of {total['n']:,} results agree with ecoinvent within 0.1 % "
                   f"(median deviation {total['median']:.2g} %).")
    elif total.get("n") and total["within_1"] >= 95:
        verdict = (f"Close agreement: {total['within_1']:.1f} % of results within 1 %, {total['within_0_1']:.1f} % within "
                   "0.1 %. Look at the categories and datasets below before publishing.")
    else:
        verdict = "Deviations found. The table per category says where to look; send the Excel report for help."
    return {"verdict": verdict, "summary": total, "by_category": by_cat, "by_group": by_group, "worst": worst,
            "rows": out, "datasets": n_datasets, "datasets_in_file": n_file, "datasets_matched": n_matched,
            "categories": len(mcols), "families": sorted({c["method"]["family"] for c in mcols}),
            "unlinked_inputs": unlinked, "environment": environment()}


def benchmark_excel(path, res):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    b = Font(bold=True)
    ws.append(["Cyclia benchmark against ecoinvent's cumulative LCIA results"])
    ws["A1"].font = b
    env = res["environment"]
    for k, v in (("Verdict", res["verdict"]), ("Cyclia", env["cyclia"]), ("Date", env["date"]),
                 ("Datasets compared", res["datasets"]), ("Datasets in the results file", res["datasets_in_file"]),
                 ("Found in the library", res["datasets_matched"]), ("Categories", res["categories"]),
                 ("Results compared", res["summary"].get("n")), ("Median deviation (%)", res["summary"].get("median")),
                 ("Within 0.1 % (%)", res["summary"].get("within_0_1")), ("Within 1 % (%)", res["summary"].get("within_1")),
                 ("Inputs without supplier in the library", res["unlinked_inputs"])):
        ws.append([k, v])
    ws2 = wb.create_sheet("By category")
    ws2.append(["Family", "Category", "Indicator", "Unit", "Results", "Median |dev| %", "95th pct |dev| %", "Max |dev| %",
                "Within 0.1 %", "Within 1 %", "Flows without factor", "Hint"])
    for c in res["by_category"]:
        ws2.append([c["family"], c["category"], c["indicator"], c["unit"], c.get("n"), c.get("median"), c.get("p95"),
                    c.get("max"), c.get("within_0_1"), c.get("within_1"), c["flows_without_factor"], c["hint"]])
    ws3 = wb.create_sheet("All results")
    ws3.append(["Group", "Dataset", "Location", "Product", "Category", "Indicator", "ecoinvent", "Cyclia", "Deviation %", "Note"])
    for x in res["rows"]:
        ws3.append([x["group"], x["activity"], x["location"], x["product"], x["category"], x["indicator"], x["reference"],
                    x["cyclia"], x["deviation_percent"], x["note"]])
    ws4 = wb.create_sheet("Diagnosis")
    ws4.append(["Category", "Dataset", "Location", "ecoinvent", "Cyclia", "Gap", "Explained by unmatched factors",
                "Explained %", "Flow without factor", "Flow compartment", "Canonical subcompartment", "Amount", "Unit",
                "Factors the method has for this name", "Missing contribution"])
    for d in res.get("diagnosis") or []:
        base = [d["category"], d["dataset"], d["location"], d["ecoinvent"], d["cyclia"], d["gap"],
                d["explained_by_unmatched_factors"], d["explained_percent"]]
        if not d["flows"]:
            ws4.append(base + ["(no unmatched factor found: the cause is elsewhere)"])
        for fl in d["flows"]:
            ws4.append(base + [fl["flow"], fl["flow_context"], fl["canonical_sub"], fl["amount"], fl["unit"], fl["method_has"],
                               fl["missing_contribution"]])
    for c in ws4[1]:
        c.font = b
    if res.get("land_use"):
        wl = wb.create_sheet("Land use reconciliation")
        wl.append(["Category", "Indicator", "Datasets", "Flow group", "Share of Cyclia result", "Factor change that explains the gap (%)",
                   "Gap variance explained"])
        for c_ in res["land_use"]:
            for g in c_["groups"]:
                wl.append([c_["category"], c_["indicator"], c_["n"], g["group"], g["share_of_result"],
                           g["factor_change_percent"], c_["explained"]])
        wl.append([])
        wl.append(["Category", "Land flow without a factor in Cyclia", "Compartment", "Weight (sum of amount / |result|)"])
        for c_ in res["land_use"]:
            for f_ in c_["uncharacterised_land_flows"]:
                wl.append([c_["category"], f_["flow"], f_["compartment"], f_["weight"]])
        wl.append([])
        wl.append([res["land_use"][0]["note"]])
    if res.get("cf_conflicts"):
        wc = wb.create_sheet("Conflicting factors")
        wc.append(["Category", "Flow (canonical)", "Compartment", "Location", "Different values", "Min", "Max"])
        for c_ in res["cf_conflicts"]:
            wc.append([c_["category"], c_["flow"], c_["compartment"], c_["location"], c_["values"], c_["min"], c_["max"]])
    ws5 = wb.create_sheet("Factor finder")
    ws5.append(["Category", "Indicator", "Results compared", "Deviating > 0.1 %", "Deviation explained %", "Flow",
                "Compartment", "Unit", "Factor in Cyclia", "Factor ecoinvent appears to use", "Factors in the method file"])
    for d in res.get("factor_finder") or []:
        for fl in d["flows"]:
            ws5.append([d["category"], d["indicator"], d["results"], d["deviating"], d["explained_percent"], fl["flow"],
                        fl["flow_context"], fl["unit"], fl["cyclia_factor"], fl["implied_factor"], fl["method_has"]])
    for c in ws5[1]:
        c.font = b
    ws5.column_dimensions["F"].width = 40
    ws5.column_dimensions["K"].width = 60
    for w in (ws, ws2, ws3, ws4):
        w.column_dimensions["A"].width = 34
        w.column_dimensions["B"].width = 40
    for c in ws2[1] + ws3[1]:
        c.font = b
    wb.save(path)
    return path


def preferred_family(store):
    """EF 3.1 if it is in the library (the EU reference), else every method found in the results file."""
    fams = [m["family"] for m in store.methods()]
    for pat in (r"^ef v?3\.1$", r"^ef v?3\.1", r"^ef v?3"):
        hit = next((f for f in fams if re.search(pat, f.strip().lower()) and "no lt" not in f.lower()), None)
        if hit:
            return hit
    return ""
