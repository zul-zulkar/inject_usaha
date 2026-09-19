# -*- coding: utf-8 -*-
"""Uji tandai_selesai.py — offline. Jalankan: python tests/test_tandai_selesai.py"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tandai_selesai.tandai_selesai import KONSOL_TEMPLATE, PENANDA_CAKUPAN, PENANDA_TARGET, isi_template

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


template = KONSOL_TEMPLATE.read_text(encoding="utf-8")
check("penanda target tepat 1x di template", template.count(PENANDA_TARGET), 1)
check("penanda cakupan tepat 1x di template", template.count(PENANDA_CAKUPAN), 1)

kode = ["5108010001000203", "5108010001000302"]
daftar = isi_template(template, kode, semua=False)
check("daftar: target tersuntik",
      'const TARGET = [{"idsubsls": "5108010001000203"}, {"idsubsls": "5108010001000302"}];' in daftar, True)
check("daftar: cakupan daftar", 'const CAKUPAN = "daftar";' in daftar, True)

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
