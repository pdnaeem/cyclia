"""Collaborative critical review, Cyclia 1.8.0.

A review in the sense of ISO 14044 6 and ISO/TS 14071: the reviewer raises comments on the study (on the whole
model, on one inventory line or on one item of the ISO 14044 checklist), each with a severity; the practitioner
answers; the reviewer resolves or keeps them open. Reviewer and practitioner work on their own computers: the
practitioner sends the project (Projects > Export), the reviewer sends back a review file, and each side merges
the other's file. Comments carry a unique identifier, so merging never duplicates them; for a comment changed on
both sides the later change is kept and the earlier one stays in its history.

The review can be closed only when no critical or major comment is open or answered without being resolved. The
closing statement records a fingerprint of the model; when the model changes afterwards, the review is shown as
referring to an earlier state of the model.
"""
import datetime
import hashlib
import json
import uuid

SEVERITY = ("critical", "major", "minor", "editorial")
STATUS = ("open", "answered", "resolved", "withdrawn")
ROLES = ("reviewer", "practitioner")
BLOCKING = ("critical", "major")
FORMAT = "cyclia-review"

SCHEMA = """
CREATE TABLE IF NOT EXISTS main.review_comments (uid TEXT PRIMARY KEY, model_id INTEGER, parent TEXT, target TEXT,
    target_label TEXT, author TEXT, role TEXT, severity TEXT, status TEXT, text TEXT, created TEXT, modified TEXT,
    history TEXT DEFAULT '[]');
CREATE INDEX IF NOT EXISTS main.idx_review_model ON review_comments(model_id);
"""


class ReviewError(ValueError):
    pass


def ensure(store):
    with store.lock:
        store.conn.executescript(SCHEMA)
        store.conn.commit()


def _now():
    # microseconds: the later of two changes made within one second must still be recognised when merging
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def _txt(v, what, required=True, n=4000):
    v = (str(v) if v is not None else "").strip()
    if required and not v:
        raise ReviewError(f"{what} is required.")
    return v[:n]


def fingerprint(store, model_id):
    """Hash of what determines the results of the model: its inputs, parameters and scope (without the review
    notes). Equal fingerprints mean reviewer and practitioner look at the same model."""
    m = store.one("SELECT * FROM main.models WHERE id=?", (int(model_id),))
    if not m:
        raise ReviewError("Model not found.")
    sc = json.loads(m["scope"] or "{}")
    for k in ("review_items", "review_closure", "review", "review_status"):
        sc.pop(k, None)
    keep = ("kind", "ref_db", "ref_key", "amount", "formula", "stage", "avoided", "input_amount", "input_unit",
            "pedigree", "year", "fixed")
    inputs = [{k: r[k] for k in keep if k in r.keys()}
              for r in store.q("SELECT * FROM main.model_inputs WHERE model_id=? ORDER BY position, id", (int(model_id),))]
    params = [{k: r[k] for k in ("name", "value", "formula", "utype", "p1", "p2", "p3")}
              for r in store.q("SELECT * FROM main.parameters WHERE model_id=? ORDER BY name", (int(model_id),))]
    doc = {"name": m["name"], "amount": m["amount"], "unit": m["unit"], "scope": sc, "inputs": inputs, "params": params}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _target(store, model_id, target):
    target = (target or "general").strip()
    if target == "general":
        return target, "The study as a whole"
    kind, _, ref = target.partition(":")
    if kind == "line":
        r = store.one("SELECT i.id, i.label, i.ref_key, a.name FROM main.model_inputs i LEFT JOIN activities a ON "
                      "i.kind='activity' AND a.id=i.ref_id WHERE i.id=? AND i.model_id=?", (int(ref), int(model_id)))
        if not r:
            raise ReviewError("That inventory line is not in this model.")
        return target, "Line: " + (r["label"] or r["name"] or r["ref_key"] or f"#{ref}")
    if kind == "item":
        import standards
        for key, clause, text in standards.REVIEW_ITEMS:
            if key == ref:
                return target, f"ISO 14044 {clause}: {text}"
        raise ReviewError("Unknown checklist item.")
    raise ReviewError("A comment is on the study, on a line or on a checklist item.")


def add(store, model_id, d):
    ensure(store)
    if not store.one("SELECT id FROM main.models WHERE id=?", (int(model_id),)):
        raise ReviewError("Model not found.")
    role = d.get("role") or "reviewer"
    if role not in ROLES:
        raise ReviewError("The role is reviewer or practitioner.")
    text = _txt(d.get("text"), "The comment")
    author = _txt(d.get("author"), "Your name (Settings)", n=200)
    now = _now()
    parent = d.get("parent") or None
    if parent:
        p = store.one("SELECT * FROM main.review_comments WHERE uid=? AND model_id=?", (parent, int(model_id)))
        if not p or p["parent"]:
            raise ReviewError("Reply to a comment of this model.")
        target, label, severity, status = p["target"], p["target_label"], "", ""
    else:
        if role != "reviewer":
            raise ReviewError("Comments are raised by the reviewer; the practitioner answers them.")
        severity = d.get("severity") or ""
        if severity not in SEVERITY:
            raise ReviewError("Choose a severity: " + ", ".join(SEVERITY) + ".")
        target, label = _target(store, model_id, d.get("target"))
        status = "open"
    uid = str(uuid.uuid4())
    store.x("INSERT INTO main.review_comments(uid, model_id, parent, target, target_label, author, role, severity, "
            "status, text, created, modified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, int(model_id), parent, target, label, author, role, severity, status, text, now, now))
    if parent and role == "practitioner" and p["status"] == "open":
        _status(store, parent, "answered", author, role, auto=True)
    return uid


def _status(store, uid, status, author, role, auto=False):
    c = store.one("SELECT * FROM main.review_comments WHERE uid=?", (uid,))
    hist = json.loads(c["history"] or "[]")
    hist.append({"time": _now(), "author": author, "role": role, "status": c["status"], "to": status,
                 "auto": auto})
    store.x("UPDATE main.review_comments SET status=?, modified=?, history=? WHERE uid=?",
            (status, _now(), json.dumps(hist), uid))


def set_status(store, uid, status, author, role):
    ensure(store)
    c = store.one("SELECT * FROM main.review_comments WHERE uid=?", (uid,))
    if not c or c["parent"]:
        raise ReviewError("Comment not found.")
    if status not in STATUS:
        raise ReviewError("Unknown status.")
    author = _txt(author, "Your name (Settings)", n=200)
    if status in ("resolved", "withdrawn") and role != "reviewer":
        raise ReviewError("Only the reviewer resolves or withdraws a comment; answer it instead.")
    if role not in ROLES:
        raise ReviewError("The role is reviewer or practitioner.")
    _status(store, uid, status, author, role)


def threads(store, model_id):
    ensure(store)
    rows = [dict(r) for r in store.q("SELECT * FROM main.review_comments WHERE model_id=? ORDER BY created",
                                     (int(model_id),))]
    tops = [r for r in rows if not r["parent"]]
    for t in tops:
        t["replies"] = [r for r in rows if r["parent"] == t["uid"]]
        t["history"] = json.loads(t["history"] or "[]")
    order = {s: i for i, s in enumerate(STATUS)}
    sev = {s: i for i, s in enumerate(SEVERITY)}
    tops.sort(key=lambda t: (order.get(t["status"], 9), sev.get(t["severity"], 9), t["created"]))
    return tops


def summary(store, model_id):
    ts = threads(store, model_id)
    m = store.model(int(model_id))
    closure = (m["scope"] or {}).get("review_closure") if m else None
    fp = fingerprint(store, model_id)
    counts = {s: {st: sum(1 for t in ts if t["severity"] == s and t["status"] == st) for st in STATUS} for s in SEVERITY}
    blocking = [t for t in ts if t["severity"] in BLOCKING and t["status"] in ("open", "answered")]
    return {"threads": ts, "counts": counts, "blocking": len(blocking), "fingerprint": fp, "closure": closure,
            "closure_current": bool(closure) and closure.get("fingerprint") == fp,
            "severity": SEVERITY, "status": STATUS}


def close(store, model_id, reviewer, statement):
    s = summary(store, model_id)
    if s["blocking"]:
        raise ReviewError(f"{s['blocking']} critical or major comment(s) are not resolved. Resolve or withdraw them "
                          "before closing the review.")
    m = store.model(int(model_id))
    sc = m["scope"]
    sc["review_closure"] = {"reviewer": _txt(reviewer, "The reviewer's name", n=200),
                            "statement": _txt(statement, "The review statement", n=6000), "date": _now()[:10],
                            "fingerprint": s["fingerprint"],
                            "comments": sum(sum(v.values()) for v in s["counts"].values()),
                            "open_minor": sum(s["counts"][x]["open"] + s["counts"][x]["answered"]
                                              for x in ("minor", "editorial"))}
    store.x("UPDATE main.models SET scope=? WHERE id=?", (json.dumps(sc), int(model_id)))
    return sc["review_closure"]


def reopen(store, model_id):
    m = store.model(int(model_id))
    sc = m["scope"]
    sc.pop("review_closure", None)
    store.x("UPDATE main.models SET scope=? WHERE id=?", (json.dumps(sc), int(model_id)))


def export_file(store, model_id, path, author=""):
    ensure(store)
    m = store.model(int(model_id))
    if not m:
        raise ReviewError("Model not found.")
    rows = [dict(r) for r in store.q("SELECT * FROM main.review_comments WHERE model_id=?", (int(model_id),))]
    for r in rows:
        r.pop("model_id", None)
        r["history"] = json.loads(r["history"] or "[]")
    doc = {"format": FORMAT, "version": 1, "exported": _now(), "by": author,
           "model": {"name": m["name"], "fingerprint": fingerprint(store, model_id)},
           "checklist": (m["scope"] or {}).get("review_items") or {},
           "closure": (m["scope"] or {}).get("review_closure"), "comments": rows}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return {"comments": len(rows)}


def import_file(store, model_id, path):
    """Merge a review file into the model. Returns what was added, updated and kept."""
    ensure(store)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        raise ReviewError(f"The file could not be read ({e}).")
    if doc.get("format") != FORMAT:
        raise ReviewError("This is not a Cyclia review file.")
    if int(doc.get("version") or 0) > 1:
        raise ReviewError("The review file was written by a newer Cyclia. Update Cyclia first.")
    m = store.model(int(model_id))
    if not m:
        raise ReviewError("Model not found.")
    out = {"added": 0, "updated": 0, "unchanged": 0, "kept_local": 0, "skipped": 0,
           "model_name": doc.get("model", {}).get("name", ""),
           "same_model": doc.get("model", {}).get("fingerprint") == fingerprint(store, model_id)}
    cols = ("uid", "parent", "target", "target_label", "author", "role", "severity", "status", "text", "created",
            "modified")
    incoming = doc.get("comments") or []
    known = {c.get("uid") for c in incoming}
    # parents first, so replies always find their comment
    for c in sorted(incoming, key=lambda c: bool(c.get("parent"))):
        if not c.get("uid") or c.get("role") not in ROLES or (c.get("status") or "") not in STATUS + ("",) or \
                (c.get("severity") or "") not in SEVERITY + ("",) or not str(c.get("text") or "").strip():
            out["skipped"] += 1
            continue
        if c.get("parent") and c["parent"] not in known and not store.one(
                "SELECT 1 AS x FROM main.review_comments WHERE uid=?", (c["parent"],)):
            out["skipped"] += 1
            continue
        hist = json.dumps(c.get("history") or [])
        old = store.one("SELECT * FROM main.review_comments WHERE uid=?", (c["uid"],))
        vals = tuple(str(c.get(k) or "")[:6000] if k != "parent" else (c.get("parent") or None) for k in cols)
        if not old:
            store.x("INSERT INTO main.review_comments(" + ",".join(cols) + ", model_id, history) VALUES(" +
                    ",".join("?" * len(cols)) + ",?,?)", vals + (int(model_id), hist))
            out["added"] += 1
        elif old["model_id"] != int(model_id):
            out["skipped"] += 1
        elif (old["modified"] or "") == (c.get("modified") or "") and old["status"] == c.get("status") and \
                old["text"] == c.get("text"):
            out["unchanged"] += 1
        elif (c.get("modified") or "") > (old["modified"] or ""):
            h = json.loads(old["history"] or "[]")
            seen = {json.dumps(x, sort_keys=True) for x in h}
            for x in c.get("history") or []:
                if json.dumps(x, sort_keys=True) not in seen:
                    h.append(x)
            h.append({"time": _now(), "merged": True, "replaced": {"status": old["status"], "text": old["text"],
                                                                    "modified": old["modified"]}})
            store.x("UPDATE main.review_comments SET status=?, text=?, modified=?, history=? WHERE uid=?",
                    (c.get("status") or "", str(c.get("text"))[:6000], c.get("modified"), json.dumps(h), c["uid"]))
            out["updated"] += 1
        else:
            out["kept_local"] += 1
    sc = m["scope"]
    items = sc.get("review_items") or {}
    for k, v in (doc.get("checklist") or {}).items():
        if isinstance(v, dict) and (v.get("status") or v.get("comment")):
            items[k] = {"status": str(v.get("status") or "")[:40], "comment": str(v.get("comment") or "")[:4000],
                        "reviewer": str(v.get("reviewer") or "")[:200]}
    sc["review_items"] = items
    cl = doc.get("closure")
    if isinstance(cl, dict) and cl.get("statement") and (not sc.get("review_closure") or
                                                          (cl.get("date") or "") >= sc["review_closure"].get("date", "")):
        sc["review_closure"] = cl
        out["closure"] = True
    store.x("UPDATE main.models SET scope=? WHERE id=?", (json.dumps(sc), int(model_id)))
    return out
