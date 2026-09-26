# Catatan teknis — perilaku fasih-web & fasih-sm

Untuk yang memperbaiki skrip saat tampilan/perilaku server berubah. Semua di sini temuan dari dump
DOM & percobaan langsung (2026-09), bukan tebakan. Kalau skrip berhenti dengan pesan "tidak
dikenal", itu pengaman yang bekerja — cari sebabnya, jangan longgarkan pengamannya.

## Form-engine fasih-web

1. **Hanya section AKTIF yang ada di DOM** — field section lain tidak ter-render. Pindah section
   dulu (`goto_section()` / `next_section()`) sebelum mengisi.
2. **Komponen dirender dgn `id` = dataKey** (`<div id="kodepos">`). Selektor utama = dataKey
   (`inti/config.py` → `DK`). Petakan section baru dgn `--dump-dom` → `hasil/log_screenshots/*.map.tsv`.
3. **Section berikutnya baru ter-unlock setelah prasyarat terisi**; tombol Next hanya ada kalau
   memang ada section berikutnya.
4. **Teks dirender dua kali** (mobile & desktop, satu di-hidden) → saring `visible` sebelum `.first`.
5. **Komponen waktu tanpa tombol saat sudah terisi** — deteksi lewat hilangnya "Waktu belum diambil".
6. **Pertanyaan bersyarat memunculkan komponen baru** — dump ulang setelah mengisi.

Urutan section: PENGANTAR → IDENTITAS WILAYAH → SE2026 - P → SE2026 - L BLOK II (kartu **nested**,
harus diklik; `next_section()` dari dalam nested kembali ke induk, keluar lewat sidebar) →
KETERANGAN PEMBERI JAWABAN → CATATAN.

## Jebakan yang sudah memakan korban

- **Kirim tidak bisa dibatalkan**; toast "berhasil dikirim" ≠ terkirim — status diverifikasi lewat
  list/API (`sinkron_list`).
- **"Nomor Urut Bangunan" jangan disentuh**: sekali fokus nilainya jadi `0` permanen → GALAT.
  Diperbaiki hanya kalau itu satu-satunya GALAT (angka terbesar + 1 lewat chevron).
- **`.count()` bukan bukti "tidak ada"** (snapshot, tidak menunggu render) — pernah membuat
  dokumen ganda. Pakai `wait_for`.
- **Mengklik ulang radio yang sudah benar me-reset turunannya**; `pilih_umkm_sls` hilang permanen
  setelah `keberadaan_usaha` dijawab → isi lebih dulu.
- **Memilih ulang KBLI yang sudah terpilih membatalkan pilihan** (13h kosong, 26c hilang).
- Combobox = `<textarea>` yang harus diklik dulu; checkbox Kobalte = klik div `[id$="-control"]`.
- `get_by_role("button", name=/Gunakan Lokasi/)` juga cocok tombol peta → `exact=True`.
- Nama dataKey menyesatkan: `aset_usaha_thn` = 28a tanah & bangunan, `aset_lain_thn` = 28b.
- **Headless ditolak** (halaman anti-bot) — selalu headed.
- Aturan validasi form lengkap (JS per rincian): `GET /api/designer/api/template/file-validation/<template>`
  — sumber terbaik untuk pemeriksaan offline baru.

## Sesi & akun

Login lewat SSO Keycloak (`sso.bps.go.id`); logout fasih-web saja tidak memutus sesi. Skrip
menghapus cookie semua domain saat ganti akun dan **memverifikasi akun aktif** lewat respons
`/users/check-user` sebelum mengisi (`ERROR_AKUN_SALAH` kalau beda). Satu akun = satu proses:
proses lain yang logout memutus sesi akun yang sama.

## API yang dipakai (READ-ONLY kecuali disebut)

| Endpoint | Guna |
| --- | --- |
| `POST /api/analytic/api/v2/assignment/web-entry/datatable-all-user-survey-periode` | list PENDATAAN (id, `data1` = nama, status, `sumError`) — `sinkron_list` |
| `GET .../assignment/web-entry/get-by-id-with-data?id=` | status & isi satu dokumen — `approve_pml`, verifikasi wilayah |
| fasih-sm `.../assignment-region/datatable`, `/undone`, `/done` | status & buka/tandai wilayah (TULIS) — butuh header `X-XSRF-TOKEN` |
| fasih-sm `PUT .../assignment/update-region-bulk` | pindah wilayah (TULIS) |

## fasih-sm & manajemen-mitra

Keduanya mendeteksi browser otomatis (F5/TSPD), jadi alatnya berupa skrip **Console** yang
ditempel di Chrome biasa. Rate limit (HTTP 429) & 504 umum terjadi: skrip menunggu & mengulang,
request TULIS yang kena galat sementara tidak dikirim ulang buta — status dibaca dulu. Jangan
pindah halaman tabel (paginasi) saat skrip jalan; jaga tab tetap di depan.
