# -*- coding: utf-8 -*-
"""Uji buka_wilayah.py — offline. Jalankan: python tests/test_buka_wilayah.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from buka_wilayah.buka_wilayah import KONSOL_TEMPLATE, PENANDA_TARGET, baca_daftar

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


teks = """5108010001000203
5108010001000302, 5108010001000303
# komentar
5108010001000203
 5108010001200100  # sisa baris
5.10808E+15
510801000100020
"""
kode, tidak_valid, dup = baca_daftar(teks)
check("kode unik urut kemunculan", kode,
      ["5108010001000203", "5108010001000302", "5108010001000303", "5108010001200100"])
check("duplikat dihitung", dup, 1)
check("notasi ilmiah & 15 digit tidak ditebak", tidak_valid, [(6, "5.10808E+15"), (7, "510801000100020")])
check("penanda target tepat 1x di template", KONSOL_TEMPLATE.read_text(encoding="utf-8").count(PENANDA_TARGET), 1)

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
