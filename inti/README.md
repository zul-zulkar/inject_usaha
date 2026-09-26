# inti — modul bersama

Dipakai semua alat (`from inti.x import ...`). Arah dependensi satu arah: `inti` tidak pernah
mengimpor folder alat.

| Berkas | Isi | Diubah kalau… |
| --- | --- | --- |
| `config.py` | nilai bawaan: URL, aturan `TAHAP2_*` & `TAHAP2_DEFAULT`, selektor fasih-web (`DK` dataKey, `SEL` struktural, `L` label) — semuanya dari dump DOM asli | tampilan fasih-web berubah (`FieldNotFound`) atau aturan pengisian berubah |
| `config_lokal.py` | **milik Anda, tidak ikut git** (templat: `templates/config_lokal.contoh.py`); menimpa nama apa pun di `config.py` | password, kode kabupaten, kodepos, akun |
| `lokasi.py` | semua lokasi berkas: `bahan/`, `audit/`, `<alat>/hasil/`, audit bawaan & pengaman struktur lama | folder dipindah |
| `tahap2_loader.py` | **format input usaha**: pemetaan kolom, kode opsi, penggantian nilai, pemeriksaan khas tahap 2 | kolom sheet / aturan data berubah |
| `gabungan_loader.py` | dasar baris & pemeriksaan (`GabunganRow`, `periksa_semua`, `OPSI_FORM`) + pembaca format lama Agenda | opsi form berubah |
| `fasih_web.py` | `FasihWebSession`: login SSO + verifikasi akun, buat/buka dokumen, isi field per dataKey, geotag, KBLI, ringkasan GALAT, kirim | perilaku fasih-web berubah |
| `id_dokumen.py` | kolom "ID Dokumen FASIH" di sheet sumber (baca, cocokkan, tulis balik aman) | — |

Kebiasaan penting: selektor pakai **dataKey** (`DK`) atau struktur (`SEL`), bukan koordinat;
keputusan "ada/tidak ada" pakai `wait_for`, **bukan `.count()`** (snapshot, pernah membuat dokumen
ganda). Rincian perilaku form: [`docs/CATATAN_TEKNIS.md`](../docs/CATATAN_TEKNIS.md).
Uji selektor tanpa VPN: `python tests/test_selectors.py`.
