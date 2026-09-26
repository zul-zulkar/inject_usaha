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

Alasan itu dihitung dgn fungsi yang SAMA PERSIS dgn yang dipakai input_usaha
saat batch jalan (pemeriksaan offline -> --lewati-selesai -> pemeriksaan giliran),
jadi angkanya bukan perkiraan.

Bagian "BELUM TUNTAS & ERROR" mendaftar nomor baris per keadaan (draft ber-galat,
draft tanpa koordinat, dokumen setengah jadi, gagal di run terakhir + pesannya, ...)
dgn format laporan sinkron_list. Status server diambil dari list_api_*.json hasil
sinkron_list.py KALAU ada (umurnya dicetak — berkas lama bisa ketinggalan); tanpa
berkas itu rekapnya murni dari audit.

Contoh:
    python input_usaha/rangkum_audit.py --sumber bahan/input_usaha.xlsx \
        --akun-tunggal ppl.contoh@gmail.com --subsls-tunggal 5108060006000224 --dari 2 --sampai 500
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti import lokasi  # noqa: E402
import input_usaha.mesin as mg  # noqa: E402
from input_usaha.bersihkan_error import ringkas_baris  # noqa: E402
from antar_pc.gabung_audit import baca_status_server  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LAPORAN_PATH = lokasi.HASIL_INPUT / "rangkum_audit.csv"
KOLOM = ["baris", "nama_usaha", "kunci", "status_audit", "kelompok", "dikerjakan", "alasan",
         "detail", "akun_login", "idsubsls_input", "dokumen_url",
         "rekap", "status_server", "galat_server", "pesan_terakhir"]

# Rekap "BELUM TUNTAS & ERROR": kode -> judul, dicetak berurutan spt laporan sinkron_list.
REKAP_JUDUL = {
    "SERVER_DRAFT": "Audit bilang terkirim, server masih DRAFT — dikirim ulang lewat URL",
    "DRAFT_GALAT": "Draft ber-GALAT di server — dikerjakan paling dulu oleh run berikutnya",
    "KOORDINAT_SUDAH_ADA": "Draft tanpa koordinat, koordinat SUDAH ada di sheet — geotag & kirim run berikutnya",
    "TUNGGU_KOORDINAT": "Draft tanpa koordinat — menunggu Latitude/Longitude diisi di sheet",
    "BELUM_SELESAI_DIISI": "Dokumen sudah dibuat, pengisian belum selesai — dibuka lewat URL run berikutnya",
    "DIHAPUS": "Dokumen lama dihapus admin — dibuat baru run berikutnya",
    "TERKIRIM_BELUM_TERBUKTI": "Toast 'terkirim' tanpa bukti server — pastikan dgn sinkron_list.py",
    "TANPA_URL": "Dokumen tanpa URL tercatat — jalankan sinkron_list.py --tulis dulu",
    "TERKUNCI": "Dokumen read-only padahal server DRAFT — perlu admin/PML",
    "GAGAL": "Gagal di run terakhir",
    "LAIN": "Status lain",
}
_TERKIRIM_SERVER = ("SUBMITTED", "APPROVED")


def rekap_baris(status: str, punya_koordinat: bool, srv: str = "", galat_srv: int = 0) -> str:
    """Kode REKAP_JUDUL utk satu baris, "" = tuntas / belum disentuh (yang terakhir
    sudah dilaporkan di bagian BELUM TERINPUT). `srv`/`galat_srv` = status & jumlah
    galat dokumennya menurut list_api_*.json ("" / 0 kalau tidak diketahui).
    Fungsi murni (diuji tests/test_gabung_audit.py)."""
    srv = (srv or "").upper()
    if status in mg.STATUS_TERKIRIM:
        if srv.startswith("DRAFT"):
            return "TERKUNCI" if status == mg.STATUS_TERKUNCI else "SERVER_DRAFT"
        if status == "TERKIRIM_BELUM_TERVERIFIKASI" and not srv.startswith(_TERKIRIM_SERVER):
            return "TERKIRIM_BELUM_TERBUKTI"
        return ""
    if not status:
        return ""
    if galat_srv > 0 and srv.startswith("DRAFT"):
        return "DRAFT_GALAT"
    if status == mg.STATUS_DRAFT_GALAT:
        return "DRAFT_GALAT"
    if status == mg.STATUS_DRAFT_TANPA_KOORDINAT:
        return "KOORDINAT_SUDAH_ADA" if punya_koordinat else "TUNGGU_KOORDINAT"
    if status == "DRAFT_DI_SERVER":
        return "SERVER_DRAFT"
    if status == mg.STATUS_DIBUAT:
        return "BELUM_SELESAI_DIISI"
    if status == mg.STATUS_DIHAPUS:
        return "DIHAPUS"
    if status in mg.STATUS_TANPA_URL_SEMUA:
        return "TANPA_URL"
    if status.startswith(("ERROR_", "SKIP_", "STOP_")) or status == "SUBMIT_GAGAL":
        return "GAGAL"
    return "LAIN"


def pesan_terakhir_dari(audit: list[dict]) -> dict:
    """{kunci: error_message terbaru yang tidak kosong} — DOKUMEN_DIBUAT dilewati
    (pesannya cuma "dibuat di luar audit ini" dsb., bukan penyebab gagal)."""
    out: dict = {}
    for b in audit:
        pesan = " ".join((b.get("error_message") or "").split())
        if b.get("kunci") and pesan and b.get("status") != mg.STATUS_DIBUAT:
            out[b["kunci"]] = pesan
    return out


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


def rangkum(rows, hasil, audit, target, tuntas, satu_subsls=True, status_server=None, galat_server=None):
    """-> (baris laporan, Counter kelompok, Counter alasan). Fungsi murni.
    `status_server`/`galat_server` = {id dokumen: ...} dari list_api_*.json (boleh None)."""
    status_server, galat_server = status_server or {}, galat_server or {}
    status_audit = mg.status_terakhir_dari(audit)
    dokumen = mg.dokumen_dari(audit)
    pesan = pesan_terakhir_dari(audit)
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
        id_dok = mg._id_dokumen(tercatat[2]) if tercatat[2] else ""
        srv, galat_srv = status_server.get(id_dok, ""), int(galat_server.get(id_dok) or 0)
        keluar.append({
            "baris": r.baris, "nama_usaha": r.nama_dokumen, "kunci": r.kunci,
            "status_audit": st, "kelompok": kel, "dikerjakan": "tidak" if alasan else "ya",
            "alasan": alasan, "detail": cek.pesan if cek else "",
            "akun_login": tercatat[0], "idsubsls_input": tercatat[1],
            "dokumen_url": tercatat[2],
            "rekap": rekap_baris(st, r.punya_koordinat, srv, galat_srv),
            "status_server": srv, "galat_server": galat_srv if srv else "",
            "pesan_terakhir": pesan.get(r.kunci, "") if st not in tuntas else "",
        })
    return keluar, kelompok, alasan_c


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rangkuman progres sheet vs audit_log_gabungan.csv")
    ap.add_argument("--sumber", required=True)
    mg.opsi_format(ap)
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
    ap.add_argument("--list-json", action="append",
                    help="list_api_<akun>.json hasil sinkron_list.py (boleh diulang/pola; bawaan list_api_*.json)")
    ap.add_argument("--tanpa-server", action="store_true",
                    help="abaikan list_api_*.json — rekap murni dari audit")
    mg.opsi_audit(ap)
    args = ap.parse_args(argv)
    lokasi.cek_struktur_lama()
    mg.pakai_audit(args.audit)

    otomatis = mg.koordinat_otomatis(args.koordinat, args.format)
    rows, hasil = mg.muat_sumber(args.sumber, args.format, mode_satu_subsls=True,
                                 izinkan_tanpa_koordinat=otomatis)
    total_sheet = len(rows)
    rows = mg.saring_rentang(rows, args.dari, args.sampai)
    audit = mg._baca_audit()
    mg.pastikan_audit_utuh(audit)
    tuntas = set(mg.STATUS_TERKIRIM if not args.tanpa_submit else mg.STATUS_SELESAI_DRY_RUN)
    target = ((args.akun_tunggal or "").lower(), args.subsls_tunggal or "")

    pola_json = [] if args.tanpa_server else (args.list_json or [lokasi.POLA_LIST_API])
    status_server, galat_server, _nama = baca_status_server(pola_json) if pola_json else ({}, {}, {})
    berkas_json = [f for p in pola_json for f in (lokasi.cari(p) if any(c in p for c in "*?")
                                                  else [Path(p)]) if f.exists()]
    keluar, kelompok, alasan_c = rangkum(rows, hasil, audit, target, tuntas,
                                         status_server=status_server, galat_server=galat_server)

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

    cetak_belum_tuntas(keluar, berkas_json)

    belum = [r for r in keluar if r["kelompok"] in ("BELUM DISENTUH", "DITOLAK PEMERIKSAAN DATA")]
    print(f"\n=== BELUM TERINPUT: {len(belum)} baris ===")
    if belum:
        print("  nomor baris: " + ringkas_baris([r["baris"] for r in belum])[:400])
    for r in belum[:max(0, args.daftar)]:
        print(f"  baris {r['baris']:>5}  {r['nama_usaha'][:44]:<44} {r['alasan'][:70]}")
    if args.daftar and len(belum) > args.daftar:
        print(f"  ... {len(belum) - args.daftar} lagi — semuanya ada di {args.csv}")

    with lokasi.siapkan(Path(args.csv)).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        for r in keluar:
            w.writerow({k: r.get(k, "") for k in KOLOM})
    print(f"\nRincian per baris: {args.csv}")
    return 0


def daftar_baris(baris: list, batas: int = 300) -> str:
    """Nomor baris ringkas ("2-4,9"), dipotong di batas koma + jumlah sisanya."""
    teks = ringkas_baris(baris)
    if len(teks) <= batas:
        return teks
    potong = teks[:batas].rsplit(",", 1)[0]
    tampil = 0
    for bagian in potong.split(","):
        awal, _, akhir = bagian.partition("-")
        tampil += int(akhir) - int(awal) + 1 if akhir else 1
    return f"{potong} … (+{len(set(baris)) - tampil} baris lagi — kolom 'rekap' di CSV)"


def cetak_belum_tuntas(keluar: list[dict], berkas_json: list[Path]) -> None:
    """Bagian "BELUM TUNTAS & ERROR": nomor baris per keadaan (format laporan
    sinkron_list), yang gagal dirinci per status + pesan terbarunya."""
    ada = [r for r in keluar if r["rekap"]]
    print(f"\n=== BELUM TUNTAS & ERROR: {len(ada)} baris ===")
    if berkas_json:
        terbaru = max(f.stat().st_mtime for f in berkas_json)
        print(f"  status server: {len(berkas_json)} list_api_*.json, terbaru "
              f"{datetime.datetime.fromtimestamp(terbaru):%Y-%m-%d %H:%M} — dokumen yang berubah sesudah itu "
              "belum terlihat (perbarui dgn sinkron_list.py)")
    else:
        print("  status server: tidak ada list_api_*.json — rekap ini murni dari audit "
              "(jalankan sinkron_list.py utk mencocokkan dgn server)")
    if not ada:
        print("  Tidak ada — semua yang sudah disentuh sudah tuntas.")
        return
    per_kode: dict[str, list[dict]] = defaultdict(list)
    for r in ada:
        per_kode[r["rekap"]].append(r)
    for kode, judul in REKAP_JUDUL.items():
        isi = per_kode.get(kode)
        if not isi:
            continue
        if kode in ("GAGAL", "LAIN"):
            print(f"  {judul} ({len(isi)}):")
            per_status: dict[str, list[dict]] = defaultdict(list)
            for r in isi:
                per_status[r["status_audit"]].append(r)
            for st, bag in sorted(per_status.items(), key=lambda t: -len(t[1])):
                pesan = next((r["pesan_terakhir"] for r in reversed(bag) if r["pesan_terakhir"]), "")
                print(f"      {st} ({len(bag)}): {daftar_baris([r['baris'] for r in bag])}")
                if pesan:
                    print(f"          pesan terbaru: {pesan[:150]}")
            continue
        tambahan = ""
        if kode == "DRAFT_GALAT":
            galat = Counter(r["galat_server"] for r in isi if r["galat_server"])
            if galat:
                tambahan = "  [galat menurut server: " + ", ".join(
                    f"{g} galat x{n}" for g, n in sorted(galat.items())) + "]"
        print(f"  {judul} ({len(isi)}): {daftar_baris([r['baris'] for r in isi])}{tambahan}")


if __name__ == "__main__":
    sys.exit(main())
