# CLAUDE.md

Panduan untuk Claude Code saat bekerja di repo ini.

## Tentang proyek ini

Skrip Playwright/Python untuk mengisi & mengirim dokumen SE2026-P "Usaha Pecahan" ke fasih-web.bps.go.id (Sensus Ekonomi 2026, BPS Buleleng). Sumber data: Google Sheet backlog usaha pecahan (diexport ke CSV) + scraping tambahan dari fasih-sm.bps.go.id (sistem sumber, read-only).

Dibuat SETELAH 3 dokumen diisi & dikirim manual penuh sampai sukses (No urut 2510/2511/2512) — supaya pola form benar-benar dipahami dulu sebelum diotomatisasi. Detail lengkap ketiga record itu (semua nilai field, hasil ringkasan, kronologi temuan) ada di dokumen proyek `catatan-usaha-pecahan-se2026.md` pada Claude Project "Otomatisasi Pekerjaan" di claude.ai — **bukan file lokal**, tapi jadi ground truth utama utk memvalidasi dry-run pertama.

## Struktur folder (2026-09-14 — dipisah per fungsi)

Dulu semua file di root; sekarang dikelompokkan. **Jalankan semua perintah DARI ROOT proyek** (path data seperti `Agenda.xlsx`, `export/`, `audit_log*.csv`, `log_screenshots/` relatif ke cwd = root). Tiap skrip entry sudah menyisipkan root ke `sys.path` (`_sys.path.insert...` di awal file), jadi impor `from inti.x import ...` tetap jalan walau dipanggil `python <folder>/<skrip>.py`.

| Folder | Isi | Dipakai bagaimana |
|---|---|---|
| `inti/` | Modul BERSAMA: `config.py`, `data_loader.py`, `scrape_source.py` (definisi `SourceBlok2`), `fasih_web.py`, `fill_blok2.py`, `gabungan_loader.py`. Punya `__init__.py`. | Diimpor semua alat lain sbg `inti.<modul>`. Jangan buat `inti` mengimpor dari folder alat (arah dependensi 1 arah). |
| `input_fasihweb/` | Alur backlog LAMA (LKpenyalinan): `main.py`, `export_source.py`, `preflight.py`, `convert_manual_export.py`, `repair_idsubsls_from_xlsx.py`, `console_export_source.js`. | `python input_fasihweb/main.py --csv LKpenyalinan.csv ...` |
| `input_gabungan/` | Alur sheet gabungan: `fill_gabungan.py`, `main_gabungan.py`. | `python input_gabungan/main_gabungan.py --sumber Agenda.xlsx ...` |
| `ganti_moda/` | CAPI→PAPI fasih-sm: `ubah_moda.py` (+ `--console`), `ubah_moda_console.js`. | `python ganti_moda/ubah_moda.py --sumber Agenda.xlsx --console` |
| `reset_mitra/` | Reset password akun PPL di manajemen-mitra: `reset_mitra.py` (+ `--console`), `reset_mitra_console.js`. | `python reset_mitra/reset_mitra.py --sumber Agenda.xlsx --console` |
| `tests/` | Uji offline (Python & Node). Semua menambahkan root ke path, impor `from inti...`/`from input_gabungan...`. Jalankan mis. `python tests/test_gabungan_loader.py`, `node tests/test_ubah_moda_console.js`. |
| `docs/` | `PANDUAN_*.md`, `catatan usaha pecahan se2026.md`. `CLAUDE.md` sengaja TETAP di root (dimuat otomatis tiap sesi). |
| root | Data & artefak runtime: `Agenda.xlsx`, `LKpenyalinan.csv`, `export/`, `log_screenshots/`, `log_fasih_sm/`, `audit_log*.csv`, `*.siap.js`. |

Kalau memindah file antar folder: perbarui impor (`inti.x`), pastikan folder tujuan punya `__init__.py`, dan jalankan seluruh test. Kalau menambah entry-script baru di folder, salin blok bootstrap `_sys.path.insert` dari skrip lain.

Di bawah, kolom pertama tabel "Peta arsitektur" memakai nama file polos — lokasinya sesuai tabel folder di atas.

## ATURAN KESELAMATAN — baca sebelum ubah apapun

1. **Kirim/Submit itu IRREVERSIBLE.** Tidak ada cara membatalkan setelah "Konfirmasi Kirim" diklik. Pengaman yang sudah ada di `main.py` (default dry-run, wajib flag `--submit`, wajib ketik "YA" per-batch) jangan dilonggarkan.
2. **Jangan pernah reload/navigate-away paksa dari dokumen yang sudah ada data terisi.** Retry otomatis pada error transien (403/504) hanya aman kalau dokumen masih 0% progres — lihat `allow_retry_if_fresh` di `FasihWebSession.open_entry_for()`, dipanggil hanya sesaat setelah `create_document()`.
3. **Field "Nomor Urut Bangunan" (SE2026-P) jangan pernah disentuh saat pengisian normal.** Aman selama benar-benar belum pernah di-klik/fokus (tampil "-"). Begitu tersentuh sekali, nilainya jadi literal `0` dan tidak bisa dikembalikan ke null — `0` yang tersimpan memicu GALAT keras "Tidak boleh kurang dari 1" saat cek ringkasan pra-Kirim. `fill_se2026_p()` sengaja tidak pernah menyentuhnya; perbaikan hanya lewat `fix_nomor_urut_bangunan_if_needed()`, dipanggil dari `main.py` HANYA kalau `read_galat_detail()` membuktikan GALAT satu-satunya adalah field ini. Aturan isi: field readonly "NOMOR URUT BANGUNAN TERBESAR" ada angka → pakai angka+1; kosong → pakai 1. Isi via klik chevron ▲, bukan keyboard (spinner ini kadang tidak stabil dgn input keyboard langsung).
4. **Status di list PENDATAAN bisa stale sesaat setelah submit** (pernah tampil "DRAFT" padahal sudah terkirim, di record 3). `verify_submitted_in_list()` sudah klik "Muat Ulang" dulu sebelum baca status — jangan hapus langkah itu.
5. **GALAT harus 0 sebelum kirim.** Kalau GALAT>0 dan bukan cuma soal Nomor Urut Bangunan, `process_one_row()` skip record itu (`SKIP_GALAT_PERLU_REVIEW`/`SKIP_GALAT_TIDAK_TERATASI` di audit log) — jangan tambah logika utk menebak fix galat lain secara otomatis.
6. **JANGAN pakai `.count()` untuk memutuskan "belum ada"/"tidak ketemu".** `count()` adalah snapshot dan TIDAK menunggu render. Pada run 2026-09-03 cek duplikat di `create_document()` berjalan saat list PENDATAAN masih loading → hasilnya 0 → **dokumen duplikat terbuat**, padahal hapus dokumen itu soft-delete & ribet di level admin pusat. Untuk keputusan ada/tidak ada, pakai `wait_for(state=...)` atau `_find_row_visible()` yang auto-wait. `count()` hanya boleh dipakai untuk cabang opsional yang tidak berkonsekuensi (mis. "kalau tombol Muat Ulang ada, klik").

## Lingkungan

- Wajib VPN kantor BPS aktif — fasih-web/fasih-sm tidak bisa diakses tanpa itu.
- **Status uji live (per 2026-09-03):** SELURUH alur dry-run sudah berjalan end-to-end pada record 2513 dan berhenti di `DRY_RUN_SIAP_KIRIM` dengan **GALAT=0, PERINGATAN=1, CATATAN=0, KOSONG=20** — cocok dgn pola 3 record manual yang sukses terkirim. Yang BELUM pernah dijalankan: `submit_final()` & `verify_submitted_in_list()` (sengaja — lihat aturan keselamatan #1 dan aturan #14 di `catatan usaha pecahan se2026.md`: konfirmasi eksplisit user per record).
- Selector kini berbasis **dataKey** (`config.py -> DK`), bukan label. Semua entri di `DK` diambil dari hasil `--dump-dom` pada dokumen asli, bukan tebakan. `L` tinggal dipakai utk teks OPSI (mis. "2. Tidak") dan judul tombol.
- Selektor **struktural** (bukan teks) dipusatkan di `config.py -> dict SEL`, semuanya dikutip dari dump DOM asli halaman Entri Dokumen. Ini lebih tahan banting daripada `L` karena tidak ikut berubah kalau bahasa UI diganti — prioritaskan `SEL` kalau ada pilihan.
- Setup sekali: `pip install playwright && playwright install chromium`.
- **Uji selector tanpa VPN**: `python tests/test_selectors.py` — menjalankan fixture DOM hasil dump asli. Jalankan ini dulu setiap kali mengubah selector; jauh lebih murah drpd membakar satu run live.

## Cara pakai

**Baca `PANDUAN_INPUT_OTOMATIS.md` dulu** — di situ alur harian 3 langkahnya, tabel status `audit_log.csv`, dan daftar nilai default yang ditetapkan user. Detail flag CLI ada di docstring atas `main.py`.

⚠️ **Skrip tidak selalu bisa membuat dokumen sendiri.** Kalau wilayah/SLS tujuan belum punya assignment di fasih-web, `create_document()` gagal (status `SKIP_DOKUMEN_BELUM_ADA`) — buat dokumennya manual dulu, lalu jalankan ulang; cek duplikat akan menemukannya dan skrip langsung mengisi. Poin paling penting: **validasi dry-run dulu thd 3 record yang sudah diketahui hasilnya (No 2510/2511/2512) sebelum menyentuh backlog baru**, dan perbaiki `FieldNotFound` dengan mengedit `config.py -> dict L` (bukan logika di file lain). Default tanpa `--submit` = dry-run aman; `--submit` + ketik "YA" = live/irreversible.

Sumber field BLOK II defaultnya BUKAN live-scrape fasih-sm lagi (rawan deteksi bot), tapi baca file `export/{No}_{assignment_id}.converted.json` hasil ekspor manual — lihat `PANDUAN_EKSPOR_MANUAL.md` utk cara bikin file itu, dan `export_source.py` utk logika pemetaan+fuzzy-match-nya. Baris tanpa file export otomatis di-skip (`SKIP_EXPORT_...`); pakai `--allow-live-scrape` di `main.py` HANYA kalau sadar mau fallback ke `scrape_source.py` yang berisiko deteksi bot.

## Peta arsitektur

| File | Isi |
|---|---|
| `config.py` | Konstanta: URL, `FIXED_PASSWORD` (sama utk semua akun), override tetap (NIK/aset tanah/luas tanah), dict `L` (label field — `# EXACT` = dikutip persis dari screenshot nyata), dict `SEL` (selektor struktural) & dict `DK` (dataKey komponen) — keduanya dari dump DOM asli, `KODEPOS_BY_IDSUBSLS` (41 entri), `WILAYAH_BY_IDSUBSLS` (73 entri) |
| `data_loader.py` | CSV backlog → `BacklogRow`; `rupiah10()`/`sum_rupiah10()` (lihat bawah); parsing URL fasih-sm |
| `console_export_source.js` | Fallback DOM-scrape via DevTools Console kalau Metode A (Network tab) tidak bisa dipakai — lihat `PANDUAN_EKSPOR_MANUAL.md` |
| `convert_manual_export.py` | CLI: ubah hasil "Copy response" endpoint `get-by-assignment-id` (fasih-sm) jadi field BLOK II rapi (`export/*.converted.json`) — dataKey ASLI, bukan tebakan label DOM |
| `export_source.py` | Sumber BLOK II UTAMA (menggantikan live-scrape di alur normal): baca `export/{No}_{assignment_id}.converted.json`, cocokkan usaha ke kolom P backlog (`nama_usaha_di_keluarga`) via fuzzy match — hanya match EXACT (score 1.0) yang dipakai otomatis, FUZZY/NO_MATCH/file hilang dikembalikan sbg status utk di-skip main.py (`SKIP_EXPORT_<status>`), bukan ditebak |
| `scrape_source.py` | FALLBACK opsional (`--allow-live-scrape` di `main.py`) — live-scrape field deskriptif dari fasih-sm. **Paling berisiko** — selector belum pernah diverifikasi thd HTML asli & rawan deteksi bot; tidak scrape 13b1-3/pekerja/kepemilikan-modal (lihat "Gap yang diketahui") |
| `fasih_web.py` | Semua interaksi ke fasih-web: login, buka dokumen, SE2026-P, geotagging, fix Nomor Urut Bangunan, KBLI Master search (dgn retry), cek ringkasan, submit, verifikasi status. Kelas: `FasihWebSession` |
| `fill_blok2.py` | Pemetaan BacklogRow+SourceBlok2 → field BLOK II; deteksi kondisional 26c/rincian-20 dari DOM (`field_present()`), bukan tabel kategori KBLI hardcode; rincian 29 pakai `src.kepemilikan_modal` (dari export) kalau ada, fallback `KEPEMILIKAN_MODAL_DEFAULT` |
| `preflight.py` | Pemeriksa kesiapan backlog TANPA browser/VPN: kodepos, file export & kecocokannya, alamat, kredensial; plus usulan kodepos yang DITURUNKAN dari desa yang sama (10 digit pertama idsubsls). Jalankan sebelum `main.py` |
| `main.py` | Orkestrasi CLI: baca CSV → grup per (email PPL, assignment) → per baris coba `export_source.py` dulu (fallback `scrape_source.py` kalau `--allow-live-scrape`) → proses → `audit_log.csv` |
| `gabungan_loader.py` | Sumber KEDUA: tab "gabungan" sheet Agenda (.xlsx/.csv) → `GabunganRow`; pemeriksaan offline (`periksa_semua`) yg men-skip baris SEBELUM dokumen dibuat. Opsi radio divalidasi thd `OPSI_FORM` (dikutip dari dump DOM) |
| `fill_gabungan.py` | Isi BLOK II dari `GabunganRow` — nilai apa adanya, urutan bersyarat sama dgn `fill_blok2.py` |
| `main_gabungan.py` | Orkestrasi sumber gabungan (`--cek` = preflight tanpa browser) → `audit_log_gabungan.csv`. Panduan: `PANDUAN_GABUNGAN.md` |
| `ubah_moda.py` | fasih-sm (TULIS): ganti mode assignment CAPI→PAPI per idsubsls Agenda, supaya fasih-web bisa "+Dokumen Baru". Login manual (profil persisten), `--petakan` → dry-run → `--eksekusi`. Logika murni diuji di `tests/test_ubah_moda.py`. `--console` menulis file siap-tempel utk jalur utama di bawah |
| `ubah_moda_console.js` | **Jalur utama** ganti mode: template yang ditempel di DevTools Console Chrome biasa (fasih-sm mendeteksi Playwright). Mode `petakan`/`dryrun`/`manual` (manusia klik Ganti Mode)/`otomatis`. Logika murni HARUS sama dgn `ubah_moda.py` — kasus uji kembar di `tests/test_ubah_moda_console.js` (`node ...`) |
| `reset_mitra.py` | Kumpulkan akun PPL unik dari Agenda (kunci cocok = **gmail sbg username**, cakupan **PPL saja** — ketetapan user 2026-09-14) → `target_reset_mitra.csv`; `--console` menyuntik ke template Console. TIDAK buka browser, TIDAK sentuh password |
| `reset_mitra_console.js` | Reset password akun mitra di manajemen-mitra dari Console Chrome. Struktur akun-mitra dipetakan 2026-09-14 (lihat catatan bawah); `SELEKTOR_RESET` sudah terisi (tombol "Reset PW" per baris). Mode `petakan`/`cocok` READ-ONLY; `manual` (manusia klik Reset PW + konfirmasi); `otomatis` (butuh manual dulu). Logika murni: `tests/test_reset_mitra_console.js`. Panduan: `docs/PANDUAN_RESET_MITRA.md` |

## Cara kerja form-engine fasih-web (dari dump DOM asli, 2026-09-02)

Kuesioner fasih-web dirender oleh "form-engine" (SolidJS) yang perilakunya sangat menentukan cara menulis selector. Enam hal yang wajib diingat:

1. **Hanya section AKTIF yang ada di DOM.** Field milik section lain benar-benar tidak ter-render — bukan sekadar tersembunyi. Jadi setiap `fill_*()` wajib dipastikan berjalan saat section-nya aktif; kalau tidak, hasilnya pasti `FieldNotFound`. Pakai `goto_section()` / `next_section()` sebelum mengisi.
2. **Setiap komponen dirender dengan `id` = `dataKey`-nya** (mis. `<div id="mulai">`, `<div id="keterangan">`). Ini pegangan paling stabil untuk menargetkan field — jauh lebih baik daripada menebak label. Pakai `--dump-dom` untuk memetakan `dataKey` section yang selektornya belum diketahui; hasilnya `log_screenshots/*.map.tsv` (kolom: dataKey / jenis input / teks).
3. **Section berikutnya baru ter-unlock setelah prasyaratnya terisi.** Tombol `#fasih-form-nav-next-button` HANYA dirender kalau memang ada section berikutnya yang ter-enable; kalau tidak, yang muncul justru `#fasih-form-nav-submit-button`. Jadi `has_next_section()` adalah deteksi akurat, bukan tebakan. Contoh: sebelum Waktu Mulai terisi, PENGANTAR adalah satu-satunya section di sidebar.
4. **Sebagian teks dirender DUA KALI** (varian mobile & desktop), salah satunya di-`hidden` via CSS. Akibatnya `.first` bisa nyangkut di elemen hidden lalu `wait_for()` (default `state=visible`) timeout padahal elemen visible-nya ada — ini persis penyebab kegagalan `open_entry_for()`. **Selalu saring `visible=true` dulu** (`FasihWebSession._visible()`) sebelum `.first`/`wait_for()`. Perhatikan `count()` TIDAK menyaring hidden, sedangkan `get_by_role()` otomatis mengabaikan `display:none` — perbedaan ini pernah bikin `create_document()` lolos tapi `open_entry_for()` gagal pada halaman yang sama.

5. **Komponen waktu tidak punya tombol saat sudah terisi.** `#mulai` yang kosong menampilkan "Waktu belum diambil" + tombol "Ambil Waktu"; setelah terisi ia hanya menampilkan tanggal/jam — **tanpa tombol apa pun**, termasuk tanpa "Perbarui Waktu" (waktu mulai memang tidak bisa diubah lagi). Jadi deteksi "sudah terisi" harus lewat hilangnya teks "Waktu belum diambil", bukan lewat keberadaan tombol.
6. **Pertanyaan bersyarat bisa memunculkan komponen baru**, bukan cuma menyembunyikan yang ada. Contoh nyata: `#kunjungan_1` ("Waktu Kunjungan I") TIDAK ADA di DOM sampai `#mulai` terisi. Jadi jangan menyimpulkan "field X tidak ada" dari satu dump — dump ulang setiap selesai mengisi sesuatu.

Konsekuensi lain: field milik **pengawas (PML)** — `#kunjungan_pml`, `#geotag_pml`, `#catatan_pml` — ada di template tapi di-`display:none` oleh CSS yang disuntikkan komponen `#pml_hidden`. Itu beda dari `#kunjungan_1` yang memang jatah pencacah.

### Urutan section (terverifikasi via `--dump-dom`, dokumen "Bangunan Lainnya")

```
PENGANTAR → IDENTITAS WILAYAH → SE2026 - P → SE2026 - L BLOK II
          → [nested: Keterangan Usaha/Perusahaan] → KETERANGAN PEMBERI JAWABAN → CATATAN
```

Bukan PENGANTAR → SE2026-P seperti dugaan awal. Blok I (Keterangan Umum Keluarga) memang di-skip — sesuai aturan #11 di `catatan usaha pecahan se2026.md`.

Tiga hal yang bikin navigasi ini tidak sesederhana "klik Berikutnya":

1. **Judul section pakai spasi**: `"SE2026 - P"`, `"SE2026 - L BLOK II"` — bukan `SE2026-P`.
2. **BLOK II adalah komponen NESTED.** Field detailnya tidak ada di DOM sampai kartunya diklik (`buka_nested()`, atribut stabil `[data-nested-view="true"]`).
3. **Dari dalam nested, `next_section()` kembali ke induknya**, bukan maju. Untuk keluar, lompat lewat sidebar: `goto_section("KETERANGAN PEMBERI JAWABAN")`.

### dataKey yang sudah terpetakan

Semua ada di `config.py -> dict DK` (diambil dari dump, bukan tebakan):

| Section | dataKey |
|---|---|
| PENGANTAR | `keterangan`, `mulai`, `kunjungan_1`, `pml_hidden` |
| BLOK I. IDENTITAS WILAYAH | `prov`, `kab`, `kec`, `desa`, `ubah_wilayah` (hidden), `klas_desa`, `kode_sls`, `nama_sls`, `ubah_sls` (wajib), `kodepos` (wajib) |

| SE2026 - P | `jenis_prelist`, `is_new`, `pilih_umkm`, `nama_usaha_bang`, `ada_bang_usaha` → lalu bersyarat: `jalan_domisili`, `nomor_domisili`, `no_bangunan_terbesar`, `no_bang` ⚠️, `kode_bang`, `geotag` |
| SE2026 - L BLOK II (nested) | `keberadaan_usaha` → `nama_komersial`, `rt`, `rw`, `hp`, `jenis_kawasan`, `punya_nib`, `badan_usaha`, `lap_keuangan`, `pengusaha`, `jk`, `umur`, `nik_pengusaha`, `keg_utama`, `produk_sendiri`, `layanan_mamin`, `keg_penjualan` → bersyarat `keg_jasa` (13b4, muncul kalau 13b1/b2/b3 semuanya "Tidak"), `produk`, `kbli_genai`+`kbli`, `kategori`, `jaringan`, `internet` (16a) → bersyarat `internet_pesanan`/`internet_produksi`/`internet_distribusi`/`internet_beli`/`internet_promosi`/`internet_lainnya` (16b1-b6) + `digital` (16c) + `pendapatan_online` (27d), `pilih_umkm_sls`, `produksi_lingkungan`, `perlindungan_lingkungan`, `produk_seni`, `izin_edar`, `mitra_kdkmp`, `peran_mbg`, `barang_non_pddk`, `jasa_non_pddk`, `beli_jasa_non_pddk`, `tk_laki`, `tk_pr`, `tk_dibayar`, `tk_tdk_dibayar`, `tahun_operasi`, `gaji`, `biaya_produksi`, `biaya_pembelian`, `operasional`, `non_operasional`, `nilai_pendapatan`, `pendapatan_lain`, `aset_usaha_thn`, `aset_lain_thn`, `luas_tanah_thn`, `pribadi`…`asing` |
| KETERANGAN PEMBERI JAWABAN | `nama_info_list` (combobox), `telp_info`, `email_info`, `persetujuan_responden` (checkbox) |

Rincian 1-7 di BLOK I sudah auto-terisi dari wilayah dokumen — jangan disentuh.

### Jebakan selector yang sudah memakan waktu (jangan diulang)

- **`get_by_role("button", name=/Gunakan Lokasi/i)` juga cocok dengan tombol locate peta** (`title="Gunakan lokasi saat ini"`), dan tombol locate lebih dulu di DOM. Akibatnya `.first` mengklik tombol yang salah tanpa error & tanpa jejak konsol. Pakai `exact=True`.
- **`offsetParent` selalu `null` untuk elemen `position: fixed`** — jangan dipakai menilai visibilitas modal (sempat bikin modal "Pilih Lokasi" dikira tidak muncul padahal terbuka).
- **Combobox fasih-web berbasis `<textarea>` dan harus DIKLIK dulu** supaya popover opsinya terbuka; mengetik tanpa membuka popover tidak memunculkan opsi apa pun. Pakai `pilih_combobox_by_datakey()`.
- **Checkbox Kobalte**: `<input type=checkbox>` disembunyikan, yang harus diklik adalah div `[id$="-control"]`.
- **Nama dataKey bisa menyesatkan**: `aset_usaha_thn` = *28a aset TANAH DAN BANGUNAN* (override 0), `aset_lain_thn` = *28b aset SELAIN tanah/bangunan* (10% sumber). Selalu cek label di dump, jangan menebak dari nama dataKey.
- **`pilih_umkm_sls` HANYA ada selama `keberadaan_usaha` belum terjawab.** Combobox "Pilih UMKM dalam satu SLS yang sama" (BLOK II, paling atas) hilang permanen dari DOM begitu `keberadaan_usaha` dijawab — dan radio tidak bisa di-*unset*, jadi tidak ada jalan kembali (diuji: set "9. Non Respon" lalu balik "2. Baru" tetap tidak memunculkannya). Padahal validator ringkasan tetap menagihnya "Wajib diisi". Karena itu `fill_blok2()` mengisinya **sebelum** `keberadaan_usaha` — jangan pernah dibalik. Terverifikasi di dokumen baru (record 2523): opsinya cuma satu, **"Tidak Ada"**, cocok dgn aturan #8. Field ini tidak muncul di SLS yang tidak punya daftar UMKM prelist (record 2513).
- **Mengklik ulang radio me-RESET jawaban komponen turunannya.** Pada pengisian ulang record 2523, klik ulang `keberadaan_usaha` (yang nilainya sudah benar) menghapus jawaban `pilih_umkm_sls` dari run sebelumnya — dan karena komponennya sudah tidak dirender, jawabannya tidak bisa dikembalikan → GALAT. `select_radio_by_datakey()` sekarang **tidak mengklik kalau opsi yang diminta sudah tercentang** (`_radio_tercentang()`), jadi pengisian ulang aman. Jangan hapus penjagaan ini.
- **Identitas akun tidak selalu langsung terbaca.** Respons API `/users/check-user` bisa BELUM tiba saat verifikasi dipanggil, dan menu avatar belum ada selama halaman masih "Memuat Halaman..." — akibatnya `verifikasi_akun()` sempat mengembalikan `TIDAK_DIKETAHUI` di run user 2026-09-07 sehingga pengamannya diam. `identitas_akun()` sekarang MENUNGGU sadapan (6 dtk), lalu memanggil endpoint itu sendiri lewat `fetch` (GET, cookie sesi yang sama), baru menu avatar sbg cadangan terakhir. Kalau tetap gagal, `main.py` menandai baris itu `AKUN TIDAK TERVERIFIKASI` di kolom `review_disarankan` — jangan dihapus, itu satu-satunya jejak kalau pengaman sedang tidak bekerja.
- **Nama depan bukan identitas.** Sapaan dasbor ("Selamat sore, Komang") tidak bisa dipakai memverifikasi akun: KEDUA BELAS PPL di backlog ini bernama depan "Komang". Pakai `identitas_akun()` yang membaca respons API `/users/check-user` (fullname + email).
- **Fallback "klik teks pertama di halaman" DIHAPUS dari `select_radio()`** — opsi radio BLOK II hampir semuanya berteks "1. Ya"/"2. Tidak", jadi fallback itu pasti menjawab pertanyaan yang salah. `select_radio_by_datakey()` sekarang memverifikasi radio mana yang benar-benar tercentang setelah klik. Yang diisi skrip cuma rincian 8 (`ubah_sls` → "2. Tidak") & rincian 10 (`kodepos`). Menjawab rincian 8 dengan "1. Ya" akan memunculkan rincian 9 yang tidak punya sumber data di backlog.

## Pergantian akun (SSO Keycloak)

Sesi login **bukan milik fasih-web**, melainkan Keycloak di `sso.bps.go.id` — cookie `KEYCLOAK_IDENTITY`, `KEYCLOAK_SESSION`, `AUTH_SESSION_ID` ada di domain `.sso.bps.go.id` (diverifikasi 2026-09-06). Konsekuensinya:

- Logout dari fasih-web saja **tidak memutus sesi**; klik "SSO Eksternal" berikutnya langsung tembus ke Dasbor sbg akun LAMA tanpa menanyakan kredensial sama sekali. Ini gejala yang dilaporkan user 2026-09-06.
- Di skrip, yang benar-benar memutus sesi adalah `context.clear_cookies()` (semua domain), bukan logout UI. `FasihWebSession.logout()` melakukan keduanya: buka menu avatar → klik "Keluar", lalu bersihkan cookie + storage.
- Di Chrome biasa milik user, padanannya: logout dari `sso.bps.go.id`, atau hapus cookie situs itu — bukan cuma fasih-web.

Pengaman yang lebih penting drpd logout itu sendiri: **`login()` memverifikasi akun yang benar-benar aktif** lewat `identitas_akun()`, dan melempar `RuntimeError("AKUN SALAH: ...")` kalau tidak cocok (`ERROR_AKUN_SALAH` di audit log). Tanpa ini, sesi nyangkut akan membuat skrip mengisi — dan di mode `--submit` MENGIRIM — dokumen atas nama PPL yang salah tanpa satu pun tanda peringatan. Sudah diuji live: login A → logout → login B dalam satu context, keduanya terverifikasi benar.

## Kalkulasi finansial

Rincian 26/27/28b = 10% nilai sumber, dibulatkan **round-half-up** (bukan round-half-even default `round()` Python) — pakai `decimal.Decimal` + `ROUND_HALF_UP`. Kategori KBLI B–F & I-gol.56 tidak render field 26c terpisah: `biaya_produksi`+`biaya_pembelian` harus dijumlah dulu sbg Decimal, baru dikali 10% & dibulatkan sekali (`sum_rupiah10`) — urutan ini sudah divalidasi persis thd record 2 (33.600.008 → ×10% → 3.360.000,8 → round half up → 3.360.001, cocok data submit asli). Ini bagian paling percaya diri dari seluruh skrip: `rupiah10`/`sum_rupiah10` sudah diuji cocok 100% thd nilai asli ketiga record manual.

### Aturan pekerja (24) ↔ upah/gaji (26a) — ditetapkan user 2026-09-06

Bukan turunan dari data sumber, melainkan **keputusan pengguna**. Logikanya murni di `data_loader.rencana_pekerja()` + `rencana_pengeluaran()` (tanpa Playwright, jadi bisa diuji offline: `python tests/test_pengeluaran.py`); `fill_blok2.py` cuma mengetik hasilnya.

| Total pekerja (24a1+24b1) | Rincian 24 | Rincian 26a | Pos pengeluaran lain |
|---|---|---|---|
| ≤ 3 (`BATAS_TK_SEMUA_TIDAK_DIBAYAR`) | 24a2 (dibayar) = **0**, 24b2 (tidak dibayar) = total | **0** | tidak disentuh — total 26f ikut turun |
| > 3 | apa adanya dari sumber | 10% sumber (normal) | 26a **dipotong** dari pos terbesar, kaskade ke terbesar berikutnya kalau kurang |

Tiga hal yang sengaja dibuat begitu:

- **Asimetris.** Cabang ≤3 menurunkan total pengeluaran tanpa kompensasi (pekerja tidak dibayar memang tidak menimbulkan biaya upah); cabang >3 menjaga total tetap. Itu memang bunyi aturannya, bukan kelalaian.
- **Pemotongan dilakukan pada angka FINAL** (pasca 10% & pembulatan), bukan di level sumber — supaya total yang terisi persis sama dgn sebelum pemotongan. Kalau dipotong di level sumber, pembulatan bisa geser ±1.
- **Kalau total pekerja tidak diketahui dari sumber, aturan TIDAK diterapkan** (jatuh ke perilaku lama, 26a = 10%) dan dicatat sbg peringatan di log — sesuai prinsip repo ini: lebih baik berhenti/lapor drpd menebak. Begitu juga kalau pos lain tidak cukup menutupi 26a: sisanya tidak dipotong dan diperingatkan, bukan dipaksa jadi negatif.

⚠️ Pada backlog per 2026-09-06 (2513–2520) aturan ini **belum mengubah apa pun**: kedelapan baris punya 1 pekerja tidak dibayar dan `gaji` sumber = 0. Jadi cabang >3 (pemotongan) baru teruji lewat `tests/test_pengeluaran.py`, belum lewat data nyata.

## Varian kuesioner & kendala form (temuan batch 90 baris, 2026-09-07)

- **HEADLESS DILARANG.** `fasih-web.bps.go.id/login` membalas browser headless dgn halaman tantangan anti-bot ("Kami mendeteksi perilaku yang tidak wajar pada perangkat anda"), bukan form login — headed di mesin & VPN yang sama normal. Flag `--headless` sengaja dipertahankan tapi menolak jalan, supaya penolakannya eksplisit. (Flag ini dulu tidak pernah berefek karena `--headed` default `True`; begitu bug itu dibetulkan, 42 login gagal beruntun.)
- **Varian BULANAN (rincian 30-33).** Kalau usaha MULAI BEROPERASI pada tahun berjalan, form mengganti 26/27/28/29 dgn 30/31/32/33: pengeluaran & penjualan **satu bulan terakhir**, aset **akhir bulan lalu**, kepemilikan modal **saat didirikan**, plus 31e "Bulan beroperasi selama tahun 2026". Minimal totalnya 10.000 (bukan 100.000). dataKey-nya berakhiran `_bln` (lihat `DK`). Nilai backlog bersifat TAHUNAN sehingga TIDAK boleh dipakai apa adanya — `fill_blok2()` melempar `VarianTidakDidukung` dan `main.py` menandainya `SKIP_VARIAN_BULANAN` utk diisi manual. Jangan diam-diam mengisinya dgn angka tahunan.
- **Minimal 100.000** pada 26f & 27c ("Nilai minimal 100.000"). Ketetapan user: kekurangannya ditambahkan ke pos terbesar sampai pas 100.000 (kalau semua pos nol, ditampung `POS_PENAMPUNG_MINIMAL` = 26d). Baris yang kena ditandai `DINAIKKAN` di `review_disarankan` — angkanya tidak lagi 10% sumber.
- **Minimal satu dari 16b1-b6 harus "1. Ya"** ("Salah satu dari 16b1 - 16b6 wajib terisi YA"). `fill_blok2()` gagal cepat kalau `DEFAULT_16B_TUJUAN_INTERNET` melanggarnya.
- **20c wajib di SEMUA cabang jawaban 20a**, bukan hanya saat "3. Tidak". **20b** (`sudah_bpom`) muncul bersamanya.
- **13d & 13e** (`input`, `proses`) muncul kalau 13b1 = "1. Ya"; **13b4** (`keg_jasa`) muncul kalau 13b1/b2/b3 semuanya "2. Tidak" — pilihannya diturunkan dari kategori KBLI (A = Pertanian, selain itu Jasa), bukan ditebak.
- Ketiga field di atas ADA di sumber tapi dulu tidak dipetakan `convert_manual_export.py`. Kalau menambah pemetaan baru di sana, **konversi ulang seluruh export**: `for f in export/*.json; do python convert_manual_export.py "$f"; done` (lewati `*.converted.json`).
- **Kegagalan transien itu normal & harus di-retry, bukan dibiarkan gagal**: pencarian Master KBLI, mount form-engine di dokumen baru, tombol "+Dokumen Baru", dan combobox "Nama Pemberi Informasi" semuanya pernah gagal sesaat lalu sukses saat diulang. Retry-nya sudah terpasang di masing-masing; jangan dihapus.
- **Tombol "+Dokumen Baru" tidak ada** = wilayah itu belum punya assignment. `create_document()` mengembalikan False (-> `SKIP_DOKUMEN_BELUM_ADA`), bukan melempar TimeoutError.

## Sumber data gabungan (sheet "Agenda", 2026-09-13)

Alur terpisah (`main_gabungan.py`), bukan pengganti backlog LKpenyalinan. Hal yang beda & mudah salah:

- **Nilai sheet = jawaban final.** JANGAN terapkan `rupiah10`, `rencana_pekerja` (≤3), `ASET_TANAH_OVERRIDE`/`LUAS_TANAH_OVERRIDE` — itu aturan backlog lama. `tests/test_fill_gabungan.py` mengunci ini.
- **Tidak ada kolom No.** Identitas baris = `GabunganRow.kunci` (hash akun+idsubsls+nama); `--lewati-selesai` memakai kunci, bukan nomor baris.
- **⚠️ RENCANA 2026-09-14: SATU subsls + SATU akun PPL utk SEMUA dokumen** (sebagian subsls sudah ditandai selesai → tidak bisa tambah assignment). `GABUNGAN_SUBSLS_TUNGGAL`/`GABUNGAN_AKUN_TUNGGAL` di config atau `--subsls-tunggal`/`--akun-tunggal`; tanpa itu browser-run ditolak, alur lama = `--per-baris`. Wilayah dipindah BELAKANGAN lewat "ubah alokasi wilayah" — otomatisasinya baru dibuat SETELAH semua terinput (permintaan user); bahannya di audit: `idsubsls` (wilayah asli/tujuan), `idsubsls_input`, `akun_login`, `dokumen_url`. Kodepos/geotag/alamat tetap milik baris. Konsekuensi yang dikunci test (`tests/test_gabungan_loader.py`, `tests/test_main_gabungan.py`):
  - **Satu list PENDATAAN** → `NAMA_TUMPANG_TINDIH` diperiksa lintas SELURUH sheet pada `nama_dokumen` (termasuk nama sama persis beda kunci); nama mentah cukup tanda (risiko `SKIP_DOKUMEN_NAMA_LAMA`). `WILAYAH_TIDAK_KONSISTEN` → tanda, bukan skip.
  - **List berhalaman ratusan dokumen** → `create_document` cuma cek halaman 1, jadi pencegah duplikat utamanya AUDIT: begitu `sess.dokumen_dibuat`, baris `DOKUMEN_DIBUAT` (+URL kalau ada) ditulis SEBELUM mengisi. Run berikut: ada URL → `buka_dokumen_url()`; tanpa URL → `open_entry_for` saja, TIDAK PERNAH create lagi. Kunci yang dokumennya tercatat dgn akun/subsls lain dilewati. Jangan ubah jadi pencarian list.
  - **Cek langsung** (permintaan user): akun login wajib terbaca = akun tunggal (bukan `TIDAK_DIKETAHUI`); `STOP_SUBSLS_TIDAK_BISA_DIPILIH` / `SKIP_DOKUMEN_BELUM_ADA` / `STOP_WILAYAH_DOKUMEN_BEDA` menghentikan batch; `baca_wilayah_dokumen()` + `cocokkan_wilayah_dokumen()` membaca rincian 1-6 BLOK I setelah PENGANTAR. Format nilai field itu BELUM terekam (dump tidak memuat `value`) — `TIDAK_TERBACA` tetap diisi tapi tidak dikirim (`SKIP_WILAYAH_TIDAK_TERVERIFIKASI`). Setelah dry-run live pertama, kunci formatnya di sini dari kolom `wilayah_dokumen`.
  - Login ulang tiap `GABUNGAN_BARIS_PER_SESI` baris (sesi SSO ±12 jam). Audit lama dimigrasi header otomatis (`_pastikan_header_audit`).
- **Temuan run LIVE pertama mode satu subsls (2026-09-14, akun `wisada9@mail.com`, subsls `5108010010000105`)** — kunci di sini, jangan diulang:
  - Modal "Buat Dokumen Baru" akun ini **TIDAK punya field nama** (hanya 6 dropdown Wilayah). Nama dokumen di list berasal dari SE2026-P (`data1`). Pencarian field nama kini dibatasi di dalam `[role=dialog]` & opsional (`sess.nama_di_modal`); versi lama mencari di seluruh halaman.
  - Placeholder dropdown level 1 bisa masih "Pilih Wilayah Level 1" + "Memuat data wilayah..." (popover terbuka sendiri) → terima kedua placeholder, tunggu 30 dtk, klik pemicu maks 2x sebelum menyimpulkan opsi tidak ada.
  - **Toast "berhasil dibuat" muncul SEBELUM navigasi ke /entry.** Jangan ke list setelah toast (membatalkan navigasi → dokumen kosong tanpa nama & tanpa URL = yatim; terjadi di baris 4, URL-nya `fc284567…` dicatat manual di audit). Sekarang ditunggu 25 dtk; tetap tanpa URL & modal tanpa nama → `STOP_DOKUMEN_TANPA_URL` (batch berhenti).
  - **Nama Jalan (SE2026-P) wajib >= 10 huruf a-z** kalau diisi selain kosong/"-" (validasi template `jalan_domisili`). Ketetapan user: alamat pendek DILENGKAPI nama wilayah baris (banjar dari config kalau ada → `DESA …` → `KECAMATAN …` → provinsi, berhenti begitu cukup; "0" dianggap kosong) lewat `lengkapi_alamat()` / `row.jalan_lengkap`. Nama desa/kec dari tab "Pangkalan Gas"/"Faskes" di Agenda.xlsx (`_baca_nama_wilayah`, suara terbanyak per kode), cadangan kolom 8c. Kalau kedua sumber menunjuk desa berbeda → **pakai desa menurut idsubsls** (ketetapan user 2026-09-14, dulu skip), bentroknya ikut dicatat di tanda review.
  - **Aturan validasi form ada lengkap di** `GET /api/designer/api/template/file-validation/2230fffc-…?templateVersion=6.5.3` (JSON `testFunctions[].validations[].test` = JS). Sumber terbaik utk pemeriksaan offline baru — jangan menebak aturan dari pesan GALAT.
  - **8b maksimal 50 karakter** (GALAT "Panjang maksimal 50") → `MAKS_8B`. Ketetapan user 2026-09-14 (Agenda1-1: 12a berisi JABATAN "Bidan/Perawat Penanggung Jawab Pustu", bukan nama orang): kalau `<nama> (<12a>)` > 50, `nama_muat()` memakai **nama usaha saja tanpa kurung** utk nama dokumen & 8b (12a di form tetap utuh, tanda "tanpa (12a)"). Nama usaha sendiri > 50 → tetap skip `8B_TERLALU_PANJANG` (tidak dipotong). Efek samping: nama tanpa kurung lebih mudah saling memuat → `NAMA_TUMPANG_TINDIH` (Agenda1-1 baris 60/137 "PUSKESMAS PEMBANTU MUNDUK [BESTALA]").
  - **Pekerja 24 pola `0/2/0/1`** (laki/perempuan/dibayar/tidak dibayar; Agenda1-1 66 baris, Agenda2 57 baris) → dikoreksi `0/2/0/2` (`KOREKSI_PEKERJA`, ketetapan user). Dibayar sengaja tetap 0: validasi `gaji` menolak 24a2>0 bila 26a/24a2 ≤ Rp50.000 (26a baris itu 0). Pola lain tetap skip. Aturan validasi lengkap (218 testFunctions) ada di endpoint file-validation — type 2 = GALAT, type 1 = peringatan.
  - **12c Umur wajib 10-99** (GALAT "Wajib terisi 10-99"). `Agenda1-1.xlsx` berisi umur `0` di SEMUA 200 baris → tiap baris sempat jadi DRAFT tak terkirim (baris 10/26/36/49/65/74/82/83/91, URL di audit). Kini skip offline `UMUR_DI_LUAR_10_99` SEBELUM dokumen dibuat — umur tidak ditebak.
  - **⛔ Satu akun = satu proses.** Run 2026-09-14: `Agenda.xlsx` & `Agenda1-1.xlsx` dijalankan bersamaan dgn akun megakartika → (a) sesi satu proses tiba-tiba ke halaman login di tengah "Buat Dokumen" (dugaan: `logout()` proses lain mencabut token akun itu, terasa saat access token habis), (b) dokumen yang dibuat proses lain menaikkan jumlah list → `STOP_DOKUMEN_TANPA_URL` PALSU (dicek via API: 0 yatim). `kunci_proses_akun()` (file `.proses_<akun>.lock` berisi PID) kini menolak proses kedua dgn akun sama, termasuk dgn `--paralel`. Paralel = akun & subsls BERBEDA per proses.
  - Memeriksa dokumen yatim: `status_dokumen` via API datatable (login akun itu, TANPA logout) lalu cocokkan `id` dgn segmen URL `dokumen_url` di audit. Dokumen lama milik akun (mis. dibuat Juni) memang tidak ada di audit.
  - Dokumen yang dikirim manual jadi read-only (input kodepos `disabled`) → `DOKUMEN_TERKUNCI`, dianggap tuntas.
  - Nilai rincian 1-6 BLOK I terekam: `prov='[51] BALI'; kab='[08] BULELENG'; kec='[010] GEROKGAK'; desa='[010] PATAS'; kode_sls='0001'` (kode SLS 4 digit, TANPA subsls) → `cocokkan_wilayah_dokumen` = COCOK.
  - Mengisi ulang dokumen lengkap memunculkan GALAT "Pilih UMKM dalam satu SLS yang sama" (komponennya sudah tidak dirender). Tersangka: `fill()` ulang `nama_usaha_bang`. `fill_by_datakey` kini melewati nilai yang sudah sama (`nilai_sama`). BELUM terbukti — kalau GALAT itu muncul lagi pada pengisian ulang, cari pemicunya.
  - List PENDATAAN dimuat dari `POST /api/analytic/api/v2/assignment/web-entry/datatable-all-user-survey-periode` (DataTables: `start`/`length`/`order`; respons `searchData[]` berisi `id` = segmen URL entry, `codeIdentity`, `data1` = nama, `assignmentStatusAlias`, `dateCreated`, `totalHit`). Belum dipakai skrip; kandidat utk mencari dokumen tanpa paginasi & utk ubah alokasi wilayah nanti.
- **Penamaan usaha = `<nama> (<12a pengusaha>)`** (ketetapan user 2026-09-14, `format_nama_usaha`). Dipakai utk nama dokumen/pencarian list/SE2026-P (`row.nama_dokumen`) dan 8b (`row.nama_komersial`) — user: berlaku utk nama usaha DAN komersial. `row.nama` & `kunci` tetap nama MENTAH. Kalau nama pemilik utuh sudah tertulis di nama usaha, yang di LUAR kurung dihapus ("PANGKALAN GAS JAMALUDIN" → "PANGKALAN GAS (JAMALUDIN)") supaya muat 50 karakter 8b. Hasil SELALU tepat satu pasang kurung di belakang: kurung lain dibuang, isinya dipertahankan (baris 393: 12a "…Sp.P (K" → "PRAKTIK DOKTER (I Nyoman Nama Putra Sp.P K)"). Karena dokumen lama bisa terlanjur dibuat dgn nama mentah, `main_gabungan` memanggil `create_document(..., nama_lama=row.nama)`: nama baru tidak ada tapi nama lama ada → `DokumenNamaLamaAda` → `SKIP_DOKUMEN_NAMA_LAMA`, TIDAK membuat duplikat. `NAMA_TUMPANG_TINDIH` diperiksa pada nama dokumen DAN nama mentah.
- **Kolom kode wilayah kehilangan nol di depan** ("60" utk "060") → `idsubsls_pilih` di-zero-pad. 60 baris tetap beda dgn kolom `idsubsls` → di-skip, tidak ditebak mana yang benar.
- **dataKey 10b = `nib`**, tapi key `nib` di `DK` sudah milik 10a (`punya_nib`) → pakai key `nib_nomor`.
- **Opsi 11a di sheet "1. Perseroan Terbatas (PT)/CV" tidak ada di form** (form: "1.a. Perseroan …" / "7. Persekutuan Komanditer (CV)"). Pemeriksaan opsi offline menangkapnya; kalau form berubah, perbarui `OPSI_FORM` dari dump baru.
- **13f tidak ada di sheet** → `GABUNGAN_13F_DARI_13A`. **Nama Jalan** di dump tidak bertanda `*` tapi belum diuji kosong → `GABUNGAN_IZINKAN_JALAN_KOSONG=False`.
- `open_entry_for(allow_retry_if_fresh=...)` di sini hanya True kalau `create_document` BARU membuat dokumen (`dokumen_url_terakhir` terisi) — main.py lama selalu True.
- Belum pernah dijalankan live. `ASSIGNMENT_ID_GABUNGAN` (segmen URL list) diasumsikan sama dgn backlog lama.

### fasih-sm: ganti mode (`ubah_moda.py`, dipetakan 2026-09-13)

Beda dgn catatan lama "fasih-sm read-only": skrip ini MENULIS ke fasih-sm. Yang terlihat langsung di list `/app/surveys/{SURVEY_ID}/{periode}/data`: kolom Kode Identitas (`idsubsls - JENIS - no`), Status, **Mode**, **Petugas Saat Ini**, Keterangan; checkbox "Pilih baris"; "Aksi Lainnya" → item massal **"Ganti Mode (Ke PAPI) (N)"** (N = jumlah tercentang; saat N=0 diklik tidak muncul apa pun). Menu ⋮ per baris juga punya "Ganti Mode".

- **Belum terverifikasi**: kotak "Cari..." menyaring per idsubsls atau tidak, dan ada/tidaknya dialog konfirmasi saat N≥1. Karena itu dry-run TIDAK PERNAH mengklik item Ganti Mode, dan semua kejanggalan berstatus di `STATUS_BERHENTI_SEGERA`. Setelah run `--petakan`/live pertama, baca `log_fasih_sm/` lalu kunci temuan di sini.
- **Menu Radix yang belum tertutup menelan klik berikutnya** — saat pemetaan, klik ikon filter malah mengenai item "Broadcast Status". `tutup_menu()` wajib (pakai `wait_for(hidden)`, bukan `count()`).
- **Jangan cocokkan baris lewat `has_text`**: "…- UMK - 4" juga cocok "…- UMK - 41". `_baris_tr()` memverifikasi kode persis di indeks barisnya.
- Login fasih-sm TIDAK diotomatiskan (tidak ada kata sandi di skrip); profil `.profil_fasih_sm/` berisi sesi — sudah di `.gitignore`.
- **fasih-sm mendeteksi bot** (F5/TSPD) → jalur utama `ubah_moda_console.js` di Chrome biasa. Kalau mengubah logika rencana/parsing, ubah KEDUA file & kedua test.
- Console memakai event sintetis — **belum pernah diuji di halaman asli**: pemicu menu Radix dibuka lewat `pointerdown` (bukan `click`, dgn cadangan click lalu Enter), kotak Cari diisi lewat setter nilai native + event `input` + Enter. Kalau `petakan` gagal membuka menu atau tabel tidak berubah, di situ dulu yang dicek.
- Pilihan TanStack bisa bertahan lintas pencarian → centang dilepas lagi (dicocokkan lewat KODE, bukan indeks) setelah tiap subsls, termasuk setelah sukses; sisa centang tertangkap sbg `JUMLAH_TERCENTANG_BEDA`.
- **Cukup SATU assignment PAPI mana pun per subsls** (ketetapan user 2026-09-14): petugasnya tidak harus PPL sheet — `PETUGAS_BEDA`/`PAPI_ADA_PETUGAS_LAIN`/`izinkanPetugasLain` dihapus; milik PPL sheet cuma didahulukan. Baris subsls LAIN di hasil pencarian **diabaikan** di `rencanakan()` (bukan lagi `PENCARIAN_TIDAK_MENYARING` yg menghentikan batch). Halaman tanpa satu pun baris subsls target -> `SUBSLS_TIDAK_TAMPIL` (berhenti).
- **⛔ JANGAN PINDAH PAGINASI** (temuan user 2026-09-14): halaman fasih-sm yang dipindah tidak memuat datanya dgn benar. Dryrun pertama: subsls pertama (`5108070…`, 322 assignment) dibaca 4 halaman, subsls KEDUA lalu terbaca 100 baris subsls lain — kemungkinan besar akibat pindah halaman itu (plus kotak Cari yg dikosongkan dulu). Kode paginasi (`geserHalaman`/`keHalaman`/`maksHalaman`) DIHAPUS; `cari()` hanya membaca halaman yang tampil setelah pencarian ("Page x of y" cuma DIBACA). Konsekuensi: PAPI di halaman 2 dst. tidak terlihat -> subsls itu bisa dapat 1 PAPI tambahan (diizinkan user: "pilih terserah"); pesan mencatat ">1 halaman, hanya halaman tampil yang dibaca". Cakupan "semua" berhenti `PERLU_HALAMAN_LAIN` begitu halaman tampil habis CAPI-nya. `perPage` < 50 tetap ditolak (makin banyak baris tampil, makin besar peluang PAPI terlihat).
- **Filter Mode (CAPI/PAPI) ada di tabel** (kata user) tapi strukturnya BELUM dipetakan — itulah jalan menutup celah PAPI di halaman lain. Jangan menebak: user buka filter manual, jalankan `ubahModa.petakanFilter("catatan")` (READ-ONLY, tidak mengklik) di tiap langkah, lalu `ubahModa.petakanFilter.hasil()` mengunduh JSON-nya. Selama filter belum diotomatiskan, JANGAN pasang filter Mode manual saat skrip jalan: filter PAPI membuat subsls tanpa PAPI terbaca kosong, filter CAPI membuat baris yg sudah diubah "hilang" saat verifikasi.
- **Tombol "Aksi Lainnya" setelah baris dicentang** (dryrun 2026-09-14): pencocokan teks PERSIS tanpa menunggu gagal (`TIDAK_ADA_AKSES`) tepat setelah 1 baris dicentang, padahal saat 0 dicentang tombolnya ketemu — teksnya kemungkinan berubah (mis. "Aksi Lainnya (1)") atau toolbar render ulang. Sekarang: diawali "Aksi Lainnya", ditunggu 10 dtk, dan kalau gagal pesan memuat daftar tombol yang terlihat (pakai itu utk memperbaiki selektor). `TIDAK_ADA_AKSES` tidak lagi menghentikan batch seketika (user: "tetap jalankan"); 3x beruntun baru berhenti.
- **Pencarian**: kotak Cari hanya dikosongkan kalau isinya subsls yang SAMA (verifikasi), dan ditunggu sampai daftar tanpa-saring benar-benar tampil sebelum diisi lagi; hasil dianggap siap kalau baris subsls target tampil & tabel diam (`tungguHasilCari`). Sebelum membuka menu, baris yang tercentang di halaman harus persis = rencana (`CENTANG_TIDAK_SESUAI`).

### manajemen-mitra: reset password (`reset_mitra_console.js`, dipetakan 2026-09-14)

- **Kunci cocok = gmail lewat kolom Email.** Halaman `/mitra/akun-mitra` punya tabel [NIK, Email, Nama Lengkap, Tanggal Terdaftar, Kelengkapan Data, Status SSO, Status Akun & Aksi] + kotak "Cari NIK, Email, Nama Lengkap, atau Sobat ID / Username (min. 5 karakter)". Satu email → tepat 1 mitra (diuji: `dinata.id2023@gmail.com` → "Luh Putu Irma Sandra Devi"). NIK ditampilkan ter-mask.
- **Reset = tombol "Reset PW" per baris** (kolom "Status Akun & Aksi"). Klik "Reset PW" TIDAK langsung mereset — membuka panel **2 field** (temuan user 2026-09-14): field 1 = password baru, **field 2 = email yg SUDAH terisi (JANGAN disentuh)**, lalu tombol **"Reset Password"**. `resetDiDialog()` mengisi HANYA field non-email (prefer `type=password`; berhenti kalau kandidatnya bukan tepat 1) dgn `PASSWORD_BARU` ("Mitra5108", = `FIXED_PASSWORD`; override via `jalankan({passwordBaru})`), lalu klik tombol "Reset Password" (exact), fallback `pilihTombolKonfirmasi`.
- **Panel "OK" pasca-reset** (temuan user 2026-09-14): setelah "Reset Password" & toast sukses, muncul panel konfirmasi ber-tombol "OK" yang WAJIB ditutup — kalau tidak, ia menutupi akun berikutnya & batch macet. `tutupKonfirmasiOK()` mengkliknya (OK/Oke/Tutup/Selesai/Mengerti, via `kontrolKlik` yg juga cakup `<a>`/`[role=button]`), dipanggil setelah tiap reset + defensif di awal `cari()`. Tombol "Reset Password" TERNYATA bukan `<button>` polos (0 `<button>` di panel) → `kontrolKlik` mencakup `button, [role=button], a, input submit`, target teks persis "Reset Password" (fallback global kalau footer di luar node dialog).
- **False-positive sukses (diperbaiki):** `POLA_SUKSES` versi lama memuat "password baru" → cocok dgn LABEL field dialog → menandai DIRESET padahal belum. Sekarang `POLA_SUKSES=/berhasil|sukses|tersimpan|diperbarui|diubah|ter-update/i` (toast pasca-simpan saja). `isiInputReact` juga TIDAK menekan Enter di field password (bisa submit prematur) — Enter hanya di kotak cari.
- **Struktur dialog "Reset PW" TERKONFIRMASI (dump `petakanDialog()` user 2026-09-14, akun LUH PUTU SUKMAYANTI):** dialog "Formulir Reset Password" berisi **DUA `<input type="text">` yang keduanya `placeholder="Password"`** — field 1 = password baru (value kosong), field 2 = **email mitra yang SUDAH terisi** (mis. `ptsukma78@gmail.com`). Pembeda satu-satunya = `@` di `value` field email. Kontrol: `<button>Close`, `<a>Kembali`, `<a>Reset Password` — jadi "Reset Password" memang `<a>` (bukan `<button>`), dan `type=password` TIDAK dipakai (kedua field `type=text`). Pemilihan field dipusatkan di fungsi murni **`pilihFieldPassword(inputs)`** (diuji di `tests/test_reset_mitra_console.js` thd dump ini): kecualikan field email (type email / bertanda email / value ber-`@`), lalu PILIH (1 kandidat) / KOSONG (0 → biasanya belum render) / GANDA (>1 → stop).
- **Field dialog bisa mount TERLAMBAT (diperbaiki 2026-09-14):** run user berhenti `FIELD_PASSWORD_TIDAK_ADA` di akun ke-4 dgn "input di dialog:" KOSONG, padahal akun 1-3 sukses — kontainer `[role=dialog]` sudah tampak & teksnya cocok, tapi `<input>`-nya belum ter-render (animasi buka). `resetDiDialog()` sekarang **polling** (`tunggu(cariTarget, 8000, 300)`) sampai `pilihFieldPassword` mengembalikan `PILIH`, baru memutuskan; kalau sampai batas waktu tetap `KOSONG`/`GANDA` → tetap `FIELD_PASSWORD_TIDAK_ADA` (stop, tidak menebak). Jadi akun yang gagal transien ini otomatis diproses ulang di run berikut (belum `DIRESET_TERVERIFIKASI` → tidak dilewati).
- **⚠️ JANGAN di dashboard.** `/mitra/dashboard` punya kotak "Cari survei atau kegiatan..." yang beda; petakan pertama salah mendarat di sana (0 kandidat). Skrip menolak kalau `location.pathname` bukan `akun-mitra`, dan `kotakCari()` mensyaratkan placeholder memuat NIK/Email/Sobat/Username/Nama Lengkap & bukan survei/kegiatan.
- **Dialog Reset PW sudah dipetakan** lewat `resetMitra.petakanDialog()` (lihat bullet "Struktur dialog … TERKONFIRMASI" di atas). Tetap: `otomatis` wajib dimulai `limit:1` lalu verifikasi login mitra dgn password baru sebelum dibesarkan. Kalau suatu akun berhenti `FIELD_PASSWORD_TIDAK_ADA`/`TOMBOL_KONFIRMASI_AMBIGU` (mungkin struktur beda), user buka 1 dialog akun itu lalu `resetMitra.petakanDialog()` utk merekam struktur → sesuaikan `pilihFieldPassword`.
- **Akun GANDA dilewati, bukan menghentikan batch** (ketetapan user 2026-09-14): `putuskanStatus()` (fungsi murni, diuji) mengembalikan `LEWATI` utk `GANDA` selama opsi `lewatiGanda` (default `true`); akun itu tetap berstatus `GANDA` di audit + pesan "DILEWATI", dan daftarnya dicetak di akhir run. Aman karena `prosesEmail()` hanya mereset `COCOK`. Status galat lain di `STATUS_BERHENTI_SEGERA` TETAP menghentikan batch — jangan ikut dilonggarkan. `lewatiGanda:false` = perilaku lama.
- Gate `otomatis` = `sayaSudahMelihatDialog:true` (bukan lagi butuh manual-sukses; manual = human ketik, bukan alur yg diinginkan user). Stop-on-anomaly menjaga: 1 galat menghentikan batch, bukan 371. Logika parsing/pilih HARUS sama dgn `tests/test_reset_mitra_console.js`.

## Gap yang diketahui — perbaiki sebelum pakai ke backlog sungguhan

- **Jalur live-scrape (`scrape_source_blok2()`, dipakai HANYA kalau `--allow-live-scrape`) tidak scrape 13b1/13b2/13b3, rincian 24 (pekerja), maupun rincian 29 (kepemilikan modal).** Ini SUDAH TERTUTUP di jalur normal (tanpa `--allow-live-scrape`) karena `export_source.py` mengisi semua field ini dari data sumber asli (lihat `convert_manual_export.py`) — TAPI kalau suatu baris terpaksa fallback live-scrape, field-field ini kosong lagi seperti sebelumnya.
- Rincian 24 (pekerja) dari export TERNYATA cuma 2 pasang angka MARGINAL (`tk_laki`/`tk_pr` per gender, `tk_dibayar`/`tk_tdk_dibayar` per status bayar), BUKAN cross-tab lengkap. `convert_manual_export.py` menandai kasus ambigu (kedua gender sama2 punya pekerja dibayar) sbg status mengandung `"AMBIGU"` — `export_source.py` meneruskan ini ke `src.catatan_scrape`, tapi `fill_blok2.py` BELUM baca `src.catatan_scrape` utk stop/flag record itu secara eksplisit (cuma di-log). Review manual `audit_log.csv`/log kalau ada catatan ini sebelum submit batch besar.
- **Kodepos TIDAK perlu di-scrape** — nilainya sudah ada di file export mentah fasih-sm (`dataKey` `kodepos`, berpasangan dgn `var_desa` = kode desa 10 digit). Divalidasi silang 2026-09-07: **41 dari 41** entri `KODEPOS_BY_IDSUBSLS` cocok persis, 0 bentrok. `export_source.kodepos_dari_export()` memakainya sbg CADANGAN (config tetap menang) dan mengambil nilai **mayoritas per-DESA** dari seluruh file export, bukan dari satu file — karena export bisa kotor (satu keluarga mengisi `99999` di desa 5108030013 yang benarnya 81154; satu baris punya `var_desa` `5108000000` = kode kabupaten, bukan desa). Kodepos dialokasikan **per desa**, jadi pencocokan di level desa, bukan per banjar — semua SLS dalam satu desa memakai kodepos yang sama. Uji: `python tests/test_kodepos.py`.
- **Kolom `idsubsls` di `LKpenyalinan.csv` versi lokal saat ini MASIH dalam notasi ilmiah** (mis. "5.10808E+15") — jalankan `repair_idsubsls_from_xlsx.py` dgn export `.xlsx` yang sesuai SEBELUM dipakai `main.py`, kalau tidak SEMUA baris ikut ke-skip `SKIP_KODEPOS_TIDAK_DIKETAHUI`.
- Rincian 28b (`aset_lain_thn` × 10%) belum divalidasi eksplisit thd sumber — cocok scr kebetulan/logis di 3 sample, tidak dicek silang saat itu.
- `izin_edar_bpom` kondisional per kategori KBLI (tidak semua kategori menampilkannya) — sebagian file `export/*.converted.json` LAMA masih menyimpan nilainya sbg list mentah `[{"label":...}]` (belum lewat `_label()`), makanya `export_source.py` punya `_label_or_str()` defensif utk toleransi format lama ini.
- `FasihWebSession.save()` hanya coba selector `aria-label`/`title` yang mengandung "impan"; kalau tidak ketemu, cuma log warning dan lanjut (mengandalkan autosave per-field fasih-web) — bukan bug fatal, tapi verifikasi saat dry-run apakah save eksplisit ini pernah benar-benar diperlukan.
- Tidak ada test suite otomatis di repo. Kalkulasi & loader CSV pernah divalidasi manual pakai script sementara (tidak disimpan) — kalau mau test permanen, titik awal yang baik: assert `rupiah10`/`sum_rupiah10` thd nilai record 2 (33.600.008 → 3.360.001).

## Konvensi kode

- Semua log/komentar/docstring dalam Bahasa Indonesia — pertahankan.
- Locator Playwright berbasis label/teks (`get_by_label`, `get_by_text`), bukan koordinat pixel atau CSS selector rapuh.
- String label dipusatkan di `config.py -> dict L` — kalau tampilan fasih-web berubah, cukup edit di situ, jangan hardcode string baru langsung di file lain.
- `FieldNotFound` (di `fasih_web.py`) khusus utk "selector tidak ketemu", di-catch di `main.py -> process_one_row()` supaya 1 record gagal tidak menghentikan batch. Pertahankan pola ini kalau menambah step baru.
- Setiap kegagalan step (`FasihWebSession._fail()`) otomatis screenshot ke `./log_screenshots/` — cek folder ini duluan kalau debug dry-run, sebelum baca ulang seluruh kode.
- `audit_log.csv` & `log_screenshots/` adalah output runtime (lihat `.gitignore`), bukan source — begitu juga file CSV backlog apa pun, karena isinya data pribadi responden (nama, NIK, dll).
