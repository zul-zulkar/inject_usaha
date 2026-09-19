#!/usr/bin/env python3
"""
main.py — Orkestrasi otomatisasi input Usaha Pecahan SE2026.

⚠️ JALANKAN DI KOMPUTER YANG VPN KANTORNYA AKTIF. fasih-web.bps.go.id &
fasih-sm.bps.go.id tidak bisa diakses tanpa VPN — skrip ini TIDAK bisa
dites/dijalankan dari lingkungan cloud manapun yang tidak tersambung VPN
BPS, termasuk dari sandbox yang dipakai Claude untuk menulis kode ini.

CARA PAKAI (baca sampai habis sebelum menjalankan!)
====================================================
1. Install dependency (sekali saja):
       pip install playwright
       playwright install chromium

2. Export baris backlog dari Google Sheet ke CSV:
   File > Download > Comma Separated Values (.csv), simpan mis. sbg
   backlog.csv di folder yang sama dgn skrip ini. Lihat data_loader.py
   utk daftar nama kolom yang wajib ada.

2b. Sumber field BLOK II diambil dari file
    export/{No}_{assignment_id}.converted.json (ekspor manual per
    assignment, BUKAN live-scrape fasih-sm — lihat PANDUAN_EKSPOR_MANUAL.md
    & export_source.py). Pastikan file export sudah ada utk baris yang mau
    diproses SEBELUM menjalankan skrip ini; baris tanpa file export
    otomatis di-skip (SKIP_EXPORT_...) drpd live-scrape (yang berisiko
    deteksi bot). Kalau memang mau fallback live-scrape, tambahkan
    --allow-live-scrape secara sadar.

3. WAJIB — validasi dulu sebelum dipakai ke data baru:
       python3 main.py --csv backlog_test_3record.csv --dry-run --headed --only-no 2510,2511,2512
   Jalankan dry-run terhadap 3 record yang SUDAH diketahui hasil akhirnya
   (lihat catatan-usaha-pecahan-se2026.md di project), lalu BANDINGKAN
   manual angka yang dihasilkan skrip (ada di audit_log.csv, kolom
   *_computed) dengan angka yang sudah didokumentasikan sukses terkirim.
   Kalau ada field yang selector-nya tidak ketemu (error
   "FieldNotFound: ..."), edit STRING LABEL yang bersangkutan di
   config.py -> dict L, lalu ulangi.

4. Dry-run terhadap backlog sungguhan (TIDAK akan klik Kirim final):
       python3 main.py --csv backlog.csv --dry-run --headed --limit 5

5. Setelah dry-run beberapa record terlihat benar (GALAT=0, field2
   penting cocok), baru jalankan mode submit sungguhan utk sejumlah kecil
   dulu (mis. 3-5 record), REVIEW hasilnya di fasih-web, baru perbesar
   batch:
       python3 main.py --csv backlog.csv --submit --headed --limit 5

   --headed direkomendasikan tetap dipakai (browser terlihat) minimal
   sampai kamu percaya diri dgn hasilnya — lebih gampang menghentikan
   manual (Ctrl+C) kalau ada yang terlihat salah di layar.

KESELAMATAN
===========
- Default TANPA --submit = dry-run: skrip mengisi semua field, mengecek
  ringkasan (GALAT/PERINGATAN/KOSONG), TAPI BERHENTI SEBELUM klik Kirim
  final. Kamu harus SENGAJA menambahkan --submit utk mode live.
- GALAT harus 0 sebelum sebuah record dianggap "siap kirim" — kalau
  GALAT>0 dan bukan cuma soal Nomor Urut Bangunan (auto-fix), record
  di-skip & dicatat di audit log utk direview manual, TIDAK ditebak.
- PERINGATAN/KOSONG yang jumlahnya jauh dari pola normal (~1 peringatan,
  ~19-20 kosong) ikut di-flag di audit log sbg 'REVIEW_DISARANKAN' —
  skrip tetap lanjut (bukan hard-stop) tapi catat supaya kamu review.
- Dokumen yang SUDAH ada data terisi TIDAK PERNAH di-reload/navigate-away
  paksa oleh skrip ini (sesuai Temuan Kritis di catatan proyek) — kalau
  ada error di tengah pengisian 1 record, skrip berhenti utk record itu
  saja (log error, lanjut ke record berikutnya), BUKAN mencoba reload.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import sys
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

# -- jalankan dari root proyek; sisipkan root ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import FIXED_PASSWORD, KODEPOS_BY_IDSUBSLS
from inti.data_loader import (
    group_by_credential, load_backlog, rencana_pendapatan, rupiah10,
)
from input_fasihweb.export_source import kodepos_dari_export, load_source_blok2_from_export
from inti.fasih_web import FasihWebSession, FieldNotFound
from inti.fill_blok2 import fill_blok2, fill_catatan, fill_keterangan_pemberi_jawaban
from inti.scrape_source import scrape_source_blok2

# Konsol Windows default-nya cp1252 dan meledak (UnicodeEncodeError) begitu
# log memuat emoji/karakter non-latin1. Samakan dgn convert_manual_export.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

AUDIT_LOG_PATH = Path("./audit_log.csv")
AUDIT_FIELDS = [
    "timestamp", "no", "nama_usaha_pecahan", "kbli_pecahan", "idsubsls",
    "email_ppl", "status", "galat", "peringatan", "kosong", "catatan_count",
    "review_disarankan", "error_message",
]


def append_audit(row: dict):
    is_new = not AUDIT_LOG_PATH.exists()
    with AUDIT_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv_module.DictWriter(f, fieldnames=AUDIT_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in AUDIT_FIELDS})


STATUS_TERKIRIM = {"TERKIRIM_TERVERIFIKASI", "TERKIRIM_BELUM_TERVERIFIKASI"}
STATUS_SELESAI_DRY_RUN = STATUS_TERKIRIM | {"DRY_RUN_SIAP_KIRIM"}


def status_terakhir_per_no() -> dict:
    """{no: status} dari audit_log.csv, baris TERAKHIR yang menang.

    Dipakai --lewati-selesai. Baca ulang tiap run supaya batch yang terputus
    (mis. VPN drop) bisa dilanjutkan tanpa mengerjakan ulang yang sudah beres:
    satu record makan ~1,7 menit, jadi mengulang 40 record = 1 jam terbuang."""
    if not AUDIT_LOG_PATH.exists():
        return {}
    out: dict = {}
    with AUDIT_LOG_PATH.open(newline="", encoding="utf-8") as f:
        for baris in csv_module.DictReader(f):
            no = (baris.get("no") or "").strip()
            if no:
                out[no] = (baris.get("status") or "").strip()
    return out


def process_one_row(sess: FasihWebSession, row, dry_run: bool, allow_live_scrape: bool = False) -> dict:
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "no": row.no, "nama_usaha_pecahan": row.nama_usaha_pecahan,
        "kbli_pecahan": row.kbli_pecahan, "idsubsls": row.idsubsls,
        "email_ppl": row.email_ppl, "status": "GAGAL", "galat": "",
        "peringatan": "", "kosong": "", "catatan_count": "",
        "review_disarankan": "", "error_message": "",
    }

    # Kodepos: config yang DIKURASI menang, export cuma cadangan.
    # Urutan ini penting — export bisa kotor (ada keluarga yang mengisi
    # "99999"), sedangkan config sudah ditinjau manusia. Cadangan export
    # tetap layak dipercaya: 41 dari 41 entri config cocok persis dgn export
    # (dicek 2026-09-07), dan nilainya diambil mayoritas per-desa.
    kodepos = KODEPOS_BY_IDSUBSLS.get(row.idsubsls)
    if not kodepos:
        kodepos, ket = kodepos_dari_export(row.idsubsls)
        if kodepos:
            sess._log(
                f"kodepos {kodepos} diambil dari file export ({ket}) — idsubsls "
                f"{row.idsubsls} belum terdaftar di config.KODEPOS_BY_IDSUBSLS."
            )
    if not kodepos:
        result["status"] = "SKIP_KODEPOS_TIDAK_DIKETAHUI"
        result["error_message"] = (
            f"idsubsls {row.idsubsls} tidak ada di config.py -> KODEPOS_BY_IDSUBSLS "
            "maupun di file export mentah. Lengkapi dulu drpd menebak field wajib ini."
        )
        return result

    try:
        # 1. Sumber BLOK II — UTAMA: file export/{No}_{assignment_id}.converted.json
        #    hasil ekspor manual (lihat PANDUAN_EKSPOR_MANUAL.md). Live-scrape
        #    fasih-sm cuma dipakai kalau --allow-live-scrape SENGAJA diaktifkan
        #    (berisiko deteksi bot).
        lookup = load_source_blok2_from_export(row.no, row.row_assignment_id, row.nama_usaha_di_keluarga)
        if lookup.status == "OK":
            src = lookup.src
            sess._log(f"Sumber BLOK II dari export (match={lookup.match_score:.2f}, usaha='{lookup.usaha_terpilih}').")
            if src.catatan_scrape:
                sess._log(f"Catatan sumber (export): {src.catatan_scrape}")
        elif allow_live_scrape:
            sess._log(f"Export tidak dipakai ({lookup.status}: {lookup.detail}) -> fallback live-scrape fasih-sm.")
            src = scrape_source_blok2(sess.page, row.survey_assignment_id, row.row_assignment_id)
            if src.catatan_scrape:
                sess._log(f"⚠️ Sebagian field sumber tidak ke-scrape: {src.catatan_scrape}")
        else:
            result["status"] = f"SKIP_EXPORT_{lookup.status}"
            result["error_message"] = (
                f"export/{row.no}_{row.row_assignment_id}.converted.json -> {lookup.status}. {lookup.detail} "
                "Jalankan dgn --allow-live-scrape kalau mau fallback ke scrape_source.py (berisiko deteksi bot "
                "fasih-sm), atau lengkapi/perbaiki data export dulu (lihat PANDUAN_EKSPOR_MANUAL.md)."
            )
            return result

        # 2. Buat & buka dokumen baru di fasih-web
        if not sess.create_document(row.survey_assignment_id, row.idsubsls, row.nama_usaha_pecahan):
            # Paling sering: wilayah/SLS tujuan belum punya assignment di
            # fasih-web sehingga dokumen tidak bisa dibuat dari skrip.
            # Bukan error kode — cukup buat dokumennya manual lalu ulangi.
            result["status"] = "SKIP_DOKUMEN_BELUM_ADA"
            result["error_message"] = (
                f"Dokumen '{row.nama_usaha_pecahan}' belum ada & gagal dibuat otomatis "
                f"(idsubsls {row.idsubsls}). Buat dokumennya manual di fasih-web, "
                "lalu jalankan ulang baris ini."
            )
            return result
        sess.open_entry_for(row.nama_usaha_pecahan, row.survey_assignment_id, allow_retry_if_fresh=True)

        # 3. PENGANTAR (Waktu Mulai) — halaman pertama setelah Entri. WAJIB
        #    diisi lebih dulu: section berikutnya baru ter-enable setelah ini.
        sess.fill_pengantar()

        # 3b. Pindah ke section berikutnya. Form-engine fasih-web HANYA
        #     merender section yang sedang aktif — field section lain benar2
        #     tidak ada di DOM, jadi tanpa langkah ini pengisian PASTI
        #     FieldNotFound.
        if not sess.next_section():
            raise FieldNotFound(
                "Section setelah PENGANTAR tidak ter-enable — tombol 'Berikutnya' tidak "
                f"dirender. Section tersedia: {sess.list_sections()}"
            )

        # 3c. BLOK I. IDENTITAS WILAYAH — ternyata section KEDUA, langsung
        #     setelah PENGANTAR (terverifikasi via --dump-dom). Rincian 1-7
        #     sudah auto-terisi; kita cuma mengisi rincian 8 & 10.
        sess.fill_identitas_wilayah(kodepos)

        # 3d. Lanjut ke section berikutnya (SE2026-P).
        if not sess.next_section():
            raise FieldNotFound(
                "Section setelah IDENTITAS WILAYAH tidak ter-enable. "
                f"Section tersedia: {sess.list_sections()}"
            )

        # 4. SE2026-P (alamat dari nama_usaha_di_keluarga sumber sbg fallback nama jalan
        #    kalau tidak ada kolom alamat terpisah — SESUAIKAN kalau sheet-mu
        #    punya kolom alamat/nama jalan sendiri).
        # Alamat TIDAK ada di CSV backlog — sumbernya export fasih-sm
        # (SourceBlok2.alamat_nama_jalan, dari dataKey alamat_usaha_view).
        # Kalau kosong, JANGAN tulis placeholder ke record resmi: skip saja.
        nama_jalan = (src.alamat_nama_jalan or "").strip()
        if not nama_jalan:
            result["status"] = "SKIP_ALAMAT_KOSONG"
            result["error_message"] = (
                "alamat_nama_jalan kosong di export — field 'Nama Jalan/Gang/Komplek' wajib "
                "dan tidak boleh ditebak. Lengkapi export/konfirmasi ke petugas dulu."
            )
            return result
        sess.fill_se2026_p(
            nama_usaha=row.nama_usaha_pecahan,
            nama_jalan=nama_jalan,
            # Hint field-nya: "Jika tidak ada nomor rumah, tulis strip (-)".
            blok_nomor=(row.raw.get("blok_nomor") or "").strip() or "-",
        )
        sess.do_geotagging(row.latitude, row.longitude)
        sess.save()

        # 4b. Pindah ke section BLOK II. Form-engine hanya merender section
        #     aktif, jadi ini wajib sebelum fill_blok2().
        if not sess.next_section():
            raise FieldNotFound(
                "Section setelah SE2026-P tidak ter-enable. "
                f"Section tersedia: {sess.list_sections()}"
            )

        # 4c. BLOK II berisi komponen NESTED ("Keterangan Usaha/Perusahaan").
        #     Field detailnya baru ter-render setelah kartunya diklik.
        sess.buka_nested(0)

        # 5. BLOK II
        fill_blok2(sess, row, src, kbli_name_hint=row.raw.get("nama_kategori_kbli", ""))
        sess.save()

        # 5b. Keluar dari detail nested BLOK II. next_section() dari dalam
        #     nested justru kembali ke induknya, jadi lompat lewat sidebar.
        if not sess.goto_section("KETERANGAN PEMBERI JAWABAN"):
            raise FieldNotFound(
                "Section KETERANGAN PEMBERI JAWABAN tidak ter-enable. "
                f"Section tersedia: {sess.list_sections()}"
            )

        # 6. Keterangan pemberi jawaban + catatan
        fill_keterangan_pemberi_jawaban(sess)
        if not sess.goto_section("CATATAN"):
            raise FieldNotFound(f"Section CATATAN tidak ter-enable. Tersedia: {sess.list_sections()}")
        fill_catatan(sess)
        sess.save()

        # 7. Ringkasan
        ring = sess.check_ringkasan()
        if ring.galat > 0:
            detail = sess.read_galat_detail()
            if "Nomor Urut Bangunan" in detail and detail.count("\n") <= 3:
                # Auto-fix HANYA kalau satu2nya galat memang field ini.
                sess.close_ringkasan_dialog()
                sess.fix_nomor_urut_bangunan_if_needed()
                sess.save()
                ring = sess.check_ringkasan()
            else:
                result["status"] = "SKIP_GALAT_PERLU_REVIEW"
                result["galat"], result["peringatan"], result["kosong"] = ring.galat, ring.peringatan, ring.kosong
                # Daftar GALAT ditulis UTUH (dulu dipotong 300 char, akibatnya
                # galat ke-5 dst tidak pernah kelihatan di audit_log).
                result["error_message"] = f"GALAT selain Nomor Urut Bangunan: {detail}"
                sess.close_ringkasan_dialog()
                # Dump DOM section yang bermasalah tanpa menunggu --dump-dom:
                # tanpa ini, mendiagnosa field baru butuh mengulang 1 run live.
                # Dialog ringkasan HARUS benar-benar tertutup dulu — kalau
                # tidak, yang ke-dump cuma isi dialognya (kejadian 2026-09-07
                # di record 2545/2546: dump-nya tidak memuat satu pun field).
                try:
                    sess.page.keyboard.press("Escape")
                    sess.page.wait_for_selector('[role="dialog"]', state="hidden", timeout=8_000)
                except Exception:
                    pass
                sess.page.wait_for_timeout(800)
                sess.dump(f"GALAT_{row.no}_blok2", paksa=True)
                try:
                    sess.goto_section("SE2026 - P")
                    sess.dump(f"GALAT_{row.no}_se2026p", paksa=True)
                except Exception:
                    pass
                return result

        result["galat"], result["peringatan"] = ring.galat, ring.peringatan
        result["catatan_count"], result["kosong"] = ring.catatan, ring.kosong
        tanda = []
        if ring.peringatan > 2 or ring.kosong > 22 or ring.kosong < 17:
            tanda.append("jumlah peringatan/kosong menyimpang dari pola normal (~1 / ~19-20)")
        # Baris yang angkanya DINAIKKAN ke minimal 100.000 tidak lagi bernilai
        # 10% dari sumber — itu ketetapan user, tapi harus kelihatan di audit
        # supaya bisa ditinjau, bukan lewat begitu saja.
        if rencana_pendapatan(row).ditambah > 0:
            tanda.append("27a DINAIKKAN ke minimal 100.000 (bukan lagi 10% sumber)")
        total26 = sum(rupiah10(v) for v in (
            row.gaji, row.biaya_produksi, row.biaya_pembelian,
            row.operasional, row.non_operasional))
        if total26 < 100_000:
            tanda.append("26 DINAIKKAN ke minimal 100.000 (bukan lagi 10% sumber)")
        # Asumsi yang dipakai karena export-nya kosong — harus terlihat.
        if not (src.b1_produksi_lokasi or src.b2_layanan_makan_minum or src.b3_penjualan_barang):
            tanda.append("13b1/b2/b3 pakai DEFAULT (export kosong) — ASUMSI")
        if (src.izin_edar_bpom or "").strip().startswith("1") and not src.varian_sudah_bpom:
            tanda.append("20b pakai DEFAULT (export kosong) — ASUMSI")
        if tanda:
            result["review_disarankan"] = "YA — " + "; ".join(tanda)

        if ring.galat != 0:
            result["status"] = "SKIP_GALAT_TIDAK_TERATASI"
            sess.close_ringkasan_dialog()
            return result

        if dry_run:
            result["status"] = "DRY_RUN_SIAP_KIRIM"
            sess.close_ringkasan_dialog()
            return result

        # 7. Submit sungguhan (hanya kalau --submit)
        submitted = sess.submit_final()
        verified = sess.verify_submitted_in_list(row.survey_assignment_id, row.nama_usaha_pecahan)
        result["status"] = "TERKIRIM_TERVERIFIKASI" if verified else (
            "TERKIRIM_BELUM_TERVERIFIKASI" if submitted else "SUBMIT_GAGAL"
        )
        return result

    except FieldNotFound as e:
        result["status"] = "ERROR_FIELD_NOT_FOUND"
        result["error_message"] = str(e)
        return result
    except Exception as e:  # noqa: BLE001 — sengaja luas, 1 record gagal jangan hentikan batch
        result["status"] = "ERROR_TAK_TERDUGA"
        # Traceback WAJIB ikut. Tanpa ini pesan seperti "OSError: [Errno 22]
        # Invalid argument" (record 2528, 2026-09-07) tidak bisa dilacak sama
        # sekali — tidak ketahuan baris mana yang meledak.
        jejak = " ~ ".join(traceback.format_exc().splitlines())
        result["error_message"] = f"{type(e).__name__}: {e} || {jejak[-900:]}"
        try:
            sess._shot(f"ERROR_{row.no}_{type(e).__name__}")
        except Exception:
            pass
        return result


def main():
    ap = argparse.ArgumentParser(description="Otomatisasi input Usaha Pecahan SE2026")
    ap.add_argument("--csv", required=True, help="Path CSV hasil export sheet backlog")
    ap.add_argument("--submit", action="store_true", help="Mode LIVE — benar2 klik Kirim. Default: dry-run.")
    ap.add_argument("--headed", action="store_true", default=True, help="Tampilkan browser (default: True, direkomendasikan)")
    ap.add_argument("--headless", action="store_true",
                    help="JANGAN DIPAKAI. fasih-web menolak browser headless dgn halaman "
                         "anti-bot; flag ini sengaja dibiarkan ada agar penolakannya "
                         "eksplisit, bukan jadi kegagalan misterius.")
    ap.add_argument("--limit", type=int, default=None, help="Batasi jumlah baris diproses (utk uji coba)")
    ap.add_argument("--only-no", type=str, default=None, help="Proses hanya baris dgn kolom No tertentu, pisah koma (mis. 2510,2511,2512)")
    ap.add_argument(
        "--dump-dom", action="store_true",
        help="Simpan peta komponen (dataKey -> jenis input + label) & HTML section aktif ke "
        "./log_screenshots/*.map.tsv setiap pindah section / saat gagal. Dipakai utk memetakan "
        "dataKey section yang selektornya belum diketahui. Ingat: form-engine cuma merender "
        "section AKTIF, jadi 1 file dump = 1 section.",
    )
    ap.add_argument(
        "--lewati-selesai", action="store_true",
        help="Lewati baris yang di audit_log.csv sudah selesai. Di dry-run: status "
        "DRY_RUN_SIAP_KIRIM atau TERKIRIM_*. Di --submit: hanya TERKIRIM_*. Dipakai utk "
        "melanjutkan batch yang terputus tanpa mengulang dari nol.",
    )
    ap.add_argument(
        "--allow-live-scrape", action="store_true",
        help="Fallback ke scrape_source.py (live scrape fasih-sm, BERISIKO deteksi bot) kalau file "
        "export/{No}_{assignment_id}.converted.json tidak ketemu/tidak cocok. Default: skip record itu "
        "(SKIP_EXPORT_...) drpd live-scrape otomatis.",
    )
    args = ap.parse_args()

    dry_run = not args.submit
    # ⚠️ HEADLESS DILARANG. Diuji langsung 2026-09-07: dgn headless=True,
    # https://fasih-web.bps.go.id/login tidak merender form login sama sekali,
    # melainkan halaman tantangan anti-bot ("Kami mendeteksi perilaku yang
    # tidak wajar pada perangkat anda..."). Headed di mesin & VPN yang sama
    # normal. Sebelumnya flag ini tidak pernah berefek (bug: --headed
    # default True bikin `args.headless and not args.headed` selalu False),
    # jadi baru ketahuan begitu bug itu dibetulkan — dan langsung menghasilkan
    # 42 login gagal beruntun. Menabrak halaman anti-bot berulang kali juga
    # bukan hal yang pantas dilakukan ke sistem kantor.
    if args.headless:
        print(
            "❌ --headless tidak didukung: fasih-web membalas browser headless dgn halaman "
            "anti-bot, sehingga SEMUA login gagal. Jalankan tanpa flag itu (mode headed).",
            file=sys.stderr,
        )
        return
    headless = False

    rows = load_backlog(args.csv, only_ready=True)
    if args.only_no:
        wanted = {s.strip() for s in args.only_no.split(",")}
        rows = [r for r in rows if r.no in wanted]
    if args.lewati_selesai:
        sudah = status_terakhir_per_no()
        tuntas = STATUS_TERKIRIM if args.submit else STATUS_SELESAI_DRY_RUN
        sebelum = len(rows)
        rows = [r for r in rows if sudah.get(r.no) not in tuntas]
        print(f"--lewati-selesai: {sebelum - len(rows)} baris dilewati (sudah selesai di audit_log.csv).")
    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        print("Tidak ada baris siap diproses (kolom nama_usaha_pecahan & kbli_pecahan harus terisi).")
        return

    print(f"{'DRY-RUN' if dry_run else '⚠️ MODE LIVE — akan klik Kirim final'} — {len(rows)} baris akan diproses.")
    if not dry_run:
        confirm = input(f"Ketik 'YA' utk konfirmasi submit {len(rows)} dokumen SUNGGUHAN (irreversible): ")
        if confirm.strip().upper() != "YA":
            print("Dibatalkan.")
            return

    groups = group_by_credential(rows)
    print(f"Dikelompokkan jadi {len(groups)} sesi login (per email PPL + assignment).")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        for (email, survey_assignment_id), group_rows in groups.items():
            if not email or not survey_assignment_id:
                for row in group_rows:
                    append_audit({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "no": row.no,
                        "nama_usaha_pecahan": row.nama_usaha_pecahan, "status": "SKIP_KREDENSIAL_TIDAK_LENGKAP",
                        "error_message": f"email_ppl='{email}' survey_assignment_id='{survey_assignment_id}'",
                    })
                continue

            # Context BARU per (PPL, assignment) = cookie & storage kosong,
            # jadi pergantian akun tidak mewarisi sesi SSO akun sebelumnya.
            # Pengaman kedua ada di FasihWebSession.login() yang memverifikasi
            # akun yang benar-benar aktif (lihat catatan di fasih_web.py).
            context = browser.new_context()
            page = context.new_page()
            sess = FasihWebSession(page, dump_dom=args.dump_dom)
            try:
                sess.login(email, FIXED_PASSWORD)
            except Exception as e:
                print(f"❌ Login gagal utk {email}: {e}")
                for row in group_rows:
                    append_audit({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "no": row.no,
                        "nama_usaha_pecahan": row.nama_usaha_pecahan,
                        "email_ppl": email,
                        "status": "ERROR_AKUN_SALAH" if "AKUN SALAH" in str(e) else "ERROR_LOGIN",
                        "error_message": str(e),
                    })
                try:
                    sess.logout()
                except Exception:
                    pass
                context.close()
                continue

            for row in group_rows:
                print(f"\n=== No {row.no} — {row.nama_usaha_pecahan} ({row.kbli_pecahan}) ===")
                res = process_one_row(sess, row, dry_run, args.allow_live_scrape)
                # Jejak audit kalau pengaman akun sedang tidak bisa bekerja.
                # Risikonya rendah (tiap grup dapat context baru = cookie
                # kosong, jadi tidak mungkin mewarisi sesi akun lain), tapi
                # harus KELIHATAN di audit, bukan cuma lewat di layar.
                if not sess.akun_api.get("email"):
                    res["review_disarankan"] = " | ".join(filter(None, [
                        res.get("review_disarankan"),
                        "AKUN TIDAK TERVERIFIKASI — cocokkan manual dgn Nama PPL di sheet",
                    ]))
                append_audit(res)
                print(f"  -> {res['status']}" + (f" ({res['error_message']})" if res["error_message"] else ""))

            # Logout eksplisit sebelum context ditutup. Menutup context memang
            # sudah membuang cookie-nya, tapi logout resmi bikin sesi di sisi
            # SERVER ikut berakhir — ini yang bikin login akun berikutnya (juga
            # di browser biasa milik user) tidak nyangkut di akun lama.
            try:
                sess.logout()
            except Exception as e:
                print(f"⚠️ Logout {email} gagal (tidak fatal): {e}")
            context.close()

        browser.close()

    print(f"\nSelesai. Lihat {AUDIT_LOG_PATH} utk audit trail lengkap.")


if __name__ == "__main__":
    main()
