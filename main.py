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
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import FIXED_PASSWORD, KODEPOS_BY_IDSUBSLS
from data_loader import group_by_credential, load_backlog
from fasih_web import FasihWebSession, FieldNotFound
from fill_blok2 import fill_blok2, fill_catatan, fill_keterangan_pemberi_jawaban
from scrape_source import scrape_source_blok2

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


def process_one_row(sess: FasihWebSession, row, dry_run: bool) -> dict:
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "no": row.no, "nama_usaha_pecahan": row.nama_usaha_pecahan,
        "kbli_pecahan": row.kbli_pecahan, "idsubsls": row.idsubsls,
        "email_ppl": row.email_ppl, "status": "GAGAL", "galat": "",
        "peringatan": "", "kosong": "", "catatan_count": "",
        "review_disarankan": "", "error_message": "",
    }

    kodepos = KODEPOS_BY_IDSUBSLS.get(row.idsubsls)
    if not kodepos:
        result["status"] = "SKIP_KODEPOS_TIDAK_DIKETAHUI"
        result["error_message"] = (
            f"idsubsls {row.idsubsls} belum ada di config.py -> KODEPOS_BY_IDSUBSLS. "
            "Tambahkan dulu drpd menebak field wajib ini."
        )
        return result

    try:
        # 1. Scrape sumber dari fasih-sm
        src = scrape_source_blok2(sess.page, row.survey_assignment_id, row.row_assignment_id)
        if src.catatan_scrape:
            sess._log(f"⚠️ Sebagian field sumber tidak ke-scrape: {src.catatan_scrape}")

        # 2. Buat & buka dokumen baru di fasih-web
        sess.create_document(row.survey_assignment_id, row.idsubsls, row.nama_usaha_pecahan)
        sess.open_entry_for(row.nama_usaha_pecahan, row.survey_assignment_id, allow_retry_if_fresh=True)

        # 3. SE2026-P (alamat dari nama_usaha_di_keluarga sumber sbg fallback nama jalan
        #    kalau tidak ada kolom alamat terpisah — SESUAIKAN kalau sheet-mu
        #    punya kolom alamat/nama jalan sendiri).
        nama_jalan = src.nama_komersial and "" or ""  # placeholder — lihat catatan di bawah
        sess.fill_se2026_p(
            nama_usaha=row.nama_usaha_pecahan,
            nama_jalan=row.raw.get("nama_jalan", "") or "ISI MANUAL - kolom nama_jalan tidak ada di sheet",
        )
        sess.fill_identitas_wilayah_extra(kodepos)
        sess.do_geotagging(row.latitude, row.longitude)
        sess.save()

        # 4. BLOK II
        fill_blok2(sess, row, src, kbli_name_hint=row.raw.get("nama_kategori_kbli", ""))
        sess.save()

        # 5. Keterangan pemberi jawaban + catatan
        fill_keterangan_pemberi_jawaban(sess)
        fill_catatan(sess)
        sess.save()

        # 6. Ringkasan
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
                result["error_message"] = f"GALAT selain Nomor Urut Bangunan: {detail[:300]}"
                sess.close_ringkasan_dialog()
                return result

        result["galat"], result["peringatan"] = ring.galat, ring.peringatan
        result["catatan_count"], result["kosong"] = ring.catatan, ring.kosong
        if ring.peringatan > 2 or ring.kosong > 22 or ring.kosong < 17:
            result["review_disarankan"] = "YA — jumlah peringatan/kosong menyimpang dari pola normal (~1 / ~19-20)"

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
        result["error_message"] = f"{type(e).__name__}: {e}"
        return result


def main():
    ap = argparse.ArgumentParser(description="Otomatisasi input Usaha Pecahan SE2026")
    ap.add_argument("--csv", required=True, help="Path CSV hasil export sheet backlog")
    ap.add_argument("--submit", action="store_true", help="Mode LIVE — benar2 klik Kirim. Default: dry-run.")
    ap.add_argument("--headed", action="store_true", default=True, help="Tampilkan browser (default: True, direkomendasikan)")
    ap.add_argument("--headless", action="store_true", help="Sembunyikan browser (override --headed)")
    ap.add_argument("--limit", type=int, default=None, help="Batasi jumlah baris diproses (utk uji coba)")
    ap.add_argument("--only-no", type=str, default=None, help="Proses hanya baris dgn kolom No tertentu, pisah koma (mis. 2510,2511,2512)")
    args = ap.parse_args()

    dry_run = not args.submit
    headless = args.headless and not args.headed

    rows = load_backlog(args.csv, only_ready=True)
    if args.only_no:
        wanted = {s.strip() for s in args.only_no.split(",")}
        rows = [r for r in rows if r.no in wanted]
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

            context = browser.new_context()
            page = context.new_page()
            sess = FasihWebSession(page)
            try:
                sess.login(email, FIXED_PASSWORD)
            except Exception as e:
                print(f"❌ Login gagal utk {email}: {e}")
                for row in group_rows:
                    append_audit({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "no": row.no,
                        "nama_usaha_pecahan": row.nama_usaha_pecahan, "status": "ERROR_LOGIN",
                        "error_message": str(e),
                    })
                context.close()
                continue

            for row in group_rows:
                print(f"\n=== No {row.no} — {row.nama_usaha_pecahan} ({row.kbli_pecahan}) ===")
                res = process_one_row(sess, row, dry_run)
                append_audit(res)
                print(f"  -> {res['status']}" + (f" ({res['error_message']})" if res["error_message"] else ""))

            context.close()

        browser.close()

    print(f"\nSelesai. Lihat {AUDIT_LOG_PATH} utk audit trail lengkap.")


if __name__ == "__main__":
    main()
