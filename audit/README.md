# audit/ — catatan dokumen yang sudah dibuat/dikirim

Isi folder ini **tidak ikut git** (hanya README ini). Berkas di sini **tidak bisa dibuat ulang**
— jangan dihapus, jangan dibuka lalu disimpan di Excel (kunci & idsubsls rusak; pulihkan dengan
`antar_pc/pulihkan_excel.py`).

| Berkas | Isi | Ditulis oleh |
| --- | --- | --- |
| `audit_log_gabungan.csv` | audit input BAWAAN: status tiap baris sheet + URL dokumennya. Pencegah dokumen ganda. | `input_usaha/` |
| `<batch>/audit_log_gabungan.csv` | audit batch lain, dipakai dgn `--audit audit/<batch>` | `input_usaha/ --audit` |
| `audit_approve_pml.csv` | dokumen yang sudah di-approve PML | `approve_pml/` |
| `ganda_dihapus*.csv` | dokumen ganda yang sudah dihapus admin (unduhan Console) | `fasih_sm/hapus_ganda/` |
| `pc/` | audit & sheet kiriman PC lain sebelum digabung; hasil gabungan di `pc/hasil/` | Anda (salin manual) |

Satu audit = satu batch (satu sheet sumber). Menjalankan sheet dengan audit yang salah akan
dihentikan skrip ("audit lain jauh lebih mengenal sheet ini") — pakai `--audit` yang benar.
