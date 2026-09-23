#!/usr/bin/env python3
"""
test_tahap2_loader.py — Uji OFFLINE (tanpa browser/VPN) pemetaan FORMAT
TAHAP 2 -> baris FORMAT STANDAR. Jalankan: python tests/test_tahap2_loader.py

Yang dikunci di sini adalah hal-hal yang kalau salah baru ketahuan setelah
dokumen terlanjur dibuat di fasih-web: pengubahan nilai (uang/desimal/kode
opsi), penurunan 13b1-b3 dari KBLI, default TAHAP2_DEFAULT, pemeriksaan
kolom total, dan `kunci` yang harus memisahkan dua responden bernama usaha
sama.
"""

import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh Buleleng di config.py

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import csv
import tempfile
from pathlib import Path

from inti.tahap2_loader import (
    _wilayah_dari_info, desimal_ke_titik, kodepos_untuk, load_tahap2, normalkan_hp, opsi_dari_kode,
    periksa_semua_tahap2, periksa_total, persen_ke_bulat, rencana_13b, rupiah_ke_angka,
)

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


def cek_benar(nama, syarat):
    cek(nama, bool(syarat), True)


# --------------------------------------------------------------------------
# Sheet contoh (CSV) — judul PERSIS seperti bahan/input_tahap2.xlsx, termasuk
# "24.Total" yang muncul dua kali dan judul satu-huruf "3"/"4"/"5".
# --------------------------------------------------------------------------
JUDUL = ["Sumber/Kec.", "Periode", "Uraian:", "Nama PPL", "3", "4", "5", "8b.", "8c.", "no WA",
         "12a", "12b", "12c", "12d", "13a", "13f", "14a", "16a", "16b1-b6", "17b", "21", "22",
         "24.L", "24.P", "24.Total", "24.Dibayar", "24.Tidak dibayar", "24.Total", "25", "Rp26",
         "26a", "26b", "26c", "26d", "26e", "27a", "27b", "27c", "27d", "28a", "28b", "28c",
         "28c1", "28d", "Latitude", "Longitude", "Kode KBLI", "Judul KBLI"]


def baris(**ubah):
    b = ["010", "21Sep", "Responden 1", "I PUTU ARIK PARMANA", "GEROKGAK 510801", "PATAS 0010",
         "5108010008000101", "USAHA JUAL BERAS", "BD TEGAL ASRI DS PATAS", "81340828334",
         "ULLUMA RAHMA", "1", "34", "9999", "MENJUAL BERAS ECERAN", "BERAS ECERAN (47241)",
         "1", "2", "2", "1", "2", "5",
         "1", "2", "3", "0", "3", "3", "2025", "Rp10.700.000",
         "Rp0", "Rp0", "Rp10.500.000", "Rp200.000", "Rp0", "Rp11.800.000", "Rp0", "Rp11.800.000",
         "0,00", "Rp1.000.000", "Rp2.000.000", "Rp3.000.000", "-", "4",
         "-8,2004731", "114,7987732", "47241", ""]
    for judul, nilai in ubah.items():
        b[JUDUL.index(judul.replace("_", " ").replace("no WA", "no WA"))] = nilai
    return b


def tulis(rows, **kw):
    f = Path(tempfile.mkdtemp()) / "tahap2.csv"
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(JUDUL)
        w.writerows(rows)
    return load_tahap2(f, **kw)


print("\n== pengubah nilai ==")
cek("rupiah biasa", rupiah_ke_angka("Rp10.500.000"), "10500000")
cek("rupiah + spasi + desimal", rupiah_ke_angka("Rp 10.500.000,75"), "10500000")
cek("rupiah nol", rupiah_ke_angka("Rp0"), "0")
cek("rupiah kosong", rupiah_ke_angka(""), "")
cek("rupiah strip", rupiah_ke_angka("-"), "")
cek("rupiah angka polos", rupiah_ke_angka("2500000"), "2500000")
cek("rupiah tak terbaca", rupiah_ke_angka("tidak ada"), "")
cek("desimal koma", desimal_ke_titik("-8,2004731"), "-8.2004731")
cek("desimal ribuan+koma", desimal_ke_titik("1.234,56"), "1234.56")
cek("desimal sudah titik", desimal_ke_titik("114.79"), "114.79")
cek("persen 0,00", persen_ke_bulat("0,00"), "0")
cek("persen 12,5 half-up", persen_ke_bulat("12,5"), "13")
cek("hp nol hilang", normalkan_hp("81340828334"), "081340828334")
cek("hp +62", normalkan_hp("+6281340828334"), "081340828334")
cek("hp sudah 0", normalkan_hp("081340828334"), "081340828334")
cek("hp placeholder 9999", normalkan_hp("9999"), "9999")

print("\n== kode opsi -> teks form ==")
cek("12b 1", opsi_dari_kode("jk", "1"), "1. Laki-laki")
cek("22 5", opsi_dari_kode("peran_mbg", "5"), "5. Tidak terlibat MBG")
cek("8d 10 (bukan 1)", opsi_dari_kode("jenis_kawasan", "10"), "10. Di luar kawasan")
cek("8d 1", opsi_dari_kode("jenis_kawasan", "1"), "1. Kawasan Ekonomi Khusus (KEK)")
cek("11a 1 ambigu (1.a/1.b) -> kosong", opsi_dari_kode("badan_usaha", "1"), "")
cek("kode tidak ada -> kosong", opsi_dari_kode("jk", "7"), "")
cek("teks opsi diteruskan", opsi_dari_kode("jk", "2. Perempuan"), "2. Perempuan")
cek("teks lain diteruskan (divalidasi periksa_baris)", opsi_dari_kode("jk", "Lk/Pr"), "Lk/Pr")

print("\n== 13b1/b2/b3 dari golongan KBLI ==")
cek("47xxx perdagangan eceran -> 13b3",
    rencana_13b("47241"), {"produk_sendiri": "2. Tidak", "layanan_mamin": "2. Tidak", "keg_penjualan": "1. Ya"})
cek("46xxx perdagangan besar -> 13b3", rencana_13b("46900")["keg_penjualan"], "1. Ya")
cek("56xxx makan minum -> 13b2", rencana_13b("56304")["layanan_mamin"], "1. Ya")
cek("10xxx industri -> 13b1", rencana_13b("10710")["produk_sendiri"], "1. Ya")
cek("33xxx industri (batas atas) -> 13b1", rencana_13b("33110")["produk_sendiri"], "1. Ya")
cek("01xxx pertanian -> semua Tidak (13b4 muncul)",
    set(rencana_13b("01111").values()), {"2. Tidak"})
cek("86xxx jasa kesehatan -> semua Tidak", set(rencana_13b("86101").values()), {"2. Tidak"})

print("\n== kodepos ==")
cek("dari kolom sheet menang", kodepos_untuk("5108010008000101", "81999", "81155"), "81999")
cek("dari KODEPOS_BY_IDSUBSLS", kodepos_untuk("5108010008000101", "", ""), "81155")
cek("dari KODEPOS_BY_DESA (contoh config)", kodepos_untuk("5108010010000302", "", ""), "81155")
cek("tidak diketahui -> cadangan --kodepos", kodepos_untuk("9999999999000101", "", "81160"), "81160")
cek("tidak diketahui & tanpa cadangan -> kosong", kodepos_untuk("9999999999000101", "", ""), "")

print("\n== nama wilayah utk melengkapi Nama Jalan ==")
cek("kolom 3/4", _wilayah_dari_info({"kec": "GEROKGAK 510801", "desa": "PATAS 0010"}),
    {"kecamatan": "GEROKGAK", "desa": "PATAS"})

print("\n== pemetaan satu baris utuh ==")
r = tulis([baris()])[0]
cek("jumlah kolom terbaca (tidak ada yang hilang)", len(JUDUL), 48)
cek("idsubsls", r.idsubsls, "5108010008000101")
cek("nama mentah = 8b", r.nama, "USAHA JUAL BERAS")
cek("nama dokumen = <8b> (<12a>)", r.nama_dokumen, "USAHA JUAL BERAS (ULLUMA RAHMA)")
cek("8b <= 50 karakter", len(r.nama_komersial) <= 50, True)
cek("8c jadi Nama Jalan", r.jalan_lengkap, "BD TEGAL ASRI DS PATAS")
cek("blok/nomor default '-'", r.nomor_rumah, "-")
cek("no WA", r["hp"], "081340828334")
cek("12b", r["jk"], "1. Laki-laki")
cek("14a", r["jaringan"], "1. Tunggal")
cek("16a", r["internet"], "2. Tidak")
cek("17b", r["perlindungan_lingkungan"], "1. Ya")
cek("21", r["mitra_kdkmp"], "2. Tidak")
cek("22", r["peran_mbg"], "5. Tidak terlibat MBG")
cek("26c", r["biaya_pembelian"], "10500000")
cek("27a", r["nilai_pendapatan"], "11800000")
cek("27d", r["pendapatan_online"], "0")
cek("28a tanah & bangunan", r["aset_usaha_thn"], "1000000")
cek("28b selain tanah & bangunan", r["aset_lain_thn"], "2000000")
cek("28d luas tanah", r["luas_tanah_thn"], "4")
cek("latitude", r["latitude"], "-8.2004731")
cek("longitude", r["longitude"], "114.7987732")
cek("kbli", r["kbli"], "47241")
cek("13f apa adanya", r["produk"], "BERAS ECERAN (47241)")
cek("kodepos dari daftar wilayah", r["kodepos"], "81155")
cek("13b3 dari KBLI 47", r["keg_penjualan"], "1. Ya")
cek("13b4 tidak dirender (13b3 Ya)", r.rincian_13b4_dirender, False)

print("\n== default TAHAP2_DEFAULT ==")
for key, harap in (("jenis_kawasan", "10. Di luar kawasan"), ("punya_nib", "2. Tidak"),
                   ("tidak_nib", "3. Tidak memerlukan NIB"), ("badan_usaha", "13. Bukan Badan Usaha"),
                   ("lap_keuangan", "2. Tidak"), ("lokasi_usaha", "4. Toko, ruko, dan sejenisnya"),
                   ("produksi_lingkungan", "3. Tidak sama sekali"), ("produk_seni", "2. Tidak"),
                   ("barang_non_pddk", "2. Tidak"), ("jasa_non_pddk", "2. Tidak"),
                   ("beli_jasa_non_pddk", "2. Tidak"), ("pribadi", "100"), ("asing", "0"),
                   ("ubah_sls", "2. Tidak"), ("keberadaan_usaha", "2. Baru"),
                   ("pilih_umkm_sls", "Tidak Ada"), ("nama_info_list", "Lainnya")):
    cek(f"default {key}", r[key], harap)
cek("29 jumlahnya 100", sum(int(r[k]) for k in
                            ("pribadi", "non_profit", "publik", "non_publik", "pemerintah", "asing")), 100)
cek("no_bang TIDAK diisi (aturan keselamatan #3)", r["no_bang"], "")
cek("default dicatat sbg tanda review", any("default" in t for t in r.koreksi), True)
cek("koreksi no WA dicatat", any("no WA" in t for t in r.koreksi), True)

print("\n== kolom tambahan MENANG atas default ==")
r2 = tulis([baris()], )[0]
f = Path(tempfile.mkdtemp()) / "t.csv"
with f.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(JUDUL + ["11a", "13c", "kodepos"])
    w.writerow(baris() + ["7", "3. Los Pasar", "81161"])
r3 = load_tahap2(f)[0]
cek("11a dari kolom sheet", r3["badan_usaha"], "7. Persekutuan Komanditer (CV)")
cek("13c dari kolom sheet", r3["lokasi_usaha"], "3. Los Pasar")
cek("kodepos dari kolom sheet", r3["kodepos"], "81161")

print("\n== pemeriksaan kolom total ==")
import inti.tahap2_loader as t2  # noqa: E402  (saklar ketetapan user diuji dua arah)
cek("total cocok -> tidak ada masalah", periksa_total(tulis([baris()])[0]), [])
# Ketetapan user 2026-09-22: total beda -> RINCIAN yang dipakai (form menghitung total), cuma ditandai.
for judul, nilai, nama in (("Rp26", "Rp1.000", "26f"), ("24.Total", "9", "24.Total ke-1"), ("27c", "Rp1.000", "27c")):
    rb = tulis([baris(**{judul: nilai})])[0]
    tanda_total: list = []
    cek(f"{nama} tidak cocok -> bukan masalah (rincian dipakai)", periksa_total(rb, tanda_total), [])
    cek_benar(f"{nama} tidak cocok -> ditandai", any("dipakai rinciannya" in t for t in tanda_total))
t2.TAHAP2_TOTAL_BEDA = "skip"
cek("TAHAP2_TOTAL_BEDA='skip' -> TOTAL_TIDAK_COCOK",
    [k for k, _ in periksa_total(tulis([baris(Rp26="Rp1.000")])[0])], ["TOTAL_TIDAK_COCOK"])
cek("TAHAP2_TOTAL_BEDA='skip' -> di-skip sebelum dokumen dibuat",
    periksa_semua_tahap2(tulis([baris(Rp26="Rp1.000")]))[2].status, "SKIP_DATA_TOTAL_TIDAK_COCOK")
cek("--abaikan-cek-total mematikan pemeriksaan itu",
    periksa_semua_tahap2(tulis([baris(Rp26="Rp1.000")]), cek_total=False)[2].status, "SIAP")
t2.TAHAP2_TOTAL_BEDA = "rincian"
# File contoh user 2026-09-22: "Rp26" = "Rp0" di semua baris padahal 26a-26e terisi
# -> kolom total tidak diisi, bukan selisih: tanda review, BUKAN skip.
rb = tulis([baris(Rp26="Rp0")])[0]
tanda_total = []
cek("total 0 + rincian > 0 -> bukan masalah", periksa_total(rb, tanda_total), [])
cek_benar("total 0 + rincian > 0 -> tanda review", any("dianggap tidak diisi" in t for t in tanda_total))
rb = tulis([baris(**{"28c": ""})])[0]
cek("kolom total kosong -> tidak diperiksa", periksa_total(rb), [])

print("\n== pemeriksaan menyeluruh ==")
hasil = periksa_semua_tahap2(tulis([baris()]))
cek("baris contoh SIAP", hasil[2].status, "SIAP")
hasil = periksa_semua_tahap2(tulis([baris(Rp26="Rp1.000")]))
cek("total beda -> tetap SIAP", hasil[2].status, "SIAP")
hasil = periksa_semua_tahap2(tulis([baris(Rp26="Rp0")]))
cek("total 0 (tidak diisi) -> tetap SIAP", hasil[2].status, "SIAP")
cek_benar("total 0 (tidak diisi) -> tercatat di tanda", any("Rp" not in t and "26a+26b" in t for t in hasil[2].tanda))

hasil = periksa_semua_tahap2(tulis([baris(**{"Kode KBLI": "10710", "13f": "ROTI"})]))
cek_benar("KBLI industri tanpa Judul KBLI -> minta 13d/13e (skip, bukan ditebak)",
          any(k == "13DE_TIDAK_ADA_DI_TAHAP2" for k, _ in hasil[2].masalah))
ri = tulis([baris(**{"Kode KBLI": "10710", "13f": "ROTI", "Judul KBLI": "INDUSTRI ROTI DAN KUE", "26c": "Rp0",
                     "26b": "Rp10.500.000"})])[0]
cek("industri + Judul KBLI -> 13d dari judul", ri["input_produksi"], "INDUSTRI ROTI DAN KUE")
cek("industri + Judul KBLI -> 13e dari judul (>=15)", ri["proses_produksi"], "INDUSTRI ROTI DAN KUE")
cek("industri + Judul KBLI -> SIAP", periksa_semua_tahap2([ri])[2].status, "SIAP")
ri = tulis([baris(**{"Kode KBLI": "10710", "13a": "BUAT ROTI", "Judul KBLI": "INDUSTRI ROTI"})])[0]
cek("judul < 15 -> 13e didahului 13a", ri["proses_produksi"], "BUAT ROTI INDUSTRI ROTI")

print("\n== 26c -> 26b utk KBLI tanpa 26c (B-F / gol 56) ==")
r56 = tulis([baris(**{"Kode KBLI": "56304", "26b": "Rp1.000.000"})])[0]
cek("26b = 26b + 26c", r56["biaya_produksi"], "11500000")
cek("26c jadi 0", r56["biaya_pembelian"], "0")
cek("gol 56 + 26c dipindah -> SIAP", periksa_semua_tahap2([r56])[2].status, "SIAP")
cek("kategori G -> 26c tetap", tulis([baris()])[0]["biaya_pembelian"], "10500000")
cek("gol 56 & 26b+26c = 0 -> 26B_HARUS_LEBIH_0",
    periksa_semua_tahap2(tulis([baris(**{"Kode KBLI": "56304", "26c": "Rp0", "Rp26": "",
                                         "26d": "Rp200.000"})]))[2].status, "SKIP_DATA_26B_HARUS_LEBIH_0")

hasil = periksa_semua_tahap2(tulis([baris(**{"5": "9999999999000101"})]))
cek_benar("kodepos tidak diketahui -> skip",
          any(k == "KODEPOS_TIDAK_DIKETAHUI" for k, _ in hasil[2].masalah))

hasil = periksa_semua_tahap2(tulis([baris(**{"12c": "0"})]))
cek("umur 0 ditolak (GALAT form 10-99)", hasil[2].status, "SKIP_DATA_UMUR_DI_LUAR_10_99")

print("\n== varian bulanan (mulai beroperasi 2026) ==")
import datetime as _dt  # noqa: E402
_th = str(_dt.date.today().year)
hasil = periksa_semua_tahap2(tulis([baris(**{"25": _th})]))
cek("mulai tahun berjalan -> SIAP (30-33 diisi dari kolom 26-29)", hasil[2].status, "SIAP")
cek_benar("... ditandai varian bulanan", any("varian bulanan" in t for t in hasil[2].tanda))
cek("bulanan: minimal 10.000 (bukan 100.000)", periksa_semua_tahap2(tulis([baris(**{
    "25": _th, "26c": "Rp20.000", "26d": "Rp0", "Rp26": "", "27a": "Rp50.000", "27c": ""})]))[2].status, "SIAP")
cek("tahunan: 26f < 100.000 tetap ditolak", periksa_semua_tahap2(tulis([baris(**{
    "26c": "Rp20.000", "26d": "Rp0", "Rp26": "", "27a": "Rp50.000", "27c": ""})]))[2].status,
    "SKIP_DATA_DI_BAWAH_MINIMAL")
cek("bulanan kategori G + 26c 0 -> 30C_HARUS_LEBIH_0", periksa_semua_tahap2(tulis([baris(**{
    "25": _th, "26c": "Rp0", "26d": "Rp200.000", "Rp26": ""})]))[2].status, "SKIP_DATA_30C_HARUS_LEBIH_0")
cek("tahun operasi di masa depan -> ditolak",
    periksa_semua_tahap2(tulis([baris(**{"25": str(int(_th) + 1)})]))[2].status, "SKIP_DATA_ANGKA_TIDAK_VALID")
t2.TAHAP2_ISI_VARIAN_BULANAN = False
cek("TAHAP2_ISI_VARIAN_BULANAN=False -> di-skip (perilaku lama)",
    periksa_semua_tahap2(tulis([baris(**{"25": _th})]))[2].status, "SKIP_DATA_VARIAN_BULANAN")
t2.TAHAP2_ISI_VARIAN_BULANAN = True

print("\n== pekerja ikut jenis kelamin pemilik ==")
rp = tulis([baris(**{"12b": "2", "24.L": "1", "24.P": "1", "24.Total": "", "24.Dibayar": "0",
                     "24.Tidak dibayar": "1"})])[0]
cek("L+P (2) != dibayar+tdk (1), pemilik perempuan -> 0/1", (rp["tk_laki"], rp["tk_pr"]), ("0", "1"))
cek("... baris jadi SIAP", periksa_semua_tahap2([rp])[2].status, "SIAP")
rp = tulis([baris(**{"12b": "PEREMPUAN", "24.L": "0", "24.P": "1", "24.Total": "", "24.Dibayar": "0",
                     "24.Tidak dibayar": "2"})])[0]
cek("L+P (1) != status (2) -> semua perempuan 0/2", (rp["tk_laki"], rp["tk_pr"]), ("0", "2"))
rp = tulis([baris(**{"12b": "2", "24.L": "1", "24.P": "0", "24.Total": "", "24.Dibayar": "0",
                     "24.Tidak dibayar": "1"})])[0]
cek("1 pekerja laki, pemilik perempuan (GALAT form) -> 0/1", (rp["tk_laki"], rp["tk_pr"]), ("0", "1"))
rp = tulis([baris(**{"24.L": "2", "24.P": "1", "24.Total": "", "24.Tidak dibayar": "3"})])[0]
cek("konsisten -> tidak diubah", (rp["tk_laki"], rp["tk_pr"]), ("2", "1"))
t2.TAHAP2_PEKERJA_IKUT_JK_PEMILIK = False
hasil = periksa_semua_tahap2(tulis([baris(**{"24.Dibayar": "1", "24.Tidak dibayar": "1", "24.Total": ""})]))
cek_benar("saklar mati: 24a1+24b1 != 24a2+24b2 ditolak",
          any(k == "PEKERJA_24_TIDAK_KONSISTEN" for k, _ in hasil[2].masalah))
t2.TAHAP2_PEKERJA_IKUT_JK_PEMILIK = True

print("\n== jawaban berupa teks & 16b ==")
from inti.gabungan_loader import KEY_16B  # noqa: E402
from inti.tahap2_loader import rencana_16b  # noqa: E402
for teks, harap in (("LAKI-LAKI", "1. Laki-laki"), ("LAKI - LAKI", "1. Laki-laki"), ("L", "1. Laki-laki"),
                    ("PEREMPUAN", "2. Perempuan"), ("P", "2. Perempuan"), ("perempuan", "2. Perempuan")):
    cek(f"12b '{teks}'", opsi_dari_kode("jk", teks), harap)
cek("16a 'YA'", opsi_dari_kode("internet", "YA"), "1. Ya")
cek("17b 'TIDAK'", opsi_dari_kode("perlindungan_lingkungan", "TIDAK"), "2. Tidak")
cek("'P' bukan opsi Ya/Tidak -> diteruskan (ditolak periksa)", opsi_dari_kode("internet", "P"), "P")
r16, _ = rencana_16b("1,2,1,1,1,1")
cek("16b daftar 6 nilai", [r16[k][0] for k in KEY_16B], ["1", "2", "1", "1", "1", "1"])
cek("16b daftar 5 nilai -> tidak jelas", rencana_16b("2,1,2,2,2")[0], None)
r16, _ = rencana_16b("B1,B3")
cek("16b B1,B3", [r16[k][0] for k in KEY_16B], ["1", "2", "1", "2", "2", "2"])
r16, _ = rencana_16b("PROMOSI/KOMUNIKASI")
cek("16b PROMOSI/KOMUNIKASI -> b5,b6", [r16[k][0] for k in KEY_16B], ["2", "2", "2", "2", "1", "1"])
cek("16b YA -> keenamnya", set(rencana_16b("YA")[0].values()), {"1. Ya"})
cek("16b '-' -> kosong", rencana_16b("-"), ({}, ""))
cek("16b teks asing -> tidak dikenali", rencana_16b("WA BISNIS")[0], None)
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1", "16b1-b6": "2,1,2,2,2"})]))
cek("16a Ya + 16b 5 nilai -> 16B_TIDAK_JELAS", hasil[2].status, "SKIP_DATA_16B_TIDAK_JELAS")
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "2", "16b1-b6": "2,2,2,2,2"})]))
cek("16a Tidak + 16b 5 nilai -> tidak dipakai, SIAP", hasil[2].status, "SIAP")
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1"})]))
cek_benar("16a Ya tapi 16b1-b6 semua Tidak -> ditolak form",
          any(k == "16B_TANPA_YA" for k, _ in hasil[2].masalah))

hasil = periksa_semua_tahap2(tulis([baris(**{"12b": "3"})]))
cek_benar("kode opsi tidak dikenal -> kolom kosong -> skip",
          any(k == "WAJIB_KOSONG" for k, _ in hasil[2].masalah))

print("\n== HP/WA kosong / tidak valid -> 9999 (TAHAP2_HP_TIDAK_VALID_JADI) ==")
from inti.gabungan_loader import hp_valid  # noqa: E402
for hp, harap in (("081340828334", True), ("9999", True), ("0812345678", True), ("081310", False),
                  ("81340828334", False), ("0811111111111", False), ("08123456789012", False), ("", False)):
    cek(f"hp_valid('{hp}')", hp_valid(hp), harap)
cek("'8,13E+10' tidak dijadikan 081310", normalkan_hp("8,13E+10"), "8,13E+10")
rh = tulis([baris(**{"no WA": "8,13E+10"})])[0]
cek("HP rusak Excel -> 9999", rh["hp"], "9999")
cek_benar("... ditandai", any("8,13E+10" in t for t in periksa_semua_tahap2([rh])[2].tanda))
cek("HP kosong -> 9999", tulis([baris(**{"no WA": ""})])[0]["hp"], "9999")
cek("HP valid tidak diubah", tulis([baris()])[0]["hp"], "081340828334")
t2.TAHAP2_HP_TIDAK_VALID_JADI = ""
cek("saklar kosong -> HP_TIDAK_VALID (skip)",
    periksa_semua_tahap2(tulis([baris(**{"no WA": "8,13E+10"})]))[2].status, "SKIP_DATA_HP_TIDAK_VALID")
t2.TAHAP2_HP_TIDAK_VALID_JADI = "9999"

print("\n== NIK tidak valid -> 9999 (TAHAP2_NIK_TIDAK_VALID_JADI) ==")
from inti.gabungan_loader import nik_valid  # noqa: E402
for nik, harap in (("5108032406800001", True), ("9999", True), ("8888", True), ("7777", True),
                   ("518014105850001", False), ("5,11E+15", False), ("123", False), ("1111111111111111", False),
                   ("51080324068000011", False)):
    cek(f"nik_valid('{nik}')", nik_valid(nik), harap)
rn = tulis([baris(**{"12d": "518014105850001"})])[0]
cek("NIK 15 digit -> 9999", rn["nik_pengusaha"], "9999")
cek("... baris tetap SIAP", periksa_semua_tahap2([rn])[2].status, "SIAP")
cek_benar("... ditandai", any("12d NIK '518014105850001'" in t for t in periksa_semua_tahap2([rn])[2].tanda))
cek("NIK 16 digit tidak diubah", tulis([baris(**{"12d": "5108032406800001"})])[0]["nik_pengusaha"], "5108032406800001")
t2.TAHAP2_NIK_TIDAK_VALID_JADI = ""
cek("saklar kosong -> NIK_TIDAK_VALID (skip)",
    periksa_semua_tahap2(tulis([baris(**{"12d": "518014105850001"})]))[2].status, "SKIP_DATA_NIK_TIDAK_VALID")
t2.TAHAP2_NIK_TIDAK_VALID_JADI = "9999"

print("\n== koordinat belum ada / rusak -> DRAFT (--koordinat otomatis) ==")
for lat, lon, ket in (("", "", "kosong"), ("-", "-", "strip"), ("0", "0", "nol"), ("-8,2004731", "", "hanya lat"),
                      ("-8.148.438", "1.145.951", "rusak (titik ribuan Excel)"), ("abc", "114,79", "bukan angka")):
    rk = tulis([baris(Latitude=lat, Longitude=lon)])[0]
    cek(f"{ket}: punya_koordinat False", rk.punya_koordinat, False)
    h = periksa_semua_tahap2([rk], izinkan_tanpa_koordinat=True)[2]
    cek(f"{ket}: otomatis -> SIAP_TANPA_KOORDINAT", h.status, "SIAP_TANPA_KOORDINAT")
    cek_benar(f"{ket}: otomatis -> bisa diproses", h.bisa_diproses)
    cek_benar(f"{ket}: tanda DRAFT tercatat", any("KOORDINAT BELUM ADA" in t for t in h.tanda))
    h = periksa_semua_tahap2([rk])[2]
    cek_benar(f"{ket}: wajib -> di-skip", h.status.startswith("SKIP_DATA_"))
cek_benar("hanya lat: disebut di tanda",
          any("hanya latitude" in t for t in periksa_semua_tahap2(
              tulis([baris(Latitude="-8,2004731", Longitude="")]), izinkan_tanpa_koordinat=True)[2].tanda))
cek_benar("rusak: nilainya disebut di tanda",
          any("TIDAK TERBACA '-8.148.438'" in t for t in periksa_semua_tahap2(
              tulis([baris(Latitude="-8.148.438", Longitude="1.145.951")]), izinkan_tanpa_koordinat=True)[2].tanda))
rk = tulis([baris()])[0]
cek("koordinat lengkap: punya_koordinat", rk.punya_koordinat, True)
cek("koordinat lengkap + otomatis -> SIAP biasa (dikirim)",
    periksa_semua_tahap2([rk], izinkan_tanpa_koordinat=True)[2].status, "SIAP")
h = periksa_semua_tahap2(tulis([baris(Latitude="", Longitude="", **{"12c": "0"})]), izinkan_tanpa_koordinat=True)[2]
cek_benar("tanpa koordinat TIDAK meloloskan masalah lain (umur 0)", h.status.startswith("SKIP_DATA_"))

print("\n== 13a < 15 karakter dilengkapi judul KBLI ==")
from inti.gabungan_loader import judul_dari_opsi_kbli, lengkapi_13a  # noqa: E402
cek("judul dari teks opsi Master KBLI",
    judul_dari_opsi_kbli("[G][47241]Perdagangan Eceran Beras [G][47241]Perdagangan Eceran Beras"),
    "Perdagangan Eceran Beras")
cek("sedikit: kata ditambah sampai >= 15", lengkapi_13a("JUAL SAYUR", "Perdagangan Eceran Sayuran", cara="sedikit"),
    "JUAL SAYUR (PERDAGANGAN)")
cek("penuh: seluruh judul", lengkapi_13a("JUAL SAYUR", "Perdagangan Eceran Sayuran", cara="penuh"),
    "JUAL SAYUR (PERDAGANGAN ECERAN SAYURAN)")
cek("huruf kecil 13a -> judul tidak di-UPPERCASE", lengkapi_13a("Bengkel", "Reparasi Sepeda Motor", cara="sedikit"),
    "Bengkel (Reparasi)")
cek("13a huruf campur + judul HURUF BESAR -> judul disamakan",
    lengkapi_13a("Menjual Rokok", "PERDAGANGAN ECERAN ROKOK", cara="sedikit"), "Menjual Rokok (Perdagangan)")
cek("13a sudah >= 15 -> tidak diubah", lengkapi_13a("MENJUAL GAS LPG", "Perdagangan Eceran Gas", cara="penuh"),
    "MENJUAL GAS LPG")
cek("judul kosong -> apa adanya (pemanggil berhenti)", lengkapi_13a("WARUNG", "", cara="sedikit"), "WARUNG")
cek("cara kosong -> tidak dilengkapi", lengkapi_13a("WARUNG", "Perdagangan Eceran", cara=""), "WARUNG")
h = periksa_semua_tahap2(tulis([baris(**{"13a": "JUAL BERAS", "Judul KBLI": "Perdagangan Eceran Beras"})]))[2]
cek("13a pendek + Judul KBLI sheet -> tetap SIAP", h.status, "SIAP")
cek_benar("13a pendek + Judul KBLI sheet -> hasilnya terlihat di tanda",
          any("-> 'JUAL BERAS (PERDAGANGAN)'" in t for t in h.tanda))
h = periksa_semua_tahap2(tulis([baris(**{"13a": "JUAL BERAS"})]))[2]
cek("13a pendek tanpa Judul KBLI -> SIAP (judul dari Master KBLI saat isi)", h.status, "SIAP")
cek_benar("... dan dicatat di tanda", any("dari Master KBLI saat pengisian" in t for t in h.tanda))
cek("13a sudah cukup -> tidak ada tanda 13a",
    any("13a" in t for t in periksa_semua_tahap2(tulis([baris()]))[2].tanda), False)

print("\n== kunci baris ==")
dua = tulis([baris(), baris(**{"Uraian:": "Responden 2", "12a": "I KETUT CONTOH"})])
cek("nama usaha sama + pemilik beda -> kunci BERBEDA", dua[0].kunci != dua[1].kunci, True)
cek("bukan BARIS_GANDA", [h.status for h in periksa_semua_tahap2(dua).values()], ["SIAP", "SIAP"])
sama = tulis([baris(), baris()])
cek("baris identik -> BARIS_GANDA",
    all("BARIS_GANDA" in [k for k, _ in h.masalah] for h in periksa_semua_tahap2(sama).values()), True)
cek("kunci stabil antar-pemuatan", tulis([baris()])[0].kunci, dua[0].kunci)

print("\n== judul kolom hilang -> berhenti, tidak menebak ==")
f = Path(tempfile.mkdtemp()) / "kurang.csv"
with f.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow([j for j in JUDUL if j != "8b."])
    w.writerow([v for j, v in zip(JUDUL, baris()) if j != "8b."])
try:
    load_tahap2(f)
    cek("kolom 8b. hilang -> ValueError", "tidak error", "ValueError")
except ValueError as e:
    cek("kolom 8b. hilang -> ValueError", "8b." in str(e), True)

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
