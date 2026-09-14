# -*- coding: utf-8 -*-
"""Uji fill_gabungan.fill_blok2_gabungan dgn sesi PALSU — offline, tanpa
browser/VPN. Membuktikan nilai sheet diketik APA ADANYA ke dataKey yang benar
(tanpa 10%, tanpa aturan pekerja <=3, tanpa override aset 0), dan urutan
field bersyarat dipertahankan.
Jalankan: python tests/test_fill_gabungan.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.config import DK
from input_gabungan.fill_gabungan import BarisPerluManual, fill_blok2_gabungan
from inti.gabungan_loader import GabunganRow

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


class FakePage:
    def __init__(self):
        self.keyboard = self

    def press(self, _):
        pass

    def wait_for_timeout(self, _):
        pass


class FakeSess:
    """Meniru API FasihWebSession yang dipakai fill_gabungan. `dirender` =
    dataKey ASLI yang dianggap ada di DOM."""

    def __init__(self, dirender):
        self.page = FakePage()
        self.dirender = set(dirender)
        self.aksi = []

    def _log(self, _):
        pass

    def komponen_ada(self, key, timeout_ms=6000):
        return DK.get(key, key) in self.dirender

    def select_radio_by_datakey(self, key, nilai):
        self.aksi.append(("radio", DK.get(key, key), nilai))

    def fill_by_datakey(self, key, nilai):
        if nilai is None or str(nilai) == "":
            return
        self.aksi.append(("isi", DK.get(key, key), str(nilai)))

    def pilih_combobox_pertama_yang_cocok(self, key, kandidat):
        self.aksi.append(("combo", DK.get(key, key), kandidat[0]))

    def datakey_by_label(self, pola):
        return ""

    def isi_bersyarat_by_label(self, pola, nilai, nama=""):
        return False

    def fill_kbli_master(self, kode, search_phrase_fallback=""):
        self.aksi.append(("kbli", "kbli", kode))

    def dump(self, *a, **k):
        pass

    def nilai(self, dk):
        return [v for _, k, v in self.aksi if k == dk]

    def urutan(self, dk):
        return next(i for i, (_, k, _) in enumerate(self.aksi) if k == dk)


BARIS_LPG = {
    "nama": "PANGKALAN GAS X", "akun_ppl": "ppl@gmail.com", "idsubsls": "5108070013000901",
    "pilih_umkm_sls": "Tidak Ada", "keberadaan_usaha": "2. Baru", "nama_komersial": "PANGKALAN GAS X",
    "hp": "9999", "jenis_kawasan": "10. Di luar kawasan", "punya_nib": "2. Tidak", "nib_nomor": "",
    "tidak_nib": "3. Tidak memerlukan NIB", "badan_usaha": "13. Bukan Badan Usaha",
    "lap_keuangan": "1. Ya", "pengusaha": "I KETUT X", "jk": "1. Laki-laki", "umur": "45",
    "nik_pengusaha": "9999", "keg_utama": "Perdagangan eceran gas elpiji (LPG) dalam tabung",
    "produk_sendiri": "2. Tidak", "layanan_mamin": "2. Tidak", "keg_penjualan": "1. Ya",
    "keg_jasa": "3. Perdagangan Besar dan Eceran", "lokasi_usaha": "4. Toko, ruko, dan sejenisnya",
    "kbli": "47772", "jaringan": "1. Tunggal", "internet": "1. Ya",
    "internet_pesanan": "1. Ya", "internet_produksi": "2. Tidak", "internet_distribusi": "1. Ya",
    "internet_beli": "1. Ya", "internet_promosi": "1. Ya", "internet_lainnya": "2. Tidak",
    "digital": "2. Tidak", "produksi_lingkungan": "3. Tidak sama sekali",
    "perlindungan_lingkungan": "2. Tidak", "produk_seni": "2. Tidak", "mitra_kdkmp": "2. Tidak",
    "peran_mbg": "5. Tidak terlibat MBG", "barang_non_pddk": "1. Ya", "jasa_non_pddk": "2. Tidak",
    "beli_jasa_non_pddk": "2. Tidak",
    # total pekerja 3 & ada yang dibayar: aturan <=3 backlog lama TIDAK boleh diterapkan
    "tk_laki": "1", "tk_pr": "2", "tk_dibayar": "3", "tk_tdk_dibayar": "0", "tahun_operasi": "2019",
    "gaji": "15056000", "biaya_produksi": "0", "biaya_pembelian": "29200000", "operasional": "912000",
    "non_operasional": "0", "nilai_pendapatan": "32850000", "pendapatan_lain": "0",
    "pendapatan_online": "0", "aset_usaha_thn": "48550000", "aset_lain_thn": "2550000",
    "luas_tanah_thn": "140", "pribadi": "100", "non_profit": "0", "publik": "0", "non_publik": "0",
    "pemerintah": "0", "asing": "0",
}
DIRENDER_LPG = {
    "pilih_umkm_sls", "tidak_nib", "produk_sendiri", "layanan_mamin", "keg_penjualan", "lokasi_usaha",
    "internet_pesanan", "internet_produksi", "internet_distribusi", "internet_beli",
    "internet_promosi", "internet_lainnya", "digital", "gaji", "biaya_pembelian",
    "pendapatan_online", "pribadi",
}


def jalankan(ubah=None, dirender=DIRENDER_LPG):
    sess = FakeSess(dirender)
    row = GabunganRow(2, {**BARIS_LPG, **(ubah or {})})
    return sess, fill_blok2_gabungan(sess, row)


sess, asumsi = jalankan()
check("pilih_umkm_sls diisi SEBELUM keberadaan_usaha",
      sess.urutan("pilih_umkm_sls") < sess.urutan("keberadaan_usaha"), True)
check("combobox UMKM pakai nilai sheet", sess.nilai("pilih_umkm_sls"), ["Tidak Ada"])
check("8b = '<nama> (<12a>)'", sess.nilai("nama_komersial"), ["PANGKALAN GAS X (I KETUT X)"])
check("10c dari sheet, 10b tidak disentuh", (sess.nilai("tidak_nib"), sess.nilai("nib")),
      (["3. Tidak memerlukan NIB"], []))
check("13f = 13a", sess.nilai("produk"), ["Perdagangan eceran gas elpiji (LPG) dalam tabung"])
check("13b4 tidak dirender -> tidak diklik", sess.nilai("keg_jasa"), [])
check("16b dari sheet (bukan DEFAULT_16B)",
      [sess.nilai(k)[0] for k in ("internet_pesanan", "internet_distribusi", "internet_beli", "internet_promosi")],
      ["1. Ya", "1. Ya", "1. Ya", "1. Ya"])
check("23a dari sheet (bukan asumsi '2. Tidak')", sess.nilai("barang_non_pddk"), ["1. Ya"])
check("24 apa adanya (tanpa aturan <=3)",
      [sess.nilai(k)[0] for k in ("tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar")], ["1", "2", "3", "0"])
check("26a apa adanya (tanpa 10% & tidak dinolkan)", sess.nilai("gaji"), ["15056000"])
check("26c diisi", sess.nilai("biaya_pembelian"), ["29200000"])
check("27a apa adanya", sess.nilai("nilai_pendapatan"), ["32850000"])
check("28a dari sheet (bukan override 0)", sess.nilai("aset_usaha_thn"), ["48550000"])
check("28d dari sheet (bukan override 0)", sess.nilai("luas_tanah_thn"), ["140"])
check("29 dari sheet", [sess.nilai(k)[0] for k in ("pribadi", "pemerintah")], ["100", "0"])
check("KBLI dari sheet", sess.nilai("kbli"), ["47772"])
check("asumsi hanya 13f", asumsi, ["13f disalin dari 13a"])

# 10a = Ya -> 10b diisi lewat DK "nib_nomor" (dataKey asli "nib", BUKAN punya_nib)
sess, _ = jalankan({"punya_nib": "1. Ya", "nib_nomor": "9999", "tidak_nib": ""}, DIRENDER_LPG | {"nib"})
check("10b diisi ke dataKey 'nib'", (sess.nilai("nib"), sess.nilai("punya_nib")), (["9999"], ["1. Ya"]))
try:
    jalankan({"punya_nib": "1. Ya", "nib_nomor": "9999"})
    check("10a Ya tapi 10b tidak dirender -> berhenti", "tidak berhenti", "10B_TIDAK_DIRENDER")
except BarisPerluManual as e:
    check("10a Ya tapi 10b tidak dirender -> berhenti", e.kode, "10B_TIDAK_DIRENDER")

# 13b4 dirender (faskes: 13b1-b3 Tidak) -> nilai sheet dipakai, KBLI lebih dulu
sess, asumsi = jalankan({"keg_penjualan": "2. Tidak", "keg_jasa": "1. Jasa"}, DIRENDER_LPG | {"keg_jasa"})
check("13b4 dari sheet & diisi SETELAH KBLI",
      (sess.nilai("keg_jasa"), sess.urutan("kbli") < sess.urutan("keg_jasa")), (["1. Jasa"], True))
sess, asumsi = jalankan({"keg_penjualan": "2. Tidak"}, DIRENDER_LPG | {"keg_jasa"})
check("13b4 sheet bukan opsi -> turunan kategori + dicatat ASUMSI",
      (sess.nilai("keg_jasa"), any(a.startswith("13b4") for a in asumsi)), (["1. Jasa"], True))

for label, dirender, ubah, kode in (
    ("varian bulanan -> berhenti", (DIRENDER_LPG - {"gaji"}) | {"gaji_bln"}, None, "VARIAN_BULANAN"),
    ("26c tidak dirender padahal sheet > 0 -> berhenti", DIRENDER_LPG - {"biaya_pembelian"}, None,
     "26C_TIDAK_DIRENDER"),
):
    try:
        jalankan(ubah, dirender)
        check(label, "tidak berhenti", kode)
    except BarisPerluManual as e:
        check(label, e.kode, kode)

sess, _ = jalankan({"biaya_pembelian": "0"}, DIRENDER_LPG - {"biaya_pembelian"})
check("26c tidak dirender & sheet 0 -> dilewati tanpa berhenti", sess.nilai("biaya_pembelian"), [])

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
