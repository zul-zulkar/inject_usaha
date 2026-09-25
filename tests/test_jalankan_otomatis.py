"""Uji offline input_tahap2/jalankan_otomatis.py — deteksi rate limit dari output bot.

Yang dikunci: "429" polos BUKAN tanda rate limit. ID survei di setiap URL dokumen
(`a0429e96-…`) memuatnya, sehingga (2026-09-25) SEMUA run terbaca "kena limit" &
wrapper pindah ke akun cadangan / berhenti padahal server tidak menolak apa pun."""
import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh Buleleng di config.py

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from input_tahap2.jalankan_otomatis import evaluasi_hasil

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


print("\n== rate limit ==")
for teks, harap in (("HTTP 429", True), ("status: 429", True), ("429 Too Many Requests", True),
                    ('{"error":"RATE_LIMIT_EXCEEDED"}', True), ("Too many request", True),
                    ("terlalu banyak permintaan", True),
                    ("https://fasih-web.bps.go.id/survey/a0429e96-51a5-477b/entry", False),
                    ("baris 429: SIAP", False), ("totalHit 1429", False), ("id 4291abcd", False)):
    cek(teks, evaluasi_hasil(teks)["rate_limited"], harap)

print("\n== tuntas ==")
cek("selesai tanpa sisa", evaluasi_hasil(
    "Ringkasan run: 5 baris diproses, 2 dilewati, 0 belum sempat dikerjakan\nSelesai. Audit: a.csv")["tuntas"], True)
cek("masih ada sisa", evaluasi_hasil(
    "Ringkasan run: 5 baris diproses, 2 dilewati, 3 belum sempat dikerjakan\nSelesai. Audit: a.csv")["tuntas"], False)

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
