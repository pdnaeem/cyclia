"""Regression tests for Cyclia 1.3.6 (database integrity and scientific reliability release).

Each test reproduces a defect found in the external audits of 1.3.5, so it fails on 1.3.5 and passes on 1.3.6."""
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc  # noqa: E402
import factormatch  # noqa: E402
import linking  # noqa: E402
from importers import ecospold2, jsonld, lcia, other_formats, tutorial  # noqa: E402
from store import Workspace  # noqa: E402
from test_engine import CO2, write_spold  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        calc.invalidate()

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def gwp_fossil(self):
        lcia.install_builtin(self.st)
        return [self.st.method_by_key(lcia.BUILTIN_FAMILY, "climate change: fossil", "GWP100")["id"]]

    def result(self, act_id, mids):
        m = self.st.save_model({"name": f"m{act_id}", "product": "x", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", act_id, 1)
        return calc.run(self.st, m, mids)["results"][0]["total"]


SP_HEAD = "{SimaPro 9.5.0}\n{CSV separator: Semicolon}\n{Decimal separator: .}\n\n"


def sp_process(product, co2, geo="CH", ident="", name="", inputs=""):
    s = "Process\n\n"
    if ident:
        s += f"Process identifier\n{ident}\n\n"
    if name:
        s += f"Process name\n{name}\n\n"
    s += f"Geography\n{geo}\n\nProducts\n{product};kg;1;100;not defined;Cat;\n\n"
    if inputs:
        s += f"Materials/fuels\n{inputs}\n\n"
    s += f"Emissions to air\nCarbon dioxide, fossil;;kg;{co2};Undefined;0;0;0;\n\nEnd\n\n"
    return s


# ---------------------------------------------------------------------------------------- importers: identity
class TestSimaProIdentity(Base):
    def _import(self, text):
        p = os.path.join(self.dir, "sp.csv")
        with open(p, "w") as fh:
            fh.write(SP_HEAD + text)
        return other_formats.import_simapro_csv(self.st, p, "SP")

    def test_two_routes_of_the_same_product_stay_separate(self):
        """Audit P0: two processes with the same product and location were merged into one dataset."""
        res = self._import(sp_process("Widget", 1.0, ident="ROUTE-A", name="Widget, route A")
                           + sp_process("Widget", 5.0, ident="ROUTE-B", name="Widget, route B"))
        self.assertEqual(res["activities"], 2)
        rows = self.st.q("SELECT id, key FROM activities ORDER BY id")
        self.assertEqual(len(rows), 2)
        mids = self.gwp_fossil()
        self.assertEqual(sorted(round(self.result(r["id"], mids), 9) for r in rows), [1.0, 5.0])

    def test_without_identifiers_kept_separate_and_reported(self):
        res = self._import(sp_process("Widget", 1.0) + sp_process("Widget", 5.0))
        self.assertEqual(len(self.st.q("SELECT id FROM activities")), 2)
        self.assertEqual(res["n_duplicates"], 1)
        self.assertTrue(any("kept as separate datasets" in w for w in res["warnings"]))
        mids = self.gwp_fossil()
        vals = sorted(round(self.result(r["id"], mids), 9) for r in self.st.q("SELECT id FROM activities"))
        self.assertEqual(vals, [1.0, 5.0])

    def test_input_of_an_ambiguous_product_is_not_guessed(self):
        """A consumer of 'Widget' with two producers is left unresolved with both candidates, not linked to the first."""
        res = self._import(sp_process("Widget", 1.0, ident="A") + sp_process("Widget", 5.0, ident="B")
                           + sp_process("Gadget", 0.0, ident="G", inputs="Widget;kg;2;Undefined;0;0;0;"))
        self.assertEqual(res["ambiguous_inputs"], 1)
        db = self.st.databases()[0]["id"]
        g = linking.groups(self.st, db)
        self.assertEqual((g[0]["product"], g[0]["reasons"], len(g[0]["candidates"])), ("Widget", "ambiguous", 2))
        self.assertEqual(self.st.one("SELECT COUNT(*) n FROM tech")["n"], 0)
        # the user chooses route B (a dataset of the same database), and the result follows
        b = self.st.one("SELECT id FROM activities WHERE key LIKE 'B|%'")["id"]
        sug = linking.suggest(self.st, db, "Widget", "kg", location="")
        self.assertTrue({s["id"] for s in sug if s["recorded_candidate"]} >= {b})
        linking.link(self.st, db, "Widget", "kg", b, location="")
        gadget = self.st.one("SELECT id FROM activities WHERE key LIKE 'G|%'")["id"]
        self.assertAlmostEqual(self.result(gadget, self.gwp_fossil()), 2 * 5.0)
        # auto-link never resolves an ambiguous group
        linking.unlink(self.st, db, "Widget", "kg", location="")
        self.assertEqual(linking.auto_link(self.st, db)["auto_linked"], 0)


# ---------------------------------------------------------------------------------------- importers: ecoSpold2
class TestEcoSpold2KeepsInputs(Base):
    def test_input_without_activity_link_is_kept_as_unresolved(self):
        """Audit P0: an intermediate input without activityLinkId disappeared from the inventory."""
        d = os.path.join(self.dir, "ei", "datasets")
        os.makedirs(d)
        write_spold(d, "A1", "P1", "steel production", "kg", 1, [], [(CO2, "Carbon dioxide, fossil", 2.0)])
        write_spold(d, "A2", "P2", "bolt production", "kg", 1, [("A1", "P1", 1.0), ("", "P1", 0.5)], [])
        res = ecospold2.import_folder(self.st, os.path.dirname(d), "ei", "3.11", "cut-off")
        self.assertEqual(res["inputs_without_link"], 1)
        db = self.st.databases()[0]["id"]
        row = self.st.one("SELECT product, amount, reason FROM unlinked WHERE db_id=?", (db,))
        self.assertEqual((row["product"], row["amount"], row["reason"]), ("P1", 0.5, "no supplier link in the dataset"))
        self.assertTrue(any("kept as unresolved" in w for w in res["warnings"]))
        # linked by the user to the steel of the same database: 1.5 kg steel in total
        steel = self.st.one("SELECT id FROM activities WHERE key LIKE 'A1_%'")["id"]
        linking.link(self.st, db, "P1", "kg", steel)
        bolt = self.st.one("SELECT id FROM activities WHERE key LIKE 'A2_%'")["id"]
        lcia.install_builtin(self.st)
        mid = self.st.method_by_key(lcia.BUILTIN_FAMILY, "climate change: fossil", "GWP100")["id"]
        self.assertAlmostEqual(self.result(bolt, [mid]), 1.5 * 2.0)


# ---------------------------------------------------------------------------------------- linking by location
class TestLinkingGeography(Base):
    def _db_with_electricity_inputs(self):
        tutorial.install(self.st)
        b = other_formats._Builder(self.st, "Imported", "test")
        for loc in ("FR", "DE", "PL"):
            ai = b.activity(f"use|{loc}", f"use {loc}", f"product {loc}", loc, "kg")
            b.input(ai, "electricity, medium voltage", "kWh", 1.0, location=loc)
        b.write(lambda *a: None)
        return self.st.one("SELECT id FROM databases WHERE name='Imported'")["id"]

    def test_locations_are_separate_groups_and_links(self):
        """Audit P1: inputs at FR, DE and PL were one group, so one click gave all three the same supplier."""
        db = self._db_with_electricity_inputs()
        g = linking.groups(self.st, db)
        self.assertEqual(sorted(x["location"] for x in g), ["DE", "FR", "PL"])
        elec = self.st.search_activities("electricity")[0]["id"]
        r = linking.link(self.st, db, "electricity, medium voltage", "kWh", elec, location="FR")
        self.assertEqual(r["linked"], 1)
        st = {x["location"]: bool(x["linked"]) for x in linking.groups(self.st, db)}
        self.assertEqual(st, {"FR": True, "DE": False, "PL": False})

    def test_auto_link_needs_one_supplier_at_the_location(self):
        db = self._db_with_electricity_inputs()
        r = linking.auto_link(self.st, db)
        # the tutorial has no electricity dataset at FR, DE or PL: nothing may be linked by guessing
        self.assertEqual(r["auto_linked"], 0)
        self.assertEqual(r["left_for_review"], 3)


# ---------------------------------------------------------------------------------------- JSON-LD providers
class TestJsonLdProviders(Base):
    def _zip(self, with_default):
        p = os.path.join(self.dir, f"db{int(with_default)}.zip")
        z = zipfile.ZipFile(p, "w")
        put = lambda pth, o: z.writestr(pth, json.dumps(o))
        put("unit_groups/ug.json", {"@id": "ug", "units": [{"@id": "kg", "name": "kg", "conversionFactor": 1, "isRefUnit": True}]})
        put("flow_properties/mass.json", {"@id": "mass", "unitGroup": {"@id": "ug"}})
        for fid, name, ft, cat in [("fs", "steel", "PRODUCT_FLOW", "P"), ("fb", "bolt", "PRODUCT_FLOW", "P"),
                                   ("fe", "Carbon dioxide, fossil", "ELEMENTARY_FLOW", "Elementary flows/Emission to air/unspecified")]:
            put(f"flows/{fid}.json", {"@id": fid, "name": name, "flowType": ft, "category": cat,
                                      "flowProperties": [{"flowProperty": {"@id": "mass"}, "conversionFactor": 1, "isRefFlowProperty": True}]})

        def ex(f, ft, amt, inp, ref=False, prov=None):
            e = {"flow": {"@id": f, "flowType": ft}, "amount": amt, "isInput": inp, "isQuantitativeReference": ref,
                 "unit": {"@id": "kg"}, "flowProperty": {"@id": "mass"}}
            if prov:
                e["defaultProvider"] = {"@id": prov}
            return e
        put("processes/s1.json", {"@id": "s1", "name": "steel, route 1", "exchanges": [
            ex("fs", "PRODUCT_FLOW", 1, False, True), ex("fe", "ELEMENTARY_FLOW", 1.0, False)]})
        put("processes/s2.json", {"@id": "s2", "name": "steel, route 2", "exchanges": [
            ex("fs", "PRODUCT_FLOW", 1, False, True), ex("fe", "ELEMENTARY_FLOW", 3.0, False)]})
        put("processes/b.json", {"@id": "b", "name": "bolt making", "exchanges": [
            ex("fb", "PRODUCT_FLOW", 1, False, True), ex("fs", "PRODUCT_FLOW", 1, True, prov="s2" if with_default else None)]})
        z.close()
        return p

    def test_several_producers_without_default_provider_stay_unresolved(self):
        """Audit P1: without a defaultProvider the first producer found was used."""
        res = jsonld.import_jsonld(self.st, self._zip(False), "J")
        self.assertEqual(res["ambiguous_inputs"], 1)
        u = self.st.one("SELECT reason, candidates FROM unlinked")
        self.assertEqual((u["reason"], len(json.loads(u["candidates"]))), ("ambiguous", 2))
        self.assertEqual(self.st.one("SELECT COUNT(*) n FROM tech")["n"], 0)

    def test_default_provider_is_used(self):
        res = jsonld.import_jsonld(self.st, self._zip(True), "J")
        self.assertEqual(res["ambiguous_inputs"], 0)
        b = self.st.search_activities("bolt")[0]["id"]
        mids = self.gwp_fossil()
        self.assertAlmostEqual(self.result(b, mids), 3.0)


# ---------------------------------------------------------------------------------------- factor matching verdict
class TestFactorMatchingVerdict(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)
        self.mid = [m["id"] for m in self.st.methods() if m["category"] == "climate change"][0]
        self.rows = self.st.q("SELECT f.uuid, f.name, f.compartment, f.subcompartment, f.unit, c.value FROM cfs c "
                              "JOIN flows f ON f.id=c.flow_id WHERE c.method_id=?", (self.mid,))

    def _ext(self, unit=None, extra=False, scale=1.0):
        fs = [{"uuid": r["uuid"], "name": r["name"], "comp": r["compartment"], "sub": r["subcompartment"],
               "unit": unit or r["unit"], "location": "", "value": r["value"] * scale} for r in self.rows]
        if extra:
            fs.append({"uuid": None, "name": "Not a flow in the library", "comp": "air", "sub": "", "unit": "kg",
                       "location": "", "value": 5.0})
        return [{"method": "", "category": "climate change", "unit": "", "factors": fs}]

    def test_identical_factors_pass(self):
        res = factormatch.compare(self.st, [self.mid], self._ext(), "test")
        self.assertTrue(res["passed"], res["open_items"])

    def test_unresolved_external_flow_is_not_a_pass(self):
        """Audit experiment A: identical factors plus one external flow the library cannot resolve gave PASS."""
        res = factormatch.compare(self.st, [self.mid], self._ext(extra=True), "test")
        self.assertFalse(res["passed"])
        self.assertTrue(any("match no flow" in x for x in res["open_items"]))

    def test_wrong_units_are_not_a_pass(self):
        """Audit experiment B: identical numbers with wrong units gave PASS."""
        res = factormatch.compare(self.st, [self.mid], self._ext(unit="MJ"), "test")
        c = res["categories"][0]
        self.assertFalse(res["passed"])
        self.assertEqual(c["same"], 0)
        self.assertGreater(c["unit_mismatch"], 0)

    def test_convertible_units_are_converted(self):
        """A factor per g is 1000 x smaller than per kg: converted, then identical."""
        res = factormatch.compare(self.st, [self.mid], self._ext(unit="g", scale=1e-3), "test")
        self.assertTrue(res["passed"], res["open_items"])
        self.assertGreater(res["categories"][0]["units_converted"], 0)

    def test_pairing_is_one_to_one(self):
        ms = [{"id": 1, "category": "climate change: fossil", "indicator": "GWP100"},
              {"id": 2, "category": "climate change: biogenic", "indicator": "GWP100"},
              {"id": 3, "category": "climate change", "indicator": "GWP100"}]
        ext = [{"category": "climate change", "factors": []}, {"category": "Climate change - Fossil", "factors": []}]
        pairs, unpaired = factormatch.pair_categories(ms, ext)
        got = {m["category"]: (e["category"] if e else None) for m, e, _ in pairs}
        self.assertEqual(got["climate change"], "climate change")
        self.assertEqual(got["climate change: fossil"], "Climate change - Fossil")
        self.assertIsNone(got["climate change: biogenic"])
        self.assertEqual(unpaired, [])


# ---------------------------------------------------------------------------------------- AWARE water balance
class TestAwareWater(Base):
    def test_classification(self):
        """Audit P0: evaporated water was treated as returned water and subtracted from consumption."""
        import regional
        self.assertEqual(regional._water_kind("Water, evaporated", "air/unspecified", "m3")[:2], ("evaporated", 0))
        self.assertEqual(regional._water_kind("Water", "water/ocean", "m3")[:2], ("to_sea", 0))
        self.assertEqual(regional._water_kind("Water", "soil/unspecified", "m3")[:2], ("to_soil", 0))
        self.assertEqual(regional._water_kind("Water", "water/surface water", "m3")[:2], ("returned", -1))
        self.assertEqual(regional._water_kind("Water, river", "natural resource/in water", "m3")[:2], ("withdrawal", 1))
        self.assertEqual(regional._water_kind("Water", "water/unspecified", "kg")[2], 0.001)

    def test_consumption_of_a_model(self):
        """10 m3 withdrawn, 6 returned to a river, 3 evaporated, 1 to the sea: consumption 4 m3 (not 10 - 6 - 3 - 1 = 0)."""
        import regional
        st = self.st
        fl = {n: st.add_flow(f"w-{n}", *spec) for n, spec in {
            "in": ("Water, river", "natural resource", "in water", "m3"),
            "ret": ("Water", "water", "surface water", "m3"),
            "evap": ("Water, evaporated", "air", "unspecified", "m3"),
            "sea": ("Water", "water", "ocean", "m3")}.items()}
        st.conn.commit()
        tutorial.install(st)
        regional.import_factors(st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,30\nFR,8,5,7\n")
        m = st.save_model({"name": "w", "product": "w", "unit": "kg", "amount": 1,
                           "scope": {"aware_location": "FR", "aware_use": "non_agri"}})
        for k, a in (("in", 10), ("ret", 6), ("evap", 3), ("sea", 1)):
            st.add_input(m, "flow", fl[k], a)
        r = regional.aware(st, m)
        self.assertAlmostEqual(r["consumption_m3"], 4.0)
        self.assertAlmostEqual(r["total"], 4.0 * 5)        # FR non-agricultural factor, found (1.3.5 used unknown)
        b = r["water_balance_m3"]
        self.assertEqual({k: round(v, 9) for k, v in b.items()},
                         {"withdrawal": 10.0, "returned": 6.0, "evaporated": 3.0, "to_sea": 1.0, "to_soil": 0.0})

    def test_old_non_agri_keys_still_found(self):
        import regional
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,30\n")
        self.st.x("UPDATE native_factors SET key='non-agri' WHERE key='non_agri'")   # as stored by 1.3.5
        self.assertEqual(regional._use_key("non-agri"), "non_agri")
        tutorial.install(self.st)
        m = self.st.save_model({"name": "w", "product": "w", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("tap water")[0]["id"], 100)
        r = regional.aware(self.st, m)
        self.assertTrue(all(x["factor"] == 20.0 for x in r["top"]))


# ---------------------------------------------------------------------------------------- social LCA coverage
class TestSocialCoverage(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)

    def _model(self):
        m = self.st.save_model({"name": "c", "product": "c", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("cement")[0]["id"], 2)
        return m

    def test_coverage_is_not_100_percent_when_processes_lack_data(self):
        """Audit P1: with 1 of 7 processes covered, Cyclia reported 100 % coverage."""
        import slca
        slca.import_data(self.st, "match,location,worker_hours,stakeholder,indicator,risk\n"
                                  "cement production,,0.01,workers,Fair salary,high\n")
        r = slca.assess(self.st, self._model())
        self.assertGreater(r["n_processes"], 1)
        self.assertEqual(r["n_with_data"], 1)
        self.assertAlmostEqual(r["process_coverage"], 1 / r["n_processes"])
        self.assertFalse(r["complete"])
        self.assertIsNone(r["coverage_hours"])                 # cannot be known without a default row
        self.assertIsNone(r["indicators"][0]["coverage"])

    def test_default_row_estimates_hours_and_coverage(self):
        import slca
        slca.import_data(self.st, "match,location,worker_hours,stakeholder,indicator,risk\n"
                                  "cement production,,0.01,workers,Fair salary,high\n"
                                  "*,,0.002,workers,Fair salary,medium\n")
        r = slca.assess(self.st, self._model())
        est = sum(x["estimated_hours"] for x in r["processes_without_data"])
        self.assertAlmostEqual(r["worker_hours_estimated"], est)
        self.assertAlmostEqual(r["coverage_hours"], r["worker_hours"] / (r["worker_hours"] + est))
        self.assertLess(r["coverage_hours"], 1.0)

    def test_avoided_products_are_not_added_or_netted(self):
        import slca
        slca.import_data(self.st, "match,location,worker_hours,stakeholder,indicator,risk\n"
                                  "cement production,,0.01,workers,Fair salary,high\n"
                                  "electricity production,,0.001,workers,Fair salary,low\n"
                                  "steel,,0.05,workers,Fair salary,high\n")
        m = self._model()
        base = slca.assess(self.st, m)["worker_hours"]
        self.st.add_input(m, "activity", self.st.search_activities("steel")[0]["id"], 1, avoided=True)
        r = slca.assess(self.st, m)
        self.assertGreater(r["worker_hours_avoided"], 0)
        # not reduced by the credit, not increased by it, also for electricity used by both cement and steel
        self.assertAlmostEqual(r["worker_hours"], base, places=12)


# ---------------------------------------------------------------------------------------- MFA circularity
class TestMfaCircularity(unittest.TestCase):
    def test_recirculated_share_uses_the_production_input(self):
        """Audit P1: an unrelated external inflow diluted the recirculated inflow share (20 % instead of 33.3 %)."""
        import mfa
        d = {"years": [2020, 2021], "production_process": "prod", "recycling_processes": ["rec"],
             "processes": [{"id": "prod"}, {"id": "rec"}, {"id": "other"},
                           {"id": "use", "stock": True, "lifetime": {"type": "fixed", "mean": 50}},
                           {"id": "out", "sink": True}],
             "inflows": [{"to": "prod", "values": {"2020": 100}}, {"to": "rec", "values": {"2020": 50}},
                         {"to": "other", "values": {"2020": 100}}],
             "flows": [{"from": "rec", "to": "prod", "share": 1}, {"from": "prod", "to": "use", "share": 1},
                       {"from": "use", "to": "out", "share": 1}, {"from": "other", "to": "out", "share": 1}]}
        r = mfa.run(d)
        row = r["rows"][0]
        self.assertTrue(r["mass_balance_ok"])
        self.assertAlmostEqual(row["recirculated_inflow_share"], 50 / 150)
        self.assertAlmostEqual(row["recycled_content"], 50 / 150)
        self.assertAlmostEqual(row["virgin_inflow_to_production"], 100)

    def test_mci_comes_from_the_mfa(self):
        import mfa
        r = mfa.run(mfa.EXAMPLE)
        late = r["rows"][-1]
        self.assertIsNotNone(late["mci"])
        self.assertTrue(0.1 <= late["mci"] <= 1.0)


# ---------------------------------------------------------------------------------------- LANCA units
class TestLancaUnits(Base):
    def test_factor_units_are_validated_and_converted(self):
        import regional
        r = regional.import_factors(self.st, "LANCA", "indicator,kind,land_use,location,value,unit\n"
                                    "erosion resistance,occupation,arable land,GLO,2,kg/(m2*a)\n"
                                    "erosion resistance,transformation_to,arable land,GLO,5,kg/(m2*a)\n"
                                    "erosion resistance,occupation,forest,GLO,30000,kg/(ha*a)\n", source="test set v1")
        self.assertEqual((r["factors"], r["n_rejected"]), (2, 1))
        self.assertIn("transformation factor must be per m2", r["rejected"][0]["reason"])
        v = self.st.one("SELECT value FROM native_factors WHERE key='occupation|forest'")["value"]
        self.assertAlmostEqual(v, 3.0)                       # 30000 per ha*a = 3 per m2*a

    def test_inventory_in_hectares_is_converted(self):
        """1 ha*a of arable land with a factor of 2 per m2*a is 20000, not 2."""
        import regional
        regional.import_factors(self.st, "LANCA", "indicator,kind,land_use,location,value,unit\n"
                                "erosion resistance,occupation,arable land,GLO,2,kg/(m2*a)\n", source="test")
        fid = self.st.add_flow("occ-ha", "Occupation, arable land", "natural resource", "land", "ha*a")
        self.st.conn.commit()
        tutorial.install(self.st)
        m = self.st.save_model({"name": "f", "product": "f", "unit": "kg", "amount": 1})
        self.st.add_input(m, "flow", fid, 1)
        er = next(x for x in regional.lanca(self.st, m)["indicators"] if x["indicator"] == "erosion resistance")
        self.assertAlmostEqual(er["total"], 20000.0)


# ---------------------------------------------------------------------------------------- EPD additional indicators
class TestEpdAdditional(unittest.TestCase):
    EF31 = [("human toxicity: carcinogenic, inorganics", "CTUh"), ("human toxicity: carcinogenic", "CTUh"),
            ("human toxicity: non-carcinogenic, organics", "CTUh"), ("human toxicity: non-carcinogenic", "CTUh"),
            ("ecotoxicity: freshwater, organics", "CTUe"), ("ecotoxicity: freshwater", "CTUe"),
            ("ionising radiation: human health", "kBq U235-Eq"), ("particulate matter formation", "disease incidence"),
            ("land use", "dimensionless")]

    def test_ef31_names_match_the_total_not_the_sub_category(self):
        """EF 3.1 (ecoinvent) names toxicity 'carcinogenic'; 1.3.5 only knew 'cancer', and sub-categories could win."""
        import epd_profiles
        res = [{"category": c, "indicator": c, "unit": u} for c, u in self.EF31]
        found = epd_profiles.match_additional(res)
        self.assertEqual(res[found["HTP-c"]]["category"], "human toxicity: carcinogenic")
        self.assertEqual(res[found["HTP-nc"]]["category"], "human toxicity: non-carcinogenic")
        self.assertEqual(res[found["ETP-fw"]]["category"], "ecotoxicity: freshwater")
        self.assertEqual(set(found), {"HTP-c", "HTP-nc", "ETP-fw", "IRP", "PM", "SQP"})

    def test_units_of_additional_indicators(self):
        import epd_profiles
        import standards
        for a, toks in epd_profiles.ADDITIONAL_UNITS.items():
            self.assertFalse(standards.unit_ok("kg CO2-Eq", toks) and a != "GWP-GHG", a)
        self.assertTrue(standards.unit_ok("kBq U235-Eq", epd_profiles.ADDITIONAL_UNITS["IRP"]))
        self.assertTrue(standards.unit_ok("dimensionless", epd_profiles.ADDITIONAL_UNITS["SQP"]))


# ---------------------------------------------------------------------------------------- land use benchmark
class TestLandUseUncharacterised(unittest.TestCase):
    def test_implied_factor_of_a_flow_without_factor_is_recovered(self):
        """Benchmark file of 1.3.4 (user's ecoinvent 3.x, EF 3.1): Cyclia up to 14 % lower in land use, largest for
        datasets with hydro reservoirs and offshore extraction, whose land flows (lake, artificial; seabed) have no
        factor in Cyclia. The reconciliation must be able to show that such flows explain the gap."""
        import numpy as np
        import trust
        names = ["Occupation, arable", "Occupation, lake, artificial", "Transformation, to seabed, drilling and mining",
                 "Carbon dioxide"]

        class St:
            def flow(self, fid):
                return {"name": names[fid], "compartment": "natural resource", "subcompartment": "land",
                        "unit": "m2*year"}

        class MC:
            flow_ids = np.arange(4)

        class Mx:
            C = np.array([[1.0, 0.0, 0.0, 0.0]])       # Cyclia: no factor for the lake and the seabed flow
        rng = np.random.default_rng(3)
        out, G = [], {}
        for d in range(15):
            g = np.array([rng.uniform(1, 10), rng.uniform(0, 0.5), rng.uniform(0, 0.01), 1.0])
            G[d] = g
            cy = float(Mx.C[0] @ g)
            ref = cy + 12.0 * g[1] + 300.0 * g[2]        # ecoinvent characterises both
            out.append({"category": "land use", "indicator": "soil quality index", "reference": ref, "cyclia": cy,
                        "act_id": d, "note": "", "deviation_percent": (cy - ref) / ref * 100})
        res = trust.land_use_reconciliation(St(), MC(), Mx(), [{"method": {"category": "land use",
                                                                      "indicator": "soil quality index"}}], out, G)[0]
        imp = {x["flow"]: x["implied_factor"] for x in res["implied_factors_uncharacterised"]}
        self.assertAlmostEqual(imp["Occupation, lake, artificial"], 12.0, places=6)
        self.assertAlmostEqual(imp["Transformation, to seabed, drilling and mining"], 300.0, places=4)
        self.assertGreater(res["explained_by_uncharacterised"], 0.999)


class TestLandCoverageCheck(Base):
    def test_land_flow_without_factor_is_reported(self):
        tutorial.install(self.st)
        lake = self.st.add_flow("lake-1", "Occupation, lake, artificial", "natural resource", "land", "m2*year")
        self.st.conn.commit()
        m = self.st.save_model({"name": "h", "product": "h", "unit": "kWh", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("wheat")[0]["id"], 1)
        self.st.add_input(m, "flow", lake, 1.82)                 # as much lake as the wheat's arable land
        mids = [x["id"] for x in self.st.methods() if x["category"] == "land use"]
        r = calc.run(self.st, m, mids)
        lc = next(x for x in r["land_coverage"] if x["kind"] == "occupation")
        self.assertAlmostEqual(lc["share_without_factor"], 0.5, places=6)
        self.assertEqual(lc["flows_without_factor"][0]["name"], "Occupation, lake, artificial")
        txt = " ".join(c["message"] for c in r["checks"])
        self.assertIn("50.0 % of the land occupation in the inventory has no factor", txt)


class TestBenchmarkVerdict(unittest.TestCase):
    def _summary(self, land_devs):
        import numpy as np
        import trust

        class St:
            def one(self, q, *a):
                return {"n": 0}

        class MC:
            b_rows = np.array([0])

        class Mx:
            C = np.ones((2, 1))
        mcols = [{"id": 1, "method": {"category": "climate change", "indicator": "GWP", "family": "EF", "unit": "kg"}},
                 {"id": 2, "method": {"category": "land use", "indicator": "SQI", "family": "EF", "unit": "-"}}]
        out = [{"category": "climate change", "indicator": "GWP", "deviation_percent": 0.0001, "group": "g"} for _ in range(96)]
        out += [{"category": "land use", "indicator": "SQI", "deviation_percent": d, "group": "g"} for d in land_devs]
        return trust._bench_summary(St(), MC(), Mx(), mcols, out, 100, 100, 100, ["g"])

    def test_one_weak_category_is_named_in_the_verdict(self):
        """1.3.4 said 'Validated: 96.2 %' while land use was up to 14 % off (only 30 % within 0.1 %)."""
        r = self._summary([-14.0, -9.0, -0.4, -0.3])
        self.assertTrue(r["verdict"].startswith("Validated except 1 category"), r["verdict"])
        self.assertIn("land use", r["verdict"])

    def test_all_good_is_validated(self):
        r = self._summary([0.0001] * 4)
        self.assertTrue(r["verdict"].startswith("Validated:"), r["verdict"])


if __name__ == "__main__":
    unittest.main()
