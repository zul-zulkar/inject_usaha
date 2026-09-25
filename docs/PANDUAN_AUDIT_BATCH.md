# Panduan Lokasi Audit per Batch

`audit_log_gabungan.csv` adalah **ingatan** skrip input: dokumen mana yang sudah dibuat (beserta
URL-nya), mana yang sudah terkirim, mana yang masih draft. Dari situlah skrip tahu harus membuka
dokumen lama, bukan membuat dokumen baru. Secara bawaan audit ada di folder kerja
(`./audit_log_gabungan.csv`) dan dipakai bersama oleh semua sumber data.

Panduan ini untuk kalau Anda ingin **batch lain** (sumber data baru, pekerjaan terpisah) punya audit
sendiri, di folder dan dengan nama yang Anda tentukan.

---

## Kapan perlu audit sendiri

| Pakai audit sendiri | Tetap pakai audit bawaan |
| --- | --- |
| Sumber data baru yang usahanya **belum pernah diinput** | Melanjutkan / mengulang sheet yang sudah pernah diinput |
| Ingin progres batch itu terpisah & mudah dilaporkan | Memperbaiki draft/galat dari batch lama |
| Uji coba yang tidak boleh mengotori audit utama | Menggabung progres beberapa PC untuk batch yang sama |

⚠️ **Audit baru = kosong.** Dokumen yang tercatat di audit lain **tidak dikenali**. Pencegah dokumen
ganda tinggal `--sinkron-dulu`, yang hanya melihat daftar akun yang sedang dipakai dan hanya
mengenali nama yang persis sama. Jadi jangan membuat audit baru untuk sheet yang sebagian barisnya
sudah pernah diinput — dokumennya bisa terbuat dua kali (dan hanya admin yang bisa menghapusnya).

---

## Cara menentukan lokasi audit

Ada dua cara. Hasilnya sama; pilih salah satu dan konsisten.

### Cara A — variabel lingkungan `FASIH_AUDIT` (disarankan)

Atur **sekali per jendela terminal**; semua perintah di jendela itu otomatis memakai audit tersebut,
termasuk alat yang tidak punya pilihan `--audit` (`approve_pml.py`) dan perintah yang dicetak alat
lain (mis. `bersihkan_error.py`).

PowerShell:

```powershell
$env:FASIH_AUDIT = "audit_batch2\audit_log_gabungan.csv"
```

Command Prompt (cmd):

```bat
set FASIH_AUDIT=audit_batch2\audit_log_gabungan.csv
```

Git Bash:

```bash
export FASIH_AUDIT=audit_batch2/audit_log_gabungan.csv
```

Berlaku sampai jendela terminal ditutup. Membuka terminal baru = kembali ke audit bawaan, jadi atur
lagi. Untuk kembali ke bawaan di jendela yang sama: PowerShell `Remove-Item Env:FASIH_AUDIT`,
cmd `set FASIH_AUDIT=`, Git Bash `unset FASIH_AUDIT`.

### Cara B — pilihan `--audit` di setiap perintah

```bash
python input_tahap2/main_tahap2.py --sumber bahan/SUMBER_BARU.xlsx --audit audit_batch2/ --akun-tunggal EMAIL --subsls-tunggal SUBSLS --sinkron-dulu --lewati-selesai --submit
```

`--audit` menerima:

| Bentuk | Contoh | Audit yang dipakai |
| --- | --- | --- |
| Folder (diakhiri `/` atau `\`, sudah ada, atau tanpa akhiran `.csv`) | `--audit audit_batch2/` | `audit_batch2/audit_log_gabungan.csv` |
| Berkas `.csv` dengan nama sendiri | `--audit D:\batch\audit_kecamatan_020.csv` | berkas itu persis |

Folder induknya **dibuat otomatis**. Kalau `--audit` dan `FASIH_AUDIT` sama-sama diberikan,
`--audit` yang menang.

⚠️ Dengan cara B, **setiap** perintah untuk batch itu wajib memakai `--audit` yang sama. Lupa sekali
saja, perintah itu membaca/menulis audit bawaan.

### Contoh: audit di folder `audit\`

`--audit audit` (tanpa akhiran `.csv`) dibaca sebagai folder, jadi auditnya menjadi
`audit\audit_log_gabungan.csv`; folder `audit\` dibuat sendiri kalau belum ada.

```powershell
$env:FASIH_AUDIT = "audit\audit_log_gabungan.csv"
```

atau per perintah: `--audit audit` (sama dengan `--audit audit\`). Nama berkas lain juga boleh, mis.
`$env:FASIH_AUDIT = "audit\batch2.csv"` atau `--audit audit\batch2.csv`.

**Memindahkan audit yang SUDAH berjalan** ke folder itu (bukan batch baru): hentikan semua proses
input dulu, lalu pindahkan berkasnya beserta cadangannya.

```powershell
New-Item -ItemType Directory -Force audit
Move-Item audit_log_gabungan.csv audit\
Move-Item audit_log_gabungan.csv.bak-* audit\
```

Sejak itu **setiap** terminal wajib mengatur `FASIH_AUDIT` (atau setiap perintah memakai `--audit
audit`). Kalau lupa, alat memakai `audit_log_gabungan.csv` di folder kerja yang sekarang tidak ada →
audit kosong → skrip tidak mengenali dokumen yang sudah dibuat dan bisa membuat dokumen **ganda**.
Cek baris `Audit:` sebelum mengetik YA.

### Selalu cek baris pertama keluaran

Setiap alat mencetak lokasi audit yang benar-benar dipakai:

```
Audit: D:\...\audit_batch2\audit_log_gabungan.csv (BARU — belum ada isinya)
```

Kalau audit itu kosong sementara `audit_log_gabungan.csv` di folder kerja berisi, muncul peringatan
tambahan — pastikan memang batch baru, bukan salah ketik lokasi.

---

## Kapan audit dibuat & diperbarui

Berkas audit **dibuat otomatis** saat pertama kali ada yang ditulis ke sana; tidak perlu membuat
berkas kosong. Yang **menulis** ke audit:

| Perintah | Kapan menulis |
| --- | --- |
| `input_tahap2/main_tahap2.py`, `input_gabungan/main_gabungan.py` | Tiap baris diproses: `DOKUMEN_DIBUAT` (+URL) segera sesudah dokumen dibuat, lalu status akhirnya (terkirim, draft, galat, dst.) |
| `input_gabungan/sinkron_list.py --tulis` | Mencocokkan daftar dokumen di server dengan audit; menambah dokumen yang dibuat PC/proses lain |
| `hapus_ganda/hapus_ganda.py --catat --tulis` | Mengarahkan audit ke dokumen yang dipertahankan sesudah dokumen ganda dihapus |
| `gabung_audit/gabung_audit.py --tulis` | Menyatukan audit beberapa PC ke berkas `--keluaran` |
| `gabung_audit/pulihkan_excel.py --tulis` | Memulihkan audit yang pernah disimpan ulang Excel |

Alat yang hanya **membaca** audit: `rangkum_audit.py`, `bersihkan_error.py`, `kontrol_kualitas.py
--hanya-belum-terkirim`, `rencana_ubah_wilayah.py`, `pindah_wilayah.py`, `tulis_id_sumber.py`,
`approve_pml.py`.

Perintah yang menulis ulang seluruh berkas (gabung, pulihkan, hapus ganda) membuat cadangan
`<nama audit>.bak-<waktu>` di **folder yang sama** dengan auditnya.

---

## Contoh lengkap satu batch baru

PowerShell, dari root proyek:

```powershell
$env:FASIH_AUDIT = "audit_batch2\audit_log_gabungan.csv"

# 1. periksa sumber (tanpa browser)
python input_gabungan/kontrol_kualitas.py --sumber bahan/SUMBER_BARU.xlsx --format tahap2

# 2. input
python input_tahap2/main_tahap2.py --sumber bahan/SUMBER_BARU.xlsx --akun-tunggal EMAIL --subsls-tunggal SUBSLS --sinkron-dulu --lewati-selesai --submit

# 3. cocokkan dengan server & lihat progres
python input_gabungan/sinkron_list.py --sumber bahan/SUMBER_BARU.xlsx --format tahap2 --akun-tunggal EMAIL --subsls-tunggal SUBSLS --tulis
python gabung_audit/rangkum_audit.py --sumber bahan/SUMBER_BARU.xlsx --format tahap2 --akun-tunggal EMAIL --subsls-tunggal SUBSLS
python gabung_audit/bersihkan_error.py --sumber-tahap2 bahan/SUMBER_BARU.xlsx
```

Kalau batch itu punya dokumen ganda (terlihat di `rangkum_audit`/`gabung_audit`), perintah hapus
ganda juga mengikuti audit yang sama — dengan `FASIH_AUDIT` terpasang cukup seperti biasa, atau
dengan `--audit`:

```powershell
python hapus_ganda/hapus_ganda.py --audit audit
python hapus_ganda/hapus_ganda.py --audit audit --catat
python hapus_ganda/hapus_ganda.py --audit audit --catat --tulis
```

Urutan lengkapnya (Console admin, rekam, `limit: 1`) di
[`PANDUAN_HAPUS_GANDA.md`](PANDUAN_HAPUS_GANDA.md) bagian "Audit di lokasi lain".

Hari berikutnya, buka terminal baru → atur `FASIH_AUDIT` yang **sama** lagi → lanjutkan dari
langkah 2 (`--lewati-selesai` melewati yang sudah tuntas menurut audit batch itu).

(Pilihan persis tiap perintah lihat `--help` masing-masing; yang penting di sini audit-nya.)

---

## Beberapa PC dalam satu batch

- Tiap PC memakai lokasi audit batch yang sama **di PC-nya sendiri** (mis. `audit_batch2\` di
  masing-masing PC) dan mengerjakan rentang baris berbeda (`--dari`/`--sampai`).
- Sesudah semua PC berhenti, kumpulkan audit batch itu dari tiap PC ke satu folder (mis.
  `audit_batch2\pc\pc1.csv`, `pc2.csv`, …) lalu gabungkan ke audit batch — **bukan** ke audit bawaan:

```bash
python gabung_audit/gabung_audit.py --sumber audit_batch2/pc --keluaran audit_batch2/audit_log_gabungan.csv
python gabung_audit/gabung_audit.py --sumber audit_batch2/pc --keluaran audit_batch2/audit_log_gabungan.csv --tulis
```

  Perintah pertama hanya laporan; tambahkan `--tulis` sesudah hasilnya dicek. Rincian cara kerja
  penggabungan: [`PANDUAN_GABUNG_AUDIT.md`](PANDUAN_GABUNG_AUDIT.md).
- `bungkus_pc.py` ikut membungkus folder audit batch yang ada di dalam folder proyek. Meng-extract zip
  di PC yang **masih punya pekerjaan belum digabung** akan menimpa audit PC itu — sebar zip hanya
  sesudah semua audit digabung.

---

## Yang TIDAK ikut pindah bersama audit

- **Kunci satu akun satu proses** (`.proses_<akun>.lock`) tetap di folder kerja. Satu akun tetap
  hanya boleh dipakai satu proses, apa pun audit-nya.
- **Keluaran turunan** — `rangkum_audit.csv`, `bersihkan_error.csv`, `dokumen_tanpa_url.csv`,
  `laporan_gabung*.csv`, `list_api_<akun>.json` — tetap ditulis di folder kerja. Kalau menjalankan
  dua batch bergantian, baca laporannya sebelum batch berikutnya menimpanya (atau gunakan
  `--keluaran`/`--laporan` pada alat yang menyediakannya).
- **Audit approve PML** (`audit_approve_pml.csv`) terpisah dari audit input dan tetap di folder kerja.

---

## Kesalahan yang perlu dihindari

- **Jangan membuka lalu menyimpan audit dengan Excel.** Excel merusak kunci & kode wilayah (mis.
  `1.40E+09`, `5.10806E+15`), dan kunci yang rusak membuat dokumen terbuat **ganda**. Semua alat
  menolak audit yang rusak; pemulihannya lewat `gabung_audit/pulihkan_excel.py`. Kalau ingin melihat
  isinya, buka salinannya, atau buka tanpa menyimpan.
- **Jangan memakai audit baru untuk sheet lama** (lihat peringatan di atas).
- **Jangan berganti lokasi audit di tengah batch** — progres batch terpecah di dua berkas dan
  `--lewati-selesai` tidak lagi mengenali yang sudah selesai.
- Berkas audit berisi nama usaha & email petugas: sudah diabaikan git (`*.csv`, `audit_*.csv`,
  `*.bak-*`), jangan diunggah ke tempat publik.
