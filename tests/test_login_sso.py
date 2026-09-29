"""Uji offline pilihan jalur login SSO (Pegawai / Eksternal) di inti/fasih_web.py.
Halaman tiruan meniru form SSO Pegawai asli (sso.bps.go.id realm pegawai-bps, dilihat
2026-09-29: #username, #password, #kc-login) — tanpa browser/VPN.
Jalankan: python tests/test_login_sso.py"""
import os
os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"   # uji pakai data contoh di config.py

import argparse
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inti.fasih_web as fw
from inti.config import L, SEL

gagal = 0


def cek(nama, dapat, harap):
    global gagal
    if dapat == harap:
        print(f"  OK  {nama}")
    else:
        gagal += 1
        print(f"  !!  {nama}\n        dapat : {dapat!r}\n        harap : {harap!r}")


print("\n== jenis_sso_akun ==")
for akun, pilihan, harap in (("ppl.contoh@gmail.com", "otomatis", "eksternal"),
                             ("pegawai.contoh@bps.go.id", "otomatis", "pegawai"),
                             ("PEGAWAI.Contoh@BPS.GO.ID ", "otomatis", "pegawai"),
                             ("pegawai.contoh@bali.bps.go.id", "otomatis", "pegawai"),
                             ("orang@bukanbps.go.id", "otomatis", "eksternal"),
                             ("pegawai.contoh", "otomatis", "pegawai"),
                             ("pegawai.contoh@bps.go.id", "eksternal", "eksternal"),
                             ("ppl.contoh@gmail.com", "pegawai", "pegawai")):
    cek(f"{akun} / {pilihan}", fw.jenis_sso_akun(akun, pilihan), harap)
try:
    fw.jenis_sso_akun("a@b.c", "sso-lain")
    cek("pilihan tak dikenal ditolak", False, True)
except SystemExit:
    cek("pilihan tak dikenal ditolak", True, True)

print("\n== opsi --sso ==")
ap = argparse.ArgumentParser()
fw.opsi_sso(ap)
cek("bawaan kosong", ap.parse_args([]).sso, "")
lama = fw.JENIS_SSO
fw.pakai_opsi_sso(ap.parse_args(["--sso", "pegawai"]))
cek("--sso pegawai menimpa JENIS_SSO", fw.jenis_sso_akun("ppl.contoh@gmail.com"), "pegawai")
fw.pakai_opsi_sso(ap.parse_args([]))
cek("tanpa --sso tidak mengubah", fw.JENIS_SSO, "pegawai")
fw.JENIS_SSO = lama


# ------------------------------------------------------------------ halaman tiruan
class Lok:
    def __init__(self, hal, kunci):
        self.hal, self.kunci = hal, kunci

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self.kunci in self.hal.ada else 0

    def evaluate(self, js):
        return f"<button>{self.kunci}</button>"

    def click(self, **kw):
        self.hal.aksi.append(("klik", self.kunci))
        if self.kunci == L["sso_pegawai_btn"]:
            self.hal.url = "https://sso.bps.go.id/auth/realms/pegawai-bps/protocol/openid-connect/auth"
            self.hal.ada = {SEL["sso_pegawai_username"], SEL["sso_pegawai_password"], SEL["sso_pegawai_masuk"]}
        elif self.kunci == L["sso_eksternal_btn"]:
            self.hal.url = "https://sso.bps.go.id/auth/realms/eksternal/protocol/openid-connect/auth"
            self.hal.ada = {"email", "password", "tombol"}
        elif self.kunci in (SEL["sso_pegawai_masuk"], "tombol"):
            self.hal.url = "https://fasih-web.bps.go.id/"

    def fill(self, nilai, **kw):
        self.hal.aksi.append(("isi", self.kunci, nilai))

    def wait_for(self, **kw):
        raise TimeoutError("bukan dasbor")


class Halaman:
    def __init__(self):
        self.url = "https://fasih-web.bps.go.id/login"
        self.ada = {L["sso_pegawai_btn"], L["sso_eksternal_btn"]}
        self.aksi = []

    def get_by_text(self, teks, exact=False):
        return Lok(self, teks if isinstance(teks, str) else "dasbor")

    def get_by_label(self, pola):
        return Lok(self, "email" if "email" in pola.pattern else "password")

    def get_by_role(self, peran, name=None):
        return Lok(self, "tombol")

    def locator(self, css):
        return Lok(self, css)

    def wait_for_load_state(self, *a, **kw):
        pass

    def wait_for_timeout(self, ms):
        pass


def sesi_tiruan():
    s = object.__new__(fw.FasihWebSession)
    s.page = Halaman()
    s.akun_api = {}
    s._log = lambda m: None
    s._shot = lambda n: None
    s._buka_halaman_login = lambda: None
    s._visible = lambda loc: loc
    s.verifikasi_akun = lambda email: "COCOK"
    return s


print("\n== login lewat SSO Pegawai ==")
lama = (fw.FIXED_PASSWORD, fw.PASSWORD_PEGAWAI)
fw.FIXED_PASSWORD, fw.PASSWORD_PEGAWAI = "sandi-mitra", "sandi-pegawai"
s = sesi_tiruan()
s.login("pegawai.contoh@bps.go.id")
cek("tombol SSO Pegawai yang diklik", s.page.aksi[0], ("klik", L["sso_pegawai_btn"]))
cek("form Keycloak pegawai diisi username & password pegawai", s.page.aksi[1:4],
    [("isi", SEL["sso_pegawai_username"], "pegawai.contoh@bps.go.id"),
     ("isi", SEL["sso_pegawai_password"], "sandi-pegawai"),
     ("klik", SEL["sso_pegawai_masuk"])])
cek("password mitra tidak pernah diketik", any("sandi-mitra" in str(a) for a in s.page.aksi), False)

print("\n== login lewat SSO Eksternal (perilaku lama) ==")
s = sesi_tiruan()
s.login("ppl.contoh@gmail.com")
cek("tombol SSO Eksternal yang diklik", s.page.aksi[0], ("klik", L["sso_eksternal_btn"]))
cek("password mitra dipakai", ("isi", "password", "sandi-mitra") in s.page.aksi, True)
cek("password pegawai tidak pernah diketik", any("sandi-pegawai" in str(a) for a in s.page.aksi), False)

print("\n== password pegawai kosong -> berhenti SEBELUM membuka halaman ==")
fw.PASSWORD_PEGAWAI = ""
s = sesi_tiruan()
try:
    s.login("pegawai.contoh@bps.go.id")
    cek("SystemExit", False, True)
except SystemExit as e:
    cek("SystemExit dgn pesan pegawai", "PEGAWAI" in str(e), True)
cek("tidak ada klik", s.page.aksi, [])
fw.FIXED_PASSWORD, fw.PASSWORD_PEGAWAI = lama

print("\n== verifikasi akun pegawai lewat username ==")
s = object.__new__(fw.FasihWebSession)
s._log = lambda m: None
s.identitas_akun = lambda: {"email": "pegawai.contoh@bps.go.id", "fullname": "Pegawai Contoh"}
cek("username = bagian depan email", fw.FasihWebSession.verifikasi_akun(s, "pegawai.contoh"), "COCOK")
cek("email penuh", fw.FasihWebSession.verifikasi_akun(s, "Pegawai.Contoh@bps.go.id"), "COCOK")
cek("username lain", fw.FasihWebSession.verifikasi_akun(s, "pegawai.lain"), "BEDA")
cek("email domain lain dgn awalan sama", fw.FasihWebSession.verifikasi_akun(s, "pegawai.contoh@gmail.com"), "BEDA")

print(f"\n{'SEMUA LULUS' if not gagal else f'{gagal} GAGAL'}")
sys.exit(1 if gagal else 0)
