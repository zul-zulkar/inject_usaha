#!/usr/bin/env python3
"""
pindah_wilayah.py — Siapkan "Ubah Wilayah" (Change Region) assignment hasil suntik
mode satu subsls ke idsubsls aslinya (kolom idsubsls sheet input usaha) di fasih-sm.

fasih-sm menolak Playwright, jadi JALUR-nya Console Chrome biasa
(pindah_wilayah_console.js). File ini hanya membaca sheet input usaha + audit dan
menyuntikkan target ke template Console — TIDAK membuka browser, TIDAK butuh VPN.

Per baris input usaha (unik per `kunci`):
  - tujuan  = kolom idsubsls (ketetapan user)
  - nama    = nama dokumen di fasih (row.nama_dokumen, dinormalkan huruf besar)
  - ids     = ID dokumen dari dokumen_url audit_log_gabungan.csv (boleh kosong:
              sebagian dokumen diinput di perangkat lain -> dicocokkan lewat nama)
  - nama yang dipakai >1 baris ditandai `g` -> Console TIDAK mencocokkan lewat nama.
  - a       = subsls asal baris itu (idsubsls_input audit) -> kode identitas "<asal> - <nama>"
  - na      = nama lain dokumen yang sama di audit (format nama lama), ikut dicari
Subsls ASAL = idsubsls_input audit (+ --subsls-asal). Status APPROVED, pencocokan
dokumen, wilayah tujuan & petugas diperiksa di Console terhadap data server.

--dari-approve (alur SATUAN, disarankan): target HANYA dokumen yang pernah
APPROVED_TERVERIFIKASI di audit_approve_pml.csv (id dokumen pasti, hasil approve_pml.py),
lalu di Console dicari satu per satu lewat nama / kode identitas dan dipindah satu per satu.

LANGKAH
-------
    python pindah_wilayah/pindah_wilayah.py --sumber input_usaha.xlsx --sumber input_usaha_2.xlsx \
        --dari-approve --console
Lalu di Chrome (login fasih-sm, halaman Data survei) -> F12 Console -> tempel
pindah_wilayah_console.siap.js:
    await pindahWilayah.jalankan({mode: "cari", limit: 10})     // READ-ONLY per dokumen
    await pindahWilayah.jalankan({mode: "pindah", limit: 1})    // pindah 1 dokumen, cek hasilnya
    await pindahWilayah.jalankan({mode: "pindah"})              // sisanya, satu per satu
Alur lama dua tahap (petakan -> cek -> eksekusi) tetap ada, lihat docs/PANDUAN_PINDAH_WILAYAH.md.

FORMAT TAHAP 2 (hasil pendataan kertas, bahan/input_tahap2.xlsx)
---------------------------------------------------------------
Tambahkan --format tahap2. Tujuan = kolom "5" sheet; target HANYA baris yang
dokumennya tercatat di audit (--hanya-tercatat otomatis) supaya Console tidak
mencari ratusan baris yang belum pernah diinput. Dokumen yang diinput di PC
lain: jalankan dulu `input_gabungan/sinkron_list.py --format tahap2 ... --tulis`.
    python approve_pml/approve_pml.py --akun-pml <PML> --akun-ppl <PPL> --eksekusi   (approve dulu)
    python pindah_wilayah/pindah_wilayah.py --format tahap2 --sumber bahan/input_tahap2.xlsx \
        --dari-approve --daftar-tujuan tujuan_tahap2.txt --console
    python buka_wilayah/buka_wilayah.py --daftar tujuan_tahap2.txt --console      (kalau tujuan Listing Selesai)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti.config import KODE_KAB
from inti.gabungan_loader import GabunganRow, load_gabungan
from inti.tahap2_loader import load_tahap2
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
AUDIT_APPROVE_PATH = Path("./audit_approve_pml.csv")
STATUS_APPROVED = "APPROVED_TERVERIFIKASI"  # = approve_pml.ST_OK
PENANDA_TARGET = "/*__TARGET__*/[]"
PENANDA_ASAL = "/*__ASAL__*/[]"
PENANDA_KODE_KAB = '/*__KODE_KAB__*/"5108"'
POLA_KODE = re.compile(rf"{re.escape(KODE_KAB)}\d{{12}}")


def approved_per_kunci(audit_approve: list[dict]) -> tuple[dict[str, dict[str, str]], Counter]:
    """audit_approve_pml.csv -> ({kunci: {id dokumen: nama}}, ringkasan).
    Dokumen yang PERNAH APPROVED_TERVERIFIKASI (approve_pml.py tidak menulis ulang dokumen yang sudah
    APPROVED, dan status segarnya tetap dicek Console). Baris tanpa kunci = dokumen di luar sheet input usaha
    (sumber rencana SQL Lab / list) -> tidak dipakai, hanya dihitung."""
    hasil: dict[str, dict[str, str]] = defaultdict(dict)
    ringkasan = Counter()
    for b in audit_approve:
        if (b.get("status") or "").strip() != STATUS_APPROVED or not b.get("id"):
            continue
        if not b.get("kunci"):
            ringkasan["approved_tanpa_kunci"] += 1
            continue
        hasil[b["kunci"]][b["id"].strip()] = b.get("nama") or ""
    return dict(hasil), ringkasan


def bangun_target(sumber_rows: list[tuple[str, GabunganRow]], audit: list[dict],
                  approve: dict[str, dict[str, str]] | None = None, hanya_tercatat: bool = False):
    """Fungsi murni -> (target[], masalah[(sumber, baris, pesan)], ringkasan Counter).
    `approve` (hasil approved_per_kunci) -> target HANYA baris yang dokumennya sudah di-approve,
    dgn `ids` = id dokumen approve itu (bukan semua id audit).
    `hanya_tercatat` -> baris tanpa id dokumen di audit TIDAK jadi target (format tahap 2: sheet
    berisi ribuan baris yang sebagian besar belum diinput; mencarinya lewat nama = ratusan
    request sia-sia & rawan 429)."""
    ids_per_kunci = defaultdict(set)
    asal_per_kunci = defaultdict(set)
    nama_per_kunci = defaultdict(set)
    for b in audit:
        if not b.get("kunci"):
            continue
        doc_id = id_dari_url(b.get("dokumen_url"))
        if doc_id:
            ids_per_kunci[b["kunci"]].add(doc_id)
        if POLA_KODE.fullmatch((b.get("idsubsls_input") or "").strip()):
            asal_per_kunci[b["kunci"]].add(b["idsubsls_input"].strip())
        if b.get("nama_usaha"):
            nama_per_kunci[b["kunci"]].add(norm(b["nama_usaha"]))
    for kunci, per_id in (approve or {}).items():
        nama_per_kunci[kunci].update(norm(n) for n in per_id.values() if n)

    ringkasan = Counter()
    masalah = []
    baris_unik: dict[str, tuple[str, GabunganRow]] = {}
    for sumber, row in sumber_rows:
        if not POLA_KODE.fullmatch(row.idsubsls or ""):
            masalah.append((sumber, row.baris, f"idsubsls tujuan '{row.idsubsls}' bukan 16 digit berawalan {KODE_KAB}"))
            continue
        if row.kunci in baris_unik:
            ringkasan["baris_kembar_digabung"] += 1
            continue
        baris_unik[row.kunci] = (sumber, row)

    kunci_per_nama = defaultdict(set)
    for kunci, (_, row) in baris_unik.items():
        kunci_per_nama[norm(row.nama_dokumen)].add(kunci)

    if approve is not None:
        for kunci, per_id in approve.items():
            if kunci not in baris_unik:
                masalah.append((AUDIT_APPROVE_PATH.name, "", f"kunci {kunci} (id {', '.join(sorted(per_id))}) "
                                                             "sudah di-approve tapi tidak ada di sheet input usaha"))

    target = []
    for kunci, (sumber, row) in baris_unik.items():
        if approve is not None and kunci not in approve:
            continue
        if approve is None and hanya_tercatat and not ids_per_kunci.get(kunci):
            ringkasan["belum_ada_dokumen"] += 1
            continue
        n = norm(row.nama_dokumen)
        ids = approve[kunci] if approve is not None else ids_per_kunci.get(kunci, ())
        t = {"k": kunci, "s": Path(sumber).name, "b": row.baris, "n": n, "t": row.idsubsls,
             "p": row.akun_ppl, "ids": sorted(ids)}
        if asal_per_kunci.get(kunci):
            t["a"] = sorted(asal_per_kunci[kunci])
        if nama_per_kunci.get(kunci, set()) - {n, ""}:
            t["na"] = sorted(nama_per_kunci[kunci] - {n, ""})
        if len(kunci_per_nama[n]) > 1:
            t["g"] = 1
            ringkasan["nama_ganda"] += 1
        ringkasan["dgn_id_audit" if t["ids"] else "tanpa_id_audit"] += 1
        if approve is not None:
            ringkasan["dari_approve"] += 1
        if len(t["ids"]) > 1:
            ringkasan["id_ganda"] += 1
        target.append(t)
    return target, masalah, ringkasan


def subsls_asal(audit: list[dict], tambahan: list[str]) -> tuple[list[str], list[str]]:
    """-> (asal unik terurut, token tidak valid). Asal = idsubsls_input audit + tambahan."""
    kode = {b.get("idsubsls_input", "").strip() for b in audit} | {x.strip() for x in tambahan}
    kode.discard("")
    return sorted(k for k in kode if POLA_KODE.fullmatch(k)), sorted(k for k in kode if not POLA_KODE.fullmatch(k))


def tulis_daftar_tujuan(target: list[dict], path: Path) -> list[str]:
    """Subsls tujuan unik (satu per baris) -> bahan `buka_wilayah.py --daftar`."""
    kode = sorted({t["t"] for t in target})
    path.write_text("# subsls tujuan pindah wilayah (dibangkitkan pindah_wilayah.py)\n" + "\n".join(kode) + "\n",
                    encoding="utf-8")
    return kode


def tulis_console(target: list[dict], asal: list[str]) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    for penanda in (PENANDA_TARGET, PENANDA_ASAL, PENANDA_KODE_KAB):
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    teks = teks.replace(PENANDA_TARGET, json.dumps(target, ensure_ascii=False, separators=(",", ":")))
    teks = teks.replace(PENANDA_ASAL, json.dumps(asal))
    teks = teks.replace(PENANDA_KODE_KAB, json.dumps(KODE_KAB))
    KONSOL_SIAP.write_text(teks, encoding="utf-8")
    return KONSOL_SIAP


def main() -> int:
    ap = argparse.ArgumentParser(description="Siapkan pindah wilayah assignment (fasih-sm) dari sheet input usaha")
    ap.add_argument("--sumber", action="append", required=True, help="xlsx/csv sheet input usaha (boleh berulang)")
    ap.add_argument("--format", choices=("standar", "tahap2"), default="standar",
                    help="Format SEMUA --sumber: standar (input_usaha.xlsx) / tahap2 (bahan/input_tahap2.xlsx)")
    ap.add_argument("--hanya-tercatat", action="store_true",
                    help="Target hanya baris yang dokumennya tercatat di audit (otomatis utk --format tahap2)")
    ap.add_argument("--daftar-tujuan", default="", metavar="TXT",
                    help="Tulis subsls tujuan unik ke file ini (bahan buka_wilayah.py --daftar)")
    ap.add_argument("--subsls-asal", action="append", default=[],
                    help="subsls tempat dokumen disuntik, selain yang tercatat di audit (boleh berulang)")
    ap.add_argument("--dari-approve", nargs="?", const=str(AUDIT_APPROVE_PATH), default=None, metavar="CSV",
                    help="target HANYA dokumen APPROVED_TERVERIFIKASI di audit approve PML "
                         f"(default {AUDIT_APPROVE_PATH.name}) -> alur satuan mode cari/pindah")
    ap.add_argument("--console", action="store_true", help=f"Tulis {KONSOL_SIAP} utk ditempel di Console Chrome")
    mg.opsi_audit(ap)
    args = ap.parse_args()
    mg.pakai_audit(args.audit)

    sumber_rows = []
    for s in args.sumber:
        rows = load_tahap2(s) if args.format == "tahap2" else load_gabungan(s)
        print(f"{s}: {len(rows)} baris")
        sumber_rows += [(s, r) for r in rows]
    audit = mg._baca_audit()
    approve = None
    if args.dari_approve:
        path_approve = Path(args.dari_approve)
        if not path_approve.exists():
            print(f"⛔ {path_approve} tidak ada — jalankan approve_pml.py dulu atau beri path yang benar.")
            return 1
        with path_approve.open(newline="", encoding="utf-8-sig") as f:
            approve, ringkas_approve = approved_per_kunci(list(csv.DictReader(f)))
        print(f"{path_approve}: {sum(len(v) for v in approve.values())} dokumen APPROVED_TERVERIFIKASI ber-kunci input usaha"
              + (f", {ringkas_approve['approved_tanpa_kunci']} tanpa kunci (bukan dokumen suntikan, diabaikan)"
                 if ringkas_approve["approved_tanpa_kunci"] else ""))
    target, masalah, ringkasan = bangun_target(sumber_rows, audit, approve,
                                               hanya_tercatat=args.hanya_tercatat or args.format == "tahap2")
    asal, asal_salah = subsls_asal(audit, args.subsls_asal)

    print(f"\n{len(target)} baris unik jadi target | dgn ID audit: {ringkasan['dgn_id_audit']}, "
          f"tanpa ID audit (dicocokkan lewat nama): {ringkasan['tanpa_id_audit']}")
    if ringkasan["belum_ada_dokumen"]:
        print(f"  {ringkasan['belum_ada_dokumen']} baris dilewati: belum ada dokumennya di {mg.AUDIT_LOG_PATH} "
              "(belum diinput, atau diinput di PC lain -> sinkron_list.py --tulis dulu)")
    if approve is not None:
        print(f"  alur SATUAN: {ringkasan['dari_approve']} dokumen sudah di-approve -> "
              'mode "cari" / "pindah" di Console')
        tanpa_asal = sum(1 for t in target if not t.get("a"))
        if tanpa_asal:
            print(f"  ⚠️ {tanpa_asal} target tanpa subsls asal di audit -> kode identitas tidak bisa dicari, "
                  "dicari lewat nama saja")
    if ringkasan["id_ganda"]:
        print(f"  ⚠️ {ringkasan['id_ganda']} baris punya >1 id dokumen -> DOKUMEN_GANDA di Console (tidak dipindah)")
    if sum(1 for t in target if t.get("na")):
        print(f"  {sum(1 for t in target if t.get('na'))} baris punya nama lama di audit -> nama lama ikut dicari")
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
    if not target:
        print("⛔ Tidak ada target.")
        return 1
    if args.daftar_tujuan:
        kode = tulis_daftar_tujuan(target, Path(args.daftar_tujuan))
        print(f"\n{args.daftar_tujuan}: {len(kode)} subsls tujuan -> kalau ada yang masih Listing Selesai:\n"
              f"  python buka_wilayah/buka_wilayah.py --daftar {args.daftar_tujuan} --console")
    if args.console:
        path = tulis_console(target, asal)
        print(f"\n{path} ditulis. Chrome biasa -> login fasih-sm -> halaman Data survei (tab baru) -> F12 Console -> tempel ->")
        if approve is not None:
            print('  await pindahWilayah.jalankan({mode: "cari", limit: 10})')
        else:
            print('  await pindahWilayah.jalankan({mode: "petakan"})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
