"""Exchange with other LCA software and with code.

* Brightway: export models in the bw2io Excel importer layout (plus a small import script), and read that layout back.
* openLCA: export models as a JSON-LD zip (processes and the flows they need).
* Python and R: clients for the local Cyclia API.
"""
import json
import os
import re
import time
import uuid
import zipfile

from openpyxl import Workbook, load_workbook

import units

NS = uuid.UUID("8d1f7b8e-55a1-4a3c-a6d4-3c0e2f9b6a70")


# ============================================================================ Brightway
def _is_uuid(v):
    return bool(v) and bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", str(v)))


def _model_rows(store, model_id, seen=None):
    seen = seen if seen is not None else set()
    m = store.model(model_id)
    seen.add(model_id)
    subs = []
    exch = [{"name": m["name"], "amount": m["amount"], "unit": m["unit"], "location": "GLO", "type": "production",
             "database": None, "reference product": m["product"] or m["name"]}]
    for i in m["inputs"]:
        amt = i["amount"] * (-1 if i["avoided"] else 1)
        if i["kind"] == "activity" and not i["missing"]:
            a = store.one("SELECT a.name, a.product, a.location, a.unit, a.key, a.product_uuid, d.name AS db, d.source "
                          "FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.id=?", (i["ref_id"],))
            prod_uuid = a["product_uuid"]
            if not prod_uuid and "_" in (a["key"] or "") and _is_uuid(a["key"].split("_")[-1]):
                prod_uuid = a["key"].split("_")[-1]  # ecoSpold2: <activity id>_<product id>
            exch.append({"name": a["name"], "amount": amt, "unit": a["unit"], "location": a["location"], "type": "technosphere",
                         "database": a["db"], "reference product": a["product"], "source key": a["key"],
                         "product_uuid": prod_uuid if _is_uuid(prod_uuid) else None,
                         "provider": a["key"] if a["source"] == "openLCA JSON-LD" and _is_uuid(a["key"]) else None,
                         "comment": i["comment"], "stage": i["stage"], "formula": i["formula"] or ""})
        elif i["kind"] == "flow":
            f = store.one("SELECT name, compartment, subcompartment, unit, uuid FROM flows WHERE id=?", (i["ref_id"],))
            exch.append({"name": f["name"], "amount": amt, "unit": f["unit"],
                         "categories": "::".join(x for x in (f["compartment"], f["subcompartment"]) if x),
                         "type": "biosphere", "database": "biosphere3", "code": f["uuid"], "comment": i["comment"],
                         "stage": i["stage"], "formula": i["formula"] or ""})
        elif i["kind"] == "model":
            sub = store.model(i["ref_id"])
            exch.append({"name": sub["name"], "amount": amt / (sub["amount"] or 1) * sub["amount"], "unit": sub["unit"],
                         "location": "GLO", "type": "technosphere", "database": None,
                         "reference product": sub["product"] or sub["name"], "comment": i["comment"], "stage": i["stage"]})
            if i["ref_id"] not in seen:
                subs.append(i["ref_id"])
        else:
            exch.append({"name": i["label"] or "EPD values", "amount": amt, "unit": i["input_unit"], "type": "skipped",
                         "comment": "EPD fixed values have no equivalent in Brightway and were not exported"})
    out = [(m, exch)]
    for s in subs:
        out += _model_rows(store, s, seen)
    return out


def brightway_excel(store, model_ids, path, db_name="Cyclia export"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cyclia"
    ws.append(["Database", db_name])
    ws.append([])
    params = store.parameters(None)
    if params:
        ws.append(["Project parameters"])
        ws.append(["name", "amount", "formula", "unit"])
        for p in params:
            ws.append([p["name"], p["value"], p["formula"] or "", p["unit"] or ""])
        ws.append([])
    done = set()
    for mid in model_ids:
        for m, exch in _model_rows(store, int(mid)):
            if m["id"] in done:
                continue
            done.add(m["id"])
            ws.append(["Activity", m["name"]])
            ws.append(["code", f"cyclia-{m['id']}"])
            ws.append(["location", "GLO"])
            ws.append(["unit", m["unit"]])
            ws.append(["reference product", m["product"] or m["name"]])
            ws.append(["production amount", m["amount"]])
            if m["parameters"]:
                ws.append(["Parameters"])
                ws.append(["name", "amount", "formula", "unit"])
                for p in m["parameters"]:
                    ws.append([p["name"], p["value"], p["formula"] or "", p["unit"] or ""])
            ws.append(["Exchanges"])
            ws.append(["name", "amount", "unit", "location", "database", "type", "reference product", "categories",
                       "formula", "comment", "stage"])
            for e in exch:
                if e["type"] == "skipped":
                    continue
                ws.append([e["name"], e["amount"], e["unit"], e.get("location", ""), e.get("database") or db_name, e["type"],
                           e.get("reference product", ""), e.get("categories", ""), e.get("formula", ""),
                           e.get("comment", ""), e.get("stage", "")])
            ws.append([])
    wb.save(path)
    script = os.path.splitext(path)[0] + "_import.py"
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(BW_SCRIPT.replace("__FILE__", os.path.basename(path)).replace("__DB__", db_name))
    return {"path": path, "file": os.path.basename(path), "script": script}


BW_SCRIPT = '''"""Import a Cyclia export into Brightway 2.5 (bw2io). Run inside your Brightway project:
    python __FILE___import.py
Background datasets are matched by name, reference product, location and unit to the databases named in the file.
"""
import bw2data as bd
import bw2io as bi

bd.projects.set_current("my project")      # change to your project name
imp = bi.ExcelImporter("__FILE__")
imp.apply_strategies()
for db in {exc.get("database") for act in imp.data for exc in act.get("exchanges", [])}:
    if db and db in bd.databases and db != "__DB__":
        imp.match_database(db, fields=("name", "reference product", "location", "unit"))
imp.match_database(fields=("name", "unit", "location"))
imp.match_database("biosphere3", fields=("name", "unit", "categories"))
imp.statistics()
imp.write_excel(only_unlinked=True)      # lists anything that did not link
if not list(imp.unlinked):
    imp.write_database()
'''


def read_brightway_excel(path):
    """Parse the bw2io Excel layout into activities with exchanges."""
    wb = load_workbook(path, read_only=True, data_only=True)
    acts = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        i = 0
        while i < len(rows):
            r = rows[i]
            if r and str(r[0] or "").strip().lower() == "activity":
                act = {"name": str(r[1] or "").strip(), "meta": {}, "exchanges": [], "parameters": []}
                i += 1
                while i < len(rows) and rows[i] and rows[i][0] not in (None, "") and \
                        str(rows[i][0]).strip().lower() not in ("exchanges", "parameters", "activity"):
                    act["meta"][str(rows[i][0]).strip().lower()] = rows[i][1]
                    i += 1
                if i < len(rows) and rows[i] and str(rows[i][0] or "").strip().lower() == "parameters":
                    head = [str(h or "").strip().lower() for h in rows[i + 1]]
                    i += 2
                    while i < len(rows) and rows[i] and rows[i][0] not in (None, "") and \
                            str(rows[i][0]).strip().lower() not in ("exchanges", "activity"):
                        act["parameters"].append(dict(zip(head, rows[i])))
                        i += 1
                if i < len(rows) and rows[i] and str(rows[i][0] or "").strip().lower() == "exchanges":
                    head = [str(h or "").strip().lower() for h in rows[i + 1]]
                    i += 2
                    while i < len(rows) and rows[i] and any(v not in (None, "") for v in rows[i]) and \
                            str(rows[i][0] or "").strip().lower() != "activity":
                        act["exchanges"].append(dict(zip(head, rows[i])))
                        i += 1
                acts.append(act)
                continue
            i += 1
    if not acts:
        raise ValueError("No 'Activity' blocks found. Use the Brightway (bw2io) Excel layout.")
    return acts


def import_brightway_excel(store, path):
    """Each activity becomes a Cyclia model; technosphere exchanges link to library datasets by name, reference
    product, location and unit; biosphere exchanges link by name and compartment."""
    acts = read_brightway_excel(path)
    created, problems = [], []
    for act in acts:
        prod = [e for e in act["exchanges"] if str(e.get("type", "")).lower() == "production"]
        unit = act["meta"].get("unit") or (prod[0].get("unit") if prod else "")
        amount = float(act["meta"].get("production amount") or (prod[0].get("amount") if prod else 1) or 1)
        mid = store.save_model({"name": act["name"] or "Imported activity", "unit": unit or "unit", "amount": abs(amount),
                                "product": act["meta"].get("reference product") or act["name"],
                                "scope": {"imported_from": os.path.basename(path)}})
        for p in act["parameters"]:
            try:
                store.save_parameter({"model_id": mid, "name": p.get("name"), "value": p.get("amount") or 0,
                                      "formula": p.get("formula") or "", "unit": p.get("unit") or ""})
            except ValueError as e:
                problems.append(f"{act['name']}: parameter {p.get('name')}: {e}")
        for e in act["exchanges"]:
            t = str(e.get("type", "")).lower()
            if t not in ("technosphere", "biosphere", "substitution"):
                continue
            try:
                amt = float(e.get("amount") or 0)
            except (TypeError, ValueError):
                problems.append(f"{act['name']}: amount of '{e.get('name')}' is not a number")
                continue
            if t == "biosphere":
                cats = [c for c in re.split(r"::|/|,", str(e.get("categories") or "")) if c]
                comp = cats[0] if cats else "air"
                f = store.one("SELECT id, unit FROM flows WHERE uuid=?", (e.get("code"),)) if e.get("code") else None
                f = f or store.one("SELECT id, unit FROM flows WHERE lower(name)=lower(?) AND lower(compartment)=lower(?) "
                                   "ORDER BY subcompartment='unspecified' DESC", (e.get("name"), comp))
                if not f:
                    problems.append(f"{act['name']}: flow '{e.get('name')}' ({comp}) not in the library")
                    continue
                kind, ref, tunit = "flow", f["id"], f["unit"]
            else:
                sql = "SELECT a.id, a.unit FROM activities a JOIN databases d ON d.id=a.db_id WHERE lower(a.name)=lower(?)"
                args = [e.get("name")]
                for col, key in (("a.location", "location"), ("a.product", "reference product"), ("d.name", "database")):
                    if e.get(key):
                        sql += f" AND lower({col})=lower(?)"
                        args.append(e[key])
                a = store.one(sql, args) or store.one("SELECT id, unit FROM activities WHERE lower(name)=lower(?)",
                                                      (e.get("name"),))
                if not a:
                    problems.append(f"{act['name']}: dataset '{e.get('name')}' [{e.get('location', '')}] not in the library")
                    continue
                kind, ref, tunit = "activity", a["id"], a["unit"]
            unit = e.get("unit") or tunit
            fac = units.factor(unit, tunit)
            if fac is None:
                problems.append(f"{act['name']}: unit '{unit}' of '{e.get('name')}' does not match '{tunit}'")
                continue
            store.add_input(mid, kind, ref, abs(amt) * fac, label=e.get("name") if kind == "flow" else "",
                            comment=str(e.get("comment") or "imported from Brightway"), stage=str(e.get("stage") or ""),
                            input_amount=abs(amt), input_unit=unit, avoided=(amt < 0) or t == "substitution",
                            formula=(str(e.get("formula")).strip() or None) if e.get("formula") else None)
        created.append(mid)
    return {"models": created, "problems": problems[:60]}


# ============================================================================ openLCA JSON-LD
def _ref(kind, id_, name, **extra):
    return dict({"@type": kind, "@id": id_, "name": name}, **extra)


UNIT_GROUPS = {  # openLCA reference data UUIDs for the common flow properties
    "mass": ("93a60a56-a3c8-11da-a746-0800200b9a66", "Mass"),
    "energy": ("f6811440-ee37-11de-8a39-0800200c9a66", "Energy"),
    "volume": ("93a60a56-a3c8-22da-a746-0800200c9a66", "Volume"),
    "area": ("93a60a56-a3c8-19da-a746-0800200c9a66", "Area"),
    "transport": ("838aaa21-0117-11db-92e3-0800200c9a66", "Goods transport (mass*distance)"),
    "count": ("01846770-4cfe-4a25-8ad9-919d8d378345", "Number of items"),
    "length": ("838aaa23-0117-11db-92e3-0800200c9a66", "Length"),
    "area_time": ("93a60a56-a3c8-21da-a746-0800200b9a66", "Area*time"),
}


def _prop(unit):
    i = units.info(unit)
    dim = i[0] if i else "mass"
    key = {"mass*length": "transport", "area*time": "area_time"}.get(dim, dim)
    return UNIT_GROUPS.get(key, UNIT_GROUPS["mass"])


def openlca_jsonld(store, model_ids, path):
    flows, procs = {}, []

    def product_flow(name, unit, key=None):
        fid = str(uuid.uuid5(NS, f"product|{key or name}|{unit}"))
        if fid not in flows:
            pid, pname = _prop(unit)
            flows[fid] = {"@type": "Flow", "@id": fid, "name": name, "flowType": "PRODUCT_FLOW",
                          "flowProperties": [{"@type": "FlowPropertyFactor", "isRefFlowProperty": True, "conversionFactor": 1.0,
                                              "flowProperty": _ref("FlowProperty", pid, pname)}]}
        return fid

    done = set()
    for mid in model_ids:
        for m, exch in _model_rows(store, int(mid)):
            if m["id"] in done:
                continue
            done.add(m["id"])
            pid = str(uuid.uuid5(NS, f"process|{m['id']}|{m['name']}"))
            exchanges = []
            for n, e in enumerate(exch, 1):
                if e["type"] == "skipped":
                    continue
                if e["type"] == "biosphere":
                    fid = e["code"]
                    if fid not in flows:
                        pid2, pname = _prop(e["unit"])
                        flows[fid] = {"@type": "Flow", "@id": fid, "name": e["name"], "flowType": "ELEMENTARY_FLOW",
                                      "category": "Elementary flows/" + e.get("categories", "").replace("::", "/"),
                                      "flowProperties": [{"@type": "FlowPropertyFactor", "isRefFlowProperty": True,
                                                          "conversionFactor": 1.0,
                                                          "flowProperty": _ref("FlowProperty", pid2, pname)}]}
                    is_input = (e.get("categories", "").startswith("natural resource")) != (e["amount"] < 0)
                else:
                    if e.get("product_uuid"):
                        fid = e["product_uuid"]  # the source database's own product flow: openLCA links it to that flow
                        if fid not in flows:
                            pid0, pname0 = _prop(e["unit"])
                            flows[fid] = {"@type": "Flow", "@id": fid, "name": e.get("reference product") or e["name"],
                                          "flowType": "PRODUCT_FLOW",
                                          "flowProperties": [{"@type": "FlowPropertyFactor", "isRefFlowProperty": True,
                                                              "conversionFactor": 1.0,
                                                              "flowProperty": _ref("FlowProperty", pid0, pname0)}]}
                    else:
                        fid = product_flow(e.get("reference product") or e["name"], e["unit"], e.get("source key"))
                    is_input = e["type"] == "technosphere" and e["amount"] >= 0
                pid3, pname3 = _prop(e["unit"])
                ex = {"@type": "Exchange", "internalId": n, "amount": abs(e["amount"]), "isInput": bool(is_input),
                      "isQuantitativeReference": e["type"] == "production", "flow": _ref("Flow", fid, flows[fid]["name"]),
                      "flowProperty": _ref("FlowProperty", pid3, pname3), "unit": {"@type": "Unit", "name": e["unit"]},
                      "description": " ".join(x for x in (e.get("stage", ""), e.get("comment", "")) if x)}
                if e["type"] == "production":
                    ex["isInput"] = False
                if e.get("formula"):
                    ex["amountFormula"] = e["formula"]
                if e["type"] == "technosphere" and e["amount"] < 0:
                    ex["isAvoidedProduct"] = True
                    ex["isInput"] = False
                if e.get("location"):
                    ex["location"] = {"@type": "Location", "name": e["location"]}
                if e.get("provider"):
                    ex["defaultProvider"] = _ref("Process", e["provider"], e["name"])
                exchanges.append(ex)
            procs.append({"@type": "Process", "@id": pid, "name": m["name"], "processType": "UNIT_PROCESS",
                          "description": f"Exported from Cyclia on {time.strftime('%Y-%m-%d')}. Inputs use the product "
                                         "flow identifiers of the source database (and its processes as default "
                                         "providers when it came from openLCA), so they link to the same database "
                                         "in openLCA; build the product system with 'auto-link processes'.",
                          "parameters": [{"@type": "Parameter", "name": p["name"], "value": p["value"],
                                          "formula": p["formula"] or None, "isInputParameter": not p["formula"],
                                          "parameterScope": "PROCESS_SCOPE"} for p in m["parameters"]],
                          "exchanges": exchanges})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("olca-schema.json", json.dumps({"version": 2}))
        for f in flows.values():
            z.writestr(f"flows/{f['@id']}.json", json.dumps(f, indent=1))
        for p in procs:
            z.writestr(f"processes/{p['@id']}.json", json.dumps(p, indent=1))
    return {"path": path, "file": os.path.basename(path), "processes": len(procs), "flows": len(flows)}


# ============================================================================ API clients
PYTHON_CLIENT = r'''"""Cyclia Python client. Talks to the Cyclia engine running on this computer.

    from cyclia_client import Cyclia
    cy = Cyclia()                       # finds the running app (api.json in the Cyclia data folder)
    cy.open_project("Cyclia feature demo")
    m = cy.models()[0]
    methods = [x["id"] for x in cy.methods() if "climate change" in x["category"]]
    res = cy.calculate(m["id"], methods)
    print(res["results"][0]["category"], res["results"][0]["total"])
    df = cy.results_table(res)          # pandas DataFrame if pandas is installed

Standard library only (pandas optional).
"""
import json
import os
import sys
import time
import urllib.request


def _data_dir():
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Cyclia", "data")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Cyclia/data")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "Cyclia", "data")


class Cyclia:
    def __init__(self, url=None, token=None, info_file=None):
        if not (url and token):
            path = info_file or os.environ.get("CYCLIA_API_FILE") or os.path.join(_data_dir(), "api.json")
            if not os.path.exists(path):
                raise RuntimeError(f"Cyclia is not running (no {path}). Start the Cyclia app first.")
            with open(path, encoding="utf-8") as fh:
                info = json.load(fh)
            url, token = info["url"], info["token"]
        self.url, self.token = url.rstrip("/"), token

    def _call(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "X-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(json.loads(e.read() or b"{}").get("error", str(e)))

    def status(self):
        return self._call("GET", "/api/status")

    def projects(self):
        return self._call("GET", "/api/projects")["projects"]

    def open_project(self, name):
        return self._call("POST", "/api/projects/open", {"name": name})

    def models(self):
        return self._call("GET", "/api/models")["models"]

    def model(self, model_id):
        return self._call("GET", f"/api/models/{model_id}")["model"]

    def methods(self):
        return self._call("GET", "/api/methods")["methods"]

    def search(self, text, location=""):
        return self._call("GET", "/api/search?q=" + urllib.parse.quote(text) + "&loc=" + urllib.parse.quote(location))["results"]

    def add_line(self, model_id, kind, ref_id, amount, unit=None, stage="", comment=""):
        return self._call("POST", f"/api/models/{model_id}/inputs", {"kind": kind, "ref_id": ref_id, "amount": amount,
                                                                     "unit": unit, "stage": stage, "comment": comment})

    def set_parameter(self, name, value, model_id=None):
        return self._call("POST", "/api/parameters", {"model_id": model_id, "name": name, "value": value})

    def calculate(self, model_id, method_ids, scenario=None, background=None, year=None, mc_iterations=0):
        return self._call("POST", "/api/calculate", {"model_id": model_id, "method_ids": list(method_ids), "scenario": scenario,
                                                     "bg_id": background, "bg_year": year, "mc_iterations": mc_iterations})

    def sweep(self, model_id, method_ids, params):
        """params: [{"name": "thickness", "lo": 0.1, "hi": 0.4, "n": 11}]"""
        return self._call("POST", "/api/sweep", {"model_id": model_id, "method_ids": list(method_ids), "params": params})

    def monte_carlo(self, model_ids, method_ids, iterations=500):
        job = self._call("POST", "/api/uncertainty", {"model_ids": list(model_ids), "method_ids": list(method_ids),
                                                      "iterations": iterations})["job"]
        return self.wait(job["id"])

    def wait(self, job_id, poll=1.0):
        while True:
            j = self._call("GET", f"/api/jobs/{job_id}")["job"]
            if j["status"] == "done":
                return j["result"]
            if j["status"] in ("error", "cancelled"):
                raise RuntimeError(j.get("error") or j["status"])
            time.sleep(poll)

    @staticmethod
    def results_table(res):
        rows = [{"category": r["category"], "indicator": r["indicator"], "unit": r["unit"], "total": r["total"],
                 "module_d": r["module_d"]} for r in res["results"]]
        try:
            import pandas as pd
            return pd.DataFrame(rows)
        except ImportError:
            return rows


import urllib.parse  # noqa: E402
'''

R_CLIENT = r'''# Cyclia R client. Talks to the Cyclia engine running on this computer.
# Needs the packages httr and jsonlite:  install.packages(c("httr", "jsonlite"))
#
#   source("cyclia.R")
#   cy <- cyclia_connect()
#   cyclia_open_project(cy, "Cyclia feature demo")
#   models <- cyclia_models(cy)
#   meth <- cyclia_methods(cy)
#   gwp <- meth$id[grepl("climate change", meth$category)]
#   res <- cyclia_calculate(cy, models$id[1], gwp)
#   cyclia_results_table(res)

library(httr)
library(jsonlite)

cyclia_data_dir <- function() {
  if (.Platform$OS.type == "windows") return(file.path(Sys.getenv("APPDATA"), "Cyclia", "data"))
  if (Sys.info()[["sysname"]] == "Darwin") return(path.expand("~/Library/Application Support/Cyclia/data"))
  file.path(Sys.getenv("XDG_CONFIG_HOME", path.expand("~/.config")), "Cyclia", "data")
}

cyclia_connect <- function(info_file = file.path(cyclia_data_dir(), "api.json")) {
  if (!file.exists(info_file)) stop("Cyclia is not running. Start the Cyclia app first.")
  info <- fromJSON(info_file)
  list(url = sub("/$", "", info$url), token = info$token)
}

.cy_call <- function(cy, method, path, body = NULL) {
  h <- add_headers(`X-Token` = cy$token, `Content-Type` = "application/json")
  url <- paste0(cy$url, path)
  r <- if (method == "GET") GET(url, h) else VERB(method, url, h, body = toJSON(body, auto_unbox = TRUE, null = "null"))
  out <- fromJSON(content(r, as = "text", encoding = "UTF-8"), simplifyVector = TRUE)
  if (status_code(r) >= 400) stop(out$error)
  out
}

cyclia_projects <- function(cy) .cy_call(cy, "GET", "/api/projects")$projects
cyclia_open_project <- function(cy, name) .cy_call(cy, "POST", "/api/projects/open", list(name = name))
cyclia_models <- function(cy) .cy_call(cy, "GET", "/api/models")$models
cyclia_methods <- function(cy) .cy_call(cy, "GET", "/api/methods")$methods
cyclia_calculate <- function(cy, model_id, method_ids, scenario = NULL, mc_iterations = 0) {
  .cy_call(cy, "POST", "/api/calculate", list(model_id = model_id, method_ids = as.list(method_ids),
                                              scenario = scenario, mc_iterations = mc_iterations))
}
cyclia_sweep <- function(cy, model_id, method_ids, name, lo, hi, n = 11) {
  .cy_call(cy, "POST", "/api/sweep", list(model_id = model_id, method_ids = as.list(method_ids),
                                          params = list(list(name = name, lo = lo, hi = hi, n = n))))
}
cyclia_results_table <- function(res) {
  r <- res$results
  data.frame(category = r$category, indicator = r$indicator, unit = r$unit, total = r$total, module_d = r$module_d)
}
'''
