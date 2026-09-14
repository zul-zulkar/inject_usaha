"""
export_source.py — Muat data BLOK II dari hasil ekspor manual fasih-sm
(export/{No}_{assignment_id}.converted.json, hasil convert_manual_export.py
— lihat PANDUAN_EKSPOR_MANUAL.md) sbg SourceBlok2, PENGGANTI
scrape_source_blok2() yang rawan deteksi bot & masih berlubang (lihat
"Gap yang diketahui" di CLAUDE.md).

Kalau 1 keluarga di sumber punya >1 usaha (umum terjadi — dari 204
assignment pertama yang diekspor, 72 di antaranya begitu), hasil export
berisi konversi SEMUA usaha itu. Fungsi di sini mencocokkan
'nama_usaha_raw' tiap kandidat ke kolom P backlog (nama_usaha_di_keluarga)
via normalisasi teks (uppercase, buang tanda baca) + fuzzy match
(difflib). HANYA match PERSIS (score 1.0) yang dipakai otomatis — FUZZY
atau NO_MATCH dikembalikan sbg None + alasan, BUKAN ditebak, supaya
main.py men-skip baris itu utk direview manual (prinsip proyek: jangan
menebak field yang tidak pasti, lihat CLAUDE.md rule #5).
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from inti.scrape_source import SourceBlok2

EXPORT_DIR = Path("export")

# Field "fields" hasil convert_manual_export.py yang sudah lewat _label()
# di sana (list [{"label":...}] -> string) bisa dipakai langsung. Field ini
# BELUM (raw dari sumber) di beberapa versi lama .converted.json yang
# sudah kadung ditulis sebelum perbaikan _label() — ditoleransi di sini juga
# (defensif) drpd wajib re-generate ulang semua file lama.
_MAYBE_RAW_LIST_FIELDS = {"izin_edar_bpom"}


def _norm_name(s: str) -> str:
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _label_or_str(v: Any) -> str:
    """Toleransi kalau field ternyata masih list [{"label":...}] mentah
    (file .converted.json lama sebelum fix izin_edar_bpom) — tetap
    dikonversi jadi string label yg rapi drpd dibiarkan jadi repr Python."""
    if isinstance(v, list) and v and isinstance(v[0], dict) and "label" in v[0]:
        return ", ".join(str(x.get("label", "")) for x in v)
    if v is None:
        return ""
    return str(v)


def _num_or_blank_str(v: Any) -> str:
    """Teks bebas dari export -> string bersih ("" kalau kosong/None)."""
    return "" if v is None else str(v).strip()


def _num_or_blank(v: Any) -> str:
    return "" if v is None else str(v)


@dataclass
class ExportLookupResult:
    src: Optional[SourceBlok2]
    # OK | FILE_NOT_FOUND | FILE_INVALID | NO_USAHA_FIELD | FUZZY_PERLU_CEK | NO_MATCH
    status: str
    detail: str = ""
    match_score: float = 0.0
    usaha_terpilih: str = ""
    jumlah_usaha: int = 0


def load_source_blok2_from_export(
    no: str,
    assignment_id: str,
    nama_usaha_di_keluarga: str,
    export_dir: Path = EXPORT_DIR,
) -> ExportLookupResult:
    path = export_dir / f"{no}_{assignment_id}.converted.json"
    if not path.exists():
        return ExportLookupResult(None, "FILE_NOT_FOUND", detail=str(path))

    try:
        results = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return ExportLookupResult(None, "FILE_INVALID", detail=f"{type(e).__name__}: {e}")

    if not results:
        return ExportLookupResult(None, "NO_USAHA_FIELD", detail="File .converted.json kosong (0 usaha).")

    col_p_norm = _norm_name(nama_usaha_di_keluarga)
    best = None
    best_score = -1.0
    for r in results:
        cand_norm = _norm_name(r.get("nama_usaha_raw", ""))
        if cand_norm == col_p_norm and col_p_norm:
            score = 1.0
        else:
            score = difflib.SequenceMatcher(None, cand_norm, col_p_norm).ratio() if col_p_norm else 0.0
        if score > best_score:
            best_score, best = score, r

    jumlah_usaha = len(results)

    if best_score < 1.0:
        status = "FUZZY_PERLU_CEK" if best_score >= 0.6 else "NO_MATCH"
        return ExportLookupResult(
            None,
            status,
            detail=(
                f"kolom_P backlog='{nama_usaha_di_keluarga}' vs kandidat terbaik "
                f"di export='{best.get('nama_usaha_raw') if best else None}' (score={best_score:.2f})"
            ),
            match_score=best_score,
            usaha_terpilih=best.get("nama_usaha_raw", "") if best else "",
            jumlah_usaha=jumlah_usaha,
        )

    fields = best.get("fields", {})
    pekerja = best.get("pekerja", {})

    src = SourceBlok2(
        nama_komersial=fields.get("nama_komersial", ""),
        alamat_nama_jalan=fields.get("alamat_nama_jalan", ""),
        input_produksi=_num_or_blank_str(fields.get("input_produksi")),
        proses_produksi=_num_or_blank_str(fields.get("proses_produksi")),
        varian_sudah_bpom=_num_or_blank(fields.get("varian_sudah_bpom")),
        tk_laki_total=str(pekerja.get("tk_laki_total", "")),
        tk_perempuan_total=str(pekerja.get("tk_perempuan_total", "")),
        tk_dibayar_total=str(pekerja.get("tk_dibayar_total", "")),
        tk_tidak_dibayar_total=str(pekerja.get("tk_tidak_dibayar_total", "")),
        rt=fields.get("rt", ""),
        rw=fields.get("rw", ""),
        no_hp_wa=fields.get("no_hp_wa", ""),
        nama_pengusaha=fields.get("nama_pengusaha", ""),
        jenis_kelamin=fields.get("jenis_kelamin", ""),
        umur=_num_or_blank(fields.get("umur")),
        kegiatan_utama=fields.get("kegiatan_utama", ""),
        b1_produksi_lokasi=fields.get("b1_produksi_lokasi", ""),
        b2_layanan_makan_minum=fields.get("b2_layanan_makan_minum", ""),
        b3_penjualan_barang=fields.get("b3_penjualan_barang", ""),
        tempat_usaha=fields.get("tempat_usaha", ""),
        produk_utama=fields.get("produk_utama", ""),
        jaringan_usaha=fields.get("jaringan_usaha", ""),
        pakai_internet=fields.get("pakai_internet", ""),
        produk_ramah_lingkungan=fields.get("produk_ramah_lingkungan", ""),
        input_ramah_lingkungan=fields.get("input_ramah_lingkungan", ""),
        karya_seni_budaya=fields.get("karya_seni_budaya", ""),
        izin_edar_bpom=_label_or_str(fields.get("izin_edar_bpom", "")),
        mitra_kdkmp=fields.get("mitra_kdkmp", ""),
        program_mbg=fields.get("program_mbg", ""),
        tahun_mulai_komersial=_num_or_blank(fields.get("tahun_mulai_komersial")),
        pekerja_laki2_dibayar=_num_or_blank(pekerja.get("pekerja_laki2_dibayar")),
        pekerja_perempuan_dibayar=_num_or_blank(pekerja.get("pekerja_perempuan_dibayar")),
        pekerja_tdk_dibayar=_num_or_blank(pekerja.get("pekerja_tdk_dibayar")),
    )
    src.kepemilikan_modal = best.get("kepemilikan_modal", {}) or {}
    src.sumber = "export"

    if jumlah_usaha > 1:
        src.catatan_scrape.append(
            f"1 keluarga punya {jumlah_usaha} usaha di sumber — dipilih '{best.get('nama_usaha_raw')}' "
            f"krn cocok persis dgn kolom P backlog."
        )
    pekerja_status = pekerja.get("status")
    if pekerja_status and "AMBIGU" in pekerja_status:
        src.catatan_scrape.append(
            f"pekerja {pekerja_status}: {pekerja.get('catatan', '')} — 24a/24b jangan ditebak, cek manual."
        )

    return ExportLookupResult(
        src, "OK", match_score=best_score, usaha_terpilih=best.get("nama_usaha_raw", ""),
        jumlah_usaha=jumlah_usaha,
    )


# ---------------------------------------------------------------------------
# Kodepos dari file export MENTAH
# ---------------------------------------------------------------------------
# Temuan 2026-09-07: kodepos SUDAH ADA di file export mentah fasih-sm
# (dataKey "kodepos", berpasangan dgn "var_desa" = kode desa 10 digit) —
# jadi TIDAK PERLU scraping situs kodepos manapun. Divalidasi silang thd
# KODEPOS_BY_IDSUBSLS: 41 dari 41 entri cocok persis, 0 bentrok.
#
# Dipakai sbg CADANGAN saja (config tetap menang) karena export bisa kotor:
#   - satu keluarga mengisi kodepos "99999" (placeholder) di desa 5108030013
#     yang kodepos benarnya 81154;
#   - satu baris punya var_desa "5108000000" (kode tingkat kabupaten, bukan
#     desa) sehingga tidak bisa dipetakan ke desa manapun.
# Karena itu: nilai per-DESA diambil secara mayoritas dari SEMUA file export,
# bukan dari satu file, dan nilai placeholder dibuang lebih dulu.

_KODEPOS_PLACEHOLDER = {"99999", "00000", "11111"}
_peta_kodepos_cache: Optional[dict] = None


def _kodepos_valid(nilai: str) -> bool:
    nilai = (nilai or "").strip()
    return nilai.isdigit() and len(nilai) == 5 and nilai not in _KODEPOS_PLACEHOLDER


def peta_kodepos_desa(export_dir: Path = EXPORT_DIR, paksa_muat_ulang: bool = False) -> dict:
    """{kode_desa_10_digit: {'kodepos': str, 'dukungan': int, 'varian': dict}}

    Dibangun dari SELURUH file export mentah (export/*.json, bukan
    *.converted.json). Hasilnya di-cache karena dipakai per-baris."""
    global _peta_kodepos_cache
    if _peta_kodepos_cache is not None and not paksa_muat_ulang:
        return _peta_kodepos_cache

    from collections import Counter, defaultdict

    hitung: dict = defaultdict(Counter)
    for path in export_dir.glob("*.json"):
        if path.name.endswith(".converted.json"):
            continue
        try:
            outer = json.loads(path.read_text(encoding="utf-8-sig"))
            record = outer.get("data", outer)
            inner = record.get("data")
            inner = json.loads(inner) if isinstance(inner, str) else inner
            jawaban = {a["dataKey"]: a["answer"] for a in (inner or {}).get("answers", [])}
        except Exception:
            continue  # file rusak/format lain — diam-diam dilewati, ini cuma cadangan
        desa = str(jawaban.get("var_desa") or "").strip()
        kp = str(jawaban.get("kodepos") or "").strip()
        if len(desa) == 10 and desa.isdigit() and _kodepos_valid(kp):
            hitung[desa][kp] += 1

    _peta_kodepos_cache = {
        desa: {"kodepos": c.most_common(1)[0][0], "dukungan": c.most_common(1)[0][1],
               "varian": dict(c)}
        for desa, c in hitung.items()
    }
    return _peta_kodepos_cache


def kodepos_dari_export(idsubsls: str, export_dir: Path = EXPORT_DIR) -> tuple:
    """-> (kodepos, keterangan). kodepos "" kalau tidak bisa ditentukan.

    Kodepos di Indonesia dialokasikan per DESA, jadi seluruh SLS/banjar dalam
    satu desa memakai kodepos yang sama — pencocokan sengaja di level desa
    (10 digit pertama idsubsls), bukan per-banjar."""
    desa = (idsubsls or "")[:10]
    if len(desa) != 10 or not desa.isdigit():
        return "", f"idsubsls '{idsubsls}' tidak berbentuk kode wilayah 16 digit"
    entri = peta_kodepos_desa(export_dir).get(desa)
    if not entri:
        return "", f"desa {desa} tidak ada di satu pun file export mentah"
    ket = f"desa {desa} dari export (dukungan {entri['dukungan']} file"
    if len(entri["varian"]) > 1:
        ket += f", varian {entri['varian']} -> dipakai mayoritas"
    return entri["kodepos"], ket + ")"
