"""Canonical elementary-flow naming so that flows and characterisation factors from different
nomenclatures (ecoinvent, ILCD/EF, openLCA, FEDEFL, SimaPro) can be matched.

canon(name, compartment, subcompartment) -> (name, compartment, subcompartment), all lower case, with
compartments mapped to the ecoinvent vocabulary: air, water, soil, natural resource.
"""
import re


def canon_name(name):
    n = str(name or "").strip().lower()
    n = re.sub(r"\s+", " ", n)
    # "carbon dioxide (fossil)" -> "carbon dioxide, fossil"
    m = re.fullmatch(r"(.+?)\s*\((.+)\)", n)
    if m and not re.search(r"\(\d", n):
        n = f"{m.group(1)}, {m.group(2)}"
    n = n.replace(" ,", ",")
    return n


def _has(s, *words):
    return any(w in s for w in words)


def canon_context(comp, sub=""):
    """Map any compartment description to (compartment, subcompartment) in ecoinvent terms."""
    full = f"{comp or ''}/{sub or ''}".lower().replace("_", " ")
    full = full.replace("elementary flows/", "")
    head = (comp or "").strip().lower()
    long_term = "long-term" in full or "long term" in full
    if _has(full, "resource", "raw material", "land use", "occupation", "transformation") and not head.startswith("emission"):
        c = "natural resource"
        if _has(full, "land", "occupation", "transformation"):
            s = "land"
        elif _has(full, "biotic", "biosphere", "biomass") and "abiotic" not in full:
            s = "biotic"
        elif _has(full, "ground", "soil", "fossil well"):
            s = "in ground"
        elif "water" in full:
            s = "in water"
        elif "air" in full:
            s = "in air"
        else:
            s = "unspecified"
        return c, s
    if head in ("air", "water", "soil"):
        c = head
    elif "air" in full:
        c = "air"
    elif "water" in full:
        c = "water"
    elif "soil" in full:
        c = "soil"
    else:
        return head, (sub or "").strip().lower()
    rest = (sub or "").lower() if head in ("air", "water", "soil") else full
    if c == "air":
        if "stratosphere" in rest:
            s = "lower stratosphere + upper troposphere"
        elif _has(rest, "non-urban", "low population", "high stack", "rural", "low. pop", "low pop"):
            s = "low population density, long-term" if long_term else "non-urban air or from high stacks"
        elif _has(rest, "urban", "high population", "high. pop", "high pop"):
            s = "urban air close to ground"
        elif "indoor" in rest:
            s = "indoor"
        else:
            s = "low population density, long-term" if long_term else "unspecified"
    elif c == "water":
        if "ground" in rest:
            s = "ground-, long-term" if long_term else "ground-"
        elif _has(rest, "sea", "ocean", "marine"):
            s = "ocean"
        elif _has(rest, "fresh", "surface", "river", "lake"):
            s = "surface water"
        else:
            s = "unspecified"
    else:
        if "non-agricultural" in rest or "industrial" in rest:
            s = "industrial"
        elif "agricultur" in rest:
            s = "agricultural"
        elif "forest" in rest:
            s = "forestry"
        else:
            s = "unspecified"
    return c, s


def canon(name, comp, sub=""):
    c, s = canon_context(comp, sub)
    return canon_name(name), c, s
