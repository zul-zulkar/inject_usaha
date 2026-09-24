#!/usr/bin/env python3
"""
sinkron_list.py — cocokkan list PENDATAAN fasih-web (lewat API, READ-ONLY) dgn
baris sheet gabungan & audit_log_gabungan.csv.

Kenapa ada: 2026-09-14 Agenda1-1.xlsx sempat diinput program LAIN dgn akun yang
sama (audit berbeda) -> ±70 dokumen tidak tercatat di audit & 5 duplikat
terkirim; plus satu baris (Agenda baris 96) tercatat terkirim padahal masih
DRAFT di server. Audit saja tidak bisa dipercaya sbg satu-satunya sumber.

Yang dilaporkan per baris (pencocokan lewat nama dokumen, di-UPPERCASE form):
  TERKIRIM / DRAFT / BELUM_ADA / GANDA (>1 dokumen bernama sama) /
  DI_AKUN_LAIN (audit mencatat dokumen baris ini di akun lain) — plus dokumen
  server yang tidak cocok dgn baris mana pun.

--tulis menambahkan ke audit (tidak pernah mengubah server):
  - DOKUMEN_DIBUAT + URL utk dokumen server yang belum tercatat  -> main_gabungan
    membukanya lewat URL, TIDAK membuat dokumen baru;
  - TERKIRIM_TERVERIFIKASI utk baris yang dokumennya sudah terkirim -> dilewati
    --lewati-selesai;
  - DRAFT_DI_SERVER utk baris yang audit bilang terkirim tapi server DRAFT ->
    diproses ulang (dibuka lewat URL) oleh --lewati-selesai.
  - DOKUMEN_DIHAPUS utk baris bertanda DOKUMEN_TANPA_URL_PERLU_CEK yang TERBUKTI
    tidak punya dokumen di server (list utuh, nama tidak ada, & tidak ada DRAFT
    kosong tanpa nama) -> tandanya gugur, main_gabungan boleh membuat dokumennya.
  Baris GANDA yang dua-duanya DRAFT tidak ditulis (pilih manual).

Contoh:
    python input_gabungan/sinkron_list.py --sumber input_usaha.xlsx --sumber input_usaha_2.xlsx \
        --akun-tunggal ppl.kedua@gmail.com --subsls-tunggal 5108060014000403
    (tambahkan --tulis setelah laporan ditinjau; --dari-json utk memakai hasil unduhan terakhir)

    Format tahap 2 (hasil pendataan kertas): tambahkan --format tahap2, mis.
    python input_gabungan/sinkron_list.py --format tahap2 --sumber bahan/input_tahap2.xlsx         --akun-tunggal ppl.contoh@gmail.com --subsls-tunggal 5108010010000105
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from inti.config import ASSIGNMENT_ID_GABUNGAN, FASIH_WEB_BASE, FIXED_PASSWORD, SURVEY_ID
from inti.gabungan_loader import GabunganRow
import input_gabungan.main_gabungan as mg

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

STATUS_DRAFT_SERVER = "DRAFT_DI_SERVER"
# Draft yang oleh SERVER ditandai bergalat (sumError > 0 = kartu "Jumlah Error" di
# halaman PENDATAAN). Ditulis sbg status TERAKHIR kunci itu supaya --lewati-selesai
# TIDAK melewatinya — termasuk draft tanpa koordinat, yang tanpa penanda ini
# dianggap tuntas sementara & galatnya tidak pernah dibereskan.
STATUS_DRAFT_GALAT = mg.STATUS_DRAFT_GALAT
LAPORAN_PATH = Path("./sinkron_list.csv")


def norm(teks: str) -> str:
    return " ".join((teks or "").split()).upper()


def status_server(alias: str) -> str:
    a = (alias or "").upper()
    if a.startswith("DRAFT"):
        return "DRAFT"
    if "SUBMIT" in a or "APPROV" in a or "COMPLETE" in a:
        return "TERKIRIM"
    return "LAIN"


def url_entry(doc_id: str, assignment_id: str) -> str:
    return f"{FASIH_WEB_BASE}/survey/{SURVEY_ID}/{assignment_id}/{doc_id}/entry"


def id_dari_url(url: str) -> str:
    bagian = (url or "").rstrip("/").split("/")
    return bagian[-2] if len(bagian) >= 2 and bagian[-1] == "entry" else ""


def jam_lokal(iso: str) -> str:
    try:
        return datetime.datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return time.strftime("%Y-%m-%d %H:%M:%S")


def rencana_sinkron(sumber_rows: list[tuple[str, GabunganRow, str]], items: list[dict], akun: str,
                    subsls: str, assignment_id: str, audit: list[dict], lengkap: bool = False):
    """Fungsi murni. `sumber_rows` = [(nama_file, row, status_cek)]. `lengkap` = list
    server terbukti utuh (dibaca langsung, id unik == totalHit): HANYA saat itu dokumen
    audit yang tidak ada di server boleh dinyatakan DOKUMEN_DIHAPUS.
    -> (laporan per baris, baris audit yang akan ditulis, dokumen server tak dikenali)."""
    akun = akun.lower()
    items = list({it.get("id"): it for it in items}.values())  # id sama terbaca 2x saat list bergeser
    id_server = {it.get("id") for it in items}
    per_nama = defaultdict(list)
    for it in items:
        per_nama[norm(it.get("data1"))].append(it)
    url_audit = {id_dari_url(b.get("dokumen_url")) for b in audit} - {""}
    akhir: dict = {}
    dok: dict = {}      # kunci -> akun_login dokumen tercatat
    dok_url: dict = {}  # kunci -> URL dokumen tercatat terakhir
    for b in audit:
        k = b.get("kunci")
        if not k:
            continue
        akhir[k] = (b.get("status") or "").strip()
        if b.get("status") == mg.STATUS_DIHAPUS:
            dok.pop(k, None)
            dok_url.pop(k, None)
        elif b.get("dokumen_url") or b.get("status") == mg.STATUS_DIBUAT:
            dok[k] = (b.get("akun_login") or "").lower()
            dok_url[k] = b.get("dokumen_url") or dok_url.get(k, "")

    # DRAFT TANPA NAMA yang belum tercatat di audit: dokumen kosong yang tidak bisa
    # dicocokkan lewat nama. Selama ada satu saja, tanda "tanpa URL" TIDAK digugurkan
    # otomatis — dokumen baris itu bisa jadi salah satunya.
    draft_kosong = [it for it in items
                    if status_server(it.get("assignmentStatusAlias")) == "DRAFT"
                    and not norm(it.get("data1")) and it.get("id") not in url_audit]

    laporan, tulis = [], []
    sudah_kunci = set()  # kunci yang sama bisa muncul di dua file sumber
    digugurkan = set()   # kunci yang tanda "tanpa URL"-nya sudah digugurkan di run ini
    # id dokumen -> kunci pemiliknya menurut audit. Dua usaha BERBEDA bisa bernama dokumen
    # sama (Agenda2 baris 267 vs Agenda baris 108): dokumen milik kunci lain bukan milik baris ini.
    id_milik: dict = {}
    for b in audit:
        i = id_dari_url(b.get("dokumen_url"))
        if i and b.get("kunci") and b.get("status") != mg.STATUS_DIHAPUS:
            id_milik[i] = b["kunci"]
    for sumber, row, status_cek in sumber_rows:
        semua_docs = per_nama.get(norm(row.nama_dokumen), [])
        docs = [d for d in semua_docs if id_milik.get(d["id"], row.kunci) == row.kunci]
        dipakai_lain = len(docs) < len(semua_docs)
        terkirim = [d for d in docs if status_server(d.get("assignmentStatusAlias")) == "TERKIRIM"]
        draft = [d for d in docs if status_server(d.get("assignmentStatusAlias")) == "DRAFT"]
        st_audit = akhir.get(row.kunci, "")
        akun_audit = dok.get(row.kunci, "")
        id_tercatat = id_dari_url(dok_url.get(row.kunci, ""))
        hilang = (lengkap and akun_audit == akun and id_tercatat and id_tercatat not in id_server
                  and row.kunci not in sudah_kunci)
        if hilang:
            # Dihapus admin (Agenda1-1 baris 88, 2026-09-15): gugurkan catatannya supaya
            # main_gabungan membuat dokumen baru, bukan membuka URL yang sudah tidak ada.
            tulis.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "baris": row.baris, "kunci": row.kunci,
                "nama_usaha": row.nama_dokumen, "kbli": row["kbli"], "idsubsls": row.idsubsls,
                "idsubsls_input": subsls, "akun_ppl": row.akun_ppl, "akun_login": akun,
                "status": mg.STATUS_DIHAPUS, "dokumen_url": dok_url[row.kunci],
                "error_message": f"sinkron list API: dokumen {id_tercatat[:8]} tidak ada lagi di list (dihapus)",
            })
            st_audit, akun_audit = mg.STATUS_DIHAPUS, ""
        # Tanda "dokumen mungkin terbuat tanpa URL" menahan baris itu selamanya.
        # Kalau list server TERBUKTI utuh, tidak ada dokumen bernama ini, dan tidak
        # ada DRAFT kosong yang mencurigakan -> dokumennya memang tidak pernah ada:
        # catatannya digugurkan supaya barisnya boleh dibuat lagi.
        tanda_tanpa_url = (st_audit in mg.STATUS_TANPA_URL_SEMUA and not docs
                           and (not akun_audit or akun_audit == akun)
                           and row.kunci not in digugurkan)
        gugur = tanda_tanpa_url and lengkap and not draft_kosong
        if gugur:
            digugurkan.add(row.kunci)
            tulis.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "baris": row.baris, "kunci": row.kunci,
                "nama_usaha": row.nama_dokumen, "kbli": row["kbli"], "idsubsls": row.idsubsls,
                "idsubsls_input": subsls, "akun_ppl": row.akun_ppl, "akun_login": akun,
                "status": mg.STATUS_DIHAPUS, "dokumen_url": "",
                "error_message": (f"sinkron list API: tanda '{st_audit}' diperiksa — tidak ada dokumen "
                                  "bernama ini & tidak ada DRAFT kosong di list; catatan digugurkan, "
                                  "baris boleh dibuat lagi"),
            })
            st_audit = mg.STATUS_DIHAPUS
        if akun_audit and akun_audit != akun:
            kategori = "DI_AKUN_LAIN" + ("+GANDA_LINTAS_AKUN" if docs else "")
        elif not docs:
            kategori = "BELUM_ADA" + ("+AUDIT_BILANG_TERKIRIM" if st_audit in mg.STATUS_TERKIRIM else "")
        elif terkirim:
            kategori = "TERKIRIM"
        elif draft:
            kategori = "DRAFT"
        else:
            kategori = "LAIN"
        if len(docs) > 1:
            kategori += "+GANDA"
        if hilang:
            kategori += "+DOKUMEN_AUDIT_DIHAPUS"
        if dipakai_lain:
            kategori += "+NAMA_DIPAKAI_BARIS_LAIN"
        if st_audit == mg.STATUS_TERKUNCI and draft and not terkirim:
            kategori += "+TERKUNCI_TAPI_SERVER_DRAFT"
        if gugur:
            kategori += "+TANDA_TANPA_URL_DIGUGURKAN"
        elif tanda_tanpa_url:
            kategori += ("+TANDA_TANPA_URL_PERIKSA_MANUAL" if draft_kosong
                         else "+TANDA_TANPA_URL_LIST_TIDAK_UTUH")
        laporan.append({
            "sumber": sumber, "baris": row.baris, "kunci": row.kunci, "nama_dokumen": row.nama_dokumen,
            "cek_data": status_cek, "kategori": kategori, "status_audit": st_audit,
            "dokumen_server": " ; ".join(f"{d['id'][:8]} {d.get('assignmentStatusAlias')} "
                                         f"{jam_lokal(d.get('dateCreated'))}" for d in docs),
        })
        if kategori.startswith("DI_AKUN_LAIN") or not docs or row.kunci in sudah_kunci:
            continue
        if not terkirim and len(draft) > 1:
            continue  # dua DRAFT bernama sama: jangan menebak mana yang dipakai
        sudah_kunci.add(row.kunci)

        def baris_audit(status, doc, pesan):
            return {
                "timestamp": jam_lokal(doc.get("dateCreated")) if status == mg.STATUS_DIBUAT
                else time.strftime("%Y-%m-%d %H:%M:%S"),
                "baris": row.baris, "kunci": row.kunci, "nama_usaha": row.nama_dokumen, "kbli": row["kbli"],
                "idsubsls": row.idsubsls, "idsubsls_input": subsls, "akun_ppl": row.akun_ppl,
                "akun_login": akun, "status": status, "dokumen_url": url_entry(doc["id"], assignment_id),
                "error_message": pesan,
            }

        # Urutan: dokumen terkirim ditulis TERAKHIR supaya URL terakhir kunci ini
        # menunjuk dokumen terkirim (dokumen_per_kunci: URL terakhir menang).
        dicatat = False
        for d in draft + terkirim:
            # `hilang`: dokumen yang ditunjuk audit sudah tidak ada (mis. dokumen GANDA yang
            # dihapus admin lewat hapus_ganda) -> dokumen bernama sama yang TERSISA dicatat
            # ulang walau id-nya pernah tercatat. Tanpa ini DOKUMEN_DIHAPUS di atas membuat
            # baris ini tak berdokumen & run berikutnya MEMBUAT dokumen baru = ganda lagi.
            if d["id"] not in url_audit or hilang:
                dicatat = True
                tulis.append(baris_audit(mg.STATUS_DIBUAT, d, f"sinkron list API ({sumber}): dokumen dibuat di "
                                                              f"luar audit ini, status {d.get('assignmentStatusAlias')}"))
        # Status TERAKHIR per kunci yang menentukan --lewati-selesai: DOKUMEN_DIBUAT
        # yang baru ditulis menimpa status terkirim lama -> ulangi status terkirimnya.
        if terkirim and (st_audit not in mg.STATUS_TERKIRIM or dicatat):
            tulis.append(baris_audit("TERKIRIM_TERVERIFIKASI", terkirim[0],
                                     f"sinkron list API: {terkirim[0].get('assignmentStatusAlias')}"
                                     + (f" ({len(docs)} dokumen bernama sama)" if len(docs) > 1 else "")))
        elif not terkirim and draft and st_audit in mg.STATUS_TERKIRIM:
            # DOKUMEN_TERKUNCI dikecualikan: itu bukan "audit salah kira", tapi BUKTI
            # dari UI bahwa dokumennya read-only (kodepos disabled 3 dtk penuh).
            # Menurunkannya jadi DRAFT_DI_SERVER bikin ping-pong: sinkron menurunkan
            # -> batch membukanya -> tetap terkunci -> DOKUMEN_TERKUNCI lagi, tiap run
            # (baris 232, 2026-09-23: 4 putaran, dokumen tidak berubah sama sekali).
            if st_audit != mg.STATUS_TERKUNCI:
                tulis.append(baris_audit(STATUS_DRAFT_SERVER, draft[0],
                                         f"audit '{st_audit}' tapi server masih DRAFT — kirim ulang lewat URL"))
        # Ditulis PALING BELAKANG: status terakhir per kunci yang menentukan
        # apakah baris ini dikerjakan lagi.
        galat_draft = next((d for d in draft if int(d.get("sumError") or 0) > 0), None)
        if galat_draft and not terkirim and (st_audit != STATUS_DRAFT_GALAT or dicatat):
            tulis.append(baris_audit(
                STATUS_DRAFT_GALAT, galat_draft,
                f"server menandai {galat_draft.get('sumError')} galat "
                f"(jawaban bersih {galat_draft.get('sumClean')}) — isi ulang lewat URL lalu kirim"))
    dikenali_nama = {norm(r.nama_dokumen) for _, r, _ in sumber_rows}
    tak_dikenal = [it for it in items if norm(it.get("data1")) not in dikenali_nama]
    return laporan, tulis, tak_dikenal


def ambil_items(akun: str, assignment_id: str) -> list[dict]:
    from playwright.sync_api import sync_playwright
    from inti.fasih_web import FasihWebSession
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        sess = FasihWebSession(browser.new_context().new_page())
        sess.login(akun, FIXED_PASSWORD)
        aktif = (sess.akun_api.get("email") or "").lower()
        if aktif != akun:
            raise RuntimeError(f"AKUN TIDAK TERVERIFIKASI: diminta '{akun}', terbaca '{aktif or '-'}'")
        items = sess.daftar_dokumen_api(assignment_id)
        lengkap = sess.daftar_dokumen_lengkap
        if not lengkap:
            print("⚠️ List berubah selama dibaca (ada proses lain yang sedang input dgn akun ini?) — "
                  "hasil bisa kurang; ulangi sinkron saat akun tidak dipakai.")
        # Sengaja TANPA logout: logout mencabut sesi akun yang sama di proses lain.
        browser.close()
    return items, lengkap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", action="append", required=True, help="xlsx/csv sheet gabungan (boleh berulang)")
    ap.add_argument("--format", choices=("standar", "tahap2"), default="standar",
                    help="Format SEMUA --sumber: standar (input_usaha.xlsx) / tahap2 (bahan/input_tahap2.xlsx)")
    ap.add_argument("--akun-tunggal", required=True)
    ap.add_argument("--subsls-tunggal", required=True)
    ap.add_argument("--assignment-id", default=ASSIGNMENT_ID_GABUNGAN)
    ap.add_argument("--dari-json", help="pakai daftar dokumen hasil unduhan sebelumnya (tanpa login)")
    ap.add_argument("--simpan-json", default="", help="default: list_api_<akun>.json")
    ap.add_argument("--tulis", action="store_true", help="tambahkan hasil sinkron ke audit_log_gabungan.csv")
    args = ap.parse_args()
    akun = args.akun_tunggal.strip().lower()

    kunci_akun = None
    if args.tulis:
        kunci_akun = mg.kunci_proses_akun(akun)
        if kunci_akun is None:
            print(f"❌ Akun {akun} sedang dipakai main_gabungan — tunggu selesai sebelum --tulis.", file=sys.stderr)
            return 2
    try:
        if args.dari_json:
            # Kelengkapan unduhan lama tidak diketahui -> DOKUMEN_DIHAPUS tidak pernah ditulis.
            items, lengkap = json.loads(Path(args.dari_json).read_text(encoding="utf-8")), False
        else:
            items, lengkap = ambil_items(akun, args.assignment_id)
            simpan = Path(args.simpan_json or f"list_api_{akun.replace('@', '_at_')}.json")
            simpan.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"Daftar dokumen disimpan: {simpan}")

        sumber_rows = []
        for sumber in args.sumber:
            rows, cek = mg.muat_sumber(sumber, args.format, mode_satu_subsls=True,
                                       izinkan_tanpa_koordinat=mg.koordinat_otomatis(None, args.format))
            sumber_rows += [(sumber, r, cek[r.baris].status) for r in rows]
        laporan, tulis, tak_dikenal = rencana_sinkron(sumber_rows, items, akun, args.subsls_tunggal,
                                                      args.assignment_id, mg._baca_audit(), lengkap)

        print(f"\n=== {len(items)} dokumen di list {akun}: "
              f"{dict(Counter(status_server(i.get('assignmentStatusAlias')) for i in items))} ===")
        for sumber in args.sumber:
            bagian = [l for l in laporan if l["sumber"] == sumber]
            print(f"\n--- {sumber}: {len(bagian)} baris ---")
            for kat, n in Counter(l["kategori"] for l in bagian).most_common():
                print(f"  {n:4d}  {kat}")
            for judul, syarat in (
                    ("BELUM ADA di server & data SIAP", lambda l: l["kategori"] == "BELUM_ADA" and mg.hasil_ok(l["cek_data"])),
                    ("BELUM ADA & data belum lolos cek", lambda l: l["kategori"] == "BELUM_ADA" and not mg.hasil_ok(l["cek_data"])),
                    ("DRAFT (belum terkirim)", lambda l: l["kategori"].startswith("DRAFT")),
                    ("GANDA", lambda l: "GANDA" in l["kategori"]),
                    ("Audit bilang terkirim, server tidak", lambda l: "AUDIT_BILANG" in l["kategori"]
                     or (l["kategori"].startswith("DRAFT") and l["status_audit"] in mg.STATUS_TERKIRIM))):
                pilih = [l for l in bagian if syarat(l)]
                if pilih:
                    print(f"  {judul} ({len(pilih)}): " + ", ".join(
                        f"{l['baris']}" + (f" [{l['cek_data']}]" if l['cek_data'] != 'SIAP' else "") for l in pilih))
        if tak_dikenal:
            print(f"\nDokumen server yang tidak cocok dgn baris mana pun ({len(tak_dikenal)}):")
            for it in tak_dikenal:
                print(f"  {it['id'][:8]} {it.get('assignmentStatusAlias')} {jam_lokal(it.get('dateCreated'))} | {it.get('data1')}")

        with LAPORAN_PATH.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(laporan[0].keys()) if laporan else ["sumber"])
            w.writeheader()
            w.writerows(laporan)
        print(f"\nRincian per baris: {LAPORAN_PATH}")

        print(f"\nAkan ditambahkan ke audit: {len(tulis)} baris "
              f"{dict(Counter(t['status'] for t in tulis))}")
        if args.tulis:
            for t in tulis:
                mg.append_audit(t)
            print(f"✅ Ditulis ke {mg.AUDIT_LOG_PATH}.")
        elif tulis:
            print("(belum ditulis — ulangi dgn --tulis, bisa pakai --dari-json supaya tidak login lagi)")
        return 0
    finally:
        if kunci_akun is not None:
            kunci_akun.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
