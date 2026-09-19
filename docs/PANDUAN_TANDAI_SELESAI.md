# Panduan Tandai Selesai Listing (fasih-sm)

Kebalikan [Buka Wilayah](PANDUAN_BUKA_WILAYAH.md): menandai subsls berstatus **"Proses Listing"**
menjadi **"Listing Selesai"** (sama dengan tombol **"Tandai Selesai Listing"** di dialog
*Progress Penyelesaian Wilayah*) secara massal.

- **Cara:** DevTools Console di Chrome biasa. fasih-sm menolak Playwright/browser otomatis.
- **Cakupan:** **semua subsls periode** (`--semua`) atau **daftar idsubsls** (`--daftar`).
- **Yang ditandai:** hanya wilayah berstatus **Proses Listing**. Yang sudah **Listing Selesai**
  dilewati (tidak disentuh).
- **Yang tidak pernah dilakukan skrip:** "Buka Wilayah".

> ⚠️ **Jalankan SETELAH input dokumen & pindah wilayah selesai.** Skrip pindah wilayah menolak
> subsls tujuan yang sudah Listing Selesai (`TUJUAN_BELUM_DIBUKA`).
>
> ⚠️ Mode `--semua` juga menandai subsls yang **dibuka orang lain** (bukan hanya yang kamu buka
> lewat Buka Wilayah). Kalau ada tim yang masih listing, pakai `--daftar` atau opsi `kecuali`.

> Cara kerja: di awal, skrip membaca status **seluruh wilayah sekaligus** (±30 detik). Yang sudah
> **Listing Selesai** langsung dilewati. Sisanya diproses satu per satu: dicari (harus tepat
> 1 kode yang persis sama dan statusnya Proses Listing), ditandai dengan permintaan yang sama
> dengan tombol "Tandai Selesai Listing", lalu **dicari ulang untuk memastikan statusnya sudah
> Listing Selesai**. Detail teknis: komentar di `tandai_selesai/tandai_selesai_console.js`.

---

## 0. Persiapan (sekali)

- VPN kantor aktif.
- Akun fasih-sm yang bisa melihat tombol **"Progress Penyelesaian Wilayah"** (pojok kanan
  atas halaman Data survei).
- Python terpasang, jalankan perintah **dari root proyek**.

## 1. Buat file siap-tempel

**Semua subsls periode:**

```bash
python tandai_selesai/tandai_selesai.py --semua --console
```

**Atau hanya daftar tertentu** (format sama dengan buka wilayah: satu idsubsls per baris,
`#` = komentar). Contoh memakai daftar yang dulu dibuka:

```bash
python tandai_selesai/tandai_selesai.py --daftar daftar_buka_wilayah.txt --console
```

Hasilnya `tandai_selesai_console.siap.js`. Kalau muncul `⛔ ... bukan idsubsls 16 digit`,
perbaiki baris yang disebut lalu ulangi.

## 2. Buka halaman Data survei di Chrome

1. Chrome biasa → login fasih-sm (SSO).
2. Buka halaman Data survei SE2026 pencacahan:

   [https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&amp;perPage=10](https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10)

## 3. Tempel skrip di Console

1. Tekan **F12** → tab **Console**.
2. Buka `tandai_selesai_console.siap.js` di editor → **Ctrl+A**, **Ctrl+C**.
3. Klik di Console → **Ctrl+V** → **Enter** (pertama kali ketik `allow pasting` dulu).
4. Harus muncul salah satu:

   ```text
   [tandaiSelesai] Siap: cakupan SEMUA subsls periode (dibaca saat dijalankan). ...
   [tandaiSelesai] Siap: 578 subsls. ...
   ```

## 4. Cek status (READ-ONLY, tidak mengubah apa pun)

```js
await tandaiSelesai.jalankan({mode: "cek"})
```

Di awal tampil `N subsls sudah Listing Selesai (dilewati tanpa request), M diproses satu per satu`.
Tabel akhir misalnya:

| status                 | jumlah |
| ---------------------- | ------ |
| `SUDAH_SELESAI`      | 2012   |
| `CEK_PERLU_DITANDAI` | 602    |

Mode cek ±3 detik per subsls yang masih Proses Listing. Mau cepat, cukup lihat angka **M** lalu
tekan `tandaiSelesai.berhenti()`; mode eksekusi tetap memeriksa ulang setiap subsls.

## 5. Tandai SATU wilayah dulu (wajib)

```js
await tandaiSelesai.jalankan({mode: "eksekusi", limit: 1})
```

1. Console menampilkan tabel jumlah per kecamatan, lalu dialog
   **"TANDAI SELESAI LISTING SUNGGUHAN … utk maks. 1 subsls"**. Ketik **`YA`** → OK.
2. Console harus menampilkan `-> DITANDAI_TERVERIFIKASI`.
3. **Periksa sendiri:** klik **Progress Penyelesaian Wilayah**, cari subsls itu. Statusnya harus
   **Listing Selesai** dengan tombol **Buka Wilayah**.

Eksekusi massal **ditolak** sampai ada minimal satu `DITANDAI_TERVERIFIKASI` di browser ini.

> **Kode SLS nol dilewati.** Dengan `--semua`, subsls yang 6 digit terakhirnya `000000`
> (mis. `5108020009000000`) tidak diproses, karena server menolaknya dengan "Anda tidak memiliki
> akses ke dalam survey". Subsls biasa dengan akun yang sama berhasil (uji 15 Sep 2026:
> `5108060001000106`). Kalau tetap ingin mencobanya: `{mode: "eksekusi", sertakanSlsNol: true}`.
>
> Kalau hasil `limit: 1` tetap `TIDAK_ADA_AKSES`, pilih subsls biasa yang pasti masih Proses Listing:
> `await tandaiSelesai.jalankan({mode: "eksekusi", idsubsls: ["<kode>"], limit: 1})`.
>
> Server daftar wilayah bisa sangat lambat (504 setelah 30 detik) atau membalas daftar kosong
> (`data: null`). Bot menunggu dan mengulang sendiri, dan membaca wilayah dengan halaman lebih kecil
> (sampai 50 baris). Console menampilkan `⏳ … tunggu` dan `⚠️ Pindai … dicoba N baris`; itu normal.
> Kalau sudah tahu servernya lambat, langsung mulai kecil: `{mode: "cek", panjangPindai: 50}`.
> Kalau berhenti `SERVER_SIBUK_TERUS`, coba lagi nanti. Di dialog manual, **tempel**
> kodenya, jangan diketik per huruf (setiap ketikan memicu satu pencarian ke server).

## 6. Tandai sisanya

```js
await tandaiSelesai.jalankan({mode: "eksekusi"})
```

- Ketik **`YA`** lagi. Periksa dulu tabel per kecamatan di Console.
- Perkiraan **±10–12 detik per wilayah** yang ditandai (600 wilayah ≈ 2 jam).
- **Biarkan tab tetap terbuka**, jangan reload atau logout.
- Mencicil: `{mode: "eksekusi", limit: 50}`.
- Mengecualikan subsls yang masih dikerjakan:
  `{mode: "eksekusi", kecuali: ["5108010001000203", "5108010001000302"]}`.
- Hanya subsls tertentu: `{mode: "eksekusi", idsubsls: ["5108010001000203"]}`.

Perintah lain:

```js
tandaiSelesai.berhenti()    // berhenti setelah subsls yang sedang diproses
tandaiSelesai.ringkasan()   // hitungan status yang tersimpan
tandaiSelesai.unduh()       // unduh hasil sbg CSV (audit_tandai_selesai_<waktu>.csv)
```

## 7. Kalau terputus

Login lagi → buka halaman Data survei → tempel ulang → jalankan lagi
`await tandaiSelesai.jalankan({mode: "eksekusi"})`. Status dibaca ulang dari server, jadi yang
sudah Listing Selesai otomatis dilewati. Setelah selesai, **`tandaiSelesai.unduh()`**.

---

## Arti status

| Status                              | Arti                                                                                      | Tindakan                                                                                                                                               |
| ----------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `CEK_PERLU_DITANDAI`              | (mode cek) Proses Listing, akan ditandai saat eksekusi                                    | —                                                                                                                                                     |
| `DITANDAI_TERVERIFIKASI`          | Berhasil ditandai & terbukti Listing Selesai                                              | Selesai                                                                                                                                                |
| `SUDAH_SELESAI`                   | Memang sudah Listing Selesai, tidak disentuh                                              | Selesai                                                                                                                                                |
| `WILAYAH_TIDAK_ADA`               | Kode tidak ada di daftar wilayah survei ini                                               | Cek ketikan kode / survei                                                                                                                              |
| `WILAYAH_GANDA`                   | Lebih dari satu wilayah berkode sama                                                      | Tandai manual lewat dialog                                                                                                                             |
| `KODE_TIDAK_VALID`                | Bukan 16 digit                                                                            | Perbaiki daftar                                                                                                                                        |
| `GAGAL_TANDAI`                    | Server menolak (pesan server di kolom pesan)                                              | Baca pesannya. 3x beruntun → batch berhenti. Kalau penolakan wajar (mis. syarat wilayah belum terpenuhi) dan ingin lanjut:`maksGagalBeruntun: 20`   |
| `TIDAK_ADA_AKSES`                 | Server menolak: "Anda tidak memiliki akses ke dalam survey" (contoh:`5108020009000000`) | Dilewati & didaftar di akhir run. Sebelum akun ini pernah berhasil menandai, 3x beruntun → batch berhenti. Coba dulu 1 subsls biasa (lihat langkah 5) |
| `SERVER_SIBUK`                    | Server 429/5xx saat menandai & status belum berubah                                       | Otomatis dicoba lagi di run berikut                                                                                                                    |
| `SERVER_SIBUK_TERUS` ⛔           | Server tetap 429/5xx setelah ditunggu ±8 menit                                           | Tunggu beberapa menit, jalankan lagi                                                                                                                   |
| `SESI_DITOLAK` ⛔                 | Sesi habis / token CSRF ditolak                                                           | Reload, login, tempel ulang                                                                                                                            |
| `RESPONS_TIDAK_DIKENAL` ⛔        | Balasan server di luar dugaan                                                             | Berhenti; laporkan isi kolom pesan                                                                                                                     |
| `DITANDAI_BELUM_TERVERIFIKASI` ⛔ | Server bilang sukses tapi status masih Proses Listing                                     | Cek manual di dialog                                                                                                                                   |
| `DIHENTIKAN_PENGGUNA` ⛔          | `tandaiSelesai.berhenti()` dipanggil                                                    | Jalankan lagi kapan saja                                                                                                                               |
| `ERROR_TAK_TERDUGA`               | Error lain                                                                                | 3x beruntun → batch berhenti                                                                                                                          |

⛔ = batch langsung berhenti.

## Masalah umum

- **"TARGET kosong"**: yang ditempel file template. Tempel `tandai_selesai_console.siap.js`.
- **"Pindai massal gagal … cakupan SEMUA butuh hasil pindai"**: mode semua tidak punya daftar
  cadangan. Cek VPN/sesi lalu jalankan lagi.
- **Salah tandai**: skrip tidak bisa membatalkan. Buka dialog *Progress Penyelesaian Wilayah* →
  **Buka Wilayah** (manual), atau pakai bot buka wilayah dengan daftar subsls itu.
