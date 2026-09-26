# -*- coding: utf-8 -*-
"""Uji penggabungan audit antar-PC & laporannya — offline, tanpa browser/VPN.
Jalankan: python tests/test_gabung_audit.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import input_usaha.mesin as mg  # noqa: E402
from antar_pc.gabung_audit import (  # noqa: E402
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
from input_usaha.bersihkan_error import klasifikasi, perintah, ringkas_baris  # noqa: E402
from antar_pc.gabung_audit import kelompok_status  # noqa: E402


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
      "python input_usaha/jalankan.py --sumber bahan/input_tahap2.xlsx --akun-tunggal a@x.com "
      "--subsls-tunggal 51080 --baris 3-4 --lewati-selesai --submit")
check("format agenda (nama lama 'standar') & --tanpa-submit",
      perintah("standar", "Agenda.xlsx", "a@x.com", "51080", [3], submit=False),
      "python input_usaha/jalankan.py --sumber Agenda.xlsx --format agenda --akun-tunggal a@x.com "
      "--subsls-tunggal 51080 --baris 3 --lewati-selesai")

check("DRAFT_GALAT_DI_SERVER masuk kelompok DRAFT", kelompok_status("DRAFT_GALAT_DI_SERVER"), "DRAFT")
check("draft bergalat -> ULANGI lewat URL",
      klasifikasi(rec("DRAFT_GALAT_DI_SERVER", dokumen_url=URL1), False)[0], "ULANGI")

# --- rangkum_audit: progres per BARIS sheet & alasan run tidak mengerjakan apa-apa ---
from input_usaha.rangkum_audit import kelompok_baris, rangkum  # noqa: E402
from inti.gabungan_loader import GabunganRow, Pemeriksaan  # noqa: E402

AKUN_R, SUBSLS_R = "a@mail.com", "5108060006000224"
TUNTAS_R = set(mg.STATUS_TERKIRIM)


def row_r(baris, nama):
    return GabunganRow(baris, {"akun_ppl": "p@gmail.com", "idsubsls": "5108060006000224", "nama": nama,
                               "pengusaha": "MADE", "kbli": "47111", "latitude": "-8.1",
                               "longitude": "115.1"})


check("terkirim -> kelompok TERKIRIM",
      kelompok_baris("TERKIRIM_TERVERIFIKASI", "SIAP", TUNTAS_R, True), "TERKIRIM")
check("draft tanpa koordinat punya kelompok sendiri",
      kelompok_baris(mg.STATUS_DRAFT_TANPA_KOORDINAT, "SIAP", TUNTAS_R, False), "DRAFT_TANPA_KOORDINAT")
check("bertanda galat server -> kelompoknya sendiri",
      kelompok_baris(mg.STATUS_DRAFT_GALAT, "SIAP", TUNTAS_R, True), "DRAFT_GALAT_DI_SERVER")
check("belum ada catatan & data bersih -> BELUM DISENTUH",
      kelompok_baris("", "SIAP", TUNTAS_R, True), "BELUM DISENTUH")
check("belum ada catatan tapi data ditolak -> DITOLAK PEMERIKSAAN DATA",
      kelompok_baris("", "SKIP_DATA_WAJIB_KOSONG", TUNTAS_R, True), "DITOLAK PEMERIKSAAN DATA")
check("status audit menang atas hasil pemeriksaan",
      kelompok_baris("TERKIRIM_TERVERIFIKASI", "SKIP_DATA_WAJIB_KOSONG", TUNTAS_R, True), "TERKIRIM")

r_siap, r_kirim, r_tolak, r_lain = (row_r(2, "TOKO A"), row_r(3, "TOKO B"),
                                    row_r(4, "TOKO C"), row_r(5, "TOKO D"))
rows_r = [r_siap, r_kirim, r_tolak, r_lain]
hasil_r = {2: Pemeriksaan(), 3: Pemeriksaan(), 5: Pemeriksaan(),
           4: Pemeriksaan(masalah=[("WAJIB_KOSONG", "kolom kosong: pendapatan_lain")])}
audit_r = [
    {"kunci": r_kirim.kunci, "status": "TERKIRIM_TERVERIFIKASI", "akun_login": AKUN_R,
     "idsubsls_input": SUBSLS_R, "dokumen_url": "https://x/s/p/dB/entry"},
    {"kunci": r_lain.kunci, "status": mg.STATUS_DIBUAT, "akun_login": "lain@mail.com",
     "idsubsls_input": "5108060006000116", "dokumen_url": "https://x/s/p/dD/entry"},
]
keluar_r, kel_r, alasan_r = rangkum(rows_r, hasil_r, audit_r, (AKUN_R, SUBSLS_R), TUNTAS_R)
per_baris = {r["baris"]: r for r in keluar_r}
check("baris bersih & belum tersentuh -> dikerjakan", per_baris[2]["dikerjakan"], "ya")
check("baris terkirim -> tidak dikerjakan", per_baris[3]["dikerjakan"], "tidak")
check("alasan baris terkirim", "sudah selesai" in per_baris[3]["alasan"], True)
check("baris yang datanya ditolak -> alasannya kode SKIP_DATA_*",
      per_baris[4]["alasan"].startswith("SKIP_DATA_WAJIB_KOSONG"), True)
check("detail pemeriksaan ikut tercatat", "pendapatan_lain" in per_baris[4]["detail"], True)
check("dokumen milik akun lain -> tidak dikerjakan",
      (per_baris[5]["dikerjakan"], "proses lain" in per_baris[5]["alasan"]), ("tidak", True))
check("rekap kelompok", dict(kel_r), {"BELUM DISENTUH": 1, "TERKIRIM": 1,
                                      "DITOLAK PEMERIKSAAN DATA": 1, "SUDAH DISENTUH (belum tuntas)": 1})
check("baris yang dikerjakan tidak punya alasan", alasan_r[""], 1)

# --- rangkum_audit: rekap BELUM TUNTAS & ERROR ---
from input_usaha.rangkum_audit import daftar_baris, rekap_baris  # noqa: E402

check("terkirim & server setuju -> tuntas", rekap_baris("TERKIRIM_TERVERIFIKASI", True, "SUBMITTED BY Pencacah"), "")
check("audit terkirim tapi server DRAFT", rekap_baris("TERKIRIM_TERVERIFIKASI", True, "DRAFT"), "SERVER_DRAFT")
check("toast terkirim, server tidak diketahui -> belum terbukti",
      rekap_baris("TERKIRIM_BELUM_TERVERIFIKASI", True, ""), "TERKIRIM_BELUM_TERBUKTI")
check("toast terkirim, server APPROVED -> tuntas",
      rekap_baris("TERKIRIM_BELUM_TERVERIFIKASI", True, "APPROVED BY Pengawas"), "")
check("terkunci + server DRAFT -> perlu admin", rekap_baris(mg.STATUS_TERKUNCI, True, "DRAFT"), "TERKUNCI")
check("terkunci tanpa bukti server -> dianggap tuntas (dikirim manual)", rekap_baris(mg.STATUS_TERKUNCI, True), "")
check("draft tanpa koordinat, sheet sudah berkoordinat",
      rekap_baris(mg.STATUS_DRAFT_TANPA_KOORDINAT, True), "KOORDINAT_SUDAH_ADA")
check("draft tanpa koordinat, masih menunggu", rekap_baris(mg.STATUS_DRAFT_TANPA_KOORDINAT, False), "TUNGGU_KOORDINAT")
check("draft tanpa koordinat TAPI server menandai galat -> draft ber-galat",
      rekap_baris(mg.STATUS_DRAFT_TANPA_KOORDINAT, False, "DRAFT", 3), "DRAFT_GALAT")
check("DRAFT_GALAT_DI_SERVER", rekap_baris(mg.STATUS_DRAFT_GALAT, True), "DRAFT_GALAT")
check("dokumen dibuat, belum selesai diisi", rekap_baris(mg.STATUS_DIBUAT, True), "BELUM_SELESAI_DIISI")
check("dokumen tanpa URL", rekap_baris(mg.STATUS_TANPA_URL, True), "TANPA_URL")
check("gagal di run terakhir", rekap_baris("ERROR_FIELD_NOT_FOUND", True), "GAGAL")
check("SUBMIT_GAGAL ikut gagal", rekap_baris("SUBMIT_GAGAL", True), "GAGAL")
check("belum disentuh -> bukan bagian rekap ini", rekap_baris("", True), "")

audit_g = [{"kunci": r_siap.kunci, "status": "ERROR_FIELD_NOT_FOUND", "akun_login": AKUN_R,
            "idsubsls_input": SUBSLS_R, "dokumen_url": "https://x/s/p/dA/entry", "error_message": "radio 8d macet"},
           {"kunci": r_siap.kunci, "status": mg.STATUS_DIBUAT, "akun_login": AKUN_R,
            "idsubsls_input": SUBSLS_R, "dokumen_url": "https://x/s/p/dA/entry",
            "error_message": "dibuat di luar audit ini"},
           {"kunci": r_kirim.kunci, "status": "TERKIRIM_TERVERIFIKASI", "akun_login": AKUN_R,
            "idsubsls_input": SUBSLS_R, "dokumen_url": "https://x/s/p/dB/entry"}]
keluar_g, _, _ = rangkum(rows_r, hasil_r, audit_g, (AKUN_R, SUBSLS_R), TUNTAS_R,
                         status_server={"dA": "DRAFT", "dB": "DRAFT"}, galat_server={"dA": 2})
per_g = {r["baris"]: r for r in keluar_g}
check("server menandai 2 galat -> DRAFT_GALAT + jumlahnya",
      (per_g[2]["rekap"], per_g[2]["galat_server"]), ("DRAFT_GALAT", 2))
check("pesan terakhir = penyebab gagal, bukan catatan DOKUMEN_DIBUAT",
      per_g[2]["pesan_terakhir"], "radio 8d macet")
check("terkirim di audit, DRAFT di server -> SERVER_DRAFT", per_g[3]["rekap"], "SERVER_DRAFT")
check("daftar baris pendek utuh", daftar_baris([2, 3, 4, 9]), "2-4,9")
check("daftar baris panjang dipotong di koma + sisanya",
      daftar_baris(list(range(2, 100)) + [150, 152] + list(range(200, 400, 2)), 60).split(" … ")[1],
      "(+89 baris lagi — kolom 'rekap' di CSV)")

# --- daftar ganda & usulan (kasus kembar dgn putuskanGrup di tests/test_hapus_ganda_console.js) ---
from antar_pc.gabung_audit import daftar_ganda, peringkat_status, usulan_grup  # noqa: E402

check("peringkat status", [peringkat_status(x) for x in ("APPROVED BY Pengawas", "SUBMITTED BY Pencacah",
                                                          "REJECTED BY Pengawas", "DRAFT", "OPEN", "")],
      [4, 3, 2, 1, 1, 0])


def dk(status, **o):
    return {"status": status, "dicatat": False, "luar": False, "bersama": False, "mode": "", "galat": 0,
            "bersih": 80, **o}


def usul(dok, **o):
    return [u for u, _ in usulan_grup(dok, **o)]


# Ketetapan user 2026-09-24 (kembar dgn putuskanGrup di tests/test_hapus_ganda_console.js)
check("SUBMITTED + DRAFT -> DRAFT dihapus", usul([dk("DRAFT"), dk("SUBMITTED BY Pencacah")]), ["HAPUS", "PERTAHANKAN"])
check("SUBMITTED + SUBMITTED -> salah satu dihapus",
      usul([dk("SUBMITTED BY Pencacah", dicatat=True), dk("SUBMITTED BY Pencacah")]), ["PERTAHANKAN", "HAPUS"])
check("SUBMITTED dimatikan dgn izinkan_hapus_terkirim=False",
      usul([dk("SUBMITTED BY Pencacah", dicatat=True), dk("SUBMITTED BY Pencacah")], izinkan_hapus_terkirim=False),
      ["PERTAHANKAN", "PERIKSA"])
check("DRAFT + DRAFT: yang ber-galat dihapus walau ditunjuk audit",
      usul([dk("DRAFT", galat=3, dicatat=True), dk("DRAFT", galat=0)]), ["HAPUS", "PERTAHANKAN"])
check("DRAFT + DRAFT keduanya bersih -> yang ditunjuk audit dipertahankan",
      usul([dk("DRAFT"), dk("DRAFT", dicatat=True)]), ["HAPUS", "PERTAHANKAN"])
check("DRAFT + DRAFT tanpa penunjuk -> jawaban lebih lengkap dipertahankan",
      usul([dk("DRAFT", bersih=20), dk("DRAFT", bersih=91)]), ["HAPUS", "PERTAHANKAN"])
check("DRAFT + DRAFT keduanya ber-galat -> galat lebih banyak dihapus",
      usul([dk("DRAFT", galat=1), dk("DRAFT", galat=5, dicatat=True)]), ["PERTAHANKAN", "HAPUS"])
check("DRAFT + DRAFT galat tidak diketahui -> PERIKSA",
      usul([dk("DRAFT", galat=None, dicatat=True), dk("DRAFT", galat=2)]), ["PERTAHANKAN", "PERIKSA"])
check("APPROVED tidak pernah dihapus", usul([dk("APPROVED BY Pengawas"), dk("APPROVED BY Pengawas")]),
      ["PERTAHANKAN", "PERIKSA"])
check("APPROVED + SUBMITTED -> SUBMITTED dihapus",
      usul([dk("SUBMITTED BY Pencacah", dicatat=True), dk("APPROVED BY Pengawas")]), ["HAPUS", "PERTAHANKAN"])
check("status tertinggi menang atas penunjuk audit",
      usul([dk("DRAFT", dicatat=True), dk("SUBMITTED BY Pencacah", galat=2)]), ["HAPUS", "PERTAHANKAN"])
check("di luar audit -> PERIKSA", usul([dk("SUBMITTED BY Pencacah"), dk("DRAFT", luar=True)]), ["PERTAHANKAN", "PERIKSA"])
check("URL diklaim baris lain -> PERIKSA", usul([dk("SUBMITTED BY Pencacah"), dk("DRAFT", bersama=True)]),
      ["PERTAHANKAN", "PERIKSA"])
check("tiga dokumen", usul([dk("DRAFT"), dk("SUBMITTED BY Pencacah"), dk("DRAFT")]), ["HAPUS", "PERTAHANKAN", "HAPUS"])
check("status belum diketahui -> PERIKSA semua", usul([dk(""), dk("DRAFT")]), ["PERIKSA", "PERIKSA"])
check("hanya_papi: CAPI tidak disentuh & tidak jadi pembanding",
      usul([dk("DRAFT", mode="PAPI"), dk("SUBMITTED BY Pencacah", mode="CAPI")], hanya_papi=True),
      ["PERTAHANKAN", "BUKAN_PAPI"])
check("hanya_papi: mode tak diketahui tetap diputuskan (Console membaca ulang)",
      usul([dk("DRAFT"), dk("SUBMITTED BY Pencacah", mode="PAPI")], hanya_papi=True), ["HAPUS", "PERTAHANKAN"])

U = "https://fasih-web.bps.go.id/survey/s/p/{}/entry"
I1, I2, I3 = ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222",
              "33333333-3333-4333-8333-333333333333")
audit_d = [
    {"kunci": "k1", "status": mg.STATUS_DIBUAT, "akun_login": "a@mail.com", "dokumen_url": U.format(I1), "baris": "5",
     "nama_usaha": "WARUNG (MADE)"},
    {"kunci": "k1", "status": "DRAFT_TANPA_KOORDINAT", "akun_login": "a@mail.com", "dokumen_url": U.format(I1)},
    {"kunci": "k1", "status": mg.STATUS_DIBUAT, "akun_login": "b@mail.com", "dokumen_url": U.format(I2)},
    {"kunci": "k1", "status": "TERKIRIM_TERVERIFIKASI", "akun_login": "b@mail.com", "dokumen_url": U.format(I2)},
    {"kunci": "k2", "status": mg.STATUS_DIBUAT, "akun_login": "a@mail.com", "dokumen_url": U.format(I3)},
]
g = daftar_ganda(audit_d, {I1: "DRAFT", I2: "SUBMITTED BY Pencacah"},
                 info_server={I1: {"mode": "PAPI", "bersih": 80}, I2: {"mode": "PAPI", "bersih": 80}}, hanya_papi=True)
check("satu baris dgn 2 dokumen -> satu grup BARIS_SAMA", sorted((r["id_dokumen"], r["usulan"]) for r in g),
      sorted([(I1, "HAPUS"), (I2, "PERTAHANKAN")]))
check("dokumen yang ditunjuk audit ditandai", [r["dicatat_audit"] for r in g if r["id_dokumen"] == I2], ["ya"])
check("baris tunggal tidak masuk daftar", any(r["kunci"] == "k2" for r in g), False)
check("yang sudah dihapus admin tidak dihitung lagi", daftar_ganda(audit_d, sudah_dihapus={I1}), [])
check("DOKUMEN_DIHAPUS mengosongkan catatan dokumen lama",
      daftar_ganda(audit_d[:2] + [{"kunci": "k1", "status": mg.STATUS_DIHAPUS}] + audit_d[2:4]), [])
luar = daftar_ganda(audit_d, {I2: "SUBMITTED BY Pencacah", I3: "DRAFT", "44444444-4444-4444-8444-444444444444": "DRAFT"},
                    nama_server={"WARUNG (MADE)": [I2, "44444444-4444-4444-8444-444444444444"]})
check("dokumen server bernama sama di luar audit masuk grup barisnya",
      [r["di_luar_audit"] for r in luar if r["id_dokumen"].startswith("4444")], ["ya"])

from fasih_sm.hapus_ganda.hapus_ganda import target_dari_ganda, tulis_console  # noqa: E402
t = target_dari_ganda(g)
check("TARGET Console", [(x["g"], [d["id"] for d in x["d"]], [d["c"] for d in x["d"]]) for x in t],
      [("k1", [I1, I2], [False, True])])
g_capi = daftar_ganda(audit_d, {I1: "DRAFT", I2: "SUBMITTED BY Pencacah"},
                     info_server={I1: {"mode": "PAPI"}, I2: {"mode": "CAPI"}})
check("hanya PAPI: grup yang tinggal 1 dokumen PAPI tidak ikut", target_dari_ganda(g_capi), [])
check("--semua-mode: ikut", len(target_dari_ganda(g_capi, hanya_papi=False)), 1)
import tempfile  # noqa: E402
_siap = Path(tempfile.mkdtemp()) / "hg.siap.js"
tulis_console(t, _siap)
_teks = _siap.read_text(encoding="utf-8")
check("siap.js: penanda terisi", ("/*__TARGET__*/[]" in _teks, "__SURVEI__*/\"\"" in _teks, I1 in _teks),
      (False, False, True))

# --- hapus_ganda --catat: arahkan audit ke dokumen yang dipertahankan ---
from fasih_sm.hapus_ganda.hapus_ganda import rencana_catat  # noqa: E402
hapus_r = [{"id": I2, "status": "DIHAPUS_TERVERIFIKASI", "grup": "k1", "baris": "5", "alias": "SUBMITTED BY Pencacah",
            "dipertahankan": I1, "alias_dipertahankan": "SUBMITTED BY Pencacah", "akun_dipertahankan": "a@mail.com",
            "subsls_dipertahankan": "5108060006000224"}]
cat = rencana_catat(audit_d, hapus_r, "p")
check("catat: audit menunjuk dokumen terhapus -> diarahkan ke yang dipertahankan",
      [(t["status"], id_dokumen(t["dokumen_url"]), t["akun_login"]) for t in cat],
      [(mg.STATUS_DIBUAT, I1, "a@mail.com"), ("TERKIRIM_TERVERIFIKASI", I1, "a@mail.com")])
check("catat: sesudahnya audit menunjuk & berstatus benar",
      (id_dokumen(mg.dokumen_dari(audit_d + cat)["k1"][2]), mg.status_terakhir_dari(audit_d + cat)["k1"]),
      (I1, "TERKIRIM_TERVERIFIKASI"))
check("catat: idempoten", rencana_catat(audit_d + cat, hapus_r, "p"), [])
check("catat: yang terhapus bukan yang ditunjuk audit -> tidak menulis apa pun",
      rencana_catat(audit_d, [{**hapus_r[0], "id": I1, "dipertahankan": I2}], "p"), [])
draft_r = [{**hapus_r[0], "alias_dipertahankan": "DRAFT"}]
check("catat: yang dipertahankan DRAFT -> cukup DOKUMEN_DIBUAT (dibuka & diisi run berikutnya)",
      [t["status"] for t in rencana_catat(audit_d, draft_r, "p")], [mg.STATUS_DIBUAT])

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
