#!/usr/bin/env python3
"""
bantu.py — pembantu gui/server.py yang dijalankan sbg PROSES TERPISAH (server tidak pernah
mengimpor modul proyek, jadi config yang dibaca selalu segar & server tetap ringan).
Keluaran = satu objek JSON di stdout.

    python gui/bantu.py config                 daftar pengaturan inti/config.py: nilai bawaan,
                                               nilai inti/config_lokal.py, komentar di atasnya
    python gui/bantu.py kodepos --dari F ...   KODEPOS_BY_DESA dari sheet lama (sama dgn
                                               input_usaha/kodepos_desa.py, tanpa menulis)
    python gui/bantu.py peta F --kode-kab 5108 nama wilayah per idsubsls + kotak koordinat
                                               dari peta poligon SLS (GeoJSON)
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import math
import os
import sys
import tokenize
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

# Tidak ditampilkan di Pengaturan: rahasia, URL layanan, peta selektor form (bukan pengaturan).
DISEMBUNYIKAN = {"FIXED_PASSWORD", "FASIH_WEB_LOGIN_URL", "FASIH_WEB_BASE", "FASIH_SM_BASE",
                 "L", "SEL", "DK", "PESAN_PASSWORD_KOSONG"}
# Dict besar: hanya jumlah entrinya yang dikirim ke halaman.
BESAR = {"KODEPOS_BY_IDSUBSLS", "WILAYAH_BY_IDSUBSLS"}


def _jsonkan(v):
    """Nilai config -> JSON. Tipe non-JSON -> {"__py__": repr} (dibaca balik dgn literal_eval)."""
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    teks = repr(v)
    try:
        ast.literal_eval(teks)
    except (ValueError, SyntaxError):
        return {"__tidak_bisa_diubah__": teks[:2000]}
    if isinstance(v, dict) and all(isinstance(k, str) for k in v) and \
            all(x is None or isinstance(x, (str, bool, int, float)) for x in v.values()):
        return v
    return {"__py__": teks}


def _komentar(sumber: str) -> dict[int, str]:
    """{nomor baris: komentar} — komentar di baris itu sendiri (setelah kode)."""
    hasil = {}
    for tok in tokenize.generate_tokens(io.StringIO(sumber).readline):
        if tok.type == tokenize.COMMENT:
            hasil.setdefault(tok.start[0], tok.string.lstrip("#").strip())
    return hasil


def daftar_config() -> dict:
    os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
    import inti.config as cfg

    path = AKAR / "inti" / "config.py"
    sumber = path.read_text(encoding="utf-8")
    baris = sumber.splitlines()
    komentar_inline = _komentar(sumber)
    urut: dict[str, int] = {}
    for node in ast.parse(sumber).body:
        target = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for t in target:
            if isinstance(t, ast.Name) and t.id.isupper() and t.id not in urut:
                urut[t.id] = node.lineno

    lokal: dict = {}
    path_lokal = AKAR / "inti" / "config_lokal.py"
    galat_lokal = ""
    if path_lokal.exists():
        ruang = {"__name__": "inti.config_lokal", "__file__": str(path_lokal)}
        try:
            exec(compile(path_lokal.read_text(encoding="utf-8"), str(path_lokal), "exec"), ruang)  # noqa: S102
            lokal = {k: v for k, v in ruang.items() if k.isupper()}
        except Exception as e:  # noqa: BLE001
            galat_lokal = f"{type(e).__name__}: {e}"

    item = []
    for nama, n in urut.items():
        if nama in DISEMBUNYIKAN:
            continue
        atas = []
        i = n - 2
        while i >= 0 and baris[i].strip().startswith("#"):
            atas.insert(0, baris[i].strip().lstrip("#").strip())
            i -= 1
        teks = " ".join(x for x in atas + [komentar_inline.get(n, "")] if x and not set(x) <= set("-=# "))
        v = getattr(cfg, nama, None)
        data = {"nama": nama, "baris": n, "komentar": teks, "jenis": type(v).__name__}
        if nama in BESAR:
            data["jumlah"] = len(v or {})
            if nama in lokal:
                data["jumlah_lokal"] = len(lokal[nama] or {})
        else:
            data["bawaan"] = _jsonkan(v)
            if nama in lokal and lokal[nama] != v:
                data["lokal"] = _jsonkan(lokal[nama])
        item.append(data)
    return {"pengaturan": item, "config_lokal_ada": path_lokal.exists(), "galat_config_lokal": galat_lokal,
            "password_lokal_ada": bool(lokal.get("FIXED_PASSWORD"))}


def kodepos(dari: list[str], kode_kab: str) -> dict:
    """Sama dgn input_usaha/kodepos_desa.py (kumpulkan + putuskan), tanpa menulis config_lokal."""
    from input_usaha import kodepos_desa as kd
    stdout = sys.stdout
    sys.stdout = io.StringIO()                  # pesan cetak kodepos_desa jangan merusak JSON
    try:
        suara = kd.kumpulkan([f for f in dari if Path(f).exists()])
        pilih, bentrok = kd.putuskan(suara)
        cetak = sys.stdout.getvalue()
    finally:
        sys.stdout = stdout
    pilih = {d: k for d, k in pilih.items() if d.startswith(kode_kab)}
    return {"pilih": pilih, "bentrok": {d: dict(c) for d, c in bentrok.items() if d.startswith(kode_kab)},
            "catatan": cetak.strip()}


def peta(path: str, kode_kab: str, margin: float) -> dict:
    fitur = json.loads(Path(path).read_text(encoding="utf-8")).get("features") or []
    wilayah, hilang = {}, set()
    lat_min = lon_min = math.inf
    lat_maks = lon_maks = -math.inf
    kab_lain = 0
    for f in fitur:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        ids = str(p.get("idsubsls") or "")
        if len(ids) != 16:
            continue
        if not ids.startswith(kode_kab):
            kab_lain += 1
            continue
        nilai = {"provinsi": p.get("nmprov"), "kabkota": p.get("nmkab"), "kecamatan": p.get("nmkec"),
                 "desa": p.get("nmdesa"), "sls": p.get("nmsls"), "subsls": p.get("nmsls")}
        hilang |= {k for k, v in nilai.items() if not v}
        wilayah[ids] = {k: str(v or "").strip().upper() for k, v in nilai.items()}
        if g.get("type") in ("Polygon", "MultiPolygon"):
            poligon = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for pol in poligon:
                for x, y, *_ in pol[0]:
                    lon_min, lon_maks = min(lon_min, x), max(lon_maks, x)
                    lat_min, lat_maks = min(lat_min, y), max(lat_maks, y)
    kotak = None
    if wilayah and lat_min < math.inf:
        kotak = [math.floor((lat_min - margin) * 100) / 100, math.ceil((lat_maks + margin) * 100) / 100,
                 math.floor((lon_min - margin) * 100) / 100, math.ceil((lon_maks + margin) * 100) / 100]
    return {"wilayah": wilayah, "jumlah": len(wilayah), "kab_lain": kab_lain, "kotak": kotak,
            "kolom_kosong": sorted(hilang)}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="perintah", required=True)
    sub.add_parser("config")
    k = sub.add_parser("kodepos")
    k.add_argument("--dari", action="append", default=[])
    k.add_argument("--kode-kab", default="")
    p = sub.add_parser("peta")
    p.add_argument("berkas")
    p.add_argument("--kode-kab", required=True)
    p.add_argument("--margin", type=float, default=0.05)
    args = ap.parse_args()
    try:
        if args.perintah == "config":
            hasil = daftar_config()
        elif args.perintah == "kodepos":
            hasil = kodepos(args.dari, args.kode_kab)
        else:
            hasil = peta(args.berkas, args.kode_kab, args.margin)
    except Exception as e:  # noqa: BLE001
        hasil = {"galat": f"{type(e).__name__}: {e}"}
    print(json.dumps(hasil, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
