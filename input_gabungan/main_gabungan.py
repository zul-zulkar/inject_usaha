#!/usr/bin/env python3
"""
main_gabungan.py — Otomatisasi input dari tab "gabungan" (Google Sheet "Agenda").

Alurnya SAMA dgn main.py (baca docstring di sana utk latar belakang
keselamatan). Bedanya sumber data: sheet gabungan sudah berisi jawaban final
per rincian (lihat gabungan_loader.py), jadi tidak ada file export fasih-sm,
tidak ada kalkulasi 10%, dan tidak ada kolom No — tiap baris dikenali lewat
nomor baris sheet (--baris) & `kunci` (hash akun+idsubsls+nama) di audit.

⚠️ VPN kantor wajib aktif. ⚠️ Headless dilarang (fasih-web membalas dgn
halaman anti-bot).

MODE SATU SUBSLS + SATU AKUN (default sejak 2026-09-14)
======================================================
Sebagian subsls sudah ditandai selesai & tidak bisa ditambah assignment, jadi
SEMUA dokumen dibuat di SATU subsls (--subsls-tunggal / config
GABUNGAN_SUBSLS_TUNGGAL) oleh SATU akun PPL (--akun-tunggal /
GABUNGAN_AKUN_TUNGGAL). Wilayah asli tiap baris tetap dicatat di kolom
`idsubsls` audit, bersama `dokumen_url` — bahan utk ubah alokasi wilayah
nanti. Yang DICEK LANGSUNG saat input:
  - akun yang login WAJIB terverifikasi = akun tunggal, kalau tidak batch berhenti;
  - subsls tidak bisa dipilih / "+Dokumen Baru" tidak ada -> batch BERHENTI di
    baris pertama (semua baris memakai subsls yang sama);
  - tiap dokumen yang dibuka dibaca wilayah BLOK I-nya: beda dgn subsls
    tujuan -> batch BERHENTI; tidak terbaca -> diisi tapi TIDAK dikirim.
Alur lama (subsls & akun per baris sheet): --per-baris.

LANGKAH
=======
1. Download tab "gabungan": File > Download > Microsoft Excel (.xlsx).

2. Periksa TANPA browser (2 detik) — daftar lengkap per baris ditulis ke
   cek_gabungan.csv utk diperbaiki di sheet:
       python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --cek

3. Dry-run SATU baris dulu, tinjau hasilnya di browser:
       python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --baris 2

4. Dry-run bertahap (batch terputus bisa dilanjutkan):
       python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --lewati-selesai --limit 10

5. Kirim HANYA baris yang sudah ditinjau (irreversible, wajib ketik YA):
       python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --baris 2,3,4 --submit

Audit: audit_log_gabungan.csv (terpisah dari audit_log.csv backlog lama).
Baris yang gagal pemeriksaan offline TIDAK pernah dibuka di browser.

PENAMAAN USAHA: nama dokumen, SE2026-P & 8b diketik sbg "<nama> (<12a>)"
(GabunganRow.nama_dokumen / .nama_komersial). Dokumen lama yang terlanjur
dibuat dgn nama mentah sheet tidak dibuatkan duplikat -> SKIP_DOKUMEN_NAMA_LAMA.
"""

from __future__ import annotations

import argparse
import csv as csv_module
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
    GABUNGAN_SUBSLS_TUNGGAL, WILAYAH_BY_IDSUBSLS,
)
from inti.fasih_web import DokumenNamaLamaAda, FasihWebSession, FieldNotFound
from inti.fill_blok2 import fill_catatan, fill_keterangan_pemberi_jawaban
from input_gabungan.fill_gabungan import BarisPerluManual, fill_blok2_gabungan
from inti.gabungan_loader import (
    GabunganRow, Pemeriksaan, cocokkan_wilayah_dokumen, kelompok_per_akun, load_gabungan,
    parse_pilihan_baris, periksa_semua,
)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

AUDIT_LOG_PATH = Path("./audit_log_gabungan.csv")
# idsubsls = wilayah ASLI baris (tujuan ubah alokasi nanti); idsubsls_input =
# subsls tempat dokumen benar-benar dibuat; akun_login = akun yang membuatnya.
AUDIT_FIELDS = [
    "timestamp", "baris", "kunci", "nama_usaha", "kbli", "idsubsls", "idsubsls_input", "akun_ppl",
    "akun_login", "status", "galat", "peringatan", "kosong", "catatan_count", "review_disarankan",
    "wilayah_dokumen", "dokumen_url", "error_message",
]
CEK_PATH = Path("./cek_gabungan.csv")
MENIT_PER_BARIS = 1.7  # ukuran nyata batch backlog lama, termasuk ganti akun

# Dokumen yang ternyata sudah terkunci (dikirim di luar skrip) ikut dianggap
# tuntas oleh --lewati-selesai: mengisinya ulang pasti gagal.
STATUS_TERKUNCI = "DOKUMEN_TERKUNCI"
STATUS_TERKIRIM = {"TERKIRIM_TERVERIFIKASI", "TERKIRIM_BELUM_TERVERIFIKASI", STATUS_TERKUNCI}
STATUS_SELESAI_DRY_RUN = STATUS_TERKIRIM | {"DRY_RUN_SIAP_KIRIM"}
# Ditulis SEGERA setelah dokumen baru terbuat (sebelum diisi), supaya proses
# yang mati di tengah tidak berujung dokumen duplikat pada run berikutnya.
STATUS_DIBUAT = "DOKUMEN_DIBUAT"
# Dokumen tercatat sudah DIHAPUS admin (dibuktikan list API, lihat sinkron_list.py):
# catatan dokumen kunci itu sebelum baris ini gugur -> baris dibuatkan dokumen baru.
STATUS_DIHAPUS = "DOKUMEN_DIHAPUS"
# Kejanggalan yang pasti berulang di baris berikutnya -> hentikan batch.
# SUBMIT_GAGAL ikut: jalur kirim yang tidak bekerja (run 2026-09-14 baris 4)
# pasti berulang di semua baris & tidak boleh lolos diam-diam.
STATUS_BERHENTI_SEGERA = {"STOP_SUBSLS_TIDAK_BISA_DIPILIH", "STOP_WILAYAH_DOKUMEN_BEDA", "STOP_DOKUMEN_TANPA_URL",
                          "SUBMIT_GAGAL"}
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
    STOP_DOKUMEN_TANPA_URL palsu. Paralel = akun BERBEDA per proses."""
    path = Path(".proses_" + re.sub(r"[^a-z0-9]+", "_", akun.lower()) + ".lock")
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


def status_terakhir_per_kunci() -> dict:
    """{kunci: status} dari audit, baris TERAKHIR yang menang. Pakai kunci,
    BUKAN nomor baris — nomor baris bergeser kalau sheet diurutkan/disisipi."""
    return {b["kunci"]: (b.get("status") or "").strip() for b in _baca_audit() if b.get("kunci")}


def dokumen_per_kunci() -> dict:
    """{kunci: (akun_login, idsubsls_input, dokumen_url)} utk baris yang
    dokumennya PERNAH dibuat/dibuka (URL bisa "" kalau terbuat tanpa URL
    tertangkap). Dipakai membuka dokumen lewat URL (list satu akun berhalaman
    ratusan dokumen) & mencegah dokumen kedua dibuat utk baris yang sama."""
    out: dict = {}
    for b in _baca_audit():
        kunci, url = b.get("kunci"), b.get("dokumen_url") or ""
        if kunci and b.get("status") == STATUS_DIHAPUS:
            out.pop(kunci, None)  # dokumen lama sudah tidak ada -> boleh dibuat baru
            continue
        if not kunci or not (url or b.get("status") == STATUS_DIBUAT):
            continue
        lama = out.get(kunci)
        out[kunci] = ((b.get("akun_login") or "").lower(), b.get("idsubsls_input") or "",
                      url or (lama[2] if lama else ""))
    return out


def kunci_lain_bernama_sama(nama_dokumen: str, kunci: str, akun: str = "") -> str:
    """Kunci baris LAIN yang dokumennya (akun `akun` kalau diisi) tercatat dgn nama dokumen
    yang sama persis, "" kalau tidak ada. Run 2026-09-15: Agenda2 baris 267 &
    Agenda baris 108 = dua usaha BERBEDA bernama "PANGKALAN GAS (NYOMAN SHUARJANA)".
    create_document mencari nama di list -> akan membuka dokumen baris 108 (terkirim)
    & baris 267 salah dianggap tuntas (DOKUMEN_TERKUNCI)."""
    n = " ".join((nama_dokumen or "").split()).upper()
    milik = dokumen_per_kunci()
    for b in _baca_audit():
        k = b.get("kunci")
        if (k and k != kunci and k in milik and (not akun or milik[k][0] == akun.lower())
                and " ".join((b.get("nama_usaha") or "").split()).upper() == n):
            return k
    return ""


def alasan_lewati_saat_giliran(kunci: str, target: tuple[str, str], tuntas: set, nama_dokumen: str = "") -> str:
    """Audit dibaca ULANG tepat sebelum baris dikerjakan (daftar awal dihitung saat
    start). Batch lain (akun lain) bisa sudah membuat/mengirim dokumen baris ini
    selama batch ini berjalan -> membuatnya lagi di sini = duplikat. "" = kerjakan."""
    tercatat = dokumen_per_kunci().get(kunci)
    if tercatat and tercatat[:2] != target:
        return f"dokumennya sudah dibuat proses lain ({tercatat[0]} / {tercatat[1]})"
    if tuntas and status_terakhir_per_kunci().get(kunci) in tuntas:
        return "sudah selesai di audit (dikerjakan proses lain)"
    if nama_dokumen and not tercatat:
        lain = kunci_lain_bernama_sama(nama_dokumen, kunci, target[0])
        if lain:
            return (f"SKIP_NAMA_DIPAKAI_BARIS_LAIN: '{nama_dokumen}' sudah jadi nama dokumen baris lain "
                    f"(kunci {lain}) di list akun ini — bedakan nama di sheet (atau KOREKSI_NAMA)")
    return ""


def berkas_stop(akun: str) -> str:
    """Nama file penghenti yang ada ("" = tidak ada). `STOP_GABUNGAN` menghentikan
    semua batch; `STOP_<akun>` hanya batch akun itu. Dicek di ANTARA baris, jadi
    tidak pernah memotong pengisian/kirim."""
    for nama in ("STOP_GABUNGAN", f"STOP_{akun}" if akun else ""):
        if nama and Path(nama).exists():
            return nama
    return ""


def _hasil_awal(row: GabunganRow, subsls_input: str, akun_login: str) -> dict:
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "baris": row.baris, "kunci": row.kunci,
        "nama_usaha": row.nama_dokumen, "kbli": row["kbli"], "idsubsls": row.idsubsls,
        "idsubsls_input": subsls_input, "akun_ppl": row.akun_ppl, "akun_login": akun_login,
        "status": "GAGAL",
    }


def process_one_row(sess: FasihWebSession, row: GabunganRow, cek: Pemeriksaan, dry_run: bool,
                    assignment_id: str, subsls_input: str, akun_login: str,
                    pernah_dibuat: bool = False, url_audit: str = "", mode_satu_list: bool = False) -> dict:
    """`subsls_input` = subsls tempat dokumen dibuat (mode satu subsls: sama
    utk semua baris). `pernah_dibuat` = audit mencatat dokumen baris ini dgn
    akun & subsls yang sama -> TIDAK PERNAH dibuat ulang; dibuka lewat
    `url_audit` kalau ada, kalau tidak dicari di list."""
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
                                              nama_lama=row.nama)
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
                    if lebih is not None and lebih > 0:
                        result["status"] = "STOP_DOKUMEN_TANPA_URL"
                        result["error_message"] = (
                            f"'Buat Dokumen' tampak gagal tapi jumlah dokumen naik {n_awal} -> {n_akhir} "
                            f"({lebih} tidak terjelaskan oleh DOKUMEN_DIBUAT baris lain): kemungkinan ada dokumen "
                            "tanpa URL tercatat. Cari DRAFT terbaru di list, catat URL-nya sbg DOKUMEN_DIBUAT "
                            "baris ini di audit, lalu jalankan ulang.")
                        _tulis_tanda()
                        return result
                    if lebih is not None and lebih <= 0:
                        sess._log(f"Jumlah dokumen {n_awal} -> {n_akhir}, semua terjelaskan — aman diulang sekali.")
                        dibuat = sess.create_document(assignment_id, subsls_input, row.nama_dokumen,
                                                      nama_lama=row.nama)
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
            if sess.dokumen_dibuat and not dokumen_baru and not getattr(sess, "nama_di_modal", True):
                # Dokumen baru tanpa nama & tanpa URL tidak bisa dicari di list —
                # lanjut ke baris lain hanya menumpuk dokumen kosong yatim.
                result["status"] = "STOP_DOKUMEN_TANPA_URL"
                result["error_message"] = (
                    "Dokumen baru terbuat tapi tidak terbuka otomatis & modal tidak punya field nama — "
                    "URL-nya tidak diketahui. Cari dokumen DRAFT BLANK terbaru di list, catat URL-nya "
                    "sbg DOKUMEN_DIBUAT utk baris ini di audit, lalu jalankan ulang.")
                _tulis_tanda()
                return result
            if not dokumen_baru:
                tanda.append("dokumen SUDAH ADA sebelumnya (diisi ulang)")
            sess.open_entry_for(row.nama_dokumen, assignment_id, allow_retry_if_fresh=dokumen_baru)
        if "/entry" in sess.page.url:
            result["dokumen_url"] = sess.page.url

        # 2. PENGANTAR -> IDENTITAS WILAYAH -> SE2026 - P (form-engine hanya
        #    merender section aktif; lihat CLAUDE.md).
        sess.fill_pengantar()
        if not sess.next_section():
            raise FieldNotFound(f"Section setelah PENGANTAR tidak ter-enable. Tersedia: {sess.list_sections()}")

        # CEK LANGSUNG: dokumen ini benar-benar ada di subsls tujuan input?
        # Dibaca dari rincian 1-6 BLOK I (prefilled dari wilayah dokumen).
        status_w, pesan_w = cocokkan_wilayah_dokumen(
            sess.baca_wilayah_dokumen(), subsls_input, WILAYAH_BY_IDSUBSLS.get(subsls_input))
        result["wilayah_dokumen"] = f"{status_w}: {pesan_w}"
        if status_w == "BEDA":
            result["status"] = "STOP_WILAYAH_DOKUMEN_BEDA"
            result["error_message"] = pesan_w
            sess._shot(f"WILAYAH_BEDA_gabungan_{row.baris}")
            _tulis_tanda()
            return result
        wilayah_terverifikasi = status_w == "COCOK"
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
                           blok_nomor=row["nomor_domisili"] or "-")
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
        if ring.galat > 0:
            detail = sess.read_galat_detail()
            if "Nomor Urut Bangunan" in detail and detail.count("\n") <= 3:
                sess._log(f"Nomor Urut Bangunan di sheet = '{row['no_bang']}' (pembanding saja, tidak dipakai).")
                sess.close_ringkasan_dialog()
                sess.fix_nomor_urut_bangunan_if_needed()
                sess.save()
                ring = sess.check_ringkasan()
            else:
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


def laporan_cek(rows: list[GabunganRow], hasil: dict[int, Pemeriksaan], sumber: str,
                semua: list[GabunganRow], mode: str, n_sesi) -> int:
    """Cetak ringkasan pemeriksaan `rows` (pilihan --baris) + tulis rincian
    SELURUH sheet (`semua`) ke CSV — supaya file itu selalu lengkap utk
    dipakai memperbaiki sheet, apa pun pilihan --baris-nya."""
    siap = [r for r in rows if hasil[r.baris].status == "SIAP"]
    print(f"=== PEMERIKSAAN: {len(rows)} baris dari {sumber} — {mode} ===\n")
    for status, n in Counter(hasil[r.baris].status for r in rows).most_common():
        print(f"  {'OK ' if status == 'SIAP' else '!! '}{n:4d}  {status}")

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

    with CEK_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv_module.writer(f)
        w.writerow(["baris", "kunci", "akun_ppl", "idsubsls", "nama", "nama_dokumen", "status", "masalah", "tanda"])
        for r in semua:
            h = hasil[r.baris]
            w.writerow([r.baris, r.kunci, r.akun_ppl, r.idsubsls, r.nama, r.nama_dokumen, h.status, h.pesan,
                        " | ".join(h.tanda)])
    print(f"\nRincian per baris: {CEK_PATH} (buka di Excel/Sheets, filter kolom status).")

    if siap:
        jam = len(siap) * MENIT_PER_BARIS / 60
        print(f"\n{len(siap)} baris SIAP, {n_sesi(siap)} sesi login, estimasi ±{jam:.1f} jam VPN nonstop.")
        print("Perintah berikutnya (dry-run SATU baris, TIDAK mengirim):")
        print(f"  python input_gabungan/main_gabungan.py --sumber {sumber} --baris {siap[0].baris}")
    return 0 if len(siap) == len(rows) else 1


def main():
    ap = argparse.ArgumentParser(description="Otomatisasi input SE2026 dari sheet gabungan")
    ap.add_argument("--sumber", required=True, help="File .xlsx (tab 'gabungan') atau .csv hasil download sheet")
    ap.add_argument("--cek", action="store_true", help="Hanya periksa data (tanpa browser/VPN), tulis cek_gabungan.csv")
    ap.add_argument("--submit", action="store_true", help="Mode LIVE — benar2 klik Kirim. Default: dry-run.")
    ap.add_argument("--headless", action="store_true", help="JANGAN DIPAKAI — ditolak (lihat main.py).")
    ap.add_argument("--baris", default=None, help="Nomor baris sheet, mis. 2,5,10-20")
    ap.add_argument("--limit", type=int, default=None, help="Batasi jumlah baris diproses")
    ap.add_argument("--lewati-selesai", action="store_true",
                    help="Lewati baris yang sudah selesai di audit_log_gabungan.csv (dicocokkan lewat kunci)")
    ap.add_argument("--assignment-id", default=ASSIGNMENT_ID_GABUNGAN,
                    help="Segmen URL list PENDATAAN /survey/{SURVEY_ID}/{ini} (default: config)")
    ap.add_argument("--subsls-tunggal", default=GABUNGAN_SUBSLS_TUNGGAL,
                    help="idsubsls 16 digit tempat SEMUA dokumen dibuat (default: config GABUNGAN_SUBSLS_TUNGGAL)")
    ap.add_argument("--akun-tunggal", default=GABUNGAN_AKUN_TUNGGAL,
                    help="Email akun PPL yang membuat SEMUA dokumen (default: config GABUNGAN_AKUN_TUNGGAL)")
    ap.add_argument("--baris-per-sesi", type=int, default=GABUNGAN_BARIS_PER_SESI,
                    help="Mode satu akun: login ulang tiap N baris (default: config)")
    ap.add_argument("--paralel", action="store_true",
                    help="Dijalankan bersamaan dgn batch lain (rentang --baris TIDAK BOLEH tumpang tindih): "
                         "gagal buat dokumen TIDAK diulang (hindari duplikat), dikerjakan pass tunggal sesudahnya")
    ap.add_argument("--per-baris", action="store_true",
                    help="Alur LAMA: dokumen dibuat di idsubsls baris oleh akun PPL baris")
    ap.add_argument("--maks-error-beruntun", type=int, default=3,
                    help="Hentikan batch setelah N baris ERROR_* berturut-turut (mis. VPN putus). 0 = jangan berhenti.")
    ap.add_argument("--dump-dom", action="store_true", help="Simpan peta dataKey tiap section ke log_screenshots/")
    args = ap.parse_args()

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
    if satu_subsls and not args.cek and not (re.fullmatch(r"\d{16}", subsls_tunggal) and "@" in akun_tunggal):
        print("❌ Mode satu subsls butuh --subsls-tunggal (16 digit) DAN --akun-tunggal (email PPL), atau isi "
              "GABUNGAN_SUBSLS_TUNGGAL/GABUNGAN_AKUN_TUNGGAL di inti/config.py. Alur lama: --per-baris.",
              file=sys.stderr)
        return 2

    rows = semua = load_gabungan(args.sumber)
    hasil = periksa_semua(rows, mode_satu_subsls=satu_subsls)  # lintas-baris -> selalu atas SELURUH sheet
    if args.baris:
        ingin = parse_pilihan_baris(args.baris)
        rows = [r for r in rows if r.baris in ingin]
        tak_ada = sorted(ingin - {r.baris for r in rows})
        if tak_ada:
            print(f"⚠️ Baris {tak_ada} kosong/tidak ada di sheet — diabaikan.")

    if args.cek:
        return laporan_cek(rows, hasil, args.sumber, semua, mode,
                           lambda siap: len(rencana_sesi(siap, (akun_tunggal or "-") if satu_subsls else "",
                                                         args.baris_per_sesi)))

    ditolak = [r for r in rows if hasil[r.baris].status != "SIAP"]
    if ditolak:
        print(f"{len(ditolak)} baris dilewati karena gagal pemeriksaan data (detail: --cek).")
        if args.baris:
            for r in ditolak:
                print(f"  baris {r.baris}: {hasil[r.baris].status} — {hasil[r.baris].pesan[:200]}")
    rows = [r for r in rows if hasil[r.baris].status == "SIAP"]

    def target(row: GabunganRow) -> tuple[str, str]:
        """(akun_login, subsls_input) utk baris ini."""
        return (akun_tunggal, subsls_tunggal) if satu_subsls else (row.akun_ppl, row.idsubsls)

    # Dokumen yang pernah dibuat utk baris ini dgn akun/subsls LAIN (mis. konfigurasi
    # diganti di tengah jalan) — membuat lagi di sini = duplikat. Lewati & laporkan.
    dokumen = dokumen_per_kunci()
    di_tempat_lain = [r for r in rows if r.kunci in dokumen and dokumen[r.kunci][:2] != target(r)]
    if di_tempat_lain:
        print(f"⛔ {len(di_tempat_lain)} baris sudah punya dokumen dgn akun/subsls lain di {AUDIT_LOG_PATH} — dilewati:")
        for r in di_tempat_lain[:10]:
            print(f"  baris {r.baris}: {dokumen[r.kunci][0]} / {dokumen[r.kunci][1]} -> {dokumen[r.kunci][2]}")
        rows = [r for r in rows if r not in di_tempat_lain]

    tuntas_audit: set = set()
    if args.lewati_selesai:
        sudah = status_terakhir_per_kunci()
        tuntas = tuntas_audit = set(STATUS_TERKIRIM if args.submit else STATUS_SELESAI_DRY_RUN)
        sebelum = len(rows)
        rows = [r for r in rows if sudah.get(r.kunci) not in tuntas]
        print(f"--lewati-selesai: {sebelum - len(rows)} baris dilewati (sudah selesai di {AUDIT_LOG_PATH}).")
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("Tidak ada baris yang perlu diproses.")
        return 0

    kunci_akun = None
    if satu_subsls:
        kunci_akun = kunci_proses_akun(akun_tunggal)
        if kunci_akun is None:
            print(f"❌ Akun {akun_tunggal} sedang dipakai proses main_gabungan lain (lihat file "
                  f".proses_*.lock). Dua proses satu akun saling memutus sesi & memicu "
                  f"STOP_DOKUMEN_TANPA_URL palsu — tunggu proses itu selesai, atau pakai akun lain.",
                  file=sys.stderr)
            return 2
        import atexit
        atexit.register(lambda: kunci_akun.unlink(missing_ok=True))

    dry_run = not args.submit
    print(mode)
    print(f"{'DRY-RUN' if dry_run else '⚠️ MODE LIVE — akan klik Kirim final'} — {len(rows)} baris.")
    if not dry_run:
        konfirmasi = input(f"Ketik 'YA' utk konfirmasi submit {len(rows)} dokumen SUNGGUHAN (irreversible): ")
        if konfirmasi.strip().upper() != "YA":
            print("Dibatalkan.")
            return 1

    sesi = rencana_sesi(rows, akun_tunggal, args.baris_per_sesi)
    print(f"Dibagi jadi {len(sesi)} sesi login.")

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
                """Context baru = cookie SSO kosong (CLAUDE.md -> Pergantian akun), login &
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
                pernah_dibuat = bool(tercatat) and tercatat[:2] == (akun_login, subsls_input)
                res = process_one_row(sess, row, hasil[row.baris], dry_run, args.assignment_id,
                                      subsls_input, akun_login, pernah_dibuat,
                                      tercatat[2] if pernah_dibuat else "", mode_satu_list=satu_subsls and not args.paralel)
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
                                                    row.nama_dokumen if satu_subsls else "")
                if alasan:
                    print(f"\n=== baris {row.baris} — dilewati: {alasan} ===")
                    continue
                print(f"\n=== baris {row.baris} — {row.nama_dokumen} ({row['kbli']}) — subsls {target(row)[1]} ===")
                res = proses(row)
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
                    if res["status"] == "SKIP_DOKUMEN_BELUM_ADA" and n0 is not None:
                        # Percobaan buat terakhir di sesi lama tidak dicek jumlahnya —
                        # pastikan tidak ada dokumen yatim sebelum membuat lagi.
                        sess.page.wait_for_timeout(30_000)
                        n_kini = sess.jumlah_dokumen_list(args.assignment_id)
                        if n_kini is None or kenaikan_tak_terjelaskan(
                                n0, n_kini, res.get("_waktu_awal", 0.0), row.kunci, akun) != 0:
                            res = {**res, "status": "STOP_DOKUMEN_TANPA_URL", "error_message": (
                                f"Sebelum mengulang di sesi baru, jumlah dokumen {n0} -> {n_kini}: kemungkinan ada "
                                "dokumen tanpa URL tercatat. Cek DRAFT terbaru di list, catat URL-nya sbg "
                                "DOKUMEN_DIBUAT baris ini di audit, lalu jalankan ulang.")}
                            append_audit(res)
                            print(f"  -> {res['status']} ({res['error_message'][:200]})")
                            harus_berhenti(res["status"])
                            berhenti = True
                            break
                    res = proses(row)
                if harus_berhenti(res["status"]):
                    berhenti = True
                    break
            if sesi_aktif:
                tutup_sesi(context, sess)
        browser.close()

    print(f"\nSelesai. Audit: {AUDIT_LOG_PATH}")
    return 1 if berhenti else 0


if __name__ == "__main__":
    sys.exit(main())
