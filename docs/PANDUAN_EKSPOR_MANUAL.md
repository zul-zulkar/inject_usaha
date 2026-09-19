# Panduan Praktis — Ekspor Manual Data fasih-sm per Assignment

Dipakai SELAMA `scrape_source.py` (otomatis via Playwright) kena deteksi bot
di fasih-sm. Ini jalan pintas manual — dijalankan lewat browser & akun biasa
satu assignment per satu waktu, jadi tidak ada automation fingerprint. **Ini
BUKAN dibuat untuk bulk/loop otomatis** — kalau butuh proses banyak
assignment sekaligus tanpa risiko deteksi bot lagi, itu di luar cakupan
skrip-skrip di repo ini (pertimbangkan tool lain, bukan otomatisasi
tambahan di sini).

## Metode A (UTAMA) — Copy response API, lalu konversi

Terbukti jauh lebih akurat daripada scrape DOM: satu request yang sudah
otomatis dipanggil SPA-nya sendiri saat halaman dimuat ternyata
mengembalikan SELURUH jawaban assignment sbg JSON, dgn nama field asli
(bukan tebakan label teks). Sudah divalidasi cocok 100% terhadap satu
sample nyata (lihat `export/coba.json` → `export/coba.converted.json`).

### Langkah 1 — Buka assignment manual

1. VPN kantor aktif, login manual biasa ke fasih-sm.
2. Buka link assignment yang dituju (dari kolom `link` backlog CSV/Excel,
   atau gabungan `survey_assignment_id` + `row_assignment_id` — lihat
   `scrape_source.py:62-66` utk polanya kalau cuma pegang potongan id).
3. Tunggu sampai teks "Loading Data..." hilang & halaman selesai render.

### Langkah 2 — Ambil response dari Network tab

1. `F12` → tab **Network** → filter **Fetch/XHR**.
2. Reload halaman (Ctrl+R) sekali.
3. Cari request ke:
   ```
   .../app/api/assignment-general/api/assignment/get-by-assignment-id?assignmentId=...
   ```
4. Klik request itu → panel kanan tab **Response** → klik-kanan di dalam
   area response → **"Copy value"** (atau **"Store as global variable"**
   lalu di Console ketik `copy(temp1)`).
5. Paste ke file baru di folder `export/`, simpan sbg `.json` (folder ini
   sudah masuk `.gitignore` — aman berisi data pribadi responden).

**Tidak ada request baru yang dikirim** di langkah ini (cuma baca response
yang sudah ke-load pas reload normal) — risiko deteksi bot minimal, sama
seperti kamu buka halaman itu manual seperti biasa.

### Langkah 3 — Konversi ke field yang rapi

```bash
python convert_manual_export.py export/nama_file.json
```

Ini otomatis:
- Cari suffix usaha (`nama_komersial#1002` dst — 1 keluarga bisa >1 usaha,
  script proses semua & tampilkan `nama_usaha_raw` masing2 biar kamu pilih
  yang benar).
- Petakan ke field BLOK II (nama komersial, nama pengusaha, jenis kelamin,
  kegiatan utama, 13b1/b2/b3, dst) — termasuk yang jadi gap di
  `scrape_source.py` selama ini.
- Scrape **kepemilikan modal** (rincian 29) langsung dari sumber, bukan
  hardcode 100% Pribadi seperti asumsi lama di `config.py`.
- Hitung **pekerja dibayar/tidak dibayar** dari 2 pasang angka marginal
  (`tk_laki`/`tk_pr` & `tk_dibayar`/`tk_tdk_dibayar`) — kalau kombinasinya
  ambigu (kedua gender sama2 punya pekerja dibayar), ditandai
  `AMBIGU_PERLU_CEK_MANUAL`, TIDAK ditebak.
- Sertakan `financial_crosscheck_vs_backlog_csv` (gaji, biaya produksi,
  pendapatan, aset, dst) — buat konfirmasi angka backlog CSV kamu memang
  cocok dgn sumber, bukan sumber utama (backlog CSV tetap yang dipakai utk
  isi form).

Output tersimpan di `export/nama_file.converted.json`, ringkasannya juga
tercetak di terminal.

### Langkah 4 — Verifikasi & catatan yang masih perlu dicek manual

- `izin_edar_bpom` selalu kosong di semua sample sejauh ini — kemungkinan
  field kondisional per kategori KBLI (belum ketemu di kategori manapun
  yang sudah dites). Kalau muncul di sample lain, kabari saya biar
  ditambahkan mapping-nya di `convert_manual_export.py`.
- Field finansial di `financial_crosscheck_vs_backlog_csv` HARUS dicocokkan
  ke kolom backlog CSV baris yang sama — kalau beda, backlog CSV yang jadi
  acuan, tapi selisihnya perlu ditelusuri kenapa.

## Metode B (FALLBACK) — Console DOM-scrape

Pakai `console_export_source.js` **hanya kalau** Metode A tidak bisa
dipakai (mis. request `get-by-assignment-id` tidak ketemu di Network tab,
atau endpoint-nya berubah). Cara pakai & keterbatasannya (heuristik
label→value, banyak field bisa `tidak_ketemu`) ada di komentar di dalam
file itu sendiri.

## Kalau mau sample tambahan

Link assignment lain ada di kolom A backlog Excel/CSV — ulangi Langkah 1-4
di atas satu per satu. **Jangan** dibuatkan otomatisasi loop/bulk utk ini —
itu balik lagi ke risiko deteksi bot yang sama seperti `scrape_source.py`
sekarang. Kalau butuh proses banyak assignment tanpa browsing manual
satu-satu, itu di luar cakupan perbaikan di repo ini.

## Kalau nanti scraping otomatis (Playwright) sudah bisa dipakai lagi

Struktur `dataKey` yang sudah dipetakan di `convert_manual_export.py` bisa
jadi referensi utk memperbaiki `scrape_source.py` — tapi Playwright
scraping DOM tetap tidak bisa langsung baca endpoint API ini tanpa
otentikasi/konteks browser yang sama; treat sebagai referensi nilai yang
benar utk validasi, bukan auto-porting logic-nya mentah-mentah.
