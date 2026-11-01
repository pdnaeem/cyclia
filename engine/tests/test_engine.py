"""Cyclia engine test suite.   Run:  python -m unittest discover -s engine/tests -v"""
import json
import math
import os
import shutil
import sqlite3
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
import formula as fm  # noqa: E402
import inventory_io  # noqa: E402
import linking  # noqa: E402
import report  # noqa: E402
import units  # noqa: E402
from canon import canon  # noqa: E402
from importers import ecospold2, jsonld, lcia, other_formats, tutorial  # noqa: E402
from store import Workspace  # noqa: E402

CO2 = "349b29d1-3e58-4c66-98b9-9d1a076efd2e"
CH4 = "baf58fc9-573c-419c-8c16-831ac03203b9"


def gwp(st):
    return [m["id"] for m in st.methods() if m["category"] == "climate change"]


def write_spold(folder, act, prod, name, unit, prodamt, inputs, elems, loc="FR", unc=""):
    ix = "".join(
        f'<intermediateExchange id="x{i}" intermediateExchangeId="{p}" activityLinkId="{a}" amount="{amt}">'
        f'<name>{p}</name><unitName>kg</unitName>{unc}<inputGroup>5</inputGroup></intermediateExchange>'
        for i, (a, p, amt) in enumerate(inputs))
    ex = "".join(
        f'<elementaryExchange id="e{i}" elementaryExchangeId="{u}" amount="{amt}"><name>{n}</name><unitName>kg</unitName>'
        f'<compartment subcompartmentId="s"><compartment>air</compartment><subcompartment>unspecified</subcompartment>'
        f'</compartment>{unc}<outputGroup>4</outputGroup></elementaryExchange>' for i, (u, n, amt) in enumerate(elems))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><ecoSpold xmlns="http://www.EcoInvent.org/EcoSpold02"><activityDataset>'
           f'<activityDescription><activity id="{act}" activityNameId="n"><activityName>{name}</activityName></activity>'
           f'<geography><shortname>{loc}</shortname></geography></activityDescription><flowData>'
           f'<intermediateExchange id="r" intermediateExchangeId="{prod}" amount="{prodamt}"><name>{prod}</name>'
           f'<unitName>{unit}</unitName><outputGroup>0</outputGroup></intermediateExchange>{ix}{ex}</flowData>'
           f'</activityDataset></ecoSpold>')
    with open(os.path.join(folder, f"{act}_{prod}.spold"), "w") as fh:
        fh.write(xml)


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


class TestBasics(unittest.TestCase):
    def test_units(self):
        self.assertAlmostEqual(units.factor("g", "kg"), 1e-3)
        self.assertAlmostEqual(units.factor("kWh", "MJ"), 3.6)
        self.assertAlmostEqual(units.factor("kg*km", "t*km"), 1e-3)
        self.assertAlmostEqual(units.factor("ha*a", "m2*year"), 1e4)
        self.assertIsNone(units.factor("kg", "MJ"))

    def test_formula(self):
        self.assertEqual(fm.evaluate("2*a + b^2", {"a": 3, "b": 2}), 10)
        self.assertEqual(fm.evaluate("if_(a > 1, 5, 7)", {"a": 2}), 5)
        self.assertEqual(fm.resolve([{"name": "a", "value": 2, "formula": None},
                                     {"name": "b", "value": 0, "formula": "a*3"}], {"a": 4}), {"a": 4.0, "b": 12.0})
        for bad in ("__import__('os')", "a.b", "open('x')", "1/0", "a +", "[1]"):
            with self.assertRaises(fm.FormulaError):
                fm.evaluate(bad, {"a": 1})
        with self.assertRaises(fm.FormulaError):
            fm.resolve([{"name": "a", "value": 0, "formula": "b"}, {"name": "b", "value": 0, "formula": "a"}])
        self.assertFalse(fm.valid_name("1x"))
        self.assertFalse(fm.valid_name("pi"))

    def test_canon(self):
        self.assertEqual(canon("Carbon dioxide (fossil)", "Emissions to air", "Emissions to urban air close to ground"),
                         ("carbon dioxide, fossil", "air", "urban air close to ground"))
        self.assertEqual(canon("x", "Emission to water", "ground water, long-term")[1:], ("water", "ground-, long-term"))
        self.assertEqual(canon("x", "Resources", "Resources from ground")[1:], ("natural resource", "in ground"))
        self.assertEqual(canon("x", "Land use", "Land occupation")[1:], ("natural resource", "land"))


class TestTutorialCalc(Base):
    def setUp(self):
        super().setUp()
        tutorial.install(self.st)
        self.find = lambda q: self.st.search_activities(q)[0]["id"]

    def model(self, name="Wall", **scope):
        sc = {"goal": "g", "boundary": "cradle-to-gate", **scope}
        return self.st.save_model({"name": name, "product": "wall", "unit": "m2", "amount": 1, "scope": sc})

    def total(self, m, **kw):
        return calc.run(self.st, m, gwp(self.st), **kw)["results"][0]["total"]

    def test_hand_calculation(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        self.st.add_input(m, "activity", self.find("reinforcing steel"), 12)
        self.st.add_input(m, "flow", self.st.search_flows("carbon dioxide fossil")[0]["id"], 0.5, "on-site CO2")
        r = calc.run(self.st, m, gwp(self.st))
        self.assertAlmostEqual(r["results"][0]["total"], 70.7167, places=3)
        self.assertAlmostEqual(sum(b["impact"] for b in r["results"][0]["by_input"]), r["results"][0]["total"], places=9)

    def test_independent_dense_solution(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("hempcrete"), 110)
        mids = [x["id"] for x in self.st.methods() if x["family"].startswith("Tutorial")]
        r = calc.run(self.st, m, mids)
        mc = calc._cache
        s = np.linalg.solve(mc.A.toarray(), (lambda f: (f.__setitem__(mc.act_index[self.find("hempcrete")], 110), f)[1])(np.zeros(mc.n)))
        M = calc.Methods(self.st, mc, mids)
        h = M.C @ (mc.B.toarray() @ s)
        for k in range(len(mids)):
            self.assertTrue(math.isclose(r["results"][k]["total"], h[k], rel_tol=1e-9, abs_tol=1e-12))

    def test_lci_and_uncharacterised(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("hemp shiv"), 10)
        r = calc.run(self.st, m, gwp(self.st))
        names = {x["name"] for x in r["lci"]}
        self.assertIn("Carbon dioxide, fossil", names)
        self.assertIn("Ammonia", {u["name"] for u in r["uncharacterised"]})  # NH3 has no GWP factor
        co2air = next(x for x in r["lci"] if x["name"] == "Carbon dioxide, in air")
        self.assertAlmostEqual(co2air["amount"], 16.0)

    def test_builtin_gwp_biogenic(self):
        fam = lcia.BUILTIN_FAMILY
        lcia.install_builtin(self.st)
        ids = {m["category"]: m["id"] for m in self.st.methods() if m["family"] == fam}
        m = self.model()
        self.st.add_input(m, "activity", self.find("sawn timber"), 1)
        r = calc.run(self.st, m, [ids["climate change: fossil"], ids["climate change: biogenic"], ids["climate change: total"]])
        fossil, bio, total = [x["total"] for x in r["results"]]
        self.assertAlmostEqual(bio, -750.0, places=6)  # 750 kg CO2 taken up from air
        self.assertAlmostEqual(total, fossil + bio, places=6)
        tut = self.total(m)
        self.assertAlmostEqual(fossil, tut, places=6)  # tutorial GWP = same fossil factors (no CH4 non-fossil here)

    def test_stages_and_module_d(self):
        m = self.model(stage_system="EN 15804 (construction products)")
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, stage="A1 Raw material supply")
        self.st.add_input(m, "activity", self.find("lorry"), 10, stage="A4 Transport to site")
        self.st.add_input(m, "activity", self.find("steel"), 2, stage="D Benefits", avoided=True)
        r = calc.run(self.st, m, gwp(self.st))
        res = r["results"][0]
        ac = sum(s["impact"] for s in res["by_stage"] if not s["module_d"])
        self.assertAlmostEqual(res["total"], ac, places=9)
        self.assertLess(res["module_d"], 0)
        self.assertTrue(r["has_module_d"])
        m2 = self.model("no D")
        self.st.add_input(m2, "activity", self.find("concrete"), 0.2)
        self.st.add_input(m2, "activity", self.find("lorry"), 10)
        self.assertAlmostEqual(res["total"], self.total(m2), places=9)

    def test_avoided_product_outside_d(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        base = self.total(m)
        self.st.add_input(m, "activity", self.find("steel"), 2, avoided=True)
        r = calc.run(self.st, m, gwp(self.st))
        self.assertAlmostEqual(r["results"][0]["total"], base - 2 * r["lines"][1]["unit_impact"][0], places=9)

    def test_allocation_manual_and_coproducts(self):
        a = self.model("a", alloc_share=40)
        self.st.add_input(a, "activity", self.find("concrete"), 0.2)
        full = self.model("full")
        self.st.add_input(full, "activity", self.find("concrete"), 0.2)
        self.assertAlmostEqual(self.total(a), 0.4 * self.total(full), places=9)
        cp = self.model("cp", alloc_basis="price", main_price=30, coproducts=[{"name": "grain", "price": 70}])
        self.st.add_input(cp, "activity", self.find("concrete"), 0.2)
        self.assertAlmostEqual(self.total(cp), 0.3 * self.total(full), places=9)
        with self.assertRaises(ValueError):
            self.st.save_model({"name": "x", "unit": "m2", "amount": 1, "scope": {"alloc_share": 150}})

    def test_parameters_formulas_scenarios(self):
        m = self.model()
        self.st.save_parameter({"name": "thickness", "value": 0.2})
        self.st.save_parameter({"model_id": m, "name": "volume", "formula": "thickness * 1"})
        c = self.find("concrete")
        self.st.add_input(m, "activity", c, 0.2, formula="volume", input_amount=0.2, input_unit="m3")
        r = calc.run(self.st, m, gwp(self.st))
        self.assertAlmostEqual(r["parameters"]["volume"], 0.2)
        base = r["results"][0]["total"]
        sid = self.st.save_scenario({"name": "thick", "overrides": {"thickness": 0.3}})
        self.assertAlmostEqual(self.total(m, scenario=sid), 1.5 * base, places=9)
        ps = r["parameter_sensitivity"]
        self.assertEqual(ps[0]["name"], "thickness")
        self.assertAlmostEqual(ps[0]["high"][0], 0.1 * base, places=9)
        cmp_ = calc.compare_scenarios(self.st, m, gwp(self.st), [sid])
        self.assertAlmostEqual(cmp_["scenarios"][1]["totals"][0], 1.5 * base, places=9)
        with self.assertRaises(ValueError):
            self.st.save_parameter({"name": "thickness", "value": 1})  # duplicate
        with self.assertRaises(ValueError):
            self.st.save_parameter({"name": "bad name", "value": 1})

    def test_parameter_distribution_mc(self):
        m = self.model()
        self.st.save_parameter({"name": "t", "value": 0.2, "utype": 4, "p1": 0.1, "p2": 0.3})
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, formula="t", input_amount=0.2, input_unit="m3",
                          pedigree=[1, 1, 1, 1, 1])
        r = calc.run(self.st, m, gwp(self.st), mc_iterations=3000)
        u = r["uncertainty"]["methods"][0]
        tot = r["results"][0]["total"]
        self.assertAlmostEqual(u["mean"] / tot, 1.0, delta=0.03)
        self.assertLess(u["p2_5"], 0.6 * tot)  # uniform 0.1-0.3 spreads widely
        s = calc.sobol(self.st, m, gwp(self.st), n=256)
        idx = s["factors"].index("parameter: t")
        self.assertGreater(s["ST"][idx][0], 0.9)

    def test_sobol_consistency(self):
        m = self.model()
        self.st.save_parameter({"name": "t", "value": 0.2, "utype": 4, "p1": 0.18, "p2": 0.22})
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, formula="t", input_amount=0.2, input_unit="m3")
        self.st.add_input(m, "activity", self.find("reinforcing steel"), 12)
        s = calc.sobol(self.st, m, gwp(self.st), n=2048)
        s1 = [x[0] for x in s["S1"]]
        st_ = [x[0] for x in s["ST"]]
        for a, b in zip(s1, st_):
            self.assertLessEqual(a, b + 0.05)  # first order never exceeds total (within sampling error)
        self.assertAlmostEqual(sum(s1), 1.0, delta=0.08)  # nearly additive model

    def test_fixed_epd_line(self):
        m = self.model()
        key = next(x for x in self.st.methods() if x["category"] == "climate change")
        fx = {"name": "Insulation EPD", "unit": "kg", "impacts": [{"family": key["family"], "category": key["category"],
                                                                     "indicator": key["indicator"], "value": 2.5}]}
        self.st.add_input(m, "fixed", None, 4, fixed=fx, input_unit="kg")
        r = calc.run(self.st, m, gwp(self.st))
        self.assertAlmostEqual(r["results"][0]["total"], 10.0)
        self.assertTrue(any("EPD" in p["name"] for p in r["results"][0]["processes"]))

    def test_nested_model_loop_undo(self):
        wall = self.model()
        self.st.add_input(wall, "activity", self.find("concrete"), 0.2)
        bld = self.st.save_model({"name": "Building", "product": "b", "unit": "p", "amount": 1})
        self.st.add_input(bld, "model", wall, 250)
        self.assertAlmostEqual(self.total(bld), 250 * self.total(wall), places=6)
        with self.assertRaises(ValueError):
            self.st.add_input(wall, "model", bld, 1)
        self.st.snapshot(wall, "add steel")
        self.st.add_input(wall, "activity", self.find("steel"), 1)
        self.assertEqual(len(self.st.model(wall)["inputs"]), 2)
        self.assertEqual(self.st.undo(wall), "add steel")
        self.assertEqual(len(self.st.model(wall)["inputs"]), 1)
        with self.assertRaises(ValueError):
            self.st.undo(wall)

    def test_tree_adds_up(self):
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        mid = gwp(self.st)[0]
        root = calc.tree(self.st, m, mid)
        self.assertAlmostEqual(root["total"], self.total(m), places=9)
        kid = root["children"][0]
        sub = calc.tree(self.st, m, mid, kid["node"], kid["amount"])
        self.assertAlmostEqual(sub["direct"] + sum(c["impact"] for c in sub["children"]) + sub["rest"], sub["total"], places=9)

    def test_dynamic_gwp(self):
        self.assertAlmostEqual(calc.dynamic_weight("CO2", 0), 1.0)
        self.assertAlmostEqual(calc.dynamic_weight("CH4f", 0), 29.8)
        self.assertLess(calc.dynamic_weight("CO2", 50), 0.7)
        self.assertEqual(calc.dynamic_weight("CO2", 120), 0.0)
        m = self.model()
        steel = self.find("steel")
        self.st.add_input(m, "activity", steel, 1, year=0)
        self.st.add_input(m, "activity", steel, 1, year=60)
        d = calc.run(self.st, m, gwp(self.st))["dynamic_gwp"]
        self.assertAlmostEqual(d["by_line"][0]["dynamic"], d["by_line"][0]["static"], places=9)
        self.assertLess(d["by_line"][1]["dynamic"], 0.6 * d["by_line"][1]["static"])

    def test_full_mc_pairs_and_cancel(self):
        a = self.model("A")
        self.st.add_input(a, "activity", self.find("concrete"), 0.2)
        b = self.model("B")
        self.st.add_input(b, "activity", self.find("concrete"), 0.3)
        out = calc.full_mc(self.st, [a, b], gwp(self.st), iterations=60)
        self.assertEqual(out["mode"], "full")
        self.assertGreaterEqual(out["pairs"][0]["p_a_lower"][0], 0.9)  # foreground data-quality draws are independent per model
        with self.assertRaises(calc.Cancelled):
            calc.full_mc(self.st, [a], gwp(self.st), iterations=50, cancelled=lambda: True)

    def test_regional_factors(self):
        p = os.path.join(self.dir, "reg.csv")
        with open(p, "w") as fh:
            fh.write("method,category,indicator,unit,flow_name,compartment,subcompartment,cf,flow_uuid,location\n"
                     "Water,scarcity,AWARE,m3 world-eq,\"Water, well, in ground\",natural resource,,1,,\n"
                     "Water,scarcity,AWARE,m3 world-eq,\"Water, well, in ground\",natural resource,,40,,GLO\n")
        lcia.import_cf_csv(self.st, p)
        mid = next(m["id"] for m in self.st.methods() if m["family"] == "Water")
        m = self.model()
        self.st.add_input(m, "activity", self.find("tap water"), 1000)
        r = calc.run(self.st, m, [mid])
        self.assertAlmostEqual(r["results"][0]["total"], 1000 * 0.001 * 1 + 1000 * 0.0005 * 0.002 * 1, places=9)

    def test_regional_by_location(self):
        st = self.st
        mid = st.get_or_create_method("Reg", "water", "w", "m3", "test")
        lcia.store_raw(st, mid, [("Water, well, in ground", "natural resource", "", "", None, 1.0),
                                 ("Water, well, in ground", "natural resource", "", "XX", None, 10.0)])
        lcia.rematch(st, [mid])
        tap = self.find("tap water")
        st.x("UPDATE activities SET location='XX' WHERE id=?", (tap,))
        st.bump_version()
        m = self.model()
        st.add_input(m, "activity", tap, 1000)
        r = calc.run(st, m, [mid])
        # tap water's own water use (0.001 m3/kg) is characterised with the XX factor; electricity's with 1
        self.assertAlmostEqual(r["results"][0]["total"], 1000 * 0.001 * 10 + 1000 * 0.0005 * 0.002 * 1, places=9)

    def test_checks_and_errors(self):
        bare = self.st.save_model({"name": "Bare", "product": "", "unit": "", "amount": 1})
        self.assertIn("error", {c["level"] for c in calc.checks(self.st, bare, gwp(self.st))})
        m = self.model(main_mass=10)
        self.st.add_input(m, "activity", self.find("steel"), 1)
        r = calc.run(self.st, m, gwp(self.st))
        msgs = " ".join(c["message"] for c in r["checks"])
        self.assertIn("tutorial", msgs.lower())
        self.assertIn("Mass balance", msgs)
        with self.assertRaises(calc.LCAError):
            calc.run(self.st, bare, gwp(self.st))
        with self.assertRaises(ValueError):
            self.st.add_input(m, "activity", 999999, 1)

    def test_normalisation_weighting(self):
        p = os.path.join(self.dir, "nw.csv")
        with open(p, "w") as fh:
            fh.write("method,category,indicator,set,normalisation,weighting\n"
                     "Tutorial: IPCC 2021 GWP100,climate change,,S,8000,0.2\n"
                     "Tutorial: CML-IA baseline,acidification,,S,55,0.06\n")
        self.assertEqual(lcia.import_nw_csv(self.st, p)["factors"], 2)
        m = self.model()
        self.st.add_input(m, "activity", self.find("concrete"), 0.2)
        mids = [x["id"] for x in self.st.methods() if x["category"] in ("climate change", "acidification")]
        r = calc.run(self.st, m, mids, nw_set="S")
        for x in r["results"]:
            f = (8000, 0.2) if x["category"] == "climate change" else (55, 0.06)
            self.assertAlmostEqual(x["weighted"], x["total"] / f[0] * f[1])

    def test_excel_round_trip(self):
        from openpyxl import Workbook
        m = self.model()
        p = os.path.join(self.dir, "inv.xlsx")
        wb = Workbook()
        ws = wb.active
        ws.title = "Inventory"
        ws.append(inventory_io.COLUMNS)
        ws.append(["dataset", "", "concrete production, ready-mix (tutorial)", "GLO", 200, "L", "A1", "", "EPD", "2,2,2,2,2"])
        ws.append(["emission", "", "Carbon dioxide, fossil", "air", 500, "g", "A3", "", "calc", ""])
        ws.append(["dataset", "", "reinforcing steel production (tutorial)", "GLO", 1, "kg", "D", "yes", "", ""])
        wb.save(p)
        self.assertEqual(inventory_io.import_rows(self.st, m, p)["added"], 3)
        out = os.path.join(self.dir, "out.xlsx")
        inventory_io.export(self.st, m, out)
        m2 = self.model("copy")
        self.assertEqual(inventory_io.import_rows(self.st, m2, out)["added"], 3)
        self.assertAlmostEqual(self.total(m), self.total(m2))
        bad = os.path.join(self.dir, "bad.xlsx")
        wb = Workbook()
        ws = wb.active
        ws.append(inventory_io.COLUMNS)
        ws.append(["dataset", "", "no such dataset", "", 1, "kg", "", "", "", ""])
        ws.append(["dataset", "", "concrete production, ready-mix (tutorial)", "GLO", 1, "kWh", "", "", "", ""])
        wb.save(bad)
        n = len(self.st.model(m)["inputs"])
        res = inventory_io.import_rows(self.st, m, bad)
        self.assertEqual((res["added"], len(res["problems"])), (0, 2))
        self.assertEqual(len(self.st.model(m)["inputs"]), n)

    def test_reports(self):
        m = self.model(stage_system="EN 15804 (construction products)")
        self.st.save_parameter({"model_id": m, "name": "d", "value": 5})
        self.st.add_input(m, "activity", self.find("concrete"), 0.2, stage="A1")
        self.st.add_input(m, "activity", self.find("lorry"), 5, stage="A4", formula="d", input_amount=5, input_unit="t*km")
        self.st.add_input(m, "activity", self.find("steel"), 1, stage="D", avoided=True)
        mids = [x["id"] for x in self.st.methods() if x["family"].startswith("Tutorial")]
        r = calc.run(self.st, m, mids, mc_iterations=300)
        doc, xl = os.path.join(self.dir, "r.docx"), os.path.join(self.dir, "r.xlsx")
        report.word_report(doc, self.st.model(m), r, self.st.databases(), "1.1.0")
        report.excel_results(xl, self.st.model(m), r)
        from docx import Document
        d = Document(doc)
        text = "\n".join(p.text for p in d.paragraphs)
        for needle in ("1. Goal and scope", "3. Life cycle impact assessment", "4.2 Evaluation", "Annex B"):
            self.assertIn(needle, text)
        self.assertTrue(any("Module D" in c.text for t in d.tables for c in t.rows[0].cells))
        from openpyxl import load_workbook
        self.assertTrue({"LCI", "Module D", "By stage"} <= set(load_workbook(xl).sheetnames))

    def test_validation(self):
        v = calc.validate_database(self.st)
        self.assertLess(v["max_relative_residual"], 1e-10)
        self.assertEqual(v["zero_production"], 0)

    def test_benchmark(self):
        m = self.model()
        c = self.find("concrete")
        self.st.add_input(m, "activity", c, 1)
        ref = self.total(m)
        out = calc.benchmark(self.st, [{"activity": "concrete production, ready-mix (tutorial)", "location": "GLO",
                                        "method": "Tutorial: IPCC 2021 GWP100", "category": "climate change",
                                        "indicator": "global warming potential (GWP100)", "value": ref * 1.001},
                                       {"activity": "nothing", "method": "x", "category": "y", "indicator": "", "value": 1}])
        self.assertEqual(out["compared"], 1)
        self.assertAlmostEqual(out["rows"][0]["deviation_percent"], -0.0999, places=3)
        self.assertEqual(out["n_missing"], 1)


class TestLibraryAndPortability(Base):
    def test_library_shared_and_project_portable(self):
        tutorial.install(self.st)
        c = self.st.search_activities("concrete")[0]["id"]
        m = self.st.save_model({"name": "w", "product": "w", "unit": "m2", "amount": 1})
        self.st.add_input(m, "activity", c, 0.2)
        other = self.ws.create("Other")
        self.assertEqual(len(other.databases()), 1)  # same library, no second import
        self.assertEqual(self.ws.database_usage("Tutorial database (illustrative)"), [{"project": "T", "lines": 1}])
        dest = os.path.join(self.dir, "share.lca")
        info = self.ws.export("T", dest)
        self.assertEqual(info["databases"], ["Tutorial database (illustrative)"])
        self.assertLess(os.path.getsize(dest), 200_000)  # the project file holds no database
        # a colleague's computer: new library with the same database imported (ids differ)
        other_dir = tempfile.mkdtemp()
        try:
            ws2 = Workspace(other_dir)
            s2 = ws2.create("Seed")
            s2.x("INSERT INTO databases(name, source) VALUES('padding', 'x')")
            s2.x("INSERT INTO activities(db_id, key, name) VALUES(1, 'k', 'pad')")
            tutorial.install(s2)
            name = ws2.import_file(dest)
            s3 = ws2.open(name)
            line = s3.model(s3.models()[0]["id"])["inputs"][0]
            self.assertFalse(line["missing"])
            self.assertNotEqual(line["ref_id"], c)
            self.assertEqual(line["target"]["name"], "concrete production, ready-mix (tutorial)")
            calc.invalidate()
            ref = calc.run(self.st, m, gwp(self.st))["results"][0]["total"]
            calc.invalidate()
            self.assertAlmostEqual(calc.run(s3, s3.models()[0]["id"], gwp(s3))["results"][0]["total"], ref, places=9)
            ws2.close_all()
            # without the database the line is reported missing, not silently wrong
            ws3 = Workspace(tempfile.mkdtemp())
            s4 = ws3.open(ws3.import_file(dest))
            line = s4.model(s4.models()[0]["id"])["inputs"][0]
            self.assertTrue(line["missing"])
            self.assertIn("Tutorial", line["target"]["name"])
            ws3.close_all()
        finally:
            shutil.rmtree(other_dir, ignore_errors=True)

    def test_legacy_project_moves_into_library(self):
        p = os.path.join(self.ws.dir, "Old.lca")
        c = sqlite3.connect(p)
        c.executescript("""
            CREATE TABLE databases (id INTEGER PRIMARY KEY, name TEXT UNIQUE, source TEXT, version TEXT, system_model TEXT,
              imported_at TEXT, n_activities INTEGER, note TEXT);
            CREATE TABLE activities (id INTEGER PRIMARY KEY, db_id INTEGER, key TEXT, name TEXT, product TEXT, location TEXT,
              unit TEXT, production REAL, comment TEXT);
            CREATE TABLE tech (output_id INTEGER, input_id INTEGER, amount REAL);
            CREATE TABLE flows (id INTEGER PRIMARY KEY, uuid TEXT, name TEXT, compartment TEXT, subcompartment TEXT, unit TEXT, cas TEXT);
            CREATE TABLE bio (activity_id INTEGER, flow_id INTEGER, amount REAL);
            CREATE TABLE methods (id INTEGER PRIMARY KEY, family TEXT, category TEXT, indicator TEXT, unit TEXT, source TEXT);
            CREATE TABLE cfs (method_id INTEGER, flow_id INTEGER, value REAL);
            CREATE TABLE models (id INTEGER PRIMARY KEY, name TEXT, product TEXT, unit TEXT, amount REAL, scope TEXT, created_at TEXT);
            CREATE TABLE model_inputs (id INTEGER PRIMARY KEY, model_id INTEGER, kind TEXT, ref_id INTEGER, amount REAL,
              label TEXT, comment TEXT, pedigree TEXT, position INTEGER);
            INSERT INTO databases VALUES (7, 'Old DB', 'x', '', '', '', 2, '');
            INSERT INTO activities VALUES (70, 7, 'a', 'electricity', 'electricity', 'FR', 'kWh', 1, '');
            INSERT INTO activities VALUES (71, 7, 'b', 'widget', 'widget', 'FR', 'kg', 1, '');
            INSERT INTO tech VALUES (71, 70, 2.0);
            INSERT INTO flows VALUES (5, 'u-co2', 'Carbon dioxide, fossil', 'air', 'unspecified', 'kg', '');
            INSERT INTO bio VALUES (70, 5, 0.5);
            INSERT INTO methods VALUES (3, 'M', 'climate change', 'GWP', 'kg', 'x');
            INSERT INTO cfs VALUES (3, 5, 1.0);
            INSERT INTO models VALUES (1, 'W', 'w', 'kg', 1, '{}', '');
            INSERT INTO model_inputs VALUES (1, 1, 'activity', 71, 3, '', '', '[3,3,3,3,3]', 1);
        """)
        c.commit()
        c.close()
        st = self.ws.open("Old")
        self.assertNotIn("activities", {r["name"] for r in st.q("SELECT name FROM main.sqlite_master")})
        line = st.model(1)["inputs"][0]
        self.assertEqual((line["ref_db"], line["target"]["name"]), ("Old DB", "widget"))
        mid = st.method_by_key("M", "climate change", "GWP")["id"]
        self.assertAlmostEqual(calc.run(st, 1, [mid])["results"][0]["total"], 3 * 2 * 0.5)


class TestImporters(Base):
    def test_ecospold2_unlinked_and_link(self):
        d = os.path.join(self.dir, "ei", "datasets")
        os.makedirs(d)
        unc = '<uncertainty><lognormal meanValue="1" mu="0" variance="0.01" varianceWithPedigreeUncertainty="0.04"/></uncertainty>'
        write_spold(d, "A1", "P1", "market for electricity", "kWh", 1, [("A2", "P2", 0.5)], [(CO2, "Carbon dioxide, fossil", 0.1)], unc=unc)
        write_spold(d, "A2", "P2", "electricity production, coal", "kWh", 1, [("A1", "P1", 0.05)],
                    [(CO2, "Carbon dioxide, fossil", 0.9), (CH4, "Methane, fossil", 0.001)])
        write_spold(d, "A3", "P3", "treatment of waste", "kg", -1, [("A1", "P1", 0.2)], [(CH4, "Methane, fossil", 0.05)])
        write_spold(d, "A4", "P4", "widget production", "kg", 1, [("A1", "P1", 2), ("A3", "P3", -0.5), ("ZZ", "PZ", 1)], [])
        with open(os.path.join(d, "broken.spold"), "w") as fh:
            fh.write("<not xml")
        res = ecospold2.import_folder(self.st, os.path.dirname(d), "ei", "3.10", "cut-off")
        self.assertEqual(res["activities"], 4)
        self.assertAlmostEqual(self.st.one("SELECT p1 FROM tech WHERE utype=1")["p1"], 0.2)
        p = os.path.join(self.dir, "cf.csv")
        with open(p, "w") as fh:
            fh.write("method;category;indicator;unit;flow_name;compartment;subcompartment;cf\n"
                     "IPCC;climate change;GWP;kg CO2-eq;Carbon dioxide, fossil;air;;1\n"
                     "IPCC;climate change;GWP;kg CO2-eq;Methane, fossil;air;unspecified;29,8\n")
        self.assertEqual(lcia.import_cf_csv(self.st, p)["factors_matched"], 2)
        w = self.st.search_activities("widget")[0]["id"]
        m = self.st.save_model({"name": "w", "product": "w", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", w, 1)
        A = np.array([[1, -0.05, -0.2, -2], [-0.5, 1, 0, 0], [0, 0, -1, 0.5], [0, 0, 0, 1.]])
        s = np.linalg.solve(A, np.array([0, 0, 0, 1.]))
        expected = 0.1 * s[0] + 0.9 * s[1] + 29.8 * (0.001 * s[1] + 0.05 * s[2])
        self.assertAlmostEqual(calc.run(self.st, m, gwp(self.st))["results"][0]["total"], expected, places=10)
        db = self.st.databases()[0]
        self.assertEqual(db["n_unlinked"], 1)
        # link the missing supplier PZ to the tutorial steel (another database): 1 kg PZ per widget
        tutorial.install(self.st)
        steel = self.st.search_activities("reinforcing steel")[0]
        g = linking.groups(self.st, db["id"])[0]
        self.assertEqual(g["product"], "PZ")
        linking.link(self.st, db["id"], "PZ", "kg", steel["id"])
        m2 = self.st.save_model({"name": "s", "product": "s", "unit": "kg", "amount": 1})
        self.st.add_input(m2, "activity", steel["id"], 1)
        steel_gwp = calc.run(self.st, m2, gwp(self.st))["results"][0]["total"]
        self.assertAlmostEqual(calc.run(self.st, m, gwp(self.st))["results"][0]["total"], expected + steel_gwp, places=9)
        linking.unlink(self.st, db["id"], "PZ", "kg")
        self.assertAlmostEqual(calc.run(self.st, m, gwp(self.st))["results"][0]["total"], expected, places=10)

    def test_failed_import_leaves_nothing(self):
        d = os.path.join(self.dir, "empty", "datasets")
        os.makedirs(d)
        with open(os.path.join(d, "x.spold"), "w") as fh:
            fh.write("<x/>")
        with self.assertRaises(ValueError):
            ecospold2.import_folder(self.st, os.path.dirname(d), "nothing")
        self.assertEqual(self.st.databases(), [])

    def test_methods_before_databases_rematch(self):
        p = os.path.join(self.dir, "cf.csv")
        with open(p, "w") as fh:
            fh.write("method,category,indicator,unit,flow_name,compartment,subcompartment,cf\n"
                     "Early,climate change,GWP,kg,\"Carbon dioxide (fossil)\",Emissions to air,,1\n")
        r = lcia.import_cf_csv(self.st, p)
        self.assertEqual(r["factors_unmatched"], 1)
        tutorial.install(self.st)  # adds the flow later; the factor must match automatically
        mid = self.st.method_by_key("Early", "climate change", "GWP")["id"]
        self.assertGreater(self.st.one("SELECT COUNT(*) AS n FROM cfs WHERE method_id=?", (mid,))["n"], 0)

    def test_flow_mapping_fedefl_format(self):
        tutorial.install(self.st)
        p = os.path.join(self.dir, "m.csv")
        with open(p, "w") as fh:
            fh.write("method,category,indicator,unit,flow_name,compartment,subcompartment,cf\n"
                     "TRACI,global warming,GWP,kg,CO2-fedefl,air,,1\n")
        lcia.import_cf_csv(self.st, p)
        mid = self.st.method_by_key("TRACI", "global warming", "GWP")["id"]
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM cfs WHERE method_id=?", (mid,))["n"], 0)
        mp = os.path.join(self.dir, "map.csv")
        with open(mp, "w") as fh:
            fh.write("SourceListName,SourceFlowName,SourceFlowUUID,SourceFlowContext,SourceUnit,MatchCondition,"
                     "ConversionFactor,TargetListName,TargetFlowName,TargetFlowUUID,TargetFlowContext,TargetUnit\n"
                     "ecoinvent,\"Carbon dioxide, fossil\",,air/unspecified,kg,=,1,FEDEFL,CO2-fedefl,,emission/air,kg\n")
        r = lcia.import_mapping_csv(self.st, mp)
        self.assertEqual(r["factors_added"], 1)

    def test_lcia_xlsx(self):
        tutorial.install(self.st)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "CFs"
        ws.append(["Method", "Category", "Indicator", "Name", "Compartment", "Subcompartment", "CF"])
        ws.append(["EF v3.1", "climate change", "GWP100", "Methane, fossil", "air", "unspecified", 29.8])
        ws.append(["EF v3.1", "climate change", "GWP100", "Unknown gas", "air", "unspecified", 5])
        ws2 = wb.create_sheet("Indicators")
        ws2.append(["Method", "Category", "Indicator", "Indicator Unit"])
        ws2.append(["EF v3.1", "climate change", "GWP100", "kg CO2-Eq"])
        p = os.path.join(self.dir, "l.xlsx")
        wb.save(p)
        r = lcia.import_ecoinvent_lcia_xlsx(self.st, p)
        self.assertEqual((r["factors_matched"], r["factors_unmatched"]), (1, 1))

    def _jsonld(self, path, with_processes=True):
        z = zipfile.ZipFile(path, "w")
        put = lambda pth, o: z.writestr(pth, json.dumps(o))
        put("unit_groups/ug.json", {"@id": "ug", "units": [{"@id": "kg", "name": "kg", "conversionFactor": 1, "isRefUnit": True},
                                                           {"@id": "g", "name": "g", "conversionFactor": 0.001}]})
        put("flow_properties/mass.json", {"@id": "mass", "unitGroup": {"@id": "ug"}})
        for fid, name, ft, cat in [("fp1", "steel", "PRODUCT_FLOW", "P"), ("fp2", "bolt", "PRODUCT_FLOW", "P"),
                                   ("fw", "scrap", "WASTE_FLOW", "W"), ("fx", "zinc", "PRODUCT_FLOW", "P"),
                                   ("fe", "Carbon dioxide, fossil", "ELEMENTARY_FLOW", "Elementary flows/Emission to air/unspecified")]:
            put(f"flows/{fid}.json", {"@id": fid, "name": name, "flowType": ft, "category": cat,
                                      "flowProperties": [{"flowProperty": {"@id": "mass"}, "conversionFactor": 1, "isRefFlowProperty": True}]})

        def ex(f, ft, amt, inp, ref=False, unit="kg", prov=None, unc=None):
            e = {"flow": {"@id": f, "flowType": ft}, "amount": amt, "isInput": inp, "isQuantitativeReference": ref,
                 "unit": {"@id": unit}, "flowProperty": {"@id": "mass"}}
            if prov:
                e["defaultProvider"] = {"@id": prov}
            if unc:
                e["uncertainty"] = unc
            return e
        if with_processes:
            put("processes/p1.json", {"@id": "p1", "name": "steel making", "location": {"name": "US"},
                                      "exchanges": [ex("fp1", "PRODUCT_FLOW", 1, False, True),
                                                    ex("fe", "ELEMENTARY_FLOW", 2000, False, unit="g",
                                                       unc={"distributionType": "LOG_NORMAL_DISTRIBUTION", "geomMean": 2000, "geomSd": 1.2})]})
            put("processes/p2.json", {"@id": "p2", "name": "bolt making",
                                      "exchanges": [ex("fp2", "PRODUCT_FLOW", 1, False, True), ex("fp1", "PRODUCT_FLOW", 1.1, True, prov="p1"),
                                                    ex("fw", "WASTE_FLOW", 0.1, False), ex("fx", "PRODUCT_FLOW", 0.05, True)]})
            put("processes/p3.json", {"@id": "p3", "name": "scrap treatment",
                                      "exchanges": [ex("fw", "WASTE_FLOW", 1, True, True), ex("fe", "ELEMENTARY_FLOW", 0.3, False)]})
        put("lcia_methods/m.json", {"@id": "m", "name": "TRACI 2.1", "impactCategories": [{"@id": "c1"}]})
        put("lcia_categories/c1.json", {"@id": "c1", "name": "Global warming", "refUnit": "kg CO2 eq",
                                        "impactFactors": [{"flow": {"@id": "fe", "name": "Carbon dioxide, fossil"}, "value": 1,
                                                           "unit": {"@id": "kg"}, "flowProperty": {"@id": "mass"}}]})
        z.close()

    def test_jsonld_full(self):
        p = os.path.join(self.dir, "db.zip")
        self._jsonld(p)
        res = jsonld.import_jsonld(self.st, p, "USLCI test")
        self.assertEqual((res["activities"], res["methods"]), (3, 1))
        self.assertEqual(self.st.databases()[0]["n_unlinked"], 1)  # zinc has no provider
        b = self.st.search_activities("bolt")[0]["id"]
        m = self.st.save_model({"name": "b", "product": "b", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", b, 1)
        r = calc.run(self.st, m, [x["id"] for x in self.st.methods() if x["family"] == "TRACI 2.1"])
        self.assertAlmostEqual(r["results"][0]["total"], 1.1 * 2 + 0.1 * 0.3)

    def test_jsonld_method_package_matches_by_name(self):
        tutorial.install(self.st)
        p = os.path.join(self.dir, "methods.zip")
        self._jsonld(p, with_processes=False)
        res = jsonld.import_jsonld(self.st, p, "method pack")
        self.assertEqual((res["database"], res["methods"]), (None, 1))
        mid = self.st.method_by_key("TRACI 2.1", "Global warming", "Global warming")["id"]
        self.assertEqual(self.st.one("SELECT COUNT(*) AS n FROM cfs WHERE method_id=?", (mid,))["n"], 1)

    def test_ecospold1(self):
        d = os.path.join(self.dir, "es1")
        os.makedirs(d)
        xml = ('<?xml version="1.0"?><ecoSpold xmlns="http://www.EcoInvent.org/EcoSpold01">'
               '<dataset number="1"><metaInformation><processInformation><referenceFunction name="power" unit="kWh"/>'
               '<geography location="CH"/></processInformation></metaInformation><flowData>'
               '<exchange name="power" unit="kWh" meanValue="1" location="CH"><outputGroup>0</outputGroup></exchange>'
               '<exchange name="Carbon dioxide, fossil" category="air" subCategory="unspecified" unit="kg" meanValue="0.4" '
               'uncertaintyType="1" standardDeviation95="1.21"><outputGroup>4</outputGroup></exchange></flowData></dataset>'
               '<dataset number="2"><metaInformation><processInformation><referenceFunction name="alu" unit="kg"/>'
               '<geography location="CH"/></processInformation></metaInformation><flowData>'
               '<exchange name="alu" unit="kg" meanValue="1" location="CH"><outputGroup>0</outputGroup></exchange>'
               '<exchange name="power" unit="kWh" meanValue="15" location="CH"><inputGroup>5</inputGroup></exchange>'
               '</flowData></dataset></ecoSpold>')
        with open(os.path.join(d, "x.xml"), "w") as fh:
            fh.write(xml)
        res = other_formats.import_ecospold1(self.st, d, "es1")
        self.assertEqual(res["activities"], 2)
        lcia.install_builtin(self.st)
        mid = self.st.method_by_key(lcia.BUILTIN_FAMILY, "climate change: fossil", "GWP100")["id"]
        m = self.st.save_model({"name": "a", "product": "a", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("alu")[0]["id"], 1)
        self.assertAlmostEqual(calc.run(self.st, m, [mid])["results"][0]["total"], 6.0)
        self.assertAlmostEqual(self.st.one("SELECT p1 FROM bio")["p1"], 0.5 * math.log(1.21))

    def test_simapro_csv(self):
        csvtext = ("{SimaPro 9.5.0}\n{CSV separator: Semicolon}\n{Decimal separator: .}\n\n"
                   "Process\n\nCategory type\nmaterial\n\nGeography\nFR\n\nProducts\nWheat grain;kg;1;80;not defined;Agri;\n\n"
                   "Materials/fuels\nDiesel;MJ;2;Lognormal;1.21;0;0;\nUnknown seed;kg;0.1;Undefined;0;0;0;\n\n"
                   "Emissions to air\nDinitrogen monoxide;low. pop.;kg;0.01;Undefined;0;0;0;\n\nEnd\n\n"
                   "Process\n\nProducts\nDiesel;MJ;1;100;not defined;Fuel;\n\n"
                   "Emissions to air\nCarbon dioxide, fossil;;kg;0.07;Undefined;0;0;0;\n\nEnd\n")
        p = os.path.join(self.dir, "sp.csv")
        with open(p, "w") as fh:
            fh.write(csvtext)
        res = other_formats.import_simapro_csv(self.st, p, "SimaPro test")
        self.assertEqual(res["activities"], 2)
        self.assertEqual(self.st.databases()[0]["n_unlinked"], 1)
        lcia.install_builtin(self.st)
        mid = self.st.method_by_key(lcia.BUILTIN_FAMILY, "climate change: fossil", "GWP100")["id"]
        m = self.st.save_model({"name": "g", "product": "g", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("wheat")[0]["id"], 1)
        # 80 % allocated: (2 MJ x 0.07 + 0.01 x 273) x 0.8
        self.assertAlmostEqual(calc.run(self.st, m, [mid])["results"][0]["total"], (2 * 0.07 + 0.01 * 273) * 0.8, places=9)

    def test_ilcd(self):
        p = os.path.join(self.dir, "ilcd.zip")
        z = zipfile.ZipFile(p, "w")
        C = 'xmlns:common="http://lca.jrc.it/ILCD/Common"'
        z.writestr("ILCD/unitgroups/u.xml", f'<unitGroupDataSet xmlns="http://lca.jrc.it/ILCD/UnitGroup" {C}><unitGroupInformation>'
                   '<dataSetInformation><common:UUID>ug</common:UUID></dataSetInformation><quantitativeReference>'
                   '<referenceToReferenceUnit>0</referenceToReferenceUnit></quantitativeReference></unitGroupInformation>'
                   '<units><unit dataSetInternalID="0"><name>kg</name><meanValue>1</meanValue></unit></units></unitGroupDataSet>')
        z.writestr("ILCD/flowproperties/m.xml", f'<flowPropertyDataSet xmlns="http://lca.jrc.it/ILCD/FlowProperty" {C}>'
                   '<flowPropertiesInformation><dataSetInformation><common:UUID>mass</common:UUID></dataSetInformation>'
                   '<quantitativeReference><referenceToReferenceUnitGroup refObjectId="ug"/></quantitativeReference>'
                   '</flowPropertiesInformation></flowPropertyDataSet>')

        def flow(uid, name, typ, cats=""):
            return (f'<flowDataSet xmlns="http://lca.jrc.it/ILCD/Flow" {C}><flowInformation><dataSetInformation>'
                    f'<common:UUID>{uid}</common:UUID><name><baseName>{name}</baseName></name>'
                    f'<classificationInformation><common:elementaryFlowCategorization>{cats}</common:elementaryFlowCategorization>'
                    '</classificationInformation></dataSetInformation><quantitativeReference><referenceToReferenceFlowProperty>0'
                    '</referenceToReferenceFlowProperty></quantitativeReference></flowInformation><modellingAndValidation>'
                    f'<LCIMethod><typeOfDataSet>{typ}</typeOfDataSet></LCIMethod></modellingAndValidation><flowProperties>'
                    '<flowProperty dataSetInternalID="0"><referenceToFlowPropertyDataSet refObjectId="mass"/><meanValue>1'
                    '</meanValue></flowProperty></flowProperties></flowDataSet>')
        z.writestr("ILCD/flows/a.xml", flow("fa", "cement", "Product flow"))
        z.writestr("ILCD/flows/b.xml", flow("fb", "mortar", "Product flow"))
        z.writestr("ILCD/flows/c.xml", flow("fc", "carbon dioxide (fossil)", "Elementary flow",
                                            '<common:category level="0">Emissions</common:category>'
                                            '<common:category level="1">Emissions to air</common:category>'
                                            '<common:category level="2">Emissions to air, unspecified</common:category>'))

        def proc(uid, name, ref, exs):
            body = "".join(f'<exchange dataSetInternalID="{i}"><referenceToFlowDataSet refObjectId="{f}"/>'
                           f'<exchangeDirection>{d}</exchangeDirection><meanAmount>{a}</meanAmount><resultingAmount>{a}</resultingAmount>'
                           '</exchange>' for i, (f, d, a) in enumerate(exs))
            return (f'<processDataSet xmlns="http://lca.jrc.it/ILCD/Process" {C}><processInformation><dataSetInformation>'
                    f'<common:UUID>{uid}</common:UUID><name><baseName>{name}</baseName></name></dataSetInformation>'
                    f'<quantitativeReference><referenceToReferenceFlow>{ref}</referenceToReferenceFlow></quantitativeReference>'
                    '<geography><locationOfOperationSupplyOrProduction location="DE"/></geography></processInformation>'
                    f'<exchanges>{body}</exchanges></processDataSet>')
        z.writestr("ILCD/processes/p1.xml", proc("p1", "cement production", 0, [("fa", "Output", 1), ("fc", "Output", 0.8)]))
        z.writestr("ILCD/processes/p2.xml", proc("p2", "mortar production", 0, [("fb", "Output", 1), ("fa", "Input", 0.25)]))
        z.close()
        res = other_formats.import_ilcd(self.st, p, "Oekobaudat test")
        self.assertEqual(res["activities"], 2)
        lcia.install_builtin(self.st)
        mid = self.st.method_by_key(lcia.BUILTIN_FAMILY, "climate change: fossil", "GWP100")["id"]
        m = self.st.save_model({"name": "m", "product": "m", "unit": "kg", "amount": 1})
        self.st.add_input(m, "activity", self.st.search_activities("mortar")[0]["id"], 1)
        self.assertAlmostEqual(calc.run(self.st, m, [mid])["results"][0]["total"], 0.2)


class TestApi(Base):
    def setUp(self):
        super().setUp()
        import server
        self.state = server.State(self.dir)
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.state, "tok"))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.state.ws.close_all()
        super().tearDown()

    def call(self, method, path, body=None, token="tok", expect=200):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                code, data = r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            code, data = e.code, json.loads(e.read())
        self.assertEqual(code, expect, data)
        return data

    def wait(self, job):
        for _ in range(600):
            j = self.call("GET", f"/api/jobs/{job['id']}")["job"]
            if j["status"] != "running":
                return j
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_full_study(self):
        self.call("GET", "/api/status", token="wrong", expect=403)
        self.call("POST", "/api/projects", {"name": "Thesis"})
        self.assertEqual(self.wait(self.call("POST", "/api/import/tutorial")["job"])["status"], "done")
        st = self.call("GET", "/api/status")
        self.assertTrue(any(m for m in st["databases"]))
        m = self.call("POST", "/api/models", {"name": "Wall", "product": "wall", "unit": "m2", "amount": 1,
                                              "scope": {"goal": "x", "boundary": "cradle-to-gate"}})["model"]
        conc = self.call("GET", "/api/search?q=concrete")["results"][0]
        self.call("POST", "/api/parameters", {"model_id": m["id"], "name": "vol", "value": 0.2})
        self.call("POST", "/api/parameters", {"model_id": m["id"], "name": "bad", "formula": "nope * 2"}, expect=400)
        self.call("POST", f"/api/models/{m['id']}/inputs", {"kind": "activity", "ref_id": conc["id"], "formula": "vol * 1000",
                                                            "unit": "l", "stage": "A1"})
        self.call("POST", f"/api/models/{m['id']}/inputs", {"kind": "activity", "ref_id": conc["id"], "formula": "zzz"}, expect=400)
        self.call("POST", f"/api/models/{m['id']}/inputs", {"kind": "activity", "ref_id": conc["id"], "amount": 1, "unit": "kWh"}, expect=400)
        line = self.call("GET", f"/api/models/{m['id']}")["model"]["inputs"][0]
        self.assertAlmostEqual(line["amount"], 0.2)
        self.call("PATCH", f"/api/inputs/{line['id']}", {"input_amount": 300, "input_unit": "l"})
        self.call("POST", f"/api/models/{m['id']}/undo", {})
        self.assertAlmostEqual(self.call("GET", f"/api/models/{m['id']}")["model"]["inputs"][0]["amount"], 0.2)
        steel = self.call("GET", "/api/search?q=reinforcing+steel")["results"][0]
        self.call("POST", f"/api/models/{m['id']}/inputs", {"kind": "activity", "ref_id": steel["id"], "amount": 1})
        line2 = self.call("GET", f"/api/models/{m['id']}")["model"]["inputs"][1]
        hemp = self.call("GET", "/api/search?q=hemp+shiv")["results"][0]
        self.call("POST", f"/api/inputs/{line2['id']}/replace", {"ref_id": hemp["id"]})
        mids = [x["id"] for x in self.call("GET", "/api/methods")["methods"]]
        r = self.call("POST", "/api/calculate", {"model_id": m["id"], "method_ids": mids, "mc_iterations": 200})
        self.assertEqual(len(r["results"]), len(mids))
        self.assertIn("lci", r)
        sid = self.call("POST", "/api/scenarios", {"name": "thick", "overrides": {"vol": 0.3}})["id"]
        r2 = self.call("POST", "/api/calculate", {"model_id": m["id"], "method_ids": mids, "scenario": sid})
        self.assertNotEqual([x["total"] for x in r2["results"]], [x["total"] for x in r["results"]])
        tr = self.call("GET", f"/api/tree?model_id={m['id']}&method_id={mids[0]}")
        self.assertTrue(tr["children"])
        j = self.wait(self.call("POST", "/api/sobol", {"model_id": m["id"], "method_ids": mids[:1], "n": 64})["job"])
        self.assertEqual(j["status"], "done", j)
        copy = self.call("POST", f"/api/activity/{conc['id']}/copy", {})["model"]
        self.assertTrue(copy["inputs"])
        dup = self.call("POST", f"/api/models/{m['id']}/duplicate", {})["model"]
        self.wait(self.call("POST", "/api/uncertainty", {"model_ids": [m["id"], dup["id"]], "method_ids": mids, "iterations": 25})["job"])
        for kind in ("word", "excel"):
            self.assertTrue(os.path.isfile(self.call("POST", f"/api/export/{kind}", {"model_id": m["id"], "method_ids": mids})["path"]))
        self.assertTrue(self.call("POST", "/api/validate", {})["sampled"] > 0)
        self.assertTrue(os.path.isfile(self.call("POST", "/api/diagnostics", {})["path"]))
        db = self.call("GET", "/api/databases")["databases"][0]
        self.call("DELETE", f"/api/databases/{db['id']}", expect=400)  # still used by the model
        self.call("GET", "/api/nothing", expect=404)


if __name__ == "__main__":
    unittest.main()
