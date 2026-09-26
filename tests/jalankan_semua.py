#!/usr/bin/env python3
"""
jalankan_semua.py — Jalankan SEMUA uji offline (tanpa VPN/browser) sekaligus.

    python tests/jalankan_semua.py

Menjalankan setiap tests/test_*.py dgn Python yang sama, dan tests/test_*.js dgn
Node.js (dilewati kalau `node` tidak terpasang). Keluar dgn kode 1 kalau ada yang gagal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):   # konsol Windows cp1252 tidak bisa mencetak emoji keluaran uji
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def jalankan(perintah: list[str]) -> tuple[bool, str]:
    env = {**os.environ, "FASIH_ABAIKAN_CONFIG_LOKAL": "1", "PYTHONIOENCODING": "utf-8"}
    hasil = subprocess.run(perintah, cwd=AKAR, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
    keluaran = (hasil.stdout + hasil.stderr).strip()
    gagal = hasil.returncode != 0 or any(b.startswith("FAIL") for b in keluaran.splitlines())
    return not gagal, keluaran


def main() -> int:
    uji = [[sys.executable, str(p)] for p in sorted((AKAR / "tests").glob("test_*.py"))]
    node = shutil.which("node")
    berkas_js = sorted((AKAR / "tests").glob("test_*.js"))
    if node:
        uji += [[node, str(p)] for p in berkas_js]
    elif berkas_js:
        print(f"(node tidak ditemukan — {len(berkas_js)} uji JavaScript dilewati)")

    gagal = []
    for perintah in uji:
        nama = Path(perintah[1]).name
        ok, keluaran = jalankan(perintah)
        print(f"{'LULUS' if ok else 'GAGAL'}  {nama}")
        if not ok:
            gagal.append(nama)
            baris = [b for b in keluaran.splitlines() if b.startswith("FAIL") or "Error" in b]
            for b in (baris or keluaran.splitlines())[-10:]:
                print(f"         {b[:200]}")
    print(f"\n{len(uji) - len(gagal)}/{len(uji)} berkas uji lulus.")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
