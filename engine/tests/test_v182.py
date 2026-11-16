"""Data integrity of MFA inputs (1.8.2): external inflows, coefficients, lifetimes and link factors must be finite;
inflows non-negative. A negative inflow used to be offset against the losses and report a closed mass balance."""
import copy
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mfa  # noqa: E402


class TestMfaInputs(unittest.TestCase):
    def defn(self):
        return copy.deepcopy(mfa.EXAMPLE)

    def test_example_runs(self):
        r = mfa.run(self.defn())
        self.assertTrue(r["mass_balance_ok"])
        self.assertTrue(all(row["external_inflow"] >= 0 for row in r["rows"]))

    def test_inflow_values(self):
        for v in (float("nan"), float("inf"), -float("inf"), -10, "abc", None):
            d = self.defn()
            first = d["inflows"][0]
            yr = next(iter(first["values"]))
            first["values"][yr] = v
            with self.subTest(v=v), self.assertRaises(ValueError):
                mfa.run(d)

    def test_inflow_year(self):
        d = self.defn()
        d["inflows"][0]["values"]["year two"] = 5
        with self.assertRaises(ValueError):
            mfa.run(d)

    def test_zero_inflow_is_allowed(self):
        d = self.defn()
        first = d["inflows"][0]
        for k in first["values"]:
            first["values"][k] = 0
        mfa.run(d)

    def test_coefficient_and_lifetime(self):
        d = self.defn()
        d["flows"][0]["share"] = float("nan")
        with self.assertRaises(ValueError):
            mfa.run(d)
        d = self.defn()
        st = [p for p in d["processes"] if p.get("stock")][0]
        st["lifetime"] = dict(st["lifetime"], mean=float("inf"))
        with self.assertRaises(ValueError):
            mfa.run(d)

    def test_years(self):
        d = self.defn()
        d["years"] = ["2020", "later"]
        with self.assertRaises(ValueError):
            mfa.run(d)

    def test_json_constants_refused_by_the_server_reader(self):
        import server
        with self.assertRaises(ValueError):
            json.loads('{"x": NaN}', parse_constant=server._no_constant)
        with self.assertRaises(ValueError):
            json.loads('{"x": -Infinity}', parse_constant=server._no_constant)
        self.assertEqual(json.loads('{"x": 1e308}', parse_constant=server._no_constant)["x"], 1e308)
        self.assertTrue(math.isfinite(json.loads('{"x": 2.5}', parse_constant=server._no_constant)["x"]))


if __name__ == "__main__":
    unittest.main()
