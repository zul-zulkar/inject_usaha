#!/usr/bin/env python3
"""
approve_capi.py — approve otomatis assignment CAPI "SUBMITTED BY Pencacah" dari banyak PML.

fasih-web (web-entry) hanya membuka dokumen PAPI, jadi alurnya tiga langkah:

  1. GANTI KE PAPI (fasih-sm, akun ADMIN, Console Chrome):
         python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --console
     -> approve_capi/hasil/approve_capi_console.siap.js (daftar PML tersuntik). Tempel di Console halaman
        Data survei: await approveCapi.periksa() -> kePapi() -> approveCapi.unduh()
        -> simpan CSV approve_capi_<waktu>.csv di bahan/ (atau biarkan di Downloads).
  2. APPROVE (fasih-web, login tiap PML bergiliran, Playwright; password FIXED_PASSWORD di inti/config_lokal.py):
         python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --cek
         python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --eksekusi
     = approve_pml mode server per PML, target = ID yang tercatat DIGANTI_PAPI_TERVERIFIKASI di CSV (list server
       tidak dibaca; dokumen PAPI lain milik PML itu tidak ikut). Opsi lain (--ya, --sso, --login-manual, ...)
       diteruskan apa adanya ke approve_pml.py.
  3. KEMBALIKAN KE CAPI (Console yang sama): await approveCapi.keCapi() -> unduh().
     Hanya dokumen yang diganti alat ini DAN sudah APPROVED.

PARALEL LANGKAH 1 & 3 DI SATU BROWSER: berkas .siap.js yang sama di beberapa tab, kePapi({bagian: "k/n"}) /
keCapi({bagian: "k/n"}) per tab (dokumen dibagi lewat hash id); unduh() di satu tab = CSV gabungan semua bagian.

PARALEL DALAM SATU PC: --paralel K -> K bot approve bersamaan (PML dibagi per jumlah dokumen, satu akun tidak
pernah di dua bot), satu YA utk semua, keluaran berawalan [bot k] + log per bot di approve_capi/hasil/.

PARALEL / BEBERAPA PC: --bagi N membagi daftar PML jadi N bagian SALING LEPAS (beban seimbang; --jumlah
<csv approveCapi.unduhPerPml()> utk menimbang per jumlah dokumen). Tiap bagian = daftar_pml + Console .siap.js
sendiri di approve_capi/hasil/bagian/; satu PC / satu bot mengerjakan satu bagian dari langkah 1 s.d. 3.

Berkas daftar PML: satu email per baris (baris kosong & diawali # diabaikan; koma/spasi juga pemisah).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti import lokasi

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

FOLDER = Path(__file__).resolve().parent
HASIL = lokasi.hasil("approve_capi")
FOLDER_BAGIAN = HASIL / "bagian"
TEMPLAT = FOLDER / "approve_capi_console.js"
KONSOL_SIAP = HASIL / "approve_capi_console.siap.js"
PENANDA_PML = "/*__DAFTAR_PML__*/[]"
PENANDA_LABEL = '/*__LABEL__*/""'
ST_SIAP_APPROVE = "DIGANTI_PAPI_TERVERIFIKASI"
POLA_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def baca_daftar_pml(path: Path) -> tuple[list[str], list[str]]:
    """-> (email unik huruf kecil urut berkas, token yang bukan email)."""
    emails: list[str] = []
    salah: list[str] = []
    for baris in path.read_text(encoding="utf-8-sig").splitlines():
        baris = baris.split("#", 1)[0]
        for tok in re.split(r"[\s,;]+", baris):
            tok = tok.strip().lower()
            if not tok:
                continue
            (emails if POLA_EMAIL.match(tok) else salah).append(tok)
    return list(dict.fromkeys(emails)), salah


def tulis_console(daftar: list[str], keluaran: Path = KONSOL_SIAP, label: str = "") -> Path:
    teks = TEMPLAT.read_text(encoding="utf-8")
    for penanda in (PENANDA_PML, PENANDA_LABEL):
        if teks.count(penanda) != 1:
            raise SystemExit(f"Penanda {penanda} tidak ditemukan tepat satu kali di {TEMPLAT}")
    teks = teks.replace(PENANDA_PML, json.dumps(daftar)).replace(PENANDA_LABEL, json.dumps(label))
    lokasi.siapkan(keluaran).write_text(teks, encoding="utf-8")
    return keluaran


def baca_jumlah(path: Path) -> dict[str, int]:
    """CSV approveCapi.unduhPerPml() (pml, siap, lain) -> {pml: siap}."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {(b.get("pml") or "").strip().lower(): int(b.get("siap") or 0) for b in csv.DictReader(f)}


def bagi_pml(daftar: list[str], n: int, jumlah: dict[str, int] | None = None) -> list[list[str]]:
    """PML -> n bagian SALING LEPAS, beban (jumlah dokumen; tanpa `jumlah`: 1 per PML) seimbang: PML terbesar
    dulu ke bagian paling ringan. Urutan dalam bagian = urutan berkas daftar. Satu PML tidak pernah dipecah
    (satu akun = satu bot)."""
    beban = {p: (jumlah.get(p, 0) if jumlah is not None else 1) for p in daftar}
    urut = {p: i for i, p in enumerate(daftar)}
    bagian: list[list[str]] = [[] for _ in range(max(1, n))]
    total = [0] * len(bagian)
    for p in sorted(daftar, key=lambda x: (-beban[x], urut[x])):
        k = min(range(len(bagian)), key=lambda i: (total[i], len(bagian[i]), i))
        bagian[k].append(p)
        total[k] += beban[p]
    return [sorted(b, key=urut.__getitem__) for b in bagian]


def tulis_bagian(daftar: list[str], n: int, jumlah: dict[str, int] | None,
                 folder: Path = FOLDER_BAGIAN) -> list[tuple[Path, Path, list[str]]]:
    """Tulis daftar_pml.bagian-K-dari-N.txt + approve_capi_console.bagian-K-dari-N.siap.js (bagian lama dihapus)."""
    if folder.exists():
        for lama in folder.glob("*.bagian-*"):
            lama.unlink()
    hasil = []
    for k, b in enumerate(bagi_pml(daftar, n, jumlah), start=1):
        label = f".bagian-{k}-dari-{n}"
        txt = lokasi.siapkan(folder / f"daftar_pml{label}.txt")
        txt.write_text(f"# bagian {k} dari {n}\n" + "".join(f"{p}\n" for p in b), encoding="utf-8")
        hasil.append((txt, tulis_console(b, folder / f"approve_capi_console{label}.siap.js", label), b))
    return hasil


def cari_csv() -> list[Path]:
    """Semua CSV approveCapi.unduh() (semua bagian) di bahan/, approve_capi/hasil/, Downloads — urut lama -> baru."""
    kandidat: set[Path] = set()
    for folder in (lokasi.BAHAN, HASIL, Path.home() / "Downloads"):
        kandidat |= {p for p in folder.glob("approve_capi*.csv")
                     if ".bak" not in p.name and not p.name.startswith("approve_capi_id")}
    return sorted(kandidat, key=lambda p: p.stat().st_mtime)


def gabung_csv(paths: list[Path]) -> list[dict]:
    """Baris per id dari beberapa CSV (lama -> baru; berkas lebih baru menang). Aman lintas bagian: tiap bagian
    hanya menyentuh PML-nya sendiri, dan CSV satu bagian bersifat kumulatif."""
    per_id: dict[str, dict] = {}
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as f:
            baris = list(csv.DictReader(f))
        if not baris or "id" not in baris[0] or "status" not in baris[0]:
            print(f"⚠️ {path}: bukan CSV approveCapi.unduh() — dilewati")
            continue
        for b in baris:
            if (b.get("id") or "").strip():
                per_id[b["id"].strip()] = b
    return list(per_id.values())


def target_approve(baris: list[dict], daftar: list[str]) -> tuple[dict[str, list[str]], Counter, Counter]:
    """CSV Console -> ({pml: [id]} hanya DIGANTI_PAPI_TERVERIFIKASI & PML di daftar, status per CSV,
    PML di CSV yang tidak ada di daftar)."""
    per_pml: dict[str, list[str]] = {p: [] for p in daftar}
    status = Counter()
    luar = Counter()
    for b in baris:
        st = (b.get("status") or "").strip() or "(belum diganti)"
        status[st] += 1
        if st != ST_SIAP_APPROVE:
            continue
        pml = (b.get("pml") or "").strip().lower()
        i = (b.get("id") or "").strip()
        if pml in per_pml and i:
            per_pml[pml].append(i)
        else:
            luar[pml or "(kosong)"] += 1
    return {p: ids for p, ids in per_pml.items() if ids}, status, luar


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daftar-pml", required=True, metavar="TXT", help="email PML, satu per baris")
    ap.add_argument("--console", action="store_true", help="langkah 1/3: tulis Console .siap.js (tanpa browser)")
    ap.add_argument("--bagi", type=int, default=0, metavar="N",
                    help="bagi daftar PML jadi N bagian saling lepas (tiap bagian = satu PC / tab Console / bot)")
    ap.add_argument("--jumlah", metavar="CSV", help="--bagi: CSV approveCapi.unduhPerPml() utk menimbang beban")
    ap.add_argument("--paralel", type=int, default=1, metavar="K",
                    help="approve dgn K bot BERSAMAAN (PML dibagi rata per jumlah dokumen; satu Chromium ±1,5 GB per bot; "
                         "YA ditanyakan sekali utk semua bot)")
    ap.add_argument("--hasil", metavar="CSV", action="append", default=[],
                    help="CSV approveCapi.unduh() (boleh diulang; bawaan: SEMUA approve_capi*.csv di bahan/, "
                         "approve_capi/hasil/, Downloads, digabung — yang lebih baru menang)")
    args, terus = ap.parse_known_args()
    lokasi.cek_struktur_lama()
    daftar, salah = baca_daftar_pml(Path(args.daftar_pml))
    if salah:
        print(f"⚠️ Bukan email, diabaikan: {salah[:10]}")
    if not daftar:
        print(f"❌ {args.daftar_pml}: tidak ada email PML.", file=sys.stderr)
        return 2
    print(f"Daftar PML: {len(daftar)} akun")

    if args.bagi:
        if terus or args.console:
            ap.error("--bagi berdiri sendiri (tanpa --console / opsi approve)")
        jumlah = baca_jumlah(Path(args.jumlah)) if args.jumlah else None
        if jumlah is not None:
            tak = [p for p in daftar if p not in jumlah]
            if tak:
                print(f"  {len(tak)} PML tidak ada di {args.jumlah} (dianggap 0 dokumen): {', '.join(tak[:10])}")
        for txt, js, b in tulis_bagian(daftar, args.bagi, jumlah):
            n = sum(jumlah.get(p, 0) for p in b) if jumlah is not None else None
            print(f"  {txt.relative_to(lokasi.AKAR)}  ({len(b)} PML" + (f", {n} dokumen" if n is not None else "")
                  + f")\n    Console: {js.relative_to(lokasi.AKAR)}")
        print("Tiap bagian = satu PC (atau satu tab Console + satu bot approve). Di PC bagian K:\n"
              "  1. tempel approve_capi_console.bagian-K-dari-N.siap.js di Console fasih-sm -> kePapi -> unduh()\n"
              "  2. python approve_capi/approve_capi.py --daftar-pml "
              "approve_capi/hasil/bagian/daftar_pml.bagian-K-dari-N.txt --eksekusi\n"
              "  3. keCapi di Console yang sama.")
        return 0

    if args.console:
        if terus:
            ap.error(f"opsi tidak dikenal utk --console: {terus}")
        path = tulis_console(daftar)
        print(f"Console siap: {path}\nTempel di Console fasih-sm (halaman Data survei, akun admin), lalu:\n"
              "  await approveCapi.kePapi()\n  approveCapi.unduh()                     // simpan CSV di bahan/\n"
              "Paralel (berkas yang sama di beberapa tab): tab 1 await approveCapi.kePapi({bagian: \"1/4\"}), "
              "tab 2 {bagian: \"2/4\"}, ... lalu unduh() di satu tab (gabungan semua bagian).")
        return 0

    paths = [Path(h) for h in args.hasil] if args.hasil else cari_csv()
    hilang = [str(p) for p in paths if not p.exists()]
    if not paths or hilang:
        print(f"❌ CSV hasil Console {'tidak ada: ' + ', '.join(hilang) if hilang else 'belum ada'} — jalankan "
              "langkah 1 (approveCapi.unduh()) atau isi --hasil.", file=sys.stderr)
        return 2
    baris = gabung_csv(paths)
    per_pml, status, luar = target_approve(baris, daftar)
    print(f"CSV ({len(paths)} berkas, terbaru {paths[-1].name}): {len(baris)} dokumen: "
          + ", ".join(f"{s}: {n}" for s, n in status.most_common()))
    for p in daftar:
        if p in per_pml:
            print(f"  {p}: {len(per_pml[p])} dokumen siap di-approve")
    tanpa = [p for p in daftar if p not in per_pml]
    if tanpa:
        print(f"  PML di daftar tanpa dokumen siap (tidak login): {len(tanpa)} — {', '.join(tanpa[:10])}"
              + (" …" if len(tanpa) > 10 else ""))
    if luar:
        print(f"  Diganti ke PAPI tapi PML-nya tidak di daftar ini (bagian lain / tidak di-approve di sini): "
              f"{sum(luar.values())} dokumen, {len(luar)} PML")
    if not per_pml:
        print("Tidak ada dokumen utk di-approve.")
        return 0
    grup = kelompok_bot(per_pml, args.paralel)
    total = sum(map(len, per_pml.values()))
    mode = " ".join(terus) or "DRY-RUN (tambah --eksekusi utk sungguhan)"
    print(f"\n-> approve_pml: {total} ID, {len(per_pml)} PML, {len(grup)} bot paralel | {mode}")
    for k, g in enumerate(grup, start=1):
        print(f"   bot {k}: {len(g)} PML, {sum(len(per_pml[p]) for p in g)} dokumen")
    peringatan_ram(len(grup))
    eksekusi = "--eksekusi" in terus and "--cek" not in terus
    if len(grup) > 1 and eksekusi and "--ya" not in terus:
        # Satu konfirmasi utk semua bot: bot anak tidak bisa bergantian membaca keyboard yang sama.
        if input(f"Ketik 'YA' utk APPROVE sungguhan {total} dokumen oleh {len(grup)} bot paralel: ").strip().upper() != "YA":
            print("Dibatalkan — tidak ada yang di-approve.")
            return 1
        terus = [*terus, "--ya"]
    stem = Path(args.daftar_pml).stem
    perintah = []
    for k, g in enumerate(grup, start=1):
        # Satu berkas ID per bot (dan per daftar PML): bot & run lain di PC yang sama tidak saling menimpa.
        akhiran = f".bot-{k}-dari-{len(grup)}" if len(grup) > 1 else ""
        id_approve = tulis_id({p: per_pml[p] for p in g}, HASIL / f"approve_capi_id.{stem}{akhiran}.csv")
        perintah.append([sys.executable, str(lokasi.AKAR / "approve_pml" / "approve_pml.py"),
                         "--akun-pml", ",".join(g), "--hanya-id", str(id_approve), *terus])
    if len(perintah) == 1:
        return subprocess.call(perintah[0], cwd=lokasi.AKAR)
    return jalankan_paralel(perintah, stem)


def kelompok_bot(per_pml: dict[str, list[str]], n: int) -> list[list[str]]:
    """PML -> <= n kelompok (satu per bot) saling lepas, beban = jumlah dokumen; kelompok kosong dibuang."""
    return [g for g in bagi_pml(list(per_pml), max(1, n), {p: len(i) for p, i in per_pml.items()}) if g]


def tulis_id(per_pml: dict[str, list[str]], path: Path) -> Path:
    with open(lokasi.siapkan(path), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "pml"])
        for p, ids in per_pml.items():
            w.writerows([i, p] for i in ids)
    return path


RAM_PER_BOT_GB = 1.5   # Python ±0,75 + Chromium ±0,8 (diukur 2026-09-27)


def ram_kosong_gb() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().available / 2**30
    except Exception:
        pass
    try:
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        return m.ullAvailPhys / 2**30 if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) else None
    except Exception:
        return None


def peringatan_ram(n_bot: int) -> None:
    kosong = ram_kosong_gb()
    if kosong is not None and n_bot * RAM_PER_BOT_GB > kosong - 1:
        print(f"⚠️ RAM kosong {kosong:.1f} GB, {n_bot} bot butuh ±{n_bot * RAM_PER_BOT_GB:.1f} GB — Chromium bisa crash "
              f"(pernah terjadi 2026-09-27). Kurangi --paralel (saran: {max(1, int((kosong - 1) // RAM_PER_BOT_GB))}).")


def jalankan_paralel(perintah: list[list[str]], stem: str, jeda_mulai: float = 5) -> int:
    """Jalankan semua bot bersamaan; keluaran tiap bot diberi awalan [bot k] di layar & ditulis ke
    approve_capi/hasil/log_approve_capi.<stem>.bot-k.txt. Ctrl+C menghentikan semua bot. -> 0 kalau semua 0."""
    import threading
    proses = []
    n = len(perintah)
    kunci_cetak = threading.Lock()

    def alirkan(k, pr, log):
        with open(log, "w", encoding="utf-8") as f:
            for baris in pr.stdout:
                f.write(baris)
                f.flush()
                with kunci_cetak:
                    print(f"[bot {k}] {baris}", end="", flush=True)

    benang = []
    for k, cmd in enumerate(perintah, start=1):
        pr = subprocess.Popen(cmd, cwd=lokasi.AKAR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                              env={**_os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        log = lokasi.siapkan(HASIL / f"log_approve_capi.{stem}.bot-{k}-dari-{n}.txt")
        t = threading.Thread(target=alirkan, args=(k, pr, log), daemon=True)
        t.start()
        proses.append(pr)
        benang.append(t)
        time.sleep(jeda_mulai)  # login bertahap, tidak serentak ke SSO
    try:
        kode = [pr.wait() for pr in proses]
    except KeyboardInterrupt:
        print("\nCtrl+C — menghentikan semua bot...", flush=True)
        for pr in proses:
            pr.terminate()
        kode = [pr.wait() for pr in proses]
    for t in benang:
        t.join(timeout=5)
    print("\nSelesai: " + ", ".join(f"bot {k} kode {c}" for k, c in enumerate(kode, start=1))
          + f" | log per bot: {HASIL / f'log_approve_capi.{stem}.bot-*.txt'}", flush=True)
    return 0 if all(c == 0 for c in kode) else 1


if __name__ == "__main__":
    sys.exit(main())
