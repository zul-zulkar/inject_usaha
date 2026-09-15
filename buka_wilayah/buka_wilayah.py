#!/usr/bin/env python3
"""
buka_wilayah.py — Siapkan "Buka Wilayah" (batal tandai Selesai Listing) massal
di fasih-sm dari daftar idsubsls polos.

Tombol aslinya ada di halaman Data survei -> "Progress Penyelesaian Wilayah"
(pojok kanan atas) -> kartu wilayah berstatus "Listing Selesai" -> "Buka Wilayah".
fasih-sm menolak Playwright, jadi JALUR-nya Console Chrome biasa
(buka_wilayah_console.js). File ini hanya memvalidasi daftar & menyuntikkannya
ke template Console — TIDAK membuka browser.

LANGKAH
-------
    python buka_wilayah/buka_wilayah.py --daftar daftar_buka_wilayah.txt --console
Lalu di Chrome (login fasih-sm, halaman Data survei) -> F12 Console -> tempel
buka_wilayah_console.siap.js:
    await bukaWilayah.jalankan({mode: "cek"})                 // READ-ONLY
    await bukaWilayah.jalankan({mode: "eksekusi", limit: 1})  // 1 wilayah, cek hasilnya
    await bukaWilayah.jalankan({mode: "eksekusi"})            // sisanya
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "buka_wilayah_console.js"
KONSOL_SIAP = Path("./buka_wilayah_console.siap.js")
PENANDA_TARGET = "/*__TARGET__*/[]"
POLA_KODE = re.compile(r"5108\d{12}")


def baca_daftar(teks: str):
    """Daftar idsubsls (satu per baris; koma/spasi/titik-koma juga boleh; '#' =
    komentar) -> (kode_unik_urut, tidak_valid[(no_baris, token)], jumlah_duplikat).
    Token yang bukan 16 digit berawalan 5108 TIDAK diperbaiki/ditebak."""
    kode, tidak_valid, dup = [], [], 0
    terlihat = set()
    for no, baris in enumerate(teks.splitlines(), start=1):
        for token in re.split(r"[\s,;]+", baris.split("#", 1)[0].strip()):
            if not token:
                continue
            if not POLA_KODE.fullmatch(token):
                tidak_valid.append((no, token))
            elif token in terlihat:
                dup += 1
            else:
                terlihat.add(token)
                kode.append(token)
    return kode, tidak_valid, dup


def tulis_console(kode) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    if teks.count(PENANDA_TARGET) != 1:
        raise ValueError(f"Penanda {PENANDA_TARGET} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    data = [{"idsubsls": k} for k in kode]
    KONSOL_SIAP.write_text(teks.replace(PENANDA_TARGET, json.dumps(data)), encoding="utf-8")
    return KONSOL_SIAP


def main():
    ap = argparse.ArgumentParser(description="Siapkan Buka Wilayah massal (fasih-sm) dari daftar idsubsls")
    ap.add_argument("--daftar", required=True, help="File teks berisi idsubsls, satu per baris")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    args = ap.parse_args()

    kode, tidak_valid, dup = baca_daftar(Path(args.daftar).read_text(encoding="utf-8-sig"))
    print(f"{args.daftar}: {len(kode)} idsubsls unik" + (f", {dup} duplikat digabung" if dup else ""))
    for kec, n in sorted(Counter(k[:7] for k in kode).items()):
        print(f"  kec {kec}: {n}")
    if tidak_valid:
        print(f"⛔ {len(tidak_valid)} entri bukan idsubsls 16 digit (baris, isi): {tidak_valid[:10]}")
        print("Perbaiki file daftarnya dulu — tidak ada yang ditebak.")
        return 1
    if args.console:
        path = tulis_console(kode)
        print(f"\n{path} ditulis. Chrome biasa -> login fasih-sm -> halaman Data survei -> F12 Console -> tempel ->")
        print('  await bukaWilayah.jalankan({mode: "cek"})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
