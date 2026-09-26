#!/usr/bin/env python3
"""
bungkus_pc.py — bungkus folder proyek jadi SATU .zip ringan untuk dibawa ke PC lain.

IKUT: kode, docs, templat, bahan/, audit/ (audit_log_gabungan.csv, audit_approve_pml.csv,
ganda_dihapus*.csv, audit batch lain spt audit/batch21/) & inti/config_lokal.py.
TIDAK IKUT:

  cache & sampah    __pycache__/, *.pyc, .git/, *.zip, .claude/
  keluaran alat     semua folder hasil/ (laporan, *.siap.js, list_api_*.json, log,
                    screenshot, sesi browser) — dibuat ulang oleh alatnya sendiri
  sesi browser      .profil_*/, .sesi_*.json, .proses_*.lock -> login ulang di PC tujuan
  audit per-PC      audit/pc/ (audit PC lain sebelum digabung) & cadangan *.bak-*
  arsip             arsip/ (data lama yang sudah tidak dipakai)

⚠️ audit/ IKUT supaya hasil gabung_audit tersebar ke semua PC sekaligus. Meng-extract zip
di PC yang masih punya pekerjaan BELUM digabung akan MENIMPA audit PC itu (ingatan
anti-duplikatnya hilang) — sebar zip hanya sesudah semua PC berhenti & auditnya digabung.

⚠️ Zip ini berisi DATA RESPONDEN & PASSWORD (config_lokal.py). Pindahkan lewat
flashdisk/drive kantor — jangan diunggah ke tempat publik.

    python antar_pc/bungkus_pc.py --daftar     # lihat isi & ukurannya saja
    python antar_pc/bungkus_pc.py              # buat antar_pc/hasil/split_usaha_pc_<waktu>.zip
    python antar_pc/bungkus_pc.py --kode-saja    # kode saja: utk PC yang masih bekerja (audit-nya aman)
    python antar_pc/bungkus_pc.py --kecuali audit/batch21   # buang folder/berkas tertentu

Tutorial (termasuk extract di PC tujuan): antar_pc/README.md.
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
sys.path.insert(0, str(ROOT))
from inti import lokasi  # noqa: E402

# (kelompok, pola) — folder dicocokkan per nama komponen path, berkas per nama berkas.
FOLDER_DIBUANG: list[tuple[str, str]] = [
    ("cache", "__pycache__"), ("cache", ".pytest_cache"), ("cache", ".git"), ("cache", ".claude"),
    ("cache", ".venv"), ("cache", "venv"), ("cache", "node_modules"),
    ("sesi browser", ".profil_*"),
    ("keluaran alat", "hasil"),
    ("log", "log_screenshots"), ("log", "log_fasih_sm"), ("log", "log_approve"),
    ("audit per-PC", "audit_pc"), ("audit per-PC", "bahan_pc"),
    ("arsip", "arsip"),
    ("hasil turunan", "kontrol_kualitas_per_ppl"),
]
# Folder yang dibuang berdasarkan PATH relatif (bukan nama saja): "pc" di tempat lain boleh ikut.
PATH_DIBUANG: list[tuple[str, str]] = [
    ("audit per-PC", "audit/pc"),
]
BERKAS_DIBUANG: list[tuple[str, str]] = [
    ("cache", "*.pyc"), ("cache", "*.zip"), ("cache", "nul"),
    ("sesi browser", ".sesi_*.json"), ("sesi browser", ".proses_*.lock"),
    # audit/audit_log_gabungan.csv SENGAJA ikut: zip dipakai menyebarkan hasil gabung_audit
    # ke semua PC sekaligus. Risikonya (menimpa audit PC yang masih bekerja) diperingatkan
    # saat zip dibuat — lihat akhir main().
    ("cadangan", "*.bak-*"),
    ("hasil turunan", "cek_gabungan.csv"), ("hasil turunan", "rangkum_audit.csv"),
    ("hasil turunan", "bersihkan_error.csv"), ("hasil turunan", "laporan_gabung*.csv"),
    ("hasil turunan", "sinkron_list.csv"), ("hasil turunan", "dokumen_tanpa_url.csv"),
    ("hasil turunan", "rencana_ubah_wilayah.csv"), ("hasil turunan", "*.siap.js"),
    ("hasil turunan", "list_api_*.json"),
    ("hasil turunan", "daftar_ganda.csv"),
    ("hasil turunan", "kontrol_kualitas*.xlsx"), ("hasil turunan", "kontrol_kualitas*.csv"),
]


KELOMPOK_KECUALI = "--kecuali"
# --kode-saja: data & pengaturan milik PC tujuan tidak ikut (extract tidak menimpanya).
KECUALI_KODE_SAJA = ("audit", "bahan", "inti/config_lokal.py", "gui/pengaturan.json*")


def cocok_kecuali(rel: Path, kecuali: tuple[str, ...] | list[str]) -> bool:
    """True kalau path relatif cocok salah satu pola --kecuali: pola tanpa '/' dicocokkan ke
    SETIAP komponen path (jadi 'audit' membuang folder audit/ di mana pun, 'audit_log_gabungan.csv'
    membuang berkas itu di mana pun); pola ber-'/' dicocokkan ke path relatif utuh & awalannya
    ('audit_pc2/lama' membuang isi folder itu saja)."""
    posix = rel.as_posix()
    for pola in kecuali:
        pola = pola.replace("\\", "/").strip("/")
        if not pola:
            continue
        if "/" in pola:
            if fnmatch.fnmatch(posix, pola) or fnmatch.fnmatch(posix, pola + "/*"):
                return True
        elif any(fnmatch.fnmatch(bagian, pola) for bagian in rel.parts):
            return True
    return False


def alasan_dibuang(rel: Path, kecuali: tuple[str, ...] | list[str] = ()) -> str:
    """Kelompok pengecualian utk path relatif thd root, "" = ikut dibungkus.
    Fungsi murni (diuji tests/test_bungkus_pc.py)."""
    if cocok_kecuali(rel, kecuali):
        return KELOMPOK_KECUALI
    posix = rel.as_posix()
    for kelompok, awalan in PATH_DIBUANG:
        if posix == awalan or posix.startswith(awalan + "/"):
            return kelompok
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


def pindai(root: Path, kecuali: tuple[str, ...] | list[str] = ()
           ) -> tuple[list[Path], dict[str, list[tuple[Path, int]]]]:
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
                kel = KELOMPOK_KECUALI if cocok_kecuali(rel, kecuali) else next(
                    (k for k, awalan in PATH_DIBUANG if rel.as_posix() == awalan), "") or next(
                    (k for k, pola in FOLDER_DIBUANG if fnmatch.fnmatch(p.name, pola)), "")
                if kel:
                    buang[kel].append((rel, ukuran_folder(p)))
                else:
                    tumpukan.append(p)
                continue
            kel = alasan_dibuang(rel, kecuali)
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


def audit_rusak_excel(path: Path) -> str:
    """Pesan kalau audit pernah disimpan ulang Excel (kunci/idsubsls rusak), "" kalau utuh."""
    if not path.exists():
        return ""
    import csv
    import input_usaha.mesin as mg
    with path.open(newline="", encoding="utf-8-sig") as f:
        rusak = mg.kerusakan_excel(list(csv.DictReader(f)))
    return mg.pesan_audit_rusak(rusak, path.name) if rusak else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bungkus proyek jadi satu .zip ringan utk PC lain")
    ap.add_argument("--daftar", action="store_true", help="tampilkan isi & ukuran saja, TANPA membuat zip")
    ap.add_argument("--rinci", action="store_true", help="cetak setiap berkas yang ikut (bukan cuma ringkasan)")
    ap.add_argument("--keluaran", help="nama berkas zip (bawaan antar_pc/hasil/split_usaha_pc_<waktu>.zip)")
    ap.add_argument("--kecuali", action="append", default=[], metavar="POLA",
                    help="buang folder/berkas ini juga (boleh diulang; nama mis. 'audit' = folder audit/ di "
                         "mana pun, path relatif mis. 'bahan/lama', wildcard mis. '*.bak')")
    ap.add_argument("--kode-saja", action="store_true",
                    help="HANYA kode/dokumen/templat: tanpa audit/, bahan/, inti/config_lokal.py & "
                         "gui/pengaturan.json. Pakai utk "
                         "memperbarui kode di PC yang masih punya pekerjaan (audit-nya tidak tertimpa)")
    args = ap.parse_args(argv)

    kecuali = list(args.kecuali) + (list(KECUALI_KODE_SAJA) if args.kode_saja else [])
    ikut, buang = pindai(ROOT, kecuali)
    ukuran = {rel: (ROOT / rel).stat().st_size for rel in ikut}
    rusak = "" if args.kode_saja else audit_rusak_excel(lokasi.AUDIT_BAWAAN)
    if rusak and not args.daftar:
        # Zip ini dipakai menyebar audit ke PC lain — audit rusak akan ikut menyebar.
        print("❌ " + rusak)
        return 2

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
    keluaran = lokasi.siapkan(Path(args.keluaran) if args.keluaran
                              else lokasi.hasil("antar_pc") / f"split_usaha_pc_{waktu}.zip")
    with zipfile.ZipFile(keluaran, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in ikut:
            zf.write(ROOT / rel, arcname=f"split_usaha/{rel.as_posix()}")
    print(f"\nZip dibuat : {keluaran}  ({mb(keluaran.stat().st_size).strip()})")
    print("Berisi data responden & password (inti/config_lokal.py) — pindahkan lewat flashdisk/drive kantor.")
    if lokasi.AUDIT_BAWAAN in (ROOT / r for r in ikut):
        print()
        print("⚠️  audit/ IKUT di zip. Meng-extract-nya di PC yang SUDAH bekerja lagi akan MENIMPA audit")
        print("    PC itu — ingatan anti-duplikatnya hilang & dokumen bisa terbuat GANDA.")
        print("    Sebar hanya sesudah semua PC berhenti & auditnya digabung (antar_pc/README.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
