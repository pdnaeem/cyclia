"""EPD programme template profiles (Cyclia 1.3.5).

A profile describes how an EPD of one programme is laid out and what it must contain: the order of sections,
the fields of the general information, the mandatory statements, the indicator tables, translations and the
programme-specific checks. The Word EPD is rendered from the profile.

The profiles for the International EPD System, IBU and INIES are drafts modelled on EPDs published by those
programmes (sources in each profile). They are NOT approved by the programme operators: check them against the
current General Programme Instructions and PCR of your programme before submitting, and edit the statements in
the EPD form where your programme requires other wording. Custom profiles (JSON with the same keys) can be loaded.
"""
import copy
import json
import os
import re

GENERIC = {
    "id": "generic", "name": "Cyclia generic EPD (ISO 14025:2026, EN 15804+A2)", "language": "en",
    "status": "Cyclia's own layout covering ISO 14025:2026 and EN 15804+A2. Programme-neutral.",
    "based_on": [], "validity_years": None,
    "fields": [],
    "statements": [],
    "required_indicators": [],
    "grouped_tables": False,
    "sections": ["title", "readiness", "general", "programme", "description", "modules", "indicators", "uncertainty",
                 "resource_note", "lca_info", "statements", "checklist", "references"],
}

INTERNATIONAL_EPD = {
    "id": "international-epd-system", "name": "The International EPD System (EPD International, GPI 5)", "language": "en",
    "status": "Draft profile modelled on EPDs published under the General Programme Instructions 5 of EPD International. "
              "Not approved by EPD International. Check against the current GPI and the PCR (e.g. PCR 2019:14) before "
              "submitting.",
    "based_on": ["https://environdec.com/news/gpi_500",
                 "https://mannigroup.b-cdn.net/2026/06/EPD-portoni-sezionali-EN-light.pdf"],
    "validity_years": 5,
    "fixed": {"Programme": "The International EPD System", "Programme operator": "EPD International AB"},
    "fields": [
        {"key": "registration", "label": "EPD registration number", "required": True},
        {"key": "pcr_core", "label": "Core PCR", "required": True, "default": "EN 15804:2012+A2:2019/AC:2021"},
        {"key": "pcr_product", "label": "Product PCR (name and number)", "required": True, "default": "PCR 2019:14 Construction products"},
        {"key": "pcr_version", "label": "Product PCR version", "required": True},
        {"key": "epd_type", "label": "EPD type (GPI 5)", "required": True, "type": "select",
         "options": ["Single product EPD", "Multi-product EPD of a company", "Sector EPD", "EPD published by a trader",
                     "Single footprint EPD", "Machine-readable EPD", "EPD for a product recently placed on the market",
                     "EPD for a product not yet on the market"]},
        {"key": "un_cpc", "label": "UN CPC code", "required": True},
        {"key": "lca_accountability", "label": "LCA accountability (who did the LCA)", "required": True},
        {"key": "verifier", "label": "Third-party verifier (name, organisation)", "required": True},
        {"key": "accreditation", "label": "Accreditation of the verifier (body and number)", "required": False},
        {"key": "follow_up", "label": "Procedure for follow-up of data during EPD validity", "type": "select",
         "options": ["Yes", "No"], "required": True},
        {"key": "geographical_scope", "label": "Geographical scope", "required": True},
        {"key": "time_representativeness", "label": "Time representativeness of the data", "required": True},
        {"key": "variation", "label": "Variation between products or sites (multi-product or multi-site EPDs)", "required": False},
        {"key": "content_declaration", "label": "Content declaration (product and packaging materials)", "type": "textarea",
         "required": True},
    ],
    "statements": [
        "The EPD owner has the sole ownership, liability, and responsibility for the EPD.",
        "EPDs within the same product category but registered in different EPD programmes, or not compliant with EN 15804, "
        "may not be comparable. For two EPDs to be comparable, they must be based on the same PCR (including the same "
        "version number) or on fully aligned PCRs; cover products with identical functions, technical performances and "
        "use; have equivalent system boundaries and descriptions of data; apply equivalent data quality requirements, "
        "methods of data collection and allocation methods; apply identical cut-off rules and impact assessment methods "
        "(including the same version of characterisation factors); have equivalent content declarations; and be valid "
        "at the time of comparison.",
        "An EPD should provide current information and may be updated if conditions change.",
    ],
    "required_indicators": ["GWP-GHG"],
    "grouped_tables": True,
    "sections": ["title", "readiness", "general", "description", "content", "modules", "indicators", "uncertainty",
                 "lca_info", "statements", "checklist", "references"],
}

IBU = {
    "id": "ibu", "name": "IBU, Institut Bauen und Umwelt e.V. (Germany)", "language": "en",
    "status": "Draft profile modelled on EPDs published by IBU. Not approved by IBU. Check against the current IBU "
              "General Instructions and PCR Part A and B before submitting.",
    "based_on": ["https://ibu-epd.com/wp-content/uploads/2017/12/Textile-covered-acoustic-frame-systems.pdf",
                 "https://ibu-epd.com/wp-content/uploads/2026/08/260702_ENG-PCR-Part-AA2_v.1.5.pdf"],
    "validity_years": 5,
    "fixed": {"Programme holder": "IBU - Institut Bauen und Umwelt e.V.", "Core PCR": "EN 15804+A2"},
    "fields": [
        {"key": "declaration_number", "label": "Declaration number", "required": True},
        {"key": "owner", "label": "Owner of the declaration (name and address)", "required": True},
        {"key": "pcr", "label": "Product category rules (PCR name, date)", "required": True},
        {"key": "scope", "label": "Scope (products, plants, representativeness)", "type": "textarea", "required": True},
        {"key": "verification_kind", "label": "Independent verification according to ISO 14025", "type": "select",
         "options": ["internally", "externally"], "required": True},
        {"key": "verifier", "label": "Verifier", "required": True},
        {"key": "conversion_kg", "label": "Conversion factor of the declared unit to 1 kg", "required": True},
        {"key": "application", "label": "2.2 Application", "type": "textarea", "required": True},
        {"key": "technical_data", "label": "2.3 Technical data", "type": "textarea", "required": True},
        {"key": "base_materials", "label": "2.5 Base materials / ancillary materials", "type": "textarea", "required": True},
        {"key": "svhc", "label": "Substances of the candidate list above 0.1 % by mass (yes/no, list)", "required": True},
        {"key": "cmr", "label": "Other CMR substances of categories 1A or 1B above 0.1 % by mass (yes/no)", "required": True},
        {"key": "biocides", "label": "Biocide products added or treated (Regulation (EU) No 528/2012) (yes/no)", "required": True},
        {"key": "manufacture", "label": "2.6 Manufacture", "type": "textarea", "required": True},
        {"key": "installation", "label": "2.8 Product processing / installation", "type": "textarea", "required": False},
        {"key": "packaging", "label": "2.9 Packaging", "type": "textarea", "required": False},
        {"key": "use", "label": "2.10 to 2.11 Condition and environment during use", "type": "textarea", "required": False},
        {"key": "reuse_disposal", "label": "2.14 to 2.15 Re-use phase and disposal", "type": "textarea", "required": True},
        {"key": "interpretation", "label": "6. LCA: Interpretation", "type": "textarea", "required": True},
        {"key": "evidence", "label": "7. Requisite evidence", "type": "textarea", "required": False},
    ],
    "statements": [
        "The owner of the declaration shall be liable for the underlying information and evidence; IBU shall not be "
        "liable with respect to manufacturer information, life cycle assessment data and evidences.",
        "The CEN standard EN 15804 serves as the core PCR.",
        "Any type of reproduction, including excerpts thereof, is only permitted with the publisher's approval.",
    ],
    "required_indicators": [],
    "grouped_tables": True,
    "sections": ["title", "readiness", "general", "ibu_product", "lca_rules", "modules", "indicators", "uncertainty",
                 "ibu_interpretation", "lca_info", "statements", "checklist", "references"],
}

INIES = {
    "id": "inies-fdes", "name": "INIES FDES (France, NF EN 15804+A2 and NF EN 15804/CN)", "language": "fr",
    "status": "Profil provisoire construit d'après des FDES publiées dans INIES. Non approuvé par le programme "
              "FDES-INIES. A vérifier avec le programme de vérification FDES-INIES et la NF EN 15804+A2/CN en vigueur "
              "avant toute soumission. Une FDES est déclarée dans INIES selon le format du programme.",
    "based_on": ["https://forbo.blob.core.windows.net/forbodocuments/578270/EVEA%20pour%20FORBO_FDES%20Tapis_EN%2015804%20A2_vF.pdf"],
    "validity_years": 5,
    "fixed": {"Programme": "FDES-INIES", "Norme de référence": "NF EN 15804+A2 et NF EN 15804+A2/CN"},
    "fields": [
        {"key": "inies_number", "label": "Numéro d'enregistrement INIES", "required": True},
        {"key": "fdes_version", "label": "Version de la FDES", "required": True},
        {"key": "author", "label": "Auteur de l'ACV", "required": True},
        {"key": "declarant", "label": "Déclarant (nom et adresse)", "required": True},
        {"key": "fdes_type", "label": "Type de FDES", "type": "select", "required": True,
         "options": ["individuelle", "individuelle de gamme", "collective", "collective de gamme"]},
        {"key": "functional_unit", "label": "Unité fonctionnelle (texte complet)", "type": "textarea", "required": True},
        {"key": "dvr", "label": "Durée de vie de référence (DVR)", "required": True},
        {"key": "verifier", "label": "Vérificateur (nom, organisme)", "required": True},
        {"key": "verification_date", "label": "Date de vérification", "required": True},
        {"key": "indoor_air", "label": "Qualité de l'air intérieur (émissions de COV, classe)", "type": "textarea", "required": True},
        {"key": "soil_water", "label": "Relargage dans le sol et l'eau", "type": "textarea", "required": True},
        {"key": "comfort", "label": "Contribution au confort (hygrothermique, acoustique, visuel, olfactif)", "type": "textarea",
         "required": False},
    ],
    "statements": [
        "Les informations contenues dans cette déclaration sont fournies sous la responsabilité du déclarant. Toute "
        "exploitation, totale ou partielle, des informations fournies dans ce document doit au minimum être accompagnée "
        "de la référence complète de la déclaration et du nom de son producteur.",
        "Les résultats présentés sont fondés seulement sur des faits, circonstances et hypothèses retenus pour "
        "l'analyse du cycle de vie.",
        "Les FDES ne sont pas des outils permettant de comparer des produits et des services de construction en dehors "
        "d'une évaluation à l'échelle du bâtiment.",
        "Lorsque le résultat de calcul de l'inventaire est nul, alors la valeur zéro est affichée.",
    ],
    "required_indicators": ["PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP"],
    "grouped_tables": True,
    "zero_shown": True,
    "sections": ["title", "readiness", "general", "description", "modules", "indicators", "uncertainty", "lca_info",
                 "fdes_health", "statements", "checklist", "references"],
}

BUILTIN = {p["id"]: p for p in (GENERIC, INTERNATIONAL_EPD, IBU, INIES)}

LABELS_FR = {
    "GWP-total": "Changement climatique - total", "GWP-fossil": "Changement climatique - combustibles fossiles",
    "GWP-biogenic": "Changement climatique - biogénique",
    "GWP-luluc": "Changement climatique - occupation des sols et transformation de l'occupation des sols",
    "ODP": "Appauvrissement de la couche d'ozone", "AP": "Acidification",
    "EP-freshwater": "Eutrophisation aquatique eaux douces", "EP-marine": "Eutrophisation aquatique marine",
    "EP-terrestrial": "Eutrophisation terrestre", "POCP": "Formation d'ozone photochimique",
    "ADP-minerals&metals": "Épuisement des ressources abiotiques - minéraux et métaux",
    "ADP-fossil": "Épuisement des ressources abiotiques - combustibles fossiles", "WDP": "Besoin en eau",
    "PM": "Émissions de particules fines", "IRP": "Rayonnements ionisants, santé humaine",
    "ETP-fw": "Écotoxicité (eaux douces)", "HTP-c": "Toxicité humaine, effets cancérigènes",
    "HTP-nc": "Toxicité humaine, effets non cancérigènes", "SQP": "Impacts liés à l'occupation des sols / qualité du sol",
    "PERE": "Utilisation de l'énergie primaire renouvelable, à l'exclusion des ressources d'énergie primaire "
            "renouvelables utilisées comme matières premières",
    "PERM": "Utilisation des ressources d'énergie primaire renouvelables utilisées en tant que matières premières",
    "PERT": "Utilisation totale des ressources d'énergie primaire renouvelables",
    "PENRE": "Utilisation de l'énergie primaire non renouvelable, à l'exclusion des ressources d'énergie primaire non "
             "renouvelables utilisées comme matières premières",
    "PENRM": "Utilisation des ressources d'énergie primaire non renouvelables utilisées en tant que matières premières",
    "PENRT": "Utilisation totale des ressources d'énergie primaire non renouvelables",
    "SM": "Utilisation de matière secondaire", "RSF": "Utilisation de combustibles secondaires renouvelables",
    "NRSF": "Utilisation de combustibles secondaires non renouvelables", "FW": "Utilisation nette d'eau douce",
    "HWD": "Déchets dangereux éliminés", "NHWD": "Déchets non dangereux éliminés", "RWD": "Déchets radioactifs éliminés",
    "CRU": "Composants destinés à la réutilisation", "MFR": "Matériaux destinés au recyclage",
    "MER": "Matériaux destinés à la récupération d'énergie", "EEE": "Énergie fournie à l'extérieur - électricité",
    "EET": "Énergie fournie à l'extérieur - thermique",
}

UI_FR = {"General information": "Informations générales", "Indicator": "Indicateur", "Unit": "Unité",
         "Core environmental impact indicators": "Indicateurs d'impacts environnementaux",
         "Additional environmental impact indicators": "Indicateurs d'impacts environnementaux additionnels",
         "Resource use": "Utilisation des ressources", "Waste categories": "Catégories de déchets",
         "Output flows": "Flux sortants", "Other indicators": "Autres indicateurs",
         "System boundary: modules declared": "Étapes du cycle de vie déclarées",
         "Product description": "Description de l'unité fonctionnelle et du produit",
         "LCA information": "Informations pour le calcul de l'analyse de cycle de vie",
         "Statements": "Mentions obligatoires", "Verification support checklist": "Liste de contrôle pour la vérification",
         "References": "Bibliographie", "Item": "Rubrique", "Content": "Contenu",
         "Health and comfort": "Contribution du produit à la qualité de vie à l'intérieur des bâtiments",
         "Environmental Product Declaration (EPD)": "Fiche de Déclaration Environnementale et Sanitaire (FDES)"}

# EN 15804+A2 Table 3 additional indicators, and the GWP-GHG indicator of EPD International
def _sub(t):
    """EF 3.1 splits toxicity into ', inorganics' and ', organics' sub-categories: those are not the EPD indicator."""
    return "inorganics" in t or re.search(r"\borganics\b", t) is not None


def _cancer(t):
    return ("cancer" in t or "carcinogenic" in t) and not _noncancer(t)


def _noncancer(t):
    return any(w in t for w in ("non-cancer", "non cancer", "non-carcinogenic", "non carcinogenic", "noncarcinogenic"))


ADDITIONAL = [
    ("PM", lambda t: "particulate" in t or "respiratory inorganics" in t),
    ("IRP", lambda t: "ionising radiation" in t or "ionizing radiation" in t),
    ("ETP-fw", lambda t: "ecotoxicity" in t and "fresh" in t and not _sub(t)),
    ("HTP-c", lambda t: "human toxicity" in t and _cancer(t) and not _sub(t)),
    ("HTP-nc", lambda t: "human toxicity" in t and _noncancer(t) and not _sub(t)),
    ("SQP", lambda t: ("land use" in t or "soil quality" in t) and "climate" not in t),
    ("GWP-GHG", lambda t: "gwp-ghg" in t or ("climate change" in t and ("ghg" in t or "excluding biogenic" in t))),
]
# expected unit tokens of the additional indicators (EN 15804+A2 Table 4 / Annex C)
ADDITIONAL_UNITS = {"PM": ("disease incidence",), "IRP": ("u235", "u-235"), "ETP-fw": ("ctue",), "HTP-c": ("ctuh",),
                    "HTP-nc": ("ctuh",), "SQP": ("dimensionless", "pt"), "GWP-GHG": ("co2",)}


def match_additional(results):
    found = {}
    for k, r in enumerate(results):
        t = f"{r['category']} {r['indicator']}".lower()
        raw = f"{r['category']} {r['indicator']}"
        for a, test in ADDITIONAL:
            if a in found:
                continue
            if re.search(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z-])", raw) or test(t):
                found[a] = k
                break
    return found


def _custom_dir():
    base = os.environ.get("CYCLIA_DATA") or os.path.join(os.path.expanduser("~"), ".cyclia")
    return os.path.join(base, "epd_profiles")


def validate_profile(p):
    for k in ("id", "name", "sections", "fields", "statements"):
        if k not in p:
            raise ValueError(f"The profile has no '{k}'.")
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,60}$", str(p["id"])):
        raise ValueError("The profile id may only contain lower-case letters, digits and hyphens.")
    known = set(GENERIC["sections"]) | set(INTERNATIONAL_EPD["sections"]) | set(IBU["sections"]) | set(INIES["sections"])
    bad = [s for s in p["sections"] if s not in known]
    if bad:
        raise ValueError(f"Unknown sections in the profile: {', '.join(bad)}. Known: {', '.join(sorted(known))}.")
    for f in p["fields"]:
        if not f.get("key") or not f.get("label"):
            raise ValueError("Every field needs a key and a label.")
    return p


def all_profiles(extra_dir=None):
    out = {k: copy.deepcopy(v) for k, v in BUILTIN.items()}
    d = extra_dir or _custom_dir()
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as fh:
                        p = validate_profile(json.load(fh))
                    if p["id"] not in BUILTIN:
                        p["custom"] = True
                        out[p["id"]] = p
                except (ValueError, OSError, json.JSONDecodeError):
                    continue
    return out


def get(profile_id, extra_dir=None):
    return all_profiles(extra_dir).get(profile_id or "generic") or copy.deepcopy(GENERIC)


def save_custom(profile, extra_dir=None):
    p = validate_profile(dict(profile))
    if p["id"] in BUILTIN:
        raise ValueError("Choose another id: built-in profiles cannot be replaced (copy one and change its id).")
    d = extra_dir or _custom_dir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, p["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(p, fh, ensure_ascii=False, indent=2)
    return p["id"]
