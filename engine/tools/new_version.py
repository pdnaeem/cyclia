"""Prepare a new Cyclia release in one step.

    python engine/tools/new_version.py 1.2.1

Sets the version in app/package.json, the engine and the README citation, refreshes the credits
(CITATION.cff, installer, app), adds a section to docs/CHANGELOG.md and creates
docs/releases/RELEASE_NOTES_v<version>.md for you to fill in. Then commit, push, and create the tag v<version>.
"""
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def edit(path, pattern, repl, count=1):
    p = os.path.join(ROOT, path)
    with open(p, encoding="utf-8") as f:
        s = f.read()
    new, n = re.subn(pattern, repl, s, count=count, flags=re.M)
    if not n:
        print(f"  warning: version not found in {path}")
    with open(p, "w", encoding="utf-8") as f:
        f.write(new)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit("Usage: python engine/tools/new_version.py 1.2.1")
    v = sys.argv[1]
    pkg_path = os.path.join(ROOT, "app", "package.json")
    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)
    old = pkg["version"]
    if tuple(map(int, v.split("."))) <= tuple(map(int, old.split("."))):
        sys.exit(f"The new version must be higher than the current one ({old}).")
    pkg["version"] = v
    with open(pkg_path, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2, ensure_ascii=False)
        f.write("\n")

    edit("engine/server.py", r'^VERSION = "[\d.]+"', f'VERSION = "{v}"')
    edit("README.md", r"\(version [\d.]+\)", f"(version {v})")
    edit("docs/ROADMAP.md", r"^Version: [\d.]+\.", f"Version: {v}.")
    edit("docs/ROADMAP.md", r"^\| Feature \| Cyclia [\d.]+ \|", f"| Feature | Cyclia {v} |")
    edit("docs/index.html", r'"softwareVersion": "[\d.]+"', f'"softwareVersion": "{v}"')
    edit("docs/index.html", r"\(version [\d.]+\)", f"(version {v})")
    edit("docs/FEATURE_STATUS.md", r"Status of Cyclia [\d.]+,", f"Status of Cyclia {v},")

    today = datetime.date.today().isoformat()
    edit("docs/CHANGELOG.md", r"# Changelog\n", f"# Changelog\n\n## {v} ({today})\n\n- \n")

    notes = os.path.join(ROOT, "docs", "releases", f"RELEASE_NOTES_v{v}.md")
    if not os.path.exists(notes):
        with open(notes, "w", encoding="utf-8") as f:
            f.write(f"""# Cyclia {v}

## What is new

-

## Fixed

-

## Download

Windows: `Cyclia-Setup-{v}.exe` · macOS: `.dmg` · Linux: `.AppImage` or `.deb`.
Installed copies of Cyclia update themselves.

## Cite

Rehman, N. U. (2026). *Cyclia: open-source life cycle assessment software for researchers* (version {v})
[Computer software]. https://doi.org/{json.load(open(os.path.join(ROOT, 'credits.json'), encoding='utf-8'))['doi']}
""")

    subprocess.run([sys.executable, os.path.join(ROOT, "engine", "tools", "apply_credits.py")], check=False)
    print(f"\nCyclia {old} -> {v}. Next:")
    print(f"  1. Write what changed in docs/CHANGELOG.md and docs/releases/RELEASE_NOTES_v{v}.md")
    print(f"  2. GitHub Desktop: commit 'Cyclia {v}', Push origin")
    print(f"  3. History tab: right-click that commit > Create Tag > v{v} > Push origin")


if __name__ == "__main__":
    main()
