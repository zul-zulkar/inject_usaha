# Panduan Pindah Wilayah (fasih-sm)

Memindahkan dokumen hasil suntik (semua dibuat di satu subsls) ke **subsls aslinya** —
kolom `idsubsls` di `Agenda.xlsx`, `Agenda1-1.xlsx`, `Agenda2.xlsx`. Kode 16 digit itu adalah
wilayah dari provinsi sampai subsls:

```text
51 (provinsi) > 5108 (kabupaten) > 5108060 (kecamatan) > 5108060002 (desa) > 51080600020002 (SLS) > 5108060002000203 (subsls)
```

Sama dengan menu **Aksi Lainnya → Change Region by Selection** di halaman Data survei.

- **Cara:** DevTools Console di Chrome biasa. fasih-sm menolak Playwright/browser otomatis.
- **Yang dipindah:** hanya dokumen yang **sudah di-approve otomatis** oleh `approve_pml.py`
  (`APPROVED_TERVERIFIKASI` di `audit_approve_pml.csv`) dan di server statusnya masih **APPROVED**.
- **Petugas:** otomatis diisi **Pengawas & Pencacah subsls tujuan** (masing-masing harus tepat
  1 orang). Skrip tidak pernah memindah "tanpa petugas".
- **Wilayah tujuan harus sudah dibuka** (Proses Listing). Yang belum dibuka dilewati
  (`TUJUAN_BELUM_DIBUKA`) dan otomatis diproses saat skrip dijalankan lagi setelah buka wilayah
  selesai.

> Cara kerja — **satu dokumen per satu dokumen**:
>
> 1. **Cari** dokumennya lewat **nama** (kalau tidak tampil: nama lama di audit, lalu **kode identitas**
>    `<subsls asal> - <nama>`) dan cocokkan dengan **ID dokumen hasil approve**. Dokumen lain yang
>    kebetulan bernama sama hanya dilaporkan, tidak pernah dipindah.
> 2. **Baca detail** dokumen itu (data terbaru): nama cocok, masih di subsls asal, masih APPROVED.
> 3. **Cek tujuan:** wilayah tujuan ada & sudah dibuka, Pengawas & Pencacah tujuan tepat 1 orang.
> 4. **Pindah**, lalu detail dibaca ulang: **setiap level wilayah — provinsi, kabupaten, kecamatan,
>    desa, SLS, subsls — harus sama dengan kode tujuan** dan status tetap APPROVED.
>
> Dokumen berikutnya baru diproses setelah dokumen ini tuntas. Tidak ada peta/cache: kalau terputus,
> tinggal jalankan lagi — yang sudah dipindah dilewati.
>
> Server sibuk (HTTP 429 / 504 / jaringan putus sesaat) **tidak** menghentikan batch: skrip menunggu
> lalu mengulang, dan jeda antar-pencarian diperlambat otomatis. Kalau pencarian tetap gagal, dokumen
> dilanjutkan lewat ID approve (nama tetap dicek dari detail).
>
> Detail teknis: komentar di `pindah_wilayah/pindah_wilayah_console.js`.

---

## 0. Persiapan (sekali)

- VPN kantor aktif.
- Akun fasih-sm yang punya menu **Change Region by Selection** (Admin Kabupaten).
- `Agenda.xlsx`, `Agenda1-1.xlsx`, `Agenda2.xlsx`, `audit_log_gabungan.csv` dan
  **`audit_approve_pml.csv`** di root proyek.
- Python terpasang, jalankan perintah **dari root proyek**.
- **Jangan jalankan bersamaan dengan buka wilayah** — kuota request akun sama, hasilnya HTTP 429.

## 1. Buat file siap-tempel

```bash
python pindah_wilayah/pindah_wilayah.py --sumber Agenda.xlsx --sumber Agenda1-1.xlsx --sumber Agenda2.xlsx --dari-approve --console
```

Hasilnya (contoh 2026-09-15):

```text
audit_approve_pml.csv: 457 dokumen APPROVED_TERVERIFIKASI ber-kunci Agenda

457 baris unik jadi target | dgn ID audit: 457, tanpa ID audit (dicocokkan lewat nama): 0
  alur SATUAN: 457 dokumen sudah di-approve -> mode "cari" / "pindah" di Console
  5 baris punya nama lama di audit -> nama lama ikut dicari
Subsls asal (2): 5108010010000105, 5108060014000403
pindah_wilayah_console.siap.js ditulis.
```

Ada dokumen yang baru di-approve? Jalankan `approve_pml.py` dulu, lalu buat ulang file ini dan tempel
ulang di Console.

## 2. Buka halaman Data survei di TAB BARU

[https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&amp;perPage=10](https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10)

Kalau buka wilayah sedang berjalan, **pakai tab lain** — dialog `YA` di satu tab membuat skrip lain
di tab yang sama ikut berhenti menunggu.

## 3. Tempel skrip di Console

F12 → Console → tempel seluruh isi `pindah_wilayah_console.siap.js` → Enter. Harus muncul:

```text
[pindahWilayah] Siap: 457 baris Agenda (457 ber-ID), asal 5108010010000105, 5108060014000403. Mulai dgn: ...
```

Menempel ulang (file baru) di tab yang sudah dipakai tidak masalah — hasil tersimpan di browser.

## 4. Cari & cek (READ-ONLY)

```js
await pindahWilayah.jalankan({mode: "cari", limit: 10})                      // 10 dokumen pertama
await pindahWilayah.jalankan({mode: "cari"})                                 // semua
await pindahWilayah.jalankan({mode: "cari", tujuan: ["5108060002000203"]})    // subsls tujuan tertentu
```

Contoh baris di Console:

```text
[3/457] Agenda.xlsx:4 f1acecae 5108010010000105 -> 5108060002000203 -> CEK_SIAP_PINDAH (cari: PANGKALAN GAS (I PUTU CONTOH))
```

- Yang ideal: `CEK_SIAP_PINDAH`. Yang lain → lihat [Arti status](#arti-status).
- Teks dalam kurung (kolom `cara` di CSV) = bagaimana dokumen ditemukan: `cari: <istilah>`, atau
  `detail ID (...)` kalau tidak tampil di pencarian / pencarian sedang gagal.
- Pencarian diberi jeda ±2,5–4,5 detik (otomatis lebih lambat kalau server membalas 429/504), jadi
  ±5–8 detik per dokumen.

## 5. Pindah SATU dokumen dulu (wajib)

```js
await pindahWilayah.jalankan({mode: "pindah", limit: 1})
```

1. Ketik **`YA`** di dialog.
2. Console harus menampilkan `-> DIPINDAH_TERVERIFIKASI` dengan pesan
   `wilayah 51 > 5108 > … terverifikasi`.
3. **Periksa sendiri** di halaman Data: cari nama dokumennya → Kode Identitas/wilayah harus subsls
   tujuan, petugasnya PML/PPL subsls itu, status tetap APPROVED.

Di mode `pindah`, `limit` = jumlah dokumen yang **benar-benar dipindah**. Dokumen yang sudah di tujuan,
belum dibuka, dll. tetap diperiksa tapi tidak dihitung.

Pindah massal **ditolak** sampai ada minimal satu `DIPINDAH_TERVERIFIKASI` di browser ini.

## 6. Pindah sisanya

```js
await pindahWilayah.jalankan({mode: "pindah"})              // semua
await pindahWilayah.jalankan({mode: "pindah", limit: 50})   // mencicil 50 dokumen
```

- ±8–15 detik per dokumen (cari → detail → cek tujuan & petugas → pindah → verifikasi → jeda).
- Yang tujuannya belum dibuka dilewati; **jalankan lagi setelah buka wilayah selesai**. Yang sudah
  `DIPINDAH_TERVERIFIKASI` / `SUDAH_DI_TUJUAN` (oleh mode pindah) tidak diproses ulang.
- Biarkan tab tetap terbuka.

```js
pindahWilayah.berhenti()    // berhenti setelah dokumen yang sedang diproses
pindahWilayah.ringkasan()   // hitungan status yang tersimpan
pindahWilayah.unduh()       // unduh hasil sbg CSV (audit_pindah_wilayah_<waktu>.csv)
```

Kalau terputus: login lagi → buka halaman Data → tempel ulang → jalankan lagi.

Opsi tambahan (gabungkan di dalam `{...}`):

| Opsi                               | Default             | Arti                                                                                                       |
| ---------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `pakaiPencarian: false`          | `true`            | Lewati pencarian, langsung detail ID approve (nama tetap dicek). Untuk saat pencarian server sangat lambat |
| `jedaCariMin` / `jedaCariMaks` | `2500` / `4500` | Jeda antar-pencarian (ms), sebelum dikali faktor perlambatan otomatis                                      |
| `ulangCari`                      | `2`               | Berapa kali pencarian yang kena 429/504 diulang sebelum lanjut lewat detail ID                             |
| `kunci` / `tujuan`             | semua               | Batasi ke kunci baris / subsls tujuan tertentu                                                             |
| `izinkanTujuanSelesai: true`     | `false`           | Tetap pindah walau tujuan masih Listing Selesai                                                            |

---

## Alur lama: dua tahap (petakan → cek → eksekusi)

Untuk **semua** baris Agenda (termasuk yang tidak tercatat di audit approve). Buat file siap-tempel
**tanpa** `--dari-approve`, lalu:

```js
await pindahWilayah.jalankan({mode: "petakan"})             // READ-ONLY, sekali: pindai subsls asal + cari nama
await pindahWilayah.jalankan({mode: "cek", limit: 20})      // READ-ONLY per ID dari peta
await pindahWilayah.jalankan({mode: "eksekusi", limit: 1})  // 1 dokumen, cek hasilnya
await pindahWilayah.jalankan({mode: "eksekusi"})            // sisanya
```

- Petakan membaca semua assignment di subsls asal (±12 request) dan mencari lewat nama hanya untuk
  baris yang tidak ada di sana (±2 detik/nama, disimpan 12 jam; `cariPerNama: false` untuk
  melewatinya; `pindahWilayah.hapusCacheNama()` untuk mencari ulang). Hasilnya disimpan sebagai peta.
- Cek/eksekusi tidak mencari lagi — langsung per ID dari peta. Petakan ulang kalau ada dokumen baru.
- Dokumen APPROVED di subsls asal yang tidak cocok dengan baris mana pun: `pindahWilayah.tidakDikenali`.
- Sejak 2026-09-15, 504/jaringan putus saat petakan juga ditunggu & diulang (dulu langsung berhenti
  `RESPONS_TIDAK_DIKENAL`).

---

## Arti status

| Status                                                           | Arti                                                                                           | Tindakan                                                                            |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `CEK_SIAP_PINDAH`                                              | (mode cari/cek) dokumen cocok, tujuan terbuka & petugas tujuan tepat 1+1                       | —                                                                                  |
| `PERLU_PINDAH`                                                 | (petakan) cocok, APPROVED, masih di subsls asal                                                | —                                                                                  |
| `DIPINDAH_TERVERIFIKASI`                                       | Berhasil dipindah & semua level wilayah terbukti = tujuan, status tetap APPROVED               | Selesai                                                                             |
| `SUDAH_DI_TUJUAN`                                              | Dokumen memang sudah di subsls tujuan                                                          | Selesai                                                                             |
| `TUJUAN_BELUM_DIBUKA`                                          | Subsls tujuan masih Listing Selesai                                                            | Buka wilayah, lalu jalankan lagi                                                    |
| `BELUM_APPROVED`                                               | Dokumen belum di-approve (atau statusnya berubah)                                              | Approve dulu, jalankan lagi                                                         |
| `NAMA_TIDAK_COCOK`                                             | ID approve ada, tapi nama dokumen di server beda dengan Agenda & nama lama audit               | Cek manual dokumen itu; tidak dipindah                                              |
| `DOKUMEN_TIDAK_DITEMUKAN`                                      | Dokumen tidak tampil di pencarian & tidak ada ID                                               | Baris memang belum diinput?                                                         |
| `PENCARIAN_GAGAL`                                              | Pencarian server gagal (429/504) & tidak ada ID untuk dilanjutkan                              | Jalankan lagi nanti                                                                 |
| `DOKUMEN_GANDA`                                                | >1 dokumen APPROVED / >1 ID untuk satu baris                                                   | Pilih manual / minta admin hapus duplikat                                           |
| `NAMA_GANDA_DI_AGENDA`                                         | Nama dokumen dipakai >1 baris & tidak ada ID                                                   | Pindah manual                                                                       |
| `DI_SUBSLS_LAIN` / `ASAL_BERUBAH`                            | Dokumen ada di subsls yang bukan asal & bukan tujuan                                           | Cek siapa yang memindah; kalau memang asal, tambahkan`--subsls-asal`              |
| `PETUGAS_TUJUAN_TIDAK_ADA` / `PETUGAS_TUJUAN_GANDA`          | Pengawas/Pencacah tujuan bukan tepat 1                                                         | Perbaiki alokasi petugas, jalankan lagi                                             |
| `TUJUAN_TIDAK_ADA` / `TUJUAN_GANDA` / `TUJUAN_TIDAK_VALID` | Kode tujuan tidak dikenal fasih-sm                                                             | Periksa kolom idsubsls Agenda                                                       |
| `GAGAL_PINDAH`                                                 | Server menolak (pesan di kolom pesan)                                                          | Baca pesannya; 3x beruntun → berhenti                                              |
| `SERVER_SIBUK`                                                 | Server tetap 502/503/504 setelah ditunggu                                                      | Otomatis lanjut ke dokumen berikutnya; 3x beruntun → berhenti, jalankan lagi nanti |
| `SESI_DITOLAK` ⛔                                              | Sesi habis / CSRF ditolak                                                                      | Reload, login, tempel ulang                                                         |
| `RESPONS_TIDAK_DIKENAL` ⛔                                     | Balasan server di luar dugaan                                                                  | Laporkan isi pesan                                                                  |
| `DIPINDAH_BELUM_TERVERIFIKASI` ⛔                              | Server bilang sukses (atau balasannya hilang) tapi detail belum/tidak terbaca di subsls tujuan | Cek manual sebelum lanjut                                                           |
| `DIPINDAH_LEVEL_BEDA` ⛔                                       | Subsls sudah = tujuan tapi level lain (mis. kecamatan) tidak cocok                             | Cek manual dokumen itu, laporkan                                                    |
| `DIPINDAH_STATUS_BERUBAH` ⛔                                   | Sudah dipindah tapi status tidak APPROVED lagi                                                 | Cek dampaknya sebelum lanjut                                                        |
| `DIHENTIKAN_PENGGUNA` ⛔                                       | `pindahWilayah.berhenti()`                                                                   | Jalankan lagi kapan saja                                                            |
| `RATE_LIMIT` ⛔                                                | Server masih membalas HTTP 429 setelah ±6 kali menunggu                                       | Tunggu 10–15 menit (atau sampai buka wilayah selesai), jalankan lagi               |

⛔ = batch langsung berhenti.

## Masalah umum

- **`⏳ HTTP 429 (rate limit)` / `⏳ HTTP 504 (server sibuk)` … tunggu N dtk**: normal — skrip menunggu
  lalu mengulang sendiri, biarkan. Muncul `Jeda antar-pencarian dinaikkan jadi x2/x4/x8` artinya skrip
  memperlambat diri; kembali normal pelan-pelan setelah pencarian sukses. Kalau sering sekali, pastikan
  buka wilayah / tab lain tidak sedang memakai akun yang sama, atau pakai `pakaiPencarian: false`.
- **Error lama `RESPONS_TIDAK_DIKENAL … HTTP 504, bukan JSON`** (saat `petakan`): tempel ulang
  `pindah_wilayah_console.siap.js` versi baru — 504 kini ditunggu & diulang.
- **"Belum ada peta di browser ini"**: itu alur lama. Pakai `{mode: "cari"}` / `{mode: "pindah"}`, atau
  jalankan `{mode: "petakan"}` dulu.
- **"TARGET/ASAL kosong"**: yang ditempel template `pindah_wilayah/pindah_wilayah_console.js`;
  tempel `pindah_wilayah_console.siap.js`.
- **Salah pindah**: skrip tidak membatalkan. Pindah balik manual lewat Aksi Lainnya → Change
  Region by Selection.
