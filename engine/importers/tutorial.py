"""Small built-in tutorial database so a new user can learn the workflow without a licence.

The process data below are ILLUSTRATIVE ONLY: rounded, simplified numbers meant to teach the
software, not to be cited. The GWP100 factors are the IPCC AR6 (2021) values; the acidification
factors are CML-IA baseline values. Use a licensed or published database for real studies.
"""
import uuid

NS = uuid.UUID("6f1c2d6e-3c8a-4b8e-9a51-1b2f0f5d7a10")

FLOWS = {
    "co2": ("Carbon dioxide, fossil", "air", "unspecified", "kg"),
    "co2bio": ("Carbon dioxide, non-fossil", "air", "unspecified", "kg"),
    "co2air": ("Carbon dioxide, in air", "natural resource", "in air", "kg"),
    "ch4": ("Methane, fossil", "air", "unspecified", "kg"),
    "ch4bio": ("Methane, non-fossil", "air", "unspecified", "kg"),
    "n2o": ("Dinitrogen monoxide", "air", "unspecified", "kg"),
    "so2": ("Sulfur dioxide", "air", "unspecified", "kg"),
    "nox": ("Nitrogen oxides", "air", "unspecified", "kg"),
    "nh3": ("Ammonia", "air", "unspecified", "kg"),
    "land": ("Occupation, arable land", "natural resource", "land", "m2*year"),
    "water": ("Water, well, in ground", "natural resource", "in water", "m3"),
}

# key: (name, product, unit, {input_key: amount}, {flow_key: amount})
PROCESSES = {
    "elec": ("electricity production, grid mix (tutorial)", "electricity, medium voltage", "kWh",
             {}, {"co2": 0.45, "ch4": 0.0010, "so2": 0.0006, "nox": 0.0005, "water": 0.002}),
    "gas": ("heat production, natural gas boiler (tutorial)", "heat, natural gas", "MJ",
            {}, {"co2": 0.056, "ch4": 0.0001, "nox": 0.00004}),
    "diesel": ("diesel, burned in machine (tutorial)", "diesel, burned", "MJ",
               {}, {"co2": 0.074, "nox": 0.0009, "so2": 0.00002, "n2o": 0.000003}),
    "lorry": ("transport, freight lorry 16-32t (tutorial)", "transport, freight, lorry", "t*km",
              {"diesel": 1.2}, {}),
    "limestone": ("limestone quarrying (tutorial)", "limestone, crushed", "kg",
                  {"diesel": 0.03, "elec": 0.005}, {}),
    "gravel": ("gravel and sand quarrying (tutorial)", "gravel and sand", "kg",
               {"diesel": 0.02, "elec": 0.002}, {}),
    "water_tap": ("tap water production (tutorial)", "tap water", "kg",
                  {"elec": 0.0005}, {"water": 0.001}),
    "clinker": ("clinker production (tutorial)", "clinker", "kg",
                {"limestone": 1.25, "gas": 3.3, "elec": 0.03}, {"co2": 0.53, "nox": 0.0012, "so2": 0.0002}),
    "cement": ("cement production, Portland (tutorial)", "cement, Portland", "kg",
               {"clinker": 0.9, "elec": 0.05, "lorry": 0.05}, {}),
    "concrete": ("concrete production, ready-mix (tutorial)", "concrete, normal strength", "m3",
                 {"cement": 300, "gravel": 1900, "water_tap": 180, "elec": 4, "lorry": 95}, {}),
    "steel": ("reinforcing steel production (tutorial)", "reinforcing steel", "kg",
              {"elec": 0.6, "gas": 12, "lorry": 0.1}, {"co2": 1.1, "so2": 0.002, "nox": 0.0015}),
    "lime": ("hydrated lime production (tutorial)", "lime, hydrated", "kg",
             {"limestone": 1.35, "gas": 4.5, "elec": 0.04}, {"co2": 0.75, "nox": 0.0008}),
    "hemp": ("hemp shiv production, dried (tutorial)", "hemp shiv", "kg",
             {"diesel": 0.6, "elec": 0.08, "lorry": 0.08},
             {"n2o": 0.002, "nh3": 0.003, "land": 1.5, "co2air": 1.6}),
    "hempcrete": ("hempcrete block production (tutorial)", "hempcrete block", "kg",
                  {"hemp": 0.35, "lime": 0.45, "water_tap": 0.4, "elec": 0.05}, {}),
    "timber": ("sawn timber production, softwood (tutorial)", "sawnwood, softwood", "m3",
               {"diesel": 350, "elec": 110, "lorry": 50}, {"land": 200, "co2air": 750}),
    "insul_mw": ("mineral wool production (tutorial)", "mineral wool", "kg",
                 {"elec": 1.6, "gas": 9, "lorry": 0.1}, {"co2": 0.4, "nox": 0.002}),
    # agriculture and food
    "fert_n": ("nitrogen fertiliser production, as N (tutorial)", "nitrogen fertiliser, as N", "kg",
               {"gas": 35, "elec": 0.5, "lorry": 0.2}, {"co2": 2.0, "n2o": 0.006, "nh3": 0.002}),
    "wheat": ("wheat grain production (tutorial)", "wheat grain", "kg",
              {"fert_n": 0.022, "diesel": 0.6, "lorry": 0.02},
              {"n2o": 0.00035, "nh3": 0.0025, "land": 1.4, "co2air": 1.5}),
    "flour": ("wheat flour milling (tutorial)", "wheat flour", "kg",
              {"wheat": 1.3, "elec": 0.1, "lorry": 0.05}, {}),
    "bread": ("bread baking, industrial (tutorial)", "bread", "kg",
              {"flour": 0.65, "water_tap": 0.4, "gas": 2.5, "elec": 0.3}, {}),
    # textiles
    "cotton": ("cotton fibre production, irrigated (tutorial)", "cotton fibre", "kg",
               {"fert_n": 0.12, "diesel": 4, "elec": 0.8},
               {"n2o": 0.0019, "nh3": 0.01, "land": 6, "water": 2.0, "co2air": 1.6}),
    "yarn": ("cotton yarn spinning (tutorial)", "cotton yarn", "kg",
             {"cotton": 1.1, "elec": 4, "lorry": 0.5}, {}),
    "fabric": ("cotton fabric weaving and dyeing (tutorial)", "cotton fabric, dyed", "kg",
               {"yarn": 1.05, "elec": 6, "gas": 30, "water_tap": 100}, {}),
    "tshirt": ("T-shirt sewing (tutorial)", "T-shirt, cotton", "item",
               {"fabric": 0.2, "elec": 0.3, "lorry": 1.5}, {}),
    # plastics and chemicals
    "pe": ("polyethylene production, granulate (tutorial)", "polyethylene, granulate", "kg",
           {"gas": 30, "elec": 1.5, "lorry": 0.1}, {"co2": 1.2, "nox": 0.001, "so2": 0.0008}),
    "bottle": ("plastic bottle blow moulding (tutorial)", "plastic bottle, 1 l", "item",
               {"pe": 0.03, "elec": 0.06, "lorry": 0.01}, {}),
    # energy and water
    "pv_panel": ("photovoltaic panel production, multi-Si (tutorial)", "photovoltaic panel", "m2",
                 {"elec": 300, "gas": 200, "lorry": 2}, {"co2": 15, "so2": 0.03, "nox": 0.02}),
    "pv_elec": ("electricity production, photovoltaic rooftop (tutorial)", "electricity, from photovoltaic", "kWh",
                {"pv_panel": 0.00017, "lorry": 0.0002}, {}),
    "elec_lv": ("electricity, low voltage, distribution (tutorial)", "electricity, low voltage", "kWh",
                {"elec": 1.08}, {}),
    "mswi": ("treatment of municipal solid waste, incineration (tutorial)", "municipal solid waste, incinerated", "kg",
             {"lorry": 0.03, "elec": 0.02}, {"co2": 0.45, "co2bio": 0.4, "nox": 0.0009, "so2": 0.0001}),
    "landfill": ("treatment of inert waste, landfill (tutorial)", "inert waste, landfilled", "kg",
                 {"diesel": 0.02, "lorry": 0.02}, {}),
    "pet": ("polyethylene terephthalate production, granulate (tutorial)", "polyethylene terephthalate, granulate", "kg",
            {"gas": 35, "elec": 1.8, "lorry": 0.1}, {"co2": 1.5, "nox": 0.0012, "so2": 0.001}),
    "wwt": ("wastewater treatment, municipal (tutorial)", "wastewater treatment, municipal", "m3",
            {"elec": 0.5, "lorry": 0.05}, {"n2o": 0.00005, "ch4bio": 0.0006, "co2bio": 0.1}),
}

METHODS = [
    ("Tutorial: IPCC 2021 GWP100", "climate change", "global warming potential (GWP100)", "kg CO2-eq",
     {"co2": 1.0, "co2bio": 0.0, "ch4": 29.8, "ch4bio": 27.0, "n2o": 273.0}),
    ("Tutorial: CML-IA baseline", "acidification", "acidification potential (average Europe)", "kg SO2-eq",
     {"so2": 1.2, "nox": 0.5, "nh3": 1.6}),
    ("Tutorial: inventory indicators", "land use", "land occupation", "m2*year", {"land": 1.0}),
    ("Tutorial: inventory indicators", "water use", "water withdrawal", "m3", {"water": 1.0}),
]


def install(store, progress=lambda *a: None):
    name = "Tutorial database (illustrative)"
    if store.one("SELECT id FROM databases WHERE source='built-in'"):
        raise ValueError("The tutorial database is already in this project.")
    db_id = store.create_database(name, "built-in", "1.0", "", "Illustrative data for learning only. Do not cite.")
    with store.lock:
        c = store.conn
        flow_ids = {}
        for k, (fname, comp, sub, unit) in FLOWS.items():
            flow_ids[k] = store.add_flow(str(uuid.uuid5(NS, "flow-" + k)), fname, comp, sub, unit)
        act_ids = {}
        for k, (aname, prod, unit, _, _) in PROCESSES.items():
            cur = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) "
                            "VALUES(?,?,?,?,?,?,1.0)", (db_id, k, aname, prod, "GLO", unit))
            act_ids[k] = cur.lastrowid
        for k, (_, _, _, inputs, emissions) in PROCESSES.items():
            # illustrative lognormal uncertainty so background Monte Carlo can be tried out
            for ik, amt in inputs.items():
                c.execute("INSERT INTO tech(output_id,input_id,amount,utype,p1) VALUES(?,?,?,1,?)",
                          (act_ids[k], act_ids[ik], amt, 0.1))
            for fk, amt in emissions.items():
                c.execute("INSERT INTO bio(activity_id,flow_id,amount,utype,p1) VALUES(?,?,?,1,?)",
                          (act_ids[k], flow_ids[fk], amt, 0.05 if fk in ("co2", "co2bio") else 0.3))
        c.commit()
    from importers import lcia
    store.finish_database(db_id)
    for fam, cat, ind, unit, cfs in METHODS:
        mid = store.get_or_create_method(fam, cat, ind, unit, "built-in tutorial")
        store.x("DELETE FROM cf_raw WHERE method_id=?", (mid,))
        lcia.store_raw(store, mid, [(FLOWS[fk][0], FLOWS[fk][1], FLOWS[fk][2], "", None, v) for fk, v in cfs.items()])
    lcia.rematch_all(store)
    progress(100, "Tutorial database installed")
    return {"database": name, "activities": len(PROCESSES)}
