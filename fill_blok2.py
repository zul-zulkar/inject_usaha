"""
fill_blok2.py — Pemetaan data (BacklogRow + SourceBlok2 hasil scrape) ke
field-field SE2026-L BLOK II di fasih-web, termasuk semua logika kondisional
yg terdokumentasi (26c/rincian 20 tergantung kategori KBLI HASIL PILIHAN,
bukan kategori sumber — dideteksi dari DOM, bukan ditebak dari tabel).

⚠️ CATATAN PENTING SOAL SUMBER ANGKA rincian 28b & rincian 29:
- 28b (aset selain tanah&bangunan) diasumsikan = kolom sheet
  'aset_lain_thn' × 10%. Pemetaan ini BELUM pernah eksplisit dikonfirmasi
  di 3 record manual (nilainya cocok scr kebetulan/logis, tapi TIDAK
  divalidasi silang saat itu). WAJIB divalidasi: jalankan script dgn
  --dry-run terhadap salah satu dari 3 record yang SUDAH diketahui hasil
  akhirnya (lihat catatan-usaha-pecahan-se2026.md), lalu bandingkan angka
  yg dihasilkan script vs angka yg didokumentasikan.
- 29 (kepemilikan modal) di 3 sample SELALU 100% Pribadi/Perorangan, dan
  TIDAK ADA kolom sumber di sheet utk field ini -> dipakai sbg default
  tetap. Kalau ternyata source fasih-sm juga expose field ini, sebaiknya
  di-scrape drpd diasumsikan konstan (lihat TODO di scrape_source.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Page

from config import (
    ASET_TANAH_OVERRIDE, KEPEMILIKAN_MODAL_DEFAULT, LUAS_TANAH_OVERRIDE,
    L, NIK_OVERRIDE, UMKM_SATU_SLS,
)
from data_loader import BacklogRow, rupiah10, sum_rupiah10
from fasih_web import FasihWebSession
from scrape_source import SourceBlok2


def field_present(page: Page, label_substr: str, timeout: int = 2500) -> bool:
    """Deteksi DOM: apakah sebuah field/label benar2 dirender di halaman
    SEKARANG. Dipakai utk 26c, rincian 20, dll — TIDAK menebak dari
    kategori KBLI, karena mapping kategori->field belum tentu lengkap."""
    try:
        page.get_by_text(re.compile(re.escape(label_substr), re.I)).first.wait_for(
            state="visible", timeout=timeout
        )
        return True
    except Exception:
        return False


def read_kategori_lapangan_usaha(page: Page) -> str:
    """Baca field readonly '13.h Kategori Lapangan Usaha' (auto-terisi
    begitu KBLI dipilih) — dipakai sbg SINYAL tambahan, bukan satu2nya
    dasar keputusan (deteksi utama tetap field_present di atas)."""
    try:
        lbl = page.get_by_text(L["kategori_lapangan_usaha"], exact=False).first
        val_el = lbl.locator("xpath=following::input[1]")
        return (val_el.input_value() or "").strip()
    except Exception:
        return ""


def fill_blok2(sess: FasihWebSession, row: BacklogRow, src: SourceBlok2, kbli_name_hint: str = ""):
    page = sess.page
    log = sess._log

    log("Isi BLOK II ...")

    # --- Identitas usaha ---
    sess.select_radio("umkm_satu_sls", UMKM_SATU_SLS)
    sess.select_radio("keberadaan_usaha", L["opsi_baru"])
    sess.fill_text("nama_komersial", src.nama_komersial or row.nama_usaha_di_keluarga)

    # 8c Alamat: NAMA JALAN biasanya sudah auto-terisi dari SE2026-P — cukup
    # lengkapi RT/RW/No HP kalau field masih editable & belum terisi.
    if src.rt:
        sess.fill_text("rt", src.rt)
    if src.rw:
        sess.fill_text("rw", src.rw)
    if src.no_hp_wa:
        sess.fill_text("no_hp_wa", src.no_hp_wa)

    sess.select_radio("jenis_kawasan", L["opsi_luar_kawasan"])

    # rincian 9 (Jenis usaha) HANYA muncul di alur "Keluarga", TIDAK muncul
    # di alur "Bangunan Lainnya" yg dipakai skrip ini (terverifikasi di 3
    # record manual) — sengaja tidak diisi.

    sess.select_radio("nib", "2. Tidak")
    sess.select_radio("alasan_tanpa_nib", "3. Tidak memerlukan NIB")
    sess.select_radio("status_badan_usaha", L["opsi_bukan_badan_usaha"])
    sess.select_radio("laporan_keuangan", "2. Tidak")

    # 12a — SALIN PERSIS dari field sumber (BUKAN dari roster/kolom P kalau beda ejaan)
    sess.fill_text("nama_pengusaha", src.nama_pengusaha or row.nama_usaha_di_keluarga)
    if src.jenis_kelamin:
        sess.select_radio("jenis_kelamin", src.jenis_kelamin)
    if src.umur:
        sess.fill_text("umur", src.umur)
    sess.fill_text("nik", NIK_OVERRIDE)  # override tetap, abaikan sumber

    sess.fill_text("kegiatan_utama", src.kegiatan_utama)
    for key, val in (
        ("produksi_di_lokasi", src.b1_produksi_lokasi),
        ("layanan_makan_minum", src.b2_layanan_makan_minum),
        ("penjualan_barang", src.b3_penjualan_barang),
    ):
        if val:
            sess.select_radio(key, val)
    if src.tempat_usaha:
        sess.select_radio("tempat_usaha", src.tempat_usaha)
    sess.fill_text("produk_utama", src.produk_utama)

    # --- 13g KBLI (Master KBLI, dgn retry logic) ---
    sess.fill_kbli_master(row.kbli_pecahan.strip(), search_phrase_fallback=kbli_name_hint)
    page.wait_for_timeout(500)
    kategori = read_kategori_lapangan_usaha(page)
    log(f"13h Kategori Lapangan Usaha (auto) = '{kategori}'")

    sess.select_radio("jaringan_usaha", src.jaringan_usaha or L["opsi_tunggal"])

    if src.pakai_internet:
        sess.select_radio("pakai_internet", src.pakai_internet)
    if src.produk_ramah_lingkungan:
        sess.select_radio("produk_ramah_lingkungan", src.produk_ramah_lingkungan)
    if src.input_ramah_lingkungan:
        sess.select_radio("input_ramah_lingkungan", src.input_ramah_lingkungan)
    if src.karya_seni_budaya:
        sess.select_radio("karya_seni_budaya", src.karya_seni_budaya)

    # --- rincian 20 (BPOM) — kondisional, deteksi dari DOM ---
    if field_present(page, "izin edar"):
        bpom_val = src.izin_edar_bpom or "3. Tidak"
        sess.select_radio("izin_edar_bpom", bpom_val)
        if bpom_val.strip().startswith("3"):
            # 20c TETAP wajib diisi walau 20a="Tidak" (temuan termodokumentasi)
            sess.fill_text("jumlah_varian_belum_bpom", "1")
    else:
        log("Rincian 20 (BPOM) tidak muncul di form utk kategori ini — dilewati.")

    sess.select_radio("mitra_kdkmp", src.mitra_kdkmp or "2. Tidak")
    sess.select_radio("program_mbg", src.program_mbg or "5. Tidak terlibat MBG")

    for key in ("transaksi_bukan_penduduk",):
        pass  # 23a/23b/23c — di 3 sample selalu "2. Tidak" x3, isi manual di bawah:
    for label_hint in ("23", "bukan penduduk Indonesia"):
        pass
    # 23a/23b/23c: tiga radio group terpisah tapi teksnya mirip. Diisi
    # berurutan "2. Tidak" — kalau di source fasih-sm ada bedanya per
    # sub-pertanyaan, sesuaikan di sini dgn field terpisah dari SourceBlok2.
    try:
        blocks = page.get_by_text(re.compile("bukan penduduk Indonesia", re.I))
        for i in range(min(blocks.count(), 3)):
            container = blocks.nth(i).locator("xpath=ancestor::*[self::div or self::fieldset][1]")
            container.get_by_text("2. Tidak", exact=False).first.click()
    except Exception:
        log("⚠️ 23a/23b/23c tidak terisi otomatis — cek manual.")

    # --- 24 pekerja ---
    if src.pekerja_laki2_dibayar:
        sess.fill_text("pekerja_laki2_dibayar", src.pekerja_laki2_dibayar)
    # 24b1/24a2/24b2 idealnya juga dari SourceBlok2 kalau tersedia — saat
    # ini scrape_source.py belum melengkapi semuanya, isi manual/cek dulu.

    if src.tahun_mulai_komersial:
        sess.fill_text("tahun_mulai_komersial", src.tahun_mulai_komersial)

    # --- rincian 26 (Pengeluaran) — kondisional 26c ---
    has_26c = field_present(page, "biaya pembelian")
    biaya_produksi_10 = rupiah10(row.biaya_produksi)
    biaya_pembelian_10 = rupiah10(row.biaya_pembelian)
    sess.fill_text("upah_gaji", str(rupiah10(row.gaji)))
    if has_26c:
        sess.fill_text("biaya_produksi", str(biaya_produksi_10))
        sess.fill_text("biaya_pembelian", str(biaya_pembelian_10))
        log("26c terdeteksi di DOM -> mapping normal (26b & 26c terpisah).")
    else:
        gabung = sum_rupiah10(row.biaya_produksi, row.biaya_pembelian)
        sess.fill_text("biaya_produksi", str(gabung))
        log(f"26c TIDAK terdeteksi di DOM -> gabung biaya_produksi+biaya_pembelian ke 26b = {gabung}.")
    sess.fill_text("operasional_26d", str(rupiah10(row.operasional)))
    sess.fill_text("non_operasional_26e", str(rupiah10(row.non_operasional)))

    # --- rincian 27 (Pendapatan) ---
    sess.fill_text("nilai_penjualan", str(rupiah10(row.nilai_pendapatan)))
    sess.fill_text("pendapatan_lain", str(rupiah10(row.pendapatan_lain)))

    # --- rincian 28 (Aset) ---
    sess.fill_text("aset_tanah_bangunan", ASET_TANAH_OVERRIDE)
    sess.fill_text("aset_selain_tanah", str(rupiah10(row.aset_lain_thn)))  # ⚠️ lihat catatan validasi di atas
    sess.fill_text("luas_tanah_28d", LUAS_TANAH_OVERRIDE)

    # --- rincian 29 (Kepemilikan modal) — default 100% Pribadi ---
    sess.fill_text("pribadi_perorangan", KEPEMILIKAN_MODAL_DEFAULT["pribadi"])
    for key, label in (
        ("nonprofit", "nonprofit"),
        ("korporasi_publik", "korporasi_publik"),
        ("korporasi_nonpublik", "korporasi_nonpublik"),
        ("pemerintah_29e", "pemerintah"),
        ("asing_29f", "asing"),
    ):
        sess.fill_text(key, KEPEMILIKAN_MODAL_DEFAULT[label])

    log("BLOK II selesai diisi.")


def fill_keterangan_pemberi_jawaban(sess: FasihWebSession):
    sess.page.get_by_text(L["nama_pemberi_informasi"], exact=False).click()
    sess.page.get_by_text("Lainnya", exact=True).click()
    sess.page.locator("body").click(position={"x": 5, "y": 5})  # blur dropdown
    checkbox = sess.page.get_by_text(L["checkbox_pernyataan"], exact=False).first
    checkbox.locator("xpath=preceding::input[@type='checkbox'][1]").click()
    sess._log("KETERANGAN PEMBERI JAWABAN selesai.")


def fill_catatan(sess: FasihWebSession):
    sess.click_button("ambil_waktu_btn")
    sess.confirm_dialog("Ya")
    sess.page.get_by_text(re.compile("berhasil mendapatkan waktu", re.I)).wait_for(timeout=8000)
    sess._log("CATATAN (Waktu Selesai) selesai. Textarea Catatan sengaja dibiarkan kosong.")
