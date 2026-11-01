"""ecoSpold2 importer (ecoinvent 3.x allocated system models: cut-off, APOS, consequential).

Expects the extracted release folder: <folder>/datasets/*.spold.
Activities are keyed by "<activityId>_<referenceProductId>", which is how ecoinvent links inputs
(activityLinkId + intermediateExchangeId). Exchange uncertainty (lognormal, normal, triangular,
uniform, including the pedigree-widened variance) is kept for Monte Carlo.
"""
import math
import os

from lxml import etree

NS = "{http://www.EcoInvent.org/EcoSpold02}"


def _find_datasets(folder, depth=0):
    for cand in (os.path.join(folder, "datasets"), folder):
        if os.path.isdir(cand):
            files = [f for f in os.listdir(cand) if f.lower().endswith(".spold")]
            if files:
                return cand, sorted(files)
    if depth < 2:
        for sub in sorted(os.listdir(folder)):
            p = os.path.join(folder, sub)
            if os.path.isdir(p):
                try:
                    return _find_datasets(p, depth + 1)
                except ValueError:
                    pass
    raise ValueError("No .spold files found. Select the extracted ecoinvent folder that contains 'datasets'.")


def _text(el, path):
    x = el.find(path) if el is not None else None
    return x.text if x is not None and x.text else ""


def _f(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def parse_uncertainty(ex):
    """Return (utype, p1, p2, p3). lognormal: p1=sigma of ln; normal: p1=sd; triangular: min, mode, max;
    uniform: min, max."""
    u = ex.find(NS + "uncertainty")
    if u is None:
        return 0, None, None, None
    ln = u.find(NS + "lognormal")
    if ln is not None:
        var = _f(ln.get("varianceWithPedigreeUncertainty")) or _f(ln.get("variance"))
        if var and var > 0:
            return 1, math.sqrt(var), None, None
    no = u.find(NS + "normal")
    if no is not None:
        var = _f(no.get("varianceWithPedigreeUncertainty")) or _f(no.get("variance"))
        if var and var > 0:
            return 2, math.sqrt(var), None, None
    tr = u.find(NS + "triangular")
    if tr is not None:
        lo, mode, hi = _f(tr.get("minValue")), _f(tr.get("mostLikelyValue")), _f(tr.get("maxValue"))
        if None not in (lo, mode, hi) and lo <= mode <= hi and hi > lo:
            return 3, lo, mode, hi
    un = u.find(NS + "uniform")
    if un is not None:
        lo, hi = _f(un.get("minValue")), _f(un.get("maxValue"))
        if None not in (lo, hi) and hi > lo:
            return 4, lo, hi, None
    return 0, None, None, None


def import_folder(store, folder, name, version="", system_model="", progress=lambda *a: None):
    ds_dir, files = _find_datasets(folder)
    db_id = store.create_database(name, "ecoSpold2", version, system_model)
    try:
        return _import(store, db_id, name, ds_dir, files, progress)
    except Exception:
        store.abort_database(db_id)
        raise


def _import(store, db_id, name, ds_dir, files, progress):
    flow_ids = store.flow_id_map()
    parser = etree.XMLParser(huge_tree=True, remove_comments=True, resolve_entities=False, no_network=True)
    skipped_links = unallocated = bad_files = 0
    c = store.conn
    with store.lock:
        c.execute("DROP TABLE IF EXISTS temp.pending")
        c.execute("CREATE TEMP TABLE pending (output_id INTEGER, link_key TEXT, amount REAL, "
                  "utype INTEGER, p1 REAL, p2 REAL, p3 REAL, p_name TEXT, p_unit TEXT)")
        c.execute("DELETE FROM pending")
        batch_bio, batch_pending = [], []
        total = len(files)
        for n, fname in enumerate(files):
            try:
                root = etree.parse(os.path.join(ds_dir, fname), parser).getroot()
            except etree.XMLSyntaxError:
                bad_files += 1
                continue
            ds = root.find(NS + "activityDataset")
            if ds is None:
                ds = root.find(NS + "childActivityDataset")
            if ds is None:
                bad_files += 1
                continue
            act = ds.find(f"{NS}activityDescription/{NS}activity")
            if act is None:
                bad_files += 1
                continue
            act_id = act.get("id")
            act_name = _text(act, NS + "activityName")
            loc = _text(ds, f"{NS}activityDescription/{NS}geography/{NS}shortname")
            comment = " ".join(t.text or "" for t in act.findall(f"{NS}generalComment/{NS}text"))[:3000]
            flow_data = ds.find(NS + "flowData")
            if flow_data is None:
                continue
            ref, refs = None, 0
            for ex in flow_data.iter(NS + "intermediateExchange"):
                if _text(ex, NS + "outputGroup") == "0" and _f(ex.get("amount"), 0) != 0:
                    refs += 1
                    if ref is None:
                        ref = ex
            if ref is None:
                continue
            if refs > 1:
                unallocated += 1
            key = f"{act_id}_{ref.get('intermediateExchangeId')}"
            cur = c.execute(
                "INSERT OR IGNORE INTO activities(db_id,key,name,product,location,unit,production,comment,product_uuid) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (db_id, key, act_name, _text(ref, NS + "name"), loc, _text(ref, NS + "unitName"),
                 _f(ref.get("amount"), 1.0), comment, ref.get("intermediateExchangeId")))
            if cur.rowcount == 0:
                continue
            out_id = cur.lastrowid
            for ex in flow_data.iter(NS + "intermediateExchange"):
                if ex is ref or _text(ex, NS + "inputGroup") == "":
                    continue
                amt = _f(ex.get("amount"), 0.0)
                if amt == 0:
                    continue
                link = ex.get("activityLinkId")
                if not link:
                    skipped_links += 1
                    continue
                batch_pending.append((out_id, f"{link}_{ex.get('intermediateExchangeId')}", amt) + parse_uncertainty(ex)
                                     + (_text(ex, NS + "name"), _text(ex, NS + "unitName")))
            for ex in flow_data.iter(NS + "elementaryExchange"):
                amt = _f(ex.get("amount"), 0.0)
                if amt == 0:
                    continue
                fuuid = ex.get("elementaryExchangeId")
                fid = flow_ids.get(fuuid)
                if fid is None:
                    comp = ex.find(NS + "compartment")
                    fid = store.add_flow(fuuid, _text(ex, NS + "name"), _text(comp, NS + "compartment"),
                                         _text(comp, NS + "subcompartment"), _text(ex, NS + "unitName"),
                                         ex.get("casNumber", ""))
                    flow_ids[fuuid] = fid
                batch_bio.append((out_id, fid, amt) + parse_uncertainty(ex))
            if len(batch_bio) > 50000 or len(batch_pending) > 50000:
                c.executemany("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", batch_bio)
                c.executemany("INSERT INTO pending VALUES(?,?,?,?,?,?,?,?,?)", batch_pending)
                batch_bio, batch_pending = [], []
            if n % 200 == 0:
                progress(int(88 * n / max(total, 1)), f"Reading datasets {n:,}/{total:,}")
        c.executemany("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)", batch_bio)
        c.executemany("INSERT INTO pending VALUES(?,?,?,?,?,?,?,?,?)", batch_pending)
        progress(90, "Linking supply chains")
        c.execute("CREATE INDEX IF NOT EXISTS temp.idx_pending ON pending(link_key)")
        c.execute("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) "
                  "SELECT p.output_id, a.id, p.amount, p.utype, p.p1, p.p2, p.p3 FROM pending p "
                  "JOIN activities a ON a.db_id=? AND a.key=p.link_key", (db_id,))
        c.execute("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3) "
                  "SELECT ?, p.output_id, p.p_name, p.p_unit, p.amount, '', p.link_key, p.utype, p.p1, p.p2, p.p3 "
                  "FROM pending p WHERE NOT EXISTS (SELECT 1 FROM activities a WHERE a.db_id=? AND a.key=p.link_key)",
                  (db_id, db_id))
        unresolved = c.execute("SELECT COUNT(*) FROM unlinked WHERE db_id=?", (db_id,)).fetchone()[0]
        c.execute("DROP TABLE IF EXISTS temp.pending")
        c.commit()
    progress(96, "Building search index")
    store.finish_database(db_id)
    from importers import lcia
    lcia.rematch_all(store)
    n_act = store.one("SELECT n_activities FROM databases WHERE id=?", (db_id,))["n_activities"]
    warnings = []
    if unresolved:
        warnings.append(f"{unresolved} inputs point to datasets that are not in this folder. Link them under "
                        "'Link missing suppliers' so the supply chains are complete.")
    if skipped_links:
        warnings.append(f"{skipped_links} inputs had no supplier link; they were left out.")
    if unallocated:
        warnings.append(f"{unallocated} datasets have several co-products. Use an allocated system model "
                        "(cut-off, APOS or consequential), not the 'undefined' unit processes.")
    if bad_files:
        warnings.append(f"{bad_files} files could not be read and were skipped.")
    return {"database": name, "activities": n_act, "warnings": warnings}
