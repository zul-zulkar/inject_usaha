#!/usr/bin/env python3
"""test_templat.py — templates/input_usaha.xlsx masih cocok dgn loader (inti/tahap2_loader.py):
baris contohnya dibaca, ditolak HANYA karena penanda CONTOH, dan SIAP tanpa penandanya.
Gagal = judul kolom / kode opsi di loader berubah -> jalankan templates/buat_templat_input_usaha.py.
Jalankan: python tests/test_templat.py"""

import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "templates"))

from buat_templat_input_usaha import KELUARAN, verifikasi  # noqa: E402

masalah = verifikasi(KELUARAN) if KELUARAN.exists() else [f"{KELUARAN} tidak ada"]
for m in masalah:
    print("FAIL |", m)
print("SEMUA PASS" if not masalah else "ADA YANG FAIL")
sys.exit(1 if masalah else 0)
