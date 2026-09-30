# approve_capi — approve otomatis assignment CAPI (banyak PML)

fasih-web hanya membuka dokumen **PAPI** untuk di-approve. Dokumen CAPI ditolak dengan pesan
"tidak memiliki akses". Karena itu alurnya tiga langkah:

| Langkah                                     | Di mana                 | Akun                | Alat                                                 |
| ------------------------------------------- | ----------------------- | ------------------- | ---------------------------------------------------- |
| 1. CAPI`SUBMITTED BY Pencacah` → PAPI    | Console Chrome fasih-sm | admin kab           | `approveCapi.kePapi()`                             |
| 2. Approve                                  | fasih-web (Playwright)  | tiap PML bergiliran | `approve_capi.py` (→ `approve_pml` mode server) |
| 3. PAPI → CAPI (hanya yang sudah APPROVED) | Console Chrome fasih-sm | admin kab           | `approveCapi.keCapi()`                             |

Siapkan berkas **daftar PML**: satu email per baris (contoh `templates/daftar_pml.contoh.txt`),
misalnya di `bahan/daftar_pml.txt`. Password semua PML diambil dari `FIXED_PASSWORD` di
`inti/config_lokal.py`. Kalau PML-nya pegawai BPS, tambahkan `--sso pegawai` (+ `PASSWORD_PEGAWAI`).

## 1. Ganti ke PAPI (fasih-sm, akun admin)

```bash
python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --console
```

Buka `approve_capi/hasil/approve_capi_console.siap.js`, lalu tempel isinya di Console halaman **Data**
survei (cara menempel: [fasih_sm/README.md](../fasih_sm/README.md)).

```js
await approveCapi.periksa()              // opsional, READ-ONLY: jumlah CAPI SUBMITTED per PML
await approveCapi.kePapi()               // semua (ketik YA)
approveCapi.unduh()                      // approve_capi_<waktu>.csv → simpan di bahan/ (atau biarkan di Downloads)
```

**Paralel di satu browser.** Tempel berkas `.siap.js` yang **sama** di beberapa tab (lebih baik jendela
terpisah yang berdampingan), lalu jalankan satu perintah per tab:

```js
await approveCapi.kePapi({bagian: "1/4"})   // tab 1
await approveCapi.kePapi({bagian: "2/4"})   // tab 2
await approveCapi.kePapi({bagian: "3/4"})   // tab 3
await approveCapi.kePapi({bagian: "4/4"})   // tab 4
approveCapi.unduh()                          // di tab mana saja: CSV GABUNGAN semua bagian
```

- Dokumen dibagi berdasarkan ID, jadi tidak ada dokumen yang dikerjakan dua tab. Tiap tab menanyakan
  `YA` sendiri.
- Daftar CAPI hanya dibaca **satu** tab. Tab lain menulis "⏳ Tab lain sedang membaca daftar CAPI" dan
  menunggu, lalu memakai daftar tersimpan itu. Supaya ini berlaku, mulai tab 1 lebih dulu, lalu tab
  lain beberapa detik kemudian.
- Jumlah bagian bebas, mis. `{bagian: "1/10"}` … `"10/10"`, langsung di Console tanpa berkas baru. Semua
  tab wajib memakai angka pembagi yang sama. Tiap tab menambah ±1,25 request/detik ke server; kalau
  server sedang berat, mulai dari 2–4 tab.
- Ditolak otomatis (di browser yang sama): bagian yang sudah berjalan di tab lain, jumlah bagian yang
  berbeda, atau perintah tanpa bagian selagi ada bagian yang berjalan. Tab yang ditutup di tengah jalan
  dianggap berhenti 3 menit kemudian.
- Chrome memperlambat timer di tab latar belakang. Jendela terpisah yang terlihat berjalan lebih cepat.
- Yang diganti hanya dokumen yang petugas saat ininya PML **di daftar**. Dokumen yang dipegang PPL,
  tidak punya petugas, atau dipegang PML di luar daftar hanya dilaporkan.
- Tepat sebelum diganti, detail dokumen dibaca ulang dan harus SUBMITTED + CAPI. Sesudah diganti,
  detail dibaca lagi dan mode harus PAPI dengan status tetap. Kejanggalan menghentikan batch.
- **HTTP 401 (sesi habis):** skrip **tidak** langsung berhenti. Ia menulis "🔑 … Login ulang di TAB LAIN" lalu
  menunggu **tanpa batas**. Buka fasih-sm di tab lain dan login ulang; tab yang sedang berjalan **jangan** dimuat
  ulang. Begitu sesi aktif lagi, skrip menulis "✅ Sesi aktif lagi" dan melanjutkan sendiri. Supaya login ulang
  ini juga otomatis (tanpa ditunggui), pasang tab penjaga:
  [`fasih_sm/login_otomatis`](../fasih_sm/login_otomatis/README.md).
- **Kalau tetap harus dijalankan ulang** (bot dihentikan, atau tab terlanjur dimuat ulang): login ulang, muat ulang
  halaman Data, tempel berkas `.siap.js` yang **sama**, lalu jalankan perintah yang sama lagi (dengan bagian yang
  **sama** kalau paralel). Dokumen yang sudah dipindah ke PAPI **dilewati** tanpa satu request pun, dan daftar CAPI
  tidak dibaca ulang. Dokumen yang sudah sempat dikirim sebelum putus (`DIGANTI_PAPI_DIKIRIM`) diakui tanpa dikirim
  ulang. Untuk sengaja membaca ulang dari server (mis. mengambil dokumen SUBMITTED yang baru masuk):
  `kePapi({telusurUlang: true})`.
- **HTTP 429 / server sibuk:** batch tidak berhenti karena satu dokumen.

  - change-mode yang dijawab 429 ditunggu (5, 10, 20, 40, 60 detik), status dokumen dicek, lalu dikirim ulang
    (maks 5×).
  - Dokumen yang tetap sibuk (`SERVER_SIBUK`) ditaruh di akhir antrean dan dicoba sekali lagi.
  - Batch baru berhenti kalau 3 dokumen berturut-turut sibuk. Jalankan lagi nanti; daftarnya dilanjutkan.
- **Kecepatan:** jeda bawaan kecil (0,4 detik antar-request, 0,5–1 detik antar-dokumen) dan **adaptif**. Tiap 429/5xx
  menggandakan semua jeda (maks 8×), tiap respons sukses menurunkannya lagi (×0,9). Masih bisa diatur, misalnya
  `kePapi({jarakRequestMs: 800, jedaTulisMin: 1000, jedaTulisMaks: 2000})` kalau server sedang berat, atau
  `{tungguLoginMs: 0}` supaya 401 langsung berhenti.
- Catatan hasil disimpan ringkas di localStorage (±100 karakter per dokumen). Kalau tetap penuh, batch
  berhenti dengan `PENYIMPANAN_PENUH`. Jalankan `approveCapi.unduh()` sesudahnya; CSV itu bukti sekaligus
  bahan approve.

## 2. Approve (fasih-web, semua PML bergiliran)

```bash
python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --cek
python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt
python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --eksekusi
```

Perintah pertama hanya login dan membaca list tiap PML. Perintah kedua adalah dry-run: dokumen
dibuka tetapi tidak diklik. Perintah ketiga meng-approve sungguhan. `YA` ditanyakan per PML,
sesudah jumlah dokumennya terlihat. Tambahkan `--ya` untuk melewati pertanyaan itu.

Semua CSV `approve_capi*.csv` dari langkah 1 (di `bahan/`, `hasil/`, Downloads) digabung otomatis; pilih sendiri dengan `--hasil <csv>`. Hanya ID
berstatus `DIGANTI_PAPI_TERVERIFIKASI` yang di-approve. Dokumen PAPI lain milik PML yang sama **tidak**
ikut. PML tanpa dokumen tidak di-login-kan. Opsi lain (`--limit`, `--ya`, `--sso`, `--login-manual`)
diteruskan ke `approve_pml`. Catatan approve ditulis ke `audit/audit_approve_pml.csv`.

## 3. Kembalikan ke CAPI

Tempel ulang berkas `.siap.js` yang sama di Console fasih-sm:

```js
await approveCapi.keCapi()               // atau paralel: keCapi({bagian: "1/4"}) … "4/4", satu per tab
approveCapi.unduh()                      // bukti akhir
```

Yang dikembalikan hanya dokumen yang **diganti oleh alat ini** dan sudah APPROVED. Dokumen yang
masih SUBMITTED tetap PAPI (`BELUM_APPROVED`), jadi jalankan lagi sesudah approve berikutnya.
Kalau memang harus dikembalikan juga, pakai `keCapi({termasukBelumApproved: true})`. Dokumen yang
aslinya PAPI tidak pernah disentuh.

Catatan hasil tersimpan di localStorage browser itu. Kalau pindah browser, pulihkan dengan
`approveCapi.muatHasil(\`<isi CSV unduhan></isi>\`)`.

## Paralel: ringkasan

| Langkah         | Satu PC                                                    | Beberapa PC                     |
| --------------- | ---------------------------------------------------------- | ------------------------------- |
| 1. CAPI → PAPI | beberapa tab:`kePapi({bagian: "k/n"})` (lihat langkah 1) | `--bagi N` per PML (di bawah) |
| 2. Approve      | beberapa bot:`--paralel K`                               | `--bagi N` per PML            |
| 3. PAPI → CAPI | beberapa tab:`keCapi({bagian: "k/n"})`                   | `--bagi N` per PML            |

Keduanya bisa digabung. Di PC yang memegang bagian `--bagi` K, berkas `.siap.js` bagian itu boleh
dijalankan di beberapa tab dengan `{bagian: "k/n"}`. Catatannya tetap terpisah per berkas.

## Paralel: beberapa PC / beberapa bot

Pekerjaan dibagi **per PML**. Satu PML hanya dikerjakan satu bagian, jadi tidak ada dokumen yang
dikerjakan dua kali. Satu bagian = satu PC (atau satu tab Console + satu bot approve) dari langkah 1
sampai 3.

1. Di PC utama, baca jumlahnya dulu dengan Console tanpa bagian:
   `await approveCapi.periksa()` lalu `approveCapi.unduhPerPml()` → `jumlah_capi_per_pml.csv`.
2. Bagi daftar PML menjadi N bagian dengan beban seimbang:
   ```bash
   python approve_capi/approve_capi.py --daftar-pml bahan/daftar_pml.txt --bagi 5 --jumlah bahan/jumlah_capi_per_pml.csv
   ```

   Hasilnya ada di `approve_capi/hasil/bagian/`: `daftar_pml.bagian-K-dari-5.txt` dan
   `approve_capi_console.bagian-K-dari-5.siap.js`.
3. Kirim ke tiap PC kodenya (`antar_pc/bungkus_pc.py --kode-saja`) **dan** dua berkas bagiannya.
   Folder `hasil/` tidak ikut zip. Kalau tiap PC menjalankan perintah `--bagi` yang sama dengan
   daftar dan CSV jumlah yang sama, hasilnya identik.
4. Di PC bagian K, jalankan langkah 1–3 seperti biasa dengan berkas bagiannya:
   ```bash
   python approve_capi/approve_capi.py --daftar-pml approve_capi/hasil/bagian/daftar_pml.bagian-K-dari-5.txt --eksekusi
   ```

   Catatan Console tiap bagian tersimpan terpisah (localStorage dan nama CSV berlabel bagian).

**Beberapa bot approve sekaligus dalam satu PC:** tambahkan `--paralel K`.

```bash
python approve_capi/approve_capi.py --daftar-pml <daftar/bagian> --eksekusi --paralel 4
```

- PML dibagi ke K bot dengan jumlah dokumen yang seimbang. Satu PML tidak pernah dipegang dua bot.
- Semua bot jalan bersamaan (mulai berselang 5 detik supaya login tidak serentak), dan `YA` cukup
  diketik sekali.
- Keluaran di layar diberi awalan `[bot k]`, dan log tiap bot ada di
  `hasil/log_approve_capi.<daftar>.bot-k-dari-K.txt`.
- Ctrl+C menghentikan semua bot.
- Kalau RAM kosong kurang dari ±1,5 GB × K, skrip memperingatkan dan menyarankan jumlah bot.
- Satu bot yang berhenti karena anomali tidak menghentikan bot lain.

Terminal terpisah per berkas daftar juga boleh. PML yang sama di dua bot pada satu PC ditolak otomatis. **Antar-PC tidak ada kunci**, jadi jangan menjalankan satu
berkas bagian di dua PC. Tiap bot memakan ±1,5 GB RAM.

Approve bisa dijalankan **sambil** `kePapi` masih berjalan: panggil `approveCapi.unduh()` kapan saja
(boleh di tengah proses), lalu jalankan approve. Jalankan lagi nanti untuk dokumen yang baru diganti.
Dokumen yang sudah APPROVED dilewati cukup dengan satu pembacaan status.

**Perkiraan waktu:**

- Approve: ±5 detik per dokumen per bot (median 5.743 approve di audit).
- `kePapi`: ±3–4 detik per dokumen per tab selama server lancar (dulu ±6–7 detik). Saat 429/5xx, jedanya
  melambat sendiri. Dengan 4 tab `{bagian: "k/4"}` kira-kira 4× lebih cepat, selama server tidak membalas 429.
- Beberapa tab Console dengan akun admin yang **sama** kemungkinan berbagi kuota rate limit (belum
  terbukti). Akun admin yang berbeda per PC lebih aman.

## Kode yang berpengaruh

| Berkas                            | Isi                                                                                                                                                                                                                                    |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `approve_capi_console.js`       | baca CAPI SUBMITTED (per jendela tanggal, batas 1.000 server), ganti mode`POST …/assignment/{id}/change-mode`, verifikasi detail, bagian paralel per tab (`bagian`, tanda jalan/membaca di localStorage), lanjut sesudah 401, CSV |
| `approve_capi.py`               | daftar PML → suntik Console; CSV →`hasil/id_approve_capi.csv` → `approve_pml.py --akun-pml … --hanya-id …`                                                                                                                    |
| `../approve_pml/approve_pml.py` | `--hanya-id` (mode server dibatasi ke ID berkas), klik Approve + verifikasi status                                                                                                                                                   |
| Uji                               | `tests/test_approve_capi_console.js` (server palsu), `tests/test_approve_capi.py`                                                                                                                                                  |

⚠️ Status live: ganti mode CAPI → PAPI untuk dokumen SUBMITTED lewat endpoint ini **belum pernah
dicoba skrip** (arah PAPI → CAPI terbukti 27 Sep). Tidak ada tahap percobaan `limit: 1` (ketetapan
user). Pengamannya: tiap dokumen diverifikasi sesudah diganti, dan dokumen pertama yang gagal
diverifikasi atau ditolak server menghentikan batch.
