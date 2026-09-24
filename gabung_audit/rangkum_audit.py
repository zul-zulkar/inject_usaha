#!/usr/bin/env python3
"""
rangkum_audit.py — rangkuman progres SATU sheet terhadap `audit_log_gabungan.csv`,
dan jawaban untuk "kenapa run berikutnya tidak mengerjakan apa-apa?".

OFFLINE & READ-ONLY: tidak membuka browser, tidak menyentuh server, tidak
mengubah audit. Aman dijalankan kapan saja, termasuk saat batch lain berjalan.

Bedanya dgn alat tetangga:
  gabung_audit.py   -> menyatukan audit beberapa PC + laporan per DOKUMEN
  bersihkan_error.py-> daftar sisa masalah + perintah perbaikannya
  rangkum_audit.py  -> progres per BARIS SHEET: sudah/belum, dan alasan tiap
                       baris yang TIDAK akan dikerjakan run berikutnya

Alasan itu dihitung dgn fungsi yang SAMA PERSIS dgn yang dipakai main_gabungan
saat batch jalan (pemeriksaan offline -> --lewati-selesai -> pemeriksaan giliran),
jadi angkanya bukan perkiraan.

Contoh:
    python gabung_audit/rangkum_audit.py --sumber bahan/input_tahap2.xlsx --format tahap2 \
        --akun-tunggal ppl.contoh@gmail.com --subsls-tunggal 5108060006000224 --dari 2 --sampai 500
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_gabungan.main_gabungan as mg  # noqa: E402
from gabung_audit.bersihkan_error import ringkas_baris  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LAPORAN_PATH = Path("./rangkum_audit.csv")
KOLOM = ["baris", "nama_usaha", "kunci", "status_audit", "kelompok", "dikerjakan", "alasan",
         "detail", "akun_login", "idsubsls_input", "dokumen_url"]


def kelompok_baris(status: str, cek_status: str, tuntas: set, punya_koordinat: bool) -> str:
    """Satu baris sheet masuk kelompok progres apa. Urutannya penting: status
    audit menang atas hasil pemeriksaan offline (dokumennya memang sudah ada)."""
    if status in mg.STATUS_TERKIRIM:
        return "TERKIRIM"
    if status == mg.STATUS_DRAFT_TANPA_KOORDINAT:
        return "DRAFT_TANPA_KOORDINAT"
    if status == mg.STATUS_DRAFT_GALAT:
        return "DRAFT_GALAT_DI_SERVER"
    if status in mg.STATUS_TANPA_URL_SEMUA:
        return "DOKUMEN_TANPA_URL"
    if status:
        return "SUDAH DISENTUH (belum tuntas)"
    if cek_status and cek_status.startswith("SKIP_"):
        return "DITOLAK PEMERIKSAAN DATA"
    return "BELUM DISENTUH"


def rangkum(rows, hasil, audit, target, tuntas, satu_subsls=True):
    """-> (baris laporan, Counter kelompok, Counter alasan). Fungsi murni."""
    status_audit = mg.status_terakhir_dari(audit)
    dokumen = mg.dokumen_dari(audit)
    keluar, kelompok, alasan_c = [], Counter(), Counter()
    # Aturannya TIDAK disalin ke sini: yang dipakai fungsi yang sama dgn batch.
    alasan_per_baris = dict(mg.kenapa_tidak_dikerjakan(rows, hasil, tuntas, lambda _r: target,
                                                       audit, satu_subsls))
    for r in rows:
        st = status_audit.get(r.kunci, "")
        cek = hasil.get(r.baris)
        cek_status = cek.status if cek else ""
        kel = kelompok_baris(st, cek_status, tuntas, r.punya_koordinat)
        kelompok[kel] += 1
        alasan = alasan_per_baris.get(r.baris, "")
        alasan_c[alasan.split(":")[0] if alasan else ""] += 1
        tercatat = dokumen.get(r.kunci) or ("", "", "")
        keluar.append({
            "baris": r.baris, "nama_usaha": r.nama_dokumen, "kunci": r.kunci,
            "status_audit": st, "kelompok": kel, "dikerjakan": "tidak" if alasan else "ya",
            "alasan": alasan, "detail": cek.pesan if cek else "",
            "akun_login": tercatat[0], "idsubsls_input": tercatat[1],
            "dokumen_url": tercatat[2],
        })
    return keluar, kelompok, alasan_c


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rangkuman progres sheet vs audit_log_gabungan.csv")
    ap.add_argument("--sumber", required=True)
    ap.add_argument("--format", choices=("standar", "tahap2"), default="standar")
    ap.add_argument("--akun-tunggal", default=mg.GABUNGAN_AKUN_TUNGGAL)
    ap.add_argument("--subsls-tunggal", default=mg.GABUNGAN_SUBSLS_TUNGGAL)
    ap.add_argument("--dari", type=int)
    ap.add_argument("--sampai", type=int)
    ap.add_argument("--koordinat", choices=("wajib", "otomatis", "kirim"))
    ap.add_argument("--tanpa-submit", action="store_true",
                    help="hitung spt run tanpa --submit (DRY_RUN_SIAP_KIRIM ikut dianggap tuntas)")
    ap.add_argument("--daftar", type=int, default=15,
                    help="cetak N baris pertama yang BELUM dikerjakan (0 = jangan)")
    ap.add_argument("--csv", default=str(LAPORAN_PATH))
    args = ap.parse_args(argv)

    otomatis = mg.koordinat_otomatis(args.koordinat, args.format)
    rows, hasil = mg.muat_sumber(args.sumber, args.format, mode_satu_subsls=True,
                                 izinkan_tanpa_koordinat=otomatis)
    total_sheet = len(rows)
    rows = mg.saring_rentang(rows, args.dari, args.sampai)
    audit = mg._baca_audit()
    tuntas = set(mg.STATUS_TERKIRIM if not args.tanpa_submit else mg.STATUS_SELESAI_DRY_RUN)
    target = ((args.akun_tunggal or "").lower(), args.subsls_tunggal or "")

    keluar, kelompok, alasan_c = rangkum(rows, hasil, audit, target, tuntas)

    print(f"Sumber   : {args.sumber} ({total_sheet} baris, rentang dipakai: {len(rows)})")
    print(f"Audit    : {mg.AUDIT_LOG_PATH} ({len(audit)} baris)")
    print(f"Target   : akun {target[0] or '(tidak disetel)'} | subsls {target[1] or '(tidak disetel)'}")

    print("\n=== PROGRES ===")
    for nama, n in sorted(kelompok.items(), key=lambda t: -t[1]):
        print(f"  {n:6d}  {nama}")

    akan = [r for r in keluar if r["dikerjakan"] == "ya"]
    print(f"\n=== RUN BERIKUTNYA (--lewati-selesai) ===\n  {len(akan)} baris akan dikerjakan.")
    if akan:
        print("  nomor baris: " + ringkas_baris([r["baris"] for r in akan])[:400])
    else:
        print("  Tidak ada baris yang bisa dikerjakan — itu sebabnya run langsung berhenti.")
        print("  Lihat alasannya di bawah; yang perlu tindakan biasanya "
              "'SKIP_DATA_*' (betulkan sheet) atau 'LEWATI_TANPA_URL' (sinkron_list --tulis).")

    print("\n=== ALASAN BARIS TIDAK DIKERJAKAN ===")
    for nama, n in sorted(alasan_c.items(), key=lambda t: -t[1]):
        if nama:
            print(f"  {n:6d}  {nama}")

    ditolak = Counter(r["detail"][:110] for r in keluar if r["kelompok"] == "DITOLAK PEMERIKSAAN DATA")
    if ditolak:
        print("\n=== YANG DITOLAK PEMERIKSAAN DATA (betulkan di Excel, lalu jalankan lagi) ===")
        for pesan, n in ditolak.most_common(12):
            print(f"  {n:6d}  {pesan}")
        if len(ditolak) > 12:
            print(f"  ... {len(ditolak) - 12} pola lain — lihat kolom 'detail' di {args.csv}")

    belum = [r for r in keluar if r["kelompok"] in ("BELUM DISENTUH", "DITOLAK PEMERIKSAAN DATA")]
    print(f"\n=== BELUM TERINPUT: {len(belum)} baris ===")
    if belum:
        print("  nomor baris: " + ringkas_baris([r["baris"] for r in belum])[:400])
    for r in belum[:max(0, args.daftar)]:
        print(f"  baris {r['baris']:>5}  {r['nama_usaha'][:44]:<44} {r['alasan'][:70]}")
    if args.daftar and len(belum) > args.daftar:
        print(f"  ... {len(belum) - args.daftar} lagi — semuanya ada di {args.csv}")

    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        for r in keluar:
            w.writerow({k: r.get(k, "") for k in KOLOM})
    print(f"\nRincian per baris: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
