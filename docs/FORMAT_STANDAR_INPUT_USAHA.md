# Format Standar Input Usaha (inject usaha)

**Inject usaha** = menambahkan dokumen usaha baru ke fasih-web berdasarkan data yang sudah
dikumpulkan di luar aplikasi. Setiap usaha menjadi satu dokumen SE2026 dengan pola yang
sama: SE2026-P "Tambah: Bangunan Lainnya", "Keberadaan: 2. Baru", lalu SE2026-L BLOK II
diisi, lalu (setelah ditinjau) dikirim.

**Format standar** adalah satu file Excel yang menampung data tersebut:

- **satu baris = satu usaha = satu dokumen**;
- **satu kolom = jawaban final satu rincian kuesioner**, diketik apa adanya (tidak ada
  kalkulasi, tidak ada file tambahan);
- berlaku untuk **jenis usaha apa pun**: perdagangan, jasa, fasilitas kesehatan, pangkalan
  gas, produksi makanan, dan seterusnya. Rincian yang hanya muncul untuk jenis usaha
  tertentu punya kolom sendiri yang boleh dikosongkan kalau tidak relevan.

Dibaca oleh `input_gabungan/main_gabungan.py`. Nama baku: file **`input_usaha.xlsx`**, tab
**`input_usaha`**. Nama file sebenarnya bebas (diberikan lewat `--sumber`, boleh lebih dari satu
file); nama tab harus `input_usaha`. Nama lama dari BPS Buleleng — file `Agenda.xlsx` dengan tab
`gabungan` (dulu menggabungkan data pangkalan gas & faskes) — tetap diterima.

---

## Templat

| File | Isi | Kapan dipakai |
| --- | --- | --- |
| [`templates/input_usaha.kosong.xlsx`](../templates/input_usaha.kosong.xlsx) | Hanya tab `input_usaha`: baris judul semua kolom, dropdown opsi form, format teks untuk kolom kode. Tanpa data. | Tempat menyalin hasil pendataan lapangan. |
| [`templates/input_usaha.contoh.xlsx`](../templates/input_usaha.contoh.xlsx) | Sama, plus tab `petunjuk` (penjelasan & status wajib tiap kolom), `contoh` (dua baris fiktif: perdagangan & produksi), `Nama Wilayah`. | Belajar formatnya; rujukan saat mengisi. |

Kolom dikenali lewat **awalan judul** (mis. `26. a.`), bukan posisi, jadi urutan kolom bebas
dan kolom tambahan milik Anda sendiri diabaikan. Judul yang dibaca skrip tercantum di tab
`petunjuk` dan di `KOLOM` pada `inti/gabungan_loader.py`.

Teks opsi harus **persis** sama dengan opsi form (termasuk nomor dan titik), mis. `2. Tidak`,
`10. Di luar kawasan`. Dropdown di templat sudah berisi daftar yang benar.

---

## Dua mode pengisian

| | Mode normal (bawaan) | **Mode murni** |
| --- | --- | --- |
| Setelan | `GABUNGAN_MODE_MURNI = False` | `GABUNGAN_MODE_MURNI = True` di `inti/config_lokal.py` |
| Sumber isian | Sheet + aturan & default yang ditetapkan BPS Buleleng | **100% dari sheet** hasil pendataan lapangan |
| Nama dokumen & 8b | `<nama usaha> (<12a pemilik>)` | apa adanya |
| 13f produk utama kosong | disalin dari 13a | baris di-skip |
| Nama Jalan < 10 huruf | dilengkapi nama desa/kecamatan | baris di-skip |
| Blok/Nomor kosong | diisi `-` | dibiarkan kosong |
| 13b4 bukan opsi form | diturunkan dari kategori KBLI | baris di-skip |
| 19/20 kosong padahal form memunculkannya | default config (`3. Tidak/Belum`, `3. Tidak`, jumlah `1`), dicatat di `review_disarankan` | baris di-skip |
| "Pilih UMKM dalam satu SLS" kosong | dicoba "Tidak ada" | baris di-skip |
| Koreksi data (pekerja `0/2/0/1`, badan usaha dari awalan PT/CV/UD, BUMDES, nama tertentu) | dikoreksi, dicatat | **tidak dikoreksi** — pelanggaran aturan form dilaporkan & baris di-skip |

**Disarankan mode murni** untuk data hasil pendataan lapangan: tidak ada isian yang muncul
dari aturan skrip, jadi setiap nilai di fasih-web bisa ditelusuri ke sel Excel. Konsekuensinya,
kolom yang di mode normal boleh kosong (13f, dan 19/20 untuk kategori tertentu) harus diisi.

Kalau form meminta sesuatu yang tidak ada di sheet, baris itu **di-skip, tidak ditebak**.
Sebisa mungkin ini diketahui saat pemeriksaan offline (`--cek`, sebelum dokumen dibuat);
yang hanya bisa diketahui dari form (mis. rincian 19 muncul untuk kategori tertentu)
tercatat sebagai `SKIP_<kode>` saat pengisian, dan dokumennya tetap DRAFT.

---

## Kolom menurut jenis usaha

Semua baris wajib mengisi kolom identitas, SE2026-P, dan BLOK II umum (8–18, 21–29) — lihat
status `WAJIB` di tab `petunjuk`. Kolom berikut bergantung pada jenis usaha:

| Kondisi | Rincian yang dimunculkan form | Yang harus diisi di sheet |
| --- | --- | --- |
| 13b1 = `1. Ya` (memproduksi barang di lokasi) | 13d input, 13e proses | kolom `13. d.` & `13. e.` (dicek offline) |
| 13b1, 13b2, 13b3 semuanya `2. Tidak` (jasa murni, mis. faskes, bengkel) | 13b4 | `13. b4.`: `1. Jasa` atau `2. Pertanian, Perikanan, dan Kehutanan` |
| KBLI kategori B–F (golongan 05–43) atau golongan 56 (makan minum) | 26c **tidak** ada | `26. c.` = 0; biaya pembelian barang dimasukkan ke `26. b.` (dicek offline) |
| Kategori tertentu (BPOM) — terlihat pada perdagangan (G) | 20a, 20c (kadang 20b) | `20. a.`, `20. c.` (& `20. b.`) |
| Kategori tertentu (BPJPH) | 19a, 19c (19b kalau 19a = Ya) | `19. a.`, `19. c.` (& `19. b.`) |
| 10a = `1. Ya` (punya NIB) | 10b | `10. b.` |
| 10a = `2. Tidak` | 10c | `10. c.` |
| 16a = `1. Ya` (pakai internet) | 16b1–16b6, 16c, 27d | minimal satu 16b = `1. Ya` |
| SLS punya daftar UMKM prelist | "Pilih UMKM dalam satu SLS yang sama" | `Tidak Ada` |

Tidak ada salahnya mengisi kolom bersyarat yang ternyata tidak dimunculkan form — nilainya
diabaikan.

---

## Pemeriksaan offline (`--cek`)

```bash
python input_gabungan/main_gabungan.py --sumber input_usaha.xlsx --cek
```

Tanpa browser/VPN, dalam hitungan detik. Hasil per baris ditulis ke `cek_gabungan.csv`
(status `SIAP` atau `SKIP_DATA_<kode>`). Aturan yang dicek, semuanya berasal dari validasi
form atau batasan skrip:

- kolom wajib terisi; opsi radio persis salah satu opsi form;
- format: idsubsls 16 digit, kodepos 5 digit, KBLI 5 digit, tahun 4 digit, angka bulat,
  koordinat di wilayah Indonesia; 6 kolom "Pilih PROVINSI..SUBSLS" = idsubsls (mode per baris:
  skip; mode satu subsls: hanya tanda review);
- 12c umur 10–99; 24a1+24b1 = 24a2+24b2; 29a–29f berjumlah 100; 26f & 27c minimal 100.000;
  27d ≤ 100;
- 8b maksimal 50 karakter; Nama Jalan minimal 10 huruf;
- 16a Ya → minimal satu 16b Ya; 13b1 Ya → 13d & 13e terisi; KBLI B–F/56 → 26c = 0;
- tahun operasi < tahun berjalan (usaha yang mulai tahun ini memakai rincian 30–33 bulanan,
  **belum didukung**);
- nama dokumen tidak saling memuat antarbaris (pencarian dokumen bisa salah buka), baris ganda;
- mode murni: nama BUMDES wajib badan usaha `6. BUM Desa`; 8b tidak boleh diawali `CV`.

---

## Yang tidak didukung (isi manual)

- SE2026-P selain "Bangunan Lainnya", keberadaan selain `2. Baru`, perubahan SLS `1. Ya`.
- Varian bulanan (rincian 30–33).
- Rincian 13d/13e/19b dicari lewat teks labelnya karena dataKey-nya belum terpetakan;
  jalankan dry-run satu baris dulu untuk jenis usaha yang baru pertama kali diinput.

---

## Menambah rincian/kolom baru (pengembang)

1. **Ambil dari form asli, jangan menebak**: jalankan dry-run dengan `--dump-dom` pada dokumen
   yang memunculkan rincian itu, baca dataKey & teks opsinya dari `log_screenshots/*.map.tsv`.
2. `inti/gabungan_loader.py`: tambah ke `KOLOM` (awalan judul), `KOLOM_OPSIONAL` kalau
   bersyarat, `OPSI_FORM` kalau radio, dan aturannya di `periksa_baris()`.
3. `input_gabungan/fill_gabungan.py`: isi hanya kalau komponennya dirender (`komponen_ada` /
   `isi_bersyarat_by_label`); kalau dirender tapi kolomnya kosong → `BarisPerluManual`
   (mode murni wajib begitu; mode normal boleh default config asalkan dicatat di `asumsi`).
4. `templates/buat_templat_input_usaha.py`: tambah ke `KOLOM_TEMPLAT`, lalu
   `python templates/buat_templat_input_usaha.py` (sekaligus memverifikasi templat).
5. Tambah uji di `tests/test_gabungan_loader.py` & `tests/test_fill_gabungan.py`, lalu
   `python tests/jalankan_semua.py`.

---

## Alur lain: salin dari dokumen sumber (`salin_dokumen_sumber.csv`)

`input_fasihweb/` adalah alur yang lebih khusus: usaha **pecahan** yang jawabannya
**disalin dari dokumen keluarga/usaha lain di fasih-sm** (file export per dokumen), dengan
penyesuaian yang ditetapkan BPS Buleleng (nilai finansial 10%, NIK `9999`, aset tanah 0, dll).
Di Buleleng dipakai untuk usaha perdagangan. Kalau data Anda berasal dari pendataan lapangan,
pakai format standar ini; alur salin hanya relevan kalau sumbernya memang dokumen fasih-sm
lain. Nama lama file backlognya: `LKpenyalinan.csv`. Panduannya: [`PANDUAN_INPUT_OTOMATIS.md`](PANDUAN_INPUT_OTOMATIS.md) &
[`PANDUAN_EKSPOR_MANUAL.md`](PANDUAN_EKSPOR_MANUAL.md).
