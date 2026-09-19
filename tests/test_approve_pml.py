"""Uji offline logika murni approve_pml.py (tanpa browser/VPN).
Jalankan: python tests/test_approve_pml.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py
import tempfile
from pathlib import Path

from approve_pml.approve_pml import (ST_OK, ST_SIAP, ST_SUDAH, ST_TANPA_AKSES, approve_satu, baca_rencana,
                                     baku_kode, cocokkan_list, dokumen_audit_ppl, gabung_target,
                                     id_sudah_approved, kelompokkan_per_pml, kode_halaman_error,
                                     kode_sudah_approved, nilai_dokumen, penolakan_akses, petugas_dokumen,
                                     subsls_audit_ppl, target_dari_daftar, target_dari_rencana)

U = "https://fasih-web.bps.go.id/survey/s/p/{}/entry"


def detail(alias, created="ppl.contoh@mail.com", updated="ppl.contoh@mail.com"):
    # Bentuk nyata: data.data adalah JSON STRING (respons get-by-id-with-data 2026-09-15).
    return {"assignment_status_alias": alias, "data1": "X",
            "data": json.dumps({"createdBy": created, "updatedBy": updated, "answers": []})}


def test_nilai_dokumen():
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah"), "ppl.contoh@mail.com") == (ST_SIAP, "SUBMITTED BY Pencacah")
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah"), "PPL.CONTOH@mail.com")[0] == ST_SIAP
    assert nilai_dokumen(detail("APPROVED BY Pengawas"), "ppl.contoh@mail.com")[0] == ST_SUDAH
    assert nilai_dokumen(detail("DRAFT"), "ppl.contoh@mail.com")[0] == "SKIP_STATUS_DRAFT"
    assert nilai_dokumen(detail("REJECTED BY Pengawas"), "ppl.contoh@mail.com")[0] == "SKIP_STATUS_REJECTED_BY_PENGAWAS"
    # Dokumen PPL lain di subsls yang sama TIDAK boleh ikut di-approve.
    k, pesan = nilai_dokumen(detail("SUBMITTED BY Pencacah", "lain@gmail.com", "lain@gmail.com"), "ppl.contoh@mail.com")
    assert k == "SKIP_BUKAN_PPL" and "lain@gmail.com" in pesan
    # updatedBy saja cukup (createdBy bisa akun lain kalau dokumen dibuat ulang).
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah", "x@y.z", "ppl.contoh@mail.com"), "ppl.contoh@mail.com")[0] == ST_SIAP
    assert nilai_dokumen(None, "ppl.contoh@mail.com")[0] == "SKIP_DETAIL_TIDAK_TERBACA"
    # data rusak -> tidak ada petugas -> bukan PPL
    assert nilai_dokumen({"assignment_status_alias": "SUBMITTED BY Pencacah", "data": "{rusak"},
                         "ppl.contoh@mail.com")[0] == "SKIP_BUKAN_PPL"


def test_penolakan_akses():
    # Bentuk nyata 2026-09-15 (akun pml.satu, dokumen DTSEN) & 403 kosong (akun pml.delapan).
    t23 = '{"success":false,"message":"Anda tidak memiliki akses ke dalam survey","data":null,"errorCode":23}'
    assert "tidak memiliki akses" in penolakan_akses(200, t23)
    assert penolakan_akses(403, "").startswith("HTTP 403")
    # Bukan penolakan -> tetap diulang sbg gangguan transien.
    assert penolakan_akses(200, '{"success":true,"data":{"_id":"x"}}') == ""
    assert penolakan_akses(0, "evaluate gagal") == ""
    assert penolakan_akses(504, "Gateway Timeout") == ""
    assert penolakan_akses(200, "<html>") == ""


def test_petugas_dokumen_dict():
    assert petugas_dokumen({"data": {"createdBy": "A@b.c", "updatedBy": ""}}) == {"a@b.c"}


def test_dokumen_audit_ppl():
    audit = [
        {"akun_login": "ppl.contoh@mail.com", "dokumen_url": U.format("d1"), "status": "DOKUMEN_DIBUAT", "baris": "1"},
        {"akun_login": "ppl.contoh@mail.com", "dokumen_url": U.format("d1"), "status": "TERKIRIM_TERVERIFIKASI", "baris": "1"},
        {"akun_login": "ppl.kedua@gmail.com", "dokumen_url": U.format("d2"), "status": "TERKIRIM_TERVERIFIKASI"},
        {"akun_login": "ppl.contoh@mail.com", "dokumen_url": U.format("d3"), "status": "DOKUMEN_DIBUAT"},
        {"akun_login": "ppl.contoh@mail.com", "dokumen_url": U.format("d3"), "status": "DOKUMEN_DIHAPUS"},
        {"akun_login": "ppl.contoh@mail.com", "dokumen_url": "", "status": "ERROR_LOGIN"},
    ]
    hasil = dokumen_audit_ppl(audit, "PPL.CONTOH@mail.com")
    assert list(hasil) == ["d1"]
    assert hasil["d1"]["status"] == "TERKIRIM_TERVERIFIKASI"


def test_subsls_audit_ppl():
    audit = [{"akun_login": "ppl.contoh@mail.com", "idsubsls_input": "5108010010000105"},
             {"akun_login": "ppl.contoh@mail.com", "idsubsls_input": ""},
             {"akun_login": "lain@mail.com", "idsubsls_input": "5108060014000403"}]
    assert subsls_audit_ppl(audit, "ppl.contoh@mail.com") == ["5108010010000105"]


def test_gabung_target():
    docs = {"d1": {"baris": "1", "kunci": "k1", "nama_usaha": "A"}}
    items = [{"id": "d1", "data1": "A"}, {"id": "d9", "data1": "B"}, {"id": "d9", "data1": "B"}]
    t = gabung_target(docs, items)
    assert [(x["id"], x["sumber"]) for x in t] == [("d1", "audit"), ("d9", "list")]
    assert gabung_target(docs, []) == [t[0]]


def baris_sqllab(pml, ppl, doc_id, nama="USAHA X"):
    # Header persis file SQL Lab 2026-09-15 (sqllab_assingment_selain_approve_*.xlsx).
    return {"PML": "NAMA " + pml[:3], "PPL": "NAMA " + ppl[:3], "Email PML": pml, "Email PPL": ppl,
            "assignment_id": doc_id, "code_identity": "5108070005000603 - DTSEN - 23",
            "level_6_full_code": "5108070005000603", "data1": nama, "data2": None,
            "assignment_status_alias": "SUBMITTED BY Pencacah"}


def test_target_dari_rencana():
    rows = [
        baris_sqllab("A@x.com", "p1@x.com", "d1"),
        baris_sqllab("b@x.com", "p2@x.com", "d2"),
        baris_sqllab("a@x.com ", "P3@x.com", "d3", nama=None),
        {k: None for k in baris_sqllab("a@x.com", "p1@x.com", "")},   # baris kosong: diam
        baris_sqllab("", "p1@x.com", "d4"),                             # PML kosong: dilaporkan
        baris_sqllab("a@x.com", "p1@x.com", "d1"),                     # duplikat identik: sekali
        baris_sqllab("b@x.com", "p2@x.com", "d5"),
        baris_sqllab("c@x.com", "p2@x.com", "d5"),                     # pasangan beda: gugur
        baris_sqllab("b@x.com", "p2@x.com", "d5"),
    ]
    target, masalah = target_dari_rencana(rows)
    assert [t["id"] for t in target] == ["d1", "d2", "d3"]
    assert target[0]["akun_pml"] == "a@x.com" and target[0]["akun_ppl"] == "p1@x.com"
    assert target[0]["baris"] == "2" and target[2]["baris"] == "4"      # nomor baris file (header = 1)
    assert target[2]["akun_ppl"] == "p3@x.com" and target[2]["nama"].startswith("5108")  # data1 kosong -> code_identity
    assert len(masalah) == 2 and "baris 6" in masalah[0] and "d5" in masalah[1]


def test_kelompokkan_per_pml():
    target, _ = target_dari_rencana([baris_sqllab("a@x.com", "p1@x.com", "d1"),
                                     baris_sqllab("b@x.com", "p2@x.com", "d2"),
                                     baris_sqllab("a@x.com", "p3@x.com", "d3")])
    k = kelompokkan_per_pml(target)
    assert [(p, [t["id"] for t in tg]) for p, tg in k] == [("a@x.com", ["d1", "d3"]), ("b@x.com", ["d2"])]
    assert [p for p, _ in kelompokkan_per_pml(target, ["B@x.com"])] == ["b@x.com"]
    assert kelompokkan_per_pml(target, ["z@x.com"]) == []


def test_id_sudah_approved():
    audit = [{"id": "d1", "status": ST_OK}, {"id": "d2", "status": "ERROR_FORM_TIDAK_MOUNT"},
             {"id": "d2", "status": ST_OK}, {"id": "d3", "status": ST_OK},
             {"id": "d3", "status": "APPROVE_TIDAK_TERVERIFIKASI"}, {"id": "", "status": "ERROR_LOGIN_PML"}]
    assert id_sudah_approved(audit) == {"d1", "d2"}   # status TERAKHIR yang menentukan


def test_baca_rencana_csv_dan_kolom_wajib():
    with tempfile.TemporaryDirectory() as d:
        ok = Path(d) / "r.csv"
        ok.write_text("﻿PML,Email PML,Email PPL,assignment_id\nX,a@x.com,p@x.com,d1\n", encoding="utf-8")
        rows = baca_rencana(ok)
        assert target_dari_rencana(rows)[0][0]["id"] == "d1"
        rusak = Path(d) / "rusak.csv"
        rusak.write_text("PML,Email PPL,assignment_id\nX,p@x.com,d1\n", encoding="utf-8")
        try:
            baca_rencana(rusak)
            raise AssertionError("kolom Email PML hilang harus ditolak")
        except ValueError as e:
            assert "Email PML" in str(e)


def test_nilai_dokumen_tanpa_cek_ppl():
    # --daftar: PPL tidak ada di file -> None mematikan cek petugas; "" tetap gagal-tertutup.
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah", "lain@x.com", "lain@x.com"), None)[0] == ST_SIAP
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah"), "")[0] == "SKIP_BUKAN_PPL"
    assert nilai_dokumen(detail("REJECTED BY Pengawas"), None)[0] == "SKIP_STATUS_REJECTED_BY_PENGAWAS"


def sel_sm(kode, nama="USAHA X", status="submitted by pencacah", mode="PAPI", pml="pml.satu@gmail.com",
           email_usaha="-"):
    # Bentuk nyata baris submit.xlsx 2026-09-15 (16 sel; header bergeser): kolom 6 = Email USAHA.
    return [None, kode, nama, "-", "36 /", "-", email_usaha, "-", 1, 81119, "-", "-", status, mode, pml, "-"]


HEADER_SM = [None, "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist", "Nomor Urut Bangunan / IDSBR", "NIB / No. KK",
             "Email", "Skala Usaha / Jenis Prelist", "Jumlah Usaha", "Kode Pos", "Perubahan SLS",
             "IDSBR UMKM SLS Sama", "Status", "Mode", "Petugas Saat Ini", "Keterangan", None]


def test_target_dari_daftar():
    rows = [
        HEADER_SM,
        sel_sm("5108060005000103 - BAGJA GORDEN - 36 / - - - 1 - 81119", pml="Pml.Tiga@gmail.com"),
        sel_sm("5108070005000602 - UMK - 8", email_usaha="usaha@gmail.com"),   # email usaha BUKAN petugas
        [None] * 16,                                                           # baris kosong: diam
        sel_sm("5108060005000405 - UMK - 20", status="rejected by pengawas", pml="arya@gmail.com"),
        sel_sm("5108070005000603 - DTSEN - 1", mode="CAPI"),
        sel_sm("5108070005000603 - DTSEN - 2", pml="-"),
        sel_sm("5108070005000602  -  UMK - 8"),                                # duplikat identik (spasi): sekali
        sel_sm("5108070013000103 - UMK - 32", pml="a@x.com"),
        sel_sm("5108070013000103 - UMK - 32", pml="b@x.com"),                  # PML beda: gugur
    ]
    target, masalah = target_dari_daftar(rows)
    assert [t["kode"] for t in target] == ["5108060005000103 - BAGJA GORDEN - 36 / - - - 1 - 81119",
                                           "5108070005000602 - UMK - 8"]
    assert target[0]["akun_pml"] == "pml.tiga@gmail.com" and target[0]["baris"] == "2"
    assert target[1]["akun_pml"] == "pml.satu@gmail.com" and target[1]["nama"] == "USAHA X"
    assert target[0]["akun_ppl"] is None and target[0]["id"] == "" and target[0]["kunci"] == target[0]["kode"]
    assert len(masalah) == 4, masalah
    assert "rejected" in masalah[0] and "CAPI" in masalah[1] and "bukan email" in masalah[2] and "UMK - 32" in masalah[3]


def test_cocokkan_list():
    target, _ = target_dari_daftar([sel_sm("5108070005000602 - UMK - 8"), sel_sm("5108070005000602 - UMK - 9"),
                                    sel_sm("5108070005000602 - UMK - 10"), sel_sm("5108070005000602 - UMK - 11"),
                                    sel_sm("5108070005000602 - UMK - 12"), sel_sm("5108070005000602 - UMK - 13")])
    pml = "pml.satu@gmail.com"

    def item(i, kode, pemegang=pml, mode=("PAPI",), alias="SUBMITTED BY Pencacah"):
        return {"id": i, "codeIdentity": kode, "currentUserUsername": pemegang, "mode": list(mode),
                "assignmentStatusAlias": alias, "data1": "NAMA " + i}
    items = [item("d8", "5108070005000602 - umk - 8"),                     # beda huruf besar/kecil: tetap cocok
             item("d80", "5108070005000602 - UMK - 80"),                   # "- 8" BUKAN "- 80"
             item("d9a", "5108070005000602 - UMK - 9"), item("d9b", "5108070005000602 - UMK - 9"),
             item("d10", "5108070005000602 - UMK - 10", pemegang="ppl@gmail.com"),
             item("d11", "5108070005000602 - UMK - 11", mode=("CAPI",)),
             item("d12", "5108070005000602 - UMK - 12", pemegang="admin@bps.go.id", alias="APPROVED BY Pengawas")]
    h = {t["kode"][-2:].strip(" -"): t for t in cocokkan_list(target, items, pml)}
    assert h["8"]["id"] == "d8" and "status" not in h["8"]
    assert h["9"]["status"] == "SKIP_KODE_GANDA"
    assert h["10"]["status"] == "SKIP_BUKAN_PML_SAAT_INI" and "ppl@gmail.com" in h["10"]["pesan"]
    assert h["11"]["status"] == "SKIP_MODE_BUKAN_PAPI"
    assert h["12"]["id"] == "d12" and "status" not in h["12"]   # sudah APPROVED: diputuskan API detail
    assert h["13"]["status"] == "SKIP_KODE_TIDAK_DI_LIST"
    assert "status" not in target[0]                             # target asli tidak diubah


def test_kode_sudah_approved():
    audit = [{"sumber": "daftar", "kunci": "5108 - UMK - 1", "status": ST_OK},
             {"sumber": "daftar", "kunci": "5108 - UMK - 2", "status": ST_OK},
             {"sumber": "daftar", "kunci": "5108  -  UMK - 2", "status": "ERROR_FORM_TIDAK_MOUNT"},
             {"sumber": "daftar", "kunci": "5108 - UMK - 3", "status": ST_SUDAH},
             {"sumber": "audit", "kunci": "k-agenda", "status": ST_OK}]
    assert kode_sudah_approved(audit) == {baku_kode("5108 - UMK - 1"), baku_kode("5108 - UMK - 3")}


def test_kode_halaman_error():
    # Teks halaman galat nyata (screenshot approve_form_tidak_mount 2026-09-15).
    assert kode_halaman_error("Terjadi Kesalahan (504)\nService unavailable.\nStatus Code: 504") == 504
    assert kode_halaman_error("Status Code: 502") == 502
    assert kode_halaman_error("PENGANTAR SE2026 bertujuan ...") == 0


class _Loc:
    def __init__(self):
        self.first = self

    def wait_for(self, **kw):
        pass


class _PageTiruan:
    """Cukup utk jalur approve_satu yang TIDAK membuka dokumen / cuma membuka ulang (fallback)."""
    def __init__(self, respons):
        self.respons = list(respons)
        self.goto_ke = []

    def evaluate(self, script, arg=None):
        return self.respons.pop(0) if len(self.respons) > 1 else self.respons[0]

    def goto(self, url, **kw):
        self.goto_ke.append(url)

    def locator(self, sel):
        return _Loc()

    def wait_for_load_state(self, *a, **kw):
        pass

    def wait_for_timeout(self, ms):
        pass


class _SesiTiruan:
    def __init__(self, respons):
        self.page = _PageTiruan(respons)
        self.log = []

    def _log(self, m):
        self.log.append(m)

    def _shot(self, nama):
        pass


def _ok(d):
    return {"status": 200, "text": json.dumps({"success": True, "data": d})}


def test_approve_satu_tanpa_membuka_dokumen():
    # Regresi merge 6338cad: `info` hilang -> NameError di SETIAP dokumen.
    t = {"id": "d1", "baris": "2", "kunci": "", "nama": "", "sumber": "rencana", "akun_pml": "p@x.com",
         "akun_ppl": "ppl.contoh@mail.com"}
    t23 = '{"success":false,"message":"Anda tidak memiliki akses ke dalam survey","data":null,"errorCode":23}'
    s = _SesiTiruan([{"status": 200, "text": t23}])
    r = approve_satu(s, t, "periode", "ppl.contoh@mail.com", eksekusi=False)
    assert r["status"] == ST_TANPA_AKSES and "tidak memiliki akses" in r["pesan"]
    assert s.page.goto_ke == []                                   # penolakan: dokumen tidak dibuka
    s = _SesiTiruan([_ok(detail("APPROVED BY Pengawas"))])
    r = approve_satu(s, t, "periode", "ppl.contoh@mail.com", eksekusi=False)
    assert r["status"] == ST_SUDAH and r["nama"] == "X"
    # Detail kosong 4x (halaman redirect) -> dokumen dibuka SEKALI lalu dibaca ulang (8565f61).
    s = _SesiTiruan([{"status": 0, "text": "evaluate gagal"}] * 4 + [_ok(detail("SUBMITTED BY Pencacah", "l@x.com", "l@x.com"))])
    r = approve_satu(s, t, "periode", "ppl.contoh@mail.com", eksekusi=False)
    assert r["status"] == "SKIP_BUKAN_PPL" and len(s.page.goto_ke) == 1
    # --daftar (akun_ppl None): petugas dokumen dicatat di kolom akun_ppl audit.
    s = _SesiTiruan([_ok(detail("REJECTED BY Pengawas", "a@x.com", "b@x.com"))])
    r = approve_satu(s, {**t, "akun_ppl": None, "sumber": "daftar"}, "periode", None, eksekusi=False)
    assert r["status"] == "SKIP_STATUS_REJECTED_BY_PENGAWAS" and r["akun_ppl"] == "a@x.com,b@x.com"


def test_jalankan_semua_pml():
    """Orkestrasi multi PML tanpa browser: tiap PML context baru + login, --daftar dipetakan ke id
    di sesi PML itu, logout + tutup context SETIAP PML (termasuk yang berhenti/error), login gagal
    dilewati tanpa NameError, STOP menghentikan seluruh run."""
    import types
    import approve_pml.approve_pml as m

    jejak, audit_tulis = [], []

    class Ctx:
        def __init__(self, akun):
            self.akun = akun

        def close(self):
            jejak.append(("tutup", self.akun))

    class Sesi:
        def __init__(self, akun):
            self.akun = akun

        def logout(self):
            jejak.append(("logout", self.akun))

    def mulai(browser, akun, manual, file_sesi):
        jejak.append(("login", akun, file_sesi))
        if akun == "gagal@x.com":
            raise RuntimeError("Login gagal: masih di halaman login")
        return Ctx(akun), Sesi(akun)

    def siapkan(sess, target, akun, assignment_id):
        jejak.append(("siapkan", sess.akun, akun))
        return [{**t, "id": "id-" + t["kode"][-1]} for t in target]

    def proses(sess, akun, target, args, hitung, file_sesi):
        jejak.append(("proses", sess.akun, [t["id"] for t in target]))
        hitung[m.ST_OK] += len(target)
        if akun == "stop@x.com":
            return "STOP_DIALOG_TIDAK_MUNCUL"
        if akun == "meledak@x.com":
            raise RuntimeError("Target page, context or browser has been closed")
        return ""

    asli = {n: getattr(m, n) for n in ("mulai_sesi_pml", "siapkan_target_daftar", "proses_kelompok",
                                        "append_audit", "simpan_sesi")}
    m.mulai_sesi_pml, m.siapkan_target_daftar, m.proses_kelompok = mulai, siapkan, proses
    m.append_audit, m.simpan_sesi = audit_tulis.append, (lambda s, f: None)
    try:
        args = types.SimpleNamespace(daftar="submit.xlsx", rencana=None, login_manual=False,
                                     assignment_id="periode", termasuk_di_luar_audit=False)
        tg = lambda *kode: [{"kode": "5108 - UMK - " + k, "id": ""} for k in kode]
        kelompok = [("gagal@x.com", tg("1")), ("a@x.com", tg("2", "3")), ("b@x.com", tg("4"))]
        hitung, kode = m.jalankan_semua_pml(None, kelompok, args, [], {}, "")
        assert kode == 1 and hitung["ERROR_LOGIN_PML"] == 1 and hitung[m.ST_OK] == 3
        assert audit_tulis[0]["status"] == "ERROR_LOGIN_PML" and audit_tulis[0]["akun_pml"] == "gagal@x.com"
        assert jejak == [
            ("login", "gagal@x.com", None),                                   # multi PML: tanpa file sesi
            ("login", "a@x.com", None), ("siapkan", "a@x.com", "a@x.com"),
            ("proses", "a@x.com", ["id-2", "id-3"]), ("logout", "a@x.com"), ("tutup", "a@x.com"),
            ("login", "b@x.com", None), ("siapkan", "b@x.com", "b@x.com"),
            ("proses", "b@x.com", ["id-4"]), ("logout", "b@x.com"), ("tutup", "b@x.com"),
        ], jejak

        # STOP & exception: sesi tetap ditutup, PML berikutnya TIDAK login.
        for akun_henti in ("stop@x.com", "meledak@x.com"):
            jejak.clear()
            audit_tulis.clear()
            hitung, kode = m.jalankan_semua_pml(None, [(akun_henti, tg("5")), ("c@x.com", tg("6"))], args, [], {}, "")
            assert kode == 1 and ("logout", akun_henti) in jejak and ("tutup", akun_henti) in jejak
            assert not any(j[0] == "login" and j[1] == "c@x.com" for j in jejak), jejak
        assert audit_tulis and audit_tulis[0]["status"] == "ERROR_TAK_TERDUGA"

        # Satu PML: file sesi dipakai & TIDAK logout (sesi disimpan utk run berikutnya).
        jejak.clear()
        m.jalankan_semua_pml(None, [("a@x.com", tg("7"))], args, [], {}, "")
        assert jejak[0][2] is not None and ("logout", "a@x.com") not in jejak and ("tutup", "a@x.com") in jejak
    finally:
        for n, f in asli.items():
            setattr(m, n, f)


if __name__ == "__main__":
    for nama, fn in list(globals().items()):
        if nama.startswith("test_") and callable(fn):
            fn()
            print(f"OK {nama}")
    print("Semua test lulus.")
