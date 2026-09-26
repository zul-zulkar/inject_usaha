# hapus_ganda — hapus dokumen GANDA (fasih-sm, akun admin)

Satu baris sheet kadang punya ≥ 2 dokumen di server (draft yatim, kiriman dobel antar-PC). PPL
tidak bisa menghapus dokumen; alat ini membantu **admin** menghapusnya dari halaman Data fasih-sm.

Keputusan per grup (baris yang sama): pertahankan status tertinggi (APPROVED > SUBMITTED >
REJECTED > DRAFT); yang dihapus hanya DRAFT/REJECTED — dan SUBMITTED kembar yang isinya sama
(bisa dimatikan `izinkanHapusTerkirim: false`). APPROVED tidak pernah dihapus; tidak jelas →
`PERIKSA`. **Endpoint hapus tidak ditebak**: Anda menghapus SATU dokumen manual sambil skrip
merekam request-nya, lalu pola itu dipakai untuk sisanya.

## Pakai

```bash
python antar_pc/gabung_audit.py --sumber audit/pc          # (opsional) daftar ganda dari audit gabungan
python fasih_sm/hapus_ganda/hapus_ganda.py                  # -> hasil/hapus_ganda_console.siap.js
```

Tempel di Console halaman Data survei dgn akun **admin** ([cara](../README.md)):

```js
hapusGanda.cek()                                   // baca-saja: keputusan tiap grup (cek({grup: 20}) sebagian)
hapusGanda.rekam()                                 // lalu hapus SATU dokumen HAPUS lewat menu ⋮ secara manual
hapusGanda.jalankan({ mode: "hapus", limit: 1 })   // 1 dokumen oleh skrip, cek di web
hapusGanda.jalankan({ mode: "hapus" })             // sisanya
hapusGanda.unduh()                                 // -> ganda_dihapus_<waktu>.csv
```

**Wajib sesudahnya:** pindahkan `ganda_dihapus_*.csv` dari folder Unduhan ke **`audit/`**, lalu
arahkan audit ke dokumen yang dipertahankan (kalau tidak, run input berikutnya bisa membuat ganda lagi):

```bash
python fasih_sm/hapus_ganda/hapus_ganda.py --catat          # lihat
python fasih_sm/hapus_ganda/hapus_ganda.py --catat --tulis  # tulis ke audit
```

## Status penting

| Status | Arti |
| --- | --- |
| `DIHAPUS_TERVERIFIKASI` | dokumen hilang/berubah sesuai bukti rekaman |
| `PERIKSA` | keputusan tidak jelas — putuskan manual |
| ⛔ `POLA_BELUM_ADA` / `LIMIT_PERTAMA` | belum `rekam()` / penghapusan skrip pertama wajib `limit: 1` |
| ⛔ `DIHAPUS_BELUM_TERVERIFIKASI`, `PEMBANDING_HILANG` | cek dokumen itu & sesi sebelum lanjut |
| ⛔ `SESI_DITOLAK` | login ulang akun admin, reload halaman Data, tempel ulang |

## Berkas

`hapus_ganda.py` (grup ganda dari audit via `antar_pc/gabung_audit.daftar_ganda`, `--catat`),
`hapus_ganda_console.js` (cek, rekam, hapus, verifikasi), `hasil/hapus_ganda_console.siap.js`.
Uji: `node tests/test_hapus_ganda_console.js`, `python tests/test_gabung_audit.py`.
