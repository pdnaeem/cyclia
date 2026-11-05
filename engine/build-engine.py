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
run(sys.executable, "-m", "unittest", "discover", "-s", "tests")
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "cyclia-engine", "--paths", ".",
    "--hidden-import", "importers.tutorial", "--hidden-import", "importers.ecospold2",
    "--hidden-import", "importers.jsonld", "--hidden-import", "importers.lcia",
    "--hidden-import", "importers.ecoinvent_login", "--hidden-import", "importers.other_formats",
    "--hidden-import", "importers.demo", "--hidden-import", "science", "--hidden-import", "trust",
    "--hidden-import", "productivity", "--hidden-import", "standards", "--hidden-import", "interop",
    "--hidden-import", "teaching", "--hidden-import", "credits", "--hidden-import", "analysis", "--hidden-import", "hier", "--hidden-import", "matplotlib.backends.backend_svg", "--hidden-import", "scipy.optimize", "--hidden-import", "scipy.stats.qmc",
    "--collect-submodules", "pdfplumber", "--collect-submodules", "pypdf",
    "--collect-data", "docx", *EI,
    "--exclude-module", "tkinter", "--exclude-module", "matplotlib.tests", "--exclude-module", "numpy.tests",
    "server.py")
exe = os.path.join(HERE, "dist", "cyclia-engine", "cyclia-engine" + (".exe" if os.name == "nt" else ""))
if not os.path.isfile(exe):
    sys.exit("Build failed: engine executable not found")
# smoke test: the frozen engine must start and print its ready line
import threading
p = subprocess.Popen([exe, "--port", "0", "--data", os.path.join(HERE, "build", "smoke-data"), "--token", "x"],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
got = []
t = threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True)
t.start()
t.join(90)
p.kill()
if not got or "CYCLIA_READY" not in got[0]:
    err = p.stderr.read()[-2000:] if p.stderr else ""
    sys.exit("Build failed: the frozen engine did not start.\n" + err)
print("Engine built and started correctly:", exe)
