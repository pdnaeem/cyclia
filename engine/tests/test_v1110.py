"""Cyclia 1.10.0, modelling step of the road to 2.0: end-of-life approaches side by side, the supply chain tree,
subdivision of multi-output processes and named process versions."""
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
import custom_data as cd  # noqa: E402
from custom_data import CustomDataError  # noqa: E402
import supplychain  # noqa: E402
from importers import demo, tutorial  # noqa: E402
from store import Workspace  # noqa: E402


class TestEolCoefficients(unittest.TestCase):
    def totals(self, p):
        co, _ = analysis.eol_coefficients(p)
        E = {"virgin": 10.0, "recycled": 3.0, "recycling_eol": 2.0, "avoided_virgin": 10.0, "disposal": 1.0}
        return {a: sum(co[a][r] * E[r] for r in E) for a in co}

    def test_hand_calculated(self):
        # Ev 10, ERin 3, ERout 2, E*v 10, ED 1; R1 0.3, R2 0.6, A 0.5, Q 1
        t = self.totals({"R1": 0.3, "R2": 0.6, "A": 0.5})
        self.assertAlmostEqual(t["cut-off"], 0.7 * 10 + 0.3 * 3 + 0.4 * 1)                       # 8.3
        self.assertAlmostEqual(t["end-of-life recycling"], 10 + 0.6 * (2 - 10) + 0.4 * 1)       # 5.6
        self.assertAlmostEqual(t["50:50"], 0.5 * (0.7 + 0.4) * (10 + 1) + 0.5 * (0.3 * 3 + 0.6 * 2))   # 7.1
        self.assertAlmostEqual(t["Circular Footprint Formula"],
                               0.7 * 10 + 0.3 * (0.5 * 3 + 0.5 * 10) + 0.5 * 0.6 * (2 - 10) + 0.4 * 1)  # 6.95
        self.assertAlmostEqual(t["Circular Footprint Formula"], 6.95)

    def test_without_recycling_all_approaches_agree(self):
        t = self.totals({"R1": 0, "R2": 0})
        self.assertTrue(all(abs(v - 11.0) < 1e-12 for v in t.values()), t)

    def test_cff_matches_the_cff_lines(self):
        p = {"R1": 0.2, "R2": 0.7, "A": 0.2, "Qsin": 0.9, "Qsout": 0.8}
        co, _ = analysis.eol_coefficients(p)
        lines, _ = analysis.cff_lines(p)
        L = {r: (-c if credit else c) for r, c, credit in lines}
        for role, c in co["Circular Footprint Formula"].items():
            self.assertAlmostEqual(c, L.get(role, 0.0), msg=role)

    def test_published_cff_example(self):
        """Rickert and Ciroth (2020), 'Application of the Circular Footprint Formula', GreenDelta: mixed pulp for a
        solid board box with the PEF Annex C (v2.1, May 2020) values for paper, A = 0.2 and R1 = 0.47, Qsin/Qp = 1,
        and R2 = R3 = ED = 0 (cradle-to-gate, PEFCR intermediate paper product). Their vectors of virgin pulp (Ev) and
        recycled pulp (Erecycled) per kg of pulp give the published ECFF vector."""
        p = {"A": 0.2, "R1": 0.47, "Qsin": 1.0, "R2": 0.0, "R3": 0.0}
        lines, _ = analysis.cff_lines(p)
        L = {r: c for r, c, _ in lines}
        self.assertAlmostEqual(L["virgin"], 0.906, places=12)
        self.assertAlmostEqual(L["recycled"], 0.094, places=12)
        self.assertEqual([r for r, c, _ in lines if c and r not in ("virgin", "recycled", "disposal")], [])
        co, _ = analysis.eol_coefficients(p)
        self.assertAlmostEqual(co["Circular Footprint Formula"]["virgin"], 0.906, places=12)
        self.assertAlmostEqual(co["Circular Footprint Formula"]["recycled"], 0.094, places=12)
        # flow: (Ev, Erecycled, published ECFF); the paper gives ECFF to four significant digits
        flows = {"wood": (-3, 0, -2.718), "pulp": (1, 1, 1), "recycled paper": (0, -2, -0.188),
                 "energy": (-15, -5, -14.06), "water": (-20, -10, -19.06), "chemical": (-0.2, -0.1, -0.1906),
                 "PM emissions": (0.0008, 0.0006, 0.0007812), "CO2 to air": (0.009, 0.007, 0.008812),
                 "waste water": (19, 9, 18.06), "residues": (5, 0.5, 4.577)}
        for name, (ev, erec, pub) in flows.items():
            with self.subTest(flow=name):
                got = L["virgin"] * ev + L["recycled"] * erec
                self.assertAlmostEqual(got, pub, delta=abs(pub) * 5e-4 + 1e-15)

    def test_parameters_are_checked(self):
        for bad in ({"R1": 1.2}, {"R2": True}, {"A": "x"}, {"R1": float("inf")}):
            with self.assertRaises(ValueError):
                analysis.eol_coefficients(bad)


class Lib(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.ws = Workspace(cls.dir)
        cls.st = cls.ws.create("P")
        tutorial.install(cls.st)
        demo.install_database(cls.st)
        calc.invalidate()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close_all()
        calc.invalidate()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def unit_score(self, act_id, mid):
        mc = calc._cache.get(self.st)
        M = calc.Methods(self.st, mc, [mid])
        f = np.zeros(mc.n)
        f[mc.act_index[act_id]] = 1.0
        return float((M.Q @ mc.solve(f))[0])

    def method(self, word="climate"):
        return next(m for m in self.st.methods() if word in m["category"])


class TestEolCompare(Lib):
    def test_results_are_coefficients_times_dataset_results(self):
        st = self.st
        acts = [a for a in st.q("SELECT id, unit FROM activities WHERE unit='kg' ORDER BY id")][:4]
        ds = {"virgin": acts[0]["id"], "recycled": acts[1]["id"], "recycling_eol": acts[2]["id"],
              "disposal": acts[3]["id"]}
        m = self.method()
        r = analysis.eol_compare(st, {"R1": 0.3, "R2": 0.6, "A": 0.5}, ds, [m["id"]], mass=2.0, unit="kg")
        E = {k: self.unit_score(v, m["id"]) * 2.0 for k, v in ds.items()}
        E["avoided_virgin"] = E["virgin"]
        co = r["coefficients"]
        for ap in r["approaches"]:
            want = sum(co[ap][k] * E[k] for k in E)
            self.assertAlmostEqual(r["results"][0]["approaches"][ap]["total"], want, delta=1e-9 * max(1, abs(want)))
        # a unit that cannot be converted and a missing dataset are refused
        with self.assertRaises(ValueError):
            analysis.eol_compare(st, {"R1": 0.3}, {"virgin": acts[0]["id"]}, [m["id"]])
        with self.assertRaises(ValueError):
            analysis.eol_compare(st, {"R1": 0.3}, ds, [m["id"]], unit="kWh")


class TestSupplyChain(Lib):
    def check(self, n):
        if n["loop"]:
            return
        if n["children"] or n["rest"]:
            parts = n["direct"] + sum(c["result"] for c in n["children"]) + n["rest"]
            self.assertAlmostEqual(parts, n["result"], delta=1e-9 * max(1.0, abs(n["result"])), msg=n["name"])
        for c in n["children"]:
            self.check(c)

    def test_parts_add_up_and_total_is_the_result(self):
        st = self.st
        m = self.method()
        for a in st.q("SELECT id FROM activities ORDER BY id")[:25]:
            r = supplychain.supply_chain(st, a["id"], m["id"], depth=3, top=3, min_share=0.0)
            self.assertAlmostEqual(r["total"], self.unit_score(a["id"], m["id"]),
                                   delta=1e-9 * max(1.0, abs(r["total"])))
            self.check(r["tree"])

    def test_limits(self):
        st = self.st
        a = st.q("SELECT id FROM activities ORDER BY id")[0]["id"]
        m = self.method()
        for kw in ({"depth": 0}, {"depth": 9}, {"top": True}, {"min_share": 2}):
            with self.assertRaises(ValueError):
                supplychain.supply_chain(st, a, m["id"], **kw)
        with self.assertRaises(ValueError):
            supplychain.supply_chain(st, 999999, m["id"])
        with self.assertRaises(ValueError):
            supplychain.supply_chain(st, a, 999999)



class Dairy(unittest.TestCase):
    """Cheese making: 1 kg cheese (price 3) and 2 kg whey (price 0.5), economic shares 75 % and 25 %.
    Lines: 10 kg CO2 shared; 4 kg CO2 from drying the whey, assigned to whey; 2 kWh electricity (0.5 kg CO2 per kWh)
    for pressing the cheese, assigned to cheese.
    Cheese per kg: 0.75 x 10 + 2 x 0.5 = 8.5. Whey per kg: (0.25 x 10 + 4) / 2 = 3.25. Together 8.5 + 2 x 3.25 = 15,
    the 10 + 4 + 1 kg of the process."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        st = self.st = self.ws.create("T")
        calc.invalidate()
        self.db = cd.create_database(st, "Dairy")
        self.cheese = cd.save_product(st, self.db, {"name": "cheese", "unit": "kg"})
        self.whey = cd.save_product(st, self.db, {"name": "whey", "unit": "kg"})
        self.p_el = cd.save_product(st, self.db, {"name": "electricity", "unit": "kWh"})
        self.co2 = cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                           "subcompartment": "unspecified", "unit": "kg"})
        self.el = cd.save_process(st, self.db, {"name": "grid", "product": self.p_el, "amount": 1})
        cd.save_exchange(st, self.el, {"kind": "elementary", "flow": self.co2, "amount": 0.5, "unit": "kg"})
        self.proc = cd.save_process(st, self.db, {
            "name": "cheese making", "product": self.cheese, "amount": 1,
            "coproducts": [{"product": self.whey, "amount": 2}],
            "allocation": {"method": "economic", "values": {self.cheese: 3, self.whey: 0.5}, "currency": "USD",
                           "price_year": 2024}})
        self.shared = cd.save_exchange(st, self.proc, {"kind": "elementary", "flow": self.co2, "amount": 10, "unit": "kg"})
        self.dry = cd.save_exchange(st, self.proc, {"kind": "elementary", "flow": self.co2, "amount": 4, "unit": "kg",
                                                    "assign": self.whey})
        self.press = cd.save_exchange(st, self.proc, {"kind": "technosphere", "supplier": self.el, "amount": 2,
                                                      "unit": "kWh", "assign": self.cheese})
        self.mid = cd.create_method(st, "M", "climate change", "GWP", "kg CO2-eq", "src")
        cd.save_factor(st, self.mid, self.co2, "value", 1.0, "kg", source="src")

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def refs(self):
        import json
        it = self.st.one("SELECT ref_id, data FROM custom_items WHERE uuid=?", (self.proc,))
        return it["ref_id"], json.loads(it["data"])["coproduct_refs"][self.whey]

    def per_kg(self, ref):
        m = self.st.save_model({"name": "m", "product": "p", "unit": "kg", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.st.add_input(m, "activity", ref, 1.0)
        calc.invalidate()
        return calc.run(self.st, m, [self.mid])["results"][0]["total"]


class TestSubdivision(Dairy):
    def test_hand_calculated(self):
        c, w = self.refs()
        self.assertAlmostEqual(self.per_kg(c), 8.5, places=12)
        self.assertAlmostEqual(self.per_kg(w), 3.25, places=12)
        self.assertAlmostEqual(self.per_kg(c) + 2 * self.per_kg(w), 15.0, places=12)   # nothing lost or doubled
        # the electricity line is only in the cheese dataset, in full
        t = self.st.q("SELECT output_id, amount FROM tech WHERE input_id=(SELECT ref_id FROM custom_items WHERE uuid=?)",
                      (self.el,))
        self.assertEqual([(r["output_id"], r["amount"]) for r in t], [(c, 2.0)])

    def test_allocation_compare_keeps_assigned_lines(self):
        r = cd.allocation_compare(self.st, self.proc, [self.mid])
        by = {x["method"]: {o["product"]: o["per_unit"][0] for o in x["outputs"]} for x in r["comparison"]
              if x["available"]}
        self.assertAlmostEqual(by["economic"]["cheese"], 8.5, places=12)
        self.assertAlmostEqual(by["economic"]["whey"], 3.25, places=12)
        # mass: shared 10 kg as 1/3 and 2/3; cheese 10/3 + 1, whey (20/3 + 4) / 2
        self.assertAlmostEqual(by["mass"]["cheese"], 10 / 3 + 1, places=12)
        self.assertAlmostEqual(by["mass"]["whey"], (20 / 3 + 4) / 2, places=12)
        self.assertAlmostEqual(r["total_burden"][0], 15.0, places=12)
        self.assertAlmostEqual(r["assigned_burden"][0], 5.0, places=12)

    def test_subdivision_only(self):
        d = self.st.one("SELECT data FROM custom_items WHERE uuid=?", (self.proc,))
        import json
        base = {"uuid": self.proc, "name": "cheese making", "product": self.cheese, "amount": 1,
                "coproducts": [{"product": self.whey, "amount": 2}], "allocation": {"method": "subdivision"}}
        with self.assertRaises(CustomDataError):          # the 10 kg line is still shared
            cd.save_process(self.st, self.db, base)
        self.assertEqual(json.loads(self.st.one("SELECT data FROM custom_items WHERE uuid=?", (self.proc,))["data"])
                         ["allocation"]["method"], "economic")   # nothing changed
        self.assertEqual(d["data"], self.st.one("SELECT data FROM custom_items WHERE uuid=?", (self.proc,))["data"])
        cd.save_exchange(self.st, self.proc, {"id": self.shared, "kind": "elementary", "flow": self.co2, "amount": 10,
                                              "unit": "kg", "assign": self.cheese})
        cd.save_process(self.st, self.db, base)
        c, w = self.refs()
        self.assertAlmostEqual(self.per_kg(c), 11.0, places=12)
        self.assertAlmostEqual(self.per_kg(w), 2.0, places=12)
        with self.assertRaises(CustomDataError):          # a new shared line is refused under subdivision
            cd.save_exchange(self.st, self.proc, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg"})
        self.assertAlmostEqual(self.per_kg(c), 11.0, places=12)

    def test_checks(self):
        with self.assertRaises(CustomDataError):          # not an output of the process
            cd.save_exchange(self.st, self.proc, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg",
                                                  "assign": self.p_el})
        with self.assertRaises(CustomDataError):          # one product: nothing to assign
            cd.save_exchange(self.st, self.el, {"kind": "elementary", "flow": self.co2, "amount": 1, "unit": "kg",
                                                "assign": self.p_el})
        with self.assertRaises(CustomDataError):          # whey has a line of its own
            cd.save_process(self.st, self.db, {"uuid": self.proc, "name": "cheese making", "product": self.cheese,
                                               "amount": 1})
        self.assertEqual(len(self.refs()), 2)

    def test_monte_carlo_parameters_follow_the_assignment(self):
        # a formula line assigned to whey: drawing its parameter changes only the whey dataset
        cd.set_database_parameters(self.st, self.db, [{"name": "q", "value": 1.0,
                                                       "uncertainty": {"type": "uniform", "min": 0.5, "max": 3}}])
        cd.save_exchange(self.st, self.proc, {"id": self.dry, "kind": "elementary", "flow": self.co2, "formula": "4 * q",
                                              "unit": "kg", "assign": self.whey})
        c, w = self.refs()
        calc.invalidate()
        mc = calc.get_mc(self.st)
        plan = cd.mc_plan(self.st, mc)
        key = plan["parameters"][0][0]
        rows = plan["deltas_for"]({key: 2.0})["B"]
        self.assertEqual(sorted(set(rows[1])), [mc.act_index[w]])
        self.assertAlmostEqual(sum(rows[2]), 4.0, places=12)          # 4 x 2 - 4, all of it to whey

    def test_export_import_keeps_assignment(self):
        doc = cd.export_json(self.st, self.db)
        db2 = cd.import_json(self.st, doc, "Dairy copy")
        rows = self.st.q("SELECT e.assign, e.amount FROM custom_exchanges e JOIN custom_items i ON i.uuid=e.process_uuid "
                         "WHERE i.db_id=? AND i.name='cheese making' ORDER BY e.amount", (db2,))
        self.assertEqual([r["assign"] is not None for r in rows], [True, True, False])


class TestVersions(Dairy):
    def test_save_compare_restore(self):
        c, w = self.refs()
        v1 = cd.save_version(self.st, self.proc, "as reviewed", "checked by M. Khan")
        with self.assertRaises(CustomDataError):
            cd.save_version(self.st, self.proc, "as reviewed")
        self.assertTrue(cd.versions(self.st, self.proc)[0]["same_as_current"])
        cd.save_exchange(self.st, self.proc, {"id": self.shared, "kind": "elementary", "flow": self.co2, "amount": 12,
                                              "unit": "kg"})
        cd.delete_exchange(self.st, self.proc, self.dry)
        self.assertAlmostEqual(self.per_kg(c), 0.75 * 12 + 1, places=12)
        v = cd.versions(self.st, self.proc)[0]
        self.assertFalse(v["same_as_current"])
        cmp = cd.compare_versions(self.st, self.proc, v1)
        st = {(r["state"], r["a"], r["b"]) for r in cmp["lines"]}
        self.assertIn(("changed", 10.0, 12.0), st)
        self.assertIn(("removed", 4.0, None), st)
        self.assertEqual(cmp["summary"]["same"], 1)
        cd.restore_version(self.st, self.proc, v1)
        self.assertEqual(self.refs(), (c, w))               # the datasets keep their ids
        self.assertAlmostEqual(self.per_kg(c), 8.5, places=12)
        self.assertAlmostEqual(self.per_kg(w), 3.25, places=12)
        self.assertTrue(cd.versions(self.st, self.proc)[0]["same_as_current"])
        cd.undo(self.st, self.proc)                          # the restore is one change in the history
        self.assertAlmostEqual(self.per_kg(c), 0.75 * 12 + 1, places=12)
        cd.delete_version(self.st, self.proc, v1)
        self.assertEqual(cd.versions(self.st, self.proc), [])

    def test_ids_are_checked(self):
        for bad in (True, 0, -1, 2.5, "x"):
            with self.assertRaises(CustomDataError):
                cd.restore_version(self.st, self.proc, bad)
        with self.assertRaises(CustomDataError):
            cd.restore_version(self.st, self.proc, "current")
        with self.assertRaises(CustomDataError):
            cd.save_version(self.st, self.proc, "")


class CheeseModel(unittest.TestCase):
    """A cheese model (1 kg cheese; co-product 2 kg whey; scope values per product output: mass 1 and 2, value 3 and 1). Datasets: milk 10, electricity 2,
    whey powder 4 kg CO2 per unit. Lines: 1 kg milk shared; 1 kWh for pressing, cheese only; 0.5 kWh for drying the
    whey, whey only.
    mass (1/3): 2 + 10/3. economic (3 / 4 = 0.75): 2 + 7.5 = 9.5. Shared milk, so subdivision needs a decision on it.
    system expansion, whey replacing 0.5 kg whey powder: 10 + 2 + 1 - 0.5 x 4 = 11."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ws = Workspace(self.dir)
        st = self.st = self.ws.create("T")
        db = st.create_database("bg", "test", "1", "test")
        with st.lock:
            fid = st.add_flow("co2", "Carbon dioxide, fossil", "air", "unspecified", "kg", "")
            ids = []
            for key, name, unit, co2 in (("m", "milk", "kg", 10), ("e", "electricity", "kWh", 2),
                                         ("w", "whey powder", "kg", 4)):
                a = st.conn.execute("INSERT INTO activities(db_id,key,name,product,location,unit,production) "
                                    "VALUES(?,?,?,?,?,?,1)", (db, key, name, name, "GLO", unit)).lastrowid
                st.conn.execute("INSERT INTO bio(activity_id,flow_id,amount) VALUES(?,?,?)", (a, fid, co2))
                ids.append(a)
            st._bump_lib()
            st.conn.commit()
        self.milk, self.el, self.wp = ids
        self.mid = st.get_or_create_method("M", "cc", "cc", "kg CO2-eq", "t")
        from importers import lcia
        lcia.store_raw(st, self.mid, [("Carbon dioxide, fossil", "air", "unspecified", "", None, 1.0)])
        lcia.rematch(st, [self.mid])
        self.scope = {"goal": "g", "boundary": "cradle-to-gate", "alloc_basis": "mass", "main_mass": 1, "main_price": 3,
                      "coproducts": [{"name": "whey", "mass": 2, "price": 1, "replaces": self.wp,
                                      "replaces_amount": 0.5}]}
        self.m = st.save_model({"name": "cheese", "product": "cheese", "unit": "kg", "amount": 1, "scope": self.scope})
        self.l_milk = st.add_input(self.m, "activity", self.milk, 1.0)
        self.l_press = st.add_input(self.m, "activity", self.el, 1.0)
        self.l_dry = st.add_input(self.m, "activity", self.el, 0.5)
        st.update_input(self.l_press, {"assign": "main"})
        st.update_input(self.l_dry, {"assign": "coproducts"})
        calc.invalidate()

    def tearDown(self):
        self.ws.close_all()
        calc.invalidate()
        shutil.rmtree(self.dir, ignore_errors=True)

    def rescope(self, **kw):
        self.st.save_model({"id": self.m, "name": "cheese", "product": "cheese", "unit": "kg", "amount": 1,
                            "scope": {**self.scope, **kw}})
        calc.invalidate()

    def total(self):
        calc.invalidate()
        return calc.run(self.st, self.m, [self.mid])["results"][0]["total"]


class TestModelMultifunctionality(CheeseModel):
    def test_allocation_with_subdivided_lines(self):
        self.assertAlmostEqual(self.total(), 2 + 10 / 3, places=12)
        self.rescope(alloc_basis="price")
        self.assertAlmostEqual(self.total(), 9.5, places=12)

    def test_compare_matches_full_calculations(self):
        r = calc.allocation_compare(self.st, self.m, [self.mid])
        by = {x["choice"].split(" (")[0]: x for x in r["rows"]}
        self.assertAlmostEqual(by["mass"]["totals"][0], 2 + 10 / 3, places=12)
        self.assertAlmostEqual(by["economic"]["totals"][0], 9.5, places=12)
        self.assertFalse(by["subdivision"]["available"])
        self.assertAlmostEqual(by["system expansion"]["totals"][0], 11.0, places=12)
        self.assertAlmostEqual(by["no allocation"]["totals"][0], 13.0, places=12)
        self.rescope(multifunctional="system_expansion")
        self.assertAlmostEqual(self.total(), 11.0, places=12)
        self.st.update_input(self.l_milk, {"assign": "main"})
        self.rescope(multifunctional="subdivision")
        self.assertAlmostEqual(self.total(), 12.0, places=12)
        by = {x["choice"].split(" (")[0]: x for x in calc.allocation_compare(self.st, self.m, [self.mid])["rows"]}
        self.assertTrue(by["subdivision"]["current"])
        self.assertAlmostEqual(by["subdivision"]["totals"][0], 12.0, places=12)

    def test_system_expansion_credit_line(self):
        self.rescope(multifunctional="system_expansion")
        res = calc.run(self.st, self.m, [self.mid])
        cr = [l for l in res["lines"] if l["derived"]]
        self.assertEqual(len(cr), 1)
        self.assertTrue(cr[0]["avoided"])
        self.assertAlmostEqual(cr[0]["impact"][0], -2.0, places=12)
        self.assertEqual(res["allocation_share"], 1.0)
        # Monte Carlo tree and the independent cross-check carry the credit too
        import hier
        ctx = calc.Context(self.st, {})
        mc = calc.get_mc(self.st)
        M = calc.Methods(self.st, mc, [self.mid])
        T = hier.build(ctx, self.m)
        tot = float(hier.path_amounts(ctx, T) @ np.asarray(hier.leaf_units(ctx, mc, M, T))[:, 0])
        self.assertAlmostEqual(tot, 11.0, places=10)
        import crosscheck
        x = crosscheck.run(self.st, [self.mid], sample=2, model_ids=[self.m])
        self.assertTrue(x["passed"], x["verdict"])

    def test_refusals(self):
        self.rescope(multifunctional="subdivision")
        with self.assertRaises(calc.LCAError):            # the milk line is shared
            self.total()
        self.rescope(multifunctional="system_expansion", coproducts=[{"name": "whey", "mass": 2}])
        with self.assertRaises(calc.LCAError):            # nothing to credit
            self.total()
        for bad in ({"multifunctional": "both"},
                    {"coproducts": [{"name": "whey", "replaces": True}]},
                    {"coproducts": [{"name": "whey", "replaces_amount": float("inf")}]},
                    {"coproducts": [{"name": "whey", "replaces_amount": -1}]}):
            with self.assertRaises(ValueError):
                self.st.save_model({"id": self.m, "name": "c", "product": "c", "unit": "kg", "amount": 1,
                                    "scope": {**self.scope, **bad}})
        with self.assertRaises(ValueError):
            self.st.update_input(self.l_milk, {"assign": "whey"})

    def test_checks_and_inventory(self):
        self.rescope(multifunctional="subdivision")
        cs = calc.checks(self.st, self.m, [self.mid])
        txt = " ".join(c.get("text") or c.get("message") or "" for c in (cs.get("checks") if isinstance(cs, dict) else cs))
        self.assertIn("Subdivision: 1 line(s) are shared", txt)
        self.rescope()
        inv = calc.provenance(self.st, self.m, [self.mid])
        milk = next(d for d in inv["datasets"] if d["dataset"] == "milk")
        self.assertAlmostEqual(milk["amount"], 1 / 3, places=12)        # the share once (1.9.2 applied it twice)
        self.assertAlmostEqual(milk["direct"][0], 10 / 3, places=12)

class TestApi(unittest.TestCase):
    def test_routes(self):
        from test_features import Api
        d = tempfile.mkdtemp()
        api = Api(d)
        try:
            api("POST", "/api/projects", {"name": "P"})
            tutorial.install(api.st.store)
            calc.invalidate()
            st = api.st.store
            kg = [a["id"] for a in st.q("SELECT id FROM activities WHERE unit='kg' ORDER BY id")][:2]
            m = next(x for x in st.methods() if "climate" in x["category"])
            r = api("POST", "/api/eol/compare", {"params": {"R1": 0.2, "R2": 0.5}, "mass": 1, "unit": "kg",
                                                 "datasets": {"virgin": kg[0], "recycled": kg[1], "recycling_eol": kg[1],
                                                              "disposal": kg[0]}, "method_ids": [m["id"]]})
            self.assertEqual(r["approaches"], list(analysis.EOL_APPROACHES))
            r = api("POST", "/api/eol/compare", {"params": {"R1": 2}, "datasets": {}, "method_ids": [m["id"]]}, ok=False)
            self.assertEqual(r["_code"], 400)
            t = api("GET", f"/api/activities/{kg[0]}/supply-chain?method_id={m['id']}&depth=2&top=3")
            self.assertIn("tree", t)
            r = api("GET", f"/api/activities/{kg[0]}/supply-chain?method_id=0", ok=False)
            self.assertEqual(r["_code"], 400)
            db = cd.create_database(st, "Own")
            pr = cd.save_product(st, db, {"name": "x", "unit": "kg"})
            proc = cd.save_process(st, db, {"name": "make x", "product": pr, "amount": 1})
            cd.save_exchange(st, proc, {"kind": "technosphere", "supplier": str(kg[0]), "amount": 1, "unit": "kg"})
            v = api("POST", "/api/custom/versions", {"process": proc, "name": "first"})["id"]
            self.assertEqual(api("GET", f"/api/custom/versions?process={proc}")["versions"][0]["id"], v)
            r = api("POST", "/api/custom/versions/compare", {"process": proc, "a": v})
            self.assertEqual(r["summary"]["same"], 1)
            api("POST", "/api/custom/versions/restore", {"process": proc, "version": v})
            r = api("POST", "/api/custom/versions/restore", {"process": proc, "version": True}, ok=False)
            self.assertEqual(r["_code"], 400)
            api("POST", "/api/custom/versions/delete", {"process": proc, "version": v})
            mid = api("POST", "/api/models", {"name": "c", "product": "c", "unit": "kg", "amount": 1,
                                              "scope": {"multifunctional": "subdivision",
                                                        "coproducts": [{"name": "b", "mass": 1}]}})["model"]["id"]
            line = api("POST", f"/api/models/{mid}/inputs", {"kind": "activity", "ref_id": kg[0], "amount": 1,
                                                             "unit": "kg"})["model"]["inputs"][0]["id"]
            api("PATCH", f"/api/inputs/{line}", {"assign": "main"})
            self.assertEqual(st.get_input(line)["assign"], "main")
            r = api("PATCH", f"/api/inputs/{line}", {"assign": "whey"}, ok=False)
            self.assertEqual(r["_code"], 400)
            r = api("POST", "/api/models", {"name": "c", "product": "c", "unit": "kg", "amount": 1,
                                            "scope": {"multifunctional": "x"}}, ok=False)
            self.assertEqual(r["_code"], 400)
            r = api("POST", "/api/allocation/compare", {"model_id": mid, "method_ids": [m["id"]]})
            self.assertTrue(any(x["choice"] == "subdivision" and x["current"] for x in r["rows"]))
        finally:
            api.close()
            calc.invalidate()
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
