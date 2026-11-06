"""Custom data entry: a complete product system, its flows and its factors built from an empty library.

Hand calculation of the reference system (per 1 kg of steel sheet):
- steel: 2 kg CO2, 10 g solvent X, 3.6 MJ electricity (= 1 kWh), 0.2 kg waste to incineration, 0.1 kWh avoided;
- electricity: 0.5 kg CO2 per kWh;
- incineration (treatment): 1 kg CO2 per kg treated.
Climate change with CO2 = 1 and solvent X = 0.005 per g (= 5 per kg):
2 + 1 x 0.5 + 0.2 x 1 + 0.01 x 5 - 0.1 x 0.5 = 2.70 kg CO2-eq.
"""
import json
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


class TestReview161(Base):
    """Defects reported in the review of 1.6.0 and the additions of 1.6.1."""

    def lib_methane(self):
        """A library flow, as an installed database would bring it."""
        with self.st.lock:
            self.st.add_flow("lib-ch4", "Methane, fossil", "air", "unspecified", "kg", "74-82-8")
            self.st.conn.commit()

    def test_library_flow_in_custom_method_is_unknown_not_zero(self):
        self.lib_methane()
        self.build()
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": "lib-ch4", "amount": 1, "unit": "kg"})
        r = self.calc(self.steel)
        gp = r["results"][0]["factor_gaps"]
        self.assertEqual([f["name"] for f in gp["flows"]], ["Methane, fossil"])
        self.assertTrue(gp["custom_method"])
        self.assertAlmostEqual(r["results"][0]["total"], 2.70, places=12)   # methane not counted, and flagged
        msgs = [f["message"] for f in cd.check(self.st, self.db)["findings"]]
        self.assertTrue(any("Methane, fossil" in m and "Custom method" in m for m in msgs), msgs)
        # giving the factor completes the result
        cd.save_factor(self.st, self.mid, "lib-ch4", "value", 29.8, "kg", source="IPCC AR6, table 7.15")
        r = self.calc(self.steel)
        self.assertNotIn("factor_gaps", r["results"][0])
        self.assertAlmostEqual(r["results"][0]["total"], 2.70 + 29.8, places=10)

    def test_method_scope_no_effect_needs_a_reason(self):
        self.lib_methane()
        self.build()
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": "lib-ch4", "amount": 1, "unit": "kg"})
        with self.assertRaises(CustomDataError):
            cd.set_method_scope(self.st, self.mid, "zero", "")
        cd.set_method_scope(self.st, self.mid, "zero", "The method lists every greenhouse gas it covers.")
        r = self.calc(self.steel)
        self.assertNotIn("factor_gaps", r["results"][0])
        # custom flows stay unknown even then
        new = cd.save_elementary(self.st, {"name": "Gas Z", "compartment": "air", "subcompartment": "unspecified",
                                           "unit": "kg"})
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": new, "amount": 1, "unit": "kg"})
        self.assertEqual(self.calc(self.steel)["results"][0]["factor_gaps"]["flows"][0]["name"], "Gas Z")
        with self.assertRaises(CustomDataError):
            cd.set_method_scope(self.st, 999999, "zero", "x")

    def test_recorded_zero_factor_is_known(self):
        self.build()
        new = cd.save_elementary(self.st, {"name": "Argon (example)", "compartment": "air",
                                           "subcompartment": "unspecified", "unit": "kg"})
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": new, "amount": 1, "unit": "kg"})
        self.assertIn("factor_gaps", self.calc(self.steel)["results"][0])
        cd.save_factor(self.st, self.mid, new, "value", 0.0, "kg", source="IPCC AR6: no radiative forcing")
        r = self.calc(self.steel)
        self.assertNotIn("factor_gaps", r["results"][0])
        rows = [x for x in cd.factor_table(self.st, [self.mid]) if x["flow_uuid"] == new]
        self.assertEqual((rows[0]["status"], rows[0]["value"]), ("value", 0.0))
        self.assertFalse(any("Argon" in f["message"] for f in cd.check(self.st, self.db)["findings"]))

    def test_installed_method_zero_factor_is_known(self):
        self.build()
        mid = self.st.get_or_create_method("Installed", "climate change", "GWP100", "kg CO2-eq", "test")
        lcia.store_raw(self.st, mid, [("Carbon dioxide, fossil", "air", "unspecified", "", None, 1.0),
                                      ("Solvent X", "air", "urban air close to ground", "", None, 0.0)])
        lcia.rematch(self.st, [mid])
        self.assertNotIn("factor_gaps", self.calc(self.steel, [mid])["results"][0])

    def test_product_rename_updates_the_dataset(self):
        self.build()
        cd.save_product(self.st, self.db, {"uuid": self.p_steel, "name": "cold-rolled steel sheet", "unit": "kg"})
        a = self.st.one("SELECT product FROM activities WHERE id=?", (self.ref(self.steel),))
        self.assertEqual(a["product"], "cold-rolled steel sheet")

    def test_elementary_flow_edit_rematches_factors(self):
        self.build()
        mid = self.st.get_or_create_method("Installed", "climate change", "GWP100", "kg CO2-eq", "test")
        lcia.store_raw(self.st, mid, [("Solvent X", "air", "urban air close to ground", "", None, 3.0)])
        lcia.rematch(self.st, [mid])
        r = self.calc(self.steel, [mid])
        self.assertAlmostEqual(r["results"][0]["total"], 0.01 * 3.0, places=12)
        cd.save_elementary(self.st, {"uuid": self.solv, "name": "Solvent X", "compartment": "water",
                                     "subcompartment": "surface water", "unit": "kg"})
        r = self.calc(self.steel, [mid])
        self.assertEqual(r["results"][0]["total"], 0.0)          # the air factor no longer applies
        self.assertIn("factor_gaps", r["results"][0])           # and the water factor is unknown
        self.lib_methane()
        with self.assertRaises(CustomDataError):                # library flows are not edited here
            cd.save_elementary(self.st, {"uuid": "lib-ch4", "name": "Methane", "compartment": "air",
                                         "subcompartment": "unspecified", "unit": "kg"})

    def test_exchange_edit_keeps_id_and_counts_revisions(self):
        self.build()
        ex = cd.contents(self.st, self.db)
        e = [x for p in ex["processes"] if p["uuid"] == self.steel for x in p["exchanges"]
             if x["kind"] == "elementary" and x["amount"] == 2.0][0]
        cd.save_exchange(self.st, self.steel, {"id": e["id"], "kind": "elementary", "flow": self.co2, "amount": 3,
                                               "unit": "kg", "author": "reviewer", "source": "remeasured"})
        e2 = [x for p in cd.contents(self.st, self.db)["processes"] if p["uuid"] == self.steel
              for x in p["exchanges"] if x["id"] == e["id"]][0]
        self.assertEqual((e2["amount"], e2["revision"], e2["author"]), (3.0, 2, "reviewer"))
        self.assertAlmostEqual(self.calc(self.steel)["results"][0]["total"], 3.70, places=12)
        h = cd.history(self.st, self.steel)
        self.assertEqual(h[0]["action"], "exchange changed")
        self.assertEqual(h[0]["author"], "reviewer")
        self.assertTrue(any(x["action"] == "created" for x in h))

    def test_worked_example(self):
        r = cd.example(self.st)
        p = self.st.one("SELECT ref_id FROM custom_items WHERE uuid=?", (r["process"],))["ref_id"]
        m = self.st.save_model({"name": "m", "product": "bread", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(m, "activity", p, 1.0)
        calc.invalidate()
        res = calc.run(self.st, m, [r["method_id"]])["results"][0]
        self.assertAlmostEqual(res["total"], 0.437, places=12)
        self.assertNotIn("factor_gaps", res)
        self.assertTrue(cd.check(self.st, r["db_id"])["complete"])
        with self.assertRaises(CustomDataError):
            cd.example(self.st)

    def test_custom_method_delete_and_scope_round_trip(self):
        self.build()
        cd.set_method_scope(self.st, self.mid, "zero", "complete list")
        doc = cd.export_json(self.st, self.db)
        self.assertEqual(doc["methods"][0]["unlisted"], "zero")
        m2 = cd.create_method(self.st, "Tmp", "x", "x", "u", "src")
        cd.delete_method(self.st, m2)
        self.assertIsNone(self.st.one("SELECT 1 AS x FROM methods WHERE id=?", (m2,)))
        with self.assertRaises(CustomDataError):
            cd.delete_method(self.st, 999999)


class TestParametersAndFormulas(Base):
    def setup_bakery(self):
        st = self.st
        self.db = cd.create_database(st, "Bakery", author="t")
        self.p_bread = cd.save_product(st, self.db, {"name": "bread", "unit": "kg"})
        self.p_flour = cd.save_product(st, self.db, {"name": "flour", "unit": "kg"})
        self.co2 = cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                           "subcompartment": "unspecified", "unit": "kg"})
        self.flour = cd.save_process(st, self.db, {"name": "flour", "product": self.p_flour, "amount": 1})
        cd.save_exchange(st, self.flour, {"kind": "elementary", "flow": self.co2, "amount": 0.4, "unit": "kg"})
        cd.set_database_parameters(st, self.db, [{"name": "loss", "value": 0.2}])
        self.bread = cd.save_process(st, self.db, {"name": "bread", "product": self.p_bread, "amount": 1,
                                                   "parameters": [{"name": "dough", "value": 0.65},
                                                                  {"name": "flour_in", "formula": "dough / (1 - loss)"}]})
        self.ex = cd.save_exchange(st, self.bread, {"kind": "technosphere", "supplier": self.flour,
                                                    "formula": "flour_in * 1000", "unit": "g",
                                                    "uncertainty": "lognormal", "gsd": 1.1})
        self.mid = cd.create_method(st, "M", "climate change", "GWP", "kg CO2-eq", "src")
        cd.save_factor(st, self.mid, self.co2, "value", 1.0, "kg", source="src")

    def test_formula_with_database_and_process_parameters(self):
        self.setup_bakery()
        # 0.65 / 0.8 = 0.8125 kg flour, x 0.4 kg CO2
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 0.8125 * 0.4, places=12)
        e = self.st.one("SELECT amount, amount_ref, unit_factor FROM custom_exchanges WHERE id=?", (self.ex,))
        self.assertAlmostEqual(e["amount"], 812.5)
        self.assertAlmostEqual(e["amount_ref"], 0.8125)

    def test_changing_a_parameter_recalculates(self):
        self.setup_bakery()
        cd.set_database_parameters(self.st, self.db, [{"name": "loss", "value": 0.35}])
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 0.65 / 0.65 * 0.4, places=12)

    def test_process_parameter_overrides_database_parameter(self):
        self.setup_bakery()
        cd.save_process(self.st, self.db, {"uuid": self.bread, "name": "bread", "product": self.p_bread, "amount": 1,
                                           "parameters": [{"name": "dough", "value": 0.65}, {"name": "loss", "value": 0.5},
                                                          {"name": "flour_in", "formula": "dough / (1 - loss)"}]})
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 1.3 * 0.4, places=12)

    def test_bad_parameters_are_refused_and_nothing_changes(self):
        self.setup_bakery()
        bad = [[{"name": "loss", "value": 1.5}],                     # flour_in negative
               [{"name": "loss", "formula": "loss + 1"}],            # depends on itself
               [{"name": "loss", "formula": "1 +"}],                 # does not parse
               [{"name": "2x", "value": 1}],                         # invalid name
               [{"name": "loss", "value": 0.1}, {"name": "loss", "value": 0.2}]]
        for b in bad:
            with self.subTest(b=b), self.assertRaises(CustomDataError):
                cd.set_database_parameters(self.st, self.db, b)
        self.assertEqual(cd._db_params(self.st, self.db)[0]["value"], 0.2)
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 0.8125 * 0.4, places=12)
        with self.assertRaises(CustomDataError):            # a process edit that breaks a formula is refused too
            cd.save_process(self.st, self.db, {"uuid": self.bread, "name": "bread", "product": self.p_bread,
                                               "amount": 1, "parameters": [{"name": "dough", "value": 0.65}]})
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 0.8125 * 0.4, places=12)

    def test_formula_rules(self):
        self.setup_bakery()
        with self.assertRaises(CustomDataError):
            cd.save_exchange(self.st, self.bread, {"kind": "elementary", "flow": self.co2, "formula": "dough * 2",
                                                   "unit": "kg", "uncertainty": "triangular", "min": 1, "mode": 1.3,
                                                   "max": 2})
        with self.assertRaises(CustomDataError):
            cd.save_exchange(self.st, self.bread, {"kind": "elementary", "flow": self.co2, "formula": "unknown_p",
                                                   "unit": "kg"})
        with self.assertRaises(CustomDataError):
            cd.save_exchange(self.st, self.bread, {"kind": "elementary", "flow": self.co2, "formula": "0 - dough",
                                                   "unit": "kg"})
        cd.save_exchange(self.st, self.bread, {"kind": "elementary", "flow": self.co2, "formula": "dough * 0",
                                               "unit": "kg"})                   # zero is allowed (a switch)
        self.assertAlmostEqual(self.calc(self.bread)["results"][0]["total"], 0.8125 * 0.4, places=12)


class TestCoproducts(Base):
    """A dairy makes 1 kg cheese (price 3) and 2 kg whey (price 0.5) and emits 10 kg CO2.
    Economic: cheese 3 / (3 + 1) = 75 % -> 7.5 kg CO2 per kg; whey 2.5 for 2 kg -> 1.25 per kg.
    Mass: 1 / 3 and 2 / 3 -> 3.333 kg CO2 per kg of each. Both conserve the 10 kg."""

    def setup_dairy(self, method="economic", values=None):
        st = self.st
        self.db = cd.create_database(st, "Dairy")
        self.cheese = cd.save_product(st, self.db, {"name": "cheese", "unit": "kg"})
        self.whey = cd.save_product(st, self.db, {"name": "whey", "unit": "kg"})
        self.co2 = cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                           "subcompartment": "unspecified", "unit": "kg"})
        self.proc = cd.save_process(st, self.db, {
            "name": "cheese making", "product": self.cheese, "amount": 1,
            "coproducts": [{"product": self.whey, "amount": 2}],
            "allocation": {"method": method, "values": values if values is not None else {self.cheese: 3, self.whey: 0.5}}})
        cd.save_exchange(st, self.proc, {"kind": "elementary", "flow": self.co2, "amount": 10, "unit": "kg",
                                         "uncertainty": "normal", "sd": 1})
        self.mid = cd.create_method(st, "M", "climate change", "GWP", "kg CO2-eq", "src")
        cd.save_factor(st, self.mid, self.co2, "value", 1.0, "kg", source="src")

    def whey_ref(self):
        return json.loads(self.st.one("SELECT data FROM custom_items WHERE uuid=?", (self.proc,))["data"])[
            "coproduct_refs"][self.whey]

    def per_kg(self, ref):
        m = self.st.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(m, "activity", ref, 1.0)
        calc.invalidate()
        return calc.run(self.st, m, [self.mid])["results"][0]["total"]

    def test_economic_allocation(self):
        self.setup_dairy()
        self.assertAlmostEqual(self.per_kg(self.ref(self.proc)), 7.5, places=12)
        self.assertAlmostEqual(self.per_kg(self.whey_ref()), 1.25, places=12)
        b = self.st.one("SELECT amount, p1 FROM bio WHERE activity_id=?", (self.whey_ref(),))
        self.assertAlmostEqual(b["amount"], 2.5)
        self.assertAlmostEqual(b["p1"], 0.25)                     # standard deviation scaled with the share
        tot = sum(r["amount"] for r in self.st.q("SELECT amount FROM bio WHERE activity_id IN (?,?)",
                                                   (self.ref(self.proc), self.whey_ref())))
        self.assertAlmostEqual(tot, 10.0)                        # nothing lost, nothing counted twice

    def test_mass_allocation_from_units(self):
        self.setup_dairy("mass", {})
        self.assertAlmostEqual(self.per_kg(self.ref(self.proc)), 10 / 3, places=12)
        self.assertAlmostEqual(self.per_kg(self.whey_ref()), 10 / 3, places=12)

    def test_manual_shares_must_add_up_to_one(self):
        with self.assertRaises(CustomDataError):
            self.setup_dairy("manual", {})
        self.tearDown(); self.setUp()
        with self.assertRaises(CustomDataError):
            self.setup_dairy("manual", {"x": 1})
        self.tearDown(); self.setUp()
        self.st2 = None
        st = self.st
        db = cd.create_database(st, "D")
        a = cd.save_product(st, db, {"name": "a", "unit": "kg"})
        b = cd.save_product(st, db, {"name": "b", "unit": "kg"})
        with self.assertRaises(CustomDataError):
            cd.save_process(st, db, {"name": "p", "product": a, "amount": 1, "coproducts": [{"product": b, "amount": 1}],
                                     "allocation": {"method": "manual", "values": {a: 0.5, b: 0.6}}})
        self.assertIsNone(st.one("SELECT 1 AS x FROM custom_items WHERE kind='process'"))   # nothing left behind
        cd.save_process(st, db, {"name": "p", "product": a, "amount": 1, "coproducts": [{"product": b, "amount": 1}],
                                 "allocation": {"method": "manual", "values": {a: 0.4, b: 0.6}}})

    def test_consuming_a_coproduct(self):
        self.setup_dairy()
        feed = cd.save_product(self.st, self.db, {"name": "pig feed", "unit": "kg"})
        pf = cd.save_process(self.st, self.db, {"name": "feed mixing", "product": feed, "amount": 1})
        cd.save_exchange(self.st, pf, {"kind": "technosphere", "supplier": f"{self.proc}/{self.whey}", "amount": 500,
                                       "unit": "g"})
        self.assertAlmostEqual(self.per_kg(self.ref(pf)), 0.5 * 1.25, places=12)
        with self.assertRaises(CustomDataError):                # the whey is used: it cannot be removed
            cd.save_process(self.st, self.db, {"uuid": self.proc, "name": "cheese making", "product": self.cheese,
                                               "amount": 1})
        with self.assertRaises(CustomDataError):
            cd.delete_item(self.st, self.proc)

    def test_removing_a_coproduct_removes_its_dataset(self):
        self.setup_dairy()
        ref = self.whey_ref()
        cd.save_process(self.st, self.db, {"uuid": self.proc, "name": "cheese making", "product": self.cheese,
                                           "amount": 1})
        self.assertIsNone(self.st.one("SELECT 1 AS x FROM activities WHERE id=?", (ref,)))
        self.assertAlmostEqual(self.per_kg(self.ref(self.proc)), 10.0, places=12)

    def test_rules(self):
        self.setup_dairy()
        with self.assertRaises(CustomDataError):                # no allocation method
            cd.save_process(self.st, self.db, {"uuid": self.proc, "name": "x", "product": self.cheese, "amount": 1,
                                               "coproducts": [{"product": self.whey, "amount": 2}]})
        with self.assertRaises(CustomDataError):                # treatment with co-products
            cd.save_process(self.st, self.db, {"name": "y", "product": self.cheese, "amount": 1, "type": "treatment",
                                               "coproducts": [{"product": self.whey, "amount": 2}],
                                               "allocation": {"method": "mass"}})
        with self.assertRaises(CustomDataError):                # the same product twice
            cd.save_process(self.st, self.db, {"name": "z", "product": self.cheese, "amount": 1,
                                               "coproducts": [{"product": self.cheese, "amount": 2}],
                                               "allocation": {"method": "mass"}})
        e = cd.save_product(self.st, self.db, {"name": "heat", "unit": "MJ"})
        with self.assertRaises(CustomDataError):                # mass allocation needs kg per MJ of heat
            cd.save_process(self.st, self.db, {"name": "w", "product": self.cheese, "amount": 1,
                                               "coproducts": [{"product": e, "amount": 2}],
                                               "allocation": {"method": "mass"}})


class TestUnits(Base):
    def test_unit_in_a_known_dimension(self):
        self.build()
        cd.save_unit(self.st, {"name": "bag", "dimension": "mass", "factor": 25, "source": "supplier sheet"})
        cd.save_exchange(self.st, self.steel, {"kind": "elementary", "flow": self.co2, "amount": 0.004, "unit": "bag"})
        self.assertAlmostEqual(self.calc(self.steel)["results"][0]["total"], 2.70 + 0.1, places=12)
        with self.assertRaises(CustomDataError):                # in use: its size cannot change
            cd.save_unit(self.st, {"name": "bag", "dimension": "mass", "factor": 20})
        with self.assertRaises(CustomDataError):
            cd.delete_unit(self.st, "bag")
        with self.assertRaises(CustomDataError):
            cd.save_unit(self.st, {"name": "kg", "dimension": "mass", "factor": 1})
        with self.assertRaises(CustomDataError):
            cd.save_unit(self.st, {"name": "box", "dimension": "mass", "factor": -1})

    def test_new_kind_of_quantity(self):
        self.build()
        cd.save_unit(self.st, {"name": "seat", "dimension": "new"})
        cd.save_unit(self.st, {"name": "row", "dimension": "custom:seat", "factor": 20})
        seats = cd.save_product(self.st, self.db, {"name": "cinema seat", "unit": "seat"})
        hall = cd.save_product(self.st, self.db, {"name": "cinema hall", "unit": "unit"})
        ps = cd.save_process(self.st, self.db, {"name": "seat making", "product": seats, "amount": 1})
        cd.save_exchange(self.st, ps, {"kind": "elementary", "flow": self.co2, "amount": 5, "unit": "kg"})
        ph = cd.save_process(self.st, self.db, {"name": "hall fitting", "product": hall, "amount": 1})
        cd.save_exchange(self.st, ph, {"kind": "technosphere", "supplier": ps, "amount": 10, "unit": "row"})
        self.assertAlmostEqual(self.calc(ph)["results"][0]["total"], 200 * 5, places=9)
        with self.assertRaises(CustomDataError):
            cd.save_exchange(self.st, ph, {"kind": "technosphere", "supplier": ps, "amount": 1, "unit": "kg"})
        with self.assertRaises(CustomDataError):
            cd.delete_unit(self.st, "seat")                     # used, and 'row' is defined from it

    def test_units_survive_a_restart(self):
        cd.save_unit(self.st, {"name": "bag", "dimension": "mass", "factor": 25})
        self.ws.close_all()
        import units
        units.set_custom([])
        self.ws = Workspace(self.dir)
        self.st = self.ws.open("T")
        self.assertEqual(units.factor("bag", "kg"), 25.0)


class TestRoundTripAll(Base):
    def test_everything_survives_export_and_import_into_an_empty_library(self):
        st = self.st
        cd.save_unit(st, {"name": "bag", "dimension": "mass", "factor": 25})
        db = cd.create_database(st, "Full")
        cd.set_database_parameters(st, db, [{"name": "k", "value": 2}])
        a = cd.save_product(st, db, {"name": "a", "unit": "kg"})
        b = cd.save_product(st, db, {"name": "b", "unit": "bag"})
        co2 = cd.save_elementary(st, {"name": "Gas Q", "compartment": "air", "subcompartment": "unspecified",
                                      "unit": "kg"})
        p = cd.save_process(st, db, {"name": "p", "product": a, "amount": 1, "coproducts": [{"product": b, "amount": 1}],
                                     "allocation": {"method": "mass"}, "parameters": [{"name": "m", "formula": "k * 3"}]})
        cd.save_exchange(st, p, {"kind": "elementary", "flow": co2, "formula": "m", "unit": "kg"})
        user = cd.save_product(st, db, {"name": "c", "unit": "kg"})
        pu = cd.save_process(st, db, {"name": "user", "product": user, "amount": 1})
        cd.save_exchange(st, pu, {"kind": "technosphere", "supplier": f"{p}/{b}", "amount": 2, "unit": "bag"})
        mid = cd.create_method(st, "M", "x", "x", "u", "src")
        cd.save_factor(st, mid, co2, "value", 1, "kg", source="s")
        # 6 kg gas, mass shares 1 : 25 -> b gets 25/26; 2 bags of b -> 2 x 6 x 25/26
        expect = 2 * 6 * 25 / 26
        self.assertAlmostEqual(self.calc(pu, [mid])["results"][0]["total"], expect, places=12)
        doc = json.loads(json.dumps(cd.export_json(st, db)))
        ws2 = Workspace(tempfile.mkdtemp())
        try:
            import units
            units.set_custom([])
            st2 = ws2.create("U")
            calc.invalidate()
            db2 = cd.import_json(st2, doc)
            ref = st2.one("SELECT ref_id FROM custom_items WHERE kind='process' AND db_id=? AND name='user'", (db2,))["ref_id"]
            m2 = st2.method_by_key("M", "x", "x")["id"]
            mm = st2.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                 "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
            st2.add_input(mm, "activity", ref, 1.0)
            calc.invalidate()
            self.assertAlmostEqual(calc.run(st2, mm, [m2])["results"][0]["total"], expect, places=12)
        finally:
            ws2.close_all()
            calc.invalidate()

    def test_layout_is_not_a_revision(self):
        self.build()
        r0 = self.st.one("SELECT revision FROM custom_items WHERE uuid=?", (self.steel,))["revision"]
        cd.save_layout(self.st, self.steel, 120, 40)
        it = self.st.one("SELECT revision, data FROM custom_items WHERE uuid=?", (self.steel,))
        self.assertEqual(it["revision"], r0)
        self.assertEqual(json.loads(it["data"])["layout"], [120.0, 40.0])


if __name__ == "__main__":
    unittest.main()
