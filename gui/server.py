#!/usr/bin/env python3
"""
server.py — GUI web lokal utk seluruh alat proyek ini (tanpa paket tambahan).

    python gui/server.py            (atau klik dua kali gui/buka_gui.bat)

Membuka http://127.0.0.1:8765 di browser. GUI hanya MENYUSUN & MENJALANKAN perintah yang sama
dgn terminal (gui/alat.py); tidak ada kode lama yang diubah. Tutorial: gui/README.md.

Keamanan:
  * hanya mendengar di 127.0.0.1; setiap panggilan /api wajib membawa token acak per-sesi
    (header X-Token) & Host localhost -> halaman web lain tidak bisa menyuruh GUI menjalankan alat.
  * password SSO hanya di memori proses ini, diteruskan ke alat lewat variabel lingkungan
    FASIH_PASSWORD; tidak pernah ditulis ke disk, tidak pernah dikirim balik ke browser.
  * Kirim/Approve: prompt 'Ketik YA' dari skrip diteruskan ke dialog GUI; jawaban YA harus
    DIKETIK pengguna. otomatis.py (yang mengetik YA sendiri) baru dijalankan sesudah pengguna
    mengetik YA di GUI.
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

GUI = Path(__file__).resolve().parent
AKAR = GUI.parent
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from gui import alat as A  # noqa: E402
from gui import berkas_tabel as T  # noqa: E402

WEB = GUI / "web"
SISIP = GUI / "sisip"
HASIL = GUI / "hasil"
LOG = HASIL / "log"
SNAPSHOT = HASIL / "proses"
PENGATURAN_PATH = GUI / "pengaturan.json"
# Isian formulir terakhir = milik PC ini (memuat akun yang dipakai PC ini) -> di hasil/, yang tidak pernah
# ikut git maupun zip bungkus_pc, supaya PC lain tidak mewarisi akun yang sama.
ISIAN_PATH = HASIL / "isian_terakhir.json"
PORT_BAWAAN = 8765
NAMA_APL = "inject-usaha-gui"
WINDOWS = os.name == "nt"

EKSTENSI_BUKA = {".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".md", ".json", ".zip", ".log", ".pdf", ".png", ".jpg"}
EKSTENSI_BACA = {".js", ".txt", ".md", ".csv", ".json", ".log"}
NAMA_GABUNG = {"KODEPOS_BY_DESA", "KODEPOS_BY_IDSUBSLS", "WILAYAH_BY_IDSUBSLS"}
POLA_UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
VALIDASI_KHUSUS = {
    "KODE_KAB": (r"^\d{4}$", "4 digit (2 provinsi + 2 kab/kota)"),
    "GABUNGAN_SUBSLS_TUNGGAL": (r"^(\d{16})?$", "kosong atau 16 digit"),
    "GABUNGAN_AKUN_TUNGGAL": (r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$", "kosong atau email"),
    "SURVEY_ID": (POLA_UUID, "UUID dari URL fasih-web"),
    "ASSIGNMENT_ID_GABUNGAN": (POLA_UUID, "UUID dari URL list PENDATAAN"),
}


def sekarang() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def relatif(p: str | Path) -> str:
    """Path di dalam proyek -> relatif (garis miring /), di luar -> absolut apa adanya."""
    try:
        return Path(p).resolve().relative_to(AKAR).as_posix()
    except ValueError:
        return str(p)


def mutlak(p: str | Path, dasar: Path = AKAR) -> Path:
    p = Path(str(p).strip().strip('"'))
    return p if p.is_absolute() else (dasar / p)


# ============================================================================ pengaturan
class Pengaturan:
    """gui/pengaturan.json (TIDAK ikut git): timpaan config + pengaturan aplikasi. Tanpa password."""

    def __init__(self, path: Path):
        self.path = path
        self.kunci = threading.RLock()
        self.peringatan = ""
        self.data = self._muat()

    @staticmethod
    def kosong() -> dict:
        return {"versi": 1, "pakai_config_lokal": True, "timpa": {}, "tambah": {},
                "gui": {"kbli_folder": "", "epapi_folder": ""}}

    def _muat(self) -> dict:
        data = self.kosong()
        if not self.path.exists():
            return data
        try:
            isi = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            cadangan = self.path.with_name(f"{self.path.name}.rusak-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(self.path, cadangan)
            self.peringatan = f"pengaturan.json rusak ({e}); disalin ke {cadangan.name}, GUI memakai pengaturan kosong."
            return data
        for k in ("pakai_config_lokal", "timpa", "tambah"):
            if k in isi:
                data[k] = isi[k]
        data["gui"].update({k: v for k, v in (isi.get("gui") or {}).items() if k != "isian"})
        return data

    def simpan(self) -> None:
        with self.kunci:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)

    def untuk_alat(self) -> dict:
        with self.kunci:
            return {"timpa": self.data["timpa"], "tambah": self.data["tambah"]}


PENG = Pengaturan(PENGATURAN_PATH)
SESI = {"password": ""}
KUNCI_SESI = threading.Lock()


class Config:
    """Cache hasil `gui/bantu.py config` (nilai bawaan config.py + config_lokal.py)."""

    def __init__(self):
        self.data: dict = {}
        self.per_nama: dict = {}
        self.kunci = threading.Lock()

    def segarkan(self) -> dict:
        hasil = jalankan_bantu(["config"])
        with self.kunci:
            self.data = hasil
            self.per_nama = {x["nama"]: x for x in hasil.get("pengaturan", [])}
        return hasil

    def item(self, nama: str) -> dict | None:
        if not self.per_nama:
            self.segarkan()
        return self.per_nama.get(nama)


CONFIG = Config()


def jalankan_bantu(argumen: list[str], env_alat: bool = False, timeout: int = 120) -> dict:
    env = siapkan_env(snapshot=None) if env_alat else {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, str(GUI / "bantu.py"), *argumen], cwd=AKAR, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)
    try:
        hasil = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"galat": (p.stderr or p.stdout or "bantu.py tidak memberi keluaran").strip()[-2000:]}
    return hasil


def _nilai(v):
    if isinstance(v, dict) and set(v) == {"__py__"}:
        import ast
        return ast.literal_eval(v["__py__"])
    return v


def efektif(nama: str):
    """Nilai config yang BERLAKU utk alat yang dijalankan GUI: timpaan GUI > config_lokal > config.py."""
    with PENG.kunci:
        if nama in PENG.data["timpa"]:
            return _nilai(PENG.data["timpa"][nama])
        pakai_lokal = PENG.data["pakai_config_lokal"]
    item = CONFIG.item(nama) or {}
    v = item.get("lokal", item.get("bawaan")) if pakai_lokal else item.get("bawaan")
    try:
        return _nilai(v)
    except (ValueError, SyntaxError):
        return v


def periksa_pengaturan(timpa: dict, tambah: dict) -> list[str]:
    import ast
    masalah = []
    for nama, v in timpa.items():
        item = CONFIG.item(nama)
        if item is None:
            masalah.append(f"{nama}: bukan pengaturan yang dikenal.")
            continue
        jenis = item["jenis"]
        if isinstance(item.get("bawaan"), dict) and "__tidak_bisa_diubah__" in item["bawaan"]:
            masalah.append(f"{nama}: tidak bisa diubah dari GUI (ubah lewat inti/config_lokal.py).")
            continue
        if isinstance(v, dict) and set(v) == {"__py__"}:
            try:
                nilai = ast.literal_eval(v["__py__"])
            except (ValueError, SyntaxError) as e:
                masalah.append(f"{nama}: bukan nilai Python yang sah ({e}).")
                continue
        else:
            nilai = v
        if nama == "TAHAP2_KOTAK_KOORDINAT":
            if nilai is not None and not (isinstance(nilai, tuple) and len(nilai) == 4
                                          and all(isinstance(x, (int, float)) for x in nilai)
                                          and nilai[0] < nilai[1] and nilai[2] < nilai[3]):
                masalah.append(f"{nama}: harus (lintang_min, lintang_maks, bujur_min, bujur_maks) dgn min < maks.")
            continue
        ok = {"str": isinstance(nilai, str), "bool": isinstance(nilai, bool),
              "int": isinstance(nilai, int) and not isinstance(nilai, bool),
              "float": isinstance(nilai, (int, float)) and not isinstance(nilai, bool)}.get(jenis)
        if ok is None:
            ok = type(nilai).__name__ == jenis
        if not ok:
            masalah.append(f"{nama}: jenis nilai harus {jenis} (dapat {type(nilai).__name__}).")
            continue
        if nama in VALIDASI_KHUSUS and not re.fullmatch(VALIDASI_KHUSUS[nama][0], str(nilai)):
            masalah.append(f"{nama}: harus {VALIDASI_KHUSUS[nama][1]} (dapat '{nilai}').")
    for nama, isi in tambah.items():
        if nama not in NAMA_GABUNG:
            masalah.append(f"{nama}: tidak bisa ditambah (hanya {', '.join(sorted(NAMA_GABUNG))}).")
            continue
        if not isinstance(isi, dict):
            masalah.append(f"{nama}: harus berupa tabel.")
            continue
        lebar = 10 if nama == "KODEPOS_BY_DESA" else 16
        for k, v in isi.items():
            if not re.fullmatch(rf"\d{{{lebar}}}", str(k)):
                masalah.append(f"{nama}: kode '{k}' harus {lebar} digit.")
                break
            if nama.startswith("KODEPOS") and not re.fullmatch(r"\d{5}", str(v)):
                masalah.append(f"{nama}: kodepos '{v}' (kode {k}) harus 5 digit.")
                break
            if nama == "WILAYAH_BY_IDSUBSLS" and not (isinstance(v, dict) and set(v) <= set(T.KOLOM_WILAYAH)):
                masalah.append(f"{nama}: isi {k} harus {{{', '.join(T.KOLOM_WILAYAH)}}}.")
                break
    return masalah


# ============================================================================ proses
class Proses:
    BATAS_BARIS = 60_000

    def __init__(self, id_: int, alat: dict, aksi_: dict, isian: dict, perintah: list[str], cwd: Path,
                 env: dict, snapshot: Path | None):
        self.id = id_
        self.alat, self.aksi, self.isian = alat, aksi_, isian
        self.judul = f"{alat['judul']} — {aksi_['label']}"
        self.perintah, self.cwd, self.env, self.snapshot = perintah, cwd, env, snapshot
        self.baris: list[str] = []
        self.terbuang = 0
        self.sisa = ""
        self.status = "berjalan"
        self.kode: int | None = None
        self.mulai, self.selesai = sekarang(), ""
        self.menunggu_ya = False
        self.dihentikan = False
        self.kunci = threading.Lock()
        LOG.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG / f"{datetime.now():%Y%m%d-%H%M%S}_{id_:03d}_{alat['id']}_{aksi_['id']}.txt"
        self.popen: subprocess.Popen | None = None

    def teks_perintah(self) -> str:
        return teks_perintah(self.perintah)

    def mulai_jalan(self) -> None:
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if WINDOWS else 0
        self._log_tulis(f"# {sekarang()}  {self.judul}\n# folder: {self.cwd}\n# perintah: {self.teks_perintah()}\n\n")
        self.popen = subprocess.Popen(self.perintah, cwd=self.cwd, env=self.env, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags,
                                      start_new_session=not WINDOWS)
        threading.Thread(target=self._baca, daemon=True).start()

    def _log_tulis(self, teks: str) -> None:
        with open(self.log_path, "a", encoding="utf-8", newline="") as f:
            f.write(teks)

    def _tambah(self, teks: str) -> None:
        with self.kunci:
            gabung = self.sisa + teks
            potong = gabung.split("\n")
            self.sisa = potong.pop()
            for b in potong:
                b = b.rstrip("\r")
                if "\r" in b:                       # progres yang menimpa baris yang sama
                    b = b.split("\r")[-1]
                self.baris.append(b)
            if "\r" in self.sisa:
                self.sisa = self.sisa.split("\r")[-1]
            if len(self.baris) > self.BATAS_BARIS:
                buang = len(self.baris) - self.BATAS_BARIS + 10_000
                del self.baris[:buang]
                self.terbuang += buang
            self.menunggu_ya = bool(A.POLA_PROMPT_YA.search(self.sisa))

    def _baca(self) -> None:
        dekoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        fd = self.popen.stdout.fileno()
        while True:
            try:
                potongan = os.read(fd, 8192)
            except OSError:
                potongan = b""
            if not potongan:
                break
            teks = dekoder.decode(potongan)
            self._log_tulis(teks)
            self._tambah(teks)
        self._tambah(dekoder.decode(b"", final=True))
        kode = self.popen.wait()
        with self.kunci:
            if self.sisa:
                self.baris.append(self.sisa)
                self.sisa = ""
            self.kode = kode
            self.menunggu_ya = False
            self.selesai = sekarang()
            self.status = "dihentikan" if self.dihentikan else ("selesai" if kode == 0 else "gagal")
        self._log_tulis(f"\n# {sekarang()}  selesai, kode keluar {kode}\n")
        if self.snapshot:
            try:
                self.snapshot.unlink()
            except OSError:
                pass

    def masukan(self, teks: str) -> None:
        if self.status != "berjalan" or not self.popen or not self.popen.stdin:
            raise ValueError("Proses tidak sedang berjalan.")
        with self.kunci:
            if self.sisa:
                self.baris.append(self.sisa + teks)
                self.sisa = ""
            else:
                self.baris.append(f"» {teks}")
            self.menunggu_ya = False
        self._log_tulis(f"{teks}\n")
        self.popen.stdin.write((teks + "\n").encode("utf-8"))
        self.popen.stdin.flush()

    def hentikan(self) -> None:
        if self.status != "berjalan" or not self.popen:
            return
        self.dihentikan = True
        if WINDOWS:
            subprocess.run(["taskkill", "/PID", str(self.popen.pid), "/T", "/F"], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            import signal
            try:
                os.killpg(self.popen.pid, signal.SIGTERM)
            except OSError:
                pass

    def ringkas(self) -> dict:
        with self.kunci:
            return {"id": self.id, "judul": self.judul, "alat": self.alat["id"], "aksi": self.aksi["id"],
                    "jenis": self.aksi.get("jenis"), "status": self.status, "kode": self.kode, "mulai": self.mulai,
                    "selesai": self.selesai, "menunggu_ya": self.menunggu_ya,
                    "prompt": self.sisa if self.menunggu_ya else "", "jumlah": self.terbuang + len(self.baris),
                    "perintah": self.teks_perintah(), "log": relatif(self.log_path), "isian": self.isian,
                    "keluaran": self.keluaran()}

    def keluaran(self) -> list[dict]:
        hasil = []
        for k in self.alat.get("keluaran", []):
            if k.get("aksi") and self.aksi["id"] not in k["aksi"]:
                continue
            p = A.path_keluaran(k, self.isian, AKAR) if k["jenis"] != "folder" else AKAR / k["path"]
            hasil.append({"label": k["label"], "jenis": k["jenis"], "path": str(p), "tampil": relatif(p),
                          "ada": p.exists()})
        return hasil

    def potong(self, dari: int) -> dict:
        with self.kunci:
            awal = max(0, dari - self.terbuang)
            return {"baris": self.baris[awal:], "dari": self.terbuang + awal,
                    "sampai": self.terbuang + len(self.baris), "sisa": self.sisa, "terbuang": self.terbuang}


class Pengelola:
    def __init__(self):
        self.proses: dict[int, Proses] = {}
        self.berikut = 1
        self.kunci = threading.Lock()

    def baru(self, **kw) -> Proses:
        with self.kunci:
            p = Proses(self.berikut, **kw)
            self.proses[p.id] = p
            self.berikut += 1
        p.mulai_jalan()
        return p

    def ambil(self, id_: int) -> Proses:
        p = self.proses.get(id_)
        if not p:
            raise KeyError("Proses tidak ada (mungkin GUI sudah dimulai ulang).")
        return p

    def daftar(self) -> list[dict]:
        return [p.ringkas() for p in sorted(self.proses.values(), key=lambda x: -x.id)]

    def berjalan(self) -> list[Proses]:
        return [p for p in self.proses.values() if p.status == "berjalan"]


PROSES = Pengelola()


def teks_perintah(perintah: list[str]) -> str:
    bagian = []
    for i, x in enumerate(perintah):
        if i == 0 and x == sys.executable:
            x = "python"
        elif i == 1 and x == "-u":
            continue
        else:
            x = relatif(x) if (os.sep in x or "/" in x) and Path(x).is_absolute() else x
        bagian.append(f'"{x}"' if (" " in x or not x) else x)
    return " ".join(bagian)


def siapkan_env(snapshot: Path | None, kbli: bool = False) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with KUNCI_SESI:
        password = SESI["password"]
    if kbli:
        env.pop("FASIH_PASSWORD", None)
        return env
    env["PYTHONPATH"] = str(SISIP) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if snapshot is None:
        SNAPSHOT.mkdir(parents=True, exist_ok=True)
        snapshot = SNAPSHOT / "bantu.json"
        snapshot.write_text(json.dumps(PENG.untuk_alat(), ensure_ascii=False), encoding="utf-8")
    env["FASIH_GUI_PENGATURAN"] = str(snapshot)
    if PENG.data["pakai_config_lokal"]:
        env.pop("FASIH_ABAIKAN_CONFIG_LOKAL", None)
    else:
        env["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
    if password:
        env["FASIH_PASSWORD"] = password
    return env


def password_tersedia() -> bool:
    with KUNCI_SESI:
        if SESI["password"]:
            return True
    return bool(PENG.data["pakai_config_lokal"] and CONFIG.data.get("password_lokal_ada"))


def folder_kbli() -> tuple[Path, Path | None]:
    g = PENG.data["gui"]
    folder = mutlak(g.get("kbli_folder") or (AKAR.parent / "generate_kbli"))
    epapi = mutlak(g["epapi_folder"]) if g.get("epapi_folder") else None
    return folder, epapi


def status_kbli() -> dict:
    folder, epapi = folder_kbli()
    epapi_efektif = epapi or folder.parent / "epapi-se2026"
    onnx = folder / "model" / "onnx"
    return {"folder": str(folder), "ada": (folder / "generate_kbli.py").exists(), "node": shutil.which("node") or "",
            "epapi": str(epapi_efektif), "epapi_ada": (epapi_efektif / "shared" / "kbli-cari.js").exists(),
            "model_ada": onnx.exists() and any(onnx.iterdir()),
            "unduh_model_ada": (folder / "unduh_model.py").exists()}


def susun_perintah(alat_id: str, aksi_id: str, isian: dict) -> tuple[dict, dict, list[str], Path]:
    alat = A.ALAT_PER_ID.get(alat_id)
    if not alat:
        raise A.IsianSalah(f"Alat '{alat_id}' tidak dikenal.")
    aksi_ = A.cari_aksi(alat, aksi_id)
    argumen = A.susun_argumen(alat, aksi_id, isian, efektif)
    if alat["skrip"].startswith("@kbli/"):
        folder, epapi = folder_kbli()
        skrip = folder / alat["skrip"].split("/", 1)[1]
        if not skrip.exists():
            raise A.IsianSalah(f"generate_kbli tidak ditemukan di {folder} — atur foldernya di Pengaturan > Aplikasi.")
        # cwd = folder generate_kbli -> semua path diubah ke absolut (relatif thd akar proyek ini)
        argumen = [str(mutlak(x)) if i == 0 else x for i, x in enumerate(argumen)]
        if "-o" in argumen:
            i = argumen.index("-o") + 1
            argumen[i] = str(mutlak(argumen[i]))
        else:
            out = A.path_keluaran(alat["keluaran"][0], isian, AKAR)
            out.parent.mkdir(parents=True, exist_ok=True)
            argumen += ["-o", str(out)]
        if epapi:
            argumen += ["--epapi", str(epapi)]
        return alat, aksi_, [sys.executable, "-u", str(skrip), *argumen], folder
    return alat, aksi_, [sys.executable, "-u", str(AKAR / alat["skrip"]), *argumen], AKAR


def jalankan_alat(data: dict) -> Proses:
    alat, aksi_, perintah, cwd = susun_perintah(data.get("alat", ""), data.get("aksi", ""), data.get("isian") or {})
    isian = data.get("isian") or {}
    if aksi_.get("ya_dulu") and data.get("konfirmasi_ya") != "YA":
        raise A.IsianSalah("Aksi ini wajib dikonfirmasi dgn mengetik YA.")
    if A.butuh_password(alat, aksi_, isian) and not password_tersedia():
        raise A.IsianSalah("Password SSO belum diisi — klik 'Password' di kanan atas (tidak disimpan ke disk).")
    kbli = alat["skrip"].startswith("@kbli/")
    snapshot = None
    if not kbli:
        SNAPSHOT.mkdir(parents=True, exist_ok=True)
        snapshot = SNAPSHOT / f"{datetime.now():%Y%m%d-%H%M%S}_{secrets.token_hex(3)}.json"
        snapshot.write_text(json.dumps(PENG.untuk_alat(), ensure_ascii=False), encoding="utf-8")
    env = siapkan_env(snapshot, kbli=kbli)
    simpan_isian(alat["id"], isian)
    return PROSES.baru(alat=alat, aksi_=aksi_, isian=isian, perintah=perintah, cwd=cwd, env=env, snapshot=snapshot)


KUNCI_ISIAN = threading.Lock()


def muat_isian() -> dict:
    try:
        return json.loads(ISIAN_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def simpan_isian(alat_id: str, isian: dict) -> None:
    with KUNCI_ISIAN:
        data = muat_isian()
        data[alat_id] = isian
        ISIAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = ISIAN_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, ISIAN_PATH)


def jalankan_pasang(apa: str) -> Proses:
    """Tombol Persiapan: pasang paket / Chromium / unduh model KBLI (proses biasa, log terlihat)."""
    if apa == "paket":
        perintah, cwd, judul = [sys.executable, "-u", "-m", "pip", "install", "-r", str(AKAR / "requirements.txt")], AKAR, "Pasang paket Python"
    elif apa == "chromium":
        perintah, cwd, judul = [sys.executable, "-u", "-m", "playwright", "install", "chromium"], AKAR, "Pasang Chromium Playwright"
    elif apa == "model_kbli":
        folder, _ = folder_kbli()
        if not (folder / "unduh_model.py").exists():
            raise A.IsianSalah(f"unduh_model.py tidak ada di {folder}.")
        perintah, cwd, judul = [sys.executable, "-u", str(folder / "unduh_model.py")], folder, "Unduh model KBLI"
    else:
        raise A.IsianSalah(f"'{apa}' tidak dikenal.")
    alat = {"id": "persiapan", "judul": judul, "keluaran": []}
    aksi_ = {"id": apa, "label": "pasang", "jenis": "aman"}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    env.pop("FASIH_PASSWORD", None)
    return PROSES.baru(alat=alat, aksi_=aksi_, isian={}, perintah=perintah, cwd=cwd, env=env, snapshot=None)


# ============================================================================ persiapan & lain-lain
def folder_chromium() -> bool:
    dasar = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright")
    if not WINDOWS and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        dasar = str(Path.home() / ".cache" / "ms-playwright")
    return any(Path(dasar).glob("chromium-*"))


def persiapan() -> dict:
    import importlib.util
    CONFIG.segarkan()
    kode_kab = str(efektif("KODE_KAB") or "")
    kodepos = dict(efektif("KODEPOS_BY_DESA") or {})
    kodepos.update(PENG.data["tambah"].get("KODEPOS_BY_DESA") or {})
    kotak = efektif("TAHAP2_KOTAK_KOORDINAT")
    kotak_buleleng = tuple(kotak or ()) == (-8.45, -8.0, 114.4, 115.45)
    cek = [
        {"nama": "Python", "ok": sys.version_info >= (3, 10), "teks": sys.version.split()[0],
         "saran": "Pasang Python 3.10 atau lebih baru."},
        {"nama": "Paket openpyxl", "ok": importlib.util.find_spec("openpyxl") is not None, "pasang": "paket"},
        {"nama": "Paket playwright", "ok": importlib.util.find_spec("playwright") is not None, "pasang": "paket"},
        {"nama": "Browser Chromium (Playwright)", "ok": folder_chromium(), "pasang": "chromium"},
        {"nama": "Tkinter (jendela pilih berkas)", "ok": importlib.util.find_spec("tkinter") is not None,
         "saran": "Tanpa ini, ketik path berkas manual. Pasang ulang Python dgn opsi 'tcl/tk'."},
        {"nama": "Node.js (hanya utk Generate KBLI)", "ok": bool(shutil.which("node")), "opsional": True,
         "saran": "Pasang dari nodejs.org kalau memakai Generate KBLI."},
        {"nama": "Kode kabupaten (KODE_KAB)", "ok": bool(re.fullmatch(r"\d{4}", kode_kab)), "teks": kode_kab,
         "saran": "Isi di Pengaturan > Dasar."},
        {"nama": "Kodepos per desa", "ok": any(k.startswith(kode_kab) for k in kodepos),
         "teks": f"{sum(1 for k in kodepos if k.startswith(kode_kab))} desa",
         "saran": "Isi di Pengaturan > Wilayah (atau beri kolom 'kodepos' di sheet)."},
        {"nama": "Kotak koordinat kabupaten", "ok": bool(kotak) and not (kotak_buleleng and kode_kab != "5108"),
         "teks": str(kotak), "saran": "Masih kotak Buleleng — isi di Pengaturan > Dasar (bisa dihitung dari peta SLS)."},
        {"nama": "Password SSO (sesi ini)", "ok": password_tersedia(), "teks": "",
         "saran": "Klik 'Password' di kanan atas. Tidak disimpan ke disk."},
    ]
    if (AKAR / "audit_log_gabungan.csv").exists():
        cek.append({"nama": "Struktur folder", "ok": False, "teks": "audit masih di akar proyek",
                    "saran": "Jalankan Antar PC > Pindah ke struktur folder baru."})
    if CONFIG.data.get("galat_config_lokal"):
        cek.append({"nama": "inti/config_lokal.py", "ok": False, "teks": CONFIG.data["galat_config_lokal"]})
    return {"cek": cek, "akar": str(AKAR), "python": sys.executable,
            "config_lokal_ada": CONFIG.data.get("config_lokal_ada", False),
            "pakai_config_lokal": PENG.data["pakai_config_lokal"]}


def cek_vpn() -> dict:
    hasil = {}
    for host in ("fasih-web.bps.go.id", "fasih-sm.bps.go.id"):
        t = time.time()
        try:
            with socket.create_connection((host, 443), timeout=5):
                hasil[host] = {"ok": True, "teks": f"terjangkau ({(time.time() - t) * 1000:.0f} ms)"}
        except OSError as e:
            hasil[host] = {"ok": False, "teks": f"tidak terjangkau ({e.__class__.__name__}) — VPN kantor aktif?"}
    return hasil


DIALOG_PY = r"""
import json, sys, tkinter as tk
from tkinter import filedialog
a = json.loads(sys.argv[1])
root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True); root.update()
kw = {"parent": root, "title": a.get("judul") or "Pilih"}
if a.get("awal"): kw["initialdir"] = a["awal"]
ft = [tuple(x) for x in (a.get("filter") or [])] + [("Semua berkas", "*.*")]
j = a["jenis"]
if j == "buka":
    r = filedialog.askopenfilename(filetypes=ft, **kw); h = [r] if r else []
elif j == "buka_banyak":
    h = list(filedialog.askopenfilenames(filetypes=ft, **kw))
elif j == "folder":
    r = filedialog.askdirectory(mustexist=True, **kw); h = [r] if r else []
else:
    r = filedialog.asksaveasfilename(filetypes=ft, defaultextension=a.get("ekstensi") or "", initialfile=a.get("nama") or "", **kw); h = [r] if r else []
root.destroy()
sys.stdout.write(json.dumps(h))
"""


def dialog_berkas(data: dict) -> list[str]:
    jenis = data.get("jenis") if data.get("jenis") in ("buka", "buka_banyak", "folder", "simpan") else "buka"
    awal = data.get("awal") or ""
    if awal:
        a = mutlak(awal)
        awal = str(a if a.is_dir() else a.parent)
    else:
        awal = str(AKAR / "bahan") if (AKAR / "bahan").exists() else str(AKAR)
    arg = json.dumps({"jenis": jenis, "judul": data.get("judul", ""), "awal": awal, "filter": data.get("filter") or [],
                      "ekstensi": data.get("ekstensi", ""), "nama": data.get("nama", "")})
    p = subprocess.run([sys.executable, "-c", DIALOG_PY, arg], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=3600)
    if p.returncode != 0:
        raise A.IsianSalah("Jendela pilih berkas tidak bisa dibuka (Tkinter?). Ketik path-nya langsung.\n"
                           + (p.stderr or "")[-400:])
    return [relatif(Path(x)) for x in json.loads(p.stdout or "[]")]


def boleh_dibaca(p: Path) -> bool:
    try:
        r = p.resolve()
    except OSError:
        return False
    dasar = [AKAR.resolve(), folder_kbli()[0].resolve()]
    return any(r == d or d in r.parents for d in dasar)


def riwayat_log(n: int = 40) -> list[dict]:
    if not LOG.exists():
        return []
    berkas = sorted(LOG.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
    return [{"nama": p.name, "path": str(p), "ukuran": p.stat().st_size,
             "waktu": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")} for p in berkas]


def daftar_audit() -> list[str]:
    """Folder audit yang ada (berisi audit_log_gabungan.csv), utk pilihan cepat di formulir."""
    hasil = []
    dasar = AKAR / "audit"
    if dasar.exists():
        for p in sorted(dasar.rglob("audit_log_gabungan.csv")):
            hasil.append(relatif(p.parent))
    return hasil


def data_awal() -> dict:
    if not CONFIG.data:
        CONFIG.segarkan()
    with PENG.kunci:
        peng = json.loads(json.dumps(PENG.data))
    return {"alat": A.untuk_gui(), "pengaturan": peng, "isian": muat_isian(), "config": CONFIG.data, "akar": str(AKAR),
            "password": {"sesi": bool(SESI["password"]), "tersedia": password_tersedia()},
            "audit": daftar_audit(), "kbli": status_kbli(), "peringatan": PENG.peringatan}


# ============================================================================ HTTP
class Penangan(BaseHTTPRequestHandler):
    server_version = "InjectUsahaGUI/1"
    token = ""
    port = PORT_BAWAAN

    def log_message(self, fmt, *args):  # sunyi: log proses ada di gui/hasil/log/
        pass

    # --- utilitas ------------------------------------------------------------
    def _kirim(self, kode: int, isi: bytes, jenis: str) -> None:
        self.send_response(kode)
        self.send_header("Content-Type", jenis)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(isi)

    def _json(self, data, kode: int = 200) -> None:
        self._kirim(kode, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _galat(self, pesan: str, kode: int = 400) -> None:
        self._json({"galat": pesan}, kode)

    def _host_sah(self) -> bool:
        return self.headers.get("Host", "") in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def _token_sah(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Token", ""), self.token)

    def _badan(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 50 * 1024 * 1024:
            raise A.IsianSalah("Permintaan terlalu besar.")
        return json.loads(self.rfile.read(n) or b"{}")

    # --- GET -----------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        if not self._host_sah():
            return self._galat("Host tidak diizinkan.", 403)
        u = urlparse(self.path)
        if u.path == "/":
            html = (WEB / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", self.token)
            return self._kirim(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if u.path.startswith("/web/"):
            nama = u.path[5:]
            jenis = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}.get(Path(nama).suffix)
            p = (WEB / nama).resolve()
            if not jenis or WEB.resolve() not in p.parents or not p.exists():
                return self._galat("Tidak ada.", 404)
            return self._kirim(200, p.read_bytes(), f"{jenis}; charset=utf-8")
        if u.path == "/api/ping":
            return self._json({"aplikasi": NAMA_APL})
        if not u.path.startswith("/api/") or not self._token_sah():
            return self._galat("Tidak diizinkan.", 403)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/awal":
                return self._json(data_awal())
            if u.path == "/api/proses":
                return self._json({"proses": PROSES.daftar(), "password": {"tersedia": password_tersedia(),
                                                                           "sesi": bool(SESI["password"])}})
            m = re.fullmatch(r"/api/proses/(\d+)", u.path)
            if m:
                p = PROSES.ambil(int(m.group(1)))
                return self._json({**p.ringkas(), **p.potong(int((q.get("dari") or ["0"])[0]))})
            if u.path == "/api/riwayat":
                return self._json({"log": riwayat_log()})
            if u.path == "/api/persiapan":
                return self._json(persiapan())
            if u.path == "/api/pengaturan":
                CONFIG.segarkan()
                return self._json({"pengaturan": PENG.data, "config": CONFIG.data, "kbli": status_kbli()})
            if u.path == "/api/kbli/status":
                return self._json(status_kbli())
            return self._galat("Tidak ada.", 404)
        except (A.IsianSalah, T.TabelSalah, KeyError, ValueError) as e:
            return self._galat(str(e).strip("'\""))

    # --- POST ----------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        if not self._host_sah() or not self._token_sah():
            return self._galat("Tidak diizinkan.", 403)
        u = urlparse(self.path)
        try:
            d = self._badan()
            m = re.fullmatch(r"/api/proses/(\d+)/(\w+)", u.path)
            if m:
                return self._json(self._aksi_proses(int(m.group(1)), m.group(2), d))
            fungsi = {
                "/api/password": self._password,
                "/api/pratinjau": self._pratinjau,
                "/api/jalankan": lambda d: {"id": jalankan_alat(d).id},
                "/api/dialog": lambda d: {"path": dialog_berkas(d)},
                "/api/buka": self._buka,
                "/api/baca": self._baca,
                "/api/lembar": lambda d: {"lembar": T.daftar_lembar(mutlak(d.get("path", "")))},
                "/api/salin/kbli": lambda d: T.salin_kbli(mutlak(d["hasil"]), mutlak(d["sumber"]) if d.get("sumber") else None,
                                                          d.get("lembar") or None, bool(d.get("pertahankan", True))),
                "/api/salin/koordinat": lambda d: T.salin_koordinat(mutlak(d["hasil"]),
                                                                    mutlak(d["sumber"]) if d.get("sumber") else None,
                                                                    d.get("lembar") or None),
                "/api/persiapan/vpn": lambda d: cek_vpn(),
                "/api/persiapan/pasang": lambda d: {"id": jalankan_pasang(d.get("apa", "")).id},
                "/api/templat": self._templat,
                "/api/pengaturan": self._simpan_pengaturan,
                "/api/pengaturan/tabel": lambda d: T.pratinjau(mutlak(d["path"]), d.get("lembar") or None),
                "/api/pengaturan/impor-tabel": lambda d: T.impor_tabel(mutlak(d["path"]), d.get("jenis", ""),
                                                                       d.get("kolom") or {}, d.get("lembar") or None),
                "/api/pengaturan/impor-peta": self._impor_peta,
                "/api/pengaturan/kodepos-lama": self._kodepos_lama,
            }.get(u.path)
            if not fungsi:
                return self._galat("Tidak ada.", 404)
            return self._json(fungsi(d))
        except (A.IsianSalah, T.TabelSalah, KeyError, ValueError, OSError, subprocess.SubprocessError) as e:
            return self._galat(str(e).strip("'\"") or e.__class__.__name__)

    def _aksi_proses(self, id_: int, aksi_: str, d: dict) -> dict:
        p = PROSES.ambil(id_)
        if aksi_ == "masukan":
            p.masukan(str(d.get("teks", "")))
        elif aksi_ == "jawab":
            if not p.menunggu_ya:
                raise ValueError("Proses tidak sedang menunggu konfirmasi YA.")
            p.masukan("YA" if d.get("jawab") == "YA" else "TIDAK")
        elif aksi_ == "hentikan":
            p.hentikan()
        elif aksi_ == "hapus":
            if p.status == "berjalan":
                raise ValueError("Proses masih berjalan — hentikan dulu.")
            PROSES.proses.pop(id_, None)
        else:
            raise ValueError(f"Aksi '{aksi_}' tidak dikenal.")
        return {"ok": True}

    def _password(self, d: dict) -> dict:
        with KUNCI_SESI:
            SESI["password"] = str(d.get("password") or "")
        return {"sesi": bool(SESI["password"]), "tersedia": password_tersedia()}

    def _pratinjau(self, d: dict) -> dict:
        try:
            _, _, perintah, cwd = susun_perintah(d.get("alat", ""), d.get("aksi", ""), d.get("isian") or {})
        except A.IsianSalah as e:
            return {"masalah": str(e)}
        return {"perintah": teks_perintah(perintah), "folder": relatif(cwd) if cwd != AKAR else ""}

    def _buka(self, d: dict) -> dict:
        p = mutlak(d.get("path", ""))
        if not p.exists():
            raise ValueError(f"Belum ada: {relatif(p)}")
        if p.is_file() and p.suffix.lower() not in EKSTENSI_BUKA:
            p = p.parent                             # mis. .siap.js: buka foldernya, JANGAN jalankan berkasnya
        if WINDOWS:
            os.startfile(str(p))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return {"ok": True}

    def _baca(self, d: dict) -> dict:
        p = mutlak(d.get("path", ""))
        if p.suffix.lower() not in EKSTENSI_BACA or not boleh_dibaca(p):
            raise ValueError("Berkas ini tidak boleh dibaca GUI.")
        if not p.exists():
            raise ValueError(f"Belum ada: {relatif(p)}")
        if p.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Berkas terlalu besar utk ditampilkan.")
        return {"teks": p.read_text(encoding="utf-8", errors="replace"), "path": relatif(p)}

    def _templat(self, d: dict) -> dict:
        tujuan = mutlak(d.get("tujuan", ""))
        if tujuan.exists():
            raise ValueError(f"{relatif(tujuan)} sudah ada — pilih nama lain (templat tidak pernah menimpa berkas).")
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(AKAR / "templates" / "input_usaha.xlsx", tujuan)
        return {"path": relatif(tujuan)}

    def _simpan_pengaturan(self, d: dict) -> dict:
        timpa = d.get("timpa") if isinstance(d.get("timpa"), dict) else PENG.data["timpa"]
        tambah = d.get("tambah") if isinstance(d.get("tambah"), dict) else PENG.data["tambah"]
        timpa = {k: v for k, v in timpa.items() if v is not None or k == "TAHAP2_KOTAK_KOORDINAT"}
        tambah = {k: v for k, v in tambah.items() if v}
        masalah = periksa_pengaturan(timpa, tambah)
        if masalah:
            raise A.IsianSalah("\n".join(masalah))
        with PENG.kunci:
            PENG.data["timpa"], PENG.data["tambah"] = timpa, tambah
            if "pakai_config_lokal" in d:
                PENG.data["pakai_config_lokal"] = bool(d["pakai_config_lokal"])
            for k in ("kbli_folder", "epapi_folder"):
                if k in (d.get("gui") or {}):
                    PENG.data["gui"][k] = str(d["gui"][k] or "").strip()
            PENG.simpan()
        return {"ok": True, "pengaturan": PENG.data, "kbli": status_kbli()}

    def _impor_peta(self, d: dict) -> dict:
        kode = str(efektif("KODE_KAB") or "")
        if not re.fullmatch(r"\d{4}", kode):
            raise A.IsianSalah("Isi KODE_KAB dulu (Pengaturan > Dasar).")
        p = mutlak(d.get("path", ""))
        if not p.exists():
            raise ValueError(f"Berkas tidak ada: {p}")
        hasil = jalankan_bantu(["peta", str(p), "--kode-kab", kode, "--margin", str(float(d.get("margin", 0.05)))],
                               timeout=600)
        if hasil.get("galat"):
            raise ValueError(hasil["galat"])
        return hasil

    def _kodepos_lama(self, d: dict) -> dict:
        kode = str(efektif("KODE_KAB") or "")
        arg = ["kodepos", "--kode-kab", kode]
        for f in d.get("dari") or []:
            arg += ["--dari", str(mutlak(f))]
        hasil = jalankan_bantu(arg, env_alat=True, timeout=600)
        if hasil.get("galat"):
            raise ValueError(hasil["galat"])
        return hasil


def server_lain_hidup(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return json.loads(r.read()).get("aplikasi") == NAMA_APL
    except (OSError, ValueError):
        return False


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="GUI web lokal Inject Usaha SE2026")
    ap.add_argument("--port", type=int, default=PORT_BAWAAN)
    ap.add_argument("--tanpa-browser", action="store_true", help="jangan buka browser otomatis")
    args = ap.parse_args()

    if server_lain_hidup(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        print(f"GUI sudah berjalan di {url} — membuka browser.")
        if not args.tanpa_browser:
            webbrowser.open(url)
        return 0

    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Penangan)
            break
        except OSError:
            continue
    if server is None:
        print(f"⛔ Tidak ada port kosong di {args.port}-{args.port + 19}.")
        return 1
    server.daemon_threads = True
    Penangan.token = secrets.token_urlsafe(24)
    Penangan.port = server.server_address[1]
    url = f"http://127.0.0.1:{Penangan.port}/"
    HASIL.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=CONFIG.segarkan, daemon=True).start()
    print("=" * 70)
    print(f"  GUI Inject Usaha SE2026 berjalan di {url}")
    print("  Biarkan jendela ini terbuka selama memakai GUI.")
    print("  Tutup: Ctrl+C di jendela ini (proses yang masih berjalan ditanyakan dulu).")
    print("=" * 70)
    if PENG.peringatan:
        print("⚠️ " + PENG.peringatan)
    if not args.tanpa_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    peringatan_terakhir = 0.0
    while True:
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            hidup = PROSES.berjalan()
            if hidup and time.time() - peringatan_terakhir > 10:
                peringatan_terakhir = time.time()
                print(f"\n⚠️ Masih ada {len(hidup)} proses berjalan: " + "; ".join(p.judul for p in hidup))
                print("   Tekan Ctrl+C sekali lagi dalam 10 detik utk MENGHENTIKAN semuanya & menutup GUI.")
                continue
            for p in hidup:
                print(f"Menghentikan: {p.judul}")
                p.hentikan()
            server.shutdown()
            print("GUI ditutup.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
