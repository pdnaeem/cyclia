"""Scientific release gate (Cyclia 1.9.0). The installers are built only when this passes.

    python engine/tools/release_gate.py            # Brightway required (release builds, validation workflow)
    python engine/tools/release_gate.py --no-brightway   # local check without Brightway

It runs, and fails on the first that does not pass:
1. the whole test suite, with Brightway required: any skipped test is a failure, so the comparison with Brightway's
   own calculation (bw2calc, pinned in engine/tools/brightway-pins.txt) always runs and is never counted as passed
   when it did not run;
2. the full-library regression of the reference libraries (part of the suite: tests/test_regression.py), named
   separately in the summary;
3. the validation suite (35 product systems with exact answers) and the IPCC 2021 GWP100 check against the values
   published by the IPCC.
"""
import argparse
import os
import sys
import unittest

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)


def run_suite(require_brightway):
    if require_brightway:
        os.environ["CYCLIA_REQUIRE_BRIGHTWAY"] = "1"
    tests = os.path.join(ENGINE, "tests")
    sys.path.insert(0, tests)
    suite = unittest.defaultTestLoader.discover(tests, top_level_dir=tests)
    # counted before the run: the runner releases the tests it has run
    bw_tests = sum(1 for t in _iter(suite) if t.id().startswith("test_brightway.TestBrightway."))
    res = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
    bw_skipped = [t.id() for t, _ in res.skipped if t.id().startswith("test_brightway.")]
    reg_failed = [t.id() for t, _ in res.failures + res.errors if t.id().startswith("test_regression.")]
    bw_ran = bw_tests - len(bw_skipped)
    return res, bw_ran, bw_skipped, reg_failed


def _iter(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from _iter(t)
        else:
            yield t


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cyclia scientific release gate")
    ap.add_argument("--no-brightway", action="store_true", help="do not require Brightway (local use only)")
    args = ap.parse_args(argv)
    require = not args.no_brightway
    problems = []
    res, bw_ran, bw_skipped, reg_failed = run_suite(require)
    if res.failures or res.errors:
        problems.append(f"test suite: {len(res.failures)} failure(s), {len(res.errors)} error(s)")
    if reg_failed:
        problems.append("full-library regression: " + ", ".join(reg_failed))
    if require:
        if res.skipped:
            problems.append(f"{len(res.skipped)} test(s) skipped while Brightway is required: "
                            + ", ".join(t.id() for t, _ in res.skipped[:5]))
        if not bw_ran:
            problems.append("the Brightway comparison did not run (no test_brightway.TestBrightway test was found)")
    import benchmark
    import trust
    v = trust.validation_suite()
    if v["passed"] != v["total"]:
        problems.append(f"validation suite: {v['passed']} of {v['total']} systems reproduced")
    ipcc = benchmark.ipcc_check()
    if not ipcc["passed"]:
        problems.append("IPCC 2021 GWP100 check: " + ipcc["verdict"])
    print()
    print(f"Tests run: {res.testsRun}, failures: {len(res.failures)}, errors: {len(res.errors)}, "
          f"skipped: {len(res.skipped)}")
    print(f"Brightway comparison: {'required, ' if require else 'not required, '}{bw_ran} test(s), "
          f"{len(bw_skipped)} skipped")
    print(f"Full-library regression: {'passed' if not reg_failed else 'FAILED'}")
    print(f"Validation suite: {v['passed']} of {v['total']} systems reproduced")
    print(f"IPCC 2021 GWP100: {ipcc['verdict']}")
    if problems:
        print("\nRELEASE GATE FAILED")
        for p in problems:
            print(" - " + p)
        return 1
    print("\nRelease gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
