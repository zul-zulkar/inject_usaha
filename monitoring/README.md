# monitoring — rekap hasil input usaha per daerah

Satu perintah → **Excel + dasbor HTML** berisi status SEMUA usaha di sheet input (approved, terkirim,
draft, belum diinput, ditolak pemeriksaan data, ...), **dokumen ganda**, dan rekap **per kecamatan,
desa, SLS, PPL & batch**. Offline & read-only: aman dijalankan kapan saja, termasuk saat bot input
atau approve sedang berjalan.

## Pakai

```bash
python monitoring/monitoring.py
```

Hasil di `monitoring/hasil/`:

| Berkas | Isi |
| --- | --- |
| `monitoring.xlsx` | Ringkasan per batch, Per kecamatan, Per desa, Per SLS, Per PPL, Ganda, Di luar sheet, Detail (satu baris per usaha) |
| `monitoring.html` | Dasbor satu berkas: angka ringkas, grafik progres per kecamatan → klik turun ke desa → SLS, filter batch/kategori, pencarian, tabel yang bisa diurutkan. Buka dengan klik dua kali |

Keduanya memuat nama usaha & email petugas — **jangan diunggah ke tempat publik**; bagikan seperlunya.

Opsi: `--sumber SHEET` (berulang; bawaan semua `bahan/input_tahap2*.xlsx`), `--audit` (bawaan semua
`audit/**/audit_log_gabungan*.csv`), `--snapshot CSV`, `--tanpa-snapshot`, `--peta GEOJSON`,
`--keluaran FOLDER`, `--tanpa-html`.

## Status server yang akurat: snapshot fasih-sm (disarankan)

Tanpa snapshot, status diambil dari catatan skrip (audit input + audit approve) — bisa ketinggalan
(approve manual, dokumen yang dihapus admin, dokumen buatan PC lain yang auditnya belum digabung).
Dengan snapshot, status **server** yang dipakai.

1. Chrome biasa, VPN, login **fasih-sm akun admin**, buka halaman **Data** survei
   (`…/app/surveys/<survei>/<periode>/data`) → F12 → Console.
2. Tempel seluruh isi [`monitoring_console.js`](monitoring_console.js) → Enter, lalu:
   ```js
   await monitoring.jalankan()   // baca-saja: semua dokumen mode PAPI (±2 dtk per 150 dokumen)
   monitoring.unduh()            // snapshot_fasih_sm_<waktu>.csv
   ```
3. Pindahkan CSV ke `bahan/` (atau biarkan di folder Downloads) lalu jalankan `monitoring.py` —
   snapshot **terbaru** di `bahan/` atau Downloads dipakai otomatis (umurnya dicetak).

Skrip Console hanya membaca daftar (endpoint yang sama dengan tabel Data), dipecah per tanggal
dibuat karena server tidak memberi lebih dari ±1.000 baris per saringan; 429/5xx ditunggu lalu diulang.
`monitoring.berhenti()` menghentikan; hasil sebagian tetap bisa diunduh dan ditandai tidak lengkap.

## Kategori per usaha

Satu baris sheet = satu usaha. Kategori diambil dari dokumen "utama" usaha itu (status paling maju):

| Kategori | Arti |
| --- | --- |
| Approved | server APPROVED (atau audit approve `APPROVED_TERVERIFIKASI` kalau tanpa snapshot) |
| Terkirim (belum approve) | SUBMITTED / audit terkirim |
| Ditolak PML (rejected) | REJECTED di server |
| Draft | dokumen ada, belum terkirim (keterangan: tanpa koordinat, galat server) |
| Status server lain | status server di luar daftar di atas |
| Dokumen tanpa URL (perlu cek) | audit mencatat dokumen mungkin terbuat tanpa URL — jalankan `input_usaha/sinkron_list.py` |
| Dokumen tidak ada di server | ada di audit/sheet tapi tidak ada di snapshot LENGKAP (dihapus / beda mode) |
| Belum diinput | lolos pemeriksaan data, belum punya dokumen |
| Ditolak pemeriksaan data | ditolak pemeriksaan yang sama dengan `jalankan.py --cek` (lihat kolom `pesan_data`) |

**% terkirim / % approved** dihitung dari usaha yang lolos pemeriksaan data.
**Daerah** = lokasi usaha di sheet (kolom `5` idsubsls), bukan subsls wadah tempat dokumen dibuat;
kolom *Dok. masih di wadah* menghitung dokumen yang belum dipindah ke wilayahnya
([`fasih_sm/pindah_wilayah`](../fasih_sm/pindah_wilayah/)). Nama kecamatan/desa/SLS dari peta SLS
(`PETA_SLS_PATH` di `inti/config_lokal.py`), cadangan kolom `3`/`4` sheet.

## Ganda

| Jenis | Arti & tindakan |
| --- | --- |
| `USAHA_DOKUMEN_GANDA` | satu baris usaha punya ≥ 2 dokumen hidup — pasti ganda → [`fasih_sm/hapus_ganda`](../fasih_sm/hapus_ganda/) |
| `DOKUMEN_DIPAKAI_BANYAK_BARIS` | satu dokumen tercatat utk ≥ 2 baris (baris identik) — cek sheet |
| `NAMA_SAMA_SATU_BATCH` | dokumen bernama sama dari baris berbeda di batch yang sama — periksa |
| `NAMA_SAMA_BEDA_BATCH` | nama sama dari batch berbeda — bawaan dipertahankan, hanya informasi |
| `NAMA_SAMA_LUAR_SHEET` | (dengan snapshot) dokumen server bernama sama yang tidak dikenal sheet mana pun |

Dengan snapshot, dokumen server yang **tidak tercatat di audit** tapi bernamanya sama persis dengan
satu baris sheet ikut dihitung sebagai dokumen baris itu (ganda di luar audit). Dokumen yang sudah
dihapus admin (tidak ada di snapshot lengkap, `DOKUMEN_DIHAPUS` di audit, atau `audit/ganda_dihapus*.csv`)
tidak dihitung ganda lagi.

## Kode yang berpengaruh

| Berkas | Peran |
| --- | --- |
| `monitoring/monitoring.py` | pembaca sheet/audit/snapshot, `bangun()` (kategori & ganda), `rekap()`, Excel & HTML |
| `monitoring/dasbor.html` | templat dasbor (data disuntik saat dibangkitkan) |
| `monitoring/monitoring_console.js` | snapshot fasih-sm (Console, read-only) |
| `input_usaha/mesin.py` | `muat_sumber` (pemeriksaan data), status audit (`STATUS_TERKIRIM`, ...) |
| `tests/test_monitoring.py`, `tests/test_monitoring_console.js` | uji offline |
