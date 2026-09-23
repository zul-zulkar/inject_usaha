# Inject Usaha SE2026 — otomatisasi fasih-web & fasih-sm

Skrip Python (Playwright) dan skrip Console Chrome untuk **inject usaha** pada
**Sensus Ekonomi 2026**: menambahkan dokumen usaha baru ke **fasih-web** dari data yang sudah
dikumpulkan di luar aplikasi — membuat dokumen, mengisi SE2026-P & SE2026-L BLOK II, lalu
mengirim. Termasuk alat pendukung di **fasih-sm** & **manajemen-mitra**: ganti mode
CAPI→PAPI, reset password mitra, approve oleh PML, buka/tandai selesai wilayah, dan pindah
wilayah dokumen.

Dikembangkan dan dipakai di **BPS Kabupaten Buleleng** (kode wilayah `5108`). Repo ini
dibuka supaya kabupaten/kota lain bisa menduplikasinya. Semua nilai milik Buleleng
bisa diganti lewat satu file konfigurasi lokal (lihat [Menyesuaikan untuk kabupaten Anda](#menyesuaikan-untuk-kabupaten-anda)).

> [!WARNING]
> **Bukan aplikasi resmi BPS.** Gunakan hanya dengan akun & kewenangan Anda sendiri, lewat
> VPN kantor, dan patuhi ketentuan kerahasiaan data statistik. Tindakan **Kirim, Approve,
> Reset password, Pindah wilayah, dan Tandai/Buka wilayah TIDAK BISA dibatalkan.** Semua skrip
> default-nya *dry-run*/read-only; jalankan mode eksekusi dengan `--limit 1` dulu dan periksa
> hasilnya sebelum memproses banyak data.

---

## Format input: satu standar untuk semua jenis usaha

Data usaha disiapkan dalam **format standar**: satu file Excel, **satu baris = satu usaha =
satu dokumen**, **satu kolom = jawaban final satu rincian kuesioner**. Format ini berlaku untuk
jenis usaha apa pun — perdagangan, jasa, fasilitas kesehatan, pangkalan gas, produksi makanan,
dst. Rincian yang hanya muncul untuk jenis usaha tertentu (13d/13e produksi, 19 halal, 20 BPOM)
punya kolom sendiri yang boleh dikosongkan kalau tidak relevan.

- **Templat kosong:** [`templates/input_usaha.kosong.xlsx`](templates/input_usaha.kosong.xlsx) — tinggal
  salin hasil pendataan lapangan ke tab `input_usaha`.
- **Templat berpetunjuk:** [`templates/input_usaha.contoh.xlsx`](templates/input_usaha.contoh.xlsx) — penjelasan
  tiap kolom + dua contoh fiktif (usaha perdagangan & usaha produksi).
- **Spesifikasi lengkap:** [`docs/FORMAT_STANDAR_INPUT_USAHA.md`](docs/FORMAT_STANDAR_INPUT_USAHA.md) —
  kolom per jenis usaha, aturan pemeriksaan, cara menambah rincian baru.

**Mode murni** (`GABUNGAN_MODE_MURNI = True`, disarankan untuk data hasil pendataan lapangan):
setiap isian di fasih-web diambil apa adanya dari Excel — tanpa aturan penamaan, nilai default,
atau koreksi data buatan skrip. Kalau form meminta sesuatu yang tidak ada di Excel, baris itu
dilewati, tidak ditebak. Mode normal (bawaan) memakai aturan & koreksi yang ditetapkan BPS
Buleleng; perbedaannya dirinci di spesifikasi.

> Nama baku: file `input_usaha.xlsx`, tab `input_usaha` (nama file sebenarnya bebas). Nama lama
> di Buleleng — `Agenda.xlsx` dengan tab `gabungan` — tetap diterima.

Ada juga alur khusus **salin dari dokumen sumber** (`input_fasihweb/`, backlog `salin_dokumen_sumber.csv`):
usaha *pecahan* yang jawabannya disalin dari dokumen lain di fasih-sm dengan penyesuaian
(nilai finansial 10%, dst.). Di Buleleng dipakai untuk usaha perdagangan. Kalau data Anda dari
pendataan lapangan, pakai format standar.

---

## Isi repo

| Folder | Fungsi | Sistem | Cara kerja |
| --- | --- | --- | --- |
| [`input_gabungan/`](input_gabungan/) | **Inject usaha dari format standar** (semua jenis usaha): cek offline, buat & isi dokumen, kirim, sinkron list, rencana ubah wilayah | fasih-web | Playwright (browser terbuka) |
| [`input_fasihweb/`](input_fasihweb/) | Inject usaha **salin dari dokumen sumber** (`salin_dokumen_sumber.csv` + file export fasih-sm) | fasih-web | Playwright |
| [`approve_pml/`](approve_pml/) | Approve dokumen oleh akun PML (Pengawas) | fasih-web | Playwright |
| [`ganti_moda/`](ganti_moda/) | Ganti mode assignment CAPI → PAPI supaya "+ Dokumen Baru" muncul | fasih-sm | Console Chrome |
| [`reset_mitra/`](reset_mitra/) | Seragamkan password akun PPL | manajemen-mitra | Console Chrome |
| [`buka_wilayah/`](buka_wilayah/) | Buka Wilayah (batal "Selesai Listing") | fasih-sm | Console Chrome |
| [`tandai_selesai/`](tandai_selesai/) | Tandai Selesai Listing | fasih-sm | Console Chrome |
| [`pindah_wilayah/`](pindah_wilayah/) | Pindah wilayah (Change Region) dokumen yang sudah di-approve | fasih-sm | Console Chrome |
| [`gabung_audit/`](gabung_audit/) | Satukan audit beberapa PC + laporan progres (per akun, wilayah, status) | — | offline |
| [`inti/`](inti/) | Modul bersama: konfigurasi, pembaca format standar, interaksi fasih-web | — | — |
| [`templates/`](templates/) | **Templat** untuk memulai (format standar kosong & berpetunjuk, CSV, daftar kode, config lokal) | — | — |
| [`docs/`](docs/) | Spesifikasi format & panduan langkah-demi-langkah per alat | — | — |
| [`tests/`](tests/) | Uji offline (tanpa VPN/browser) | — | — |

**Kenapa ada dua cara kerja?** fasih-web bisa dikendalikan Playwright. fasih-sm &
manajemen-mitra mendeteksi browser otomatis, jadi untuk keduanya skrip Python hanya
*menyiapkan* file `*.siap.js`, lalu Anda menempelkannya di DevTools Console Chrome biasa
yang sudah login.

---

## Prasyarat

- **VPN kantor BPS aktif** — fasih-web/fasih-sm tidak bisa diakses tanpa itu.
- **Python 3.10+** (diuji di 3.12) dan **Google Chrome**.
- **Node.js** — opsional, hanya untuk menjalankan uji skrip Console.
- Akun petugas SE2026 (PPL/PML) dan, untuk alat fasih-sm, akun dengan hak admin kabupaten.

## Mulai cepat

```bash
git clone <url-repo-ini>
cd split_usaha
pip install -r requirements.txt
playwright install chromium
```

1. **Konfigurasi lokal** (sekali) — salin templat, lalu isi password & kode kabupaten:

   ```bash
   copy templates\config_lokal.contoh.py inti\config_lokal.py
   ```

   (Linux/macOS: `cp templates/config_lokal.contoh.py inti/config_lokal.py`.)
   `inti/config_lokal.py` ada di `.gitignore`, jadi password tidak ikut ter-commit. Templat ini
   sudah menyalakan mode murni.

2. **Siapkan data** — salin `templates/input_usaha.kosong.xlsx` ke root proyek sebagai `input_usaha.xlsx`,
   lalu isi tab `input_usaha` dengan hasil pendataan lapangan (lihat tab `petunjuk` di
   `input_usaha.contoh.xlsx` untuk arti tiap kolom).

3. **Periksa offline** (tanpa browser/VPN):

   ```bash
   python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --cek
   ```

4. **Dry-run** (browser terbuka, mengisi tapi tidak mengirim), lalu tinjau hasilnya di fasih-web.
5. **Kirim** hanya setelah dry-run bersih: tambah `--submit` dan ketik `YA` saat diminta.

Urutan lengkap (reset password → ganti mode → cek → input → approve → pindah wilayah) ada di
[`docs/TUTORIAL_INPUT_OTOMATIS.md`](docs/TUTORIAL_INPUT_OTOMATIS.md).

> Semua perintah dijalankan **dari root proyek** (folder berisi `README.md` ini).

---

## Templat

| File | Untuk | Dipakai oleh |
| --- | --- | --- |
| [`templates/config_lokal.contoh.py`](templates/config_lokal.contoh.py) | Password, `KODE_KAB`, mode murni, akun & subsls tunggal, kodepos/wilayah, path peta | salin ke `inti/config_lokal.py` |
| [`templates/input_usaha.kosong.xlsx`](templates/input_usaha.kosong.xlsx) | Format standar **kosong**: tab `input_usaha` (92 kolom, dropdown opsi form) | `input_gabungan/`, `reset_mitra/`, `ganti_moda/`, `pindah_wilayah/` (`--sumber`) |
| [`templates/input_usaha.contoh.xlsx`](templates/input_usaha.contoh.xlsx) | Format standar + tab `petunjuk`, `contoh` (perdagangan & produksi), `Nama Wilayah` | rujukan saat mengisi |
| [`templates/salin_dokumen_sumber.contoh.csv`](templates/salin_dokumen_sumber.contoh.csv) | Header backlog alur salin dari dokumen sumber | `input_fasihweb/main.py --csv` |
| [`templates/daftar_idsubsls.contoh.txt`](templates/daftar_idsubsls.contoh.txt) | Daftar idsubsls, satu per baris | `buka_wilayah/`, `tandai_selesai/` (`--daftar`) |
| [`templates/daftar_kode_identitas.contoh.txt`](templates/daftar_kode_identitas.contoh.txt) | Daftar kode identitas assignment | `ganti_moda/ubah_moda.py --daftar` |
| [`templates/rencana_approve.contoh.csv`](templates/rencana_approve.contoh.csv) | Rencana approve multi-PML | `approve_pml/approve_pml.py --rencana` |

Detail tiap templat: [`templates/README.md`](templates/README.md).

---

## Menyesuaikan untuk kabupaten Anda

Semua diisi di `inti/config_lokal.py`. Nama apa pun di `inti/config.py` boleh ditimpa di sana.

| Pengaturan | Wajib? | Keterangan |
| --- | --- | --- |
| `FIXED_PASSWORD` | ya | Password SSO yang sama untuk semua akun petugas yang dipakai skrip (disamakan lewat `reset_mitra/`). Bisa juga lewat variabel lingkungan `FASIH_PASSWORD`. Kosong → skrip berhenti sebelum login. |
| `KODE_KAB` | ya | 2 digit provinsi + 2 digit kab/kota, awalan idsubsls. Dipakai memvalidasi daftar wilayah & disuntikkan ke skrip Console. |
| `GABUNGAN_MODE_MURNI` | disarankan `True` | Isian 100% dari Excel, tanpa aturan/default/koreksi Buleleng (lihat [spesifikasi](docs/FORMAT_STANDAR_INPUT_USAHA.md#dua-mode-pengisian)). |
| `GABUNGAN_SUBSLS_TUNGGAL`, `GABUNGAN_AKUN_TUNGGAL` | format standar | Subsls & akun PPL tempat semua dokumen dibuat (bisa juga lewat `--subsls-tunggal` / `--akun-tunggal`). |
| `ASSIGNMENT_ID_GABUNGAN` | cek | Segmen kedua URL list PENDATAAN fasih-web (`/survey/<SURVEY_ID>/<ini>`). Bawaan = periode SE2026 yang dipakai di Buleleng. |
| `SURVEY_ID` | jarang | ID survei SE2026 di URL fasih-web; kemungkinan sama secara nasional. |
| `KODEPOS_BY_IDSUBSLS` | alur salin | Kodepos per idsubsls untuk `input_fasihweb/`. Format standar membaca kodepos dari sheet. |
| `WILAYAH_BY_IDSUBSLS` | tidak | Nama wilayah per idsubsls, hanya referensi log/pencocokan. |
| `PETA_SLS_PATH` | tidak | GeoJSON batas SUBSLS untuk `rencana_ubah_wilayah.py` (atau pakai `--tanpa-peta`). |

**Keputusan lokal Buleleng.** Tanpa mode murni, format standar memakai aturan yang ditetapkan
BPS Buleleng (nama `<usaha> (<pemilik>)`, 13f disalin dari 13a, default rincian 19/20, dan
koreksi data `KOREKSI_*` di `inti/gabungan_loader.py`). Alur salin dari dokumen sumber juga punya
aturan sendiri (nilai finansial 10%, NIK `9999`, aset & luas tanah `0`, aturan pekerja ≤ 3 orang).
Semuanya diberi komentar "ketetapan user" di kode. Tinjau dulu sebelum mengirim data sungguhan.

---

## Aturan keselamatan (ringkas)

1. **Default selalu dry-run / read-only.** Eksekusi butuh flag eksplisit (`--submit`,
   `--eksekusi`, `mode: "eksekusi"`) dan konfirmasi ketik `YA`.
2. **Mulai dengan `--limit 1`** di setiap alat yang menulis, periksa hasilnya di web, baru perbesar.
3. **GALAT harus 0 sebelum Kirim.** Skrip melewati dokumen yang masih GALAT — jangan ditebak.
4. **Jangan menyentuh "Nomor Urut Bangunan"** saat mengisi manual di dokumen yang sedang diproses skrip.
5. **Satu akun = satu proses.** Jangan menjalankan dua proses dengan akun yang sama.
6. **Jalankan headed** (jendela browser terlihat) — fasih-web menolak browser headless.

Penjelasan lengkap & alasannya ada di panduan per alat (`docs/`).

## Privasi data

Repo ini **publik**. `.gitignore` sudah menahan data sensus & rahasia: `*.xlsx`, `*.csv`,
`export/`, `audit_*`, `*.siap.js`, `list_api_*.json`, `log_*`, profil/sesi browser, dan
`inti/config_lokal.py`. Satu-satunya pengecualian adalah folder `templates/` — isinya harus
tetap kosong/fiktif. Sebelum commit, selalu cek `git status` dan jangan pernah menyalin
email petugas, nama responden, NIK, nomor HP, atau link Google Sheet ke file yang ikut git.

---

## Uji offline

```bash
python tests/jalankan_semua.py
```

Menjalankan semua `tests/test_*.py` dan (kalau Node.js ada) `tests/test_*.js` — tanpa VPN,
tanpa browser. Uji memakai data contoh Buleleng di `inti/config.py` dan mengabaikan
`inti/config_lokal.py`, jadi hasilnya sama di komputer mana pun. Jalankan setiap kali
mengubah kode, terutama selektor (`tests/test_selectors.py`).

## Dokumentasi

| Dokumen | Isi |
| --- | --- |
| [`docs/MULAI_CEPAT.md`](docs/MULAI_CEPAT.md) | **Mulai di sini kalau menyiapkan PC baru**: setup, satu perintah jalan, pembagian baris antar-PC |
| [`docs/FORMAT_STANDAR_INPUT_USAHA.md`](docs/FORMAT_STANDAR_INPUT_USAHA.md) | **Spesifikasi format standar**: kolom per jenis usaha, mode murni, aturan pemeriksaan |
| [`docs/TUTORIAL_INPUT_OTOMATIS.md`](docs/TUTORIAL_INPUT_OTOMATIS.md) | Tutorial end-to-end inject usaha dari format standar |
| [`docs/PANDUAN_GABUNGAN.md`](docs/PANDUAN_GABUNGAN.md) | Referensi `main_gabungan.py`: mode satu subsls, status audit, setelan |
| [`docs/PANDUAN_INPUT_TAHAP2.md`](docs/PANDUAN_INPUT_TAHAP2.md) | Input hasil pendataan KERTAS tahap 2 (`main_tahap2.py`) |
| [`docs/PANDUAN_INPUT_OTOMATIS.md`](docs/PANDUAN_INPUT_OTOMATIS.md), [`docs/PANDUAN_EKSPOR_MANUAL.md`](docs/PANDUAN_EKSPOR_MANUAL.md) | Alur salin dari dokumen sumber (`salin_dokumen_sumber.csv` + export fasih-sm) |
| [`docs/PANDUAN_UBAH_MODA.md`](docs/PANDUAN_UBAH_MODA.md) | Ganti mode CAPI → PAPI |
| [`docs/PANDUAN_RESET_MITRA.md`](docs/PANDUAN_RESET_MITRA.md) | Reset password mitra |
| [`docs/PANDUAN_BUKA_WILAYAH.md`](docs/PANDUAN_BUKA_WILAYAH.md), [`docs/PANDUAN_TANDAI_SELESAI.md`](docs/PANDUAN_TANDAI_SELESAI.md) | Buka / tandai selesai wilayah |
| [`docs/PANDUAN_PINDAH_WILAYAH.md`](docs/PANDUAN_PINDAH_WILAYAH.md) | Pindah wilayah dokumen |
| [`docs/PANDUAN_GABUNG_AUDIT.md`](docs/PANDUAN_GABUNG_AUDIT.md) | Menggabungkan progres beberapa PC & laporannya |
| [`docs/catatan usaha pecahan se2026.md`](docs/catatan%20usaha%20pecahan%20se2026.md) | Temuan awal perilaku form fasih-web |

Tanggal di dokumen-dokumen itu (2026-09-xx) adalah tanggal temuan saat skrip dikembangkan.
Perilaku fasih-web/fasih-sm bisa berubah — kalau skrip berhenti dengan pesan "tidak dikenal",
itu pengaman yang bekerja, bukan kesalahan yang perlu dipaksa lewat.

## Lisensi

[MIT](LICENSE) — bebas dipakai, disalin, diubah, dan dibagikan ulang, asalkan pemberitahuan
hak cipta & lisensi tetap disertakan. Perangkat lunak disediakan "apa adanya" tanpa jaminan;
tanggung jawab atas data yang dikirim lewat skrip ini ada pada penggunanya.
