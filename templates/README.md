# templates — titik awal pengguna baru

Semua berkas di sini **kosong atau fiktif** dan ikut git — jangan pernah mengisi data sungguhan di
folder ini. Salin dulu ke `bahan/` / `inti/`, baru diisi.

| Berkas | Untuk | Salin ke |
| --- | --- | --- |
| `input_usaha.xlsx` | **templat input usaha** (format tahap 2): tab `input_usaha` = judul kolom + **1 baris contoh** (kuning), tab `petunjuk` = arti tiap kolom, kode opsi, kolom tambahan & nilai bawaannya | `bahan/input_usaha.xlsx` |
| `config_lokal.contoh.py` | password, `KODE_KAB`, kodepos per desa, akun & subsls, aturan yang boleh ditimpa | `inti/config_lokal.py` |
| `daftar_idsubsls.contoh.txt` | satu idsubsls per baris (`#` = komentar) | `bahan/` — untuk `buka_wilayah`, `tandai_selesai`, `ganti_moda --subsls` |
| `daftar_akun_ppl.contoh.txt` | satu email akun PPL per baris | `bahan/` — untuk `reset_mitra --daftar` |
| `daftar_kode_identitas.contoh.txt` | kode identitas assignment | `bahan/` — untuk `ganti_moda --daftar` |
| `rencana_approve.contoh.csv` | rencana approve banyak PML | `bahan/` — untuk `approve_pml --rencana` |

Baris contoh di `input_usaha.xlsx` bertanda `CONTOH` di kolom `Uraian:` sehingga **selalu ditolak**
skrip walau lupa dihapus. Timpa baris itu dengan data Anda (kolom `Uraian:` boleh diisi apa saja
selain awalan `CONTOH`). Semua sel sudah berformat Teks — biarkan begitu.

Templat dibangkitkan & diverifikasi (dibaca loader, ditolak hanya karena penanda contoh, SIAP
tanpa penandanya) oleh:

```bash
python templates/buat_templat_input_usaha.py
```

Jalankan ulang kalau judul kolom / kode opsi di `inti/tahap2_loader.py` berubah
(`tests/test_templat.py` gagal kalau templat sudah tidak cocok).
