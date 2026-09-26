# fasih_sm — alat Console fasih-sm

fasih-sm menolak browser otomatis (Playwright), jadi kelima alat di sini bekerja **dua langkah**:
skrip Python menyiapkan target dan menulis `<alat>/hasil/<alat>_console.siap.js`, lalu Anda
**menempelkan isi berkas itu di DevTools Console Chrome biasa** yang sudah login fasih-sm.

| Alat | Fungsi | Akun | Tutorial |
| --- | --- | --- | --- |
| [`ganti_moda/`](ganti_moda/) | ganti mode assignment CAPI → PAPI (supaya "+ Dokumen Baru" muncul), atau balik ke CAPI | admin kab | [README](ganti_moda/README.md) |
| [`buka_wilayah/`](buka_wilayah/) | Buka Wilayah (batalkan "Listing Selesai") | admin kab | [README](buka_wilayah/README.md) |
| [`pindah_wilayah/`](pindah_wilayah/) | pindahkan dokumen yang sudah di-approve ke subsls aslinya | admin kab | [README](pindah_wilayah/README.md) |
| [`tandai_selesai/`](tandai_selesai/) | Tandai Selesai Listing | admin kab | [README](tandai_selesai/README.md) |
| [`hapus_ganda/`](hapus_ganda/) | hapus dokumen GANDA (sisa draft/kiriman dobel) | admin | [README](hapus_ganda/README.md) |

## Cara menempel (sama untuk semua alat)

1. Jalankan perintah Python alatnya (lihat README-nya) → berkas `*.siap.js` di `hasil/`.
2. Chrome biasa → login fasih-sm → buka halaman **Data** survei
   (`.../app/surveys/<survei>/<periode>/data`; reset mitra: halaman akun-mitra).
3. `F12` → tab **Console** → ketik `allow pasting` sekali kalau Chrome memintanya.
4. Buka berkas `*.siap.js` di Notepad → salin semua → tempel di Console → Enter.
5. Jalankan mode baca-saja dulu, lalu eksekusi **`limit: 1`**, periksa di web, baru sisanya.

Perintah bantu yang ada di semua alat (ganti `alat` dengan `ubahModa`, `bukaWilayah`,
`pindahWilayah`, `tandaiSelesai`, `hapusGanda`):

```js
alat.berhenti()    // berhenti rapi setelah item yang sedang diproses
alat.ringkasan()   // hitungan status yang tersimpan
alat.unduh()       // unduh hasil sbg CSV — simpan sbg bukti
```

Hasil tersimpan di browser (localStorage) per tab/domain: kalau terputus (reload, sesi habis),
tempel ulang berkas yang sama dan jalankan perintah yang sama — yang sudah tuntas dilewati.
Jaga tab fasih-sm tetap di depan saat skrip berjalan. Status bertanda ⛔ menghentikan batch —
baca pesannya dulu, jangan dipaksa.

## Kode

Tiap alat = `<alat>.py` (target + suntik ke template, TANPA browser) + `<alat>_console.js`
(logika Console yang diuji Node: `tests/test_<alat>_console.js`). Kode kabupaten disuntik dari
`KODE_KAB` (`inti/config_lokal.py`).
