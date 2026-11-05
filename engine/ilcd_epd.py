"""ILCD+EPD export (Cyclia 1.3.7): the EPD of a model as a machine-readable ILCD+EPD 1.2 dataset.

Structure, namespaces and identifiers follow the InData ILCD+EPD data format
(https://github.com/InDataWG/ILCD-EPD-Data-Format, Apache License 2.0):

- one process data set (typeOfDataSet "EPD", epd:subType) with the declared unit as reference flow;
- resource, waste and output indicators (EN 15804+A2 Tables 4 to 6) as exchanges of the authoritative indicator
  flows, impact indicators (Table 3 and additional indicators) as LCIA results of the authoritative EN 15804+A2
  (EF 3.1) LCIA method data sets, with one epd:amount per declared module;
- a product flow data set for the declared unit.

Every exported process and flow data set is validated against the official XSD schemas shipped in
engine/schemas/ilcd_epd before the zip is written; the export refuses invalid XML. Referenced indicator flows, LCIA
methods, unit groups, contacts and sources are referenced by their authoritative UUIDs and are not included (the
receiving system, e.g. ÖKOBAUDAT or the EPD Editor, holds them). Not included: ILCD+EPD 1.3 (2024 extension)
elements, scenarios, content declaration, contact data sets. Check the file in the EPD Editor before upload.
"""
import datetime
import io
import os
import uuid
import zipfile

from lxml import etree

import standards

NS_P = "http://lca.jrc.it/ILCD/Process"
NS_F = "http://lca.jrc.it/ILCD/Flow"
NS_C = "http://lca.jrc.it/ILCD/Common"
NS_E = "http://www.iai.kit.edu/EPD/2013"
NS_E2 = "http://www.indata.network/EPD/2019"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas", "ilcd_epd")

# InData identifiers, EN15804+A2_EF3.1_indicators.csv: abbreviation -> (uuid, version, name, unit, unit group uuid)
LCIA = {
    "AP": ("b5c611c6-def3-11e6-bf01-fe55135034f3", "01.04.000", "Acidification potential, Accumulated Exceedance (AP)", "mol H+ eqv.", "42e089ac-92bf-4bf2-8ca1-5fc40d18f2ed"),
    "GWP-total": ("a7ea142a-9749-11ed-a8fc-0242ac120002", "01.00.000", "Global Warming Potential - total (GWP-total)", "kg CO2 eqv.", "1ebf3012-d0db-4de2-aefd-ef30cedb0be1"),
    "GWP-biogenic": ("a7ea186c-9749-11ed-a8fc-0242ac120002", "01.00.000", "Global Warming Potential - biogenic (GWP-biogenic)", "kg CO2 eqv.", "1ebf3012-d0db-4de2-aefd-ef30cedb0be1"),
    "GWP-fossil": ("a7ea19c0-9749-11ed-a8fc-0242ac120002", "01.00.000", "Global Warming Potential - fossil fuels (GWP-fossil)", "kg CO2 eqv.", "1ebf3012-d0db-4de2-aefd-ef30cedb0be1"),
    "GWP-luluc": ("a7ea1ae2-9749-11ed-a8fc-0242ac120002", "01.00.000", "Global Warming Potential - land use and land use change (GWP-luluc)", "kg CO2 eqv.", "1ebf3012-d0db-4de2-aefd-ef30cedb0be1"),
    "ETP-fw": ("05316e7a-b254-4bea-9cf0-6bf33eb5c630", "01.00.000", "Potential Comparative Toxic Unit for ecosystems (ETP-fw)", "CTUe", "aa959ded-f1eb-4efb-9c5c-2d60be36b3e6"),
    "PM": ("b5c602c6-def3-11e6-bf01-fe55135034f3", "02.00.011", "Potential incidence of disease due to PM emissions (PM)", "disease incidence", "3883559b-648f-4afc-8ba2-0bd24f3affa3"),
    "EP-marine": ("b5c619fa-def3-11e6-bf01-fe55135034f3", "02.00.010", "Eutrophication potential - marine (EP-marine)", "kg N eqv.", "d05bb823-ecdf-4686-8c40-bf1d9257859f"),
    "EP-freshwater": ("b53ec18f-7377-4ad3-86eb-cc3f4f276b2b", "01.00.010", "Eutrophication potential - freshwater (EP-freshwater)", "kg P eqv.", "0429039d-a61d-4590-ba67-aa4a20a810a1"),
    "EP-terrestrial": ("b5c614d2-def3-11e6-bf01-fe55135034f3", "01.02.009", "Eutrophication potential - terrestrial (EP-terrestrial)", "mol N eqv.", "71b4d617-0ec9-4d3f-b65e-e438940c2401"),
    "HTP-c": ("2299222a-bbd8-474f-9d4f-4dd1f18aea7c", "01.01.000", "Potential Comparative Toxic Unit for humans - cancer effects (HTP-c)", "CTUh", "d4c9523e-2d7e-49fd-8469-998f547d3a70"),
    "HTP-nc": ("7cfdcfcf-b222-4b26-888a-a55f9fbf7ac8", "01.00.000", "Potential Comparative Toxic Unit for humans - non-cancer effects (HTP-nc)", "CTUh", "d4c9523e-2d7e-49fd-8469-998f547d3a70"),
    "IRP": ("b5c632be-def3-11e6-bf01-fe55135034f3", "01.00.011", "Potential Human exposure efficiency relative to U235 (IRP)", "kBq U235 eqv.", "456b05bf-1415-44a9-9993-02452f554c09"),
    "SQP": ("b2ad6890-c78d-11e6-9d9d-cec0c932ce01", "01.00.010", "Potential Soil quality index (SQP)", "unitless", "f130951c-e67f-4f7f-8dd4-665de3974e18"),
    "ODP": ("b5c629d6-def3-11e6-bf01-fe55135034f3", "02.00.012", "Depletion potential of the stratospheric ozone layer (ODP)", "kg CFC 11 eqv.", "d9e957c9-7309-4474-bf3a-7777df6c4e5b"),
    "POCP": ("b5c610fe-def3-11e6-bf01-fe55135034f3", "02.01.000", "Photochemical Ozone Creation Potential (POCP)", "kg NMVOC eqv.", "d27c25f8-fbc1-44c6-b47b-4adbae4199c6"),
    "ADP-fossil": ("b2ad6110-c78d-11e6-9d9d-cec0c932ce01", "01.00.010", "Abiotic depletion potential - fossil resources (ADPF)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66"),
    "ADP-minerals&metals": ("b2ad6494-c78d-11e6-9d9d-cec0c932ce01", "01.00.010", "Abiotic depletion potential - non-fossil resources (ADPE)", "kg Sb-eqv.", "54ccd2d9-a32a-4fc2-923d-f2c8c93e89d4"),
    "WDP": ("b2ad66ce-c78d-11e6-9d9d-cec0c932ce01", "03.00.014", "Water (user) deprivation potential (WDP)", "m3 world eqv.", "6ae2df01-888e-46c8-b17d-49fa3869b476"),
}
FLOWS = {  # resource use (input), waste and output flows (output)
    "PERE": ("20f32be5-0398-4288-9b6d-accddd195317", "Use of renewable primary energy (PERE)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "PERM": ("fb3ec0de-548d-4508-aea5-00b73bf6f702", "Use of renewable primary energy resources used as raw materials (PERM)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "PERT": ("53f97275-fa8a-4cdd-9024-65936002acd0", "Total use of renewable primary energy resources (PERT)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "PENRE": ("ac857178-2b45-46ec-892a-a9a4332f0372", "Use of non renewable primary energy (PENRE)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "PENRM": ("1421caa0-679d-4bf4-b282-0eb850ccae27", "Use of non renewable primary energy resources used as raw materials (PENRM)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "PENRT": ("06159210-646b-4c8d-8583-da9b3b95a6c1", "Total use of non renewable primary energy resource (PENRT)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "SM": ("c6a1f35f-2d09-4f54-8dfb-97e502e1ce92", "Use of secondary material (SM)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Input"),
    "RSF": ("64333088-a55f-4aa2-9a31-c10b07816787", "Use of renewable secondary fuels (RSF)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "NRSF": ("89def144-d39a-4287-b86f-efde453ddcb2", "Use of non renewable secondary fuels (NRSF)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Input"),
    "FW": ("3cf952c8-f3a4-461d-8c96-96456ca62246", "Use of net fresh water (FW)", "m3", "cd950537-0a98-4044-9ba7-9f9a68d0a504", "Input"),
    "HWD": ("430f9e0f-59b2-46a0-8e0d-55e0e84948fc", "Hazardous waste disposed (HWD)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "NHWD": ("b29ef66b-e286-4afa-949f-62f1a7b4d7fa", "Non hazardous waste dispose (NHWD)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "RWD": ("3449546e-52ad-4b39-b809-9fb77cea8ff6", "Radioactive waste disposed (RWD)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "CRU": ("a2b32f97-3fc7-4af2-b209-525bc6426f33", "Components for re-use (CRU)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "MFR": ("d7fe48a5-4103-49c8-9aae-b0b5dfdbd6ae", "Materials for recycling (MFR)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "MER": ("59a9181c-3aaf-46ee-8b13-2b3723b6e447", "Materials for energy recovery (MER)", "kg", "ad38d542-3fe9-439d-9b95-2f5f7752acaf", "Output"),
    "EEE": ("4da0c987-2b76-40d6-9e9e-82a017aaaf29", "Exported electrical energy (EEE)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Output"),
    "EET": ("98daf38a-7a79-46d3-9a37-2b7bd0955810", "Exported thermal energy (EET)", "MJ", "93a60a57-a3c8-11da-a746-0800200c9a66", "Output"),
}
SRC_ILCD = ("a97a0155-0234-4b87-b4ce-a45da52f2a40", "ILCD format")
SRC_EPD12 = ("a29449fd-aa2f-4de8-b5d7-4b06b43c6fde", "EPD Data Format Extensions v1.2")
SRC_EN15804A2 = ("c0016b33-8cf7-415c-ac6e-deba0d21440d", "EN 15804+A2")
# reference flow properties of declared units: unit -> (flow property uuid, name)
FLOW_PROPERTY = {"kg": ("93a60a56-a3c8-11da-a746-0800200b9a66", "Mass"), "t": ("93a60a56-a3c8-11da-a746-0800200b9a66", "Mass"),
                 "m3": ("93a60a56-a3c8-22da-a746-0800200c9a66", "Volume"), "m2": ("93a60a56-a3c8-19da-a746-0800200c9a66", "Area"),
                 "m": ("838aaa23-0117-11db-92e3-0800200c9a66", "Length"), "item": ("01846770-4cfe-4a25-8ad9-919d8d378345", "Number of items"),
                 "p": ("01846770-4cfe-4a25-8ad9-919d8d378345", "Number of items"), "mj": ("93a60a56-a3c8-11da-a746-0800200c9a66", "Net calorific value"),
                 "kwh": ("93a60a56-a3c8-11da-a746-0800200c9a66", "Net calorific value")}
SUBTYPES = ("generic dataset", "representative dataset", "average dataset", "specific dataset", "template dataset")
_validators = {}


def validator(kind="process"):
    """Process data sets: ILCD process schema with the EPD extensions 2013 and 2019. Flow data sets: ILCD flow schema.
    (Loaded separately: lxml fails with an internal error when both are in one schema set.)"""
    if kind not in _validators:
        f = "_cyclia_validate.xsd" if kind == "process" else "ILCD_FlowDataSet.xsd"
        _validators[kind] = etree.XMLSchema(etree.parse(os.path.join(SCHEMA_DIR, f)))
    return _validators[kind]


def _q(ns, tag):
    return f"{{{ns}}}{tag}"


def _sub(parent, ns, tag, text=None, **attrs):
    el = etree.SubElement(parent, _q(ns, tag), {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        el.text = str(text)
    return el


def _ml(parent, ns, tag, text, lang="en"):
    el = _sub(parent, ns, tag, text)
    el.set(XML_LANG, lang)
    return el


def _ref(parent, ns, tag, typ, uid, desc, version=None, uri=None):
    el = _sub(parent, ns, tag, type=typ, refObjectId=uid, version=version, uri=uri)
    _ml(el, NS_C, "shortDescription", desc)
    return el


def _num(v):
    return repr(float(v))


def indicator_values(model, result):
    """{abbreviation: {module: value}} for the EN 15804+A2 indicators found among the results, declared modules only."""
    mods = standards.by_module(result)
    declared = standards.declared_modules(model, result)
    import epd_profiles
    found = {}
    found.update(standards._match_core(result["results"]))
    found.update(standards.match_inventory(result["results"]))
    for a, k in epd_profiles.match_additional(result["results"]).items():
        found.setdefault(a, k)
    out = {}
    for a, k in found.items():
        if a not in LCIA and a not in FLOWS:
            continue
        out[a] = {m: mods[k]["modules"][m] for m in declared}
    return out, declared


def build(model, result, version="", now=None, dataset_uuid=None):
    """(process xml bytes, flow xml bytes, process uuid, flow uuid, list of indicators exported, warnings)."""
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    sc = model.get("scope") or {}
    epd = sc.get("epd") or {}
    fields = epd.get("fields") or {}
    pid = dataset_uuid or str(uuid.uuid5(uuid.NAMESPACE_URL, f"cyclia:epd:{model['id']}:{model['name']}"))
    fid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cyclia:epd-flow:{model['id']}:{model['name']}"))
    vals, declared = indicator_values(model, result)
    warnings = []
    if not vals:
        raise ValueError("No EN 15804+A2 indicator was found among the results. Calculate the EN 15804+A2 (EF 3.1) categories in step 4.")
    missing = [a for a in LCIA if a in ("GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater",
                                         "EP-marine", "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP") and a not in vals]
    if missing:
        warnings.append("Core indicators not calculated and not exported: " + ", ".join(missing))
    sub = (fields.get("epd_type") or epd.get("subtype") or "specific dataset").strip().lower()
    if not sub.endswith("dataset"):
        sub = sub + " dataset"
    if sub not in SUBTYPES:
        warnings.append(f"EPD type '{sub}' is not an ILCD+EPD sub-type; 'specific dataset' was used.")
        sub = "specific dataset"
    nsmap = {None: NS_P, "common": NS_C, "epd": NS_E, "epd2": NS_E2}
    root = etree.Element(_q(NS_P, "processDataSet"), nsmap=nsmap, version="1.1")
    root.set(_q(NS_E2, "epd-version"), "1.2")
    pi = _sub(root, NS_P, "processInformation")
    dsi = _sub(pi, NS_P, "dataSetInformation")
    _sub(dsi, NS_C, "UUID", pid)
    nm = _sub(dsi, NS_P, "name")
    _ml(nm, NS_P, "baseName", model["name"])
    if epd.get("description") or model.get("product"):
        _ml(dsi, NS_C, "generalComment", epd.get("description") or model.get("product"))
    qr = _sub(pi, NS_P, "quantitativeReference", type="Reference flow(s)")
    _sub(qr, NS_P, "referenceToReferenceFlow", "0")
    tm = _sub(pi, NS_P, "time")
    year = (epd.get("issued") or "")[:4] or str(now.year)
    _sub(tm, NS_C, "referenceYear", year)
    if (epd.get("valid_until") or "")[:4]:
        _sub(tm, NS_C, "dataSetValidUntil", epd["valid_until"][:4])
    if epd.get("issued"):
        to = _sub(tm, NS_C, "other")
        _sub(to, NS_E2, "publicationDateOfEPD", epd["issued"][:10])
    geo = (sc.get("geography") or "GLO").strip() or "GLO"
    import re as _re
    if not _re.fullmatch(r"[A-Z]{2,3}(-[A-Z0-9]{1,4})?|GLO|RER|RoW", geo):
        warnings.append(f"Geography '{geo}' is not an ILCD location code (e.g. FR, DE, RER, GLO): correct it in the EPD Editor.")
    g = _sub(pi, NS_P, "geography")
    _sub(g, NS_P, "locationOfOperationSupplyOrProduction", location=geo)
    mv = _sub(root, NS_P, "modellingAndValidation")
    lm = _sub(mv, NS_P, "LCIMethodAndAllocation")
    _sub(lm, NS_P, "typeOfDataSet", "EPD")
    lo = _sub(lm, NS_C, "other")
    _sub(lo, NS_E, "subType", sub)
    cd = _sub(mv, NS_P, "complianceDeclarations")
    cp = _sub(cd, NS_P, "compliance")
    _ref(cp, NS_C, "referenceToComplianceSystem", "source data set", SRC_EN15804A2[0], SRC_EN15804A2[1], "00.01.000")
    ad = _sub(root, NS_P, "administrativeInformation")
    de = _sub(ad, NS_P, "dataEntryBy")
    _sub(de, NS_C, "timeStamp", now.isoformat())
    _ref(de, NS_C, "referenceToDataSetFormat", "source data set", SRC_ILCD[0], SRC_ILCD[1], "01.00.000")
    _ref(de, NS_C, "referenceToDataSetFormat", "source data set", SRC_EPD12[0], SRC_EPD12[1], "00.01.000")
    po = _sub(ad, NS_P, "publicationAndOwnership")
    _sub(po, NS_C, "dataSetVersion", "00.01.000")
    reg = epd.get("number") or fields.get("registration") or fields.get("declaration_number")
    if reg:
        _sub(po, NS_C, "registrationNumber", reg)
    if not reg:
        warnings.append("No EPD registration number: add it in the EPD form before upload.")
    ex = _sub(root, NS_P, "exchanges")
    e0 = _sub(ex, NS_P, "exchange", dataSetInternalID="0")
    _ref(e0, NS_P, "referenceToFlowDataSet", "flow data set", fid, model.get("product") or model["name"], "00.01.000",
         f"../flows/{fid}.xml")
    _sub(e0, NS_P, "exchangeDirection", "Output")
    _sub(e0, NS_P, "meanAmount", _num(model.get("amount") or 1.0))
    exported = []
    n = 1
    for a, (uid, name, unit, ug, direction) in FLOWS.items():
        if a not in vals:
            continue
        e = _sub(ex, NS_P, "exchange", dataSetInternalID=str(n))
        n += 1
        _ref(e, NS_P, "referenceToFlowDataSet", "flow data set", uid, name, None, f"../flows/{uid}.xml")
        _sub(e, NS_P, "exchangeDirection", direction)
        _sub(e, NS_P, "meanAmount", "0.0")
        o = _sub(e, NS_C, "other")
        for mod, v in vals[a].items():
            _sub(o, NS_E, "amount", _num(v), **{_q(NS_E, "module"): mod})
        u = _sub(o, NS_E, "referenceToUnitGroupDataSet", type="unit group data set", refObjectId=ug)
        _ml(u, NS_C, "shortDescription", unit)
        exported.append(a)
    lr = _sub(root, NS_P, "LCIAResults")
    for a, (uid, ver, name, unit, ug) in LCIA.items():
        if a not in vals:
            continue
        r = _sub(lr, NS_P, "LCIAResult")
        _ref(r, NS_P, "referenceToLCIAMethodDataSet", "LCIA method data set", uid, name, ver, f"../lciamethods/{uid}.xml")
        _sub(r, NS_P, "meanAmount", "0.0")
        o = _sub(r, NS_C, "other")
        for mod, v in vals[a].items():
            _sub(o, NS_E, "amount", _num(v), **{_q(NS_E, "module"): mod})
        u = _sub(o, NS_E, "referenceToUnitGroupDataSet", type="unit group data set", refObjectId=ug)
        _ml(u, NS_C, "shortDescription", unit)
        exported.append(a)
    if not len(lr):
        root.remove(lr)
    proc = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    flow = _product_flow(fid, model, now)
    return proc, flow, pid, fid, exported, declared, warnings


def _product_flow(fid, model, now):
    unit = (model.get("unit") or "kg").strip().lower().replace("³", "3").replace("²", "2")
    prop = FLOW_PROPERTY.get(unit) or FLOW_PROPERTY.get(unit.rstrip("s")) or FLOW_PROPERTY["item"]
    root = etree.Element(_q(NS_F, "flowDataSet"), nsmap={None: NS_F, "common": NS_C}, version="1.1")
    fi = _sub(root, NS_F, "flowInformation")
    dsi = _sub(fi, NS_F, "dataSetInformation")
    _sub(dsi, NS_C, "UUID", fid)
    nm = _sub(dsi, NS_F, "name")
    _ml(nm, NS_F, "baseName", model.get("product") or model["name"])
    qr = _sub(fi, NS_F, "quantitativeReference")
    _sub(qr, NS_F, "referenceToReferenceFlowProperty", "0")
    mv = _sub(root, NS_F, "modellingAndValidation")
    lm = _sub(mv, NS_F, "LCIMethod")
    _sub(lm, NS_F, "typeOfDataSet", "Product flow")
    ad = _sub(root, NS_F, "administrativeInformation")
    de = _sub(ad, NS_F, "dataEntryBy")
    _sub(de, NS_C, "timeStamp", now.isoformat())
    _ref(de, NS_C, "referenceToDataSetFormat", "source data set", SRC_ILCD[0], SRC_ILCD[1], "01.00.000")
    po = _sub(ad, NS_F, "publicationAndOwnership")
    _sub(po, NS_C, "dataSetVersion", "00.01.000")
    fp = _sub(root, NS_F, "flowProperties")
    p = _sub(fp, NS_F, "flowProperty", dataSetInternalID="0")
    _ref(p, NS_F, "referenceToFlowPropertyDataSet", "flow property data set", prop[0], prop[1], "03.00.000")
    _sub(p, NS_F, "meanValue", "1.0")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def validate(xml_bytes, kind="process"):
    """List of schema errors (empty when valid)."""
    v = validator(kind)
    ok = v.validate(etree.fromstring(xml_bytes))
    return [] if ok else [f"line {e.line}: {e.message}" for e in v.error_log][:20]


def export(path, model, result, version=""):
    proc, flow, pid, fid, exported, declared, warnings = build(model, result, version)
    errors = validate(proc, "process") + validate(flow, "flow")
    if errors:
        raise ValueError("The ILCD+EPD file does not pass the schema check: " + "; ".join(errors[:5]))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"ILCD/processes/{pid}.xml", proc)
        z.writestr(f"ILCD/flows/{fid}.xml", flow)
        z.writestr("ILCD/README.txt", (
            f"ILCD+EPD 1.2 dataset written by Cyclia {version}.\n"
            "Validated against the ILCD and EPD extension (2013, 2019) schemas of the InData ILCD+EPD data format.\n"
            "Indicator flows, LCIA methods, unit groups and sources are referenced by their authoritative UUIDs and are\n"
            "not included. Open the zip in the EPD Editor (GreenDelta) to add contacts, review and the background report,\n"
            "and to check it before upload to ÖKOBAUDAT or another InData node.\n"))
    return {"path": path, "file": os.path.basename(path), "process_uuid": pid, "flow_uuid": fid,
            "indicators": exported, "modules": declared, "warnings": warnings, "schema_valid": True}
