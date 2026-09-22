#!/usr/bin/env python3
"""
main_tahap2.py — Input otomatis hasil pendataan KERTAS SE2026 TAHAP 2
(bahan/input_tahap2.xlsx) ke fasih-web.

Ini hanya PINTU MASUK: seluruh orkestrasi, audit, kunci proses, pembagian
sesi login & pengaman submit dipakai ulang apa adanya dari
input_gabungan/main_gabungan.py (`--format tahap2`). Yang khas tahap 2 cuma
pemetaan kolom & pemeriksaan datanya, di inti/tahap2_loader.py.
Jadi `python input_tahap2/main_tahap2.py ...` = `python
input_gabungan/main_gabungan.py --format tahap2 ...`, dan semua flag
main_gabungan tetap berlaku.

⚠️ VPN kantor wajib aktif. ⚠️ Headless dilarang (fasih-web membalas browser
headless dgn halaman anti-bot).

LANGKAH
=======
1. Periksa data TANPA browser (detik-an) — rinciannya ke cek_gabungan.csv:
       python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --cek

2. Dry-run SATU baris, tinjau hasilnya di browser (TIDAK mengirim):
       python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx ^
           --akun-tunggal <email PPL> --subsls-tunggal <16 digit> --baris 2

3. Kirim baris yang sudah ditinjau (IRREVERSIBLE, wajib ketik YA):
       python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx ^
           --akun-tunggal <email PPL> --subsls-tunggal <16 digit> --baris 2 --submit

RENTANG BARIS & PARALEL
=======================
--dari N --sampai M (nomor baris sheet, judul = baris 1, kedua ujung ikut;
salah satunya boleh dihilangkan) atau --baris "2,5,10-20". Pembagian kerja
antar-PC/proses tinggal memberi rentang yang TIDAK tumpang tindih, mis.
PC A `--dari 2 --sampai 200`, PC B `--dari 201`.

Paralel DI SATU PC hanya boleh dgn AKUN & SUBSLS BERBEDA per proses (+
`--paralel`). Dua proses dgn akun yang sama saling memutus sesi SSO &
memicu STOP_DOKUMEN_TANPA_URL palsu — kunci `.proses_<akun>.lock` menolaknya.
Kunci itu TIDAK berlaku lintas PC: kalau dua komputer memakai akun yang
sama, audit masing-masing tidak saling tahu dan dokumen bisa DUPLIKAT
terkirim (kejadian nyata 2026-09-15, 7 pasang duplikat). Jalankan
`python input_gabungan/sinkron_list.py` sebelum & sesudah tiap batch.
"""

from __future__ import annotations

# -- jalankan dari root proyek; sisipkan root ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from input_gabungan.main_gabungan import main as _main


def main() -> int:
    return _main(format_bawaan="tahap2", perintah="python input_tahap2/main_tahap2.py")


if __name__ == "__main__":
    _sys.exit(main())
