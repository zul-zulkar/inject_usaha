"""Kunci antar-PROSES berbasis berkas (O_EXCL), dipakai bersama semua alat.

- `KunciBerkas(path)`: kunci SINGKAT selama menulis satu berkas bersama (audit input,
  audit approve), supaya beberapa bot yang jalan bersamaan di satu PC bergantian menulis,
  bukan saling menimpa baris.
- `kunci_proses_akun(akun)`: satu akun fasih-web = satu proses di PC ini, APA PUN alatnya
  (input_usaha, sinkron_list, approve_pml). Berkasnya satu tempat utk semua alat
  (`input_usaha/hasil/.proses_<akun>.lock`), jadi akun yang sedang dipakai bot input juga
  ditolak bot approval & sebaliknya.

Dulu (sampai 2026-09-27) hanya ada di input_usaha/mesin.py; bot approval belum punya
keduanya, padahal user menjalankan approval bersamaan dgn beberapa bot input."""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from inti import lokasi


class KunciBerkas:
    """Kunci tulis `path` (berkas `<path>.lock`, dibuat O_EXCL). Kunci basi (> `basi_dtk`,
    proses pemegangnya mati di tengah jalan) dibuang. Menunggu lebih dari `tunggu_dtk`
    -> RuntimeError (lebih baik gagal jelas daripada menulis tanpa kunci)."""

    def __init__(self, path: str | Path, tunggu_dtk: float = 60, basi_dtk: float = 60):
        self.target = Path(path)
        self.tunggu_dtk = tunggu_dtk
        self.basi_dtk = basi_dtk

    def __enter__(self):
        self.path = lokasi.siapkan(self.target.with_name(self.target.name + ".lock"))
        batas = time.time() + self.tunggu_dtk
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.basi_dtk:
                        self.path.unlink()
                        continue
                except OSError:
                    pass
                if time.time() > batas:
                    raise RuntimeError(f"Berkas terkunci > {self.tunggu_dtk:g} dtk: {self.path}")
                time.sleep(0.1)

    def __exit__(self, *exc):
        os.close(self.fd)
        try:
            self.path.unlink()
        except OSError:
            pass


def pid_hidup(pid: int) -> bool:
    """Proses `pid` masih berjalan? (os.kill(pid, 0) di Windows justru MEMBUNUH
    proses, jadi pakai OpenProcess/GetExitCodeProcess.)"""
    if pid <= 0:
        return False
    if os.name == "nt":
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
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def jalur_kunci_akun(akun: str) -> Path:
    return lokasi.HASIL_INPUT / (".proses_" + re.sub(r"[^a-z0-9]+", "_", akun.lower()) + ".lock")


def pemegang_kunci_akun(akun: str) -> str:
    """Isi berkas kunci akun ("<PID> <waktu> <perintah>") utk pesan penolakan; "" = tidak ada."""
    try:
        return jalur_kunci_akun(akun).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def kunci_proses_akun(akun: str) -> Path | None:
    """Klaim akun ini utk proses sekarang. None = sudah dipakai proses lain yang MASIH hidup.
    Run 2026-09-14: dua proses (Agenda.xlsx & Agenda1-1.xlsx) memakai akun ppl.kedua
    bersamaan -> logout proses satu memutus sesi proses lain (halaman login di tengah
    'Buat Dokumen') & jumlah dokumen yang dinaikkan proses lain memicu
    DOKUMEN_TANPA_URL_PERLU_CEK palsu. Paralel = akun BERBEDA per proses."""
    path = lokasi.siapkan(jalur_kunci_akun(akun))
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="utf-8").split()[0])
            except (OSError, ValueError, IndexError):
                pid = 0
            if pid != os.getpid() and pid_hidup(pid):
                return None
            try:
                path.unlink()  # basi: prosesnya sudah mati
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv)}\n")
        return path
    return None
