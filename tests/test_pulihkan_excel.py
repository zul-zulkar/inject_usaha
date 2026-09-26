# -*- coding: utf-8 -*-
"""Uji pemulihan audit yang rusak karena disimpan Excel — offline, tanpa browser/VPN.
Jalankan: python tests/test_pulihkan_excel.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import input_usaha.mesin as mg  # noqa: E402
from antar_pc.gabung_audit import baca_audit  # noqa: E402
from antar_pc.pulihkan_excel import (  # noqa: E402
    cocok_excel, pulihkan, subsls_dari_catatan_wilayah, urutan_tanggal, waktu_iso,
)

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


def b(**isi):
    baris = {k: "" for k in mg.AUDIT_FIELDS}
    baris.update(isi)
    return baris


# --- cocok_excel: nilai asli yang ditulis ulang Excel harus menghasilkan tampilannya ---
check("kunci hash angka+e", cocok_excel("1404364e03", "1.40E+09"), True)
check("kunci beda digit", cocok_excel("1414364e03", "1.40E+09"), False)
check("idsubsls 16 digit", cocok_excel("5108060006000224", "5.10806E+15"), True)
check("idsubsls kecamatan lain", cocok_excel("5108070006000224", "5.10806E+15"), False)
check("kbli nol di depan", cocok_excel("01464", "1464"), True)
check("kunci di luar jangkauan Excel dibiarkan utuh", cocok_excel("039573e516", "039573e516"), True)
check("eksponen raksasa tidak meledak", cocok_excel("2e87654321", "1.40E+09"), False)
check("bukan angka", cocok_excel("abcdef0123", "1.40E+09"), False)

# --- tanggal Excel ---
check("M/D", waktu_iso("9/23/2026 4:25"), "2026-09-23 04:25:00")
check("D/M", waktu_iso("23/09/2026 18:05", "DM"), "2026-09-23 18:05:00")
check("ISO dibiarkan", waktu_iso("2026-09-23 18:05:12"), "2026-09-23 18:05:12")
check("urutan dari tanggal tak ambigu (Inggris)", urutan_tanggal(["9/3/2026 1:00", "9/23/2026 1:00"]), "MD")
check("urutan dari tanggal tak ambigu (Indonesia)", urutan_tanggal(["3/9/2026 1:00", "23/9/2026 1:00"]), "DM")

# --- kolom wilayah_dokumen -> subsls run ---
W6 = "COCOK: prov='[51] BALI'; kab='[08] BULELENG'; kec='[060] KEC'; desa='[006] DESA'; kode_sls='000116'"
W4 = "COCOK: prov='[51] BALI'; kab='[08] BULELENG'; kec='[060] KEC'; desa='[006] DESA'; kode_sls='0002'"
B4 = ("BEDA: wilayah dokumen BUKAN 5108060006000116: kode_sls='0002' | prov='[51] BALI'; kab='[08] BULELENG'; "
      "kec='[060] KEC'; desa='[006] DESA'; kode_sls='0002'")
B6 = ("BEDA: wilayah dokumen BUKAN 5108060006000205: kode_sls='000116' | prov='[51] BALI'; kab='[08] BULELENG'; "
      "kec='[060] KEC'; desa='[006] DESA'; kode_sls='000116'")
check("COCOK kode SLS 6 digit", subsls_dari_catatan_wilayah(W6), "5108060006000116")
check("COCOK kode SLS 4 digit = tidak pasti", subsls_dari_catatan_wilayah(W4), "")
check("COCOK 4 digit sbg penyaring", subsls_dari_catatan_wilayah(W4, minimal=14), "51080600060002")
check("BEDA 4 digit -> subsls run (audit tetap subsls run)", subsls_dari_catatan_wilayah(B4), "5108060006000116")
check("BEDA 6 digit -> wilayah dokumen", subsls_dari_catatan_wilayah(B6), "5108060006000116")
check("kosong", subsls_dari_catatan_wilayah(""), "")

# --- deteksi ---
utuh = b(timestamp="2026-09-23 18:05:12", kunci="039573e516", idsubsls="5108060006000224")
check("audit utuh (kunci 039573e516 bukan kerusakan)", dict(mg.kerusakan_excel([utuh])), {})
check("audit rusak", dict(mg.kerusakan_excel([b(timestamp="9/23/2026 18:05", kunci="1.40E+09",
                                                 idsubsls="5.10806E+15", idsubsls_input="5.10806E+15")])),
      {"kunci": 1, "idsubsls": 1, "idsubsls_input": 1, "timestamp": 1})
try:
    mg.pastikan_audit_utuh([b(kunci="1.40E+09")])
    check("pastikan_audit_utuh menghentikan program", False, True)
except SystemExit as e:
    check("pastikan_audit_utuh menghentikan program", "pulihkan_excel.py" in str(e), True)
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "pc1.csv"
    f.write_text(",".join(mg.AUDIT_FIELDS) + "\n" + ",".join(
        b(timestamp="9/23/2026 18:05", kunci="1.40E+09", status="DOKUMEN_DIBUAT")[k] for k in mg.AUDIT_FIELDS)
        + "\n", encoding="utf-8")
    try:
        baca_audit(f)
        check("gabung_audit menolak sumber rusak", False, True)
    except ValueError as e:
        check("gabung_audit menolak sumber rusak", "RUSAK" in str(e), True)

# --- pulihkan ---
URL1 = "https://fasih-web.bps.go.id/survey/S/P/1111aaaa-0000/entry"
URL2 = "https://fasih-web.bps.go.id/survey/S/P/2222bbbb-0000/entry"
URL3 = "https://fasih-web.bps.go.id/survey/S/P/3333cccc-0000/entry"
A1, A2 = "ppl.contoh@gmail.com", "ppl.kedua@gmail.com"
rujukan = [
    b(timestamp="2026-09-23 18:05:12", baris="421", kunci="1404364e03", nama_usaha="WARUNG CONTOH (I KETUT CONTOH)",
      kbli="01464", idsubsls="5108050010000205", idsubsls_input="5108060006000224", akun_login=A1,
      status="DOKUMEN_DIBUAT", dokumen_url=URL1),
]
rusak = [
    # 0: ada persis di rujukan -> dipakai utuh (detik ikut kembali)
    b(timestamp="9/23/2026 18:05", baris="421", kunci="1.40E+09", nama_usaha="WARUNG CONTOH (I KETUT CONTOH)",
      kbli="1464", idsubsls="5.10805E+15", idsubsls_input="5.10806E+15", akun_login=A1,
      status="DOKUMEN_DIBUAT", dokumen_url=URL1),
    # 1: baris baru kunci sama -> kunci dari (baris, nama), subsls input dari URL yang sama
    b(timestamp="9/24/2026 11:37", baris="421", kunci="1.40E+09", nama_usaha="WARUNG CONTOH (I KETUT CONTOH)",
      kbli="1464", idsubsls="5.10805E+15", idsubsls_input="5.10806E+15", akun_login=A1,
      status="TERKIRIM_TERVERIFIKASI", dokumen_url=URL1),
    # 2: baris yang tidak ada di rujukan -> idsubsls dari sheet, subsls input dari kolom wilayah
    b(timestamp="9/24/2026 17:02", baris="700", kunci="aaaaabbbbb", nama_usaha="TOKO CONTOH (NI LUH CONTOH)",
      kbli="47111", idsubsls="5.10806E+15", idsubsls_input="5.10806E+15", akun_login=A2,
      status="DOKUMEN_DIBUAT", dokumen_url=URL2, wilayah_dokumen=B4),
    # 3: dokumen yang sama tanpa kolom wilayah -> dari baris 2 (URL sama, berkas ini sendiri)
    b(timestamp="9/24/2026 17:03", baris="700", kunci="aaaaabbbbb", nama_usaha="TOKO CONTOH (NI LUH CONTOH)",
      kbli="47111", idsubsls="5.10806E+15", idsubsls_input="5.10806E+15", akun_login=A2,
      status="DRAFT_TANPA_KOORDINAT", dokumen_url=URL2),
    # 4: tanpa dokumen -> subsls run yang sama (akun sama, 10 mnt kemudian)
    b(timestamp="9/24/2026 17:12", baris="701", kunci="cccccddddd", nama_usaha="KIOS CONTOH (I MADE CONTOH)",
      kbli="47111", idsubsls="5.10806E+15", idsubsls_input="5.10806E+15", akun_login=A2,
      status="SKIP_DOKUMEN_BELUM_ADA"),
    # 5: akun lain tanpa jejak apa pun -> TIDAK ditebak
    b(timestamp="9/24/2026 20:00", baris="702", kunci="eeeeefffff", nama_usaha="KEDAI CONTOH (I WAYAN CONTOH)",
      kbli="47111", idsubsls="5.10806E+15", idsubsls_input="5.10806E+15", akun_login="ppl.ketiga@gmail.com",
      status="DOKUMEN_DIBUAT", dokumen_url=URL3),
    # 6: baris utuh (ditulis program sesudah Excel) -> tidak disentuh
    b(timestamp="2026-09-24 21:38:41", baris="703", kunci="0123456789", nama_usaha="X", kbli="47111",
      idsubsls="5108060006000224", idsubsls_input="5108060006000224", akun_login=A1, status="DOKUMEN_DIBUAT"),
]
sheet = [("700", "TOKO CONTOH (NI LUH CONTOH)", "aaaaabbbbb", "5108060021000401"),
         ("701", "KIOS CONTOH (I MADE CONTOH)", "cccccddddd", "5108060021000402"),
         ("702", "KEDAI CONTOH (I WAYAN CONTOH)", "eeeeefffff", "5108060021000403")]
hasil, masalah, disimpulkan = pulihkan(rusak, rujukan, {}, sheet)
check("0: baris rujukan dipakai utuh", hasil[0], rujukan[0])
check("1: kunci, idsubsls, subsls input, kbli, waktu",
      {k: hasil[1][k] for k in ("kunci", "idsubsls", "idsubsls_input", "kbli", "timestamp")},
      {"kunci": "1404364e03", "idsubsls": "5108050010000205", "idsubsls_input": "5108060006000224",
       "kbli": "01464", "timestamp": "2026-09-24 11:37:00"})
check("2: idsubsls dari sheet, input dari wilayah", (hasil[2]["idsubsls"], hasil[2]["idsubsls_input"]),
      ("5108060021000401", "5108060006000116"))
check("3: input dari baris berdokumen sama", hasil[3]["idsubsls_input"], "5108060006000116")
check("4: input dari run yang sama (dilaporkan)",
      (hasil[4]["idsubsls_input"], [d["baris"] for d in disimpulkan]), ("5108060006000116", ["701"]))
check("5: tanpa jejak -> masalah, nilai rusak dibiarkan",
      ([(m["baris"], m["kolom"]) for m in masalah], hasil[5]["idsubsls_input"]),
      ([("702", "idsubsls_input")], "5.10806E+15"))
check("6: baris utuh tidak disentuh", hasil[6], rusak[6])
check("sisa kerusakan hanya baris 5", dict(mg.kerusakan_excel(hasil)), {"idsubsls_input": 1})

# Tanpa kunci pulih, nama dianggap milik baris lain (gejala 2026-09-24) — sesudah pulih tidak lagi.
audit_rusak = [rusak[0]]
check("gejala: kunci rusak -> nama dipakai 'baris lain'",
      mg.kunci_lain_bernama_sama("WARUNG CONTOH (I KETUT CONTOH)", "1404364e03", A1, audit_rusak), "1.40E+09")
check("sesudah pulih: kunci sendiri", mg.kunci_lain_bernama_sama(
    "WARUNG CONTOH (I KETUT CONTOH)", "1404364e03", A1, hasil[:2]), "")

print("\nSEMUA PASS" if ok_all else "\nADA YANG FAIL")
sys.exit(0 if ok_all else 1)
