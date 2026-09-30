"""Uji offline input_usaha/sisir.py (rencana & penjadwal, tanpa browser)."""
import os
import sys
import threading
from pathlib import Path

os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_usaha.mesin as mg  # noqa: E402
from input_usaha import sisir  # noqa: E402

GAGAL = []


def cek(nama, benar):
    print(("OK   " if benar else "FAIL ") + nama)
    if not benar:
        GAGAL.append(nama)


S = sisir.Sheet("bahan/x.xlsx")
AKUN = {"a@x.com", "b@x.com"}
tuntas = set(mg.STATUS_TERKIRIM)


def tf(st, koord):
    return mg.tuntas_menurut_audit(st, tuntas, koord)


def gol(**kw):
    d = dict(baris=2, nama="N", kunci="k", lolos=True, punya_koordinat=True, id_sheet="",
             status="", dokumen=None, akun_dipakai=AKUN, tuntas_fn=tf)
    d.update(kw)
    return sisir.golongkan(**d)


# --- golongan
cek("ditolak pemeriksaan", gol(lolos=False)[0] == sisir.GOL_DITOLAK)
cek("terkirim = tuntas", gol(status="TERKIRIM_TERVERIFIKASI", dokumen=("a@x.com", "", "u"))[0] == sisir.GOL_TUNTAS)
cek("draft milik akun", gol(status="DOKUMEN_DIBUAT", dokumen=("A@x.com", "", "u")) == (sisir.GOL_MILIK, "a@x.com"))
cek("draft akun luar daftar", gol(status="DOKUMEN_DIBUAT", dokumen=("z@x.com", "", "u"))[0] == sisir.GOL_LUAR)
cek("tanpa url -> sinkron", gol(status=mg.STATUS_TANPA_URL, dokumen=("a@x.com", "", ""))[0] == sisir.GOL_SINKRON)
cek("ID sheet tanpa audit", gol(id_sheet="1234")[0] == sisir.GOL_ID_SAJA)
cek("belum ada = baru", gol()[0] == sisir.GOL_BARU)
cek("draft tanpa koordinat, sheet masih kosong = tuntas",
    gol(status=mg.STATUS_DRAFT_TANPA_KOORDINAT, punya_koordinat=False, dokumen=("a@x.com", "", "u"))[0] == sisir.GOL_TUNTAS)
cek("draft tanpa koordinat, koordinat sudah diisi = milik",
    gol(status=mg.STATUS_DRAFT_TANPA_KOORDINAT, punya_koordinat=True, dokumen=("a@x.com", "", "u"))[0] == sisir.GOL_MILIK)

# --- susun pekerjaan
R = sisir.BarisRencana
rencana = ([R(S, b, "n", sisir.GOL_BARU) for b in range(2, 12)]
           + [R(S, 20, "n", sisir.GOL_MILIK, "a@x.com"), R(S, 21, "n", sisir.GOL_MILIK, "a@x.com"),
              R(S, 30, "n", sisir.GOL_TUNTAS)])
kerja = sisir.susun_pekerjaan(rencana, 4)
cek("milik dulu", kerja[0].akun == "a@x.com" and kerja[0].baris == [20, 21])
cek("baru dipotong 4", [len(k.baris) for k in kerja[1:]] == [4, 4, 2])
semua = [b for k in kerja for b in k.baris]
cek("tiap baris tepat sekali", sorted(semua) == sorted(set(semua)) and 30 not in semua)
cek("ringkas baris", sisir.ringkas_baris([7, 2, 3, 4, 9, 10]) == "2-4,7,9-10")


# --- penjadwal (jam virtual, pelari tiruan)
class Jam:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def tidur(self, d):
        self.t += d


def hasil_ok():
    return {"rc": 0, "tuntas": True, "sisa": 0, "rate_limited": False, "akun_dipakai": False,
            "stop_manusia": False, "audit_tidak_cocok": False}


def uji_penjadwal(perilaku, akun, kerja, paralel=2):
    jam = Jam()
    log = []
    aktif = {}
    kunci = threading.Lock()
    maks = [0]

    def jalan(p, a):
        with kunci:
            aktif[a] = aktif.get(a, 0) + 1
            cek_satu = aktif[a] == 1
            maks[0] = max(maks[0], sum(aktif.values()))
            log.append((p.ke, a, cek_satu))
        h = hasil_ok()
        h.update(perilaku(p, a, len(log)))
        with kunci:
            aktif[a] -= 1
        return h

    pj = sisir.Penjadwal(akun, jalan, paralel=paralel, jeda_limit=100, jam=jam, tidur=jam.tidur)
    hasil = pj.putaran(kerja)
    return pj, hasil, log, maks[0]


def kerja_baru(n):
    ks = [sisir.Pekerjaan(S, [i]) for i in range(n)]
    for i, k in enumerate(ks, 1):
        k.ke = i
    return ks


pj, hasil, log, maks = uji_penjadwal(lambda p, a, n: {}, ["a", "b", "c"], kerja_baru(6), paralel=2)
cek("semua pekerjaan jalan", sorted(p.ke for p, _, _ in hasil) == [1, 2, 3, 4, 5, 6])
cek("maks paralel dipatuhi", maks <= 2)
cek("satu akun satu proses", all(x[2] for x in log))

# limit: potongan baru dikembalikan & dikerjakan akun lain
dilimit = set()


def limit_sekali(p, a, n):
    if a == "a" and "a" not in dilimit:
        dilimit.add("a")
        return {"rate_limited": True, "tuntas": False}
    return {}


pj, hasil, log, _ = uji_penjadwal(limit_sekali, ["a", "b"], kerja_baru(3), paralel=1)
ke_ok = sorted(p.ke for p, a, h in hasil if not h.get("rate_limited"))
cek("potongan yang kena limit dikerjakan ulang", ke_ok == [1, 2, 3])
cek("akun limit istirahat", pj.keadaan["a"].istirahat_sampai > 0)

# pekerjaan milik akun yang mati tidak dijalankan akun lain
k = [sisir.Pekerjaan(S, [1], "a", 1), sisir.Pekerjaan(S, [2], "a", 2), sisir.Pekerjaan(S, [3], "", 3)]
pj, hasil, log, _ = uji_penjadwal(lambda p, a, n: {"akun_dipakai": a == "a"}, ["a", "b"], k, paralel=1)
cek("akun mati tidak dipakai lagi", pj.keadaan["a"].mati and not any(a == "b" and p.akun == "a" for p, a, _ in hasil))
cek("pekerjaan milik tidak pindah akun", all(p.akun in ("", a) for p, a, _ in hasil))

# audit tidak cocok -> berhenti total
pj, hasil, log, _ = uji_penjadwal(lambda p, a, n: {"audit_tidak_cocok": True}, ["a"], kerja_baru(4), paralel=1)
cek("audit tidak cocok menghentikan semuanya", pj.berhenti_total and len(hasil) == 1)

# daftar sheet & akun
tmp = Path(os.environ.get("TEMP", ".")) / "sisir_uji_sheet.txt"
tmp.write_text("# komentar\nbahan/a.xlsx audit/batch21\n\nbahan/b.xlsx  # bawaan\n", encoding="utf-8")
ds = sisir.baca_daftar_sheet(str(tmp))
cek("daftar sheet", ds == [sisir.Sheet("bahan/a.xlsx", "audit/batch21"), sisir.Sheet("bahan/b.xlsx", "")])
tmp.unlink()
cek("baca akun unik & kecil", sisir.baca_akun("A@x.com, a@x.com\nppl.contoh@mail.com") == ["a@x.com", "ppl.contoh@mail.com"])

# --- TAHAP 0: sinkron semua akun (pelari tiruan)
sh = [sisir.Sheet("bahan/a.xlsx", "audit/batch21"), sisir.Sheet("bahan/b.xlsx", "audit/batch23"),
      sisir.Sheet("bahan/c.xlsx", "audit/batch23"), sisir.Sheet("bahan/d.xlsx", "")]
cek("kelompok audit", sisir.kelompok_audit(sh) == [("audit/batch21", ["bahan/a.xlsx"]),
                                                  ("audit/batch23", ["bahan/b.xlsx", "bahan/c.xlsx"]),
                                                  ("", ["bahan/d.xlsx"])])
c1 = sisir.perintah_sinkron("a@x.com", "5108010010000105", "audit/batch21", ["bahan/a.xlsx"], Path("l.json"), True)
c2 = sisir.perintah_sinkron("a@x.com", "5108010010000105", "", ["bahan/d.xlsx"], Path("l.json"), False)
cek("pertama: login & simpan json, tulis", "--simpan-json" in c1 and "--dari-json" not in c1 and "--tulis" in c1)
cek("berikutnya: dari json, audit bawaan tanpa --audit", "--dari-json" in c2 and "--audit" not in c2)
panggilan = []
kunci_uji = threading.Lock()


def pelari(cmd, _log):
    akun = cmd[cmd.index("--akun-tunggal") + 1]
    with kunci_uji:
        panggilan.append((akun, "--simpan-json" in cmd))
    if akun == "b@x.com" and "--simpan-json" in cmd:
        return 1, "gagal login"
    return 0, "Akan ditambahkan ke audit: 2 baris {'DITOLAK_PML': 2}"


hs = sisir.sinkron_semua(["a@x.com", "b@x.com"], sh, "5108010010000105", 2, jalankan=pelari)
cek("akun a: 3 kelompok audit, login sekali", sorted(p for a, p in panggilan if a == "a@x.com") == [False, False, True])
cek("akun b gagal login -> kelompok lain dilewati", [p for a, p in panggilan if a == "b@x.com"] == [True])
cek("ringkasan per akun", "DITOLAK_PML" in hs["a@x.com"] and "GAGAL" in hs["b@x.com"])

print(f"\n{len(GAGAL)} gagal")
sys.exit(1 if GAGAL else 0)
