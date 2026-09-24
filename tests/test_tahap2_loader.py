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
from inti.config import MINIMAL_TOTAL_RUPIAH, TAHAP2_TAHUN_OPERASI_KOSONG_JADI, TAHAP2_UMUR_KOSONG_JADI

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

from inti.config import DEFAULT_13C_TEMPAT_USAHA, GALAT_13C_JADI  # noqa: E402

# 13c tidak ada di kuesioner tahap 2 -> TAHAP2_DEFAULT. Default "4. Toko, ruko"
# PASTI ditolak form utk usaha makan-minum ("lokasi hanya bisa diisi kode 5-11",
# 8 GALAT 22-23 Sep 2026) -> gol. 56 memakai GALAT_13C_JADI sejak dari loader.
cek("gol 56 -> 13c default kode 5, bukan kode 4", r56["lokasi_usaha"], GALAT_13C_JADI)
cek("gol 56 -> alasannya dicatat sbg asumsi",
    any("makan-minum" in c for c in r56.koreksi), True)
cek("non makan-minum tetap default lama", tulis([baris()])[0]["lokasi_usaha"], DEFAULT_13C_TEMPAT_USAHA)
_f13c = Path(tempfile.mkdtemp()) / "tahap2_13c.csv"
with _f13c.open("w", newline="", encoding="utf-8") as _fh:
    _w = csv.writer(_fh)
    _w.writerow([*JUDUL, "13c"])
    _w.writerow([*baris(**{"Kode KBLI": "56304"}), "9"])
cek("kolom 13c sheet tetap menang atas default",
    load_tahap2(_f13c)[0]["lokasi_usaha"], "9. Restoran, warung makan, dan sejenisnya")
_b0 = tulis([baris(**{"Kode KBLI": "56304", "26c": "Rp0", "Rp26": "", "26d": "Rp200.000"})])
cek("gol 56 & 26b+26c = 0 -> 26d dipindah ke 26b (ketetapan 2026-09-24)",
    (_b0[0]["biaya_produksi"], _b0[0]["operasional"], periksa_semua_tahap2(_b0)[2].status), ("200000", "0", "SIAP"))
t2.TAHAP2_26B_NOL_AMBIL_DARI_26D = False
cek("saklar mati: gol 56 & 26b+26c = 0 -> 26B_HARUS_LEBIH_0",
    periksa_semua_tahap2(tulis([baris(**{"Kode KBLI": "56304", "26c": "Rp0", "Rp26": "",
                                         "26d": "Rp200.000"})]))[2].status, "SKIP_DATA_26B_HARUS_LEBIH_0")
t2.TAHAP2_26B_NOL_AMBIL_DARI_26D = True

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
_kecil = tulis([baris(**{"26c": "Rp20.000", "26d": "Rp0", "Rp26": "", "27a": "Rp50.000", "27c": ""})])
cek("tahunan: 26f/27c < 100.000 -> dinaikkan ke pos terbesar (ketetapan 2026-09-24)",
    (_kecil[0]["biaya_pembelian"], _kecil[0]["nilai_pendapatan"], periksa_semua_tahap2(_kecil)[2].status),
    ("100000", "100000", "SIAP"))
cek_benar("... dicatat DINAIKKAN", any("DINAIKKAN" in k for k in _kecil[0].koreksi))
_p0 = tulis([baris(**{"26c": "Rp0", "26d": "Rp0", "Rp26": ""})])
cek("26f 0 -> 26d minimal (ketetapan 2026-09-24)",
    (_p0[0]["operasional"], periksa_semua_tahap2(_p0)[2].status), ("100000", "SIAP"))
t2.TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL = False
cek("saklar mati: 26f 0 TIDAK dikarang -> tetap ditolak", periksa_semua_tahap2(tulis([baris(**{
    "26c": "Rp0", "26d": "Rp0", "Rp26": ""})]))[2].status, "SKIP_DATA_DI_BAWAH_MINIMAL")
t2.TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL = True
t2.TAHAP2_NAIKKAN_KE_MINIMAL = False
cek("saklar mati: 26f < 100.000 ditolak", periksa_semua_tahap2(tulis([baris(**{
    "26c": "Rp20.000", "26d": "Rp0", "Rp26": "", "27a": "Rp50.000", "27c": ""})]))[2].status,
    "SKIP_DATA_DI_BAWAH_MINIMAL")
t2.TAHAP2_NAIKKAN_KE_MINIMAL = True
_c0 = tulis([baris(**{"25": _th, "26b": "Rp50.000", "26c": "Rp0", "26d": "Rp200.000", "Rp26": ""})])
cek("bulanan kategori G + 30c 0 -> 30b dipindah ke 30c (ketetapan 2026-09-24)",
    (_c0[0]["biaya_pembelian"], _c0[0]["biaya_produksi"], periksa_semua_tahap2(_c0)[2].status),
    ("50000", "0", "SIAP"))
_c1 = tulis([baris(**{"25": _th, "26c": "Rp0", "26d": "Rp200.000", "Rp26": ""})])
cek("... 30b juga 0 -> pos terbesar (30d) dipindah", (_c1[0]["biaya_pembelian"], _c1[0]["operasional"]),
    ("200000", "0"))
t2.TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN = False
cek("saklar mati: bulanan kategori G + 26c 0 -> 30C_HARUS_LEBIH_0", periksa_semua_tahap2(tulis([baris(**{
    "25": _th, "26c": "Rp0", "26d": "Rp200.000", "Rp26": ""})]))[2].status, "SKIP_DATA_30C_HARUS_LEBIH_0")
t2.TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN = True
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
r16, _ = rencana_16b("2,1,2,2,2")
cek("16b daftar 5 nilai -> b1-b5 + b6 Tidak (ketetapan 2026-09-23)",
    [r16[k][0] for k in KEY_16B], ["2", "1", "2", "2", "2", "2"])
cek("16b daftar 4 nilai -> tetap tidak jelas", rencana_16b("2,1,2,2")[0], None)
t2.TAHAP2_16B_LIMA_NILAI_B6 = ""
cek("saklar mati: 5 nilai -> tidak jelas", rencana_16b("2,1,2,2,2")[0], None)
t2.TAHAP2_16B_LIMA_NILAI_B6 = "2. Tidak"
r16, _ = rencana_16b("B1,B3")
cek("16b B1,B3", [r16[k][0] for k in KEY_16B], ["1", "2", "1", "2", "2", "2"])
r16, _ = rencana_16b("PROMOSI/KOMUNIKASI")
cek("16b PROMOSI/KOMUNIKASI -> b5,b6", [r16[k][0] for k in KEY_16B], ["2", "2", "2", "2", "1", "1"])
# Ketetapan user 2026-09-24: satu kolom "YA"/"1" TIDAK berarti keenamnya Ya —
# cuma b1 menerima pesanan, b4 membeli bahan baku & b5 promosi.
cek("16b YA -> hanya b1,b4,b5", [rencana_16b("YA")[0][k][0] for k in KEY_16B],
    ["1", "2", "2", "1", "1", "2"])
cek("16b '1' sama dgn 'YA'", rencana_16b("1")[0], rencana_16b("YA")[0])
cek("16b TIDAK -> keenamnya Tidak", set(rencana_16b("TIDAK")[0].values()), {"2. Tidak"})
cek("16b satu kolom Ya -> alasannya dicatat", "b1,b4,b5" in rencana_16b("YA")[1], True)
cek("16b '-' -> kosong", rencana_16b("-"), ({}, ""))
cek("16b teks asing -> tidak dikenali", rencana_16b("WA BISNIS")[0], None)
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1", "16b1-b6": "2,1,2,2,2"})]))
cek("16a Ya + 16b 5 nilai (ada Ya) -> SIAP", hasil[2].status, "SIAP")
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1", "16b1-b6": "2,2,2,2,2"})]))
cek("16a Ya + 16b 5 nilai semua Tidak -> b6 Lainnya Ya (ketetapan 2026-09-24)", hasil[2].status, "SIAP")
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1", "16b1-b6": "2,1,2,2"})]))
cek("16a Ya + 16b 4 nilai -> 16B_TIDAK_JELAS", hasil[2].status, "SKIP_DATA_16B_TIDAK_JELAS")
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "2", "16b1-b6": "2,2,2,2,2"})]))
cek("16a Tidak + 16b 5 nilai -> tidak dipakai, SIAP", hasil[2].status, "SIAP")
_r16 = tulis([baris(**{"16a": "1"})])
cek("16a Ya tapi 16b '2' -> b1-b5 Tidak, b6 Ya", [_r16[0][k][:1] for k in (
    "internet_pesanan", "internet_produksi", "internet_distribusi", "internet_beli", "internet_promosi",
    "internet_lainnya")], ["2", "2", "2", "2", "2", "1"])
t2.TAHAP2_16B_TANPA_YA_JADI_B6 = False
hasil = periksa_semua_tahap2(tulis([baris(**{"16a": "1"})]))
cek_benar("saklar mati: 16a Ya tapi 16b1-b6 semua Tidak -> ditolak form",
          any(k == "16B_TANPA_YA" for k, _ in hasil[2].masalah))
t2.TAHAP2_16B_TANPA_YA_JADI_B6 = True

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
                      ("-8,2004731", "1,15E+09", "rusak (notasi ilmiah Excel)"), ("abc", "114,79", "bukan angka")):
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
          any("TIDAK TERBACA" in t for t in periksa_semua_tahap2(
              tulis([baris(Latitude="-8,2004731", Longitude="1,15E+09")]), izinkan_tanpa_koordinat=True)[2].tanda))

print("\n== koordinat yang formatnya dirusak Excel dipulihkan (2026-09-24) ==")
for lat, lon, harap in (("-8.148.438", "1.145.951", ("-8.148438", "114.5951")),
                        ("-8,152133", "-115,142881", ("-8.152133", "115.142881")),
                        ("-8.142753,115.059837", "", ("-8.142753", "115.059837")),
                        ("-8.149636, 115.057187", None, ("-8.149636", "115.057187")),
                        ("-8,1423759, 115,0601420", None, ("-8.1423759", "115.060142")),
                        ("-8155247,", "115.098819", ("-8.155247", "115.098819")),
                        ("-81362115", "115,35943", ("-8.1362115", "115.35943")),
                        ("-8,136239", "115.359.466", ("-8.136239", "115.359466"))):
    rk = tulis([baris(Latitude=lat, Longitude=lon)])[0]
    cek(f"{lat!r}/{lon!r} -> {harap}", (rk["latitude"], rk["longitude"]), harap)
    cek_benar(f"{lat!r}: tercatat sbg koreksi", any("format rusak Excel" in k for k in rk.koreksi))
for lat, lon, ket in (("-8,1423759,", "1,15E+09", "notasi ilmiah (digit hilang)"),
                      ("-8,14773115", "149223166", "bujur di luar kotak"),
                      ("-8,1395", "-8,1306", "bujur = lintang"),
                      ("-8,47722", "-115,142003", "lintang di luar kabupaten (baris 1266)")):
    rk = tulis([baris(Latitude=lat, Longitude=lon)])[0]
    cek(f"{ket}: TIDAK ditebak", rk.punya_koordinat, False)
rk = tulis([baris(Latitude="-8,2004731", Longitude="114,7987732")])[0]
cek("koordinat benar: tidak ada koreksi", any("format rusak" in k for k in rk.koreksi), False)
t2.TAHAP2_KOTAK_KOORDINAT = None
cek("kotak None -> tidak dipulihkan", tulis([baris(Latitude="-8.148.438", Longitude="1.145.951")])[0].punya_koordinat,
    False)
t2.TAHAP2_KOTAK_KOORDINAT = (-8.45, -8.0, 114.4, 115.45)

print("\n== awalan kabupaten idsubsls salah ketik (2026-09-24) ==")
rk = tulis([baris(**{"Sumber/Kec.": "010", "5": "5100010010000302"})])[0]
cek("5100010... + kec 010 -> 5108010...", rk.idsubsls, "5108010010000302")
cek_benar("dicatat", any("awalan kabupaten salah ketik" in k for k in rk.koreksi))
cek("kec tidak cocok -> dibiarkan", tulis([baris(**{"Sumber/Kec.": "020", "5": "5100010010000302"})])[0].idsubsls,
    "5100010010000302")
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

print("\n== usaha pecahan bernama sama -> dibedakan 13f (ketetapan 2026-09-23) ==")
pecah = tulis([baris(**{"8b.": "WARUNG ULLUMA RAHMA", "13f": "BERAS ECERAN"}),
               baris(**{"8b.": "WARUNG ULLUMA RAHMA", "13f": "GAS LPG"}),
               baris(**{"8b.": "WARUNG ULLUMA RAHMA", "13f": "AIR GALON"}),
               baris(**{"8b.": "WARUNG ULLUMA RAHMA", "13f": "AIR GALON"})])
cek("nama dokumen diberi 13f", [r.nama_dokumen for r in pecah[:2]],
    ["WARUNG BERAS ECERAN (ULLUMA RAHMA)", "WARUNG GAS LPG (ULLUMA RAHMA)"])
cek("8b ikut", pecah[1].nama_komersial, "WARUNG GAS LPG (ULLUMA RAHMA)")
st = [h.status for h in periksa_semua_tahap2(pecah).values()]
cek("13f beda -> SIAP; 13f kembar -> tetap BARIS_GANDA", st,
    ["SIAP", "SIAP", "SKIP_DATA_BARIS_GANDA", "SKIP_DATA_BARIS_GANDA"])
cek("kunci baris tunggal TIDAK berubah (audit lama aman)",
    tulis([baris(**{"8b.": "WARUNG ULLUMA RAHMA"})])[0].kunci, pecah[2].kunci)
cek("baris bernama unik tanpa pembeda", tulis([baris()])[0].pembeda, "")
panjang = tulis([baris(**{"8b.": "WARUNG BU", "12a": "NI LUH PUTU SETIAWATI KARTIKA",
                          "13f": "AIR MINUM KEMASAN AIR GALON ISI ULANG"}),
                 baris(**{"8b.": "WARUNG BU", "12a": "NI LUH PUTU SETIAWATI KARTIKA", "13f": "GAS LPG"})])
cek_benar("> 50 karakter tetap memuat (12a), tidak jatuh ke nama tanpa pemilik",
          "(NI LUH PUTU SETIAWATI KARTIKA)" in panjang[0].nama_dokumen)
cek("... bagian usahanya diringkas di belakang (2026-09-24)", panjang[0].nama_dokumen,
    "AIR MINUM KEMASAN (NI LUH PUTU SETIAWATI KARTIKA)")
cek("... jadi tidak lagi di-skip", periksa_semua_tahap2(panjang)[2].status, "SIAP")
rk = tulis([baris(**{"8b.": "Pedagang eceran sparepart mobil (I Made Contoh Wirawan)", "12a": "I Made Contoh Wirawan"})])[0]
cek("8b sudah memuat pemilik & > 50 -> kata umum di depan dibuang", rk.nama_dokumen,
    "sparepart mobil (I Made Contoh Wirawan)")
cek("8b ikut", rk.nama_komersial, "sparepart mobil (I Made Contoh Wirawan)")
beda_sls = tulis([baris(**{"8b.": "WR CONTOH", "12a": "MD CONTOH", "13f": "Eceran bumbu dapur"}),
                  baris(**{"8b.": "WR CONTOH", "12a": "MD CONTOH", "13f": "Eceran kue kering",
                           "5": "5108010010000301"})])
cek("8b+12a sama di subsls BEDA -> tetap dibedakan 13f (satu list PENDATAAN)",
    [r.nama_dokumen for r in beda_sls], ["WR CONTOH Eceran bumbu dapur (MD CONTOH)", "WR CONTOH Eceran kue kering (MD CONTOH)"])
beda_13a = tulis([baris(**{"8b.": "WR PUTU", "13a": "Eceran perlengkapan AT", "13f": "alat tulis"}),
                  baris(**{"8b.": "WR PUTU", "13a": "Jual eceran alat penunjang", "13f": "alat tulis"})])
cek("13f kembar tapi 13a beda -> dibedakan 13a",
    [h.status for h in periksa_semua_tahap2(beda_13a).values()], ["SIAP", "SIAP"])
t2.TAHAP2_PEMBEDA_13F_UTK_GANDA = False
cek("saklar mati -> semua BARIS_GANDA", {h.status for h in periksa_semua_tahap2(tulis(
    [baris(**{"13f": "A B C D"}), baris(**{"13f": "E F G H"})])).values()}, {"SKIP_DATA_BARIS_GANDA"})
t2.TAHAP2_PEMBEDA_13F_UTK_GANDA = True

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

# --- indikator ekonomi kosong = 0, & 26a kalau ada pekerja dibayar (user 2026-09-23) ---
from inti.tahap2_loader import ALIAS_OPSI_PER_KEY, opsi_dari_kode as _opsi  # noqa: E402

cek("peran_mbg 'TIDAK' -> opsi 5 (labelnya bukan 'Tidak' polos)",
      _opsi("peran_mbg", "TIDAK"), "5. Tidak terlibat MBG")
cek("huruf kecil ikut cocok", _opsi("peran_mbg", "tidak"), "5. Tidak terlibat MBG")
cek("'YA' peran_mbg TIDAK ditebak (ada 4 varian Ya)", _opsi("peran_mbg", "YA"), "YA")
cek("alias khusus tidak bocor ke rincian lain", _opsi("mitra_kdkmp", "TIDAK"), "2. Tidak")
cek("kode angka tetap menang", _opsi("peran_mbg", "2"), "2. Ya, sebagai supplier")

print("\n== ketetapan user 2026-09-24 (temuan cek 24 Sep) ==")
from inti.config import TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN  # noqa: E402

# 27d: 16b1 Ya (pesanan lewat internet) tapi 27d kosong/0 -> 10% (baris 1556-1559).
r27 = tulis([baris(**{"16a": "1", "16b1-b6": "1", "27d": "0,00"})])[0]
cek("16b1 Ya + 27d 0 -> 27d 10%", r27["pendapatan_online"], str(TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN))
cek("... alasannya dicatat", any("16b1" in c and "27d" in c for c in r27.koreksi), True)
cek("27d sheet > 0 TIDAK diubah",
    tulis([baris(**{"16a": "1", "16b1-b6": "1", "27d": "35"})])[0]["pendapatan_online"], "35")
cek("16b1 Tidak -> 27d dibiarkan 0",
    tulis([baris(**{"16a": "1", "16b1-b6": "2,2,2,2,1", "27d": "0,00"})])[0]["pendapatan_online"], "0")
cek("16a Tidak -> 27d dibiarkan 0",
    tulis([baris(**{"16a": "2", "16b1-b6": "1", "27d": "0,00"})])[0]["pendapatan_online"], "0")

# 12a "-" -> nama dalam kurung, kalau tidak ada "PEMILIK <nama usaha>" (baris 1595-1597).
from inti.tahap2_loader import pengusaha_cadangan  # noqa: E402

cek("12a '-' + nama usaha berkurung -> isi kurung",
    tulis([baris(**{"12a": "-", "8b.": "KIOS MADE (NI KETUT SRI)"})])[0]["pengusaha"], "NI KETUT SRI")
cek("12a '-' tanpa kurung -> PEMILIK <usaha>",
    tulis([baris(**{"12a": "-", "8b.": "WARUNG SEMBAKO"})])[0]["pengusaha"], "PEMILIK WARUNG SEMBAKO")
cek("12a kosong diperlakukan sama",
    tulis([baris(**{"12a": "", "8b.": "WARUNG SEMBAKO"})])[0]["pengusaha"], "PEMILIK WARUNG SEMBAKO")
cek("kurung berisi angka/keterangan TIDAK dipakai sbg nama",
    pengusaha_cadangan("TOKO ABC (2)")[0], "PEMILIK TOKO ABC")
cek("12a terisi tidak diutak-atik", tulis([baris()])[0]["pengusaha"], "ULLUMA RAHMA")

# Nama kembar persis -> desa, lalu kecamatan, lalu penomoran.
kembar_desa = tulis([baris(**{"26a": "Rp0", "4": "PATAS 0010"}),
                     baris(**{"26a": "Rp100.000", "24.Dibayar": "1", "24.Tidak dibayar": "2",
                              "4": "PENYABANGAN 0011", "5": "5108010009000101"})],
                    kodepos="81155")   # subsls kedua belum ada di KODEPOS_BY_IDSUBSLS
cek("nama kembar + desa beda -> nama dibedakan desa",
    [r.nama_dokumen for r in kembar_desa],
    ["USAHA JUAL BERAS PATAS (ULLUMA RAHMA)", "USAHA JUAL BERAS PENYABANGAN (ULLUMA RAHMA)"])
cek("... keduanya lolos BARIS_GANDA",
    [h.status for h in periksa_semua_tahap2(kembar_desa).values()], ["SIAP", "SIAP"])

kembar_nomor = tulis([baris(**{"26a": "Rp0"}), baris(**{"26a": "Rp100.000", "24.Dibayar": "1",
                                                        "24.Tidak dibayar": "2"})])
cek("nama & wilayah kembar, isi beda -> penomoran",
    [r.nama_dokumen for r in kembar_nomor],
    ["USAHA JUAL BERAS 1 (ULLUMA RAHMA)", "USAHA JUAL BERAS 2 (ULLUMA RAHMA)"])
cek("... dan keduanya diproses",
    [h.status for h in periksa_semua_tahap2(kembar_nomor).values()], ["SIAP", "SIAP"])

# Pengaman: baris yang isinya SAMA PERSIS tetap BARIS_GANDA (duplikat entri,
# bukan dua usaha) — menomorinya = dua dokumen sensus utk satu usaha.
cek("baris identik tetap BARIS_GANDA, tidak dinomori",
    [h.status for h in periksa_semua_tahap2(tulis([baris(), baris()])).values()],
    ["SKIP_DATA_BARIS_GANDA", "SKIP_DATA_BARIS_GANDA"])
cek("... namanya pun tidak diubah",
    [r.nama_dokumen for r in tulis([baris(), baris()])],
    ["USAHA JUAL BERAS (ULLUMA RAHMA)"] * 2)
cek("baris tunggal tidak pernah dinomori",
    tulis([baris()])[0].nama_dokumen, "USAHA JUAL BERAS (ULLUMA RAHMA)")

# KBLI yang tidak nyambung dgn 13a/13f -> TANDA (baris 1730: sewa sound system
# tapi KBLI 43213). Form MENERIMA KBLI itu, jadi tidak pernah muncul sbg GALAT.
_sound = {"8b.": "SEWA SOUND SYSTEM BUDI", "13a": "SEWA SOUND SYSTEM UTK ACARA",
          "13f": "SEWA SOUND SYSTEM", "Kode KBLI": "43213",
          "Judul KBLI": "Instalasi Sistem Elektronika"}
_h = periksa_semua_tahap2(tulis([baris(**_sound)]))[2]
cek("KBLI tidak nyambung -> ditandai", any("generate KBLI" in t for t in _h.tanda), True)
cek("... tapi TIDAK di-skip", _h.status, "SIAP")
cek("KBLI nyambung -> tidak ditandai",
    any("generate KBLI" in t for t in
        periksa_semua_tahap2(tulis([baris(**{"Judul KBLI": "Perdagangan Eceran Beras"})]))[2].tanda), False)
cek("Judul KBLI kosong -> tidak dinilai",
    any("generate KBLI" in t for t in periksa_semua_tahap2(tulis([baris()]))[2].tanda), False)
# BUMDES: koreksi format standar (2026-09-15) dulu TIDAK berlaku di tahap 2, jadi
# barisnya lolos SIAP lalu GALAT "status badan usaha harus berkode 6" di form.
for _nama in ("PANGKALAN GAS BUMDES PANCA GIRI", "PANGKALAN GAS BUM DESA MAJU",
              "TOKO BADAN USAHA MILIK DESA PATAS"):
    _rb = tulis([baris(**{"8b.": _nama})])[0]
    cek(f"'{_nama[:22]}...' -> 11a kode 6 + 11d Ya + 29e 100",
        (_rb["badan_usaha"], _rb["lap_keuangan"], _rb["pemerintah"], _rb["pribadi"]),
        ("6. BUM Desa", "1. Ya", "100", "0"))
cek("koreksi BUMDES dicatat sbg asumsi",
    any("BUMDES" in k for k in tulis([baris(**{"8b.": "GAS BUMDES X"})])[0].koreksi), True)
cek("nama tanpa BUMDES tidak diubah",
    (tulis([baris()])[0]["badan_usaha"], tulis([baris()])[0]["lap_keuangan"]),
    ("13. Bukan Badan Usaha", "2. Tidak"))
# 11a yang SUDAH kode 6 di sheet tidak dianggap koreksi (tidak ada yang berubah).
from inti.gabungan_loader import koreksi_bumdes  # noqa: E402

cek("11a sudah kode 6 -> tidak ada koreksi",
    koreksi_bumdes({"nama": "GAS BUMDES X", "badan_usaha": "6. BUM Desa"}), "")
cek("nama tanpa pola BUMDES -> tidak ada koreksi",
    koreksi_bumdes({"nama": "GAS BIASA", "badan_usaha": "13. Bukan Badan Usaha"}), "")

cek("judul yang cuma berisi kata umum -> tidak menuduh",
    any("generate KBLI" in t for t in
        periksa_semua_tahap2(tulis([baris(**{"Judul KBLI": "Jasa Lainnya"})]))[2].tanda), False)

print("\n== 26a > 0 tapi 24a2 = 0 -> pekerja jadi dibayar (ketetapan 2026-09-24) ==")
_ru = tulis([baris(**{"24.Dibayar": "0", "24.Tidak dibayar": "2", "24.L": "1", "24.P": "1", "24.Total": "2",
                     "26a": "Rp17.000.000"})])
cek("24a2/24b2 0/2 -> 2/0, 26a tetap", (_ru[0]["tk_dibayar"], _ru[0]["tk_tdk_dibayar"], _ru[0]["gaji"]),
    ("2", "0", "17000000"))
cek("... tidak lagi ditolak", periksa_semua_tahap2(_ru)[2].status, "SIAP")

print("\n== 26a = 0 + pekerja dibayar -> 100.000 PER pekerja (2026-09-24) ==")
for dibayar, harap in (("1", "100000"), ("3", "300000")):
    rk = tulis([baris(**{"24.L": dibayar, "24.P": "0", "24.Dibayar": dibayar, "24.Tidak dibayar": "0",
                         "26a": "Rp0"})])[0]
    cek(f"{dibayar} pekerja dibayar -> 26a {harap}", rk["gaji"], harap)
    cek(f"{dibayar} pekerja dibayar -> tidak lagi 26A_PER_PEKERJA_DI_BAWAH_MINIMAL",
        "26A_PER_PEKERJA_DI_BAWAH_MINIMAL" in [k for k, _ in periksa_semua_tahap2([rk])[2].masalah], False)

print("\n== sel kosong yang dilengkapi (ketetapan user 2026-09-24) ==")
# Umur & tahun operasi: salin dari usaha lain PEMILIK yang sama, sisanya nilai pengganti.
r1, r2, r3 = tulis([baris(**{"8b.": "JUAL BERAS", "12c": "", "25": ""}),
                    baris(**{"8b.": "JUAL GAS", "12c": "34", "25": "2025"}),
                    baris(**{"8b.": "JUAL KOPI", "12a": "PEMILIK LAIN", "12c": "", "25": ""})])
cek("umur & tahun kosong disalin dari usaha lain pemilik yang sama",
    (r1["umur"], r1["tahun_operasi"]), ("34", "2025"))
cek("pemilik tanpa isian -> nilai pengganti config",
    (r3["umur"], r3["tahun_operasi"]), (TAHAP2_UMUR_KOSONG_JADI, TAHAP2_TAHUN_OPERASI_KOSONG_JADI))
cek_benar("nilai pengganti ditandai di koreksi", any("nilai pengganti" in k for k in r3.koreksi))
a, b, c = tulis([baris(**{"8b.": "A", "12c": ""}), baris(**{"8b.": "B", "12c": "30"}),
                 baris(**{"8b.": "C", "12c": "40"})])
cek("usaha lain pemilik berbeda-beda -> nilai pengganti, tidak memilih salah satu",
    a["umur"], TAHAP2_UMUR_KOSONG_JADI)
# 24: satu rincian kosong, kolom total terisi -> selisihnya (baris 1383).
(rk,) = tulis([baris(**{"24.Dibayar": "3", "24.Tidak dibayar": ""})])
cek("24b2 kosong = total bayar - 24a2", (rk["tk_dibayar"], rk["tk_tdk_dibayar"]), ("3", "0"))
# 27a & 27b kosong -> 27a minimal form (baris 1374/1375).
(rp,) = tulis([baris(**{"27a": "", "27b": "", "27c": "Rp0"})])
cek("27c 0 -> 27a minimal", (rp["nilai_pendapatan"], rp["pendapatan_lain"]), (str(MINIMAL_TOTAL_RUPIAH), "0"))
cek("27c 0 -> tidak lagi DI_BAWAH_MINIMAL",
    "DI_BAWAH_MINIMAL" in [k for k, _ in periksa_semua_tahap2([rp])[rp.baris].masalah], False)
# KBLI P/U -> 13g GenAI; 26c TIDAK dipindah ke 26b (KBLI sebenarnya belum diketahui).
(rg,) = tulis([baris(**{"Kode KBLI": "98100", "Judul KBLI": "AKTIVITAS PRODUKSI BARANG OLEH RUMAH TANGGA"})])
cek("KBLI 98100 -> GenAI, 13b dari KBLI, 26c tetap",
    (rg.kbli_genai, rg.b13_dari_kbli, rg["biaya_pembelian"], rg.judul_kbli), (True, True, "10500000", ""))
cek("KBLI 98100 -> tidak di-skip KBLI_KATEGORI_DITOLAK",
    periksa_semua_tahap2([rg])[rg.baris].status.startswith("SIAP"), True)

(rw,) = tulis([baris(**{"12b": "2", "24.L": "", "24.P": "", "24.Total": "", "24.Dibayar": "",
                        "24.Tidak dibayar": ""})])
cek("24 kosong semua -> 1 pekerja perempuan (ikut pemilik) tidak dibayar",
    tuple(rw[k] for k in ("tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar")), ("0", "1", "0", "1"))
(rw,) = tulis([baris(**{"24.L": "", "24.P": "", "24.Total": "", "24.Dibayar": "", "24.Tidak dibayar": "",
                        "26a": "Rp4.800.000"})])
cek("24 kosong semua + 26a terisi -> 1 pekerja dibayar",
    tuple(rw[k] for k in ("tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar")), ("1", "0", "1", "0"))
# 16b1-b6 "1" TIDAK dipakai di sini: sejak ketetapan 2026-09-24 nilai itu membuat
# 16b1 (menerima pesanan) = Ya, dan 27d kosong lalu jadi 10% — bukan 0. Jalur "kosong
# -> 0" diuji dgn 16b yang b1-nya Tidak (b5 promosi saja).
(rw,) = tulis([baris(**{"16a": "1", "16b1-b6": "2,2,2,2,1", "27d": ""})])
cek("27d kosong (16a Ya, 16b1 Tidak) -> 0", rw["pendapatan_online"], "0")

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
