# -*- coding: utf-8 -*-
"""Uji koordinat/peta.py (titik-dalam-poligon SUBSLS) — offline, tanpa file peta asli.
Jalankan: python tests/test_peta.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

from koordinat.peta import peta_dari_fitur  # noqa: E402

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


def kotak(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


A, B, INPUT = "5108010001000101", "5108010002000301", "5108060014000403"
peta = peta_dari_fitur([
    {"properties": {"idsubsls": A, "nmkec": "GEROKGAK", "nmdesa": "SATU", "nmsls": "BANJAR A"},
     "geometry": {"type": "Polygon", "coordinates": [kotak(0, 0, 1, 1), kotak(0.4, 0.4, 0.6, 0.6)]}},  # berlubang
    {"properties": {"idsubsls": B, "nmkec": "GEROKGAK", "nmdesa": "DUA", "nmsls": "BANJAR B"},
     "geometry": {"type": "MultiPolygon", "coordinates": [[kotak(2, 0, 3, 1)], [kotak(0.45, 0.45, 0.55, 0.55)]]}},
    {"properties": {"idsubsls": INPUT}, "geometry": {"type": "Polygon", "coordinates": [kotak(5, 5, 6, 6)]}},
])

# --- peta -------------------------------------------------------------------
check("titik di A", peta.titik(0.2, 0.2), [A])
check("titik di lubang A = pulau B", peta.titik(0.5, 0.5), [B])
check("titik di lubang A di luar pulau B", peta.titik(0.42, 0.42), [])
check("titik di luar semua", peta.titik(10, 10), [])
check("jarak 0 kalau di dalam", peta.jarak_m(A, 0.2, 0.2), 0.0)
check("jarak ±111 m ke tepi atas A", round(peta.jarak_m(A, 0.5, 1.001)), 111)
check("jarak subsls tak dikenal", peta.jarak_m("x", 0, 0), None)
check("nama wilayah", peta.nama(A), "[010] GEROKGAK | [001] SATU | [0001] BANJAR A | sub [01]")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
