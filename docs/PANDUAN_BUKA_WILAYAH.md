# Panduan Buka Wilayah (fasih-sm)

Membuka kembali subsls yang sudah **"Listing Selesai"** (sama dengan tombol **"Buka Wilayah"**
di dialog *Progress Penyelesaian Wilayah*) secara massal. Kebalikan
[Tandai Selesai Listing](PANDUAN_TANDAI_SELESAI.md).

- **Cara:** DevTools Console di Chrome biasa. fasih-sm menolak Playwright/browser otomatis.
- **Cakupan:** **semua subsls periode** (`--semua`) atau **daftar idsubsls** (`--daftar`).
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

## 1. Pilih cakupan

### A. Semua subsls periode

Tidak perlu file daftar. Skrip Console membaca seluruh wilayah dari server saat dijalankan:

```bash
python buka_wilayah/buka_wilayah.py --semua --console
```

> ⚠️ `--semua` juga membuka wilayah yang **ditandai Selesai Listing oleh orang lain**
> (tim lain, kecamatan lain). Kalau ada yang harus tetap selesai, kecualikan dengan opsi
> `kecuali: ["<kode>", ...]` atau pakai `--daftar`.
>
> **Kode SLS nol dilewati.** Subsls yang 6 digit terakhirnya `000000` (mis. `5108020009000000`)
> tidak diproses, karena server menolak tombol pasangannya (Tandai Selesai) untuk kode seperti ini.
> Untuk tetap mencobanya: `{mode: "eksekusi", sertakanSlsNol: true}`.

Lanjut ke langkah 3.

### B. Daftar subsls tertentu

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

## 2. Buat file siap-tempel (khusus daftar)

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
4. Harus muncul salah satu:

   ```text
   [bukaWilayah] Siap: cakupan SEMUA subsls periode (dibaca saat dijalankan). ...
   [bukaWilayah] Siap: 578 subsls. Mulai dgn: await bukaWilayah.jalankan({mode: "cek"})
   ```

## 5. (Opsional) Cek status — READ-ONLY, tidak mengubah apa pun

```js
await bukaWilayah.jalankan({mode: "cek"})
```

Di akhir tampil tabel ringkasan, misalnya `CEK_PERLU_DIBUKA 439`, `SUDAH_TERBUKA 139`. Boleh
dilewati: mode eksekusi tetap memeriksa ulang setiap subsls sebelum membuka.

> Mode cek: ±30 detik membaca semua wilayah, lalu ±3 detik per subsls yang masih Listing
> Selesai (439 subsls ≈ 20–25 menit). Mau cepat, cukup lihat angka di baris
> `N subsls sudah terbuka …, M diproses satu per satu` lalu `bukaWilayah.berhenti()`.

## 6. Buka

```js
await bukaWilayah.jalankan({mode: "eksekusi"})
```

- Console menampilkan tabel kandidat per kecamatan, lalu dialog
  **"BUKA WILAYAH … SUNGGUHAN … utk maks. M subsls"**. Ketik **`YA`** (huruf besar) → OK.
- **Tidak ada lagi tahap wajib "buka 1 dulu".** Wilayah pertama yang dibuka langsung jadi
  percobaannya: setiap wilayah dicari ulang setelah dibuka, dan kalau ada satu saja yang tidak
  terbukti Proses Listing (`DIBUKA_BELUM_TERVERIFIKASI`), batch langsung berhenti.
- Log per wilayah: `[3/1742] (dibuka 2) 5108… -> DIBUKA_TERVERIFIKASI`.
- Perkiraan waktu **±10–12 detik per wilayah yang dibuka** (cari → buka → verifikasi → jeda
  acak). Contohnya 438 wilayah ≈ 1,5 jam.
- **Biarkan tab tetap terbuka.** Boleh pindah ke tab lain, tapi jangan tutup atau reload
  tab ini dan jangan logout.

**Mau dicicil / dicoba sedikit dulu?** Pakai `limit`. Yang dihitung hanya wilayah yang
**benar-benar dibuka**. Yang ternyata sudah terbuka, Tarik Sampel, ditolak, dan sebagainya
dilewati tanpa memakan jatah, jadi tidak perlu mencari kode manual:

```js
await bukaWilayah.jalankan({mode: "eksekusi", limit: 1})   // buka tepat 1 wilayah, lalu berhenti
await bukaWilayah.jalankan({mode: "eksekusi", limit: 50})  // 50 wilayah per run
```

Subsls tertentu saja: `{mode: "eksekusi", idsubsls: ["5108010001000302"]}`.

Perintah lain:

```js
bukaWilayah.berhenti()    // berhenti setelah subsls yang sedang diproses
bukaWilayah.ringkasan()   // hitungan status yang tersimpan
bukaWilayah.unduh()       // unduh hasil sbg CSV (audit_buka_wilayah_<waktu>.csv)
```

## 7. Kalau terputus (reload, sesi habis, laptop tidur)

Hasil tersimpan di `localStorage` browser, jadi tidak hilang saat reload.

1. Login lagi kalau perlu → buka halaman Data survei (langkah 3).
2. Tempel ulang `buka_wilayah_console.siap.js` (langkah 4).
3. Jalankan lagi `await bukaWilayah.jalankan({mode: "eksekusi"})`. Yang sudah terbuka dilewati
   menurut status server saat itu (bukan catatan lama di browser), jadi wilayah yang sempat
   ditandai selesai lagi ikut dibuka.

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
| `TIDAK_ADA_AKSES` | Server: "Anda tidak memiliki akses ke dalam survey" untuk wilayah itu | Dilewati & didaftar di akhir. Dihitung gagal beruntun hanya selama belum ada `DIBUKA_TERVERIFIKASI` |
| `SERVER_SIBUK` | Permintaan buka kena 429/5xx dan status masih Listing Selesai setelah ditunggu | Otomatis dicoba lagi di run berikut; 3x beruntun → batch berhenti |
| `SERVER_SIBUK_TERUS` ⛔ | Server daftar wilayah terus 504/429/`data: null` setelah ditunggu ±8 menit | Coba lagi nanti, mulai kecil: `{mode: "cek", panjangPindai: 50}` |
| `SESI_DITOLAK` ⛔ | Sesi habis / token keamanan (CSRF) ditolak | Reload, login, tempel ulang, jalankan lagi |
| `RESPONS_TIDAK_DIKENAL` ⛔ | Balasan server di luar dugaan | Berhenti; laporkan isi kolom pesan |
| `DIBUKA_BELUM_TERVERIFIKASI` ⛔ | Server bilang sukses tapi status masih Listing Selesai setelah 3x cek | Cek manual di dialog sebelum melanjutkan |
| `DIHENTIKAN_PENGGUNA` ⛔ | `bukaWilayah.berhenti()` dipanggil | Jalankan lagi kapan saja |
| `ERROR_TAK_TERDUGA` | Error lain (koneksi/VPN) | 3x beruntun → batch berhenti; cek VPN |

⛔ = batch langsung berhenti.

## Masalah umum

- **"TARGET kosong"**: yang ditempel file template `buka_wilayah/buka_wilayah_console.js`.
  Tempel `buka_wilayah_console.siap.js` (hasil langkah 2).
- **Dialog YA tidak muncul / tidak bisa diketik**: pastikan tab fasih-sm sedang aktif
  (dialog Chrome hanya tampil di tab yang menjalankan skrip).
- **"Masih berjalan"**: tunggu selesai, atau `bukaWilayah.berhenti()`.
- **"Pindai massal gagal … dicek satu per satu"** (hanya `--daftar`): tidak berbahaya, hanya
  lebih lambat. Untuk mematikan pindai: `{mode: "eksekusi", pindaiDulu: false}`. Dengan `--semua`,
  pindai yang gagal menghentikan run, karena daftar wilayahnya berasal dari pindai.
- **Jumlah wilayah terlalu sedikit (mis. cuma 500)**: lihat baris `Pindai massal selesai: N wilayah`.
  Versi lama berhenti setelah halaman pertama; pastikan file siap-tempel dibuat ulang
  (`python buka_wilayah/buka_wilayah.py --semua --console`) lalu tempel ulang di tab yang di-reload.
- **`⏳ … tunggu` / `⚠️ Pindai … dicoba N baris`**: server daftar wilayah lambat (504 setelah
  30 detik) atau membalas daftar kosong. Bot menunggu, mengulang, dan memperkecil halaman
  sampai 50 baris. Itu normal.
- **Salah buka wilayah**: skrip tidak bisa membatalkan. Buka dialog *Progress Penyelesaian
  Wilayah*, cari subsls itu → **Tandai Selesai Listing** (manual).
- **Jangan jalankan dua kali bersamaan** (dua tab/dua orang dgn daftar sama). Aman secara
  data, karena yang sudah terbuka dilewati, tapi hasil audit di tiap browser jadi terpecah.
