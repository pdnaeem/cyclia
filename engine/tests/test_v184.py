"""Numerical integrity on every path (1.8.4).

Every number a user or a file can store is checked where it is saved (site-specific factors, fixed EPD values,
parameters and their distributions, scenario values, background scenarios, LCIA factors, line fields), a line is
changed in one transaction or not at all, and the calculation refuses to report a result that is not finite: the
matrices, factors and results are checked again, so data stored by an earlier version or written by hand cannot
produce NaN silently."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
from importers import lcia, tutorial  # noqa: E402
from test_engine import Base  # noqa: E402

INF = json.loads("1e309")
BAD = (INF, -INF, float("nan"), "1e309", "nan", "inf")


class TestNumericalIntegrity(Base):
    def setUp(self):
        super().setUp()
        st = self.st
        tutorial.install(st)
        self.mid = st.get_or_create_method("Reg", "water", "w", "m3", "test")
        lcia.store_raw(st, self.mid, [("Water, well, in ground", "natural resource", "", "", None, 1.0)])
        lcia.rematch(st, [self.mid])
        self.tap = st.search_activities("tap water")[0]["id"]
        self.flow = st.one("SELECT uuid, id FROM flows WHERE name LIKE 'Water, well%' LIMIT 1")
        self.m = st.save_model({"name": "W", "product": "w", "unit": "m2", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate"}})
        self.line = st.add_input(self.m, "activity", self.tap, 1000)
        calc.invalidate()

    def total(self):
        return calc.run(self.st, self.m, [self.mid])["results"][0]["total"]

    # ------------------------------------------------------------------ A. site-specific factors
    def test_site_factor(self):
        cf = {"family": "Reg", "category": "water", "indicator": "w", "flow_uuid": self.flow["uuid"]}
        for v in BAD:
            with self.subTest(v=v), self.assertRaises(ValueError):
                self.st.save_site_cf(dict(cf, value=v))
        self.st.save_site_cf(dict(cf, value=2.5))
        # a factor written by hand (or by an earlier version) is refused by the calculation, never used
        self.st.x("UPDATE main.site_cfs SET value=?", (INF,))
        self.st.add_input(self.m, "flow", self.flow["id"], 1.0)
        with self.assertRaises(calc.LCAError):
            self.total()

    # ------------------------------------------------------------------ B. fixed EPD values
    def test_fixed_values(self):
        fx = lambda v: {"name": "EPD", "unit": "kg", "impacts": [{"family": "Reg", "category": "water",  # noqa: E731
                                                                  "indicator": "w", "value": v}]}
        for v in BAD:
            with self.subTest(v=v):
                with self.assertRaises(ValueError):
                    self.st.add_input(self.m, "fixed", None, 1.0, fixed=fx(v))
        iid = self.st.add_input(self.m, "fixed", None, 2.0, fixed=fx(3.0))
        with self.assertRaises(ValueError):
            self.st.update_input(iid, {"fixed": fx(float("nan"))})
        self.assertAlmostEqual(self.total(), 1.001 + 6.0, places=9)        # 1000 kg tap water + 2 x 3
        self.st.x("UPDATE main.model_inputs SET fixed=? WHERE id=?", (json.dumps(fx(float("nan"))), iid))
        with self.assertRaises(calc.LCAError):
            self.total()

    # ------------------------------------------------------------------ C. parameters and scenarios
    def test_parameters(self):
        p = {"name": "k", "model_id": self.m, "value": 1}
        for bad in ({"value": INF}, {"value": "nan"}, {"utype": 1, "p1": INF}, {"utype": 1, "p1": "nan"},
                    {"utype": 2, "p1": INF}, {"utype": 3, "p1": 0, "p2": 1, "p3": INF},
                    {"utype": 4, "p1": -INF, "p2": 1}, {"utype": 9}, {"utype": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.st.save_parameter(dict(p, **bad))
        self.st.save_parameter(dict(p, utype=1, p1=1.2))

    def test_scenarios(self):
        for v in BAD:
            with self.subTest(v=v), self.assertRaises(ValueError):
                self.st.save_scenario({"name": "s", "overrides": {"k": v}})
        self.st.save_scenario({"name": "s", "overrides": {"k": 2}})
        rule = {"type": "scale_emission", "activity": "tap", "flow": "water", "factor": 1.0}
        bad_rules = [dict(rule, factor=INF), dict(rule, factor="nan"), dict(rule, factor={"2030": INF}),
                     dict(rule, factor={"2030.5": 1}),
                     {"type": "swap", "activity": "tap", "product": "electricity",
                      "to": [{"id": 1, "share": float("nan")}]},
                     {"type": "set_exchanges", "tech": [["db", "a", "db", "b", INF]], "bio": []}]
        for r in bad_rules:
            with self.subTest(rule=r), self.assertRaises(ValueError):
                self.st.save_bg_scenario({"name": "b", "rules": [r]})
        for y in (INF, "nan", 1e6):
            with self.subTest(base_year=y), self.assertRaises(ValueError):
                self.st.save_bg_scenario({"name": "b", "rules": [rule], "base_year": y})
        self.st.save_bg_scenario({"name": "b", "rules": [rule], "base_year": 2020})

    # ------------------------------------------------------------------ D. one transaction per line change
    def test_line_update_is_atomic(self):
        before = self.st.get_input(self.line)
        with self.assertRaises(ValueError):
            self.st.update_input(self.line, {"amount": 5, "year": INF})
        self.assertEqual(self.st.get_input(self.line)["amount"], before["amount"])
        self.st.update_input(self.line, {"label": "tap"})               # a later change commits nothing else
        after = self.st.get_input(self.line)
        self.assertEqual((after["amount"], after["label"]), (before["amount"], "tap"))
        self.assertFalse(self.st.conn.in_transaction)

    # ------------------------------------------------------------------ E. library matrices and factors
    def test_dataset_amount_not_finite(self):
        self.st.x("UPDATE tech SET amount=? WHERE output_id=?", (float("nan"), self.tap))
        self.st.bump_version()
        calc.invalidate()
        with self.assertRaises(calc.LCAError) as e:
            self.total()
        self.assertIn("tap water", str(e.exception))

    def test_elementary_amount_not_finite(self):
        self.st.x("UPDATE bio SET amount=? WHERE activity_id=?", (INF, self.tap))
        self.st.bump_version()
        calc.invalidate()
        with self.assertRaises(calc.LCAError):
            self.total()

    def test_lcia_factor_not_finite(self):
        with self.assertRaises(ValueError):
            lcia.store_raw(self.st, self.mid, [("Water, well, in ground", "natural resource", "", "", None, INF)])
        self.st.x("UPDATE cfs SET value=? WHERE method_id=?", (float("nan"), self.mid))
        calc.invalidate()
        with self.assertRaises(calc.LCAError) as e:
            self.total()
        self.assertIn("water", str(e.exception))

    def test_choices_and_parameter_search(self):
        import choices
        import productivity
        slot = [{"input_id": self.line, "options": [{"ref_id": self.tap, "amount": INF}]}]
        with self.assertRaises(choices.OptimiseError):
            choices.optimise(self.st, self.m, [self.mid], slot, {"method_id": self.mid})
        slot = [{"input_id": self.line, "options": [{"ref_id": self.tap, "amount": 10, "unit_cost": "nan"}]}]
        with self.assertRaises(choices.OptimiseError):
            choices.optimise(self.st, self.m, [self.mid], slot, {"method_id": self.mid})
        slot = [{"input_id": self.line, "options": [{"ref_id": self.tap, "amount": 10}]}]
        with self.assertRaises(choices.OptimiseError):
            choices.optimise(self.st, self.m, [self.mid], slot, {"method_id": self.mid},
                             [{"method_id": self.mid, "max": "nan"}])
        self.st.save_parameter({"name": "k", "model_id": self.m, "value": 1})
        with self.assertRaises(ValueError):
            productivity.sweep(self.st, self.m, [self.mid], [{"name": "k", "lo": 0, "hi": INF}])

    # ------------------------------------------------------------------ F. the last guards
    def test_result_guard(self):
        with self.assertRaises(calc.LCAError):
            calc.check_finite_results({"results": [{"category": "x", "total": float("nan")}], "lines": []})
        with self.assertRaises(calc.LCAError):
            calc.check_finite_results({"results": [{"category": "x", "total": 1.0}],
                                       "lines": [{"name": "l", "impact": [INF]}]})
        calc.check_finite_results({"results": [{"category": "x", "total": 1.0}], "lines": [{"name": "l", "impact": [1]}]})

    def test_monte_carlo_guard(self):
        with self.assertRaises(calc.LCAError):
            calc._stats([1.0, 2.0, float("nan")])
        self.assertAlmostEqual(calc._stats([1.0, 2.0, 3.0])["mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
