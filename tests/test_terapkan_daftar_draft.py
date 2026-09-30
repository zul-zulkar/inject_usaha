"""Uji offline input_usaha/terapkan_daftar_draft.py + deteksi list terpotong di fasih_web."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_usaha.mesin as mg  # noqa: E402
from input_usaha import sisir  # noqa: E402
from input_usaha import terapkan_daftar_draft as tdd  # noqa: E402
from inti import fasih_web  # noqa: E402

GAGAL = []


def cek(nama, benar):
    print(("OK   " if benar else "FAIL ") + nama)
    if not benar:
        GAGAL.append(nama)


S = sisir.Sheet("bahan/x.xlsx")
D = tdd.Draft("5108010010000105 - Warung Contoh (I Ketut Contoh)", "WARUNG CONTOH (I KETUT CONTOH)",
              "ppl.contoh@mail.com", "draft", "PAPI")


def calon(baris, status, akun="ppl.contoh@mail.com", ada_dok=True):
    return tdd.Calon(S, SimpleNamespace(baris=baris, kunci=f"k{baris}"), status,
                     (akun, "5108010010000105", f"https://x/{baris}/entry") if ada_dok else None)


cek("terkirim palsu", tdd.golongkan(D, [calon(2, "TERKIRIM_BELUM_TERVERIFIKASI")])[0] == tdd.G_PALSU)
cek("terkunci", tdd.golongkan(D, [calon(2, mg.STATUS_TERKUNCI)])[0] == tdd.G_KUNCI)
cek("sudah antre", tdd.golongkan(D, [calon(2, "DRAFT_GALAT_DI_SERVER")])[0] == tdd.G_ANTRE)
cek("akun beda = ganda/pindah", tdd.golongkan(D, [calon(2, "TERKIRIM_TERVERIFIKASI", "ppl.kedua@mail.com")])[0]
    == tdd.G_AKUN)
cek("di luar audit", tdd.golongkan(D, [calon(2, "", ada_dok=False)])[0] == tdd.G_LUAR)
cek("tidak di sheet", tdd.golongkan(D, [])[0] == tdd.G_TIDAK)
DT = tdd.Draft(D.kode, D.nama, D.petugas, "rejected by pengawas", "PAPI")
cek("rejected -> DITOLAK_PML", tdd.golongkan(DT, [calon(2, "TERKIRIM_TERVERIFIKASI")])[0] == tdd.G_DITOLAK)
cek("rejected walau audit terkunci", tdd.golongkan(DT, [calon(2, mg.STATUS_TERKUNCI)])[0] == tdd.G_DITOLAK)
c_baru = calon(2, "TERKIRIM_BELUM_TERVERIFIKASI")
c_baru.terakhir = "2026-09-29 17:30:00"
cek("dikerjakan bot sesudah ekspor -> tidak ditandai ulang",
    tdd.golongkan(D, [c_baru], "2026-09-29 17:06:47")[0] == tdd.G_BASI)
cek("dikerjakan sebelum ekspor -> tetap terkirim palsu",
    tdd.golongkan(D, [c_baru], "2026-09-29 18:00:00")[0] == tdd.G_PALSU)
cek("rejected sudah bertanda -> sudah antre", tdd.golongkan(DT, [calon(2, mg.STATUS_DITOLAK)])[0] == tdd.G_ANTRE)
cek("ambigu", tdd.golongkan(D, [calon(2, "TERKIRIM_BELUM_TERVERIFIKASI"),
                                calon(3, "TERKIRIM_BELUM_TERVERIFIKASI")])[0] == tdd.G_AMBIGU)
cek("baris sama lewat 2 nama bukan ambigu",
    tdd.golongkan(D, [calon(2, "TERKIRIM_BELUM_TERVERIFIKASI")] * 2)[0] == tdd.G_PALSU)
cek("nama '-' diabaikan", not tdd.nama_berarti("-") and tdd.nama_berarti("WARUNG X"))
cek("nama dari kode identitas", tdd.nama_dari_kode(D.kode) == "WARUNG CONTOH (I KETUT CONTOH)")
idx = {"WARUNG CONTOH (I KETUT CONTOH)": [calon(2, "TERKIRIM_BELUM_TERVERIFIKASI")]}
kosong = tdd.Draft(D.kode, "-", D.petugas, "draft", "PAPI")
cek("draft bernama '-' dicocokkan lewat kode identitas", tdd.cocokkan([kosong], idx)[0][1] == tdd.G_PALSU)

# ekspor fasih-sm (kolom dicari lewat judul, non-draft/non-PAPI dibuang)
tmp = Path(os.environ.get("TEMP", ".")) / "uji_daftar_draft.csv"
tmp.write_text("Kode Identitas,Nama Keluarga/Bangunan/Usaha,Status,Mode,Petugas Saat Ini\n"
               f"{D.kode},{D.nama},draft,PAPI,PPL.Contoh@mail.com\n"
               f"{D.kode},{D.nama},submitted by pencacah,PAPI,ppl.contoh@mail.com\n"
               f"{D.kode},{D.nama},draft,CAPI,ppl.contoh@mail.com\n"
               f"{D.kode},{D.nama},rejected by pengawas,PAPI,ppl.contoh@mail.com\n", encoding="utf-8")
dd = tdd.baca_daftar_draft(str(tmp))
tmp.unlink()
cek("baca ekspor: draft & rejected PAPI saja, petugas kecil",
    [x.status for x in dd] == ["draft", "rejected by pengawas"] and dd[0].petugas == "ppl.contoh@mail.com")


# --- fasih_web: list terpotong 1.000 -> tidak lengkap + DRAFT tersaring digabung
class HalamanPalsu:
    """Server palsu: 1.500 dokumen, hanya 1.000 pertama bisa dipaging, totalHit dibatasi 1.000.
    Saringan DRAFT mengembalikan 3 draft (2 di luar 1.000 pertama)."""
    def __init__(self, saring_jujur=True):
        self.dok = [{"id": f"d{i}", "data1": f"U{i}", "assignmentStatusAlias":
                     "DRAFT" if i in (5, 1200, 1400) else "SUBMITTED BY Pencacah"} for i in range(1500)]
        self.saring_jujur = saring_jujur

    def evaluate(self, _js, arg):
        _url, body, _hdr = arg
        ekstra = body.get("assignmentExtraParam") or {}
        if ekstra.get("assignmentStatusAlias") == "DRAFT":
            data = [d for d in self.dok if d["assignmentStatusAlias"] == "DRAFT" or not self.saring_jujur]
            total = len(data)
        else:
            data, total = self.dok[:1000], 1000
        start, n = body["start"], body["length"]
        return {"status": 200, "text": json.dumps({"searchData": data[start:start + n] if start < 1000 else [],
                                                   "totalHit": total})}


def sesi(halaman):
    s = fasih_web.FasihWebSession.__new__(fasih_web.FasihWebSession)
    s.page = halaman
    s.daftar_dokumen_lengkap = True
    s.daftar_dokumen_terpotong = False
    s._log = lambda *_a, **_k: None
    return s


s = sesi(HalamanPalsu())
per_id, total = s._baca_list_berhalaman("u", {}, {}, 100)
cek("paging berhenti di batas server", len(per_id) == 1000 and total == 1000)
items = s._draft_tersaring("u", {}, {}, 100)
cek("draft tersaring terbaca", sorted(i["id"] for i in items) == ["d1200", "d1400", "d5"])
s2 = sesi(HalamanPalsu(saring_jujur=False))
cek("saringan tidak terbukti -> tidak dipakai", s2._draft_tersaring("u", {}, {}, 100) == [])

print(f"\n{len(GAGAL)} gagal")
sys.exit(1 if GAGAL else 0)
