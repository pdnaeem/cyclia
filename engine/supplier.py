"""Supplier data requests, Cyclia 1.8.0.

The user prepares a custom process with the lines they need (inputs, emissions, resources). Cyclia writes an Excel
workbook for the supplier: what the process is, the reference amount every value refers to, one row per line with
the expected unit, and a sheet for items that are not listed. The supplier fills it in and sends it back. Cyclia
reads it, checks every value (number, unit of the same kind, range), shows what will change, and only then applies
it to the process, with the supplier and the date as the source of each value.

Rules:
- nothing is changed without the preview: read_response never writes;
- a blank amount leaves the line as it is and is reported as not answered; 0 is a value ("not used");
- a line changed in Cyclia after the request is not overwritten: it is reported as a conflict;
- items the supplier adds are never linked automatically: they are listed for the user to model;
- a lowest and highest plausible value given with the amount become a triangular distribution (min, amount, max).
"""
import datetime
import json
import math
import os
import secrets

import custom_data as cd
import units

SCHEMA = """
CREATE TABLE IF NOT EXISTS lib.supplier_requests (id INTEGER PRIMARY KEY, token TEXT UNIQUE, process_uuid TEXT,
    supplier TEXT, contact TEXT, created TEXT, rows TEXT, status TEXT, received TEXT, result TEXT);
"""
HOW = ("measured", "calculated", "estimated", "not known")
HEAD = ["Row", "Type", "Item", "Unit Cyclia expects", "Amount", "Unit", "How obtained", "Lowest plausible",
        "Highest plausible", "Source or comment"]


class SupplierError(ValueError):
    pass


def ensure(store):
    with store.lock:
        store.conn.executescript(SCHEMA)
        store.conn.commit()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _lines(store, uid):
    """The lines of a process as they are offered to the supplier."""
    out = []
    for e in store.q("SELECT * FROM custom_exchanges WHERE process_uuid=? ORDER BY id", (uid,)):
        if e["kind"] == "elementary":
            f = store.one("SELECT name, compartment, subcompartment, unit FROM flows WHERE uuid=?", (e["target"],))
            item = (f"{f['name']} ({f['compartment']}" + (f", {f['subcompartment']}" if f["subcompartment"] else "")
                    + ")") if f else e["target"]
            typ = "Resource taken from nature" if f and (f["compartment"] or "").lower().startswith(
                ("natural resource", "resource")) else "Emission to " + ((f["compartment"] if f else "") or "the environment")
        else:
            try:
                _, _, _, item = cd._supplier(store, e["target"])
            except cd.CustomDataError:
                item = str(e["target"])
            typ = "Product credited (avoided)" if e["avoided"] else "Input (material, energy, transport, service)"
        out.append({"id": e["id"], "type": typ, "item": item, "unit": e["unit"], "amount": e["amount"],
                    "formula": e["formula"], "revision": e["revision"] or 1})
    return out


def request_workbook(store, process_uuid, path, supplier, contact="", include_current=False, message=""):
    """Write the request workbook and record the request. Returns the request id."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill, Protection
    from openpyxl.worksheet.datavalidation import DataValidation
    ensure(store)
    p = cd._item(store, process_uuid, "process")
    prod = cd._item(store, p["data"]["product"], "product")
    supplier = cd._text(supplier, "The supplier", maxlen=200)
    contact = cd._text(contact, "Contact", False, 200)
    lines = _lines(store, process_uuid)
    if not lines:
        raise SupplierError("The process has no lines yet. Add the inputs and emissions you need in step 5, then "
                            "ask the supplier for their amounts.")
    token = secrets.token_hex(12)
    ref = f"{_fmt(p['data']['amount'])} {prod['data']['unit']} of {prod['name']}"
    wb = openpyxl.Workbook()
    bold, wrap = Font(bold=True), Alignment(wrap_text=True, vertical="top")
    fill = PatternFill("solid", fgColor="FFF4CC")
    open_ = Protection(locked=False)

    ws = wb.active
    ws.title = "Read me"
    text = [
        ("Data request", True),
        (f"From: {contact or 'the requester'}, using Cyclia. To: {supplier}.", False),
        (message, False) if message else None,
        ("", False),
        ("What we ask", True),
        (f"Please give the amounts for the process '{p['name']}'. Every amount refers to {ref}: give how much of each "
         "item goes into or comes out of the process to make that amount.", False),
        ("How to fill it in", True),
        ("1. Sheet 'Process': fill in the yellow cells (company, period the data covers, location, technology).", False),
        ("2. Sheet 'Inputs and outputs': give the amount of each row in the yellow 'Amount' column. You can change the "
         "unit to another unit of the same kind (for example g instead of kg). Leave a row empty if you do not know "
         "it; write 0 if the item is not used.", False),
        ("3. If you know the range, give the lowest and highest plausible values as well.", False),
        ("4. Sheet 'Other items': list anything the process uses or emits that is not in the list.", False),
        ("5. Save the file and send it back. Please do not add, remove or reorder rows in 'Inputs and outputs'.", False),
        ("", False),
        ("What happens with it", True),
        ("The requester's software checks every value before it is used and records your company and the date as the "
         "source of each value.", False),
    ]
    for i, t in enumerate([t for t in text if t], start=1):
        c = ws.cell(i, 1, t[0])
        c.font = Font(bold=True, size=13 if i == 1 else 11) if t[1] else Font()
        c.alignment = wrap
    ws.column_dimensions["A"].width = 110

    wp = wb.create_sheet("Process")
    rows = [("Process", p["name"], False), ("Every amount refers to", ref, False),
            ("Company", supplier, True), ("Contact person", "", True), ("Date of these data (YYYY-MM-DD)", "", True),
            ("Period the data cover (e.g. 2025)", p["data"].get("time_period") or "", True),
            ("Location (country or region)", p["data"].get("location") or "", True),
            ("Technology (short description)", p["data"].get("technology") or "", True),
            ("Comment", "", True)]
    for i, (k, v, editable) in enumerate(rows, start=1):
        wp.cell(i, 1, k).font = bold
        c = wp.cell(i, 2, v)
        c.alignment = wrap
        if editable:
            c.fill, c.protection = fill, open_
    wp.column_dimensions["A"].width = 38
    wp.column_dimensions["B"].width = 70

    wx = wb.create_sheet("Inputs and outputs")
    for j, h in enumerate(HEAD, start=1):
        wx.cell(1, j, h).font = bold
    how = DataValidation(type="list", formula1='"' + ",".join(HOW) + '"', allow_blank=True)
    wx.add_data_validation(how)
    for i, ln in enumerate(lines, start=2):
        vals = [i - 1, ln["type"], ln["item"], ln["unit"],
                (ln["amount"] if include_current and not ln["formula"] else None), ln["unit"], None, None, None, None]
        for j, v in enumerate(vals, start=1):
            c = wx.cell(i, j, v)
            c.alignment = wrap
            if j >= 5:
                c.fill, c.protection = fill, open_
        same, n = [], 0
        for u in units.compatible(ln["unit"]):
            if "," in u or '"' in u or n + len(u) + 1 > 250:     # Excel list validations hold 255 characters
                continue
            same.append(u)
            n += len(u) + 1
        if len(same) > 1:
            dv = DataValidation(type="list", formula1='"' + ",".join(same) + '"', allow_blank=False)
            dv.error = "Choose a unit of the same kind as the expected unit."
            wx.add_data_validation(dv)
            dv.add(wx.cell(i, 6))
        how.add(wx.cell(i, 7))
    for col, w in zip("ABCDEFGHIJ", (6, 30, 50, 14, 14, 10, 14, 14, 14, 40)):
        wx.column_dimensions[col].width = w
    wx.freeze_panes = "E2"

    wo = wb.create_sheet("Other items")
    for j, h in enumerate(["Type (input, emission, waste, product)", "Description", "Amount", "Unit", "Comment"], 1):
        wo.cell(1, j, h).font = bold
    for i in range(2, 42):
        for j in range(1, 6):
            c = wo.cell(i, j)
            c.fill, c.protection = fill, open_
    for col, w in zip("ABCDE", (28, 50, 14, 10, 40)):
        wo.column_dimensions[col].width = w

    meta = wb.create_sheet("_cyclia")
    meta["A1"], meta["B1"] = "token", token
    meta["A2"], meta["B2"] = "process", process_uuid
    meta["A3"], meta["B3"] = "rows", json.dumps([ln["id"] for ln in lines])
    meta.sheet_state = "veryHidden"
    for s in (ws, wp, wx):
        s.protection.sheet = True
        s.protection.formatColumns = False
        s.protection.formatRows = False
    wb.save(path)
    with store.lock:
        rid = store.conn.execute("INSERT INTO supplier_requests(token, process_uuid, supplier, contact, created, rows, "
                                 "status) VALUES(?,?,?,?,?,?,?)",
                                 (token, process_uuid, supplier, contact, _now(),
                                  json.dumps({str(ln["id"]): ln["revision"] for ln in lines}), "sent")).lastrowid
        store.conn.commit()
    return rid


def _fmt(x):
    return f"{float(x):.6g}"


def _num(v, what):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        x = float(v)
    else:
        s = str(v).strip().replace(" ", "").replace(" ", "")
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            x = float(s)
        except ValueError:
            raise SupplierError(f"{what}: '{v}' is not a number.")
    if not math.isfinite(x):
        raise SupplierError(f"{what} is not a finite number.")
    return x


def _cell(v):
    return "" if v is None else str(v).strip()


def read_response(store, path):
    """Read and check a returned workbook. Writes nothing. Returns the preview: the changes, what was not
    answered, conflicts, errors per row, and the extra items."""
    import openpyxl
    ensure(store)
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as e:
        raise SupplierError(f"The file could not be read as an Excel workbook ({e}).")
    if "_cyclia" not in wb.sheetnames or "Inputs and outputs" not in wb.sheetnames:
        raise SupplierError("This workbook is not a Cyclia data request (its hidden identification sheet is missing).")
    meta = wb["_cyclia"]
    req = store.one("SELECT * FROM supplier_requests WHERE token=?", (_cell(meta["B1"].value),))
    if not req:
        raise SupplierError("This request was not made from this library. Open the library the request was sent from.")
    uid = req["process_uuid"]
    try:
        p = cd._item(store, uid, "process")
    except cd.CustomDataError:
        raise SupplierError("The process of this request no longer exists.")
    sent = json.loads(req["rows"])
    order = json.loads(_cell(meta["B3"].value) or "[]")
    current = {str(e["id"]): e for e in store.q("SELECT * FROM custom_exchanges WHERE process_uuid=?", (uid,))}
    wx = wb["Inputs and outputs"]
    changes, unanswered, conflicts, errors = [], [], [], []
    for i, eid in enumerate(order, start=2):
        r = [wx.cell(i, j).value for j in range(1, len(HEAD) + 1)]
        label = _cell(r[2]) or f"row {i - 1}"
        try:
            amount = _num(r[4], f"Row {i - 1} ({label}), amount")
            lo = _num(r[7], f"Row {i - 1} ({label}), lowest plausible value")
            hi = _num(r[8], f"Row {i - 1} ({label}), highest plausible value")
        except SupplierError as e:
            errors.append({"row": i - 1, "item": label, "error": str(e)})
            continue
        if amount is None:
            if lo is not None or hi is not None:
                errors.append({"row": i - 1, "item": label, "error": "A range is given without an amount."})
            else:
                unanswered.append({"row": i - 1, "item": label})
            continue
        e = current.get(str(eid))
        if not e:
            conflicts.append({"row": i - 1, "item": label, "reason": "The line was deleted in Cyclia after the request."})
            continue
        if (e["revision"] or 1) != sent.get(str(eid)):
            conflicts.append({"row": i - 1, "item": label, "reason": "The line was changed in Cyclia after the "
                                                                     "request; its value was not overwritten."})
            continue
        unit = _cell(r[5]) or e["unit"]
        msg = None
        if amount < 0:
            msg = "Amounts are positive (an avoided product is marked as such in Cyclia)."
        else:
            try:
                cd.convert(1.0, unit, e["unit"])
            except cd.CustomDataError:
                msg = f"The unit '{unit}' is not of the same kind as '{e['unit']}'."
        if not msg and (lo is None) != (hi is None):
            msg = "Give both the lowest and the highest plausible value, or neither."
        if not msg and lo is not None and not (lo <= amount <= hi and lo < hi):
            msg = "The range must satisfy lowest <= amount <= highest, with lowest < highest."
        if msg:
            errors.append({"row": i - 1, "item": label, "error": msg})
            continue
        how = _cell(r[6]).lower()
        if how and how not in HOW:
            how = ""
        changes.append({"row": i - 1, "exchange": e["id"], "item": label, "old": e["amount"], "old_unit": e["unit"],
                        "old_formula": e["formula"] or "", "amount": amount, "unit": unit, "min": lo, "max": hi,
                        "how": how, "comment": _cell(r[9])[:2000]})
    wp = wb["Process"] if "Process" in wb.sheetnames else None
    pv = {}
    if wp:
        for i in range(1, 30):
            k = _cell(wp.cell(i, 1).value)
            if k:
                pv[k] = _cell(wp.cell(i, 2).value)
    info = {"company": pv.get("Company", "") or req["supplier"], "contact": pv.get("Contact person", ""),
            "date": pv.get("Date of these data (YYYY-MM-DD)", ""), "period": pv.get("Period the data cover (e.g. 2025)", ""),
            "location": pv.get("Location (country or region)", ""), "technology": pv.get("Technology (short description)", ""),
            "comment": pv.get("Comment", "")}
    if info["date"]:
        try:
            datetime.date.fromisoformat(info["date"][:10])
            info["date"] = info["date"][:10]
        except ValueError:
            errors.append({"row": 0, "item": "Process", "error": f"The date '{info['date']}' is not YYYY-MM-DD."})
            info["date"] = ""
    extra = []
    if "Other items" in wb.sheetnames:
        wo = wb["Other items"]
        for i in range(2, wo.max_row + 1):
            vals = [_cell(wo.cell(i, j).value) for j in range(1, 6)]
            if any(vals):
                extra.append({"type": vals[0], "description": vals[1], "amount": vals[2], "unit": vals[3],
                              "comment": vals[4]})
    return {"request": req["id"], "process": uid, "process_name": p["name"], "supplier": info, "changes": changes,
            "unanswered": unanswered, "conflicts": conflicts, "errors": errors, "extra": extra,
            "note": "Nothing has been changed yet. Apply to write the changes; rows with errors or conflicts are "
                    "left as they are, and the extra items must be modelled by you (they are not linked "
                    "automatically)."}


def apply_response(store, path, author=""):
    """Apply a checked response. Rows with errors or conflicts are skipped; the result says what was done."""
    pv = read_response(store, path)
    uid = pv["process"]
    sup = pv["supplier"]
    src = f"Supplier data: {sup['company']}" + (f", {sup['contact']}" if sup["contact"] else "") + \
          (f", data of {sup['date']}" if sup["date"] else "") + f" (Cyclia request {pv['request']})"
    applied = []
    for c in pv["changes"]:
        e = store.one("SELECT * FROM custom_exchanges WHERE id=?", (c["exchange"],))
        d = {"id": e["id"], "kind": e["kind"], "amount": c["amount"], "unit": c["unit"], "avoided": bool(e["avoided"]),
             "source": src, "comment": "; ".join(x for x in (c["how"], c["comment"]) if x),
             "author": author or sup["company"]}
        if e["kind"] == "elementary":
            d["flow"] = e["target"]
        else:
            d["supplier"] = e["target"]
        if c["min"] is not None:
            d.update({"uncertainty": "triangular", "min": c["min"], "mode": c["amount"], "max": c["max"]})
        elif e["utype"] and e["uncertainty"] in ("lognormal", "normal", "pedigree"):
            # keep the existing spread only where it is relative (lognormal, pedigree); a normal sd was absolute
            if e["uncertainty"] == "pedigree" and e["pedigree"]:
                d.update({"uncertainty": "pedigree", "pedigree": json.loads(e["pedigree"])})
            elif e["uncertainty"] == "lognormal":
                d.update({"uncertainty": "lognormal", "gsd": math.exp(e["p1"])})
        cd.save_exchange(store, uid, d)
        applied.append(c["row"])
    it = cd._item(store, uid, "process")
    data = dict(it["data"])
    upd = {"uuid": uid, "name": it["name"], "product": data["product"], "amount": data["amount"], "type": data["type"],
           "location": sup["location"] or data.get("location") or "GLO",
           "technology": sup["technology"] or data.get("technology", ""),
           "time_period": sup["period"] or data.get("time_period", ""), "comment": data.get("comment", ""),
           "dq": data.get("dq") or {}, "coproducts": data.get("coproducts") or [], "allocation": data.get("allocation"),
           "source": "; ".join(x for x in (it.get("source") or "", src) if x and src not in (it.get("source") or ""))
                     or it.get("source") or src, "author": author or it.get("author") or ""}
    hows = {c["how"] for c in pv["changes"] if c["how"]}
    # primary data only when every answered value was measured or calculated by the supplier
    upd["data_type"] = "primary" if hows and hows <= {"measured", "calculated"} and \
        all(c["how"] for c in pv["changes"]) else (data.get("data_type") or "")
    if applied:
        cd.save_process(store, it["db_id"], upd)
    res = {"applied": len(applied), "unanswered": len(pv["unanswered"]), "conflicts": pv["conflicts"],
           "errors": pv["errors"], "extra": pv["extra"], "source": src}
    store.x("UPDATE supplier_requests SET status=?, received=?, result=? WHERE id=?",
            ("received", _now(), json.dumps(res), pv["request"]))
    # one entry in the process history that ties the changed lines to the request and the file
    cd._log(store, uid, "process", "supplier data applied", author or sup["company"],
            {"request": pv["request"], "file": os.path.basename(str(path)), "supplier": sup, "lines": applied,
             "conflicts": len(pv["conflicts"]), "errors": len(pv["errors"]), "extra": len(pv["extra"])})
    return res


def requests(store, process_uuid=None):
    ensure(store)
    sql = "SELECT id, process_uuid, supplier, contact, created, status, received, result FROM supplier_requests"
    rows = store.q(sql + (" WHERE process_uuid=?" if process_uuid else "") + " ORDER BY id DESC",
                   (process_uuid,) if process_uuid else ())
    out = []
    for r in rows:
        d = dict(r)
        d["result"] = json.loads(d["result"]) if d["result"] else None
        out.append(d)
    return out
