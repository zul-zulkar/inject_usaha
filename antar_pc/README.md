# antar_pc — kerja di beberapa PC

Tiap PC punya audit sendiri, dan audit PC lain tidak saling tahu. Aturan main:

- **Rentang baris tidak tumpang tindih** (`--dari/--sampai` berbeda per PC).
- **Satu akun hanya di satu PC pada satu waktu** — dua PC dgn akun sama = dokumen ganda.
- Setelah batch berhenti: **audit semua PC digabung** di PC utama, lalu disebar lagi.

## 1. Memasang / memperbarui PC lain

Di PC utama, buat zip ringan (tanpa cache, sesi browser, `hasil/`, `arsip/`, `audit/pc/`):

```bash
python antar_pc/bungkus_pc.py --daftar       # lihat isi & ukurannya
python antar_pc/bungkus_pc.py --kode-saja    # PC tujuan MASIH bekerja: kode saja, audit & bahan-nya aman
python antar_pc/bungkus_pc.py                # PC baru / sesudah audit digabung: ikut audit/, bahan/, config lokal
```

Hasilnya `antar_pc/hasil/split_usaha_pc_<waktu>.zip`. ⚠️ Berisi data responden & password — pindahkan
lewat flashdisk/drive kantor. ⚠️ Zip **tanpa** `--kode-saja` membawa `audit/` PC utama: extract di PC
yang auditnya belum digabung akan **menimpa** audit PC itu (dokumennya lalu dibuat ganda).

Di PC tujuan: extract ke folder proyek (mis. `D:\split_usaha`), lalu:

```bash
pip install -r requirements.txt
playwright install chromium
python antar_pc/pindah_struktur.py            # PC yang dipakai sebelum 25-09-2026: lihat rencana
python antar_pc/pindah_struktur.py --jalankan # pindahkan berkas lama ke struktur baru
python tests/jalankan_semua.py
```

`pindah_struktur.py` hanya **memindah** (tidak pernah menghapus/menimpa): audit lama di akar →
`audit/batch21/`, laporan → `<alat>/hasil/`, kode lama → `arsip/kode_lama/`. Selama audit lama
masih di akar, semua alat audit menolak jalan. PC baru dari GitHub: salin
`templates/config_lokal.contoh.py` ke `inti/config_lokal.py` dan isi.

## 2. Menggabungkan audit

Hentikan batch di **semua** PC dulu, termasuk PC utama.

1. Salin audit **dan** sheet bahan tiap PC ke PC utama, satu subfolder per PC, nama berkas apa adanya:
   `audit/pc/pc2/audit_log_gabungan.csv`, `audit/pc/pc2/input_usaha.xlsx`, … Jangan menaruh berkas
   audit lain (mis. audit batch lama atau hasil gabungan sebelumnya) di `audit/pc/`: semua CSV audit di
   sana ikut digabung.
2. Gabungkan audit semua PC **plus audit PC utama sendiri** langsung ke audit kerja (cadangan
   `.bak-<waktu>` otomatis). Tanpa `--tulis` = laporan saja:

```bash
python antar_pc/gabung_audit.py --sumber audit/pc --sumber audit/audit_log_gabungan.csv --sheet bahan/input_usaha.xlsx --keluaran audit/audit_log_gabungan.csv --tulis
```

3. Satukan kolom "ID Dokumen FASIH" sheet semua PC ke sheet kerja, lalu isi sisa ID dari audit gabungan
   (yang kedua hanya mengisi sel kosong & tidak membuat cadangan):

```bash
python antar_pc/gabung_id_sumber.py --utama bahan/input_usaha.xlsx --sumber audit/pc --keluaran bahan/input_usaha.xlsx --tulis
python input_usaha/tulis_id_sumber.py --sumber bahan/input_usaha.xlsx --tulis
```

4. Sebar ke PC lain dengan `python antar_pc/bungkus_pc.py` (zip ini membawa `audit/` & `bahan/`). Di PC
   tujuan: ganti nama folder lama (cadangan), extract ke folder baru. Laporan (`laporan_gabung*.csv`,
   `daftar_ganda.csv`) ada di `audit/pc/hasil/`. Dokumen ganda: [`fasih_sm/hapus_ganda`](../fasih_sm/hapus_ganda/).

⚠️ Sheet dan audit harus dipasang **bersamaan**. Sheet ber-ID gabungan + audit yang belum digabung =
baris milik PC lain dibuka lewat ID dgn akun yang salah (form tidak mount, login ulang tiap baris).
`input_usaha/jalankan.py` berhenti sebelum membuka browser kalau mendeteksinya ("AUDIT TIDAK COCOK").

## 3. Audit rusak karena dibuka-simpan Excel

Gejala: kunci seperti `1.40E+09`, idsubsls `5.10806E+15`, pesan "RUSAK krn pernah disimpan Excel".
Semua alat menolak audit seperti itu. Pulihkan (nilai hanya ditulis kalau pasti):

```bash
python antar_pc/pulihkan_excel.py            # laporan
python antar_pc/pulihkan_excel.py --tulis    # tulis (cadangan .bak-<waktu>)
```

## Berkas

| Berkas                  | Fungsi                                                              |
| ----------------------- | ------------------------------------------------------------------- |
| `bungkus_pc.py`       | aturan isi zip (`alasan_dibuang`), `--kode-saja`, `--kecuali` |
| `pindah_struktur.py`  | migrasi sekali per PC dari struktur lama (sebelum 2026-09-25)       |
| `gabung_audit.py`     | gabung audit per blok (berkas, kunci), laporan & daftar ganda       |
| `gabung_id_sumber.py` | gabung kolom ID dokumen sheet beberapa PC                           |
| `pulihkan_excel.py`   | pulihkan audit yang pernah disimpan Excel                           |
| `hasil/`              | zip hasil`bungkus_pc`                                             |

Uji: `python tests/test_bungkus_pc.py`, `tests/test_pindah_struktur.py`, `tests/test_gabung_audit.py`,
`tests/test_gabung_id_sumber.py`, `tests/test_pulihkan_excel.py`.
