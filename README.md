# Inject Usaha SE2026 — otomatisasi fasih-web & fasih-sm

Skrip Python (Playwright) dan skrip Console Chrome untuk **menambahkan dokumen usaha** Sensus
Ekonomi 2026 ke **fasih-web** dari hasil pendataan kertas: membuat dokumen, mengisi SE2026-P &
SE2026-L BLOK II, lalu mengirim. Plus alat pendukung di **fasih-sm** & **manajemen-mitra**: ganti
mode CAPI→PAPI, reset password mitra, approve PML, buka/tandai selesai wilayah, pindah wilayah,
dan hapus dokumen ganda.

Dikembangkan di **BPS Kabupaten Buleleng** (kode `5108`) dan dibuka supaya kabupaten/kota lain
bisa menduplikasinya. Semua nilai milik Buleleng bisa diganti lewat `inti/config_lokal.py`.

> [!WARNING]
> **Bukan aplikasi resmi BPS.** Pakai hanya dengan akun & kewenangan Anda sendiri, lewat VPN
> kantor, dan patuhi kerahasiaan data statistik. **Kirim, Approve, Reset password, Pindah wilayah,
> Buka/Tandai wilayah, dan Hapus TIDAK BISA dibatalkan.** Semua alat bawaannya *dry-run*/read-only;
> jalankan eksekusi dengan `--limit 1` dulu dan periksa hasilnya di web.

## Peta folder

| Folder | Isi | Tutorial |
| --- | --- | --- |
| [`gui/`](gui/) | **GUI web lokal** untuk semua alat di bawah (klik dua kali `gui\buka_gui.bat`): pilih berkas, atur pengaturan, klik tombol | [README](gui/README.md) |
| [`input_usaha/`](input_usaha/) | **Alat utama**: periksa sheet, buat & isi & kirim dokumen di fasih-web, sinkron, laporan progres | [README](input_usaha/README.md) |
| [`approve_pml/`](approve_pml/) | Approve dokumen oleh akun PML (fasih-web) | [README](approve_pml/README.md) |
| [`fasih_sm/`](fasih_sm/) | Alat Console fasih-sm: `ganti_moda`, `buka_wilayah`, `tandai_selesai`, `pindah_wilayah`, `hapus_ganda` | [README](fasih_sm/README.md) |
| [`reset_mitra/`](reset_mitra/) | Samakan password akun PPL (manajemen-mitra, Console) | [README](reset_mitra/README.md) |
| [`koordinat/`](koordinat/) | Perbaiki / ganti koordinat yang rusak atau di luar subsls | [README](koordinat/README.md) |
| [`antar_pc/`](antar_pc/) | Kerja di beberapa PC: bungkus zip, pindah struktur, gabung audit & ID | [README](antar_pc/README.md) |
| [`inti/`](inti/) | Modul bersama: konfigurasi, pembaca & pemeriksa sheet, otomasi fasih-web | [README](inti/README.md) |
| [`templates/`](templates/) | **Templat input usaha** (1 baris contoh), config lokal, contoh daftar | [README](templates/README.md) |
| [`docs/`](docs/) | [Alur kerja lengkap](docs/ALUR_KERJA.md), [format input usaha](docs/FORMAT_INPUT_USAHA.md), [catatan teknis](docs/CATATAN_TEKNIS.md) | |
| [`tests/`](tests/) | Uji offline (tanpa VPN/browser): `python tests/jalankan_semua.py` | |
| `bahan/` | **Data masukan Anda** (sheet input usaha, daftar kode) — tidak ikut git | [README](bahan/README.md) |
| `audit/` | **Catatan dokumen** yang sudah dibuat/dikirim — tidak ikut git, jangan dihapus | [README](audit/README.md) |

Aturan berkas: **masukan di `bahan/`, catatan di `audit/`, semua keluaran alat di `<alat>/hasil/`**
(laporan, `*.siap.js`, log, screenshot — boleh dihapus kapan saja). Lokasinya diatur satu tempat,
[`inti/lokasi.py`](inti/lokasi.py).

## Mulai cepat

Prasyarat: **VPN kantor**, Python 3.10+, Google Chrome (Node.js opsional, hanya untuk uji Console).

```bash
pip install -r requirements.txt
playwright install chromium
copy templates\config_lokal.contoh.py inti\config_lokal.py
copy templates\input_usaha.xlsx bahan\input_usaha.xlsx
```

1. Isi `inti/config_lokal.py`: minimal `FIXED_PASSWORD` dan `KODE_KAB`.
2. Isi `bahan/input_usaha.xlsx` (tab `input_usaha`, mulai baris 2 — baris contoh ditimpa/dihapus).
   Arti tiap kolom ada di tab `petunjuk` dan [`docs/FORMAT_INPUT_USAHA.md`](docs/FORMAT_INPUT_USAHA.md).
3. Periksa tanpa browser, lalu dry-run satu baris, lalu kirim:

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --cek
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --baris 2
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda --submit
```

Urutan lengkap (reset password → ganti mode → input → approve → pindah wilayah → tandai selesai):
[`docs/ALUR_KERJA.md`](docs/ALUR_KERJA.md). Semua perintah dijalankan **dari folder proyek ini**.

## Aturan keselamatan (ringkas)

1. **Default selalu dry-run / read-only.** Eksekusi butuh flag eksplisit (`--submit`, `--eksekusi`,
   `mode: "eksekusi"`) dan konfirmasi ketik `YA`.
2. **Mulai dengan `--limit 1`**, periksa hasilnya di web, baru perbesar.
3. **GALAT harus 0 sebelum Kirim** — dokumen yang masih GALAT dilewati, tidak ditebak.
4. **Satu akun = satu proses = satu PC** pada satu waktu (dua proses saling memutus sesi; dua PC
   tidak saling tahu audit-nya → dokumen ganda).
5. **Satu batch = satu audit.** Sheet lama dijalankan dengan `--audit` miliknya; skrip berhenti
   kalau audit yang dipakai jelas bukan milik sheet itu.
6. **Jangan buka-simpan audit di Excel**; jangan sentuh "Nomor Urut Bangunan" di dokumen yang sedang
   diproses; jalankan headed (fasih-web menolak browser headless).

## Privasi

Repo ini **publik**. `.gitignore` menahan `bahan/`, `audit/`, `arsip/`, semua `hasil/`, `*.xlsx`,
`*.csv`, sesi browser, dan `inti/config_lokal.py`. Satu-satunya pengecualian `templates/` — isinya
harus tetap fiktif. Sebelum commit selalu cek `git status`; jangan menyalin email petugas, nama
responden, NIK, no HP, atau link Google Sheet ke berkas yang ikut git.

## Lisensi

[MIT](LICENSE) — perangkat lunak disediakan "apa adanya"; tanggung jawab atas data yang dikirim
lewat skrip ini ada pada penggunanya.
