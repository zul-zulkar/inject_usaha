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
import datetime
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from inti.config import (
    GALAT_13C_JADI, KBLI_DITOLAK_PAKAI_GENAI, KODE_KAB, KODEPOS_BY_DESA, KODEPOS_BY_IDSUBSLS, TAHAP2_13B_DARI_KBLI,
    TAHAP2_13DE_DARI_KBLI, TAHAP2_26C_KE_26B, TAHAP2_DEFAULT, TAHAP2_GAJI_JIKA_DIBAYAR,
    TAHAP2_HP_TIDAK_VALID_JADI, TAHAP2_ISI_VARIAN_BULANAN, TAHAP2_KOTAK_KOORDINAT,
    TAHAP2_PERBAIKI_AWALAN_IDSUBSLS, TAHAP2_16B_TANPA_YA_JADI_B6, TAHAP2_NAIKKAN_KE_MINIMAL,
    TAHAP2_UPAH_ADA_PEKERJA_JADI_DIBAYAR, MINIMAL_TOTAL_RUPIAH, MINIMAL_TOTAL_RUPIAH_BULANAN,
    TAHAP2_NIK_TIDAK_VALID_JADI, TAHAP2_PEKERJA_IKUT_JK_PEMILIK, TAHAP2_TOTAL_BEDA,
    TAHAP2_UANG_KOSONG_JADI_NOL, TAHAP2_16B_LIMA_NILAI_B6, TAHAP2_PEMBEDA_13F_UTK_GANDA,
    TAHAP2_PENJUALAN_NOL_JADI_MINIMAL, TAHAP2_TAHUN_OPERASI_KOSONG_JADI, TAHAP2_UMUR_KOSONG_JADI,
    TAHAP2_26B_NOL_AMBIL_DARI_26D, TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN, TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL,
    TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL, TAHAP2_16B_YA_TUNGGAL, TAHAP2_PEMBEDA_WILAYAH_UTK_KEMBAR,
    TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN, TAHAP2_PENGUSAHA_KOSONG_AWALAN,
    TAHAP2_TANDAI_KBLI_TIDAK_NYAMBUNG, TAHAP2_KOREKSI_BUMDES, KATA_UMUM_KBLI,
    TAHAP2_JALAN_KOSONG_DARI_WILAYAH, TAHAP2_13A_KOSONG_DARI_KBLI, TAHAP2_KOREKSI_BARIS, WILAYAH_BY_IDSUBSLS,
)
from inti.gabungan_loader import (
    KEY_16B, KEY_26, KEY_27, KEY_28, KEY_29, KEY_PEKERJA, MAKS_8B, OPSI_FORM, YA_TIDAK, GabunganRow, Pemeriksaan,
    _norm_judul, _sel, format_nama_usaha, hp_valid, judul_dari_opsi_kbli, koreksi_bumdes, kbli_26b_wajib_positif,
    kbli_kategori_ditolak, kbli_makan_minum, kbli_punya_30c, kbli_tanpa_26c,
    koordinat_kosong, koordinat_valid, lengkapi_alamat, nama_muat, nama_tampil, nik_valid, periksa_semua,
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


def _di_kotak(nilai: float, sumbu: str) -> bool:
    lat_min, lat_maks, lon_min, lon_maks = TAHAP2_KOTAK_KOORDINAT
    return lat_min <= nilai <= lat_maks if sumbu == "lat" else lon_min <= nilai <= lon_maks


def _pulihkan_satu(teks: str, sumbu: str) -> str:
    """Satu nilai koordinat rusak -> "-8.148438" / "" (tidak bisa dipulihkan).
    Urutan: angka biasa; bujur bertanda minus (Indonesia di bujur TIMUR);
    lalu angka yang titik desimalnya hilang ("-8.148.438" = -8148438, "-8155247,")
    -> desimal disisipkan setelah digit ke-1 (lintang) / ke-3 (bujur).
    Notasi ilmiah ("1,15E+09") digitnya sudah hilang -> tidak dipulihkan."""
    t = str(teks or "").strip().rstrip(",;").strip()
    if not t or "E" in t.upper():
        return ""
    try:
        nilai = float(desimal_ke_titik(t))
    except ValueError:
        nilai = None
    if nilai is not None:
        if _di_kotak(nilai, sumbu):
            return f"{nilai}"
        if sumbu == "lon" and _di_kotak(-nilai, sumbu):
            return f"{-nilai}"
    digit = re.sub(r"\D", "", t)
    for lebar in ((1, 2) if sumbu == "lat" else (3,)):
        if len(digit) <= lebar:
            continue
        nilai = float(f"{digit[:lebar]}.{digit[lebar:]}")
        nilai = -nilai if sumbu == "lat" else nilai     # sisi selatan khatulistiwa
        if _di_kotak(nilai, sumbu):
            return f"{nilai}"
    return ""


def pulihkan_koordinat(lat_mentah, lon_mentah) -> tuple[str, str, str]:
    """(lat, lon) sheet -> (lat, lon, catatan). Nilai yang sudah benar kembali
    apa adanya (catatan ""). Yang rusak dipulihkan HANYA kalau hasilnya jatuh di
    TAHAP2_KOTAK_KOORDINAT; kalau tidak, nilai lama dikembalikan (baris tetap
    jadi draft tanpa koordinat, tidak ditebak)."""
    lat, lon = desimal_ke_titik(lat_mentah), desimal_ke_titik(lon_mentah)
    if TAHAP2_KOTAK_KOORDINAT is None or koordinat_valid(lat, lon) or koordinat_kosong(lat_mentah):
        return lat, lon, ""
    a, b = str(lat_mentah or "").strip(), str(lon_mentah or "").strip()
    if koordinat_kosong(lon_mentah):
        # Lat & long ditulis di SATU sel: "-8.142753,115.059837" / "-8,14, 115,06".
        dua = [x for x in re.split(r"\s*[,;]\s+|\s*;\s*", a) if x]
        if len(dua) != 2 and a.count(",") == 1 and "." in a:
            dua = a.split(",")
        if len(dua) != 2:
            return lat, lon, ""
        a, b = dua
    p_lat, p_lon = _pulihkan_satu(a, "lat"), _pulihkan_satu(b, "lon")
    if not (p_lat and p_lon):
        return lat, lon, ""
    return p_lat, p_lon, (f"koordinat sheet '{lat_mentah}' / '{lon_mentah or ''}' (format rusak Excel) "
                          f"-> {p_lat}, {p_lon}")


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
        if tunggal.startswith("2") or not TAHAP2_16B_YA_TUNGGAL:
            return {k: tunggal for k in KEY_16B}, f"16b1-b6 diisi '{tunggal}' dari satu kolom '16b1-b6'"
        # "Ya" satu kolom TIDAK berarti keenam rincian Ya (ketetapan user 2026-09-24):
        # cuma menerima pesanan, membeli bahan baku & promosi. Lihat TAHAP2_16B_YA_TUNGGAL.
        hasil = {k: ("1. Ya" if k in TAHAP2_16B_YA_TUNGGAL else "2. Tidak") for k in KEY_16B}
        ya = [f"b{KEY_16B.index(k) + 1}" for k in KEY_16B if k in TAHAP2_16B_YA_TUNGGAL]
        return hasil, f"16b1-b6 '{t}' (satu kolom) -> Ya hanya utk {','.join(ya)}, sisanya Tidak"
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

# Kata umum di DEPAN nama usaha yang boleh dibuang kalau nama dokumen > 50
# karakter (Tahap2Row._nama_ringkas) — nama pemilik & produknya tetap.
KATA_UMUM_NAMA = frozenset({"PEDAGANG", "PENJUAL", "JUAL", "MENJUAL", "ECERAN", "USAHA", "DAGANG",
                            "PERDAGANGAN", "JASA"})


@dataclass
class Tahap2Row(GabunganRow):
    """GabunganRow + kolom khas tahap 2 yang TIDAK dikirim ke form."""
    cek: dict = field(default_factory=dict)   # {key cek: angka} utk periksa_total
    info: dict = field(default_factory=dict)  # kolom informasi (uraian, nama PPL, dst.)
    # 13f pembeda usaha pecahan bernama sama (lihat beri_pembeda_ganda). Kosong = tidak ada.
    pembeda: str = ""
    # Nama dokumen & 8b FINAL dari TAHAP2_KOREKSI_BARIS (ketetapan user per baris).
    # Menang atas semua aturan penamaan; kunci tetap dari 8b mentah.
    nama_tetap: str = ""

    def _nama_dgn_pembeda(self, nama: str) -> str:
        """"<8b> (<12a>)"; usaha pecahan bernama sama: "<8b> <13f> (<12a>)". Yang
        terakhir > MAKS_8B -> "<13f> (<12a>)" (8b generik "warung bu" dilepas, 13f
        yang membedakan). Masih kepanjangan -> 8B_TERLALU_PANJANG, BUKAN cadangan
        nama_muat tanpa (<12a>): tanpa pemilik, 13f generik ("air galon") bentrok
        dgn usaha pecahan pemilik lain."""
        if self.nama_tetap:
            return self.nama_tetap
        if not self.pembeda:
            hasil = nama_muat(nama_tampil(nama, self.akhiran_badan), self["pengusaha"])
            if len(hasil) > MAKS_8B:
                # nama_muat membuang kurungnya tapi nama pemilik yang sudah tertulis
                # di 8b tetap ikut -> ringkas bentuk "<usaha> (<12a>)"-nya.
                hasil = self._nama_ringkas(format_nama_usaha(nama_tampil(nama, self.akhiran_badan),
                                                             self["pengusaha"])) or hasil
            return hasil
        hasil = format_nama_usaha(nama_tampil(f"{nama} {self.pembeda}", self.akhiran_badan), self["pengusaha"])
        if len(hasil) > MAKS_8B:
            hasil = format_nama_usaha(self.pembeda, self["pengusaha"])
        if len(hasil) > MAKS_8B:
            hasil = self._nama_ringkas(hasil) or hasil
        return hasil

    def _nama_ringkas(self, hasil: str) -> str:
        """Cadangan terakhir (2026-09-24) kalau "<usaha> (<12a>)" > MAKS_8B: bagian
        USAHA diringkas, nama pemilik tetap (pembeda antar-responden). 8b sheet
        sendiri wajar ("TOKO CONTOH") — yang kepanjangan susunan skrip / 8b yang
        sudah memuat pemilik ("Pedagang eceran sparepart mobil (I Made Contoh
        Wirawan Putra)" 53; 8 baris dulu ter-skip 8B_TERLALU_PANJANG). Kata umum di depan
        (KATA_UMUM_NAMA: "Pedagang eceran", "Jual") dibuang dulu, lalu kata di
        belakang. "" kalau tidak bisa (baris tetap 8B_TERLALU_PANJANG)."""
        pemilik = " ".join(re.sub(r"[()]", " ", self["pengusaha"]).split())
        akhir = f" ({pemilik})"
        if not pemilik or not hasil.endswith(akhir):
            return ""
        kata = hasil[: -len(akhir)].split()
        while len(kata) > 1 and kata[0].upper().strip(".,") in KATA_UMUM_NAMA:
            kata.pop(0)
        while len(kata) > 1 and len(" ".join(kata)) + len(akhir) > MAKS_8B:
            kata.pop()
        usaha = " ".join(kata).strip(" ,;:-/&")
        if len(usaha) + len(akhir) > MAKS_8B or len(re.sub(r"[^A-Za-z]", "", usaha)) < 4:
            return ""
        return usaha + akhir

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
    def b13_dari_kbli(self) -> bool:
        return self.info.get("13b_dari_kbli") == "1"

    @property
    def pindah_26c_ke_26b(self) -> bool:
        return TAHAP2_26C_KE_26B

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
    # Putaran 1 (aturan 2026-09-23, JANGAN diubah: pembedanya ikut `kunci`, jadi
    # mengubah hasil putaran ini memutus audit baris yang sudah punya dokumen).
    grup: dict[str, list[Tahap2Row]] = defaultdict(list)
    for r in rows:
        grup[r._kunci_dasar()].append(r)
    for anggota in grup.values():
        _beri_pembeda(anggota, "produk", "13f")
    # Putaran 2 (2026-09-24) — HANYA menambah pembeda utk baris yang putaran 1
    # tidak memberinya (baris itu dulu ter-skip, jadi belum punya audit):
    #  a. 8b+12a sama tapi idsubsls BEDA (baris 498/499 "WR CONTOH (MD CONTOH)"):
    #     mode satu subsls memasukkan semuanya ke SATU list -> nama dokumen bentrok.
    #  b. 13f juga sama, 13a beda (baris 441/442 "penjualan alat tulis").
    grup = defaultdict(list)
    for r in rows:
        grup[f"{r.akun_ppl}|{r.nama.upper()}|{r['pengusaha'].upper()}"].append(r)
    for anggota in grup.values():
        _beri_pembeda(anggota, "produk", "13f", hanya_kosong=True)
        _beri_pembeda(anggota, "keg_utama", "13a", hanya_kosong=True)
    # Putaran 3 (2026-09-24): nama, 13f & 13a sama persis -> desa/kecamatan/nomor.
    bedakan_nama_kembar(rows)


def _beri_pembeda(anggota: list[Tahap2Row], key: str, rincian: str, hanya_kosong: bool = False) -> None:
    """Beri `pembeda` = isian `key` pada anggota grup yang isiannya UNIK di grup.
    hanya_kosong: anggota yang sudah berpembeda tidak diubah, tapi isiannya tetap
    dihitung (supaya pembeda baru tidak kembar dgn yang sudah ada)."""
    if len(anggota) < 2:
        return
    isian = [" ".join(r[key].split()) for r in anggota]
    jumlah: dict[str, int] = defaultdict(int)
    for p in isian:
        jumlah[p.upper()] += 1
    terpakai = {r.pembeda.upper() for r in anggota if r.pembeda}
    daftar = [r.baris for r in anggota]
    for r, p in zip(anggota, isian):
        if hanya_kosong and (r.pembeda or p.upper() in terpakai):
            continue
        if p and jumlah[p.upper()] == 1:
            r.pembeda = p
            r.koreksi.append(f"usaha pecahan bernama sama (baris {daftar}) -> nama dibedakan {rincian} "
                             f"'{p}': {r.nama_dokumen}")


def _nama_wilayah(row: Tahap2Row, bagian: str) -> str:
    """Nama desa/kecamatan baris ini dari kolom informasi ("4"/"3"), "" kalau kosong."""
    return _wilayah_dari_info(row.info).get(bagian, "")


def bedakan_nama_kembar(rows: list[Tahap2Row]) -> None:
    """Putaran 3 (ketetapan user 2026-09-24, TAHAP2_PEMBEDA_WILAYAH_UTK_KEMBAR):
    nama dokumen yang MASIH kembar persis sesudah putaran 13f & 13a dibedakan
    bertahap — nama DESA, lalu KECAMATAN, lalu PENOMORAN. Kasusnya baris
    1214/1223 ("toko ni luh sri ameni" gas LPG) & 1362/1363 (sabun/sampo Yuda):
    nama, 13f DAN 13a sama persis, cuma angka uangnya yang beda, jadi kedua
    putaran sebelumnya tidak punya bahan pembeda & barisnya cuma ter-skip.

    Wilayah dicoba lebih dulu karena lebih informatif drpd angka, tapi hanya
    kalau nilainya MEMBEDAKAN SEMUA anggota — desa yang cuma memisah sebagian
    menyisakan kembar, jadi kasus itu langsung jatuh ke penomoran.

    Sama dgn putaran 2, yang diubah HANYA baris yang masih bentrok — baris lain
    kuncinya tetap, jadi audit dokumen yang sudah ada tidak terputus.

    Syaratnya baris-baris itu memang USAHA BERBEDA ("kalau memang dua usaha
    berbeda, bedakan namanya"): isian yang dikirim harus ada yang beda. Kalau ada
    dua baris yang isinya SAMA PERSIS, itu duplikat entri, bukan dua usaha —
    seluruh kelompok dibiarkan di-skip BARIS_GANDA spt semula, karena menomorinya
    berarti mengirim dua dokumen sensus utk satu usaha yang sama & itu tidak bisa
    dibatalkan."""
    if not TAHAP2_PEMBEDA_WILAYAH_UTK_KEMBAR:
        return
    kembar: dict[str, list[Tahap2Row]] = defaultdict(list)
    for r in rows:
        kembar[r.nama_dokumen.upper()].append(r)
    for anggota in kembar.values():
        if len(anggota) < 2:
            continue
        sidik = [tuple(sorted(r.v.items())) for r in anggota]
        if len(set(sidik)) != len(anggota):
            continue    # ada baris yang isinya sama persis -> duplikat, tidak ditebak
        anggota.sort(key=lambda r: r.baris)
        daftar = [r.baris for r in anggota]
        for bagian in ("desa", "kecamatan"):
            nilai = [_nama_wilayah(r, bagian) for r in anggota]
            if all(nilai) and len(set(nilai)) == len(anggota):
                for r, n in zip(anggota, nilai):
                    r.pembeda = f"{r.pembeda} {n}".strip()
                    r.koreksi.append(f"nama kembar persis (baris {daftar}) -> nama dibedakan {bagian} "
                                     f"'{n}': {r.nama_dokumen}")
                break
        else:
            # Wilayahnya sama juga (mis. satu subsls) -> nomor urut. Baris PERTAMA
            # ikut diberi nomor supaya tidak ada yang bernama ambigu "tanpa nomor".
            for ke, r in enumerate(anggota, start=1):
                r.pembeda = f"{r.pembeda} {ke}".strip()
                r.koreksi.append(f"nama kembar persis (baris {daftar}) & wilayahnya sama -> "
                                 f"nama dibedakan penomoran '{ke}': {r.nama_dokumen}")


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
    # Awalan kabupaten salah ketik ("5100090007000901", baris 1719-1726 data
    # 2026-09-24): kode kecamatannya cocok dgn kolom "Sumber/Kec." -> awalan KODE_KAB.
    kec = re.sub(r"\D", "", sel.get("info_sumber_kec", ""))
    if (TAHAP2_PERBAIKI_AWALAN_IDSUBSLS and len(v["idsubsls"]) == 16 and len(kec) == 3
            and not v["idsubsls"].startswith(KODE_KAB) and v["idsubsls"][:2] == KODE_KAB[:2]
            and v["idsubsls"][4:7] == kec):
        lama = v["idsubsls"]
        v["idsubsls"] = KODE_KAB + lama[4:]
        catatan.append(f"idsubsls '{lama}' -> '{v['idsubsls']}' (awalan kabupaten salah ketik; "
                       f"kecamatan {kec} cocok dgn kolom Sumber/Kec.)")
    for key in ("pengusaha", "nik_pengusaha", "keg_utama", "produk", "jalan_domisili",
                "nib_nomor", "input_produksi", "proses_produksi"):
        v[key] = sel.get(key, "")

    # 2. Angka & uang.
    for key in KEY_RUPIAH:
        v[key] = rupiah_ke_angka(sel.get(key, ""))
    for key in KEY_BULAT:
        mentah = sel.get(key, "")
        v[key] = re.sub(r"\D", "", mentah) if mentah else ""
    # 2a. Satu rincian 24 kosong tapi kolom TOTAL-nya terisi -> selisihnya (baris 1383
    #     data 2026-09-24: 24.Total 2, dibayar 2, tidak dibayar kosong -> 0). Hitungan,
    #     bukan tebakan; total lebih kecil dari rincian lainnya -> tetap kosong.
    for key_cek, pasangan in (("cek_tk_gender", ("tk_laki", "tk_pr")),
                              ("cek_tk_bayar", ("tk_dibayar", "tk_tdk_dibayar"))):
        total = re.sub(r"\D", "", cek.get(key_cek, "") or "")
        for kosong, isi in (pasangan, pasangan[::-1]):
            if not v[kosong] and v[isi] and total and int(total) >= int(v[isi]):
                v[kosong] = str(int(total) - int(v[isi]))
                catatan.append(f"{kosong} kosong -> {v[kosong]} (total {total} - {isi} {v[isi]})")
    v["latitude"], v["longitude"], ket = pulihkan_koordinat(sel.get("latitude", ""), sel.get("longitude", ""))
    if ket:
        catatan.append(ket)
    v["kbli"] = re.sub(r"\D", "", sel.get("kbli", ""))
    v["judul_kbli"] = sel.get("info_judul_kbli", "")   # dipakai melengkapi 13a < 15 karakter
    # KBLI P/U ditolak form -> 13g diisi rekomendasi GenAI saat pengisian (KBLI_DITOLAK_PAKAI_GENAI);
    # turunan yang bergantung KBLI (26c -> 26b) ditunda sampai KBLI sebenarnya terpilih.
    kbli_genai = KBLI_DITOLAK_PAKAI_GENAI and bool(kbli_kategori_ditolak(v["kbli"]))
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
    # 4a. 16a Ya tapi 16b tidak ada Ya -> b6 "Lainnya" Ya (TAHAP2_16B_TANPA_YA_JADI_B6).
    if (TAHAP2_16B_TANPA_YA_JADI_B6 and rencana and v.get("internet", "").startswith("1")
            and not any(v.get(k, "").startswith("1") for k in KEY_16B)):
        v[KEY_16B[-1]] = "1. Ya"
        catatan.append(f"16a Ya tapi 16b '{sel.get('internet_semua', '')}' tanpa Ya -> 16b6 Lainnya = Ya")
    # 4b. 27d: pesanan masuk lewat internet (16b1 Ya) tapi persentase pendapatan online
    # kosong/0 -> tidak konsisten. Ketetapan user 2026-09-24 (baris 1556-1559): isi
    # TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN. Nilai sheet yang > 0 TIDAK diubah.
    # Harus di DEPAN pengisian "indikator ekonomi kosong = 0" (bagian 5c): kalau
    # dibalik, 27d sudah jadi "0" & aturan ini tidak pernah kelihatan berlaku.
    if (TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN and v.get("internet", "").startswith("1")
            and v.get("internet_pesanan", "").startswith("1")
            and int(v.get("pendapatan_online") or 0) == 0):
        v["pendapatan_online"] = str(TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN)
        catatan.append(f"27d {'0' if sel.get('pendapatan_online') else 'kosong'} -> "
                       f"{TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN}% krn 16b1 (menerima pesanan) = Ya")

    # 5. 13b1/b2/b3 dari golongan KBLI (kolom sheet menang kalau ada).
    dari_kbli = rencana_13b(v["kbli"])
    for key, nilai in dari_kbli.items():
        if not v.get(key):
            v[key] = nilai
    if all(not sel.get(k) for k in dari_kbli):
        info["13b_dari_kbli"] = "1"
    if any(not sel.get(k) for k in dari_kbli):
        catatan.append(f"13b1/b2/b3 diturunkan dari golongan KBLI {v['kbli'][:2]}: "
                       + "/".join(dari_kbli[k][0] for k in ("produk_sendiri", "layanan_mamin", "keg_penjualan")))

    # 5a. NIK tidak valid -> kode "lainnya" (TAHAP2_NIK_TIDAK_VALID_JADI).
    if v["nik_pengusaha"] and not nik_valid(v["nik_pengusaha"]) and TAHAP2_NIK_TIDAK_VALID_JADI:
        catatan.append(f"12d NIK '{v['nik_pengusaha']}' tidak valid (bukan 16 digit) -> "
                       f"'{TAHAP2_NIK_TIDAK_VALID_JADI}'")
        v["nik_pengusaha"] = TAHAP2_NIK_TIDAK_VALID_JADI

    # 5a2. 12a nama pengusaha kosong / "-" -> nama cadangan (lihat pengusaha_cadangan).
    if " ".join(v.get("pengusaha", "").split()) in ("", "-", "\u2013"):
        pengganti, alasan = pengusaha_cadangan(v.get("nama", ""))
        if pengganti:
            v["pengusaha"] = pengganti
            catatan.append(alasan)

    # 5a3. 13a kegiatan utama kosong -> judul KBLI (TAHAP2_13A_KOSONG_DARI_KBLI).
    judul_13a = " ".join(judul_dari_opsi_kbli(v.get("judul_kbli", "")).split())
    if TAHAP2_13A_KOSONG_DARI_KBLI and not v["keg_utama"].strip() and judul_13a:
        v["keg_utama"] = judul_13a
        catatan.append(f"13a kosong -> judul KBLI '{judul_13a}' (ketetapan user)")

    # 5b. 13d/13e (industri: 13b1 Ya & 13b2 Tidak) dari judul KBLI.
    if (TAHAP2_13DE_DARI_KBLI and v["produk_sendiri"].startswith("1") and v["layanan_mamin"].startswith("2")
            and not (v["input_produksi"] and v["proses_produksi"])):
        inp, proses = isian_13de_dari_kbli(v.get("judul_kbli", ""), v.get("keg_utama", ""))
        if inp and proses:
            v["input_produksi"] = v["input_produksi"] or inp
            v["proses_produksi"] = v["proses_produksi"] or proses
            catatan.append(f"13d/13e diisi dari judul KBLI: '{v['input_produksi']}' / '{v['proses_produksi']}'")

    # 5c. KBLI non-perdagangan tidak punya 26c di form -> dijumlahkan ke 26b.
    if (TAHAP2_26C_KE_26B and not kbli_genai and kbli_tanpa_26c(v["kbli"]) and v["biaya_pembelian"].isdigit()
            and int(v["biaya_pembelian"]) > 0 and (v["biaya_produksi"] or "0").isdigit()):
        lama_b, lama_c = int(v["biaya_produksi"] or 0), int(v["biaya_pembelian"])
        v["biaya_produksi"], v["biaya_pembelian"] = str(lama_b + lama_c), "0"
        catatan.append(f"KBLI {v['kbli']} tanpa 26c di form: 26c {lama_c:,} dijumlahkan ke 26b "
                       f"({lama_b:,} -> {lama_b + lama_c:,})")

    # 5c2. Kolom 24 kosong SEMUA -> nilai minimal (TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL): 1 pekerja
    #      berjenis kelamin pemilik — pemilik ikut dihitung di 24 (cek 24c1 form) & tidak ada satu
    #      pun baris sheet ber-24 nol; dibayar hanya kalau 26a > 0 (24a2 = 0 -> 26a wajib 0).
    if (TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL and not any(v[k] for k in KEY_PEKERJA)
            and v.get("jk", "")[:1] in ("1", "2")):
        laki, dibayar = v["jk"].startswith("1"), int(v.get("gaji") or 0) > 0
        v["tk_laki"], v["tk_pr"] = ("1", "0") if laki else ("0", "1")
        v["tk_dibayar"], v["tk_tdk_dibayar"] = ("1", "0") if dibayar else ("0", "1")
        catatan.append(f"24 kosong semua -> 1 pekerja {'laki-laki' if laki else 'perempuan'} (ikut pemilik), "
                       f"{'dibayar (26a terisi)' if dibayar else 'tidak dibayar'} (nilai minimal)")

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
        # 27d (% pendapatan online) hanya ditanyakan kalau 16a Ya (ketetapan user 2026-09-24:
        # "blok ekonomi yang kosong isikan 0").
        if not v.get("pendapatan_online") and v.get("internet", "").startswith("1"):
            nol.append("pendapatan_online")
        for key in nol:
            v[key] = "0"
        if nol:
            catatan.append(f"indikator ekonomi kosong dianggap 0: {', '.join(nol)}")

    # 5e2. 26a > 0 tapi tidak ada pekerja dibayar -> semua pekerja jadi dibayar
    #      (TAHAP2_UPAH_ADA_PEKERJA_JADI_DIBAYAR; form: "Wajib terisi = 0, karena
    #      jumlah pekerja dibayar=0"). Total & jenis kelamin tidak berubah.
    if (TAHAP2_UPAH_ADA_PEKERJA_JADI_DIBAYAR and all(v.get(k, "").isdigit() for k in ("tk_dibayar", "tk_tdk_dibayar"))
            and int(v["tk_dibayar"]) == 0 and int(v["tk_tdk_dibayar"]) > 0 and int(v.get("gaji") or 0) > 0):
        catatan.append(f"26a {int(v['gaji']):,} terisi tapi 24a2 = 0 -> {v['tk_tdk_dibayar']} pekerja tidak "
                       f"dibayar dipindah ke dibayar (24a2 {v['tk_tdk_dibayar']}, 24b2 0)")
        v["tk_dibayar"], v["tk_tdk_dibayar"] = v["tk_tdk_dibayar"], "0"

    # 5f. Form menolak pekerja DIBAYAR > 0 sementara 26a = 0 (validasi "gaji":
    #     26a/24a2 harus > Rp50.000). Ketetapan user: isi 26a TAHAP2_GAJI_JIKA_DIBAYAR.
    if (TAHAP2_GAJI_JIKA_DIBAYAR and (v.get("tk_dibayar") or "0").isdigit()
            and int(v.get("tk_dibayar") or 0) > 0 and int(v.get("gaji") or 0) == 0):
        # PER pekerja: 100.000 rata utk 2+ pekerja jatuh <= Rp50.000/orang -> GALAT lagi.
        v["gaji"] = str(TAHAP2_GAJI_JIKA_DIBAYAR * int(v["tk_dibayar"]))
        catatan.append(f"26a diisi {int(v['gaji']):,} ({TAHAP2_GAJI_JIKA_DIBAYAR:,} x {v['tk_dibayar']} pekerja dibayar) "
                       f"(form menolak 26a = 0)")

    # 5g. Total 26f / 27c > 0 tapi < minimal form -> kekurangan ke pos terbesar
    #     (TAHAP2_NAIKKAN_KE_MINIMAL). Varian bulanan (tahun operasi = tahun ini) 10.000.
    #     Total 0 (semua pos kosong/nol) -> 26d / 27a = minimal (TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL,
    #     TAHAP2_PENJUALAN_NOL_JADI_MINIMAL; ketetapan user 2026-09-24).
    bulanan = (TAHAP2_ISI_VARIAN_BULANAN and v.get("tahun_operasi", "").isdigit()
               and int(v["tahun_operasi"]) == datetime.date.today().year)
    minimal = MINIMAL_TOTAL_RUPIAH_BULANAN if bulanan else MINIMAL_TOTAL_RUPIAH
    r = "30" if bulanan else "26"    # awalan nomor rincian pengeluaran di form
    for kelompok, nama, pos_nol, rincian_nol, saklar_nol in (
            (KEY_26, f"{r}f", "operasional", f"{r}d", TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL),
            (KEY_27, "31c" if bulanan else "27c", KEY_27[0], "31a" if bulanan else "27a",
             TAHAP2_PENJUALAN_NOL_JADI_MINIMAL)):
        if not all(v.get(k, "").isdigit() for k in kelompok):
            continue
        total = sum(int(v[k]) for k in kelompok)
        if total == 0 and saklar_nol:
            v[pos_nol] = str(minimal)
            catatan.append(f"{nama} 0 (semua pos kosong/nol) -> {rincian_nol} diisi minimal {minimal:,} (DINAIKKAN)")
        elif 0 < total < minimal and TAHAP2_NAIKKAN_KE_MINIMAL:
            terbesar = max(kelompok, key=lambda k: int(v[k]))
            v[terbesar] = str(int(v[terbesar]) + minimal - total)
            catatan.append(f"{nama} {total:,} < minimal {minimal:,} -> {terbesar} ditambah "
                           f"{minimal - total:,} (DINAIKKAN)")

    # 5h/5i. Pos pengeluaran yang WAJIB > 0 menurut KBLI tapi 0 di sheet -> diisi dari pos lain
    #        (dipindah, total 26f tetap; ketetapan user 2026-09-24). KBLI yang akan diganti
    #        GenAI dilewati — KBLI sebenarnya belum diketahui.
    nama_pos = {"biaya_produksi": f"{r}b", "operasional": f"{r}d", "non_operasional": f"{r}e"}

    def pindahkan(ke: str, dari: tuple[str, ...], alasan: str) -> None:
        asal = next((k for k in dari if int(v[k]) > 0), "")
        if asal:
            catatan.append(f"{alasan} -> {nama_pos[asal]} {int(v[asal]):,} dipindah ke "
                           f"{nama_pos.get(ke, r + 'c')}")
            v[ke], v[asal] = v[asal], "0"

    if not kbli_genai and all(v.get(k, "").isdigit() for k in KEY_26):
        # 5h. Usaha dagang varian bulanan: form mewajibkan 30c (pembelian barang dagangan) > 0.
        #     26b dulu, 26b 0 -> pos terbesar dari 26d/26e (baris 405/563/1076/1586).
        if (TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN and bulanan and kbli_punya_30c(v["kbli"])
                and int(v["biaya_pembelian"]) == 0):
            lain = sorted(("operasional", "non_operasional"), key=lambda k: -int(v[k]))
            pindahkan("biaya_pembelian", ("biaya_produksi", *lain), f"{r}c 0 (usaha dagang, varian bulanan)")
        # 5i. KBLI B-F / gol. 56: form mewajibkan 26b > 0 (baris 1675/1676/1730).
        if (TAHAP2_26B_NOL_AMBIL_DARI_26D and kbli_26b_wajib_positif(v["kbli"])
                and int(v["biaya_produksi"]) == 0):
            pindahkan("biaya_produksi", ("operasional", "non_operasional"),
                      f"{r}b 0 (KBLI {v['kbli']} wajib biaya produksi)")

    # 6. Default utk rincian yang tidak ditanyakan di kuesioner kertas.
    for key, bawaan in TAHAP2_DEFAULT.items():
        if not v.get(key):
            # 13c: default "4. Toko, ruko" PASTI ditolak form kalau usahanya
            # makan-minum ("Usaha Makan Minum, maka lokasi hanya bisa diisi kode
            # 5-11") — 8 GALAT di audit 22-23 Sep 2026, SEMUANYA KBLI gol. 56 yang
            # 13c-nya memang tidak ada di kuesioner kertas alias dari default ini.
            # Dipakai GALAT_13C_JADI: nilai yang sama dgn ketetapan user 2026-09-23
            # utk membetulkan GALAT 13c ("langsung ubah ke kode 5 saja"), hanya
            # dipasang di depan drpd menunggu dokumen terbuat lalu ber-GALAT.
            if key == "lokasi_usaha" and GALAT_13C_JADI and kbli_makan_minum(v.get("kbli", "")):
                v[key] = GALAT_13C_JADI
                catatan.append(f"13c default '{GALAT_13C_JADI}' (usaha makan-minum KBLI {v.get('kbli')}: "
                               f"form menolak kode 1-4; tidak ada di kuesioner tahap 2)")
                continue
            v[key] = bawaan
            if key not in ("ubah_sls", "is_new", "ada_bang_usaha", "keberadaan_usaha", "kode_bang",
                           "pilih_umkm_sls", "nama_info_list", "nomor_domisili"):
                catatan.append(f"{key} default '{bawaan}' (tidak ada di kuesioner tahap 2)")

    # 6a. BUMDES -> 11a kode 6 + 11d Ya + 29 pemerintah 100 (TAHAP2_KOREKSI_BUMDES).
    #     HARUS sesudah bagian 6: 11a/11d/29 tahap 2 datang dari TAHAP2_DEFAULT, jadi
    #     kalau dijalankan lebih dulu koreksinya langsung ditimpa default.
    if TAHAP2_KOREKSI_BUMDES and (ket_bumdes := koreksi_bumdes(v)):
        catatan.append(ket_bumdes)

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


def lengkapi_umur_tahun(sels: list[dict]) -> list[list[str]]:
    """12c umur & 25 tahun operasi yang KOSONG (sel mentah, diubah di tempat) ->
    catatan per baris. (1) Disalin dari usaha lain PEMILIK yang sama (PPL + idsubsls
    + 12a) kalau yang terisi sepakat satu nilai — usaha pecahan satu orang;
    (2) sisanya TAHAP2_UMUR_KOSONG_JADI / TAHAP2_TAHUN_OPERASI_KOSONG_JADI
    (ketetapan user 2026-09-24; "" = dibiarkan kosong -> WAJIB_KOSONG)."""
    def angka(teks: str) -> str:
        return re.sub(r"\D", "", teks or "")

    def pemilik(sel: dict) -> tuple:
        return ((sel.get("akun_ppl") or sel.get("info_nama_ppl") or "").strip().lower(),
                angka(sel.get("idsubsls", "")), " ".join(sel.get("pengusaha", "").upper().split()))

    grup: dict[tuple, list[int]] = defaultdict(list)
    for i, sel in enumerate(sels):
        if pemilik(sel)[2]:
            grup[pemilik(sel)].append(i)
    catatan: list[list[str]] = [[] for _ in sels]
    for key, nama, bawaan in (("umur", "12c umur", TAHAP2_UMUR_KOSONG_JADI),
                              ("tahun_operasi", "25 tahun operasi", TAHAP2_TAHUN_OPERASI_KOSONG_JADI)):
        # Nilai saudara diambil dari sheet ASLI dulu, supaya nilai pengganti yang
        # baru dipasang tidak ikut "disalin" ke baris pemilik yang sama.
        asli = [angka(sel.get(key, "")) for sel in sels]
        for i, sel in enumerate(sels):
            if asli[i]:
                continue
            nilai = {asli[j] for j in grup.get(pemilik(sel), []) if j != i} - {""}
            if len(nilai) == 1:
                (isi,) = nilai
                sel[key] = isi
                catatan[i].append(f"{nama} kosong -> {isi} (disalin dari usaha lain pemilik yang sama)")
            elif bawaan:
                sel[key] = bawaan
                catatan[i].append(f"{nama} kosong -> {bawaan} (nilai pengganti, tidak ada di sheet)"
                                  + (f"; usaha lain pemilik ini berbeda-beda: {sorted(nilai)}" if nilai else ""))
    return catatan


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
    sels: list[tuple[int, dict]] = []
    for nomor, baris in enumerate(mentah[1:], start=2):
        if not any(_sel(x) for x in baris):
            continue
        sels.append((nomor, {k: (_sel(baris[i]) if i < len(baris) else "") for k, i in idx.items()}))
    catatan_isi = lengkapi_umur_tahun([sel for _, sel in sels])
    out: list[Tahap2Row] = []
    for (nomor, sel), tambahan in zip(sels, catatan_isi):
        v, cek, info, catatan = _v_dari_sheet(sel, kodepos)
        row = Tahap2Row(nomor, v, cek=cek, info=info, murni=False)
        row.koreksi.extend(tambahan + catatan)
        # Wilayah baris: dipakai lengkapi_alamat() kalau Nama Jalan < 10 huruf.
        # Nama kec/desa diambil dari kolom informasi "3"/"4" ("GEROKGAK 510801").
        row.wilayah = _wilayah_dari_info(info, v["idsubsls"])
        terapkan_koreksi_baris(row)
        # Nama Jalan kosong -> nama wilayah baris (TAHAP2_JALAN_KOSONG_DARI_WILAYAH).
        if TAHAP2_JALAN_KOSONG_DARI_WILAYAH and not row["jalan_domisili"].strip():
            isi = lengkapi_alamat("0", row.wilayah)
            if isi and isi != "0":
                row.v["jalan_domisili"] = isi
                row.koreksi.append(f"Nama Jalan kosong -> nama wilayah '{isi}' (ketetapan user)")
        out.append(row)
    beri_pembeda_ganda(out)
    return out


def pengusaha_cadangan(nama_usaha: str) -> tuple[str, str]:
    """12a kosong/"-" -> (nama pengganti, alasan); ("", "") kalau tidak bisa.
    Ketetapan user 2026-09-24 (baris 1595-1597): pakai nama di dalam KURUNG pada
    nama usaha kalau ada, kalau tidak "<TAHAP2_PENGUSAHA_KOSONG_AWALAN> <nama usaha>".
    Isi kurung dipakai HANYA kalau berupa nama (bukan angka/keterangan spt "(2)",
    "(cabang)") — kalau ragu, jalur awalan yang dipakai, bukan tebakan."""
    nama = " ".join(str(nama_usaha or "").split())
    if not TAHAP2_PENGUSAHA_KOSONG_AWALAN or not nama:
        return "", ""
    dalam_kurung = [" ".join(m.split()) for m in re.findall(r"\(([^)]*)\)", nama)]
    for isi in dalam_kurung:
        if len(isi) >= 3 and re.fullmatch(r"[A-Za-z.'\- ]+", isi):
            return isi.upper(), f"12a kosong/'-' -> '{isi.upper()}' (nama dalam kurung di nama usaha)"
    tanpa_kurung = " ".join(re.sub(r"\([^)]*\)", " ", nama).split()) or nama
    pengganti = f"{TAHAP2_PENGUSAHA_KOSONG_AWALAN} {tanpa_kurung}".upper()
    return pengganti, f"12a kosong/'-' -> '{pengganti}' (tidak ada nama dalam kurung di nama usaha)"


def _kunci_teks(teks) -> str:
    return " ".join(str(teks or "").split()).upper()


def terapkan_koreksi_baris(row: "Tahap2Row") -> None:
    """TAHAP2_KOREKSI_BARIS: koreksi yang diputuskan user utk baris tertentu,
    dicocokkan lewat (idsubsls, 8b, 12a) — bukan nomor baris, supaya tetap kena
    kalau sheet disisipi baris. Hanya "nama" & "umur" yang dikenal; kunci lain
    ditolak (salah ketik config jangan diam-diam diabaikan)."""
    cari = (row["idsubsls"], _kunci_teks(row["nama_komersial"]), _kunci_teks(row["pengusaha"]))
    for (ids, nama, pemilik), isi in TAHAP2_KOREKSI_BARIS.items():
        if (ids, _kunci_teks(nama), _kunci_teks(pemilik)) != cari:
            continue
        asing = set(isi) - {"nama", "umur"}
        if asing:
            raise ValueError(f"TAHAP2_KOREKSI_BARIS {ids}/{nama}: kunci tidak dikenal {sorted(asing)}")
        if isi.get("nama"):
            row.nama_tetap = " ".join(isi["nama"].split())
            row.koreksi.append(f"nama usaha diganti -> '{row.nama_tetap}' (ketetapan user)")
        if isi.get("umur"):
            lama = row["umur"]
            row.v["umur"] = str(isi["umur"])
            row.koreksi.append(f"12c umur '{lama}' -> '{row.v['umur']}' (koreksi per baris, ketetapan user)")
        return


def _nama_kabkota(idsubsls: str) -> str:
    """Nama kabupaten utk lengkapi_alamat: WILAYAH_BY_IDSUBSLS persis, kalau tidak
    ada nama TERBANYAK di antara entri berawalan 4 digit yang sama. "" kalau tidak ada."""
    persis = WILAYAH_BY_IDSUBSLS.get(idsubsls, {}).get("kabkota", "")
    if persis:
        return persis
    suara: dict[str, int] = defaultdict(int)
    for kode, wil in WILAYAH_BY_IDSUBSLS.items():
        if idsubsls and kode[:4] == idsubsls[:4] and wil.get("kabkota"):
            suara[wil["kabkota"]] += 1
    return max(suara, key=suara.get) if suara else ""


def _wilayah_dari_info(info: dict, idsubsls: str = "") -> dict:
    """Kolom "3" = "GEROKGAK 510801", kolom "4" = "PATAS 0010" -> nama kec &
    desa (angka di belakang dibuang), plus nama kabupaten dari idsubsls
    (_nama_kabkota). Dipakai HANYA utk melengkapi Nama Jalan yang kurang dari
    10 huruf; kode wilayah tetap dari kolom idsubsls."""
    def _nama(teks: str) -> str:
        return " ".join(re.sub(r"[\d.\-]+\s*$", "", str(teks or "")).split()).upper()
    wil = {}
    if _nama(info.get("kec", "")):
        wil["kecamatan"] = _nama(info["kec"])
    if _nama(info.get("desa", "")):
        wil["desa"] = _nama(info["desa"])
    if kab := _nama_kabkota(idsubsls):
        wil["kabkota"] = kab.upper()
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


def _kata_penting(teks: str) -> set:
    """Kata >= 4 huruf dari `teks`, tanpa KATA_UMUM_KBLI & tanpa kode dalam kurung."""
    bersih = re.sub(r"\([^)]*\)", " ", str(teks or "")).lower()
    return {k for k in re.findall(r"[a-z]{4,}", bersih) if k not in KATA_UMUM_KBLI}


def kbli_tidak_nyambung(row: Tahap2Row) -> str:
    """Alasan kalau judul KBLI tidak berbagi satu kata pun dgn 13a/13f, "" kalau
    nyambung / tidak bisa dinilai. Lihat TAHAP2_TANDAI_KBLI_TIDAK_NYAMBUNG."""
    if not TAHAP2_TANDAI_KBLI_TIDAK_NYAMBUNG:
        return ""
    judul = row.judul_kbli
    kata_judul = _kata_penting(judul)
    kata_isi = _kata_penting(row["keg_utama"]) | _kata_penting(row["produk"])
    # Salah satunya tidak punya kata yang bisa dinilai -> jangan menuduh.
    if not judul or not kata_judul or not kata_isi or kata_judul & kata_isi:
        return ""
    return (f"KBLI {row['kbli']} '{judul}' tidak berbagi satu kata pun dgn 13a "
            f"'{row['keg_utama']}'" + (f" / 13f '{row['produk']}'" if row["produk"] else "")
            + " — periksa apakah KBLI-nya keliru (di form bisa pakai tombol generate KBLI lalu opsi 1)")


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
        if alasan_kbli := kbli_tidak_nyambung(row):
            h.tanda.append(alasan_kbli)
        if not row["kodepos"]:
            h.masalah.append(("KODEPOS_TIDAK_DIKETAHUI",
                              f"kodepos desa {row.idsubsls[:10]} tidak ada di KODEPOS_BY_IDSUBSLS/"
                              "KODEPOS_BY_DESA — tambahkan di inti/config_lokal.py, beri kolom 'kodepos' "
                              "di sheet, atau pakai --kodepos"))
    return hasil
