"""Uji approve_capi.py (daftar PML, suntik Console, target approve) + approve_pml --hanya-id. Offline.
Jalankan: python tests/test_approve_capi.py"""
import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approve_capi import approve_capi as ac
from approve_pml import approve_pml as ap

ok_semua = True


def check(label, got, want):
    global ok_semua
    ok = got == want
    ok_semua &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    daftar = tmp / "pml.txt"
    daftar.write_text("# PML kec A\nPML.Satu@contoh.id\npml.dua@contoh.id, pml.satu@contoh.id\n\nbukan-email\n", encoding="utf-8")
    emails, salah = ac.baca_daftar_pml(daftar)
    check("daftar PML: huruf kecil, unik, komentar & koma", emails, ["pml.satu@contoh.id", "pml.dua@contoh.id"])
    check("token bukan email dilaporkan", salah, ["bukan-email"])

    siap = ac.tulis_console(emails, tmp / "c.siap.js")
    teks = siap.read_text(encoding="utf-8")
    check("Console: daftar PML tersuntik", 'const DAFTAR_PML = ["pml.satu@contoh.id", "pml.dua@contoh.id"];' in teks, True)
    check("Console: penanda hilang", ac.PENANDA_PML in teks, False)

    baris = [
        {"id": "a1", "pml": "pml.satu@contoh.id", "status": ac.ST_SIAP_APPROVE},
        {"id": "a2", "pml": "PML.DUA@contoh.id", "status": ac.ST_SIAP_APPROVE},
        {"id": "a3", "pml": "lain@contoh.id", "status": ac.ST_SIAP_APPROVE},
        {"id": "a4", "pml": "pml.satu@contoh.id", "status": "DIKEMBALIKAN_CAPI_TERVERIFIKASI"},
        {"id": "a5", "pml": "pml.satu@contoh.id", "status": ""},
    ]
    per_pml, status, luar = ac.target_approve(baris, emails)
    check("target: hanya DIGANTI_PAPI_TERVERIFIKASI & PML di daftar", per_pml,
          {"pml.satu@contoh.id": ["a1"], "pml.dua@contoh.id": ["a2"]})
    check("PML di luar daftar dilaporkan", dict(luar), {"lain@contoh.id": 1})
    check("status dihitung", status[ac.ST_SIAP_APPROVE], 3)

    # approve_pml --hanya-id
    f = tmp / "id.csv"
    f.write_text("id,pml,status\nA1,pml.satu@contoh.id,DIGANTI_PAPI_TERVERIFIKASI\n"
                 "a9,pml.satu@contoh.id,DIKEMBALIKAN_CAPI_TERVERIFIKASI\nb1,,DIGANTI_PAPI_TERVERIFIKASI\n",
                 encoding="utf-8")
    check("baca --hanya-id (id huruf kecil, status disaring, pml kosong = umum)", ap.baca_hanya_id(f),
          {"pml.satu@contoh.id": {"a1"}, "": {"b1"}})
    f2 = tmp / "id2.csv"
    f2.write_text("id,pml\nx1,p@x.id\n", encoding="utf-8")
    check("--hanya-id tanpa kolom status", ap.baca_hanya_id(f2), {"p@x.id": {"x1"}})

    tg = ap.target_dari_berkas({"b2", "a1"}, "pml.satu@contoh.id", {"a1": {"kunci": "k", "baris": "7"}})
    check("target dari berkas: urut id, tanpa cek PPL, catatan audit ikut",
          [(t["id"], t["akun_ppl"], t["kunci"], t["sumber"]) for t in tg],
          [("a1", None, "k", "berkas"), ("b2", None, "", "berkas")])

    # --- paralel: bagi PML
    d5 = ["a@x.id", "b@x.id", "c@x.id", "d@x.id", "e@x.id"]
    check("bagi tanpa jumlah: rata per PML, urutan berkas", ac.bagi_pml(d5, 2),
          [["a@x.id", "c@x.id", "e@x.id"], ["b@x.id", "d@x.id"]])
    jml = {"a@x.id": 900, "b@x.id": 100, "c@x.id": 500, "d@x.id": 400, "e@x.id": 50}
    bag = ac.bagi_pml(d5, 2, jml)
    check("bagi dgn jumlah: beban seimbang", sorted(sum(jml[p] for p in b) for b in bag), [950, 1000])
    check("bagi: saling lepas & lengkap", sorted(p for b in bag for p in b), d5)
    check("bagi lebih banyak dari PML: bagian kosong boleh", [len(b) for b in ac.bagi_pml(d5[:2], 3)], [1, 1, 0])
    fj = tmp / "jumlah.csv"
    fj.write_text('﻿pml,siap,lain\n"A@x.id",12,3\n', encoding="utf-8")
    check("baca jumlah per PML", ac.baca_jumlah(fj), {"a@x.id": 12})

    folder = tmp / "bagian"
    (folder).mkdir()
    (folder / "daftar_pml.bagian-9-dari-9.txt").write_text("lama", encoding="utf-8")
    out = ac.tulis_bagian(d5, 2, None, folder)
    check("tulis bagian: berkas lama dihapus", (folder / "daftar_pml.bagian-9-dari-9.txt").exists(), False)
    check("tulis bagian: daftar terbaca ulang", ac.baca_daftar_pml(out[1][0])[0], ["b@x.id", "d@x.id"])
    js = out[0][1].read_text(encoding="utf-8")
    check("tulis bagian: label & PML tersuntik", ['const LABEL = ".bagian-1-dari-2";' in js,
          'const DAFTAR_PML = ["a@x.id", "c@x.id", "e@x.id"];' in js], [True, True])

    # --- gabung CSV beberapa bagian / versi
    c1 = tmp / "approve_capi.bagian-1-dari-2_20260929-0100Z.csv"
    c2 = tmp / "approve_capi.bagian-2-dari-2_20260929-0200Z.csv"
    c3 = tmp / "approve_capi.bagian-1-dari-2_20260929-0300Z.csv"
    c1.write_text("id,pml,status\nx1,a@x.id,DIGANTI_PAPI_TERVERIFIKASI\n", encoding="utf-8")
    c2.write_text("id,pml,status\ny1,b@x.id,DIGANTI_PAPI_TERVERIFIKASI\n", encoding="utf-8")
    c3.write_text("id,pml,status\nx1,a@x.id,DIKEMBALIKAN_CAPI_TERVERIFIKASI\nx2,a@x.id,DIGANTI_PAPI_TERVERIFIKASI\n",
                  encoding="utf-8")
    g = {b["id"]: b["status"] for b in ac.gabung_csv([c1, c2, c3])}
    check("gabung CSV: berkas lebih baru menang, bagian lain ikut", g,
          {"x1": "DIKEMBALIKAN_CAPI_TERVERIFIKASI", "y1": "DIGANTI_PAPI_TERVERIFIKASI", "x2": "DIGANTI_PAPI_TERVERIFIKASI"})

# --- approve paralel dlm satu PC
per = {"a@x.id": ["1"] * 900, "b@x.id": ["2"] * 100, "c@x.id": ["3"] * 500, "d@x.id": ["4"] * 400}
g = ac.kelompok_bot(per, 2)
check("bot paralel: saling lepas, beban seimbang", sorted(sum(len(per[p]) for p in k) for k in g), [900, 1000])
check("bot paralel: lebih banyak bot dari PML -> kelompok kosong dibuang", len(ac.kelompok_bot({"a@x.id": ["1"]}, 4)), 1)
with tempfile.TemporaryDirectory() as tmp2:
    import contextlib
    import io
    ac.HASIL = Path(tmp2)

    def cmd(teks, kode):
        return [sys.executable, "-c", f"import sys,time; time.sleep(0.5); print({teks!r}); sys.exit({kode})"]

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        kode = ac.jalankan_paralel([cmd("halo satu", 0), cmd("halo dua", 0)], "uji", jeda_mulai=0)
    keluar = buf.getvalue()
    check("paralel: semua sukses -> 0, keluaran berawalan bot",
          [kode, "[bot 1] halo satu" in keluar, "[bot 2] halo dua" in keluar], [0, True, True])
    check("paralel: log per bot", (Path(tmp2) / "log_approve_capi.uji.bot-2-dari-2.txt").read_text(encoding="utf-8").strip(),
          "halo dua")
    with contextlib.redirect_stdout(io.StringIO()):
        check("paralel: satu bot gagal -> 1", ac.jalankan_paralel([cmd("a", 0), cmd("b", 3)], "uji", jeda_mulai=0), 1)

print("\nSEMUA LULUS" if ok_semua else "\nADA YANG GAGAL")
sys.exit(0 if ok_semua else 1)
