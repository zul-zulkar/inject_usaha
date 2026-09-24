#!/usr/bin/env python3
"""test_bungkus_pc.py — uji OFFLINE aturan isi zip bungkus_pc.py.
Jalankan: python tests/test_bungkus_pc.py

Yang dikunci: audit gabungan `audit_log_gabungan.csv` IKUT (2026-09-24 — zip
dipakai menyebarkan hasil gabung_audit ke semua PC sekaligus), tapi CADANGANNYA
(`*.bak-*`) & audit per-PC (`audit_pc/`) tetap tidak ikut; sesi browser & cache
tidak ikut; bahan & config lokal ikut.

⚠️ Konsekuensi yang disengaja: meng-extract zip ini di PC yang SUDAH bekerja lagi
akan MENIMPA audit PC itu, dan ingatan anti-duplikatnya hilang. Zip hanya boleh
disebar setelah semua PC berhenti & auditnya digabung (docs/PANDUAN_GABUNG_AUDIT.md)."""

import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh Buleleng di config.py

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from pathlib import Path

from bungkus_pc.bungkus_pc import alasan_dibuang

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


print("\n== yang TIDAK ikut ==")
for path, kelompok in (("audit_log_gabungan.csv.bak-20260924-081355", "audit gabungan"),
                       ("audit_pc/pc2.csv", "audit gabungan"),
                       ("inti/__pycache__/config.cpython-312.pyc", "cache"),
                       (".git/HEAD", "cache"),
                       (".git.zip", "cache"),
                       ("split_usaha_pc_20260924-1128.zip", "cache"),
                       (".claude/worktrees/x/inti/config.py", "cache"),
                       (".profil_fasih_sm/Default/Cookies", "sesi browser"),
                       (".sesi_fasih_web_ppl_contoh_gmail_com.json", "sesi browser"),
                       (".proses_ppl_contoh_gmail_com.lock", "sesi browser"),
                       ("log_screenshots/gagal.png", "log"),
                       ("cek_gabungan.csv", "hasil turunan"),
                       ("rangkum_audit.csv", "hasil turunan"),
                       ("list_api_ppl.contoh_at_mail.com.json", "hasil turunan"),
                       ("pindah_wilayah_console.siap.js", "hasil turunan"),
                       ("kontrol_kualitas.xlsx", "hasil turunan"),
                       ("kontrol_kualitas_tahap2.csv", "hasil turunan"),
                       ("kontrol_kualitas_per_ppl/I_KETUT_CONTOH.xlsx", "hasil turunan"),
                       ("daftar_ganda.csv", "hasil turunan")):
    cek(path, alasan_dibuang(Path(path)), kelompok)

print("\n== yang IKUT ==")
for path in ("audit_log_gabungan.csv",   # sengaja IKUT sejak 2026-09-24 (lihat docstring)
             "bahan/input_tahap2.xlsx", "Agenda.xlsx", "inti/config_lokal.py", "inti/config.py",
             "export/2510_abc.converted.json", "audit_approve_pml.csv", "docs/MULAI_CEPAT.md",
             "templates/input_usaha.kosong.xlsx", "CLAUDE.md", "input_tahap2/main_tahap2.py",
             "pindah_wilayah/pindah_wilayah_console.js", "input_gabungan/kontrol_kualitas.py",
             "ganda_dihapus_202609241530.csv"):   # catatan hapus admin — tidak bisa dibuat ulang
    cek(path, alasan_dibuang(Path(path)), "")

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
