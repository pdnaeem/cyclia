"""Staging imports (Cyclia 1.3.7, checks extended in 1.3.8): a database is imported into a separate staging library first, checked there, and
only then merged into the user's library in one transaction.

1. A temporary workspace with its own library.db is created next to the user's data folder.
2. The importer runs against it (the user's library is not touched while the import runs).
3. Checks on the staging library (integrity()): at least one dataset; finite amounts of technosphere, elementary
   and unresolved inputs; finite uncertainty parameters and known uncertainty types; finite, nonzero production;
   no link to a dataset or flow that does not exist; a solvable matrix (random solves reproduce the demand). Any failure stops here; the user's library is
   unchanged and the staging folder is deleted.
4. Merge in one SQLite transaction: the database row, its datasets (ids shifted), exchanges, elementary flows (joined
   by UUID with the flows already in the library), unresolved inputs (with their candidates), dataset data quality
   and impact methods that are new to the library (their factors are matched again against the whole library).
   On any error the transaction is rolled back.
"""
import json
import os
import shutil
import tempfile

import numpy as np

import calc
from store import Workspace


def _bad(col, nullable=False):
    """SQL condition: not a finite number (NaN is stored as NULL by SQLite, Infinity as a REAL above 1e308)."""
    cond = f"{col} != {col} OR abs({col}) > 1e300"
    return f"({cond})" if nullable else f"({col} IS NULL OR {cond})"


def integrity(store, db_id=None):
    """Counts of every problem that makes data unusable, for one database (db_id) or the whole store:
    non-finite amounts (technosphere, elementary, unresolved inputs), non-finite uncertainty parameters, zero or
    non-finite production, unknown uncertainty types, and references to datasets or flows that do not exist."""
    acts = "SELECT id FROM activities" + (" WHERE db_id=?" if db_id else "")
    a = (db_id,) if db_id else ()
    n = {}
    unc = " OR ".join(_bad(f"x.{p}", True) for p in ("p1", "p2", "p3"))
    n["technosphere amounts"] = store.one(f"SELECT COUNT(*) AS n FROM tech x WHERE x.output_id IN ({acts}) AND {_bad('x.amount')}", a)["n"]
    n["elementary amounts"] = store.one(f"SELECT COUNT(*) AS n FROM bio x WHERE x.activity_id IN ({acts}) AND {_bad('x.amount')}", a)["n"]
    n["unresolved input amounts"] = store.one(f"SELECT COUNT(*) AS n FROM unlinked x WHERE x.output_id IN ({acts}) AND {_bad('x.amount')}", a)["n"]
    n["uncertainty parameters"] = sum(store.one(f"SELECT COUNT(*) AS n FROM {t} x WHERE x.{c} IN ({acts}) AND ({unc})", a)["n"]
                                      for t, c in (("tech", "output_id"), ("bio", "activity_id"), ("unlinked", "output_id")))
    n["uncertainty types"] = sum(store.one(f"SELECT COUNT(*) AS n FROM {t} x WHERE x.{c} IN ({acts}) AND "
                                           "COALESCE(x.utype,0) NOT IN (0,1,2,3,4)", a)["n"]
                                 for t, c in (("tech", "output_id"), ("bio", "activity_id"), ("unlinked", "output_id")))
    n["production amounts"] = store.one("SELECT COUNT(*) AS n FROM activities x WHERE " + ("x.db_id=? AND " if db_id else "")
                                        + f"({_bad('x.production')} OR x.production = 0)", a)["n"]
    n["links to missing datasets"] = store.one(f"SELECT COUNT(*) AS n FROM tech x WHERE x.output_id IN ({acts}) AND "
                                               "x.input_id NOT IN (SELECT id FROM activities)", a)["n"]
    n["links to missing flows"] = store.one(f"SELECT COUNT(*) AS n FROM bio x WHERE x.activity_id IN ({acts}) AND "
                                            "x.flow_id NOT IN (SELECT id FROM flows)", a)["n"]
    n["unresolved inputs of missing datasets"] = store.one("SELECT COUNT(*) AS n FROM unlinked x WHERE "
                                                           + ("x.db_id=? AND " if db_id else "")
                                                           + "x.output_id NOT IN (SELECT id FROM activities)", a)["n"]
    return {k: v for k, v in n.items() if v}


CHECKS = ["at least one dataset", "finite technosphere, elementary and unresolved-input amounts",
          "finite uncertainty parameters and known uncertainty types", "finite, nonzero production amounts",
          "no link to a missing dataset or flow", "solvable matrix (10 random unit demands reproduced)"]


def counts(store):
    """What the staged import contains, for the import report."""
    one = lambda sql: store.one(sql)["n"]
    return {"datasets": one("SELECT COUNT(*) AS n FROM activities"),
            "technosphere exchanges": one("SELECT COUNT(*) AS n FROM tech"),
            "elementary exchanges": one("SELECT COUNT(*) AS n FROM bio"),
            "elementary flows": one("SELECT COUNT(*) AS n FROM flows"),
            "unresolved inputs": one("SELECT COUNT(*) AS n FROM unlinked WHERE linked_to IS NULL"),
            "exchanges with uncertainty": one("SELECT (SELECT COUNT(*) FROM tech WHERE COALESCE(utype,0)>0)"
                                              " + (SELECT COUNT(*) FROM bio WHERE COALESCE(utype,0)>0) AS n")}


def check(store, report=None):
    """Problems that block the merge (empty list when the staged database may be merged). When report is a dict,
    the counts, the checks run and the matrix residual are written into it."""
    problems = []
    if report is not None:
        report.update({"checks": CHECKS, "contents": counts(store)})
    n = store.one("SELECT COUNT(*) AS n FROM activities")["n"]
    if not n:
        problems.append("no datasets were imported")
        return problems
    problems += [f"{v} {k} not valid" for k, v in integrity(store).items()]
    try:
        calc.invalidate()
        mc = calc.get_mc(store)
        rng = np.random.default_rng(1)
        worst = 0.0
        for j in rng.choice(mc.n, size=min(10, mc.n), replace=False):
            f = np.zeros(mc.n)
            f[j] = 1.0
            s = mc.solve(f)
            worst = max(worst, float(np.linalg.norm(mc.A @ s - f)))
        if report is not None:
            report["matrix_residual"] = float(worst)
        if not np.isfinite(worst) or worst > 1e-6:
            problems.append(f"the matrix cannot be solved reliably (residual {worst:.1e})")
    except Exception as e:  # singular matrix and the like
        problems.append(f"the matrix cannot be solved ({e})")
    finally:
        calc.invalidate()
    return problems


def merge(stage_lib, store):
    """Merge every database of the staging library into the store's library. Returns the new database ids."""
    c = store.conn
    new_ids = []
    with store.lock:
        c.execute("ATTACH DATABASE ? AS stg", (stage_lib,))
        try:
            c.execute("BEGIN")
            off = (c.execute("SELECT MAX(id) FROM lib.activities").fetchone()[0] or 0)
            off = max(off, 0)
            # flows: joined by UUID, new ones added
            c.execute("INSERT OR IGNORE INTO lib.flows(uuid,name,compartment,subcompartment,unit,cas,c_name,c_comp,c_sub) "
                      "SELECT uuid,name,compartment,subcompartment,unit,cas,c_name,c_comp,c_sub FROM stg.flows")
            c.execute("DROP TABLE IF EXISTS temp.fmap")
            c.execute("CREATE TEMP TABLE fmap AS SELECT s.id AS sid, m.id AS mid FROM stg.flows s JOIN lib.flows m ON m.uuid=s.uuid")
            c.execute("CREATE INDEX temp.idx_fmap ON fmap(sid)")
            for d in c.execute("SELECT * FROM stg.databases").fetchall():
                d = dict(d)
                if c.execute("SELECT 1 FROM lib.databases WHERE name=?", (d["name"],)).fetchone():
                    raise ValueError(f"A database called '{d['name']}' is already in the library.")
                cols = [k for k in d if k != "id"]
                cur = c.execute(f"INSERT INTO lib.databases({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                                [d[k] for k in cols])
                nid = cur.lastrowid
                new_ids.append(nid)
                c.execute("INSERT INTO lib.activities(id,db_id,key,name,product,location,unit,production,comment,product_uuid) "
                          "SELECT id+?, ?, key,name,product,location,unit,production,comment,product_uuid FROM stg.activities "
                          "WHERE db_id=?", (off, nid, d["id"]))
            c.execute("INSERT INTO lib.tech(output_id,input_id,amount,utype,p1,p2,p3,src_unlinked) "
                      "SELECT output_id+?, input_id+?, amount,utype,p1,p2,p3,NULL FROM stg.tech", (off, off))
            c.execute("INSERT INTO lib.bio(activity_id,flow_id,amount,utype,p1,p2,p3) "
                      "SELECT b.activity_id+?, f.mid, b.amount,b.utype,b.p1,b.p2,b.p3 FROM stg.bio b JOIN temp.fmap f ON f.sid=b.flow_id",
                      (off,))
            dbmap = {}
            for d in c.execute("SELECT id, name FROM stg.databases").fetchall():
                dbmap[d["id"]] = c.execute("SELECT id FROM lib.databases WHERE name=?", (d["name"],)).fetchone()[0]
            for u in c.execute("SELECT * FROM stg.unlinked").fetchall():
                u = dict(u)
                cand = json.dumps([x + off for x in json.loads(u["candidates"])]) if u.get("candidates") else None
                c.execute("INSERT INTO lib.unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3,linked_to,"
                          "reason,candidates) VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)",
                          (dbmap[u["db_id"]], u["output_id"] + off, u["product"], u["unit"], u["amount"], u["location"],
                           u["link_key"], u["utype"], u["p1"], u["p2"], u["p3"], u.get("reason") or "no producer", cand))
            c.execute("INSERT OR REPLACE INTO lib.activity_dq SELECT activity_id+?, ter,ger,tir,p,completeness,methodological,"
                      "overall,source FROM stg.activity_dq", (off,))
            # impact methods new to the library (built-in methods already present are kept as they are)
            for m in c.execute("SELECT * FROM stg.methods").fetchall():
                m = dict(m)
                if c.execute("SELECT 1 FROM lib.methods WHERE family=? AND category=? AND indicator=?",
                             (m["family"], m["category"], m["indicator"])).fetchone():
                    continue
                cur = c.execute("INSERT INTO lib.methods(family,category,indicator,unit,source,note) VALUES(?,?,?,?,?,?)",
                                (m["family"], m["category"], m["indicator"], m["unit"], m["source"], m["note"]))
                mid = cur.lastrowid
                c.execute("INSERT INTO lib.cf_raw(method_id,c_name,c_comp,c_sub,location,flow_uuid,value) "
                          "SELECT ?, c_name,c_comp,c_sub,location,flow_uuid,value FROM stg.cf_raw WHERE method_id=?", (mid, m["id"]))
                c.execute("INSERT OR IGNORE INTO lib.nw(method_id,set_name,normalisation,weighting) "
                          "SELECT ?, set_name,normalisation,weighting FROM stg.nw WHERE method_id=?", (mid, m["id"]))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.execute("DROP TABLE IF EXISTS temp.fmap")
            c.execute("DETACH DATABASE stg")
        c.execute("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
        store._bump_lib()
        c.commit()
    from importers import lcia
    lcia.rematch_all(store)
    calc.invalidate()
    return new_ids


def staged(store, data_dir, run, progress=lambda *a: None):
    """Run an importer (run(stage_store, progress) -> result dict) in a staging library, check it, merge it."""
    root = tempfile.mkdtemp(prefix="cyclia-staging-", dir=data_dir if data_dir and os.path.isdir(data_dir) else None)
    ws = Workspace(root)
    try:
        st = ws.create("staging")
        res = run(st, lambda pc, msg="": progress(min(80, pc * 0.8), msg))
        progress(82, "Checking the imported database before it enters the library")
        report = {}
        problems = check(st, report)
        if problems:
            raise ValueError("The import was stopped before it reached your library: " + "; ".join(problems) + ".")
        ws.close_all()
        progress(88, "Adding the checked database to the library")
        ids = merge(ws.library_path, store)
        if isinstance(res, dict):
            res["staged"] = True
            res["staging_checks"] = "passed: " + "; ".join(CHECKS)
            report["result"] = "passed"
            res["integrity_report"] = report
            res["database_ids"] = ids
        return res
    finally:
        try:
            ws.close_all()
        except Exception:
            pass
        shutil.rmtree(root, ignore_errors=True)
