"""
data_loader.py — Baca backlog dari CSV hasil export Google Sheet sumber,
dan helper kalkulasi (pembulatan 10% round-half-up).

CARA EXPORT CSV DARI GOOGLE SHEET
----------------------------------
File > Download > Comma Separated Values (.csv) — HANYA sheet/tab yang
relevan. Pastikan baris header (nama kolom) ikut ter-export di baris 1,
karena loader ini mencocokkan kolom berdasar NAMA HEADER, bukan posisi
huruf kolom (lebih tahan kalau ada kolom disisipkan/dihapus di masa depan).

Header yang WAJIB ada (samakan persis dgn nama di row 1 sheet sumber):
    link, nama_usaha_pecahan, kbli_pecahan, No, assignment_id, index1,
    idsubsls, nama_kepala_keluarga, PIC, Nama PML, Nama PPL,
    Email PML, Email PPL, keberadaan_keluarga, nama_usaha_di_bangunan,
    nama_usaha_di_keluarga, skala_usaha, kbli_akhir, kategori,
    kategori_2025, keberadaan_usaha, latitude, longitude, nik,
    tk_dibayar, tk_tdk_dibayar, nilai_pendapatan, pendapatan_lain, gaji,
    biaya_produksi, biaya_pembelian, operasional, non_operasional,
    total_pengeluaran, aset_usaha_thn, aset_lain_thn, total_aset_thn,
    luas_tanah_thn

Kalau nama header di sheet asli berbeda (mis. tanpa header row, atau beda
kapitalisasi), sesuaikan dict HEADER_ALIASES di bawah — jangan ubah logika
lain.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from inti.config import (
    BATAS_TK_SEMUA_TIDAK_DIBAYAR, MINIMAL_TOTAL_RUPIAH, POS_PENAMPUNG_MINIMAL,
    POS_PENGELUARAN_KANDIDAT_POTONG,
)

# Kalau nama kolom di file CSV-mu sedikit beda dari daftar di atas,
# tambahkan alias di sini: {"nama_di_csv_kamu": "nama_field_internal"}
HEADER_ALIASES: dict[str, str] = {}

REQUIRED_HEADERS = [
    "nama_usaha_pecahan", "kbli_pecahan", "No", "assignment_id",
    "idsubsls", "nama_usaha_di_keluarga", "latitude", "longitude",
]


def _to_decimal(raw: str | None) -> Decimal:
    """Parse angka dari sel sheet (bisa kosong, ada koma ribuan, dll) -> Decimal(0) kalau kosong/invalid."""
    if raw is None:
        return Decimal(0)
    s = str(raw).strip().replace(".", "").replace(",", ".") if "," in str(raw) and "." in str(raw) else str(raw).strip()
    # Sheet biasanya export angka polos (mis. "46800000"), tapi jaga-jaga
    # kalau format lokal (titik ribuan) ikut ter-export sbg teks:
    s = re.sub(r"[^\d\-.]", "", s)
    if s in ("", "-", "."):
        return Decimal(0)
    try:
        return Decimal(s)
    except Exception:
        return Decimal(0)


def rupiah10(source_value: str | None) -> int:
    """10% dari nilai sumber, dibulatkan ke rupiah terdekat (round HALF UP,
    BUKAN round-half-even default Python) — sesuai rule #5 catatan proyek.
    """
    d = _to_decimal(source_value) * Decimal("0.1")
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def sum_rupiah10(*source_values: str | None) -> int:
    """Jumlahkan beberapa nilai sumber (Decimal, BUKAN float — hindari
    imprecision) dulu, BARU dikali 10% & dibulatkan sekali di akhir. Dipakai
    utk kasus kategori B-F/I(gol56) yg menggabungkan biaya_produksi +
    biaya_pembelian ke satu field 26b (lihat fill_blok2.py). Urutan
    'jumlah dulu baru bulatkan' ini PENTING — sudah dikonfirmasi cocok dgn
    hasil record 2 yg terverifikasi sukses (33.600.008 x 10% = 3.360.000,8
    -> round half up -> 3.360.001)."""
    total = sum((_to_decimal(v) for v in source_values), Decimal(0))
    d = total * Decimal("0.1")
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_survey_assignment_id(fasih_sm_url: str) -> Optional[str]:
    """Ambil {survey_assignment_id} dari URL kolom 'link' (kolom A sheet),
    pola: https://fasih-sm.bps.go.id/app/assignment/{survey_assignment_id}/{row_id}
    Dipakai sbg sumber-kebenaran per-baris drpd mengasumsikan 1 nilai
    konstan utk semua baris (beda PPL/wilayah bisa beda assignment).
    """
    try:
        path = urlparse(fasih_sm_url).path.strip("/")
        parts = path.split("/")
        # parts contoh: ['app', 'assignment', '{survey_assignment_id}', '{row_id}']
        idx = parts.index("assignment")
        return parts[idx + 1]
    except Exception:
        return None


@dataclass
class BacklogRow:
    no: str
    nama_usaha_pecahan: str
    kbli_pecahan: str
    link_fasih_sm: str
    survey_assignment_id: Optional[str]
    row_assignment_id: str  # kolom E (dipakai sbg {row_id} di URL fasih-sm)
    idsubsls: str
    nama_kepala_keluarga: str
    email_ppl: str
    nama_ppl: str
    nama_usaha_di_keluarga: str
    kbli_akhir_sumber: str
    kategori_sumber: str
    latitude: str
    longitude: str
    # kolom finansial mentah (sebelum dikali 10%) — disimpan sbg string
    # supaya kalkulasi/pembulatan dilakukan eksplisit di kode pengisi form,
    # bukan diam2 di sini.
    nilai_pendapatan: str
    pendapatan_lain: str
    gaji: str
    biaya_produksi: str
    biaya_pembelian: str
    operasional: str
    non_operasional: str
    aset_lain_thn: str
    raw: dict = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """Baris siap diproses otomatisasi = kolom B & C (nama & KBLI
        pecahan) SUDAH diisi manual oleh manusia (keputusan bisnis, bukan
        sesuatu yg boleh ditebak otomatisasi)."""
        return bool(self.nama_usaha_pecahan.strip()) and bool(self.kbli_pecahan.strip())


def _get(row: dict, *names: str) -> str:
    for n in names:
        key = HEADER_ALIASES.get(n, n)
        if key in row and row[key] is not None:
            return str(row[key]).strip()
    return ""


def load_backlog(csv_path: str | Path, only_ready: bool = True) -> list[BacklogRow]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV tidak ditemukan: {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV kosong / tidak ada header row.")
        missing = [h for h in REQUIRED_HEADERS if h not in reader.fieldnames and HEADER_ALIASES.get(h, h) not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"Header CSV kurang: {missing}. Header yang terbaca: {reader.fieldnames}. "
                "Sesuaikan HEADER_ALIASES di data_loader.py kalau nama kolommu berbeda."
            )

        out: list[BacklogRow] = []
        for raw_row in reader:
            link = _get(raw_row, "link")
            row = BacklogRow(
                no=_get(raw_row, "No"),
                nama_usaha_pecahan=_get(raw_row, "nama_usaha_pecahan"),
                kbli_pecahan=_get(raw_row, "kbli_pecahan"),
                link_fasih_sm=link,
                survey_assignment_id=parse_survey_assignment_id(link) if link else None,
                row_assignment_id=_get(raw_row, "assignment_id"),
                idsubsls=_get(raw_row, "idsubsls"),
                nama_kepala_keluarga=_get(raw_row, "nama_kepala_keluarga"),
                email_ppl=_get(raw_row, "Email PPL"),
                nama_ppl=_get(raw_row, "Nama PPL"),
                nama_usaha_di_keluarga=_get(raw_row, "nama_usaha_di_keluarga"),
                kbli_akhir_sumber=_get(raw_row, "kbli_akhir"),
                kategori_sumber=_get(raw_row, "kategori"),
                latitude=_get(raw_row, "latitude"),
                longitude=_get(raw_row, "longitude"),
                nilai_pendapatan=_get(raw_row, "nilai_pendapatan"),
                pendapatan_lain=_get(raw_row, "pendapatan_lain"),
                gaji=_get(raw_row, "gaji"),
                biaya_produksi=_get(raw_row, "biaya_produksi"),
                biaya_pembelian=_get(raw_row, "biaya_pembelian"),
                operasional=_get(raw_row, "operasional"),
                non_operasional=_get(raw_row, "non_operasional"),
                aset_lain_thn=_get(raw_row, "aset_lain_thn"),
                raw=raw_row,
            )
            if only_ready and not row.is_ready:
                continue
            out.append(row)
        return out


def group_by_credential(rows: list[BacklogRow]) -> dict[tuple[str, str], list[BacklogRow]]:
    """Kelompokkan baris per (email_ppl, survey_assignment_id) supaya
    login/logout tidak dilakukan berulang2 utk baris yg sama akunnya."""
    groups: dict[tuple[str, str], list[BacklogRow]] = {}
    for r in rows:
        key = (r.email_ppl, r.survey_assignment_id or "")
        groups.setdefault(key, []).append(r)
    return groups


# ---------------------------------------------------------------------------
# Aturan pekerja (rincian 24) <-> upah/gaji (rincian 26a)
# ---------------------------------------------------------------------------
# Ditetapkan user 2026-09-06. Sengaja ditaruh di sini (bukan di fill_blok2.py)
# supaya bisa diuji tanpa browser/VPN — lihat tests/test_pengeluaran.py.

def _to_int_or_none(raw: str | int | None) -> Optional[int]:
    """Angka pekerja dari sumber: "" / None / non-numerik -> None (BUKAN 0),
    supaya 'tidak diketahui' bisa dibedakan dari 'nol orang'."""
    if raw is None:
        return None
    s = re.sub(r"[^\d\-]", "", str(raw).strip())
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except Exception:
        return None


def _s(v: Optional[int]) -> str:
    return "" if v is None else str(v)


@dataclass
class RencanaPekerja:
    """Empat angka marginal rincian 24 yang akan diketik ke form, plus
    keputusan apakah 26a (upah/gaji) harus dinolkan."""
    laki: str            # 24a1
    perempuan: str       # 24b1
    dibayar: str         # 24a2
    tidak_dibayar: str   # 24b2
    total: Optional[int]
    nolkan_upah: bool
    catatan: list[str] = field(default_factory=list)


def rencana_pekerja(
    tk_laki: str, tk_pr: str, tk_dibayar: str, tk_tdk_dibayar: str,
    batas: int = BATAS_TK_SEMUA_TIDAK_DIBAYAR,
) -> RencanaPekerja:
    """Aturan user: usaha dgn total pekerja <= `batas` (3) dicatat sbg
    SELURUHNYA pekerja tidak dibayar, dan 26a dinolkan. Di atas itu, angka
    sumber dipakai apa adanya (pemotongan 26a diurus rencana_pengeluaran()).

    Kalau total pekerja tidak bisa ditentukan dari sumber, aturan TIDAK
    diterapkan — lebih baik jatuh ke perilaku lama drpd menebak.
    """
    l, p = _to_int_or_none(tk_laki), _to_int_or_none(tk_pr)
    d, td = _to_int_or_none(tk_dibayar), _to_int_or_none(tk_tdk_dibayar)
    catatan: list[str] = []

    if l is not None and p is not None:
        total = l + p
    elif d is not None and td is not None:
        total = d + td
        catatan.append("Total pekerja dihitung dari 24a2+24b2 (24a1/24b1 kosong di sumber).")
    else:
        total = None

    if None not in (l, p, d, td) and (l + p) != (d + td):
        catatan.append(
            f"⚠️ Marginal sumber tidak konsisten: 24a1+24b1={l + p} vs 24a2+24b2={d + td}. "
            "Form akan menolak kalau kedua total tidak sama — cek manual."
        )

    if total is None:
        catatan.append(
            "⚠️ Total pekerja tidak diketahui dari sumber — aturan '<=3 orang semua "
            "tidak dibayar' TIDAK diterapkan; 26a tetap 10% sumber."
        )
        return RencanaPekerja(_s(l), _s(p), _s(d), _s(td), None, False, catatan)

    if total <= batas:
        catatan.append(
            f"Total pekerja {total} <= {batas} -> 24a2 (dibayar)=0, 24b2 (tidak dibayar)={total}, "
            "26a (upah/gaji) dinolkan."
        )
        return RencanaPekerja(_s(l), _s(p), "0", str(total), total, True, catatan)

    catatan.append(
        f"Total pekerja {total} > {batas} -> angka pekerja dipakai apa adanya; "
        "26a = 10% sumber lalu dipotong dari pos pengeluaran terbesar."
    )
    return RencanaPekerja(_s(l), _s(p), _s(d), _s(td), total, False, catatan)


@dataclass
class RencanaPengeluaran:
    """Angka rincian 26 yang siap diketik (SUDAH 10% & sudah dibulatkan)."""
    upah_gaji: int                  # 26a
    biaya_produksi: int             # 26b (sudah termasuk 26c kalau digabung)
    biaya_pembelian: Optional[int]  # 26c — None kalau tidak dirender form
    operasional: int                # 26d
    non_operasional: int            # 26e
    potongan: list[tuple[str, int]] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (self.upah_gaji + self.biaya_produksi + (self.biaya_pembelian or 0)
                + self.operasional + self.non_operasional)


def rencana_pengeluaran(
    row: "BacklogRow", has_26c: bool, nolkan_upah: bool,
    minimal: int = MINIMAL_TOTAL_RUPIAH,
) -> RencanaPengeluaran:
    """Hitung 26a-26e final.

    - `has_26c` dari DOM (kategori B-F & I gol.56 tidak punya 26c terpisah;
      26b & 26c digabung — pakai sum_rupiah10 supaya pembulatan sekali di akhir).
    - `nolkan_upah` dari rencana_pekerja(): total pekerja <= 3.
      Saat True, 26a=0 TANPA kompensasi ke pos lain -> total pengeluaran turun.
      Saat False dan 26a>0, nilai 26a DIPOTONG dari pos lain yang paling besar
      (kaskade ke pos terbesar berikutnya kalau tidak cukup) supaya total
      pengeluaran tidak membengkak.

    Pemotongan dilakukan pada angka FINAL (pasca-10%-dan-pembulatan), bukan
    pada nilai sumber, supaya total yang terisi persis sama dgn sebelum
    pemotongan — kalau dipotong di level sumber, pembulatan bisa geser +-1.
    """
    catatan: list[str] = []
    upah = rupiah10(row.gaji)

    if has_26c:
        pos: dict[str, int] = {
            "biaya_produksi": rupiah10(row.biaya_produksi),
            "biaya_pembelian": rupiah10(row.biaya_pembelian),
        }
    else:
        pos = {"biaya_produksi": sum_rupiah10(row.biaya_produksi, row.biaya_pembelian)}
        catatan.append(
            "26c tidak dirender -> biaya_produksi+biaya_pembelian digabung ke 26b = "
            f"{pos['biaya_produksi']}."
        )
    pos["operasional"] = rupiah10(row.operasional)
    pos["non_operasional"] = rupiah10(row.non_operasional)

    potongan: list[tuple[str, int]] = []

    if nolkan_upah:
        if upah:
            catatan.append(
                f"26a {upah} -> 0 (semua pekerja tidak dibayar). "
                f"Total pengeluaran ikut turun {upah} — sesuai aturan user, tanpa kompensasi."
            )
        upah = 0
    elif upah > 0:
        # Urut pos dari kontribusi TERBESAR. Sort stabil, jadi kalau nilainya
        # sama urutannya mengikuti POS_PENGELUARAN_KANDIDAT_POTONG.
        kandidat = [k for k in POS_PENGELUARAN_KANDIDAT_POTONG if k in pos]
        kandidat.sort(key=lambda k: pos[k], reverse=True)
        sisa = upah
        for nama in kandidat:
            if sisa <= 0:
                break
            ambil = min(sisa, pos[nama])
            if ambil <= 0:
                continue
            pos[nama] -= ambil
            sisa -= ambil
            potongan.append((nama, ambil))
        if potongan:
            rincian = ", ".join(f"{n} -{j}" for n, j in potongan)
            catatan.append(f"26a {upah} dipotong dari pos terbesar: {rincian}.")
        if sisa > 0:
            catatan.append(
                f"⚠️ Pos pengeluaran lain tidak cukup menutupi 26a — sisa {sisa} TIDAK dipotong, "
                f"total pengeluaran naik {sisa}. Cek manual sebelum Kirim."
            )

    # Naikkan sampai total = MINIMAL_TOTAL_RUPIAH kalau masih kurang.
    # Dilakukan PALING AKHIR, setelah pemotongan 26a, supaya totalnya benar2
    # pas di angka minimal.
    total_kini = upah + sum(pos.values())
    if total_kini < minimal:
        kurang = minimal - total_kini
        kandidat = [k for k in POS_PENGELUARAN_KANDIDAT_POTONG if k in pos]
        terbesar = max(kandidat, key=lambda k: pos[k])
        sasaran = terbesar if pos[terbesar] > 0 else (
            POS_PENAMPUNG_MINIMAL if POS_PENAMPUNG_MINIMAL in pos else kandidat[0])
        pos[sasaran] += kurang
        catatan.append(
            f"⚠️ Total 26f {total_kini} < minimal {minimal} yang diwajibkan form "
            f"-> ditambah {kurang} ke '{sasaran}' sampai pas {minimal}. "
            "Angka ini TIDAK lagi 10% dari sumber — tinjau manual."
        )

    return RencanaPengeluaran(
        upah_gaji=upah,
        biaya_produksi=pos["biaya_produksi"],
        biaya_pembelian=pos.get("biaya_pembelian"),
        operasional=pos["operasional"],
        non_operasional=pos["non_operasional"],
        potongan=potongan,
        catatan=catatan,
    )


@dataclass
class RencanaPendapatan:
    """Angka rincian 27 yang siap diketik (SUDAH 10% & dibulatkan)."""
    nilai_penjualan: int      # 27a
    pendapatan_lain: int      # 27b
    ditambah: int = 0
    catatan: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:   # 27c, dihitung otomatis oleh form
        return self.nilai_penjualan + self.pendapatan_lain


def rencana_pendapatan(row: "BacklogRow", minimal: int = MINIMAL_TOTAL_RUPIAH) -> RencanaPendapatan:
    """27a & 27b = 10% sumber. Kalau totalnya di bawah `minimal` yang
    diwajibkan form ("Nilai minimal 100.000"), kekurangannya ditambahkan ke
    27a (nilai penjualan) — pos utama — sampai total pas di angka minimal.
    Ketetapan user 2026-09-07; setiap kejadian dicatat supaya bisa ditinjau."""
    penjualan = rupiah10(row.nilai_pendapatan)
    lain = rupiah10(row.pendapatan_lain)
    catatan: list[str] = []
    ditambah = 0
    if penjualan + lain < minimal:
        ditambah = minimal - (penjualan + lain)
        catatan.append(
            f"⚠️ Total 27c {penjualan + lain} < minimal {minimal} yang diwajibkan form "
            f"-> 27a ditambah {ditambah} sampai pas {minimal}. "
            "Angka ini TIDAK lagi 10% dari sumber — tinjau manual."
        )
        penjualan += ditambah
    return RencanaPendapatan(penjualan, lain, ditambah, catatan)
