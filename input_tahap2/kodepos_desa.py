#!/usr/bin/env python3
"""
kodepos_desa.py — Susun KODEPOS_BY_DESA (kodepos per DESA, 10 digit pertama
idsubsls) dari data yang SUDAH ada, untuk sheet yang tidak punya kolom kodepos
(format tahap 2). TIDAK membuka browser.

Sumber (semuanya berisi pasangan wilayah -> kodepos yang pernah diisi/terkirim):
  --dari <file>  sheet format standar (input_usaha.xlsx, Agenda*.xlsx; boleh
                 berulang). Bawaan: bahan/input_usaha.xlsx + Agenda*.xlsx di root.
  export/*.json  file export mentah fasih-sm (lihat export_source.peta_kodepos_desa).

Kodepos dialokasikan per desa, jadi yang dipakai adalah nilai TERBANYAK per
desa dari semua sumber. Desa yang bentrok (lebih dari satu kodepos) tetap
diambil mayoritasnya tapi DICETAK supaya bisa dicek; kalau imbang, desa itu
TIDAK ditulis (tidak ditebak).

Contoh:
    python input_tahap2/kodepos_desa.py --sumber bahan/input_tahap2.xlsx
    python input_tahap2/kodepos_desa.py --sumber bahan/input_tahap2.xlsx --tulis

--tulis mengganti blok bertanda di inti/config_lokal.py (file itu TIDAK ikut
git — kodepos/wilayah kabupaten sendiri memang disimpan di sana).
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# -- jalankan dari root proyek; sisipkan root ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from inti.config import KODEPOS_BY_DESA, KODEPOS_BY_IDSUBSLS
from inti.gabungan_loader import load_gabungan
from inti.tahap2_loader import load_tahap2

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

CONFIG_LOKAL = Path("inti/config_lokal.py")
AWAL_BLOK = "# >>> KODEPOS_BY_DESA — dibangkitkan input_tahap2/kodepos_desa.py (jangan diedit manual) >>>"
AKHIR_BLOK = "# <<< KODEPOS_BY_DESA <<<"


def kumpulkan(sumber_standar: list[str], pakai_export: bool = True) -> dict[str, Counter]:
    """{desa 10 digit: Counter(kodepos -> dukungan)} dari semua sumber."""
    suara: dict[str, Counter] = defaultdict(Counter)
    for f in sumber_standar:
        try:
            rows = load_gabungan(f)
        except Exception as e:  # noqa: BLE001 — satu file rusak jangan hentikan yang lain
            print(f"⚠️ {f} dilewati: {str(e)[:120]}")
            continue
        for r in rows:
            kp = r["kodepos"]
            if re.fullmatch(r"\d{5}", kp or "") and re.fullmatch(r"\d{16}", r.idsubsls):
                suara[r.idsubsls[:10]][kp] += 1
    for ids, kp in KODEPOS_BY_IDSUBSLS.items():
        suara[ids[:10]][kp] += 1
    if pakai_export:
        try:
            from input_fasihweb.export_source import peta_kodepos_desa
            for desa, entri in peta_kodepos_desa().items():
                for kp, n in (entri.get("varian") or {entri["kodepos"]: entri.get("dukungan", 1)}).items():
                    if re.fullmatch(r"\d{5}", str(kp)):
                        suara[desa][str(kp)] += int(n)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ export fasih-sm tidak terbaca: {str(e)[:120]}")
    return suara


def putuskan(suara: dict[str, Counter]) -> tuple[dict[str, str], dict[str, Counter]]:
    """(kodepos terpilih per desa, desa yang bentrok). Imbang -> tidak dipilih."""
    pilih, bentrok = {}, {}
    for desa, c in suara.items():
        urut = c.most_common()
        if len(urut) > 1:
            bentrok[desa] = c
            if urut[0][1] == urut[1][1]:
                continue
        pilih[desa] = urut[0][0]
    return pilih, bentrok


def tulis_config_lokal(peta: dict[str, str]) -> None:
    isi = CONFIG_LOKAL.read_text(encoding="utf-8") if CONFIG_LOKAL.exists() else ""
    baris = [AWAL_BLOK, "KODEPOS_BY_DESA = {"]
    baris += [f'    "{d}": "{k}",' for d, k in sorted(peta.items())]
    baris += ["}", AKHIR_BLOK]
    blok = "\n".join(baris)
    if AWAL_BLOK in isi and AKHIR_BLOK in isi:
        a, b = isi.index(AWAL_BLOK), isi.index(AKHIR_BLOK) + len(AKHIR_BLOK)
        isi = isi[:a] + blok + isi[b:]
    else:
        isi = isi.rstrip("\n") + "\n\n" + blok + "\n"
    CONFIG_LOKAL.write_text(isi, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", required=True, help="sheet format tahap 2 yang butuh kodepos")
    ap.add_argument("--dari", action="append", default=None,
                    help="sheet format standar sumber kodepos (bawaan: bahan/input_usaha.xlsx + Agenda*.xlsx)")
    ap.add_argument("--tanpa-export", action="store_true", help="jangan pakai export/*.json fasih-sm")
    ap.add_argument("--tulis", action="store_true", help="tulis hasilnya ke inti/config_lokal.py")
    args = ap.parse_args(argv)

    dari = args.dari or [f for f in ["bahan/input_usaha.xlsx", *sorted(glob.glob("Agenda*.xlsx"))] if Path(f).exists()]
    print(f"Sumber kodepos: {dari}" + ("" if args.tanpa_export else " + export/*.json"))
    suara = kumpulkan(dari, pakai_export=not args.tanpa_export)
    pilih, bentrok = putuskan(suara)

    rows = load_tahap2(args.sumber)
    per_desa: dict[str, list] = defaultdict(list)
    for r in rows:
        if re.fullmatch(r"\d{16}", r.idsubsls):
            per_desa[r.idsubsls[:10]].append(r)
    print(f"\n{args.sumber}: {len(rows)} baris, {len(per_desa)} desa\n")
    print(f"  {'desa':10s}  {'nama':28s} {'baris':>5s}  kodepos  keterangan")
    kurang = 0
    for desa, anggota in sorted(per_desa.items()):
        nama = " / ".join(filter(None, (anggota[0].wilayah.get("kecamatan", ""), anggota[0].wilayah.get("desa", ""))))
        lama = KODEPOS_BY_DESA.get(desa, "")
        kp = pilih.get(desa, "")
        if desa in bentrok:
            ket = "BENTROK " + ", ".join(f"{k}x{n}" for k, n in bentrok[desa].most_common())
            ket += "" if kp else " -> IMBANG, tidak ditulis"
        elif kp:
            ket = f"{sum(suara[desa].values())} dukungan"
        else:
            ket = "TIDAK ADA di sumber mana pun — isi manual di config_lokal / kolom 'kodepos' sheet"
        if lama and kp and lama != kp:
            ket += f" (config sekarang {lama})"
        kurang += not kp
        print(f"  {desa:10s}  {nama[:28]:28s} {len(anggota):5d}  {kp or '-':7s}  {ket}")

    print(f"\n{len(per_desa) - kurang}/{len(per_desa)} desa terisi; {len(pilih)} desa total dari sumber.")
    if args.tulis:
        tulis_config_lokal(pilih)
        print(f"✅ KODEPOS_BY_DESA ({len(pilih)} desa) ditulis ke {CONFIG_LOKAL}.")
    else:
        print("(belum ditulis — ulangi dgn --tulis)")
    return 0 if not kurang else 1


if __name__ == "__main__":
    sys.exit(main())
