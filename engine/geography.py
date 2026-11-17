"""Geographies of ecoinvent and how they contain each other (Cyclia 1.10).

The topology is that of constructive_geometries (Chris Mutel and Paul Scherrer Institute, BSD 3-clause; see
data/geographies-LICENSE.txt), which ecoinvent's own linking is built on. The world is split into faces that do not
overlap. Each geography (a country, a province, a grid region, RER, "Europe without Switzerland", ...) is a set of
faces, so "A contains B" is "the faces of B are a subset of the faces of A", and the size of a geography is the area of
its faces. GLO is every face. RoW ("rest of the world") has no faces of its own: it is the world minus the
geographies of the other suppliers of the same product.

Supplier choice for an input at location L follows ecoinvent's linking rules:
1. a supplier at L itself;
2. the smallest supplier geography that contains L (a province in a country, a country in a region);
3. RoW, when no other supplier geography contains L;
4. GLO.
A supplier whose geography only overlaps L, or lies inside it, is not a match for L.
"""
import functools
import gzip
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "geographies.json.gz")
SPECIAL = {"GLO", "ROW", "ROE"}


@functools.lru_cache(maxsize=1)
def _data():
    with gzip.open(DATA, "rb") as fh:
        d = json.loads(fh.read().decode())
    faces = {k: frozenset(v) for k, v in d["faces"].items()}
    upper = {k.upper(): k for k in faces}
    for old, new in d["aliases"].items():
        if new in faces:
            upper.setdefault(old.upper(), new)
    areas = {int(k): v for k, v in d["areas"].items()}
    world = frozenset().union(*faces.values())
    return faces, upper, areas, world, frozenset(x.upper() for x in d["empty"]), d["source"]


def source():
    return _data()[5]


def name(code):
    """The geography's name in the topology, or None when unknown (RoW and GLO have no entry)."""
    if not code:
        return None
    return _data()[1].get(str(code).strip().upper())


def known(code):
    c = (code or "").strip().upper()
    return c in SPECIAL or name(c) is not None


def faces(code):
    """The faces of a geography; GLO is the world; None for RoW, an empty geography or an unknown code."""
    c = (code or "").strip().upper()
    if c == "GLO":
        return _data()[3]
    n = name(c)
    return _data()[0][n] if n else None


def area(code):
    f = faces(code)
    if f is None:
        return None
    a = _data()[2]
    return sum(a.get(i, 0.0) for i in f)


def contains(outer, inner):
    """Whether geography `outer` contains `inner` (both known, not RoW)."""
    fo, fi = faces(outer), faces(inner)
    return bool(fo is not None and fi and fi <= fo)


def relation(consumer, supplier, others=()):
    """How a supplier geography relates to a consumer location, given the other suppliers' geographies (for RoW).

    Returns (kind, rank, text): kind is 'exact', 'contains', 'row', 'glo', 'overlaps', 'inside', 'other' or 'unknown';
    rank orders the matches (lower is better; None for no match)."""
    c, s = (consumer or "").strip().upper(), (supplier or "").strip().upper()
    if not c:
        if s in ("GLO", "ROW"):
            return "glo" if s == "GLO" else "row", 3, f"{supplier}: input without a location"
        return "other", None, "input without a location"
    if c == s:
        return "exact", 0, f"same location ({supplier})"
    if s == "GLO":
        return "glo", 3, "global dataset"
    if s == "ROW":
        if faces(c) is None:
            return "row", 2.8, f"rest of the world; location '{consumer}' is not in the topology, so this is not checked"
        # RoW covers the consumer only when no other supplier's geography contains it
        cover = [o for o in others if (o or "").strip().upper() not in SPECIAL and contains(o, consumer)]
        if cover:
            return "other", None, f"RoW excludes {consumer}: {', '.join(sorted(set(cover)))} covers it"
        part = [o for o in others if (o or "").strip().upper() not in SPECIAL and faces(o) and faces(consumer)
                and faces(o) & faces(consumer)]
        if part:
            return "row", 2.5, f"rest of the world; part of {consumer} is supplied by {', '.join(sorted(set(part)))}"
        return "row", 2, f"rest of the world (no other supplier covers {consumer})"
    if faces(c) is None or faces(s) is None:
        return "unknown", None, f"geography '{consumer if faces(c) is None else supplier}' is not in the topology"
    if contains(s, c):
        a_s, a_c = area(s) or 0.0, area(c) or 1.0
        # 1 < rank < 2: a smaller containing region ranks better
        return "contains", 1 + min(0.99, (a_s / (a_s + a_c * 10))), f"{supplier} contains {consumer}"
    if contains(c, s):
        return "inside", None, f"{supplier} is only part of {consumer}"
    if faces(c) & faces(s):
        return "overlaps", None, f"{supplier} overlaps {consumer} only in part"
    return "other", None, f"{supplier} does not cover {consumer}"


def best(consumer, suppliers):
    """(index, reason, rank) of the supplier ecoinvent's rules choose for `consumer` among supplier locations;
    (None, reason, None) when no supplier matches or two match equally well."""
    ranks = []
    for i, s in enumerate(suppliers):
        kind, rank, text = relation(consumer, s, [o for j, o in enumerate(suppliers) if j != i])
        if rank is not None:
            ranks.append((rank, i, kind, text))
    if not ranks:
        return None, "no supplier geography covers this location", None
    ranks.sort()
    if len(ranks) > 1 and ranks[0][0] == ranks[1][0]:
        return None, f"{len([r for r in ranks if r[0] == ranks[0][0]])} suppliers match equally ({ranks[0][3]})", None
    return ranks[0][1], ranks[0][3], ranks[0][0]
