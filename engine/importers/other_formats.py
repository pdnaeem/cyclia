"""Importers for ecoSpold1 (XML), SimaPro CSV and ILCD process datasets.

All three link technosphere inputs to producers in the same import by product (ecoSpold1, SimaPro: name,
location and unit; ILCD: flow UUID). Inputs without a producer are kept as 'unlinked' for cross-database
linking. Elementary flows without a UUID (ecoSpold1, SimaPro) get a stable key from their canonical name
and compartment, so the same flow from two such databases is one flow in the library.
"""
import csv
import json
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
    """Writes an import to the library as it is read (Cyclia 1.3.8): every dataset is inserted when it is read and
    elementary exchanges are written in batches, so the file and its parsed form are never held in memory as a whole.
    Technosphere inputs are kept until the end in compact form, because a supplier can only be chosen once every
    dataset of the import is known. Everything is one transaction: a failure removes the whole database."""

    BATCH = 20000

    def __init__(self, store, name, source, version="", system_model=""):
        self.store = store
        self.db_id = store.create_database(name, source, version, system_model)
        self.name = name
        self.ids = []       # library id of every dataset, by the index the importer uses
        self.tech = []      # (act index, link, amount, unc, product, unit, location)
        self.bio = []       # buffer: (act index, flow uuid, name, comp, sub, unit, amount, unc)
        self.n_bio = 0
        self._fid = {}      # flow uuid -> flow id
        self.by_product = {}  # product key -> every activity index that produces it
        self.keys = {}
        self.duplicates = []  # processes that came with the same identity as an earlier one: kept separate
        self.skipped = 0

    @property
    def acts(self):
        """Kept for callers that only test whether datasets were read."""
        return self.ids

    def activity(self, key, name, product, location, unit, production=1.0, comment=""):
        if key in self.keys:
            n = 2
            while f"{key}#{n}" in self.keys:
                n += 1
            self.duplicates.append({"key": key, "name": name, "location": location or "", "kept_as": f"{key}#{n}"})
            key = f"{key}#{n}"
        with self.store.lock:
            cur = self.store.conn.execute(
                "INSERT INTO activities(db_id,key,name,product,location,unit,production,comment) VALUES(?,?,?,?,?,?,?,?)",
                (self.db_id, key, name, product, location or "", unit or "", production or 1.0, (comment or "")[:3000]))
        self.ids.append(cur.lastrowid)
        i = len(self.ids) - 1
        self.keys[key] = i
        for k in self._product_keys(product, location, unit):
            lst = self.by_product.setdefault(k, [])
            if i not in lst:
                lst.append(i)
        return i

    @staticmethod
    def _product_keys(product, location, unit):
        p = (product or "").strip().lower()
        return [(p, (location or "").upper(), (unit or "").lower()), (p, "", (unit or "").lower()), (p, "", "")]

    def input(self, ai, product, unit, amount, location="", unc=(0, None, None, None), link=None):
        self.tech.append((ai, link, amount, tuple(unc), product, unit, location))

    def emission(self, ai, uuid, name, comp, sub, unit, amount, unc=(0, None, None, None)):
        self.bio.append((ai, uuid, name, comp, sub, unit, amount, tuple(unc)))
        if len(self.bio) >= self.BATCH:
            self._flush_bio()

    def _flush_bio(self):
        if not self.bio:
            return
        st = self.store
        rows = []
        with st.lock:
            for ai, uuid, name, comp, sub, unit, amount, unc in self.bio:
                fid = self._fid.get(uuid)
                if fid is None:
                    fid = self._fid[uuid] = st.add_flow(uuid, name, comp, sub, unit)
                rows.append((self.ids[ai], fid, amount) + unc)
            st.conn.executemany("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", rows)
        self.n_bio += len(rows)
        self.bio = []

    def abort(self):
        self.store.abort_database(self.db_id)

    def resolve(self, product, unit, loc):
        """The producer of an input: the most specific product key (product, location, unit; then product and unit;
        then product) that has producers. One producer: linked. Several: ambiguous, never guessed."""
        if loc:
            keys = self._product_keys(product, loc, unit)
        else:
            keys = self._product_keys(product, "", unit)[1:]
        for k in keys:
            c = self.by_product.get(k)
            if c:
                return (c[0], "", []) if len(c) == 1 else (None, "ambiguous", c)
        return None, "no producer", []

    def write(self, progress):
        st, c = self.store, self.store.conn
        ids = self.ids
        try:
            with st.lock:
                self._flush_bio()
                progress(70, "Linking supply chains")
                tech, unlinked = [], []
                n_amb = 0
                n_unl = 0
                products = set()
                for ai, link, amount, unc, product, unit, loc in self.tech:
                    target = link if isinstance(link, int) else None
                    reason, cands = "", []
                    if target is None:
                        target, reason, cands = self.resolve(product, unit, loc)
                    if target is None:
                        n_amb += reason == "ambiguous"
                        n_unl += 1
                        products.add(product)
                        unlinked.append((self.db_id, ids[ai], product, unit, amount, loc or "", None) + unc
                                        + (reason or "no producer", json.dumps([ids[x] for x in cands]) if cands else None))
                    else:
                        tech.append((ids[ai], ids[target], amount) + unc)
                    if len(tech) >= self.BATCH:
                        c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", tech)
                        tech = []
                c.executemany("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", tech)
                c.executemany("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3,"
                              "reason,candidates) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", unlinked)
                self.tech = []
                c.commit()
            progress(90, "Building search index")
            st.finish_database(self.db_id)
            lcia.rematch_all(st)
        except Exception:
            self.abort()
            raise
        warnings = []
        if n_unl:
            warnings.append(f"{n_unl} inputs ({len(products)} products) have no single producer in "
                            f"this import ({n_amb} of them because several datasets produce the same product: Cyclia does "
                            "not guess). Link them under 'Link missing suppliers'.")
        if self.duplicates:
            warnings.append(f"{len(self.duplicates)} processes had the same identity as an earlier process (for example "
                            f"'{self.duplicates[0]['key']}'). They were kept as separate datasets, not merged.")
        if self.skipped:
            warnings.append(f"{self.skipped} exchanges could not be read (non-numeric amounts or formulas) and were skipped.")
        return {"database": self.name, "activities": len(ids), "warnings": warnings, "unlinked_inputs": n_unl,
                "ambiguous_inputs": n_amb, "duplicates": self.duplicates[:50], "n_duplicates": len(self.duplicates),
                "skipped_exchanges": self.skipped, "elementary_exchanges": self.n_bio}


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
    try:
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
                _es1_exchanges(b, ai, exs, out_ref)
            del root
            if n % 50 == 0:
                progress(int(50 * n / len(files)), f"Reading files {n:,}/{len(files):,}")
    except Exception:
        b.abort()
        raise
    return b.write(progress)


def _es1_exchanges(b, ai, exs, out_ref):
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


def _sp_encoding(path):
    """The text encoding of a SimaPro export, found by reading the file in chunks (never the whole file at once)."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                while fh.read(1 << 20):
                    pass
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _sp_blocks(fh, delim):
    """Process blocks of a SimaPro CSV export, read row by row: only one process is in memory at a time."""
    block = None
    for r in csv.reader(fh, delimiter=delim):
        first = r[0].strip() if r else ""
        if block is None:
            if first == "Process":
                block = []
        elif first == "End":
            yield block
            block = None
        else:
            block.append(r)


def import_simapro_csv(store, path, name, progress=lambda *a: None):
    enc = _sp_encoding(path)
    with open(path, encoding=enc, newline="") as fh:
        head = fh.read(3000)
    if "SimaPro" not in head:
        raise ValueError("This does not look like a SimaPro CSV export (the header line must mention SimaPro).")
    delim = ";" if "Separator: Semicolon" in head or "separator: Semicolon" in head.lower() or head.count(";") > head.count(",") else ","
    if "{CSV separator: Tab}" in head:
        delim = "\t"
    comma_decimal = "Decimal separator: ," in head
    num = lambda v: _f(str(v).replace(",", ".") if comma_decimal else v)
    size = max(1, os.path.getsize(path))
    b = _Builder(store, name, "SimaPro CSV")
    processes = 0
    try:
        with open(path, encoding=enc, newline="") as fh:
            for block in _sp_blocks(fh, delim):
                _sp_process(b, block, num)
                processes += 1
                if processes % 200 == 0:
                    try:
                        pos = fh.buffer.tell()
                    except (AttributeError, OSError):
                        pos = 0
                    progress(min(60, int(60 * pos / size)), f"Reading processes ({processes:,})")
    except Exception:
        b.abort()
        raise
    if not b.ids:
        b.abort()
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
    # identity of the process: SimaPro's process identifier, else the process name (never product + location alone,
    # which merged two routes of the same product)
    ident = ((sections.get("process identifier") or [[""]])[0] or [""])[0] or \
        ((sections.get("process name") or [[""]])[0] or [""])[0]
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
        key = f"{ident}|{prod_name}|{geo}" if ident else f"{prod_name}|{geo}"
        ai = b.activity(key, prod_name, prod_name, geo, unit, sign * amt, comment)
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
    ref_flow_owner = {}
    dq_rows = {}
    pending = []   # (index in b.tech, flow uuid): suppliers are set once every reference flow is known
    try:
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
            dq = dataset_dqr(r)
            if dq:
                dq_rows[_lang_text(r, f".//{NSC}UUID") or pname] = dq
            ref_flow_owner.setdefault(fuid, ai)
            _ilcd_exchanges(b, ai, exs, ref, flows, pending)
            del r, exs
            if k % 100 == 0:
                progress(5 + int(55 * k / len(procs)), f"Reading processes {k:,}/{len(procs):,}")
    except Exception:
        b.abort()
        raise
    for idx, fuid in pending:
        t = b.tech[idx]
        b.tech[idx] = (t[0], ref_flow_owner.get(fuid)) + t[2:]
    res = b.write(progress)
    if dq_rows:
        with store.lock:
            for key, dq in dq_rows.items():
                row = store.conn.execute("SELECT id FROM activities WHERE db_id=? AND key=?", (b.db_id, key)).fetchone()
                if row:
                    store.conn.execute("INSERT OR REPLACE INTO activity_dq VALUES(?,?,?,?,?,?,?,?,?)",
                                       (row[0], dq.get("TeR"), dq.get("GeR"), dq.get("TiR"), dq.get("P"), dq.get("C"),
                                        dq.get("M"), dq.get("overall", ""), "ILCD dataQualityIndicators"))
            store.conn.commit()
        if isinstance(res, dict):
            res["datasets_with_dqr"] = len(dq_rows)
    return res


def _ilcd_exchanges(b, ai, exs, ref, flows, pending):
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
        pending.append((len(b.tech), fuid))
        b.input(ai, fl["name"], fl["unit"], amt if not waste else -amt, "", unc)


DQ_LEVELS = {"very good": 1.0, "good": 2.0, "fair": 3.0, "poor": 4.0, "very poor": 5.0}
DQ_NAMES = {"technological representativeness": "TeR", "geographical representativeness": "GeR",
            "time representativeness": "TiR", "precision": "P", "completeness": "C",
            "methodological appropriateness and consistency": "M", "overall quality": "overall"}


def dataset_dqr(root):
    """Data quality indicators of an ILCD/EF process dataset (common:dataQualityIndicator name/value), as numbers
    1 (very good) to 5 (very poor). Numeric values are kept; 'not evaluated' and 'not applicable' are skipped."""
    out = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag != "dataQualityIndicator":
            continue
        name = (el.get("name") or "").strip().lower()
        val = (el.get("value") or "").strip()
        key = DQ_NAMES.get(name)
        if not key:
            continue
        if key == "overall":
            out["overall"] = val
            continue
        num = DQ_LEVELS.get(val.lower())
        if num is None:
            try:
                num = float(val)
            except ValueError:
                continue
        if 1 <= num <= 5:
            out[key] = num
    return out if any(k in out for k in ("TeR", "GeR", "TiR", "P")) else {}
