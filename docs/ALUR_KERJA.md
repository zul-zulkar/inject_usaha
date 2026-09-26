# Alur kerja lengkap

Urutan dari data kertas sampai dokumen berada di wilayah aslinya. Tiap langkah satu alat; rincian
di README folder alatnya. Semua perintah dari folder proyek, VPN kantor aktif.

```text
 bahan/input_usaha.xlsx
   │ 0. siapkan (sekali)          inti/config_lokal.py, templat
   │ 1. reset password PPL        reset_mitra/            manajemen-mitra (Console)
   │ 2. ganti mode → PAPI         fasih_sm/ganti_moda/    fasih-sm (Console)
   │ 3. periksa data              input_usaha/ --cek, kontrol_kualitas
   │ 4. input & kirim             input_usaha/            fasih-web (Playwright)
   │ 5. approve                   approve_pml/            fasih-web (Playwright, akun PML)
   │ 6. buka wilayah tujuan       fasih_sm/buka_wilayah/  (kalau tujuan sudah "Listing Selesai")
   │ 7. pindah wilayah            fasih_sm/pindah_wilayah/
   │ 8. tandai selesai listing    fasih_sm/tandai_selesai/
   ▼    (kapan saja) gabung audit beberapa PC → antar_pc/;  hapus dokumen ganda → fasih_sm/hapus_ganda/
```

## 0. Siapkan (sekali per PC)

```bash
pip install -r requirements.txt
playwright install chromium
copy templates\config_lokal.contoh.py inti\config_lokal.py
copy templates\input_usaha.xlsx bahan\input_usaha.xlsx
python tests/jalankan_semua.py
```

Isi `FIXED_PASSWORD`, `KODE_KAB`, `KODEPOS_BY_DESA` di `inti/config_lokal.py`. PC tambahan / PC
yang dipakai sebelum 25-09-2026: [`antar_pc/README.md`](../antar_pc/README.md).

## 1. Samakan password akun PPL — [`reset_mitra/`](../reset_mitra/README.md)

Semua akun yang dipakai skrip harus ber-password `FIXED_PASSWORD`.

```bash
python reset_mitra/reset_mitra.py --daftar bahan/daftar_akun_ppl.txt --console
```

Tempel `reset_mitra/hasil/reset_mitra_console.siap.js` di Console Chrome (halaman akun-mitra).

## 2. Pastikan subsls wadah punya assignment PAPI — [`fasih_sm/ganti_moda/`](../fasih_sm/ganti_moda/README.md)

Tanpa assignment PAPI, tombol "+ Dokumen Baru" tidak muncul (`SKIP_DOKUMEN_BELUM_ADA`).

```bash
python fasih_sm/ganti_moda/ubah_moda.py --daftar bahan/daftar_kode_identitas.txt --console
```

## 3. Periksa data — [`input_usaha/`](../input_usaha/README.md)

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --cek
python input_usaha/kontrol_kualitas.py --sumber bahan/input_usaha.xlsx --per-ppl
```

Betulkan sel yang ditolak (atau kembalikan ke PPL), ulangi sampai jumlah SIAP sesuai harapan.
Koordinat rusak: [`koordinat/`](../koordinat/README.md).

## 4. Input & kirim — [`input_usaha/`](../input_usaha/README.md)

```bash
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --baris 2
python input_usaha/jalankan.py --sumber bahan/input_usaha.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --dari 2 --sampai 500 --sinkron-dulu --lewati-selesai --izinkan-wilayah-beda --submit
```

Baris pertama = dry-run (tinjau di web). Beberapa PC: rentang baris & akun berbeda per PC, lalu
gabungkan audit ([`antar_pc/`](../antar_pc/README.md)).

## 5. Approve — [`approve_pml/`](../approve_pml/README.md)

```bash
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL --eksekusi --limit 1
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL --eksekusi
```

## 6–8. Kembalikan dokumen ke wilayah aslinya — [`fasih_sm/`](../fasih_sm/README.md)

```bash
python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber bahan/input_usaha.xlsx --dari-approve --daftar-tujuan bahan/daftar_tujuan.txt --console
python fasih_sm/buka_wilayah/buka_wilayah.py --daftar bahan/daftar_tujuan.txt --console      # tujuan yang sudah Listing Selesai
python fasih_sm/tandai_selesai/tandai_selesai.py --daftar bahan/daftar_tujuan.txt --console  # sesudah semua dipindah
```

Tiap perintah menulis `fasih_sm/<alat>/hasil/*.siap.js` untuk ditempel di Console Chrome
(halaman Data survei fasih-sm, akun admin kabupaten): buka wilayah → pindah → tandai selesai.

## Kalau ada yang janggal

Semua alat berhenti & melapor, tidak menebak. Baca pesannya, lihat tabel status di README alat
itu, dan jangan longgarkan pengamannya. Perilaku fasih-web/fasih-sm bisa berubah; catatan teknis
untuk memperbaiki skrip: [`CATATAN_TEKNIS.md`](CATATAN_TEKNIS.md).
