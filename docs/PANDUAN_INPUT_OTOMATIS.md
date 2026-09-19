# Panduan Input Otomatis — Usaha Pecahan SE2026

Panduan singkat. Aturan keselamatan ada di `README.md`, aturan pengisian resmi ada di
`catatan usaha pecahan se2026.md`.

---

## Alur harian: 3 langkah

### 1. Pastikan dokumennya sudah ada di fasih-web

Skrip **tidak selalu bisa membuat dokumen sendiri** — kalau wilayah/SLS tujuan
belum punya assignment, pembuatan gagal (terkonfirmasi pada 2514, idsubsls
`…0203`). Cara paling aman: **buat dulu semua dokumennya manual** lewat tombol
"+ Dokumen Baru", pakai nama persis kolom `nama_usaha_pecahan`.

Kalau dokumennya sudah ada, skrip otomatis mendeteksinya dan langsung mengisi
(tidak akan bikin duplikat).

### 2. Jalankan dry-run per record

```bash
python main.py --csv LKpenyalinan.csv --only-no 2514
```

Isi semuanya, berhenti tepat sebelum Kirim. Hasil akhir yang diharapkan:

```
Ringkasan: GALAT=0 PERINGATAN=1 CATATAN=0 KOSONG=20
status: DRY_RUN_SIAP_KIRIM
```

**GALAT harus 0.** PERINGATAN ~1 dan KOSONG 19–21 itu normal (field vestigial &
field milik PML) — polanya sama dengan 3 record yang sudah sukses terkirim.

### 3. Tinjau di browser, lalu kirim sendiri

Buka dokumennya, cek sekilas, baru:

```bash
python main.py --csv LKpenyalinan.csv --only-no 2514 --submit --headed
```

Skrip akan minta ketik `YA` dulu. **Kirim itu irreversible** — konfirmasi wajib
per record, izin di satu record tidak berlaku untuk record lain.

---

## Kalau gagal, baca `audit_log.csv`

| status | artinya | tindakan |
|---|---|---|
| `DRY_RUN_SIAP_KIRIM` | beres, GALAT=0 | tinjau lalu `--submit` |
| `SKIP_DOKUMEN_BELUM_ADA` | wilayah belum punya assignment | buat dokumen manual, ulangi |
| `SKIP_KODEPOS_TIDAK_DIKETAHUI` | idsubsls baru | tambah di `KODEPOS_BY_IDSUBSLS` (`inti/config_lokal.py`) |
| `SKIP_EXPORT_*` | file export belum ada / tidak cocok | lihat `PANDUAN_EKSPOR_MANUAL.md` |
| `SKIP_ALAMAT_KOSONG` | alamat tidak ada di export | lengkapi export dulu |
| `SKIP_GALAT_PERLU_REVIEW` | GALAT>0 & bukan Nomor Urut Bangunan | buka dokumen, perbaiki manual |
| `ERROR_FIELD_NOT_FOUND` | selector meleset | jalankan ulang dgn `--dump-dom`, lihat bawah |

Setiap kegagalan otomatis menyimpan screenshot di `log_screenshots/`.

---

## Kalau ada field baru yang tidak ketemu

```bash
python main.py --csv LKpenyalinan.csv --only-no 2514 --dump-dom
```

Menghasilkan `log_screenshots/*.map.tsv` berisi `dataKey / jenis input / label`
untuk section yang sedang aktif. Ambil dataKey-nya, tambahkan ke
`config.py -> DK`, lalu pakai `fill_by_datakey()` / `select_radio_by_datakey()`.

Ingat: **form hanya merender section yang sedang aktif**, dan banyak field baru
muncul setelah pertanyaan pemicunya dijawab. Jadi satu file dump = satu keadaan.

Sebelum menjalankan ulang ke server, uji dulu tanpa VPN:

```bash
python tests/test_selectors.py
```

---

## Nilai default kalau data export kosong

Ditetapkan pengguna, ada di `config.py` (bukan tebakan skrip):

| Rincian | Nilai |
|---|---|
| 10c alasan tidak punya NIB | `3. Tidak memerlukan NIB` |
| 13c tempat usaha | `4. Toko, ruko, dan sejenisnya` |
| 19a | `3. Tidak/Belum` |
| 19c | `1` |
| 20c jumlah varian belum BPOM | `1` |
| 16b1 menerima pesanan barang/jasa | `2. Tidak` |
| 16b2 produksi barang/jasa | `2. Tidak` |
| 16b3 distribusi barang/jasa | `2. Tidak` |
| 16b4 membeli bahan baku online | `2. Tidak` |
| 16b5 promosi | `1. Ya` |
| 16b6 lainnya | `2. Tidak` |
| 16c teknologi digital (AI/IoT/dll) | `2. Tidak` |
| 27d persentase pendapatan online | `0` |
| 13b4 aktivitas (kalau 13b1/b2/b3 semua Tidak) | kategori A → `2. Pertanian…`, selain itu `1. Jasa` |
| Pilih UMKM dalam satu SLS yang sama | `Tidak Ada` |

Kalau export **punya** nilainya, nilai export yang dipakai. Default hanya
menambal yang kosong.

Rincian **16b1-b6, 16c, dan 27d** hanya muncul kalau 16a (pakai internet)
dijawab `1. Ya`. Sumber fasih-sm sama sekali tidak menyimpan ketiganya,
jadi nilainya selalu dari tabel di atas — ubah di `config.py`
**Minimal satu dari 16b1-16b6 harus `1. Ya`** — form menolak kalau semuanya
`2. Tidak` ("Salah satu dari 16b1 - 16b6 wajib terisi YA"). Skrip berhenti
lebih awal kalau konfigurasinya melanggar itu.
(`DEFAULT_16B_TUJUAN_INTERNET`, `DEFAULT_16C_TEKNOLOGI_DIGITAL`,
`DEFAULT_27D_PERSEN_PENDAPATAN_ONLINE`).

Ketiga field waktu (Waktu Mulai, Waktu Kunjungan I, Waktu Selesai) diisi
otomatis; rincian 19a/19c dicari lewat labelnya, jadi tetap tertangani walau
dataKey-nya belum terdaftar.

---

## Aturan pekerja & upah/gaji

Berlaku otomatis, tidak perlu flag apa pun. Yang menentukan: **total pekerja**
(24a1 + 24b1 dari export).

| Total pekerja | Yang diisi skrip |
|---|---|
| **≤ 3 orang** | 24a2 (dibayar) = `0`, 24b2 (tidak dibayar) = total. **26a upah/gaji = `0`.** Pos pengeluaran lain tidak diubah, jadi total 26f ikut turun. |
| **> 3 orang** | Keempat angka pekerja apa adanya. 26a = 10% sumber, lalu **angka itu dipotong dari pos pengeluaran terbesar** (26b/26c/26d/26e) supaya total 26f tidak membengkak. |

Cek log-nya — setiap keputusan dicetak dgn awalan `24:` dan `26:`, mis.:

```
24: Total pekerja 5 > 3 -> angka pekerja dipakai apa adanya; 26a = 10% sumber lalu dipotong dari pos pengeluaran terbesar.
26: 26a 1000000 dipotong dari pos terbesar: biaya_pembelian -1000000.
26f total pengeluaran (hitungan skrip) = 10680000
```

Dua kondisi yang **wajib kamu tengok manual** kalau muncul di log:

- `⚠️ Total pekerja tidak diketahui dari sumber` — aturan tidak diterapkan,
  26a tetap 10%. Skrip sengaja tidak menebak.
- `⚠️ Pos pengeluaran lain tidak cukup menutupi 26a` — sisanya tidak dipotong
  (tidak dipaksa negatif), jadi total 26f naik sebesar sisa itu.

Batasnya (3 orang) ada di `config.py -> BATAS_TK_SEMUA_TIDAK_DIBAYAR`.
Uji perhitungannya tanpa VPN: `python tests/test_pengeluaran.py`.

---

## Periksa dulu sebelum jalan (2 detik, tanpa VPN)

```bash
python preflight.py --csv LKpenyalinan.csv
```

Menampilkan berapa baris SIAP, mana yang bakal ke-skip beserta alasannya,
berapa sesi login yang akan terjadi, dan perintah `main.py` berikutnya.
Tambahkan `--verbose` untuk melihat pratinjau angka pekerja & pengeluaran
per baris. Kalau ada `SKIP_KODEPOS_TIDAK_DIKETAHUI`, biasanya itu sudah teratasi
sendiri: kodepos diambil otomatis dari file export mentah (`var_desa` +
`kodepos`), jadi idsubsls baru tidak perlu didaftarkan manual lagi. Yang
tersisa hanya kalau desanya memang belum pernah muncul di satu pun export —
preflight akan bilang begitu apa adanya.

---

## Menjalankan banyak record

Satu record makan **±1,7 menit** termasuk ganti akun, jadi 90 baris ≈ 2,5 jam
VPN nonstop. Jangan dijalankan sekaligus — pecah per batch, dan pakai
`--lewati-selesai` supaya batch yang terputus bisa dilanjutkan tanpa
mengulang yang sudah beres:

```bash
python main.py --csv LKpenyalinan.csv --lewati-selesai --limit 10
```

`--lewati-selesai` membaca `audit_log.csv` dan melewati baris yang statusnya
sudah selesai — di dry-run berarti `DRY_RUN_SIAP_KIRIM` atau `TERKIRIM_*`, di
`--submit` hanya `TERKIRIM_*`. Jadi urutan kerja sehari-hari:

1. `python preflight.py --csv LKpenyalinan.csv` — pastikan tidak ada yang bakal ke-skip.
2. `python main.py --csv LKpenyalinan.csv --lewati-selesai --limit 10` — dry-run 10 baris.
3. Buka `audit_log.csv`, pastikan semuanya `DRY_RUN_SIAP_KIRIM` & kolom
   `review_disarankan` kosong.
4. Baru kirim, dengan daftar No yang sudah kamu tinjau:
   `python main.py --csv LKpenyalinan.csv --only-no 2524,2537,2540 --submit`
5. Ulangi dari langkah 2.

Kalau VPN putus di tengah, baris grup itu tercatat `ERROR_LOGIN` dan sisanya
tidak ikut rusak. Jalankan ulang perintah yang sama — pengisian ulang aman
(radio yang nilainya sudah benar tidak diklik ulang, jadi jawaban turunannya
tidak ter-reset).

**Yang wajib ditengok di `audit_log.csv` sebelum kirim:**

| Kolom/nilai | Artinya |
|---|---|
| `ERROR_AKUN_SALAH` | Login masuk ke akun PPL lain — **jangan dikirim**, jalankan ulang. |
| `AKUN TIDAK TERVERIFIKASI` di `review_disarankan` | Pengaman akun tidak bisa membaca identitas; cocokkan manual dgn Nama PPL di sheet. |
| `SKIP_GALAT_PERLU_REVIEW` | Ada field wajib yang belum tertangani — baca kolom `error_message`. |
| `kosong` jauh dari 20-22 | Pola tidak normal, periksa manual. |
| `DINAIKKAN ke minimal 100.000` | Angka 26/27 baris itu **bukan lagi 10% sumber** — form menolak di bawah 100.000. Tinjau sebelum kirim. |
| `pakai DEFAULT (export kosong) — ASUMSI` | Skrip memakai nilai default karena export tidak punya datanya. |
| `SKIP_VARIAN_BULANAN` | Usaha mulai beroperasi tahun berjalan → form pakai rincian 30-33 (angka **bulanan**). Isi manual; jangan pakai angka tahunan. |
| `SKIP_DOKUMEN_BELUM_ADA` | Wilayahnya belum punya assignment. Buat dokumennya manual, lalu jalankan ulang. |

---

## Ganti akun PPL

Skrip sudah mengurusnya sendiri: satu sesi login per (PPL + assignment),
cookie dibersihkan di antaranya, dan **akun yang benar-benar aktif
diverifikasi** sebelum satu baris pun diisi. Kalau ternyata yang login akun
lain, baris itu berhenti dgn status `ERROR_AKUN_SALAH` — bukan diisi diam-diam.

Yang perlu kamu tahu kalau ganti akun **manual di Chrome**: sesi login bukan
milik fasih-web, tapi Keycloak di `sso.bps.go.id`. Logout dari fasih-web saja
akan membuatmu masuk lagi ke akun lama. Yang benar:

1. Logout dari `sso.bps.go.id`, **atau**
2. Hapus cookie situs `sso.bps.go.id`, **atau**
3. Pakai jendela Samaran/Incognito.

---

## Jangan diubah tanpa alasan kuat

1. **Default tanpa `--submit` = dry-run.** Jangan dilonggarkan.
2. **Field "Nomor Urut Bangunan" tidak pernah disentuh.** Sekali ter-klik,
   nilainya jadi `0` permanen dan memicu GALAT. Perbaikan hanya lewat
   `fix_nomor_urut_bangunan_if_needed()`.
3. **Jangan pakai `.count()` untuk memutuskan "tidak ada".** Tidak menunggu
   render — pernah bikin dokumen duplikat dan 3 field wajib terlewat. Pakai
   `komponen_ada()` atau `wait_for()`.
4. **Jangan hidupkan lagi fallback "klik teks pertama di halaman"** di
   `select_radio()`. Hampir semua opsi BLOK II berteks "1. Ya"/"2. Tidak",
   jadi fallback itu menjawab pertanyaan yang salah tanpa jejak.

---

## Sisa pekerjaan

Record 2513 sudah terkirim. Sisa: **2514–2520** (7 record), semuanya sudah punya
kodepos & file export. Yang perlu dipastikan cuma dokumennya sudah ada di
fasih-web untuk masing-masing wilayah.
