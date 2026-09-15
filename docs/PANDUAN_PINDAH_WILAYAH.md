# Panduan Pindah Wilayah (fasih-sm)

Memindahkan dokumen hasil suntik (semua dibuat di satu subsls) ke **subsls aslinya** —
kolom `idsubsls` di `Agenda.xlsx`, `Agenda1-1.xlsx`, `Agenda2.xlsx`. Sama dengan menu
**Aksi Lainnya → Change Region by Selection** di halaman Data survei.

- **Cara:** DevTools Console di Chrome biasa. fasih-sm menolak Playwright/browser otomatis.
- **Yang dipindah:** hanya dokumen yang **cocok dengan baris Agenda** dan statusnya
  **APPROVED** (sudah dikirim PPL & di-approve PML).
- **Petugas:** otomatis diisi **Pengawas & Pencacah subsls tujuan** (masing-masing harus tepat
  1 orang). Skrip tidak pernah memindah "tanpa petugas".
- **Wilayah tujuan harus sudah dibuka** (Proses Listing). Yang belum dibuka dilewati
  (`TUJUAN_BELUM_DIBUKA`) dan otomatis diproses saat skrip dijalankan lagi setelah buka wilayah
  selesai.

> Cara kerja — **dua tahap**:
> 1. **Petakan** (sekali, hanya membaca): semua assignment di subsls asal dibaca sekaligus
>    (±12 request, bukan satu pencarian per dokumen), dicocokkan dengan baris Agenda (ID dokumen di
>    `audit_log_gabungan.csv`, atau nama dokumen yang persis sama & unik). Pencarian per nama hanya
>    untuk baris yang tidak ada di subsls asal. Hasilnya (baris → ID dokumen → subsls tujuan)
>    **disimpan** di browser.
> 2. **Cek / eksekusi**: tidak mencari lagi. Per ID dari peta: baca detail (sekaligus memastikan
>    masih di subsls asal & **APPROVED**) → cek wilayah tujuan & petugasnya → pindah → **baca ulang
>    detail untuk memastikan sudah di subsls tujuan dan status tetap APPROVED**.
>
> Detail teknis: `CLAUDE.md` → "fasih-sm: pindah wilayah".

---

## 0. Persiapan (sekali)

- VPN kantor aktif.
- Akun fasih-sm yang punya menu **Change Region by Selection** (Admin Kabupaten).
- `Agenda.xlsx`, `Agenda1-1.xlsx`, `Agenda2.xlsx` dan `audit_log_gabungan.csv` di root proyek.
- Python terpasang, jalankan perintah **dari root proyek**.

## 1. Buat file siap-tempel

```bash
python pindah_wilayah/pindah_wilayah.py --sumber Agenda.xlsx --sumber Agenda1-1.xlsx --sumber Agenda2.xlsx --console
```

Hasilnya (contoh 2026-09-15):

```text
862 baris unik jadi target | dgn ID audit: 606, tanpa ID audit (dicocokkan lewat nama): 256
  ⚠️ 4 baris memakai nama dokumen yang sama dgn baris lain -> hanya bisa dicocokkan lewat ID audit
Subsls asal (2): 5108010010000105, 5108060014000403
pindah_wilayah_console.siap.js ditulis.
```

Subsls asal diambil dari audit. Kalau ada dokumen yang disuntik di subsls lain (perangkat lain),
tambahkan: `--subsls-asal 51080...`.

## 2. Buka halaman Data survei di TAB BARU

<https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10>

Kalau buka wilayah sedang berjalan, **pakai tab lain** — dialog `YA` di satu tab membuat skrip lain
di tab yang sama ikut berhenti menunggu.

## 3. Tempel skrip di Console

F12 → Console → tempel seluruh isi `pindah_wilayah_console.siap.js` → Enter. Harus muncul:

```text
[pindahWilayah] Siap: 862 baris Agenda, asal 5108010010000105, 5108060014000403. Mulai dgn: ...
```

## 4. Petakan (READ-ONLY, cukup sekali)

```js
await pindahWilayah.jalankan({mode: "petakan"})
```

- Tabel di akhir = hasil pencocokan per baris (`PERLU_PINDAH`, `BELUM_APPROVED`,
  `DOKUMEN_TIDAK_DITEMUKAN`, …). Console menulis `Peta tersimpan: … N siap dikerjakan`.
- Pencarian nama (untuk baris yang tidak ada di subsls asal) pelan (±2 detik/nama) & disimpan 12 jam.
  Mau cepat dulu: `{mode: "petakan", cariPerNama: false}`, lalu petakan lagi (tanpa opsi itu) saat
  buka wilayah sudah selesai — yang sudah ketemu tidak hilang.
- Dokumen APPROVED di subsls asal yang **tidak cocok** dengan baris Agenda mana pun tidak dipindah;
  daftarnya ada di `pindahWilayah.tidakDikenali`.
- **Petakan ulang** hanya perlu kalau ada dokumen baru diinput/dikirim ulang, atau file siap-tempel
  dibuat ulang dari Agenda yang berubah. Dokumen yang baru di-approve **tidak** perlu dipetakan ulang
  (entri `BELUM_APPROVED` ikut dicek ulang saat eksekusi).

## 5. Cek per dokumen (READ-ONLY)

```js
await pindahWilayah.jalankan({mode: "cek", limit: 20})                       // 20 dokumen pertama dari peta
await pindahWilayah.jalankan({mode: "cek", tujuan: ["5108060002000203"]})     // subsls tujuan tertentu
```

Hasil per dokumen: `CEK_SIAP_PINDAH`, `TUJUAN_BELUM_DIBUKA`, `BELUM_APPROVED`, dll.

## 6. Pindah SATU dokumen dulu (wajib)

```js
await pindahWilayah.jalankan({mode: "eksekusi", limit: 1})
```

1. Ketik **`YA`** di dialog.
2. Console harus menampilkan `-> DIPINDAH_TERVERIFIKASI`.
3. **Periksa sendiri** di halaman Data: cari nama dokumennya → Kode Identitas harus berawalan
   subsls tujuan, petugasnya PML/PPL subsls itu, status tetap APPROVED.

Eksekusi massal **ditolak** sampai ada minimal satu `DIPINDAH_TERVERIFIKASI` di browser ini.

## 7. Pindah sisanya

```js
await pindahWilayah.jalankan({mode: "eksekusi"})              // semua yang ada di peta
await pindahWilayah.jalankan({mode: "eksekusi", limit: 50})   // mencicil
```

- Tidak ada pencarian lagi — langsung per ID dari peta.
- ±8–12 detik per dokumen (cek detail → cek tujuan & petugas → pindah → verifikasi → jeda acak).
- Yang tujuannya belum dibuka dilewati; **jalankan lagi setelah buka wilayah selesai**. Yang sudah
  `DIPINDAH_TERVERIFIKASI` tidak diproses ulang.
- Biarkan tab tetap terbuka.

```js
pindahWilayah.berhenti()    // berhenti setelah dokumen yang sedang diproses
pindahWilayah.ringkasan()   // hitungan status yang tersimpan
pindahWilayah.unduh()       // unduh hasil sbg CSV (audit_pindah_wilayah_<waktu>.csv)
```

Kalau terputus: login lagi → buka halaman Data → tempel ulang → jalankan lagi. Hasil tersimpan di
`localStorage` browser itu.

---

## Arti status

| Status | Arti | Tindakan |
|---|---|---|
| `PERLU_PINDAH` | (petakan) cocok, APPROVED, masih di subsls asal | — |
| `CEK_SIAP_PINDAH` | (mode cek) tujuan terbuka & petugas tujuan tepat 1+1 | — |
| `DIPINDAH_TERVERIFIKASI` | Berhasil dipindah & terbukti di subsls tujuan, status tetap APPROVED | Selesai |
| `SUDAH_DI_TUJUAN` | Dokumen memang sudah di subsls tujuan | Selesai |
| `TUJUAN_BELUM_DIBUKA` | Subsls tujuan masih Listing Selesai | Buka wilayah, lalu jalankan lagi |
| `BELUM_APPROVED` | Dokumen belum di-approve (atau status berubah) | Approve dulu, jalankan lagi |
| `DOKUMEN_TIDAK_DITEMUKAN` | Baris Agenda tanpa dokumen di server (tidak ada di subsls asal & tidak ketemu lewat nama) | Baris memang belum diinput? |
| `DOKUMEN_GANDA` | >1 dokumen APPROVED untuk satu baris | Pilih manual / minta admin hapus duplikat |
| `NAMA_GANDA_DI_AGENDA` | Nama dokumen dipakai >1 baris & tidak ada ID audit | Pindah manual |
| `DI_SUBSLS_LAIN` | Dokumen ada di subsls yang bukan asal & bukan tujuan | Cek; kalau memang asal, tambahkan `--subsls-asal` |
| `ASAL_BERUBAH` | Saat akan dipindah, dokumen sudah di subsls lain | Cek siapa yang memindah |
| `PETUGAS_TUJUAN_TIDAK_ADA` / `PETUGAS_TUJUAN_GANDA` | Pengawas/Pencacah tujuan bukan tepat 1 | Perbaiki alokasi petugas, jalankan lagi |
| `TUJUAN_TIDAK_ADA` / `TUJUAN_GANDA` / `TUJUAN_TIDAK_VALID` | Kode tujuan tidak dikenal fasih-sm | Periksa kolom idsubsls Agenda |
| `GAGAL_PINDAH` | Server menolak (pesan di kolom pesan) | Baca pesannya; 3x beruntun → berhenti |
| `SESI_DITOLAK` ⛔ | Sesi habis / CSRF ditolak | Reload, login, tempel ulang |
| `RESPONS_TIDAK_DIKENAL` ⛔ | Balasan server di luar dugaan | Laporkan isi pesan |
| `DIPINDAH_BELUM_TERVERIFIKASI` ⛔ | Server bilang sukses tapi detail masih di subsls lama | Cek manual sebelum lanjut |
| `DIPINDAH_STATUS_BERUBAH` ⛔ | Sudah dipindah tapi status tidak APPROVED lagi | Cek dampaknya sebelum lanjut |
| `DIHENTIKAN_PENGGUNA` ⛔ | `pindahWilayah.berhenti()` | Jalankan lagi kapan saja |
| `RATE_LIMIT` ⛔ | Server masih membalas HTTP 429 setelah ±6 kali menunggu | Tunggu 10–15 menit (atau sampai buka wilayah selesai), jalankan lagi |

⛔ = batch langsung berhenti.

## Masalah umum

- **"Belum ada peta di browser ini"**: jalankan `{mode: "petakan"}` dulu (peta disimpan per
  browser; tab lain di browser yang sama ikut memakainya).
- **"TARGET/ASAL kosong"**: yang ditempel template `pindah_wilayah/pindah_wilayah_console.js`;
  tempel `pindah_wilayah_console.siap.js`.
- **Salah pindah**: skrip tidak membatalkan. Pindah balik manual lewat Aksi Lainnya → Change
  Region by Selection.
- **`⏳ HTTP 429 (rate limit) … tunggu N dtk`**: fasih-sm membatasi jumlah request per akun
  (terjadi 2026-09-15 saat pencarian nama berjalan bersamaan dgn buka wilayah). Skrip menunggu
  lalu mengulang sendiri — biarkan. Kalau sampai berhenti `RATE_LIMIT`, jalankan lagi nanti.
  Buka wilayah & pindah wilayah memakai kuota akun yang sama, jadi paling cepat dijalankan
  bergantian.
- **Banyak `DOKUMEN_TIDAK_DITEMUKAN` membuat cek lambat**: tiap baris itu dicari lewat nama
  (±2 detik). Hasil pencarian disimpan 12 jam, jadi run berikutnya tidak mengulang; kalau
  terputus 429, run berikutnya melanjutkan dari yang belum dicari. Lewati pencarian sama sekali
  dengan `cariPerNama: false` (baris itu tetap `DOKUMEN_TIDAK_DITEMUKAN`, yang lain tetap diproses).
  Paksa cari ulang: `pindahWilayah.hapusCacheNama()`.
