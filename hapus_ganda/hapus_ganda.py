#!/usr/bin/env python3
"""
hapus_ganda.py — siapkan skrip Console utk MENGHAPUS dokumen ganda (akun admin fasih-sm).

Membaca audit gabungan (+ list_api_*.json & ganda_dihapus*.csv kalau ada), mengambil grup
BARIS_SAMA dari gabung_audit.daftar_ganda() — satu baris sheet yang tercatat punya >= 2
dokumen — lalu menyuntikkannya ke hapus_ganda/hapus_ganda_console.js ->
hapus_ganda_console.siap.js. TIDAK membuka browser & TIDAK menyentuh server: keputusan
hapus/pertahankan dibuat ulang di Console dgn status SEGAR dari server.

Grup NAMA_SAMA_* (baris sheet berbeda / di luar audit) TIDAK ikut: bisa usaha berbeda
bernama sama — lihat daftar_ganda.csv dan putuskan manual.

    python hapus_ganda/hapus_ganda.py
    python hapus_ganda/hapus_ganda.py --akun ppl.contoh@gmail.com     # hanya grup akun ini

SESUDAH menghapus (hapusGanda.unduh() -> ganda_dihapus_*.csv di folder proyek):

    python hapus_ganda/hapus_ganda.py --catat           # lihat rencananya
    python hapus_ganda/hapus_ganda.py --catat --tulis   # tulis ke audit_log_gabungan.csv

--catat mengarahkan audit ke dokumen yang DIPERTAHANKAN utk baris yang dokumen
tercatatnya ikut terhapus — kalau tidak, run berikutnya membuka URL yang sudah tidak
ada, atau (lewat DOKUMEN_DIHAPUS sinkron_list) membuat dokumen baru = ganda lagi.

Panduan: docs/PANDUAN_HAPUS_GANDA.md.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import input_gabungan.main_gabungan as mg  # noqa: E402
from gabung_audit.gabung_audit import (  # noqa: E402
    _ASAL_DOKUMEN, POLA_GANDA_DIHAPUS, baca_ganda_dihapus, baca_info_server, baca_status_server, daftar_ganda,
    id_dokumen, peringkat_status,
)
from input_gabungan.sinkron_list import url_entry  # noqa: E402
from inti.config import ASSIGNMENT_ID_GABUNGAN, SURVEY_ID  # noqa: E402

for _stream in (_sys.stdout, _sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "hapus_ganda_console.js"
KONSOL_SIAP = Path("./hapus_ganda_console.siap.js")
PENANDA_TARGET = "/*__TARGET__*/[]"
PENANDA_SURVEI = '/*__SURVEI__*/""'
PENANDA_PERIODE = '/*__PERIODE__*/""'


def target_dari_ganda(ganda: list[dict], akun: set | None = None, hanya_papi: bool = True) -> list[dict]:
    """Baris daftar_ganda() -> TARGET Console: [{g: kunci, b: baris, n: nama,
    d: [{id, c: ditunjuk audit, l: di luar audit, x: URL diklaim baris lain, a: akun, m: mode}]}].
    Hanya jenis BARIS_SAMA; `akun` menyaring grup yang punya dokumen milik akun itu.
    hanya_papi: dokumen yang mode-nya DIKETAHUI bukan PAPI dibuang, grup yang tinggal < 2
    dokumen ikut dibuang (mode tidak diketahui tetap ikut — Console membacanya segar)."""
    grup: dict = defaultdict(list)
    for r in ganda:
        if r["jenis"] == "BARIS_SAMA":
            grup[r["grup"]].append(r)
    keluar = []
    for _no, isi in sorted(grup.items()):
        if akun and not any((r["akun_login"] or "").lower() in akun for r in isi):
            continue
        if hanya_papi:
            isi = [r for r in isi if r.get("mode_server", "") in ("", "PAPI")]
            if len(isi) < 2:
                continue
        keluar.append({
            "g": isi[0]["kunci"], "b": next((r["baris"] for r in isi if r["baris"]), ""),
            "n": next((r["nama_usaha"] for r in isi if r["nama_usaha"]), ""),
            "d": [{"id": r["id_dokumen"], "c": r["dicatat_audit"] == "ya", "l": r["di_luar_audit"] == "ya",
                   "x": "juga tercatat utk baris lain" in r["alasan_usulan"], "a": r["akun_login"],
                   "m": r.get("mode_server", "")} for r in isi],
        })
    return keluar


def baca_unduhan(pola: str = POLA_GANDA_DIHAPUS) -> list[dict]:
    """Baris ganda_dihapus*.csv (hapusGanda.unduh()) yang penghapusannya TERVERIFIKASI."""
    out = []
    for f in sorted(Path().glob(pola)):
        with f.open(newline="", encoding="utf-8-sig") as fh:
            out += [b for b in csv.DictReader(fh) if "TERVERIFIKASI" in (b.get("status") or "") and b.get("id")]
    return out


def rencana_catat(audit: list[dict], dihapus: list[dict], assignment_id: str = ASSIGNMENT_ID_GABUNGAN) -> list[dict]:
    """Baris audit yang mengarahkan tiap baris sheet ke dokumen yang DIPERTAHANKAN, HANYA
    kalau dokumen yang kini ditunjuk audit ikut terhapus (atau baris itu sudah tak
    berdokumen krn DOKUMEN_DIHAPUS). DOKUMEN_DIBUAT(URL dipertahankan) — URL baru menang
    di dokumen_dari/status_terakhir_dari — lalu TERKIRIM_TERVERIFIKASI kalau yang
    dipertahankan sudah SUBMITTED/APPROVED. Fungsi murni; idempoten."""
    dokumen = mg.dokumen_dari(audit)
    terakhir: dict = {}
    for b in audit:
        if b.get("kunci"):
            terakhir[b["kunci"]] = {**terakhir.get(b["kunci"], {}), **{k: v for k, v in b.items() if v}}
    dihapus_id = {r["id"].lower() for r in dihapus}
    keluar, sudah = [], set()
    for r in dihapus:
        kunci, simpan = r.get("grup") or "", (r.get("dipertahankan") or "").strip()
        if not kunci or not simpan or kunci in sudah or simpan.lower() in dihapus_id:
            continue
        kini = id_dokumen(dokumen.get(kunci, ("", "", ""))[2]).lower()
        if kini not in ("", r["id"].lower()):
            continue            # audit sudah/masih menunjuk dokumen lain yang masih ada
        sudah.add(kunci)
        dasar = terakhir.get(kunci, {})
        url = url_entry(simpan, assignment_id)
        isi = {"baris": dasar.get("baris", r.get("baris", "")), "kunci": kunci,
               "nama_usaha": dasar.get("nama_usaha", r.get("nama", "")), "kbli": dasar.get("kbli", ""),
               "idsubsls": dasar.get("idsubsls", ""), "akun_ppl": dasar.get("akun_ppl", ""),
               "akun_login": (r.get("akun_dipertahankan") or dasar.get("akun_login", "")).lower(),
               "idsubsls_input": r.get("subsls_dipertahankan") or dasar.get("idsubsls_input", ""),
               "dokumen_url": url}
        waktu = time.strftime("%Y-%m-%d %H:%M:%S")
        pesan = (f"hapus_ganda: dokumen {r['id'][:8]} ({r.get('alias', '')}) dihapus admin sbg ganda — "
                 f"dipertahankan {simpan[:8]} ({r.get('alias_dipertahankan', '')})")
        keluar.append({"timestamp": waktu, **isi, "status": mg.STATUS_DIBUAT, "error_message": pesan})
        if peringkat_status(r.get("alias_dipertahankan", "")) >= 3:
            keluar.append({"timestamp": waktu, **isi, "status": "TERKIRIM_TERVERIFIKASI", "error_message": pesan})
    return keluar


def tulis_console(target: list[dict], keluaran: Path = KONSOL_SIAP) -> Path:
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    for penanda in (PENANDA_TARGET, PENANDA_SURVEI, PENANDA_PERIODE):
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    teks = (teks.replace(PENANDA_TARGET, json.dumps(target, ensure_ascii=False, separators=(",", ":")))
            .replace(PENANDA_SURVEI, json.dumps(SURVEY_ID))
            .replace(PENANDA_PERIODE, json.dumps(ASSIGNMENT_ID_GABUNGAN)))
    keluaran.write_text(teks, encoding="utf-8")
    return keluaran


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Siapkan Console hapus dokumen ganda (fasih-sm, akun admin)")
    ap.add_argument("--akun", action="append", default=[], help="hanya grup yang punya dokumen akun ini (boleh diulang)")
    ap.add_argument("--list-json", action="append", default=[],
                    help="list_api_<akun>.json dari sinkron_list.py (default: semua di folder ini)")
    ap.add_argument("--semua-mode", action="store_true",
                    help="ikutkan dokumen CAPI/CAWI (bawaan: hanya PAPI). Console juga perlu {hanyaPapi: false}")
    ap.add_argument("--keluaran", default=str(KONSOL_SIAP))
    ap.add_argument("--catat", action="store_true",
                    help=f"SESUDAH menghapus: arahkan audit ke dokumen yang dipertahankan ({POLA_GANDA_DIHAPUS})")
    ap.add_argument("--tulis", action="store_true", help="dgn --catat: benar-benar tulis ke audit")
    args = ap.parse_args(argv)

    audit = mg._baca_audit()
    if args.catat:
        dihapus = baca_unduhan()
        tulis = rencana_catat(audit, dihapus)
        print(f"{len(dihapus)} penghapusan terverifikasi di {POLA_GANDA_DIHAPUS}; "
              f"{len({t['kunci'] for t in tulis})} baris sheet perlu diarahkan ke dokumen yang dipertahankan "
              f"({len(tulis)} baris audit).")
        for t in tulis[:15]:
            print(f"  baris {t['baris']:>5}  {t['status']:<24} {id_dokumen(t['dokumen_url'])[:8]}  {t['nama_usaha'][:40]}")
        if not args.tulis:
            print("(rencana saja — tambahkan --tulis utk menulis ke audit)" if tulis else "Tidak ada yang perlu dicatat.")
            return 0
        for t in tulis:
            mg.append_audit(t)
        print(f"✅ {len(tulis)} baris ditulis ke {mg.AUDIT_LOG_PATH}. Lalu cocokkan dgn server: sinkron_list.py per akun.")
        return 0

    status_server, galat_server, nama_server = baca_status_server(args.list_json or ["list_api_*.json"])
    sudah = baca_ganda_dihapus()
    info_server = baca_info_server(args.list_json or ["list_api_*.json"])
    ganda = daftar_ganda(audit, status_server, galat_server, nama_server, _ASAL_DOKUMEN, sudah,
                         info_server=info_server, hanya_papi=not args.semua_mode)
    akun = {a.strip().lower() for a in args.akun if a.strip()}
    target = target_dari_ganda(ganda, akun or None, hanya_papi=not args.semua_mode)

    print(f"Audit: {mg.AUDIT_LOG_PATH} ({len(audit)} baris)" + (f" | sudah dihapus: {len(sudah)} dokumen" if sudah else ""))
    print(f"Grup BARIS_SAMA utk Console: {len(target)} grup, {sum(len(t['d']) for t in target)} dokumen"
          + (f" (akun {sorted(akun)})" if akun else "")
          + (" — SEMUA mode" if args.semua_mode else " — hanya PAPI (mode dibaca ulang dari server di Console)"))
    lain = Counter(r["jenis"] for r in ganda if r["jenis"] != "BARIS_SAMA")
    if lain:
        print(f"TIDAK ikut (periksa manual di daftar_ganda.csv): {dict(lain)} dokumen")
    if not target:
        print("Tidak ada grup ganda — tidak ada yang perlu dihapus.")
        return 0
    path = tulis_console(target, Path(args.keluaran))
    print(f"\n✅ {path} — buka fasih-sm (akun ADMIN) di halaman Data survei, tempel isinya di Console, lalu:")
    print("   hapusGanda.cek()                               // READ-ONLY dulu")
    print("   hapusGanda.rekam()                             // hapus SATU manual, polanya direkam")
    print("   hapusGanda.jalankan({mode: 'hapus', limit: 1}) // lalu tanpa limit")
    print("Panduan: docs/PANDUAN_HAPUS_GANDA.md")
    return 0


if __name__ == "__main__":
    _sys.exit(main())
