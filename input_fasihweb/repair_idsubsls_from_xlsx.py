#!/usr/bin/env python3
"""
repair_idsubsls_from_xlsx.py — Perbaiki kolom idsubsls di salin_dokumen_sumber.csv
(nama lama: LKpenyalinan.csv)
yang rusak jadi notasi ilmiah (mis. "5.10808E+15") akibat export CSV dari
Google Sheets. Angka idsubsls 16-digit ini MASIH DALAM BATAS presisi exact
double-precision float (< 2^53), jadi export ke .xlsx (binary, bukan teks)
TIDAK memotong presisinya seperti CSV — openpyxl bisa baca nilai aslinya
utuh dari .xlsx, lalu dipakai utk menimpa HANYA sel idsubsls yang rusak di
CSV (kolom lain di CSV tidak disentuh).

CARA PAKAI:
    1. Di Google Sheets backlog salin dokumen sumber: File > Download > Microsoft Excel
       (.xlsx) — simpan di folder yang sama dgn skrip ini (atau path bebas,
       tinggal isi --xlsx).
    2. python3 repair_idsubsls_from_xlsx.py --xlsx "salin_dokumen_sumber.xlsx"
       (default --csv=salin_dokumen_sumber.csv, --out=timpa file yg sama, backup
       otomatis dibuat di salin_dokumen_sumber.csv.bak)

Skrip ini HANYA memperbaiki kolom idsubsls yg pola-nya kelihatan rusak
(mengandung 'E+'/'e+') — kolom lain & baris yg idsubsls-nya sudah normal
TIDAK disentuh sama sekali.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import openpyxl


def load_idsubsls_map_from_xlsx(xlsx_path: Path, sheet_name: str | None) -> dict[str, str]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter)
    header = [str(h).strip() if h is not None else "" for h in header]

    try:
        no_idx = header.index("No")
    except ValueError:
        raise SystemExit(f"Kolom 'No' tidak ketemu di header xlsx: {header}")
    try:
        idsubsls_idx = header.index("idsubsls")
    except ValueError:
        raise SystemExit(f"Kolom 'idsubsls' tidak ketemu di header xlsx: {header}")

    out: dict[str, str] = {}
    for r in rows_iter:
        if r is None or no_idx >= len(r):
            continue
        no_val = r[no_idx]
        if no_val is None or str(no_val).strip() == "":
            continue
        no_key = str(no_val).strip()
        if no_key.endswith(".0"):
            no_key = no_key[:-2]

        raw_id = r[idsubsls_idx] if idsubsls_idx < len(r) else None
        if raw_id is None:
            continue
        # openpyxl (data_only) memberi nilai numerik asli (int/float) tanpa
        # dipotong notasi ilmiah — float 16-digit ini masih < 2^53, jadi
        # exact, aman dikonversi ke int lalu string.
        if isinstance(raw_id, float):
            if raw_id.is_integer():
                id_str = str(int(raw_id))
            else:
                id_str = repr(raw_id)
        else:
            id_str = str(raw_id).strip()
        out[no_key] = id_str
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", required=True, help="Path file .xlsx hasil download Google Sheets backlog salin dokumen sumber")
    ap.add_argument("--sheet", default=None, help="Nama sheet/tab di xlsx (default: sheet aktif pertama)")
    ap.add_argument("--csv", default="salin_dokumen_sumber.csv", help="Path CSV yang mau diperbaiki (default: salin_dokumen_sumber.csv)")
    ap.add_argument("--out", default=None, help="Path output (default: timpa --csv, backup otomatis dibuat)")
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx)
    csv_path = Path(args.csv)
    out_path = Path(args.out) if args.out else csv_path

    if not xlsx_path.exists():
        raise SystemExit(f"File xlsx tidak ditemukan: {xlsx_path}")
    if not csv_path.exists():
        raise SystemExit(f"File csv tidak ditemukan: {csv_path}")

    id_map = load_idsubsls_map_from_xlsx(xlsx_path, args.sheet)
    print(f"Terbaca {len(id_map)} baris idsubsls dari xlsx.")

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    fixed, already_ok, not_found, no_col_match = 0, 0, 0, 0
    for row in rows:
        no_key = (row.get("No") or "").strip()
        current = (row.get("idsubsls") or "").strip()
        looks_broken = "e+" in current.lower()
        if not looks_broken:
            already_ok += 1
            continue
        new_val = id_map.get(no_key)
        if new_val is None:
            not_found += 1
            print(f"  ⚠️ No {no_key}: idsubsls rusak ('{current}') tapi TIDAK ketemu di xlsx — dibiarkan apa adanya, cek manual.")
            continue
        if "e+" in new_val.lower():
            no_col_match += 1
            print(f"  ⚠️ No {no_key}: nilai dari xlsx JUGA masih notasi ilmiah ('{new_val}') — kemungkinan kolom idsubsls di sheet-nya sendiri berformat Number/Automatic, bukan Plain text. Dibiarkan, cek manual/format sel di sheet.")
            continue
        row["idsubsls"] = new_val
        print(f"  ✓ No {no_key}: '{current}' -> '{new_val}'")
        fixed += 1

    print(f"\nRingkasan: fixed={fixed}, sudah_normal={already_ok}, rusak_tapi_tdk_ketemu_di_xlsx={not_found}, xlsx_jg_rusak={no_col_match}")

    if fixed == 0:
        print("Tidak ada perubahan — CSV output TIDAK ditulis ulang.")
        return

    if out_path == csv_path:
        backup_path = csv_path.with_suffix(csv_path.suffix + ".bak")
        shutil.copy2(csv_path, backup_path)
        print(f"Backup asli disimpan di: {backup_path}")

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"CSV diperbaiki ditulis ke: {out_path}")


if __name__ == "__main__":
    main()
