# -*- coding: utf-8 -*-
"""Uji logika murni ubah_moda.py — offline, tanpa browser/VPN.
Jalankan: python tests/test_ubah_moda.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.gabungan_loader import GabunganRow, Pemeriksaan
from ganti_moda.ubah_moda import (
    STATUS_BERHENTI_SEGERA, STATUS_TUNTAS_LIVE, BarisAssignment, Berhenti, Target, angka_item_menu, bangun_target,
    baca_daftar, baris_dari_tabel, normalisasi_kode, pilih_tombol_konfirmasi, rencanakan, target_dari_daftar_kode,
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

# --- list kode identitas milik user (2026-09-15): HANYA kode itu yang diubah ---
# Kasus kembar dgn tests/test_ubah_moda_console.js.
check("normalisasi kode: spasi & huruf kecil & nol depan", normalisasi_kode(f"{S}-umk-04"), f"{S} - UMK - 4")
check("normalisasi kode: bukan kode", normalisasi_kode(S), "")
check("normalisasi kode: 17 digit bukan idsubsls", normalisasi_kode(f"9{S} - UMK - 4"), "")
dk_t, dk_tidak, dk_ganda = target_dari_daftar_kode([
    "Kode Identitas\tNama",
    f"{S} - UMK - 4\tWARUNG A",
    f"{S} - UMK - 41",
    f"{LAIN} - UMK - 2 ; {S} - umk - 4",
    "5108070013000999\tNIK tanpa kode",
    f"{S} - WARUNG - BU SRI - 12",
    f"{S} - NON-UMK - 3",
])
check("daftar kode: SATU target per kode, urutan list dipertahankan",
      [(t.kode, t.idsubsls, t.baris_sheet) for t in dk_t],
      [(f"{S} - UMK - 4", S, [2]), (f"{S} - UMK - 41", S, [3]), (f"{LAIN} - UMK - 2", LAIN, [4]),
       (f"{S} - NON-UMK - 3", S, [7])])
check("daftar kode: ganda dilaporkan", dk_ganda, [(4, f"{S} - UMK - 4")])
check("daftar kode: 16 digit tanpa pola kode dilaporkan", [x[0] for x in dk_tidak], [5, 6])
# Bentuk nyata dari list user & tabel fasih-sm (2026-09-15)
check("kode nama keluarga dgn '/'", normalisasi_kode("5108060029000102 - I KETUT REDIKA / I KOMANG AGUS SETIAWAN - 46"),
      "5108060029000102 - I KETUT REDIKA / I KOMANG AGUS SETIAWAN - 46")
check("kode nama diakhiri '/'", normalisasi_kode("5108070005000601 - WAYAN DERAWA / - 21"),
      "5108070005000601 - WAYAN DERAWA / - 21")
check("kode nama berangka", normalisasi_kode("5108020014000104 - MUH UMAR FARIDL / 1 - 48"),
      "5108020014000104 - MUH UMAR FARIDL / 1 - 48")
check("kode nama ber-apostrof & titik", normalisasi_kode(f"{S} - WR. MAK'E (BU TUT) - 9"), f"{S} - WR. MAK'E (BU TUT) - 9")
check("sel tabel berakhiran '/ - 81119'", normalisasi_kode("5108060029000102 - BANGUNAN KOSONG - 6 / - 81119"),
      "5108060029000102 - BANGUNAN KOSONG - 6")
check("sel tabel berakhiran '/ - 0'", normalisasi_kode("5108060029000102 - I KADEK RIKI SAPUTRA / KETUT ARINI - 46 / - 0"),
      "5108060029000102 - I KADEK RIKI SAPUTRA / KETUT ARINI - 46")
check("kode dari xlsx (tab + nama)", normalisasi_kode(f"{S} - DTSEN - 44\tNAMA"), f"{S} - DTSEN - 44")

# Pencarian memakai KODE itu sendiri; hasil pencarian "…- UMK - 4" bisa ikut memuat "- 41", "- 40", dst.
TK = Target(S, (), [2], kode=f"{S} - UMK - 4")
check("kode: istilah cari = kode identitas", TK.istilah_cari, f"{S} - UMK - 4")
check("sheet: istilah cari = idsubsls", T.istilah_cari, S)
r = rencanakan(TK, [b(41), b(4, petugas="x@gmail.com"), b(40)])
check("kode: pilih PERSIS '- 4', bukan '- 41'/'- 40'", (r.status, [x.kode for x in r.pilih]),
      ("PERLU_DIUBAH", [f"{S} - UMK - 4"]))
check("kode: baris lain yg ikut tampil dicatat", "2 baris kode lain" in r.pesan, True)
check("kode: kode di tabel beda spasi/huruf tetap cocok",
      rencanakan(TK, [BarisAssignment(kode=f"{S}-umk-4", mode="CAPI")]).status, "PERLU_DIUBAH")
check("kode: PAPI lain di subsls TIDAK membuat kode ini dilewati", rencanakan(TK, [b(41, "PAPI"), b(4)]).status,
      "PERLU_DIUBAH")
check("kode: sudah PAPI", rencanakan(TK, [b(4, "PAPI")]).status, "KODE_SUDAH_PAPI")
check("kode: KODE_SUDAH_PAPI tuntas", "KODE_SUDAH_PAPI" in STATUS_TUNTAS_LIVE, True)
check("kode: hasil kosong -> KODE_TIDAK_ADA (lanjut)", rencanakan(TK, []).status, "KODE_TIDAK_ADA")
check("kode: hanya kode lain subsls sama -> KODE_TIDAK_ADA", rencanakan(TK, [b(41)]).status, "KODE_TIDAK_ADA")
check("kode: tidak ada di halaman tampil tapi >1 halaman -> KODE_TIDAK_TAMPIL",
      rencanakan(TK, [b(41)], ada_halaman_lain=True).status, "KODE_TIDAK_TAMPIL")
check("kode: KODE_TIDAK_ADA/TIDAK_TAMPIL tidak tuntas & tidak menghentikan",
      [s in STATUS_TUNTAS_LIVE or s in STATUS_BERHENTI_SEGERA for s in ("KODE_TIDAK_ADA", "KODE_TIDAK_TAMPIL")],
      [False, False])
r = rencanakan(TK, [b(1, sub=LAIN), b(2, sub=LAIN)])
check("kode: hasil berisi subsls lain -> PENCARIAN_TIDAK_MENYARING (berhenti)",
      (r.status, r.status in STATUS_BERHENTI_SEGERA), ("PENCARIAN_TIDAK_MENYARING", True))
check("kode: kode sendiri tampil + subsls lain -> tetap kode itu saja",
      [x.kode for x in rencanakan(TK, [b(4), b(1, sub=LAIN)]).pilih], [f"{S} - UMK - 4"])
r = rencanakan(TK, [b(4), b(4)])
check("kode: tampil 2x -> KODE_GANDA (berhenti)", (r.status, r.status in STATUS_BERHENTI_SEGERA), ("KODE_GANDA", True))
check("kode: cakupan 'semua' diabaikan", len(rencanakan(TK, [b(4), b(41)], cakupan="semua").pilih), 1)
check("kode: mode aneh pada kode ini", rencanakan(TK, [b(4, "CAWI")]).status, "MODE_TIDAK_DIKENAL")
check("kode: mode aneh pada kode LAIN tidak menghalangi", rencanakan(TK, [b(41, "CAWI"), b(4)]).status,
      "PERLU_DIUBAH")
check("kunci: target sheet = idsubsls", T.kunci, S)
check("kunci: target kode = kode identitas", TK.kunci, f"{S} - UMK - 4")
check("cocok kode: '- 41' bukan '- 4'", [TK.cocok(x) for x in (b(4), b(41))], [True, False])
check("cocok sheet: semua baris subsls", [T.cocok(x) for x in (b(4), b(41), b(1, sub=LAIN))], [True, True, False])

# --- baca file daftar (.txt & .xlsx) ---
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    txt = Path(tmp) / "list.txt"
    txt.write_text(f"kode\n{S} - UMK - 4\n", encoding="utf-8")
    check("baca daftar .txt", baca_daftar(txt), ["kode", f"{S} - UMK - 4"])
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["No", "Kode Identitas"])
    wb.active.append([1, f"{S} - UMK - 4"])
    wb.create_sheet("lain").append([f"{LAIN} - UMK - 2"])
    xl = Path(tmp) / "list.xlsx"
    wb.save(xl)
    check("baca daftar .xlsx: sheet pertama saja", [t.kode for t in target_dari_daftar_kode(baca_daftar(xl))[0]],
          [f"{S} - UMK - 4"])
    check("baca daftar .xlsx: --sheet", [t.idsubsls for t in target_dari_daftar_kode(baca_daftar(xl, "lain"))[0]],
          [LAIN])

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
