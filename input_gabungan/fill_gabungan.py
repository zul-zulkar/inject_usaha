"""
fill_gabungan.py — Isi SE2026-L BLOK II dari SATU baris format standar
(input_usaha.xlsx, tab "input_usaha") — berlaku utk jenis usaha apa pun.

Padanan fill_blok2.py utk sumber gabungan. Urutan & penjagaan field
bersyarat SENGAJA sama (alasannya dicatat panjang di fill_blok2.py):
pilih_umkm_sls sebelum keberadaan_usaha, 13b4 setelah KBLI,
blok finansial baru dirender setelah rincian 25 di-blur.

Bedanya: nilai diambil APA ADANYA dari sheet. Tidak ada 10%, tidak ada
aturan pekerja <=3, tidak ada override aset/luas tanah = 0 — sheet ini sudah
berisi jawaban final per rincian. Default config HANYA dipakai utk rincian
19/20 kalau kolom opsionalnya kosong/tidak ada, dan setiap pemakaiannya
dikembalikan sbg daftar ASUMSI supaya masuk kolom review_disarankan. Rincian
bersyarat yang WAJIB tapi tidak ada nilainya (13d/13e, 19b) -> BarisPerluManual,
tidak ditebak.
"""

from __future__ import annotations

from inti.config import (
    DEFAULT_19A, DEFAULT_19C, DEFAULT_20B_VARIAN_SUDAH_BPOM, DEFAULT_20C_VARIAN_BELUM_BPOM,
    ISI_PILIH_UMKM_SLS, MIN_KARAKTER_13A, OPSI_13B4_JASA, OPSI_13B4_PERTANIAN, TAHAP2_BULAN_OPERASI,
    UMKM_SATU_SLS_KANDIDAT,
)
from inti.fasih_web import FasihWebSession, FieldNotFound
from inti.fill_blok2 import read_kategori_lapangan_usaha
from inti.gabungan_loader import (
    KEY_16B, KEY_26, KEY_29, KEY_PEKERJA, OPSI_FORM, GabunganRow, judul_dari_opsi_kbli, kbli_kategori_ditolak,
    lengkapi_13a,
)


class BarisPerluManual(RuntimeError):
    """Form meminta sesuatu yang tidak bisa dipenuhi sheet apa adanya.
    main_gabungan.py mencatatnya sbg SKIP_<kode> (isi manual), bukan ERROR."""

    def __init__(self, kode: str, pesan: str):
        super().__init__(pesan)
        self.kode = kode


# Varian bulanan (30-33): dataKey tujuan (key DK) utk tiap kolom 26-29 sheet —
# dari template 2026-09-22 (label "30. a." .. "33. f.").
PETA_BULANAN_30 = (("gaji", "gaji_bln"), ("biaya_produksi", "biaya_produksi_bln"),
                   ("biaya_pembelian", "biaya_pembelian_bln"), ("operasional", "operasional_bln"),
                   ("non_operasional", "non_operasional_bln"))
PETA_BULANAN_32 = (("aset_usaha_thn", "aset_tanah_bln"), ("aset_lain_thn", "aset_lain_bln"),
                   ("luas_tanah_thn", "luas_tanah_bln"))
PETA_BULANAN_33 = dict(zip(KEY_29, ("pribadi_didirikan", "nonprofit_didirikan", "korporasi_publik_didirikan",
                                    "korporasi_nonpublik_didirikan", "pemerintah_didirikan", "asing_didirikan")))


def isi_13de(sess: FasihWebSession, row: GabunganRow, judul_kbli: str = "") -> None:
    """13d/13e (input & proses produksi) muncul kalau 13b1 = Ya. dataKey sisi
    fasih-web belum terpetakan -> dicari lewat label (sama dgn fill_blok2).
    Kolom sheet kosong: baris tahap 2 yang 13b-nya baru disesuaikan dgn KBLI GenAI
    memakai judul KBLI terpilih (TAHAP2_13DE_DARI_KBLI); selain itu berhenti."""
    for pola, key, nama in ((r"^13\.\s*d\.", "input_produksi", "13d"),
                            (r"^13\.\s*e\.", "proses_produksi", "13e")):
        if not sess.datakey_by_label(pola):
            continue
        nilai = row[key]
        if not nilai and judul_kbli and row.b13_dari_kbli:
            from inti.config import TAHAP2_13DE_DARI_KBLI
            from inti.tahap2_loader import isian_13de_dari_kbli
            if TAHAP2_13DE_DARI_KBLI:
                nilai = isian_13de_dari_kbli(judul_kbli, row["keg_utama"])[0 if key == "input_produksi" else 1]
        if not nilai:
            raise BarisPerluManual("13DE_KOSONG", f"{nama} dirender tapi kolom '{nama}' di sheet kosong.")
        sess.isi_bersyarat_by_label(pola, nilai, nama)


def pilih_kbli_genai(sess: FasihWebSession, row: GabunganRow, asumsi: list[str]) -> str:
    """13g utk KBLI sheet yang ditolak form (kategori P/U): rekomendasi GenAI
    pertama (KBLI_DITOLAK_PAKAI_GENAI) -> judul KBLI terpilih.

    Baris tahap 2 menurunkan 13b1-b3 dari golongan KBLI SHEET — yang salah itu.
    Radio 13b ada DI ATAS 13g, jadi 13b disamakan dgn golongan KBLI terpilih
    SESUDAHNYA; perubahan 13b bisa me-reset 13g, maka rekomendasi dipilih ulang
    (sekali). Masih tidak sejalan -> BarisPerluManual, tidak ditebak lagi."""
    from inti.tahap2_loader import rencana_13b
    kode, kategori, label = sess.pilih_kbli_genai_pertama()
    asumsi.append(f"KBLI sheet {row['kbli']} (kategori {kbli_kategori_ditolak(row['kbli'])}) ditolak form -> "
                  f"13g rekomendasi GenAI: {label[:90]}")
    if not row.b13_dari_kbli:
        return judul_dari_opsi_kbli(label)
    sekarang = {k: row[k] for k in ("produk_sendiri", "layanan_mamin", "keg_penjualan")}
    for percobaan in (1, 2):
        target = rencana_13b(kode)
        beda = [k for k in target if target[k] != sekarang[k]]
        if not beda:
            return judul_dari_opsi_kbli(label)
        if percobaan == 2:
            raise BarisPerluManual("KBLI_GENAI_13B_BEDA",
                                   f"13b tidak sejalan dgn KBLI GenAI {kode} setelah disesuaikan: {beda}")
        for k in beda:
            if sess.komponen_ada(k, timeout_ms=4000):
                sess.select_radio_by_datakey(k, target[k])
            sekarang[k] = target[k]
        asumsi.append(f"13b disesuaikan dgn golongan KBLI GenAI {kode}: "
                      + ", ".join(f"{k} {target[k]}" for k in beda))
        kode, kategori, label = sess.pilih_kbli_genai_pertama()
    return judul_dari_opsi_kbli(label)


def gabung_26c_ke_26b(row: GabunganRow, asumsi: list[str]) -> None:
    """26c/30c tidak dirender untuk KBLI yang baru diketahui saat pengisian (13g
    GenAI) -> 26c dijumlahkan ke 26b, sama dgn TAHAP2_26C_KE_26B yang dilakukan
    loader utk KBLI sheet. row.v diubah (pengisian ulang tidak menjumlah dua kali)."""
    b, c = row.angka("biaya_produksi"), row.angka("biaya_pembelian")
    row.v["biaya_produksi"], row.v["biaya_pembelian"] = str(b + c), "0"
    asumsi.append(f"26c {c:,} tidak dirender utk KBLI GenAI -> dijumlahkan ke 26b ({b:,} -> {b + c:,})")


def isi_varian_bulanan(sess: FasihWebSession, row: GabunganRow, asumsi: list[str]) -> None:
    """Rincian 30-33 (usaha mulai beroperasi tahun berjalan) diisi dari kolom
    26-29 sheet APA ADANYA — ketetapan user 2026-09-22: kuesioner kertas tahap 2
    menanyakan versi bulanan dgn kolom yang sama. 31e "bulan beroperasi" hanya
    mencentang TAHAP2_BULAN_OPERASI (AGUSTUS). Hanya utk baris yang
    `bulanan_dari_kolom` (format tahap 2); format standar tetap berhenti."""
    log = sess._log
    if not sess.komponen_ada("biaya_pembelian_bln", timeout_ms=4000) and row.angka("biaya_pembelian") > 0:
        if row.kbli_genai and row.pindah_26c_ke_26b:
            gabung_26c_ke_26b(row, asumsi)
    if not sess.komponen_ada("biaya_pembelian_bln", timeout_ms=1000) and row.angka("biaya_pembelian") > 0:
        raise BarisPerluManual(
            "26C_TIDAK_DIRENDER",
            f"30c tidak dirender utk KBLI {row['kbli']} padahal sheet 26c={row['biaya_pembelian']}.")
    for src, dst in PETA_BULANAN_30:
        if dst == "biaya_pembelian_bln" and not sess.komponen_ada(dst, timeout_ms=1000):
            continue
        sess.fill_by_datakey(dst, row[src])
    log(f"30f total pengeluaran SEBULAN (sheet) = {sum(row.angka(k) for k in KEY_26):,}")
    sess.fill_by_datakey("nilai_pendapatan_bln", row["nilai_pendapatan"])
    sess.fill_by_datakey("pendapatan_lain_bln", row["pendapatan_lain"])
    if sess.komponen_ada("pendapatan_online_bln", timeout_ms=4000):
        sess.fill_by_datakey("pendapatan_online_bln", row["pendapatan_online"])
    else:
        log("31d (persentase pendapatan online) tidak dirender — dilewati.")
    for bulan in TAHAP2_BULAN_OPERASI:
        sess.centang_teks_dalam_komponen("bulan_operasi", bulan)
    for src, dst in PETA_BULANAN_32:
        sess.fill_by_datakey(dst, row[src])
    if sess.komponen_ada("pribadi_didirikan", timeout_ms=8_000):
        for src in KEY_29:
            sess.fill_by_datakey(PETA_BULANAN_33[src], row[src])
    else:
        log("Rincian 33 (kepemilikan modal saat didirikan) tidak dirender — dilewati.")
    asumsi.append(f"varian bulanan: 30-33 diisi dari kolom 26-29, 31e = {'/'.join(TAHAP2_BULAN_OPERASI)}")


def fill_blok2_gabungan(sess: FasihWebSession, row: GabunganRow) -> list[str]:
    """Isi BLOK II. Return daftar ASUMSI (nilai yang BUKAN dari sheet)."""
    log = sess._log
    asumsi: list[str] = []
    log(f"Isi BLOK II dari sheet gabungan (baris {row.baris}) ...")

    # --- 8a-8d ---------------------------------------------------------
    # pilih_umkm_sls HILANG dari DOM begitu keberadaan_usaha dijawab, jadi
    # wajib lebih dulu (radio tidak bisa di-unset, jadi tidak ada jalan kembali).
    if ISI_PILIH_UMKM_SLS and sess.komponen_ada("pilih_umkm_sls", timeout_ms=4000):
        if row.murni:
            if not row["pilih_umkm_sls"]:
                raise BarisPerluManual("UMKM_SLS_KOSONG",
                                       "'Pilih UMKM dalam satu SLS yang sama' dirender tapi kolomnya kosong di sheet.")
            kandidat = (row["pilih_umkm_sls"],)
        else:
            kandidat = tuple(dict.fromkeys(filter(None, (row["pilih_umkm_sls"], *UMKM_SATU_SLS_KANDIDAT))))
        sess.pilih_combobox_pertama_yang_cocok("pilih_umkm_sls", kandidat)
    else:
        log("'Pilih UMKM dalam satu SLS yang sama' tidak dirender — dilewati.")

    sess.select_radio_by_datakey("keberadaan_usaha", row["keberadaan_usaha"])
    sess.fill_by_datakey("nama_komersial", row.nama_komersial)  # "<8b> (<12a>)"
    sess.fill_by_datakey("hp", row["hp"])
    sess.select_radio_by_datakey("jenis_kawasan", row["jenis_kawasan"])

    # --- 10 NIB ---------------------------------------------------------
    sess.select_radio_by_datakey("punya_nib", row["punya_nib"])
    if row["punya_nib"].startswith("1"):
        if not sess.komponen_ada("nib_nomor"):
            raise BarisPerluManual("10B_TIDAK_DIRENDER", "10a = Ya tapi field 10b (Tuliskan NIB) tidak dirender.")
        sess.fill_by_datakey("nib_nomor", row["nib_nomor"])
    elif sess.komponen_ada("tidak_nib"):
        sess.select_radio_by_datakey("tidak_nib", row["tidak_nib"])
    else:
        log("10c (alasan tanpa NIB) tidak dirender — dilewati.")

    # --- 11-12 ----------------------------------------------------------
    sess.select_radio_by_datakey("badan_usaha", row["badan_usaha"])
    sess.select_radio_by_datakey("lap_keuangan", row["lap_keuangan"])
    sess.fill_by_datakey("pengusaha", row["pengusaha"])
    sess.select_radio_by_datakey("jk", row["jk"])
    sess.fill_by_datakey("umur", row["umur"])
    sess.fill_by_datakey("nik_pengusaha", row["nik_pengusaha"])

    # --- 13 -------------------------------------------------------------
    # 13a < 15 karakter ditolak form -> diisi SETELAH KBLI terpilih, dilengkapi
    # judul KBLI-nya (LENGKAPI_13A_DGN_KBLI). Aman: field KBLI hanya bergantung
    # pada radio 13g, bukan pada 13a (enableCondition template, 2026-09-22).
    keg = " ".join(row["keg_utama"].split())
    keg_pendek = len(keg) < MIN_KARAKTER_13A
    if keg_pendek:
        log(f"13a '{keg}' < {MIN_KARAKTER_13A} karakter — diisi SETELAH KBLI, dilengkapi judul KBLI.")
    else:
        sess.fill_by_datakey("keg_utama", row["keg_utama"])
    # 13b1-b3 per-dataKey: opsinya berteks identik ("1. Ya"/"2. Tidak").
    for key in ("produk_sendiri", "layanan_mamin", "keg_penjualan"):
        if not sess.komponen_ada(key):
            log(f"{key} tidak dirender di form ini — dilewati.")
            continue
        sess.select_radio_by_datakey(key, row[key])
    if sess.komponen_ada("lokasi_usaha"):
        sess.select_radio_by_datakey("lokasi_usaha", row["lokasi_usaha"])
    else:
        log("13c (tempat usaha) tidak dirender — dilewati.")
    sess.fill_by_datakey("produk", row.produk_utama)
    if not row["produk"] and row.produk_utama:
        asumsi.append("13f disalin dari 13a")

    # 13d/13e (input & proses produksi) muncul kalau 13b1 = Ya.
    isi_13de(sess, row)

    # 13g KBLI. Frasa cadangan = 13a; pilih() tetap memverifikasi KODE ada
    # di teks opsi sebelum mengklik, jadi frasa ini tidak bisa salah pilih.
    # KBLI sheet kategori P/U (ditolak form) -> rekomendasi GenAI pertama.
    judul_genai = ""
    if row.kbli_genai:
        judul_genai = pilih_kbli_genai(sess, row, asumsi)
        isi_13de(sess, row, judul_genai)   # 13b1 bisa baru jadi Ya
    else:
        sess.fill_kbli_master(row["kbli"], search_phrase_fallback=row["keg_utama"])
    sess.page.wait_for_timeout(500)
    kategori = read_kategori_lapangan_usaha(sess.page)
    log(f"13h Kategori Lapangan Usaha (auto) = '{kategori}'")

    if keg_pendek:
        judul = row.judul_kbli or judul_genai or sess.judul_kbli_terpilih()
        baru = "" if row.murni else lengkapi_13a(keg, judul)
        if len(baru) < MIN_KARAKTER_13A:
            raise BarisPerluManual("13A_KURANG_15_KARAKTER",
                                   f"13a '{keg}' < {MIN_KARAKTER_13A} karakter & tidak bisa dilengkapi judul KBLI "
                                   f"('{judul}') — perbaiki 13a di sheet.")
        sess.fill_by_datakey("keg_utama", baru)
        asumsi.append(f"13a '{keg}' dilengkapi judul KBLI -> '{baru}'")

    # 13b4 diisi SETELAH KBLI (sama dgn fill_blok2): baru ter-render kalau
    # 13b1-b3 semuanya Tidak, dan cadangannya diturunkan dari kategori 13h.
    if sess.komponen_ada("keg_jasa", timeout_ms=4000):
        pilihan = row["keg_jasa"]
        if pilihan not in OPSI_FORM["keg_jasa"] and row.murni:
            raise BarisPerluManual("13B4_KOSONG", f"13b4 dirender tapi kolom 13b4 sheet '{pilihan}' bukan opsi form.")
        if pilihan not in OPSI_FORM["keg_jasa"]:
            pilihan = OPSI_13B4_PERTANIAN if kategori.strip().upper() == "A" else OPSI_13B4_JASA
            asumsi.append(f"13b4 sheet '{row['keg_jasa']}' bukan opsi -> '{pilihan}' dari kategori {kategori}")
        sess.select_radio_by_datakey("keg_jasa", pilihan)

    sess.select_radio_by_datakey("jaringan", row["jaringan"])

    # --- 16-18 ----------------------------------------------------------
    sess.select_radio_by_datakey("internet", row["internet"])
    if row["internet"].startswith("1"):
        for key in KEY_16B:
            if sess.komponen_ada(key, timeout_ms=4000):
                sess.select_radio_by_datakey(key, row[key])
            else:
                log(f"{key} (16b) tidak dirender — dilewati.")
        if sess.komponen_ada("digital", timeout_ms=4000):
            sess.select_radio_by_datakey("digital", row["digital"])
    for key in ("produksi_lingkungan", "perlindungan_lingkungan", "produk_seni"):
        sess.select_radio_by_datakey(key, row[key])

    # --- 19 (halal BPJPH) & 20 (izin edar BPOM): hanya dirender utk kategori
    # tertentu. Kolom opsional sheet dipakai kalau terisi; kosong -> default
    # config & dicatat ASUMSI. 19a dijawab dulu (19b/19c baru muncul sesudahnya).
    def _perlu_nilai(key: str, nama: str):
        if row.murni and not row[key]:
            raise BarisPerluManual("19_20_KOSONG", f"{nama} dirender tapi kolom {nama} sheet kosong "
                                                   "(mode murni: tanpa default).")

    def _isi_label(pola: str, key: str, bawaan: str, nama: str) -> bool:
        if sess.datakey_by_label(pola):
            _perlu_nilai(key, nama)
        nilai = row[key] or bawaan
        diisi = sess.isi_bersyarat_by_label(pola, nilai, nama)
        if diisi and not row[key]:
            asumsi.append(f"{nama} default '{bawaan}'")
        return diisi

    if _isi_label(r"^19\.\s*a\.", "halal", DEFAULT_19A, "19a"):
        sess.page.wait_for_timeout(800)  # datakey_by_label snapshot: beri waktu 19b/19c ter-render
    if sess.datakey_by_label(r"^19\.\s*b\."):
        if not row["sudah_halal"]:
            raise BarisPerluManual("19B_KOSONG", "19b dirender tapi kolom '19b' di sheet kosong.")
        sess.isi_bersyarat_by_label(r"^19\.\s*b\.", row["sudah_halal"], "19b")
    _isi_label(r"^19\.\s*c\.", "belum_halal", DEFAULT_19C, "19c")

    if sess.komponen_ada("izin_edar_bpom"):
        _perlu_nilai("izin_edar", "20a")
        sess.select_radio_by_datakey("izin_edar_bpom", row["izin_edar"] or "3. Tidak")
        if not row["izin_edar"]:
            asumsi.append("20a default '3. Tidak'")
        if sess.datakey_by_label(r"^20\.\s*b\."):
            _isi_label(r"^20\.\s*b\.", "sudah_bpom", DEFAULT_20B_VARIAN_SUDAH_BPOM, "20b")
        # 20c wajib di SEMUA cabang jawaban 20a (lihat fill_blok2).
        if sess.komponen_ada("jumlah_varian_belum_bpom"):
            _perlu_nilai("belum_bpom", "20c")
            sess.fill_by_datakey("jumlah_varian_belum_bpom", row["belum_bpom"] or DEFAULT_20C_VARIAN_BELUM_BPOM)
            if not row["belum_bpom"]:
                asumsi.append(f"20c default '{DEFAULT_20C_VARIAN_BELUM_BPOM}'")
    else:
        log("Rincian 20 (BPOM) tidak dirender utk kategori ini — dilewati.")

    # --- 21-25 ----------------------------------------------------------
    sess.select_radio_by_datakey("mitra_kdkmp", row["mitra_kdkmp"])
    sess.select_radio_by_datakey("peran_mbg", row["peran_mbg"])
    for key in ("barang_non_pddk", "jasa_non_pddk", "beli_jasa_non_pddk"):
        sess.select_radio_by_datakey(key, row[key])
    for key in KEY_PEKERJA:
        sess.fill_by_datakey(key, row[key])
    sess.fill_by_datakey("tahun_operasi", row["tahun_operasi"])

    # --- 26-29 ----------------------------------------------------------
    # Blok finansial baru selesai dirender setelah rincian 25 di-blur; saat
    # server lambat perlu ditunggu (record 2566 & 2571, lihat fill_blok2).
    def _deteksi_varian():
        if sess.komponen_ada("upah_gaji", timeout_ms=20_000):
            return "tahunan"
        if sess.komponen_ada("gaji_bln", timeout_ms=6_000):
            return "bulanan"
        return None

    sess.page.keyboard.press("Tab")
    sess.page.wait_for_timeout(1500)
    varian = _deteksi_varian()
    if varian is None:
        sess.page.keyboard.press("Tab")
        sess.page.wait_for_timeout(3000)
        varian = _deteksi_varian()
    if varian is None:
        raise FieldNotFound(f"Blok finansial (26-29) tidak dirender (tahun_operasi={row['tahun_operasi']}).")
    if varian == "bulanan":
        if not row.bulanan_dari_kolom:
            raise BarisPerluManual(
                "VARIAN_BULANAN",
                f"Form memakai rincian 30-33 (angka SATU BULAN) utk tahun_operasi={row['tahun_operasi']}; "
                "angka sheet tahunan — isi manual.")
        isi_varian_bulanan(sess, row, asumsi)
        sess.dump("blok2_gabungan_selesai_terisi")
        log("BLOK II (varian bulanan) selesai diisi." + (f" ASUMSI: {asumsi}" if asumsi else ""))
        return asumsi

    if (row.kbli_genai and row.pindah_26c_ke_26b and row.angka("biaya_pembelian") > 0
            and not sess.komponen_ada("biaya_pembelian")):
        gabung_26c_ke_26b(row, asumsi)
    if not sess.komponen_ada("biaya_pembelian") and row.angka("biaya_pembelian") > 0:
        # Kategori B-F & I gol.56 tidak punya 26c terpisah. Menggabungkannya
        # ke 26b adalah keputusan data, bukan urusan skrip — berhenti.
        raise BarisPerluManual(
            "26C_TIDAK_DIRENDER",
            f"26c tidak dirender utk KBLI {row['kbli']} padahal sheet 26c={row['biaya_pembelian']}.")
    for key in KEY_26:
        if key == "biaya_pembelian" and not sess.komponen_ada(key, timeout_ms=1000):
            continue
        sess.fill_by_datakey(key, row[key])
    log(f"26f total pengeluaran (sheet) = {sum(row.angka(k) for k in KEY_26):,}")

    sess.fill_by_datakey("nilai_pendapatan", row["nilai_pendapatan"])
    sess.fill_by_datakey("pendapatan_lain", row["pendapatan_lain"])
    if sess.komponen_ada("pendapatan_online", timeout_ms=4000):
        sess.fill_by_datakey("pendapatan_online", row["pendapatan_online"])
    else:
        log("27d (persentase pendapatan online) tidak dirender — dilewati.")

    # Nama dataKey 28 menyesatkan: aset_usaha_thn = 28a TANAH & BANGUNAN,
    # aset_lain_thn = 28b SELAIN tanah & bangunan. Kolom sheet dipetakan
    # lewat awalan "28. a." / "28. b.", jadi sudah sesuai label.
    for key in ("aset_usaha_thn", "aset_lain_thn", "luas_tanah_thn"):
        sess.fill_by_datakey(key, row[key])

    if sess.komponen_ada("pribadi", timeout_ms=8_000):
        for key in KEY_29:
            sess.fill_by_datakey(key, row[key])
    else:
        log("Rincian 29 (kepemilikan modal) tidak dirender — dilewati.")

    sess.dump("blok2_gabungan_selesai_terisi")
    log("BLOK II selesai diisi." + (f" ASUMSI: {asumsi}" if asumsi else ""))
    return asumsi
