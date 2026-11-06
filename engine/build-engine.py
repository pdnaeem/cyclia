"""Build the standalone Cyclia engine with PyInstaller (Windows, macOS, Linux).

    python engine/build-engine.py

Runs the test suite first and stops if any test fails. Output: engine/dist/cyclia-engine/
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*cmd):
    print(">", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=HERE)


run(sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller>=6.6")
# Optional: ecoinvent login connector. The app works without it (folder import still available).
try:
    run(sys.executable, "-m", "pip", "install", "ecoinvent_interface")
    EI = ["--collect-submodules", "ecoinvent_interface"]
except subprocess.CalledProcessError:
    print("WARNING: ecoinvent_interface could not be installed; the login connector will be disabled.")
    EI = []
# Optional: Brightway's calculation library for the in-app comparison with Brightway (Toolbox > Validation).
try:
    run(sys.executable, "-m", "pip", "install", "bw2calc>=2.0", "bw_processing>=1.0")
    BW = ["--collect-submodules", "bw2calc", "--collect-submodules", "bw_processing", "--collect-submodules", "matrix_utils",
          "--collect-submodules", "stats_arrays", "--collect-submodules", "morefs", "--collect-data", "bw_processing",
          "--collect-data", "bw2calc", "--copy-metadata", "bw2calc", "--copy-metadata", "bw_processing"]
except subprocess.CalledProcessError:
    print("WARNING: bw2calc could not be installed; the comparison with Brightway will be disabled.")
    BW = []
run(sys.executable, "-m", "unittest", "discover", "-s", "tests")
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "cyclia-engine", "--paths", ".",
    "--hidden-import", "importers.tutorial", "--hidden-import", "importers.ecospold2",
    "--hidden-import", "importers.jsonld", "--hidden-import", "importers.lcia",
    "--hidden-import", "importers.ecoinvent_login", "--hidden-import", "importers.other_formats",
    "--hidden-import", "importers.demo", "--hidden-import", "science", "--hidden-import", "trust",
    "--hidden-import", "productivity", "--hidden-import", "standards", "--hidden-import", "interop",
    "--hidden-import", "teaching", "--hidden-import", "credits", "--hidden-import", "analysis", "--hidden-import", "hier", "--hidden-import", "crosscheck", "--hidden-import", "factormatch", "--hidden-import", "epd_profiles", "--hidden-import", "regional", "--hidden-import", "slca", "--hidden-import", "mfa", "--hidden-import", "ilcd_epd", "--hidden-import", "staging", "--hidden-import", "compare_kit", "--hidden-import", "brightway_check", "--hidden-import", "lci_check", "--hidden-import", "custom_data", "--hidden-import", "matplotlib.backends.backend_svg", "--hidden-import", "scipy.optimize", "--hidden-import", "scipy.stats.qmc",
    "--collect-submodules", "pdfplumber", "--collect-submodules", "pypdf",
    "--collect-data", "docx", *EI, *BW,
    # data read at run time: ILCD+EPD schemas (validation of exports) and the comparison kit scripts
    "--add-data", os.path.join("schemas", "ilcd_epd") + os.pathsep + os.path.join("schemas", "ilcd_epd"),
    "--add-data", os.path.join("tools", "compare_kit") + os.pathsep + os.path.join("tools", "compare_kit"),
    "--exclude-module", "tkinter", "--exclude-module", "matplotlib.tests", "--exclude-module", "numpy.tests",
    "server.py")
exe = os.path.join(HERE, "dist", "cyclia-engine", "cyclia-engine" + (".exe" if os.name == "nt" else ""))
if not os.path.isfile(exe):
    sys.exit("Build failed: engine executable not found")
base = os.path.join(HERE, "dist", "cyclia-engine")
for rel in (os.path.join("schemas", "ilcd_epd", "_cyclia_validate.xsd"), os.path.join("tools", "compare_kit", "compare.py")):
    if not any(os.path.isfile(os.path.join(base, sub, rel)) for sub in ("_internal", "")):
        sys.exit(f"Build failed: {rel} is missing from the engine bundle")
# smoke test: the frozen engine must start and print its ready line
import threading
p = subprocess.Popen([exe, "--port", "0", "--data", os.path.join(HERE, "build", "smoke-data"), "--token", "x"],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
got = []
t = threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True)
t.start()
t.join(90)
if not got or "CYCLIA_READY" not in got[0]:
    p.kill()
    err = p.stderr.read()[-2000:] if p.stderr else ""
    sys.exit("Build failed: the frozen engine did not start.\n" + err)
# the Brightway comparison must work in the frozen engine when bw2calc was bundled
if BW:
    import json
    import urllib.request
    port = got[0].split("port=")[1].split()[0]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/brightway/status", headers={"X-Token": "x"})
    try:
        status = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except Exception as e:
        status = {"available": False, "error": str(e)}
    finally:
        p.kill()
    if status.get("available"):
        print("Brightway in the frozen engine:", status)
    else:   # the app still works; Toolbox > Validation then offers the comparison kit instead
        print("WARNING: bw2calc was installed but is not available in the frozen engine; the in-app comparison with "
              "Brightway will be disabled in this build.")
else:
    p.kill()
print("Engine built and started correctly:", exe)
