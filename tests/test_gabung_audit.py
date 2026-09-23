# -*- coding: utf-8 -*-
"""Uji penggabungan audit antar-PC & laporannya — offline, tanpa browser/VPN.
Jalankan: python tests/test_gabung_audit.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import input_gabungan.main_gabungan as mg  # noqa: E402
from gabung_audit.gabung_audit import (  # noqa: E402
    agregat, gabung, id_dokumen, kelompok_status, periksa_bentrok, ringkas_per_kunci,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


def b(kunci, status, waktu, **lain):
    """Satu baris audit."""
    baris = {k: "" for k in mg.AUDIT_FIELDS}
    baris.update({"kunci": kunci, "status": status, "timestamp": waktu})
    baris.update(lain)
    return baris


URL1 = "https://fasih-web.bps.go.id/survey/S/P/1111aaaa-0000/entry"
URL2 = "https://fasih-web.bps.go.id/survey/S/P/2222bbbb-0000/entry"

# --- kelompok status: ikut daftar status main_gabungan, bukan salinan ---
check("TERKIRIM_TERVERIFIKASI -> TERKIRIM", kelompok_status("TERKIRIM_TERVERIFIKASI"), "TERKIRIM")
check("DOKUMEN_TERKUNCI ikut TERKIRIM", kelompok_status(mg.STATUS_TERKUNCI), "TERKIRIM")
check("DRAFT_TANPA_KOORDINAT sendiri", kelompok_status("DRAFT_TANPA_KOORDINAT"), "DRAFT_TANPA_KOORDINAT")
check("DOKUMEN_DIBUAT -> DRAFT", kelompok_status("DOKUMEN_DIBUAT"), "DRAFT")
check("SKIP_* -> DILEWATI", kelompok_status("SKIP_26C_TIDAK_DIRENDER"), "DILEWATI")
check("ERROR_* -> GAGAL", kelompok_status("ERROR_FIELD_NOT_FOUND"), "GAGAL")
check("STOP_* -> GAGAL", kelompok_status("STOP_SUBSLS_TIDAK_BISA_DIPILIH"), "GAGAL")
check("tanpa URL (nama lama) -> GAGAL", kelompok_status("STOP_DOKUMEN_TANPA_URL"), "GAGAL")
check("tanpa URL (nama baru) -> GAGAL", kelompok_status(mg.STATUS_TANPA_URL), "GAGAL")
check("SUBMIT_GAGAL -> GAGAL", kelompok_status("SUBMIT_GAGAL"), "GAGAL")
check("status asing -> LAIN", kelompok_status("SESUATU_YANG_BARU"), "LAIN")
check("id dokumen dari URL entry", id_dokumen(URL1), "1111aaaa-0000")
check("URL bukan /entry -> kosong", id_dokumen("https://x/y/z"), "")

# --- baris kembar (audit pernah disalin antar-PC) ditulis sekali ---
pc1 = [b("K1", "DOKUMEN_DIBUAT", "2026-09-20 10:00:30", dokumen_url=URL1),
       b("K1", "TERKIRIM_TERVERIFIKASI", "2026-09-20 10:00:00", dokumen_url=URL1)]
gabungan, lap = gabung([("pc1.csv", pc1), ("pc2.csv", list(pc1))])
check("baris sama persis tidak dobel", (len(gabungan), lap["ganda_persis"]), (2, 2))
# Berkas yang isinya cuma SALINAN tidak dihitung sbg asal: kalau dihitung, setiap
# PC yang menerima audit gabungan akan tampil sbg "dikerjakan >1 PC" — peringatan
# palsu yang menenggelamkan bentrok sungguhan.
check("berkas yang cuma salinan tidak dihitung sbg asal", lap["asal_per_kunci"]["K1"], ["pc1.csv"])

# --- JEBAKAN: timestamp DOKUMEN_DIBUAT lebih BARU drpd baris status akhirnya ---
# (timestamp baris hasil = AWAL pemrosesan). Kalau baris diurutkan per waktu satu
# per satu, DOKUMEN_DIBUAT jadi baris terakhir -> baris yang sudah terkirim akan
# dikerjakan ulang. Urutan asli per kunci HARUS dipertahankan.
check("urutan dalam satu kunci tetap (bukan urut waktu)",
      [x["status"] for x in gabungan], ["DOKUMEN_DIBUAT", "TERKIRIM_TERVERIFIKASI"])
check("status akhir = baris terakhir", mg.status_terakhir_dari(gabungan)["K1"], "TERKIRIM_TERVERIFIKASI")

# --- PC yang paling baru mengerjakan satu kunci menang ---
lama = [b("K9", "DRAFT_TANPA_KOORDINAT", "2026-09-20 08:00:00", dokumen_url=URL1)]
baru = [b("K9", "TERKIRIM_TERVERIFIKASI", "2026-09-22 09:00:00", dokumen_url=URL1)]
for urutan, nama in (((("pcA.csv", lama), ("pcB.csv", baru)), "PC baru di belakang"),
                     ((("pcB.csv", baru), ("pcA.csv", lama)), "PC baru di depan")):
    g, _ = gabung(list(urutan))
    check(f"status akhir tidak bergantung urutan --sumber ({nama})",
          mg.status_terakhir_dari(g)["K9"], "TERKIRIM_TERVERIFIKASI")

# --- baris tanpa kunci (mis. ERROR_LOGIN) tidak saling menelan ---
tanpa = [b("", "ERROR_LOGIN", "2026-09-20 07:00:00"), b("", "ERROR_LOGIN", "2026-09-20 07:00:01")]
g, _ = gabung([("pc1.csv", tanpa)])
check("baris tanpa kunci tetap 2", len(g), 2)

# --- pemeriksaan bentrok ---
dua_url = [b("K2", "DOKUMEN_DIBUAT", "2026-09-20 10:00:00", dokumen_url=URL1, akun_login="a@x.com"),
           b("K2", "DOKUMEN_DIBUAT", "2026-09-21 10:00:00", dokumen_url=URL2, akun_login="b@x.com")]
g, lap2 = gabung([("pc1.csv", dua_url[:1]), ("pc2.csv", dua_url[1:])])
hasil = periksa_bentrok(g, lap2["asal_per_kunci"])
check("dokumen ganda terdeteksi", hasil["dokumen_ganda"], {"K2": [URL1, URL2]})
check("akun ganda terdeteksi", hasil["akun_ganda"], {"K2": ["a@x.com", "b@x.com"]})
check("kunci dikerjakan 2 PC terdeteksi", hasil["lintas_berkas"], {"K2": ["pc1.csv", "pc2.csv"]})

# DOKUMEN_DIHAPUS = dokumen lama sudah tidak ada -> dokumen berikutnya BUKAN duplikat
dihapus = [b("K3", "DOKUMEN_DIBUAT", "2026-09-20 10:00:00", dokumen_url=URL1),
           b("K3", "DOKUMEN_DIHAPUS", "2026-09-20 11:00:00", dokumen_url=URL1),
           b("K3", "DOKUMEN_DIBUAT", "2026-09-20 12:00:00", dokumen_url=URL2)]
g, lap3 = gabung([("pc1.csv", dihapus)])
check("dokumen setelah DOKUMEN_DIHAPUS bukan ganda", periksa_bentrok(g, lap3["asal_per_kunci"])["dokumen_ganda"], {})

# satu dokumen dipakai dua baris sheet
sama = [b("K4", "DOKUMEN_DIBUAT", "2026-09-20 10:00:00", dokumen_url=URL1),
        b("K5", "DOKUMEN_DIBUAT", "2026-09-20 10:05:00", dokumen_url=URL1)]
g, lap4 = gabung([("pc1.csv", sama)])
check("satu URL utk 2 kunci terdeteksi", periksa_bentrok(g, lap4["asal_per_kunci"])["url_banyak_kunci"],
      {URL1: ["K4", "K5"]})

# --- laporan per dokumen ---
riwayat = [b("K6", "DOKUMEN_DIBUAT", "2026-09-20 10:00:30", dokumen_url=URL1, akun_login="a@x.com",
             baris="7", nama_usaha="WARUNG CONTOH", idsubsls="5108010010000205",
             idsubsls_input="5108060006000223"),
           b("K6", "TERKIRIM_TERVERIFIKASI", "2026-09-20 10:00:00", akun_login="a@x.com", baris="7")]
g, lap5 = gabung([("pc1.csv", riwayat)])
lapor = ringkas_per_kunci(g, lap5["asal_per_kunci"], {"1111aaaa-0000": "SUBMITTED BY Pencacah"},
                          {"5108010010000205": {"kecamatan": "GEROKGAK", "desa": "PATAS"}})
check("satu baris laporan per dokumen", len(lapor), 1)
r = lapor[0]
check("laporan: status, kelompok, wilayah, server, url",
      (r["status"], r["kelompok"], r["kecamatan"], r["desa"], r["status_server"], r["id_dokumen"]),
      ("TERKIRIM_TERVERIFIKASI", "TERKIRIM", "GEROKGAK", "PATAS", "SUBMITTED BY Pencacah", "1111aaaa-0000"))
check("laporan: nilai kolom diambil dari baris terakhir yang ISI",
      (r["nama_usaha"], r["idsubsls_input"], r["waktu_terakhir"]),
      ("WARUNG CONTOH", "5108060006000223", "2026-09-20 10:00:30"))

# --- rekap ---
contoh = [{"akun_login": "a@x.com", "kelompok": "TERKIRIM", "idsubsls": "X"},
          {"akun_login": "a@x.com", "kelompok": "TERKIRIM", "idsubsls": "X"},
          {"akun_login": "b@x.com", "kelompok": "GAGAL", "idsubsls": "Y"}]
rekap = agregat(contoh, "akun_login", "akun")
check("rekap per akun (urut jumlah terbanyak)",
      [(x["nilai"], x["total"], x["TERKIRIM"], x["GAGAL"]) for x in rekap],
      [("a@x.com", 2, 2, 0), ("b@x.com", 1, 0, 1)])
check("nilai kosong tidak hilang dari rekap",
      [x["nilai"] for x in agregat([{"akun_login": "", "kelompok": "GAGAL"}], "akun_login", "akun")],
      ["(kosong)"])

# --- bersihkan_error: tindakan per jenis masalah ---
from gabung_audit.bersihkan_error import klasifikasi, perintah, ringkas_baris  # noqa: E402
from gabung_audit.gabung_audit import kelompok_status  # noqa: E402


def rec(status, **lain):
    d = {"status": status, "kelompok": kelompok_status(status), "status_server": "", "dokumen_url": ""}
    d.update(lain)
    return d


check("galat sesi tanpa dokumen -> ULANGI", klasifikasi(rec("ERROR_LOGIN"), None)[0], "ULANGI")
check("gagal kirim (dokumen ada) -> ULANGI", klasifikasi(rec("SUBMIT_GAGAL", dokumen_url=URL1), None)[0], "ULANGI")
check("DRAFT belum tuntas -> ULANGI", klasifikasi(rec("DOKUMEN_DIBUAT", dokumen_url=URL1), None)[0], "ULANGI")
check("isian ditolak form -> PERBAIKI_DATA", klasifikasi(rec("SKIP_26C_TIDAK_DIRENDER"), None)[0], "PERBAIKI_DATA")
check("terkirim & server terkirim -> tidak perlu tindakan",
      klasifikasi(rec("TERKIRIM_TERVERIFIKASI", status_server="SUBMITTED BY Pencacah"), None)[0], "")
# "toast berhasil dikirim" pernah muncul padahal server tetap DRAFT -> audit disinkronkan dulu
check("audit terkirim tapi server DRAFT -> SINKRON_DULU",
      klasifikasi(rec("TERKIRIM_BELUM_TERVERIFIKASI", status_server="DRAFT"), None)[0], "SINKRON_DULU")
check("draft tanpa koordinat, sheet masih kosong -> TUNGGU_KOORDINAT",
      klasifikasi(rec("DRAFT_TANPA_KOORDINAT"), False)[0], "TUNGGU_KOORDINAT")
check("draft tanpa koordinat, sheet sudah diisi -> LENGKAPI_KOORDINAT",
      klasifikasi(rec("DRAFT_TANPA_KOORDINAT"), True)[0], "LENGKAPI_KOORDINAT")
check("baris tidak ada di sheet -> koordinat tidak dianggap ada",
      klasifikasi(rec("DRAFT_TANPA_KOORDINAT"), None)[0], "TUNGGU_KOORDINAT")
check("dokumen dihapus admin -> ULANGI", klasifikasi(rec("DOKUMEN_DIHAPUS"), None)[0], "ULANGI")
check("terkunci tapi server DRAFT -> MANUAL (bukan SINKRON_DULU yang berputar)",
      klasifikasi(rec(mg.STATUS_TERKUNCI, status_server="DRAFT"), None)[0], "MANUAL")
# Dokumen mungkin ada di server tanpa URL tercatat -> JANGAN "ULANGI" (dokumen kedua).
check("tanpa URL -> SINKRON_DULU, bukan ULANGI",
      klasifikasi(rec(mg.STATUS_TANPA_URL), None)[0], "SINKRON_DULU")
check("tanpa URL nama lama -> SINKRON_DULU juga",
      klasifikasi(rec("STOP_DOKUMEN_TANPA_URL"), None)[0], "SINKRON_DULU")
check("tanpa URL tapi URL-nya sudah tercatat -> ULANGI lewat URL itu",
      klasifikasi(rec(mg.STATUS_TANPA_URL, dokumen_url=URL1), None)[0], "ULANGI")
check("dokumen terkunci -> tidak perlu tindakan", klasifikasi(rec(mg.STATUS_TERKUNCI), None)[0], "")

# Jebakan GANDA: dokumen sudah ada di server tapi tidak tercatat di audit.
# Kalau baris seperti ini dijalankan ulang, skrip membuat dokumen KEDUA
# (kejadian nyata Agenda1-1 2026-09-15) -> harus disinkronkan dulu.
check("dokumen ada di server tapi tak tercatat -> SINKRON_DULU, bukan ULANGI",
      klasifikasi(rec("ERROR_LOGIN"), None, ada_di_server=True)[0], "SINKRON_DULU")
check("dokumen tercatat (punya URL) tetap ULANGI walau namanya ada di server",
      klasifikasi(rec("SUBMIT_GAGAL", dokumen_url=URL1), None, ada_di_server=True)[0], "ULANGI")
check("server menandai galat & masih DRAFT -> ULANGI",
      klasifikasi(rec("DOKUMEN_DIBUAT", dokumen_url=URL1, status_server="DRAFT", galat_server=2), None)[0],
      "ULANGI")
check("sudah terkirim tapi server menandai galat -> MANUAL (PPL tidak bisa edit)",
      klasifikasi(rec("TERKIRIM_TERVERIFIKASI", status_server="SUBMITTED BY Pencacah", galat_server=1), None)[0],
      "MANUAL")

check("nomor baris diringkas jadi rentang", ringkas_baris([9, 2, 3, 4, 11, 10]), "2-4,9-11")
check("satu nomor tetap tunggal", ringkas_baris([7]), "7")
check("tahap 2 memakai entry point-nya sendiri",
      perintah("tahap2", "bahan/input_tahap2.xlsx", "a@x.com", "51080", [3, 4]),
      "python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal a@x.com "
      "--subsls-tunggal 51080 --baris 3-4 --lewati-selesai --submit")
check("format standar & --tanpa-submit",
      perintah("standar", "Agenda.xlsx", "a@x.com", "51080", [3], submit=False),
      "python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --akun-tunggal a@x.com "
      "--subsls-tunggal 51080 --baris 3 --lewati-selesai")

check("DRAFT_GALAT_DI_SERVER masuk kelompok DRAFT", kelompok_status("DRAFT_GALAT_DI_SERVER"), "DRAFT")
check("draft bergalat -> ULANGI lewat URL",
      klasifikasi(rec("DRAFT_GALAT_DI_SERVER", dokumen_url=URL1), False)[0], "ULANGI")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
