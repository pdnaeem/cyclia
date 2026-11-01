"""Tests for the 1.2 features, through the HTTP API as the app uses it.   python -m unittest discover -s engine/tests"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calc  # noqa: E402
import interop  # noqa: E402
import productivity  # noqa: E402
import science  # noqa: E402
import server  # noqa: E402
import trust  # noqa: E402
from importers import demo  # noqa: E402


class Api:
    def __init__(self, data):
        self.st = server.State(data)
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.st, "tok"))
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def __call__(self, method, path, body=None, ok=True):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "X-Token": "tok"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read() or b"{}")
                if not ok:
                    raise AssertionError(f"{path} should have failed")
                return out
        except urllib.error.HTTPError as e:
            out = json.loads(e.read() or b"{}")
            if ok:
                raise AssertionError(f"{method} {path}: {e.code} {out}")
            out["_code"] = e.code
            return out

    def job(self, path, body=None):
        j = self("POST", path, body or {})["job"]
        for _ in range(1200):
            r = self("GET", f"/api/jobs/{j['id']}")["job"]
            if r["status"] != "running":
                if r["status"] != "done":
                    raise AssertionError(f"job {path}: {r['error']}")
                return r["result"]
            time.sleep(0.05)
        raise AssertionError("job timed out")

    def close(self):
        self.httpd.shutdown()
        self.st.ws.close_all()


class TestFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        calc.invalidate()
        cls.api = Api(cls.dir)
        cls.api("POST", "/api/settings", {"author": "Tester"})
        cls.demo = cls.api.job("/api/demo")
        cls.models = {m["name"]: m["id"] for m in cls.api("GET", "/api/models")["models"]}
        cls.methods = cls.demo["methods"]
        meths = cls.api("GET", "/api/methods")["methods"]
        cls.gwp = next(m["id"] for m in meths if m["family"] == demo.FAMILY and m["category"] == "climate change")
        cls.wall = cls.models["Concrete wall (demo)"]
        cls.hemp = cls.models["Hempcrete wall (demo)"]
        cls.roof = cls.models["Copper roof runoff, 1 m2 over 30 years (demo)"]
        cls.kiln = cls.models["Clinker kiln with co-product (demo)"]

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        calc.invalidate()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def calc_body(self, mid=None, **kw):
        return dict({"model_id": mid or self.wall, "method_ids": self.methods, "nw_set": demo.NW_SET}, **kw)

    # ---------------------------------------------------------------- demo
    def test_demo_project(self):
        self.assertEqual(self.demo["project"], "Cyclia feature demo")
        self.assertEqual(len(self.models), 7)
        st = self.api("GET", "/api/status")
        self.assertTrue(st["demo"])
        self.assertEqual(len(st["bg_scenarios"]), 2)
        for name, mid in self.models.items():
            r = self.api("POST", "/api/calculate", self.calc_body(mid))
            self.assertFalse([c for c in r["checks"] if c["level"] == "error"], name)
        r = self.api("POST", "/api/calculate", self.calc_body())
        self.assertTrue(any("demo" in c["message"] for c in r["checks"]))
        self.assertTrue(r["dynamic_gwp"])
        self.assertTrue(r["has_module_d"])

    def test_examples(self):
        ex = self.api("GET", "/api/examples")
        self.assertIn("Portland cement", ex["literature"])

    # ---------------------------------------------------------------- trust
    def test_validation_suite_and_report(self):
        before = len(self.api("GET", "/api/models")["models"])
        res = self.api.job("/api/validation-suite")
        self.assertEqual(res["passed"], res["total"], [c for c in res["cases"] if not c["passed"]])
        self.assertGreaterEqual(res["total"], 30)
        out = self.api("POST", "/api/export/validation", {})
        self.assertTrue(os.path.exists(out["path"]))
        # the user's project is untouched by the temporary validation library
        self.assertEqual(len(self.api("GET", "/api/models")["models"]), before)

    def test_bundle_roundtrip(self):
        b = self.api.job("/api/bundle/export", {"model_ids": [self.wall, self.hemp], "method_ids": self.methods,
                                                "nw_set": demo.NW_SET})
        self.assertTrue(zipfile.is_zipfile(b["path"]))
        v = self.api.job("/api/bundle/verify", {"path": b["path"]})
        self.assertTrue(v["reproduced"], v)
        # changing the data must be detected
        with zipfile.ZipFile(b["path"]) as z:
            man = json.loads(z.read("manifest.json"))
            proj = z.read("project.lca")
        man["results"][str(self.wall)]["totals"][0] += 1.0
        bad = b["path"].replace(".zip", "-bad.zip")
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("manifest.json", json.dumps(man))
            z.writestr("project.lca", proj)
        v2 = self.api.job("/api/bundle/verify", {"path": bad})
        self.assertFalse(v2["reproduced"])

    # ---------------------------------------------------------------- science
    def test_background_scenarios(self):
        base = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp]))["results"][0]["total"]
        bgs = {b["name"]: b["id"] for b in self.api("GET", "/api/bg-scenarios")["scenarios"]}
        pid = bgs["Electricity decarbonisation (illustrative)"]
        r2030 = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp], bg_id=pid, bg_year=2030))
        r2050 = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp], bg_id=pid, bg_year=2050))
        self.assertLess(r2050["results"][0]["total"], r2030["results"][0]["total"])
        self.assertLess(r2030["results"][0]["total"], base)
        self.assertTrue(r2050["background"]["changes"])
        cons = bgs["Marginal electricity is onshore wind (illustrative)"]
        rc = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp], bg_id=cons))
        self.assertLess(rc["results"][0]["total"], base)
        mk = self.api("GET", f"/api/models/{self.wall}/markets")["markets"]
        self.assertTrue(any(m["market"]["name"].startswith("market for electricity") for m in mk))
        t = self.api("POST", f"/api/bg-scenarios/{pid}/test", {"year": 2040})
        self.assertTrue(t["changes"])
        bad = self.api("POST", "/api/bg-scenarios", {"name": "x", "rules": [{"type": "swap", "activity": "a", "product": "p",
                                                                             "to": [{"id": 1, "share": 0.5}]}]}, ok=False)
        self.assertIn("add up to 1", bad["error"])

    def test_site_factor_and_toxicity(self):
        r = self.api("POST", "/api/calculate", self.calc_body(self.roof))
        self.assertTrue(r["site_factors"])
        eco = next(x for x in r["results"] if x["category"] == "ecotoxicity, freshwater")
        self.assertGreater(eco["total"], 0)
        cov = {t["category"]: t for t in r["toxicity_coverage"]}
        self.assertIn("ecotoxicity, freshwater", cov)
        ch = self.api("GET", "/api/chemicals")
        self.assertTrue(any(c["name"] == "Substance X (demo)" for c in ch["chemicals"]))
        prev = self.api("POST", "/api/chemicals/preview", {"props": demo.SUBSTANCE_X})
        self.assertLess(prev["fate"]["mass_balance_error"], 1e-9)
        self.assertGreater(prev["factors"]["water"]["freshwater ecotoxicity"], prev["factors"]["air"]["freshwater ecotoxicity"])
        self.api("POST", "/api/chemicals/preview", {"props": {"mw": 100}}, ok=False)
        # a new chemical becomes a flow and a characterised substance
        self.api("POST", "/api/chemicals", {"name": "Test chemical Q", "props": dict(demo.SUBSTANCE_X, hc50=1.0)})
        flows = self.api("GET", "/api/flows?q=Test%20chemical%20Q")["results"]
        self.assertEqual({f["compartment"] for f in flows}, {"air", "water", "soil"})

    def test_external_emissions(self):
        mid = self.api("POST", "/api/models", {"name": "ext test", "unit": "m2", "product": "x", "amount": 1})["model"]["id"]
        r = self.api("POST", f"/api/models/{mid}/external", {"text": demo.EXTERNAL_EXAMPLE, "stage": "B1 Use"})
        self.assertEqual(r["added"], 10)
        self.assertTrue(all(i["year"] > 0 for i in r["model"]["inputs"]))
        r = self.api("POST", f"/api/models/{mid}/external", {"text": "year,flow,compartment,amount\n1,Unobtainium,water,1\n"})
        self.assertTrue(r["problems"])
        r = self.api("POST", f"/api/models/{mid}/external", {"text": "year,flow,compartment,amount\n1,Unobtainium,water,1\n",
                                                             "create_missing": True})
        self.assertEqual(r["added"], 1)

    def test_map_coordinates(self):
        c = self.api("GET", "/api/coords")
        self.assertIn("FR", c["coords"])
        r = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp]))
        locs = {x["location"] for x in r["results"][0]["by_location"]}
        self.assertTrue({"FR", "DE", "PL"} <= locs)
        self.assertAlmostEqual(sum(x["impact"] for x in r["results"][0]["by_location"]), r["results"][0]["total"], places=6)

    # ---------------------------------------------------------------- productivity
    def test_literature_import(self):
        p = self.api("POST", "/api/literature/parse", {"text": demo.LITERATURE_EXAMPLE})
        rows = p["rows"]
        self.assertEqual(len(rows), 6)
        gravel = next(r for r in rows if r["name"].startswith("Gravel"))
        self.assertEqual(gravel["amount"], 1900)
        lorry = next(r for r in rows if "lorry" in r["name"].lower())
        self.assertEqual(lorry["unit"], "t*km")
        meth = next(r for r in rows if "Methane" in r["name"])
        self.assertEqual(meth["candidates"][0]["kind"], "flow")
        mid = self.api("POST", "/api/models", {"name": "lit", "unit": "m3", "product": "concrete", "amount": 1})["model"]["id"]
        add = [{"kind": r["candidates"][0]["kind"], "ref_id": r["candidates"][0]["id"], "amount": r["amount"],
                "unit": r["unit"], "stage": r["stage"], "name": r["name"]} for r in rows if r["candidates"]]
        out = self.api("POST", f"/api/models/{mid}/literature", {"rows": add, "source": "Example et al. 2023"})
        self.assertEqual(out["added"], len(add))
        rows2, _ = productivity.parse_table("Steel; 1.234,5; kg\nCopper sheet  2,5 kg  A1\nnothing here")
        self.assertEqual(rows2[0]["amount"], 1234.5)
        self.assertEqual(rows2[1]["amount"], 2.5)

    def test_sweep_and_optimise(self):
        s = self.api("POST", "/api/sweep", {"model_id": self.wall, "method_ids": [self.gwp],
                                            "params": [{"name": "thickness", "lo": 0.15, "hi": 0.3, "n": 4}]})
        v = [x[0] for x in s["values"]]
        self.assertTrue(all(b > a for a, b in zip(v, v[1:])))
        s2 = self.api("POST", "/api/sweep", {"model_id": self.wall, "method_ids": [self.gwp],
                                             "params": [{"name": "thickness", "lo": 0.15, "hi": 0.3, "n": 3},
                                                        {"name": "steel_kg", "lo": 8, "hi": 16, "n": 3}]})
        self.assertEqual(len(s2["grid"]), 3)
        self.api("POST", "/api/sweep", {"model_id": self.wall, "method_ids": [self.gwp],
                                        "params": [{"name": "nope", "lo": 0, "hi": 1}]}, ok=False)
        acid = next(m for m in self.api("GET", "/api/methods")["methods"] if m["family"] == demo.FAMILY and
                    m["category"] == "acidification")["id"]
        o = self.api.job("/api/optimise", {"model_id": self.wall, "method_ids": [self.gwp, acid], "objective": 0,
                                           "second_objective": 1, "samples": 80,
                                           "params": [{"name": "thickness", "lo": 0.18, "hi": 0.25},
                                                      {"name": "steel_kg", "lo": 8, "hi": 16}]})
        self.assertAlmostEqual(o["optimum"]["values"]["thickness"], 0.18, places=3)
        self.assertAlmostEqual(o["optimum"]["values"]["steel_kg"], 8, places=2)
        self.assertTrue(o["pareto"]["front"])
        lim = o["baseline"]["totals"][1] * 0.95
        o2 = self.api.job("/api/optimise", {"model_id": self.wall, "method_ids": [self.gwp, acid], "objective": 1,
                                            "constraints": [{"index": 1, "max": lim}],
                                            "params": [{"name": "thickness", "lo": 0.18, "hi": 0.25},
                                                       {"name": "steel_kg", "lo": 8, "hi": 16}]})
        self.assertTrue(o2["optimum"]["feasible"])
        self.assertLessEqual(o2["optimum"]["totals"][1], lim * 1.000001)
        o3 = self.api.job("/api/optimise", {"model_id": self.wall, "method_ids": [self.gwp, acid], "objective": 0,
                                            "constraints": [{"index": 1, "max": 1e-9}],
                                            "params": [{"name": "thickness", "lo": 0.18, "hi": 0.25}]})
        self.assertFalse(o3["optimum"]["feasible"])

    def test_templates(self):
        t = self.api("GET", "/api/model-templates")["templates"]
        self.assertGreaterEqual(len(t), 4)
        r = self.api("POST", "/api/model-templates/apply", {"id": "wall-en15804", "name": "Wall from template"})
        self.assertFalse(r["missing"], r)
        self.assertEqual(len(r["model"]["inputs"]), 5)
        self.api("POST", "/api/model-templates/save", {"model_id": r["model_id"], "name": "My wall template"})
        t2 = self.api("GET", "/api/model-templates")["templates"]
        mine = next(x for x in t2 if x["name"] == "My wall template")
        r2 = self.api("POST", "/api/model-templates/apply", {"id": mine["id"]})
        self.assertEqual(len(r2["model"]["inputs"]), 5)
        self.api("DELETE", f"/api/model-templates/{mine['db_id']}")

    def test_comments_versions_lock(self):
        c = self.api("GET", f"/api/models/{self.wall}/comments")["comments"]
        self.assertGreaterEqual(len(c), 3)
        c = self.api("POST", f"/api/models/{self.wall}/comments", {"text": "new note"})["comments"]
        self.assertEqual(c[0]["author"], "Tester")
        self.api("PATCH", f"/api/comments/{c[0]['id']}", {"resolved": True})
        vs = self.api("GET", f"/api/models/{self.wall}/versions")["versions"]
        self.assertEqual(len(vs), 2)
        d = self.api("GET", f"/api/versions/diff?model_id={self.wall}&a={vs[-1]['id']}&b={vs[0]['id']}")
        self.assertEqual(d["parameters"][0]["name"], "steel_kg")
        # locked model refuses edits
        r = self.api("POST", f"/api/models/{self.kiln}/inputs", {"kind": "flow", "ref_id": 1, "amount": 1}, ok=False)
        self.assertEqual(r["_code"], 423)
        self.api("POST", f"/api/models/{self.kiln}/lock", {"locked": False})
        dup = self.api("POST", f"/api/models/{self.kiln}/duplicate", {"name": "kiln copy"})["model"]
        self.api("POST", f"/api/models/{self.kiln}/lock", {"locked": True, "reason": "again"})
        # restore an old version on an unlocked copy
        mid = dup["id"]
        self.api("POST", f"/api/models/{mid}/versions", {"name": "v1"})
        line = dup["inputs"][0]["id"]
        self.api("DELETE", f"/api/inputs/{line}")
        v = self.api("GET", f"/api/models/{mid}/versions")["versions"]
        restored = self.api("POST", f"/api/versions/{v[0]['id']}/restore", {})["model"]
        self.assertEqual(len(restored["inputs"]), len(dup["inputs"]))
        d2 = self.api("GET", f"/api/versions/diff?model_id={mid}&a={v[0]['id']}&b=current")
        self.assertTrue(d2["identical"], d2)

    # ---------------------------------------------------------------- standards
    def test_epd(self):
        e = self.api("POST", "/api/epd/check", self.calc_body())
        self.assertIn("A1-A3", e["declared"])
        self.assertIn("D", e["declared"])
        ref = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp]))["results"][0]
        row = next(m for m in e["modules"] if m["category"] == "climate change" and m["family"] == demo.FAMILY)
        self.assertAlmostEqual(sum(v for k, v in row["modules"].items() if k != "D"), ref["total"], places=6)
        self.assertAlmostEqual(row["modules"]["D"], ref["module_d"], places=6)
        for path in ("/api/export/epd", "/api/export/epd-excel"):
            self.assertTrue(os.path.exists(self.api("POST", path, self.calc_body())["path"]))

    def test_pef_14067_ghg(self):
        p = self.api("POST", "/api/pef", self.calc_body())
        self.assertGreaterEqual(sum(c["share"] for c in p["relevant_categories"]), 0.8 - 1e-9)
        self.api("POST", "/api/pef", self.calc_body(nw_set=None), ok=False)
        self.assertTrue(os.path.exists(self.api("POST", "/api/export/iso14067", self.calc_body(self.hemp))["path"]))
        x = self.api("POST", "/api/export/ghg", self.calc_body(self.hemp))
        from openpyxl import load_workbook
        ws = load_workbook(x["path"]).worksheets[0]
        labels = [r[0].value for r in ws.iter_rows(min_row=3)]
        self.assertIn("Material acquisition and pre-processing", labels)
        self.assertIn("End of life", labels)

    def test_review(self):
        r = self.api("POST", "/api/review", self.calc_body())
        self.assertEqual(r["total"], 21)
        self.api("POST", f"/api/models/{self.wall}/review", {"items": {"goal": {"status": "accepted", "comment": "fine"}}})
        r = self.api("POST", "/api/review", self.calc_body())
        g = next(i for i in r["items"] if i["key"] == "goal")
        self.assertEqual(g["reviewer_status"], "accepted")
        self.assertEqual(g["reviewer"], "Tester")
        self.assertTrue(os.path.exists(self.api("POST", "/api/export/review", self.calc_body())["path"]))

    # ---------------------------------------------------------------- interoperability, API, teaching
    def test_brightway_roundtrip_and_openlca(self):
        x = self.api("POST", "/api/export/brightway", {"model_ids": [self.wall]})
        self.assertTrue(os.path.exists(x["script"]))
        acts = interop.read_brightway_excel(x["path"])
        self.assertEqual(acts[0]["name"], "Concrete wall (demo)")
        imp = self.api("POST", "/api/import/brightway", {"path": x["path"]})
        self.assertFalse(imp["problems"], imp["problems"])
        new = imp["models"][0]
        a = self.api("POST", "/api/calculate", self.calc_body(method_ids=[self.gwp]))["results"][0]["total"]
        b = self.api("POST", "/api/calculate", self.calc_body(new, method_ids=[self.gwp]))["results"][0]
        epd_line = 10.0 * 0.12  # the EPD line has no Brightway equivalent and is not exported
        self.assertAlmostEqual(b["total"] + b["module_d"], a - epd_line + self.api(
            "POST", "/api/calculate", self.calc_body(method_ids=[self.gwp]))["results"][0]["module_d"], places=6)
        o = self.api("POST", "/api/export/openlca", {"model_ids": [self.wall, self.hemp]})
        with zipfile.ZipFile(o["path"]) as z:
            procs = [n for n in z.namelist() if n.startswith("processes/")]
            self.assertEqual(len(procs), 2)
            p = json.loads(z.read(procs[0]))
            self.assertTrue(any(e["isQuantitativeReference"] for e in p["exchanges"]))

    def test_python_client(self):
        self.api.st.api_info = {"url": self.api.url, "token": "tok"}
        info = self.api("GET", "/api/api-info")
        files = self.api("POST", "/api/export/clients", {})["files"]
        py = next(f for f in files if f["file"].endswith(".py"))["path"]
        sys.path.insert(0, os.path.dirname(py))
        import importlib
        cl = importlib.import_module("cyclia_client")
        cy = cl.Cyclia(self.api.url, "tok")
        res = cy.calculate(self.wall, [self.gwp])
        self.assertGreater(res["results"][0]["total"], 0)
        sw = cy.sweep(self.wall, [self.gwp], [{"name": "thickness", "lo": 0.2, "hi": 0.3, "n": 2}])
        self.assertEqual(len(sw["values"]), 2)
        self.assertIn("token", info)

    def test_teaching(self):
        ex = self.api("GET", "/api/teaching/exercises")
        self.assertTrue(ex["demo_ready"])
        key = {k["id"]: k for k in self.api("POST", "/api/teaching/key", {})["key"]}
        for e in ex["exercises"]:
            if e.get("options"):
                good = e["options"].index(key[e["id"]]["answer"])
                self.assertTrue(self.api("POST", "/api/teaching/check", {"id": e["id"], "answer": good})["correct"])
            else:
                ans = float(key[e["id"]]["answer"])
                self.assertTrue(self.api("POST", "/api/teaching/check", {"id": e["id"], "answer": ans})["correct"], e["id"])
                self.assertFalse(self.api("POST", "/api/teaching/check", {"id": e["id"], "answer": ans * 2})["correct"])
        self.assertTrue(os.path.exists(self.api("POST", "/api/export/answer-key", {})["path"]))


class TestOfficial(unittest.TestCase):
    """Official EF 3.1 factors, CAS tables, scenario files and export identifiers (through the API)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        calc.invalidate()
        cls.api = Api(cls.dir)
        cls.api.job("/api/demo")
        cls.st = cls.api.st.store
        cls.wall = next(m["id"] for m in cls.api("GET", "/api/models")["models"] if m["name"] == "Concrete wall (demo)")
        cls.gwp = next(m["id"] for m in cls.st.methods() if m["family"] == demo.FAMILY and m["category"] == "climate change")

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        calc.invalidate()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_ef31_normalisation_weighting(self):
        import official
        fam = "EF v3.1"
        names = [("climate change", "global warming potential (GWP100)"), ("climate change: fossil", "GWP100"),
                 ("climate change: biogenic", "GWP100"), ("climate change: land use and land use change", "GWP100"),
                 ("ozone depletion", "ozone depletion potential (ODP)"),
                 ("human toxicity: carcinogenic", "comparative toxic unit for human (CTUh)"),
                 ("human toxicity: carcinogenic, inorganics", "CTUh"),
                 ("human toxicity: non-carcinogenic", "comparative toxic unit for human (CTUh)"),
                 ("particulate matter formation", "impact on human health"), ("ionising radiation: human health", "x"),
                 ("photochemical oxidant formation: human health", "x"), ("acidification", "accumulated exceedance (AE)"),
                 ("eutrophication: terrestrial", "x"), ("eutrophication: freshwater", "x"), ("eutrophication: marine", "x"),
                 ("ecotoxicity: freshwater", "comparative toxic unit for ecosystems (CTUe)"),
                 ("ecotoxicity: freshwater, metals", "CTUe"), ("land use", "soil quality index"),
                 ("water use", "user deprivation potential (deprivation-weighted water consumption)"),
                 ("material resources: metals/minerals", "abiotic depletion potential (ADP): elements (ultimate reserves)"),
                 ("energy resources: non-renewable", "abiotic depletion potential (ADP): fossil fuels")]
        ids = {c: self.st.get_or_create_method(fam, c, i, "u", "test") for c, i in names}
        self.assertIn(fam, self.api("GET", "/api/ef31")["families"])
        r = self.api("POST", "/api/ef31/install", {"family": fam})
        self.assertEqual(len(r["matched"]), 16, r["missing"])
        got = {m["ef"]: m["category"] for m in r["matched"]}
        self.assertEqual(got["Climate change"], "climate change")
        self.assertEqual(got["Human toxicity, cancer"], "human toxicity: carcinogenic")
        self.assertEqual(got["Ecotoxicity, freshwater"], "ecotoxicity: freshwater")
        self.assertEqual(got["Resource use, fossils"], "energy resources: non-renewable")
        nw = {row["method_id"]: row for row in self.st.q("SELECT * FROM nw WHERE set_name=?", (official.EF31_SET,))}
        self.assertAlmostEqual(nw[ids["climate change"]]["normalisation"], 7550.0)
        self.assertAlmostEqual(nw[ids["climate change"]]["weighting"], 0.2106)
        self.assertNotIn(ids["climate change: fossil"], nw)
        self.assertAlmostEqual(sum(row["weighting"] for row in nw.values()), 1.0, places=9)

    def test_cas_table(self):
        import official
        from openpyxl import Workbook
        with self.st.lock:
            self.st.add_flow("11111111-1111-4111-8111-111111111111", "Copper (II)", "water", "surface water", "kg", "007440-50-8")
            self.st.conn.commit()
        path = os.path.join(self.dir, "usetox.xlsx")
        wb = Workbook()
        ws = wb.active
        ws.append(["USEtox 2 characterisation factors (test)"])
        ws.append(["CAS RN", "Substance name", "Ecotox CF [CTUe/kg] em.cont.freshwater", "Ecotox CF [CTUe/kg] em.cont.air",
                   "Human health CF [CTUh/kg] cancer, em.freshwater"])
        ws.append([7440508, "Copper", 55000.0, 1200.0, None])
        ws.append(["7440-66-6", "Zinc, ion", 30000.0, 900.0, 1e-6])
        ws.append(["", "", "", "", ""])
        wb.save(path)
        p = self.api("POST", "/api/cf-table/preview", {"path": path})
        self.assertEqual(p["header_row"], 2)
        self.assertEqual(p["cas_col"], 0)
        self.assertEqual(p["name_col"], 1)
        comps = {c["index"]: c["compartment"] for c in p["columns"]}
        self.assertEqual((comps[2], comps[3]), ("water", "air"))
        mapping = {"header_row": 2, "cas_col": 0, "name_col": 1, "family": "USEtox test",
                   "columns": [{"index": 2, "category": "freshwater ecotoxicity", "unit": "CTUe", "compartment": "water",
                                "subcompartment": ""},
                               {"index": 3, "category": "freshwater ecotoxicity", "unit": "CTUe", "compartment": "air",
                                "subcompartment": ""}]}
        r = self.api.job("/api/import/cf-table", {"path": path, "mapping": mapping})
        self.assertEqual(r["by_cas"], 1)
        mid = self.st.method_by_key("USEtox test", "freshwater ecotoxicity", "freshwater ecotoxicity")["id"]
        cu = self.st.one("SELECT c.value FROM cfs c JOIN flows f ON f.id=c.flow_id WHERE c.method_id=? AND f.name='Copper (II)'",
                         (mid,))
        self.assertEqual(cu["value"], 55000.0)
        zn = self.st.one("SELECT c.value FROM cfs c JOIN flows f ON f.id=c.flow_id WHERE c.method_id=? AND f.name='Zinc, ion' "
                         "AND f.compartment='water'", (mid,))
        self.assertEqual(zn["value"], 30000.0)
        self.assertEqual(official.norm_cas("7440-50-9"), "")

    def test_scenario_file(self):
        csv_text = ("from activity name;from reference product;from location;from categories;from database;from key;"
                    "to activity name;to reference product;to location;to categories;to database;to key;flow type;"
                    "SSP2 2030;SSP2 2050\n"
                    "market for electricity, medium voltage (demo);electricity, medium voltage;PL;;ei;x;"
                    "reinforcing steel production (demo);reinforcing steel;RER;;ei;y;technosphere;0.4;0.2\n"
                    "Carbon dioxide, fossil;;;('air', 'unspecified');biosphere3;z;"
                    "reinforcing steel production (demo);reinforcing steel;RER;;ei;y;biosphere;0.9;0.5\n"
                    "nothing like this;p;XX;;ei;q;reinforcing steel production (demo);reinforcing steel;RER;;ei;y;"
                    "technosphere;1;1\n")
        path = os.path.join(self.dir, "sdf.csv")
        with open(path, "w") as fh:
            fh.write(csv_text)
        r = self.api.job("/api/import/scenario-file", {"path": path, "prefix": "premise"})
        self.assertEqual(r["scenarios"], 2)
        self.assertEqual(r["unmatched"], 1)
        bgs = {b["name"]: b["id"] for b in self.api("GET", "/api/bg-scenarios")["scenarios"]}
        body = {"model_id": self.wall, "method_ids": [self.gwp]}
        base = self.api("POST", "/api/calculate", body)["results"][0]["total"]
        r30 = self.api("POST", "/api/calculate", dict(body, bg_id=bgs["premise SSP2 2030"]))
        r50 = self.api("POST", "/api/calculate", dict(body, bg_id=bgs["premise SSP2 2050"]))
        self.assertLess(r50["results"][0]["total"], r30["results"][0]["total"])
        self.assertLess(r30["results"][0]["total"], base)
        self.assertIn("1 technosphere and 1 biosphere", r50["background"]["changes"][0])
        # direct check against the matrix: steel per kg in 2050 = 0.5 + 0.2 kWh PL + other inputs unchanged
        import calc as c
        st = self.st
        steel = demo.act_id(st, "steel")
        M = c.Methods(st, c.get_mc(st), [self.gwp])
        unit = lambda bg: float(c.impacts(c.get_mc(st, bg), M if not bg else c.Methods(st, c.get_mc(st, bg), [self.gwp]),
                                          {steel: 1.0}, {}, [])[0][0])
        el = float(c.impacts(c.get_mc(st), M, {demo.act_id(st, "mkt_el_PL"): 1.0}, {}, [])[0][0])
        diff = unit(None) - unit({"id": bgs["premise SSP2 2050"]})
        # first-order expectation; wind power uses steel, so the loop adds a small second-order term
        self.assertAlmostEqual(diff, (1.1 - 0.5) + (0.6 - 0.2) * el, delta=1e-3 * diff)

    def _results_file(self, layout):
        """A results workbook in the shape of ecoinvent's cumulative LCIA file, with Cyclia's own values (one changed)."""
        import calc as c
        from openpyxl import Workbook
        st = self.st
        meths = [m for m in st.methods() if m["family"] == demo.FAMILY]
        acts = st.q("SELECT id, key, name, location, product, unit FROM activities")
        mc = c.get_mc(st)
        M = c.Methods(st, mc, [m["id"] for m in meths], regional=False)  # ecoinvent publishes non-regionalised results
        wb = Workbook()
        ws = wb.active
        idh = ["Activity UUID_Product UUID", "Activity Name", "Geography", "Reference Product Name", "Reference Product Unit"]
        if layout in ("per_sheet", "combined"):
            pass
        elif layout == "labels_above":
            ws.append([""] * 5 + [demo.FAMILY] + [""] * (len(meths) - 1))
            ws.append([""] * 5 + [m["category"] for m in meths])
            ws.append(idh + [m["indicator"] for m in meths])
        else:
            ws.append(idh + [demo.FAMILY] * len(meths))
            ws.append([""] * 5 + [m["category"] for m in meths])
            ws.append([""] * 5 + [m["indicator"] for m in meths])
            ws.append([""] * 5 + [m["unit"] for m in meths])
        if layout == "combined":
            ws.append(idh + [f"{demo.FAMILY} | {m['category']} | {m['indicator']} [{m['unit']}]" for m in meths] +
                      [f"{demo.FAMILY} no LT | {m['category']} | {m['indicator']} [{m['unit']}]" for m in meths])
        if layout == "per_sheet":
            ws.title = "Readme"
            ws.append(["This workbook has one sheet per method."])
            ws = wb.create_sheet("Other method")
            ws.append(idh + ["something"])
            ws.append(["x", "y", "GLO", "z", "kg", 1.0])
            ws = wb.create_sheet(demo.FAMILY)
            ws.append([""] * 5 + [m["category"] for m in meths])
            ws.append(idh + [m["indicator"] for m in meths])
        for k, a in enumerate(acts):
            f = np.zeros(mc.n)
            f[mc.act_index[a["id"]]] = 1.0
            h = (M.Q @ mc.solve(f)).tolist()
            if k == 3:
                h[0] *= 1.05
            extra = [v * 10 for v in h] if layout == "combined" else []
            ws.append([a["key"], a["name"], a["location"], a["product"], a["unit"]] + h + extra)
        path = os.path.join(self.dir, f"lcia_{layout}.xlsx")
        wb.save(path)
        return path, len(acts), len(meths)

    def test_benchmark_ecoinvent(self):
        st = self.st
        for m in [m for m in st.methods() if m["family"] == demo.FAMILY]:  # a decoy family with the same categories
            st.get_or_create_method(demo.FAMILY + " no LT", m["category"], m["indicator"], m["unit"], "test")
        for layout in ("labels_above", "labels_below", "per_sheet", "combined"):
            path, n_acts, n_m = self._results_file(layout)
            r = self.api.job("/api/benchmark-ecoinvent", {"path": path, "family": demo.FAMILY, "sample": 20})
            self.assertEqual(r["categories"], n_m, layout)
            self.assertEqual(r["datasets_matched"], n_acts)
            self.assertLessEqual(r["datasets"], 20)
            full = self.api.job("/api/benchmark-ecoinvent", {"path": path, "family": demo.FAMILY, "sample": 0})
            self.assertEqual(full["datasets"], n_acts)
            nonzero = full["summary"]["n"]
            self.assertEqual(round(full["summary"]["within_0_1"] / 100 * nonzero), nonzero - 1)
            self.assertAlmostEqual(abs(full["worst"][0]["deviation_percent"]), 100 * (1 - 1 / 1.05), places=6)
            self.assertTrue(os.path.exists(self.api("POST", "/api/export/benchmark", {})["path"]))
        bad = os.path.join(self.dir, "bad.xlsx")
        from openpyxl import Workbook
        Workbook().save(bad)
        j = self.api("POST", "/api/benchmark-ecoinvent", {"path": bad})["job"]
        for _ in range(100):
            jj = self.api("GET", f"/api/jobs/{j['id']}")["job"]
            if jj["status"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(jj["status"], "error")

    def test_benchmark_diagnosis(self):
        """A factor that the library lost must show up in the diagnosis, and numerically-zero pairs must agree."""
        st = self.st
        path, n_acts, n_m = self._results_file("labels_above")
        eco = next(m["id"] for m in st.methods() if m["family"] == demo.FAMILY and m["category"] == "ecotoxicity, freshwater")
        zn = st.one("SELECT id FROM flows WHERE name='Zinc, ion'")["id"]
        old = st.one("SELECT value FROM cfs WHERE method_id=? AND flow_id=?", (eco, zn))["value"]
        st.x("DELETE FROM cfs WHERE method_id=? AND flow_id=?", (eco, zn))
        calc.invalidate()
        try:
            r = self.api.job("/api/benchmark-ecoinvent", {"path": path, "family": demo.FAMILY, "sample": 0})
            d = [x for x in r["diagnosis"] if x["category"] == "ecotoxicity, freshwater"]
            self.assertTrue(d)
            self.assertEqual(d[0]["flows"][0]["flow"], "Zinc, ion")
            self.assertAlmostEqual(d[0]["explained_percent"], 100.0, places=4)
        finally:
            st.x("INSERT OR REPLACE INTO cfs VALUES(?,?,?)", (eco, zn, old))
            calc.invalidate()
        x = self.api("POST", "/api/export/benchmark", {})
        from openpyxl import load_workbook
        self.assertIn("Diagnosis", load_workbook(x["path"]).sheetnames)

    def test_factor_finder(self):
        """A factor with a wrong value (not a missing one) must be named by the factor finder, with the right value."""
        st = self.st
        path, n_acts, n_m = self._results_file("labels_above")
        cc = next(m["id"] for m in st.methods() if m["family"] == demo.FAMILY and m["category"] == "climate change")
        ch4 = st.one("SELECT f.id FROM flows f JOIN cfs c ON c.flow_id=f.id WHERE c.method_id=? AND f.name LIKE 'Methane%' "
                     "ORDER BY c.value DESC LIMIT 1", (cc,))["id"]
        old = st.one("SELECT value FROM cfs WHERE method_id=? AND flow_id=?", (cc, ch4))["value"]
        st.x("UPDATE cfs SET value=? WHERE method_id=? AND flow_id=?", (old * 0.5, cc, ch4))
        calc.invalidate()
        try:
            r = self.api.job("/api/benchmark-ecoinvent", {"path": path, "family": demo.FAMILY, "sample": 0})
            ff = [x for x in r["factor_finder"] if x["category"] == "climate change"]
            self.assertTrue(ff, r["factor_finder"])
            top = ff[0]["flows"][0]
            self.assertTrue(top["flow"].startswith("Methane"))
            self.assertAlmostEqual(top["implied_factor"], old, delta=abs(old) * 0.02)
            self.assertGreater(ff[0]["explained_percent"], 95)
        finally:
            st.x("UPDATE cfs SET value=? WHERE method_id=? AND flow_id=?", (old, cc, ch4))
            calc.invalidate()
        from openpyxl import load_workbook
        self.assertIn("Factor finder", load_workbook(self.api("POST", "/api/export/benchmark", {})["path"]).sheetnames)

    def test_unspecified_subcompartment_fallback(self):
        """ecoinvent convention: the 'unspecified' factor applies to subcompartments without a factor of their own."""
        from importers import lcia
        st = self.st
        fid_sw = st.add_flow("t-sw-0001", "Testium-230", "water", "surface water", "kBq")
        fid_oc = st.add_flow("t-oc-0001", "Testium-230", "water", "ocean", "kBq")
        st.conn.commit()
        mid = st.get_or_create_method("Fallback test", "radiation", "x", "kBq U235-Eq", "test")
        lcia.store_raw(st, mid, [("Testium-230", "water", "unspecified", "", None, 2.0),
                                 ("Testium-230", "water", "ocean", "", None, 0.5)])
        lcia.rematch(st, [mid])
        got = {r["flow_id"]: r["value"] for r in st.q("SELECT flow_id, value FROM cfs WHERE method_id=?", (mid,))}
        self.assertEqual(got.get(fid_sw), 2.0)
        self.assertEqual(got.get(fid_oc), 0.5)

    def test_ecoinvent_one_click_validation(self):
        """Login download is replaced by a local results file; the rest of the pipeline is the real one."""
        from importers import ecoinvent_login
        path, n_acts, n_m = self._results_file("labels_above")
        orig = ecoinvent_login.download_cumulative_lcia
        ecoinvent_login.download_cumulative_lcia = lambda *a, **k: path
        try:
            r = self.api.job("/api/ecoinvent/validate", {"username": "u", "password": "p", "version": "3.11",
                                                         "system_model": "cutoff", "db_name": demo.DB_NAME, "sample": 0})
            self.assertEqual(r["database"], demo.DB_NAME)
            self.assertEqual(r["datasets"], n_acts)
            self.assertEqual(r["families"], [demo.FAMILY])
            # install with an existing database: not imported again, validated
            res = self.api.job("/api/ecoinvent/install", {"username": "u", "password": "p", "version": "3.11",
                                                          "system_model": "cutoff", "name": demo.DB_NAME, "sample": 10})
            self.assertTrue(any("already in the library" in w for w in res["warnings"]))
            self.assertLessEqual(res["benchmark"]["datasets"], 10)
            self.api("POST", "/api/ecoinvent/validate", {"username": "u", "password": "p", "version": "9", "system_model": "x"},
                     ok=False)
            ecoinvent_login.download_cumulative_lcia = lambda *a, **k: (_ for _ in ()).throw(ValueError("no access"))
            res = self.api.job("/api/ecoinvent/install", {"username": "u", "password": "p", "version": "3.11",
                                                          "system_model": "cutoff", "name": demo.DB_NAME})
            self.assertIn("no access", res["benchmark"]["error"])
        finally:
            ecoinvent_login.download_cumulative_lcia = orig
        self.assertEqual(ecoinvent_login.find_xlsx(path), path)

    def test_openlca_product_ids(self):
        st = self.st
        steel = demo.act_id(st, "steel")
        pu = "22222222-2222-4222-8222-222222222222"
        st.x("UPDATE activities SET product_uuid=? WHERE id=?", (pu, steel))
        o = self.api("POST", "/api/export/openlca", {"model_ids": [self.wall]})
        with zipfile.ZipFile(o["path"]) as z:
            self.assertIn(f"flows/{pu}.json", z.namelist())
            p = json.loads(z.read([n for n in z.namelist() if n.startswith("processes/")][0]))
        self.assertTrue(any(e["flow"]["@id"] == pu for e in p["exchanges"]))
        st.x("UPDATE activities SET product_uuid=NULL WHERE id=?", (steel,))


class TestScience(unittest.TestCase):
    def test_factor_interpolation(self):
        self.assertEqual(science._factor({"2050": 0.5}, 2020, 2035), 0.75)
        self.assertEqual(science._factor({"2030": 0.8, "2050": 0.4}, 2020, 2040), 0.6000000000000001)
        self.assertEqual(science._factor({"2050": 0.5}, 2020, 2010), 1.0)
        self.assertEqual(science._factor({"2050": 0.5}, 2020, 2070), 0.5)
        self.assertEqual(science._factor(0.3, 2020, None), 0.3)

    def test_fate_limits(self):
        persistent = science.fate_model({"mw": 300, "log_kow": 6, "henry": 0.01, "hl_air": 100, "hl_water": 1000,
                                         "hl_soil": 1000})
        quick = science.fate_model({"mw": 300, "log_kow": 6, "henry": 0.01, "hl_air": 1, "hl_water": 1, "hl_soil": 1})
        self.assertGreater(persistent["persistence_days"]["water"], quick["persistence_days"]["water"])
        self.assertLess(persistent["mass_balance_error"], 1e-9)

    def test_diff_identical(self):
        snap = {"model": {"name": "a", "product": "", "unit": "kg", "amount": 1, "scope": "{}"}, "inputs": [], "parameters": []}

        class S:
            def one(self, *a):
                return None
        self.assertTrue(productivity.diff_snapshots(S(), snap, snap)["identical"])


if __name__ == "__main__":
    unittest.main()
