# ganti_moda — ganti mode assignment CAPI ⇄ PAPI (fasih-sm)

fasih-web hanya bisa "+ Dokumen Baru" di subsls yang punya assignment **PAPI**. Alat ini mengubah
assignment tertentu dari CAPI ke PAPI (atau balik), **satu kode identitas per putaran**: cari kode
→ centang baris yang kodenya PERSIS sama → Aksi Lainnya → "Ganti Mode (Ke PAPI) (1)" → konfirmasi
→ mode dicek ulang berkala sampai terbaca PAPI. Kode yang sudah diklik tidak pernah diklik ulang.

## Pakai

Siapkan daftar kode identitas (`<idsubsls> - <jenis> - <no>`, satu per baris, atau .xlsx) — contoh
[`templates/daftar_kode_identitas.contoh.txt`](../../templates/daftar_kode_identitas.contoh.txt).

```bash
python fasih_sm/ganti_moda/ubah_moda.py --daftar bahan/daftar_kode_identitas.txt --cek       # periksa daftar
python fasih_sm/ganti_moda/ubah_moda.py --daftar bahan/daftar_kode_identitas.txt --console   # -> hasil/ubah_moda_console.siap.js
```

Tempel di Console halaman Data survei (lihat [`../README.md`](../README.md)), lalu:

```js
await ubahModa.jalankan({mode: "petakan"})              // baca-saja: struktur tabel & menu
await ubahModa.jalankan({mode: "dryrun", limit: 3})     // tidak ada yang diubah
await ubahModa.jalankan({mode: "otomatis", limit: 1})   // 1 kode sungguhan, cek di fasih-sm
await ubahModa.jalankan({mode: "otomatis"})             // sisanya
ubahModa.unduh()
```

**Balik PAPI → CAPI per subsls:** `--subsls bahan/daftar_subsls.txt --ke CAPI --console` (lewat menu
⋮ per baris). Target tanpa Python: `ubahModa.muatDaftarKode(\`...\`)` di Console.

## Status penting

| Status | Arti |
| --- | --- |
| `DIUBAH_TERVERIFIKASI` / `KODE_SUDAH_PAPI` | tuntas |
| `DIUBAH_MENUNGGU` | sudah diklik, menunggu terbaca PAPI — **jangan klik manual lagi** |
| `KODE_TIDAK_ADA` / `KODE_TIDAK_TAMPIL` | kode tidak ditemukan / di halaman lain — cek manual; batch lanjut |
| ⛔ `DIUBAH_BELUM_TERVERIFIKASI` | 15 menit belum PAPI — cek di fasih-sm sebelum mengulang |
| ⛔ `PENCARIAN_TIDAK_MENYARING`, `KODE_GANDA`, `CENTANG_TIDAK_SESUAI` | tampilan tidak sesuai dugaan — lepas centang manual, laporkan |
| ⛔ `RATE_LIMIT` | server membalas 429 terus — tunggu, jalankan lagi |

## Berkas

| Berkas | Isi |
| --- | --- |
| `ubah_moda.py` | baca daftar/sheet → target, `--console` suntik ke template; jalur Playwright lama (`--petakan`/`--eksekusi`) |
| `ubah_moda_console.js` | logika Console (cari, centang, menu, verifikasi, antrean cek ulang, 429) |
| `hasil/` | `ubah_moda_console.siap.js`, `target_ubah_moda.csv`, audit & profil jalur Playwright |

Uji: `python tests/test_ubah_moda.py`, `node tests/test_ubah_moda_console.js` (8 kegagalan lama:
`normalisasiKode()` di Console sengaja tidak lagi mengurai kode, ujinya masih mengharapkan bentuk
baku — belum diputuskan mana yang benar).
