"""Download ecoinvent with the user's own licence, using the open-source `ecoinvent_interface` package
(https://pypi.org/project/ecoinvent-interface/).

Credentials are only sent to ecoinvent's own servers and are never written to disk by Cyclia.
Downloads are cached by ecoinvent_interface in the user's data folder, so a second install is fast.
"""
import glob
import os


def _client(username, password):
    try:
        from ecoinvent_interface import EcoinventRelease, Settings
    except ImportError:
        raise ValueError("The ecoinvent download is not available in this installation. Download the release from "
                         "ecoquery.ecoinvent.org and use 'ecoinvent folder you already downloaded'.")
    username = (username or "").strip()
    if not username or not password:
        raise ValueError("Enter your ecoinvent username and password.")
    rel = EcoinventRelease(Settings(username=username, password=password))
    try:
        versions = rel.list_versions()
    except Exception as e:
        raise ValueError(_explain(e, username))
    return rel, versions


FOLDER_HINT = ("You can always download the release yourself at ecoquery.ecoinvent.org (Files) and use "
               "'ecoinvent folder you already downloaded'.")


def _explain(e, username):
    """Turn the ecoinvent login error into advice a user can act on."""
    resp = getattr(e, "response", None)
    status = getattr(resp, "status_code", None)
    code, detail = "", ""
    try:
        body = resp.json()
        code, detail = body.get("error", ""), body.get("error_description", "")
    except Exception:
        pass
    if status in (400, 401) and code in ("invalid_grant", ""):
        tips = ["ecoinvent did not accept this username and password."]
        if "@" in username:
            tips.append("You typed an e-mail address. Try your ecoinvent username instead "
                        "(shown at ecoinvent.org > My account).")
        tips.append("If you sign in to ecoinvent through your university, Google or Microsoft, your account has "
                    "no ecoinvent password yet: use 'Forgot password' on the ecoinvent login page to set one.")
        tips.append("Test the same login at ecoquery.ecoinvent.org; if it works there, it works here.")
        tips.append(FOLDER_HINT)
        return " ".join(tips) + (f" (ecoinvent: {detail})" if detail else "")
    if status in (400, 401):
        return (f"ecoinvent refused the connection ({code or status}: {detail or 'no detail'}). ecoinvent may have "
                f"changed its login service; if the problem remains, contact support@niellosoft.com. {FOLDER_HINT}")
    if status == 403:
        return ("Login worked, but this account has no ecoinvent licence attached. Ask your university's "
                "ecoinvent administrator to add your account to the licence. " + FOLDER_HINT)
    if resp is None:
        return f"Could not reach ecoinvent. Check the internet connection or proxy. ({e}) {FOLDER_HINT}"
    return f"ecoinvent login failed ({status}). ({e}) {FOLDER_HINT}"


def list_releases(username, password):
    rel, versions = _client(username, password)
    out = []
    for v in versions:
        try:
            models = list(rel.list_system_models(v))
        except Exception:
            models = []
        if models:
            out.append({"version": v, "system_models": models})
    return out


def _extract_xlsx(path):
    path = str(path)
    if os.path.isdir(path):
        found = sorted(glob.glob(os.path.join(path, "**", "*.xlsx"), recursive=True))
        lcia = [f for f in found if "lcia" in os.path.basename(f).lower()] or found
        return lcia[0] if lcia else None
    if path.lower().endswith(".xlsx"):
        return path
    if path.lower().endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            return None
        out = path[:-3]
        os.makedirs(out, exist_ok=True)
        with py7zr.SevenZipFile(path) as z:
            z.extractall(out)
        return _extract_xlsx(out)
    return None


def download(username, password, version, system_model, progress=lambda *a: None):
    from ecoinvent_interface import ReleaseType
    rel, _ = _client(username, password)
    progress(3, f"Downloading ecoinvent {version} {system_model}; this can take several minutes")
    path = rel.get_release(version=version, system_model=system_model, release_type=ReleaseType.ecospold)
    progress(40, "Downloading the LCIA implementation file")
    lcia = None
    try:
        extras = rel.list_extra_files(version)
        names = list(extras.keys()) if isinstance(extras, dict) else list(extras)
        name = next((n for n in names if "lcia" in n.lower() and "implementation" in n.lower()), None) or \
            next((n for n in names if "lcia" in n.lower()), None)
        if name:
            lcia = _extract_xlsx(rel.get_extra(version=version, filename=name))
    except Exception:
        lcia = None
    return str(path), lcia


def find_xlsx(path, words=("lcia",)):
    """The results workbook inside a downloaded (and extracted) release folder, or the file itself."""
    path = str(path)
    if os.path.isfile(path) and path.lower().endswith(".xlsx"):
        return path
    if path.lower().endswith(".7z") and os.path.isfile(path):
        x = _extract_xlsx(path)
        return x
    found = sorted(glob.glob(os.path.join(path, "**", "*.xlsx"), recursive=True), key=os.path.getsize, reverse=True)
    pref = [f for f in found if all(w in os.path.basename(f).lower() for w in words)]
    return (pref or found or [None])[0]


def download_cumulative_lcia(username, password, version, system_model, progress=lambda *a: None):
    """ecoinvent's own LCIA results for every dataset of a release (Excel), used to validate Cyclia."""
    from ecoinvent_interface import ReleaseType
    rel, _ = _client(username, password)
    progress(2, f"Downloading ecoinvent's LCIA results for {version} {system_model}")
    try:
        path = rel.get_release(version=version, system_model=system_model, release_type=ReleaseType.cumulative_lcia)
    except Exception as e:
        raise ValueError(f"ecoinvent did not provide the cumulative LCIA results for {version} {system_model} ({e}).")
    x = find_xlsx(path)
    if not x:
        raise ValueError("The downloaded LCIA results contain no Excel file.")
    return x


def download_cumulative_lci(username, password, version, system_model, progress=lambda *a: None):
    """ecoinvent's cumulative LCI (every elementary flow of every dataset, Excel), used to tell an inventory
    difference from a factor difference. A large download; it is cached by ecoinvent_interface."""
    from ecoinvent_interface import ReleaseType
    rel, _ = _client(username, password)
    progress(2, f"Downloading ecoinvent's cumulative LCI for {version} {system_model} (a large file)")
    try:
        path = rel.get_release(version=version, system_model=system_model, release_type=ReleaseType.cumulative_lci)
    except Exception as e:
        raise ValueError(f"ecoinvent did not provide the cumulative LCI for {version} {system_model} ({e}).")
    x = find_xlsx(path, ("lci",))
    if not x:
        raise ValueError("The downloaded cumulative LCI contains no Excel file.")
    return x
