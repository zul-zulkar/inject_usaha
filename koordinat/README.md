# koordinat — perbaiki / ganti koordinat sheet input usaha

Baris tanpa koordinat valid jadi DRAFT (tidak dikirim). Alat ini membuat **berkas xlsx baru** berisi
Latitude/Longitude yang sudah dirapikan, siap **salin-tempel** ke sheet sumber (sumber tidak disentuh).

1. **Format dibaca dulu:** koma/titik desimal, akhiran S/E, derajat-menit-detik, titik ribuan
   Excel; derajat tanpa simbol & salah ketik satu digit hanya dipakai kalau hasilnya jatuh di subsls barisnya.
2. **> 500 m di luar poligon subsls (`--batas-m`), di luar kabupaten, atau kosong → diganti** titik acak
   di subsls itu, diambil dari geotag **listing** (pemukiman), diutamakan dekat **jalan**; digeser 5–15 m.
   Acakannya tetap (dijalankan ulang = titik sama).
3. **Pemilik (12a) & alamat (8c) sama = satu koordinat.**

Koordinat pengganti adalah **imputasi**, bukan hasil pengukuran.

## Pakai

Isi sekali di `inti/config_lokal.py`: `PETA_SLS_PATH` (GeoJSON poligon SUBSLS), `TITIK_LISTING_PATH`
(CSV berkolom `latitude`/`longitude`), `JALAN_PATH` (opsional, GeoJSON/Overpass).

```bash
python koordinat/koordinat_pengganti.py --sumber bahan/input_usaha.xlsx
```

Hasil `koordinat/hasil/input_usaha_koordinat.xlsx`: baris ke-N = baris ke-N sheet. Salin `A2:B<akhir>`
→ Paste Values ke sel **Latitude baris 2** sheet sumber. Baris yang berubah berwarna kuning, asal
tiap koordinat di kolom `Sumber koordinat` (`ASLI`, `KELOMPOK`, `SALAH_KETIK_DIPERBAIKI`,
`DERAJAT_TANPA_SIMBOL`, `ACAK_LISTING…`, `ACAK_POLIGON…`). Lalu `input_usaha/jalankan.py --cek`:
baris DRAFT harus berkurang.

## Berkas

`koordinat_pengganti.py` (baca format, nilai jarak, kelompok, titik acak berbenih), `peta.py`
(titik-dalam-poligon SUBSLS, murni Python). Uji: `python tests/test_koordinat_pengganti.py`,
`python tests/test_peta.py`.
