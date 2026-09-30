# pindah_wilayah — pindahkan dokumen ke subsls aslinya (fasih-sm)

Semua dokumen `input_usaha` dibuat di subsls **wadah**. Alat ini memindahkan tiap dokumen ke
**subsls aslinya** (kolom `5` sheet), sama dengan **Aksi Lainnya → Change Region by Selection**,
dengan petugas = Pengawas & Pencacah subsls tujuan (masing-masing harus tepat 1).

Hemat request (rate limit 429): daftar dokumen dibaca **sekali** per run (dipecah per tanggal
dibuat, tanpa pencarian nama), lalu dokumen dipindah **per rombongan ≤ 50 dokumen** ke subsls
tujuan yang sama — ±600 request pindah untuk ±7.400 dokumen, bukan satu request per dokumen.
Target bisa **dibagi ke beberapa akun admin** yang masing-masing menempel bagiannya sendiri.

## Pakai

Urutan: [`approve_pml`](../../approve_pml/) (hanya dokumen APPROVED yang dipindah) → alat ini
→ (buka wilayah tujuan yang masih Listing Selesai) → pindah. **Jangan jalankan selagi batch
`input_usaha`/`approve_pml` akun PPL yang sama berjalan** — dokumen keluar dari list akun itu dan
hitungan list-nya bisa salah (risiko dokumen ganda).

```bash
python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber bahan/input_tahap2.xlsx --sumber bahan/input_tahap2_22.xlsx --sumber bahan/input_tahap2_23.xlsx --bagi 3 --daftar-tujuan bahan/tujuan_pindah.txt --console
```

- **Target** = baris sheet yang punya dokumen: ID kolom `ID Dokumen FASIH` sheet + URL di audit.
  Audit tiap sheet dipilih otomatis (yang paling mengenal sheet itu di `audit/`, bukan `audit/pc/`);
  `--audit` memaksa satu audit. Baris tanpa dokumen dilewati.
- **Saringan:** `--dari N --sampai M` (baris sheet, berlaku utk tiap sheet), `--tujuan 5108060`
  (awalan kode tujuan, boleh berulang/koma), `--subsls-asal` (wadah tambahan).
- **Beberapa akun:** `--bagi N` → `hasil/pindah_wilayah_console.bagian-K-dari-N.siap.js`. Satu subsls
  tujuan selalu utuh di satu bagian; rinciannya `hasil/pembagian_pindah_wilayah.csv`. Tiap bagian
  ditempel **satu** akun admin di browser/PC-nya sendiri — jangan menempel bagian yang sama dua kali.
  Kalau batasnya per IP (belum diketahui), akun di PC yang sama tidak mengurangi 429 — pakai PC lain.
- **Beban:** `--per-kirim 50` (dokumen per request, maks 50), `--cek-sesudah 3` (dokumen per request
  yang dibaca detailnya sesudah dipindah), `--jeda-kirim 3`, `--jeda-baca 1.5`, `--jarak-request 0.8`
  (detik). Semua bisa juga diubah saat menjalankan: `jalankan({mode: "pindah", perKirim: 20})`.
  Jeda otomatis x2 (s.d. x8) tiap 429/504 dan turun lagi saat lancar.

Tempel berkas `.siap.js` di Console halaman **Data** survei ([cara](../README.md)):

```js
await pindahWilayah.jalankan({mode: "periksa"})            // baca-saja: posisi tiap dokumen + cek tujuan & petugas
await pindahWilayah.jalankan({mode: "pindah", limit: 1})   // 1 dokumen, cek di web
await pindahWilayah.jalankan({mode: "pindah"})             // sisanya (atau limit: 300 mencicil)
await pindahWilayah.jalankan({mode: "periksa"})            // pastikan semuanya sudah di tujuan
pindahWilayah.unduh()                                      // CSV -> simpan di folder audit/
copy(pindahWilayah.daftarTujuan("TUJUAN_BELUM_DIBUKA"))    // bahan buka_wilayah --daftar
```

Sesudah semua akun selesai, **catat ke audit** (wajib — tanpa ini sheet batch itu yang dijalankan
lagi dengan `--sinkron-dulu` bisa membuat dokumen ulang karena dokumennya hilang dari list PPL input):

```bash
python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat            # rencana (unduhan di audit/**/audit_pindah_wilayah*.csv)
python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat --tulis    # DIPINDAH_WILAYAH ke setiap audit yg menunjuk dokumennya
```

## Status penting

| Status                                                                                                             | Arti / tindakan                                                                  |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `DIPINDAH_TERVERIFIKASI`                                                                                         | dipindah, detail 6 level wilayah dibaca cocok & tetap APPROVED                   |
| `DIPINDAH_SERVER_OK`                                                                                             | server menjawab berhasil utk rombongannya; dipastikan oleh`periksa` berikutnya |
| `SUDAH_DI_TUJUAN`                                                                                                | sudah di subsls tujuan (tuntas)                                                  |
| `SIAP_PINDAH`                                                                                                    | (periksa) di wadah, APPROVED, tujuan & petugas siap                              |
| `TUJUAN_BELUM_DIBUKA`                                                                                            | tujuan masih Listing Selesai → buka wilayah, jalankan lagi                      |
| `BELUM_APPROVED`                                                                                                 | approve dulu                                                                     |
| `NAMA_TIDAK_COCOK`, `DOKUMEN_GANDA`, `DI_SUBSLS_LAIN`, `DOKUMEN_HILANG`, `TIDAK_TERBACA`                 | tidak dipindah — cek manual                                                     |
| `PETUGAS_TUJUAN_TIDAK_ADA` / `_GANDA`                                                                          | alokasi petugas tujuan bukan tepat 1 — perbaiki, jalankan lagi                  |
| ⛔`DIPINDAH_BELUM_TERVERIFIKASI`, `DIPINDAH_LEVEL_BEDA`, `DIPINDAH_STATUS_BERUBAH`, `DIPINDAH_JUMLAH_BEDA` | cek dokumen itu manual sebelum lanjut                                            |
| ⛔`RATE_LIMIT`, `SERVER_SIBUK`, `SESI_DITOLAK`                                                               | tunggu 10–15 menit / login ulang, jalankan lagi (yang sudah dipindah dilewati)  |

Salah pindah tidak dibatalkan skrip — pindah balik manual lewat Change Region by Selection.

## Kode yang berpengaruh

| Berkas                        | Isi                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| `pindah_wilayah.py`         | target dari sheet + audit,`--bagi`, pengaturan beban, `--catat`                            |
| `pindah_wilayah_console.js` | baca daftar per jendela tanggal, klasifikasi, rombongan, PUT`update-region-bulk`, verifikasi |
| `input_usaha/mesin.py`      | `STATUS_DIPINDAH` (= tuntas di akun lain)                                                    |

Uji: `python tests/test_pindah_wilayah.py`, `node tests/test_pindah_wilayah_console.js`,
`node tests/test_pindah_wilayah_simulasi.js` (alur browser penuh terhadap server palsu).
