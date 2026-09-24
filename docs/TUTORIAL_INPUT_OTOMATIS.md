# Tutorial Inject Usaha — format standar (**input_usaha.xlsx**)

Panduan langkah-demi-langkah untuk membuat, mengisi & mengirim dokumen usaha SE2026 ke
**fasih-web** secara otomatis dari **format standar input usaha** (file `input_usaha.xlsx`,
tab `input_usaha`) — untuk jenis usaha apa pun.

> Arti tiap kolom & aturan pemeriksaan: `docs/FORMAT_STANDAR_INPUT_USAHA.md`. Referensi padat
> skrip input: `docs/PANDUAN_GABUNGAN.md`. Alur khusus salin dari dokumen sumber (`salin_dokumen_sumber.csv`):
> `docs/PANDUAN_INPUT_OTOMATIS.md`.

Semua perintah **dijalankan DARI ROOT proyek** (folder hasil clone, mis. `D:\innovations\split_usaha`),
bukan dari dalam folder. Contoh benar: `python input_gabungan/main_gabungan.py ...`.

---

## Gambaran besar — 4 tahap

```
[A] Reset password mitra     -> semua PPL berpassword sama = FIXED_PASSWORD
        |                         (supaya skrip bisa login sbg tiap PPL)
[B] Ganti moda CAPI -> PAPI  -> tiap subsls punya assignment, fasih-web bisa "+Dokumen Baru"
        |
[C] Cek data (offline)       -> tahu baris mana SIAP, mana harus diperbaiki di sheet
        |
[D] Input ke fasih-web       -> dry-run dulu (aman), tinjau, baru --submit (irreversible)
```

Tahap **A** dan **B** adalah **prasyarat**: tanpa keduanya, tahap D akan gagal
login atau gagal membuat dokumen. Kalau password mitra & assignment sudah beres dari
sesi sebelumnya, langsung ke tahap **C**.

---

## Langkah 0 — siapkan sekali

1. **VPN kantor BPS aktif.** Tanpa ini fasih-web/fasih-sm/manajemen-mitra tidak bisa dibuka.
2. **Install** (sekali saja):
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. **Google Chrome biasa** (untuk tahap A & B yang lewat DevTools Console).
4. **Konfigurasi lokal** (sekali): salin `templates/config_lokal.contoh.py` ke `inti/config_lokal.py`,
   lalu isi `FIXED_PASSWORD`, `KODE_KAB`, dan (alur satu subsls) `GABUNGAN_SUBSLS_TUNGGAL` /
   `GABUNGAN_AKUN_TUNGGAL`. Templat itu menyalakan `GABUNGAN_MODE_MURNI` (isian 100% dari Excel).
   File itu tidak ikut git — aman untuk password.
5. **Siapkan sheet format standar**: salin hasil pendataan lapangan ke templat
   `templates/input_usaha.kosong.xlsx` (arti tiap kolom ada di tab `petunjuk` pada
   `templates/input_usaha.contoh.xlsx`), simpan sebagai **`input_usaha.xlsx`** di root proyek. Kalau diisi
   bersama di Google Sheets: unggah templatnya, isi tab **input_usaha**, lalu
   `File > Download > Microsoft Excel (.xlsx)` → simpan sebagai **`input_usaha.xlsx`**.
   > Setiap kali sheet diperbaiki, **download ulang** dan timpa `input_usaha.xlsx`.
   >

---

## Tahap A — Reset password mitra jadi `FIXED_PASSWORD`

**Kenapa perlu:** skrip input login ke fasih-web sebagai tiap PPL memakai satu
password tetap `FIXED_PASSWORD` (isi di `inti/config_lokal.py`, lihat `templates/config_lokal.contoh.py`). Reset ini
menyeragamkan password semua PPL ke nilai itu. **Lewati kalau sudah dilakukan.**

manajemen-mitra mendeteksi browser otomatis → jalurnya **Console Chrome biasa**.

```bash
python reset_mitra/reset_mitra.py --sumber input_usaha.xlsx --console
```

1. Chrome → login manajemen-mitra → buka **`/mitra/akun-mitra`** (JANGAN dashboard).
2. F12 → **Console** → tempel **seluruh** isi `reset_mitra_console.siap.js` → Enter
   (pertama kali Chrome minta ketik: `allow pasting`).
3. Uji dulu 1 akun, verifikasi mitra itu bisa login dengan password baru:
   ```js
   await resetMitra.jalankan({mode: "otomatis", limit: 1, sayaSudahMelihatDialog: true})
   ```
4. Kalau berhasil, besarkan bertahap lalu simpan audit:
   ```js
   await resetMitra.jalankan({mode: "otomatis", limit: 20, sayaSudahMelihatDialog: true})
   await resetMitra.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})
   resetMitra.unduh()
   ```

Progres tersimpan di browser; kalau terputus cukup tempel ulang & jalankan lagi —
akun yang sudah `DIRESET_TERVERIFIKASI` dilewati otomatis. Detail & troubleshooting:
**`docs/PANDUAN_RESET_MITRA.md`**.

---

## Tahap B — Ganti mode assignment CAPI → PAPI (fasih-sm)

**Kenapa perlu:** fasih-web hanya bisa "+ Dokumen Baru" di subsls yang **sudah
punya assignment**. Ini membuat tiap subsls di sheet input usaha punya assignment PAPI.
**Lewati kalau sudah dilakukan.**

fasih-sm juga mendeteksi bot → jalurnya **Console Chrome biasa**.

```bash
python ganti_moda/ubah_moda.py --sumber input_usaha.xlsx --cek       # daftar target, tanpa browser
python ganti_moda/ubah_moda.py --sumber input_usaha.xlsx --console   # tulis ubah_moda_console.siap.js
```

1. Chrome → login fasih-sm → buka list dengan **`perPage=100`** (wajib — satu subsls
   bisa ratusan assignment; skrip membaca semua halaman & menolak jalan kalau perPage < 50):
   `https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=100`
2. F12 → Console → tempel **seluruh** `ubah_moda_console.siap.js` → Enter.
3. Jalankan bertahap:
   ```js
   await ubahModa.jalankan({mode: "petakan"})                 // 1 subsls, read-only
   await ubahModa.jalankan({mode: "dryrun", limit: 5})        // centang & cek, TANPA klik Ganti Mode
   await ubahModa.jalankan({mode: "manual", limit: 1})        // KAMU klik "Ganti Mode" + konfirmasi
   await ubahModa.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})   // sisanya
   ubahModa.unduh()
   ```

Detail lengkap (cakupan satu vs semua, status berhenti, dll): **`docs/PANDUAN_GABUNGAN.md`
→ "Langkah 0"**.

---

## Tahap C — Cek data offline (tanpa browser/VPN)

Ini cepat (±2 detik) dan tidak menyentuh apa pun — cuma memvalidasi sheet.

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --cek
```

Hasilnya diringkas di layar + ditulis ke **`cek_gabungan.csv`** (rincian per baris).
Yang penting: baris berstatus **SIAP** aman diinput; baris `SKIP_DATA_*` **harus
diperbaiki di sheet dulu** (mis. Umur/Jenis Kelamin/Tahun beroperasi kosong, atau
opsi 11a yang tidak ada di form). Setelah memperbaiki sheet: download ulang → `--cek` lagi.

> Tabel masalah umum & cara perbaikannya ada di `docs/PANDUAN_GABUNGAN.md`
> ("Hasil pemeriksaan sheet").

---

## Tahap D — Input ke fasih-web

> **Butuh VPN aktif.** Skrip membuka Chrome (Playwright), login sebagai PPL baris
> itu (password `FIXED_PASSWORD`), membuat/menemukan dokumen, mengisi, dan **berhenti
> sebelum Kirim** kecuali kamu memberi `--submit`.

### D1. Dry-run SATU baris, lalu tinjau di browser

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --baris 2
```

`--baris` memakai **nomor baris seperti di Google Sheets** (judul = baris 1).
Tanpa `--submit` ini **dry-run**: mengisi tapi tidak mengirim. Buka dokumennya di
browser, cocokkan isian dengan sheet. Kalau ada yang salah, betulkan sheet /
lapor, jangan lanjut submit.

### D2. Dry-run bertahap (aman kalau terputus)

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --lewati-selesai --limit 10
```

`--lewati-selesai` mencocokkan lewat **kunci** (akun PPL + idsubsls + nama), jadi
tetap benar walau sheet diurutkan ulang. Batch **berhenti sendiri** setelah 3 baris
`ERROR_*` berturut-turut (mis. VPN putus) — atur dengan `--maks-error-beruntun N`.
`SKIP_*` tidak dihitung error.

Cek hasilnya di **`audit_log_gabungan.csv`** (lihat tabel status di bawah).

### D3. Kirim HANYA baris yang sudah ditinjau ⚠️ IRREVERSIBLE

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --baris 2,3,4 --submit
```

`--submit` = mode LIVE. Skrip akan minta ketik **`YA`** per batch sebelum benar-benar
klik Kirim. **Kirim tidak bisa dibatalkan** — kirim hanya baris yang sudah kamu tinjau
di D1/D2 dan yakin benar.

### Sesudah terkirim

1. **Approve oleh PML** — `docs/PANDUAN_APPROVE_PML.md`:

   ```bash
   python approve_pml/approve_pml.py --akun-pml <akun PML> --akun-ppl <akun PPL> --cek
   ```

2. **Pindah wilayah** ke subsls aslinya (kalau semua dokumen dibuat di satu subsls) —
   `docs/PANDUAN_PINDAH_WILAYAH.md`.

---

## Aturan emas keselamatan

1. **Kirim itu final.** Tidak ada undo setelah "Konfirmasi Kirim". Selalu dry-run &
   tinjau dulu; `--submit` hanya untuk baris yang sudah dicek.
2. **Jangan pernah sentuh field "Nomor Urut Bangunan".** Skrip sengaja tidak
   menyentuhnya; sekali tersentuh nilainya jadi `0` dan memicu galat keras.
3. **GALAT harus 0 sebelum kirim.** Baris dengan GALAT (selain kasus Nomor Urut
   Bangunan yang ditangani otomatis) otomatis di-skip — jangan dipaksa.
4. **Berhenti kalau ada yang janggal.** Semua skrip di sini dirancang berhenti &
   melapor daripada menebak. Kalau berhenti dengan status aneh, baca pesannya, jangan
   longgarkan pengaman.

---

## Status di `audit_log_gabungan.csv` (yang sering muncul)

| status                                                                             | artinya / tindakan                                                                    |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `DRY_RUN_SIAP_KIRIM`                                                             | GALAT=0 — tinjau lalu boleh`--submit`                                              |
| `SKIP_DOKUMEN_BELUM_ADA`                                                         | subsls belum punya assignment → ulang**Tahap B**, atau cek `--assignment-id` |
| `SKIP_GALAT_PERLU_REVIEW`                                                        | ada GALAT selain Nomor Urut Bangunan → baca`error_message`                         |
| `SKIP_VARIAN_BULANAN`                                                            | form minta rincian 30–33 (usaha baru beroperasi) → isi manual                       |
| `SKIP_26C_TIDAK_DIRENDER` / `SKIP_10B_TIDAK_DIRENDER` / `SKIP_13DE_KOSONG` / `SKIP_19_20_KOSONG` | form memunculkan rincian yang tidak ada/kosong di sheet → lengkapi sheet atau isi manual |
| `ERROR_LOGIN`                                                                    | cek VPN & password (harus = `FIXED_PASSWORD` → ulang **Tahap A**)                    |
| `ERROR_AKUN_SALAH`                                                               | sesi login nyangkut ke akun lain —**jangan kirim** baris ini                   |
| `ERROR_FIELD_NOT_FOUND`                                                          | selector meleset → ulangi dengan`--dump-dom`, lapor                                |

Selalu tengok kolom **`review_disarankan`**, terutama `dokumen SUDAH ADA sebelumnya`,
`AKUN TIDAK TERVERIFIKASI`, dan pola peringatan/kosong.

---

## Cheat sheet (jalankan dari root)

```bash
# Prasyarat (lewati kalau sudah)
python reset_mitra/reset_mitra.py  --sumber input_usaha.xlsx --console   # A: reset password -> Console
python ganti_moda/ubah_moda.py     --sumber input_usaha.xlsx --console   # B: ganti moda    -> Console

# Input
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --cek                      # C: cek offline
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --baris 2                  # D1: dry-run 1 baris
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --lewati-selesai --limit 10 # D2: dry-run batch
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --baris 2,3,4 --submit     # D3: KIRIM (irreversible)

# Uji offline (tanpa VPN, kapan saja)
python tests/test_gabungan_loader.py
python tests/test_fill_gabungan.py
```

Panduan terkait: `docs/PANDUAN_GABUNGAN.md` (referensi alur & tabel temuan sheet),
`docs/PANDUAN_RESET_MITRA.md` (tahap A), `docs/PANDUAN_EKSPOR_MANUAL.md` (khusus backlog lama).
