# -*- coding: utf-8 -*-
"""Uji sumber kodepos (config vs export mentah) — offline, tanpa VPN.
Jalankan: python tests/test_kodepos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.config import KODEPOS_BY_IDSUBSLS
from input_fasihweb.export_source import _kodepos_valid, kodepos_dari_export, peta_kodepos_desa

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


# --- penyaring nilai placeholder ---
check("99999 ditolak", _kodepos_valid("99999"), False)
check("00000 ditolak", _kodepos_valid("00000"), False)
check("kosong ditolak", _kodepos_valid(""), False)
check("4 digit ditolak", _kodepos_valid("8117"), False)
check("bukan angka ditolak", _kodepos_valid("8117a"), False)
check("81171 diterima", _kodepos_valid("81171"), True)

# --- idsubsls tidak valid ---
check("idsubsls kosong -> tidak ada hasil", kodepos_dari_export("")[0], "")
check("idsubsls pendek -> tidak ada hasil", kodepos_dari_export("51080")[0], "")
check("desa tak dikenal -> tidak ada hasil", kodepos_dari_export("9999999999000101")[0], "")

peta = peta_kodepos_desa()
if not peta:
    print("SKIP | folder export/ kosong — uji silang thd data nyata dilewati.")
else:
    # --- konsistensi thd config yang sudah dikurasi ---
    beda = []
    for idsubsls, nilai in KODEPOS_BY_IDSUBSLS.items():
        dari_export, _ = kodepos_dari_export(idsubsls)
        if dari_export and dari_export != nilai:
            beda.append((idsubsls, nilai, dari_export))
    check("config vs export: tidak ada yang bentrok", beda, [])

    # --- mayoritas per-desa mengalahkan satu isian placeholder ---
    # Desa 5108030013: 3 file berisi 81154, 1 file berisi 99999.
    if "5108030013" in peta:
        check("placeholder 99999 tidak menang di desa 5108030013",
              kodepos_dari_export("5108030013000402")[0], "81154")

    # --- semua nilai hasil pemetaan berbentuk kodepos yang sah ---
    tidak_sah = [(d, e["kodepos"]) for d, e in peta.items() if not _kodepos_valid(e["kodepos"])]
    check("semua kodepos hasil pemetaan sah", tidak_sah, [])

    # --- pencocokan di level DESA, bukan banjar: dua SLS berbeda dalam satu
    #     desa harus menghasilkan kodepos yang sama ---
    desa = next(iter(peta))
    check("dua SLS beda dalam 1 desa -> kodepos sama",
          kodepos_dari_export(desa + "000101")[0] == kodepos_dari_export(desa + "999999")[0],
          True)

print("\n" + ("SEMUA UJI KODEPOS LOLOS" if ok_all else "ADA YANG GAGAL"))
sys.exit(0 if ok_all else 1)
