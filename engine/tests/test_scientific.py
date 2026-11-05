"""Regression tests for the scientific corrections of Cyclia 1.3.3 (external audit of 1.3.2)."""
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
import hier  # noqa: E402
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

    def model(self, name="M", unit="kg", amount=1, product="p", **scope):
        sc = {"goal": "g", "boundary": "cradle-to-gate", **scope}
        return self.st.save_model({"name": name, "product": product, "unit": unit, "amount": amount, "scope": sc})

    def param(self, mid, name, value, utype=0, p1=None, p2=None):
        self.st.save_parameter({"model_id": mid, "name": name, "value": value, "utype": utype, "p1": p1, "p2": p2})


# ---------------------------------------------------------------------------------------------- audit P0-1
class TestNestedUncertainty(Base):
    def test_tree_reproduces_the_deterministic_result(self):
        sub = self.model("Concrete", amount=2, unit="m3")
        self.st.add_input(sub, "activity", self.find("cement"), 600)
        self.st.add_input(sub, "activity", self.find("lorry"), 50)
        top = self.model("Wall", alloc_basis="", alloc_share="80")
        self.st.add_input(top, "model", sub, 0.5)
        self.st.add_input(top, "activity", self.find("steel"), 3, avoided=True)
        r = calc.run(self.st, top, gwp(self.st))
        ctx = calc.Context(self.st)
        mc = calc.get_mc(self.st)
        M = calc.Methods(self.st, mc, gwp(self.st))
        T = hier.build(ctx, top)
        total = float(hier.path_amounts(ctx, T) @ hier.leaf_units(ctx, mc, M, T)[:, 0])
        self.assertAlmostEqual(total, r["results"][0]["total"], places=9)
        self.assertEqual(len(T["leaves"]), 3)
        self.assertTrue(next(lf for lf in T["leaves"] if lf["credit"]))

    def test_pedigree_of_nested_lines_is_propagated(self):
        def cv(score):
            sub = self.model(f"Sub{score}")
            self.st.add_input(sub, "activity", self.find("cement"), 1, pedigree=[score] * 5)
            top = self.model(f"Top{score}")
            self.st.add_input(top, "model", sub, 1, pedigree=[1, 1, 1, 1, 1])
            return calc.run(self.st, top, gwp(self.st), mc_iterations=4000)["uncertainty"]["methods"][0]["cv_percent"]
        good, poor = cv(1), cv(5)
        self.assertGreater(poor, 3 * good)

    def test_parameters_of_nested_models_are_sampled(self):
        sub = self.model("Sub")
        self.param(sub, "fuel", 2.0, utype=2, p1=0.4)
        i = self.st.add_input(sub, "activity", self.find("electricity"), 2.0, formula="fuel", input_amount=2.0, input_unit="kWh")
        self.st.update_input(i, {"pedigree": [1, 1, 1, 1, 1]})
        top = self.model("Top")
        self.st.add_input(top, "model", sub, 1, pedigree=[1, 1, 1, 1, 1])
        u = calc.run(self.st, top, gwp(self.st), mc_iterations=4000)["uncertainty"]
        self.assertEqual(u["n_parameters"], 1)
        self.assertGreater(u["methods"][0]["cv_percent"], 15)      # normal SD 0.4 on 2.0 -> about 20 %
        s = calc.sobol(self.st, top, gwp(self.st), n=256)
        k = next(i for i, f in enumerate(s["factors"]) if f.startswith("parameter: fuel"))
        self.assertGreater(s["ST"][k][0], 0.8)

    def test_same_parameter_name_in_two_models_is_sampled_separately(self):
        a = self.model("A")
        self.param(a, "x", 1.0, utype=2, p1=0.2)
        self.st.add_input(a, "activity", self.find("electricity"), 1.0, formula="x", input_amount=1.0, input_unit="kWh")
        b = self.model("B")
        self.param(b, "x", 1.0, utype=2, p1=0.2)
        self.st.add_input(b, "activity", self.find("electricity"), 1.0, formula="x", input_amount=1.0, input_unit="kWh")
        top = self.model("Top")
        self.st.add_input(top, "model", a, 1)
        self.st.add_input(top, "model", b, 1)
        ctx = calc.Context(self.st)
        T = hier.build(ctx, top)
        self.assertEqual(len(hier.variables(ctx, T["models"])), 2)

    def test_spearman_correlation_is_achieved(self):
        from scipy import stats
        dist = [{"name": "a", "utype": 1, "p1": 1.5, "p2": None, "p3": None, "value": 1},
                {"name": "b", "utype": 4, "p1": 0.0, "p2": 1.0, "p3": None, "value": 0.5}]
        for rho in (0.8, -0.5, 0.3):
            d = analysis.correlated_draws(np.random.default_rng(5), dist, 60000, [{"a": "a", "b": "b", "r": rho}])
            self.assertAlmostEqual(stats.spearmanr(d["a"], d["b"])[0], rho, delta=0.01)

    def test_shared_sub_model_is_paired_in_comparison(self):
        sub = self.model("Shared")
        self.st.add_input(sub, "activity", self.find("cement"), 1, pedigree=[5, 5, 5, 5, 5])
        a = self.model("A")
        self.st.add_input(a, "model", sub, 1.0, pedigree=[1, 1, 1, 1, 1])
        b = self.model("B")
        self.st.add_input(b, "model", sub, 1.1, pedigree=[1, 1, 1, 1, 1])
        out = calc.full_mc(self.st, [a, b], gwp(self.st), iterations=400)
        self.assertGreater(out["pairs"][0]["p_a_lower"][0], 0.95)


# ---------------------------------------------------------------------------------------------- audit P0-2
class TestComparisonGate(Base):
    def test_blocked_screening_valid(self):
        a = self.model("A", unit="m2", product="wall U 0.25")
        self.st.add_input(a, "activity", self.find("concrete"), 0.2)
        b = self.model("B", unit="kg", product="wall U 0.25")
        self.st.add_input(b, "activity", self.find("timber"), 10)
        r = calc.compare(self.st, [a, b], gwp(self.st))
        self.assertEqual(r["status"], "blocked")
        self.assertIsNone(r["models"][0]["totals"][0])
        c = self.model("C", unit="m2", product="timber wall U 0.25", boundary="cradle-to-grave")
        self.st.add_input(c, "activity", self.find("timber"), 10)
        r = calc.compare(self.st, [a, c], gwp(self.st), equivalence="Both give 1 m2 at U = 0.25 W/m2K for 60 years.")
        self.assertEqual(r["status"], "screening")
        self.assertTrue(any("system boundaries" in i for i in r["issues"]))
        d = self.model("D", unit="m2", product="wall U 0.25")
        self.st.add_input(d, "activity", self.find("timber"), 10)
        self.assertEqual(calc.compare(self.st, [a, d], gwp(self.st))["status"], "screening")
        r = calc.compare(self.st, [a, d], gwp(self.st), equivalence="Both give 1 m2 at U = 0.25 W/m2K for 60 years.")
        self.assertEqual(r["status"], "valid")
        self.assertIsNotNone(r["models"][1]["totals"][0])


# ---------------------------------------------------------------------------------------------- audit P0-4 and EPD table
class TestEpdModules(Base):
    def _model(self, stage="A1-A3", extra_stage=None):
        m = self.model("E", stage_system="EN 15804 (construction products)")
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, stage=stage)
        if extra_stage:
            self.st.add_input(m, "activity", self.find("lorry"), 5, stage=extra_stage)
        return m

    def test_unassigned_stage_blocks_epd(self):
        m = self._model(extra_stage="Transport to site")
        r = calc.run(self.st, m, gwp(self.st))
        chk = standards.epd_checklist(self.st.model(m), r)
        self.assertFalse(next(i for i in chk["items"] if "EN 15804 module" in i["text"])["ok"])
        with self.assertRaises(ValueError):
            standards.epd_word(os.path.join(self.dir, "e.docx"), self.st.model(m), r, self.st.databases(), "x")
        m2 = self._model(extra_stage="A4")
        r2 = calc.run(self.st, m2, gwp(self.st))
        standards.epd_word(os.path.join(self.dir, "e2.docx"), self.st.model(m2), r2, self.st.databases(), "x")
        self.assertLess(standards.reconcile(r2), 1e-9)

    def test_a1_a3_not_declared_without_lines(self):
        m = self._model(stage="C4")
        r = calc.run(self.st, m, gwp(self.st))
        self.assertNotIn("A1-A3", standards.declared_modules(self.st.model(m), r))

    def test_rsl_condition_and_ef_version(self):
        m = self._model(extra_stage="B4")
        r = calc.run(self.st, m, gwp(self.st))
        item = lambda: next(i for i in standards.epd_checklist(self.st.model(m), r)["items"] if "service life" in i["text"])
        self.assertFalse(item()["ok"])
        mod = self.st.model(m)
        mod["scope"]["epd"] = {"rsl": "60 years"}
        self.assertTrue(next(i for i in standards.epd_checklist(mod, r)["items"] if "service life" in i["text"])["ok"])
        self.assertTrue(standards.ef_reference(["EF v3.1"]))
        self.assertTrue(standards.ef_reference(["EF v3.0 EN15804"]))
        self.assertFalse(standards.ef_reference(["EF v2.0"]))
        self.assertFalse(standards.ef_reference(["ReCiPe 2016 (H)", "EF v3.1"]))
        self.assertFalse(standards.ef_reference(["Cyclia demo method (EF-like)"]))


# ---------------------------------------------------------------------------------------------- audit P1-5
class TestDataQuality(Base):
    def test_credits_excluded_nested_included_pef_separate(self):
        sub = self.model("Sub")
        self.st.add_input(sub, "activity", self.find("cement"), 1, pedigree=[5, 5, 5, 5, 5])
        top = self.model("Top")
        self.st.add_input(top, "model", sub, 1, pedigree=[1, 1, 1, 1, 1])
        self.st.add_input(top, "activity", self.find("steel"), 50, avoided=True, pedigree=[1, 1, 1, 1, 1])
        dq = calc.run(self.st, top, gwp(self.st))["data_quality"]
        c = dq["by_category"][0]
        self.assertAlmostEqual(c["dqr"], 5.0)                 # weakest link of the only burden path; credit left out
        self.assertGreater(c["credit_share"], 0)
        self.assertIsNone(c["pef_dqr"])
        line = self.st.model(sub)["inputs"][0]
        self.st.update_input(line["id"], {"pef": [2, 1, 2, 3]})
        self.st.update_input(self.st.model(top)["inputs"][0]["id"], {"pef": [1, 1, 1, 1]})
        c = calc.run(self.st, top, gwp(self.st))["data_quality"]["by_category"][0]
        self.assertAlmostEqual(c["pef_dqr"], 2.0)
        self.assertAlmostEqual(c["pef_coverage"], 1.0)
        self.assertTrue(any("(in Sub)" in x["name"] for x in calc.run(self.st, top, gwp(self.st))["data_quality"]["lines"]))


# ---------------------------------------------------------------------------------------------- audit P1-6, P1-7
class TestFindings(Base):
    def test_credit_is_not_recommended_for_reduction(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("electricity"), 10)
        self.st.add_input(m, "activity", self.find("steel"), 20, avoided=True)
        r = calc.run(self.st, m, gwp(self.st))
        self.assertLess(r["results"][0]["total"], 0)
        imp = next(f for f in r["findings"] if f["kind"] == "improve")
        self.assertIn("electricity", imp["text"])
        self.assertNotIn("steel", imp["text"])
        cred = next(f for f in r["findings"] if f["kind"] == "credit")
        self.assertIn("result rises", cred["text"])

    def test_hotspots_are_not_called_burden_shifting(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("cement"), 1)
        self.st.add_input(m, "activity", self.find("timber"), 10)
        mids = [x["id"] for x in self.st.methods() if x["family"].startswith("Tutorial")][:4]
        r = calc.run(self.st, m, mids)
        h = [f for f in r["findings"] if f["kind"] == "hotspots"]
        for f in h:
            self.assertIn("do not show burden shifting", f["text"])


# ---------------------------------------------------------------------------------------------- audit P1-8
class TestDataAge(Base):
    def test_five_and_ten_year_thresholds(self):
        import time
        y = time.localtime().tm_year
        m = self.model(period=f"{y - 1} to {y}")
        a = self.st.add_input(m, "activity", self.find("concrete"), 1)
        self.st.update_input(a, {"data_year": y - 7, "data_type": "primary"})
        b = self.st.add_input(m, "activity", self.find("steel"), 1)
        self.st.update_input(b, {"data_year": y - 7, "data_type": "secondary"})
        msgs = " ".join(c["message"] for c in calc.run(self.st, m, gwp(self.st))["checks"])
        self.assertIn("producer-specific (primary) line(s) use data older than 5 years", msgs)
        self.assertNotIn("generic line(s) use data older than 10 years", msgs)
        self.assertIn("outside the time period", msgs)
        self.st.update_input(b, {"data_year": y - 12})
        msgs = " ".join(c["message"] for c in calc.run(self.st, m, gwp(self.st))["checks"])
        self.assertIn("generic line(s) use data older than 10 years", msgs)


# ---------------------------------------------------------------------------------------------- audit P1-10
class TestMigration(Base):
    def test_recursive_migration_and_rollback(self):
        from tests.test_analysis import TestDatabases
        src, new, _ = TestDatabases._copy_db(self)
        raw = self.model("Raw")
        self.st.add_input(raw, "activity", self.find("cement"), 1)
        poly = self.model("Poly")
        self.st.add_input(poly, "model", raw, 1)
        prod = self.model("Product")
        self.st.add_input(prod, "model", poly, 2)
        self.st.add_input(prod, "activity", self.find("lorry"), 1)
        plan = analysis.relink_plan(self.st, prod, src, new)
        self.assertEqual({m["name"] for m in plan["models"]}, {"Raw", "Product"})
        res = analysis.relink_plan(self.st, prod, src, new, apply=True, method_ids=gwp(self.st))
        self.assertEqual(sorted(res["changed_models"]), sorted([raw, prod]))
        self.assertEqual(self.st.model(raw)["inputs"][0]["target"]["db"], "Tutorial v2")
        self.assertGreater(res["results"][0]["change_percent"], 0)
        u = analysis.undo_migration(self.st, res["changed_models"])
        self.assertEqual(sorted(u["undone"]), sorted([raw, prod]))
        self.assertEqual(self.st.model(raw)["inputs"][0]["target"]["db"], "Tutorial database (illustrative)")


if __name__ == "__main__":
    unittest.main()
