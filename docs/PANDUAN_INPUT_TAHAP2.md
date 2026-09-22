# Panduan input otomatis — hasil pendataan KERTAS SE2026 TAHAP 2

Alur ini untuk menginput hasil pendataan **kertas** Sensus Ekonomi 2026 tahap 2
(`bahan/input_tahap2.xlsx`) ke fasih-web. Jalur pengisian & pengirimannya
**sama persis** dengan alur input otomatis format standar — yang berbeda hanya
bentuk file sumbernya.

| | Format standar | Format tahap 2 |
|---|---|---|
| File | `input_usaha.xlsx`, tab `input_usaha` | `input_tahap2.xlsx`, tab pertama |
| Jumlah kolom | 92 | 48 |
| Entry point | `input_gabungan/main_gabungan.py` | `input_tahap2/main_tahap2.py` |
| Pemetaan kolom | `inti/gabungan_loader.py` | `inti/tahap2_loader.py` |
| Pengisian form | `input_gabungan/fill_gabungan.py` | sama (dipakai ulang) |
| Audit | `audit_log_gabungan.csv` | sama |

Semua flag `main_gabungan.py` tetap berlaku — `input_tahap2/main_tahap2.py`
hanyalah `main_gabungan.py --format tahap2`.

---

## 1. Kuesioner kertas lebih pendek dari form

Kuesioner tahap 2 hanya menanyakan sebagian rincian SE2026-L BLOK II, padahal
fasih-web tetap mewajibkan sisanya. Rincian yang tidak ditanyakan diisi dari
`TAHAP2_DEFAULT` di `inti/config.py` — **ketetapan pengguna, bukan tebakan
skrip** — dan setiap pemakaiannya dicatat sebagai ASUMSI di kolom
`review_disarankan` audit:

| Rincian | Default |
|---|---|
| 8d jenis kawasan | `10. Di luar kawasan` |
| 10a NIB / 10c alasan | `2. Tidak` / `3. Tidak memerlukan NIB` |
| 11a badan usaha | `13. Bukan Badan Usaha` |
| 11d catatan keuangan | `2. Tidak` |
| 13c tempat usaha | `4. Toko, ruko, dan sejenisnya` |
| 16c teknologi digital | `2. Tidak` (hanya dirender kalau 16a = Ya) |
| 17a produksi ramah lingkungan | `3. Tidak sama sekali` |
| 18 produk seni | `2. Tidak` |
| 23a/23b/23c non-penduduk | `2. Tidak` |
| 29 kepemilikan modal | pribadi 100% |
| Blok/Nomor Rumah | `-` |
| Nama pemberi informasi | `Lainnya` |

**Kalau satu baris perlu jawaban lain, tambahkan kolomnya di Excel** —
nilai kolom sheet SELALU menang atas default. Judul kolom yang dikenali ada
di `KOLOM_TAHAP2_TAMBAHAN` (`inti/tahap2_loader.py`): `8d.`, `10a`, `10b`,
`10c`, `11a`, `11d`, `13b1`, `13b2`, `13b3`, `13b4`, `13c`, `13d`, `13e`,
`16c`, `17a`, `18`, `19a`, `19b`, `19c`, `20a`, `20b`, `20c`, `23a`, `23b`,
`23c`, `29a`–`29f`, `kodepos`, `Blok/Nomor`, `Akun PPL`.

Untuk mengubah default secara permanen (berlaku semua baris), timpa
`TAHAP2_DEFAULT` di `inti/config_lokal.py`.

## 2. Rincian 13b1/13b2/13b3 diturunkan dari KBLI

Ketiganya wajib di form tapi tidak ada di kuesioner kertas. Ketetapan pengguna
2026-09-22: diturunkan dari **golongan KBLI** (2 digit pertama):

| Golongan KBLI | Hasil |
|---|---|
| 45–47 (perdagangan besar/eceran & reparasi) | 13b3 “menjual barang” = **1. Ya** |
| 56 (penyediaan makan minum) | 13b2 “layanan makan minum” = **1. Ya** |
| 10–33 (industri pengolahan) | 13b1 “memproduksi barang” = **1. Ya** |
| lainnya | ketiganya **2. Tidak** → form merender 13b4, diisi dari kategori 13h |

⚠️ 13b1 = Ya membuat form ikut mewajibkan **13d & 13e** (input & proses
produksi) yang tidak ada di kuesioner kertas. Baris itu **di-skip sebelum
dokumen dibuat** (`SKIP_DATA_13DE_TIDAK_ADA_DI_TAHAP2`) — tambahkan kolom
`13d` & `13e` di sheet, atau isi dokumennya manual. Tidak pernah ditebak.

## 3. Kolom TOTAL dipakai sebagai pemeriksa

Form menghitung sendiri total 24, 26f, 27c dan 28c, jadi kolom total di sheet
**tidak dikirim** — tapi dibandingkan dengan jumlah rinciannya. Selisih berarti
ada angka salah ketik, dan itu harus ketahuan sebelum dokumen dibuat:

| Kolom sheet | Dibandingkan dengan |
|---|---|
| `24.Total` (kemunculan ke-1) | `24.L` + `24.P` |
| `24.Total` (kemunculan ke-2) | `24.Dibayar` + `24.Tidak dibayar` |
| `Rp26` | `26a`+`26b`+`26c`+`26d`+`26e` |
| `27c` | `27a` + `27b` |
| `28c` | `28a` + `28b` |

Tidak cocok → `SKIP_DATA_TOTAL_TIDAK_COCOK`. Kolom total yang **kosong** tidak
diperiksa. Kolom total yang berisi **0 padahal rinciannya terisi** (mis. `Rp26`
= `Rp0` sementara 26c = `Rp10.500.000`) dianggap *tidak diisi*, bukan selisih:
barisnya tetap SIAP dan dicatat di kolom `tanda` / `review_disarankan`. Kalau kolom total di Excel memang belum diisi dengan benar,
gunakan `--abaikan-cek-total` (angka yang dikirim tidak berubah — totalnya
dihitung form).

Kolom `28c1` belum diketahui artinya: **tidak dikirim & tidak diperiksa**.

## 4. Pengubahan nilai otomatis

| Kolom | Contoh sheet | Dikirim sebagai |
|---|---|---|
| 26a–28b | `Rp10.500.000` | `10500000` |
| Latitude/Longitude | `-8,2004731` | `-8.2004731` |
| 27d | `0,00` | `0` (pembulatan half-up; kalau nilainya berubah, ditandai) |
| 12b, 14a, 16a, 17b, 21, 22 | kode `1`/`2`/`5` | teks opsi form (`1. Laki-laki`, …) |
| `no WA` | `81340828334` | `081340828334` (nol yang dibuang Excel dikembalikan) |
| `16b1-b6` | satu kode | berlaku untuk **keenam** rincian 16b1–16b6 |

Kode opsi yang tidak dikenal atau ambigu **dikosongkan**, sehingga barisnya
di-skip — tidak pernah ditebak.

### 13a terlalu pendek → dilengkapi judul KBLI

Form menolak 13a (kegiatan utama) yang kurang dari **15 karakter**. 13a seperti
itu dilengkapi dengan kata dari **judul KBLI**: kolom `Judul KBLI` di sheet,
atau judul opsi Master KBLI yang terpilih di form kalau kolom itu kosong.
13a yang sudah 15 karakter atau lebih tidak diubah.

| 13a di sheet | Judul KBLI | Dikirim sebagai |
|---|---|---|
| `MENJUAL ROKOK` | PERDAGANGAN ECERAN ROKOK … | `MENJUAL ROKOK (PERDAGANGAN)` |
| `Menjual Beras` | PERDAGANGAN ECERAN BERAS | `Menjual Beras (Perdagangan)` |
| `MENJUAL GAS LPG` | — | tidak diubah (sudah 15 karakter) |

Bawaannya kata ditambahkan **seperlunya** sampai 15 karakter. Untuk memakai
judul KBLI utuh (`MENJUAL ROKOK (PERDAGANGAN ECERAN ROKOK …)`), set
`LENGKAPI_13A_DGN_KBLI = "penuh"` di `inti/config_lokal.py`; `""` mematikannya
(baris seperti itu lalu di-skip `13A_KURANG_15_KARAKTER`). Hasil pelengkapan
terlihat di kolom `tanda` `cek_gabungan.csv`.

## 5. Kodepos

Template tahap 2 tidak punya kolom kodepos. Urutan sumbernya:

1. kolom `kodepos` di sheet (kalau ditambahkan),
2. `KODEPOS_BY_IDSUBSLS` (cocok persis 16 digit),
3. `KODEPOS_BY_DESA` (10 digit pertama — kodepos memang dialokasikan per desa),
4. nilai tunggal `KODEPOS_BY_IDSUBSLS` untuk desa yang sama,
5. `--kodepos` di CLI.

Semuanya kosong → `SKIP_DATA_KODEPOS_TIDAK_DIKETAHUI`. `KODEPOS_BY_DESA` bisa
disusun otomatis dari data yang sudah ada (sheet format standar + export
fasih-sm, suara terbanyak per desa; desa yang bentrok dicetak):

```bash
python input_tahap2/kodepos_desa.py --sumber bahan/input_tahap2.xlsx
python input_tahap2/kodepos_desa.py --sumber bahan/input_tahap2.xlsx --tulis
```

`--tulis` menulis blok bertanda di `inti/config_lokal.py` (tidak ikut git).

### Penyesuaian otomatis lain (ketetapan pengguna 2026-09-22, data asli)

Semuanya bisa dimatikan di `inti/config_lokal.py`, dan setiap pemakaiannya
tercatat di kolom `tanda` / `review_disarankan`.

| Keadaan di sheet | Yang dilakukan | Saklar |
|---|---|---|
| Jawaban berupa teks: `LAKI-LAKI`, `L`, `P`, `YA`, `TIDAK`, `2. PEREMPUAN` | dicocokkan ke opsi form (harus sama persis, setelah membuang nomor/spasi/tanda baca) | — |
| `16b1-b6` berisi daftar `1,2,1,1,1,1`, kode `B1,B3`, atau kata `PROMOSI`, `KOMUNIKASI` (→ b6 Lainnya) | diurai per rincian; daftar yang **bukan 6 nilai** → `SKIP_DATA_16B_TIDAK_JELAS` (tidak ditebak) | — |
| Kolom total beda dengan jumlah rincian | rincian yang dikirim (form menghitung total sendiri) | `TAHAP2_TOTAL_BEDA` |
| Mulai beroperasi 2026 | 30–33 diisi dari kolom 26–29, 31e hanya **AGUSTUS**; minimal total 10.000 | `TAHAP2_ISI_VARIAN_BULANAN`, `TAHAP2_BULAN_OPERASI` |
| KBLI industri (13b1 Ya) tanpa kolom 13d/13e | 13d & 13e diisi judul KBLI | `TAHAP2_13DE_DARI_KBLI` |
| KBLI kategori B–F / golongan 56 dengan 26c > 0 | 26c dijumlahkan ke 26b | `TAHAP2_26C_KE_26B` |
| 24 laki+perempuan ≠ dibayar+tidak dibayar, atau 1 pekerja beda jenis kelamin dengan pemilik | seluruh pekerja = jenis kelamin pemilik, jumlahnya = dibayar + tidak dibayar | `TAHAP2_PEKERJA_IKUT_JK_PEMILIK` |
| NIK bukan 16 digit (mis. 15 digit, `5,11E+15`) | diganti `9999` ("lainnya", sesuai pesan form) | `TAHAP2_NIK_TIDAK_VALID_JADI` |
| Koordinat rusak (`-8.148.438` / `1.145.951`) | diperlakukan belum ada → DRAFT | `--koordinat wajib` |

## 6. Nama dokumen

Sama dengan format standar: `<8b> (<12a>)`, mis.
`USAHA JUAL BERAS (ULLUMA RAHMA)`. Maksimal 50 karakter (validasi form);
lebih dari itu → dipakai nama usaha saja tanpa kurung, masih lebih → baris
di-skip.

Identitas baris (`kunci` di audit) memakai **akun PPL + idsubsls + nama usaha
+ nama pengusaha**. Berbeda dengan format standar yang tidak memakai nama
pengusaha: nama usaha di kuesioner kertas sering generik (“WARUNG”,
“TOKO KELONTONG”), jadi tanpa 12a dua responden berbeda akan dikira baris
ganda.

## 7. Koordinat belum lengkap → otomatis jadi DRAFT

Satu perintah yang sama menyesuaikan diri per baris (`--koordinat otomatis`,
bawaan format tahap 2):

| Latitude & Longitude di sheet | Yang dilakukan skrip |
|---|---|
| keduanya terisi | diisi lengkap + geotagging, **dikirim** kalau pakai `--submit` |
| salah satu/keduanya kosong, `-`, atau `0` | dibuat & diisi lengkap **kecuali geotagging**, lalu disimpan sebagai **DRAFT** — tidak pernah dikirim, walau pakai `--submit` (status audit `DRAFT_TANPA_KOORDINAT`) |

Form fasih-web **tidak** menolak dokumen PAPI tanpa geotag (geotag hanya wajib
untuk mode CAPI), jadi yang menahan dokumen itu tetap DRAFT adalah skrip ini.
`--cek` menampilkan baris seperti ini sebagai `SIAP_TANPA_KOORDINAT`.

**Melengkapi koordinat nanti:** isi Latitude/Longitude di Excel, lalu jalankan
ulang perintah yang sama dengan `--lewati-selesai`. Skrip membuka **dokumen
DRAFT yang sama** lewat URL di audit (tidak membuat dokumen baru), mengisi
geotagging, memeriksa ringkasan, lalu mengirim. Baris yang koordinatnya masih
kosong dilewati (draftnya sudah ada), baris yang sudah terkirim juga dilewati.

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL_PPL --subsls-tunggal IDSUBSLS16 --lewati-selesai --submit
```

Kalau draft tanpa koordinat ternyata masih punya GALAT lain, statusnya tetap
`DRAFT_TANPA_KOORDINAT` tetapi kolom `galat` > 0 dan rinciannya ada di
`error_message` — perbaiki datanya dulu sebelum koordinat dilengkapi.
Perilaku lama (baris tanpa koordinat di-skip, tidak dibuatkan dokumen):
tambahkan `--koordinat wajib`. Format standar (`input_usaha.xlsx`) tetap
`wajib` kecuali diberi `--koordinat otomatis`.

⚠️ Audit tiap PC terpisah. Kalau draft dibuat di PC A, lengkapi koordinatnya
juga di PC A (atau salin `audit_log_gabungan.csv` ke PC B dulu) — tanpa catatan
URL di audit, PC B tidak tahu draft itu ada.

## 8. Langkah pemakaian

### a. Periksa data (tanpa browser/VPN, beberapa detik)

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --cek
```

Rincian per baris ditulis ke `cek_gabungan.csv` — buka di Excel, filter kolom
`status`, perbaiki sheet, ulangi sampai semua `SIAP`.

### b. Dry-run SATU baris (tidak mengirim apa pun)

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL_PPL --subsls-tunggal IDSUBSLS16 --baris 2
```

Tinjau dokumennya di fasih-web. Status yang diharapkan: `DRY_RUN_SIAP_KIRIM`
dengan GALAT = 0.

### c. Kirim (IRREVERSIBLE — wajib ketik `YA`)

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL_PPL --subsls-tunggal IDSUBSLS16 --baris 2 --submit
```

Perbesar bertahap: 1 baris → beberapa baris → `--lewati-selesai --limit N`.

## 9. Membagi pekerjaan: rentang baris, beberapa PC, paralel

Rentang baris ditentukan dengan `--dari N --sampai M` (nomor baris sheet,
judul = baris 1, kedua ujung ikut diproses) atau `--baris 2,5,10-20`. Salah
satu ujung boleh dihilangkan: `--dari 201` = baris 201 sampai akhir.
Pembagian tinggal memberi rentang yang **tidak tumpang tindih**:

```bash
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal A --subsls-tunggal X --dari 2 --sampai 200 --submit
python input_tahap2/main_tahap2.py --sumber bahan/input_tahap2.xlsx --akun-tunggal B --subsls-tunggal Y --dari 201 --paralel --submit
```

Cek dulu isi rentangnya tanpa browser: tambahkan `--cek` ke perintah yang sama.

Aturan yang tidak boleh dilanggar:

- **Satu akun = satu proses.** Dua proses dengan akun yang sama saling memutus
  sesi SSO dan memicu `STOP_DOKUMEN_TANPA_URL` palsu. Kunci
  `.proses_<akun>.lock` menolak proses kedua, termasuk dengan `--paralel`.
- **Paralel di satu PC = akun DAN subsls berbeda per proses**, plus flag
  `--paralel` (mematikan pengulangan “buat dokumen” yang tidak bisa dibuktikan
  aman saat list bertambah dari proses lain).
- **Kunci proses tidak berlaku lintas PC.** Dua komputer dengan akun yang sama
  tidak saling tahu isi audit masing-masing — ini yang pada 2026-09-15
  menghasilkan ±130 dokumen tak tercatat dan 7 pasang duplikat terkirim. Kalau
  memang harus beda PC, **beri akun berbeda per PC**, dan jalankan
  sinkron list sebelum & sesudah tiap batch (READ-ONLY, tanpa `--tulis` hanya
  melapor):

  ```bash
  python input_gabungan/sinkron_list.py --format tahap2 --sumber bahan/input_tahap2.xlsx --akun-tunggal EMAIL_PPL --subsls-tunggal IDSUBSLS16
  ```
- Audit (`audit_log_gabungan.csv`) juga per PC. Salin file itu ke PC lain kalau
  ingin `--lewati-selesai` melihat pekerjaan yang sudah selesai di sana.

## 10. Uji offline

```bash
python tests/test_tahap2_loader.py
python tests/jalankan_semua.py
```
