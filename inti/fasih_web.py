"""
fasih_web.py — Wrapper Playwright untuk semua interaksi dgn fasih-web.bps.go.id
(sistem tujuan input). Mengimplementasikan SEMUA temuan di
catatan-usaha-pecahan-se2026.md: retry KBLI, nuance Nomor Urut Bangunan,
field kondisional (26c/rincian 20), geotagging, dsb.

Desain: setiap method sengaja DIBUNGKUS try/except yg logging jelas +
screenshot ke folder ./log_screenshots/ setiap kali sebuah langkah gagal,
supaya waktu dry-run pertama gampang didiagnosis field mana yg selector-nya
meleset (lihat config.py -> dict L) tanpa harus baca ulang seluruh kode.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout

from inti.config import (
    DEFAULT_TIMEOUT_MS, FASIH_WEB_BASE, FASIH_WEB_LOGIN_URL, FIXED_PASSWORD,
    DK, L, NAV_RETRY_ON_TRANSIENT_ERROR, SEL, SURVEY_ID, WILAYAH_BY_IDSUBSLS,
)

SCREENSHOT_DIR = Path("./log_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class FieldNotFound(RuntimeError):
    """Field/label tidak ketemu di halaman — kemungkinan besar string di
    config.py -> L perlu disesuaikan dgn label asli yg dirender browser."""


class DokumenNamaLamaAda(RuntimeError):
    """create_document() tidak menemukan dokumen bernama baru, tapi MENEMUKAN
    dokumen bernama lama (sebelum aturan penamaan diganti). Membuat dokumen
    baru di titik ini pasti menghasilkan duplikat — berhenti, cek manual."""


def nilai_sama(sekarang: str, target) -> bool:
    """Apakah isi field `sekarang` sudah sama dgn nilai yang mau diketik.
    Angka dibandingkan per digit (field mata uang tampil "15.056.000"), teks
    tanpa beda spasi & huruf besar (form meng-UPPERCASE nama)."""
    t = " ".join(str(target).split())
    s = " ".join(str(sekarang or "").split())
    if not s:
        return False
    if t.isdigit():
        return re.sub(r"\D", "", s) == t
    return s.upper() == t.upper()


@dataclass
class Ringkasan:
    galat: int
    peringatan: int
    catatan: int
    kosong: int
    total_jawaban: Optional[int] = None

    @property
    def aman_utk_review(self) -> bool:
        return self.galat == 0


# JS pemeta komponen: form-engine merender tiap komponen kuesioner dengan
# id = dataKey-nya, jadi cukup enumerasi semua [id] di dalam #fasih-form utk
# dapat peta "dataKey -> jenis input + label". Jauh lebih berguna drpd HTML
# mentah waktu menyusun selector field baru.
_JS_FIELD_MAP = r"""
() => {
  const root = document.querySelector('#fasih-form');
  if (!root) return 'ERROR: #fasih-form tidak ada di DOM';
  const skip = /^(radix-|collapsible-|kobalte-|fasih-form-nav-)/;
  const out = [];
  root.querySelectorAll('[id]').forEach(el => {
    const id = el.id;
    if (!id || skip.test(id)) return;
    const ctrls = [...el.querySelectorAll('input,textarea,select,[role="radio"],[role="checkbox"],[role="option"]')]
      .map(c => c.tagName.toLowerCase() + (c.type ? ':' + c.type : ''));
    const uniq = [...new Set(ctrls)].join(',') || '-';
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160);
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    const tampak = r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    const hidden = tampak ? '' : ' [HIDDEN]';
    out.push(id + '\t' + uniq + hidden + '\t' + txt);
  });
  return out.join('\n');
}
"""


# Ambil teks dialog/modal teratas yang benar-benar terlihat.
# CATATAN: jangan menilai visibilitas dgn offsetParent — selalu null untuk
# elemen position:fixed, dan modal fasih-web semuanya fixed.
_JS_DIALOG_TEXT = r"""
() => {
  const terlihat = d => {
    const r = d.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const dlgs = [...document.querySelectorAll('[role="dialog"]')].filter(terlihat);
  const d = dlgs[dlgs.length - 1];
  if (!d) return '';
  const NL = String.fromCharCode(10);
  return (d.innerText || '').split(NL).map(x => x.trim()).filter(Boolean).join(' | ');
}
"""

class FasihWebSession:
    def __init__(self, page: Page, step_log: Optional[list] = None, dump_dom: bool = False):
        self.page = page
        self.page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        self.step_log = step_log if step_log is not None else []
        self.dump_dom = dump_dom
        # Diisi create_document kalau aplikasi langsung membuka dokumen baru.
        self.dokumen_url_terakhir = ""
        self.dokumen_dibuat = False
        self.nama_di_modal = False
        # Identitas akun hasil sadapan respons API (lihat _pasang_penyadap_akun).
        self.akun_api: dict = {}
        # Sadapan respons datatable list PENDATAAN (totalHit + kapan diterima).
        self.total_list: Optional[int] = None
        self.total_list_waktu = 0.0
        # Jumlah dokumen di list tepat sebelum create_document mengklik "+Dokumen Baru".
        self.jumlah_dokumen_awal: Optional[int] = None
        # False kalau daftar_dokumen_api() tidak berhasil membaca list yang konsisten.
        self.daftar_dokumen_lengkap = True
        self._pasang_penyadap_akun()

    # ------------------------------------------------------------------
    # Util dasar
    # ------------------------------------------------------------------
    def _pasang_penyadap_akun(self):
        """Rekam identitas akun dari respons API yang MEMANG sudah dipanggil
        fasih-web sendiri saat login:
            GET /api/survey/api/v1/users/check-user
            -> {"data":{"fullname":..., "username":..., "email":...}}
        Dipakai supaya verifikasi akun tidak perlu request tambahan dan tidak
        bergantung pada DOM header yang bisa berubah."""
        def _on_response(resp):
            try:
                if "datatable-all-user-survey-periode" in resp.url:
                    # List PENDATAAN selesai dimuat -> totalHit = jumlah dokumen.
                    self.total_list = int((resp.json() or {}).get("totalHit"))
                    self.total_list_waktu = time.time()
                    return
                if "check-user" not in resp.url and "users/me" not in resp.url:
                    return
                data = (resp.json() or {}).get("data") or {}
                if not isinstance(data, dict):
                    return
                info = {
                    "email": str(data.get("email") or data.get("username") or "").strip().lower(),
                    "fullname": str(data.get("fullname") or "").strip(),
                }
                if info["email"] or info["fullname"]:
                    self.akun_api = info
            except Exception:
                pass
        try:
            self.page.on("response", _on_response)
        except Exception:
            pass

    def _log(self, msg: str):
        self.step_log.append(msg)
        # Jam di setiap baris log: dasar mengukur langkah mana yang lambat.
        print(f"[fasih-web {time.strftime('%H:%M:%S')}] {msg}")

    def _shot(self, name: str):
        try:
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:80]
            self.page.screenshot(path=str(SCREENSHOT_DIR / f"{int(time.time())}_{safe}.png"))
        except Exception:
            pass

    def dump(self, name: str, paksa: bool = False):
        """Simpan peta komponen (dataKey -> input + label) + HTML section
        aktif ke ./log_screenshots/. Normalnya hanya jalan kalau dump_dom=True
        (flag --dump-dom di main.py). Dipakai utk memetakan dataKey section
        yang belum pernah kita lihat, tanpa perlu copy-paste DOM manual.

        `paksa=True` mengabaikan flag itu — dipakai di jalur yang JELAS butuh
        bukti DOM utk didiagnosa (mis. GALAT>0 yang tidak bisa di-auto-fix),
        supaya tidak perlu mengulang satu run live cuma buat melihat DOM-nya.

        Ingat: form-engine cuma merender section AKTIF, jadi satu dump = satu
        section. Panggil ulang tiap kali pindah section."""
        if not (self.dump_dom or paksa):
            return
        try:
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:60]
            stamp = f"{int(time.time())}_{safe}"
            field_map = self.page.evaluate(_JS_FIELD_MAP)
            header = f"# section aktif : {self.active_section_title()}\n# url          : {self.page.url}\n# kolom        : dataKey \\t jenis-input \\t teks\n\n"
            (SCREENSHOT_DIR / f"{stamp}.map.tsv").write_text(header + field_map, encoding="utf-8")
            root = self.page.locator(SEL["form_root"])
            if root.count() > 0:
                (SCREENSHOT_DIR / f"{stamp}.html").write_text(root.first.inner_html(), encoding="utf-8")
            self._log(f"📄 DOM di-dump: log_screenshots/{stamp}.map.tsv (+ .html)")
        except Exception as e:
            self._log(f"⚠️ dump DOM gagal (tidak fatal): {e}")

    def debug_dialog(self, nama: str):
        """Log isi dialog/modal teratas: teks tombol, input + placeholder,
        dan judulnya. Dipakai saat memetakan alur modal yang belum diketahui
        (mis. Pilih Lokasi) tanpa harus membuka file dump."""
        try:
            info = self.page.evaluate(r"""() => {
                const dlgs = [...document.querySelectorAll('[role="dialog"],[data-dialog],[class*="fixed"],[data-state="open"]')]
                    .filter(d => {
                        const r = d.getBoundingClientRect(), cs = getComputedStyle(d);
                        return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'
                               && cs.display !== 'none' && d.innerText.trim();
                    });
                const d = dlgs[dlgs.length - 1];
                if (!d) return null;
                return {
                  teks: d.innerText.replace(/\s+/g, ' ').trim().slice(0, 300),
                  tombol: [...d.querySelectorAll('button')].filter(b => b.getBoundingClientRect().width > 0)
                            .map(b => (b.innerText || b.getAttribute('aria-label') || '').trim()).filter(Boolean),
                  input: [...d.querySelectorAll('input,textarea')].filter(i => i.getBoundingClientRect().width > 0)
                            .map(i => ({ph: i.placeholder || '', id: i.id || '', val: i.value || ''})),
                };
            }""")
            self._log(f"🔍 dialog[{nama}]: {info}")
        except Exception as e:
            self._log(f"⚠️ debug_dialog gagal: {e}")

    def klik_tahan(self, locator, nama: str = "elemen"):
        """Klik yang tahan elemen 'tidak stabil'. Sebagian kontrol fasih-web
        (mis. pemicu combobox) beranimasi/re-render terus sehingga cek
        actionability Playwright tidak pernah puas. Urutan: klik normal ->
        force (lewati cek) -> klik langsung via DOM."""
        try:
            locator.click(timeout=6_000)
            return
        except Exception:
            pass
        try:
            locator.click(force=True, timeout=6_000)
            self._log(f"  (klik force) {nama}")
            return
        except Exception:
            pass
        try:
            locator.evaluate("el => el.click()")
            self._log(f"  (klik DOM) {nama}")
        except Exception as e:
            self._fail(f"klik_tahan: gagal mengklik {nama}: {e}")

    def datakeys_in_dom(self) -> list:
        """Daftar dataKey komponen yang ADA di DOM saat ini (section aktif),
        dgn penanda [HIDDEN]. Dipakai untuk melaporkan field bersyarat yang
        baru muncul tanpa harus membuka file dump."""
        try:
            return self.page.evaluate("""() => {
                const root = document.querySelector('#fasih-form');
                if (!root) return [];
                const skip = /^(radix-|collapsible-|kobalte-|fasih-form-nav-|textfield-|radiogroup-|checkbox-|select-)/;
                return [...root.querySelectorAll('[id]')]
                    .map(el => el.id + (el.offsetParent === null ? ' [HIDDEN]' : ''))
                    .filter(id => !skip.test(id));
            }""")
        except Exception:
            return []

    def _visible(self, locator):
        """Aplikasi fasih-web merender sebagian teks DUA KALI (varian mobile
        & desktop), salah satunya di-hide via CSS. Akibatnya `.first` bisa
        nyangkut di elemen hidden lalu `wait_for()` (default state=visible)
        timeout padahal versi visible-nya ada di DOM. Selalu saring dulu."""
        return locator.locator("visible=true")

    def _fail(self, msg: str):
        # Sebut section aktif: penyebab paling sering "field tidak ketemu"
        # adalah kita mengisi saat berada di section yang salah (form-engine
        # cuma merender section aktif).
        try:
            msg = f"{msg} [section aktif: '{self.active_section_title()}']"
        except Exception:
            pass
        self._log(f"❌ {msg}")
        self._shot(msg)
        self.dump(f"FAIL_{msg}")
        raise FieldNotFound(msg)

    def save(self):
        """Klik ikon disket floating toolbar. TIDAK dianggap jaring
        pengaman mutlak (lihat Temuan Kritis) — cuma dilakukan berkala
        sesuai kebiasaan yg terbukti aman selama sesi manual."""
        try:
            # Terverifikasi dari dump DOM asli: tombol save di floating
            # toolbar kanan berisi <svg class="tabler-icon tabler-icon-device-floppy">
            # dan TIDAK punya teks/aria-label sama sekali — jadi ikonnya yang
            # jadi pegangan. Toolbar dirender 2x (varian mobile & desktop),
            # yang mobile di-hide -> wajib saring visible.
            btn = self._visible(self.page.locator(SEL["toolbar_save"]))
            if btn.count() > 0:
                btn.first.click()
                self._log("Save diklik (ikon disket floating toolbar).")
                self.page.wait_for_timeout(1500)
                return
            # Fallback lama, kalau suatu saat mereka menambahkan label teks.
            for sel in ['button[aria-label*="impan" i]', 'button[title*="impan" i]']:
                loc = self._visible(self.page.locator(sel))
                if loc.count() > 0:
                    loc.first.click()
                    self._log("Save diklik (aria-label/title match).")
                    self.page.wait_for_timeout(1500)
                    return
            self._log("⚠️ Tombol save tidak ketemu — SKIP (form autosave saat pindah field biasanya tetap jalan).")
        except Exception as e:
            self._log(f"⚠️ save() gagal tanpa fatal: {e}")

    # ------------------------------------------------------------------
    # Login & navigasi dokumen
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Pergantian akun
    # ------------------------------------------------------------------
    # ⚠️ Sesi SSO BPS hidup di DOMAIN TERPISAH dari fasih-web. Akibatnya
    # "logout" dari fasih-web saja TIDAK memutus sesi: klik "SSO Eksternal"
    # berikutnya langsung masuk lagi sbg akun LAMA tanpa menanyakan
    # kredensial sama sekali. Ini persis gejala yang dilaporkan user
    # 2026-09-06 ("logout malah masuk ke akun lama lagi saat login").
    #
    # Bahayanya bukan sekadar merepotkan: tanpa verifikasi, skrip akan
    # mengisi & (di mode --submit) MENGIRIM dokumen atas nama PPL yang
    # salah, tanpa satu pun tanda peringatan. Karena itu login() sekarang
    # WAJIB memverifikasi akun dan menolak lanjut kalau tidak cocok.

    def identitas_akun(self, tunggu_ms: int = 6_000) -> dict:
        """{'email':..., 'fullname':...} akun yang SEDANG login, atau {} .

        TIGA sumber, berurut — dulu cuma dua dan ternyata sering gagal
        keduanya (run user 2026-09-07: "Identitas akun tidak terbaca"),
        karena respons API bisa BELUM tiba saat verifikasi dipanggil dan
        halaman masih "Memuat Halaman..." sehingga menu avatar belum ada:
          1. respons API /users/check-user yang disadap saat login —
             DITUNGGU sampai `tunggu_ms`, bukan dicek sekali lalu menyerah;
          2. panggil endpoint itu langsung dari halaman (GET, pakai cookie
             sesi yang sama) kalau sadapannya tidak kunjung datang;
          3. menu avatar di pojok kanan atas (nama + email).

        ⚠️ Sapaan dasbor ("Selamat sore, Komang") SENGAJA TIDAK dipakai:
        di batch Buleleng ini KEDUA BELAS PPL bernama depan "Komang", jadi
        sapaan itu cocok utk semua orang dan sama sekali bukan pengaman.
        """
        # 1. tunggu sadapan
        batas = time.time() + tunggu_ms / 1000.0
        while time.time() < batas:
            if self.akun_api.get("email"):
                return dict(self.akun_api)
            self.page.wait_for_timeout(400)

        # 2. panggil endpoint sendiri. GET saja — endpoint lain tidak ditebak,
        #    dan POST ke endpoint yang belum dipahami bisa punya efek samping.
        try:
            hasil = self.page.evaluate("""async () => {
              try {
                const r = await fetch('/api/survey/api/v1/users/check-user',
                                      {credentials: 'include'});
                if (!r.ok) return null;
                const j = await r.json();
                return (j && j.data) ? j.data : null;
              } catch (e) { return null; }
            }""")
            if isinstance(hasil, dict):
                info = {
                    "email": str(hasil.get("email") or hasil.get("username") or "").strip().lower(),
                    "fullname": str(hasil.get("fullname") or "").strip(),
                }
                if info["email"]:
                    self.akun_api = info
                    return dict(info)
        except Exception as e:
            self._log(f"  (fetch check-user gagal: {str(e)[:80]})")

        # 3. menu avatar
        try:
            self.page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        try:
            pemicu = self._visible(self.page.locator('[aria-haspopup="menu"]'))
            if pemicu.count() == 0:
                pemicu = self._visible(self.page.get_by_role(
                    "button", name=re.compile(r"^\s*[A-Za-z]{1,2}\s*$")))
            if pemicu.count() == 0:
                return {}
            pemicu.last.click(timeout=6_000)
            self.page.wait_for_timeout(1200)
            teks = self.page.evaluate(
                "() => [...document.querySelectorAll('[role=menu],[data-state=open]')]"
                ".map(e => e.innerText || '').join(' ')"
            ) or ""
            self.page.keyboard.press("Escape")
            m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", teks)
            return {"email": m.group(0).lower() if m else "",
                    "fullname": " ".join(teks.split())[:80]}
        except Exception as e:
            self._log(f"⚠️ baca menu akun gagal: {e}")
            return {}

    def verifikasi_akun(self, email_diharapkan: str) -> str:
        """-> 'COCOK' | 'BEDA' | 'TIDAK_DIKETAHUI'.

        'TIDAK_DIKETAHUI' tidak dianggap gagal (kalau API belum sempat
        terpanggil), tapi di-log keras supaya kelihatan kalau pengaman ini
        sedang tidak bekerja."""
        info = self.identitas_akun()
        target = (email_diharapkan or "").strip().lower()
        aktif = (info.get("email") or "").strip().lower()
        if not aktif:
            self._log("⚠️ Identitas akun tidak terbaca — verifikasi akun TIDAK bisa dilakukan.")
            return "TIDAK_DIKETAHUI"
        if aktif == target:
            self._log(f"✅ Akun terverifikasi: {aktif} ({info.get('fullname', '')})")
            return "COCOK"
        self._log(f"❌ Akun AKTIF '{aktif}' ({info.get('fullname', '')}) != diminta '{target}'")
        return "BEDA"

    def logout(self, bersihkan_sesi: bool = True):
        """Keluar dari akun sekarang & putus sesi SSO-nya.

        ⚠️ Sesi login BUKAN milik fasih-web, melainkan Keycloak di
        sso.bps.go.id (cookie KEYCLOAK_IDENTITY / KEYCLOAK_SESSION /
        AUTH_SESSION_ID pada domain .sso.bps.go.id — diverifikasi
        2026-09-06). Itu sebabnya "logout" dari fasih-web saja tidak cukup:
        klik "SSO Eksternal" berikutnya langsung masuk lagi sbg akun LAMA
        tanpa menanyakan kredensial. Yang benar-benar memutus sesi adalah
        clear_cookies() level CONTEXT, karena itu menghapus cookie
        sso.bps.go.id juga.

        Di browser biasa (Chrome milik user) padanannya: logout dari
        sso.bps.go.id, atau hapus cookie situs itu — bukan cuma fasih-web.
        """
        self._log("Logout & bersihkan sesi ...")
        try:
            self.page.goto(FASIH_WEB_BASE, wait_until="domcontentloaded")
            self.page.wait_for_timeout(1200)
        except Exception:
            pass

        # Menu "Keluar" hanya ada DI DALAM menu avatar — harus dibuka dulu.
        # Versi sebelumnya mencari teks "Keluar" di halaman & selalu gagal.
        try:
            pemicu = self._visible(self.page.locator('[aria-haspopup="menu"]'))
            if pemicu.count() == 0:
                pemicu = self._visible(self.page.get_by_role(
                    "button", name=re.compile(r"^\s*[A-Za-z]{1,2}\s*$")))
            if pemicu.count() > 0:
                pemicu.last.click(timeout=6_000)
                self.page.wait_for_timeout(1000)
                keluar = self._visible(self.page.get_by_text(
                    re.compile(r"^\s*(keluar|logout|sign out)\s*$", re.I)))
                if keluar.count() > 0:
                    keluar.last.click(timeout=6_000)
                    self.page.wait_for_timeout(2500)
                    self._log("Tombol 'Keluar' di menu akun diklik.")
                else:
                    self._log("Item 'Keluar' tidak ada di menu akun.")
                    self.page.keyboard.press("Escape")
            else:
                self._log("Tombol menu akun tidak ketemu — lanjut bersihkan sesi.")
        except Exception as e:
            self._log(f"Logout lewat UI gagal ({str(e)[:90]}) — lanjut bersihkan sesi.")

        self.akun_api = {}
        if not bersihkan_sesi:
            return
        try:
            self.page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} }")
        except Exception:
            pass
        try:
            self.page.context.clear_cookies()
            self._log("Cookie SEMUA domain (termasuk sso.bps.go.id) + storage dibersihkan.")
        except Exception as e:
            self._log(f"⚠️ clear_cookies gagal: {e}")

    def login(self, email: str, password: str = FIXED_PASSWORD, _percobaan: int = 1):
        """Login sbg `email`, lalu VERIFIKASI bahwa yang benar-benar masuk
        memang akun itu (lihat catatan panjang di atas logout()).

        Kalau sesi SSO lama ternyata masih hidup sbg akun lain, sesi itu
        diputus otomatis lalu login diulang sekali dgn kredensial penuh.
        Kalau tetap tidak cocok -> RuntimeError (BUKAN lanjut diam-diam).
        """
        self._log(f"Login sbg {email} (percobaan {_percobaan}) ...")
        self.page.goto(FASIH_WEB_LOGIN_URL, wait_until="domcontentloaded")
        sso_loc = self.page.get_by_text(L["sso_eksternal_btn"], exact=False)
        try:
            count = sso_loc.count()
            self._log(f"Locator '{L['sso_eksternal_btn']}' ketemu {count} elemen.")
            if count:
                try:
                    html_snip = sso_loc.first.evaluate("el => el.outerHTML")
                    self._log(f"outerHTML elemen pertama: {html_snip[:300]}")
                except Exception as e:
                    self._log(f"(gagal ambil outerHTML: {e})")
            sso_loc.first.click(timeout=10_000)
        except Exception:
            self._shot(f"login_klik_sso_eksternal_gagal_{email}")
            raise
        # Klik SSO Eksternal kadang LANGSUNG menyelesaikan login (sesi/token
        # sudah valid) tanpa form email/password terpisah sama sekali —
        # cek dulu apakah sudah di dashboard sebelum coba isi form kredensial,
        # supaya tidak menunggu 15 detik penuh menunggu field yg tidak ada.
        try:
            self.page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        already_in = False
        try:
            self.page.get_by_text(re.compile("dasbor", re.I)).first.wait_for(state="visible", timeout=5_000)
            already_in = True
            self._log("Sudah di Dasbor setelah klik SSO Eksternal — form email/password dilewati.")
        except Exception:
            already_in = False

        # ⚠️ Cabang inilah sumber bug "logout malah masuk ke akun lama":
        # sesi SSO yang masih hidup membuat klik SSO Eksternal langsung
        # tembus ke Dasbor, dan dulu skrip menyimpulkan "sesi sudah valid"
        # TANPA mengecek itu akun siapa. Sekarang dicek dan diputus.
        if already_in and _percobaan == 1:
            if self.verifikasi_akun(email) == "BEDA":
                self._log("Sesi SSO lama milik akun LAIN — diputus, lalu login ulang dgn kredensial penuh.")
                self.logout()
                return self.login(email, password, _percobaan=2)

        if not already_in:
            # Form SSO eksternal — coba label resmi dulu, fallback ke
            # placeholder/type kalau form-nya tidak pakai <label> semantik
            # (umum di form SSO eksternal/pihak ketiga).
            try:
                email_loc = self.page.get_by_label(re.compile("email", re.I))
                if email_loc.count() == 0:
                    email_loc = self.page.locator(
                        'input[type="email"], input[name*="email" i], input[placeholder*="email" i]'
                    )
                email_loc.first.fill(email, timeout=10_000)

                pass_loc = self.page.get_by_label(re.compile("password|kata sandi", re.I))
                if pass_loc.count() == 0:
                    pass_loc = self.page.locator(
                        'input[type="password"], input[name*="password" i], input[placeholder*="sandi" i]'
                    )
                pass_loc.first.fill(password, timeout=10_000)

                # Anchor (^...$) SENGAJA dipakai supaya "Log In"/"Login" tombol
                # utama tidak nyasar cocok ke "Login dengan Google" (secondary,
                # sering nonaktif) yg juga mengandung substring "login" — lihat
                # screenshot EKSTERNAL BPS SSO: tombol utama teksnya "Log In"
                # (ada spasi), bukan "Login" satu kata.
                self.page.get_by_role(
                    "button", name=re.compile(r"^\s*(masuk|log\s*in|sign\s*in)\s*$", re.I)
                # no_wait_after: klik ini memicu navigasi SSO yang kadang
                # lambat; menunggunya DI DALAM click() bikin timeout palsu
                # padahal login-nya sebenarnya jalan. Hasilnya diverifikasi
                # terpisah di bawah.
                ).first.click(timeout=15_000, no_wait_after=True)
            except Exception:
                self._shot(f"login_isi_form_sso_gagal_{email}")
                raise
        try:
            self.page.wait_for_load_state("networkidle", timeout=45_000)
        except Exception:
            self._log("⚠️ networkidle tidak tercapai — lanjut verifikasi via URL/halaman.")
        # Verifikasi nyata: sudah keluar dari halaman login SSO?
        # SSO BPS kadang butuh puluhan detik utk menyelesaikan redirect —
        # jangan simpulkan gagal terlalu cepat.
        for _ in range(20):
            u = self.page.url.lower()
            if "/login" not in u and "auth" not in u and "fasih-web.bps.go.id" in u:
                break
            self.page.wait_for_timeout(2_000)
        else:
            self._shot(f"login_masih_di_halaman_login_{email}")
            raise RuntimeError(f"Login gagal: masih di halaman login ({self.page.url})")
        # Verifikasi terakhir: URL sudah benar TIDAK menjamin akunnya benar.
        status = self.verifikasi_akun(email)
        if status == "BEDA":
            self._shot(f"login_akun_salah_{email}")
            aktif = self.identitas_akun()
            raise RuntimeError(
                f"AKUN SALAH: diminta login sbg '{email}' tapi yang aktif '{aktif.get('email')}' "
                f"({aktif.get('fullname')}). "
                "Skrip berhenti — mengisi dokumen atas nama PPL yang salah jauh lebih mahal "
                "drpd satu run yang gagal. Jalankan ulang; sesi sudah dibersihkan."
            )
        if status == "TIDAK_DIKETAHUI":
            self._log(
                "⚠️ Akun tidak bisa diverifikasi otomatis. Kalau ini run pergantian akun, "
                "PASTIKAN MANUAL di layar bahwa yang login memang PPL yang benar sebelum lanjut."
            )
        self._log(f"Login selesai — URL sekarang: {self.page.url}")

    def goto_pendataan(self, assignment_id: str):
        url = f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/{assignment_id}"
        self.page.goto(url, wait_until="domcontentloaded")

    def _pilih_wilayah_cascade(self, idsubsls: str):
        """Modal 'Buat Dokumen Baru' punya 6 dropdown cascading Wilayah
        Responden (PROVINSI->SUBSLS) yg WAJIB dipilih manual — tombol
        'Buat Dokumen' tetap disabled sampai semua terisi (dikonfirmasi
        dari screenshot nyata, BUKAN auto-prefill dari idsubsls seperti
        dugaan awal).

        Tiap opsi dropdown dirender sbg teks "[KODE] NAMA" (dikonfirmasi
        screenshot, mis. "[51] BALI", "[08] BULELENG") — dicocokkan lewat
        KODE yg dipecah LANGSUNG dari idsubsls (2+2+3+3+4+2 = 16 digit:
        provinsi+kabkota+kecamatan+desa+sls+subsls), BUKAN lewat nama
        (SLS & SUBSLS sering bernama tampilan sama — lihat catatan di
        config.py -> WILAYAH_BY_IDSUBSLS, yg di sini cuma dipakai utk log
        informatif, bukan dasar pencocokan)."""
        digits = idsubsls.strip()
        if len(digits) != 16 or not digits.isdigit():
            self._fail(f"idsubsls '{idsubsls}' bukan 16 digit angka — tidak bisa dipecah jadi kode wilayah PROVINSI..SUBSLS.")

        steps = [
            ("Pilih PROVINSI", digits[0:2]),
            ("Pilih KABUPATEN/KOTA", digits[2:4]),
            ("Pilih KECAMATAN", digits[4:7]),
            ("Pilih DESA", digits[7:10]),
            ("Pilih SLS", digits[10:14]),
            ("Pilih SUBSLS", digits[14:16]),
        ]
        for level, (placeholder, kode) in enumerate(steps, start=1):
            # PENTING: field ini <input placeholder="Pilih PROVINSI" ...>, BUKAN
            # teks biasa — dikonfirmasi dari outerHTML asli (DevTools). get_by_text()
            # TIDAK PERNAH bisa nemu placeholder attribute, makanya versi
            # sebelumnya selalu timeout. get_by_placeholder() yg benar.
            # Run 2026-09-14: selama "Memuat data wilayah..." placeholder-nya
            # masih generik "Pilih Wilayah Level N" & popover sudah terbuka
            # sendiri -> tunggu lebih lama & terima kedua placeholder.
            trigger = self.page.get_by_placeholder(placeholder).or_(
                self.page.get_by_placeholder(f"Pilih Wilayah Level {level}")).first
            trigger.wait_for(state="visible", timeout=30_000)

            # Opsi baru muncul setelah dropdown sebelumnya dipilih (fetch API
            # cascading) — tunggu SEBELUM mencari, bukan langsung query. Opsi
            # ini BENAR teks biasa: <div role="option"><span>[51] BALI</span></div>.
            option = self.page.get_by_text(re.compile(rf"^\[{re.escape(kode)}\]"), exact=False)
            ada_opsi = False
            for percobaan in range(2):
                # Selalu klik pemicu DULU (opsi popover level sebelumnya bisa
                # masih terlihat & berkode sama, mis. kec [010] vs desa [010]).
                # Kalau popover sudah terbuka sendiri, klik ini MENUTUPNYA —
                # karena itu percobaan kedua mengklik lagi, bukan langsung
                # menyimpulkan opsi tidak ada (itu menghentikan seluruh batch).
                trigger.click(timeout=8_000)
                try:
                    option.first.wait_for(state="visible", timeout=20_000)
                    ada_opsi = True
                    break
                except Exception:
                    self._log(f"⚠️ Dropdown '{placeholder}': opsi '[{kode}]' belum tampil (percobaan {percobaan + 1}/2).")
            if not ada_opsi:
                self._fail(f"Dropdown '{placeholder}': tidak ada opsi dgn kode '[{kode}]' (idsubsls={idsubsls}).")
            cnt = option.count()
            if cnt > 1:
                self._log(f"⚠️ Dropdown '{placeholder}': {cnt} opsi dgn kode '[{kode}]' — pakai yg pertama.")
            try:
                html_snip = option.first.evaluate("el => el.outerHTML")
                self._log(f"Opsi '[{kode}]' outerHTML: {html_snip[:200]}")
            except Exception as e:
                self._log(f"(gagal ambil outerHTML opsi '[{kode}]': {e})")

            try:
                option.first.click(timeout=5_000)
            except Exception as e:
                self._log(f"Klik normal opsi '[{kode}]' gagal ({type(e).__name__}) -> coba force click.")
                option.first.click(timeout=5_000, force=True)

            # Verifikasi via VALUE input trigger-nya (bukan placeholder — itu
            # atribut statis yg tidak pernah "hilang" dari DOM).
            try:
                val = trigger.input_value(timeout=3_000)
                if not val:
                    self._log(f"⚠️ Input '{placeholder}' masih kosong setelah klik opsi '[{kode}]' — kemungkinan belum ke-set.")
                else:
                    self._log(f"Input '{placeholder}' -> '{val}'")
            except Exception:
                pass
            self.page.wait_for_timeout(400)  # beri waktu dropdown berikutnya ke-populate

        wilayah_nama = WILAYAH_BY_IDSUBSLS.get(idsubsls)
        self._log(f"Wilayah Responden dipilih via kode idsubsls={idsubsls}" + (f" ({wilayah_nama})" if wilayah_nama else " (nama referensi tidak ada di WILAYAH_BY_IDSUBSLS, tapi kode tetap dipilih)."))

    def create_document(self, assignment_id: str, idsubsls: str, nama_usaha: str,
                        nama_lama: str = "") -> bool:
        """Klik '+Dokumen Baru', pilih 6 dropdown Wilayah Responden, isi
        nama usaha, klik 'Buat Dokumen'. Return True kalau toast 'berhasil
        dibuat' terdeteksi (atau dokumen dgn nama sama sudah ada -> di-skip).

        Cek dulu apakah dokumen dgn nama sama SUDAH ADA di list sebelum bikin
        baru — hapus dokumen di fasih-web soft-delete & ribet di level admin
        pusat, jadi lebih aman hindari duplikat drpd bersih-bersih belakangan.

        `nama_lama`: nama dokumen menurut aturan penamaan SEBELUMNYA (alur
        Agenda: nama mentah sheet, sebelum format "<nama> (<pemilik>)").
        Kalau nama baru tidak ada tapi nama lama ada -> DokumenNamaLamaAda,
        TIDAK membuat dokumen.

        `self.dokumen_dibuat` = True HANYA kalau dokumen benar-benar baru
        dibuat di panggilan ini (bukan ditemukan di list) — termasuk jalur
        toast yang tidak mengisi `dokumen_url_terakhir`."""
        self.dokumen_dibuat = False
        self.nama_di_modal = False
        self.jumlah_dokumen_awal = None
        t0 = time.time()
        self.goto_pendataan(assignment_id)
        self._reload_list()
        # ⚠️ JANGAN pakai `.count() > 0` di sini. count() adalah snapshot dan
        # TIDAK menunggu — pada run 2026-09-03 pengecekan berjalan saat list
        # masih loading, hasilnya 0, dan dokumen DUPLIKAT terbuat. Hapus
        # dokumen di fasih-web itu soft-delete & ribet di level admin pusat.
        #
        # Percepatan 2026-09-14: dulu menunggu buta 10 dtk + 3 dtk utk nama
        # yang (utk baris baru) memang tidak ada. Sekarang "list sudah dimuat"
        # DIBUKTIKAN dulu — respons API datatable sesudah t0 tertangkap DAN
        # (kalau totalHit > 0) baris dokumen sudah dirender — baru nama dicek
        # singkat. Tanpa bukti itu, kembali ke tunggu panjang versi lama.
        list_terbukti = False
        batas = time.time() + 30
        while time.time() < batas:
            if self.total_list is not None and self.total_list_waktu >= t0:
                break
            self.page.wait_for_timeout(300)
        if self.total_list is not None and self.total_list_waktu >= t0:
            self.jumlah_dokumen_awal = self.total_list
            if self.total_list == 0:
                list_terbukti = True
            else:
                try:
                    self._visible(self.page.locator(SEL["entry_link_href"])).first.wait_for(
                        state="visible", timeout=15_000)
                    list_terbukti = True
                except Exception:
                    pass
        if not list_terbukti:
            try:
                self.page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
        tunggu_nama, tunggu_lama = (2_500, 1_500) if list_terbukti else (10_000, 3_000)
        if self._find_row_visible(nama_usaha, timeout_ms=tunggu_nama) is not None:
            self._log(f"Dokumen '{nama_usaha}' SUDAH ADA di list -> skip create_document (hindari duplikat).")
            return True
        # Substring nama lama juga cocok dgn nama baru, tapi nama baru sudah
        # terbukti tidak ada -> yang cocok di sini adalah dokumen lain/bernama
        # lama. Keduanya alasan utk berhenti, bukan menebak.
        if (nama_lama and nama_lama.strip().upper() != nama_usaha.strip().upper()
                and self._find_row_visible(nama_lama, timeout_ms=tunggu_lama) is not None):
            self._shot(f"dokumen_nama_lama_{nama_lama}")
            raise DokumenNamaLamaAda(
                f"Dokumen '{nama_usaha}' tidak ada, tapi list memuat '{nama_lama}' (nama format lama?). "
                "Dokumen baru TIDAK dibuat supaya tidak duplikat — cek list PENDATAAN manual.")

        # Tombol '+Dokumen Baru' kadang belum dirender dalam 15 dtk kalau list
        # PENDATAAN sudah panjang (7 record gagal begini pada batch
        # 2026-09-07). Ditunggu lebih lama, lalu list dimuat ulang & dicoba
        # lagi — memuat ulang di sini aman: kita masih di HALAMAN LIST, belum
        # membuka dokumen apa pun.
        tombol_baru = self._visible(self.page.get_by_text(L["dokumen_baru_btn"], exact=False))
        for percobaan in range(1, 4):
            try:
                tombol_baru.first.click(timeout=30_000)
                break
            except Exception:
                if percobaan == 3:
                    # Tombol benar-benar tidak ada. Paling sering: wilayah/SLS
                    # tujuan belum punya assignment di fasih-web sehingga
                    # dokumen tidak bisa dibuat dari sini sama sekali.
                    # Kembalikan False (-> SKIP_DOKUMEN_BELUM_ADA di main.py)
                    # supaya audit-nya terbaca sbg "buat manual dulu", bukan
                    # TimeoutError mentah yang tidak memberi petunjuk apa pun.
                    self._shot(f"dokumen_baru_tidak_muncul_{assignment_id}")
                    self._log(
                        f"❌ Tombol '{L['dokumen_baru_btn']}' tidak ada di assignment "
                        f"{assignment_id} setelah 3 percobaan — kemungkinan besar wilayah "
                        "ini belum punya assignment. Buat dokumennya manual."
                    )
                    return False
                self._log(f"⚠️ Tombol '{L['dokumen_baru_btn']}' belum muncul "
                          f"(percobaan {percobaan}/3) — muat ulang list.")
                self._reload_list()
                try:
                    self.page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                tombol_baru = self._visible(self.page.get_by_text(L["dokumen_baru_btn"], exact=False))
        try:
            self.page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass
        try:
            self._pilih_wilayah_cascade(idsubsls)

            # Field nama di modal TIDAK SELALU ADA: di assignment akun tunggal
            # (run 2026-09-14) modal "Buat Dokumen Baru" hanya berisi Wilayah
            # Responden — nama dokumen lalu berasal dari SE2026-P. Dicari HANYA
            # di dalam dialog (versi lama mencari di seluruh halaman & sempat
            # mengisi elemen di belakang modal). Semua dropdown sudah terpilih
            # di titik ini, jadi modal sudah selesai dirender.
            # Diagnostik modal 2026-09-14: field-nya <input id="create-document-data1"
            # placeholder="Masukkan Nama Keluarga/Bangunan/Usaha..."> — tapi kadang
            # baru dirender beberapa detik setelah SUBSLS dipilih (baris 3-5 run
            # pertama tidak melihatnya), jadi ditunggu lebih lama.
            dialog = self._visible(self.page.locator('[role="dialog"]')).last
            name_loc = self._visible(self.page.locator("#create-document-data1")).or_(
                dialog.locator('input[placeholder*="nama" i], textarea[placeholder*="nama" i]')).first
            try:
                name_loc.wait_for(state="visible", timeout=8_000)
                name_loc.fill(nama_usaha, timeout=10_000)
                self.nama_di_modal = True
                self._log(f"Nama dokumen di modal = '{nama_usaha}'.")
            except Exception:
                self._log("Modal tidak punya field nama — nama dokumen diisi lewat SE2026-P.")
            tombol_buat = self._visible(self.page.get_by_role(
                "button", name=re.compile("simpan|buat|tambah", re.I)))
            self.klik_tahan(tombol_buat.first, "tombol Buat Dokumen")
        except FieldNotFound:
            raise
        except Exception:
            self._shot(f"create_document_gagal_{assignment_id}")
            raise
        # Setelah "Buat Dokumen", fasih-web biasanya LANGSUNG menavigasi ke
        # halaman entry dokumen baru ("Memuat Halaman..."), sehingga toast
        # "berhasil dibuat" gampang terlewat. Jadi terima KEDUA sinyal.
        try:
            # 45 dtk (dulu 20): baris 6 run 2026-09-14 tertahan "Memuat Halaman..."
            # lebih dari 20 dtk setelah "Buat Dokumen".
            for _ in range(45):
                if "/entry" in self.page.url:
                    self.dokumen_dibuat = True
                    self.dokumen_url_terakhir = self.page.url
                    self._log(f"Dokumen baru '{nama_usaha}' dibuat & langsung terbuka: {self.page.url}")
                    return True
                if self.page.get_by_text(re.compile("berhasil dibuat", re.I)).count() > 0:
                    break
                self.page.wait_for_timeout(1000)
            self.page.get_by_text(re.compile("berhasil dibuat", re.I)).wait_for(timeout=5000)
            self.dokumen_dibuat = True
            self._log(f"Dokumen baru '{nama_usaha}' berhasil dibuat.")
            # Run 2026-09-14 (baris 4): toast muncul DULUAN, aplikasi baru
            # menavigasi ke /entry sesudahnya. Versi lama langsung pindah ke
            # list (goto) & membatalkan navigasi itu -> dokumen tanpa nama
            # tidak bisa ditemukan lagi. Tunggu navigasinya dulu.
            for _ in range(25):
                if "/entry" in self.page.url:
                    self.dokumen_url_terakhir = self.page.url
                    self._log(f"  ... lalu terbuka: {self.page.url}")
                    return True
                self.page.wait_for_timeout(1000)
            if not self.nama_di_modal:
                # Tanpa nama & tanpa URL, dokumen ini tidak bisa dicari. JANGAN
                # ke list (bisa membatalkan navigasi yang telat); caller berhenti.
                self._log("⚠️ Dokumen terbuat tapi tidak terbuka & tidak bernama — URL tidak diketahui.")
                self._shot(f"dokumen_tanpa_url_{nama_usaha}")
                return True
            self._peringatkan_kalau_duplikat(assignment_id, nama_usaha)
            return True
        except PWTimeout:
            # PENYEBAB PALING SERING (terkonfirmasi 2026-09-03): wilayah/SLS
            # tujuan belum punya assignment sama sekali di fasih-web, jadi
            # dokumen memang tidak bisa dibuat dari sini. Buat dokumennya
            # manual dulu, lalu jalankan ulang skrip — cek duplikat akan
            # menemukannya dan skrip langsung mengisi.
            self._log(
                f"⚠️ Dokumen '{nama_usaha}' TIDAK terbuat (tidak ada toast & tidak "
                f"diarahkan ke halaman entry). Kemungkinan besar wilayah idsubsls "
                f"{idsubsls} belum punya assignment di fasih-web — buat dokumennya "
                f"manual dulu, lalu jalankan ulang skrip ini."
            )
            self.debug_dialog("modal_buat_dokumen_setelah_klik")
            self._shot(f"buat_dokumen_tanpa_toast_{nama_usaha}")
            return False

    def _peringatkan_kalau_duplikat(self, assignment_id: str, nama_usaha: str):
        """Setelah membuat dokumen, hitung ulang berapa baris di list yang
        memuat nama ini. Lebih dari satu = duplikat (perlu dibersihkan lewat
        admin). Sengaja hanya PERINGATAN, bukan exception: dokumennya sudah
        terlanjur ada, menghentikan proses tidak membatalkan apa pun."""
        try:
            self.goto_pendataan(assignment_id)
            self._reload_list()
            self.page.wait_for_load_state("networkidle", timeout=10_000)
            jml = self.page.evaluate(
                """(nama) => [...document.querySelectorAll('a[href$="/entry"]')]
                     .filter(a => {
                       const row = a.closest('tr') || a.parentElement?.parentElement;
                       return row && row.innerText.toLowerCase().includes(nama.toLowerCase());
                     }).length""",
                nama_usaha,
            )
            if jml > 1:
                self._log(
                    f"🚨 DUPLIKAT: ada {jml} dokumen bernama '{nama_usaha}' di assignment "
                    f"{assignment_id}. Hapus yang berlebih lewat admin (soft-delete)."
                )
                self._shot(f"DUPLIKAT_{nama_usaha}")
            elif jml == 1:
                self._log("Verifikasi: tepat 1 dokumen dgn nama ini di list (tidak ada duplikat).")
        except Exception as e:
            self._log(f"⚠️ Cek duplikat gagal (tidak fatal): {e}")

    def jumlah_dokumen_list(self, assignment_id: str) -> Optional[int]:
        """Total dokumen di list PENDATAAN akun ini (`totalHit` respons API
        datatable-all-user-survey-periode yang dipanggil list sendiri saat
        dimuat), atau None kalau respons tidak tertangkap. READ-ONLY.
        Dipakai membuktikan "Buat Dokumen" yang gagal memang TIDAK membuat
        dokumen sebelum diulang (dokumen tanpa nama tidak bisa dicari)."""
        try:
            with self.page.expect_response(
                    lambda r: "datatable-all-user-survey-periode" in r.url and r.request.method == "POST",
                    timeout=30_000) as info:
                self.goto_pendataan(assignment_id)
            data = info.value.json()
            n = int(data.get("totalHit"))
            self._log(f"Jumlah dokumen di list (API): {n}")
            return n
        except Exception as e:
            self._log(f"⚠️ jumlah dokumen list tidak terbaca: {str(e)[:120]}")
            return None

    def daftar_dokumen_api(self, assignment_id: str, per_halaman: int = 100) -> list[dict]:
        """SEMUA dokumen akun ini di list PENDATAAN, lewat API datatable yang
        dipanggil list sendiri (request pertamanya disadap: body DataTables +
        header x-xsrf-token), lalu diulang dgn start/length per halaman. READ-ONLY.
        Tiap item: id (segmen URL entry), data1 (nama, di-UPPERCASE form),
        assignmentStatusAlias ("DRAFT" / "SUBMITTED BY Pencacah" / ...), dateCreated,
        dateModified. Melempar RuntimeError kalau request list tidak tertangkap."""
        tangkap: dict = {}

        def _on_request(req):
            if ("datatable-all-user-survey-periode" in req.url and req.method == "POST"
                    and "body" not in tangkap):
                tangkap.update(url=req.url, body=req.post_data, headers=req.headers)

        self.page.on("request", _on_request)
        try:
            self.goto_pendataan(assignment_id)
            batas = time.time() + 45
            while "body" not in tangkap and time.time() < batas:
                self.page.wait_for_timeout(300)
        finally:
            self.page.remove_listener("request", _on_request)
        if "body" not in tangkap:
            raise RuntimeError("Request datatable list PENDATAAN tidak tertangkap dalam 45 dtk")
        body = json.loads(tangkap["body"])
        hdr = {k: v for k, v in tangkap["headers"].items()
               if k.lower() in ("content-type", "accept") or k.lower().startswith("x-")}
        # Run 2026-09-15: program lain membuat dokumen SELAMA halaman dibaca -> halaman
        # bergeser, satu dokumen terbaca 2x (bisa juga terlewat). Saring per id & cocokkan
        # dgn totalHit; tidak cocok -> baca ulang semua (maks 3x), lalu peringatkan.
        for percobaan in range(1, 4):
            per_id: dict = {}
            start, total = 0, 0
            while True:
                body["start"], body["length"] = start, per_halaman
                hasil = self.page.evaluate("""async ([url, body, hdr]) => {
                    const r = await fetch(url, {method: 'POST', credentials: 'include', headers: hdr,
                                                body: JSON.stringify(body)});
                    return {status: r.status, text: await r.text()};
                }""", [tangkap["url"], body, hdr])
                if hasil["status"] != 200:
                    raise RuntimeError(f"API list status {hasil['status']}: {hasil['text'][:200]}")
                data = json.loads(hasil["text"])
                halaman = data.get("searchData") or []
                total = int(data.get("totalHit") or 0)
                for it in halaman:
                    per_id[it.get("id")] = it
                start += per_halaman
                if not halaman or start >= total:
                    break
            self.daftar_dokumen_lengkap = len(per_id) == total
            if self.daftar_dokumen_lengkap:
                break
            self._log(f"⚠️ Daftar dokumen API: {len(per_id)} id unik != totalHit {total} "
                      f"(list berubah saat dibaca?) — baca ulang ({percobaan}/3).")
            self.page.wait_for_timeout(3_000)
        self._log(f"Daftar dokumen lewat API: {len(per_id)} dokumen"
                  + ("." if self.daftar_dokumen_lengkap else " — ⚠️ TIDAK LENGKAP/berubah saat dibaca."))
        return list(per_id.values())

    def _reload_list(self):
        """Klik 'Muat Ulang' di list PENDATAAN. List bisa stale sesaat
        setelah aksi (mis. baru create_document) — lihat aturan #4 di
        CLAUDE.md, jangan hapus langkah ini."""
        btn = self._visible(self.page.get_by_text(L["muat_ulang_btn"], exact=False))
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    def _find_row_visible(self, nama_usaha: str, timeout_ms: int = 8_000):
        """Cari baris dokumen di list PENDATAAN berdasarkan nama usaha.
        WAJIB disaring visible=true: teks yg sama dirender 2x (mobile &
        desktop) dan `.first` bisa kena versi hidden -> wait_for timeout
        selamanya padahal barisnya ada. Return locator atau None."""
        loc = self._visible(self.page.get_by_text(nama_usaha, exact=False)).first
        try:
            loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except Exception:
            return None

    def _find_row_di_semua_halaman(self, nama_usaha: str, maks_halaman: int = 10):
        """Cari baris dokumen menyusuri PAGINASI list PENDATAAN.

        List-nya berhalaman (tombol "Selanjutnya"); dokumen yang baru dibuat
        sering mendarat di halaman terakhir, jadi mencari hanya di halaman
        pertama akan menyimpulkan "tidak ada" secara keliru."""
        for halaman in range(1, maks_halaman + 1):
            row = self._find_row_visible(nama_usaha, timeout_ms=4_000)
            if row is not None:
                if halaman > 1:
                    self._log(f"  '{nama_usaha}' ketemu di halaman list ke-{halaman}.")
                return row
            lanjut = self._visible(self.page.get_by_role("button", name=re.compile("^Selanjutnya$", re.I)))
            if lanjut.count() == 0 or not lanjut.first.is_enabled():
                return None
            lanjut.first.click()
            self.page.wait_for_timeout(1200)
        return None

    def open_entry_for(self, nama_usaha: str, assignment_id: str, allow_retry_if_fresh: bool = True) -> bool:
        """Cari baris dokumen di list PENDATAAN & buka kuesionernya. Kalau
        kena 403/504 (error transien), retry HANYA berlaku aman kalau dokumen
        msh 0% progres (allow_retry_if_fresh=True dipanggil segera setelah
        create_document, BELUM ada data terisi) — lihat Temuan Kritis di
        catatan proyek. JANGAN pernah panggil dgn allow_retry_if_fresh=True
        pada dokumen yang sudah ada isinya.

        CATATAN: kotak Cari di list SENGAJA TIDAK dipakai. Placeholder-nya
        "Cari berdasarkan kode, wilayah, atau petugas..." — bukan nama
        dokumen — dan mengisinya cuma menambah kemungkinan list ter-filter
        kosong tanpa manfaat."""
        # Kalau create_document barusan sudah membuka dokumennya, tidak perlu
        # balik ke list sama sekali (dan lebih aman: tidak navigasi ulang).
        if self.dokumen_url_terakhir and "/entry" in self.page.url:
            self._log("Dokumen baru sudah terbuka langsung — lewati pencarian di list.")
            url_dokumen = self.page.url
            self.dokumen_url_terakhir = ""
            # Form-engine kadang butuh lebih dari 20 dtk utk mount saat server
            # sibuk — pada batch 2026-09-07 hampir separuh dokumen BARU gagal
            # di titik ini, dan semuanya sukses begitu dijalankan ulang. Jadi
            # ditunggu lebih lama, lalu dimuat ulang kalau perlu.
            #
            # Muat ulang di sini AMAN dan hanya di sini: cabang ini khusus
            # dokumen yang BARU SAJA dibuat create_document(), jadi dijamin
            # 0% progres — tidak ada data yang bisa hilang. Lihat aturan
            # keselamatan #2 di CLAUDE.md; jangan tiru pola ini di tempat lain.
            mount_ok = False
            for percobaan in range(1, 4):
                try:
                    self.page.locator(SEL["form_root"]).first.wait_for(
                        state="attached", timeout=30_000)
                    mount_ok = True
                    break
                except Exception:
                    if percobaan == 3 or not allow_retry_if_fresh:
                        break
                    self._log(
                        f"⚠️ form-engine belum mount (percobaan {percobaan}/3) — muat ulang "
                        "dokumen baru ini (aman: belum ada data terisi)."
                    )
                    try:
                        self.page.goto(url_dokumen, wait_until="domcontentloaded", timeout=45_000)
                        self.page.wait_for_timeout(3000)
                    except Exception as e:
                        self._log(f"  (muat ulang gagal: {str(e)[:90]})")
            if not mount_ok:
                self._fail("open_entry_for: form-engine tidak mount di dokumen yang baru dibuka")
            self._log(f"Dokumen '{nama_usaha}' terbuka: True (section aktif: {self.active_section_title()})")
            self.dump(f"entry_terbuka_{nama_usaha}")
            return True

        self.goto_pendataan(assignment_id)
        self._reload_list()

        row = self._find_row_di_semua_halaman(nama_usaha)
        if row is None:
            self._log(f"'{nama_usaha}' tidak ketemu di percobaan pertama — Muat Ulang & coba lagi.")
            self._reload_list()
            row = self._find_row_di_semua_halaman(nama_usaha)
        if row is None:
            self._fail(f"open_entry_for: baris '{nama_usaha}' tidak ketemu di list PENDATAAN assignment {assignment_id}")

        # Teks link aksi berbeda tergantung status dokumen: "Entri" (masih
        # bisa diisi) vs "Tinjau" (sudah SUBMITTED/APPROVED). Yang konsisten
        # adalah href-nya berakhiran /entry — pakai itu sbg pegangan utama,
        # naik ke ancestor TERDEKAT yg memuat link tsb (= baris dokumen ini),
        # supaya tidak salah klik link milik baris lain.
        entri_link = self._visible(row.locator(
            f'xpath=ancestor::*[.//a[substring(@href, string-length(@href) - 5) = "/entry"]][1]'
            f'//a[substring(@href, string-length(@href) - 5) = "/entry"]'
        )).first
        if entri_link.count() == 0:
            entri_link = self._visible(row.locator(
                "xpath=ancestor::*[.//a][1]//a[contains(., 'Entri') or contains(., 'Tinjau')]"
            )).first
        if entri_link.count() == 0:
            self._fail(f"open_entry_for: link 'Entri'/'Tinjau' utk baris '{nama_usaha}' tidak ketemu")
        entri_link.click()

        attempts = 0
        while allow_retry_if_fresh and attempts < NAV_RETRY_ON_TRANSIENT_ERROR:
            error_text = self.page.get_by_text(re.compile(r"\(40[0-9]\)|\(50[0-9]\)|Forbidden|Service unavailable", re.I))
            if error_text.count() == 0:
                break
            self._log(f"Error transien terdeteksi (percobaan {attempts + 1}) — dokumen msh 0% progres, aman utk retry.")
            refresh_btn = self._visible(self.page.get_by_text(L["refresh_halaman_btn"], exact=False))
            if refresh_btn.count() > 0:
                refresh_btn.first.click()
            else:
                self.goto_pendataan(assignment_id)
                self._reload_list()
                r2 = self._find_row_visible(nama_usaha)
                if r2 is not None:
                    r2.click()
            self.page.wait_for_timeout(2000)
            attempts += 1

        # Penanda paling andal bahwa kuesioner benar2 mount adalah akar
        # form-engine (#fasih-form), bukan teks "PENGANTAR" — teks itu juga
        # muncul di sidebar/header dan bisa menyesatkan.
        try:
            self.page.locator(SEL["form_root"]).first.wait_for(state="attached", timeout=20_000)
            ok = True
        except Exception:
            ok = False
        self._log(f"Dokumen '{nama_usaha}' terbuka: {ok} (section aktif: {self.active_section_title()})")
        self.dump(f"entry_terbuka_{nama_usaha}")
        return ok

    def buka_dokumen_url(self, url: str, nama_usaha: str = ""):
        """Buka dokumen lewat URL entry yang tercatat di audit (…/{id}/entry).

        Dipakai alur satu-akun: list PENDATAAN berisi ratusan dokumen &
        berhalaman, jadi mencari lewat nama tidak bisa diandalkan. Setara
        mengklik "Entri" dari list — TIDAK memuat ulang kalau form belum
        mount (dokumen ini bisa sudah berisi; aturan keselamatan #2)."""
        if "/entry" not in url:
            self._fail(f"buka_dokumen_url: '{url}' bukan URL entry dokumen")
        self._log(f"Buka dokumen '{nama_usaha}' lewat URL audit: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        try:
            self.page.locator(SEL["form_root"]).first.wait_for(state="attached", timeout=45_000)
        except Exception:
            self._fail(f"buka_dokumen_url: form-engine tidak mount di {url}")
        self.dump(f"entry_terbuka_{nama_usaha}")

    def dokumen_terkunci(self, tunggu_ms: int = 3_000) -> bool:
        """True kalau dokumen yang terbuka sudah tidak bisa diubah (SUBMITTED/
        terkunci). Wajib dipanggil saat IDENTITAS WILAYAH aktif: field
        kodepos (satu-satunya input teks yang diisi pencacah di situ) jadi
        `disabled`. Run 2026-09-14: dokumen yang dikirim manual lalu diisi
        ulang skrip berakhir TimeoutError "element is not enabled".
        Harus disabled TERUS selama `tunggu_ms` (bukan sesaat saat mount)."""
        inp = self._komponen_wajib("kodepos").first.locator("input").first
        batas = time.time() + tunggu_ms / 1000.0
        try:
            inp.wait_for(state="attached", timeout=8_000)
            while time.time() < batas:
                if not inp.is_disabled():
                    return False
                self.page.wait_for_timeout(300)
            return True
        except Exception:
            return False

    def baca_wilayah_dokumen(self, tunggu_ms: int = 8_000) -> dict:
        """Nilai rincian 1-4 & 6 BLOK I (prefilled dari wilayah dokumen) —
        HANYA membaca, tidak mengklik. Wajib dipanggil saat section IDENTITAS
        WILAYAH aktif. Nilai diisi form-engine sesaat setelah mount, jadi
        ditunggu sampai kode SLS terisi (atau batas waktu)."""
        hasil: dict = {}
        batas = time.time() + tunggu_ms / 1000.0
        while True:
            for key in ("prov", "kab", "kec", "desa", "kode_sls"):
                inp = self._komponen_wajib(key).first.locator("input").first
                try:
                    hasil[key] = (inp.input_value(timeout=2_000) or "").strip()
                except Exception:
                    hasil[key] = ""
            if hasil["kode_sls"] or time.time() >= batas:
                break
            self.page.wait_for_timeout(500)
        self._log(f"Wilayah dokumen (BLOK I): {hasil}")
        return hasil

    # ------------------------------------------------------------------
    # Navigasi antar-section kuesioner
    #
    # PENTING: form-engine fasih-web HANYA merender section yang sedang
    # aktif. Field milik section lain benar2 TIDAK ADA di DOM sampai kita
    # pindah ke sana — jadi semua fill_*() wajib dipastikan berjalan saat
    # section-nya aktif, kalau tidak pasti FieldNotFound.
    # ------------------------------------------------------------------
    def list_sections(self) -> list:
        """Daftar section yang ter-enable saat ini (dari sidebar). Section
        yang belum ter-unlock TIDAK muncul di sini."""
        items = self.page.locator(SEL["sidebar_item"])
        return [items.nth(i).get_attribute("title") or "" for i in range(items.count())]

    def active_section_title(self) -> str:
        try:
            active = self.page.locator(SEL["sidebar_item_active"])
            if active.count() > 0:
                return active.first.get_attribute("title") or "?"
        except Exception:
            pass
        return "?"

    def has_next_section(self) -> bool:
        """True kalau masih ada section berikutnya. fasih-web merender
        #fasih-form-nav-next-button HANYA kalau ada section berikutnya yang
        ter-enable; kalau tidak, yang dirender justru #fasih-form-nav-submit-button.
        Jadi ini indikator akurat, bukan tebakan."""
        return self.page.locator(SEL["nav_next"]).count() > 0

    def next_section(self) -> bool:
        """Klik 'Berikutnya'. Return False kalau sudah di section terakhir
        yang ter-enable."""
        btn = self.page.locator(SEL["nav_next"])
        if btn.count() == 0:
            self._log(f"Tidak ada section berikutnya (aktif: '{self.active_section_title()}').")
            return False
        sebelum = self.active_section_title()
        btn.first.click()
        self.page.wait_for_timeout(1200)
        sesudah = self.active_section_title()
        self._log(f"Pindah section: '{sebelum}' -> '{sesudah}'")
        self.dump(f"section_{sesudah}")
        return True

    def buka_nested(self, index: int = 0):
        """Buka detail komponen nested (mis. "Keterangan Usaha/Perusahaan"
        di BLOK II). Kartu nested dirender sbg elemen ber-atribut
        data-nested-view="true"; field di dalamnya TIDAK ada di DOM sampai
        kartu itu diklik."""
        kartu = self._visible(self.page.locator(SEL["nested_card"]))
        try:
            kartu.nth(index).wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail(f"buka_nested: kartu nested index {index} tidak ketemu")
        judul = " ".join(kartu.nth(index).inner_text().split())[:100]
        kartu.nth(index).click()
        self.page.wait_for_timeout(1500)
        self._log(f"Buka nested[{index}]: {judul} -> section aktif '{self.active_section_title()}'")
        self.dump(f"nested_{index}")

    def goto_section(self, nama: str) -> bool:
        """Pindah ke section lewat sidebar. Return False (tanpa raise) kalau
        section-nya belum ter-enable — pemanggil yang memutuskan apakah itu
        fatal, krn sebagian section memang kondisional."""
        if self.active_section_title() == nama:
            return True
        item = self.page.locator(f'div.fasih-form-sidebar > div[title="{nama}"]')
        if item.count() == 0:
            self._log(f"⚠️ Section '{nama}' belum ter-enable. Yang tersedia: {self.list_sections()}")
            return False
        # Di viewport sempit sidebar tersembunyi — buka dulu lewat hamburger.
        if self._visible(item).count() == 0:
            toggle = self._visible(self.page.locator(SEL["sidebar_toggle"]))
            if toggle.count() > 0:
                toggle.first.click()
                self.page.wait_for_timeout(600)
        self._visible(item).first.click()
        self.page.wait_for_timeout(1200)
        ok = self.active_section_title() == nama
        self._log(f"goto_section('{nama}') -> {ok}")
        self.dump(f"section_{nama}")
        return ok

    # ------------------------------------------------------------------
    # Helper generik isi field (label-based, dgn fallback)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Helper berbasis dataKey (id elemen == dataKey komponen).
    # Selalu lebih disukai daripada helper berbasis label di bawahnya:
    # tidak ikut berubah kalau teks/bahasa UI diubah, dan otomatis meng-scope
    # pencarian ke dalam satu komponen saja sehingga tidak bisa salah kena
    # field pertanyaan lain yang kebetulan labelnya mirip.
    # ------------------------------------------------------------------
    def komponen(self, datakey_or_key: str):
        """Locator satu komponen kuesioner. Menerima key di config DK
        maupun dataKey mentah. Pakai [id="..."] (bukan #id) supaya dataKey
        bernested seperti "nama_usaha#1002" tetap valid sbg selector."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        # Komponen di dalam nested diberi sufiks instance oleh form-engine
        # (mis. dataKey "nama_usaha" -> id "nama_usaha#2001"). Cocokkan
        # keduanya dalam SATU locator supaya tidak perlu count() (yg tidak
        # menunggu render).
        return self.page.locator(f'[id="{dk}"], [id^="{dk}#"]')

    def _komponen_wajib(self, datakey_or_key: str, timeout_ms: int = 10_000):
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self.komponen(dk)
        try:
            comp.first.wait_for(state="attached", timeout=timeout_ms)
        except Exception:
            self._fail(
                f"komponen dataKey '{dk}' tidak ada di DOM (section aktif: "
                f"'{self.active_section_title()}'). Ingat: form-engine cuma merender "
                f"section aktif — cek urutan goto_section()/next_section()."
            )
        return comp

    def _nilai_combobox(self, comp) -> str:
        """Teks nilai combobox yang SEDANG terpilih (value textarea/input di
        dalam komponen), "" kalau kosong/tidak terbaca. Read-only."""
        try:
            v = comp.first.evaluate(
                "el => { const f = el.querySelector('textarea, input');"
                " return f ? (f.value || '') : ''; }"
            )
        except Exception:
            v = ""
        return " ".join((v or "").split())

    def pilih_combobox_by_datakey(self, datakey_or_key: str, teks_opsi: str):
        """Pilih satu opsi pada komponen combobox (pola berulang di fasih-web:
        KBLI, Nama Pemberi Informasi, Daftar Usaha Non Prelist).

        Combobox ini berbasis <textarea> dan HARUS diklik dulu supaya popover
        daftar opsinya terbuka — mengetik tanpa membuka popover tidak
        memunculkan opsi apa pun. Opsi dirender sbg [role="option"]."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)
        pemicu = self._visible(comp.locator("textarea, input, button")).first
        try:
            pemicu.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail(f"pilih_combobox: pemicu di '{dk}' tidak ketemu")
        sekarang = self._nilai_combobox(comp)
        if teks_opsi.strip().lower() in sekarang.lower():
            # Klik ulang opsi yang sudah terpilih = melepasnya (toggle).
            self._log(f"  [{dk}] sudah '{sekarang}' — tidak diklik ulang.")
            return
        self.klik_tahan(pemicu, f"combobox {dk}")
        self.page.wait_for_timeout(900)

        opsi = self._visible(self.page.get_by_role("option")).filter(has_text=teks_opsi)
        try:
            opsi.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            tersedia = self._visible(self.page.get_by_role("option"))
            contoh = [" ".join((tersedia.nth(i).inner_text() or "").split())[:40]
                      for i in range(min(tersedia.count(), 5))]
            self._fail(f"pilih_combobox: opsi '{teks_opsi}' tidak ada di '{dk}'. Contoh opsi: {contoh}")
        terpilih = " ".join((opsi.first.inner_text() or "").split())
        opsi.first.click()
        self.page.wait_for_timeout(1000)

        # Verifikasi baca-balik + RETRY. Klik pada daftar opsi tidak selalu
        # berarti nilainya tersimpan: "Nama Pemberi Informasi" pernah lolos
        # di log tapi tetap muncul sbg GALAT "Wajib diisi" di ringkasan —
        # 2x di record 2513 (2026-09-03) & 1x di record 2521 (2026-09-06),
        # dan hilang sendiri saat run diulang. Dulu ini cuma di-log sbg
        # peringatan lalu dibiarkan; sekarang diulang sampai nilainya
        # benar-benar terbaca di komponen.
        def _terbaca() -> str:
            try:
                v = comp.first.evaluate(
                    "el => { const f = el.querySelector('textarea, input');"
                    " return f ? (f.value || '') : (el.innerText || ''); }"
                )
            except Exception:
                v = ""
            return " ".join((v or "").split())

        nilai = _terbaca()
        for percobaan in range(2, 5):
            if teks_opsi.strip().lower() in nilai.lower():
                break
            self._log(f"  ⚠️ [{dk}] '{terpilih[:40]}' belum nyantol (terbaca '{nilai[:50]}') — ulangi ke-{percobaan}")
            try:
                self.klik_tahan(pemicu, f"combobox {dk} (ulang {percobaan})")
                self.page.wait_for_timeout(1200)
                ulang = self._visible(self.page.get_by_role("option")).filter(has_text=teks_opsi)
                ulang.first.wait_for(state="visible", timeout=8_000)
                ulang.first.click()
                self.page.wait_for_timeout(1500)
            except Exception as e:
                self._log(f"  ⚠️ [{dk}] percobaan {percobaan} gagal: {str(e)[:120]}")
            nilai = _terbaca()

        if teks_opsi.strip().lower() not in nilai.lower():
            self._fail(
                f"pilih_combobox: [{dk}] tetap kosong setelah 4 percobaan "
                f"(terbaca '{nilai[:60]}'). Field ini wajib — jangan dilanjutkan diam-diam."
            )
        self._log(f"  [{dk}] -> {nilai[:60]}")

    def pilih_combobox_pertama_yang_cocok(self, datakey_or_key: str, kandidat) -> str:
        """Buka combobox SEKALI, baca SELURUH opsinya, lalu pilih kandidat
        pertama yang cocok (substring, case-insensitive).

        Dipakai utk combobox yang teks opsinya belum pernah terbaca dari DOM
        (popover baru dirender saat diklik), mis. "Pilih UMKM dalam satu SLS
        yang sama". Kalau tidak ada kandidat yang cocok, SELURUH opsi dicetak
        lalu FieldNotFound — jadi run berikutnya tinggal memasukkan teks yang
        benar ke config, bukan menebak-nebak.
        """
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)
        sekarang = self._nilai_combobox(comp)
        for teks in kandidat:
            if teks.strip() and teks.strip().lower() in sekarang.lower():
                # Mengklik opsi yang SUDAH terpilih justru MELEPASNYA (toggle) —
                # run 2026-09-14: pengisian ulang mengosongkan "Pilih UMKM dalam
                # satu SLS yang sama" -> GALAT "Wajib diisi".
                self._log(f"  [{dk}] sudah '{sekarang}' — tidak diklik ulang.")
                return sekarang
        pemicu = self._visible(comp.locator("textarea, input, button")).first
        self.klik_tahan(pemicu, f"combobox {dk}")
        self.page.wait_for_timeout(1000)

        opsi = self._visible(self.page.get_by_role("option"))
        try:
            opsi.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            self._fail(f"pilih_combobox_pertama_yang_cocok: '{dk}' tidak memunculkan opsi apa pun")
        semua = [" ".join((opsi.nth(i).inner_text() or "").split()) for i in range(opsi.count())]
        self._log(f"  [{dk}] {len(semua)} opsi tersedia: {semua[:12]}")

        for teks in kandidat:
            for i, label in enumerate(semua):
                if teks.strip().lower() in label.lower():
                    opsi.nth(i).click()
                    self.page.wait_for_timeout(900)
                    self._log(f"  [{dk}] -> '{label}' (cocok kandidat '{teks}')")
                    return label
        self.page.keyboard.press("Escape")
        self._fail(
            f"pilih_combobox_pertama_yang_cocok: tidak ada kandidat {list(kandidat)} di '{dk}'. "
            f"Opsi yang benar-benar tersedia: {semua}"
        )

    def centang_by_datakey(self, datakey_or_key: str):
        """Centang checkbox di dalam komponen ber-dataKey tsb (idempoten)."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)
        box = comp.locator("input[type=checkbox]").first
        try:
            box.wait_for(state="attached", timeout=10_000)
        except Exception:
            self._fail(f"centang_by_datakey: checkbox di '{dk}' tidak ketemu")
        if box.is_checked():
            self._log(f"  [{dk}] sudah tercentang.")
            return
        # Kobalte merender <input type=checkbox> tersembunyi + div kontrol
        # ber-id "<...>-control". Klik ke input tersembunyi tidak berefek —
        # yang harus diklik adalah div kontrolnya.
        target = self._visible(comp.locator('[id$="-control"], label')).first
        self.klik_tahan(target, f"checkbox {dk}")
        self.page.wait_for_timeout(500)
        if not box.is_checked():
            self._fail(f"centang_by_datakey: '{dk}' tetap tidak tercentang setelah diklik")
        self._log(f"  [{dk}] dicentang.")

    def centang_teks_dalam_komponen(self, datakey_or_key: str, teks_opsi: str):
        """Centang SATU opsi checkbox (dari beberapa) di dalam komponen
        multi-pilih ber-dataKey tsb — beda dari centang_by_datakey() yang
        cuma menangani komponen ber-checkbox TUNGGAL. Dipakai utk 31e
        'Bulan beroperasi' (satu checkbox per bulan dalam satu komponen).
        Idempoten: tidak diklik ulang kalau sudah tercentang."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)
        opsi = self._visible(comp.get_by_text(teks_opsi, exact=True)).last
        try:
            opsi.wait_for(state="visible", timeout=8_000)
        except Exception:
            self._fail(f"centang_teks_dalam_komponen: opsi '{teks_opsi}' tidak ada di '{dk}'")
        # Cari <input type=checkbox> terdekat (leluhur bersama dgn label ini)
        # utk cek status sebelum & sesudah klik.
        grup = opsi.locator("xpath=ancestor::*[@role='group'][1]")
        box = grup.locator("input[type=checkbox]").first
        if box.count() and box.is_checked():
            self._log(f"  [{dk}] '{teks_opsi}' sudah tercentang.")
            return
        self.klik_tahan(opsi, f"checkbox '{teks_opsi}' di {dk}")
        self.page.wait_for_timeout(400)
        if box.count() and not box.is_checked():
            self._fail(f"centang_teks_dalam_komponen: '{teks_opsi}' tetap tidak tercentang di '{dk}'")
        self._log(f"  [{dk}] '{teks_opsi}' dicentang.")

    def datakey_by_label(self, pola: str) -> str:
        """Cari dataKey komponen yang teksnya cocok `pola` (regex, case-insensitive).

        Dipakai untuk field BERSYARAT yang dataKey-nya belum sempat
        terpetakan lewat --dump-dom (mis. rincian 19, yang tidak dirender
        untuk kategori KBLI tertentu). Dipilih komponen dgn teks TERPENDEK
        yang cocok, supaya yang kena komponennya sendiri — bukan container
        induk yang kebetulan memuat teks itu juga.

        Return "" kalau tidak ketemu."""
        try:
            return self.page.evaluate(
                """(pola) => {
                    const root = document.querySelector('#fasih-form');
                    if (!root) return '';
                    const buang = /^(radix-|collapsible-|kobalte-|fasih-form-nav-|textfield-|radiogroup-|checkbox-|select-|combobox-|numberfield-)/;
                    const re = new RegExp(pola, 'i');
                    let terbaik = '', panjang = Infinity;
                    root.querySelectorAll('[id]').forEach(el => {
                        if (!el.id || buang.test(el.id)) return;
                        const t = (el.innerText || '').trim();
                        if (t && re.test(t) && t.length < panjang) {
                            panjang = t.length; terbaik = el.id;
                        }
                    });
                    return terbaik;
                }""",
                pola,
            ) or ""
        except Exception:
            return ""

    def isi_bersyarat_by_label(self, pola: str, nilai: str, nama: str = "") -> bool:
        """Isi field bersyarat yang ditemukan lewat label. Otomatis memilih
        cara isi: radio kalau komponennya punya <input type=radio>, selain
        itu diketik. Return False (tanpa raise) kalau field-nya tidak ada —
        memang banyak rincian yang hanya muncul utk kategori KBLI tertentu."""
        dk = self.datakey_by_label(pola)
        if not dk:
            self._log(f"  {nama or pola}: tidak dirender di form ini — dilewati.")
            return False
        punya_radio = self.komponen(dk).locator("input[type=radio]").count() > 0
        if punya_radio:
            self.select_radio_by_datakey(dk, nilai)
        else:
            self.fill_by_datakey(dk, nilai)
        return True

    def komponen_ada(self, datakey_or_key: str, timeout_ms: int = 6_000) -> bool:
        """True kalau komponen ber-dataKey tsb ADA di DOM, dgn MENUNGGU.

        Jangan pakai `.count() > 0` untuk ini: field bersyarat dirender
        beberapa ratus milidetik setelah pemicunya dijawab, dan count()
        tidak menunggu — itu yang bikin 10c/13c/20c terlewat dan muncul
        sbg GALAT "Wajib diisi" di ringkasan."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        try:
            self.komponen(dk).first.wait_for(state="attached", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def fill_by_datakey(self, datakey_or_key: str, value: str):
        """Isi input/textarea di dalam komponen ber-dataKey tsb."""
        if value is None or str(value) == "":
            return
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)
        inp = self._visible(comp.locator("input, textarea")).first
        try:
            # wait_for, BUKAN count(): count() snapshot & tidak menunggu render.
            inp.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail(f"fill_by_datakey: tidak ada input/textarea visible di dalam '{dk}'")
        # Pengisian ulang: nilai yang SUDAH sama tidak diketik lagi (sama dgn
        # penjagaan radio). Run 2026-09-14: mengisi ulang dokumen yang sudah
        # lengkap memunculkan GALAT "Pilih UMKM dalam satu SLS yang sama" —
        # tersangka utamanya fill() ulang nama_usaha_bang (induk nested BLOK II).
        try:
            sekarang = inp.input_value(timeout=2_000) or ""
        except Exception:
            sekarang = ""
        if nilai_sama(sekarang, value):
            self._log(f"  [{dk}] sudah = {value} (tidak diketik ulang)")
            return
        inp.fill(str(value))
        self._log(f"  [{dk}] = {value}")

    def _radio_tercentang(self, comp, option_text: str) -> bool:
        """True kalau radio yang SEDANG tercentang di komponen `comp` sudah
        berlabel `option_text`. Dipakai supaya pengisian ulang tidak
        mengklik ulang jawaban yang sudah benar (lihat catatan di
        select_radio_by_datakey)."""
        try:
            label = comp.first.evaluate(r"""el => {
                const c = el.querySelector('input[type=radio]:checked');
                if (!c) return null;
                const bersih = t => (t || '').replace(/\s+/g, ' ').trim();
                if (c.labels && c.labels.length) return bersih(c.labels[0].innerText);
                const w = c.closest('[id*="-item-"]');
                if (w) {
                    const l = w.querySelector('label');
                    if (l) return bersih(l.innerText);
                }
                return null;
            }""")
        except Exception:
            return False
        return bool(label) and option_text.strip().lower() in label.strip().lower()

    def select_radio_by_datakey(self, datakey_or_key: str, option_text: str):
        """Pilih opsi radio di dalam komponen ber-dataKey tsb. Klik diarahkan
        ke <label>-nya (input radio aslinya sering di-hide & digantikan
        indikator kustom, jadi klik ke input bisa gagal)."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk)

        # Kalau opsi yang diminta SUDAH tercentang, jangan diklik lagi.
        # Mengklik ulang radio memicu form-engine mengevaluasi ulang
        # kondisinya, dan itu me-RESET jawaban komponen turunannya: pada
        # pengisian ulang record 2523 (2026-09-06), klik ulang
        # `keberadaan_usaha` menghapus jawaban `pilih_umkm_sls` yang sudah
        # benar di run sebelumnya — padahal komponennya sudah tidak dirender
        # lagi, jadi tidak bisa diisi ulang & langsung jadi GALAT.
        if self._radio_tercentang(comp, option_text):
            self._log(f"  [{dk}] sudah '{option_text}' — tidak diklik ulang.")
            return

        opt = self._visible(comp.get_by_text(option_text, exact=False)).last
        try:
            opt.wait_for(state="visible", timeout=10_000)
        except Exception:
            tersedia = " | ".join(comp.first.inner_text().split())[:200]
            self._fail(
                f"select_radio_by_datakey: opsi '{option_text}' tidak ada di '{dk}'. "
                f"Isi komponen: {tersedia}"
            )
        opt.click()
        # Verifikasi: radio yang benar2 tercentang harus cocok dgn yg diminta.
        # Tanpa ini, klik yang meleset (mis. kena label pertanyaan lain) lewat
        # tanpa jejak — dan itu berarti data sensus yang salah.
        self.page.wait_for_timeout(400)
        try:
            terpilih = comp.first.evaluate(r"""el => {
                const c = el.querySelector('input[type=radio]:checked');
                if (!c) return null;
                const bersih = t => (t || '').replace(/\s+/g, ' ').trim();
                // Label bisa datang dari beberapa tempat tergantung struktur.
                if (c.labels && c.labels.length) return bersih(c.labels[0].innerText);
                const w = c.closest('[id*="-item-"]');
                if (w) {
                    const l = w.querySelector('label');
                    if (l) return bersih(l.innerText);
                    if (bersih(w.innerText)) return bersih(w.innerText);
                }
                if (c.id) {
                    const l = document.querySelector('label[for="' + c.id + '"]');
                    if (l) return bersih(l.innerText);
                }
                return '(nilai=' + (c.value || '?') + ')';
            }""")
        except Exception:
            terpilih = None
        if terpilih is None:
            self._fail(f"select_radio_by_datakey: tidak ada opsi tercentang di '{dk}' setelah klik '{option_text}'")
        if option_text.strip().lower() in terpilih.strip().lower():
            self._log(f"  [{dk}] -> {terpilih}")
        else:
            # Label tidak terbaca utuh bukan berarti klik salah — tapi WAJIB
            # kelihatan di log supaya bisa diverifikasi manual.
            self._log(
                f"  ⚠️ [{dk}] diminta '{option_text}', label tercentang terbaca '{terpilih}' "
                f"— tidak cocok persis, VERIFIKASI di ringkasan pra-Kirim."
            )

    def fill_text(self, label_key_or_text: str, value: str, exact: bool = False):
        label = L.get(label_key_or_text, label_key_or_text)
        if not value:
            return
        try:
            field = self.page.get_by_label(re.compile(re.escape(label), re.I), exact=exact).first
            field.fill(str(value))
            return
        except Exception:
            pass
        # fallback: cari label sbg teks, lalu input terdekat
        try:
            lbl = self.page.get_by_text(re.compile(re.escape(label), re.I)).first
            inp = lbl.locator("xpath=following::input[1] | following::textarea[1]").first
            inp.fill(str(value))
        except Exception:
            self._fail(f"fill_text: field '{label}' tidak ketemu (nilai='{value}')")

    def select_radio(self, group_label_hint: str, option_text: str):
        """Pilih radio button. group_label_hint dipakai utk mempersempit
        area pencarian (hindari salah pilih radio dari pertanyaan lain yg
        kebetulan opsinya mirip, mis. banyak '2. Tidak' di halaman yg sama)."""
        try:
            group_hint = L.get(group_label_hint, group_label_hint)
            container = self.page.get_by_text(re.compile(re.escape(group_hint), re.I)).first.locator(
                "xpath=ancestor::*[self::div or self::fieldset][1]"
            )
            opt = container.get_by_text(option_text, exact=False).first
            opt.click()
            self._log(f"  (label) {group_label_hint} -> {option_text}")
        except Exception:
            try:
                # ⛔ Fallback "klik teks pertama di seluruh halaman" DIHAPUS.
                # Opsi radio di BLOK II hampir semuanya berteks sama
                # ("1. Ya"/"2. Tidak"), jadi fallback ini pasti mengklik
                # pertanyaan yang salah dan menulis jawaban sensus keliru
                # tanpa jejak. Lebih baik berhenti & minta dataKey.
                raise RuntimeError(
                    f"select_radio: grup '{group_label_hint}' tidak ketemu. Fallback global "
                    f"sengaja dinonaktifkan (berisiko menjawab pertanyaan lain). "
                    f"Petakan dataKey-nya di config.py -> DK lalu pakai select_radio_by_datakey()."
                )
            except Exception:
                self._fail(f"select_radio: opsi '{option_text}' (grup≈'{group_label_hint}') tidak ketemu")

    def click_button(self, label_key_or_text: str):
        label = L.get(label_key_or_text, label_key_or_text)
        try:
            self.page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first.click()
        except Exception:
            try:
                self.page.get_by_text(label, exact=False).first.click()
            except Exception:
                self._fail(f"click_button: '{label}' tidak ketemu")

    def confirm_dialog(self, yes_text: str = "Ya"):
        try:
            self.page.get_by_role("button", name=re.compile(rf"^{re.escape(yes_text)}$", re.I)).click(timeout=5000)
        except Exception:
            self.page.get_by_text(yes_text, exact=True).first.click()

    # ------------------------------------------------------------------
    # PENGANTAR
    # ------------------------------------------------------------------
    def isi_waktu_by_datakey(self, datakey_or_key: str):
        """Isi satu komponen waktu ("Ambil Waktu" + konfirmasi "Ya").

        Komponen waktu punya dua tampilan (terverifikasi dari dump):
          KOSONG -> teks "Waktu belum diambil" + tombol "Ambil Waktu"
          TERISI -> hanya tanggal/jam; tombolnya bisa hilang sama sekali
                    (mis. #mulai tidak bisa diubah lagi setelah diisi).
        Karena itu deteksi "sudah terisi" lewat HILANGNYA empty-state,
        bukan lewat keberadaan tombol."""
        dk = DK.get(datakey_or_key, datakey_or_key)
        comp = self._komponen_wajib(dk, timeout_ms=15_000)
        teks = " ".join(comp.first.inner_text().split())
        if L["waktu_belum_diambil"] not in teks:
            self._log(f"  [{dk}] sudah terisi ({teks[:60]}) — dilewati.")
            return
        btn = self._visible(comp.get_by_role(
            "button", name=re.compile(re.escape(L["ambil_waktu_btn"]), re.I)))
        try:
            btn.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail(f"isi_waktu: tombol '{L['ambil_waktu_btn']}' tidak muncul di [{dk}] (isi: {teks})")
        btn.first.click(timeout=8_000)
        self.confirm_dialog(L["konfirmasi_ambil_lokasi_ya"])
        kosong = comp.get_by_text(L["waktu_belum_diambil"], exact=False)
        try:
            kosong.first.wait_for(state="hidden", timeout=10_000)
        except Exception:
            self._fail(f"isi_waktu: [{dk}] masih kosong setelah klik + konfirmasi")
        self._log(f"  [{dk}] terisi: {' '.join(comp.first.inner_text().split())[:60]}")

    def fill_pengantar(self):
        """Halaman pertama setelah Entri. Ada DUA field waktu yang wajib
        diisi, dan yang kedua BERSYARAT:

          #mulai        -> "Waktu Mulai"
          #kunjungan_1  -> "Waktu Kunjungan I"  (BARU dirender setelah
                           #mulai terisi — sebelum itu tidak ada di DOM
                           sama sekali)

        Jangan tertukar dengan field milik PENGAWAS (#kunjungan_pml,
        #geotag_pml, #catatan_pml): itu ada di template tapi di-display:none
        oleh CSS yang disuntikkan #pml_hidden, dan bukan urusan pencacah.

        Section berikutnya (IDENTITAS WILAYAH) baru ter-enable setelah
        PENGANTAR beres."""
        self._log("Isi PENGANTAR (Waktu Mulai + Waktu Kunjungan I) ...")
        # Urutan penting: #kunjungan_1 BARU dirender setelah #mulai terisi.
        for key in ("waktu_mulai", "waktu_kunjungan_1"):
            self.isi_waktu_by_datakey(key)

        if not self.has_next_section():
            self._log(
                "⚠️ PENGANTAR beres tapi tombol 'Berikutnya' tetap tidak ada "
                f"— section ter-enable: {self.list_sections()}. Cek screenshot/dump."
            )
            self._shot("pengantar_tanpa_next_button")
        self.dump("pengantar_selesai")

    # ------------------------------------------------------------------
    # SE2026-P
    # ------------------------------------------------------------------
    def fill_se2026_p(self, nama_usaha: str, nama_jalan: str, blok_nomor: str = "-"):
        """Section "SE2026 - P" (judul persis pakai spasi) — BLOK V.
        KETERANGAN KELUARGA DAN USAHA. dataKey diverifikasi dari --dump-dom.

        Field yang ada saat section dibuka:
          #jenis_prelist          readonly/prefilled
          #is_new                 "Tambah: pilih jenis assignment yang ditambahkan"
                                  -> Keluarga | Bangunan Lainnya (...)
          #pilih_umkm             Daftar Usaha Non Prelist (textarea/combobox)
          #nama_usaha_bang        Nama Bangunan/ Usaha/ Perusahaan
          #ada_bang_usaha         Keberadaan Bangunan Lainnya/ Usaha — WAJIB
          #jumlah_usaha_ditemukan auto-terisi

        ⚠️ Field alamat (nama jalan, blok/nomor) TIDAK ada di DOM sampai
        #ada_bang_usaha dijawab — pertanyaan bersyarat. Karena itu urutannya
        tidak boleh dibalik.
        """
        self._log("Isi SE2026-P ...")
        self.select_radio_by_datakey("is_new", L["opsi_bangunan_lainnya"])
        self.fill_by_datakey("nama_usaha_bang", nama_usaha)
        # #pilih_umkm (Daftar Usaha Non Prelist) SENGAJA dibiarkan kosong —
        # aturan #10 di catatan proyek.
        self.select_radio_by_datakey("ada_bang_usaha", L["opsi_baru"])

        # Menjawab keberadaan usaha memunculkan blok Alamat + geotag.
        # _komponen_wajib() di dalam fill_by_datakey sudah auto-wait, jadi
        # tidak perlu sleep tetap di sini.
        self.fill_by_datakey("jalan_domisili", nama_jalan)
        self.fill_by_datakey("nomor_domisili", blok_nomor)

        # ⚠️ #no_bang (Nomor Urut Bangunan): SENGAJA TIDAK DISENTUH SAMA
        # SEKALI — lihat aturan keselamatan #3 di CLAUDE.md. Sekali ter-klik
        # nilainya jadi literal 0 dan memicu GALAT keras yg tidak bisa
        # dikembalikan ke null. Perbaikan HANYA lewat
        # fix_nomor_urut_bangunan_if_needed(), dipanggil dari main.py kalau
        # ringkasan membuktikan GALAT-nya memang cuma field ini.
        #
        # #kode_bang dibiarkan pada default "1. Bangunan Khusus Usaha"
        # (sudah terpilih otomatis — terverifikasi dari dump).
        self.dump("se2026p_selesai")
        self._log("SE2026-P selesai (Nomor Urut Bangunan sengaja tidak disentuh).")

    def fix_nomor_urut_bangunan_if_needed(self):
        """HANYA dipanggil kalau check_ringkasan() melaporkan GALAT pada
        field 'Nomor Urut Bangunan'. Cek field readonly 'NOMOR URUT
        BANGUNAN TERBESAR' — kalau ada isi angkanya, lanjutkan +1; kalau
        kosong/tidak ada info, isi 1 (instruksi eksplisit user). Diisi via
        klik chevron ▲ (bukan keyboard) krn field spinner ini kadang
        menolak/tidak stabil dgn input keyboard langsung."""
        self._log("Fix Nomor Urut Bangunan (GALAT terdeteksi di ringkasan) ...")
        terbesar_val = ""
        try:
            terbesar_val = (self._visible(
                self.komponen("no_bangunan_terbesar").locator("input")
            ).first.input_value() or "").strip()
        except Exception:
            pass
        target = int(terbesar_val) + 1 if terbesar_val.isdigit() else 1
        self._log(f"NOMOR URUT BANGUNAN TERBESAR='{terbesar_val or '(kosong)'}' -> target Nomor Urut Bangunan={target}")

        nub = self._komponen_wajib("no_bang")
        spinner = self._visible(nub.locator("input")).first
        # Spinner punya sepasang tombol ▼▲; yang menaikkan adalah yang TERAKHIR.
        up_chevron = self._visible(nub.locator("button")).last
        try:
            current_raw = (spinner.input_value() or "0").strip()
            current = int(current_raw) if current_raw.lstrip("-").isdigit() else 0
        except Exception:
            current = 0
        clicks_needed = max(0, target - current)
        for _ in range(clicks_needed):
            up_chevron.click()
            self.page.wait_for_timeout(200)
        self._log(f"Nomor Urut Bangunan di-set ke {target} via {clicks_needed}x klik chevron (dari {current}).")

    def do_geotagging(self, latitude: str, longitude: str, akurasi_m: int = 10):
        """Isi Geotagging (#geotag) lewat modal "Pilih Lokasi".

        Alur yang TERBUKTI (dipetakan 2026-09-03):
          1. Klik "Ambil Lokasi" di #geotag -> modal peta Leaflet terbuka.
          2. Klik tombol locate di peta (title="Gunakan lokasi saat ini").
             Tombol itu memanggil navigator.geolocation.getCurrentPosition,
             yang koordinatnya SUDAH KITA KENDALIKAN lewat
             context.set_geolocation() — jadi yang masuk persis lat/long dari
             backlog, bukan lokasi komputer yang menjalankan skrip.
          3. Tombol "Gunakan Lokasi" baru menjadi enabled; klik untuk commit.

        ⚠️ JEBAKAN SELECTOR (menghabiskan banyak waktu debugging):
        `get_by_role("button", name=re.compile("Gunakan Lokasi", re.I))` juga
        cocok dengan tombol LOCATE, karena accessible name-nya berasal dari
        title="Gunakan lokasi saat ini" — dan tombol locate lebih dulu di DOM,
        jadi `.first` mengklik tombol yang salah tanpa error apa pun. WAJIB
        pakai exact=True untuk tombol commit.

        ⚠️ Mengetik langsung ke #geo-latitude/#geo-longitude TIDAK cukup:
        teks "Pin dipilih" berubah, tapi tombol commit tetap disabled.

        ⚠️ ASUMSI: `akurasi_m` (default 10 m) ditetapkan skrip, bukan hasil
        ukur — backlog tidak menyimpan akurasi GPS. Koordinatnya sendiri asli."""
        lat, lon = float(latitude), float(longitude)
        self._log(f"Geotagging: lat={lat}, long={lon}, akurasi={akurasi_m}m (akurasi = asumsi skrip)")
        try:
            ctx = self.page.context
            ctx.grant_permissions(["geolocation"], origin=FASIH_WEB_BASE)
            ctx.set_geolocation({"latitude": lat, "longitude": lon, "accuracy": akurasi_m})
        except Exception as e:
            self._fail(f"do_geotagging: gagal menyetel geolocation Playwright: {e}")

        geo = self._komponen_wajib("geotag")
        if L["lokasi_belum_diambil"] not in " ".join(geo.first.inner_text().split()):
            self._log("  [geotag] sudah terisi — dilewati.")
            return

        btn = self._visible(geo.get_by_role(
            "button", name=re.compile(re.escape(L["ambil_lokasi_btn"]), re.I)))
        try:
            btn.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail(f"do_geotagging: tombol '{L['ambil_lokasi_btn']}' tidak ada di [geotag]")
        btn.first.click()

        lat_inp = self.page.locator(SEL["geo_lat"])
        try:
            lat_inp.first.wait_for(state="visible", timeout=15_000)
        except Exception:
            self.debug_dialog("pilih_lokasi_tidak_muncul")
            self._fail("do_geotagging: modal 'Pilih Lokasi' tidak muncul")

        locate = self._visible(self.page.locator(SEL["geo_locate"]))
        try:
            locate.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            self.debug_dialog("locate_tidak_ada")
            self._fail("do_geotagging: tombol locate 'Gunakan lokasi saat ini' tidak ada di modal")
        locate.first.click()

        # exact=True — lihat JEBAKAN SELECTOR di docstring.
        gunakan = self._visible(self.page.get_by_role(
            "button", name=L["gunakan_lokasi_btn"], exact=True)).first
        try:
            gunakan.wait_for(state="visible", timeout=10_000)
            self.page.wait_for_function(
                """() => { const b = [...document.querySelectorAll('button')]
                       .find(x => (x.innerText || '').trim() === 'Gunakan Lokasi');
                     return b && !b.disabled; }""",
                timeout=15_000,
            )
        except Exception:
            self.debug_dialog("gunakan_lokasi_tetap_disabled")
            self._fail("do_geotagging: tombol 'Gunakan Lokasi' tidak pernah enabled setelah locate")

        koord = self.page.evaluate(
            """() => ({lat: (document.getElementById('geo-latitude') || {}).value,
                       lon: (document.getElementById('geo-longitude') || {}).value,
                       acc: (document.getElementById('geo-accuracy') || {}).value})"""
        )
        self._log(f"  koordinat di modal sebelum commit: {koord}")
        gunakan.click()

        try:
            self.confirm_dialog(L["konfirmasi_ambil_lokasi_ya"])
        except Exception:
            pass

        kosong = geo.get_by_text(L["lokasi_belum_diambil"], exact=False)
        try:
            kosong.first.wait_for(state="hidden", timeout=15_000)
        except Exception:
            self.debug_dialog("geotag_gagal")
            self._fail("do_geotagging: [geotag] masih kosong setelah 'Gunakan Lokasi'")
        self._log(f"  [geotag] terisi: {' '.join(geo.first.inner_text().split())[:140]}")

    # ------------------------------------------------------------------
    # IDENTITAS WILAYAH (2 field wajib yg mudah kelewat)
    # ------------------------------------------------------------------
    def fill_identitas_wilayah(self, kodepos: str):
        """BLOK I. IDENTITAS WILAYAH — section KEDUA, langsung setelah
        PENGANTAR (BUKAN setelah SE2026-P seperti dugaan awal). dataKey
        diverifikasi dari --dump-dom, lihat log_screenshots/*.map.tsv.

        Rincian 1-7 (prov, kab, kec, desa, klas_desa, kode_sls, nama_sls)
        SUDAH terisi otomatis dari wilayah dokumen — jangan disentuh.
        Yang wajib kita isi cuma dua: rincian 8 dan rincian 10.

        ⚠️ Rincian 8 dijawab "2. Tidak": usaha pecahan didaftarkan ke SLS
        yang SUDAH ADA, jadi tidak ada pemekaran/penggabungan/perubahan nama
        maupun perubahan batas SLS. Menjawab "1. Ya" akan memunculkan
        rincian 9 (pertanyaan lanjutan) yang tidak punya sumber data di
        backlog — itulah kenapa nomor 9 tidak terlihat di dump."""
        self._log("Isi BLOK I. IDENTITAS WILAYAH ...")
        self.select_radio_by_datakey("ubah_sls", L["opsi_tidak_2"])
        self.fill_by_datakey("kodepos", kodepos)
        self.dump("identitas_wilayah_selesai")

    # ------------------------------------------------------------------
    # BLOK II — KBLI Master search dgn retry logic (bug termodokumentasi)
    # ------------------------------------------------------------------
    def fill_kbli_master(self, kbli_code: str, search_phrase_fallback: str = "") -> bool:
        """Rincian 13g — pilih KBLI dari Master KBLI.

        Struktur (dipetakan 2026-09-03):
          #kbli_genai  radio 13g; pilih opsi "Pilih dari Master KBLI"
                       (opsi lain: rekomendasi GenAI).
          #kbli        MUNCUL setelah radio itu dipilih. Combobox berbasis
                       <textarea>: harus DIKLIK dulu supaya popover daftar
                       KBLI terbuka; mengetik tanpa membuka popover tidak
                       memunculkan opsi apa pun.

        Opsi dirender sbg [role="option"] dgn format "[KATEGORI][KODE]Nama…".
        WAJIB verifikasi kode ada di teks opsi sebelum diklik — bug search
        yang terdokumentasi bisa menampilkan hasil tidak terfilter."""
        self.select_radio_by_datakey("kbli_radio", L["pilih_master_kbli_radio"])
        kbli_comp = self._komponen_wajib("kbli_pilihan", timeout_ms=15_000)

        pemicu = self._visible(kbli_comp.locator("textarea, input, button")).first
        try:
            pemicu.wait_for(state="visible", timeout=10_000)
        except Exception:
            self.dump("kbli_pemicu_tidak_ada")
            self._fail("fill_kbli_master: pemicu combobox di [kbli] tidak ketemu")
        self.klik_tahan(pemicu, "pemicu combobox KBLI")
        self.page.wait_for_timeout(1000)

        # Kotak cari = <textarea> MILIK komponen #kbli itu sendiri (bukan
        # elemen terakhir di halaman — itu kena field 13h "kategori" yang
        # disabled dan bikin click menggantung).
        kotak = self._visible(kbli_comp.locator("textarea")).first

        def opsi_terlihat() -> list:
            o = self._visible(self.page.get_by_role("option"))
            return [" ".join((o.nth(i).inner_text() or "").split())[:70]
                    for i in range(min(o.count(), 6))]

        def pilih(term: str, jeda_ms: int) -> bool:
            """Ketik `term` di kotak cari lalu klik opsi yang memuat kode.
            `jeda_ms` = waktu tunggu hasil pencarian (pencarian ini jalan di
            SERVER, jadi lambatnya jaringan langsung terasa)."""
            kotak.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            self.page.wait_for_timeout(300)
            kotak.type(term, delay=40)
            self.page.wait_for_timeout(jeda_ms)
            opsi = self._visible(self.page.get_by_role("option")).filter(has_text=kbli_code)
            try:
                opsi.first.wait_for(state="visible", timeout=8_000)
            except Exception:
                return False
            teks = " ".join((opsi.first.inner_text() or "").split())
            if kbli_code not in teks:
                self._log(f"⚠️ Opsi teratas tidak memuat kode {kbli_code}: '{teks[:80]}'")
                return False
            self._log(f"  KBLI dipilih: {teks[:90]}")
            opsi.first.click()
            self.page.wait_for_timeout(1200)
            return True

        # Pencarian Master KBLI kadang gagal SEMENTARA (hasilnya belum tiba
        # saat dicek), bukan karena kodenya tidak ada: record 2526 gagal utk
        # KBLI 47192 padahal record 2513 memakai kode yang sama dgn sukses.
        # Karena itu istilah yang sama dicoba beberapa kali dgn jeda menaik
        # SEBELUM menyerah — satu record gagal berarti mengulang ~1,7 menit.
        ok = False
        for percobaan, jeda in enumerate((1800, 3000, 4500), start=1):
            ok = pilih(kbli_code, jeda)
            if ok:
                break
            self._log(f"⚠️ KBLI '{kbli_code}' belum ketemu (percobaan {percobaan}, jeda {jeda}ms).")
        if not ok and search_phrase_fallback:
            self._log(f"⚠️ Coba frasa deskriptif '{search_phrase_fallback}'.")
            ok = pilih(search_phrase_fallback, 3000)
        if not ok:
            self.dump("kbli_gagal", paksa=True)
            self._fail(
                f"fill_kbli_master: KBLI {kbli_code} tidak ketemu di Master KBLI setelah "
                f"beberapa percobaan. Opsi yang terlihat saat gagal: {opsi_terlihat()}. "
                "Verifikasi kode di backlog, atau beri search_phrase_fallback yang deskriptif."
            )

        # 13h Kategori Lapangan Usaha terisi OTOMATIS dari KBLI yang dipilih.
        # Itu bukti terkuat bahwa pilihannya benar-benar tersimpan — sekaligus
        # penentu pemetaan rincian 26 (lihat catatan proyek).
        try:
            kat = self._visible(self.komponen("kategori_lapangan_usaha").locator("input")).first
            kat.wait_for(state="visible", timeout=8_000)
            nilai = (kat.input_value() or "").strip()
            self._log(f"  [kategori] 13h terisi otomatis: '{nilai}'")
        except Exception:
            self._log("⚠️ 13h Kategori Lapangan Usaha tidak terbaca — verifikasi manual.")
        return True

    def check_ringkasan(self) -> Ringkasan:
        """Buka dialog ringkasan pra-Kirim & baca 4 hitungan.

        ⚠️ Label kartu di-UPPERCASE lewat CSS (`tw:uppercase`), jadi teks
        DOM-nya sebenarnya "Galat"/"Peringatan"/"Catatan"/"Kosong".
        `get_by_text("GALAT", exact=True)` TIDAK akan pernah cocok — itu
        sebabnya versi lama selalu mengembalikan -1. Di sini kartunya
        di-parse langsung dari DOM (label + angka ada di dalam satu tombol).

        Dialog ini TIDAK mengirim apa pun — cuma ringkasan. Klik "Kirim" di
        dalam dialog inilah yang irreversible, dan itu ada di submit_final()."""
        tombol = self._visible(self.page.locator(SEL["nav_submit"]))
        if tombol.count() == 0:
            tombol = self._visible(self.page.get_by_role(
                "button", name=L["kirim_btn"], exact=True))
        try:
            tombol.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            self._fail("check_ringkasan: tombol 'Kirim' tidak ketemu")
        self.klik_tahan(tombol.first, "tombol Kirim (buka ringkasan)")
        self.page.wait_for_timeout(2500)

        data = self.page.evaluate(r"""() => {
            const hasil = {};
            const pola = /^(Galat|Peringatan|Catatan|Kosong)\s+(\d+)/i;
            document.querySelectorAll('button').forEach(b => {
                const t = (b.innerText || '').replace(/\s+/g, ' ').trim();
                const m = t.match(pola);
                if (m) hasil[m[1].toLowerCase()] = parseInt(m[2], 10);
            });
            const dlg = [...document.querySelectorAll('[role="dialog"]')].pop();
            hasil._teks = dlg ? (dlg.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) : '';
            return hasil;
        }""")

        if not all(k in data for k in ("galat", "peringatan", "catatan", "kosong")):
            self.dump("ringkasan_tidak_terbaca")
            self._fail(f"check_ringkasan: kartu ringkasan tidak terbaca. Isi dialog: {data.get('_teks', '')}")

        m = re.search(r"(\d+)\s+Jawaban", data.get("_teks", ""), re.I)
        r = Ringkasan(
            galat=data["galat"], peringatan=data["peringatan"],
            catatan=data["catatan"], kosong=data["kosong"],
            total_jawaban=int(m.group(1)) if m else None,
        )
        self._log(
            f"Ringkasan: GALAT={r.galat} PERINGATAN={r.peringatan} "
            f"CATATAN={r.catatan} KOSONG={r.kosong} JAWABAN={r.total_jawaban}"
        )
        return r

    def read_galat_detail(self) -> str:
        """Buka detail kartu GALAT & kembalikan teks daftar itemnya.

        Dipakai main.py utk memutuskan apakah auto-fix Nomor Urut Bangunan
        relevan, atau ada GALAT lain yang butuh review manual (skrip TIDAK
        boleh menebak fix utk galat selain field itu).

        ⚠️ Label kartu di-uppercase lewat CSS — teks DOM-nya "Galat".
        Kartunya adalah <button> berisi "Galat <jumlah>"."""
        try:
            kartu = self._visible(self.page.get_by_role("button").filter(
                has_text=re.compile(r"Galat\s*\d+", re.I)))
            if kartu.count() == 0:
                self._log("⚠️ read_galat_detail: kartu 'Galat' tidak ketemu di dialog ringkasan.")
                return ""
            self.klik_tahan(kartu.first, "kartu Galat")
            self.page.wait_for_timeout(1200)
            teks = self.page.evaluate(_JS_DIALOG_TEXT)
            self._log("Detail GALAT: " + teks[:700])
            return teks
        except Exception as e:
            self._log(f"⚠️ read_galat_detail gagal: {e}")
            return ""

    def close_ringkasan_dialog(self):
        try:
            self.page.get_by_role("button", name=re.compile("batal", re.I)).click(timeout=3000)
        except Exception:
            self.page.keyboard.press("Escape")

    def submit_final(self) -> bool:
        """HANYA dipanggil setelah caller mengonfirmasi GALAT=0 DAN sudah
        dapat izin eksplisit dari user (per-batch, bukan otomatis).
        Dialog ringkasan diasumsikan SUDAH TERBUKA (dari check_ringkasan).

        Run live pertama 2026-09-14 (baris 4): versi lama `click_button()`
        mengambil tombol /Kirim/ & /Konfirmasi/ PERTAMA di seluruh halaman
        (bisa tombol di belakang modal) -> tidak ada error, tapi dokumen tetap
        DRAFT. Sekarang setiap klik dibatasi pada dialog teratas yang benar,
        teks tombol harus persis, dan sukses dinilai dari toast "berhasil
        dikirim" ATAU halaman meninggalkan /entry (redirect ke list)."""
        def dialog(pola=None):
            loc = self.page.locator('[role="dialog"], [role="alertdialog"]')
            if pola is not None:
                loc = loc.filter(has_text=pola)
            return self._visible(loc).last

        kirim = dialog().get_by_role("button", name=re.compile(r"^\s*Kirim\s*$", re.I)).first
        try:
            kirim.wait_for(state="visible", timeout=8_000)
        except Exception:
            self.debug_dialog("ringkasan_tanpa_tombol_kirim")
            self._fail("submit_final: tombol 'Kirim' di dialog ringkasan tidak ketemu")
        self.klik_tahan(kirim, "Kirim (dialog ringkasan)")

        konfirmasi = dialog(re.compile("yakin ingin mengirimkan", re.I))
        tombol = konfirmasi.get_by_role("button", name=re.compile(r"^\s*Konfirmasi\s*$", re.I)).first
        try:
            tombol.wait_for(state="visible", timeout=10_000)
        except Exception:
            self.debug_dialog("konfirmasi_kirim_tidak_muncul")
            self._fail("submit_final: dialog 'Konfirmasi Kirim' / tombol 'Konfirmasi' tidak muncul")
        self.page.wait_for_timeout(600)  # animasi buka dialog
        self._shot("submit_sebelum_konfirmasi")

        # Rekam respons non-GET & teks toast/alert selama proses kirim: baris 22
        # (2026-09-14) dua kali gagal kirim tanpa pesan yang tertangkap.
        jejak_api: list = []
        teks_toast: list = []

        def _rekam(resp):
            try:
                if resp.request.method != "GET" and "/api/" in resp.url:
                    isi = ""
                    try:
                        isi = (resp.text() or "")[:300]
                    except Exception:
                        pass
                    jejak_api.append(f"{resp.request.method} {resp.status} {resp.url.split('/api/', 1)[-1][:90]} {isi}")
            except Exception:
                pass
        self.page.on("response", _rekam)

        def _catat_toast():
            try:
                for t in self.page.evaluate(
                        "() => [...document.querySelectorAll('[data-sonner-toast],[role=status],[role=alert],"
                        "[class*=toast]')].map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean)"):
                    if t not in teks_toast:
                        teks_toast.append(t[:200])
            except Exception:
                pass

        self.klik_tahan(tombol, "Konfirmasi (dialog Konfirmasi Kirim)")
        try:
            return self._tunggu_sukses_kirim(_catat_toast, jejak_api, teks_toast)
        finally:
            try:
                self.page.remove_listener("response", _rekam)
            except Exception:
                pass

    def _tunggu_sukses_kirim(self, catat_toast, jejak_api: list, teks_toast: list) -> bool:
        for _ in range(40):
            catat_toast()
            if "/entry" not in self.page.url:
                self._log(f"Submit: halaman pindah ke {self.page.url} (redirect pasca-kirim).")
                return True
            if self._visible(self.page.get_by_text(re.compile("berhasil dikirim", re.I))).count() > 0:
                self._log("Submit: toast 'berhasil dikirim' terdeteksi.")
                # Biarkan redirect aplikasi ke list selesai dulu: goto() ke list
                # saat masih di /entry sempat membuat verifikasi tidak menemukan
                # baris sama sekali (baris 3, 2026-09-14).
                for _ in range(20):
                    if "/entry" not in self.page.url:
                        break
                    self.page.wait_for_timeout(1000)
                return True
            self.page.wait_for_timeout(1000)
        self.debug_dialog("pasca_konfirmasi_kirim")
        self._shot("submit_tanpa_tanda_sukses")
        self._log("⚠️ Tidak ada tanda sukses kirim dlm 40 dtk (toast/redirect) — cek status via list.")
        self._log(f"  toast/alert terekam: {teks_toast or '-'}")
        self._log(f"  respons API non-GET selama kirim: {jejak_api[-8:] or '-'}")
        self.submit_jejak = f"toast={teks_toast} | api={jejak_api[-8:]}"
        return False

    def verify_submitted_in_list(self, assignment_id: str, nama_usaha: str) -> bool:
        """WAJIB dipanggil setelah submit_final() — status di list bisa
        tampil stale ('DRAFT') sesaat sebelum di-refresh (temuan nyata dari
        record 3)."""
        self.goto_pendataan(assignment_id)
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        # Visible saja (teks dirender 2x) & menyusuri paginasi. Status WAJIB
        # "SUBMITTED": versi lama menerima "CLEAN", padahal dokumen yang belum
        # dikirim pun tampil "DRAFT CLEAN" (baris 4, 2026-09-14). List bisa
        # stale BEBERAPA DETIK walau sudah Muat Ulang (baris 4: DRAFT saat
        # dicek, SUBMITTED semenit kemudian). Percepatan 2026-09-14: cukup 2x
        # (dulu 4x, ±20-40 dtk/baris) — tanda sukses kirim sudah dicek di
        # submit_final; status akhir dicek massal sesudah batch.
        teks = ""
        for percobaan in range(1, 3):
            self._reload_list()
            self.page.wait_for_timeout(2_000 * percobaan)
            row = self._find_row_di_semua_halaman(nama_usaha)
            if row is None:
                continue
            try:
                teks = " ".join((row.locator("xpath=ancestor::tr[1]").first.inner_text(timeout=5_000) or "").split())
            except Exception:
                teks = ""
            if re.search(r"SUBMITTED", teks, re.I):
                self._log(f"Verifikasi status list utk '{nama_usaha}': SUBMITTED (percobaan {percobaan}).")
                return True
        self._log(f"⚠️ Verifikasi status list utk '{nama_usaha}': belum SUBMITTED setelah 2x muat ulang ({teks[:120]})")
        return False
