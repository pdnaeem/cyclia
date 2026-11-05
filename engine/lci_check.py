"""Inventory check against ecoinvent's cumulative LCI (Cyclia 1.3.8).

When Cyclia's LCIA result of a dataset differs from ecoinvent's published result, the gap has two possible parts:

    gap = ecoinvent result - Cyclia result
        = (ecoinvent result - C . g_ecoinvent)      factor part: ecoinvent's own inventory, characterised with the
                                                    factors in Cyclia (ecoinvent's LCIA implementation file), does not
                                                    give ecoinvent's own result
        + C . (g_ecoinvent - g_Cyclia)              inventory part: Cyclia's cumulative inventory differs from ecoinvent's

g are the cumulative elementary flows of one unit of the dataset, C the factors of one category. ecoinvent publishes
g_ecoinvent for every dataset (the cumulative LCI workbook), so both parts are measured, not guessed. A factor part
means ecoinvent's results use factors that are not in the factor file (Cyclia cannot fix that without the source);
an inventory part means the import or the linking differs and points to the flows that carry it.

The workbook is large (every dataset times every elementary flow), so it is read as a stream of XML rows and only the
rows of the compared datasets are kept.
"""
import re
import zipfile

import numpy as np
from lxml import etree

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _clear(el):
    el.clear()
    while el.getprevious() is not None:
        del el.getparent()[0]


def _col(ref):
    n = 0
    for ch in ref:
        if "A" <= ch <= "Z":
            n = n * 26 + ord(ch) - 64
        else:
            break
    return n - 1


def xlsx_sheets(path):
    """(sheet name, function that yields the rows of the sheet as {column index: value}) for each sheet, read as a
    stream (an xlsx file of several GB is never loaded as a whole)."""
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    ss = []
    if "xl/sharedStrings.xml" in names:
        for _, el in etree.iterparse(z.open("xl/sharedStrings.xml"), tag=NS + "si"):
            ss.append("".join(t.text or "" for t in el.iter(NS + "t")))
            _clear(el)
    rels = {}
    if "xl/_rels/workbook.xml.rels" in names:
        for r in etree.parse(z.open("xl/_rels/workbook.xml.rels")).getroot():
            t = r.get("Target", "")
            rels[r.get("Id")] = t.lstrip("/") if t.startswith("/") else "xl/" + t
    out = []
    for s in etree.parse(z.open("xl/workbook.xml")).getroot().iter(NS + "sheet"):
        target = rels.get(s.get(RNS + "id"))
        if target in names:
            out.append((s.get("name"), _rows_reader(z, target, ss)))
    return out


def _rows_reader(z, target, ss):
    def rows(keep=None):
        """Yields (row number from 0, cells) for every row; cells is None for a row that keep(first cells) rejected,
        in which case the rest of the row is not decoded. keep sees the cells of columns 0 to 9."""
        n = -1
        for _, row in etree.iterparse(z.open(target), tag=NS + "row"):
            n = int(row.get("r")) - 1 if row.get("r") else n + 1
            cells, checked, ok = {}, keep is None, True
            for c in row:
                j = _col(c.get("r")) if c.get("r") else len(cells)
                if not checked and j > 9:
                    checked = True
                    if not keep(cells):
                        ok = False
                        break
                t = c.get("t")
                if t == "inlineStr":
                    v = "".join(x.text or "" for x in c.iter(NS + "t"))
                else:
                    ve = c.find(NS + "v")
                    if ve is None or ve.text is None:
                        continue
                    v = ve.text
                    if t == "s":
                        v = ss[int(v)]
                    elif t == "b":
                        v = v == "1"
                    elif t not in ("str", "e"):
                        try:
                            v = float(v)
                        except ValueError:
                            pass
                cells[j] = v
            if ok and not checked and not keep(cells):
                ok = False
            _clear(row)
            yield n, (cells if ok else None)
    return rows


def _dense(cells, width=None):
    if not cells:
        return []
    w = width or max(cells) + 1
    return [cells.get(j, "") for j in range(w)]


def read_lci(path, keys, names, progress=lambda *a: None):
    """The cumulative inventories of the wanted datasets from ecoinvent's cumulative LCI workbook.
    keys: set of 'activity uuid_product uuid'; names: set of (name, location, product) normalised.
    Returns (columns, {row key: {column index: amount}}, number of data rows in the file)."""
    import trust
    if not str(path).lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("Choose the Excel file (.xlsx) with ecoinvent's cumulative LCI.")
    found, all_cols, n_rows = {}, [], 0
    for sname, rows in xlsx_sheets(path):
        buf, h = [], None
        for _n, cells in rows():
            buf.append(cells)
            top = [[trust._clean(v) for v in _dense(c)] for c in buf]
            h = next((i for i, r in enumerate(top) if any(x.lower() in ("activity name", "activity uuid_product uuid",
                                                                         "activity uuid") for x in r)), None)
            if h is not None and len(buf) >= h + 2 and any(isinstance(v, float) for j, v in cells.items() if j > 4):
                break
            if len(buf) >= 25:
                break
        if h is None or not any(buf):
            continue
        width = max(max(c) + 1 for c in buf if c)
        top = [[trust._clean(v) for v in _dense(c, width)] for c in buf]
        ids, data_start, cols = trust._parse_sheet(type("S", (), {"title": sname})(), top, h)
        all_cols += cols
        want = [(c["index"], c["id"]) for c in cols]

        def key_of(cells, ids=ids):
            get = lambda k: trust._clean(cells.get(ids[k], "")) if k in ids else ""
            key = get("key") or (f"{get('act')}_{get('prod')}" if "act" in ids else "")
            return key, (trust._norm(get("name")), trust._norm(get("location")), trust._norm(get("product")))

        def keep(cells):
            k, nm = key_of(cells)
            return bool((k and k in keys) or nm in names)
        target = max(1, len(keys) or len(names))
        for n, cells in rows(keep):
            if n < data_start:
                continue
            n_rows += 1
            if cells is None:
                if n_rows % 2000 == 0:
                    progress(min(95, 100 * len(found) / target),
                             f"Reading ecoinvent's cumulative LCI: {n_rows:,} datasets read, {len(found)} of the compared found")
                continue
            k, nm = key_of(cells)
            vals = found.setdefault(k if k in keys else nm, {})
            for j, cid in want:
                v = cells.get(j)
                if isinstance(v, float):
                    vals[cid] = vals.get(cid, 0.0) + v
                elif isinstance(v, str) and trust._isnum(v):
                    vals[cid] = vals.get(cid, 0.0) + float(v.replace(",", "."))
    if not all_cols:
        raise ValueError("No sheet with an 'Activity Name' or 'Activity UUID_Product UUID' column was found. This does "
                         "not look like ecoinvent's cumulative LCI file.")
    return all_cols, found, n_rows


def match_columns(store, mc, cols):
    """Pair each LCI column with an elementary flow of the matrix: by UUID when the header has one, else by name,
    compartment and subcompartment. Returns {column id: (flow index or None, label)}."""
    import trust
    flows = store.q("SELECT id, uuid, name, compartment, subcompartment, unit FROM flows")
    by_uuid = {f["uuid"]: f for f in flows if f["uuid"]}
    by_name = {}
    for f in flows:
        by_name.setdefault(trust._norm(f["name"]), []).append(f)
    out = {}
    for c in cols:
        labels = [trust._norm(x) for x in c["labels"][:-1]]
        lab = set(labels)
        f = next((by_uuid[x] for x in labels if UUID.match(x) and x in by_uuid), None)
        if f is None:
            cands = [x for lb in labels for x in by_name.get(lb, [])]
            best, score = None, -1
            for x in cands:
                comp, sub = trust._norm(x["compartment"]), trust._norm(x["subcompartment"])
                if comp not in lab and not any(comp in lb for lb in labels if lb != trust._norm(x["name"])):
                    continue
                s = 2 if sub and sub in lab else (1 if not sub else 0)
                if s > score:
                    best, score = x, s
            f = best
        name = " / ".join(x for x in c["labels"][:-1] if not UUID.match(trust._norm(x)))
        idx = mc.flow_index.get(f["id"]) if f else None
        out[c["id"]] = (idx, name, f)
    return out


def _is_land(name):
    n = (name or "").strip().lower()
    return n.startswith("occupation") or n.startswith("transformation")


def inventory_check(store, mc, M, mcols, out, chosen, G, cols, lci_rows, n_file_rows):
    """Split the gap of every compared result into an inventory part and a factor part (see the module docstring),
    and list the flows whose cumulative amounts differ. chosen: [(group, results row, activity)]."""
    import trust
    match = match_columns(store, mc, cols)
    nflow = len(mc.flow_ids)
    names = {}

    def fname(i):
        if i not in names:
            r = store.flow(int(mc.flow_ids[i])) or {}
            names[i] = (r.get("name", ""), "/".join(x for x in (r.get("compartment"), r.get("subcompartment")) if x),
                        r.get("unit", ""), (r.get("compartment") or "").lower())
        return names[i]
    # cumulative inventory of each compared dataset as ecoinvent reports it, in the flow order of the matrix
    E, U, have = {}, {}, []
    for g, r, a in chosen:
        vals = lci_rows.get(r["key"]) if r.get("key") else None
        if vals is None:
            vals = lci_rows.get((trust._norm(r["name"]), trust._norm(r["location"]), trust._norm(r["product"])))
        if vals is None or a["id"] not in G:
            continue
        e = np.zeros(nflow)
        un = {}
        for cid, v in vals.items():
            idx, name, _f = match.get(cid, (None, "", None))
            if idx is None:
                if v:
                    un[name] = un.get(name, 0.0) + v
            else:
                e[idx] += v
        E[a["id"]], U[a["id"]] = e, un
        have.append(a["id"])
    if not have:
        return {"error": "None of the compared datasets was found in the cumulative LCI file. Use the file of the same "
                         "ecoinvent version and system model.", "datasets": 0}
    # sign convention per compartment (ecoinvent may report resources with the opposite sign): from all pairs
    signs, conv = {}, []
    for aid in have:
        gc, ge = G[aid], E[aid]
        nz = np.where((gc != 0) & (ge != 0))[0]
        for i in nz:
            signs.setdefault(fname(i)[3], []).append(ge[i] / gc[i])
    flip = {comp for comp, r in signs.items() if len(r) >= 3 and np.median(r) < 0}
    if flip:
        idx = np.array([i for i in range(nflow) if fname(i)[3] in flip], dtype=int)
        for aid in have:
            E[aid][idx] *= -1
        conv = sorted(flip)
    # per flow: differences of the cumulative amounts
    per = {}
    for aid in have:
        gc, ge = G[aid], E[aid]
        scale = max(np.abs(gc).max(), np.abs(ge).max(), 1e-300)
        d = np.where(np.abs(ge - gc) > np.maximum(1e-3 * np.maximum(np.abs(ge), np.abs(gc)), 1e-12 * scale))[0]
        for i in d:
            p = per.setdefault(int(i), {"datasets": 0, "ratios": [], "only_cyclia": 0, "only_ecoinvent": 0})
            p["datasets"] += 1
            if gc[i] == 0:
                p["only_ecoinvent"] += 1
            elif ge[i] == 0:
                p["only_cyclia"] += 1
            else:
                p["ratios"].append(ge[i] / gc[i])
    flows_diff = []
    for i, p in sorted(per.items(), key=lambda t: -t[1]["datasets"])[:300]:
        nm, comp, unit, _ = fname(i)
        flows_diff.append({"flow": nm, "compartment": comp, "unit": unit, "datasets_differing": p["datasets"],
                           "median_ratio_ecoinvent_to_cyclia": float(np.median(p["ratios"])) if p["ratios"] else None,
                           "only_in_ecoinvent": p["only_ecoinvent"], "only_in_cyclia": p["only_cyclia"]})
    unmatched = {}
    for aid in have:
        for nm, v in U[aid].items():
            unmatched.setdefault(nm, [0, 0.0])
            unmatched[nm][0] += 1
            unmatched[nm][1] += abs(v)
    # gap decomposition per category
    cats = []
    for k, c in enumerate(mcols):
        m = c["method"]
        land = "land" in f"{m['category']} {m['indicator']}".lower()
        items = [x for x in out if x["category"] == m["category"] and x["indicator"] == m["indicator"]
                 and x["act_id"] in E and x["reference"] and x["note"] != "both numerically zero"]
        if not items:
            continue
        Ck = np.asarray(M.C[k]).ravel()
        rows = []
        for x in items:
            he = float(Ck @ E[x["act_id"]])
            rows.append((x, he, he - x["cyclia"], x["reference"] - he))
        dev = [r for r in rows if r[0]["deviation_percent"] is not None and abs(r[0]["deviation_percent"]) > 0.1]
        rel_e = np.array([abs(r[3]) / abs(r[0]["reference"]) * 100 for r in rows])
        entry = {"category": m["category"], "indicator": m["indicator"], "results": len(rows), "deviating": len(dev),
                 "ecoinvent_lci_times_factors_within_0_1": float((rel_e <= 0.1).mean() * 100),
                 "max_dev_ecoinvent_lci_times_factors": float(rel_e.max()) if len(rel_e) else 0.0,
                 "inventory_share": None, "factor_share": None, "cause": "", "inventory_flows": [],
                 "implied_factors": [], "implied_explained": None,
                 "datasets": [{"dataset": r[0]["activity"], "location": r[0]["location"], "ecoinvent": r[0]["reference"],
                               "cyclia": r[0]["cyclia"], "ecoinvent_lci_times_factors": r[1], "inventory_part": r[2],
                               "factor_part": r[3]} for r in sorted(dev, key=lambda r: -abs(r[0]["deviation_percent"]))[:40]]}
        if dev:
            S = sum(abs(r[2] + r[3]) for r in dev)
            sg = [np.sign(r[2] + r[3]) for r in dev]
            inv = sum(s * r[2] for s, r in zip(sg, dev)) / S * 100 if S else 0.0
            fac = sum(s * r[3] for s, r in zip(sg, dev)) / S * 100 if S else 0.0
            entry["inventory_share"], entry["factor_share"] = float(inv), float(fac)
            # flows that carry the inventory part
            contrib = np.zeros(nflow)
            for r in dev:
                x = r[0]
                contrib += np.abs(Ck * (E[x["act_id"]] - G[x["act_id"]])) / abs(x["reference"])
            for i in np.argsort(-contrib)[:10]:
                if contrib[i] <= 0:
                    break
                nm, comp, unit, _ = fname(int(i))
                p = per.get(int(i), {})
                entry["inventory_flows"].append({"flow": nm, "compartment": comp, "unit": unit, "factor": float(Ck[i]),
                                                 "weight": float(contrib[i]), "datasets_differing": p.get("datasets", 0),
                                                 "median_ratio_ecoinvent_to_cyclia":
                                                     float(np.median(p["ratios"])) if p.get("ratios") else None})
            # flows that could carry the factor part: flows of ecoinvent's inventory without a factor in Cyclia
            w = np.array([1.0 / abs(r[0]["reference"]) for r in dev])
            y = np.array([r[3] for r in dev]) * w
            # candidates: land flows for a land use category; otherwise flows whose name the method file knows
            known = {str(x["c_name"]).lower(): abs(x["v"] or 0) or 1.0 for x in store.q(
                "SELECT c_name, MAX(abs(value)) AS v FROM cf_raw WHERE method_id=? GROUP BY c_name", (m["id"],))}
            cand = {}
            for r in dev:
                e = E[r[0]["act_id"]]
                for i in np.where((e != 0) & (Ck == 0))[0]:
                    nm = fname(int(i))[0]
                    if (land and not _is_land(nm)) or (not land and str(mc.flow_cname[i][0]).lower() not in known):
                        continue
                    scale_ = 1.0 if land else known.get(str(mc.flow_cname[i][0]).lower(), 1.0)
                    cand[("f", int(i))] = cand.get(("f", int(i)), 0.0) + abs(e[i]) * scale_ / abs(r[0]["reference"])
                for nm, v in U[r[0]["act_id"]].items():
                    parts = [p_.strip().lower() for p_ in nm.split(" / ")]
                    if (land and not any(_is_land(p_) for p_ in parts)) or (not land and not any(p_ in known for p_ in parts)):
                        continue
                    cand[("u", nm)] = cand.get(("u", nm), 0.0) + abs(v) / abs(r[0]["reference"])
            top = [kk for kk, _ in sorted(cand.items(), key=lambda t: -t[1])[:8]]
            if top and np.any(y) and len(dev) >= 3:
                X = np.array([[E[r[0]["act_id"]][kk[1]] if kk[0] == "f" else U[r[0]["act_id"]].get(kk[1], 0.0)
                               for kk in top] for r in dev]) * w[:, None]
                keep_ = [j for j in range(X.shape[1]) if np.any(X[:, j])]
                if keep_:
                    sol, *_ = np.linalg.lstsq(X[:, keep_], y, rcond=None)
                    fit = X[:, keep_] @ sol
                    entry["implied_explained"] = float(1 - np.sum((y - fit) ** 2) / np.sum(y ** 2)) if np.sum(y ** 2) else None
                    for j, cf in zip(keep_, sol):
                        kk = top[j]
                        if kk[0] == "f":
                            nm, comp, unit, _ = fname(kk[1])
                        else:
                            nm, comp, unit = kk[1], "(not in Cyclia's flows)", ""
                        entry["implied_factors"].append({"flow": nm, "compartment": comp, "unit": unit,
                                                         "implied_factor": float(cf),
                                                         "datasets_with_flow": int(np.count_nonzero(X[:, j]))})
            if inv >= 80:
                entry["cause"] = ("inventory: Cyclia's cumulative inventory differs from ecoinvent's for the flows listed. "
                                  "The factors agree (ecoinvent's inventory with Cyclia's factors gives ecoinvent's "
                                  "results). This is an import or linking difference to fix in Cyclia.")
            elif fac >= 80:
                entry["cause"] = ("factors: Cyclia's inventory equals ecoinvent's, but ecoinvent's own inventory with the "
                                  "factors of its LCIA implementation file does not give ecoinvent's published results. "
                                  "ecoinvent's results use factors that are not in that file (the flows that would need "
                                  "them are listed). Not a calculation error in Cyclia; add factors only from the method's "
                                  "source.")
            else:
                entry["cause"] = (f"both: {inv:.0f} % of the gap comes from the inventory and {fac:.0f} % from factors "
                                  "ecoinvent uses that are not in its LCIA file.")
        cats.append(entry)
    return {"datasets": len(have), "rows_in_file": n_file_rows, "columns_in_file": len(cols),
            "columns_matched": sum(1 for v in match.values() if v[0] is not None),
            "sign_converted": conv, "flows_differing": flows_diff,
            "flows_not_in_cyclia": [{"flow": k, "datasets": v[0], "sum_abs_amount": v[1]}
                                    for k, v in sorted(unmatched.items(), key=lambda t: -t[1][0])[:100]],
            "categories": cats}
