"""Life cycle costing (ISO 15686-5): escalation per cost type, residual value and price uncertainty, by hand."""
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
from store import Workspace  # noqa: E402


class TestLCC(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        db = self.st.create_database("bg", "test", "1", "test")
        with self.st.lock:
            self.a = self.st.conn.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) "
                                          "VALUES(?,?,?,?,?,?,1)", (db, "a", "pump", "pump", "GLO", "unit")).lastrowid
            self.st._bump_lib()
            self.st.conn.commit()
        calc.invalidate()

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def lcc(self, scope, **line):
        m = self.st.save_model({"name": "m", "product": "p", "unit": "unit", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-grave", **scope}})
        iid = self.st.add_input(m, "activity", self.a, 1.0)
        self.st.update_input(iid, {"unit_cost": 100, **line})
        return analysis.lcc(calc.Context(self.st), m)

    def test_replacements_and_residual_value(self):
        # bought in years 0, 10, 20 of a 25-year period; the last one has 5 of its 10 years left: -50
        r = self.lcc({"lcc_period": 25}, replace_every=10)
        self.assertAlmostEqual(r["total"], 300 - 50, places=9)
        self.assertAlmostEqual(r["residual_value"], -50, places=9)

    def test_discounting_and_escalation(self):
        r = self.lcc({"lcc_period": 25, "lcc_rate": 3, "lcc_escalation": {"maintenance": 2}}, replace_every=10,
                     cost_type="maintenance")
        buy = sum(100 * 1.02 ** y / 1.03 ** y for y in (0, 10, 20))
        res = -100 * 1.02 ** 20 * 0.5 / 1.03 ** 25
        self.assertAlmostEqual(r["total_discounted"], buy + res, places=9)
        self.assertAlmostEqual(r["total"], sum(100 * 1.02 ** y for y in (0, 10, 20)) - 100 * 1.02 ** 20 * 0.5, places=9)

    def test_residual_can_be_switched_off(self):
        r = self.lcc({"lcc_period": 25, "lcc_residual": False}, replace_every=10)
        self.assertAlmostEqual(r["total"], 300, places=9)

    def test_price_uncertainty(self):
        r = self.lcc({}, cost_gsd=1.5)
        u = r["uncertainty"]
        self.assertAlmostEqual(u["median"], 100, delta=4)
        self.assertAlmostEqual(u["p97_5"], 100 * 1.5 ** 1.96, delta=0.06 * 100 * 1.5 ** 1.96)
        self.assertAlmostEqual(u["p2_5"], 100 * 1.5 ** -1.96, delta=0.06 * 100 * 1.5 ** -1.96)


if __name__ == "__main__":
    unittest.main()


class TestModelAllocationCompare(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        self.st = self.ws.create("T")
        db = self.st.create_database("bg", "test", "1", "test")
        with self.st.lock:
            fid = self.st.add_flow("co2", "Carbon dioxide, fossil", "air", "unspecified", "kg", "")
            a = self.st.conn.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) "
                                     "VALUES(?,?,?,?,?,?,1)", (db, "a", "milk", "milk", "GLO", "kg")).lastrowid
            self.st.conn.execute("INSERT INTO bio(activity_id,flow_id,amount) VALUES(?,?,10)", (a, fid))
            self.st._bump_lib()
            self.st.conn.commit()
        self.mid = self.st.get_or_create_method("M", "cc", "cc", "kg CO2-eq", "t")
        from importers import lcia
        lcia.store_raw(self.st, self.mid, [("Carbon dioxide, fossil", "air", "unspecified", "", None, 1.0)])
        lcia.rematch(self.st, [self.mid])
        self.a = a
        calc.invalidate()

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_every_choice_matches_a_full_calculation(self):
        scope = {"goal": "g", "boundary": "cradle-to-gate", "alloc_basis": "mass", "main_mass": 1, "main_price": 3,
                 "coproducts": [{"name": "whey", "mass": 2, "price": 1}]}
        m = self.st.save_model({"name": "cheese", "product": "cheese", "unit": "kg", "amount": 1, "scope": scope})
        self.st.add_input(m, "activity", self.a, 1.0)
        calc.invalidate()
        r = calc.allocation_compare(self.st, m, [self.mid])
        by = {x["choice"]: x for x in r["rows"]}
        self.assertAlmostEqual(by["mass"]["totals"][0], 10 / 3, places=12)
        self.assertTrue(by["mass"]["current"])
        self.assertAlmostEqual(by["no allocation (system expansion: all burdens, credit lines as entered)"]["totals"][0],
                               10.0, places=12)
        self.assertFalse(by["energy"]["available"])
        # economic needs main_price stored: compute it with a full calculation under that basis and compare
        self.st.save_model({"id": m, "name": "cheese", "product": "cheese", "unit": "kg", "amount": 1,
                            "scope": {**scope, "alloc_basis": "price"}})
        calc.invalidate()
        full = calc.run(self.st, m, [self.mid])["results"][0]["total"]
        self.assertAlmostEqual(full, 7.5, places=12)
        by2 = {x["choice"]: x for x in calc.allocation_compare(self.st, m, [self.mid])["rows"]}
        self.assertAlmostEqual(by2["economic"]["totals"][0], full, places=12)
        self.assertAlmostEqual(by2["mass"]["totals"][0], 10 / 3, places=12)
