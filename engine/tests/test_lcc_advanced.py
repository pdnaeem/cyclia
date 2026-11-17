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


class TestNestedLCC(unittest.TestCase):
    """Sub-models follow the line rules at every level (1.8.2). Child model: one pump at 100 per unit."""
    setUp = TestLCC.setUp
    tearDown = TestLCC.tearDown

    def child(self, **line):
        c = self.st.save_model({"name": "child", "product": "c", "unit": "unit", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        iid = self.st.add_input(c, "activity", self.a, 1.0)
        self.st.update_input(iid, {"unit_cost": 100, **line})
        return c

    def parent(self, scope, children, **line):
        m = self.st.save_model({"name": "parent", "product": "p", "unit": "unit", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-grave", **scope}})
        for c in children:
            iid = self.st.add_input(m, "model", c, 1.0)
            if line:
                self.st.update_input(iid, line)
        return analysis.lcc(calc.Context(self.st), m)

    def test_replacements_of_a_child_line(self):
        r = self.parent({"lcc_period": 20}, [self.child(replace_every=5)])
        self.assertAlmostEqual(r["total"], 400, places=9)               # 0, 5, 10, 15
        self.assertEqual(r["lines"][0]["replacements"], 3)
        r = self.parent({"lcc_period": 20}, [self.child(replace_every=6)])
        self.assertAlmostEqual(r["total"], 400 - 100 * 4 / 6, places=9)   # 0, 6, 12, 18; 4 of 6 years left
        self.assertAlmostEqual(r["residual_value"], -100 * 4 / 6, places=9)
        self.assertEqual(r["sub_model_items"][0]["path"], "child > pump")

    def test_escalation_and_discounting_of_a_child_line(self):
        c = self.child(replace_every=5, cost_type="maintenance")
        r = self.parent({"lcc_period": 20, "lcc_rate": 3, "lcc_escalation": {"maintenance": 2}}, [c])
        ys = (0, 5, 10, 15)
        self.assertAlmostEqual(r["total"], sum(100 * 1.02 ** y for y in ys), places=9)
        self.assertAlmostEqual(r["total_discounted"], sum(100 * 1.02 ** y / 1.03 ** y for y in ys), places=9)

    def test_child_replaced_with_its_sub_model(self):
        # the sub-model is replaced every 10 years; inside it the pump every 4 years
        r = self.parent({"lcc_period": 20}, [self.child(replace_every=4)], replace_every=10)
        self.assertAlmostEqual(r["total"], 600, places=9)               # 0, 4, 8 | 10, 14, 18
        r = self.parent({"lcc_period": 25}, [self.child(replace_every=4)], replace_every=10)
        # ... | 20, 24; the pump bought in year 24 has 3 of its 4 years left at 25
        self.assertAlmostEqual(r["total"], 800 - 75, places=9)

    def test_child_price_uncertainty(self):
        c = self.child(replace_every=5, cost_gsd=2.0)
        r = self.parent({"lcc_period": 20}, [c, c])                    # the same child twice: one price
        u = r["uncertainty"]
        self.assertEqual(u["lines"], 1)
        self.assertAlmostEqual(u["median"] / r["total_discounted"], 1.0, delta=0.08)
        self.assertAlmostEqual(u["p97_5"] / u["median"], 2.0 ** 1.96, delta=0.4)
        self.assertAlmostEqual(u["p2_5"] / u["median"], 2.0 ** -1.96, delta=0.05)

    def test_allocation_share_and_two_levels(self):
        """1.8.3 regression: the share of the study's main product (50 %) and a grandchild. The grandchild pump is
        replaced every 8 years inside a child bought once: 0, 8, 16 in 20 years, 4 of 8 years left at 20."""
        g = self.child(replace_every=8)
        c = self.st.save_model({"name": "assembly", "product": "a", "unit": "unit", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(c, "model", g, 1.0)
        r = self.parent({"lcc_period": 20, "alloc_share": 50}, [c])
        self.assertAlmostEqual(r["total"], 0.5 * (300 - 100 * 4 / 8), places=9)
        self.assertEqual(r["sub_model_items"][0]["path"], "assembly > child > pump")
        self.assertEqual(r["sub_model_items"][0]["purchases"], 3)

    def test_interval_longer_than_the_period(self):
        r = self.parent({"lcc_period": 20}, [self.child(replace_every=30)])
        self.assertAlmostEqual(r["total"], 100 - 100 * 10 / 30, places=9)   # one purchase, 10 of 30 years left

    def test_without_period_a_child_is_bought_once(self):
        r = self.parent({}, [self.child(replace_every=5)])
        self.assertAlmostEqual(r["total"], 100, places=9)


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
        self.assertAlmostEqual(by["no allocation (all lines, credit lines as entered, co-products not credited)"]["totals"][0],
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
