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
import re
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
        # 1.9.0: deviation statistics per category are kept for the publishable report (statistics only: no
        # ecoinvent value is stored here)
        cats_kept = [{k: c.get(k) for k in ("category", "indicator", "unit", "n", "median", "p95", "max", "within_0_1",
                                            "within_1", "median_signed", "hint", "cancellation", "numerically_zero")} for c in cs]
        record(store, "ecoinvent", fam, {
            "n": n, "median": float(sorted(c["median"] for c in cs)[len(cs) // 2]), "max": max(c["max"] for c in cs),
            "within_0_1": sum(c["within_0_1"] * c["n"] for c in cs) / n,
            "within_1": sum(c["within_1"] * c["n"] for c in cs) / n, "weak": ", ".join(weak),
            "missing_flows": "see report", "database": _db_label(res), "categories": cats_kept,
            "datasets_compared": res.get("datasets_matched") or res.get("datasets"),
            "datasets_in_file": res.get("datasets_in_file"), "inventory_checked": bool(res.get("inventory")),
            "unlinked_inputs": res.get("unlinked_inputs"), "per_method": True})


def _db_label(res):
    """'ecoinvent 3.11 (cut-off)' from the databases a benchmark compared (dicts with name, version, system
    model; plain names are accepted too)."""
    out = []
    for d in res.get("databases_compared") or []:
        if isinstance(d, dict):
            extra = ", ".join(str(x) for x in (d.get("version"), d.get("system_model")) if x)
            out.append(str(d.get("name") or "") + (f" ({extra})" if extra else ""))
        else:
            out.append(str(d))
    return "; ".join(x for x in out if x) or res.get("database") or "ecoinvent"


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


# ============================================================================ publishable benchmark reports (1.9.0)
GROUPS = (("recipe", "ReCiPe"), ("cml", "CML-IA"), ("ipcc", "IPCC"), ("environmental footprint", "EF"),
          ("ef v3", "EF"), ("ef 3", "EF"))


def method_group(family):
    """ReCiPe, CML-IA, IPCC or EF for a method family name; the family itself otherwise ("no LT" variants, without
    long-term emissions, go with their family)."""
    family = re.sub(r"\s+no lt$", "", (family or "").strip(), flags=re.I)
    low = family.lower()
    for k, g in GROUPS:
        if k in low:
            return g
    if low.startswith("ef "):
        return "EF"
    return family


def _status(sm):
    if sm.get("within_0_1", 0) >= 95 and not sm.get("weak"):
        return "Validated"
    return "Validated except some categories" if sm.get("within_0_1", 0) >= 95 else "Deviations"


def _pct(v, digits=3):
    return "" if v is None else f"{v:.{digits}g}"


def _slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def publication(store, cyclia_version=""):
    """Markdown reports of the latest ecoinvent benchmark of every method family, grouped (ReCiPe, CML-IA, IPCC, EF).

    The reports hold deviation statistics only (how far Cyclia's results are from ecoinvent's own results), never an
    ecoinvent value, so they can be published. Returns {file name: text}; empty when no benchmark was run."""
    latest = {}
    for r in store.q("SELECT * FROM benchmark_runs WHERE kind='ecoinvent' ORDER BY id"):
        sm = json.loads(r["summary"])
        sm.setdefault("pooled", bool(sm.get("categories")) and not sm.get("per_method"))   # recorded by 1.9.0
        latest[r["title"]] = dict(r) | {"summary": sm}
    return _publication(latest, cyclia_version)


def _publication(latest, cyclia_version=""):
    """{family: {"time", "summary"}} -> {file name: Markdown}."""
    by_group = {}
    for fam, r in latest.items():
        key = (method_group(fam), r["summary"].get("database") or "ecoinvent")
        by_group.setdefault(key, []).append((fam, r))
    files = {}
    index = []
    for (grp, db), runs in sorted(by_group.items()):
        name = f"{_slug(grp)}-{_slug(db)}.md"
        text = _report(grp, db, runs, cyclia_version)
        files[name] = text
        sms = [r["summary"] for _, r in runs]
        statuses = {_status(sm) for sm in sms}
        status = "Validated" if statuses == {"Validated"} else (
            "Deviations" if "Deviations" in statuses else "Validated except some categories")
        n = sum(sm.get("n", 0) for sm in sms)
        index.append(f"| [{grp}]({name}) | {db} | {n:,} | {status} | "
                     f"{max(r['time'] for _, r in runs)[:10]} | "
                     f"{max((r['summary'].get('environment') or {}).get('cyclia', '') for _, r in runs)} |")
    if files:
        files["README.md"] = "\n".join([
            "# Cyclia benchmarks against ecoinvent",
            "",
            "Each report compares Cyclia's results with ecoinvent's own cumulative LCIA results, for the method "
            "family and the ecoinvent version named. The reports contain deviation statistics only; no ecoinvent value "
            "is reproduced. They are produced by Cyclia (Validation > Benchmark Centre > Publish benchmark reports) "
            "on a computer with an ecoinvent licence.",
            "",
            "| Method | Database | Results compared | Status | Date | Cyclia |",
            "|---|---|---:|---|---|---|",
            *index,
            "",
            "A method that is not listed here has not been benchmarked against ecoinvent and is not claimed as "
            "validated. Status rule: 'Validated' when at least 95 % of all results agree within 0.1 % and every "
            "category has at least 95 % of its results within 1 %.",
            ""])
    return files


def _report(grp, db, runs, cyclia_version):
    env = max(((r["summary"].get("environment") or {}) for _, r in runs), key=lambda e: e.get("date", ""))
    sms = [r["summary"] for _, r in runs]
    n = sum(sm.get("n", 0) for sm in sms)
    lines = [f"# {grp} benchmark: Cyclia against ecoinvent's cumulative LCIA results", "", f"Database: {db}", ""]
    for fam, r in runs:
        sm = r["summary"]
        lines += [f"**{fam}**: {_status(sm)}. {sm.get('within_0_1', 0):.2f} % of {sm.get('n', 0):,} results within "
                  f"0.1 % of ecoinvent's value" + (f", {sm['within_1']:.2f} % within 1 %" if sm.get("within_1") is not None
                                                  else "") + "." +
                  (f" Categories with less than 95 % of results within 1 %: {sm['weak']}." if sm.get("weak") else ""), ""]
    lines += ["## What was compared", "",
              f"- Reference: ecoinvent's own cumulative LCIA results for {db}, the file ecoinvent provides to licence "
              "holders with the database. Cyclia imported the same database (ecoSpold2) and the method, calculated "
              "every sampled dataset with its full supply chain and compared the scores, result by result.",
              f"- Results compared: {n:,} (datasets x impact categories)."]
    d = next((sm.get("datasets_compared") for sm in sms if sm.get("datasets_compared")), None)
    if d:
        f = next((sm.get("datasets_in_file") for sm in sms if sm.get("datasets_in_file")), None)
        lines.append(f"- Datasets: {d:,} compared" + (f" of {f:,} in the results file" if f else "") +
                     ", matched by 'Activity UUID_Product UUID' (or by name, geography and product).")
    if any(sm.get("inventory_checked") for sm in sms):
        lines.append("- The cumulative inventory was compared with ecoinvent's cumulative LCI as well, which separates "
                     "deviations caused by the inventory from those caused by the factors.")
    sw = [f"Cyclia {env.get('cyclia') or cyclia_version}"] + [f"{k} {env[v]}" for k, v in
                                                             (("Python", "python"), ("NumPy", "numpy"), ("SciPy", "scipy"))
                                                             if env.get(v)] + ([env["platform"]] if env.get("platform") else [])
    lines += [f"- Software: {', '.join(sw)}; run on {env.get('date', '')[:10]}.", "",
              "## Deviation per impact category", "",
              "Deviation = |Cyclia - ecoinvent| / |ecoinvent| x 100, per dataset. Signed median: negative when Cyclia "
              "is lower for most datasets.", "",
              "| Method | Category | Indicator | Unit | Results | Median % | Signed median % | 95th percentile % | Max % "
              "| Within 0.1 % | Within 1 % | Within round-off |",
              "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    notes = []
    for fam, r in runs:
        cats = r["summary"].get("categories")
        if not cats:
            notes.append(f"{fam}: this benchmark was recorded by a version before 1.9.0, which kept the family totals "
                         "only. Run it again for the table per category.")
            continue
        for c in cats:
            lines.append(f"| {fam} | {c['category']} | {c.get('indicator') or ''} | {c.get('unit') or ''} | "
                         f"{c.get('n') or 0:,} | {_pct(c.get('median'))} | {_pct(c.get('median_signed'))} | "
                         f"{_pct(c.get('p95'))} | {_pct(c.get('max'))} | {_pct(c.get('within_0_1'), 4)} % | "
                         f"{_pct(c.get('within_1'), 4)} % | "
                         f"{'' if c.get('cancellation') is None else format(c['cancellation'], ',')} |")
            if c.get("analysis"):
                notes.append(f"{fam}, {c['category']} ({c.get('indicator') or ''}): {c['analysis']}")
            elif c.get("hint") and (c.get("median") or 0) > 0.1:
                notes.append(f"{c['category']}: {c['hint']}")
    lines += [""]
    if any(sm.get("pooled") for sm in sms):
        notes.insert(0, "This run was saved by Cyclia 1.9.0 or earlier, which pooled the statistics of methods with the "
                        "same category and indicator names (the 'Results' column counts all of them). Cyclia 1.9.1 "
                        "keeps each method apart.")
    if notes:
        lines += ["## Notes", ""] + [f"- {x}" for x in notes] + [""]
    lines += ["## How to read this", "",
              "- 'Validated' requires that at least 95 % of all results agree within 0.1 % and that every category has "
              "at least 95 % of its results within 1 %. A category below that is named above and its results should "
              "not be published before the cause is found.",
              "- The benchmark checks Cyclia's matrix calculation, its import of ecoinvent and the matching of the "
              "method's factors to ecoinvent's elementary flows. It does not check the method itself: Cyclia uses the "
              "factors as published.",
              "- Only the ecoinvent version and system model named were compared. Another version or system model "
              "needs its own run.",
              "- 'Within round-off' counts results whose net value is the small remainder of positive and negative "
              "contributions that cancel, and where the gap to ecoinvent is below 1e-9 of the sum of the absolute "
              "contributions (Cyclia 1.9.1 and later; empty for earlier runs). These count as agreeing.",
              "- From Cyclia 1.9.2, a deviating result that Cyclia's own solver does not determine to 0.1 % (forward, "
              "adjoint and refined solutions differ) and that is below 1e-6 of the category's largest result in "
              "ecoinvent's file is reported as 'below numerical resolution' and left out of the statistics, with its count.",
              "- No ecoinvent data is reproduced here: the report holds deviation statistics only.", "",
              "## Reproduce", "",
              "1. Import the ecoinvent database (ecoSpold2) and the method in Cyclia.",
              "2. Validation > ecoinvent: choose ecoinvent's cumulative LCIA results file for the same version and "
              "system model (optionally the cumulative LCI file too) and run the benchmark.",
              "3. Validation > Benchmark Centre > Publish benchmark reports writes this file.", ""]
    return "\n".join(lines)


def write_publication(store, folder, cyclia_version=""):
    """Write the reports of publication() into a folder; returns the paths written."""
    import os
    files = publication(store, cyclia_version)
    if not files:
        raise ValueError("No ecoinvent benchmark has been run in this project. Run Validation > ecoinvent first.")
    os.makedirs(folder, exist_ok=True)
    out = []
    for name, text in files.items():
        p = os.path.join(folder, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        out.append(p)
    return out


def publication_from_workbook(path):
    """The reports of publication() from a benchmark workbook saved by Cyclia (Validation > ecoinvent > Export).

    The By category sheet of Cyclia 1.9.0 and earlier pooled the statistics of methods that share a category and
    indicator name (seven 'climate change / GWP100' rows each showed 700 results). When the All results sheet is
    present and each dataset's rows follow the order of the By category sheet, the statistics are computed again per
    method from it; otherwise the pooled statistics are reported and the report says so. Each category below the
    status rule gets an analysis of its deviating results in relative terms only, so no ecoinvent value enters the
    report."""
    import itertools
    import numpy as np
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    if "Summary" not in wb.sheetnames or "By category" not in wb.sheetnames:
        raise ValueError("This is not a benchmark workbook saved by Cyclia (sheets Summary and By category).")
    summ = {}
    for r in wb["Summary"].iter_rows(values_only=True):
        if r and r[0] and len(r) > 1:
            summ[str(r[0])] = r[1]
    rows = list(wb["By category"].iter_rows(values_only=True))
    head = [str(h or "") for h in rows[0]]
    col = {h: i for i, h in enumerate(head)}

    def g(r, name):
        i = col.get(name)
        return r[i] if i is not None and i < len(r) else None
    cats = []
    for r in rows[1:]:
        if r and g(r, "Family"):
            cats.append((g(r, "Family"), {
                "category": g(r, "Category"), "indicator": g(r, "Indicator"), "unit": g(r, "Unit"), "n": g(r, "Results"),
                "median": g(r, "Median |dev| %"), "p95": g(r, "95th pct |dev| %"), "max": g(r, "Max |dev| %"),
                "within_0_1": g(r, "Within 0.1 %"), "within_1": g(r, "Within 1 %"), "hint": g(r, "Hint"),
                "median_signed": None, "cancellation": g(r, "Results within round-off of cancelling contributions")}))
    per_method = False
    if "All results" in wb.sheetnames:
        it = wb["All results"].iter_rows(values_only=True)
        ah = {str(h or ""): i for i, h in enumerate(next(it))}
        seq = [(c["category"], c["indicator"]) for _, c in cats]
        blocks = [list(b) for _, b in itertools.groupby(it, key=lambda r: (r[ah["Dataset"]], r[ah["Location"]],
                                                                           r[ah["Product"]]))]
        if blocks and all([(r[ah["Category"]], r[ah["Indicator"]]) for r in b] == seq for b in blocks):
            per_method = True
            for k, (_, c) in enumerate(cats):
                gi = ah.get("Sum of absolute contributions")
                vals = [(b[k][ah["ecoinvent"]], b[k][ah["Cyclia"]], b[k][ah["Deviation %"]],
                         b[k][gi] if gi is not None and gi < len(b[k]) else None) for b in blocks]
                d = np.array([v[2] for v in vals if v[2] is not None], dtype=float)
                if not len(d):
                    continue
                a = np.abs(d)
                c.update(n=int(len(d)), median=float(np.median(a)), p95=float(np.percentile(a, 95)), max=float(a.max()),
                         within_0_1=float((a <= 0.1).mean() * 100), within_1=float((a <= 1).mean() * 100),
                         median_signed=float(np.median(d)))
                c["_vals"] = vals
    for fam, c in cats:
        vals = c.pop("_vals", None)
        if vals and (c["within_1"] or 0) < 95:
            c["analysis"] = _weak_analysis(vals)
    db = summ.get("Database") or "ecoinvent"
    ver, sysm = summ.get("Database version"), summ.get("System model")
    label = f"ecoinvent ({ver}, {sysm})" if ver and str(db).lower().startswith("ecoinvent") else str(db)
    env = {"cyclia": str(summ.get("Cyclia") or ""), "date": str(summ.get("Date") or "")}
    lci = summ.get("ecoinvent cumulative LCI file")
    fams = {}
    for fam, c in cats:
        fams.setdefault(fam, []).append(c)
    latest = {}
    for fam, cs in fams.items():
        n = sum(c["n"] or 0 for c in cs)
        latest[fam] = {"time": env["date"], "summary": {
            "n": n, "database": label, "categories": cs, "environment": env,
            "within_0_1": sum((c["within_0_1"] or 0) * (c["n"] or 0) for c in cs) / n if n else 0,
            "within_1": sum((c["within_1"] or 0) * (c["n"] or 0) for c in cs) / n if n else 0,
            "weak": ", ".join(c["category"] for c in cs if (c["within_1"] or 0) < 95),
            "datasets_compared": summ.get("Datasets compared"), "datasets_in_file": summ.get("Datasets in the results file"),
            "inventory_checked": bool(lci and lci != "not used"),
            "pooled": not per_method}}
    return _publication(latest, env["cyclia"])


def _weak_analysis(vals):
    """Factual description, in relative terms only, of the deviating results of a category below the status rule."""
    top = max(abs(v[0] or 0) for v in vals) or 1.0
    dev = [v for v in vals if v[2] is not None and abs(v[2]) > 0.1]
    if not dev:
        return ""
    big = max(max(abs(v[0] or 0), abs(v[1] or 0)) for v in dev) / top
    flips = sum(1 for v in dev if (v[0] or 0) * (v[1] or 0) < 0)
    text = (f"{len(dev)} of {len(vals)} results deviate by more than 0.1 %. In each of them both results are at most "
            f"{big:.1g} of the largest result of the category in the sample"
            + (f", and in {flips} the two programs give opposite signs" if flips else "") + ".")
    g = [abs(v[3]) / abs(v[1]) for v in dev if v[3] is not None and v[1]]
    if g:
        text += (f" Cyclia's sum of absolute contributions is at most {max(g):.2g} times its net result, far from the "
                 "1e9 the round-off rule of 1.9.1 needs, so that rule does not apply.")
    text += (" The category is not validated. Cyclia 1.9.2 measures whether each such result is resolved by the solver "
             "and lists the datasets and exchanges that carry it (sheets Contributions and Negative exchanges).")
    return text