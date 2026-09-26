#!/usr/bin/env python3
"""
pulihkan_excel.py — pulihkan `audit_log_gabungan.csv` yang RUSAK karena pernah
dibuka lalu DISIMPAN Excel.

Excel membaca kolom teks sbg angka lalu menulisnya kembali (kejadian 2026-09-24):

    kunci      "1404364e03"          -> "1.40E+09"      (hash yang kebetulan angka+e)
    idsubsls   "5108060006000224"    -> "5.10806E+15"   (SEMUA baris; 16 digit)
    kbli       "01464"               -> "1464"
    timestamp  "2026-09-23 18:05:12" -> "9/23/2026 18:05"

Akibatnya baris tidak dikenali lagi: SKIP_NAMA_DIPAKAI_BARIS_LAIN ("nama sudah jadi
nama dokumen baris lain (kunci 1.40E+09)"), dokumen dianggap milik subsls lain, atau
dokumen dibuat GANDA. Digit yang hilang tidak bisa dihitung balik dari berkas itu
sendiri, jadi dicari dari RUJUKAN yang masih utuh — dan setiap nilai pulihan WAJIB
menghasilkan tampilan Excel yang sama ("5108060006000224" -> "5.10806E+15"):

  1. baris yang sama di audit UTUH (cadangan .bak-*, audit/pc/, --rujukan) -> dipakai utuh
  2. per kolom: kunci dari (baris, nama usaha); idsubsls dari kunci; idsubsls_input dari
     URL dokumen yang sama, lalu kode identitas list_api_*.json, lalu (kunci, akun);
     kbli dari kunci / nol di depan; timestamp -> 2026-09-23 18:05:00
  3. --sheet (opsional): kunci & idsubsls dari sheet sumber

Nilai yang tetap tidak ketemu (atau kandidatnya lebih dari satu) dilaporkan, dan
berkas TIDAK ditulis — tidak ada yang ditebak.

    python antar_pc/pulihkan_excel.py              # rencana saja
    python antar_pc/pulihkan_excel.py --tulis      # tulis (cadangan .bak otomatis)

Bawaan memeriksa audit_log_gabungan.csv & audit/pc/**/*.csv (subfolder per PC ikut); yang utuh dilewati.
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import datetime
import glob
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti import lokasi  # noqa: E402
import input_usaha.mesin as mg  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

TARGET_BAWAAN = [str(mg.AUDIT_LOG_PATH), str(lokasi.AUDIT / "pc" / "**" / "*.csv")]
RUJUKAN_BAWAAN = [str(lokasi.AUDIT / "**" / "audit_log_gabungan*.csv*"), str(lokasi.AUDIT / "pc" / "**" / "*.csv"),
                  str(lokasi.AUDIT / "pc" / "**" / "*.csv.bak-*")]
SHEET_BAWAAN = str(lokasi.BAHAN / "input_usaha.xlsx")
KOLOM_TIDAK_DIUBAH = ("baris", "nama_usaha", "status", "dokumen_url", "akun_login", "error_message")
# Tanda +/- WAJIB: tulisan Excel selalu "1.40E+09". Kunci "039573e516" (di luar jangkauan
# angka Excel) justru dibiarkan Excel apa adanya — itu kunci utuh, bukan angka rusak.
_POLA_ILMIAH = re.compile(r"(-?\d+)(?:[.,](\d+))?E([+-]\d+)", re.I)
_POLA_WAKTU = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2})(?::(\d{2}))?")


# --------------------------------------------------------------------------
# Logika murni (diuji tests/test_pulihkan_excel.py)
# --------------------------------------------------------------------------
def cocok_excel(asli: str, tampil: str) -> bool:
    """True kalau `asli` yang ditulis ulang Excel menghasilkan `tampil`.
    "1404364e03" ~ "1.40E+09"; "5108060006000224" ~ "5.10806E+15"; "01464" ~ "1464"."""
    asli, tampil = (asli or "").strip(), (tampil or "").strip()
    if asli == tampil:
        return True
    m = _POLA_ILMIAH.fullmatch(tampil)
    if not m:
        if tampil.isdigit() and asli.isdigit():
            return asli.lstrip("0") == tampil.lstrip("0")
        return asli == tampil
    try:
        x = Decimal(asli)          # "1404364e03" juga angka yang sah
    except InvalidOperation:
        return False
    desimal = len(m.group(2) or "")
    pangkat = int(m.group(3))
    if not x.is_finite() or abs(x.adjusted() - pangkat) > 1:
        return False        # mis. kunci "2e87654321": angka sah tapi jauh dari tampilannya
    nilai = Decimal(f"{m.group(1)}.{m.group(2) or '0'}E{pangkat}")
    # Excel membulatkan ke `desimal` angka di belakang koma -> selisih <= setengah digit terakhir.
    return abs(x - nilai) <= Decimal(5).scaleb(pangkat - desimal - 1)


def urutan_tanggal(nilai: list[str]) -> str:
    """"MD" (9/23/2026, Excel bahasa Inggris) atau "DM" (23/09/2026, bahasa Indonesia),
    diputuskan dari tanggal yang tidak ambigu di berkas yang sama."""
    md = dm = 0
    for v in nilai:
        m = _POLA_WAKTU.fullmatch(v or "")
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            md += b > 12
            dm += a > 12
    return "DM" if dm > md else "MD"


def waktu_iso(v: str, urutan: str = "MD") -> str:
    """"9/23/2026 4:25" -> "2026-09-23 04:25:00"; nilai lain dikembalikan apa adanya."""
    m = _POLA_WAKTU.fullmatch(v or "")
    if not m:
        return v
    a, b, th, j, mn, dt = m.groups()
    bulan, hari = (int(a), int(b)) if urutan == "MD" else (int(b), int(a))
    return f"{th}-{bulan:02d}-{hari:02d} {int(j):02d}:{mn}:{int(dt or 0):02d}"


def _sama_menit(asli: str, rusak: str, urutan: str) -> bool:
    return (asli or "")[:16] == waktu_iso(rusak, urutan)[:16]


def baris_cocok(utuh: dict, rusak: dict, urutan: str) -> bool:
    """Baris audit utuh `utuh` = versi asli baris rusak `rusak`?"""
    for k, v in rusak.items():
        u = utuh.get(k, "")
        if k == "timestamp":
            if not _sama_menit(u, v, urutan):
                return False
        elif k in ("kunci", "idsubsls", "idsubsls_input", "kbli"):
            if not cocok_excel(u, v):
                return False
        elif (u or "") != (v or ""):
            return False
    return True


def _satu(kandidat, tampil: str) -> tuple[str, list[str]]:
    """(nilai, semua kandidat yang cocok) — nilai "" kalau tidak tepat satu."""
    cocok = sorted({c for c in kandidat if c and cocok_excel(c, tampil)})
    return (cocok[0] if len(cocok) == 1 else ""), cocok


def pulihkan(rusak: list[dict], rujukan: list[dict], kode_dokumen: dict | None = None,
             sheet: list[tuple[str, str, str, str]] | None = None) -> tuple[list[dict], list[dict]]:
    """(baris hasil, daftar masalah). `rujukan` = baris audit UTUH; `kode_dokumen` =
    {id dokumen: subsls 16 digit} dari list API; `sheet` = [(baris, nama_dokumen, kunci,
    idsubsls)]. Baris yang tidak rusak dikembalikan apa adanya."""
    kode_dokumen, sheet = kode_dokumen or {}, sheet or []
    urutan = urutan_tanggal([b.get("timestamp", "") for b in rusak])
    per_isi: dict = defaultdict(list)
    for u in rujukan:
        per_isi[tuple(u.get(k, "") for k in KOLOM_TIDAK_DIUBAH)].append(u)

    hasil: list[dict | None] = [None] * len(rusak)
    for i, b in enumerate(rusak):
        if not mg.kerusakan_excel([b]) and not (b.get("kbli", "").isdigit() and len(b["kbli"]) == 4):
            hasil[i] = dict(b)
            continue
        cocok = [u for u in per_isi.get(tuple(b.get(k, "") for k in KOLOM_TIDAK_DIUBAH), [])
                 if baris_cocok(u, b, urutan)]
        if cocok:
            hasil[i] = {k: cocok[0].get(k, "") for k in b}

    # Indeks per kolom dari baris UTUH: rujukan + baris yang sudah pulih di langkah 1.
    utuh = rujukan + [h for h in hasil if h and not mg.kerusakan_excel([h])]
    kunci_dari: dict = defaultdict(set)
    nilai_per_kunci: dict = defaultdict(lambda: defaultdict(set))
    input_per_url: dict = defaultdict(set)
    input_per_kunci_akun: dict = defaultdict(set)
    for u in utuh:
        kunci_dari[(u.get("baris", ""), u.get("nama_usaha", ""))].add(u.get("kunci", ""))
        for kol in ("idsubsls", "kbli"):
            nilai_per_kunci[u.get("kunci", "")][kol].add(u.get(kol, ""))
        if u.get("idsubsls_input"):
            if u.get("dokumen_url"):
                input_per_url[u["dokumen_url"]].add(u["idsubsls_input"])
            input_per_kunci_akun[(u.get("kunci", ""), (u.get("akun_login") or "").lower())].add(u["idsubsls_input"])
    for baris, nama, kunci, idsubsls in sheet:
        kunci_dari[(baris, nama)].add(kunci)
        nilai_per_kunci[kunci]["idsubsls"].add(idsubsls)

    masalah: list[dict] = []
    tunda: list[int] = []            # idsubsls_input yang belum ketemu di putaran pertama
    for i, b in enumerate(rusak):
        if hasil[i] is not None:
            continue
        h = dict(b)
        h["timestamp"] = waktu_iso(b.get("timestamp", ""), urutan)

        def gagal(kol, kandidat):
            masalah.append({"indeks": i, "baris": b.get("baris", ""), "nama_usaha": b.get("nama_usaha", ""),
                            "kolom": kol, "nilai_rusak": b.get(kol, ""), "kandidat": " | ".join(kandidat)})

        if b.get("kunci") and not mg._POLA_KUNCI_AUDIT.fullmatch(b["kunci"]):
            h["kunci"], kand = _satu(kunci_dari[(b.get("baris", ""), b.get("nama_usaha", ""))], b["kunci"])
            if not h["kunci"]:
                gagal("kunci", kand)
                h["kunci"] = b["kunci"]
        kunci = h["kunci"]
        if mg._POLA_ANGKA_ILMIAH.fullmatch(b.get("idsubsls") or ""):
            h["idsubsls"], kand = _satu(nilai_per_kunci[kunci]["idsubsls"], b["idsubsls"])
            if not h["idsubsls"]:
                gagal("idsubsls", kand)
                h["idsubsls"] = b["idsubsls"]
        if mg._POLA_ANGKA_ILMIAH.fullmatch(b.get("idsubsls_input") or ""):
            tampil, nilai = b["idsubsls_input"], ""
            id_dok = _id_url(b)
            # Kolom wilayah_dokumen baris ITU SENDIRI paling langsung: mencatat subsls run-nya.
            # Audit lama bisa mencatat satu dokumen dgn 2 subsls (dibuat di ...0205, lalu
            # sinkron_list run ...0116 menulisnya ulang) — karena itu URL bukan yang pertama.
            for sumber in ({subsls_dari_catatan_wilayah(b.get("wilayah_dokumen", ""))} - {""},
                           input_per_url.get(b.get("dokumen_url", ""), set()) if b.get("dokumen_url") else set(),
                           {kode_dokumen[id_dok]} if id_dok in kode_dokumen else set(),
                           input_per_kunci_akun.get((kunci, (b.get("akun_login") or "").lower()), set())):
                nilai, kand = _satu(sumber, tampil)
                if nilai or len(kand) > 1:
                    break
            if nilai:
                h["idsubsls_input"] = nilai
            else:
                tunda.append(i)
        kbli = b.get("kbli", "")
        if kbli.isdigit() and len(kbli) < 5:
            asal = {k for k in nilai_per_kunci[kunci]["kbli"] if k and cocok_excel(k, kbli)}
            h["kbli"] = asal.pop() if len(asal) == 1 else kbli.zfill(5)
        hasil[i] = h

    # Putaran 2: dokumen yang SAMA di berkas ini sendiri (baris DRAFT_TANPA_KOORDINAT
    # tanpa kolom wilayah, sedangkan baris DOKUMEN_DIBUAT-nya punya).
    input_url_sini: dict = defaultdict(set)
    for h in hasil:
        if h and h.get("dokumen_url") and (h.get("idsubsls_input") or "").isdigit():
            input_url_sini[h["dokumen_url"]].add(h["idsubsls_input"])
    disimpulkan: list[dict] = []
    for i in tunda:
        b, h = rusak[i], hasil[i]
        nilai, kand = _satu(input_url_sini.get(b.get("dokumen_url", ""), set()) if b.get("dokumen_url") else set(),
                            b["idsubsls_input"])
        if not nilai:
            # Putaran 3: subsls RUN yang sama — akun sama, ±`MENIT_RUN` menit, tampilan Excel
            # sama, dan sepakat dgn 14 digit wilayah dokumen kalau ada. Satu proses per akun
            # (kunci_proses_akun) = satu subsls per run.
            awalan = subsls_dari_catatan_wilayah(b.get("wilayah_dokumen", ""), minimal=14)
            dugaan = {v for v in _subsls_sekitar(hasil, h, rujukan) if v.startswith(awalan)}
            nilai, kand = _satu(dugaan & set(kand) if len(kand) > 1 else dugaan, b["idsubsls_input"])
            if nilai:
                disimpulkan.append({"baris": b.get("baris", ""), "nama_usaha": b.get("nama_usaha", ""),
                                    "status": b.get("status", ""), "idsubsls_input": nilai,
                                    "ada_dokumen": bool(b.get("dokumen_url"))})
        if nilai:
            h["idsubsls_input"] = nilai
        else:
            masalah.append({"indeks": i, "baris": b.get("baris", ""), "nama_usaha": b.get("nama_usaha", ""),
                            "kolom": "idsubsls_input", "nilai_rusak": b["idsubsls_input"],
                            "kandidat": " | ".join(kand)})
    return [h for h in hasil if h is not None], masalah, disimpulkan


MENIT_RUN = 30


def _subsls_sekitar(hasil: list, h: dict, rujukan: list[dict]) -> set:
    """idsubsls_input baris akun yang sama dlm ±MENIT_RUN menit dari baris `h`."""
    try:
        t = datetime.datetime.strptime(h.get("timestamp", "")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return set()
    akun = (h.get("akun_login") or "").lower()
    out = set()
    for x in list(hasil) + rujukan:
        if not x or x is h or (x.get("akun_login") or "").lower() != akun:
            continue
        v = x.get("idsubsls_input") or ""
        if not (v.isdigit() and len(v) == 16):
            continue
        try:
            tx = datetime.datetime.strptime(x.get("timestamp", "")[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if abs((tx - t).total_seconds()) <= MENIT_RUN * 60:
            out.add(v)
    return out


def subsls_dari_catatan_wilayah(teks: str, minimal: int = 16) -> str:
    """Kolom audit `wilayah_dokumen` -> subsls tempat dokumen dibuat/diisi ("" = tidak pasti).
    "COCOK: prov='[51] ..'; ..; kode_sls='000116'" -> 5108060006000116 (kode SLS 6 digit);
    "BEDA: wilayah dokumen BUKAN <subsls run>: ... | <wilayah>" -> wilayah 16 digit kalau
    terbaca (input_usaha mencatatnya sbg idsubsls_input), selain itu subsls run.
    `minimal`=14 juga menerima kode SLS 4 digit (tanpa subsls) — dipakai sbg penyaring."""
    teks = teks or ""
    bagian = teks.rsplit("|", 1)[-1] if teks.startswith("BEDA") else teks.split(":", 1)[-1]
    nilai = {k: v for k, v in re.findall(r"(\w+)='([^']*)'", bagian)}
    nyata = mg.idsubsls_dari_wilayah(nilai) if nilai else ""
    if teks.startswith("BEDA"):
        run = re.search(r"BUKAN (\d{16})", teks)
        if len(nyata) == 16:
            return nyata
        return run.group(1) if run and minimal == 16 else nyata if len(nyata) >= minimal else ""
    return nyata if len(nyata) >= minimal else ""


def _id_url(b: dict) -> str:
    bagian = [p for p in (b.get("dokumen_url") or "").split("/") if p]
    return bagian[-2] if len(bagian) >= 2 and bagian[-1] == "entry" else ""


# --------------------------------------------------------------------------
# I/O & CLI
# --------------------------------------------------------------------------
def _berkas(pola: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in pola:
        # glob.glob, bukan Path().glob: --audit / FASIH_AUDIT boleh path absolut.
        for f in ([Path(x) for x in sorted(glob.glob(p, recursive=True))] if any(c in p for c in "*?") else [Path(p)]):
            if f.is_file() and f not in out:
                out.append(f)
    return out


def _baca(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def kode_dari_list_api(pola: str = lokasi.POLA_LIST_API) -> dict:
    """{id dokumen: 16 digit awal codeIdentity} — wilayah dokumen SEKARANG di server."""
    out = {}
    for f in lokasi.cari(pola):
        try:
            for it in json.loads(f.read_text(encoding="utf-8")):
                kode = str(it.get("codeIdentity") or "")[:16]
                if it.get("id") and kode.isdigit():
                    out[it["id"]] = kode
        except (ValueError, OSError):
            pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="append", default=[],
                    help="audit yang dipulihkan (boleh pola; default audit_log_gabungan.csv & audit/pc/**/*.csv)")
    ap.add_argument("--rujukan", action="append", default=[],
                    help="audit UTUH tambahan sbg sumber nilai asli (mis. audit dari PC lain)")
    ap.add_argument("--sheet", default=SHEET_BAWAAN if Path(SHEET_BAWAAN).exists() else "",
                    help=f"sheet sumber sbg cadangan kunci & idsubsls (default {SHEET_BAWAAN} kalau ada; "
                         "'' = tanpa sheet)")
    mg.opsi_format(ap, "format --sheet (bawaan tahap2; agenda = format lama)")
    ap.add_argument("--tulis", action="store_true", help="tulis hasil (berkas lama dicadangkan .bak-*)")
    args = ap.parse_args(argv)

    target = [(p, *_baca(p)) for p in _berkas(args.audit or TARGET_BAWAAN)]
    target = [(p, judul, b) for p, judul, b in target if "kunci" in judul and mg.kerusakan_excel(b)]
    if not target:
        print("✅ Tidak ada audit yang rusak Excel.")
        return 0

    rujukan, dipakai = [], []
    # Cadangan audit bernama lain (--audit / FASIH_AUDIT) ikut jadi rujukan.
    for p in _berkas(RUJUKAN_BAWAAN + [f"{mg.AUDIT_LOG_PATH}.bak-*"] + args.rujukan):
        try:
            judul, b = _baca(p)
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
        if "kunci" in judul and b and not mg.kerusakan_excel(b):
            rujukan += b
            dipakai.append(f"{p} ({len(b)})")
    print(f"Rujukan utuh: {len(dipakai)} berkas, {len(rujukan)} baris")
    for d in dipakai:
        print(f"  {d}")
    kode = kode_dari_list_api()
    print(f"Kode identitas list_api_*.json: {len(kode)} dokumen")
    sheet = []
    if args.sheet:
        rows, _ = mg.muat_sumber(args.sheet, args.format, mode_satu_subsls=True)
        sheet = [(str(r.baris), r.nama_dokumen, r.kunci, r.idsubsls) for r in rows]
        print(f"Sheet {args.sheet}: {len(sheet)} baris")

    ada_masalah = False
    for p, judul, baris in target:
        rusak = mg.kerusakan_excel(baris)
        hasil, masalah, disimpulkan = pulihkan(baris, rujukan, kode, sheet)
        utuh = sum(1 for a, h in zip(baris, hasil) if a == h)
        berubah = Counter(k for a, h in zip(baris, hasil) for k in a if a[k] != h.get(k))
        print(f"\n=== {p} — {len(baris)} baris, rusak: "
              f"{', '.join(f'{k} {n}' for k, n in rusak.most_common())}")
        print(f"  dipulihkan per kolom: {', '.join(f'{k} {n}' for k, n in berubah.most_common()) or '-'}"
              f"  (baris tidak berubah: {utuh})")
        kunci_pulih = sorted({(a['kunci'], h['kunci'], a['baris'], a['nama_usaha'][:40])
                              for a, h in zip(baris, hasil) if a['kunci'] != h['kunci']})
        for lama, baru, br, nama in kunci_pulih:
            print(f"  kunci {lama:>10} -> {baru}  baris {br:>5}  {nama}")
        if disimpulkan:
            print(f"  ℹ️  {len(disimpulkan)} idsubsls_input disimpulkan dari RUN yang sama (akun sama, "
                  f"±{MENIT_RUN} mnt; {sum(d['ada_dokumen'] for d in disimpulkan)} di antaranya punya dokumen):")
            for d in disimpulkan[:10]:
                print(f"     baris {d['baris']:>5} {d['status']:<28} -> {d['idsubsls_input']}  {d['nama_usaha'][:35]}")
        if masalah:
            ada_masalah = True
            print(f"  ❌ {len(masalah)} nilai TIDAK bisa dipulihkan (tidak ada / lebih dari satu kandidat):")
            for m in masalah[:30]:
                print(f"     baris {m['baris']:>5} {m['kolom']:<15} {m['nilai_rusak']:<12} "
                      f"kandidat [{m['kandidat'][:60]}]  {m['nama_usaha'][:35]}")
            continue
        if mg.kerusakan_excel(hasil):
            ada_masalah = True
            print(f"  ❌ masih rusak sesudah dipulihkan: {dict(mg.kerusakan_excel(hasil))}")
            continue
        if not args.tulis:
            continue
        cadangan = p.with_name(p.name + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-excel")
        shutil.copy2(p, cadangan)
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=judul)
            w.writeheader()
            w.writerows(hasil)
        print(f"  ✅ ditulis; versi rusak dicadangkan: {cadangan}")

    if ada_masalah:
        print("\nBerkas yang bermasalah TIDAK ditulis. Tambahkan rujukan utuh (--rujukan audit PC lain "
              "yang belum pernah disimpan Excel) atau --sheet, lalu jalankan lagi.")
        return 2
    if not args.tulis:
        print("\n(rencana saja — tambahkan --tulis utk menulis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
