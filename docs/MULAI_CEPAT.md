# Mulai cepat — satu perintah per PC

Halaman ini untuk PC **kedua dan seterusnya**: menyiapkan mesin baru lalu
menjalankan input dengan **satu perintah**. Penjelasan lengkap tiap bagian ada di
`PANDUAN_INPUT_TAHAP2.md` (format tahap 2), `PANDUAN_GABUNGAN.md` (format
standar) dan `PANDUAN_GABUNG_AUDIT.md` (menyatukan hasil antar-PC).

## 1. Siapkan PC (sekali saja)

Cara termudah: bungkus seluruh proyek di PC utama jadi **satu zip ringan**, lalu
extract di PC tujuan.

### 1a. Di PC utama — buat zip

Lihat dulu apa saja yang ikut & ukurannya (tidak membuat apa pun):

```bash
python bungkus_pc/bungkus_pc.py --daftar
```

Buat zip-nya:

```bash
python bungkus_pc/bungkus_pc.py
```

Hasilnya `split_usaha_pc_<tanggal-jam>.zip` di folder proyek (±8 MB; folder
aslinya ratusan MB karena cache & profil browser).

| Ikut                                                        | Tidak ikut                                                                                                           |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| semua kode,`docs/`, `templates/`, `tests/`            | cache:`__pycache__/`, `.git/`, `*.zip`, `.claude/`                                                           |
| `bahan/`, `Agenda*.xlsx`, `export/` & data kerja lain | sesi & profil browser (`.profil_*`, `.sesi_*`) — login ulang di PC tujuan                                       |
| `inti/config_lokal.py` (password, kodepos)                | log & screenshot                                                                                                     |
| audit lain (`audit_approve_pml.csv`, `audit_log.csv`)   | cadangan audit (`*.bak-*`) & audit per-PC (`audit_pc/`)                                                        |
| **`audit_log_gabungan.csv`** (sejak 2026-09-24)       |                                                                                                                        |
|                                                             | laporan yang bisa dibuat ulang (`cek_gabungan.csv`, `rangkum_audit.csv`, `*.siap.js`, `list_api_*.json`, …) |

⚠️ Zip ini berisi **data responden dan password**. Pindahkan lewat flashdisk atau
drive kantor — jangan diunggah ke tempat publik.

⚠️ **`audit_log_gabungan.csv` IKUT di zip** (sejak 2026-09-24), supaya hasil
`gabung_audit` bisa disebar ke semua PC sekaligus. Konsekuensinya: meng-extract zip
di PC yang **sudah bekerja lagi** akan **menimpa audit PC itu** — catatan dokumen
yang sudah dibuatnya hilang, lalu dokumennya dibuat dua kali (dan PPL tidak bisa
menghapus dokumen).

Jadi zip ini hanya boleh disebar **sesudah semua PC berhenti dan auditnya digabung**
(`docs/PANDUAN_GABUNG_AUDIT.md`). Kalau sebuah PC masih punya pekerjaan yang belum
masuk gabungan, jangan extract zip ini di sana — perbarui kodenya saja, lalu salin
auditnya ke PC utama dulu (bagian 5).

### 1b. Di PC tujuan — extract & pasang

1. Extract zip-nya: klik kanan → **Extract All** → pilih `D:\`. Hasilnya folder
   `D:\split_usaha`. Atau lewat PowerShell:

   ```powershell
   Expand-Archive -Path split_usaha_pc_XXXX.zip -DestinationPath D:\ -Force
   ```

   Kalau PC itu **sudah punya** folder proyek, extract ke tempat yang sama akan
   memperbarui kode & bahan — **dan menimpa `audit_log_gabungan.csv` PC itu** dengan
   audit gabungan dari zip. Itu memang yang diinginkan sesudah penggabungan; kalau
   PC itu masih menyimpan pekerjaan yang belum digabung, salin auditnya keluar dulu.
2. Pasang pustaka (sekali per PC; butuh Python):

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Masuk ke folder proyek dan pastikan semuanya jalan (tanpa VPN, beberapa detik):

   ```bash
   python tests/jalankan_semua.py
   ```

`inti/config_lokal.py` sudah ikut di zip, jadi tidak perlu disalin dari templat.
(Kalau memasang dari GitHub, bukan dari zip: `copy templates\config_lokal.contoh.py inti\config_lokal.py`,
lalu isi `FIXED_PASSWORD`, `KODE_KAB`, dan kalau perlu `KODEPOS_BY_IDSUBSLS`. Tanpa
password, skrip berhenti sendiri — tidak pernah menebak.)

### 1c. Audit di PC tujuan

| Keadaan PC tujuan                             | Yang dilakukan                                                                                                                                  |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| PC baru, belum pernah input                   | tidak perlu apa-apa — audit gabungan sudah ikut di zip                                                                                          |
| sudah bekerja & auditnya SUDAH masuk gabungan | extract saja; audit lamanya memang diganti audit gabungan                                                                                        |
| sudah bekerja & auditnya BELUM digabung       | salin `audit_log_gabungan.csv` PC itu ke PC utama dulu (bagian 5), gabungkan, buat zip baru — baru extract                                       |

Sebagai jaring pengaman, `--sinkron-dulu` di perintah bagian 3 tetap membaca daftar
dokumen server untuk akun yang dipakai sebelum mulai, jadi dokumen akun itu yang
sudah ada dikenali, bukan dibuat ulang.

Terakhir: **VPN kantor harus aktif**, dan jangan jalankan headless (ditolak).

## 2. Periksa data dulu — tanpa browser, beberapa detik

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --cek
```

Rinciannya ke `cek_gabungan.csv`. Baris yang ter-skip di sini tidak akan
dikerjakan, jadi tidak ada gunanya menunggu browser untuk mengetahuinya.

## 3. Jalankan — satu perintah

Ganti `EMAIL`, `SUBSLS`, dan rentang barisnya:

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --dari 2 --sampai 500 --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda --submit
```

Skrip akan berhenti sekali untuk minta konfirmasi: **ketik `YA`**. Sesudah itu
jalan sendiri sampai rentangnya habis.

Apa yang dikerjakan perintah itu, berurutan:

| Flag                       | Gunanya                                                                                                            |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `--sinkron-dulu`         | baca daftar dokumen di server dulu, catat ke audit — dokumen buatan PC lain dikenali & dibuka, bukan dibuat ulang |
| `--lewati-selesai`       | lewati baris yang memang sudah tuntas                                                                              |
| `--izinkan-wilayah-beda` | jangan berhenti kalau dokumen ada di subsls lain milik akun yang sama (wadah sementara)                            |
| `--submit`               | benar-benar mengirim (tanpa ini cuma dry-run)                                                                      |
| `--dari/--sampai`        | jatah baris PC ini                                                                                                 |

Urutan kerjanya sudah otomatis: **draft bertanda error di server** dikerjakan
lebih dulu, lalu dokumen yang sudah ada, baru baris yang belum punya dokumen.

### Kalau mau membereskan error saja

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --hanya-galat --izinkan-wilayah-beda --submit
```

## 4. Bagi rentang baris antar-PC

**Jangan sampai tumpang tindih**, dan **satu akun hanya untuk satu PC pada satu
waktu** — dua proses dengan akun sama saling memutus sesi login.

| PC  | Rentang                       |
| --- | ----------------------------- |
| PC1 | `--dari 2 --sampai 500`     |
| PC2 | `--dari 501 --sampai 1000`  |
| PC3 | `--dari 1001 --sampai 1500` |
| PC4 | `--dari 1501 --sampai 2000` |
| PC5 | `--dari 2001`               |

## 5. Selesai: kirim audit kembali

Setelah batch berhenti, salin `audit_log_gabungan.csv` PC ini ke PC utama
(`audit_pc/pc3.csv`, dst.), lalu di PC utama:

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc --tulis
```

Hasil gabungannya disebar lagi ke semua PC. Gabungkan **setelah** semua batch
berhenti, bukan saat masih jalan.

## 6. Rekap progres

Ada empat tingkat. Urutan lengkapnya sesudah semua PC berhenti: gabung → sinkron
→ rangkum & bersihkan. Kalau cuma ingin angka progres, **6a saja sudah cukup**.

### 6a. Progres per baris sheet — offline, beberapa detik

Jumlah terkirim / draft / ditolak, plus alasan tiap baris yang TIDAK akan
dikerjakan run berikutnya. Rinciannya ke `rangkum_audit.csv`. Jalankan sekali per
akun (ganti `EMAIL` & `SUBSLS`):

```bash
python gabung_audit/rangkum_audit.py --sumber bahan/input_tahap2.xlsx --format tahap2 --akun-tunggal EMAIL --subsls-tunggal SUBSLS
```

Rekap **semua akun sekaligus**: hilangkan `--akun-tunggal` & `--subsls-tunggal`.

```bash
python gabung_audit/rangkum_audit.py --sumber bahan/input_tahap2.xlsx --format tahap2
```

Bagian `PROGRES` angkanya sama persis (dihitung dari audit, tidak bergantung
akun). Bedanya di `RUN BERIKUTNYA`: yang dihitung hanya baris yang **belum punya
dokumen di akun mana pun**, dan baris yang sudah punya dokumen muncul di `ALASAN`
sebagai "dokumennya sudah dibuat proses lain (akun / subsls)" — itu sekaligus
rincian jumlah baris per akun.

Bagian **`BELUM TUNTAS & ERROR`** mendaftar nomor baris per keadaan, formatnya
sama dengan laporan sinkron:

| Keadaan | Artinya |
| --- | --- |
| Audit bilang terkirim, server masih DRAFT | dikirim ulang lewat URL oleh run berikutnya |
| Draft ber-GALAT di server | dikerjakan paling dulu oleh run berikutnya (jumlah galatnya ikut dicetak) |
| Draft tanpa koordinat, koordinat SUDAH ada di sheet | tinggal geotag & kirim |
| Draft tanpa koordinat — menunggu | isi Latitude/Longitude di Excel dulu |
| Dokumen sudah dibuat, pengisian belum selesai | dibuka lewat URL oleh run berikutnya |
| Toast "terkirim" tanpa bukti server | pastikan dengan `sinkron_list.py` |
| Dokumen tanpa URL tercatat | jalankan `sinkron_list.py --tulis` dulu |
| Dokumen read-only padahal server DRAFT | perlu admin/PML |
| Gagal di run terakhir | dirinci per status + pesan error terbarunya |

Status server dibaca dari `list_api_*.json` hasil `sinkron_list.py` (bagian 6c)
kalau berkasnya ada; jam berkas terbaru ikut dicetak, karena berkas lama bisa
ketinggalan. Tanpa berkas itu (atau dengan `--tanpa-server`), rekapnya murni dari
audit. Daftar lengkap per baris ada di kolom `rekap`, `status_server`,
`galat_server` dan `pesan_terakhir` di `rangkum_audit.csv`.

### 6b. Satukan audit beberapa PC

Salin `audit_log_gabungan.csv` tiap PC ke folder `audit_pc/` (nama berbeda,
mis. `pc1.csv`, `pc2.csv`). Lihat laporannya dulu — tidak menulis apa pun:

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc
```

Tidak ada peringatan bentrok → tulis hasil gabungannya (audit lama otomatis
dicadangkan `.bak-<waktu>`):

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc --tulis
```

Keduanya juga menulis **`daftar_ganda.csv`**: dokumen ganda (satu baris sheet, ≥ 2
dokumen di server) beserta usulan mana yang dipertahankan/dihapus. Menghapusnya butuh
akun **admin** fasih-sm — lihat `docs/PANDUAN_HAPUS_GANDA.md`:

```bash
python hapus_ganda/hapus_ganda.py
```

### 6c. Cocokkan dengan server — butuh VPN, hanya membaca

Audit bisa mencatat "terkirim" padahal server masih DRAFT (toast sukses ≠
terkirim). Tanpa `--tulis` cuma laporan (`sinkron_list.csv`); tambahkan `--tulis`
untuk mencatat hasilnya ke audit:

```bash
python input_gabungan/sinkron_list.py --sumber bahan/input_tahap2.xlsx --format tahap2 --akun-tunggal EMAIL --subsls-tunggal SUBSLS
```

### 6d. Sisa error + perintah untuk membereskannya — offline

Dikelompokkan jadi `ULANGI` / `LENGKAPI_KOORDINAT` / `PERBAIKI_DATA` /
`SINKRON_DULU` / `TUNGGU_KOORDINAT` / `MANUAL`, lengkap dengan perintah siap
jalan. Hasilnya ke `bersihkan_error.csv`:

```bash
python gabung_audit/bersihkan_error.py --sumber bahan/input_tahap2.xlsx --format tahap2
```

## Kalau berhenti di tengah

| Pesan                         | Artinya                                                           | Tindakan                                                                                                |
| ----------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `STOP_WILAYAH_DOKUMEN_BEDA` | wilayah dokumen di luar kabupaten                                 | benar-benar salah wilayah — jangan dipaksa                                                             |
| `SKIP_DOKUMEN_BELUM_ADA`    | subsls itu belum punya assignment                                 | buat satu dokumen manual dulu                                                                           |
| `ERROR_AKUN_SALAH`          | sesi nyangkut di akun lain                                        | jalankan ulang; skrip membersihkan cookie sendiri                                                       |
| `DRAFT_TANPA_KOORDINAT`     | bukan galat                                                       | isi Latitude/Longitude di Excel, lalu jalankan ulang perintah yang sama                                 |
| `DOKUMEN_TERKUNCI`          | dokumen read-only di UI (padahal daftar server bisa bilang DRAFT) | PPL tidak bisa apa-apa — minta admin/PML memeriksa. Sesudah dibuka, jalankan dengan`--coba-terkunci` |

Menjalankan ulang perintah yang sama **aman**: dokumen lama dibuka lewat URL di
audit, tidak dibuat ulang.

## Yang TIDAK menghentikan batch lagi

`DOKUMEN_TANPA_URL_PERLU_CEK` — dokumen kemungkinan terbuat tapi URL-nya tidak
tertangkap. Dulu batch berhenti di sini; sekarang barisnya **dilewati** dan batch
lanjut, jadi run malam tidak perlu ditunggui. Semuanya didaftar di akhir run dan
di `dokumen_tanpa_url.csv`: nomor baris, nama usaha, akun, subsls dan **jam
kejadiannya** — itu yang dipakai mencari dokumen DRAFT kosong di daftar server.

Baris seperti itu tidak pernah dikerjakan ulang otomatis (mengulanginya =
dokumen kedua, dan PPL tidak bisa menghapus dokumen). Membuka blokirnya:

```bash
python input_gabungan/sinkron_list.py --format tahap2 --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --tulis
```

Perintah itu memeriksa daftar dokumen di server dan memutuskan sendiri:

| Yang ditemukan                                             | Yang ditulis                                              | Akibatnya                                                                                                     |
| ---------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| dokumen bernama sama**ada**                          | `DOKUMEN_DIBUAT` + URL-nya                              | run berikutnya membuka dokumen itu & melanjutkannya                                                           |
| **tidak ada**, dan tidak ada DRAFT kosong tanpa nama | `DOKUMEN_DIHAPUS` (catatan digugurkan)                  | run berikutnya**membuat usahanya dari awal**                                                            |
| tidak ada, tapi ada DRAFT kosong tanpa nama                | tidak ada — dilaporkan`TANDA_TANPA_URL_PERIKSA_MANUAL` | dokumen baris itu bisa jadi salah satu DRAFT kosong itu; minta admin menghapusnya, lalu jalankan sinkron lagi |

Jalankan dulu tanpa `--tulis` untuk melihat keputusannya di kolom `kategori`
(`sinkron_list.csv`) sebelum apa pun ditulis.

Batch tetap berhenti kalau ini terjadi **3 kali dalam satu run** (`--maks-tanpa-url`,
0 = jangan pernah berhenti): sebanyak itu artinya "Buat Dokumen" memang sedang
rusak, dan meneruskannya cuma menumpuk dokumen kosong.
