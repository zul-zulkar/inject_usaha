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
