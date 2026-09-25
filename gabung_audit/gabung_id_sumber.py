#!/usr/bin/env python3
"""
gabung_id_sumber.py — satukan kolom "ID Dokumen FASIH" sheet sumber dari BEBERAPA PC.

Kenapa ada: main_gabungan/main_tahap2 menulis ID dokumen ke sheet sumber MILIK PC
ITU SENDIRI (inti/id_dokumen.py). Kalau 5 PC mengerjakan rentang baris berbeda,
tiap salinan sheet hanya berisi ID rentangnya — sama seperti audit, sheet-nya
perlu disatukan supaya PC mana pun mengenali dokumen buatan PC lain.

SIFAT: OFFLINE & READ-ONLY thd server, thd salinan sumber, DAN thd sheet `--utama`.
Keluaran masuk `<folder --sumber>/hasil/`: laporan_gabung_id.csv selalu, sheet hasil
(= salinan `--utama` + ID baru, nama berkas sama) hanya dgn `--tulis`; hasil lama
dicadangkan `.bak-<waktu>`. `--keluaran <sama dgn --utama>` = isi sheet utama langsung. Penulisan memakai PencatatIdSumber yang sama dgn batch:
sel yang sudah berisi apa pun TIDAK PERNAH ditimpa, sheet ber-rumus tidak ditulis,
berkas yang sedang dibuka Excel ditunda.

Baris salinan dicocokkan ke baris sheet utama lewat:
  ISI    sidik isi baris sama persis (tanpa kolom ID) — cara utama;
  KUNCI  isi beda (mis. koordinat dikoreksi di satu PC) tapi `kunci` loader sama
         (akun + idsubsls + nama + pemilik) — nomor baris sama didahulukan.
Tidak ketemu keduanya -> TIDAK_KETEMU (ID tidak dipindah, dilaporkan).

Hasil per baris sheet utama:
  TULIS         sel utama kosong, semua PC sepakat satu ID     -> diisi (dgn --tulis)
  SUDAH         sel utama sudah berisi ID itu
  BEDA          sel utama berisi ID lain dari yang dibawa PC lain -> TIDAK ditimpa
  KONFLIK       >= 2 PC membawa ID BERBEDA utk baris yang sama  -> TIDAK ditulis
  ID_GANDA      satu ID jatuh ke >1 baris sheet utama           -> TIDAK ditulis
  SEL_TIDAK_VALID sel utama berisi teks bukan ID                -> TIDAK ditimpa
BEDA/KONFLIK hampir pasti = satu baris punya DUA dokumen di server (ganda):
cek lewat gabung_audit (daftar_ganda.csv) & hapus_ganda, lalu isi selnya manual.

LANGKAH (jalankan dari root proyek, sesudah batch di semua PC berhenti)
-------
1. Salin sheet sumber tiap PC ke folder yang SAMA dgn audit-nya, satu subfolder per PC
   (berkas disalin apa adanya, tanpa ganti nama):
       audit_pc/pc2/audit_log_gabungan.csv   audit_pc/pc2/input_tahap2.xlsx
       audit_pc/pc3/audit_log_gabungan.csv   audit_pc/pc3/input_tahap2.xlsx
   Alat ini hanya mengambil berkas ber-kolom ID; gabung_audit hanya mengambil audit.
2. Laporan dulu (tidak menulis apa pun):
       python gabung_audit/gabung_id_sumber.py --format tahap2 --utama bahan/input_tahap2.xlsx --sumber audit_pc
3. Tulis (-> audit_pc/hasil/input_tahap2.xlsx):
       python gabung_audit/gabung_id_sumber.py --format tahap2 --utama bahan/input_tahap2.xlsx --sumber audit_pc --tulis
4. Isi sisa ID dari audit gabungan (hasil gabung_audit --tulis di folder yang sama):
       python input_gabungan/tulis_id_sumber.py --format tahap2 --sumber audit_pc/hasil/input_tahap2.xlsx --audit audit_pc/hasil --tulis
5. Sebarkan audit_pc/hasil/audit_log_gabungan.csv (ke root) & input_tahap2.xlsx (ke bahan/)
   ke SEMUA PC, termasuk PC ini.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gabung_audit.gabung_audit import FOLDER_HASIL, di_folder_hasil, folder_hasil  # noqa: E402
from inti.id_dokumen import JUDUL_ID, PencatatIdSumber, baca_kolom_id, id_dari_teks  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LAPORAN_PATH = Path("./laporan_gabung_id.csv")
EKSTENSI = (".xlsx", ".xlsm", ".csv")
URUT_KATEGORI = ["TULIS", "SUDAH", "BEDA", "KONFLIK", "ID_GANDA", "SEL_TIDAK_VALID"]
DITAHAN = ("BEDA", "KONFLIK", "ID_GANDA", "SEL_TIDAK_VALID")


@dataclass
class Salinan:
    """Isi kolom ID satu salinan sheet + identitas tiap barisnya."""
    nama: str
    mentah: dict = field(default_factory=dict)   # {baris: teks sel ID}
    sidik: dict = field(default_factory=dict)    # {baris: sidik isi baris tanpa kolom ID}
    kunci: dict = field(default_factory=dict)    # {baris: kunci loader} ({} kalau loader gagal)
    label: dict = field(default_factory=dict)    # {baris: nama dokumen} utk laporan


@dataclass
class Keputusan:
    baris: int
    kategori: str
    id_tulis: str = ""
    usulan: dict = field(default_factory=dict)   # {id: [(salinan, baris_salinan, cara)]}
    catatan: str = ""


def daftar_berkas(sumber: list[str], utama: Path, format_sumber: str = "standar") -> list[Path]:
    """Berkas salinan dari argumen --sumber (berkas atau folder, subfolder ikut —
    mis. `audit_pc/pc2/input_tahap2.xlsx`). Sheet utama sendiri, cadangan .bak-*,
    berkas kunci Excel ~$, berkas tersembunyi, dan berkas TANPA kolom ID (audit,
    laporan, sheet lama) dilewati — jadi satu folder boleh berisi audit & sheet
    bahan sekaligus."""
    out: list[Path] = []
    for s in sumber:
        p = Path(s)
        calon = sorted(p.rglob("*")) if p.is_dir() else [p]
        for c in calon:
            if not c.is_file() or c.suffix.lower() not in EKSTENSI:
                continue
            if c.name.startswith(("~$", ".")) or ".bak-" in c.name:
                continue
            if p.is_dir() and di_folder_hasil(c, p):
                continue
            if c.resolve() == utama.resolve() or c.resolve() in [o.resolve() for o in out]:
                continue
            try:
                ada_kolom = baca_kolom_id(c, format_sumber).kolom is not None
            except Exception as e:  # noqa: BLE001 — berkas rusak/bukan sheet: lewati & laporkan
                print(f"  (dilewati, tidak terbaca: {c} — {e})")
                continue
            if not ada_kolom:
                print(f"  (dilewati, tidak punya kolom '{JUDUL_ID}': {c})")
                continue
            out.append(c)
    return out


def label_berkas(path: Path, sumber: list[str]) -> str:
    for s in sumber:
        akar = Path(s)
        if akar.is_dir():
            try:
                return Path(path).resolve().relative_to(akar.resolve()).as_posix()
            except ValueError:
                continue
    return Path(path).name


def baca_salinan(path: Path, format_sumber: str, nama: str | None = None) -> Salinan:
    isi = baca_kolom_id(path, format_sumber)
    s = Salinan(nama=nama or path.name, mentah=dict(isi.mentah), sidik=dict(isi.sidik))
    try:
        if format_sumber == "tahap2":
            from inti.tahap2_loader import load_tahap2
            rows = load_tahap2(path)
        else:
            from inti.gabungan_loader import load_gabungan
            rows = load_gabungan(path)
        s.kunci = {r.baris: r.kunci for r in rows}
        s.label = {r.baris: r.nama_dokumen for r in rows}
    except Exception as e:  # noqa: BLE001 — tanpa kunci, pencocokan jatuh ke sidik saja
        print(f"  ⚠ {s.nama}: loader gagal ({e}) — dicocokkan lewat isi baris saja.")
    return s


def _indeks(nilai: dict) -> dict:
    per = defaultdict(list)
    for baris, v in nilai.items():
        if v:
            per[v].append(baris)
    return per


def cocokkan(baris: int, salin: Salinan, utama: Salinan, per_sidik: dict, per_kunci: dict
             ) -> tuple[int | None, str]:
    """(baris sheet utama, cara) utk satu baris salinan; (None, alasan) kalau tidak ketemu."""
    calon = per_sidik.get(salin.sidik.get(baris, ""), [])
    if len(calon) == 1:
        return calon[0], "ISI"
    if baris in calon:                       # baris identik >1: nomor baris sama didahulukan
        return baris, "ISI"
    k = salin.kunci.get(baris, "")
    if k:
        if utama.kunci.get(baris) == k:
            return baris, "KUNCI"
        calon_k = per_kunci.get(k, [])
        if len(calon_k) == 1:
            return calon_k[0], "KUNCI"
        if len(calon_k) > 1:
            return None, f"kunci ada di {len(calon_k)} baris utama {calon_k[:5]}"
    if len(calon) > 1:
        return None, f"isi baris sama persis dgn {len(calon)} baris utama {calon[:5]}"
    return None, "isi & kunci baris tidak ditemukan di sheet utama"


def rencana_gabung(utama: Salinan, salinan: list[Salinan]) -> tuple[list[Keputusan], list[tuple]]:
    """Fungsi murni: (keputusan per baris utama yang disentuh, [(salinan, baris, id, alasan)]
    ID salinan yang TIDAK dipakai: bukan ID dokumen / barisnya tidak ketemu)."""
    per_sidik = _indeks(utama.sidik)
    per_kunci = _indeks(utama.kunci)
    usulan: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    terbuang: list[tuple] = []
    for s in salinan:
        for baris, teks in sorted(s.mentah.items()):
            if not teks:
                continue
            i = id_dari_teks(teks)
            if not i:
                terbuang.append((s.nama, baris, teks[:60], "SUMBER_TIDAK_VALID: sel bukan ID dokumen"))
                continue
            tujuan, cara = cocokkan(baris, s, utama, per_sidik, per_kunci)
            if tujuan is None:
                terbuang.append((s.nama, baris, i, f"TIDAK_KETEMU: {cara}"))
                continue
            usulan[tujuan][i].append((s.nama, baris, cara))

    id_utama: dict[str, list[int]] = defaultdict(list)
    for baris, teks in utama.mentah.items():
        i = id_dari_teks(teks)
        if i:
            id_utama[i].append(baris)

    keputusan: list[Keputusan] = []
    for baris in sorted(usulan):
        u = {i: list(v) for i, v in usulan[baris].items()}
        lama = utama.mentah.get(baris, "")
        lama_id = id_dari_teks(lama)
        if lama and not lama_id:
            k = Keputusan(baris, "SEL_TIDAK_VALID", usulan=u, catatan=f"sel utama berisi '{lama[:40]}'")
        elif lama_id:
            lain = sorted(set(u) - {lama_id})
            k = (Keputusan(baris, "SUDAH", usulan=u) if not lain else
                 Keputusan(baris, "BEDA", usulan=u,
                           catatan=f"utama {lama_id[:8]} vs salinan {', '.join(x[:8] for x in lain)}"))
        elif len(u) > 1:
            k = Keputusan(baris, "KONFLIK", usulan=u,
                          catatan="salinan membawa ID berbeda: " + ", ".join(x[:8] for x in sorted(u)))
        else:
            k = Keputusan(baris, "TULIS", id_tulis=next(iter(u)), usulan=u)
        keputusan.append(k)

    # Satu dokumen hanya milik satu baris: ID yang sudah ada di baris utama LAIN,
    # atau diusulkan utk >1 baris, tidak ditulis.
    per_id_tulis = defaultdict(list)
    for k in keputusan:
        if k.kategori == "TULIS":
            per_id_tulis[k.id_tulis].append(k.baris)
    for k in keputusan:
        if k.kategori != "TULIS":
            continue
        lain = sorted(set(per_id_tulis[k.id_tulis] + id_utama.get(k.id_tulis, [])) - {k.baris})
        if lain:
            k.kategori, k.catatan = "ID_GANDA", f"ID {k.id_tulis[:8]} juga jatuh ke baris utama {lain[:5]}"
            k.id_tulis = ""
    return keputusan, terbuang


def _asal(usulan: dict) -> str:
    return "; ".join(f"{i[:8]}<-{n}:{b}({c})" for i, v in sorted(usulan.items()) for n, b, c in v)


def tulis_laporan(path: Path, utama: Salinan, keputusan: list[Keputusan], terbuang: list[tuple]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["kategori", "baris_utama", "nama_dokumen", "id_ditulis", "id_di_utama", "asal", "catatan"])
        for k in sorted(keputusan, key=lambda k: (URUT_KATEGORI.index(k.kategori), k.baris)):
            w.writerow([k.kategori, k.baris, utama.label.get(k.baris, ""), k.id_tulis,
                        id_dari_teks(utama.mentah.get(k.baris, "")), _asal(k.usulan), k.catatan])
        for nama, baris, i, alasan in terbuang:
            kat, _, cat = alasan.partition(": ")
            w.writerow([kat, "", "", "", "", f"{i[:36]}<-{nama}:{baris}", cat])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"Satukan kolom '{JUDUL_ID}' sheet sumber dari beberapa PC (offline)")
    ap.add_argument("--utama", required=True, help="sheet yang diisi (mis. bahan/input_tahap2.xlsx)")
    ap.add_argument("--sumber", required=True, action="append",
                    help="salinan sheet PC lain: berkas atau folder (boleh diulang)")
    ap.add_argument("--format", choices=("standar", "tahap2"), default="standar")
    ap.add_argument("--tulis", action="store_true",
                    help="benar-benar menulis sheet hasil (tanpa ini: laporan saja)")
    ap.add_argument("--keluaran", default=None,
                    help=f"sheet hasil (bawaan <folder --sumber>/{FOLDER_HASIL}/<nama sheet utama>; "
                         "sama dgn --utama = isi sheet utama langsung)")
    ap.add_argument("--laporan", default=None,
                    help=f"CSV laporan (bawaan <folder --sumber>/{FOLDER_HASIL}/{LAPORAN_PATH.name})")
    args = ap.parse_args(argv)

    utama_path = Path(args.utama)
    if not utama_path.exists():
        print(f"Sheet utama tidak ditemukan: {utama_path}")
        return 2
    hasil = folder_hasil(args.sumber)
    keluaran = Path(args.keluaran) if args.keluaran else hasil / utama_path.name
    args.laporan = args.laporan or str(hasil / LAPORAN_PATH.name)
    Path(args.laporan).parent.mkdir(parents=True, exist_ok=True)
    berkas = daftar_berkas(args.sumber, utama_path, args.format)
    if not berkas:
        print(f"Tidak ada salinan sheet ber-kolom '{JUDUL_ID}' di {', '.join(args.sumber)}.")
        return 2

    print(f"Sheet utama: {utama_path}")
    utama = baca_salinan(utama_path, args.format, nama="UTAMA")
    salinan = []
    for p in berkas:
        s = baca_salinan(p, args.format, nama=label_berkas(p, args.sumber))
        n_id = sum(1 for t in s.mentah.values() if id_dari_teks(t))
        print(f"  salinan {p}: {len(s.sidik)} baris, {n_id} ber-ID")
        salinan.append(s)
    n_utama = sum(1 for t in utama.mentah.values() if id_dari_teks(t))
    print(f"  utama: {len(utama.sidik)} baris, {n_utama} ber-ID")
    beda_jumlah = [s.nama for s in salinan if len(s.sidik) != len(utama.sidik)]
    if beda_jumlah:
        print(f"  ℹ Jumlah baris beda dgn utama: {', '.join(beda_jumlah)} — baris tetap dicocokkan lewat isi/kunci.")

    keputusan, terbuang = rencana_gabung(utama, salinan)
    jumlah = Counter(k.kategori for k in keputusan)
    print("\nHASIL per baris sheet utama:")
    for kat in URUT_KATEGORI:
        if jumlah[kat]:
            print(f"  {jumlah[kat]:5}  {kat}")
    cara = Counter(c for k in keputusan if k.kategori == "TULIS" for v in k.usulan.values() for _, _, c in v)
    if cara.get("KUNCI"):
        print(f"  ({cara['KUNCI']} usulan dicocokkan lewat KUNCI — isi barisnya sudah beda antar-PC)")

    for k in keputusan:
        if k.kategori in DITAHAN:
            print(f"  ⚠ {k.kategori} baris {k.baris} {utama.label.get(k.baris, '')[:40]}: {k.catatan} "
                  f"[{_asal(k.usulan)}]")
    if terbuang:
        print(f"\n{len(terbuang)} ID salinan TIDAK dipakai:")
        for nama, baris, i, alasan in terbuang[:30]:
            print(f"  ⚠ {nama} baris {baris} ({i[:8]}): {alasan}")
        if len(terbuang) > 30:
            print(f"  ... {len(terbuang) - 30} lagi — lihat {args.laporan}")
    tulis_laporan(Path(args.laporan), utama, keputusan, terbuang)
    print(f"\nLaporan: {args.laporan}")
    if any(k.kategori in ("BEDA", "KONFLIK") for k in keputusan):
        print("BEDA/KONFLIK = satu baris punya >1 dokumen di server (ganda). Cek daftar_ganda.csv "
              "(gabung_audit) / docs/PANDUAN_HAPUS_GANDA.md, lalu isi selnya manual.")

    tulis = [k for k in keputusan if k.kategori == "TULIS"]
    sama_utama = keluaran.resolve() == utama_path.resolve()
    if not tulis:
        print("Tidak ada ID baru utk ditulis ke sheet utama.")
        if not args.tulis or sama_utama:
            return 0
        # --tulis tetap membuat sheet hasil, supaya berkas yang disebar selalu ada di sana.
    if not args.tulis:
        print(f"\n(laporan saja) Tambahkan --tulis utk membuat {keluaran} "
              f"(= {utama_path.name} + {len(tulis)} ID baru di kolom '{JUDUL_ID}').")
        return 0

    excel = keluaran.with_name("~$" + keluaran.name)
    if excel.exists():
        print(f"{keluaran} sedang dibuka di Excel (ada {excel.name}) — tutup dulu, lalu ulangi.")
        return 1
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    if keluaran.exists():
        cadangan = keluaran.with_name(f"{keluaran.name}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(keluaran, cadangan)
        print(f"Cadangan: {cadangan}")
    if not sama_utama:
        # Sheet utama TIDAK disentuh: hasil = salinannya + ID baru (sidik baris sama).
        shutil.copy2(utama_path, keluaran)
    pencatat = PencatatIdSumber(keluaran, args.format)
    for k in tulis:
        pencatat.antre(SimpleNamespace(baris=k.baris, sidik_sumber=utama.sidik.get(k.baris, "")), k.id_tulis)
    pencatat.simpan()
    print(pencatat.ringkasan())
    if not sama_utama:
        print(f"Sheet utama {utama_path} tidak diubah. Salin {keluaran} ke SEMUA PC (termasuk PC ini).")
    return 0 if not pencatat.tertunda and not pencatat.dimatikan else 1


if __name__ == "__main__":
    sys.exit(main())
