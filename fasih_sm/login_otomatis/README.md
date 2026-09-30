# login_otomatis — penjaga sesi & login ulang otomatis fasih-sm (Tampermonkey)

Sesi fasih-sm habis berkala (HTTP 401), bisa tiap beberapa menit bisa tiap jam. Bot Console (`semuaKeCapi`,
`approveCapi`) lalu **menunggu tanpa batas**. Userscript ini langsung melakukan login ulang tiap kali sesi habis,
tanpa jeda dan tanpa batas jumlah, lalu membangunkan bot. Jadi bot bisa jalan tanpa ditunggui.

```
tab PENJAGA (userscript)          8 tab bot (Console)
  cek sesi tiap 60 dtk      ◄──── kena 401 → sinyal localStorage "fasihSesi.minta.v1"
  sesi habis → /app/auth/login → sso.bps.go.id: isi username/password, klik "Log In"
  kembali ke fasih-sm, sesi hidup → sinyal "fasihSesi.pulih.v1" ───► bot langsung lanjut
```

## Pasang (sekali per PC)

1. Pasang ekstensi **Tampermonkey** dari Chrome Web Store.
2. Di `chrome://extensions` → Tampermonkey → **Details**, aktifkan **Allow User Scripts**. Di Chrome versi lama
   yang belum punya tombol itu, aktifkan **Developer mode** (pojok kanan atas).
3. Ikon Tampermonkey → **Create a new script** → hapus isinya → tempel seluruh isi
   [`fasih_login_otomatis.user.js`](fasih_login_otomatis.user.js) → **File → Save**.
4. Buka halaman fasih-sm mana saja → ikon Tampermonkey → **🔑 Atur akun SSO (username & password)**.
   Isi username SSO akun admin, password, dan jenis SSO (`pegawai` untuk tombol "Lanjutkan dengan SSO",
   `eksternal` untuk "Lanjutkan dengan SSO Eksternal").

Password tersimpan di penyimpanan Tampermonkey **di PC ini saja**. Password tidak pernah ditulis ke berkas
repo, jadi jangan menempelkannya ke dalam skrip. Siapa pun yang bisa membuka profil Chrome ini bisa membacanya.
Kalau sudah selesai, hapus lewat menu **🗑️ Hapus password tersimpan**.

## Pakai

1. Buka satu tab di halaman **Data** survei (`…/app/surveys/<survei>/<periode>/data`), lalu pilih menu
   Tampermonkey **🛡️ Jadikan tab ini PENJAGA sesi**. Pojok kiri bawah tab itu kini menampilkan spanduk hijau
   "🛡️ Penjaga sesi — sesi aktif (cek …)", dan judul tabnya diawali 🛡️.
2. Buka tab bot seperti biasa. Tempel berkas Console lalu `jalankan({bagian: "k/8"})` / `kePapi({bagian: "k/8"})`.
3. Biarkan. Kalau sesi habis, tab penjaga pindah sendiri ke login SSO, mengisi form, dan kembali ke halaman Data.
   Bot mencetak "✅ Sesi aktif lagi" lalu lanjut.

Tab penjaga jangan dipakai untuk menjalankan bot, dan jangan dipindah ke halaman lain. Tandanya bertahan
walau tab dimuat ulang; tanda itu hilang kalau tab ditutup. Untuk berhenti, pilih menu **⏹️ Hentikan penjaga
di tab ini**.

## Jumlah & jeda

- **Tanpa batas jumlah, tanpa jeda.** Setiap kali sesi habis, penjaga langsung login ulang. Tidak ada jendela waktu
  yang dihitung: sesi yang habis tiap 3 menit, 5 menit, atau 1 jam ditangani sama.
- Login yang **berhasil** tidak dihitung apa pun.
- Satu-satunya jeda: kalau **3 putaran login berturut-turut tidak memulihkan sesi** (SSO atau fasih-sm sedang
  bermasalah), putaran berikutnya diberi jeda 30 detik supaya tab tidak berputar menghantam server. Putaran tetap
  diulang terus, tanpa batas. Jedanya bisa diubah atau dimatikan (`0`) lewat menu **⏱️ Atur jeda login GAGAL
  berturut-turut**.
- Bot bangun **seketika** saat penjaga menulis sinyal pulih, tidak menunggu sampai 20 detik.

## Pengaman

| Keadaan | Yang dilakukan |
| --- | --- |
| Halaman SSO dibuka **tanpa** permintaan penjaga (< 3 menit lalu) | tidak diisi (login manual Anda tidak disentuh) |
| Tujuan login bukan fasih-sm (mis. fasih-web) | tidak diisi |
| Form sudah dikirim di putaran ini tapi kembali ke halaman login | tidak dikirim lagi; kembali ke fasih-sm, penjaga memulai putaran baru |
| Halaman SSO tanpa form (galat server) di tengah putaran | kembali ke fasih-sm, putaran baru |
| SSO menampilkan **pesan galat** (password salah, akun terkunci) | **tidak diulang**, karena mengulang bisa memperpanjang kunci akun admin; notifikasi desktop + judul tab "⚠️ LOGIN GAGAL" |
| Cek sesi dijawab 429/5xx/gagal jaringan | bukan urusan login: tidak ada tindakan, dicek lagi semenit kemudian |
| Tab fasih-sm lain (bukan penjaga) | userscript diam (hanya menambah menu) |

Kalau notifikasi "LOGIN GAGAL" muncul, periksa password lewat menu **🔑 Atur akun SSO**, lalu login manual di
tab penjaga. Bot tetap menunggu tanpa batas sejak 401 pertama (`tungguLoginMs`), dan bisa dihentikan dengan
`.berhenti()`. Kalau bot terlanjur dihentikan, jalankan ulang dengan bagian yang sama; sisanya dilanjutkan
tanpa menelusuri ulang.

## Struktur halaman yang dipakai

Dibaca langsung pada 2026-09-30:
- `/app` tanpa sesi menampilkan tautan "Lanjutkan dengan SSO" → `/app/auth/login?redirect_to=…`. SSO Eksternal
  memakai tautan yang sama ditambah `realms=eksternal`.
- Tautan itu menuju `sso.bps.go.id/auth/realms/pegawai-bps/…/auth` dengan `redirect_uri` ke
  `https://fasih-sm.bps.go.id/login/oauth2/code/…`.
- Form di sana: `#kc-form-login`, `#username`, `#password`, tombol `#kc-login`.
- Cek sesi memakai `GET /app/api/survey/api/v1/survey-roles?surveyId=<survei>`: 200 = hidup, 401 = habis.

Yang **belum terbukti live**:
- Apakah login di tab penjaga langsung memulihkan tab bot (cookie sesi yang sama). Tandanya: bot mencetak
  "✅ Sesi aktif lagi".
- Apakah form SSO realm eksternal memakai id yang sama. Kalau tidak cocok, userscript diam dan tidak salah isi.

## Kode yang berpengaruh

| Berkas | Isi |
| --- | --- |
| `fasih_login_otomatis.user.js` | userscript: menu, penjaga (cek sesi, sinyal bot, hitungan gagal beruntun), pengisi form SSO (syarat, maks 1 kiriman per putaran) |
| `../../approve_capi/approve_capi_console.js`, `../ganti_moda/semua_ke_capi_console.js` | `kirim()`: 401 → tulis sinyal `fasihSesi.minta.v1`, tunggu tanpa batas; `tungguPulih()` bangun seketika saat `fasihSesi.pulih.v1` baru, selain itu ulang tiap 20 dtk |
| Uji | `tests/test_login_otomatis_userscript.js` (logika + simulasi SSO/penjaga dgn DOM & Tampermonkey palsu) |
