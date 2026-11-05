"""Acceptance tests for Cyclia 1.3.5: factor matching validation, EPD programme profiles, EF dataset DQR, marginal
supplier guidance, LCC cost types and replacements, AWARE and LANCA, social LCA and dynamic MFA."""
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
import epd_profiles  # noqa: E402
import factormatch  # noqa: E402
import mfa  # noqa: E402
import regional  # noqa: E402
import slca  # noqa: E402
import standards  # noqa: E402
from importers import other_formats, tutorial  # noqa: E402
from store import Workspace  # noqa: E402


def gwp(st):
    return [m["id"] for m in st.methods() if m["category"] == "climate change"]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        calc.invalidate()
        tutorial.install(self.st)
        self.find = lambda q: self.st.search_activities(q)[0]["id"]

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def model(self, name="M", unit="kg", amount=1, product="p", **scope):
        sc = {"goal": "g", "boundary": "cradle-to-gate", **scope}
        return self.st.save_model({"name": name, "product": product, "unit": unit, "amount": amount, "scope": sc})

    def own_factors(self, mid, change=None, drop=None):
        return self.st.q("SELECT f.uuid, f.name, f.compartment, f.subcompartment, f.unit, c.value FROM cfs c "
                         "JOIN flows f ON f.id=c.flow_id WHERE c.method_id=?", (mid,))


# ---------------------------------------------------------------------------------------------- factor matching
class TestFactorMatching(Base):
    def _csv(self, mid, path, mod):
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["category", "flow_uuid", "flow_name", "compartment", "subcompartment", "unit", "cf"])
            for r in self.own_factors(mid):
                v = mod(r)
                if v is not None:
                    w.writerow(["climate change GWP100", r["uuid"], r["name"], r["compartment"], r["subcompartment"], r["unit"], v])
            w.writerow(["climate change GWP100", "", "Not a flow in the library", "air", "", "kg", 5])

    def test_csv_flow_by_flow_and_effect(self):
        mid = gwp(self.st)[0]
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        p = os.path.join(self.dir, "ext.csv")
        self._csv(mid, p, lambda r: None if "dinitrogen" in r["name"].lower() else r["value"] * (1.1 if r["name"].startswith("Methane") else 1))
        ext, kind = factormatch.read_external(p)
        res = factormatch.compare(self.st, [mid], ext, kind, [m])
        c = res["categories"][0]
        self.assertEqual(c["external_category"], "climate change GWP100")
        self.assertEqual((c["different"], c["only_cyclia"], c["unresolved"]), (2, 1, 1))
        self.assertFalse(res["passed"])
        eff = c["models"][0]
        g = factormatch.model_inventories(self.st, [m])[m]["g"]
        cy = {r["flow_id"]: r["value"] for r in self.st.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (mid,))}
        names = {r["id"]: r["name"] for r in self.st.q("SELECT id, name FROM flows")}
        expected = sum(v * cy.get(f, 0) * (0.1 if names[f].startswith("Methane") else (-1 if "dinitrogen" in names[f].lower() else 0))
                       for f, v in g.items())
        self.assertAlmostEqual(eff["with_external_factors"] - eff["cyclia"], expected, places=10)
        self.assertAlmostEqual(eff["cyclia"], calc.run(self.st, m, [mid])["results"][0]["total"], places=9)
        x = os.path.join(self.dir, "fm.xlsx")
        factormatch.to_excel(x, res, "t")
        from openpyxl import load_workbook
        self.assertTrue({"Summary", "Flow by flow", "Effect on models"} <= set(load_workbook(x).sheetnames))

    def test_identical_factors_pass_and_external_results_split(self):
        mid = gwp(self.st)[0]
        m = self.model("Wall")
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        p = os.path.join(self.dir, "same.csv")
        self._csv(mid, p, lambda r: r["value"])
        ext, kind = factormatch.read_external(p)
        tot = calc.run(self.st, m, [mid])["results"][0]["total"]
        rp = os.path.join(self.dir, "res.csv")
        with open(rp, "w") as fh:
            fh.write(f"model,category,value\nWall,climate change GWP100,{tot * 1.02}\n")
        res = factormatch.compare(self.st, [mid], ext, kind, [m], factormatch.read_external_results(rp))
        c = res["categories"][0]
        self.assertTrue(res["passed"] or c["unresolved"] == 1)
        self.assertEqual(c["different"] + c["only_cyclia"] + c["only_external"], 0)
        e = c["models"][0]
        self.assertAlmostEqual(e["explained_by_factors"], 0.0, places=12)
        self.assertAlmostEqual(e["other_differences"], tot * 0.02, places=9)

    def test_shipped_demonstration_files(self):
        """docs/examples/factor_matching_demo_*.csv against the demo database: the expected outcome written in
        docs/ACCEPTANCE_1.3.5.md."""
        from importers import demo
        ws = Workspace(os.path.join(self.dir, "demo"))  # the demo database alone, as in the app's feature demo
        self.addCleanup(ws.close_all)
        self.st = ws.create("Demo")
        demo.install_database(self.st)
        demo.build_project(self.st)
        ex = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "examples")
        ext, kind = factormatch.read_external(os.path.join(ex, "factor_matching_demo_factors.csv"))
        results = factormatch.read_external_results(os.path.join(ex, "factor_matching_demo_results.csv"))
        self.assertEqual(len(results), 4)
        cc, ac = demo.method_id(self.st, "climate change"), demo.method_id(self.st, "acidification")
        models = [x["id"] for x in self.st.models()]
        res = factormatch.compare(self.st, [cc, ac], ext, kind, models, results)
        c, a = res["categories"]
        self.assertEqual((c["same"], c["different"], c["only_cyclia"], c["unresolved"]), (1, 1, 1, 1))
        self.assertEqual((a["same"], a["different"], a["only_cyclia"]), (3, 0, 0))
        self.assertEqual({f["flow"]: f["status"] for f in res["flows"]},
                         {"Methane, fossil": "different", "Dinitrogen monoxide": "only_cyclia"})
        self.assertFalse(res["passed"])
        wall = next(x for x in c["models"] if x["model"] == "Concrete wall (demo)")
        self.assertAlmostEqual(wall["other_differences"], 0.0, delta=1e-6 * abs(wall["cyclia"]))
        wall_a = next(x for x in a["models"] if x["model"] == "Concrete wall (demo)")
        self.assertAlmostEqual(wall_a["explained_by_factors"], 0.0, places=12)
        self.assertAlmostEqual(wall_a["other_differences"] / wall_a["cyclia"], 0.02, places=6)

    def test_openlca_jsonld(self):
        mid = gwp(self.st)[0]
        rows = self.own_factors(mid)
        z = os.path.join(self.dir, "m.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("lcia_methods/m.json", json.dumps({"@type": "ImpactMethod", "@id": "m", "name": "Test method",
                                                          "impactCategories": [{"@id": "c"}]}))
            zf.writestr("lcia_categories/c.json", json.dumps({"@type": "ImpactCategory", "@id": "c", "name": "Climate change",
                        "refUnit": "kg CO2 eq", "impactFactors": [{"flow": {"@id": r["uuid"], "name": r["name"]},
                                                                    "value": r["value"] * 2} for r in rows]}))
        ext, kind = factormatch.read_external(z)
        self.assertEqual(kind, "openLCA JSON-LD")
        res = factormatch.compare(self.st, [mid], ext, kind, [])
        c = res["categories"][0]
        self.assertEqual(c["external_category"], "Climate change")
        self.assertEqual(c["different"], len([r for r in rows if r["value"]]))


# ---------------------------------------------------------------------------------------------- EPD profiles
class TestEpdProfiles(Base):
    def _model(self, profile, fields=None):
        m = self.model("Panel", unit="m2", stage_system="EN 15804 (construction products)",
                       epd={"profile": profile, "fields": fields or {}, "issued": "2026-11-01", "valid_until": "2031-10-31"})
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, stage="A1-A3")
        return m

    def test_profiles_render_with_their_structure(self):
        from docx import Document
        expect = {"generic": "Environmental Product Declaration (EPD)", "international-epd-system": "The International EPD System",
                  "ibu": "2. Product", "inies-fdes": "Fiche de Déclaration Environnementale et Sanitaire (FDES)"}
        for pid, needle in expect.items():
            m = self._model(pid)
            r = calc.run(self.st, m, gwp(self.st))
            p = os.path.join(self.dir, f"{pid}.docx")
            standards.epd_word(p, self.st.model(m), r, self.st.databases(), "t")
            d = Document(p)
            text = "\n".join(x.text for x in d.paragraphs) + " ".join(c.text for t in d.tables for row in t.rows for c in row.cells)
            self.assertIn(needle, text, pid)
            self.assertIn("NOT READY FOR SUBMISSION", text)
            if pid != "generic":
                self.assertIn("Not approved", text) if pid != "inies-fdes" else self.assertIn("Non approuvé", text)

    def test_required_fields_and_indicators(self):
        m = self._model("international-epd-system")
        r = calc.run(self.st, m, gwp(self.st))
        txt = " ".join(i["text"] for i in standards.epd_checklist(self.st.model(m), r)["items"] if not i["ok"])
        self.assertIn("EPD registration number", txt)
        self.assertIn("GWP-GHG", txt)
        prof = epd_profiles.get("international-epd-system")
        full = {f["key"]: "x" for f in prof["fields"]}
        m2 = self._model("international-epd-system", full)
        txt2 = " ".join(i["text"] for i in standards.epd_checklist(self.st.model(m2), r)["items"] if not i["ok"])
        self.assertNotIn("required information given (missing", txt2)
        m3 = self.model("Long", stage_system="EN 15804 (construction products)",
                        epd={"profile": "ibu", "issued": "2026-01-01", "valid_until": "2033-01-01"})
        self.st.add_input(m3, "activity", self.find("concrete"), 0.2, stage="A1-A3")
        txt3 = " ".join(i["text"] for i in standards.epd_checklist(self.st.model(m3), calc.run(self.st, m3, gwp(self.st)))["items"] if not i["ok"])
        self.assertIn("Validity at most 5 years", txt3)

    def test_custom_profile_roundtrip(self):
        d = os.path.join(self.dir, "profiles")
        p = dict(epd_profiles.get("generic"), id="my-programme", name="My programme",
                 statements=["Our statement."], fields=[{"key": "reg", "label": "Registration", "required": True}])
        epd_profiles.save_custom(p, d)
        self.assertIn("my-programme", epd_profiles.all_profiles(d))
        with self.assertRaises(ValueError):
            epd_profiles.save_custom(dict(p, id="generic"), d)
        with self.assertRaises(ValueError):
            epd_profiles.save_custom(dict(p, sections=["title", "nonsense"]), d)

    def test_additional_indicator_matching(self):
        res = [{"category": c, "indicator": c} for c in ("particulate matter formation", "ionising radiation, human health",
               "ecotoxicity, freshwater", "human toxicity, cancer", "human toxicity, non-cancer", "land use",
               "climate change: GWP-GHG", "climate change: land use and land use change")]
        found = epd_profiles.match_additional(res)
        self.assertEqual(found["SQP"], 5)
        self.assertEqual(found["HTP-c"], 3)
        self.assertEqual(found["HTP-nc"], 4)
        self.assertEqual(found["GWP-GHG"], 6)


# ---------------------------------------------------------------------------------------------- EF dataset DQR
class TestDatasetDqr(Base):
    def test_ilcd_dqi_parsing_and_use(self):
        import xml.etree.ElementTree as ET
        xml = ('<processDataSet xmlns:common="http://lca.jrc.it/ILCD/Common"><modellingAndValidation><validation><review>'
               '<common:dataQualityIndicators>'
               '<common:dataQualityIndicator name="Technological representativeness" value="Good"/>'
               '<common:dataQualityIndicator name="Geographical representativeness" value="Very good"/>'
               '<common:dataQualityIndicator name="Time representativeness" value="Fair"/>'
               '<common:dataQualityIndicator name="Precision" value="Good"/>'
               '<common:dataQualityIndicator name="Completeness" value="Not evaluated / unknown"/>'
               '<common:dataQualityIndicator name="Overall quality" value="Good quality"/>'
               '</common:dataQualityIndicators></review></validation></modellingAndValidation></processDataSet>')
        dq = other_formats.dataset_dqr(ET.fromstring(xml))
        self.assertEqual((dq["TeR"], dq["GeR"], dq["TiR"], dq["P"]), (2.0, 1.0, 3.0, 2.0))
        self.assertNotIn("C", dq)
        aid = self.find("concrete")
        self.st.x("INSERT INTO activity_dq VALUES(?,?,?,?,?,?,?,?,?)", (aid, 2, 1, 3, 2, None, None, "", "test"))
        m = self.model()
        self.st.add_input(m, "activity", aid, 1)
        c = calc.run(self.st, m, gwp(self.st))["data_quality"]["by_category"][0]
        self.assertAlmostEqual(c["pef_dqr"], 2.0)
        self.assertAlmostEqual(c["pef_from_datasets"], 1.0)


# ---------------------------------------------------------------------------------------------- marginal suppliers
class TestMarginal(Base):
    def test_constrained_suppliers_excluded(self):
        st = self.st
        db = st.one("SELECT id FROM databases")["id"]
        with st.lock:
            c = st.conn
            mk = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                           (db, "mkt", "market for steel", "steel", "GLO", "kg")).lastrowid
            rec = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,1)",
                            (db, "rec", "steel production, from recycled scrap", "steel, low-alloyed", "GLO", "kg")).lastrowid
            steel = self.find("steel")
            st.conn.execute("UPDATE activities SET product='steel, low-alloyed' WHERE id=?", (steel,))
            c.execute("INSERT INTO tech(output_id,input_id,amount) VALUES(?,?,?)", (mk, rec, 0.7))
            c.execute("INSERT INTO tech(output_id,input_id,amount) VALUES(?,?,?)", (mk, steel, 0.3))
            c.commit()
        st._bump_lib()
        calc.invalidate()
        m = self.model()
        self.st.add_input(m, "activity", mk, 1)
        g = analysis.marginal_guidance(self.st, m)
        mkt = next(x for x in g["markets"] if x["market"]["id"] == mk)
        self.assertTrue(next(s for s in mkt["suppliers"] if s["id"] == rec)["constrained"])
        self.assertEqual(mkt["proposal"]["id"], steel)
        rule = mkt["rule"]
        import science
        science.validate_rules([rule])
        # applied as a consequential scenario, the market supplies only the proposed (primary) steel
        sid = self.st.save_bg_scenario({"name": "marginal", "kind": "consequential", "base_year": 2020, "rules": [rule]})
        mids = gwp(self.st)
        with_bg = calc.run(self.st, m, mids, bg={"id": sid})["results"][0]["total"]
        m_primary = self.model("primary only")
        self.st.add_input(m_primary, "activity", steel, 1)
        primary = calc.run(self.st, m_primary, mids)["results"][0]["total"]
        before = calc.run(self.st, m, mids)["results"][0]["total"]
        self.assertAlmostEqual(with_bg, primary, places=9)
        self.assertNotAlmostEqual(with_bg, before, places=6)


# ---------------------------------------------------------------------------------------------- LCC
class TestLccExtended(Base):
    def test_replacements_and_cost_types(self):
        m = self.model(lcc_rate="0", lcc_period="60")
        a = self.st.add_input(m, "activity", self.find("timber"), 1, stage="B4")
        self.st.update_input(a, {"unit_cost": 100, "cost_type": "replacement", "replace_every": 25})
        b = self.st.add_input(m, "activity", self.find("concrete"), 1, stage="A1-A3")
        self.st.update_input(b, {"unit_cost": 50, "cost_type": "capex"})
        lc = calc.run(self.st, m, gwp(self.st))["lcc"]
        self.assertAlmostEqual(lc["total"], 100 * 3 + 50)        # years 0, 25, 50 within 60 years
        types = {t["type"]: t["cost"] for t in lc["by_type"]}
        self.assertEqual(types, {"replacement": 300.0, "capex": 50.0})
        m2 = self.model("D", lcc_rate="3", lcc_period="60")
        a2 = self.st.add_input(m2, "activity", self.find("timber"), 1)
        self.st.update_input(a2, {"unit_cost": 100, "replace_every": 25})
        self.assertAlmostEqual(calc.run(self.st, m2, gwp(self.st))["lcc"]["total_discounted"],
                               100 * (1 + 1.03 ** -25 + 1.03 ** -50))


# ---------------------------------------------------------------------------------------------- AWARE and LANCA
class TestRegional(Base):
    def test_aware_by_location_and_fallbacks(self):
        aw = "location,agri,non_agri,unknown\nGLO,40,20,30\nFR,8,5,7\n"
        r = regional.import_factors(self.st, "AWARE", aw)
        self.assertEqual(r["factors"], 6)
        bad = regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nXX,500,1,1\n", replace=False)
        self.assertEqual(bad["n_rejected"], 1)
        self.st.x("UPDATE activities SET location='FR' WHERE name LIKE 'electricity production, grid%'")
        self.st.x("UPDATE activities SET location='FR-IDF' WHERE name LIKE 'tap water%'")
        calc.invalidate()
        m = self.model(geography="DE")
        elec = self.find("electricity production, grid")
        self.st.add_input(m, "activity", elec, 10)
        water = self.st.search_flows("Water, well")[0]["id"]
        self.st.add_input(m, "flow", water, 0.5)
        self.st.add_input(m, "activity", self.find("tap water"), 100)
        res = regional.aware(self.st, m)
        # electricity: 10 kWh x 0.002 m3 at FR (unknown 7); own water 0.5 m3 at DE -> GLO (30);
        # tap water: 100 kg x 0.001 m3 at FR-IDF -> country FR (7), plus its electricity at FR
        e = 10 * 0.002 * 7 + 0.5 * 30 + 100 * 0.001 * 7 + 100 * 0.0005 * 0.002 * 7
        self.assertAlmostEqual(res["total"], e, places=10)
        self.assertGreater(res["completeness"]["global"], 0)
        self.assertGreater(res["completeness"]["country"], 0)

    def test_aware_irrigation_uses_the_agricultural_factor(self):
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,30\n")
        tap = self.find("tap water")
        self.st.x("UPDATE activities SET name='irrigation water, from tap water' WHERE id=?", (tap,))
        calc.invalidate()
        m = self.model()
        self.st.add_input(m, "activity", tap, 100)
        res = regional.aware(self.st, m)
        row = next(x for x in res["top"] if x["process"].startswith("irrigation"))
        self.assertEqual((row["use"], row["factor"]), ("agri", 40.0))
        others = [x for x in res["top"] if not x["process"].startswith("irrigation")]
        self.assertTrue(all(x["use"] == "unknown" and x["factor"] == 30.0 for x in others))

    def test_lanca_occupation_and_transformation(self):
        rows = ("indicator,kind,land_use,location,value,unit\n"
                "erosion resistance,occupation,arable land,GLO,2,kg/m2a\n"
                "biotic production,occupation,arable land,GLO,3,kg/m2a\n")
        regional.import_factors(self.st, "LANCA", rows)
        with self.assertRaises(ValueError):
            regional.import_factors(self.st, "LANCA", "indicator,kind,land_use,location,value\nsomething,occupation,x,GLO,1\n")
        m = self.model()
        self.st.add_input(m, "activity", self.find("wheat grain"), 1)
        res = regional.lanca(self.st, m)
        land = calc.run(self.st, m, [x["id"] for x in self.st.methods() if x["category"] == "land use"])["results"][0]["total"]
        er = next(x for x in res["indicators"] if x["indicator"] == "erosion resistance")
        self.assertAlmostEqual(er["total"], 2 * land, places=9)
        self.assertAlmostEqual(er["completeness"]["exact"] + er["completeness"]["global"], 1.0)
        self.assertFalse(res["empty"])
        self.assertGreater(er["land_area"], 0)
        # a model without any land flow in its supply chain is reported as empty, not as 0 % complete
        m0 = self.model("no land")
        self.st.add_input(m0, "flow", self.st.search_flows("Carbon dioxide, fossil")[0]["id"], 1)
        r0 = regional.lanca(self.st, m0)
        self.assertTrue(r0["empty"])
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,30\n")
        a0 = regional.aware(self.st, m0)
        self.assertTrue(a0["empty"])
        self.assertEqual(a0["total"], 0.0)
        self.assertEqual(regional.land_flow("Transformation, to urban, discontinuously built"),
                         ("transformation_to", "urban, discontinuously built"))

    def test_demo_is_labelled(self):
        s = regional.demo_factors(self.st)
        self.assertTrue(s["AWARE"]["demo"] and s["LANCA"]["demo"])


# ---------------------------------------------------------------------------------------------- social LCA
class TestSocial(Base):
    def test_worker_hours_and_risk_hours(self):
        data = ("match,location,worker_hours,stakeholder,indicator,risk\n"
                "cement production,,0.01,workers,Fair salary,high\n"
                "electricity production,,0.001,workers,Fair salary,low\n"
                "cement production,,0.01,local community,Access to water,medium\n")
        r = slca.import_data(self.st, data)
        self.assertEqual(r["rows"], 3)
        with self.assertRaises(ValueError):
            slca.import_data(self.st, "match,worker_hours,stakeholder,indicator,risk\nx,1,aliens,y,high\n")
        m = self.model()
        self.st.add_input(m, "activity", self.find("cement"), 2)
        res = slca.assess(self.st, m)
        mc = calc.get_mc(self.st)
        ctx = calc.Context(self.st)
        acts, fl, fx = {}, {}, []
        calc.expand(ctx, m, 1.0, acts, fl, fx)
        s = mc.solve(calc.demand_vector(mc, acts))
        out = {int(mc.act_ids[i]): s[i] * mc.diag[i] for i in range(mc.n)}
        cem = self.find("cement")
        el = self.find("electricity production, grid")
        hours = out[cem] * 0.01 + out[el] * 0.001
        self.assertAlmostEqual(res["worker_hours"], hours, places=12)
        fs = next(x for x in res["indicators"] if x["indicator"] == "Fair salary")
        self.assertAlmostEqual(fs["risk_hours"], out[cem] * 0.01 * 10 + out[el] * 0.001 * 0.1, places=12)
        self.assertGreater(res["n_without_data"], 0)

    def test_most_specific_row_and_location_first(self):
        acts = [{"id": 1, "key": "k1", "name": "cement production, Portland", "location": "CN"},
                {"id": 2, "key": "k2", "name": "cement production, Portland", "location": "FR"},
                {"id": 3, "key": "k3", "name": "cement production, blast furnace slag", "location": "FR"}]
        data = [{"match": "cement production", "location": "", "worker_hours": 1, "x": "generic"},
                {"match": "cement production, portland", "location": "", "worker_hours": 2, "x": "longer"},
                {"match": "cement production, portland", "location": "CN", "worker_hours": 3, "x": "longer, CN"}]
        a = slca._assign(acts, data)
        self.assertEqual([a[i][0]["x"] for i in (1, 2, 3)], ["longer, CN", "longer", "generic"])


# ---------------------------------------------------------------------------------------------- MFA
class TestMfa(unittest.TestCase):
    def test_fixed_lifetime_exact(self):
        d = {"years": [2000, 2010], "processes": [{"id": "a"}, {"id": "s", "stock": True, "lifetime": {"type": "fixed", "mean": 3}},
                                                  {"id": "k", "sink": True}],
             "inflows": [{"to": "a", "values": {"2000": 10}}],
             "flows": [{"from": "a", "to": "s", "share": 1}, {"from": "s", "to": "k", "share": 1}]}
        r = mfa.run(d)
        # tolerance, not exact equality: macOS arm64 numpy uses Accelerate, which can differ in the last digit
        for got, want in zip([x["end_of_life_outflow"] for x in r["rows"]], [0, 0, 0] + [10.0] * 8):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(r["rows"][-1]["stock"], 30.0, places=9)
        self.assertTrue(r["mass_balance_ok"])

    def test_loop_and_rates(self):
        r = mfa.run(mfa.EXAMPLE)
        self.assertTrue(r["mass_balance_ok"])
        late = r["rows"][-1]
        self.assertAlmostEqual(late["recycling_rate"], 0.85 * 0.95)
        self.assertGreater(late["recycled_content"], 0)

    def test_validation(self):
        bad = json.loads(json.dumps(mfa.EXAMPLE))
        bad["flows"][0]["share"] = 0.5
        with self.assertRaises(ValueError):
            mfa.run(bad)
        loop = {"years": [2000, 2001], "processes": [{"id": "a"}, {"id": "b"}], "inflows": [{"to": "a", "values": {"2000": 1}}],
                "flows": [{"from": "a", "to": "b", "share": 1}, {"from": "b", "to": "a", "share": 1}]}
        with self.assertRaises(ValueError):
            mfa.run(loop)

    def test_normal_and_weibull_retire_everything_eventually(self):
        for lt in ({"type": "normal", "mean": 10, "sd": 3}, {"type": "weibull", "shape": 2, "scale": 10}):
            c = mfa.retirement(lt, 200)
            self.assertEqual(c[0], 0.0)
            self.assertAlmostEqual(c.sum(), 1.0, places=9)

    def test_mci(self):
        self.assertAlmostEqual(mfa.mci()["MCI"], 0.1)
        self.assertAlmostEqual(mfa.mci(Fr=1, Cr=1)["MCI"], 1.0)
        self.assertAlmostEqual(mfa.mci(L_ratio=2)["MCI"], 0.55)


# ---------------------------------------------------------------------------------------------- shipped examples
class TestShippedExamples(Base):
    EX = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "examples")

    def read(self, name):
        with open(os.path.join(self.EX, name), encoding="utf-8") as fh:
            return fh.read()

    def test_every_example_file_is_usable(self):
        import xml.etree.ElementTree as ET
        # EPD profile example: valid, loads as a custom profile, renders its fields as required
        d = os.path.join(self.dir, "profiles")
        pid = epd_profiles.save_custom(json.loads(self.read("epd_profile_example.json")), d)
        self.assertEqual(epd_profiles.get(pid, d)["name"], "My programme (example)")
        # templates import (one row each) into the library
        aw = regional.import_factors(self.st, "AWARE", self.read("aware_factors_template.csv"))
        self.assertEqual((aw["factors"], aw["n_rejected"]), (3, 0))   # one location x agri, non-agri, unknown
        la = regional.import_factors(self.st, "LANCA", self.read("lanca_factors_template.csv"))
        self.assertEqual((la["factors"], la["n_rejected"]), (1, 0))
        self.assertEqual(slca.import_data(self.st, self.read("social_data_template.csv"))["rows"], 1)
        # MFA example runs and closes the mass balance
        self.assertTrue(mfa.run(json.loads(self.read("mfa_aluminium_example.json")))["mass_balance_ok"])
        # ILCD fragment gives the documented DQR
        dq = other_formats.dataset_dqr(ET.parse(os.path.join(self.EX, "ilcd_process_with_dqr.xml")).getroot())
        self.assertEqual((dq["TeR"], dq["GeR"], dq["TiR"], dq["P"]), (2.0, 1.0, 3.0, 2.0))
        self.assertAlmostEqual((dq["TeR"] + dq["GeR"] + dq["TiR"] + dq["P"]) / 4, 2.0)


if __name__ == "__main__":
    unittest.main()
