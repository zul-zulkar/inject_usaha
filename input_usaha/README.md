# input_usaha — input usaha ke fasih-web

Membaca sheet input usaha (format tahap 2, templat [`templates/input_usaha.xlsx`](../templates/input_usaha.xlsx)),
memeriksanya offline, lalu per baris: **buat dokumen → isi PENGANTAR, SE2026-P, BLOK II → cek
ringkasan (GALAT harus 0) → kirim** (hanya dengan `--submit` + ketik `YA`). Playwright, browser
terbuka (headless ditolak fasih-web). Butuh VPN.

Semua dokumen dibuat di **satu subsls oleh satu akun PPL** (`--subsls-tunggal`/`--akun-tunggal`);
wilayah asli tiap baris dicatat di audit dan dipindah belakangan dengan
[`fasih_sm/pindah_wilayah`](../fasih_sm/pindah_wilayah/). Akun itu harus punya assignment **PAPI**
di subsls tersebut ([`fasih_sm/ganti_moda`](../fasih_sm/ganti_moda/)).

## Langkah

**1. Periksa data** — tanpa browser, beberapa detik. Rincian per baris →
`hasil/cek_input.csv`; laporan per sel berwarna untuk dibagikan ke PPL → `hasil/kontrol_kualitas.xlsx`.

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --cek
python input_usaha/kontrol_kualitas.py --sumber bahan/input_usaha.xlsx --per-ppl
```

Baris yang ditolak di sini tidak pernah dibuka di browser. Aturan pemeriksaan & penggantian nilai:
[`docs/FORMAT_INPUT_USAHA.md`](../docs/FORMAT_INPUT_USAHA.md).

**2. Dry-run satu baris** — mengisi tapi TIDAK mengirim; tinjau dokumennya di fasih-web.

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --baris 2
```

**3. Kirim** — satu perintah untuk seluruh rentang PC ini; minta ketik `YA` sekali.

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --dari 2 --sampai 500 --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda --submit
```

Urutan kerja otomatis: draft yang ditandai galat oleh server dulu, lalu dokumen yang sudah ada,
baru baris yang belum punya dokumen. Menjalankan ulang perintah yang sama **aman** — dokumen yang
sudah ada dibuka lewat URL di audit, tidak dibuat ulang.

**4. Tanpa ditunggui (malam hari)** — `otomatis.py` menjalankan perintah langkah 3 berulang
sampai tuntas, mengetik `YA` sendiri, dan pindah ke akun cadangan kalau kena limit permintaan.

```bash
python input_usaha/otomatis.py --sumber bahan/input_usaha.xlsx --dari 2 --sampai 500 --akun EMAIL --subsls SUBSLS --akun-cadangan EMAIL2 --subsls-cadangan SUBSLS2 --label-pc _pc1
```

Log: `hasil/log_otomatis<label>.txt`. Berhenti rapi di antara baris: buat berkas kosong
`STOP_GABUNGAN` (semua batch) atau `STOP_<email>` di folder proyek.

**5. Pantau & bereskan** — offline kecuali `sinkron_list`.

```bash
python input_usaha/rangkum_audit.py --sumber bahan/input_usaha.xlsx          # progres per baris + alasan tidak dikerjakan
python input_usaha/sinkron_list.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS   # bandingkan dgn server (+ --tulis)
python input_usaha/bersihkan_error.py --sumber bahan/input_usaha.xlsx        # kelompokkan sisa error + perintah perbaikannya
```

## Satu batch = satu audit

Audit bawaan `audit/audit_log_gabungan.csv`. Sheet/batch lain memakai audit sendiri, dengan
`--audit` yang **sama di setiap perintah** batch itu (termasuk `sinkron_list`, `rangkum_audit`,
`approve_pml`, `pindah_wilayah`, `hapus_ganda`):

```bash
python input_usaha/jalankan.py --sumber bahan/input_tahap2.xlsx --audit audit/batch21 --akun-tunggal EMAIL --subsls-tunggal SUBSLS --lewati-selesai --submit
```

Baris pertama keluaran selalu `Audit: <lokasi>`. Kalau audit yang dipakai jauh kurang mengenal
sheet itu dibanding audit lain di `audit/`, perintah **berhenti** (lupa `--audit` = dokumen ganda);
batch yang memang baru: tambah `--audit-baru`. Perintah juga berhenti kalau kolom "ID Dokumen FASIH"
sheet memuat ID yang tidak dikenal audit aktif tapi dikenal audit lain (sheet sudah digabung, audit
belum): gabungkan audit dulu (`antar_pc/README.md` bagian 2). Pesan keduanya diawali
`⛔ AUDIT TIDAK COCOK`; `otomatis.py` lalu berhenti (kode 5), tidak mengulang.

## Opsi penting

| Opsi                                                            | Guna                                                                                   |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `--cek`                                                       | periksa saja, tanpa browser                                                            |
| `--submit`                                                    | benar-benar mengirim (tanpa ini = dry-run)                                             |
| `--baris 2,5,10-20` / `--dari N --sampai M` / `--limit N` | pilih baris (nomor baris sheet, judul = 1)                                             |
| `--akun-tunggal` / `--subsls-tunggal`                       | akun PPL & subsls tempat semua dokumen dibuat                                          |
| `--sinkron-dulu`                                              | baca daftar dokumen server dulu → dokumen buatan PC lain dikenali, bukan dibuat ulang |
| `--lewati-selesai`                                            | lewati baris yang sudah tuntas menurut audit                                           |
| `--izinkan-wilayah-beda`                                      | jangan berhenti kalau dokumen lama ada di subsls wadah lain milik akun yang sama       |
| `--hanya-galat`                                               | kerjakan hanya draft yang ditandai galat oleh server                                   |
| `--koordinat otomatis\|wajib\|kirim`                            | baris tanpa koordinat: DRAFT (bawaan) / ditolak / tetap dikirim                        |
| `--audit BERKAS\|FOLDER` / `--audit-baru`                    | audit batch lain (lihat di atas)                                                       |
| `--coba-terkunci`                                             | kerjakan lagi`DOKUMEN_TERKUNCI` setelah admin/PML membukanya                         |
| `--maks-tanpa-url N`                                          | berhenti setelah N dokumen tanpa URL (bawaan 3; 0 = tidak pernah)                      |
| `--dump-dom`                                                  | simpan peta dataKey tiap section ke`hasil/log_screenshots/` (memperbaiki selektor)   |

Daftar lengkap: `python input_usaha/jalankan.py --help`.

## Status audit yang perlu tindakan

| Status                                                             | Tindakan                                                                                                      |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `SKIP_DATA_*`                                                    | data sheet ditolak pemeriksaan — betulkan sel (lihat`hasil/cek_input.csv`)                                 |
| `DRAFT_TANPA_KOORDINAT`                                          | isi Latitude/Longitude di sheet (atau[`koordinat/`](../koordinat/)), jalankan ulang dgn `--lewati-selesai` |
| `SKIP_GALAT_PERLU_REVIEW` / `SKIP_GALAT_TIDAK_TERATASI`        | ada GALAT di form — baca`error_message`, isi manual kalau perlu                                            |
| `DOKUMEN_TANPA_URL_PERLU_CEK`                                    | dokumen mungkin terbuat tanpa URL; baris dilewati.`sinkron_list.py --tulis` memutuskan buka/buat ulang      |
| `DOKUMEN_TERKUNCI`                                               | dokumen read-only; minta admin/PML, lalu`--coba-terkunci`                                                   |
| `TERKIRIM_BELUM_TERVERIFIKASI`                                   | toast terkirim tanpa bukti server — pastikan dgn`sinkron_list.py`                                          |
| `STOP_WILAYAH_DOKUMEN_BEDA` / `STOP_SUBSLS_TIDAK_BISA_DIPILIH` | batch berhenti: subsls/wilayah salah — periksa, jangan dipaksa                                               |
| `SKIP_DOKUMEN_BELUM_ADA`                                         | subsls belum punya assignment PAPI →`fasih_sm/ganti_moda`                                                  |
| `ERROR_AKUN_SALAH` / `ERROR_LOGIN`                             | sesi nyangkut / password beda dgn`FIXED_PASSWORD` → jalankan ulang / `reset_mitra`                       |
| `ERROR_FIELD_NOT_FOUND`                                          | tampilan form berubah →`--dump-dom`, perbaiki `inti/config.py` (`DK`/`SEL`/`L`)                    |

Kolom `review_disarankan` di audit mencatat setiap nilai yang diganti/diasumsikan skrip.

## Keluaran (`input_usaha/hasil/`, boleh dihapus)

`cek_input.csv`, `kontrol_kualitas.xlsx` (+ `kontrol_kualitas_per_ppl/`), `rangkum_audit.csv`,
`bersihkan_error.csv`, `sinkron_list.csv`, `list_api_<akun>.json` (daftar dokumen server),
`dokumen_tanpa_url.csv`, `log_otomatis*.txt`, `log_screenshots/`, `.proses_<akun>.lock`.
Yang **tidak** di sini: audit (`audit/`) dan kolom "ID Dokumen FASIH" yang ditulis balik ke sheet.

## Kode

| Berkas                                                  | Fungsi                                                                                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jalankan.py`                                         | pintu masuk (perintah langkah 1-3)                                                                                                                      |
| `mesin.py`                                            | orkestrasi: muat & periksa sheet, audit, kunci proses per akun, sesi login,`process_one_row` (buat/buka → isi → ringkasan → kirim), pengaman audit |
| `isi_blok2.py`                                        | mengisi BLOK II, KETERANGAN PEMBERI JAWABAN, CATATAN dari satu baris                                                                                    |
| `otomatis.py`                                         | pembungkus jalan-ulang + akun cadangan                                                                                                                  |
| `sinkron_list.py`                                     | baca daftar dokumen server (READ-ONLY) → laporan /`--tulis` ke audit                                                                                 |
| `kontrol_kualitas.py`                                 | laporan kualitas sumber per sel (aturan = pemeriksaan`--cek`)                                                                                         |
| `rangkum_audit.py`, `bersihkan_error.py`            | progres per baris & klasifikasi sisa error                                                                                                              |
| `tulis_id_sumber.py`                                  | isi kolom "ID Dokumen FASIH" sheet dari audit                                                                                                           |
| `kodepos_desa.py`                                     | susun`KODEPOS_BY_DESA` di config lokal dari sheet lama                                                                                                |
| [`../inti/tahap2_loader.py`](../inti/tahap2_loader.py) | pemetaan kolom sheet + pemeriksaan & penggantian nilai                                                                                                  |
| [`../inti/fasih_web.py`](../inti/fasih_web.py)         | semua klik/isi di fasih-web (login, buat dokumen, geotag, KBLI, kirim)                                                                                  |
| [`../inti/config.py`](../inti/config.py)               | nilai bawaan & aturan`TAHAP2_*`, selektor `DK`/`SEL`/`L`                                                                                        |

Uji: `python tests/test_mesin.py`, `tests/test_isi_blok2.py`, `tests/test_tahap2_loader.py`,
`tests/test_sinkron_list.py`, `tests/test_kontrol_kualitas.py`, `tests/test_otomatis.py`.
