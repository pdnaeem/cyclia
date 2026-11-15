"""Optimisation of discrete choices (1.8.0), hand calculation.

Materials per kg: A 2 kg CO2 and 1 g X; B 1.5 kg CO2 and 4 g X; C 1 kg CO2 and 10 g X. Electricity per kWh: grid
0.5 kg CO2, solar 0.05 kg CO2. Climate: CO2 = 1; toxicity: X = 1 per g. Model: 2 kg of A (cost 1 per kg) and 10 kWh
grid (0.2 per kWh). Alternatives: 2 kg B (1.2), 2 kg C (1.5); 10 kWh solar (0.3).

combination   climate  toxicity  cost
A, grid         9.0       2       4.0
A, solar        4.5       2       5.0
B, grid         8.0       8       4.4
B, solar        3.5       8       5.4
C, grid         7.0      20       5.0
C, solar        2.5      20       6.0
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import custom_data as cd  # noqa: E402
import choices as optimise  # noqa: E402
from test_custom_data import Base  # noqa: E402


class TestOptimise(Base):
    def setUp(self):
        super().setUp()
        st = self.st
        db = cd.create_database(st, "Options")
        co2 = cd.save_elementary(st, {"name": "Carbon dioxide, fossil", "compartment": "air",
                                      "subcompartment": "unspecified", "unit": "kg"})
        x = cd.save_elementary(st, {"name": "Substance X", "compartment": "water", "subcompartment": "surface water", "unit": "kg"})
        self.p = {}
        for name, unit, c, g in (("A", "kg", 2, 1), ("B", "kg", 1.5, 4), ("C", "kg", 1, 10),
                                 ("grid", "kWh", 0.5, 0), ("solar", "kWh", 0.05, 0)):
            prod = cd.save_product(st, db, {"name": "product " + name, "unit": unit})
            pr = cd.save_process(st, db, {"name": name, "product": prod, "amount": 1})
            cd.save_exchange(st, pr, {"kind": "elementary", "flow": co2, "amount": c, "unit": "kg"})
            if g:
                cd.save_exchange(st, pr, {"kind": "elementary", "flow": x, "amount": g, "unit": "g"})
            self.p[name] = self.ref(pr)
        self.clim = cd.create_method(st, "M", "climate", "", "kg CO2-eq", "s")
        cd.save_factor(st, self.clim, co2, "value", 1.0, "kg", source="s")
        self.tox = cd.create_method(st, "M", "toxicity", "", "g X-eq", "s")
        cd.save_factor(st, self.tox, x, "value", 1.0, "g", source="s")
        self.m = st.save_model({"name": "product", "product": "p", "unit": "p", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.l1 = st.add_input(self.m, "activity", self.p["A"], 2.0, input_amount=2.0, input_unit="kg")
        self.l2 = st.add_input(self.m, "activity", self.p["grid"], 10.0, input_amount=10.0, input_unit="kWh")
        st.update_input(self.l1, {"unit_cost": 1.0})
        st.update_input(self.l2, {"unit_cost": 0.2})
        calc.invalidate()
        self.slots = [{"input_id": self.l1, "options": [{"ref_id": self.p["B"], "amount": 2, "unit": "kg", "unit_cost": 1.2},
                                                        {"ref_id": self.p["C"], "amount": 2000, "unit": "g",
                                                         "unit_cost": 0.0015}]},
                      {"input_id": self.l2, "options": [{"ref_id": self.p["solar"], "amount": 10, "unit": "kWh",
                                                         "unit_cost": 0.3}]}]

    def run_opt(self, objective, constraints=()):
        return optimise.optimise(self.st, self.m, [self.clim, self.tox], self.slots, objective, constraints)

    def names(self, r):
        return tuple(c["choice"].replace("current: ", "") for c in r["choices"])

    def test_limit_absolute(self):
        r = self.run_opt({"method_id": self.clim}, [{"method_id": self.tox, "max": 10}])
        self.assertEqual(r["combinations"], 6)
        self.assertEqual(r["feasible"], 4)
        self.assertEqual(self.names(r["best"])[0][:1] + self.names(r["best"])[1][:5], "Bsolar")
        self.assertAlmostEqual(r["best"]["totals"][0], 3.5, places=10)
        self.assertAlmostEqual(r["best"]["totals"][1], 8.0, places=10)
        self.assertAlmostEqual(r["best"]["cost"], 5.4, places=10)
        self.assertAlmostEqual(r["baseline"]["totals"][0], 9.0, places=10)
        self.assertAlmostEqual(r["baseline"]["cost"], 4.0, places=10)
        front = sorted((round(p["totals"][0], 9), round(p["totals"][1], 9)) for p in r["pareto"])
        self.assertEqual(front, [(2.5, 20.0), (3.5, 8.0), (4.5, 2.0)])

    def test_no_worse_than_now(self):
        r = self.run_opt({"method_id": self.clim}, [{"method_id": self.tox, "max_change_pct": 0}])
        self.assertAlmostEqual(r["best"]["totals"][0], 4.5, places=10)

    def test_cost_objective(self):
        r = self.run_opt({"cost": True}, [{"method_id": self.clim, "max": 5}])
        self.assertAlmostEqual(r["best"]["cost"], 5.0, places=10)
        self.assertAlmostEqual(r["best"]["totals"][0], 4.5, places=10)

    def test_saved_combination_reproduces_the_total(self):
        r = self.run_opt({"method_id": self.clim}, [{"method_id": self.tox, "max": 10}])
        choice = {str(c["input_id"]): c["option"] for c in r["best"]["choices"]}
        nid = optimise.apply(self.st, self.m, [self.clim, self.tox], self.slots, choice)
        calc.invalidate()
        res = calc.run(self.st, nid, [self.clim, self.tox])["results"]
        self.assertAlmostEqual(res[0]["total"], 3.5, places=10)
        self.assertAlmostEqual(res[1]["total"], 8.0, places=10)
        self.assertAlmostEqual(calc.run(self.st, self.m, [self.clim])["results"][0]["total"], 9.0, places=10)

    def test_infeasible_and_errors(self):
        r = self.run_opt({"method_id": self.clim}, [{"method_id": self.tox, "max": 1}])
        self.assertIsNone(r["best"])
        bad = [dict(self.slots[0], options=[{"ref_id": self.p["B"], "amount": 2, "unit": "kWh"}])]
        with self.assertRaises(optimise.OptimiseError):
            optimise.optimise(self.st, self.m, [self.clim], bad, {"method_id": self.clim})
        no_cost = [dict(self.slots[0], options=[{"ref_id": self.p["B"], "amount": 2}])]
        with self.assertRaises(optimise.OptimiseError):
            optimise.optimise(self.st, self.m, [self.clim], no_cost, {"cost": True})


if __name__ == "__main__":
    unittest.main()
