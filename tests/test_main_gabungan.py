# -*- coding: utf-8 -*-
"""Uji bagian main_gabungan yang tidak butuh browser: audit (migrasi header,
dokumen per kunci utk mencegah duplikat) & pembagian sesi login.
Jalankan: python tests/test_main_gabungan.py
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import input_gabungan.main_gabungan as mg
from inti.gabungan_loader import GabunganRow

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


with tempfile.TemporaryDirectory() as d:
    mg.AUDIT_LOG_PATH = Path(d) / "audit.csv"

    # Audit format lama (2026-09-13) -> ditulis ulang dgn header baru, isi utuh.
    lama = ["timestamp", "baris", "kunci", "nama_usaha", "kbli", "idsubsls", "akun_ppl", "status",
            "galat", "peringatan", "kosong", "catatan_count", "review_disarankan", "error_message"]
    with mg.AUDIT_LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(lama)
        w.writerow(["t", "2", "k0", "X", "47772", "5108070013000901", "a@gmail.com", "ERROR_LOGIN",
                    "", "", "", "", "", "gagal"])
    mg.append_audit({"kunci": "k1", "status": mg.STATUS_DIBUAT, "akun_login": "tunggal@gmail.com",
                     "idsubsls_input": "5108060014000302", "dokumen_url": "https://x/survey/s/p/d1/entry"})
    with mg.AUDIT_LOG_PATH.open(newline="", encoding="utf-8") as f:
        isi = list(csv.DictReader(f))
    check("header audit dimigrasi", list(isi[0].keys()), mg.AUDIT_FIELDS)
    check("baris lama tetap utuh", (isi[0]["kunci"], isi[0]["status"], isi[0]["error_message"]),
          ("k0", "ERROR_LOGIN", "gagal"))

    # DOKUMEN_DIBUAT tanpa URL (jalur toast) tetap dianggap pernah dibuat.
    mg.append_audit({"kunci": "k2", "status": mg.STATUS_DIBUAT, "akun_login": "tunggal@gmail.com",
                     "idsubsls_input": "5108060014000302"})
    # Status akhir tanpa URL tidak menghapus URL yang sudah tercatat.
    mg.append_audit({"kunci": "k1", "status": "ERROR_TAK_TERDUGA", "akun_login": "tunggal@gmail.com",
                     "idsubsls_input": "5108060014000302"})
    dok = mg.dokumen_per_kunci()
    check("URL dokumen dipertahankan", dok["k1"][2], "https://x/survey/s/p/d1/entry")
    check("dibuat tanpa URL tetap tercatat", dok["k2"], ("tunggal@gmail.com", "5108060014000302", ""))
    check("baris tanpa dokumen tidak tercatat", "k0" in dok, False)
    check("status terakhir menang", mg.status_terakhir_per_kunci()["k1"], "ERROR_TAK_TERDUGA")


# --- process_one_row dgn sesi PALSU: cabang buka/buat dokumen & cek langsung ---
from inti.fasih_web import FieldNotFound
from inti.gabungan_loader import Pemeriksaan

SUBSLS = "5108060014000302"
URL = "https://fasih-web.bps.go.id/survey/s/p/doc1/entry"


class FakePage:
    def __init__(self):
        self.url = "https://fasih-web.bps.go.id/survey/s/p"

    def wait_for_timeout(self, _):
        pass


class FakeSess:
    def __init__(self, wilayah=None, buat=True, url_baru=URL, gagal_dropdown=False):
        self.page, self.aksi = FakePage(), []
        self.wilayah = wilayah or {"prov": "51", "kab": "08", "kec": "060", "desa": "014", "kode_sls": "000302"}
        self.buat, self.url_baru, self.gagal_dropdown = buat, url_baru, gagal_dropdown
        self.dokumen_url_terakhir, self.dokumen_dibuat = "", False
        self.terkunci = False

    def _log(self, *_):
        pass

    def _shot(self, *_):
        pass

    def create_document(self, assignment_id, idsubsls, nama, nama_lama=""):
        self.aksi.append(("create", idsubsls, nama))
        if self.gagal_dropdown:
            raise FieldNotFound("Dropdown 'Pilih SUBSLS': tidak ada opsi dgn kode '[02]'")
        if self.buat:
            self.dokumen_dibuat = True
            self.dokumen_url_terakhir = self.page.url = self.url_baru
        return self.buat

    def open_entry_for(self, nama, assignment_id, allow_retry_if_fresh=True):
        self.aksi.append(("open", allow_retry_if_fresh))
        self.page.url = URL

    def buka_dokumen_url(self, url, nama=""):
        self.aksi.append(("url", url))
        self.page.url = url

    def fill_pengantar(self):
        pass

    def next_section(self):
        return True

    def baca_wilayah_dokumen(self):
        return self.wilayah

    def dokumen_terkunci(self):
        return self.terkunci

    def fill_identitas_wilayah(self, kodepos):
        raise FieldNotFound("berhenti di sini (uji)")


ROW = GabunganRow(5, {"akun_ppl": "asli@gmail.com", "idsubsls": "5108010001000101", "nama": "TOKO A",
                      "pengusaha": "MADE", "kbli": "47111", "kodepos": "81111"})


def proses(sess, **kw):
    return mg.process_one_row(sess, ROW, Pemeriksaan(), True, "p", SUBSLS, "tunggal@gmail.com", **kw)


with tempfile.TemporaryDirectory() as d:
    mg.AUDIT_LOG_PATH = Path(d) / "audit.csv"

    s = FakeSess()
    res = proses(s)
    check("buat dokumen di subsls TUNGGAL dgn nama dokumen", s.aksi[0], ("create", SUBSLS, "TOKO A (MADE)"))
    check("DOKUMEN_DIBUAT + URL ditulis sebelum mengisi", mg.dokumen_per_kunci()[ROW.kunci],
          ("tunggal@gmail.com", SUBSLS, URL))
    check("audit mencatat wilayah asli & URL", (res["idsubsls"], res["idsubsls_input"], res["dokumen_url"]),
          ("5108010001000101", SUBSLS, URL))
    check("wilayah cocok -> lanjut mengisi", (res["status"], res["wilayah_dokumen"][:5]),
          ("ERROR_FIELD_NOT_FOUND", "COCOK"))

    s = FakeSess()
    proses(s, pernah_dibuat=True, url_audit=URL)
    check("pernah dibuat + URL -> dibuka lewat URL, tidak dibuat", s.aksi, [("url", URL)])
    s = FakeSess()
    proses(s, pernah_dibuat=True)
    check("pernah dibuat tanpa URL -> dicari di list tanpa retry, tidak dibuat", s.aksi, [("open", False)])

    res = proses(FakeSess(wilayah={"desa": "014", "kode_sls": "000401"}))
    check("wilayah dokumen beda -> STOP", res["status"], "STOP_WILAYAH_DOKUMEN_BEDA")
    res = proses(FakeSess(gagal_dropdown=True))
    check("subsls tidak bisa dipilih -> STOP", res["status"], "STOP_SUBSLS_TIDAK_BISA_DIPILIH")
    res = proses(FakeSess(buat=False))
    check("+Dokumen Baru tidak ada -> SKIP_DOKUMEN_BELUM_ADA", res["status"], "SKIP_DOKUMEN_BELUM_ADA")
    s = FakeSess()
    s.terkunci = True
    res = proses(s, pernah_dibuat=True, url_audit=URL)
    check("dokumen sudah terkirim di luar skrip -> DOKUMEN_TERKUNCI, tidak diisi",
          (res["status"], res["status"] in mg.STATUS_TERKIRIM), ("DOKUMEN_TERKUNCI", True))

    # Buat dokumen gagal (tertahan "Memuat Halaman...") -> diulang SEKALI hanya
    # kalau jumlah dokumen di list terbukti tidak bertambah.
    class SessUlang(FakeSess):
        def __init__(self, hasil_buat, jumlah):
            super().__init__()
            self.hasil_buat, self.jumlah = list(hasil_buat), list(jumlah)

        def jumlah_dokumen_list(self, assignment_id):
            return self.jumlah.pop(0)

        def create_document(self, assignment_id, idsubsls, nama, nama_lama=""):
            self.aksi.append(("create", idsubsls, nama))
            self.jumlah_dokumen_awal = self.jumlah.pop(0)  # dibaca create_document dari API list
            self.buat = self.hasil_buat.pop(0)
            if self.buat:
                self.dokumen_dibuat = True
                self.dokumen_url_terakhir = self.page.url = self.url_baru
            return self.buat

    s = SessUlang([False, True], [7, 7, 7])
    res = proses(s, mode_satu_list=True)
    check("gagal buat + jumlah tetap -> diulang sekali & lanjut",
          (len([x for x in s.aksi if x[0] == "create"]), res["dokumen_url"]), (2, URL))
    s = SessUlang([False], [7, 8])
    res = proses(s, mode_satu_list=True)
    check("gagal buat + jumlah naik -> ditandai tanpa-URL, tidak diulang",
          (len([x for x in s.aksi if x[0] == "create"]), res["status"]), (1, mg.STATUS_TANPA_URL))
    s = SessUlang([False, False], [7, 7, 7])
    res = proses(s, mode_satu_list=True)
    check("gagal 2x -> SKIP_DOKUMEN_BELUM_ADA (batch berhenti)", res["status"], "SKIP_DOKUMEN_BELUM_ADA")

from inti.fasih_web import nilai_sama
for label, sekarang, target, want in (
    ("kosong -> ketik", "", "PANGKALAN GAS X", False),
    ("nama di-UPPERCASE form", "PANGKALAN GAS X (MADE)", "Pangkalan Gas X (Made)", True),
    ("mata uang berformat", "15.056.000", "15056000", True),
    ("angka beda", "15.056.000", "15056001", False),
    ("nol", "0", "0", True),
    ("teks beda", "JL. MAWAR", "JL. MELATI", False),
):
    check(f"nilai_sama: {label}", nilai_sama(sekarang, target), want)

rows = [GabunganRow(i, {"akun_ppl": f"ppl{i % 2}@gmail.com", "nama": f"U{i}"}) for i in range(2, 12)]
sesi = mg.rencana_sesi(rows, "tunggal@gmail.com", 4)
check("satu akun: dipotong per 4 baris", [(a, len(b)) for a, b in sesi],
      [("tunggal@gmail.com", 4), ("tunggal@gmail.com", 4), ("tunggal@gmail.com", 2)])
check("per baris: satu sesi per akun PPL", sorted(a for a, _ in mg.rencana_sesi(rows, "", 4)),
      ["ppl0@gmail.com", "ppl1@gmail.com"])

# --- dokumen dihapus admin (2026-09-15, Agenda1-1 baris 88) -> baris dibuatkan dokumen baru ---
with tempfile.TemporaryDirectory() as d:
    mg.AUDIT_LOG_PATH = Path(d) / "audit.csv"
    mg.append_audit({"kunci": "k88", "status": mg.STATUS_DIBUAT, "akun_login": "m@mail.com",
                     "idsubsls_input": "1", "dokumen_url": "https://x/s/p/lama/entry"})
    mg.append_audit({"kunci": "k88", "status": mg.STATUS_TERKUNCI, "akun_login": "m@mail.com", "idsubsls_input": "1"})
    mg.append_audit({"kunci": "k88", "status": mg.STATUS_DIHAPUS, "akun_login": "m@mail.com", "idsubsls_input": "1",
                     "dokumen_url": "https://x/s/p/lama/entry"})
    check("DOKUMEN_DIHAPUS menggugurkan catatan dokumen", "k88" in mg.dokumen_per_kunci(), False)
    check("DOKUMEN_DIHAPUS bukan status tuntas", mg.status_terakhir_per_kunci()["k88"] in mg.STATUS_TERKIRIM, False)
    mg.append_audit({"kunci": "k88", "status": mg.STATUS_DIBUAT, "akun_login": "m@mail.com",
                     "idsubsls_input": "1", "dokumen_url": "https://x/s/p/baru/entry"})
    check("dokumen baru sesudahnya tercatat lagi", mg.dokumen_per_kunci()["k88"][2], "https://x/s/p/baru/entry")

# --- paralel beda akun: list per akun, audit bersama ---
import time as _time
with tempfile.TemporaryDirectory() as d:
    mg.AUDIT_LOG_PATH = Path(d) / "audit.csv"
    t0 = _time.time() - 100
    jam = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(t0 + 50))
    mg.append_audit({"timestamp": jam, "kunci": "kA", "status": mg.STATUS_DIBUAT, "akun_login": "a@mail.com",
                     "idsubsls_input": "1", "dokumen_url": "https://x/s/p/dA/entry"})
    mg.append_audit({"timestamp": jam, "kunci": "kB", "status": mg.STATUS_DIBUAT, "akun_login": "b@mail.com",
                     "idsubsls_input": "2", "dokumen_url": "https://x/s/p/dB/entry"})
    mg.append_audit({"timestamp": jam, "kunci": "kB", "status": "TERKIRIM_BELUM_TERVERIFIKASI",
                     "akun_login": "b@mail.com", "idsubsls_input": "2"})
    check("dokumen akun LAIN tidak menutupi yatim di list akun a",
          mg.kenaikan_tak_terjelaskan(5, 7, t0, "kX", "a@mail.com"), 1)
    check("tanpa filter akun (perilaku lama) semua dihitung", mg.kenaikan_tak_terjelaskan(5, 7, t0, "kX"), 0)
    tuntas = set(mg.STATUS_TERKIRIM)
    check("giliran: dokumen sudah dibuat proses akun lain -> lewati",
          bool(mg.alasan_lewati_saat_giliran("kA", ("b@mail.com", "2"), tuntas)), True)
    check("giliran: dokumen milik akun sendiri -> kerjakan (dibuka lewat URL)",
          mg.alasan_lewati_saat_giliran("kA", ("a@mail.com", "1"), tuntas), "")
    check("giliran: sudah terkirim -> lewati",
          bool(mg.alasan_lewati_saat_giliran("kB", ("b@mail.com", "2"), tuntas)), True)
    check("giliran: belum pernah -> kerjakan", mg.alasan_lewati_saat_giliran("kZ", ("a@mail.com", "1"), tuntas), "")
    # Agenda2 baris 267 vs Agenda baris 108: usaha beda, nama dokumen sama, akun list sama.
    mg.append_audit({"kunci": "k108", "status": mg.STATUS_DIBUAT, "akun_login": "a@mail.com", "idsubsls_input": "1",
                     "nama_usaha": "PANGKALAN GAS (NYOMAN SHUARJANA)", "dokumen_url": "https://x/s/p/d108/entry"})
    check("giliran: nama dokumen sudah dipakai baris lain di akun ini -> lewati",
          mg.alasan_lewati_saat_giliran("k267", ("a@mail.com", "1"), tuntas, "Pangkalan Gas (Nyoman  Shuarjana)")
          .startswith("SKIP_NAMA_DIPAKAI_BARIS_LAIN"), True)
    check("giliran: nama sama tapi di akun lain -> kerjakan",
          mg.alasan_lewati_saat_giliran("k267", ("z@mail.com", "9"), tuntas, "PANGKALAN GAS (NYOMAN SHUARJANA)"), "")
    check("giliran: pemilik nama itu sendiri -> kerjakan (dibuka lewat URL)",
          mg.alasan_lewati_saat_giliran("k108", ("a@mail.com", "1"), tuntas, "PANGKALAN GAS (NYOMAN SHUARJANA)"), "")

    # --- dokumen yang mungkin terbuat TANPA URL (batch tidak lagi berhenti) ---
    mg.append_audit({"timestamp": "2026-09-23 23:10:00", "baris": 77, "kunci": "kTU",
                     "status": mg.STATUS_TANPA_URL, "akun_login": "a@mail.com", "idsubsls_input": "1",
                     "nama_usaha": "WARUNG TANPA URL", "error_message": "jumlah dokumen 7 -> 8"})
    check("tanpa URL: kunci tetap dihitung punya dokumen (anti-duplikat)",
          mg.dokumen_per_kunci().get("kTU"), ("a@mail.com", "1", ""))
    check("tanpa URL: barisnya dilewati sampai ada bukti URL",
          mg.alasan_lewati_saat_giliran("kTU", ("a@mail.com", "1"), tuntas)
          .startswith(mg.TANDA_LEWATI_TANPA_URL), True)
    check("tanpa URL: tanda nama LAMA diperlakukan sama",
          mg.tanda_tanpa_url_terakhir("kTU", [{"kunci": "kTU", "status": "STOP_DOKUMEN_TANPA_URL",
                                               "timestamp": "2026-09-14 01:00:00"}])["timestamp"],
          "2026-09-14 01:00:00")
    asal = mg.tanda_tanpa_url_terakhir("kTU")
    check("tanpa URL: waktu yang dilaporkan = waktu kejadian aslinya",
          mg.catatan_tanpa_url(asal, mg.TANDA_LEWATI_TANPA_URL)["waktu"], "2026-09-23 23:10:00")
    check("tanpa URL: tidak ada tanda -> {}", mg.tanda_tanpa_url_terakhir("kA"), {})
    # Sesudah sinkron_list menemukan dokumennya, baris itu boleh dikerjakan lagi.
    mg.append_audit({"kunci": "kTU", "status": mg.STATUS_DIBUAT, "akun_login": "a@mail.com",
                     "idsubsls_input": "1", "dokumen_url": "https://x/s/p/dTU/entry"})
    check("tanpa URL: setelah URL-nya tercatat, baris dikerjakan lagi",
          mg.alasan_lewati_saat_giliran("kTU", ("a@mail.com", "1"), tuntas), "")

laporan = [mg.catatan_tanpa_url({"timestamp": "2026-09-23 23:10:00", "baris": 77, "nama_usaha": "WARUNG TANPA URL",
                                 "kunci": "kTU", "akun_login": "a@mail.com", "idsubsls_input": "51080",
                                 "status": mg.STATUS_TANPA_URL, "error_message": "jumlah dokumen 7 -> 8"})]
teks = mg.ringkas_tanpa_url(laporan)
check("laporan menyebut baris, nama dokumen & jamnya",
      all(x in teks for x in ("77", "WARUNG TANPA URL", "23:10:00", "51080")), True)
# --- "dokumen apa yang terbuat di sana": dibaca dari list server, hanya DILAPORKAN ---
_list = [
    {"id": "aaa", "data1": "WARUNG LAMA", "assignmentStatusAlias": "DRAFT",
     "dateCreated": "2026-09-23T14:00:00+08:00"},
    {"id": "bbb", "data1": "", "assignmentStatusAlias": "DRAFT",
     "dateCreated": "2026-09-23T23:11:00+08:00"},
    {"id": "ccc", "data1": "SUDAH KIRIM", "assignmentStatusAlias": "SUBMITTED BY Pencacah",
     "dateCreated": "2026-09-23T23:12:00+08:00"},
    {"id": "ddd", "data1": "TERCATAT", "assignmentStatusAlias": "DRAFT",
     "dateCreated": "2026-09-23T23:13:00+08:00"},
]
_asing = mg.dokumen_asing(_list, {"ddd"}, sejak="2026-09-23 23:10:00")
check("cuma DRAFT baru yang belum tercatat yang dilaporkan",
      [d["id"] for d in _asing], ["bbb"])
check("dokumen terkirim & dokumen lama tidak ikut",
      all(d["id"] not in ("aaa", "ccc", "ddd") for d in _asing), True)
check("tanpa batas waktu: semua DRAFT tak tercatat ikut",
      sorted(d["id"] for d in mg.dokumen_asing(_list, set())), ["aaa", "bbb", "ddd"])
check("dokumen yang ID-nya sudah tercatat di audit tidak dilaporkan",
      sorted(d["id"] for d in mg.dokumen_asing(_list, {"ddd", "bbb"})), ["aaa"])
check("ID dokumen dibaca dari URL entry", mg.id_dari_url("https://x/s/p/dTU/entry"), "dTU")
check("URL bukan /entry -> tidak dianggap ID", mg.id_dari_url("https://x/y"), "")
check("dateCreated tidak terbaca -> jam kosong", mg.jam_dokumen("bukan tanggal"), "")

teks2 = mg.ringkas_tanpa_url([mg.catatan_tanpa_url(
    {"timestamp": "2026-09-23 23:10:00", "baris": 77, "nama_usaha": "WARUNG TANPA URL",
     "akun_login": "a@mail.com", "idsubsls_input": "51080", "status": mg.STATUS_TANPA_URL,
     "error_message": "jumlah dokumen 7 -> 8 || DRAFT di list yang belum tercatat: bbb '(tanpa nama)' @ 23:11"})])
check("laporan menyebut dokumen yang terbaca di list", "bbb" in teks2, True)

check("tanpa kejadian -> tidak ada laporan", mg.ringkas_tanpa_url([]), "")
with tempfile.TemporaryDirectory() as d:
    jalur = Path(d) / "tanpa_url.csv"
    mg.tulis_laporan_tanpa_url(laporan, jalur)
    isi = jalur.read_text(encoding="utf-8-sig")
    check("berkas laporan berisi barisnya", "WARUNG TANPA URL" in isi, True)
    mg.tulis_laporan_tanpa_url([], jalur)
    check("run bersih -> berkas laporan lama dihapus", jalur.exists(), False)

_cwd0 = __import__("os").getcwd()
with tempfile.TemporaryDirectory() as d:
    __import__("os").chdir(d)
    try:
        check("tanpa file stop", mg.berkas_stop("a@mail.com"), "")
        Path("STOP_a@mail.com").write_text("")
        check("STOP_<akun> hanya akun itu", (mg.berkas_stop("a@mail.com"), mg.berkas_stop("b@mail.com")),
              ("STOP_a@mail.com", ""))
        Path("STOP_GABUNGAN").write_text("")
        check("STOP_GABUNGAN semua akun", mg.berkas_stop("b@mail.com"), "STOP_GABUNGAN")
    finally:
        __import__("os").chdir(_cwd0)

# --- satu akun = satu proses (run 2026-09-14: 2 proses akun ppl.kedua saling memutus sesi) ---
import os
import subprocess
_cwd = os.getcwd()
with tempfile.TemporaryDirectory() as d:
    os.chdir(d)
    try:
        p1 = mg.kunci_proses_akun("Ab.C@mail.com")
        check("klaim pertama berhasil", p1 is not None and p1.exists(), True)
        mati = subprocess.Popen([sys.executable, "-c", "pass"])
        mati.wait()
        p1.write_text(f"{mati.pid} x\n", encoding="utf-8")
        check("kunci basi (PID mati) diambil alih", mg.kunci_proses_akun("ab.c@mail.com") is not None, True)
        hidup = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            p1.write_text(f"{hidup.pid} x\n", encoding="utf-8")
            check("akun dipakai proses lain yang hidup -> ditolak", mg.kunci_proses_akun("ab.c@mail.com"), None)
            check("akun lain tetap boleh", mg.kunci_proses_akun("lain@mail.com") is not None, True)
            check("proses yang dicek tidak ikut terbunuh", hidup.poll(), None)
        finally:
            hidup.kill()
            hidup.wait()
    finally:
        os.chdir(_cwd)

# --dari/--sampai: pembagian kerja antar-PC/proses per rentang baris sheet.
_rows = [GabunganRow(n, {}) for n in (2, 3, 7, 10, 11)]
check("--dari 3 --sampai 10 (kedua ujung ikut)", [r.baris for r in mg.saring_rentang(_rows, 3, 10)], [3, 7, 10])
check("--dari saja", [r.baris for r in mg.saring_rentang(_rows, 10, None)], [10, 11])
check("--sampai saja", [r.baris for r in mg.saring_rentang(_rows, None, 3)], [2, 3])
check("tanpa rentang = semua", len(mg.saring_rentang(_rows, None, None)), 5)

# --koordinat: bawaan per format & --lewati-selesai utk DRAFT_TANPA_KOORDINAT.
check("bawaan tahap2 = otomatis", mg.koordinat_otomatis(None, "tahap2"), True)
check("bawaan standar = wajib", mg.koordinat_otomatis(None, "standar"), False)
check("--koordinat wajib menang", mg.koordinat_otomatis("wajib", "tahap2"), False)
check("--koordinat otomatis menang", mg.koordinat_otomatis("otomatis", "standar"), True)
_tuntas = set(mg.STATUS_TERKIRIM)
check("draft tanpa koordinat, sheet masih kosong -> dilewati",
      mg.tuntas_menurut_audit(mg.STATUS_DRAFT_TANPA_KOORDINAT, _tuntas, punya_koordinat=False), True)
check("draft tanpa koordinat, koordinat SUDAH diisi -> diproses lagi (geotag + kirim)",
      mg.tuntas_menurut_audit(mg.STATUS_DRAFT_TANPA_KOORDINAT, _tuntas, punya_koordinat=True), False)
check("terkirim tetap dilewati", mg.tuntas_menurut_audit("TERKIRIM_TERVERIFIKASI", _tuntas, True), True)
check("error tetap diproses", mg.tuntas_menurut_audit("ERROR_LOGIN", _tuntas, False), False)

# --- --koordinat kirim: draft tanpa geotag ikut dikirim ---
from input_gabungan.main_gabungan import koordinat_dikirim, koordinat_otomatis  # noqa: E402

check("kirim: baris tanpa koordinat tetap diisi", koordinat_otomatis("kirim", "tahap2"), True)
check("kirim: dikirim, bukan ditahan draft", koordinat_dikirim("kirim"), True)
check("otomatis: ditahan draft", koordinat_dikirim("otomatis"), False)
check("wajib: bukan mode kirim", koordinat_dikirim("wajib"), False)
check("bawaan tahap2 bukan kirim", koordinat_dikirim(None), False)
# Draft tanpa koordinat TIDAK boleh dianggap tuntas di mode kirim — justru baris
# itulah yang mau diselesaikan jadi terkirim (main melewatkan punya_koordinat=True).
check("mode kirim: draft tanpa koordinat diproses lagi",
      mg.tuntas_menurut_audit("DRAFT_TANPA_KOORDINAT", set(mg.STATUS_TERKIRIM), True), False)
check("mode biasa: draft tanpa koordinat dianggap tuntas",
      mg.tuntas_menurut_audit("DRAFT_TANPA_KOORDINAT", set(mg.STATUS_TERKIRIM), False), True)

# --- --sinkron-dulu: audit diperbarui dari tabel server sebelum mengisi ---
class SesiTiruan:
    def __init__(self, items):
        self._items = items
        self.daftar_dokumen_lengkap = True

    def daftar_dokumen_api(self, assignment_id):
        return self._items


ditulis = []
asli_append = mg.append_audit
mg.append_audit = ditulis.append
try:
    # Daftar tidak terbaca -> JANGAN menulis apa pun & jangan menghentikan batch.
    n = mg.sinkron_audit_dari_server(SesiTiruan(None), [], {}, "x.xlsx", "a@x.com", "51080", "AID")
    check("list server tidak terbaca -> 0 catatan, batch lanjut", (n, len(ditulis)), (0, 0))
    # Daftar kosong -> tidak ada yang perlu ditulis (dan tidak error).
    n = mg.sinkron_audit_dari_server(SesiTiruan([]), [], {}, "x.xlsx", "a@x.com", "51080", "AID")
    check("list server kosong -> 0 catatan", (n, len(ditulis)), (0, 0))
finally:
    mg.append_audit = asli_append

# Draft yang ditandai galat server TIDAK boleh dianggap tuntas, walau barisnya
# belum punya koordinat — tanda itulah yang membuatnya dikerjakan lagi.
check("draft bergalat server selalu dikerjakan lagi",
      mg.tuntas_menurut_audit("DRAFT_GALAT_DI_SERVER", set(mg.STATUS_TERKIRIM), False), False)

# --- urutan kerja: galat server -> dokumen belum tuntas -> input baru ---
def giliran_urut(bertanda, punya, baris):
    """Tiruan urutan di main(): kunci = (giliran, nomor baris)."""
    def giliran(b):
        return 0 if b in bertanda else 1 if b in punya else 2
    return sorted(baris, key=lambda b: (giliran(b), b))

check("bertanda galat dikerjakan lebih dulu, input baru terakhir",
      giliran_urut({"c"}, {"b", "c"}, ["a", "b", "c"]), ["c", "b", "a"])
check("tanpa tanda galat: dokumen lama tetap didahulukan",
      giliran_urut(set(), {"b"}, ["a", "b", "c"]), ["b", "a", "c"])
check("urutan nomor baris dipertahankan dlm satu giliran",
      giliran_urut(set(), set(), [3, 1, 2]), [1, 2, 3])

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
