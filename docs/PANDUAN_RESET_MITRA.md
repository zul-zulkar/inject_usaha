# Panduan Reset Password Mitra (manajemen-mitra)

Reset password **akun PPL** yang terdaftar di `Agenda.xlsx` (tab gabungan) lewat
[https://manajemen-mitra.bps.go.id/mitra/akun-mitra](https://manajemen-mitra.bps.go.id/mitra/akun-mitra).

- **Cakupan:** hanya kolom **Akun PPL** (371 akun unik). PML tidak disentuh.
- **Kunci cocok:** alamat gmail di Agenda = username/pencarian di manajemen-mitra.
- **Cara:** DevTools Console Chrome biasa (login sendiri), sama seperti `ganti_moda` —
  manajemen-mitra login-gated & kemungkinan mendeteksi browser otomatis.

> ⚠️ **Reset password itu sensitif dan sulit dibatalkan (mitra bisa terkunci).**
> Struktur halaman dipetakan (2026-09-14): tabel kolom NIK, Email, Nama Lengkap,
> Tanggal Terdaftar, Kelengkapan Data, Status SSO, Status Akun & Aksi; kotak
> "Cari NIK, Email, Nama Lengkap, atau Sobat ID / Username (min. 5 karakter)" —
> **gmail ketemu lewat kolom Email** (terbukti: 1 mitra untuk 1 email); dan tombol
> **"Reset PW" per baris**. Klik "Reset PW" membuka panel **2 field** (temuan user
> 2026-09-14): **field 1 = password baru**, **field 2 = email yang SUDAH terisi (jangan
> disentuh)**, lalu tombol **"Reset Password"**. Skrip mengisi HANYA field non-email
> dengan **password baru = `FIXED_PASSWORD`** (dari `inti/config_lokal.py`, disuntik `--console` — jadi semua mitra
> tahu passwordnya, tidak terkunci), lalu klik "Reset Password". Ubah nilai lewat
> `jalankan({passwordBaru: "..."})` atau `PASSWORD_BARU` di skrip.
>
> Panel itu **belum pernah saya render sendiri** (tab yang saya buka selalu mendarat di
> modal "Pilih Akun"). Skrip mengisi field non-email & menekan "Reset Password"; kalau
> bentuknya di luar dugaan ia BERHENTI (`FIELD_PASSWORD_TIDAK_ADA`/`TOMBOL_KONFIRMASI_AMBIGU`)
> daripada mengisi field salah. Karena itu **WAJIB mulai `otomatis` dengan `limit: 1`**,
> lalu pastikan mitra itu bisa login dengan password baru itu, baru dibesarkan. Kalau berhenti,
> buka satu dialog Reset PW lalu jalankan `resetMitra.petakanDialog()` dan kirim outputnya.
>
> Terverifikasi 2026-09-14 (limit:1 → `DIRESET_TERVERIFIKASI`): tombol "Reset Password"
> **bukan `<button>` polos**, jadi skrip mencakup `<a>`/`role=button` juga. Setelah reset
> berhasil muncul **panel konfirmasi "OK"** — skrip menutupnya otomatis (kalau dibiarkan,
> panel itu menutupi akun berikutnya & batch macet).
>
> ⚠️ Jalankan hanya di halaman **`/mitra/akun-mitra`**, bukan dashboard — skrip menolak
> kalau URL-nya bukan akun-mitra (di dashboard ada kotak "Cari survei atau kegiatan"
> yang beda; ini sempat salah 2026-09-14).

## Langkah

```bash
python reset_mitra/reset_mitra.py --sumber Agenda.xlsx --cek       # daftar email PPL -> target_reset_mitra.csv
python reset_mitra/reset_mitra.py --sumber Agenda.xlsx --console   # tulis reset_mitra_console.siap.js
```

1. Chrome → login manajemen-mitra → buka `/mitra/akun-mitra`.
2. F12 → Console → tempel **seluruh** isi `reset_mitra_console.siap.js` → Enter
   (pertama kali Chrome minta ketik `allow pasting`).
3. **Petakan** (read-only, 1 email): buktikan pencarian gmail menemukan mitra & rekam
   kontrol reset:

   ```js
   await resetMitra.jalankan({mode: "petakan"})
   resetMitra.unduhDump()   // kirim file dump ini ke pengembang untuk mengisi SELEKTOR_RESET
   ```
4. **Cocok** (read-only, semua email): pastikan tiap gmail menemukan tepat satu mitra:

   ```js
   await resetMitra.jalankan({mode: "cocok"})
   resetMitra.unduh()       // simpan hasil sebagai CSV audit
   ```

   Tinjau statusnya: `COCOK` (aman), `COCOK_TEKS` (email cuma muncul di teks — periksa),
   `GANDA`/`TIDAK_KETEMU` (jangan direset; cek manual).
5. **Otomatis SATU akun dulu** (wajib) — skrip klik "Reset PW", isi password baru (`FIXED_PASSWORD`), simpan:

   ```js
   await resetMitra.jalankan({mode: "otomatis", limit: 1, sayaSudahMelihatDialog: true})
   ```

   Lalu **buka login mitra & pastikan password baru bisa masuk** untuk akun itu. Kalau ya:
6. **Otomatis batch** — perbesar bertahap (aman diputus/disambung, yang beres dilewati):

   ```js
   await resetMitra.jalankan({mode: "otomatis", limit: 20, sayaSudahMelihatDialog: true})
   await resetMitra.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})   // sisanya
   ```

   Alternatif tanpa otomatis: `mode: "manual"` (skrip menyorot tombol, **kamu** yang isi & simpan).

`resetMitra.berhenti()` / `.ringkasan()` / `.unduh()` / `.unduhDump()` / `.hapusHasil()`.
Hasil tersimpan di browser (localStorage), jadi kalau terputus cukup tempel ulang & jalankan lagi.

## Status di audit

| status                                              | arti                                                                                                                                                                                   |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COCOK`                                           | gmail = username/email mitra, tepat satu. Aman.                                                                                                                                        |
| `COCOK_TEKS`                                      | gmail hanya muncul di teks baris (bukan kolom username) — tinjau dulu.                                                                                                                |
| `GANDA`                                           | 1 gmail → >1 mitra.**Tidak direset & dilewati**, batch lanjut; daftarnya dicetak di akhir run. Telusuri manual. (`lewatiGanda: false` = batch berhenti di sini seperti dulu.) |
| `TIDAK_KETEMU`                                    | jangan reset; perbaiki/telusuri manual (dilewati, batch lanjut).                                                                                                                       |
| `SELEKTOR_BELUM_DIISI`                            | mode reset dipanggil sebelum`SELEKTOR_RESET` diisi dari petakan.                                                                                                                     |
| `DIRESET_TERVERIFIKASI`                           | reset berhasil (ada indikasi sukses di halaman).                                                                                                                                       |
| `DIRESET_BELUM_TERVERIFIKASI` / `BELUM_BERUBAH` | reset diklik tapi sukses tak terkonfirmasi — cek manual.                                                                                                                              |
