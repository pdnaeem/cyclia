"""Regionalised factors (1.8.0): country fallback for sub-national locations and coverage reporting.

Tutorial library: tap water uses 0.001 m3 of well water per kg and 0.0005 kWh of electricity per kg; electricity uses
0.002 m3 per kWh. Factors: generic 1, location XX 10. For 1000 kg of tap water: tap water's own 1 m3 and the
electricity's 0.001 m3."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
from importers import lcia  # noqa: E402
from importers import tutorial  # noqa: E402
from test_engine import Base  # noqa: E402


class TestRegionalCoverage(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)
        self.find = lambda q: self.st.search_activities(q)[0]["id"]

    def model(self):
        return self.st.save_model({"name": "W", "product": "w", "unit": "m2", "amount": 1,
                                   "scope": {"goal": "g", "boundary": "cradle-to-gate"}})

    def setup_loc(self, loc):
        st = self.st
        mid = st.get_or_create_method("Reg", "water", "w", "m3", "test")
        lcia.store_raw(st, mid, [("Water, well, in ground", "natural resource", "", "", None, 1.0),
                                 ("Water, well, in ground", "natural resource", "", "XX", None, 10.0)])
        lcia.rematch(st, [mid])
        tap = self.find("tap water")
        st.x("UPDATE activities SET location=? WHERE id=?", (loc, tap))
        st.bump_version()
        calc.invalidate()
        m = self.model()
        st.add_input(m, "activity", tap, 1000)
        return calc.run(st, m, [mid])

    def test_exact(self):
        r = self.setup_loc("XX")
        cov = r["regional_coverage"][0]
        self.assertAlmostEqual(r["results"][0]["total"], 10 + 0.001, places=9)
        self.assertAlmostEqual(cov["exact"], 10 / 10.001, places=9)
        self.assertAlmostEqual(cov["generic"], 0.001 / 10.001, places=9)
        self.assertEqual(cov["country"], 0)

    def test_subnational_takes_the_country_factor(self):
        r = self.setup_loc("XX-01")
        cov = r["regional_coverage"][0]
        self.assertAlmostEqual(r["results"][0]["total"], 10 + 0.001, places=9)
        self.assertAlmostEqual(cov["country"], 10 / 10.001, places=9)
        self.assertEqual(r["regional_country_fallbacks"], 1)

    def test_location_without_factor(self):
        r = self.setup_loc("YY")
        cov = r["regional_coverage"][0]
        self.assertAlmostEqual(r["results"][0]["total"], 1 + 0.001, places=9)
        self.assertAlmostEqual(cov["generic"], 1.0, places=12)
        self.assertEqual(cov["generic_locations"][0]["location"], "YY")
        self.assertAlmostEqual(cov["generic_locations"][0]["share"], 1 / 1.001, places=9)


if __name__ == "__main__":
    unittest.main()
