"""Uji offline logika murni approve_pml.py (tanpa browser/VPN).
Jalankan: python tests/test_approve_pml.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from approve_pml.approve_pml import (ST_SIAP, ST_SUDAH, dokumen_audit_ppl, gabung_target, nilai_dokumen,
                                     petugas_dokumen, subsls_audit_ppl)

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


if __name__ == "__main__":
    for nama, fn in list(globals().items()):
        if nama.startswith("test_") and callable(fn):
            fn()
            print(f"OK {nama}")
    print("Semua test lulus.")
