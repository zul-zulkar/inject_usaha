# Mulai cepat — satu perintah per PC

Halaman ini untuk PC **kedua dan seterusnya**: menyiapkan mesin baru lalu
menjalankan input dengan **satu perintah**. Penjelasan lengkap tiap bagian ada di
`PANDUAN_INPUT_TAHAP2.md` (format tahap 2), `PANDUAN_GABUNGAN.md` (format
standar) dan `PANDUAN_GABUNG_AUDIT.md` (menyatukan hasil antar-PC).

## 1. Siapkan PC (sekali saja)

```bash
pip install playwright
playwright install chromium
```

```bash
copy templates\config_lokal.contoh.py inti\config_lokal.py
```

Isi `inti/config_lokal.py`: `FIXED_PASSWORD`, `KODE_KAB`, dan (kalau perlu)
`KODEPOS_BY_IDSUBSLS`. Tanpa password, skrip berhenti sendiri — tidak pernah
menebak.

Salin **tiga berkas** dari PC utama ke folder proyek:

| Berkas | Taruh di | Kenapa |
| --- | --- | --- |
| `bahan/input_tahap2.xlsx` | `bahan/` | data yang diinput |
| `audit_log_gabungan.csv` | root proyek | ingatan anti-duplikat; tanpa ini dokumen bisa dibuat dua kali |
| `inti/config_lokal.py` | `inti/` | boleh disalin utuh dari PC lain |

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

| Flag | Gunanya |
| --- | --- |
| `--sinkron-dulu` | baca daftar dokumen di server dulu, catat ke audit — dokumen buatan PC lain dikenali & dibuka, bukan dibuat ulang |
| `--lewati-selesai` | lewati baris yang memang sudah tuntas |
| `--izinkan-wilayah-beda` | jangan berhenti kalau dokumen ada di subsls lain milik akun yang sama (wadah sementara) |
| `--submit` | benar-benar mengirim (tanpa ini cuma dry-run) |
| `--dari/--sampai` | jatah baris PC ini |

Urutan kerjanya sudah otomatis: **draft bertanda error di server** dikerjakan
lebih dulu, lalu dokumen yang sudah ada, baru baris yang belum punya dokumen.

### Kalau mau membereskan error saja

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --hanya-galat --izinkan-wilayah-beda --submit
```

## 4. Bagi rentang baris antar-PC

**Jangan sampai tumpang tindih**, dan **satu akun hanya untuk satu PC pada satu
waktu** — dua proses dengan akun sama saling memutus sesi login.

| PC | Rentang |
| --- | --- |
| PC1 | `--dari 2 --sampai 500` |
| PC2 | `--dari 501 --sampai 1000` |
| PC3 | `--dari 1001 --sampai 1500` |
| PC4 | `--dari 1501 --sampai 2000` |
| PC5 | `--dari 2001` |

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

| Pesan | Artinya | Tindakan |
| --- | --- | --- |
| `STOP_WILAYAH_DOKUMEN_BEDA` | wilayah dokumen di luar kabupaten | benar-benar salah wilayah — jangan dipaksa |
| `SKIP_DOKUMEN_BELUM_ADA` | subsls itu belum punya assignment | buat satu dokumen manual dulu |
| `ERROR_AKUN_SALAH` | sesi nyangkut di akun lain | jalankan ulang; skrip membersihkan cookie sendiri |
| `DRAFT_TANPA_KOORDINAT` | bukan galat | isi Latitude/Longitude di Excel, lalu jalankan ulang perintah yang sama |
| `DOKUMEN_TERKUNCI` | dokumen read-only di UI (padahal daftar server bisa bilang DRAFT) | PPL tidak bisa apa-apa — minta admin/PML memeriksa. Sesudah dibuka, jalankan dengan `--coba-terkunci` |

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

| Yang ditemukan | Yang ditulis | Akibatnya |
| --- | --- | --- |
| dokumen bernama sama **ada** | `DOKUMEN_DIBUAT` + URL-nya | run berikutnya membuka dokumen itu & melanjutkannya |
| **tidak ada**, dan tidak ada DRAFT kosong tanpa nama | `DOKUMEN_DIHAPUS` (catatan digugurkan) | run berikutnya **membuat usahanya dari awal** |
| tidak ada, tapi ada DRAFT kosong tanpa nama | tidak ada — dilaporkan `TANDA_TANPA_URL_PERIKSA_MANUAL` | dokumen baris itu bisa jadi salah satu DRAFT kosong itu; minta admin menghapusnya, lalu jalankan sinkron lagi |

Jalankan dulu tanpa `--tulis` untuk melihat keputusannya di kolom `kategori`
(`sinkron_list.csv`) sebelum apa pun ditulis.

Batch tetap berhenti kalau ini terjadi **3 kali dalam satu run** (`--maks-tanpa-url`,
0 = jangan pernah berhenti): sebanyak itu artinya "Buat Dokumen" memang sedang
rusak, dan meneruskannya cuma menumpuk dokumen kosong.
