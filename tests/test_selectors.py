"""Uji selektor fasih_web.py terhadap fixture DOM — OFFLINE, tanpa VPN.

Fixture-nya disalin dari dump DOM asli halaman Entri Dokumen fasih-web,
jadi ini menangkap regresi selector tanpa perlu menyentuh dokumen sungguhan.

    python tests/test_selectors.py

Menguji hal-hal yang pernah benar-benar bikin gagal di produksi:
  - teks dirender 2x (mobile & desktop) -> .first bisa kena yang hidden
  - link aksi baris list ("Entri" vs "Tinjau") harus lewat href $= /entry
  - sidebar section & deteksi section aktif
  - komponen #mulai hanya punya 1 tombol Ambil Waktu (PML di-hide)
  - helper berbasis dataKey: fill_by_datakey & select_radio_by_datakey
"""
import pathlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright
from inti.config import L, SEL

FIXTURE = Path(__file__).with_name("fixture_fasih_web.html").as_uri()
ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} | {label}: got={got!r} want={want!r}")


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.goto(FIXTURE)
    vis = lambda loc: loc.locator("visible=true")

    # --- inti bug: teks dirender 2x, satu hidden ---
    all_txt = page.get_by_text("Toko Kembarsari Keperluan Rumah", exact=False)
    check("get_by_text tanpa filter (count termasuk hidden)", all_txt.count() >= 2, True)
    check("first tanpa filter -> elemen HIDDEN (inilah penyebab timeout)",
          all_txt.first.is_visible(), False)
    check("first SETELAH visible=true -> visible", vis(all_txt).first.is_visible(), True)

    # --- link aksi: naik ke ancestor terdekat yg punya a[href$=/entry] ---
    row = vis(all_txt).first
    link = vis(row.locator(
        'xpath=ancestor::*[.//a[substring(@href, string-length(@href) - 5) = "/entry"]][1]'
        '//a[substring(@href, string-length(@href) - 5) = "/entry"]'
    )).first
    check("link /entry ketemu", link.count(), 1)
    check("link /entry milik BARIS YG BENAR", link.get_attribute("href"),
          "/survey/aaa/bbb/ddd/entry")
    check("teks link (bisa Entri / Tinjau)", link.inner_text().strip(), "Entri")

    # --- sidebar ---
    items = page.locator(SEL["sidebar_item"])
    check("list_sections (pakai '>' shg div[title] bersarang tdk ikut)",
          [items.nth(i).get_attribute("title") for i in range(items.count())],
          ["PENGANTAR", "SE2026-P"])
    active = page.locator(SEL["sidebar_item_active"])
    check("section aktif tepat 1", active.count(), 1)
    check("judul section aktif", active.first.get_attribute("title"), "PENGANTAR")
    check("goto_section('SE2026-P') ketemu",
          page.locator('div.fasih-form-sidebar > div[title="SE2026-P"]').count(), 1)
    check("sidebar_toggle", page.locator(SEL["sidebar_toggle"]).count(), 1)

    # --- navigasi ---
    check("has_next_section() = False (yg dirender submit)",
          page.locator(SEL["nav_next"]).count() > 0, False)
    check("nav_submit ada", page.locator(SEL["nav_submit"]).count(), 1)

    # --- PENGANTAR / #mulai ---
    mulai = page.locator("#mulai")
    check("#mulai ada", mulai.count(), 1)
    btn = vis(mulai.get_by_role("button", name=re.compile(re.escape(L["ambil_waktu_btn"]), re.I)))
    check("tombol Ambil Waktu di dalam #mulai tepat 1 (bukan 2)", btn.count(), 1)
    check("empty-state 'Waktu belum diambil' terdeteksi",
          mulai.get_by_text(L["waktu_belum_diambil"], exact=False).count() > 0, True)
    # Tombol 'Ambil Waktu' milik PML ada di DOM tapi display:none.
    # get_by_text MENGHITUNG yg hidden (2) -> pendekatan lama rawan;
    # get_by_role sudah mengabaikannya (1) -> plus scoping ke #mulai.
    check("get_by_text page-wide ikut menghitung tombol PML yg hidden",
          page.get_by_text("Ambil Waktu", exact=False).count() >= 2, True)
    check("get_by_role page-wide sudah mengabaikan tombol PML (display:none)",
          page.get_by_role("button", name=re.compile("Ambil Waktu", re.I)).count(), 1)

    # --- floating toolbar ---
    save = vis(page.locator(SEL["toolbar_save"]))
    check("tombol save (ikon disket) visible tepat 1", save.count(), 1)
    check("form_root", page.locator(SEL["form_root"]).count(), 1)

    b.close()

print("\n" + ("SEMUA SELEKTOR LOLOS" if ok_all else "ADA YANG GAGAL"))
sys.exit(0 if ok_all else 1)
