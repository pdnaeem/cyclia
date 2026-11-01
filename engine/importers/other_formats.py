"""Importers for ecoSpold1 (XML), SimaPro CSV and ILCD process datasets.

All three link technosphere inputs to producers in the same import by product (ecoSpold1, SimaPro: name,
location and unit; ILCD: flow UUID). Inputs without a producer are kept as 'unlinked' for cross-database
linking. Elementary flows without a UUID (ecoSpold1, SimaPro) get a stable key from their canonical name
and compartment, so the same flow from two such databases is one flow in the library.
"""
import csv
import hashlib
import io
import math
import os
import re
import zipfile

from lxml import etree

from canon import canon
from importers import lcia

PARSER = etree.XMLParser(huge_tree=True, remove_comments=True, resolve_entities=False, no_network=True)


def _f(v, default=None):
    try:
        x = float(str(v).strip().replace(",", ".")) if isinstance(v, str) else float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def flow_key(prefix, name, comp, sub, unit):
    c = canon(name, comp, sub)
    return f"{prefix}:" + hashlib.sha1("|".join(c + ((unit or "").lower(),)).encode()).hexdigest()[:24]


class _Builder:
    """Collects activities and exchanges, links them, and writes them to the library in one go."""

    def __init__(self, store, name, source, version="", system_model=""):
        self.store = store
        self.db_id = store.create_database(name, source, version, system_model)
        self.name = name
        self.acts = []      # (key, name, product, location, unit, production, comment)
        self.tech = []      # (act index, link product key, amount, unc, product, unit, location)
        self.bio = []       # (act index, flow uuid, name, comp, sub, unit, amount, unc)
        self.by_product = {}
        self.skipped = 0

    def activity(self, key, name, product, location, unit, production=1.0, comment=""):
        self.acts.append((key, name, product, location or "", unit or "", production or 1.0, comment or ""))
        i = len(self.acts) - 1
        for k in self._product_keys(product, location, unit):
            self.by_product.setdefault(k, i)
        return i

    @staticmethod
    def _product_keys(product, location, unit):
        p = (product or "").strip().lower()
        return [(p, (location or "").upper(), (unit or "").lower()), (p, "", (unit or "").lower()), (p, "", "")]

    def input(self, ai, product, unit, amount, location="", unc=(0, None, None, None), link=None):
        self.tech.append((ai, link, amount, unc, product, unit, location))

    def emission(self, ai, uuid, name, comp, sub, unit, amount, unc=(0, None, None, None)):
        self.bio.append((ai, uuid, name, comp, sub, unit, amount, unc))

    def write(self, progress):
        st, c = self.store, self.store.conn
        try:
            with st.lock:
                ids = []
                for key, name, product, loc, unit, prod, comment in self.acts:
                    cur = c.execute("INSERT OR IGNORE INTO activities(db_id,key,name,product,location,unit,production,comment) "
                                    "VALUES(?,?,?,?,?,?,?,?)", (self.db_id, key, name, product, loc, unit, prod, comment[:3000]))
                    ids.append(cur.lastrowid if cur.rowcount else c.execute(
                        "SELECT id FROM activities WHERE db_id=? AND key=?", (self.db_id, key)).fetchone()[0])
                progress(70, "Linking supply chains")
                tech, unlinked = [], []
                for ai, link, amount, unc, product, unit, loc in self.tech:
                    target = link if isinstance(link, int) else None
                    if target is None:
                        for k in self._product_keys(product, loc, unit):
                            if k in self.by_product:
                                target = self.by_product[k]
                                break
                    if target is None:
                        unlinked.append((self.db_id, ids[ai], product, unit, amount, loc or "", None) + tuple(unc))
                    else:
                        tech.append((ids[ai], ids[target], amount) + tuple(unc))
                c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", tech)
                c.executemany("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3) "
                              "VALUES(?,?,?,?,?,?,?,?,?,?,?)", unlinked)
                bio = []
                for ai, uuid, name, comp, sub, unit, amount, unc in self.bio:
                    fid = st.add_flow(uuid, name, comp, sub, unit)
                    bio.append((ids[ai], fid, amount) + tuple(unc))
                c.executemany("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", bio)
                c.commit()
            progress(90, "Building search index")
            st.finish_database(self.db_id)
            lcia.rematch_all(st)
        except Exception:
            st.abort_database(self.db_id)
            raise
        warnings = []
        if unlinked:
            warnings.append(f"{len(unlinked)} inputs ({len({u[2] for u in unlinked})} products) have no producer in this "
                            "import. Link them under 'Link missing suppliers'.")
        if self.skipped:
            warnings.append(f"{self.skipped} exchanges could not be read (non-numeric amounts or formulas) and were skipped.")
        return {"database": self.name, "activities": len(ids), "warnings": warnings}


# ------------------------------------------------------------------------------------------- ecoSpold1
NS1 = "{http://www.EcoInvent.org/EcoSpold01}"


def _es1_unc(ex, amount):
    t = ex.get("uncertaintyType")
    sd95 = _f(ex.get("standardDeviation95"))
    if t == "1" and sd95 and sd95 > 1:
        return (1, 0.5 * math.log(sd95), None, None)  # SD95 = GSD^2
    if t == "2" and sd95 and sd95 > 0:
        return (2, sd95 / 2.0, None, None)
    lo, mode, hi = _f(ex.get("minValue")), _f(ex.get("mostLikelyValue"), amount), _f(ex.get("maxValue"))
    if t == "3" and None not in (lo, hi) and lo <= mode <= hi and hi > lo:
        return (3, lo, mode, hi)
    if t == "4" and None not in (lo, hi) and hi > lo:
        return (4, lo, hi, None)
    return (0, None, None, None)


def import_ecospold1(store, path, name, progress=lambda *a: None):
    files = []
    if os.path.isdir(path):
        for d, _, fs in os.walk(path):
            files += [os.path.join(d, f) for f in fs if f.lower().endswith(".xml")]
    elif os.path.isfile(path):
        files = [path]
    if not files:
        raise ValueError("No ecoSpold1 .xml files found.")
    b = _Builder(store, name, "ecoSpold1")
    pending = []
    for n, fpath in enumerate(sorted(files)):
        try:
            root = etree.parse(fpath, PARSER).getroot()
        except etree.XMLSyntaxError:
            b.skipped += 1
            continue
        for ds in root.iter(NS1 + "dataset"):
            ref = ds.find(f".//{NS1}referenceFunction")
            geo = ds.find(f".//{NS1}geography")
            if ref is None:
                continue
            loc = geo.get("location", "") if geo is not None else ""
            exs = ds.findall(f".//{NS1}exchange")
            out_ref = next((e for e in exs if (e.findtext(NS1 + "outputGroup") or "").strip() == "0"), None)
            amount = _f(out_ref.get("meanValue"), 1.0) if out_ref is not None else _f(ref.get("amount"), 1.0)
            ai = b.activity(f"{ds.get('number', '')}_{ref.get('name')}_{loc}", ref.get("name"), ref.get("name"), loc,
                            ref.get("unit"), amount or 1.0, ref.get("generalComment", ""))
            pending.append((ai, exs, out_ref))
        if n % 50 == 0:
            progress(int(50 * n / len(files)), f"Reading files {n:,}/{len(files):,}")
    for ai, exs, out_ref in pending:
        for e in exs:
            if e is out_ref:
                continue
            ig, og = (e.findtext(NS1 + "inputGroup") or "").strip(), (e.findtext(NS1 + "outputGroup") or "").strip()
            amt = _f(e.get("meanValue"))
            if amt is None:
                b.skipped += 1
                continue
            if amt == 0:
                continue
            unc = _es1_unc(e, amt)
            if ig == "5":
                b.input(ai, e.get("name"), e.get("unit"), amt, e.get("location", ""), unc)
            elif ig == "4" or og == "4":
                comp = "natural resource" if ig == "4" else (e.get("category") or "")
                uuid = flow_key("es1", e.get("name"), comp, e.get("subCategory", ""), e.get("unit"))
                b.emission(ai, uuid, e.get("name"), comp, e.get("subCategory", ""), e.get("unit"), amt, unc)
    return b.write(progress)


# ------------------------------------------------------------------------------------------- SimaPro CSV
SP_ELEM = {"resources": "natural resource", "emissions to air": "air", "emissions to water": "water",
           "emissions to soil": "soil"}
SP_TECH = {"materials/fuels", "electricity/heat", "waste to treatment"}
SP_SKIP = {"final waste flows", "non material emissions", "social issues", "economic issues", "input parameters",
           "calculated parameters", "avoided products", "known outputs to technosphere. avoided products"}


def _sp_unc(kind, v1, v2, v3, amount):
    k = (kind or "").strip().lower()
    a, lo, hi = _f(v1), _f(v2), _f(v3)
    if k == "lognormal" and a and a > 1:
        return (1, 0.5 * math.log(a), None, None)  # SimaPro stores the squared geometric SD
    if k == "normal" and a and a > 0:
        return (2, a / 2.0, None, None)
    if k == "triangle" and None not in (lo, hi) and lo <= amount <= hi and hi > lo:
        return (3, lo, amount, hi)
    if k == "uniform" and None not in (lo, hi) and hi > lo:
        return (4, lo, hi, None)
    return (0, None, None, None)


def import_simapro_csv(store, path, name, progress=lambda *a: None):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    head = text[:3000]
    if "SimaPro" not in head:
        raise ValueError("This does not look like a SimaPro CSV export (the header line must mention SimaPro).")
    delim = ";" if "Separator: Semicolon" in head or "separator: Semicolon" in head.lower() or head.count(";") > head.count(",") else ","
    if "{CSV separator: Tab}" in head:
        delim = "\t"
    comma_decimal = "Decimal separator: ," in head
    num = lambda v: _f(str(v).replace(",", ".") if comma_decimal else v)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    b = _Builder(store, name, "SimaPro CSV")
    i, n = 0, len(rows)
    processes = 0
    while i < n:
        if rows[i] and rows[i][0].strip() == "Process":
            block = []
            i += 1
            while i < n and not (rows[i] and rows[i][0].strip() == "End"):
                block.append(rows[i])
                i += 1
            _sp_process(b, block, num)
            processes += 1
            if processes % 200 == 0:
                progress(min(60, processes // 50), f"Reading processes ({processes:,})")
        i += 1
    if not b.acts:
        raise ValueError("No processes were found in the SimaPro file.")
    return b.write(progress)


def _sp_process(b, block, num):
    sections, cur = {}, None
    for r in block:
        cells = [c.strip() for c in r]
        if not any(cells):
            cur = None
            continue
        if len([c for c in cells if c]) == 1 and cur is None:
            cur = cells[0].lower()
            sections[cur] = []
            continue
        if cur is not None:
            sections[cur].append(cells)
    geo = (sections.get("geography") or [[""]])[0][0]
    comment = " ".join(x[0] for x in sections.get("comment", []) if x)
    products = sections.get("products") or []
    waste = sections.get("waste treatment") or []
    refs = []
    for p in products:
        if len(p) >= 3:
            amt = num(p[2])
            share = (num(p[3]) if len(p) > 3 and p[3] else 100.0) or 100.0
            refs.append((p[0], p[1], amt, share / 100.0, 1.0))
    for w in waste:
        if len(w) >= 3:
            refs.append((w[0], w[1], num(w[2]), 1.0, -1.0))
    if not refs:
        return
    for prod_name, unit, amt, share, sign in refs:
        if not amt:
            continue
        ai = b.activity(f"{prod_name}|{geo}", prod_name, prod_name, geo, unit, sign * amt, comment)
        for sec, rws in sections.items():
            if sec in SP_TECH:
                for r in rws:
                    if len(r) < 3:
                        continue
                    a = num(r[2])
                    if a is None:
                        b.skipped += 1
                        continue
                    if a == 0:
                        continue
                    unc = _sp_unc(r[3] if len(r) > 3 else "", *(r[4:7] + [""] * 3)[:3], a)
                    a2 = a * share
                    unc = _scale_unc(unc, share)
                    if sec == "waste to treatment":
                        a2, unc = -a2, _neg_unc(unc)
                    b.input(ai, r[0], r[1], a2, "", unc)
            elif sec in SP_ELEM:
                for r in rws:
                    if len(r) < 4:
                        continue
                    a = num(r[3])
                    if a is None:
                        b.skipped += 1
                        continue
                    if a == 0:
                        continue
                    unc = _scale_unc(_sp_unc(r[4] if len(r) > 4 else "", *(r[5:8] + [""] * 3)[:3], a), share)
                    comp = SP_ELEM[sec]
                    b.emission(ai, flow_key("sp", r[0], comp, r[1], r[2]), r[0], comp, r[1], r[2], a * share, unc)


def _scale_unc(unc, f):
    if unc[0] in (2,):
        return (2, unc[1] * f, None, None)
    if unc[0] in (3, 4):
        return (unc[0],) + tuple(v * f if v is not None else None for v in unc[1:])
    return unc


def _neg_unc(unc):
    if unc[0] in (3, 4):
        vals = sorted(-v for v in unc[1:] if v is not None)
        return (unc[0],) + tuple(vals) + ((None,) if unc[0] == 4 else ())
    return unc


# ------------------------------------------------------------------------------------------- ILCD
NSP, NSC = "{http://lca.jrc.it/ILCD/Process}", "{http://lca.jrc.it/ILCD/Common}"
NSF, NSFP, NSU = "{http://lca.jrc.it/ILCD/Flow}", "{http://lca.jrc.it/ILCD/FlowProperty}", "{http://lca.jrc.it/ILCD/UnitGroup}"


class _Files:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path) if zipfile.is_zipfile(path) else None
        if self.zip:
            self.names = self.zip.namelist()
        elif os.path.isdir(path):
            self.names = []
            for d, _, fs in os.walk(path):
                self.names += [os.path.relpath(os.path.join(d, f), path).replace(os.sep, "/") for f in fs]
        else:
            raise ValueError("Choose an ILCD .zip file or its extracted folder.")
        self.root = path

    def kind(self, folder):
        return [n for n in self.names if f"/{folder}/" in "/" + n.lower() and n.lower().endswith(".xml")]

    def parse(self, name):
        try:
            data = self.zip.read(name) if self.zip else open(os.path.join(self.root, name), "rb").read()
            return etree.fromstring(data, PARSER)
        except (etree.XMLSyntaxError, KeyError, OSError):
            return None


def _lang_text(el, path):
    x = el.find(path)
    if x is None:
        return ""
    return (x.text or "").strip()


def import_ilcd(store, path, name, progress=lambda *a: None):
    files = _Files(path)
    procs = files.kind("processes")
    if not procs:
        raise ValueError("No 'processes' folder in this ILCD package.")
    progress(3, "Reading units and flows")
    ug_unit = {}
    for n in files.kind("unitgroups"):
        r = files.parse(n)
        if r is None:
            continue
        uid = _lang_text(r, f".//{NSC}UUID")
        ref = _lang_text(r, f".//{NSU}referenceToReferenceUnit")
        for u in r.iter(NSU + "unit"):
            if u.get("dataSetInternalID") == ref:
                ug_unit[uid] = _lang_text(u, NSU + "name")
    fp_unit = {}
    for n in files.kind("flowproperties"):
        r = files.parse(n)
        if r is None:
            continue
        ref = r.find(f".//{NSFP}referenceToReferenceUnitGroup")
        fp_unit[_lang_text(r, f".//{NSC}UUID")] = ug_unit.get(ref.get("refObjectId") if ref is not None else "", "")
    flows = {}
    for n in files.kind("flows"):
        r = files.parse(n)
        if r is None:
            continue
        uid = _lang_text(r, f".//{NSC}UUID")
        fname = _lang_text(r, f".//{NSF}baseName")
        ftype = _lang_text(r, f".//{NSF}typeOfDataSet")
        cats = [c.text or "" for c in r.iter(NSC + "category")]
        ref_prop = _lang_text(r, f".//{NSF}referenceToReferenceFlowProperty")
        unit = ""
        for fp in r.iter(NSF + "flowProperty"):
            if fp.get("dataSetInternalID") == ref_prop:
                rr = fp.find(NSF + "referenceToFlowPropertyDataSet")
                unit = fp_unit.get(rr.get("refObjectId") if rr is not None else "", "")
        flows[uid] = {"name": fname, "type": ftype, "comp": cats[0] if cats else "",
                      "sub": "/".join(cats[1:]), "unit": unit}
    b = _Builder(store, name, "ILCD")
    loaded, ref_flow_owner = [], {}
    for k, n in enumerate(procs):
        r = files.parse(n)
        if r is None:
            b.skipped += 1
            continue
        pname = ", ".join(x for x in (_lang_text(r, f".//{NSP}baseName"), _lang_text(r, f".//{NSP}treatmentStandardsRoutes"),
                                      _lang_text(r, f".//{NSP}mixAndLocationTypes")) if x)
        loc_el = r.find(f".//{NSP}locationOfOperationSupplyOrProduction")
        loc = loc_el.get("location", "") if loc_el is not None else ""
        ref_ids = [x.text for x in r.iter(NSP + "referenceToReferenceFlow")]
        exs = list(r.iter(NSP + "exchange"))
        ref = next((e for e in exs if e.get("dataSetInternalID") in ref_ids), None)
        if ref is None:
            continue
        fr = ref.find(NSP + "referenceToFlowDataSet")
        fuid = fr.get("refObjectId") if fr is not None else ""
        fl = flows.get(fuid, {"name": _lang_text(fr, NSC + "shortDescription") if fr is not None else "", "unit": ""})
        amt = _f(_lang_text(ref, NSP + "resultingAmount")) or _f(_lang_text(ref, NSP + "meanAmount"), 1.0)
        direction = _lang_text(ref, NSP + "exchangeDirection")
        ai = b.activity(_lang_text(r, f".//{NSC}UUID") or pname, pname or fl["name"], fl["name"], loc, fl["unit"],
                        (-amt if direction == "Input" else amt) or 1.0, "")
        ref_flow_owner.setdefault(fuid, ai)
        loaded.append((ai, exs, ref))
        if k % 100 == 0:
            progress(5 + int(55 * k / len(procs)), f"Reading processes {k:,}/{len(procs):,}")
    for ai, exs, ref in loaded:
        for e in exs:
            if e is ref:
                continue
            fr = e.find(NSP + "referenceToFlowDataSet")
            fuid = fr.get("refObjectId") if fr is not None else ""
            fl = flows.get(fuid)
            amt = _f(_lang_text(e, NSP + "resultingAmount"))
            if amt is None:
                amt = _f(_lang_text(e, NSP + "meanAmount"))
            if amt is None or fl is None:
                b.skipped += 1
                continue
            if amt == 0:
                continue
            is_input = _lang_text(e, NSP + "exchangeDirection") == "Input"
            rsd = _f(_lang_text(e, NSP + "relativeStandardDeviation95In"))
            unc = (0, None, None, None)
            if _lang_text(e, NSP + "uncertaintyDistributionType") == "log-normal" and rsd and rsd > 1:
                unc = (1, 0.5 * math.log(rsd), None, None) if rsd < 50 else (1, 0.5 * math.log(1 + rsd / 100.0), None, None)
            if "elementary" in fl["type"].lower():
                b.emission(ai, fuid, fl["name"], fl["comp"], fl["sub"], fl["unit"], amt, unc)
                continue
            waste = "waste" in fl["type"].lower()
            if (not waste and not is_input) or (waste and is_input):
                continue  # co-products
            target = ref_flow_owner.get(fuid)
            b.input(ai, fl["name"], fl["unit"], amt if not waste else -amt, "", unc, link=target)
    return b.write(progress)
