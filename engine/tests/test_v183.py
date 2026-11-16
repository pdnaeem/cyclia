"""Finite numbers in the goal and scope and in model lines (1.8.3).

The engine's JSON reader refuses NaN and Infinity, but a number such as 1e309 becomes infinity, and stored scopes
reach the calculation by other paths too. Every number of the scope and of a line is checked when it is saved, and
the life cycle cost checks the stored values again and cannot loop without end."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import calc  # noqa: E402
from test_lcc_advanced import TestLCC  # noqa: E402

INF = json.loads("1e309")          # what a JSON reader makes of 1e309


class TestFiniteScope(unittest.TestCase):
    setUp = TestLCC.setUp
    tearDown = TestLCC.tearDown

    def model(self, scope=None, amount=1):
        return self.st.save_model({"name": "m", "product": "p", "unit": "unit", "amount": amount,
                                   "scope": {"goal": "g", "boundary": "cradle-to-grave", **(scope or {})}})

    def test_scope_numbers(self):
        self.assertEqual(INF, float("inf"))
        bad = [{"lcc_period": INF}, {"lcc_period": float("nan")}, {"lcc_period": "1e309"}, {"lcc_period": -5},
               {"lcc_period": 5000}, {"lcc_rate": float("nan")}, {"lcc_rate": -100}, {"lcc_rate": INF},
               {"lcc_escalation": {"maintenance": float("nan")}}, {"lcc_escalation": {"energy": INF}},
               {"lcc_escalation": {"energy": -120}}, {"lcc_escalation": "2"}, {"alloc_share": INF},
               {"alloc_share": 0}, {"main_mass": float("nan")}, {"coproducts": [{"name": "whey", "mass": INF}]},
               {"coproducts": [{"name": "whey", "price": -1}]}, {"aware_lat": 95}, {"aware_lon": "x"}]
        for sc in bad:
            with self.subTest(scope=sc), self.assertRaises(ValueError):
                self.model(sc)
        # valid values are kept
        m = self.model({"lcc_period": 60, "lcc_rate": 3, "lcc_escalation": {"energy": 2}, "alloc_share": 80})
        self.assertEqual(self.st.model(m)["scope"]["lcc_period"], 60)

    def test_model_amount(self):
        for a in (INF, float("nan"), "1e309", 0, -1):
            with self.subTest(amount=a), self.assertRaises(ValueError):
                self.model(amount=a)

    def test_line_numbers(self):
        m = self.model()
        with self.assertRaises(ValueError):
            self.st.add_input(m, "activity", self.a, INF)
        iid = self.st.add_input(m, "activity", self.a, 1.0)
        for f in ({"amount": INF}, {"amount": float("nan")}, {"input_amount": -1}, {"year": 1e9}, {"year": -1},
                  {"replace_every": 0.001}, {"replace_every": INF}, {"unit_cost": float("nan")}, {"cost_gsd": 0.5},
                  {"data_year": 3000}):
            with self.subTest(fields=f), self.assertRaises(ValueError):
                self.st.update_input(iid, f)
        self.st.update_input(iid, {"unit_cost": -20, "replace_every": 5, "year": 2})   # a revenue is negative
        self.assertEqual(self.st.get_input(iid)["unit_cost"], -20)

    def test_stored_infinite_period_cannot_hang(self):
        """A scope written before 1.8.3 (or by hand) with an infinite period: the cost is refused at once."""
        m = self.model()
        iid = self.st.add_input(m, "activity", self.a, 1.0)
        self.st.update_input(iid, {"unit_cost": 100, "replace_every": 5})
        self.st.x("UPDATE main.models SET scope=? WHERE id=?", ('{"goal": "g", "lcc_period": Infinity}', m))
        t = time.time()
        with self.assertRaises(calc.LCAError):
            analysis.lcc(calc.Context(self.st), m)
        self.assertLess(time.time() - t, 5)

    def test_too_many_purchases(self):
        m = self.model({"lcc_period": 1000})
        iid = self.st.add_input(m, "activity", self.a, 1.0)
        self.st.update_input(iid, {"unit_cost": 1})
        self.st.x("UPDATE main.model_inputs SET replace_every=0.05 WHERE id=?", (iid,))    # 20 000 purchases
        with self.assertRaises(calc.LCAError):
            analysis.lcc(calc.Context(self.st), m)
        self.st.update_input(iid, {"replace_every": 0.5})                                # 2 000 purchases
        self.assertAlmostEqual(analysis.lcc(calc.Context(self.st), m)["total"], 2000, places=6)


if __name__ == "__main__":
    unittest.main()
