# Panduan: menggabungkan progres beberapa PC (`gabung_audit/`)

Alur input otomatis bisa dijalankan di beberapa PC sekaligus supaya cepat. Yang
perlu disatukan sesudahnya cuma **satu berkas**: `audit_log_gabungan.csv`.

## Kenapa audit harus disatukan

`audit_log_gabungan.csv` bukan sekadar catatan. Berkas itulah yang dipakai skrip
untuk:

- `--lewati-selesai` — melewati baris yang dokumennya sudah selesai;
- mencegah dokumen dibuat **dua kali** untuk baris yang sama (`dokumen_per_kunci`);
- membuka kembali dokumen lewat URL-nya, bukan membuat yang baru.

Tiap PC menulis audit sendiri. Selama belum disatukan, PC A tidak tahu apa yang
sudah dikerjakan PC B. Kalau rentang barisnya sampai bersinggungan, dokumennya
jadi ganda di server — dan **PPL tidak bisa menghapus dokumen**, itu urusan admin
pusat.

## Aturan main saat membagi pekerjaan

1. **Satu akun hanya boleh dipakai satu PC pada satu waktu.** Dua proses dengan
   akun sama saling memutus sesi login. Di satu PC hal ini dijaga berkas kunci
   `.proses_<akun>.lock`, tapi kunci itu **tidak berlaku lintas PC** — pembagian
   akun adalah tanggung jawab Anda.
2. **Bagi rentang barisnya, jangan sampai tumpang tindih**, mis. PC1
   `--dari 2 --sampai 500`, PC2 `--dari 501 --sampai 1000`, dst.
3. Satukan audit **setelah** semua batch berhenti, bukan saat masih jalan.
4. **Jangan pernah menyimpan audit dari Excel.** Membuka `audit_log_gabungan.csv` di Excel
   lalu Save mengubah kunci `1404364e03` jadi `1.40E+09` dan idsubsls jadi `5.10806E+15`.
   Baris itu tidak dikenali lagi, jadi skrip membuat dokumen **GANDA** atau berhenti
   `SKIP_NAMA_DIPAKAI_BARIS_LAIN`. Untuk dibaca di Excel, pakai `rangkum_audit.csv`. Semua alat
   (batch, sinkron, gabung, rangkum, bungkus) kini menolak audit yang rusak begini — lihat
   [Audit rusak karena Excel](#audit-rusak-karena-excel).

## Langkah

### 1. Kumpulkan audit (dan sheet bahan) tiap PC ke satu folder

Cara paling mudah: satu **subfolder per PC**, dan berkasnya disalin apa adanya tanpa
ganti nama. Sheet bahan PC itu ikut ditaruh di subfolder yang sama (lihat
[kolom ID](#menggabungkan-kolom-id-dokumen-fasih-di-sheet-bahan)):

```
audit_pc/
  pc2/
    audit_log_gabungan.csv
    input_tahap2.xlsx
  pc3/
    audit_log_gabungan.csv
    input_tahap2.xlsx
  ...
```

`gabung_audit` hanya mengambil CSV audit dari folder itu, sedangkan
`gabung_id_sumber` hanya mengambil sheet yang punya kolom "ID Dokumen FASIH".
Berkas lain dilewati dan disebut di layar. Cara lama (semua audit langsung di
`audit_pc/` dengan nama berbeda, mis. `pc1.csv`, `pc2.csv`) tetap bisa.

### 2. Lihat laporannya dulu (tidak menulis apa pun)

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc
```

Keluarannya:

| Bagian                            | Isi                                                        |
| --------------------------------- | ---------------------------------------------------------- |
| SUMBER                            | jumlah baris, jumlah dokumen & rentang waktu tiap PC       |
| PER AKUN                          | dokumen per akun petugas, dipecah per status               |
| PER WILAYAH TEMPAT DOKUMEN DIBUAT | rekap per`idsubsls_input`                                |
| PER WILAYAH ASLI BARIS            | rekap per`idsubsls` — bahan pindah wilayah nanti        |
| PER BERKAS ASAL                   | sumbangan tiap PC                                          |
| STATUS AKHIR PER DOKUMEN          | jumlah tiap status audit                                   |
| STATUS DI SERVER                  | status assignment sebenarnya, kalau ada`list_api_*.json` |
| PEMERIKSAAN BENTROK               | lihat bagian di bawah                                      |

Semua keluaran ditulis ke **`audit_pc/hasil/`** (subfolder `hasil/` di folder
`--sumber`). Isi folder itu tidak pernah dibaca ulang sebagai sumber, dan berkas
kerja PC ini (`audit_log_gabungan.csv` di root, `bahan/`) tidak disentuh. Berkas
yang ditulis setiap kali dijalankan (turunan, aman ditimpa):

- `laporan_gabung.csv` — **satu baris per dokumen**: kunci, nomor baris, nama
  usaha, KBLI, akun PPL, akun yang login, wilayah asli + nama kecamatan/desa,
  wilayah tempat dokumen dibuat, status, kelompok status, status server, ID &
  URL dokumen, waktu terakhir, PC asal, catatan review, pesan galat.
- `laporan_gabung_agregat.csv` — rekap tabel-tabel di atas.
- `daftar_ganda.csv` — dokumen ganda + usulan mana yang dihapus.

Tambahkan sheet sumbernya untuk tahu berapa baris yang **belum disentuh sama
sekali**:

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc --format tahap2 --sheet bahan/input_tahap2.xlsx
```

### 3. Tulis hasil gabungannya

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc --tulis
```

Hasilnya `audit_pc/hasil/audit_log_gabungan.csv`. Kalau berkas itu sudah ada dari
penggabungan sebelumnya, ia dicadangkan dulu ke `audit_log_gabungan.csv.bak-<waktu>`
di folder yang sama. Mau langsung menimpa audit kerja PC ini? Tambahkan
`--keluaran audit_log_gabungan.csv` (audit lamanya juga dicadangkan).

### 4. Sebarkan ke semua PC

Salin `audit_pc/hasil/audit_log_gabungan.csv` ke **setiap** PC — termasuk PC ini —
ke root proyek, timpa yang lama. Sejak itu `--lewati-selesai` di PC mana pun
melihat progres semua PC.

### 5. Cocokkan dengan server

Audit bukan satu-satunya sumber kebenaran: toast "berhasil dikirim" pernah muncul
padahal server masih DRAFT. Jalankan per akun (READ-ONLY dulu, tanpa `--tulis`):

```bash
python input_gabungan/sinkron_list.py --format tahap2 --sumber bahan/input_tahap2.xlsx --akun-tunggal AKUN --subsls-tunggal SUBSLS
```

Perintah itu juga menghasilkan `list_api_<akun>.json`, yang membuat kolom
**status server** di laporan terisi pada penggabungan berikutnya.

## Membaca "PEMERIKSAAN BENTROK"

| Peringatan                    | Artinya                                            | Tindakan                                                          |
| ----------------------------- | -------------------------------------------------- | ----------------------------------------------------------------- |
| dokumen dikerjakan >1 PC      | dua PC punya catatan BERBEDA untuk baris yang sama | pastikan dokumennya satu, bukan dua                               |
| **DOKUMEN GANDA**       | satu baris punya dua URL dokumen berbeda           | duplikat di server — rinciannya di `daftar_ganda.csv`; admin menghapusnya lewat `docs/PANDUAN_HAPUS_GANDA.md` (PPL tidak bisa menghapus) |
| dokumen tercatat di >1 akun   | baris dibuat dengan akun berbeda                   | skrip akan melewati baris ini; periksa manual                     |
| satu dokumen dipakai >1 baris | dua baris sheet menunjuk dokumen sama              | cek nama dokumen di server                                        |

Berkas yang isinya hanya salinan audit PC lain tidak dihitung sebagai PC kedua,
jadi menyebarkan hasil gabungan ke semua PC tidak memunculkan peringatan palsu.

## Memantau progres & "kenapa run langsung berhenti" (`rangkum_audit.py`)

```bash
python gabung_audit/rangkum_audit.py --sumber bahan/input_tahap2.xlsx --format tahap2 --akun-tunggal EMAIL --subsls-tunggal SUBSLS --dari 2 --sampai 500
```

Offline & read-only. Yang dicetak:

| Bagian                        | Isi                                                                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| PROGRES                       | jumlah baris per kelompok: TERKIRIM, DRAFT_TANPA_KOORDINAT, DRAFT_GALAT_DI_SERVER, SUDAH DISENTUH, BELUM DISENTUH, DITOLAK PEMERIKSAAN DATA |
| RUN BERIKUTNYA                | berapa baris yang**akan** dikerjakan + nomor barisnya; 0 berarti run memang langsung berhenti                                         |
| ALASAN BARIS TIDAK DIKERJAKAN | dikelompokkan: sudah selesai / dokumennya milik akun lain / ditolak pemeriksaan data / menunggu sinkron                                     |
| YANG DITOLAK PEMERIKSAAN DATA | pesan aslinya, mis.`WAJIB_KOSONG: kolom kosong: pendapatan_lain` — ini yang dibetulkan di Excel                                          |
| BELUM TERINPUT                | nomor barisnya, diringkas jadi rentang                                                                                                      |

Alasan tiap baris dihitung dengan **fungsi yang sama persis** dengan yang dipakai
`main_gabungan` saat batch jalan (pemeriksaan offline → `--lewati-selesai` →
pemeriksaan giliran), jadi angkanya bukan perkiraan. Rinciannya per baris ke
`rangkum_audit.csv`.

Pakai `--tanpa-submit` kalau ingin melihatnya seperti run dry-run, dan
`--daftar 0` untuk mematikan cetakan contoh barisnya.

## Membereskan sisa yang error (`bersihkan_error.py`)

Setelah audit disatukan, kumpulkan semua yang belum beres:

```bash
python gabung_audit/bersihkan_error.py --sumber input_usaha.xlsx
```

Untuk format tahap 2: tambahkan `--format tahap2`. Sebutkan `--sumber` untuk
setiap sheet yang dipakai — nomor baris hanya bisa dipetakan lewat sheet itu.

Alat ini **offline dan read-only**: tidak membuka browser, tidak menyentuh
server, tidak mengubah audit. Yang benar-benar membereskan tetap
`main_gabungan.py` / `main_tahap2.py`, karena di situlah semua pengaman kirim
berada. Yang dihasilkan di sini adalah daftar + perintah siap jalan.

| Tindakan                     | Artinya                                                                                                                                               | Yang harus dilakukan                                                                                                                       |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `ULANGI`                   | galat sesi, DRAFT belum tuntas, gagal kirim                                                                                                           | jalankan perintah yang dicetak — dokumen lama dibuka lewat URL audit,**tidak** dibuat baru                                          |
| `LENGKAPI_KOORDINAT`       | DRAFT tanpa geotag, koordinatnya sudah ada di sheet                                                                                                   | sama; dokumen digeotag lalu dikirim                                                                                                        |
| `PERBAIKI_DATA`            | isian sheet ditolak form                                                                                                                              | betulkan sheet dulu — menjalankan ulang tidak menolong                                                                                    |
| `SINKRON_DULU`             | audit dan server tidak sepakat: audit bilang terkirim padahal server DRAFT,**atau** dokumennya sudah ada di server tapi tidak tercatat di audit | `sinkron_list.py --tulis` dulu. Kalau langsung dijalankan ulang, skrip membuat dokumen **kedua**                                   |
| `TUNGGU_KOORDINAT`         | bukan galat                                                                                                                                           | isi koordinat di sheet kalau sudah ada                                                                                                     |
| `SINKRON_DULU` (tanpa URL) | audit menandai`DOKUMEN_TANPA_URL_PERLU_CEK`: dokumen mungkin terbuat tapi URL-nya tidak tertangkap                                                  | `sinkron_list.py --tulis` dulu. Ketemu → URL dicatat & baris jalan lagi; yang ada cuma DRAFT kosong tanpa nama → minta admin menghapus |
| `MANUAL`                   | dokumen ganda / DRAFT yatim / terkunci                                                                                                                | PPL tidak bisa menghapus dokumen — laporkan ke admin                                                                                      |

**Kapan dokumen lama dipakai, kapan dokumen baru dibuat.** Skrip memutuskannya
dari audit, bukan dari server:

1. audit punya URL dokumen untuk baris itu → dokumen **yang sama** dibuka lewat URL
   dan diisi ulang;
2. audit mencatat dokumen tapi tanpa URL → dicari di daftar berdasarkan nama;
   tidak ketemu = gagal, **bukan** membuat baru;
3. audit tidak punya catatan apa pun → dokumen **baru** dibuat.

Kasus 3 itulah sumber dokumen ganda: kalau dokumennya sebenarnya sudah ada di
server (dibuat PC lain yang auditnya belum digabung, atau dibuat manual), skrip
tidak tahu. Penjaga di `create_document` hanya memeriksa halaman pertama daftar,
dan daftar bisa ratusan dokumen. Karena itu alat ini mencocokkan nama dokumen ke
`list_api_*.json` lebih dulu dan menurunkan baris seperti itu jadi `SINKRON_DULU`.

Perintahnya sudah dikelompokkan per sheet + akun + subsls, dengan nomor baris
yang diringkas (`--baris 354-382,384`). Jalankan satu per satu, jangan dua proses
dengan akun yang sama.

Batasi ke akun tertentu dengan `--akun` (boleh diulang) kalau sebagian akun sudah
tidak dikerjakan lagi:

```bash
python gabung_audit/bersihkan_error.py --sumber input_usaha.xlsx --sumber-tahap2 input_tahap2.xlsx --akun ppl.satu@mail.com --akun ppl.dua@mail.com
```

`--sumber-tahap2` membuat sheet format standar dan tahap 2 bisa diperiksa dalam
satu perintah; tanpa itu laporan kedua menimpa yang pertama.

Untuk akun yang benar-benar ditinggalkan, catatannya bisa dibuang dari audit:

```bash
python gabung_audit/gabung_audit.py --sumber audit_log_gabungan.csv --buang-akun ppl.lama@mail.com --tulis
```

Dokumennya **tidak** terhapus di server — yang hilang hanya catatannya di sini,
termasuk ingatan anti-duplikat untuk dokumen akun itu. Audit lama dicadangkan
otomatis.

Rinciannya ditulis ke `bersihkan_error.csv`.

Dokumen server yang tidak ada di audit **tidak** semuanya dianggap masalah: yang
sudah terkirim/approved hanya dihitung, karena biasanya milik sheet lain atau PC
yang auditnya belum digabung. Yang ditampilkan hanya yang masih DRAFT — itu yang
biasanya dokumen terputus di tengah.

## Kenapa baris tidak diurutkan per waktu

Aturan audit adalah **baris terakhir menang**. Kolom `timestamp` untuk baris hasil
diisi dengan waktu **mulai** memproses baris itu, sedangkan baris `DOKUMEN_DIBUAT`
memakai waktu dokumen benar-benar dibuat — jadi `DOKUMEN_DIBUAT` bisa terlihat
lebih baru daripada baris status akhirnya. Kalau semua baris diurutkan per waktu,
baris yang sudah terkirim bisa berubah status menjadi "baru dibuat" dan dikerjakan
ulang.

Karena itu yang diurutkan adalah **blok per (berkas, kunci)**, memakai waktu
terbesar di blok itu; isi tiap blok tetap urut aslinya. Hasilnya tidak bergantung
pada urutan `--sumber`.

## Audit rusak karena Excel

Gejala: `SKIP_NAMA_DIPAKAI_BARIS_LAIN ... (kunci 1.40E+09)`, atau program berhenti dengan
pesan `audit_log_gabungan.csv RUSAK krn pernah disimpan Excel`. Digit yang hilang dicari dari
cadangan audit yang masih utuh (`audit_log_gabungan.csv.bak-*`, `audit_pc/`), dari
`list_api_*.json`, dan dari sheet `bahan/input_tahap2.xlsx`. Nilai yang tidak pasti **tidak
ditebak**: kalau ada, berkasnya tidak ditulis.

1. Hentikan dulu semua batch yang menulis ke audit itu (tunggu selesai, atau buat berkas
   `STOP_<akun>`).
2. Lihat rencananya:

```bash
python gabung_audit/pulihkan_excel.py
```

3. Tulis. Versi rusaknya disimpan sebagai `.bak-<waktu>-excel`:

```bash
python gabung_audit/pulihkan_excel.py --tulis
```

Bawaannya memulihkan `audit_log_gabungan.csv` dan semua audit di `audit_pc/` (termasuk subfolder). Audit PC lain yang juga
rusak: salin dulu ke `audit_pc/` di PC yang punya cadangan, pulihkan di sana, baru gabungkan.

## Menggabungkan kolom "ID Dokumen FASIH" di sheet bahan

Sejak batch menulis ID dokumen ke kolom **"ID Dokumen FASIH"** di sheet bahan
(mis. `bahan/input_tahap2.xlsx`), sheet itu juga berbeda di tiap PC: tiap PC hanya
berisi ID dokumen yang dibuatnya sendiri. Satukan bersamaan dengan audit, dengan
`gabung_audit/gabung_id_sumber.py`.

1. Setelah batch di semua PC berhenti, salin sheet bahan tiap PC ke subfolder PC
   itu di `audit_pc/`, di samping audit-nya (lihat [langkah 1](#1-kumpulkan-audit-dan-sheet-bahan-tiap-pc-ke-satu-folder)).
   Sheet PC utama sendiri tidak perlu disalin, karena dialah `--utama`.

2. Lihat laporannya dulu. Perintah ini tidak menulis apa pun:

   ```bash
   python gabung_audit/gabung_id_sumber.py --format tahap2 --utama bahan/input_tahap2.xlsx --sumber audit_pc
   ```

3. Tulis. Hasilnya **`audit_pc/hasil/input_tahap2.xlsx`** = salinan sheet utama +
   ID dari PC lain. Sheet utama (`bahan/input_tahap2.xlsx`) tidak diubah. Hasil lama
   di folder itu dicadangkan dulu ke `.bak-<waktu>`:

   ```bash
   python gabung_audit/gabung_id_sumber.py --format tahap2 --utama bahan/input_tahap2.xlsx --sumber audit_pc --tulis
   ```

   Mau langsung mengisi sheet utama? Tambahkan `--keluaran bahan/input_tahap2.xlsx`
   (sheet utama dicadangkan dulu).

4. Isi ID yang masih kosong dari audit gabungan (langkah 3 bagian atas). Ini mencakup
   dokumen yang dibuat sebelum kolom ID ada. Keduanya berkas di `audit_pc/hasil/`:

   ```bash
   python input_gabungan/tulis_id_sumber.py --format tahap2 --sumber audit_pc/hasil/input_tahap2.xlsx --audit audit_pc/hasil --tulis
   ```

5. Sebarkan kedua berkas di `audit_pc/hasil/` ke **setiap** PC, termasuk PC ini:
   `audit_log_gabungan.csv` ke root proyek, `input_tahap2.xlsx` ke `bahan/`. Folder
   `audit_pc/` (termasuk `hasil/`) tidak ikut `bungkus_pc`; kalau mau menyebar lewat
   zip, salin kedua berkas ke tempatnya di PC ini dulu, baru bungkus.

Baris salinan dicocokkan ke baris sheet utama lewat **isi barisnya** (tanpa kolom ID),
jadi urutan sheet yang berbeda tidak masalah. Kalau isi baris di satu PC sudah
dikoreksi (mis. koordinat), pencocokan memakai `kunci` (akun + idsubsls + nama +
pemilik). Hasil per baris:

| Hasil             | Artinya                                          | Tindakan                                                                                                   |
| ----------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `TULIS`           | sel utama kosong, semua PC membawa ID yang sama | diisi (dengan `--tulis`)                                                                                   |
| `SUDAH`           | sel utama sudah berisi ID itu                    | —                                                                                                          |
| `BEDA`            | sel utama berisi ID lain                         | **tidak ditimpa**. Satu baris punya 2 dokumen (ganda) — cek `daftar_ganda.csv`, lalu isi selnya manual |
| `KONFLIK`         | dua PC membawa ID berbeda untuk baris yang sama  | sama seperti `BEDA`                                                                                        |
| `ID_GANDA`        | satu ID jatuh ke lebih dari satu baris           | tidak ditulis; periksa baris-baris itu                                                                     |
| `SEL_TIDAK_VALID` | sel utama berisi teks yang bukan ID              | kosongkan atau perbaiki selnya                                                                             |
| `TIDAK_KETEMU`    | baris salinan tidak ada di sheet utama           | barisnya dihapus/diubah besar-besaran di salah satu PC; ID-nya tetap ada di audit                          |

Rinciannya ditulis ke `audit_pc/hasil/laporan_gabung_id.csv`. Sel yang sudah berisi apa pun **tidak
pernah ditimpa**, jadi perintah ini aman dijalankan ulang, juga di PC mana pun
(mis. di tiap PC dengan sheetnya sendiri sebagai `--utama`).

## Catatan

- Alat ini **tidak pernah menyentuh server** dan tidak mengubah audit sumber.
- Semua `*.csv` diabaikan git (berisi data responden) — termasuk laporannya.
- Uji: `python tests/test_gabung_audit.py`, `python tests/test_gabung_id_sumber.py`.
