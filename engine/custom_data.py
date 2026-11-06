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
  cannot go into an EPD until every factor is decided.

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
    return uid


def _product_used(store, uid):
    return bool(store.one("SELECT 1 AS x FROM custom_items WHERE kind='process' AND json_extract(data,'$.product')=?",
                          (uid,)))


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
    _own(store, uid, "elementary", None)
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
            store.conn.execute("UPDATE flows SET name=?, compartment=?, subcompartment=?, unit=?, cas=?, c_name=?, c_comp=?, "
                               "c_sub=? WHERE uuid=?", (name, comp, sub, unit, cas, *cn, uid))
            fid = old[0]
        else:
            fid = store.add_flow(uid, name, comp, sub, unit, cas)
        store.conn.commit()
    _save_item(store, "elementary", uid, None, fid, name, data, _text(d.get("source"), "Source", False, 1000),
               _text(d.get("author"), "Author", False, 200))
    if old:
        _refresh_factors(store)
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
    data = {"product": prod["uuid"], "amount": amount, "type": kind, "location": loc,
            "technology": _text(d.get("technology"), "Technology", False, 2000),
            "time_period": _text(d.get("time_period"), "Time period", False, 100),
            "comment": _text(d.get("comment"), "Comment", False, 3000), "dq": dq,
            "data_type": d.get("data_type") if d.get("data_type") in ("primary", "secondary", "estimate") else ""}
    _save_item(store, "process", uid, int(db_id), None, name, data, _text(d.get("source"), "Source", False, 1000),
               _text(d.get("author"), "Author", False, 200))
    compile(store, int(db_id))
    return uid


def _supplier(store, target):
    """(activity id, unit, production, label) of a supplier: a custom process UUID or a library dataset id."""
    if isinstance(target, str) and not target.isdigit():
        p = _item(store, target, "process")
        if not p["ref_id"]:
            raise CustomDataError("The supplier process has not been saved yet.")
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
    kind = d.get("kind")
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
    row = (process_uuid, kind, target, amount, unit, amount_ref, int(avoided), utype, p1, p2, p3,
           json.dumps(ped) if ped else None, ulabel, _text(d.get("source"), "Source", False, 1000),
           _text(d.get("comment"), "Comment", False, 2000), _now())
    with store.lock:
        if d.get("id"):
            n = store.conn.execute("UPDATE custom_exchanges SET process_uuid=?, kind=?, target=?, amount=?, unit=?, "
                                   "amount_ref=?, avoided=?, utype=?, p1=?, p2=?, p3=?, pedigree=?, uncertainty=?, "
                                   "source=?, comment=?, modified=? WHERE id=? AND process_uuid=?",
                                   row + (int(d["id"]), process_uuid)).rowcount
            if not n:
                raise CustomDataError("The exchange was not found.")
            eid = int(d["id"])
        else:
            eid = store.conn.execute("INSERT INTO custom_exchanges(process_uuid,kind,target,amount,unit,amount_ref,avoided,"
                                     "utype,p1,p2,p3,pedigree,uncertainty,source,comment,modified) "
                                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row).lastrowid
        store.conn.commit()
    compile(store, p["db_id"])
    return eid


def delete_exchange(store, process_uuid, exchange_id):
    p = _item(store, process_uuid, "process")
    store.x("DELETE FROM custom_exchanges WHERE id=? AND process_uuid=?", (int(exchange_id), process_uuid))
    compile(store, p["db_id"])


def delete_item(store, uid):
    """Delete a product, elementary flow or process that nothing uses."""
    it = _item(store, uid)
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
        if store.one("SELECT 1 AS x FROM custom_exchanges WHERE kind='technosphere' AND target=?", (uid,)):
            raise CustomDataError("Another process uses this process as a supplier. Change that input first.")
        if it["ref_id"] and store.one("SELECT 1 AS x FROM tech WHERE input_id=? AND output_id NOT IN "
                                      "(SELECT id FROM activities WHERE db_id=?)", (it["ref_id"], it["db_id"])):
            raise CustomDataError("A dataset of another database uses this process.")
        if it["ref_id"] and store.one("SELECT 1 AS x FROM main.model_inputs WHERE kind='activity' AND ref_id=?",
                                      (it["ref_id"],)):
            raise CustomDataError("A model of this project uses this process. Remove that line first.")
        with store.lock:
            store.conn.execute("DELETE FROM custom_exchanges WHERE process_uuid=?", (uid,))
            store.conn.execute("DELETE FROM custom_items WHERE uuid=?", (uid,))
            if it["ref_id"]:
                for sql in ("DELETE FROM tech WHERE output_id=?", "DELETE FROM bio WHERE activity_id=?",
                            "DELETE FROM unlinked WHERE output_id=?", "DELETE FROM activity_dq WHERE activity_id=?",
                            "DELETE FROM activities WHERE id=?"):
                    store.conn.execute(sql, (it["ref_id"],))
            store.conn.commit()
        compile(store, it["db_id"])
        return
    raise CustomDataError("This item cannot be deleted here.")


# ----------------------------------------------------------------------------------------------- factors and methods
def create_method(store, family, category, indicator, unit, source, author=""):
    ensure_schema(store)
    family = _text(family, "The method name", maxlen=200)
    category = _text(category, "The impact category", maxlen=200)
    indicator = _text(indicator or category, "The indicator", maxlen=200)
    unit = _text(unit, "The indicator unit (for example kg CO2-eq)", maxlen=60)
    src = _text(source, "The source of the method (publication or standard)", maxlen=1000)
    if store.method_by_key(family, category, indicator):
        raise CustomDataError("This method, category and indicator already exist.")
    mid = store.get_or_create_method(family, category, indicator, unit, METHOD_SOURCE, note=src)
    _save_item(store, "method", _new_uuid(), None, mid, f"{family} | {category}", {"unit": unit}, src, author)
    return mid


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
        store.conn.execute("INSERT OR REPLACE INTO custom_factors VALUES(?,?,?,?,?,?,?,?,?,?)",
                           row + (_text(author, "Author", False, 200), _now()))
        store.conn.commit()
    _refresh_factors(store, [int(method_id)])


def delete_factor(store, method_id, flow_uuid):
    store.x("DELETE FROM custom_factors WHERE method_id=? AND flow_uuid=?", (int(method_id), flow_uuid))
    _refresh_factors(store, [int(method_id)])


def _refresh_factors(store, method_ids=None):
    """Write custom factors into cf_raw (matched by flow UUID) and rematch the affected categories. Factors of
    installed methods for library flows are not touched."""
    from importers import lcia
    from canon import canon as _canon
    rows = store.q("SELECT c.method_id, c.flow_uuid, c.value, f.name, f.compartment, f.subcompartment FROM custom_factors c "
                   "JOIN flows f ON f.uuid=c.flow_uuid WHERE c.status='value'")
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
    """Status of every custom flow in the given categories: value, not_applicable or missing."""
    ensure_schema(store)
    flows = store.q("SELECT f.id, f.uuid, f.name, f.compartment, f.subcompartment, f.unit FROM custom_items i "
                    "JOIN flows f ON f.uuid=i.uuid WHERE i.kind='elementary' ORDER BY f.name")
    out = []
    for mid in method_ids:
        m = store.one("SELECT id, family, category, indicator, unit FROM methods WHERE id=?", (int(mid),))
        if not m:
            continue
        dec = {r["flow_uuid"]: dict(r) for r in store.q("SELECT * FROM custom_factors WHERE method_id=?", (int(mid),))}
        matched = {r["flow_id"]: r["value"] for r in store.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (int(mid),))}
        for f in flows:
            d = dec.get(f["uuid"])
            st = d["status"] if d else ("value" if f["id"] in matched else "missing")
            out.append({"method_id": m["id"], "family": m["family"], "category": m["category"], "indicator": m["indicator"],
                        "method_unit": m["unit"], "flow_uuid": f["uuid"], "flow": f["name"],
                        "compartment": f"{f['compartment']}/{f['subcompartment']}", "flow_unit": f["unit"], "status": st,
                        "value": d["value"] if d and d["status"] == "value" else matched.get(f["id"]),
                        "value_entered": d.get("value_entered") if d else None, "unit_entered": d.get("unit_entered") if d else None,
                        "source": d.get("source") if d else ("installed method" if f["id"] in matched else ""),
                        "comment": d.get("comment") if d else ""})
    return out


def factor_gaps(store, mc, M, g, flow_label, limit=25):
    """Per category: custom flows of the inventory g whose factor is unknown, i.e. that have no factor (given here or
    matched from the method) and no 'does not apply' decision. Installed methods define which library flows they
    characterise; a new flow is unknown to them, so its factor is not taken as zero. Returns a list aligned with M.ids
    of None or {"n", "custom_method", "flows"}."""
    try:
        custom_flow_ids = {r["ref_id"] for r in store.q("SELECT ref_id FROM custom_items WHERE kind='elementary'")}
        cmeth = custom_methods(store)
        na = {}
        for r in store.q("SELECT c.method_id, f.id FROM custom_factors c JOIN flows f ON f.uuid=c.flow_uuid "
                         "WHERE c.status='not_applicable'"):
            na.setdefault(r["method_id"], set()).add(r["id"])
    except Exception:   # library without the custom tables
        return [None] * len(M.ids)
    if not custom_flow_ids:
        return [None] * len(M.ids)
    nz = np.where(np.abs(g) > 1e-15 * (np.abs(g).max() or 1))[0] if len(g) else []
    Cd = getattr(M, "Cd", M.C)
    out = []
    for k, mid in enumerate(M.ids):
        miss = []
        for i in nz:
            fid = int(mc.flow_ids[i])
            if M.C[k, i] != 0 or Cd[k, i] != 0 or fid in na.get(mid, ()):
                continue
            if fid in custom_flow_ids:
                miss.append(i)
        if not miss:
            out.append(None)
            continue
        miss.sort(key=lambda i: -abs(g[i]))
        out.append({"n": len(miss), "custom_method": mid in cmeth,
                    "flows": [{"name": flow_label(i)[0], "context": flow_label(i)[1], "unit": flow_label(i)[2],
                               "amount": float(g[i])}
                              for i in miss[:limit]]})
    return out


# ----------------------------------------------------------------------------------------------- compile and check
def compile(store, db_id):
    """Write the custom data of one database into the library tables, in one transaction."""
    ensure_schema(store)
    db_id = int(db_id)
    procs = [dict(r) for r in store.q("SELECT * FROM custom_items WHERE kind='process' AND db_id=? ORDER BY created", (db_id,))]
    prods = {r["uuid"]: json.loads(r["data"]) | {"name": r["name"]}
             for r in store.q("SELECT uuid, name, data FROM custom_items WHERE kind='product' AND db_id=?", (db_id,))}
    with store.lock:
        c = store.conn
        c.commit()
        try:
            c.execute("BEGIN")
            # datasets: created once, then updated in place (stable ids)
            for p in procs:
                d = json.loads(p["data"])
                prod = prods[d["product"]]
                production = (-1.0 if d["type"] == "treatment" else 1.0) * d["amount"]
                comment = "\n".join(x for x in (d.get("technology"), d.get("comment"),
                                                f"Time period: {d['time_period']}" if d.get("time_period") else "",
                                                f"Source: {p['source']}" if p.get("source") else "") if x)
                if p["ref_id"] and c.execute("SELECT 1 FROM activities WHERE id=?", (p["ref_id"],)).fetchone():
                    c.execute("UPDATE activities SET key=?, name=?, product=?, location=?, unit=?, production=?, comment=?, "
                              "product_uuid=? WHERE id=?", (p["uuid"], p["name"], prod["name"], d["location"], prod["unit"],
                                                            production, comment[:3000], d["product"], p["ref_id"]))
                else:
                    p["ref_id"] = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production,comment,"
                                            "product_uuid) VALUES(?,?,?,?,?,?,?,?,?)",
                                            (db_id, p["uuid"], p["name"], prod["name"], d["location"], prod["unit"],
                                             production, comment[:3000], d["product"])).lastrowid
                    c.execute("UPDATE custom_items SET ref_id=? WHERE uuid=?", (p["ref_id"], p["uuid"]))
                dq = d.get("dq") or {}
                if len(dq) == 4:
                    c.execute("INSERT OR REPLACE INTO activity_dq VALUES(?,?,?,?,?,?,?,?,?)",
                              (p["ref_id"], dq["ter"], dq["ger"], dq["tir"], dq["p"], None, None,
                               f"{(dq['ter'] + dq['ger'] + dq['tir'] + dq['p']) / 4:.1f}", "custom data entry"))
                else:
                    c.execute("DELETE FROM activity_dq WHERE activity_id=?", (p["ref_id"],))
            ids = [p["ref_id"] for p in procs]
            refs = {p["uuid"]: p["ref_id"] for p in procs}
            q = ",".join("?" * len(ids))
            if ids:
                c.execute(f"DELETE FROM tech WHERE output_id IN ({q})", ids)
                c.execute(f"DELETE FROM bio WHERE activity_id IN ({q})", ids)
                c.execute(f"DELETE FROM unlinked WHERE db_id=? AND output_id IN ({q})", [db_id] + ids)
            for p in procs:
                for e in c.execute("SELECT * FROM custom_exchanges WHERE process_uuid=?", (p["uuid"],)).fetchall():
                    e = dict(e)
                    a = e["amount_ref"]
                    unc = (e["utype"], e["p1"], e["p2"], e["p3"])
                    if e["kind"] == "elementary":
                        fid = c.execute("SELECT id FROM flows WHERE uuid=?", (e["target"],)).fetchone()
                        if fid:
                            c.execute("INSERT INTO bio(activity_id,flow_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                                      (p["ref_id"], fid[0], a, *unc))
                        continue
                    sid = refs.get(e["target"]) if not str(e["target"]).isdigit() else int(e["target"])
                    srow = c.execute("SELECT production, unit, product, location FROM activities WHERE id=?",
                                     (sid,)).fetchone() if sid else None
                    if not srow:
                        c.execute("INSERT INTO unlinked(db_id,output_id,product,unit,amount,location,link_key,utype,p1,p2,p3,"
                                  "reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (db_id, p["ref_id"], "(supplier missing)", e["unit"], e["amount"], "", e["target"], *unc,
                                   "the chosen supplier no longer exists"))
                        continue
                    # sign: an input consumes (A = -amount); an avoided product is a negative input; waste sent to a
                    # treatment dataset (negative reference amount) is entered as the amount treated and stored as a
                    # negative input, so that the treatment runs for that amount
                    sign = (-1.0 if e["avoided"] else 1.0) * (-1.0 if (srow[0] or 1.0) < 0 else 1.0)
                    t, p1, p2, p3 = unc
                    if sign < 0 and t in (3, 4):
                        p1, p2, p3 = ((-p3, -p2, -p1) if t == 3 else (-p2, -p1, None))
                    elif sign < 0 and t == 2:
                        p1 = abs(p1)
                    c.execute("INSERT INTO tech(output_id,input_id,amount,utype,p1,p2,p3) VALUES(?,?,?,?,?,?,?)",
                              (p["ref_id"], sid, sign * a, t, p1, p2, p3))
            n = len(procs)
            c.execute("UPDATE databases SET n_activities=? WHERE id=?", (n, db_id))
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
    for r in factor_table(store, all_mids) if used else []:
        status.setdefault(r["flow_uuid"], []).append(r["status"])
    for u in used:
        st = status.get(u["uuid"], [])
        miss = st.count("missing")
        if miss:
            out.append({"level": "warning", "message": f"Custom flow '{u['name']}': no factor and no 'does not apply' "
                                                       f"decision in {miss} of {len(st)} impact categories. Results that "
                                                       "include it are marked incomplete in those categories."})
    errors = sum(1 for x in out if x["level"] == "error")
    return {"complete": errors == 0, "findings": out, "processes": len(procs), "errors": errors,
            "warnings": sum(1 for x in out if x["level"] == "warning")}


# ----------------------------------------------------------------------------------------------- reading
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
                    r = store.one("SELECT ref_id FROM custom_items WHERE uuid=?", (e["target"],))
                    sid = r["ref_id"] if r else None
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
    flows = elementary_flows(store)
    return {"database": dict(store.one("SELECT * FROM databases WHERE id=?", (db_id,))), "products": items("product"),
            "processes": procs, "elementary_flows": flows,
            "methods": [dict(r) for r in store.q("SELECT m.* FROM methods m JOIN custom_items i ON i.ref_id=m.id AND "
                                                 "i.kind='method'")]}


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
    return {"format": "cyclia-custom-data", "format_version": 1, "exported": _now(), **c,
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
    for m in doc.get("methods", []):
        if not store.method_by_key(m["family"], m["category"], m["indicator"]):
            create_method(store, m["family"], m["category"], m["indicator"], m["unit"], m.get("note") or "imported")
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
        save_process(store, db, {**p["data"], "product": remap[p["data"]["product"]], "uuid": remap[p["uuid"]],
                                 "name": p["name"], "source": p.get("source"), "author": p.get("author")})
    for p in procs:
        for e in p["exchanges"]:
            sup = remap.get(e["target"], e["target"])
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
                                             "unit": e["unit"], "avoided": e["avoided"], "source": e.get("source"),
                                             "comment": e.get("comment"), **_unc_back(e, ped)})
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
    fac = e["amount_ref"] / e["amount"] if e["amount"] else 1.0
    if lab == "lognormal":
        return {"uncertainty": "lognormal", "gsd": math.exp(e["p1"])}
    if lab == "normal":
        return {"uncertainty": "normal", "sd": e["p1"] / fac}
    if lab == "triangular":
        return {"uncertainty": "triangular", "min": e["p1"] / fac, "mode": e["p2"] / fac, "max": e["p3"] / fac}
    if lab == "uniform":
        return {"uncertainty": "uniform", "min": e["p1"] / fac, "max": e["p2"] / fac}
    return {"uncertainty": "none"}
