"""Custom data entry: a complete product system, its flows and its factors built from an empty library.

Hand calculation of the reference system (per 1 kg of steel sheet):
- steel: 2 kg CO2, 10 g solvent X, 3.6 MJ electricity (= 1 kWh), 0.2 kg waste to incineration, 0.1 kWh avoided;
- electricity: 0.5 kg CO2 per kWh;
- incineration (treatment): 1 kg CO2 per kg treated.
Climate change with CO2 = 1 and solvent X = 0.005 per g (= 5 per kg):
2 + 1 x 0.5 + 0.2 x 1 + 0.01 x 5 - 0.1 x 0.5 = 2.70 kg CO2-eq.
"""
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import custom_data as cd  # noqa: E402
from custom_data import CustomDataError  # noqa: E402
from importers import lcia, other_formats  # noqa: E402
from store import Workspace  # noqa: E402


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

    def build(self):
        st = self.st
        self.db = cd.create_database(st, "My data", "Primary data of plant A", author="N. Rehman")
        self.p_steel = cd.save_product(st, self.db, {"name": "steel sheet", "unit": "kg"})
        self.p_el = cd.save_product(st, self.db, {"name": "electricity", "unit": "kWh"})
        self.p_waste = cd.save_product(st, self.db, {"name": "steel waste", "unit": "kg"})
        self.co2 = cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                           "subcompartment": "unspecified", "unit": "kg", "cas": "124-38-9",
                                           "source": "ecoinvent elementary flow list"})
        self.solv = cd.save_elementary(st, {"name": "Solvent X", "compartment": "air",
                                            "subcompartment": "urban air close to ground", "unit": "kg",
                                            "source": "plant measurement 2025"})
        self.el = cd.save_process(st, self.db, {"name": "electricity, plant grid", "product": self.p_el, "amount": 1,
                                                "location": "PK", "source": "utility bill 2025",
                                                "dq": {"ter": 2, "ger": 1, "tir": 1, "p": 2}})
        cd.save_exchange(st, self.el, {"kind": "elementary", "flow": self.co2, "amount": 0.5, "unit": "kg",
                                       "source": "grid factor"})
        self.inc = cd.save_process(st, self.db, {"name": "incineration of steel waste", "product": self.p_waste,
                                                 "amount": 1, "type": "treatment", "source": "estimate"})
        cd.save_exchange(st, self.inc, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg"})
        self.steel = cd.save_process(st, self.db, {"name": "steel sheet rolling", "product": self.p_steel, "amount": 1,
                                                   "location": "PK", "source": "plant A, 2025"})
        cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": 2, "unit": "kg",
                                          "uncertainty": "pedigree", "pedigree": [2, 2, 1, 1, 2]})
        cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.solv, "amount": 10, "unit": "g",
                                          "uncertainty": "lognormal", "gsd": 1.5})
        cd.save_exchange(st, self.steel, {"kind": "technosphere", "supplier": self.el, "amount": 3.6, "unit": "MJ"})
        cd.save_exchange(st, self.steel, {"kind": "technosphere", "supplier": self.inc, "amount": 0.2, "unit": "kg",
                                          "uncertainty": "triangular", "min": 0.1, "mode": 0.2, "max": 0.4})
        cd.save_exchange(st, self.steel, {"kind": "technosphere", "supplier": self.el, "amount": 0.1, "unit": "kWh",
                                          "avoided": True, "uncertainty": "uniform", "min": 0.05, "max": 0.15})
        self.mid = cd.create_method(st, "My method", "climate change", "GWP100", "kg CO2-eq", "IPCC AR6, table 7.SM.7")
        cd.save_factor(st, self.mid, self.co2, "value", 1.0, "kg", source="IPCC AR6")
        cd.save_factor(st, self.mid, self.solv, "value", 0.005, "g", source="own estimate")

    def ref(self, uid):
        return self.st.one("SELECT ref_id FROM custom_items WHERE uuid=?", (uid,))["ref_id"]

    def calc(self, uid, mids=None):
        m = self.st.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(m, "activity", self.ref(uid), 1.0)
        calc.invalidate()
        return calc.run(self.st, m, mids or [self.mid])


class TestSupplyChain(Base):
    def test_hand_calculation(self):
        self.build()
        r = self.calc(self.steel)
        self.assertAlmostEqual(r["results"][0]["total"], 2.70, places=12)
        self.assertNotIn("factor_gaps", r["results"][0])
        self.assertEqual(r["factor_gaps"], 0)

    def test_treatment_and_avoided_signs(self):
        self.build()
        st = self.st
        t = {(x["input_id"]): x for x in st.q("SELECT * FROM tech WHERE output_id=?", (self.ref(self.steel),))}
        inc = t[self.ref(self.inc)]
        self.assertAlmostEqual(inc["amount"], -0.2)          # waste to a treatment dataset: negative input
        self.assertEqual((inc["p1"], inc["p2"], inc["p3"]), (-0.4, -0.2, -0.1))
        el = [x for x in st.q("SELECT * FROM tech WHERE output_id=? AND input_id=?",
                              (self.ref(self.steel), self.ref(self.el)))]
        self.assertEqual(sorted(round(x["amount"], 12) for x in el), [-0.1, 1.0])   # 3.6 MJ = 1 kWh; avoided 0.1
        av = [x for x in el if x["amount"] < 0][0]
        self.assertEqual((av["utype"], round(av["p1"], 12), round(av["p2"], 12)), (4, -0.15, -0.05))
        self.assertEqual(st.one("SELECT production FROM activities WHERE id=?", (self.ref(self.inc),))["production"], -1.0)

    def test_units_and_uncertainty_are_converted(self):
        self.build()
        b = {x["amount"]: x for x in self.st.q("SELECT * FROM bio WHERE activity_id=?", (self.ref(self.steel),))}
        sol = [x for x in b.values() if abs(x["amount"] - 0.01) < 1e-15][0]     # 10 g = 0.01 kg
        self.assertEqual(sol["utype"], 1)
        self.assertAlmostEqual(sol["p1"], math.log(1.5))
        co2 = [x for x in b.values() if x["amount"] == 2.0][0]
        self.assertAlmostEqual(co2["p1"], calc.pedigree_sigma([2, 2, 1, 1, 2], "flow", "Carbon dioxide, fossil"))

    def test_monte_carlo_runs(self):
        self.build()
        m = self.st.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(m, "activity", self.ref(self.steel), 1.0)
        calc.invalidate()
        r = calc.run(self.st, m, [self.mid], mc_iterations=200)
        self.assertAlmostEqual(r["results"][0]["total"], 2.70, places=12)

    def test_ids_stay_stable_and_models_stay_linked(self):
        self.build()
        before = self.ref(self.steel)
        cd.save_process(self.st, self.db, {"uuid": self.steel, "name": "steel sheet rolling, revised",
                                           "product": self.p_steel, "amount": 2, "source": "plant A, 2026"})
        self.assertEqual(self.ref(self.steel), before)
        it = self.st.one("SELECT revision FROM custom_items WHERE uuid=?", (self.steel,))
        self.assertEqual(it["revision"], 2)
        # reference amount 2 kg: every exchange now per 2 kg
        self.assertAlmostEqual(self.calc(self.steel)["results"][0]["total"], 1.35, places=12)

    def test_check_finds_missing_provenance_and_passes(self):
        self.build()
        c = cd.check(self.st, self.db)
        self.assertTrue(c["complete"], c)
        msgs = " ".join(f["message"] for f in c["findings"])
        self.assertIn("incineration of steel waste: no data quality rating", msgs)

    def test_library_dataset_as_supplier(self):
        b = other_formats._Builder(self.st, "Background", "test")
        b.activity("bg", "aluminium", "aluminium", "GLO", "kg", production=1.0)
        b.write(lambda *x: None)
        a = self.st.one("SELECT id FROM activities WHERE key='bg'")["id"]
        self.build()
        cd.save_exchange(self.st, self.steel, {"kind": "technosphere", "supplier": str(a), "amount": 500, "unit": "g"})
        t = self.st.one("SELECT amount FROM tech WHERE output_id=? AND input_id=?", (self.ref(self.steel), a))
        self.assertAlmostEqual(t["amount"], 0.5)


class TestFactors(Base):
    def test_unknown_factor_is_not_zero(self):
        self.build()
        new = cd.save_elementary(self.st, {"name": "Solvent Y", "compartment": "water", "subcompartment": "surface water",
                                           "unit": "kg"})
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": new, "amount": 1, "unit": "g"})
        r = self.calc(self.steel)
        gp = r["results"][0]["factor_gaps"]
        self.assertEqual(gp["n"], 1)
        self.assertEqual(gp["flows"][0]["name"], "Solvent Y")
        self.assertEqual(r["factor_gaps"], 1)
        self.assertTrue(any(c["level"] == "error" and "incomplete" in c["message"] for c in r["checks"]))
        cd.save_factor(self.st, self.mid, new, "not_applicable", comment="not a greenhouse gas")
        r = self.calc(self.steel)
        self.assertNotIn("factor_gaps", r["results"][0])
        self.assertAlmostEqual(r["results"][0]["total"], 2.70, places=12)

    def test_custom_flow_in_an_installed_method(self):
        self.build()
        mid = self.st.get_or_create_method("Installed", "climate change", "GWP100", "kg CO2-eq", "test")
        lcia.store_raw(self.st, mid, [("Carbon dioxide, fossil", "air", "unspecified", "", None, 1.0)])
        lcia.rematch(self.st, [mid])
        msgs = [f["message"] for f in cd.check(self.st, self.db)["findings"]]
        self.assertTrue(any("Solvent X" in m and "1 of 2" in m for m in msgs), msgs)
        self.assertFalse(any("Carbon dioxide" in m and "impact categories" in m for m in msgs), msgs)
        r = self.calc(self.steel, [mid])
        # CO2 is matched by name and context; solvent X has no factor in the installed method
        self.assertAlmostEqual(r["results"][0]["total"], 2 + 0.5 + 0.2 - 0.05, places=12)
        self.assertEqual([f["name"] for f in r["results"][0]["factor_gaps"]["flows"]], ["Solvent X"])
        cd.save_factor(self.st, mid, self.solv, "value", 5.0, "kg", source="own estimate")
        r = self.calc(self.steel, [mid])
        self.assertAlmostEqual(r["results"][0]["total"], 2.70, places=12)
        self.assertNotIn("factor_gaps", r["results"][0])
        # the installed method's own factor is untouched
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM cf_raw WHERE method_id=? AND flow_uuid IS NULL",
                                     (mid,))["n"], 1)

    def test_new_category_lists_every_custom_flow(self):
        self.build()
        m2 = cd.create_method(self.st, "My method", "acidification", "AP", "mol H+-eq", "own")
        r = self.calc(self.steel, [m2])
        self.assertEqual(r["results"][0]["factor_gaps"]["n"], 2)
        self.assertEqual(r["results"][0]["total"], 0.0)

    def test_factor_unit_conversion(self):
        self.build()
        f = self.st.one("SELECT value FROM custom_factors WHERE method_id=? AND flow_uuid=?", (self.mid, self.solv))
        self.assertAlmostEqual(f["value"], 5.0)
        with self.assertRaises(CustomDataError):
            cd.save_factor(self.st, self.mid, self.solv, "value", 1.0, "MJ", source="x")

    def test_factor_needs_a_source_and_a_reason(self):
        self.build()
        with self.assertRaises(CustomDataError):
            cd.save_factor(self.st, self.mid, self.solv, "value", 1.0, "kg", source="")
        with self.assertRaises(CustomDataError):
            cd.save_factor(self.st, self.mid, self.solv, "not_applicable", comment="")

    def test_installed_factors_of_library_flows_are_not_overwritten(self):
        self.build()
        b = other_formats._Builder(self.st, "Background", "test")
        a = b.activity("bg", "x", "x", "GLO", "kg", production=1.0)
        b.emission(a, "lib-ch4", "Methane, fossil", "air", "unspecified", "kg", 1.0)
        b.write(lambda *x: None)
        mid = self.st.get_or_create_method("Installed", "climate change", "GWP100", "kg CO2-eq", "test")
        with self.assertRaises(CustomDataError):
            cd.save_factor(self.st, mid, "lib-ch4", "value", 30, "kg", source="x")
        cd.save_factor(self.st, self.mid, "lib-ch4", "value", 29.8, "kg", source="IPCC AR6")   # custom method: allowed


class TestValidation(Base):
    def test_rejections(self):
        self.build()
        st = self.st
        bad = [
            lambda: cd.save_product(st, self.db, {"name": "x", "unit": "kilo"}),
            lambda: cd.save_product(st, self.db, {"name": "steel sheet", "unit": "kg"}),
            lambda: cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                            "subcompartment": "unspecified", "unit": "kg"}),
            lambda: cd.save_elementary(st, {"name": "Z", "compartment": "air", "subcompartment": "deep sea",
                                            "unit": "kg"}),
            lambda: cd.save_elementary(st, {"name": "Z", "compartment": "air", "subcompartment": "unspecified",
                                            "unit": "kg", "cas": "124-38-8"}),
            lambda: cd.save_elementary(st, {"name": "Occupation, urban", "compartment": "natural resource",
                                            "subcompartment": "land", "unit": "kg"}),
            lambda: cd.save_elementary(st, {"name": "Transformation, from forest", "compartment": "natural resource",
                                            "subcompartment": "land", "unit": "m2*a"}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "technosphere", "supplier": self.el, "amount": 1,
                                                      "unit": "kg"}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": -1,
                                                      "unit": "kg"}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": float("nan"),
                                                      "unit": "kg"}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg",
                                                      "uncertainty": "pedigree", "pedigree": [1, 2, 3]}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg",
                                                      "uncertainty": "triangular", "min": 2, "mode": 1, "max": 3}),
            lambda: cd.save_exchange(st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg",
                                                      "uncertainty": "lognormal", "gsd": 0.9}),
            lambda: cd.save_exchange(st, self.el, {"kind": "technosphere", "supplier": self.el, "amount": 1,
                                                   "unit": "kWh"}),
            lambda: cd.save_process(st, self.db, {"name": "x", "product": self.p_el, "amount": 1,
                                                  "dq": {"ter": 6, "ger": 1, "tir": 1, "p": 1}}),
            lambda: cd.save_process(st, self.db, {"name": "x", "product": self.p_el, "amount": 1, "dq": {"ter": 2}}),
            lambda: cd.delete_item(st, self.p_steel),
            lambda: cd.delete_item(st, self.el),
            lambda: cd.delete_item(st, self.co2),
        ]
        for i, f in enumerate(bad):
            with self.subTest(i=i), self.assertRaises(CustomDataError):
                f()

    def test_cas_checksum(self):
        self.assertTrue(cd.cas_ok("7732-18-5"))
        self.assertTrue(cd.cas_ok("124-38-9"))
        self.assertFalse(cd.cas_ok("124-38-8"))
        self.assertFalse(cd.cas_ok("12438-9"))

    def test_imported_database_cannot_be_edited(self):
        b = other_formats._Builder(self.st, "Background", "test")
        b.activity("bg", "x", "x", "GLO", "kg", production=1.0)
        b.write(lambda *x: None)
        dbid = self.st.one("SELECT id FROM databases WHERE name='Background'")["id"]
        with self.assertRaises(CustomDataError):
            cd.save_product(self.st, dbid, {"name": "x", "unit": "kg"})

    def test_unique_ids_and_provenance(self):
        self.build()
        rows = self.st.q("SELECT uuid, created, modified, author, source FROM custom_items")
        self.assertEqual(len({r["uuid"] for r in rows}), len(rows))
        for r in rows:
            self.assertEqual(len(r["uuid"]), 36)
            self.assertTrue(r["created"] and r["modified"])

    def test_removed_library_database_leaves_an_unresolved_input(self):
        b = other_formats._Builder(self.st, "Background", "test")
        b.activity("bg", "aluminium", "aluminium", "GLO", "kg", production=1.0)
        b.write(lambda *x: None)
        a = self.st.one("SELECT id FROM activities WHERE key='bg'")["id"]
        self.build()
        cd.save_exchange(self.st, self.steel, {"kind": "technosphere", "supplier": str(a), "amount": 1, "unit": "kg"})
        self.st.delete_database(self.st.one("SELECT id FROM databases WHERE name='Background'")["id"])
        cd.recompile_all(self.st)
        c = cd.check(self.st, self.db)
        self.assertFalse(c["complete"])
        self.assertTrue(any("no supplier" in f["message"] for f in c["findings"]))

    def test_deleted_process_leaves_no_exchanges(self):
        self.build()
        p = cd.save_process(self.st, self.db, {"name": "spare", "product": self.p_el, "amount": 1})
        cd.save_exchange(self.st, p, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg"})
        ref = self.ref(p)
        cd.delete_item(self.st, p)
        self.assertIsNone(self.st.one("SELECT 1 AS x FROM bio WHERE activity_id=?", (ref,)))
        self.assertIsNone(self.st.one("SELECT 1 AS x FROM activities WHERE id=?", (ref,)))

    def test_delete_and_database_removal(self):
        self.build()
        new = cd.save_product(self.st, self.db, {"name": "unused", "unit": "kg"})
        cd.delete_item(self.st, new)
        self.st.delete_database(self.db)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM custom_items WHERE kind IN ('product','process')")["n"], 0)
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM custom_exchanges")["n"], 0)


class TestBackup(Base):
    def test_json_round_trip(self):
        self.build()
        doc = cd.export_json(self.st, self.db)
        db2 = cd.import_json(self.st, doc, name="My data (copy)")
        steel2 = self.st.one("SELECT uuid FROM custom_items WHERE kind='process' AND db_id=? AND name=?",
                             (db2, "steel sheet rolling"))["uuid"]
        self.assertNotEqual(steel2, self.steel)
        self.assertAlmostEqual(self.calc(steel2)["results"][0]["total"], 2.70, places=12)
        d2 = cd.export_json(self.st, db2)
        ex = lambda d: sorted((p["name"], e["kind"], e["amount"], e["unit"], e["uncertainty"], e["avoided"])
                              for p in d["processes"] for e in p["exchanges"])
        self.assertEqual(ex(doc), ex(d2))

    def test_round_trip_into_an_empty_library(self):
        self.build()
        doc = cd.export_json(self.st, self.db)
        ws2 = Workspace(tempfile.mkdtemp())
        try:
            st2 = ws2.create("U")
            calc.invalidate()
            db = cd.import_json(st2, doc)
            steel = st2.one("SELECT ref_id FROM custom_items WHERE kind='process' AND db_id=? AND name=?",
                            (db, "steel sheet rolling"))["ref_id"]
            mid = st2.method_by_key("My method", "climate change", "GWP100")["id"]
            m = st2.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
            st2.add_input(m, "activity", steel, 1.0)
            calc.invalidate()
            self.assertAlmostEqual(calc.run(st2, m, [mid])["results"][0]["total"], 2.70, places=12)
        finally:
            ws2.close_all()
            calc.invalidate()


if __name__ == "__main__":
    unittest.main()
