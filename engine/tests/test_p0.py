"""Stage P0 of the development plan: reference tests with hand-calculated or analytic expected values.

Comparative LCA (paired Monte Carlo, conclusions with their sampling error), nested uncertainty and data quality,
AWARE water balance, LANCA indicators and SQI aggregation, social LCA activity levels, MFA collection and
recycling rates, and the Material Circularity Indicator."""
import math
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import hier  # noqa: E402
import mfa  # noqa: E402
import regional  # noqa: E402
import slca  # noqa: E402
from importers import other_formats  # noqa: E402
from store import Workspace  # noqa: E402


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


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

    def db(self, acts, name="P0 database"):
        """acts: list of (key, location, production, [(supplier key, amount)], [(flow uuid, name, comp, sub, unit,
        amount)]). Returns {key: activity id}."""
        b = other_formats._Builder(self.st, name, "test")
        idx = {}
        for key, loc, prod, _, _ in acts:
            idx[key] = b.activity(key, key, key, loc, "kg", production=prod)
        for key, _, _, ins, ems in acts:
            for sup, amt in ins:
                b.input(idx[key], sup, "kg", amt, link=idx[sup])
            for u, n, c, s, un, amt in ems:
                b.emission(idx[key], u, n, c, s, un, amt)
        b.write(lambda *a: None)
        calc.invalidate()
        return {r["key"]: r["id"] for r in self.st.q("SELECT id, key FROM activities")}

    def method(self, factors, category="climate change"):
        fids = {r["uuid"]: r["id"] for r in self.st.q("SELECT id, uuid FROM flows")}
        with self.st.lock:
            cur = self.st.conn.execute("INSERT INTO lib.methods(family,category,indicator,unit,source,note) VALUES(?,?,?,?,?,?)",
                                       ("P0 test method", category, "indicator", "kg CO2-eq", "test", ""))
            self.st.conn.executemany("INSERT INTO lib.cfs(method_id, flow_id, value) VALUES(?,?,?)",
                                     [(cur.lastrowid, fids[u], v) for u, v in factors.items()])
            self.st.conn.commit()
        calc.invalidate()
        return cur.lastrowid

    def model(self, name, inputs, **scope):
        m = self.st.save_model({"name": name, "product": "p", "unit": "unit", "amount": 1,
                                "scope": {"goal": "g", "boundary": "cradle-to-gate", **scope}})
        for kind, ref, amt, ped in inputs:
            self.st.add_input(m, kind, ref, amt, pedigree=ped)
        return m

    def sigma(self, model_id):
        ctx = calc.Context(self.st, {})
        return [L["sigma"] for L in hier.build(ctx, model_id)["lines"]]


CO2 = ("co2", "Carbon dioxide, fossil", "air", "unspecified", "kg")


# ------------------------------------------------------------------------------------------- comparative LCA
class TestComparisonConclusion(unittest.TestCase):
    def test_clear_difference(self):
        rng = np.random.default_rng(1)
        a, b = rng.normal(1.0, 0.05, 2000), rng.normal(2.0, 0.05, 2000)
        c = calc.compare_conclusion(a, b, 0.95)
        self.assertEqual(c["result"], "a_lower")
        self.assertGreater(c["interval"][0], 0.95)
        self.assertEqual(calc.compare_conclusion(b, a, 0.95)["result"], "b_lower")

    def test_overlap_is_not_distinguishable(self):
        rng = np.random.default_rng(2)
        a, b = rng.normal(1.0, 0.5, 2000), rng.normal(1.05, 0.5, 2000)
        self.assertEqual(calc.compare_conclusion(a, b, 0.95)["result"], "not_distinguishable")

    def test_sampling_error_asks_for_more_iterations(self):
        """96 of 100 runs lower: the estimate (96 %) passes 95 %, its Wilson interval (90 to 98 %) does not."""
        a = np.r_[np.zeros(96), np.full(4, 2.0)]
        b = np.ones(100)
        c = calc.compare_conclusion(a, b, 0.95)
        self.assertEqual(c["result"], "more_iterations")
        lo, hi = calc.wilson(96, 100)
        self.assertAlmostEqual(lo, 0.9016, places=3)
        self.assertAlmostEqual(hi, 0.9843, places=3)

    def test_identical_results(self):
        x = np.linspace(1, 2, 50)
        self.assertEqual(calc.compare_conclusion(x, x.copy())["result"], "no_difference")


class TestComparativeMonteCarlo(Base):
    def setUp(self):
        super().setUp()
        self.ids = self.db([("X", "GLO", 1.0, [], [CO2 + (1.0,)])])
        self.gwp = self.method({"co2": 1.0})

    def test_probability_matches_the_analytic_value(self):
        """A = 1.0 x X, B = 1.25 x X, independent lognormal line factors exp(sigma Z): P(A < B) =
        Phi(ln(1.25) / sqrt(sigma_A^2 + sigma_B^2))."""
        a = self.model("A", [("activity", self.ids["X"], 1.0, [3, 3, 3, 3, 3])])
        b = self.model("B", [("activity", self.ids["X"], 1.25, [4, 4, 4, 4, 4])])
        sa, sb = self.sigma(a)[0], self.sigma(b)[0]
        expected = phi(math.log(1.25) / math.sqrt(sa ** 2 + sb ** 2))
        n = 5000
        r = calc.full_mc(self.st, [a, b], [self.gwp], iterations=n, seed=5)
        p = r["pairs"][0]["p_a_lower"][0]
        se = math.sqrt(expected * (1 - expected) / n)
        self.assertLess(abs(p - expected), 4 * se, (p, expected))
        lo, hi = r["pairs"][0]["conclusions"][0]["interval"]
        self.assertTrue(lo <= expected <= hi)

    def test_paired_runs(self):
        """The same model on both sides shares every draw: no difference in any run (unpaired runs would give P near
        50 %)."""
        a = self.model("A", [("activity", self.ids["X"], 1.0, [5, 5, 5, 5, 5])])
        r = calc.full_mc(self.st, [a, a], [self.gwp], iterations=300, seed=1)
        self.assertEqual(r["pairs"][0]["conclusions"][0]["result"], "no_difference")

    def test_confidence_level_is_checked(self):
        a = self.model("A", [("activity", self.ids["X"], 1.0, None)])
        b = self.model("B", [("activity", self.ids["X"], 2.0, None)])
        with self.assertRaises(calc.LCAError):
            calc.full_mc(self.st, [a, b], [self.gwp], iterations=50, confidence=1.2)


# ------------------------------------------------------------------------------------------- nested uncertainty and DQR
class TestNested(Base):
    def setUp(self):
        super().setUp()
        self.ids = self.db([("X", "GLO", 1.0, [], [CO2 + (1.0,)]), ("Y", "GLO", 1.0, [], [CO2 + (1.0,)])])
        self.gwp = self.method({"co2": 1.0})

    def test_two_level_lognormal(self):
        """Top = 2 x S, S = 1 x X. Result = 2 exp(s1 Z1 + s2 Z2): lognormal with median 2 and log standard deviation
        sqrt(s1^2 + s2^2)."""
        s = self.model("S", [("activity", self.ids["X"], 1.0, [2, 2, 2, 2, 2])])
        top = self.model("Top", [("model", s, 2.0, [4, 4, 4, 4, 4])])
        sig = self.sigma(top)
        self.assertEqual(len(sig), 2)
        expected_sd = math.sqrt(sum(x * x for x in sig))
        n = 6000
        r = calc.full_mc(self.st, [top], [self.gwp], iterations=n, seed=9)
        st_ = r["models"][0]["methods"][0]
        self.assertAlmostEqual(st_["median"], 2.0, delta=2.0 * 4 * expected_sd / math.sqrt(n) * 1.3)
        # log standard deviation from the 2.5 and 97.5 percentiles: (ln p97.5 - ln p2.5) / (2 x 1.96)
        sd = (math.log(st_["p97_5"]) - math.log(st_["p2_5"])) / (2 * 1.959964)
        self.assertLess(abs(sd - expected_sd) / expected_sd, 0.05)

    def test_nested_data_quality(self):
        """Top = 3 x S + 1 x Y; S = 1 x X. Shares 0.75 (path Top>S>X) and 0.25 (Y). The path takes the worst score of
        its chain: S line scores 2, X line 1 -> 2; Y line 4. Pedigree indicator = 0.75 x 2 + 0.25 x 4 = 2.5."""
        s = self.model("S", [("activity", self.ids["X"], 1.0, [1, 1, 1, 1, 1])])
        top = self.model("Top", [("model", s, 3.0, [2, 2, 2, 2, 2]), ("activity", self.ids["Y"], 1.0, [4, 4, 4, 4, 4])])
        r = calc.run(self.st, top, [self.gwp])
        self.assertAlmostEqual(r["results"][0]["total"], 4.0)
        dq = r["data_quality"]["by_category"][0]
        self.assertAlmostEqual(dq["dqr"], 2.5)
        self.assertEqual([round(x, 9) for x in dq["pedigree"]], [2.5] * 5)


# ------------------------------------------------------------------------------------------- AWARE
class TestAware(Base):
    W = [("w_in", "Water, river", "natural resource", "in water", "m3"),
         ("w_air", "Water", "air", "unspecified", "m3"),
         ("w_ret", "Water", "water", "surface water", "m3"),
         ("w_sea", "Water", "water", "ocean", "m3")]

    def test_consumption_and_balance(self):
        """A process in FR withdraws 10 m3 from a river, evaporates 2, returns 7 to surface water and discharges 1 to
        the ocean. Consumption = 10 - 7 = 3 m3 (evaporation and discharge to the sea are consumption). Non-agricultural
        factor for FR 5: impact 15 m3 world-eq; consumption fully identified by outputs (2 + 1 = 3)."""
        flows = [w + (amt,) for w, amt in zip(self.W, (10.0, 2.0, 7.0, 1.0))]
        ids = self.db([("cooling", "FR", 1.0, [], flows)])
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nFR,8,5,7\nGLO,40,20,40\n",
                                source="test factors")
        m = self.model("Plant", [("activity", ids["cooling"], 1.0, None)])
        r = regional.aware(self.st, m)
        self.assertAlmostEqual(r["consumption_m3"], 3.0)
        self.assertAlmostEqual(r["total"], 15.0)
        self.assertAlmostEqual(r["water_balance_m3"]["withdrawal"], 10.0)
        self.assertAlmostEqual(r["consumption_identified_m3"], 3.0)
        self.assertAlmostEqual(r["consumption_not_identified_m3"], 0.0)
        self.assertEqual(r["completeness"]["exact"], 1.0)

    def test_unreported_outputs_are_shown(self):
        """Withdrawal 4 m3 and nothing reported as output: consumption 4 m3, none of it identified."""
        ids = self.db([("product", "DE", 1.0, [], [self.W[0] + (4.0,)])])
        regional.import_factors(self.st, "AWARE", "location,agri,non_agri,unknown\nGLO,40,20,40\n", source="test")
        m = self.model("Product", [("activity", ids["product"], 1.0, None)])
        r = regional.aware(self.st, m)
        self.assertAlmostEqual(r["consumption_m3"], 4.0)
        self.assertAlmostEqual(r["consumption_not_identified_m3"], 4.0)
        self.assertAlmostEqual(r["total"], 80.0)        # global fallback, non-agricultural 20
        self.assertEqual(r["completeness"]["global"], 1.0)


# ------------------------------------------------------------------------------------------- LANCA
class TestLanca(Base):
    def test_indicators_by_hand(self):
        """100 m2a of arable land and a transformation of 10 m2 from forest to arable land, in FR.
        Erosion resistance factors: occupation 0.8 per m2a, to arable 16 per m2, from forest -16 per m2 ->
        80 + 160 - 160 = 80. Biotic production factors given per hectare (8000 per ha*a = 0.8 per m2a)."""
        land = [("occ", "Occupation, arable land", "natural resource", "land", "m2*a", 100.0),
                ("to", "Transformation, to arable land", "natural resource", "land", "m2", 10.0),
                ("from", "Transformation, from forest", "natural resource", "land", "m2", 10.0)]
        ids = self.db([("wheat", "FR", 1.0, [], land)])
        table = ("indicator,kind,land_use,location,value,unit\n"
                 "erosion resistance,occupation,arable land,FR,0.8,t/(m2*a)\n"
                 "erosion resistance,transformation_to,arable land,FR,16,t/m2\n"
                 "erosion resistance,transformation_from,forest,FR,-16,t/m2\n"
                 "biotic production,occupation,arable land,FR,8000,kg/(ha*a)\n")
        imp = regional.import_factors(self.st, "LANCA", table, source="test factors")
        self.assertEqual(imp["n_rejected"], 0)
        m = self.model("Wheat", [("activity", ids["wheat"], 1.0, None)])
        r = regional.lanca(self.st, m)
        er = next(x for x in r["indicators"] if x["indicator"] == "erosion resistance")
        self.assertAlmostEqual(er["total"], 80.0)
        bp = next(x for x in r["indicators"] if x["indicator"] == "biotic production")
        self.assertAlmostEqual(bp["total"], 80.0)       # 100 m2a x 0.8 per m2a
        self.assertEqual(bp["without_factor"][0]["flow"], "transformation_to: arable land")

    def test_wrong_factor_unit_is_rejected(self):
        table = "indicator,kind,land_use,location,value,unit\nerosion resistance,occupation,arable land,FR,1,t/m2\n"
        with self.assertRaises(ValueError):
            regional.import_factors(self.st, "LANCA", table, source="t")

    def test_sqi_aggregation_by_hand(self):
        """SQI = sum w_i CF_i / N_i with equal weights: (2/4 + 3/6 + 1/2 + 8/8) / 4 = 0.625."""
        rows = ["indicator,kind,land_use,location,value,unit"]
        for ind, v in (("erosion resistance", 2), ("mechanical filtration", 3), ("groundwater regeneration", 1),
                       ("biotic production", 8)):
            rows.append(f"{ind},occupation,arable land,GLO,{v},x/(m2*a)")
        regional.import_factors(self.st, "LANCA", "\n".join(rows), source="t")
        r = regional.sqi_aggregate(self.st, {"erosion resistance": 4, "mechanical filtration": 6,
                                             "groundwater regeneration": 2, "biotic production": 8})
        self.assertEqual(r["factors"], 1)
        v = self.st.one("SELECT value FROM native_factors WHERE indicator='soil quality index'")["value"]
        self.assertAlmostEqual(v, 0.625)


# ------------------------------------------------------------------------------------------- social LCA
class TestSocial(Base):
    def test_waste_treatment_and_credits(self):
        """Model: 2 kg of product P (P needs 0.5 kg of material M), 1 kg of waste sent to treatment W (reference
        amount -1), and 1 kg of avoided M. Worker hours per unit: P 0.1, M 0.2, W 0.3.
        Used: P 2 x 0.1 + M (2 x 0.5) x 0.2 + W 1 x 0.3 = 0.7 h. Avoided: M 1 x 0.2 = 0.2 h, listed apart."""
        ids = self.db([("P", "GLO", 1.0, [("M", 0.5)], []), ("M", "GLO", 1.0, [], []), ("W", "GLO", -1.0, [], [])])
        slca.import_data(self.st, "match,location,worker_hours,stakeholder,indicator,risk,source\n"
                                  "P,,0.1,workers,Fair salary,high,t\nM,,0.2,workers,Fair salary,low,t\n"
                                  "W,,0.3,workers,Fair salary,medium,t\n")
        m = self.st.save_model({"name": "S", "product": "p", "unit": "unit", "amount": 1, "scope": {"goal": "g"}})
        self.st.add_input(m, "activity", ids["P"], 2.0)
        self.st.add_input(m, "activity", ids["W"], 1.0)
        self.st.add_input(m, "activity", ids["M"], 1.0, avoided=True)
        r = slca.assess(self.st, m)
        self.assertAlmostEqual(r["worker_hours"], 0.7)
        self.assertAlmostEqual(r["worker_hours_avoided"], 0.2)
        ind = r["indicators"][0]
        # risk hours: P 0.2 x 10 + M 0.2 x 0.1 + W 0.3 x 1 = 2.32
        self.assertAlmostEqual(ind["risk_hours"], 2.32)
        self.assertEqual(r["process_coverage"], 1.0)

    def test_inconsistent_activity_variable(self):
        ids = self.db([("P", "GLO", 1.0, [], [])])
        slca.import_data(self.st, "match,location,worker_hours,stakeholder,indicator,risk\n"
                                  "P,,0.1,workers,Fair salary,high\nP,,0.4,workers,Child labour,low\n")
        m = self.model("S", [("activity", ids["P"], 1.0, None)])
        r = slca.assess(self.st, m)
        self.assertEqual(r["inconsistent_activity_variables"][0]["worker_hours"], [0.1, 0.4])


# ------------------------------------------------------------------------------------------- MFA and MCI
class TestMfa(unittest.TestCase):
    def defn(self):
        return {"years": [2020, 2022], "production_process": "prod", "recycling_processes": ["rec"],
                "processes": [{"id": "prod"}, {"id": "use", "stock": True, "lifetime": {"type": "fixed", "mean": 1}},
                              {"id": "eol"}, {"id": "sort"}, {"id": "rec"}, {"id": "loss", "sink": True}],
                "inflows": [{"to": "prod", "values": {"2020": 100}}],
                "flows": [{"from": "prod", "to": "use", "share": 0.9}, {"from": "prod", "to": "rec", "share": 0.1},
                          {"from": "use", "to": "eol", "share": 1.0},
                          {"from": "eol", "to": "sort", "share": 0.8}, {"from": "eol", "to": "loss", "share": 0.2},
                          {"from": "sort", "to": "rec", "share": 0.75}, {"from": "sort", "to": "loss", "share": 0.25},
                          {"from": "rec", "to": "prod", "share": 0.9}, {"from": "rec", "to": "loss", "share": 0.1}]}

    def test_collection_and_recycling_rate_by_hand(self):
        """End-of-life material reaching recycling = 0.8 x 0.75 = 60 % of the end-of-life outflow (production scrap
        to recycling is not end-of-life material). Recycling efficiency 90 %. End-of-life recycling rate 54 %."""
        r = mfa.run(self.defn())
        self.assertTrue(r["mass_balance_ok"])
        y = r["rows"][1]                      # 2021: the 2020 inflow to use retires
        self.assertGreater(y["end_of_life_outflow"], 0)
        self.assertAlmostEqual(y["collection_rate"], 0.6)
        self.assertAlmostEqual(y["recycling_efficiency"], 0.9)
        self.assertAlmostEqual(y["recycling_rate"], 0.54)

    def test_mci_reference_values(self):
        """Ellen MacArthur Foundation (2015): fully linear 0.1, fully circular 1, and a hand calculation:
        F_R = C_R = 0.5, E_C = 0.8, E_F = 1: V 0.5, W 0.55, LFI 1.05 / 1.95, MCI = 1 - 0.9 x 0.538462 = 0.515385."""
        self.assertAlmostEqual(mfa.mci()["MCI"], 0.1)
        self.assertAlmostEqual(mfa.mci(Fr=1, Cr=1, Ec=1, Ef=1)["MCI"], 1.0)
        r = mfa.mci(Fr=0.5, Cr=0.5, Ec=0.8, Ef=1)
        self.assertAlmostEqual(r["LFI"], 1.05 / 1.95)
        self.assertAlmostEqual(r["MCI"], 1 - 0.9 * 1.05 / 1.95)


if __name__ == "__main__":
    unittest.main()
