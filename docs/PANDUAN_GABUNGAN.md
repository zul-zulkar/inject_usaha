# Panduan Input — Sheet "gabungan" (Agenda)

Sumber: Google Sheet **Agenda**, tab **gabungan** (pangkalan gas LPG + faskes).
Beda dengan backlog LKpenyalinan: setiap kolom sudah berupa **jawaban final per
rincian form**. Skrip mengetik apa adanya: tidak ada 10%, tidak ada file export,
tidak ada aturan pekerja ≤3, dan tidak ada override aset/luas tanah = 0.

**Templat kosong:** `templates/Agenda.contoh.xlsx` — tab `gabungan` berjudul kolom persis yang dibaca skrip, dengan dropdown opsi form, tab `petunjuk` (penjelasan tiap kolom) dan tab `contoh` (satu baris fiktif). Salin ke root proyek sebagai `Agenda.xlsx`, isi tab `gabungan`, lalu jalankan `--cek`.

Aturan keselamatan di `README.md` tetap berlaku penuh: default dry-run, `--submit`
wajib ketik `YA`, dan Nomor Urut Bangunan tidak disentuh.

---

## ⚠️ Rencana 2026-09-14 — SATU subsls + SATU akun PPL

Sebagian subsls sudah ditandai selesai sehingga tidak bisa ditambah assignment. Karena itu
**semua dokumen dibuat di satu subsls oleh satu akun PPL**, lalu wilayahnya dipindah
belakangan lewat *ubah alokasi wilayah* (otomatisasinya dibuat setelah semua terinput).

- Isi `GABUNGAN_SUBSLS_TUNGGAL` & `GABUNGAN_AKUN_TUNGGAL` di `inti/config_lokal.py` (salin dari `templates/config_lokal.contoh.py`), atau beri
  `--subsls-tunggal 51080… --akun-tunggal ppl@gmail.com` di setiap perintah. Tanpa keduanya skrip
  menolak jalan (alur lama: `--per-baris`).
- Langkah 0 di bawah cukup untuk **subsls tunggal itu saja**, dan assignment PAPI-nya harus
  milik **akun tunggal** (akun lain tidak akan melihat "+ Dokumen Baru" di subsls itu).
- Semua dokumen masuk **satu list PENDATAAN**, jadi nama dokumen yang sama persis di sheet
  (walau beda PPL/subsls) di-skip `NAMA_TUMPANG_TINDIH` — beri pembeda di sheet.
- Wilayah asli baris tetap di kolom `idsubsls` audit; `idsubsls_input` = subsls tempat dokumen
  dibuat; `dokumen_url` = alamat dokumennya. Ketiganya bahan ubah alokasi wilayah nanti.
  `WILAYAH_TIDAK_KONSISTEN` jadi tanda review (baru berarti saat realokasi), bukan skip.
- Kodepos, geotag, dan alamat tetap milik baris (data asli usaha), bukan milik subsls tunggal.

**Yang dicek langsung saat input otomatis:**

| Cek | Kalau gagal |
|---|---|
| Akun yang login = akun tunggal (dibaca dari API, bukan sapaan) | `ERROR_AKUN_SALAH`, batch **berhenti** |
| Subsls tunggal bisa dipilih di Wilayah Responden | `STOP_SUBSLS_TIDAK_BISA_DIPILIH`, batch **berhenti** |
| Tombol "+ Dokumen Baru" ada / dokumen berhasil dibuat | `SKIP_DOKUMEN_BELUM_ADA`, batch **berhenti** (pasti berulang) |
| Rincian 1–6 BLOK I dokumen = subsls tunggal | beda → `STOP_WILAYAH_DOKUMEN_BEDA`, batch **berhenti**; tidak terbaca → tetap diisi, tanda review, dan saat `--submit` jadi `SKIP_WILAYAH_TIDAK_TERVERIFIKASI` (tidak dikirim) |

Format nilai rincian 1–6 belum pernah terekam; lihat kolom `wilayah_dokumen` di audit setelah
dry-run pertama. Kalau isinya `TIDAK_TERBACA`, kirimkan nilainya supaya pencocokannya disesuaikan.

Duplikat dicegah lewat audit: begitu dokumen baru terbuat, baris `DOKUMEN_DIBUAT` + URL-nya
langsung ditulis. Run berikutnya membuka dokumen itu lewat URL (list satu akun berhalaman,
pencarian nama tidak bisa diandalkan) dan **tidak pernah membuatnya lagi**. Jangan hapus/edit
`audit_log_gabungan.csv` di tengah pekerjaan. Login diulang tiap `GABUNGAN_BARIS_PER_SESI` (40) baris.

## Langkah 0 — ubah mode assignment CAPI → PAPI (fasih-sm)

fasih-web hanya bisa "+ Dokumen Baru" di subsls yang sudah punya assignment, jadi subsls
tujuan perlu punya assignment PAPI dulu (rencana satu subsls: hanya subsls tunggal, milik akun tunggal).

**fasih-sm mendeteksi browser otomatis (F5/TSPD)**, jadi jalur utamanya **Console Chrome
biasa**, bukan Playwright. Pakai akun yang berhak "Ganti Mode", login seperti biasa.

```bash
python ganti_moda/ubah_moda.py --sumber Agenda.xlsx --cek       # daftar target, tanpa browser
python ganti_moda/ubah_moda.py --sumber Agenda.xlsx --console   # tulis ubah_moda_console.siap.js
```

1. Chrome → login fasih-sm → buka list dengan `perPage=100` (**wajib** — skrip menolak jalan kalau
   perPage < 50). Skrip **tidak pernah memindah halaman**: hanya membaca halaman yang tampil setelah
   pencarian, karena halaman yang dipindah tidak memuat datanya dengan benar. **Jangan pasang filter
   Mode** saat skrip jalan (belum didukung):
   `https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=100`
2. F12 → Console → tempel **seluruh** isi `ubah_moda_console.siap.js` → Enter
   (pertama kali Chrome minta ketik `allow pasting`).
3. Jalankan bertahap, satu perintah per langkah:

| Perintah di Console | Yang terjadi |
|---|---|
| `await ubahModa.jalankan({mode: "petakan"})` | 1 subsls: cari & baca tabel, buka/tutup menu. **Tanpa centang.** |
| `await ubahModa.jalankan({mode: "dryrun", limit: 5})` | Centang, cocokkan angka "(N)" di menu, lepas centang. **Tidak klik Ganti Mode.** |
| `await ubahModa.jalankan({mode: "manual", limit: 1})` | Skrip menyiapkan & menyorot item; **kamu yang klik "Ganti Mode" + konfirmasi**. Skrip memverifikasi Mode = PAPI. |
| `await ubahModa.jalankan({mode: "manual"})` | Sisanya, tetap satu klik manusia per subsls. |
| `await ubahModa.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})` | Opsional. Hanya bisa setelah ada ≥1 hasil manual terverifikasi. |

`ubahModa.berhenti()` menghentikan, `ubahModa.ringkasan()` menghitung status,
`ubahModa.unduh()` menyimpan hasil sebagai CSV (audit). Hasil tersimpan di browser itu, jadi
kalau terputus cukup tempel ulang & jalankan lagi — subsls yang sudah tuntas dilewati.

Cadangan (berisiko terdeteksi bot): `ganti_moda/ubah_moda.py --petakan` / `--eksekusi` lewat
Playwright, login manual, profil di `.profil_fasih_sm/`.

- `cakupan: "satu"` (default): pastikan ada **satu** assignment PAPI per subsls — petugasnya
  **siapa pun** (ketetapan 2026-09-14; `PETUGAS_BEDA`/`izinkanPetugasLain` sudah dihapus, kini
  bawaan). Assignment milik PPL sheet didahulukan kalau ada. Subsls yang sudah punya PAPI →
  `SUDAH_ADA_PAPI` — tapi hanya PAPI di halaman yang tampil yang terlihat; kalau PAPI-nya ada di
  halaman 2 dst., subsls itu bisa mendapat 1 PAPI tambahan (diizinkan). `cakupan: "semua"`: ubah
  seluruh CAPI yang tampil; berhenti `PERLU_HALAMAN_LAIN` kalau sisanya di halaman lain.
- **Memetakan filter Mode** (supaya PAPI di halaman lain ikut terlihat): buka filter secara manual,
  lalu di tiap langkah (semua tertutup → ikon filter terbuka → pilihan Mode tampil → PAPI dipilih →
  filter diterapkan) jalankan `ubahModa.petakanFilter("keterangan langkah")`. Tidak mengklik apa
  pun. Terakhir `ubahModa.petakanFilter.hasil()` mengunduh JSON-nya — kirimkan untuk diotomatiskan.
- Baris subsls **lain** yang ikut tampil di hasil pencarian diabaikan (tidak pernah dicentang) —
  dicatat di kolom `pesan` sebagai "N baris subsls lain diabaikan".
- Batch **berhenti seketika** kalau cara kerja halaman tidak sesuai dugaan: halaman hasil pencarian
  tidak memuat satu pun baris subsls itu (`SUBSLS_TIDAK_TAMPIL`), baris tercentang ≠
  rencana, angka "(N)" di menu ≠ jumlah dicentang, dialog/tombol konfirmasi tidak jelas, atau
  mode tidak terverifikasi PAPI setelah diubah. Lihat `log_fasih_sm/` (dump + rekaman API) dan
  `audit_ubah_moda.csv`.
- 29 pasangan idsubsls yang tidak konsisten dengan kolom Pilih **dikeluarkan** dari target.

## Alur input

```bash
# 0. Sekali: pip install -r requirements.txt && playwright install chromium
# 1. Download tab gabungan: File > Download > Microsoft Excel (.xlsx) -> Agenda.xlsx

# 2. Periksa tanpa browser/VPN (2 detik). Rincian per baris -> cek_gabungan.csv
python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --cek

# 3. Dry-run SATU baris, lalu tinjau dokumennya di browser
python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --baris 2

# 4. Dry-run bertahap (aman dilanjutkan kalau terputus)
python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --lewati-selesai --limit 10

# 5. Kirim HANYA baris yang sudah ditinjau (irreversible)
python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --baris 2,3,4 --submit
```

`--baris` memakai nomor baris seperti yang terlihat di Google Sheets (judul = baris 1).
`--lewati-selesai` mencocokkan lewat `kunci` (akun PPL + idsubsls + nama), jadi
tetap benar walaupun sheet diurutkan ulang.

**Penamaan usaha** (ketetapan 2026-09-14): nama dokumen ("+ Dokumen Baru"), nama di
SE2026-P, dan 8b diketik sebagai `<nama usaha> (<12a nama pengusaha>)`, mis.
`PANGKALAN GAS I NYOMAN CONTOH (I NYOMAN CONTOH)`. Kalau membuat dokumen manual,
pakai nama persis kolom `nama_dokumen` di `cek_gabungan.csv`. `kunci` tetap dihitung
dari nama mentah sheet.

Batch **berhenti sendiri** setelah 3 baris `ERROR_*` berturut-turut (mis. VPN putus);
atur dengan `--maks-error-beruntun N`. `SKIP_*` tidak dihitung sebagai error.

---

## Hasil pemeriksaan sheet per 2026-09-13

| | baris |
|---|---|
| **SIAP** (semuanya pangkalan gas LPG, 269 akun PPL, ±12 jam) | **432** |
| `SKIP_DATA_WAJIB_KOSONG` | 396 |
| `SKIP_DATA_OPSI_TIDAK_ADA_DI_FORM` | 14 |

Satu baris bisa kena lebih dari satu masalah. Seluruh baris faskes tertahan.
Yang perlu diperbaiki **di sheet**:

| Masalah | Baris | Keterangan |
|---|---|---|
| 12c Umur kosong | 396 | Wajib (`*`) di form |
| Nama Jalan kosong | 242 | Lihat `GABUNGAN_IZINKAN_JALAN_KOSONG` di bawah |
| 12b Jenis Kelamin kosong | 208 | Wajib (`*`) |
| 25 Tahun beroperasi kosong | 164 | Blok 26–29 tidak dirender tanpa ini |
| 24a1+24b1 ≠ 24a2+24b2 | 123 | Semuanya praktik bidan/dokter, mis. perempuan 2 tapi tidak dibayar 1 |
| idsubsls ≠ kolom "Pilih KECAMATAN..SUBSLS" | 60 | 33 beda desa, 27 beda SLS (idsubsls berpola `…200100`). Tidak ditebak mana yang benar |
| 11a `1. Perseroan Terbatas (PT)/CV` | 14 | Opsi itu **tidak ada** di form. Pilih `1.a. Perseroan (PT/NV, …)` atau `7. Persekutuan Komanditer (CV)` |

Setelah sheet diperbaiki, download ulang lalu jalankan `--cek` lagi.

---

## Keputusan yang dipakai skrip (ubah di `config.py`)

| Setelan | Default | Arti |
|---|---|---|
| `GABUNGAN_13F_DARI_13A` | `True` | 13f "produk utama" wajib, tapi sheet tidak punya kolomnya → disalin dari 13a. Preseden: record manual 3 (KBLI 47772). Kalau sheet diberi kolom `13. f.`, kolom itu yang dipakai. |
| `GABUNGAN_IZINKAN_JALAN_KOSONG` | `False` | Label Nama Jalan di form **tanpa** tanda wajib, tapi belum pernah diuji dikosongkan. Kalau diubah `True`, uji dulu 1 baris. |
| `ASSIGNMENT_ID_GABUNGAN` | `fd68e454-…` | Segmen URL list PENDATAAN; konstan di backlog lama (12 PPL). Belum diuji untuk PPL gabungan — kalau `SKIP_DOKUMEN_BELUM_ADA` massal, cek ini dulu (`--assignment-id`). |

Rincian yang tidak punya kolom di sheet memakai default lama **hanya kalau dirender**,
dan dicatat di kolom `review_disarankan`: 19a/19c dan 20a/20b/20c (BPOM).

---

## Status di `audit_log_gabungan.csv`

| status | artinya |
|---|---|
| `DRY_RUN_SIAP_KIRIM` | GALAT=0, tinjau lalu `--submit` |
| `SKIP_DOKUMEN_BELUM_ADA` | wilayah belum punya assignment / assignment-id salah |
| `SKIP_DOKUMEN_NAMA_LAMA` | list memuat dokumen bernama mentah sheet (format lama) tapi tidak ada yang bernama `<nama> (<12a>)` — dokumen baru TIDAK dibuat agar tidak duplikat; cek list manual |
| `DOKUMEN_DIBUAT` | catatan antara (dokumen baru + URL), selalu disusul status akhir; kalau jadi status terakhir, proses mati di tengah — jalankan ulang, dokumen dibuka lewat URL |
| `STOP_SUBSLS_TIDAK_BISA_DIPILIH` | subsls tunggal tidak ada di Wilayah Responden akun ini (belum PAPI / sudah selesai) — batch berhenti |
| `STOP_WILAYAH_DOKUMEN_BEDA` | dokumen yang terbuka ternyata di subsls lain — batch berhenti, cek `wilayah_dokumen` |
| `SKIP_WILAYAH_TIDAK_TERVERIFIKASI` | `--submit`: wilayah dokumen tidak terbaca, sengaja tidak dikirim |
| `SKIP_GALAT_PERLU_REVIEW` | ada GALAT selain Nomor Urut Bangunan — baca `error_message` |
| `SKIP_VARIAN_BULANAN` | form minta rincian 30–33 (bulanan); isi manual |
| `SKIP_26C_TIDAK_DIRENDER` | KBLI tanpa 26c padahal sheet 26c > 0; isi manual |
| `SKIP_10B_TIDAK_DIRENDER` / `SKIP_13DE_DIRENDER` | form bercabang di luar isi sheet |
| `ERROR_LOGIN` / `ERROR_AKUN_SALAH` | cek VPN/kata sandi; jangan kirim baris akun salah |
| `ERROR_FIELD_NOT_FOUND` | selector meleset — ulangi dgn `--dump-dom` |

Wajib ditengok sebelum kirim: kolom `review_disarankan`, terutama
`dokumen SUDAH ADA sebelumnya`, `AKUN TIDAK TERVERIFIKASI`, dan pola peringatan/kosong.

Uji offline: `python tests/test_gabungan_loader.py` dan `python tests/test_fill_gabungan.py`.
