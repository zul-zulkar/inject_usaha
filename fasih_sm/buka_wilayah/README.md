# buka_wilayah — Buka Wilayah / batalkan "Listing Selesai" (fasih-sm)

Sama dengan tombol **Buka Wilayah** di dialog "Progress Penyelesaian Wilayah". Dibutuhkan sebelum
dokumen dipindah ke subsls yang sudah ditandai Listing Selesai. Per subsls: status dibaca → kalau
Listing Selesai, dibuka lewat API yang sama dengan tombolnya → dibaca ulang harus Proses Listing.
Yang sudah terbuka / sudah Tarik Sampel dilewati.

## Pakai

```bash
python fasih_sm/buka_wilayah/buka_wilayah.py --daftar bahan/daftar_tujuan.txt --console   # subsls tertentu
python fasih_sm/buka_wilayah/buka_wilayah.py --semua --console                             # semua wilayah periode
```

Daftar = satu idsubsls 16 digit per baris ([contoh](../../templates/daftar_idsubsls.contoh.txt));
`pindah_wilayah.py --daftar-tujuan` bisa membuatkannya. Tempel `hasil/buka_wilayah_console.siap.js`
di Console halaman Data survei ([cara](../README.md)), lalu:

```js
await bukaWilayah.jalankan({mode: "cek"})                    // baca-saja
await bukaWilayah.jalankan({mode: "eksekusi", limit: 1})     // buka tepat 1 wilayah, cek di web
await bukaWilayah.jalankan({mode: "eksekusi"})               // sisanya
bukaWilayah.unduh()
```

## Status penting

| Status | Arti |
| --- | --- |
| `DIBUKA_TERVERIFIKASI` / `SUDAH_TERBUKA` | tuntas |
| `SUDAH_TARIK_SAMPEL` | dilewati (opsi `izinkanTarikSampel` kalau memang perlu) |
| `TIDAK_ADA_AKSES` | server menolak wilayah itu — dilewati & didaftar |
| ⛔ `DIBUKA_BELUM_TERVERIFIKASI` | server bilang sukses tapi status belum berubah — cek manual |
| ⛔ `SERVER_SIBUK_TERUS`, `SESI_DITOLAK` | server lambat / sesi habis — reload, tempel ulang, jalankan lagi |

## Berkas

`buka_wilayah.py` (daftar → target, suntik `KODE_KAB`), `buka_wilayah_console.js` (pindai massal,
buka per subsls, verifikasi, tahan server lambat), `hasil/buka_wilayah_console.siap.js`.
Uji: `python tests/test_buka_wilayah.py`, `node tests/test_buka_wilayah_console.js`.
