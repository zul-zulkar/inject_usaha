# Otomatisasi Input SE2026 "Usaha Pecahan" — fasih-web & fasih-sm

Kumpulan skrip Python (Playwright) dan skrip Console Chrome untuk membantu pekerjaan
**Sensus Ekonomi 2026**: membuat, mengisi, dan mengirim dokumen SE2026-P "Usaha Pecahan"
di **fasih-web**, lalu alat pendukungnya di **fasih-sm** & **manajemen-mitra**: ganti mode
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

## Isi repo

| Folder | Fungsi | Sistem | Cara kerja |
| --- | --- | --- | --- |
| [`input_gabungan/`](input_gabungan/) | **Alur utama**: buat & isi dokumen SE2026-P dari sheet **Agenda** (tab `gabungan`), sinkron list, rencana ubah wilayah | fasih-web | Playwright (browser terbuka) |
| [`input_fasihweb/`](input_fasihweb/) | Alur lama: backlog `LKpenyalinan.csv` + file export fasih-sm (nilai 10%) | fasih-web | Playwright |
| [`approve_pml/`](approve_pml/) | Approve dokumen oleh akun PML (Pengawas) | fasih-web | Playwright |
| [`ganti_moda/`](ganti_moda/) | Ganti mode assignment CAPI → PAPI supaya "+ Dokumen Baru" muncul | fasih-sm | Console Chrome |
| [`reset_mitra/`](reset_mitra/) | Seragamkan password akun PPL | manajemen-mitra | Console Chrome |
| [`buka_wilayah/`](buka_wilayah/) | Buka Wilayah (batal "Selesai Listing") | fasih-sm | Console Chrome |
| [`tandai_selesai/`](tandai_selesai/) | Tandai Selesai Listing | fasih-sm | Console Chrome |
| [`pindah_wilayah/`](pindah_wilayah/) | Pindah wilayah (Change Region) dokumen yang sudah di-approve | fasih-sm | Console Chrome |
| [`inti/`](inti/) | Modul bersama: konfigurasi, loader data, interaksi fasih-web | — | — |
| [`templates/`](templates/) | **Templat kosong** untuk memulai (sheet Agenda, CSV, daftar kode, config lokal) | — | — |
| [`docs/`](docs/) | Panduan langkah-demi-langkah per alat | — | — |
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
   `inti/config_lokal.py` ada di `.gitignore`, jadi password tidak ikut ter-commit.

2. **Siapkan data** dari templat di [`templates/`](templates/) — untuk alur utama salin
   `templates/Agenda.contoh.xlsx` ke root sebagai `Agenda.xlsx` lalu isi tab `gabungan`
   (tab `petunjuk` menjelaskan setiap kolom).

3. **Periksa offline** (tanpa browser/VPN):

   ```bash
   python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --cek
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
| [`templates/config_lokal.contoh.py`](templates/config_lokal.contoh.py) | Password, `KODE_KAB`, akun & subsls tunggal, kodepos/wilayah, path peta | salin ke `inti/config_lokal.py` |
| [`templates/Agenda.contoh.xlsx`](templates/Agenda.contoh.xlsx) | Sheet Agenda: tab `gabungan` kosong (83 kolom persis, dropdown opsi), `petunjuk`, `contoh` | `input_gabungan/`, `reset_mitra/`, `ganti_moda/`, `pindah_wilayah/` (`--sumber`) |
| [`templates/LKpenyalinan.contoh.csv`](templates/LKpenyalinan.contoh.csv) | Header backlog alur lama | `input_fasihweb/main.py --csv` |
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
| `GABUNGAN_SUBSLS_TUNGGAL`, `GABUNGAN_AKUN_TUNGGAL` | alur Agenda | Subsls & akun PPL tempat semua dokumen dibuat (bisa juga lewat `--subsls-tunggal` / `--akun-tunggal`). |
| `ASSIGNMENT_ID_GABUNGAN` | cek | Segmen kedua URL list PENDATAAN fasih-web (`/survey/<SURVEY_ID>/<ini>`). Bawaan = periode SE2026 yang dipakai di Buleleng. |
| `SURVEY_ID` | jarang | ID survei SE2026 di URL fasih-web; kemungkinan sama secara nasional. |
| `KODEPOS_BY_IDSUBSLS` | alur lama | Kodepos per idsubsls untuk `input_fasihweb/`. Alur Agenda membaca kodepos dari sheet. |
| `WILAYAH_BY_IDSUBSLS` | tidak | Nama wilayah per idsubsls, hanya referensi log/pencocokan. |
| `PETA_SLS_PATH` | tidak | GeoJSON batas SUBSLS untuk `rencana_ubah_wilayah.py` (atau pakai `--tanpa-peta`). |

**Keputusan lokal yang perlu Anda tinjau.** Beberapa aturan pengisian adalah ketetapan
BPS Buleleng, bukan aturan form — terutama di alur lama (`input_fasihweb/`): nilai
finansial = 10% nilai sumber, NIK diisi `9999`, aset & luas tanah `0`, aturan pekerja ≤ 3
orang, default rincian 13b/16b/19/20, dan koreksi nama/badan usaha di
`inti/gabungan_loader.py` (`KOREKSI_*`). Semuanya diberi komentar "ketetapan user" di kode.
Sesuaikan dengan kebijakan kabupaten Anda **sebelum** mengirim data sungguhan.

---

## Aturan keselamatan (ringkas)

1. **Default selalu dry-run / read-only.** Eksekusi butuh flag eksplisit (`--submit`,
   `--eksekusi`, `mode: "eksekusi"`) dan konfirmasi ketik `YA`.
2. **Mulai dengan `--limit 1`** di setiap alat yang menulis, periksa hasilnya di web, baru perbesar.
3. **GALAT harus 0 sebelum Kirim.** Skrip melewati dokumen yang masih GALAT — jangan ditebak.
4. **Jangan menyentuh "Nomor Urut Bangunan"** saat mengisi manual di dokumen yang sedang diproses skrip.
5. **Satu akun = satu proses.** Jangan menjalankan dua proses dengan akun yang sama.
6. **Jalankan headed** (jendela browser terlihat) — fasih-web menolak browser headless.

Penjelasan lengkap & alasannya ada di [`CLAUDE.md`](CLAUDE.md) (bagian "ATURAN KESELAMATAN") dan di
panduan per alat.

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
| [`docs/TUTORIAL_INPUT_OTOMATIS.md`](docs/TUTORIAL_INPUT_OTOMATIS.md) | Tutorial end-to-end alur Agenda |
| [`docs/PANDUAN_GABUNGAN.md`](docs/PANDUAN_GABUNGAN.md) | Referensi alur Agenda: status audit, keputusan skrip |
| [`docs/PANDUAN_INPUT_OTOMATIS.md`](docs/PANDUAN_INPUT_OTOMATIS.md), [`docs/PANDUAN_EKSPOR_MANUAL.md`](docs/PANDUAN_EKSPOR_MANUAL.md) | Alur lama (LKpenyalinan + export fasih-sm) |
| [`docs/PANDUAN_UBAH_MODA.md`](docs/PANDUAN_UBAH_MODA.md) | Ganti mode CAPI → PAPI |
| [`docs/PANDUAN_RESET_MITRA.md`](docs/PANDUAN_RESET_MITRA.md) | Reset password mitra |
| [`docs/PANDUAN_BUKA_WILAYAH.md`](docs/PANDUAN_BUKA_WILAYAH.md), [`docs/PANDUAN_TANDAI_SELESAI.md`](docs/PANDUAN_TANDAI_SELESAI.md) | Buka / tandai selesai wilayah |
| [`docs/PANDUAN_PINDAH_WILAYAH.md`](docs/PANDUAN_PINDAH_WILAYAH.md) | Pindah wilayah dokumen |
| [`docs/catatan usaha pecahan se2026.md`](docs/catatan%20usaha%20pecahan%20se2026.md) | Temuan awal perilaku form fasih-web |
| [`CLAUDE.md`](CLAUDE.md) | Catatan teknis lengkap (arsitektur, jebakan selektor, temuan per run). Dimuat otomatis oleh Claude Code. |

Tanggal di dokumen-dokumen itu (2026-09-xx) adalah tanggal temuan saat skrip dikembangkan.
Perilaku fasih-web/fasih-sm bisa berubah — kalau skrip berhenti dengan pesan "tidak dikenal",
itu pengaman yang bekerja, bukan kesalahan yang perlu dipaksa lewat.

## Lisensi

[MIT](LICENSE) — bebas dipakai, disalin, diubah, dan dibagikan ulang, asalkan pemberitahuan
hak cipta & lisensi tetap disertakan. Perangkat lunak disediakan "apa adanya" tanpa jaminan;
tanggung jawab atas data yang dikirim lewat skrip ini ada pada penggunanya.
