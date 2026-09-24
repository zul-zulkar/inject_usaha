# Panduan Kontrol Kualitas Sumber Data

`input_gabungan/kontrol_kualitas.py` memeriksa file sumber input usaha — format standar
(`input_usaha.xlsx`) maupun hasil pendataan kertas tahap 2 — lalu menghasilkan laporan Excel yang
menunjuk **sel mana yang perlu dibetulkan, kenapa, dan bagaimana**.

- **Tidak ada aturan baru.** Pemeriksaannya persis `main_gabungan.py --cek` yang sedang berlaku
  (aturan offline + koreksi & nilai pengganti yang dipasang pembaca sheet). Kalau aturan
  pemeriksaan berubah, laporan ini ikut berubah dengan sendirinya.
- **Offline & hanya membaca.** Tanpa VPN, tanpa browser, file sumber tidak diubah.
- Dipakai **sebelum** input (membersihkan data) dan untuk **umpan balik ke PPL/pengolah** (siapa
  harus membetulkan apa).

---

## Menjalankan

Dari root proyek:

```bash
python input_gabungan/kontrol_kualitas.py --sumber input_usaha.xlsx
```

```bash
python input_gabungan/kontrol_kualitas.py --sumber bahan/input_tahap2.xlsx --format tahap2
```

Pilihan yang sering dipakai:

| Pilihan | Guna |
| --- | --- |
| `--format tahap2` | Sheet hasil pendataan kertas tahap 2 (bawaan: `standar`) |
| `--dari N --sampai M` / `--baris 2,5,10-20` | Laporkan sebagian baris saja. Pemeriksaan antarbaris (nama ganda, dst.) tetap atas **seluruh** sheet |
| `--per-ppl [FOLDER]` | Tambahan: satu file per PPL (bawaan folder `kontrol_kualitas_per_ppl/`), hanya temuan yang perlu tindakan — siap dibagikan |
| `--hanya-belum-terkirim` | Lewati baris yang menurut `audit_log_gabungan.csv` sudah terkirim |
| `--csv temuan.csv` | Daftar temuan juga dalam CSV |
| `--tanpa-salinan` | Tanpa lembar "Data bertanda" (lebih cepat & kecil) |
| `--keluaran FILE` | Nama file laporan (bawaan `kontrol_kualitas.xlsx`) |
| `--koordinat`, `--per-baris`, `--abaikan-cek-total`, `--kodepos` | Sama artinya dengan di `main_gabungan.py` — samakan dengan cara Anda menjalankan input supaya hasilnya identik |

Kode keluar: `0` = tidak ada baris ditolak, `1` = ada baris ditolak, `2` = file/pilihan salah.

---

## Isi laporan `kontrol_kualitas.xlsx`

| Lembar | Isi |
| --- | --- |
| **Ringkasan** | Status input baris (SIAP / tanpa koordinat / ditolak), jumlah per kategori, **daftar jenis temuan** beserta nomor barisnya (format `--baris`) dan saran perbaikan, asumsi untuk rincian yang tidak ada kolomnya di sheet |
| **Temuan** | Satu baris per temuan: nomor baris, **sel** (mis. `M15`), judul kolom, kategori, nilai di sheet, nilai yang akan dipakai skrip, keterangan pemeriksaan, saran, PPL, nama usaha, status input & status audit. Bisa difilter; klik sel untuk melompat ke "Data bertanda" |
| **Per PPL** | Jumlah baris per kategori untuk tiap PPL, % baris bersih, jenis temuan terbanyak |
| **Per kolom** | Kolom mana yang paling sering bermasalah |
| **Data bertanda** | Salinan sheet dengan **nomor baris & huruf kolom yang sama** dengan aslinya. Sel bermasalah diwarnai + diberi komentar; kolom `QC_STATUS` & `QC_TEMUAN` ditambahkan di paling kanan |

⚠️ Laporan berisi data responden. File `*.xlsx`/`*.csv` sudah diabaikan git — jangan diunggah
ke tempat publik; bagikan berkas per PPL lewat saluran internal saja.

---

## Kategori temuan

| Kategori | Warna | Arti | Tindakan |
| --- | --- | --- | --- |
| **DITOLAK** | merah | Baris **tidak akan diinput** (status `SKIP_DATA_*`) | Wajib dibetulkan di sheet |
| **DRAFT** | ungu | Koordinat kosong/tidak terbaca → dokumen diisi tapi **ditahan sebagai draft**, tidak dikirim | Isi latitude & longitude |
| **DIGANTI** | oranye | Isian kosong/tidak valid → skrip memakai **nilai pengganti** (umur/tahun pengganti, HP/NIK 9999, nilai minimal, 16b diasumsikan, KBLI dari rekomendasi, dst.). Dokumen tetap dikirim dengan nilai itu | Betulkan dari kuesioner kalau datanya ada |
| **DIKOREKSI** | kuning | Isian diubah/dilengkapi skrip dengan aturan dari data baris itu sendiri (koordinat rusak Excel dipulihkan, 26c dipindah ke 26b, 13a/Nama Jalan dilengkapi, dst.) | Cek hasilnya; sebaiknya sheet ikut dibetulkan |
| **TINJAU** | biru | Mungkin tidak konsisten atau pernah memicu GALAT form (total ≠ rincian, KBLI tidak nyambung dengan 13a, jenis kelamin vs pekerja, nama kembar dinomori, dst.) | Periksa; tidak menghentikan input |
| **INFO** | — | Tafsiran & default biasa format ini (sel uang kosong = 0, format HP, nama dibedakan otomatis) | Tidak perlu tindakan |

Rincian yang **tidak punya kolom** di sheet (mis. rincian di luar kuesioner kertas tahap 2 yang diisi
default) tidak didaftar per baris — cukup diringkas di bagian "Asumsi" lembar Ringkasan.

---

## Alur kerja yang disarankan

1. Jalankan kontrol kualitas pada file sumber (bisa per rentang baris yang akan diinput).
2. Betulkan semua **DITOLAK** — tanpa itu barisnya tidak akan pernah diinput.
3. Lengkapi koordinat baris **DRAFT**.
4. Untuk **DIGANTI**, cek kuesioner: kalau datanya ada, tulis di sheet (nilai pengganti hanya asumsi).
5. Periksa **TINJAU** dan **DIKOREKSI** seperlunya.
6. Jalankan ulang sampai bersih, lalu `main_gabungan.py --cek` dan input seperti biasa.

Catatan: kalau suatu baris masih punya angka tidak valid (`ANGKA_TIDAK_VALID`), pemeriksaan
konsistensi angka baris itu (24, 26–29, dst.) baru berjalan setelah angkanya dibetulkan — jalankan
ulang sesudah memperbaikinya.

---

## Untuk pengembang

- Program ini **tidak memuat aturan**. Pesan pemeriksaan dari `inti/gabungan_loader.py` &
  `inti/tahap2_loader.py` dipetakan ke kategori, kolom, dan saran lewat `POLA_TANDA` (pesan
  review/koreksi) dan `KEYS_MASALAH`/`SARAN_MASALAH` (kode penolakan).
- Pesan yang belum dikenali **tidak hilang**: masuk kategori TINJAU tanpa sel dan jumlahnya dicetak
  di akhir run ("belum dikenali pola kolomnya").
- Menambah/mengubah teks pesan di loader → tambahkan/sesuaikan `Pola` di `POLA_TANDA` **dan** contoh
  pesannya di `tests/test_kontrol_kualitas.py` (uji mewajibkan setiap pola punya contoh).
- Uji: `python tests/test_kontrol_kualitas.py`.
