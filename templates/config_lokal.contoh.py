r"""
config_lokal.py — Pengaturan MILIK ANDA (password, akun, wilayah kabupaten).

CARA PAKAI
----------
1. Salin file ini ke  inti/config_lokal.py
       Windows :  copy templates\config_lokal.contoh.py inti\config_lokal.py
       Linux   :  cp templates/config_lokal.contoh.py inti/config_lokal.py
2. Isi nilai di bawah. Hapus / beri tanda # pada baris yang tidak perlu diubah
   (nilai bawaan di inti/config.py yang akan dipakai).

inti/config_lokal.py ada di .gitignore — TIDAK ikut ter-commit, jadi aman
untuk password & email. JANGAN menulis nilai-nilai ini di inti/config.py.

Setiap nama yang didefinisikan di sini MENIMPA nama yang sama di inti/config.py
(dimuat di baris paling bawah config.py). Jadi Anda juga bisa menimpa konstanta
lain dari config.py kalau perlu — salin nama & formatnya persis.
"""

# ---------------------------------------------------------------------------
# 1. Kredensial
# ---------------------------------------------------------------------------

# Password SSO Eksternal fasih-web yang SAMA untuk semua akun PPL/PML yang
# dipakai skrip. Biasanya diseragamkan dulu lewat reset_mitra/ (lihat
# docs/PANDUAN_RESET_MITRA.md). Alternatif: variabel lingkungan FASIH_PASSWORD.
FIXED_PASSWORD = ""

# ---------------------------------------------------------------------------
# 2. Wilayah kabupaten/kota Anda
# ---------------------------------------------------------------------------

# 2 digit provinsi + 2 digit kabupaten/kota = awalan setiap idsubsls 16 digit.
# Contoh: "5108" = Bali / Buleleng, "3201" = Jawa Barat / Bogor. GANTI.
KODE_KAB = "5108"

# Tiga pengaturan di bawah OPSIONAL. inti/config.py berisi data CONTOH Buleleng
# untuk KODEPOS_BY_IDSUBSLS & WILAYAH_BY_IDSUBSLS; data itu tidak akan cocok
# dgn idsubsls kabupaten lain, jadi aman dibiarkan. Buka tanda # kalau perlu.

# Kodepos per idsubsls (16 digit) — WAJIB untuk alur backlog lama
# (input_fasihweb/main.py): baris yang idsubsls-nya tidak ada di sini di-skip
# (SKIP_KODEPOS_TIDAK_DIKETAHUI), kecuali kodepos bisa diturunkan dari file
# export. Kodepos dialokasikan per DESA. Alur Agenda (input_gabungan/) membaca
# kodepos dari kolom sheet, jadi tidak butuh ini.
# KODEPOS_BY_IDSUBSLS = {
#     "5108080008000202": "81172",
# }

# Nama wilayah per idsubsls — hanya REFERENSI (log & pencocokan rincian 1-6
# BLOK I dokumen yang terbuka). Dropdown "Wilayah Responden" dipilih lewat kode.
# WILAYAH_BY_IDSUBSLS = {
#     "5108080008000202": {
#         "provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN",
#         "desa": "TAMBLANG", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN",
#     },
# }

# Peta batas SUBSLS (GeoJSON, properti idsubsls/nmkec/nmdesa/nmsls) — hanya
# dipakai input_gabungan/rencana_ubah_wilayah.py utk mengecek titik koordinat.
# Tanpa peta: jalankan skrip itu dengan --tanpa-peta.
# PETA_SLS_PATH = r"D:\data\peta\final_sls_5108_2025-1.json"

# ---------------------------------------------------------------------------
# 3. Alur Agenda "satu subsls + satu akun" (input_gabungan/main_gabungan.py)
# ---------------------------------------------------------------------------
# Semua dokumen dibuat di SATU subsls oleh SATU akun PPL, lalu dipindah ke
# wilayah aslinya belakangan (pindah_wilayah/). Akun ini harus punya assignment
# mode PAPI di subsls tsb (lihat ganti_moda/). Bisa juga lewat CLI:
# --subsls-tunggal / --akun-tunggal.
GABUNGAN_SUBSLS_TUNGGAL = ""   # mis. "5108010010000105"
GABUNGAN_AKUN_TUNGGAL = ""     # mis. "ppl.contoh@gmail.com"

# ---------------------------------------------------------------------------
# 4. ID periode survei (segmen URL list PENDATAAN fasih-web)
# ---------------------------------------------------------------------------
# https://fasih-web.bps.go.id/survey/<SURVEY_ID>/<ASSIGNMENT_ID_GABUNGAN>
# Bawaan di config.py = periode SE2026 yang dipakai di Buleleng. Kalau URL list
# PENDATAAN Anda berbeda, salin segmen kedua URL itu ke sini.
# ASSIGNMENT_ID_GABUNGAN = "fd68e454-ba45-4b85-8205-f3bf777ded24"
