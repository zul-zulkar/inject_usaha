#!/usr/bin/env python3
"""
mesin.py — MESIN input usaha ke fasih-web (dulu input_gabungan/main_gabungan.py).

Jangan dijalankan langsung: pintu masuknya `input_usaha/jalankan.py` (format input
usaha = format tahap 2) dan `input_usaha/otomatis.py` (jalankan ulang otomatis).
Tutorial & daftar flag: input_usaha/README.md.

Isi modul ini: baca & periksa sheet (muat_sumber), audit (append_audit, kunci proses
per akun), lalu per baris process_one_row(): buat/buka dokumen -> PENGANTAR ->
SE2026-P -> BLOK II (isi_blok2.py) -> ringkasan GALAT -> kirim (hanya --submit + "YA").

⚠️ VPN kantor wajib aktif. ⚠️ Headless dilarang (fasih-web membalas dgn halaman anti-bot).

MODE SATU SUBSLS + SATU AKUN (bawaan): semua dokumen dibuat di SATU subsls oleh SATU
akun PPL; wilayah asli baris dicatat di kolom `idsubsls` audit utk pindah wilayah
nanti (fasih_sm/pindah_wilayah). Yang DICEK LANGSUNG saat input:
  - akun yang login WAJIB terverifikasi = akun tunggal, kalau tidak batch berhenti;
  - subsls tidak bisa dipilih / "+Dokumen Baru" tidak ada -> batch BERHENTI;
  - wilayah BLOK I dokumen beda dgn subsls tujuan -> BERHENTI; tidak terbaca -> diisi
    tapi TIDAK dikirim.

Audit bawaan: audit/audit_log_gabungan.csv (inti/lokasi.py). Keluaran lain
(cek_input.csv, dokumen_tanpa_url.csv, screenshot, kunci proses) di input_usaha/hasil/.
Baris yang gagal pemeriksaan offline TIDAK pernah dibuka di browser.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import datetime
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright

# -- jalankan dari root proyek; sisipkan root ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import (
    ASSIGNMENT_ID_GABUNGAN, FIXED_PASSWORD, GABUNGAN_AKUN_TUNGGAL, GABUNGAN_BARIS_PER_SESI,
    GABUNGAN_MODE_MURNI, GABUNGAN_SUBSLS_TUNGGAL, GALAT_13C_JADI, KODE_KAB, WILAYAH_BY_IDSUBSLS,
)
from inti import fasih_web as _fasih_web, lokasi
from inti.fasih_web import DokumenNamaLamaAda, FasihWebSession, FieldNotFound
from input_usaha.isi_blok2 import (
    BarisPerluManual, fill_blok2_gabungan, fill_catatan, fill_keterangan_pemberi_jawaban,
)
from inti.gabungan_loader import (
    STATUS_SIAP_TANPA_KOORDINAT, GabunganRow, Pemeriksaan, cocokkan_wilayah_dokumen,
    idsubsls_dari_wilayah, kelompok_per_akun,
    load_gabungan, parse_pilihan_baris, periksa_semua,
)
from inti.tahap2_loader import load_tahap2, periksa_semua_tahap2
from inti.id_dokumen import PencatatIdSumber, baca_kolom_id, pasang_id, url_entry

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

AUDIT_BAWAAN = lokasi.AUDIT_BAWAAN
# Lokasi audit boleh diganti (permintaan user 2026-09-24: batch baru dgn audit kosong &
# sumber data baru): `--audit <berkas atau folder>` per perintah, atau variabel
# lingkungan FASIH_AUDIT utk semua alat di satu jendela terminal. SEMUA alat membaca
# `mg.AUDIT_LOG_PATH` saat dipakai (bukan salinan saat impor) — pertahankan begitu.
AUDIT_LOG_PATH = lokasi.audit_dari_lingkungan()
# idsubsls = wilayah ASLI baris (tujuan ubah alokasi nanti); idsubsls_input =
# subsls tempat dokumen benar-benar dibuat; akun_login = akun yang membuatnya.
AUDIT_FIELDS = [
    "timestamp", "baris", "kunci", "nama_usaha", "kbli", "idsubsls", "idsubsls_input", "akun_ppl",
    "akun_login", "status", "galat", "peringatan", "kosong", "catatan_count", "review_disarankan",
    "wilayah_dokumen", "dokumen_url", "error_message",
]
CEK_PATH = lokasi.HASIL_INPUT / "cek_input.csv"
# Daftar baris yang dokumennya mungkin terbuat tanpa URL — ditulis ulang tiap run
# supaya bisa dibaca pagi hari tanpa menyisir audit (lihat STATUS_TANPA_URL).
LAPORAN_TANPA_URL_PATH = lokasi.HASIL_INPUT / "dokumen_tanpa_url.csv"
MENIT_PER_BARIS = 1.7  # ukuran nyata batch backlog lama, termasuk ganti akun

# Dokumen yang ternyata sudah terkunci (dikirim di luar skrip) ikut dianggap
# tuntas oleh --lewati-selesai: mengisinya ulang pasti gagal.
STATUS_TERKUNCI = "DOKUMEN_TERKUNCI"
STATUS_TERKIRIM = {"TERKIRIM_TERVERIFIKASI", "TERKIRIM_BELUM_TERVERIFIKASI", STATUS_TERKUNCI}
STATUS_SELESAI_DRY_RUN = STATUS_TERKIRIM | {"DRY_RUN_SIAP_KIRIM"}
# Ditulis SEGERA setelah dokumen baru terbuat (sebelum diisi), supaya proses
# yang mati di tengah tidak berujung dokumen duplikat pada run berikutnya.
STATUS_DIBUAT = "DOKUMEN_DIBUAT"
# Baris tanpa koordinat (--koordinat otomatis): dokumen diisi lengkap KECUALI
# geotag lalu DITAHAN sbg DRAFT — juga saat --submit. Validasi form TIDAK
# menahannya (geotag hanya wajib utk mode CAPI, file-validation 2026-09-22), jadi
# penahannya skrip ini. Begitu koordinat diisi di sheet, run berikutnya membuka
# dokumen yang sama lewat URL audit, mengisi geotag, lalu mengirim.
STATUS_DRAFT_TANPA_KOORDINAT = "DRAFT_TANPA_KOORDINAT"
# Draft yang oleh SERVER ditandai bergalat (sumError > 0 = kartu "Jumlah Error"
# di halaman PENDATAAN), ditulis sinkron_list/--sinkron-dulu. Bukan status tuntas,
# dan baris bertanda ini DIDAHULUKAN saat batch jalan.
STATUS_DRAFT_GALAT = "DRAFT_GALAT_DI_SERVER"
# Dokumen tercatat sudah DIHAPUS admin (dibuktikan list API, lihat sinkron_list.py):
# catatan dokumen kunci itu sebelum baris ini gugur -> baris dibuatkan dokumen baru.
STATUS_DIHAPUS = "DOKUMEN_DIHAPUS"
# Dokumen kemungkinan TERBUAT tapi URL-nya tidak tertangkap (toast "berhasil
# dibuat" muncul sebelum navigasi ke /entry). Dulu `STOP_DOKUMEN_TANPA_URL` &
# menghentikan batch; sejak 2026-09-23 (permintaan user: run malam tidak boleh
# berhenti) baris itu DILEWATI, batch LANJUT, dan semuanya didaftar di akhir run
# + LAPORAN_TANPA_URL_PATH. Pengaman duplikatnya dipindah ke audit: kunci
# bertanda ini dihitung SUDAH punya dokumen (dokumen_dari) sehingga dokumen kedua
# tidak pernah dibuat, dan barisnya dilewati sampai ada bukti URL (sinkron_list).
STATUS_TANPA_URL = "DOKUMEN_TANPA_URL_PERLU_CEK"
# Nama lama masih ada di audit yang sudah tertulis -> diperlakukan sama.
STATUS_TANPA_URL_SEMUA = frozenset({STATUS_TANPA_URL, "STOP_DOKUMEN_TANPA_URL"})
TANDA_LEWATI_TANPA_URL = "LEWATI_TANPA_URL"
# Kejanggalan yang pasti berulang di baris berikutnya -> hentikan batch.
# SUBMIT_GAGAL ikut: jalur kirim yang tidak bekerja (run 2026-09-14 baris 4)
# pasti berulang di semua baris & tidak boleh lolos diam-diam.
STATUS_BERHENTI_SEGERA = {"STOP_SUBSLS_TIDAK_BISA_DIPILIH", "STOP_WILAYAH_DOKUMEN_BEDA", "SUBMIT_GAGAL"}
# Kegagalan yang terbukti transien per SESI (server "lelah" setelah beberapa kiriman):
# mode satu akun login ulang & mengulang baris itu SEKALI sebelum status di atas
# menghentikan batch.
STATUS_ULANG_SESI_BARU = {"SUBMIT_GAGAL", "SKIP_DOKUMEN_BELUM_ADA", "ERROR_FIELD_NOT_FOUND"}


def _pastikan_header_audit():
    """Audit lama (sebelum kolom idsubsls_input/dokumen_url dst.) ditulis
    ulang dgn header baru, supaya DictWriter tidak menggeser kolom."""
    if not AUDIT_LOG_PATH.exists():
        return
    with AUDIT_LOG_PATH.open(newline="", encoding="utf-8") as f:
        pembaca = csv_module.DictReader(f)
        if pembaca.fieldnames == AUDIT_FIELDS:
            return
        lama = list(pembaca)
    with AUDIT_LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv_module.DictWriter(f, fieldnames=AUDIT_FIELDS)
        w.writeheader()
        for b in lama:
            w.writerow({k: b.get(k, "") for k in AUDIT_FIELDS})


class _KunciAudit:
    """Kunci antar-PROSES (file .lock, O_EXCL) supaya beberapa batch paralel tidak
    menulis audit bersamaan. Kunci basi (> 60 dtk, proses mati) dibuang."""

    def __enter__(self):
        self.path = AUDIT_LOG_PATH.with_name(AUDIT_LOG_PATH.name + ".lock")
        batas = time.time() + 60
        while True:
            try:
                self.fd = _os.open(str(self.path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 60:
                        self.path.unlink()
                        continue
                except OSError:
                    pass
                if time.time() > batas:
                    raise RuntimeError(f"Audit terkunci > 60 dtk: {self.path}")
                time.sleep(0.1)

    def __exit__(self, *exc):
        _os.close(self.fd)
        try:
            self.path.unlink()
        except OSError:
            pass


def _pid_hidup(pid: int) -> bool:
    """Proses `pid` masih berjalan? (os.kill(pid, 0) di Windows justru MEMBUNUH
    proses, jadi pakai OpenProcess/GetExitCodeProcess.)"""
    if pid <= 0:
        return False
    if _os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            kode = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(kode))) and kode.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        _os.kill(pid, 0)
        return True
    except OSError:
        return False


def kunci_proses_akun(akun: str) -> Path | None:
    """Klaim akun ini utk proses sekarang. None = sudah dipakai proses lain yang MASIH hidup.
    Run 2026-09-14: dua proses (Agenda.xlsx & Agenda1-1.xlsx) memakai akun ppl.kedua
    bersamaan -> logout proses satu memutus sesi proses lain (halaman login di tengah
    'Buat Dokumen') & jumlah dokumen yang dinaikkan proses lain memicu
    DOKUMEN_TANPA_URL_PERLU_CEK palsu. Paralel = akun BERBEDA per proses."""
    path = lokasi.siapkan(lokasi.HASIL_INPUT / (".proses_" + re.sub(r"[^a-z0-9]+", "_", akun.lower()) + ".lock"))
    for _ in range(2):
        try:
            fd = _os.open(str(path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="utf-8").split()[0])
            except (OSError, ValueError, IndexError):
                pid = 0
            if pid != _os.getpid() and _pid_hidup(pid):
                return None
            try:
                path.unlink()  # basi: prosesnya sudah mati
            except OSError:
                pass
            continue
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{_os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv)}\n")
        return path
    return None


def append_audit(row: dict):
    with _KunciAudit():
        _pastikan_header_audit()
        is_new = not AUDIT_LOG_PATH.exists()
        # Audit yang disunting tangan bisa berakhir TANPA newline (2026-09-25: baris
        # DOKUMEN_DIBUAT tertempel di belakang baris ",,,,," -> kolomnya bergeser 17 &
        # dokumennya tidak dikenali audit). Tutup dulu baris terakhir itu.
        if not is_new:
            with AUDIT_LOG_PATH.open("rb") as f:
                f.seek(0, _os.SEEK_END)
                if f.tell():
                    f.seek(-1, _os.SEEK_END)
                    tanpa_newline = f.read(1) not in (b"\n", b"\r")
                else:
                    tanpa_newline = False
            if tanpa_newline:
                with AUDIT_LOG_PATH.open("ab") as f:
                    f.write(b"\r\n")
        with AUDIT_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
            w = csv_module.DictWriter(f, fieldnames=AUDIT_FIELDS)
            if is_new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in AUDIT_FIELDS})


def dokumen_lain_dibuat_sejak(sejak_epoch: float, kunci_sendiri: str, akun: str = "") -> int:
    """Jumlah DOKUMEN_DIBUAT milik baris LAIN yang tercatat setelah `sejak_epoch`.
    Batch paralel ikut menaikkan jumlah dokumen di list; kenaikan yang terjelaskan
    oleh catatan ini bukan dokumen yatim. Timestamp baris DOKUMEN_DIBUAT = saat
    dibuat (lihat process_one_row). `akun` diisi -> hanya dokumen akun itu: list
    PENDATAAN per akun, jadi dokumen akun LAIN tidak boleh "menjelaskan" kenaikan
    (kalau dihitung, dokumen yatim sungguhan bisa tertutupi -> dibuat lagi = duplikat)."""
    n = 0
    for b in _baca_audit():
        if b.get("status") != STATUS_DIBUAT or b.get("kunci") == kunci_sendiri:
            continue
        if akun and (b.get("akun_login") or "").lower() != akun.lower():
            continue
        try:
            if time.mktime(time.strptime(b["timestamp"], "%Y-%m-%d %H:%M:%S")) > sejak_epoch:
                n += 1
        except (KeyError, ValueError):
            pass
    return n


def kenaikan_tak_terjelaskan(n_awal: int, n_akhir: int, waktu_awal: float, kunci: str, akun: str = "") -> int:
    """(kenaikan jumlah dokumen) - (dokumen yang dibuat baris lain di akun yang sama sejak itu).
    > 0 = kemungkinan ada dokumen yatim. Margin 5 dtk sengaja membuat kasus di
    batas waktu jatuh ke arah BERHENTI, bukan ke arah membuat dokumen lagi."""
    return (n_akhir - n_awal) - dokumen_lain_dibuat_sejak(waktu_awal + 5, kunci, akun)


def _baca_audit() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    with AUDIT_LOG_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv_module.DictReader(f))


def pakai_audit(path: str | Path | None = "") -> Path:
    """Tetapkan lokasi audit (`--audit`). Folder (sudah ada, diakhiri garis miring, atau tanpa
    akhiran .csv) -> <folder>/audit_log_gabungan.csv. Folder induknya dibuat kalau belum ada.
    "" = tetap (bawaan / FASIH_AUDIT)."""
    global AUDIT_LOG_PATH
    teks = str(path or "").strip()
    if teks:
        p = Path(teks)
        if p.is_dir() or teks.endswith(("/", "\\")) or not p.suffix:
            p = p / AUDIT_BAWAAN.name
        if p.suffix.lower() != ".csv":
            raise SystemExit(f"❌ --audit {teks}: harus berkas .csv (atau folder)")
        p.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_LOG_PATH = p
    return AUDIT_LOG_PATH


def opsi_audit(ap) -> None:
    """Tambahkan `--audit` ke parser alat mana pun (satu teks bantuan utk semua)."""
    ap.add_argument("--audit", default="", metavar="BERKAS",
                    help=f"berkas audit (default {AUDIT_LOG_PATH}; folder -> <folder>/{AUDIT_BAWAAN.name}; "
                         "juga lewat variabel lingkungan FASIH_AUDIT)")


# Awal pesan kedua pengaman audit di bawah; dikenali otomatis.py (berhenti, tidak diulang).
PENANDA_AUDIT_TIDAK_COCOK = "⛔ AUDIT TIDAK COCOK"


def audit_lain_yang_mengenal(rows) -> tuple[int, list[tuple[Path, int]]]:
    """Apakah audit aktif SALAH utk sheet ini? -> (jumlah kunci baris yang dikenal audit aktif,
    [(audit lain, jumlah dikenal)] yang jauh lebih mengenal sheet ini; terbanyak dulu).
    Daftar kosong = aman.

    "Jauh lebih mengenal": audit aktif tidak mengenal satu pun baris padahal audit lain mengenal,
    atau audit lain mengenal >= 20 baris DAN >= 5x lipat audit aktif. Kebetulan satu-dua baris
    kembar antar-sheet (nyata: batch 21 & 22 berbagi 1 baris) tidak boleh menutupi kesalahan.
    Pengaman struktur folder 2026-09-25: audit bawaan pindah dari akar proyek ke audit/, dan
    batch lama (mis. audit/batch21) harus dijalankan dgn --audit-nya sendiri. Lupa --audit =
    semua baris dianggap belum punya dokumen = dokumen GANDA."""
    kunci = {r.kunci for r in rows if getattr(r, "kunci", "")}
    if not kunci:
        return 0, []
    n_aktif = len({b.get("kunci") for b in _baca_audit()} & kunci)
    aktif = AUDIT_LOG_PATH.resolve()
    temuan = []
    for f in lokasi.cari(lokasi.AUDIT / "**" / "audit_log_gabungan*.csv"):
        if f.resolve() == aktif:
            continue
        try:
            with f.open(newline="", encoding="utf-8-sig") as fh:
                n = len({b.get("kunci") for b in csv_module.DictReader(fh)} & kunci)
        except (OSError, UnicodeDecodeError, csv_module.Error):
            continue
        if n and (n_aktif == 0 or (n >= 20 and n >= 5 * n_aktif)):
            temuan.append((f, n))
    return n_aktif, sorted(temuan, key=lambda t: -t[1])


def id_sheet_belum_digabung(rows) -> tuple[list[int], list[tuple[Path, int]]]:
    """Kolom "ID Dokumen FASIH" sheet mengenal dokumen yang TIDAK dikenal audit aktif tapi dikenal
    audit lain di audit/** -> ([nomor baris], [(audit lain, jumlah ID itu yang dikenalnya)]).
    Daftar kedua kosong = aman (ID asing yang tak dikenal audit mana pun tetap dibuka lewat ID).

    Kejadian 2026-09-26: sheet hasil gabung_id_sumber sudah dipasang di bahan/, audit gabungannya
    belum (tertinggal di audit/pc/hasil). Baris milik PC lain dibuka lewat ID sheet dgn akun run
    ini, padahal dokumennya milik akun lain -> form tidak mount -> ERROR_FIELD_NOT_FOUND + login
    ulang di SETIAP baris (369 baris). Audit aktif yang benar mengenal ID itu -> barisnya dilewati."""
    per_id: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if getattr(r, "id_dokumen", ""):
            per_id[r.id_dokumen].append(r.baris)
    asing = set(per_id) - id_dokumen_tercatat()
    if not asing:
        return [], []
    aktif = AUDIT_LOG_PATH.resolve()
    temuan = []
    for f in lokasi.cari(lokasi.AUDIT / "**" / "audit_log_gabungan*.csv"):
        if f.resolve() == aktif:
            continue
        try:
            with f.open(newline="", encoding="utf-8-sig") as fh:
                n = len(id_dokumen_tercatat(list(csv_module.DictReader(fh))) & asing)
        except (OSError, UnicodeDecodeError, csv_module.Error):
            continue
        if n:
            temuan.append((f, n))
    return sorted(b for i in asing for b in per_id[i]), sorted(temuan, key=lambda t: -t[1])


def cetak_lokasi_audit() -> None:
    """Satu baris di awal run supaya selalu jelas audit mana yang dipakai."""
    ada = AUDIT_LOG_PATH.exists()
    n = len(_baca_audit()) if ada else 0
    print(f"Audit: {AUDIT_LOG_PATH.resolve()} ({n} baris)" if ada else
          f"Audit: {AUDIT_LOG_PATH.resolve()} (BARU — belum ada isinya)")
    if not n and AUDIT_LOG_PATH.resolve() != AUDIT_BAWAAN.resolve() and AUDIT_BAWAAN.exists():
        print(f"  ⚠️  Audit ini kosong, padahal {AUDIT_BAWAAN.name} di folder ini berisi. Dokumen yang tercatat di "
              "sana TIDAK dikenali — pencegah ganda tinggal --sinkron-dulu (akun ini saja, nama persis).")


_POLA_KUNCI_AUDIT = re.compile(r"[0-9a-f]{10}")
_POLA_ANGKA_ILMIAH = re.compile(r"-?\d+(?:[.,]\d+)?E[+-]\d+", re.I)
_POLA_WAKTU_EXCEL = re.compile(r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}(?::\d{2})?")


def kerusakan_excel(baris: list[dict]) -> Counter:
    """{kolom: jumlah baris} yang rusak krn audit pernah DISIMPAN ULANG oleh Excel
    (2026-09-24: kunci "1404364e03" -> "1.40E+09", idsubsls -> "5.10806E+15",
    timestamp -> "9/23/2026 18:05"). Kunci rusak = baris itu tidak lagi dikenali
    -> SKIP_NAMA_DIPAKAI_BARIS_LAIN / dokumen dibuat ulang; idsubsls_input rusak =
    dokumen dianggap milik subsls lain. Kosong = utuh."""
    c: Counter = Counter()
    for b in baris:
        k = b.get("kunci") or ""
        if k and not _POLA_KUNCI_AUDIT.fullmatch(k):
            c["kunci"] += 1
        for kol in ("idsubsls", "idsubsls_input"):
            if _POLA_ANGKA_ILMIAH.fullmatch(b.get(kol) or ""):
                c[kol] += 1
        if _POLA_WAKTU_EXCEL.fullmatch(b.get("timestamp") or ""):
            c["timestamp"] += 1
    return c


def pesan_audit_rusak(rusak: Counter, berkas) -> str:
    rinci = ", ".join(f"{k} {n}" for k, n in rusak.most_common())
    return (f"{berkas} RUSAK krn pernah disimpan Excel ({rinci} baris). Jangan dipakai — "
            f"kunci/idsubsls yang rusak membuat baris tidak dikenali (nama dianggap milik baris lain, "
            f"dokumen bisa dibuat GANDA). Pulihkan dulu:\n"
            f"    python antar_pc/pulihkan_excel.py            (lihat rencananya)\n"
            f"    python antar_pc/pulihkan_excel.py --tulis\n"
            f"Lain kali buka audit hanya utk DIBACA (tutup tanpa Save), atau pakai rangkum_audit.csv.")


def pastikan_audit_utuh(baris: list[dict] | None = None, berkas=None) -> None:
    """Hentikan program (SystemExit) kalau audit rusak Excel — dipanggil SEKALI di awal
    tiap alat yang memakai audit, sebelum apa pun ditulis."""
    rusak = kerusakan_excel(_baca_audit() if baris is None else baris)
    if rusak:
        raise SystemExit("❌ " + pesan_audit_rusak(rusak, berkas or AUDIT_LOG_PATH))


def status_terakhir_per_kunci() -> dict:
    return status_terakhir_dari(_baca_audit())


def tanda_tanpa_url_terakhir(kunci: str, baris: list[dict] | None = None) -> dict:
    """Baris audit TERAKHIR yang menandai kunci ini "dokumen tanpa URL" ({} kalau
    tidak ada). Dipakai laporan akhir run supaya yang tercetak adalah WAKTU
    kejadian aslinya — itu yang dipakai mencari dokumen DRAFT kosong di list."""
    ketemu: dict = {}
    for b in (baris if baris is not None else _baca_audit()):
        if b.get("kunci") == kunci and (b.get("status") or "").strip() in STATUS_TANPA_URL_SEMUA:
            ketemu = b
    return ketemu


def status_terakhir_dari(baris: list[dict]) -> dict:
    """{kunci: status}, baris TERAKHIR yang menang. Pakai kunci, BUKAN nomor baris
    — nomor baris bergeser kalau sheet diurutkan/disisipi. Menerima daftar baris
    (bukan langsung file) supaya gabung_audit/ memakai aturan yang SAMA PERSIS.

    Pengecualian: DOKUMEN_DIBUAT utk dokumen yang SAMA (URL sama, atau tanpa URL)
    TIDAK menimpa status yang sudah ada. Temuan 2026-09-24 (audit gabungan semua
    PC): sinkron_list di PC lain menulis DOKUMEN_DIBUAT ("dibuat di luar audit
    ini") utk 147 dokumen yang di PC pembuatnya sudah DRAFT_TANPA_KOORDINAT;
    setelah digabung baris sinkron itu jatuh paling belakang -> status turun jadi
    DOKUMEN_DIBUAT -> tiap run mengisi ulang dokumen yang sama. DOKUMEN_DIBUAT
    dgn URL BARU (dokumen lain) tetap menang."""
    out: dict = {}
    url_kunci: dict = {}
    for b in baris:
        kunci = b.get("kunci")
        if not kunci:
            continue
        status = (b.get("status") or "").strip()
        url = _id_dokumen(b.get("dokumen_url") or "")
        if (status == STATUS_DIBUAT and out.get(kunci) not in (None, "", STATUS_DIBUAT, STATUS_DIHAPUS)
                and (not url or url == url_kunci.get(kunci))):
            continue
        out[kunci] = status
        if url:
            url_kunci[kunci] = url
    return out


def _id_dokumen(url: str) -> str:
    """Segmen id dokumen dari URL entry (…/<id>/entry); URL lain apa adanya."""
    bagian = [p for p in url.strip().split("/") if p]
    if len(bagian) >= 2 and bagian[-1] == "entry":
        return bagian[-2]
    return url.strip()


def dokumen_per_kunci() -> dict:
    return dokumen_dari(_baca_audit())


def dokumen_dari(baris: list[dict]) -> dict:
    """{kunci: (akun_login, idsubsls_input, dokumen_url)} utk baris yang
    dokumennya PERNAH dibuat/dibuka (URL bisa "" kalau terbuat tanpa URL
    tertangkap). Dipakai membuka dokumen lewat URL (list satu akun berhalaman
    ratusan dokumen) & mencegah dokumen kedua dibuat utk baris yang sama."""
    out: dict = {}
    for b in baris:
        kunci, url = b.get("kunci"), b.get("dokumen_url") or ""
        if kunci and b.get("status") == STATUS_DIHAPUS:
            out.pop(kunci, None)  # dokumen lama sudah tidak ada -> boleh dibuat baru
            continue
        # Status "tanpa URL" ikut mendaftarkan kunci walau URL-nya "" — dokumennya
        # kemungkinan besar ADA di server, jadi jangan sampai dibuatkan yang kedua.
        if not kunci or not (url or b.get("status") in ({STATUS_DIBUAT} | set(STATUS_TANPA_URL_SEMUA))):
            continue
        lama = out.get(kunci)
        out[kunci] = ((b.get("akun_login") or "").lower(), b.get("idsubsls_input") or "",
                      url or (lama[2] if lama else ""))
    return out


def kunci_lain_bernama_sama(nama_dokumen: str, kunci: str, akun: str = "", audit: list | None = None) -> str:
    """Kunci baris LAIN yang dokumennya (akun `akun` kalau diisi) tercatat dgn nama dokumen
    yang sama persis, "" kalau tidak ada. Run 2026-09-15: Agenda2 baris 267 &
    Agenda baris 108 = dua usaha BERBEDA bernama "PANGKALAN GAS (NYOMAN SHUARJANA)".
    create_document mencari nama di list -> akan membuka dokumen baris 108 (terkirim)
    & baris 267 salah dianggap tuntas (DOKUMEN_TERKUNCI)."""
    n = " ".join((nama_dokumen or "").split()).upper()
    baris = _baca_audit() if audit is None else audit
    milik = dokumen_dari(baris)
    for b in baris:
        k = b.get("kunci")
        if (k and k != kunci and k in milik and (not akun or milik[k][0] == akun.lower())
                and " ".join((b.get("nama_usaha") or "").split()).upper() == n):
            return k
    return ""


def alasan_lewati_saat_giliran(kunci: str, target: tuple[str, str], tuntas: set, nama_dokumen: str = "",
                               punya_koordinat: bool = True, audit: list | None = None,
                               id_sheet: str = "") -> str:
    """Audit dibaca ULANG tepat sebelum baris dikerjakan (daftar awal dihitung saat
    start). Batch lain (akun lain) bisa sudah membuat/mengirim dokumen baris ini
    selama batch ini berjalan -> membuatnya lagi di sini = duplikat. "" = kerjakan.

    `audit` = daftar baris audit yang sudah dibaca (alat laporan offline
    memakainya supaya tidak membaca ulang berkas utk SETIAP baris); saat batch
    jalan ia SELALU None supaya tulisan proses lain ikut terbaca."""
    baris_audit_ = _baca_audit() if audit is None else audit
    tercatat = dokumen_dari(baris_audit_).get(kunci)
    if tercatat and tercatat[:2] != target:
        return f"dokumennya sudah dibuat proses lain ({tercatat[0]} / {tercatat[1]})"
    if status_terakhir_dari(baris_audit_).get(kunci, "") in STATUS_TANPA_URL_SEMUA:
        # Dokumennya kemungkinan ada di server tanpa URL tercatat. Mengerjakannya
        # lagi = dokumen kedua; dibuka lewat URL juga tidak bisa. Buktikan dulu
        # lewat sinkron_list (nama ketemu di list -> DOKUMEN_DIBUAT + URL ditulis,
        # tidak ketemu -> hapus baris tanda ini dari audit), baru dikerjakan lagi.
        return (f"{TANDA_LEWATI_TANPA_URL}: dokumen tanpa URL tercatat — "
                f"jalankan sinkron_list.py --tulis dulu (lihat {LAPORAN_TANPA_URL_PATH})")
    if tuntas and tuntas_menurut_audit(status_terakhir_dari(baris_audit_).get(kunci, ""),
                                       tuntas, punya_koordinat):
        return "sudah selesai di audit (dikerjakan proses lain)"
    if nama_dokumen and not tercatat and not id_sheet:
        # Ber-ID di sheet: dokumennya dibuka lewat ID, tidak dicari lewat nama.
        lain = kunci_lain_bernama_sama(nama_dokumen, kunci, target[0], baris_audit_)
        if lain:
            return (f"SKIP_NAMA_DIPAKAI_BARIS_LAIN: '{nama_dokumen}' sudah jadi nama dokumen baris lain "
                    f"(kunci {lain}) di list akun ini — bedakan nama di sheet (atau KOREKSI_NAMA)")
    return ""


def kenapa_tidak_dikerjakan(rows, hasil: dict, tuntas: set, target_fn, audit: list,
                           satu_subsls: bool = True) -> list[tuple]:
    """[(nomor baris, alasan)] utk SETIAP baris; alasan "" = akan dikerjakan.

    SATU sumber kebenaran: dipakai pesan "Tidak ada baris yang perlu diproses"
    di main() DAN laporan input_usaha/rangkum_audit.py, supaya keduanya tidak
    pernah berbeda jawaban. Urutan pemeriksaannya sama dgn saat batch jalan:
    pemeriksaan data offline dulu, baru pemeriksaan giliran."""
    keluar = []
    for r in rows:
        cek = hasil.get(r.baris)
        if cek is not None and not cek.bisa_diproses:
            keluar.append((r.baris, f"{cek.status}: {cek.pesan[:150]}"))
            continue
        keluar.append((r.baris, alasan_lewati_saat_giliran(
            r.kunci, target_fn(r), tuntas, r.nama_dokumen if satu_subsls else "",
            r.punya_koordinat, audit=audit, id_sheet=getattr(r, "id_dokumen", ""))))
    return keluar


def berkas_stop(akun: str) -> str:
    """Nama file penghenti yang ada ("" = tidak ada). `STOP_GABUNGAN` menghentikan
    semua batch; `STOP_<akun>` hanya batch akun itu. Dicek di ANTARA baris, jadi
    tidak pernah memotong pengisian/kirim."""
    for nama in ("STOP_GABUNGAN", f"STOP_{akun}" if akun else ""):
        if nama and Path(nama).exists():
            return nama
    return ""


def coba_13c_alternatif(sess, galat_lama: int, tanda: list):
    """GALAT yang belum teratasi -> COBA ganti 13c jadi `GALAT_13C_JADI`
    (permintaan user 2026-09-23: "pokoknya ganti saja jadi kode 5 sebagai
    alternatif"). Sengaja TIDAK bergantung pada teks detail galat — teksnya
    belum pernah terekam, dan menebak polanya berarti perbaikan ini bisa
    diam-diam tidak pernah jalan.

    Kalau galatnya TIDAK berkurang, 13c DIKEMBALIKAN ke jawaban semula: baris
    yang galatnya bukan soal 13c tidak boleh ikut berubah isiannya.

    Return ringkasan BARU (dialognya terbuka lagi), atau None kalau memang tidak
    ada yang dicoba — None berarti dialog ringkasan masih seperti semula."""
    if not GALAT_13C_JADI:
        return None
    sess.close_ringkasan_dialog()
    sebelum = sess.isi_13c(GALAT_13C_JADI)
    if sebelum is None:                       # 13c tidak dirender -> tidak ada alternatif
        tanda.append("13c tidak dirender — alternatif kode 5 tidak bisa dipakai")
        return sess.check_ringkasan()
    if sebelum == GALAT_13C_JADI:             # sudah kode 5, tidak ada yang berubah
        return sess.check_ringkasan()
    sess.save()
    ring = sess.check_ringkasan()
    if ring.galat < galat_lama:
        tanda.append(f"13c '{sebelum or '(kosong)'}' -> '{GALAT_13C_JADI}': GALAT "
                     f"{galat_lama} -> {ring.galat} (alternatif, ketetapan user)")
        return ring
    if not sebelum:
        # Tadinya belum terjawab: biarkan terisi — radio tidak bisa dikosongkan lagi.
        tanda.append(f"13c diisi '{GALAT_13C_JADI}' (tadinya kosong), GALAT tidak berkurang")
        return ring
    sess.close_ringkasan_dialog()
    sess.isi_13c(sebelum)
    sess.save()
    tanda.append(f"13c dicoba '{GALAT_13C_JADI}' tapi GALAT tetap {ring.galat} — "
                 f"dikembalikan ke '{sebelum}'")
    return sess.check_ringkasan()


def id_dari_url(url: str) -> str:
    """ID dokumen dari URL entry fasih-web (.../<survey>/<periode>/<ID>/entry)."""
    bagian = [p for p in str(url or "").split("/") if p]
    return bagian[-2] if len(bagian) >= 2 and bagian[-1] == "entry" else ""


def id_dokumen_tercatat(baris: list[dict] | None = None) -> set:
    """Semua ID dokumen yang sudah tercatat di audit (dari kolom dokumen_url)."""
    sumber = baris if baris is not None else _baca_audit()
    return {i for i in (id_dari_url(b.get("dokumen_url")) for b in sumber) if i}


def jam_dokumen(iso) -> str:
    """dateCreated list API -> "YYYY-MM-DD HH:MM:SS" waktu lokal ("" kalau tidak terbaca)."""
    try:
        return datetime.datetime.fromisoformat(str(iso)).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def dokumen_asing(daftar: list[dict], id_tercatat: set, sejak: str = "") -> list[dict]:
    """Dokumen DRAFT di list server yang TIDAK tercatat di audit & dibuat pada/sesudah
    `sejak` (waktu lokal, "" = tanpa batas). Inilah jawaban "dokumen apa yang terbuat
    di sana" saat sebuah baris berakhir tanpa URL — hanya DILAPORKAN, tidak pernah
    otomatis diakui sbg dokumen baris itu (salah akui = data baris lain tertimpa)."""
    out = []
    for d in daftar:
        ident = str(d.get("id") or "")
        if not ident or ident in id_tercatat:
            continue
        if not str(d.get("assignmentStatusAlias") or "").upper().startswith("DRAFT"):
            continue
        jam = jam_dokumen(d.get("dateCreated"))
        if sejak and jam and jam < sejak:
            continue
        out.append({"id": ident, "nama": d.get("data1") or "", "waktu": jam,
                    "status": d.get("assignmentStatusAlias") or ""})
    return sorted(out, key=lambda x: x["waktu"], reverse=True)


def dokumen_bernama_persis(daftar: list[dict], nama: str, id_tercatat: set, sejak: str = "") -> dict | None:
    """Dokumen yang BOLEH diakui sbg milik baris bernama `nama` sesudah 'Buat Dokumen'
    tampak gagal: di SELURUH list tepat satu dokumen ber-`data1` persis `nama` (spasi &
    huruf besar diabaikan, sama spt sinkron_list), dan dokumen itu DRAFT, belum tercatat
    di audit, dibuat pada/sesudah `sejak`. Selain itu None (tetap dicek manual).
    Kasus 2026-09-25 baris 58: server tertahan "Memuat Halaman...", dokumen bernama
    persis terbuat 54 dtk kemudian, tapi jumlah list naik 5 krn proses lain di akun yang
    sama -> dulu DOKUMEN_TANPA_URL_PERLU_CEK padahal dokumennya jelas."""
    kunci = " ".join((nama or "").split()).upper()
    if not kunci:
        return None
    sama = [d for d in daftar if " ".join(str(d.get("data1") or "").split()).upper() == kunci]
    if len(sama) != 1:
        return None
    kandidat = dokumen_asing(sama, id_tercatat, sejak)
    return kandidat[0] if kandidat else None


def baca_list_dokumen(sess, assignment_id: str) -> list[dict] | None:
    """List API (READ-ONLY); None kalau tidak terbaca."""
    try:
        return sess.daftar_dokumen_api(assignment_id)
    except Exception as e:  # list tidak terbaca -> laporan tetap jalan, tanpa rincian
        sess._log(f"List dokumen tidak terbaca ({e}) — dokumen yang terbuat tidak bisa disebutkan.")
        return None


def sebut_dokumen_asing(sess, assignment_id: str, sejak: str = "", daftar: list[dict] | None = None) -> str:
    """Kalimat "dokumen yang terbuat" utk error_message & laporan ("" kalau tidak ada
    / list tidak terbaca). READ-ONLY: cuma membaca list API (kecuali `daftar` sudah dibaca)."""
    if daftar is None:
        daftar = baca_list_dokumen(sess, assignment_id)
    if daftar is None:
        return ""
    asing = dokumen_asing(daftar, id_dokumen_tercatat(), sejak)
    if not asing:
        return "tidak ada DRAFT baru di list yang tidak tercatat di audit"
    return "DRAFT di list yang belum tercatat: " + "; ".join(
        f"{d['id']} '{d['nama'] or '(tanpa nama)'}' @ {d['waktu'] or '?'}" for d in asing[:5])


KOLOM_TANPA_URL = ["waktu", "baris", "nama_usaha", "kunci", "akun_login", "idsubsls_input",
                   "sebab", "keterangan"]


def catatan_tanpa_url(res: dict, sebab: str = "") -> dict:
    """Satu entri laporan "dokumen mungkin terbuat tanpa URL" dari hasil satu baris."""
    return {
        "waktu": res.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "baris": res.get("baris", ""),
        "nama_usaha": res.get("nama_usaha", ""),
        "kunci": res.get("kunci", ""),
        "akun_login": res.get("akun_login", ""),
        "idsubsls_input": res.get("idsubsls_input", ""),
        "sebab": sebab or res.get("status", ""),
        "keterangan": " ".join((res.get("error_message") or "").split()),
    }


def ringkas_tanpa_url(daftar: list[dict]) -> str:
    """Laporan akhir run: dokumen MANA saja yang perlu dicek manual. Dicetak di
    layar & ditulis ke berkas, supaya run malam tidak perlu dihentikan cuma agar
    kejanggalan ini terlihat."""
    if not daftar:
        return ""
    baru = sum(1 for d in daftar if d.get("sebab") != TANDA_LEWATI_TANPA_URL)
    baris = [f"⚠ {len(daftar)} baris DILEWATI karena dokumennya mungkin terbuat tanpa URL "
             f"({baru} kejadian baru di run ini, {len(daftar) - baru} tanda lama yang belum dibereskan). "
             f"Batch tetap lanjut. Rincian: {LAPORAN_TANPA_URL_PATH}"]
    for d in daftar:
        baris.append(f"  - baris {d['baris']} — {d['nama_usaha']} — {d['akun_login']} / "
                     f"{d['idsubsls_input']} @ {d['waktu']} ({d['sebab']})")
        # Bagian sesudah "||" = dokumen yang saat itu terbaca di list tapi belum
        # tercatat di audit (lihat sebut_dokumen_asing) — itu "dokumen apa yang terbuat".
        rinci = (d.get("keterangan") or "").split("||")
        if len(rinci) > 1 and rinci[-1].strip():
            baris.append(f"      {rinci[-1].strip()}")
    baris.append("  Yang perlu dicek: cari dokumen DRAFT kosong/tanpa nama di list akun itu yang "
                 "dibuat pada jam di atas.")
    baris.append("  Ketemu  -> jalankan sinkron_list.py --tulis (URL-nya dicatat sbg DOKUMEN_DIBUAT), "
                 "atau minta admin menghapus dokumen kosongnya.")
    baris.append("  Tidak ada -> hapus baris bertanda ini dari audit supaya barisnya dikerjakan lagi.")
    return "\n".join(baris)


def tulis_laporan_tanpa_url(daftar: list[dict], path: Path = LAPORAN_TANPA_URL_PATH) -> None:
    """Tulis ulang berkas laporan (kosong = berkas dihapus, supaya sisa run lama
    tidak terbaca sbg masalah yang masih ada)."""
    if not daftar:
        if path.exists():
            path.unlink()
        return
    with lokasi.siapkan(path).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv_module.DictWriter(f, fieldnames=KOLOM_TANPA_URL)
        w.writeheader()
        for d in daftar:
            w.writerow({k: d.get(k, "") for k in KOLOM_TANPA_URL})


def _hasil_awal(row: GabunganRow, subsls_input: str, akun_login: str) -> dict:
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "baris": row.baris, "kunci": row.kunci,
        "nama_usaha": row.nama_dokumen, "kbli": row["kbli"], "idsubsls": row.idsubsls,
        "idsubsls_input": subsls_input, "akun_ppl": row.akun_ppl, "akun_login": akun_login,
        "status": "GAGAL",
    }


def process_one_row(sess: FasihWebSession, row: GabunganRow, cek: Pemeriksaan, dry_run: bool,
                    assignment_id: str, subsls_input: str, akun_login: str,
                    pernah_dibuat: bool = False, url_audit: str = "", mode_satu_list: bool = False,
                    izinkan_wilayah_beda: bool = False, kirim_tanpa_koordinat: bool = False,
                    catat_id=None) -> dict:
    """`subsls_input` = subsls tempat dokumen dibuat (mode satu subsls: sama
    utk semua baris). `pernah_dibuat` = audit mencatat dokumen baris ini dgn
    akun & subsls yang sama -> TIDAK PERNAH dibuat ulang; dibuka lewat
    `url_audit` kalau ada, kalau tidak dicari di list. `catat_id(row, url)` =
    tulis ID dokumen ke sheet sumber (PencatatIdSumber.catat; tidak pernah melempar)."""
    catat_id = catat_id or (lambda _row, _url: None)
    result = _hasil_awal(row, subsls_input, akun_login)
    tanda = list(cek.tanda)

    def _tulis_tanda():
        if tanda:
            result["review_disarankan"] = "YA — " + "; ".join(dict.fromkeys(tanda))

    try:
        # 1. Buka / buat dokumen. Retry-muat-ulang di open_entry_for HANYA
        #    diizinkan utk dokumen yang BARU dibuat (0% progres) — dokumen
        #    lama yang ketemu di list bisa sudah berisi (aturan keselamatan #2).
        sess.dokumen_url_terakhir = ""
        diakui_dari_list = False
        if url_audit:
            tanda.append("dokumen SUDAH ADA sebelumnya (dibuka lewat URL audit, diisi ulang)")
            sess.buka_dokumen_url(url_audit, row.nama_dokumen)
        elif pernah_dibuat:
            # Terbuat di run sebelumnya tapi URL-nya tidak tertangkap. Cari di
            # list saja; tidak ketemu -> FieldNotFound (cek manual), BUKAN buat lagi.
            tanda.append("dokumen pernah dibuat (URL tidak tercatat) — dicari di list, tidak dibuat ulang")
            sess.open_entry_for(row.nama_dokumen, assignment_id, allow_retry_if_fresh=False)
        else:
            # Run 2026-09-14: "Buat Dokumen" tepat setelah dokumen lain dikirim
            # dua kali tertahan "Memuat Halaman..." tanpa membuat dokumen, sedang
            # percobaan di sesi/run berikutnya lancar. Diulang SEKALI, hanya kalau
            # jumlah dokumen (API list) terbukti tidak bertambah.
            try:
                dibuat = sess.create_document(assignment_id, subsls_input, row.nama_dokumen,
                                              nama_lama=row.nama_lama_dicari)
                # Jumlah dokumen dibaca create_document sendiri dari respons API
                # list sebelum "+Dokumen Baru" (dulu muat list terpisah, ±5 dtk).
                n_awal = getattr(sess, "jumlah_dokumen_awal", None) if mode_satu_list else None
                waktu_awal = getattr(sess, "total_list_waktu", 0.0)
                # Dibawa ke main utk pengulangan di SESI BARU: di sana jumlah dokumen
                # wajib masih = angka ini, kalau tidak ada dokumen yatim -> berhenti.
                result["_jumlah_awal"], result["_waktu_awal"] = n_awal, waktu_awal
                if not dibuat and n_awal is not None:
                    sess._log("Buat dokumen gagal — tunggu 60 dtk lalu cek jumlah dokumen sebelum mengulang.")
                    sess.page.wait_for_timeout(60_000)
                    n_akhir = sess.jumlah_dokumen_list(assignment_id)
                    lebih = (kenaikan_tak_terjelaskan(n_awal, n_akhir, waktu_awal, row.kunci, akun_login)
                             if n_akhir is not None else None)
                    daftar = baca_list_dokumen(sess, assignment_id) if lebih is not None and lebih > 0 else None
                    milik = dokumen_bernama_persis(daftar or [], row.nama_dokumen, id_dokumen_tercatat(),
                                                   result.get("timestamp", ""))
                    if milik:
                        # Dokumen bernama PERSIS baris ini (satu-satunya di list, belum
                        # tercatat) = 'Buat Dokumen' sebenarnya berhasil, server saja lambat.
                        sess._log(f"'Buat Dokumen' tampak gagal, tapi list memuat tepat satu DRAFT bernama persis "
                                  f"'{row.nama_dokumen}' ({milik['id']} @ {milik['waktu'] or '?'}) — dokumen itu dipakai.")
                        tanda.append(f"'Buat Dokumen' tampak gagal; dokumen bernama persis {milik['id']} "
                                     f"ditemukan di list & dipakai (jumlah list {n_awal} -> {n_akhir})")
                        sess.dokumen_dibuat = True
                        sess.dokumen_url_terakhir = url_entry(milik["id"], assignment_id)
                        dibuat = diakui_dari_list = True
                    elif lebih is not None and lebih > 0:
                        result["status"] = STATUS_TANPA_URL
                        result["error_message"] = (
                            f"'Buat Dokumen' tampak gagal tapi jumlah dokumen naik {n_awal} -> {n_akhir} "
                            f"({lebih} tidak terjelaskan oleh DOKUMEN_DIBUAT baris lain): kemungkinan ada dokumen "
                            "tanpa URL tercatat. Cari DRAFT terbaru di list, catat URL-nya sbg DOKUMEN_DIBUAT "
                            "baris ini di audit, lalu jalankan ulang.")
                        result["error_message"] += " || " + sebut_dokumen_asing(
                            sess, assignment_id, result.get("timestamp", ""), daftar)
                        _tulis_tanda()
                        return result
                    elif lebih is not None and lebih <= 0:
                        sess._log(f"Jumlah dokumen {n_awal} -> {n_akhir}, semua terjelaskan — aman diulang sekali.")
                        dibuat = sess.create_document(assignment_id, subsls_input, row.nama_dokumen,
                                                      nama_lama=row.nama_lama_dicari)
            except FieldNotFound as e:
                if "Dropdown" not in str(e):
                    raise
                result["status"] = "STOP_SUBSLS_TIDAK_BISA_DIPILIH"
                result["error_message"] = (
                    f"Subsls {subsls_input} tidak bisa dipilih di Wilayah Responden akun ini "
                    f"(belum ada assignment / sudah ditandai selesai?): {e}")
                _tulis_tanda()
                return result
            if not dibuat:
                result["status"] = "SKIP_DOKUMEN_BELUM_ADA"
                result["error_message"] = (
                    f"Dokumen '{row.nama_dokumen}' belum ada & gagal dibuat otomatis (subsls {subsls_input}). "
                    "Buat manual di fasih-web DENGAN NAMA PERSIS INI, lalu jalankan ulang baris ini.")
                return result
            dokumen_baru = bool(sess.dokumen_url_terakhir)
            if sess.dokumen_dibuat:
                append_audit({**result, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "status": STATUS_DIBUAT,
                              "dokumen_url": sess.dokumen_url_terakhir})
                # Ke sheet SEKARANG, sebelum mengisi: kalau pengisian gagal di tengah,
                # baris ini tetap terikat ke dokumennya walau namanya diubah nanti.
                catat_id(row, sess.dokumen_url_terakhir)
            if sess.dokumen_dibuat and not dokumen_baru and not getattr(sess, "nama_di_modal", True):
                # Dokumen baru tanpa nama & tanpa URL tidak bisa dicari di list —
                # lanjut ke baris lain hanya menumpuk dokumen kosong yatim.
                result["status"] = STATUS_TANPA_URL
                result["error_message"] = (
                    "Dokumen baru terbuat tapi tidak terbuka otomatis & modal tidak punya field nama — "
                    "URL-nya tidak diketahui. Cari dokumen DRAFT BLANK terbaru di list, catat URL-nya "
                    "sbg DOKUMEN_DIBUAT utk baris ini di audit, lalu jalankan ulang.")
                result["error_message"] += " || " + sebut_dokumen_asing(
                    sess, assignment_id, result.get("timestamp", ""))
                _tulis_tanda()
                return result
            if not dokumen_baru:
                tanda.append("dokumen SUDAH ADA sebelumnya (diisi ulang)")
            if diakui_dari_list:
                sess.buka_dokumen_url(sess.dokumen_url_terakhir, row.nama_dokumen)
            else:
                sess.open_entry_for(row.nama_dokumen, assignment_id, allow_retry_if_fresh=dokumen_baru)
        if "/entry" in sess.page.url:
            result["dokumen_url"] = sess.page.url
            catat_id(row, sess.page.url)

        # 2. PENGANTAR -> IDENTITAS WILAYAH -> SE2026 - P (form-engine hanya
        #    merender section aktif).
        sess.fill_pengantar()
        if not sess.next_section():
            raise FieldNotFound(f"Section setelah PENGANTAR tidak ter-enable. Tersedia: {sess.list_sections()}")

        # CEK LANGSUNG: dokumen ini benar-benar ada di subsls tujuan input?
        # Dibaca dari rincian 1-6 BLOK I (prefilled dari wilayah dokumen).
        wilayah_dok = sess.baca_wilayah_dokumen()
        status_w, pesan_w = cocokkan_wilayah_dokumen(
            wilayah_dok, subsls_input, WILAYAH_BY_IDSUBSLS.get(subsls_input))
        result["wilayah_dokumen"] = f"{status_w}: {pesan_w}"
        server_w = ""
        if status_w == "BEDA":
            # Kode SLS BLOK I TIDAK selalu = wilayah assignment (2026-09-25, subsls
            # 5108060006000110: modal [0001]->[10] benar & server level6 benar, form
            # menampilkan kode_sls '0002'). Yang menentukan = region dokumen di SERVER.
            server_w, sumber_w = sess.wilayah_dokumen_server(id_dari_url(sess.page.url), row.nama_dokumen)
            sess._log(f"  Wilayah dokumen menurut server: {server_w or '-'} ({sumber_w})")
            if server_w == subsls_input:
                tanda.append(f"kode SLS BLOK I form '{wilayah_dok.get('kode_sls')}' beda dgn {subsls_input}, "
                             f"tapi wilayah dokumen di server ({sumber_w}) = {subsls_input} — diteruskan")
                status_w = "COCOK"
                pesan_w = f"server ({sumber_w}) = {subsls_input}; BLOK I beda: {pesan_w}"
                result["wilayah_dokumen"] = f"{status_w}: {pesan_w}"
            else:
                pesan_w += f" | server: {server_w or 'tidak terbaca'} ({sumber_w})"
        if status_w == "BEDA":
            # Beberapa subsls dipakai bergantian sbg WADAH dokumen (dikembalikan
            # ke wilayah aslinya belakangan lewat pindah_wilayah). Dokumen yang
            # SUDAH ADA & masih di kabupaten sendiri boleh diteruskan — yang tidak
            # pernah boleh: dokumen yang BARU dibuat (berarti subsls salah dipilih)
            # atau dokumen di kabupaten lain (bukan wilayah kerja akun ini).
            nyata = server_w or idsubsls_dari_wilayah(wilayah_dok)
            sudah_ada = bool(url_audit) or pernah_dibuat
            if not (izinkan_wilayah_beda and sudah_ada and nyata.startswith(KODE_KAB)):
                result["status"] = "STOP_WILAYAH_DOKUMEN_BEDA"
                sebab = ("dokumen BARU dibuat (berarti subsls salah dipilih, bukan sekadar wadah lain)"
                         if not sudah_ada else
                         f"wilayah dokumen '{nyata or 'tidak terbaca'}' di luar kabupaten {KODE_KAB}")
                result["error_message"] = pesan_w + (
                    f" | --izinkan-wilayah-beda tidak berlaku: {sebab}" if izinkan_wilayah_beda else "")
                sess._shot(f"WILAYAH_BEDA_gabungan_{row.baris}")
                _tulis_tanda()
                return result
            sess._log(f"  ⚠️ Wilayah dokumen {nyata} != subsls input {subsls_input} — diteruskan.")
            if len(nyata) == 16:
                tanda.append(f"wilayah dokumen {nyata} BEDA dari subsls input {subsls_input} — diteruskan "
                             "(--izinkan-wilayah-beda); subsls yang dicatat di audit = wilayah dokumen")
                result["idsubsls_input"] = nyata
                subsls_input = nyata
            else:
                # Kode SLS 4 digit: subsls-nya tidak ditampilkan form, jadi jangan
                # ditebak — audit tetap memakai subsls run ini, dgn tanda.
                tanda.append(f"wilayah dokumen {nyata} (subsls tidak terbaca dari form) BEDA dari "
                             f"{subsls_input} — diteruskan, subsls audit tetap {subsls_input}")
        wilayah_terverifikasi = status_w in ("COCOK", "BEDA")
        if not wilayah_terverifikasi:
            tanda.append("WILAYAH DOKUMEN TIDAK TERVERIFIKASI (lihat kolom wilayah_dokumen) — tidak dikirim")
        if sess.dokumen_terkunci():
            result["status"] = STATUS_TERKUNCI
            result["error_message"] = ("Dokumen sudah tidak bisa diubah (SUBMITTED/terkunci, mis. dikirim manual) "
                                       "— tidak diisi ulang. Cek statusnya di list PENDATAAN.")
            _tulis_tanda()
            return result

        sess.fill_identitas_wilayah(row["kodepos"])
        if not sess.next_section():
            raise FieldNotFound(f"Section setelah IDENTITAS WILAYAH tidak ter-enable. Tersedia: {sess.list_sections()}")

        # Nomor Urut Bangunan dari sheet SENGAJA tidak diketik (aturan
        # keselamatan #3) — cuma dicatat utk pembanding kalau auto-fix jalan.
        sess.fill_se2026_p(nama_usaha=row.nama_dokumen, nama_jalan=row.jalan_lengkap,
                           blok_nomor=row.nomor_rumah)
        if cek.tanpa_koordinat:
            sess._log("Geotagging DILEWATI — koordinat baris ini belum ada"
                      + (" (dokumen TETAP DIKIRIM: --koordinat kirim)." if kirim_tanpa_koordinat
                         else " (dokumen ditahan sbg DRAFT)."))
            tanda.append("geotag KOSONG (koordinat tidak ada di sheet)"
                         + (" — dikirim tanpa geotag" if kirim_tanpa_koordinat else ""))
        else:
            sess.do_geotagging(row["latitude"], row["longitude"])
        sess.save()
        if not sess.next_section():
            raise FieldNotFound(f"Section setelah SE2026-P tidak ter-enable. Tersedia: {sess.list_sections()}")

        # 3. BLOK II (nested)
        sess.buka_nested(0)
        tanda.extend(fill_blok2_gabungan(sess, row))
        sess.save()

        # 4. Keterangan pemberi jawaban + catatan
        if not sess.goto_section("KETERANGAN PEMBERI JAWABAN"):
            raise FieldNotFound(f"Section KETERANGAN PEMBERI JAWABAN tidak ter-enable. Tersedia: {sess.list_sections()}")
        fill_keterangan_pemberi_jawaban(sess)
        if not sess.goto_section("CATATAN"):
            raise FieldNotFound(f"Section CATATAN tidak ter-enable. Tersedia: {sess.list_sections()}")
        fill_catatan(sess)
        sess.save()

        # 5. Ringkasan — pola GALAT sama persis dgn main.py.
        ring = sess.check_ringkasan()
        if cek.tanpa_koordinat and not kirim_tanpa_koordinat:
            # TIDAK PERNAH dikirim, apa pun --submit-nya. GALAT tetap dilaporkan
            # supaya draft yang masih bermasalah ketahuan sebelum koordinatnya
            # dilengkapi (Nomor Urut Bangunan diperbaiki di run pelengkap).
            if ring.galat > 0:
                # 13c ikut dibereskan di sini juga: draft tanpa koordinat memang
                # tidak dikirim, tapi galatnya terhitung di kartu "Jumlah Error"
                # server & harus sudah bersih saat koordinatnya dilengkapi nanti.
                detail = sess.read_galat_detail()
                ring_alt = coba_13c_alternatif(sess, ring.galat, tanda)
                if ring_alt is not None:
                    ring = ring_alt
                    detail = sess.read_galat_detail() if ring.galat > 0 else ""
            result["status"] = STATUS_DRAFT_TANPA_KOORDINAT
            result["galat"], result["peringatan"] = ring.galat, ring.peringatan
            result["catatan_count"], result["kosong"] = ring.catatan, ring.kosong
            if ring.galat > 0:
                result["error_message"] = f"Draft tanpa koordinat, GALAT {ring.galat}: {detail}"[:1500]
                tanda.append(f"DRAFT MASIH ADA GALAT ({ring.galat}) — tinjau sebelum koordinat dilengkapi")
            sess.close_ringkasan_dialog()
            try:
                sess.page.keyboard.press("Escape")
                sess.page.wait_for_selector('[role="dialog"]', state="hidden", timeout=8_000)
            except Exception:
                pass
            _tulis_tanda()
            return result
        if ring.galat > 0:
            detail = sess.read_galat_detail()
            # Cabang lama: satu-satunya galat = Nomor Urut Bangunan (aturan keselamatan #3).
            nomor_urut = "Nomor Urut Bangunan" in detail and detail.count("\n") <= 3
            if nomor_urut:
                sess._log(f"Nomor Urut Bangunan di sheet = '{row['no_bang']}' (pembanding saja, tidak dipakai).")
                sess.close_ringkasan_dialog()
                sess.fix_nomor_urut_bangunan_if_needed()
                sess.save()
                ring = sess.check_ringkasan()
            else:
                # Alternatif yang diminta user: coba 13c = kode 5 dulu sebelum menyerah.
                ring_alt = coba_13c_alternatif(sess, ring.galat, tanda)
                if ring_alt is not None:
                    ring = ring_alt
                    detail = sess.read_galat_detail() if ring.galat > 0 else detail
            if ring.galat > 0 and not nomor_urut:
                result["status"] = "SKIP_GALAT_PERLU_REVIEW"
                result["galat"], result["peringatan"], result["kosong"] = ring.galat, ring.peringatan, ring.kosong
                result["error_message"] = f"GALAT selain Nomor Urut Bangunan: {detail}"
                sess.close_ringkasan_dialog()
                try:
                    sess.page.keyboard.press("Escape")
                    sess.page.wait_for_selector('[role="dialog"]', state="hidden", timeout=8_000)
                except Exception:
                    pass
                sess.page.wait_for_timeout(800)
                sess.dump(f"GALAT_gabungan_{row.baris}_blok2", paksa=True)
                _tulis_tanda()
                return result

        result["galat"], result["peringatan"] = ring.galat, ring.peringatan
        result["catatan_count"], result["kosong"] = ring.catatan, ring.kosong
        if ring.peringatan > 2 or ring.kosong > 22 or ring.kosong < 17:
            tanda.append(f"peringatan/kosong ({ring.peringatan}/{ring.kosong}) menyimpang dari pola backlog lama (~1 / ~19-20)")
        _tulis_tanda()

        if ring.galat != 0:
            result["status"] = "SKIP_GALAT_TIDAK_TERATASI"
            sess.close_ringkasan_dialog()
            return result
        if dry_run:
            result["status"] = "DRY_RUN_SIAP_KIRIM"
            sess.close_ringkasan_dialog()
            return result
        if not wilayah_terverifikasi:
            result["status"] = "SKIP_WILAYAH_TIDAK_TERVERIFIKASI"
            result["error_message"] = f"Tidak dikirim: wilayah dokumen tidak bisa dipastikan = {subsls_input}. {pesan_w}"
            sess.close_ringkasan_dialog()
            return result

        submitted = sess.submit_final()
        if not submitted and "/entry" in sess.page.url:
            # Run 2026-09-14 (satu baris Agenda): "Konfirmasi" diklik, dialog tertutup,
            # tapi tidak ada toast/redirect & status tetap DRAFT — server sibuk.
            # Mengirim ulang DOKUMEN YANG SAMA tidak membuat duplikat; kalau
            # ternyata sudah terkirim, tombol Kirim/ringkasan tidak ada lagi.
            sess._log("Kirim tanpa tanda sukses — tunggu 15 dtk, cek ringkasan & kirim ulang sekali.")
            sess.page.wait_for_timeout(15_000)
            ring2 = sess.check_ringkasan()
            if ring2.galat == 0:
                submitted = sess.submit_final()
            else:
                sess.close_ringkasan_dialog()
        # Percepatan 2026-09-14: kalau submit_final sudah melihat tanda sukses JELAS
        # (toast "berhasil dikirim" / redirect ke list), list tidak dicek per baris —
        # statusnya tertinggal beberapa detik-menit (±8-18 dtk terbuang/baris) & dicek
        # massal lewat API setelah batch. Kiriman TANPA tanda sukses tetap dicek di list.
        verified = False if submitted else sess.verify_submitted_in_list(assignment_id, row.nama_dokumen)
        result["status"] = "TERKIRIM_TERVERIFIKASI" if verified else (
            "TERKIRIM_BELUM_TERVERIFIKASI" if submitted else "SUBMIT_GAGAL")
        if result["status"] == "SUBMIT_GAGAL":
            result["error_message"] = f"Kirim tanpa tanda sukses (2x). {getattr(sess, 'submit_jejak', '')}"[:1500]
        return result

    except DokumenNamaLamaAda as e:
        result["status"] = "SKIP_DOKUMEN_NAMA_LAMA"
        result["error_message"] = str(e)
        _tulis_tanda()
        return result
    except BarisPerluManual as e:
        result["status"] = f"SKIP_{e.kode}"
        result["error_message"] = str(e)
        _tulis_tanda()
        return result
    except FieldNotFound as e:
        result["status"] = "ERROR_FIELD_NOT_FOUND"
        result["error_message"] = str(e)
        _tulis_tanda()
        return result
    except Exception as e:  # noqa: BLE001 — 1 baris gagal jangan hentikan batch
        result["status"] = "ERROR_TAK_TERDUGA"
        jejak = " ~ ".join(traceback.format_exc().splitlines())
        result["error_message"] = f"{type(e).__name__}: {e} || {jejak[-900:]}"
        try:
            sess._shot(f"ERROR_gabungan_{row.baris}_{type(e).__name__}")
        except Exception:
            pass
        _tulis_tanda()
        return result


def rencana_sesi(rows: list[GabunganRow], akun_tunggal: str, per_sesi: int) -> list[tuple[str, list[GabunganRow]]]:
    """[(akun, baris)] — satu login per elemen. Mode satu akun: dipotong tiap
    `per_sesi` baris (sesi SSO ±12 jam nonstop berisiko kedaluwarsa)."""
    if akun_tunggal:
        n = max(1, per_sesi)
        return [(akun_tunggal, rows[i:i + n]) for i in range(0, len(rows), n)]
    return list(kelompok_per_akun(rows).items())


def sinkron_audit_dari_server(sess, semua, hasil, sumber: str, akun: str, subsls: str,
                             assignment_id: str) -> int:
    """Perbarui audit dari TABEL daftar dokumen di server (list API, READ-ONLY),
    sebelum batch mengerjakan barisnya. Dokumen yang dibuat PC lain jadi dikenali
    -> dibuka lewat URL, bukan dibuat lagi (duplikat), dan yang sudah terkirim
    dilewati --lewati-selesai. Logikanya dipinjam dari sinkron_list.rencana_sinkron
    (fungsi murni yang sama) supaya tidak ada dua versi aturan."""
    from input_usaha.sinkron_list import rencana_sinkron   # impor di sini: sinkron_list impor modul ini
    items = sess.daftar_dokumen_api(assignment_id)
    if items is None:
        print("⚠️ Daftar dokumen server tidak terbaca — sinkron dilewati, batch lanjut apa adanya.")
        return 0
    sumber_rows = [(sumber, r, hasil[r.baris].status) for r in semua]
    _laporan, tulis, tak_dikenal = rencana_sinkron(
        sumber_rows, items, akun, subsls, assignment_id, _baca_audit(),
        lengkap=bool(getattr(sess, "daftar_dokumen_lengkap", False)))
    for t in tulis:
        append_audit(t)
    print(f"Sinkron tabel: {len(items)} dokumen di server, {len(tulis)} catatan audit diperbarui "
          f"{dict(Counter(t['status'] for t in tulis))}; {len(tak_dikenal)} dokumen server tak dikenali.")
    return len(tulis)


def laporan_cek(rows: list[GabunganRow], hasil: dict[int, Pemeriksaan], sumber: str,
                semua: list[GabunganRow], mode: str, n_sesi, perintah: str = "") -> int:
    """Cetak ringkasan pemeriksaan `rows` (pilihan --baris) + tulis rincian
    SELURUH sheet (`semua`) ke CSV — supaya file itu selalu lengkap utk
    dipakai memperbaiki sheet, apa pun pilihan --baris-nya."""
    siap = [r for r in rows if hasil[r.baris].bisa_diproses]
    print(f"=== PEMERIKSAAN: {len(rows)} baris dari {sumber} — {mode} ===\n")
    for status, n in Counter(hasil[r.baris].status for r in rows).most_common():
        ket = ""
        if status == STATUS_SIAP_TANPA_KOORDINAT:
            ket = ("  (dibuat & diisi TANPA geotag, lalu DIKIRIM)" if "DIKIRIM tanpa geotag" in mode
                   else "  (dibuat & diisi TANPA geotag, disimpan DRAFT — tidak dikirim)")
        print(f"  {'OK ' if hasil_ok(status) else '!! '}{n:4d}  {status}{ket}")

    semua_kode = Counter(k for r in rows for k, _ in hasil[r.baris].masalah)
    if semua_kode:
        print("\n=== semua masalah (satu baris bisa punya lebih dari satu) ===")
        contoh = defaultdict(list)
        for r in rows:
            for k, p in hasil[r.baris].masalah:
                contoh[k].append((r, p))
        for kode, n in semua_kode.most_common():
            print(f"  {n:4d}  {kode}")
            for r, p in contoh[kode][:3]:
                print(f"          baris {r.baris:<5} {r.nama_dokumen[:38]:38s} {p[:110]}")

    tanda = Counter(re.sub(r"'[^']*'|\b\d{4,}\b", "#", t.split(" (")[0].split(":")[0])
                    for r in siap for t in hasil[r.baris].tanda)
    if tanda:
        print("\n=== tanda review pada baris SIAP (tidak di-skip) ===")
        for t, n in tanda.most_common(8):
            print(f"  {n:4d}  {t}")

    with lokasi.siapkan(CEK_PATH).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv_module.writer(f)
        w.writerow(["baris", "kunci", "akun_ppl", "idsubsls", "nama", "nama_dokumen", "status", "masalah", "tanda"])
        for r in semua:
            h = hasil[r.baris]
            w.writerow([r.baris, r.kunci, r.akun_ppl, r.idsubsls, r.nama, r.nama_dokumen, h.status, h.pesan,
                        " | ".join(h.tanda)])
    print(f"\nRincian per baris: {CEK_PATH} (buka di Excel/Sheets, filter kolom status).")

    if siap:
        jam = len(siap) * MENIT_PER_BARIS / 60
        n_draft = sum(hasil[r.baris].tanpa_koordinat for r in siap)
        print(f"\n{len(siap)} baris bisa diproses ({len(siap) - n_draft} lengkap -> dikirim kalau --submit, "
              f"{n_draft} tanpa koordinat -> DRAFT), {n_sesi(siap)} sesi login, estimasi ±{jam:.1f} jam VPN nonstop.")
        print("Perintah berikutnya (dry-run SATU baris, TIDAK mengirim):")
        print(f"  {perintah or PERINTAH} --sumber {sumber} "
              f"--baris {siap[0].baris}")
    return 0 if len(siap) == len(rows) else 1


def hasil_ok(status: str) -> bool:
    return status in ("SIAP", STATUS_SIAP_TANPA_KOORDINAT)


FORMAT_BAWAAN = "tahap2"
PERINTAH = "python input_usaha/jalankan.py"


def _nama_format(teks: str) -> str:
    """Nilai --format; "standar" = nama lama utk "agenda" (sebelum 2026-09-25)."""
    teks = str(teks).strip().lower()
    return {"standar": "agenda"}.get(teks, teks)


def opsi_format(ap, bantuan: str = "") -> None:
    """Tambahkan `--format` ke parser alat mana pun. tahap2 = SATU-SATUNYA format input
    usaha yang dipakai & didokumentasikan sejak 2026-09-25; agenda = format lama Buleleng
    (Agenda*.xlsx, 92 kolom), hanya utk membaca ulang data lama."""
    ap.add_argument("--format", type=_nama_format, choices=("tahap2", "agenda"), default=FORMAT_BAWAAN,
                    help=bantuan or "tahap2 (bawaan) = format input usaha (templates/input_usaha.xlsx); "
                                    "agenda = format lama Agenda*.xlsx")


def muat_sumber(sumber: str, format_sumber: str = "standar", mode_satu_subsls: bool = True,
                kodepos: str = "", cek_total: bool = True,
                izinkan_tanpa_koordinat: bool = False) -> tuple[list[GabunganRow], dict[int, Pemeriksaan]]:
    """(baris, hasil pemeriksaan offline) satu file sumber. Pemeriksaan lintas-baris
    selalu atas SELURUH sheet, apa pun pilihan --baris/--dari/--sampai. Dipakai juga
    sinkron_list.py supaya format tahap 2 dikenali di kedua skrip."""
    if format_sumber == "tahap2":
        rows = load_tahap2(sumber, kodepos=kodepos)
        hasil = periksa_semua_tahap2(rows, mode_satu_subsls=mode_satu_subsls, cek_total=cek_total,
                                     izinkan_tanpa_koordinat=izinkan_tanpa_koordinat)
    else:
        rows = load_gabungan(sumber)
        hasil = periksa_semua(rows, mode_satu_subsls=mode_satu_subsls,
                              izinkan_tanpa_koordinat=izinkan_tanpa_koordinat)
    # Kolom "ID Dokumen FASIH" (ditulis balik oleh PencatatIdSumber): row.id_dokumen.
    pasang_id(rows, hasil, baca_kolom_id(sumber, format_sumber))
    return rows, hasil


def koordinat_otomatis(pilihan: str | None, format_sumber: str) -> bool:
    """Baris tanpa koordinat tetap dibuat & diisi? None = bawaan per format
    (tahap2 -> otomatis, standar -> wajib). "kirim" juga ikut mengisi."""
    return (pilihan or ("otomatis" if format_sumber == "tahap2" else "wajib")) in ("otomatis", "kirim")


def koordinat_dikirim(pilihan: str | None) -> bool:
    """--koordinat kirim: dokumen tanpa geotag TIDAK ditahan sbg draft, tapi
    dikirim juga. Dipakai kalau koordinat tidak akan dilengkapi & dokumen harus
    bersih di server (draft selalu terhitung di kartu "Jumlah Error")."""
    return pilihan == "kirim"


def tuntas_menurut_audit(status_audit: str, tuntas: set, punya_koordinat: bool) -> bool:
    """--lewati-selesai: baris sudah tidak perlu dikerjakan? DRAFT_TANPA_KOORDINAT
    tuntas HANYA selama koordinatnya masih kosong di sheet — begitu diisi, baris
    diproses lagi (buka dokumen yang sama lewat URL audit, geotag, kirim)."""
    if status_audit == STATUS_DRAFT_TANPA_KOORDINAT:
        return not punya_koordinat
    return status_audit in tuntas


def saring_rentang(rows: list[GabunganRow], dari: int | None, sampai: int | None) -> list[GabunganRow]:
    """--dari/--sampai: nomor baris sheet (judul = baris 1), kedua ujung ikut."""
    return [r for r in rows if (dari is None or r.baris >= dari) and (sampai is None or r.baris <= sampai)]


def main(argv: list[str] | None = None, perintah: str = PERINTAH):
    """Dipanggil input_usaha/jalankan.py (pintu masuk). Semua orkestrasi, audit &
    pengaman ada di file ini supaya tidak diduplikasi."""
    _fasih_web.SCREENSHOT_DIR = lokasi.HASIL_INPUT / "log_screenshots"
    ap = argparse.ArgumentParser(description="Input usaha SE2026 ke fasih-web dari sheet input usaha (format tahap 2)")
    ap.add_argument("--sumber", required=True, help="File .xlsx / .csv sheet input usaha, mis. bahan/input_usaha.xlsx")
    opsi_format(ap)
    ap.add_argument("--kodepos", default="",
                    help="Format tahap2: kodepos cadangan utk desa yang belum ada di KODEPOS_BY_IDSUBSLS/"
                         "KODEPOS_BY_DESA. Dipakai HANYA kalau sumber lain kosong.")
    ap.add_argument("--koordinat", choices=("otomatis", "wajib", "kirim"), default=None,
                    help="otomatis = baris tanpa latitude/longitude TETAP dibuat & diisi lengkap kecuali "
                         "geotag, lalu ditahan sbg DRAFT (tidak dikirim walau --submit); jalankan ulang "
                         "setelah koordinat diisi -> geotag + kirim. wajib = baris tanpa koordinat di-skip. "
                         "kirim = sama dgn otomatis TAPI dokumennya tetap DIKIRIM tanpa geotag "
                         "(form hanya mewajibkan geotag utk mode CAPI; dokumen PAPI lolos). "
                         "Bawaan: otomatis (format agenda: wajib).")
    ap.add_argument("--abaikan-cek-total", action="store_true",
                    help="Format tahap2: jangan bandingkan kolom TOTAL sheet (24.Total, Rp26, 27c, 28c) "
                         "dgn jumlah rinciannya. Pakai kalau kolom total di Excel memang belum diisi.")
    ap.add_argument("--cek", action="store_true", help="Hanya periksa data (tanpa browser/VPN), tulis input_usaha/hasil/cek_input.csv")
    ap.add_argument("--submit", action="store_true", help="Mode LIVE — benar2 klik Kirim. Default: dry-run.")
    ap.add_argument("--headless", action="store_true", help="JANGAN DIPAKAI — ditolak (fasih-web membalas headless dgn halaman anti-bot).")
    ap.add_argument("--baris", default=None, help="Nomor baris sheet, mis. 2,5,10-20")
    ap.add_argument("--dari", type=int, default=None,
                    help="Mulai dari baris sheet ke-N (judul = baris 1). Boleh digabung --sampai; "
                         "dipakai membagi pekerjaan antar-PC/proses, mis. --dari 2 --sampai 200")
    ap.add_argument("--sampai", type=int, default=None, help="Sampai baris sheet ke-N (ikut diproses)")
    ap.add_argument("--limit", type=int, default=None, help="Batasi jumlah baris diproses")
    ap.add_argument("--lewati-selesai", action="store_true",
                    help="Lewati baris yang sudah selesai menurut audit (dicocokkan lewat kunci)")
    ap.add_argument("--assignment-id", default=ASSIGNMENT_ID_GABUNGAN,
                    help="Segmen URL list PENDATAAN /survey/{SURVEY_ID}/{ini} (default: config)")
    ap.add_argument("--subsls-tunggal", default=GABUNGAN_SUBSLS_TUNGGAL,
                    help="idsubsls 16 digit tempat SEMUA dokumen dibuat (default: config GABUNGAN_SUBSLS_TUNGGAL)")
    ap.add_argument("--akun-tunggal", default=GABUNGAN_AKUN_TUNGGAL,
                    help="Email akun PPL yang membuat SEMUA dokumen (default: config GABUNGAN_AKUN_TUNGGAL)")
    ap.add_argument("--hanya-galat", action="store_true",
                    help="kerjakan HANYA baris yang dokumennya ditandai galat oleh server "
                         f"({STATUS_DRAFT_GALAT}; tanda ditulis sinkron_list/--sinkron-dulu). "
                         "Gabungkan dgn --sinkron-dulu supaya tandanya segar")
    ap.add_argument("--urut-sheet", action="store_true",
                    help="kerjakan murni urut nomor baris; tanpa ini baris yang dokumennya ditandai "
                         "galat oleh server didahulukan")
    ap.add_argument("--sinkron-dulu", action="store_true",
                    help="sebelum mengisi, perbarui audit dari TABEL daftar dokumen di server "
                         "(seperti sinkron_list.py --tulis, memakai sesi login yang sama). Dokumen "
                         "yang dibuat PC lain jadi dikenali -> dibuka, bukan dibuat lagi")
    ap.add_argument("--izinkan-wilayah-beda", action="store_true",
                    help="dokumen yang SUDAH ADA boleh diisi & dikirim walau wilayah BLOK I-nya bukan "
                         "--subsls-tunggal (beberapa subsls dipakai bergantian sbg wadah; dikembalikan "
                         "belakangan lewat pindah_wilayah). Subsls yang dicatat di audit = wilayah "
                         "dokumen yang sebenarnya. Dokumen yang BARU dibuat tetap menghentikan batch")
    ap.add_argument("--baris-per-sesi", type=int, default=GABUNGAN_BARIS_PER_SESI,
                    help="Mode satu akun: login ulang tiap N baris (default: config)")
    ap.add_argument("--paralel", action="store_true",
                    help="Dijalankan bersamaan dgn batch lain (rentang --baris TIDAK BOLEH tumpang tindih): "
                         "gagal buat dokumen TIDAK diulang (hindari duplikat), dikerjakan pass tunggal sesudahnya")
    ap.add_argument("--per-baris", action="store_true",
                    help="Alur LAMA: dokumen dibuat di idsubsls baris oleh akun PPL baris")
    ap.add_argument("--maks-error-beruntun", type=int, default=3,
                    help="Hentikan batch setelah N baris ERROR_* berturut-turut (mis. VPN putus). 0 = jangan berhenti.")
    ap.add_argument("--coba-terkunci", action="store_true",
                    help="Kerjakan lagi baris berstatus DOKUMEN_TERKUNCI (bawaan: dilewati sbg tuntas, "
                         "karena UI membuktikan dokumennya read-only). Pakai setelah admin/PML membukanya.")
    ap.add_argument("--maks-tanpa-url", type=int, default=3,
                    help="Hentikan batch setelah N baris berstatus DOKUMEN_TANPA_URL_PERLU_CEK "
                         "(1 = perilaku lama: berhenti di kejadian pertama; 0 = jangan pernah berhenti). "
                         "Baris itu sendiri SELALU dilewati, tidak pernah diulang otomatis.")
    ap.add_argument("--dump-dom", action="store_true",
                    help="Simpan peta dataKey tiap section ke input_usaha/hasil/log_screenshots/")
    ap.add_argument("--audit-baru", action="store_true",
                    help="Izinkan audit yang TIDAK mengenal satu pun baris sheet walau audit lain di audit/ "
                         "mengenalnya (bawaan: berhenti, kemungkinan besar --audit lupa/salah).")
    opsi_audit(ap)
    args = ap.parse_args(argv)
    lokasi.cek_struktur_lama()
    pakai_audit(args.audit)
    cetak_lokasi_audit()

    pastikan_audit_utuh()
    if args.headless:
        print("❌ --headless tidak didukung: fasih-web membalas browser headless dgn halaman anti-bot.",
              file=sys.stderr)
        return 2

    satu_subsls = not args.per_baris
    subsls_tunggal = (args.subsls_tunggal or "").strip() if satu_subsls else ""
    akun_tunggal = (args.akun_tunggal or "").strip().lower() if satu_subsls else ""
    if satu_subsls:
        mode = f"MODE SATU SUBSLS: subsls={subsls_tunggal or '(belum diisi)'} akun={akun_tunggal or '(belum diisi)'}"
    else:
        mode = "MODE PER BARIS (alur lama)"
    mode += f" | format {args.format}"
    if args.format == "tahap2":
        mode += " (rincian di luar kuesioner kertas diisi TAHAP2_DEFAULT)"
    else:
        mode += " | ISIAN MURNI dari Excel" if GABUNGAN_MODE_MURNI else " | aturan & koreksi Buleleng aktif"
    if satu_subsls and not args.cek and not (re.fullmatch(r"\d{16}", subsls_tunggal) and "@" in akun_tunggal):
        print("❌ Mode satu subsls butuh --subsls-tunggal (16 digit) DAN --akun-tunggal (email PPL), atau isi "
              "GABUNGAN_SUBSLS_TUNGGAL/GABUNGAN_AKUN_TUNGGAL di inti/config_lokal.py. Alur lama: --per-baris.",
              file=sys.stderr)
        return 2

    if args.format == "tahap2" and args.per_baris:
        print("❌ Format tahap2 tidak mendukung --per-baris: sheet-nya tidak punya kolom email akun PPL "
              "(kolom 'Nama PPL' berisi NAMA, bukan email). Pakai --akun-tunggal + --subsls-tunggal, atau "
              "tambahkan kolom 'Akun PPL' berisi email di sheet.", file=sys.stderr)
        return 2

    if args.dari is not None and args.sampai is not None and args.dari > args.sampai:
        print(f"❌ --dari {args.dari} lebih besar dari --sampai {args.sampai}.", file=sys.stderr)
        return 2
    izinkan_tanpa_koordinat = koordinat_otomatis(args.koordinat, args.format)
    kirim_tanpa_koordinat = koordinat_dikirim(args.koordinat)
    mode += (" | koordinat OTOMATIS (tanpa koordinat -> DIKIRIM tanpa geotag)" if kirim_tanpa_koordinat
             else " | koordinat OTOMATIS (tanpa koordinat -> DRAFT)" if izinkan_tanpa_koordinat
             else " | koordinat WAJIB")
    rows, hasil = muat_sumber(args.sumber, args.format, satu_subsls, args.kodepos,
                              cek_total=not args.abaikan_cek_total,
                              izinkan_tanpa_koordinat=izinkan_tanpa_koordinat)
    semua = rows
    n_dikenal, lain = audit_lain_yang_mengenal(semua)
    if lain:
        print(f"{PENANDA_AUDIT_TIDAK_COCOK}: {AUDIT_LOG_PATH} hanya mengenal {n_dikenal} dari {len(semua)} "
              f"baris {args.sumber}, padahal audit lain jauh lebih mengenalnya:")
        for f, n in lain[:5]:
            print(f"     {f}  ({n} baris)")
        print("   Kemungkinan besar --audit lupa/salah -> semua baris akan dianggap belum punya dokumen (GANDA).")
        print("   Ulangi dgn --audit <berkas di atas>. Kalau memang batch baru dgn audit baru: tambah --audit-baru.")
        if not args.cek and not args.audit_baru:
            return 2
    baris_id_asing, kenal_id = id_sheet_belum_digabung(semua)
    if kenal_id:
        print(f"{PENANDA_AUDIT_TIDAK_COCOK}: {len(baris_id_asing)} baris {args.sumber} menyimpan ID dokumen yang "
              f"TIDAK dikenal {AUDIT_LOG_PATH}, padahal dikenal audit lain:")
        for f, n in kenal_id[:5]:
            print(f"     {f}  ({n} ID)")
        print(f"   Contoh baris: {', '.join(map(str, baris_id_asing[:10]))}"
              + (" …" if len(baris_id_asing) > 10 else ""))
        print("   Sheet sudah digabung, audit belum. Dokumen itu akan dibuka lewat ID padahal bisa milik akun lain")
        print("   (form tidak mount, login ulang tiap baris). Gabungkan audit dulu (antar_pc/README.md bagian 2):")
        print(f"     python antar_pc/gabung_audit.py --sumber audit/pc --sumber {AUDIT_LOG_PATH} "
              f"--keluaran {AUDIT_LOG_PATH} --tulis")
        if not args.cek:
            return 2
    elif baris_id_asing:
        print(f"ℹ️ {len(baris_id_asing)} baris punya ID dokumen di sheet yang belum tercatat di audit — "
              "dibuka lewat ID itu, tidak dibuat baru.")
    if args.baris:
        ingin = parse_pilihan_baris(args.baris)
        rows = [r for r in rows if r.baris in ingin]
        tak_ada = sorted(ingin - {r.baris for r in rows})
        if tak_ada:
            print(f"⚠️ Baris {tak_ada} kosong/tidak ada di sheet — diabaikan.")
    if args.dari is not None or args.sampai is not None:
        rows = saring_rentang(rows, args.dari, args.sampai)
        print(f"Rentang baris {args.dari or 2}–{args.sampai or 'akhir'}: {len(rows)} baris.")

    if args.cek:
        return laporan_cek(rows, hasil, args.sumber, semua, mode,
                           lambda siap: len(rencana_sesi(siap, (akun_tunggal or "-") if satu_subsls else "",
                                                         args.baris_per_sesi)),
                           perintah)

    rows_rentang = list(rows)   # sebelum penyaringan, utk menjelaskan kalau hasilnya 0 baris
    ditolak = [r for r in rows if not hasil[r.baris].bisa_diproses]
    if ditolak:
        print(f"{len(ditolak)} baris dilewati karena gagal pemeriksaan data (detail: --cek).")
        if args.baris:
            for r in ditolak:
                print(f"  baris {r.baris}: {hasil[r.baris].status} — {hasil[r.baris].pesan[:200]}")
    rows = [r for r in rows if hasil[r.baris].bisa_diproses]

    def target(row: GabunganRow) -> tuple[str, str]:
        """(akun_login, subsls_input) utk baris ini."""
        return (akun_tunggal, subsls_tunggal) if satu_subsls else (row.akun_ppl, row.idsubsls)

    def dokumen_milik_target(tercatat: tuple, row: GabunganRow) -> bool:
        """Dokumen yang tercatat di audit itu memang milik target run ini?
        --izinkan-wilayah-beda: subsls dipakai bergantian sbg WADAH, jadi yang
        harus sama cuma AKUNNYA (kalau tidak, baris yang dokumennya terlanjur
        tercatat di subsls wadah lain akan dilewati selamanya)."""
        n = 1 if args.izinkan_wilayah_beda else 2
        return tuple(tercatat[:n]) == target(row)[:n]

    # Dokumen yang pernah dibuat utk baris ini dgn akun/subsls LAIN (mis. konfigurasi
    # diganti di tengah jalan) — membuat lagi di sini = duplikat. Lewati & laporkan.
    dokumen = dokumen_per_kunci()
    di_tempat_lain = [r for r in rows if r.kunci in dokumen and not dokumen_milik_target(dokumen[r.kunci], r)]
    if di_tempat_lain:
        print(f"⛔ {len(di_tempat_lain)} baris sudah punya dokumen dgn akun/subsls lain di {AUDIT_LOG_PATH} — dilewati:")
        for r in di_tempat_lain[:10]:
            print(f"  baris {r.baris}: {dokumen[r.kunci][0]} / {dokumen[r.kunci][1]} -> {dokumen[r.kunci][2]}")
        rows = [r for r in rows if r not in di_tempat_lain]

    kunci_akun = None
    if satu_subsls:
        kunci_akun = kunci_proses_akun(akun_tunggal)
        if kunci_akun is None:
            print(f"❌ Akun {akun_tunggal} sedang dipakai proses input lain (lihat file "
                  f"{lokasi.HASIL_INPUT}/.proses_*.lock). Dua proses satu akun saling memutus sesi & memicu "
                  f"DOKUMEN_TANPA_URL_PERLU_CEK palsu — tunggu proses itu selesai, atau pakai akun lain.",
                  file=sys.stderr)
            return 2
        import atexit
        atexit.register(lambda: kunci_akun.unlink(missing_ok=True))

    if args.sinkron_dulu:
        # Harus SEBELUM --lewati-selesai & pengurutan: tanda DRAFT_GALAT_DI_SERVER
        # yang baru ditulis di sini yang menentukan baris mana didahulukan.
        # Sesi pendek sendiri (login -> baca tabel -> logout), lalu batch memakai
        # sesi barunya seperti biasa.
        print("Sinkron tabel server dulu (login sebentar)...")
        with sync_playwright() as p_sink:
            b_sink = p_sink.chromium.launch(headless=False)
            ctx_sink = b_sink.new_context()
            s_sink = FasihWebSession(ctx_sink.new_page(), dump_dom=args.dump_dom)
            try:
                s_sink.login(akun_tunggal or "", FIXED_PASSWORD)
                sinkron_audit_dari_server(s_sink, semua, hasil, args.sumber, akun_tunggal or "",
                                          subsls_tunggal or "", args.assignment_id)
            except Exception as e:
                print(f"⚠️ Sinkron tabel gagal ({e}) — batch lanjut apa adanya.")
            finally:
                try:
                    s_sink.logout()
                except Exception:
                    pass
                ctx_sink.close()
                b_sink.close()

    if args.hanya_galat:
        bertanda = {k for k, st in status_terakhir_per_kunci().items() if st == STATUS_DRAFT_GALAT}
        sebelum = len(rows)
        rows = [r for r in rows if r.kunci in bertanda]
        print(f"--hanya-galat: {len(rows)} baris bertanda galat server dikerjakan "
              f"({sebelum - len(rows)} baris lain dilewati).")
        if not rows:
            print("Tidak ada dokumen bertanda galat di audit. Jalankan dgn --sinkron-dulu "
                  "(atau sinkron_list.py --tulis) supaya tandanya terisi dari tabel server.")

    tuntas_audit: set = set()
    if args.lewati_selesai:
        sudah = status_terakhir_per_kunci()
        tuntas = tuntas_audit = set(STATUS_TERKIRIM if args.submit else STATUS_SELESAI_DRY_RUN)
        if args.coba_terkunci:
            # Dokumen terkunci hanya bisa dibuka admin/PML; sesudah itu baris ini
            # perlu dicoba lagi, dan list server tidak bisa membuktikan sudah dibuka.
            tuntas = tuntas_audit = tuntas - {STATUS_TERKUNCI}
        sebelum = len(rows)
        # --koordinat kirim: DRAFT_TANPA_KOORDINAT tidak lagi dianggap tuntas —
        # justru baris itulah yang mau diselesaikan jadi terkirim.
        rows = [r for r in rows
                if not tuntas_menurut_audit(sudah.get(r.kunci, ""), tuntas,
                                            r.punya_koordinat or kirim_tanpa_koordinat)]
        print(f"--lewati-selesai: {sebelum - len(rows)} baris dilewati (sudah selesai di {AUDIT_LOG_PATH}).")
    # URUTAN KERJA (permintaan user 2026-09-23): bereskan yang sudah ada dulu,
    # dokumen BARU paling belakang.
    #   1. dokumen yang ditandai GALAT oleh server  -> paling mendesak
    #   2. dokumen yang sudah ada tapi belum tuntas -> tinggal dilengkapi & dikirim
    #   3. baris yang belum punya dokumen           -> input baru
    # Tanda galat dibaca dari audit SAAT MULAI; hasil --sinkron-dulu di run yang
    # sama baru berpengaruh pada run berikutnya.
    if not args.urut_sheet:
        bertanda = {k for k, st in status_terakhir_per_kunci().items() if st == STATUS_DRAFT_GALAT}
        punya_dokumen = set(dokumen) | {r.kunci for r in rows if r.id_dokumen}

        def giliran(r: GabunganRow) -> int:
            return 0 if r.kunci in bertanda else 1 if r.kunci in punya_dokumen else 2

        jumlah = Counter(giliran(r) for r in rows)
        if jumlah[0] or jumlah[1]:
            rows.sort(key=lambda r: (giliran(r), r.baris))
            print(f"Urutan kerja: {jumlah[0]} bertanda galat server, {jumlah[1]} dokumen belum tuntas, "
                  f"lalu {jumlah[2]} input baru.")
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        # Dulu cuma satu baris ini — user tidak punya cara tahu BEDA antara
        # "semuanya memang sudah selesai" dan "ada yang tertahan". Sekarang
        # alasannya dihitung dgn aturan yang sama & dirinci di sini.
        print("Tidak ada baris yang perlu diproses.")
        rekap = Counter(a.split(":")[0] for _b, a in kenapa_tidak_dikerjakan(
            rows_rentang, hasil, tuntas_audit, target, _baca_audit(), satu_subsls) if a)
        if rekap:
            print(f"Alasannya, dari {len(rows_rentang)} baris dalam rentang ini:")
            for nama, n in sorted(rekap.items(), key=lambda t: -t[1]):
                print(f"  {n:6d}  {nama}")
            print("Rincian per baris: python input_usaha/rangkum_audit.py --sumber "
                  f"{args.sumber}" + (f" --format {args.format}" if args.format != FORMAT_BAWAAN else "")
                  + (f" --dari {args.dari}" if args.dari else "")
                  + (f" --sampai {args.sampai}" if args.sampai else ""))
        return 0

    dry_run = not args.submit
    n_draft = sum(hasil[r.baris].tanpa_koordinat for r in rows)
    print(mode)
    print(f"{'DRY-RUN' if dry_run else '⚠️ MODE LIVE — akan klik Kirim final'} — {len(rows)} baris"
          + (f" ({n_draft} tanpa koordinat -> hanya disimpan DRAFT, TIDAK dikirim)" if n_draft else "") + ".")
    if not dry_run and len(rows) > n_draft:
        konfirmasi = input(f"Ketik 'YA' utk konfirmasi submit {len(rows) - n_draft} dokumen SUNGGUHAN "
                           "(irreversible): ")
        if konfirmasi.strip().upper() != "YA":
            print("Dibatalkan.")
            return 1

    sesi = rencana_sesi(rows, akun_tunggal, args.baris_per_sesi)
    print(f"Dibagi jadi {len(sesi)} sesi login.")
    # ID dokumen ditulis balik ke kolom "ID Dokumen FASIH" sheet sumber (permintaan
    # user 2026-09-25): nama usaha bisa diubah, ID tidak.
    pencatat_id = PencatatIdSumber(args.sumber, args.format)

    berhenti_segera = set(STATUS_BERHENTI_SEGERA)
    if satu_subsls and not args.paralel:
        # Semua baris memakai subsls & akun yang sama: "+Dokumen Baru" yang
        # tidak ada utk satu baris pasti tidak ada utk baris berikutnya.
        berhenti_segera.add("SKIP_DOKUMEN_BELUM_ADA")
    ulang_sesi = set(STATUS_ULANG_SESI_BARU)
    if args.paralel:
        # Paralel: jumlah dokumen di list ikut dinaikkan batch lain (dgn jeda indeks),
        # jadi "tidak ada dokumen yatim" tidak bisa dibuktikan -> gagal buat TIDAK diulang.
        ulang_sesi.discard("SKIP_DOKUMEN_BELUM_ADA")

    error_beruntun = 0
    # Baris yang dokumennya mungkin terbuat tanpa URL: batch LANJUT, semuanya
    # didaftar di sini lalu dicetak & ditulis ke berkas di akhir run.
    tanpa_url: list[dict] = []
    n_proses = n_lewati = 0  # utk ringkasan akhir: kenapa run berakhir di baris itu

    def harus_berhenti(status: str) -> bool:
        """True kalau batch harus BERHENTI (kejanggalan berulang / error beruntun)."""
        nonlocal error_beruntun
        if status in berhenti_segera:
            print(f"\n⛔ {status} — batch DIHENTIKAN (akan berulang di baris berikutnya). Baca error_message "
                  f"di {AUDIT_LOG_PATH} & log_screenshots/.")
            return True
        gagal = status.startswith("ERROR_") or (args.paralel and status == "SKIP_DOKUMEN_BELUM_ADA")
        error_beruntun = error_beruntun + 1 if gagal else 0
        if args.maks_error_beruntun and error_beruntun >= args.maks_error_beruntun:
            print(f"\n⛔ {error_beruntun} baris ERROR berturut-turut — batch DIHENTIKAN. Periksa VPN, "
                  f"log_screenshots/ & {AUDIT_LOG_PATH}, lalu jalankan ulang dgn --lewati-selesai.")
            return True
        return False

    berhenti = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        for nomor_sesi, (akun, anggota) in enumerate(sesi, start=1):
            if berhenti:
                break
            print(f"\n##### sesi {nomor_sesi}/{len(sesi)} — {akun} — {len(anggota)} baris #####")

            def mulai_sesi():
                """Login dgn pengulangan utk gangguan transien (run 2026-09-14 "Execution context
                was destroyed", 2026-09-15 "Page.goto: Timeout 15000ms" — fasih-web normal lagi
                beberapa detik kemudian). Akun salah TIDAK diulang."""
                for percobaan in range(1, 4):
                    try:
                        return _mulai_sesi_sekali()
                    except Exception as e:
                        if "AKUN" in str(e) or percobaan == 3:
                            raise
                        print(f"⚠️ Login gagal (percobaan {percobaan}/3): {str(e)[:150]} — ulangi 30 dtk lagi.")
                        time.sleep(30)

            def _mulai_sesi_sekali():
                """Context baru = cookie SSO kosong (sesi Keycloak sso.bps.go.id ikut terputus), login &
                verifikasi akun. Melempar exception kalau gagal (context sudah ditutup)."""
                ctx = browser.new_context()
                s = FasihWebSession(ctx.new_page(), dump_dom=args.dump_dom)
                try:
                    s.login(akun, FIXED_PASSWORD)
                    aktif = (s.akun_api.get("email") or "").lower()
                    if satu_subsls and aktif != akun:
                        # Semua dokumen atas nama satu akun: "tidak terbaca" tidak
                        # boleh dianggap aman seperti di alur per baris.
                        raise RuntimeError(f"AKUN TIDAK TERVERIFIKASI: diminta '{akun}', terbaca '{aktif or '-'}'")
                except Exception:
                    try:
                        if not args.paralel:  # lihat tutup_sesi
                            s.logout()
                    except Exception:
                        pass
                    ctx.close()
                    raise
                return ctx, s

            def tutup_sesi(ctx, s):
                if args.paralel:
                    # Run 2026-09-14/15: logout satu proses memutus sesi proses lain yang
                    # memakai akun SAMA. Context baru sudah tanpa cookie, jadi cukup ditutup.
                    ctx.close()
                    return
                try:
                    s.logout()
                except Exception as e:
                    print(f"⚠️ Logout {akun} gagal (tidak fatal): {e}")
                ctx.close()

            try:
                context, sess = mulai_sesi()
            except Exception as e:
                print(f"❌ Login gagal utk {akun}: {e}")
                for row in anggota:
                    akun_login, subsls_input = target(row)
                    res = _hasil_awal(row, subsls_input, akun_login)
                    res["status"] = "ERROR_AKUN_SALAH" if "AKUN" in str(e) else "ERROR_LOGIN"
                    res["error_message"] = str(e)
                    append_audit(res)
                # Satu akun yang gagal login dihitung SATU error, bukan per baris.
                # Mode satu akun: tidak ada akun lain utk dicoba -> berhenti.
                berhenti = satu_subsls or harus_berhenti("ERROR_LOGIN")
                continue

            def proses(row):
                akun_login, subsls_input = target(row)
                tercatat = dokumen_per_kunci().get(row.kunci)
                pernah_dibuat = bool(tercatat) and dokumen_milik_target(tercatat, row)
                url = tercatat[2] if pernah_dibuat else ""
                catatan_id = ""
                if row.id_dokumen and not url:
                    # Audit tidak mengenal dokumen baris ini (mis. nama/kunci diubah di sheet,
                    # atau dibuat PC lain) tapi sheet menyimpan ID-nya -> buka lewat ID itu,
                    # JANGAN dicari lewat nama / dibuat baru.
                    url, pernah_dibuat = url_entry(row.id_dokumen, args.assignment_id), True
                    catatan_id = f"dokumen dibuka lewat ID di sheet ({row.id_dokumen[:8]})"
                elif row.id_dokumen and id_dari_url(url) != row.id_dokumen:
                    catatan_id = (f"ID di sheet ({row.id_dokumen[:8]}) BEDA dgn audit "
                                  f"({id_dari_url(url)[:8]}) — dipakai audit; periksa dokumen ganda")
                    print(f"  ⚠ {catatan_id}")
                res = process_one_row(sess, row, hasil[row.baris], dry_run, args.assignment_id,
                                      subsls_input, akun_login, pernah_dibuat, url,
                                      mode_satu_list=satu_subsls and not args.paralel,
                                      izinkan_wilayah_beda=args.izinkan_wilayah_beda,
                                      kirim_tanpa_koordinat=kirim_tanpa_koordinat,
                                      catat_id=pencatat_id.catat)
                if catatan_id:
                    res["review_disarankan"] = " | ".join(filter(None, [res.get("review_disarankan"), catatan_id]))
                if not sess.akun_api.get("email"):
                    res["review_disarankan"] = " | ".join(filter(None, [
                        res.get("review_disarankan"),
                        "AKUN TIDAK TERVERIFIKASI — cocokkan manual dgn Akun PPL di sheet"]))
                append_audit(res)
                pesan = str(res.get("error_message") or "")
                print(f"  -> {res['status']}" + (f" ({pesan[:300]})" if pesan else ""))
                return res

            sesi_aktif = True
            for row in anggota:
                file_stop = berkas_stop(akun)
                if file_stop:
                    print(f"\n⏹ File {file_stop} ada — batch berhenti rapi SEBELUM baris {row.baris}. "
                          "Hapus file itu sebelum menjalankan ulang.")
                    berhenti = True
                    break
                alasan = alasan_lewati_saat_giliran(row.kunci, target(row), tuntas_audit,
                                                    row.nama_dokumen if satu_subsls else "",
                                                    row.punya_koordinat, id_sheet=row.id_dokumen)
                if alasan:
                    print(f"\n=== baris {row.baris} — dilewati: {alasan} ===")
                    n_lewati += 1
                    if alasan.startswith(TANDA_LEWATI_TANPA_URL):
                        tanpa_url.append(catatan_tanpa_url(
                            tanda_tanpa_url_terakhir(row.kunci)
                            or _hasil_awal(row, target(row)[1], target(row)[0]),
                            TANDA_LEWATI_TANPA_URL))
                    continue
                print(f"\n=== baris {row.baris} — {row.nama_dokumen} ({row['kbli']}) — subsls {target(row)[1]} ===")
                res = proses(row)
                n_proses += 1
                if satu_subsls and res["status"] in ulang_sesi:
                    # Run 2026-09-14: kirim/buat dokumen yang gagal di sesi yang sudah
                    # lama langsung berhasil di sesi baru (baris 22). Dokumen yang sudah
                    # dibuat dibuka lewat URL audit, jadi pengulangan tidak menduplikasi.
                    print(f"  ↻ {res['status']} — login ulang (sesi baru) & ulangi baris {row.baris} sekali.")
                    tutup_sesi(context, sess)
                    sesi_aktif = False
                    try:
                        context, sess = mulai_sesi()
                        sesi_aktif = True
                    except Exception as e:
                        print(f"❌ Login ulang gagal utk {akun}: {e}")
                        berhenti = True
                        break
                    n0 = res.get("_jumlah_awal")
                    ulangi_baris = True
                    if res["status"] == "SKIP_DOKUMEN_BELUM_ADA" and n0 is not None:
                        # Percobaan buat terakhir di sesi lama tidak dicek jumlahnya —
                        # pastikan tidak ada dokumen yatim sebelum membuat lagi.
                        sess.page.wait_for_timeout(30_000)
                        n_kini = sess.jumlah_dokumen_list(args.assignment_id)
                        if n_kini is None or kenaikan_tak_terjelaskan(
                                n0, n_kini, res.get("_waktu_awal", 0.0), row.kunci, akun) != 0:
                            res = {**res, "status": STATUS_TANPA_URL, "error_message": (
                                f"Sebelum mengulang di sesi baru, jumlah dokumen {n0} -> {n_kini}: kemungkinan ada "
                                "dokumen tanpa URL tercatat. Cek DRAFT terbaru di list, catat URL-nya sbg "
                                "DOKUMEN_DIBUAT baris ini di audit, lalu jalankan ulang.")}
                            res["error_message"] += " || " + sebut_dokumen_asing(
                                sess, args.assignment_id, res.get("timestamp", ""))
                            append_audit(res)
                            print(f"  -> {res['status']} ({res['error_message'][:200]})")
                            ulangi_baris = False
                    if ulangi_baris:
                        res = proses(row)
                if res["status"] in STATUS_TANPA_URL_SEMUA:
                    # Permintaan user 2026-09-23: run malam tidak boleh berhenti di sini.
                    # Barisnya dilewati (mengulanginya = dokumen kedua) & dicatat utk
                    # dicek pagi harinya; batch lanjut ke baris berikutnya.
                    tanpa_url.append(catatan_tanpa_url(res))
                    # Yang dihitung cuma kejadian BARU malam ini — tanda sisa run
                    # sebelumnya (yang cuma dilewati) tidak boleh ikut menghentikan.
                    baru_kini = sum(1 for d in tanpa_url if d["sebab"] != TANDA_LEWATI_TANPA_URL)
                    if args.maks_tanpa_url and baru_kini >= args.maks_tanpa_url:
                        print(f"\n⛔ {len(tanpa_url)} baris dgn dokumen tanpa URL — batch DIHENTIKAN "
                              "(kemungkinan 'Buat Dokumen' memang sedang rusak; kalau diteruskan, tiap "
                              "baris menambah dokumen kosong yang cuma admin bisa hapus).")
                        berhenti = True
                        break
                    print(f"  ↷ baris {row.baris} dilewati & dicatat — batch LANJUT "
                          f"({baru_kini}/{args.maks_tanpa_url} sebelum berhenti)."
                          if args.maks_tanpa_url else
                          f"  ↷ baris {row.baris} dilewati & dicatat — batch LANJUT.")
                    continue
                if harus_berhenti(res["status"]):
                    berhenti = True
                    break
            if sesi_aktif:
                tutup_sesi(context, sess)
        browser.close()

    tulis_laporan_tanpa_url(tanpa_url)
    pencatat_id.simpan()   # sisa yang tertunda (mis. Excel sempat membuka sheet)
    print(pencatat_id.ringkasan())
    print(f"\nSelesai. Audit: {AUDIT_LOG_PATH}")
    sisa = len(rows) - n_proses - n_lewati
    print(f"Ringkasan run: {n_proses} baris diproses, {n_lewati} dilewati, {sisa} belum sempat dikerjakan "
          f"(dari {len(rows)} baris dalam rentang ini).")
    if berhenti:
        print("Run BERHENTI di tengah — alasannya tercetak di atas & tersimpan di audit.")
    elif sisa > 0:
        print("Run selesai normal tapi masih ada sisa — biasanya --limit, --hanya-galat, "
              "atau baris-baris itu ada di sesi/akun lain.")
    laporan = ringkas_tanpa_url(tanpa_url)
    if laporan:
        print(laporan)
    return 1 if berhenti else 0


if __name__ == "__main__":
    sys.exit(main())
