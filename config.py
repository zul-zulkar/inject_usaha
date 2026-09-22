"""
config.py — Konfigurasi & konstanta untuk otomatisasi input Usaha Pecahan SE2026.

SEMUA nilai di file ini diringkas dari catatan proyek
"catatan-usaha-pecahan-se2026.md" (hasil 3x pengisian manual penuh yang
sudah terverifikasi sukses terkirim). Kalau ada label field yang ternyata
tidak ketemu saat dry-run, PALING BESAR KEMUNGKINAN cukup edit string di
sini saja — logika utama di otomatisasi_se2026.py tidak perlu diubah.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# URL & kredensial
# ---------------------------------------------------------------------------

# ID level survei SE2026 (bagian pertama URL fasih-web, tampaknya konstan
# utk seluruh gelombang sensus, BUKAN per-petugas). Sudah dikonfirmasi dari
# 3 dokumen yang berhasil dikirim.
SURVEY_ID = "a0429e96-51a5-477b-a415-485f9c153004"

# Password SSO eksternal fasih-web — SAMA utk semua akun (dikonfirmasi user).
# SENGAJA kosong: repo ini publik. Isi di inti/config_lokal.py (di .gitignore)
# atau env FASIH_PASSWORD — lihat README.md.
FIXED_PASSWORD = ""

FASIH_WEB_LOGIN_URL = "https://fasih-web.bps.go.id/login"
FASIH_WEB_BASE = "https://fasih-web.bps.go.id"
FASIH_SM_BASE = "https://fasih-sm.bps.go.id"

# ---------------------------------------------------------------------------
# Aturan tetap / override (dari rule #6, #7, #8, #9 di catatan proyek)
# ---------------------------------------------------------------------------

NIK_OVERRIDE = "9999"          # 12d — selalu 9999, abaikan NIK sumber
ASET_TANAH_OVERRIDE = "0"       # 28a — selalu 0, abaikan sumber
LUAS_TANAH_OVERRIDE = "0"       # 28d — selalu 0, abaikan sumber
UMKM_SATU_SLS = "Tidak ada"     # "Pilih UMKM dalam satu SLS yang sama"
NAMA_PEMBERI_INFORMASI = "Lainnya"

# rincian 29 (kepemilikan modal) — di 3 sample record SELALU 100% Pribadi/
# Perorangan. TIDAK ADA kolom sumber di sheet utk field ini, jadi dipakai
# sbg default. ⚠️ VERIFIKASI: kalau fasih-sm sumber ternyata punya rincian
# kepemilikan modal juga, sebaiknya di-scrape drpd diasumsikan konstan —
# lihat TODO di scrape_source.py.
KEPEMILIKAN_MODAL_DEFAULT = {
    "pribadi": "100", "nonprofit": "0", "korporasi_publik": "0",
    "korporasi_nonpublik": "0", "pemerintah": "0", "asing": "0",
}

# ---------------------------------------------------------------------------
# Label / teks yang dicari di halaman (Playwright get_by_label / get_by_text)
# ---------------------------------------------------------------------------
# String yang diberi tanda "# EXACT" sudah dikutip persis dari screenshot
# nyata selama sesi manual (confident). String lain adalah rekonstruksi dari
# catatan & KEMUNGKINAN perlu sedikit disesuaikan (mis. kurang kata, beda
# kapitalisasi) — WAJIB dicek saat dry-run pertama (--headed --dry-run).

L = {
    # --- SE2026-P ---
    "tambah_dropdown": "Tambah",
    "opsi_bangunan_lainnya": "Bangunan Lainnya (Selain Tempat Tinggal dan Campuran)",  # EXACT
    "nama_bangunan_usaha": "Nama Bangunan/Usaha/Perusahaan",
    "keberadaan_bangunan_lainnya": "Keberadaan Bangunan Lainnya/Usaha",  # EXACT
    "opsi_baru": "2. Baru",
    "nama_jalan": "Nama Jalan/Gang/Komplek/Gedung/dll",  # EXACT
    "blok_nomor_rumah": "Blok/Nomor Rumah",  # EXACT
    "nomor_urut_bangunan_terbesar": "NOMOR URUT BANGUNAN TERBESAR",  # EXACT (readonly)
    "nomor_urut_bangunan": "Nomor Urut Bangunan",  # EXACT — JANGAN PERNAH disentuh kecuali perlu fix GALAT
    "kode_penggunaan_bangunan": "Kode Penggunaan Bangunan",  # EXACT
    "ambil_lokasi_btn": "Ambil Lokasi",  # EXACT
    "pilih_lokasi_modal_title": "Pilih Lokasi",  # EXACT
    "latitude": "Latitude",
    "longitude": "Longitude",
    "gunakan_lokasi_btn": "Gunakan Lokasi",  # EXACT
    "konfirmasi_ambil_lokasi_ya": "Ya",

    # --- IDENTITAS WILAYAH ---
    "perubahan_sls": "Apakah mengalami perubahan SLS",
    "opsi_tidak_2": "2. Tidak",
    "kodepos": "Kodepos",  # EXACT (label "10. Kodepos")

    # --- BLOK II umum ---
    "umkm_satu_sls": "Pilih UMKM dalam satu SLS yang sama",  # EXACT
    "keberadaan_usaha": "Keberadaan Usaha",
    "nama_komersial": "Nama",  # rincian 8b — pola: "Nama Usaha/Perusahaan (Komersial)" -> VERIFIKASI persis
    "alamat_usaha": "Alamat usaha",  # 8c, biasanya sudah auto-terisi dari SE2026-P
    "rt": "RT",
    "rw": "RW",
    "kode_pos_8c": "Kode Pos",
    "kode_area": "Kode Area",  # EXACT
    "no_telepon": "Nomor Telepon",  # EXACT
    "ekstensi": "Ekstensi",  # EXACT
    "email": "Email",  # EXACT
    "no_hp_wa": "No HP/WA",
    "homepage": "Homepage/website",  # EXACT (ada hint "diawali dengan www")
    "jenis_kawasan": "Jenis kawasan",
    "opsi_luar_kawasan": "10. Di luar kawasan",
    "nib": "NIB",
    "alasan_tanpa_nib": "Tidak memerlukan NIB",
    "status_badan_usaha": "status badan usaha",
    "opsi_bukan_badan_usaha": "13. Bukan Badan Usaha",
    "laporan_keuangan": "laporan keuangan",
    "nama_pengusaha": "Nama Pengusaha",
    "jenis_kelamin": "Jenis Kelamin",
    "umur": "Umur",
    "nik": "NIK",
    "kegiatan_utama": "kegiatan utama",  # 13a (textarea)
    "produksi_di_lokasi": "memproduksi barang",  # 13b1
    "layanan_makan_minum": "layanan makan",  # 13b2
    "penjualan_barang": "penjualan barang",  # 13b3
    "tempat_usaha": "tempat usaha",  # 13c
    "produk_utama": "produk utama",  # 13f (textarea)
    "pilih_master_kbli_radio": "Pilih dari Master KBLI",  # EXACT
    "kbli_search_box": "Cari",  # kotak pencarian dropdown Master KBLI
    "kbli_clear_x": "Konfirmasi Hapus Pilihan",  # EXACT (dialog title)
    "kategori_lapangan_usaha": "Kategori Lapangan Usaha",  # 13h, readonly auto
    "jaringan_usaha": "jaringan usaha",
    "opsi_tunggal": "1. Tunggal",
    "pakai_internet": "menggunakan internet",  # EXACT (16a, dipotong)
    "produk_ramah_lingkungan": "produk ramah lingkungan",  # 17a
    "input_ramah_lingkungan": "input ramah lingkungan",  # 17b
    "karya_seni_budaya": "karya seni",  # 18
    "izin_edar_bpom": "izin edar",  # 20a
    "jumlah_varian_belum_bpom": "jumlah varian produk yang belum memiliki izin edar BPOM",  # EXACT 20c
    "mitra_kdkmp": "KDKMP",  # 21
    "program_mbg": "MBG",  # 22
    "transaksi_bukan_penduduk": "bukan penduduk Indonesia",  # 23a/b/c
    "pekerja_laki2_dibayar": "24",  # placeholder, diisi manual per-field di kode
    "tahun_mulai_komersial": "tahun mulai",  # 25

    # rincian 26 (Pengeluaran)
    "upah_gaji": "upah",  # 26a
    "biaya_produksi": "biaya produksi",  # 26b
    "biaya_pembelian": "biaya pembelian",  # 26c (kondisional)
    "operasional_26d": "operasional",  # 26d — hati2 duplikat kata, pakai locator scoped rincian 26
    "non_operasional_26e": "non-operasional",  # 26e

    # rincian 27 (Pendapatan)
    "nilai_penjualan": "nilai penjualan",  # 27a
    "pendapatan_lain": "pendapatan lain",  # 27b

    # rincian 28 (Aset)
    "aset_tanah_bangunan": "aset tanah",  # 28a
    "aset_selain_tanah": "aset selain tanah",  # 28b
    "luas_tanah_28d": "luas tanah",  # 28d

    # rincian 29 (Kepemilikan modal)
    "pribadi_perorangan": "Pribadi/Perorangan",  # EXACT
    "nonprofit": "Lembaga Nonprofit",
    "korporasi_publik": "Korporasi Publik",
    "korporasi_nonpublik": "Korporasi Non Publik",
    "pemerintah_29e": "29. e. Pemerintah",
    "asing_29f": "29. f. Asing",

    # --- KETERANGAN PEMBERI JAWABAN ---
    "nama_pemberi_informasi": "Nama Pemberi Informasi",  # EXACT
    "checkbox_pernyataan": "Saya menyatakan bahwa data yang saya berikan sesuai dengan kondisi yang sebenarnya",  # EXACT

    # --- CATATAN ---
    "waktu_selesai": "Waktu Selesai",  # EXACT
    "ambil_waktu_btn": "Ambil Waktu",  # EXACT
    "catatan_textarea": "Catatan",  # EXACT (section & field sama nama)

    # --- Umum / navigasi ---
    "kirim_btn": "Kirim",  # EXACT
    "konfirmasi_btn": "Konfirmasi",  # EXACT (dialog "Konfirmasi Kirim")
    "save_icon_testid": None,  # fallback pakai posisi ikon disket di floating toolbar
    "dokumen_baru_btn": "Dokumen Baru",  # EXACT ("+ Dokumen Baru")
    "muat_ulang_btn": "Muat Ulang",  # EXACT
    "refresh_halaman_btn": "Refresh Halaman",  # EXACT (di error page 403/504)
    "entri_link": "Entri",  # EXACT (link aksi di baris dokumen list)
    "sso_eksternal_btn": "SSO Eksternal",  # EXACT
}

# ---------------------------------------------------------------------------
# Kategori KBLI yang TIDAK menampilkan rincian 20 (BPOM) sama sekali.
# Dari sample: kategori I golongan 56 (Aktivitas Kedai Minuman) tidak
# menampilkan rincian 20. Ini dipakai HANYA sbg fallback cepat —
# deteksi UTAMA tetap harus dari DOM (lihat catatan di kode utama),
# bukan dari tabel ini, karena polanya belum tentu lengkap.
KATEGORI_TANPA_RINCIAN_20_HINT = {"I"}

# Kategori yang butuh field 26b digabung (biaya_produksi + biaya_pembelian)
# krn form tidak render 26c terpisah. Sample: kategori I golongan 56.
# Deteksi UTAMA tetap dari DOM (apakah field 26c benar2 ada di halaman).
KATEGORI_GABUNG_26B_HINT = {"B", "C", "D", "E", "F", "I"}

# ---------------------------------------------------------------------------
# Timeout & perilaku
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_MS = 15_000
SAVE_DEBOUNCE_MS = 1_500
NAV_RETRY_ON_TRANSIENT_ERROR = 2  # hanya berlaku pada dokumen 0% progres (lihat catatan kritis)

# ---------------------------------------------------------------------------
# Kodepos per idsubsls — WAJIB dilengkapi kalau backlog mencakup SLS selain
# yang sudah diketahui. Baru ada 1 entri terverifikasi dari sesi manual.
# Kalau idsubsls suatu baris tidak ada di dict ini, skrip akan berhenti &
# minta kodepos diisi manual (lihat main.py) drpd menebak/mengosongkan
# field wajib ini.
# ---------------------------------------------------------------------------
KODEPOS_BY_IDSUBSLS: dict[str, str] = {
    "5108080008000202": "81172",
}
