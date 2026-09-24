# -*- coding: utf-8 -*-
"""Uji loader & pemeriksaan sheet "gabungan" — offline, tanpa browser/VPN.
Jalankan: python tests/test_gabungan_loader.py
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

from inti.gabungan_loader import (
    _pasangan_termuat, cocokkan_wilayah_dokumen, format_nama_usaha, load_gabungan, parse_pilihan_baris,
    periksa_semua,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


# Judul PERSIS seperti sheet asli 2026-09-13 (termasuk judul ganda,
# baris baru di akhir judul, dan "8.c." tanpa spasi).
KOLOM_CONTOH = [
    ("Akun PML", "pml@gmail.com"), ("Akun PPL", "PPL.Satu@gmail.com"),
    ("Pilih PROVINSI", "51"), ("Pilih KABUPATEN/KOTA", "08"), ("Pilih KECAMATAN", "60"),
    ("Pilih DESA", "014"), ("Pilih SLS", "3"), ("Pilih SUBSLS", "2"),
    ("Nama Keluarga/Bangunan/Usaha", "APOTEK SEHAT"),
    ("8. Apakah mengalami perubahan SLS (pemekaran/penggabungan/perubahan nama/perubahan batas?)", "2. Tidak"),
    ("10. Kodepos", "81113"), ("Tambah :", "Bangunan Lainnya (Selain Tempat Tinggal dan Campuran)"),
    ("Nama Keluarga/Bangunan/Usaha", "APOTEK SEHAT"), ("Keberadaan Bangunan Lainnya/ Usaha\n", "  2. Baru"),
    ("Nama Jalan/Gang/Komplek/Gedung/dll (Tuliskan dengan rinci)", "JL. MAWAR INDAH"), ("Blok/Nomor Rumah", "-"),
    ("Nomor Urut Bangunan", "3"), ("Kode Penggunaan Bangunan", " 1. Bangunan Khusus Usaha"),
    ("Latitude", "-8.11"), ("Longitude", "115.09"), ("Pilih UMKM dalam satu SLS yang sama", "Tidak Ada"),
    ("Keberadaan Usaha", "2. Baru"), ("8. b. Nama komersial usaha/perusahaan", "APOTEK SEHAT"),
    ("8.c. Alamat usaha/perusahaan", "JL. MAWAR"), ("Nomor HP/whatsapp", "9999"),
    ("8. d. Jenis kawasan beroperasi\n", "10. Di luar kawasan"),
    ("10. a. Apakah memiliki Nomor Induk Berusaha (NIB)?", "2. Tidak"), ("10. b. Tuliskan NIB", ""),
    ("10. c. Apa alasan utama tidak memiliki NIB?\n", "3. Tidak memerlukan NIB"),
    ("11. a. Apa status badan usaha dari usaha/perusahaan ini?", "13. Bukan Badan Usaha"),
    ("11. d. Apakah mempunyai laporan/catatan keuangan?", "2. Tidak"),
    ("12. a. Nama Pengusaha / Penanggung Jawab", "I MADE"), ("12. b. Jenis Kelamin\n", "1. Laki-laki"),
    ("12. c. Umur", "40"), ("12. d. Nomor Induk Kependudukan (NIK)\n", "9999"),
    ("13. a. Apa kegiatan utama usaha/perusahaan ini? Tuliskan selengkapnya", "Perdagangan eceran obat"),
    ("13. b1. Apakah memproduksi barang di lokasi ini?", "2. Tidak"),
    ("13. b2. Apakah menyediakan layanan makan minum?", "2. Tidak"),
    ("13. b3. Apakah melakukan penjualan barang?", "1. Ya"),
    ("13. b4. Pilih salah satu aktivitas yang dilakukan:", "3. Perdagangan Besar dan Eceran"),
    ("13. c. Di mana usaha tersebut biasa dilakukan?", "4. Toko, ruko, dan sejenisnya"),
    ("Pilih dari Master KBLI", "47721"), ("14. a. Apa jaringan usaha dari usaha/perusahaan ini?", "1. Tunggal"),
    ("16. a. Apakah usaha/perusahaan ini menggunakan internet dalam menjalankan usaha?", "1. Ya"),
    ("16. b1. Menerima pesanan barang/jasa", "2. Tidak"), ("16. b2. Produksi barang/jasa", "2. Tidak"),
    ("16. b3. Distribusi barang/jasa", "2. Tidak"), ("16. b4. Membeli bahan baku online", "2. Tidak"),
    ("16. b5. Promosi", "1. Ya"), ("16. b6. Lainnya\n", "2. Tidak"),
    ("16. c. Apakah usaha/perusahaan ini memanfaatkan teknologi digital", "2. Tidak"),
    ("17. a. Apakah usaha/perusahaan ini memproduksi barang/jasa yang ramah lingkungan?", "3. Tidak sama sekali"),
    ("17. b. Apakah usaha/perusahaan ini menggunakan input untuk tujuan perlindungan lingkungan", "2. Tidak"),
    ("18. Apakah usaha/perusahaan ini menggunakan produk karya seni", "2. Tidak"),
    ("21. Apakah usaha/perusahaan ini bermitra dengan Koperasi Desa/Kelurahan Merah Putih (KDKMP)?", "2. Tidak"),
    ("22. Apakah usaha/perusahaan ini terlibat dalam program Makan Bergizi Gratis (MBG)?", "5. Tidak terlibat MBG"),
    ("23. a. Penjualan dan/atau pembelian barang", "1. Ya"), ("23. b. Penjualan jasa\n", "2. Tidak"),
    ("23. c. Pembelian jasa", "2. Tidak"),
    ("24. a1. Pekerja laki-laki", "1"), ("24. b1. Pekerja perempuan", "2"),
    ("24. a2. Pekerja dibayar", "1"), ("24. b2. Pekerja tidak dibayar", "2"),
    ("25. Tahun berapa usaha/perusahaan ini mulai beroperasi secara komersial?", "2018"),
    ("idsubsls", "5108060014000302"),
    ("26. a. Total upah dan gaji, serta jaminan sosial pegawai", "12000000"),
    ("26. b. Biaya produksi\n", "0"), ("26. c. Biaya pembelian barang yang terjual", "30000000"),
    ("26. d. Biaya operasional (air, listrik, gas, internet, pulsa, pemeliharaan, biaya angkutan, dll.)", "900000"),
    ("26. e. Biaya non-operasional", "0"),
    ("27. a. Nilai produksi/pendapatan/penjualan barang dan jasa", "50000000"),
    ("27. b. Pendapatan lainnya yang dihasilkan perusahaan", "0"),
    ("27. d. Berapa persentase pendapatan yang dilakukan secara online ?", "0"),
    ("28. a. Nilai aset tanah dan bangunan pada 31 Desember 2025", "0"),
    ("28. b. Nilai aset selain tanah dan bangunan pada 31 Desember 2025", "2500000"),
    ("28. d. Berapa luas tanah yang dikuasai dan digunakan untuk kegiatan usaha pada 31 Desember 2025 ? (m2)", "40"),
    ("29. a. Pribadi/Perorangan", "100"), ("29. b. Lembaga Nonprofit yang Melayani Rumah Tangga", "0"),
    ("29. c. Korporasi Publik", "0"), ("29. d. Korporasi Non Publik", "0"), ("29. e. Pemerintah\n", "0"),
    ("29. f. Asing\n", "0"), ("Nama Pemberi Informasi\n", "Lainnya"),
]
JUDUL = [k for k, _ in KOLOM_CONTOH]


def baris(**ubah):
    """Satu baris valid; `ubah` = {indeks_kolom: nilai_baru}."""
    nilai = [v for _, v in KOLOM_CONTOH]
    for i, v in ubah.items():
        nilai[int(i[1:])] = v
    return nilai


def idx(awalan):
    return next(i for i, j in enumerate(JUDUL) if j.startswith(awalan))


def muat(*daftar_baris, satu_subsls=False):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "gabungan.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(JUDUL)
            w.writerow([""] * len(JUDUL))  # baris kosong harus dilewati
            for b in daftar_baris:
                w.writerow(b)
        rows = load_gabungan(p)
    return rows, periksa_semua(rows, tahun_berjalan=2026, mode_satu_subsls=satu_subsls)


def u(awalan, nilai):
    return {f"c{idx(awalan)}": nilai}


# --- baris valid ---
rows, hasil = muat(baris())
r = rows[0]
check("baris kosong dilewati, nomor baris = baris sheet", r.baris, 3)
check("judul ganda 'Nama Keluarga' -> kolom pertama", r.nama, "APOTEK SEHAT")
check("spasi opsi dinormalkan", r["ada_bang_usaha"], "2. Baru")
check("akun PPL di-lowercase", r.akun_ppl, "ppl.satu@gmail.com")
check("wilayah zero-pad ('60'->'060', '3'->'0003')", r.idsubsls_pilih, "5108060014000302")
check("13f disalin dari 13a", r.produk_utama, "Perdagangan eceran obat")
check("13b4 tidak dirender kalau 13b3 Ya -> opsi '3. Perdagangan' tidak dipersoalkan",
      hasil[3].status, "SIAP")
check("baris valid ditandai review 13f", hasil[3].tanda, ["13f disalin dari 13a (sheet tidak punya kolom 13f)"])
check("kunci stabil & 10 hex", (len(r.kunci), r.kunci == muat(baris())[0][0].kunci), (10, True))

# --- penamaan usaha "<nama> (<pemilik 12a>)" (ketetapan user 2026-09-14) ---
check("nama dokumen = nama (12a)", r.nama_dokumen, "APOTEK SEHAT (I MADE)")
check("8b ikut format", r.nama_komersial, "APOTEK SEHAT (I MADE)")
check("kunci tetap dari nama MENTAH", r.kunci == muat(baris(**u("12. a.", "I KETUT")))[0][0].kunci, True)
check("format tidak digandakan (ejaan pemilik dari 12a)", format_nama_usaha("WARUNG A (I MADE)", "i made"), "WARUNG A (i made)")
check("tanpa spasi sebelum kurung dirapikan", format_nama_usaha("WARUNG A(I MADE)", "I MADE"), "WARUNG A (I MADE)")
check("12a kosong -> nama apa adanya", format_nama_usaha("WARUNG A", ""), "WARUNG A")
# pemilik sudah tertulis di nama -> yang di luar kurung dihapus (ketetapan user 2026-09-14)
for label, nama, pemilik, want in (
    ("nyata: 55 karakter jadi 35", "PANGKALAN GAS PUTU MILA WIRAYANTI", "PUTU MILA WIRAYANTI",
     "PANGKALAN GAS (PUTU MILA WIRAYANTI)"),
    ("beda huruf besar", "PRAKTIK BIDAN GST AYU ANIK ARIANI", "Gst Ayu Anik Ariani", "PRAKTIK BIDAN (Gst Ayu Anik Ariani)"),
    ("gelar ikut", "PANGKALAN GAS NI NYOMAN CONTOH, SE. MM", "NI NYOMAN CONTOH, SE. MM",
     "PANGKALAN GAS (NI NYOMAN CONTOH, SE. MM)"),
    ("pemisah di tepi dibuang", "UD. WIDE/ SUARDANTI", "SUARDANTI", "UD. WIDE (SUARDANTI)"),
    ("pemilik di tengah", "WARUNG KETUT TOYA JAYA", "KETUT TOYA", "WARUNG JAYA (KETUT TOYA)"),
    ("bukan kata utuh -> tidak dihapus", "TOKO MADELINE", "MADE", "TOKO MADELINE (MADE)"),
    ("nama pemilik tidak utuh -> format biasa", "PANGKALAN GAS DHARMA HADI", "DHARMA HADI KUSUMA",
     "PANGKALAN GAS DHARMA HADI (DHARMA HADI KUSUMA)"),
    ("nama = pemilik", "KETUT TOYA", "KETUT TOYA", "(KETUT TOYA)"),
    ("idempoten", "PANGKALAN GAS (BUDIMAN)", "BUDIMAN", "PANGKALAN GAS (BUDIMAN)"),
    ("nyata baris 393: kurung tak tertutup -> satu kurung saja",
     "PRAKTIK DOKTER I NYOMAN CONTOH PUTRA SP.P (K)", "I Nyoman Contoh Putra Sp.P (K",
     "PRAKTIK DOKTER (I Nyoman Contoh Putra Sp.P K)"),
    ("kurung lain di nama dibuang", "APOTEK SEHAT (CABANG 2)", "I MADE", "APOTEK SEHAT CABANG 2 (I MADE)"),
):
    check(f"format nama: {label}", format_nama_usaha(nama, pemilik), want)

nyata = "APOTEK INA FARMA 2"  # baris 246: + "(DESAK KADEK INDAH PURNAMAYANTI)" = 51 karakter
rows_p, h = muat(baris(**u("Nama Keluarga", nyata), **u("8. b.", nyata), **u("12. a.", "DESAK KADEK INDAH PURNAMAYANTI")))
# Ketetapan user 2026-09-14 (Agenda1-1): format lengkap > 50 -> nama usaha saja tanpa kurung.
check("8b & nama dokumen berformat > 50 karakter -> nama usaha saja, SIAP + tanda",
      (rows_p[0].nama_komersial, rows_p[0].nama_dokumen, h[3].status,
       any("tanpa (12a)" in t for t in h[3].tanda)),
      ("APOTEK INA FARMA 2", "APOTEK INA FARMA 2", "SIAP", True))
jabatan = "Bidan/Perawat Penanggung Jawab Pustu"  # Agenda1-1 baris 2: 12a berisi jabatan
rows_p, h = muat(baris(**u("Nama Keluarga", "PUSKESMAS PEMBANTU (SUMBER) KLAMPOK"),
                       **u("8. b.", "PUSKESMAS PEMBANTU SUMBER KLAMPOK"), **u("12. a.", jabatan)))
check("12a jabatan: tanpa kurung, kurung di nama dibuang, 12a utuh",
      (rows_p[0].nama_dokumen, rows_p[0].nama_komersial, rows_p[0]["pengusaha"], h[3].status),
      ("PUSKESMAS PEMBANTU SUMBER KLAMPOK", "PUSKESMAS PEMBANTU SUMBER KLAMPOK", jabatan, "SIAP"))
panjang = "PRAKTIK DOKTER GIGI CATHRINE VIVIAN DAISY OCTAVIANA"  # 51 karakter tanpa kurung pun
_, h = muat(baris(**u("Nama Keluarga", panjang), **u("8. b.", panjang), **u("12. a.", "X Y")))
check("nama usaha sendiri > 50 -> tetap skip, tidak dipotong", h[3].status, "SKIP_DATA_8B_TERLALU_PANJANG")
rows_p, h = muat(baris(**u("8. b.", "APOTEK X"), **u("12. a.", "I MADE")))
check("8b ikut format penamaan", (rows_p[0].nama_komersial, h[3].status), ("APOTEK X (I MADE)", "SIAP"))
rows_k, h = muat(baris(**u("12. a.", "Dr. X Sp.P (K")))
check("kurung tak tertutup di 12a -> satu kurung di belakang, tetap SIAP",
      (rows_k[0].nama_dokumen, h[3].status), ("APOTEK SEHAT (Dr. X Sp.P K)", "SIAP"))

# --- kasus skip nyata dari sheet 2026-09-13 ---
_, h = muat(baris(**u("11. a.", "1. Perseroan Terbatas (PT)/CV")))
check("11a 'PT/CV' bukan opsi form", h[3].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")

# Ketetapan user 2026-09-15: 11a "PT/CV" diturunkan dari awalan nama; PT/CV dipindah ke belakang.
for nama, want_opsi, want_nama in (
    ("PT. WIRA DEK SU", "1.a. Perseroan (PT/NV, PT Persero, PT Tbk, PT Persero Tbk, Perseroan Daerah",
     "WIRA DEK SU, PT (I MADE)"),
    ("CV. DEWI KUNTI DUA/ SPBU 5480315", "7. Persekutuan Komanditer (CV)", "DEWI KUNTI DUA/ SPBU 5480315, CV (I MADE)"),
    ("UD.SINAR PRIANDANA SARI", "13. Bukan Badan Usaha", "UD.SINAR PRIANDANA SARI (I MADE)"),
    ("SPBU 54.811.03", "1.a. Perseroan (PT/NV, PT Persero, PT Tbk, PT Persero Tbk, Perseroan Daerah",
     "SPBU 54.811.03 (I MADE)"),
):
    rows_b, h = muat(baris(**u("Nama Keluarga", nama), **u("8. b.", nama), **u("11. a.", "1. Perseroan Terbatas (PT)/CV"),
                           **u("10. a.", "1. Ya"), **u("10. b.", "9999"), **u("10. c.", "0")))
    check(f"11a PT/CV dari awalan '{nama}' (10c '0' diabaikan krn 10a Ya)",
          (rows_b[0]["badan_usaha"], rows_b[0].nama_dokumen, rows_b[0].nama_komersial, h[3].status,
           rows_b[0].kunci == muat(baris(**u("Nama Keluarga", nama)))[0][0].kunci),
          (want_opsi, want_nama, want_nama, "SIAP", True))
rows_bd, h = muat(baris(**u("Nama Keluarga", "PANGKALAN GAS BUMDES PANCA GIRI KENCANA"),
                        **u("11. d.", "2. Tidak")))
check("BUMDES (Agenda2 baris 239): 11a 6, 11d Ya, modal pemerintah 100, SIAP",
      (rows_bd[0]["badan_usaha"], rows_bd[0]["lap_keuangan"],
       [rows_bd[0][k] for k in ("pribadi", "non_profit", "publik", "non_publik", "pemerintah", "asing")], h[3].status),
      ("6. BUM Desa", "1. Ya", ["0", "0", "0", "0", "100", "0"], "SIAP"))
_, h = muat(baris(**u("11. a.", "1. Perseroan Terbatas (PT)/CV")))
check("11a PT/CV tanpa awalan dikenal -> tetap skip", h[3].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")
_, h = muat(baris(**u("10. a.", "2. Tidak"), **u("10. c.", "0")))
check("10c '0' saat 10a Tidak -> tetap skip", h[3].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")
rows_n, h = muat(baris(**u("Nama Keluarga", "PUSKESMAS PEMBANTU DESA LOKAPAKSA DI BANJAR DINAS SORGA"),
                       **u("8. b.", "PUSKESMAS PEMBANTU DESA LOKAPAKSA DI BANJAR DINAS SORGA"), **u("12. a.", "X")))
check("KOREKSI_NAMA (Agenda1-1 baris 90): 55 -> nama pengganti, SIAP",
      (rows_n[0].nama_dokumen, h[3].status), ("PUSTU DESA LOKAPAKSA BANJAR DINAS SORGA (X)", "SIAP"))

_, h = muat(baris(**u("24. a2.", "0"), **u("24. b2.", "1")))
check("24a1+24b1 != 24a2+24b2", h[3].status, "SKIP_DATA_PEKERJA_24_TIDAK_KONSISTEN")

# Ketetapan user 2026-09-14: pola PERSIS 0/2/0/1 (Agenda1-1 66 baris) -> 0/2/0/2; pola lain tidak ditebak.
rows_k, h = muat(baris(**u("24. a1.", "0"), **u("24. b1.", "2"), **u("24. a2.", "0"), **u("24. b2.", "1"),
                       **u("26. a.", "0")))
check("pola 24 0/2/0/1 dikoreksi jadi tidak dibayar 2, SIAP + tanda",
      (tuple(rows_k[0][k] for k in ("tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar")), h[3].status,
       any("ketetapan user" in t for t in h[3].tanda)),
      (("0", "2", "0", "2"), "SIAP", True))
_, h = muat(baris(**u("24. a1.", "0"), **u("24. b1.", "3"), **u("24. a2.", "0"), **u("24. b2.", "1")))
check("pola 24 lain tetap skip", h[3].status, "SKIP_DATA_PEKERJA_24_TIDAK_KONSISTEN")

_, h = muat(baris(**u("idsubsls", "5108060014200100")))
check("idsubsls beda dgn kolom Pilih", h[3].status, "SKIP_DATA_WILAYAH_TIDAK_KONSISTEN")

_, h = muat(baris(**u("12. c.", "")))
check("umur kosong (wajib *)", h[3].status, "SKIP_DATA_WAJIB_KOSONG")

for umur, want in (("0", "SKIP_DATA_UMUR_DI_LUAR_10_99"), ("9", "SKIP_DATA_UMUR_DI_LUAR_10_99"),
                   ("100", "SKIP_DATA_UMUR_DI_LUAR_10_99"), ("10", "SIAP"), ("99", "SIAP")):
    _, h = muat(baris(**u("12. c.", umur)))
    check(f"umur {umur} (form: wajib 10-99; Agenda1-1.xlsx semua 0)", h[3].status, want)

_, h = muat(baris(**u("Nama Jalan", "")))
check("nama jalan kosong -> skip (GABUNGAN_IZINKAN_JALAN_KOSONG=False)", h[3].status, "SKIP_DATA_WAJIB_KOSONG")

# Fixture CSV tanpa nama wilayah & 8c "JL. MAWAR" -> alamat pendek tidak bisa dilengkapi.
for jalan, want in (("0", "SKIP_DATA_JALAN_KURANG_10_HURUF"), ("BR. KAJANAN", "SKIP_DATA_JALAN_KURANG_10_HURUF"),
                    ("JL. P. ARU NO.56.", "SKIP_DATA_JALAN_KURANG_10_HURUF"),
                    ("BANJAR DINAS KAJA", "SIAP"), ("-", "SIAP")):
    _, h = muat(baris(**u("Nama Jalan", jalan)))
    check(f"nama jalan '{jalan}' tanpa nama wilayah (validasi >= 10 huruf)", h[3].status, want)

# Alamat pendek dilengkapi nama wilayah (ketetapan user 2026-09-14) — kasus nyata sheet.
from inti.gabungan_loader import lengkapi_alamat, jumlah_huruf
WIL = {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "SAWAN", "desa": "SUDAJI"}
for label, jalan, wil, want in (
    ("banjar pendek + desa", "BR. KAJANAN", {**WIL, "desa": "BENGKALA"}, "BR. KAJANAN, DESA BENGKALA"),
    ("desa sudah tertulis -> lompat ke kecamatan", "DS. SUDAJI", WIL, "DS. SUDAJI, KECAMATAN SAWAN"),
    ("'0' dianggap kosong", "0", {**WIL, "desa": "SUMBERKLAMPOK"}, "DESA SUMBERKLAMPOK"),
    ("desa pendek -> + kecamatan", "0", {**WIL, "desa": "MUSI", "kecamatan": "GEROKGAK"}, "DESA MUSI, KECAMATAN GEROKGAK"),
    ("banjar dari config didahulukan", "1", {**WIL, "sls": "BANJAR KAYU PUTIH"}, "1, BANJAR KAYU PUTIH"),
    ("sudah >= 10 huruf -> tidak diubah", "BANJAR DINAS KAJA", WIL, "BANJAR DINAS KAJA"),
    ("'-' tidak diubah", "-", WIL, "-"),
    ("tanpa nama wilayah -> tetap pendek", "0", {}, "0"),
):
    got = lengkapi_alamat(jalan, wil)
    check(f"lengkapi alamat: {label}", (got, got in ("0", "-") or jumlah_huruf(got) >= 10), (want, True))

rows_8c, h = muat(baris(**u("Nama Jalan", "0"),
                        **u("8.c.", "Desa/Kel. TINGA-TINGA, Kec. GEROKGAK, BULELENG, BALI, 81155")))
check("nama wilayah cadangan dari 8c -> alamat dilengkapi & SIAP",
      (rows_8c[0].jalan_lengkap, h[3].status), ("DESA TINGA-TINGA", "SIAP"))

_, h = muat(baris(**u("25.", "2026")))
check("mulai beroperasi tahun berjalan -> varian bulanan", h[3].status, "SKIP_DATA_VARIAN_BULANAN")

_, h = muat(baris(**u("13. b3.", "2. Tidak")))
check("13b4 dirender & '3. Perdagangan' bukan opsi", h[3].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")
_, h = muat(baris(**u("13. b3.", "2. Tidak"), **u("13. b4.", "1. Jasa")))
check("13b4 dirender & '1. Jasa' valid", h[3].status, "SIAP")

_, h = muat(baris(**u("29. a.", "90")))
check("29 tidak berjumlah 100", h[3].status, "SKIP_DATA_MODAL_29_BUKAN_100")

# 24a2 dinolkan (24b2 menyerap semuanya) supaya yang diuji benar-benar 26f, bukan
# aturan 26a/24a2 > Rp 50.000 yang ikut kena kalau ada pekerja dibayar tapi 26a = 0.
_, h = muat(baris(**u("26. a.", "0"), **u("26. c.", "50000"), **u("26. d.", "0"),
                  **u("24. a2.", "0"), **u("24. b2.", "3")))
check("26f < 100.000", h[3].status, "SKIP_DATA_DI_BAWAH_MINIMAL")

_, h = muat(baris(**u("16. b5.", "2. Tidak")))
check("16a Ya tanpa satu pun 16b Ya", h[3].status, "SKIP_DATA_16B_TANPA_YA")

_, h = muat(baris(**u("10. a.", "1. Ya"), **u("10. c.", "")))
check("10a Ya tanpa 10b", h[3].status, "SKIP_DATA_WAJIB_KOSONG")

_, h = muat(baris(), baris(**u("Nama Keluarga", "APOTEK SEHAT 2")))
check("nama terkandung di nama lain utk PPL sama", (h[3].status, h[4].status),
      ("SKIP_DATA_NAMA_TUMPANG_TINDIH", "SKIP_DATA_NAMA_TUMPANG_TINDIH"))

# satu list: "GAS (MADE)" terkandung di "PANGKALAN GAS (MADE)" (beda PPL)
_, h = muat(baris(**u("Nama Keluarga", "GAS"), **u("12. a.", "MADE")),
            baris(**u("Akun PPL", "ppl.dua@gmail.com"), **u("Nama Keluarga", "PANGKALAN GAS"), **u("12. a.", "MADE")),
            satu_subsls=True)
check("nama DOKUMEN terkandung di nama dokumen lain -> skip",
      (h[3].status, h[4].status), ("SKIP_DATA_NAMA_TUMPANG_TINDIH", "SKIP_DATA_NAMA_TUMPANG_TINDIH"))

_, h = muat(baris(), baris())
check("baris ganda", h[3].status, "SKIP_DATA_BARIS_GANDA")

_, h = muat(baris(), baris(**u("Nama Keluarga", "TOKO A"), **u("10. Kodepos", "81153")),
            baris(**u("Nama Keluarga", "TOKO B")))
check("kodepos minoritas di desa sama -> tanda, bukan skip",
      (h[4].status, any("kodepos 81153" in t for t in h[4].tanda)), ("SIAP", True))

check("parse_pilihan_baris", sorted(parse_pilihan_baris("2, 5,9-7")), [2, 5, 7, 8, 9])

# --- mode satu subsls + satu akun (ketetapan user 2026-09-14) ---
_, h = muat(baris(**u("idsubsls", "5108060014200100")), satu_subsls=True)
check("satu subsls: wilayah baris tidak konsisten -> tanda, bukan skip",
      (h[3].status, any("ubah alokasi" in t for t in h[3].tanda)), ("SIAP", True))

beda_ppl = {**u("Akun PPL", "ppl.dua@gmail.com"), **u("idsubsls", "5108060014000301"),
            **u("Pilih SUBSLS", "1")}
_, h = muat(baris(), baris(**beda_ppl))
check("per baris: nama sama beda PPL -> tidak bentrok", (h[3].status, h[4].status), ("SIAP", "SIAP"))
_, h = muat(baris(), baris(**beda_ppl), satu_subsls=True)
check("satu subsls: nama dokumen sama beda PPL -> bentrok di list satu akun",
      (h[3].status, h[4].status), ("SKIP_DATA_NAMA_TUMPANG_TINDIH", "SKIP_DATA_NAMA_TUMPANG_TINDIH"))
check("  bentrok dilaporkan sekali per baris", len(h[3].masalah), 1)

_, h = muat(baris(**u("Nama Keluarga", "SARI"), **u("12. a.", "MADE")),
            baris(**beda_ppl, **u("Nama Keluarga", "WARUNG"), **u("12. a.", "SARI")), satu_subsls=True)
check("satu subsls: nama mentah ada di nama dokumen lain -> tanda risiko SKIP_DOKUMEN_NAMA_LAMA",
      (h[3].status, any("SKIP_DOKUMEN_NAMA_LAMA" in t for t in h[3].tanda)), ("SIAP", True))

# cocokkan_wilayah_dokumen: format nilai field belum pernah terekam
ID = "5108060014000302"
REF = {"provinsi": "BALI", "kabkota": "BULELENG", "kecamatan": "BULELENG", "desa": "BANJAR BALI"}
for label, nilai, ref, want in (
    ("kode pendek", {"prov": "51", "kab": "08", "kec": "060", "desa": "014", "kode_sls": "000302"}, None, "COCOK"),
    ("kode panjang", {"prov": "51", "kab": "5108", "kec": "5108060", "desa": "5108060014", "kode_sls": ID}, None, "COCOK"),
    ("[kode] NAMA, angka di nama diabaikan", {"desa": "[014] BANJAR 2", "kode_sls": "[0003] BANJAR 2"}, None, "COCOK"),
    ("nama saja + kode sls", {"prov": "BALI", "desa": "BANJAR BALI", "kode_sls": "0003"}, REF, "COCOK"),
    ("kode sls beda", {"desa": "014", "kode_sls": "000401"}, None, "BEDA"),
    ("desa beda lewat nama", {"desa": "KALIASEM", "kode_sls": "000302"}, REF, "BEDA"),
    ("kode sls kosong", {"prov": "51", "kode_sls": ""}, None, "TIDAK_TERBACA"),
    ("kode sls cuma nama", {"kode_sls": "BANJAR X"}, None, "TIDAK_TERBACA"),
):
    check(f"wilayah dokumen: {label}", cocokkan_wilayah_dokumen(nilai, ID, ref)[0], want)

# --- FORMAT STANDAR: kolom opsional utk jenis usaha lain (produksi, halal, BPOM) ---
OPSIONAL = [
    ("13. d. Input yang digunakan", ""), ("13. e. Proses produksi", ""),
    ("13. f. Apa produk utama yang dihasilkan?", ""),
    ("19. a. Apakah usaha/perusahaan ini menghasilkan produk bersertifikat halal?", ""),
    ("19. b. Jumlah varian produk yang sudah bersertifikat halal BPJPH", ""),
    ("19. c. Berapa jumlah varian produk yang belum bersertifikat halal BPJPH?", ""),
    ("20. a. Apakah usaha/perusahaan ini memiliki izin edar?", ""),
    ("20. b. Berapa jumlah varian produk yang sudah memiliki izin edar BPOM?", ""),
    ("20. c. Berapa jumlah varian produk yang belum memiliki izin edar BPOM?", ""),
]
JUDUL_STD = JUDUL + [j for j, _ in OPSIONAL]


def _idx_std(key):
    from inti.gabungan_loader import KOLOM, _norm_judul
    return next(i for i, j in enumerate(JUDUL_STD) if _norm_judul(j).startswith(KOLOM[key]))


def muat_std(murni=False, **isi):
    """Satu baris sheet berkolom lengkap (termasuk kolom opsional). `isi` = {key loader: nilai}."""
    nilai = baris() + ["" for _ in OPSIONAL]
    for key, v in isi.items():
        nilai[_idx_std(key)] = v
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "std.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(JUDUL_STD)
            w.writerow(nilai)
        rows = load_gabungan(p, murni=murni)
    return rows[0], periksa_semua(rows, tahun_berjalan=2026)[rows[0].baris]


r, h = muat_std()
check("std: kolom opsional kosong -> tetap SIAP", h.status, "SIAP")
r, h = muat_std(produk="Obat-obatan")
check("std: 13f dari kolom sendiri (bukan salinan 13a)", (r.produk_utama, h.tanda), ("Obat-obatan", []))

PRODUKSI = dict(produk_sendiri="1. Ya", keg_utama="Membuat keripik singkong", kbli="10794",
                biaya_produksi="30000000", biaya_pembelian="0")
r, h = muat_std(**PRODUKSI)
check("std: 13b1 Ya tanpa 13d/13e -> WAJIB_KOSONG sebelum dokumen dibuat",
      (h.status, "input_produksi" in h.pesan and "proses_produksi" in h.pesan), ("SKIP_DATA_WAJIB_KOSONG", True))
r, h = muat_std(**PRODUKSI, input_produksi="Singkong, minyak", proses_produksi="Mengiris, menggoreng")
check("std: 13b1 Ya + 13d/13e terisi -> SIAP", h.status, "SIAP")
r, h = muat_std(**{**PRODUKSI, "biaya_pembelian": "5000000"}, input_produksi="x", proses_produksi="y")
check("std: KBLI kategori C + 26c > 0 -> skip (form tidak punya 26c)", h.status, "SKIP_DATA_26C_KATEGORI_TANPA_26C")
# 13c ikut diisi kode 5: golongan 56 = usaha makan-minum, dan form hanya menerima
# 13c kode 5-11 utk usaha makan-minum (lihat uji 13C_MAMIN_BUKAN_5_11 di bawah).
r, h = muat_std(kbli="56304", biaya_pembelian="1000000", lokasi_usaha="5. Kedai, stan, tenda")
check("std: golongan 56 + 26c > 0 -> skip", h.status, "SKIP_DATA_26C_KATEGORI_TANPA_26C")
check("std: kategori G + 26c > 0 -> tetap SIAP", muat_std()[1].status, "SIAP")

r, h = muat_std(halal="1. Ya, oleh BPJPH", sudah_halal="2", belum_halal="0",
                izin_edar="2. Ya, bukan oleh BPOM", sudah_bpom="1", belum_bpom="3")
check("std: 19/20 dari sheet terbaca & SIAP",
      (h.status, r["halal"], r["sudah_halal"], r["izin_edar"], r["belum_bpom"]),
      ("SIAP", "1. Ya, oleh BPJPH", "2", "2. Ya, bukan oleh BPOM", "3"))
check("std: opsi 20a bukan opsi form -> skip", muat_std(izin_edar="Ya")[1].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")
check("std: opsi 19a bukan opsi form -> skip", muat_std(halal="Belum")[1].status, "SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM")
check("std: 20c bukan bilangan -> skip", muat_std(belum_bpom="dua")[1].status, "SKIP_DATA_ANGKA_TIDAK_VALID")

# --- MODE MURNI: isian 100% dari Excel, tanpa aturan/default/koreksi skrip ---
LENGKAP = dict(produk="Obat-obatan", pengusaha="I MADE", nama="APOTEK SEHAT", nama_komersial="APOTEK SEHAT")
r, h = muat_std(murni=True, **LENGKAP)
check("murni: baris lengkap SIAP tanpa tanda", (h.status, h.tanda), ("SIAP", []))
check("murni: nama dokumen & 8b apa adanya (tanpa '(12a)')", (r.nama_dokumen, r.nama_komersial),
      ("APOTEK SEHAT", "APOTEK SEHAT"))
check("non-murni: tetap '<nama> (<12a>)'", muat_std(**LENGKAP)[0].nama_dokumen, "APOTEK SEHAT (I MADE)")
r, h = muat_std(murni=True)
check("murni: 13f kosong TIDAK disalin dari 13a -> WAJIB_KOSONG",
      (r.produk_utama, h.status, "produk (13f)" in h.pesan), ("", "SKIP_DATA_WAJIB_KOSONG", True))
r, h = muat_std(murni=True, **LENGKAP, nomor_domisili="")
check("murni: Blok/Nomor kosong tetap kosong (non-murni '-')",
      (r.nomor_rumah, muat_std(nomor_domisili="")[0].nomor_rumah), ("", "-"))
r, h = muat_std(murni=True, **{**LENGKAP, "jalan_domisili": "BR. X"})
check("murni: Nama Jalan < 10 huruf tidak dilengkapi -> skip",
      (h.status, "mode murni" in h.pesan), ("SKIP_DATA_JALAN_KURANG_10_HURUF", True))
r, h = muat_std(murni=True, **LENGKAP, tk_laki="0", tk_pr="2", tk_dibayar="0", tk_tdk_dibayar="1")
check("murni: KOREKSI_PEKERJA tidak diterapkan -> 24 tidak konsisten", h.status,
      "SKIP_DATA_PEKERJA_24_TIDAK_KONSISTEN")
check("non-murni: KOREKSI_PEKERJA tetap jalan",
      muat_std(**LENGKAP, tk_laki="0", tk_pr="2", tk_dibayar="0", tk_tdk_dibayar="1")[0]["tk_tdk_dibayar"], "2")
r, h = muat_std(murni=True, **{**LENGKAP, "nama": "BUMDES MAJU", "nama_komersial": "BUMDES MAJU"})
check("murni: BUMDES tidak dikoreksi -> dilaporkan", (r["badan_usaha"], h.status),
      ("13. Bukan Badan Usaha", "SKIP_DATA_BUMDES_BUKAN_KODE_6"))
r, h = muat_std(murni=True, **{**LENGKAP, "nama_komersial": "CV. MAJU"})
check("murni: 8b diawali CV -> dilaporkan", h.status, "SKIP_DATA_8B_DIAWALI_CV")

# --- nama tab: "input_usaha" (baku) & "gabungan" (nama lama Buleleng) sama-sama diterima ---
import openpyxl  # noqa: E402


def muat_xlsx(tab_isi: dict):
    """tab_isi = {nama tab: nama usaha di baris data} -> nama usaha yang terbaca loader."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tab.xlsx"
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for tab, nama in tab_isi.items():
            ws = wb.create_sheet(tab)
            ws.append(JUDUL)
            ws.append(baris(**u("Nama Keluarga", nama)))
        wb.save(p)
        return [r.nama for r in load_gabungan(p)]


check("tab 'input_usaha' dibaca", muat_xlsx({"input_usaha": "BARU"}), ["BARU"])
check("tab lama 'gabungan' tetap dibaca", muat_xlsx({"gabungan": "LAMA"}), ["LAMA"])
check("keduanya ada -> 'input_usaha' dipakai", muat_xlsx({"gabungan": "LAMA", "input_usaha": "BARU"}), ["BARU"])
try:
    muat_xlsx({"Sheet lain": "X"})
    check("tab tidak dikenal -> ditolak", "tidak ditolak", "ValueError")
except ValueError:
    check("tab tidak dikenal -> ditolak", "ValueError", "ValueError")

# --- indeks n-gram pemeriksaan nama = hasil yang SAMA dgn adu semua pasangan ---
# Pemeriksaan NAMA_TUMPANG_TINDIH dulu mengadu setiap nama dgn setiap nama; pada
# sheet tahap 2 (4.099 baris) itu ±9,5 menit sebelum prompt "YA". _pasangan_termuat
# memakai indeks 4-gram — uji ini mengunci bahwa hasilnya tetap identik, termasuk
# untuk nama yang lebih pendek dari 4 huruf (tidak punya potongan utuh di indeks).
import random  # noqa: E402

def kasar(jarum, jerami):
    return [(i, j) for i, na in enumerate(jarum) for j, nb in enumerate(jerami) if na in nb]

CONTOH = ["", "A", "TOK", "TOKO", "TOKO BERAS", "TOKO BERAS (I KETUT CONTOH)",
          "toko beras", "TOKO BERAS (I KETUT CONTOH)", "WARUNG", "WARUNG MAKAN (NI MADE CONTOH)",
          "BERAS", "(I KETUT CONTOH)", "PT. X", "X"]
def sama(jarum, jerami):
    """(cocok?, jumlah pasangan) — daftar penuhnya terlalu panjang utk dicetak."""
    got, want = _pasangan_termuat(jarum, jerami), kasar(jarum, jerami)
    return (got == want, len(want))

check("indeks n-gram = adu semua pasangan (contoh)", sama(CONTOH, CONTOH), (True, 51))

acak = random.Random(20260923)
kata = ["TOKO", "WARUNG", "BERAS", "GAS", "AB", "CONTOH", "I", "PUTU", "MADE", "X", "YZ"]
acakan = [" ".join(acak.choice(kata) for _ in range(acak.randint(1, 4))) for _ in range(120)]
check("indeks n-gram = adu semua pasangan (acak)", sama(acakan, acakan)[0], True)
lain = [" ".join(acak.choice(kata) for _ in range(acak.randint(1, 3))) for _ in range(80)]
check("indeks n-gram = adu semua pasangan (dua daftar beda)", sama(lain, acakan)[0], True)

# --- idsubsls dari rincian 1-6 BLOK I (dipakai --izinkan-wilayah-beda) ---
from inti.gabungan_loader import idsubsls_dari_wilayah  # noqa: E402

BLOK1 = {"prov": "[51] BALI", "kab": "[08] BULELENG", "kec": "[060] BULELENG",
         "desa": "[006] BANYUASRI", "kode_sls": "000116"}
check("idsubsls disusun dari rincian 1-6", idsubsls_dari_wilayah(BLOK1), "5108060006000116")
check("format kode polos juga terbaca",
      idsubsls_dari_wilayah({"prov": "51", "kab": "08", "kec": "060", "desa": "006", "kode_sls": "000205"}),
      "5108060006000205")
# Sebagian tidak terbaca -> "" (JANGAN menebak: nilai ini dipakai jadi subsls di audit)
check("kode_sls kosong -> kosong", idsubsls_dari_wilayah({**BLOK1, "kode_sls": ""}), "")
# Kode SLS di form kadang 4 digit (SLS saja, subsls tidak ditampilkan) — diterima,
# hasilnya 14 digit: cukup utk memastikan masih di kabupaten yang sama, TIDAK cukup
# utk dicatat sbg subsls (main_gabungan hanya menimpa audit kalau 16 digit).
check("kode_sls 4 digit -> 14 digit", idsubsls_dari_wilayah({**BLOK1, "kode_sls": "0002"}), "51080600060002")
check("kode_sls 3 digit -> kosong", idsubsls_dari_wilayah({**BLOK1, "kode_sls": "002"}), "")
check("nama tanpa kode -> kosong", idsubsls_dari_wilayah({**BLOK1, "desa": "BANYUASRI"}), "")

# --- 26c hanya dirender utk perdagangan (aturan sama dgn 30c) ---
# Dulu aturannya "kategori B-F / golongan 56" saja, sehingga KBLI lain lolos
# pemeriksaan offline lalu gagal di tengah pengisian (SKIP_26C_TIDAK_DIRENDER)
# setelah dokumennya terlanjur dibuat. Terbukti live 2026-09-23.
from inti.gabungan_loader import kbli_26b_wajib_positif, kbli_tanpa_26c  # noqa: E402

for kbli, tanpa in (("47241", False), ("46100", True), ("47909", True), ("61209", False),
                    ("61201", True), ("01464", True), ("86101", True), ("56304", True), ("", False)):
    check(f"26c tidak dirender utk KBLI {kbli or '(kosong)'}", kbli_tanpa_26c(kbli), tanpa)
# 26b wajib > 0 TETAP aturan lamanya (B-F & gol 56) — jangan ikut diperlebar,
# kalau tidak baris jasa ber-26b nol ikut ter-skip tanpa dasar.
check("26b wajib > 0 hanya B-F & gol 56",
      [kbli_26b_wajib_positif(k) for k in ("56304", "10110", "86101", "47241")],
      [True, True, False, False])

# --- 13f minimal 4 karakter: dilengkapi judul KBLI seperti 13a ---
# Data tahap 2 punya 13f sependek "GAS" (37 baris) — form menolaknya (lengthInput).
from inti.gabungan_loader import lengkapi_13a  # noqa: E402
from inti.config import MIN_KARAKTER_13F  # noqa: E402

from inti.gabungan_loader import lengkapi_13f  # noqa: E402

check("13f 'GAS' -> 'GAS ECERAN'", lengkapi_13f("GAS", "[G][47772] PERDAGANGAN ECERAN GAS"), "GAS ECERAN")
check("huruf mengikuti isian asli", lengkapi_13f("Gas", ""), "Gas Eceran")
check("13f pendek tanpa KBLI pun tertolong", lengkapi_13f("ATK", ""), "ATK ECERAN")
check("13f yang sudah cukup panjang tidak diubah",
      lengkapi_13f("BERAS ECERAN", "[G][47241] PERDAGANGAN ECERAN BERAS"), "BERAS ECERAN")
check("13f kosong tetap kosong (WAJIB_KOSONG yang menanganinya)", lengkapi_13f("", "X"), "")
# Kalau kata pelengkapnya dikosongkan di config, jalur judul KBLI yang dipakai.
check("tanpa kata pelengkap -> judul KBLI",
      lengkapi_13a("GAS", "[G][47772] PERDAGANGAN ECERAN GAS TABUNGAN", minimal=MIN_KARAKTER_13F),
      "GAS (PERDAGANGAN)")

# --- Aturan form yang dulu baru ketahuan SAAT pengisian (audit gabungan 22-23 Sep 2026) ---
# Keempat GALAT di bawah semuanya soal isian sheet, jadi dokumen terlanjur dibuat
# lalu nyangkut DRAFT ber-GALAT. Sekarang dicegat `--cek` sebelum browser dibuka.
from inti.gabungan_loader import (  # noqa: E402
    kbli_kategori_ditolak, kbli_makan_minum, kode_opsi,
)

check("kode_opsi angka dua digit", [kode_opsi(v) for v in ("5. Kedai", "10. Keliling", "11. Daring")], [5, 10, 11])
check("kode_opsi tanpa angka -> None", [kode_opsi(v) for v in ("Tidak Ada", "", "1 Ya")], [None, None, None])
check("makan-minum = golongan 56",
      [kbli_makan_minum(k) for k in ("56102", "56304", "47241", "")], [True, True, False, False])
check("kategori KBLI yang ditolak 13g",
      [kbli_kategori_ditolak(k) for k in ("98100", "85499", "99000", "47241", "97000", "")],
      ["U", "P", "U", "", "", ""])

# 13c: usaha makan-minum hanya boleh kode 5-11 (8x GALAT, semua KBLI gol. 56).
r, h = muat_std(kbli="56102", biaya_pembelian="0", biaya_produksi="30000000")
check("std: gol. 56 + 13c kode 4 -> skip", h.status, "SKIP_DATA_13C_MAMIN_BUKAN_5_11")
check("std: gol. 56 + 13c kode 11 (Daring) -> lolos 13c",
      muat_std(kbli="56102", biaya_pembelian="0", biaya_produksi="30000000",
               lokasi_usaha="11. Daring (online)")[1].status, "SIAP")
check("std: 13b2 Ya (KBLI bukan 56) + 13c kode 4 -> skip",
      muat_std(layanan_mamin="1. Ya")[1].status, "SKIP_DATA_13C_MAMIN_BUKAN_5_11")
check("std: bukan makan-minum -> 13c kode 4 tetap boleh", muat_std()[1].status, "SIAP")

# 13g: KBLI kategori P/U ditolak form (2x GALAT, KBLI 98100). Ketetapan user
# 2026-09-24: 13g diisi rekomendasi GenAI pertama saat pengisian (KBLI_DITOLAK_PAKAI_GENAI).
import inti.gabungan_loader as _gl  # noqa: E402
_r, _h = muat_std(kbli="98100", biaya_pembelian="2000000", biaya_produksi="0")
check("std: KBLI 98100 (kategori U) -> SIAP, 13g GenAI, 26c tidak dicek offline",
      (_h.status, _r.kbli_genai, any("GenAI" in t for t in _h.tanda)), ("SIAP", True, True))
check("std: KBLI GenAI -> judul KBLI sheet tidak dipakai", _r.judul_kbli, "")
_gl.KBLI_DITOLAK_PAKAI_GENAI = False
check("std: KBLI 98100 tanpa GenAI -> skip (perilaku lama)",
      muat_std(kbli="98100", biaya_pembelian="0", biaya_produksi="30000000")[1].status,
      "SKIP_DATA_KBLI_KATEGORI_DITOLAK")
_gl.KBLI_DITOLAK_PAKAI_GENAI = True

from inti.gabungan_loader import judul_dari_opsi_kbli, opsi_kbli_genai, pilih_opsi_genai  # noqa: E402
check("opsi GenAI (label export fasih-sm asli)",
      opsi_kbli_genai("[A] 01282 Pertanian Cengkih"), ("A", "01282", "Pertanian Cengkih"))
check("opsi Master bukan rekomendasi GenAI", opsi_kbli_genai("Pilih dari Master KBLI"), None)
check("judul dari opsi GenAI", judul_dari_opsi_kbli("[G] 47112 Perdagangan Eceran"), "Perdagangan Eceran")
check("pilih rekomendasi PERTAMA", pilih_opsi_genai(["[G] 47599 A", "[G] 47192 B", "Pilih dari Master KBLI"]),
      (0, ""))
check("rekomendasi kategori P/U dilewati",
      pilih_opsi_genai(["[P] 85550 A", "[U] 98100 B", "[S] 96230 C"])[0], 2)
check("semua P/U -> tidak ada yang dipilih", pilih_opsi_genai(["[P] 85550 A", "Pilih dari Master KBLI"])[0], -1)

# 26a vs 24a2 — dua aturan file-validation `gaji`.
check("std: 24a2=0 tapi 26a > 0 -> skip",
      muat_std(tk_laki="1", tk_pr="2", tk_dibayar="0", tk_tdk_dibayar="3")[1].status,
      "SKIP_DATA_26A_HARUS_0_TANPA_PEKERJA_DIBAYAR")
check("std: 24a2=0 & 26a=0 -> SIAP",
      muat_std(tk_laki="1", tk_pr="2", tk_dibayar="0", tk_tdk_dibayar="3", gaji="0")[1].status, "SIAP")
check("std: 26a/24a2 tepat Rp 50.000 masih ditolak (form minta > 50.000)",
      muat_std(gaji="50000")[1].status, "SKIP_DATA_26A_PER_PEKERJA_DI_BAWAH_MINIMAL")
check("std: 26a/24a2 Rp 50.001 -> lolos", muat_std(gaji="50001")[1].status, "SIAP")

# 24c1 "Cek konsistensi jenis kelamin pengusaha" = TANDA, bukan skip: pola laki 0 +
# perempuan 2 ada di 123 baris nyata yang terkirim tanpa GALAT (lihat KOREKSI_PEKERJA).
_r, _h = muat_std(tk_laki="0", tk_pr="3", tk_dibayar="1", tk_tdk_dibayar="2")
check("std: 12b laki-laki tapi 24a1=0 -> tanda saja, tetap SIAP",
      (_h.status, any("jenis kelamin pengusaha" in t for t in _h.tanda)), ("SIAP", True))


print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
