"""Excel round trip for a model's inventory: template, export, and validated bulk import.

Import is all-or-nothing: every row is checked first, and if any row has a problem nothing is
added and the user gets a row-by-row list of what to fix.
"""
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

import units

COLUMNS = ["Type", "Database", "Dataset, flow or model name", "Location or compartment", "Amount", "Unit",
           "Stage", "Avoided product", "Source note", "Data quality"]
TYPES = {"dataset": "activity", "emission": "flow", "resource": "flow", "model": "model"}
HELP = [
    ("Type", "dataset (material, energy, transport, waste treatment), emission, resource, or model (one of your other models)."),
    ("Database", "Optional. Exact database name as shown in step 1, to choose between databases."),
    ("Dataset, flow or model name", "Exact name as shown in the search results of step 3 (case does not matter)."),
    ("Location or compartment", "Dataset location code (e.g. FR, RER, GLO) or, for emissions, compartment like air or air/urban air close to ground."),
    ("Amount", "Amount per functional unit. Always positive; use the Avoided product column for credits."),
    ("Unit", "Any unit convertible to the dataset's unit (e.g. g, kg, t; kWh, MJ; L, m3; kg*km, t*km). Empty = dataset unit."),
    ("Stage", "Life cycle stage, e.g. A1 Raw material supply, A4 Transport, C4 Disposal. Free text."),
    ("Avoided product", "yes for a credit from system expansion, otherwise leave empty."),
    ("Source note", "Where the number comes from (measurement, EPD, literature)."),
    ("Data quality", "Pedigree scores 1-5 for reliability, completeness, temporal, geographical, technological, e.g. 2,3,1,2,2."),
]


def _style(ws):
    hdr = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="2F5D50")
    for c in ws[1]:
        c.font, c.fill = hdr, fill
    widths = [12, 26, 52, 22, 12, 10, 26, 14, 30, 14]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w


def _workbook(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.append(COLUMNS)
    for r in rows:
        ws.append(r)
    _style(ws)
    dv = DataValidation(type="list", formula1='"dataset,emission,resource,model"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("A2:A2000")
    h = wb.create_sheet("Help")
    h.append(["Column", "What to enter"])
    for r in HELP:
        h.append(list(r))
    h.column_dimensions["A"].width = 28
    h.column_dimensions["B"].width = 110
    for c in h[1]:
        c.font = Font(bold=True)
    return wb


def template(path):
    _workbook([["dataset", "", "market for electricity, medium voltage", "FR", 12, "kWh", "A3 Manufacturing", "", "meter reading 2025", "1,2,1,1,1"],
               ["emission", "", "Carbon dioxide, fossil", "air", 2.5, "kg", "A3 Manufacturing", "", "stoichiometry", "2,2,1,1,1"]]).save(path)
    return path


def export(store, model_id, path):
    m = store.model(model_id)
    rows = []
    for i in m["inputs"]:
        t = i["target"]
        typ = {"activity": "dataset", "flow": "emission", "model": "model"}.get(i["kind"])
        if typ is None:
            continue  # EPD lines hold their own values and are not part of the Excel exchange format
        rows.append([typ, t.get("db", "") if i["kind"] == "activity" else "", t["name"], t.get("location", ""),
                     i["input_amount"], i["input_unit"], i["stage"], "yes" if i["avoided"] else "", i["comment"],
                     ",".join(str(x) for x in i["pedigree"])])
    _workbook(rows).save(path)
    return path


def _pedigree(v):
    if v in (None, ""):
        return [3, 3, 3, 3, 3]
    parts = [p for p in str(v).replace(";", ",").replace(" ", ",").split(",") if p]
    vals = [int(float(p)) for p in parts]
    if len(vals) != 5 or not all(1 <= x <= 5 for x in vals):
        raise ValueError("data quality must be five scores from 1 to 5, e.g. 2,3,1,2,2")
    return vals


def import_rows(store, model_id, path):
    if not store.one("SELECT id FROM models WHERE id=?", (model_id,)):
        raise ValueError("Model not found.")
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["Inventory"] if "Inventory" in wb.sheetnames else wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    head = [str(h or "").strip().lower() for h in next(it, [])]
    if not head or "type" not in head[0]:
        raise ValueError("The first row must hold the template headers. Download the template from step 3.")
    dbs = {d["name"].lower(): d["id"] for d in store.databases()}
    models = {m["name"].lower(): m for m in store.models()}
    planned, problems = [], []
    for n, row in enumerate(it, start=2):
        row = list(row) + [None] * (10 - len(row))
        if not any(v not in (None, "") for v in row[:10]):
            continue
        typ, db, name, loc, amount, unit, stage, avoided, note, dq = [
            (str(v).strip() if isinstance(v, str) else v) for v in row[:10]]
        typ = (typ or "").lower()
        try:
            if typ not in TYPES:
                raise ValueError("Type must be dataset, emission, resource or model")
            if not name:
                raise ValueError("name is empty")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                raise ValueError("Amount must be a number")
            if amount < 0:
                raise ValueError("Amount must be positive (use the Avoided product column for credits)")
            kind = TYPES[typ]
            if kind == "activity":
                sql = "SELECT a.id, a.unit, a.name, a.location FROM activities a WHERE lower(a.name)=lower(?)"
                args = [name]
                if db:
                    if db.lower() not in dbs:
                        raise ValueError(f"database '{db}' is not in this project")
                    sql += " AND a.db_id=?"
                    args.append(dbs[db.lower()])
                if loc:
                    sql += " AND upper(a.location)=upper(?)"
                    args.append(loc)
                hits = store.q(sql, args)
                if not hits:
                    sugg = store.search_activities(name, dbs.get((db or "").lower()), loc, limit=1)
                    raise ValueError(f"dataset '{name}'{' [' + loc + ']' if loc else ''} not found"
                                     + (f"; closest match: '{sugg[0]['name']}' [{sugg[0]['location']}]" if sugg else ""))
                if len(hits) > 1 and not loc:
                    raise ValueError(f"'{name}' exists in {len(hits)} locations; fill in the Location column")
                ref_id, target_unit = hits[0]["id"], hits[0]["unit"]
            elif kind == "flow":
                comp, _, sub = (loc or "").partition("/")
                sql = "SELECT id, unit FROM flows WHERE lower(name)=lower(?)"
                args = [name]
                if comp:
                    sql += " AND lower(compartment)=lower(?)"
                    args.append(comp.strip())
                if sub:
                    sql += " AND lower(subcompartment)=lower(?)"
                    args.append(sub.strip())
                hits = store.q(sql, args)
                if not hits:
                    raise ValueError(f"elementary flow '{name}' ({loc or 'any compartment'}) not found")
                if len(hits) > 1:
                    fallback = hits
                    hits = store.q(sql + " AND lower(COALESCE(subcompartment,'')) IN ('unspecified','')", args) or fallback
                ref_id, target_unit = hits[0]["id"], hits[0]["unit"]
            else:
                mm = models.get(name.lower())
                if not mm:
                    raise ValueError(f"model '{name}' not found in this project")
                if mm["id"] == model_id or store._model_depends_on(mm["id"], model_id):
                    raise ValueError(f"model '{name}' would create a loop (a model cannot contain itself)")
                ref_id, target_unit = mm["id"], mm["unit"]
            unit = unit or target_unit
            fac = units.factor(unit, target_unit)
            if fac is None:
                raise ValueError(f"unit '{unit}' cannot be converted to the dataset unit '{target_unit}'")
            planned.append({"kind": kind, "ref_id": ref_id, "amount": amount * fac, "input_amount": amount,
                            "input_unit": unit, "stage": stage or "", "comment": note or "",
                            "avoided": str(avoided or "").strip().lower() in ("yes", "y", "1", "true", "x"),
                            "pedigree": _pedigree(dq), "label": name if kind != "activity" else ""})
        except ValueError as e:
            problems.append(f"Row {n}: {e}.")
    if problems:
        return {"added": 0, "problems": problems}
    if not planned:
        return {"added": 0, "problems": ["The sheet has no data rows."]}
    for p in planned:
        store.add_input(model_id, p["kind"], p["ref_id"], p["amount"], p["label"], p["comment"], p["stage"],
                        p["input_amount"], p["input_unit"], p["avoided"], p["pedigree"])
    return {"added": len(planned), "problems": []}
