#!/usr/bin/env python3
"""test_pindah_struktur.py — uji OFFLINE antar_pc/pindah_struktur.py (migrasi struktur folder
2026-09-25) di folder sementara. Jalankan: python tests/test_pindah_struktur.py

Yang dikunci: audit LAMA di akar -> audit/batch21/ (utuh, byte sama), batch 22 di audit/ tidak
disentuh, tujuan yang sudah ada TIDAK ditimpa (asal dibiarkan & dilaporkan), tanpa --jalankan
tidak ada yang berpindah, dan kode lama masuk arsip/kode_lama/ (tidak dihapus)."""

import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from antar_pc.pindah_struktur import nama_tujuan, pindahkan  # noqa: E402

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


def tulis(akar: Path, rel: str, isi: str = "x") -> None:
    p = akar / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(isi, encoding="utf-8")


cek("cek_gabungan -> cek_input", nama_tujuan("cek_gabungan.csv"), "cek_input.csv")
cek("status otomatis tanpa _tahap2", nama_tujuan(".status_otomatis_tahap2_pst.json"), ".status_otomatis_pst.json")
cek("log otomatis tanpa _tahap2", nama_tujuan("log_otomatis_tahap2_pc2.txt"), "log_otomatis_pc2.txt")
cek("nama lain tetap", nama_tujuan("list_api_a_at_x.json"), "list_api_a_at_x.json")

with tempfile.TemporaryDirectory() as d:
    akar = Path(d)
    tulis(akar, "audit_log_gabungan.csv", "batch21")
    tulis(akar, "audit_log_gabungan.csv.bak-20260924-143912", "cadangan")
    tulis(akar, "audit/audit_log_gabungan.csv", "batch22")          # batch 22 sudah di tempat baru
    tulis(akar, "audit_approve_pml.csv", "approve")
    tulis(akar, "audit_pc/pc_a/audit_log_gabungan_a.csv", "pc a")
    tulis(akar, "cek_gabungan.csv")
    tulis(akar, "list_api_a_at_x.json", "[]")
    tulis(akar, "pindah_wilayah_console.siap.js")
    tulis(akar, ".sesi_fasih_web_a_x.json", "{}")
    tulis(akar, "daftar_subsls.txt", "5108")
    tulis(akar, "Agenda.xlsx")
    tulis(akar, "input_gabungan/main_gabungan.py", "# lama")
    tulis(akar, "config.py", "# lama")
    tulis(akar, "run_tahap2.txt", "catatan")
    tulis(akar, "README.md", "readme")
    tulis(akar, "entah.dat")
    tulis(akar, "input_usaha/hasil/list_api_a_at_x.json", "baru")     # tujuan SUDAH ada -> konflik

    dipindah, konflik, tak_dikenal = pindahkan(akar, "audit/batch21", jalankan=False)
    cek("rencana saja: audit lama belum berpindah", (akar / "audit_log_gabungan.csv").exists(), True)
    tujuan = dict(dipindah)
    cek("audit lama -> audit/batch21", tujuan.get("audit_log_gabungan.csv"), "audit/batch21/audit_log_gabungan.csv")
    cek("cadangan ikut batch21", tujuan.get("audit_log_gabungan.csv.bak-20260924-143912"),
        "audit/batch21/audit_log_gabungan.csv.bak-20260924-143912")
    cek("approve -> audit/", tujuan.get("audit_approve_pml.csv"), "audit/audit_approve_pml.csv")
    cek("audit_pc isi -> audit/pc", tujuan.get("audit_pc/pc_a"), "audit/pc/pc_a")
    cek("cek_gabungan -> input_usaha/hasil/cek_input.csv", tujuan.get("cek_gabungan.csv"),
        "input_usaha/hasil/cek_input.csv")
    cek("siap.js -> fasih_sm/<alat>/hasil", tujuan.get("pindah_wilayah_console.siap.js"),
        "fasih_sm/pindah_wilayah/hasil/pindah_wilayah_console.siap.js")
    cek("sesi -> approve_pml/hasil", tujuan.get(".sesi_fasih_web_a_x.json"), "approve_pml/hasil/.sesi_fasih_web_a_x.json")
    cek("daftar -> bahan", tujuan.get("daftar_subsls.txt"), "bahan/daftar_subsls.txt")
    cek("Agenda -> arsip", tujuan.get("Agenda.xlsx"), "arsip/Agenda.xlsx")
    cek("kode lama -> arsip/kode_lama", (tujuan.get("input_gabungan"), tujuan.get("config.py")),
        ("arsip/kode_lama/input_gabungan", "arsip/kode_lama/config.py"))
    cek("run_*.txt & README dibiarkan", ("run_tahap2.txt" in tujuan, "README.md" in tujuan), (False, False))
    cek("tujuan sudah ada = konflik", konflik, [("list_api_a_at_x.json", "input_usaha/hasil/list_api_a_at_x.json")])
    cek("tak dikenal dibiarkan", [p.name for p in tak_dikenal], ["entah.dat"])

    pindahkan(akar, "audit/batch21", jalankan=True)
    cek("audit batch21 utuh", (akar / "audit/batch21/audit_log_gabungan.csv").read_text(encoding="utf-8"), "batch21")
    cek("audit batch22 tidak disentuh", (akar / "audit/audit_log_gabungan.csv").read_text(encoding="utf-8"), "batch22")
    cek("akar bersih dari audit lama", (akar / "audit_log_gabungan.csv").exists(), False)
    cek("audit_pc kosong dihapus", (akar / "audit_pc").exists(), False)
    cek("konflik TIDAK ditimpa", ((akar / "list_api_a_at_x.json").read_text(encoding="utf-8"),
                                  (akar / "input_usaha/hasil/list_api_a_at_x.json").read_text(encoding="utf-8")),
        ("[]", "baru"))
    cek("kode lama tetap ada (dipindah, bukan dihapus)",
        (akar / "arsip/kode_lama/input_gabungan/main_gabungan.py").read_text(encoding="utf-8"), "# lama")
    dipindah2, _, _ = pindahkan(akar, "audit/batch21", jalankan=False)
    cek("dijalankan ulang: tidak ada lagi yang dipindah", dipindah2, [])

print(f"\n{'SEMUA UJI LULUS' if not gagal else f'{gagal} UJI GAGAL'}")
_sys.exit(1 if gagal else 0)
