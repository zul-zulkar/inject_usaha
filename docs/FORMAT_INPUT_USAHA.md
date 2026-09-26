# Format input usaha (standar tunggal = format tahap 2)

Satu format untuk semua usaha: salinan **kuesioner kertas SE2026** dalam satu sheet Excel.
Templat + 1 baris contoh + tab petunjuk: [`templates/input_usaha.xlsx`](../templates/input_usaha.xlsx).
Pemetaan & pemeriksaannya di [`inti/tahap2_loader.py`](../inti/tahap2_loader.py).

## Bentuk sheet

- **Satu baris = satu usaha = satu dokumen.** Judul di baris 1, data mulai baris 2.
- Tab bernama `input_usaha` (juga diterima: `input_tahap2`, `tahap2`; kalau tidak ada, tab pertama).
- Judul kolom harus **persis** (huruf besar/kecil & spasi bebas); urutan bebas; kolom `24.Total`
  muncul dua kali (pertama = L+P, kedua = dibayar+tidak dibayar).
- **Semua sel berformat Teks** — NIK, idsubsls & KBLI rusak kalau jadi Angka di Excel.
- Kolom berkode diisi **angka kode opsi** (`12b` = `2` → "2. Perempuan"). Teks (`L`, `P`, `YA`,
  `TIDAK`, `2. PEREMPUAN`) juga dikenali. Kode tak dikenal → baris ditolak, tidak ditebak.
- Uang boleh `Rp10.500.000` atau `10500000`; koordinat boleh koma (`-8,2004731`).
- Kolom **"ID Dokumen FASIH"** (paling kanan) diisi skrip begitu dokumen dibuat — jangan diubah.
- Baris yang kolom `Uraian:`-nya diawali **`CONTOH`** selalu ditolak (baris contoh templat).

## Kolom

| Kolom | Rincian | Isi |
| --- | --- | --- |
| `Sumber/Kec.`, `Periode`, `Uraian:` | info | bebas, tidak dikirim |
| `Nama PPL` | petugas | nama (untuk rekap per PPL; login memakai `--akun-tunggal`) |
| `3`, `4` | kecamatan, desa | info `<nama> <kode>` |
| `5` | 5–7 wilayah | idsubsls 16 digit **wilayah asli** usaha |
| `8b.` | nama usaha | nama dokumen jadi `<8b> (<12a>)`, maks 50 karakter |
| `8c.` | alamat | Nama Jalan SE2026-P (≥ 10 huruf; pendek dilengkapi nama wilayah) |
| `no WA` | 12e HP | `08…` 10–13 digit; tidak ada → `9999` |
| `12a`, `12b`, `12c`, `12d` | pengusaha | nama; `1` L / `2` P; umur 10–99; NIK 16 digit atau `7777`/`8888`/`9999` |
| `13a`, `13f` | kegiatan & produk utama | 13a ≥ 15 karakter, 13f ≥ 4 (pendek dilengkapi judul KBLI) |
| `14a` | jaringan usaha | `1` Tunggal … `6` Unit pembantu |
| `16a`, `16b1-b6` | internet | 16a `1`/`2`; 16b: 6 nilai `1,2,2,1,2,2`, atau `B1,B3`, kosong kalau 16a = 2 |
| `17b`, `21`, `22` | lingkungan, KDKMP, MBG | `1`/`2`; 22 = `1`–`5` (`5` tidak terlibat) |
| `24.L`, `24.P`, `24.Dibayar`, `24.Tidak dibayar` | pekerja | angka; L+P harus = dibayar+tidak dibayar |
| `25` | tahun mulai beroperasi | 4 digit; tahun berjalan → varian bulanan 30–33 |
| `26a`–`26e` | pengeluaran setahun | rupiah; 26c hanya perdagangan |
| `27a`, `27b`, `27d` | pendapatan setahun, % online | rupiah; 27d 0–100 |
| `28a`, `28b`, `28d` | aset tanah&bangunan, aset lain, luas tanah | rupiah, rupiah, m² |
| `24.Total` (2x), `Rp26`, `27c`, `28c` | pemeriksa | tidak dikirim; harus = jumlah rinciannya |
| `28c1` | info | tidak dikirim & tidak diperiksa |
| `Latitude`, `Longitude` | geotag | desimal; kosong → dokumen DRAFT |
| `Kode KBLI`, `Judul KBLI` | 13g | 5 digit KBLI 2025; judul dipakai melengkapi 13a |

**Kolom tambahan (opsional):** tambahkan di kanan kalau satu baris perlu jawaban selain bawaan —
nilai kolom selalu menang. Judul yang dikenali: `kodepos`, `Akun PPL`, `Blok/Nomor`, `8d.`, `10a`,
`10b`, `10c`, `11a`, `11d`, `13b1`–`13b4`, `13c`, `13d`, `13e`, `16c`, `17a`, `18`, `19a`–`19c`,
`20a`–`20c`, `23a`–`23c`, `29a`–`29f` (daftar & nilai bawaan di tab `petunjuk` templat).

## Rincian yang tidak ada di kuesioner kertas

Diisi `TAHAP2_DEFAULT` ([`inti/config.py`](../inti/config.py)) dan dicatat sebagai ASUMSI di kolom
`review_disarankan` audit. Ubah permanen dengan menimpa `TAHAP2_DEFAULT` di `inti/config_lokal.py`.

| Rincian | Bawaan |
| --- | --- |
| 8d jenis kawasan | `10. Di luar kawasan` |
| 10a NIB / 10c | `2. Tidak` / `3. Tidak memerlukan NIB` |
| 11a badan usaha / 11d catatan keuangan | `13. Bukan Badan Usaha` / `2. Tidak` |
| 13b1 / 13b2 / 13b3 | dari golongan KBLI: 10–33 produksi, 56 makan-minum, 45–47 menjual; lainnya Tidak → 13b4 |
| 13c tempat usaha | `4. Toko, ruko`; KBLI golongan 56 `5. Kedai, stan, tenda` |
| 16c, 18, 23a–23c | `2. Tidak` |
| 17a | `3. Tidak sama sekali` |
| 29 modal | pribadi 100% |

13b1 = Ya membuat form mewajibkan 13d & 13e → diisi judul KBLI (`TAHAP2_13DE_DARI_KBLI`), atau
tambahkan kolom `13d`/`13e`.

## Nilai yang diganti/dikoreksi skrip

Semua keputusan BPS Buleleng, masing-masing punya saklar di `inti/config.py` (timpa di config
lokal kalau kebijakan Anda berbeda) dan tercatat di `review_disarankan`.

| Keadaan di sheet | Perlakuan | Saklar |
| --- | --- | --- |
| umur / tahun operasi kosong | disalin dari usaha lain pemilik sama, sisanya `45` / `2019` | `TAHAP2_UMUR_KOSONG_JADI`, `TAHAP2_TAHUN_OPERASI_KOSONG_JADI` |
| HP / NIK tidak valid | `9999` | `TAHAP2_HP_TIDAK_VALID_JADI`, `TAHAP2_NIK_TIDAK_VALID_JADI` |
| 16b1-b6 satu kode `1` | Ya hanya utk b1, b4, b5 | `TAHAP2_16B_YA_TUNGGAL` |
| 16b 5 nilai / 16a Ya tanpa 16b Ya | b6 = Tidak / b6 = Ya | `TAHAP2_16B_LIMA_NILAI_B6`, `TAHAP2_16B_TANPA_YA_JADI_B6` |
| pekerja 24 tidak konsisten / kosong | ikut jenis kelamin pemilik / 1 pekerja | `TAHAP2_PEKERJA_IKUT_JK_PEMILIK`, `TAHAP2_PEKERJA_KOSONG_JADI_MINIMAL` |
| 26a > 0 tapi tidak ada pekerja dibayar | pekerja jadi dibayar | `TAHAP2_UPAH_ADA_PEKERJA_JADI_DIBAYAR` |
| total 26f / 27c = 0 atau di bawah minimal (100.000; bulanan 10.000) | dinaikkan ke minimal | `TAHAP2_PENGELUARAN_NOL_JADI_MINIMAL`, `TAHAP2_PENJUALAN_NOL_JADI_MINIMAL`, `TAHAP2_NAIKKAN_KE_MINIMAL` |
| KBLI B–F / 56 dengan 26c > 0, atau 26b = 0 | 26c → 26b; 26d → 26b | `TAHAP2_26C_KE_26B`, `TAHAP2_26B_NOL_AMBIL_DARI_26D` |
| usaha mulai tahun ini | 30–33 dari kolom 26–29, 31e AGUSTUS | `TAHAP2_ISI_VARIAN_BULANAN`, `TAHAP2_BULAN_OPERASI` |
| kolom total beda dgn rincian | rincian yang dikirim (form menghitung total) | `TAHAP2_TOTAL_BEDA` |
| koordinat rusak Excel (`-8.148.438`, bujur minus) | dipulihkan kalau pasti; sisanya DRAFT | `TAHAP2_KOTAK_KOORDINAT` |
| idsubsls `5100…` salah ketik | awalan diganti `KODE_KAB` | `TAHAP2_PERBAIKI_AWALAN_IDSUBSLS` |
| 8c / 13a kosong | nama wilayah / judul KBLI | `TAHAP2_JALAN_KOSONG_DARI_WILAYAH`, `TAHAP2_13A_KOSONG_DARI_KBLI` |
| nama BUMDes | 11a `6. BUM Desa`, 11d Ya, modal pemerintah | `TAHAP2_KOREKSI_BUMDES` |
| usaha pecahan (8b & 12a sama, 13f beda) | nama `<8b> <13f> (<12a>)` | `TAHAP2_PEMBEDA_13F_UTK_GANDA` |
| KBLI kategori P/U (ditolak form) | rekomendasi KBLI GenAI pertama | `KBLI_DITOLAK_PAKAI_GENAI` |
| keputusan per baris | ditulis di config lokal, dicocokkan idsubsls+8b+12a | `TAHAP2_KOREKSI_BARIS` |

Yang **tidak pernah** ditebak (baris ditolak `SKIP_DATA_*`): kode opsi tak dikenal, kolom wajib
hilang, total bukan-nol yang tidak cocok, baris identik (`BARIS_GANDA`), kodepos desa tak
diketahui, nama > 50 karakter.

## Kodepos

Urutan sumber: kolom `kodepos` sheet → `KODEPOS_BY_IDSUBSLS` → `KODEPOS_BY_DESA` (10 digit
pertama idsubsls) → `--kodepos`. Semua kosong → `SKIP_DATA_KODEPOS_TIDAK_DIKETAHUI`. Isi
`KODEPOS_BY_DESA` di `inti/config_lokal.py` (atau `input_usaha/kodepos_desa.py`).

## Nama dokumen & identitas baris

Nama dokumen, SE2026-P & 8b = `<8b> (<12a>)`; lebih dari 50 karakter diringkas, masih lebih →
ditolak. Identitas baris di audit (`kunci`) = hash akun + idsubsls + 8b + 12a (+ pembeda 13f) —
jadi **jangan mengubah 8b/12a baris yang sudah punya dokumen**; kolom "ID Dokumen FASIH" menjaga
baris itu tetap dikenali.

## Koordinat

Latitude & Longitude terisi → geotag + dikirim. Kosong/`-`/`0`/rusak → dokumen diisi lengkap
**kecuali geotag** lalu ditahan DRAFT (`DRAFT_TANPA_KOORDINAT`), tidak pernah dikirim. Setelah
koordinat diisi, jalankan ulang dengan `--lewati-selesai`: draft yang sama dibuka, di-geotag,
dikirim. Koordinat salah/di luar subsls: [`koordinat/`](../koordinat/).
