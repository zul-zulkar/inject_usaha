#!/usr/bin/env python3
"""
gabung_audit.py — satukan `audit_log_gabungan.csv` dari BEBERAPA PC jadi satu
berkas, lalu buat laporan progres (per akun, per wilayah, per status).

Kenapa ada: tiap PC menulis audit SENDIRI, dan audit itulah yang dipakai
`--lewati-selesai` & pencegah duplikat (`dokumen_per_kunci`). Selama audit belum
disatukan, PC A tidak tahu baris mana yang sudah dikerjakan PC B — kalau
rentang barisnya sampai bersinggungan, dokumennya jadi GANDA dan PPL TIDAK BISA
menghapusnya (urusan admin pusat).

SIFAT: READ-ONLY thd server & thd audit sumber. Berkas gabungan baru ditulis
kalau ada `--tulis` (audit lama di tujuan otomatis dicadangkan .bak-<waktu>).

LANGKAH
-------
1. Hentikan/selesaikan batch di semua PC, lalu salin `audit_log_gabungan.csv`
   tiap PC ke SATU folder dgn nama berbeda, mis. `audit_pc/pc1.csv`, `pc2.csv`, ...
2. Lihat laporannya dulu (tidak menulis apa pun):
       python gabung_audit/gabung_audit.py --sumber audit_pc
3. Kalau tidak ada peringatan bentrok, tulis hasil gabungannya:
       python gabung_audit/gabung_audit.py --sumber audit_pc --tulis
4. Salin `audit_log_gabungan.csv` hasil gabungan itu KE SEMUA PC.
5. Cocokkan dgn server (per akun, READ-ONLY dulu, lihat PANDUAN_GABUNG_AUDIT.md):
       python input_gabungan/sinkron_list.py --format tahap2 --sumber <sheet> \
           --akun-tunggal <akun> --subsls-tunggal <subsls>

Urutan baris dijaga PER KUNCI: aturan audit adalah "baris TERAKHIR menang", dan
timestamp audit = AWAL pemrosesan baris (baris DOKUMEN_DIBUAT bisa bertimestamp
LEBIH BARU drpd baris status akhirnya). Jadi baris TIDAK diurutkan per waktu satu
per satu — yang diurutkan blok per (berkas, kunci), memakai waktu TERBESAR di blok
itu; isi blok tetap urut aslinya.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_gabungan.main_gabungan as mg  # noqa: E402
from inti.config import WILAYAH_BY_IDSUBSLS  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

AUDIT_FIELDS = mg.AUDIT_FIELDS
LAPORAN_PATH = Path("./laporan_gabung.csv")
AGREGAT_PATH = Path("./laporan_gabung_agregat.csv")

KOLOM_LAPORAN = [
    "kunci", "baris", "nama_usaha", "kbli", "akun_ppl", "akun_login",
    "idsubsls", "kecamatan", "desa", "sls", "idsubsls_input",
    "status", "kelompok", "status_server", "galat_server", "id_dokumen", "dokumen_url",
    "waktu_terakhir", "berkas", "review_disarankan", "error_message",
]
# Urutan tampil kelompok (dari "sudah beres" ke "perlu tindakan").
URUT_KELOMPOK = ["TERKIRIM", "DRAFT_TANPA_KOORDINAT", "DRAFT", "DRY_RUN",
                 "DIHAPUS", "DILEWATI", "GAGAL", "LAIN"]


# --------------------------------------------------------------------------
# Fungsi murni (diuji di tests/test_gabung_audit.py)
# --------------------------------------------------------------------------
def kelompok_status(status: str) -> str:
    """Status audit -> kelompok ringkas utk laporan. Nama status ikut
    main_gabungan (jangan disalin ulang ke sini) supaya tidak berbeda arti."""
    s = (status or "").strip()
    if s in mg.STATUS_TERKIRIM:
        return "TERKIRIM"
    if s == mg.STATUS_DRAFT_TANPA_KOORDINAT:
        return "DRAFT_TANPA_KOORDINAT"
    if s in mg.STATUS_TANPA_URL_SEMUA:
        # Dokumen mungkin ADA di server tanpa URL tercatat — belum beres.
        return "GAGAL"
    if s in (mg.STATUS_DIBUAT, "DRAFT_DI_SERVER", "DRAFT_GALAT_DI_SERVER"):
        return "DRAFT"
    if s == "DRY_RUN_SIAP_KIRIM":
        return "DRY_RUN"
    if s == mg.STATUS_DIHAPUS:
        return "DIHAPUS"
    if s.startswith("SKIP_"):
        return "DILEWATI"
    if s.startswith(("ERROR_", "STOP_")) or s == "SUBMIT_GAGAL":
        return "GAGAL"
    return "LAIN"


def id_dokumen(url: str) -> str:
    """ID assignment dari URL entry fasih-web (.../<survey>/<periode>/<ID>/entry)."""
    bagian = [p for p in str(url or "").split("/") if p]
    if len(bagian) >= 2 and bagian[-1] == "entry":
        return bagian[-2]
    return ""


def baca_audit(path: Path) -> list[dict]:
    """Baca satu audit; kolom yang tidak ada diisi "". Berkas yang bukan audit
    (tidak punya kolom kunci & status) ditolak — jangan sampai ikut tergabung."""
    with Path(path).open(newline="", encoding="utf-8") as f:
        pembaca = csv.DictReader(f)
        judul = pembaca.fieldnames or []
        if "kunci" not in judul or "status" not in judul:
            raise ValueError(f"{path}: bukan audit_log_gabungan (tidak ada kolom 'kunci'/'status'). "
                             f"Judul terbaca: {judul[:6]}")
        return [{k: (b.get(k) or "").strip() if k != "error_message" else (b.get(k) or "")
                 for k in AUDIT_FIELDS} for b in pembaca]


def gabung(berkas: list[tuple[str, list[dict]]]) -> tuple[list[dict], dict]:
    """[(nama berkas, baris)] -> (baris gabungan, laporan).

    - Baris yang SAMA PERSIS di lebih dari satu berkas ditulis sekali (audit yang
      pernah disalin antar-PC tidak jadi dobel).
    - Urutan: blok (berkas, kunci) diurutkan per waktu TERBESAR di blok itu; isi
      blok tetap urut aslinya, jadi "baris terakhir menang" tetap benar dan
      catatan PC yang paling baru mengerjakan satu kunci ada di paling belakang.
    """
    terlihat: set = set()
    bersih: list[tuple[int, int, dict]] = []
    ganda_persis = 0
    for i, (_nama, baris) in enumerate(berkas):
        for j, b in enumerate(baris):
            sidik = tuple(b.get(k, "") for k in AUDIT_FIELDS)
            if sidik in terlihat:
                ganda_persis += 1
                continue
            terlihat.add(sidik)
            bersih.append((i, j, b))

    def blok(i: int, j: int, b: dict) -> tuple:
        # Baris tanpa kunci (mis. ERROR_LOGIN sebelum baris dikenali) berdiri sendiri.
        return (i, b.get("kunci") or f"#{j}")

    waktu: dict = {}
    for i, j, b in bersih:
        k = blok(i, j, b)
        waktu[k] = max(waktu.get(k, ""), b.get("timestamp", ""))
    bersih.sort(key=lambda t: (waktu[blok(*t)], t[0], t[1]))

    gabungan = [b for _i, _j, b in bersih]
    # Asal = berkas yang menyumbang baris BARU. Berkas yang isinya cuma salinan
    # (hasil gabungan yang disebar ke semua PC) sengaja tidak dihitung, supaya
    # peringatan "dikerjakan >1 PC" hanya muncul kalau catatannya memang BEDA.
    asal: dict = defaultdict(set)
    for i, _j, b in bersih:
        if b.get("kunci"):
            asal[b["kunci"]].add(berkas[i][0])
    laporan = {
        "ganda_persis": ganda_persis,
        "asal_per_kunci": {k: sorted(v) for k, v in asal.items()},
        "per_berkas": [{"berkas": nama, "baris": len(baris),
                        "kunci": len({b["kunci"] for b in baris if b.get("kunci")}),
                        "mulai": min((b.get("timestamp", "") for b in baris), default=""),
                        "akhir": max((b.get("timestamp", "") for b in baris), default="")}
                       for nama, baris in berkas],
    }
    return gabungan, laporan


def periksa_bentrok(gabungan: list[dict], asal_per_kunci: dict) -> dict:
    """Kejanggalan yang HARUS dilihat manusia sebelum hasil gabungan dipakai."""
    dokumen: dict = defaultdict(list)     # kunci -> [url] (direset kalau DOKUMEN_DIHAPUS)
    akun: dict = defaultdict(set)         # kunci -> {akun_login yang pernah bikin dokumen}
    for b in gabungan:
        kunci, url = b.get("kunci"), b.get("dokumen_url") or ""
        if not kunci:
            continue
        if b.get("status") == mg.STATUS_DIHAPUS:
            dokumen[kunci].clear()
            continue
        if url and url not in dokumen[kunci]:
            dokumen[kunci].append(url)
        if url or b.get("status") == mg.STATUS_DIBUAT:
            if b.get("akun_login"):
                akun[kunci].add(b["akun_login"].lower())

    pemilik_url: dict = defaultdict(set)
    for kunci, daftar in dokumen.items():
        for u in daftar:
            pemilik_url[u].add(kunci)

    return {
        "lintas_berkas": {k: v for k, v in asal_per_kunci.items() if len(v) > 1},
        "dokumen_ganda": {k: v for k, v in dokumen.items() if len(v) > 1},
        "akun_ganda": {k: sorted(v) for k, v in akun.items() if len(v) > 1},
        "url_banyak_kunci": {u: sorted(v) for u, v in pemilik_url.items() if len(v) > 1},
    }


def ringkas_per_kunci(gabungan: list[dict], asal_per_kunci: dict,
                      status_server: dict | None = None,
                      wilayah: dict | None = None,
                      galat_server: dict | None = None) -> list[dict]:
    """Satu baris laporan per kunci (= per dokumen), memakai aturan audit yang
    sama dgn main_gabungan: status & dokumen dari baris TERAKHIR."""
    status_akhir = mg.status_terakhir_dari(gabungan)
    dokumen = mg.dokumen_dari(gabungan)
    terakhir: dict = {}
    isi: dict = defaultdict(dict)     # kunci -> nilai non-kosong terakhir per kolom
    waktu: dict = defaultdict(str)
    for b in gabungan:
        kunci = b.get("kunci")
        if not kunci:
            continue
        terakhir[kunci] = b
        waktu[kunci] = max(waktu[kunci], b.get("timestamp", ""))
        for k in ("baris", "nama_usaha", "kbli", "akun_ppl", "idsubsls", "idsubsls_input",
                  "akun_login", "review_disarankan", "error_message"):
            if b.get(k):
                isi[kunci][k] = b[k]

    keluar = []
    for kunci, b in terakhir.items():
        url = dokumen.get(kunci, ("", "", ""))[2] or ""
        did = id_dokumen(url)
        w = (wilayah or {}).get(isi[kunci].get("idsubsls", "")) or \
            WILAYAH_BY_IDSUBSLS.get(isi[kunci].get("idsubsls", "")) or {}
        status = status_akhir.get(kunci, "")
        keluar.append({
            "kunci": kunci,
            "baris": isi[kunci].get("baris", ""),
            "nama_usaha": isi[kunci].get("nama_usaha", ""),
            "kbli": isi[kunci].get("kbli", ""),
            "akun_ppl": isi[kunci].get("akun_ppl", ""),
            "akun_login": dokumen.get(kunci, ("", "", ""))[0] or isi[kunci].get("akun_login", ""),
            "idsubsls": isi[kunci].get("idsubsls", ""),
            "kecamatan": w.get("kecamatan", ""),
            "desa": w.get("desa", ""),
            "sls": w.get("sls", ""),
            "idsubsls_input": dokumen.get(kunci, ("", "", ""))[1] or isi[kunci].get("idsubsls_input", ""),
            "status": status,
            "kelompok": kelompok_status(status),
            "status_server": (status_server or {}).get(did, ""),
            "galat_server": (galat_server or {}).get(did, ""),
            "id_dokumen": did,
            "dokumen_url": url,
            "waktu_terakhir": waktu[kunci],
            "berkas": " + ".join(asal_per_kunci.get(kunci, [])),
            "review_disarankan": isi[kunci].get("review_disarankan", ""),
            "error_message": (b.get("error_message") or "")[:300],
        })
    keluar.sort(key=lambda r: (r["akun_login"], r["idsubsls_input"], _angka(r["baris"])))
    return keluar


def _angka(x) -> int:
    try:
        return int(str(x))
    except (TypeError, ValueError):
        return 0


def agregat(laporan: list[dict], kolom: str, jenis: str, nama: dict | None = None) -> list[dict]:
    """Hitung jumlah per kelompok status utk satu kolom pengelompok."""
    per: dict = defaultdict(Counter)
    for r in laporan:
        per[r.get(kolom) or "(kosong)"][r["kelompok"]] += 1
    baris = []
    for nilai, c in sorted(per.items()):
        b = {"jenis": jenis, "nilai": nilai, "keterangan": (nama or {}).get(nilai, ""),
             "total": sum(c.values())}
        b.update({k: c.get(k, 0) for k in URUT_KELOMPOK})
        baris.append(b)
    baris.sort(key=lambda b: -b["total"])
    return baris


# --------------------------------------------------------------------------
# I/O & CLI
# --------------------------------------------------------------------------
def kumpulkan_sumber(sumber: list[str]) -> list[Path]:
    """--sumber boleh berkas .csv atau FOLDER berisi audit tiap PC."""
    out: list[Path] = []
    for s in sumber:
        p = Path(s)
        if p.is_dir():
            out.extend(sorted(x for x in p.glob("*.csv") if x.is_file()))
        elif p.exists():
            out.append(p)
        else:
            raise SystemExit(f"❌ --sumber {s} tidak ada.")
    if not out:
        raise SystemExit("❌ Tidak ada berkas .csv yang ditemukan di --sumber.")
    return out


# {id dokumen: (akun pemilik list, subsls dari kode identitas, status)} — diisi
# baca_status_server, dipakai melaporkan dokumen bernama sama di server.
_ASAL_DOKUMEN: dict = {}


def akun_dari_berkas(path) -> str:
    """list_api_<akun>.json -> akun (nama berkas dibuat sinkron_list.py)."""
    nama = Path(path).name
    return nama[len("list_api_"):-len(".json")].replace("_at_", "@") if nama.startswith("list_api_") else nama


def baca_status_server(pola: list[str]) -> tuple[dict, dict, dict]:
    """({id: assignmentStatusAlias}, {id: jumlah galat}) dari list_api_<akun>.json
    (hasil sinkron_list.py). Ini SATU-SATUNYA status yang benar-benar dari server.
    `sumError` = angka yang dijumlahkan fasih-web jadi kartu "Jumlah Error" di
    halaman PENDATAAN: dokumen yang perlu diperbaiki. Dict ketiga = {NAMA DOKUMEN
    (data1, huruf besar): [id]} — dipakai mendeteksi baris yang dokumennya sudah
    ada di server tapi belum tercatat di audit (kalau tetap dijalankan: GANDA)."""
    peta: dict = {}
    galat: dict = {}
    per_nama: dict = defaultdict(list)
    berkas: list[Path] = []
    for p in pola:
        berkas.extend(sorted(Path().glob(p)) if any(c in p for c in "*?") else [Path(p)])
    for f in berkas:
        if not f.exists():
            continue
        try:
            for it in json.loads(f.read_text(encoding="utf-8")):
                if it.get("id"):
                    peta[it["id"]] = it.get("assignmentStatusAlias") or ""
                    galat[it["id"]] = int(it.get("sumError") or 0)
                    nama = " ".join(str(it.get("data1") or "").split()).upper()
                    if nama:
                        per_nama[nama].append(it["id"])
                        _ASAL_DOKUMEN[it["id"]] = (akun_dari_berkas(f), (it.get("codeIdentity") or "")[:16],
                                                   it.get("assignmentStatusAlias") or "")
        except (ValueError, OSError) as e:
            print(f"⚠️ {f}: tidak terbaca ({e}) — dilewati.")
    return peta, galat, dict(per_nama)


def tabel(judul: str, baris: list[dict], lebar_nilai: int = 34):
    if not baris:
        return
    kelompok = [k for k in URUT_KELOMPOK if any(b.get(k) for b in baris)]
    print(f"\n=== {judul} ===")
    kepala = f"{'':{lebar_nilai}} {'TOTAL':>6} " + " ".join(f"{k[:9]:>9}" for k in kelompok)
    print(kepala)
    for b in baris:
        nilai = b["nilai"] + (f"  {b['keterangan']}" if b.get("keterangan") else "")
        print(f"{nilai[:lebar_nilai]:{lebar_nilai}} {b['total']:>6} "
              + " ".join(f"{b.get(k, 0):>9}" for k in kelompok))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", action="append", required=True,
                    help="audit tiap PC (.csv) atau FOLDER berisi audit-audit itu; boleh diulang")
    ap.add_argument("--keluaran", default=str(mg.AUDIT_LOG_PATH),
                    help=f"berkas audit gabungan (default {mg.AUDIT_LOG_PATH})")
    ap.add_argument("--buang-akun", action="append", default=[],
                    help="buang SEMUA baris audit milik akun ini (akun yang sudah tidak dipakai). "
                         "Ingatan anti-duplikat utk dokumen akun itu ikut hilang — dokumennya TIDAK "
                         "terhapus di server, hanya catatannya di sini")
    ap.add_argument("--tulis", action="store_true",
                    help="tulis berkas gabungan (tanpa ini hanya laporan; audit tujuan dicadangkan dulu)")
    ap.add_argument("--laporan", default=str(LAPORAN_PATH), help=f"CSV per dokumen (default {LAPORAN_PATH})")
    ap.add_argument("--agregat", default=str(AGREGAT_PATH), help=f"CSV rekap (default {AGREGAT_PATH})")
    ap.add_argument("--sheet", default="", help="sheet sumber, utk menghitung baris yang BELUM dikerjakan")
    ap.add_argument("--format", choices=["standar", "tahap2"], default="standar", help="format --sheet")
    ap.add_argument("--list-json", action="append", default=[],
                    help="list_api_<akun>.json dari sinkron_list.py (default: semua di folder ini)")
    args = ap.parse_args(argv)

    berkas = kumpulkan_sumber(args.sumber)
    sumber = []
    for p in berkas:
        try:
            sumber.append((p.name, baca_audit(p)))
        except ValueError as e:
            print(f"❌ {e}")
            return 2
    gabungan, lap = gabung(sumber)
    if args.buang_akun:
        buang = {a.strip().lower() for a in args.buang_akun}
        sebelum = len(gabungan)
        gabungan = [b for b in gabungan if (b.get("akun_login") or "").lower() not in buang]
        sisa_kunci = {b["kunci"] for b in gabungan if b.get("kunci")}
        lap["asal_per_kunci"] = {k: v for k, v in lap["asal_per_kunci"].items() if k in sisa_kunci}
        print(f"--buang-akun {sorted(buang)}: {sebelum - len(gabungan)} baris audit dibuang "
              f"(dokumennya TIDAK terhapus di server).")

    print(f"=== SUMBER ({len(sumber)} berkas) ===")
    for b in lap["per_berkas"]:
        print(f"  {b['berkas'][:40]:40} {b['baris']:>6} baris  {b['kunci']:>5} dokumen  "
              f"{b['mulai'][:16]} .. {b['akhir'][:16]}")
    print(f"  -> gabungan: {len(gabungan)} baris, {len(lap['asal_per_kunci'])} dokumen"
          + (f" ({lap['ganda_persis']} baris kembar dibuang)" if lap["ganda_persis"] else ""))

    status_server, galat_server, _nama_server = baca_status_server(args.list_json or ["list_api_*.json"])
    wilayah: dict = {}
    rows = []
    if args.sheet:
        rows, _hasil = mg.muat_sumber(args.sheet, args.format, mode_satu_subsls=True)
        wilayah = {r.idsubsls: r.wilayah for r in rows if r.wilayah}

    laporan = ringkas_per_kunci(gabungan, lap["asal_per_kunci"], status_server, wilayah, galat_server)

    nama_wil = {r["idsubsls"]: f"{r['kecamatan']} / {r['desa']}" for r in laporan if r["kecamatan"]}
    rekap = (agregat(laporan, "akun_login", "akun")
             + agregat(laporan, "idsubsls_input", "wilayah_input")
             + agregat(laporan, "idsubsls", "wilayah_asli", nama_wil)
             + agregat(laporan, "berkas", "berkas"))
    tabel("PER AKUN (akun yang membuat dokumen)", [b for b in rekap if b["jenis"] == "akun"])
    tabel("PER WILAYAH TEMPAT DOKUMEN DIBUAT (idsubsls_input)",
          [b for b in rekap if b["jenis"] == "wilayah_input"])
    tabel("PER WILAYAH ASLI BARIS (tujuan pindah wilayah nanti)",
          [b for b in rekap if b["jenis"] == "wilayah_asli"][:20], lebar_nilai=40)
    tabel("PER BERKAS ASAL", [b for b in rekap if b["jenis"] == "berkas"])

    c = Counter(r["status"] for r in laporan)
    print("\n=== STATUS AKHIR PER DOKUMEN ===")
    for s, n in c.most_common():
        print(f"  {n:>6}  {s or '(kosong)'}  [{kelompok_status(s)}]")
    if status_server:
        cs = Counter(r["status_server"] or "(tidak ada di list API)" for r in laporan)
        print("\n=== STATUS DI SERVER (dari list_api_*.json, per dokumen) ===")
        for s, n in cs.most_common():
            print(f"  {n:>6}  {s}")
        bergalat = [r for r in laporan if r["galat_server"]]
        if bergalat:
            print(f"  ⚠️ {len(bergalat)} dokumen ditandai GALAT oleh server "
                  "(kartu 'Jumlah Error' di halaman PENDATAAN) — rinciannya di bersihkan_error.py")
    else:
        print("\n(status server kosong — jalankan input_gabungan/sinkron_list.py dulu "
              "supaya ada list_api_<akun>.json)")

    if rows:
        # HANYA kunci milik sheet ini: satu audit bisa memuat dokumen dari sheet lain
        # (format standar & tahap 2 memakai audit yang sama).
        kunci_sheet = {r.kunci for r in rows}
        milik = [r for r in laporan if r["kunci"] in kunci_sheet]
        selesai = {r["kunci"] for r in milik if r["kelompok"] in ("TERKIRIM", "DRY_RUN")}
        dibuat = {r["kunci"] for r in milik}
        belum = [r for r in rows if r.kunci not in dibuat]
        print(f"\n=== THD SHEET {args.sheet} ===")
        print(f"  {len(rows)} baris sheet | {len(selesai)} terkirim | "
              f"{len(dibuat) - len(selesai)} dokumen belum tuntas | {len(belum)} belum disentuh")

    bentrok = periksa_bentrok(gabungan, lap["asal_per_kunci"])
    masalah = sum(len(v) for v in bentrok.values())
    print(f"\n=== PEMERIKSAAN BENTROK: {masalah} ===")
    for judul, isi, catatan in (
        ("dokumen dikerjakan >1 PC", bentrok["lintas_berkas"], "cek apakah dokumennya sama"),
        ("DOKUMEN GANDA (url berbeda utk satu baris)", bentrok["dokumen_ganda"],
         "⛔ duplikat di server — PPL tidak bisa menghapus, laporkan ke admin"),
        ("dokumen tercatat di >1 akun", bentrok["akun_ganda"], "main_gabungan akan melewati baris ini"),
        ("satu dokumen dipakai >1 baris", bentrok["url_banyak_kunci"], "cek nama dokumen di server"),
    ):
        if isi:
            print(f"  ⚠️ {len(isi)} {judul} — {catatan}")
            for k, v in list(isi.items())[:10]:
                print(f"      {k[:60]} -> {v}")

    with Path(args.laporan).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM_LAPORAN)
        w.writeheader()
        w.writerows(laporan)
    with Path(args.agregat).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["jenis", "nilai", "keterangan", "total"] + URUT_KELOMPOK)
        w.writeheader()
        w.writerows(rekap)
    print(f"\nLaporan per dokumen: {args.laporan}\nRekap: {args.agregat}")

    if not args.tulis:
        print(f"\n(laporan saja — tambahkan --tulis utk membuat {args.keluaran})")
        return 0
    tujuan = Path(args.keluaran)
    if tujuan.exists():
        cadangan = tujuan.with_name(tujuan.name + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(tujuan, cadangan)
        print(f"Audit lama dicadangkan: {cadangan}")
    with tujuan.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        w.writeheader()
        for b in gabungan:
            w.writerow({k: b.get(k, "") for k in AUDIT_FIELDS})
    print(f"✅ {len(gabungan)} baris ditulis ke {tujuan} — salin berkas ini ke SEMUA PC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
