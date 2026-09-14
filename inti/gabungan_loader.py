"""
gabungan_loader.py — Baca tab "gabungan" (Google Sheet "Agenda") sbg sumber
input, lalu periksa kelayakan tiap baris TANPA browser & TANPA VPN.

Beda mendasar dgn data_loader.py (backlog LKpenyalinan):
- Setiap kolom sheet ini SUDAH jawaban final per rincian form. Tidak ada
  kalkulasi 10%, tidak ada file export fasih-sm, tidak ada aturan pekerja
  <=3 / override aset 0 — angka diketik APA ADANYA.
- Tidak ada kolom No/assignment_id. Identitas baris = `kunci` (hash akun
  PPL + idsubsls + nama dokumen), stabil walau urutan sheet berubah.

CARA EXPORT
-----------
Buka tab "gabungan", lalu File > Download > Microsoft Excel (.xlsx), atau
Comma Separated Values (.csv — hanya tab yang sedang aktif yang ikut).

Kolom dicocokkan lewat AWALAN judul (mis. "26. a."), bukan posisi huruf
kolom. Spasi, baris baru & spasi di sekitar titik dinormalkan dulu, jadi
"8.c. Alamat" dan "8. c. Alamat" sama-sama cocok.

PRINSIP PEMERIKSAAN: lebih baik skip sebelum dokumen dibuat drpd baru
ketahuan GALAT setelah dokumen terlanjur ada (hapus dokumen = soft-delete
lewat admin pusat). Pilihan opsi radio divalidasi thd daftar opsi yang
DIKUTIP dari dump DOM asli (log_screenshots/*.map.tsv), bukan tebakan.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from inti.config import (
    GABUNGAN_13F_DARI_13A, GABUNGAN_IZINKAN_JALAN_KOSONG, MINIMAL_TOTAL_RUPIAH, WILAYAH_BY_IDSUBSLS,
)

NAMA_SHEET = "gabungan"

# 8b "Nama komersial usaha/perusahaan": validasi form "Panjang maksimal 50"
# (GALAT ringkasan, run live 2026-09-14).
MAKS_8B = 50
# 12c Umur: GALAT "Wajib terisi 10-99" (run live 2026-09-14, Agenda1-1.xlsx
# berisi umur 0 di SEMUA baris -> tiap baris jadi DRAFT yang tak bisa dikirim).
UMUR_MIN, UMUR_MAKS = 10, 99

# key internal -> AWALAN judul kolom (sesudah _norm_judul). Key sengaja
# disamakan dgn dataKey fasih-web kalau ada padanannya, supaya fill_gabungan
# bisa langsung memakainya. Pengecualian: "nib_nomor" (lihat config.DK).
KOLOM: dict[str, str] = {
    "akun_ppl": "akun ppl",
    "pilih_prov": "pilih provinsi",
    "pilih_kab": "pilih kabupaten",
    "pilih_kec": "pilih kecamatan",
    "pilih_desa": "pilih desa",
    "pilih_sls": "pilih sls",
    "pilih_subsls": "pilih subsls",
    "nama": "nama keluarga/bangunan/usaha",   # muncul 2x identik -> kolom pertama
    "ubah_sls": "8.apakah mengalami perubahan sls",
    "kodepos": "10.kodepos",
    "is_new": "tambah",
    "ada_bang_usaha": "keberadaan bangunan lainnya",
    "jalan_domisili": "nama jalan/gang",
    "nomor_domisili": "blok/nomor rumah",
    "no_bang": "nomor urut bangunan",          # TIDAK dipakai mengisi (aturan keselamatan #3)
    "kode_bang": "kode penggunaan bangunan",
    "latitude": "latitude",
    "longitude": "longitude",
    "pilih_umkm_sls": "pilih umkm dalam satu sls",
    "keberadaan_usaha": "keberadaan usaha",
    "nama_komersial": "8.b.",
    "alamat_usaha_view": "8.c.",               # auto dari SE2026-P, hanya informasi
    "hp": "nomor hp/whatsapp",
    "jenis_kawasan": "8.d.",
    "punya_nib": "10.a.",
    "nib_nomor": "10.b.",
    "tidak_nib": "10.c.",
    "badan_usaha": "11.a.",
    "lap_keuangan": "11.d.",
    "pengusaha": "12.a.",
    "jk": "12.b.",
    "umur": "12.c.",
    "nik_pengusaha": "12.d.",
    "keg_utama": "13.a.",
    "produk_sendiri": "13.b1.",
    "layanan_mamin": "13.b2.",
    "keg_penjualan": "13.b3.",
    "keg_jasa": "13.b4.",
    "lokasi_usaha": "13.c.",
    "produk": "13.f.",                          # OPSIONAL — tidak ada di sheet 2026-09-13
    "kbli": "pilih dari master kbli",
    "jaringan": "14.a.",
    "internet": "16.a.",
    "internet_pesanan": "16.b1.",
    "internet_produksi": "16.b2.",
    "internet_distribusi": "16.b3.",
    "internet_beli": "16.b4.",
    "internet_promosi": "16.b5.",
    "internet_lainnya": "16.b6.",
    "digital": "16.c.",
    "produksi_lingkungan": "17.a.",
    "perlindungan_lingkungan": "17.b.",
    "produk_seni": "18.",
    "mitra_kdkmp": "21.",
    "peran_mbg": "22.",
    "barang_non_pddk": "23.a.",
    "jasa_non_pddk": "23.b.",
    "beli_jasa_non_pddk": "23.c.",
    "tk_laki": "24.a1.",
    "tk_pr": "24.b1.",
    "tk_dibayar": "24.a2.",
    "tk_tdk_dibayar": "24.b2.",
    "tahun_operasi": "25.",
    "idsubsls": "idsubsls",
    "gaji": "26.a.",
    "biaya_produksi": "26.b.",
    "biaya_pembelian": "26.c.",
    "operasional": "26.d.",
    "non_operasional": "26.e.",
    "nilai_pendapatan": "27.a.",
    "pendapatan_lain": "27.b.",
    "pendapatan_online": "27.d.",
    "aset_usaha_thn": "28.a.",   # label asli: aset TANAH & BANGUNAN
    "aset_lain_thn": "28.b.",    # label asli: aset SELAIN tanah & bangunan
    "luas_tanah_thn": "28.d.",
    "pribadi": "29.a.",
    "non_profit": "29.b.",
    "publik": "29.c.",
    "non_publik": "29.d.",
    "pemerintah": "29.e.",
    "asing": "29.f.",
    "nama_info_list": "nama pemberi informasi",
}
KOLOM_OPSIONAL = {"produk"}

YA_TIDAK = ("1. Ya", "2. Tidak")

# Opsi radio yang BENAR-BENAR ada di form — dikutip dari dump DOM asli
# (log_screenshots/*.map.tsv, label "-label" di bawah tiap komponen).
# Nilai sheet yang tidak persis salah satu dari ini PASTI gagal diklik, jadi
# baris itu di-skip sebelum dokumen dibuat. Contoh nyata 2026-09-13: 14 baris
# LPG ber-11a "1. Perseroan Terbatas (PT)/CV" — opsi itu tidak ada; form
# memisahkan "1.a. Perseroan (PT/NV, ...)" dan "7. Persekutuan Komanditer (CV)".
OPSI_FORM: dict[str, tuple] = {
    "jenis_kawasan": (
        "1. Kawasan Ekonomi Khusus (KEK)", "2. Kawasan Industri (KI)", "3. Stasiun", "4. Bandara",
        "5. Pelabuhan", "6. Terminal", "7. Rest area jalan tol",
        "8. Kawasan sentra ekonomi perdesaan/kelurahan", "9. Kawasan usaha lainnya",
        "10. Di luar kawasan",
    ),
    "punya_nib": YA_TIDAK,
    "tidak_nib": (
        "1. Dalam proses pembuatan NIB", "2. Pengurusan NIB rumit", "3. Tidak memerlukan NIB",
        "4. Tidak tahu tentang NIB", "5. Lainnya",
    ),
    "badan_usaha": (
        "1.a. Perseroan (PT/NV, PT Persero, PT Tbk, PT Persero Tbk, Perseroan Daerah",
        "1.b. Perseroan perorangan", "2. Yayasan", "3. Koperasi", "4. Dana Pensiun",
        "5. Perum/Perumda", "6. BUM Desa", "7. Persekutuan Komanditer (CV)",
        "8. Persekutuan Firma (Fa)", "9. Persekutuan Perdata (Maatschap)",
        "10. Kantor Perwakilan Luar Negeri", "11. Badan Usaha Luar Negeri",
        "12. Badan Usaha Lainnya (Contoh: BLU, PTN-BH)", "13. Bukan Badan Usaha",
    ),
    "lap_keuangan": YA_TIDAK,
    "jk": ("1. Laki-laki", "2. Perempuan"),
    "produk_sendiri": YA_TIDAK,
    "layanan_mamin": YA_TIDAK,
    "keg_penjualan": YA_TIDAK,
    "keg_jasa": ("1. Jasa", "2. Pertanian, Perikanan, dan Kehutanan"),
    "lokasi_usaha": (
        "1. Apotek", "2. Swalayan", "3. Los Pasar", "4. Toko, ruko, dan sejenisnya",
        "5. Kedai, stan, tenda", "6. Bar", "7. Kelab malam, diskotek", "8. Kafe",
        "9. Restoran, warung makan, dan sejenisnya", "10. Keliling", "11. Daring (online)",
    ),
    "jaringan": (
        "1. Tunggal", "2. Kantor pusat", "3. Cabang", "4. Perwakilan", "5. Pabrik",
        "6. Unit pembantu/penunjang",
    ),
    "internet": YA_TIDAK,
    "internet_pesanan": YA_TIDAK,
    "internet_produksi": YA_TIDAK,
    "internet_distribusi": YA_TIDAK,
    "internet_beli": YA_TIDAK,
    "internet_promosi": YA_TIDAK,
    "internet_lainnya": YA_TIDAK,
    "digital": YA_TIDAK,
    "produksi_lingkungan": ("1. Ya, seluruhnya", "2. Ya, sebagian", "3. Tidak sama sekali"),
    "perlindungan_lingkungan": YA_TIDAK,
    "produk_seni": YA_TIDAK,
    "mitra_kdkmp": YA_TIDAK,
    "peran_mbg": (
        "1. Ya, sebagai SATUAN PELAYANAN PEMENUHAN GIZI (SPPG)", "2. Ya, sebagai supplier",
        "3. Ya, sebagai penerima manfaat MBG (Sekolah, Puskesmas)", "4. Ya, peran lainnya",
        "5. Tidak terlibat MBG",
    ),
    "barang_non_pddk": YA_TIDAK,
    "jasa_non_pddk": YA_TIDAK,
    "beli_jasa_non_pddk": YA_TIDAK,
}

KEY_16B = ("internet_pesanan", "internet_produksi", "internet_distribusi",
           "internet_beli", "internet_promosi", "internet_lainnya")
KEY_PEKERJA = ("tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar")
# Pola 24 tidak konsisten yang PERSIS ini diganti (ketetapan user 2026-09-14):
# Agenda1-1.xlsx 66 baris & Agenda2.xlsx 57 baris berisi laki 0 + perempuan 2
# tapi dibayar 0 + tidak dibayar 1. Dibayar sengaja tetap 0: 26a di baris itu
# 0, dan form menolak 24a2 > 0 dgn 26a/24a2 <= Rp50.000 (file-validation `gaji`).
# Pola lain TIDAK ditebak -> tetap PEKERJA_24_TIDAK_KONSISTEN.
KOREKSI_PEKERJA = {("0", "2", "0", "1"): ("0", "2", "0", "2")}
KEY_26 = ("gaji", "biaya_produksi", "biaya_pembelian", "operasional", "non_operasional")
KEY_27 = ("nilai_pendapatan", "pendapatan_lain")
KEY_28 = ("aset_usaha_thn", "aset_lain_thn", "luas_tanah_thn")
KEY_29 = ("pribadi", "non_profit", "publik", "non_publik", "pemerintah", "asing")

# Jalur yang di-hardcode fasih_web.py / main_gabungan.py. Baris yang meminta
# nilai lain butuh alur berbeda (mis. rincian 9 kalau SLS berubah), jadi
# di-skip — bukan diam-diam diisi dgn nilai hardcode.
NILAI_TETAP: dict[str, tuple] = {
    "ubah_sls": ("2. Tidak",),
    "ada_bang_usaha": ("2. Baru",),
    "keberadaan_usaha": ("2. Baru",),
    "kode_bang": ("", "1. Bangunan Khusus Usaha"),
    "pilih_umkm_sls": ("", "Tidak Ada"),
    "nama_info_list": ("Lainnya",),
}


def format_nama_usaha(nama: str, pemilik: str) -> str:
    """Penamaan usaha alur Agenda: "<nama_usaha> (<nama_pemilik>)" —
    ketetapan user 2026-09-14, sama dgn pola 3 record manual backlog lama
    (mis. "WARUNG SEMBAKO (KETUT SUDANING)"). Pemilik = kolom 12a.

    Kalau nama pemilik SUDAH tertulis di nama usaha, yang di luar kurung
    dihapus & hanya yang di dalam kurung dicetak (ketetapan user 2026-09-14,
    supaya muat batas 50 karakter 8b): "PANGKALAN GAS JAMALUDIN" + "JAMALUDIN"
    -> "PANGKALAN GAS (JAMALUDIN)". Cocok = nama pemilik UTUH sbg kata
    (bukan bagian kata lain), tanpa beda huruf besar.

    Hasilnya SELALU tepat satu pasang kurung, di belakang (ketetapan user
    2026-09-14): kurung di dalam nama/pemilik dibuang, isinya dipertahankan.
    Kasus nyata baris 393 — 12a "I Nyoman Nama Putra Sp.P (K" (kurung tak
    tertutup) — dulu jadi "PRAKTIK DOKTER ) (I Nyoman Nama Putra Sp.P (K)",
    kini "PRAKTIK DOKTER (I Nyoman Nama Putra Sp.P K)".

    Dikembalikan apa adanya kalau 12a kosong (baris itu sudah di-skip)."""
    nama = " ".join(nama.split())
    pemilik = " ".join(re.sub(r"[()]", " ", pemilik).split())
    if not nama or not pemilik:
        return nama
    # Pemilik dicari per kata, toleran thd kurung/spasi di antaranya, supaya
    # "SP.P (K)" di nama tetap cocok dgn pemilik "Sp.P K".
    pola = r"[\s()]+".join(re.escape(k) for k in pemilik.split())
    sisa = re.sub(rf"\(?\s*(?<!\w){pola}(?!\w)\s*\)?", " ", nama, flags=re.I)
    # Kurung sisa & pemisah yang tertinggal di tepi ("UD. WIDE/ SUARDANTI").
    sisa = " ".join(re.sub(r"[()]", " ", sisa).split()).strip(" ,;:-/&")
    return f"{sisa} ({pemilik})" if sisa else f"({pemilik})"


def nama_muat(nama: str, pemilik: str) -> str:
    """format_nama_usaha, KECUALI hasilnya > MAKS_8B karakter: nama usaha saja
    TANPA kurung (ketetapan user 2026-09-14 — Agenda1-1.xlsx: 12a berisi jabatan
    "Bidan/Perawat Penanggung Jawab Pustu", bukan nama orang, sehingga 78 baris
    > 50). Kurung di nama dibuang, isinya dipertahankan; kolom 12a di form tetap
    diisi utuh. Masih > MAKS_8B -> baris di-skip 8B_TERLALU_PANJANG."""
    lengkap = format_nama_usaha(nama, pemilik)
    if len(lengkap) <= MAKS_8B:
        return lengkap
    return " ".join(re.sub(r"[()]", " ", nama).split())


# Nama Jalan (SE2026-P): isi selain kosong/"-" wajib memuat >= 10 huruf a-z
# (file-validation template, dataKey jalan_domisili).
MIN_HURUF_JALAN = 10


def jumlah_huruf(teks: str) -> int:
    return len(re.findall(r"[a-zA-Z]", teks or ""))


def lengkapi_alamat(jalan: str, wilayah: dict) -> str:
    """Nama Jalan yang kurang dari MIN_HURUF_JALAN huruf dilengkapi nama
    wilayah BARIS itu (ketetapan user 2026-09-14): banjar, lalu desa, lalu
    kecamatan, lalu provinsi — berhenti begitu syarat huruf terpenuhi.
    Bagian yang namanya sudah tertulis tidak ditambah lagi ("DESA JULAH" tidak
    diberi "DESA JULAH" lagi). "0" bukan alamat -> dianggap kosong. Kosong
    atau "-" dibiarkan (lolos validasi form). Kalau nama wilayah tidak ada,
    hasilnya tetap pendek dan baris di-skip JALAN_KURANG_10_HURUF."""
    jalan = " ".join((jalan or "").split())
    if not jalan or jalan == "-" or jumlah_huruf(jalan) >= MIN_HURUF_JALAN:
        return jalan
    bagian = [] if jalan == "0" else [jalan]
    kandidat = [
        (wilayah.get("sls", ""), wilayah.get("sls", "")),
        (wilayah.get("desa", ""), f"DESA {wilayah.get('desa', '')}"),
        (wilayah.get("kecamatan", ""), f"KECAMATAN {wilayah.get('kecamatan', '')}"),
        (wilayah.get("provinsi", ""), wilayah.get("provinsi", "")),
    ]
    for nama, teks in kandidat:
        if jumlah_huruf(", ".join(bagian)) >= MIN_HURUF_JALAN:
            break
        inti = re.sub(r"^(BANJAR|BR\.?|LINGKUNGAN|LINGK\.?|DUSUN)\s+", "", nama.strip().upper())
        if not inti or inti in ", ".join(bagian).upper():
            continue
        bagian.append(teks.strip().upper())
    return ", ".join(bagian) if bagian else jalan


def _norm_judul(s) -> str:
    s = " ".join(str(s or "").split()).lower()
    return re.sub(r"\s*\.\s*", ".", s)


def _sel(v) -> str:
    """Nilai sel -> teks rapi. Angka bulat dari xlsx (15056000.0) -> "15056000"."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


def _cari_indeks(judul: list[str]) -> dict[str, int]:
    norm = [_norm_judul(j) for j in judul]
    idx: dict[str, int] = {}
    hilang, ambigu = [], []
    for key, awalan in KOLOM.items():
        cocok = [i for i, h in enumerate(norm) if h.startswith(awalan)]
        if not cocok:
            if key not in KOLOM_OPSIONAL:
                hilang.append(f"{key} (awalan '{awalan}')")
            continue
        if len({norm[i] for i in cocok}) > 1:
            ambigu.append(f"{key}: {[judul[i] for i in cocok]}")
            continue
        idx[key] = cocok[0]
    if hilang or ambigu:
        raise ValueError(
            f"Judul kolom sheet tidak sesuai. Hilang: {hilang}. Ambigu: {ambigu}. "
            "Sesuaikan KOLOM di gabungan_loader.py kalau judul sheet memang berubah."
        )
    return idx


def _baca_mentah(path: Path) -> list[list]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl  # hanya perlu kalau sumbernya xlsx
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            ws = next((w for w in wb.worksheets if w.title.strip().lower() == NAMA_SHEET), None)
            if ws is None:
                raise ValueError(f"Sheet '{NAMA_SHEET}' tidak ada di {path.name}. Tersedia: {wb.sheetnames}")
            return [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [list(r) for r in csv.reader(f)]


@dataclass
class GabunganRow:
    baris: int   # nomor baris di sheet (judul = baris 1) — yang dilihat user di Sheets
    v: dict
    # Nama wilayah asli baris {provinsi, kabkota, kecamatan, desa[, sls]} —
    # dari tab lain di xlsx (lihat _baca_nama_wilayah) & config. Bisa kosong.
    wilayah: dict = field(default_factory=dict)
    wilayah_bentrok: str = ""   # terisi kalau sumber nama wilayah saling bertentangan
    koreksi: list = field(default_factory=list)  # nilai sheet yang diubah ketetapan user (-> tanda review)

    def __getitem__(self, key: str) -> str:
        return self.v.get(key, "")

    @property
    def nama(self) -> str:
        """Nama MENTAH kolom sheet — dipakai `kunci`, BUKAN nama di fasih-web."""
        return self["nama"]

    @property
    def nama_dokumen(self) -> str:
        """Nama yang diketik ke fasih-web ("+Dokumen Baru" & SE2026-P) dan
        dipakai mencari dokumen di list: "<nama> (<12a>)" (lihat nama_muat)."""
        return nama_muat(self.nama, self["pengusaha"])

    @property
    def nama_komersial(self) -> str:
        """8b dgn format yang sama dgn nama dokumen (ketetapan user: penamaan
        berlaku utk nama usaha DAN nama komersial). Masih lebih dari MAKS_8B
        karakter setelah nama_muat -> skip 8B_TERLALU_PANJANG, tidak dipotong."""
        return nama_muat(self["nama_komersial"], self["pengusaha"])

    @property
    def akun_ppl(self) -> str:
        return self["akun_ppl"].strip().lower()

    @property
    def idsubsls(self) -> str:
        return self["idsubsls"]

    @property
    def idsubsls_pilih(self) -> str:
        """idsubsls yang disusun dari kolom "Pilih PROVINSI..SUBSLS". Sheet
        membuang nol di depan pada sebagian baris ("60" utk "060"), jadi
        di-zero-pad ke lebar kodenya (2+2+3+3+4+2)."""
        lebar = (("pilih_prov", 2), ("pilih_kab", 2), ("pilih_kec", 3),
                 ("pilih_desa", 3), ("pilih_sls", 4), ("pilih_subsls", 2))
        return "".join(self[k].zfill(n) for k, n in lebar)

    @property
    def kunci(self) -> str:
        # Sengaja dari nama MENTAH, bukan nama_dokumen: aturan penamaan boleh
        # berubah tanpa memutus pencocokan --lewati-selesai di audit lama.
        teks = f"{self.akun_ppl}|{self.idsubsls}|{self.nama.upper()}"
        return hashlib.sha1(teks.encode("utf-8")).hexdigest()[:10]

    @property
    def jalan_lengkap(self) -> str:
        """Nama Jalan yang diketik ke SE2026-P (dilengkapi nama wilayah kalau
        kurang dari 10 huruf — lihat lengkapi_alamat)."""
        return lengkapi_alamat(self["jalan_domisili"], self.wilayah)

    @property
    def produk_utama(self) -> str:
        if self["produk"]:
            return self["produk"]
        return self["keg_utama"] if GABUNGAN_13F_DARI_13A else ""

    @property
    def rincian_13b4_dirender(self) -> bool:
        return all(self[k].startswith("2") for k in ("produk_sendiri", "layanan_mamin", "keg_penjualan"))

    def angka(self, key: str) -> int:
        return int(self[key])


def _baca_nama_wilayah(path: Path) -> dict[str, dict]:
    """{kode desa 10 digit: {provinsi, kabkota, kecamatan, desa}} dari tab LAIN
    di xlsx Agenda yang punya kolom kode "Pilih DESA" + nama "Desa/Kelurahan"
    (tab "Pangkalan Gas" & "Faskes", 2026-09-14). Tab gabungan sendiri hanya
    berisi kode. Tiap baris tab dicatat di bawah kode dari kolom `idsubsls`
    (10 digit pertama) DAN dari kolom "Pilih ...": sebagian baris sheet punya
    kode Pilih yang tidak cocok dgn idsubsls-nya, jadi per kode dipilih nama
    yang PALING SERING muncul (dulu kode bentrok dibuang -> 26 baris gagal)."""
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        return {}
    import openpyxl
    kolom = {"Pilih PROVINSI": 2, "Pilih KABUPATEN/KOTA": 2, "Pilih KECAMATAN": 3, "Pilih DESA": 3}
    nama = {"Provinsi": "provinsi", "Kabupaten/Kota": "kabkota", "Kecamatan": "kecamatan",
            "Desa/Kelurahan": "desa"}
    suara: dict[str, Counter] = defaultdict(Counter)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            if ws.title.strip().lower() == NAMA_SHEET:
                continue
            it = ws.iter_rows(values_only=True)
            judul = [" ".join(str(j or "").split()) for j in (next(it, None) or [])]
            if not all(k in judul for k in (*kolom, *nama)):
                continue
            ik = {k: judul.index(k) for k in (*kolom, *nama)}
            i_id = judul.index("idsubsls") if "idsubsls" in judul else None
            for sel in it:
                try:
                    kode_pilih = "".join(_sel(sel[ik[k]]).zfill(n) for k, n in kolom.items())
                    info = tuple(_sel(sel[ik[k]]).upper() for k in nama)
                    kode_id = _sel(sel[i_id])[:10] if i_id is not None and i_id < len(sel) else ""
                except IndexError:
                    continue
                if not info[3]:
                    continue
                for kode in {kode_pilih, kode_id}:
                    if len(kode) == 10 and kode.isdigit():
                        suara[kode][info] += 1
    finally:
        wb.close()
    return {kode: dict(zip(nama.values(), c.most_common(1)[0][0])) for kode, c in suara.items()}


def _nama_wilayah_dari_8c(alamat: str) -> dict:
    """Cadangan: "Desa/Kel. TINGA-TINGA, Kec. GEROKGAK, BULELENG, BALI, 81155"
    (kolom 8c baris itu sendiri) -> {desa, kecamatan, kabkota, provinsi}."""
    m = re.search(r"Desa/Kel\.\s*([^,]+),\s*Kec\.\s*([^,]+),\s*([^,]+),\s*([^,]+)", alamat or "", re.I)
    if not m:
        return {}
    desa, kec, kab, prov = (" ".join(x.split()).upper() for x in m.groups())
    return {"desa": desa, "kecamatan": kec, "kabkota": kab, "provinsi": prov}


def load_gabungan(path: str | Path) -> list[GabunganRow]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File sumber tidak ditemukan: {path}")
    mentah = _baca_mentah(path)
    if not mentah:
        raise ValueError(f"{path.name} kosong.")
    idx = _cari_indeks([_sel(j) for j in mentah[0]])
    nama_desa = _baca_nama_wilayah(path)
    out = []
    for nomor, sel in enumerate(mentah[1:], start=2):
        if not any(_sel(x) for x in sel):
            continue
        v = {k: (_sel(sel[i]) if i < len(sel) else "") for k, i in idx.items()}
        row = GabunganRow(nomor, v)
        peta = nama_desa.get(row.idsubsls[:10]) or nama_desa.get(row.idsubsls_pilih[:10]) or {}
        dari_8c = _nama_wilayah_dari_8c(row["alamat_usaha_view"])
        if peta and dari_8c and (peta["desa"], peta["kecamatan"]) != (dari_8c["desa"], dari_8c["kecamatan"]):
            # Kode wilayah & alamat 8c baris ini menunjuk desa berbeda (Agenda baris
            # 278/366, Agenda1-1 baris 41 dst.). Ketetapan user 2026-09-14: pakai desa
            # menurut idsubsls; bentroknya tetap dicatat sbg tanda review.
            row.wilayah_bentrok = (f"desa menurut idsubsls '{peta['desa']}, {peta['kecamatan']}' vs "
                                   f"8c '{dari_8c['desa']}, {dari_8c['kecamatan']}'")
        wil = dict(peta or dari_8c)
        pekerja = tuple(v.get(k, "") for k in KEY_PEKERJA)
        if pekerja in KOREKSI_PEKERJA:
            baru = KOREKSI_PEKERJA[pekerja]
            v.update(zip(KEY_PEKERJA, baru))
            row.koreksi.append(f"24 (laki, perempuan, dibayar, tidak dibayar) {'/'.join(pekerja)} -> "
                               f"{'/'.join(baru)} (ketetapan user)")
        ref = WILAYAH_BY_IDSUBSLS.get(row.idsubsls) or {}
        if ref.get("sls"):
            wil["sls"] = ref["sls"]
        row.wilayah = wil
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Pemeriksaan offline
# ---------------------------------------------------------------------------

@dataclass
class Pemeriksaan:
    masalah: list[tuple[str, str]] = field(default_factory=list)  # (kode, pesan) -> skip
    tanda: list[str] = field(default_factory=list)                # review, tidak skip

    @property
    def status(self) -> str:
        return f"SKIP_DATA_{self.masalah[0][0]}" if self.masalah else "SIAP"

    @property
    def pesan(self) -> str:
        return " | ".join(f"{k}: {p}" for k, p in self.masalah)


def _bulat(s: str) -> bool:
    return s.isdigit()


def periksa_baris(row: GabunganRow, tahun_berjalan: int | None = None,
                  mode_satu_subsls: bool = False) -> Pemeriksaan:
    """`mode_satu_subsls` = semua dokumen dibuat di satu subsls: dokumen TIDAK dibuat di
    idsubsls baris, jadi ketidakcocokan wilayah baris baru berarti saat
    ubah alokasi wilayah nanti -> tanda, bukan skip."""
    tahun_berjalan = tahun_berjalan or datetime.date.today().year
    hasil = Pemeriksaan()
    salah = hasil.masalah.append

    wajib = [
        "akun_ppl", "idsubsls", "nama", "kodepos", "latitude", "longitude", "nama_komersial",
        "hp", "jenis_kawasan", "punya_nib", "badan_usaha", "lap_keuangan", "pengusaha", "jk",
        "umur", "nik_pengusaha", "keg_utama", "produk_sendiri", "layanan_mamin", "keg_penjualan",
        "lokasi_usaha", "kbli", "jaringan", "internet", "produksi_lingkungan",
        "perlindungan_lingkungan", "produk_seni", "mitra_kdkmp", "peran_mbg", "barang_non_pddk",
        "jasa_non_pddk", "beli_jasa_non_pddk", "tahun_operasi",
        *KEY_PEKERJA, *KEY_26, *KEY_27, "pendapatan_online", *KEY_28, *KEY_29,
    ]
    wajib.append("nib_nomor" if row["punya_nib"].startswith("1") else "tidak_nib")
    if row["internet"].startswith("1"):
        wajib += [*KEY_16B, "digital"]
    if not GABUNGAN_IZINKAN_JALAN_KOSONG:
        wajib.append("jalan_domisili")
    kosong = [k for k in wajib if not row[k]]
    if not row.produk_utama:
        kosong.append("produk (13f)")
    if kosong:
        salah(("WAJIB_KOSONG", f"kolom kosong: {', '.join(kosong)}"))

    # Validasi form (file-validation template, dataKey jalan_domisili): isi
    # selain kosong/"-" wajib memuat >= 10 huruf a-z — GALAT "Minimal terisi
    # 10 huruf" (baris 17, run 2026-09-14). Sheet berisi "0", "BR. KAJANAN", dst.
    jalan = row.jalan_lengkap
    if jalan and jalan != "-" and jumlah_huruf(jalan) < MIN_HURUF_JALAN:
        sebab = (f"nama wilayah bertentangan: {row.wilayah_bentrok}" if row.wilayah_bentrok
                 else "nama wilayah baris tidak ditemukan")
        salah(("JALAN_KURANG_10_HURUF", f"Nama Jalan '{jalan}' kurang dari {MIN_HURUF_JALAN} huruf & tidak bisa "
                                        f"dilengkapi — {sebab} (form menolak)"))
    elif jalan != " ".join(row["jalan_domisili"].split()):
        hasil.tanda.append(f"Nama Jalan dilengkapi nama wilayah: '{row['jalan_domisili']}' -> '{jalan}'"
                           + (f" (desa idsubsls dipakai; {row.wilayah_bentrok})" if row.wilayah_bentrok else ""))
    hasil.tanda.extend(row.koreksi)
    for label, nama in (("nama dokumen", row.nama_dokumen), ("8b", row.nama_komersial)):
        if nama and "(" not in nama and row["pengusaha"]:
            hasil.tanda.append(f"{label} tanpa (12a): format lengkap > {MAKS_8B} karakter")

    for key, boleh in NILAI_TETAP.items():
        if row[key].lower() not in {b.lower() for b in boleh}:
            salah(("NILAI_TIDAK_DIDUKUNG", f"{key}='{row[key]}' (alur skrip hanya mendukung {boleh})"))
    if not row["is_new"].lower().startswith("bangunan lainnya"):
        salah(("NILAI_TIDAK_DIDUKUNG", f"is_new='{row['is_new']}' (hanya 'Bangunan Lainnya ...')"))

    for key, opsi in OPSI_FORM.items():
        nilai = row[key]
        if not nilai or (key == "keg_jasa" and not row.rincian_13b4_dirender):
            continue  # kosong sudah dilaporkan di atas; 13b4 tidak dirender -> tidak dipakai
        if key in KEY_16B + ("digital",) and not row["internet"].startswith("1"):
            continue
        if nilai not in opsi:
            salah(("OPSI_TIDAK_ADA_DI_FORM", f"{key}='{nilai}' bukan salah satu opsi form (lihat OPSI_FORM)"))

    tidak_valid = [k for k in (*KEY_PEKERJA, *KEY_26, *KEY_27, "pendapatan_online", *KEY_28, *KEY_29, "umur")
                   if row[k] and not _bulat(row[k])]
    for key, pola in (("idsubsls", r"\d{16}"), ("kodepos", r"\d{5}"), ("kbli", r"\d{5}"),
                      ("tahun_operasi", r"\d{4}")):
        if row[key] and not re.fullmatch(pola, row[key]):
            tidak_valid.append(key)
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if not (-12 <= lat <= 7 and 94 <= lon <= 142):
            tidak_valid.append("latitude/longitude (di luar Indonesia)")
    except ValueError:
        if row["latitude"] and row["longitude"]:
            tidak_valid.append("latitude/longitude")
    if tidak_valid:
        salah(("ANGKA_TIDAK_VALID", f"kolom: {', '.join(tidak_valid)}"))
        return hasil  # pemeriksaan angka di bawah butuh angka yang valid

    if row["idsubsls"] and row.idsubsls_pilih != row.idsubsls:
        pesan = f"idsubsls={row.idsubsls} tapi kolom Pilih PROVINSI..SUBSLS = {row.idsubsls_pilih}"
        if mode_satu_subsls:
            hasil.tanda.append(f"wilayah tujuan ubah alokasi ambigu: {pesan}")
        else:
            salah(("WILAYAH_TIDAK_KONSISTEN", pesan))

    if all(row[k] for k in KEY_PEKERJA):
        l, p, d, td = (row.angka(k) for k in KEY_PEKERJA)
        if l + p != d + td:
            salah(("PEKERJA_24_TIDAK_KONSISTEN",
                   f"24a1+24b1={l + p} (laki {l}, perempuan {p}) != 24a2+24b2={d + td} "
                   f"(dibayar {d}, tidak dibayar {td})"))
    if all(row[k] for k in KEY_29) and sum(row.angka(k) for k in KEY_29) != 100:
        salah(("MODAL_29_BUKAN_100", f"jumlah 29a-29f = {sum(row.angka(k) for k in KEY_29)}"))
    if all(row[k] for k in KEY_26) and sum(row.angka(k) for k in KEY_26) < MINIMAL_TOTAL_RUPIAH:
        salah(("DI_BAWAH_MINIMAL", f"26f={sum(row.angka(k) for k in KEY_26)} < {MINIMAL_TOTAL_RUPIAH}"))
    if all(row[k] for k in KEY_27) and sum(row.angka(k) for k in KEY_27) < MINIMAL_TOTAL_RUPIAH:
        salah(("DI_BAWAH_MINIMAL", f"27c={sum(row.angka(k) for k in KEY_27)} < {MINIMAL_TOTAL_RUPIAH}"))
    if row["umur"] and not UMUR_MIN <= row.angka("umur") <= UMUR_MAKS:
        salah(("UMUR_DI_LUAR_10_99", f"12c umur={row['umur']} (form: wajib {UMUR_MIN}-{UMUR_MAKS}) "
                                     "— perbaiki umur di sheet, jangan ditebak"))
    if row["pendapatan_online"] and row.angka("pendapatan_online") > 100:
        salah(("ANGKA_TIDAK_VALID", f"27d={row['pendapatan_online']} > 100 persen"))
    if row["tahun_operasi"]:
        th = row.angka("tahun_operasi")
        if th >= tahun_berjalan:
            # Form mengganti 26-29 dgn 30-33 (angka SATU BULAN) utk usaha yang
            # mulai beroperasi tahun berjalan; angka sheet ini tahunan.
            salah(("VARIAN_BULANAN", f"tahun_operasi={th} -> form pakai rincian 30-33 bulanan"))
        elif th < 1900:
            salah(("ANGKA_TIDAK_VALID", f"tahun_operasi={th}"))
    if row["internet"].startswith("1") and not any(row[k].startswith("1") for k in KEY_16B):
        salah(("16B_TANPA_YA", "16a = Ya tapi 16b1-16b6 tidak ada yang Ya (form menolak)"))

    if not row["produk"] and row.produk_utama:
        hasil.tanda.append("13f disalin dari 13a (sheet tidak punya kolom 13f)")
    if len(row.nama_komersial) > MAKS_8B:
        salah(("8B_TERLALU_PANJANG", f"8b '{row.nama_komersial}' {len(row.nama_komersial)} karakter > "
                                     f"{MAKS_8B} (form menolak) — singkatkan nama usaha/12a di sheet"))
    if not row["jalan_domisili"] and GABUNGAN_IZINKAN_JALAN_KOSONG:
        hasil.tanda.append("Nama Jalan KOSONG (belum pernah diuji dikosongkan)")
    return hasil


def periksa_semua(rows: list[GabunganRow], tahun_berjalan: int | None = None,
                  mode_satu_subsls: bool = False) -> dict[int, Pemeriksaan]:
    """{baris: Pemeriksaan} — per baris + pemeriksaan LINTAS baris.
    Mode satu subsls: SEMUA dokumen masuk list PENDATAAN satu akun, jadi
    bentrok nama diperiksa lintas SELURUH sheet, bukan per akun PPL."""
    hasil = {r.baris: periksa_baris(r, tahun_berjalan, mode_satu_subsls) for r in rows}

    per_kunci = defaultdict(list)
    for r in rows:
        per_kunci[r.kunci].append(r.baris)
    for kunci, daftar in per_kunci.items():
        if len(daftar) > 1:
            for b in daftar:
                hasil[b].masalah.append(("BARIS_GANDA", f"akun+idsubsls+nama sama dgn baris {daftar}"))

    # Cek "dokumen sudah ada" di fasih_web mencocokkan nama sbg SUBSTRING.
    # Kalau satu PPL punya "APOTEK SEHAT" & "APOTEK SEHAT 2", mencari yang
    # pertama bisa menemukan yang kedua -> skrip mengisi dokumen yang SALAH.
    # Diperiksa pada nama_dokumen (yang dicari di list) DAN nama mentah (yang
    # dicari pengaman dokumen-bernama-lama di create_document).
    # Nama SAMA PERSIS dgn kunci beda (mis. subsls lain) juga bentrok —
    # pencarian membuka dokumen pertama yang ketemu. Kunci sama = BARIS_GANDA.
    per_list = defaultdict(list)
    for r in rows:
        per_list["" if mode_satu_subsls else r.akun_ppl].append(r)
    lingkup = "list satu akun" if mode_satu_subsls else "PPL sama"
    for anggota in per_list.values():
        for a in anggota:
            for b in anggota:
                if a.baris == b.baris or a.kunci == b.kunci:
                    continue
                # Mode satu subsls: nama mentah tidak pernah dipakai mencari (dokumen
                # di list satu akun ini selalu bernama nama_dokumen) -> cukup tanda di bawah.
                pasangan = [(a.nama_dokumen, b.nama_dokumen)] + ([] if mode_satu_subsls else [(a.nama, b.nama)])
                for na, nb in pasangan:
                    if na.upper() in nb.upper() and (na.upper() != nb.upper() or a.baris < b.baris):
                        for x, y in ((a, b), (b, a)):
                            hasil[x.baris].masalah.append((
                                "NAMA_TUMPANG_TINDIH",
                                f"'{na}' terkandung di '{nb}' (baris {y.baris}, {lingkup}) — "
                                "pencarian dokumen bisa membuka dokumen yang salah"))
                        break
                else:
                    # Pengaman dokumen-bernama-lama di create_document mencari
                    # nama MENTAH sbg substring; kalau dokumen baris b sudah
                    # dibuat duluan, baris a akan berhenti SKIP_DOKUMEN_NAMA_LAMA.
                    if mode_satu_subsls and a.nama.upper() in b.nama_dokumen.upper():
                        hasil[a.baris].tanda.append(
                            f"nama '{a.nama}' terkandung di nama dokumen baris {b.baris} — bisa "
                            "SKIP_DOKUMEN_NAMA_LAMA kalau dokumen baris itu dibuat lebih dulu")

    # Kodepos dialokasikan per DESA; nilai minoritas dalam satu desa patut dicek.
    per_desa = defaultdict(Counter)
    for r in rows:
        if len(r.idsubsls) == 16 and r["kodepos"]:
            per_desa[r.idsubsls[:10]][r["kodepos"]] += 1
    for r in rows:
        c = per_desa.get(r.idsubsls[:10])
        if c and len(c) > 1:
            mayoritas, n = c.most_common(1)[0]
            if r["kodepos"] != mayoritas and c[r["kodepos"]] < n:
                hasil[r.baris].tanda.append(
                    f"kodepos {r['kodepos']} beda dgn mayoritas desa {r.idsubsls[:10]} ({mayoritas}, {dict(c)})")
    return hasil


def cocokkan_wilayah_dokumen(nilai: dict, idsubsls: str, nama_ref: dict | None = None) -> tuple[str, str]:
    """Bandingkan rincian 1-6 BLOK I dokumen yang terbuka (auto dari wilayah
    dokumen) dgn subsls tujuan input. -> ('COCOK'|'BEDA'|'TIDAK_TERBACA', ringkasan).

    Format nilai field belum pernah terekam (dump DOM tidak memuat value
    input), jadi yang diterima: kode saja ("014"), kode panjang
    ("5108060014"), atau "[014] NAMA". Field TANPA angka dibandingkan lewat
    nama (`nama_ref` = WILAYAH_BY_IDSUBSLS[idsubsls]) kalau ada.
    Kode SLS WAJIB terbukti cocok; tanpa itu hasilnya TIDAK_TERBACA."""
    i = idsubsls
    kandidat = {
        "prov": {i[:2]},
        "kab": {i[2:4], i[:4]},
        "kec": {i[4:7], i[:7]},
        "desa": {i[7:10], i[:10]},
        "kode_sls": {i[10:16], i[10:14], i[:14], i[7:16], i},
    }
    kolom_ref = {"prov": "provinsi", "kab": "kabkota", "kec": "kecamatan", "desa": "desa"}
    ringkas = "; ".join(f"{k}='{nilai.get(k, '')}'" for k in kandidat)
    beda, sls_cocok = [], False
    for key, boleh in kandidat.items():
        teks = " ".join(str(nilai.get(key) or "").split())
        # Hanya kode di AWAL teks — angka di dalam nama ("BANJAR 2") bukan kode.
        m = re.match(r"\[?([\d.\-\s]*\d)", teks)
        angka = re.sub(r"\D", "", m.group(1)) if m else ""
        if angka:
            if angka in boleh:
                sls_cocok |= key == "kode_sls"
            else:
                beda.append(f"{key}='{teks}'")
        elif teks and nama_ref and key in kolom_ref:
            if teks.upper() != str(nama_ref.get(kolom_ref[key], "")).upper():
                beda.append(f"{key}='{teks}' (referensi '{nama_ref.get(kolom_ref[key])}')")
    if beda:
        return "BEDA", f"wilayah dokumen BUKAN {idsubsls}: {', '.join(beda)} | {ringkas}"
    if not sls_cocok:
        return "TIDAK_TERBACA", f"kode SLS dokumen tidak terbaca sbg angka | {ringkas}"
    return "COCOK", ringkas


def kelompok_per_akun(rows: list[GabunganRow]) -> dict[str, list[GabunganRow]]:
    """Satu sesi login per akun PPL, urutan kemunculan di sheet dipertahankan."""
    grup: dict[str, list[GabunganRow]] = {}
    for r in rows:
        grup.setdefault(r.akun_ppl, []).append(r)
    return grup


def parse_pilihan_baris(teks: str) -> set[int]:
    """"2,5,10-20" -> {2, 5, 10, ..., 20} (nomor baris seperti di Google Sheets)."""
    hasil: set[int] = set()
    for bagian in (teks or "").split(","):
        bagian = bagian.strip()
        if not bagian:
            continue
        if "-" in bagian:
            a, b = (int(x) for x in bagian.split("-", 1))
            hasil.update(range(min(a, b), max(a, b) + 1))
        else:
            hasil.add(int(bagian))
    return hasil
