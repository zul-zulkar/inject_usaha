# bahan/ — data masukan Anda

Isi folder ini **tidak ikut git** (hanya README ini). Letakkan di sini:

| Berkas | Untuk | Asal |
| --- | --- | --- |
| `input_usaha.xlsx` | sheet usaha yang akan diinput (format tahap 2) | salin `templates/input_usaha.xlsx`, isi mulai baris 2 |
| `daftar_*.txt` | daftar idsubsls / kode identitas | lihat `templates/daftar_*.contoh.txt` |

Nama berkas bebas (mis. satu berkas per batch: `input_usaha_batch1.xlsx`) — sebutkan lewat
`--sumber`. Kolom **"ID Dokumen FASIH"** di sheet diisi skrip sendiri sesudah dokumen dibuat;
jangan diubah, dan tutup berkasnya di Excel saat batch berjalan supaya ID bisa ditulis.
