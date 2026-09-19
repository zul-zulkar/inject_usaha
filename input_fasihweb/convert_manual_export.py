#!/usr/bin/env python3
"""
convert_manual_export.py — Ubah hasil "Copy response" dari endpoint
get-by-assignment-id (fasih-sm) jadi field BLOK II yang rapi, dipetakan
dari dataKey ASLI (bukan tebakan label DOM lagi — ini hasil inspeksi
langsung struktur JSON asli, lihat PANDUAN_EKSPOR_MANUAL.md).

CARA PAKAI
----------
    python convert_manual_export.py export/coba.json
    python convert_manual_export.py export/coba.json --suffix 1002   # kalau
        1 keluarga punya >1 usaha & mau pilih salah satu secara eksplisit

INPUT yang diharapkan: isi file = persis hasil "Copy response"/"Copy value"
dari request `.../assignment/get-by-assignment-id?assignmentId=...` di tab
Network, disimpan mentah sbg .json (lihat Langkah 3-4 di
PANDUAN_EKSPOR_MANUAL.md). Struktur luarnya:
    { "success": true, "data": { ..., "data": "<JSON STRING jawaban>" } }

TEMUAN PENTING dari inspeksi struktur asli (menggantikan asumsi lama di
scrape_source.py/config.py):
  - Field usaha (rincian 8-25) semuanya disimpan dgn akhiran "#{suffix}",
    mis. "nama_komersial#1002". Suffix ini ID internal, BUKAN nomor urut
    usaha (`no_usaha#1002` bisa saja = 1) — jangan diasumsikan berurutan.
  - Field kepemilikan modal (rincian 29: pribadi/non_profit/publik/
    non_publik/pemerintah/asing) TERNYATA ADA di sumber (kunci
    "pribadi#{suffix}" dst) — sebelumnya di config.py ini di-hardcode
    100% Pribadi krn dikira tidak ada di sumber. Script ini scrape
    langsung, TIDAK pakai KEPEMILIKAN_MODAL_DEFAULT lagi kalau datanya ada.
  - Field pekerja (gap yang diketahui di scrape_source.py) TERNYATA di sumber cuma
    ada sbg 2 pasang angka MARGINAL, bukan cross-tab lengkap:
      tk_laki / tk_pr           = total pekerja per JENIS KELAMIN
      tk_dibayar / tk_tdk_dibayar = total pekerja per STATUS BAYAR
    Tidak ada field gabungan "laki-laki YANG dibayar" langsung. Kalau cuma
    1 gender yang punya pekerja (tk_laki=0 atau tk_pr=0) hasilnya BISA
    dipastikan tanpa ambigu. Kalau kedua gender sama-sama >0 DAN
    tk_dibayar>0, kombinasinya AMBIGU dari angka marginal saja — script
    ini akan menandai kasus itu sbg "AMBIGU_PERLU_CEK_MANUAL" drpd
    menebak, sesuai prinsip proyek (jangan menebak field yg tidak pasti).
  - `izin_edar_bpom` (rincian 20) belum pernah ketemu di sample manapun
    sejauh ini (kemungkinan conditional per kategori KBLI) — tetap
    dikosongkan dgn catatan, BUKAN dianggap error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Konsol Windows default-nya cp1252 dan tidak bisa cetak em-dash/emoji yang
# dipakai di pesan-pesan skrip ini — paksa UTF-8 biar tidak crash di tengah run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _label(ans: Any) -> str:
    """Banyak jawaban fasih-sm disimpan sbg list [{"label": "...", "value": ...}, ...]
    (hasil pilihan radio/dropdown/checkbox). Ambil label pertama; kalau
    bentuknya bukan itu (string/angka polos), kembalikan apa adanya."""
    if isinstance(ans, list) and ans and isinstance(ans[0], dict) and "label" in ans[0]:
        return ", ".join(str(x.get("label", "")) for x in ans)
    if ans is None:
        return ""
    return str(ans)


def load_answers(raw_path: Path) -> dict[str, Any]:
    outer = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    record = outer.get("data", outer)  # jaga-jaga kalau sudah tanpa wrapper {success,data}
    data_field = record.get("data")
    if data_field is None:
        raise ValueError(
            "Tidak ketemu key 'data.data' di file ini. Pastikan ini hasil copy response "
            "dari endpoint get-by-assignment-id, BUKAN dari endpoint lain."
        )
    inner = json.loads(data_field) if isinstance(data_field, str) else data_field
    answers = {a["dataKey"]: a["answer"] for a in inner.get("answers", [])}
    return answers


def find_usaha_suffixes(answers: dict[str, Any]) -> list[str]:
    pat = re.compile(r"^nama_usaha#(\w+)$")
    return sorted({m.group(1) for k in answers if (m := pat.match(k))})


def resolve_pekerja(answers: dict[str, Any], suf: str) -> dict[str, Any]:
    def num(key: str) -> int:
        v = answers.get(key, 0)
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    tk_laki, tk_pr = num("tk_laki#" + suf), num("tk_pr#" + suf)
    tk_dibayar, tk_tdk = num("tk_dibayar#" + suf), num("tk_tdk_dibayar#" + suf)

    out = {
        "tk_laki_total": tk_laki,
        "tk_perempuan_total": tk_pr,
        "tk_dibayar_total": tk_dibayar,
        "tk_tidak_dibayar_total": tk_tdk,
        "pekerja_laki2_dibayar": None,
        "pekerja_perempuan_dibayar": None,
        "pekerja_tdk_dibayar": tk_tdk,  # ini SELALU langsung dari sumber, tidak ambigu
        "status": "OK",
    }
    if tk_dibayar == 0:
        out["pekerja_laki2_dibayar"] = 0
        out["pekerja_perempuan_dibayar"] = 0
    elif tk_laki == 0:
        out["pekerja_laki2_dibayar"] = 0
        out["pekerja_perempuan_dibayar"] = tk_dibayar
    elif tk_pr == 0:
        out["pekerja_perempuan_dibayar"] = 0
        out["pekerja_laki2_dibayar"] = tk_dibayar
    else:
        out["status"] = "AMBIGU_PERLU_CEK_MANUAL"
        out["catatan"] = (
            f"tk_laki={tk_laki}, tk_pr={tk_pr}, tk_dibayar={tk_dibayar} — tidak bisa "
            "dipastikan dari angka marginal saja siapa yg dibayar. Cek 'list_kc#" + suf +
            "' (roster pekerja per-orang, kalau terisi) atau tanyakan manual."
        )
    return out


def convert(answers: dict[str, Any], suf: str) -> dict[str, Any]:
    g = lambda k: answers.get(k + "#" + suf, "")  # noqa: E731

    alamat = g("alamat_usaha_view").strip()
    if alamat.endswith("-"):
        alamat = alamat[:-1].strip()

    pengusaha_list = answers.get("pengusaha_var#" + suf) or []
    nama_pengusaha = pengusaha_list[0].get("label", "") if pengusaha_list else ""

    fields = {
        "nama_komersial": g("nama_komersial"),
        "alamat_nama_jalan": alamat,
        "rt": g("rt"),
        "rw": g("rw"),
        "no_hp_wa": g("hp"),
        "nama_pengusaha": nama_pengusaha,
        "jenis_kelamin": _label(answers.get("jk_var#" + suf)),
        "umur": g("umur_pj_var"),
        "kegiatan_utama": g("keg_utama"),
        "b1_produksi_lokasi": _label(answers.get("produk_sendiri#" + suf)),
        "b2_layanan_makan_minum": _label(answers.get("layanan_mamin#" + suf)),
        "b3_penjualan_barang": _label(answers.get("keg_penjualan#" + suf)),
        "tempat_usaha": _label(answers.get("lokasi_usaha#" + suf)),
        "produk_utama": g("produk"),
        # 13d & 13e — bersyarat, hanya dirender kalau 13b1 (produksi di
        # lokasi) = "1. Ya". Terlewat sampai 2026-09-07 karena tidak ada
        # satu pun record contoh yang memproduksi barang sendiri.
        "input_produksi": g("input"),
        "proses_produksi": g("proses"),
        "jaringan_usaha": _label(answers.get("jaringan#" + suf)),
        "pakai_internet": _label(answers.get("internet#" + suf)),
        "produk_ramah_lingkungan": _label(answers.get("produksi_lingkungan#" + suf)),
        "input_ramah_lingkungan": _label(answers.get("perlindungan_lingkungan#" + suf)),
        "karya_seni_budaya": _label(answers.get("produk_seni#" + suf)),
        # _label() krn jawabannya list [{"label":...}] spt field pilihan lain
        # (sebelumnya dipakai mentah via g() saja -> objek Python, bukan string
        # label yg rapi; ketauan pas nyambungin export/ ke fill_blok2.py).
        # 20b — jumlah varian yang SUDAH punya izin edar BPOM. Muncul
        # bersama 20c begitu 20a dijawab.
        "varian_sudah_bpom": g("sudah_bpom"),
        "izin_edar_bpom": _label(answers.get("izin_edar#" + suf)),  # belum pernah ketemu di sample manapun — lihat catatan modul
        "mitra_kdkmp": _label(answers.get("mitra_kdkmp#" + suf)),
        "program_mbg": _label(answers.get("peran_mbg#" + suf)),
        "tahun_mulai_komersial": g("tahun_operasi"),
    }

    kepemilikan_modal = {
        "pribadi": g("pribadi"),
        "nonprofit": g("non_profit"),
        "korporasi_publik": g("publik"),
        "korporasi_nonpublik": g("non_publik"),
        "pemerintah": g("pemerintah"),
        "asing": g("asing"),
    }

    financial_crosscheck = {
        "gaji": g("gaji"),
        "biaya_produksi": g("biaya_produksi"),
        "biaya_pembelian": g("biaya_pembelian"),
        "operasional": g("operasional"),
        "non_operasional": g("non_operasional"),
        "total_pengeluaran": g("total_pengeluaran"),
        "nilai_pendapatan": g("nilai_pendapatan"),
        "pendapatan_lain": g("pendapatan_lain"),
        "aset_usaha_thn": g("aset_usaha_thn"),
        "aset_lain_thn": g("aset_lain_thn"),
        "luas_tanah_thn": g("luas_tanah_thn"),
        "kbli_akhir": g("kbli_akhir"),
        "kategori": g("kategori"),
    }

    return {
        "suffix_usaha": suf,
        "nama_usaha_raw": g("nama_usaha"),
        "fields": fields,
        "kepemilikan_modal": kepemilikan_modal,
        "pekerja": resolve_pekerja(answers, suf),
        "financial_crosscheck_vs_backlog_csv": financial_crosscheck,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_json", help="File hasil 'Copy response' dari get-by-assignment-id (mis. export/coba.json)")
    ap.add_argument("--suffix", help="Pilih suffix usaha tertentu kalau 1 keluarga punya >1 usaha")
    ap.add_argument("-o", "--out", help="Path output (default: <input>.converted.json)")
    args = ap.parse_args()

    raw_path = Path(args.raw_json)
    answers = load_answers(raw_path)
    suffixes = find_usaha_suffixes(answers)

    if not suffixes:
        sys.exit("Tidak ketemu field 'nama_usaha#<suffix>' apapun — pastikan ini record BLOK II usaha, bukan record kosong/blok lain.")

    if args.suffix:
        if args.suffix not in suffixes:
            sys.exit(f"--suffix {args.suffix} tidak ketemu. Suffix yang ada: {suffixes}")
        chosen = [args.suffix]
    else:
        chosen = suffixes
        if len(suffixes) > 1:
            print(f"⚠️  Ketemu {len(suffixes)} usaha dalam 1 keluarga: {suffixes} — konversi SEMUA, cek nama_usaha_raw masing2 buat pilih yg benar.")

    results = [convert(answers, suf) for suf in chosen]

    out_path = Path(args.out) if args.out else raw_path.with_suffix(".converted.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    for r in results:
        print(f"\n=== usaha #{r['suffix_usaha']} — {r['nama_usaha_raw']} ===")
        for k, v in r["fields"].items():
            marker = "  " if v else "⚠️ KOSONG"
            print(f"  {marker} {k}: {v}")
        print(f"  kepemilikan_modal: {r['kepemilikan_modal']}")
        print(f"  pekerja: {r['pekerja']}")

    print(f"\nHasil lengkap ditulis ke: {out_path}")


if __name__ == "__main__":
    main()
