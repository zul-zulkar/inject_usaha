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
| 13c tempat usaha | `4. Toko, ruko, dan sejenisnya`; usaha makan-minum (KBLI golongan 56) `5. Kedai, stan, tenda` |
| 16c teknologi digital | `2. Tidak` (hanya dirender kalau 16a = Ya) |
| 17a produksi ramah lingkungan | `3. Tidak sama sekali` |
| 18 produk seni | `2. Tidak` |
| 23a/23b/23c non-penduduk | `2. Tidak` |
| 29 kepemilikan modal | pribadi 100% |
| Blok/Nomor Rumah | `-` |
| Nama pemberi informasi | `Lainnya` |

Default 13c dibedakan untuk usaha makan-minum karena form menolak kode 1–4 di situ
("Usaha Makan Minum, maka lokasi hanya bisa diisi kode 5-11"): default lama membuat
8 dokumen KBLI golongan 56 terbuat lalu nyangkut DRAFT ber-GALAT pada 22–23 Sep 2026.

Kalau ringkasan pra-kirim masih menyisakan GALAT yang tidak dikenali, skrip **mencoba**
mengganti 13c jadi `5. Kedai, stan, tenda` (`GALAT_13C_JADI` di `inti/config.py`) lalu
membaca ulang ringkasannya. Galatnya berkurang → dipertahankan; tidak berkurang → 13c
dikembalikan ke jawaban semula, jadi baris yang galatnya bukan soal 13c tidak ikut berubah.
Keduanya dicatat di `review_disarankan`. Galat lain tetap tidak pernah ditebak.

### Koreksi tambahan (ketetapan user 2026-09-24)

Semuanya dicatat sebagai ASUMSI di `review_disarankan`, dan masing-masing punya
saklar di `inti/config.py` kalau perlu dimatikan:

| Temuan | Perlakuan | Saklar |
|---|---|---|
| Kolom `16b1-b6` hanya berisi `1`/`YA` | Ya **hanya** untuk 16b1 menerima pesanan, 16b4 membeli bahan baku, 16b5 promosi — sisanya Tidak (sebelumnya keenamnya Ya) | `TAHAP2_16B_YA_TUNGGAL` |
| 16b1 = Ya tapi 27d kosong/0 | 27d diisi 10% | `TAHAP2_PENDAPATAN_ONLINE_JIKA_PESANAN` |
| 12a kosong atau `-` | Nama di dalam kurung pada nama usaha; kalau tidak ada, `PEMILIK <nama usaha>` | `TAHAP2_PENGUSAHA_KOSONG_AWALAN` |
| Nama dokumen masih kembar persis sesudah pembeda 13f | Dibedakan nama **desa**, lalu **kecamatan**, lalu **penomoran** | `TAHAP2_PEMBEDA_WILAYAH_UTK_KEMBAR` |
| Judul KBLI tidak berbagi satu kata pun dengan 13a/13f | **Tanda review saja**, baris tetap diproses | `TAHAP2_TANDAI_KBLI_TIDAK_NYAMBUNG` |

Dua pengaman yang sengaja dipasang pada dua baris terakhir:

- **Baris yang isinya SAMA PERSIS tidak pernah dinomori.** Penomoran hanya untuk
  baris yang isian kirimnya berbeda (mis. angka uangnya) — itu artinya dua usaha
  berbeda. Kalau dua baris identik seluruhnya, itu duplikat entri, dan menomorinya
  berarti mengirim dua dokumen sensus untuk satu usaha yang sama. Baris seperti itu
  tetap di-skip `BARIS_GANDA` seperti semula.
- **KBLI yang tidak nyambung hanya ditandai, tidak di-skip.** Form MENERIMA KBLI
  yang keliru secara makna, jadi ini tidak pernah muncul sebagai GALAT — ketahuannya
  hanya dari isian sheet sendiri, dan pencocokan kata itu kasar. Keputusan mengganti
  KBLI tetap di tangan pemeriksa; di form bisa lewat tombol generate KBLI lalu opsi 1.

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
| `16b1-b6` berisi daftar `1,2,1,1,1,1`, kode `B1,B3`, atau kata `PROMOSI`, `KOMUNIKASI` (→ b6 Lainnya) | diurai per rincian; daftar **5 nilai** = b1–b5, b6 Lainnya = Tidak (`TAHAP2_16B_LIMA_NILAI_B6`); jumlah nilai lain → `SKIP_DATA_16B_TIDAK_JELAS` (tidak ditebak) | ya (5 nilai) |
| Beberapa baris dgn akun + idsubsls + 8b + 12a SAMA tapi 13f beda (satu warung, beberapa produk = usaha pecahan) | nama dokumen & 8b jadi `<8b> <13f> (<12a>)`, mis. `WARUNG SEMBAKO (I KETUT CONTOH)`; > 50 karakter → `<13f> (<12a>)`. 13f juga sama → tetap `SKIP_DATA_BARIS_GANDA` (`TAHAP2_PEMBEDA_13F_UTK_GANDA`) | ya |
| Kolom total beda dengan jumlah rincian | rincian yang dikirim (form menghitung total sendiri) | `TAHAP2_TOTAL_BEDA` |
| Mulai beroperasi 2026 | 30–33 diisi dari kolom 26–29, 31e hanya **AGUSTUS**; minimal total 10.000 | `TAHAP2_ISI_VARIAN_BULANAN`, `TAHAP2_BULAN_OPERASI` |
| KBLI industri (13b1 Ya) tanpa kolom 13d/13e | 13d & 13e diisi judul KBLI | `TAHAP2_13DE_DARI_KBLI` |
| KBLI kategori B–F / golongan 56 dengan 26c > 0 | 26c dijumlahkan ke 26b | `TAHAP2_26C_KE_26B` |
| 24 laki+perempuan ≠ dibayar+tidak dibayar, atau 1 pekerja beda jenis kelamin dengan pemilik | seluruh pekerja = jenis kelamin pemilik, jumlahnya = dibayar + tidak dibayar | `TAHAP2_PEKERJA_IKUT_JK_PEMILIK` |
| NIK bukan 16 digit (mis. 15 digit, `5,11E+15`) | diganti `9999` ("lainnya", sesuai pesan form) | `TAHAP2_NIK_TIDAK_VALID_JADI` |
| Koordinat rusak (`-8.148.438` / `1.145.951`) | diperlakukan belum ada → DRAFT | `--koordinat wajib` |
| 12c umur / 25 tahun operasi kosong | disalin dari usaha lain **pemilik yang sama** (akun + idsubsls + 12a) kalau isiannya sepakat; sisanya nilai pengganti umur `45` / tahun `2019` | `TAHAP2_UMUR_KOSONG_JADI`, `TAHAP2_TAHUN_OPERASI_KOSONG_JADI` |
| Satu kolom 24 kosong (mis. `24.Tidak dibayar`) tapi kolom `24.Total`-nya terisi | diisi selisihnya (total − rincian lain) | — |
| 27a & 27b kosong/nol (27c = 0) | 27a diisi minimal form 100.000 (bulanan 10.000) | `TAHAP2_PENJUALAN_NOL_JADI_MINIMAL` |
| Semua pengeluaran 26a–26e kosong/nol (26f = 0) | 26d diisi minimal form 100.000 (bulanan 10.000) | `TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL` |
| Usaha dagang yang mulai tahun ini (form bulanan) dengan 30c = 0 — form mewajibkan > 0 | 26b dipindah ke 26c; 26b juga 0 → pos terbesar dari 26d/26e. Total tetap | `TAHAP2_30C_NOL_AMBIL_DARI_POS_LAIN` |
| KBLI kategori B–F / golongan 56 dengan 26b = 0 — form mewajibkan > 0 | 26d dipindah ke 26b (26d 0 → 26e). Total tetap | `TAHAP2_26B_NOL_AMBIL_DARI_26D` |
| Keempat kolom 24 kosong | 1 pekerja berjenis kelamin pemilik (pemilik ikut dihitung di rincian 24); dibayar kalau 26a > 0, selain itu tidak dibayar | `TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL` |
| 27d kosong padahal 16a Ya | 0 | `TAHAP2_UANG_KOSONG_JADI_NOL` |
| KBLI kategori P/U (golongan 85/98/99) — ditolak 13g | 13g diklik **DAPATKAN REKOMENDASI KBLI** lalu rekomendasi GenAI **pertama** dipilih (kategori P/U dilewati); 13b1–b3 disesuaikan dengan golongan KBLI terpilih, 26c yang tidak dirender dijumlahkan ke 26b | `KBLI_DITOLAK_PAKAI_GENAI` |

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
  sesi SSO dan memicu `DOKUMEN_TANPA_URL_PERLU_CEK` palsu. Kunci
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

## Menyamakan audit dengan tabel server sebelum mengisi

Audit adalah ingatan skrip: dari situ ia tahu baris mana yang dokumennya sudah
ada. Kalau dokumen dibuat dari PC lain yang auditnya belum digabung, skrip tidak
tahu dan akan membuat dokumen **kedua**.

`--sinkron-dulu` menutup celah itu: setelah login, daftar dokumen dibaca dari
tabel server (API yang sama dengan halaman PENDATAAN, read-only), lalu audit
diperbarui sebelum baris pertama dikerjakan.

```bash
python input_tahap2/main_tahap2.py --sumber input_tahap2.xlsx --akun-tunggal AKUN --subsls-tunggal SUBSLS --dari 2 --sampai 500 --sinkron-dulu --lewati-selesai --submit
```

Yang dicatat sama persis dengan `sinkron_list.py --tulis`, karena memakai fungsi
perencana yang sama: dokumen server yang belum tercatat jadi `DOKUMEN_DIBUAT`
beserta URL-nya, yang sudah terkirim jadi `TERKIRIM_TERVERIFIKASI`, dan yang
audit bilang terkirim padahal server draft jadi `DRAFT_DI_SERVER`.

Draft yang **ditandai galat oleh server** (`sumError > 0`, yaitu angka di kartu
"Jumlah Error") ikut dicatat dengan status `DRAFT_GALAT_DI_SERVER`. Tandanya
ditulis paling belakang, jadi `--lewati-selesai` tidak melewatinya lagi —
termasuk draft tanpa koordinat, yang tanpa tanda ini dianggap tuntas sementara
dan galatnya tidak pernah dibereskan. Dokumen yang sudah terkirim tidak ditandai,
karena PPL tidak bisa mengeditnya.

Kalau daftar server tidak terbaca, sinkron dilewati dan batch tetap jalan —
bedanya perlindungan terhadap duplikat kembali bergantung pada audit yang ada.

## Hanya membereskan yang bergalat di server

```bash
python input_tahap2/main_tahap2.py --sumber input_tahap2.xlsx --akun-tunggal AKUN --subsls-tunggal SUBSLS --sinkron-dulu --hanya-galat --submit --izinkan-wilayah-beda
```

`--hanya-galat` menyisakan **hanya** baris yang dokumennya ditandai galat oleh
server. `--sinkron-dulu` wajib disertakan pada run pertama, karena tandanya
berasal dari tabel server; tanpa itu audit belum punya tanda apa pun dan batch
akan berkata tidak ada yang perlu dikerjakan.

Urutannya di dalam satu run: kunci proses diambil → login sebentar → tabel server
dibaca & audit diperbarui → baris disaring dan diurutkan → batch jalan. Karena
sinkron dilakukan **sebelum** penyaringan, tanda galat yang baru ditemukan
langsung berlaku di run yang sama.

## Isian rincian 13 yang terlalu pendek

Form menolak isian yang terlalu pendek. Skrip melengkapinya dari **judul KBLI**:

| Isian | Batas form | Perlakuan |
| --- | --- | --- |
| 13a kegiatan utama | minimal 15 | dilengkapi saat pengisian, mis. "MENJUAL TELOR" → "MENJUAL TELOR (PERDAGANGAN)" |
| 13f produk utama | minimal 4 | dilengkapi saat pemeriksaan, mis. "GAS" → "GAS (PERDAGANGAN)" |
| 13e proses produksi | 15–100 | judul KBLI; kalau judulnya pendek, didahului 13a |
| 13d input produksi | minimal 4 | judul KBLI |

Kalau baris tidak punya kode KBLI, judulnya tidak ada dan isian itu tidak bisa
dilengkapi — barisnya berhenti (`13A_KURANG_15_KARAKTER` / `13F_KURANG_4_KARAKTER`)
dan harus dibetulkan di Excel. Mode murni tidak pernah melengkapi apa pun.

## Urutan kerja batch

Batch tidak lagi berjalan murni urut nomor baris. Urutannya:

1. **dokumen yang ditandai galat oleh server** (`DRAFT_GALAT_DI_SERVER`) — paling mendesak;
2. **dokumen yang sudah ada tapi belum tuntas** — tinggal dilengkapi lalu dikirim;
3. **baris yang belum punya dokumen** — input baru, paling belakang.

Dalam tiap golongan, urutannya tetap nomor baris. Saat mulai, batch mencetak
pembagiannya, misalnya:

```
Urutan kerja: 14 bertanda galat server, 330 dokumen belum tuntas, lalu 155 input baru.
```

Gunanya: kalau batch berhenti di tengah (server bermasalah, waktu habis), yang
sudah dikerjakan adalah dokumen yang paling perlu dibereskan, bukan dokumen baru
yang justru menambah draft. `--urut-sheet` mengembalikan urutan murni nomor baris.

## Dokumen tersebar di beberapa subsls wadah

Kalau beberapa subsls dipakai bergantian sebagai **wadah** dokumen (dikembalikan
ke wilayah aslinya belakangan lewat `pindah_wilayah/`), dokumen yang dibuka
kembali bisa berada di subsls yang bukan `--subsls-tunggal` run itu. Bawaannya
skrip berhenti (`STOP_WILAYAH_DOKUMEN_BEDA`) karena mengisi dokumen di wilayah
yang salah adalah kesalahan serius.

Tambahkan `--izinkan-wilayah-beda` supaya dokumen seperti itu tetap diisi dan
dikirim:

```bash
python input_tahap2/main_tahap2.py --sumber input_tahap2.xlsx --akun-tunggal AKUN --subsls-tunggal SUBSLS --izinkan-wilayah-beda --lewati-selesai --submit
```

Yang berubah dengan flag itu:

- dokumen yang **sudah ada** dan wilayahnya masih di kabupaten sendiri diteruskan,
  dengan catatan review;
- subsls yang dicatat di audit = **wilayah dokumen yang sebenarnya**, bukan subsls
  yang diketik di perintah;
- pencocokan dokumen lama cukup lewat **akun**, tidak lagi akun+subsls — tanpa ini
  baris yang dokumennya ada di subsls wadah lain akan dilewati selamanya.

Yang **tidak** berubah: dokumen yang baru saja dibuat tetap menghentikan batch
kalau wilayahnya meleset (itu berarti subsls salah dipilih di modal, bukan sekadar
wadah lain), begitu juga dokumen di luar kabupaten sendiri.

## 10. Mengembalikan dokumen ke subsls masing-masing

Semua dokumen dibuat di satu subsls (`--subsls-tunggal`). Setelah terkirim & di-approve PML
(`docs/PANDUAN_APPROVE_PML.md`),
pindahkan ke subsls aslinya (kolom `5`) lewat fasih-sm — langkah lengkap di
`docs/PANDUAN_PINDAH_WILAYAH.md` bagian "Format tahap 2":

```bash
python pindah_wilayah/pindah_wilayah.py --format tahap2 --sumber bahan/input_tahap2.xlsx --dari-approve --daftar-tujuan tujuan_tahap2.txt --console
```

## 11. Uji offline

```bash
python tests/test_tahap2_loader.py
python tests/jalankan_semua.py
```
