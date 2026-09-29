# -*- coding: utf-8 -*-
"""Uji pindah_wilayah.py — offline, tanpa browser & tanpa sheet/audit asli (semua di folder sementara).
Alur Console: tests/test_pindah_wilayah_console.js & tests/test_pindah_wilayah_simulasi.js.
Jalankan: python tests/test_pindah_wilayah.py
"""
import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402
os.environ.setdefault("FASIH_ABAIKAN_CONFIG_LOKAL", "1")  # hasil uji tidak bergantung inti/config_lokal.py

import fasih_sm.pindah_wilayah.pindah_wilayah as pw  # noqa: E402
import input_usaha.mesin as mg  # noqa: E402
from input_usaha.sinkron_list import rencana_sinkron  # noqa: E402
from inti.gabungan_loader import GabunganRow  # noqa: E402
from inti.id_dokumen import url_entry  # noqa: E402

ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


ASG = "fd68e454-ba45-4b85-8205-f3bf777ded24"
WADAH, WADAH2 = "5108060006000224", "5108060006000116"
T1, T2, T3 = "5108060002000203", "5108010001000101", "5108010001000102"
AKUN = "ppl.contoh@mail.com"
_n = 0


def uid() -> str:
    global _n
    _n += 1
    return f"{_n:08x}-0000-4000-8000-{_n:012x}"


def row(baris, nama, tujuan=T1, pemilik="WAYAN", id_dokumen=""):
    r = GabunganRow(baris, {"akun_ppl": "komang", "idsubsls": tujuan, "nama": nama, "pengusaha": pemilik,
                            "nama_komersial": nama})
    r.id_dokumen = id_dokumen
    return r


def rec(r, status, url="", subsls=WADAH, akun=AKUN, nama=None):
    return {"timestamp": "2026-09-25 10:00:00", "baris": str(r.baris), "kunci": r.kunci,
            "nama_usaha": nama or r.nama_dokumen, "kbli": "47111", "idsubsls": r.idsubsls, "idsubsls_input": subsls,
            "akun_ppl": "komang", "akun_login": akun, "status": status, "dokumen_url": url}


# ------------------------------------------------------------------ target
ia, ib_sheet, ib_audit, ic, idd = uid(), uid(), uid(), uid(), uid()
a = row(2, "WARUNG SEMBAKO", id_dokumen=ia)                          # ID sheet = audit
b = row(3, "WARUNG KOPI", tujuan=T2, id_dokumen=ib_sheet)             # ID sheet != audit -> 2 ID
c = row(4, "BENGKEL", tujuan=T2)                                      # ID hanya di audit + nama lama
d = row(5, "TOKO BARU")                                               # belum punya dokumen
e = row(6, "SALON", tujuan="5.10806E+15", id_dokumen=idd)             # tujuan rusak
f = row(7, "KIOS PULSA", tujuan=T3, id_dokumen=uid())                 # ID hanya di sheet
kembar = row(2, "WARUNG SEMBAKO", id_dokumen="")                      # kunci sama dgn a (sheet sama)
audit1 = [
    rec(a, "DOKUMEN_DIBUAT", url_entry(ia, ASG)), rec(a, "TERKIRIM_TERVERIFIKASI", url_entry(ia, ASG)),
    rec(b, "DOKUMEN_DIBUAT", url_entry(ib_audit, ASG), subsls=WADAH2),
    rec(c, "DOKUMEN_DIBUAT", url_entry(ic, ASG), nama="BENGKEL LAMA (WAYAN)"),
    rec(c, "TERKIRIM_TERVERIFIKASI", url_entry(ic, ASG)),
    # catatan pindah lama: subsls tujuannya TIDAK boleh ikut jadi wadah
    {**rec(f, mg.STATUS_DIPINDAH, url_entry(f.id_dokumen, ASG), subsls=T3), "akun_login": "ppl.tujuan@mail.com"},
]
sheet = [("D:/x/input_tahap2.xlsx", [a, b, c, d, e, f, kembar], audit1)]
target, sumber, asal, masalah, ring = pw.bangun_target(sheet, asal_tambahan=["5108060006000205"])
per = {t["b"]: t for t in target}
check("sumber = nama berkas", sumber, ["input_tahap2.xlsx"])
check("target: baris ber-dokumen saja", sorted(per), [2, 3, 4, 7])
check("target a lengkap", per[2], {"k": a.kunci, "s": 0, "b": 2, "n": "WARUNG SEMBAKO (WAYAN)", "t": T1, "ids": [ia]})
check("ID sheet != audit -> dua-duanya", per[3]["ids"], sorted([ib_sheet, ib_audit]))
check("ID hanya audit + nama lama audit", (per[4]["ids"], per[4]["na"]), ([ic], ["BENGKEL LAMA (WAYAN)"]))
check("ringkasan", {k: ring[k] for k in ("belum_ada_dokumen", "id_sheet_beda_audit", "baris_kembar_digabung", "target_2_id")},
      {"belum_ada_dokumen": 1, "id_sheet_beda_audit": 1, "baris_kembar_digabung": 1, "target_2_id": 1})
check("tujuan rusak -> masalah", [(s, br) for s, br, _ in masalah], [("input_tahap2.xlsx", 6)])
check("wadah = idsubsls_input audit (tanpa catatan DIPINDAH) + tambahan", asal, sorted([WADAH, WADAH2, "5108060006000205"]))
t_rentang, *_ = pw.bangun_target(sheet, dari=3, sampai=4)
check("--dari/--sampai", [t["b"] for t in t_rentang], [3, 4])
t_awalan, _, _, _, r_aw = pw.bangun_target(sheet, tujuan=["510801"])
check("--tujuan awalan", ([t["b"] for t in t_awalan], r_aw["di_luar_saringan_tujuan"]), ([3, 4, 7], 3))
# dua batch berbagi kunci identik tapi dokumennya beda -> dua target terpisah
x21, x22 = uid(), uid()
t2b, s2b, *_ = pw.bangun_target([("b21.xlsx", [row(9, "APOTEK", id_dokumen=x21)], []),
                                 ("b22.xlsx", [row(9, "APOTEK", id_dokumen=x22)], [])])
check("kunci sama di dua sheet -> dua target (sumber beda)", [(t["s"], t["ids"]) for t in t2b], [(0, [x21]), (1, [x22])])

# ------------------------------------------------------------------ pilih audit
aud_kecil = [rec(a, "DOKUMEN_DIBUAT", url_entry(ia, ASG))]
pilih = pw.pilih_audit({a.kunci, b.kunci, c.kunci}, {Path("z/batch.csv"): audit1, Path("a/lain.csv"): aud_kecil, Path("b/kosong.csv"): []})
check("pilih audit yang paling mengenal dokumen sheet", pilih, (Path("z/batch.csv"), 3))
check("seri -> path terurut pertama", pw.pilih_audit({a.kunci}, {Path("b.csv"): aud_kecil, Path("a.csv"): aud_kecil}), (Path("a.csv"), 1))
check("tidak ada yang mengenal", pw.pilih_audit({"zzz"}, {Path("a.csv"): aud_kecil}), (None, 0))

# ------------------------------------------------------------------ bagi ke beberapa akun
banyak = [{"k": f"k{i}", "s": 0, "b": i, "n": "X", "t": f"51080100010{i % 7:05d}", "ids": [uid()]} for i in range(100)]
bagian = pw.bagi_target(banyak, 3)
tujuan_per = [{t["t"] for t in b_} for b_ in bagian]
check("bagi: semua target terbagi, tidak ada yang ganda", sorted(t["k"] for b_ in bagian for t in b_), sorted(t["k"] for t in banyak))
check("bagi: satu subsls tujuan utuh di satu bagian", any(tujuan_per[i] & tujuan_per[j] for i in range(3) for j in range(i + 1, 3)), False)
check("bagi: beban seimbang (selisih <= subsls terbesar)", max(map(len, bagian)) - min(map(len, bagian)) <= 15, True)
check("bagi: deterministik", [[t["k"] for t in b_] for b_ in pw.bagi_target(list(reversed(banyak)), 3)],
      [[t["k"] for t in b_] for b_ in bagian])
check("bagi: urut tujuan, baris", all(b_ == sorted(b_, key=lambda t: (t["t"], t["s"], t["b"])) for b_ in bagian), True)
check("bagi 1 = semua", len(pw.bagi_target(banyak, 1)[0]), 100)

# ------------------------------------------------------------------ Console
ns = argparse.Namespace(per_kirim=40, cek_sesudah=5, jeda_kirim=4.0, jeda_baca=None, jarak_request=1.2, izinkan_tujuan_selesai=True)
k = pw.konfig_console(ns, "2/3")
check("konfig console dari CLI", (k["bagian"], k["opsi"]),
      ("2/3", {"perKirim": 40, "cekSesudah": 5, "jedaKirimMin": 4000, "jedaKirimMaks": 8000, "jarakRequestMs": 1200,
               "izinkanTujuanSelesai": True}))
kosong = argparse.Namespace(per_kirim=None, cek_sesudah=None, jeda_kirim=None, jeda_baca=None, jarak_request=None,
                            izinkan_tujuan_selesai=False)
check("tanpa opsi -> bawaan Console", pw.konfig_console(kosong)["opsi"], {})
templat = pw.KONSOL_TEMPLATE.read_text(encoding="utf-8")
teks = pw.isi_template(templat, target, sumber, asal, k)
check("template: semua penanda terganti", [p in teks for p in pw.PENANDA.values()], [False] * len(pw.PENANDA))
check("template: target tersuntik", f'"ids":["{ia}"]' in teks, True)
try:
    pw.isi_template("tanpa penanda", [], [], [], {})
    check("template rusak ditolak", False, True)
except ValueError:
    check("template rusak ditolak", True, True)

with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp)
    (folder / "pindah_wilayah_console.bagian-1-dari-5.siap.js").write_text("lama", encoding="utf-8")
    (folder / "pindah_wilayah_console.siap.js").write_text("lama", encoding="utf-8")
    keluar = pw.tulis_console(pw.bagi_target(banyak, 2), ["s.xlsx"], [WADAH], kosong, folder)
    check("--bagi 2: dua berkas, berkas pembagian lama dihapus", sorted(p.name for p in folder.iterdir()),
          ["pindah_wilayah_console.bagian-1-dari-2.siap.js", "pindah_wilayah_console.bagian-2-dari-2.siap.js"])
    check("berkas bagian memuat label bagian", '"bagian":"2/2"' in keluar[1].read_text(encoding="utf-8"), True)
    pw.tulis_console([banyak], ["s.xlsx"], [WADAH], kosong, folder)
    check("--bagi 1: satu berkas biasa, berkas bagian dihapus", sorted(p.name for p in folder.iterdir()), ["pindah_wilayah_console.siap.js"])
    pembagian = pw.tulis_pembagian(pw.bagi_target(banyak, 2), folder / "p.csv")
    baris_p = list(csv.DictReader(pembagian.open(encoding="utf-8-sig")))
    check("pembagian.csv: jumlah dokumen", sum(int(r_["jumlah_dokumen"]) for r_ in baris_p), 100)
    tujuan_txt = pw.tulis_daftar_tujuan(target, folder / "t.txt")
    check("daftar tujuan unik", tujuan_txt, sorted({T1, T2, T3}))

# ------------------------------------------------------------------ --catat
unduh = [
    {"waktu": "2026-09-28T01:00:00", "sumber": "input_tahap2.xlsx", "baris": "2", "kunci": a.kunci, "ids": ia, "id": ia,
     "asal": WADAH, "tujuan": T1, "status": "DIPINDAH_SERVER_OK", "pengawas": "pml@x", "pencacah": "PPL.Tujuan@mail.com"},
    {"waktu": "2026-09-28T02:00:00", "sumber": "input_tahap2.xlsx", "baris": "2", "kunci": a.kunci, "ids": ia, "id": ia,
     "asal": WADAH, "tujuan": T1, "status": "DIPINDAH_TERVERIFIKASI", "pengawas": "pml@x", "pencacah": "PPL.Tujuan@mail.com"},
    # audit menunjuk ib_audit (terhapus), yang hidup & dipindah ib_sheet
    {"waktu": "2026-09-28T01:00:00", "sumber": "input_tahap2.xlsx", "baris": "3", "kunci": b.kunci,
     "ids": f"{ib_sheet};{ib_audit}", "id": ib_sheet, "asal": WADAH, "tujuan": T2, "status": "SUDAH_DI_TUJUAN"},
    {"waktu": "2026-09-28T01:00:00", "sumber": "input_tahap2.xlsx", "baris": "4", "kunci": c.kunci, "ids": ic, "id": ic,
     "asal": WADAH, "tujuan": T2, "status": "BELUM_APPROVED"},
    {"waktu": "2026-09-28T01:00:00", "sumber": "lain.xlsx", "baris": "9", "kunci": "tidakdikenal", "ids": uid(), "id": "",
     "asal": WADAH, "tujuan": T2, "status": "DIPINDAH_TERVERIFIKASI"},
]
hasil = pw.pilih_hasil(unduh)
check("pilih hasil: bukti terkuat per dokumen, status tak tuntas & ID kosong dibuang",
      sorted((h["kunci"], h["status"]) for h in hasil), sorted([(a.kunci, "DIPINDAH_TERVERIFIKASI"), (b.kunci, "SUDAH_DI_TUJUAN")]))
# audit batch lain yang kuncinya kebetulan sama dgn a, tapi dokumennya BEDA -> tidak disentuh
lain_id = uid()
audit_lain = [rec(a, "TERKIRIM_TERVERIFIKASI", url_entry(lain_id, ASG))]
audit_salinan = [dict(r_) for r_ in audit1]                  # audit bawaan yang memuat batch yang sama
tulis, rk, tidak = pw.rencana_catat(hasil, {Path("batch.csv"): audit1, Path("salinan.csv"): audit_salinan, Path("lain.csv"): audit_lain})
check("catat: ke setiap audit yang menunjuk dokumen itu", {p.name: len(v) for p, v in tulis.items()}, {"batch.csv": 2, "salinan.csv": 2})
baris_a = next(r_ for r_ in tulis[Path("batch.csv")] if r_["kunci"] == a.kunci)
check("catat: isi baris", {k_: baris_a[k_] for k_ in ("status", "akun_login", "idsubsls_input", "dokumen_url", "baris", "kbli")},
      {"status": mg.STATUS_DIPINDAH, "akun_login": "ppl.tujuan@mail.com", "idsubsls_input": T1,
       "dokumen_url": url_entry(ia, ASG), "baris": "2", "kbli": "47111"})
baris_b = next(r_ for r_ in tulis[Path("batch.csv")] if r_["kunci"] == b.kunci)
check("catat: audit yang menunjuk ID lama target diarahkan ke dokumen yang hidup",
      (baris_b["dokumen_url"], baris_b["akun_login"], "audit dulu menunjuk" in baris_b["error_message"]),
      (url_entry(ib_sheet, ASG), "", True))
check("catat: tidak ada yang tak dikenal", tidak, [])
setelah = audit1 + tulis[Path("batch.csv")]
tulis2, rk2, _ = pw.rencana_catat(hasil, {Path("batch.csv"): setelah})
check("catat: idempoten", (tulis2, rk2["sudah_dicatat"]), ({}, 2))

# efek catatan pada input_usaha & sinkron akun input
check("DIPINDAH_WILAYAH dihitung tuntas", mg.STATUS_DIPINDAH in mg.STATUS_TERKIRIM, True)
alasan = mg.alasan_lewati_saat_giliran(a.kunci, (AKUN, WADAH), set(mg.STATUS_TERKIRIM), a.nama_dokumen, audit=setelah, id_sheet=ia)
check("input_usaha: baris yang dokumennya dipindah dilewati", alasan.startswith("dokumennya sudah dibuat proses lain"), True)
check("dokumen_dari menunjuk dokumen yang dipindah", mg.dokumen_dari(setelah)[b.kunci], ("", T2, url_entry(ib_sheet, ASG)))
_lap, tulis_sinkron, _ = rencana_sinkron([("s", a, "SIAP"), ("s", c, "SIAP")], [], AKUN, WADAH, ASG, setelah, lengkap=True)
check("sinkron akun input (list utuh, dokumen tak ada): TIDAK menulis DOKUMEN_DIHAPUS utk dokumen yang dipindah",
      [(t_["kunci"] == a.kunci, t_["status"]) for t_ in tulis_sinkron], [(False, "DOKUMEN_DIHAPUS")])

with tempfile.TemporaryDirectory() as tmp:
    berkas_audit = Path(tmp) / "audit_log_gabungan.csv"
    with berkas_audit.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=mg.AUDIT_FIELDS)
        w.writeheader()
        for r_ in audit1:
            w.writerow({k_: r_.get(k_, "") for k_ in mg.AUDIT_FIELDS})
    berkas_unduh = Path(tmp) / "audit_pindah_wilayah_20260928-010000.csv"
    with berkas_unduh.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(unduh[0]))
        w.writeheader()
        w.writerows(unduh)
    kode = pw.main(["--catat", "--unduhan", str(berkas_unduh), "--audit", str(berkas_audit)])
    check("--catat tanpa --tulis tidak menulis", (kode, len(pw.baca_csv(berkas_audit))), (0, len(audit1)))
    kode = pw.main(["--catat", "--unduhan", str(berkas_unduh), "--audit", str(berkas_audit), "--tulis"])
    isi = pw.baca_csv(berkas_audit)
    check("--catat --tulis: baris ditambahkan + cadangan", (kode, len(isi), len(list(Path(tmp).glob("*.bak-*")))),
          (0, len(audit1) + 2, 1))
    pw.main(["--catat", "--unduhan", str(berkas_unduh), "--audit", str(berkas_audit), "--tulis"])
    check("--catat --tulis kedua kali: tidak ada baris baru", len(pw.baca_csv(berkas_audit)), len(audit1) + 2)

print("\nSEMUA LULUS" if ok_all else "\nADA YANG GAGAL")
sys.exit(0 if ok_all else 1)
