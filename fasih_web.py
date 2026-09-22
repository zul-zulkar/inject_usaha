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

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout

from config import (
    DEFAULT_TIMEOUT_MS, FASIH_WEB_BASE, FASIH_WEB_LOGIN_URL, FIXED_PASSWORD,
    L, NAV_RETRY_ON_TRANSIENT_ERROR, SURVEY_ID,
)

SCREENSHOT_DIR = Path("./log_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class FieldNotFound(RuntimeError):
    """Field/label tidak ketemu di halaman — kemungkinan besar string di
    config.py -> L perlu disesuaikan dgn label asli yg dirender browser."""


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


class FasihWebSession:
    def __init__(self, page: Page, step_log: Optional[list] = None):
        self.page = page
        self.page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        self.step_log = step_log if step_log is not None else []

    # ------------------------------------------------------------------
    # Util dasar
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        self.step_log.append(msg)
        print(f"[fasih-web] {msg}")

    def _shot(self, name: str):
        try:
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:80]
            self.page.screenshot(path=str(SCREENSHOT_DIR / f"{int(time.time())}_{safe}.png"))
        except Exception:
            pass

    def _fail(self, msg: str):
        self._log(f"❌ {msg}")
        self._shot(msg)
        raise FieldNotFound(msg)

    def save(self):
        """Klik ikon disket floating toolbar. TIDAK dianggap jaring
        pengaman mutlak (lihat Temuan Kritis) — cuma dilakukan berkala
        sesuai kebiasaan yg terbukti aman selama sesi manual."""
        try:
            # Ikon disket tidak selalu punya label teks — coba beberapa cara.
            btn = self.page.locator("[class*=toolbar] button, [class*=floating] button").filter(
                has=self.page.locator("svg")
            )
            # Fallback paling robust: cari tombol yg posisinya di floating
            # toolbar kanan (dari observasi manual ~x=1262,y=641 pada layar
            # 1316px) — TAPI koordinat pixel rapuh thd resolusi berbeda,
            # jadi ini betul2 fallback terakhir. Prioritaskan aria-label
            # kalau developer fasih-web memberi salah satu.
            for sel in ['button[aria-label*="impan" i]', 'button[title*="impan" i]']:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    loc.first.click()
                    self._log("Save diklik (aria-label/title match).")
                    self.page.wait_for_timeout(1500)
                    return
            self._log("⚠️ Tombol save tidak ketemu via aria-label/title — SKIP (form autosave saat pindah field biasanya tetap jalan).")
        except Exception as e:
            self._log(f"⚠️ save() gagal tanpa fatal: {e}")

    # ------------------------------------------------------------------
    # Login & navigasi dokumen
    # ------------------------------------------------------------------
    def login(self, email: str, password: str = FIXED_PASSWORD):
        self._log(f"Login sbg {email} ...")
        self.page.goto(FASIH_WEB_LOGIN_URL, wait_until="domcontentloaded")
        self.page.get_by_text(L["sso_eksternal_btn"], exact=False).click()
        # Form SSO eksternal — asumsi field email/password standar.
        self.page.get_by_label(re.compile("email", re.I)).fill(email)
        self.page.get_by_label(re.compile("password|kata sandi", re.I)).fill(password)
        self.page.get_by_role("button", name=re.compile("masuk|login|sign in", re.I)).click()
        self.page.wait_for_load_state("networkidle", timeout=20_000)
        self._log("Login selesai (asumsi sukses — verifikasi via judul halaman setelahnya).")

    def goto_pendataan(self, assignment_id: str):
        url = f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/{assignment_id}"
        self.page.goto(url, wait_until="domcontentloaded")

    def create_document(self, assignment_id: str, idsubsls: str, nama_usaha: str) -> bool:
        """Klik '+Dokumen Baru', isi nama usaha. Wilayah diasumsikan
        auto-prefill dari idsubsls (sesuai observasi manual) — kalau
        ternyata ada field wilayah manual yg wajib dipilih, tambahkan di
        sini. Return True kalau toast 'berhasil dibuat' terdeteksi."""
        self.goto_pendataan(assignment_id)
        self.page.get_by_text(L["dokumen_baru_btn"], exact=False).click()
        name_field = self.page.get_by_label(re.compile("nama", re.I)).first
        name_field.fill(nama_usaha)
        self.page.get_by_role("button", name=re.compile("simpan|buat|tambah", re.I)).click()
        try:
            self.page.get_by_text(re.compile("berhasil dibuat", re.I)).wait_for(timeout=8000)
            self._log(f"Dokumen baru '{nama_usaha}' berhasil dibuat.")
            return True
        except PWTimeout:
            self._log("⚠️ Toast 'berhasil dibuat' tidak terdeteksi dalam 8dtk — cek manual.")
            return False

    def open_entry_for(self, nama_usaha: str, assignment_id: str, allow_retry_if_fresh: bool = True) -> bool:
        """Cari baris dokumen di list PENDATAAN & klik 'Entri'. Kalau kena
        403/504 (error transien), retry HANYA berlaku aman kalau dokumen
        msh 0% progres (allow_retry_if_fresh=True dipanggil segera setelah
        create_document, BELUM ada data terisi) — lihat Temuan Kritis di
        catatan proyek. JANGAN pernah panggil dgn allow_retry_if_fresh=True
        pada dokumen yang sudah ada isinya."""
        self.goto_pendataan(assignment_id)
        search = self.page.get_by_placeholder(re.compile("cari", re.I))
        if search.count() > 0:
            search.first.fill(nama_usaha)
            self.page.wait_for_timeout(800)

        row = self.page.get_by_text(nama_usaha, exact=False).first
        row.wait_for(timeout=8000)
        entri_link = row.locator(
            "xpath=ancestor::tr[1]//a[contains(., 'Entri')] | ancestor::*[self::div][1]//a[contains(., 'Entri')]"
        ).first
        entri_link.click()

        attempts = 0
        while allow_retry_if_fresh and attempts < NAV_RETRY_ON_TRANSIENT_ERROR:
            error_text = self.page.get_by_text(re.compile(r"\(40[0-9]\)|\(50[0-9]\)|Forbidden|Service unavailable", re.I))
            if error_text.count() == 0:
                break
            self._log(f"Error transien terdeteksi (percobaan {attempts + 1}) — dokumen msh 0% progres, aman utk retry.")
            refresh_btn = self.page.get_by_text(L["refresh_halaman_btn"], exact=False)
            if refresh_btn.count() > 0:
                refresh_btn.first.click()
            else:
                self.goto_pendataan(assignment_id)
                self.page.get_by_text(nama_usaha, exact=False).first.click()
            self.page.wait_for_timeout(2000)
            attempts += 1

        ok = self.page.get_by_text(re.compile("PENGANTAR|SENSUS EKONOMI", re.I)).count() > 0
        self._log(f"Dokumen '{nama_usaha}' terbuka: {ok}")
        return ok

    # ------------------------------------------------------------------
    # Helper generik isi field (label-based, dgn fallback)
    # ------------------------------------------------------------------
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
        except Exception:
            try:
                self.page.get_by_text(option_text, exact=False).first.click()
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
    # SE2026-P
    # ------------------------------------------------------------------
    def fill_se2026_p(self, nama_usaha: str, nama_jalan: str, blok_nomor: str = "-"):
        self._log("Isi SE2026-P ...")
        self.click_button("tambah_dropdown")
        self.page.get_by_text(L["opsi_bangunan_lainnya"], exact=False).click()
        self.fill_text("nama_bangunan_usaha", nama_usaha)
        self.select_radio("keberadaan_bangunan_lainnya", L["opsi_baru"])
        # Daftar Usaha Non Prelist -> dikosongkan saja (rule #10), tidak perlu aksi.
        self.fill_text("nama_jalan", nama_jalan)
        self.fill_text("blok_nomor_rumah", blok_nomor)

        # ⚠️ Nomor Urut Bangunan: SENGAJA TIDAK DISENTUH SAMA SEKALI.
        # Jangan tambahkan .click()/.fill() apapun ke field ini di sini.
        # Kalau field ini nanti bikin GALAT (lihat check_ringkasan), fix-nya
        # ada di method fix_nomor_urut_bangunan_if_needed(), dipanggil
        # HANYA kalau ringkasan pra-Kirim melaporkan GALAT terkait field ini.

        # Kode Penggunaan Bangunan dibiarkan default "1. Bangunan Khusus Usaha".
        self._log("SE2026-P selesai (Nomor Urut Bangunan sengaja tidak disentuh).")

    def fix_nomor_urut_bangunan_if_needed(self):
        """HANYA dipanggil kalau check_ringkasan() melaporkan GALAT pada
        field 'Nomor Urut Bangunan'. Cek field readonly 'NOMOR URUT
        BANGUNAN TERBESAR' — kalau ada isi angkanya, lanjutkan +1; kalau
        kosong/tidak ada info, isi 1 (instruksi eksplisit user). Diisi via
        klik chevron ▲ (bukan keyboard) krn field spinner ini kadang
        menolak/tidak stabil dgn input keyboard langsung."""
        self._log("Fix Nomor Urut Bangunan (GALAT terdeteksi di ringkasan) ...")
        terbesar_field = self.page.get_by_text(L["nomor_urut_bangunan_terbesar"], exact=False).first
        terbesar_val = ""
        try:
            terbesar_container = terbesar_field.locator("xpath=following::input[1]")
            terbesar_val = (terbesar_container.input_value() or "").strip()
        except Exception:
            pass
        target = int(terbesar_val) + 1 if terbesar_val.isdigit() else 1
        self._log(f"NOMOR URUT BANGUNAN TERBESAR='{terbesar_val or '(kosong)'}' -> target Nomor Urut Bangunan={target}")

        nub_label = self.page.get_by_text(L["nomor_urut_bangunan"], exact=False).last
        spinner = nub_label.locator("xpath=following::input[1]")
        up_chevron = spinner.locator("xpath=following::button[1]").last  # tombol ▲ biasanya elemen terakhir dari pasangan ▼▲
        current = 0
        try:
            current_raw = (spinner.input_value() or "0").strip()
            current = int(current_raw) if current_raw.lstrip("-").isdigit() else 0
        except Exception:
            current = 0
        clicks_needed = max(0, target - current)
        for _ in range(clicks_needed):
            up_chevron.click()
            self.page.wait_for_timeout(200)
        self._log(f"Nomor Urut Bangunan di-set ke {target} via {clicks_needed}x klik chevron ▲.")

    def do_geotagging(self, latitude: str, longitude: str):
        self._log(f"Geotagging: lat={latitude}, long={longitude}")
        self.click_button("ambil_lokasi_btn")
        self.page.get_by_text(L["pilih_lokasi_modal_title"], exact=False).wait_for(timeout=8000)
        lat_field = self.page.get_by_label(re.compile("latitude", re.I)).first
        lon_field = self.page.get_by_label(re.compile("longitude", re.I)).first
        lat_field.click(click_count=3)
        lat_field.fill(str(latitude))
        lon_field.click(click_count=3)
        lon_field.fill(str(longitude))
        self.click_button("gunakan_lokasi_btn")
        self.page.wait_for_timeout(1000)
        self.click_button("gunakan_lokasi_btn")  # step preview -> konfirmasi kedua
        self.page.get_by_text(re.compile("yakin ingin mengambil lokasi", re.I)).wait_for(timeout=5000)
        self.confirm_dialog("Ya")
        try:
            self.page.get_by_text(re.compile("berhasil mengambil lokasi", re.I)).wait_for(timeout=8000)
            self._log("Geotagging berhasil.")
        except PWTimeout:
            self._log("⚠️ Toast 'berhasil mengambil lokasi' tidak terdeteksi — cek manual.")

    # ------------------------------------------------------------------
    # IDENTITAS WILAYAH (2 field wajib yg mudah kelewat)
    # ------------------------------------------------------------------
    def fill_identitas_wilayah_extra(self, kodepos: str):
        self.select_radio("perubahan_sls", L["opsi_tidak_2"])
        self.fill_text("kodepos", kodepos)

    # ------------------------------------------------------------------
    # BLOK II — KBLI Master search dgn retry logic (bug termodokumentasi)
    # ------------------------------------------------------------------
    def fill_kbli_master(self, kbli_code: str, search_phrase_fallback: str = "") -> bool:
        """Pilih radio 'Pilih dari Master KBLI', cari kode, WAJIB verifikasi
        teks hasil match mengandung kode sebelum klik. Kalau hasil search
        tidak relevan/tidak terfilter (bug termodokumentasi), retry dgn
        urutan clear yang sudah terbukti berhasil di sesi manual."""
        self.page.get_by_text(L["pilih_master_kbli_radio"], exact=False).click()
        search_box = self.page.get_by_role("combobox").filter(has_text="").first
        if search_box.count() == 0:
            search_box = self.page.locator('input[type="text"]').last

        def try_search(term: str) -> bool:
            search_box.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            self.page.wait_for_timeout(300)
            search_box.type(term, delay=40)
            self.page.wait_for_timeout(1200)
            option = self.page.get_by_text(re.compile(re.escape(kbli_code)), exact=False).first
            if option.count() > 0 and kbli_code in (option.inner_text() or ""):
                option.click()
                return True
            return False

        if try_search(kbli_code):
            self._log(f"KBLI {kbli_code} ketemu langsung via kode angka.")
            return True

        self._log(f"⚠️ Search kode angka '{kbli_code}' tidak menghasilkan match relevan — retry dgn clear + frasa deskriptif.")
        # Urutan clear yg terbukti berhasil di sesi manual:
        x_btn = self.page.get_by_role("button", name=re.compile("clear|hapus|×|x", re.I))
        if x_btn.count() > 0:
            x_btn.first.click()
            confirm = self.page.get_by_text(L["kbli_clear_x"], exact=False)
            if confirm.count() > 0:
                self.confirm_dialog("Ya")
        search_box.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        self.page.wait_for_timeout(200)
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")  # bersihkan sisa karakter nyasar

        if search_phrase_fallback and try_search(search_phrase_fallback):
            self._log(f"KBLI {kbli_code} ketemu via frasa fallback '{search_phrase_fallback}'.")
            return True

        self._fail(
            f"KBLI {kbli_code} tidak ketemu setelah retry (coba isi search_phrase_fallback yg lebih deskriptif "
            "saat memanggil fill_kbli_master, mis. nama kategori usahanya)."
        )
        return False

    # ------------------------------------------------------------------
    # Ringkasan & submit
    # ------------------------------------------------------------------
    def check_ringkasan(self) -> Ringkasan:
        self.click_button("kirim_btn")
        self.page.get_by_text("GALAT", exact=False).wait_for(timeout=8000)

        def _num_near(label: str) -> int:
            try:
                el = self.page.get_by_text(label, exact=True).first
                num_el = el.locator("xpath=following::*[1]")
                txt = num_el.inner_text(timeout=2000).strip()
                return int(re.sub(r"\D", "", txt) or 0)
            except Exception:
                return -1

        galat = _num_near("GALAT")
        peringatan = _num_near("PERINGATAN")
        catatan = _num_near("CATATAN")
        kosong = _num_near("KOSONG")
        r = Ringkasan(galat=galat, peringatan=peringatan, catatan=catatan, kosong=kosong)
        self._log(f"Ringkasan: GALAT={r.galat} PERINGATAN={r.peringatan} CATATAN={r.catatan} KOSONG={r.kosong}")
        return r

    def read_galat_detail(self) -> str:
        """Buka detail kartu GALAT (kalau >0) & kembalikan teks gabungan
        semua item galat — dipakai main.py utk memutuskan apakah auto-fix
        Nomor Urut Bangunan relevan, atau ada GALAT lain yg butuh review
        manual (skrip TIDAK boleh menebak fix utk galat selain field itu)."""
        try:
            self.page.get_by_text("GALAT", exact=True).first.click()
            self.page.wait_for_timeout(500)
            body = self.page.get_by_text(re.compile("TOTAL:", re.I)).first.locator(
                "xpath=ancestor::*[self::div][2]"
            )
            txt = body.inner_text(timeout=3000)
            return txt
        except Exception:
            return ""

    def close_ringkasan_dialog(self):
        try:
            self.page.get_by_role("button", name=re.compile("batal", re.I)).click(timeout=3000)
        except Exception:
            self.page.keyboard.press("Escape")

    def submit_final(self) -> bool:
        """HANYA dipanggil setelah caller mengonfirmasi GALAT=0 DAN sudah
        dapat izin eksplisit dari user (per-batch, bukan otomatis).
        Dialog ringkasan diasumsikan SUDAH TERBUKA (dari check_ringkasan)."""
        self.click_button("kirim_btn")  # tombol Kirim di DALAM dialog ringkasan
        self.page.get_by_text(re.compile("yakin ingin mengirimkan data", re.I)).wait_for(timeout=8000)
        self.click_button("konfirmasi_btn")
        try:
            self.page.get_by_text(re.compile("tersimpan|berhasil dikirim", re.I)).wait_for(timeout=15_000)
        except PWTimeout:
            self._log("⚠️ Toast konfirmasi submit tidak terdeteksi dlm 15dtk — WAJIB verifikasi manual via list PENDATAAN + Muat Ulang.")
            return False
        self._log("Submit terkirim (toast terdeteksi) — status FINAL tetap harus diverifikasi via list + Muat Ulang (bisa stale).")
        return True

    def verify_submitted_in_list(self, assignment_id: str, nama_usaha: str) -> bool:
        """WAJIB dipanggil setelah submit_final() — status di list bisa
        tampil stale ('DRAFT') sesaat sebelum di-refresh (temuan nyata dari
        record 3)."""
        self.goto_pendataan(assignment_id)
        reload_btn = self.page.get_by_text(L["muat_ulang_btn"], exact=False)
        if reload_btn.count() > 0:
            reload_btn.first.click()
            self.page.wait_for_timeout(1500)
        row = self.page.get_by_text(nama_usaha, exact=False).first
        try:
            row.wait_for(timeout=8000)
            container = row.locator("xpath=ancestor::tr[1] | ancestor::*[self::div][1]")
            status_ok = container.get_by_text(re.compile("SUBMITTED|CLEAN", re.I)).count() > 0
            self._log(f"Verifikasi status list utk '{nama_usaha}': {'SUBMITTED/CLEAN' if status_ok else 'BELUM/tidak terdeteksi'}")
            return status_ok
        except Exception:
            self._log(f"⚠️ Tidak bisa verifikasi status list utk '{nama_usaha}'.")
            return False
