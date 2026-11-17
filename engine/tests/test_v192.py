"""Cyclia 1.9.2: numerical resolution of deviating benchmark results, their contributions, negative exchanges, and
the cause text of the inventory comparison.

The 1.9.1 run on ecoinvent 3.13 showed that the round-off rule of 1.9.1 did not apply to Ecological Scarcity 2021
'biotic resources': Cyclia's results there are not remainders of cancelling contributions (the sum of absolute
contributions is close to the net value). 1.9.2 measures instead whether Cyclia's solution resolves each deviating
result at all, and lists what carries the result."""
import os
import sys
import unittest

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trust  # noqa: E402


class _LU:
    """splu with an optional error added to the transposed solve, to stand for a result the solver does not resolve."""

    def __init__(self, A, noise=0.0):
        self.lu, self.noise = splu(sp.csc_matrix(A)), noise

    def solve(self, b, trans="N"):
        v = self.lu.solve(np.asarray(b, dtype=float), trans=trans)
        return v + self.noise if trans == "T" else v


class _MC:
    def __init__(self, noise=0.0):
        # 3 datasets: 0 uses 1 and 2; dataset 2 emits a flow with factor 10
        self.A = sp.csc_matrix(np.array([[1.0, 0, 0], [-0.5, 1.0, 0], [-1e-6, 0, 1.0]]))
        self.B = sp.csc_matrix(np.array([[0.0, 0.0, 2.0]]))
        self.n = 3
        self.diag = np.ones(3)
        self.act_index = {10: 0, 11: 1, 12: 2}
        self.act_ids = np.array([10, 11, 12])
        self.flow_ids = np.array([5])
        self.lu = _LU(self.A, noise)

    def solve(self, f):
        return self.lu.solve(f)


class _M:
    def __init__(self, mc):
        self.C = sp.csr_matrix(np.array([[10.0]]))
        self.Q = np.asarray((self.C @ mc.B).todense())


def _row(reference, cyclia):
    return {"method_id": 1, "act_id": 10, "note": "", "reference": reference, "cyclia": cyclia,
            "deviation_percent": (cyclia - reference) / abs(reference) * 100, "category": "c", "indicator": "i",
            "activity": "a", "location": "GLO", "group": "Other"}


class TestResolution(unittest.TestCase):
    mcols = [{"id": "c1", "method": {"id": 1, "category": "c", "indicator": "i", "family": "F", "unit": "u"}}]

    def run_check(self, noise, reference, scale):
        mc = _MC(noise)
        M = _M(mc)
        h = float(M.Q[0] @ mc.solve(np.array([1.0, 0, 0])))   # 2e-5
        x = _row(reference, h)
        trust.resolution_check(mc, M, self.mcols, [x], [{"values": {"c1": scale}}])
        return x, h

    def test_resolved_deviation_stays_and_shows_its_source(self):
        x, h = self.run_check(0.0, 1e-5, 1e3)
        self.assertAlmostEqual(x["deviation_percent"], 100.0)
        self.assertEqual(x["note"], "")
        self.assertAlmostEqual(x["adjoint"], h, delta=1e-18)
        self.assertAlmostEqual(x["refined"], h, delta=1e-18)
        top = x["contributions"][0]
        self.assertEqual(top["act_index"], 2)                 # dataset 2 carries the result
        self.assertAlmostEqual(top["contribution"], h)
        self.assertEqual(top["flows"][0]["factor"], 10.0)

    def test_unresolved_negligible(self):
        x, h = self.run_check(1e-5, 1e-5, 1e3)                # largest result in the file 1e3: 2e-5 is negligible
        self.assertIsNone(x["deviation_percent"])
        self.assertTrue(x["note"].startswith("below numerical resolution"))

    def test_unresolved_but_not_negligible_stays_a_deviation(self):
        x, h = self.run_check(1e-5, 1e-5, 1.0)                # 2e-5 is not negligible next to 1
        self.assertAlmostEqual(x["deviation_percent"], 100.0)
        self.assertTrue(x["note"].startswith("not resolved"))

    def test_statistics_count_unresolved_apart(self):
        rows = [dict(_row(1.0, 1.0), deviation_percent=0.0),
                dict(_row(1e-12, 1e-10), deviation_percent=None, note="below numerical resolution: x")]
        class St:
            def one(self, *a):
                return {"n": 0}
        mc = _MC()
        mc.b_rows = np.array([0])
        res = trust._bench_summary(St(), mc, _M(mc), self.mcols, rows, 2, 2, 2, {"Other": []})
        stats = res["by_category"][0]
        self.assertEqual((stats["n"], stats["below_resolution"], stats["within_0_1"]), (1, 1, 100.0))
        self.assertIn("below numerical resolution", res["verdict"])


if __name__ == "__main__":
    unittest.main()
