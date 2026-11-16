"""Cyclia 1.9.1: the paths the 1.9.0 audit found outside the common number validator, and the round-off rule of the
ecoinvent benchmark.

- LCIA imports: a yes/no factor in the ecoinvent LCIA workbook was read as 1.0; 1e309 in a normalisation and
  weighting CSV was stored as infinity; a mapping conversion factor 1e309 made inherited factors infinite.
- Identifiers: {"model_id": true} attached a parameter to model 1 and {"id": true} renamed parameter 1. The storage
  layer now checks every identifier itself, whoever calls it.
- Benchmark: a result that is the small remainder of cancelling contributions agrees when the gap is within the
  round-off of those contributions; the label column of ecoinvent's cumulative LCI is not read as a flow."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import trust  # noqa: E402
from importers import lcia, tutorial  # noqa: E402
from test_features import Api  # noqa: E402
from test_v138 import Base  # noqa: E402


class TestLciaImports(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)

    def csv(self, name, text):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def xlsx(self, cf):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "CFs"
        ws.append(["Method", "Category", "Indicator", "Name", "Compartment", "Subcompartment", "CF"])
        ws.append(["M", "climate change", "GWP100", "Methane, fossil", "air", "unspecified", 29.8])
        ws.append(["M", "climate change", "GWP100", "Carbon dioxide, fossil", "air", "unspecified", cf])
        p = os.path.join(self.dir, "l.xlsx")
        wb.save(p)
        return p

    def test_ecoinvent_workbook(self):
        for bad in (True, False, "1e309", "inf", "NaN"):
            with self.subTest(cf=bad), self.assertRaisesRegex(ValueError, "Row 3"):
                lcia.import_ecoinvent_lcia_xlsx(self.st, self.xlsx(bad))
        self.assertFalse([m for m in self.st.methods() if m["family"] == "M"])
        # a note in the factor column is not a factor: left out and reported
        r = lcia.import_ecoinvent_lcia_xlsx(self.st, self.xlsx("n.a."))
        self.assertEqual(r["factors"], 1)
        self.assertIn("left out", " ".join(r["warnings"]))

    def test_store_raw(self):
        mid = self.st.get_or_create_method("M", "c", "i", "u", "t")
        for bad in (True, float("inf"), float("nan"), "abc", None):
            with self.subTest(v=bad), self.assertRaises(ValueError):
                lcia.store_raw(self.st, mid, [("Carbon dioxide, fossil", "air", "", "", None, bad)])
        self.assertEqual(self.st.one("SELECT COUNT(*) n FROM cf_raw WHERE method_id=?", (mid,))["n"], 0)

    def test_factor_csv(self):
        head = "method,category,indicator,unit,flow_name,compartment,subcompartment,cf,flow_uuid,location\n"
        for bad in ("1e309", "true", "nan", "-inf"):
            p = self.csv("cf.csv", head + f"M,cc,GWP,kg,\"Carbon dioxide, fossil\",air,,{bad},,\n")
            with self.subTest(cf=bad), self.assertRaisesRegex(ValueError, "Carbon dioxide"):
                lcia.import_cf_csv(self.st, p)
        p = self.csv("cf.csv", head.replace(",", ";") + "M;cc;GWP;kg;Carbon dioxide, fossil;air;;1,5;;\n")
        lcia.import_cf_csv(self.st, p)
        mid = next(m["id"] for m in self.st.methods() if m["family"] == "M")
        self.assertEqual(self.st.one("SELECT value FROM cf_raw WHERE method_id=?", (mid,))["value"], 1.5)

    def test_normalisation_and_weighting(self):
        head = "method,category,indicator,set,normalisation,weighting\n"
        row = "Tutorial: IPCC 2021 GWP100,climate change,,S,{n},{w}\n"
        for n, w in (("1e309", "0.2"), ("8000", "1e309"), ("-8000", "0.2"), ("0", "0.2"), ("8000", "-0.2"),
                     ("true", "0.2"), ("nan", "0.2")):
            with self.subTest(n=n, w=w), self.assertRaises(ValueError):
                lcia.import_nw_csv(self.st, self.csv("nw.csv", head + row.format(n=n, w=w)))
        self.assertEqual(self.st.one("SELECT COUNT(*) n FROM nw")["n"], 0)
        self.assertEqual(lcia.import_nw_csv(self.st, self.csv("nw.csv", head + row.format(n="8000", w=""))
                                            )["factors"], 1)

    def test_mapping(self):
        head = ("source_name,source_compartment,source_subcompartment,source_uuid,target_name,target_compartment,"
                "target_subcompartment,target_uuid,factor\n")
        row = "CO2,air,,,\"Carbon dioxide, fossil\",air,,,{f}\n"
        for bad in ("1e309", "0", "-1", "true", "nan"):
            with self.subTest(f=bad), self.assertRaisesRegex(ValueError, "conversion factor"):
                lcia.import_mapping_csv(self.st, self.csv("map.csv", head + row.format(f=bad)))
        self.assertEqual(self.st.one("SELECT COUNT(*) n FROM flow_mapping")["n"], 0)
        # a mapping row written by an earlier version with an infinite factor is left out of matching
        fl = self.st.one("SELECT name, c_name, c_comp, c_sub, uuid FROM flows WHERE name='Carbon dioxide, fossil' LIMIT 1")
        self.st.x("INSERT INTO flow_mapping(source,s_name,s_comp,s_sub,s_uuid,t_name,t_comp,t_sub,t_uuid,factor) "
                  "VALUES('csv','co2 legacy','air','',NULL,?,?,?,NULL,?)",
                  (fl["c_name"], fl["c_comp"], fl["c_sub"], float("inf")))
        self.st.add_flow("legacy-co2", "CO2 legacy", "air", "", "kg")
        lcia.rematch_all(self.st)
        big = self.st.one("SELECT COUNT(*) n FROM cfs WHERE value > 1e308 OR value < -1e308 OR value IS NULL")["n"]
        self.assertEqual(big, 0)


class TestIdentifiers(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)
        self.m1 = self.st.save_model({"name": "A", "product": "a", "unit": "kg", "amount": 1})
        self.m2 = self.st.save_model({"name": "B", "product": "b", "unit": "kg", "amount": 1})

    def test_parameters(self):
        st = self.st
        p1 = st.save_parameter({"name": "x", "value": 1, "model_id": self.m1})
        for data in ({"name": "y", "value": 2, "model_id": True}, {"name": "y", "value": 2, "model_id": False},
                     {"name": "y", "value": 2, "model_id": 1.5}, {"id": True, "name": "z", "value": 2},
                     {"id": p1 + 99, "name": "z", "value": 2}, {"name": "y", "value": 2, "model_id": 999},
                     {"name": "y", "value": 2, "utype": True}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                st.save_parameter(data)
        self.assertEqual([p["name"] for p in st.parameters(self.m1)], ["x"])
        self.assertEqual(st.parameters(None), [])
        with self.assertRaises(ValueError):
            st.delete_parameter(True)

    def test_scenarios(self):
        st = self.st
        sid = st.save_scenario({"name": "S", "overrides": {}})
        with self.assertRaises(ValueError):
            st.save_scenario({"id": True, "name": "T"})
        with self.assertRaises(ValueError):
            st.save_scenario({"id": sid + 5, "name": "T"})
        with self.assertRaises(ValueError):
            st.delete_scenario(False)
        self.assertEqual([s["name"] for s in st.scenarios()], ["S"])

    def test_every_store_method_checks_identifiers(self):
        st = self.st
        tap = st.search_activities("tap water")[0]["id"]
        calls = [lambda v: st.model(v), lambda v: st.model_inputs(v), lambda v: st.activity(v), lambda v: st.flow(v),
                 lambda v: st.delete_model(v), lambda v: st.get_input(v), lambda v: st.update_input(v, {"amount": 2}),
                 lambda v: st.delete_input(v), lambda v: st.add_input(v, "activity", tap, 1),
                 lambda v: st.add_input(self.m1, "activity", v, 1), lambda v: st.add_comment(v, None, "a", "t"),
                 lambda v: st.set_lock(v, True), lambda v: st.versions(v), lambda v: st.bg_scenario(v),
                 lambda v: st.delete_database(v)]
        for i, call in enumerate(calls):
            for v in (True, False, 0, -1, 2.5, "x", "1e309"):
                with self.subTest(call=i, v=v), self.assertRaises(ValueError):
                    call(v)
        self.assertEqual(st.model_inputs(self.m1), [])
        self.assertEqual(len(st.models()), 2)
        # identifiers as digit strings (from URL paths) and None where allowed still work
        self.assertEqual(st.model(str(self.m1))["name"], "A")
        st.add_comment(self.m1, None, "a", "on the whole model")

    def test_modules(self):
        import choices
        import custom_data
        import review
        # each refuses with its own error class or the storage layer's; all are ValueError (status 400 in the API)
        for call in (lambda: custom_data.save_factor(self.st, True, "x", "value", 1.0),
                     lambda: review.add(self.st, True, {"role": "reviewer", "author": "R", "severity": "minor",
                                                        "text": "x"}),
                     lambda: choices.optimise(self.st, True, [1], [], {"method_id": 1}),
                     lambda: choices.optimise(self.st, self.m1, [True], [], {"method_id": 1})):
            with self.assertRaisesRegex(ValueError, "yes/no"):
                call()


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dir = tempfile.mkdtemp()
        cls.api = Api(cls.dir)
        cls.api("POST", "/api/projects", {"name": "Ids"})
        cls.mid = cls.api("POST", "/api/models", {"name": "n", "unit": "kg", "product": "x", "amount": 1})["model"]["id"]
        cls.pid = cls.api("POST", "/api/parameters", {"name": "p", "value": 1, "model_id": cls.mid})["id"]

    @classmethod
    def tearDownClass(cls):
        import shutil
        cls.api.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_parameter_identifiers(self):
        a = self.api
        r = a("POST", "/api/parameters", {"model_id": True, "name": "bool_scope", "value": 2}, ok=False)
        self.assertEqual(r["_code"], 400)
        self.assertIn("yes/no", r["error"])
        r = a("POST", "/api/parameters", {"id": True, "name": "renamed", "value": 2}, ok=False)
        self.assertEqual(r["_code"], 400)
        r = a("POST", "/api/parameters", {"model_id": False, "name": "q", "value": 2}, ok=False)
        self.assertEqual(r["_code"], 400)
        r = a("GET", f"/api/parameters?model_id={self.mid}")
        self.assertEqual([p["name"] for p in r["model"]], ["p"])
        self.assertEqual(r["project"], [])

    def test_scenario_identifiers(self):
        a = self.api
        r = a("POST", "/api/scenarios", {"id": True, "name": "S"}, ok=False)
        self.assertEqual(r["_code"], 400)
        for body in ({"model_id": self.mid, "method_ids": [1], "scenario": True},
                     {"model_id": self.mid, "method_ids": [1], "scenario": False},
                     {"model_id": self.mid, "method_ids": [1], "bg_id": True}):
            r = a("POST", "/api/calculate", body, ok=False)
            self.assertEqual(r["_code"], 400, body)
        r = a("POST", "/api/compare-scenarios", {"model_id": self.mid, "method_ids": [1], "scenario_ids": [True]},
              ok=False)
        self.assertEqual(r["_code"], 400)


class TestBenchmarkRoundOff(unittest.TestCase):
    def test_cancellation(self):
        # values of the Ecological Scarcity 2021 'biotic resources' run on ecoinvent 3.13 with 1.9.0: both results are
        # remainders of fish exchanges of both signs; with contributions summing to 1 UBP the gap is round-off
        dev, raw, note = trust.compare_value(1.538309324026861e-12, -3.182281328030638e-10, 1.0, 0.0)
        self.assertEqual(dev, 0.0)
        self.assertLess(raw, -2e4)
        self.assertTrue(note.startswith("cancellation"))
        # the same gap with contributions of 1e-2 is not round-off
        dev, raw, note = trust.compare_value(1.538309324026861e-12, -3.182281328030638e-10, 1e-2, 0.0)
        self.assertEqual(dev, raw)
        self.assertFalse(note.startswith("cancellation"))
        # an ordinary deviation is never hidden, however large the contributions
        dev, raw, note = trust.compare_value(100.0, 101.0, 1e6, 0.0)
        self.assertAlmostEqual(dev, 1.0)
        # results within 0.1 % keep their own deviation
        dev, raw, note = trust.compare_value(100.0, 100.01, 1e12, 0.0)
        self.assertAlmostEqual(dev, 0.01)
        self.assertEqual(note, "")

    def test_lci_label_column_is_not_a_flow(self):
        top = [["Activity UUID_Product UUID", "Activity Name", "Geography", "Reference Product Name", "Unit",
                "Exchange Name", "Carbon dioxide, fossil", "Methane, fossil"],
               ["", "", "", "", "", "Compartment", "air", "air"],
               ["", "", "", "", "", "Subcompartment", "unspecified", "unspecified"],
               ["", "", "", "", "", "Reference Product Amount", "", ""],
               ["a_b", "x", "GLO", "x", "kg", "1", "2.0", "0.1"]]
        ids, start, cols = trust._parse_sheet(type("S", (), {"title": "LCI"})(), top, 0)
        self.assertEqual([c["labels"][0] for c in cols], ["Carbon dioxide, fossil", "Methane, fossil"])
        self.assertEqual(start, 4)


class TestPublicationFromWorkbook(Base):
    def workbook(self, aligned=True):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        for k, v in (("Cyclia", "1.9.0"), ("Date", "2026-11-16 21:04:36"), ("Database", "ecoinvent 3.13 cutoff"),
                     ("Database version", "3.13"), ("System model", "cutoff"), ("Datasets compared", 3),
                     ("Datasets in the results file", 27401), ("ecoinvent cumulative LCI file", "not used")):
            ws.append([k, v])
        cats = [("IPCC 2021", "climate change", "GWP100"), ("IPCC 2013", "climate change", "GWP100"),
                ("Ecological Scarcity 2021", "natural resources", "biotic resources")]
        bc = wb.create_sheet("By category")
        bc.append(["Family", "Category", "Indicator", "Unit", "Results", "Median |dev| %", "95th pct |dev| %",
                   "Max |dev| %", "Within 0.1 %", "Within 1 %", "Flows used without a factor", "Hint"])
        for f, c, i in cats:          # pooled, as 1.9.0 wrote them
            bc.append([f, c, i, "u", 6 if "IPCC" in f else 3, 0.0, 0.0, 0.0 if "IPCC" in f else 2e5,
                       100 if "IPCC" in f else 100 / 3, 100 if "IPCC" in f else 100 / 3, 0, None])
        ar = wb.create_sheet("All results")
        ar.append(["Group", "Dataset", "Location", "Product", "Category", "Indicator", "ecoinvent", "Cyclia",
                   "Deviation %", "Note"])
        for d in range(3):
            order = cats if aligned or d == 0 else list(reversed(cats))
            for f, c, i in order:
                if "biotic" in i:
                    e, y = ((10.0, 10.0) if d == 0 else (1e-12, -3e-10))
                else:
                    e, y = 2.0 + d, 2.0 + d
                ar.append(["Other", f"ds{d}", "GLO", "p", c, i, e, y, (y - e) / abs(e) * 100, None])
        p = os.path.join(self.dir, "bench.xlsx")
        wb.save(p)
        return p

    def test_per_method_statistics_and_analysis(self):
        import benchmark
        files = benchmark.publication_from_workbook(self.workbook())
        ipcc = files["ipcc-ecoinvent-3-13-cutoff.md"]
        self.assertIn("**IPCC 2013**: Validated. 100.00 % of 3 results", ipcc)     # per method, not the pooled 6
        self.assertNotIn("pooled", ipcc)
        es = files["ecological-scarcity-2021-ecoinvent-3-13-cutoff.md"]
        self.assertIn("2 of 3 results deviate by more than 0.1 %", es)
        self.assertIn("in 2 the two results have opposite signs", es)
        self.assertIn("not claimed as validated", es)
        for text in files.values():                                   # no ecoinvent or Cyclia value is written
            self.assertNotIn("3e-10", text)
            self.assertNotIn("1e-12", text)
        self.assertIn("| [IPCC](ipcc-ecoinvent-3-13-cutoff.md) | ecoinvent (3.13, cutoff) | 6 | Validated",
                      files["README.md"])

    def test_misaligned_workbook_reports_pooled_statistics(self):
        import benchmark
        files = benchmark.publication_from_workbook(self.workbook(aligned=False))
        self.assertIn("pooled the statistics", files["ipcc-ecoinvent-3-13-cutoff.md"])

    def test_api(self):
        d = self.dir
        api = Api(os.path.join(d, "ws"))
        try:
            api("POST", "/api/projects", {"name": "P"})
            r = api("POST", "/api/benchmark/publish", {"workbook": self.workbook(), "folder": os.path.join(d, "pub")})
            self.assertIn("ipcc-ecoinvent-3-13-cutoff.md", r["files"])
            self.assertTrue(os.path.exists(os.path.join(d, "pub", "README.md")))
            r = api("POST", "/api/benchmark/publish", {"workbook": os.path.join(d, "none.xlsx")}, ok=False)
            self.assertEqual(r["_code"], 400)
        finally:
            api.close()


if __name__ == "__main__":
    unittest.main()
