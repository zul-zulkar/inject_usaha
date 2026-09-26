"""
peta.py — Peta batas SUBSLS (GeoJSON) + titik-dalam-poligon, murni Python (tanpa shapely).

Dipakai koordinat/koordinat_pengganti.py utk memeriksa apakah titik koordinat jatuh di
subsls baris. Lokasi berkas peta: config PETA_SLS_PATH (inti/config_lokal.py) atau --peta.
(Dulu bagian dari input_gabungan/rencana_ubah_wilayah.py — laporan itu dihapus 2026-09-25,
digantikan fasih_sm/pindah_wilayah.)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


def _dalam_ring(x: float, y: float, ring: list) -> bool:
    dalam = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dalam = not dalam
        j = i
    return dalam


def _dalam_poligon(x: float, y: float, poligon: list) -> bool:
    """poligon GeoJSON = [ring luar, lubang...]."""
    return _dalam_ring(x, y, poligon[0]) and not any(_dalam_ring(x, y, h) for h in poligon[1:])


@dataclass
class PetaSls:
    sls: dict  # idsubsls -> {"nama", "bbox": (minx, miny, maxx, maxy), "poligon": [poligon, ...]}

    def titik(self, lon: float, lat: float) -> list[str]:
        """idsubsls yang memuat titik (normalnya 0 atau 1)."""
        return [i for i, s in self.sls.items()
                if s["bbox"][0] <= lon <= s["bbox"][2] and s["bbox"][1] <= lat <= s["bbox"][3]
                and any(_dalam_poligon(lon, lat, p) for p in s["poligon"])]

    def jarak_m(self, idsubsls: str, lon: float, lat: float) -> float | None:
        """Jarak titik ke batas subsls (meter, pendekatan equirectangular); 0 kalau di dalam."""
        s = self.sls.get(idsubsls)
        if s is None:
            return None
        if any(_dalam_poligon(lon, lat, p) for p in s["poligon"]):
            return 0.0
        kx, ky = 111320 * math.cos(math.radians(lat)), 110574
        terdekat = math.inf
        for poligon in s["poligon"]:
            for ring in poligon:
                for a, b in zip(ring, ring[1:]):
                    ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
                    dx, dy = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
                    panjang = dx * dx + dy * dy
                    t = 0.0 if panjang == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / panjang))
                    terdekat = min(terdekat, math.hypot(ax + t * dx, ay + t * dy))
        return terdekat

    def nama(self, idsubsls: str) -> str:
        return self.sls.get(idsubsls, {}).get("nama", "")


def peta_dari_fitur(features: list[dict]) -> PetaSls:
    sls = {}
    for f in features:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if not p.get("idsubsls") or g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        poligon = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        xs = [pt[0] for pol in poligon for pt in pol[0]]
        ys = [pt[1] for pol in poligon for pt in pol[0]]
        i = p["idsubsls"]
        nama = (f"[{i[4:7]}] {p.get('nmkec', '')} | [{i[7:10]}] {p.get('nmdesa', '')} | "
                f"[{i[10:14]}] {p.get('nmsls', '')} | sub [{i[14:16]}]")
        sls[i] = {"nama": nama, "bbox": (min(xs), min(ys), max(xs), max(ys)), "poligon": poligon}
    return PetaSls(sls)


def muat_peta(path: str | Path) -> PetaSls:
    return peta_dari_fitur(json.loads(Path(path).read_text(encoding="utf-8"))["features"])
