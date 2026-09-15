# Panduan Buka Wilayah (fasih-sm)

Membuka kembali subsls yang sudah **"Listing Selesai"** (sama dengan tombol **"Buka Wilayah"**
di dialog *Progress Penyelesaian Wilayah*) secara massal dari daftar idsubsls.

- **Cara:** DevTools Console di Chrome biasa. fasih-sm menolak Playwright/browser otomatis.
- **Yang dibuka:** hanya wilayah berstatus **Listing Selesai**. Wilayah yang sudah
  **Proses Listing** dilewati (tidak disentuh).
- **Yang tidak pernah dilakukan skrip:** "Tandai Selesai Listing".

> Cara kerja: di awal, skrip membaca status **seluruh wilayah sekaligus** (±30 detik).
> Subsls yang sudah **Proses Listing** langsung dilewati tanpa diperiksa satu per satu.
> Sisanya diproses satu per satu: dicari (harus tepat 1 kode yang persis sama dan statusnya
> Listing Selesai), dibuka dengan permintaan yang **sama persis** dengan tombol
> "Buka Wilayah" → "Ya, Buka Wilayah", lalu **dicari ulang untuk memastikan statusnya sudah
> Proses Listing**. Detail teknis:
> `CLAUDE.md` → "fasih-sm: buka wilayah".

---

## 0. Persiapan (sekali)

- VPN kantor aktif.
- Akun fasih-sm yang bisa melihat tombol **"Progress Penyelesaian Wilayah"** (pojok kanan
  atas halaman Data survei).
- Python terpasang, jalankan perintah **dari root proyek**.

## 1. Siapkan daftar subsls

Buat/ubah file teks **`daftar_buka_wilayah.txt`** di root proyek, **satu idsubsls per baris**:

```text
5108010001000203
5108010001000302
5108010001000303
```

Aturan:
- Harus 16 digit berawalan `5108`. Notasi ilmiah Excel (`5.10808E+15`) **ditolak**, jadi
  salin dari kolom yang diformat teks.
- Duplikat otomatis digabung. Baris yang diawali `#` dianggap komentar.

## 2. Buat file siap-tempel

```bash
python buka_wilayah/buka_wilayah.py --daftar daftar_buka_wilayah.txt --console
```

Hasilnya:

```text
daftar_buka_wilayah.txt: 578 idsubsls unik
  kec 5108010: 54
  ...
buka_wilayah_console.siap.js ditulis.
```

Kalau muncul `⛔ ... bukan idsubsls 16 digit`, perbaiki baris yang disebut lalu ulangi.

## 3. Buka halaman Data survei di Chrome

1. Chrome biasa → login fasih-sm (SSO).
2. Buka halaman Data survei SE2026 pencacahan:

   <https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10>

   (Halaman lain akan ditolak skrip: "Buka dulu halaman Data survei".)

## 4. Tempel skrip di Console

1. Tekan **F12** → tab **Console**.
2. Buka `buka_wilayah_console.siap.js` di editor → **Ctrl+A**, **Ctrl+C**.
3. Klik di Console → **Ctrl+V** → **Enter**.
   Pertama kali Chrome akan meminta kamu mengetik `allow pasting` → Enter → tempel lagi.
4. Harus muncul:

   ```text
   [bukaWilayah] Siap: 578 subsls. Mulai dgn: await bukaWilayah.jalankan({mode: "cek"})
   ```

## 5. Cek status (READ-ONLY, tidak mengubah apa pun)

```js
await bukaWilayah.jalankan({mode: "cek"})
```

Tiap subsls tercatat di Console, dan di akhir tampil tabel ringkasan, misalnya:

| status | jumlah |
|---|---|
| `CEK_PERLU_DIBUKA` | 439 |
| `SUDAH_TERBUKA` | 139 |

Kalau ada `WILAYAH_TIDAK_ADA` / `WILAYAH_GANDA` / `SUDAH_TARIK_SAMPEL`, tinjau dulu
(lihat tabel status di bawah). Simpan hasilnya kalau perlu: `bukaWilayah.unduh()`.

> Mode cek: ±30 detik membaca semua wilayah, lalu ±3 detik per subsls yang masih Listing
> Selesai (439 subsls ≈ 20–25 menit). Boleh dilewati kalau sudah yakin; mode eksekusi tetap
> memeriksa ulang setiap subsls sebelum membuka.

## 6. Buka SATU wilayah dulu (wajib)

```js
await bukaWilayah.jalankan({mode: "eksekusi", limit: 1})
```

`limit: 1` = satu subsls **yang masih Listing Selesai** (yang sudah terbuka tidak dihitung).
Mau memilih subsls tertentu: `{mode: "eksekusi", idsubsls: ["5108010001000302"], limit: 1}`.

1. Muncul dialog **"BUKA WILAYAH (batal Selesai Listing) SUNGGUHAN utk maks. 1 subsls"**.
   Ketik **`YA`** (huruf besar) → OK.
2. Console harus menampilkan `-> DIBUKA_TERVERIFIKASI`.
3. **Periksa sendiri:** tutup Console, klik **Progress Penyelesaian Wilayah**, cari subsls itu.
   Statusnya harus **Proses Listing** dengan tombol **Tandai Selesai Listing**.

Kalau benar, lanjut ke langkah 7. Eksekusi massal **ditolak** sampai ada minimal satu
`DIBUKA_TERVERIFIKASI` di browser ini.

## 7. Buka sisanya

```js
await bukaWilayah.jalankan({mode: "eksekusi"})
```

- Ketik **`YA`** lagi di dialog.
- Yang sudah terbuka dilewati di awal (Console: `N subsls sudah terbuka (dilewati tanpa
  request), M diproses satu per satu`), dan dialog YA menyebut jumlah **M** itu.
- Perkiraan waktu **±10–12 detik per wilayah yang dibuka** (cari → buka → verifikasi → jeda
  acak). Contohnya 438 wilayah ≈ 1,5 jam.
- **Biarkan tab tetap terbuka.** Boleh pindah ke tab lain, tapi jangan tutup atau reload
  tab ini dan jangan logout.
- Mau mencicil? Pakai `limit`, misalnya `await bukaWilayah.jalankan({mode: "eksekusi", limit: 50})`.

Perintah lain:

```js
bukaWilayah.berhenti()    // berhenti setelah subsls yang sedang diproses
bukaWilayah.ringkasan()   // hitungan status yang tersimpan
bukaWilayah.unduh()       // unduh hasil sbg CSV (audit_buka_wilayah_<waktu>.csv)
```

## 8. Kalau terputus (reload, sesi habis, laptop tidur)

Hasil tersimpan di `localStorage` browser, jadi tidak hilang saat reload.

1. Login lagi kalau perlu → buka halaman Data survei (langkah 3).
2. Tempel ulang `buka_wilayah_console.siap.js` (langkah 4).
3. Jalankan lagi `await bukaWilayah.jalankan({mode: "eksekusi"})`. Yang sudah beres dilewati.

Setelah selesai, **`bukaWilayah.unduh()`** untuk menyimpan bukti.

---

## Arti status

| Status | Arti | Tindakan |
|---|---|---|
| `CEK_PERLU_DIBUKA` | (mode cek) Listing Selesai, akan dibuka saat eksekusi | — |
| `DIBUKA_TERVERIFIKASI` | Berhasil dibuka & sudah terbukti Proses Listing | Selesai |
| `SUDAH_TERBUKA` | Memang sudah Proses Listing, tidak disentuh (pesan "pindai massal" = dilewati di awal) | Selesai |
| `SUDAH_TARIK_SAMPEL` | Listing Selesai tapi sudah Tarik Sampel, dilewati | Pastikan memang perlu dibuka, lalu jalankan dgn `izinkanTarikSampel: true` |
| `WILAYAH_TIDAK_ADA` | Kode tidak ada di daftar wilayah survei ini | Cek ketikan kode / survei yang dibuka |
| `WILAYAH_GANDA` | Lebih dari satu wilayah berkode sama | Buka manual lewat dialog |
| `KODE_TIDAK_VALID` | Bukan 16 digit | Perbaiki daftar |
| `GAGAL_BUKA` | Server menolak (pesan server ada di kolom pesan) | Baca pesannya; 3x beruntun → batch berhenti |
| `SESI_DITOLAK` ⛔ | Sesi habis / token keamanan (CSRF) ditolak | Reload, login, tempel ulang, jalankan lagi |
| `RESPONS_TIDAK_DIKENAL` ⛔ | Balasan server di luar dugaan | Berhenti; laporkan isi kolom pesan |
| `DIBUKA_BELUM_TERVERIFIKASI` ⛔ | Server bilang sukses tapi status masih Listing Selesai setelah 3x cek | Cek manual di dialog sebelum melanjutkan |
| `DIHENTIKAN_PENGGUNA` ⛔ | `bukaWilayah.berhenti()` dipanggil | Jalankan lagi kapan saja |
| `ERROR_TAK_TERDUGA` | Error lain (koneksi/VPN) | 3x beruntun → batch berhenti; cek VPN |

⛔ = batch langsung berhenti.

## Masalah umum

- **"TARGET kosong"**: yang ditempel file template `buka_wilayah/buka_wilayah_console.js`.
  Tempel `buka_wilayah_console.siap.js` (hasil langkah 2).
- **"Eksekusi massal butuh minimal 1 DIBUKA_TERVERIFIKASI dulu"**: jalankan langkah 6 dulu.
- **Dialog YA tidak muncul / tidak bisa diketik**: pastikan tab fasih-sm sedang aktif
  (dialog Chrome hanya tampil di tab yang menjalankan skrip).
- **"Masih berjalan"**: tunggu selesai, atau `bukaWilayah.berhenti()`.
- **"Pindai massal gagal … dicek satu per satu"**: tidak berbahaya, hanya lebih lambat.
  Untuk mematikan pindai: `{mode: "eksekusi", pindaiDulu: false}`.
- **Salah buka wilayah**: skrip tidak bisa membatalkan. Buka dialog *Progress Penyelesaian
  Wilayah*, cari subsls itu → **Tandai Selesai Listing** (manual).
- **Jangan jalankan dua kali bersamaan** (dua tab/dua orang dgn daftar sama). Aman secara
  data, karena yang sudah terbuka dilewati, tapi hasil audit di tiap browser jadi terpecah.
