#!/usr/bin/env python3
"""
reset_mitra.py — Siapkan reset password akun PPL di https://manajemen-mitra.bps.go.id/mitra/akun-mitra
supaya semua akun memakai FIXED_PASSWORD (inti/config_lokal.py) — password yang dipakai skrip login.

manajemen-mitra mendeteksi browser otomatis, jadi reset dijalankan dari Console Chrome biasa
(reset_mitra_console.js). File ini hanya menyiapkan target & menyuntikkannya ke template Console
— TIDAK membuka browser. Tutorial: reset_mitra/README.md.

    python reset_mitra/reset_mitra.py --daftar bahan/daftar_akun_ppl.txt --cek      # daftar akun, tanpa browser
    python reset_mitra/reset_mitra.py --daftar bahan/daftar_akun_ppl.txt --console  # -> reset_mitra/hasil/*.siap.js

Sumber akun (pilih satu): --daftar <txt, satu email per baris>, --email a@x.com,b@x.com, atau
--sumber <sheet> (kolom email PPL: "Akun PPL" di format tahap 2 / kolom akun di format agenda).
Kunci cocok = alamat gmail (username di manajemen-mitra). Cakupan PPL saja.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti import lokasi  # noqa: E402
from inti.config import FIXED_PASSWORD  # noqa: E402
from inti.gabungan_loader import load_gabungan  # noqa: E402
from inti.tahap2_loader import load_tahap2  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "reset_mitra_console.js"
KONSOL_SIAP = lokasi.hasil("reset_mitra") / "reset_mitra_console.siap.js"
TARGET_CSV = lokasi.hasil("reset_mitra") / "target_reset_mitra.csv"
PENANDA_TARGET = "/*__TARGET__*/[]"
PENANDA_PASSWORD = '/*__PASSWORD_BARU__*/""'


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


def baca_daftar_email(path: str) -> list[str]:
    """Email dari berkas teks: satu per baris, '#' = komentar, huruf kecil."""
    if not path:
        return []
    keluar = []
    for baris in Path(path).read_text(encoding="utf-8-sig").splitlines():
        baris = baris.split("#", 1)[0].strip().lower()
        if baris:
            keluar.append(baris)
    return keluar


def target_dari_email(emails: list[str]) -> list[dict]:
    """Target unik (urutan dipertahankan) utk --daftar/--email; email tanpa '@' dibuang."""
    lihat, keluar = set(), []
    for e in emails:
        if "@" in e and e not in lihat:
            lihat.add(e)
            keluar.append({"email": e, "baris": [], "contoh": ""})
    return keluar


def tulis_console(target, password_baru: str = FIXED_PASSWORD) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    for penanda in (PENANDA_TARGET, PENANDA_PASSWORD):
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    data = [{"email": t["email"], "baris": t["baris"]} for t in target]
    teks = (teks.replace(PENANDA_TARGET, json.dumps(data, ensure_ascii=False))
                .replace(PENANDA_PASSWORD, json.dumps(password_baru or "")))
    lokasi.siapkan(KONSOL_SIAP).write_text(teks, encoding="utf-8")
    return KONSOL_SIAP


def main():
    ap = argparse.ArgumentParser(description="Siapkan reset password akun PPL (manajemen-mitra) dari sheet input usaha")
    ap.add_argument("--daftar", default="", help="berkas .txt: satu email PPL per baris (# = komentar)")
    ap.add_argument("--sumber", default="", help="sheet input usaha (.xlsx/.csv) yang punya kolom email PPL")
    ap.add_argument("--format", choices=("tahap2", "agenda", "standar"), default="tahap2",
                    help="format --sumber (bawaan tahap2)")
    ap.add_argument("--cek", action="store_true", help="Cetak daftar email PPL + tulis target_reset_mitra.csv")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    ap.add_argument("--email", default=None, help="Batasi ke email tertentu, pisah koma")
    args = ap.parse_args()

    ingin = [s.strip().lower() for s in (args.email or "").split(",") if s.strip()]
    if args.sumber:
        rows = load_tahap2(args.sumber) if args.format == "tahap2" else load_gabungan(args.sumber)
        target = kumpulkan_ppl(rows)
        if ingin:
            target = [t for t in target if t["email"] in ingin]
        asal = args.sumber
    else:
        target = target_dari_email(ingin + baca_daftar_email(args.daftar))
        asal = args.daftar or "--email"
    if not target:
        print("❌ Tidak ada akun PPL: beri --daftar <txt>, --email, atau sheet dgn kolom email PPL.",
              file=sys.stderr)
        return 2

    if args.console:
        path = tulis_console(target)
        print(f"{path} ditulis: {len(target)} akun PPL.")
        if not FIXED_PASSWORD:
            print("⚠️ FIXED_PASSWORD kosong (inti/config_lokal.py) — mode manual/otomatis di Console akan menolak "
                  "jalan kecuali diberi jalankan({passwordBaru: \"...\"}).")
        print("⚠️ File .siap.js berisi email PPL & password baru — jangan dibagikan / di-commit.")
        print("Chrome biasa -> login manajemen-mitra -> buka /mitra/akun-mitra -> F12 Console -> tempel isi file itu ->")
        print('  await resetMitra.jalankan({mode: "petakan"})   (read-only; buktikan gmail menemukan mitra & rekam kontrol reset)')
        return 0

    total_baris = sum(len(t["baris"]) for t in target)
    print(f"=== AKUN PPL utk reset password dari {asal} ===")
    print(f"  {len(target)} akun PPL unik (dari {total_baris} baris sheet).")
    ganda = [t for t in target if len(t["baris"]) > 1]
    if ganda:
        print(f"  {len(ganda)} akun dipakai di >1 baris (reset cukup sekali per akun).")
    with lokasi.siapkan(TARGET_CSV).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["email", "jumlah_baris", "baris_sheet", "contoh_usaha"])
        for t in target:
            w.writerow([t["email"], len(t["baris"]), ",".join(map(str, t["baris"])), t["contoh"]])
    print(f"\nDaftar lengkap: {TARGET_CSV}")
    print("Berikutnya: ulangi perintah yang sama dgn --console (ganti --cek)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
