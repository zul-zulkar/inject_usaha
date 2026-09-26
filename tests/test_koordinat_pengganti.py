# -*- coding: utf-8 -*-
"""Uji koordinat pengganti tahap 2 — offline, poligon & titik FIKTIF.
Jalankan: python tests/test_koordinat_pengganti.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

from koordinat.peta import peta_dari_fitur  # noqa: E402
from koordinat.koordinat_pengganti import (  # noqa: E402
    Jalan, TitikListing, baca_koordinat, dms_tanpa_simbol, kunci_kelompok, meter, pilih_subsls, rencana,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


# --- membaca teks koordinat (pola nyata sheet 2026-09-24) ---
check("desimal koma", baca_koordinat("-8,14435", "lat"), -8.14435)
check("desimal titik", baca_koordinat("115.0794770", "lon"), 115.079477)
check("akhiran S", baca_koordinat("-8.12736124S", "lat"), -8.12736124)
check("akhiran E", baca_koordinat("115.070484E", "lon"), 115.070484)
check("derajat-menit-detik", round(baca_koordinat("8°7'35,424\"S", "lat"), 6), -8.126507)
check("derajat-menit-detik bujur", round(baca_koordinat("115°4'48,129\"E", "lon"), 6), 115.080036)
check("° sbg titik desimal", baca_koordinat("8°12887404S", "lat"), -8.12887404)
check("titik desimal hilang (lintang)", baca_koordinat("-812399973S", "lat"), -8.12399973)
check("titik desimal hilang (bujur)", baca_koordinat("115093422", "lon"), 115.093422)
check("koma dobel", baca_koordinat("-8,10356,1", "lat"), -8.103561)
check("spasi", baca_koordinat("114, 96437916", "lon"), 114.96437916)
check("lintang tanpa minus", baca_koordinat("8.130898", "lat"), -8.130898)
check("kosong", baca_koordinat("", "lat"), None)
check("angka dari sel numerik", baca_koordinat(-8.2, "lat"), -8.2)

check("derajat tanpa simbol lintang", round(dms_tanpa_simbol("-8,747", "lat"), 6), -8.129722)
check("derajat tanpa simbol bujur (155 -> 115)", round(dms_tanpa_simbol("155,2058", "lon"), 6), 115.349444)
check("menit >= 60 ditolak", dms_tanpa_simbol("115,7512", "lon"), None)

# --- kelompok pemilik + alamat ---
check("pemilik & alamat sama walau beda tulisan", kunci_kelompok(2, "I Made  Contoh.", "Jl. Contoh, No 1"),
      kunci_kelompok(3, "I MADE CONTOH", "JL CONTOH NO 1"))
check("alamat kosong -> baris sendiri", kunci_kelompok(5, "I MADE CONTOH", "-"), "baris:5")
anggota = [{"baris": 1, "idsubsls": "A"}, {"baris": 2, "idsubsls": "B"}, {"baris": 3, "idsubsls": "B"}]
check("subsls baris terbanyak", pilih_subsls(anggota, {}), "B")
seri = [{"baris": 1, "idsubsls": "B"}, {"baris": 2, "idsubsls": "A"}]
check("seri -> subsls tempat titik jatuh", pilih_subsls(seri, {1: "", 2: "A"}), "A")
check("seri tanpa titik -> kode terkecil", pilih_subsls(seri, {}), "A")

# --- rencana dgn peta fiktif: dua subsls persegi ±1,1 km di Buleleng ---
def persegi(ids, lat0, lon0, d=0.01):
    ring = [[lon0, lat0], [lon0 + d, lat0], [lon0 + d, lat0 + d], [lon0, lat0 + d], [lon0, lat0]]
    return {"properties": {"idsubsls": ids}, "geometry": {"type": "Polygon", "coordinates": [ring]}}


A, B = "5108990001000101", "5108990001000102"
peta = peta_dari_fitur([persegi(A, -8.20, 115.00), persegi(B, -8.20, 115.02)])
listing = TitikListing([(-8.195, 115.005), (-8.193, 115.007), (-8.195, 115.025)])
baris = [
    # 2: di dalam A -> tetap
    {"baris": 2, "idsubsls": A, "pemilik": "I MADE CONTOH", "alamat": "BANJAR SATU", "lat_mentah": "-8,1950",
     "lon_mentah": "115,0050"},
    # 3: pemilik & alamat sama, titik 3 km -> ikut koordinat baris 2
    {"baris": 3, "idsubsls": A, "pemilik": "I Made Contoh", "alamat": "Banjar Satu", "lat_mentah": "-8,1950",
     "lon_mentah": "115,0350"},
    # 4: sendirian, bujur 145 (salah ketik 115) -> diperbaiki
    {"baris": 4, "idsubsls": A, "pemilik": "NI LUH CONTOH", "alamat": "BANJAR DUA", "lat_mentah": "-8,1960",
     "lon_mentah": "145,0060"},
    # 5: sendirian, 2 km di luar B (di kabupaten) -> acak listing di B
    {"baris": 5, "idsubsls": B, "pemilik": "I KETUT CONTOH", "alamat": "BANJAR TIGA", "lat_mentah": "-8,1950",
     "lon_mentah": "115,0500"},
    # 6: kosong -> acak
    {"baris": 6, "idsubsls": B, "pemilik": "I WAYAN CONTOH", "alamat": "BANJAR EMPAT", "lat_mentah": "",
     "lon_mentah": ""},
    # 7-9: satu kelompok, 2 baris di B & 1 di A -> subsls B
    {"baris": 7, "idsubsls": A, "pemilik": "KADEK CONTOH", "alamat": "PASAR", "lat_mentah": "-8,1950",
     "lon_mentah": "115,0050"},
    {"baris": 8, "idsubsls": B, "pemilik": "KADEK CONTOH", "alamat": "PASAR", "lat_mentah": "", "lon_mentah": ""},
    {"baris": 9, "idsubsls": B, "pemilik": "KADEK CONTOH", "alamat": "PASAR", "lat_mentah": "", "lon_mentah": ""},
]
h = {x["baris"]: x for x in rencana(baris, peta, listing)}
check("2: titik benar tetap", (h[2]["sumber"], h[2]["lat"], h[2]["lon"]), ("ASLI", -8.195, 115.005))
check("3: ikut koordinat kelompok", (h[3]["sumber"], h[3]["lat"], h[3]["lon"]),
      ("KELOMPOK (dari baris 2)", -8.195, 115.005))
check("4: salah ketik 145 -> 115", (h[4]["sumber"], h[4]["lon"]), ("SALAH_KETIK_DIPERBAIKI", 115.006))
check("5: diganti titik listing di B (digeser 5–15 m)",
      (h[5]["sumber"], 4.9 <= meter(h[5]["lat"], h[5]["lon"], -8.195, 115.025) <= 15.1), ("ACAK_LISTING", True))
check("6: kosong -> titik listing di B", h[6]["sumber"], "ACAK_LISTING")
check("7-9: satu koordinat di subsls mayoritas B",
      ({(h[i]["lat"], h[i]["lon"]) for i in (7, 8, 9)}.__len__(), h[7]["subsls_koordinat"],
       peta.jarak_m(B, h[7]["lon"], h[7]["lat"])), (1, B, 0.0))
h2 = {x["baris"]: x for x in rencana(baris, peta, listing)}
check("acak tapi tetap (dijalankan ulang = sama)", [(h2[i]["lat"], h2[i]["lon"]) for i in (5, 6, 8)],
      [(h[i]["lat"], h[i]["lon"]) for i in (5, 6, 8)])
check("titik jauh tidak 'diperbaiki' dgn tebakan satu digit (di kabupaten)", h[5]["sumber"] != "SALAH_KETIK_DIPERBAIKI",
      True)

# --- dekat jalan: titik listing dekat ruas didahulukan; tanpa listing -> tepi ruas ---
jalan = Jalan([(-8.1931, 115.0010, -8.1931, 115.0090)])   # ruas di lintang -8.1931 dalam A
baris_j = [{"baris": 20, "idsubsls": A, "pemilik": "X CONTOH", "alamat": "Y", "lat_mentah": "", "lon_mentah": ""}]
hj = rencana(baris_j, peta, listing, jalan, jarak_jalan_m=50)[0]
check("listing dekat jalan dipilih (-8.193 bukan -8.195)",
      (hj["sumber"], jalan.jarak_m(hj["lat"], hj["lon"]) <= 50), ("ACAK_LISTING_DEKAT_JALAN", True))
hk = rencana(baris_j, peta, None, jalan, jarak_jalan_m=50)[0]
check("tanpa listing -> dekat ruas jalan di poligon",
      (hk["sumber"], jalan.jarak_m(hk["lat"], hk["lon"]) <= 20, peta.jarak_m(A, hk["lon"], hk["lat"])),
      ("ACAK_POLIGON_DEKAT_JALAN", True, 0.0))

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
