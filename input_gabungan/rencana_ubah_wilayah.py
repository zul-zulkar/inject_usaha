#!/usr/bin/env python3
"""
rencana_ubah_wilayah.py — rangkum dokumen yang wilayahnya harus dipindah ("ubah
alokasi wilayah") setelah input mode satu subsls. READ-ONLY, TANPA browser & VPN.

Kenapa ada: di mode satu subsls semua dokumen dibuat di subsls & akun input, dan
NAMA dokumen di fasih-web tidak sama dgn kolom nama Excel (format "<nama> (<12a>)",
PT/CV dipindah ke belakang, KOREKSI_NAMA, tanpa 12a kalau > 50 karakter; server
menyimpannya huruf besar). Saat memindah wilayah dokumen dicari lewat nama/ID di
fasih, jadi butuh daftar PER DOKUMEN: ID/URL, nama di fasih, nama Excel, subsls
sekarang -> subsls tujuan.

Sumber (semuanya file lokal):
  - sheet gabungan (--sumber, boleh berulang)  -> nama Excel & idsubsls TUJUAN
  - audit_log_gabungan.csv                       -> dokumen_url, akun, subsls input
  - list_api_<akun>.json (hasil sinkron_list.py) -> status & nama ASLI di server
  - peta SLS GeoJSON (config.PETA_SLS_PATH)      -> subsls tempat titik koordinat jatuh

Tujuan = kolom idsubsls Excel (ketetapan user). Titik koordinat baris (yang juga
diisikan ke geotag dokumen) dipakai MEMERIKSA, bukan memilih tujuan.

status_rencana per dokumen (urutan = prioritas kalau kena lebih dari satu):
  TIDAK_DIKENALI    dokumen di list server yang tidak cocok dgn baris mana pun — jangan dipindah
  BELUM_DISINKRON   akun dokumen belum punya list_api_<akun>.json -> status server tidak diketahui
  CEK_DOKUMEN       DRAFT / >1 dokumen utk baris yang sama / tidak ada lagi di list server
  CEK_WILAYAH       titik koordinat TIDAK di dalam subsls tujuan (atau tujuan tidak ada di peta)
  SUDAH_DI_TUJUAN   subsls input = subsls tujuan, tidak perlu dipindah
  SIAP_PINDAH       terkirim di server & titik koordinat di dalam subsls tujuan

Contoh:
    python input_gabungan/sinkron_list.py --sumber input_usaha.xlsx --akun-tunggal ppl.contoh@mail.com \
        --subsls-tunggal 5108010010000105          # (sekali per akun) unduh list server
    python input_gabungan/rencana_ubah_wilayah.py --sumber input_usaha.xlsx --sumber input_usaha_2.xlsx
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import ASSIGNMENT_ID_GABUNGAN, PETA_SLS_PATH
from inti.gabungan_loader import KOREKSI_NAMA, MAKS_8B, GabunganRow, load_gabungan, nama_tampil
import input_gabungan.main_gabungan as mg
from input_gabungan.sinkron_list import id_dari_url, norm, status_server, url_entry

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LAPORAN_PATH = Path("./rencana_ubah_wilayah.csv")
URUTAN_STATUS = ("TIDAK_DIKENALI", "BELUM_DISINKRON", "CEK_DOKUMEN", "CEK_WILAYAH",
                 "SUDAH_DI_TUJUAN", "SIAP_PINDAH")
KOLOM = ["status_rencana", "catatan", "sumber", "baris", "akun_login", "dokumen_id", "status_server",
         "subsls_sekarang", "subsls_tujuan", "tujuan_wilayah", "subsls_titik", "jarak_titik_ke_tujuan_m",
         "subsls_kolom_pilih", "nama_excel", "nama_di_fasih", "perubahan_nama", "nama_8b_excel",
         "nama_8b_fasih", "perubahan_lain", "latitude", "longitude", "kunci", "dokumen_url"]


# ---------------------------------------------------------------------------
# Peta SLS — titik-dalam-poligon murni Python (tanpa shapely)
# ---------------------------------------------------------------------------

def _dalam_ring(x: float, y: float, ring: list) -> bool:
    dalam = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dalam = not dalam
        j = i
    return dalam


def _dalam_poligon(x: float, y: float, poligon: list) -> bool:
    """poligon GeoJSON = [ring luar, lubang...]."""
    return _dalam_ring(x, y, poligon[0]) and not any(_dalam_ring(x, y, h) for h in poligon[1:])


@dataclass
class PetaSls:
    sls: dict  # idsubsls -> {"nama", "bbox": (minx, miny, maxx, maxy), "poligon": [poligon, ...]}

    def titik(self, lon: float, lat: float) -> list[str]:
        """idsubsls yang memuat titik (normalnya 0 atau 1)."""
        return [i for i, s in self.sls.items()
                if s["bbox"][0] <= lon <= s["bbox"][2] and s["bbox"][1] <= lat <= s["bbox"][3]
                and any(_dalam_poligon(lon, lat, p) for p in s["poligon"])]

    def jarak_m(self, idsubsls: str, lon: float, lat: float) -> float | None:
        """Jarak titik ke batas subsls (meter, pendekatan equirectangular); 0 kalau di dalam."""
        s = self.sls.get(idsubsls)
        if s is None:
            return None
        if any(_dalam_poligon(lon, lat, p) for p in s["poligon"]):
            return 0.0
        kx, ky = 111320 * math.cos(math.radians(lat)), 110574
        terdekat = math.inf
        for poligon in s["poligon"]:
            for ring in poligon:
                for a, b in zip(ring, ring[1:]):
                    ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
                    dx, dy = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
                    panjang = dx * dx + dy * dy
                    t = 0.0 if panjang == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / panjang))
                    terdekat = min(terdekat, math.hypot(ax + t * dx, ay + t * dy))
        return terdekat

    def nama(self, idsubsls: str) -> str:
        return self.sls.get(idsubsls, {}).get("nama", "")


def peta_dari_fitur(features: list[dict]) -> PetaSls:
    sls = {}
    for f in features:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if not p.get("idsubsls") or g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        poligon = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        xs = [pt[0] for pol in poligon for pt in pol[0]]
        ys = [pt[1] for pol in poligon for pt in pol[0]]
        i = p["idsubsls"]
        nama = (f"[{i[4:7]}] {p.get('nmkec', '')} | [{i[7:10]}] {p.get('nmdesa', '')} | "
                f"[{i[10:14]}] {p.get('nmsls', '')} | sub [{i[14:16]}]")
        sls[i] = {"nama": nama, "bbox": (min(xs), min(ys), max(xs), max(ys)), "poligon": poligon}
    return PetaSls(sls)


def muat_peta(path: str | Path) -> PetaSls:
    return peta_dari_fitur(json.loads(Path(path).read_text(encoding="utf-8"))["features"])


# ---------------------------------------------------------------------------
# Logika murni
# ---------------------------------------------------------------------------

def perubahan_nama(row: GabunganRow) -> list[str]:
    """Kenapa nama dokumen di fasih (row.nama_dokumen) beda dgn kolom nama Excel."""
    mentah = " ".join(row.nama.split())
    dok = row.nama_dokumen
    if dok == mentah:
        return []
    hasil = []
    if mentah.upper() in KOREKSI_NAMA:
        hasil.append("nama diganti ketetapan user (KOREKSI_NAMA)")
    if row.akhiran_badan:
        hasil.append(f"'{row.akhiran_badan}' dipindah ke belakang nama")
    tampil = nama_tampil(mentah, row.akhiran_badan)
    pemilik = " ".join(re.sub(r"[()]", " ", row["pengusaha"]).split())
    # format_nama_usaha selalu memberi kurung kalau 12a terisi -> tanpa kurung = nama_muat memakai nama saja.
    if pemilik and "(" not in dok:
        hasil.append(f"tanpa (12a): '<nama> (<12a>)' lebih dari {MAKS_8B} karakter")
    if dok.upper() == tampil.upper():
        return hasil or ["hanya beda huruf besar/kecil"]
    bersih = " ".join(re.sub(r"[()]", " ", tampil).split())
    if pemilik and "(" in dok:
        if dok.upper() == f"({pemilik})".upper():
            hasil.append("nama usaha hanya berisi nama 12a -> ditulis '(12a)'")
        elif re.search(rf"(?<!\w){re.escape(pemilik)}(?!\w)", bersih, flags=re.I):
            hasil.append("nama 12a yang sudah tertulis di nama dipindah ke dalam kurung")
        else:
            hasil.append("nama 12a ditambahkan dalam kurung")
    if bersih != tampil:
        hasil.append("kurung asli di nama dibuang (isinya dipertahankan)")
    return hasil


def periksa_wilayah(row: GabunganRow, peta: PetaSls | None) -> dict:
    """-> {subsls_titik, jarak_titik_ke_tujuan_m, tujuan_wilayah, masalah[], info[]}."""
    tujuan, pilih = row.idsubsls, row.idsubsls_pilih
    out = {"subsls_titik": "", "jarak_titik_ke_tujuan_m": "", "masalah": [], "info": [],
           "tujuan_wilayah": peta.nama(tujuan) if peta else
           " | ".join(filter(None, (row.wilayah.get("kecamatan"), row.wilayah.get("desa"))))}
    if row.wilayah_bentrok:
        out["info"].append(f"alamat 8c bentrok: {row.wilayah_bentrok}")
    if peta is None:
        out["info"].append("titik koordinat tidak dicek (tanpa peta)")
        if pilih != tujuan:
            out["masalah"].append(f"kolom Pilih PROVINSI..SUBSLS menunjuk {pilih}, bukan {tujuan}")
        return out
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
    except ValueError:
        out["masalah"].append(f"koordinat tidak valid ('{row['latitude']}', '{row['longitude']}')")
        return out
    kena = peta.titik(lon, lat)
    out["subsls_titik"] = " | ".join(kena)
    if tujuan not in peta.sls:
        out["masalah"].append(f"subsls tujuan {tujuan} tidak ada di peta (periode peta beda?)")
    else:
        jarak = peta.jarak_m(tujuan, lon, lat)
        out["jarak_titik_ke_tujuan_m"] = round(jarak)
        if not kena:
            out["masalah"].append(f"titik di luar semua SLS peta, {round(jarak)} m dari batas tujuan")
        elif tujuan not in kena:
            out["masalah"].append(f"titik jatuh di {kena[0]} ({peta.nama(kena[0])}), "
                                  f"{round(jarak)} m dari batas tujuan")
    if pilih != tujuan:
        if pilih in kena:
            out["masalah"].append(f"kolom Pilih PROVINSI..SUBSLS ({pilih}) SEPAKAT dgn titik, bukan dgn idsubsls")
        elif tujuan in kena:
            out["info"].append(f"kolom Pilih menunjuk {pilih}, tapi titik membenarkan idsubsls")
        else:
            out["info"].append(f"kolom Pilih menunjuk {pilih}")
    return out


def _akun_dari_nama_file(path: Path) -> str:
    m = re.fullmatch(r"list_api_(.+)\.json", path.name)
    return m.group(1).replace("_at_", "@").lower() if m else ""


def rencana_ubah_wilayah(sumber_rows: list[tuple[str, GabunganRow]], audit: list[dict],
                         lists: dict[str, list[dict]], peta: PetaSls | None,
                         assignment_id: str = ASSIGNMENT_ID_GABUNGAN) -> tuple[list[dict], dict]:
    """Fungsi murni. `lists` = {akun: item list API}. -> (baris laporan per dokumen, ringkasan)."""
    baris_per_kunci: dict[str, tuple[str, GabunganRow]] = {}
    for sumber, row in sumber_rows:
        baris_per_kunci.setdefault(row.kunci, (sumber, row))
    per_nama = defaultdict(set)
    for kunci, (_, row) in baris_per_kunci.items():
        per_nama[norm(row.nama_dokumen)].add(kunci)

    # Dokumen = (akun, id). Dari audit dulu, lalu dilengkapi/ditambah list server.
    dok: dict[tuple[str, str], dict] = {}
    status_audit: dict[tuple[str, str], str] = {}
    for b in audit:
        akun = (b.get("akun_login") or "").lower()
        if b.get("kunci") and akun:
            status_audit[(akun, b["kunci"])] = (b.get("status") or "").strip()
        doc_id = id_dari_url(b.get("dokumen_url"))
        if not doc_id or not akun:
            continue
        d = dok.setdefault((akun, doc_id), {"akun": akun, "id": doc_id, "url": b["dokumen_url"], "catatan": []})
        d["kunci"] = b.get("kunci") or d.get("kunci", "")
        d["subsls_input"] = b.get("idsubsls_input") or d.get("subsls_input", "")

    for akun, items in lists.items():
        for it in items:
            kunci_id = (akun, it["id"])
            if kunci_id not in dok:
                d = {"akun": akun, "id": it["id"], "url": url_entry(it["id"], assignment_id), "kunci": "",
                     "catatan": ["tidak tercatat di audit"]}
                kandidat = per_nama.get(norm(it.get("data1")), set())
                if len(kandidat) == 1:
                    d["kunci"] = next(iter(kandidat))
                    d["catatan"].append("dicocokkan lewat nama")
                elif len(kandidat) > 1:
                    d["catatan"].append(f"nama cocok dgn {len(kandidat)} baris")
                dok[kunci_id] = d
            dok[kunci_id]["server"] = it
            dok[kunci_id]["subsls_input"] = (it.get("codeIdentity") or "")[:16] or dok[kunci_id].get("subsls_input", "")

    ringkasan = Counter()
    dok_per_kunci = defaultdict(list)
    for d in dok.values():
        if d.get("kunci") in baris_per_kunci:
            dok_per_kunci[d["kunci"]].append(d)
        elif d.get("kunci"):
            ringkasan["dokumen_milik_sumber_lain"] += 1

    laporan = []
    for d in dok.values():
        kunci = d.get("kunci", "")
        if kunci and kunci not in baris_per_kunci:
            continue
        server = d.get("server")
        st_server = server.get("assignmentStatusAlias", "") if server else ""
        catatan = list(d["catatan"])
        if kunci not in baris_per_kunci:
            nama = (server or {}).get("data1", "")
            laporan.append({
                "status_rencana": "TIDAK_DIKENALI",
                "catatan": "; ".join(catatan + ([] if nama.strip(" /") else ["dokumen tanpa nama (yatim?)"])),
                "akun_login": d["akun"], "dokumen_id": d["id"], "status_server": st_server,
                "subsls_sekarang": d.get("subsls_input", ""), "nama_di_fasih": nama, "dokumen_url": d["url"],
            })
            continue

        sumber, row = baris_per_kunci[kunci]
        status = []
        if server is None:
            if d["akun"] in lists:
                status.append("CEK_DOKUMEN")
                catatan.append("tidak ada di list server (dihapus? atau list JSON lama — jalankan sinkron_list lagi)")
            else:
                status.append("BELUM_DISINKRON")
                catatan.append(f"list server akun ini belum diunduh (status audit: "
                               f"{status_audit.get((d['akun'], kunci), '-')})")
        elif status_server(st_server) != "TERKIRIM":
            status.append("CEK_DOKUMEN")
            catatan.append(f"server {st_server or '-'}, belum terkirim")
        kembar = dok_per_kunci[kunci]
        if len(kembar) > 1:
            status.append("CEK_DOKUMEN")
            catatan.append(f"baris ini punya {len(kembar)} dokumen: " + ", ".join(
                f"{k['id'][:8]} {k.get('server', {}).get('assignmentStatusAlias', '?')} ({k['akun']})"
                for k in kembar))
        nama_fasih = server.get("data1", "") if server else row.nama_dokumen.upper()
        if server and norm(nama_fasih) != norm(row.nama_dokumen):
            catatan.append(f"nama di server beda dgn nama skrip sekarang ('{row.nama_dokumen}')")

        wil = periksa_wilayah(row, peta)
        if wil["masalah"]:
            status.append("CEK_WILAYAH")
        catatan += wil["masalah"] + wil["info"]
        if d.get("subsls_input") == row.idsubsls:
            status.append("SUDAH_DI_TUJUAN")
        status.append("SIAP_PINDAH")

        lain = [k for k in row.koreksi if not k.startswith("nama usaha diganti")]
        jalan = " ".join(row["jalan_domisili"].split())
        if row.jalan_lengkap != jalan:
            lain.append(f"Nama Jalan '{jalan}' -> '{row.jalan_lengkap}'")
        laporan.append({
            "status_rencana": min(status, key=URUTAN_STATUS.index), "catatan": "; ".join(catatan),
            "sumber": sumber, "baris": row.baris, "akun_login": d["akun"], "dokumen_id": d["id"],
            "status_server": st_server or "-", "subsls_sekarang": d.get("subsls_input", ""),
            "subsls_tujuan": row.idsubsls, "tujuan_wilayah": wil["tujuan_wilayah"],
            "subsls_titik": wil["subsls_titik"], "jarak_titik_ke_tujuan_m": wil["jarak_titik_ke_tujuan_m"],
            "subsls_kolom_pilih": row.idsubsls_pilih if row.idsubsls_pilih != row.idsubsls else "",
            "nama_excel": row.nama, "nama_di_fasih": nama_fasih, "perubahan_nama": "; ".join(perubahan_nama(row)),
            "nama_8b_excel": row["nama_komersial"], "nama_8b_fasih": row.nama_komersial,
            "perubahan_lain": "; ".join(lain), "latitude": row["latitude"], "longitude": row["longitude"],
            "kunci": kunci, "dokumen_url": d["url"],
        })

    ringkasan["baris_tanpa_dokumen"] = sum(1 for k in baris_per_kunci if not dok_per_kunci.get(k))
    laporan.sort(key=lambda l: (URUTAN_STATUS.index(l["status_rencana"]), l.get("sumber", ""),
                                l.get("baris") or 0, l["dokumen_id"]))
    return laporan, dict(ringkasan)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", action="append", required=True, help="xlsx/csv sheet gabungan (boleh berulang)")
    ap.add_argument("--list-json", action="append", default=[],
                    help="list_api_<akun>.json (default: semua list_api_*.json di folder kerja)")
    ap.add_argument("--peta", default=PETA_SLS_PATH, help="GeoJSON batas SUBSLS")
    ap.add_argument("--tanpa-peta", action="store_true", help="lewati cek titik koordinat")
    ap.add_argument("--assignment-id", default=ASSIGNMENT_ID_GABUNGAN)
    ap.add_argument("--keluaran", default=str(LAPORAN_PATH))
    mg.opsi_audit(ap)
    args = ap.parse_args()
    mg.pakai_audit(args.audit)

    lists = {}
    for p in [Path(x) for x in args.list_json] or sorted(Path(".").glob("list_api_*.json")):
        akun = _akun_dari_nama_file(p)
        if not akun:
            print(f"❌ Nama file {p.name} bukan list_api_<akun>.json — akun tidak bisa ditentukan.", file=sys.stderr)
            return 2
        lists[akun] = json.loads(p.read_text(encoding="utf-8"))
        print(f"List server {akun}: {len(lists[akun])} dokumen ({p.name})")

    peta = None
    if not args.tanpa_peta:
        if not args.peta or not Path(args.peta).is_file():
            print(f"❌ Peta SLS tidak ditemukan: '{args.peta}' (isi PETA_SLS_PATH di inti/config_lokal.py, "
                  "atau pakai --peta / --tanpa-peta)", file=sys.stderr)
            return 2
        peta = muat_peta(args.peta)
        print(f"Peta SLS: {len(peta.sls)} subsls ({Path(args.peta).name})")

    sumber_rows = [(s, r) for s in args.sumber for r in load_gabungan(s)]
    laporan, ringkasan = rencana_ubah_wilayah(sumber_rows, mg._baca_audit(), lists, peta, args.assignment_id)

    keluaran = Path(args.keluaran)
    with keluaran.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: dibuka rapi di Excel
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        w.writerows({k: l.get(k, "") for k in KOLOM} for l in laporan)

    print(f"\n=== {len(laporan)} dokumen ===")
    for st in URUTAN_STATUS:
        bagian = [l for l in laporan if l["status_rencana"] == st]
        if not bagian:
            continue
        print(f"\n{st} ({len(bagian)})")
        if st in ("SIAP_PINDAH", "SUDAH_DI_TUJUAN"):
            for (akun, dari), n in Counter((l["akun_login"], l["subsls_sekarang"]) for l in bagian).items():
                print(f"  {n:4d} dokumen di {dari} ({akun})")
            continue
        for l in bagian:
            print(f"  {l.get('sumber', '-')} baris {l.get('baris', '-')} | {l['dokumen_id'][:8]} | "
                  f"{l['nama_di_fasih']} | {l['catatan']}")
    nama_berubah = [l for l in laporan if l.get("perubahan_nama")]
    print(f"\nNama di fasih beda dgn Excel: {len(nama_berubah)} dokumen")
    for jenis, n in Counter(j for l in nama_berubah for j in l["perubahan_nama"].split("; ")).most_common():
        print(f"  {n:4d}  {jenis}")
    if ringkasan.get("baris_tanpa_dokumen"):
        print(f"\nBaris sheet yang belum punya dokumen (tidak masuk laporan): {ringkasan['baris_tanpa_dokumen']}")
    if ringkasan.get("dokumen_milik_sumber_lain"):
        print(f"Dokumen milik sheet yang tidak dimuat --sumber (dilewati): {ringkasan['dokumen_milik_sumber_lain']}")
    print(f"\nRincian per dokumen: {keluaran}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
