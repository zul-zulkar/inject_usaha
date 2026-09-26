#!/usr/bin/env python3
"""test_bungkus_pc.py — uji OFFLINE aturan isi zip antar_pc/bungkus_pc.py.
Jalankan: python tests/test_bungkus_pc.py

Yang dikunci (struktur folder 2026-09-25): audit/ IKUT (zip dipakai menyebarkan hasil
gabung_audit ke semua PC sekaligus) kecuali audit per-PC (audit/pc/) & cadangan *.bak-*;
SEMUA folder hasil/ (keluaran alat) & arsip/ tidak ikut; sesi browser & cache tidak ikut;
bahan & config lokal ikut.

⚠️ Konsekuensi yang disengaja: meng-extract zip ini di PC yang SUDAH bekerja lagi akan
MENIMPA audit PC itu, dan ingatan anti-duplikatnya hilang. Zip hanya boleh disebar setelah
semua PC berhenti & auditnya digabung (antar_pc/README.md)."""

import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh Buleleng di config.py

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from pathlib import Path

from antar_pc.bungkus_pc import alasan_dibuang

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


print("\n== yang TIDAK ikut ==")
for path, kelompok in (("audit/audit_log_gabungan.csv.bak-20260924-081355", "cadangan"),
                       ("audit/batch21/audit_log_gabungan.csv.bak-20260924-081355", "cadangan"),
                       ("audit/pc/pc2/audit_log_gabungan.csv", "audit per-PC"),
                       ("audit/pc/hasil/laporan_gabung.csv", "audit per-PC"),
                       ("audit_pc/pc2.csv", "audit per-PC"),                 # lokasi lama
                       ("bahan_pc/pc2.xlsx", "audit per-PC"),
                       ("input_usaha/hasil/cek_input.csv", "keluaran alat"),
                       ("input_usaha/hasil/list_api_ppl.contoh_at_mail.com.json", "keluaran alat"),
                       ("input_usaha/hasil/log_screenshots/gagal.png", "keluaran alat"),
                       ("input_usaha/hasil/.proses_ppl_contoh_gmail_com.lock", "keluaran alat"),
                       ("approve_pml/hasil/.sesi_fasih_web_ppl_contoh_gmail_com.json", "keluaran alat"),
                       ("fasih_sm/pindah_wilayah/hasil/pindah_wilayah_console.siap.js", "keluaran alat"),
                       ("fasih_sm/ganti_moda/hasil/.profil_fasih_sm/Default/Cookies", "keluaran alat"),
                       ("antar_pc/hasil/split_usaha_pc_20260924-1128.zip", "keluaran alat"),
                       ("koordinat/hasil/input_usaha_koordinat.xlsx", "keluaran alat"),
                       ("arsip/Agenda.xlsx", "arsip"),
                       ("inti/__pycache__/config.cpython-312.pyc", "cache"),
                       (".git/HEAD", "cache"),
                       (".git.zip", "cache"),
                       (".claude/worktrees/x/inti/config.py", "cache"),
                       (".profil_fasih_sm/Default/Cookies", "sesi browser"),
                       (".sesi_fasih_web_ppl_contoh_gmail_com.json", "sesi browser"),
                       ("cek_gabungan.csv", "hasil turunan"),                # nama lama di akar
                       ("pindah_wilayah_console.siap.js", "hasil turunan")):
    cek(path, alasan_dibuang(Path(path)), kelompok)

print("\n== yang IKUT ==")
for path in ("audit/audit_log_gabungan.csv",   # sengaja IKUT (lihat docstring)
             "audit/batch21/audit_log_gabungan.csv", "audit/audit_approve_pml.csv",
             "audit/ganda_dihapus_202609241530.csv",   # catatan hapus admin — tidak bisa dibuat ulang
             "bahan/input_usaha.xlsx", "bahan/daftar_subsls.txt", "inti/config_lokal.py", "inti/config.py",
             "docs/ALUR_KERJA.md", "templates/input_usaha.xlsx", "CLAUDE.md", "input_usaha/jalankan.py",
             "fasih_sm/pindah_wilayah/pindah_wilayah_console.js", "input_usaha/kontrol_kualitas.py",
             "antar_pc/pindah_struktur.py"):
    cek(path, alasan_dibuang(Path(path)), "")

print("\n== --kecuali ==")
for path, kecuali, harap in (("audit/audit_log_gabungan.csv", ["audit"], "--kecuali"),
                             ("audit/sub/x.csv", ["audit"], "--kecuali"),
                             ("audit_log_gabungan.csv", ["audit"], ""),          # nama persis, bukan awalan
                             ("audit_log_gabungan.csv", ["audit_log_gabungan.csv"], "--kecuali"),
                             ("audit/audit_log_gabungan.csv", ["audit_log_gabungan.csv"], "--kecuali"),
                             ("bahan/lama/a.xlsx", ["bahan/lama"], "--kecuali"),
                             ("bahan/input_usaha.xlsx", ["bahan/lama"], ""),
                             ("audit/batch21/audit_log_gabungan.csv", ["audit/batch21"], "--kecuali"),
                             ("audit_malam/a.csv", ["audit*"], "--kecuali"),
                             ("audit/a.csv", ["audit\\"], "--kecuali"),          # garis miring Windows
                             ("audit/a.csv", [], "")):
    cek(f"{path} --kecuali {kecuali}", alasan_dibuang(Path(path), kecuali), harap)

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
