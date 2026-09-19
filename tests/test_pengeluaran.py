# -*- coding: utf-8 -*-
"""Uji aturan pekerja (rincian 24) & pengeluaran (rincian 26) — offline,
tanpa browser/VPN. Jalankan: python tests/test_pengeluaran.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

from inti.data_loader import (
    BacklogRow, rencana_pekerja, rencana_pendapatan, rencana_pengeluaran,
    rupiah10, sum_rupiah10,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


def baris(**kw) -> BacklogRow:
    d = dict(
        no="9999", nama_usaha_pecahan="X", kbli_pecahan="47111",
        link_fasih_sm="", survey_assignment_id=None, row_assignment_id="",
        idsubsls="", nama_kepala_keluarga="", email_ppl="", nama_ppl="",
        nama_usaha_di_keluarga="", kbli_akhir_sumber="", kategori_sumber="",
        latitude="", longitude="", nilai_pendapatan="0", pendapatan_lain="0",
        gaji="0", biaya_produksi="0", biaya_pembelian="0", operasional="0",
        non_operasional="0", aset_lain_thn="0",
    )
    d.update(kw)
    return BacklogRow(**d)


# --- regresi: kalkulasi 10% yg sudah terbukti cocok thd record manual ---
check("rupiah10 record-2 (round HALF UP, bukan half-even)", rupiah10("33600008"), 3360001)
check("sum_rupiah10 jumlah-dulu-baru-bulatkan", sum_rupiah10("33600004", "4"), 3360001)

# --- rencana_pekerja ---
r = rencana_pekerja("1", "1", "2", "0")
check("2 pekerja -> semua tidak dibayar", (r.dibayar, r.tidak_dibayar), ("0", "2"))
check("2 pekerja -> nolkan_upah", r.nolkan_upah, True)
check("marginal gender tidak diubah", (r.laki, r.perempuan), ("1", "1"))

r = rencana_pekerja("2", "1", "3", "0")
check("tepat 3 pekerja masih kena aturan (<=3)", (r.dibayar, r.tidak_dibayar, r.nolkan_upah),
      ("0", "3", True))

r = rencana_pekerja("3", "1", "4", "0")
check("4 pekerja -> apa adanya", (r.dibayar, r.tidak_dibayar, r.nolkan_upah), ("4", "0", False))

r = rencana_pekerja("0", "0", "0", "0")
check("0 pekerja -> tetap kena aturan, tidak error", (r.dibayar, r.tidak_dibayar, r.nolkan_upah),
      ("0", "0", True))

r = rencana_pekerja("", "", "", "")
check("sumber kosong -> aturan TIDAK diterapkan", r.nolkan_upah, False)
check("sumber kosong -> total None", r.total, None)
check("sumber kosong -> ada peringatan", any("tidak diketahui" in c for c in r.catatan), True)

r = rencana_pekerja("", "", "1", "1")
check("gender kosong -> total dari status bayar", (r.total, r.nolkan_upah), (2, True))

r = rencana_pekerja("5", "5", "4", "4")
check("marginal sumber tidak konsisten -> diperingatkan",
      any("tidak konsisten" in c for c in r.catatan), True)

# --- rencana_pengeluaran: <=3 pekerja, upah dinolkan ---
b = baris(gaji="10000000", biaya_produksi="0", biaya_pembelian="100800000",
          operasional="5000000", non_operasional="1000000")
p = rencana_pengeluaran(b, has_26c=True, nolkan_upah=True)
check("26a dinolkan", p.upah_gaji, 0)
check("pos lain TIDAK diutak-atik saat dinolkan",
      (p.biaya_produksi, p.biaya_pembelian, p.operasional, p.non_operasional),
      (0, 10080000, 500000, 100000))
check("tidak ada potongan", p.potongan, [])
check("total = jumlah pos", p.total, 10680000)

# --- >3 pekerja: 26a dipotong dari pos TERBESAR ---
p = rencana_pengeluaran(b, has_26c=True, nolkan_upah=False)
check("26a = 10% sumber", p.upah_gaji, 1000000)
check("potongan dari pos terbesar (biaya_pembelian)", p.potongan, [("biaya_pembelian", 1000000)])
check("biaya_pembelian berkurang persis 26a", p.biaya_pembelian, 10080000 - 1000000)
check("pos lain utuh", (p.biaya_produksi, p.operasional, p.non_operasional), (0, 500000, 100000))
check("TOTAL pengeluaran tidak berubah oleh pemotongan", p.total, 10680000)

# --- kaskade: pos terbesar tidak cukup ---
b2 = baris(gaji="10000000", biaya_produksi="4000000", biaya_pembelian="0",
           operasional="3000000", non_operasional="0")
p = rencana_pengeluaran(b2, has_26c=True, nolkan_upah=False)
check("kaskade ke pos terbesar berikutnya",
      p.potongan, [("biaya_produksi", 400000), ("operasional", 300000)])
check("kaskade: pos habis jadi 0", (p.biaya_produksi, p.operasional), (0, 0))
check("kaskade: sisa yg tak tertutup diperingatkan",
      any("tidak cukup menutupi" in c for c in p.catatan), True)
check("kaskade: total naik sebesar sisa", p.total, 1000000)

# --- 26c tidak dirender -> 26b gabungan, dan itu yg jadi kandidat potong ---
b3 = baris(gaji="10000000", biaya_produksi="33600004", biaya_pembelian="4",
           operasional="1000000", non_operasional="0")
p = rencana_pengeluaran(b3, has_26c=False, nolkan_upah=False)
check("26c None saat tidak dirender", p.biaya_pembelian, None)
check("26b = gabungan (bulat sekali di akhir)", p.biaya_produksi, 3360001 - 1000000)
check("potongan kena 26b gabungan", p.potongan, [("biaya_produksi", 1000000)])

# --- upah 0 di sumber -> tidak ada pemotongan sama sekali ---
b4 = baris(gaji="0", biaya_produksi="5000000")
p = rencana_pengeluaran(b4, has_26c=True, nolkan_upah=False)
check("upah 0 -> tanpa potongan", (p.upah_gaji, p.potongan, p.biaya_produksi), (0, [], 500000))

# --- minimal 100.000 yang diwajibkan form (ketetapan user 2026-09-07) ---
b5 = baris(gaji="0", biaya_produksi="525000", biaya_pembelian="0",
           operasional="0", non_operasional="0")
p = rencana_pengeluaran(b5, has_26c=True, nolkan_upah=True)
check("26f di bawah 100rb dinaikkan pas ke 100rb", p.total, 100_000)
check("kekurangan masuk ke pos terbesar", p.biaya_produksi, 100_000)
check("kenaikan 26f diperingatkan", any("minimal" in c for c in p.catatan), True)

b6 = baris(gaji="0", biaya_produksi="0", biaya_pembelian="0",
           operasional="0", non_operasional="0")
p = rencana_pengeluaran(b6, has_26c=True, nolkan_upah=True)
check("semua pos nol -> ditampung operasional", (p.operasional, p.total), (100_000, 100_000))

p = rencana_pengeluaran(baris(gaji="0", biaya_produksi="5000000"),
                        has_26c=True, nolkan_upah=True)
check("26f di atas 100rb tidak diutak-atik", (p.total, p.catatan), (500_000, []))

pd = rencana_pendapatan(baris(nilai_pendapatan="600000", pendapatan_lain="0"))
check("27c di bawah 100rb dinaikkan pas ke 100rb", pd.total, 100_000)
check("kekurangan 27 masuk ke 27a", (pd.nilai_penjualan, pd.pendapatan_lain), (100_000, 0))
check("besar kenaikan 27 tercatat", pd.ditambah, 40_000)

pd = rencana_pendapatan(baris(nilai_pendapatan="0", pendapatan_lain="0"))
check("27 nol -> jadi 100rb di 27a", (pd.nilai_penjualan, pd.total), (100_000, 100_000))

pd = rencana_pendapatan(baris(nilai_pendapatan="2400000", pendapatan_lain="0"))
check("27c di atas 100rb tidak diutak-atik", (pd.total, pd.ditambah, pd.catatan), (240_000, 0, []))

print("\n" + ("SEMUA ATURAN LOLOS" if ok_all else "ADA YANG GAGAL"))
sys.exit(0 if ok_all else 1)
