"""Uji offline logika murni approve_pml.py (tanpa browser/VPN).
Jalankan: python tests/test_approve_pml.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile
from pathlib import Path

from approve_pml.approve_pml import (ST_OK, ST_SIAP, ST_SUDAH, baca_rencana, dokumen_audit_ppl, gabung_target,
                                     id_sudah_approved, kelompokkan_per_pml, nilai_dokumen, penolakan_akses,
                                     petugas_dokumen,
                                     subsls_audit_ppl, target_dari_rencana)

U = "https://fasih-web.bps.go.id/survey/s/p/{}/entry"


def detail(alias, created="wisada9@mail.com", updated="wisada9@mail.com"):
    # Bentuk nyata: data.data adalah JSON STRING (respons get-by-id-with-data 2026-09-15).
    return {"assignment_status_alias": alias, "data1": "X",
            "data": json.dumps({"createdBy": created, "updatedBy": updated, "answers": []})}


def test_nilai_dokumen():
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah"), "wisada9@mail.com") == (ST_SIAP, "SUBMITTED BY Pencacah")
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah"), "WISADA9@mail.com")[0] == ST_SIAP
    assert nilai_dokumen(detail("APPROVED BY Pengawas"), "wisada9@mail.com")[0] == ST_SUDAH
    assert nilai_dokumen(detail("DRAFT"), "wisada9@mail.com")[0] == "SKIP_STATUS_DRAFT"
    assert nilai_dokumen(detail("REJECTED BY Pengawas"), "wisada9@mail.com")[0] == "SKIP_STATUS_REJECTED_BY_PENGAWAS"
    # Dokumen PPL lain di subsls yang sama TIDAK boleh ikut di-approve.
    k, pesan = nilai_dokumen(detail("SUBMITTED BY Pencacah", "lain@gmail.com", "lain@gmail.com"), "wisada9@mail.com")
    assert k == "SKIP_BUKAN_PPL" and "lain@gmail.com" in pesan
    # updatedBy saja cukup (createdBy bisa akun lain kalau dokumen dibuat ulang).
    assert nilai_dokumen(detail("SUBMITTED BY Pencacah", "x@y.z", "wisada9@mail.com"), "wisada9@mail.com")[0] == ST_SIAP
    assert nilai_dokumen(None, "wisada9@mail.com")[0] == "SKIP_DETAIL_TIDAK_TERBACA"
    # data rusak -> tidak ada petugas -> bukan PPL
    assert nilai_dokumen({"assignment_status_alias": "SUBMITTED BY Pencacah", "data": "{rusak"},
                         "wisada9@mail.com")[0] == "SKIP_BUKAN_PPL"


def test_penolakan_akses():
    # Bentuk nyata 2026-09-15 (akun munimaha, dokumen DTSEN) & 403 kosong (akun dicky).
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
        {"akun_login": "wisada9@mail.com", "dokumen_url": U.format("d1"), "status": "DOKUMEN_DIBUAT", "baris": "1"},
        {"akun_login": "wisada9@mail.com", "dokumen_url": U.format("d1"), "status": "TERKIRIM_TERVERIFIKASI", "baris": "1"},
        {"akun_login": "megakartika@gmail.com", "dokumen_url": U.format("d2"), "status": "TERKIRIM_TERVERIFIKASI"},
        {"akun_login": "wisada9@mail.com", "dokumen_url": U.format("d3"), "status": "DOKUMEN_DIBUAT"},
        {"akun_login": "wisada9@mail.com", "dokumen_url": U.format("d3"), "status": "DOKUMEN_DIHAPUS"},
        {"akun_login": "wisada9@mail.com", "dokumen_url": "", "status": "ERROR_LOGIN"},
    ]
    hasil = dokumen_audit_ppl(audit, "WISADA9@mail.com")
    assert list(hasil) == ["d1"]
    assert hasil["d1"]["status"] == "TERKIRIM_TERVERIFIKASI"


def test_subsls_audit_ppl():
    audit = [{"akun_login": "wisada9@mail.com", "idsubsls_input": "5108010010000105"},
             {"akun_login": "wisada9@mail.com", "idsubsls_input": ""},
             {"akun_login": "lain@mail.com", "idsubsls_input": "5108060014000403"}]
    assert subsls_audit_ppl(audit, "wisada9@mail.com") == ["5108010010000105"]


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


if __name__ == "__main__":
    for nama, fn in list(globals().items()):
        if nama.startswith("test_") and callable(fn):
            fn()
            print(f"OK {nama}")
    print("Semua test lulus.")
