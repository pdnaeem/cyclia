"""Full feature demo: an illustrative database, illustrative methods and a project that exercises every Cyclia
feature (models, parameters, scenarios, EN 15804 modules and module D, EPD values, allocation, dynamic GWP,
background scenarios, consequential rules, external model emissions, site-specific and screening toxicity
factors, templates, comments, versions, a locked model).

ALL NUMBERS ARE ILLUSTRATIVE. They are rounded, simplified values chosen to teach the software and must not be cited.
"""
import uuid

NS = uuid.UUID("5a0d3c2e-8f61-4c1b-b7e2-91d6a8f4c3b5")
DB_NAME = "Cyclia demo database (illustrative)"
FAMILY = "Demo EF-style method (illustrative)"
NW_SET = "Demo normalisation and weighting (illustrative)"

FLOWS = {  # key: (name, compartment, subcompartment, unit)
    "co2": ("Carbon dioxide, fossil", "air", "unspecified", "kg"),
    "co2bio": ("Carbon dioxide, non-fossil", "air", "unspecified", "kg"),
    "co2air": ("Carbon dioxide, in air", "natural resource", "in air", "kg"),
    "ch4": ("Methane, fossil", "air", "unspecified", "kg"),
    "ch4bio": ("Methane, non-fossil", "air", "unspecified", "kg"),
    "n2o": ("Dinitrogen monoxide", "air", "unspecified", "kg"),
    "so2": ("Sulfur dioxide", "air", "unspecified", "kg"),
    "nox": ("Nitrogen oxides", "air", "unspecified", "kg"),
    "nh3": ("Ammonia", "air", "unspecified", "kg"),
    "pm": ("Particulate Matter, < 2.5 um", "air", "unspecified", "kg"),
    "cu_w": ("Copper, ion", "water", "surface water", "kg"),
    "cu_s": ("Copper, ion", "soil", "unspecified", "kg"),
    "zn_w": ("Zinc, ion", "water", "surface water", "kg"),
    "po4": ("Phosphate", "water", "surface water", "kg"),
    "water": ("Water, river", "natural resource", "in water", "m3"),
    "land": ("Occupation, arable land", "natural resource", "land", "m2*year"),
    "oil": ("Oil, crude", "natural resource", "in ground", "kg"),
    "gas": ("Gas, natural, in ground", "natural resource", "in ground", "m3"),
    "coal": ("Coal, hard", "natural resource", "in ground", "kg"),
}
EL = "electricity, medium voltage"
# key: (name, product, unit, location, {input: amount}, {flow: amount})
PROCESSES = {
    "el_coal_PL": ("electricity production, hard coal (demo)", EL, "kWh", "PL", {},
                   {"coal": 0.40, "co2": 0.95, "ch4": 0.002, "so2": 0.003, "nox": 0.0015, "pm": 0.0002, "water": 0.002}),
    "el_coal_CN": ("electricity production, hard coal (demo)", EL, "kWh", "CN", {},
                   {"coal": 0.42, "co2": 1.00, "ch4": 0.002, "so2": 0.004, "nox": 0.002, "pm": 0.0004, "water": 0.002}),
    "el_gas_DE": ("electricity production, natural gas, combined cycle (demo)", EL, "kWh", "DE", {},
                  {"gas": 0.18, "co2": 0.37, "ch4": 0.0008, "nox": 0.0003, "water": 0.001}),
    "el_wind_DE": ("electricity production, wind, onshore (demo)", EL, "kWh", "DE", {"steel": 0.003, "concrete": 0.000005}, {}),
    "el_pv_DE": ("electricity production, photovoltaic (demo)", EL, "kWh", "DE", {"pv_panel": 0.000167}, {}),
    "el_pv_CN": ("electricity production, photovoltaic (demo)", EL, "kWh", "CN", {"pv_panel": 0.00012}, {}),
    "el_nuclear_FR": ("electricity production, nuclear (demo)", EL, "kWh", "FR", {}, {"co2": 0.006, "water": 0.004}),
    "mkt_el_FR": ("market for electricity, medium voltage (demo)", EL, "kWh", "FR",
                  {"el_nuclear_FR": 0.72, "el_gas_DE": 0.10, "el_wind_DE": 0.10, "el_pv_DE": 0.03, "el_coal_PL": 0.05}, {}),
    "mkt_el_DE": ("market for electricity, medium voltage (demo)", EL, "kWh", "DE",
                  {"el_coal_PL": 0.25, "el_gas_DE": 0.20, "el_wind_DE": 0.33, "el_pv_DE": 0.12, "el_nuclear_FR": 0.10}, {}),
    "mkt_el_PL": ("market for electricity, medium voltage (demo)", EL, "kWh", "PL",
                  {"el_coal_PL": 0.70, "el_wind_DE": 0.15, "el_gas_DE": 0.15}, {}),
    "mkt_el_CN": ("market for electricity, medium voltage (demo)", EL, "kWh", "CN", {"el_coal_CN": 0.65, "el_pv_CN": 0.35}, {}),
    "heat": ("heat production, natural gas, industrial furnace (demo)", "heat, natural gas", "MJ", "RER", {},
             {"gas": 0.027, "co2": 0.056, "ch4": 0.0001, "nox": 0.00004}),
    "diesel": ("diesel, burned in machinery (demo)", "diesel, burned in machinery", "MJ", "GLO", {},
               {"oil": 0.0235, "co2": 0.074, "nox": 0.0009, "so2": 0.00002, "n2o": 0.000003, "pm": 0.00003}),
    "lorry": ("transport, freight, lorry 16-32 metric ton (demo)", "transport, freight, lorry", "t*km", "RER",
              {"diesel": 1.2}, {"pm": 0.00001}),
    "limestone": ("limestone quarrying (demo)", "limestone, crushed", "kg", "RER", {"diesel": 0.03, "mkt_el_DE": 0.005}, {}),
    "gravel": ("gravel and sand quarrying (demo)", "gravel and sand", "kg", "FR", {"diesel": 0.02, "mkt_el_FR": 0.002},
               {"pm": 0.00001}),
    "tap_water": ("tap water production (demo)", "tap water", "kg", "FR", {"mkt_el_FR": 0.0005}, {"water": 0.001}),
    "clinker": ("clinker production (demo)", "clinker", "kg", "DE", {"limestone": 1.25, "heat": 3.3, "mkt_el_DE": 0.03},
                {"co2": 0.53, "nox": 0.0012, "so2": 0.0002, "pm": 0.00005}),
    "cement": ("cement production, Portland (demo)", "cement, Portland", "kg", "DE",
               {"clinker": 0.9, "mkt_el_DE": 0.05, "lorry": 0.05}, {}),
    "concrete": ("concrete production, normal strength (demo)", "concrete, normal strength", "m3", "FR",
                 {"cement": 300, "gravel": 1900, "tap_water": 180, "mkt_el_FR": 4, "lorry": 95}, {}),
    "steel": ("reinforcing steel production (demo)", "reinforcing steel", "kg", "RER",
              {"mkt_el_PL": 0.6, "heat": 12, "lorry": 0.1}, {"co2": 1.1, "so2": 0.002, "nox": 0.0015, "pm": 0.0003,
                                                             "zn_w": 0.00001}),
    "lime": ("lime production, hydrated (demo)", "lime, hydrated", "kg", "FR",
             {"limestone": 1.35, "heat": 4.5, "mkt_el_FR": 0.04}, {"co2": 0.75, "nox": 0.0008}),
    "fert_n": ("ammonium nitrate production (demo)", "ammonium nitrate, as N", "kg", "RER",
               {"mkt_el_DE": 0.3, "heat": 25}, {"co2": 1.8, "n2o": 0.007, "nh3": 0.002}),
    "hemp": ("hemp shiv production (demo)", "hemp shiv", "kg", "FR",
             {"diesel": 0.6, "mkt_el_FR": 0.08, "lorry": 0.08, "fert_n": 0.02},
             {"n2o": 0.002, "nh3": 0.003, "po4": 0.0005, "land": 1.5, "co2air": 1.6}),
    "hempcrete": ("hempcrete block production (demo)", "hempcrete block", "kg", "FR",
                  {"hemp": 0.35, "lime": 0.45, "tap_water": 0.4, "mkt_el_FR": 0.05}, {}),
    "timber": ("sawnwood production, softwood (demo)", "sawnwood, softwood", "m3", "SE",
               {"diesel": 350, "mkt_el_DE": 110, "lorry": 50}, {"land": 200, "co2air": 750}),
    "mineral_wool": ("mineral wool production (demo)", "mineral wool", "kg", "DE", {"mkt_el_DE": 1.6, "heat": 9, "lorry": 0.1},
                     {"co2": 0.4, "nox": 0.002}),
    "copper": ("copper sheet production (demo)", "copper sheet", "kg", "RER", {"mkt_el_PL": 3.0, "heat": 15, "lorry": 0.2},
               {"co2": 1.5, "so2": 0.02, "cu_w": 0.0002, "pm": 0.0005}),
    "pet": ("polyethylene terephthalate production, granulate (demo)", "polyethylene terephthalate, granulate", "kg", "RER",
            {"heat": 30, "mkt_el_DE": 1.5}, {"oil": 1.2, "co2": 2.0, "nox": 0.002}),
    "blow": ("stretch blow moulding (demo)", "stretch blow moulding", "kg", "RER", {"mkt_el_DE": 1.8}, {}),
    "msw": ("treatment of municipal solid waste, incineration (demo)", "municipal solid waste incineration", "kg", "FR",
            {"mkt_el_FR": 0.05}, {"co2": 1.0, "nox": 0.001}),
    "inert_landfill": ("treatment of inert waste, landfill (demo)", "inert waste landfill", "kg", "FR",
                       {"diesel": 0.01}, {"pm": 0.000002}),
    "wood_incin": ("treatment of waste wood, incineration (demo)", "waste wood incineration", "kg", "FR", {"mkt_el_FR": 0.01},
                   {"co2bio": 1.6, "nox": 0.0008}),
    "pv_panel": ("photovoltaic panel production, multi-Si (demo)", "photovoltaic panel", "m2", "CN",
                 {"mkt_el_CN": 120, "heat": 200, "lorry": 10}, {"co2": 2.0}),
    "inverter": ("inverter production, 2.5 kW (demo)", "inverter", "unit", "RER",
                 {"mkt_el_DE": 60, "copper": 1.5, "steel": 6, "lorry": 2}, {}),
}

# Illustrative characterisation factors (rounded values in the spirit of EF 3.1, USEtox and AWARE)
CATS = [
    ("climate change", "global warming potential (GWP100)", "kg CO2-eq",
     {"co2": 1.0, "co2bio": 0.0, "ch4": 29.8, "ch4bio": 27.0, "n2o": 273.0}),
    ("acidification", "accumulated exceedance", "mol H+-eq", {"so2": 1.31, "nox": 0.74, "nh3": 3.02}),
    ("particulate matter formation", "impact on human health", "disease incidence", {"pm": 6.3e-4}),
    ("eutrophication, freshwater", "fraction of nutrients reaching freshwater", "kg P-eq", {"po4": 0.33}),
    ("ecotoxicity, freshwater", "comparative toxic unit for ecosystems", "CTUe", {"cu_w": 3.5e4, "cu_s": 5.0e3, "zn_w": 1.5e4}),
    ("human toxicity, non-cancer", "comparative toxic unit for human", "CTUh", {"cu_w": 1.0e-5, "cu_s": 2.0e-6, "zn_w": 2.0e-5}),
    ("land use", "land occupation", "m2*year", {"land": 1.0}),
    ("resource use, fossils", "abiotic depletion potential, fossil fuels", "MJ", {"oil": 45.8, "gas": 38.3, "coal": 19.1}),
]
WATER = ("water use", "user deprivation potential", "m3 world-eq deprived", 43.0,
         {"FR": 20.0, "DE": 15.0, "PL": 12.0, "CN": 41.0, "SE": 2.0})
NW = {"climate change": (8.1e3, 0.211), "acidification": (55.6, 0.062), "particulate matter formation": (5.95e-4, 0.090),
      "eutrophication, freshwater": (1.61, 0.028), "ecotoxicity, freshwater": (5.67e4, 0.019),
      "human toxicity, non-cancer": (2.3e-4, 0.018), "land use": (8.0e4, 0.079), "resource use, fossils": (6.5e4, 0.083),
      "water use": (1.15e4, 0.085)}
SUBSTANCE_X = {"mw": 230.0, "log_kow": 3.2, "henry": 0.05, "vp": 1e-4, "hl_air": 1.5, "hl_water": 40, "hl_soil": 90,
               "hc50": 0.05, "ed50_noncancer": 20}


def act_id(store, key):
    r = store.one("SELECT a.id FROM activities a JOIN databases d ON d.id=a.db_id WHERE d.name=? AND a.key=?", (DB_NAME, key))
    return r["id"] if r else None


def flow_id(store, key):
    r = store.one("SELECT id FROM flows WHERE uuid=?", (str(uuid.uuid5(NS, "flow-" + key)),))
    return r["id"] if r else None


def method_id(store, category):
    r = store.one("SELECT id FROM methods WHERE family=? AND category=?", (FAMILY, category))
    return r["id"] if r else None


def install_database(store, progress=lambda *a: None):
    """Demo database and methods; idempotent."""
    from importers import lcia
    if store.one("SELECT id FROM databases WHERE name=?", (DB_NAME,)):
        return False
    db_id = store.create_database(DB_NAME, "demo", "1.0", "attributional (illustrative)",
                                  "Illustrative data for learning and testing every feature. Do not cite.")
    with store.lock:
        c = store.conn
        flows = {k: store.add_flow(str(uuid.uuid5(NS, "flow-" + k)), n, comp, sub, u) for k, (n, comp, sub, u) in FLOWS.items()}
        acts = {}
        for k, (n, prod, u, loc, _, _) in PROCESSES.items():
            acts[k] = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production,comment) "
                                "VALUES(?,?,?,?,?,?,1.0,?)", (db_id, k, n, prod, loc, u,
                                                             "Illustrative demo dataset. Not for publication.")).lastrowid
        for k, (_, _, _, _, ins, ems) in PROCESSES.items():
            for i, a in ins.items():
                c.execute("INSERT INTO tech(output_id,input_id,amount,utype,p1) VALUES(?,?,?,1,?)", (acts[k], acts[i], a, 0.1))
            for f, a in ems.items():
                c.execute("INSERT INTO bio(activity_id,flow_id,amount,utype,p1) VALUES(?,?,?,1,?)",
                          (acts[k], flows[f], a, 0.05 if f in ("co2", "co2bio", "co2air") else 0.3))
        c.commit()
    store.finish_database(db_id)
    progress(40, "Demo methods")
    mids = []
    for cat, ind, unit, cfs in CATS:
        mid = store.get_or_create_method(FAMILY, cat, ind, unit, "demo", "Illustrative factors for the demo. Do not cite.")
        store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
        lcia.store_raw(store, mid, [(FLOWS[k][0], FLOWS[k][1], FLOWS[k][2], "", None, v) for k, v in cfs.items()])
        mids.append(mid)
    cat, ind, unit, generic, regional = WATER
    mid = store.get_or_create_method(FAMILY, cat, ind, unit, "demo", "Illustrative regional factors (AWARE-like).")
    store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
    lcia.store_raw(store, mid, [(FLOWS["water"][0], FLOWS["water"][1], "", "", None, generic)] +
                   [(FLOWS["water"][0], FLOWS["water"][1], "", loc, None, v) for loc, v in regional.items()])
    mids.append(mid)
    lcia.rematch(store, mids)
    with store.lock:
        for m in mids:
            r = store.one("SELECT category FROM methods WHERE id=?", (m,))
            n, w = NW[r["category"]]
            store.conn.execute("INSERT OR REPLACE INTO nw VALUES(?,?,?,?)", (m, NW_SET, n, w))
        store.conn.commit()
    return True


def build_project(store, author="Demo author", progress=lambda *a: None):
    """Models and settings of the feature demo, in the (empty) project behind `store`."""
    import productivity
    import science
    from importers import lcia
    lcia.install_builtin(store)
    A = lambda k: act_id(store, k)
    F = lambda k: flow_id(store, k)
    en = "EN 15804 (construction products)"
    common = {"comparative": "No", "author": author, "boundary": "cradle-to-grave", "stage_system": en,
              "geography": "France", "period": "2024 to 2026",
              "cutoff": "EN 15804+A2: at most 1 % of mass and energy per unit process, at most 5 % per module",
              "application": "Software demonstration and teaching", "audience": "Researchers and students",
              "reasons": "To show every step of an LCA in Cyclia", "dynamic": True, "horizon": "100",
              "assumptions": "Reference service life 50 years; end-of-life emissions occur in year 50.",
              "epd": {"manufacturer": "Demo Materials Ltd", "site": "Lyon, France", "programme": "Demo EPD programme",
                      "number": "DEMO-0001", "pcr": "EN 15804+A2 and the demo PCR for walls", "rsl": "50 years",
                      "verification": "Independent external verification (ISO 14025)", "verifier": "A. Verifier",
                      "biogenic_product": "0", "biogenic_packaging": "0.05",
                      "declared": ["A1-A3", "A4", "C1", "C2", "C3", "C4", "D"]}}
    progress(5, "Concrete wall")
    wall = store.save_model({"name": "Concrete wall (demo)", "product": "external wall, load-bearing, U = 0.25 W/m2K",
                             "unit": "m2", "amount": 1,
                             "scope": dict(common, goal="Compare the climate and environmental impacts of a concrete and a "
                                                        "hempcrete wall per m2", fu_description="1 m2 of external wall with "
                                                        "U = 0.25 W/m2K over a 50-year reference service life",
                                           allocation="No co-products in the foreground; EN 15804 module D for steel recycling")})
    for p in ({"name": "thickness", "value": 0.2, "unit": "m", "utype": 4, "p1": 0.18, "p2": 0.25,
               "comment": "structural design, range from the engineer"},
              {"name": "steel_kg", "value": 12, "unit": "kg/m2", "utype": 2, "p1": 1.5},
              {"name": "transport_km", "value": 50, "unit": "km", "utype": 3, "p1": 20, "p2": 50, "p3": 120}):
        store.save_parameter(dict(p, model_id=wall))
    lines = [
        ("activity", "concrete", 0.2, "m3", "thickness", "A1-A3 Product stage", False, [2, 2, 2, 1, 2], "Supplier data 2024"),
        ("activity", "steel", 12, "kg", "steel_kg", "A1-A3 Product stage", False, [2, 3, 3, 3, 2], "Structural calculation"),
        ("activity", "mineral_wool", 4.0, "kg", None, "A1-A3 Product stage", False, [3, 3, 2, 3, 3], "Manufacturer datasheet"),
        ("activity", "lorry", 24.6, "t*km", "(thickness * 2400 + steel_kg + 4) / 1000 * transport_km", "A4 Transport to site",
         False, [3, 3, 2, 2, 3], "Distance to the batching plant"),
        ("activity", "diesel", 15.0, "MJ", None, "C1 Deconstruction", False, [4, 4, 3, 3, 3], "Estimate"),
        ("activity", "lorry", 14.4, "t*km", "(thickness * 2400 + steel_kg) / 1000 * 30", "C2 Transport to waste processing",
         False, [3, 3, 3, 3, 3], "30 km to the recycling plant"),
        ("activity", "inert_landfill", 72.0, "kg", "thickness * 2400 * 0.15", "C4 Disposal", False, [3, 3, 3, 3, 3],
         "85 % of concrete recycled as aggregate, 15 % landfilled"),
        ("activity", "steel", 10.2, "kg", "steel_kg * 0.85", "D Benefits and loads beyond the system boundary", True,
         [3, 3, 3, 3, 3], "Recycling rate 85 %"),
    ]
    _add_lines(store, wall, lines, A)
    years = {"C1 Deconstruction": 50, "C2 Transport to waste processing": 50, "C4 Disposal": 50}
    for i in store.model(wall)["inputs"]:
        if i["stage"] in years:
            store.update_input(i["id"], {"year": years[i["stage"]]})
    gwp_ids = [m["id"] for m in store.methods() if m["family"] == lcia.BUILTIN_FAMILY]
    impacts = [{"family": FAMILY, "category": "climate change", "indicator": "global warming potential (GWP100)", "value": 0.12}]
    for mid in gwp_ids:
        m = store.one("SELECT family, category, indicator FROM methods WHERE id=?", (mid,))
        v = {"climate change: total": 0.12, "climate change: fossil": 0.12}.get(m["category"], 0.0)
        impacts.append(dict(m, value=v))
    store.add_input(wall, "fixed", None, 10.0, label="Gypsum plaster (EPD values)", comment="EPD-DEMO-PLASTER-2025, demo "
                    "programme", stage="A1-A3 Product stage", input_amount=10.0, input_unit="kg",
                    pedigree=[2, 2, 2, 3, 3], fixed={"name": "Gypsum plaster (EPD values)", "unit": "kg", "location": "FR",
                                                      "source": "EPD-DEMO-PLASTER-2025", "impacts": impacts})
    store.save_scenario({"name": "Thin wall", "description": "18 cm wall", "overrides": {"thickness": 0.18}})
    store.save_scenario({"name": "Long transport", "description": "Remote batching plant", "overrides": {"transport_km": 150}})
    store.save_version(wall, "Baseline, 12 kg steel per m2", author)
    store.x("UPDATE main.parameters SET value=14 WHERE model_id=? AND name='steel_kg'", (wall,))
    store.save_version(wall, "Revised steel ratio, 14 kg per m2", author)
    inputs = store.model(wall)["inputs"]
    store.add_comment(wall, inputs[1]["id"], "Supervisor", "Check the steel ratio with the structural engineer; 14 kg/m2 "
                                                           "seems high for a 20 cm wall.")
    c2 = store.add_comment(wall, inputs[0]["id"], author, "Concrete volume now follows the thickness parameter.")
    store.resolve_comment(c2)
    store.add_comment(wall, None, "Reviewer", "Please add the uncertainty analysis to the report before submission.")

    progress(25, "Hempcrete wall")
    hemp = store.save_model({"name": "Hempcrete wall (demo)", "product": "external wall, load-bearing, U = 0.25 W/m2K",
                             "unit": "m2", "amount": 1,
                             "scope": dict(common, goal="Compare the climate and environmental impacts of a concrete and a "
                                                        "hempcrete wall per m2", fu_description="1 m2 of external wall with "
                                                        "U = 0.25 W/m2K over a 50-year reference service life",
                                           allocation="Hemp shiv: no allocation in this demo (whole plant attributed)")})
    store.save_parameter({"model_id": hemp, "name": "transport_km", "value": 80, "unit": "km", "utype": 3,
                          "p1": 40, "p2": 80, "p3": 200})
    hlines = [
        ("activity", "hempcrete", 110, "kg", None, "A1-A3 Product stage", False, [2, 2, 2, 1, 2], "Manufacturer data"),
        ("activity", "timber", 0.025, "m3", None, "A1-A3 Product stage", False, [2, 3, 2, 2, 2], "Frame design"),
        ("activity", "lime", 15, "kg", None, "A1-A3 Product stage", False, [3, 3, 2, 2, 3], "Render, 2 cm"),
        ("activity", "lorry", 12.0, "t*km", "0.15 * transport_km", "A4 Transport to site", False, [3, 3, 2, 2, 3], "Estimate"),
        ("activity", "lorry", 4.5, "t*km", "0.15 * 30", "C2 Transport to waste processing", False, [3, 3, 3, 3, 3], "30 km"),
        ("activity", "wood_incin", 12.0, "kg", None, "C3 Waste processing", False, [3, 3, 3, 3, 3], "Timber frame incinerated"),
        ("activity", "inert_landfill", 125, "kg", None, "C4 Disposal", False, [3, 3, 3, 3, 3], "Hempcrete and render landfilled"),
    ]
    _add_lines(store, hemp, hlines, A)
    for i in store.model(hemp)["inputs"]:
        if i["stage"].startswith("C"):
            store.update_input(i["id"], {"year": 50})

    progress(40, "Copper roof with external model emissions")
    roof = store.save_model({"name": "Copper roof runoff, 1 m2 over 30 years (demo)", "product": "roof covering, copper",
                             "unit": "m2", "amount": 1,
                             "scope": {"goal": "Include metal runoff computed by an external leaching model",
                                       "boundary": "cradle-to-grave", "stage_system": en, "geography": "France",
                                       "application": "Demonstration of fate-model coupling", "audience": "Researchers",
                                       "assumptions": "Runoff from a first-order leaching model; 70 % to surface water, "
                                                      "30 % to soil.", "dynamic": True, "horizon": "100"}})
    _add_lines(store, roof, [("activity", "copper", 5.0, "kg", None, "A1-A3 Product stage", False, [2, 2, 2, 2, 2],
                              "Sheet 0.6 mm")], A)
    rows = []
    for year in range(1, 31):
        rate = 0.0021 * (0.97 ** (year - 1))
        rows.append({"year": str(year), "flow": "Copper, ion", "compartment": "water", "subcompartment": "surface water",
                     "amount": f"{rate * 0.7:.6g}", "unit": "kg"})
        rows.append({"year": str(year), "flow": "Copper, ion", "compartment": "soil", "subcompartment": "unspecified",
                     "amount": f"{rate * 0.3:.6g}", "unit": "kg"})
    science.import_external(store, roof, rows, aggregate=True, stage="B1 Use", source="external leaching model (demo)")
    science.install_chemical(store, "Substance X (demo)", "000-00-0", SUBSTANCE_X)
    sx = store.one("SELECT id FROM flows WHERE name='Substance X (demo)' AND compartment='water'")
    store.add_input(roof, "flow", sx["id"], 2e-5, label="Substance X (demo)", comment="coating additive, leaching estimate",
                    stage="B1 Use", input_amount=2e-5, input_unit="kg", pedigree=[4, 4, 3, 3, 4])
    store.save_site_cf({"family": FAMILY, "category": "ecotoxicity, freshwater",
                        "indicator": "comparative toxic unit for ecosystems",
                        "flow_uuid": str(uuid.uuid5(NS, "flow-cu_w")), "value": 1.2e4,
                        "note": "Local river with high hardness and DOC: lower bioavailable fraction (illustrative)"})

    progress(55, "Clinker kiln with co-product")
    kiln = store.save_model({"name": "Clinker kiln with co-product (demo)", "product": "clinker", "unit": "kg", "amount": 1,
                             "scope": {"goal": "Show economic allocation between clinker and kiln dust",
                                       "boundary": "gate-to-gate", "stage_system": "General",
                                       "allocation": "Economic allocation between clinker (50 EUR/t) and bypass dust (5 EUR/t)",
                                       "alloc_basis": "price", "main_price": 50,
                                       "coproducts": [{"name": "bypass dust", "mass": 0.05, "price": 5}],
                                       "geography": "Germany", "period": "2025", "application": "Teaching",
                                       "main_mass": 1,
                                       "audience": "Students"}})
    _add_lines(store, kiln, [("activity", "limestone", 1.3, "kg", None, "Raw materials", False, [2, 2, 2, 2, 2], "Plant data"),
                             ("activity", "heat", 3.4, "MJ", None, "Manufacturing", False, [1, 2, 1, 1, 1], "Plant data"),
                             ("activity", "mkt_el_DE", 0.032, "kWh", None, "Manufacturing", False, [1, 2, 1, 1, 1],
                              "Plant data")], A)
    store.add_input(kiln, "flow", F("co2"), 0.54, label="Carbon dioxide, fossil", comment="Calcination and fuel, plant data",
                    stage="Manufacturing", input_amount=0.54, input_unit="kg", pedigree=[1, 2, 1, 1, 1])
    store.set_lock(kiln, True, author, "Reviewed by the supervisor; do not edit")

    progress(70, "Models from templates")
    for tid, name in (("packaging-pef", "Beverage bottle (template demo)"), ("food-crop", "Arable crop (template demo)"),
                      ("energy-pv", "Rooftop PV electricity (template demo)")):
        tpl = next(t for t in productivity.BUILTIN_TEMPLATES if t["id"] == tid)
        productivity.apply_template(store, tpl, name)

    progress(85, "Background scenarios")
    store.save_bg_scenario({"name": "Electricity decarbonisation (illustrative)", "kind": "prospective", "base_year": 2020,
                            "description": "Coal power with carbon capture and more efficient steel making",
                            "rules": [{"type": "scale_emission", "activity": "electricity production, hard coal",
                                       "flow": "carbon dioxide, fossil", "factor": {"2030": 0.8, "2050": 0.3}},
                                      {"type": "scale_input", "activity": "reinforcing steel production",
                                       "input": "electricity", "factor": {"2050": 0.8}}]})
    store.save_bg_scenario({"name": "Marginal electricity is onshore wind (illustrative)", "kind": "consequential",
                            "description": "Additional demand in FR and DE met by new wind power",
                            "rules": [{"type": "swap", "activity_ids": [A("mkt_el_FR"), A("mkt_el_DE")],
                                       "product": "electricity", "to": [{"id": A("el_wind_DE"), "share": 1.0}]}]})
    store.set_meta("demo", True)
    progress(100, "Demo ready")
    meths = [m for m in store.methods() if m["family"] in (FAMILY, lcia.BUILTIN_FAMILY) and m["n_cfs"]]
    order = lambda m: (0 if m["category"] == "climate change: total" else 1 if m["family"] == FAMILY else 2, m["category"])
    return {"models": [m["id"] for m in store.models()], "methods": [m["id"] for m in sorted(meths, key=order)]}


def _add_lines(store, model_id, lines, A):
    import calc
    import formula as fm
    import units
    for kind, key, amount, unit, formula, stage, avoided, ped, comment in lines:
        if formula:
            amount = fm.evaluate(formula, calc.Context(store).params(model_id))
        target = store.one("SELECT unit FROM activities WHERE id=?", (A(key),))["unit"]
        conv = float(amount) * (units.factor(unit, target) or 1.0)
        store.add_input(model_id, kind, A(key), conv, comment=comment, stage=stage, input_amount=float(amount),
                        input_unit=unit, avoided=avoided, pedigree=ped, formula=formula)


LITERATURE_EXAMPLE = """Table 2. Inventory per m3 of concrete (Example et al., 2023)
Portland cement\t300\tkg\tA1
Gravel and sand\t1,900\tkg\tA1
Tap water\t180\tkg\tA1
Electricity, medium voltage\t4\tkWh\tA3
Transport, lorry\t95\ttkm\tA2
Methane emission to air\t0.002\tkg\tA3"""

EXTERNAL_EXAMPLE = "year,flow,compartment,subcompartment,amount,unit\n" + "\n".join(
    f"{y},\"Copper, ion\",water,surface water,{0.0015 * 0.95 ** (y - 1):.6g},kg" for y in range(1, 11))
