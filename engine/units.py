"""Unit conversion so users can enter data in the unit they measured (g, kWh, L ...).

Each unit maps to (dimension, factor to the dimension's base unit). Only units of the same
dimension convert. Names are matched case-insensitively after normalising spaces, '*', '.', '·'.
"""
import re

_UNITS = {
    # mass, base kg
    "kg": ("mass", 1.0), "g": ("mass", 1e-3), "mg": ("mass", 1e-6), "ug": ("mass", 1e-9), "µg": ("mass", 1e-9),
    "t": ("mass", 1e3), "ton": ("mass", 1e3), "tonne": ("mass", 1e3), "metric ton": ("mass", 1e3),
    "lb": ("mass", 0.45359237), "oz": ("mass", 0.028349523125), "kt": ("mass", 1e6),
    # energy, base MJ
    "mj": ("energy", 1.0), "kj": ("energy", 1e-3), "j": ("energy", 1e-6), "gj": ("energy", 1e3), "tj": ("energy", 1e6),
    "kwh": ("energy", 3.6), "wh": ("energy", 3.6e-3), "mwh": ("energy", 3600.0), "gwh": ("energy", 3.6e6),
    "btu": ("energy", 1.055056e-3), "kcal": ("energy", 4.1868e-3), "therm": ("energy", 105.506),
    # volume, base m3
    "m3": ("volume", 1.0), "l": ("volume", 1e-3), "litre": ("volume", 1e-3), "liter": ("volume", 1e-3),
    "dm3": ("volume", 1e-3), "ml": ("volume", 1e-6), "cm3": ("volume", 1e-6), "gal": ("volume", 3.785411784e-3),
    # area, base m2
    "m2": ("area", 1.0), "cm2": ("area", 1e-4), "mm2": ("area", 1e-6), "ha": ("area", 1e4), "km2": ("area", 1e6),
    "ft2": ("area", 0.09290304),
    # length, base m
    "m": ("length", 1.0), "km": ("length", 1e3), "cm": ("length", 1e-2), "mm": ("length", 1e-3),
    "mile": ("length", 1609.344), "ft": ("length", 0.3048),
    # transport (mass x distance), base t*km
    "t*km": ("transport", 1.0), "tkm": ("transport", 1.0), "ton*km": ("transport", 1.0),
    "metric ton*km": ("transport", 1.0), "kg*km": ("transport", 1e-3), "kgkm": ("transport", 1e-3),
    # person transport, base p*km
    "person*km": ("ptransport", 1.0), "pkm": ("ptransport", 1.0), "p*km": ("ptransport", 1.0),
    # vehicle distance, base vkm
    "vkm": ("vtransport", 1.0), "vehicle*km": ("vtransport", 1.0),
    # time, base hour
    "h": ("time", 1.0), "hour": ("time", 1.0), "min": ("time", 1 / 60), "s": ("time", 1 / 3600),
    "d": ("time", 24.0), "day": ("time", 24.0), "year": ("time", 8760.0), "a": ("time", 8760.0), "yr": ("time", 8760.0),
    # area x time, base m2*year
    "m2*year": ("landocc", 1.0), "m2*a": ("landocc", 1.0), "m2a": ("landocc", 1.0), "ha*year": ("landocc", 1e4),
    "ha*a": ("landocc", 1e4),
    # volume x distance (ecoinvent pipeline/transport of liquids)
    "m3*km": ("voltransport", 1.0), "m3km": ("voltransport", 1.0),
    # counts
    "unit": ("count", 1.0), "units": ("count", 1.0), "item": ("count", 1.0), "items": ("count", 1.0),
    "p": ("count", 1.0), "piece": ("count", 1.0), "pcs": ("count", 1.0), "pc": ("count", 1.0),
    # radioactivity, base kBq
    "kbq": ("radioactivity", 1.0), "bq": ("radioactivity", 1e-3), "mbq": ("radioactivity", 1e3),
}

# Nice display order per dimension, offered in the unit picker.
_ORDER = {
    "mass": ["kg", "g", "mg", "t", "lb"], "energy": ["MJ", "kWh", "kJ", "GJ", "MWh", "Wh"],
    "volume": ["m3", "l", "ml", "dm3"], "area": ["m2", "cm2", "ha", "km2"], "length": ["m", "km", "cm", "mm"],
    "transport": ["t*km", "kg*km"], "ptransport": ["person*km"], "vtransport": ["vkm"],
    "time": ["h", "min", "day", "year"], "landocc": ["m2*year", "ha*year"], "voltransport": ["m3*km"],
    "count": ["unit"], "radioactivity": ["kBq", "Bq"],
}


# user-defined units (Cyclia 1.6.1), loaded from the library: {normalised name: (dimension, factor to base)}
_CUSTOM = {}
_CUSTOM_DISPLAY = {}


def set_custom(rows):
    """rows: iterable of (name, dimension, factor). Replaces the user-defined units."""
    _CUSTOM.clear()
    _CUSTOM_DISPLAY.clear()
    for name, dim, f in rows:
        _CUSTOM[norm(name)] = (dim, float(f))
        _CUSTOM_DISPLAY.setdefault(dim, []).append(name)


def builtin(u):
    return norm(u) in _UNITS


def dimensions():
    """Built-in dimensions with their base unit, then dimensions created by the user."""
    base = {"mass": "kg", "energy": "MJ", "volume": "m3", "area": "m2", "length": "m", "transport": "t*km",
            "ptransport": "person*km", "vtransport": "vkm", "time": "h", "landocc": "m2*a", "voltransport": "m3*km",
            "count": "unit", "radioactivity": "kBq"}
    for name, (dim, f) in _CUSTOM.items():
        if dim.startswith("custom:") and dim not in base:
            base[dim] = dim[7:]
    return base


def norm(u):
    u = (u or "").strip().lower().replace("·", "*").replace(" x ", "*").replace("²", "2").replace("³", "3")
    u = re.sub(r"\s*\*\s*", "*", u)
    u = u.replace("cubic meter", "m3").replace("square meter", "m2").replace("kilogram", "kg")
    return u


def info(u):
    n = norm(u)
    return _UNITS.get(n) or _CUSTOM.get(n)


def factor(from_unit, to_unit):
    """Multiply a value in from_unit by this to get to_unit. None if not convertible."""
    if norm(from_unit) == norm(to_unit):
        return 1.0
    a, b = info(from_unit), info(to_unit)
    if not a or not b or a[0] != b[0]:
        return None
    return a[1] / b[1]


def compatible(u):
    """Units a user may type for a dataset whose unit is u (dataset unit first)."""
    i = info(u)
    if not i:
        return [u]
    out = [u] + [x for x in _ORDER.get(i[0], []) + _CUSTOM_DISPLAY.get(i[0], []) if norm(x) != norm(u)]
    return out
