r"""
config_lokal.py — Pengaturan MILIK ANDA (password, akun, wilayah kabupaten).

1. Salin ke  inti/config_lokal.py
       Windows :  copy templates\config_lokal.contoh.py inti\config_lokal.py
       Linux   :  cp templates/config_lokal.contoh.py inti/config_lokal.py
2. Isi nilai di bawah. Baris yang tidak perlu diubah boleh dihapus / diberi # (nilai bawaan
   di inti/config.py yang dipakai).

inti/config_lokal.py ada di .gitignore — tidak ikut ter-commit. Setiap nama di sini MENIMPA
nama yang sama di inti/config.py, jadi konstanta lain dari config.py juga boleh ditimpa
(salin nama & formatnya persis).
"""

# ---------------------------------------------------------------------------
# 1. Kredensial (WAJIB)
# ---------------------------------------------------------------------------
# Password SSO Eksternal fasih-web yang SAMA untuk semua akun PPL/PML yang dipakai skrip
# (diseragamkan lewat reset_mitra/). Alternatif: variabel lingkungan FASIH_PASSWORD.
FIXED_PASSWORD = ""

# ---------------------------------------------------------------------------
# 2. Wilayah kabupaten/kota (WAJIB)
# ---------------------------------------------------------------------------
# 2 digit provinsi + 2 digit kab/kota = awalan setiap idsubsls. "5108" = Bali/Buleleng. GANTI.
KODE_KAB = "5108"

# Kodepos per DESA (10 digit pertama idsubsls). Sheet input usaha tidak punya kolom kodepos
# (boleh ditambah: kolom 'kodepos'), jadi kodepos diambil dari sini. Desa yang tidak ada ->
# baris ditolak SKIP_DATA_KODEPOS_TIDAK_DIKETAHUI (tidak ditebak).
# KODEPOS_BY_DESA = {
#     "5108010008": "81155",
# }

# Nama wilayah per idsubsls — hanya referensi (log & pencocokan BLOK I). Opsional.
# WILAYAH_BY_IDSUBSLS = {
#     "5108080008000202": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN",
#                          "desa": "TAMBLANG", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
# }

# ---------------------------------------------------------------------------
# 3. Akun & subsls tempat dokumen dibuat (bisa juga lewat --akun-tunggal / --subsls-tunggal)
# ---------------------------------------------------------------------------
# Semua dokumen dibuat di SATU subsls oleh SATU akun PPL, lalu dipindah ke wilayah aslinya
# belakangan (fasih_sm/pindah_wilayah). Akun ini harus punya assignment PAPI di subsls itu
# (fasih_sm/ganti_moda).
GABUNGAN_SUBSLS_TUNGGAL = ""   # mis. "5108010010000105"
GABUNGAN_AKUN_TUNGGAL = ""     # mis. "ppl.contoh@gmail.com"

# ---------------------------------------------------------------------------
# 4. Aturan pengisian (TINJAU sebelum mengirim data sungguhan)
# ---------------------------------------------------------------------------
# Rincian yang TIDAK ada di kuesioner kertas diisi TAHAP2_DEFAULT, dan sel yang kosong/rusak
# diganti menurut aturan TAHAP2_* di inti/config.py (mis. umur kosong -> 45, HP rusak -> 9999,
# 16a Ya tanpa 16b -> b6 Ya). Semuanya KEPUTUSAN BPS Buleleng. Kalau kebijakan Anda berbeda,
# timpa di sini, mis.:
# TAHAP2_UMUR_KOSONG_JADI = ""          # "" = jangan ganti, baris ditolak
# TAHAP2_DEFAULT = {...}                # salin dari inti/config.py lalu ubah

# ---------------------------------------------------------------------------
# 5. ID periode survei (segmen URL list PENDATAAN fasih-web)
# ---------------------------------------------------------------------------
# https://fasih-web.bps.go.id/survey/<SURVEY_ID>/<ASSIGNMENT_ID_GABUNGAN>
# Bawaan = periode SE2026 yang dipakai di Buleleng; ganti kalau URL list Anda berbeda.
# ASSIGNMENT_ID_GABUNGAN = "fd68e454-ba45-4b85-8205-f3bf777ded24"

# Peta batas SUBSLS (GeoJSON) — hanya utk koordinat/koordinat_pengganti.py.
# PETA_SLS_PATH = r"D:\data\peta\final_sls_5108_2025-1.json"
