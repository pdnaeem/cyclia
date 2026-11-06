"""Cyclia engine: local HTTP API used by the desktop app.

Listens on 127.0.0.1 only and requires a per-session token, so other programs and web pages cannot
call it.   python server.py [--port 8765] [--data <folder>]
"""
import argparse
import csv
import io
import json
import logging
import math
import mimetypes
import os
import platform
import re
import secrets
import sys
import threading
import time
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analysis  # noqa: E402
import crosscheck  # noqa: E402
import epd_profiles  # noqa: E402
import factormatch  # noqa: E402
import ilcd_epd  # noqa: E402
import compare_kit  # noqa: E402
import brightway_check  # noqa: E402
import custom_data  # noqa: E402
import lci_check  # noqa: E402,F401  (used by trust; imported here so the packaged engine includes it)
import staging  # noqa: E402
import mfa  # noqa: E402
import regional  # noqa: E402
import slca  # noqa: E402
import calc  # noqa: E402
import store as store_mod  # noqa: E402
import formula as fm  # noqa: E402
import interop  # noqa: E402
import inventory_io  # noqa: E402
import official  # noqa: E402
import linking  # noqa: E402
import productivity  # noqa: E402
import report  # noqa: E402
import science  # noqa: E402
import standards  # noqa: E402
import teaching  # noqa: E402
import trust  # noqa: E402
import units  # noqa: E402
from importers import demo, ecoinvent_login, ecospold2, jsonld, lcia, other_formats, tutorial  # noqa: E402
from store import Workspace  # noqa: E402

VERSION = "1.6.2"
APP = "Cyclia"
trust.APP_VERSION = VERSION
UI_DIR = os.environ.get("CYCLIA_UI") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "ui")
log = logging.getLogger("cyclia")

STAGE_PRESETS = {
    "EN 15804 (construction products)": [
        "A1 Raw material supply", "A2 Transport to manufacturer", "A3 Manufacturing", "A4 Transport to site",
        "A5 Construction and installation", "B1 Use", "B2 Maintenance", "B3 Repair", "B4 Replacement",
        "B5 Refurbishment", "B6 Operational energy use", "B7 Operational water use", "C1 Deconstruction",
        "C2 Transport to waste processing", "C3 Waste processing", "C4 Disposal",
        "D Benefits and loads beyond the system boundary"],
    "General": ["Raw materials", "Manufacturing", "Distribution", "Use", "End of life"],
    "Agriculture": ["Seeds and inputs", "Field operations", "Fertiliser and field emissions", "Harvest",
                    "Drying and storage", "Processing", "Transport"],
}
BENCHMARK_TEMPLATE = ("activity,location,product,database,method,category,indicator,value\n"
                      "\"market for electricity, medium voltage\",FR,\"electricity, medium voltage\",,EF v3.1,climate change,"
                      "global warming potential (GWP100),0.0789\n")


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


class State:
    def __init__(self, data_dir):
        self.ws = Workspace(data_dir)
        self.data_dir = data_dir
        self.exports = os.path.join(data_dir, "exports")
        os.makedirs(self.exports, exist_ok=True)
        self.project_name = None
        self.jobs = {}
        self.import_lock = threading.Lock()
        self.mc_results = {}
        self.api_info = {}
        self.last_validation = None
        last = os.path.join(data_dir, "last_project.txt")
        if os.path.exists(last):
            name = open(last, encoding="utf-8").read().strip()
            if name and any(p["name"] == name for p in self.ws.list()):
                self.project_name = name

    @property
    def store(self):
        if not self.project_name:
            raise ApiError("Open or create a project first (step 1).", 409)
        st = self.ws.open(self.project_name)
        if not st.get_meta("builtin_installed"):
            lcia.install_builtin(st)
            st.set_meta("builtin_installed", True)
        return st

    @property
    def settings(self):
        try:
            with open(os.path.join(self.data_dir, "settings.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def save_settings(self, data):
        cur = self.settings
        cur.update({k: v for k, v in data.items() if k in ("author",)})
        with open(os.path.join(self.data_dir, "settings.json"), "w", encoding="utf-8") as fh:
            json.dump(cur, fh)
        return cur

    @property
    def author(self):
        return self.settings.get("author") or ""

    def set_project(self, name):
        self.project_name = name
        with open(os.path.join(self.data_dir, "last_project.txt"), "w", encoding="utf-8") as fh:
            fh.write(name or "")
        self.mc_results.clear()
        calc.invalidate()

    def start_job(self, label, fn, exclusive=True):
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "label": label, "status": "running", "progress": 0, "message": "Starting",
               "result": None, "error": None, "started": time.time(), "cancel": False}
        self.jobs[job_id] = job

        def progress(p, msg=""):
            job["progress"], job["message"] = max(0, min(100, int(p))), msg

        def runner():
            if exclusive and not self.import_lock.acquire(blocking=False):
                job.update(status="error", error="Another import is running. Wait until it finishes.")
                return
            try:
                job["result"] = fn(progress, lambda: job["cancel"])
                job.update(status="done", progress=100, message="Finished")
            except calc.Cancelled:
                job.update(status="cancelled", message="Cancelled")
            except Exception as e:
                log.exception("job %s failed", label)
                job.update(status="error", error=str(e) or e.__class__.__name__)
            finally:
                if exclusive:
                    self.import_lock.release()
                    calc.invalidate()
        threading.Thread(target=runner, daemon=True).start()
        return {k: v for k, v in job.items() if k != "result"}


def _need(body, *keys):
    out = []
    for k in keys:
        if body.get(k) in (None, "", []):
            raise ApiError(f"Missing field: {k}")
        out.append(body[k])
    return out


def _num(v, field="Amount"):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a number.")
    if not math.isfinite(x):
        raise ApiError(f"{field} must be a finite number.")
    return x


def _check_path(p, must_exist=True):
    p = os.path.expanduser(str(p or "").strip().strip('"'))
    if not p:
        raise ApiError("Choose a file or folder first.")
    if must_exist and not os.path.exists(p):
        raise ApiError(f"Path not found: {p}")
    return p


ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _calc_error(fn, *a, **k):
    try:
        return fn(*a, **k)
    except calc.LCAError as e:
        raise ApiError(str(e))


def _unlocked(store, model_id):
    lk = store.lock_info(int(model_id)) if model_id else None
    if lk:
        raise ApiError(f"This model is locked{' by ' + lk['by'] if lk.get('by') else ''}"
                       f"{': ' + lk['reason'] if lk.get('reason') else ''}. Unlock it in step 2 (Versions and lock) to edit.", 423)


def _bg(body):
    if body.get("bg_id"):
        return {"id": int(body["bg_id"]), "year": float(body["bg_year"]) if body.get("bg_year") not in (None, "") else None}
    return None


# ------------------------------------------------------------------ status and projects
@route("GET", "/api/status")
def status(st, body, q):
    store = st.store if st.project_name else None
    return {"app": APP, "version": VERSION, "project": st.project_name, "data_dir": st.data_dir,
            "databases": store.databases() if store else [],
            "n_methods": len(store.methods()) if store else 0, "nw_sets": store.nw_sets() if store else [],
            "scenarios": store.scenarios() if store else [],
            "ecoinvent_interface": _has_module("ecoinvent_interface"), "stage_presets": STAGE_PRESETS,
            "licence": "MIT", "settings": st.settings,
            "bg_scenarios": store.bg_scenarios() if store else [], "demo": bool(store.get_meta("demo")) if store else False}


@route("GET", "/api/projects")
def projects(st, body, q):
    return {"projects": st.ws.list(), "current": st.project_name}


@route("POST", "/api/projects")
def project_create(st, body, q):
    (name,) = _need(body, "name")
    try:
        st.ws.create(name)
    except ValueError as e:
        raise ApiError(str(e))
    st.set_project(Workspace.clean_name(name))
    return {"current": st.project_name}


@route("POST", "/api/projects/open")
def project_open(st, body, q):
    (name,) = _need(body, "name")
    if not any(p["name"] == name for p in st.ws.list()):
        raise ApiError("Project not found.", 404)
    st.ws.open(name)
    st.set_project(name)
    return {"current": name}


@route("POST", "/api/projects/delete")
def project_delete(st, body, q):
    (name,) = _need(body, "name")
    if st.import_lock.locked() and st.project_name == name:
        raise ApiError("An import is running in this project. Wait until it finishes.")
    st.ws.delete(name)
    if st.project_name == name:
        st.set_project(None)
    return {"ok": True}


@route("POST", "/api/projects/export")
def project_export(st, body, q):
    name = body.get("name") or st.project_name
    if not name:
        raise ApiError("No project to export.")
    dest = _check_path(body.get("path") or os.path.join(st.exports, f"{name}.lca"), must_exist=False)
    info = st.ws.export(name, dest)
    return {"path": dest, "file": os.path.basename(dest), "databases": info["databases"]}


@route("POST", "/api/projects/import")
def project_import(st, body, q):
    (path,) = _need(body, "path")
    try:
        name = st.ws.import_file(_check_path(path))
    except ValueError as e:
        raise ApiError(str(e))
    st.set_project(name)
    missing = st.store.q("SELECT DISTINCT ref_db FROM main.model_inputs WHERE kind='activity' AND ref_id IS NULL")
    return {"current": name, "missing_databases": [m["ref_db"] for m in missing if m["ref_db"]]}


# ------------------------------------------------------------------ library: databases and imports
@route("GET", "/api/databases")
def dbs(st, body, q):
    return {"databases": st.store.databases()}


@route("DELETE", r"/api/databases/(\d+)")
def db_delete(st, body, q, db_id):
    if st.import_lock.locked():
        raise ApiError("An import is running. Wait until it finishes.")
    store = st.store
    d = store.one("SELECT name FROM databases WHERE id=?", (int(db_id),))
    if not d:
        raise ApiError("Database not found.", 404)
    usage = st.ws.database_usage(d["name"])
    if usage and not body.get("force") and not q.get("force"):
        raise ApiError("Used by: " + ", ".join(f"{u['project']} ({u['lines']} lines)" for u in usage) +
                       ". Remove those lines first; the database is shared by all projects.")
    store.delete_database(int(db_id))
    custom_data.recompile_all(store)
    calc.invalidate()
    return {"ok": True}


def _fingerprint(path):
    """SHA-256 of the source file, or of the sorted file names and contents of a folder."""
    import hashlib
    h = hashlib.sha256()
    if not path or not os.path.exists(path):
        return ""
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    for d, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for fn_ in sorted(files):
            fp = os.path.join(d, fn_)
            h.update(os.path.relpath(fp, path).replace(os.sep, "/").encode())
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()


def _integrity(store, db_id):
    """Critical problems that make a fresh import unusable (then it is rolled back): see staging.integrity."""
    return staging.integrity(store, db_id)


def _import_job(st, label, fn, path=None, body=None):
    """Run an import, then record the database's provenance (source file fingerprint, importer version, metadata
    entered by the user, import report) and check its integrity. An import that fails, or whose result has
    non-finite amounts or dangling links, is removed again: the library keeps either the whole database or nothing."""
    store = st.store
    body = body or {}

    name = str(body.get("name") or "").strip()
    if path and name and store.one("SELECT id FROM databases WHERE name=?", (name,)):
        raise ApiError(f"A database called '{name}' is already in the library. Use another name or remove it first.")

    def job(p, c):
        before = {d["id"] for d in store.databases()}
        if path:   # format imports go through a staging library and are merged only after the checks
            res = staging.staged(store, st.data_dir, fn, p)
        else:
            res = fn(store, p)
        new = [d for d in store.databases() if d["id"] not in before]
        if new and isinstance(res, dict):
            d = new[0]
            problems = _integrity(store, d["id"])
            if problems:
                store.delete_database(d["id"])
                calc.invalidate()
                raise ValueError("The import was rolled back: " + "; ".join(f"{v} {k} not valid" for k, v in problems.items()) + ".")
            p(97, "Recording the source fingerprint")
            meta = {k: str(body.get(k) or "").strip() for k in store_mod.DB_META_COLUMNS
                    if k not in ("source_path", "source_sha256", "importer_version", "import_report")}
            meta.update({"source_path": path or "", "source_sha256": _fingerprint(path) if path else "",
                         "importer_version": f"Cyclia {VERSION}",
                         "import_report": json.dumps({k: v for k, v in res.items() if k != "database"}, default=str)[:20000]})
            store.set_database_meta(d["id"], meta, version=body.get("version"), system_model=body.get("system_model"))
            res["metadata"] = store.one("SELECT * FROM databases WHERE id=?", (d["id"],))
        return res
    return {"job": st.start_job(label, job)}


@route("PATCH", r"/api/databases/(\d+)")
def db_meta(st, body, q, db_id):
    if not st.store.one("SELECT id FROM databases WHERE id=?", (int(db_id),)):
        raise ApiError("Database not found.", 404)
    editable = [k for k in store_mod.DB_META_COLUMNS if k not in ("source_sha256", "importer_version", "import_report")]
    meta = {k: str(body[k]).strip() for k in editable if k in body}
    st.store.set_database_meta(int(db_id), meta, version=body.get("version"), system_model=body.get("system_model"),
                               source=body.get("source"))
    return {"database": st.store.one("SELECT * FROM databases WHERE id=?", (int(db_id),))}


@route("POST", "/api/import/tutorial")
def imp_tutorial(st, body, q):
    return _import_job(st, "Tutorial database", lambda s, p: tutorial.install(s, p))


@route("POST", "/api/import/ecospold")
def imp_ecospold(st, body, q):
    folder, name = _need(body, "folder", "name")
    folder = _check_path(folder)
    if not os.path.isdir(folder):
        raise ApiError("Select the extracted folder, not a file. Extract the .7z download first.")
    return _import_job(st, f"Import {name}", lambda s, p: ecospold2.import_folder(
        s, folder, name, body.get("version", ""), body.get("system_model", ""), p), folder, body)


@route("POST", "/api/import/jsonld")
def imp_jsonld(st, body, q):
    path, name = _need(body, "path", "name")
    path = _check_path(path)
    return _import_job(st, f"Import {name}", lambda s, p: jsonld.import_jsonld(s, path, name, p), path, body)


@route("POST", "/api/import/ecospold1")
def imp_es1(st, body, q):
    path, name = _need(body, "path", "name")
    path = _check_path(path)
    return _import_job(st, f"Import {name}", lambda s, p: other_formats.import_ecospold1(s, path, name, p), path, body)


@route("POST", "/api/import/simapro")
def imp_sp(st, body, q):
    path, name = _need(body, "path", "name")
    path = _check_path(path)
    return _import_job(st, f"Import {name}", lambda s, p: other_formats.import_simapro_csv(s, path, name, p), path, body)


@route("POST", "/api/import/ilcd")
def imp_ilcd(st, body, q):
    path, name = _need(body, "path", "name")
    path = _check_path(path)
    return _import_job(st, f"Import {name}", lambda s, p: other_formats.import_ilcd(s, path, name, p), path, body)


@route("POST", "/api/import/lcia-xlsx")
def imp_lcia(st, body, q):
    path = _check_path(_need(body, "path")[0])
    return _import_job(st, "Import impact methods", lambda s, p: lcia.import_ecoinvent_lcia_xlsx(s, path, p))


@route("POST", "/api/import/cf-csv")
def imp_csv(st, body, q):
    path = _check_path(_need(body, "path")[0])
    return _import_job(st, "Import impact methods (CSV)", lambda s, p: lcia.import_cf_csv(s, path, p))


@route("POST", "/api/import/nw-csv")
def imp_nw(st, body, q):
    path = _check_path(_need(body, "path")[0])
    return _import_job(st, "Import normalisation & weighting", lambda s, p: lcia.import_nw_csv(s, path, p))


@route("POST", "/api/import/mapping")
def imp_mapping(st, body, q):
    path = _check_path(_need(body, "path")[0])
    return _import_job(st, "Import flow mapping", lambda s, p: lcia.import_mapping_csv(s, path, p))


@route("POST", "/api/methods/builtin")
def methods_builtin(st, body, q):
    ids = lcia.install_builtin(st.store)
    return {"methods": len(ids)}


@route("GET", "/api/templates")
def templates(st, body, q):
    return {"cf_csv": lcia.CSV_TEMPLATE, "nw_csv": lcia.NW_TEMPLATE, "mapping_csv": lcia.MAPPING_TEMPLATE,
            "benchmark_csv": BENCHMARK_TEMPLATE}


@route("POST", "/api/ecoinvent/releases")
def ei_releases(st, body, q):
    user, pw = _need(body, "username", "password")
    try:
        return {"releases": ecoinvent_login.list_releases(user, pw)}
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/ecoinvent/install")
def ei_install(st, body, q):
    user, pw, version, model = _need(body, "username", "password", "version", "system_model")
    name = body.get("name") or f"ecoinvent {version} {model}"
    validate = bool(body.get("validate", True))
    sample = int(body.get("sample") or 100)

    def job(store, progress):
        scale = 0.7 if validate else 1.0
        res = {"warnings": []}
        if store.one("SELECT id FROM databases WHERE name=?", (name,)):
            res["warnings"].append(f"'{name}' was already in the library; it was not imported again.")
        else:
            folder, lcia_file = ecoinvent_login.download(user, pw, version, model, lambda pc, m: progress(pc * scale * 0.45, m))
            res = ecospold2.import_folder(store, folder, name, version, model,
                                          lambda pc, m: progress((45 + pc * 0.45) * scale, m))
            if lcia_file:
                r2 = lcia.import_ecoinvent_lcia_xlsx(store, lcia_file, lambda pc, m: progress((90 + pc * 0.1) * scale, m))
                res["methods"] = r2["methods"]
                res["warnings"] += r2["warnings"]
            else:
                res["warnings"].append("The LCIA file could not be downloaded automatically. Download it from ecoquery "
                                       "and import it under 'Impact assessment methods'.")
        calc.invalidate()
        if validate:
            res["benchmark"] = _ei_validate(st, store, user, pw, version, model, name, sample,
                                            lambda pc, m: progress(70 + pc * 0.3, m),
                                            inventories=bool(body.get("inventories", True)),
                                            all_methods=bool(body.get("all_methods")))
        return res
    return _import_job(st, f"Install {name}", job)


def _ei_validate(st, store, user, pw, version, model, db_name, sample, progress, inventories=True, all_methods=False):
    """Download ecoinvent's own LCIA results and compare Cyclia with them. With inventories, ecoinvent's cumulative
    LCI is downloaded too and the gap of each result is split into an inventory part and a factor part.
    Never fails the installation."""
    try:
        path = ecoinvent_login.download_cumulative_lcia(user, pw, version, model, lambda pc, m: progress(pc * 0.2, m))
        lci, lci_error = None, ""
        if inventories:
            try:
                lci = ecoinvent_login.download_cumulative_lci(user, pw, version, model,
                                                              lambda pc, m: progress(20 + pc * 0.2, m))
            except Exception as e:
                lci_error = str(e)
        # all_methods: every method of ecoinvent's results file that is installed (EF, ReCiPe, CML, IPCC and others),
        # otherwise EF 3.1 when installed
        st.last_bench = trust.benchmark_ecoinvent(store, path, "" if all_methods else trust.preferred_family(store), sample,
                                                  progress=lambda pc, m: progress(40 + pc * 0.6, m), db_name=db_name,
                                                  lci_path=lci)
        if lci_error:
            st.last_bench["inventory"] = {"error": "ecoinvent's cumulative LCI could not be downloaded, so the inventory "
                                                   f"check was not run ({lci_error})."}
        out = dict(st.last_bench)
        out["rows"] = []
        return out
    except Exception as e:  # validation is an extra; the database stays installed
        log.exception("automatic validation failed")
        return {"error": str(e)}


@route("POST", "/api/ecoinvent/validate")
def ei_validate(st, body, q):
    """Validate an installed ecoinvent release against ecoinvent's own results (downloaded with the user's login)."""
    user, pw, version, model = _need(body, "username", "password", "version", "system_model")
    db_name = body.get("db_name") or f"ecoinvent {version} {model}"
    store = st.store
    if not store.one("SELECT id FROM databases WHERE name=?", (db_name,)):
        raise ApiError(f"'{db_name}' is not in the library. Install it first, or choose the database it was imported as.")

    def job(progress, cancelled):
        r = _ei_validate(st, store, user, pw, version, model, db_name, int(body.get("sample") or 100), progress,
                         inventories=bool(body.get("inventories", True)), all_methods=bool(body.get("all_methods")))
        if r.get("error"):
            raise ValueError(r["error"])
        return r
    return {"job": st.start_job("Validate against ecoinvent", job, exclusive=False)}


@route("GET", r"/api/jobs/(\w+)")
def job_status(st, body, q, job_id):
    job = st.jobs.get(job_id)
    if not job:
        raise ApiError("Job not found.", 404)
    out = dict(job)
    out.pop("cancel", None)
    return {"job": out}


@route("POST", r"/api/jobs/(\w+)/cancel")
def job_cancel(st, body, q, job_id):
    job = st.jobs.get(job_id)
    if not job:
        raise ApiError("Job not found.", 404)
    job["cancel"] = True
    return {"ok": True}


# ------------------------------------------------------------------ linking, validation, benchmark
@route("GET", r"/api/databases/(\d+)/unlinked")
def unlinked(st, body, q, db_id):
    return {"groups": linking.groups(st.store, int(db_id))}


@route("POST", r"/api/databases/(\d+)/suggest")
def unlinked_suggest(st, body, q, db_id):
    return {"suggestions": linking.suggest(st.store, int(db_id), body.get("product", ""), body.get("unit", ""),
                                           location=body.get("location"))}


@route("POST", r"/api/databases/(\d+)/link")
def unlinked_link(st, body, q, db_id):
    target = _need(body, "target_id")[0]
    try:
        r = linking.link(st.store, int(db_id), body.get("product", ""), body.get("unit", ""), int(target), body.get("factor"),
                         location=body.get("location"))
    except ValueError as e:
        raise ApiError(str(e))
    calc.invalidate()
    return r


@route("POST", r"/api/databases/(\d+)/unlink")
def unlinked_unlink(st, body, q, db_id):
    r = linking.unlink(st.store, int(db_id), body.get("product", ""), body.get("unit", ""), location=body.get("location"))
    calc.invalidate()
    return r


@route("POST", r"/api/databases/(\d+)/autolink")
def unlinked_auto(st, body, q, db_id):
    r = linking.auto_link(st.store, int(db_id))
    calc.invalidate()
    return r


@route("POST", "/api/validate")
def validate(st, body, q):
    db = body.get("db_id")
    return _calc_error(calc.validate_database, st.store, int(db) if db else None)


def _read_table(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip().lower() for h in next(it)]
        return [dict(zip(head, ["" if v is None else v for v in r])) for r in it if r and any(v not in (None, "") for v in r)]
    with open(path, newline="", encoding="utf-8-sig") as fh:
        text = fh.read()
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [{(k or "").strip().lower(): v for k, v in r.items()} for r in csv.DictReader(io.StringIO(text), dialect=dialect)]


@route("POST", "/api/benchmark")
def benchmark(st, body, q):
    path = _check_path(_need(body, "path")[0])
    rows = _read_table(path)
    need = {"activity", "method", "category", "value"}
    if not rows or not need <= set(rows[0]):
        raise ApiError("The benchmark file needs the columns: " + BENCHMARK_TEMPLATE.splitlines()[0])
    store = st.store

    def job(progress, cancelled):
        return calc.benchmark(store, rows)
    return {"job": st.start_job("Benchmark", job, exclusive=False)}


# ------------------------------------------------------------------ browse
@route("GET", "/api/search")
def search(st, body, q):
    db = q.get("db", [""])[0]
    return {"results": st.store.search_activities(q.get("q", [""])[0], int(db) if db.isdigit() else None,
                                                  q.get("loc", [""])[0])}


@route("GET", "/api/flows")
def flows(st, body, q):
    return {"results": st.store.search_flows(q.get("q", [""])[0])}


@route("GET", r"/api/activity/(\d+)")
def activity(st, body, q, act_id):
    a = st.store.activity(int(act_id))
    if not a:
        raise ApiError("Not found.", 404)
    a["units"] = units.compatible(a["unit"])
    return {"activity": a}


@route("GET", r"/api/explore/(\d+)")
def explore(st, body, q, act_id):
    a = st.store.explore(int(act_id))
    if not a:
        raise ApiError("Not found.", 404)
    return {"activity": a}


@route("GET", "/api/explore")
def explore_search(st, body, q):
    """Datasets of the library with filters, all applied in the database query (so a filter never only sees the first
    page): text (every word in name, product or location), database, location, system model, version, datasets with
    unresolved inputs, datasets with an elementary flow (name). Paged: offset, limit (at most 200); total is returned."""
    one = lambda k: (q.get(k) or [""])[0] if isinstance(q.get(k), list) else (q.get(k) or "")
    where, args = [], []
    for w in re.findall(r"[\w\-.,]+", one("q").lower())[:8]:
        where.append("(lower(a.name) LIKE ? OR lower(a.product) LIKE ? OR lower(a.location) LIKE ?)")
        args += [f"%{w}%"] * 3
    if one("db"):
        where.append("a.db_id=?")
        args.append(int(one("db")))
    if one("location"):
        where.append("upper(a.location)=?")
        args.append(one("location").strip().upper())
    if one("system_model"):
        where.append("lower(COALESCE(d.system_model,'')) LIKE ?")
        args.append(f"%{one('system_model').strip().lower()}%")
    if one("version"):
        where.append("COALESCE(d.version,'')=?")
        args.append(one("version").strip())
    if one("unresolved") == "1":
        where.append("a.id IN (SELECT output_id FROM unlinked WHERE linked_to IS NULL)")
    if one("flow"):
        where.append("a.id IN (SELECT b.activity_id FROM bio b JOIN flows f ON f.id=b.flow_id WHERE lower(f.name) LIKE ?)")
        args.append(f"%{one('flow').strip().lower()}%")
    sql = " FROM activities a JOIN databases d ON d.id=a.db_id" + (" WHERE " + " AND ".join(where) if where else "")
    limit = max(1, min(200, int(one("limit") or 50)))
    offset = max(0, int(one("offset") or 0))
    total = st.store.one("SELECT COUNT(*) AS n" + sql, args)["n"]
    rows = st.store.q("SELECT a.id, a.name, a.product, a.location, a.unit, d.name AS db, d.version, d.system_model, "
                      "(SELECT COUNT(*) FROM unlinked u WHERE u.output_id=a.id AND u.linked_to IS NULL) AS unresolved"
                      + sql + " ORDER BY a.name, a.location, a.id LIMIT ? OFFSET ?", args + [limit, offset])
    return {"results": rows, "total": total, "offset": offset, "limit": limit}


@route("POST", "/api/explore/export")
def explore_export(st, body, q):
    ids = [int(x) for x in (body.get("ids") or [])][:5000]
    if not ids:
        raise ApiError("Select datasets first.")
    from openpyxl import Workbook
    path = _export_path(st, body, {"name": "Cyclia datasets"}, "xlsx")
    _writable(path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Datasets"
    ws.append(["Id", "Database", "Version", "System model", "Key", "Name", "Product", "Location", "Unit", "Production",
               "Unresolved inputs"])
    w2 = wb.create_sheet("Technosphere")
    w2.append(["Dataset id", "Dataset", "Supplier id", "Supplier", "Supplier location", "Amount", "Unit"])
    w3 = wb.create_sheet("Elementary flows")
    w3.append(["Dataset id", "Dataset", "Flow", "Compartment", "Subcompartment", "UUID", "Amount", "Unit"])
    w4 = wb.create_sheet("Unresolved inputs")
    w4.append(["Dataset id", "Dataset", "Product", "Location", "Amount", "Unit", "Reason", "Linked to"])
    for i in ids:
        a = st.store.explore(i, limit=100000)
        if not a:
            continue
        ws.append([a["id"], a["db"], a["db_version"], a["system_model"], a["key"], a["name"], a["product"], a["location"],
                   a["unit"], a["production"], len([u for u in a["unresolved"] if not u["linked_to"]])])
        for x in a["inputs"]:
            w2.append([a["id"], a["name"], x["id"], x["name"], x["location"], x["amount"], x["unit"]])
        for x in a["emissions"]:
            w3.append([a["id"], a["name"], x["name"], x["compartment"], x["subcompartment"], x["uuid"], x["amount"], x["unit"]])
        for u in a["unresolved"]:
            w4.append([a["id"], a["name"], u["product"], u["location"], u["amount"], u["unit"], u["reason"], u["linked_to"]])
    wb.save(path)
    return {"path": path, "file": os.path.basename(path), "datasets": len(ids)}


@route("POST", r"/api/activity/(\d+)/copy")
def activity_copy(st, body, q, act_id):
    """Create an editable process (a model) from a database dataset."""
    store = st.store
    a = store.activity(int(act_id))
    if not a:
        raise ApiError("Not found.", 404)
    full_in = store.q("SELECT input_id, SUM(amount) AS amount FROM tech WHERE output_id=? AND input_id!=? GROUP BY input_id",
                      (a["id"], a["id"]))
    full_bio = store.q("SELECT flow_id, SUM(amount) AS amount FROM bio WHERE activity_id=? GROUP BY flow_id", (a["id"],))
    prod = a["production"] or 1.0
    name = body.get("name") or f"{a['name']} [{a['location']}] (editable copy)"
    mid = store.save_model({"name": name, "product": a["product"], "unit": a["unit"], "amount": 1.0,
                            "scope": {"kind": "process", "copied_from": f"{a['db']}: {a['name']} [{a['location']}]"}})
    for t in full_in:
        u = store.one("SELECT unit FROM activities WHERE id=?", (t["input_id"],))["unit"]
        amt = t["amount"] / prod
        store.add_input(mid, "activity", t["input_id"], abs(amt), comment=f"from {a['db']}", input_unit=u,
                        avoided=amt < 0, pedigree=[2, 2, 2, 2, 2])
    for b in full_bio:
        u = store.one("SELECT unit FROM flows WHERE id=?", (b["flow_id"],))["unit"]
        amt = b["amount"] / prod
        f = store.flow(b["flow_id"])
        store.add_input(mid, "flow", b["flow_id"], abs(amt), label=f["name"], comment=f"from {a['db']}", input_unit=u,
                        avoided=amt < 0, pedigree=[2, 2, 2, 2, 2])
    return {"model": store.model(mid)}


@route("GET", "/api/units")
def unit_list(st, body, q):
    return {"units": units.compatible(q.get("unit", [""])[0])}


@route("GET", "/api/methods")
def methods(st, body, q):
    return {"methods": st.store.methods(), "nw_sets": st.store.nw_sets()}


@route("POST", "/api/methods/delete")
def methods_delete(st, body, q):
    (family,) = _need(body, "family")
    st.store.delete_method_family(family)
    calc.invalidate()
    return {"ok": True}


# ------------------------------------------------------------------ models, inputs, undo
@route("GET", "/api/models")
def models(st, body, q):
    return {"models": st.store.models()}


@route("POST", "/api/models")
def model_save(st, body, q):
    store = st.store
    if body.get("id"):
        _unlocked(store, body["id"])
        store.snapshot(int(body["id"]), "edit goal & scope")
        if isinstance(body.get("scope"), dict):
            body["scope"].pop("locked", None)
    try:
        mid = store.save_model(body)
    except ValueError as e:
        raise ApiError(str(e))
    return {"model": store.model(mid)}


@route("GET", r"/api/models/(\d+)")
def model_get(st, body, q, mid):
    m = st.store.model(int(mid))
    if not m:
        raise ApiError("Model not found.", 404)
    return {"model": m}


@route("POST", r"/api/models/(\d+)/duplicate")
def model_dup(st, body, q, mid):
    try:
        nid = st.store.duplicate_model(int(mid), body.get("name"))
    except ValueError as e:
        raise ApiError(str(e))
    return {"model": st.store.model(nid)}


@route("DELETE", r"/api/models/(\d+)")
def model_delete(st, body, q, mid):
    _unlocked(st.store, mid)
    try:
        st.store.delete_model(int(mid))
    except ValueError as e:
        raise ApiError(str(e))
    return {"ok": True}


@route("POST", r"/api/models/(\d+)/undo")
def model_undo(st, body, q, mid):
    _unlocked(st.store, mid)
    try:
        label = st.store.undo(int(mid))
    except ValueError as e:
        raise ApiError(str(e))
    return {"undone": label, "model": st.store.model(int(mid))}


def _target_unit(store, kind, ref_id):
    table = {"activity": "activities", "flow": "flows", "model": "main.models"}[kind]
    r = store.one(f"SELECT unit FROM {table} WHERE id=?", (ref_id,))
    if not r:
        raise ApiError("The selected dataset or flow no longer exists.")
    return r["unit"] or ""


def _convert(store, kind, ref_id, amount, unit):
    if kind == "fixed":
        return amount, unit
    target = _target_unit(store, kind, ref_id)
    unit = unit or target
    fac = units.factor(unit, target)
    if fac is None:
        raise ApiError(f"'{unit}' cannot be converted to the dataset unit '{target}'.")
    return amount * fac, unit


def _check_formula(store, model_id, text):
    if not text:
        return None
    text = str(text).strip()
    try:
        names = fm.names_in(text)
        known = {p["name"] for p in store.parameters(model_id, include_project=True)}
        unknown = names - known
        if unknown:
            raise ApiError(f"Unknown parameter(s) in the formula: {', '.join(sorted(unknown))}. Define them first.")
        vals = calc.Context(store).params(model_id) if known else {}
        return text, fm.evaluate(text, vals)
    except fm.FormulaError as e:
        raise ApiError(str(e))
    except calc.LCAError as e:
        raise ApiError(str(e))


def _fixed(body):
    fx = body.get("fixed")
    if not fx:
        return None
    impacts = []
    for x in fx.get("impacts", []):
        if x.get("value") in (None, ""):
            continue
        impacts.append({"family": x["family"], "category": x["category"], "indicator": x["indicator"],
                        "value": _num(x["value"], f"Value for {x['category']}")})
    if not impacts:
        raise ApiError("Enter at least one value from the EPD.")
    return {"name": str(fx.get("name") or "EPD").strip(), "unit": str(fx.get("unit") or "").strip(),
            "location": str(fx.get("location") or "").strip(), "source": str(fx.get("source") or "").strip(),
            "impacts": impacts}


@route("POST", r"/api/models/(\d+)/inputs")
def input_add(st, body, q, mid):
    kind = _need(body, "kind")[0]
    if kind not in ("activity", "flow", "model", "fixed"):
        raise ApiError("kind must be activity, flow, model or fixed")
    store = st.store
    mid = int(mid)
    _unlocked(store, mid)
    ref_id = int(body["ref_id"]) if body.get("ref_id") not in (None, "") else None
    if kind != "fixed" and ref_id is None:
        raise ApiError("Missing field: ref_id")
    formula = None
    if body.get("formula"):
        formula, amount = _check_formula(store, mid, body["formula"])
    else:
        if body.get("amount") in (None, ""):
            raise ApiError("Enter an amount.")
        amount = _num(body["amount"])
    if amount < 0:
        raise ApiError("Enter a positive amount. For a credit, tick 'avoided product'.")
    fixed = _fixed(body) if kind == "fixed" else None
    unit = body.get("unit") or (fixed["unit"] if fixed else None)
    conv, unit = _convert(store, kind, ref_id, amount, unit)
    year = _num(body.get("year") or 0, "Year")
    store.snapshot(mid, "add line")
    try:
        store.add_input(mid, kind, ref_id, conv, body.get("label", ""), body.get("comment", ""), body.get("stage", ""),
                        amount, unit, bool(body.get("avoided")), body.get("pedigree"), formula, year, fixed)
    except ValueError as e:
        raise ApiError(str(e))
    return {"model": store.model(mid)}


DATA_TYPES = ("", "primary", "secondary", "estimate")
COST_TYPES = ("", "capex", "opex", "maintenance", "replacement", "end of life")


@route("PATCH", r"/api/inputs/(\d+)")
def input_update(st, body, q, iid):
    store = st.store
    row = store.get_input(int(iid))
    if not row:
        raise ApiError("That line no longer exists.", 404)
    _unlocked(store, row["model_id"])
    fields = {k: body[k] for k in ("label", "comment", "stage", "avoided", "pedigree") if k in body}
    if "data_type" in body:
        if body["data_type"] not in DATA_TYPES:
            raise ApiError("Data type must be primary, secondary or estimate.")
        fields["data_type"] = body["data_type"]
    for k in ("source_ref", "supplier"):
        if k in body:
            fields[k] = str(body[k] or "").strip()[:500]
    if "verified" in body:
        fields["verified"] = bool(body["verified"])
    if "pef" in body:
        v = body["pef"]
        if v in (None, "", []):
            fields["pef"] = None
        else:
            try:
                v = [int(x) for x in v]
            except (TypeError, ValueError):
                raise ApiError("PEF scores must be whole numbers 1 to 5.")
            if len(v) != 4 or not all(1 <= x <= 5 for x in v):
                raise ApiError("Give all four PEF scores (TeR, GeR, TiR, P), each 1 to 5.")
            fields["pef"] = v
    if "data_year" in body:
        if body["data_year"] in (None, ""):
            fields["data_year"] = None
        else:
            y = _num(body["data_year"], "Data year")
            if not 1900 <= y <= 2100:
                raise ApiError("Give the data year as a four-digit year, e.g. 2024.")
            fields["data_year"] = y
    if "cost_type" in body:
        if body["cost_type"] not in COST_TYPES:
            raise ApiError("Cost type must be one of: " + ", ".join(t or "(none)" for t in COST_TYPES) + ".")
        fields["cost_type"] = body["cost_type"]
    if "replace_every" in body:
        if body["replace_every"] in (None, ""):
            fields["replace_every"] = None
        else:
            r = _num(body["replace_every"], "Replacement interval")
            if r <= 0:
                raise ApiError("The replacement interval must be more than zero years.")
            fields["replace_every"] = r
    if "unit_cost" in body:
        if body["unit_cost"] in (None, ""):
            fields["unit_cost"] = None
        else:
            fields["unit_cost"] = _num(body["unit_cost"], "Cost per unit")
    if "pedigree" in fields:
        try:
            ped = [int(x) for x in fields["pedigree"]]
        except (TypeError, ValueError):
            raise ApiError("Data-quality scores must be whole numbers 1 to 5.")
        if len(ped) != 5 or not all(1 <= x <= 5 for x in ped):
            raise ApiError("Five data-quality scores from 1 to 5 are needed.")
        fields["pedigree"] = ped
    if "year" in body:
        fields["year"] = _num(body["year"] or 0, "Year")
    if "fixed" in body and row["kind"] == "fixed":
        fields["fixed"] = _fixed(body)
    if "formula" in body:
        if body["formula"]:
            f, val = _check_formula(store, row["model_id"], body["formula"])
            if val < 0:
                raise ApiError("The formula gives a negative amount. Use 'avoided product' for credits.")
            conv, unit = _convert(store, row["kind"], row["ref_id"], val, body.get("input_unit") or row["input_unit"])
            fields.update(formula=f, amount=conv, input_amount=val, input_unit=unit)
        else:
            fields["formula"] = None
    if ("input_amount" in body or "input_unit" in body) and "formula" not in fields:
        amount = _num(body.get("input_amount", row["input_amount"] if row["input_amount"] is not None else row["amount"]))
        if amount < 0:
            raise ApiError("Enter a positive amount. For a credit, tick 'avoided product'.")
        conv, unit = _convert(store, row["kind"], row["ref_id"], amount, body.get("input_unit") or row["input_unit"])
        fields.update(amount=conv, input_amount=amount, input_unit=unit, formula=None)
    store.snapshot(row["model_id"], "edit line")
    store.update_input(int(iid), fields)
    r = store.get_input(int(iid))
    return {"input": {k: r[k] for k in ("id", "amount", "input_amount", "input_unit", "formula")}}


@route("POST", r"/api/inputs/(\d+)/replace")
def input_replace(st, body, q, iid):
    """Swap the dataset of a line (e.g. another electricity mix), keeping amount, stage and notes."""
    store = st.store
    row = store.get_input(int(iid))
    if not row or row["kind"] != "activity":
        raise ApiError("Only dataset lines can be replaced.")
    _unlocked(store, row["model_id"])
    new_id = int(_need(body, "ref_id")[0])
    a = store.one("SELECT a.unit, a.key, d.name FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?", (new_id,))
    if not a:
        raise ApiError("The chosen dataset does not exist.")
    fac = units.factor(row["input_unit"], a["unit"])
    if fac is None:
        raise ApiError(f"The new dataset's unit '{a['unit']}' does not match '{row['input_unit']}'.")
    store.snapshot(row["model_id"], "replace dataset")
    store.update_input(int(iid), {"ref_id": new_id, "ref_db": a["name"], "ref_key": a["key"],
                                  "amount": (row["input_amount"] or 0) * fac})
    return {"model": store.model(row["model_id"])}


@route("DELETE", r"/api/inputs/(\d+)")
def input_delete(st, body, q, iid):
    store = st.store
    row = store.get_input(int(iid))
    if row:
        _unlocked(store, row["model_id"])
        store.snapshot(row["model_id"], "remove line")
        store.delete_input(int(iid))
    return {"ok": True}


@route("POST", r"/api/models/(\d+)/inventory-template")
def inv_template(st, body, q, mid):
    path = _check_path(body.get("path") or os.path.join(st.exports, "Cyclia inventory template.xlsx"), False)
    inventory_io.template(path)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", r"/api/models/(\d+)/inventory-export")
def inv_export(st, body, q, mid):
    m = st.store.model(int(mid))
    if not m:
        raise ApiError("Model not found.", 404)
    safe = re.sub(r"[^\w\-]+", "_", m["name"]).strip("_") or "model"
    path = _check_path(body.get("path") or os.path.join(st.exports, f"{safe}_inventory.xlsx"), False)
    inventory_io.export(st.store, int(mid), path)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", r"/api/models/(\d+)/inventory-import")
def inv_import(st, body, q, mid):
    (path,) = _need(body, "path")
    store = st.store
    _unlocked(store, mid)
    store.snapshot(int(mid), "Excel import")
    try:
        res = inventory_io.import_rows(store, int(mid), _check_path(path))
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        raise ApiError(f"Could not read that Excel file: {e}")
    res["model"] = store.model(int(mid))
    return res


# ------------------------------------------------------------------ parameters and scenarios
@route("GET", "/api/parameters")
def params_list(st, body, q):
    mid = q.get("model_id", [""])[0]
    store = st.store
    out = {"project": store.parameters(None)}
    if mid.isdigit():
        out["model"] = store.parameters(int(mid))
        try:
            out["values"] = calc.Context(store).params(int(mid))
        except calc.LCAError as e:
            out["error"] = str(e)
    return out


@route("POST", "/api/parameters")
def params_save(st, body, q):
    store = st.store
    if body.get("model_id"):
        _unlocked(store, body["model_id"])
    try:
        pid = store.save_parameter(body)
        mid = body.get("model_id")
        calc.Context(store).params(int(mid)) if mid else fm.resolve(store.parameters(None))
    except (ValueError, calc.LCAError) as e:
        if "pid" in locals() and not body.get("id"):
            store.delete_parameter(pid)
        raise ApiError(str(e))
    return {"id": pid}


@route("DELETE", r"/api/parameters/(\d+)")
def params_delete(st, body, q, pid):
    store = st.store
    p = store.one("SELECT name, model_id FROM main.parameters WHERE id=?", (int(pid),))
    if p and p["model_id"]:
        _unlocked(store, p["model_id"])
    if p:
        users = store.q("SELECT id FROM main.model_inputs WHERE formula LIKE ?", (f"%{p['name']}%",))
        users = [u for u in users if p["name"] in fm.names_in(store.get_input(u["id"])["formula"])]
        if users:
            raise ApiError(f"'{p['name']}' is used in {len(users)} formula(s). Change those first.")
    store.delete_parameter(int(pid))
    return {"ok": True}


@route("GET", "/api/scenarios")
def scen_list(st, body, q):
    return {"scenarios": st.store.scenarios()}


@route("POST", "/api/scenarios")
def scen_save(st, body, q):
    try:
        return {"id": st.store.save_scenario(body)}
    except ValueError as e:
        raise ApiError(str(e))


@route("DELETE", r"/api/scenarios/(\d+)")
def scen_delete(st, body, q, sid):
    st.store.delete_scenario(int(sid))
    return {"ok": True}


@route("POST", "/api/compare-scenarios")
def scen_compare(st, body, q):
    mid, mids = _need(body, "model_id", "method_ids")
    return _calc_error(calc.compare_scenarios, st.store, int(mid), [int(x) for x in mids], body.get("scenario_ids") or [],
                       bg=_bg(body))


# ------------------------------------------------------------------ calculate, analyses, export
def _mc_key(model_id, method_ids, scenario, bg=None):
    return (int(model_id), tuple(sorted(int(x) for x in method_ids)), scenario or None,
            (bg or {}).get("id"), (bg or {}).get("year"))


def _calc(st, body, top=12):
    mid, mids = _need(body, "model_id", "method_ids")
    scen = int(body["scenario"]) if body.get("scenario") else None
    bg = _bg(body)
    res = _calc_error(calc.run, st.store, int(mid), [int(x) for x in mids], top=top,
                      mc_iterations=int(body.get("mc_iterations") or 0),
                      sensitivity_pct=_num(body.get("sensitivity_pct") or 10, "Sensitivity range"),
                      nw_set=body.get("nw_set") or None, scenario=scen,
                      horizon=_num(body.get("horizon") or 100, "Time horizon"), bg=bg)
    if scen:
        res["scenario_name"] = st.store.one("SELECT name FROM main.scenarios WHERE id=?", (scen,))["name"]
    full = st.mc_results.get(_mc_key(mid, mids, scen, bg))
    if full and body.get("use_full_mc", True):
        res["uncertainty"] = full
    return res


@route("POST", "/api/calculate")
def calculate(st, body, q):
    t = time.time()
    res = _calc(st, {**body, "use_full_mc": False})
    res["seconds"] = round(time.time() - t, 2)
    res["lci_total"] = len(res["lci"])
    res["lci"] = res["lci"][:300]
    return res


@route("POST", "/api/uncertainty")
def uncertainty(st, body, q):
    ids, mids = _need(body, "model_ids", "method_ids")
    ids, mids = [int(x) for x in ids], [int(x) for x in mids]
    scen = int(body["scenario"]) if body.get("scenario") else None
    iterations = int(_num(body.get("iterations") or 200, "Iterations"))
    store = st.store
    bg = _bg(body)

    def job(progress, cancelled):
        try:
            out = calc.full_mc(store, ids, mids, iterations, progress=progress, cancelled=cancelled, scenario=scen, bg=bg,
                               confidence=float(body.get("confidence") or 0.95))
        except calc.LCAError as e:
            raise ValueError(str(e))
        for m in out["models"]:
            st.mc_results[_mc_key(m["id"], mids, scen, bg)] = {"mode": out["mode"], "iterations": out["iterations"],
                                                           "methods": m["methods"], "note": out["note"]}
        return out
    return {"job": st.start_job("Monte Carlo simulation", job, exclusive=False)}


@route("POST", "/api/sobol")
def sobol(st, body, q):
    mid, mids = _need(body, "model_id", "method_ids")
    store = st.store
    n = int(_num(body.get("n") or 512, "Sample size"))
    scen = int(body["scenario"]) if body.get("scenario") else None

    def job(progress, cancelled):
        try:
            return calc.sobol(store, int(mid), [int(x) for x in mids], n=n, scenario=scen, bg=_bg(body))
        except calc.LCAError as e:
            raise ValueError(str(e))
    return {"job": st.start_job("Global sensitivity (Sobol)", job, exclusive=False)}


@route("GET", "/api/tree")
def supply_tree(st, body, q):
    g = lambda k: q.get(k, [""])[0]
    if not g("model_id").isdigit() or not g("method_id").isdigit():
        raise ApiError("model_id and method_id are needed.")
    return _calc_error(calc.tree, st.store, int(g("model_id")), int(g("method_id")), g("node") or None,
                       float(g("amount")) if g("amount") else None, int(g("scenario")) if g("scenario").isdigit() else None)


@route("POST", "/api/compare")
def compare(st, body, q):
    ids, mids = _need(body, "model_ids", "method_ids")
    return _calc_error(calc.compare, st.store, [int(x) for x in ids], [int(x) for x in mids],
                       int(body["scenario"]) if body.get("scenario") else None, bg=_bg(body),
                       equivalence=str(body.get("equivalence") or "")[:2000])


def _export_path(st, body, model, ext):
    if body.get("path"):
        return _check_path(body["path"], must_exist=False)
    safe = re.sub(r"[^\w\-]+", "_", model["name"]).strip("_") or "lca"
    return os.path.join(st.exports, f"{safe}_{time.strftime('%Y%m%d-%H%M%S')}.{ext}")


def _writable(path):
    try:
        with open(path, "ab"):
            pass
    except PermissionError:
        raise ApiError("Cannot write the file. Close it in Word/Excel if it is open, then try again.")


@route("POST", "/api/export/word")
def export_word(st, body, q):
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, body, model, "docx")
    _writable(path)
    report.word_report(path, model, res, st.store.databases(), VERSION)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/export/excel")
def export_excel(st, body, q):
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, body, model, "xlsx")
    _writable(path)
    report.excel_results(path, model, res, VERSION)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/methods-text")
def methods_text(st, body, q):
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    return {"text": report.methods_paragraph(model, res, st.store.databases(), VERSION)}


@route("POST", "/api/diagnostics")
def diagnostics(st, body, q):
    """Zip of logs and system information for support. Contains no project data."""
    path = os.path.join(st.exports, f"cyclia-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.zip")
    info = {"app": APP, "version": VERSION, "python": sys.version, "platform": platform.platform(),
            "frozen": bool(getattr(sys, "frozen", False)), "projects": len(st.ws.list())}
    try:
        info["databases"] = [{k: d[k] for k in ("name", "source", "version", "system_model", "n_activities")}
                             for d in st.store.databases()] if st.project_name else []
    except Exception as e:  # diagnostics must never fail
        info["databases_error"] = str(e)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.json", json.dumps(info, indent=2))
        logf = os.path.join(st.data_dir, "cyclia.log")
        if os.path.exists(logf):
            z.write(logf, "cyclia.log")
        if body.get("app_log") and os.path.exists(str(body["app_log"])):
            z.write(str(body["app_log"]), "desktop.log")
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ settings, API access, examples
@route("GET", "/api/settings")
def settings_get(st, body, q):
    return {"settings": st.settings}


@route("POST", "/api/settings")
def settings_set(st, body, q):
    return {"settings": st.save_settings(body)}


@route("GET", "/api/api-info")
def api_info(st, body, q):
    return dict(st.api_info, file=os.path.join(st.data_dir, "api.json"))


@route("POST", "/api/export/clients")
def export_clients(st, body, q):
    out = []
    for name, text in (("cyclia_client.py", interop.PYTHON_CLIENT), ("cyclia.R", interop.R_CLIENT)):
        path = os.path.join(st.exports, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        out.append({"path": path, "file": name})
    return {"files": out}


@route("GET", "/api/examples")
def examples(st, body, q):
    return {"literature": demo.LITERATURE_EXAMPLE, "external": demo.EXTERNAL_EXAMPLE, "external_template": science.EXT_TEMPLATE}


# ------------------------------------------------------------------ demo and teaching
@route("POST", "/api/demo")
def demo_load(st, body, q):
    base = "Cyclia feature demo"
    name, i = base, 2
    while st.ws.exists(name):
        name = f"{base} {i}"
        i += 1
    author = st.author or "Demo author"

    def job(progress, cancelled):
        store = st.ws.create(name)
        lcia.install_builtin(store)
        store.set_meta("builtin_installed", True)
        progress(5, "Demo database")
        demo.install_database(store, lambda p, m: progress(5 + p * 0.3, m))
        calc.invalidate()
        res = demo.build_project(store, author, lambda p, m: progress(40 + p * 0.6, m))
        st.set_project(name)
        res["project"] = name
        return res
    return {"job": st.start_job("Load the full demo", job)}


@route("GET", "/api/teaching/exercises")
def teach_list(st, body, q):
    return {"exercises": teaching.listing(), "demo_ready": bool(demo.act_id(st.store, "concrete"))}


@route("POST", "/api/teaching/check")
def teach_check(st, body, q):
    ex, ans = _need(body, "id", "answer")
    try:
        return _calc_error(teaching.check, st.store, ex, ans)
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/teaching/key")
def teach_key(st, body, q):
    try:
        return {"key": _calc_error(teaching.answer_key, st.store)}
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/export/answer-key")
def teach_key_doc(st, body, q):
    path = _check_path(body.get("path") or os.path.join(st.exports, "Cyclia exercises answer key.docx"), False)
    _writable(path)
    try:
        _calc_error(teaching.answer_key_docx, st.store, path)
    except ValueError as e:
        raise ApiError(str(e))
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ trust: validation suite and bundles
@route("POST", "/api/validation-suite")
def validation_suite(st, body, q):
    def job(progress, cancelled):
        st.last_validation = trust.validation_suite(progress)
        return st.last_validation
    return {"job": st.start_job("Validation suite", job)}


@route("POST", "/api/export/validation")
def validation_doc(st, body, q):
    if not st.last_validation:
        raise ApiError("Run the validation suite first.")
    path = _check_path(body.get("path") or os.path.join(st.exports, f"Cyclia validation {time.strftime('%Y%m%d-%H%M')}.docx"), False)
    _writable(path)
    trust.validation_report(path, st.last_validation)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/bundle/export")
def bundle_export(st, body, q):
    ids, mids = _need(body, "model_ids", "method_ids")
    path = _check_path(body.get("path") or os.path.join(st.exports, f"{st.project_name} reproducibility "
                                                         f"{time.strftime('%Y%m%d-%H%M')}.zip"), False)
    settings = {"model_ids": ids, "method_ids": mids, "scenario": int(body["scenario"]) if body.get("scenario") else None,
                "bg": _bg(body), "nw_set": body.get("nw_set") or None, "mc_iterations": int(body.get("mc_iterations") or 0),
                "seed": 42}
    project = st.project_name

    def job(progress, cancelled):
        try:
            return trust.export_bundle(st.ws, project, settings, path, progress)
        except calc.LCAError as e:
            raise ValueError(str(e))
    return {"job": st.start_job("Reproducibility bundle", job, exclusive=False)}


@route("POST", "/api/bundle/verify")
def bundle_verify(st, body, q):
    path = _check_path(_need(body, "path")[0])
    st.store  # a project must be open (the library is shared)

    def job(progress, cancelled):
        try:
            return trust.verify_bundle(st.ws, path, progress)
        except calc.LCAError as e:
            raise ValueError(str(e))
    return {"job": st.start_job("Verify bundle", job, exclusive=False)}


# ------------------------------------------------------------------ science: background scenarios, site factors,
# chemicals, external model emissions, map
@route("GET", "/api/bg-scenarios")
def bg_list(st, body, q):
    return {"scenarios": st.store.bg_scenarios(), "rule_types": science.RULE_TYPES}


@route("POST", "/api/bg-scenarios")
def bg_save(st, body, q):
    try:
        sid = st.store.save_bg_scenario(body)
    except ValueError as e:
        raise ApiError(str(e))
    calc.invalidate()
    return {"id": sid}


@route("DELETE", r"/api/bg-scenarios/(\d+)")
def bg_delete(st, body, q, sid):
    st.store.delete_bg_scenario(int(sid))
    calc.invalidate()
    return {"ok": True}


@route("POST", r"/api/bg-scenarios/(\d+)/test")
def bg_test(st, body, q, sid):
    """Apply the rules and report what they change, without a model."""
    year = body.get("year")
    mc = _calc_error(calc.get_mc, st.store, {"id": int(sid), "year": float(year) if year not in (None, "") else None})
    return {"changes": mc.bg_report}


@route("GET", r"/api/models/(\d+)/markets")
def markets(st, body, q, mid):
    try:
        return {"markets": science.markets(st.store, int(mid))}
    except ValueError as e:
        raise ApiError(str(e))


@route("GET", "/api/site-cfs")
def site_list(st, body, q):
    return {"factors": st.store.site_cfs()}


@route("POST", "/api/site-cfs")
def site_save(st, body, q):
    try:
        sid = st.store.save_site_cf(body)
    except ValueError as e:
        raise ApiError(str(e))
    calc.invalidate()
    return {"id": sid}


@route("DELETE", r"/api/site-cfs/(\d+)")
def site_delete(st, body, q, sid):
    st.store.delete_site_cf(int(sid))
    calc.invalidate()
    return {"ok": True}


@route("GET", "/api/chemicals")
def chem_list(st, body, q):
    return {"chemicals": st.store.chemicals(), "fields": {k: {"label": v[0], "unit": v[1], "required": v[2]}
                                                         for k, v in science.CHEM_FIELDS.items()},
            "landscape": science.EQC, "exposure": science.EXPOSURE, "example": demo.SUBSTANCE_X}


@route("POST", "/api/chemicals/preview")
def chem_preview(st, body, q):
    try:
        r = science.toxicity_factors(body.get("props") or {})
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        raise ApiError(str(e) or "The properties give no solution; check the values.")
    except Exception as e:  # singular matrices from extreme inputs
        raise ApiError(f"The fate model could not be solved with these properties ({e}).")
    return r


@route("POST", "/api/chemicals")
def chem_save(st, body, q):
    (name,) = _need(body, "name")
    try:
        r = science.install_chemical(st.store, name, body.get("cas", ""), body.get("props") or {})
    except ValueError as e:
        raise ApiError(str(e))
    calc.invalidate()
    return {"factors": r["factors"], "fate": r["fate"]}


@route("DELETE", r"/api/chemicals/(\d+)")
def chem_delete(st, body, q, cid):
    store = st.store
    c = store.one("SELECT name FROM lib.chemicals WHERE id=?", (int(cid),))
    if c:
        from canon import canon_name
        ids = [m["id"] for m in store.q("SELECT id FROM methods WHERE family=?", (science.SCREEN_FAMILY,))]
        for mid in ids:
            store.x("DELETE FROM cf_raw WHERE method_id=? AND c_name=?", (mid, canon_name(c["name"])))
            store.x("DELETE FROM cfs WHERE method_id=?", (mid,))
        if ids:
            lcia.rematch(store, ids)
        store.delete_chemical(int(cid))
    calc.invalidate()
    return {"ok": True}


@route("POST", r"/api/models/(\d+)/external")
def external(st, body, q, mid):
    store = st.store
    _unlocked(store, mid)
    try:
        if body.get("text"):
            rows = science.read_external(str(body["text"]))
        else:
            rows = science.read_external(_check_path(_need(body, "path")[0]))
        store.snapshot(int(mid), "external model emissions")
        res = science.import_external(store, int(mid), rows, scale=_num(body.get("scale") or 1, "Scale factor"),
                                      aggregate=bool(body.get("aggregate")), stage=body.get("stage", ""),
                                      source=body.get("source") or "external model",
                                      create_missing=bool(body.get("create_missing")))
    except ValueError as e:
        raise ApiError(str(e))
    res["model"] = store.model(int(mid))
    return res


@route("GET", "/api/coords")
def coords(st, body, q):
    return {"coords": science.COORDS, "continents": science.CONTINENTS}


# ------------------------------------------------------------------ productivity
@route("POST", "/api/literature/parse")
def lit_parse(st, body, q):
    text = body.get("text")
    if not text:
        path = _check_path(_need(body, "path")[0])
        try:
            text = productivity.read_document(path)
        except ValueError as e:
            raise ApiError(str(e))
        except Exception as e:
            raise ApiError(f"Could not read that file: {e}")
    rows, skipped = productivity.parse_table(text)
    if not rows:
        raise ApiError("No rows with a name and a number were found. Paste the table with one row per line.")
    return {"rows": productivity.match_rows(st.store, rows[:200], body.get("location", "")), "skipped": skipped[:20]}


@route("POST", r"/api/models/(\d+)/literature")
def lit_add(st, body, q, mid):
    store = st.store
    _unlocked(store, mid)
    res = productivity.add_rows(store, int(mid), body.get("rows") or [], body.get("source", ""))
    res["model"] = store.model(int(mid))
    return res


def _sweep_args(body):
    mid, mids, params = _need(body, "model_id", "method_ids", "params")
    return int(mid), [int(x) for x in mids], params, int(body["scenario"]) if body.get("scenario") else None, _bg(body)


@route("POST", "/api/sweep")
def sweep(st, body, q):
    mid, mids, params, scen, bg = _sweep_args(body)
    try:
        return _calc_error(productivity.sweep, st.store, mid, mids, params, scen, bg)
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/optimise")
def optimise(st, body, q):
    mid, mids, params, scen, bg = _sweep_args(body)
    store = st.store

    def job(progress, cancelled):
        progress(10, "Searching the parameter space")
        try:
            return productivity.optimise(store, mid, mids, params, objective=int(body.get("objective") or 0),
                                         constraints=body.get("constraints"), second_objective=body.get("second_objective"),
                                         samples=int(body.get("samples") or 400), scenario=scen, bg=bg)
        except calc.LCAError as e:
            raise ValueError(str(e))
    return {"job": st.start_job("Optimisation", job, exclusive=False)}


@route("GET", "/api/model-templates")
def tpl_list(st, body, q):
    return {"templates": productivity.templates(st.store)}


@route("POST", "/api/model-templates/apply")
def tpl_apply(st, body, q):
    (tid,) = _need(body, "id")
    tpl = next((t for t in productivity.templates(st.store) if str(t["id"]) == str(tid)), None)
    if not tpl:
        raise ApiError("Template not found.", 404)
    try:
        res = _calc_error(productivity.apply_template, st.store, tpl, body.get("name") or None, body.get("location", ""))
    except ValueError as e:
        raise ApiError(str(e))
    res["model"] = st.store.model(res["model_id"])
    return res


@route("POST", "/api/model-templates/save")
def tpl_save(st, body, q):
    mid, name = _need(body, "model_id", "name")
    try:
        spec = productivity.template_from_model(st.store, int(mid))
        st.store.save_template(name, body.get("category") or "My templates", body.get("description", ""), spec)
    except ValueError as e:
        raise ApiError(str(e))
    return {"ok": True}


@route("DELETE", r"/api/model-templates/(\d+)")
def tpl_delete(st, body, q, tid):
    st.store.delete_template(int(tid))
    return {"ok": True}


@route("GET", r"/api/models/(\d+)/comments")
def comments(st, body, q, mid):
    return {"comments": st.store.comments(int(mid))}


@route("POST", r"/api/models/(\d+)/comments")
def comment_add(st, body, q, mid):
    try:
        st.store.add_comment(int(mid), body.get("input_id"), body.get("author") or st.author, body.get("text"))
    except ValueError as e:
        raise ApiError(str(e))
    return {"comments": st.store.comments(int(mid))}


@route("PATCH", r"/api/comments/(\d+)")
def comment_patch(st, body, q, cid):
    st.store.resolve_comment(int(cid), bool(body.get("resolved")))
    return {"ok": True}


@route("DELETE", r"/api/comments/(\d+)")
def comment_delete(st, body, q, cid):
    st.store.delete_comment(int(cid))
    return {"ok": True}


@route("GET", r"/api/models/(\d+)/versions")
def versions(st, body, q, mid):
    return {"versions": st.store.versions(int(mid)), "lock": st.store.lock_info(int(mid))}


@route("POST", r"/api/models/(\d+)/versions")
def version_save(st, body, q, mid):
    try:
        st.store.save_version(int(mid), body.get("name"), st.author)
    except ValueError as e:
        raise ApiError(str(e))
    return {"versions": st.store.versions(int(mid))}


@route("POST", r"/api/versions/(\d+)/restore")
def version_restore(st, body, q, vid):
    store = st.store
    try:
        v, snap = store.version_snapshot(int(vid))
    except ValueError as e:
        raise ApiError(str(e))
    _unlocked(store, v["model_id"])
    store.snapshot(v["model_id"], f"restore version '{v['name']}'")
    store.save_version(v["model_id"], f"Before restoring '{v['name']}'", st.author)
    store.restore_snapshot(v["model_id"], snap)
    return {"model": store.model(v["model_id"])}


@route("GET", "/api/versions/diff")
def version_diff(st, body, q):
    store = st.store
    g = lambda k: q.get(k, [""])[0]
    if not g("model_id").isdigit():
        raise ApiError("model_id is needed.")
    mid = int(g("model_id"))

    def side(x):
        if x in ("", "current"):
            return store._snapshot_data(mid), "Current model"
        v, snap = store.version_snapshot(int(x))
        if v["model_id"] != mid:
            raise ApiError("That version belongs to another model.")
        return snap, v["name"]
    try:
        a, la = side(g("a"))
        b, lb = side(g("b") or "current")
    except ValueError as e:
        raise ApiError(str(e))
    return productivity.diff_snapshots(store, a, b, la, lb)


@route("POST", r"/api/models/(\d+)/lock")
def model_lock(st, body, q, mid):
    try:
        st.store.set_lock(int(mid), bool(body.get("locked")), st.author, body.get("reason", ""))
    except ValueError as e:
        raise ApiError(str(e))
    return {"model": st.store.model(int(mid))}


# ------------------------------------------------------------------ standards
@route("POST", "/api/epd/check")
def epd_check(st, body, q):
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    prof = epd_profiles.get((model["scope"].get("epd") or {}).get("profile"), _profiles_dir(st))
    return {"checklist": standards.epd_checklist(model, res, prof), "modules": standards.by_module(res),
            "declared": standards.declared_modules(model, res), "columns": standards.COLUMNS}


@route("POST", r"/api/models/(\d+)/epd-info")
def epd_info(st, body, q, mid):
    store = st.store
    _unlocked(store, mid)
    m = store.model(int(mid))
    if not m:
        raise ApiError("Model not found.", 404)
    sc = m["scope"]
    keep = ("manufacturer", "site", "programme", "number", "pcr", "issued", "valid_until", "rsl", "type", "verification",
            "verifier", "biogenic_product", "biogenic_packaging", "description", "declared", "specific_months",
            "prospective", "audience", "programme_statements", "pcr_version", "profile", "fields", "statements_override")
    if body.get("profile") and body["profile"] not in epd_profiles.all_profiles(_profiles_dir(st)):
        raise ApiError("Unknown EPD programme profile.")
    if body.get("fields") is not None and not isinstance(body["fields"], dict):
        raise ApiError("fields must be an object of field values.")
    sc["epd"] = {k: body.get(k) for k in keep if body.get(k) not in (None, "", {}, [])}
    store.save_model({"id": m["id"], "name": m["name"], "product": m["product"], "unit": m["unit"], "amount": m["amount"],
                      "scope": sc})
    return {"model": store.model(int(mid))}


def _std_export(st, body, ext, fn, label):
    res = _calc(st, body, top=60)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, dict(body, path=body.get("path")), dict(model, name=f"{model['name']} {label}"), ext)
    _writable(path)
    try:
        fn(path, model, res)
    except ValueError as e:
        raise ApiError(str(e))
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/export/ilcd-epd")
def export_ilcd_epd(st, body, q):
    res = _calc(st, body, top=60)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, dict(body, path=body.get("path")), dict(model, name=f"{model['name']} ILCD+EPD"), "zip")
    _writable(path)
    try:
        out = ilcd_epd.export(path, model, res, VERSION)
    except ValueError as e:
        raise ApiError(str(e))
    return out


def _profiles_dir(st):
    return os.path.join(st.data_dir, "epd_profiles")


@route("GET", "/api/epd/profiles")
def epd_profile_list(st, body, q):
    return {"profiles": list(epd_profiles.all_profiles(_profiles_dir(st)).values())}


@route("POST", "/api/epd/profiles")
def epd_profile_save(st, body, q):
    try:
        prof = body.get("profile")
        if body.get("path"):
            with open(_check_path(body["path"]), encoding="utf-8-sig") as fh:
                prof = json.load(fh)
        if isinstance(prof, str):
            prof = json.loads(prof)
        if not isinstance(prof, dict):
            raise ValueError("the file is not a JSON object")
        pid = epd_profiles.save_custom(prof, _profiles_dir(st))
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as e:
        raise ApiError(f"The profile could not be loaded: {e}")
    return {"id": pid}


@route("POST", "/api/export/epd-profile")
def export_epd_profile(st, body, q):
    prof = epd_profiles.all_profiles(_profiles_dir(st)).get(body.get("id") or "generic")
    if not prof:
        raise ApiError("Unknown EPD programme profile.")
    prof = dict(prof, id=prof["id"] + "-copy", name=prof["name"] + " (copy)")
    prof.pop("custom", None)
    path = _export_path(st, body, {"name": f"EPD profile {prof['id']}"}, "json")
    _writable(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(prof, fh, ensure_ascii=False, indent=2)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/export/epd")
def export_epd(st, body, q):
    def fn(p, m, r):
        prof = epd_profiles.get((m["scope"].get("epd") or {}).get("profile"), _profiles_dir(st))
        return standards.epd_word(p, m, r, st.store.databases(), VERSION, profile=prof)
    return _std_export(st, body, "docx", fn, "EPD")


@route("POST", "/api/export/epd-excel")
def export_epd_x(st, body, q):
    return _std_export(st, body, "xlsx", standards.epd_excel, "EPD data")


@route("POST", "/api/pef")
def pef(st, body, q):
    res = _calc(st, body, top=60)
    try:
        return standards.pef(res)
    except ValueError as e:
        raise ApiError(str(e))


def _gwp_body(st, body):
    ids = [m["id"] for m in st.store.methods() if m["family"] == lcia.BUILTIN_FAMILY]
    if not ids:
        ids = lcia.install_builtin(st.store)
    return dict(body, method_ids=ids)


@route("POST", "/api/export/iso14067")
def export_14067(st, body, q):
    b = _gwp_body(st, body)
    return _std_export(st, b, "docx", lambda p, m, r: standards.iso14067_word(p, m, r, st.store.databases(), VERSION),
                       "ISO 14067")


@route("POST", "/api/export/ghg")
def export_ghg(st, body, q):
    return _std_export(st, _gwp_body(st, body), "xlsx", standards.ghg_protocol_excel, "GHG Protocol")


@route("POST", "/api/review")
def review(st, body, q):
    model = st.store.model(int(_need(body, "model_id")[0]))
    res = None
    if body.get("method_ids"):
        try:
            res = _calc(st, body)
        except ApiError:
            res = None
    return standards.review_checklist(model, res)


@route("POST", r"/api/models/(\d+)/review")
def review_save(st, body, q, mid):
    store = st.store
    m = store.model(int(mid))
    if not m:
        raise ApiError("Model not found.", 404)
    sc = m["scope"]
    items = sc.get("review_items") or {}
    for k, v in (body.get("items") or {}).items():
        items[k] = {"status": v.get("status", ""), "comment": v.get("comment", ""), "reviewer": st.author}
    sc["review_items"] = items
    store.x("UPDATE main.models SET scope=? WHERE id=?", (json.dumps(sc), int(mid)))
    return {"ok": True}


@route("POST", "/api/export/review")
def export_review(st, body, q):
    model = st.store.model(int(_need(body, "model_id")[0]))
    res = _calc(st, body) if body.get("method_ids") else None
    chk = standards.review_checklist(model, res)
    path = _export_path(st, body, dict(model, name=f"{model['name']} critical review"), "xlsx")
    _writable(path)
    standards.review_excel(path, model, chk)
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ interoperability
@route("POST", "/api/export/brightway")
def export_bw(st, body, q):
    (ids,) = _need(body, "model_ids")
    path = _check_path(body.get("path") or os.path.join(st.exports, f"{st.project_name} for Brightway.xlsx"), False)
    _writable(path)
    return interop.brightway_excel(st.store, ids, path, body.get("db_name") or f"Cyclia {st.project_name}")


@route("POST", "/api/export/openlca")
def export_olca(st, body, q):
    (ids,) = _need(body, "model_ids")
    path = _check_path(body.get("path") or os.path.join(st.exports, f"{st.project_name} for openLCA.zip"), False)
    _writable(path)
    return interop.openlca_jsonld(st.store, ids, path)


@route("POST", "/api/import/brightway")
def import_bw(st, body, q):
    path = _check_path(_need(body, "path")[0])
    try:
        return interop.import_brightway_excel(st.store, path)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        raise ApiError(f"Could not read that Excel file: {e}")


@route("POST", "/api/benchmark-ecoinvent")
def bench_ei(st, body, q):
    path = _check_path(_need(body, "path")[0])
    store = st.store
    sample = int(body.get("sample") or 0)

    def job(progress, cancelled):
        try:
            lci = _check_path(body["lci_path"]) if body.get("lci_path") else None
            st.last_bench = trust.benchmark_ecoinvent(store, path, body.get("family") or "", sample, progress=progress,
                                                      db_name=body.get("db_name") or None, lci_path=lci)
        except calc.LCAError as e:
            raise ValueError(str(e))
        out = dict(st.last_bench)
        out["rows"] = out["rows"][:0]
        return out
    return {"job": st.start_job("Benchmark against ecoinvent", job, exclusive=False)}


@route("POST", "/api/export/benchmark")
def bench_export(st, body, q):
    if not getattr(st, "last_bench", None):
        raise ApiError("Run the benchmark first.")
    path = _check_path(body.get("path") or os.path.join(st.exports, f"Cyclia benchmark {time.strftime('%Y%m%d-%H%M')}.xlsx"), False)
    _writable(path)
    trust.benchmark_excel(path, st.last_bench)
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ official reference data
@route("GET", "/api/ef31")
def ef31_info(st, body, q):
    return {"families": official.ef_families(st.store), "set": official.EF31_SET, "source": official.EF31_SOURCE,
            "factors": [{"category": k, "normalisation": nf, "weighting_percent": wf, "unit": u}
                        for k, nf, wf, u, _ in official.EF31]}


@route("POST", "/api/ef31/install")
def ef31_install(st, body, q):
    (family,) = _need(body, "family")
    try:
        r = official.install_ef31_nw(st.store, family)
    except ValueError as e:
        raise ApiError(str(e))
    calc.invalidate()
    return r


@route("POST", "/api/cf-table/preview")
def cf_table_preview(st, body, q):
    path = _check_path(_need(body, "path")[0])
    try:
        return official.preview_table(path, body.get("sheet") or None)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        raise ApiError(f"Could not read that file: {e}")


@route("POST", "/api/import/cf-table")
def cf_table_import(st, body, q):
    path = _check_path(_need(body, "path")[0])
    mapping = body.get("mapping") or {}
    return _import_job(st, f"Import {mapping.get('family') or 'factors'}",
                       lambda s, p: official.import_cas_table(s, path, mapping, p))


@route("POST", "/api/import/scenario-file")
def scenario_file(st, body, q):
    path = _check_path(_need(body, "path")[0])
    store = st.store

    def job(progress, cancelled):
        try:
            return science.import_scenario_file(store, path, body.get("prefix", ""), progress)
        finally:
            calc.invalidate()
    return {"job": st.start_job("Import scenario file", job, exclusive=False)}


# ------------------------------------------------------------------ professional analyses (1.3.2)
@route("POST", "/api/cff/preview")
def cff_preview(st, body, q):
    try:
        lines, v = analysis.cff_lines(body.get("params") or {})
    except ValueError as e:
        raise ApiError(str(e))
    return {"lines": [{"role": r, "label": analysis.CFF_LABEL[r], "coefficient": c, "credit": cr,
                       "unit": "MJ per kg" if r in analysis.CFF_ENERGY else "per unit of material"} for r, c, cr in lines],
            "parameters": v}


@route("POST", r"/api/models/(\d+)/cff")
def cff_apply(st, body, q, mid):
    store = st.store
    _unlocked(store, mid)
    mass = _num(_need(body, "mass")[0], "Mass")
    try:
        res = analysis.apply_cff(store, int(mid), mass, body.get("unit") or "kg", body.get("params") or {},
                                 {k: int(v) for k, v in (body.get("datasets") or {}).items() if v},
                                 body.get("stage_production") or "", body.get("stage_eol") or "")
    except ValueError as e:
        raise ApiError(str(e))
    return {**res, "model": store.model(int(mid))}


@route("POST", "/api/db-compare")
def db_compare(st, body, q):
    a, b, mids = _need(body, "db_a", "db_b", "method_ids")
    store = st.store
    act_ids = None
    if body.get("only_project"):
        act_ids = sorted({i["ref_id"] for m in store.models() for i in store.model(m["id"])["inputs"]
                          if i["kind"] == "activity" and i["ref_id"] and not i["missing"]})
        if not act_ids:
            raise ApiError("No model of this project uses a dataset yet. Compare a sample instead.")
    sample = int(_num(body.get("sample") or 100, "Sample size"))
    if not 5 <= sample <= 2000:
        raise ApiError("Sample size must be between 5 and 2000.")

    def job(progress, cancelled):
        return analysis.compare_databases(store, int(a), int(b), [int(x) for x in mids], act_ids, sample, progress=progress)
    return {"job": st.start_job("Compare databases", job, exclusive=False)}


@route("POST", r"/api/models/(\d+)/relink")
def relink(st, body, q, mid):
    store = st.store
    a, b = _need(body, "db_from", "db_to")
    try:
        if body.get("apply"):
            for m_ in analysis.relink_plan(store, int(mid), int(a), int(b))["models"]:
                _unlocked(store, m_["id"])
        res = analysis.relink_plan(store, int(mid), int(a), int(b), bool(body.get("apply")),
                                   [int(x) for x in body.get("method_ids") or []])
    except ValueError as e:
        raise ApiError(str(e))
    if res["applied"]:
        res["model"] = store.model(int(mid))
    return res


@route("POST", "/api/relink/undo")
def relink_undo(st, body, q):
    ids = _need(body, "model_ids")[0]
    res = analysis.undo_migration(st.store, [int(x) for x in ids])
    return res


@route("POST", "/api/export/executive")
def export_executive(st, body, q):
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, body, dict(model, name=f"{model['name']} summary"), "docx")
    _writable(path)
    report.executive_summary(path, model, res, VERSION)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/export/figures")
def export_figures(st, body, q):
    import tempfile
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    path = _export_path(st, body, dict(model, name=f"{model['name']} figures"), "zip")
    _writable(path)
    with tempfile.TemporaryDirectory() as tmp:
        files = report.figures(tmp, res)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(f, os.path.basename(f))
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/report-centre")
def report_centre(st, body, q):
    """What each report needs, and whether this model has it."""
    res = _calc(st, body)
    model = st.store.model(int(body["model_id"]))
    sc = model["scope"] or {}
    errors = [c for c in res["checks"] if c["level"] == "error"]
    cats = " ".join(r["category"].lower() for r in res["results"])
    fams = " ".join(r["family"] for r in res["results"])
    chk = standards.epd_checklist(model, res, epd_profiles.get((model["scope"].get("epd") or {}).get("profile"), _profiles_dir(st)))

    def item(ok, text, level="required"):
        return {"ok": bool(ok), "text": text, "level": level}
    has = lambda k: bool(str(sc.get(k) or "").strip())
    lines = res["lines"]
    missing_cf = [r["category"] for r in res["results"] if r["cfs_matched"] == 0]
    alloc_needed = res.get("allocation_share", 1) < 1 or bool(sc.get("coproducts"))
    comparative = (sc.get("comparative") or "").startswith("Yes")
    u = res.get("uncertainty")
    base = [item(not errors, "No errors in the checks"), item(has("goal"), "Goal stated (ISO 14044 4.2.2)"),
            item(has("boundary"), "System boundary stated (4.2.3.3)")]
    iso = [
        item(has("goal"), "Goal of the study (4.2.2)"),
        item(has("reasons"), "Reasons for carrying out the study (4.2.2)"),
        item(has("application"), "Intended application (4.2.2)"),
        item(has("audience"), "Intended audience (4.2.2)"),
        item(model.get("unit") and model.get("product") and model.get("amount"), "Functional unit and reference flow (4.2.3.2)"),
        item(has("boundary"), "System boundary (4.2.3.3)"),
        item(has("cutoff"), "Cut-off criteria (4.2.3.3.3)"),
        item(has("allocation") or not alloc_needed, "Allocation procedure (4.2.3.3, 4.3.4)"),
        item(has("approach"), "Modelling approach, attributional or consequential (4.2.3.3)"),
        item(has("dq_requirements"), "Data quality requirements (4.2.3.6)"),
        item(has("assumptions"), "Assumptions (4.2.3.1)"),
        item(lines and not any(l.get("missing") for l in lines), "Inventory complete: every line linked to data (4.3)"),
        item(not missing_cf, "Impact method covers every selected category (4.4)" +
             (f": no factor in {', '.join(missing_cf)}" if missing_cf else "")),
        item(not errors, "No errors in the completeness and consistency checks (4.5.3)"),
        item(True, "Contribution and sensitivity analysis (4.5.3.3, calculated by Cyclia)"),
        item(has("conclusions"), "Conclusions (4.5.4)"),
        item(has("limitations"), "Limitations (4.5.4)"),
        item(has("recommendations"), "Recommendations (4.5.4)", "recommended"),
        item(not comparative or (sc.get("review_status") in ("panel", "verified")),
             "Critical review by a panel for a public comparative assertion (6.4)" if comparative else
             "Critical review where required (6.1)"),
        item(has("geography") and has("period"), "Geographical and time coverage (4.2.3.6.2)", "recommended"),
        item(has("technology"), "Technological coverage (4.2.3.6.2)", "recommended"),
        item(bool(u), "Uncertainty analysis (4.5.3.3)", "recommended"),
        item(bool(u) and all(m.get("converged") for m in u["methods"]), "Monte Carlo converged", "recommended") if u else None,
        item(any(l.get("data_type") for l in lines), "Data type (primary or secondary) stated for the lines", "recommended"),
        item(any(l.get("source_ref") or l.get("comment") for l in lines), "Data sources documented (4.2.3.6.3)", "recommended"),
    ]
    iso = [x for x in iso if x]
    reports = [
        {"id": "word", "title": "ISO 14044 LCA report", "for": "Theses, papers, consultancy reports", "needs": iso},
        {"id": "executive", "title": "Executive summary", "for": "Managers and decision makers (2 pages)",
         "needs": base + [item(has("conclusions"), "Conclusions written (step 6)"),
                          item(has("limitations"), "Limitations written (step 6)", "recommended")]},
        {"id": "excel", "title": "Results workbook", "for": "Your own charts and further analysis", "needs": [item(True, "Always available")]},
        {"id": "figures", "title": "Figures for a journal", "for": "Contribution charts as 300 dpi PNG and SVG",
         "needs": [item(len(res["results"]) >= 1, "At least one impact category")]},
        {"id": "epd", "title": "EPD (ISO 14025:2026, EN 15804+A2)", "for": "Construction products",
         "needs": [item(i["ok"], i["text"]) for i in chk["items"]]},
        {"id": "iso14067", "title": "Carbon footprint (ISO 14067)", "for": "Product carbon footprint",
         "needs": [item("climate" in cats, "A climate change category selected"),
                   item("IPCC" in fams or "GWP" in fams or "climate" in cats, "IPCC GWP100 method")] + base[:1]},
        {"id": "ghg", "title": "GHG Protocol workbook", "for": "Corporate and product GHG reporting",
         "needs": [item("climate" in cats, "A climate change category selected")]},
        {"id": "review", "title": "Critical review checklist", "for": "The reviewer (ISO 14044 6, ISO 14071)",
         "needs": [item(True, "Always available")]},
    ]
    for r in reports:
        req = [n for n in r["needs"] if n["level"] == "required"]
        r["met"] = sum(n["ok"] for n in req)
        r["total"] = len(req)
        r["recommended_open"] = sum(1 for n in r["needs"] if n["level"] == "recommended" and not n["ok"])
    return {"reports": reports, "review_status": sc.get("review_status") or ""}


@route("POST", "/api/dashboard")
def dashboard(st, body, q):
    """Overview of all models of the project; with method_ids, also their results and data quality."""
    store = st.store
    mids = [int(x) for x in body.get("method_ids") or []]
    out = []
    for m in store.models():
        full = store.model(m["id"])
        ins = full["inputs"]
        sc = full["scope"] or {}
        row = {"id": m["id"], "name": m["name"], "fu": report.fu_text(full), "n_inputs": len(ins),
               "default_pedigree": sum(1 for i in ins if list(i["pedigree"]) == [3, 3, 3, 3, 3]),
               "typed": sum(1 for i in ins if i.get("data_type")), "primary": sum(1 for i in ins if i.get("data_type") == "primary"),
               "missing": sum(1 for i in ins if i["missing"]), "conclusions": bool(sc.get("conclusions")),
               "review_status": sc.get("review_status") or "", "locked": bool(sc.get("locked")),
               "approach": sc.get("approach") or ""}
        if mids and ins:
            try:
                r = calc.run(store, m["id"], mids, top=3)
                row["results"] = [{"category": x["category"], "unit": x["unit"], "total": x["total"]} for x in r["results"]]
                dq = {(c["family"], c["category"], c["indicator"]): c["dqr"] for c in r["data_quality"]["by_category"]}
                row["dqr"] = [dq.get((x["family"], x["category"], x["indicator"])) for x in r["results"]]
                row["errors"] = sum(1 for c in r["checks"] if c["level"] == "error")
                row["warnings"] = sum(1 for c in r["checks"] if c["level"] == "warning")
                if r.get("lcc"):
                    row["lcc"] = {"total": r["lcc"]["total"], "currency": r["lcc"]["currency"]}
            except calc.LCAError as e:
                row["error"] = str(e)
        out.append(row)
    return {"models": out}


@route("GET", "/api/allocation-overview")
def allocation_overview(st, body, q):
    """Every model of the project with its multi-functionality handling: allocation rule and share, co-products,
    avoided products (system expansion), module D, and where the model is used."""
    store = st.store
    models = store.models()
    used_in = {}
    for m in models:
        for i in store.model(m["id"])["inputs"]:
            if i["kind"] == "model" and i["ref_id"]:
                used_in.setdefault(i["ref_id"], []).append(m["name"])
    out = []
    for m in models:
        full = store.model(m["id"])
        sc = full["scope"] or {}
        share = calc.allocation_share(sc)
        basis = sc.get("alloc_basis") or ""
        cps = sc.get("coproducts") or []
        av = [i["label"] or i["target"]["name"] for i in full["inputs"] if i["avoided"]]
        rule = {"mass": "mass", "price": "economic value", "energy": "energy content",
                "physical": f"physical causality ({sc.get('alloc_property') or 'property'})"}.get(basis, "manual share" if share < 1 else "")
        issues = []
        if share < 1 and not (sc.get("allocation") or "").strip():
            issues.append("allocation procedure not described")
        if basis and not cps:
            issues.append("allocation basis chosen but no co-products entered")
        if basis == "physical" and not sc.get("alloc_property"):
            issues.append("physical property not named")
        if share < 1 and (sc.get("approach") or "").startswith("conseq"):
            issues.append("consequential study with allocation: use system expansion")
        if share < 1 and av:
            issues.append("allocation and system expansion in the same model: check for double counting")
        out.append({"id": m["id"], "name": m["name"], "share": share, "rule": rule,
                    "coproducts": [{"name": c.get("name") or "", "mass": c.get("mass"), "price": c.get("price"),
                                    "energy": c.get("energy"), "physical": c.get("physical")} for c in cps],
                    "main": {k: sc.get(f"main_{k}") for k in ("mass", "price", "energy", "physical")},
                    "avoided": av, "module_d": sum(1 for i in full["inputs"] if calc.is_module_d(sc, i["stage"])),
                    "used_in": used_in.get(m["id"], []), "procedure": sc.get("allocation") or "", "issues": issues})
    return {"models": out, "note": "ISO 14044 4.3.4.2: avoid allocation by subdivision or system expansion where possible; "
                                   "otherwise allocate by physical relationships, and only then by other relationships "
                                   "such as economic value."}


# ------------------------------------------------------------------ 1.3.5: factor matching, regional, social, MFA
@route("POST", "/api/factor-match")
def factor_match(st, body, q):
    path = _check_path(_need(body, "path")[0])
    mids = _need(body, "method_ids")[0]
    res_path = _check_path(body["results_path"]) if body.get("results_path") else None
    store = st.store

    def job(progress, cancelled):
        progress(5, "Reading the external factors")
        ext, kind = factormatch.read_external(path)
        ext_res = factormatch.read_external_results(res_path) if res_path else None
        progress(30, "Comparing flow by flow")
        res = factormatch.compare(store, [int(x) for x in mids], ext, kind, [m["id"] for m in store.models()], ext_res,
                                  body.get("pairs") or None)
        st.last_factor_match = res
        return res
    return {"job": st.start_job("Factor matching validation", job, exclusive=False)}


@route("GET", "/api/brightway/status")
def brightway_status(st, body, q):
    if not brightway_check.available():
        return {"available": False}
    return {"available": True, **brightway_check.versions()}


@route("POST", "/api/brightway/compare")
def brightway_compare(st, body, q):
    db = _need(body, "db_id")[0]
    mids = [int(x) for x in (body.get("method_ids") or [])]
    if not mids:
        raise ApiError("Choose the impact categories in step 4 first.")
    if not brightway_check.available():
        raise ApiError("Brightway (bw2calc) is not available in this installation.")
    sample = int(body.get("sample") or 0)
    store = st.store

    def job(progress, cancelled):
        try:
            st.last_bw = brightway_check.compare(store, int(db), mids, sample, progress=progress)
        except ValueError as e:
            raise ApiError(str(e))
        return st.last_bw
    return {"job": st.start_job("Comparison with Brightway", job, exclusive=False)}


@route("POST", "/api/export/brightway-check")
def export_brightway_check(st, body, q):
    res = getattr(st, "last_bw", None)
    if not res:
        raise ApiError("Run the comparison with Brightway first.")
    path = _export_path(st, body, {"name": "Cyclia compared with Brightway"}, "xlsx")
    _writable(path)
    brightway_check.excel(path, res)
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ custom data entry
def _cd(fn, *a, **k):
    try:
        return fn(*a, **k)
    except custom_data.CustomDataError as e:
        raise ApiError(str(e))


def _cd_free(st):
    if st.import_lock.locked():
        raise ApiError("An import is running. Wait until it finishes.")


@route("GET", "/api/custom")
def custom_overview(st, body, q):
    store = st.store
    custom_data.ensure_schema(store)
    return {"databases": custom_data.databases(store), "compartments": custom_data.COMPARTMENTS,
            "units": [u for v in units._ORDER.values() for u in v] + [r["name"] for r in store.q(
                "SELECT name FROM custom_units ORDER BY name")],
            "uncertainty": list(custom_data.UNCERTAINTY) + ["pedigree"],
            "methods": [{**dict(m), "unlisted": sc[0], "unlisted_reason": sc[1]}
                        for m in store.q("SELECT m.id, m.family, m.category, m.indicator, m.unit FROM methods m "
                                         "JOIN custom_items i ON i.ref_id=m.id AND i.kind='method' ORDER BY "
                                         "m.family, m.category")
                        for sc in [custom_data.method_scopes(store).get(m["id"], ("unknown", ""))]],
            "example_name": custom_data.EXAMPLE_NAME,
            "elementary_flows": custom_data.elementary_flows(store)}


@route("GET", r"/api/custom/(\d+)")
def custom_db(st, body, q, db_id):
    if not custom_data.is_custom(st.store, db_id):
        raise ApiError("Custom database not found.", 404)
    return custom_data.contents(st.store, db_id)


@route("POST", "/api/custom/database")
def custom_create_db(st, body, q):
    _cd_free(st)
    try:
        db = custom_data.create_database(st.store, body.get("name"), body.get("description") or "",
                                         body.get("author") or "", body.get("licence") or "",
                                         body.get("geography") or "", body.get("reference_period") or "")
    except ValueError as e:
        raise ApiError(str(e))
    return {"db_id": db}


@route("POST", r"/api/custom/(\d+)/product")
def custom_product(st, body, q, db_id):
    _cd_free(st)
    return {"uuid": _cd(custom_data.save_product, st.store, int(db_id), body)}


@route("POST", r"/api/custom/(\d+)/process")
def custom_process(st, body, q, db_id):
    _cd_free(st)
    return {"uuid": _cd(custom_data.save_process, st.store, int(db_id), body)}


@route("POST", "/api/custom/elementary")
def custom_elementary(st, body, q):
    _cd_free(st)
    return {"uuid": _cd(custom_data.save_elementary, st.store, body)}


@route("POST", "/api/custom/exchange")
def custom_exchange(st, body, q):
    _cd_free(st)
    (proc,) = _need(body, "process")
    return {"id": _cd(custom_data.save_exchange, st.store, proc, body)}


@route("POST", "/api/custom/exchange/delete")
def custom_exchange_delete(st, body, q):
    _cd_free(st)
    proc, eid = _need(body, "process", "id")
    _cd(custom_data.delete_exchange, st.store, proc, eid)
    return {"ok": True}


@route("POST", "/api/custom/delete")
def custom_delete(st, body, q):
    _cd_free(st)
    (uid,) = _need(body, "uuid")
    it = st.store.one("SELECT kind, ref_id FROM custom_items WHERE uuid=?", (uid,))
    if it and it["kind"] == "process" and it["ref_id"]:
        usage = st.ws.activity_usage(it["ref_id"])
        if usage:
            raise ApiError("Used by models in: " + ", ".join(f"{u['project']} ({u['lines']} lines)" for u in usage) +
                           ". Remove those lines first.")
    _cd(custom_data.delete_item, st.store, uid)
    return {"ok": True}


@route("POST", "/api/custom/method")
def custom_method(st, body, q):
    return {"method_id": _cd(custom_data.create_method, st.store, body.get("family"), body.get("category"),
                             body.get("indicator"), body.get("unit"), body.get("source"), body.get("author") or "",
                             body.get("unlisted") or "unknown", body.get("unlisted_reason") or "")}


@route("GET", "/api/custom/units")
def custom_units(st, body, q):
    return custom_data.units_list(st.store)


@route("POST", "/api/custom/units")
def custom_unit_save(st, body, q):
    return {"name": _cd(custom_data.save_unit, st.store, body)}


@route("POST", "/api/custom/units/delete")
def custom_unit_delete(st, body, q):
    (name,) = _need(body, "name")
    _cd(custom_data.delete_unit, st.store, name)
    return {"ok": True}


@route("POST", r"/api/custom/(\d+)/parameters")
def custom_db_params(st, body, q, db_id):
    _cd_free(st)
    _cd(custom_data.set_database_parameters, st.store, int(db_id), body.get("parameters") or [], body.get("author") or "")
    return {"parameters": custom_data._db_params(st.store, int(db_id))}


@route("POST", "/api/custom/layout")
def custom_layout(st, body, q):
    uid, x, y = _need(body, "uuid", "x", "y")
    _cd(custom_data.save_layout, st.store, uid, x, y)
    return {"ok": True}


@route("POST", "/api/custom/method/scope")
def custom_method_scope(st, body, q):
    (mid,) = _need(body, "method_id")
    _cd(custom_data.set_method_scope, st.store, mid, body.get("unlisted"), body.get("unlisted_reason") or "",
        body.get("author") or "")
    return {"ok": True}


@route("POST", "/api/custom/method/delete")
def custom_method_delete(st, body, q):
    (mid,) = _need(body, "method_id")
    _cd(custom_data.delete_method, st.store, mid)
    return {"ok": True}


@route("GET", "/api/custom/history")
def custom_history(st, body, q):
    item = (q.get("item") or [""])[0]
    if not item:
        raise ApiError("Missing field: item")
    return {"history": custom_data.history(st.store, item)}


@route("POST", "/api/custom/example")
def custom_example(st, body, q):
    _cd_free(st)
    return _cd(custom_data.example, st.store)


@route("POST", "/api/custom/factor")
def custom_factor(st, body, q):
    mid, flow, status = _need(body, "method_id", "flow_uuid", "status")
    _cd(custom_data.save_factor, st.store, mid, flow, status, body.get("value"), body.get("unit"),
        body.get("source") or "", body.get("comment") or "", body.get("author") or "")
    return {"ok": True}


@route("POST", "/api/custom/factor/delete")
def custom_factor_delete(st, body, q):
    mid, flow = _need(body, "method_id", "flow_uuid")
    _cd(custom_data.delete_factor, st.store, mid, flow)
    return {"ok": True}


@route("POST", "/api/custom/factors")
def custom_factor_table(st, body, q):
    mids = [int(x) for x in (body.get("method_ids") or [])]
    if not mids:
        raise ApiError("Choose the impact categories first.")
    return {"rows": custom_data.factor_table(st.store, mids)}


@route("GET", r"/api/custom/(\d+)/check")
def custom_check(st, body, q, db_id):
    return _cd(custom_data.check, st.store, int(db_id))


@route("POST", r"/api/custom/(\d+)/export")
def custom_export(st, body, q, db_id):
    doc = _cd(custom_data.export_json, st.store, int(db_id))
    path = _export_path(st, body, {"name": doc["database"]["name"] + " (Cyclia custom data)"}, "json")
    _writable(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return {"path": path, "file": os.path.basename(path)}


@route("POST", "/api/custom/import")
def custom_import(st, body, q):
    _cd_free(st)
    (path,) = _need(body, "path")
    try:
        with open(_check_path(path), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        raise ApiError(f"The file could not be read: {e}")
    try:
        return {"db_id": custom_data.import_json(st.store, doc, body.get("name") or None)}
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/export/compare-kit")
def export_compare_kit(st, body, q):
    db = _need(body, "db_id")[0]
    mids = body.get("method_ids") or []
    d = st.store.one("SELECT name FROM databases WHERE id=?", (int(db),))
    if not d:
        raise ApiError("Database not found.", 404)
    if re.search(r"ecoinvent", d["name"], re.I) and not body.get("confirm_licence"):
        raise ApiError("This looks like ecoinvent: its licence does not allow sharing the data. Build the kit from data you may share.")
    path = _export_path(st, body, {"name": f"Cyclia comparison kit {d['name']}"}, "zip")
    _writable(path)
    try:
        return compare_kit.build(st.store, int(db), mids, path, VERSION)
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/export/factor-match")
def export_factor_match(st, body, q):
    res = getattr(st, "last_factor_match", None)
    if not res:
        raise ApiError("Run the factor matching validation first.")
    path = _export_path(st, body, {"name": "Cyclia factor matching validation"}, "xlsx")
    _writable(path)
    factormatch.to_excel(path, res, VERSION)
    return {"path": path, "file": os.path.basename(path)}


@route("GET", r"/api/models/(\d+)/marginal")
def marginal(st, body, q, mid):
    try:
        return analysis.marginal_guidance(st.store, int(mid))
    except ValueError as e:
        raise ApiError(str(e))


@route("GET", "/api/regional/status")
def regional_status(st, body, q):
    return {"status": regional.status(st.store), "templates": {"AWARE": regional.AWARE_TEMPLATE, "LANCA": regional.LANCA_TEMPLATE},
            "lanca_indicators": list(regional.LANCA_INDICATORS)}


@route("POST", "/api/regional/geojson")
def regional_geojson(st, body, q):
    method = _need(body, "method")[0]
    text = body.get("text")
    if body.get("path"):
        with open(_check_path(body["path"]), encoding="utf-8-sig") as fh:
            text = fh.read()
    try:
        return regional.import_geojson(st.store, method, text or "", body.get("id_property") or "id", body.get("source", ""))
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/regional/locate")
def regional_locate(st, body, q):
    try:
        return {"found": regional.locate(st.store, body.get("method") or "AWARE", float(body["lat"]), float(body["lon"]))}
    except (KeyError, TypeError, ValueError):
        raise ApiError("Give lat and lon in decimal degrees.")


@route("POST", "/api/regional/sqi")
def regional_sqi(st, body, q):
    try:
        return regional.sqi_aggregate(st.store, body.get("normalisation") or {}, body.get("weights"), body.get("source", ""),
                                      body.get("replace", True) is not False)
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/regional/import")
def regional_import(st, body, q):
    method = _need(body, "method")[0]
    text = body.get("text")
    if body.get("path"):
        with open(_check_path(body["path"]), encoding="utf-8-sig") as fh:
            text = fh.read()
    if not text:
        raise ApiError("Give a CSV file or paste the table.")
    try:
        return regional.import_factors(st.store, method, text, body.get("source") or os.path.basename(body.get("path") or ""))
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/regional/demo")
def regional_demo(st, body, q):
    return {"status": regional.demo_factors(st.store)}


@route("POST", "/api/regional/assess")
def regional_assess(st, body, q):
    mid, method = _need(body, "model_id", "method")
    try:
        return regional.aware(st.store, int(mid)) if str(method).upper() == "AWARE" else regional.lanca(st.store, int(mid))
    except (ValueError, calc.LCAError) as e:
        raise ApiError(str(e))


@route("POST", "/api/slca/import-olca")
def slca_import_olca(st, body, q):
    path = _check_path(_need(body, "path")[0])
    mapping = ""
    if body.get("mapping_path"):
        with open(_check_path(body["mapping_path"]), encoding="utf-8-sig") as fh:
            mapping = fh.read()
    store = st.store

    def job(p, c):
        p(10, "Reading the social data")
        return slca.import_olca_social(store, path, mapping, body.get("replace", True) is not False, body.get("source", ""))
    return {"job": st.start_job("Import social data (openLCA)", job)}


@route("POST", "/api/slca/import")
def slca_import(st, body, q):
    text = body.get("text")
    if body.get("path"):
        with open(_check_path(body["path"]), encoding="utf-8-sig") as fh:
            text = fh.read()
    if not text:
        raise ApiError("Give a CSV file or paste the table.")
    try:
        return slca.import_data(st.store, text, body.get("source") or os.path.basename(body.get("path") or ""))
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/slca/demo")
def slca_demo(st, body, q):
    return slca.demo_data(st.store)


@route("GET", "/api/slca/info")
def slca_info(st, body, q):
    n = st.store.one("SELECT COUNT(*) AS n, MIN(source) AS src FROM slca_data")
    return {"rows": n["n"], "source": n["src"] or "", "template": slca.TEMPLATE, "stakeholders": list(slca.STAKEHOLDERS),
            "risk_factors": slca.RISK_FACTORS}


@route("POST", "/api/slca/assess")
def slca_assess(st, body, q):
    mid = _need(body, "model_id")[0]
    try:
        return slca.assess(st.store, int(mid), body.get("factors"))
    except (ValueError, calc.LCAError) as e:
        raise ApiError(str(e))


@route("GET", "/api/mfa/example")
def mfa_example(st, body, q):
    return {"definition": mfa.EXAMPLE}


@route("POST", "/api/mfa/run")
def mfa_run(st, body, q):
    d = body.get("definition")
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except json.JSONDecodeError as e:
            raise ApiError(f"The definition is not valid JSON: {e}")
    try:
        return mfa.run(d or {})
    except (ValueError, KeyError, TypeError) as e:
        raise ApiError(f"MFA: {e}")


@route("POST", "/api/mfa/lca")
def mfa_lca(st, body, q):
    try:
        return mfa.lca(st.store, body.get("definition") or {}, body.get("method_ids") or [], body.get("links") or {})
    except (ValueError, KeyError, TypeError) as e:
        raise ApiError(str(e))


@route("POST", "/api/mfa/mci")
def mfa_mci(st, body, q):
    try:
        return mfa.mci(**{k: float(v) for k, v in body.items() if k in ("Fr", "Fu", "Cr", "Cu", "Ec", "Ef", "L_ratio", "U_ratio")})
    except ValueError as e:
        raise ApiError(str(e))


@route("POST", "/api/crosscheck")
def cross_check(st, body, q):
    mids = _need(body, "method_ids")[0]
    store = st.store
    sample = int(_num(body.get("sample") or 200, "Sample size"))
    if not 5 <= sample <= 5000:
        raise ApiError("Sample size must be between 5 and 5000.")
    model_ids = [m["id"] for m in store.models()] if body.get("models", True) else []

    def job(progress, cancelled):
        res = crosscheck.run(store, [int(x) for x in mids], sample, model_ids=model_ids, progress=progress)
        st.last_crosscheck = res
        return res
    return {"job": st.start_job("Independent cross-check", job, exclusive=False)}


@route("POST", "/api/export/crosscheck")
def export_crosscheck(st, body, q):
    res = getattr(st, "last_crosscheck", None)
    if not res:
        raise ApiError("Run the independent cross-check first.")
    path = _export_path(st, body, {"name": "Cyclia independent cross-check"}, "xlsx")
    _writable(path)
    crosscheck.to_excel(path, res, VERSION)
    return {"path": path, "file": os.path.basename(path)}


# ------------------------------------------------------------------ HTTP plumbing
def make_handler(st, token):
    ui_root = os.path.normpath(UI_DIR)

    class Handler(BaseHTTPRequestHandler):
        server_version = f"{APP}/{VERSION}"

        def log_message(self, fmt, *args):
            if os.environ.get("CYCLIA_DEBUG"):
                sys.stderr.write(fmt % args + "\n")

        def _send(self, code, payload, ctype="application/json"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _static(self, path):
            if path in ("", "/"):
                path = "/index.html"
            full = os.path.normpath(os.path.join(ui_root, unquote(path).lstrip("/")))
            if not full.startswith(ui_root) or not os.path.isfile(full):
                msg = "Not found"
                if path == "/index.html":
                    msg += f": the interface folder {ui_root} has no index.html"
                return self._send(404, msg.encode("utf-8"), "text/plain; charset=utf-8")
            with open(full, "rb") as fh:
                data = fh.read()
            if full.endswith("index.html"):
                data = data.replace(b"__API_TOKEN__", token.encode())
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, data, ctype)

        def _download(self, name):
            full = os.path.normpath(os.path.join(st.exports, os.path.basename(unquote(name))))
            if not os.path.isfile(full):
                return self._send(404, {"error": "File not found"})
            with open(full, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(full)}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, method):
            url = urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._static(url.path) if method == "GET" else self._send(404, {"error": "Not found"})
            q = parse_qs(url.query)
            if not secrets.compare_digest(self.headers.get("X-Token") or q.get("token", [""])[0], token):
                return self._send(403, {"error": "Forbidden"})
            if url.path.startswith("/api/download/") and method == "GET":
                return self._download(url.path[len("/api/download/"):])
            body = {}
            if method in ("POST", "PATCH", "PUT", "DELETE"):
                n = int(self.headers.get("Content-Length") or 0)
                if n > 20_000_000:
                    return self._send(413, {"error": "Request too large"})
                if n:
                    try:
                        body = json.loads(self.rfile.read(n) or b"{}")
                    except json.JSONDecodeError:
                        return self._send(400, {"error": "Invalid JSON"})
                if not isinstance(body, dict):
                    return self._send(400, {"error": "Expected a JSON object"})
            for m, rx, fn in ROUTES:
                if m != method:
                    continue
                hit = rx.match(url.path)
                if hit:
                    try:
                        return self._send(200, _clean(fn(st, body, q, *hit.groups())))
                    except ApiError as e:
                        return self._send(e.code, {"error": str(e)})
                    except (ValueError, KeyError, TypeError) as e:
                        log.exception("bad request %s", url.path)
                        return self._send(400, {"error": f"Invalid request: {e}"})
                    except Exception as e:
                        log.exception("error in %s", url.path)
                        return self._send(500, {"error": f"Unexpected error: {e}. Details are in cyclia.log "
                                                         "(Help > Export diagnostics)."})
            return self._send(404, {"error": "Unknown API route"})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PATCH(self):
            self._handle("PATCH")

        def do_DELETE(self):
            self._handle("DELETE")
    return Handler


def _clean(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return obj


def default_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP)


def main():
    ap = argparse.ArgumentParser(description=f"{APP} LCA engine")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data", default=os.environ.get("CYCLIA_DATA") or default_data_dir())
    ap.add_argument("--token", default=os.environ.get("CYCLIA_TOKEN") or "")
    args = ap.parse_args()
    token = args.token or secrets.token_hex(16)
    os.makedirs(args.data, exist_ok=True)
    logging.basicConfig(filename=os.path.join(args.data, "cyclia.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    st = State(args.data)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(st, token))
    httpd.daemon_threads = True
    st.api_info = {"url": f"http://127.0.0.1:{httpd.server_address[1]}", "token": token, "pid": os.getpid()}
    try:  # lets the Python and R clients find the running engine; readable by this user only
        info_path = os.path.join(args.data, "api.json")
        with open(info_path, "w", encoding="utf-8") as fh:
            json.dump(st.api_info, fh)
        os.chmod(info_path, 0o600)
    except OSError:
        pass
    print(f"CYCLIA_READY port={httpd.server_address[1]}", flush=True)
    if not args.token:
        print(f"Open http://127.0.0.1:{httpd.server_address[1]}/ in a browser.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
