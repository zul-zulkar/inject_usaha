"""Uji offline input_usaha/otomatis.py — deteksi rate limit dari output bot.

Yang dikunci: "429" polos BUKAN tanda rate limit. ID survei di setiap URL dokumen
(`a0429e96-…`) memuatnya, sehingga (2026-09-25) SEMUA run terbaca "kena limit" &
wrapper pindah ke akun cadangan / berhenti padahal server tidak menolak apa pun."""
import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh Buleleng di config.py

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from input_usaha.otomatis import evaluasi_hasil

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


print("\n== rate limit ==")
for teks, harap in (("HTTP 429", True), ("status: 429", True), ("429 Too Many Requests", True),
                    ('{"error":"RATE_LIMIT_EXCEEDED"}', True), ("Too many request", True),
                    ("terlalu banyak permintaan", True),
                    ("https://fasih-web.bps.go.id/survey/a0429e96-51a5-477b/entry", False),
                    ("baris 429: SIAP", False), ("totalHit 1429", False), ("id 4291abcd", False)):
    cek(teks, evaluasi_hasil(teks)["rate_limited"], harap)

print("\n== tuntas ==")
cek("selesai tanpa sisa", evaluasi_hasil(
    "Ringkasan run: 5 baris diproses, 2 dilewati, 0 belum sempat dikerjakan\nSelesai. Audit: a.csv")["tuntas"], True)
cek("masih ada sisa", evaluasi_hasil(
    "Ringkasan run: 5 baris diproses, 2 dilewati, 3 belum sempat dikerjakan\nSelesai. Audit: a.csv")["tuntas"], False)

print("\n== rate limit hanya dari ekor output ==")
tengah = "HTTP 429 sesaat\n" + "\n".join(f"baris {i}: TERKIRIM" for i in range(200))
cek("limit di tengah lalu run jalan terus -> bukan limit", evaluasi_hasil(tengah)["rate_limited"], False)
cek("limit di akhir -> limit + bukti", evaluasi_hasil(tengah + "\nstatus: 429")["bukti_rate_limit"], "status: 429")

print("\n== audit tidak cocok = berhenti, tidak diulang ==")
from input_usaha.mesin import PENANDA_AUDIT_TIDAK_COCOK  # noqa: E402
cek("penanda mesin dikenali wrapper",
    evaluasi_hasil(f"{PENANDA_AUDIT_TIDAK_COCOK}: 369 baris x.xlsx menyimpan ID ...")["audit_tidak_cocok"], True)
cek("run biasa bukan audit tidak cocok",
    evaluasi_hasil("Selesai. Audit: audit/audit_log_gabungan.csv")["audit_tidak_cocok"], False)

print("\n== status tersimpan ==")
from input_usaha.otomatis import status_berlaku  # noqa: E402

ARG = {"akun": "ppl.contoh@mail.com", "subsls": "5108060006000110", "akun_cadangan": "pml.satu@mail.com",
       "subsls_cadangan": "5108060006000116", "dari": 11, "sampai": 200, "sumber": "a.xlsx"}
cadangan = {"akun_aktif": "pml.satu@mail.com", "subsls_aktif": "5108060006000116", "pakai_cadangan": True}
cek("status format lama (tanpa argumen) diabaikan", status_berlaku(cadangan, ARG)[0], {})
cek("status dari perintah SAMA dipakai", status_berlaku({**cadangan, "argumen": ARG}, ARG)[0],
    {**cadangan, "argumen": ARG})
cek("akun utama diganti -> status cadangan lama diabaikan",
    status_berlaku({**cadangan, "argumen": ARG}, {**ARG, "akun": "ppl.dua@mail.com"})[0], {})
cek("rentang diganti -> diabaikan", status_berlaku({**cadangan, "argumen": ARG}, {**ARG, "dari": 201})[0], {})
cek("pasangan akun/subsls asing -> diabaikan",
    status_berlaku({**cadangan, "subsls_aktif": "5108060006000224", "argumen": ARG}, ARG)[0], {})
cek("tanpa status -> kosong tanpa pesan", status_berlaku({}, ARG), ({}, ""))

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
