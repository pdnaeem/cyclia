"""Social LCA: subcategory assessment with performance reference points (Type I), Cyclia 1.7.0.

Structure of the UNEP Guidelines for Social Life Cycle Assessment of Products and Organizations (2020) and ISO
14075: stakeholder categories, their subcategories, and for each subcategory an assessment of the organisations or
processes of the product system against performance reference points (PRP).

Scale (reference scale approach, as used in the UNEP 2020 guidelines and their methodological sheets):
  +2  ideal performance, well beyond what is required
  +1  progressive performance, beyond compliance
   0  compliant: meets the PRP (law, international standard or norm)
  -1  risky performance, below the PRP
  -2  very poor performance, serious breach

Each assessment row gives the stakeholder category, the subcategory, the organisation or process assessed, its
indicator and evidence, the PRP used, the score, the data type (site-specific primary, secondary generic) and the
activity variable that weights it (for example worker hours or value added of that organisation per functional
unit). Per subcategory: score = weighted mean of its rows; coverage = weight of the assessed organisations over
the total weight of the product system, which the user states. Subcategories without any row are listed as
missing. Rows with -1 or -2 are hotspots.

Cyclia ships no social data and invents none. The result is the assessment of the user's evidence, not a measure
taken from a database.
"""
import datetime

SCALE = {2: "ideal", 1: "progressive", 0: "compliant", -1: "risky", -2: "very poor"}
DATA_TYPES = ("site-specific primary", "secondary specific", "secondary generic", "expert judgement")

# UNEP Guidelines for Social LCA (2020), stakeholder categories and subcategories
SUBCATEGORIES = {
    "workers": ["Freedom of association and collective bargaining", "Child labour", "Fair salary", "Working hours",
                "Forced labour", "Equal opportunities and discrimination", "Health and safety",
                "Social benefits and social security", "Employment relationship", "Sexual harassment",
                "Smallholders, including farmers"],
    "local community": ["Access to material resources", "Access to immaterial resources",
                        "Delocalization and migration", "Cultural heritage", "Safe and healthy living conditions",
                        "Respect of indigenous rights", "Community engagement", "Local employment",
                        "Secure living conditions"],
    "value chain actors": ["Fair competition", "Promoting social responsibility", "Supplier relationships",
                           "Respect of intellectual property rights", "Wealth distribution"],
    "consumers": ["Health and safety", "Feedback mechanism", "Consumer privacy", "Transparency",
                  "End-of-life responsibility"],
    "society": ["Public commitments to sustainability issues", "Contribution to economic development",
                "Prevention and mitigation of armed conflicts", "Technology development", "Corruption",
                "Ethical treatment of animals", "Poverty alleviation"],
    "children": ["Education provided in the local community", "Health issues for children as consumers",
                 "Children concerns regarding marketing practices"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS main.slca_assessment (id INTEGER PRIMARY KEY, model_id INTEGER, stakeholder TEXT,
    subcategory TEXT, unit TEXT, indicator TEXT, prp TEXT, score INTEGER, weight REAL, weight_unit TEXT,
    data_type TEXT, evidence TEXT, source TEXT, author TEXT, modified TEXT);
CREATE TABLE IF NOT EXISTS main.slca_scope (model_id INTEGER PRIMARY KEY, total_weight REAL, weight_unit TEXT,
    excluded TEXT);
"""


class SocialError(ValueError):
    pass


def ensure(store):
    with store.lock:
        store.conn.executescript(SCHEMA)
        store.conn.commit()


def _txt(v, what, required=True, n=1000):
    v = (str(v) if v is not None else "").strip()
    if required and not v:
        raise SocialError(f"{what} is required.")
    return v[:n]


def save_row(store, model_id, d):
    ensure(store)
    if not store.model(int(model_id)):
        raise SocialError("Model not found.")
    sh = _txt(d.get("stakeholder"), "The stakeholder category").lower()
    if sh not in SUBCATEGORIES:
        raise SocialError("Choose a stakeholder category of the UNEP 2020 guidelines.")
    sub = _txt(d.get("subcategory"), "The subcategory")
    if sub not in SUBCATEGORIES[sh]:
        raise SocialError(f"'{sub}' is not a subcategory of {sh} in the UNEP 2020 guidelines.")
    try:
        score = int(d.get("score"))
    except (TypeError, ValueError):
        raise SocialError("The score is an integer from -2 to +2.")
    if score not in SCALE or str(d.get("score")).strip() not in {str(score), f"+{score}"}:
        raise SocialError("The score is an integer from -2 (very poor) to +2 (ideal).")
    try:
        w = float(d.get("weight"))
    except (TypeError, ValueError):
        raise SocialError("Give the activity variable (weight) of the assessed organisation, e.g. worker hours per "
                          "functional unit.")
    if not w > 0:
        raise SocialError("The weight must be positive.")
    dt = d.get("data_type") or ""
    if dt not in DATA_TYPES:
        raise SocialError("Choose the data type: " + ", ".join(DATA_TYPES) + ".")
    row = (int(model_id), sh, sub, _txt(d.get("unit"), "The organisation or process assessed", n=300),
           _txt(d.get("indicator"), "The indicator", n=500),
           _txt(d.get("prp"), "The performance reference point (the law, standard or norm the score refers to)", n=500),
           score, w, _txt(d.get("weight_unit"), "The unit of the weight", n=40),
           dt, _txt(d.get("evidence"), "The evidence", n=2000), _txt(d.get("source"), "The source", n=1000),
           _txt(d.get("author"), "Author", False, 200),
           datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat())
    with store.lock:
        if d.get("id"):
            n = store.conn.execute("UPDATE slca_assessment SET model_id=?, stakeholder=?, subcategory=?, unit=?, "
                                   "indicator=?, prp=?, score=?, weight=?, weight_unit=?, data_type=?, evidence=?, "
                                   "source=?, author=?, modified=? WHERE id=?", row + (int(d["id"]),)).rowcount
            if not n:
                raise SocialError("The assessment row was not found.")
            rid = int(d["id"])
        else:
            rid = store.conn.execute("INSERT INTO slca_assessment(model_id,stakeholder,subcategory,unit,indicator,prp,"
                                     "score,weight,weight_unit,data_type,evidence,source,author,modified) "
                                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row).lastrowid
        store.conn.commit()
    return rid


def delete_row(store, rid):
    ensure(store)
    store.x("DELETE FROM slca_assessment WHERE id=?", (int(rid),))


def set_scope(store, model_id, total_weight, weight_unit, excluded=""):
    """Total activity variable of the product system (for coverage) and the subcategories excluded, with reasons."""
    ensure(store)
    try:
        t = float(total_weight)
    except (TypeError, ValueError):
        raise SocialError("Give the total activity variable of the product system.")
    if not t > 0:
        raise SocialError("The total must be positive.")
    store.x("INSERT OR REPLACE INTO slca_scope VALUES(?,?,?,?)", (int(model_id), t, _txt(weight_unit, "The unit"),
                                                                   _txt(excluded, "Excluded", False, 3000)))


def assess(store, model_id):
    ensure(store)
    rows = [dict(r) for r in store.q("SELECT * FROM slca_assessment WHERE model_id=? ORDER BY stakeholder, "
                                     "subcategory, unit", (int(model_id),))]
    sc = store.one("SELECT * FROM slca_scope WHERE model_id=?", (int(model_id),))
    total = sc["total_weight"] if sc else None
    unit = sc["weight_unit"] if sc else ""
    units_used = {r["weight_unit"] for r in rows}
    warn = []
    if len(units_used) > 1:
        warn.append("The rows use different weight units (" + ", ".join(sorted(units_used)) + "); weighting across "
                    "them is not meaningful. Use one activity variable.")
    if sc and rows and units_used and unit not in units_used:
        warn.append(f"The total is given in {unit}, the rows in {', '.join(sorted(units_used))}.")
    excluded = [x.strip() for x in ((sc["excluded"] if sc else "") or "").split("\n") if x.strip()]
    out, missing = [], []
    for sh, subs in SUBCATEGORIES.items():
        for sub in subs:
            rs = [r for r in rows if r["stakeholder"] == sh and r["subcategory"] == sub]
            if not rs:
                if not any(e.lower().startswith(sub.lower()) for e in excluded):
                    missing.append({"stakeholder": sh, "subcategory": sub})
                continue
            # one organisation counts once per subcategory: its rows are averaged first (equal weight per indicator)
            per_unit = {}
            for r in rs:
                per_unit.setdefault(r["unit"], []).append(r)
            wsum = sum(v[0]["weight"] for v in per_unit.values())
            score = sum(v[0]["weight"] * (sum(x["score"] for x in v) / len(v)) for v in per_unit.values()) / wsum
            primary = sum(v[0]["weight"] for v in per_unit.values() if any(x["data_type"] == "site-specific primary"
                                                                          for x in v)) / wsum
            out.append({"stakeholder": sh, "subcategory": sub, "score": score, "level": SCALE[round(score)] if
                        round(score) in SCALE else "", "organisations": len(per_unit), "weight": wsum,
                        "coverage": (wsum / total) if total else None, "primary_share": primary,
                        "hotspots": [{"unit": r["unit"], "indicator": r["indicator"], "score": r["score"],
                                      "evidence": r["evidence"]} for r in rs if r["score"] <= -1]})
    by_sh = []
    for sh in SUBCATEGORIES:
        xs = [x for x in out if x["stakeholder"] == sh]
        by_sh.append({"stakeholder": sh, "assessed": len(xs), "of": len(SUBCATEGORIES[sh]),
                      "mean_score": (sum(x["score"] for x in xs) / len(xs)) if xs else None,
                      "lowest": min((x["score"] for x in xs), default=None),
                      "missing": [m["subcategory"] for m in missing if m["stakeholder"] == sh]})
    n_all = sum(len(v) for v in SUBCATEGORIES.values())
    return {"subcategories": out, "by_stakeholder": by_sh, "missing": missing, "excluded": excluded,
            "rows": rows, "total_weight": total, "weight_unit": unit, "warnings": warn,
            "completeness": len(out) / n_all, "scale": SCALE,
            "note": "Type I (reference scale) assessment after the UNEP Guidelines for Social LCA (2020): each "
                    "organisation or process is scored against a performance reference point from -2 (very poor) to "
                    "+2 (ideal), 0 meaning compliance. A subcategory score is the mean over the assessed organisations "
                    "weighted by their activity variable (indicators of one organisation averaged first). Coverage is "
                    "the assessed weight over the total of the product system. Subcategories are not aggregated across "
                    "stakeholders into one score: each is reported, with the lowest score per stakeholder. Missing "
                    "subcategories are listed unless excluded with a reason."}
