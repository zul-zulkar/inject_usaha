
# Catatan Progres: Otomatisasi Input Usaha Pecahan SE2026

## Konteks tugas

User (Tes, BPS Buleleng) minta otomatisasi input "usaha pecahan" ke fasih-web berdasarkan data di Google Sheet sumber. PENTING dari user: koneksi (VPN/ekstensi Chrome) sering putus-nyambung — kerja HARUS cepat & sering klik tombol SAVE manual (ikon disket biru di floating toolbar kanan halaman fasih-web, sekitar koordinat kanan-bawah layar) supaya progres tidak hilang kalau sesi terputus.

- Sheet sumber: https://docs.google.com/spreadsheets/d/1SIterYlfHh41wSmBLrUuQT_A3iLH9eyUEV2uh7MVHEg
- Tempat input: https://fasih-web.bps.go.id/survey/a0429e96-51a5-477b-a415-485f9c153004/{assignment_id}
- Login fasih-web: klik "SSO Eksternal" di halaman /login, username = kolom M sheet (Email PPL), password = 'Mitra5108' (sama semua)
- Perlu VPN kantor aktif. Browser automation pakai Claude in Chrome extension (mcp__claude-in-chrome__*) yang jalan di Chrome asli user (bukan "browser pane" bawaan remote-devices yang ternyata TIDAK bisa akses fasih-web meski VPN aktif di Chrome asli — sudah dikonfirmasi user).
- Target awal: 3 record yang kolom B & C-nya sudah terisi (No 2510, 2511, 2512). Sisanya (No 2513+) kolom B & C kosong — itu backlog untuk otomatisasi.

## ⚠️⚠️ TEMUAN KRITIS: Tombol Save TIDAK bisa diandalkan lintas reload/logout

Pada percobaan pertama record 1: sudah klik Save manual berkali-kali dan selalu muncul konfirmasi "Berhasil simpan". TAPI setelah terpaksa force-reload halaman (lihat bug KBLI di bawah) yang berujung logout paksa, dan setelah login ulang + buka lagi dokumen yang sama: **SELURUH isian SE2026-P dan SE2026-L BLOK II kembali kosong/"Belum Diisi" (0%)**, padahal sudah berkali-kali "berhasil" di-save sebelumnya.

Kesimpulan: tombol Save "Berhasil simpan" nampaknya TIDAK cukup jadi jaminan data benar-benar persisten di server — mungkin hanya update state client-side/draft. **Implikasi paling penting: JANGAN PERNAH reload/force-navigate halaman dokumen fasih-web di tengah pengisian** (lihat juga bug KBLI di bawah, yang jadi penyebab awal kejadian ini). Klik Save tetap dilakukan berkala sesuai instruksi user, tapi jangan dianggap sebagai jaring pengaman mutlak — safeguard utama adalah TIDAK PERNAH reload/logout, bukan rajin nge-save.

**PENGECUALIAN yang sudah terbukti aman (record 3)**: kalau dokumen BARU DIBUAT dan BELUM ada data terisi sama sekali (nol progres), lalu navigasi ke dalamnya kena error transient 403/504 — aman untuk navigasi ulang via list "Entri" atau klik tombol "Refresh Halaman" di error page, KARENA tidak ada progres yang bisa hilang. Aturan "jangan reload" berlaku ketat HANYA setelah ada data yang sudah diisi (belum tentu ke-submit ke server).

**Status list dokumen bisa tampil STALE sesaat setelah submit** — setelah redirect ke halaman PENDATAAN pasca-Kirim, baris dokumen yang baru saja disubmit sempat masih tampil status lama ("DRAFT") sebelum di-refresh. **WAJIB klik "Muat Ulang" di halaman list dan screenshot ulang sebelum menyimpulkan submit sukses/gagal** — jangan percaya screenshot pertama langsung setelah redirect.

## ⚠️ BUG field 13g Kode KBLI — dropdown search kadang tidak filter dgn benar (transient, bisa muncul berkali² dalam satu sesi)

Field "13.g Kode KBLI" → setelah pilih radio "Pilih dari Master KBLI", muncul dropdown searchable. Dua varian bug yang pernah muncul dalam sesi yang sama (jadi BUKAN cuma sekali per sesi/per-login, bisa kambuh):

1. **Total broken** (record 1, percobaan pertama): apapun diketik → selalu "Pilihan tidak ditemukan". Fix yang berhasil: logout & login ulang (sesi baru).
2. **Search tidak memfilter** (record 3): mengetik kode "47772" di search box malah menampilkan daftar KBLI acak/tidak relevan (mis. "Pertanian Tanaman Bunga") alih-alih hasil yang sesuai — BUKAN "tidak ditemukan", tapi hasil salah/tidak terfilter. Fix yang berhasil TANPA logout ulang: klik tombol "X" utk clear (memicu dialog "Konfirmasi Hapus Pilihan" → klik "Ya", kadang perlu 2x klik krn dialog reposisi), lalu klik ulang ke field, `ctrl+a` + `Delete` (biasanya nyisa 1 karakter "a" nyasar), lalu `ctrl+a` + `Backspace` lagi utk benar2 bersih, BARU ketik ulang search term yang lebih deskriptif (mis. bukan cuma kode angka "47772" tapi frasa dari nama kategori "gas tabung LPG") — cara ini langsung berhasil dapat hasil yang benar & terfilter dgn baik.

**Rekomendasi kode otomatisasi**: JANGAN cuma ketik kode KBLI mentah ke search box lalu asumsikan hasil pertama benar — WAJIB verifikasi teks hasil match mengandung kode & nama yang diharapkan sebelum klik. Kalau hasil tidak relevan/tidak terfilter: clear field dgn urutan (klik X → konfirmasi Ya kalau muncul dialog → klik field lagi → ctrl+a+Delete → ctrl+a+Backspace) lalu retry dgn search term berbeda (coba nama/frasa kategori, bukan cuma kode angka) sebelum menyerah & re-login. Selalu klik di luar dropdown/field lain setelah pilih hasil utk memastikan dropdown ter-close & value ter-set (screenshot verifikasi).

## Struktur kolom Google Sheet sumber (header row)

A=link (ke fasih-sm.bps.go.id, sumber data asli), B=nama_usaha_pecahan (nama usaha baru), C=kbli_pecahan (KBLI baru), D=No, E=assignment_id, F=index1, G=idsubsls (16 digit: prov2+kab2+kec3+desa3+sls4+subsls2), H=nama_kepala_keluarga, I=PIC, J=Nama PML, K=Nama PPL, L=Email PML, M=Email PPL (**akun SSO login**), N=keberadaan_keluarga, O=nama_usaha_di_bangunan, P=nama_usaha_di_keluarga (**nama roster acuan sumber L Blok II**), Q=(kosong), R=skala_usaha, S=kbli_akhir, T=kategori, U=kategori_2025, V=keberadaan_usaha, W=latitude, X=longitude, Y=nik (nik kepala keluarga, BUKAN utk field NIK dok baru), Z=tk_dibayar, AA=tk_tdk_dibayar, AB=nilai_pendapatan, AC=pendapatan_lain, AD=gaji, AE=biaya_produksi, AF=biaya_pembelian, AG=operasional, AH=non_operasional, AI=total_pengeluaran, AJ-AQ=versi _bln (kosong di 3 record awal), AR=aset_usaha_thn, AS=aset_lain_thn, AT=total_aset_thn, AU-AW=versi _bln (kosong), AX=luas_tanah_thn, AY=luas_tanah_bln (kosong).

## Aturan pengisian dokumen baru (dari user) — FINAL, sudah diverifikasi konsisten dgn data sumber & 3x eksekusi penuh (SEMUA 3 record sukses terkirim)

1. Wilayah dokumen baru = wilayah sesuai idsubsls.
2. Nama Keluarga/Bangunan/Usaha (saat "+Dokumen Baru", DAN field "Nama Bangunan/Usaha/Perusahaan" di SE2026-P) = kolom B (nama_usaha_pecahan). Form otomatis UPPERCASE nama saat disimpan (kosmetik saja, bukan masalah).
3. Salin SEMUA isian dari sumber (Blok II yg match kolom P) ke dokumen baru BLOK II — copy as-is utk SEMUA field (termasuk 8b Nama komersial, 13a/13b/13c/13f — TETAP disalin literal dari sumber meski KBLI-nya beda, ini instruksi eksplisit user) KECUALI pengecualian di bawah. **Termasuk field teks bebas seperti 12a Nama Pengusaha — salin PERSIS ejaan di field sumber, JANGAN pakai nama dari label roster sidebar/kolom P sheet kalau beda ejaan (contoh nyata: roster/kolom P record 2 tertulis "KETUT SUDANING" tapi field 12a sumber aslinya "KETUT SUDIANING" — pakai yang di field, bukan roster; record 3 kebetulan SAMA persis "NI MADE DWIPAYANI"). WAJIB di-zoom & verifikasi manual tiap kali, jangan diasumsikan sama maupun beda.**
4. Rincian 13g (Kode KBLI) → pakai kolom C (kbli_pecahan). Sebelum isi, klik dulu tombol **"Pilih dari Master KBLI"**. ⚠️ Lihat catatan bug search di atas — WAJIB verifikasi hasil match sebelum klik.
5. Rincian 26(a-e), 27(a,b), 28b = **10% dari nilai asli sumber**. Kalau hasil 10% tidak bulat (desimal), bulatkan ke rupiah terdekat (round half up) — field currency tidak menerima desimal. **⚠️ Field rincian 26 yang MUNCUL di form bergantung pada KATEGORI/golongan KBLI dokumen BARU (bukan KBLI sumber)** — lihat catatan "Field 26 kondisional per kategori KBLI" di bawah. Field 26f/27c/28c/24c1/24c2 auto-terhitung TAPI kadang butuh 1 tindakan blur/klik-elsewhere ekstra sebelum nilai auto ter-update di tampilan (jangan panik kalau immediately setelah ngetik totalnya masih keliatan versi lama — screenshot ulang setelah pindah field).
6. 28a & 28d = **0** (tetap, abaikan sumber).
7. Rincian 12d NIK = **'9999'** (fixed).
8. "Pilih UMKM dalam satu SLS yang sama" = **'Tidak ada'** (satu2nya opsi yg tersedia di dropdown, konsisten di 3 record).
9. "Nama Pemberi Informasi" (Keterangan Pemberi Jawaban) = **'Lainnya'**.
10. SE2026-P "Tambah:" = **"Bangunan Lainnya (Selain Tempat Tinggal dan Campuran)"** (konfirmasi user). "Keberadaan Bangunan Lainnya/Usaha" = **"2. Baru"** (konfirmasi user). Field "Daftar Usaha Non Prelist" (muncul setelah pilih Bangunan Lainnya) = **kosongkan saja** (konfirmasi user — daftar memang selalu kosong utk wilayah ini, tidak ada opsi "Tidak Ditemukan" yang bisa diklik).
11. Memilih "Bangunan Lainnya" di SE2026-P membuat alur dokumen SKIP Blok I (Keterangan Umum Keluarga) — langsung SE2026-P → SE2026-L BLOK II → KETERANGAN PEMBERI JAWABAN → CATATAN. Ini benar & sesuai maksud (dokumen usaha pecahan tidak perlu bikin keluarga baru).
12. Koordinat geotagging pakai kolom W (latitude) & X (longitude) dari sheet, input manual di modal "Pilih Lokasi" (dibuka via tombol **"Ambil Lokasi"** di section Geotagging, bagian bawah SE2026-P setelah "Kode Penggunaan Bangunan" — bukan langsung tombol "Pilih Lokasi", itu nama modalnya). Isi field Latitude & Longitude manual (select-all dulu isi default Jakarta sblm timpa), klik "Gunakan Lokasi" (1x klik di modal peta awal → muncul preview pin di peta placeholder → klik "Gunakan Lokasi" lagi di step preview) → muncul dialog konfirmasi "Ambil Lokasi" ("Apakah Anda yakin ingin mengambil lokasi saat ini?") → klik "Ya". Setelah sukses, section Geotagging menampilkan peta asli + Latitude/Longitude/Akurasi + toast "Berhasil mengambil lokasi".
13. Di bagian akhir dokumen (CATATAN), field "Waktu Selesai" diisi via tombol "Ambil Waktu" → konfirmasi "Ya" pada dialog. Field "Catatan" (textarea) dibiarkan kosong (opsional, tidak wajib). Di PENGANTAR, field "Waktu Mulai" DAN "Waktu Kunjungan I" masing2 diisi via tombol "Ambil Waktu"-nya sendiri (keduanya harus diisi). "Catatan Kunjungan I" dibiarkan kosong (ini yang muncul di KOSONG list, memang opsional).
14. Sebelum klik "Kirim" final: cek dialog ringkasan (GALAT/PERINGATAN/CATATAN/KOSONG) — GALAT harus 0. PERINGATAN & KOSONG boleh ada asal sudah dicek satu-satu memang opsional/sesuai data (bukan field wajib yang kelewat). Field "KOSONG" berlabel "(Diisi oleh PML)" MEMANG harus kosong (bukan tugas PPL). **Submit/Kirim adalah action irreversible — SELALU minta konfirmasi eksplisit user dulu sebelum diklik, untuk SETIAP record (izin di 1 record tidak otomatis berlaku ke record lain).**
15. **IDENTITAS WILAYAH (BLOK I) — field WAJIB yang mungkin tidak konsisten muncul/diingat**: "8. Apakah mengalami perubahan SLS (pemekaran/penggabungan/perubahan nama/perubahan batas)?" → jawab **"2. Tidak"**. "10. Kodepos" → isi sesuai kodepos SLS setempat (utk SLS 5108080008000202 = **"81172"**). Field "Wajib diisi" yang masih muncul persis setelah ngetik = normal (belum ter-blur), klik elsewhere/label field utk trigger validasi ulang & hilangkan pesan error.
16. **SE2026-P — section "Alamat" & bangunan**: setelah field "Keberadaan Bangunan Lainnya/Usaha", ada section "Alamat" dgn 2 field: **"Nama Jalan/Gang/Komplek/Gedung/dll"** (textarea, isi dgn bagian NAMA JALAN dari 8c Alamat sumber, mis. "BANJAR DINAS KAJA KANGIN") dan **"Blok/Nomor Rumah"** (isi "**-**" kalau sumber alamatnya diakhiri strip/no nomor rumah, sesuai instruksi placeholder "Jika tidak ada nomor rumah, tulis strip (-)"). **PENTING: field ini OTOMATIS MENGISI field "8.c Alamat usaha/perusahaan" di BLOK II nanti** (terverifikasi: begitu masuk BLOK II, 8c sudah pre-filled dgn gabungan "NAMA JALAN -" tanpa perlu isi ulang manual). Setelah itu ada field readonly **"NOMOR URUT BANGUNAN TERBESAR:"** (referensi nomor urut bangunan terbesar yg sudah tercatat utk alamat/segmen ini, biasanya kosong/tidak ada info kalau belum ada bangunan lain tercatat) dan field **"Nomor Urut Bangunan"** (spinbox number) — **lihat ⚠️ KOREKSI PENTING di bawah, JANGAN asal ikuti catatan lama "biarkan kosong" tanpa baca nuance-nya**. Terakhir **"Kode Penggunaan Bangunan"** (radio, defaultnya SUDAH otomatis ter-pilih **"1. Bangunan Khusus Usaha"** — tidak perlu diubah, biarkan default). Baru setelah itu section "Geotagging" (lihat poin 12).

### ⚠️ KOREKSI PENTING (ditemukan di record 3 saat cek ringkasan pra-Kirim): nuance field "Nomor Urut Bangunan"

Field ini AMAN dibiarkan **benar-benar pristine/tidak pernah disentuh sama sekali** (tidak diklik, tidak difokus) — dalam kondisi itu, di list dokumen PENDATAAN field ini tampil sbg "-" dan TIDAK memicu GALAT maupun error apapun (ini persis kondisi record 1 & 2 yang sukses submit tanpa masalah).

TAPI begitu field ini sempat ter-klik/fokus (termasuk hanya klik chevron spinner-nya, walau cuma sekali coba-coba), nilai underlying-nya TIDAK bisa balik jadi benar-benar null lagi — ia tersimpan sbg literal angka **0**. Ini SERING TIDAK ketahuan sbg error inline saat itu juga di field-nya (kadang muncul kadang tidak), tapi PASTI ketahuan sbg **GALAT** (bukan cuma PERINGATAN) "Tidak boleh kurang dari 1" saat buka dialog ringkasan sebelum Kirim — dan **GALAT wajib 0 sebelum tombol Kirim final bisa dipakai**. Ini persis yang terjadi di record 3 (sempat ke-klik chevron saat eksplorasi awal sesi, videnya baru ketahuan berminggu-minggu kemudian saat cek ringkasan — GALAT=1).

**Fix kalau sudah terlanjur ke-set 0 (mustahil balik ke null via clear/delete)**: isi dengan angka valid ≥1, BUKAN coba dikosongkan lagi. Caranya (instruksi eksplisit user): cek dulu field readonly "NOMOR URUT BANGUNAN TERBESAR" di atasnya — **kalau field itu ADA isi angkanya, lanjutkan dari situ+1; kalau field itu KOSONG/tidak ada info** (spt kasus record 3), **isi dengan 1**. Cara paling aman mengisi: klik tombol chevron "▲" (naik) di sebelah field, yang akan increment nilai saat ini +1 per klik (dari 0 → 1 dgn 1x klik) — pengetikan manual (`type`/`key`) sempat tidak bisa dipakai saat terjadi gangguan sementara pada classifier tool, tapi klik chevron/tombol biasa tetap berfungsi normal, jadi ini juga fallback yang lebih robust drpd bergantung pada keyboard input.

**Efek samping ke hitungan KOSONG**: kalau field ini pristine/kosong, ia ikut terhitung sbg 1 item legitimate di daftar KOSONG (makanya record 1 & 2 total KOSONG=20). Kalau field ini akhirnya diisi angka (spt record 3 diisi "1"), ia TIDAK lagi terhitung KOSONG, jadi totalnya 1 lebih sedikit (record 3 KOSONG=19). **Kesimpulan: total KOSONG boleh beda 1 tergantung status field ini — ini NORMAL, bukan tanda ada yang salah**, selama semua item lain di list KOSONG tetap field vestigial yang sama & sudah divet aman.

**Kesimpulan utk kode otomatisasi**: default teraman = JANGAN PERNAH interact dgn field "Nomor Urut Bangunan" sama sekali (no click, no focus, no scroll_to bahkan) kecuali memang berniat mengisinya. Kalau tooling (mis. Playwright) tanpa sengaja fokus/klik field ini, WAJIB set ke angka valid ≥1 (cek referensi "NOMOR URUT BANGUNAN TERBESAR", default 1 kalau kosong) sebelum submit — jangan coba mengosongkan balik, dan WAJIB selalu cek GALAT=0 di ringkasan pra-Kirim sebagai pengaman terakhir (jangan asumsikan field ini otomatis aman tanpa dicek).

## ⚠️ Field rincian 26 (Pengeluaran) kondisional per kategori KBLI dokumen baru

Ditemukan di record 2 (KBLI baru=56304, kategori I/golongan 56 — Aktivitas Kedai Minuman): form rincian 26 HANYA menampilkan **26a (upah&gaji), 26b (biaya produksi), 26d (operasional), 26e (non-operasional)** — field **26c (biaya pembelian) TIDAK MUNCUL SAMA SEKALI** di form (beda dgn record 1 & record 3 yg KBLI-nya kategori G/Perdagangan, form-nya munculkan 26a-e lengkap termasuk 26c). Field 26f "Total (a+b+c+d+e)" tetap berlabel sama tapi cuma menjumlah field yg ada di form.

Bukti pendukung: saat 26b masih 0, form menampilkan warning eksplisit "Biaya produksi harus>0 jika kategori usaha B-F dan I (gol 56)" — mengonfirmasi bahwa utk kategori I golongan 56, nilai yg secara sumber tercatat sbg "biaya pembelian" harus dimasukkan ke **26b Biaya Produksi** (bukan field terpisah), karena kategori jasa (makan/minum) tidak punya konsep "beli barang dagangan utk dijual lagi" seperti kategori Perdagangan.

**Aturan turunan (dipakai utk record 2, TERAPKAN utk record 2013+/otomatisasi)**: kalau kategori KBLI dokumen BARU termasuk B-F atau I (gol 56) DAN form tidak menampilkan field 26c terpisah → gabungkan nilai sumber biaya_produksi(AE) + biaya_pembelian(AF) → kali 10% → masukkan ke **26b**, bukan ke field terpisah yg tidak ada. Kalau kategori G (Perdagangan) & field 26c muncul di form → pakai mapping normal (26b=biaya_produksi×10%, 26c=biaya_pembelian×10%, terpisah, boleh 26b=0 kalau sumber biaya_produksi=0). **Untuk kode otomatisasi: cek dulu field mana yg benar2 dirender di form (bukan asumsi dari kategori sumber), baru tentukan pemetaan nilai** — kategori render-nya dikonfirmasi via field **"13.h Kategori Lapangan Usaha"** yg AUTO TERISI (readonly, misal "G") begitu KBLI dipilih di 13g, jadi bisa dibaca programatis sebelum decide mapping 26.

## ⚠️ Field rincian 20 (izin edar BPOM) kondisional per kategori KBLI — dan field 20c "jumlah varian belum BPOM" ikut wajib walau 20a="Tidak"

Kategori G (record 1 & 3): field 20a MUNCUL. Kategori I gol 56 (record 2): field 20 TIDAK MUNCUL SAMA SEKALI. Kalau 20a dijawab **"3. Tidak"** (usaha tidak punya izin edar sama sekali), form TETAP memunculkan field lanjutan **"20.c Berapa jumlah varian produk yang belum memiliki izin edar BPOM?"** (wajib diisi, numeric) — diisi **"1"** di record 1 & record 3 (konsisten, karena "produk" utamanya dianggap 1 varian). Field "20b Ya, bukan oleh BPOM" tampaknya juga bisa memunculkan turunan field lain tapi belum pernah dipilih di 3 record ini (semua sumbernya "3. Tidak").

## Pola UX penting yang berulang di fasih-web / fasih-sm

- Field dropdown/combobox searchable yang mau di-clear via tombol X kadang memunculkan dialog "Konfirmasi Hapus Pilihan" (Apakah Anda yakin ingin menghapus semua pilihan?) — klik "Ya" (kadang perlu 2x klik, klik pertama suka tidak kepencet krn dialog reposisi/re-render).
- Setelah ctrl+a+Delete pada field combobox/dropdown search, kadang tersisa 1 karakter "a" nyasar — bersihkan dgn ctrl+a+Backspace lagi sebelum ketik ulang.
- Field kondisional (radio yang baru muncul setelah menjawab pertanyaan sebelumnya, ATAU total/auto-calc field yg baru muncul setelah semua sub-field terisi) SERING menggeser layout field-field di bawahnya — begitu juga munculnya/hilangnya teks error "Wajib diisi" di bawah sebuah field numerik begitu field itu diisi (menggeser field-field berikutnya ke atas/bawah). **JANGAN batch-click/type banyak field sekaligus berdasarkan koordinat dari screenshot lama** — screenshot ulang / verifikasi setelah tiap klik yang berpotensi memunculkan/menghilangkan konten, baru klik field berikutnya. Kasus nyata berulang (record 2 & record 3): batch klik/type berturut-turut berdasar 1 screenshot lama → sebagian klik meleset krn layout shift; harus diperbaiki satu-satu dgn screenshot ulang tiap klik yg berpotensi shifting. Field radio SEDERHANA yg TIDAK memunculkan apa2 baru (mis. dua radio group independen yg sama2 sudah visible penuh di layar) AMAN di-batch bersamaan.
- **Solusi lebih robust utk field beruntun (spt rincian 26-29 finansial, atau navigasi sidebar fasih-sm)**: pakai `read_page` (filter interactive) atau tool `find` untuk dapat elemen `ref_N`, lalu klik/scroll_to pakai `ref` bukan koordinat pixel. Ini terbukti jauh lebih tahan terhadap layout shift & lebih reliable drpd koordinat (koordinat sidebar fasih-sm pernah gagal total berkali-kali, langsung sukses begitu pakai `ref` dari `find`). Sangat direkomendasikan utk kode otomatisasi Playwright nanti (pakai selector/locator berbasis label field, bukan posisi pixel) — Playwright locator berbasis label/nearby-text jauh lebih robust drpd koordinat pixel yg dipakai browser-automation manual ini.
- **`read_page` (filter "all") TIDAK menampilkan status "checked" radio button dalam bentuk teks** — utk tahu radio mana yg terpilih tetap WAJIB screenshot visual (lingkaran terisi/oranye = terpilih). Tapi `read_page` SANGAT efisien utk baca semua VALUE textbox/field teks & angka sekaligus (jauh lebih hemat drpd screenshot per section) — kombinasikan: `read_page` dulu utk field teks/angka, baru screenshot bertahap utk field radio/pilihan ganda.
- Field fasih-sm (read-only) kadang render lambat & sempat stuck di "Loading Data..." beberapa detik (pernah sampai belasan detik) sebelum akhirnya render normal — bukan berarti benar-benar gagal/rusak, cukup tunggu/screenshot ulang beberapa kali sebelum menyimpulkan ada masalah nyata (JANGAN buru-buru reload/navigasi ulang).
- Tombol Save manual (ikon disket, floating toolbar kanan ~y=641) & indikator "Menyimpan..." — **lihat Temuan Kritis di atas soal reliabilitas sebenarnya**. Indikator ini juga kadang terlihat "stuck" beberapa detik sebelum hilang — normal, bukan berarti gagal.
- Sebelum submit final, tombol "Kirim" (pojok kanan atas) membuka dialog ringkasan (GALAT/PERINGATAN/CATATAN/KOSONG, masing2 bisa diklik utk lihat detail list-nya) → klik "Kirim" lagi di dialog itu → muncul dialog "Konfirmasi Kirim" ("Apakah Anda yakin ingin mengirimkan data ini?") → klik "Konfirmasi". Setelah sukses: toast "Perubahan tersimpan" lalu redirect otomatis ke halaman list PENDATAAN — **tapi status baris dokumen di list bisa tampil STALE ("DRAFT") sesaat sebelum di-refresh; WAJIB klik "Muat Ulang" & screenshot ulang utk verifikasi status final "SUBMITTED BY PENCACAH"/"CLEAN" via stats kartu ringkasan atas (Jumlah Dokumen/Progres/Clean/Error) sebelum menyimpulkan sukses**. Kalau dibuka lagi dokumennya, tombol "Kirim" di pojok kanan atas sudah berubah jadi "Ringkasan" (indikator dokumen sudah terkirim/locked, tidak bisa submit ulang). **Catatan klik**: kadang klik pertama pada tombol "Kirim" di dalam dialog ringkasan tidak langsung ter-register (dialog re-render/reposisi) — screenshot ulang & klik lagi kalau dialog ringkasan masih terbuka setelah diklik.
- **Dalam daftar detail KOSONG/PERINGATAN, beberapa item ditampilkan dgn nama field INTERNAL/cryptic (bukan label UI), mis. "alamat_sesuai", "pilih_keluarga_sls"** — item spt ini utk dokumen "Bangunan Lainnya" ternyata TIDAK punya elemen input yg terlihat sama sekali di halaman SE2026-P (klik ikon jump/panah cuma bawa ke section SE2026-P scr umum, tidak ke field spesifik). Kemungkinan besar field sisa dari template form "Keluarga" yg tidak dipakai di alur "Bangunan Lainnya". Sudah diverifikasi aman utk diabaikan: ketiga record (flow identik) konsisten total KOSONG ~19-20 (selisih 1 tergantung status field Nomor Urut Bangunan, lihat catatan di atas) & sama-sama sukses submit/diterima sistem.
- Google Sheets: klik/ketik di Name Box ("A1" box) TIDAK reliable utk navigasi cell via automation. **Solusi**: navigate langsung ke URL `https://docs.google.com/spreadsheets/d/<ID>/edit?gid=0#gid=0&range=CELL_ATAU_RANGE` — ini reliable jump & select ke cell/range yg dimaksud, baru screenshot/zoom utk baca isinya.
- Field teks bebas hasil copy dari sumber (13a, 13f, 8b, 12a, dll) harus di-**zoom** buat baca teks persis — dua field yang terlihat mirip bisa beda urutan kata ATAU beda spasi (contoh record 2: 13a="Menjual beras kopi gula makanan ringan" vs 13f="Menjual beras gula kopi makanan ringan" — urutan kata beda. Contoh record 3: 8a="WARUNG BU DEWI( NI MADE DWIPAYANI)" vs 8b="WARUNG BU DEWI (NI MADE DWIPAYANI)" — posisi spasi vs tanda kurung beda; sementara 13a & 13f record 3 justru SAMA PERSIS "Menjual makanan ringan" — jangan asumsi selalu beda, tetap cek satu2). BUKAN typo baca, field-nya memang independen.
- **URL assignment fasih-sm BUKAN `https://fasih-sm.bps.go.id/app/assignment/{kolom-E}` saja** — harus `https://fasih-sm.bps.go.id/app/assignment/{survey_assignment_id}/{kolom-E}`, di mana `{survey_assignment_id}` (mis. `fd68e454-ba45-4b85-8205-f3bf777ded24`) adalah ID level survei yg SAMA utk semua row & cuma kelihatan utuh di formula CONCATENATE kolom A sheet (klik cell kolom A yg sudah tau linknya benar → baca formula bar, bukan nilai tampilan yg terpotong). Kalau langsung pakai kolom E saja → 404 Not Found.
- **Error transient 403/504 tepat setelah "+Dokumen Baru" berhasil dibuat** (toast "Dokumen baru berhasil dibuat" & Jumlah Dokumen bertambah, TAPI auto-navigasi ke halaman entry dokumen baru gagal dgn "Terjadi Kesalahan (403) - Forbidden" atau stuck loading lalu "(504) Service unavailable"): karena dokumen sudah confirmed ada di server & belum ada data terisi (nothing to lose), AMAN utk: (a) navigasi manual ke URL list PENDATAAN survey, cari dokumen via search nama, klik link "Entri"-nya; kalau masih gagal (b) klik tombol "Refresh Halaman" di error page itu sendiri — kedua approach terbukti berhasil pulih ke halaman PENGANTAR kosong yg normal. Ini PENGECUALIAN thd aturan umum "jangan reload dokumen" (lihat Temuan Kritis di atas) — pengecualian berlaku HANYA saat dokumen benar2 masih kosong/0% progres.
- **Browser automation tool (Chrome extension) bisa sempat gangguan transient**: pernah terjadi action `type`/`key` gagal berulang dgn error "temporarily unavailable (timed out)... classifier" selama ~1-2 menit, SEMENTARA action `click`/`screenshot`/`triple_click`/`scroll`/`wait` tetap normal jalan selama itu. **Workaround yang terbukti berhasil**: kalau butuh mengubah value field numeric spinner & `type`/`key` sedang gangguan, pakai klik tombol chevron ▲/▼ (increment/decrement) sbg pengganti — ini pure click action, tidak kena gangguan yg sama. Untuk kode otomatisasi Playwright nanti ini tidak relevan (Playwright tidak lewat classifier tool ini), tapi berguna dicatat sbg pola debugging kalau sesi manual serupa terulang.

## Data LENGKAP record 1 (No 2510) — Warung Aqua Galon (I KETUT SUTARJANA), dokumen e2e96e1a-e9c9-4cbe-9cda-cd593597e717 — ✅ SUDAH TERKIRIM/SUBMIT SUKSES

idsubsls=5108080008000202 | kbli_pecahan(C)=47222 "Perdagangan Eceran Minuman Tidak Beralkohol" | login SSO=sriwidianikomang319@gmail.com/Mitra5108

Field → nilai (sudah termasuk hasil kalkulasi 10% & override) — **SEMUA FIELD DI BAWAH INI SUDAH TERISI, TERSIMPAN, & BERHASIL DIKIRIM**:

- Pilih UMKM dlm 1 SLS = Tidak ada
- Keberadaan Usaha (rincian 8) = 2. Baru
- 8b Nama komersial = WARUNG PAK SUTARJANA(KETUT SUTARJANA) [copy literal dari sumber, BUKAN nama pecahan]
- 8c Alamat = "BANJAR DINAS KAJA KANGIN -" | RT=00 | RW=00 | Kode Pos=(kosong) | Kode Area=(kosong) | No Telepon=(kosong) | Ekstensi=(kosong) | Email=(kosong) | No HP/WA=082144118789 | Homepage=(kosong)
- 8d Jenis kawasan = 10. Di luar kawasan
- 9a Jenis usaha = 1. Usaha di dalam bangunan tempat tinggal (catatan: field ini TIDAK muncul di alur "Bangunan Lainnya" record 3 — kemungkinan field 9 hanya utk alur "Keluarga")
- 10a NIB = 2. Tidak | 10c alasan = 3. Tidak memerlukan NIB
- 11a status badan usaha = 13. Bukan Badan Usaha | 11d laporan keuangan = 2. Tidak
- 12a Nama Pengusaha = I KETUT SUTARJANA | 12b Jenis Kelamin = 1. Laki-laki | 12c Umur = 72 | **12d NIK = 9999 (override)**
- 13a kegiatan utama = "Menjual makanan ringan" (copy literal) | 13b1(memproduksi barang di lokasi)=2.Tidak | 13b2(layanan makan minum)=2.Tidak | 13b3(penjualan barang)=1.Ya | 13c tempat usaha=4. Toko, ruko, dan sejenisnya | 13f produk utama="Makanan ringan" (copy literal) | **13g KBLI = 47222 Perdagangan Eceran Minuman Tidak Beralkohol — BERHASIL diisi via Master KBLI setelah login ulang** | 13h auto=G
- 14a jaringan usaha = 1. Tunggal
- 16a pakai internet = 2. Tidak
- 17a produk ramah lingkungan = 2. Ya, sebagian | 17b input ramah lingkungan = 1. Ya
- 18 karya seni/budaya = 2. Tidak
- 20a izin edar BPOM = 3. Tidak | 20c jumlah varian belum BPOM = 1
- 21 mitra KDKMP = 2. Tidak
- 22 program MBG = 5. Tidak terlibat MBG
- 23a/23b/23c (transaksi bukan penduduk Indonesia) = 2. Tidak / 2. Tidak / 2. Tidak
- 24a1 pekerja laki2=1 | 24b1 pekerja perempuan=1 | 24c1 total=2(auto) | 24a2 pekerja dibayar=0 | 24b2 pekerja tdk dibayar=2 | 24c2 total=2(auto)
- 25 tahun mulai komersial = 1995
- 26a upah&gaji = 0 | 26b biaya produksi = 0 | 26c biaya pembelian = 16.800.000 | 26d operasional = 240.000 | 26e non-operasional = 60.000 | 26f total=auto(17.100.000)  [kategori G, semua field 26a-e muncul]
- 27a nilai penjualan = 20.700.000 | 27b pendapatan lain = 0 | 27c total=auto(20.700.000)
- 28a aset tanah&bangunan = 0 (override) | 28b aset selain tanah&bangunan = 1.000.000 | 28c total=auto(1.000.000) | 28d luas tanah = 0 (override)
- 29a Pribadi/Perorangan = 100 (%) | 29b-f = 0 | 29g auto=100%
- Nomor Urut Bangunan (section SE2026-P) = **dibiarkan pristine/kosong** (tampil "-" di list dokumen, tidak memicu GALAT — lihat nuance lengkap di rule 16)
- KETERANGAN PEMBERI JAWABAN: Nama Pemberi Informasi = Lainnya, Nomor HP & E-mail dikosongkan, checkbox pernyataan data benar = dicentang.
- CATATAN: Waktu Selesai diambil via "Ambil Waktu" (31 Agustus 2026, 20:34:56). Catatan text dikosongkan.
- Ringkasan sebelum Kirim: GALAT=0, PERINGATAN=1 (16a internet), KOSONG=20 (semua vetted legitimate).

## Data LENGKAP record 2 (No 2511) — Warung Minuman Ringan (KETUT SUYITNA), dokumen 9e07d2f4-c9ef-4eaf-8d95-e6952d3a4300 — ✅ SUDAH TERKIRIM/SUBMIT SUKSES

Sumber: WARUNG SEMBAKO (KETUT SUDANING), assignment fd68e454-ba45-4b85-8205-f3bf777ded24/b7550c9c-9d89-45c2-91c9-2091b5c86970 | nama_usaha_di_keluarga(P)=WARUNG SEMBAKO ( KETUT SUDANING | kbli_akhir sumber=47112 (kategori G)

idsubsls=5108080008000202 | nama_usaha_pecahan(B)="Warung Minuman ringan (KETUT SUYITNA)" | kbli_pecahan(C)=56304 "[I][56304]Aktivitas Kedai Minuman" (kategori I, golongan 56) | latitude(W)=-8.12904166666666 | longitude(X)=115.200038333333334

**BLOK II — SEMUA FIELD BERIKUT SUDAH DIISI, TERSIMPAN, & BERHASIL DIKIRIM**:

- Pilih UMKM dlm 1 SLS = Tidak ada
- Keberadaan Usaha (rincian 8) = 2. Baru
- 8b Nama komersial = WARUNG SEMBAKO (KETUT SUDANING)
- 8c Alamat = "BANJAR DINAS KAJA KANGIN -" | RT=00 | RW=00 | No HP/WA=087853983370 | (sisanya kosong sesuai sumber)
- 8d Jenis kawasan = 10. Di luar kawasan
- 9a Jenis usaha = 1. Usaha di dalam bangunan tempat tinggal
- 10a NIB = 2. Tidak | 10c alasan = 3. Tidak memerlukan NIB
- 11a status badan usaha = 13. Bukan Badan Usaha | 11d laporan keuangan = 2. Tidak
- 12a Nama Pengusaha = KETUT SUDIANING (bukan "SUDANING" — sesuai field sumber asli) | 12b Jenis Kelamin = 2. Perempuan | 12c Umur = 56 | 12d NIK = 9999 (override)
- 13a = "Menjual beras kopi gula makanan ringan" | 13b1=2.Tidak | 13b2=2.Tidak | 13b3=1.Ya | 13c=4. Toko, ruko, dan sejenisnya | 13f = "Menjual beras gula kopi makanan ringan" | **13g KBLI = 56304 Aktivitas Kedai Minuman — berhasil via Master KBLI, search "kedai minuman"** | 13h auto=I
- 14a jaringan usaha = 1. Tunggal
- 16a pakai internet = 2. Tidak (memicu PERINGATAN standar, sama pola record 1)
- 17a produk ramah lingkungan = 3. Tidak sama sekali | 17b input ramah lingkungan = 2. Tidak
- 18 karya seni/budaya = 2. Tidak
- **Rincian 20 (izin edar BPOM) TIDAK MUNCUL SAMA SEKALI di form record 2** (beda dari record 1 yg tampilkan 20a/20c) — kondisional per KBLI, dilewati (tidak ada yg perlu diisi)
- 21 mitra KDKMP = 2. Tidak
- 22 program MBG = 5. Tidak terlibat MBG
- 23a/23b/23c = 2. Tidak / 2. Tidak / 2. Tidak
- 24a1 pekerja laki2=0 | 24b1 pekerja perempuan=1 | 24c1 total=1(auto) | 24a2 pekerja dibayar=0 | 24b2 pekerja tdk dibayar=1 | 24c2 total=1(auto)
- 25 tahun mulai komersial = 1989
- **26 (kategori I gol 56 — HANYA a,b,d,e muncul, TIDAK ada 26c terpisah)**: 26a upah&gaji=0 | 26b biaya produksi = **3.360.001** (gabungan biaya_produksi sumber=0 + biaya_pembelian sumber=33.600.008, ×10%=3.360.000,8→dibulatkan; system warning "Biaya produksi harus>0 jika kategori usaha B-F dan I (gol 56)" mengonfirmasi mapping ini benar) | 26d operasional = 100.000 (dari 1.000.000×10%) | 26e non-operasional = 50.000 (dari 500.000×10%) | 26f total=auto (3.510.001)
- 27a nilai penjualan = 5.310.000 (dari 53.100.000×10%) | 27b pendapatan lain = 0 | 27c total=auto (5.310.000)
- 28a = 0 (override) | 28b = 400.000 (dari 4.000.000×10%) | 28c total=auto (400.000) | 28d = 0 (override, sumber asli 15)
- 29a Pribadi/Perorangan = 100 (%) | 29b-f = 0 | 29g auto=100%
- Nomor Urut Bangunan (section SE2026-P) = dibiarkan pristine/kosong (sama pola record 1)
- KETERANGAN PEMBERI JAWABAN: Nama Pemberi Informasi = Lainnya, Nomor HP & E-mail dikosongkan, checkbox pernyataan data benar = dicentang.
- CATATAN: Waktu Selesai diambil via "Ambil Waktu" (31 Agustus 2026, 21:25:08). Catatan text dikosongkan.
- Ringkasan sebelum Kirim: 82 Jawaban total, GALAT=0, PERINGATAN=1 (16a internet, legitimate), KOSONG=20 (semua vetted legitimate, sama pola record 1).
- **Submit sukses**: user konfirmasi "kamu boleh langsung kirim dan pastikan clean ya" (via AskUserQuestion + pesan langsung) → klik Kirim → Kirim (dialog ringkasan) → Konfirmasi (dialog Konfirmasi Kirim) → toast "Perubahan tersimpan" lalu "Assignment berhasil dikirim" → redirect ke PENDATAAN list → verified via stats: Jumlah Dokumen=6, Progres Penyelesaian=100% (6 dari 6), Jumlah Clean=6, Jumlah Error=0.

## Data LENGKAP record 3 (No 2512) — Warung Gas Bu Dewi, dokumen 9167e0ba-67af-4d61-86ea-d7e0ffbb82f6 — ✅ SUDAH TERKIRIM/SUBMIT SUKSES

Sumber: WARUNG BU DEWI( NI MADE DWIPAYANI), assignment fd68e454-ba45-4b85-8205-f3bf777ded24/18f83fb6-5515-480e-86bb-8e9ad2ad02a0 | nama_usaha_di_keluarga(P)=WARUNG BU DEWI( NI MADE DWIPAYANI) | kbli_akhir sumber=47112 (kategori G) | kepala keluarga=I KETUT GANTEN

idsubsls=5108080008000202 | nama_usaha_pecahan(B)="Warung Gas Bu Dewi" | kbli_pecahan(C)=47772 → **KONFIRMED [G][47772] Perdagangan Eceran Gas Tabung LPG (kategori G, sama seperti dugaan)** | latitude(W)=-8.127656666666667 | longitude(X)=115.199408333334 → **geotagging BERHASIL diambil, tampil Latitude -8.127657 / Longitude 115.199408 di form**

**Proses pembuatan dokumen**: klik "+Dokumen Baru" (wilayah pre-filled sesuai idsubsls, nama diketik "Warung Gas Bu Dewi") → toast "Dokumen baru berhasil dibuat", Jumlah Dokumen 6→7 → auto-navigasi ke entry kena **403 Forbidden** → navigasi manual ke list PENDATAAN, cari "Dewi", klik "Entri" → kena **504 Service Unavailable** (stuck loading) → klik tombol "Refresh Halaman" di error page → BERHASIL, load PENGANTAR kosong normal. (Lihat pola UX di atas: aman krn dokumen msh 0% progres.)

**PENGANTAR**: Waktu Mulai = "31 Agustus 2026, 22:17:13" | Waktu Kunjungan I = "31 Agustus 2026, 22:17:28" | Catatan Kunjungan I = kosong.

**IDENTITAS WILAYAH**: semua field wilayah pre-filled/benar sesuai idsubsls, PLUS 2 field wajib: "8. Apakah mengalami perubahan SLS..." = **2. Tidak**, "10. Kodepos" = **81172**.

**SE2026-P**: Tambah=Bangunan Lainnya | Daftar Usaha Non Prelist=kosong | Nama Bangunan/Usaha/Perusahaan="WARUNG GAS BU DEWI" (auto-uppercase) | Keberadaan Bangunan Lainnya/Usaha=2. Baru | **Alamat**: Nama Jalan/Gang/dll="BANJAR DINAS KAJA KANGIN", Blok/Nomor Rumah="-" (OTOMATIS mengisi 8c Alamat di BLOK II nanti, sudah terverifikasi) | **Nomor Urut Bangunan = 1** (sempat tidak sengaja ke-klik chevron spinner saat eksplorasi awal sesi sampai tersimpan literal "0" — baru ketahuan sbg **GALAT=1** "Tidak boleh kurang dari 1" saat cek ringkasan pra-Kirim, BUKAN dari error inline. Field referensi "NOMOR URUT BANGUNAN TERBESAR" kosong/tidak ada info → atas arahan eksplisit user ["kalau tidak ada info nomor bangunan, bisa lanjutkan nomor bangunan terbesar saat itu"] diisi **1** via 1x klik chevron ▲ → GALAT langsung hilang jadi 0. Lihat nuance lengkap di rule 16.) | Kode Penggunaan Bangunan=1. Bangunan Khusus Usaha (default, tidak diubah) | **Geotagging**: via tombol "Ambil Lokasi" → isi manual Latitude/Longitude di modal "Pilih Lokasi" → 2x klik "Gunakan Lokasi" → konfirmasi "Ya" di dialog "Ambil Lokasi" → BERHASIL (lat -8.127657, long 115.199408 tampil di section).

**BLOK II — SEMUA FIELD BERIKUT SUDAH DIISI, TERSIMPAN, & BERHASIL DIKIRIM**:

- Pilih UMKM dlm 1 SLS = Tidak ada
- 7. Nomor Urut Usaha/Perusahaan = 1 (auto/readonly)
- Keberadaan Usaha (rincian 8) = 2. Baru
- 8b Nama komersial = WARUNG BU DEWI (NI MADE DWIPAYANI) [copy literal, spasi sebelum kurung — beda dgn 8a sumber yg spasi setelah kurung, sudah di-zoom & dikonfirmasi]
- 8c Alamat = "BANJAR DINAS KAJA KANGIN" (auto dari SE2026-P) | RT=00 | RW=00 | Kode Pos=(kosong) | Kode Area=(kosong) | No Telepon=(kosong) | Ekstensi=(kosong) | Email=(kosong) | No HP/WA=083832054884 | Homepage=(kosong)
- 8d Jenis kawasan = 10. Di luar kawasan
- 10a NIB = 2. Tidak | 10c alasan = 3. Tidak memerlukan NIB
- 11a status badan usaha = 13. Bukan Badan Usaha | 11d laporan keuangan = 2. Tidak
- 12a Nama Pengusaha = NI MADE DWIPAYANI | 12b Jenis Kelamin = 2. Perempuan | 12c Umur = 46 | 12d NIK = 9999 (override)
- 13a kegiatan utama = "Menjual makanan ringan" | 13b1=2.Tidak | 13b2=2.Tidak | 13b3=1.Ya | 13c tempat usaha=4. Toko, ruko, dan sejenisnya | 13f produk utama="Menjual makanan ringan" (sama persis dgn 13a kali ini) | **13g KBLI = [G][47772] Perdagangan Eceran Gas Tabung LPG — berhasil via Master KBLI setelah retry search (lihat catatan bug di atas)** | 13h auto="G"
- 14a jaringan usaha = 1. Tunggal
- 16a pakai internet = 2. Tidak (memicu PERINGATAN standar spt record 1&2)
- 17a produk ramah lingkungan = 2. Ya, sebagian | 17b input ramah lingkungan = 1. Ya
- 18 karya seni/budaya = 2. Tidak
- 20a izin edar BPOM = 3. Tidak (MUNCUL, konfirmasi kategori G) | 20c jumlah varian belum BPOM = 1
- 21 mitra KDKMP = 2. Tidak
- 22 program MBG = 5. Tidak terlibat MBG
- 23a/23b/23c = 2. Tidak / 2. Tidak / 2. Tidak
- 24a1 pekerja laki2=0 | 24b1 pekerja perempuan=1 | 24c1 total=1(auto) | 24a2 pekerja dibayar=0 | 24b2 pekerja tdk dibayar=1 | 24c2 total=1(auto)
- 25 tahun mulai komersial = 2005
- **26 (kategori G — semua field a-e muncul termasuk 26c terpisah, sama pola record 1)**: 26a=0 | 26b biaya produksi=0 | 26c biaya pembelian=4.680.000 (dari sumber 46.800.000×10%) | 26d operasional=400.000 (dari 4.000.000×10%) | 26e non-operasional=60.000 (dari 600.000×10%) | 26f total=auto **5.140.000** (dikonfirmasi match dgn sumber 51.400.000×10%)
- 27a nilai penjualan=6.340.000 (dari 63.400.000×10%) | 27b pendapatan lain=0 | 27c total=auto **6.340.000**
- 28a=0 (override) | 28b=300.000 (dari 3.000.000×10%) | 28c total=auto **300.000** | 28d=0 (override, sumber asli 30)
- 29a Pribadi/Perorangan=100,00 | 29b-f=0,00 semua | 29g total=auto **100%**
- KETERANGAN PEMBERI JAWABAN: Nama Pemberi Informasi = Lainnya, Nomor HP & E-mail dikosongkan, checkbox pernyataan data benar = dicentang.
- CATATAN: Waktu Selesai diambil via "Ambil Waktu" (31 Agustus 2026, 22:49:59). Catatan text dikosongkan.
- Ringkasan sebelum Kirim (setelah fix Nomor Urut Bangunan): **86 Jawaban** total, GALAT=0, PERINGATAN=1 (16a internet=Tidak, legitimate sama pola record 1&2), **KOSONG=19** (satu lebih sedikit dari record 1&2 yg 20 — selisihnya persis field Nomor Urut Bangunan yg di record 3 ini terisi "1" jadi tidak lagi terhitung kosong; 19 sisanya: Catatan Kunjungan I, alamat_sesuai, Daftar Usaha Non Prelist, pilih_keluarga_sls, Kode Area, Nomor Telepon, Ekstensi, Email, Homepage/website, 6× "Cek ... (Diisi oleh PML)" [Kategori&KBLI, Pekerja c1, Pekerja 24.c2, Rincian Pengeluaran 2025, Rincian Pendapatan 2025, Rincian Pengeluaran/Pendapatan 1 bulan terakhir], KETERANGAN PEMBERI JAWABAN No HP/Telepon & E-mail, CATATAN — semua vetted legitimate, sama pola record 1&2).
- **Submit sukses**: user konfirmasi eksplisit via AskUserQuestion ("Ya, kirim sekarang") → klik Kirim → Kirim (dialog ringkasan) → Konfirmasi (dialog Konfirmasi Kirim) → toast "Perubahan tersimpan" → redirect ke PENDATAAN list. **Sempat tampil status "DRAFT" krn list belum di-refresh** — setelah klik "Muat Ulang", berubah jadi **SUBMITTED BY PENCACAH / CLEAN** dgn kolom Nomor Urut Bangunan tampil "1". Verified via stats: Jumlah Dokumen=7, Progres Penyelesaian=100% (7 dari 7), Jumlah Clean=7, Jumlah Error=0.

## STATUS TERKINI (paling update)

**SEMUA 3 RECORD TARGET AWAL SUDAH SELESAI & SUKSES TERKIRIM ✅✅✅** — pola sudah terverifikasi end-to-end 3x penuh (create dokumen → isi semua field/section → validasi ringkasan → kirim final):

- RECORD 1 (dokumen `e2e96e1a-e9c9-4cbe-9cda-cd593597e717`) — Warung Aqua Galon (I KETUT SUTARJANA), KBLI 47222
- RECORD 2 (dokumen `9e07d2f4-c9ef-4eaf-8d95-e6952d3a4300`) — Warung Minuman Ringan (KETUT SUYITNA), KBLI 56304
- RECORD 3 (dokumen `9167e0ba-67af-4d61-86ea-d7e0ffbb82f6`) — Warung Gas Bu Dewi, KBLI 47772

Verifikasi akhir di list PENDATAAN (setelah "Muat Ulang"): Jumlah Dokumen=7, Progres Penyelesaian=100% (7 dari 7), Jumlah Clean=7, Jumlah Error=0. **Catatan: 7 dokumen ini termasuk 4 dokumen prelist LAIN yg sudah ada sebelumnya/di luar tugas ini** (mis. DTSEN-61, DTSEN-15, Toko Kelontong — berstatus "APPROVED BY PENGAWAS"/"SUBMITTED BY PENCACAH" duluan, bukan dibuat sesi ini) — hanya 3 dokumen "usaha pecahan" di atas yang merupakan hasil kerja tugas ini.

**✅ KODE OTOMATISASI SUDAH DIBUAT & DIKIRIM KE USER** (file `otomatisasi_usaha_pecahan_se2026.zip`, 6 file Python + requirements.txt: `config.py`, `data_loader.py`, `scrape_source.py`, `fasih_web.py`, `fill_blok2.py`, `main.py`). Detail lihat section "Kode otomatisasi" di bawah.

## Kode otomatisasi (Playwright/Python) — SUDAH DIBUAT, BELUM PERNAH DITES LIVE

Skrip dibuat berdasarkan SELURUH aturan & temuan di dokumen ini (login SSO, buat dokumen, isi SE2026-P+geotagging+identitas wilayah, isi BLOK II lengkap dgn kalkulasi 10% round-half-up, deteksi dinamis 26c/rincian20 dari DOM bukan tabel kategori, retry logic KBLI Master search, nuance Nomor Urut Bangunan (skrip TIDAK PERNAH menyentuh field ini kecuali utk fix GALAT, dgn logika "lanjut dari NOMOR URUT BANGUNAN TERBESAR+1 atau 1 kalau kosong" sesuai arahan user), cek ringkasan (GALAT wajib 0), dan mode dry-run/submit terpisah). Dikirim ke user sbg `otomatisasi_usaha_pecahan_se2026.zip`. Cara pakai lengkap ada di docstring paling atas `main.py`.

**⚠️ KETERBATASAN PENTING yg harus diketahui sesi berikutnya**: skrip ini ditulis dari sandbox cloud yang TIDAK punya akses VPN BPS (dikonfirmasi via `curl` ke fasih-web.bps.go.id → unreachable) — jadi TIDAK PERNAH bisa dites langsung terhadap DOM asli fasih-web/fasih-sm. Yang SUDAH divalidasi scr terpisah (unit test, lihat riwayat percakapan): mesin kalkulasi 10% round-half-up (`rupiah10`/`sum_rupiah10` di `data_loader.py`) menghasilkan angka PERSIS SAMA dgn semua nilai rincian 26/27/28 yg terdokumentasi sukses di record 1,2,3; loader CSV & parser URL fasih-sm (`parse_survey_assignment_id`/`build_source_url`) juga sudah diuji cocok dgn URL asli record 3. Yang BELUM divalidasi (karena tidak bisa akses live): SEMUA selector/label field di `config.py` (dict `L`) — ini rekonstruksi dari catatan visual sesi manual, BUKAN hasil inspeksi HTML asli, jadi kemungkinan besar beberapa string perlu disesuaikan begitu dijalankan `--dry-run --headed` pertama kali oleh user (yg VPN-nya aktif). Kalau ada error "FieldNotFound: ...", user/sesi Claude berikutnya cukup edit string label yg relevan di `config.py`, TIDAK perlu ubah logika lain.

**Next action yg disarankan utk user**: jalankan `python3 main.py --csv <export_3_record_awal>.csv --dry-run --headed --only-no 2510,2511,2512` dulu (BUKAN backlog baru) sbg validasi — karena hasil akhir ke-3 record itu sudah 100% diketahui benar (lihat data lengkap di atas), gampang ketauan kalau ada selector yg meleset. Baru setelah itu lanjut ke backlog No 2513+ sungguhan dgn `--limit` kecil dulu sebelum batch besar.

## Next steps

1. ~~Isi KETERANGAN PEMBERI JAWABAN & CATATAN record 3~~ ✅ selesai.
2. ~~Kirim record 3 (dgn konfirmasi eksplisit user)~~ ✅ selesai & sukses.
3. ~~Susun kode otomatisasi Playwright~~ ✅ selesai & dikirim ke user (lihat section "Kode otomatisasi" di atas) — TAPI belum pernah divalidasi live krn sandbox tidak ada akses VPN.
4. **[BERIKUTNYA] Dampingi user melakukan dry-run pertama** (`--dry-run --headed --only-no 2510,2511,2512`) di komputer yang VPN-nya aktif, bandingkan output dgn data lengkap record 1-3 di atas, perbaiki string label di `config.py` -> dict `L` satu-satu sesuai error `FieldNotFound` yg muncul, sampai dry-run 3 record itu menghasilkan GALAT=0 & field2 penting (nilai 26c/27a/28b, kategori 13h, dst) cocok persis dgn yg terdokumentasi.
5. Setelah dry-run 3-record tervalidasi: lanjut dry-run ke sebagian kecil backlog No 2513+ sungguhan (`--limit 3-5`), review manual hasilnya di fasih-web (belum submit), baru scale up ke `--submit` dgn batch kecil dulu sebelum batch besar.
6. Pertimbangkan lengkapi `scrape_source.py` (field 24a1/24b1/24a2/24b2 pekerja belum semua ke-scrape) & `config.py` -> `KODEPOS_BY_IDSUBSLS` (baru ada 1 entri) kalau backlog mencakup SLS/pekerja dgn variasi yg belum tercakup.
7. Verifikasi kode otomatisasi scr menyeluruh (dry-run bertahap seperti di atas) sebelum dipakai utk batch besar — JANGAN langsung `--submit` ke banyak record tanpa tahap dry-run/review dulu, krn Kirim = irreversible.
