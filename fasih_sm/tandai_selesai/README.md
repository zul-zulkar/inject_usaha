# tandai_selesai — Tandai Selesai Listing (fasih-sm)

Kebalikan [`buka_wilayah`](../buka_wilayah/): sama dengan tombol **Tandai Selesai Listing** →
"Ya, Tandai selesai". Dipakai sesudah semua dokumen dipindah ke wilayahnya. Per subsls: status
dibaca → kalau masih Proses Listing, ditandai → dibaca ulang harus Listing Selesai.

## Pakai

```bash
python fasih_sm/tandai_selesai/tandai_selesai.py --daftar bahan/daftar_tujuan.txt --console
python fasih_sm/tandai_selesai/tandai_selesai.py --semua --console     # semua wilayah (SLS nol dikecualikan)
```

Tempel `hasil/tandai_selesai_console.siap.js` di Console halaman Data survei ([cara](../README.md)):

```js
await tandaiSelesai.jalankan({mode: "cek"})                  // baca-saja + jumlah per kecamatan
await tandaiSelesai.jalankan({mode: "eksekusi", limit: 1})   // 1 wilayah dulu, cek di web
await tandaiSelesai.jalankan({mode: "eksekusi"})
tandaiSelesai.unduh()
```

## Status penting

| Status | Arti |
| --- | --- |
| `DITANDAI_TERVERIFIKASI` / `SUDAH_SELESAI` | tuntas |
| `TIDAK_ADA_AKSES` | server menolak wilayah itu (mis. SLS `…000000`) — dilewati & didaftar |
| `GAGAL_TANDAI`, `SERVER_SIBUK` | server menolak / lambat; 3x beruntun → berhenti |
| ⛔ `SERVER_SIBUK_TERUS`, `SESI_DITOLAK` | tunggu / login ulang, tempel ulang, jalankan lagi |

## Berkas

`tandai_selesai.py` (format daftar sama dgn buka_wilayah), `tandai_selesai_console.js`,
`hasil/tandai_selesai_console.siap.js`. Uji: `python tests/test_tandai_selesai.py`,
`node tests/test_tandai_selesai_console.js`.
