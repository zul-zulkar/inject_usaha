"""
tahap2_loader.py — Baca FORMAT TAHAP 2 (bahan/input_tahap2.xlsx) — hasil
pendataan KERTAS Sensus Ekonomi 2026 tahap 2 — lalu ubah jadi baris yang
BENTUKNYA SAMA dgn FORMAT STANDAR (gabungan_loader.GabunganRow), supaya
seluruh alur input otomatis yang sudah teruji dipakai apa adanya:
periksa_semua() -> main_gabungan.process_one_row() -> fill_blok2_gabungan().

Kenapa adaptor, bukan alur baru: jalur pengisian & pengiriman fasih-web
adalah bagian paling mahal (dan paling irreversible) di repo ini. Format
tahap 2 hanya beda SUMBER KOLOM, jadi yang ditambah cuma pemetaan kolom +
pemeriksaan khas tahap 2; logika browser tidak disentuh sama sekali.

BEDA POKOK DGN FORMAT STANDAR (input_usaha.xlsx)
------------------------------------------------
1. Kolomnya jauh lebih sedikit (48 vs 92): hanya rincian yang benar-benar
   ditanyakan di kuesioner kertas. Rincian lain diisi TAHAP2_DEFAULT
   (ketetapan user 2026-09-22) & dicatat sbg ASUMSI di review_disarankan.
2. Judul kolom PENDEK dan sebagian ambigu ("3", "4", "5", "24.Total" 2x),
   jadi dicocokkan PERSIS (bukan awalan seperti gabungan_loader) dan
   kemunculan ganda dipetakan berurutan.
3. Nilai opsi ditulis sbg KODE ANGKA ("12b" = "1", "22" = "5"), bukan teks
   opsi form -> opsi_dari_kode() mengubahnya jadi teks OPSI_FORM. Kode yang
   tidak cocok/ambigu dikosongkan supaya periksa_baris men-skip barisnya,
   BUKAN ditebak.
4. Uang ditulis "Rp10.500.000", desimal pakai koma ("-8,2004731") -> diubah
   ke angka polos.
5. 13b1/b2/b3 tidak ada kolomnya -> diturunkan dari golongan KBLI
   (TAHAP2_13B_DARI_KBLI, ketetapan user 2026-09-22).
6. Ada kolom TOTAL (24.Total 2x, Rp26, 27c, 28c) yang di form dihitung
   otomatis. Kolom itu TIDAK dikirim, tapi dipakai memeriksa konsistensi
   rincian: tidak cocok -> baris di-skip SEBELUM dokumen dibuat.

SEMUA kolom default di TAHAP2_DEFAULT bisa ditimpa per baris dgn menambah
kolomnya di Excel (mis. "11a", "13c", "29a") — lihat KOLOM_TAHAP2_TAMBAHAN.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from inti.config import (
    KODEPOS_BY_DESA, KODEPOS_BY_IDSUBSLS, TAHAP2_13B_DARI_KBLI, TAHAP2_13DE_DARI_KBLI, TAHAP2_26C_KE_26B,
    TAHAP2_DEFAULT, TAHAP2_GAJI_JIKA_DIBAYAR, TAHAP2_HP_TIDAK_VALID_JADI, TAHAP2_ISI_VARIAN_BULANAN,
    TAHAP2_NIK_TIDAK_VALID_JADI, TAHAP2_PEKERJA_IKUT_JK_PEMILIK, TAHAP2_TOTAL_BEDA,
    TAHAP2_UANG_KOSONG_JADI_NOL, TAHAP2_16B_LIMA_NILAI_B6, TAHAP2_PEMBEDA_13F_UTK_GANDA,
)
from inti.gabungan_loader import (
    KEY_16B, KEY_26, KEY_27, KEY_28, KEY_29, KEY_PEKERJA, MAKS_8B, OPSI_FORM, YA_TIDAK, GabunganRow, Pemeriksaan,
    _norm_judul, _sel, format_nama_usaha, hp_valid, judul_dari_opsi_kbli, kbli_tanpa_26c, nama_muat, nama_tampil,
    nik_valid, periksa_semua,
)

# Nama tab yang diterima. File contoh dari user bertab "Sheet1"; tab yang
# namanya cocok salah satu di bawah menang, kalau tidak ada dipakai tab PERTAMA.
NAMA_SHEET_TAHAP2 = ("input_tahap2", "tahap2", "tahap 2")

# ---------------------------------------------------------------------------
# Pemetaan kolom. Judul dicocokkan PERSIS (setelah _norm_judul: huruf kecil,
# spasi dirapikan, spasi di sekitar titik dibuang) — bukan awalan, karena
# "28c" dan "28c1" akan saling cocok kalau memakai awalan.
# Nilai dict = judul kolom; key = key FORMAT STANDAR (gabungan_loader.KOLOM)
# kalau ada padanannya, atau berawalan "cek_"/"info_" kalau tidak dikirim.
# ---------------------------------------------------------------------------
KOLOM_TAHAP2: dict[str, str] = {
    "info_sumber_kec": "sumber/kec.",
    "info_periode": "periode",
    "info_uraian": "uraian:",
    "info_nama_ppl": "nama ppl",
    "info_kec": "3",
    "info_desa": "4",
    "idsubsls": "5",
    "nama_komersial": "8b.",
    "jalan_domisili": "8c.",          # alamat tertulis di kuesioner -> Nama Jalan SE2026-P
    "hp": "no wa",
    "pengusaha": "12a",
    "jk": "12b",
    "umur": "12c",
    "nik_pengusaha": "12d",
    "keg_utama": "13a",
    "produk": "13f",
    "jaringan": "14a",
    "internet": "16a",
    "internet_semua": "16b1-b6",      # satu kode Ya/Tidak utk KEENAM rincian
    "perlindungan_lingkungan": "17b",
    "mitra_kdkmp": "21",
    "peran_mbg": "22",
    "tk_laki": "24.l",
    "tk_pr": "24.p",
    "cek_tk_gender": "24.total",      # kemunculan ke-1: 24a1 + 24b1
    "tk_dibayar": "24.dibayar",
    "tk_tdk_dibayar": "24.tidak dibayar",
    "cek_tk_bayar": "24.total",       # kemunculan ke-2: 24a2 + 24b2
    "tahun_operasi": "25",
    "cek_26f": "rp26",                # total pengeluaran 26f (ketetapan user 2026-09-22)
    "gaji": "26a",
    "biaya_produksi": "26b",
    "biaya_pembelian": "26c",
    "operasional": "26d",
    "non_operasional": "26e",
    "nilai_pendapatan": "27a",
    "pendapatan_lain": "27b",
    "cek_27c": "27c",
    "pendapatan_online": "27d",
    "aset_usaha_thn": "28a",          # label asli: aset TANAH & BANGUNAN
    "aset_lain_thn": "28b",           # label asli: aset SELAIN tanah & bangunan
    "cek_28c": "28c",
    "info_28c1": "28c1",              # arti belum diketahui — tidak dikirim, tidak dicek
    "luas_tanah_thn": "28d",
    "latitude": "latitude",
    "longitude": "longitude",
    "kbli": "kode kbli",
    "info_judul_kbli": "judul kbli",
}

# Kolom yang boleh TIDAK ADA di sheet (sisanya wajib ada, kalau hilang
# load_tahap2 berhenti dgn ValueError supaya salah file ketahuan segera).
KOLOM_TAHAP2_OPSIONAL = {
    "info_sumber_kec", "info_periode", "info_uraian", "info_kec", "info_desa",
    "info_judul_kbli", "info_28c1", "cek_tk_gender", "cek_tk_bayar", "cek_26f",
    "cek_27c", "cek_28c", "internet_semua", "produk",
}

# Kolom TAMBAHAN (semuanya opsional): kalau ada di sheet, nilainya MENANG
# atas TAHAP2_DEFAULT untuk baris itu. Dipakai kalau sebagian usaha butuh
# jawaban lain (mis. badan usaha CV, kawasan pasar) tanpa mengubah kode.
KOLOM_TAHAP2_TAMBAHAN: dict[str, str] = {
    "akun_ppl": "akun ppl",           # email PPL (kalau sheet punya); "nama ppl" TIDAK dipakai login
    "kodepos": "kodepos",
    "nomor_domisili": "blok/nomor",
    "jenis_kawasan": "8d.",
    "punya_nib": "10a",
    "nib_nomor": "10b",
    "tidak_nib": "10c",
    "badan_usaha": "11a",
    "lap_keuangan": "11d",
    "produk_sendiri": "13b1",
    "layanan_mamin": "13b2",
    "keg_penjualan": "13b3",
    "keg_jasa": "13b4",
    "lokasi_usaha": "13c",
    "input_produksi": "13d",
    "proses_produksi": "13e",
    "digital": "16c",
    "produksi_lingkungan": "17a",
    "produk_seni": "18",
    "halal": "19a",
    "sudah_halal": "19b",
    "belum_halal": "19c",
    "izin_edar": "20a",
    "sudah_bpom": "20b",
    "belum_bpom": "20c",
    "barang_non_pddk": "23a",
    "jasa_non_pddk": "23b",
    "beli_jasa_non_pddk": "23c",
    "pribadi": "29a",
    "non_profit": "29b",
    "publik": "29c",
    "non_publik": "29d",
    "pemerintah": "29e",
    "asing": "29f",
}

# Kolom yang isinya KODE ANGKA opsi form (lihat opsi_dari_kode).
KEY_BERKODE = (
    "jk", "jaringan", "internet", "perlindungan_lingkungan", "mitra_kdkmp", "peran_mbg",
    "jenis_kawasan", "punya_nib", "tidak_nib", "badan_usaha", "lap_keuangan", "lokasi_usaha",
    "produk_sendiri", "layanan_mamin", "keg_penjualan", "keg_jasa", "digital",
    "produksi_lingkungan", "produk_seni", "barang_non_pddk", "jasa_non_pddk",
    "beli_jasa_non_pddk", "halal", "izin_edar", *KEY_16B,
)
# Kolom uang ("Rp10.500.000" -> "10500000").
KEY_RUPIAH = (*KEY_26, *KEY_27, "aset_usaha_thn", "aset_lain_thn")
# Kolom bilangan bulat polos.
KEY_BULAT = (*KEY_PEKERJA, "umur", "tahun_operasi", "luas_tanah_thn", *KEY_29,
             "sudah_halal", "belum_halal", "sudah_bpom", "belum_bpom")

# (key cek, key rincian yang dijumlahkan, nama rincian utk pesan)
CEK_TOTAL: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("cek_tk_gender", ("tk_laki", "tk_pr"), "24a1+24b1"),
    ("cek_tk_bayar", ("tk_dibayar", "tk_tdk_dibayar"), "24a2+24b2"),
    ("cek_26f", KEY_26, "26a+26b+26c+26d+26e"),
    ("cek_27c", KEY_27, "27a+27b"),
    ("cek_28c", ("aset_usaha_thn", "aset_lain_thn"), "28a+28b"),
)


# ---------------------------------------------------------------------------
# Pengubah nilai
# ---------------------------------------------------------------------------

def rupiah_ke_angka(teks) -> str:
    """"Rp10.500.000" / "Rp 10.500.000,00" / "10500000" -> "10500000".
    Kosong, "-" atau tak terbaca -> "" (periksa_baris yang menolaknya)."""
    t = " ".join(str(teks or "").split())
    if not t or t in ("-", "–"):
        return ""
    t = re.sub(r"(?i)^rp\.?\s*", "", t).replace(" ", "")
    t = t.split(",")[0]          # koma = desimal (rupiah selalu bulat di form)
    t = t.replace(".", "")       # titik = pemisah ribuan
    if not re.fullmatch(r"-?\d+", t):
        return ""
    return str(int(t))


def desimal_ke_titik(teks) -> str:
    """"-8,2004731" -> "-8.2004731"; "1.234,56" -> "1234.56"; "114.79" tetap."""
    t = " ".join(str(teks or "").split()).replace(" ", "")
    if not t:
        return ""
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return t


def persen_ke_bulat(teks) -> str:
    """27d "0,00" -> "0" (form meminta bilangan bulat). Pembulatan half-up
    sama dgn aturan finansial repo ini; kalau nilainya berubah, pemanggil
    mencatatnya sbg koreksi. Tanda persen dibuang: "10%" -> "10" (data asli
    2026-09-24, 252 baris sempat dianggap kosong)."""
    t = desimal_ke_titik(str(teks or "").strip().rstrip("%").strip())
    if not t:
        return ""
    try:
        return str(int(Decimal(t).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except (InvalidOperation, ValueError):
        return ""


def _beda_angka(mentah, hasil: str) -> bool:
    """True kalau pembulatan benar-benar mengubah NILAI ("12,5" -> 13), bukan
    cuma penulisannya ("0,00" -> "0")."""
    try:
        return Decimal(desimal_ke_titik(mentah)) != Decimal(hasil)
    except (InvalidOperation, ValueError):
        return True


def normalkan_hp(teks) -> str:
    """"81340828334" -> "081340828334" (Excel membuang nol di depan);
    "+6281..." / "6281..." -> "081...". Bukan nomor -> apa adanya."""
    t = " ".join(str(teks or "").split())
    if not t:
        return ""
    if re.search(r"\d[.,]?\d*E\+?\d+", t, flags=re.I):
        return t   # "8,13E+10": digit asli sudah hilang di Excel -> dibiarkan TIDAK valid
    digit = re.sub(r"[^\d]", "", t)
    if not digit:
        return t
    if digit.startswith("62") and len(digit) >= 11:
        digit = "0" + digit[2:]
    elif digit.startswith("8"):
        digit = "0" + digit
    return digit


# Singkatan yang dipakai operator entri (data asli 2026-09-22: 12b "L"/"P",
# 16b "Y"/"T"). Dipakai HANYA kalau opsi tujuannya memang ada di komponen itu,
# jadi "P" tidak pernah jadi apa pun selain "Perempuan".
ALIAS_OPSI = {
    "L": "LAKILAKI", "LK": "LAKILAKI", "LAKI": "LAKILAKI", "PRIA": "LAKILAKI",
    "P": "PEREMPUAN", "PR": "PEREMPUAN", "WANITA": "PEREMPUAN",
    "Y": "YA", "T": "TIDAK", "TDK": "TIDAK", "TAK": "TIDAK",
}

# Alias yang hanya berlaku utk SATU rincian, krn label opsinya tidak berbunyi
# "Ya"/"Tidak" polos. 21 "peran_mbg" (: "5. Tidak terlibat MBG") -> jawaban kertas
# "TIDAK"/"Tidak"/"tidak" dulu ditolak OPSI_TIDAK_ADA_DI_FORM (249 baris data asli
# 2026-09-23). "YA" sengaja TIDAK dipetakan: ada 4 varian Ya, tidak boleh ditebak.
ALIAS_OPSI_PER_KEY = {
    "peran_mbg": {"TIDAK": "5. Tidak terlibat MBG", "TIDAKTERLIBAT": "5. Tidak terlibat MBG",
                  "TIDAKADA": "5. Tidak terlibat MBG"},
    # 17b di form cuma Ya/Tidak; 140 baris data asli (2026-09-24) berisi "3" = opsi
    # ke-3 kuesioner kertas ("Tidak sama sekali"/"Tidak tahu") -> sama-sama bukan Ya.
    "perlindungan_lingkungan": {"3": "2. Tidak"},
}


def _norm_opsi(teks: str) -> str:
    """Huruf besar, hanya huruf & angka: "Laki - laki" -> "LAKILAKI"."""
    return re.sub(r"[^A-Z0-9]", "", str(teks or "").upper())


def opsi_dari_kode(key: str, nilai) -> str:
    """Kode angka ATAU teks jawaban sheet -> teks opsi form.
    "1" (12b) -> "1. Laki-laki"; "LAKI - LAKI" / "L" -> "1. Laki-laki";
    "YA" -> "1. Ya". Teks yang SUDAH berupa opsi form diteruskan apa adanya.
    Kode/teks yang tidak ada atau AMBIGU (mis. "1" utk 11a yang punya
    "1.a."/"1.b.") -> "" supaya periksa_baris men-skip barisnya; teks yang
    sama sekali tidak dikenal diteruskan & ditolak periksa_baris. Tidak
    pernah ditebak: teks hanya cocok kalau SAMA PERSIS dgn label opsi
    (setelah membuang nomor, spasi & tanda baca) atau singkatan ALIAS_OPSI."""
    t = " ".join(str(nilai or "").split())
    opsi = OPSI_FORM.get(key, ())
    if not t or not opsi or t in opsi:
        return t
    khusus = ALIAS_OPSI_PER_KEY.get(key, {}).get(_norm_opsi(t))
    if khusus:
        return khusus
    m = re.fullmatch(r"(\d+)\.?", t)
    if m:
        cocok = [o for o in opsi if re.match(rf"^{m.group(1)}\.(?!\d)", o)]
        return cocok[0] if len(cocok) == 1 else ""
    # "2. PEREMPUAN" (opsi form beda huruf besar/kecil): nomornya harus sama juga.
    m = re.match(r"^\s*(\d+(?:\.[a-z])?)\.\s*(.+)$", t, flags=re.I)
    nomor, teks = (m.group(1).lower(), m.group(2)) if m else ("", t)
    target = ALIAS_OPSI.get(_norm_opsi(teks), _norm_opsi(teks))
    cocok = [o for o in opsi if _norm_opsi(re.sub(r"^\s*\d+(\.[a-z])?\.\s*", "", o)) == target
             and (not nomor or o.lower().startswith(nomor + "."))]
    return cocok[0] if len(cocok) == 1 else t


# Kata kunci 16b di sheet -> indeks rincian (KEY_16B: b1 pesanan, b2 produksi,
# b3 distribusi, b4 beli bahan baku, b5 promosi, b6 lainnya). "KOMUNIKASI" bukan
# salah satu b1-b5 -> b6 Lainnya (data asli 2026-09-22, 27 baris).
KATA_16B = {
    "PESAN": 0, "PESANAN": 0, "PRODUKSI": 1, "DISTRIBUSI": 2, "BELI": 3, "PEMBELIAN": 3,
    "PROMOSI": 4, "IKLAN": 4, "LAIN": 5, "LAINNYA": 5, "KOMUNIKASI": 5, "KOMONIKASI": 5,
}


def _16b_bentuk_lain(t: str) -> set[int] | None:
    """Bentuk tulisan 16b yang dipakai PPL di data asli 2026-09-24 (t sudah huruf
    besar) -> {indeks rincian yang Ya}; None = bukan salah satu bentuk ini.
      "B1.YA, B2. TIDAK, B3.YA, B4. YA, B5YA,B6.TIDAK" -> pasangan rincian+jawaban
      "1,4,6 YA" / "4,6 YA" / "B4 YA" / "6 YA"        -> rincian yang disebut Ya
      "B1-B3. 1"                                       -> rentang rincian Ya
    Rincian yang tidak disebut = Tidak. Nomor di luar 1-6 ("B7") -> None."""
    pasangan = re.findall(r"B\s*([1-6])\s*[.:=]?\s*(YA|TIDAK)\b", t)
    if pasangan and not re.sub(r"B\s*[1-6]\s*[.:=]?\s*(YA|TIDAK)\b|[,;\s]", "", t):
        return {int(n) - 1 for n, j in pasangan if j == "YA"}
    m = re.fullmatch(r"((?:B?\s*[1-6]\s*[,;&\s]\s*)*B?\s*[1-6])\s*[.:=]?\s*(YA|1)", t)
    if m and (m.group(2) == "YA" or "B" in m.group(1)):
        return {int(n) - 1 for n in re.findall(r"[1-6]", m.group(1))}
    m = re.fullmatch(r"B?\s*([1-6])\s*-\s*B?\s*([1-6])\s*[.:=]?\s*(YA|1)", t)
    if m and int(m.group(1)) <= int(m.group(2)):
        return set(range(int(m.group(1)) - 1, int(m.group(2))))
    return None


def rencana_16b(teks) -> tuple[dict | None, str]:
    """Kolom "16b1-b6" -> ({key 16b: "1. Ya"/"2. Tidak"} , catatan).
    Bentuk yang dikenali (data asli 2026-09-22):
      "1" / "YA" / "2" / "TIDAK"   -> berlaku utk KEENAM rincian
      "1,2,1,1,1,1"                -> per rincian, 6 nilai
      "2,1,2,2,2"                  -> 5 nilai = b1..b5, b6 dari TAHAP2_16B_LIMA_NILAI_B6
      "B1,B3"                      -> rincian itu Ya, sisanya Tidak
      "PROMOSI" / "PROMOSI/KOMUNIKASI" -> lewat KATA_16B, sisanya Tidak
    Kosong/"-" -> ({}, ""). Tidak dikenali / jumlah nilai bukan 6 -> (None,
    alasan): baris di-skip kalau 16a = Ya, TIDAK ditebak rincian mana."""
    t = " ".join(str(teks or "").split()).upper()
    if not t or t in ("-", "\u2013"):
        return {}, ""
    tunggal = opsi_dari_kode("internet_pesanan", t)
    if tunggal in YA_TIDAK:
        return {k: tunggal for k in KEY_16B}, f"16b1-b6 diisi '{tunggal}' dari satu kolom '16b1-b6'"
    ya = _16b_bentuk_lain(t)
    if ya is not None:
        return ({k: "1. Ya" if i in ya else "2. Tidak" for i, k in enumerate(KEY_16B)},
                f"16b1-b6 '{t}' -> Ya utk " + (",".join(f"b{i + 1}" for i in sorted(ya)) or "tidak ada"))
    bagian = [b for b in re.split(r"[,;/_\s]+", t) if b]
    if all(b in ("1", "2") for b in bagian):
        if len(bagian) == len(KEY_16B) - 1 and TAHAP2_16B_LIMA_NILAI_B6:
            # Ketetapan user 2026-09-23: 5 nilai = b1..b5 berurutan, b6 "Lainnya"
            # = TAHAP2_16B_LIMA_NILAI_B6. Empat PPL SELALU menulis 5 nilai (92 baris).
            hasil = {k: "1. Ya" if b == "1" else "2. Tidak" for k, b in zip(KEY_16B, bagian)}
            hasil[KEY_16B[-1]] = TAHAP2_16B_LIMA_NILAI_B6
            return hasil, (f"16b1-b6 '{t}' berisi 5 nilai -> dianggap b1-b5, "
                           f"b6 Lainnya = '{TAHAP2_16B_LIMA_NILAI_B6}'")
        if len(bagian) != len(KEY_16B):
            return None, (f"16b1-b6 '{t}' berisi {len(bagian)} nilai utk 6 rincian — tidak jelas rincian "
                          "mana yang dimaksud; tulis 6 nilai (mis. 2,1,2,2,2,2)")
        return ({k: "1. Ya" if b == "1" else "2. Tidak" for k, b in zip(KEY_16B, bagian)},
                f"16b1-b6 dari daftar '{t}'")
    if all(re.fullmatch(r"B[1-6]", b) for b in bagian):
        ya = {int(b[1]) - 1 for b in bagian}
    elif all(b in KATA_16B for b in bagian):
        ya = {KATA_16B[b] for b in bagian}
    else:
        return None, f"16b1-b6 '{t}' tidak dikenali (pakai kode 1/2, daftar 6 nilai, atau B1..B6)"
    return ({k: "1. Ya" if i in ya else "2. Tidak" for i, k in enumerate(KEY_16B)},
            f"16b1-b6 '{t}' -> Ya utk " + ",".join(f"b{i + 1}" for i in sorted(ya)))


def isian_13de_dari_kbli(judul_kbli: str, keg: str) -> tuple[str, str]:
    """(13d input, 13e proses) dari judul KBLI (ketetapan user 2026-09-22:
    industri memakai nama dari kode KBLI). 13d minimal 4 karakter; 13e
    15-100 karakter (lengthInput template) -> judul yang terlalu pendek
    didahului 13a, yang terlalu panjang dipotong di batas kata."""
    judul = " ".join(judul_dari_opsi_kbli(judul_kbli).split())
    if not judul:
        return "", ""
    proses = judul if len(judul) >= 15 else " ".join(f"{keg} {judul}".split())
    if len(proses) > 100:
        proses = proses[:100].rsplit(" ", 1)[0]
    return judul, proses


def gol_kbli(kbli: str) -> int | None:
    k = re.sub(r"\D", "", str(kbli or ""))
    return int(k[:2]) if len(k) >= 2 else None


def rencana_13b(kbli: str) -> dict[str, str]:
    """13b1/b2/b3 diturunkan dari golongan KBLI (TAHAP2_13B_DARI_KBLI,
    ketetapan user 2026-09-22). Golongan di luar daftar -> ketiganya
    "2. Tidak" (form lalu merender 13b4, diisi dari kategori 13h)."""
    hasil = {"produk_sendiri": "2. Tidak", "layanan_mamin": "2. Tidak", "keg_penjualan": "2. Tidak"}
    gol = gol_kbli(kbli)
    if gol is None:
        return hasil
    for (awal, akhir), key in TAHAP2_13B_DARI_KBLI:
        if awal <= gol <= akhir:
            hasil[key] = "1. Ya"
            break
    return hasil


def kodepos_untuk(idsubsls: str, dari_sheet: str = "", cadangan: str = "") -> str:
    """Urutan sumber kodepos (template tahap 2 tidak punya kolomnya):
    kolom sheet -> KODEPOS_BY_IDSUBSLS (persis) -> KODEPOS_BY_DESA ->
    mayoritas KODEPOS_BY_IDSUBSLS desa yang sama -> `cadangan` (--kodepos).
    Semuanya kosong -> "" (baris di-skip WAJIB_KOSONG, tidak ditebak)."""
    if dari_sheet:
        return dari_sheet
    if idsubsls in KODEPOS_BY_IDSUBSLS:
        return KODEPOS_BY_IDSUBSLS[idsubsls]
    desa = idsubsls[:10]
    if desa in KODEPOS_BY_DESA:
        return KODEPOS_BY_DESA[desa]
    sedesa = {v for k, v in KODEPOS_BY_IDSUBSLS.items() if k[:10] == desa and desa}
    if len(sedesa) == 1:
        return sedesa.pop()
    return cadangan


# ---------------------------------------------------------------------------
# Baris
# ---------------------------------------------------------------------------

@dataclass
class Tahap2Row(GabunganRow):
    """GabunganRow + kolom khas tahap 2 yang TIDAK dikirim ke form."""
    cek: dict = field(default_factory=dict)   # {key cek: angka} utk periksa_total
    info: dict = field(default_factory=dict)  # kolom informasi (uraian, nama PPL, dst.)
    # 13f pembeda usaha pecahan bernama sama (lihat beri_pembeda_ganda). Kosong = tidak ada.
    pembeda: str = ""

    def _nama_dgn_pembeda(self, nama: str) -> str:
        """"<8b> (<12a>)"; usaha pecahan bernama sama: "<8b> <13f> (<12a>)". Yang
        terakhir > MAKS_8B -> "<13f> (<12a>)" (8b generik "warung bu" dilepas, 13f
        yang membedakan). Masih kepanjangan -> 8B_TERLALU_PANJANG, BUKAN cadangan
        nama_muat tanpa (<12a>): tanpa pemilik, 13f generik ("air galon") bentrok
        dgn usaha pecahan pemilik lain."""
        if not self.pembeda:
            return nama_muat(nama_tampil(nama, self.akhiran_badan), self["pengusaha"])
        hasil = format_nama_usaha(nama_tampil(f"{nama} {self.pembeda}", self.akhiran_badan), self["pengusaha"])
        if len(hasil) > MAKS_8B:
            hasil = format_nama_usaha(self.pembeda, self["pengusaha"])
        return hasil

    @property
    def nama_dokumen(self) -> str:
        return self._nama_dgn_pembeda(self.nama)

    @property
    def nama_komersial(self) -> str:
        return self._nama_dgn_pembeda(self["nama_komersial"])

    @property
    def nama_lama_dicari(self) -> str:
        """Kosong: alur tahap 2 baru ada 2026-09-22, jadi TIDAK PERNAH ada
        dokumen yang dibuat dgn nama mentah sheet. Mengaktifkan pengaman itu
        justru berbahaya di sini — nama usaha kuesioner kertas sering berulang
        ("WARUNG", "TOKO KELONTONG"), dan dokumen responden kedua akan
        di-skip SKIP_DOKUMEN_NAMA_LAMA gara-gara dokumen responden pertama.
        Pembeda antar-responden ada di nama dokumen: "<8b> (<12a>)"."""
        return ""

    @property
    def bulanan_dari_kolom(self) -> bool:
        """Kuesioner kertas tahap 2 menanyakan 30-33 (bulanan) dgn kolom yang
        sama dgn 26-29 -> kolomnya diisikan apa adanya (TAHAP2_ISI_VARIAN_BULANAN)."""
        return TAHAP2_ISI_VARIAN_BULANAN

    @property
    def idsubsls_pilih(self) -> str:
        """Sheet tahap 2 TIDAK punya kolom "Pilih PROVINSI..SUBSLS" terpisah —
        kode wilayah cuma ada satu (kolom "5"). Dikembalikan sama dgn idsubsls
        supaya periksa_baris tidak melaporkan WILAYAH_TIDAK_KONSISTEN thd
        kolom yang memang tidak ada (bukan melewatkan pemeriksaan nyata)."""
        return self.idsubsls

    @property
    def kunci(self) -> str:
        """Beda dgn GabunganRow: nama pengusaha IKUT dihitung. Sheet tahap 2
        memakai nama usaha generik ("USAHA JUAL BERAS") yang gampang berulang
        antar responden; tanpa 12a, dua responden berbeda akan dianggap
        BARIS_GANDA. Tetap dari kolom MENTAH (bukan nama_dokumen) supaya
        aturan penamaan boleh berubah tanpa memutus --lewati-selesai.
        Pembeda 13f ikut dihitung HANYA kalau ada (baris yang dulu BARIS_GANDA,
        jadi belum pernah punya dokumen -> tidak ada audit lama yang terputus)."""
        return self._kunci_dasar(self.pembeda)

    def _kunci_dasar(self, pembeda: str = "") -> str:
        teks = f"{self.akun_ppl}|{self.idsubsls}|{self.nama.upper()}|{self['pengusaha'].upper()}"
        if pembeda:
            teks += f"|{pembeda.upper()}"
        return hashlib.sha1(teks.encode("utf-8")).hexdigest()[:10]


def beri_pembeda_ganda(rows: list[Tahap2Row]) -> None:
    """Usaha pecahan (ketetapan user 2026-09-23, TAHAP2_PEMBEDA_13F_UTK_GANDA):
    baris dgn kunci dasar sama (akun+idsubsls+8b+12a) tapi 13f BERBEDA =
    satu warung dgn beberapa produk ("warung (gede wirawan)" x7: sembako,
    dupa, galon, ...), bukan duplikat. Baris seperti itu diberi pembeda 13f
    -> nama dokumen, 8b & kunci jadi unik. Baris yang 13f-nya juga sama (atau
    kosong) dibiarkan -> tetap BARIS_GANDA (duplikat asli, tidak ditebak)."""
    if not TAHAP2_PEMBEDA_13F_UTK_GANDA:
        return
    grup: dict[str, list[Tahap2Row]] = defaultdict(list)
    for r in rows:
        grup[r._kunci_dasar()].append(r)
    for anggota in grup.values():
        if len(anggota) < 2:
            continue
        produk = [" ".join(r["produk"].split()) for r in anggota]
        jumlah = defaultdict(int)
        for p in produk:
            jumlah[p.upper()] += 1
        daftar = [r.baris for r in anggota]
        for r, p in zip(anggota, produk):
            if p and jumlah[p.upper()] == 1:
                r.pembeda = p
                r.koreksi.append(f"usaha pecahan bernama sama (baris {daftar}) -> nama dibedakan 13f "
                                 f"'{p}': {r.nama_dokumen}")


def _indeks_tahap2(judul: list[str]) -> dict[str, int]:
    """Judul -> {key: indeks kolom}. Judul dicocokkan PERSIS; judul yang
    muncul lebih dari sekali ("24.Total") dibagikan BERURUTAN ke key-key
    yang memintanya, sesuai urutan KOLOM_TAHAP2."""
    norm = [_norm_judul(j) for j in judul]
    posisi: dict[str, list[int]] = defaultdict(list)
    for i, h in enumerate(norm):
        if h:
            posisi[h].append(i)
    dipakai: dict[str, int] = defaultdict(int)
    idx: dict[str, int] = {}
    hilang = []
    for key, awalan in (*KOLOM_TAHAP2.items(), *KOLOM_TAHAP2_TAMBAHAN.items()):
        kandidat = posisi.get(awalan, [])
        ke = dipakai[awalan]
        if ke < len(kandidat):
            idx[key] = kandidat[ke]
            dipakai[awalan] = ke + 1
        elif key in KOLOM_TAHAP2 and key not in KOLOM_TAHAP2_OPSIONAL:
            hilang.append(f"{key} (judul '{awalan}')")
    if hilang:
        raise ValueError(
            f"Judul kolom sheet tahap 2 tidak sesuai. Hilang: {hilang}. Judul yang terbaca: "
            f"{[j for j in judul if j][:60]}. Sesuaikan KOLOM_TAHAP2 di inti/tahap2_loader.py "
            "kalau judul sheet memang berubah.")
    return idx


def _baca_mentah_tahap2(path: Path) -> list[list]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            per_nama = {w.title.strip().lower(): w for w in wb.worksheets}
            ws = next((per_nama[n] for n in NAMA_SHEET_TAHAP2 if n in per_nama), wb.worksheets[0])
            return [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [list(r) for r in csv.reader(f)]


def _v_dari_sheet(sel: dict, kodepos_cadangan: str) -> tuple[dict, dict, dict, list[str]]:
    """Satu baris sheet -> (v FORMAT STANDAR, cek, info, catatan).
    `catatan` = nilai yang BUKAN salinan langsung sheet (default / koreksi),
    semuanya masuk kolom review_disarankan audit."""
    catatan: list[str] = []
    info = {k[len("info_"):]: sel.get(k, "") for k in KOLOM_TAHAP2 if k.startswith("info_")}
    cek = {k: sel.get(k, "") for k in KOLOM_TAHAP2 if k.startswith("cek_")}

    v: dict[str, str] = {}
    # 1. Nilai apa adanya dari sheet (teks).
    v["nama"] = v["nama_komersial"] = sel.get("nama_komersial", "")
    v["idsubsls"] = re.sub(r"\D", "", sel.get("idsubsls", ""))
    for key in ("pengusaha", "nik_pengusaha", "keg_utama", "produk", "jalan_domisili",
                "nib_nomor", "input_produksi", "proses_produksi"):
        v[key] = sel.get(key, "")

    # 2. Angka & uang.
    for key in KEY_RUPIAH:
        v[key] = rupiah_ke_angka(sel.get(key, ""))
    for key in KEY_BULAT:
        mentah = sel.get(key, "")
        v[key] = re.sub(r"\D", "", mentah) if mentah else ""
    for key in ("latitude", "longitude"):
        v[key] = desimal_ke_titik(sel.get(key, ""))
    v["kbli"] = re.sub(r"\D", "", sel.get("kbli", ""))
    v["judul_kbli"] = sel.get("info_judul_kbli", "")   # dipakai melengkapi 13a < 15 karakter
    v["pendapatan_online"] = persen_ke_bulat(sel.get("pendapatan_online", ""))
    if v["pendapatan_online"] and _beda_angka(sel.get("pendapatan_online", ""), v["pendapatan_online"]):
        catatan.append(f"27d '{sel.get('pendapatan_online')}' dibulatkan -> {v['pendapatan_online']}")

    hp = normalkan_hp(sel.get("hp", ""))
    if hp_valid(hp) and hp != " ".join(str(sel.get("hp", "")).split()):
        catatan.append(f"no WA '{sel.get('hp')}' -> '{hp}' (nol di depan dikembalikan)")
    elif not hp_valid(hp) and TAHAP2_HP_TIDAK_VALID_JADI:
        catatan.append(f"no WA '{sel.get('hp', '')}' {'kosong' if not hp else 'tidak valid'} -> "
                       f"'{TAHAP2_HP_TIDAK_VALID_JADI}' (tidak ada/tidak bersedia)")
        hp = TAHAP2_HP_TIDAK_VALID_JADI
    v["hp"] = hp

    # 3. Kode angka -> teks opsi form.
    for key in KEY_BERKODE:
        if key in sel:
            v[key] = opsi_dari_kode(key, sel[key])

    # 4. 16b1-b6 dari SATU kolom (lihat rencana_16b). Kolom per rincian menang.
    rencana, ket_16b = rencana_16b(sel.get("internet_semua", ""))
    if rencana is None:
        cek["masalah_16b"] = ket_16b
    else:
        for key, nilai in rencana.items():
            if not v.get(key):
                v[key] = nilai
    if ket_16b and rencana is not None and v.get("internet", "").startswith("1"):
        catatan.append(ket_16b)

    # 5. 13b1/b2/b3 dari golongan KBLI (kolom sheet menang kalau ada).
    dari_kbli = rencana_13b(v["kbli"])
    for key, nilai in dari_kbli.items():
        if not v.get(key):
            v[key] = nilai
    if any(not sel.get(k) for k in dari_kbli):
        catatan.append(f"13b1/b2/b3 diturunkan dari golongan KBLI {v['kbli'][:2]}: "
                       + "/".join(dari_kbli[k][0] for k in ("produk_sendiri", "layanan_mamin", "keg_penjualan")))

    # 5a. NIK tidak valid -> kode "lainnya" (TAHAP2_NIK_TIDAK_VALID_JADI).
    if v["nik_pengusaha"] and not nik_valid(v["nik_pengusaha"]) and TAHAP2_NIK_TIDAK_VALID_JADI:
        catatan.append(f"12d NIK '{v['nik_pengusaha']}' tidak valid (bukan 16 digit) -> "
                       f"'{TAHAP2_NIK_TIDAK_VALID_JADI}'")
        v["nik_pengusaha"] = TAHAP2_NIK_TIDAK_VALID_JADI

    # 5b. 13d/13e (industri: 13b1 Ya & 13b2 Tidak) dari judul KBLI.
    if (TAHAP2_13DE_DARI_KBLI and v["produk_sendiri"].startswith("1") and v["layanan_mamin"].startswith("2")
            and not (v["input_produksi"] and v["proses_produksi"])):
        inp, proses = isian_13de_dari_kbli(v.get("judul_kbli", ""), v.get("keg_utama", ""))
        if inp and proses:
            v["input_produksi"] = v["input_produksi"] or inp
            v["proses_produksi"] = v["proses_produksi"] or proses
            catatan.append(f"13d/13e diisi dari judul KBLI: '{v['input_produksi']}' / '{v['proses_produksi']}'")

    # 5c. KBLI non-perdagangan tidak punya 26c di form -> dijumlahkan ke 26b.
    if (TAHAP2_26C_KE_26B and kbli_tanpa_26c(v["kbli"]) and v["biaya_pembelian"].isdigit()
            and int(v["biaya_pembelian"]) > 0 and (v["biaya_produksi"] or "0").isdigit()):
        lama_b, lama_c = int(v["biaya_produksi"] or 0), int(v["biaya_pembelian"])
        v["biaya_produksi"], v["biaya_pembelian"] = str(lama_b + lama_c), "0"
        catatan.append(f"KBLI {v['kbli']} tanpa 26c di form: 26c {lama_c:,} dijumlahkan ke 26b "
                       f"({lama_b:,} -> {lama_b + lama_c:,})")

    # 5d. Pekerja per jenis kelamin mengikuti PEMILIK (lihat TAHAP2_PEKERJA_IKUT_JK_PEMILIK).
    if TAHAP2_PEKERJA_IKUT_JK_PEMILIK and all(v[k].isdigit() for k in KEY_PEKERJA) and v.get("jk", "")[:1] in "12":
        l, p, d, td = (int(v[k]) for k in KEY_PEKERJA)
        total, laki = d + td, v["jk"].startswith("1")
        salah_jk = total == 1 and (l, p) == ((0, 1) if laki else (1, 0))
        if total > 0 and (l + p != total or salah_jk):
            v["tk_laki"], v["tk_pr"] = (str(total), "0") if laki else ("0", str(total))
            catatan.append(f"24 laki/perempuan {l}/{p} -> {v['tk_laki']}/{v['tk_pr']} (ikut jenis kelamin "
                           f"pemilik; total = dibayar {d} + tidak dibayar {td})")

    # 5e. Indikator ekonomi yang selnya kosong = tidak ada nilainya = NOL.
    #     Kuesioner kertas mengosongkan sel yang nilainya nol; tanpa ini baris itu
    #     ter-skip WAJIB_KOSONG sebelum dokumen dibuat (2026-09-23: 111 dari 499
    #     baris rentang 2-500, 78 di antaranya cuma kolom 27b).
    if TAHAP2_UANG_KOSONG_JADI_NOL:
        nol = [k for k in (*KEY_26, *KEY_27, *KEY_28) if not v.get(k)]
        for key in nol:
            v[key] = "0"
        if nol:
            catatan.append(f"indikator ekonomi kosong dianggap 0: {', '.join(nol)}")

    # 5f. Form menolak pekerja DIBAYAR > 0 sementara 26a = 0 (validasi "gaji":
    #     26a/24a2 harus > Rp50.000). Ketetapan user: isi 26a TAHAP2_GAJI_JIKA_DIBAYAR.
    if (TAHAP2_GAJI_JIKA_DIBAYAR and (v.get("tk_dibayar") or "0").isdigit()
            and int(v.get("tk_dibayar") or 0) > 0 and int(v.get("gaji") or 0) == 0):
        v["gaji"] = str(TAHAP2_GAJI_JIKA_DIBAYAR)
        catatan.append(f"26a diisi {TAHAP2_GAJI_JIKA_DIBAYAR:,} krn ada {v['tk_dibayar']} pekerja dibayar "
                       f"(form menolak 26a = 0)")

    # 6. Default utk rincian yang tidak ditanyakan di kuesioner kertas.
    for key, bawaan in TAHAP2_DEFAULT.items():
        if not v.get(key):
            v[key] = bawaan
            if key not in ("ubah_sls", "is_new", "ada_bang_usaha", "keberadaan_usaha", "kode_bang",
                           "pilih_umkm_sls", "nama_info_list", "nomor_domisili"):
                catatan.append(f"{key} default '{bawaan}' (tidak ada di kuesioner tahap 2)")

    # 7. Kodepos & akun PPL.
    v["kodepos"] = kodepos_untuk(v["idsubsls"], sel.get("kodepos", ""), kodepos_cadangan)
    if v["kodepos"] and not sel.get("kodepos"):
        catatan.append(f"kodepos {v['kodepos']} dari daftar wilayah (tidak ada kolomnya di sheet)")
    # Identitas PPL sheet. Email dipakai kalau sheet punya kolomnya; kalau tidak,
    # nama PPL dinormalkan — nilainya hanya jadi bahan `kunci` & kolom audit,
    # BUKAN akun login (itu --akun-tunggal / kolom akun_ppl di mode --per-baris).
    v["akun_ppl"] = (sel.get("akun_ppl") or info.get("nama_ppl") or "").strip().lower()

    # 8. Kolom yang memang tidak dipakai jalur skrip.
    v.setdefault("no_bang", "")          # aturan keselamatan #3 — tidak pernah diketik
    v.setdefault("alamat_usaha_view", "")
    v.setdefault("pilih_prov", "")
    for key in ("pilih_kab", "pilih_kec", "pilih_desa", "pilih_sls", "pilih_subsls"):
        v.setdefault(key, "")
    return v, cek, info, catatan


def load_tahap2(path: str | Path, kodepos: str = "") -> list[Tahap2Row]:
    """Baca sheet tahap 2 -> [Tahap2Row] siap dipakai periksa_semua_tahap2()
    & fill_blok2_gabungan(). `kodepos` = cadangan terakhir (CLI --kodepos)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File sumber tidak ditemukan: {path}")
    mentah = _baca_mentah_tahap2(path)
    if not mentah:
        raise ValueError(f"{path.name} kosong.")
    idx = _indeks_tahap2([_sel(j) for j in mentah[0]])
    out: list[Tahap2Row] = []
    for nomor, baris in enumerate(mentah[1:], start=2):
        if not any(_sel(x) for x in baris):
            continue
        sel = {k: (_sel(baris[i]) if i < len(baris) else "") for k, i in idx.items()}
        v, cek, info, catatan = _v_dari_sheet(sel, kodepos)
        row = Tahap2Row(nomor, v, cek=cek, info=info, murni=False)
        row.koreksi.extend(catatan)
        # Wilayah baris: dipakai lengkapi_alamat() kalau Nama Jalan < 10 huruf.
        # Nama kec/desa diambil dari kolom informasi "3"/"4" ("GEROKGAK 510801").
        row.wilayah = _wilayah_dari_info(info)
        out.append(row)
    beri_pembeda_ganda(out)
    return out


def _wilayah_dari_info(info: dict) -> dict:
    """Kolom "3" = "GEROKGAK 510801", kolom "4" = "PATAS 0010" -> nama kec &
    desa (angka di belakang dibuang). Dipakai HANYA utk melengkapi Nama Jalan
    yang kurang dari 10 huruf; kode wilayah tetap dari kolom idsubsls."""
    def _nama(teks: str) -> str:
        return " ".join(re.sub(r"[\d.\-]+\s*$", "", str(teks or "")).split()).upper()
    wil = {}
    if _nama(info.get("kec", "")):
        wil["kecamatan"] = _nama(info["kec"])
    if _nama(info.get("desa", "")):
        wil["desa"] = _nama(info["desa"])
    return wil


# ---------------------------------------------------------------------------
# Pemeriksaan khas tahap 2 (di ATAS periksa_semua format standar)
# ---------------------------------------------------------------------------

def periksa_total(row: Tahap2Row, tanda: list[str] | None = None) -> list[tuple[str, str]]:
    """Kolom TOTAL sheet vs jumlah rinciannya. Total di form dihitung
    otomatis, jadi kolom ini tidak dikirim — tapi selisihnya berarti salah
    satu angka salah ketik, dan itu harus ketahuan SEBELUM dokumen dibuat.
    Kolom total yang kosong tidak diperiksa (bukan semua sheet mengisinya).

    Total = 0 padahal rinciannya > 0 dianggap kolom yang TIDAK DIISI, bukan
    selisih: file contoh user (2026-09-22) berisi "Rp26" = "Rp0" di SEMUA
    baris sementara 26a-26e terisi — salah ketik rincian tidak menghasilkan
    total persis nol. Kasus itu masuk `tanda` (review), tidak men-skip; total
    bukan nol yang tidak cocok tetap TOTAL_TIDAK_COCOK."""
    masalah = []
    for key_cek, key_rincian, nama in CEK_TOTAL:
        mentah = row.cek.get(key_cek, "")
        if not mentah or mentah in ("-", "–"):
            continue
        tulis = rupiah_ke_angka(mentah) if key_cek not in ("cek_tk_gender", "cek_tk_bayar") \
            else re.sub(r"\D", "", mentah)
        if not tulis:
            if TAHAP2_TOTAL_BEDA == "rincian":
                # Mis. "########" (sel Excel terlalu sempit): total memang tidak dikirim.
                if tanda is not None:
                    tanda.append(f"kolom total '{mentah}' ({nama}) tidak terbaca — dipakai rinciannya")
            else:
                masalah.append(("TOTAL_TIDAK_TERBACA", f"kolom total '{mentah}' ({nama}) tidak terbaca sbg angka"))
            continue
        if any(not row[k] for k in key_rincian):
            continue   # rincian kosong sudah dilaporkan periksa_baris
        jumlah = sum(int(row[k]) for k in key_rincian)
        if int(tulis) == 0 and jumlah > 0:
            if tanda is not None:
                tanda.append(f"kolom total {nama} di sheet = 0 padahal rinciannya {jumlah:,} — dianggap "
                             "tidak diisi (total dihitung form)")
            continue
        if int(tulis) != jumlah and TAHAP2_TOTAL_BEDA == "rincian":
            if tanda is not None:
                tanda.append(f"kolom total {nama} di sheet = {int(tulis):,}, jumlah rincian {jumlah:,} — "
                             "dipakai rinciannya (total dihitung form)")
            continue
        if int(tulis) != jumlah:
            masalah.append(("TOTAL_TIDAK_COCOK",
                            f"kolom total {nama} di sheet = {int(tulis):,} tapi jumlah rinciannya "
                            f"{jumlah:,} — perbaiki di Excel (angka mana yang benar bukan urusan skrip)"))
    return masalah


def periksa_semua_tahap2(rows: list[Tahap2Row], tahun_berjalan: int | None = None,
                         mode_satu_subsls: bool = False, cek_total: bool = True,
                         izinkan_tanpa_koordinat: bool = False) -> dict[int, Pemeriksaan]:
    """periksa_semua() format standar + pemeriksaan khas tahap 2.
    `cek_total=False` mematikan pembandingan kolom total (dipakai kalau
    sheet-nya belum mengisi kolom itu dgn benar). `izinkan_tanpa_koordinat`
    lihat gabungan_loader.periksa_baris."""
    hasil = periksa_semua(rows, tahun_berjalan, mode_satu_subsls, izinkan_tanpa_koordinat)
    for row in rows:
        h = hasil[row.baris]
        if cek_total:
            h.masalah.extend(periksa_total(row, h.tanda))
        # 13b1 = Ya -> form merender 13d & 13e, yang tidak ada di kuesioner
        # tahap 2. periksa_baris sudah menandainya WAJIB_KOSONG; pesan di
        # bawah menjelaskan asalnya supaya tidak dikira salah isi sheet.
        if row.cek.get("masalah_16b") and row["internet"].startswith("1"):
            # Di DEPAN: 16b yang kosong juga memicu WAJIB_KOSONG/16B_TANPA_YA — status baris
            # harus menunjuk penyebabnya (isi kolom 16b1-b6), bukan akibatnya.
            h.masalah.insert(0, ("16B_TIDAK_JELAS", row.cek["masalah_16b"]))
        if (row["produk_sendiri"].startswith("1") and row["layanan_mamin"].startswith("2")
                and not (row["input_produksi"] and row["proses_produksi"])):
            h.masalah.append(("13DE_TIDAK_ADA_DI_TAHAP2",
                              f"KBLI {row['kbli']} (golongan {row['kbli'][:2]}) -> 13b1 = Ya, sehingga form "
                              "mewajibkan 13d & 13e. Tambahkan kolom '13d' & '13e' di sheet, atau isi "
                              "dokumen ini manual."))
        if not row["kodepos"]:
            h.masalah.append(("KODEPOS_TIDAK_DIKETAHUI",
                              f"kodepos desa {row.idsubsls[:10]} tidak ada di KODEPOS_BY_IDSUBSLS/"
                              "KODEPOS_BY_DESA — tambahkan di inti/config_lokal.py, beri kolom 'kodepos' "
                              "di sheet, atau pakai --kodepos"))
    return hasil
