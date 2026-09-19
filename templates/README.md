# Templat

Titik awal untuk pengguna baru. Semua file di sini **kosong atau fiktif** — jangan pernah
mengisi data sungguhan di folder ini (folder ini ikut git). Salin dulu ke root proyek,
baru diisi; file data di root otomatis diabaikan git.

## `config_lokal.contoh.py` — pengaturan milik Anda

```bash
copy templates\config_lokal.contoh.py inti\config_lokal.py      # Windows
cp templates/config_lokal.contoh.py inti/config_lokal.py        # Linux/macOS
```

Isi minimal `FIXED_PASSWORD` dan `KODE_KAB`. Setiap nama yang Anda definisikan di situ
menimpa nilai di `inti/config.py`.

## `input_usaha.kosong.xlsx` & `input_usaha.contoh.xlsx` — format standar input usaha

Satu baris = satu usaha = satu dokumen, untuk **jenis usaha apa pun**. Spesifikasi lengkap:
[`docs/FORMAT_STANDAR_INPUT_USAHA.md`](../docs/FORMAT_STANDAR_INPUT_USAHA.md).

| File | Isi |
| --- | --- |
| `input_usaha.kosong.xlsx` | **Benar-benar kosong**: hanya tab `input_usaha` berisi baris judul semua kolom (termasuk kolom opsional 13d/13e/13f, 19, 20), dropdown opsi form, dan format teks untuk kolom kode. Tempat menyalin hasil pendataan lapangan. |
| `input_usaha.contoh.xlsx` | Sama, ditambah tab `petunjuk` (wajib/bersyarat/opsional & isi tiap kolom), `contoh` (dua baris fiktif: warung perdagangan & usaha produksi keripik), dan `Nama Wilayah` (opsional). |

Salin salah satunya ke root proyek sebagai `input_usaha.xlsx` (atau unggah ke Google Sheets untuk
diisi bersama, lalu *File → Download → Microsoft Excel*). Isi tab `input_usaha` mulai baris 2;
judul kolom jangan diubah (kolom dikenali dari awalan judulnya, urutan bebas). Nama lama
(`Agenda.xlsx`, tab `gabungan`) tetap diterima.

Nilai = **jawaban final** per rincian kuesioner (diketik apa adanya). Teks opsi harus persis
sama dengan dropdown (mis. `2. Tidak`). Dengan **mode murni** (`GABUNGAN_MODE_MURNI = True`,
sudah menyala di `config_lokal.contoh.py`) tidak ada isian yang dibuat skrip: kolom berstatus
"bersyarat" wajib diisi kalau form memunculkan rinciannya. Periksa tanpa browser:

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --cek
```

Kedua file dibangkitkan oleh `buat_templat_input_usaha.py` dari daftar kolom & opsi di
`inti/gabungan_loader.py`. Kalau judul kolom atau opsi form berubah, perbarui loader lalu:

```bash
python templates/buat_templat_input_usaha.py
```

(skrip itu juga memverifikasi bahwa kedua baris contohnya lolos pemeriksaan offline, di mode
normal maupun mode murni).

## `salin_dokumen_sumber.contoh.csv` — alur salin dari dokumen sumber

Header saja. Dipakai `input_fasihweb/main.py --csv` — alur khusus **salin dari dokumen
sumber** (usaha pecahan yang jawabannya disalin dari dokumen lain di fasih-sm). Alur ini juga
butuh file export fasih-sm per baris (`export/{No}_{assignment_id}.converted.json`) — lihat
`docs/PANDUAN_EKSPOR_MANUAL.md`. Untuk data hasil pendataan lapangan, pakai format standar di atas.

## `daftar_idsubsls.contoh.txt` — daftar wilayah

Satu idsubsls 16 digit per baris (`#` = komentar), berawalan `KODE_KAB`. Untuk:

```bash
python buka_wilayah/buka_wilayah.py --daftar daftar_buka_wilayah.txt --console
python tandai_selesai/tandai_selesai.py --daftar daftar_tandai_selesai.txt --console
```

## `daftar_kode_identitas.contoh.txt` — daftar assignment

Kode identitas persis seperti kolom "Kode Identitas" tabel Data fasih-sm, satu per baris.
Untuk `python ganti_moda/ubah_moda.py --daftar list_kode.txt --console` (ganti mode CAPI → PAPI).

## `rencana_approve.contoh.csv` — rencana approve multi-PML

Kolom wajib `Email PML`, `Email PPL`, `assignment_id` (= ID dokumen, segmen URL entry
fasih-web); kolom lain opsional. Untuk:

```bash
python approve_pml/approve_pml.py --rencana rencana_approve.csv --cek
```
