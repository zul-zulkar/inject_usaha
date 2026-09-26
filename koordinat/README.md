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

### Subsls menurut koordinat

```bash
python koordinat/koordinat_pengganti.py --sumber bahan/input_usaha.xlsx --subsls-dari-koordinat
```

Kebalikan aturan 2: titik yang jatuh di poligon subsls **lain** dipakai apa adanya dan subsls barisnya
ikut titik itu. Kolom `C:E` hasil = kolom **3, 4, 5** sheet → Paste Values ke sel kolom "3" baris 2
(nama desa/kecamatan diganti hanya kalau pindah desa/kecamatan; baris itu jingga — tinjau dulu).

- Titik yang cuma ≤ `--toleransi-m` (20 m) di luar subsls kolom 5 **tidak** memindahkan subsls —
  GPS HP & garis batas peta sama-sama meleset beberapa meter. `--toleransi-m 0` = murni koordinat.
- Titik rusak / di luar kabupaten / di luar semua poligon: tetap diperlakukan spt aturan 1–2.
- Baris yang **sudah punya dokumen** (kolom "ID Dokumen FASIH" terisi, atau tercatat di audit mana
  pun di `audit/`) **tidak diubah** subsls-nya (`TETAP_SUDAH_ADA_DOKUMEN`): kolom 5 ikut membentuk
  kunci baris, mengubahnya = dokumen tidak dikenali lagi = dibuat **ganda**. Pindahkan dokumennya
  lewat `fasih_sm/pindah_wilayah/` kalau perlu.
- Tempel hanya sesudah audit semua PC digabung, lalu bagikan sheet itu ke **semua** PC.

## Berkas

`koordinat_pengganti.py` (baca format, nilai jarak, kelompok, titik acak berbenih), `peta.py`
(titik-dalam-poligon SUBSLS, murni Python). Uji: `python tests/test_koordinat_pengganti.py`,
`python tests/test_peta.py`.
