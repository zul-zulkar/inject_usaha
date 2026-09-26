# gui — semua alat lewat halaman web lokal

Formulir untuk setiap alat di proyek ini: pilih berkas, centang opsi, klik tombol. GUI **tidak punya
logika input sendiri**; setiap tombol menyusun perintah yang sama persis dengan perintah terminal
di README folder alatnya, lalu menjalankannya. Perintahnya ditampilkan di bawah formulir (bisa disalin ke
terminal). Kode alat yang lama tidak diubah.

## Mulai

Prasyarat sama dengan proyek ini: **VPN kantor**, Python 3.10+, Google Chrome. Tidak ada paket tambahan.

1. Klik dua kali **`gui\buka_gui.bat`** (atau `python gui/server.py`). Browser terbuka di
   `http://127.0.0.1:8765`. **Biarkan jendela hitamnya terbuka**; menutupnya menghentikan GUI dan
   semua proses yang sedang berjalan.
2. **Persiapan**: semua baris harus hijau. Tombol *Pasang* memasang paket & Chromium Playwright.
3. **Password** (kanan atas): password SSO akun PPL/PML. Hanya disimpan di memori, **tidak pernah ditulis
   ke disk**, dan harus diketik lagi setiap kali GUI dibuka. Kalau `inti/config_lokal.py` di PC ini sudah
   berisi password, kotak ini boleh dikosongkan.
4. **Pengaturan** (sekali per kabupaten):
   - *Dasar*: kode kabupaten, akun & subsls wadah, **kotak koordinat kabupaten** (bawaannya kotak Buleleng,
     jadi kabupaten lain wajib mengganti; bisa dihitung dari peta SLS).
   - *Wilayah*: **kodepos per desa** (baris dengan desa tanpa kodepos ditolak). Bisa diisi dengan impor
     Excel/CSV, disusun dari sheet lama, atau ditambah satu per satu. Nama wilayah bisa diimpor dari
     peta SLS (GeoJSON).
   - *Aturan pengisian*: nilai pengganti untuk sel kosong/rusak. Semuanya ketetapan BPS Buleleng;
     tinjau sebelum mengirim data sungguhan. Keterangannya diambil dari komentar `inti/config.py`.
5. Kerjakan sesuai urutan di halaman Persiapan: reset password mitra → ganti mode → isi sheet (tombol
   *Buat sheet input dari templat*) → Generate KBLI → Input Usaha → Approve → pindah wilayah.

## Pengaman

| Tindakan | Yang terjadi di GUI |
| --- | --- |
| **KIRIM** (input), **APPROVE** | Skrip mencetak ringkasan lalu meminta `Ketik 'YA'`. GUI membuka dialog merah berisi ringkasan itu, dan tombolnya baru aktif kalau Anda mengetik `YA`. *Batalkan* mengirim `TIDAK`. |
| **Input otomatis** | `otomatis.py` mengetik YA sendiri di setiap putaran, jadi GUI meminta Anda mengetik YA **sebelum** memulainya. Server menolak memulai tanpa itu. |
| Tulis ke audit / sheet (`--tulis`) | Dialog konfirmasi biasa. |
| Skrip Console fasih-sm / mitra | GUI hanya membuat `.siap.js` dan menyalinnya ke clipboard. Eksekusinya tetap di Console Chrome, dengan pengaman Console masing-masing. |
| *Hentikan* | Sama dengan menutup terminal: dokumen yang sedang diisi bisa tertinggal DRAFT; audit tetap mencatatnya. |

Aturan proyek tetap berlaku: **satu akun = satu proses = satu PC**. Kunci proses skrip tetap menolak
proses kedua dengan akun yang sama, walaupun GUI boleh menjalankan beberapa proses sekaligus.

Server hanya mendengar di `127.0.0.1`, dan setiap panggilan wajib membawa token acak per sesi, jadi
halaman web lain tidak bisa menyuruh GUI menjalankan alat.

## Generate KBLI

Memanggil proyek **terpisah** `generate_kbli` (bawaan `..\generate_kbli`; atur di Pengaturan > Aplikasi),
yang butuh Node.js, folder `epapi-se2026`, dan model ±1,2 GB (tombol *Unduh model*). Hasil →
`gui/hasil/kbli/<sheet>_kbli.xlsx`. Kartu **Salin hasil ke clipboard** menunjukkan sel tujuan (mis.
`AU2`). Klik sel itu lalu Ctrl+V: Kode + Judul KBLI terisi urut baris. Kode ditempel sebagai **teks**,
jadi `01464` tidak menjadi `1464` di Excel. Baris yang kodenya sudah terisi di sheet dipertahankan apa
adanya; bedanya dengan saran mesin dilaporkan dan tidak ditimpa. Baris bertanda PERIKSA ditampilkan
bersama alternatifnya.

Koordinat pengganti punya tombol serupa (*Salin Latitude/Longitude*). Baris yang dilewati alat tidak
mengosongkan koordinat di sheet.

## Sengaja tidak ada di GUI (tetap lewat terminal)

- `--headless` (ditolak fasih-web) dan `approve_pml.py --ya` (melewati konfirmasi YA).
- Jalur Playwright `ubah_moda.py` (`--petakan`, dry-run/`--eksekusi` browser). GUI hanya membuat skrip
  Console, yang merupakan jalur utama karena fasih-sm mendeteksi bot.
- `generate_kbli.py --kol-kbli` / `--hanya-kode`, karena tombol salin membutuhkan kolom Kode & Judul bawaan.
- `kodepos_desa.py --tulis` menulis ke `inti/config_lokal.py`. Di GUI, hasilnya masuk Pengaturan >
  Wilayah > *Susun dari sheet lama*.

## Berkas

| Berkas | Isi |
| --- | --- |
| `gui/pengaturan.json` | Pengaturan kabupaten dari GUI. **Tidak ikut git** (`gui/.gitignore`). Ikut zip `bungkus_pc` biasa, tidak ikut `--kode-saja` (sama seperti `config_lokal.py`). Tanpa password. Bagikan ke PC lain lewat Pengaturan > Ekspor/Impor. |
| `gui/hasil/log/` | Log setiap proses (juga dari sesi GUI sebelumnya); tombol *Buka log*. |
| `gui/hasil/isian_terakhir.json` | Isian formulir terakhir PC ini, **tidak pernah dibagikan**, supaya PC lain tidak mewarisi akun yang sama. |
| `gui/hasil/kbli/` | Hasil Generate KBLI. |

Urutan pengaturan yang berlaku untuk alat yang dijalankan GUI: **Pengaturan GUI > `inti/config_lokal.py` >
`inti/config.py`**. Perintah terminal biasa tidak melihat pengaturan GUI.

## Kode yang berpengaruh

| Berkas | Peran |
| --- | --- |
| [`alat.py`](alat.py) | Daftar alat: isian, opsi CLI, aksi, tombol hasil. **Menambah/mengubah opsi alat = ubah di sini**; `tests/test_gui.py` memeriksa setiap opsi benar-benar ada di skripnya. |
| [`server.py`](server.py) | Server web (pustaka standar Python), penyusun perintah, pengelola proses & dialog YA, validasi pengaturan. |
| [`sisip/sitecustomize.py`](sisip/sitecustomize.py) | Menimpakan pengaturan GUI ke `inti.config` di proses alat (hanya proses yang dijalankan GUI). Pengaturan rusak → alat berhenti (gagal-tertutup). |
| [`bantu.py`](bantu.py) | Membaca `inti/config.py` + komentar untuk halaman Pengaturan, kodepos dari sheet lama, impor peta SLS. |
| [`berkas_tabel.py`](berkas_tabel.py) | Clipboard KBLI & koordinat, impor tabel kodepos/wilayah. |
| [`web/`](web/) | Halaman (HTML/CSS/JS tanpa pustaka luar; formulir dibangkitkan dari `alat.py`). |

Uji: `python tests/test_gui.py` (ikut `tests/jalankan_semua.py`).
