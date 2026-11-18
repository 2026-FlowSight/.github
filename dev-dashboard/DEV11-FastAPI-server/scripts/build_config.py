"""Jednorazovo vygeneruje konfiguračné súbory config/cameras.yaml a config/parking.yaml.

Zdroje (sú v repe):
  - dev-dashboard/DEV13-db-search-frontend/data/cameras.js – 41 mestských kamier (MsP Pezinok 2024),
    polohy overené voči OpenStreetMap (11/2026), opravy v CAMERA_FIXES
  - scripts/data/pezinok_parking_osm.geojson – 12 skutočných parkovísk Pezinka z OpenStreetMap
    (polygóny amenity=parking, názov podľa ulice/obchodu, kapacita z OSM tagu, tlačovej správy alebo odhad z plochy)

Po vygenerovaní sú YAML súbory hlavný zdroj pravdy – dajú sa ručne upravovať (pridať kameru,
opraviť súradnice, zmeniť kapacitu parkoviska). Skript stačí spustiť znova len keď sa zmenia zdroje.

    python scripts/build_config.py
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEV12 = ROOT.parent / "DEV12-interactive-map" / "data"
DEV13 = ROOT.parent / "DEV13-db-search-frontend" / "data"

# Kamery bližšie ako toto k parkovisku ho „sledujú“ (pre DEV03 počítanie áut).
CAMERA_RADIUS_M = 200
# Opravy polôh po kontrole voči OpenStreetMap (11/2026).
CAMERA_FIXES = {
    # „Stĺp mestských hodín, Kollárova“ – OSM uzol amenity=clock 13326973204, pôvodne o 42 m vedľa
    "msp-3": (48.286607, 17.270779),
}


def read_js_value(path: Path, var: str):
    text = path.read_text(encoding="utf-8")
    start = text.index(f"window.{var}")
    start = text.index("=", start) + 1
    end = text.rindex(";")
    return json.loads(text[start:end])


def ring_of(geometry: dict) -> list[list[float]]:
    return geometry["coordinates"][0] if geometry["type"] == "Polygon" else geometry["coordinates"][0][0]


def area_m2(ring: list[list[float]]) -> float:
    lat0 = math.radians(ring[0][1])
    kx, ky = 111_320 * math.cos(lat0), 110_540
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        a += x1 * kx * y2 * ky - x2 * kx * y1 * ky
    return abs(a) / 2


def centroid(ring: list[list[float]]) -> tuple[float, float]:
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    kx = 111_320 * math.cos(math.radians(a[0]))
    return math.hypot((a[0] - b[0]) * 110_540, (a[1] - b[1]) * kx)


def main() -> None:
    cams = read_js_value(DEV13 / "cameras.js", "FLOWSIGHT_CAMERAS")
    cameras = []
    for c in cams:
        cameras.append({
            "id": c["id"],
            "no": c["no"],
            "name": c["name"],
            "area": c.get("area"),
            "street": c.get("street"),
            "type": c.get("type"),
            "mount": c.get("mount"),
            "site": c.get("site"),
            "lat": round(c["lat"], 6),
            "lng": round(c["lng"], 6),
            "precision": c.get("precision"),
        })

    for c in cameras:
        if c["id"] in CAMERA_FIXES:
            c["lat"], c["lng"] = CAMERA_FIXES[c["id"]]

    gj = json.loads((ROOT / "scripts" / "data" / "pezinok_parking_osm.geojson").read_text(encoding="utf-8"))
    parking = []
    for i, f in enumerate(gj["features"], 1):
        pr = f["properties"]
        ring = ring_of(f["geometry"])
        c = centroid(ring)
        near = sorted(cameras, key=lambda cam: dist_m(c, (cam["lat"], cam["lng"])))
        parking.append({
            "id": f"p-{i}",
            "name": pr["name"],
            "street": pr.get("street"),
            "kind": pr.get("kind"),
            "capacity": int(pr["capacity"]),
            "capacity_source": pr.get("capacity_source"),
            "lat": round(c[0], 6),
            "lng": round(c[1], 6),
            "cameras": [cam["id"] for cam in near[:3] if dist_m(c, (cam["lat"], cam["lng"])) < CAMERA_RADIUS_M],
            "area_m2": int(round(area_m2(ring), -1)),
            "source": pr.get("source"),
            "polygon": [[round(lat, 6), round(lng, 6)] for lng, lat in ring],
        })

    header_cams = (
        "# Mestské kamery Pezinok – konfigurácia pre API (DEV11) a mapu (DEV12).\n"
        "# Zdroj: Mestská polícia Pezinok, „Mestský kamerový systém Pezinok 2024“.\n"
        "# Súradnice nie sú v dokumente – sú odhadnuté z OpenStreetMap (pole precision).\n"
        "# Novú kameru pridáš novou položkou; id musí byť unikátne a rovnaké ako `camera` v Qdrante.\n"
    )
    header_parking = (
        "# Parkoviská Pezinka – konfigurácia pre API (DEV11) a mapu (DEV12).\n"
        "# Polygóny sú z OpenStreetMap (amenity=parking). OSM nemá pri parkoviskách v Pezinku názvy,\n"
        "# preto sú pomenované podľa ulice alebo obchodu. capacity_source hovorí, odkiaľ je kapacita.\n"
        "# cameras = mestské kamery do 200 m, ktoré môžu parkovisko vidieť (pre DEV03).\n"
    )
    yaml_opts = dict(allow_unicode=True, sort_keys=False, width=200)
    (ROOT / "config" / "cameras.yaml").write_text(header_cams + yaml.safe_dump({"cameras": cameras}, **yaml_opts), encoding="utf-8")
    (ROOT / "config" / "parking.yaml").write_text(
        header_parking + yaml.safe_dump({"parking": parking}, default_flow_style=None, **yaml_opts), encoding="utf-8")
    print(f"cameras.yaml: {len(cameras)} kamier, parking.yaml: {len(parking)} parkovísk")
    for p in parking:
        print(f"  {p['id']} {p['name']:<45} {p['capacity']:>4} miest  kamery={p['cameras']}")


if __name__ == "__main__":
    main()
