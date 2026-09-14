#!/usr/bin/env python3
"""
reset_mitra.py — Siapkan daftar akun PPL dari Agenda.xlsx untuk reset password
di https://manajemen-mitra.bps.go.id/mitra/akun-mitra.

Seperti ganti_moda: manajemen-mitra ada di balik login & kemungkinan mendeteksi
browser otomatis, jadi JALUR UTAMA-nya Console Chrome biasa
(reset_mitra_console.js). File ini hanya menyiapkan target & menyuntikkannya ke
template Console — TIDAK membuka browser, TIDAK menyentuh password.

⚠️ STATUS: struktur halaman akun-mitra BELUM pernah dilihat (login-gated).
Karena itu langkah pertama WAJIB "petakan"/"cocok" (read-only) di Console untuk
(1) membuktikan gmail di Agenda memang bisa menemukan mitranya, dan (2) merekam
kontrol "Reset Password" + dialog konfirmasinya. Reset sungguhan tetap diklik
MANUSIA sampai selektornya terverifikasi.

LANGKAH
-------
    python reset_mitra/reset_mitra.py --sumber Agenda.xlsx --cek       # daftar email PPL, tanpa browser
    python reset_mitra/reset_mitra.py --sumber Agenda.xlsx --console   # tulis reset_mitra_console.siap.js
Lalu di Chrome (login manmanajemen-mitra) -> F12 Console -> tempel file itu:
    await resetMitra.jalankan({mode: "petakan"})   // 1 email: cari & dump struktur, TANPA reset
    await resetMitra.jalankan({mode: "cocok"})      // cek semua email ketemu 1 mitra, TANPA reset
    // (mode "manual"/"otomatis" baru aktif setelah selektor reset diisi — lihat reset_mitra_console.js)

Cakupan: HANYA kolom "Akun PPL" (ditetapkan user 2026-09-14). PML tidak disentuh.
Kunci cocok: alamat gmail = username/pencarian di manajemen-mitra (ditetapkan user).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.gabungan_loader import load_gabungan  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "reset_mitra_console.js"
KONSOL_SIAP = Path("./reset_mitra_console.siap.js")
TARGET_CSV = Path("./target_reset_mitra.csv")
PENANDA_TARGET = "/*__TARGET__*/[]"


def kumpulkan_ppl(rows):
    """Email PPL unik (lowercase), urut kemunculan di sheet, + jumlah baris &
    contoh nama usaha (utk konteks saat meninjau). Baris tanpa email dilewati."""
    per: dict[str, dict] = {}
    for r in rows:
        email = r.akun_ppl
        if not email:
            continue
        e = per.setdefault(email, {"email": email, "baris": [], "contoh": r.nama})
        e["baris"].append(r.baris)
    return list(per.values())


def tulis_console(target) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    if teks.count(PENANDA_TARGET) != 1:
        raise ValueError(f"Penanda {PENANDA_TARGET} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    data = [{"email": t["email"], "baris": t["baris"]} for t in target]
    KONSOL_SIAP.write_text(teks.replace(PENANDA_TARGET, json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    return KONSOL_SIAP


def main():
    ap = argparse.ArgumentParser(description="Siapkan reset password akun PPL (manajemen-mitra) dari Agenda")
    ap.add_argument("--sumber", required=True, help="Agenda.xlsx (tab gabungan) atau .csv-nya")
    ap.add_argument("--cek", action="store_true", help="Cetak daftar email PPL + tulis target_reset_mitra.csv")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    ap.add_argument("--email", default=None, help="Batasi ke email tertentu, pisah koma")
    args = ap.parse_args()

    rows = load_gabungan(args.sumber)
    target = kumpulkan_ppl(rows)
    if args.email:
        ingin = {s.strip().lower() for s in args.email.split(",") if s.strip()}
        target = [t for t in target if t["email"] in ingin]

    if args.console:
        path = tulis_console(target)
        print(f"{path} ditulis: {len(target)} akun PPL.")
        print("Chrome biasa -> login manajemen-mitra -> buka /mitra/akun-mitra -> F12 Console -> tempel isi file itu ->")
        print('  await resetMitra.jalankan({mode: "petakan"})   (read-only; buktikan gmail menemukan mitra & rekam kontrol reset)')
        return 0

    total_baris = sum(len(t["baris"]) for t in target)
    print(f"=== AKUN PPL utk reset password dari {args.sumber} ===")
    print(f"  {len(target)} akun PPL unik (dari {total_baris} baris sheet).")
    ganda = [t for t in target if len(t["baris"]) > 1]
    if ganda:
        print(f"  {len(ganda)} akun dipakai di >1 baris (reset cukup sekali per akun).")
    with TARGET_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["email", "jumlah_baris", "baris_sheet", "contoh_usaha"])
        for t in target:
            w.writerow([t["email"], len(t["baris"]), ",".join(map(str, t["baris"])), t["contoh"]])
    print(f"\nDaftar lengkap: {TARGET_CSV}")
    print("Berikutnya: python reset_mitra/reset_mitra.py --sumber " + args.sumber + " --console")
    return 0


if __name__ == "__main__":
    sys.exit(main())
