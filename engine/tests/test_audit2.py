"""Regression tests for the second external audit (Cyclia 1.3.4)."""
import os
import shutil
import sys
import tempfile
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import crosscheck  # noqa: E402
import report  # noqa: E402
import standards  # noqa: E402
import trust  # noqa: E402
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
        crosscheck._Solver.DENSE_MAX = 4000
        shutil.rmtree(self.dir, ignore_errors=True)

    def model(self, name="M", unit="kg", amount=1, product="p", **scope):
        sc = {"goal": "g", "boundary": "cradle-to-gate", **scope}
        return self.st.save_model({"name": name, "product": product, "unit": unit, "amount": amount, "scope": sc})

    def nested(self):
        manu = self.model("Manufacturing", amount=2, alloc_share="50")
        line = self.st.add_input(manu, "activity", self.find("cement"), 4)
        prod = self.model("Product")
        self.st.add_input(prod, "model", manu, 3)
        self.st.add_input(prod, "model", manu, 1)
        return prod, manu, line


class TestRecursiveChecks(Base):
    def test_data_age_inside_nested_models(self):
        prod, manu, line = self.nested()
        self.st.update_input(line, {"data_type": "primary", "data_year": 2010})
        msgs = " ".join(c["message"] for c in calc.run(self.st, prod, gwp(self.st))["checks"])
        self.assertIn("older than 5 years", msgs)
        self.assertIn("in Manufacturing", msgs)

    def test_system_models_across_nested_models(self):
        from tests.test_analysis import TestDatabases
        src, new, _ = TestDatabases._copy_db(self)
        self.st.x("UPDATE databases SET system_model=? WHERE id=?", ("Substitution, consequential, long-term", new))
        self.st.x("UPDATE databases SET system_model=? WHERE id=?", ("Allocation, cut-off by classification", src))
        calc.invalidate()
        manu = self.model("Manufacturing")
        v2 = self.st.one("SELECT id FROM activities WHERE db_id=? AND key='cement'", (new,))["id"]
        self.st.add_input(manu, "activity", v2, 1)
        prod = self.model("Product", approach="attributional")
        self.st.add_input(prod, "activity", self.find("steel"), 1)
        self.st.add_input(prod, "model", manu, 1)
        msgs = " ".join(c["message"] for c in calc.run(self.st, prod, gwp(self.st))["checks"])
        self.assertIn("across the nested models", msgs)
        self.assertIn("in Manufacturing", msgs)
        self.assertIn("attributional but uses consequential", msgs)


class TestComparisonDqr(Base):
    def test_every_category_is_compared(self):
        mids = gwp(self.st) + [m["id"] for m in self.st.methods() if m["category"] == "water use"]
        water = self.st.search_flows("Water, well")[0]["id"]
        a = self.model("A", product="p")
        self.st.add_input(a, "activity", self.find("electricity"), 1, pedigree=[1, 1, 1, 1, 1])
        self.st.add_input(a, "flow", water, 1, pedigree=[5, 5, 5, 5, 5])
        b = self.model("B", product="p")
        self.st.add_input(b, "activity", self.find("electricity"), 1, pedigree=[1, 1, 1, 1, 1])
        self.st.add_input(b, "flow", water, 1, pedigree=[1, 1, 1, 1, 1])
        r = calc.compare(self.st, [a, b], mids, equivalence="Both deliver one kg of the same product, same quality.")
        txt = " ".join(r["issues"])
        self.assertIn("water use", txt)
        self.assertNotIn("climate change (", txt)
        self.assertEqual(len(r["models"][0]["dqr"]), 2)


class TestNestedInventory(Base):
    def test_per_fu_amounts_and_annexes(self):
        prod, manu, line = self.nested()
        self.st.update_input(line, {"supplier": "Plant A", "source_ref": "Supplier EPD 42", "data_year": 2025})
        r = calc.run(self.st, prod, gwp(self.st))
        self.assertTrue(r["nested"])
        cem = next(x for x in r["foreground"] if x["model"] == "Manufacturing")
        self.assertAlmostEqual(cem["per_fu"], 4.0)          # (3 + 1) kg of Manufacturing x 4 x 50 % / 2
        self.assertEqual(cem["occurrences"], 2)
        from docx import Document
        w = os.path.join(self.dir, "r.docx")
        report.word_report(w, self.st.model(prod), r, self.st.databases(), "x")
        cells = " ".join(c.text for t in Document(w).tables for row in t.rows for c in row.cells)
        self.assertIn("Plant A", cells)
        self.assertIn("Supplier EPD 42", cells)
        x = os.path.join(self.dir, "r.xlsx")
        report.excel_results(x, self.st.model(prod), r)
        from openpyxl import load_workbook
        wb = load_workbook(x)
        self.assertIn("Supply-chain inventory", wb.sheetnames)
        self.assertTrue(any(row[0].value == "Manufacturing" for row in wb["Supply-chain inventory"].iter_rows(min_row=2)))
        e = os.path.join(self.dir, "e.xlsx")
        standards.epd_excel(e, self.st.model(prod), r)
        self.assertTrue(any(row[0].value == "Manufacturing" for row in load_workbook(e)["Inventory"].iter_rows(min_row=2)))


class TestEpdIndicators(Base):
    def test_inventory_indicator_matching(self):
        names = ["use of renewable primary energy excluding renewable primary energy resources used as raw materials (PERE)",
                 "use of non-renewable primary energy resources used as raw materials", "Total use of non-renewable primary energy",
                 "Use of secondary material", "Use of non-renewable secondary fuels", "Net use of fresh water",
                 "Hazardous waste disposed", "Non-hazardous waste disposed", "Radioactive waste disposed",
                 "Components for re-use", "Materials for recycling", "Materials for energy recovery",
                 "Exported energy, electricity", "Exported energy, thermal", "Use of renewable secondary fuels",
                 "Total use of renewable primary energy resources", "renewable primary energy resources used as raw materials",
                 "non-renewable primary energy as energy carrier"]
        res = [{"category": n, "indicator": n, "unit": "MJ"} for n in names]
        found = standards.match_inventory(res)
        self.assertEqual(set(found), {a for a, *_ in standards.INVENTORY})
        self.assertEqual(names[found["NHWD"]], "Non-hazardous waste disposed")
        self.assertEqual(names[found["PENRM"]], "use of non-renewable primary energy resources used as raw materials")
        self.assertEqual(names[found["PERM"]], "renewable primary energy resources used as raw materials")

    def test_checklist_blocks_submission_not_draft(self):
        m = self.model("E", stage_system="EN 15804 (construction products)")
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, stage="A1-A3")
        r = calc.run(self.st, m, gwp(self.st))
        chk = standards.epd_checklist(self.st.model(m), r)
        self.assertFalse(chk["ready"])
        txt = " ".join(i["text"] for i in chk["items"] if not i["ok"])
        self.assertIn("Resource use indicators calculated (missing: PERE", txt)
        self.assertIn("Waste category indicators", txt)
        path = os.path.join(self.dir, "epd.docx")
        standards.epd_word(path, self.st.model(m), r, self.st.databases(), "x")
        from docx import Document
        self.assertIn("NOT READY FOR SUBMISSION", "\n".join(p.text for p in Document(path).paragraphs))

    def test_unit_check(self):
        self.assertTrue(standards.unit_ok("kg CO2-eq", ("co2",)))
        self.assertTrue(standards.unit_ok("mol H+ eq", ("mol h",)))
        self.assertFalse(standards.unit_ok("kg SO2-eq", ("mol h",)))
        self.assertTrue(standards.unit_ok("m3 world eq. deprived", ("m3",)))


class TestAllocation(Base):
    def test_physical_causality(self):
        sc = {"alloc_basis": "physical", "alloc_property": "N content", "main_physical": 3,
              "coproducts": [{"name": "straw", "physical": 1}]}
        self.assertAlmostEqual(calc.allocation_share(sc), 0.75)
        m = self.model("Grain", **sc)
        self.st.add_input(m, "activity", self.find("electricity"), 1)
        r = calc.run(self.st, m, gwp(self.st))
        self.assertAlmostEqual(r["allocation_share"], 0.75)
        self.assertTrue(any("physical causality (N content)" in c["message"] for c in r["checks"]))


class TestCrossCheck(Base):
    def _models(self):
        prod, manu, line = self.nested()
        self.st.add_input(prod, "activity", self.find("steel"), 2, avoided=True)
        return [prod, manu]

    def test_agreement_dense_and_gmres(self):
        mids = [m["id"] for m in self.st.methods()]
        ids = self._models()
        r = crosscheck.run(self.st, mids, sample=1000, model_ids=ids)
        self.assertTrue(r["passed"], r["verdict"])
        self.assertEqual(r["n_models"], 2)
        crosscheck._Solver.DENSE_MAX = 0
        r2 = crosscheck.run(self.st, mids, sample=1000, model_ids=ids)
        self.assertEqual(r2["solver"], "GMRES with ILU preconditioner")
        self.assertLess(r2["max_relative_difference"], crosscheck._Solver.TOLERANCE)
        self.assertTrue(r2["passed"])
        self.assertLess(r["max_relative_difference"], 1e-12)          # dense LU: round-off only
        xl = os.path.join(self.dir, "x.xlsx")
        crosscheck.to_excel(xl, r2, "x")
        self.assertTrue(os.path.exists(xl))

    def test_detects_a_wrong_engine(self):
        mids = gwp(self.st)
        orig = calc.impacts
        try:
            def wrong(*a, **k):
                h, s, g = orig(*a, **k)
                return h * 1.0001, s, g
            calc.impacts = wrong
            r = crosscheck.run(self.st, mids, sample=50, model_ids=self._models())
        finally:
            calc.impacts = orig
        self.assertFalse(r["passed"])


class TestCfConflicts(Base):
    def test_conflicting_raw_factors_are_found(self):
        mid = next(m["id"] for m in self.st.methods() if m["category"] == "land use")
        from importers import lcia
        lcia.store_raw(self.st, mid, [("Occupation, arable land", "natural resource", "land", "", None, 1.0),
                                      ("Occupation, arable land", "natural resource", "land", "", None, 1.2)])
        c = trust.cf_conflicts(self.st, [mid])
        self.assertTrue(any(x["flow"].startswith("occupation, arable") and x["values"] >= 2 for x in c))


class TestLandUseReconciliation(unittest.TestCase):
    def test_gap_attributed_to_transformation(self):
        names = ["Occupation, arable", "Transformation, from forest", "Transformation, to urban", "Carbon dioxide"]

        class St:
            def flow(self, fid):
                return {"name": names[fid], "compartment": "natural resource", "subcompartment": "land"}

        class MC:
            flow_ids = np.arange(4)

        class Mx:
            C = np.array([[1.0, -2.0, 50.0, 0.0]])
        rng = np.random.default_rng(1)
        out, G = [], {}
        for d in range(12):
            g = np.array([rng.uniform(1, 10), rng.uniform(0, 0.1), rng.uniform(0, 0.1), 1.0])
            G[d] = g
            cy = float(Mx.C[0] @ g)
            ref = cy + 0.08 * 50.0 * g[2]           # ecoinvent factor for 'transformation, to' 8 % higher
            out.append({"category": "land use", "indicator": "soil quality", "reference": ref, "cyclia": cy, "act_id": d,
                        "note": "", "deviation_percent": (cy - ref) / ref * 100})
        res = trust.land_use_reconciliation(St(), MC(), Mx(), [{"method": {"category": "land use", "indicator": "soil quality"}}], out, G)
        g = {x["group"]: x for x in res[0]["groups"]}
        self.assertAlmostEqual(g["transformation, to"]["factor_change_percent"], 8.0, places=6)
        self.assertAlmostEqual(g["occupation"]["factor_change_percent"], 0.0, places=6)
        self.assertGreater(res[0]["explained"], 0.999)


if __name__ == "__main__":
    unittest.main()
