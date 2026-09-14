"""
fill_gabungan.py — Isi SE2026-L BLOK II dari SATU baris sheet gabungan.

Padanan fill_blok2.py utk sumber gabungan. Urutan & penjagaan field
bersyarat SENGAJA sama (alasannya dicatat panjang di fill_blok2.py &
CLAUDE.md): pilih_umkm_sls sebelum keberadaan_usaha, 13b4 setelah KBLI,
blok finansial baru dirender setelah rincian 25 di-blur.

Bedanya: nilai diambil APA ADANYA dari sheet. Tidak ada 10%, tidak ada
aturan pekerja <=3, tidak ada override aset/luas tanah = 0 — sheet ini sudah
berisi jawaban final per rincian. Default config HANYA dipakai utk rincian
yang tidak punya kolom di sheet (19, 20) dan setiap pemakaiannya
dikembalikan sbg daftar ASUMSI supaya masuk kolom review_disarankan.
"""

from __future__ import annotations

from inti.config import (
    DEFAULT_19A, DEFAULT_19C, DEFAULT_20B_VARIAN_SUDAH_BPOM, DEFAULT_20C_VARIAN_BELUM_BPOM,
    ISI_PILIH_UMKM_SLS, OPSI_13B4_JASA, OPSI_13B4_PERTANIAN, UMKM_SATU_SLS_KANDIDAT,
)
from inti.fasih_web import FasihWebSession, FieldNotFound
from inti.fill_blok2 import read_kategori_lapangan_usaha
from inti.gabungan_loader import KEY_16B, KEY_26, KEY_29, KEY_PEKERJA, OPSI_FORM, GabunganRow


class BarisPerluManual(RuntimeError):
    """Form meminta sesuatu yang tidak bisa dipenuhi sheet apa adanya.
    main_gabungan.py mencatatnya sbg SKIP_<kode> (isi manual), bukan ERROR."""

    def __init__(self, kode: str, pesan: str):
        super().__init__(pesan)
        self.kode = kode


def fill_blok2_gabungan(sess: FasihWebSession, row: GabunganRow) -> list[str]:
    """Isi BLOK II. Return daftar ASUMSI (nilai yang BUKAN dari sheet)."""
    log = sess._log
    asumsi: list[str] = []
    log(f"Isi BLOK II dari sheet gabungan (baris {row.baris}) ...")

    # --- 8a-8d ---------------------------------------------------------
    # pilih_umkm_sls HILANG dari DOM begitu keberadaan_usaha dijawab, jadi
    # wajib lebih dulu (lihat CLAUDE.md -> jebakan selector).
    if ISI_PILIH_UMKM_SLS and sess.komponen_ada("pilih_umkm_sls", timeout_ms=4000):
        kandidat = tuple(dict.fromkeys(filter(None, (row["pilih_umkm_sls"], *UMKM_SATU_SLS_KANDIDAT))))
        sess.pilih_combobox_pertama_yang_cocok("pilih_umkm_sls", kandidat)
    else:
        log("'Pilih UMKM dalam satu SLS yang sama' tidak dirender — dilewati.")

    sess.select_radio_by_datakey("keberadaan_usaha", row["keberadaan_usaha"])
    sess.fill_by_datakey("nama_komersial", row.nama_komersial)  # "<8b> (<12a>)"
    sess.fill_by_datakey("hp", row["hp"])
    sess.select_radio_by_datakey("jenis_kawasan", row["jenis_kawasan"])

    # --- 10 NIB ---------------------------------------------------------
    sess.select_radio_by_datakey("punya_nib", row["punya_nib"])
    if row["punya_nib"].startswith("1"):
        if not sess.komponen_ada("nib_nomor"):
            raise BarisPerluManual("10B_TIDAK_DIRENDER", "10a = Ya tapi field 10b (Tuliskan NIB) tidak dirender.")
        sess.fill_by_datakey("nib_nomor", row["nib_nomor"])
    elif sess.komponen_ada("tidak_nib"):
        sess.select_radio_by_datakey("tidak_nib", row["tidak_nib"])
    else:
        log("10c (alasan tanpa NIB) tidak dirender — dilewati.")

    # --- 11-12 ----------------------------------------------------------
    sess.select_radio_by_datakey("badan_usaha", row["badan_usaha"])
    sess.select_radio_by_datakey("lap_keuangan", row["lap_keuangan"])
    sess.fill_by_datakey("pengusaha", row["pengusaha"])
    sess.select_radio_by_datakey("jk", row["jk"])
    sess.fill_by_datakey("umur", row["umur"])
    sess.fill_by_datakey("nik_pengusaha", row["nik_pengusaha"])

    # --- 13 -------------------------------------------------------------
    sess.fill_by_datakey("keg_utama", row["keg_utama"])
    # 13b1-b3 per-dataKey: opsinya berteks identik ("1. Ya"/"2. Tidak").
    for key in ("produk_sendiri", "layanan_mamin", "keg_penjualan"):
        if not sess.komponen_ada(key):
            log(f"{key} tidak dirender di form ini — dilewati.")
            continue
        sess.select_radio_by_datakey(key, row[key])
    if sess.komponen_ada("lokasi_usaha"):
        sess.select_radio_by_datakey("lokasi_usaha", row["lokasi_usaha"])
    else:
        log("13c (tempat usaha) tidak dirender — dilewati.")
    sess.fill_by_datakey("produk", row.produk_utama)
    if not row["produk"]:
        asumsi.append("13f disalin dari 13a")

    # 13d/13e muncul kalau 13b1 = Ya; sheet tidak punya kolomnya.
    for pola, nama in ((r"^13\.\s*d\.", "13d"), (r"^13\.\s*e\.", "13e")):
        if sess.datakey_by_label(pola):
            raise BarisPerluManual("13DE_DIRENDER", f"{nama} dirender tapi sheet gabungan tidak punya kolomnya.")

    # 13g KBLI. Frasa cadangan = 13a; pilih() tetap memverifikasi KODE ada
    # di teks opsi sebelum mengklik, jadi frasa ini tidak bisa salah pilih.
    sess.fill_kbli_master(row["kbli"], search_phrase_fallback=row["keg_utama"])
    sess.page.wait_for_timeout(500)
    kategori = read_kategori_lapangan_usaha(sess.page)
    log(f"13h Kategori Lapangan Usaha (auto) = '{kategori}'")

    # 13b4 diisi SETELAH KBLI (sama dgn fill_blok2): baru ter-render kalau
    # 13b1-b3 semuanya Tidak, dan cadangannya diturunkan dari kategori 13h.
    if sess.komponen_ada("keg_jasa", timeout_ms=4000):
        pilihan = row["keg_jasa"]
        if pilihan not in OPSI_FORM["keg_jasa"]:
            pilihan = OPSI_13B4_PERTANIAN if kategori.strip().upper() == "A" else OPSI_13B4_JASA
            asumsi.append(f"13b4 sheet '{row['keg_jasa']}' bukan opsi -> '{pilihan}' dari kategori {kategori}")
        sess.select_radio_by_datakey("keg_jasa", pilihan)

    sess.select_radio_by_datakey("jaringan", row["jaringan"])

    # --- 16-18 ----------------------------------------------------------
    sess.select_radio_by_datakey("internet", row["internet"])
    if row["internet"].startswith("1"):
        for key in KEY_16B:
            if sess.komponen_ada(key, timeout_ms=4000):
                sess.select_radio_by_datakey(key, row[key])
            else:
                log(f"{key} (16b) tidak dirender — dilewati.")
        if sess.komponen_ada("digital", timeout_ms=4000):
            sess.select_radio_by_datakey("digital", row["digital"])
    for key in ("produksi_lingkungan", "perlindungan_lingkungan", "produk_seni"):
        sess.select_radio_by_datakey(key, row[key])

    # --- 19 & 20: tidak ada kolomnya di sheet -> default config (ASUMSI) --
    if sess.isi_bersyarat_by_label(r"^19\.\s*a\.", DEFAULT_19A, "19a"):
        asumsi.append(f"19a default '{DEFAULT_19A}'")
    if sess.isi_bersyarat_by_label(r"^19\.\s*c\.", DEFAULT_19C, "19c"):
        asumsi.append(f"19c default '{DEFAULT_19C}'")
    if sess.komponen_ada("izin_edar_bpom"):
        sess.select_radio_by_datakey("izin_edar_bpom", "3. Tidak")
        asumsi.append("20a default '3. Tidak'")
        if sess.datakey_by_label(r"^20\.\s*b\."):
            sess.isi_bersyarat_by_label(r"^20\.\s*b\.", DEFAULT_20B_VARIAN_SUDAH_BPOM, "20b (default)")
            asumsi.append(f"20b default '{DEFAULT_20B_VARIAN_SUDAH_BPOM}'")
        if sess.komponen_ada("jumlah_varian_belum_bpom"):
            sess.fill_by_datakey("jumlah_varian_belum_bpom", DEFAULT_20C_VARIAN_BELUM_BPOM)
            asumsi.append(f"20c default '{DEFAULT_20C_VARIAN_BELUM_BPOM}'")
    else:
        log("Rincian 20 (BPOM) tidak dirender utk kategori ini — dilewati.")

    # --- 21-25 ----------------------------------------------------------
    sess.select_radio_by_datakey("mitra_kdkmp", row["mitra_kdkmp"])
    sess.select_radio_by_datakey("peran_mbg", row["peran_mbg"])
    for key in ("barang_non_pddk", "jasa_non_pddk", "beli_jasa_non_pddk"):
        sess.select_radio_by_datakey(key, row[key])
    for key in KEY_PEKERJA:
        sess.fill_by_datakey(key, row[key])
    sess.fill_by_datakey("tahun_operasi", row["tahun_operasi"])

    # --- 26-29 ----------------------------------------------------------
    # Blok finansial baru selesai dirender setelah rincian 25 di-blur; saat
    # server lambat perlu ditunggu (record 2566 & 2571, lihat fill_blok2).
    def _deteksi_varian():
        if sess.komponen_ada("upah_gaji", timeout_ms=20_000):
            return "tahunan"
        if sess.komponen_ada("gaji_bln", timeout_ms=6_000):
            return "bulanan"
        return None

    sess.page.keyboard.press("Tab")
    sess.page.wait_for_timeout(1500)
    varian = _deteksi_varian()
    if varian is None:
        sess.page.keyboard.press("Tab")
        sess.page.wait_for_timeout(3000)
        varian = _deteksi_varian()
    if varian is None:
        raise FieldNotFound(f"Blok finansial (26-29) tidak dirender (tahun_operasi={row['tahun_operasi']}).")
    if varian == "bulanan":
        raise BarisPerluManual(
            "VARIAN_BULANAN",
            f"Form memakai rincian 30-33 (angka SATU BULAN) utk tahun_operasi={row['tahun_operasi']}; "
            "angka sheet tahunan — isi manual.")

    if not sess.komponen_ada("biaya_pembelian") and row.angka("biaya_pembelian") > 0:
        # Kategori B-F & I gol.56 tidak punya 26c terpisah. Menggabungkannya
        # ke 26b adalah keputusan data, bukan urusan skrip — berhenti.
        raise BarisPerluManual(
            "26C_TIDAK_DIRENDER",
            f"26c tidak dirender utk KBLI {row['kbli']} padahal sheet 26c={row['biaya_pembelian']}.")
    for key in KEY_26:
        if key == "biaya_pembelian" and not sess.komponen_ada(key, timeout_ms=1000):
            continue
        sess.fill_by_datakey(key, row[key])
    log(f"26f total pengeluaran (sheet) = {sum(row.angka(k) for k in KEY_26):,}")

    sess.fill_by_datakey("nilai_pendapatan", row["nilai_pendapatan"])
    sess.fill_by_datakey("pendapatan_lain", row["pendapatan_lain"])
    if sess.komponen_ada("pendapatan_online", timeout_ms=4000):
        sess.fill_by_datakey("pendapatan_online", row["pendapatan_online"])
    else:
        log("27d (persentase pendapatan online) tidak dirender — dilewati.")

    # Nama dataKey 28 menyesatkan: aset_usaha_thn = 28a TANAH & BANGUNAN,
    # aset_lain_thn = 28b SELAIN tanah & bangunan. Kolom sheet dipetakan
    # lewat awalan "28. a." / "28. b.", jadi sudah sesuai label.
    for key in ("aset_usaha_thn", "aset_lain_thn", "luas_tanah_thn"):
        sess.fill_by_datakey(key, row[key])

    if sess.komponen_ada("pribadi", timeout_ms=8_000):
        for key in KEY_29:
            sess.fill_by_datakey(key, row[key])
    else:
        log("Rincian 29 (kepemilikan modal) tidak dirender — dilewati.")

    sess.dump("blok2_gabungan_selesai_terisi")
    log("BLOK II selesai diisi." + (f" ASUMSI: {asumsi}" if asumsi else ""))
    return asumsi
