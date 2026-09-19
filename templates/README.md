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

## `Agenda.contoh.xlsx` — sheet sumber alur utama

Salin ke root sebagai `Agenda.xlsx` (atau unggah ke Google Sheets untuk diisi bersama, lalu
*File → Download → Microsoft Excel*).

| Tab | Isi |
| --- | --- |
| `petunjuk` | Penjelasan tiap kolom: wajib/bersyarat/opsional, isi yang diharapkan, pilihan valid |
| `gabungan` | **Tempat mengisi data.** Satu baris = satu usaha/dokumen. Judul kolom jangan diubah. Kolom berpilihan punya dropdown; kolom kode berformat teks |
| `contoh` | Satu baris fiktif yang lolos `--cek` — contoh bentuk isian |
| `Nama Wilayah` | Opsional: kode & nama provinsi/kab/kec/desa. Dipakai melengkapi "Nama Jalan" yang kurang dari 10 huruf |

Nilai di tab `gabungan` = **jawaban final** per rincian kuesioner (diketik apa adanya).
Teks opsi harus persis sama dengan dropdown (mis. `2. Tidak`). Periksa tanpa browser:

```bash
python input_gabungan/main_gabungan.py --sumber Agenda.xlsx --cek
```

File ini dibangkitkan oleh `buat_templat_agenda.py` dari daftar kolom & opsi di
`inti/gabungan_loader.py`. Kalau judul kolom atau opsi form berubah, perbarui loader lalu:

```bash
python templates/buat_templat_agenda.py
```

(skrip itu juga memverifikasi bahwa baris contohnya lolos pemeriksaan offline).

## `LKpenyalinan.contoh.csv` — backlog alur lama

Header saja. Dipakai `input_fasihweb/main.py --csv`. Alur ini juga butuh file export
fasih-sm per baris (`export/{No}_{assignment_id}.converted.json`) — lihat
`docs/PANDUAN_EKSPOR_MANUAL.md`. Untuk pengguna baru, alur Agenda di atas lebih sederhana.

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
