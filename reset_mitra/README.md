# reset_mitra — samakan password akun PPL (manajemen-mitra)

Skrip login fasih-web memakai SATU password (`FIXED_PASSWORD`) untuk semua akun. Alat ini
mereset password akun PPL ke nilai itu di
[manajemen-mitra](https://manajemen-mitra.bps.go.id/mitra/akun-mitra) lewat Console Chrome:
cari email → tepat 1 mitra → **Reset PW** → isi field password (field email tidak disentuh) →
**Reset Password** → tutup panel "OK". Email yang cocok ke >1 mitra dilewati.
⚠️ Reset sulit dibatalkan — mulai `limit: 1` dan buktikan akun itu bisa login.

## Pakai

Daftar akun: satu email per baris di `bahan/daftar_akun_ppl.txt` (atau `--email a@x.com,b@x.com`,
atau `--sumber <sheet>` yang punya kolom `Akun PPL`).

```bash
python reset_mitra/reset_mitra.py --daftar bahan/daftar_akun_ppl.txt --cek       # -> hasil/target_reset_mitra.csv
python reset_mitra/reset_mitra.py --daftar bahan/daftar_akun_ppl.txt --console   # -> hasil/reset_mitra_console.siap.js
```

Chrome biasa → login → buka **`/mitra/akun-mitra`** (bukan dashboard) → F12 Console → tempel:

```js
await resetMitra.jalankan({mode: "cocok"})                                           // baca-saja: tiap email = 1 mitra?
await resetMitra.jalankan({mode: "otomatis", limit: 1, sayaSudahMelihatDialog: true}) // 1 akun, coba login
await resetMitra.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})           // sisanya
resetMitra.unduh()
```

## Status penting

| Status | Arti |
| --- | --- |
| `COCOK` / `DIRESET_TERVERIFIKASI` | aman / berhasil |
| `GANDA`, `TIDAK_KETEMU`, `COCOK_TEKS` | tidak direset — telusuri manual |
| ⛔ `FIELD_PASSWORD_TIDAK_ADA`, `TOMBOL_KONFIRMASI_AMBIGU` | dialog tidak sesuai dugaan — buka satu dialog Reset PW, jalankan `resetMitra.petakanDialog()` |
| ⛔ `DIRESET_BELUM_TERVERIFIKASI` | diklik tapi sukses tak terkonfirmasi — cek manual |

## Berkas

`reset_mitra.py` (daftar akun → target, suntik `FIXED_PASSWORD`), `reset_mitra_console.js`
(cari, pilih field password, reset, tutup panel OK), `hasil/` (berisi email & password — jangan
dibagikan). Uji: `node tests/test_reset_mitra_console.js`.
