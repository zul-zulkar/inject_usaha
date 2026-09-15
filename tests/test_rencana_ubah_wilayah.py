# -*- coding: utf-8 -*-
"""Uji logika murni rencana_ubah_wilayah — offline, tanpa browser & tanpa file peta asli.
Jalankan: python tests/test_rencana_ubah_wilayah.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from input_gabungan.rencana_ubah_wilayah import (
    _akun_dari_nama_file, peta_dari_fitur, perubahan_nama, rencana_ubah_wilayah,
)
from input_gabungan.sinkron_list import url_entry
from inti.gabungan_loader import GabunganRow

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


def kotak(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


A, B, INPUT = "5108010001000101", "5108010002000301", "5108060014000403"
peta = peta_dari_fitur([
    {"properties": {"idsubsls": A, "nmkec": "GEROKGAK", "nmdesa": "SATU", "nmsls": "BANJAR A"},
     "geometry": {"type": "Polygon", "coordinates": [kotak(0, 0, 1, 1), kotak(0.4, 0.4, 0.6, 0.6)]}},  # berlubang
    {"properties": {"idsubsls": B, "nmkec": "GEROKGAK", "nmdesa": "DUA", "nmsls": "BANJAR B"},
     "geometry": {"type": "MultiPolygon", "coordinates": [[kotak(2, 0, 3, 1)], [kotak(0.45, 0.45, 0.55, 0.55)]]}},
    {"properties": {"idsubsls": INPUT}, "geometry": {"type": "Polygon", "coordinates": [kotak(5, 5, 6, 6)]}},
])

# --- peta -------------------------------------------------------------------
check("titik di A", peta.titik(0.2, 0.2), [A])
check("titik di lubang A = pulau B", peta.titik(0.5, 0.5), [B])
check("titik di lubang A di luar pulau B", peta.titik(0.42, 0.42), [])
check("titik di luar semua", peta.titik(10, 10), [])
check("jarak 0 kalau di dalam", peta.jarak_m(A, 0.2, 0.2), 0.0)
check("jarak ±111 m ke tepi atas A", round(peta.jarak_m(A, 0.5, 1.001)), 111)
check("jarak subsls tak dikenal", peta.jarak_m("x", 0, 0), None)
check("nama wilayah", peta.nama(A), "[010] GEROKGAK | [001] SATU | [0001] BANJAR A | sub [01]")
check("akun dari nama file", _akun_dari_nama_file(Path("list_api_mega.k_at_gmail.com.json")), "mega.k@gmail.com")
check("nama file lain", _akun_dari_nama_file(Path("daftar.json")), "")


# --- perubahan nama ------------------------------------------------------------
def row(baris, nama, pemilik="I MADE", tujuan=A, pilih=None, titik=(0.2, 0.2), **lain):
    pilih = pilih or tujuan
    v = {"akun_ppl": "ppl@gmail.com", "idsubsls": tujuan, "nama": nama, "pengusaha": pemilik, "kbli": "47772",
         "nama_komersial": nama, "jalan_domisili": "JALAN RAYA SERIRIT", "longitude": str(titik[0]),
         "latitude": str(titik[1]), "pilih_prov": pilih[:2], "pilih_kab": pilih[2:4], "pilih_kec": pilih[4:7],
         "pilih_desa": pilih[7:10], "pilih_sls": pilih[10:14], "pilih_subsls": pilih[14:16]}
    v.update(lain)
    return GabunganRow(baris, v)


check("12a sudah di nama", perubahan_nama(row(1, "PANGKALAN GAS JAMALUDIN", "JAMALUDIN")),
      ["nama 12a yang sudah tertulis di nama dipindah ke dalam kurung"])
check("12a bagian kata lain = ditambahkan", perubahan_nama(row(1, "APOTEK MADEWI", "MADE")),
      ["nama 12a ditambahkan dalam kurung"])
check("tidak berubah", perubahan_nama(row(1, "PRAKTIK BIDAN IBU (Damiasih)", "Damiasih")), [])
check("nama = 12a", perubahan_nama(row(1, "PARKTIK DOKTER BAYU", "Parktik Dokter Bayu")),
      ["nama usaha hanya berisi nama 12a -> ditulis '(12a)'"])
check("kurung asli dibuang", perubahan_nama(row(1, "APOTEK (SEHAT) JAYA", "MADE")),
      ["nama 12a ditambahkan dalam kurung", "kurung asli di nama dibuang (isinya dipertahankan)"])
r_pt = row(1, "PT. PAWARTA", "Penanggung Jawab")
r_pt.akhiran_badan = "PT"
check("PT pindah", perubahan_nama(r_pt), ["'PT' dipindah ke belakang nama", "nama 12a ditambahkan dalam kurung"])
check("KOREKSI_NAMA + tanpa 12a", perubahan_nama(row(1, "PUSKESMAS PEMBANTU MUNDUK", "Bidan/Perawat Penanggung Jawab Pustu")),
      ["nama diganti ketetapan user (KOREKSI_NAMA)", "tanpa (12a): '<nama> (<12a>)' lebih dari 50 karakter"])

# --- rencana ------------------------------------------------------------------
MEGA, WIS, ASG = "mega@gmail.com", "wis@mail.com", "asg"
TERKIRIM = "SUBMITTED BY Pencacah"
rows = {
    "siap": row(2, "APOTEK SIAP"),
    "titik_beda": row(3, "APOTEK TITIK", titik=(2.5, 0.5)),
    "pilih_sepakat": row(4, "APOTEK PILIH", pilih=B, titik=(2.5, 0.5)),
    "pilih_salah": row(5, "APOTEK PILIHSALAH", pilih=B),
    "luar": row(6, "APOTEK LUAR", titik=(0.5, 1.001)),
    "ganda": row(7, "APOTEK GANDA"),
    "draft": row(8, "APOTEK DRAFT"),
    "wis": row(9, "APOTEK WIS"),
    "lewat_nama": row(10, "APOTEK NAMA"),
    "hilang": row(11, "APOTEK HILANG"),
    "di_tujuan": row(12, "APOTEK TUJUAN", tujuan=INPUT, titik=(5.5, 5.5)),
    "belum": row(13, "APOTEK BELUM"),
    "tak_ada_di_peta": row(14, "APOTEK PETA", tujuan="5108990000000000", titik=(0.2, 0.2)),
}
lain_sumber = row(99, "APOTEK SHEET LAIN")


def doc(i, r, status=TERKIRIM, subsls=INPUT, nama=None):
    return {"id": i, "data1": (nama or r.nama_dokumen).upper(), "assignmentStatusAlias": status,
            "codeIdentity": f"{subsls} - {nama or r.nama_dokumen}"}


def aud(i, r, akun=MEGA, status="DOKUMEN_DIBUAT"):
    return {"kunci": r.kunci, "status": status, "akun_login": akun, "idsubsls_input": INPUT,
            "dokumen_url": url_entry(i, ASG), "nama_usaha": r.nama_dokumen}


audit = [aud(k, r) for k, r in rows.items() if k not in ("wis", "lewat_nama", "belum")]
audit += [aud("ganda2", rows["ganda"]), aud("wis", rows["wis"], WIS),
          {"kunci": rows["wis"].kunci, "status": "TERKIRIM_BELUM_TERVERIFIKASI", "akun_login": WIS},
          aud("lain", lain_sumber)]
items = [doc(k, r, "DRAFT" if k == "draft" else TERKIRIM, INPUT if k != "di_tujuan" else r.idsubsls)
         for k, r in rows.items() if k not in ("wis", "hilang", "belum")]
items += [doc("ganda2", rows["ganda"]), doc("lain", lain_sumber),
          {"id": "asing", "data1": "PETRONELA / ", "assignmentStatusAlias": TERKIRIM, "codeIdentity": f"{INPUT} - x"},
          {"id": "yatim", "data1": "", "assignmentStatusAlias": "DRAFT", "codeIdentity": INPUT}]
laporan, ringkasan = rencana_ubah_wilayah([("S.xlsx", r) for r in rows.values()], audit, {MEGA: items}, peta, ASG)
st = {l["dokumen_id"]: l["status_rencana"] for l in laporan}
check("status per dokumen", st, {
    "siap": "SIAP_PINDAH", "titik_beda": "CEK_WILAYAH", "pilih_sepakat": "CEK_WILAYAH", "pilih_salah": "SIAP_PINDAH",
    "luar": "CEK_WILAYAH", "ganda": "CEK_DOKUMEN", "ganda2": "CEK_DOKUMEN", "draft": "CEK_DOKUMEN",
    "wis": "BELUM_DISINKRON", "lewat_nama": "SIAP_PINDAH", "hilang": "CEK_DOKUMEN", "di_tujuan": "SUDAH_DI_TUJUAN",
    "tak_ada_di_peta": "CEK_WILAYAH", "asing": "TIDAK_DIKENALI", "yatim": "TIDAK_DIKENALI",
})
per = {l["dokumen_id"]: l for l in laporan}
check("urutan: TIDAK_DIKENALI dulu, SIAP_PINDAH terakhir",
      (laporan[0]["status_rencana"], laporan[-1]["status_rencana"]), ("TIDAK_DIKENALI", "SIAP_PINDAH"))
check("kolom siap", {k: per["siap"][k] for k in ("subsls_sekarang", "subsls_tujuan", "subsls_titik",
                                                  "jarak_titik_ke_tujuan_m", "nama_excel", "nama_di_fasih",
                                                  "perubahan_nama", "subsls_kolom_pilih", "catatan")},
      {"subsls_sekarang": INPUT, "subsls_tujuan": A, "subsls_titik": A, "jarak_titik_ke_tujuan_m": 0,
       "nama_excel": "APOTEK SIAP", "nama_di_fasih": "APOTEK SIAP (I MADE)",
       "perubahan_nama": "nama 12a ditambahkan dalam kurung", "subsls_kolom_pilih": "", "catatan": ""})
check("titik beda: subsls titik & jarak", (per["titik_beda"]["subsls_titik"], per["titik_beda"]["jarak_titik_ke_tujuan_m"] > 100000),
      (B, True))
check("pilih sepakat dgn titik tercatat", "SEPAKAT" in per["pilih_sepakat"]["catatan"], True)
check("pilih salah tapi titik benar -> info", "titik membenarkan idsubsls" in per["pilih_salah"]["catatan"], True)
check("luar peta: jarak ±111 m", (per["luar"]["subsls_titik"], per["luar"]["jarak_titik_ke_tujuan_m"]), ("", 111))
check("ganda menyebut kedua id", all(x in per["ganda"]["catatan"] for x in ("ganda", "ganda2")), True)
check("wis: status audit disebut", "TERKIRIM_BELUM_TERVERIFIKASI" in per["wis"]["catatan"], True)
check("wis: subsls dari audit", per["wis"]["subsls_sekarang"], INPUT)
check("lewat nama tercatat", per["lewat_nama"]["catatan"], "tidak tercatat di audit; dicocokkan lewat nama")
check("hilang dari list server", "tidak ada di list server" in per["hilang"]["catatan"], True)
check("yatim ditandai", "yatim" in per["yatim"]["catatan"], True)
check("ringkasan", ringkasan, {"dokumen_milik_sumber_lain": 1, "baris_tanpa_dokumen": 1})

laporan2, _ = rencana_ubah_wilayah([("S.xlsx", rows["pilih_salah"])], [aud("pilih_salah", rows["pilih_salah"])],
                                   {MEGA: [doc("pilih_salah", rows["pilih_salah"])]}, None, ASG)
check("tanpa peta: kolom Pilih beda -> CEK_WILAYAH", laporan2[0]["status_rencana"], "CEK_WILAYAH")

print("\nSEMUA LULUS" if ok_all else "\nADA YANG GAGAL")
sys.exit(0 if ok_all else 1)
