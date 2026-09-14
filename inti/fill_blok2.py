"""
fill_blok2.py — Pemetaan data (BacklogRow + SourceBlok2 hasil scrape) ke
field-field SE2026-L BLOK II di fasih-web, termasuk semua logika kondisional
yg terdokumentasi (26c/rincian 20 tergantung kategori KBLI HASIL PILIHAN,
bukan kategori sumber — dideteksi dari DOM, bukan ditebak dari tabel).

⚠️ CATATAN PENTING SOAL SUMBER ANGKA rincian 28b & rincian 29:
- 28b (aset selain tanah&bangunan) diasumsikan = kolom sheet
  'aset_lain_thn' × 10%. Pemetaan ini BELUM pernah eksplisit dikonfirmasi
  di 3 record manual (nilainya cocok scr kebetulan/logis, tapi TIDAK
  divalidasi silang saat itu). WAJIB divalidasi: jalankan script dgn
  --dry-run terhadap salah satu dari 3 record yang SUDAH diketahui hasil
  akhirnya (lihat catatan-usaha-pecahan-se2026.md), lalu bandingkan angka
  yg dihasilkan script vs angka yg didokumentasikan.
- 29 (kepemilikan modal) TERNYATA ADA di sumber fasih-sm (field
  pribadi/non_profit/publik/non_publik/pemerintah/asing per-usaha) —
  lihat export_source.py & PANDUAN_EKSPOR_MANUAL.md. Diambil dari
  `src.kepemilikan_modal` kalau tersedia (ekspor lewat export_source.py),
  fallback ke `KEPEMILIKAN_MODAL_DEFAULT` (100% Pribadi) HANYA kalau
  sumbernya kosong/tidak ada (mis. jalur live-scrape lama yang belum
  mengisi field ini).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from playwright.sync_api import Page

from inti.config import (
    DEFAULT_10C_ALASAN_TANPA_NIB, DEFAULT_13C_TEMPAT_USAHA,
    DEFAULT_13B_KALAU_SUMBER_KOSONG, DEFAULT_16B_TUJUAN_INTERNET,
    DEFAULT_16C_TEKNOLOGI_DIGITAL, DEFAULT_20B_VARIAN_SUDAH_BPOM,
    DEFAULT_19A, DEFAULT_19C, DEFAULT_20C_VARIAN_BELUM_BPOM,
    DEFAULT_27D_PERSEN_PENDAPATAN_ONLINE, ISI_PILIH_UMKM_SLS,
    BULAN_NAMA, MINIMAL_TOTAL_RUPIAH_BULANAN,
    OPSI_13B4_JASA, OPSI_13B4_PERTANIAN,
    UMKM_SATU_SLS_KANDIDAT,
    NAMA_PEMBERI_INFORMASI,
    ASET_TANAH_OVERRIDE, KEPEMILIKAN_MODAL_DEFAULT, LUAS_TANAH_OVERRIDE,
    L, NIK_OVERRIDE, UMKM_SATU_SLS,
)
from inti.data_loader import (
    BacklogRow, rencana_pekerja, rencana_pendapatan, rencana_pengeluaran, rupiah10,
)
from inti.fasih_web import FasihWebSession
from inti.scrape_source import SourceBlok2


def read_kategori_lapangan_usaha(page: Page) -> str:
    """Baca field readonly '13.h Kategori Lapangan Usaha' (auto-terisi
    begitu KBLI dipilih) — dipakai sbg SINYAL tambahan, bukan satu2nya
    dasar keputusan (deteksi keberadaan field pakai FasihWebSession.komponen_ada())."""
    try:
        lbl = page.get_by_text(L["kategori_lapangan_usaha"], exact=False).first
        val_el = lbl.locator("xpath=following::input[1]")
        return (val_el.input_value() or "").strip()
    except Exception:
        return ""


def fill_blok2(sess: FasihWebSession, row: BacklogRow, src: SourceBlok2, kbli_name_hint: str = ""):
    page = sess.page
    log = sess._log

    log("Isi BLOK II ...")

    # --- Identitas usaha ---
    # Urutan penting: rincian selanjutnya di BLOK II baru dirender setelah
    # "Keberadaan Usaha" dijawab (pertanyaan bersyarat).
    # Catatan: field "Pilih UMKM dalam satu SLS yang sama" (aturan #8 di
    # catatan proyek, nilai UMKM_SATU_SLS="Tidak ada") TIDAK dirender di alur
    # dokumen "Bangunan Lainnya" — tidak muncul di satu pun dump, dan
    # ringkasan pra-Kirim GALAT=0 tanpa mengisinya. Kalau suatu saat muncul,
    # petakan dataKey-nya lalu pakai pilih_combobox_by_datakey().
    # ⚠️ URUTAN PENTING — "Pilih UMKM dalam satu SLS yang sama" harus lebih
    # dulu. Combobox ini cuma dirender di SLS yang punya daftar UMKM prelist,
    # dan HILANG dari DOM begitu keberadaan_usaha dijawab "2. Baru" — padahal
    # validator ringkasan TETAP menagihnya sbg "Wajib diisi" (persis yang
    # bikin record 2521 GALAT=9 pada 2026-09-06). Kalau tidak dirender sama
    # sekali (mis. record 2513), langkah ini dilewati.
    if not ISI_PILIH_UMKM_SLS:
        log("'Pilih UMKM dalam satu SLS yang sama' sengaja DIKOSONGKAN "
            "(ketetapan user 2026-09-06; record 2521 lolos GALAT=0 tanpa itu).")
    elif sess.komponen_ada("pilih_umkm_sls", timeout_ms=4000):
        sess.pilih_combobox_pertama_yang_cocok("pilih_umkm_sls", UMKM_SATU_SLS_KANDIDAT)
    else:
        log("'Pilih UMKM dalam satu SLS yang sama' tidak dirender — dilewati. "
            "Normal kalau SLS ini memang tidak punya daftar UMKM prelist (mis. record 2513), "
            "ATAU kalau ini pengisian ulang dokumen yang keberadaan_usaha-nya sudah terjawab.")

    sess.select_radio_by_datakey("keberadaan_usaha", L["opsi_baru"])
    sess.fill_by_datakey("nama_komersial", src.nama_komersial or row.nama_usaha_di_keluarga)

    # 8c Alamat: NAMA JALAN biasanya sudah auto-terisi dari SE2026-P — cukup
    # lengkapi RT/RW/No HP kalau field masih editable & belum terisi.
    if src.rt:
        sess.fill_by_datakey("rt", src.rt)
    if src.rw:
        sess.fill_by_datakey("rw", src.rw)
    if src.no_hp_wa:
        sess.fill_by_datakey("no_hp_wa", src.no_hp_wa)

    sess.select_radio_by_datakey("jenis_kawasan", L["opsi_luar_kawasan"])

    # rincian 9 (Jenis usaha) HANYA muncul di alur "Keluarga", TIDAK muncul
    # di alur "Bangunan Lainnya" yg dipakai skrip ini (terverifikasi di 3
    # record manual) — sengaja tidak diisi.

    sess.select_radio_by_datakey("nib", "2. Tidak")
    # 10c "alasan tidak punya NIB" — bersyarat & dataKey-nya belum terpetakan.
    # Dilewati kalau tidak dirender; kalau memang wajib, akan ketahuan sbg
    # GALAT di ringkasan pra-Kirim (bukan diam-diam salah isi).
    if sess.komponen_ada("alasan_tanpa_nib"):
        sess.select_radio_by_datakey("alasan_tanpa_nib", DEFAULT_10C_ALASAN_TANPA_NIB)
    else:
        log("10c (alasan tanpa NIB) tidak dirender — dilewati.")
    sess.select_radio_by_datakey("status_badan_usaha", L["opsi_bukan_badan_usaha"])
    sess.select_radio_by_datakey("laporan_keuangan", "2. Tidak")

    # 12a — SALIN PERSIS dari field sumber (BUKAN dari roster/kolom P kalau beda ejaan)
    sess.fill_by_datakey("nama_pengusaha", src.nama_pengusaha or row.nama_usaha_di_keluarga)
    if src.jenis_kelamin:
        sess.select_radio_by_datakey("jenis_kelamin", src.jenis_kelamin)
    if src.umur:
        sess.fill_by_datakey("umur", src.umur)
    sess.fill_by_datakey("nik", NIK_OVERRIDE)  # override tetap, abaikan sumber

    sess.fill_by_datakey("kegiatan_utama", src.kegiatan_utama)
    # Rincian 13b1/13b2/13b3. WAJIB per-dataKey: ketiganya punya opsi teks
    # identik ("1. Ya"/"2. Tidak"), jadi pencarian berbasis teks global pasti
    # mengklik pertanyaan yang salah. 13b3 tidak dirender di semua alur.
    for key, val in (
        ("produksi_di_lokasi", src.b1_produksi_lokasi),
        ("layanan_makan_minum", src.b2_layanan_makan_minum),
        ("penjualan_barang", src.b3_penjualan_barang),
    ):
        if not val:
            # Form mewajibkan 13b1-b3; kalau export tidak punya nilainya sama
            # sekali, dilewati = GALAT pasti (record 2553 & 2604). Pakai
            # default yang ditetapkan di config — ASUMSI, bukan data sumber.
            val = DEFAULT_13B_KALAU_SUMBER_KOSONG
            log(f"⚠️ {key} kosong di export -> pakai default '{val}' (ASUMSI, tinjau manual).")
        if not sess.komponen_ada(key):
            log(f"{key} tidak dirender di form ini — dilewati.")
            continue
        sess.select_radio_by_datakey(key, val)
    # 13c bersyarat (tidak dirender di semua alur). Nilai sumber diutamakan;
    # kalau export tidak menyediakannya, pakai default yang ditetapkan user.
    if sess.komponen_ada("tempat_usaha"):
        sess.select_radio_by_datakey("tempat_usaha", src.tempat_usaha or DEFAULT_13C_TEMPAT_USAHA)
    else:
        log("13c (tempat usaha) tidak dirender di form ini — dilewati.")
    sess.fill_by_datakey("produk_utama", src.produk_utama)

    # 13d & 13e — bersyarat, muncul kalau 13b1 (produksi di lokasi) = "1. Ya".
    # Sumbernya ADA di export (dataKey `input` & `proses`), jadi TIDAK boleh
    # ditebak. dataKey sisi fasih-web belum pernah terpetakan (tidak pernah
    # dirender di record contoh manapun), karena itu dicari lewat label —
    # datakey_by_label() mencatat dataKey aslinya di log utk didaftarkan nanti.
    for pola, nilai, nama in (
        (r"^13\.\s*d\.", src.input_produksi, "13d input produksi"),
        (r"^13\.\s*e\.", src.proses_produksi, "13e proses produksi"),
    ):
        if not nilai:
            if sess.datakey_by_label(pola):
                log(f"⚠️ {nama} dirender tapi KOSONG di export — akan jadi GALAT, lengkapi sumbernya.")
            continue
        sess.isi_bersyarat_by_label(pola, nilai, nama)

    # --- 13g KBLI (Master KBLI, dgn retry logic) ---
    sess.fill_kbli_master(row.kbli_pecahan.strip(), search_phrase_fallback=kbli_name_hint)
    page.wait_for_timeout(500)
    kategori = read_kategori_lapangan_usaha(page)
    log(f"13h Kategori Lapangan Usaha (auto) = '{kategori}'")

    # 13b4 — bersyarat, hanya kalau 13b1/b2/b3 semuanya "2. Tidak". Diisi DI
    # SINI (bukan bersama 13b1-b3) karena pilihannya diturunkan dari kategori
    # lapangan usaha, yang baru terisi otomatis setelah KBLI dipilih di atas.
    if sess.komponen_ada("aktivitas_jasa_tani", timeout_ms=4000):
        pilihan = OPSI_13B4_PERTANIAN if kategori.strip().upper() == "A" else OPSI_13B4_JASA
        log(f"13b4 muncul (13b1/b2/b3 semuanya Tidak) -> kategori '{kategori}' => {pilihan}")
        sess.select_radio_by_datakey("aktivitas_jasa_tani", pilihan)

    sess.select_radio_by_datakey("jaringan_usaha", src.jaringan_usaha or L["opsi_tunggal"])

    if src.pakai_internet:
        sess.select_radio_by_datakey("pakai_internet", src.pakai_internet)
        # 16b1-b6 & 16c baru dirender kalau 16a = "1. Ya". Sumber fasih-sm
        # tidak menyimpan rincian ini (dicek di export mentah), jadi dipakai
        # default yang ditetapkan user. Deteksi lewat komponen_ada() —
        # BUKAN dari teks jawaban 16a — supaya tetap benar kalau form
        # mengubah syarat kemunculannya.
        # Gagal CEPAT kalau konfigurasinya mustahil. Tanpa ini, kesalahan
        # baru ketahuan sbg GALAT setelah seluruh BLOK II terisi (~1 menit
        # terbuang) — dan galatnya nyangkut di 16b6 sehingga menyesatkan.
        if not any(v.strip().startswith("1") for v in DEFAULT_16B_TUJUAN_INTERNET.values()):
            raise ValueError(
                "config.DEFAULT_16B_TUJUAN_INTERNET tidak punya satu pun '1. Ya'. "
                "Form menolaknya: 'Salah satu dari 16b1 - 16b6 wajib terisi YA'."
            )
        for key, nilai in DEFAULT_16B_TUJUAN_INTERNET.items():
            if sess.komponen_ada(key, timeout_ms=4000):
                sess.select_radio_by_datakey(key, nilai)
            else:
                log(f"{key} (16b) tidak dirender — dilewati.")
        if sess.komponen_ada("teknologi_digital", timeout_ms=4000):
            sess.select_radio_by_datakey("teknologi_digital", DEFAULT_16C_TEKNOLOGI_DIGITAL)
        else:
            log("16c (teknologi digital) tidak dirender — dilewati.")
    if src.produk_ramah_lingkungan:
        sess.select_radio_by_datakey("produk_ramah_lingkungan", src.produk_ramah_lingkungan)
    if src.input_ramah_lingkungan:
        sess.select_radio_by_datakey("input_ramah_lingkungan", src.input_ramah_lingkungan)
    if src.karya_seni_budaya:
        sess.select_radio_by_datakey("karya_seni_budaya", src.karya_seni_budaya)

    # --- rincian 19 — bersyarat & belum pernah dirender di kategori G,
    # jadi dataKey-nya belum terpetakan. Dicari lewat label; nilai default
    # ditetapkan user karena export fasih-sm tidak menyediakannya.
    sess.isi_bersyarat_by_label(r"^19\.\s*a\.", DEFAULT_19A, "19a")
    sess.isi_bersyarat_by_label(r"^19\.\s*c\.", DEFAULT_19C, "19c")

    # --- rincian 20 (BPOM) — kondisional per kategori KBLI ---
    if sess.komponen_ada("izin_edar_bpom"):
        bpom_val = src.izin_edar_bpom or "3. Tidak"
        sess.select_radio_by_datakey("izin_edar_bpom", bpom_val)
        # 20b — jumlah varian yang SUDAH punya izin edar BPOM. Nilainya ada di
        # export (dataKey `sudah_bpom`); dicari lewat label krn dataKey sisi
        # fasih-web belum terpetakan.
        if src.varian_sudah_bpom:
            sess.isi_bersyarat_by_label(r"^20\.\s*b\.", src.varian_sudah_bpom, "20b varian sudah BPOM")
        elif sess.datakey_by_label(r"^20\.\s*b\."):
            log(f"⚠️ 20b dirender tapi kosong di export -> pakai default "
                f"'{DEFAULT_20B_VARIAN_SUDAH_BPOM}' (ASUMSI, tinjau manual).")
            sess.isi_bersyarat_by_label(r"^20\.\s*b\.", DEFAULT_20B_VARIAN_SUDAH_BPOM,
                                        "20b varian sudah BPOM (default)")

        # 20c wajib di SEMUA cabang jawaban 20a, bukan cuma saat "3. Tidak".
        # Dulu ada syarat startswith("3") dan record 2527 (20a = "2. Ya,
        # bukan oleh BPOM") langsung jadi GALAT karena 20c dilewati.
        # Keberadaan komponennya yang menentukan, bukan isi jawaban 20a —
        # dataKey-nya memang baru muncul setelah 20a dijawab.
        if sess.komponen_ada("jumlah_varian_belum_bpom"):
            log(f"20a = '{bpom_val}' -> 20c diisi {DEFAULT_20C_VARIAN_BELUM_BPOM} (default user).")
            sess.fill_by_datakey("jumlah_varian_belum_bpom", DEFAULT_20C_VARIAN_BELUM_BPOM)
        else:
            log("20c (jumlah varian belum BPOM) tidak dirender — dilewati.")
    else:
        log("Rincian 20 (BPOM) tidak muncul di form utk kategori ini — dilewati.")

    sess.select_radio_by_datakey("mitra_kdkmp", src.mitra_kdkmp or "2. Tidak")
    sess.select_radio_by_datakey("program_mbg", src.program_mbg or "5. Tidak terlibat MBG")

    # --- rincian 23a/b/c (transaksi dgn bukan penduduk) ---
    # ⚠️ ASUMSI: sumber fasih-sm TIDAK menyimpan rincian 23, sedangkan form
    # mewajibkannya. Dipakai "2. Tidak" — konsisten dgn KETIGA record manual
    # yang sudah sukses terkirim (2510/2511/2512). Kalau suatu saat ada usaha
    # yang benar-benar bertransaksi dgn bukan penduduk, ini WAJIB dikoreksi
    # manual sebelum Kirim.
    for key in ("trans_barang_non_pddk", "trans_jasa_non_pddk", "trans_beli_jasa_non_pddk"):
        sess.select_radio_by_datakey(key, "2. Tidak")
    log("Rincian 23a/b/c diisi '2. Tidak' (asumsi — tidak ada di sumber).")

    # --- 24 pekerja (empat angka MARGINAL, bukan cross-tab) ---
    # Aturan user 2026-09-06: total pekerja <= 3 -> SEMUA dicatat sbg pekerja
    # tidak dibayar & 26a dinolkan. Logikanya di data_loader.rencana_pekerja()
    # (murni, teruji offline) — di sini tinggal mengetik hasilnya.
    rp = rencana_pekerja(
        src.tk_laki_total, src.tk_perempuan_total,
        src.tk_dibayar_total, src.tk_tidak_dibayar_total,
    )
    for baris in rp.catatan:
        log(f"24: {baris}")
    for key, nilai in (
        ("tk_laki", rp.laki),
        ("tk_pr", rp.perempuan),
        ("tk_dibayar", rp.dibayar),
        ("tk_tdk_dibayar", rp.tidak_dibayar),
    ):
        if nilai == "":
            log(f"⚠️ {key} tidak ada di sumber — dibiarkan kosong, cek ringkasan.")
            continue
        sess.fill_by_datakey(key, nilai)
    # 24c1 & 24c2 (total) terhitung otomatis oleh form.

    if src.tahun_mulai_komersial:
        sess.fill_by_datakey("tahun_mulai_komersial", src.tahun_mulai_komersial)

    # --- rincian 26-29 (varian TAHUNAN) atau 30-33 (varian BULANAN) ---
    # DITETAPKAN USER 2026-09-07: 30-33 muncul (menggantikan 26-29) kalau
    # usaha mulai beroperasi tahun berjalan, tapi SECARA BENTUK sama persis
    # dgn 26-29 -- cuma dataKey-nya beda (akhiran "_bln"/"_didirikan") dan
    # minimal totalnya lebih kecil (10.000, bukan 100.000). Jadi dipakai
    # PERSIS logika & config yang sama (rencana_pengeluaran/rencana_pendapatan/
    # KEPEMILIKAN_MODAL_DEFAULT/ASET_TANAH_OVERRIDE), cuma diarahkan ke set
    # dataKey yang sesuai variannya.
    #
    # Blok finansial baru selesai dirender setelah rincian 25 di-blur.
    sess.page.keyboard.press("Tab")
    sess.page.wait_for_timeout(1500)
    # Tunggu blok finansial BENAR-BENAR dirender. Tanpa ini, saat render
    # lambat deteksi variannya salah dan pengisian langsung meledak
    # "komponen dataKey 'gaji' tidak ada" (record 2566 & 2571, 2026-09-07).
    def _deteksi_varian():
        if sess.komponen_ada("upah_gaji", timeout_ms=20_000):
            return "tahunan"
        if sess.komponen_ada("gaji_bln", timeout_ms=6_000):
            return "bulanan"
        return None

    varian = _deteksi_varian()
    if varian is None:
        # Coba sekali lagi -- kadang cuma lambat.
        sess.page.keyboard.press("Tab")
        sess.page.wait_for_timeout(3000)
        varian = _deteksi_varian()

    if varian is None:
        log("Blok finansial tidak dirender sama sekali (tahun_operasi = "
            f"{src.tahun_mulai_komersial or '?'}) -- rincian pengeluaran/pendapatan/"
            "aset/modal dilewati.")
    else:
        bulanan = varian == "bulanan"
        if bulanan:
            log(f"Varian BULANAN terdeteksi (rincian 30-33) -- tahun_operasi = "
                f"{src.tahun_mulai_komersial}.")
        dk_gaji, dk_produksi, dk_pembelian, dk_ops, dk_nonops = (
            ("gaji_bln", "biaya_produksi_bln", "biaya_pembelian_bln",
             "operasional_bln", "non_operasional_bln") if bulanan else
            ("upah_gaji", "biaya_produksi", "biaya_pembelian",
             "operasional_26d", "non_operasional_26e")
        )
        dk_penjualan, dk_pend_lain = (
            ("nilai_pendapatan_bln", "pendapatan_lain_bln") if bulanan else
            ("nilai_penjualan", "pendapatan_lain")
        )
        dk_aset_tanah, dk_aset_lain, dk_luas = (
            ("aset_tanah_bln", "aset_lain_bln", "luas_tanah_bln") if bulanan else
            ("aset_tanah_bangunan", "aset_selain_tanah", "luas_tanah_28d")
        )
        dk_modal = (
            ("pribadi_didirikan", "nonprofit_didirikan", "korporasi_publik_didirikan",
             "korporasi_nonpublik_didirikan", "pemerintah_didirikan", "asing_didirikan") if bulanan else
            ("pribadi_perorangan", "nonprofit", "korporasi_publik",
             "korporasi_nonpublik", "pemerintah_29e", "asing_29f")
        )
        minimal = MINIMAL_TOTAL_RUPIAH_BULANAN if bulanan else MINIMAL_TOTAL_RUPIAH
        pfx_belanja = "30" if bulanan else "26"
        pfx_jual = "31" if bulanan else "27"

        # Deteksi kondisional 26c/30c dari DOM (bukan tabel kategori KBLI
        # hardcode): kategori B-F & I gol.56 tidak menampilkan pos ini terpisah.
        has_c = sess.komponen_ada(dk_pembelian)
        peng = rencana_pengeluaran(row, has_26c=has_c, nolkan_upah=rp.nolkan_upah, minimal=minimal)
        for baris in peng.catatan:
            log(f"{pfx_belanja}: {baris}")
        sess.fill_by_datakey(dk_gaji, str(peng.upah_gaji))
        sess.fill_by_datakey(dk_produksi, str(peng.biaya_produksi))
        if peng.biaya_pembelian is not None:
            sess.fill_by_datakey(dk_pembelian, str(peng.biaya_pembelian))
        sess.fill_by_datakey(dk_ops, str(peng.operasional))
        sess.fill_by_datakey(dk_nonops, str(peng.non_operasional))
        log(f"{pfx_belanja}f total pengeluaran (hitungan skrip) = {peng.total}")

        # --- rincian 27/31 (Pendapatan) ---
        pend = rencana_pendapatan(row, minimal=minimal)
        for baris in pend.catatan:
            log(f"{pfx_jual}: {baris}")
        sess.fill_by_datakey(dk_penjualan, str(pend.nilai_penjualan))
        sess.fill_by_datakey(dk_pend_lain, str(pend.pendapatan_lain))

        if not bulanan:
            # 27d (% pendapatan online) -- cuma ada di varian tahunan, ikut
            # muncul bersama 16b; sumbernya juga tidak ada di export.
            if sess.komponen_ada("pendapatan_online", timeout_ms=4000):
                sess.fill_by_datakey("pendapatan_online", DEFAULT_27D_PERSEN_PENDAPATAN_ONLINE)
            else:
                log("27d (persentase pendapatan online) tidak dirender -- dilewati.")
        else:
            # 31e "Bulan beroperasi selama tahun ini" -- HANYA ada di varian
            # bulanan; tidak ada padanan di 26-29, dan sumber TIDAK punya data
            # bulan. DITETAPKAN USER 2026-09-07: pilih bulan MULAI secara
            # ACAK di antara opsi yang tersedia (form cuma menampilkan bulan
            # yang sudah lewat tahun berjalan), lalu centang bulan itu dan
            # SEMUA bulan sesudahnya sampai bulan terakhir yang tersedia.
            if sess.komponen_ada("bulan_operasi", timeout_ms=4000):
                teks_komponen = sess.komponen("bulan_operasi").first.inner_text()
                tersedia = [b for b in BULAN_NAMA if b in teks_komponen]
                if tersedia:
                    mulai = random.randrange(len(tersedia))
                    dipilih = tersedia[mulai:]
                    log(f"31e: opsi bulan tersedia {tersedia} -> mulai ACAK dari "
                        f"'{tersedia[mulai]}', dicentang: {dipilih}")
                    for bulan in dipilih:
                        sess.centang_teks_dalam_komponen("bulan_operasi", bulan)
                else:
                    log("31e (bulan operasi) dirender tapi tidak ada satu pun opsi "
                        "bulan terbaca -- cek manual.")
            else:
                log("31e (bulan operasi) tidak dirender -- dilewati.")

        # --- rincian 28/32 (Aset) ---
        sess.fill_by_datakey(dk_aset_tanah, ASET_TANAH_OVERRIDE)
        sess.fill_by_datakey(dk_aset_lain, str(rupiah10(row.aset_lain_thn)))  # lihat catatan validasi di atas
        sess.fill_by_datakey(dk_luas, LUAS_TANAH_OVERRIDE)

        # --- rincian 29/33 (Kepemilikan modal) -- pakai hasil export kalau
        # ada, fallback ke default 100% Pribadi kalau sumbernya tidak punya
        # field ini (lihat catatan modul & SourceBlok2.kepemilikan_modal).
        if not sess.komponen_ada(dk_modal[0], timeout_ms=8_000):
            log(f"Rincian {'33' if bulanan else '29'} (kepemilikan modal) tidak dirender -- dilewati.")
        else:
            kepemilikan = src.kepemilikan_modal or KEPEMILIKAN_MODAL_DEFAULT
            dk_pribadi, dk_nonprofit, dk_publik, dk_nonpublik, dk_pemerintah, dk_asing = dk_modal
            sess.fill_by_datakey(dk_pribadi, str(kepemilikan.get("pribadi", KEPEMILIKAN_MODAL_DEFAULT["pribadi"])))
            for key, label in (
                (dk_nonprofit, "nonprofit"),
                (dk_publik, "korporasi_publik"),
                (dk_nonpublik, "korporasi_nonpublik"),
                (dk_pemerintah, "pemerintah"),
                (dk_asing, "asing"),
            ):
                sess.fill_by_datakey(key, str(kepemilikan.get(label, KEPEMILIKAN_MODAL_DEFAULT[label])))

    # Dump SETELAH terisi. Dump saat nested baru dibuka TIDAK memuat field
    # bersyarat (16b/16c/27d/30-33 baru ada setelah pertanyaan pemicunya
    # dijawab) -- itulah sebabnya banyak dataKey di sini tidak terpetakan
    # sampai baru diketahui lewat dump ini.
    sess.dump("blok2_selesai_terisi")
    log("BLOK II selesai diisi.")


def fill_keterangan_pemberi_jawaban(sess: FasihWebSession):
    """Section KETERANGAN PEMBERI JAWABAN. dataKey terverifikasi:
      nama_info_list          combobox (textarea) -> "Lainnya"
      telp_info / email_info  opsional, dibiarkan kosong
      persetujuan_responden   checkbox WAJIB
    """
    sess._log("Isi KETERANGAN PEMBERI JAWABAN ...")
    sess.pilih_combobox_by_datakey("nama_pemberi_informasi", NAMA_PEMBERI_INFORMASI)
    sess.centang_by_datakey("checkbox_pernyataan")
    sess._log("KETERANGAN PEMBERI JAWABAN selesai.")


def fill_catatan(sess: FasihWebSession):
    """Section CATATAN. dataKey terverifikasi: `waktu_selesai` (tombol
    "Ambil Waktu") dan `catatan` (textarea). Textarea SENGAJA dibiarkan
    kosong — opsional, dan memang muncul di daftar KOSONG ringkasan."""
    sess._log("Isi CATATAN ...")
    sess.isi_waktu_by_datakey("waktu_selesai")
    sess._log("CATATAN selesai (textarea Catatan sengaja dibiarkan kosong).")
