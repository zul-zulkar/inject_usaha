# Panduan: menghapus dokumen GANDA (akun admin fasih-sm)

Dokumen **ganda** = satu baris sheet yang punya dua dokumen atau lebih di server.
Biasanya terjadi karena dua PC mengerjakan baris yang sama sebelum auditnya digabung.
PPL tidak bisa menghapus dokumen; yang bisa hanya **admin** di fasih-sm (menu ⋮ →
"Hapus Assignment"). Alat ini menyiapkan daftarnya dan menghapusnya dari DevTools
Console Chrome — satu per satu, dengan bukti di setiap langkah.

> ⚠️ Menghapus assignment **tidak bisa dibatalkan** dari sisi kabupaten. Ikuti urutannya:
> cek (read-only) → rekam satu penghapusan manual → skrip `limit: 1` → baru semuanya.

## 1. Daftar ganda — di PC utama, offline

Setelah audit semua PC digabung (`docs/PANDUAN_GABUNG_AUDIT.md`):

```bash
python gabung_audit/gabung_audit.py --sumber audit_pc
```

Selain laporan biasa, perintah ini menulis **`daftar_ganda.csv`** (satu baris per
dokumen) dan mencetak ringkasannya:

| Jenis grup               | Artinya                                                                       | Ikut dihapus Console? |
| ------------------------ | ----------------------------------------------------------------------------- | --------------------- |
| `BARIS_SAMA`           | satu baris sheet tercatat punya ≥ 2 dokumen di audit — pasti ganda          | ya                    |
| `NAMA_SAMA_BEDA_BARIS` | dokumen bernama sama milik baris sheet**berbeda** — bisa usaha berbeda | tidak, periksa manual |
| `NAMA_SAMA_LUAR_AUDIT` | dokumen bernama sama yang tidak tercatat di audit mana pun                    | tidak, periksa manual |

Kolom `usulan` (PERTAHANKAN / HAPUS / PERIKSA / BUKAN_PAPI) dihitung dari
`list_api_*.json` hasil `sinkron_list.py` — bisa sudah basi. Keputusan akhir diambil
Console dengan status **segar** dari server.

## 2. Siapkan skrip Console

```bash
python hapus_ganda/hapus_ganda.py
```

Hasilnya `hapus_ganda_console.siap.js`. Bawaannya **hanya dokumen PAPI** (dokumen
input web). Opsi: `--akun ppl.contoh@gmail.com` (hanya grup akun itu), `--semua-mode`
(ikutkan CAPI/CAWI — Console juga perlu `{hanyaPapi: false}`).

## 3. Jalankan di Console fasih-sm (akun ADMIN)

1. Buka Chrome biasa (bukan browser otomatis), login fasih-sm dengan akun admin, lalu buka
   halaman **Data** survei:
   `https://fasih-sm.bps.go.id/app/surveys/<survei>/<periode>/data?page=1&perPage=10`
2. Tekan `F12` → tab **Console**. Tempel seluruh isi `hapus_ganda_console.siap.js`, Enter.
   (Kalau Chrome menolak tempel, ketik `allow pasting` dulu.)
3. Jaga tab ini tetap di depan selama skrip berjalan.

### 3a. Cek — READ-ONLY

```js
hapusGanda.cek()
```

Setiap dokumen dibaca detailnya dari server, lalu diputuskan:

| Keputusan         | Artinya                                                                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `PERTAHANKAN`   | SATU dokumen per grup — lihat aturan di bawah                                                                                             |
| `HAPUS`         | ganda dari dokumen yang dipertahankan (nama sama)                                                                                          |
| `PERIKSA`       | APPROVED (tidak pernah dihapus), nama beda, di luar audit, URL-nya dipakai baris lain, atau DRAFT ganda yang jumlah galatnya tidak terbaca |
| `BUKAN_PAPI`    | mode CAPI/CAWI atau mode tidak terbaca — tidak disentuh                                                                                   |
| `TIDAK_TERBACA` | detail tidak terbaca (mungkin sudah dihapus)                                                                                               |

Aturan memilih yang dipertahankan (ketetapan 2026-09-24):

| Grup                  | Yang dihapus                                                                                                                                                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SUBMITTED + DRAFT     | DRAFT                                                                                                                                                                         |
| SUBMITTED + SUBMITTED | salah satu (yang ditunjuk audit dipertahankan)                                                                                                                                |
| DRAFT + DRAFT         | yang masih ber-GALAT; keduanya ber-galat → yang galatnya lebih banyak; keduanya bersih → salah satu (yang ditunjuk audit dipertahankan, lalu yang jawabannya lebih lengkap) |
| APPROVED + lainnya    | yang lain (APPROVED sendiri tidak pernah dihapus)                                                                                                                             |

Mode, jumlah galat & jawaban bersih dibaca dari detail dokumen; kalau detail tidak
memuatnya, dari tabel Data. Mode tidak terbaca → `BUKAN_PAPI`; galat DRAFT tidak terbaca →
`PERIKSA` (tidak ditebak). Cek sebagian dulu: `hapusGanda.cek({grup: 20})`.

### 3b. Rekam SATU penghapusan manual

Alamat & bentuk request "Hapus Assignment" tidak ditebak — skrip merekamnya dari
penghapusan yang Anda lakukan sendiri:

```js
hapusGanda.rekam()
```

Skrip mencetak contoh grup yang cocok (dua dokumen dengan **status berbeda**, supaya
bisa dibedakan di tabel). Lalu:

1. Ketik nama usaha itu di kotak **Cari** tabel Data.
2. Pada baris yang **Status**-nya sesuai petunjuk (mis. DRAFT), klik ⋮ → **Hapus Assignment** → konfirmasi.
3. Tunggu pesan `✅ Pola hapus terekam & terbukti`.

Selama merekam, request ubah yang menyangkut dokumen **yang harus dipertahankan**
(atau PERIKSA / BUKAN_PAPI) **diblokir** — kalau salah pilih baris, penghapusannya tidak
terkirim dan Console menampilkan `🛑 DIBLOKIR`. Batal merekam: `hapusGanda.lepasPenyadap()`.

Kalau pesan ✅ tidak muncul padahal dokumen sudah terhapus: DevTools → tab **Network** →
klik kanan request hapus tadi → **Copy** → **Copy as fetch**, lalu:

```js
hapusGanda.pakaiContoh(`<tempel di sini>`)
```

### 3c. Hapus — satu dulu, baru semuanya

```js
hapusGanda.jalankan({ mode: "hapus", limit: 1 })
```

Cek hasilnya (dokumen itu hilang dari tabel, pasangannya masih ada), lalu:

```js
hapusGanda.jalankan({ mode: "hapus" })
```

Sebelum setiap penghapusan, detail kedua dokumen dibaca ulang; sesudahnya, detail harus
menunjukkan dokumen benar-benar terhapus **dan** pasangannya masih terbaca — kalau tidak,
batch berhenti (`DIHAPUS_BELUM_TERVERIFIKASI`). Berhenti manual: `hapusGanda.berhenti()`.

Opsi (gabungkan sesuai kebutuhan, dipakai juga oleh `cek`):

| Opsi                            | Efek                                                                                                     |
| ------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `izinkanHapusTerkirim: false` | jangan hapus SUBMITTED ganda (bawaan: dihapus, satu per grup tetap dipertahankan). APPROVED tidak pernah |
| `izinkanLuarAudit: true`      | dokumen yang tidak tercatat di audit boleh dihapus                                                       |
| `hanyaPapi: false`            | semua mode (bawaan hanya PAPI)                                                                           |
| `mulai: 101`, `grup: 50`    | mulai dari grup ke-101, sebanyak 50 grup                                                                 |

### 3d. Simpan hasilnya

```js
hapusGanda.unduh()
```

Hasilnya `ganda_dihapus_<waktu>.csv`. **Taruh di folder proyek PC utama** — `gabung_audit.py`
membacanya supaya dokumen yang sudah dihapus tidak didaftar ganda lagi (berkas ini ikut
`bungkus_pc`). Lalu **arahkan audit ke dokumen yang dipertahankan** — wajib, kalau tidak
baris yang dokumen tercatatnya ikut terhapus akan dibuatkan dokumen BARU (ganda lagi):

```bash
python hapus_ganda/hapus_ganda.py --catat
```

```bash
python hapus_ganda/hapus_ganda.py --catat --tulis
```

Yang pertama hanya menampilkan rencananya. Sesudah itu cocokkan audit dengan server per akun:

```bash
python input_gabungan/sinkron_list.py --format tahap2 --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --tulis
```

## Kalau berhenti

| Pesan                           | Artinya                                              | Tindakan                                                     |
| ------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| `POLA_BELUM_ADA`              | belum ada penghapusan manual yang direkam            | `hapusGanda.rekam()`                                       |
| `LIMIT_PERTAMA`               | penghapusan skrip pertama wajib`limit: 1`          | jalankan dengan`limit: 1` dulu                             |
| `DIHAPUS_BELUM_TERVERIFIKASI` | server menjawab sukses tapi dokumennya masih terbaca | cek dokumen itu di tabel; jangan lanjut sebelum jelas        |
| `PEMBANDING_HILANG`           | dokumen yang dipertahankan ikut tidak terbaca        | cek sesi login / dokumen itu                                 |
| `SESI_DITOLAK`                | sesi habis                                           | login ulang, tempel ulang skrip (hasil tersimpan di browser) |
| `HALAMAN_SALAH`               | bukan halaman Data survei yang benar                 | buka`.../data` survei & periode yang sama                  |
