"""Full-library regression snapshots from the command line (Cyclia 1.9.0).

Record every dataset under every impact category, every model and the factor matching of a project, and compare
later versions of Cyclia (or a re-imported library) with that record:

    python engine/tools/regression.py record  --data DATA_DIR --project NAME --out ecoinvent-3.10.json.gz
    python engine/tools/regression.py compare ecoinvent-3.10.json.gz new.json.gz
    python engine/tools/regression.py check   --data DATA_DIR --project NAME --ref ecoinvent-3.10.json.gz
    python engine/tools/regression.py reference [--out engine/tests/data/reference_regression.json.gz]

DATA_DIR is Cyclia's data folder (Settings, "Data folder"); NAME the project that holds the library. Optional
filters: --family (repeatable) keeps the impact categories whose method family contains the text, --db (repeatable) the datasets of
one database. 'reference' rebuilds the snapshot of the libraries shipped with Cyclia that the test suite checks;
run it only when a difference has been explained and is intended, and say why in the CHANGELOG.

Exit code: 0 when the comparison passes, 1 when values differ, 2 on an error. A snapshot of ecoinvent contains
ecoinvent results: keep it with your licence, do not publish it.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, ENGINE)

import calc  # noqa: E402
import regression  # noqa: E402
from store import Workspace  # noqa: E402

REFERENCE = os.path.join(ENGINE, "tests", "data", "reference_regression.json.gz")


def _progress(p, msg):
    print(f"  {p:5.1f} %  {msg}", file=sys.stderr)


def _record(args):
    ws = Workspace(args.data)
    if not ws.exists(args.project):
        ws.close_all()
        raise SystemExit(f"Project '{args.project}' not found in {args.data}.")
    st = ws.open(args.project)
    try:
        mids = None
        if args.family:
            fams = {f.lower() for f in args.family}
            mids = [r["id"] for r in st.q("SELECT id, family FROM methods ORDER BY family, category, indicator")
                    if any(f in (r["family"] or "").lower() for f in fams)]
            if not mids:
                raise SystemExit("No impact category of the chosen method families in this project.")
        dbs = None
        if args.db:
            names = {d.lower() for d in args.db}
            dbs = [d["id"] for d in st.databases() if d["name"].lower() in names]
            if not dbs:
                raise SystemExit("None of the chosen databases is in this project.")
        return regression.snapshot(st, mids, dbs, label=args.label or args.project, progress=_progress)
    finally:
        ws.close_all()


def _reference():
    d = tempfile.mkdtemp()
    try:
        ws = Workspace(d)
        st = ws.create("Reference")
        regression.build_reference(st)
        snap = regression.snapshot(st, label="Cyclia reference libraries")
        ws.close_all()
        calc.invalidate()
        return snap
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("record", "check"):
        p = sub.add_parser(name)
        p.add_argument("--data", required=True)
        p.add_argument("--project", required=True)
        p.add_argument("--family", action="append")
        p.add_argument("--db", action="append")
        p.add_argument("--label")
        if name == "record":
            p.add_argument("--out", required=True)
        else:
            p.add_argument("--ref", required=True)
    p = sub.add_parser("compare")
    p.add_argument("reference")
    p.add_argument("new")
    p = sub.add_parser("reference")
    p.add_argument("--out", default=REFERENCE)
    for p in sub.choices.values():
        if p.prog.split()[-1] in ("compare", "check"):
            p.add_argument("--rtol", type=float, default=1e-9)
            p.add_argument("--atol-share", type=float, default=1e-12)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "record":
            regression.save(_record(args), args.out)
            print(f"Snapshot written: {args.out}")
            return 0
        if args.cmd == "reference":
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            regression.save(_reference(), args.out)
            print(f"Reference snapshot written: {args.out}")
            return 0
        if args.cmd == "compare":
            ref, new = regression.load(args.reference), regression.load(args.new)
        else:
            ref, new = regression.load(args.ref), _record(args)
        rep = regression.compare(ref, new, args.rtol, args.atol_share)
        print(regression.report_text(rep))
        return 0 if rep["passed"] else 1
    except (ValueError, OSError, calc.LCAError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
