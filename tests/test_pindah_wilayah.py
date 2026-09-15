# -*- coding: utf-8 -*-
"""Uji logika murni pindah_wilayah.py — offline, tanpa browser & tanpa file Agenda asli.
Jalankan: python tests/test_pindah_wilayah.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pindah_wilayah.pindah_wilayah as pw
from input_gabungan.sinkron_list import url_entry
from inti.gabungan_loader import GabunganRow

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


ASG = "fd68e454-ba45-4b85-8205-f3bf777ded24"
T1, T2 = "5108060002000203", "5108010001000101"


def row(baris, nama, tujuan=T1, pemilik="WAYAN", akun="PPL@gmail.com"):
    return GabunganRow(baris, {"akun_ppl": akun, "idsubsls": tujuan, "nama": nama, "pengusaha": pemilik,
                               "nama_komersial": nama})


a = row(2, "PANGKALAN GAS", pemilik="WAYAN SUMARTAWA")
b = row(3, "APOTEK KEMBAR", tujuan=T2, pemilik="")
b2 = row(9, "APOTEK KEMBAR", tujuan=T1, pemilik="")   # nama dokumen sama, baris beda
c = row(4, "PRAKTIK BIDAN", tujuan="5.10806E+15")
audit = [
    {"kunci": a.kunci, "dokumen_url": url_entry("id-a-1", ASG), "idsubsls_input": "5108060014000403"},
    {"kunci": a.kunci, "dokumen_url": url_entry("id-a-1", ASG), "idsubsls_input": "5108060014000403"},
    {"kunci": a.kunci, "dokumen_url": "", "idsubsls_input": "5108010010000105"},
    {"kunci": "lain", "dokumen_url": url_entry("id-x", ASG), "idsubsls_input": ""},
]
sumber = [("D:/x/Agenda.xlsx", a), ("Agenda1-1.xlsx", b), ("Agenda2.xlsx", b2), ("Agenda2.xlsx", c),
          ("Agenda2.xlsx", row(2, "PANGKALAN GAS", pemilik="WAYAN SUMARTAWA"))]
target, masalah, ringkas = pw.bangun_target(sumber, audit)
per_k = {t["k"]: t for t in target}

check("jumlah target (tujuan salah dilewati, kembar digabung)", len(target), 3)
check("tujuan tidak valid -> masalah", [(s, br) for s, br, _ in masalah], [("Agenda2.xlsx", 4)])
check("kembar digabung", ringkas["baris_kembar_digabung"], 1)
check("target a lengkap", per_k[a.kunci],
      {"k": a.kunci, "s": "Agenda.xlsx", "b": 2, "n": "PANGKALAN GAS (WAYAN SUMARTAWA)", "t": T1,
       "p": "ppl@gmail.com", "ids": ["id-a-1"]})
check("nama ganda ditandai di kedua baris", (per_k[b.kunci].get("g"), per_k[b2.kunci].get("g")), (1, 1))
check("ringkasan id audit", (ringkas["dgn_id_audit"], ringkas["tanpa_id_audit"]), (1, 2))

asal, salah = pw.subsls_asal(audit, ["5108010001000101", "123"])
check("subsls asal dari audit + tambahan", asal, ["5108010001000101", "5108010010000105", "5108060014000403"])
check("asal tidak valid dilaporkan", salah, ["123"])

# Template: penanda ada tepat sekali & hasil suntikan bisa dimuat Node dgn TARGET/ASAL terisi.
teks = pw.KONSOL_TEMPLATE.read_text(encoding="utf-8")
check("penanda template", (teks.count(pw.PENANDA_TARGET), teks.count(pw.PENANDA_ASAL)), (1, 1))
siap = teks.replace(pw.PENANDA_TARGET, json.dumps(target, ensure_ascii=False)).replace(pw.PENANDA_ASAL, json.dumps(asal))
try:
    out = subprocess.run(["node", "-e", "const m=require('module');const x=new m();x._compile(require('fs')."
                          "readFileSync(0,'utf8'),'siap.js');console.log(x.exports.TARGET.length+'|'+x.exports.ASAL.length)"],
                         input=siap, capture_output=True, text=True, encoding="utf-8", timeout=30)
    check("file siap dimuat Node", out.stdout.strip(), "3|3")
except FileNotFoundError:
    print("SKIP | node tidak ada")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
