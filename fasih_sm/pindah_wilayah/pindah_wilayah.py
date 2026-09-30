#!/usr/bin/env python3
"""
pindah_wilayah.py — siapkan pemindahan dokumen input usaha dari subsls WADAH ke subsls aslinya
(kolom "5" sheet) di fasih-sm, lalu catat hasilnya ke audit.

fasih-sm menolak Playwright, jadi pemindahannya dijalankan Console Chrome biasa
(pindah_wilayah_console.js). File ini OFFLINE: membaca sheet + audit, menyusun target, membaginya
ke beberapa akun admin, dan menulis `hasil/pindah_wilayah_console*.siap.js`. Tanpa browser/VPN.

TARGET = baris sheet yang punya dokumen: ID di kolom "ID Dokumen FASIH" sheet + URL dokumen di audit
batch-nya (dua-duanya dikirim; Console memakai yang masih hidup, dua-duanya hidup = DOKUMEN_GANDA).
Audit tiap sheet dipilih OTOMATIS: berkas audit di audit/** (tanpa audit/pc & .bak) yang paling banyak
mengenal baris sheet itu; `--audit` memaksa satu audit utk semua sheet.

LANGKAH
-------
    python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber bahan/input_tahap2.xlsx \
        --sumber bahan/input_tahap2_22.xlsx --sumber bahan/input_tahap2_23.xlsx \
        --bagi 3 --daftar-tujuan bahan/tujuan_pindah.txt --console
  -> hasil/pindah_wilayah_console.bagian-1-dari-3.siap.js dst. Tiap berkas ditempel oleh SATU akun admin
     (browser/PC sendiri) di Console halaman Data survei:
        await pindahWilayah.jalankan({mode: "pindah"})
        pindahWilayah.unduh()          -> simpan CSV-nya di folder audit/
    python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat            (rencana)
    python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat --tulis    (tulis DIPINDAH_WILAYAH ke audit)

Sisa sesudah run pertama (unduhan Console sudah di audit/):
    python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber ... --hanya-sisa --alokasi bahan/alokasi_wilayah.csv --console
  --hanya-sisa: target yang dokumennya sudah tuntas ke tujuan yang sama (menurut unduhan) tidak diikutkan.
  --alokasi: CSV/xlsx berkolom idsubsls, Email PML, Email PPL -> dipakai Console HANYA kalau server punya
  > 1 Pengawas/Pencacah di subsls tujuan (ketetapan user 2026-09-29).

Pengaturan beban (bawaan di Console, bisa juga diubah saat jalankan({...})):
  --per-kirim 50 (dokumen per request), --cek-sesudah 3 (detail diperiksa per request), --jeda-kirim 1
  (detik sesudah tiap request pindah), --jeda-baca 0.1 (detik antar-halaman daftar), --jarak-request 0.25.
  Jeda naik otomatis (x2 s.d. x8) tiap kena 429/5xx.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inti import lokasi  # noqa: E402
from inti.config import ASSIGNMENT_ID_GABUNGAN, KODE_KAB  # noqa: E402
from inti.id_dokumen import POLA_ID, url_entry  # noqa: E402
from inti.kunci import pid_hidup  # noqa: E402
import input_usaha.mesin as mg  # noqa: E402
from input_usaha.sinkron_list import id_dari_url, norm  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

KONSOL_TEMPLATE = Path(__file__).resolve().parent / "pindah_wilayah_console.js"
HASIL = lokasi.hasil("fasih_sm", "pindah_wilayah")
KONSOL_SIAP = HASIL / "pindah_wilayah_console.siap.js"
POLA_KONSOL_BAGIAN = "pindah_wilayah_console.bagian-*.siap.js"
PEMBAGIAN_CSV = HASIL / "pembagian_pindah_wilayah.csv"
# Unduhan pindahWilayah.unduh() — catatan yang tidak bisa dibuat ulang -> disimpan di audit/.
POLA_HASIL_CONSOLE = str(lokasi.AUDIT / "**" / "audit_pindah_wilayah*.csv")
PENANDA = {
    "target": "/*__TARGET__*/[]", "sumber": "/*__SUMBER__*/[]", "asal": "/*__ASAL__*/[]",
    "konfig": "/*__KONFIG__*/{}", "kode_kab": '/*__KODE_KAB__*/"5108"',
}
POLA_KODE = re.compile(rf"{re.escape(KODE_KAB)}\d{{12}}")
# Status Console yang berarti dokumen SUDAH di subsls tujuan (urut makin kuat buktinya).
PERINGKAT_TUNTAS = {"SUDAH_DI_TUJUAN": 1, "DIPINDAH_SERVER_OK": 2, "DIPINDAH_TERVERIFIKASI": 3}
MAKS_PER_KIRIM = 50


# ----------------------------------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------------------------------
def baca_csv(path: Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def audit_kandidat() -> list[Path]:
    """Audit input yang dipakai bekerja: audit/**/audit_log_gabungan*.csv, TANPA cadangan .bak-* dan
    tanpa audit/pc/** (kiriman PC lain sebelum digabung — bukan audit yang dijalankan)."""
    pc = (lokasi.AUDIT / "pc").resolve()
    return [f for f in lokasi.cari(lokasi.AUDIT / "**" / "audit_log_gabungan*.csv")
            if ".bak-" not in f.name and pc not in f.resolve().parents]


def pilih_audit(kunci_sheet: set[str], audits: dict[Path, list[dict]]) -> tuple[Path | None, int]:
    """Audit yang paling banyak mengenal DOKUMEN baris sheet ini -> (path, jumlah); (None, 0) = tidak ada.
    Seri -> path terurut pertama (isinya sama utk sheet itu, mis. audit bawaan & salinannya per batch)."""
    terbaik: tuple[Path | None, int] = (None, 0)
    for path in sorted(audits):
        n = len(kunci_sheet & set(mg.dokumen_dari(audits[path])))
        if n > terbaik[1]:
            terbaik = (path, n)
    return terbaik


# ----------------------------------------------------------------------------------------------
# Target
# ----------------------------------------------------------------------------------------------
def cocok_tujuan(kode: str, awalan: list[str]) -> bool:
    return not awalan or any(kode.startswith(a) for a in awalan)


def bangun_target(sheet: list[tuple[str, list, list[dict]]], dari: int | None = None, sampai: int | None = None,
                  tujuan: list[str] | None = None, asal_tambahan: list[str] | None = None):
    """Fungsi murni. `sheet` = [(nama berkas, rows loader ber-id_dokumen, baris audit batch itu)].
    -> (target[], sumber[], asal[], masalah[(sumber, baris, pesan)], ringkasan Counter).
    Target: {k: kunci, s: indeks sumber, b: baris, n: nama dokumen, na: [nama lama audit], t: tujuan,
    ids: [ID sheet + ID audit]}. Baris tanpa ID sama sekali = belum punya dokumen -> bukan target."""
    target, masalah, sumber = [], [], []
    ringkasan = Counter()
    asal = {a.strip() for a in (asal_tambahan or []) if a.strip()}
    for s_idx, (nama, rows, audit) in enumerate(sheet):
        sumber.append(Path(nama).name)
        dok = mg.dokumen_dari(audit)
        nama_audit = defaultdict(set)
        asal_kunci = defaultdict(set)
        for b in audit:
            k = b.get("kunci")
            if not k:
                continue
            if b.get("nama_usaha"):
                nama_audit[k].add(norm(b["nama_usaha"]))
            kode = (b.get("idsubsls_input") or "").strip()
            if b.get("status") != mg.STATUS_DIPINDAH and POLA_KODE.fullmatch(kode):
                asal_kunci[k].add(kode)
        per_kunci: dict[str, dict] = {}
        for row in rows:
            if (dari is not None and row.baris < dari) or (sampai is not None and row.baris > sampai):
                continue
            if not POLA_KODE.fullmatch(row.idsubsls or ""):
                masalah.append((sumber[-1], row.baris, f"idsubsls tujuan '{row.idsubsls}' bukan 16 digit berawalan {KODE_KAB}"))
                continue
            if not cocok_tujuan(row.idsubsls, tujuan or []):
                ringkasan["di_luar_saringan_tujuan"] += 1
                continue
            id_sheet = getattr(row, "id_dokumen", "") or ""
            id_audit = id_dari_url((dok.get(row.kunci) or ("", "", ""))[2])
            ids = {i for i in (id_sheet, id_audit) if i}
            if not ids:
                ringkasan["belum_ada_dokumen"] += 1
                continue
            if id_sheet and id_audit and id_sheet != id_audit:
                ringkasan["id_sheet_beda_audit"] += 1
            if row.kunci in per_kunci:        # baris identik (kunci sama) dalam satu sheet
                t = per_kunci[row.kunci]
                t["ids"] = sorted(set(t["ids"]) | ids)
                ringkasan["baris_kembar_digabung"] += 1
                continue
            n = norm(row.nama_dokumen)
            t = {"k": row.kunci, "s": s_idx, "b": row.baris, "n": n, "t": row.idsubsls, "ids": sorted(ids)}
            lama = sorted(nama_audit.get(row.kunci, set()) - {n, ""})
            if lama:
                t["na"] = lama
            per_kunci[row.kunci] = t
            asal |= asal_kunci.get(row.kunci, set())
        target += per_kunci.values()
        ringkasan[f"target:{sumber[-1]}"] = len(per_kunci)
    for t in target:
        if len(t["ids"]) > 1:
            ringkasan["target_2_id"] += 1
    return target, sumber, sorted(asal), masalah, ringkasan


def bagi_target(target: list[dict], n: int) -> list[list[dict]]:
    """Bagi target ke `n` akun: SATU subsls tujuan selalu utuh di satu bagian (rombongan & cek petugas
    tujuan tidak pernah dikerjakan dua akun), beban (jumlah dokumen) seimbang — terbesar dulu ke bagian
    teringan. Deterministik. Tiap bagian urut tujuan, sumber, baris."""
    n = max(1, n)
    per_tujuan: dict[str, list[dict]] = defaultdict(list)
    for t in target:
        per_tujuan[t["t"]].append(t)
    bagian: list[list[dict]] = [[] for _ in range(n)]
    beban = [0] * n
    for _kode, daftar in sorted(per_tujuan.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        i = min(range(n), key=lambda j: (beban[j], j))
        bagian[i] += daftar
        beban[i] += len(daftar)
    for b in bagian:
        b.sort(key=lambda t: (t["t"], t["s"], t["b"]))
    return bagian


def baca_alokasi(path: Path) -> dict[str, list[str]]:
    """Alokasi petugas per subsls: {idsubsls: [email PML, email PPL]} dari CSV/xlsx berjudul idsubsls,
    Email PML, Email PPL (huruf besar/kecil bebas). Baris tanpa email / kode tidak valid dilewati."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        sel = list(openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True))
        judul, isi = [str(x or "").strip().lower() for x in sel[0]], sel[1:]
    else:
        with path.open(encoding="utf-8-sig", newline="") as f:
            sel = list(csv.reader(f))
        judul, isi = [x.strip().lower() for x in sel[0]], sel[1:]
    try:
        i_kode, i_pml, i_ppl = judul.index("idsubsls"), judul.index("email pml"), judul.index("email ppl")
    except ValueError:
        raise SystemExit(f"⛔ {path}: butuh kolom idsubsls, Email PML, Email PPL (ada: {judul})")
    hasil = {}
    for r in isi:
        r = [str(x or "").strip() for x in r] + [""] * len(judul)
        kode, pml, ppl = r[i_kode], r[i_pml].lower(), r[i_ppl].lower()
        if POLA_KODE.fullmatch(kode) and (pml or ppl):
            hasil[kode] = [pml, ppl]
    return hasil


def id_tuntas(unduhan: list[dict]) -> set[tuple[str, str]]:
    """(id dokumen, tujuan) yang menurut unduhan Console sudah di subsls tujuan."""
    return {(h["id"], h["tujuan"]) for h in pilih_hasil(unduhan)}


def saring_sisa(target: list[dict], tuntas: set[tuple[str, str]]) -> tuple[list[dict], int]:
    """Buang target yang salah satu ID-nya sudah tuntas ke tujuan yang SAMA (tujuan berubah -> tetap target)."""
    sisa = [t for t in target if not any((i, t["t"]) in tuntas for i in t["ids"])]
    return sisa, len(target) - len(sisa)


def tambah_sisa_wadah(sisa: list[dict], sheet: list[tuple[str, list, list[dict]]], audits: dict[Path, list[dict]],
                      target: list[dict], target_semua: list[dict], tuntas: set[tuple[str, str]], sumber: list[str],
                      label: str = "sisa_wadah") -> tuple[list[dict], Counter, list[tuple]]:
    """Fungsi murni. `sisa` = unduhan pindahWilayah.sisaWadah() (id, kode, status_server, nama): dokumen yang masih di
    wadah tapi tidak dimiliki target. Tiap dokumen dicarikan barisnya: kunci audit yang menunjuk dokumen itu -> baris
    sheet; tidak ada -> nama server = nama dokumen baris. Keputusan (ketetapan user 2026-09-30):
      - SUDAH_DI_TEMPAT: tujuan baris = subsls dokumen sekarang -> tidak dipindah;
      - KEMBAR: kunci baris itu sudah punya dokumen LAIN yang tuntas di tujuan -> TIDAK dipindah (dibiarkan di wadah);
      - PENGGANTI: baris itu tanpa dokumen hidup (ID sheet terhapus / tanpa ID) -> id ditambahkan ke target baris
        (target baru kalau belum ada);
      - AUDIT_SAJA: tidak ada di sheet mana pun (mis. dokumen sheet Agenda lama) tapi semua baris audit dokumen itu
        sepakat SATU idsubsls tujuan yang valid -> target baru (tujuan = idsubsls audit);
      - TUJUAN_AMBIGU / TAK_DIKENAL -> dilaporkan saja.
    -> (target baru [salinan target + tambahan], Counter kategori, rincian [(kategori, id, nama, tujuan, keterangan)])."""
    dimiliki = {i for t in target_semua for i in t["ids"]} | {i for t in target for i in t["ids"]}
    per_kunci, per_nama = defaultdict(list), defaultdict(list)
    for s_idx, (_nama, rows, _audit) in enumerate(sheet):
        for r in rows:
            per_kunci[r.kunci].append((s_idx, r))
            per_nama[norm(r.nama_dokumen)].append((s_idx, r))
    aud_id: dict[str, list[dict]] = defaultdict(list)
    for rows in audits.values():
        for b in rows:
            i = id_dari_url(b.get("dokumen_url") or "")
            if i:
                aud_id[i].append(b)
    ids_kunci = defaultdict(set)
    for t in target_semua:
        ids_kunci[t["k"]].update((i, t["t"]) for i in t["ids"])
    baru = [dict(t, ids=list(t["ids"])) for t in target]
    per_k_baru = {t["k"]: t for t in baru}
    hitung, rincian = Counter(), []
    for d in sisa:
        i, kode = (d.get("id") or "").strip().lower(), (d.get("kode") or "").strip()
        nama = [n for n in (x.strip() for x in (d.get("nama") or "").split(" / ")) if n]
        if not POLA_ID.match(i) or i in dimiliki:
            hitung["SUDAH_TARGET"] += 1
            continue
        kunci = {b.get("kunci") for b in aud_id.get(i, []) if b.get("kunci")}
        baris = [x for k in kunci for x in per_kunci.get(k, [])]
        if not baris:
            baris = [x for n in nama for x in per_nama.get(norm(n), [])]
        if not baris:
            tuj = {(b.get("idsubsls") or "").strip() for b in aud_id.get(i, [])}
            k_audit = sorted(kunci)
            if len(tuj) == 1 and POLA_KODE.fullmatch(next(iter(tuj))) and len(k_audit) == 1:
                t = next(iter(tuj))
                if t == kode:
                    kat = "SUDAH_DI_TEMPAT"
                else:
                    kat = "AUDIT_SAJA"
                    if label not in sumber:
                        sumber.append(label)
                    na = {norm(b.get("nama_usaha") or "") for b in aud_id[i]} - {""}
                    tb = per_k_baru.get(k_audit[0])
                    if tb is None:     # dua dokumen hidup ber-kunci sama -> satu target 2 ID = DOKUMEN_GANDA di Console
                        tb = {"k": k_audit[0], "s": sumber.index(label), "b": 0, "n": norm(nama[0]) if nama else "",
                              "t": t, "ids": []}
                        baru.append(tb)
                        per_k_baru[k_audit[0]] = tb
                    tb["ids"] = sorted(set(tb["ids"]) | {i})
                    tb["na"] = sorted((set(tb.get("na", [])) | na) - {tb["n"]})
                rincian.append((kat, i, " / ".join(nama), t, "tujuan dari audit", kode, ""))
            else:
                kat = "TAK_DIKENAL"
                rincian.append((kat, i, " / ".join(nama), "", f"{len(aud_id.get(i, []))} baris audit, tujuan {sorted(tuj)}",
                                kode, ""))
            hitung[kat] += 1
            continue
        tujuan = {r.idsubsls for _s, r in baris}
        if len(tujuan) != 1:
            hitung["TUJUAN_AMBIGU"] += 1
            rincian.append(("TUJUAN_AMBIGU", i, " / ".join(nama), "|".join(sorted(tujuan)), "", kode, ""))
            continue
        t = tujuan.pop()
        kembaran = ""
        if t == kode:
            kat, ket = "SUDAH_DI_TEMPAT", ""
        else:
            kembar = sorted({j for _s, r in baris for (j, tj) in ids_kunci.get(r.kunci, ())
                             if j != i and (j, tj) in tuntas})
            if kembar:
                kat, ket, kembaran = "KEMBAR", "kembaran sudah di tujuan (dipertahankan)", kembar[0]
            else:
                kat = "PENGGANTI"
                s_idx, r = baris[0]
                tb = per_k_baru.get(r.kunci)
                if tb is None:
                    tb = {"k": r.kunci, "s": s_idx, "b": r.baris, "n": norm(r.nama_dokumen), "t": t, "ids": []}
                    baru.append(tb)
                    per_k_baru[r.kunci] = tb
                tb["ids"] = sorted(set(tb["ids"]) | {i})
                tb["na"] = sorted(set(tb.get("na", [])) | {norm(n) for n in nama} - {tb["n"]})
                ket = f"baris {r.baris}"
        hitung[kat] += 1
        rincian.append((kat, i, " / ".join(nama), t, ket, kode, kembaran))
    return baru, hitung, rincian


def tulis_rincian_sisa(rincian: list[tuple], path: Path = HASIL / "sisa_wadah_rincian.csv") -> Path:
    """Rincian keputusan --sisa-wadah (KEMBAR = bahan hapus manual admin, lengkap dgn kembarannya)."""
    with lokasi.siapkan(path).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["kategori", "id", "nama", "tujuan", "keterangan", "subsls_sekarang", "kembaran"])
        w.writerows(sorted(rincian))
    return path


KONSOL_HAPUS = Path(__file__).resolve().parents[1] / "hapus_ganda" / "hapus_daftar_console.js"
HAPUS_SIAP = lokasi.hasil("fasih_sm", "hapus_ganda") / "hapus_daftar_console.siap.js"


def daftar_hapus(rincian: list[tuple], tak_dikenal: bool = False) -> list[dict]:
    """Rincian --sisa-wadah -> daftar Console hapus: KEMBAR (wajib kembarannya sudah di tujuan) + TAK_DIKENAL
    kalau diminta (tanpa kembaran; ketetapan user 2026-09-30 utk dokumen yang tidak ada di sumber data)."""
    hasil = []
    for kat, i, nama, tujuan, _ket, kode, kembar in sorted(rincian):
        if kat == "KEMBAR" or (kat == "TAK_DIKENAL" and tak_dikenal):
            hasil.append({"id": i, "nama": nama, "wadah": kode, "kembar": kembar, "tujuan": tujuan if kembar else ""})
    return hasil


def tulis_console_hapus(daftar: list[dict], path: Path = HAPUS_SIAP) -> Path:
    teks = KONSOL_HAPUS.read_text(encoding="utf-8")
    for p in ("/*__DAFTAR__*/[]", "/*__KONFIG__*/{}"):
        if teks.count(p) != 1:
            raise ValueError(f"Penanda {p} harus tepat 1x di {KONSOL_HAPUS.name}")
    ringkas = {"separators": (",", ":"), "ensure_ascii": False}
    teks = (teks.replace("/*__DAFTAR__*/[]", json.dumps(daftar, **ringkas))
            .replace("/*__KONFIG__*/{}", json.dumps({"dibuat": time.strftime("%Y-%m-%d %H:%M")})))
    lokasi.siapkan(path).write_text(teks, encoding="utf-8")
    return path


def konfig_console(args, bagian: str = "", alokasi: dict | None = None) -> dict:
    """Bawaan opsi Console dari argumen CLI (yang tidak diisi = bawaan Console)."""
    opsi = {}
    if args.per_kirim is not None:
        opsi["perKirim"] = args.per_kirim
    if args.cek_sesudah is not None:
        opsi["cekSesudah"] = args.cek_sesudah
    if args.jeda_kirim is not None:
        opsi["jedaKirimMin"], opsi["jedaKirimMaks"] = round(args.jeda_kirim * 1000), round(args.jeda_kirim * 2000)
    if args.jeda_baca is not None:
        opsi["jedaBacaMin"], opsi["jedaBacaMaks"] = round(args.jeda_baca * 1000), round(args.jeda_baca * 2000)
    if args.jarak_request is not None:
        opsi["jarakRequestMs"] = round(args.jarak_request * 1000)
    if args.izinkan_tujuan_selesai:
        opsi["izinkanTujuanSelesai"] = True
    konfig = {"bagian": bagian, "dibuat": time.strftime("%Y-%m-%d %H:%M"), "opsi": opsi}
    if alokasi:
        konfig["alokasi"] = alokasi
    return konfig


def isi_template(teks: str, target: list[dict], sumber: list[str], asal: list[str], konfig: dict) -> str:
    for penanda in PENANDA.values():
        if teks.count(penanda) != 1:
            raise ValueError(f"Penanda {penanda} harus muncul tepat 1x di {KONSOL_TEMPLATE.name}")
    ringkas = {"separators": (",", ":"), "ensure_ascii": False}
    return (teks.replace(PENANDA["target"], json.dumps(target, **ringkas))
            .replace(PENANDA["sumber"], json.dumps(sumber, **ringkas))
            .replace(PENANDA["asal"], json.dumps(asal))
            .replace(PENANDA["konfig"], json.dumps(konfig, **ringkas))
            .replace(PENANDA["kode_kab"], json.dumps(KODE_KAB)))


def tulis_console(bagian: list[list[dict]], sumber: list[str], asal: list[str], args, folder: Path = HASIL,
                  alokasi: dict | None = None) -> list[Path]:
    """Satu berkas .siap.js per bagian. Berkas pembagian LAIN yang tertinggal dari run sebelumnya dihapus
    (berkas keluaran skrip ini sendiri) supaya tidak ada yang menempel target yang tumpang tindih."""
    teks = KONSOL_TEMPLATE.read_text(encoding="utf-8")
    n = len(bagian)
    lama = [folder / KONSOL_SIAP.name, *folder.glob(POLA_KONSOL_BAGIAN)]
    keluar = []
    for i, daftar in enumerate(bagian, start=1):
        path = folder / (KONSOL_SIAP.name if n == 1 else f"pindah_wilayah_console.bagian-{i}-dari-{n}.siap.js")
        tujuan = {t["t"] for t in daftar}
        konfig = konfig_console(args, "" if n == 1 else f"{i}/{n}",
                                {k: v for k, v in (alokasi or {}).items() if k in tujuan})
        lokasi.siapkan(path).write_text(isi_template(teks, daftar, sumber, asal, konfig), encoding="utf-8")
        keluar.append(path)
    for p in lama:
        if p.exists() and p not in keluar:
            p.unlink()
    return keluar


def tulis_pembagian(bagian: list[list[dict]], path: Path = PEMBAGIAN_CSV) -> Path:
    with lokasi.siapkan(path).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["bagian", "tujuan", "kecamatan", "jumlah_dokumen"])
        for i, daftar in enumerate(bagian, start=1):
            for kode, n in sorted(Counter(t["t"] for t in daftar).items()):
                w.writerow([f"{i}/{len(bagian)}", kode, kode[:7], n])
    return path


def tulis_daftar_tujuan(target: list[dict], path: Path) -> list[str]:
    """Subsls tujuan unik (satu per baris) -> bahan `buka_wilayah.py --daftar`."""
    kode = sorted({t["t"] for t in target})
    lokasi.siapkan(Path(path)).write_text(
        "# subsls tujuan pindah wilayah (dibangkitkan pindah_wilayah.py)\n" + "\n".join(kode) + "\n", encoding="utf-8")
    return kode


def input_berjalan() -> list[str]:
    """Akun yang batch input_usaha-nya MASIH berjalan di PC ini (berkas .proses_<akun>.lock hidup)."""
    hasil = []
    for f in lokasi.cari(lokasi.HASIL_INPUT / ".proses_*.lock"):
        try:
            isi = f.read_text(encoding="utf-8").split()
            if isi and pid_hidup(int(isi[0])):
                hasil.append(f.stem.removeprefix(".proses_"))
        except (OSError, ValueError):
            continue
    return hasil


# ----------------------------------------------------------------------------------------------
# --catat: hasil Console -> baris DIPINDAH_WILAYAH di audit
# ----------------------------------------------------------------------------------------------
def pilih_hasil(baris: list[dict]) -> list[dict]:
    """Baris unduhan Console (boleh dari beberapa akun/berkas) -> satu baris per (sumber, kunci, id) yang
    dokumennya terbukti di subsls tujuan; bukti terkuat, lalu terbaru."""
    terbaik: dict[tuple, dict] = {}
    for h in baris:
        st = (h.get("status") or "").strip()
        i = (h.get("id") or "").strip().lower()
        if st not in PERINGKAT_TUNTAS or not POLA_ID.match(i) or not POLA_KODE.fullmatch(h.get("tujuan") or ""):
            continue
        kunci = ((h.get("sumber") or "").strip(), (h.get("kunci") or "").strip(), i)
        lama = terbaik.get(kunci)
        if not lama or (PERINGKAT_TUNTAS[st], h.get("waktu") or "") > (PERINGKAT_TUNTAS[lama["status"]], lama.get("waktu") or ""):
            terbaik[kunci] = {**h, "status": st, "id": i}
    return list(terbaik.values())


def rencana_catat(hasil: list[dict], audits: dict[Path, list[dict]], assignment_id: str = ASSIGNMENT_ID_GABUNGAN):
    """Fungsi murni -> ({audit: [baris audit baru]}, ringkasan Counter, [hasil yang tidak dicatat di audit mana pun]).
    Ditulis ke SETIAP audit yang menunjuk dokumen itu utk kunci itu (ID-nya = id hasil atau salah satu ID target;
    audit batch lain yang kuncinya kebetulan sama tapi dokumennya beda tidak disentuh). Idempoten: audit yang
    status terakhir kuncinya sudah DIPINDAH_WILAYAH ke tujuan & dokumen yang sama dilewati."""
    indeks = {}
    for path, rows in audits.items():
        dasar: dict[str, dict] = {}
        for b in rows:
            if b.get("kunci"):
                dasar[b["kunci"]] = {**dasar.get(b["kunci"], {}), **{k: v for k, v in b.items() if v}}
        indeks[path] = (mg.dokumen_dari(rows), mg.status_terakhir_dari(rows), dasar)
    tulis: dict[Path, list[dict]] = defaultdict(list)
    ringkasan = Counter()
    tidak = []
    waktu = time.strftime("%Y-%m-%d %H:%M:%S")
    for h in hasil:
        kunci, i, tujuan = h["kunci"], h["id"], h["tujuan"]
        boleh = {i} | {x.strip().lower() for x in (h.get("ids") or "").split(";") if x.strip()}
        kena = False
        for path, (dok, st_akhir, dasar) in indeks.items():
            rec = dok.get(kunci)
            if not rec:
                continue
            id_audit = id_dari_url(rec[2]).lower()
            if id_audit and id_audit not in boleh:
                continue
            kena = True
            if st_akhir.get(kunci) == mg.STATUS_DIPINDAH and id_audit == i and rec[1] == tujuan:
                ringkasan["sudah_dicatat"] += 1
                continue
            d = dasar.get(kunci, {})
            pc = (h.get("pencacah") or "").strip().lower()
            tulis[path].append({
                "timestamp": waktu, "baris": d.get("baris", h.get("baris", "")), "kunci": kunci,
                "nama_usaha": d.get("nama_usaha", h.get("nama", "")), "kbli": d.get("kbli", ""),
                "idsubsls": d.get("idsubsls", tujuan), "idsubsls_input": tujuan, "akun_ppl": d.get("akun_ppl", ""),
                "akun_login": pc, "status": mg.STATUS_DIPINDAH, "dokumen_url": url_entry(i, assignment_id),
                "error_message": (f"pindah_wilayah fasih-sm {h.get('waktu', '')}: {h.get('asal') or '?'} -> {tujuan} "
                                  f"({h['status']}; PML {h.get('pengawas') or '-'}, PPL {pc or '-'})"
                                  + (f"; audit dulu menunjuk {id_audit[:8]}" if id_audit and id_audit != i else "")),
            })
            ringkasan["ditulis"] += 1
        if not kena:
            tidak.append(h)
    return dict(tulis), ringkasan, tidak


def jalankan_catat(args) -> int:
    berkas = [Path(p) for p in args.unduhan] if args.unduhan else lokasi.cari(POLA_HASIL_CONSOLE)
    if not berkas:
        print(f"⛔ Tidak ada unduhan Console. Simpan hasil pindahWilayah.unduh() di audit/ ({POLA_HASIL_CONSOLE}) "
              "atau sebutkan berkasnya: --catat --unduhan <csv> ...")
        return 1
    baris = []
    for f in berkas:
        isi = baca_csv(f)
        if isi and not {"kunci", "id", "tujuan", "status"} <= set(isi[0]):
            print(f"  (dilewati, bukan unduhan pindahWilayah: {f})")
            continue
        baris += isi
        print(f"{f}: {len(isi)} baris")
    hasil = pilih_hasil(baris)
    print(f"{len(hasil)} dokumen terbukti di subsls tujuan ({dict(Counter(h['status'] for h in hasil))})")

    audits: dict[Path, list[dict]] = {}
    for path in ([mg.pakai_audit(args.audit)] if args.audit else audit_kandidat()):
        rows = baca_csv(path) if path.exists() else []
        rusak = mg.kerusakan_excel(rows)
        if rusak:
            print("⛔ " + mg.pesan_audit_rusak(rusak, path))
            return 1
        audits[path] = rows
    tulis, ringkasan, tidak = rencana_catat(hasil, audits)
    for path, rows in sorted(tulis.items()):
        print(f"  {path}: {len(rows)} baris DIPINDAH_WILAYAH")
    if ringkasan["sudah_dicatat"]:
        print(f"  {ringkasan['sudah_dicatat']} catatan sudah ada sebelumnya (dilewati)")
    if tidak:
        print(f"⚠️ {len(tidak)} dokumen tidak dikenal audit mana pun (tidak dicatat), mis.: "
              + ", ".join(f"{h.get('sumber')}:{h.get('baris')} {h['id'][:8]}" for h in tidak[:8]))
    if not tulis:
        print("Tidak ada yang perlu ditulis.")
        return 0
    if not args.tulis:
        print("(rencana saja — tambahkan --tulis utk menulis ke audit; tiap audit dicadangkan .bak-<waktu> dulu)")
        return 0
    cap = time.strftime("%Y%m%d-%H%M%S")
    for path, rows in sorted(tulis.items()):
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{cap}"))
        mg.pakai_audit(path)
        mg.append_audit_banyak(rows)
        print(f"✅ {len(rows)} baris ditulis ke {path} (cadangan {path.name}.bak-{cap})")
    return 0


# ----------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Siapkan pindah wilayah dokumen input usaha (fasih-sm) & catat hasilnya")
    ap.add_argument("--sumber", action="append", default=[], help="sheet input usaha (boleh berulang, satu per batch)")
    mg.opsi_format(ap, "format SEMUA --sumber (bawaan tahap2; agenda = format lama Agenda*.xlsx)")
    ap.add_argument("--audit", default="", metavar="BERKAS",
                    help="audit utk SEMUA sheet (bawaan: dipilih otomatis per sheet dari audit/**, tanpa audit/pc)")
    ap.add_argument("--dari", type=int, help="nomor baris sheet pertama (judul = 1), berlaku utk setiap sheet")
    ap.add_argument("--sampai", type=int, help="nomor baris sheet terakhir, berlaku utk setiap sheet")
    ap.add_argument("--tujuan", action="append", default=[], metavar="AWALAN",
                    help="hanya subsls tujuan berawalan ini (kec 7 digit / desa 10 / subsls 16; boleh berulang/koma)")
    ap.add_argument("--subsls-asal", action="append", default=[],
                    help="subsls wadah tambahan (selain idsubsls_input audit) tempat dokumen boleh dipindah DARI")
    ap.add_argument("--bagi", type=int, default=1, metavar="N",
                    help="bagi target ke N akun admin -> N berkas .siap.js (satu subsls tujuan tidak pernah terbelah)")
    ap.add_argument("--per-kirim", type=int, metavar="N", help=f"dokumen per request pindah, 1-{MAKS_PER_KIRIM} (bawaan 50)")
    ap.add_argument("--cek-sesudah", type=int, metavar="N",
                    help="dokumen per request yang dibaca detailnya sesudah dipindah (bawaan 3; >= per-kirim = semua)")
    ap.add_argument("--jeda-kirim", type=float, metavar="DETIK", help="jeda sesudah tiap request pindah (bawaan 1, acak s.d. 2x)")
    ap.add_argument("--jeda-baca", type=float, metavar="DETIK", help="jeda antar-halaman daftar (bawaan 0.1, acak s.d. 2x)")
    ap.add_argument("--jarak-request", type=float, metavar="DETIK", help="jarak minimal antar-request apa pun (bawaan 0.25)")
    ap.add_argument("--izinkan-tujuan-selesai", action="store_true",
                    help="tetap pindah walau subsls tujuan masih Listing Selesai (bawaan: buka wilayah dulu)")
    ap.add_argument("--daftar-tujuan", default="", metavar="TXT",
                    help="tulis subsls tujuan unik ke berkas ini (bahan buka_wilayah.py --daftar)")
    ap.add_argument("--console", action="store_true", help="tulis hasil/pindah_wilayah_console*.siap.js")
    ap.add_argument("--alokasi", default="", metavar="CSV/XLSX",
                    help="alokasi petugas (idsubsls, Email PML, Email PPL): pemilih kalau server punya >1 PML/PPL di tujuan")
    ap.add_argument("--sisa-wadah", action="append", default=[], metavar="CSV",
                    help="unduhan pindahWilayah.sisaWadah(): dokumen wadah bukan target -> dicarikan barisnya (PENGGANTI / "
                         "AUDIT_SAJA jadi target; KEMBAR & SUDAH_DI_TEMPAT dilewati; rincian hasil/sisa_wadah_rincian.csv)")
    ap.add_argument("--hapus-tak-dikenal", action="store_true",
                    help="dgn --sisa-wadah: dokumen TAK_DIKENAL (tidak ada di sheet & audit) ikut Console hapus")
    ap.add_argument("--hanya-sisa", action="store_true",
                    help="buang target yang sudah tuntas ke tujuan yang sama menurut unduhan Console (--unduhan / audit/**)")
    ap.add_argument("--catat", action="store_true",
                    help="SESUDAH memindah: unduhan pindahWilayah.unduh() -> baris DIPINDAH_WILAYAH di audit")
    ap.add_argument("--unduhan", action="append", default=[], metavar="CSV",
                    help=f"dgn --catat: berkas unduhan Console (boleh berulang; bawaan {POLA_HASIL_CONSOLE})")
    ap.add_argument("--tulis", action="store_true", help="dgn --catat: benar-benar tulis ke audit")
    args = ap.parse_args(argv)
    lokasi.cek_struktur_lama()
    if args.per_kirim is not None and not 1 <= args.per_kirim <= MAKS_PER_KIRIM:
        ap.error(f"--per-kirim harus 1-{MAKS_PER_KIRIM}")
    if args.cek_sesudah is not None and args.cek_sesudah < 1:
        ap.error("--cek-sesudah minimal 1 (tanpa sampel, pindah massal tidak pernah punya bukti)")
    if args.bagi < 1:
        ap.error("--bagi minimal 1")
    if args.catat:
        return jalankan_catat(args)
    if not args.sumber:
        ap.error("--sumber wajib (kecuali --catat)")

    awalan = [a.strip() for x in args.tujuan for a in x.split(",") if a.strip()]
    salah = [a for a in awalan if not re.fullmatch(rf"{re.escape(KODE_KAB)}\d{{0,12}}", a)]
    if salah:
        ap.error(f"--tujuan harus awalan kode berawalan {KODE_KAB}: {salah}")

    audits: dict[Path, list[dict]] = {}
    if args.audit:
        jalur = mg.pakai_audit(args.audit)
        audits[jalur] = baca_csv(jalur) if jalur.exists() else []
    else:
        for f in audit_kandidat():
            audits[f] = baca_csv(f)
    for path, rows in audits.items():
        rusak = mg.kerusakan_excel(rows)
        if rusak:
            print("⛔ " + mg.pesan_audit_rusak(rusak, path))
            return 1

    sheet = []
    for s in args.sumber:
        rows, _ = mg.muat_sumber(s, args.format, mode_satu_subsls=True, izinkan_tanpa_koordinat=True)
        path_audit, n = pilih_audit({r.kunci for r in rows}, audits)
        ber_id = sum(1 for r in rows if getattr(r, "id_dokumen", ""))
        print(f"{s}: {len(rows)} baris, {ber_id} ber-ID di sheet | audit: "
              + (f"{path_audit} (mengenal {n} dokumen)" if path_audit else "TIDAK ADA yang mengenal sheet ini"))
        if not path_audit and not ber_id:
            print(f"⛔ {s}: tidak ada ID di sheet & tidak ada audit yang mengenalnya — tidak ada dokumen utk dipindah.")
            return 1
        sheet.append((s, rows, audits.get(path_audit, [])))

    target, sumber, asal, masalah, ringkasan = bangun_target(sheet, args.dari, args.sampai, awalan, args.subsls_asal)
    target_semua = target
    if args.hanya_sisa or args.sisa_wadah:
        berkas = [Path(u) for u in args.unduhan] or lokasi.cari(POLA_HASIL_CONSOLE)
        tuntas = id_tuntas([b for f in berkas for b in baca_csv(Path(f))])
    if args.hanya_sisa:
        target, dibuang = saring_sisa(target, tuntas)
        print(f"--hanya-sisa: {dibuang} target sudah tuntas menurut {len(berkas)} unduhan Console -> sisa {len(target)}")
    if args.sisa_wadah:
        sisa = [b for f in args.sisa_wadah for b in baca_csv(Path(f))]
        n_lama = len(target)
        target, hitung, rincian = tambah_sisa_wadah(sisa, sheet, audits, target, target_semua, tuntas, sumber)
        laporan = tulis_rincian_sisa(rincian)
        print(f"--sisa-wadah: {len(sisa)} dokumen -> {dict(hitung)}; target {n_lama} -> {len(target)} "
              f"(dokumen PENGGANTI menempel ke target barisnya). Rincian: {laporan}")
        hapus = daftar_hapus(rincian, args.hapus_tak_dikenal)
        if hapus and args.console:
            print(f"--sisa-wadah: {len(hapus)} dokumen utk dihapus (KEMBAR{' + TAK_DIKENAL' if args.hapus_tak_dikenal else ''})"
                  f" -> {tulis_console_hapus(hapus)}  (await hapusDaftar.jalankan())")
    alokasi = baca_alokasi(Path(args.alokasi)) if args.alokasi else {}
    if args.alokasi:
        kena = {t["t"] for t in target}
        print(f"--alokasi: {len(alokasi)} subsls ber-email; {len(kena & set(alokasi))}/{len(kena)} subsls tujuan tercakup")
    salah_asal = [a for a in asal if not POLA_KODE.fullmatch(a)]
    if salah_asal:
        print(f"⛔ subsls wadah tidak valid: {salah_asal}")
        return 1

    print(f"\n{len(target)} dokumen jadi target, ke {len({t['t'] for t in target})} subsls tujuan:")
    for nama in sumber:
        print(f"  {nama}: {ringkasan[f'target:{nama}']}")
    if ringkasan["belum_ada_dokumen"]:
        print(f"  {ringkasan['belum_ada_dokumen']} baris dilewati: belum punya dokumen (tanpa ID sheet & URL audit)")
    if ringkasan["di_luar_saringan_tujuan"]:
        print(f"  {ringkasan['di_luar_saringan_tujuan']} baris di luar saringan --tujuan")
    if ringkasan["target_2_id"]:
        print(f"  {ringkasan['target_2_id']} target punya 2 ID (sheet != audit) -> Console memakai yang masih ada; "
              "dua-duanya ada = DOKUMEN_GANDA (tidak dipindah)")
    if ringkasan["baris_kembar_digabung"]:
        print(f"  {ringkasan['baris_kembar_digabung']} baris kembar (kunci sama dalam satu sheet) digabung")
    for kec, n in sorted(Counter(t["t"][:7] for t in target).items()):
        print(f"    tujuan kec {kec}: {n}")
    print(f"Subsls wadah (asal) ({len(asal)}): {', '.join(asal) or '-'}")
    if masalah:
        print(f"\n⛔ {len(masalah)} baris dilewati (tidak masuk target):")
        for s, baris, pesan in masalah[:20]:
            print(f"  {s} baris {baris}: {pesan}")
    if not asal:
        print("⛔ Tidak ada subsls wadah (audit kosong?). Beri --subsls-asal.")
        return 1
    if not target:
        print("⛔ Tidak ada target.")
        return 1

    bagian = bagi_target(target, args.bagi)
    if args.bagi > 1:
        print(f"\nDibagi ke {args.bagi} akun (satu subsls tujuan utuh di satu bagian):")
        for i, daftar in enumerate(bagian, start=1):
            print(f"  bagian {i}/{args.bagi}: {len(daftar)} dokumen, {len({t['t'] for t in daftar})} subsls tujuan")
        print(f"  rinciannya: {tulis_pembagian(bagian)}")
    if args.daftar_tujuan:
        kode = tulis_daftar_tujuan(target, Path(args.daftar_tujuan))
        print(f"\n{args.daftar_tujuan}: {len(kode)} subsls tujuan -> kalau ada yang masih Listing Selesai:\n"
              f"  python fasih_sm/buka_wilayah/buka_wilayah.py --daftar {args.daftar_tujuan} --console")
    berjalan = input_berjalan()
    if berjalan:
        print(f"\n⚠️ input_usaha/approve_pml MASIH berjalan di PC ini utk: {', '.join(berjalan)}. Dokumen yang dipindah keluar "
              "dari list akun PPL-nya; selagi batch akun itu jalan, hitungan list-nya bisa salah -> 'Buat Dokumen' "
              "diulang = risiko GANDA. Pindahkan sesudah batch itu selesai (juga di PC lain).")
    if args.console:
        keluar = tulis_console(bagian, sumber, asal, args, alokasi=alokasi)
        print()
        for p in keluar:
            print(f"✅ {p}")
        print("Tiap berkas -> SATU akun admin (browser sendiri) -> halaman Data survei fasih-sm -> F12 Console -> tempel:\n"
              '  await pindahWilayah.jalankan({mode: "pindah"})\n'
              "  pindahWilayah.unduh()   -> simpan di audit/, lalu: python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat --tulis\n"
              "  pindahWilayah.sisaWadah()   (hanya berkas tanpa --bagi) -> CSV dokumen di wadah yang bukan target")
    if args.console and not args.alokasi:
        print("⚠️ Tanpa --alokasi: subsls tujuan ber-Pengawas/Pencacah ganda akan dilewati (PETUGAS_TUJUAN_GANDA).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
