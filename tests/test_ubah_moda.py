# -*- coding: utf-8 -*-
"""Uji logika murni ubah_moda.py — offline, tanpa browser/VPN.
Jalankan: python tests/test_ubah_moda.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.gabungan_loader import GabunganRow, Pemeriksaan
from ganti_moda.ubah_moda import (
    BarisAssignment, Berhenti, Target, angka_item_menu, bangun_target, baris_dari_tabel,
    pilih_tombol_konfirmasi, rencanakan,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


S = "5108070013000901"
PPL = "ppl@gmail.com"
T = Target(S, (PPL,), [2])


def b(no, mode="CAPI", petugas=PPL, sub=S, indeks=0):
    return BarisAssignment(kode=f"{sub} - UMK - {no}", mode=mode, petugas=petugas, indeks=indeks)


# --- tabel: judul & isi PERSIS seperti yang terbaca di fasih-sm 2026-09-13 ---
HEAD = ["", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist", "Nomor Urut Bangunan / IDSBR",
        "NIB / No. KK", "Email", "Skala Usaha / Jenis Prelist", "Jumlah Usaha", "Kode Pos", "Perubahan SLS",
        "IDSBR UMKM SLS Sama", "Status", "Mode", "Petugas Saat Ini", "Keterangan", ""]
ROW = ["", "5108060003000402 - UMK - 4", "MUJIANTI HARDSTONE", "DSN DHARMAKERTI", "58 / 30300442",
       "2210220006818", "mujiantihardstone468@gmail.com", "UMK / OSS PERORANGAN", "", "81119", "", "",
       "approved by pengawas", "CAPI", "erlinaw26@gmail.com", "Pengawas", ""]
hasil = baris_dari_tabel({"head": HEAD, "rows": [ROW, ["Tidak ada data"]]})
check("parse tabel: 1 baris, baris pesan dilewati", len(hasil), 1)
check("parse kolom lewat judul", (hasil[0].idsubsls, hasil[0].mode, hasil[0].petugas, hasil[0].keterangan),
      ("5108060003000402", "CAPI", "erlinaw26@gmail.com", "Pengawas"))
try:
    baris_dari_tabel({"head": [h for h in HEAD if h != "Mode"], "rows": []})
    check("kolom Mode disembunyikan -> berhenti", "tidak berhenti", "KOLOM_TIDAK_ADA")
except Berhenti as e:
    check("kolom Mode disembunyikan -> berhenti", e.kode, "KOLOM_TIDAK_ADA")

# --- rencanakan (cakupan satu) ---
LAIN = "5108010009000202"
check("tanpa assignment", rencanakan(T, []).status, "TIDAK_ADA_ASSIGNMENT")
check("mode aneh", rencanakan(T, [b(1, mode="CAWI")]).status, "MODE_TIDAK_DIKENAL")
check("sudah ada PAPI milik PPL", rencanakan(T, [b(1, "PAPI"), b(2)]).status, "SUDAH_ADA_PAPI")
r = rencanakan(T, [b(1, petugas="lain@gmail.com"), b(2), b(3)])
check("CAPI milik PPL didahulukan -> pilih tepat satu", (r.status, [x.kode for x in r.pilih]),
      ("PERLU_DIUBAH", [f"{S} - UMK - 2"]))
check("email petugas beda huruf besar tetap cocok",
      rencanakan(T, [b(1, petugas="x@gmail.com"), b(2, petugas="PPL@Gmail.com")]).pilih[0].kode, f"{S} - UMK - 2")
# Ketetapan user 2026-09-14: assignment MANA PUN di subsls itu boleh (dulu PETUGAS_BEDA / PAPI_ADA_PETUGAS_LAIN).
check("PAPI milik petugas lain sudah cukup",
      rencanakan(T, [b(1, "PAPI", "x@gmail.com"), b(2, petugas="y@gmail.com")]).status, "SUDAH_ADA_PAPI")
r = rencanakan(T, [b(1, petugas="x@gmail.com"), b(2, petugas="y@gmail.com")])
check("CAPI semua milik petugas lain -> tetap pilih satu", (r.status, [x.kode for x in r.pilih]),
      ("PERLU_DIUBAH", [f"{S} - UMK - 1"]))

# --- baris subsls lain di hasil pencarian (dryrun 2026-09-14) -> diabaikan, bukan berhenti ---
r = rencanakan(T, [b(1, sub=LAIN), b(2, petugas="x@gmail.com"), b(3, "PAPI", sub=LAIN)])
check("subsls lain diabaikan: pilih baris subsls target saja", (r.status, [x.kode for x in r.pilih]),
      ("PERLU_DIUBAH", [f"{S} - UMK - 2"]))
check("subsls lain dicatat di pesan", "2 baris subsls lain diabaikan" in r.pesan, True)
check("PAPI subsls lain tidak dihitung", rencanakan(T, [b(1, "PAPI", sub=LAIN), b(2)]).status, "PERLU_DIUBAH")
check("hanya subsls lain di halaman -> berhenti (pencarian tidak menyaring)",
      rencanakan(T, [b(1, sub=LAIN)]).status, "SUBSLS_TIDAK_TAMPIL")
check("halaman kosong tapi ada halaman lain -> berhenti",
      rencanakan(T, [], ada_halaman_lain=True).status, "SUBSLS_TIDAK_TAMPIL")

# --- paginasi TIDAK dipindah (temuan user 2026-09-14): hanya halaman tampil yang dibaca ---
r = rencanakan(T, [b(1)], ada_halaman_lain=True)
check("ada halaman lain tapi CAPI tampil -> tetap diubah, dicatat", (r.status, "hanya halaman tampil" in r.pesan),
      ("PERLU_DIUBAH", True))
check("ada halaman lain & PAPI tampil -> sudah cukup",
      rencanakan(T, [b(1), b(2, "PAPI")], ada_halaman_lain=True).status, "SUDAH_ADA_PAPI")

# --- rencanakan (cakupan semua) ---
r = rencanakan(T, [b(1), b(2, "PAPI"), b(3, petugas="x@gmail.com"), b(4, sub=LAIN)], cakupan="semua")
check("semua: seluruh CAPI subsls ini, PAPI & subsls lain dilewati", (r.status, len(r.pilih)), ("PERLU_DIUBAH", 2))
check("semua: sudah PAPI semua", rencanakan(T, [b(1, "PAPI")], cakupan="semua").status, "TIDAK_ADA_CAPI")
check("semua: tanpa CAPI tampil tapi ada halaman lain -> berhenti",
      rencanakan(T, [b(1, "PAPI")], cakupan="semua", ada_halaman_lain=True).status, "PERLU_HALAMAN_LAIN")

# --- menu & dialog ---
check("angka item menu (spasi)", angka_item_menu("Ganti Mode (Ke PAPI) (3)"), 3)
check("angka item menu (rapat + baris baru)", angka_item_menu("Ganti Mode (Ke PAPI)\n(0)"), 0)
check("angka item menu tidak ada", angka_item_menu("Ganti Mode (Ke PAPI)"), None)
check("tombol konfirmasi tunggal", pilih_tombol_konfirmasi(["Batal", "Ya, Ganti Mode"]), 1)
check("tombol 'Tidak' bukan konfirmasi", pilih_tombol_konfirmasi(["Tidak", "Ya"]), 1)
check("tanpa tombol konfirmasi", pilih_tombol_konfirmasi(["Batal", "Tutup"]), None)
check("dua kandidat -> ambigu", pilih_tombol_konfirmasi(["Ya", "Simpan"]), None)

# --- target dari sheet ---
def g(baris, ids, pilih=None, ppl=PPL):
    v = {"idsubsls": ids, "akun_ppl": ppl, "nama": f"U{baris}", "pilih_prov": (pilih or ids)[:2],
         "pilih_kab": (pilih or ids)[2:4], "pilih_kec": (pilih or ids)[4:7], "pilih_desa": (pilih or ids)[7:10],
         "pilih_sls": (pilih or ids)[10:14], "pilih_subsls": (pilih or ids)[14:16]}
    return GabunganRow(baris, v)


rows = [g(2, S), g(3, S), g(4, "5108070013000902"), g(5, "5108010001200100", pilih="5108010001000302")]
cek = {2: Pemeriksaan(), 3: Pemeriksaan([("X", "")]), 4: Pemeriksaan([("X", "")]), 5: Pemeriksaan()}
targets, keluar = bangun_target(rows, cek)
check("satu target per idsubsls, baris digabung",
      [(t.idsubsls, t.baris_sheet, t.siap_input) for t in targets],
      [(S, [2, 3], True), ("5108070013000902", [4], False)])
check("idsubsls tidak konsisten dikeluarkan", keluar, [(5, "5108010001200100", "5108010001000302")])
check("--hanya-siap", [t.idsubsls for t in bangun_target(rows, cek, hanya_siap=True)[0]], [S])

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
