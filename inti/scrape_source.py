"""
scrape_source.py — Baca field BLOK II DESKRIPTIF dari fasih-sm.bps.go.id
(sistem sumber, read-only) untuk satu baris backlog.

⚠️ BAGIAN INI PALING BERISIKO PERLU PENYESUAIAN. Selama sesi manual,
fasih-sm hanya pernah dibaca lewat screenshot visual (bukan inspeksi HTML
mentah), jadi selector di sini adalah tebakan terbaik berdasarkan pola
label yang sama dengan fasih-web (karena instrumennya sama), BUKAN hasil
verifikasi langsung terhadap DOM fasih-sm. WAJIB divalidasi saat dry-run
pertama — bandingkan hasil scrape utk salah satu dari 3 record yang sudah
diketahui nilainya persis (lihat catatan-usaha-pecahan-se2026.md) sebelum
dipakai untuk baris backlog yang belum diketahui jawabannya.

Field yang di-scrape di sini adalah field yang TIDAK ADA di kolom sheet
(nama komersial, alamat detail, nama pengusaha, jenis kelamin, umur,
deskripsi kegiatan usaha, dst) — field finansial (rincian 26-29) TIDAK
di-scrape dari sini karena sudah tersedia sbg kolom angka di sheet sumber
(lebih reliable & lebih cepat dibaca dari CSV drpd di-scroll-cari di UI).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

from playwright.sync_api import Page

from inti.config import FASIH_SM_BASE, L


@dataclass
class SourceBlok2:
    nama_komersial: str = ""          # 8b
    alamat_nama_jalan: str = ""        # bagian dari 8c sumber (dipecah "... -")
    rt: str = ""
    rw: str = ""
    no_hp_wa: str = ""
    nama_pengusaha: str = ""           # 12a — SALIN PERSIS ejaan, jangan pakai roster/kolom P
    jenis_kelamin: str = ""            # "1. Laki-laki" / "2. Perempuan"
    umur: str = ""
    kegiatan_utama: str = ""           # 13a
    b1_produksi_lokasi: str = ""       # 13b1 Ya/Tidak
    b2_layanan_makan_minum: str = ""   # 13b2
    b3_penjualan_barang: str = ""      # 13b3
    tempat_usaha: str = ""             # 13c
    produk_utama: str = ""             # 13f
    jaringan_usaha: str = ""           # 14a
    pakai_internet: str = ""           # 16a
    produk_ramah_lingkungan: str = ""  # 17a
    input_ramah_lingkungan: str = ""   # 17b
    karya_seni_budaya: str = ""        # 18
    izin_edar_bpom: str = ""           # 20a (mungkin tidak ada di sumber jg)
    mitra_kdkmp: str = ""              # 21
    program_mbg: str = ""              # 22
    tahun_mulai_komersial: str = ""    # 25
    pekerja_laki2_dibayar: str = ""    # 24a1 (dan seterusnya)
    pekerja_perempuan_dibayar: str = ""
    pekerja_tdk_dibayar: str = ""
    # Form fasih-web meminta 4 angka MARGINAL (24a1/b1 per gender, 24a2/b2
    # per status bayar) — bukan cross-tab. Inilah yang tersedia di sumber.
    # 13d/13e (bersyarat, ikut 13b1="1. Ya") & 20b — dari export.
    input_produksi: str = ""
    proses_produksi: str = ""
    varian_sudah_bpom: str = ""
    tk_laki_total: str = ""
    tk_perempuan_total: str = ""
    tk_dibayar_total: str = ""
    tk_tidak_dibayar_total: str = ""
    kepemilikan_modal: dict = dc_field(default_factory=dict)  # rincian 29 — diisi export_source.py kalau tersedia, kosong = pakai KEPEMILIKAN_MODAL_DEFAULT
    sumber: str = "scrape"              # "scrape" (live fasih-sm, ini) atau "export" (lihat export_source.py)
    catatan_scrape: list[str] = dc_field(default_factory=list)  # log ketidakpastian per field


def build_source_url(survey_assignment_id: str, row_assignment_id: str) -> str:
    """Pola URL sudah dikonfirmasi (BUKAN cuma kolom E saja -> 404):
    https://fasih-sm.bps.go.id/app/assignment/{survey_assignment_id}/{row_id}
    """
    return f"{FASIH_SM_BASE}/app/assignment/{survey_assignment_id}/{row_assignment_id}"


def _text_near_label(page: Page, label_substr: str, timeout: int = 4000) -> str:
    """Best-effort: cari teks label (partial match, case-insensitive), lalu
    ambil teks dari elemen 'saudara'/berikutnya sbg value-nya. Fasih-sm
    read-only biasanya render field sbg pasangan label+value tanpa <input>.
    Kalau tidak ketemu, kembalikan string kosong & catat di log pemanggil
    (JANGAN raise — satu field gagal tidak boleh menghentikan scraping
    field lain)."""
    try:
        loc = page.get_by_text(label_substr, exact=False).first
        loc.wait_for(timeout=timeout)
        # coba beberapa strategi umum: next sibling, parent's next sibling,
        # atau elemen dgn class yg biasa dipakai utk "value"
        candidates = [
            loc.locator("xpath=following::*[self::span or self::div or self::p][1]"),
            loc.locator("xpath=../following-sibling::*[1]"),
            loc.locator("xpath=ancestor::*[1]/following-sibling::*[1]"),
        ]
        for cand in candidates:
            try:
                txt = cand.first.inner_text(timeout=1500).strip()
                if txt and txt.lower() != label_substr.lower():
                    return txt
            except Exception:
                continue
        return ""
    except Exception:
        return ""


def scrape_source_blok2(page: Page, survey_assignment_id: str, row_assignment_id: str) -> SourceBlok2:
    url = build_source_url(survey_assignment_id, row_assignment_id)
    page.goto(url, wait_until="domcontentloaded")

    # fasih-sm kadang lambat render & stuck di "Loading Data..." belasan
    # detik — tunggu sampai teks itu hilang (atau timeout wajar), JANGAN
    # buru2 reload (sesuai catatan proyek).
    try:
        page.get_by_text("Loading Data", exact=False).wait_for(state="hidden", timeout=20_000)
    except Exception:
        pass  # kalau elemen "Loading Data..." memang tidak pernah muncul, tidak masalah

    src = SourceBlok2()
    log = src.catatan_scrape

    def grab(attr: str, label: str):
        val = _text_near_label(page, label)
        setattr(src, attr, val)
        if not val:
            log.append(f"TIDAK KETEMU: {attr} (label≈'{label}')")

    grab("nama_komersial", "Nama Usaha")
    grab("nama_pengusaha", "Nama Pengusaha")
    grab("jenis_kelamin", "Jenis Kelamin")
    grab("umur", "Umur")
    grab("kegiatan_utama", "kegiatan utama")
    grab("tempat_usaha", "tempat usaha")
    grab("produk_utama", "produk utama")
    grab("jaringan_usaha", "jaringan usaha")
    grab("pakai_internet", "menggunakan internet")
    grab("produk_ramah_lingkungan", "produk ramah lingkungan")
    grab("input_ramah_lingkungan", "input ramah lingkungan")
    grab("karya_seni_budaya", "karya seni")
    grab("izin_edar_bpom", "izin edar")
    grab("mitra_kdkmp", "KDKMP")
    grab("program_mbg", "MBG")
    grab("tahun_mulai_komersial", "tahun mulai")
    grab("no_hp_wa", "No HP")
    grab("rt", "RT")
    grab("rw", "RW")

    return src
