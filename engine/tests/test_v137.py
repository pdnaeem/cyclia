"""Tests for Cyclia 1.3.7: ILCD+EPD export, LANCA SQI aggregation, AWARE monthly and GIS factors, PSILCA/SOCA import,
MFA linked to LCA, staging imports and the Brightway/openLCA comparison kit."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc  # noqa: E402
import compare_kit  # noqa: E402
import ilcd_epd  # noqa: E402
import mfa  # noqa: E402
import regional  # noqa: E402
import slca  # noqa: E402
import staging  # noqa: E402
import standards  # noqa: E402
from importers import demo, jsonld, other_formats, tutorial  # noqa: E402
from store import Workspace  # noqa: E402
from test_v136 import SP_HEAD, sp_process  # noqa: E402


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


# ---------------------------------------------------------------------------------------------- ILCD+EPD
class TestIlcdEpd(Base):
    def setUp(self):
        super().setUp()
        demo.install_database(self.st)
        demo.build_project(self.st)
        self.wall = next(m for m in self.st.models() if m["name"] == "Concrete wall (demo)")["id"]
        self.res = calc.run(self.st, self.wall, [m["id"] for m in self.st.methods()])

    def test_export_is_schema_valid_and_carries_the_module_values(self):
        from lxml import etree
        p = os.path.join(self.dir, "e.zip")
        out = ilcd_epd.export(p, self.st.model(self.wall), self.res, "t")
        self.assertTrue(out["schema_valid"])
        z = zipfile.ZipFile(p)
        proc = z.read(f"ILCD/processes/{out['process_uuid']}.xml")
        self.assertEqual(ilcd_epd.validate(proc), [])
        self.assertEqual(ilcd_epd.validate(z.read(f"ILCD/flows/{out['flow_uuid']}.xml"), "flow"), [])
        root = etree.fromstring(proc)
        ns = {"p": ilcd_epd.NS_P, "c": ilcd_epd.NS_C, "e": ilcd_epd.NS_E}
        self.assertEqual(root.findtext("p:modellingAndValidation/p:LCIMethodAndAllocation/p:typeOfDataSet", namespaces=ns), "EPD")
        # GWP-total A1-A3 equals Cyclia's module table
        uid = ilcd_epd.LCIA["GWP-total"][0]
        res = next(r for r in root.iterfind("p:LCIAResults/p:LCIAResult", ns)
                   if r.find("p:referenceToLCIAMethodDataSet", ns).get("refObjectId") == uid)
        got = {a.get(f"{{{ilcd_epd.NS_E}}}module"): float(a.text) for a in res.iterfind("c:other/e:amount", ns)}
        k = standards._match_core(self.res["results"])["GWP-total"]
        want = standards.by_module(self.res)[k]["modules"]
        for mod, v in got.items():
            self.assertAlmostEqual(v, want[mod], places=12)
        self.assertEqual(set(got), set(standards.declared_modules(self.st.model(self.wall), self.res)))

    def test_schema_check_catches_errors(self):
        proc = ilcd_epd.build(self.st.model(self.wall), self.res)[0]
        bad = proc.replace(b"specific dataset", b"very specific dataset")
        self.assertTrue(ilcd_epd.validate(bad))

    def test_authoritative_identifiers(self):
        # values from the InData identifier lists (EN15804+A2_EF3.1_indicators.csv)
        self.assertEqual(ilcd_epd.LCIA["HTP-c"][0], "2299222a-bbd8-474f-9d4f-4dd1f18aea7c")
        self.assertEqual(ilcd_epd.FLOWS["PERT"][0], "53f97275-fa8a-4cdd-9024-65936002acd0")
        self.assertEqual(len(ilcd_epd.LCIA), 19)
        self.assertEqual(len(ilcd_epd.FLOWS), 18)


# ---------------------------------------------------------------------------------------------- SQI
class TestSqi(Base):
    ROWS = ("indicator,kind,land_use,location,value,unit\n"
            "erosion resistance,occupation,arable land,GLO,2,kg/(m2*a)\n"
            "mechanical filtration,occupation,arable land,GLO,40,cm/(m2*a)\n"
            "groundwater regeneration,occupation,arable land,GLO,0.5,m3/(m2*a)\n"
            "biotic production,occupation,arable land,GLO,8,kg/(m2*a)\n"
            "erosion resistance,occupation,forest,GLO,1,kg/(m2*a)\n"
            "soil quality index,occupation,arable land,GLO,1.5,dimensionless/(m2*a)\n")

    def test_linear_aggregation(self):
        regional.import_factors(self.st, "LANCA", self.ROWS, source="test")
        N = {"erosion resistance": 4, "mechanical filtration": 80, "groundwater regeneration": 1, "biotic production": 16}
        r = regional.sqi_aggregate(self.st, N, source="test N")
        v = self.st.one("SELECT value FROM native_factors WHERE indicator='soil quality index' AND key='occupation|arable land'")["value"]
        self.assertAlmostEqual(v, 0.25 * (2 / 4 + 40 / 80 + 0.5 / 1 + 8 / 16))
        self.assertEqual((r["factors"], r["n_incomplete"]), (1, 1))
        self.assertAlmostEqual(r["compared_with_official"][0]["relative_difference"], (0.5 - 1.5) / 1.5)

    def test_needs_every_normalisation_and_weights_summing_to_one(self):
        regional.import_factors(self.st, "LANCA", self.ROWS, source="test")
        with self.assertRaises(ValueError):
            regional.sqi_aggregate(self.st, {"erosion resistance": 1})
        with self.assertRaises(ValueError):
            regional.sqi_aggregate(self.st, dict.fromkeys(regional.SQI_INDICATORS, 1), weights={"erosion resistance": 0.9})


# ---------------------------------------------------------------------------------------------- AWARE monthly and GIS
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                                             [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]]}


class TestAwareMonthlyGis(Base):
    def _model(self, **scope):
        if not self.st.databases():
            tutorial.install(self.st)
        fid = self.st.add_flow("w-in", "Water, river", "natural resource", "in water", "m3")
        self.st.conn.commit()
        m = self.st.save_model({"name": "w", "product": "w", "unit": "kg", "amount": 1, "scope": dict(aware_use="non_agri", **scope)})
        self.st.add_input(m, "flow", fid, 10)
        return m

    def test_monthly_profile(self):
        rows = ["location,month,agri,non_agri,unknown", "FR,,40,20,30"] + [f"FR,{k},40,{k},30" for k in range(1, 13)]
        regional.import_factors(self.st, "AWARE", "\n".join(rows))
        m = self._model(aware_location="FR", aware_months="0 0 0 0 0 1 1 0 0 0 0 0")
        r = regional.aware(self.st, m)
        self.assertTrue(r["monthly_used"])
        self.assertAlmostEqual(r["total"], 10 * (6 + 7) / 2)
        m2 = self._model(aware_location="FR")
        self.assertAlmostEqual(regional.aware(self.st, m2)["total"], 10 * 20)          # annual without a profile

    def test_point_in_polygon_with_hole(self):
        self.assertTrue(regional.point_in(SQUARE, 2, 2))
        self.assertFalse(regional.point_in(SQUARE, 5, 5))          # in the hole
        self.assertFalse(regional.point_in(SQUARE, 11, 5))

    def test_geojson_basin_from_coordinates(self):
        gj = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"basin": "B-1", "name": "Basin one", "agri": 50, "non_agri": 33, "unknown": 40},
             "geometry": SQUARE},
            {"type": "Feature", "properties": {"basin": "B-2", "non_agri": 2}, "geometry": {"type": "Polygon", "coordinates": [[[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]]}}]}
        r = regional.import_geojson(self.st, "AWARE", json.dumps(gj), "basin")
        self.assertEqual((r["shapes"], r["factors"]), (2, 4))
        self.assertEqual(regional.locate(self.st, "AWARE", 2, 2)["location"], "B-1")       # lat 2, lon 2
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,30\n", replace=False)
        m = self._model(aware_lat=25, aware_lon=25)
        r = regional.aware(self.st, m)
        self.assertEqual(r["site_from_gis"]["location"], "B-2")
        self.assertAlmostEqual(r["total"], 10 * 2)


# ---------------------------------------------------------------------------------------------- PSILCA / SOCA
def olca_social_zip(path, processes):
    with zipfile.ZipFile(path, "w") as z:
        put = lambda pth, o: z.writestr(pth, json.dumps(o))
        put("locations/l-cn.json", {"@type": "Location", "@id": "l-cn", "name": "China", "code": "CN"})
        put("locations/l-glo.json", {"@type": "Location", "@id": "l-glo", "name": "Global", "code": "GLO"})
        put("social_indicators/i1.json", {"@type": "SocialIndicator", "@id": "i1", "name": "Fair salary",
                                          "category": "Workers/Fair salary", "activityVariable": "Worker hours",
                                          "activityUnit": {"name": "h"}, "unitOfMeasurement": "USD/month"})
        put("social_indicators/i2.json", {"@type": "SocialIndicator", "@id": "i2", "name": "Access to drinking water",
                                          "category": "Local community/Access to material resources", "activityVariable": "Worker hours"})
        for k, (name, loc, av, r1, r2) in enumerate(processes):
            put(f"processes/p{k}.json", {"@type": "Process", "@id": f"p{k}", "name": name, "location": {"@id": loc},
                                         "socialAspects": [
                                             {"socialIndicator": {"@id": "i1"}, "activityValue": av, "riskLevel": r1, "rawAmount": "250", "quality": "(2;3;2;1;3)"},
                                             {"socialIndicator": {"@id": "i2"}, "activityValue": av, "riskLevel": r2}]})


class TestOlcaSocial(Base):
    def test_soca_like_names_match_and_levels(self):
        tutorial.install(self.st)
        cem = self.st.search_activities("cement")[0]
        loc = "l-glo" if (cem["location"] or "GLO") == "GLO" else "l-cn"
        p = os.path.join(self.dir, "soca.zip")
        olca_social_zip(p, [(cem["name"], loc, 0.02, "HIGH_RISK", "NO_DATA")])
        r = slca.import_olca_social(self.st, p)
        self.assertEqual((r["rows"], r["processes"], r["indicators"]), (1, 1, 2))
        self.assertEqual(r["skipped_levels"], {"NO_DATA": 1})
        row = self.st.one("SELECT * FROM slca_data")
        self.assertEqual((row["stakeholder"], row["risk"], row["raw_value"], row["raw_unit"]), ("workers", "high", "250", "USD/month"))
        m = self.st.save_model({"name": "c", "product": "c", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", cem["id"], 3)
        res = slca.assess(self.st, m)
        self.assertEqual(res["n_with_data"], 1)
        self.assertGreater(res["worker_hours"], 0)

    def test_psilca_sector_mapping(self):
        tutorial.install(self.st)
        p = os.path.join(self.dir, "psilca.zip")
        olca_social_zip(p, [("Cement - CN", "l-cn", 0.5, "VERY_HIGH_RISK", "MEDIUM_RISK")])
        mp = "cyclia_match,cyclia_location,source_process,source_location\ncement production,,Cement - CN,CN\n"
        r = slca.import_olca_social(self.st, p, mp)
        self.assertEqual(r["mapped_rows"], 2)
        mapped = self.st.q("SELECT * FROM slca_data WHERE match='cement production'")
        self.assertEqual({x["risk"] for x in mapped}, {"very high", "medium"})
        self.assertTrue(all("sector: Cement - CN [CN]" in x["source"] for x in mapped))


# ---------------------------------------------------------------------------------------------- MFA linked to LCA
class TestMfaLca(Base):
    def test_impacts_over_time(self):
        tutorial.install(self.st)
        steel = self.st.search_activities("reinforcing steel")[0]["id"]
        mids = [m["id"] for m in self.st.methods() if m["category"] == "climate change"]
        r = mfa.lca(self.st, mfa.EXAMPLE, mids, {"prod": {"kind": "activity", "id": steel, "factor": 1.0}})
        run = mfa.run(mfa.EXAMPLE)
        thr = next(p for p in run["processes"] if p["id"] == "prod")["throughput"]
        mc = calc.get_mc(self.st)
        M = calc.Methods(self.st, mc, mids)
        unit = calc.impacts(mc, M, {steel: 1.0}, {}, [])[0][0]
        for t in (0, 10, len(thr) - 1):
            self.assertAlmostEqual(r["rows"][t]["total"][0], thr[t] * unit, places=9)
        self.assertAlmostEqual(r["cumulative"][0], sum(thr) * unit, places=6)
        self.assertIn("use", r["unlinked_processes"])
        with self.assertRaises(ValueError):
            mfa.lca(self.st, mfa.EXAMPLE, mids, {"nope": {"kind": "activity", "id": steel}})

    def test_virgin_input_recycling_and_credits(self):
        """Production charged on its virgin input only, recycling on its throughput, a credit for the recovered
        material with substitution 0.8: every part equals quantity x factor x unit impact, and net = gross + credits."""
        tutorial.install(self.st)
        steel = self.st.search_activities("reinforcing steel")[0]["id"]
        mids = [m["id"] for m in self.st.methods() if m["category"] == "climate change"]
        ex = dict(mfa.EXAMPLE)
        rec = ex["recycling_processes"][0]
        links = {"prod": {"kind": "activity", "id": steel, "basis": "virgin_input"},
                 "rec": {"process": rec, "kind": "activity", "id": steel, "factor": 0.1},
                 "credit": {"process": rec, "kind": "activity", "id": steel, "basis": "recovered", "avoided": True,
                            "substitution": 0.8}}
        r = mfa.lca(self.st, ex, mids, links)
        run = mfa.run(ex)
        P = {p["id"]: p for p in run["processes"]}
        mc = calc.get_mc(self.st)
        unit = calc.impacts(mc, calc.Methods(self.st, mc, mids), {steel: 1.0}, {}, [])[0][0]
        t = 15
        virgin = P["prod"]["virgin_input"][t]
        self.assertAlmostEqual(virgin, run["rows"][t]["virgin_inflow_to_production"])
        exp_prod = virgin * unit
        exp_rec = P[rec]["throughput"][t] * 0.1 * unit
        exp_cred = -P[rec]["output_to_system"][t] * 0.8 * unit
        row = r["rows"][t]
        self.assertAlmostEqual(row["by_process"]["prod"][0], exp_prod, places=9)
        self.assertAlmostEqual(row["by_process"]["rec"][0], exp_rec, places=9)
        self.assertAlmostEqual(row["credits"][0], exp_cred, places=9)
        self.assertAlmostEqual(row["total"][0], exp_prod + exp_rec + exp_cred, places=9)
        self.assertAlmostEqual(row["by_role"]["primary supply"][0], exp_prod, places=9)
        self.assertLess(virgin, P["prod"]["throughput"][t])            # recycled input is not charged as primary
        with self.assertRaises(ValueError):
            mfa.lca(self.st, ex, mids, {"x": {"process": rec, "kind": "activity", "id": steel, "basis": "virgin_input"}})
        with self.assertRaises(ValueError):
            mfa.lca(self.st, ex, mids, {"x": {"process": rec, "kind": "activity", "id": steel, "avoided": True,
                                              "substitution": 1.5}})


# ---------------------------------------------------------------------------------------------- staging
class TestStaging(Base):
    def _sp(self, text):
        p = os.path.join(self.dir, "sp.csv")
        with open(p, "w") as fh:
            fh.write(SP_HEAD + text)
        return p

    def test_merge_gives_the_same_results_as_a_direct_import(self):
        tutorial.install(self.st)
        p = self._sp(sp_process("Widget", 1.0, ident="A") + sp_process("Widget", 5.0, ident="B")
                     + sp_process("Gadget", 0.0, ident="G", inputs="Widget;kg;2;Undefined;0;0;0;"))
        res = staging.staged(self.st, self.dir, lambda s, pr: other_formats.import_simapro_csv(s, p, "SP", pr))
        self.assertTrue(res["staged"])
        db = next(d for d in self.st.databases() if d["name"] == "SP")
        u = self.st.one("SELECT candidates FROM unlinked WHERE db_id=?", (db["id"],))
        cands = json.loads(u["candidates"])
        names = {r["key"] for r in self.st.q(f"SELECT key FROM activities WHERE id IN ({','.join(map(str, cands))})")}
        self.assertEqual(names, {"A|Widget|CH", "B|Widget|CH"})       # candidate ids were shifted with the datasets
        self.assertFalse(os.listdir(self.dir) and any(x.startswith("cyclia-staging") for x in os.listdir(self.dir)))

    def test_failed_check_leaves_the_library_unchanged(self):
        tutorial.install(self.st)
        before = self.st.one("SELECT COUNT(*) AS n FROM activities")["n"]

        def bad(s, pr):
            b = other_formats._Builder(s, "Broken", "test")
            b.activity("x", "x", "x", "GLO", "kg")
            b.emission(0, "u-1", "Carbon dioxide, fossil", "air", "", "kg", float("nan"))
            return b.write(pr)
        with self.assertRaises(ValueError) as cm:
            staging.staged(self.st, self.dir, bad)
        self.assertIn("before it reached your library", str(cm.exception))
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM activities")["n"], before)
        self.assertFalse(any(d["name"] == "Broken" for d in self.st.databases()))

    def test_methods_of_a_staged_import_are_merged(self):
        from test_engine import TestImporters
        p = os.path.join(self.dir, "db.zip")
        TestImporters._jsonld(None, p)
        res = staging.staged(self.st, self.dir, lambda s, pr: jsonld.import_jsonld(s, p, "USLCI test", pr))
        self.assertTrue(res["staged"])
        b = self.st.search_activities("bolt")[0]["id"]
        m = self.st.save_model({"name": "b", "product": "b", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", b, 1)
        r = calc.run(self.st, m, [x["id"] for x in self.st.methods() if x["family"] == "TRACI 2.1"])
        self.assertAlmostEqual(r["results"][0]["total"], 1.1 * 2 + 0.1 * 0.3)       # as in test_jsonld_full


# ---------------------------------------------------------------------------------------------- comparison kit
class TestCompareKit(Base):
    def test_kit_matrices_and_jsonld_reproduce_cyclia(self):
        tutorial.install(self.st)
        db = self.st.databases()[0]["id"]
        mids = [m["id"] for m in self.st.methods()]
        p = os.path.join(self.dir, "kit.zip")
        out = compare_kit.build(self.st, db, mids, p, "t")
        k = os.path.join(self.dir, "kit")
        zipfile.ZipFile(p).extractall(k)
        self.assertEqual(out["results"], out["datasets"] * out["categories"])
        subprocess.run([sys.executable, "check_matrices.py"], cwd=k, check=True, capture_output=True)
        r = subprocess.run([sys.executable, "compare.py", "results_matrices.csv", "numpy"], cwd=k, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("agreement", open(os.path.join(k, "comparison_report.md")).read())
        # the openLCA JSON-LD, imported back, gives the same results
        ws2 = Workspace(os.path.join(self.dir, "rt"))
        self.addCleanup(ws2.close_all)
        st2 = ws2.create("rt")
        jsonld.import_jsonld(st2, os.path.join(k, "openlca", "database.zip"), "round trip")
        calc.invalidate()
        mc = calc.get_mc(st2)
        M = calc.Methods(st2, mc, [m["id"] for m in st2.methods()], regional=False)
        cats = [x["category"] for x in M.rows]
        with open(os.path.join(k, "cyclia_results.csv")) as fh:
            ref = {(x["name"], f"{x['category']} ({x['indicator']})"): float(x["value"]) for x in csv.DictReader(fh)}
        n = 0
        for a in st2.q("SELECT id, name FROM activities"):
            h = calc.impacts(mc, M, {a["id"]: 1.0}, {}, [])[0]
            for c, v in zip(cats, h):
                self.assertAlmostEqual(v, ref[(a["name"], c)], delta=1e-9 * max(1.0, abs(v)))
                n += 1
        self.assertEqual(n, out["results"])

    def test_scripts_are_in_the_kit(self):
        tutorial.install(self.st)
        p = os.path.join(self.dir, "kit.zip")
        compare_kit.build(self.st, self.st.databases()[0]["id"], [m["id"] for m in self.st.methods()], p)
        names = set(zipfile.ZipFile(p).namelist())
        self.assertTrue({"run_brightway.py", "run_openlca.py", "compare.py", "check_matrices.py", "README.md",
                         "openlca/database.zip", "cyclia_results.csv", "data/technosphere.csv"} <= names)
        for f in ("run_brightway.py", "run_openlca.py"):
            compile(zipfile.ZipFile(p).read(f).decode(), f, "exec")


if __name__ == "__main__":
    unittest.main()
