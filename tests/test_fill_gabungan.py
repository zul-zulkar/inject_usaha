# -*- coding: utf-8 -*-
"""Uji fill_gabungan.fill_blok2_gabungan dgn sesi PALSU — offline, tanpa
browser/VPN. Membuktikan nilai sheet diketik APA ADANYA ke dataKey yang benar
(tanpa 10%, tanpa aturan pekerja <=3, tanpa override aset 0), dan urutan
field bersyarat dipertahankan.
Jalankan: python tests/test_fill_gabungan.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

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

    def __init__(self, dirender, label=None):
        self.page = FakePage()
        self.dirender = set(dirender)
        self.label = label or {}   # {dataKey: teks label} utk field yang dicari lewat label
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
        return next((dk for dk, teks in self.label.items() if re.match(pola, teks, re.I)), "")

    def isi_bersyarat_by_label(self, pola, nilai, nama=""):
        dk = self.datakey_by_label(pola)
        if dk:
            self.aksi.append(("label", dk, nilai))
        return bool(dk)

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


def jalankan(ubah=None, dirender=DIRENDER_LPG, label=None, murni=False):
    sess = FakeSess(dirender, label)
    row = GabunganRow(2, {**BARIS_LPG, **(ubah or {})}, murni=murni)
    return sess, fill_blok2_gabungan(sess, row)


def berhenti(judul, kode, *a, **k):
    try:
        jalankan(*a, **k)
        check(judul, "tidak berhenti", kode)
    except BarisPerluManual as e:
        check(judul, e.kode, kode)


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

# FasihWebSession me-resolve DK lebih dari sekali (komponen/_komponen_wajib), jadi nilai
# DK yang juga key DK lain diketik ke komponen yang SALAH (run 2026-09-15: 10b -> radio 10a).
from inti.config import DK as _DK
check("tidak ada rantai DK (nilai = key lain)",
      {k: v for k, v in _DK.items() if v in _DK and _DK[v] != v}, {})

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

# --- format standar: 13d/13e, 19 (halal), 20 (BPOM) dari kolom opsional ---
LABEL_13DE = {"input": "13. d. Apa input yang digunakan?", "proses": "13. e. Proses produksi"}
sess, asumsi = jalankan({"produk_sendiri": "1. Ya", "input_produksi": "Singkong", "proses_produksi": "Menggoreng"},
                        label=LABEL_13DE)
check("13d/13e dari sheet", (sess.nilai("input"), sess.nilai("proses")), (["Singkong"], ["Menggoreng"]))
berhenti("13d dirender tapi kolom kosong -> berhenti", "13DE_KOSONG", {"produk_sendiri": "1. Ya"}, label=LABEL_13DE)

LABEL_19 = {"halal": "19. a. Apakah ... halal?", "belum_halal": "19. c. Berapa jumlah varian ... belum ..."}
sess, asumsi = jalankan(label=LABEL_19)
check("19 kosong di sheet -> default config + ASUMSI",
      (sess.nilai("halal"), sess.nilai("belum_halal"), [a for a in asumsi if a.startswith("19")]),
      (["3. Tidak/Belum"], ["1"], ["19a default '3. Tidak/Belum'", "19c default '1'"]))
sess, asumsi = jalankan({"halal": "4. Dalam proses", "belum_halal": "5"}, label=LABEL_19)
check("19 dari sheet, tanpa ASUMSI",
      (sess.nilai("halal"), sess.nilai("belum_halal"), [a for a in asumsi if a.startswith("19")]),
      (["4. Dalam proses"], ["5"], []))
berhenti("19b dirender tapi kolom kosong -> berhenti", "19B_KOSONG", {"halal": "1. Ya, oleh BPJPH"},
         label={**LABEL_19, "sudah_halal": "19. b. Berapa jumlah varian ... sudah ..."})

DIRENDER_20 = DIRENDER_LPG | {"izin_edar", "belum_bpom"}
sess, asumsi = jalankan({"izin_edar": "2. Ya, bukan oleh BPOM", "belum_bpom": "3"}, DIRENDER_20)
check("20a/20c dari sheet, tanpa ASUMSI",
      (sess.nilai("izin_edar"), sess.nilai("belum_bpom"), [a for a in asumsi if a.startswith("20")]),
      (["2. Ya, bukan oleh BPOM"], ["3"], []))
sess, asumsi = jalankan(None, DIRENDER_20)
check("20 kosong di sheet -> default + ASUMSI (perilaku lama)",
      (sess.nilai("izin_edar"), sess.nilai("belum_bpom"), len([a for a in asumsi if a.startswith("20")])),
      (["3. Tidak"], ["1"], 2))

# --- MODE MURNI: tanpa default/aturan skrip ---
LENGKAP = {"produk": "Gas LPG 3 kg"}
sess, asumsi = jalankan(LENGKAP, murni=True)
check("murni: 8b apa adanya & tanpa ASUMSI", (sess.nilai("nama_komersial"), asumsi), (["PANGKALAN GAS X"], []))
check("murni: combobox UMKM hanya nilai sheet", sess.nilai("pilih_umkm_sls"), ["Tidak Ada"])
berhenti("murni: UMKM dirender tapi kolom kosong -> berhenti", "UMKM_SLS_KOSONG",
         {**LENGKAP, "pilih_umkm_sls": ""}, murni=True)
berhenti("murni: 13b4 bukan opsi -> berhenti (tidak diturunkan dari kategori)", "13B4_KOSONG",
         {**LENGKAP, "keg_penjualan": "2. Tidak"}, DIRENDER_LPG | {"keg_jasa"}, murni=True)
berhenti("murni: 19 dirender tapi kolom kosong -> berhenti", "19_20_KOSONG", LENGKAP, label=LABEL_19, murni=True)
berhenti("murni: 20 dirender tapi kolom kosong -> berhenti", "19_20_KOSONG", LENGKAP, DIRENDER_20, murni=True)
sess, asumsi = jalankan({**LENGKAP, "halal": "3. Tidak/Belum", "belum_halal": "2", "izin_edar": "3. Tidak",
                         "belum_bpom": "1"}, DIRENDER_20, label=LABEL_19, murni=True)
check("murni: 19/20 lengkap di sheet -> terisi, tanpa ASUMSI",
      (sess.nilai("halal"), sess.nilai("belum_halal"), sess.nilai("izin_edar"), sess.nilai("belum_bpom"), asumsi),
      (["3. Tidak/Belum"], ["2"], ["3. Tidak"], ["1"], []))

# --- 13g GenAI utk KBLI sheet kategori P/U (ketetapan user 2026-09-24) ---------
# Baris tahap 2 menurunkan 13b dari KBLI sheet (98100 -> semua Tidak); setelah
# GenAI memilih KBLI perdagangan, 13b3 harus jadi Ya lalu rekomendasi dipilih ulang.
from input_gabungan.fill_gabungan import pilih_kbli_genai  # noqa: E402
from inti.tahap2_loader import Tahap2Row  # noqa: E402


class GenaiSess(FakeSess):
    def __init__(self, hasil):
        super().__init__({"produk_sendiri", "layanan_mamin", "keg_penjualan"})
        self.hasil = list(hasil)

    def pilih_kbli_genai_pertama(self):
        self.aksi.append(("genai", "kbli_genai", ""))
        return self.hasil.pop(0)


def baris_genai():
    v = {**BARIS_LPG, "kbli": "98100", "produk_sendiri": "2. Tidak", "layanan_mamin": "2. Tidak",
         "keg_penjualan": "2. Tidak"}
    return Tahap2Row(2, v, info={"13b_dari_kbli": "1"})


G = ("47599", "G", "[G] 47599 Perdagangan Eceran Peralatan Rumah Tangga Lainnya")
s, asumsi = GenaiSess([G, G]), []
check("GenAI perdagangan -> 13b3 Ya, rekomendasi dipilih ulang, judul dikembalikan",
      (pilih_kbli_genai(s, baris_genai(), asumsi), s.nilai("keg_penjualan"), len(s.nilai("kbli_genai"))),
      ("Perdagangan Eceran Peralatan Rumah Tangga Lainnya", ["1. Ya"], 2))
s = GenaiSess([("96230", "S", "[S] 96230 Aktivitas SPA Harian")])
pilih_kbli_genai(s, baris_genai(), [])
check("GenAI jasa (13b tetap semua Tidak) -> tanpa klik 13b, dipilih sekali",
      ([a for a in s.aksi if a[0] == "radio"], len(s.nilai("kbli_genai"))), ([], 1))
try:
    pilih_kbli_genai(GenaiSess([G, ("10710", "C", "[C] 10710 Industri Roti")]), baris_genai(), [])
    check("13b tetap tidak sejalan -> berhenti", "lanjut", "KBLI_GENAI_13B_BEDA")
except BarisPerluManual as e:
    check("13b tetap tidak sejalan -> berhenti", e.kode, "KBLI_GENAI_13B_BEDA")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
