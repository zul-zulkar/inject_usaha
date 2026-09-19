#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight.py — Periksa kesiapan baris backlog TANPA membuka browser & TANPA VPN.

Jalankan ini SEBELUM main.py. Satu run live yang gagal di baris ke-30 karena
kodepos/export bermasalah jauh lebih mahal daripada pemeriksaan 2 detik ini.

    python preflight.py --csv salin_dokumen_sumber.csv
    python preflight.py --csv salin_dokumen_sumber.csv --only-no 2522,2523
    python preflight.py --csv salin_dokumen_sumber.csv --verbose     # rincian per baris

Yang diperiksa (persis urutan gerbang di main.process_one_row):
  1. kodepos idsubsls terdaftar di config.KODEPOS_BY_IDSUBSLS
  2. file export/{No}_{assignment_id}.converted.json ada & cocok (match 1.0)
  3. alamat_nama_jalan tidak kosong
  4. kredensial (Email PPL + survey_assignment_id) lengkap
Plus pratinjau aturan pekerja/pengeluaran, dan usulan kodepos utk idsubsls
yang belum terdaftar — DITURUNKAN dari entri lain di DESA yang sama
(10 digit pertama idsubsls), bukan ditebak. Tetap perlu kamu konfirmasi.

Keluar dgn kode 0 kalau semua baris SIAP, 1 kalau ada yang tidak.
"""

from __future__ import annotations

import argparse
import collections
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# -- jalankan dari root proyek; sisipkan root ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import KODEPOS_BY_IDSUBSLS, WILAYAH_BY_IDSUBSLS
from inti.data_loader import (
    group_by_credential, load_backlog, rencana_pekerja, rencana_pengeluaran,
)
from input_fasihweb.export_source import kodepos_dari_export, load_source_blok2_from_export


def periksa_baris(row):
    """-> (status, keterangan, src|None)."""
    if not row.email_ppl or not row.survey_assignment_id:
        return ("SKIP_KREDENSIAL_TIDAK_LENGKAP",
                f"email='{row.email_ppl}' assignment='{row.survey_assignment_id}'", None)
    if not KODEPOS_BY_IDSUBSLS.get(row.idsubsls):
        kp, ket = kodepos_dari_export(row.idsubsls)
        if not kp:
            return ("SKIP_KODEPOS_TIDAK_DIKETAHUI", f"idsubsls {row.idsubsls} — {ket}", None)
    lk = load_source_blok2_from_export(row.no, row.row_assignment_id, row.nama_usaha_di_keluarga)
    if lk.status != "OK":
        return (f"SKIP_EXPORT_{lk.status}", lk.detail[:120], None)
    if not (lk.src.alamat_nama_jalan or "").strip():
        return ("SKIP_ALAMAT_KOSONG", "alamat_nama_jalan kosong di export", lk.src)
    return ("SIAP", "", lk.src)


def usul_kodepos(idsubsls: str):
    """Kodepos utk idsubsls yang belum ada di config, dari dua sumber bebas:
      (a) entri lain di DESA yang sama di config (10 digit pertama idsubsls);
      (b) file export mentah fasih-sm (dataKey 'kodepos' + 'var_desa').
    Keduanya di level DESA, bukan banjar — kodepos memang dialokasikan
    per desa, jadi semua banjar dalam satu desa memakai kodepos yang sama.
    Kembalikan (nilai, sumber) atau (None, alasan)."""
    desa = idsubsls[:10]
    dari_config = {v for k, v in KODEPOS_BY_IDSUBSLS.items() if k[:10] == desa}
    dari_export, ket = kodepos_dari_export(idsubsls)
    if len(dari_config) == 1 and dari_export:
        satu = next(iter(dari_config))
        if satu == dari_export:
            return satu, "config(desa sama) + export SEPAKAT"
        return None, f"BENTROK: config-desa={satu} vs export={dari_export} — cek manual"
    if dari_export:
        return dari_export, ket
    if len(dari_config) == 1:
        return next(iter(dari_config)), "dari entri desa yang sama di config"
    return None, ket


def main():
    ap = argparse.ArgumentParser(description="Pra-terbang backlog Usaha Pecahan SE2026")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--only-no", default=None, help="Batasi ke No tertentu, pisah koma")
    ap.add_argument("--verbose", action="store_true", help="Tampilkan rincian tiap baris SIAP")
    args = ap.parse_args()

    rows = load_backlog(args.csv, only_ready=True)
    if args.only_no:
        ingin = {s.strip() for s in args.only_no.split(",")}
        rows = [r for r in rows if r.no in ingin]
    if not rows:
        print("Tidak ada baris siap-proses (kolom nama_usaha_pecahan & kbli_pecahan wajib terisi).")
        return 1

    hitung = collections.Counter()
    masalah, siap = [], []
    for row in rows:
        status, ket, src = periksa_baris(row)
        hitung[status] += 1
        (siap if status == "SIAP" else masalah).append((row, status, ket, src))

    print(f"=== PRA-TERBANG: {len(rows)} baris dari {args.csv} ===\n")
    for status, n in hitung.most_common():
        tanda = "OK " if status == "SIAP" else "!! "
        print(f"  {tanda}{n:4d}  {status}")

    if masalah:
        print(f"\n=== {len(masalah)} baris TIDAK akan diproses ===")
        for row, status, ket, _ in masalah:
            print(f"  {row.no}  {status:32s} {ket}")

    kurang = sorted({r.idsubsls for r, s, _, _ in masalah if s == "SKIP_KODEPOS_TIDAK_DIKETAHUI"})
    if kurang:
        print("\n=== usulan KODEPOS_BY_IDSUBSLS (turunan desa yang sama — konfirmasi dulu) ===")
        for k in kurang:
            n = sum(1 for r in rows if r.idsubsls == k)
            usul, sumber = usul_kodepos(k)
            w = WILAYAH_BY_IDSUBSLS.get(k) or {}
            wilayah = f"{w.get('kecamatan', '?')} / {w.get('desa', '?')} / {w.get('sls', '?')}"
            if usul:
                print(f'    "{k}": "{usul}",   # {n} baris — {wilayah} [{sumber}]')
            else:
                print(f'    "{k}": "?????",   # {n} baris — {wilayah} ({sumber})')

    if args.verbose and siap:
        print(f"\n=== rincian {len(siap)} baris SIAP ===")
        print(f"  {'No':<6}{'pekerja':>8}{'26a':>10}{'26f':>12}  usaha")
        for row, _, _, src in siap:
            rp = rencana_pekerja(src.tk_laki_total, src.tk_perempuan_total,
                                 src.tk_dibayar_total, src.tk_tidak_dibayar_total)
            pg = rencana_pengeluaran(row, has_26c=True, nolkan_upah=rp.nolkan_upah)
            print(f"  {row.no:<6}{str(rp.total):>8}{pg.upah_gaji:>10,}{pg.total:>12,}  "
                  f"{row.nama_usaha_pecahan[:44]}")

    if siap:
        grup = group_by_credential([r for r, _, _, _ in siap])
        print(f"\n=== {len(grup)} sesi login utk {len(siap)} baris siap ===")
        for (email, assignment), anggota in sorted(grup.items(), key=lambda x: -len(x[1])):
            print(f"  {len(anggota):3d} baris  {email:34s} {assignment}")
        print("\nPerintah berikutnya (dry-run, TIDAK mengirim):")
        print(f"  python main.py --csv {args.csv} --only-no {siap[0][0].no}")

    return 0 if not masalah else 1


if __name__ == "__main__":
    sys.exit(main())
