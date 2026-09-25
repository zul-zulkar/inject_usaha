#!/usr/bin/env python3
"""
tulis_id_sumber.py — isi kolom "ID Dokumen FASIH" di sheet sumber dari AUDIT.

main_gabungan / main_tahap2 sekarang menulis ID dokumen ke sheet sendiri begitu
dokumennya dibuat/dibuka (inti/id_dokumen.py). Alat ini utk dokumen yang SUDAH
terlanjur dibuat sebelum itu, dan utk ID yang tertunda karena sheet sedang dibuka
Excel. OFFLINE: tidak membuka browser & tidak menyentuh server.

Per baris sheet (dicocokkan lewat `kunci`, ID = URL dokumen TERAKHIR kunci itu di audit):
  TULIS       sel kosong, audit punya dokumen   -> diisi (dgn --tulis)
  SUDAH       sel = audit
  BEDA        sel berisi ID lain                -> TIDAK ditimpa, periksa manual
  HANYA_SHEET sel berisi ID, audit tidak kenal  -> dibiarkan (main_gabungan memakainya)
  ID_GANDA    audit memberi ID yang sama ke >1 baris -> TIDAK ditulis (dokumen ganda?)
  -           belum ada dokumen

Contoh (jalankan dari root proyek; tanpa --tulis = laporan saja):
    python input_gabungan/tulis_id_sumber.py --format tahap2 --sumber bahan/input_tahap2.xlsx
    python input_gabungan/tulis_id_sumber.py --format tahap2 --sumber bahan/input_tahap2.xlsx --tulis
TUTUP berkasnya di Excel dulu — berkas yang sedang dibuka tidak bisa ditulis.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import input_gabungan.main_gabungan as mg
from inti.id_dokumen import JUDUL_ID, PencatatIdSumber


def rencana_id(rows, dokumen: dict) -> list[tuple]:
    """Fungsi murni: [(row, kategori, id_audit)] — lihat docstring modul."""
    id_audit = {r.baris: mg.id_dari_url((dokumen.get(r.kunci) or ("", "", ""))[2]) for r in rows}
    per_id = defaultdict(list)
    for r in rows:
        if id_audit[r.baris] and not r.id_dokumen:
            per_id[id_audit[r.baris]].append(r.baris)
    keluar = []
    for r in rows:
        i = id_audit[r.baris]
        if r.id_dokumen:
            kategori = "SUDAH" if r.id_dokumen == i else ("BEDA" if i else "HANYA_SHEET")
        elif not i:
            kategori = "-"
        elif len(per_id[i]) > 1:
            kategori = "ID_GANDA"
        else:
            kategori = "TULIS"
        keluar.append((r, kategori, i))
    return keluar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"Isi kolom '{JUDUL_ID}' sheet sumber dari audit (offline)")
    ap.add_argument("--sumber", required=True, help="File .xlsx/.csv sumber (sama dgn --sumber main_gabungan)")
    ap.add_argument("--format", choices=("standar", "tahap2"), default="standar")
    ap.add_argument("--tulis", action="store_true", help="benar-benar menulis ke sheet (tanpa ini: laporan saja)")
    mg.opsi_audit(ap)
    args = ap.parse_args(argv)
    mg.pakai_audit(args.audit)
    mg.cetak_lokasi_audit()
    mg.pastikan_audit_utuh()

    rows, _ = mg.muat_sumber(args.sumber, args.format, mode_satu_subsls=True, izinkan_tanpa_koordinat=True)
    rencana = rencana_id(rows, mg.dokumen_per_kunci())
    jumlah = Counter(k for _, k, _ in rencana)
    print(f"{len(rows)} baris di {args.sumber}:")
    for k in ("TULIS", "SUDAH", "BEDA", "HANYA_SHEET", "ID_GANDA", "-"):
        if jumlah[k]:
            print(f"  {jumlah[k]:5}  {k}")
    for r, k, i in rencana:
        if k == "BEDA":
            print(f"  ⚠ baris {r.baris}: sheet {r.id_dokumen[:8]} vs audit {i[:8]} — {r.nama_dokumen}")
        elif k == "ID_GANDA":
            print(f"  ⚠ baris {r.baris}: ID {i[:8]} juga milik baris lain menurut audit — {r.nama_dokumen}")

    tulis = [(r, i) for r, k, i in rencana if k == "TULIS"]
    if not tulis:
        print("Tidak ada yang perlu ditulis.")
        return 0
    if not args.tulis:
        print(f"\n(laporan saja) Tambahkan --tulis utk mengisi {len(tulis)} sel kolom '{JUDUL_ID}'.")
        return 0
    pencatat = PencatatIdSumber(args.sumber, args.format)
    for r, i in tulis:
        pencatat.antre(r, i)
    pencatat.simpan()
    print(pencatat.ringkasan())
    return 0 if not pencatat.tertunda and not pencatat.dimatikan else 1


if __name__ == "__main__":
    sys.exit(main())
