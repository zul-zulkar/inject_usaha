"""
lokasi.py — SATU tempat utk semua lokasi berkas proyek.

Aturannya sederhana (permintaan user 2026-09-25, "setiap file yang digenerate taruh
di folder subproyeknya"):

  bahan/            data masukan Anda (sheet input usaha, daftar kode/idsubsls)
  audit/            catatan dokumen input usaha (audit_log_gabungan.csv) — dipakai
                    bersama input_usaha, approve_pml, fasih_sm/*, antar_pc
  <alat>/hasil/     SEMUA yang dibuat alat itu: laporan, *.siap.js, log, screenshot,
                    sesi browser. Boleh dihapus kapan saja kecuali disebut lain di
                    README alatnya (mis. approve_pml/hasil/audit_approve_pml.csv).

Lokasi di sini ABSOLUT (dari akar proyek), jadi perintah tetap benar walau dijalankan
dari folder lain. Path yang Anda ketik sendiri (--sumber, --audit, ...) tetap relatif
thd folder tempat perintah dijalankan.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]

BAHAN = AKAR / "bahan"
AUDIT = AKAR / "audit"
NAMA_AUDIT = "audit_log_gabungan.csv"
AUDIT_BAWAAN = AUDIT / NAMA_AUDIT
# Catatan dokumen ganda yang SUDAH dihapus admin (unduhan hapusGanda.unduh()). Tidak bisa
# dibuat ulang -> disimpan bersama audit, bukan di hasil/.
POLA_GANDA_DIHAPUS = str(AUDIT / "ganda_dihapus*.csv")

# Audit di lokasi LAMA (sebelum 2026-09-25 audit bawaan ada di akar proyek). Kalau berkas
# ini masih ada, alat audit berhenti & menyuruh menjalankan antar_pc/pindah_struktur.py —
# supaya tidak ada run yang diam-diam memakai audit kosong lalu membuat dokumen GANDA.
AUDIT_LOKASI_LAMA = AKAR / NAMA_AUDIT


def hasil(*alat: str) -> Path:
    """Folder keluaran satu alat, mis. hasil("input_usaha") -> <akar>/input_usaha/hasil.
    Belum dibuat; pakai siapkan() sebelum menulis."""
    return AKAR.joinpath(*alat, "hasil")


def siapkan(path: Path) -> Path:
    """Buat folder induk `path` (kalau belum ada), kembalikan `path` apa adanya."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return Path(path)


HASIL_INPUT = hasil("input_usaha")
POLA_LIST_API = str(HASIL_INPUT / "list_api_*.json")
HASIL_APPROVE = hasil("approve_pml")
AUDIT_APPROVE = AUDIT / "audit_approve_pml.csv"   # catatan approve: tidak bisa dibuat ulang -> audit/


def jalur_audit(path: str | Path | None = "") -> Path:
    """Berkas audit utk nilai --audit / FASIH_AUDIT: folder -> <folder>/audit_log_gabungan.csv,
    berkas apa adanya, kosong -> AUDIT_BAWAAN."""
    if not path:
        return AUDIT_BAWAAN
    p = Path(path)
    if p.is_dir() or str(path).endswith(("/", "\\")) or not p.suffix:
        return p / NAMA_AUDIT
    return p


def audit_dari_lingkungan() -> Path:
    """Audit bawaan saat modul diimpor: FASIH_AUDIT kalau diisi, kalau tidak audit/."""
    return jalur_audit(os.environ.get("FASIH_AUDIT") or "")


def cari(pola: str | Path) -> list[Path]:
    """glob yang menerima pola absolut maupun relatif (Path().glob menolak pola absolut)."""
    return sorted(Path(p) for p in glob.glob(str(pola), recursive=True))


def cek_struktur_lama() -> None:
    """Hentikan program kalau PC ini belum pindah ke struktur folder 2026-09-25 (audit masih
    di akar proyek). Tanpa ini alat akan memakai audit/ yang KOSONG -> semua baris dianggap
    belum punya dokumen -> dokumen GANDA. Dipanggil di awal setiap alat yang memakai audit."""
    if AUDIT_LOKASI_LAMA.exists():
        raise SystemExit(
            f"⛔ Ditemukan {AUDIT_LOKASI_LAMA.name} di akar proyek (lokasi LAMA).\n"
            "   Struktur folder berubah 2026-09-25: audit sekarang di audit/, keluaran tiap alat di <alat>/hasil/.\n"
            "   Pindahkan dulu (sekali per PC, tidak menghapus apa pun):\n"
            "       python antar_pc/pindah_struktur.py            # lihat rencananya\n"
            "       python antar_pc/pindah_struktur.py --jalankan")
