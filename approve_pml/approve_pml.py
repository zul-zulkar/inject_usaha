#!/usr/bin/env python3
"""
approve_pml.py — Approve (oleh PML/Pengawas) dokumen SE2026 yang sudah dikirim PPL
lewat main_gabungan.py. Dipetakan langsung 2026-09-15 (akun PML misdiantosgr, PPL wisada9).

YANG SUDAH DILIHAT DI fasih-web (akun Pengawas)
----------------------------------------------
- Membuka dokumen PML = URL entry yang sama dgn PPL (…/{id}/entry). Bar bawah kuesioner
  berisi tombol "Reject" (ikon x) & "Approve" (ikon checklist).
- Klik "Approve" -> dialog "Konfirmasi Approve" ("Apakah Anda yakin ingin melakukan approve
  dokumen ini?") dgn tombol "Batal" / "Approve" / "Close". Klik "Approve" DI DIALOG itulah
  yang mengeksekusi (irreversible).
- Status per dokumen: GET /api/assignment-general/api/assignment/web-entry/get-by-id-with-data?id=
  -> data.assignment_status_alias ("SUBMITTED BY Pencacah" / "APPROVED BY Pengawas") dan
  data.data (JSON string) berisi createdBy/updatedBy = email PPL pembuat.
- List PENDATAAN akun PML berisi ribuan dokumen (misdiantosgr: 4.870) -> API datatable dgn
  length 100 membalas 504. Karena itu target TIDAK diambil dari list penuh, melainkan dari
  audit_log_gabungan.csv (+ opsional pencarian list per subsls, length kecil).

PENGAMAN (gagal-tertutup)
------------------------
Satu dokumen hanya di-approve kalau, tepat sebelum diklik, API menyatakan
SUBMITTED BY Pencacah DAN createdBy/updatedBy = --akun-ppl; tombol Approve di bar & di
dialog masing-masing tepat satu. Sukses = status API berubah jadi APPROVED (bukan toast).
Dialog konfirmasi yang tidak muncul / tombol ambigu -> batch berhenti.

LANGKAH
-------
1. Petakan / cek (READ-ONLY, tanpa klik): status semua target lewat API
       python approve_pml/approve_pml.py --akun-pml misdiantosgr@gmail.com --akun-ppl wisada9@mail.com
2. Eksekusi 1 dokumen dulu, cek hasilnya:
       python approve_pml/approve_pml.py --akun-pml ... --akun-ppl ... --eksekusi --limit 1
3. Sisanya (dokumen yang sudah APPROVED otomatis dilewati):
       python approve_pml/approve_pml.py --akun-pml ... --akun-ppl ... --eksekusi

Login: cookie sesi disimpan di .sesi_fasih_web_<akun>.json (+ profil .profil_fasih_web_<akun>/),
keduanya berisi sesi -> .gitignore. Kalau sesi tidak hidup: default login otomatis dgn
FIXED_PASSWORD (seperti main_gabungan); --login-manual = tunggu manusia login di jendela browser.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import (ASSIGNMENT_ID_GABUNGAN, FASIH_WEB_BASE, FASIH_WEB_LOGIN_URL, FIXED_PASSWORD, L,
                         SEL, SURVEY_ID)

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

AUDIT_GABUNGAN = Path("./audit_log_gabungan.csv")
AUDIT_APPROVE = Path("./audit_approve_pml.csv")
AUDIT_FIELDS = ["timestamp", "akun_pml", "akun_ppl", "id", "baris", "kunci", "nama", "sumber",
                "status_sebelum", "status", "pesan", "dokumen_url"]
LOG_DIR = Path("./log_approve")
API_DETAIL = "/api/assignment-general/api/assignment/web-entry/get-by-id-with-data?id="

ST_SIAP = "SIAP_APPROVE"
ST_SUDAH = "SUDAH_APPROVED"
ST_OK = "APPROVED_TERVERIFIKASI"
# Kejanggalan yang pasti berulang di dokumen berikutnya -> hentikan batch.
STATUS_BERHENTI_SEGERA = {"STOP_DIALOG_TIDAK_MUNCUL", "STOP_TOMBOL_AMBIGU", "STOP_AKUN_BERUBAH",
                          "APPROVE_TIDAK_TERVERIFIKASI"}


def slug_akun(akun: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", akun.lower()).strip("_")


def id_dari_url(url: str) -> str:
    bagian = (url or "").rstrip("/").split("/")
    return bagian[-2] if len(bagian) >= 2 and bagian[-1] == "entry" else ""


def url_entry(doc_id: str, assignment_id: str) -> str:
    return f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/{assignment_id}/{doc_id}/entry"


# ----------------------------------------------------------------------
# Logika murni (tanpa browser) — diuji tests/test_approve_pml.py
# ----------------------------------------------------------------------
def dokumen_audit_ppl(audit: list[dict], akun_ppl: str) -> dict[str, dict]:
    """id dokumen -> baris audit TERAKHIR yang menyebut dokumen itu, utk akun PPL ini.
    Dokumen yang dicatat DOKUMEN_DIHAPUS digugurkan."""
    akun_ppl = akun_ppl.lower()
    hasil: dict[str, dict] = {}
    for b in audit:
        if (b.get("akun_login") or "").lower() != akun_ppl:
            continue
        i = id_dari_url(b.get("dokumen_url"))
        if not i:
            continue
        if b.get("status") == "DOKUMEN_DIHAPUS":
            hasil.pop(i, None)
            continue
        hasil[i] = b
    return hasil


def subsls_audit_ppl(audit: list[dict], akun_ppl: str) -> list[str]:
    """Subsls tempat dokumen PPL ini dibuat (kolom idsubsls_input)."""
    akun_ppl = akun_ppl.lower()
    return sorted({(b.get("idsubsls_input") or "").strip() for b in audit
                   if (b.get("akun_login") or "").lower() == akun_ppl} - {""})


def petugas_dokumen(detail: dict) -> set[str]:
    """{createdBy, updatedBy} dari data.data (JSON string) respons get-by-id-with-data."""
    isi = detail.get("data")
    if isinstance(isi, str):
        try:
            isi = json.loads(isi)
        except ValueError:
            isi = {}
    if not isinstance(isi, dict):
        return set()
    return {str(isi.get(k) or "").strip().lower() for k in ("createdBy", "updatedBy")} - {""}


def nilai_dokumen(detail: dict | None, akun_ppl: str) -> tuple[str, str]:
    """-> (kategori, pesan) satu dokumen menurut API detail. Hanya ST_SIAP yang boleh di-approve."""
    if not detail:
        return "SKIP_DETAIL_TIDAK_TERBACA", "respons get-by-id-with-data kosong"
    alias = str(detail.get("assignment_status_alias") or "")
    up = alias.upper()
    if "APPROVED" in up:
        return ST_SUDAH, alias
    if not up.startswith("SUBMITTED BY PENCACAH"):
        return "SKIP_STATUS_" + (re.sub(r"[^A-Z]+", "_", up).strip("_") or "KOSONG"), alias
    petugas = petugas_dokumen(detail)
    if akun_ppl.lower() not in petugas:
        return "SKIP_BUKAN_PPL", f"createdBy/updatedBy = {sorted(petugas) or '-'}"
    return ST_SIAP, alias


def gabung_target(audit_docs: dict[str, dict], items_list: list[dict]) -> list[dict]:
    """Target = dokumen audit PPL (urut audit) + dokumen list tersaring yang tidak ada di audit."""
    target = [{"id": i, "baris": b.get("baris", ""), "kunci": b.get("kunci", ""),
               "nama": b.get("nama_usaha", ""), "sumber": "audit"} for i, b in audit_docs.items()]
    sudah = set(audit_docs)
    for it in items_list:
        i = it.get("id")
        if i and i not in sudah:
            sudah.add(i)
            target.append({"id": i, "baris": "", "kunci": "", "nama": it.get("data1") or "", "sumber": "list"})
    return target


def baca_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_audit(row: dict):
    baru = not AUDIT_APPROVE.exists()
    with AUDIT_APPROVE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        if baru:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in AUDIT_FIELDS})


# ----------------------------------------------------------------------
# Browser
# ----------------------------------------------------------------------
def api_get(sess, path: str) -> dict | None:
    """GET JSON dari halaman (cookie sesi). Endpoint get-by-id-with-data cukup dgn cookie
    (terlihat dari request aplikasi sendiri: tanpa header Authorization)."""
    try:
        hasil = sess.page.evaluate("""async (url) => {
          try {
            const r = await fetch(url, {credentials: 'include', headers: {'content-type': 'application/json'}});
            return {status: r.status, text: await r.text()};
          } catch (e) { return {status: 0, text: String(e)}; }
        }""", path)
    except Exception:
        return None
    if not hasil or hasil.get("status") != 200:
        return None
    try:
        return json.loads(hasil["text"])
    except ValueError:
        return None


def detail_dokumen(sess, doc_id: str, percobaan: int = 4) -> dict | None:
    """Detail dokumen, diulang kalau gagal: run 2026-09-15 empat dokumen berturut-turut
    "kosong" tepat setelah approve dokumen sebelumnya (halaman sedang redirect -> evaluate
    gagal), padahal API-nya normal saat dicek ulang."""
    for ke in range(1, percobaan + 1):
        j = api_get(sess, API_DETAIL + doc_id)
        data = (j or {}).get("data")
        if isinstance(data, dict):
            return data
        if ke < percobaan:
            try:
                sess.page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                pass
            sess.page.wait_for_timeout(2_000 * ke)
    return None


def email_aktif(sess) -> str:
    """Email akun yang sedang login (fetch check-user), '' kalau tidak terbaca.
    Catatan: aplikasi memanggil check-user dgn POST (201); GET bisa gagal -> andalkan sadapan."""
    for metode in ("POST", "GET"):
        try:
            hasil = sess.page.evaluate("""async (m) => {
              try {
                const r = await fetch('/api/survey/api/v1/users/check-user', {method: m, credentials: 'include',
                                      headers: {'content-type': 'application/json'}});
                if (!r.ok) return null;
                const j = await r.json();
                return (j && j.data) ? j.data : null;
              } catch (e) { return null; }
            }""", metode)
        except Exception:
            continue
        if isinstance(hasil, dict):
            e = str(hasil.get("email") or hasil.get("username") or "").strip().lower()
            if e:
                return e
    return ""


def akun_terbaca(sess, tunggu_ms: int) -> str:
    """Email akun aktif: sadapan respons check-user (FasihWebSession) — fetch langsung
    TIDAK cukup (run 2026-09-15: login manual sukses tapi fetch GET tetap kosong) —
    dgn fetch sbg cadangan."""
    batas = time.time() + tunggu_ms / 1000.0
    while True:
        if sess.akun_api.get("email"):
            return sess.akun_api["email"].lower()
        if time.time() >= batas:
            return email_aktif(sess)
        sess.page.wait_for_timeout(500)


def pastikan_login(sess, akun: str, manual: bool, file_sesi: Path):
    """Pakai sesi tersimpan kalau masih hidup & akunnya benar; kalau tidak, login.
    Cookie sesi (SSO & fasih-web tanpa tanggal kedaluwarsa -> TIDAK disimpan profil
    Chromium, terbukti 2026-09-15) disimpan di `file_sesi` & dipasang ulang saat mulai."""
    akun = akun.lower()
    ctx = sess.page.context
    if file_sesi.exists():
        try:
            ctx.add_cookies(json.loads(file_sesi.read_text(encoding="utf-8")).get("cookies", []))
        except Exception as e:
            sess._log(f"⚠️ cookie sesi tersimpan tidak bisa dipasang: {e}")
    sess.akun_api = {}
    sess.page.goto(FASIH_WEB_BASE, wait_until="domcontentloaded", timeout=45_000)
    aktif = akun_terbaca(sess, 15_000)
    if aktif == akun:
        sess._log(f"✅ Sesi tersimpan masih hidup: {aktif}")
        return
    if aktif:
        sess._log(f"Sesi tersimpan milik akun LAIN ({aktif}) — diputus.")
        sess.logout()
    if not manual:
        sess.login(akun, FIXED_PASSWORD)
    else:
        sess.page.goto(FASIH_WEB_LOGIN_URL, wait_until="domcontentloaded", timeout=45_000)
        try:
            sess.page.get_by_text(L["sso_eksternal_btn"], exact=False).first.click(timeout=15_000)
        except Exception:
            pass
        print(f"\n>>> LOGIN MANUAL di jendela browser sbg {akun} (menunggu maks 15 menit) ...", flush=True)
        batas = time.time() + 15 * 60
        terakhir_lapor = 0.0
        while time.time() < batas:
            sess.page.wait_for_timeout(3_000)
            u = sess.page.url.lower()
            if time.time() - terakhir_lapor > 30:
                print(f"    (menunggu login — url sekarang {sess.page.url[:100]})", flush=True)
                terakhir_lapor = time.time()
            if "fasih-web.bps.go.id" in u and "/login" not in u and "/auth" not in u:
                if akun_terbaca(sess, 3_000):
                    break
        else:
            raise RuntimeError("Login manual tidak selesai dalam 15 menit")
    aktif = akun_terbaca(sess, 10_000)
    if aktif != akun:
        raise RuntimeError(f"AKUN SALAH/TIDAK TERVERIFIKASI: diminta '{akun}', aktif '{aktif or '-'}'")
    sess._log(f"✅ Login terverifikasi: {aktif}")
    simpan_sesi(sess, file_sesi)


def simpan_sesi(sess, file_sesi: Path):
    try:
        file_sesi.write_text(json.dumps(sess.page.context.storage_state()), encoding="utf-8")
    except Exception as e:
        sess._log(f"⚠️ sesi tidak tersimpan: {e}")


def cari_list(sess, assignment_id: str, kata: str, per_halaman: int = 50) -> list[dict]:
    """Item list PENDATAAN yang cocok kata cari (mis. subsls), lewat API datatable yang
    dipanggil list sendiri (body + header x-* disadap), length KECIL: list PML penuh
    (length 100 tanpa saring) membalas 504. READ-ONLY."""
    tangkap: dict = {}

    def _on_request(req):
        if "datatable-all-user-survey-periode" in req.url and req.method == "POST" and "body" not in tangkap:
            tangkap.update(url=req.url, body=req.post_data, headers=req.headers)
    sess.page.on("request", _on_request)
    try:
        sess.goto_pendataan(assignment_id)
        batas = time.time() + 60
        while "body" not in tangkap and time.time() < batas:
            sess.page.wait_for_timeout(300)
    finally:
        sess.page.remove_listener("request", _on_request)
    if "body" not in tangkap:
        raise RuntimeError("Request datatable list PENDATAAN tidak tertangkap dalam 60 dtk")
    body = json.loads(tangkap["body"])
    hdr = {k: v for k, v in tangkap["headers"].items()
           if k.lower() in ("content-type", "accept") or k.lower().startswith("x-")}
    body["search"] = {"value": kata, "regex": False}
    per_id: dict = {}
    start = 0
    while True:
        body["start"], body["length"] = start, per_halaman
        hasil = None
        for percobaan in range(1, 4):
            hasil = sess.page.evaluate("""async ([url, body, hdr]) => {
                const r = await fetch(url, {method: 'POST', credentials: 'include', headers: hdr,
                                            body: JSON.stringify(body)});
                return {status: r.status, text: await r.text()};
            }""", [tangkap["url"], body, hdr])
            if hasil["status"] == 200:
                break
            sess._log(f"⚠️ API list '{kata}' start={start} status {hasil['status']} (percobaan {percobaan}/3)")
            sess.page.wait_for_timeout(5_000)
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
    sess._log(f"List tersaring '{kata}': {len(per_id)} dokumen (totalHit {total}).")
    return list(per_id.values())


def _dialog_konfirmasi(sess):
    return sess._visible(sess.page.locator('[role="dialog"], [role="alertdialog"]').filter(
        has_text=re.compile(r"yakin ingin melakukan approve", re.I)))


def approve_satu(sess, t: dict, assignment_id: str, akun_ppl: str, eksekusi: bool) -> dict:
    """Proses satu dokumen. Mengembalikan baris audit (tanpa timestamp/akun)."""
    res = {**t, "dokumen_url": url_entry(t["id"], assignment_id)}
    detail = detail_dokumen(sess, t["id"])
    kategori, pesan = nilai_dokumen(detail, akun_ppl)
    res["status_sebelum"] = (detail or {}).get("assignment_status_alias", "")
    if not res["nama"] and detail:
        res["nama"] = detail.get("data1") or ""
    if kategori != ST_SIAP:
        return {**res, "status": kategori, "pesan": pesan}

    sess.page.goto(res["dokumen_url"], wait_until="domcontentloaded", timeout=45_000)
    try:
        sess.page.locator(SEL["form_root"]).first.wait_for(state="attached", timeout=45_000)
    except Exception:
        sess._shot(f"approve_form_tidak_mount_{t['id'][:8]}")
        return {**res, "status": "ERROR_FORM_TIDAK_MOUNT", "pesan": "form-engine tidak mount dlm 45 dtk"}
    tombol = sess._visible(sess.page.get_by_role("button", name=re.compile(r"^\s*Approve\s*$")))
    try:
        tombol.first.wait_for(state="visible", timeout=30_000)
    except Exception:
        sess._shot(f"approve_tombol_tidak_ada_{t['id'][:8]}")
        return {**res, "status": "ERROR_TOMBOL_APPROVE_TIDAK_ADA",
                "pesan": "tombol Approve di bar bawah tidak tampil dlm 30 dtk"}
    if tombol.count() != 1:
        return {**res, "status": "STOP_TOMBOL_AMBIGU", "pesan": f"{tombol.count()} tombol Approve terlihat"}
    if not eksekusi:
        return {**res, "status": "DRY_RUN_SIAP_APPROVE", "pesan": "tombol Approve ada (tidak diklik)"}

    sess.klik_tahan(tombol.first, "Approve (bar bawah)")
    dialog = _dialog_konfirmasi(sess)
    try:
        dialog.first.wait_for(state="visible", timeout=15_000)
    except Exception:
        sess.debug_dialog("approve_tanpa_dialog")
        sess._shot(f"approve_dialog_tidak_muncul_{t['id'][:8]}")
        # Bisa jadi aplikasi langsung meng-approve tanpa dialog: status tetap diperiksa.
        d2 = detail_dokumen(sess, t["id"])
        if d2 and "APPROVED" in str(d2.get("assignment_status_alias") or "").upper():
            return {**res, "status": ST_OK, "pesan": "dialog tidak muncul, tapi status API sudah APPROVED"}
        return {**res, "status": "STOP_DIALOG_TIDAK_MUNCUL", "pesan": "dialog 'Konfirmasi Approve' tidak muncul"}
    konfirmasi = dialog.first.get_by_role("button", name=re.compile(r"^\s*Approve\s*$"))
    if konfirmasi.count() != 1:
        sess.debug_dialog("approve_konfirmasi_ambigu")
        return {**res, "status": "STOP_TOMBOL_AMBIGU", "pesan": f"{konfirmasi.count()} tombol Approve di dialog"}
    sess.page.wait_for_timeout(500)  # animasi buka dialog

    jejak: list[str] = []

    def _rekam(resp):
        try:
            if resp.request.method != "GET" and "/api/" in resp.url and "check-user" not in resp.url:
                isi = ""
                try:
                    isi = (resp.text() or "")[:200]
                except Exception:
                    pass
                jejak.append(f"{resp.request.method} {resp.status} {resp.url.split('/api/', 1)[-1][:90]} {isi}")
        except Exception:
            pass
    sess.page.on("response", _rekam)
    try:
        sess.klik_tahan(konfirmasi, "Approve (dialog Konfirmasi Approve)")
        # Sukses = status API berubah (toast/redirect bukan bukti, lihat CLAUDE.md "Toast ≠ terkirim").
        status_akhir = ""
        for _ in range(30):
            sess.page.wait_for_timeout(2_000)
            d2 = detail_dokumen(sess, t["id"])
            status_akhir = str((d2 or {}).get("assignment_status_alias") or "")
            if "APPROVED" in status_akhir.upper():
                sess._log(f"✅ APPROVED: {res['nama']} ({t['id'][:8]}) -> {status_akhir}")
                return {**res, "status": ST_OK, "pesan": f"{status_akhir} | api={jejak[-3:]}"}
        sess._shot(f"approve_tidak_terverifikasi_{t['id'][:8]}")
        sess.debug_dialog("pasca_approve")
        return {**res, "status": "APPROVE_TIDAK_TERVERIFIKASI",
                "pesan": f"status API tetap '{status_akhir}' 60 dtk setelah konfirmasi | api={jejak[-5:]}"}
    finally:
        try:
            sess.page.remove_listener("response", _rekam)
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--akun-pml", required=True)
    ap.add_argument("--akun-ppl", required=True, help="akun_login PPL di audit_log_gabungan.csv")
    ap.add_argument("--assignment-id", default=ASSIGNMENT_ID_GABUNGAN)
    ap.add_argument("--eksekusi", action="store_true", help="SUNGGUHAN klik Approve (irreversible)")
    ap.add_argument("--ya", action="store_true", help="lewati prompt ketik YA (izin sudah diberikan)")
    ap.add_argument("--limit", type=int, default=0, help="maks dokumen yang di-approve/di-dry-run")
    ap.add_argument("--termasuk-di-luar-audit", action="store_true",
                    help="ikut proses dokumen list (dicari per subsls audit) yang tidak tercatat di audit; "
                         "tetap wajib createdBy/updatedBy = akun PPL")
    ap.add_argument("--login-manual", action="store_true", help="tunggu manusia login di jendela browser")
    ap.add_argument("--maks-error-beruntun", type=int, default=3)
    args = ap.parse_args()
    akun_pml = args.akun_pml.strip().lower()
    akun_ppl = args.akun_ppl.strip().lower()

    audit = baca_csv(AUDIT_GABUNGAN)
    audit_docs = dokumen_audit_ppl(audit, akun_ppl)
    if not audit_docs:
        print(f"❌ Tidak ada dokumen akun {akun_ppl} di {AUDIT_GABUNGAN}.", file=sys.stderr)
        return 2
    print(f"{'⚠️ EKSEKUSI (klik Approve sungguhan)' if args.eksekusi else 'DRY-RUN (tanpa klik Approve)'} — "
          f"PML {akun_pml}, PPL {akun_ppl}, {len(audit_docs)} dokumen di audit.")
    if args.eksekusi and not args.ya:
        if input("Ketik 'YA' utk APPROVE sungguhan (irreversible): ").strip().upper() != "YA":
            print("Dibatalkan.")
            return 1

    from playwright.sync_api import sync_playwright
    from inti.fasih_web import FasihWebSession
    hitung: Counter = Counter()
    kode = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(Path(f".profil_fasih_web_{slug_akun(akun_pml)}")), headless=False,
            viewport={"width": 1440, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        sess = FasihWebSession(page)
        file_sesi = Path(f".sesi_fasih_web_{slug_akun(akun_pml)}.json")
        try:
            pastikan_login(sess, akun_pml, args.login_manual, file_sesi)
            items_list: list[dict] = []
            for subsls in subsls_audit_ppl(audit, akun_ppl):
                try:
                    items_list += cari_list(sess, args.assignment_id, subsls)
                except Exception as e:
                    print(f"⚠️ Pencarian list subsls {subsls} gagal (tidak fatal): {str(e)[:150]}")
            luar = [it for it in items_list if it.get("id") not in audit_docs]
            target = gabung_target(audit_docs, items_list if args.termasuk_di_luar_audit else [])
            print(f"Dokumen list subsls PPL yg TIDAK di audit: {len(luar)} "
                  f"{dict(Counter(i.get('assignmentStatusAlias') for i in luar))}"
                  + ("" if args.termasuk_di_luar_audit else " — tidak diproses (pakai --termasuk-di-luar-audit)"))
            print(f"Target: {len(target)} dokumen.\n")

            diproses = 0
            error_beruntun = 0
            for n, t in enumerate(target, start=1):
                if args.limit and diproses >= args.limit:
                    break
                res = approve_satu(sess, t, args.assignment_id, akun_ppl, args.eksekusi)
                res.update(timestamp=time.strftime("%Y-%m-%d %H:%M:%S"), akun_pml=akun_pml, akun_ppl=akun_ppl)
                if res["status"] not in (ST_SUDAH,) and not res["status"].startswith("SKIP_"):
                    diproses += 1
                if res["status"] != ST_SUDAH:
                    append_audit(res)
                hitung[res["status"]] += 1
                print(f"[{n}/{len(target)}] {res['status']:28s} {t['id'][:8]} baris {t['baris'] or '-':>4} "
                      f"{res['nama']}" + (f" | {res['pesan'][:160]}" if res["status"] not in (ST_OK, ST_SUDAH) else ""),
                      flush=True)
                if res["status"] in STATUS_BERHENTI_SEGERA:
                    print(f"\n⛔ {res['status']} — batch DIHENTIKAN. Lihat {AUDIT_APPROVE} & log_screenshots/.")
                    kode = 1
                    break
                error_beruntun = error_beruntun + 1 if res["status"].startswith("ERROR_") else 0
                if args.maks_error_beruntun and error_beruntun >= args.maks_error_beruntun:
                    print(f"\n⛔ {error_beruntun} ERROR berturut-turut — batch DIHENTIKAN (VPN/sesi?).")
                    kode = 1
                    break
                if n % 10 == 0:
                    if akun_terbaca(sess, 0) not in ("", akun_pml):
                        print("\n⛔ STOP_AKUN_BERUBAH — akun aktif bukan PML yang diminta.")
                        kode = 1
                        break
                    simpan_sesi(sess, file_sesi)
            simpan_sesi(sess, file_sesi)
        finally:
            ctx.close()
    print(f"\nRingkasan: {dict(hitung)}\nAudit: {AUDIT_APPROVE}")
    return kode


if __name__ == "__main__":
    sys.exit(main())
