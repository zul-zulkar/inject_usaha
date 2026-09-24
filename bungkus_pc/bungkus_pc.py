#!/usr/bin/env python3
"""
bungkus_pc.py — bungkus folder proyek jadi SATU .zip ringan untuk dibawa ke PC lain.

Isi zip: kode, dokumen, templat, bahan Excel/CSV & data kerja lain (termasuk
inti/config_lokal.py). Yang TIDAK ikut:

  cache & sampah    __pycache__/, *.pyc, .git/, *.zip (mis. .git.zip), .claude/
  sesi browser      .profil_*/ (cookie login, puluhan MB), .sesi_*.json, .proses_*.lock
                    -> login ulang di PC tujuan, sesi PC ini tidak berlaku di sana
  log               log_screenshots/, log_fasih_sm/, log_approve/
  AUDIT GABUNGAN    audit_log_gabungan.csv (+ .bak-*) & audit_pc/ — SENGAJA: kalau
                    ikut, meng-extract zip di PC yang sudah bekerja akan MENIMPA
                    audit PC itu (ingatan anti-duplikatnya hilang). Audit dipindah
                    lewat gabung_audit.py, bukan lewat zip.
  hasil turunan     laporan yang dibuat ulang oleh perintahnya sendiri (cek_gabungan.csv,
                    rangkum_audit.csv, bersihkan_error.csv, laporan_gabung*.csv,
                    sinkron_list.csv, *.siap.js, list_api_*.json, ...)

⚠️ Zip ini berisi DATA RESPONDEN & PASSWORD (config_lokal.py). Pindahkan lewat
flashdisk/drive kantor — jangan diunggah ke tempat publik.

    python bungkus_pc/bungkus_pc.py --daftar     # lihat isi & ukurannya saja, tanpa membuat zip
    python bungkus_pc/bungkus_pc.py              # buat split_usaha_pc_<waktu>.zip di folder proyek

Panduan lengkap (termasuk cara extract di PC tujuan): docs/MULAI_CEPAT.md.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent

# (kelompok, pola) — folder dicocokkan per nama komponen path, berkas per nama berkas.
FOLDER_DIBUANG: list[tuple[str, str]] = [
    ("cache", "__pycache__"), ("cache", ".pytest_cache"), ("cache", ".git"), ("cache", ".claude"),
    ("cache", ".venv"), ("cache", "venv"), ("cache", "node_modules"),
    ("sesi browser", ".profil_*"),
    ("log", "log_screenshots"), ("log", "log_fasih_sm"), ("log", "log_approve"),
    ("audit gabungan", "audit_pc"),
]
BERKAS_DIBUANG: list[tuple[str, str]] = [
    ("cache", "*.pyc"), ("cache", "*.zip"), ("cache", "nul"),
    ("sesi browser", ".sesi_*.json"), ("sesi browser", ".proses_*.lock"),
    # ("audit gabungan", "audit_log_gabungan.csv"),
    ("audit gabungan", "audit_log_gabungan.csv.bak-*"),
    ("audit gabungan", "*.bak-*"),
    ("hasil turunan", "cek_gabungan.csv"), ("hasil turunan", "rangkum_audit.csv"),
    ("hasil turunan", "bersihkan_error.csv"), ("hasil turunan", "laporan_gabung*.csv"),
    ("hasil turunan", "sinkron_list.csv"), ("hasil turunan", "dokumen_tanpa_url.csv"),
    ("hasil turunan", "rencana_ubah_wilayah.csv"), ("hasil turunan", "*.siap.js"),
    ("hasil turunan", "list_api_*.json"),
]


def alasan_dibuang(rel: Path) -> str:
    """Kelompok pengecualian utk path relatif thd root, "" = ikut dibungkus.
    Fungsi murni (diuji tests/test_bungkus_pc.py)."""
    for bagian in rel.parts[:-1]:
        for kelompok, pola in FOLDER_DIBUANG:
            if fnmatch.fnmatch(bagian, pola):
                return kelompok
    nama = rel.name
    for kelompok, pola in FOLDER_DIBUANG:        # rel bisa berupa folder itu sendiri
        if fnmatch.fnmatch(nama, pola) and len(rel.parts) == 1 and (ROOT / rel).is_dir():
            return kelompok
    for kelompok, pola in BERKAS_DIBUANG:
        if fnmatch.fnmatch(nama, pola):
            return kelompok
    return ""


def pindai(root: Path) -> tuple[list[Path], dict[str, list[tuple[Path, int]]]]:
    """-> (berkas yang ikut, {kelompok: [(berkas, ukuran)]} yang dibuang).
    Folder yang dibuang tidak ditelusuri isinya (profil browser ribuan berkas)."""
    ikut: list[Path] = []
    buang: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    tumpukan = [root]
    while tumpukan:
        folder = tumpukan.pop()
        for p in sorted(folder.iterdir()):
            rel = p.relative_to(root)
            if p.is_dir():
                kel = next((k for k, pola in FOLDER_DIBUANG if fnmatch.fnmatch(p.name, pola)), "")
                if kel:
                    buang[kel].append((rel, ukuran_folder(p)))
                else:
                    tumpukan.append(p)
                continue
            kel = alasan_dibuang(rel)
            if kel:
                buang[kel].append((rel, p.stat().st_size))
            else:
                ikut.append(rel)
    return sorted(ikut), buang


def ukuran_folder(folder: Path) -> int:
    total = 0
    for p in folder.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def mb(n: int) -> str:
    return f"{n / 1_048_576:7.1f} MB" if n >= 1_048_576 else f"{n / 1024:7.0f} KB"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bungkus proyek jadi satu .zip ringan utk PC lain")
    ap.add_argument("--daftar", action="store_true", help="tampilkan isi & ukuran saja, TANPA membuat zip")
    ap.add_argument("--rinci", action="store_true", help="cetak setiap berkas yang ikut (bukan cuma ringkasan)")
    ap.add_argument("--keluaran", help="nama berkas zip (bawaan split_usaha_pc_<waktu>.zip di folder proyek)")
    args = ap.parse_args(argv)

    ikut, buang = pindai(ROOT)
    ukuran = {rel: (ROOT / rel).stat().st_size for rel in ikut}

    print(f"Folder proyek : {ROOT}")
    print(f"\n=== IKUT DIBUNGKUS: {len(ikut)} berkas, {mb(sum(ukuran.values())).strip()} sebelum dikompres ===")
    per_folder: dict[str, list[Path]] = defaultdict(list)
    for rel in ikut:
        per_folder[rel.parts[0] if len(rel.parts) > 1 else "(root)"].append(rel)
    for folder, isi in sorted(per_folder.items(), key=lambda t: -sum(ukuran[r] for r in t[1])):
        print(f"  {mb(sum(ukuran[r] for r in isi))}  {len(isi):4d} berkas  {folder}")
    if args.rinci:
        for rel in ikut:
            print(f"      {mb(ukuran[rel])}  {rel.as_posix()}")
    terbesar = sorted(ikut, key=lambda r: -ukuran[r])[:8]
    print("  berkas terbesar: " + ", ".join(f"{r.as_posix()} ({mb(ukuran[r]).strip()})" for r in terbesar))

    print("\n=== TIDAK IKUT ===")
    for kel, isi in sorted(buang.items(), key=lambda t: -sum(u for _, u in t[1])):
        contoh = ", ".join(r.as_posix() for r, _ in isi[:4]) + (f", +{len(isi) - 4} lagi" if len(isi) > 4 else "")
        print(f"  {mb(sum(u for _, u in isi))}  {kel:15s} {contoh}")

    if args.daftar:
        print("\n(--daftar: zip TIDAK dibuat)")
        return 0

    waktu = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    keluaran = Path(args.keluaran) if args.keluaran else ROOT / f"split_usaha_pc_{waktu}.zip"
    with zipfile.ZipFile(keluaran, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in ikut:
            zf.write(ROOT / rel, arcname=f"split_usaha/{rel.as_posix()}")
    print(f"\nZip dibuat : {keluaran}  ({mb(keluaran.stat().st_size).strip()})")
    print("Berisi data responden & password (inti/config_lokal.py) — pindahkan lewat flashdisk/drive kantor.")
    # print("audit_log_gabungan.csv TIDAK ada di zip — lihat docs/MULAI_CEPAT.md bagian 'Pindah ke PC lain'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
