"""Teaching mode: exercises on the demo database with answers computed live by the engine, so the answer key is
always consistent with the data. Students check their own answers; teachers export the key."""
import math

import calc
import units
from importers import demo


def _gwp(store):
    mid = demo.method_id(store, "climate change")
    if not mid:
        raise ValueError("Load the demo first (step 1, 'Load the full demo').")
    return mid


def _unit_impact(store, method_id, acts):
    mc = calc.get_mc(store)
    M = calc.Methods(store, mc, [method_id])
    h, _, _ = calc.impacts(mc, M, acts, {}, [])
    return float(h[0])


def _a(store, key):
    i = demo.act_id(store, key)
    if not i:
        raise ValueError("The demo database is not in the library. Load the demo first.")
    return i


def ex_dataset(store):
    g = _gwp(store)
    return _unit_impact(store, g, {_a(store, "concrete"): 1.0}), (
        "Search 'concrete' in step 3, add 1 m3 of 'concrete production, normal strength (demo)' to an empty model, select "
        "'Demo EF-style method: climate change' in step 4 and calculate.")


def ex_model(store):
    g = _gwp(store)
    v = _unit_impact(store, g, {_a(store, "concrete"): 0.2, _a(store, "steel"): 12.0})
    return v, "Model with 0.2 m3 concrete and 12 kg reinforcing steel; the result is the sum of both lines."


def ex_units(store):
    g = _gwp(store)
    v = _unit_impact(store, g, {_a(store, "steel"): 0.5, _a(store, "mkt_el_FR"): units.factor("MJ", "kWh") * 3.6})
    return v, "500 g steel = 0.5 kg; 3.6 MJ electricity = 1 kWh (market for electricity, FR). Choose the units in the amount field."


def ex_allocation(store):
    g = _gwp(store)
    kiln = {_a(store, "limestone"): 1.3, _a(store, "heat"): 3.4, _a(store, "mkt_el_DE"): 0.032}
    total = _unit_impact(store, g, kiln) + 0.54
    share = 50 / (50 + 5)
    return total * share, (f"Total burden of the kiln {total:.4g} kg CO2-eq (including 0.54 kg direct CO2) x economic share "
                           f"50/(50+5) = {share:.4f}. Open 'Clinker kiln with co-product (demo)'.")


def ex_credit(store):
    g = _gwp(store)
    s = _a(store, "steel")
    return _unit_impact(store, g, {s: 10.0 - 8.5}), "10 kg steel produced minus 8.5 kg avoided by recycling (system expansion)."


def ex_contribution(store):
    g = _gwp(store)
    cem = _unit_impact(store, g, {_a(store, "cement"): 1.0})
    cl = _unit_impact(store, g, {_a(store, "clinker"): 0.9})
    return 100 * cl / cem, "Supply chain tab: expand cement; clinker (0.9 kg per kg cement) divided by the cement total x 100."


def ex_dynamic(store):
    return calc.dynamic_weight("CH4f", 50, 100), ("Time-dependent weight of fossil methane emitted in year 50, counted to a "
                                                   "100-year horizon from the start (Levasseur et al. 2010).")


def ex_regional(store):
    mid = demo.method_id(store, "water use")
    if not mid:
        raise ValueError("Load the demo first.")
    return _unit_impact(store, mid, {_a(store, "tap_water"): 1000.0}), (
        "1000 kg tap water (FR) use 1 m3 river water; the French regional factor (20) applies, not the global 43.")


def ex_tox(store):
    import science
    r = science.toxicity_factors(demo.SUBSTANCE_X)
    return r["factors"]["water"]["freshwater ecotoxicity"], (
        "Toolbox > Chemicals: build screening factors for Substance X with the demo properties; read the ecotoxicity "
        "factor for emissions to water (CTUe per kg).")


EXERCISES = [
    {"id": "e1", "title": "Impact of one dataset", "level": "Beginner", "fn": ex_dataset, "unit": "kg CO2-eq", "tol": 0.01,
     "goal": "Find a dataset, add it with the right unit, read a result.",
     "task": "What is the climate change impact (Demo EF-style method) of 1 m3 of 'concrete production, normal strength "
             "(demo)'?", "hint": "Use 'market' or production datasets as they are; one line is enough."},
    {"id": "e2", "title": "A small product system", "level": "Beginner", "fn": ex_model, "unit": "kg CO2-eq", "tol": 0.01,
     "goal": "Build a model from several inputs.",
     "task": "A wall per m2 needs 0.2 m3 concrete (demo) and 12 kg reinforcing steel (demo). What is its climate change impact?",
     "hint": "Results of lines add up because the model is linear."},
    {"id": "e3", "title": "Units", "level": "Beginner", "fn": ex_units, "unit": "kg CO2-eq", "tol": 0.01,
     "goal": "Enter amounts in any convertible unit.",
     "task": "A part uses 500 g reinforcing steel (demo) and 3.6 MJ of electricity from 'market for electricity, medium "
             "voltage (demo)' in FR. Climate change impact?", "hint": "Cyclia converts g to kg and MJ to kWh for you."},
    {"id": "e4", "title": "Allocation", "level": "Intermediate", "fn": ex_allocation, "unit": "kg CO2-eq per kg clinker",
     "tol": 0.01, "goal": "Apply economic allocation to a multi-output process.",
     "task": "The kiln makes 1 kg clinker (50 EUR/t) and bypass dust worth 5 EUR/t per kg clinker. What climate impact is "
             "allocated to 1 kg clinker?", "hint": "Share = 50 / (50 + 5); open the locked demo model to see the inputs."},
    {"id": "e5", "title": "System expansion", "level": "Intermediate", "fn": ex_credit, "unit": "kg CO2-eq", "tol": 0.01,
     "goal": "Credit avoided production.",
     "task": "10 kg reinforcing steel (demo) are used; 8.5 kg are recycled at end of life and avoid new steel. Net climate "
             "impact including the credit?", "hint": "Tick 'Avoided product' on the credit line."},
    {"id": "e6", "title": "Contribution analysis", "level": "Intermediate", "fn": ex_contribution, "unit": "%", "tol": 0.02,
     "goal": "Read the supply chain tree.",
     "task": "What share (%) of the climate impact of 1 kg 'cement production, Portland (demo)' comes from clinker?",
     "hint": "Supply chain tab, expand the cement line."},
    {"id": "e7", "title": "Dynamic GWP", "level": "Advanced", "fn": ex_dynamic, "unit": "kg CO2-eq per kg CH4", "tol": 0.01,
     "goal": "Understand the timing of emissions.",
     "task": "With a 100-year horizon from today, what is the time-dependent weight of 1 kg fossil methane emitted in "
             "year 50?", "hint": "Later emissions count for less of the horizon."},
    {"id": "e8", "title": "Regional factors", "level": "Advanced", "fn": ex_regional, "unit": "m3 world-eq deprived", "tol": 0.01,
     "goal": "See how location changes a result.",
     "task": "Water use impact (demo, regional) of 1000 kg 'tap water production (demo)' in FR?",
     "hint": "The dataset is located in FR, so the French factor applies."},
    {"id": "e9", "title": "Screening toxicity factor", "level": "Advanced", "fn": ex_tox, "unit": "CTUe per kg", "tol": 0.02,
     "goal": "Build a factor from fate, exposure and effect.",
     "task": "Using the demo properties of Substance X, what is its freshwater ecotoxicity factor for emissions to water?",
     "hint": "Toolbox > Chemicals shows the properties of Substance X (demo)."},
    {"id": "q1", "title": "Interpreting a comparison", "level": "Intermediate", "choice": True,
     "goal": "Read uncertainty results correctly.",
     "task": "Wall A and wall B have overlapping 95 % intervals, but a paired Monte Carlo says A is lower in 97 % of "
             "iterations. Which statement is right?",
     "options": ["The difference is not meaningful because the intervals overlap.",
                 "A is lower with high confidence, because the shared background uncertainty cancels out in the paired comparison.",
                 "The comparison cannot be made without normalisation.",
                 "B is lower because its interval is narrower."],
     "answer": 1, "explanation": "Intervals of each wall include uncertainty they share (the same background data); a paired "
                                 "comparison uses the same random values for both and measures only the difference."},
    {"id": "q2", "title": "ISO 14044 rules", "level": "Beginner", "choice": True,
     "goal": "Know when weighting may be used.",
     "task": "Your study compares two products and will be published as a comparative assertion. May you use weighting "
             "to a single score?",
     "options": ["Yes, it is required.", "Yes, if the weights are from EF 3.1.",
                 "No, ISO 14044 does not allow weighting in comparative assertions disclosed to the public.",
                 "Only for climate change."],
     "answer": 2, "explanation": "ISO 14044 4.4.5: weighting shall not be used in LCA studies intended for comparative "
                                 "assertions disclosed to the public."},
]


def listing(teacher=False):
    out = []
    for e in EXERCISES:
        x = {k: e[k] for k in ("id", "title", "level", "goal", "task", "hint") if k in e}
        x["unit"] = e.get("unit", "")
        if e.get("choice"):
            x["options"] = e["options"]
        out.append(x)
    return out


def check(store, ex_id, answer):
    e = next((x for x in EXERCISES if x["id"] == ex_id), None)
    if not e:
        raise ValueError("Unknown exercise.")
    if e.get("choice"):
        ok = int(answer) == e["answer"]
        return {"correct": ok, "explanation": e["explanation"] if ok else "Not quite. Think about what the statement assumes.",
                "expected": e["options"][e["answer"]] if ok else None}
    try:
        val = float(str(answer).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("Enter a number.")
    exp, how = e["fn"](store)
    ok = abs(val - exp) <= e["tol"] * max(abs(exp), 1e-12)
    close = abs(val - exp) <= 0.1 * max(abs(exp), 1e-12)
    return {"correct": ok, "close": close and not ok,
            "message": "Correct." if ok else ("Close: check rounding, units or a missing line." if close else
                                              "Not yet. " + e.get("hint", ""))}


def answer_key(store):
    rows = []
    for e in EXERCISES:
        if e.get("choice"):
            rows.append({"id": e["id"], "title": e["title"], "task": e["task"], "answer": e["options"][e["answer"]],
                         "unit": "", "how": e["explanation"]})
        else:
            v, how = e["fn"](store)
            rows.append({"id": e["id"], "title": e["title"], "task": e["task"], "answer": f"{v:.4g}", "unit": e["unit"],
                         "how": how + f" Accepted within ±{e['tol'] * 100:g} %."})
    return rows


def answer_key_docx(store, path):
    from docx import Document
    from docx.shared import Pt
    import report
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading("Cyclia exercises: answer key", 0)
    report._note(doc, "Answers are calculated from the demo database installed on this computer. The data are illustrative.",
                 italic=True)
    for r in answer_key(store):
        doc.add_heading(f"{r['id'].upper()} {r['title']}", 2)
        doc.add_paragraph(r["task"])
        doc.add_paragraph(f"Answer: {r['answer']} {r['unit']}".strip())
        report._note(doc, r["how"])
    import report as _r
    _r._footer(doc)
    doc.save(path)
    return path
