# Panduan Ganti Mode CAPI ⇄ PAPI (fasih-sm)

Mengubah mode assignment di fasih-sm dari **CAPI** ke **PAPI** berdasarkan **list kode
identitas milikmu sendiri**, lewat DevTools Console di Chrome biasa.

Untuk arah sebaliknya (**PAPI → CAPI untuk subsls tertentu**), lihat
[Arah balik: PAPI → CAPI per subsls](#arah-balik-papi--capi-per-subsls) di bagian bawah.

> ⚠️ **Ganti mode mengubah data di sistem produksi dan tidak ada tombol "batalkan" di skrip.**
> Selalu jalankan berurutan: `petakan` → `dryrun` → `manual` 1 kode → cek hasilnya di fasih-sm → baru sisanya.
> Alur kode identitas dibuat 2026-09-15 dan **belum pernah dijalankan live**, jadi perhatikan
> tabel di Console pada run pertama.

## Cara kerjanya (per kode identitas)

Skrip meniru apa yang kamu lakukan manual, **satu kode identitas per putaran**:

```
list: 5108060003000402 - UMK - 4
        │
        ▼
1. Ketik "5108060003000402 - UMK - 4" di kotak "Cari..."
2. Baca tabel hasil. Hasil bisa ikut memuat "- UMK - 40", "- UMK - 41", dst.
   → skrip hanya mengambil baris yang kodenya PERSIS "- UMK - 4"
3. Mode baris itu?
     PAPI → lewati (KODE_SUDAH_PAPI)
     CAPI → centang baris itu saja
4. Aksi Lainnya → "Ganti Mode (Ke PAPI) (1)"   ← angka harus 1
5. Konfirmasi (kamu yang klik di mode manual)      → DIUBAH_MENUNGGU
6. Lanjut ke kode berikutnya. Mode baru butuh waktu untuk terbaca di tabel, jadi
   kode ini dicari ulang BELAKANGAN (±30 dtk, 45, 60, 90, 120, lalu tiap 3 mnt):
     PAPI                   → DIUBAH_TERVERIFIKASI
     15 mnt tetap belum PAPI → DIUBAH_BELUM_TERVERIFIKASI (batch berhenti)
        │
        ▼
kode berikutnya di list  (setelah list habis, skrip menunggu sisa kode yang belum terbaca PAPI)
```

- **Kode yang sudah diklik tidak pernah diklik ulang otomatis**, termasuk di run berikutnya. Kode itu
  hanya dicari & diperiksa.
- Paling banyak **10 kode** menunggu sekaligus (`maksMenunggu`). Kalau penuh, skrip menunggu salah satunya
  terbaca PAPI dulu. Selama belum ada satu kode pun yang terbukti PAPI di browser ini, batasnya **1**:
  kode pertama harus terbukti berubah sebelum kode kedua diklik.
- Kalau fasih-sm membalas **HTTP 429 (Too Many Requests)**, hasil pencarian itu tidak dipakai. Skrip menunggu
  (15 dtk, 30, 60, 120…) lalu mencari ulang. Setelah 6 kali tetap 429, skrip berhenti (`RATE_LIMIT`).
- **idsubsls tidak dipakai untuk mencari.** idsubsls (16 digit pertama kode) hanya dipakai untuk
  memeriksa bahwa hasil pencarian memang milik kode itu.
- Assignment lain yang tidak ada di list **tidak pernah disentuh**, termasuk assignment di subsls
  yang sama.
- Kode yang tidak ditemukan dilaporkan, **tidak ditebak**.
- Kalau hasil pencarian kode ternyata berisi subsls lain (kotak Cari tidak menyaring dengan benar),
  skrip **berhenti** (`PENCARIAN_TIDAK_MENYARING`).

Kenapa lewat Console, bukan Playwright: fasih-sm mendeteksi browser otomatis (F5/TSPD).

---

## 1. Siapkan list kode identitas

Format kode sama persis dengan kolom **Kode Identitas** di fasih-sm:

```
5108060003000402 - UMK - 4
```

File boleh **.xlsx**, **.csv**, atau **.txt**. Kodenya boleh di kolom mana saja dan boleh ada kolom
lain (nama usaha, catatan, dll.). Contoh Excel:

| No | Kode Identitas              | Nama Usaha |
| -- | --------------------------- | ---------- |
| 1  | 5108060003000402 - UMK - 4  | WARUNG A   |
| 2  | 5108060003000402 - UMK - 7  | TOKO B     |
| 3  | 5108070013000901 - UMK - 12 | BENGKEL C  |

Pembacaan list:

| Isi baris                                           | Perlakuan                                                                       |
| --------------------------------------------------- | ------------------------------------------------------------------------------- |
| `5108060003000402 - UMK - 4`                      | dimuat                                                                          |
| `5108060003000402-umk-04` (spasi/huruf kecil/nol) | dimuat, dirapikan jadi`5108060003000402 - UMK - 4` sebelum dicari             |
| kode yang sama tertulis 2x                          | diproses sekali, dilaporkan sbg**ganda**                                  |
| judul kolom / baris tanpa angka 16 digit            | diabaikan diam-diam                                                             |
| angka 16 digit tapi bukan kode (NIK, idsubsls saja) | **tidak dimuat**, dilaporkan sbg "bukan kode identitas" → periksa listmu |
| jenis yang memuat tanda "-" (mis.`NON-UMK`)       | **tidak dimuat**, dilaporkan (tidak ditebak)                              |

Untuk file .xlsx, yang dibaca **sheet pertama**. Kalau list ada di sheet lain, tambahkan `--sheet "Nama Sheet"`.

---

## 2. Muat list ke skrip (pilih salah satu)

### Cara A: dengan Python (disarankan, ada laporan pemeriksaan)

Jalankan dari **root proyek**:

```bash
python ganti_moda/ubah_moda.py --daftar list_kode.xlsx --cek
```

Contoh keluaran:

```
=== TARGET GANTI MODE (kode identitas) dari list_kode.xlsx ===
  3 kode identitas (tiap kode dicari sendiri), tersebar di 2 idsubsls
  1 kode GANDA dilewati (hanya diproses sekali), mis.: baris 5: 5108060003000402 - UMK - 4
  !! 1 baris berisi 16 digit tapi BUKAN kode identitas — TIDAK dimuat, periksa:
       baris 6: 3201234567890123,NIK
```

Cocokkan jumlah kodenya dengan listmu. Rinciannya ada di `target_ubah_moda.csv`. Kalau sudah benar, buat file siap-tempel:

```bash
python ganti_moda/ubah_moda.py --daftar list_kode.xlsx --console
```

Hasilnya `ubah_moda_console.siap.js` di root proyek.

### Cara B: tanpa Python

Tempel isi **template** `ganti_moda/ubah_moda_console.js` di Console (langkah 3 di bawah), lalu salin
kolom kode dari Excel ke dalam tanda backtick:

```js
ubahModa.muatDaftarKode(`
5108060003000402 - UMK - 4
5108060003000402 - UMK - 7
5108070013000901 - UMK - 12
`)
```

Console akan menampilkan "Daftar kode dimuat: N kode identitas", beserta tabel baris yang tidak
dikenali kalau ada.

---

## 3. Siapkan Chrome

1. **VPN kantor aktif**, lalu buka Chrome biasa (bukan jendela Playwright).
2. Login fasih-sm dengan akun yang berhak **Ganti Mode**.
3. Buka list assignment dengan **`perPage=100`**. Skrip menolak jalan kalau perPage kurang dari 50:
   `https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=100`
4. Pastikan kolom **Kode Identitas, Status, Mode, Petugas Saat Ini** tampil. Kalau ada yang
   tersembunyi, tampilkan lewat tombol "Kolom".
5. **Jangan pasang filter Mode**, **jangan pindah halaman**, dan **jangan mengetik di kotak Cari**
   selama skrip berjalan.
6. Tekan F12, buka tab **Console**, tempel **seluruh** isi `ubah_moda_console.siap.js` (Cara A) atau
   template + `muatDaftarKode` (Cara B), lalu Enter. Pertama kali, Chrome meminta kamu mengetik
   `allow pasting`.

---

## 4. Jalankan bertahap

Jalankan satu perintah per langkah dan tunggu sampai muncul "Selesai".

**a. Petakan** (kode pertama, read-only, tanpa centang):

```js
await ubahModa.jalankan({mode: "petakan"})
```

Lihat baris log `Pencarian "5108… - UMK - 4": … N baris tampil (1 kode persis)` dan tabel yang dicetak.
**Ini langkah yang membuktikan kotak Cari menyaring per kode identitas.** Statusnya harus
`PETAKAN_PERLU_DIUBAH` atau `PETAKAN_KODE_SUDAH_PAPI`. Kalau muncul `PETAKAN_PENCARIAN_TIDAK_MENYARING`,
berhenti dan laporkan.

**b. Dry-run** (centang → cek angka menu = (1) → lepas centang, **tidak** mengklik Ganti Mode):

```js
await ubahModa.jalankan({mode: "dryrun", limit: 3})
```

Tabel kedua di tiap kode = baris yang **akan** diubah. Isinya harus tepat satu baris dengan kode yang
sama persis. Menjalankan perintah yang sama lagi akan melanjutkan ke 3 kode berikutnya.

**c. Manual 1 kode** (kamu yang mengklik perubahan):

```js
await ubahModa.jalankan({mode: "manual", limit: 1})
```

Skrip meminta konfirmasi, lalu mencari kode, mencentang barisnya, membuka menu, dan **menyorot oranye**
item "Ganti Mode (Ke PAPI) (1)".

1. **Klik item itu sendiri** dan konfirmasi dialognya.
2. Kode tercatat `DIUBAH_MENUNGGU`. Mode baru butuh waktu untuk terbaca, jadi skrip mencari ulang kode itu
   berkala (mulai ±30 dtk) sampai kolom Mode PAPI → `DIUBAH_TERVERIFIKASI`. Dengan `limit: 1`, skrip
   menunggu di situ, maksimal 15 menit.

Kalau ingin batal, tekan **Esc** sebelum dialog muncul. Kode itu tercatat `BELUM_BERUBAH` dan batch berhenti.

Setelah itu, **cek sendiri di fasih-sm** bahwa kode tersebut sudah PAPI.

**d. Sisanya**, tetap manual:

```js
await ubahModa.jalankan({mode: "manual"})
```

**e. (Opsional) Otomatis.** Skrip ikut mengklik item dan tombol konfirmasi. Kamu harus mengetik `YA`
setiap batch. Selama belum ada satu kode yang terbukti PAPI di browser ini, skrip menunggu kode pertama
terbaca PAPI dulu sebelum mengklik kode kedua:

```js
await ubahModa.jalankan({mode: "otomatis", limit: 5})
```

Dialog konfirmasi Ganti Mode belum pernah direkam skrip. Kalau teks atau tombolnya tidak jelas,
skrip berhenti (`DIALOG_TIDAK_DIKENAL` / `TOMBOL_KONFIRMASI_AMBIGU`) daripada menebak.

**f. Simpan hasil** setiap selesai sesi:

```js
ubahModa.unduh()     // audit_ubah_moda_<waktu>.csv — simpan sbg bukti
```

---

## 5. Kalau ada list baru lagi

Ulangi dari langkah 2 **di Chrome yang sama**:

```bash
python ganti_moda/ubah_moda.py --daftar list_kode_baru.xlsx --cek
```

```bash
python ganti_moda/ubah_moda.py --daftar list_kode_baru.xlsx --console
```

Tempel ulang file siap-tempel yang baru, lalu jalankan lagi dari `dryrun`.

- Hasil tersimpan di **localStorage browser ini, per kode identitas**. Kode yang sudah
  `DIUBAH_TERVERIFIKASI` atau `KODE_SUDAH_PAPI` dilewati tanpa dicari lagi, walaupun muncul lagi di list baru.
- Kode yang dulu `KODE_TIDAK_ADA`, `KODE_TIDAK_TAMPIL`, atau gagal akan dicoba lagi.
- Pindah komputer/browser atau menghapus data situs = riwayat hilang. Itu tidak berbahaya karena kode
  yang sudah PAPI tetap terbaca `KODE_SUDAH_PAPI` dan tidak diubah lagi, tapi prosesnya lebih lama.
  Karena itu selalu `ubahModa.unduh()`.

---

## 6. Perintah bantu

| Perintah                             | Fungsi                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------ |
| `ubahModa.berhenti()`              | berhenti di langkah berikutnya (centang yang sedang aktif tetap dilepas) |
| `ubahModa.ringkasan()`             | hitungan status yang tersimpan                                           |
| `ubahModa.unduh()`                 | unduh hasil sbg CSV                                                      |
| `ubahModa.target`                  | lihat target yang sedang dimuat                                          |
| `ubahModa.muatDaftarKode(\`...\`)` | ganti target dgn list kode yang ditempel                                 |
| `ubahModa.hapusHasil()`            | hapus seluruh riwayat di browser ini (unduh dulu!)                       |

Opsi `jalankan`: `limit`, `idsubsls: ["5108..."]` (hanya kode milik subsls tertentu),
`lewatiSelesai: false` (proses ulang yang sudah tuntas), `jedaMin`/`jedaMaks` (ms, default 1500–3000).
Opsi `cakupan` **tidak berlaku** untuk list kode.

Opsi untuk menunggu perubahan mode:

| Opsi              | Default             | Fungsi                                                                                                                                                                                                                                                                                     |
| ----------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `batasTungguMs` | `900000` (15 mnt) | lama maksimal menunggu satu kode terbaca PAPI sejak diklik                                                                                                                                                                                                                                 |
| `maksMenunggu`  | `10`              | jumlah kode yang boleh menunggu sekaligus sebelum kode baru diklik                                                                                                                                                                                                                         |
| `jarakCariMs`   | `2000`            | jarak minimal antar-pencarian (mencegah HTTP 429)                                                                                                                                                                                                                                          |
| `klikUlang`     | `false`           | `true` atau `["kode", …]`: kode yang **sudah** diklik tapi modenya tetap belum berubah boleh diklik lagi. Pakai hanya setelah kamu cek sendiri di fasih-sm bahwa kode itu memang belum berubah.                                                                                 |
| `maksPerKlik`   | `50`              | target subsls: baris maksimal yang dicentang per klik "Ganti Mode". Selama belum ada satu perubahan terbukti ke arah itu di browser ini:**1**. Kalau hasil pencarian subsls >1 halaman: maks **10** (baris yang berubah bisa pindah halaman, lalu diverifikasi satu per satu). |

---

## 7. Arti status

Status yang ditandai **⛔** menghentikan batch seketika. Periksa layar dulu sebelum menjalankan ulang.

| Status                                                    | Arti & tindakan                                                                                                                                                                                                                                              |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PETAKAN_…`                                            | hasil mode petakan; tidak ada yang diubah                                                                                                                                                                                                                    |
| `DRY_RUN_AKAN_DIUBAH`                                   | dry-run: kode ini CAPI dan akan diubah; tidak ada yang diubah                                                                                                                                                                                                |
| `DIUBAH_TERVERIFIKASI`                                  | kode sudah PAPI setelah diubah.**Tuntas.**                                                                                                                                                                                                             |
| `DIUBAH_MENUNGGU`                                       | sudah diklik & dikonfirmasi, Mode belum terbaca PAPI. Skrip mencarinya ulang berkala.**Jangan klik Ganti Mode manual lagi.** Kalau run berhenti sebelum terbaca PAPI, jalankan ulang perintah yang sama: kode ini hanya diperiksa, tidak diklik ulang. |
| `KODE_SUDAH_PAPI`                                       | kode memang sudah PAPI; tidak ada yang diklik.**Tuntas.**                                                                                                                                                                                              |
| `KODE_SUDAH_CAPI` / `TIDAK_ADA_PAPI`                  | arah balik: kode sudah CAPI / subsls tidak punya PAPI lagi di hasil pencarian (1 halaman).**Tuntas.**                                                                                                                                                  |
| `CEK_HALAMAN_LAIN`                                      | arah balik: tidak ada PAPI di halaman tampil, tapi hasil pencarian subsls >1 halaman. PAPI di halaman lain (kalau ada) tidak terlihat. Batch lanjut; ubah sisanya lewat list kode identitas`{ke: "CAPI"}`.                                                 |
| `SUDAH_DIKLIK_MENUNGGU`                                 | yang akan dipilih sudah pernah diklik (lewat target lain) dan belum terbukti berubah; tidak diklik ulang. Jalankan ulang nanti.                                                                                                                              |
| ⛔`MENU_BARIS_TIDAK_ADA`                                | arah balik: tombol ⋮ baris tidak ketemu / menunya tidak terbuka. Pastikan tab fasih-sm di depan, muat ulang halaman.                                                                                                                                        |
| ⛔`OPSI_MODE_TIDAK_JELAS`                               | arah balik: dialog "Ganti Mode" tidak sesuai (pilihan CAPI / tombol "Ubah Mode Pendataan" tidak ada, atau CAPI gagal dipilih). Tidak ada yang dikirim.                                                                                                       |
| ⛔`DIALOG_TIDAK_TERTUTUP`                               | arah balik: dialog masih terbuka sesudah "Ubah Mode Pendataan" (pesan galat ada di kolom pesan). Kode ini dianggap sudah diklik — cek di fasih-sm.                                                                                                          |
| `KODE_TIDAK_ADA`                                        | pencarian kode tidak menemukan kode itu. Cek salah ketik (nomor/jenis) atau periode survei. Batch lanjut.                                                                                                                                                    |
| `KODE_TIDAK_TAMPIL`                                     | kode tidak ada di halaman tampil, tapi hasil pencarian >1 halaman. Ubah manual di fasih-sm. Batch lanjut.                                                                                                                                                    |
| `MODE_TIDAK_DIKENAL`                                    | kolom Mode kode itu bukan CAPI/PAPI; cek manual                                                                                                                                                                                                              |
| `TIDAK_ADA_AKSES`                                       | tombol "Aksi Lainnya" tidak muncul; 3x berturut-turut → berhenti (akun tanpa hak? sesi habis?)                                                                                                                                                              |
| ⛔`PENCARIAN_TIDAK_MENYARING`                           | hasil pencarian kode berisi subsls lain dan kode itu tidak ada: kotak Cari tidak menyaring per kode. Laporkan.                                                                                                                                               |
| ⛔`KODE_GANDA`                                          | kode yang sama tampil 2x di tabel; tidak dipilih. Cek manual.                                                                                                                                                                                                |
| ⛔`KOLOM_TIDAK_ADA`                                     | kolom Mode/Petugas/Status disembunyikan; tampilkan lewat tombol "Kolom"                                                                                                                                                                                      |
| ⛔`PER_PAGE_KECIL`                                      | buka ulang list dgn`perPage=100`, tempel ulang skrip                                                                                                                                                                                                       |
| ⛔`CENTANG_TIDAK_SESUAI` / `JUMLAH_TERCENTANG_BEDA`   | yang tercentang ≠ kode itu, atau angka (N) di menu ≠ 1. Lepas semua centang manual.                                                                                                                                                                        |
| ⛔`TABEL_BERUBAH` / `CENTANG_GAGAL`                   | tabel bergeser saat mencentang; lepas centang manual, jalankan ulang                                                                                                                                                                                         |
| ⛔`MENU_TIDAK_TERTUTUP` / `ITEM_MENU_TIDAK_ADA`       | menu "Aksi Lainnya" bermasalah; tutup manual (Esc), cek tampilan                                                                                                                                                                                             |
| ⛔`BELUM_BERUBAH`                                       | mode manual: kamu batal/Esc, atau Mode belum terbaca PAPI. Cek di fasih-sm.                                                                                                                                                                                  |
| ⛔`DIUBAH_BELUM_TERVERIFIKASI`                          | mode otomatis: sudah diklik tapi Mode belum terbaca PAPI.**Cek di fasih-sm sebelum mengulang.**                                                                                                                                                        |
| ⛔`DIALOG_TIDAK_DIKENAL` / `TOMBOL_KONFIRMASI_AMBIGU` | mode otomatis: dialog tidak jelas → tidak diklik. Pakai mode manual.                                                                                                                                                                                        |
| ⛔`DIHENTIKAN_PENGGUNA`                                 | kamu memanggil`ubahModa.berhenti()`                                                                                                                                                                                                                        |
| `ERROR_TAK_TERDUGA`                                     | lihat pesan & Console; 3x berturut-turut → berhenti (`GAGAL_BERUNTUN`)                                                                                                                                                                                    |

`KODE_TIDAK_TAMPIL` seharusnya jarang, karena pencarian per kode biasanya hanya menghasilkan beberapa
baris. Skrip sengaja **tidak pernah pindah halaman**, karena halaman fasih-sm yang dipindah tidak
memuat datanya dengan benar.

---

## Alur lain: dari sheet input usaha

Kalau targetnya bukan list kode tapi sheet `input_usaha.xlsx` (tab input_usaha), ganti `--daftar` dengan `--sumber`:

```bash
python ganti_moda/ubah_moda.py --sumber input_usaha.xlsx --console
```

Alur ini **berbeda**: skrip mencari per **idsubsls** dan **memilih sendiri** assignment yang diubah.
Cukup satu PAPI per subsls, dan milik PPL sheet didahulukan (`cakupan: "semua"` = semua CAPI yang
tampil). Langkah di Chrome sama seperti bagian 3–4.

---

## Arah balik: PAPI → CAPI per subsls

Untuk subsls tertentu saja: **semua** assignment PAPI di subsls itu dikembalikan ke CAPI. Assignment di
subsls lain tidak disentuh.

### 1. Siapkan list idsubsls

Satu idsubsls 16 digit per baris (boleh ada kolom lain, mis. nama SLS). File .xlsx/.csv/.txt, atau
langsung dipisah koma di perintah.

> ⚠️ **Kolom idsubsls di Excel harus berformat Teks.** Angka 16 digit yang disimpan sebagai *Number*
> dipotong Excel jadi 15 digit (`5108060029000201` → `5108060029000200`), dan hasilnya bisa saja subsls
> lain yang memang ada. Dari file .xlsx, sel berformat angka **tidak dimuat** dan dilaporkan.

| Isi baris                                           | Perlakuan                                                                                                 |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `5108060029000201`                                | dimuat                                                                                                    |
| `5108060029000201, 5108060029000202`              | keduanya dimuat                                                                                           |
| `5108060029000201 - UMK - 3` (kode identitas)     | **tidak dimuat**, dilaporkan. Kalau hanya kode itu yang ingin diubah, pakai list kode (lihat bawah) |
| `5.10806E+15`, angka 15/17 digit, sel angka Excel | **tidak dimuat**, dilaporkan                                                                        |
| subsls yang sama 2x                                 | diproses sekali                                                                                           |

### 2. Buat file siap-tempel

```bash
python ganti_moda/ubah_moda.py --subsls daftar_subsls.txt --ke CAPI --cek
```

```bash
python ganti_moda/ubah_moda.py --subsls daftar_subsls.txt --ke CAPI --console
```

`--ke` **wajib** ditulis untuk `--subsls`. Arahnya ikut tersimpan di `ubah_moda_console.siap.js`, jadi
Console tidak bisa jalan ke arah lain. Tanpa Python: tempel template, lalu

```js
ubahModa.muatDaftarSubsls(`
5108060029000201
5108060029000202
`, {ke: "CAPI"})
```

### 3. Jalankan bertahap (Chrome sama seperti bagian 3)

```js
await ubahModa.jalankan({mode: "petakan"})             // baris pertama: buka ⋮ -> Ganti Mode -> catat dialog -> Close
await ubahModa.jalankan({mode: "dryrun"})              // pilih CAPI di dialog, cek tombol aktif, Close TANPA dikirim
await ubahModa.jalankan({mode: "otomatis", limit: 1})  // 1 subsls sungguhan (ketik YA), cek di fasih-sm
await ubahModa.jalankan({mode: "otomatis"})            // sisanya
```

Skrip meniru cara manual, **satu baris satu per satu** (bukan centang massal):

```
cari subsls → untuk tiap baris PAPI yang tampil:
      ⋮ (ujung kanan baris) → "Ganti Mode" → dialog "Mode Pendataan": pilih CAPI → "Ubah Mode Pendataan"
   → tunggu sampai terbaca CAPI (±30 dtk, 45, 60, 90, 120, lalu tiap 3 mnt; maks 15 mnt)
   → cari lagi → masih ada PAPI? ulangi → tidak ada: TIDAK_ADA_PAPI (tuntas)
```

Struktur menu & dialog ini dilihat langsung di fasih-sm (2026-09-22) tanpa mengirim apa pun. Yang
**belum** pernah terlihat: apa yang muncul sesudah "Ubah Mode Pendataan". Skrip menerima dialog yang
tertutup (terkirim) atau satu dialog konfirmasi yang searah; dialog yang tetap terbuka →
`DIALOG_TIDAK_TERTUTUP` (berhenti). Karena itu jalankan `limit: 1` dulu dan cek hasilnya di fasih-sm.

- **Tab fasih-sm harus tetap di depan** selama skrip jalan. Di tab latar belakang, menu yang sudah
  ditutup tertinggal di halaman dan menu ⋮ berikutnya bisa tidak terbuka (`MENU_BARIS_TIDAK_ADA`).
- Menu ⋮ juga berisi **"Hapus Assignment"**. Skrip hanya mengklik item yang teksnya persis
  "Ganti Mode"; kalau item itu tidak ada tepat satu, skrip berhenti (`ITEM_MENU_TIDAK_ADA`).
- **Baris pertama saja dulu** sampai ada satu perubahan ke CAPI yang terbukti di browser ini. Setelah
  itu maks 50 baris per putaran (10 kalau hasil pencarian subsls >1 halaman).
- Mode manual: skrip menyorot oranye tombol ⋮ baris yang harus diubah, lalu **kamu** yang klik
  ⋮ → Ganti Mode → CAPI → Ubah Mode Pendataan. Kalau baris itu tidak jadi diubah, ketik
  `ubahModa.lewati()` di Console.
- Jalur centang massal ("Aksi Lainnya") masih bisa dicoba dengan `caraKlik: "massal"`, tapi item
  "Ganti Mode (Ke CAPI)" belum pernah terlihat.
- **Subsls >1 halaman.** Skrip tetap tidak pindah halaman. PAPI di halaman 2 dst. tidak terlihat; kalau
  halaman tampil sudah tidak punya PAPI, status `CEK_HALAMAN_LAIN` (batch lanjut). Untuk sisanya, pakai
  list kode identitas ke CAPI:

```bash
python ganti_moda/ubah_moda.py --daftar list_kode.xlsx --ke CAPI --console
```

  atau `ubahModa.muatDaftarKode(`...`, {ke: "CAPI"})`.

- Hasil arah CAPI disimpan terpisah (kunci berawalan `CAPI:`). Subsls yang dulu `SUDAH_ADA_PAPI` lalu
  dikembalikan ke CAPI akan **diperiksa lagi** kalau alur PAPI dijalankan ulang, tidak dilewati.
