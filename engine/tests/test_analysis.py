"""Tests of the 1.3.2 analyses: LCC, water, CFF, database comparison and relinking, checks, correlations, reports."""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
import report  # noqa: E402
import standards  # noqa: E402
from importers import tutorial  # noqa: E402
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

    def model(self, name="M", unit="kg", amount=1, **scope):
        sc = {"goal": "g", "boundary": "cradle-to-gate", **scope}
        return self.st.save_model({"name": name, "product": "p", "unit": unit, "amount": amount, "scope": sc})

    def unit_gwp(self, act_id):
        mc = calc.get_mc(self.st)
        M = calc.Methods(self.st, mc, gwp(self.st))
        return float(calc.impacts(mc, M, {act_id: 1.0}, {}, [])[0][0])


class TestLcc(Base):
    def test_costs_discounting_revenue_and_submodels(self):
        sub = self.model("Sub", amount=2)
        i = self.st.add_input(sub, "activity", self.find("electricity"), 4)
        self.st.update_input(i, {"unit_cost": 0.25})            # 4 kWh * 0.25 = 1.0 per 2 kg -> 0.5 per kg
        m = self.model("Top", lcc_rate="5", lcc_currency="EUR")
        a = self.st.add_input(m, "activity", self.find("concrete"), 2, stage="A1")
        self.st.update_input(a, {"unit_cost": 10})                # 20
        b = self.st.add_input(m, "activity", self.find("electricity"), 100, stage="B6", year=10)
        self.st.update_input(b, {"unit_cost": 0.2})               # 20 in year 10
        c = self.st.add_input(m, "activity", self.find("steel"), 1, stage="C3", avoided=True)
        self.st.update_input(c, {"unit_cost": 3})                 # revenue -3
        self.st.add_input(m, "model", sub, 4, stage="A1")         # 4 kg of sub -> 2.0
        self.st.add_input(m, "activity", self.find("lorry"), 5, stage="A4")   # no price
        r = calc.run(self.st, m, gwp(self.st))
        lc = r["lcc"]
        self.assertAlmostEqual(lc["total"], 20 + 20 - 3 + 2.0, places=9)
        self.assertAlmostEqual(lc["total_discounted"], 20 + 20 / 1.05 ** 10 - 3 + 2.0, places=9)
        self.assertEqual(lc["n_uncosted"], 1)
        self.assertEqual(next(s for s in lc["by_stage"] if s["stage"] == "A1")["cost"], 22.0)
        self.assertIn("cost", {f["kind"] for f in r["findings"]})
        self.assertTrue(any("no price" in c["message"] for c in r["checks"]))

    def test_no_costs_no_lcc(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 1)
        self.assertIsNone(calc.run(self.st, m, gwp(self.st))["lcc"])


class TestWater(Base):
    def test_water_withdrawal(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("electricity"), 10)
        w = calc.run(self.st, m, gwp(self.st))["water"]
        self.assertAlmostEqual(w["withdrawal"], 10 * 0.002, places=12)
        self.assertAlmostEqual(w["consumption"], w["withdrawal"] - w["release"])

    def test_classification(self):
        lci = [{"name": "Water, river", "context": "natural resource/in water", "unit": "m3", "amount": 5.0},
               {"name": "Water, turbine use, unspecified natural origin", "context": "natural resource/in water",
                "unit": "m3", "amount": 100.0},
               {"name": "Water", "context": "water/surface water", "unit": "m3", "amount": 102.0},
               {"name": "Water", "context": "air", "unit": "kg", "amount": 1000.0}]
        w = analysis.water_inventory(lci)
        self.assertAlmostEqual(w["withdrawal"], 105)
        self.assertAlmostEqual(w["withdrawal_turbine"], 100)
        self.assertAlmostEqual(w["release"], 103)
        self.assertAlmostEqual(w["consumption"], 2)


class TestCff(Base):
    def test_coefficients_match_formula(self):
        p = {"A": 0.2, "B": 0, "R1": 0.3, "R2": 0.6, "R3": 0.25, "Qsin": 0.9, "Qsout": 0.8, "LHV": 20, "X_heat": 0.5,
             "X_elec": 0.2}
        lines, v = analysis.cff_lines(p)
        c = {r: k for r, k, _ in lines}
        self.assertAlmostEqual(c["virgin"], 0.7 + 0.3 * 0.8 * 0.9)
        self.assertAlmostEqual(c["recycled"], 0.06)
        self.assertAlmostEqual(c["recycling_eol"], 0.48)
        self.assertAlmostEqual(c["avoided_virgin"], 0.48 * 0.8)
        self.assertAlmostEqual(c["energy_recovery"], 0.25)
        self.assertAlmostEqual(c["avoided_heat"], 0.25 * 20 * 0.5)
        self.assertAlmostEqual(c["disposal"], 0.15)
        with self.assertRaises(ValueError):
            analysis.cff_lines({"R2": 0.7, "R3": 0.5})
        with self.assertRaises(ValueError):
            analysis.cff_lines({"A": 1.2})

    def test_apply_gives_formula_result(self):
        m = self.model()
        steel, mswi, land = self.find("steel"), self.find("incineration"), self.find("landfill")
        heat, elec = self.find("natural gas boiler"), self.find("electricity production, grid")
        p = {"A": 0.2, "R1": 0.3, "R2": 0.6, "R3": 0.3, "Qsin": 1, "Qsout": 1, "LHV": 10, "X_heat": 0.4, "X_elec": 0.1}
        res = analysis.apply_cff(self.st, m, 2.0, "kg", p, {"virgin": steel, "recycled": steel, "recycling_eol": steel,
                                 "energy_recovery": mswi, "avoided_heat": heat, "avoided_electricity": elec,
                                 "disposal": land}, "A1-A3", "End of life")
        self.assertEqual(len(res["added"]), 8)
        E = {k: self.unit_gwp(v) for k, v in (("s", steel), ("mswi", mswi), ("land", land), ("heat", heat), ("el", elec))}
        A, R1, R2, R3 = 0.2, 0.3, 0.6, 0.3
        per_kg = ((1 - R1) * E["s"] + R1 * (A * E["s"] + (1 - A) * E["s"]) + (1 - A) * R2 * (E["s"] - E["s"])
                  + R3 * (E["mswi"] - 10 * 0.4 * E["heat"] - 10 * 0.1 * E["el"] / 3.6) + (1 - R2 - R3) * E["land"])
        total = calc.run(self.st, m, gwp(self.st))["results"][0]["total"]
        self.assertAlmostEqual(total, 2.0 * per_kg, places=9)
        with self.assertRaises(ValueError):
            analysis.apply_cff(self.st, m, 1.0, "kg", p, {"virgin": steel})


class TestDatabases(Base):
    def _copy_db(self, scale_key="clinker", factor=2.0):
        """Second version of the tutorial database where one dataset has twice the CO2 emissions."""
        st = self.st
        src = st.one("SELECT id FROM databases WHERE source='built-in'")["id"]
        new = st.create_database("Tutorial v2", "test", "2.0", "")
        ids = {}
        with st.lock:
            c = st.conn
            for a in st.q("SELECT * FROM activities WHERE db_id=?", (src,)):
                cur = c.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) VALUES(?,?,?,?,?,?,?)",
                                (new, a["key"], a["name"], a["product"], a["location"], a["unit"], a["production"]))
                ids[a["id"]] = cur.lastrowid
            for t in st.q(f"SELECT * FROM tech WHERE output_id IN ({','.join(map(str, ids))})"):
                c.execute("INSERT INTO tech(output_id,input_id,amount) VALUES(?,?,?)", (ids[t["output_id"]], ids[t["input_id"]], t["amount"]))
            for b in st.q(f"SELECT b.*, a.key FROM bio b JOIN activities a ON a.id=b.activity_id WHERE b.activity_id IN ({','.join(map(str, ids))})"):
                c.execute("INSERT INTO bio(activity_id,flow_id,amount) VALUES(?,?,?)",
                          (ids[b["activity_id"]], b["flow_id"], b["amount"] * (factor if b["key"] == scale_key else 1)))
            c.commit()
        st.finish_database(new)
        calc.invalidate()
        return src, new, ids

    def test_compare_and_relink(self):
        src, new, ids = self._copy_db()
        res = analysis.compare_databases(self.st, src, new, gwp(self.st), sample=1000)
        self.assertEqual(res["n_missing"], 0)
        top = res["rows"][0]
        self.assertTrue(top["change_percent"][0] > 1)
        unchanged = next(r for r in res["rows"] if r["name"].startswith("electricity production, grid"))
        self.assertAlmostEqual(unchanged["change_percent"][0], 0.0, places=9)
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 1)
        before = calc.run(self.st, m, gwp(self.st))["results"][0]["total"]
        plan = analysis.relink_plan(self.st, m, src, new)
        self.assertEqual((plan["n_found"], plan["n_missing"], plan["applied"]), (1, 0, False))
        analysis.relink_plan(self.st, m, src, new, apply=True)
        line = self.st.model(m)["inputs"][0]
        self.assertEqual(line["target"]["db"], "Tutorial v2")
        after = calc.run(self.st, m, gwp(self.st))["results"][0]["total"]
        self.assertGreater(after, before)
        self.st.undo(m)
        self.assertEqual(self.st.model(m)["inputs"][0]["target"]["db"], "Tutorial database (illustrative)")


class TestChecks(Base):
    def test_method_versions(self):
        g = analysis.method_versions(["EF v3.0", "EF v3.1", "ReCiPe 2016 Midpoint (H)", "IPCC 2021 GWP100"])
        self.assertEqual(g, [["EF v3.0", "EF v3.1"]])
        self.assertEqual(analysis.method_versions(["EF v3.1", "ReCiPe 2016"]), [])

    def test_approach_and_data_age(self):
        m = self.model(approach="consequential", alloc_basis="mass")
        i = self.st.add_input(m, "activity", self.find("concrete"), 1)
        self.st.update_input(i, {"data_year": 2001})
        msgs = " ".join(c["message"] for c in calc.run(self.st, m, gwp(self.st))["checks"])
        self.assertIn("consequential study should avoid allocation", msgs)
        self.assertIn("older than 10 years", msgs)
        self.assertEqual(analysis.approach_issues({"approach": "consequential"}, ["Allocation, cut-off by classification"])[0][0],
                         "warning")
        self.assertTrue(analysis.approach_issues({"approach": "attributional"}, ["Substitution, consequential, long-term"]))

    def test_energy_balance(self):
        m = self.model(unit="MJ", amount=1)
        self.st.add_input(m, "activity", self.find("electricity"), 0.5, input_amount=0.5, input_unit="kWh")  # 1.8 MJ in
        self.assertFalse(any("Energy balance" in c["message"] for c in calc.run(self.st, m, gwp(self.st))["checks"]))
        m2 = self.model("E2", unit="MJ", amount=10)
        self.st.add_input(m2, "activity", self.find("electricity"), 0.5, input_amount=0.5, input_unit="kWh")
        self.assertTrue(any("Energy balance" in c["message"] for c in calc.run(self.st, m2, gwp(self.st))["checks"]))


class TestUncertainty(Base):
    def test_correlated_draws(self):
        rng = np.random.default_rng(1)
        dist = [{"name": "a", "utype": 2, "p1": 1.0, "p2": None, "p3": None, "value": 10},
                {"name": "b", "utype": 4, "p1": 0.0, "p2": 1.0, "p3": None, "value": 0.5},
                {"name": "c", "utype": 2, "p1": 1.0, "p2": None, "p3": None, "value": 0}]
        d = analysis.correlated_draws(rng, dist, 20000, [{"a": "a", "b": "b", "r": 0.8}])
        from scipy import stats
        self.assertGreater(stats.spearmanr(d["a"], d["b"])[0], 0.7)
        self.assertLess(abs(stats.spearmanr(d["a"], d["c"])[0]), 0.05)
        self.assertAlmostEqual(float(np.mean(d["a"])), 10, delta=0.05)
        self.assertTrue(0 <= d["b"].min() and d["b"].max() <= 1)
        with self.assertRaises(calc.LCAError):
            analysis.correlated_draws(rng, dist, 10, [{"a": "a", "b": "b", "r": 0.9}, {"a": "a", "b": "c", "r": 0.9},
                                                       {"a": "b", "b": "c", "r": -0.9}])

    def test_convergence_reported(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 1)
        u = calc.run(self.st, m, gwp(self.st), mc_iterations=2000)["uncertainty"]["methods"][0]
        self.assertIn("converged", u)
        self.assertLess(u["se_mean_percent"], 5)


class TestReports(Base):
    def test_executive_summary_figures_epd(self):
        m = self.model(conclusions="Concrete dominates.", review_status="internal")
        i = self.st.add_input(m, "activity", self.find("concrete"), 1, stage="A1-A3")
        self.st.update_input(i, {"data_type": "primary", "source_ref": "Plant data 2024", "data_year": 2024,
                                 "supplier": "Plant X", "verified": True, "unit_cost": 90})
        self.st.add_input(m, "activity", self.find("lorry"), 10, stage="A4")
        r = calc.run(self.st, m, gwp(self.st))
        from docx import Document
        p = os.path.join(self.dir, "s.docx")
        report.executive_summary(p, self.st.model(m), r, "1.3.2")
        text = "\n".join(x.text for x in Document(p).paragraphs)
        self.assertIn("Concrete dominates.", text)
        self.assertIn("Life cycle cost", text)
        files = report.figures(os.path.join(self.dir, "fig"), r)
        self.assertTrue(any(f.endswith(".svg") for f in files) and any(f.endswith(".png") for f in files))
        w = os.path.join(self.dir, "w.docx")
        report.word_report(w, self.st.model(m), r, self.st.databases(), "1.3.2")
        d = Document(w)
        cells = " ".join(c.text for t in d.tables for row in t.rows for c in row.cells)
        self.assertIn("Plant data 2024", cells)
        self.assertIn("Modelling approach", cells)
        sh = standards.specific_share(r)
        self.assertTrue(0.5 < sh < 1)
        x = os.path.join(self.dir, "x.xlsx")
        report.excel_results(x, self.st.model(m), r)
        from openpyxl import load_workbook
        self.assertTrue({"Data quality", "Key findings", "LCC"} <= set(load_workbook(x).sheetnames))


if __name__ == "__main__":
    unittest.main()
