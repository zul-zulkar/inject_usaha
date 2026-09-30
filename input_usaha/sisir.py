#!/usr/bin/env python3
"""
sisir.py — PENYISIRAN semua batch: habiskan draft & input baris yang tertinggal, dgn
beberapa akun PPL sekaligus (paralel, akun dipindah-pindah otomatis).

Bukan alur input baru: tiap pekerjaan = satu proses `jalankan.py` biasa
(`--baris … --akun-tunggal … --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda`),
jadi semua pengaman mesin (audit, kunci proses per akun, cek wilayah, GALAT) tetap berlaku.

Yang dikerjakan skrip ini:
  1. RENCANA (offline, tanpa browser): tiap sheet dibaca dgn audit-nya masing-masing
     (`--daftar-sheet`: satu baris `<sheet> [<audit>]`), lalu tiap baris yang LOLOS
     pemeriksaan data digolongkan:
       - TUNTAS            : status terakhir di audit sudah terkirim/terkunci/dipindah
       - MILIK_AKUN        : dokumen sudah ada (draft/galat) -> HANYA akun pembuatnya
                             (akun_login audit) yang boleh mengerjakan
       - BARU              : belum punya dokumen -> dibagi ke akun mana pun, per potongan
                             `--per-potong` baris; satu baris hanya pernah ada di SATU potongan
       - PERLU_SINKRON     : bertanda dokumen tanpa URL -> jalankan sinkron_list dulu
       - ID_SHEET_SAJA     : ada ID di sheet tapi audit tidak kenal -> pemilik tak diketahui
       - AKUN_LUAR_DAFTAR  : dokumen milik akun yang tidak ada di --akun
     Tiga golongan terakhir TIDAK dikerjakan, hanya dilaporkan.
  2. EKSEKUSI (`--submit`, ketik YA SEKALI): `--paralel` proses sekaligus (bawaan 4). Satu
     akun = satu proses. Pekerjaan MILIK_AKUN didahulukan. Kena limit -> akun istirahat
     `--jeda-limit` detik, potongan BARU-nya dikembalikan ke antrean utk akun lain.
     Sesudah antrean habis, rencana DIHITUNG ULANG dari audit (putaran berikutnya) sampai
     tidak ada kemajuan atau `--maks-putaran` tercapai.

Tanpa `--submit` = hanya mencetak rencana (+ CSV `input_usaha/hasil/sisir_rencana.csv`).

⚠️ SEBELUM menjalankan: audit SEMUA PC harus sudah digabung ke audit di PC ini
(antar_pc/gabung_audit.py) & PC lain sudah berhenti. Baris yang dikerjakan PC lain tapi belum
tercatat di sini akan dianggap BARU -> dokumen GANDA.

CONTOH:
    python input_usaha/sisir.py --daftar-sheet bahan/sisir_sheet.txt --daftar-akun bahan/akun_sisir.txt ^
        --subsls 5108060006000224
    python input_usaha/sisir.py ... --submit --paralel 4
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from inti import lokasi  # noqa: E402
from inti.config import SISIR_SUBSLS  # noqa: E402
from input_usaha.otomatis import evaluasi_hasil  # noqa: E402

GOL_TUNTAS = "TUNTAS"
GOL_MILIK = "MILIK_AKUN"
GOL_BARU = "BARU"
GOL_SINKRON = "PERLU_SINKRON"
GOL_ID_SAJA = "ID_SHEET_SAJA"
GOL_LUAR = "AKUN_LUAR_DAFTAR"
GOL_DITOLAK = "DITOLAK_PEMERIKSAAN"
GOL_BUKAN_DRAFT = "BUKAN_DRAFT_SERVER"
GOL_TUNGGU = "DITOLAK_TUNGGU_KOREKSI"
DIKERJAKAN = (GOL_MILIK, GOL_BARU)

HASIL = lokasi.HASIL_INPUT / "sisir"
RENCANA_CSV = lokasi.HASIL_INPUT / "sisir_rencana.csv"
# Bawaan supaya cukup satu perintah pendek (isi berkasnya data lokal, di bahan/ yang gitignored).
DAFTAR_SHEET_BAWAAN = lokasi.BAHAN / "sisir_sheet.txt"
DAFTAR_AKUN_BAWAAN = lokasi.BAHAN / "akun_sisir.txt"


# ---------------------------------------------------------------- masukan

@dataclass(frozen=True)
class Sheet:
    sumber: str
    audit: str = ""   # "" = audit bawaan

    @property
    def label(self) -> str:
        return Path(self.sumber).stem


def baca_daftar_sheet(path: str) -> list[Sheet]:
    out = []
    for n, baris in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        baris = baris.split("#", 1)[0].strip()
        if not baris:
            continue
        bagian = baris.split()
        if len(bagian) > 2:
            raise SystemExit(f"{path} baris {n}: format '<sheet> [<audit>]' (tanpa spasi di path): {baris!r}")
        out.append(Sheet(bagian[0], bagian[1] if len(bagian) > 1 else ""))
    if not out:
        raise SystemExit(f"{path}: tidak ada sheet.")
    return out


POLA_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def baca_akun(teks: str) -> list[str]:
    akun = []
    for e in POLA_EMAIL.findall(teks):
        e = e.lower()
        if e not in akun:
            akun.append(e)
    return akun


# ---------------------------------------------------------------- rencana (fungsi murni)

@dataclass
class BarisRencana:
    sheet: Sheet
    baris: int
    nama: str
    golongan: str
    akun: str = ""        # pemilik dokumen (MILIK_AKUN / AKUN_LUAR_DAFTAR)
    status: str = ""      # status terakhir audit
    catatan: str = ""


def golongkan(baris: int, nama: str, kunci: str, lolos: bool, punya_koordinat: bool, id_sheet: str,
              status: str, dokumen: tuple | None, akun_dipakai: set, tuntas_fn) -> tuple[str, str]:
    """-> (golongan, akun). `dokumen` = (akun_login, idsubsls_input, url) dari mesin.dokumen_dari."""
    import input_usaha.mesin as mg
    if not lolos:
        return GOL_DITOLAK, ""
    if tuntas_fn(status, punya_koordinat):
        return GOL_TUNTAS, ""
    if status in mg.STATUS_TANPA_URL_SEMUA:
        return GOL_SINKRON, (dokumen[0] if dokumen else "")
    if dokumen:
        akun = (dokumen[0] or "").lower()
        return (GOL_MILIK if akun in akun_dipakai else GOL_LUAR), akun
    if id_sheet:
        return GOL_ID_SAJA, ""
    return GOL_BARU, ""


@dataclass
class DraftServer:
    """Ekspor daftar DRAFT fasih-sm (--daftar-draft): baris sheet yang dokumennya MASIH draft di
    server menurut ekspor itu, dan jam ekspor diunduh (mtime berkas)."""
    baris: set          # {(sumber, baris)}
    jam: str            # "YYYY-MM-DD HH:MM:SS"


def muat_draft_server(path: str, sheets: list[Sheet], tulis: bool = False) -> DraftServer:
    """Terapkan ekspor fasih-sm (terapkan_daftar_draft: tulis=True -> DRAFT_DI_SERVER / DITOLAK_PML ke
    audit) lalu kembalikan baris yang dokumennya masih draft/rejected di server."""
    from input_usaha import terapkan_daftar_draft as tdd
    print(f"\n--- Daftar fasih-sm {path} ---")
    hasil = tdd.terapkan(path, sheets, tulis)
    baris = {(c.sheet.sumber, c.row.baris) for _, g, c, _ in hasil
             if c is not None and g in (tdd.G_PALSU, tdd.G_KUNCI, tdd.G_ANTRE, tdd.G_DITOLAK, tdd.G_BASI)}
    jam = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(Path(path).stat().st_mtime))
    print(f"Daftar draft server: {len(baris)} baris sheet masih DRAFT per {jam} ({path})")
    return DraftServer(baris, jam)


def rencana_sheet(sheet: Sheet, akun_dipakai: set, draft_server: DraftServer | None = None) -> list[BarisRencana]:
    """Baca sheet + audit-nya (sama persis dgn yang dipakai jalankan.py) -> golongan per baris.
    `draft_server`: dokumen yang audit bilang belum tuntas TAPI tidak ada di ekspor draft fasih-sm
    & tidak disentuh sesudah ekspor diunduh = sudah terkirim/dihapus/dipindah (2026-09-29: 6 "draft"
    batch 22 suliyanti form-nya tidak mount, 3x error beruntun tiap putaran) -> BUKAN_DRAFT_SERVER."""
    import input_usaha.mesin as mg
    # "" di pakai_audit = "tetap" (audit sheet SEBELUMNYA) -> wajib eksplisit ke audit bawaan.
    mg.pakai_audit(sheet.audit or mg.AUDIT_BAWAAN)
    rows, hasil = mg.muat_sumber(sheet.sumber, "tahap2", True, "", True, True)
    aud = mg._baca_audit()
    mg.pastikan_audit_utuh(aud)
    status = mg.status_terakhir_dari(aud)
    dokumen = mg.dokumen_dari(aud)
    tuntas = set(mg.STATUS_TERKIRIM)
    sidik_tolak = mg.sidik_ditolak_dari(aud)
    # Jam dokumen kunci itu DIBUAT (bukan percobaan terakhir): dokumen lama yang tidak ada di
    # ekspor draft bukan draft lagi, walau bot mencoba membukanya lagi sesudah ekspor diunduh.
    terakhir: dict = {}
    for b in aud:
        if b.get("kunci") and b.get("status") == mg.STATUS_DIBUAT:
            terakhir[b["kunci"]] = max(terakhir.get(b["kunci"], ""), (b.get("timestamp") or "")[:19])

    def tuntas_fn(st, koord):
        return mg.tuntas_menurut_audit(st, tuntas, koord)

    out = []
    for r in rows:
        p = hasil[r.baris]
        gol, akun = golongkan(r.baris, r.nama_dokumen, r.kunci, p.bisa_diproses, not p.tanpa_koordinat,
                              getattr(r, "id_dokumen", "") or "", status.get(r.kunci, ""),
                              dokumen.get(r.kunci), akun_dipakai, tuntas_fn)
        if (gol == GOL_MILIK and draft_server is not None
                and (sheet.sumber, r.baris) not in draft_server.baris
                and terakhir.get(r.kunci, "") <= draft_server.jam):
            gol = GOL_BUKAN_DRAFT
        if gol == GOL_MILIK and mg.menunggu_koreksi(r, sidik_tolak):
            gol = GOL_TUNGGU     # ditolak PML, sheet belum dikoreksi (jalankan.py juga melewatinya)
        out.append(BarisRencana(sheet, r.baris, r.nama_dokumen, gol, akun, status.get(r.kunci, "")))
    return out


@dataclass
class Pekerjaan:
    sheet: Sheet
    baris: list[int]
    akun: str = ""        # "" = potongan BARU, boleh akun mana pun
    ke: int = 0           # nomor urut (utk log)

    @property
    def jenis(self) -> str:
        return "draft/milik" if self.akun else "baru"


def susun_pekerjaan(rencana: list[BarisRencana], per_potong: int) -> list[Pekerjaan]:
    """MILIK_AKUN -> satu pekerjaan per (sheet, akun); BARU -> potongan per sheet. Milik dulu."""
    milik: dict = {}
    baru: dict = {}
    for b in rencana:
        if b.golongan == GOL_MILIK:
            milik.setdefault((b.sheet, b.akun), []).append(b.baris)
        elif b.golongan == GOL_BARU:
            baru.setdefault(b.sheet, []).append(b.baris)
    kerja = [Pekerjaan(s, sorted(bb), a) for (s, a), bb in milik.items()]
    for s, bb in baru.items():
        bb = sorted(bb)
        kerja += [Pekerjaan(s, bb[i:i + per_potong]) for i in range(0, len(bb), per_potong)]
    for i, k in enumerate(kerja, 1):
        k.ke = i
    return kerja


def ringkas_baris(baris: list[int]) -> str:
    """[2,3,4,7] -> '2-4,7' (argumen --baris jalankan.py)."""
    out, mulai, akhir = [], None, None
    for b in sorted(baris):
        if mulai is None:
            mulai = akhir = b
        elif b == akhir + 1:
            akhir = b
        else:
            out.append(f"{mulai}-{akhir}" if akhir > mulai else str(mulai))
            mulai = akhir = b
    if mulai is not None:
        out.append(f"{mulai}-{akhir}" if akhir > mulai else str(mulai))
    return ",".join(out)


def cetak_rencana(rencana: list[BarisRencana], kerja: list[Pekerjaan]) -> None:
    from collections import Counter
    print("\nRENCANA PENYISIRAN")
    per_sheet: dict = {}
    for b in rencana:
        per_sheet.setdefault(b.sheet.label, Counter())[b.golongan] += 1
    kolom = [GOL_TUNTAS, GOL_MILIK, GOL_BARU, GOL_SINKRON, GOL_ID_SAJA, GOL_LUAR, GOL_BUKAN_DRAFT, GOL_TUNGGU,
             GOL_DITOLAK]
    print(f"  {'sheet':<22}" + "".join(f"{k[:14]:>15}" for k in kolom))
    for s, c in per_sheet.items():
        print(f"  {s:<22}" + "".join(f"{c.get(k, 0):>15}" for k in kolom))
    milik = Counter(b.akun for b in rencana if b.golongan == GOL_MILIK)
    if milik:
        print("\n  Draft/dokumen belum tuntas per akun pemilik:")
        for a, n in milik.most_common():
            print(f"    {a:<40} {n}")
    for gol, pesan in ((GOL_TUNGGU, "DITOLAK PML, sheet belum dikoreksi sejak ditolak (koreksi baris itu dulu)"),
                       (GOL_BUKAN_DRAFT, "audit belum tuntas tapi TIDAK ada di daftar draft server (tidak dikerjakan)"),
                       (GOL_LUAR, "milik akun di luar --akun (tidak dikerjakan)"),
                       (GOL_SINKRON, "bertanda tanpa URL — jalankan sinkron_list --tulis akun itu dulu"),
                       (GOL_ID_SAJA, "ID di sheet tapi audit tak kenal — pemilik tak diketahui")):
        daftar = [b for b in rencana if b.golongan == gol]
        if daftar:
            print(f"\n  {len(daftar)} baris {pesan}:")
            for b in daftar[:15]:
                print(f"    {b.sheet.label} baris {b.baris} {b.nama[:45]} {b.akun} {b.status}")
            if len(daftar) > 15:
                print(f"    … (lengkap di {RENCANA_CSV})")
    print(f"\n  Pekerjaan: {sum(1 for k in kerja if k.akun)} draft/milik-akun, "
          f"{sum(1 for k in kerja if not k.akun)} potongan baris baru "
          f"({sum(len(k.baris) for k in kerja)} baris).")


def tulis_rencana_csv(rencana: list[BarisRencana]) -> None:
    with lokasi.siapkan(RENCANA_CSV).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "audit", "baris", "nama_dokumen", "golongan", "akun", "status_audit"])
        for b in rencana:
            w.writerow([b.sheet.sumber, b.sheet.audit or "(bawaan)", b.baris, b.nama, b.golongan, b.akun, b.status])


# ---------------------------------------------------------------- penjadwal

@dataclass
class KeadaanAkun:
    istirahat_sampai: float = 0.0
    mati: str = ""        # alasan akun tidak dipakai lagi di run ini


@dataclass
class Penjadwal:
    """Antrean pekerjaan -> `paralel` slot; satu akun satu proses. `jalankan(pekerjaan, akun)` ->
    dict evaluasi_hasil + 'rc'. Dipisah dari subprocess supaya bisa diuji tanpa browser."""
    akun: list[str]
    jalankan: object
    paralel: int = 4
    jeda_limit: int = 1800
    jam: object = time.time
    tidur: object = time.sleep
    keadaan: dict = field(default_factory=dict)
    berhenti_total: str = ""

    def __post_init__(self):
        for a in self.akun:
            self.keadaan.setdefault(a, KeadaanAkun())

    def _bisa(self, a: str, sibuk: set) -> bool:
        k = self.keadaan[a]
        return not k.mati and a not in sibuk and k.istirahat_sampai <= self.jam()

    def putaran(self, kerja: list[Pekerjaan]) -> list[tuple[Pekerjaan, str, dict]]:
        antre = list(kerja)
        sibuk: set = set()
        hasil: list = []
        kunci = threading.Lock()
        benang: list[threading.Thread] = []

        def kerjakan(p: Pekerjaan, a: str):
            try:
                h = self.jalankan(p, a)
            except Exception as e:  # noqa: BLE001
                h = {"rc": -1, "galat": repr(e)}
            with kunci:
                sibuk.discard(a)
                hasil.append((p, a, h))
                k = self.keadaan[a]
                if h.get("audit_tidak_cocok"):
                    self.berhenti_total = f"AUDIT TIDAK COCOK ({p.sheet.sumber}, akun {a})"
                elif h.get("akun_dipakai"):
                    k.mati = "akun sedang dipakai proses lain"
                elif h.get("stop_manusia"):
                    k.mati = "STOP_WILAYAH_DOKUMEN_BEDA / STOP_SUBSLS_TIDAK_BISA_DIPILIH"
                elif h.get("rate_limited"):
                    k.istirahat_sampai = self.jam() + self.jeda_limit
                    if not p.akun:          # potongan baru: berikan ke akun lain
                        antre.append(p)

        while True:
            with kunci:
                if self.berhenti_total:
                    antre.clear()
                # pilih pekerjaan pertama yang bisa jalan sekarang
                mulai = None
                for p in list(antre):
                    if len(sibuk) >= self.paralel:
                        break
                    if p.akun:
                        if p.akun not in self.keadaan or self.keadaan[p.akun].mati:
                            antre.remove(p)      # akun mati: ditunda ke laporan
                            continue
                        if self._bisa(p.akun, sibuk):
                            mulai = (p, p.akun)
                            break
                    else:
                        bebas = [a for a in self.akun if self._bisa(a, sibuk)]
                        # akun tanpa pekerjaan milik yang masih antre didahulukan
                        punya_milik = {q.akun for q in antre if q.akun}
                        bebas.sort(key=lambda a: a in punya_milik)
                        if bebas:
                            mulai = (p, bebas[0])
                            break
                if mulai:
                    p, a = mulai
                    antre.remove(p)
                    sibuk.add(a)
                    t = threading.Thread(target=kerjakan, args=(p, a), daemon=True)
                    benang.append(t)
                    t.start()
                    continue
                tersisa = list(antre)
                lagi_jalan = bool(sibuk)
            if not tersisa and not lagi_jalan:
                break
            if tersisa and not lagi_jalan:
                # tidak ada yang jalan & tidak ada yang bisa mulai: semua istirahat/mati
                hidup = [self.keadaan[a] for a in self.akun if not self.keadaan[a].mati]
                if not hidup:
                    break
                bisa_nanti = [p for p in tersisa if not p.akun or not self.keadaan[p.akun].mati]
                if not bisa_nanti:
                    break
                tunggu = max(1.0, min(k.istirahat_sampai for k in hidup) - self.jam())
                print(f"[sisir] semua akun istirahat (limit) — tunggu {int(tunggu)} dtk")
                self.tidur(tunggu)
                continue
            self.tidur(1.0)
        for t in benang:
            t.join()
        return hasil


# ---------------------------------------------------------------- satu proses jalankan.py

_kunci_cetak = threading.Lock()


def cetak(teks: str) -> None:
    with _kunci_cetak:
        print(teks, flush=True)


def jalankan_proses(p: Pekerjaan, akun: str, subsls: str, sso: str = "") -> dict:
    cmd = [sys.executable, str(ROOT / "input_usaha" / "jalankan.py"),
           "--sumber", p.sheet.sumber,
           *(["--audit", p.sheet.audit] if p.sheet.audit else []),
           *(["--sso", sso] if sso else []),
           "--akun-tunggal", akun, "--subsls-tunggal", subsls,
           "--sinkron-dulu", "--lewati-selesai", "--izinkan-wilayah-beda", "--submit",
           "--baris", ringkas_baris(p.baris)]
    log = lokasi.siapkan(HASIL / f"log_{akun.split('@')[0]}.txt")
    cetak(f"[sisir] ▶ #{p.ke} {akun} | {p.sheet.label} | {p.jenis} {len(p.baris)} baris "
          f"({ringkas_baris(p.baris)[:60]})")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    keluaran: list[str] = []
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} #{p.ke} {p.sheet.sumber} "
                f"--baris {ringkas_baris(p.baris)} =====\n{' '.join(cmd)}\n")
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, encoding="utf-8", errors="replace")
        try:
            proc.stdin.write("YA\n")   # user sudah mengetik YA sekali utk seluruh rencana
            proc.stdin.close()
        except Exception:
            pass
        for baris in proc.stdout:
            f.write(baris)
            keluaran.append(baris)
            if re.search(r"TERKIRIM_TERVERIFIKASI|SKIP_|STOP_|ERROR_|DRAFT_TANPA_KOORDINAT|⛔", baris):
                cetak(f"    [{akun.split('@')[0]}] {baris.rstrip()[:160]}")
        proc.wait()
    h = evaluasi_hasil("".join(keluaran))
    h["rc"] = proc.returncode
    cetak(f"[sisir] ■ #{p.ke} {akun} selesai rc={proc.returncode} tuntas={h['tuntas']} sisa={h['sisa']}"
          + (" LIMIT" if h["rate_limited"] else ""))
    return h


# ---------------------------------------------------------------- main

def kelompok_audit(sheets: list[Sheet]) -> list[tuple[str, list[str]]]:
    """[(audit, [sheet, ...])] urut kemunculan — satu sinkron_list per audit (sheet se-audit digabung)."""
    grup: dict = {}
    for s in sheets:
        grup.setdefault(s.audit, []).append(s.sumber)
    return list(grup.items())


def perintah_sinkron(akun: str, subsls: str, audit: str, sumber: list[str], json_path: Path,
                     pertama: bool, sso: str = "") -> list[str]:
    """sinkron_list.py utk satu akun & satu kelompok audit. Pertama = login & baca list server lalu
    simpan JSON; berikutnya --dari-json (tanpa login; DOKUMEN_DIHAPUS tidak pernah ditulis)."""
    cmd = [sys.executable, str(ROOT / "input_usaha" / "sinkron_list.py")]
    for s in sumber:
        cmd += ["--sumber", s]
    cmd += [*(["--audit", audit] if audit else []), *(["--sso", sso] if sso and pertama else []),
            "--akun-tunggal", akun, "--subsls-tunggal", subsls,
            *(["--simpan-json", str(json_path)] if pertama else ["--dari-json", str(json_path)]), "--tulis"]
    return cmd


def sinkron_semua(akun: list[str], sheets: list[Sheet], subsls: str, paralel: int, sso: str = "",
                  jalankan=None) -> dict:
    """TAHAP 0 (2026-09-29, user: "daftar reject kan dinamis"): list server SEMUA akun dibaca lebih dulu
    (satu login per akun) lalu diterapkan ke audit tiap kelompok sheet lewat sinkron_list —
    REJECTED -> DITOLAK_PML, draft yang audit-nya terkirim -> DRAFT_DI_SERVER, dokumen buatan PC lain
    tercatat. Tanpa ini rencana disusun dari audit saja: dokumen yang ditolak PML masih tercatat
    terkirim & tidak pernah dijadwalkan. Akun yang gagal dibaca dilewati (dilaporkan). -> {akun: pesan}."""
    grup = kelompok_audit(sheets)
    kunci = threading.Lock()
    hasil: dict = {}
    jatah = threading.Semaphore(max(1, paralel))
    jalankan = jalankan or _jalankan_log

    def satu(a: str):
        with jatah:
            json_path = HASIL / f"list_{a.split('@')[0]}.json"
            ringkas = []
            for ke, (audit, sumber) in enumerate(grup):
                rc, keluaran = jalankan(perintah_sinkron(a, subsls, audit, sumber, json_path, ke == 0, sso),
                                        HASIL / f"sinkron_{a.split('@')[0]}.txt")
                m = re.search(r"Akan ditambahkan ke audit: (\d+) baris (\{.*\})", keluaran)
                ringkas.append(f"{audit or 'bawaan'}: " + (f"{m.group(1)} {m.group(2)}" if m else f"rc={rc}"))
                if rc != 0:
                    ringkas.append("GAGAL — akun ini dilewati" if ke == 0 else "gagal")
                    if ke == 0:
                        break
            with kunci:
                hasil[a] = "; ".join(ringkas)
                cetak(f"[sinkron] {a}: {hasil[a]}")

    benang = [threading.Thread(target=satu, args=(a,), daemon=True) for a in akun]
    for t in benang:
        t.start()
    for t in benang:
        t.join()
    return hasil


def _jalankan_log(cmd: list[str], log: Path) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    with lokasi.siapkan(log).open("a", encoding="utf-8") as f:
        f.write(f"\n\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n{' '.join(cmd)}\n")
        r = subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        f.write(r.stdout)
    return r.returncode, r.stdout


def buat_rencana(sheets: list[Sheet], akun: list[str], draft_server: DraftServer | None = None) -> list[BarisRencana]:
    rencana = []
    for s in sheets:
        print(f"Membaca {s.sumber} (audit {s.audit or 'bawaan'}) …")
        if Path(s.sumber).with_name("~$" + Path(s.sumber).name).exists():
            print(f"  ⚠️ {s.sumber} sedang dibuka Excel — ID dokumen baru tidak bisa ditulis ke sheet "
                  f"selama itu (audit tetap mencatat). Sebaiknya tutup Excel dulu.")
        rencana += rencana_sheet(s, set(akun), draft_server)
    return rencana


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daftar-sheet", default=str(DAFTAR_SHEET_BAWAAN),
                    help=f"TXT: satu baris '<sheet> [<audit>]' (bawaan {DAFTAR_SHEET_BAWAAN.relative_to(lokasi.AKAR)})")
    ap.add_argument("--akun", default="", help="email PPL, dipisah koma (menggantikan --daftar-akun)")
    ap.add_argument("--daftar-akun", default=str(DAFTAR_AKUN_BAWAAN),
                    help=f"TXT berisi email PPL (bawaan {DAFTAR_AKUN_BAWAAN.relative_to(lokasi.AKAR)})")
    ap.add_argument("--subsls", default=SISIR_SUBSLS,
                    help="subsls wadah 16 digit, sama utk semua akun (bawaan SISIR_SUBSLS di config_lokal)")
    ap.add_argument("--paralel", type=int, default=4, help="proses sekaligus (bawaan 4, ±1,5 GB RAM per bot)")
    ap.add_argument("--per-potong", type=int, default=40, help="baris BARU per pekerjaan (bawaan 40)")
    ap.add_argument("--jeda-limit", type=int, default=1800, help="detik istirahat akun yang kena limit")
    ap.add_argument("--maks-putaran", type=int, default=3)
    ap.add_argument("--daftar-draft", default="",
                    help="ekspor tabel Data fasih-sm (.xlsx) status draft/rejected: diterapkan ke audit (dgn "
                         "--submit), lalu draft di audit yang tidak ada di sana dilewati")
    ap.add_argument("--tanpa-sinkron", action="store_true",
                    help="lewati TAHAP 0 (baca list server semua akun -> audit). Bawaan: jalan dgn --submit")
    ap.add_argument("--sinkron", action="store_true", help="jalankan TAHAP 0 juga tanpa --submit (menulis audit)")
    ap.add_argument("--sso", choices=("otomatis", "eksternal", "pegawai"), default="")
    ap.add_argument("--submit", action="store_true", help="LIVE (kirim). Tanpa ini hanya rencana.")
    args = ap.parse_args()
    lokasi.cek_struktur_lama()

    if args.akun:
        akun = baca_akun(args.akun)
    elif Path(args.daftar_akun).exists():
        akun = baca_akun(Path(args.daftar_akun).read_text(encoding="utf-8-sig"))
    else:
        akun = []
    if not akun:
        ap.error(f"isi --akun, atau buat {args.daftar_akun} (satu email PPL per baris)")
    if not re.fullmatch(r"\d{16}", args.subsls):
        ap.error("--subsls harus 16 digit (atau isi SISIR_SUBSLS di inti/config_lokal.py)")
    sheets = baca_daftar_sheet(args.daftar_sheet)
    print(f"Akun ({len(akun)}): {', '.join(akun)}\nSheet: {', '.join(s.label for s in sheets)}")

    # --submit: tanda DRAFT_DI_SERVER / DITOLAK_PML langsung ditulis (bukan pengiriman; aman walau YA
    # dibatalkan — baris itu hanya jadi dikerjakan lagi). Tanpa --submit: laporan saja.
    if (args.submit or args.sinkron) and not args.tanpa_sinkron:
        print(f"\n--- TAHAP 0: baca list server {len(akun)} akun -> audit (draft, REJECTED, dokumen PC lain) ---")
        sinkron_semua(akun, sheets, args.subsls, args.paralel, args.sso)
    draft_server = muat_draft_server(args.daftar_draft, sheets, tulis=args.submit) if args.daftar_draft else None
    rencana = buat_rencana(sheets, akun, draft_server)
    tulis_rencana_csv(rencana)
    kerja = susun_pekerjaan(rencana, args.per_potong)
    cetak_rencana(rencana, kerja)
    print(f"\nRencana lengkap: {RENCANA_CSV}")
    if not args.submit:
        print("\n(Tanpa --submit: hanya rencana, tidak ada yang dijalankan.)")
        return 0
    if not kerja:
        print("\nTidak ada yang perlu dikerjakan.")
        return 0

    print(f"\n⚠️ MODE LIVE — {sum(len(k.baris) for k in kerja)} baris akan diisi & DIKIRIM oleh "
          f"{min(args.paralel, len(akun))} bot paralel. Pastikan audit semua PC sudah digabung & "
          f"PC lain berhenti.")
    if input("Ketik 'YA' utk menjalankan seluruh rencana: ").strip() != "YA":
        print("Dibatalkan.")
        return 1

    penjadwal = Penjadwal(akun, lambda p, a: jalankan_proses(p, a, args.subsls, args.sso),
                          paralel=args.paralel, jeda_limit=args.jeda_limit)
    sisa_lalu = None
    for ke in range(1, args.maks_putaran + 1):
        print(f"\n{'=' * 70}\nPUTARAN {ke}: {len(kerja)} pekerjaan\n{'=' * 70}")
        penjadwal.putaran(kerja)
        if penjadwal.berhenti_total:
            print(f"\n⛔ Penyisiran dihentikan: {penjadwal.berhenti_total}")
            return 5
        rencana = buat_rencana(sheets, akun, draft_server)
        tulis_rencana_csv(rencana)
        kerja = susun_pekerjaan(rencana, args.per_potong)
        sisa = sorted((b.sheet.sumber, b.baris) for b in rencana if b.golongan in DIKERJAKAN)
        print(f"\nSesudah putaran {ke}: {len(sisa)} baris masih tersisa.")
        if not sisa or sisa == sisa_lalu:
            break
        sisa_lalu = sisa
    cetak_rencana(rencana, kerja)
    mati = {a: k.mati for a, k in penjadwal.keadaan.items() if k.mati}
    for a, alasan in mati.items():
        print(f"  ⛔ akun {a} dihentikan: {alasan}")
    print(f"\nLog per akun: {HASIL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
