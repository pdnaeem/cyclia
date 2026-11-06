"""Scientific Benchmark Centre: one place that lists, per method and per check, the reference, Cyclia's result, the
differences, the missing flows and the status.

Rules
- A check counts as validated only when it ran in this installation and every result is within its tolerance.
- A check that did not run is "Not run"; a check whose software is not installed (Brightway) is "Not available".
  Neither counts as validated. Skipped automated tests are never shown as validation.
- Every run is recorded with its date, Cyclia version and environment, so the Centre shows the latest evidence.
"""
import datetime
import json
import shutil
import tempfile

import calc

# IPCC AR6 WG1 (2021), chapter 7, Table 7.15 and Table 7.SM.7: GWP100 (kg CO2-eq per kg). Transcribed here
# independently of the built-in method, so that the check compares the implementation with the publication.
AR6_GWP100 = [
    ("Carbon dioxide, fossil", 1.0), ("Methane, fossil", 29.8), ("Methane, non-fossil", 27.0),
    ("Dinitrogen monoxide", 273.0), ("Sulfur hexafluoride", 25200.0), ("Nitrogen fluoride", 17400.0),
    ("Methane, tetrafluoro-, R-14", 7380.0), ("Ethane, hexafluoro-, HFC-116", 12400.0),
    ("Methane, trifluoro-, HFC-23", 14600.0), ("Methane, difluoro-, HFC-32", 771.0),
    ("Ethane, pentafluoro-, HFC-125", 3740.0), ("Ethane, 1,1,1,2-tetrafluoro-, HFC-134a", 1530.0),
    ("Ethane, 1,1,1-trifluoro-, HFC-143a", 5810.0), ("Ethane, 1,1-difluoro-, HFC-152a", 164.0),
]
AR6_SOURCE = "IPCC AR6 WG1 (2021), chapter 7, Table 7.15 and Table 7.SM.7, GWP100"

# methods whose factors Cyclia can only check against the official package of their authors
OFFICIAL_PACKAGE = {"aware": "AWARE 2.0 (WULCA)", "lanca": "LANCA (Fraunhofer IBP)", "usetox": "USEtox 2 (USEtox team)"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def record(store, kind, title, summary):
    """Keep the summary of a run (kind: suite, brightway, ecoinvent, ipcc)."""
    from trust import environment
    with store.lock:
        store.conn.execute("INSERT INTO benchmark_runs(kind, title, time, summary) VALUES(?,?,?,?)",
                           (kind, title, _now(), json.dumps({**summary, "environment": environment()})))
        store.conn.commit()


def _latest(store, kind, title=None):
    q = "SELECT * FROM benchmark_runs WHERE kind=?" + (" AND title=?" if title else "") + " ORDER BY id DESC LIMIT 1"
    r = store.one(q, (kind, title) if title else (kind,))
    if not r:
        return None
    r = dict(r)
    r["summary"] = json.loads(r["summary"])
    return r


def ipcc_check(progress=lambda *a: None):
    """Numerical check of the built-in IPCC 2021 GWP100 method: in an empty library, one dataset emits 1 kg of each
    gas, and the result must equal the published GWP100 within 1e-12."""
    from importers import lcia
    from store import Workspace
    tmp = tempfile.mkdtemp(prefix="cyclia-ipcc-")
    ws = Workspace(tmp)
    rows = []
    try:
        calc.invalidate()
        st = ws.create("ipcc")
        db = st.create_database("IPCC check", "Cyclia benchmark", "1", "test")
        with st.lock:
            fids = {}
            for i, (name, _) in enumerate(AR6_GWP100):
                fids[name] = st.add_flow(f"ipcc-{i}", name, "air", "unspecified", "kg", "")
            acts = {}
            for i, (name, _) in enumerate(AR6_GWP100):
                acts[name] = st.conn.execute(
                    "INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                    (db, f"g{i}", f"emission of 1 kg {name}", "test", "GLO", "unit")).lastrowid
                st.conn.execute("INSERT INTO bio(activity_id,flow_id,amount) VALUES(?,?,1)", (acts[name], fids[name]))
            st.conn.execute("UPDATE databases SET n_activities=? WHERE id=?", (len(acts), db))
            st._bump_lib()
            st.conn.commit()
        mids = lcia.install_builtin(st)
        total = [m for m in mids if st.one("SELECT category FROM methods WHERE id=?", (m,))["category"].endswith("total")][0]
        calc.invalidate()
        for k, (name, ref) in enumerate(AR6_GWP100):
            progress(int(100 * k / len(AR6_GWP100)), name)
            m = st.save_model({"name": name, "product": "p", "unit": "kg", "amount": 1,
                               "scope": {"goal": "IPCC check", "boundary": "cradle-to-gate"}})
            st.add_input(m, "activity", acts[name], 1.0)
            got = calc.run(st, m, [total])["results"][0]["total"]
            rel = abs(got - ref) / ref
            rows.append({"gas": name, "reference": ref, "cyclia": got, "absolute_difference": abs(got - ref),
                         "relative_difference": rel, "passed": rel <= 1e-12})
    finally:
        ws.close_all()
        calc.invalidate()
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(r["passed"] for r in rows)
    return {"rows": rows, "passed": ok, "source": AR6_SOURCE, "n": len(rows),
            "max_relative_difference": max(r["relative_difference"] for r in rows),
            "verdict": (f"All {len(rows)} gases equal the published GWP100 values ({AR6_SOURCE})." if ok else
                        f"{sum(not r['passed'] for r in rows)} gas(es) differ from the published values.")}


def centre(store):
    """The table of the Benchmark Centre."""
    import brightway_check
    rows = []

    def add(check, reference, ref_result, cyc_result, abs_diff, rel_diff, max_dev, missing, status, run=None, note=""):
        rows.append({"check": check, "reference": reference, "reference_result": ref_result, "cyclia_result": cyc_result,
                     "absolute_difference": abs_diff, "relative_difference": rel_diff, "maximum_deviation": max_dev,
                     "missing_flows": missing, "status": status, "date": (run or {}).get("time", "")[:10],
                     "cyclia_version": ((run or {}).get("summary") or {}).get("environment", {}).get("cyclia", ""),
                     "note": note})

    s = _latest(store, "suite")
    if s:
        sm = s["summary"]
        add("Calculation core: 35 systems with exact answers", "Hand-calculated and analytic results",
            f"{sm['total']} exact answers", f"{sm['passed']} reproduced", sm.get("max_absolute_error"),
            sm.get("max_relative_error"), sm.get("max_relative_error"), "-",
            "Validated" if sm["passed"] == sm["total"] else "Deviations", s)
    else:
        add("Calculation core: 35 systems with exact answers", "Hand-calculated and analytic results", "", "", None,
            None, None, "-", "Not run", note="Run the validation suite.")
    b = _latest(store, "brightway")
    if b:
        sm = b["summary"]
        add(f"Brightway (bw2calc {sm.get('bw2calc', '')}) on {sm.get('database', '')}", "Brightway's own matrices and solve",
            f"{sm['results']:,} results", f"{sm['results']:,} results", None, sm["max_relative_difference"],
            sm["max_relative_difference"], "-", "Validated" if sm["passed"] else "Deviations", b)
    else:
        avail = brightway_check.available()
        add("Brightway (bw2calc)", "Brightway's own matrices and solve", "", "", None, None, None, "-",
            "Not run" if avail else "Not available",
            note="Run Compare with Brightway below." if avail else
            "Brightway is not installed here, so this check cannot run and is not counted as validated.")
    i = _latest(store, "ipcc")
    if i:
        sm = i["summary"]
        add("IPCC 2021 GWP100 (built-in method)", AR6_SOURCE, f"{sm['n']} published values", f"{sm['n']} computed",
            sm.get("max_absolute_difference"), sm["max_relative_difference"], sm["max_relative_difference"], "-",
            "Validated" if sm["passed"] else "Deviations", i)
    else:
        add("IPCC 2021 GWP100 (built-in method)", AR6_SOURCE, "", "", None, None, None, "-", "Not run",
            note="Run the IPCC check.")
    bench = {}
    for r in store.q("SELECT * FROM benchmark_runs WHERE kind='ecoinvent' ORDER BY id"):
        bench[r["title"]] = dict(r) | {"summary": json.loads(r["summary"])}
    for fam, r in bench.items():
        sm = r["summary"]
        status = "Validated" if sm.get("within_0_1", 0) >= 95 and not sm.get("weak") else (
            "Validated except some categories" if sm.get("within_0_1", 0) >= 95 else "Deviations")
        add(f"{fam} on {sm.get('database', 'ecoinvent')}", "ecoinvent's own cumulative LCIA results",
            f"{sm.get('n', 0):,} results", f"{sm.get('n', 0):,} results", None, (sm.get("median") or 0) / 100,
            (sm.get("max") or 0) / 100, sm.get("missing_flows", "-"), status, r,
            note=f"{sm.get('within_0_1', 0):.1f} % within 0.1 %" + (f"; not: {sm['weak']}" if sm.get("weak") else ""))
    for pk in package_checks(store):
        add(f"{pk['package']} factor package: structure", f"{pk['source'] or 'imported'}",
            f"{pk['factors']:,} factors" + (f", {pk['locations']:,} locations" if pk["locations"] else ""), "", None, None,
            None, "-", pk["status"],
            note=("; ".join(pk["problems"]) if pk["problems"] else "Complete, units and ranges correct.") +
            " The values are not compared with the package's reference results.")
    fams = [f["family"] for f in store.q("SELECT DISTINCT family FROM methods ORDER BY family")]
    for fam in fams:
        if fam in bench or fam.startswith("Cyclia built-in"):
            continue
        low = fam.lower()
        off = next((v for k, v in OFFICIAL_PACKAGE.items() if k in low), None)
        add(fam, "ecoinvent's cumulative LCIA results" if not off else f"official factor package: {off}", "", "", None,
            None, None, "-", "Not run",
            note=("Validate with ecoinvent's results file (Validation > ecoinvent), with the option for every installed "
                  "method." if not off else
                  f"The factor values are checked only against the official {off} package, which is not bundled."))
    return {"rows": rows, "rule": "Only checks that ran in this installation with every result within tolerance count "
                                  "as validated. 'Not run' and 'Not available' are not validation.",
            "generated": _now()}


def package_checks(store):
    """Structure checks of imported official factor packages. These check completeness, units and ranges; they do
    not compare values with the package's reference results, so their status is 'Package checked', never
    'Validated'."""
    import regional
    out = []
    # AWARE
    rows = store.q("SELECT key, location, value, source FROM native_factors WHERE method=?", (regional.AWARE,))
    if rows:
        src = rows[0]["source"] or ""
        locs = {}
        for r in rows:
            use, _, m = r["key"].partition("|m")
            locs.setdefault(r["location"], {}).setdefault(use, set()).add(int(m) if m else 0)
        problems = []
        if "GLO" not in locs:
            problems.append("no world (GLO) factor for locations without their own")
        part = [l for l, u in locs.items() if set(u) != {"agri", "non_agri", "unknown"}]
        if part:
            problems.append(f"{len(part)} location(s) without all three uses (agri, non_agri, unknown), e.g. {part[0]}")
        months = [l for l, u in locs.items() for use, ms in u.items() if (ms - {0}) and (ms - {0}) != set(range(1, 13))]
        if months:
            problems.append(f"{len(set(months))} location(s) with monthly factors for only some months")
        out_rng = [r for r in rows if not regional.AWARE_RANGE[0] - 1e-9 <= r["value"] <= regional.AWARE_RANGE[1] + 1e-9]
        if out_rng:
            problems.append(f"{len(out_rng)} factor(s) outside 0.1 to 100")
        if src.startswith("demo"):
            problems.append("these are the demo factors, not the official package")
        elif not src or src == "imported table":
            problems.append("the package and its version are not named")
        out.append({"package": "AWARE", "factors": len(rows), "locations": len(locs), "source": src,
                    "problems": problems, "status": "Package checked" if not problems else "Package incomplete"})
    # LANCA
    rows = store.q("SELECT indicator, key, location, source FROM native_factors WHERE method=?", (regional.LANCA,))
    if rows:
        src = rows[0]["source"] or ""
        have = {}
        for r in rows:
            kind, _, lu = r["key"].partition("|")
            have.setdefault((lu, r["location"]), set()).add((r["indicator"], kind))
        # the five LANCA indicators of the package; soil organic carbon is optional and the SQI is aggregated by
        # Cyclia from the others
        core = regional.LANCA_INDICATORS[:5]
        need = {(i, k) for i in core for k in ("occupation", "transformation_to", "transformation_from")}
        problems = []
        gaps = [k for k, v in have.items() if not need <= v]
        if gaps:
            problems.append(f"{len(gaps)} land use / location pair(s) without every indicator for occupation and "
                            f"both transformations, e.g. {gaps[0][0]} in {gaps[0][1]}")
        if not any(loc == "GLO" for _, loc in have):
            problems.append("no world (GLO) factors for locations without their own")
        if src.startswith("demo"):
            problems.append("these are the demo factors, not the official package")
        elif not src or src == "imported table":
            problems.append("the package and its version are not named")
        out.append({"package": "LANCA", "factors": len(rows), "locations": len({l for _, l in have}), "source": src,
                    "problems": problems, "status": "Package checked" if not problems else "Package incomplete"})
    # USEtox (methods whose family names it)
    for fam in [r["family"] for r in store.q("SELECT DISTINCT family FROM methods WHERE lower(family) LIKE '%usetox%'")]:
        cats = store.q("SELECT id, category, unit FROM methods WHERE family=?", (fam,))
        problems = []
        for c in cats:
            u = (c["unit"] or "").lower()
            want = "ctuh" if "human" in c["category"].lower() else "ctue"
            if want not in u.replace(" ", ""):
                problems.append(f"{c['category']}: unit '{c['unit']}' is not {want.upper()}")
        neg = store.one(f"SELECT COUNT(*) AS n FROM cf_raw WHERE value<0 AND method_id IN "
                        f"(SELECT id FROM methods WHERE family=?)", (fam,))["n"]
        if neg:
            problems.append(f"{neg} negative factor(s)")
        comps = {r["c_comp"] for r in store.q("SELECT DISTINCT c_comp FROM cf_raw WHERE method_id IN (SELECT id FROM "
                                              "methods WHERE family=?)", (fam,))}
        miss = [c for c in ("air", "water", "soil") if c not in comps]
        if miss:
            problems.append("no factors for emissions to " + ", ".join(miss))
        n = store.one("SELECT COUNT(DISTINCT c_name) AS n FROM cf_raw WHERE method_id IN (SELECT id FROM methods WHERE "
                      "family=?)", (fam,))["n"]
        out.append({"package": fam, "factors": n, "locations": None, "source": fam, "problems": problems,
                    "status": "Package checked" if not problems else "Package incomplete"})
    return out


def summarise(kind, res):
    """Compact summary of a run result, for record()."""
    if kind == "suite":
        errs = [c for c in res["cases"]]
        return {"passed": res["passed"], "total": res["total"],
                "max_relative_error": max((c["error"] for c in errs if c["error_kind"] == "relative"), default=0.0),
                "max_absolute_error": max((c["error"] for c in errs if c["error_kind"] == "absolute"), default=0.0)}
    if kind == "brightway":
        return {k: res.get(k) for k in ("passed", "database", "results", "max_relative_difference", "categories",
                                        "datasets")} | {"bw2calc": (res.get("brightway") or {}).get("bw2calc")}
    if kind == "ipcc":
        return {"passed": res["passed"], "n": res["n"], "max_relative_difference": res["max_relative_difference"],
                "max_absolute_difference": max(r["absolute_difference"] for r in res["rows"])}
    raise ValueError(kind)


def record_ecoinvent(store, res):
    """One record per method family of an ecoinvent benchmark."""
    cats = res.get("by_category") or []
    for fam in sorted({c["family"] for c in cats}):
        cs = [c for c in cats if c["family"] == fam and c.get("n")]
        if not cs:
            continue
        n = sum(c["n"] for c in cs)
        weak = [c["category"] for c in cs if c["within_1"] < 95]
        record(store, "ecoinvent", fam, {
            "n": n, "median": float(sorted(c["median"] for c in cs)[len(cs) // 2]), "max": max(c["max"] for c in cs),
            "within_0_1": sum(c["within_0_1"] * c["n"] for c in cs) / n, "weak": ", ".join(weak),
            "missing_flows": "see report", "database": ", ".join(res.get("databases_compared") or []) or "ecoinvent"})


def excel(path, c):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Benchmark Centre"
    ws.append(["Scientific Benchmark Centre", c["generated"]])
    ws.append([c["rule"]])
    ws.append([])
    cols = ["Check", "Reference", "Reference result", "Cyclia result", "Absolute difference", "Relative difference",
            "Maximum deviation", "Missing flows", "Status", "Date", "Cyclia version", "Note"]
    ws.append(cols)
    for cell in ws[4]:
        cell.font = Font(bold=True)
    for r in c["rows"]:
        ws.append([r["check"], r["reference"], r["reference_result"], r["cyclia_result"], r["absolute_difference"],
                   r["relative_difference"], r["maximum_deviation"], r["missing_flows"], r["status"], r["date"],
                   r["cyclia_version"], r["note"]])
    for col, w in zip("ABCDEFGHIJKL", (44, 40, 18, 18, 14, 14, 14, 12, 22, 12, 10, 60)):
        ws.column_dimensions[col].width = w
    wb.save(path)
