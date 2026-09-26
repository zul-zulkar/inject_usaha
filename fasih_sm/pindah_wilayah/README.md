# pindah_wilayah — pindahkan dokumen ke subsls aslinya (fasih-sm)

Semua dokumen `input_usaha` dibuat di satu subsls wadah. Alat ini memindahkan tiap dokumen ke
**subsls aslinya** (kolom `5` sheet), sama dengan **Aksi Lainnya → Change Region by Selection**,
dengan petugas = Pengawas & Pencacah subsls tujuan (masing-masing harus tepat 1).

Hanya dokumen yang **sudah di-approve oleh `approve_pml`** (`APPROVED_TERVERIFIKASI` di
`audit/audit_approve_pml.csv`) dan masih APPROVED di server. Per dokumen: cari (nama → nama lama →
kode identitas, dicocokkan lewat **ID** hasil approve) → baca detail → cek tujuan terbuka & petugas
→ pindah → **keenam level wilayah dibaca ulang harus = tujuan**. Server sibuk (429/504) ditunggu.

## Pakai

Urutan: [`approve_pml`](../../approve_pml/) → (buka wilayah tujuan yang Listing Selesai) → alat ini.

```bash
python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber bahan/input_usaha.xlsx --dari-approve --daftar-tujuan bahan/daftar_tujuan.txt --console
```

`--daftar-tujuan` menulis daftar subsls tujuan untuk [`buka_wilayah`](../buka_wilayah/) /
[`tandai_selesai`](../tandai_selesai/). Batch dengan audit sendiri: tambah `--audit audit/<batch>`.
Tempel `hasil/pindah_wilayah_console.siap.js` di Console halaman Data survei ([cara](../README.md)):

```js
await pindahWilayah.jalankan({mode: "cari", limit: 10})    // baca-saja
await pindahWilayah.jalankan({mode: "pindah", limit: 1})   // 1 dokumen, cek di web
await pindahWilayah.jalankan({mode: "pindah"})             // sisanya (atau limit: 50 mencicil)
pindahWilayah.unduh()
```

## Status penting

| Status | Arti / tindakan |
| --- | --- |
| `DIPINDAH_TERVERIFIKASI` / `SUDAH_DI_TUJUAN` | tuntas |
| `TUJUAN_BELUM_DIBUKA` | tujuan masih Listing Selesai → buka wilayah, jalankan lagi |
| `BELUM_APPROVED` | approve dulu |
| `NAMA_TIDAK_COCOK`, `DOKUMEN_GANDA`, `DI_SUBSLS_LAIN` | tidak dipindah — cek manual |
| `PETUGAS_TUJUAN_TIDAK_ADA` / `_GANDA` | alokasi petugas tujuan bukan tepat 1 — perbaiki, jalankan lagi |
| ⛔ `DIPINDAH_BELUM_TERVERIFIKASI`, `DIPINDAH_LEVEL_BEDA`, `DIPINDAH_STATUS_BERUBAH` | cek dokumen itu manual sebelum lanjut |
| ⛔ `RATE_LIMIT`, `SESI_DITOLAK` | tunggu 10–15 menit / login ulang, jalankan lagi |

Salah pindah tidak dibatalkan skrip — pindah balik manual lewat Change Region by Selection.

## Berkas

`pindah_wilayah.py` (target dari sheet + audit input + audit approve), `pindah_wilayah_console.js`
(alur satuan cari/pindah + alur lama petakan/cek/eksekusi), `hasil/pindah_wilayah_console.siap.js`.
Uji: `python tests/test_pindah_wilayah.py`, `node tests/test_pindah_wilayah_console.js`.
