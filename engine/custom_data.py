"""Custom LCA data entry (Cyclia 1.6.0): build a complete product system from an empty library.

The user creates, in a custom database:
- product flows (the reference products of processes), each with a unit;
- elementary flows (emissions and resources) with compartment, subcompartment, unit and CAS number;
- processes with their reference product, location, technology, time period and data quality (PEF DQR);
- exchanges: technosphere inputs from a chosen supplier (a custom process or any library dataset), avoided products,
  and elementary exchanges, each with its unit, uncertainty (or pedigree scores) and source;
- characterisation factors for custom flows in any installed method, and custom methods with factors for any flow.

Rules
- Every item gets a UUID (version 4) and provenance: source, author, created and modified time, revision.
- Units are validated: a flow's unit must be a known unit, and an amount entered in another unit is converted only
  within the same dimension (g to kg, kWh to MJ); anything else is refused. Land occupation needs area x time,
  land transformation needs area.
- Compartments follow the ecoinvent elementary-flow list, so that factors of installed methods match.
- An elementary flow that already exists in the library (same name and compartment) is not created again: the
  existing flow and its factors are used.
- A factor that is not known is never taken as zero. For each custom flow and impact category the user gives a
  factor (with its source) or records that the category does not apply (with the reason). A result that contains a
  custom flow with neither is marked incomplete, the flows are listed, and the checks report an error, so the result
  cannot go into an EPD until every factor is decided. A factor of zero recorded with its source is a known value.
- In a custom method, a flow without a factor is unknown too, unless the method's scope states (with the reason)
  that flows without a factor have no effect in the category, as published methods do.

The custom tables are the master data. compile() writes them into the library tables (activities, tech, bio,
unlinked, activity_dq, cf_raw) in one transaction, keeping the dataset ids stable so that models stay linked.
"""
import datetime
import json
import math
import re
import uuid as uuidlib

import numpy as np

import calc
import formula as fm
import units as unitconv
from canon import canon_context

SOURCE = "Cyclia custom data"
METHOD_SOURCE = "Cyclia custom method"

from store import CUSTOM_SCHEMA as SCHEMA  # noqa: E402  (created with the library)

# ecoinvent elementary-flow compartments (the ones Cyclia's factor matching uses)
COMPARTMENTS = {
    "air": ["unspecified", "urban air close to ground", "non-urban air or from high stacks",
            "low population density, long-term", "lower stratosphere + upper troposphere", "indoor"],
    "water": ["unspecified", "surface water", "ground-", "ground-, long-term", "ocean"],
    "soil": ["unspecified", "agricultural", "forestry", "industrial"],
    "natural resource": ["in ground", "in water", "in air", "land", "biotic", "unspecified"],
}
UNCERTAINTY = {"none": 0, "lognormal": 1, "normal": 2, "triangular": 3, "uniform": 4}


class CustomDataError(ValueError):
    pass


def ensure_schema(store):
    with store.lock:
        store.conn.executescript(SCHEMA)
        store.conn.commit()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _text(v, what, required=True, maxlen=500):
    v = (str(v) if v is not None else "").strip()
    if required and not v:
        raise CustomDataError(f"{what} is required.")
    if len(v) > maxlen:
        raise CustomDataError(f"{what} is too long (at most {maxlen} characters).")
    return v


def _number(v, what, allow_zero=False):
    try:
        x = float(v)
    except (TypeError, ValueError):
        if isinstance(v, str) and re.fullmatch(r"\s*-?\d+,\d+\s*", v):
            raise CustomDataError(f"{what}: use a dot as the decimal separator ({v.strip().replace(',', '.')}, not "
                                  f"{v.strip()}).")
        raise CustomDataError(f"{what} must be a number.")
    if not math.isfinite(x):
        raise CustomDataError(f"{what} must be a finite number.")
    if not allow_zero and x == 0:
        raise CustomDataError(f"{what} must not be zero.")
    return x


def check_unit(u, what="The unit"):
    """A known unit (units.py); returns it as entered (trimmed)."""
    u = _text(u, what, maxlen=40)
    if not unitconv.info(u):
        raise CustomDataError(f"{what} '{u}' is not a known unit. Use, for example, kg, g, t, MJ, kWh, m3, l, m2, "
                              "m2*a, t*km, person*km, unit, h or kBq.")
    return u


def convert(amount, unit_from, unit_to, what="The amount"):
    f = unitconv.factor(unit_from, unit_to)
    if f is None:
        raise CustomDataError(f"{what} is given in {unit_from}, which cannot be converted to {unit_to} (different "
                              "dimension).")
    return amount * f


def cas_ok(cas):
    """CAS registry number with a valid check digit."""
    m = re.fullmatch(r"(\d{2,7})-(\d{2})-(\d)", cas or "")
    if not m:
        return False
    digits = (m.group(1) + m.group(2))[::-1]
    return sum((i + 1) * int(d) for i, d in enumerate(digits)) % 10 == int(m.group(3))


def _item(store, uid, kind=None):
    r = store.one("SELECT * FROM custom_items WHERE uuid=?", (uid,))
    if not r or (kind and r["kind"] != kind):
        raise CustomDataError(f"The {kind or 'item'} was not found.")
    r = dict(r)
    r["data"] = json.loads(r["data"] or "{}")
    return r


def _log(store, item, kind, action, author="", data=None):
    """Change history: one row per creation, change or deletion (caller may hold the lock; commits itself)."""
    with store.lock:
        store.conn.execute("INSERT INTO custom_history(item,kind,action,author,time,data) VALUES(?,?,?,?,?,?)",
                           (item, kind, action, author or "", _now(), json.dumps(data) if data is not None else None))
        store.conn.commit()


def _diff(before, after):
    """Plain description of what changed between two versions of a process."""
    if before is None:
        return "created"
    if after is None:
        return "deleted"
    out = []
    bi, ai = before["item"], after["item"]
    if bi["name"] != ai["name"]:
        out.append(f"name '{bi['name']}' -> '{ai['name']}'")
    bd, ad = json.loads(bi["data"] or "{}"), json.loads(ai["data"] or "{}")
    for k in ("amount", "type", "location", "technology", "time_period", "data_type", "dq", "parameters",
              "coproducts", "allocation", "product"):
        if bd.get(k) != ad.get(k):
            out.append(k.replace("_", " ") + " changed")
    if (bi.get("source") or "") != (ai.get("source") or ""):
        out.append("source changed")
    be = {e["id"]: e for e in before["exchanges"]}
    ae = {e["id"]: e for e in after["exchanges"]}
    add = [i for i in ae if i not in be]
    rem = [i for i in be if i not in ae]
    chg = [i for i in ae if i in be and any(ae[i].get(k) != be[i].get(k) for k in
                                            ("target", "amount", "unit", "avoided", "utype", "p1", "p2", "p3",
                                             "formula", "source"))]
    for label, ids, src in (("added", add, ae), ("removed", rem, be), ("changed", chg, ae)):
        for i in ids[:5]:
            e = src[i]
            amt = f"{e['amount']:g} {e['unit']}" + (f" (= {e['formula']})" if e.get("formula") else "")
            if label == "changed":
                o = be[i]
                amt = f"{o['amount']:g} {o['unit']} -> {amt}"
            out.append(f"line {label}: {amt}")
    return "; ".join(out) or "no change in the data"


def history(store, item, limit=100):
    """Change history of an item, newest first. Versions are summarised (what changed, and whether the state before
    and after can be restored) instead of being returned in full."""
    ensure_schema(store)
    rows = store.q("SELECT * FROM custom_history WHERE item=? ORDER BY id DESC LIMIT ?", (item, int(limit)))
    for r in rows:
        d = json.loads(r["data"]) if r["data"] else None
        if isinstance(d, dict) and ("before" in d or "after" in d):
            r["diff"] = _diff(d.get("before"), d.get("after"))
            r["can_restore_before"] = d.get("before") is not None
            r["can_restore_after"] = d.get("after") is not None
            d = {k: v for k, v in d.items() if k not in ("before", "after")}
        r["data"] = d
    return rows


_EX_COLS = ("kind", "target", "amount", "unit", "amount_ref", "avoided", "utype", "p1", "p2", "p3", "pedigree",
            "uncertainty", "source", "comment", "modified", "author", "created", "revision", "formula", "unit_factor")


def snapshot(store, uid):
    """The complete state of a process: its record and all its lines (for versions, undo and restore)."""
    it = store.one("SELECT uuid, db_id, name, data, source, author, revision FROM custom_items WHERE uuid=? AND "
                   "kind='process'", (uid,))
    if not it:
        return None
    return {"item": dict(it), "exchanges": [{k: e[k] for k in ("id",) + _EX_COLS} for e in store.q(
        "SELECT * FROM custom_exchanges WHERE process_uuid=? ORDER BY id", (uid,))]}


def _attach_versions(store, uid, before):
    """Store the state before and after the latest change of a process in its history row."""
    after = snapshot(store, uid)
    h = store.one("SELECT id, data FROM custom_history WHERE item=? ORDER BY id DESC LIMIT 1", (uid,))
    if not h:
        return
    d = json.loads(h["data"] or "{}") if h["data"] else {}
    d["before"], d["after"] = before, after
    store.x("UPDATE custom_history SET data=? WHERE id=?", (json.dumps(d), h["id"]))


def restore(store, uid, history_id, which="before", author=""):
    """Bring a process back to the state before (or after) a recorded change. The restore is itself recorded, so it
    can be undone. Refused, with nothing changed, when the old state no longer fits (for example a supplier or a
    product that was deleted since)."""
    h = store.one("SELECT * FROM custom_history WHERE id=? AND item=?", (int(history_id), uid))
    if not h or not h["data"]:
        raise CustomDataError("That version was not found.")
    snap = (json.loads(h["data"]) or {}).get("before" if which == "before" else "after")
    if snap is None and which == "before":
        raise CustomDataError("The process did not exist before this change. Delete it instead.")
    if not snap:
        raise CustomDataError("No version is recorded for this change.")
    now = snapshot(store, uid)
    it = snap["item"]
    with store.lock:
        c = store.conn
        if now:
            c.execute("UPDATE custom_items SET name=?, data=?, source=?, author=?, modified=?, revision=revision+1 "
                      "WHERE uuid=?", (it["name"], it["data"], it["source"], author or it["author"], _now(), uid))
        else:
            c.execute("INSERT INTO custom_items(uuid,kind,db_id,ref_id,name,data,source,author,created,modified,revision) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (uid, "process", it["db_id"], None, it["name"], it["data"],
                                                        it["source"], author or it["author"], _now(), _now(),
                                                        (it.get("revision") or 1) + 1))
        c.execute("DELETE FROM custom_exchanges WHERE process_uuid=?", (uid,))
        for e in snap["exchanges"]:
            free = not c.execute("SELECT 1 FROM custom_exchanges WHERE id=?", (e["id"],)).fetchone()
            cols = (("id",) if free else ()) + _EX_COLS + ("process_uuid",)
            vals = ((e["id"],) if free else ()) + tuple(e.get(k) for k in _EX_COLS) + (uid,)
            c.execute(f"INSERT INTO custom_exchanges({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals)
        c.commit()
    try:
        if now is None:
            # recreate the dataset for the restored process (its earlier id is gone)
            d = json.loads(it["data"])
            d["coproduct_refs"] = {}
            store.x("UPDATE custom_items SET data=? WHERE uuid=?", (json.dumps(d), uid))
        compile(store, it["db_id"])
    except Exception:
        _put_back(store, uid, now, it["db_id"])
        raise
    _log(store, uid, "process", f"restored the version {'before' if which == 'before' else 'after'} the change of "
                                f"{(h['time'] or '')[:19].replace('T', ' ')}", author)
    _attach_versions(store, uid, now)


def _put_back(store, uid, snap, db_id):
    with store.lock:
        c = store.conn
        c.execute("DELETE FROM custom_exchanges WHERE process_uuid=?", (uid,))
        if snap is None:
            c.execute("DELETE FROM custom_items WHERE uuid=?", (uid,))
        else:
            it = snap["item"]
            c.execute("UPDATE custom_items SET name=?, data=?, source=?, author=?, revision=? WHERE uuid=?",
                      (it["name"], it["data"], it["source"], it["author"], it["revision"], uid))
            for e in snap["exchanges"]:
                cols = ("id",) + _EX_COLS + ("process_uuid",)
                c.execute(f"INSERT INTO custom_exchanges({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                          (e["id"],) + tuple(e.get(k) for k in _EX_COLS) + (uid,))
        c.commit()
    compile(store, db_id)


def undo(store, uid, author=""):
    """Undo the latest recorded change of a process (a second undo undoes the undo)."""
    h = store.one("SELECT id FROM custom_history WHERE item=? AND data LIKE '%\"before\"%' ORDER BY id DESC LIMIT 1",
                  (uid,))
    if not h:
        raise CustomDataError("There is no recorded change to undo for this process.")
    restore(store, uid, h["id"], "before", author)


def deleted_processes(store, db_id):
    """Processes of a custom database that were deleted and can be restored."""
    out = []
    for h in store.q("SELECT id, item, time, data FROM custom_history WHERE kind='process' AND action='deleted' "
                     "ORDER BY id DESC LIMIT 200"):
        d = json.loads(h["data"] or "{}")
        b = d.get("before")
        if b and b["item"]["db_id"] == int(db_id) and not store.one("SELECT 1 AS x FROM custom_items WHERE uuid=?",
                                                                    (h["item"],)):
            if all(o["uuid"] != h["item"] for o in out):
                out.append({"uuid": h["item"], "name": b["item"]["name"], "time": h["time"], "history_id": h["id"]})
    return out


def dependents(store, uid, usage=None):
    """What a change of a process affects: the custom processes that use it, directly or further down the chain,
    and (with usage(activity_id) -> [{project, lines}]) the models of every project that use any of them."""
    seen, order, todo = {uid}, [], [uid]
    while todo:
        cur = todo.pop()
        for r in store.q("SELECT DISTINCT e.process_uuid, i.name FROM custom_exchanges e JOIN custom_items i ON "
                         "i.uuid=e.process_uuid WHERE e.kind='technosphere' AND (e.target=? OR e.target LIKE ?)",
                         (cur, cur + "/%")):
            if r["process_uuid"] not in seen:
                seen.add(r["process_uuid"])
                order.append({"uuid": r["process_uuid"], "name": r["name"], "via": cur})
                todo.append(r["process_uuid"])
    models = {}
    if usage:
        for p in [uid] + [o["uuid"] for o in order]:
            it = store.one("SELECT ref_id, data FROM custom_items WHERE uuid=?", (p,))
            if not it:
                continue
            refs = [it["ref_id"]] + list((json.loads(it["data"] or "{}").get("coproduct_refs") or {}).values())
            for ref in refs:
                if ref:
                    for u in usage(ref):
                        models[u["project"]] = models.get(u["project"], 0) + u["lines"]
    return {"processes": order, "models": [{"project": k, "lines": v} for k, v in sorted(models.items())]}


def _save_item(store, kind, uid, db_id, ref_id, name, data, source, author):
    now = _now()
    with store.lock:
        old = store.conn.execute("SELECT revision, created FROM custom_items WHERE uuid=?", (uid,)).fetchone()
        if old:
            store.conn.execute("UPDATE custom_items SET name=?, data=?, source=?, author=?, modified=?, revision=?, "
                               "ref_id=COALESCE(?, ref_id) WHERE uuid=?",
                               (name, json.dumps(data), source, author, now, (old[0] or 1) + 1, ref_id, uid))
        else:
            store.conn.execute("INSERT INTO custom_items(uuid,kind,db_id,ref_id,name,data,source,author,created,modified,"
                               "revision) VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                               (uid, kind, db_id, ref_id, name, json.dumps(data), source, author, now, now))
        store.conn.commit()
    _log(store, uid, kind, "changed" if old else "created", author, {"name": name, "source": source, **data})


def _own(store, uid, kind, db_id):
    """The existing item with this UUID, or None. Refuses a UUID that belongs to another kind or database."""
    r = store.one("SELECT kind, db_id FROM custom_items WHERE uuid=?", (uid,))
    if r and (r["kind"] != kind or (db_id is not None and r["db_id"] != int(db_id))):
        raise CustomDataError("This identifier is already used by another item.")
    return _item(store, uid, kind) if r else None


def _new_uuid(given=None):
    if given:
        try:
            return str(uuidlib.UUID(str(given)))
        except ValueError:
            raise CustomDataError("The identifier is not a valid UUID.")
    return str(uuidlib.uuid4())


# ----------------------------------------------------------------------------------------------- user-defined units
def _reload_units(store):
    unitconv.set_custom([(r["name"], r["dimension"], r["factor"]) for r in store.q(
        "SELECT name, dimension, factor FROM custom_units ORDER BY name")])


def units_list(store):
    ensure_schema(store)
    dims = unitconv.dimensions()
    out = []
    for r in store.q("SELECT * FROM custom_units ORDER BY dimension, name"):
        r = dict(r)
        r["base"] = dims.get(r["dimension"], "")
        r["used"] = _unit_used(store, r["name"])
        out.append(r)
    return {"units": out, "dimensions": dims}


def _unit_used(store, name):
    n = unitconv.norm(name)
    sources = [
        "SELECT DISTINCT unit AS u FROM custom_exchanges", "SELECT DISTINCT unit_entered AS u FROM custom_factors",
        "SELECT DISTINCT json_extract(data,'$.unit') AS u FROM custom_items WHERE kind IN ('product','elementary')",
        "SELECT DISTINCT unit AS u FROM activities", "SELECT DISTINCT unit AS u FROM flows",
        "SELECT DISTINCT input_unit AS u FROM main.model_inputs"]
    for sql in sources:
        try:
            if any(unitconv.norm(r["u"]) == n for r in store.q(sql) if r["u"]):
                return True
        except Exception:
            continue
    return False


def save_unit(store, d):
    """A unit of your own: either in a known dimension with its factor to the base unit (a bag of 25 kg: mass, 25),
    or a new kind of quantity that is its own base unit (dimension 'new', for example 'seat')."""
    ensure_schema(store)
    name = _text(d.get("name"), "The unit name", maxlen=40)
    if not re.search(r"[A-Za-z]", name):
        raise CustomDataError("A unit name needs at least one letter.")
    if unitconv.builtin(name):
        raise CustomDataError(f"'{name}' is already a unit of Cyclia.")
    dims = unitconv.dimensions()
    dim = d.get("dimension") or ""
    if dim == "new":
        dim, factor = "custom:" + name, 1.0
    elif dim in dims or dim.startswith("custom:"):
        factor = _number(d.get("factor"), f"The size of one {name} in {dims.get(dim, dim[7:])}")
        if factor <= 0:
            raise CustomDataError("The conversion factor must be positive.")
        if dim == "custom:" + name and factor != 1:
            raise CustomDataError("The base unit of a new kind of quantity has the factor 1.")
    else:
        raise CustomDataError("Choose the kind of quantity of the unit, or 'new kind of quantity'.")
    clash = [r["name"] for r in store.q("SELECT name FROM custom_units WHERE name!=?", (name,))
             if unitconv.norm(r["name"]) == unitconv.norm(name)]
    if clash:
        raise CustomDataError(f"The unit '{clash[0]}' already exists.")
    old = store.one("SELECT dimension, factor FROM custom_units WHERE name=?", (name,))
    if old and (old["dimension"] != dim or abs(old["factor"] - factor) > 1e-15 * factor) and _unit_used(store, name):
        raise CustomDataError(f"'{name}' is in use, so its size cannot change: the amounts entered with it would "
                              "change meaning. Create a new unit instead.")
    with store.lock:
        store.conn.execute("INSERT OR REPLACE INTO custom_units VALUES(?,?,?,?,?,?,?)",
                           (name, dim, factor, _text(d.get("description"), "Description", False, 500),
                            _text(d.get("source"), "Source", False, 500), _text(d.get("author"), "Author", False, 200),
                            _now()))
        store.conn.commit()
    _reload_units(store)
    _log(store, "unit:" + name, "unit", "changed" if old else "created", d.get("author") or "",
         {"dimension": dim, "factor": factor})
    return name


def delete_unit(store, name):
    if not store.one("SELECT 1 AS x FROM custom_units WHERE name=?", (name,)):
        raise CustomDataError("The unit was not found.")
    if _unit_used(store, name):
        raise CustomDataError(f"'{name}' is in use. Change the amounts that use it first.")
    if store.one("SELECT 1 AS x FROM custom_units WHERE dimension=? AND name!=?", ("custom:" + name, name)):
        raise CustomDataError(f"Other units are defined in multiples of '{name}'. Delete them first.")
    store.x("DELETE FROM custom_units WHERE name=?", (name,))
    _reload_units(store)
    _log(store, "unit:" + name, "unit", "deleted")


# ----------------------------------------------------------------------------------------------- databases
def create_database(store, name, description="", author="", licence="", geography="", reference_period="",
                    version="1"):
    ensure_schema(store)
    db_id = store.create_database(_text(name, "The database name", maxlen=120), SOURCE, version or "1", "custom data",
                                  note=_text(description, "Description", required=False, maxlen=2000))
    store.set_database_meta(db_id, {"licence": licence, "geography": geography, "reference_period": reference_period,
                                    "importer_version": "custom data entry"})
    _save_item(store, "database", _new_uuid(), db_id, db_id, name, {"description": description}, "", author)
    return db_id


def is_custom(store, db_id):
    r = store.one("SELECT source FROM databases WHERE id=?", (int(db_id),))
    return bool(r and r["source"] == SOURCE)


def _need_custom(store, db_id):
    if not is_custom(store, db_id):
        raise CustomDataError("This database was imported and cannot be edited. Create a custom database for your own "
                              "data.")


def databases(store):
    ensure_schema(store)
    out = []
    for d in store.q("SELECT id, name, version, note, n_activities FROM databases WHERE source=? ORDER BY name", (SOURCE,)):
        d = dict(d)
        for kind in ("product", "process"):
            d["n_" + kind] = store.one("SELECT COUNT(*) AS n FROM custom_items WHERE kind=? AND db_id=?",
                                       (kind, d["id"]))["n"]
        out.append(d)
    return out


# ----------------------------------------------------------------------------------------------- product flows
def save_product(store, db_id, d):
    ensure_schema(store)
    _need_custom(store, db_id)
    uid = _new_uuid(d.get("uuid"))
    name = _text(d.get("name"), "The product name", maxlen=300)
    unit = check_unit(d.get("unit"), "The product unit")
    existing = store.one("SELECT uuid FROM custom_items WHERE kind='product' AND db_id=? AND lower(name)=lower(?) "
                         "AND uuid!=?", (int(db_id), name, uid))
    if existing:
        raise CustomDataError(f"A product called '{name}' already exists in this database.")
    old = _own(store, uid, "product", db_id)
    if old:
        if unitconv.norm(old["data"]["unit"]) != unitconv.norm(unit) and _product_used(store, uid):
            raise CustomDataError("The unit of a product that processes already use cannot be changed. Create a new "
                                  "product instead.")
    data = {"unit": unit, "description": _text(d.get("description"), "Description", required=False, maxlen=2000),
            "category": _text(d.get("category"), "Category", required=False, maxlen=200)}
    _save_item(store, "product", uid, int(db_id), None, name, data, _text(d.get("source"), "Source", False, 1000),
               _text(d.get("author"), "Author", False, 200))
    if old:
        compile(store, int(db_id))   # the datasets that make this product carry its name and unit
    return uid


def _product_used(store, uid):
    """A process makes the product, as reference product or as co-product."""
    return any(json.loads(r["data"]).get("product") == uid or
               any(c["product"] == uid for c in json.loads(r["data"]).get("coproducts") or [])
               for r in store.q("SELECT data FROM custom_items WHERE kind='process'"))


# ----------------------------------------------------------------------------------------------- elementary flows
def save_elementary(store, d):
    """A new elementary flow. Returns its UUID. Refused when the library already has the flow."""
    ensure_schema(store)
    name = _text(d.get("name"), "The flow name", maxlen=300)
    comp = _text(d.get("compartment"), "The compartment").lower()
    sub = _text(d.get("subcompartment"), "The subcompartment").lower()
    if comp not in COMPARTMENTS or sub not in COMPARTMENTS[comp]:
        raise CustomDataError(f"Choose the compartment and subcompartment from the list ('{comp}/{sub}' is not one).")
    if canon_context(comp, sub) != (comp, sub):
        raise CustomDataError(f"'{comp}/{sub}' is not a valid elementary-flow context.")
    unit = check_unit(d.get("unit"), "The flow unit")
    dim = unitconv.info(unit)[0]
    nl = name.lower()
    if sub == "land" or nl.startswith(("occupation", "transformation")):
        if nl.startswith("occupation") and dim != "landocc":
            raise CustomDataError("A land occupation flow needs an area x time unit (m2*a).")
        if nl.startswith("transformation") and dim != "area":
            raise CustomDataError("A land transformation flow needs an area unit (m2).")
        if sub != "land":
            raise CustomDataError("Land occupation and transformation flows belong to natural resource/land.")
    cas = _text(d.get("cas"), "CAS number", required=False, maxlen=20)
    if cas and not cas_ok(cas):
        raise CustomDataError(f"'{cas}' is not a valid CAS number (format 1234-56-7 with a matching check digit).")
    uid = _new_uuid(d.get("uuid"))
    mine = _own(store, uid, "elementary", None)
    if not mine and store.one("SELECT 1 AS x FROM flows WHERE uuid=?", (uid,)):
        raise CustomDataError("This flow belongs to an installed database and cannot be edited here.")
    from canon import canon as _canon
    cn = _canon(name, comp, sub)
    dup = store.one("SELECT uuid, name FROM flows WHERE c_name=? AND c_comp=? AND c_sub=? AND uuid!=?", (*cn, uid))
    if dup:
        raise CustomDataError(f"The library already has the flow '{dup['name']}' in {comp}/{sub}. Use it instead: "
                              "it keeps the factors of the installed methods.")
    data = {"compartment": comp, "subcompartment": sub, "unit": unit, "cas": cas,
            "description": _text(d.get("description"), "Description", required=False, maxlen=2000)}
    with store.lock:
        old = store.conn.execute("SELECT id, unit FROM flows WHERE uuid=?", (uid,)).fetchone()
        if old:
            if unitconv.norm(old[1]) != unitconv.norm(unit) and _flow_used(store, uid):
                raise CustomDataError("The unit of a flow that exchanges or factors already use cannot be changed.")
            prev, pcomp, psub, pname, pcas = store.conn.execute(
                "SELECT c_name, compartment, subcompartment, name, cas FROM flows WHERE uuid=?", (uid,)).fetchone()
            changed = [w for w, a, b in (("name", pname, name), ("compartment", pcomp, comp), ("subcompartment", psub, sub),
                                          ("CAS number", pcas or "", cas)) if (a or "") != (b or "")]
            if changed:
                # a factor belongs to a substance in a context: when either changes, the factors given for it are
                # no longer known to apply. They are kept for review and are not used until confirmed.
                store.conn.execute("UPDATE custom_factors SET review=? WHERE flow_uuid=? AND review IS NULL",
                                   (f"The flow's {', '.join(changed)} changed (was {pname}, {pcomp}/{psub}); "
                                    "confirm or correct this factor.", uid))
            store.conn.execute("UPDATE flows SET name=?, compartment=?, subcompartment=?, unit=?, cas=?, c_name=?, c_comp=?, "
                               "c_sub=? WHERE uuid=?", (name, comp, sub, unit, cas, *cn, uid))
            fid = old[0]
            # factors matched by name or context may change: drop this flow's matches and rematch the methods that
            # could match it (by its old or new name, or by its UUID)
            remat = [r[0] for r in store.conn.execute(
                "SELECT DISTINCT method_id FROM cf_raw WHERE c_name IN (?,?) OR flow_uuid=? UNION "
                "SELECT DISTINCT method_id FROM cfs WHERE flow_id=?", (prev, cn[0], uid, fid)).fetchall()]
            store.conn.execute("DELETE FROM cfs WHERE flow_id=?", (fid,))
            store.conn.execute("DELETE FROM cfs_regional WHERE flow_id=?", (fid,))
            remat += [r[0] for r in store.conn.execute("SELECT DISTINCT method_id FROM custom_factors WHERE flow_uuid=?",
                                                       (uid,)).fetchall()]
            store._bump_lib()
        else:
            fid = store.add_flow(uid, name, comp, sub, unit, cas)
            remat = []
        store.conn.commit()
    _save_item(store, "elementary", uid, None, fid, name, data, _text(d.get("source"), "Source", False, 1000),
               _text(d.get("author"), "Author", False, 200))
    if old:
        # rewrite this flow's own factors (those under review are left out) and rematch every method that could
        # characterise it
        _refresh_factors(store, sorted(set(remat)))
        calc.invalidate()
    return uid


def _flow_used(store, uid):
    return bool(store.one("SELECT 1 AS x FROM custom_exchanges WHERE kind='elementary' AND target=? UNION "
                          "SELECT 1 FROM custom_factors WHERE flow_uuid=?", (uid, uid)))


def flow_info(store, flow_uuid):
    r = store.one("SELECT id, uuid, name, compartment, subcompartment, unit FROM flows WHERE uuid=?", (flow_uuid,))
    if not r:
        raise CustomDataError("The elementary flow was not found.")
    r = dict(r)
    r["custom"] = bool(store.one("SELECT 1 AS x FROM custom_items WHERE uuid=? AND kind='elementary'", (flow_uuid,)))
    return r


# ----------------------------------------------------------------------------------------------- parameters
def _check_params(params, what):
    """[{name, value, formula, comment}] validated (names, numbers, formulas parse); returns the clean list."""
    out, seen = [], set()
    for q in params or []:
        name = _text(q.get("name"), "A parameter name", maxlen=60)
        if not fm.valid_name(name):
            raise CustomDataError(f"'{name}' is not a valid parameter name: use letters, digits and _, starting with a "
                                  "letter, and not a function name such as min or exp.")
        if name in seen:
            raise CustomDataError(f"The parameter '{name}' is defined twice in {what}.")
        seen.add(name)
        f = (q.get("formula") or "").strip()
        if f:
            try:
                fm.parse(f)
            except fm.FormulaError as e:
                raise CustomDataError(f"Parameter '{name}': {e}")
            v = None
        else:
            v = _number(q.get("value"), f"The value of parameter '{name}'", allow_zero=True)
        item = {"name": name, "value": v, "formula": f, "comment": _text(q.get("comment"), "Comment", False, 500),
                "utype": 0, "p1": None, "p2": None, "p3": None}
        t = (q.get("uncertainty") or {}).get("type") if isinstance(q.get("uncertainty"), dict) else None
        t = t or {1: "lognormal", 2: "normal", 3: "triangular", 4: "uniform"}.get(q.get("utype") or 0, "none")
        if t != "none":
            if f:
                raise CustomDataError(f"Parameter '{name}' is a formula; give the distribution to the parameters it uses.")
            u = q.get("uncertainty") if isinstance(q.get("uncertainty"), dict) else {
                "gsd": q.get("p1"), "sd": q.get("p1"), "min": q.get("p1"), "mode": q.get("p2"),
                "max": q.get("p3") if (q.get("utype") == 3) else q.get("p2")}
            if t == "lognormal":
                g = _number(u.get("gsd"), f"The GSD of parameter '{name}'")
                if g <= 1 or v <= 0:
                    raise CustomDataError(f"Parameter '{name}': a lognormal needs a positive value and a GSD above 1.")
                item.update(utype=1, p1=g)
            elif t == "normal":
                sd = _number(u.get("sd"), f"The standard deviation of parameter '{name}'")
                if sd <= 0:
                    raise CustomDataError(f"Parameter '{name}': the standard deviation must be positive.")
                item.update(utype=2, p1=sd)
            elif t == "triangular":
                lo, mo, hi = (_number(u.get(k), f"The {k} of parameter '{name}'", True) for k in ("min", "mode", "max"))
                if not (lo <= mo <= hi and lo < hi and lo <= v <= hi):
                    raise CustomDataError(f"Parameter '{name}': minimum <= most likely <= maximum, minimum < maximum, "
                                          "and the value between them.")
                item.update(utype=3, p1=lo, p2=mo, p3=hi)
            elif t == "uniform":
                lo, hi = (_number(u.get(k), f"The {k} of parameter '{name}'", True) for k in ("min", "max"))
                if not (lo < hi and lo <= v <= hi):
                    raise CustomDataError(f"Parameter '{name}': minimum < maximum, with the value between them.")
                item.update(utype=4, p1=lo, p2=hi)
            else:
                raise CustomDataError(f"Parameter '{name}': unknown distribution.")
        out.append(item)
    return out


def _db_params(store, db_id):
    r = store.one("SELECT data FROM custom_items WHERE kind='database' AND db_id=?", (int(db_id),))
    return (json.loads(r["data"] or "{}").get("parameters") or []) if r else []


def parameter_values(store, db_id, proc_data=None):
    """Resolved parameter values for a process: database parameters, overridden by the process's own."""
    by = {q["name"]: q for q in _db_params(store, db_id)}
    for q in (proc_data or {}).get("parameters") or []:
        by[q["name"]] = q
    try:
        return fm.resolve(list(by.values()))
    except fm.FormulaError as e:
        raise CustomDataError(f"Parameters: {e}")


def set_database_parameters(store, db_id, params, author=""):
    """Replace the parameters of a custom database. Every formula that uses them is evaluated again; the change is
    refused (and nothing is changed) when a formula fails or gives a negative amount."""
    _need_custom(store, db_id)
    clean = _check_params(params, "the database")
    r = store.one("SELECT uuid, name, data, source, author FROM custom_items WHERE kind='database' AND db_id=?",
                  (int(db_id),))
    if not r:
        raise CustomDataError("The custom database was not found.")
    old = json.loads(r["data"] or "{}")
    _save_item(store, "database", r["uuid"], int(db_id), None, r["name"], {**old, "parameters": clean}, r["source"] or "",
               author or r["author"] or "")
    try:
        compile(store, int(db_id))
    except Exception:
        _raw_data(store, r["uuid"], old)
        raise


def _raw_data(store, uid, data):
    """Restore an item's data without a new revision (used when a change is refused)."""
    with store.lock:
        store.conn.execute("UPDATE custom_items SET data=? WHERE uuid=?", (json.dumps(data), uid))
        store.conn.commit()


def mc_plan(store, mc):
    """Monte Carlo of the parameters of custom data. Returns None, or a sampler: deltas(rng) gives the change of the
    technosphere and elementary entries, for one iteration, caused by drawing every parameter with a distribution
    and evaluating the formulas again. Database parameters are drawn once per iteration and shared by all its
    processes; a process's own parameter replaces the database parameter of the same name."""
    try:
        dbs = store.q("SELECT id FROM databases WHERE source=?", (SOURCE,))
    except Exception:
        return None
    groups = []
    for d in dbs:
        dbp = _db_params(store, d["id"])
        for r in store.q("SELECT uuid, name, data FROM custom_items WHERE kind='process' AND db_id=?", (d["id"],)):
            pd = json.loads(r["data"] or "{}")
            by = {q["name"]: ("db", q) for q in dbp}
            for q in pd.get("parameters") or []:
                by[q["name"]] = ("proc", q)
            if not any((q.get("utype") or 0) > 0 for _, q in by.values()):
                continue
            exs = store.q("SELECT * FROM custom_exchanges WHERE process_uuid=? AND formula IS NOT NULL AND formula!=''",
                          (r["uuid"],))
            if not exs:
                continue
            outs = [(r["uuid"], d["id"])]
            shares = allocation_shares(store, pd) if pd.get("coproducts") else {pd["product"]: 1.0}
            aids = {pd["product"]: store.one("SELECT ref_id FROM custom_items WHERE uuid=?", (r["uuid"],))["ref_id"],
                    **(pd.get("coproduct_refs") or {})}
            entries = []
            for e in exs:
                fac = e["unit_factor"] if e["unit_factor"] is not None else 1.0
                ents = []
                for puid, f in shares.items():
                    aid = aids.get(puid)
                    if aid is None or f <= 0 or aid not in mc.act_index:
                        continue
                    col = mc.act_index[aid]
                    if e["kind"] == "elementary":
                        fr = store.one("SELECT id FROM flows WHERE uuid=?", (e["target"],))
                        if fr and fr["id"] in mc.flow_index:
                            ents.append(("B", mc.flow_index[fr["id"]], col, fac * f))
                    else:
                        sid = int(e["target"]) if str(e["target"]).isdigit() else target_activity(store, e["target"])
                        if sid not in mc.act_index:
                            continue
                        sp_ = store.one("SELECT production FROM activities WHERE id=?", (sid,))["production"] or 1.0
                        sign = (-1.0 if e["avoided"] else 1.0) * (-1.0 if sp_ < 0 else 1.0)
                        ents.append(("A", mc.act_index[sid], col, sign * fac * f))
                if ents:
                    entries.append((e["formula"], float(e["amount"]), ents))
            if entries:
                groups.append({"db": d["id"], "process": r["uuid"], "params": by, "entries": entries})
    if not groups:
        return None

    def deltas(rng):
        draws = {}
        rows = {"A": ([], [], []), "B": ([], [], [])}
        for g in groups:
            vals = []
            for name, (lvl, q) in g["params"].items():
                if q.get("formula"):
                    vals.append({"name": name, "formula": q["formula"]})
                    continue
                if (q.get("utype") or 0) > 0:
                    key = (g["db"], None, name) if lvl == "db" else (g["db"], g["process"], name)
                    if key not in draws:
                        draws[key] = float(calc.sample_param(rng, q))
                    vals.append({"name": name, "value": draws[key]})
                else:
                    vals.append({"name": name, "value": q["value"]})
            try:
                env = fm.resolve(vals)
            except fm.FormulaError:
                continue
            for formula, base, ents in g["entries"]:
                try:
                    v = float(fm.evaluate(formula, env))
                except fm.FormulaError:
                    continue
                if not math.isfinite(v):
                    continue
                dv = max(v, 0.0) - base       # amounts stay non-negative, as in the deterministic model
                if dv == 0:
                    continue
                for m, i, j, c in ents:
                    rows[m][0].append(i)
                    rows[m][1].append(j)
                    rows[m][2].append(c * dv)
        return rows

    keys = {(g["db"], None if lvl == "db" else g["process"], name) for g in groups
            for name, (lvl, q) in g["params"].items() if (q.get("utype") or 0) > 0}
    return {"deltas": deltas, "n_parameters": len(keys),
            "n_lines": sum(len(g["entries"]) for g in groups)}


# ----------------------------------------------------------------------------------------------- allocation
ALLOCATION = ("mass", "energy", "economic", "physical", "manual")


def allocation_shares(store, d):
    """{product uuid: share} of a process with co-products, from its allocation method:
    mass and energy: amount x (kg or MJ per unit, taken from the unit when it is a mass or energy unit);
    economic: amount x price per unit; manual: the given shares, which must add up to 1."""
    outs = [(d["product"], d["amount"])] + [(c["product"], c["amount"]) for c in d.get("coproducts") or []]
    if len(outs) == 1:
        return {d["product"]: 1.0}
    al = d.get("allocation") or {}
    method, vals = al.get("method"), al.get("values") or {}
    if method not in ALLOCATION:
        raise CustomDataError("Choose the allocation method for the co-products: mass, energy, economic, physical "
                              "causality or manual.")
    w = {}
    for uid, amt in outs:
        prod = _item(store, uid, "product")
        unit = prod["data"]["unit"]
        if method in ("mass", "energy"):
            dim, base = ("mass", "kg") if method == "mass" else ("energy", "MJ")
            i = unitconv.info(unit)
            if i and i[0] == dim:
                per = unitconv.factor(unit, base)
            else:
                v = vals.get(uid)
                if v in (None, ""):
                    raise CustomDataError(f"Give the {'mass (kg)' if method == 'mass' else 'energy content (MJ)'} per "
                                          f"{unit} of '{prod['name']}' for {method} allocation.")
                per = _number(v, f"The {method} value of '{prod['name']}'", allow_zero=True)
            if per < 0:
                raise CustomDataError("Allocation values cannot be negative.")
            w[uid] = amt * per
        elif method == "physical":
            v = vals.get(uid)
            prop = (al.get("property") or "").strip()
            if not prop:
                raise CustomDataError("Name the physical property that causes the shares (for example protein content, "
                                      "volume or machine hours) for physical causality allocation.")
            if v in (None, ""):
                raise CustomDataError(f"Give the {prop} per {unit} of '{prod['name']}'.")
            v = _number(v, f"The {prop} of '{prod['name']}'", allow_zero=True)
            if v < 0:
                raise CustomDataError("Allocation values cannot be negative.")
            w[uid] = amt * v
        elif method == "economic":
            v = vals.get(uid)
            if v in (None, ""):
                raise CustomDataError(f"Give the price per {unit} of '{prod['name']}' for economic allocation.")
            v = _number(v, f"The price of '{prod['name']}'", allow_zero=True)
            if v < 0:
                raise CustomDataError("Prices for allocation cannot be negative.")
            w[uid] = amt * v
        else:
            v = vals.get(uid)
            if v in (None, ""):
                raise CustomDataError(f"Give the share of '{prod['name']}' (manual allocation).")
            v = _number(v, f"The share of '{prod['name']}'", allow_zero=True)
            if not 0 <= v <= 1:
                raise CustomDataError("Manual shares lie between 0 and 1.")
            w[uid] = v
    tot = sum(w.values())
    if method == "manual":
        if abs(tot - 1) > 1e-6:
            raise CustomDataError(f"The manual shares add up to {tot:g}; they must add up to 1.")
        return w
    if tot <= 0:
        raise CustomDataError("The allocation values add up to zero, so no share can be calculated.")
    return {k: v / tot for k, v in w.items()}


def allocation_compare(store, uid, method_ids, alternatives=None):
    """Sensitivity of the results of a multi-output process to the allocation method.

    The process's total burden T (all outputs together) does not depend on the allocation, because the allocated
    datasets together carry exactly the exchanges of the process: T = sum_i a_i x I_i, with I_i the current result
    per unit of output i. Under another method m, output i carries f_i,m x T, so I_i,m = f_i,m x T / a_i. This holds
    exactly when the process does not use its own outputs, directly or through its supply chain; otherwise the
    comparison is refused. alternatives: {method: values} to try values not saved with the process."""
    p = _item(store, uid, "process")
    d = p["data"]
    if not d.get("coproducts"):
        raise CustomDataError("This process has one product, so there is nothing to allocate.")
    dep = dependents(store, uid)
    ups, todo = set(), [uid]
    while todo:
        cur = todo.pop()
        for e in store.q("SELECT target FROM custom_exchanges WHERE process_uuid=? AND kind='technosphere'", (cur,)):
            t = str(e["target"]).split("/")[0]
            if not t.isdigit() and t not in ups:
                ups.add(t)
                todo.append(t)
    if uid in ups or ups & {x["uuid"] for x in dep["processes"]}:
        raise CustomDataError("The process uses its own products through its supply chain, so the comparison would not "
                              "be exact. Compare by saving each allocation in turn instead.")
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, [int(m) for m in method_ids])
    outs = [(d["product"], d["amount"])] + [(c["product"], c["amount"]) for c in d["coproducts"]]
    aids = {d["product"]: p["ref_id"], **(d.get("coproduct_refs") or {})}
    per_unit = {}
    for puid, _ in outs:
        j = mc.act_index.get(aids.get(puid))
        if j is None:
            raise CustomDataError("The datasets of this process are not compiled yet.")
        f = np.zeros(mc.n)
        f[j] = 1.0
        s = mc.solve(f)
        per_unit[puid] = np.asarray(M.Q @ s).ravel()
    T = sum(a * per_unit[u] for u, a in outs)
    current = (d.get("allocation") or {}).get("method")
    tries = {}
    for m in ALLOCATION:
        al = dict(d.get("allocation") or {})
        al["method"] = m
        if alternatives and m in alternatives:
            al.update(alternatives[m])
        elif m != current:
            al["values"] = {}           # values saved for another method do not apply to this one
        try:
            tries[m] = allocation_shares(store, {**d, "allocation": al})
        except CustomDataError as e:
            tries[m] = str(e)
    names = {u: _item(store, u, "product")["name"] for u, _ in outs}
    units_ = {u: _item(store, u, "product")["data"]["unit"] for u, _ in outs}
    rows = []
    for m, sh in tries.items():
        if isinstance(sh, str):
            rows.append({"method": m, "available": False, "reason": sh})
            continue
        rows.append({"method": m, "available": True, "current": m == current, "outputs": [
            {"product": names[u], "unit": units_[u], "share": sh[u],
             "per_unit": [float(sh[u] * T[k] / a) if a else None for k in range(len(M.ids))]} for u, a in outs]})
    return {"methods": [{k: r[k] for k in ("id", "family", "category", "indicator", "unit")} for r in M.rows],
            "comparison": rows, "total_burden": [float(x) for x in T],
            "note": "Per unit of each product. The total burden of the process is the same under every method; "
                    "only its division between the products changes."}


# ----------------------------------------------------------------------------------------------- processes
def save_process(store, db_id, d):
    ensure_schema(store)
    _need_custom(store, db_id)
    uid = _new_uuid(d.get("uuid"))
    _own(store, uid, "process", db_id)
    name = _text(d.get("name"), "The process name", maxlen=300)
    prod = _item(store, _text(d.get("product"), "The reference product"), "product")
    if prod["db_id"] != int(db_id):
        raise CustomDataError("The reference product belongs to another custom database.")
    amount = _number(d.get("amount", 1.0), "The reference amount")
    if amount < 0:
        raise CustomDataError("Give the reference amount as a positive number; choose 'treatment' for a waste "
                              "treatment process.")
    kind = d.get("type") or "production"
    if kind not in ("production", "treatment"):
        raise CustomDataError("The process type is production or treatment.")
    loc = _text(d.get("location") or "GLO", "The location", maxlen=40).upper()
    dq = {}
    for k in ("ter", "ger", "tir", "p"):
        v = (d.get("dq") or {}).get(k)
        if v in (None, ""):
            continue
        v = _number(v, f"Data quality {k.upper()}")
        if not 1 <= v <= 5:
            raise CustomDataError("Data quality ratings go from 1 (very good) to 5 (very poor).")
        dq[k] = v
    if dq and len(dq) < 4:
        raise CustomDataError("Give all four data quality ratings (TeR, GeR, TiR, P) or none.")
    before = snapshot(store, uid)
    old = store.one("SELECT data FROM custom_items WHERE uuid=?", (uid,))
    old = json.loads(old["data"]) if old else None
    cps, seen = [], {prod["uuid"]}
    for cp in d.get("coproducts") or []:
        cprod = _item(store, _text(cp.get("product"), "A co-product"), "product")
        if cprod["db_id"] != int(db_id):
            raise CustomDataError("A co-product belongs to another custom database.")
        if cprod["uuid"] in seen:
            raise CustomDataError(f"'{cprod['name']}' is listed twice among the outputs of the process.")
        seen.add(cprod["uuid"])
        cps.append({"product": cprod["uuid"], "amount": _number(cp.get("amount"), f"The amount of '{cprod['name']}'")})
        if cps[-1]["amount"] < 0:
            raise CustomDataError("Co-product amounts are positive.")
    if cps and kind == "treatment":
        raise CustomDataError("A waste treatment process has no co-products here; model recovered products as "
                              "avoided products instead.")
    al = d.get("allocation") or {}
    allocation = {"method": al.get("method") or "", "values": {k: v for k, v in (al.get("values") or {}).items()
                                                                if k in seen and v not in (None, "")},
                  "source": _text(al.get("source"), "Source of the allocation values", False, 500),
                  "property": _text(al.get("property"), "The physical property", False, 120),
                  "property_unit": _text(al.get("property_unit"), "The unit of the property", False, 40),
                  "currency": _text(al.get("currency"), "The currency", False, 12).upper(),
                  "price_year": al.get("price_year")} if cps else {}
    if cps and allocation["method"] == "economic":
        # prices change over time and between currencies: both are part of the allocation's definition
        if not allocation["currency"]:
            raise CustomDataError("Give the currency of the prices (for example EUR or USD) for economic allocation.")
        y = _number(allocation["price_year"], "The year of the prices")
        if not 1900 <= y <= 2100 or y != int(y):
            raise CustomDataError("The year of the prices is a year such as 2025.")
        allocation["price_year"] = int(y)
    data = {"product": prod["uuid"], "amount": amount, "type": kind, "location": loc,
            "technology": _text(d.get("technology"), "Technology", False, 2000),
            "time_period": _text(d.get("time_period"), "Time period", False, 100),
            "comment": _text(d.get("comment"), "Comment", False, 3000), "dq": dq,
            "data_type": d.get("data_type") if d.get("data_type") in ("primary", "secondary", "estimate") else "",
            "parameters": _check_params(d.get("parameters") if "parameters" in d else (old or {}).get("parameters"),
                                        "the process"),
            "coproducts": cps, "allocation": allocation,
            "coproduct_refs": (old or {}).get("coproduct_refs") or {}, "layout": (old or {}).get("layout")}
    if cps:
        allocation_shares(store, data)          # validates the method and its values before anything is saved
    gone = [k for k in data["coproduct_refs"] if k not in {c["product"] for c in cps}]
    for g in gone:
        if store.one("SELECT 1 AS x FROM custom_exchanges WHERE kind='technosphere' AND target=?", (f"{uid}/{g}",)):
            raise CustomDataError("Another process uses a co-product you removed. Change that input first.")
        ref = data["coproduct_refs"][g]
        if store.one("SELECT 1 AS x FROM main.model_inputs WHERE kind='activity' AND ref_id=?", (ref,)):
            raise CustomDataError("A model of this project uses a co-product you removed. Remove that line first.")
    _save_item(store, "process", uid, int(db_id), None, name, data, _text(d.get("source"), "Source", False, 1000),
               _text(d.get("author"), "Author", False, 200))
    try:
        compile(store, int(db_id))
    except Exception:
        if old is not None:
            _raw_data(store, uid, old)
        else:
            store.x("DELETE FROM custom_items WHERE uuid=?", (uid,))
        compile(store, int(db_id))
        raise
    _attach_versions(store, uid, before)
    return uid


def save_layout(store, uid, x, y):
    """Position of a process in the diagram (no new revision: layout is not data)."""
    it = _item(store, uid, "process")
    _raw_data(store, uid, {**it["data"], "layout": [float(_number(x, "x", True)), float(_number(y, "y", True))]})


def _supplier(store, target):
    """(activity id, unit, production, label) of a supplier: a custom process UUID or a library dataset id."""
    if isinstance(target, str) and not target.isdigit():
        puid, _, cprod = target.partition("/")
        p = _item(store, puid, "process")
        if not p["ref_id"]:
            raise CustomDataError("The supplier process has not been saved yet.")
        if cprod and cprod != p["data"]["product"]:
            cp = [c for c in p["data"].get("coproducts") or [] if c["product"] == cprod]
            ref = (p["data"].get("coproduct_refs") or {}).get(cprod)
            if not cp or not ref:
                raise CustomDataError("That co-product is no longer an output of the process.")
            prod = _item(store, cprod, "product")
            return ref, prod["data"]["unit"], cp[0]["amount"], f"{p['name']} ({prod['name']})"
        prod = _item(store, p["data"]["product"], "product")
        sign = -1.0 if p["data"]["type"] == "treatment" else 1.0
        return p["ref_id"], prod["data"]["unit"], sign * p["data"]["amount"], p["name"]
    a = store.one("SELECT id, name, unit, production FROM activities WHERE id=?", (int(target),))
    if not a:
        raise CustomDataError("The supplier dataset was not found.")
    return a["id"], a["unit"], float(a["production"] or 1.0), a["name"]


def _uncertainty(d, amount_ref, factor, kind, name):
    """(utype, p1, p2, p3, pedigree, label) in the reference unit. factor converts entered values to it."""
    ped = d.get("pedigree")
    t = d.get("uncertainty") or ("pedigree" if ped else "none")
    if t == "pedigree":
        scores = [int(_number(x, "A pedigree score")) for x in (ped or [])]
        if len(scores) != 5 or not all(1 <= x <= 5 for x in scores):
            raise CustomDataError("Give five pedigree scores from 1 to 5.")
        return 1, calc.pedigree_sigma(scores, kind, name), None, None, scores, "pedigree"
    if t not in UNCERTAINTY:
        raise CustomDataError("Unknown uncertainty type.")
    if t == "none":
        return 0, None, None, None, None, "none"
    if t == "lognormal":
        gsd = _number(d.get("gsd"), "The geometric standard deviation")
        if gsd <= 1:
            raise CustomDataError("The geometric standard deviation must be greater than 1.")
        return 1, math.log(gsd), None, None, None, "lognormal"
    if t == "normal":
        sd = _number(d.get("sd"), "The standard deviation")
        if sd <= 0:
            raise CustomDataError("The standard deviation must be positive.")
        return 2, abs(sd * factor), None, None, None, "normal"
    lo = _number(d.get("min"), "The minimum", allow_zero=True) * factor
    hi = _number(d.get("max"), "The maximum", allow_zero=True) * factor
    if t == "triangular":
        mode = _number(d.get("mode", d.get("amount")), "The most likely value", allow_zero=True) * factor
        if not lo <= mode <= hi or lo == hi:
            raise CustomDataError("Triangular: minimum <= most likely <= maximum, and minimum < maximum.")
        if not lo <= amount_ref <= hi:
            raise CustomDataError("The amount must lie between the minimum and the maximum.")
        return 3, lo, mode, hi, None, "triangular"
    if not lo < hi or not lo <= amount_ref <= hi:
        raise CustomDataError("Uniform: minimum < maximum, with the amount between them.")
    return 4, lo, hi, None, None, "uniform"


def save_exchange(store, process_uuid, d):
    """An input from a supplier (kind 'technosphere') or an elementary exchange (kind 'elementary')."""
    ensure_schema(store)
    p = _item(store, process_uuid, "process")
    before = snapshot(store, process_uuid)
    kind = d.get("kind")
    formula = (d.get("formula") or "").strip()
    if formula:
        try:
            amount = fm.evaluate(formula, parameter_values(store, p["db_id"], p["data"]))
        except fm.FormulaError as e:
            raise CustomDataError(f"The formula '{formula}': {e}")
        amount = _number(amount, "The value of the formula", allow_zero=True)
        if (d.get("uncertainty") or "none") in ("triangular", "uniform"):
            raise CustomDataError("A line with a formula takes no triangular or uniform range, because the range would "
                                  "not follow the formula. Use lognormal, normal or pedigree scores, or give "
                                  "parameters their own scenarios.")
    else:
        amount = _number(d.get("amount"), "The amount")
    unit = check_unit(d.get("unit"))
    avoided = bool(d.get("avoided"))
    if kind == "technosphere":
        target = str(_text(d.get("supplier"), "The supplier"))
        sid, sunit, sprod, sname = _supplier(store, target)
        if target == process_uuid and amount * convert(1.0, unit, sunit) >= abs(sprod):
            raise CustomDataError("A process cannot consume as much of its own product as it makes.")
        ref_unit, uname = sunit, sname
    elif kind == "elementary":
        f = flow_info(store, _text(d.get("flow"), "The elementary flow"))
        target, ref_unit, uname = f["uuid"], f["unit"], f["name"]
        if avoided:
            raise CustomDataError("Elementary exchanges cannot be avoided products.")
    else:
        raise CustomDataError("The exchange kind is technosphere or elementary.")
    if amount < 0:
        raise CustomDataError("Give a positive amount; mark an avoided product with 'avoided'.")
    fac = convert(1.0, unit, ref_unit)
    amount_ref = amount * fac
    utype, p1, p2, p3, ped, ulabel = _uncertainty({**d, "amount": amount}, amount_ref, fac,
                                                  "flow" if kind == "elementary" else "activity", uname)
    author = _text(d.get("author"), "Author", False, 200)
    now = _now()
    row = (process_uuid, kind, target, amount, unit, amount_ref, int(avoided), utype, p1, p2, p3,
           json.dumps(ped) if ped else None, ulabel, _text(d.get("source"), "Source", False, 1000),
           _text(d.get("comment"), "Comment", False, 2000), now, author, formula or None, fac)
    with store.lock:
        if d.get("id"):
            n = store.conn.execute("UPDATE custom_exchanges SET process_uuid=?, kind=?, target=?, amount=?, unit=?, "
                                   "amount_ref=?, avoided=?, utype=?, p1=?, p2=?, p3=?, pedigree=?, uncertainty=?, "
                                   "source=?, comment=?, modified=?, author=?, formula=?, unit_factor=?, "
                                   "revision=COALESCE(revision,1)+1 "
                                   "WHERE id=? AND process_uuid=?", row + (int(d["id"]), process_uuid)).rowcount
            if not n:
                raise CustomDataError("The exchange was not found.")
            eid = int(d["id"])
        else:
            eid = store.conn.execute("INSERT INTO custom_exchanges(process_uuid,kind,target,amount,unit,amount_ref,avoided,"
                                     "utype,p1,p2,p3,pedigree,uncertainty,source,comment,modified,author,formula,"
                                     "unit_factor,created,revision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                                     row + (now,)).lastrowid
        store.conn.commit()
    _log(store, process_uuid, "exchange", "exchange changed" if d.get("id") else "exchange added", author,
         {"exchange": eid, "kind": kind, "target": target, "amount": amount, "unit": unit, "avoided": avoided,
          "formula": formula, "uncertainty": ulabel, "source": row[13]})
    try:
        compile(store, p["db_id"])
    except Exception:
        _put_back(store, process_uuid, before, p["db_id"])
        raise
    _attach_versions(store, process_uuid, before)
    return eid


def delete_exchange(store, process_uuid, exchange_id):
    p = _item(store, process_uuid, "process")
    old = store.one("SELECT kind, target, amount, unit FROM custom_exchanges WHERE id=? AND process_uuid=?",
                    (int(exchange_id), process_uuid))
    if not old:
        raise CustomDataError("The exchange was not found.")
    before = snapshot(store, process_uuid)
    store.x("DELETE FROM custom_exchanges WHERE id=? AND process_uuid=?", (int(exchange_id), process_uuid))
    _log(store, process_uuid, "exchange", "exchange removed", "", {"exchange": int(exchange_id), **old})
    compile(store, p["db_id"])
    _attach_versions(store, process_uuid, before)


def delete_item(store, uid):
    """Delete a product, elementary flow or process that nothing uses."""
    it = _item(store, uid)
    before = snapshot(store, uid) if it["kind"] == "process" else None
    _delete_item(store, uid, it)
    _log(store, uid, it["kind"], "deleted", "", {"name": it["name"], "before": before, "after": None}
         if before else {"name": it["name"]})


def _delete_item(store, uid, it):
    if it["kind"] == "product":
        if _product_used(store, uid):
            raise CustomDataError("A process produces this product. Delete or change that process first.")
        store.x("DELETE FROM custom_items WHERE uuid=?", (uid,))
        return
    if it["kind"] == "elementary":
        if _flow_used(store, uid):
            raise CustomDataError("Exchanges or factors use this flow. Remove them first.")
        if store.one("SELECT 1 AS x FROM bio b JOIN flows f ON f.id=b.flow_id WHERE f.uuid=?", (uid,)):
            raise CustomDataError("A dataset of the library uses this flow.")
        with store.lock:
            store.conn.execute("DELETE FROM flows WHERE uuid=?", (uid,))
            store.conn.execute("DELETE FROM custom_items WHERE uuid=?", (uid,))
            store._bump_lib()
            store.conn.commit()
        calc.invalidate()
        return
    if it["kind"] == "process":
        if store.one("SELECT 1 AS x FROM custom_exchanges WHERE kind='technosphere' AND (target=? OR target LIKE ?) "
                     "AND process_uuid!=?", (uid, uid + "/%", uid)):
            raise CustomDataError("Another process uses this process as a supplier. Change that input first.")
        for ref in (it["data"].get("coproduct_refs") or {}).values():
            if store.one("SELECT 1 AS x FROM main.model_inputs WHERE kind='activity' AND ref_id=?", (ref,)):
                raise CustomDataError("A model of this project uses a co-product of this process. Remove that line first.")
        if it["ref_id"] and store.one("SELECT 1 AS x FROM tech WHERE input_id=? AND output_id NOT IN "
                                      "(SELECT id FROM activities WHERE db_id=?)", (it["ref_id"], it["db_id"])):
            raise CustomDataError("A dataset of another database uses this process.")
        if it["ref_id"] and store.one("SELECT 1 AS x FROM main.model_inputs WHERE kind='activity' AND ref_id=?",
                                      (it["ref_id"],)):
            raise CustomDataError("A model of this project uses this process. Remove that line first.")
        with store.lock:
            store.conn.execute("DELETE FROM custom_exchanges WHERE process_uuid=?", (uid,))
            store.conn.execute("DELETE FROM custom_items WHERE uuid=?", (uid,))
            for ref in [it["ref_id"]] + list((it["data"].get("coproduct_refs") or {}).values()):
                if not ref:
                    continue
                for sql in ("DELETE FROM tech WHERE output_id=?", "DELETE FROM bio WHERE activity_id=?",
                            "DELETE FROM unlinked WHERE output_id=?", "DELETE FROM activity_dq WHERE activity_id=?",
                            "DELETE FROM activities WHERE id=?"):
                    store.conn.execute(sql, (ref,))
            store.conn.commit()
        compile(store, it["db_id"])
        return
    raise CustomDataError("This item cannot be deleted here.")


# ----------------------------------------------------------------------------------------------- factors and methods
SCOPES = ("unknown", "zero")


def _scope(unlisted, reason):
    unlisted = unlisted or "unknown"
    if unlisted not in SCOPES:
        raise CustomDataError("Flows without a factor are either unknown or have no effect in this category.")
    reason = _text(reason, "The reason why flows without a factor have no effect", unlisted == "zero", 1000)
    return unlisted, reason


def create_method(store, family, category, indicator, unit, source, author="", unlisted="unknown", unlisted_reason=""):
    """A custom impact category. unlisted: how a flow without a factor in it is treated. 'unknown' (default): the
    factor is unknown and the result is incomplete until a factor or a 'does not apply' decision is recorded.
    'zero': the method is complete, a flow without a factor has no effect (the reason is required)."""
    unlisted, unlisted_reason = _scope(unlisted, unlisted_reason)
    ensure_schema(store)
    family = _text(family, "The method name", maxlen=200)
    category = _text(category, "The impact category", maxlen=200)
    indicator = _text(indicator or category, "The indicator", maxlen=200)
    unit = _text(unit, "The indicator unit (for example kg CO2-eq)", maxlen=60)
    src = _text(source, "The source of the method (publication or standard)", maxlen=1000)
    if store.method_by_key(family, category, indicator):
        raise CustomDataError("This method, category and indicator already exist.")
    mid = store.get_or_create_method(family, category, indicator, unit, METHOD_SOURCE, note=src)
    _save_item(store, "method", _new_uuid(), None, mid, f"{family} | {category}",
               {"unit": unit, "unlisted": unlisted, "unlisted_reason": unlisted_reason}, src, author)
    return mid


def method_scopes(store):
    """{method id: (unlisted, reason)} of the custom methods."""
    ensure_schema(store)
    out = {}
    for r in store.q("SELECT ref_id, data FROM custom_items WHERE kind='method'"):
        d = json.loads(r["data"] or "{}")
        out[r["ref_id"]] = (d.get("unlisted") or "unknown", d.get("unlisted_reason") or "")
    return out


def set_method_scope(store, method_id, unlisted, reason="", author=""):
    it = store.one("SELECT uuid FROM custom_items WHERE kind='method' AND ref_id=?", (int(method_id),))
    if not it:
        raise CustomDataError("Only custom methods can be changed here.")
    item = _item(store, it["uuid"], "method")
    unlisted, reason = _scope(unlisted, reason)
    _save_item(store, "method", item["uuid"], None, None, item["name"],
               {**item["data"], "unlisted": unlisted, "unlisted_reason": reason}, item["source"], author or item["author"])
    calc.invalidate()


def delete_method(store, method_id):
    it = store.one("SELECT uuid, name FROM custom_items WHERE kind='method' AND ref_id=?", (int(method_id),))
    if not it:
        raise CustomDataError("Only custom methods can be deleted here.")
    mid = int(method_id)
    with store.lock:
        for t in ("cfs", "cfs_regional", "cf_raw", "nw", "custom_factors"):
            store.conn.execute(f"DELETE FROM {t} WHERE method_id=?", (mid,))
        store.conn.execute("DELETE FROM methods WHERE id=?", (mid,))
        store.conn.execute("DELETE FROM custom_items WHERE uuid=?", (it["uuid"],))
        store._bump_lib()
        store.conn.commit()
    _log(store, it["uuid"], "method", "deleted", "", {"name": it["name"]})
    calc.invalidate()


def custom_methods(store):
    ensure_schema(store)
    return {r["ref_id"] for r in store.q("SELECT ref_id FROM custom_items WHERE kind='method'")}


def save_factor(store, method_id, flow_uuid, status, value=None, unit=None, source="", comment="", author=""):
    """status 'value': a characterisation factor (per `unit` of the flow's dimension) with its source.
    status 'not_applicable': the category does not apply to the flow, with the reason. Never an implicit zero."""
    ensure_schema(store)
    m = store.one("SELECT id, unit FROM methods WHERE id=?", (int(method_id),))
    if not m:
        raise CustomDataError("The impact category was not found.")
    f = flow_info(store, flow_uuid)
    if not f["custom"] and int(method_id) not in custom_methods(store):
        raise CustomDataError("Factors of installed methods for library flows come from the method itself. Assign "
                              "factors here to your own flows, or create a custom method.")
    if status == "value":
        v = _number(value, "The factor", allow_zero=True)
        u = check_unit(unit or f["unit"], "The unit the factor refers to")
        # factor per u -> per the flow's unit: CF_ref = CF_u x (amount in u per 1 flow unit)
        ref = v * convert(1.0, f["unit"], u, "The factor")
        src = _text(source, "The source of the factor")
        row = (int(method_id), flow_uuid, "value", ref, v, u, src, _text(comment, "Comment", False, 2000))
    elif status == "not_applicable":
        row = (int(method_id), flow_uuid, "not_applicable", None, None, None, _text(source, "Source", False, 1000),
               _text(comment, "The reason why this category does not apply"))
    else:
        raise CustomDataError("Give a factor or state that the category does not apply.")
    with store.lock:
        store.conn.execute("INSERT OR REPLACE INTO custom_factors(method_id,flow_uuid,status,value,value_entered,"
                           "unit_entered,source,comment,author,modified,review) VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                           row + (_text(author, "Author", False, 200), _now()))
        store.conn.commit()
    _log(store, flow_uuid, "factor", "factor saved", author,
         {"method_id": int(method_id), "status": status, "value_entered": row[4], "unit": row[5], "source": row[6],
          "comment": row[7]})
    _refresh_factors(store, [int(method_id)])


def confirm_factor(store, method_id, flow_uuid, author=""):
    """Accept a factor that was put under review, unchanged."""
    r = store.one("SELECT * FROM custom_factors WHERE method_id=? AND flow_uuid=?", (int(method_id), flow_uuid))
    if not r or not r["review"]:
        raise CustomDataError("This factor is not under review.")
    store.x("UPDATE custom_factors SET review=NULL, author=?, modified=? WHERE method_id=? AND flow_uuid=?",
            (author or r["author"], _now(), int(method_id), flow_uuid))
    _log(store, flow_uuid, "factor", "factor confirmed after review", author, {"method_id": int(method_id)})
    _refresh_factors(store, [int(method_id)])


def delete_factor(store, method_id, flow_uuid):
    store.x("DELETE FROM custom_factors WHERE method_id=? AND flow_uuid=?", (int(method_id), flow_uuid))
    _log(store, flow_uuid, "factor", "factor removed", "", {"method_id": int(method_id)})
    _refresh_factors(store, [int(method_id)])


def _refresh_factors(store, method_ids=None):
    """Write custom factors into cf_raw (matched by flow UUID) and rematch the affected categories. Factors of
    installed methods for library flows are not touched."""
    from importers import lcia
    from canon import canon as _canon
    rows = store.q("SELECT c.method_id, c.flow_uuid, c.value, f.name, f.compartment, f.subcompartment FROM custom_factors c "
                   "JOIN flows f ON f.uuid=c.flow_uuid WHERE c.status='value' AND c.review IS NULL")
    mids = set(method_ids or []) | {r["method_id"] for r in rows}
    if not mids:
        return
    cmeth = custom_methods(store)
    cflows = [r["ref_id"] for r in store.q("SELECT ref_id FROM custom_items WHERE kind='elementary' AND ref_id IS NOT NULL")]
    cuuids = [r["uuid"] for r in store.q("SELECT uuid FROM custom_items WHERE kind='elementary'")]
    with store.lock:
        c = store.conn
        for mid in mids:
            if mid in cmeth:
                for t in ("cf_raw", "cfs", "cfs_regional"):
                    c.execute(f"DELETE FROM {t} WHERE method_id=?", (mid,))
                continue
            if cuuids:
                c.execute(f"DELETE FROM cf_raw WHERE method_id=? AND flow_uuid IN ({','.join('?' * len(cuuids))})",
                          [mid] + cuuids)
            if cflows:
                for t in ("cfs", "cfs_regional"):
                    c.execute(f"DELETE FROM {t} WHERE method_id=? AND flow_id IN ({','.join('?' * len(cflows))})",
                              [mid] + cflows)
        c.executemany("INSERT INTO cf_raw VALUES(?,?,?,?,?,?,?)",
                      [(r["method_id"], *_canon(r["name"], r["compartment"], r["subcompartment"]), "", r["flow_uuid"],
                        r["value"]) for r in rows if r["method_id"] in mids])
        c.commit()
    lcia.rematch(store, sorted(mids))
    calc.invalidate()


def factor_table(store, method_ids):
    """Factor status per impact category: value, not_applicable or missing. Covers every custom flow, and in a custom
    method also the library flows that custom processes use. A factor of zero with its source is a value."""
    ensure_schema(store)
    custom = store.q("SELECT f.id, f.uuid, f.name, f.compartment, f.subcompartment, f.unit FROM custom_items i "
                     "JOIN flows f ON f.uuid=i.uuid WHERE i.kind='elementary' ORDER BY f.name")
    cids = {f["uuid"] for f in custom}
    lib = [f for f in store.q("SELECT DISTINCT f.id, f.uuid, f.name, f.compartment, f.subcompartment, f.unit FROM "
                              "custom_exchanges e JOIN flows f ON f.uuid=e.target WHERE e.kind='elementary' "
                              "ORDER BY f.name") if f["uuid"] not in cids]
    scopes = method_scopes(store)
    out = []
    for mid in method_ids:
        m = store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (int(mid),))
        if not m:
            continue
        dec = {r["flow_uuid"]: dict(r) for r in store.q("SELECT * FROM custom_factors WHERE method_id=?", (int(mid),))}
        matched = {r["flow_id"]: r["value"] for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (int(mid),))}
        flows = custom + (lib if m["id"] in scopes else [])
        for f in flows:
            d = dec.get(f["uuid"])
            st = ("review" if d and d.get("review") else d["status"]) if d else ("value" if f["id"] in matched else "missing")
            if st == "missing" and f["uuid"] not in cids and scopes.get(m["id"], ("unknown",))[0] == "zero":
                st = "outside_scope"
            out.append({"method_id": m["id"], "family": m["family"], "category": m["category"], "indicator": m["indicator"],
                        "method_unit": m["unit"], "flow_uuid": f["uuid"], "flow": f["name"], "custom_flow": f["uuid"] in cids,
                        "compartment": f"{f['compartment']}/{f['subcompartment']}", "flow_unit": f["unit"], "status": st,
                        "review": d.get("review") if d else None, "previous_status": d["status"] if d else None,
                        "value": d["value"] if d and d["status"] == "value" else matched.get(f["id"]),
                        "value_entered": d.get("value_entered") if d else None, "unit_entered": d.get("unit_entered") if d else None,
                        "source": d.get("source") if d else ("installed method" if f["id"] in matched else ""),
                        "comment": d.get("comment") if d else (scopes[m["id"]][1] if st == "outside_scope" else "")})
    return out


def factor_gaps(store, mc, M, g, flow_label, limit=25):
    """Per category: flows of the inventory g whose characterisation factor is unknown. A factor is known when the
    method has one for the flow (whatever its value, zero included), when a factor was recorded here (zero
    included), or when the category was recorded as not applying to the flow. Unknown, and so never taken as zero:
    - a custom flow without a known factor, in any method (installed methods do not know new flows);
    - any flow without a known factor in a custom method whose scope says that such flows are unknown (the default).
    Returns a list aligned with M.ids of None or {"n", "custom_method", "flows"}."""
    try:
        custom_flow_ids = {r["ref_id"] for r in store.q("SELECT ref_id FROM custom_items WHERE kind='elementary'")}
        scopes = method_scopes(store)
    except Exception:   # library without the custom tables
        return [None] * len(M.ids)
    open_methods = {m for m, (sc, _) in scopes.items() if sc == "unknown"} & set(M.ids)
    if not custom_flow_ids and not open_methods:
        return [None] * len(M.ids)
    q = ",".join("?" * len(M.ids))
    known = {}
    for sql in (f"SELECT method_id, flow_id FROM cfs WHERE method_id IN ({q})",
                f"SELECT DISTINCT method_id, flow_id FROM cfs_regional WHERE method_id IN ({q})",
                f"SELECT c.method_id, f.id AS flow_id FROM custom_factors c JOIN flows f ON f.uuid=c.flow_uuid "
                f"WHERE c.review IS NULL AND c.method_id IN ({q})"):
        for r in store.q(sql, list(M.ids)):
            known.setdefault(r["method_id"], set()).add(r["flow_id"])
    nz = np.where(np.abs(g) > 1e-15 * (np.abs(g).max() or 1))[0] if len(g) else []
    Cd = getattr(M, "Cd", M.C)
    out = []
    for k, mid in enumerate(M.ids):
        kn = known.get(mid, set())
        miss = []
        for i in nz:
            fid = int(mc.flow_ids[i])
            if fid in kn or M.C[k, i] != 0 or Cd[k, i] != 0:
                continue
            if fid in custom_flow_ids or mid in open_methods:
                miss.append(i)
        if not miss:
            out.append(None)
            continue
        miss.sort(key=lambda i: -abs(g[i]))
        out.append({"n": len(miss), "custom_method": mid in scopes,
                    "flows": [{"name": flow_label(i)[0], "context": flow_label(i)[1], "unit": flow_label(i)[2],
                               "amount": float(g[i]), "custom": int(mc.flow_ids[i]) in custom_flow_ids}
                              for i in miss[:limit]]})
    return out


# ----------------------------------------------------------------------------------------------- compile and check
def _scale_unc(unc, f):
    """Uncertainty of an amount multiplied by f > 0 (allocation share): lognormal unchanged, absolute values scaled."""
    t, p1, p2, p3 = unc
    if f == 1.0 or t in (0, 1):
        return unc
    return (t, None if p1 is None else p1 * f, None if p2 is None else p2 * f, None if p3 is None else p3 * f)


def compile(store, db_id):
    """Write the custom data of one database into the library tables, in one transaction.

    Every output of a process becomes one dataset: the reference product keeps the process's dataset id, each
    co-product gets its own (created once, then kept). With co-products, every exchange of the process is
    multiplied by the allocation share of the output. Amounts given as formulas are evaluated with the parameters
    of the database and of the process; a formula that fails or gives a negative amount stops the compilation, and
    nothing is changed."""
    ensure_schema(store)
    db_id = int(db_id)
    procs = [dict(r) for r in store.q("SELECT * FROM custom_items WHERE kind='process' AND db_id=? ORDER BY created", (db_id,))]
    prods = {r["uuid"]: json.loads(r["data"]) | {"name": r["name"]}
             for r in store.q("SELECT uuid, name, data FROM custom_items WHERE kind='product' AND db_id=?", (db_id,))}
    for p in procs:
        p["d"] = json.loads(p["data"])
        p["shares"] = allocation_shares(store, p["d"]) if p["d"].get("coproducts") else {p["d"]["product"]: 1.0}
        p["params"] = parameter_values(store, db_id, p["d"])
    with store.lock:
        c = store.conn
        c.commit()
        try:
            c.execute("BEGIN")
            refs, outs_of = {}, {}
            for p in procs:
                d = p["d"]
                method = (d.get("allocation") or {}).get("method")
                outputs = [(d["product"], d["amount"], True)] + [(cp["product"], cp["amount"], False)
                                                                 for cp in d.get("coproducts") or []]
                cref = dict(d.get("coproduct_refs") or {})
                acts = []
                for puid, amt, main in outputs:
                    prod = prods[puid]
                    production = (-1.0 if d["type"] == "treatment" else 1.0) * amt
                    share = p["shares"][puid]
                    comment = "\n".join(x for x in (
                        d.get("technology"), d.get("comment"),
                        f"Time period: {d['time_period']}" if d.get("time_period") else "",
                        f"Source: {p['source']}" if p.get("source") else "",
                        f"Multi-output process, {method} allocation: {share * 100:.4g} % of the exchanges to "
                        f"{prod['name']}." if len(outputs) > 1 else "") if x)
                    key = p["uuid"] if main else f"{p['uuid']}/{puid}"
                    aid = p["ref_id"] if main else cref.get(puid)
                    if aid and c.execute("SELECT 1 FROM activities WHERE id=?", (aid,)).fetchone():
                        c.execute("UPDATE activities SET key=?, name=?, product=?, location=?, unit=?, production=?, "
                                  "comment=?, product_uuid=? WHERE id=?",
                                  (key, p["name"], prod["name"], d["location"], prod["unit"], production, comment[:3000],
                                   puid, aid))
                    else:
                        aid = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production,comment,"
                                        "product_uuid) VALUES(?,?,?,?,?,?,?,?,?)",
                                        (db_id, key, p["name"], prod["name"], d["location"], prod["unit"], production,
                                         comment[:3000], puid)).lastrowid
                    if main:
                        p["ref_id"] = aid
                        c.execute("UPDATE custom_items SET ref_id=? WHERE uuid=?", (aid, p["uuid"]))
                    else:
                        cref[puid] = aid
                    acts.append((aid, share))
                    refs[key] = aid
                    if main:
                        refs[f"{p['uuid']}/{puid}"] = aid
                # co-products that were removed: their datasets go
                for puid in [k for k in cref if k not in {o[0] for o in outputs[1:]}]:
                    old = cref.pop(puid)
                    for sql in ("DELETE FROM tech WHERE output_id=?", "DELETE FROM bio WHERE activity_id=?",
                                "DELETE FROM unlinked WHERE output_id=?", "DELETE FROM activity_dq WHERE activity_id=?",
                                "DELETE FROM activities WHERE id=?"):
                        c.execute(sql, (old,))
                if cref != (d.get("coproduct_refs") or {}):
                    d["coproduct_refs"] = cref
                    c.execute("UPDATE custom_items SET data=? WHERE uuid=?", (json.dumps(d), p["uuid"]))
                outs_of[p["uuid"]] = acts
                dq = d.get("dq") or {}
                for aid, _ in acts:
                    if len(dq) == 4:
                        c.execute("INSERT OR REPLACE INTO activity_dq VALUES(?,?,?,?,?,?,?,?,?)",
                                  (aid, dq["ter"], dq["ger"], dq["tir"], dq["p"], None, None,
                                   f"{(dq['ter'] + dq['ger'] + dq['tir'] + dq['p']) / 4:.1f}", "custom data entry"))
                    else:
                        c.execute("DELETE FROM activity_dq WHERE activity_id=?", (aid,))
            ids = [aid for acts in outs_of.values() for aid, _ in acts]
            q = ",".join("?" * len(ids))
            if ids:
                c.execute(f"DELETE FROM tech WHERE output_id IN ({q})", ids)
                c.execute(f"DELETE FROM bio WHERE activity_id IN ({q})", ids)
                c.execute(f"DELETE FROM unlinked WHERE db_id=? AND output_id IN ({q})", [db_id] + ids)
            for p in procs:
                for e in c.execute("SELECT * FROM custom_exchanges WHERE process_uuid=?", (p["uuid"],)).fetchall():
                    e = dict(e)
                    if e.get("formula"):
                        try:
                            v = float(fm.evaluate(e["formula"], p["params"]))
                        except fm.FormulaError as err:
                            raise CustomDataError(f"{p['name']}: the formula '{e['formula']}' cannot be evaluated: {err}")
                        if not math.isfinite(v) or v < 0:
                            raise CustomDataError(f"{p['name']}: the formula '{e['formula']}' gives {v:g}; amounts must "
                                                  "be zero or positive (mark credits as avoided products).")
                        fac = e["unit_factor"] if e.get("unit_factor") is not None else 1.0
                        if v != e["amount"]:
                            c.execute("UPDATE custom_exchanges SET amount=?, amount_ref=? WHERE id=?", (v, v * fac, e["id"]))
                        e["amount"], e["amount_ref"] = v, v * fac
                    a = e["amount_ref"]
                    unc = (e["utype"], e["p1"], e["p2"], e["p3"])
                    if e["kind"] == "elementary":
                        fid = c.execute("SELECT id FROM flows WHERE uuid=?", (e["target"],)).fetchone()
                        if fid:
                            for aid, f in outs_of[p["uuid"]]:
                                if f > 0:
                                    c.execute("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                                              (aid, fid[0], a * f, *_scale_unc(unc, f)))
                        continue
                    tgt = str(e["target"])
                    sid = int(tgt) if tgt.isdigit() else refs.get(tgt)
                    srow = c.execute("SELECT production, unit, product, location FROM activities WHERE id=?",
                                     (sid,)).fetchone() if sid else None
                    if not srow:
                        for aid, f in outs_of[p["uuid"]]:
                            c.execute("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,"
                                      "p2,p3,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                      (db_id, aid, "(supplier missing)", e["unit"], e["amount"] * f, "", e["target"],
                                       *_scale_unc(unc, f), "the chosen supplier no longer exists"))
                        continue
                    # sign: an input consumes (A = -amount); an avoided product is a negative input; waste sent to a
                    # treatment dataset (negative reference amount) is entered as the amount treated and stored as a
                    # negative input, so that the treatment runs for that amount
                    sign = (-1.0 if e["avoided"] else 1.0) * (-1.0 if (srow[0] or 1.0) < 0 else 1.0)
                    for aid, f in outs_of[p["uuid"]]:
                        if f <= 0:
                            continue
                        t, p1, p2, p3 = _scale_unc(unc, f)
                        if sign < 0 and t in (3, 4):
                            p1, p2, p3 = ((-p3, -p2, -p1) if t == 3 else (-p2, -p1, None))
                        elif sign < 0 and t == 2:
                            p1 = abs(p1)
                        c.execute("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                                  (aid, sid, sign * a * f, t, p1, p2, p3))
            c.execute("UPDATE databases SET n_activities=(SELECT COUNT(*) FROM activities WHERE db_id=?) WHERE id=?",
                      (db_id, db_id))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        c.execute("INSERT INTO lib.activities_fts(activities_fts) VALUES('rebuild')")
        store._bump_lib()
        c.commit()
    calc.invalidate()


def recompile_all(store):
    """After a library database was removed: inputs from its datasets become unresolved inputs."""
    for d in store.q("SELECT id FROM databases WHERE source=?", (SOURCE,)):
        compile(store, d["id"])


def check(store, db_id):
    """Everything that keeps the custom database from being complete, as a list of findings (level, message)."""
    import staging
    ensure_schema(store)
    db_id = int(db_id)
    out = []
    procs = store.q("SELECT * FROM custom_items WHERE kind='process' AND db_id=?", (db_id,))
    if not procs:
        return {"complete": False, "findings": [{"level": "error", "message": "The database has no process yet."}],
                "processes": 0}
    for k, v in staging.integrity(store, db_id).items():
        out.append({"level": "error", "message": f"{v} {k} not valid."})
    for u in store.q("SELECT a.name, u.unit, u.amount, u.reason FROM unlinked u JOIN activities a ON a.id=u.output_id "
                     "WHERE u.db_id=? AND u.linked_to IS NULL", (db_id,)):
        out.append({"level": "error", "message": f"{u['name']}: an input ({u['amount']:g} {u['unit']}) has no supplier "
                                                 f"({u['reason']})."})
    for p in procs:
        d = json.loads(p["data"])
        n_ex = store.one("SELECT COUNT(*) AS n FROM custom_exchanges WHERE process_uuid=?", (p["uuid"],))["n"]
        if not n_ex:
            out.append({"level": "warning", "message": f"{p['name']}: no inputs and no emissions yet."})
        if not p["source"]:
            out.append({"level": "warning", "message": f"{p['name']}: give the source of the data (provenance)."})
        if len(d.get("dq") or {}) < 4:
            out.append({"level": "info", "message": f"{p['name']}: no data quality rating (TeR, GeR, TiR, P)."})
        for e in store.q("SELECT kind, target, amount, unit, source FROM custom_exchanges WHERE process_uuid=? AND "
                         "(source IS NULL OR source='')", (p["uuid"],)):
            out.append({"level": "info", "message": f"{p['name']}: an exchange of {e['amount']:g} {e['unit']} has no source."})
    # plausibility: mass balance and orders of magnitude (warnings only: they can be right, but are often a unit slip)
    for p in procs:
        d = json.loads(p["data"])
        outs = [(d["product"], d["amount"])] + [(c["product"], c["amount"]) for c in d.get("coproducts") or []]
        out_kg = 0.0
        for puid, amt in outs:
            pr = store.one("SELECT data FROM custom_items WHERE uuid=?", (puid,))
            f = unitconv.factor(json.loads(pr["data"])["unit"], "kg") if pr else None
            if f is None:
                out_kg = None
                break
            out_kg += amt * f
        in_kg, ref_amt = 0.0, abs(d["amount"]) or 1.0
        for e in store.q("SELECT kind, target, amount, unit, amount_ref, avoided FROM custom_exchanges WHERE "
                         "process_uuid=?", (p["uuid"],)):
            f = unitconv.factor(e["unit"], "kg")
            if e["kind"] == "technosphere" and not e["avoided"] and f is not None:
                tgt = str(e["target"])
                sid = int(tgt) if tgt.isdigit() else target_activity(store, tgt)
                sp_ = store.one("SELECT production FROM activities WHERE id=?", (sid,)) if sid else None
                if sp_ and (sp_["production"] or 1) > 0:      # waste sent to treatment is not a material input
                    in_kg += e["amount"] * f
            if e["amount_ref"] and e["amount_ref"] > 1e4 * ref_amt:
                out.append({"level": "warning", "message": f"{p['name']}: a line of {e['amount']:g} {e['unit']} is more "
                                                           f"than 10,000 times the reference amount. Check its unit."})
            elif e["amount_ref"] and 0 < e["amount_ref"] < 1e-9 * ref_amt:
                out.append({"level": "info", "message": f"{p['name']}: a line of {e['amount']:g} {e['unit']} is below a "
                                                        "billionth of the reference amount. Check its unit."})
        if d["type"] != "treatment" and out_kg and in_kg:
            ratio = in_kg / out_kg
            if ratio < 0.5 or ratio > 20:
                out.append({"level": "warning", "message": f"{p['name']}: {in_kg:g} kg of material inputs for {out_kg:g} kg "
                                                           f"of products (ratio {ratio:.2g}). Check the amounts and units, "
                                                           "or note why the mass balance differs."})
    # every process can be calculated: unit demand solved with a small residual
    try:
        calc.invalidate()
        mc = calc.get_mc(store)
        for p in procs:
            j = mc.act_index.get(p["ref_id"])
            if j is None:
                continue
            f = np.zeros(mc.n)
            f[j] = 1.0
            s = mc.solve(f)
            res = float(np.linalg.norm(mc.A @ s - f))
            if not np.isfinite(res) or res > 1e-8:
                out.append({"level": "error", "message": f"{p['name']} cannot be calculated (residual {res:.1e}): check "
                                                         "for a loop that consumes all of its own output."})
    except Exception as e:
        out.append({"level": "error", "message": f"The supply chain cannot be calculated: {e}"})
    # factor decisions for the custom flows used by this database
    used = store.q("SELECT DISTINCT e.target AS uuid, f.name FROM custom_exchanges e JOIN custom_items p ON "
                   "p.uuid=e.process_uuid JOIN custom_items i ON i.uuid=e.target AND i.kind='elementary' JOIN flows f "
                   "ON f.uuid=e.target WHERE p.db_id=? AND e.kind='elementary'", (db_id,))
    all_mids = [r["id"] for r in store.q("SELECT id FROM methods")]
    status = {}
    rows = factor_table(store, all_mids)
    for r in rows if used else []:
        if r["custom_flow"]:
            status.setdefault(r["flow_uuid"], []).append(r["status"])
    libgap = {}
    mine = {r["uuid"] for r in store.q("SELECT DISTINCT e.target AS uuid FROM custom_exchanges e JOIN custom_items p ON "
                                       "p.uuid=e.process_uuid WHERE p.db_id=? AND e.kind='elementary'", (db_id,))}
    for r in rows:
        if not r["custom_flow"] and r["status"] == "missing" and r["flow_uuid"] in mine:
            libgap.setdefault(f"{r['family']} | {r['category']}", []).append(r["flow"])
    for m, fl in libgap.items():
        out.append({"level": "warning", "message": f"Custom method '{m}': {len(fl)} flow(s) of this database have no "
                                                   f"factor and no decision (e.g. {', '.join(fl[:3])}). Give their "
                                                   "factors, record that the category does not apply, or state in the "
                                                   "method that flows without a factor have no effect."})
    for u in used:
        st = status.get(u["uuid"], [])
        miss = st.count("missing") + st.count("review")
        if miss:
            out.append({"level": "warning", "message": f"Custom flow '{u['name']}': no factor and no 'does not apply' "
                                                       f"decision in {miss} of {len(st)} impact categories. Results that "
                                                       "include it are marked incomplete in those categories."})
    errors = sum(1 for x in out if x["level"] == "error")
    return {"complete": errors == 0, "findings": out, "processes": len(procs), "errors": errors,
            "warnings": sum(1 for x in out if x["level"] == "warning")}


# ----------------------------------------------------------------------------------------------- reading
def target_activity(store, target):
    """Dataset id of a custom supplier: 'process uuid' (reference product) or 'process uuid/product uuid'."""
    puid, _, cprod = str(target).partition("/")
    r = store.one("SELECT ref_id, data FROM custom_items WHERE uuid=?", (puid,))
    if not r:
        return None
    d = json.loads(r["data"] or "{}")
    if cprod and cprod != d.get("product"):
        return (d.get("coproduct_refs") or {}).get(cprod)
    return r["ref_id"]


def contents(store, db_id):
    ensure_schema(store)
    db_id = int(db_id)
    items = lambda kind: [dict(r) | {"data": json.loads(r["data"] or "{}")} for r in store.q(
        "SELECT * FROM custom_items WHERE kind=? AND db_id=? ORDER BY name", (kind, db_id))]
    procs = items("process")
    for p in procs:
        ex = []
        for e in store.q("SELECT * FROM custom_exchanges WHERE process_uuid=? ORDER BY kind, id", (p["uuid"],)):
            e = dict(e)
            if e["kind"] == "elementary":
                f = store.one("SELECT name, compartment, subcompartment, unit FROM flows WHERE uuid=?", (e["target"],))
                e["label"] = f"{f['name']} ({f['compartment']}/{f['subcompartment']})" if f else "(flow missing)"
                e["ref_unit"] = f["unit"] if f else ""
            else:
                sid = None
                if str(e["target"]).isdigit():
                    sid = int(e["target"])
                else:
                    sid = target_activity(store, e["target"])
                a = store.one("SELECT a.name, a.key, a.location, a.unit, a.production, d.name AS db FROM activities a JOIN "
                              "databases d ON d.id=a.db_id WHERE a.id=?", (sid,)) if sid else None
                e["label"] = f"{a['name']} [{a['location']}] ({a['db']})" if a else "(supplier missing)"
                if a and str(e["target"]).isdigit():
                    e["supplier_key"] = {"key": a["key"], "database": a["db"]}
                e["ref_unit"] = a["unit"] if a else ""
                e["treatment"] = bool(a and (a["production"] or 1) < 0)
            e["pedigree"] = json.loads(e["pedigree"]) if e["pedigree"] else None
            ex.append(e)
        p["exchanges"] = ex
        try:
            p["shares"] = allocation_shares(store, p["data"]) if p["data"].get("coproducts") else None
        except CustomDataError:
            p["shares"] = None
    flows = elementary_flows(store)
    dbrow = dict(store.one("SELECT * FROM databases WHERE id=?", (db_id,)))
    it = store.one("SELECT author FROM custom_items WHERE kind='database' AND db_id=?", (db_id,))
    dbrow["author"] = it["author"] if it else ""
    dbrow["parameters"] = _db_params(store, db_id)
    for p in procs:
        try:
            p["param_values"] = parameter_values(store, db_id, p["data"])
        except CustomDataError:
            p["param_values"] = {}
    return {"database": dbrow, "products": items("product"),
            "processes": procs, "elementary_flows": flows,
            "methods": [dict(r) | {"unlisted": json.loads(r["data"] or "{}").get("unlisted") or "unknown",
                                   "unlisted_reason": json.loads(r["data"] or "{}").get("unlisted_reason") or "",
                                   "data": None}
                        for r in store.q("SELECT m.*, i.data FROM methods m JOIN custom_items i ON i.ref_id=m.id AND "
                                         "i.kind='method' ORDER BY m.family, m.category")]}


def elementary_flows(store):
    """All custom elementary flows (they belong to the library, not to one database)."""
    ensure_schema(store)
    out = []
    for r in store.q("SELECT i.*, f.id AS flow_id FROM custom_items i LEFT JOIN flows f ON f.uuid=i.uuid "
                     "WHERE i.kind='elementary' ORDER BY i.name"):
        r = dict(r)
        r["data"] = json.loads(r["data"] or "{}")
        out.append(r)
    return out


def export_json(store, db_id):
    """The custom database as one JSON document (identifiers, provenance, exchanges, factors), to move or archive."""
    c = contents(store, db_id)
    uuids = {e["target"] for p in c["processes"] for e in p["exchanges"] if e["kind"] == "elementary"}
    facs = [dict(r) for r in store.q("SELECT c.*, m.family, m.category, m.indicator FROM custom_factors c JOIN methods m "
                                     "ON m.id=c.method_id")] if uuids or c["methods"] else []
    used = set()
    for pr in c["products"]:
        used.add(unitconv.norm(pr["data"]["unit"]))
    for p in c["processes"]:
        used |= {unitconv.norm(e["unit"]) for e in p["exchanges"]}
    used |= {unitconv.norm(f["data"]["unit"]) for f in c["elementary_flows"]}
    ulist = [dict(u) for u in store.q("SELECT name, dimension, factor, description, source FROM custom_units")
             if unitconv.norm(u["name"]) in used]
    return {"format": "cyclia-custom-data", "format_version": 2, "exported": _now(), **c, "units": ulist,
            "parameters": _db_params(store, db_id),
            "factors": [f for f in facs if f["flow_uuid"] in uuids or f["method_id"] in {m["id"] for m in c["methods"]}]}


def import_json(store, doc, name=None):
    """Recreate a custom database from export_json(). Identifiers are kept; library datasets used as suppliers must
    exist with the same key in the library (they are found by dataset key and database name)."""
    if (doc or {}).get("format") != "cyclia-custom-data":
        raise CustomDataError("This is not a Cyclia custom data file.")
    ensure_schema(store)
    d = doc["database"]
    db = create_database(store, name or d["name"], d.get("note") or "", version=d.get("version") or "1",
                         licence=d.get("licence") or "", geography=d.get("geography") or "",
                         reference_period=d.get("reference_period") or "")
    for u in doc.get("units", []):
        have = store.one("SELECT dimension, factor FROM custom_units WHERE name=?", (u["name"],))
        if not have and not unitconv.builtin(u["name"]):
            save_unit(store, {**u, "dimension": u["dimension"]})
        elif have and (have["dimension"] != u["dimension"] or abs(have["factor"] - u["factor"]) > 1e-12 * u["factor"]):
            raise CustomDataError(f"The unit '{u['name']}' is defined differently in this library "
                                  f"({have['factor']:g} instead of {u['factor']:g}). Rename one of them first.")
    if doc.get("parameters"):
        set_database_parameters(store, db, doc["parameters"])
    for m in doc.get("methods", []):
        if not store.method_by_key(m["family"], m["category"], m["indicator"]):
            create_method(store, m["family"], m["category"], m["indicator"], m["unit"], m.get("note") or "imported",
                          unlisted=m.get("unlisted") or "unknown", unlisted_reason=m.get("unlisted_reason") or "")
    for f in doc.get("elementary_flows", []):
        if not store.one("SELECT 1 AS x FROM flows WHERE uuid=?", (f["uuid"],)):
            save_elementary(store, {**f["data"], "uuid": f["uuid"], "name": f["name"], "source": f.get("source"),
                                    "author": f.get("author")})
    # products and processes keep their identifiers, unless the library already has them (a copy of a database
    # that is still installed): then they get new ones
    remap = {}
    for it in doc.get("products", []) + doc.get("processes", []):
        remap[it["uuid"]] = it["uuid"] if not store.one("SELECT 1 AS x FROM custom_items WHERE uuid=?",
                                                        (it["uuid"],)) else _new_uuid()
    for pr in doc.get("products", []):
        save_product(store, db, {**pr["data"], "uuid": remap[pr["uuid"]], "name": pr["name"],
                                 "source": pr.get("source"), "author": pr.get("author")})
    procs = doc.get("processes", [])
    for p in procs:
        pd = p["data"]
        al = pd.get("allocation") or {}
        save_process(store, db, {**pd, "product": remap[pd["product"]], "uuid": remap[p["uuid"]],
                                 "coproducts": [{**c, "product": remap[c["product"]]} for c in pd.get("coproducts") or []],
                                 "allocation": {**al, "values": {remap.get(k, k): v for k, v in (al.get("values") or {}).items()}},
                                 "coproduct_refs": {}, "name": p["name"], "source": p.get("source"),
                                 "author": p.get("author")})
    re_t = lambda t: "/".join(remap.get(x, x) for x in str(t).split("/"))
    for p in procs:
        for e in p["exchanges"]:
            sup = re_t(e["target"])
            if e["kind"] == "technosphere" and str(sup).isdigit():
                lib = e.get("supplier_key")
                a = store.one("SELECT a.id FROM activities a JOIN databases d ON d.id=a.db_id WHERE a.key=? AND d.name=?",
                              (lib["key"], lib["database"])) if lib else None
                if not a:
                    raise CustomDataError(f"{p['name']} uses the library dataset '{e.get('label')}', which is not "
                                          "installed. Install that database first.")
                sup = str(a["id"])
            ped = e.get("pedigree")
            save_exchange(store, remap[p["uuid"]], {"kind": e["kind"], "supplier": sup, "flow": sup, "amount": e["amount"],
                                                    "formula": e.get("formula") or "", "unit": e["unit"],
                                                    "avoided": e["avoided"], "source": e.get("source"),
                                                    "comment": e.get("comment"), "author": e.get("author") or "",
                                                    **_unc_back(e, ped)})
    for f in doc.get("factors", []):
        m = store.method_by_key(f["family"], f["category"], f["indicator"])
        if m:
            save_factor(store, m["id"], f["flow_uuid"], f["status"], f.get("value_entered"), f.get("unit_entered"),
                        f.get("source") or "", f.get("comment") or "")
    return db


def _unc_back(e, ped):
    lab = e.get("uncertainty") or "none"
    if lab == "pedigree":
        return {"uncertainty": "pedigree", "pedigree": ped}
    fac = e.get("unit_factor") or (e["amount_ref"] / e["amount"] if e["amount"] else 1.0)
    if lab == "lognormal":
        return {"uncertainty": "lognormal", "gsd": math.exp(e["p1"])}
    if lab == "normal":
        return {"uncertainty": "normal", "sd": e["p1"] / fac}
    if lab == "triangular":
        return {"uncertainty": "triangular", "min": e["p1"] / fac, "mode": e["p2"] / fac, "max": e["p3"] / fac}
    if lab == "uniform":
        return {"uncertainty": "uniform", "min": e["p1"] / fac, "max": e["p2"] / fac}
    return {"uncertainty": "none"}


# ----------------------------------------------------------------------------------------------- worked example
EXAMPLE_NAME = "Example: bread from a small bakery (illustrative values)"


def example(store, author="Cyclia example"):
    """A small worked example to learn from: bread made with flour and electricity, with its waste sent to landfill.
    The values are illustrative and say so; the factors are IPCC AR6 GWP100 values (CO2 fossil 1, CH4 non-fossil
    27.0). Returns {"db_id", "process": uuid of the bread process, "method_id", "expected": result per kg}."""
    ensure_schema(store)
    if store.one("SELECT id FROM databases WHERE name=?", (EXAMPLE_NAME,)):
        raise CustomDataError("The example is already in the library. Delete it in step 1 to create it again.")
    note = "Illustrative value for learning, not for publication."
    db = create_database(store, EXAMPLE_NAME, "A worked example of custom data entry. " + note, author=author,
                         geography="GLO", reference_period="2026")
    bread = save_product(store, db, {"name": "bread", "unit": "kg", "category": "food", "source": note})
    flour = save_product(store, db, {"name": "wheat flour", "unit": "kg", "category": "food", "source": note})
    elec = save_product(store, db, {"name": "electricity", "unit": "kWh", "category": "energy", "source": note})
    waste = save_product(store, db, {"name": "bread waste", "unit": "kg", "category": "waste", "source": note})

    def flow(name, comp, sub, unit, cas):
        from canon import canon as _canon
        r = store.one("SELECT uuid FROM flows WHERE c_name=? AND c_comp=? AND c_sub=?", _canon(name, comp, sub))
        if r:
            return r["uuid"]
        return save_elementary(store, {"name": name, "compartment": comp, "subcompartment": sub, "unit": unit,
                                       "cas": cas, "source": "ecoinvent elementary flow list (name and context)"})
    co2 = flow("Carbon dioxide, fossil", "air", "unspecified", "kg", "124-38-9")
    ch4 = flow("Methane, non-fossil", "air", "unspecified", "kg", "74-82-8")
    dust = save_elementary(store, {"name": "Flour dust (example)", "compartment": "air",
                                   "subcompartment": "urban air close to ground", "unit": "kg",
                                   "source": note}) if not store.one(
        "SELECT uuid FROM custom_items WHERE kind='elementary' AND name='Flour dust (example)'") else store.one(
        "SELECT uuid FROM custom_items WHERE kind='elementary' AND name='Flour dust (example)'")["uuid"]
    dq = {"ter": 3, "ger": 3, "tir": 2, "p": 4}
    p_flour = save_process(store, db, {"name": "wheat flour, from the mill", "product": flour, "amount": 1,
                                       "location": "GLO", "source": note, "data_type": "estimate", "dq": dq,
                                       "technology": "Milling of wheat, cultivation included"})
    save_exchange(store, p_flour, {"kind": "elementary", "flow": co2, "amount": 0.4, "unit": "kg", "source": note,
                                   "uncertainty": "pedigree", "pedigree": [4, 3, 3, 3, 3], "author": author})
    p_el = save_process(store, db, {"name": "electricity, local grid", "product": elec, "amount": 1, "location": "GLO",
                                    "source": note, "data_type": "estimate", "dq": dq})
    save_exchange(store, p_el, {"kind": "elementary", "flow": co2, "amount": 0.5, "unit": "kg", "source": note,
                                "uncertainty": "lognormal", "gsd": 1.2, "author": author})
    p_lf = save_process(store, db, {"name": "landfill of bread waste", "product": waste, "amount": 1,
                                    "type": "treatment", "location": "GLO", "source": note, "data_type": "estimate",
                                    "dq": dq})
    save_exchange(store, p_lf, {"kind": "elementary", "flow": ch4, "amount": 20, "unit": "g", "source": note,
                            "uncertainty": "triangular", "min": 10, "mode": 20, "max": 40, "author": author})
    p_bread = save_process(store, db, {"name": "bread baking", "product": bread, "amount": 1, "location": "GLO",
                                       "source": note, "data_type": "estimate", "dq": dq,
                                       "technology": "Small bakery, electric oven", "time_period": "2026"})
    for d in ({"kind": "technosphere", "supplier": p_flour, "amount": 650, "unit": "g", "uncertainty": "normal",
               "sd": 20},
              {"kind": "technosphere", "supplier": p_el, "amount": 1.08, "unit": "MJ"},
              {"kind": "technosphere", "supplier": p_lf, "amount": 0.05, "unit": "kg"},
              {"kind": "elementary", "flow": dust, "amount": 1, "unit": "g"}):
        save_exchange(store, p_bread, {**d, "source": note, "author": author})
    fam = "Example: climate change"
    m = store.method_by_key(fam, "climate change", "GWP100")
    mid = m["id"] if m else create_method(
        store, fam, "climate change", "GWP100", "kg CO2-eq",
        "IPCC AR6 WG1 (2021), chapter 7, table 7.15: GWP100 of CO2 = 1, of non-fossil CH4 = 27.0", author,
        unlisted="unknown")
    src = "IPCC AR6 WG1 (2021), table 7.15"
    save_factor(store, mid, co2, "value", 1.0, "kg", source=src, author=author)
    save_factor(store, mid, ch4, "value", 27.0, "kg", source=src, author=author)
    save_factor(store, mid, dust, "not_applicable", comment="Flour dust is not a greenhouse gas.", author=author)
    # 0.65 x 0.4 + 0.3 x 0.5 + 0.05 x 0.02 x 27 = 0.26 + 0.15 + 0.027
    return {"db_id": db, "process": p_bread, "method_id": mid, "expected": 0.437}
