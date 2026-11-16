"""One number validator on every path (Cyclia 1.9.0).

In Python, and after JSON parsing, True is 1 and False is 0, so a yes/no value sent in place of a number used to pass
as an amount, an identifier, a year or a factor. 1e309 is read as infinity. numcheck refuses both, and every path that
reads a number uses it: the API, the storage layer, the calculation and analysis modules and the importers. Importers
that read whole files count the values they could not use and report them in the import warnings."""
import json
import os
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis  # noqa: E402
import inventory_io  # noqa: E402
import numcheck  # noqa: E402
import regional  # noqa: E402
import science  # noqa: E402
import staging  # noqa: E402
from importers import jsonld, tutorial  # noqa: E402
from test_features import Api  # noqa: E402
from test_v138 import Base, ex, olca_zip  # noqa: E402

INF = json.loads("1e309")
NOT_NUMBERS = (True, False, INF, -INF, float("nan"), "1e309", "nan", "inf", "abc", [1], {"a": 1}, None, "")


class TestNumcheck(unittest.TestCase):
    def test_parse(self):
        for v in NOT_NUMBERS:
            with self.subTest(v=v):
                self.assertIsNone(numcheck.parse(v))
        self.assertEqual(numcheck.parse("2.5"), 2.5)
        self.assertEqual(numcheck.parse(" 3 "), 3.0)
        self.assertIsNone(numcheck.parse("1,5"))
        self.assertEqual(numcheck.parse("1,5", comma=True), 1.5)
        self.assertEqual(numcheck.parse(0), 0.0)

    def test_numpy_values(self):
        import numpy as np
        self.assertEqual(numcheck.parse(np.float64(2.0)), 2.0)
        self.assertEqual(numcheck.parse(np.int64(3)), 3.0)
        self.assertIsNone(numcheck.parse(np.bool_(True)))
        self.assertIsNone(numcheck.parse(np.float64("nan")))

    def test_finite_and_whole(self):
        with self.assertRaisesRegex(ValueError, "not a yes/no value"):
            numcheck.finite(True, "Amount")
        with self.assertRaises(numcheck.NotANumber):
            numcheck.finite(INF, "Amount")
        with self.assertRaises(ValueError):
            numcheck.finite(0, "Amount", lo=0, lo_open=True)
        self.assertEqual(numcheck.finite(0, "Amount", lo=0), 0.0)
        with self.assertRaises(ValueError):
            numcheck.integer(2.5, "Count")
        self.assertEqual(numcheck.integer("3", "Count"), 3)
        with self.assertRaises(ValueError):
            numcheck.identifier(True)
        with self.assertRaises(ValueError):
            numcheck.identifier(0)
        with self.assertRaises(ValueError):
            numcheck.year(2020.5)

    def test_own_error_class(self):
        class E(Exception):
            pass
        with self.assertRaises(E):
            numcheck.finite(False, "x", err=E)

    def test_reader_counts(self):
        with numcheck.reading() as r:
            self.assertEqual(numcheck.read("2", 0), 2.0)
            self.assertEqual(numcheck.read(True, 0, "amount"), 0)
            self.assertEqual(numcheck.read("1e309", 0), 0)
            self.assertIsNone(numcheck.read("", None))          # blank: not counted
            self.assertEqual(numcheck.read("1,5", 0, comma=True), 1.5)
        self.assertEqual(r.bad, 2)
        self.assertIn("2 value(s)", r.message())

        @numcheck.counted()
        def importer():
            numcheck.read("nan", 0)
            return {"warnings": []}
        res = importer()
        self.assertEqual(res["unusable_numbers"], 1)
        self.assertEqual(len(res["warnings"]), 1)


class TestStoreAndModules(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)
        self.tap = self.st.search_activities("tap water")[0]["id"]
        self.m = self.st.save_model({"name": "W", "product": "w", "unit": "m2", "amount": 1})

    def test_store(self):
        st = self.st
        for v in (True, False, INF, "nan"):
            with self.subTest(v=v):
                with self.assertRaises(ValueError):
                    st.save_model({"name": "x", "product": "x", "unit": "kg", "amount": v})
                with self.assertRaises(ValueError):
                    st.add_input(self.m, "activity", self.tap, v)
                with self.assertRaises(ValueError):
                    st.save_parameter({"model_id": self.m, "name": "p", "value": v})
        line = st.add_input(self.m, "activity", self.tap, 2.0)
        with self.assertRaises(ValueError):
            st.update_input(line, {"year": True})
        with self.assertRaises(ValueError):
            st.update_input(line, {"amount": INF})
        self.assertEqual(st.get_input(line)["amount"], 2.0)

    def test_science_rules(self):
        base = {"type": "scale_emission", "activity": "x", "flow": "carbon"}
        for f in (True, INF, "abc", None, {2030: True}, {"20x": 1.0}, {2030.5: 1.0}, -1):
            with self.subTest(f=f), self.assertRaises(ValueError):
                science.validate_rules([dict(base, factor=f)])
        science.validate_rules([dict(base, factor=0.5), dict(base, factor={"2030": 0.8, 2040: "0.6"})])
        swap = {"type": "swap", "activity": "x", "product": "p"}
        with self.assertRaises(ValueError):
            science.validate_rules([dict(swap, to=[{"id": 1, "share": True}])])
        science.validate_rules([dict(swap, to=[{"id": 1, "share": 0.5}, {"id": 2, "share": "0.5"}])])
        with self.assertRaises(ValueError):
            science.validate_rules([{"type": "set_exchanges", "tech": [(1, 2, True)]}])

    def test_cff_and_correlations(self):
        with self.assertRaises(ValueError):
            analysis.cff_lines({"A": True})
        with self.assertRaises(ValueError):
            analysis.cff_lines({"R1": "1e309"})
        with self.assertRaises(ValueError):
            analysis.apply_cff(self.st, self.m, True, "kg", {}, {})
        import numpy as np
        dist = [{"name": "a", "dist": "normal", "value": 1, "sd": 0.1},
                {"name": "b", "dist": "normal", "value": 1, "sd": 0.1}]
        with self.assertRaises(ValueError):
            analysis.correlated_draws(np.random.default_rng(1), dist, 10, [{"a": "a", "b": "b", "r": True}])

    def test_regional_and_inventory(self):
        self.assertIsNone(regional._month_profile(True))
        self.assertIsNone(regional._month_profile(2.5))
        self.assertIsNone(regional._month_profile([1] * 11 + [INF]))
        self.assertEqual(regional._month_profile(3)[2], 1.0)
        self.assertIsNone(regional._num("true"))
        self.assertIsNone(regional._num(True))
        self.assertEqual(regional._num("2,5"), 2.5)
        with self.assertRaises(ValueError):
            inventory_io._pedigree("2,3,1,2,2.5")
        with self.assertRaises(ValueError):
            inventory_io._pedigree("2,3,1,2,inf")
        self.assertEqual(inventory_io._pedigree("2,3,1,2,2"), [2, 3, 1, 2, 2])

    def test_teaching(self):
        import teaching
        q = next(e for e in teaching.EXERCISES if e.get("choice"))
        with self.assertRaises(ValueError):
            teaching.check(self.st, q["id"], True)
        with self.assertRaises(ValueError):
            teaching.check(self.st, q["id"], 1.5)


class TestImporters(Base):
    def test_jsonld_amount_yes_no_is_refused(self):
        tmp = os.path.join(self.dir, "b.zip")
        olca_zip(tmp, [("b", "bolt making", "fb", [ex("fe", "ELEMENTARY_FLOW", True, False)])])
        with self.assertRaisesRegex(ValueError, "not a yes/no value"):
            staging.staged(self.st, self.dir, lambda s, p: jsonld.import_jsonld(s, tmp, "B", p))
        self.assertFalse(any(d["name"] == "B" for d in self.st.databases()))

    def test_jsonld_unusable_uncertainty_is_reported(self):
        tmp = os.path.join(self.dir, "u.zip")
        unc = {"distributionType": "LOG_NORMAL_DISTRIBUTION", "geomSd": True}
        olca_zip(tmp, [("b", "bolt making", "fb", [ex("fe", "ELEMENTARY_FLOW", 2.0, False, uncertainty=unc)])])
        res = staging.staged(self.st, self.dir, lambda s, p: jsonld.import_jsonld(s, tmp, "U", p))
        self.assertEqual(res["unusable_numbers"], 1)
        self.assertTrue(any("not finite numbers" in w for w in res["warnings"]))
        row = self.st.one("SELECT amount, utype FROM bio")
        self.assertEqual((row["amount"], row["utype"]), (2.0, 0))       # amount kept, no invented uncertainty


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dir = tempfile.mkdtemp()
        cls.api = Api(cls.dir)
        cls.api("POST", "/api/settings", {"author": "Tester"})
        cls.api("POST", "/api/projects", {"name": "Numbers"})
        cls.mid = cls.api("POST", "/api/models", {"name": "n", "unit": "kg", "product": "x", "amount": 1})["model"]["id"]

    @classmethod
    def tearDownClass(cls):
        import shutil
        cls.api.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def raw(self, path, text):
        req = urllib.request.Request(self.api.url + path, method="POST", data=text.encode(),
                                     headers={"Content-Type": "application/json", "X-Token": "tok"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status
        except urllib.error.HTTPError as e:
            with e:
                return e.code

    def test_yes_no_in_place_of_numbers(self):
        a = self.api
        r = a("POST", "/api/models", {"name": "b", "unit": "kg", "product": "x", "amount": True}, ok=False)
        self.assertEqual(r["_code"], 400)
        r = a("POST", f"/api/models/{self.mid}/inputs", {"kind": "activity", "ref_id": True, "amount": 1}, ok=False)
        self.assertEqual(r["_code"], 400)
        r = a("POST", f"/api/models/{self.mid}/inputs", {"kind": "activity", "ref_id": 1, "amount": True}, ok=False)
        self.assertEqual(r["_code"], 400)
        # int(True) is 1: before 1.9.0 a yes/no model_id calculated model 1
        r = a("POST", "/api/calculate", {"model_id": True, "method_ids": [1]}, ok=False)
        self.assertEqual(r["_code"], 400)
        self.assertIn("yes/no", r["error"])
        r = a("POST", "/api/calculate", {"model_id": self.mid, "method_ids": [False]}, ok=False)
        self.assertIn("yes/no", r["error"])
        r = a("POST", "/api/calculate", {"model_id": 1.5, "method_ids": [1]}, ok=False)
        self.assertIn("whole number", r["error"])
        r = a("POST", "/api/compare", {"model_ids": [self.mid, True], "method_ids": [1]}, ok=False)
        self.assertEqual(r["_code"], 400)

    def test_overflow_and_constants(self):
        self.assertEqual(self.raw("/api/models", '{"name": "o", "unit": "kg", "product": "x", "amount": 1e309}'), 400)
        self.assertEqual(self.raw("/api/models", '{"name": "o", "unit": "kg", "product": "x", "amount": NaN}'), 400)
        names = [m["name"] for m in self.api("GET", "/api/models")["models"]]
        self.assertNotIn("o", names)
        self.assertNotIn("b", names)


if __name__ == "__main__":
    unittest.main()
