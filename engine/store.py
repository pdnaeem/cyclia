"""Storage.

library.db  (one per computer) : databases, datasets, elementary flows, impact methods, mappings.
<name>.lca  (one per project)   : models, inputs, parameters, scenarios, undo history.

The library is ATTACHed to every project connection as schema 'lib'. SQLite resolves unqualified
table names in 'main' first and then in attached schemas, so data tables are written unqualified.
Model inputs keep the database name and dataset key next to the numeric id, so a project file can be
opened on another computer and relinked to the same databases there.
"""
import json
import os
import re
import shutil
import sqlite3
import threading
import time

from canon import canon

SCHEMA_VERSION = 4

LIB_SCHEMA = """
CREATE TABLE IF NOT EXISTS lib.lmeta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS lib.databases (
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, source TEXT, version TEXT, system_model TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP, n_activities INTEGER DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS lib.activities (
    id INTEGER PRIMARY KEY, db_id INTEGER, key TEXT, name TEXT, product TEXT, location TEXT, unit TEXT,
    production REAL DEFAULT 1.0, comment TEXT, product_uuid TEXT, UNIQUE(db_id, key));
CREATE INDEX IF NOT EXISTS lib.idx_act_db ON activities(db_id);
CREATE INDEX IF NOT EXISTS lib.idx_act_product ON activities(product);
CREATE VIRTUAL TABLE IF NOT EXISTS lib.activities_fts USING fts5(name, product, location, content='activities', content_rowid='id');
CREATE TABLE IF NOT EXISTS lib.tech (output_id INTEGER, input_id INTEGER, amount REAL,
    utype INTEGER DEFAULT 0, p1 REAL, p2 REAL, p3 REAL, src_unlinked INTEGER);
CREATE INDEX IF NOT EXISTS lib.idx_tech_out ON tech(output_id);
CREATE INDEX IF NOT EXISTS lib.idx_tech_in ON tech(input_id);
CREATE TABLE IF NOT EXISTS lib.flows (
    id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, name TEXT, compartment TEXT, subcompartment TEXT, unit TEXT,
    cas TEXT, c_name TEXT, c_comp TEXT, c_sub TEXT);
CREATE INDEX IF NOT EXISTS lib.idx_flow_name ON flows(name);
CREATE INDEX IF NOT EXISTS lib.idx_flow_canon ON flows(c_name, c_comp, c_sub);
CREATE TABLE IF NOT EXISTS lib.bio (activity_id INTEGER, flow_id INTEGER, amount REAL,
    utype INTEGER DEFAULT 0, p1 REAL, p2 REAL, p3 REAL);
CREATE INDEX IF NOT EXISTS lib.idx_bio_act ON bio(activity_id);
CREATE TABLE IF NOT EXISTS lib.methods (
    id INTEGER PRIMARY KEY, family TEXT, category TEXT, indicator TEXT, unit TEXT, source TEXT, note TEXT,
    UNIQUE(family, category, indicator));
CREATE TABLE IF NOT EXISTS lib.cfs (method_id INTEGER, flow_id INTEGER, value REAL, PRIMARY KEY(method_id, flow_id));
CREATE TABLE IF NOT EXISTS lib.cfs_regional (method_id INTEGER, flow_id INTEGER, location TEXT, value REAL,
    PRIMARY KEY(method_id, flow_id, location));
CREATE TABLE IF NOT EXISTS lib.cf_raw (method_id INTEGER, c_name TEXT, c_comp TEXT, c_sub TEXT, location TEXT,
    flow_uuid TEXT, value REAL);
CREATE INDEX IF NOT EXISTS lib.idx_cfraw ON cf_raw(c_name);
CREATE TABLE IF NOT EXISTS lib.nw (method_id INTEGER, set_name TEXT, normalisation REAL, weighting REAL,
    PRIMARY KEY(method_id, set_name));
CREATE TABLE IF NOT EXISTS lib.flow_mapping (id INTEGER PRIMARY KEY, source TEXT, s_name TEXT, s_comp TEXT,
    s_sub TEXT, s_uuid TEXT, t_name TEXT, t_comp TEXT, t_sub TEXT, t_uuid TEXT, factor REAL DEFAULT 1.0);
CREATE TABLE IF NOT EXISTS lib.unlinked (id INTEGER PRIMARY KEY, db_id INTEGER, output_id INTEGER, product TEXT,
    unit TEXT, amount REAL, location TEXT, link_key TEXT, utype INTEGER DEFAULT 0, p1 REAL, p2 REAL, p3 REAL,
    linked_to INTEGER);
CREATE INDEX IF NOT EXISTS lib.idx_unlinked_db ON unlinked(db_id, product);
CREATE TABLE IF NOT EXISTS lib.templates (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, description TEXT,
    spec TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS lib.chemicals (id INTEGER PRIMARY KEY, name TEXT UNIQUE, cas TEXT, props TEXT, result TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY, name TEXT, product TEXT, unit TEXT, amount REAL DEFAULT 1.0,
    scope TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS model_inputs (
    id INTEGER PRIMARY KEY, model_id INTEGER, kind TEXT, ref_id INTEGER, amount REAL,
    label TEXT, comment TEXT, pedigree TEXT DEFAULT '[3,3,3,3,3]', position INTEGER DEFAULT 0,
    stage TEXT DEFAULT '', input_amount REAL, input_unit TEXT, avoided INTEGER DEFAULT 0,
    ref_db TEXT, ref_key TEXT, formula TEXT, year REAL DEFAULT 0, fixed TEXT, data_type TEXT DEFAULT '',
    source_ref TEXT DEFAULT '', data_year REAL, supplier TEXT DEFAULT '', verified INTEGER DEFAULT 0, unit_cost REAL, pef TEXT);
CREATE INDEX IF NOT EXISTS idx_inputs_model ON model_inputs(model_id);
CREATE TABLE IF NOT EXISTS parameters (
    id INTEGER PRIMARY KEY, model_id INTEGER, name TEXT, value REAL, formula TEXT, unit TEXT, comment TEXT,
    utype INTEGER DEFAULT 0, p1 REAL, p2 REAL, p3 REAL);
CREATE TABLE IF NOT EXISTS scenarios (id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT,
    overrides TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, model_id INTEGER, ts REAL, label TEXT, snapshot TEXT);
CREATE TABLE IF NOT EXISTS site_cfs (id INTEGER PRIMARY KEY, family TEXT, category TEXT, indicator TEXT, flow_uuid TEXT,
    flow_name TEXT, value REAL, note TEXT);
CREATE TABLE IF NOT EXISTS bg_scenarios (id INTEGER PRIMARY KEY, name TEXT UNIQUE, kind TEXT DEFAULT 'prospective',
    description TEXT, base_year REAL DEFAULT 2020, rules TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, model_id INTEGER, input_id INTEGER, author TEXT, text TEXT,
    ts REAL, resolved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, model_id INTEGER, name TEXT, author TEXT, ts REAL, snapshot TEXT);
"""

PROJECT_MIGRATIONS = {
    "model_inputs": [("stage", "TEXT DEFAULT ''"), ("input_amount", "REAL"), ("input_unit", "TEXT"),
                     ("avoided", "INTEGER DEFAULT 0"), ("ref_db", "TEXT"), ("ref_key", "TEXT"),
                     ("formula", "TEXT"), ("year", "REAL DEFAULT 0"), ("fixed", "TEXT"),
                     ("data_type", "TEXT DEFAULT ''"), ("source_ref", "TEXT DEFAULT ''"), ("data_year", "REAL"),
                     ("supplier", "TEXT DEFAULT ''"), ("verified", "INTEGER DEFAULT 0"), ("unit_cost", "REAL"), ("pef", "TEXT")],
}
LIB_MIGRATIONS = {"tech": [("src_unlinked", "INTEGER")], "flow_mapping": [("s_uuid", "TEXT")],
                  "activities": [("product_uuid", "TEXT")]}
LEGACY_DATA_TABLES = ["databases", "activities", "activities_fts", "tech", "flows", "bio", "methods", "cfs", "nw"]
INPUT_COLUMNS = ["id", "model_id", "kind", "ref_id", "amount", "label", "comment", "pedigree", "position", "stage",
                 "input_amount", "input_unit", "avoided", "ref_db", "ref_key", "formula", "year", "fixed", "data_type",
                 "source_ref", "data_year", "supplier", "verified", "unit_cost", "pef"]
UNCERTAINTY_TYPES = {0: "none", 1: "lognormal", 2: "normal", 3: "triangular", 4: "uniform"}


def _cols(conn, schema, table):
    return {r[1] for r in conn.execute(f"PRAGMA {schema}.table_info({table})")}


def _tables(conn, schema):
    return {r[0] for r in conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")}


class ProjectStore:
    def __init__(self, path, library_path):
        self.path = path
        self.library_path = library_path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("ATTACH DATABASE ? AS lib", (library_path,))
        self.conn.execute("PRAGMA lib.journal_mode=WAL")
        self._migrate()

    # ---------------------------------------------------------------- schema
    def _migrate(self):
        with self.lock:
            c = self.conn
            main_tables = _tables(c, "main")
            for table, cols in PROJECT_MIGRATIONS.items():
                if table in main_tables:
                    have = _cols(c, "main", table)
                    for col, decl in cols:
                        if col not in have:
                            c.execute(f"ALTER TABLE main.{table} ADD COLUMN {col} {decl}")
            lib_tables = _tables(c, "lib")
            for table, cols in LIB_MIGRATIONS.items():
                if table in lib_tables:
                    have = _cols(c, "lib", table)
                    for col, decl in cols:
                        if col not in have:
                            c.execute(f"ALTER TABLE lib.{table} ADD COLUMN {col} {decl}")
            c.executescript(LIB_SCHEMA)
            c.executescript(PROJECT_SCHEMA)
            c.commit()
            if "activities" in main_tables:
                self._move_legacy_data()
            c.execute("INSERT OR REPLACE INTO main.meta(key,value) VALUES('schema_version', ?)", (json.dumps(SCHEMA_VERSION),))
            c.commit()
        self.relink()
        self._refresh_matching()

    MATCH_RULES = "3"  # bump when the factor-matching rules in importers/lcia.py change

    def _refresh_matching(self):
        """Re-apply the factor-matching rules once after an update that changed them."""
        try:
            r = self.one("SELECT value FROM lib.lmeta WHERE key='match_rules'")
            if r and r["value"] == self.MATCH_RULES:
                return
            if self.one("SELECT 1 FROM lib.cf_raw LIMIT 1"):
                from importers import lcia
                with self.lock:  # rebuild from scratch so factors added by older rules disappear
                    self.conn.execute("DELETE FROM lib.cfs WHERE method_id IN (SELECT DISTINCT method_id FROM lib.cf_raw)")
                    self.conn.execute("DELETE FROM lib.cfs_regional WHERE method_id IN (SELECT DISTINCT method_id FROM lib.cf_raw)")
                    self.conn.commit()
                lcia.rematch_all(self)
            with self.lock:
                self.conn.execute("INSERT OR REPLACE INTO lib.lmeta(key,value) VALUES('match_rules', ?)", (self.MATCH_RULES,))
                self.conn.commit()
        except Exception:
            pass  # never block opening a project; the next import rematches anyway

    def _move_legacy_data(self):
        """Version 1/2 project files held their own databases. Move them into the shared library."""
        c = self.conn
        for t in ("tech", "bio"):
            if "utype" not in _cols(c, "main", t):
                for col, decl in (("utype", "INTEGER DEFAULT 0"), ("p1", "REAL"), ("p2", "REAL"), ("p3", "REAL")):
                    c.execute(f"ALTER TABLE main.{t} ADD COLUMN {col} {decl}")
        act_map, flow_map, method_map = {}, {}, {}
        for f in c.execute("SELECT * FROM main.flows").fetchall():
            cn = canon(f["name"], f["compartment"], f["subcompartment"])
            c.execute("INSERT OR IGNORE INTO lib.flows(uuid,name,compartment,subcompartment,unit,cas,c_name,c_comp,c_sub) "
                      "VALUES(?,?,?,?,?,?,?,?,?)", (f["uuid"], f["name"], f["compartment"], f["subcompartment"],
                                                    f["unit"], f["cas"], *cn))
            flow_map[f["id"]] = c.execute("SELECT id FROM lib.flows WHERE uuid=?", (f["uuid"],)).fetchone()[0]
        for d in c.execute("SELECT * FROM main.databases").fetchall():
            existing = c.execute("SELECT id FROM lib.databases WHERE name=?", (d["name"],)).fetchone()
            if existing:
                new_db = existing[0]
                copy = False
            else:
                new_db = c.execute("INSERT INTO lib.databases(name,source,version,system_model,n_activities,note) "
                                   "VALUES(?,?,?,?,?,?)", (d["name"], d["source"], d["version"], d["system_model"],
                                                           d["n_activities"], d["note"])).lastrowid
                copy = True
            rows = c.execute("SELECT * FROM main.activities WHERE db_id=?", (d["id"],)).fetchall()
            for a in rows:
                if copy:
                    c.execute("INSERT OR IGNORE INTO lib.activities(db_id,key,name,product,location,unit,production,comment) "
                              "VALUES(?,?,?,?,?,?,?,?)", (new_db, a["key"], a["name"], a["product"], a["location"],
                                                          a["unit"], a["production"], a["comment"]))
                r = c.execute("SELECT id FROM lib.activities WHERE db_id=? AND key=?", (new_db, a["key"])).fetchone()
                if r:
                    act_map[a["id"]] = r[0]
            if copy:
                ids = [a["id"] for a in rows]
                for chunk in range(0, len(ids), 500):
                    part = ids[chunk:chunk + 500]
                    q = ",".join("?" * len(part))
                    c.executemany("INSERT INTO lib.tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                                  [(act_map[t["output_id"]], act_map[t["input_id"]], t["amount"], t["utype"], t["p1"],
                                    t["p2"], t["p3"]) for t in c.execute(f"SELECT * FROM main.tech WHERE output_id IN ({q})", part)
                                   if t["output_id"] in act_map and t["input_id"] in act_map])
                    c.executemany("INSERT INTO lib.bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                                  [(act_map[b["activity_id"]], flow_map[b["flow_id"]], b["amount"], b["utype"], b["p1"],
                                    b["p2"], b["p3"]) for b in c.execute(f"SELECT * FROM main.bio WHERE activity_id IN ({q})", part)
                                   if b["activity_id"] in act_map and b["flow_id"] in flow_map])
        for m in c.execute("SELECT * FROM main.methods").fetchall():
            r = c.execute("SELECT id FROM lib.methods WHERE family=? AND category=? AND indicator=?",
                          (m["family"], m["category"], m["indicator"])).fetchone()
            if r:
                method_map[m["id"]] = r[0]
                continue
            method_map[m["id"]] = c.execute("INSERT INTO lib.methods(family,category,indicator,unit,source) VALUES(?,?,?,?,?)",
                                            (m["family"], m["category"], m["indicator"], m["unit"], m["source"])).lastrowid
            c.executemany("INSERT OR IGNORE INTO lib.cfs VALUES(?,?,?)",
                          [(method_map[m["id"]], flow_map[x["flow_id"]], x["value"])
                           for x in c.execute("SELECT * FROM main.cfs WHERE method_id=?", (m["id"],)) if x["flow_id"] in flow_map])
            if "nw" in _tables(c, "main"):
                c.executemany("INSERT OR IGNORE INTO lib.nw VALUES(?,?,?,?)",
                              [(method_map[m["id"]], x["set_name"], x["normalisation"], x["weighting"])
                               for x in c.execute("SELECT * FROM main.nw WHERE method_id=?", (m["id"],))])
        for i in c.execute("SELECT id, kind, ref_id FROM main.model_inputs").fetchall():
            if i["kind"] == "activity" and i["ref_id"] in act_map:
                new = act_map[i["ref_id"]]
                a = c.execute("SELECT a.key, d.name FROM lib.activities a JOIN lib.databases d ON d.id=a.db_id WHERE a.id=?", (new,)).fetchone()
                c.execute("UPDATE main.model_inputs SET ref_id=?, ref_key=?, ref_db=? WHERE id=?", (new, a[0], a[1], i["id"]))
            elif i["kind"] == "flow" and i["ref_id"] in flow_map:
                new = flow_map[i["ref_id"]]
                u = c.execute("SELECT uuid FROM lib.flows WHERE id=?", (new,)).fetchone()[0]
                c.execute("UPDATE main.model_inputs SET ref_id=?, ref_key=? WHERE id=?", (new, u, i["id"]))
        for t in LEGACY_DATA_TABLES:
            c.execute(f"DROP TABLE IF EXISTS main.{t}")
        c.commit()
        c.execute("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
        self._bump_lib()
        c.commit()

    def relink(self):
        """Point model inputs at the right library rows, using database name + dataset key."""
        changed = 0
        with self.lock:
            c = self.conn
            for i in c.execute("SELECT id, kind, ref_id, ref_db, ref_key FROM main.model_inputs "
                               "WHERE kind IN ('activity','flow')").fetchall():
                if i["kind"] == "activity":
                    cur = c.execute("SELECT a.id, a.key, d.name FROM activities a JOIN databases d ON d.id=a.db_id "
                                    "WHERE a.id=?", (i["ref_id"],)).fetchone()
                    if cur and (not i["ref_key"] or (cur["key"] == i["ref_key"] and cur["name"] == i["ref_db"])):
                        if not i["ref_key"]:
                            c.execute("UPDATE main.model_inputs SET ref_key=?, ref_db=? WHERE id=?", (cur["key"], cur["name"], i["id"]))
                        continue
                    if i["ref_key"]:
                        hit = c.execute("SELECT a.id FROM activities a JOIN databases d ON d.id=a.db_id "
                                        "WHERE d.name=? AND a.key=?", (i["ref_db"], i["ref_key"])).fetchone()
                        new = hit[0] if hit else None
                        if new != i["ref_id"]:
                            c.execute("UPDATE main.model_inputs SET ref_id=? WHERE id=?", (new, i["id"]))
                            changed += 1
                else:
                    cur = c.execute("SELECT id, uuid FROM flows WHERE id=?", (i["ref_id"],)).fetchone()
                    if cur and (not i["ref_key"] or cur["uuid"] == i["ref_key"]):
                        if not i["ref_key"]:
                            c.execute("UPDATE main.model_inputs SET ref_key=? WHERE id=?", (cur["uuid"], i["id"]))
                        continue
                    if i["ref_key"]:
                        hit = c.execute("SELECT id FROM flows WHERE uuid=?", (i["ref_key"],)).fetchone()
                        new = hit[0] if hit else None
                        if new != i["ref_id"]:
                            c.execute("UPDATE main.model_inputs SET ref_id=? WHERE id=?", (new, i["id"]))
                            changed += 1
            c.commit()
        return changed

    def close(self):
        with self.lock:
            self.conn.close()

    # ---------------------------------------------------------------- helpers
    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def get_meta(self, key, default=None):
        r = self.one("SELECT value FROM main.meta WHERE key=?", (key,))
        return json.loads(r["value"]) if r else default

    def set_meta(self, key, value):
        self.x("INSERT OR REPLACE INTO main.meta(key,value) VALUES(?,?)", (key, json.dumps(value)))

    def lib_version(self):
        r = self.one("SELECT value FROM lib.lmeta WHERE key='data_version'")
        return json.loads(r["value"]) if r else 0

    def _bump_lib(self):
        v = self.lib_version() + 1
        self.conn.execute("INSERT OR REPLACE INTO lib.lmeta(key,value) VALUES('data_version', ?)", (json.dumps(v),))

    def bump_version(self):
        with self.lock:
            self._bump_lib()
            self.conn.commit()

    # ---------------------------------------------------------------- databases
    def databases(self):
        rows = self.q("SELECT * FROM databases ORDER BY id")
        for r in rows:
            r["has_uncertainty"] = bool(self.one(
                "SELECT 1 AS x FROM tech t JOIN activities a ON a.id=t.output_id WHERE a.db_id=? AND t.utype>0 LIMIT 1",
                (r["id"],)))
            r["n_unlinked"] = self.one("SELECT COUNT(DISTINCT product) AS n FROM unlinked WHERE db_id=? AND linked_to IS NULL",
                                       (r["id"],))["n"]
        return rows

    def create_database(self, name, source, version="", system_model="", note=""):
        name = (name or "").strip()
        if not name:
            raise ValueError("Give the database a name.")
        if self.one("SELECT id FROM databases WHERE name=?", (name,)):
            raise ValueError(f"A database called '{name}' is already in the library. Use another name or remove it first.")
        return self.x("INSERT INTO databases(name,source,version,system_model,note) VALUES(?,?,?,?,?)",
                      (name, source, version, system_model, note))

    def finish_database(self, db_id):
        with self.lock:
            n = self.conn.execute("SELECT COUNT(*) FROM activities WHERE db_id=?", (db_id,)).fetchone()[0]
            if n == 0:
                self.conn.execute("DELETE FROM databases WHERE id=?", (db_id,))
                self.conn.commit()
                raise ValueError("No usable datasets were found, so nothing was imported.")
            self.conn.execute("UPDATE databases SET n_activities=? WHERE id=?", (n, db_id))
            self.conn.execute("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
            self._bump_lib()
            self.conn.commit()

    def _purge_db(self, db_id):
        ids = "SELECT id FROM activities WHERE db_id=?"
        c = self.conn
        c.execute(f"DELETE FROM tech WHERE output_id IN ({ids})", (db_id,))
        c.execute(f"DELETE FROM tech WHERE input_id IN ({ids})", (db_id,))
        c.execute(f"UPDATE unlinked SET linked_to=NULL WHERE linked_to IN ({ids})", (db_id,))
        c.execute(f"DELETE FROM bio WHERE activity_id IN ({ids})", (db_id,))
        c.execute("DELETE FROM unlinked WHERE db_id=?", (db_id,))
        c.execute("DELETE FROM activities WHERE db_id=?", (db_id,))
        c.execute("DELETE FROM databases WHERE id=?", (db_id,))

    def abort_database(self, db_id):
        with self.lock:
            self.conn.rollback()
            self._purge_db(db_id)
            self._bump_lib()
            self.conn.commit()

    def delete_database(self, db_id):
        with self.lock:
            self._purge_db(db_id)
            self.conn.execute("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
            self._bump_lib()
            self.conn.commit()

    def flow_id_map(self):
        return {r["uuid"]: r["id"] for r in self.q("SELECT id, uuid FROM flows")}

    def add_flow(self, uuid, name, comp, sub, unit, cas=""):
        """Insert an elementary flow if new; returns its id. Caller holds the lock and commits."""
        c = self.conn
        cn = canon(name, comp, sub)
        c.execute("INSERT OR IGNORE INTO flows(uuid,name,compartment,subcompartment,unit,cas,c_name,c_comp,c_sub) "
                  "VALUES(?,?,?,?,?,?,?,?,?)", (uuid, name, comp, sub, unit, cas or "", *cn))
        return c.execute("SELECT id FROM flows WHERE uuid=?", (uuid,)).fetchone()[0]

    # ---------------------------------------------------------------- search
    def search_activities(self, text, db_id=None, location=None, limit=60):
        tokens = [t for t in re.findall(r"[\w\-\.]+", (text or "").lower()) if t]
        if not tokens:
            return []
        fts = " AND ".join('"%s"*' % t.replace('"', "") for t in tokens)
        sql = ("SELECT a.id, a.name, a.product, a.location, a.unit, d.name AS db, d.system_model "
               "FROM activities_fts f JOIN activities a ON a.id=f.rowid "
               "JOIN databases d ON d.id=a.db_id WHERE activities_fts MATCH ?")
        args = [fts]
        if db_id:
            sql += " AND a.db_id=?"
            args.append(db_id)
        sql += " LIMIT 500"
        try:
            rows = self.q(sql, args)
        except sqlite3.OperationalError:
            return []
        want_loc = (location or "").strip().upper()

        def score(r):
            s = 0
            name = (r["name"] or "").lower()
            prod = (r["product"] or "").lower()
            for t in tokens:
                if t in prod:
                    s += 3
                if re.search(r"\b" + re.escape(t), name):
                    s += 2
            if name.startswith("market for"):
                s += 2
            loc = (r["location"] or "").upper()
            if want_loc and loc == want_loc:
                s += 4
            elif loc in ("GLO", "ROW", "RER", "EUROPE"):
                s += 1
            return -(s - len(name) / 200.0)

        rows.sort(key=score)
        for r in rows:
            n = (r["name"] or "").lower()
            r["kind"] = "market" if n.startswith("market") else "treatment" if "treatment of" in n else "production"
        return rows[:limit]

    def search_flows(self, text, limit=40):
        tokens = [t for t in re.findall(r"[\w\-\.]+", (text or "").lower()) if t]
        if not tokens:
            return []
        where = " AND ".join("lower(name) LIKE ?" for _ in tokens)
        rows = self.q(f"SELECT * FROM flows WHERE {where} LIMIT 400", [f"%{t}%" for t in tokens])
        rows.sort(key=lambda r: (len(r["name"]), r["compartment"] or "", r["subcompartment"] or ""))
        return rows[:limit]

    def activity(self, act_id):
        a = self.one("SELECT a.*, d.name AS db, d.system_model FROM activities a JOIN databases d ON d.id=a.db_id "
                     "WHERE a.id=?", (act_id,))
        if not a:
            return None
        a["inputs"] = self.q(
            "SELECT t.amount, i.id, i.name, i.product, i.location, i.unit FROM tech t "
            "JOIN activities i ON i.id=t.input_id WHERE t.output_id=? AND t.input_id!=? "
            "ORDER BY abs(t.amount) DESC LIMIT 60", (act_id, act_id))
        a["emissions"] = self.q(
            "SELECT b.amount, f.name, f.compartment, f.subcompartment, f.unit FROM bio b "
            "JOIN flows f ON f.id=b.flow_id WHERE b.activity_id=? ORDER BY abs(b.amount) DESC LIMIT 60", (act_id,))
        return a

    def flow(self, flow_id):
        return self.one("SELECT * FROM flows WHERE id=?", (flow_id,))

    # ---------------------------------------------------------------- methods
    def methods(self):
        rows = self.q("SELECT m.*, (SELECT COUNT(*) FROM cfs c WHERE c.method_id=m.id) AS n_cfs, "
                      "(SELECT COUNT(*) FROM cfs_regional r WHERE r.method_id=m.id) AS n_regional "
                      "FROM methods m ORDER BY family, category, indicator")
        sets = {}
        for r in self.q("SELECT method_id, set_name FROM nw"):
            sets.setdefault(r["method_id"], []).append(r["set_name"])
        for r in rows:
            r["nw_sets"] = sets.get(r["id"], [])
        return rows

    def method_by_key(self, family, category, indicator):
        return self.one("SELECT * FROM methods WHERE family=? AND category=? AND indicator=?", (family, category, indicator))

    def get_or_create_method(self, family, category, indicator, unit, source, note=""):
        family, category = str(family or "").strip(), str(category or "").strip()
        indicator = str(indicator or "").strip() or category
        r = self.method_by_key(family, category, indicator)
        if r:
            if unit and not r["unit"]:
                self.x("UPDATE methods SET unit=? WHERE id=?", (unit, r["id"]))
            return r["id"]
        return self.x("INSERT INTO methods(family,category,indicator,unit,source,note) VALUES(?,?,?,?,?,?)",
                      (family, category, indicator, unit or "", source, note))

    def delete_method_family(self, family):
        with self.lock:
            sub = "SELECT id FROM methods WHERE family=?"
            for t in ("cfs", "cfs_regional", "cf_raw", "nw"):
                self.conn.execute(f"DELETE FROM {t} WHERE method_id IN ({sub})", (family,))
            self.conn.execute("DELETE FROM methods WHERE family=?", (family,))
            self.conn.commit()

    def nw_sets(self):
        return [r["set_name"] for r in self.q("SELECT DISTINCT set_name FROM nw ORDER BY set_name")]

    # ---------------------------------------------------------------- models
    def models(self):
        rows = self.q("SELECT m.*, (SELECT COUNT(*) FROM main.model_inputs i WHERE i.model_id=m.id) AS n_inputs "
                      "FROM main.models m ORDER BY id DESC")
        for r in rows:
            r["scope"] = json.loads(r["scope"] or "{}")
        return rows

    def model(self, model_id):
        m = self.one("SELECT * FROM main.models WHERE id=?", (model_id,))
        if not m:
            return None
        m["scope"] = json.loads(m["scope"] or "{}")
        m["inputs"] = self.model_inputs(model_id)
        m["parameters"] = self.parameters(model_id)
        m["history"] = self.history(model_id)
        return m

    def model_inputs(self, model_id):
        rows = self.q("SELECT * FROM main.model_inputs WHERE model_id=? ORDER BY position, id", (model_id,))
        for r in rows:
            r["pedigree"] = json.loads(r["pedigree"] or "[3,3,3,3,3]")
            r["avoided"] = bool(r["avoided"])
            r["fixed"] = json.loads(r["fixed"]) if r["fixed"] else None
            r["pef"] = json.loads(r["pef"]) if r.get("pef") else None
            a = None
            if r["kind"] == "activity" and r["ref_id"]:
                a = self.one("SELECT a.name, a.product, a.location, a.unit, d.name AS db, d.system_model, d.version "
                             "FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?", (r["ref_id"],))
            elif r["kind"] == "model":
                a = self.one("SELECT name, product, '' AS location, unit, 'my models' AS db FROM main.models WHERE id=?",
                             (r["ref_id"],))
            elif r["kind"] == "flow" and r["ref_id"]:
                a = self.one("SELECT name, compartment || COALESCE('/' || NULLIF(subcompartment,''), '') AS location, "
                             "unit, 'elementary flow' AS db, '' AS product FROM flows WHERE id=?", (r["ref_id"],))
            elif r["kind"] == "fixed" and r["fixed"]:
                fx = r["fixed"]
                a = {"name": fx.get("name", "EPD"), "product": fx.get("name", ""), "location": fx.get("location", ""),
                     "unit": fx.get("unit", ""), "db": "EPD / fixed values"}
            r["missing"] = a is None
            if a is None:
                need = f" (needs database '{r['ref_db']}')" if r["ref_db"] else ""
                a = {"name": f"(missing: source not in this library{need})", "unit": "", "location": "", "db": r["ref_db"] or ""}
            r["target"] = a
            if r["input_unit"] is None:
                r["input_unit"] = a["unit"]
                r["input_amount"] = r["amount"]
        return rows

    def save_model(self, data):
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Give the model a name.")
        try:
            amount = float(data.get("amount") or 1)
        except (TypeError, ValueError):
            raise ValueError("The functional unit amount must be a number.")
        if not amount > 0:
            raise ValueError("The functional unit amount must be greater than zero.")
        scope = data.get("scope") or {}
        share = scope.get("alloc_share", "")
        if share not in ("", None):
            try:
                share = float(share)
            except (TypeError, ValueError):
                raise ValueError("Allocation share must be a number between 0 and 100.")
            if not 0 < share <= 100:
                raise ValueError("Allocation share must be between 0 and 100 %.")
        for cp in scope.get("coproducts") or []:
            for k in ("mass", "price", "energy"):
                v = cp.get(k)
                if v not in (None, ""):
                    try:
                        if float(v) < 0:
                            raise ValueError
                    except (TypeError, ValueError):
                        raise ValueError(f"Co-product '{cp.get('name', '')}': {k} must be a positive number.")
        js = json.dumps(scope)
        if data.get("id"):
            if not self.one("SELECT id FROM main.models WHERE id=?", (data["id"],)):
                raise ValueError("That model no longer exists.")
            self.x("UPDATE main.models SET name=?, product=?, unit=?, amount=?, scope=? WHERE id=?",
                   (name, data.get("product", ""), data.get("unit", ""), amount, js, data["id"]))
            return data["id"]
        return self.x("INSERT INTO main.models(name,product,unit,amount,scope) VALUES(?,?,?,?,?)",
                      (name, data.get("product", ""), data.get("unit", ""), amount, js))

    def duplicate_model(self, model_id, new_name=None):
        m = self.one("SELECT * FROM main.models WHERE id=?", (model_id,))
        if not m:
            raise ValueError("Model not found.")
        cols = [c for c in INPUT_COLUMNS if c not in ("id", "model_id")]
        with self.lock:
            nid = self.conn.execute("INSERT INTO main.models(name,product,unit,amount,scope) VALUES(?,?,?,?,?)",
                                    (new_name or m["name"] + " (copy)", m["product"], m["unit"], m["amount"], m["scope"])).lastrowid
            self.conn.execute(f"INSERT INTO main.model_inputs(model_id,{','.join(cols)}) SELECT ?,{','.join(cols)} "
                              "FROM main.model_inputs WHERE model_id=?", (nid, model_id))
            self.conn.execute("INSERT INTO main.parameters(model_id,name,value,formula,unit,comment,utype,p1,p2,p3) "
                              "SELECT ?,name,value,formula,unit,comment,utype,p1,p2,p3 FROM main.parameters WHERE model_id=?",
                              (nid, model_id))
            self.conn.commit()
        return nid

    def delete_model(self, model_id):
        if self.one("SELECT id FROM main.model_inputs WHERE kind='model' AND ref_id=?", (model_id,)):
            raise ValueError("Another model uses this one as an input. Remove it there first.")
        with self.lock:
            for t in ("model_inputs", "parameters", "history"):
                self.conn.execute(f"DELETE FROM main.{t} WHERE model_id=?", (model_id,))
            self.conn.execute("DELETE FROM main.models WHERE id=?", (model_id,))
            self.conn.commit()

    def target_exists(self, kind, ref_id):
        table = {"activity": "activities", "flow": "flows", "model": "main.models"}[kind]
        return self.one(f"SELECT id FROM {table} WHERE id=?", (ref_id,)) is not None

    def add_input(self, model_id, kind, ref_id, amount, label="", comment="", stage="", input_amount=None,
                  input_unit=None, avoided=False, pedigree=None, formula=None, year=0.0, fixed=None):
        if not self.one("SELECT id FROM main.models WHERE id=?", (model_id,)):
            raise ValueError("Model not found. Save the goal & scope first.")
        ref_db = ref_key = None
        if kind == "fixed":
            if not fixed or not fixed.get("impacts"):
                raise ValueError("Enter at least one impact value for this EPD line.")
            ref_id = None
        else:
            if not self.target_exists(kind, ref_id):
                raise ValueError("The selected dataset or flow no longer exists.")
            if kind == "model" and (int(ref_id) == int(model_id) or self._model_depends_on(int(ref_id), int(model_id))):
                raise ValueError("That would create a loop: a model cannot contain itself.")
            if kind == "activity":
                r = self.one("SELECT a.key, d.name FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?", (ref_id,))
                ref_db, ref_key = r["name"], r["key"]
            elif kind == "flow":
                ref_key = self.one("SELECT uuid FROM flows WHERE id=?", (ref_id,))["uuid"]
        ped = json.dumps([min(5, max(1, int(v))) for v in (pedigree or [3, 3, 3, 3, 3])][:5])
        pos = (self.one("SELECT MAX(position) AS p FROM main.model_inputs WHERE model_id=?", (model_id,))["p"] or 0) + 1
        return self.x("INSERT INTO main.model_inputs(model_id,kind,ref_id,amount,label,comment,position,stage,"
                      "input_amount,input_unit,avoided,pedigree,ref_db,ref_key,formula,year,fixed) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (model_id, kind, ref_id, float(amount), label or "", comment or "", pos, stage or "",
                       input_amount if input_amount is not None else float(amount), input_unit, 1 if avoided else 0,
                       ped, ref_db, ref_key, formula or None, float(year or 0), json.dumps(fixed) if fixed else None))

    def _model_depends_on(self, model_id, target):
        stack, seen = [model_id], set()
        while stack:
            m = stack.pop()
            if m == target:
                return True
            if m in seen:
                continue
            seen.add(m)
            stack += [r["ref_id"] for r in self.q("SELECT ref_id FROM main.model_inputs WHERE model_id=? AND kind='model'", (m,))]
        return False

    def get_input(self, input_id):
        return self.one("SELECT * FROM main.model_inputs WHERE id=?", (input_id,))

    def update_input(self, input_id, fields):
        allowed = {"amount", "label", "comment", "stage", "input_amount", "input_unit", "avoided", "pedigree",
                   "formula", "year", "fixed", "ref_id", "ref_db", "ref_key", "data_type", "source_ref", "data_year",
                   "supplier", "verified", "unit_cost", "pef"}
        with self.lock:
            for k, v in fields.items():
                if k not in allowed:
                    continue
                if k == "pedigree":
                    v = json.dumps([min(5, max(1, int(x))) for x in v][:5])
                elif k in ("avoided", "verified"):
                    v = 1 if v else 0
                elif k == "pef":
                    v = json.dumps([min(5, max(1, int(x))) for x in v][:4]) if v else None
                elif k in ("data_year", "unit_cost"):
                    v = None if v in (None, "") else float(v)
                elif k == "fixed":
                    v = json.dumps(v) if v else None
                elif k == "formula":
                    v = (v or "").strip() or None
                self.conn.execute(f"UPDATE main.model_inputs SET {k}=? WHERE id=?", (v, input_id))
            self.conn.commit()

    def delete_input(self, input_id):
        self.x("DELETE FROM main.model_inputs WHERE id=?", (input_id,))

    # ---------------------------------------------------------------- undo history
    def snapshot(self, model_id, label):
        m = self.one("SELECT * FROM main.models WHERE id=?", (model_id,))
        if not m:
            return
        snap = {"model": m, "inputs": self.q("SELECT * FROM main.model_inputs WHERE model_id=?", (model_id,)),
                "parameters": self.q("SELECT * FROM main.parameters WHERE model_id=?", (model_id,))}
        with self.lock:
            self.conn.execute("INSERT INTO main.history(model_id,ts,label,snapshot) VALUES(?,?,?,?)",
                              (model_id, time.time(), label, json.dumps(snap)))
            self.conn.execute("DELETE FROM main.history WHERE model_id=? AND id NOT IN (SELECT id FROM main.history "
                              "WHERE model_id=? ORDER BY id DESC LIMIT 40)", (model_id, model_id))
            self.conn.commit()

    def undo(self, model_id):
        h = self.one("SELECT * FROM main.history WHERE model_id=? ORDER BY id DESC LIMIT 1", (model_id,))
        if not h:
            raise ValueError("Nothing to undo for this model.")
        snap = json.loads(h["snapshot"])
        m = snap["model"]
        with self.lock:
            c = self.conn
            c.execute("UPDATE main.models SET name=?, product=?, unit=?, amount=?, scope=? WHERE id=?",
                      (m["name"], m["product"], m["unit"], m["amount"], m["scope"], model_id))
            c.execute("DELETE FROM main.model_inputs WHERE model_id=?", (model_id,))
            for r in snap["inputs"]:
                cols = [k for k in r if k in INPUT_COLUMNS]
                c.execute(f"INSERT INTO main.model_inputs({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                          [r[k] for k in cols])
            c.execute("DELETE FROM main.parameters WHERE model_id=?", (model_id,))
            for p in snap.get("parameters", []):
                cols = list(p)
                c.execute(f"INSERT INTO main.parameters({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                          [p[k] for k in cols])
            c.execute("DELETE FROM main.history WHERE id=?", (h["id"],))
            c.commit()
        self.relink()
        return h["label"]

    def history(self, model_id):
        return self.q("SELECT id, ts, label FROM main.history WHERE model_id=? ORDER BY id DESC LIMIT 10", (model_id,))

    # ---------------------------------------------------------------- parameters & scenarios
    def parameters(self, model_id=None, include_project=False):
        if model_id is None:
            return self.q("SELECT * FROM main.parameters WHERE model_id IS NULL ORDER BY name")
        rows = self.q("SELECT * FROM main.parameters WHERE model_id=? ORDER BY name", (model_id,))
        if include_project:
            rows = self.q("SELECT * FROM main.parameters WHERE model_id IS NULL ORDER BY name") + rows
        return rows

    def save_parameter(self, data):
        import formula as fm
        name = str(data.get("name") or "").strip()
        if not fm.valid_name(name):
            raise ValueError("Parameter names use letters, digits and _, start with a letter, and cannot be "
                             "a reserved word (e.g. density_wood).")
        model_id = data.get("model_id") or None
        clash = self.one("SELECT id FROM main.parameters WHERE name=? AND COALESCE(model_id,0)=COALESCE(?,0)",
                         (name, model_id))
        if clash and clash["id"] != data.get("id"):
            raise ValueError(f"A parameter called '{name}' already exists here.")
        f = (data.get("formula") or "").strip() or None
        try:
            value = float(data.get("value") or 0)
        except (TypeError, ValueError):
            raise ValueError("The parameter value must be a number.")
        if f:
            fm.parse(f)
        utype = int(data.get("utype") or 0)
        vals = [data.get(k) for k in ("p1", "p2", "p3")]
        vals = [float(v) if v not in (None, "") else None for v in vals]
        if utype == 1 and not (vals[0] and vals[0] > 0):
            raise ValueError("Lognormal: give the geometric standard deviation (above 1) as p1.")
        if utype == 2 and not (vals[0] and vals[0] > 0):
            raise ValueError("Normal: give the standard deviation as p1.")
        if utype == 3 and not (None not in vals and vals[0] <= vals[1] <= vals[2] and vals[2] > vals[0]):
            raise ValueError("Triangular: give minimum, mode and maximum (min <= mode <= max).")
        if utype == 4 and not (vals[0] is not None and vals[1] is not None and vals[1] > vals[0]):
            raise ValueError("Uniform: give minimum and maximum.")
        if utype == 1 and vals[0] <= 1:
            raise ValueError("Lognormal: the geometric standard deviation must be above 1 (e.g. 1.2).")
        row = (model_id, name, value, f, data.get("unit", ""), data.get("comment", ""), utype, *vals)
        if data.get("id"):
            self.x("UPDATE main.parameters SET model_id=?, name=?, value=?, formula=?, unit=?, comment=?, utype=?, "
                   "p1=?, p2=?, p3=? WHERE id=?", row + (data["id"],))
            return data["id"]
        return self.x("INSERT INTO main.parameters(model_id,name,value,formula,unit,comment,utype,p1,p2,p3) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)", row)

    def delete_parameter(self, pid):
        self.x("DELETE FROM main.parameters WHERE id=?", (pid,))

    def scenarios(self):
        rows = self.q("SELECT * FROM main.scenarios ORDER BY name")
        for r in rows:
            r["overrides"] = json.loads(r["overrides"] or "{}")
        return rows

    def save_scenario(self, data):
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Give the scenario a name.")
        ov = {}
        for k, v in (data.get("overrides") or {}).items():
            if v in (None, ""):
                continue
            try:
                ov[k] = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"Scenario value for '{k}' must be a number.")
        clash = self.one("SELECT id FROM main.scenarios WHERE name=?", (name,))
        if clash and clash["id"] != data.get("id"):
            raise ValueError("A scenario with that name already exists.")
        if data.get("id"):
            self.x("UPDATE main.scenarios SET name=?, description=?, overrides=? WHERE id=?",
                   (name, data.get("description", ""), json.dumps(ov), data["id"]))
            return data["id"]
        return self.x("INSERT INTO main.scenarios(name,description,overrides) VALUES(?,?,?)",
                      (name, data.get("description", ""), json.dumps(ov)))

    def delete_scenario(self, sid):
        self.x("DELETE FROM main.scenarios WHERE id=?", (sid,))

    # ---------------------------------------------------------------- site-specific factors
    def site_cfs(self):
        return self.q("SELECT * FROM main.site_cfs ORDER BY category, flow_name")

    def save_site_cf(self, data):
        for k in ("family", "category", "flow_uuid"):
            if not str(data.get(k) or "").strip():
                raise ValueError("A site-specific factor needs a method, a category and a flow.")
        try:
            v = float(data.get("value"))
        except (TypeError, ValueError):
            raise ValueError("The site-specific factor must be a number.")
        f = self.one("SELECT name, compartment, subcompartment FROM flows WHERE uuid=?", (data["flow_uuid"],))
        if not f:
            raise ValueError("That elementary flow is not in the library.")
        row = (data["family"], data["category"], data.get("indicator") or data["category"], data["flow_uuid"],
               f"{f['name']} ({'/'.join(x for x in (f['compartment'], f['subcompartment']) if x)})", v, data.get("note", ""))
        old = self.one("SELECT id FROM main.site_cfs WHERE family=? AND category=? AND indicator=? AND flow_uuid=?", row[:4])
        if old:
            self.x("UPDATE main.site_cfs SET value=?, note=?, flow_name=? WHERE id=?", (v, row[6], row[4], old["id"]))
            return old["id"]
        return self.x("INSERT INTO main.site_cfs(family,category,indicator,flow_uuid,flow_name,value,note) "
                      "VALUES(?,?,?,?,?,?,?)", row)

    def delete_site_cf(self, sid):
        self.x("DELETE FROM main.site_cfs WHERE id=?", (sid,))

    # ---------------------------------------------------------------- background scenarios
    def bg_scenarios(self):
        rows = self.q("SELECT * FROM main.bg_scenarios ORDER BY kind, name")
        for r in rows:
            r["rules"] = json.loads(r["rules"] or "[]")
        return rows

    def bg_scenario(self, sid):
        r = self.one("SELECT * FROM main.bg_scenarios WHERE id=?", (int(sid),))
        if r:
            r["rules"] = json.loads(r["rules"] or "[]")
        return r

    def save_bg_scenario(self, data):
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Give the background scenario a name.")
        kind = data.get("kind") or "prospective"
        if kind not in ("prospective", "consequential"):
            raise ValueError("kind must be prospective or consequential")
        rules = data.get("rules") or []
        if not isinstance(rules, list) or not rules:
            raise ValueError("Add at least one rule.")
        import science
        science.validate_rules(rules)
        clash = self.one("SELECT id FROM main.bg_scenarios WHERE name=?", (name,))
        if clash and clash["id"] != data.get("id"):
            raise ValueError("A background scenario with that name already exists.")
        row = (name, kind, data.get("description", ""), float(data.get("base_year") or 2020), json.dumps(rules))
        if data.get("id"):
            self.x("UPDATE main.bg_scenarios SET name=?, kind=?, description=?, base_year=?, rules=? WHERE id=?",
                   row + (data["id"],))
            return data["id"]
        return self.x("INSERT INTO main.bg_scenarios(name,kind,description,base_year,rules) VALUES(?,?,?,?,?)", row)

    def delete_bg_scenario(self, sid):
        self.x("DELETE FROM main.bg_scenarios WHERE id=?", (sid,))

    # ---------------------------------------------------------------- comments, versions, lock
    def comments(self, model_id):
        return self.q("SELECT * FROM main.comments WHERE model_id=? ORDER BY resolved, ts DESC", (model_id,))

    def add_comment(self, model_id, input_id, author, text):
        text = str(text or "").strip()
        if not text:
            raise ValueError("Write a comment first.")
        if not self.one("SELECT id FROM main.models WHERE id=?", (model_id,)):
            raise ValueError("Model not found.")
        return self.x("INSERT INTO main.comments(model_id,input_id,author,text,ts) VALUES(?,?,?,?,?)",
                      (model_id, input_id or None, author or "", text[:4000], time.time()))

    def resolve_comment(self, cid, resolved=True):
        self.x("UPDATE main.comments SET resolved=? WHERE id=?", (1 if resolved else 0, cid))

    def delete_comment(self, cid):
        self.x("DELETE FROM main.comments WHERE id=?", (cid,))

    def _snapshot_data(self, model_id):
        m = self.one("SELECT * FROM main.models WHERE id=?", (model_id,))
        if not m:
            raise ValueError("Model not found.")
        return {"model": m, "inputs": self.q("SELECT * FROM main.model_inputs WHERE model_id=? ORDER BY position, id", (model_id,)),
                "parameters": self.q("SELECT * FROM main.parameters WHERE model_id=?", (model_id,))}

    def save_version(self, model_id, name, author=""):
        name = str(name or "").strip() or time.strftime("Version %Y-%m-%d %H:%M")
        snap = self._snapshot_data(model_id)
        return self.x("INSERT INTO main.versions(model_id,name,author,ts,snapshot) VALUES(?,?,?,?,?)",
                      (model_id, name, author or "", time.time(), json.dumps(snap)))

    def versions(self, model_id):
        return self.q("SELECT id, model_id, name, author, ts FROM main.versions WHERE model_id=? ORDER BY id DESC", (model_id,))

    def version_snapshot(self, vid):
        r = self.one("SELECT * FROM main.versions WHERE id=?", (vid,))
        if not r:
            raise ValueError("Version not found.")
        return r, json.loads(r["snapshot"])

    def restore_snapshot(self, model_id, snap):
        m = snap["model"]
        with self.lock:
            c = self.conn
            c.execute("UPDATE main.models SET name=?, product=?, unit=?, amount=?, scope=? WHERE id=?",
                      (m["name"], m["product"], m["unit"], m["amount"], m["scope"], model_id))
            c.execute("DELETE FROM main.model_inputs WHERE model_id=?", (model_id,))
            for r in snap["inputs"]:
                cols = [k for k in r if k in INPUT_COLUMNS and k != "id"]
                c.execute(f"INSERT INTO main.model_inputs(model_id,{','.join(k for k in cols if k != 'model_id')}) "
                          f"VALUES(?,{','.join('?' * len([k for k in cols if k != 'model_id']))})",
                          [model_id] + [r[k] for k in cols if k != "model_id"])
            c.execute("DELETE FROM main.parameters WHERE model_id=?", (model_id,))
            for p in snap.get("parameters", []):
                cols = [k for k in p if k not in ("id", "model_id")]
                c.execute(f"INSERT INTO main.parameters(model_id,{','.join(cols)}) VALUES(?,{','.join('?' * len(cols))})",
                          [model_id] + [p[k] for k in cols])
            c.commit()
        self.relink()

    def lock_info(self, model_id):
        m = self.one("SELECT scope FROM main.models WHERE id=?", (model_id,))
        return (json.loads(m["scope"] or "{}").get("locked") if m else None) or None

    def set_lock(self, model_id, locked, author="", reason=""):
        m = self.one("SELECT scope FROM main.models WHERE id=?", (model_id,))
        if not m:
            raise ValueError("Model not found.")
        sc = json.loads(m["scope"] or "{}")
        if locked:
            sc["locked"] = {"by": author or "", "ts": time.time(), "reason": reason or ""}
        else:
            sc.pop("locked", None)
        self.x("UPDATE main.models SET scope=? WHERE id=?", (json.dumps(sc), model_id))

    # ---------------------------------------------------------------- templates and chemicals (library)
    def user_templates(self):
        rows = self.q("SELECT * FROM lib.templates ORDER BY category, name")
        for r in rows:
            r["spec"] = json.loads(r["spec"] or "{}")
        return rows

    def save_template(self, name, category, description, spec):
        name = str(name or "").strip()
        if not name:
            raise ValueError("Give the template a name.")
        self.x("INSERT OR REPLACE INTO lib.templates(name,category,description,spec) VALUES(?,?,?,?)",
               (name, category or "My templates", description or "", json.dumps(spec)))

    def delete_template(self, tid):
        self.x("DELETE FROM lib.templates WHERE id=?", (tid,))

    def chemicals(self):
        rows = self.q("SELECT * FROM lib.chemicals ORDER BY name")
        for r in rows:
            r["props"] = json.loads(r["props"] or "{}")
            r["result"] = json.loads(r["result"] or "{}")
        return rows

    def save_chemical(self, name, cas, props, result):
        self.x("INSERT OR REPLACE INTO lib.chemicals(name,cas,props,result) VALUES(?,?,?,?)",
               (name, cas or "", json.dumps(props), json.dumps(result)))
        return self.one("SELECT id FROM lib.chemicals WHERE name=?", (name,))["id"]

    def delete_chemical(self, cid):
        self.x("DELETE FROM lib.chemicals WHERE id=?", (cid,))


class Workspace:
    """Data folder: library.db plus projects/*.lca"""

    def __init__(self, root):
        self.root = root
        self.dir = os.path.join(root, "projects")
        os.makedirs(self.dir, exist_ok=True)
        self.library_path = os.path.join(root, "library.db")
        self._open = {}
        self.lock = threading.Lock()

    @staticmethod
    def clean_name(name):
        safe = re.sub(r"[^\w\- ]", "", str(name or "")).strip()
        if not safe:
            raise ValueError("Project name needs letters or numbers.")
        return safe[:80]

    def _path(self, name):
        return os.path.join(self.dir, self.clean_name(name) + ".lca")

    def list(self):
        out = []
        for f in sorted(os.listdir(self.dir)):
            if f.endswith(".lca"):
                p = os.path.join(self.dir, f)
                n = None
                try:  # model count without opening the project (read-only, no lock on the library)
                    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=1)
                    n = con.execute("SELECT COUNT(*) FROM models").fetchone()[0]
                    con.close()
                except Exception:
                    pass
                out.append({"name": f[:-4], "size_mb": round(os.path.getsize(p) / 1e6, 2), "models": n,
                            "modified": os.path.getmtime(p)})
        return out

    def exists(self, name):
        return os.path.exists(self._path(name))

    def create(self, name):
        if self.exists(name):
            raise ValueError("A project with that name already exists.")
        return self.open(name)

    def open(self, name):
        p = self._path(name)
        with self.lock:
            if p not in self._open:
                self._open[p] = ProjectStore(p, self.library_path)
            return self._open[p]

    def close(self, name):
        p = self._path(name)
        with self.lock:
            st = self._open.pop(p, None)
        if st:
            st.close()

    def close_all(self):
        with self.lock:
            stores = list(self._open.values())
            self._open.clear()
        for st in stores:
            st.close()

    def delete(self, name):
        self.close(name)
        p = self._path(name)
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(p + suffix):
                os.remove(p + suffix)

    def database_usage(self, db_name):
        """Projects (and number of lines) that use a library database."""
        out = []
        for pr in self.list():
            p = self._path(pr["name"])
            try:
                c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                n = c.execute("SELECT COUNT(*) FROM model_inputs WHERE ref_db=?", (db_name,)).fetchone()[0]
                c.close()
            except sqlite3.Error:
                n = 0
            if n:
                out.append({"project": pr["name"], "lines": n})
        return out

    def export(self, name, dest):
        st = self.open(name)
        with st.lock:
            st.conn.commit()
            out = sqlite3.connect(dest)
            st.conn.backup(out)  # copies the project schema ('main') only; databases stay in the library
            out.close()
        used = st.q("SELECT DISTINCT ref_db FROM main.model_inputs WHERE ref_db IS NOT NULL")
        return {"path": dest, "databases": [u["ref_db"] for u in used]}

    def import_file(self, src, name=None):
        if not os.path.isfile(src):
            raise ValueError("File not found.")
        test = sqlite3.connect(src)
        try:
            ok = test.execute("SELECT name FROM sqlite_master WHERE name='models'").fetchone()
        except sqlite3.DatabaseError:
            ok = None
        finally:
            test.close()
        if not ok:
            raise ValueError("This is not a Cyclia project file (.lca).")
        base = self.clean_name(name or os.path.splitext(os.path.basename(src))[0])
        cand, i = base, 2
        while self.exists(cand):
            cand = f"{base} {i}"
            i += 1
        shutil.copyfile(src, self._path(cand))
        self.open(cand)
        return cand
