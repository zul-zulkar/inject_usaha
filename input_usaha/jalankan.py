#!/usr/bin/env python3
"""
jalankan.py — PINTU MASUK input usaha ke fasih-web (dulu input_tahap2/main_tahap2.py).

Sumber = sheet input usaha format tahap 2 (templat: templates/input_usaha.xlsx). Seluruh
orkestrasi, audit, kunci proses & pengaman kirim ada di input_usaha/mesin.py; pemetaan
kolom & pemeriksaan data di inti/tahap2_loader.py. Tutorial: input_usaha/README.md.

⚠️ VPN kantor wajib aktif. ⚠️ Headless dilarang.

    # 1. periksa data TANPA browser (detik-an) -> input_usaha/hasil/cek_input.csv
    python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --cek

    # 2. dry-run satu baris (mengisi, TIDAK mengirim)
    python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --baris 2

    # 3. kirim (IRREVERSIBLE, wajib ketik YA)
    python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS ^
        --dari 2 --sampai 500 --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda --submit
"""

from __future__ import annotations

# -- jalankan dari mana saja; sisipkan akar proyek ke sys.path utk paket inti/ dll --
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from input_usaha.mesin import main as _main  # noqa: E402


def main() -> int:
    return _main()


if __name__ == "__main__":
    _sys.exit(main())
