# -*- coding: utf-8 -*-
"""Uji buka_wilayah.py — offline. Jalankan: python tests/test_buka_wilayah.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import subprocess

from fasih_sm.buka_wilayah.buka_wilayah import KONSOL_TEMPLATE, PENANDA_CAKUPAN, PENANDA_TARGET, baca_daftar, isi_template

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
template = KONSOL_TEMPLATE.read_text(encoding="utf-8")
check("penanda target tepat 1x di template", template.count(PENANDA_TARGET), 1)
check("penanda cakupan tepat 1x di template", template.count(PENANDA_CAKUPAN), 1)

daftar = isi_template(template, kode[:2], semua=False)
check("daftar: target tersuntik",
      'const TARGET = [{"idsubsls": "5108010001000203"}, {"idsubsls": "5108010001000302"}];' in daftar, True)
check("daftar: cakupan daftar", 'const CAKUPAN = "daftar";' in daftar, True)
check("daftar: kode kabupaten dari config tersuntik", 'const KODE_KAB = "5108";' in daftar, True)

semua = isi_template(template, kode, semua=True)
check("semua: target kosong", "const TARGET = [];" in semua, True)
check("semua: cakupan semua", 'const CAKUPAN = "semua";' in semua, True)

try:
    isi_template("tanpa penanda", kode, semua=True)
    check("template tanpa penanda ditolak", False, True)
except ValueError:
    check("template tanpa penanda ditolak", True, True)

# Hasil suntikan harus tetap JS yang valid & terbaca sbg modul (Node).
node = subprocess.run(
    ["node", "-e", "const m=eval(require('fs').readFileSync(0,'utf8').replace(/^/, 'var module={exports:{}};')"
                   "+';module.exports');console.log(m.CAKUPAN, m.TARGET.length)"],
    input=semua, capture_output=True, text=True, encoding="utf-8")
check("siap.js semua bisa dimuat Node", node.stdout.strip(), "semua 0")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
