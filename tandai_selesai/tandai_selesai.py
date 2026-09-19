#!/usr/bin/env python3
"""
tandai_selesai.py — Siapkan "Tandai Selesai Listing" massal di fasih-sm
(kebalikan buka_wilayah.py).

Tombol aslinya ada di halaman Data survei -> "Progress Penyelesaian Wilayah"
(pojok kanan atas) -> kartu wilayah berstatus "Proses Listing" -> "Tandai Selesai
Listing". fasih-sm menolak Playwright, jadi JALUR-nya Console Chrome biasa
(tandai_selesai_console.js). File ini hanya memvalidasi daftar & menyuntikkannya
ke template Console — TIDAK membuka browser.

LANGKAH
-------
    python tandai_selesai/tandai_selesai.py --semua --console
    python tandai_selesai/tandai_selesai.py --daftar daftar_buka_wilayah.txt --console
Lalu di Chrome (login fasih-sm, halaman Data survei) -> F12 Console -> tempel
tandai_selesai_console.siap.js:
    await tandaiSelesai.jalankan({mode: "cek"})                 // READ-ONLY
    await tandaiSelesai.jalankan({mode: "eksekusi", limit: 1})  // 1 wilayah, cek hasilnya
    await tandaiSelesai.jalankan({mode: "eksekusi"})            // sisanya
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from buka_wilayah.buka_wilayah import PENANDA_KODE_KAB, baca_daftar  # noqa: E402 — format daftar sama persis
from inti.config import KODE_KAB  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "tandai_selesai_console.js"
KONSOL_SIAP = Path("./tandai_selesai_console.siap.js")
PENANDA_TARGET = "/*__TARGET__*/[]"
PENANDA_CAKUPAN = '/*__CAKUPAN__*/"daftar"'


def isi_template(teks: str, kode, semua: bool) -> str:
    """Suntikkan target ke template. Cakupan semua -> TARGET tetap [] (dibaca dari
    pindai massal di browser), daftar -> TARGET berisi kode."""
    for penanda in (PENANDA_TARGET, PENANDA_CAKUPAN, PENANDA_KODE_KAB):
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    data = [] if semua else [{"idsubsls": k} for k in kode]
    return (teks.replace(PENANDA_TARGET, json.dumps(data))
                .replace(PENANDA_CAKUPAN, json.dumps("semua" if semua else "daftar"))
                .replace(PENANDA_KODE_KAB, json.dumps(KODE_KAB)))


def tulis_console(kode, semua: bool) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    KONSOL_SIAP.write_text(isi_template(teks, kode, semua), encoding="utf-8")
    return KONSOL_SIAP


def main():
    ap = argparse.ArgumentParser(description="Siapkan Tandai Selesai Listing massal (fasih-sm)")
    sumber = ap.add_mutually_exclusive_group(required=True)
    sumber.add_argument("--semua", action="store_true",
                        help="SEMUA subsls periode (daftar dibaca di browser dari Progress Penyelesaian Wilayah)")
    sumber.add_argument("--daftar", help="File teks berisi idsubsls, satu per baris")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    args = ap.parse_args()

    kode = []
    if args.semua:
        print("Cakupan: SEMUA subsls periode — daftarnya dibaca skrip Console dari server saat dijalankan.")
    else:
        kode, tidak_valid, dup = baca_daftar(Path(args.daftar).read_text(encoding="utf-8-sig"))
        print(f"{args.daftar}: {len(kode)} idsubsls unik" + (f", {dup} duplikat digabung" if dup else ""))
        for kec, n in sorted(Counter(k[:7] for k in kode).items()):
            print(f"  kec {kec}: {n}")
        if tidak_valid:
            print(f"⛔ {len(tidak_valid)} entri bukan idsubsls 16 digit (baris, isi): {tidak_valid[:10]}")
            print("Perbaiki file daftarnya dulu — tidak ada yang ditebak.")
            return 1
        if not kode:
            print("⛔ Daftar kosong.")
            return 1
    if args.console:
        path = tulis_console(kode, args.semua)
        print(f"\n{path} ditulis. Chrome biasa -> login fasih-sm -> halaman Data survei -> F12 Console -> tempel ->")
        print('  await tandaiSelesai.jalankan({mode: "cek"})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
