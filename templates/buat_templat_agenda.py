#!/usr/bin/env python3
"""
buat_templat_agenda.py — Bangkitkan templates/Agenda.contoh.xlsx: templat KOSONG
sheet "Agenda" (tab "gabungan") untuk alur input_gabungan/main_gabungan.py.

Isi workbook:
  gabungan      judul kolom PERSIS yang dibaca inti/gabungan_loader.py (KOLOM),
                dropdown utk kolom berpilihan (OPSI_FORM & NILAI_TETAP), kolom kode
                berformat teks (idsubsls 16 digit tidak berubah jadi notasi ilmiah).
                Baris 2 dst. KOSONG — isi data Anda di sini.
  contoh        satu baris FIKTIF yang lolos pemeriksaan offline (--cek). Tab ini
                tidak dibaca skrip (hanya tab bernama "gabungan").
  petunjuk      penjelasan tiap kolom: wajib/opsional & isi yang diharapkan.
  Nama Wilayah  (opsional) kode + nama provinsi/kab/kec/desa. Dipakai melengkapi
                "Nama Jalan" yang kurang dari 10 huruf (lihat lengkapi_alamat).
  opsi          (tersembunyi) sumber daftar dropdown.

Jalankan ulang setiap kali KOLOM/OPSI_FORM di gabungan_loader.py berubah:
    python templates/buat_templat_agenda.py
Skrip ini juga MEMVERIFIKASI hasilnya: judul kolom harus diterima loader dan
baris contoh harus berstatus SIAP di pemeriksaan offline.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # templat tidak bergantung config lokal

import openpyxl  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from inti.gabungan_loader import (  # noqa: E402
    KOLOM, NAMA_SHEET, NILAI_TETAP, OPSI_FORM, _cari_indeks, _norm_judul, load_gabungan, periksa_semua,
)

KELUARAN = Path(__file__).resolve().parent / "Agenda.contoh.xlsx"
BARIS_DISIAPKAN = 500   # baris berformat teks + dropdown

OPSI_IS_NEW = ("Bangunan Lainnya (Selain Tempat Tinggal dan Campuran)",)

# (judul kolom persis seperti sheet asli, key loader atau None, isi contoh, penjelasan)
# Key None = kolom yang ada di sheet asli tapi tidak dibaca skrip.
KOLOM_TEMPLAT: list[tuple[str, str | None, str, str]] = [
    ("Akun PML", None, "pml.contoh@gmail.com", "Email akun Pengawas. Tidak dibaca main_gabungan (informasi)."),
    ("Akun PPL", "akun_ppl", "ppl.contoh@gmail.com", "Email akun SSO PPL yang login & membuat dokumen (mode --per-baris)."),
    ("Pilih PROVINSI", "pilih_prov", "51", "Kode provinsi 2 digit."),
    ("Pilih KABUPATEN/KOTA", "pilih_kab", "08", "Kode kab/kota 2 digit."),
    ("Pilih KECAMATAN", "pilih_kec", "080", "Kode kecamatan 3 digit."),
    ("Pilih DESA", "pilih_desa", "008", "Kode desa/kelurahan 3 digit."),
    ("Pilih SLS", "pilih_sls", "0002", "Kode SLS 4 digit."),
    ("Pilih SUBSLS", "pilih_subsls", "02", "Kode sub-SLS 2 digit. Gabungan 6 kolom Pilih harus = idsubsls."),
    ("Nama Keluarga/Bangunan/Usaha", "nama", "WARUNG CONTOH",
     "Nama usaha (tanpa nama pemilik). Nama dokumen = '<nama> (<12a>)', maks 50 karakter."),
    ("8. Apakah mengalami perubahan SLS (pemekaran/penggabungan/perubahan nama/perubahan batas?)", "ubah_sls",
     "2. Tidak", "Hanya '2. Tidak' yang didukung."),
    ("10. Kodepos", "kodepos", "81172", "Kodepos 5 digit (per desa)."),
    ("Tambah :", "is_new", OPSI_IS_NEW[0], "Hanya 'Bangunan Lainnya (...)' yang didukung."),
    ("Nama Keluarga/Bangunan/Usaha", None, "WARUNG CONTOH", "Salinan kolom nama (sheet asli punya 2 kolom identik)."),
    ("Keberadaan Bangunan Lainnya/ Usaha", "ada_bang_usaha", "2. Baru", "Hanya '2. Baru'."),
    ("Nama Jalan/Gang/Komplek/Gedung/dll (Tuliskan dengan rinci)", "jalan_domisili", "BANJAR DINAS KAJA KANGIN",
     "WAJIB. Minimal 10 huruf a-z (kalau kurang, dilengkapi nama desa/kec dari tab 'Nama Wilayah' / kolom 8c)."),
    ("Blok/Nomor Rumah", "nomor_domisili", "-", "Isi '-' kalau tidak ada nomor."),
    ("Nomor Urut Bangunan", "no_bang", "", "JANGAN diisi — skrip tidak pernah menyentuh field ini."),
    ("Kode Penggunaan Bangunan", "kode_bang", "1. Bangunan Khusus Usaha", "Kosong atau '1. Bangunan Khusus Usaha'."),
    ("Latitude", "latitude", "-8.129", "Desimal, titik sbg pemisah (mis. -8.1290)."),
    ("Longitude", "longitude", "115.200", "Desimal, titik sbg pemisah (mis. 115.2000)."),
    ("Pilih UMKM dalam satu SLS yang sama", "pilih_umkm_sls", "", "Kosong atau 'Tidak Ada'."),
    ("Keberadaan Usaha", "keberadaan_usaha", "2. Baru", "Hanya '2. Baru'."),
    ("8. b. Nama komersial usaha/perusahaan", "nama_komersial", "WARUNG CONTOH",
     "Nama komersial; ditulis '<8b> (<12a>)', maks 50 karakter."),
    ("8.c. Alamat usaha/perusahaan", "alamat_usaha_view",
     "BANJAR DINAS KAJA KANGIN, Desa/Kel. TAMBLANG, Kec. KUBUTAMBAHAN, BULELENG, BALI, 81172",
     "Informasi (form mengisinya otomatis). Pola 'Desa/Kel. X, Kec. Y, KAB, PROV' dipakai sbg cadangan nama wilayah."),
    ("Nomor HP/whatsapp", "hp", "081200000000", "WAJIB. Format teks."),
    ("8. d. Jenis kawasan beroperasi", "jenis_kawasan", "10. Di luar kawasan", "Pilih dari dropdown."),
    ("10. a. Apakah memiliki Nomor Induk Berusaha (NIB)?", "punya_nib", "2. Tidak", "Pilih dari dropdown."),
    ("10. b. Tuliskan NIB", "nib_nomor", "", "WAJIB kalau 10a = '1. Ya'. Format teks."),
    ("10. c. Apa alasan utama tidak memiliki NIB?", "tidak_nib", "3. Tidak memerlukan NIB",
     "WAJIB kalau 10a = '2. Tidak'."),
    ("11. a. Apa status badan usaha dari usaha/perusahaan ini?", "badan_usaha", "13. Bukan Badan Usaha",
     "Pilih dari dropdown. Badan usaha 1a/2-12 wajib 11d = '1. Ya'."),
    ("11. d. Apakah mempunyai laporan/catatan keuangan?", "lap_keuangan", "2. Tidak", "Pilih dari dropdown."),
    ("12. a. Nama Pengusaha / Penanggung Jawab", "pengusaha", "I KETUT CONTOH", "WAJIB."),
    ("12. b. Jenis Kelamin", "jk", "1. Laki-laki", "Pilih dari dropdown."),
    ("12. c. Umur", "umur", "45", "WAJIB, 10-99 (umur 0 ditolak form)."),
    ("12. d. Nomor Induk Kependudukan (NIK)", "nik_pengusaha", "9999", "WAJIB. Format teks."),
    ("13. a. Apa kegiatan utama usaha/perusahaan ini? Tuliskan selengkapnya", "keg_utama",
     "Menjual makanan ringan dan minuman", "WAJIB. Juga dipakai sbg 13f (produk utama)."),
    ("13. b1. Apakah memproduksi barang di lokasi ini?", "produk_sendiri", "2. Tidak", "Pilih dari dropdown."),
    ("13. b2. Apakah menyediakan layanan makan minum?", "layanan_mamin", "2. Tidak", "Pilih dari dropdown."),
    ("13. b3. Apakah melakukan penjualan barang?", "keg_penjualan", "1. Ya", "Pilih dari dropdown."),
    ("13. b4. Pilih salah satu aktivitas yang dilakukan:", "keg_jasa", "",
     "Hanya dipakai kalau 13b1, 13b2, 13b3 semuanya '2. Tidak'."),
    ("13. c. Di mana usaha tersebut biasa dilakukan?", "lokasi_usaha", "4. Toko, ruko, dan sejenisnya",
     "Pilih dari dropdown."),
    ("Pilih dari Master KBLI", "kbli", "47112", "WAJIB. Kode KBLI 5 digit."),
    ("14. a. Apa jaringan usaha dari usaha/perusahaan ini?", "jaringan", "1. Tunggal", "Pilih dari dropdown."),
    ("16. a. Apakah usaha/perusahaan ini menggunakan internet dalam menjalankan usaha?", "internet", "2. Tidak",
     "Kalau '1. Ya': 16b1-16b6 & 16c wajib, minimal satu 16b = '1. Ya'."),
    ("16. b1. Menerima pesanan barang/jasa", "internet_pesanan", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. b2. Produksi barang/jasa", "internet_produksi", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. b3. Distribusi barang/jasa", "internet_distribusi", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. b4. Membeli bahan baku online", "internet_beli", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. b5. Promosi", "internet_promosi", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. b6. Lainnya", "internet_lainnya", "", "Hanya kalau 16a = '1. Ya'."),
    ("16. c. Apakah usaha/perusahaan ini memanfaatkan teknologi digital Aritifical Intelligence (AI), Internet of "
     "Things (IoT), big data, printer 3D, blockchain, atau cloud computing?", "digital", "",
     "Hanya kalau 16a = '1. Ya'."),
    ("17. a. Apakah usaha/perusahaan ini memproduksi barang/jasa yang ramah lingkungan?", "produksi_lingkungan",
     "3. Tidak sama sekali", "Pilih dari dropdown."),
    ("17. b. Apakah usaha/perusahaan ini menggunakan input untuk tujuan perlindungan lingkungan dan/atau "
     "pembelian barang dan jasa yang ramah lingkungan?", "perlindungan_lingkungan", "2. Tidak",
     "Pilih dari dropdown."),
    ("18. Apakah usaha/perusahaan ini menggunakan produk karya seni, sastra, desain, teknologi atau warisan "
     "budaya, baik diproduksi sendiri maupun oleh pihak lain?", "produk_seni", "2. Tidak", "Pilih dari dropdown."),
    ("21. Apakah usaha/perusahaan ini bermitra dengan Koperasi Desa/Kelurahan Merah Putih (KDKMP)?",
     "mitra_kdkmp", "2. Tidak", "Pilih dari dropdown."),
    ("22. Apakah usaha/perusahaan ini terlibat dalam program Makan Bergizi Gratis (MBG)?", "peran_mbg",
     "5. Tidak terlibat MBG", "Pilih dari dropdown."),
    ("23. a. Penjualan dan/atau pembelian barang", "barang_non_pddk", "2. Tidak", "Pilih dari dropdown."),
    ("23. b. Penjualan jasa", "jasa_non_pddk", "2. Tidak", "Pilih dari dropdown."),
    ("23. c. Pembelian jasa", "beli_jasa_non_pddk", "2. Tidak", "Pilih dari dropdown."),
    ("24. a1. Pekerja laki-laki", "tk_laki", "1", "Bilangan bulat. 24a1+24b1 harus = 24a2+24b2."),
    ("24. b1. Pekerja perempuan", "tk_pr", "0", "Bilangan bulat."),
    ("24. a2. Pekerja dibayar", "tk_dibayar", "0", "Bilangan bulat."),
    ("24. b2. Pekerja tidak dibayar", "tk_tdk_dibayar", "1", "Bilangan bulat."),
    ("25. Tahun berapa usaha/perusahaan ini mulai beroperasi secara komersial?", "tahun_operasi", "2015",
     "4 digit. Tahun berjalan TIDAK didukung (form memakai rincian 30-33 bulanan)."),
    ("idsubsls", "idsubsls", "5108080008000202", "WAJIB. 16 digit, format TEKS (bukan angka)."),
    ("26. a. Total upah dan gaji, serta jaminan sosial pegawai", "gaji", "0", "Rupiah, bilangan bulat tanpa titik."),
    ("26. b. Biaya produksi", "biaya_produksi", "0", "Rupiah."),
    ("26. c. Biaya pembelian barang yang terjual", "biaya_pembelian", "4000000", "Rupiah."),
    ("26. d. Biaya operasional (air, listrik, gas, internet, pulsa, pemeliharaan, biaya angkutan, dll.)",
     "operasional", "300000", "Rupiah."),
    ("26. e. Biaya non-operasional", "non_operasional", "50000", "Rupiah. Total 26a-26e minimal 100.000."),
    ("27. a. Nilai produksi/pendapatan/penjualan barang dan jasa", "nilai_pendapatan", "6000000", "Rupiah."),
    ("27. b. Pendapatan lainnya yang dihasilkan perusahaan", "pendapatan_lain", "0",
     "Rupiah. Total 27a+27b minimal 100.000."),
    ("27. d. Berapa persentase pendapatan yang dilakukan secara online ?", "pendapatan_online", "0", "0-100."),
    ("28. a. Nilai aset tanah dan bangunan pada 31 Desember 2025", "aset_usaha_thn", "0", "Rupiah."),
    ("28. b. Nilai aset selain tanah dan bangunan pada 31 Desember 2025", "aset_lain_thn", "1500000", "Rupiah."),
    ("28. d. Berapa luas tanah yang dikuasai dan digunakan untuk kegiatan usaha pada 31 Desember 2025 ? (m2)",
     "luas_tanah_thn", "0", "m2, bilangan bulat."),
    ("29. a. Pribadi/Perorangan", "pribadi", "100", "Persen. 29a-29f harus berjumlah 100."),
    ("29. b. Lembaga Nonprofit yang Melayani Rumah Tangga", "non_profit", "0", "Persen."),
    ("29. c. Korporasi Publik", "publik", "0", "Persen."),
    ("29. d. Korporasi Non Publik", "non_publik", "0", "Persen."),
    ("29. e. Pemerintah", "pemerintah", "0", "Persen."),
    ("29. f. Asing", "asing", "0", "Persen."),
    ("Nama Pemberi Informasi", "nama_info_list", "Lainnya", "Hanya 'Lainnya'."),
]

# Kolom yang WAJIB diformat teks (kode panjang / nol di depan).
KEY_TEKS = {"pilih_prov", "pilih_kab", "pilih_kec", "pilih_desa", "pilih_sls", "pilih_subsls", "kodepos", "hp",
            "nib_nomor", "nik_pengusaha", "kbli", "idsubsls"}

WAJIB_SELALU = {
    "akun_ppl", "idsubsls", "nama", "kodepos", "latitude", "longitude", "nama_komersial", "hp", "jenis_kawasan",
    "punya_nib", "badan_usaha", "lap_keuangan", "pengusaha", "jk", "umur", "nik_pengusaha", "keg_utama",
    "produk_sendiri", "layanan_mamin", "keg_penjualan", "lokasi_usaha", "kbli", "jaringan", "internet",
    "produksi_lingkungan", "perlindungan_lingkungan", "produk_seni", "mitra_kdkmp", "peran_mbg", "barang_non_pddk",
    "jasa_non_pddk", "beli_jasa_non_pddk", "tahun_operasi", "tk_laki", "tk_pr", "tk_dibayar", "tk_tdk_dibayar",
    "gaji", "biaya_produksi", "biaya_pembelian", "operasional", "non_operasional", "nilai_pendapatan",
    "pendapatan_lain", "pendapatan_online", "aset_usaha_thn", "aset_lain_thn", "luas_tanah_thn", "pribadi",
    "non_profit", "publik", "non_publik", "pemerintah", "asing", "jalan_domisili",
}

JUDUL_WILAYAH = ["Pilih PROVINSI", "Provinsi", "Pilih KABUPATEN/KOTA", "Kabupaten/Kota", "Pilih KECAMATAN",
                 "Kecamatan", "Pilih DESA", "Desa/Kelurahan", "idsubsls"]

TEBAL = Font(bold=True)
ISI_JUDUL = PatternFill("solid", fgColor="DDEBF7")
ISI_CONTOH = PatternFill("solid", fgColor="FFF2CC")
BUNGKUS = Alignment(wrap_text=True, vertical="top")


def opsi_untuk(key: str | None) -> tuple | None:
    if key is None:
        return None
    if key == "is_new":
        return OPSI_IS_NEW
    if key in OPSI_FORM:
        return OPSI_FORM[key]
    if key in NILAI_TETAP:
        return tuple(o for o in NILAI_TETAP[key] if o)
    return None


def tulis_judul(ws, judul: list[str]):
    for c, teks in enumerate(judul, start=1):
        sel = ws.cell(row=1, column=c, value=teks)
        sel.font, sel.fill, sel.alignment = TEBAL, ISI_JUDUL, BUNGKUS
        ws.column_dimensions[get_column_letter(c)].width = 24
    ws.row_dimensions[1].height = 90
    ws.freeze_panes = "C2"


def bangun(path: Path, baris_contoh_di_gabungan: bool = False) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = NAMA_SHEET
    judul = [j for j, _, _, _ in KOLOM_TEMPLAT]
    tulis_judul(ws, judul)

    # Tab opsi (tersembunyi) + dropdown.
    wo = wb.create_sheet("opsi")
    kol_opsi = 0
    for c, (_, key, _, _) in enumerate(KOLOM_TEMPLAT, start=1):
        huruf = get_column_letter(c)
        if key in KEY_TEKS:
            for r in range(2, BARIS_DISIAPKAN + 2):
                ws.cell(row=r, column=c).number_format = "@"
        opsi = opsi_untuk(key)
        if not opsi:
            continue
        kol_opsi += 1
        ho = get_column_letter(kol_opsi)
        wo.cell(row=1, column=kol_opsi, value=key)
        for i, o in enumerate(opsi, start=2):
            wo.cell(row=i, column=kol_opsi, value=o)
        dv = DataValidation(type="list", formula1=f"=opsi!${ho}$2:${ho}${len(opsi) + 1}", allow_blank=True,
                            showErrorMessage=True, errorTitle="Opsi tidak dikenal",
                            error="Pilih salah satu opsi form (teks harus persis).")
        dv.add(f"{huruf}2:{huruf}{BARIS_DISIAPKAN + 1}")
        ws.add_data_validation(dv)
    wo.sheet_state = "hidden"

    # Tab contoh: satu baris fiktif.
    wc = wb.create_sheet("contoh")
    tulis_judul(wc, judul)
    for c, (_, key, isi, _) in enumerate(KOLOM_TEMPLAT, start=1):
        sel = wc.cell(row=2, column=c, value=isi)
        sel.fill = ISI_CONTOH
        if key in KEY_TEKS:
            sel.number_format = "@"
        if baris_contoh_di_gabungan:
            s2 = ws.cell(row=2, column=c, value=isi)
            s2.number_format = "@" if key in KEY_TEKS else "General"
    wc.cell(row=4, column=1, value="Baris kuning di atas FIKTIF — hanya contoh bentuk isian. "
                                   "Skrip hanya membaca tab 'gabungan'.").font = Font(italic=True)

    # Tab petunjuk.
    wp = wb.create_sheet("petunjuk")
    for c, (t, w) in enumerate((("No", 5), ("Judul kolom (tab gabungan)", 45), ("Key skrip", 22),
                                ("Wajib?", 14), ("Isi yang diharapkan", 60), ("Pilihan valid", 60)), start=1):
        sel = wp.cell(row=1, column=c, value=t)
        sel.font, sel.fill = TEBAL, ISI_JUDUL
        wp.column_dimensions[get_column_letter(c)].width = w
    for r, (j, key, _, ket) in enumerate(KOLOM_TEMPLAT, start=2):
        if key is None:
            wajib = "tidak dibaca"
        elif key in WAJIB_SELALU:
            wajib = "WAJIB"
        elif key in ("nib_nomor", "tidak_nib", "keg_jasa") or key.startswith("internet_") or key == "digital":
            wajib = "bersyarat"
        else:
            wajib = "opsional"
        opsi = opsi_untuk(key)
        for c, v in enumerate((r - 1, j, key or "-", wajib, ket, "\n".join(opsi) if opsi else ""), start=1):
            wp.cell(row=r, column=c, value=v).alignment = BUNGKUS
    catatan = len(KOLOM_TEMPLAT) + 3
    for i, t in enumerate((
        "Cara pakai: isi tab 'gabungan' mulai baris 2 (satu baris = satu usaha/dokumen). Nilai = jawaban FINAL "
        "per rincian form (tidak ada kalkulasi 10%).",
        "Teks opsi harus PERSIS seperti di dropdown (termasuk nomor & titik), mis. '2. Tidak'.",
        "Kolom kode (idsubsls, kodepos, NIK, HP, KBLI) berformat TEKS; jangan diubah ke angka.",
        "Periksa tanpa browser: python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --cek",
        "Google Sheets: File > Import > unggah file ini, lalu File > Download > .xlsx setelah diisi.",
    )):
        wp.cell(row=catatan + i, column=2, value=t).alignment = Alignment(wrap_text=False)

    # Tab Nama Wilayah (opsional).
    ww = wb.create_sheet("Nama Wilayah")
    tulis_judul(ww, JUDUL_WILAYAH)
    ww.row_dimensions[1].height = 30
    for c in range(1, len(JUDUL_WILAYAH) + 1):
        for r in range(2, BARIS_DISIAPKAN + 2):
            ww.cell(row=r, column=c).number_format = "@"

    urutan = ["petunjuk", NAMA_SHEET, "contoh", "Nama Wilayah", "opsi"]
    wb._sheets = [wb[n] for n in urutan]
    wb.active = urutan.index(NAMA_SHEET)
    wb.save(path)


def verifikasi() -> None:
    """Judul diterima loader & baris contoh SIAP di pemeriksaan offline."""
    judul = [j for j, _, _, _ in KOLOM_TEMPLAT]
    idx = _cari_indeks(judul)
    for key, i in idx.items():
        k_templat = KOLOM_TEMPLAT[i][1]
        assert k_templat == key or (key == "nama" and k_templat == "nama"), (key, judul[i])
    hilang = set(KOLOM) - set(idx)
    assert hilang <= {"produk"}, hilang
    assert all(_norm_judul(j) for j in judul)
    with tempfile.TemporaryDirectory() as tmp:
        uji = Path(tmp) / "uji.xlsx"
        bangun(uji, baris_contoh_di_gabungan=True)
        rows = load_gabungan(uji)
        assert len(rows) == 1, len(rows)
        hasil = periksa_semua(rows, mode_satu_subsls=True)[rows[0].baris]
        assert hasil.status == "SIAP", (hasil.status, hasil.pesan)
        print(f"  baris contoh: {hasil.status}; nama dokumen '{rows[0].nama_dokumen}'")


def main() -> int:
    verifikasi()
    bangun(KELUARAN)
    print(f"Ditulis: {KELUARAN} ({len(KOLOM_TEMPLAT)} kolom, tab gabungan kosong)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
