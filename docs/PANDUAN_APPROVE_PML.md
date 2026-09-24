# Panduan Approve PML (fasih-web)

Meng-approve, sebagai **PML (Pengawas)**, dokumen yang sudah **dikirim PPL** — biasanya hasil input
otomatis `main_gabungan.py` / `main_tahap2.py`. Sama dengan membuka dokumen di fasih-web lalu klik
**Approve** di bar bawah → **Approve** di dialog "Konfirmasi Approve".

```text
input & kirim (PPL) ──> APPROVE (PML, panduan ini) ──> pindah wilayah (fasih-sm)
```

- **Cara:** Playwright — jendela Chromium terbuka sendiri, login otomatis sebagai akun PML.
  Headless tidak dipakai (fasih-web menolak browser headless).
- **Yang di-approve:** hanya dokumen yang, **tepat sebelum diklik**, statusnya di server
  `SUBMITTED BY Pencacah`. Pada sumber audit & file rencana, dokumen itu juga harus dibuat/diubah
  oleh akun **PPL yang diminta** — dokumen PPL lain di subsls yang sama tidak pernah disentuh.
- **Default = dry-run.** Tanpa `--eksekusi` skrip hanya membaca status dan memastikan tombol
  Approve ada; tidak ada yang diklik.
- **Hasil:** `audit_approve_pml.csv` di root proyek (ditambah tiap run, tidak ditimpa). Berkas ini
  yang dibaca `pindah_wilayah.py --dari-approve` sesudahnya.

> Cara kerja — **satu dokumen per satu dokumen**:
>
> 1. **Baca status** dokumen lewat API fasih-web (tanpa membuka form): harus `SUBMITTED BY Pencacah`
>    dan (kalau dicek) pembuatnya = akun PPL. Sudah APPROVED → dilewati.
> 2. **Buka dokumen** (URL entry yang sama dengan PPL) sampai form tampil; halaman "Terjadi
>    Kesalahan (504)" dibuka ulang maks 3x.
> 3. Tombol **Approve** di bar bawah harus tepat satu → klik → dialog **Konfirmasi Approve** harus
>    muncul dengan tepat satu tombol Approve → klik.
> 4. **Verifikasi:** status di API dibaca ulang tiap 2 detik sampai jadi `APPROVED BY Pengawas`
>    (maks 60 detik). Toast "berhasil" **bukan** bukti — yang dicatat `APPROVED_TERVERIFIKASI`
>    hanya yang terbukti di server.
>
> Ada yang janggal (dialog tidak muncul, tombol ganda, status tidak berubah, akun berganti) →
> **seluruh run berhenti**, tidak menebak.

⚠️ **Anggap approve tidak bisa dibatalkan.** Di bar bawah dokumen yang sudah di-approve memang
muncul tombol "Revoke", tapi skrip tidak pernah memakainya dan dampaknya belum pernah dicoba.
Selalu dry-run dulu, lalu eksekusi **satu** dokumen dan periksa sendiri sebelum massal.

---

## Pilih sumber dokumen

| Sumber | Dipakai kalau | Perintah inti | Ikut pindah wilayah? |
| --- | --- | --- | --- |
| **Audit input** (alur utama) | Dokumen hasil input skrip; **satu PML** meng-approve dokumen **satu PPL** | `--akun-pml … --akun-ppl …` | **Ya** |
| **File rencana** | Banyak PML sekaligus, **id dokumen sudah diketahui** (mis. hasil query) | `--rencana rencana.csv` | Tidak |
| **Salinan tabel fasih-sm** | Banyak PML sekaligus, yang ada cuma **kode identitas** dari halaman Data fasih-sm | `--daftar submit.xlsx` | Tidak |

"Ikut pindah wilayah" = hasilnya dikenali `pindah_wilayah.py --dari-approve`, karena hanya sumber audit
yang membawa kunci baris sheet input usaha. Kalau dokumennya nanti mau dipindah wilayah, pakai
**sumber audit**.

---

## 0. Persiapan (sekali)

- **VPN kantor aktif.**
- Python + Playwright sudah terpasang (`pip install -r requirements.txt`, `playwright install chromium`).
  Semua perintah dijalankan **dari root proyek**.
- **Password PML** di `inti/config_lokal.py` → `FIXED_PASSWORD` (salin dari
  `templates/config_lokal.contoh.py` kalau belum ada). Login otomatis memakai password ini untuk
  semua akun. Password PML berbeda → pakai `--login-manual` (lihat [Login & sesi](#login--sesi)).
- **Akun PML** yang tepat: di halaman Data fasih-sm, dokumen yang sudah dikirim PPL menampilkan
  akun pengawasnya di kolom **Petugas Saat Ini**.
- Dokumen harus **mode PAPI**. Dokumen hasil input skrip memang PAPI (lihat `PANDUAN_UBAH_MODA.md`).
  Dokumen **CAPI** (dari aplikasi mobile) tidak bisa dibuka lewat fasih-web → `SKIP_TIDAK_ADA_AKSES`.
- **Sumber audit:** `audit_log_gabungan.csv` harus memuat dokumen PPL itu. Kalau input dijalankan di
  beberapa PC, satukan dulu auditnya (`docs/PANDUAN_GABUNG_AUDIT.md`) atau jalankan
  `input_gabungan/sinkron_list.py … --tulis` supaya dokumen buatan PC lain tercatat.

---

## 1. Approve dokumen satu PPL — sumber audit (alur utama)

Target = semua dokumen di `audit_log_gabungan.csv` yang `akun_login`-nya = `--akun-ppl` dan punya
URL dokumen (dokumen yang tercatat `DOKUMEN_DIHAPUS` diabaikan). Dokumen yang masih draft ikut
dibaca tapi otomatis dilewati karena statusnya bukan `SUBMITTED BY Pencacah`.

### 1a. Lihat rencana (tanpa browser)

```bash
python approve_pml/approve_pml.py --akun-pml pml.contoh@gmail.com --akun-ppl ppl.contoh@gmail.com --cek
```

```text
DRY-RUN (tanpa klik Approve) — 1 PML, 120 dokumen:
  1. pml.contoh@gmail.com  — 120 dokumen, PPL {'ppl.contoh@gmail.com': 120}
```

`Tidak ada dokumen akun … di audit_log_gabungan.csv` → akun PPL salah ketik, atau audit PC lain belum
disatukan.

### 1b. Dry-run (browser terbuka, tidak ada yang diklik)

```bash
python approve_pml/approve_pml.py --akun-pml pml.contoh@gmail.com --akun-ppl ppl.contoh@gmail.com
```

Tambah `--limit 5` untuk mencoba beberapa dokumen dulu. Contoh keluaran:

```text
===== PML 1/1: pml.contoh@gmail.com — 120 dokumen =====
Dokumen list subsls PPL yg TIDAK di audit: 3 {'SUBMITTED BY Pencacah': 3} — tidak diproses (pakai --termasuk-di-luar-audit)
Target: 120 dokumen.

[1/120] DRY_RUN_SIAP_APPROVE         0a1b2c3d baris   12 WARUNG CONTOH (I KETUT CONTOH) | tombol Approve ada (tidak diklik)
[2/120] SUDAH_APPROVED               4e5f6a7b baris   13 TOKO CONTOH (NI LUH CONTOH)
[3/120] SKIP_STATUS_DRAFT            8c9d0e1f baris   14 KIOS CONTOH (I MADE CONTOH) | DRAFT
...
Ringkasan PML pml.contoh@gmail.com: {'DRY_RUN_SIAP_APPROVE': 97, 'SUDAH_APPROVED': 11, ...}
```

(Teks status draft persisnya mengikuti server — lihat kolom `pesan`.)

Yang ideal: `DRY_RUN_SIAP_APPROVE`. Yang lain → [Arti status](#arti-status).

### 1c. Eksekusi SATU dokumen dulu (wajib)

```bash
python approve_pml/approve_pml.py --akun-pml pml.contoh@gmail.com --akun-ppl ppl.contoh@gmail.com --eksekusi --limit 1
```

1. Ketik **`YA`** saat diminta.
2. Terminal harus menampilkan `APPROVED_TERVERIFIKASI` untuk dokumen itu.
3. **Periksa sendiri** di fasih-web (akun PML) atau fasih-sm: status dokumen `APPROVED BY Pengawas`,
   dokumen PPL lain tidak berubah.

### 1d. Sisanya

```bash
python approve_pml/approve_pml.py --akun-pml pml.contoh@gmail.com --akun-ppl ppl.contoh@gmail.com --eksekusi
```

- Aman dijalankan berulang: dokumen yang sudah APPROVED dilewati (`SUDAH_APPROVED`, tidak ditulis
  ulang ke audit). Mencicil: `--limit 50`.
- Kalau terputus (VPN, laptop tidur), jalankan perintah yang sama lagi.
- PPL lain dengan PML yang sama: ulangi 1a–1d dengan `--akun-ppl` berikutnya.

### Dokumen yang tidak tercatat di audit

Skrip juga mencari list PENDATAAN PML per subsls tempat dokumen PPL dibuat, lalu **melaporkan**
dokumen yang tidak ada di audit (baris "Dokumen list subsls PPL yg TIDAK di audit"). Untuk ikut
memprosesnya:

```bash
python approve_pml/approve_pml.py --akun-pml pml.contoh@gmail.com --akun-ppl ppl.contoh@gmail.com --termasuk-di-luar-audit
```

Pengaman pembuat dokumen tetap berlaku: dokumen PPL lain di subsls itu jadi `SKIP_BUKAN_PPL`.
Dokumen ini tidak punya kunci baris sheet, jadi **tidak ikut pindah wilayah `--dari-approve`** —
lebih baik catat dulu ke audit lewat `sinkron_list.py --tulis`, lalu approve tanpa flag ini.

---

## 2. Banyak PML sekaligus — file rencana (`--rencana`)

File `.csv`/`.xlsx` (sheet pertama) dengan kolom wajib **`Email PML`**, **`Email PPL`**,
**`assignment_id`** (= id dokumen, segmen URL sebelum `/entry`). Kolom `data1`, `code_identity`,
`assignment_status_alias`, `PML`, `PPL` boleh ada (hanya untuk tampilan). Contoh:
[`templates/rencana_approve.contoh.csv`](../templates/rencana_approve.contoh.csv).

```bash
python approve_pml/approve_pml.py --rencana rencana_approve.csv --cek                   # 0. rencana per PML, tanpa browser
python approve_pml/approve_pml.py --rencana rencana_approve.csv                         # 1. dry-run semua PML
python approve_pml/approve_pml.py --rencana rencana_approve.csv --eksekusi --limit 1    # 2. 1 dokumen PER PML
python approve_pml/approve_pml.py --rencana rencana_approve.csv --eksekusi              # 3. sisanya
```

- Dokumen dikelompokkan per `Email PML` (urut kemunculan di file). Tiap PML: login → proses →
  logout → PML berikutnya. `YA` cukup diketik **sekali** untuk semua PML.
- Tiap dokumen tetap wajib dibuat/diubah oleh `Email PPL` **baris itu**.
- `--limit` berlaku **per PML**. Batasi PML tertentu: `--akun-pml a@x.com --akun-pml b@y.com`
  (atau dipisah koma).
- Baris tanpa id/email valid dilewati & dilaporkan. Id yang muncul dua kali dengan pasangan PML/PPL
  **berbeda** digugurkan seluruhnya (tidak ditebak).
- Id yang status terakhirnya di `audit_approve_pml.csv` sudah `APPROVED_TERVERIFIKASI` dilewati
  tanpa login. Cek ulang semuanya: `--abaikan-audit-approve`.

⚠️ Pastikan isinya dokumen **PAPI**. Pada uji 2026-09-15, 765 dari 768 dokumen hasil query berupa
dokumen CAPI dan semuanya `SKIP_TIDAK_ADA_AKSES`.

---

## 3. Banyak PML sekaligus — salinan tabel fasih-sm (`--daftar`)

Untuk saat yang tersedia hanya tabel halaman **Data** fasih-sm (Kode Identitas, Nama, …, Status,
Mode, Petugas Saat Ini) yang disimpan sebagai `.xlsx`/`.csv`. Judul kolom boleh bergeser: skrip
mencari sel `PAPI`/`CAPI` (kolom Mode) sebagai patokan — sel sebelumnya dibaca sebagai Status,
sel sesudahnya sebagai Petugas Saat Ini (= akun PML).

```bash
python approve_pml/approve_pml.py --daftar submit.xlsx --cek
python approve_pml/approve_pml.py --daftar submit.xlsx
python approve_pml/approve_pml.py --daftar submit.xlsx --eksekusi --limit 1
python approve_pml/approve_pml.py --daftar submit.xlsx --eksekusi
```

- Yang diproses hanya baris **PAPI** + status **submitted by pencacah** + Petugas Saat Ini berupa
  email; sisanya dilaporkan di awal.
- File tidak memuat id dokumen, jadi setelah login tiap PML, list PENDATAAN dicari per subsls
  (16 digit awal kode) dan kode identitas dicocokkan **persis** untuk mendapatkan id-nya.
- File juga tidak memuat email PPL, jadi pembuat dokumen **tidak dicek** — hanya dicatat di kolom
  `akun_ppl` audit. Pengaman yang tersisa: dokumen di list harus PAPI & Petugas Saat Ini = PML yang
  sedang login.
- Kode yang status terakhirnya `APPROVED_TERVERIFIKASI`/`SUDAH_APPROVED` di audit dilewati tanpa
  login. `--akun-pml`, `--limit` (per PML), `--abaikan-audit-approve` sama dengan `--rencana`.

---

## Login & sesi

- **Satu PML** (sumber audit, atau file berisi satu PML): sesi disimpan di
  `.sesi_fasih_web_<akun>.json` dan dipakai lagi di run berikutnya tanpa login ulang; tidak logout
  di akhir. Sesi milik akun lain otomatis diputus.
- **Banyak PML:** tiap PML memakai browser context **baru** (cookie SSO kosong, jadi tidak mungkin
  "tembus" sebagai PML sebelumnya), login dengan `FIXED_PASSWORD`, lalu logout + tutup context.
  ±25 detik per akun.
- Akun yang aktif setelah login **wajib terbaca = PML yang diminta**; kalau tidak → berhenti
  (`AKUN SALAH/TIDAK TERVERIFIKASI`). Dicek lagi tiap 10 dokumen.
- Login gagal karena gangguan diulang maks 3x (jeda 30 detik). Tetap gagal → PML itu dilewati
  (`ERROR_LOGIN_PML`), PML berikutnya lanjut.
- **`--login-manual`**: skrip membuka halaman login lalu menunggu Anda login sendiri di jendela
  browser (maks 15 menit per PML). Pakai kalau password PML tidak sama dengan `FIXED_PASSWORD`.

File sesi & `audit_approve_pml.csv` sudah di `.gitignore` — jangan di-commit.

---

## Setelah approve: pindah wilayah

```bash
python pindah_wilayah/pindah_wilayah.py --sumber input_usaha.xlsx --dari-approve --console
```

Langkah lengkapnya di [`PANDUAN_PINDAH_WILAYAH.md`](PANDUAN_PINDAH_WILAYAH.md). Yang ikut hanya
dokumen yang pernah **`APPROVED_TERVERIFIKASI`** di `audit_approve_pml.csv` dan berasal dari sumber
audit.

⚠️ Dokumen yang sudah APPROVED **sebelum** skrip ini dijalankan (di-approve manual, atau di-approve
tapi baru terbaca di run berikutnya) tercatat `SUDAH_APPROVED` dan tidak ditulis ke audit, jadi
**tidak ikut `--dari-approve`**. Untuk dokumen seperti itu pakai "Alur lama: dua tahap" di panduan
pindah wilayah.

---

## Opsi

| Opsi | Arti |
| --- | --- |
| `--akun-pml` | Sumber audit: akun PML (wajib, tepat satu). `--rencana`/`--daftar`: saring PML yang diproses (boleh diulang / dipisah koma) |
| `--akun-ppl` | Sumber audit: akun PPL (`akun_login` di `audit_log_gabungan.csv`) |
| `--rencana FILE` / `--daftar FILE` | Sumber banyak PML (pilih salah satu) |
| `--cek` | Tampilkan rencana per PML lalu keluar, tanpa browser |
| `--eksekusi` | **Sungguhan** klik Approve (minta ketik `YA` sekali) |
| `--ya` | Lewati pertanyaan `YA` — hanya kalau izinnya memang sudah diberikan |
| `--limit N` | Maks dokumen yang dibuka untuk di-approve/di-dry-run **per PML**; yang dilewati (`SKIP_*`, `SUDAH_APPROVED`) tidak dihitung |
| `--termasuk-di-luar-audit` | Sumber audit: ikut proses dokumen list subsls PPL yang tidak ada di audit |
| `--abaikan-audit-approve` | `--rencana`/`--daftar`: cek ulang juga dokumen yang di audit sudah approved |
| `--login-manual` | Tunggu manusia login di jendela browser (tiap PML) |
| `--maks-error-beruntun N` | Berhenti setelah N status `ERROR_*` berturut-turut (default 3) |
| `--assignment-id` | Segmen URL list PENDATAAN (default dari config, sama dengan input) |

---

## Arti status

Kolom `status` di `audit_approve_pml.csv` dan di terminal.

| Status | Arti | Tindakan |
| --- | --- | --- |
| `DRY_RUN_SIAP_APPROVE` | Status SUBMITTED, pembuat cocok, tombol Approve ada (tidak diklik) | Boleh `--eksekusi` |
| `APPROVED_TERVERIFIKASI` | Sudah diklik & status server terbukti APPROVED | Selesai |
| `SUDAH_APPROVED` | Dokumen memang sudah approved (termasuk tombol Approve tidak ada karena sudah approved) | Selesai. Hanya `--daftar` yang menulisnya ke audit |
| `SKIP_STATUS_…` | Status bukan `SUBMITTED BY Pencacah` — mis. masih draft atau di-reject (`SKIP_STATUS_REJECTED_BY_PENGAWAS`) | Kirim dulu dari PPL, jalankan lagi |
| `SKIP_BUKAN_PPL` | Pembuat/pengubah dokumen bukan akun PPL yang diminta | Tidak di-approve. Cek `--akun-ppl` atau approve manual |
| `SKIP_TIDAK_ADA_AKSES` | Server menolak akun PML ini membuka dokumen ("Anda tidak memiliki akses ke dalam survey" / HTTP 403) — biasanya dokumen **CAPI** | Approve lewat jalur lain (aplikasi FASIH PML) |
| `SKIP_DETAIL_TIDAK_TERBACA` | Status dokumen tidak terbaca walau sudah diulang | Jalankan lagi nanti |
| `SKIP_KODE_TIDAK_DI_LIST` | (`--daftar`) kode tidak ada di list PENDATAAN PML | Cek kode / PML-nya |
| `SKIP_KODE_GANDA` | (`--daftar`) >1 dokumen berkode sama | Approve manual |
| `SKIP_BUKAN_PML_SAAT_INI` | (`--daftar`) petugas saat ini di list bukan PML yang login | Perbarui file / cek alokasi |
| `SKIP_MODE_BUKAN_PAPI` | (`--daftar`) mode di list bukan PAPI | Jalur lain |
| `SKIP_LIST_TIDAK_TERBACA` | (`--daftar`) list subsls gagal dibaca | Jalankan lagi (diulang otomatis) |
| `ERROR_FORM_TIDAK_MOUNT` | Form tidak tampil setelah 3x dibuka (biasanya halaman "Terjadi Kesalahan (504)") | Jalankan lagi nanti; 3x beruntun → berhenti |
| `ERROR_TOMBOL_APPROVE_TIDAK_ADA` | Tombol Approve tidak tampil 30 detik & status belum approved | Buka dokumennya manual, lihat screenshot |
| `ERROR_LOGIN_PML` | Login PML gagal 3x / akun salah | Cek VPN & password, atau `--login-manual` |
| `STOP_DIALOG_TIDAK_MUNCUL` ⛔ | Dialog "Konfirmasi Approve" tidak muncul & status tidak berubah | Cek tampilan fasih-web; jangan dipaksa |
| `STOP_TOMBOL_AMBIGU` ⛔ | Tombol Approve di bar/dialog bukan tepat satu | Tampilan berubah — laporkan |
| `APPROVE_TIDAK_TERVERIFIKASI` ⛔ | Sudah diklik tapi status server tetap bukan APPROVED setelah 60 detik | Cek manual dokumen itu sebelum lanjut |
| `ERROR_TAK_TERDUGA` ⛔ | Galat program di tengah satu PML | Baca pesannya, laporkan |

⛔ = seluruh run berhenti. Run juga berhenti kalau akun aktif berganti di tengah jalan
(`STOP_AKUN_BERUBAH`) atau ada 3 status `ERROR_*` berturut-turut (VPN putus / sesi habis).

Screenshot setiap kegagalan ada di `log_screenshots/` (`<waktu>_approve_….png`).

---

## Masalah umum

- **Hampir semua dokumen `SKIP_TIDAK_ADA_AKSES`:** dokumennya CAPI. fasih-web (web-entry) hanya
  membuka dokumen PAPI; tidak ada yang bisa diubah dari sisi skrip.
- **Banyak `SKIP_STATUS_…` draft:** dokumen belum terkirim. Selesaikan input/kirimnya dulu
  (`--lewati-selesai --submit` di `main_gabungan.py`), lalu approve lagi.
- **`ERROR_LOGIN_PML` / "AKUN SALAH":** password PML tidak sama dengan `FIXED_PASSWORD`, atau
  sesi SSO lama nyangkut. Pakai `--login-manual`, atau hapus `.sesi_fasih_web_<akun>.json` lalu ulangi.
- **Dokumen yang jelas sudah dikirim tidak muncul di rencana:** belum tercatat di audit PC ini.
  Satukan audit / `sinkron_list.py --tulis`, atau lihat baris "Dokumen list subsls PPL yg TIDAK di audit".
- **Salah approve:** skrip tidak membatalkan. Tangani manual di fasih-web (akun PML).

---

## Uji offline

```bash
python tests/test_approve_pml.py
```

Menguji logika pemilihan target, pembacaan file rencana/daftar, pengaman status & pembuat dokumen,
dan alur ganti akun antar-PML dengan browser tiruan — tanpa VPN.
