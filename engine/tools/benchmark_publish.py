"""Benchmark reports for publication from a benchmark workbook saved by Cyclia (Cyclia 1.9.1).

    python engine/tools/benchmark_publish.py "Cyclia benchmark against ecoinvent.xlsx" docs/benchmarks

Writes one Markdown report per method family group and a README with the status table. The reports hold deviation
statistics only; the workbook itself contains ecoinvent results and stays with your licence.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        files = benchmark.publication_from_workbook(argv[0])
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    os.makedirs(argv[1], exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(argv[1], name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print(f"{len(files)} files written to {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
