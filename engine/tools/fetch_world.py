"""Download Natural Earth 1:110m country outlines (public domain) and write a compact app/ui/world.json for the
results map. Run during the build; if there is no internet the app falls back to a schematic map.

    python engine/tools/fetch_world.py
"""
import json
import os
import sys
import urllib.request

URLS = ["https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
        "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app", "ui", "world.json")


def simplify(gj, digits=1):
    out = []
    for f in gj.get("features", []):
        p = f.get("properties", {})
        code = next((str(p.get(k)) for k in ("ISO_A2_EH", "ISO_A2", "WB_A2") if p.get(k) and str(p.get(k)) not in ("-99", "None")), "")
        g = f.get("geometry") or {}
        polys = g.get("coordinates", []) if g.get("type") == "MultiPolygon" else [g.get("coordinates", [])] if g.get("type") == "Polygon" else []
        rings = []
        for poly in polys:
            if not poly:
                continue
            ring, last = [], None
            for x, y in poly[0]:
                pt = (round(x, digits), round(y, digits))
                if pt != last:
                    ring.append(list(pt))
                    last = pt
            if len(ring) >= 4:
                rings.append(ring)
        if rings:
            out.append({"code": code.upper(), "name": p.get("NAME") or p.get("ADMIN") or code, "rings": rings})
    return {"source": "Natural Earth 1:110m admin 0 countries (public domain)", "countries": out}


def main():
    for url in URLS:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                gj = json.loads(r.read().decode("utf-8"))
            data = simplify(gj)
            if len(data["countries"]) < 100:
                raise ValueError("too few countries")
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(data, fh, separators=(",", ":"))
            print(f"World map written: {len(data['countries'])} countries, {os.path.getsize(OUT) // 1024} kB")
            return 0
        except Exception as e:  # the map is optional
            print(f"Could not download the world map from {url}: {e}")
    print("The results map will use the schematic outline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
