#!/usr/bin/env python3
"""
bersihkan_error.py — kumpulkan dokumen/baris yang BELUM beres (galat, DRAFT
nyangkut, dokumen yatim) dari audit + list API, lalu siapkan perintah untuk
membereskannya.

SIFAT: OFFLINE & READ-ONLY. Tidak membuka browser, tidak menyentuh server, tidak
mengubah audit. Yang dihasilkan cuma daftar + perintah siap jalan — karena yang
benar-benar membereskan tetap `input_usaha/jalankan.py` (di situ semua
pengaman submit berada; jangan dibuat jalur kirim kedua).

Kenapa perlu: sesudah beberapa PC digabung (lihat gabung_audit.py), sisa
masalahnya tercecer di ratusan baris audit. Tiap jenis masalah butuh tindakan
BERBEDA — ada yang cukup dijalankan ulang, ada yang datanya harus dibetulkan
dulu di sheet, dan ada yang cuma bisa diberesi admin pusat.

    python input_usaha/bersihkan_error.py --sumber bahan/input_usaha.xlsx
    python input_usaha/bersihkan_error.py --sumber Agenda.xlsx --sumber Agenda2.xlsx

Tindakan yang dikeluarkan:
  ULANGI            jalankan ulang barisnya — dokumen lama dibuka lewat URL audit,
                    TIDAK dibuat baru (galat sesi, DRAFT belum tuntas, gagal kirim)
  LENGKAPI_KOORDINAT  DRAFT tanpa geotag yang koordinatnya SUDAH ada di sheet
  PERBAIKI_DATA     isian sheet ditolak form — betulkan sheet dulu, jalan ulang tidak menolong
  SINKRON_DULU      audit & server tidak sepakat -> sinkron_list.py --tulis DULU:
                    audit bilang terkirim tapi server DRAFT, ATAU dokumennya sudah ada
                    di server tapi tak tercatat (dijalankan sekarang = dokumen GANDA)
  TUNGGU_KOORDINAT  bukan galat: menunggu koordinat diisi di sheet
  MANUAL            dokumen ganda/yatim/terkunci — PPL tidak bisa menghapus dokumen
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_usaha.mesin as mg  # noqa: E402
from inti import lokasi  # noqa: E402
from inti.config import FASIH_WEB_BASE, SURVEY_ID  # noqa: E402
from antar_pc.gabung_audit import (  # noqa: E402
    _ASAL_DOKUMEN, baca_audit, baca_ganda_dihapus, baca_status_server, gabung, periksa_bentrok, ringkas_per_kunci,
)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KELUARAN_PATH = lokasi.HASIL_INPUT / "bersihkan_error.csv"
KOLOM = ["tindakan", "alasan", "sumber", "baris", "kunci", "nama_usaha", "akun_login",
         "idsubsls_input", "status", "status_server", "galat_server", "dokumen_url", "error_message"]
KOLOM.insert(3, "format")
# Tindakan yang perlu dikerjakan manusia/alat lain, bukan sekadar jalan ulang.
URUT_TINDAKAN = ["ULANGI", "LENGKAPI_KOORDINAT", "PERBAIKI_DATA", "SINKRON_DULU",
                 "TUNGGU_KOORDINAT", "MANUAL"]


def klasifikasi(rec: dict, punya_koordinat: bool | None,
                ada_di_server: bool = False) -> tuple[str, str]:
    """(tindakan, alasan) utk satu dokumen. `punya_koordinat` None = barisnya
    tidak ada di sheet yang diberikan (jadi tidak bisa dipastikan).
    `ada_di_server` = ada dokumen bernama sama di list API padahal audit tidak
    mencatat dokumen utk baris ini — menjalankan ulang akan membuat dokumen KEDUA."""
    status, srv = rec.get("status", ""), (rec.get("status_server") or "")
    kelompok = rec.get("kelompok", "")
    galat = int(rec.get("galat_server") or 0)

    if kelompok == "TERKIRIM":
        # Toast "berhasil dikirim" pernah muncul padahal server tetap DRAFT.
        if srv == "DRAFT" and status == mg.STATUS_TERKUNCI:
            # UI membuktikan dokumen read-only padahal list bilang DRAFT: PPL tidak
            # bisa mengisi maupun mengirimnya, dan mengulang cuma berputar-putar.
            return "MANUAL", ("dokumen READ-ONLY di UI padahal server bilang DRAFT — PPL tidak bisa "
                              "mengirimnya; minta admin/PML memeriksa dokumen ini")
        if srv == "DRAFT":
            return "SINKRON_DULU", f"audit '{status}' tapi server DRAFT"
        if galat:
            # Dokumen terkirim tidak bisa diedit PPL lagi (read-only).
            return "MANUAL", f"server menandai {galat} galat padahal dokumen sudah terkirim — minta PML reject dulu"
        return "", ""
    if galat and srv.upper().startswith("DRAFT"):
        return "ULANGI", f"server menandai {galat} galat (DRAFT) — isi ulang lewat URL audit"
    if status == mg.STATUS_DRAFT_TANPA_KOORDINAT:
        if punya_koordinat:
            return "LENGKAPI_KOORDINAT", "koordinat sudah ada di sheet — tinggal geotag lalu kirim"
        return "TUNGGU_KOORDINAT", "menunggu koordinat diisi di sheet (bukan galat)"
    if status.startswith("SKIP_"):
        return "PERBAIKI_DATA", f"{status} — betulkan sheet dulu, jalan ulang tidak menolong"
    if status == mg.STATUS_DIHAPUS:
        return "ULANGI", "dokumen lama dihapus admin — dokumen baru akan dibuat"
    if status in mg.STATUS_TANPA_URL_SEMUA and not rec.get("dokumen_url"):
        # JANGAN "ULANGI": dokumennya kemungkinan sudah ada di server tanpa URL
        # tercatat, jadi menjalankan ulang baris ini membuat dokumen KEDUA.
        return "SINKRON_DULU", (f"{status} — dokumen mungkin terbuat tanpa URL tercatat; "
                                "cocokkan namanya lewat sinkron_list --tulis dulu. Kalau di server "
                                "cuma ada DRAFT kosong tanpa nama, minta admin menghapusnya")
    if kelompok in ("GAGAL", "DRAFT", "DRY_RUN", "LAIN"):
        if rec.get("dokumen_url"):
            return "ULANGI", f"{status} — dokumen sudah ada, dibuka lewat URL audit & diisi ulang"
        if ada_di_server:
            # Kejadian nyata 2026-09-15 (Agenda1-1): dokumen dibuat PC lain yang
            # auditnya tidak digabung -> dijalankan lagi = dokumen KEDUA terkirim.
            return "SINKRON_DULU", (f"{status} — dokumen bernama sama SUDAH ADA di server tapi tidak "
                                    "tercatat di audit; jalankan sinkron_list --tulis dulu, kalau "
                                    "langsung dijalankan akan terbuat GANDA")
        return "ULANGI", f"{status} — dokumen belum dibuat, akan dibuat baru"
    return "", ""


def perintah(format_sumber: str, sumber: str, akun: str, subsls: str, baris: list[int],
             submit: bool = True) -> str:
    """Perintah siap jalan utk satu kelompok (akun, subsls, sheet)."""
    format_lain = "" if format_sumber == "tahap2" else f" --format {mg._nama_format(format_sumber)}"
    return (f"python input_usaha/jalankan.py --sumber {sumber}{format_lain} --akun-tunggal {akun} "
            f"--subsls-tunggal {subsls} --baris {ringkas_baris(baris)} --lewati-selesai"
            + (" --submit" if submit else ""))


def ringkas_baris(baris: list[int]) -> str:
    """[2,3,4,9] -> '2-4,9' (format --baris)."""
    urut = sorted(set(baris))
    bagian, mulai, akhir = [], None, None
    for n in urut:
        if mulai is None:
            mulai = akhir = n
        elif n == akhir + 1:
            akhir = n
        else:
            bagian.append(f"{mulai}-{akhir}" if akhir > mulai else f"{mulai}")
            mulai = akhir = n
    if mulai is not None:
        bagian.append(f"{mulai}-{akhir}" if akhir > mulai else f"{mulai}")
    return ",".join(bagian)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="append", default=[],
                    help=f"audit (default {mg.AUDIT_LOG_PATH}); boleh diulang/folder utk gabungan beberapa PC")
    ap.add_argument("--sumber", action="append", default=[],
                    help="sheet sumber; boleh diulang. Tanpa ini nomor barisnya tidak bisa dipetakan")
    mg.opsi_format(ap, "format utk --sumber (bawaan tahap2; agenda = format lama)")
    ap.add_argument("--sumber-tahap2", action="append", default=[],
                    help="sheet format tahap 2; boleh dicampur dgn --sumber dlm SATU perintah, "
                         "supaya audit yang memuat dua format tidak perlu diperiksa dua kali")
    ap.add_argument("--list-json", action="append", default=[],
                    help="list_api_<akun>.json dari sinkron_list.py (default: semua di folder ini)")
    ap.add_argument("--akun", action="append", default=[],
                    help="hanya tangani dokumen milik akun ini (boleh diulang); akun lain diabaikan")
    ap.add_argument("--dari", type=int, default=None, help="batasi ke baris sheet >= N (pembagian antar-PC)")
    ap.add_argument("--sampai", type=int, default=None, help="batasi ke baris sheet <= N")
    ap.add_argument("--hanya-galat-server", action="store_true",
                    help="hanya dokumen yang DITANDAI GALAT oleh server (sumError > 0, = kartu "
                         "'Jumlah Error' di halaman PENDATAAN). Butuh list_api_<akun>.json yang SEGAR")
    ap.add_argument("--izinkan-wilayah-beda", action="store_true",
                    help="tambahkan flag itu ke perintah yang dicetak (dokumen tersebar di beberapa "
                         "subsls wadah)")
    ap.add_argument("--keluaran", default=str(KELUARAN_PATH))
    ap.add_argument("--tanpa-submit", action="store_true", help="perintah yang dicetak tanpa --submit")
    args = ap.parse_args(argv)
    if not args.audit:
        lokasi.cek_struktur_lama()

    from antar_pc.gabung_audit import kumpulkan_sumber, label_berkas
    asal_audit = args.audit or [str(mg.AUDIT_LOG_PATH)]
    berkas = kumpulkan_sumber(asal_audit)
    try:
        gabungan, lap = gabung([(label_berkas(p, asal_audit), baca_audit(p)) for p in berkas])
    except ValueError as e:
        print(f"❌ {e}")
        return 2
    status_server, galat_server, nama_server = baca_status_server(args.list_json or [lokasi.POLA_LIST_API])
    laporan = ringkas_per_kunci(gabungan, lap["asal_per_kunci"], status_server, None, galat_server)

    # kunci -> (sheet, baris, punya_koordinat, nama dokumen, format sheet itu)
    peta: dict = {}
    for s, fmt in ([(x, args.format) for x in args.sumber]
                   + [(x, "tahap2") for x in args.sumber_tahap2]):
        rows, _hasil = mg.muat_sumber(s, fmt, mode_satu_subsls=True)
        for r in rows:
            peta[r.kunci] = (s, r.baris, r.punya_koordinat, r.nama_dokumen, fmt)

    laporan_penuh = laporan   # penyaring di bawah TIDAK boleh membuat dokumen lain tampak yatim
    if args.hanya_galat_server:
        if not galat_server:
            print("❌ --hanya-galat-server tapi tidak ada list_api_*.json — jalankan sinkron_list.py dulu.",
                  file=sys.stderr)
            return 2
        sebelum = len(laporan)
        laporan = [r for r in laporan if int(r["galat_server"] or 0) > 0]
        print(f"--hanya-galat-server: {len(laporan)} dokumen bergalat menurut server "
              f"({sebelum - len(laporan)} lainnya diabaikan).")

    hanya = {a.strip().lower() for a in args.akun}
    if hanya:
        sebelum = len(laporan)
        laporan = [r for r in laporan if (r["akun_login"] or "").lower() in hanya]
        print(f"--akun {sorted(hanya)}: {sebelum - len(laporan)} dokumen akun lain diabaikan.")

    keluar: list[dict] = []
    for rec in laporan:
        di_sheet = peta.get(rec["kunci"])
        nama = (di_sheet[3] if di_sheet else rec["nama_usaha"]) or ""
        di_server = bool(nama_server.get(" ".join(nama.split()).upper()))
        tindakan, alasan = klasifikasi(rec, di_sheet[2] if di_sheet else None, di_server)
        if not tindakan:
            continue
        keluar.append({"tindakan": tindakan, "alasan": alasan,
                       "sumber": di_sheet[0] if di_sheet else "",
                       "format": di_sheet[4] if di_sheet else "",
                       "baris": di_sheet[1] if di_sheet else rec["baris"],
                       "kunci": rec["kunci"], "nama_usaha": rec["nama_usaha"],
                       "akun_login": rec["akun_login"], "idsubsls_input": rec["idsubsls_input"],
                       "status": rec["status"], "status_server": rec["status_server"],
                       "galat_server": rec["galat_server"],
                       "dokumen_url": rec["dokumen_url"],
                       "error_message": " ".join((rec["error_message"] or "").split())[:200]})

    # Dokumen bermasalah yang TIDAK terhubung ke baris mana pun (yatim) + duplikat.
    id_audit = {rec["id_dokumen"] for rec in laporan_penuh if rec["id_dokumen"]}
    luar_audit = [i for i in (status_server or {}) if i not in id_audit]
    # Dokumen di luar audit yang sudah SUBMITTED/APPROVED bukan masalah: itu hasil
    # sheet lain / PC yang auditnya belum digabung / dokumen prelist. Yang benar-benar
    # perlu dilihat manusia cuma yang masih DRAFT — kemungkinan terbuat lalu terputus.
    yatim = [i for i in luar_audit
             if ((status_server[i] or "").upper().startswith("DRAFT") or galat_server.get(i))
             and (not hanya or (_ASAL_DOKUMEN.get(i, ("", "", ""))[0] or "").lower() in hanya)]
    lain_di_luar = len(luar_audit) - len(yatim)
    for i in yatim:
        g = galat_server.get(i) or 0
        keluar.append({"tindakan": "MANUAL", "sumber": "", "format": "", "baris": "", "kunci": "", "nama_usaha": "",
                       "akun_login": "", "idsubsls_input": "", "status": "",
                       "status_server": status_server[i], "galat_server": g,
                       "alasan": f"dokumen di server tanpa catatan audit ({status_server[i]}"
                                 + (f", {g} galat" if g else "") + ") — buka & periksa manual",
                       "dokumen_url": f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/{mg.ASSIGNMENT_ID_GABUNGAN}/{i}/entry",
                       "error_message": ""})
    bentrok = periksa_bentrok(gabungan, lap["asal_per_kunci"], baca_ganda_dihapus())
    for kunci, urls in bentrok["dokumen_ganda"].items():   # noqa: E501
        rec = next((r for r in laporan if r["kunci"] == kunci), {})
        keluar.append({"tindakan": "MANUAL", "alasan": f"dokumen GANDA di server ({len(urls)} URL) — "
                                                       "PPL tidak bisa menghapus, laporkan ke admin",
                       "sumber": (peta.get(kunci) or ("", "", ""))[0], "format": "",
                       "baris": (peta.get(kunci) or ("", rec.get("baris", ""), ""))[1],
                       "kunci": kunci, "nama_usaha": rec.get("nama_usaha", ""),
                       "akun_login": rec.get("akun_login", ""), "idsubsls_input": rec.get("idsubsls_input", ""),
                       "status": rec.get("status", ""), "status_server": rec.get("status_server", ""),
                       "galat_server": rec.get("galat_server", ""),
                       "dokumen_url": " ; ".join(urls), "error_message": ""})

    # Dokumen bernama SAMA di server (lintas akun/subsls maupun dalam satu akun).
    # Nama dokumen dipakai skrip utk mencari dokumen di list, jadi nama kembar =
    # dokumen bisa tertukar; kalau usahanya memang sama, itu duplikat yang tidak
    # bisa dihapus PPL. Tahap 2 punya banyak baris ber-8b+12a sama, jadi ini
    # DILAPORKAN utk diperiksa, bukan divonis.
    for nama, ids in sorted(nama_server.items()):
        if len(ids) < 2:
            continue
        tempat = [_ASAL_DOKUMEN.get(i, ("", "", "")) for i in ids]
        if hanya and not any((t[0] or "").lower() in hanya for t in tempat):
            continue
        lintas = len({t[0] for t in tempat}) > 1 or len({t[1] for t in tempat}) > 1
        keluar.append({
            "tindakan": "MANUAL", "sumber": "", "format": "", "baris": "", "kunci": "",
            "nama_usaha": nama[:60], "akun_login": " ; ".join(sorted({t[0] for t in tempat})),
            "idsubsls_input": " ; ".join(sorted({t[1] for t in tempat})),
            "status": "", "status_server": " ; ".join(t[2] for t in tempat), "galat_server": "",
            "alasan": (f"{len(ids)} dokumen di server bernama sama"
                       + (" DI AKUN/SUBSLS BERBEDA — kemungkinan besar duplikat lintas PC"
                          if lintas else " di satu akun — cek apakah usahanya memang berbeda")),
            "dokumen_url": " ; ".join(f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/"
                                      f"{mg.ASSIGNMENT_ID_GABUNGAN}/{i}/entry" for i in ids[:3]),
            "error_message": ""})

    if args.dari is not None or args.sampai is not None:
        # Rentang dipakai membagi pekerjaan antar-PC. Baris yang tidak ketemu di
        # sheet (baris "" ) ikut dibuang — nomor barisnya tidak bisa dipastikan.
        sebelum = len(keluar)
        keluar = [r for r in keluar
                  if r["baris"] != "" and (args.dari is None or _int(r["baris"]) >= args.dari)
                  and (args.sampai is None or _int(r["baris"]) <= args.sampai)]
        print(f"rentang baris {args.dari or 2}–{args.sampai or 'akhir'}: {len(keluar)} temuan "
              f"({sebelum - len(keluar)} di luar rentang/tanpa nomor baris diabaikan).")

    urut = {t: i for i, t in enumerate(URUT_TINDAKAN)}
    keluar.sort(key=lambda r: (urut.get(r["tindakan"], 9), str(r["sumber"]), _int(r["baris"])))

    print(f"=== {len(keluar)} dokumen/baris belum beres (dari {len(laporan)} dokumen diperiksa, "
          f"{len(laporan_penuh)} di audit) ===")
    for t, n in sorted(Counter(r["tindakan"] for r in keluar).items(), key=lambda x: urut.get(x[0], 9)):
        print(f"  {n:>5}  {t}")
    if yatim:
        print(f"         (termasuk {len(yatim)} dokumen DRAFT/bergalat di server tanpa catatan audit)")
    if status_server and lain_di_luar:
        print(f"  ({lain_di_luar} dokumen server lain di luar audit ini sudah terkirim/approved — "
              "sheet lain atau PC yang auditnya belum digabung, bukan masalah)")

    for t in URUT_TINDAKAN:
        anggota = [r for r in keluar if r["tindakan"] == t]
        if not anggota:
            continue
        print(f"\n=== {t} ({len(anggota)}) ===")
        for a, n in Counter(r["alasan"] for r in anggota).most_common(6):
            print(f"  {n:>5}  {a}")
        for r in anggota[:5]:
            print(f"     {str(r['sumber'])[:22]:22} baris {str(r['baris']):>5}  {r['nama_usaha'][:32]:32} "
                  f"{r['status']}")
        if len(anggota) > 5:
            print(f"     ... {len(anggota) - 5} lagi (lihat {args.keluaran})")

    siap = [r for r in keluar if r["tindakan"] in ("ULANGI", "LENGKAPI_KOORDINAT") and r["sumber"]]
    if siap:
        print("\n=== PERINTAH UNTUK MEMBERESKAN ===")
        print("Jalankan SATU per satu; satu akun jangan dipakai dua proses bersamaan.")
        per: dict = defaultdict(list)
        for r in siap:
            per[(r["sumber"], r["format"], r["akun_login"], r["idsubsls_input"])].append(_int(r["baris"]))
        for (sumber, fmt, akun, subsls), baris in sorted(per.items()):
            if not (akun and subsls):
                print(f"\n# {len(baris)} baris tanpa akun/subsls tercatat — tentukan sendiri: "
                      f"{ringkas_baris(baris)}")
                continue
            print(f"\n# {sumber} | {akun} | {subsls} | {len(baris)} baris")
            print(perintah(fmt, sumber, akun, subsls, baris, not args.tanpa_submit)
                  + (" --izinkan-wilayah-beda" if args.izinkan_wilayah_beda else ""))
    tanpa_sheet = [r for r in keluar if r["tindakan"] in ("ULANGI", "LENGKAPI_KOORDINAT") and not r["sumber"]]
    if tanpa_sheet:
        print(f"\n⚠️ {len(tanpa_sheet)} baris tidak ketemu di --sumber yang diberikan "
              "(sheet lain / format lain) — ulangi perintah ini dgn sheet itu.")

    if any(r["tindakan"] == "SINKRON_DULU" for r in keluar):
        print("\n=== SINKRON_DULU ===\nAudit bilang terkirim tapi server DRAFT. Perbarui audit dulu:")
        for akun in sorted({r["akun_login"] for r in keluar if r["tindakan"] == "SINKRON_DULU" and r["akun_login"]}):
            subsls = next((r["idsubsls_input"] for r in keluar
                           if r["tindakan"] == "SINKRON_DULU" and r["akun_login"] == akun), "")
            bendera = f" --format {args.format}" if args.sumber and args.format != "tahap2" else ""
            sheet = (args.sumber or args.sumber_tahap2 or ["<sheet>"])[0]
            print(f"python input_usaha/sinkron_list.py{bendera} --sumber {sheet} "
                  f"--akun-tunggal {akun} --subsls-tunggal {subsls}   # tambahkan --tulis setelah ditinjau")

    if yatim:
        print(f"\n=== DOKUMEN DRAFT DI SERVER TANPA CATATAN AUDIT ({len(yatim)}) ===")
        print("Kalau jumlahnya banyak, biasanya BUKAN yatim: dokumen itu dibuat PC lain yang "
              "auditnya belum digabung.")
        print("Gabungkan dulu audit PC itu (gabung_audit.py), baru sisanya diperiksa manual.")
        print("Tidak bisa dihapus PPL: buka URL-nya, cek isinya, lalu isi manual atau lapor admin.")
        for i in yatim[:10]:
            print(f"  {FASIH_WEB_BASE}/survey/{SURVEY_ID}/{mg.ASSIGNMENT_ID_GABUNGAN}/{i}/entry"
                  f"  ({status_server[i]})")

    with lokasi.siapkan(Path(args.keluaran)).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        w.writerows(keluar)
    print(f"\nRincian: {args.keluaran}")
    return 0


def _int(x) -> int:
    try:
        return int(str(x))
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
