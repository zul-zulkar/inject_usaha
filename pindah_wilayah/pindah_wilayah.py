#!/usr/bin/env python3
"""
pindah_wilayah.py — Siapkan "Ubah Wilayah" (Change Region) assignment hasil suntik
mode satu subsls ke idsubsls aslinya (kolom idsubsls sheet Agenda) di fasih-sm.

fasih-sm menolak Playwright, jadi JALUR-nya Console Chrome biasa
(pindah_wilayah_console.js). File ini hanya membaca sheet Agenda + audit dan
menyuntikkan target ke template Console — TIDAK membuka browser, TIDAK butuh VPN.

Per baris Agenda (unik per `kunci`):
  - tujuan  = kolom idsubsls (ketetapan user)
  - nama    = nama dokumen di fasih (row.nama_dokumen, dinormalkan huruf besar)
  - ids     = ID dokumen dari dokumen_url audit_log_gabungan.csv (boleh kosong:
              sebagian dokumen diinput di perangkat lain -> dicocokkan lewat nama)
  - nama yang dipakai >1 baris ditandai `g` -> Console TIDAK mencocokkan lewat nama.
Subsls ASAL = idsubsls_input audit (+ --subsls-asal). Status APPROVED, pencocokan
dokumen, wilayah tujuan & petugas diperiksa di Console terhadap data server.

LANGKAH
-------
    python pindah_wilayah/pindah_wilayah.py --sumber Agenda.xlsx --sumber Agenda1-1.xlsx \
        --sumber Agenda2.xlsx --console
Lalu di Chrome (login fasih-sm, halaman Data survei) -> F12 Console -> tempel
pindah_wilayah_console.siap.js:
    await pindahWilayah.jalankan({mode: "petakan"})             // READ-ONLY, sekali: cari semua dokumen
    await pindahWilayah.jalankan({mode: "cek", limit: 20})      // READ-ONLY per ID dari peta
    await pindahWilayah.jalankan({mode: "eksekusi", limit: 1})  // 1 dokumen, cek hasilnya
    await pindahWilayah.jalankan({mode: "eksekusi"})            // sisanya
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.gabungan_loader import GabunganRow, load_gabungan
import input_gabungan.main_gabungan as mg
from input_gabungan.sinkron_list import id_dari_url, norm

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "pindah_wilayah_console.js"
KONSOL_SIAP = Path("./pindah_wilayah_console.siap.js")
PENANDA_TARGET = "/*__TARGET__*/[]"
PENANDA_ASAL = "/*__ASAL__*/[]"
POLA_KODE = re.compile(r"5108\d{12}")


def bangun_target(sumber_rows: list[tuple[str, GabunganRow]], audit: list[dict]):
    """Fungsi murni -> (target[], masalah[(sumber, baris, pesan)], ringkasan Counter)."""
    ids_per_kunci = defaultdict(set)
    for b in audit:
        doc_id = id_dari_url(b.get("dokumen_url"))
        if b.get("kunci") and doc_id:
            ids_per_kunci[b["kunci"]].add(doc_id)

    ringkasan = Counter()
    masalah = []
    baris_unik: dict[str, tuple[str, GabunganRow]] = {}
    for sumber, row in sumber_rows:
        if not POLA_KODE.fullmatch(row.idsubsls or ""):
            masalah.append((sumber, row.baris, f"idsubsls tujuan '{row.idsubsls}' bukan 16 digit berawalan 5108"))
            continue
        if row.kunci in baris_unik:
            ringkasan["baris_kembar_digabung"] += 1
            continue
        baris_unik[row.kunci] = (sumber, row)

    kunci_per_nama = defaultdict(set)
    for kunci, (_, row) in baris_unik.items():
        kunci_per_nama[norm(row.nama_dokumen)].add(kunci)

    target = []
    for kunci, (sumber, row) in baris_unik.items():
        n = norm(row.nama_dokumen)
        t = {"k": kunci, "s": Path(sumber).name, "b": row.baris, "n": n, "t": row.idsubsls,
             "p": row.akun_ppl, "ids": sorted(ids_per_kunci.get(kunci, ()))}
        if len(kunci_per_nama[n]) > 1:
            t["g"] = 1
            ringkasan["nama_ganda"] += 1
        ringkasan["dgn_id_audit" if t["ids"] else "tanpa_id_audit"] += 1
        target.append(t)
    return target, masalah, ringkasan


def subsls_asal(audit: list[dict], tambahan: list[str]) -> tuple[list[str], list[str]]:
    """-> (asal unik terurut, token tidak valid). Asal = idsubsls_input audit + tambahan."""
    kode = {b.get("idsubsls_input", "").strip() for b in audit} | {x.strip() for x in tambahan}
    kode.discard("")
    return sorted(k for k in kode if POLA_KODE.fullmatch(k)), sorted(k for k in kode if not POLA_KODE.fullmatch(k))


def tulis_console(target: list[dict], asal: list[str]) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    for penanda in (PENANDA_TARGET, PENANDA_ASAL):
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    teks = teks.replace(PENANDA_TARGET, json.dumps(target, ensure_ascii=False, separators=(",", ":")))
    teks = teks.replace(PENANDA_ASAL, json.dumps(asal))
    KONSOL_SIAP.write_text(teks, encoding="utf-8")
    return KONSOL_SIAP


def main() -> int:
    ap = argparse.ArgumentParser(description="Siapkan pindah wilayah assignment (fasih-sm) dari sheet Agenda")
    ap.add_argument("--sumber", action="append", required=True, help="xlsx/csv sheet Agenda (boleh berulang)")
    ap.add_argument("--subsls-asal", action="append", default=[],
                    help="subsls tempat dokumen disuntik, selain yang tercatat di audit (boleh berulang)")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    args = ap.parse_args()

    sumber_rows = []
    for s in args.sumber:
        rows = load_gabungan(s)
        print(f"{s}: {len(rows)} baris")
        sumber_rows += [(s, r) for r in rows]
    audit = mg._baca_audit()
    target, masalah, ringkasan = bangun_target(sumber_rows, audit)
    asal, asal_salah = subsls_asal(audit, args.subsls_asal)

    print(f"\n{len(target)} baris unik jadi target | dgn ID audit: {ringkasan['dgn_id_audit']}, "
          f"tanpa ID audit (dicocokkan lewat nama): {ringkasan['tanpa_id_audit']}")
    if ringkasan["baris_kembar_digabung"]:
        print(f"  {ringkasan['baris_kembar_digabung']} baris kembar (kunci sama di beberapa sheet) digabung")
    if ringkasan["nama_ganda"]:
        print(f"  ⚠️ {ringkasan['nama_ganda']} baris memakai nama dokumen yang sama dgn baris lain -> "
              "hanya bisa dicocokkan lewat ID audit")
    for kec, n in sorted(Counter(t["t"][:7] for t in target).items()):
        print(f"  tujuan kec {kec}: {n}")
    print(f"Subsls asal ({len(asal)}): {', '.join(asal) or '-'}")
    if masalah:
        print(f"\n⛔ {len(masalah)} baris dilewati (tidak masuk target):")
        for sumber, baris, pesan in masalah[:20]:
            print(f"  {sumber} baris {baris}: {pesan}")
    if asal_salah:
        print(f"⛔ subsls asal tidak valid: {asal_salah} — perbaiki audit/--subsls-asal dulu.")
        return 1
    if not asal:
        print("⛔ Tidak ada subsls asal (audit kosong?). Beri --subsls-asal.")
        return 1
    if args.console:
        path = tulis_console(target, asal)
        print(f"\n{path} ditulis. Chrome biasa -> login fasih-sm -> halaman Data survei (tab baru) -> F12 Console -> tempel ->")
        print('  await pindahWilayah.jalankan({mode: "petakan"})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
