# -*- coding: utf-8 -*-
"""Uji logika murni sinkron_list.rencana_sinkron — offline, tanpa browser.
Jalankan: python tests/test_sinkron_list.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import input_gabungan.main_gabungan as mg
from input_gabungan.sinkron_list import id_dari_url, rencana_sinkron, status_server, url_entry
from inti.gabungan_loader import GabunganRow

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


AKUN, SUBSLS, ASG = "m@mail.com", "5108060014000403", "asg"


def row(baris, nama, pemilik="I MADE"):
    return GabunganRow(baris, {"akun_ppl": "ppl@gmail.com", "idsubsls": "5108010002000501", "nama": nama,
                               "pengusaha": pemilik, "kbli": "86201"})


def doc(i, nama, status, jam="2026-09-14T13:51:06.000+00:00"):
    return {"id": i, "data1": nama.upper(), "assignmentStatusAlias": status, "dateCreated": jam}


r_kirim, r_draft, r_belum, r_ganda, r_96, r_lain = (
    row(2, "APOTEK A"), row(3, "APOTEK B"), row(4, "APOTEK C"), row(5, "APOTEK D"), row(96, "PANGKALAN E"),
    row(7, "APOTEK F"))
items = [
    doc("id-kirim", "APOTEK A (I MADE)", "SUBMITTED BY Pencacah"),
    doc("id-draft", "APOTEK B (i  made)", "DRAFT"),  # beda huruf besar & spasi tetap cocok
    doc("id-g1", "APOTEK D (I MADE)", "SUBMITTED BY Pencacah"),
    doc("id-g2", "APOTEK D (I MADE)", "SUBMITTED BY Pencacah"),
    doc("id-96", "PANGKALAN E (I MADE)", "DRAFT"),
    doc("id-f", "APOTEK F (I MADE)", "SUBMITTED BY Pencacah"),
    doc("id-asing", "PETRONELA", "SUBMITTED BY Pencacah"),
]
audit = [
    {"kunci": r_ganda.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN, "dokumen_url": url_entry("id-g1", ASG)},
    {"kunci": r_ganda.kunci, "status": "SKIP_GALAT_PERLU_REVIEW", "akun_login": AKUN},
    {"kunci": r_96.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN, "dokumen_url": url_entry("id-96", ASG)},
    {"kunci": r_96.kunci, "status": "TERKIRIM_BELUM_TERVERIFIKASI", "akun_login": AKUN},
    {"kunci": r_lain.kunci, "status": mg.STATUS_DIBUAT, "akun_login": "ppl.contoh@mail.com", "dokumen_url": "x"},
]
sumber = [("S.xlsx", r, "SIAP") for r in (r_kirim, r_draft, r_belum, r_ganda, r_96, r_lain)]
laporan, tulis, tak = rencana_sinkron(sumber, items, AKUN, SUBSLS, ASG, audit)
kat = {l["baris"]: l["kategori"] for l in laporan}
check("kategori", kat, {2: "TERKIRIM", 3: "DRAFT", 4: "BELUM_ADA", 5: "TERKIRIM+GANDA",
                        96: "DRAFT", 7: "DI_AKUN_LAIN+GANDA_LINTAS_AKUN"})
per = {}
for t in tulis:
    per.setdefault(t["baris"], []).append((t["status"], id_dari_url(t["dokumen_url"])))
check("terkirim di luar audit -> DOKUMEN_DIBUAT + TERKIRIM_TERVERIFIKASI", per.get(2),
      [(mg.STATUS_DIBUAT, "id-kirim"), ("TERKIRIM_TERVERIFIKASI", "id-kirim")])
check("draft di luar audit -> DOKUMEN_DIBUAT saja (dibuka lewat URL, tidak dibuat baru)", per.get(3),
      [(mg.STATUS_DIBUAT, "id-draft")])
check("belum ada -> tidak menulis apa pun", per.get(4), None)
check("ganda: dokumen yang belum tercatat ikut dicatat + terkirim", per.get(5),
      [(mg.STATUS_DIBUAT, "id-g2"), ("TERKIRIM_TERVERIFIKASI", "id-g1")])
check("audit terkirim tapi server DRAFT (baris 96) -> DRAFT_DI_SERVER", per.get(96),
      [("DRAFT_DI_SERVER", "id-96")])
check("DRAFT_DI_SERVER bukan status terkirim", "DRAFT_DI_SERVER" in mg.STATUS_TERKIRIM, False)
check("dokumen milik akun lain di audit -> tidak ditulis", per.get(7), None)
check("dokumen server tak dikenal dilaporkan", [i["id"] for i in tak], ["id-asing"])
check("akun_login & subsls input = akun tunggal", {(t["akun_login"], t["idsubsls_input"]) for t in tulis},
      {(AKUN, SUBSLS)})

# Kasus nyata 2026-09-15 (Agenda1-1 baris 10): audit sudah DOKUMEN_TERKUNCI, program lain membuat
# duplikat terkirim. DOKUMEN_DIBUAT duplikat tidak boleh jadi status terakhir.
audit_t = [{"kunci": r_kirim.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN, "dokumen_url": url_entry("id-lama", ASG)},
           {"kunci": r_kirim.kunci, "status": mg.STATUS_TERKUNCI, "akun_login": AKUN}]
items_t = [doc("id-lama", "APOTEK A (I MADE)", "SUBMITTED BY Pencacah"),
           doc("id-baru", "APOTEK A (I MADE)", "SUBMITTED BY Pencacah")]
_, tulis_t, _ = rencana_sinkron([("S", r_kirim, "SIAP")], items_t, AKUN, SUBSLS, ASG, audit_t)
check("duplikat terkirim dicatat & status terakhir tetap terkirim",
      [(t["status"], id_dari_url(t["dokumen_url"])) for t in tulis_t],
      [(mg.STATUS_DIBUAT, "id-baru"), ("TERKIRIM_TERVERIFIKASI", "id-lama")])
audit_t2 = audit_t + [{"kunci": r_kirim.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN,
                       "dokumen_url": url_entry("id-baru", ASG)}]
_, tulis_t2, _ = rencana_sinkron([("S", r_kirim, "SIAP")], items_t, AKUN, SUBSLS, ASG, audit_t2)
check("perbaikan audit yang sudah salah (sinkron diulang) -> status terkirim ditulis",
      [t["status"] for t in tulis_t2], ["TERKIRIM_TERVERIFIKASI"])
_, tulis_t3, _ = rencana_sinkron([("S", r_kirim, "SIAP")], items_t, AKUN, SUBSLS, ASG,
                                 audit_t2 + [{"kunci": r_kirim.kunci, "status": "TERKIRIM_TERVERIFIKASI"}])
check("sinkron idempoten (tidak menulis apa pun lagi)", tulis_t3, [])

# Kasus nyata 2026-09-15 (Agenda baris 85): list bergeser saat dibaca -> id sama 2x, BUKAN ganda.
lap_d, _, _ = rencana_sinkron([("S", r_kirim, "SIAP")], [items[0], dict(items[0])], AKUN, SUBSLS, ASG, [])
check("id sama terbaca dua kali bukan GANDA", lap_d[0]["kategori"], "TERKIRIM")

# Kasus nyata 2026-09-15 (Agenda1-1 baris 88): dokumen terkunci dihapus admin -> DOKUMEN_DIHAPUS.
audit_h = [{"kunci": r_belum.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN, "dokumen_url": url_entry("id-dihapus", ASG)},
           {"kunci": r_belum.kunci, "status": mg.STATUS_TERKUNCI, "akun_login": AKUN}]
lap_h, tulis_h, _ = rencana_sinkron([("S", r_belum, "SIAP")], items, AKUN, SUBSLS, ASG, audit_h, lengkap=True)
check("dokumen audit tidak ada di list lengkap -> DOKUMEN_DIHAPUS",
      ([(t["status"], id_dari_url(t["dokumen_url"])) for t in tulis_h], lap_h[0]["kategori"]),
      ([(mg.STATUS_DIHAPUS, "id-dihapus")], "BELUM_ADA+DOKUMEN_AUDIT_DIHAPUS"))
_, tulis_h2, _ = rencana_sinkron([("S", r_belum, "SIAP")], items, AKUN, SUBSLS, ASG, audit_h, lengkap=False)
check("list tidak terbukti lengkap (--dari-json/bergeser) -> TIDAK menulis DOKUMEN_DIHAPUS", tulis_h2, [])
_, tulis_h3, _ = rencana_sinkron([("S", r_belum, "SIAP")], items, AKUN, SUBSLS, ASG,
                                 audit_h + tulis_h, lengkap=True)
check("sinkron diulang sesudah DOKUMEN_DIHAPUS -> idempoten", tulis_h3, [])

# Kasus nyata 2026-09-15: Agenda2 baris 267 bernama sama dgn dokumen Agenda baris 108 (usaha berbeda).
r_267 = GabunganRow(267, {"akun_ppl": "lain@gmail.com", "idsubsls": "5108060021000113", "nama": "APOTEK A",
                          "pengusaha": "I MADE", "kbli": "47772"})
audit_n = [{"kunci": r_kirim.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN, "dokumen_url": url_entry("id-kirim", ASG)}]
lap_n, tulis_n, _ = rencana_sinkron([("A2", r_267, "SIAP")], items, AKUN, SUBSLS, ASG, audit_n, lengkap=True)
check("dokumen bernama sama milik kunci lain -> bukan milik baris ini, tidak ditulis",
      (lap_n[0]["kategori"], tulis_n), ("BELUM_ADA+NAMA_DIPAKAI_BARIS_LAIN", []))

# Dua DRAFT bernama sama & tidak ada yang terkirim: jangan menebak.
_, tulis2, _ = rencana_sinkron([("S", r_draft, "SIAP")],
                               [doc("d1", "APOTEK B (I MADE)", "DRAFT"), doc("d2", "APOTEK B (I MADE)", "DRAFT")],
                               AKUN, SUBSLS, ASG, [])
check("dua DRAFT bernama sama -> tidak ditulis", tulis2, [])

check("status_server", [status_server(s) for s in ("DRAFT", "SUBMITTED BY Pencacah", "APPROVED BY PML", "REJECTED")],
      ["DRAFT", "TERKIRIM", "TERKIRIM", "LAIN"])

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
