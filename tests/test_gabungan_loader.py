# -*- coding: utf-8 -*-
"""Uji loader & pemeriksaan sheet "gabungan" — offline, tanpa browser/VPN.
Jalankan: python tests/test_gabungan_loader.py
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.gabungan_loader import (
    cocokkan_wilayah_dokumen, format_nama_usaha, load_gabungan, parse_pilihan_baris, periksa_semua,
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
    ("gelar ikut", "PANGKALAN GAS NI NYOMAN MURTINI, SE. MM", "NI NYOMAN MURTINI, SE. MM",
     "PANGKALAN GAS (NI NYOMAN MURTINI, SE. MM)"),
    ("pemisah di tepi dibuang", "UD. WIDE/ SUARDANTI", "SUARDANTI", "UD. WIDE (SUARDANTI)"),
    ("pemilik di tengah", "WARUNG KETUT TOYA JAYA", "KETUT TOYA", "WARUNG JAYA (KETUT TOYA)"),
    ("bukan kata utuh -> tidak dihapus", "TOKO MADELINE", "MADE", "TOKO MADELINE (MADE)"),
    ("nama pemilik tidak utuh -> format biasa", "PANGKALAN GAS DHARMA HADI", "DHARMA HADI KUSUMA",
     "PANGKALAN GAS DHARMA HADI (DHARMA HADI KUSUMA)"),
    ("nama = pemilik", "KETUT TOYA", "KETUT TOYA", "(KETUT TOYA)"),
    ("idempoten", "PANGKALAN GAS (JAMALUDIN)", "JAMALUDIN", "PANGKALAN GAS (JAMALUDIN)"),
    ("nyata baris 393: kurung tak tertutup -> satu kurung saja",
     "PRAKTIK DOKTER I NYOMAN NAMA PUTRA SP.P (K)", "I Nyoman Nama Putra Sp.P (K",
     "PRAKTIK DOKTER (I Nyoman Nama Putra Sp.P K)"),
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

_, h = muat(baris(**u("26. a.", "0"), **u("26. c.", "50000"), **u("26. d.", "0")))
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

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
