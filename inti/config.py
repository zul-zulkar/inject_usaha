"""
config.py — Konfigurasi & konstanta untuk otomatisasi input Usaha Pecahan SE2026.

SEMUA nilai di file ini diringkas dari catatan proyek
"docs/catatan usaha pecahan se2026.md" (hasil 3x pengisian manual penuh yang
sudah terverifikasi sukses terkirim). Kalau ada label field yang ternyata
tidak ketemu saat dry-run, PALING BESAR KEMUNGKINAN cukup edit string di
sini saja — logika utama di file lain tidak perlu diubah.

⚠️ JANGAN menulis rahasia (password, email akun) di file ini — file ini ikut
git. Nilai milik Anda sendiri (password, akun, kode kabupaten, kodepos &
wilayah kabupaten Anda, path peta) ditulis di `inti/config_lokal.py`, yang
TIDAK ikut git. Salin dari `templates/config_lokal.contoh.py`. Semua nama
di file ini boleh ditimpa di sana (lihat bagian paling bawah).
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# URL & kredensial
# ---------------------------------------------------------------------------

# ID level survei SE2026 (bagian pertama URL fasih-web, tampaknya konstan
# utk seluruh gelombang sensus, BUKAN per-petugas). Sudah dikonfirmasi dari
# 3 dokumen yang berhasil dikirim.
SURVEY_ID = "a0429e96-51a5-477b-a415-485f9c153004"

# Password SSO eksternal fasih-web — SAMA utk semua akun petugas (hasil reset
# password mitra, lihat reset_mitra/). SENGAJA kosong di sini: isi di
# inti/config_lokal.py atau variabel lingkungan FASIH_PASSWORD. Kosong ->
# FasihWebSession.login() berhenti dgn pesan yang jelas, tidak mencoba login.
FIXED_PASSWORD = os.environ.get("FASIH_PASSWORD", "")

# Kode wilayah kabupaten/kota 4 digit (2 digit provinsi + 2 digit kab/kota),
# awalan setiap idsubsls 16 digit. Dipakai memvalidasi daftar idsubsls di
# buka_wilayah/, tandai_selesai/, pindah_wilayah/ (Python & template Console).
# Default = contoh Kab. Buleleng (5108); ganti di config_lokal.py.
KODE_KAB = "5108"

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
# ---------------------------------------------------------------------------
# Nilai default untuk field WAJIB yang sumbernya (export fasih-sm) kosong.
# DITETAPKAN EKSPLISIT OLEH USER (2026-09-03) — ini keputusan pengguna,
# BUKAN tebakan skrip. Hanya dipakai kalau datanya memang tidak terambil
# saat export; kalau sumber punya nilainya, nilai sumber yang menang.
# ---------------------------------------------------------------------------
DEFAULT_10C_ALASAN_TANPA_NIB = "3. Tidak memerlukan NIB"
DEFAULT_13C_TEMPAT_USAHA = "4. Toko, ruko, dan sejenisnya"
# Kalau ringkasan pra-kirim menandai GALAT pada 13c (lokasi usaha), jawabannya
# LANGSUNG diganti ini lalu ringkasan dibaca ulang — ketetapan user 2026-09-23
# ("13c kalau ada kode error, langsung ubah ke kode 5 saja"). "" = matikan.
GALAT_13C_JADI = "5. Kedai, stan, tenda"
# KBLI sheet berkategori P/U (form menolak 13g: "Kategori tidak boleh berisi P atau
# U") -> 13g diisi lewat tombol "DAPATKAN REKOMENDASI KBLI" lalu rekomendasi GenAI
# PERTAMA dipilih (ketetapan user 2026-09-24). Rekomendasi yang kategorinya juga P/U
# dilewati. False = baris di-skip KBLI_KATEGORI_DITOLAK (perilaku lama). Mode murni
# tidak memakainya.
KBLI_DITOLAK_PAKAI_GENAI = True

# Indikator ekonomi (26a-26e, 27a-27b, 28a-28b) yang selnya KOSONG di kuesioner
# kertas = tidak ada nilainya = NOL — ketetapan user 2026-09-23 ("untuk indikator
# ekonomi yang ga ada datanya harusnya kau peka kalau itu diisikan dengan nol").
# Sebelum ini baris spt itu ter-skip SKIP_DATA_WAJIB_KOSONG sebelum dokumen dibuat.
TAHAP2_UANG_KOSONG_JADI_NOL = True
# 12c umur / 25 tahun mulai operasi KOSONG di sheet (2026-09-24: 62 baris di
# 1301-1500, pemilik yang sama pun kosong di semua usahanya). Urutan: (1) disalin
# dari usaha lain PEMILIK yang sama (akun + idsubsls + 12a) kalau yang terisi
# sepakat satu nilai; (2) sisanya diisi nilai ini — ketetapan user 2026-09-24,
# median data tahap 2 hari itu (umur 45, tahun 2019; sengaja bukan tahun berjalan
# supaya tidak memicu varian bulanan). "" = baris tetap skip WAJIB_KOSONG.
TAHAP2_UMUR_KOSONG_JADI = "45"
TAHAP2_TAHUN_OPERASI_KOSONG_JADI = "2019"
# 27c = 0 (penjualan 27a & 27b kosong/nol) -> 27a diisi minimal form (100.000;
# varian bulanan 10.000) — ketetapan user 2026-09-24 (baris 1374/1375). False =
# skip DI_BAWAH_MINIMAL (perilaku lama). 26f = 0 TETAP skip.
TAHAP2_PENJUALAN_NOL_JADI_MINIMAL = True
# Lanjutan ketetapan user 2026-09-24 ("blok ekonomi yang kosong isikan 0, kalau tidak
# boleh nilai minimal"). False = baris itu di-skip seperti dulu.
#   26f = 0 (semua pengeluaran kosong/nol) -> 26d = minimal form (100.000 / bulanan 10.000).
TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL = True
#   Usaha dagang varian bulanan dgn 30c = 0 (form mewajibkan > 0) -> 26b dipindah ke 26c;
#   26b juga 0 -> pos terbesar dari 26d/26e. Total pengeluaran tetap.
TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN = True
#   KBLI B-F / gol. 56 dgn 26b = 0 (form mewajibkan > 0) -> 26d dipindah ke 26b (26d 0 -> 26e).
TAHAP2_26B_NOL_AMBIL_DARI_26D = True
#   Kolom 24 kosong SEMUA -> 1 pekerja berjenis kelamin pemilik (pemilik ikut dihitung di
#   24), dibayar kalau 26a > 0, selain itu tidak dibayar. 27d kosong (16a Ya) -> 0 ikut
#   TAHAP2_UANG_KOSONG_JADI_NOL.
TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL = True
# Form menolak 24a2 (pekerja DIBAYAR) > 0 sementara 26a = 0 ("gaji": 26a/24a2 harus
# > Rp50.000). Ketetapan user 2026-09-23: "kalau error karena ada tenaga kerja yang
# dibayar, isikan 26a 100.000". 0 = matikan aturan ini.
# Nilainya PER PEKERJA DIBAYAR (2026-09-24): 100.000 rata utk 2+ pekerja jatuh
# <= Rp50.000/orang -> ditolak lagi oleh aturan kedua `gaji` (baris 285/828/1680
# ter-skip 26A_PER_PEKERJA_DI_BAWAH_MINIMAL padahal sheetnya 26a = 0 apa adanya).
TAHAP2_GAJI_JIKA_DIBAYAR = 100_000
# Koordinat yang formatnya dirusak Excel (2026-09-24, 114 baris "tanpa koordinat"
# yang sebenarnya berisi titik): "-8.148.438" (titik jadi pemisah ribuan),
# bujur negatif "-115,142881", lat & long dalam satu sel "-8.142753,115.059837",
# "-8155247,". Dipulihkan HANYA kalau hasilnya jatuh di kotak ini
# (lat_min, lat_maks, lon_min, lon_maks) — contoh: Kabupaten Buleleng + margin
# (kotak se-Bali meloloskan baris 1266/1267: "-8,47722" = 37 km dari desanya,
# hampir pasti salah ketik). Kabupaten lain menimpanya di config_lokal.py.
# None = tidak dipulihkan (perilaku lama: DRAFT).
TAHAP2_KOTAK_KOORDINAT = (-8.45, -8.0, 114.4, 115.45)
# Kolom idsubsls yang 4 digit awalnya salah ketik ("5100090007000901") padahal
# kode kecamatannya (digit 5-7) sama dgn kolom "Sumber/Kec." -> awalan diganti
# KODE_KAB. False = baris itu tetap di-skip KODEPOS_TIDAK_DIKETAHUI.
TAHAP2_PERBAIKI_AWALAN_IDSUBSLS = True
DEFAULT_19A = "3. Tidak/Belum"
DEFAULT_19C = "1"
DEFAULT_20C_VARIAN_BELUM_BPOM = "1"

# 13b1/b2/b3 kalau export TIDAK punya nilainya sama sekali (record 2553 &
# 2604). Form mewajibkannya. "2. Tidak" dipilih karena SELURUH record lain
# di backlog ini menjawab b1="2. Tidak" (warung/toko, tidak memproduksi
# sendiri) — konsisten, dan bikin 13b4 muncul lalu terisi dari kategori
# KBLI. ⚠️ ASUMSI, belum dikonfirmasi user: baris yang memakainya ditandai
# di kolom review_disarankan.
DEFAULT_13B_KALAU_SUMBER_KOSONG = "2. Tidak"

# 20b kalau field-nya dirender tapi export tidak punya angkanya (record
# 2585 & 2587, yang 20a-nya "1. Ya, oleh BPOM" sehingga jumlah varian
# ber-izin mustahil nol). Sejalan dgn DEFAULT_20C yang juga "1".
# ⚠️ ASUMSI, ditandai di review_disarankan.
DEFAULT_20B_VARIAN_SUDAH_BPOM = "1"

# Rincian 16b1-b6 / 16c / 27d — muncul HANYA kalau 16a (pakai internet)
# dijawab "1. Ya". Sumber fasih-sm TIDAK menyimpan rincian ini sama
# sekali (dicek di export mentah: tidak ada satu pun key internet/
# digital/online), jadi nilainya adalah DEFAULT yang ditetapkan user.
#
# ⚠️ FORM MEWAJIBKAN MINIMAL SATU "1. Ya". User sempat memilih "semua
# Tidak" (2026-09-06), tapi ringkasan menolaknya dgn galat harfiah
# "Salah satu dari 16b1 - 16b6 wajib terisi YA". Dipakai satu Ya paling
# minim (promosi) — promosi tidak menyiratkan penjualan online, jadi
# 27d = 0 tetap konsisten. Kalau mau Ya-nya di rincian lain, cukup pindah
# nilainya di dict ini; jangan menjadikan semuanya "2. Tidak".
DEFAULT_16B_TUJUAN_INTERNET = {
    "internet_pesanan": "2. Tidak",      # 16b1 menerima pesanan barang/jasa
    "internet_produksi": "2. Tidak",     # 16b2 produksi barang/jasa
    "internet_distribusi": "2. Tidak",   # 16b3 distribusi barang/jasa
    "internet_beli": "2. Tidak",         # 16b4 membeli bahan baku online
    "internet_promosi": "1. Ya",         # 16b5 promosi — WAJIB ada 1 Ya (lihat catatan)
    "internet_lainnya": "2. Tidak",      # 16b6 lainnya
}
DEFAULT_16C_TEKNOLOGI_DIGITAL = "2. Tidak"
DEFAULT_27D_PERSEN_PENDAPATAN_ONLINE = "0"

# Rincian 13b4 "Pilih salah satu aktivitas yang dilakukan" — muncul kalau
# 13b1/b2/b3 semuanya "2. Tidak" (usaha tidak memproduksi, tidak melayani
# makan-minum, tidak menjual barang). Hanya 2 opsi, dan pilihannya BUKAN
# tebakan: kategori lapangan usaha "A" = Pertanian/Kehutanan/Perikanan,
# selain itu masuk Jasa. Kategori dibaca dari rincian 13h yang terisi
# otomatis setelah KBLI dipilih, jadi 13b4 SENGAJA diisi setelah 13g.
OPSI_13B4_JASA = "1. Jasa"
OPSI_13B4_PERTANIAN = "2. Pertanian, Perikanan, dan Kehutanan"

# Combobox "Pilih UMKM dalam satu SLS yang sama" (BLOK II).
# ⚠️ HARUS DIISI — tidak bisa dikosongkan. User sempat menetapkan
# "kosongi saja" (2026-09-06) berdasarkan record 2521 yang lolos GALAT=0
# tanpa mengisinya, TAPI itu menyesatkan: di 2521 field-nya memang sudah
# telanjur hilang dari DOM. Diuji ulang di DOKUMEN BARU (record 2522):
# dibiarkan kosong -> "GALAT 1/1 | Pilih UMKM dalam satu SLS yang sama |
# Wajib diisi", dan GALAT>0 memblokir Kirim. Jadi ini kendala form, bukan
# preferensi. Biarkan True.
ISI_PILIH_UMKM_SLS = True

# Kandidat teks opsi, dipakai HANYA kalau ISI_PILIH_UMKM_SLS = True. Aturan #8
# catatan proyek menetapkan "Tidak ada". Teks opsi persisnya belum
# pernah terbaca dari DOM (popover baru dirender saat diklik), jadi
# dicoba berurutan; kalau tidak ada yang cocok skrip BERHENTI dan
# mencetak SELURUH opsi yang tersedia, bukan menebak.
UMKM_SATU_SLS_KANDIDAT = ("Tidak ada", "Tidak Ditemukan", "Tidak ditemukan")

# Rincian 31e "Bulan beroperasi selama tahun 2026" — HANYA ada di varian
# bulanan (usaha yang mulai beroperasi tahun berjalan). Sumber fasih-sm
# TIDAK punya data bulan sama sekali. DITETAPKAN USER 2026-09-07: pilih
# bulan MULAI secara ACAK di antara bulan yang tersedia (form hanya
# menampilkan bulan yang sudah lewat), lalu centang bulan itu dan SEMUA
# bulan sesudahnya sampai bulan terakhir yang tersedia.
BULAN_NAMA = (
    "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI",
    "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER",
)

# ---------------------------------------------------------------------------
# Aturan rincian 24 (pekerja) <-> rincian 26a (upah/gaji).
# DITETAPKAN EKSPLISIT OLEH USER (2026-09-06) — keputusan pengguna, bukan
# tebakan skrip. Logikanya murni di data_loader.rencana_pekerja() /
# rencana_pengeluaran(), dipakai fill_blok2.py.
#
#   total pekerja <= BATAS_TK_SEMUA_TIDAK_DIBAYAR (3 orang)
#       -> 24a2 (dibayar) = 0, 24b2 (tidak dibayar) = total
#       -> 26a (upah/gaji) DINOLKAN. Tidak ada kompensasi ke pos lain:
#          pekerja tidak dibayar memang tidak menimbulkan biaya upah, jadi
#          total pengeluaran ikut turun (ini konsekuensi yg disadari).
#
#   total pekerja > 3
#       -> keempat angka pekerja apa adanya dari sumber
#       -> 26a = 10% sumber (perilaku normal), LALU angka itu DIPOTONG dari
#          pos pengeluaran lain yang kontribusinya paling besar, supaya
#          total pengeluaran tidak ikut membengkak.
# ---------------------------------------------------------------------------
BATAS_TK_SEMUA_TIDAK_DIBAYAR = 3

# Form menolak total rincian 26f & 27c di bawah nilai ini ("Nilai minimal
# 100.000"). Aturan 10% bisa menghasilkan angka di bawahnya utk usaha yang
# sangat kecil — 7 baris (26f) & 6 baris (27c) di backlog per 2026-09-07.
# Ditetapkan user: kekurangannya DITAMBAHKAN sampai total pas 100.000.
# ⚠️ Konsekuensi yang disadari: baris yang kena tidak lagi bernilai 10%
# dari sumber, dan baris yang sumbernya nol jadi bukan nol. Setiap kali
# ini terjadi dicatat di log & ditandai di kolom review_disarankan.
MINIMAL_TOTAL_RUPIAH = 100_000
# Padanan varian BULANAN (rincian 30f/31c) — form sendiri bilang
# "harus lebih dari 10.000" / "Nilai minimal 10.000", beda dari yang
# tahunan (100.000). Diverifikasi dari dump DOM record 2566, 2026-09-07.
MINIMAL_TOTAL_RUPIAH_BULANAN = 10_000
# Pos yang dipakai menampung kekurangan kalau SEMUA pos bernilai 0.
# 26d dipilih krn paling universal (air, listrik, gas, pulsa, angkutan).
POS_PENAMPUNG_MINIMAL = "operasional"

# Urutan kandidat pemotongan kalau pos terbesar tidak cukup menutupi 26a:
# lanjut ke pos terbesar berikutnya. Kunci = nama field di RencanaPengeluaran.
POS_PENGELUARAN_KANDIDAT_POTONG = (
    "biaya_produksi", "biaya_pembelian", "operasional", "non_operasional",
)

KEPEMILIKAN_MODAL_DEFAULT = {
    "pribadi": "100", "nonprofit": "0", "korporasi_publik": "0",
    "korporasi_nonpublik": "0", "pemerintah": "0", "asing": "0",
}

# ---------------------------------------------------------------------------
# FORMAT STANDAR input usaha (input_usaha.xlsx, tab input_usaha; nama lama: sheet
# "Agenda" tab gabungan — 2026-09-13). Beda dari backlog salin dokumen sumber: tiap kolom sheet ini SUDAH berupa jawaban
# final per rincian form (tidak ada 10%, tidak ada file export). Dipakai
# gabungan_loader.py / fill_gabungan.py / main_gabungan.py.
# ---------------------------------------------------------------------------

# Segmen URL list PENDATAAN: /survey/{SURVEY_ID}/{ini}. Sheet gabungan tidak
# punya kolom ini. Nilai di bawah KONSTAN di seluruh 90 baris backlog lama
# (12 PPL berbeda), jadi tampaknya ID periode survei, bukan per-PPL — tapi
# belum diuji utk PPL gabungan. Bisa ditimpa: main_gabungan.py --assignment-id.
ASSIGNMENT_ID_GABUNGAN = "fd68e454-ba45-4b85-8205-f3bf777ded24"

# MODE SATU SUBSLS + SATU AKUN (ketetapan user 2026-09-14). Sebagian subsls
# sudah ditandai selesai sehingga tidak bisa ditambah assignment, jadi SEMUA
# dokumen dibuat di SATU subsls oleh SATU akun PPL; wilayah asli tiap baris
# (kolom idsubsls sheet) dipindahkan belakangan lewat "ubah alokasi wilayah".
# Isi keduanya (atau pakai --subsls-tunggal / --akun-tunggal). Akun ini harus
# punya assignment PAPI di subsls tsb (lihat ganti_moda/). Kosong = main_gabungan
# menolak jalan kecuali diberi --per-baris (alur lama: subsls & akun per baris).
GABUNGAN_SUBSLS_TUNGGAL = ""
GABUNGAN_AKUN_TUNGGAL = ""
# Satu login ±12 jam berisiko sesi SSO kedaluwarsa -> login ulang tiap N baris.
GABUNGAN_BARIS_PER_SESI = 40

# Peta batas SUBSLS kabupaten (GeoJSON, properti `idsubsls`/`nmkec`/`nmdesa`/`nmsls`,
# periode 2025_1) — dipakai input_gabungan/rencana_ubah_wilayah.py utk memeriksa
# apakah titik koordinat baris jatuh di subsls tujuan. Di luar repo (±15 MB),
# isi path-nya di config_lokal.py atau lewat --peta.
PETA_SLS_PATH = os.environ.get("FASIH_PETA_SLS", "")

# 13f "Apa produk utama yang dihasilkan?" WAJIB di form, tapi TIDAK ADA
# kolomnya di sheet gabungan (maupun sheet asalnya). True = salin teks 13a
# apa adanya — preseden record manual 3 (KBLI 47772, sukses terkirim) yang
# 13f-nya sama persis dgn 13a. Kalau sheet kelak punya kolom "13. f.",
# kolom itu yang dipakai. False = baris tanpa 13f di-skip.
GABUNGAN_13F_DARI_13A = True

# 13a "kegiatan utama" minimal 15 KARAKTER (file-validation template keg_utama:
# `val.length < 15` -> GALAT "Tuliskan kegiatan utama usaha dengan jelas dan
# lengkap", dibaca 2026-09-22). Isian kertas sering pendek ("WARUNG", "JUAL
# SAYUR"). Ketetapan user 2026-09-22: 13a yang kurang dilengkapi JUDUL KBLI-nya
# (kolom "Judul KBLI" sheet kalau ada, kalau tidak judul opsi Master KBLI yang
# terpilih di form), mis. "JUAL SAYUR" -> "JUAL SAYUR (PERDAGANGAN)".
#   "sedikit" = kata judul ditambahkan satu per satu sampai >= 15 karakter
#   "penuh"   = seluruh judul KBLI ditambahkan -> "JUAL SAYUR (PERDAGANGAN ECERAN SAYURAN)"
#   ""        = tidak dilengkapi -> baris berhenti 13A_KURANG_15_KARAKTER
# 13a yang sudah >= 15 karakter TIDAK diubah. Mode murni tidak pernah melengkapi.
MIN_KARAKTER_13A = 15
LENGKAPI_13A_DGN_KBLI = "sedikit"
# 13f (produk utama) minimal 4 karakter (lengthInput template). Data tahap 2 punya
# isian sependek "GAS"/"ATK"/"BIR"/"BBM" (110 baris) — semuanya perdagangan eceran
# (KBLI 47xx), jadi ketetapan user 2026-09-23: tambahkan kata di bawah ini
# ("GAS" -> "GAS ECERAN"; huruf mengikuti isian aslinya). Kalau masih kurang
# panjang, dilengkapi judul KBLI spt 13a; kalau itu pun tidak bisa (KBLI kosong)
# baris berhenti 13F_KURANG_4_KARAKTER. "" = langsung pakai judul KBLI.
MIN_KARAKTER_13F = 4
LENGKAPI_13F_DGN = "ECERAN"

# "Nama Jalan/Gang/Komplek" kosong di 242 baris gabungan. Label field di dump
# DOM TIDAK bertanda wajib (*), berbeda dgn field wajib lain — tapi belum
# pernah diuji dikosongkan. False = skip baris itu (aman, perilaku lama);
# True = biarkan kosong & tandai review (uji dulu 1 baris sebelum massal).
GABUNGAN_IZINKAN_JALAN_KOSONG = False

# MODE MURNI format standar: setiap isian form diambil APA ADANYA dari Excel
# hasil pendataan lapangan — TANPA aturan/default/koreksi skrip:
#   - nama dokumen & 8b = kolom sheet apa adanya (bukan "<nama> (<12a>)"),
#   - Nama Jalan tidak dilengkapi nama wilayah, Blok/Nomor kosong tidak jadi "-",
#   - 13f tidak disalin dari 13a, 13b4 tidak diturunkan dari kategori KBLI,
#   - 19/20 & "Pilih UMKM dalam satu SLS" tidak memakai default config,
#   - koreksi data khusus Buleleng (KOREKSI_NAMA, KOREKSI_PEKERJA, badan usaha
#     dari awalan PT/CV/UD, BUMDES) TIDAK diterapkan — pelanggaran aturan form
#     dilaporkan sbg masalah (baris di-skip), bukan diperbaiki diam-diam.
# Form meminta sesuatu yang kosong di Excel -> baris di-skip (offline kalau bisa
# diketahui dari data, selain itu SKIP_<kode> saat pengisian), TIDAK ditebak.
# False = perilaku Buleleng (aturan & koreksi di atas aktif). Disarankan True
# untuk pengguna baru — set di inti/config_lokal.py.
GABUNGAN_MODE_MURNI = False

# ---------------------------------------------------------------------------
# FORMAT TAHAP 2 (bahan/input_tahap2.xlsx — hasil pendataan KERTAS SE2026
# tahap 2, 2026-09-22). Dipakai inti/tahap2_loader.py + input_tahap2/.
#
# Format ini JAUH lebih pendek dari FORMAT STANDAR: hanya rincian yang
# benar-benar ditanyakan di kuesioner kertas. Rincian lain tetap WAJIB di
# fasih-web, jadi diisi dari TAHAP2_DEFAULT di bawah — NILAINYA KETETAPAN
# USER (2026-09-22), bukan tebakan skrip, dan setiap pemakaiannya dicatat
# sbg ASUMSI di kolom review_disarankan audit. Tambahkan kolomnya di Excel
# (mis. "11a", "13c") kalau suatu baris perlu nilai lain — kolom sheet
# SELALU menang atas default ini.
# ---------------------------------------------------------------------------
TAHAP2_DEFAULT = {
    "jenis_kawasan": "10. Di luar kawasan",              # 8d
    "punya_nib": "2. Tidak",                             # 10a
    "tidak_nib": DEFAULT_10C_ALASAN_TANPA_NIB,           # 10c
    "badan_usaha": "13. Bukan Badan Usaha",              # 11a
    "lap_keuangan": "2. Tidak",                          # 11d
    "lokasi_usaha": DEFAULT_13C_TEMPAT_USAHA,            # 13c
    "digital": DEFAULT_16C_TEKNOLOGI_DIGITAL,            # 16c (hanya kalau 16a Ya)
    "produksi_lingkungan": "3. Tidak sama sekali",       # 17a
    "produk_seni": "2. Tidak",                           # 18
    "barang_non_pddk": "2. Tidak",                       # 23a
    "jasa_non_pddk": "2. Tidak",                         # 23b
    "beli_jasa_non_pddk": "2. Tidak",                    # 23c
    "nomor_domisili": "-",                               # Blok/Nomor Rumah (SE2026-P)
    # Rincian 29 (kepemilikan modal): 100% pribadi, sama dgn KEPEMILIKAN_MODAL_DEFAULT.
    "pribadi": "100", "non_profit": "0", "publik": "0",
    "non_publik": "0", "pemerintah": "0", "asing": "0",
    # Nilai yang jalur skrip memang hardcode (lihat gabungan_loader.NILAI_TETAP).
    "ubah_sls": "2. Tidak",                              # rincian 8
    "is_new": "Bangunan Lainnya (Selain Tempat Tinggal dan Campuran)",
    "ada_bang_usaha": "2. Baru",
    "keberadaan_usaha": "2. Baru",
    "kode_bang": "1. Bangunan Khusus Usaha",
    "pilih_umkm_sls": "Tidak Ada",
    "nama_info_list": "Lainnya",
}

# Kodepos per DESA (10 digit pertama idsubsls). Kodepos dialokasikan per desa,
# jadi seluruh SLS dalam satu desa memakai nilai yang sama (lihat
# export_source.kodepos_dari_export). Template tahap 2 tidak punya kolom
# kodepos; urutan sumbernya: kolom "kodepos" di sheet -> KODEPOS_BY_IDSUBSLS
# (persis) -> dict ini -> turunan mayoritas KODEPOS_BY_IDSUBSLS desa itu ->
# --kodepos di CLI. Semuanya gagal -> baris di-skip, TIDAK ditebak.
KODEPOS_BY_DESA = {
    "5108010010": "81155",   # GEROKGAK / PATAS — contoh Buleleng
}

# 13b1/b2/b3 tidak ada kolomnya di template tahap 2 padahal wajib di form.
# Ketetapan user 2026-09-22: DITURUNKAN dari golongan KBLI (2 digit pertama),
# bukan default tetap — mayoritas baris tahap 2 adalah perdagangan eceran.
# Golongan di luar daftar ini -> ketiganya "2. Tidak" (form lalu merender
# 13b4, yang diisi dari kategori lapangan usaha 13h seperti alur lama).
# --- Ketetapan user 2026-09-22 utk data asli tahap 2 (1.796 baris) -----------
# Usaha yang MULAI beroperasi 2026: form mengganti 26-29 dgn 30-33 (SATU BULAN
# terakhir) + 31e "bulan beroperasi". Kuesioner kertas menanyakan hal yang sama
# versi bulanan, jadi kolom 26-29 sheet DIISIKAN ke 30-33 apa adanya, dan 31e
# hanya mencentang bulan di bawah. False = baris seperti ini di-skip (perilaku lama).
TAHAP2_ISI_VARIAN_BULANAN = True
TAHAP2_BULAN_OPERASI = ("AGUSTUS",)
MINIMAL_TOTAL_RUPIAH_BULANAN = 10_000   # 30f & 31c (file-validation "minimal 10.000")
# Kolom TOTAL sheet (Rp26/27c/28c/24.Total) beda dgn jumlah rinciannya: "rincian"
# = rincian dikirim apa adanya (form menghitung total sendiri), selisihnya hanya
# ditandai; "skip" = baris di-skip TOTAL_TIDAK_COCOK (perilaku lama).
TAHAP2_TOTAL_BEDA = "rincian"
# Kolom "16b1-b6" berisi 5 nilai (4 PPL selalu begitu, 92 baris): dianggap b1..b5
# berurutan, b6 "Lainnya" diisi nilai ini (ketetapan user 2026-09-23). "" = skip
# 16B_TIDAK_JELAS (perilaku lama). Kelimanya "2" padahal 16a Ya tetap ditolak 16B_TANPA_YA.
TAHAP2_16B_LIMA_NILAI_B6 = "2. Tidak"
# 16a Ya tapi kolom 16b tidak memuat satu pun Ya ("2" / "2,2,2,2,2"; 77 baris data
# 2026-09-24, PPL yang sama SELALU menulis begitu) -> 16b6 "Lainnya" = Ya, b1-b5
# tetap Tidak (ketetapan user 2026-09-24). False = skip 16B_TANPA_YA (perilaku lama).
TAHAP2_16B_TANPA_YA_JADI_B6 = True
# 26f/27c (bulanan 30f/31c) > 0 tapi < minimal form (100.000 / 10.000): kekurangannya
# ditambahkan ke pos terbesar (ketetapan user 2026-09-24, sama dgn aturan backlog
# lama). Total 0 = tidak ada data -> TETAP di-skip DI_BAWAH_MINIMAL, tidak dikarang.
TAHAP2_NAIKKAN_KE_MINIMAL = True
# 26a > 0 tapi 24a2 (pekerja dibayar) = 0 -> form mewajibkan 26a = 0. Ketetapan user
# 2026-09-24: semua pekerja dipindah ke DIBAYAR (24a2 = 24a2 + 24b2, 24b2 = 0), 26a
# tetap. False = skip 26A_HARUS_0_TANPA_PEKERJA_DIBAYAR (perilaku lama).
TAHAP2_UPAH_ADA_PEKERJA_JADI_DIBAYAR = True
# Usaha pecahan: beberapa baris dgn akun+idsubsls+8b+12a SAMA tapi 13f beda (satu
# warung, produk berbeda) -> nama dokumen & 8b diberi 13f: "<8b> <13f> (<12a>)"
# (ketetapan user 2026-09-23). 13f juga sama -> tetap BARIS_GANDA. False = perilaku lama.
TAHAP2_PEMBEDA_13F_UTK_GANDA = True
# Nama dokumen yang MASIH kembar persis sesudah pembeda 13f dipakai (13f-nya sama
# juga, mis. baris 1214/1223 "toko ni luh sri ameni" gas LPG & 1362/1363 sabun/sampo
# Yuda — cuma angka uangnya yang beda) dibedakan bertahap (ketetapan user 2026-09-24):
# nama DESA dulu, lalu nama KECAMATAN, dan kalau keduanya sama persis juga (baris
# dalam satu subsls) barulah PENOMORAN "2", "3", ... Dipakai HANYA pada baris yang
# memang bentrok; baris lain kuncinya tidak berubah, jadi audit lama tetap cocok.
# False = perilaku lama (baris kembar di-skip BARIS_GANDA / NAMA_TUMPANG_TINDIH).
TAHAP2_PEMBEDA_WILAYAH_UTK_KEMBAR = True
# Kolom "16b1-b6" yang cuma berisi SATU nilai "1"/"YA": dulu keenam rincian diisi Ya.
# Ketetapan user 2026-09-24: yang Ya hanya ketiga rincian di bawah — menerima pesanan
# (16b1), membeli bahan baku (16b4) & promosi (16b5); b2/b3/b6 jadi "2. Tidak".
# Kolom per rincian & bentuk lain ("1,2,1,...", "B1,B3") TIDAK terpengaruh.
# () = perilaku lama (keenamnya Ya).
TAHAP2_16B_YA_TUNGGAL = ("internet_pesanan", "internet_beli", "internet_promosi")
# 16b1 (menerima pesanan lewat internet) = Ya tapi 27d (persentase pendapatan online)
# kosong/0 -> 27d diisi angka ini (ketetapan user 2026-09-24, baris 1556-1559).
# Pesanan masuk lewat internet berarti ada pendapatan online, jadi 0 tidak konsisten.
# 0 = matikan (27d dibiarkan apa adanya).
TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN = 10
# 12a nama pengusaha kosong atau "-" (baris 1595-1597) -> ketetapan user 2026-09-24:
# pakai nama di dalam KURUNG pada nama usaha kalau ada ("KIOS MADE (NI KETUT SRI)"
# -> "NI KETUT SRI"); kalau tidak ada, awalan ini + nama usaha ("PEMILIK KIOS MADE").
# "" = matikan (baris tetap di-skip WAJIB_KOSONG).
TAHAP2_PENGUSAHA_KOSONG_AWALAN = "PEMILIK"
# Judul KBLI yang tidak berbagi SATU KATA PUN dgn 13a/13f ditandai utk ditinjau
# (ketetapan user 2026-09-24, baris 1730: "sewa sound system" tapi KBLI 43213
# "pemasangan sistem elektronika"). Form MENERIMA KBLI itu — jadi ini tidak
# pernah jadi GALAT & tidak bisa ditangkap dari pesan form; ketahuannya cuma dari
# isian sheet sendiri. TANDA saja, BUKAN skip: kecocokan kata itu kasar (13a bisa
# memakai kata sehari-hari yang tidak ada di judul resmi KBLI), jadi keputusan
# mengganti KBLI tetap di tangan pemeriksa — di form bisa lewat tombol generate
# KBLI lalu opsi 1. False = matikan penandaan.
TAHAP2_TANDAI_KBLI_TIDAK_NYAMBUNG = True
# Nama usaha memuat BUMDes/Bumdes/Badan Usaha Milik Desa -> 11a "6. BUM Desa",
# 11d catatan keuangan "1. Ya", 29 modal pemerintah 100% (ketetapan user 2026-09-24;
# aturan & nilai SAMA dgn koreksi format standar 2026-09-15, lihat koreksi_bumdes()).
# Sebelum ini koreksi itu hanya jalan di format standar, jadi baris BUMDES tahap 2
# lolos cek offline sbg SIAP lalu GALAT di form ("status badan usaha harus berkode 6").
# Ketiganya dibetulkan sekaligus: form menolak kode 6 yang 11d-nya Tidak atau yang
# modal pemerintahnya tidak dominan, jadi membetulkan 11a saja tidak menyelesaikan.
# False = baris BUMDES tahap 2 dibiarkan spt semula (akan GALAT di form).
TAHAP2_KOREKSI_BUMDES = True
# Kata yang diabaikan saat mencocokkan 13a/13f dgn judul KBLI (terlalu umum,
# hampir semua judul KBLI memuatnya -> kalau dihitung, semua baris terlihat cocok).
KATA_UMUM_KBLI = frozenset("""
dan atau yang untuk dengan di ke dari pada serta lainnya lain jasa aktivitas usaha
perdagangan eceran besar industri pengolahan barang produk bukan termasuk golongan
kegiatan penyediaan pelayanan penjualan berbagai macam utama khusus umum ini itu
""".split())
# 13d/13e (input & proses produksi, muncul kalau 13b1 Ya & 13b2 Tidak) tidak ada
# di kuesioner kertas -> diisi dari JUDUL KBLI (kolom sheet 13d/13e tetap menang).
TAHAP2_13DE_DARI_KBLI = True
# KBLI kategori B-F / golongan 56 tidak punya 26c di form -> 26c dijumlahkan ke 26b.
TAHAP2_26C_KE_26B = True
# 24 pekerja: jumlah per jenis kelamin (24a1+24b1) != jumlah per status bayar
# (24a2+24b2), atau 1 pekerja yang jenis kelaminnya beda dgn pemilik (GALAT "Cek
# konsistensi jenis kelamin pengusaha") -> seluruh pekerja dianggap berjenis
# kelamin PEMILIK (12b), jumlahnya mengikuti 24a2+24b2.
TAHAP2_PEKERJA_IKUT_JK_PEMILIK = True
# 12d NIK yang tidak valid menurut form (bukan 16 digit & bukan 7777/8888/9999 —
# mis. 15 digit, "5,11E+15" hasil Excel; 48 baris data asli 2026-09-22) diganti
# kode ini ("9999 untuk lainnya", pesan GALAT form; sama dgn NIK_OVERRIDE backlog
# lama). "" = baris di-skip NIK_TIDAK_VALID.
TAHAP2_NIK_TIDAK_VALID_JADI = "9999"
# Nomor HP/WA kosong atau tidak valid (bukan 08 + 10-13 digit — mis. "8,13E+10" hasil
# Excel; 11 baris rusak + 86 kosong di data asli 2026-09-22) diganti kode ini: pesan
# GALAT form sendiri "jika tidak ada/tidak bersedia ... diisi angka 9 sebanyak 4 kali".
# HP rusak yang diketik ke form juga membuat klik radio 8d berikutnya tidak menempel
# (akun windasariani 2026-09-22: 3 baris gagal -> login ulang beruntun). "" = skip.
TAHAP2_HP_TIDAK_VALID_JADI = "9999"

TAHAP2_13B_DARI_KBLI = (
    ((10, 33), "produk_sendiri"),   # B/C industri pengolahan -> 13b1 memproduksi barang
    ((56, 56), "layanan_mamin"),    # I gol. 56 penyediaan makan minum -> 13b2
    ((45, 47), "keg_penjualan"),    # G perdagangan besar/eceran & reparasi -> 13b3
)

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
    "nama_bangunan_usaha": "Nama Bangunan/ Usaha/ Perusahaan",  # EXACT (perhatikan spasi setelah slash)
    "keberadaan_bangunan_lainnya": "Keberadaan Bangunan Lainnya/ Usaha",  # EXACT (spasi setelah slash)
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
    "gunakan_lokasi_btn": "Gunakan Lokasi",  # EXACT (tidak dipakai lagi — lihat do_geotagging)
    "lokasi_belum_diambil": "Lokasi belum diambil",  # EXACT (empty-state #geotag)
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
    "kbli_genai_tombol": "DAPATKAN REKOMENDASI KBLI",      # EXACT (dump kbli_setelah_pilih_master)
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

    # --- PENGANTAR (dikutip persis dari dump DOM asli 2026-09-02) ---
    "perbarui_waktu_btn": "Perbarui Waktu",  # EXACT (label tombol SETELAH waktu terisi)
    "waktu_belum_diambil": "Waktu belum diambil",  # EXACT (empty-state Waktu Mulai)
}

# ---------------------------------------------------------------------------
# SELECTOR STRUKTURAL fasih-web (BUKAN teks — tidak berubah kalau bahasa UI
# diganti). Semua diverifikasi langsung dari dump DOM asli halaman Entri
# Dokumen (2026-09-02).
#
# TEMUAN PENTING: form-engine merender SETIAP komponen kuesioner dengan
# atribut id = dataKey-nya (mis. <div id="mulai">, <div id="keterangan">).
# Jadi field bisa ditarget lewat `#<dataKey>` / `[id="<dataKey>"]` — jauh
# lebih stabil daripada menebak label. Pakai --dump-dom di main.py utk
# memetakan dataKey tiap section.
#
# TEMUAN PENTING #2: form-engine HANYA merender section yang sedang AKTIF.
# Field section lain benar2 tidak ada di DOM sampai kita pindah ke sana.
# ---------------------------------------------------------------------------
SEL = {
    # Akar form-engine — penanda paling andal bahwa kuesioner sudah mount.
    "form_root": "#fasih-form",
    # Tombol navigasi bawah. Catatan: "next" HANYA dirender kalau memang ada
    # section berikutnya yang ter-enable; kalau tidak, yang muncul justru
    # tombol "submit". Jadi ada/tidaknya #fasih-form-nav-next-button adalah
    # cara paling akurat mendeteksi ujung kuesioner.
    "nav_prev": "#fasih-form-nav-prev-button",
    "nav_next": "#fasih-form-nav-next-button",
    "nav_submit": "#fasih-form-nav-submit-button",
    # Sidebar daftar section: div.fasih-form-sidebar > div[title="NAMA SECTION"]
    "sidebar_item": "div.fasih-form-sidebar > div[title]",
    # Item section yang sedang aktif ditandai class "tw:bg-primary". :not()
    # mencegah salah tangkap item non-aktif yang kebetulan punya varian
    # "tw:hover:bg-primary/..." di daftar class-nya.
    "sidebar_item_active": (
        'div.fasih-form-sidebar > div[title][class*="bg-primary"]'
        ':not([class*="hover:bg-primary"])'
    ),
    "sidebar_toggle": '[aria-label="sidebar-toggle"]',
    # Floating toolbar kanan — ikon dari tabler-icons, class-nya stabil.
    "toolbar_save": "button:has(svg.tabler-icon-device-floppy)",
    "toolbar_refresh": "button:has(svg.tabler-icon-refresh)",
    # Link aksi di baris list PENDATAAN. Teksnya bisa "Entri" (dokumen masih
    # bisa diisi) ATAU "Tinjau" (sudah submitted/approved) — href-nya yang
    # konsisten berakhiran /entry.
    "entry_link_href": 'a[href$="/entry"]',
    # Modal "Pilih Lokasi" (geotagging). Punya id stabil — jauh lebih baik
    # daripada menebak label. Modal ini position:fixed, jadi JANGAN pakai
    # offsetParent utk mengecek visibilitasnya (selalu null utk fixed).
    "geo_lat": "#geo-latitude",
    "geo_lon": "#geo-longitude",
    "geo_acc": "#geo-accuracy",
    # Tombol locate di dalam peta. Mengetik koordinat ke #geo-latitude/
    # #geo-longitude TIDAK mengaktifkan tombol "Gunakan Lokasi" (tetap
    # disabled); yang mengaktifkannya adalah alur getCurrentPosition lewat
    # tombol ini. Koordinatnya kita kendalikan via Playwright set_geolocation.
    "geo_locate": 'button[title="Gunakan lokasi saat ini"]',
    # Kartu komponen nested (mis. "Keterangan Usaha/Perusahaan" di BLOK II).
    # Harus diklik dulu utk masuk ke detailnya — field di dalamnya tidak ada
    # di DOM sebelum itu. Atribut ini di-set form-engine, stabil.
    "nested_card": '[data-nested-view="true"]',
}

# ---------------------------------------------------------------------------
# dataKey komponen kuesioner. form-engine merender tiap komponen dengan
# id = dataKey-nya, jadi `#<dataKey>` adalah pegangan paling stabil untuk
# menargetkan field (tidak ikut berubah kalau label/bahasa UI diubah).
#
# SEMUA nilai di bawah DIVERIFIKASI dari hasil --dump-dom pada dokumen asli
# (log_screenshots/*.map.tsv), BUKAN tebakan. Kalau menambah entri baru,
# ambil dari dump juga — jangan mengarang.
# ---------------------------------------------------------------------------
DK = {
    # --- PENGANTAR ---
    # ⚠️ #kunjungan_1 BARU muncul di DOM setelah #mulai terisi (pertanyaan
    # bersyarat). Jangan simpulkan "cuma ada 1 Ambil Waktu" dari dump yang
    # diambil sebelum Waktu Mulai diisi.
    "waktu_mulai": "mulai",
    "waktu_kunjungan_1": "kunjungan_1",

    # --- BLOK I. IDENTITAS WILAYAH ---
    "prov": "prov",                # 1. Provinsi (prefilled)
    "kab": "kab",                  # 2. Kabupaten/Kota (prefilled)
    "kec": "kec",                  # 3. Kecamatan (prefilled)
    "desa": "desa",                # 4. Desa/Kelurahan (prefilled)
    "ubah_wilayah": "ubah_wilayah",  # bersyarat, biasanya HIDDEN
    "klas_desa": "klas_desa",      # 5. Klasifikasi Desa/Kelurahan (prefilled)
    "kode_sls": "kode_sls",        # 6. Kode SLS/Non-SLS/Sub-SLS (prefilled)
    "nama_sls": "nama_sls",        # 7. Nama SLS/Non-SLS (prefilled)
    "ubah_sls": "ubah_sls",        # 8. Perubahan SLS? — WAJIB, memicu rincian 9
    "kodepos": "kodepos",          # 10. Kodepos — WAJIB

    # --- SE2026 - P (judul section persis: "SE2026 - P", pakai spasi) ---
    "jenis_prelist": "jenis_prelist",              # readonly/prefilled
    "alamat_sesuai": "alamat_sesuai",              # bersyarat, biasanya HIDDEN
    "is_new": "is_new",                            # "Tambah: pilih jenis assignment"
    "pilih_umkm": "pilih_umkm",                    # Daftar Usaha Non Prelist — dibiarkan kosong
    "nama_usaha_bang": "nama_usaha_bang",          # Nama Bangunan/ Usaha/ Perusahaan
    "ada_bang_usaha": "ada_bang_usaha",            # Keberadaan Bangunan Lainnya/Usaha — WAJIB
    "jumlah_usaha_ditemukan": "jumlah_usaha_ditemukan",  # auto-terisi
    "pilih_keluarga_sls": "pilih_keluarga_sls",    # bersyarat, biasanya HIDDEN
    # Bersyarat: baru muncul SETELAH #ada_bang_usaha dijawab.
    "alamat_domisili": "alamat_domisili",          # header "Alamat"
    "jalan_domisili": "jalan_domisili",            # textarea nama jalan
    "nomor_domisili": "nomor_domisili",            # Blok/Nomor Rumah
    "no_bangunan_terbesar": "no_bangunan_terbesar",  # readonly, acuan utk no_bang
    "no_bang": "no_bang",                          # ⚠️ Nomor Urut Bangunan — JANGAN DISENTUH
    "kode_bang": "kode_bang",                      # default "1. Bangunan Khusus Usaha" — biarkan
    "geotag": "geotag",                            # Geotagging

    # --- SE2026 - L BLOK II (di dalam komponen nested; id asli bersufiks
    #     instance, mis. "nama_komersial#2001" — komponen() mencocokkan
    #     dataKey polos maupun bersufiks) ---
    # ⚠️ BEDA dari "pilih_umkm" (SE2026-P, "Daftar Usaha Non Prelist").
    # Ini combobox paling ATAS di BLOK II & hanya dirender di SLS yang
    # punya daftar UMKM prelist — hilang dari DOM begitu keberadaan_usaha
    # dijawab, jadi WAJIB diisi lebih dulu.
    "pilih_umkm_sls": "pilih_umkm_sls",
    "keberadaan_usaha": "keberadaan_usaha",   # memicu render rincian berikutnya
    "no_usaha": "no_usaha",                   # 7. Nomor Urut Usaha
    "nama_komersial": "nama_komersial",       # 8b
    "alamat_usaha": "alamat_usaha_view",      # 8c — auto dari SE2026-P
    "rt": "rt",
    "rw": "rw",
    "kode_pos_8c": "kode_pos",
    "kode_area": "kode_area",
    "no_telepon": "no_telp",
    "ekstensi": "eks",
    "email": "email",
    "no_hp_wa": "hp",
    "homepage": "website",
    "jenis_kawasan": "jenis_kawasan",
    "punya_nib": "punya_nib",                 # 10a
    # 10b — bersyarat (10a = Ya). dataKey aslinya "nib". Dulu key "nib" di dict ini
    # milik 10a -> komponen()/_komponen_wajib() me-resolve DUA KALI ("nib_nomor" ->
    # "nib" -> "punya_nib") & 10b diketik ke radio 10a (run 2026-09-15, Agenda baris 40,
    # "Input of type radio cannot be filled"). JANGAN buat key DK yang sama dgn nilai
    # key lain — dikunci tests/test_fill_gabungan.py.
    "nib_nomor": "nib",
    "alasan_tanpa_nib": "tidak_nib",          # 10c — bersyarat (10a = Tidak)
    "tempat_usaha": "lokasi_usaha",           # 13c — bersyarat (muncul stlh 13b3)
    "jumlah_varian_belum_bpom": "belum_bpom", # 20c — bersyarat (20a = Tidak)
    "status_badan_usaha": "badan_usaha",
    "laporan_keuangan": "lap_keuangan",
    "nama_pengusaha": "pengusaha",            # 12a
    "jenis_kelamin": "jk",
    "umur": "umur",
    "nik": "nik_pengusaha",                   # 12d — override 9999
    "kegiatan_utama": "keg_utama",            # 13a
    "produksi_di_lokasi": "produk_sendiri",   # 13b1
    "layanan_makan_minum": "layanan_mamin",   # 13b2
    "penjualan_barang": "keg_penjualan",
    # 13b4 — bersyarat: hanya dirender kalau 13b1, b2 & b3 SEMUANYA "2. Tidak".
    "aktivitas_jasa_tani": "keg_jasa",      # 13b3 — baru muncul stlh 13b2 dijawab
    "produk_utama": "produk",                 # 13f
    "kbli_radio": "kbli_genai",               # 13g — radio "Pilih dari Master KBLI"
    "kbli_pilihan": "kbli",                   # 13g — combobox (textarea) hasil pilihan KBLI
    "kbli_genai_tombol": "genai_button",      # 13g — tombol "DAPATKAN REKOMENDASI KBLI" (opsi GenAI masuk ke kbli_genai)
    "kategori_lapangan_usaha": "kategori",    # 13h — readonly, auto dari KBLI
    "jaringan_usaha": "jaringan",
    "pakai_internet": "internet",                    # 16a
    # 16b1-b6 + 16c + 27d: HANYA dirender kalau 16a dijawab "1. Ya".
    # Tidak ada di dump manapun sebelum 2026-09-06 karena ketiga record
    # manual & record 2513 semuanya menjawab 16a = "2. Tidak".
    "internet_pesanan": "internet_pesanan",          # 16b1 Menerima pesanan barang/jasa
    "internet_produksi": "internet_produksi",        # 16b2 Produksi barang/jasa
    "internet_distribusi": "internet_distribusi",    # 16b3 Distribusi barang/jasa
    "internet_beli": "internet_beli",                # 16b4 Membeli bahan baku online
    "internet_promosi": "internet_promosi",          # 16b5 Promosi
    "internet_lainnya": "internet_lainnya",          # 16b6 Lainnya
    "teknologi_digital": "digital",                  # 16c AI/IoT/big data/3D/blockchain/cloud
    "produk_ramah_lingkungan": "produksi_lingkungan",  # 17a
    "input_ramah_lingkungan": "perlindungan_lingkungan",  # 17b
    "karya_seni_budaya": "produk_seni",              # 18
    "izin_edar_bpom": "izin_edar",                   # 20a
    "mitra_kdkmp": "mitra_kdkmp",                    # 21
    "program_mbg": "peran_mbg",                      # 22
    "trans_barang_non_pddk": "barang_non_pddk",      # 23a
    "trans_jasa_non_pddk": "jasa_non_pddk",          # 23b
    "trans_beli_jasa_non_pddk": "beli_jasa_non_pddk",  # 23c
    "tk_laki": "tk_laki",                            # 24a1
    "tk_pr": "tk_pr",                                # 24b1
    "tk_dibayar": "tk_dibayar",                      # 24a2
    "tk_tdk_dibayar": "tk_tdk_dibayar",              # 24b2
    "tahun_mulai_komersial": "tahun_operasi",        # 25
    # rincian 26 (Pengeluaran) — 26f total dihitung otomatis oleh form
    "upah_gaji": "gaji",                             # 26a
    "biaya_produksi": "biaya_produksi",              # 26b
    "biaya_pembelian": "biaya_pembelian",            # 26c (kondisional per kategori KBLI)
    "operasional_26d": "operasional",                # 26d
    "non_operasional_26e": "non_operasional",        # 26e
    # rincian 27 (Pendapatan) — 27c total otomatis
    "nilai_penjualan": "nilai_pendapatan",           # 27a
    # --- VARIAN BULANAN (rincian 30-33) ---
    # Dirender sbg pengganti 26/27/28/29 kalau usaha MULAI BEROPERASI pada
    # tahun berjalan (terlihat di record 2566 & 2571, tahun_operasi=2026).
    # Angkanya SATU BULAN TERAKHIR, bukan setahun — jadi TIDAK bisa diisi
    # dgn nilai sumber tahunan begitu saja. Minimalnya juga beda: 10.000.
    # Dipetakan dari dump asli 2026-09-07; belum dipakai mengisi apa pun.
    "gaji_bln": "gaji_bln",                          # 30a
    "biaya_produksi_bln": "biaya_produksi_bln",      # 30b
    "biaya_pembelian_bln": "biaya_pembelian_bln",    # 30c
    "operasional_bln": "operasional_bln",            # 30d
    "non_operasional_bln": "non_operasional_bln",    # 30e
    "nilai_pendapatan_bln": "nilai_pendapatan_bln",  # 31a
    "pendapatan_lain_bln": "pendapatan_lain_bln",    # 31b
    "bulan_operasi": "bln_operasi",                  # 31e (pilih bulan)
    "aset_tanah_bln": "aset_tanah_bln",              # 32a
    "aset_lain_bln": "aset_lain_bln",                # 32b
    "luas_tanah_bln": "luas_tanah_bln",              # 32d
    "pribadi_didirikan": "pribadi_didirikan",        # 33a
    "nonprofit_didirikan": "nonprofit_didirikan",    # 33b
    "korporasi_publik_didirikan": "publik_didirikan",       # 33c
    "korporasi_nonpublik_didirikan": "nonpublik_didirikan", # 33d
    "pemerintah_didirikan": "pemerintah_didirikan",  # 33e
    "asing_didirikan": "asing_didirikan",            # 33f
    "pendapatan_lain": "pendapatan_lain",            # 27b
    "pendapatan_online": "pendapatan_online",        # 27d — bersyarat, ikut 16a="1. Ya"
    # rincian 28 (Aset). ⚠️ Nama dataKey MENYESATKAN — label aslinya:
    #   aset_usaha_thn = "28.a Nilai aset TANAH DAN BANGUNAN"  -> override 0
    #   aset_lain_thn  = "28.b Nilai aset SELAIN tanah/bangunan" -> 10% sumber
    "aset_tanah_bangunan": "aset_usaha_thn",         # 28a
    "aset_selain_tanah": "aset_lain_thn",            # 28b
    "luas_tanah_28d": "luas_tanah_thn",              # 28d — override 0
    # rincian 29 (Kepemilikan modal)
    "pribadi_perorangan": "pribadi",                 # 29a
    "nonprofit": "non_profit",                       # 29b
    "korporasi_publik": "publik",                    # 29c
    "korporasi_nonpublik": "non_publik",             # 29d
    "pemerintah_29e": "pemerintah",                  # 29e
    "asing_29f": "asing",                            # 29f

    # --- KETERANGAN PEMBERI JAWABAN ---
    "nama_pemberi_informasi": "nama_info_list",      # combobox -> "Lainnya"
    "telp_pemberi": "telp_info",
    "email_pemberi": "email_info",
    "checkbox_pernyataan": "persetujuan_responden",  # checkbox wajib

    # --- CATATAN ---
    "waktu_selesai": "waktu_selesai",   # tombol "Ambil Waktu"
    "catatan_textarea": "catatan",      # opsional, sengaja dibiarkan kosong
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
# ⚠️ DUA dict di bawah (KODEPOS_BY_IDSUBSLS & WILAYAH_BY_IDSUBSLS) berisi data
# CONTOH Kab. Buleleng — dipakai juga oleh uji offline. Untuk kabupaten lain,
# definisikan ulang keduanya di inti/config_lokal.py (format sama persis).
#
# Kodepos per idsubsls — WAJIB dilengkapi kalau backlog mencakup SLS selain
# yang sudah diketahui. Kalau idsubsls suatu baris tidak ada di dict ini,
# skrip akan berhenti & minta kodepos diisi manual (lihat main.py) drpd
# menebak/mengosongkan field wajib ini.
#
# Entri di bawah ini (38 idsubsls) BUKAN tebakan — diambil langsung dari
# field "kodepos" pada data mentah export/{No}_{assignment_id}.json (sumber
# fasih-sm asli, hasil ekspor manual No 2513-2716) via region.full_code,
# dicocokkan otomatis, bukan diketik manual satu-satu.
#
# ⚠️ CATATAN: idsubsls "5108030013000402" punya 2 nilai kodepos berbeda di
# 2 record berbeda sumbernya ("81154" vs "99999"). "99999" kelihatan sbg
# placeholder/tidak diisi (bukan kodepos valid), jadi dipakai "81154" —
# TAPI kalau nanti ada baris backlog dgn idsubsls ini yg hasilnya
# meragukan, cek manual dulu drpd percaya penuh ke nilai ini.
# ---------------------------------------------------------------------------
KODEPOS_BY_IDSUBSLS: dict[str, str] = {
    "5108080008000202": "81172",
    "5108080008000203": "81172",
    "5108080008000204": "81172",
    "5108060015000302": "81113",
    "5108010008000101": "81155",
    "5108010008000102": "81155",
    "5108010008000103": "81155",
    "5108010008000104": "81155",
    "5108070005000603": "81171",
    "5108080004000205": "81172",
    "5108080004000303": "81172",
    "5108080008000106": "81172",
    "5108080008000107": "81172",
    "5108070004000501": "81171",
    "5108070004000502": "81171",
    "5108040014000407": "81152",
    "5108070012000402": "81171",
    "5108070012000403": "81171",
    "5108070012000501": "81171",
    "5108050007000301": "81161",
    "5108050007000302": "81161",
    "5108050007000401": "81161",
    "5108020010000401": "81153",
    "5108020010000402": "81153",
    "5108020010000403": "81153",
    "5108030013000401": "81154",
    "5108030013000402": "81154",  # sumber juga pernah muncul "99999" di 1 record lain — lihat catatan di atas
    "5108030013000403": "81154",
    "5108060016000202": "81114",
    "5108060022000202": "81151",
    "5108090007000603": "81173",
    "5108090007000701": "81173",
    "5108020021000301": "81153",
    "5108080011000401": "81172",
    "5108080011000402": "81172",
    "5108080012000305": "81172",
    "5108090008000302": "81173",
    "5108090008000303": "81173",
    "5108090008000305": "81173",
    "5108060002000201": "81119",
    "5108060002000202": "81119",
}

# ---------------------------------------------------------------------------
# Wilayah (nama provinsi/kab-kota/kecamatan/desa/sls/subsls) per idsubsls —
# dipakai FasihWebSession.create_document() utk memilih 6 dropdown cascading
# "Wilayah Responden" di modal "Buat Dokumen Baru" (field ini TIDAK auto-
# prefill dari idsubsls seperti dugaan awal — tombol "Buat Dokumen" tetap
# disabled sampai semua 6 dropdown ini dipilih manual).
#
# SAMA seperti KODEPOS_BY_IDSUBSLS: nilai di bawah BUKAN tebakan, diambil
# langsung dari field region.level_1..level_6 pada data mentah
# export/{No}_{assignment_id}.json (73 idsubsls, semua Kab. Buleleng, tidak
# ada konflik nama antar record). idsubsls yg tidak ada di dict ini akan
# bikin create_document() berhenti (_fail) drpd menebak.
#
# ⚠️ CATATAN: nama "sls" & "subsls" SELALU identik di semua 73 entri
# (mis. "BANJAR KAJA KANGIN" dipakai baik utk level SLS maupun SUBSLS).
# Kemungkinan besar 1 SLS bisa punya BEBERAPA SUBSLS dgn nama tampilan yg
# SAMA (beda cuma di kode internal, mis. idsubsls ...0202/...0203/...0204).
# Kalau dropdown SUBSLS menampilkan >1 opsi dgn teks identik,
# create_document() akan pilih yg PERTAMA & log peringatan — WAJIB
# diverifikasi manual apakah pilihan itu benar (lihat log & screenshot di
# log_screenshots/ kalau ragu), terutama utk idsubsls yg SLS-nya diketahui
# beranak >1 SUBSLS.
# ---------------------------------------------------------------------------
WILAYAH_BY_IDSUBSLS: dict[str, dict[str, str]] = {
    "5108010008000101": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "GEROKGAK", "desa": "SANGGALANGIT", "sls": "BANJAR KAYU PUTIH", "subsls": "BANJAR KAYU PUTIH"},
    "5108010008000102": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "GEROKGAK", "desa": "SANGGALANGIT", "sls": "BANJAR KAYU PUTIH", "subsls": "BANJAR KAYU PUTIH"},
    "5108010008000103": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "GEROKGAK", "desa": "SANGGALANGIT", "sls": "BANJAR KAYU PUTIH", "subsls": "BANJAR KAYU PUTIH"},
    "5108010008000104": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "GEROKGAK", "desa": "SANGGALANGIT", "sls": "BANJAR KAYU PUTIH", "subsls": "BANJAR KAYU PUTIH"},
    "5108020010000401": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "KALIANGET", "sls": "BANJAR ALAS HARUM", "subsls": "BANJAR ALAS HARUM"},
    "5108020010000402": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "KALIANGET", "sls": "BANJAR ALAS HARUM", "subsls": "BANJAR ALAS HARUM"},
    "5108020010000403": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "KALIANGET", "sls": "BANJAR ALAS HARUM", "subsls": "BANJAR ALAS HARUM"},
    "5108020021000301": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "PANGKUNGPARUK", "sls": "BANJAR LABA AMERTA", "subsls": "BANJAR LABA AMERTA"},
    "5108020021000302": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "PANGKUNGPARUK", "sls": "BANJAR LABA AMERTA", "subsls": "BANJAR LABA AMERTA"},
    "5108020021000303": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "PANGKUNGPARUK", "sls": "BANJAR LABA AMERTA", "subsls": "BANJAR LABA AMERTA"},
    "5108020021000304": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SERIRIT", "desa": "PANGKUNGPARUK", "sls": "BANJAR LABA AMERTA", "subsls": "BANJAR LABA AMERTA"},
    "5108030013000401": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BUSUNGBIU", "desa": "KEDIS", "sls": "BANJAR KAJA", "subsls": "BANJAR KAJA"},
    "5108030013000402": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BUSUNGBIU", "desa": "KEDIS", "sls": "BANJAR KAJA", "subsls": "BANJAR KAJA"},
    "5108030013000403": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BUSUNGBIU", "desa": "KEDIS", "sls": "BANJAR KAJA", "subsls": "BANJAR KAJA"},
    "5108040014000102": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BANJAR", "desa": "BANJAR", "sls": "BANJAR AMBENGAN", "subsls": "BANJAR AMBENGAN"},
    "5108040014000103": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BANJAR", "desa": "BANJAR", "sls": "BANJAR AMBENGAN", "subsls": "BANJAR AMBENGAN"},
    "5108040014000104": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BANJAR", "desa": "BANJAR", "sls": "BANJAR AMBENGAN", "subsls": "BANJAR AMBENGAN"},
    "5108040014000406": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BANJAR", "desa": "BANJAR", "sls": "BANJAR MUNDUK", "subsls": "BANJAR MUNDUK"},
    "5108040014000407": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BANJAR", "desa": "BANJAR", "sls": "BANJAR MUNDUK", "subsls": "BANJAR MUNDUK"},
    "5108050007000301": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SUKASADA", "desa": "PEGADUNGAN", "sls": "BANJAR PEGADUNGAN", "subsls": "BANJAR PEGADUNGAN"},
    "5108050007000302": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SUKASADA", "desa": "PEGADUNGAN", "sls": "BANJAR PEGADUNGAN", "subsls": "BANJAR PEGADUNGAN"},
    "5108050007000401": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SUKASADA", "desa": "PEGADUNGAN", "sls": "BANJAR LONG SEGEHA", "subsls": "BANJAR LONG SEGEHA"},
    "5108060002000201": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "ANTURAN", "sls": "BANJAR PASAR", "subsls": "BANJAR PASAR"},
    "5108060002000202": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "ANTURAN", "sls": "BANJAR PASAR", "subsls": "BANJAR PASAR"},
    "5108060015000302": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "BANJAR BALI", "sls": "LINGKUNGAN TEGAL MAWAR", "subsls": "LINGKUNGAN TEGAL MAWAR"},
    "5108060016000201": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "KAMPUNG KAJANAN", "sls": "LINGKUNGAN TENGAH", "subsls": "LINGKUNGAN TENGAH"},
    "5108060016000202": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "KAMPUNG KAJANAN", "sls": "LINGKUNGAN TENGAH", "subsls": "LINGKUNGAN TENGAH"},
    "5108060022000201": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108060022000202": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108060022000203": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108060022000204": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108060022000205": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108060022000207": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "PENARUKAN", "sls": "LINGKUNGAN KETEWEL", "subsls": "LINGKUNGAN KETEWEL"},
    "5108070004000501": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "BEBETIN", "sls": "BANJAR TABANG", "subsls": "BANJAR TABANG"},
    "5108070004000502": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "BEBETIN", "sls": "BANJAR TABANG", "subsls": "BANJAR TABANG"},
    "5108070004000503": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "BEBETIN", "sls": "BANJAR TABANG", "subsls": "BANJAR TABANG"},
    "5108070004000601": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "BEBETIN", "sls": "BANJAR MANUKSESA", "subsls": "BANJAR MANUKSESA"},
    "5108070005000601": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SUDAJI", "sls": "BANJAR DUKUH", "subsls": "BANJAR DUKUH"},
    "5108070005000603": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SUDAJI", "sls": "BANJAR DUKUH", "subsls": "BANJAR DUKUH"},
    "5108070012000402": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SANGSIT", "sls": "BANJAR CELUK", "subsls": "BANJAR CELUK"},
    "5108070012000403": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SANGSIT", "sls": "BANJAR CELUK", "subsls": "BANJAR CELUK"},
    "5108070012000501": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SANGSIT", "sls": "BANJAR TEGAL", "subsls": "BANJAR TEGAL"},
    "5108080004000205": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAJUN", "sls": "BANJAR PUDEH", "subsls": "BANJAR PUDEH"},
    "5108080004000301": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAJUN", "sls": "BANJAR BAKUNGAN", "subsls": "BANJAR BAKUNGAN"},
    "5108080004000303": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAJUN", "sls": "BANJAR BAKUNGAN", "subsls": "BANJAR BAKUNGAN"},
    "5108080008000106": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAMBLANG", "sls": "BANJAR KELOD KAUH", "subsls": "BANJAR KELOD KAUH"},
    "5108080008000107": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAMBLANG", "sls": "BANJAR KELOD KAUH", "subsls": "BANJAR KELOD KAUH"},
    "5108080008000202": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAMBLANG", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080008000203": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAMBLANG", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080008000204": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "TAMBLANG", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080011000401": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080011000402": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080011000403": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080011000404": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KAJA KANGIN", "subsls": "BANJAR KAJA KANGIN"},
    "5108080011000601": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KUTA BANDING", "subsls": "BANJAR KUTA BANDING"},
    "5108080011000603": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KUTA BANDING", "subsls": "BANJAR KUTA BANDING"},
    "5108080011000604": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "KUBUTAMBAHAN", "sls": "BANJAR KUTA BANDING", "subsls": "BANJAR KUTA BANDING"},
    "5108080012000204": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "BUKTI", "sls": "BANJAR BUKTI", "subsls": "BANJAR BUKTI"},
    "5108080012000205": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "BUKTI", "sls": "BANJAR BUKTI", "subsls": "BANJAR BUKTI"},
    "5108080012000305": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "BUKTI", "sls": "BANJAR MEKAR SARI", "subsls": "BANJAR MEKAR SARI"},
    "5108080012000306": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "KUBUTAMBAHAN", "desa": "BUKTI", "sls": "BANJAR MEKAR SARI", "subsls": "BANJAR MEKAR SARI"},
    "5108090006000606": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "TEJAKULA", "sls": "BANJAR ANTAPURA", "subsls": "BANJAR ANTAPURA"},
    "5108090006000607": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "TEJAKULA", "sls": "BANJAR ANTAPURA", "subsls": "BANJAR ANTAPURA"},
    "5108090006000608": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "TEJAKULA", "sls": "BANJAR ANTAPURA", "subsls": "BANJAR ANTAPURA"},
    "5108090006000701": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "TEJAKULA", "sls": "BANJAR TEGAL SUMAGA", "subsls": "BANJAR TEGAL SUMAGA"},
    "5108090006000702": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "TEJAKULA", "sls": "BANJAR TEGAL SUMAGA", "subsls": "BANJAR TEGAL SUMAGA"},
    "5108090007000601": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "LES", "sls": "BANJAR KAWANAN", "subsls": "BANJAR KAWANAN"},
    "5108090007000603": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "LES", "sls": "BANJAR KAWANAN", "subsls": "BANJAR KAWANAN"},
    "5108090007000701": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "LES", "sls": "BANJAR LEMPEDU", "subsls": "BANJAR LEMPEDU"},
    "5108090008000302": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "PENUKTUKAN", "sls": "BANJAR BELIMBING", "subsls": "BANJAR BELIMBING"},
    "5108090008000303": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "PENUKTUKAN", "sls": "BANJAR BELIMBING", "subsls": "BANJAR BELIMBING"},
    "5108090008000304": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "PENUKTUKAN", "sls": "BANJAR BELIMBING", "subsls": "BANJAR BELIMBING"},
    "5108090008000305": {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "TEJAKULA", "desa": "PENUKTUKAN", "sls": "BANJAR BELIMBING", "subsls": "BANJAR BELIMBING"},
}

# ---------------------------------------------------------------------------
# Timpaan lokal — inti/config_lokal.py (TIDAK ikut git, lihat .gitignore).
# Salin dari templates/config_lokal.contoh.py. Setiap nama di atas yang
# didefinisikan ulang di sana MENANG (password, akun tunggal, KODE_KAB,
# KODEPOS_BY_IDSUBSLS, WILAYAH_BY_IDSUBSLS, PETA_SLS_PATH, ASSIGNMENT_ID_GABUNGAN,
# dst.). Uji offline (tests/) mengabaikannya lewat FASIH_ABAIKAN_CONFIG_LOKAL=1
# supaya hasil uji tidak bergantung pada data lokal masing-masing kabupaten.
# ---------------------------------------------------------------------------
if os.environ.get("FASIH_ABAIKAN_CONFIG_LOKAL") != "1":
    try:
        from inti.config_lokal import *  # noqa: E402,F401,F403
    except ModuleNotFoundError as _e:
        if _e.name != "inti.config_lokal":
            raise

PESAN_PASSWORD_KOSONG = (
    "STOP: password akun belum diisi. Salin templates/config_lokal.contoh.py ke "
    "inti/config_lokal.py lalu isi FIXED_PASSWORD (atau set variabel lingkungan "
    "FASIH_PASSWORD). Password TIDAK PERNAH ditulis di inti/config.py (file itu ikut git)."
)
