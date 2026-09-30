#!/usr/bin/env python3
"""
terapkan_daftar_draft.py — cocokkan DAFTAR DRAFT dari fasih-sm (tabel Data akun admin, disaring
status DRAFT + mode PAPI, diunduh .xlsx) dgn sheet & audit semua batch, lalu perbarui audit supaya
bot input (jalankan.py / sisir.py) mengerjakan draft itu lagi.

Kenapa perlu (2026-09-29): 23 draft PAPI tidak pernah disentuh bot lagi karena audit mencatatnya
tuntas — TERKIRIM_BELUM_TERVERIFIKASI (toast "berhasil dikirim" tapi server tetap DRAFT) atau
DOKUMEN_TERKUNCI — dan --sinkron-dulu tidak melihatnya (list akun > 1.000 dokumen terpotong server).

Golongan per draft (kolom `golongan` di CSV):
  TUNTAS_PALSU        audit terkirim-belum-terverifikasi, petugas = akun audit -> --tulis menambah
                      DRAFT_DI_SERVER (URL & akun sama) -> baris dikerjakan lagi (buka URL, kirim)
  TERKUNCI            audit DOKUMEN_TERKUNCI (form read-only saat dibuka). TERBUKTI 2026-09-29: detail
                      dokumen (ikon info) = SUBMITTED, hanya tabel Data/list yang masih "draft" (basi)
                      -> sudah TUNTAS, tidak ditulis. --termasuk-terkunci hanya kalau detail = DRAFT.
  SUDAH_ANTRE         audit sudah bukan status tuntas (draft/galat/error) -> tidak perlu apa-apa
  AKUN_BEDA           petugas saat ini != akun di audit -> kemungkinan dokumen GANDA / dipindah
                      petugas. Tidak ditulis; periksa manual (lihat CSV)
  DI_LUAR_AUDIT       nama cocok baris sheet yang belum punya dokumen di audit -> jalankan
                      sinkron (jalankan.py --sinkron-dulu / sinkron_list --tulis) akun itu
  TIDAK_DI_SHEET      nama tidak ada di sheet mana pun (mis. draft kosong "-") -> admin
  AMBIGU              nama cocok > 1 baris dgn akun sama -> tidak ditebak
  SESUDAH_EKSPOR      bot sudah mengerjakan baris ini SESUDAH ekspor diunduh (mtime berkas) -> ekspor basi,
                      tidak ditulis (unduh ekspor baru utk memeriksanya lagi)
  DITOLAK_PML         baris ekspor berstatus REJECTED (ekspor boleh berisi draft & rejected) -> --tulis
                      menambah DITOLAK_PML + sidik isi baris sheet. Bot (jalankan/sisir) baru mengisi ulang &
                      mengirim SESUDAH baris itu dikoreksi di sheet (mesin.menunggu_koreksi); paksa kirim ulang
                      apa adanya: jalankan.py --kirim-ulang-ditolak

Tanpa --tulis = laporan saja (input_usaha/hasil/terapkan_daftar_draft.csv).

CONTOH:
    python input_usaha/terapkan_daftar_draft.py --daftar "C:/Users/<user>/Downloads/daftar_draft_papi.xlsx" ^
        --daftar-sheet bahan/sisir_sheet.txt
    python input_usaha/terapkan_daftar_draft.py ... --tulis
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from inti import lokasi  # noqa: E402

LAPORAN = lokasi.HASIL_INPUT / "terapkan_daftar_draft.csv"

G_PALSU, G_KUNCI, G_ANTRE = "TUNTAS_PALSU", "TERKUNCI", "SUDAH_ANTRE"
G_DITOLAK = "DITOLAK_PML"
G_BASI = "SESUDAH_EKSPOR"   # bot sudah mengerjakan baris ini SESUDAH ekspor diunduh -> ekspor basi utk baris ini
G_AKUN, G_LUAR, G_TIDAK, G_AMBIGU = "AKUN_BEDA", "DI_LUAR_AUDIT", "TIDAK_DI_SHEET", "AMBIGU"
STATUS_DRAFT_SERVER = "DRAFT_DI_SERVER"   # = sinkron_list.STATUS_DRAFT_SERVER


def baku(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


# ---------------------------------------------------------------- ekspor fasih-sm

@dataclass
class Draft:
    kode: str
    nama: str
    petugas: str
    status: str
    mode: str


def baca_daftar_draft(path: str) -> list[Draft]:
    """Ekspor tabel Data fasih-sm (.xlsx/.csv). Kolom dicari lewat JUDUL (Kode Identitas, Nama …,
    Status, Mode, Petugas Saat Ini). Hanya status draft + mode PAPI yang dipakai."""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8-sig", newline="") as f:
            baris = list(csv.reader(f))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        baris = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    if not baris:
        raise SystemExit(f"{path}: kosong")
    judul = [baku(x) for x in baris[0]]

    def kolom(*awalan):
        for i, j in enumerate(judul):
            if any(j.startswith(a) for a in awalan):
                return i
        raise SystemExit(f"{path}: kolom {awalan[0]!r} tidak ada (judul: {baris[0]})")

    ik, inm, ist, imd, ipt = (kolom("KODE IDENTITAS"), kolom("NAMA"), kolom("STATUS"), kolom("MODE"),
                             kolom("PETUGAS SAAT INI"))
    out = []
    for r in baris[1:]:
        if not r or not any(r):
            continue
        sel = lambda i: str(r[i] if i < len(r) and r[i] is not None else "").strip()  # noqa: E731
        d = Draft(sel(ik), sel(inm), sel(ipt).lower(), sel(ist).lower(), sel(imd).upper())
        if d.status.startswith(("draft", "reject")) and d.mode == "PAPI":
            out.append(d)
    return out


def nama_dari_kode(kode: str) -> str:
    """'5108060006000224 - Nama Usaha' -> 'NAMA USAHA'."""
    m = re.match(r"^\s*\d{16}\s*-\s*(.+)$", kode or "")
    return baku(m.group(1)) if m else ""


# ---------------------------------------------------------------- indeks sheet + audit

@dataclass
class Calon:
    sheet: object          # sisir.Sheet
    row: object            # GabunganRow
    status: str
    dokumen: tuple | None  # (akun_login, idsubsls_input, url)
    terakhir: str = ""     # timestamp baris audit TERAKHIR kunci ini (bot mengerjakannya kapan)


def indeks_sheet(sheets) -> dict:
    """{NAMA BAKU: [Calon]} dari nama dokumen sheet + semua nama_usaha audit kunci itu."""
    import input_usaha.mesin as mg
    idx: dict = defaultdict(list)
    for s in sheets:
        mg.pakai_audit(s.audit or mg.AUDIT_BAWAAN)
        rows, hasil = mg.muat_sumber(s.sumber, "tahap2", True, "", True, True)
        aud = mg._baca_audit()
        st = mg.status_terakhir_dari(aud)
        dok = mg.dokumen_dari(aud)
        nama_aud = defaultdict(set)
        terakhir: dict = {}
        for b in aud:
            if b.get("nama_usaha") and b.get("kunci"):
                nama_aud[b["kunci"]].add(baku(b["nama_usaha"]))
            if b.get("kunci"):
                terakhir[b["kunci"]] = max(terakhir.get(b["kunci"], ""), (b.get("timestamp") or "")[:19])
        for r in rows:
            c = Calon(s, r, st.get(r.kunci, ""), dok.get(r.kunci), terakhir.get(r.kunci, ""))
            for n in {baku(r.nama_dokumen)} | nama_aud.get(r.kunci, set()):
                if nama_berarti(n):
                    idx[n].append(c)
    return idx


def golongkan(d: Draft, calon: list[Calon], jam_ekspor: str = "") -> tuple[str, Calon | None, str]:
    """-> (golongan, calon terpilih, catatan). Fungsi murni (tanpa berkas)."""
    import input_usaha.mesin as mg
    if not calon:
        return G_TIDAK, None, ""
    # satu baris bisa terdaftar lewat dua nama (sheet & audit) -> unik per (sheet, baris)
    unik = list({(c.sheet.sumber, c.row.baris): c for c in calon}.values())
    ber_dok = [c for c in unik if c.dokumen]
    sama = [c for c in ber_dok if (c.dokumen[0] or "").lower() == d.petugas]
    if len(sama) > 1:
        return G_AMBIGU, None, "; ".join(f"{c.sheet.label}:{c.row.baris}" for c in sama)
    if len(sama) == 1:
        c = sama[0]
        # Ekspor basi utk baris ini: bot sudah membuka/mengirimnya SESUDAH ekspor diunduh (2026-09-29:
        # ekspor 17:06 dipakai lagi -> 6 draft yang sudah dikerjakan ditandai ulang -> dibuka ulang).
        if jam_ekspor and c.terakhir > jam_ekspor and c.status != mg.STATUS_DITOLAK:
            return G_BASI, c, f"audit {c.terakhir} > ekspor {jam_ekspor}"
        if d.status.startswith("reject"):
            return (G_ANTRE if c.status == mg.STATUS_DITOLAK else G_DITOLAK), c, ""
        if c.status == mg.STATUS_TERKUNCI:
            return G_KUNCI, c, ""
        if c.status in mg.STATUS_TERKIRIM - {mg.STATUS_DIPINDAH}:
            return G_PALSU, c, ""
        return G_ANTRE, c, ""
    if ber_dok:
        return G_AKUN, ber_dok[0], "akun audit " + ", ".join(
            f"{c.sheet.label}:{c.row.baris}={c.dokumen[0]} ({c.status})" for c in ber_dok)
    if len(unik) == 1:
        return G_LUAR, unik[0], ""
    return G_AMBIGU, None, "; ".join(f"{c.sheet.label}:{c.row.baris}" for c in unik)


def nama_berarti(n: str) -> bool:
    """Nama "-"/kosong (draft kosong, catatan audit tanpa nama) tidak boleh dipakai mencocokkan."""
    return len(re.findall(r"[A-Z]", n)) >= 3


def cocokkan(drafts: list[Draft], idx: dict, jam_ekspor: str = "") -> list[tuple[Draft, str, Calon | None, str]]:
    out = []
    for d in drafts:
        calon = [c for n in (baku(d.nama), nama_dari_kode(d.kode)) if nama_berarti(n) for c in idx.get(n, [])]
        out.append((d, *golongkan(d, calon, jam_ekspor)))
    return out


def baris_audit(c: Calon, d: Draft, pesan: str, status: str = STATUS_DRAFT_SERVER) -> dict:
    r = c.row
    return {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "baris": r.baris, "kunci": r.kunci,
            "nama_usaha": r.nama_dokumen, "kbli": r["kbli"], "idsubsls": r.idsubsls,
            "idsubsls_input": c.dokumen[1], "akun_ppl": r.akun_ppl, "akun_login": c.dokumen[0],
            "status": status, "dokumen_url": c.dokumen[2], "error_message": pesan}


def terapkan(daftar: str, sheets, tulis: bool, termasuk_terkunci: bool = False) -> list:
    """Cocokkan ekspor fasih-sm dgn sheet+audit, cetak & tulis laporan CSV, dan (tulis=True) tambahkan
    DRAFT_DI_SERVER / DITOLAK_PML ke audit masing-masing sheet. -> hasil cocokkan() (dipakai sisir.py)."""
    import input_usaha.mesin as mg
    from collections import Counter
    drafts = baca_daftar_draft(daftar)
    print(f"{len(drafts)} dokumen PAPI draft/rejected di {daftar}")
    jam = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(Path(daftar).stat().st_mtime))
    print(f"Ekspor diunduh {jam} — baris yang dikerjakan bot sesudah jam itu tidak ditandai ulang ({G_BASI}).")
    hasil = cocokkan(drafts, indeks_sheet(sheets), jam)
    ditulis = defaultdict(list)   # audit -> baris audit
    with lokasi.siapkan(LAPORAN).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["golongan", "petugas", "nama_draft", "sheet", "baris", "kunci", "status_audit",
                    "akun_audit", "dokumen_url", "catatan", "tindakan"])
        for d, gol, c, cat in hasil:
            perlu = gol in (G_PALSU, G_DITOLAK) or (gol == G_KUNCI and termasuk_terkunci)
            status_baru = mg.STATUS_DITOLAK if gol == G_DITOLAK else STATUS_DRAFT_SERVER
            tindakan = (status_baru + (" (ditulis)" if tulis else " (akan ditulis)")) if perlu else ""
            if perlu and tulis:
                if gol == G_DITOLAK:
                    pesan = mg.pesan_ditolak(f"daftar fasih-sm: REJECTED (petugas {d.petugas}), audit '{c.status}'",
                                             getattr(c.row, "sidik_sumber", ""))
                else:
                    pesan = (f"daftar draft fasih-sm: server DRAFT (petugas {d.petugas}) padahal audit "
                             f"'{c.status}' — kirim ulang lewat URL")
                ditulis[c.sheet.audit or ""].append(baris_audit(c, d, pesan, status_baru))
            w.writerow([gol, d.petugas, d.nama, c.sheet.label if c else "", c.row.baris if c else "",
                        c.row.kunci if c else "", c.status if c else "",
                        (c.dokumen or ("",))[0] if c else "", (c.dokumen or ("", "", ""))[2] if c else "",
                        cat, tindakan])
            if gol != G_ANTRE:
                print(f"  {gol:<15} {d.petugas:<30} {d.nama[:48]:<48} "
                      + (f"{c.sheet.label}:{c.row.baris} [{c.status}]" if c else "") + (f"  {cat}" if cat else ""))
    print("Ringkasan daftar fasih-sm:", dict(Counter(g for _, g, _, _ in hasil)))
    for audit, baris in ditulis.items():
        mg.pakai_audit(audit or mg.AUDIT_BAWAAN)
        mg.append_audit_banyak(baris)
        print(f"✍ {len(baris)} baris ({dict(Counter(b['status'] for b in baris))}) ditulis ke {mg.AUDIT_LOG_PATH}")
    print(f"Laporan: {LAPORAN}")
    return hasil


def main() -> int:
    from input_usaha import sisir
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daftar", required=True, help="ekspor tabel Data fasih-sm (.xlsx/.csv) status draft/rejected")
    ap.add_argument("--daftar-sheet", default=str(sisir.DAFTAR_SHEET_BAWAAN),
                    help="TXT '<sheet> [<audit>]' (sama dgn sisir.py)")
    ap.add_argument("--termasuk-terkunci", action="store_true",
                    help="DOKUMEN_TERKUNCI juga ditulis DRAFT_DI_SERVER (hanya kalau detail dokumen = DRAFT)")
    ap.add_argument("--tulis", action="store_true", help="tulis ke audit (tanpa ini laporan saja)")
    args = ap.parse_args()
    lokasi.cek_struktur_lama()
    terapkan(args.daftar, sisir.baca_daftar_sheet(args.daftar_sheet), args.tulis, args.termasuk_terkunci)
    if not args.tulis:
        print("(laporan saja — tambahkan --tulis utk memperbarui audit; sisir.py --daftar-draft melakukannya sendiri)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
