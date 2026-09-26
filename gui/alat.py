"""
alat.py — DAFTAR alat yang bisa dijalankan dari GUI + penyusun perintahnya.

GUI tidak punya logika input sendiri: setiap tombol hanya menyusun perintah yang SAMA
dengan yang diketik di terminal (lihat README tiap folder alat), lalu menjalankannya.
Karena itu setiap `arg` di sini WAJIB sama persis dengan opsi argparse skripnya —
tests/test_gui.py memeriksanya langsung dari kode sumber skrip.

Satu alat = dict:
    id, grup, judul, keterangan, skrip (relatif akar proyek, atau "@kbli/..." utk
    proyek generate_kbli terpisah), petunjuk (README), isian[], aksi[], keluaran[]

Satu isian (lihat `isian()`):
    jenis   berkas | berkas_banyak | folder | lokasi_banyak (berkas/folder) | simpan |
            teks | teks_banyak | angka | desimal | centang | centang_nilai | pilihan |
            audit | email | subsls
    arg     opsi CLI ("--sumber"); None = tidak diteruskan (pengendali tampilan saja);
            "@posisi" = argumen posisi (tanpa nama opsi)
    lanjutan, wajib, wajib_jika, tampil_jika, aksi (hanya diteruskan utk aksi ini),
    pengaturan (nama config: kosong -> nilai efektif pengaturan dipakai), pola, bantuan

Satu aksi:
    id, label, tambah (opsi tetap), jenis aman|tulis|bahaya, password (butuh login),
    ya_dulu (GUI minta ketik YA SEBELUM mulai — hanya utk skrip yang mengetik YA sendiri,
    yaitu otomatis.py), konfirmasi (teks dialog biasa sebelum mulai)
"""

from __future__ import annotations

import re
from pathlib import Path

XLSX_CSV = [["Excel / CSV", "*.xlsx *.xlsm *.csv"]]
XLSX = [["Excel", "*.xlsx *.xlsm"]]
CSV = [["CSV", "*.csv"]]
TXT = [["Teks", "*.txt"]]
TXT_XLSX_CSV = [["Daftar (txt / Excel / CSV)", "*.txt *.xlsx *.csv"]]
JSON = [["JSON", "*.json"]]
GEOJSON = [["GeoJSON / JSON", "*.json *.geojson"]]
ZIP = [["Zip", "*.zip"]]
JS = [["Skrip Console", "*.js"]]

POLA_SUBSLS = r"^\d{16}$"
POLA_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
POLA_BARIS = r"^\s*\d+(\s*-\s*\d+)?(\s*,\s*\d+(\s*-\s*\d+)?)*\s*$"
POLA_KOLOM = r"^[A-Za-z]{1,3}$"


def isian(nama: str, jenis: str, label: str, arg: str | None = None, **kw) -> dict:
    return {"nama": nama, "jenis": jenis, "label": label, "arg": arg, **kw}


def aksi(id_: str, label: str, *, tambah: list[str] | None = None, jenis: str = "aman",
         password: bool | str = False, ya_dulu: bool = False, konfirmasi: str = "", **kw) -> dict:
    return {"id": id_, "label": label, "tambah": tambah or [], "jenis": jenis, "password": password,
            "ya_dulu": ya_dulu, "konfirmasi": konfirmasi, **kw}


def keluaran(label: str, path: str, *, jenis: str = "buka", aksi_: list[str] | None = None,
             isian_: str = "") -> dict:
    """jenis: buka (xlsx/csv/folder via Windows) | salin (isi teks ke clipboard) |
    kbli / koordinat (clipboard khusus). path boleh memuat {stem:<isian>}; isian_ = nama
    isian yang, kalau diisi, MENGGANTI path bawaan."""
    return {"label": label, "path": path, "jenis": jenis, "aksi": aksi_, "isian": isian_}


# --- isian yang dipakai banyak alat -------------------------------------------
def _audit(**kw) -> dict:
    return isian("audit", "audit", "Audit (catatan dokumen)", "--audit",
                 bantuan="Kosong = audit bawaan (folder audit/). SATU batch = SATU audit: sheet lama "
                         "dijalankan dgn folder audit-nya sendiri, mis. audit/batch21.", **kw)


def _format(**kw) -> dict:
    return isian("format", "pilihan", "Format sheet", "--format", lanjutan=True,
                 opsi=[["", "tahap2 (bawaan, templat input_usaha.xlsx)"], ["agenda", "agenda (format lama)"]], **kw)


def _sumber(label="Sheet input usaha", **kw) -> dict:
    return isian("sumber", "berkas", label, "--sumber", wajib=True, filter=XLSX_CSV, **kw)


def _akun(nama="akun_tunggal", arg="--akun-tunggal", label="Akun PPL (email)", **kw) -> dict:
    return isian(nama, "email", label, arg, pengaturan="GABUNGAN_AKUN_TUNGGAL",
                 bantuan="Kosong = akun di Pengaturan > Dasar.", **kw)


def _subsls(nama="subsls_tunggal", arg="--subsls-tunggal", label="Subsls wadah (16 digit)", **kw) -> dict:
    return isian(nama, "subsls", label, arg, pengaturan="GABUNGAN_SUBSLS_TUNGGAL",
                 bantuan="Subsls tempat SEMUA dokumen dibuat. Kosong = Pengaturan > Dasar.", **kw)


def _koordinat(opsi=("otomatis", "wajib", "kirim"), **kw) -> dict:
    return isian("koordinat", "pilihan", "Baris tanpa koordinat", "--koordinat", lanjutan=True,
                 opsi=[["", "bawaan (otomatis utk tahap2)"]] + [[o, o] for o in opsi],
                 bantuan="otomatis = dibuat & diisi tapi ditahan DRAFT; wajib = dilewati; "
                         "kirim = tetap dikirim tanpa geotag.", **kw)


def _dari_sampai(bantuan_dari="") -> list[dict]:
    return [isian("dari", "angka", "Dari baris", "--dari", bantuan=bantuan_dari or "Nomor baris sheet (judul = 1)."),
            isian("sampai", "angka", "Sampai baris", "--sampai")]


def _list_json(**kw) -> dict:
    return isian("list_json", "berkas_banyak", "list_api_<akun>.json", "--list-json", lanjutan=True, filter=JSON,
                 bantuan="Hasil unduhan sinkron_list. Kosong = semua di input_usaha/hasil/.", **kw)


def _assignment(**kw) -> dict:
    return isian("assignment_id", "teks", "ID periode (segmen URL list)", "--assignment-id", lanjutan=True,
                 pengaturan="ASSIGNMENT_ID_GABUNGAN", **kw)


def _console(nama_alat: str, folder: str, berkas: str, aksi_=("console",)) -> list[dict]:
    return [keluaran("Salin skrip Console", f"{folder}/hasil/{berkas}", jenis="salin", aksi_=list(aksi_)),
            keluaran("Buka folder hasil", f"{folder}/hasil", jenis="folder")]


GRUP = [
    {"id": "input", "judul": "Input Usaha"},
    {"id": "approve", "judul": "Approve PML"},
    {"id": "fasihsm", "judul": "fasih-sm & Mitra"},
    {"id": "antarpc", "judul": "Antar PC & Koordinat"},
    {"id": "kbli", "judul": "Generate KBLI"},
]

ALAT: list[dict] = [
    # ======================================================================== INPUT USAHA
    {
        "id": "input", "grup": "input", "judul": "Input usaha (cek, dry-run, kirim)",
        "skrip": "input_usaha/jalankan.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Buat, isi & kirim dokumen usaha di fasih-web dari sheet input usaha. Urutan aman: "
                      "Periksa data → Dry-run 1 baris → KIRIM. Kirim tidak bisa dibatalkan; skrip menampilkan "
                      "ringkasan lalu meminta Anda mengetik YA.",
        "isian": [
            _sumber(), _audit(),
            _akun(aksi=["dryrun", "kirim"], wajib_jika={"@aksi": ["dryrun", "kirim"], "per_baris": ["0"]}),
            _subsls(aksi=["dryrun", "kirim"], wajib_jika={"@aksi": ["dryrun", "kirim"], "per_baris": ["0"]}),
            isian("baris", "teks", "Nomor baris", "--baris", pola=POLA_BARIS, contoh="2,5,10-20",
                  bantuan="Kosong = semua baris (atau pakai Dari/Sampai)."),
            *_dari_sampai("Membagi pekerjaan antar-PC, mis. 2 sampai 500."),
            isian("limit", "angka", "Batas jumlah baris", "--limit", bantuan="Mulai dgn 1 saat pertama kali."),
            isian("lewati_selesai", "centang", "Lewati baris yang sudah selesai menurut audit", "--lewati-selesai",
                  bawaan=True),
            isian("sinkron_dulu", "centang", "Sinkron dulu dgn daftar dokumen di server", "--sinkron-dulu",
                  bawaan=True, aksi=["dryrun", "kirim"],
                  bantuan="Dokumen buatan PC lain dikenali & dibuka, bukan dibuat lagi."),
            isian("izinkan_wilayah_beda", "centang", "Izinkan wilayah BLOK I beda (beberapa subsls wadah)",
                  "--izinkan-wilayah-beda", aksi=["dryrun", "kirim"]),
            isian("hanya_galat", "centang", "Hanya baris yang ditandai galat oleh server", "--hanya-galat"),
            isian("abaikan_cek_total", "centang", "Jangan cocokkan kolom TOTAL sheet dgn rinciannya",
                  "--abaikan-cek-total"),
            _koordinat(),
            isian("kodepos", "teks", "Kodepos cadangan", "--kodepos", lanjutan=True, pola=r"^\d{5}$",
                  bantuan="Dipakai HANYA utk desa yang belum ada di daftar kodepos (Pengaturan > Wilayah)."),
            _format(),
            isian("urut_sheet", "centang", "Kerjakan murni urut baris sheet", "--urut-sheet", lanjutan=True),
            isian("coba_terkunci", "centang", "Coba lagi dokumen TERKUNCI (sesudah admin membukanya)",
                  "--coba-terkunci", lanjutan=True),
            isian("paksa", "centang", "Paksa: abaikan keputusan audit utk baris terpilih (wajib isi Baris; "
                  "dokumen dari ID sheet/URL audit, tidak pernah dibuat baru)", "--paksa", lanjutan=True),
            isian("paralel", "centang", "Berjalan paralel dgn batch lain (rentang tidak tumpang tindih)",
                  "--paralel", lanjutan=True),
            isian("per_baris", "centang", "Alur lama: dokumen per akun & subsls baris", "--per-baris", lanjutan=True),
            isian("baris_per_sesi", "angka", "Login ulang tiap N baris", "--baris-per-sesi", lanjutan=True,
                  pengaturan="GABUNGAN_BARIS_PER_SESI"),
            isian("maks_error_beruntun", "angka", "Berhenti setelah N error beruntun", "--maks-error-beruntun",
                  lanjutan=True, contoh="3"),
            isian("maks_tanpa_url", "angka", "Berhenti setelah N dokumen tanpa URL", "--maks-tanpa-url",
                  lanjutan=True, contoh="3"),
            _assignment(aksi=["dryrun", "kirim"]),
            isian("audit_baru", "centang", "Audit baru untuk batch baru (lewati pengaman audit)", "--audit-baru",
                  lanjutan=True, bantuan="HANYA utk batch yang benar-benar baru dgn audit kosong."),
            isian("dump_dom", "centang", "Simpan peta dataKey (debug)", "--dump-dom", lanjutan=True),
        ],
        "aksi": [
            aksi("cek", "Periksa data (tanpa browser)", tambah=["--cek"]),
            aksi("dryrun", "Dry-run (isi, TIDAK kirim)", password=True),
            aksi("kirim", "KIRIM (tidak bisa dibatalkan)", tambah=["--submit"], jenis="bahaya", password=True),
        ],
        "keluaran": [
            keluaran("Buka cek_input.csv", "input_usaha/hasil/cek_input.csv", aksi_=["cek"]),
            keluaran("Buka folder hasil", "input_usaha/hasil", jenis="folder"),
        ],
    },
    {
        "id": "otomatis", "grup": "input", "judul": "Input otomatis (tanpa ditunggui)",
        "skrip": "input_usaha/otomatis.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Menjalankan input + KIRIM sampai tuntas: mengulang sendiri kalau berhenti, pindah ke akun "
                      "cadangan kalau kena limit. Skrip ini mengetik YA sendiri, jadi GUI meminta YA dari Anda "
                      "SEBELUM mulai. Satu akun hanya boleh dipakai satu PC/proses.",
        "isian": [
            _sumber(), _audit(),
            isian("dari", "angka", "Dari baris", "--dari", wajib=True),
            isian("sampai", "angka", "Sampai baris", "--sampai", wajib=True),
            isian("akun", "email", "Akun PPL utama", "--akun", wajib=True),
            isian("subsls", "subsls", "Subsls akun utama", "--subsls", wajib=True),
            isian("akun_cadangan", "email", "Akun cadangan (kalau kena limit)", "--akun-cadangan"),
            isian("subsls_cadangan", "subsls", "Subsls akun cadangan", "--subsls-cadangan"),
            isian("label_pc", "teks", "Label PC", "--label-pc", pola=r"^[\w-]*$", contoh="_pc2",
                  bantuan="Akhiran salinan audit & log, supaya audit antar-PC tidak tertukar."),
            isian("jeda_retry", "angka", "Jeda ulang (detik)", "--jeda-retry", lanjutan=True),
            isian("jeda_retry_maks", "angka", "Jeda ulang maksimal (detik)", "--jeda-retry-maks", lanjutan=True),
        ],
        "aksi": [
            aksi("jalan", "Jalankan otomatis + KIRIM", jenis="bahaya", password=True, ya_dulu=True),
        ],
        "keluaran": [keluaran("Buka folder hasil", "input_usaha/hasil", jenis="folder")],
    },
    {
        "id": "sinkron", "grup": "input", "judul": "Sinkron dgn daftar dokumen server",
        "skrip": "input_usaha/sinkron_list.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Mencocokkan list PENDATAAN fasih-web (READ-ONLY) dgn sheet & audit. Tinjau laporannya dulu, "
                      "baru 'Tulis ke audit'. Jalankan sebelum & sesudah tiap batch.",
        "isian": [
            isian("sumber", "berkas_banyak", "Sheet input usaha", "--sumber", wajib=True, filter=XLSX_CSV),
            _audit(),
            _akun(wajib=True), _subsls(wajib=True),
            isian("dari_json", "berkas", "Pakai daftar unduhan sebelumnya (tanpa login)", "--dari-json", filter=JSON,
                  bantuan="list_api_<akun>.json di input_usaha/hasil/. Kosong = baca server (butuh password)."),
            isian("simpan_json", "simpan", "Simpan daftar server ke", "--simpan-json", lanjutan=True, filter=JSON,
                  ekstensi=".json"),
            _format(), _assignment(),
        ],
        "aksi": [
            aksi("laporan", "Laporan (tidak menulis)", password="kecuali:dari_json"),
            aksi("tulis", "Tulis ke audit", tambah=["--tulis"], jenis="tulis", password="kecuali:dari_json",
                 konfirmasi="Hasil sinkron akan DITAMBAHKAN ke audit (server tidak diubah). Sudah meninjau laporannya?"),
        ],
        "keluaran": [
            keluaran("Buka sinkron_list.csv", "input_usaha/hasil/sinkron_list.csv"),
            keluaran("Buka folder hasil", "input_usaha/hasil", jenis="folder"),
        ],
    },
    {
        "id": "rangkum", "grup": "input", "judul": "Rangkuman progres",
        "skrip": "input_usaha/rangkum_audit.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Progres per BARIS sheet dari audit (+ daftar server) dan alasan tiap baris yang tidak akan "
                      "dikerjakan run berikutnya. Offline.",
        "isian": [
            _sumber(), _audit(), _akun(), _subsls(), *_dari_sampai(),
            _koordinat(opsi=("wajib", "otomatis", "kirim")),
            isian("tanpa_submit", "centang", "Hitung seperti run dry-run", "--tanpa-submit"),
            isian("daftar", "angka", "Cetak N baris pertama yang belum dikerjakan", "--daftar"),
            isian("tanpa_server", "centang", "Abaikan daftar server (murni dari audit)", "--tanpa-server"),
            _list_json(),
            isian("csv", "simpan", "Simpan laporan ke", "--csv", lanjutan=True, filter=CSV, ekstensi=".csv"),
            _format(),
        ],
        "aksi": [aksi("jalan", "Buat rangkuman")],
        "keluaran": [keluaran("Buka rangkum_audit.csv", "input_usaha/hasil/rangkum_audit.csv", isian_="csv")],
    },
    {
        "id": "kontrol", "grup": "input", "judul": "Kontrol kualitas sheet",
        "skrip": "input_usaha/kontrol_kualitas.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Pemeriksaan yang sama dgn 'Periksa data', dijadikan Excel berwarna per sel "
                      "(Ringkasan, Temuan, Per PPL, Data bertanda). Offline.",
        "isian": [
            _sumber(),
            isian("baris", "teks", "Nomor baris", "--baris", pola=POLA_BARIS, contoh="2,5,10-20"),
            *_dari_sampai(),
            isian("hanya_belum_terkirim", "centang", "Lewati baris yang sudah terkirim menurut audit",
                  "--hanya-belum-terkirim"),
            _audit(),
            isian("per_ppl", "centang_nilai", "Tulis juga satu berkas per PPL", "--per-ppl", jenis_nilai="folder",
                  bantuan="Folder tujuan boleh kosong (bawaan input_usaha/hasil/kontrol_kualitas_per_ppl/)."),
            isian("tanpa_salinan", "centang", "Tanpa lembar 'Data bertanda' (lebih cepat)", "--tanpa-salinan"),
            isian("abaikan_cek_total", "centang", "Jangan cocokkan kolom TOTAL", "--abaikan-cek-total"),
            _koordinat(),
            isian("kodepos", "teks", "Kodepos cadangan", "--kodepos", lanjutan=True, pola=r"^\d{5}$"),
            isian("per_baris", "centang", "Periksa spt alur lama (per akun & subsls baris)", "--per-baris",
                  lanjutan=True),
            isian("keluaran", "simpan", "Simpan Excel hasil ke", "--keluaran", lanjutan=True, filter=XLSX,
                  ekstensi=".xlsx"),
            isian("csv", "simpan", "Tulis juga CSV temuan ke", "--csv", lanjutan=True, filter=CSV, ekstensi=".csv"),
            _format(),
        ],
        "aksi": [aksi("jalan", "Periksa kualitas")],
        "keluaran": [
            keluaran("Buka kontrol_kualitas.xlsx", "input_usaha/hasil/kontrol_kualitas.xlsx", isian_="keluaran"),
            keluaran("Buka folder hasil", "input_usaha/hasil", jenis="folder"),
        ],
    },
    {
        "id": "bersihkan", "grup": "input", "judul": "Daftar perbaikan (bersihkan error)",
        "skrip": "input_usaha/bersihkan_error.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Mengelompokkan sisa masalah (ULANGI / LENGKAPI_KOORDINAT / PERBAIKI_DATA / SINKRON_DULU / "
                      "MANUAL) dan mencetak perintah untuk membereskannya. Offline & read-only.",
        "isian": [
            isian("sumber", "berkas_banyak", "Sheet sumber", "--sumber", filter=XLSX_CSV,
                  bantuan="Tanpa sheet, nomor baris tidak bisa dipetakan."),
            isian("audit", "lokasi_banyak", "Audit (boleh lebih dari satu)", "--audit",
                  bantuan="Kosong = audit bawaan. Boleh folder utk gabungan beberapa PC."),
            isian("akun", "teks_banyak", "Hanya akun ini", "--akun", contoh="ppl.satu@..., ppl.dua@..."),
            *_dari_sampai(),
            isian("hanya_galat_server", "centang", "Hanya dokumen yang ditandai galat oleh server",
                  "--hanya-galat-server"),
            isian("izinkan_wilayah_beda", "centang", "Tambahkan --izinkan-wilayah-beda ke perintah",
                  "--izinkan-wilayah-beda"),
            isian("tanpa_submit", "centang", "Perintah yang dicetak tanpa --submit", "--tanpa-submit"),
            isian("sumber_tahap2", "berkas_banyak", "Sheet format tahap 2 tambahan", "--sumber-tahap2",
                  lanjutan=True, filter=XLSX_CSV),
            _list_json(),
            isian("keluaran", "simpan", "Simpan CSV ke", "--keluaran", lanjutan=True, filter=CSV, ekstensi=".csv"),
            _format(),
        ],
        "aksi": [aksi("jalan", "Susun daftar perbaikan")],
        "keluaran": [keluaran("Buka bersihkan_error.csv", "input_usaha/hasil/bersihkan_error.csv", isian_="keluaran")],
    },
    {
        "id": "tulis_id", "grup": "input", "judul": "Isi kolom 'ID Dokumen FASIH' dari audit",
        "skrip": "input_usaha/tulis_id_sumber.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Mengisi kolom ID dokumen di sheet sumber dari audit (offline). Sel yang sudah berisi tidak "
                      "pernah ditimpa. TUTUP berkasnya di Excel sebelum menulis.",
        "isian": [_sumber(label="Sheet sumber"), _audit(), _format()],
        "aksi": [
            aksi("laporan", "Laporan (tidak menulis)"),
            aksi("tulis", "Tulis ke sheet", tambah=["--tulis"], jenis="tulis",
                 konfirmasi="ID dokumen akan DITULIS ke sheet sumber. Berkasnya sudah ditutup di Excel?"),
        ],
        "keluaran": [],
    },
    {
        "id": "kodepos", "grup": "input", "judul": "Kodepos per desa dari data lama",
        "skrip": "input_usaha/kodepos_desa.py", "petunjuk": "input_usaha/README.md",
        "keterangan": "Laporan kodepos per desa yang dibutuhkan sheet, disusun dari sheet lama berkolom kodepos. "
                      "Untuk MEMAKAI hasilnya: Pengaturan > Wilayah > 'Susun dari sheet lama' (GUI tidak menulis "
                      "inti/config_lokal.py).",
        "isian": [
            isian("sumber", "berkas", "Sheet tahap 2 yang butuh kodepos", "--sumber", wajib=True, filter=XLSX_CSV),
            isian("dari", "berkas_banyak", "Sheet lama berkolom kodepos (format agenda)", "--dari", filter=XLSX_CSV),
        ],
        "aksi": [aksi("laporan", "Laporan kodepos")],
        "keluaran": [],
    },
    # ======================================================================== APPROVE PML
    {
        "id": "approve", "grup": "approve", "judul": "Approve PML",
        "skrip": "approve_pml/approve_pml.py", "petunjuk": "approve_pml/README.md",
        "keterangan": "Approve dokumen yang sudah dikirim PPL, oleh akun PML. Dokumen hanya di-approve kalau API "
                      "menyatakan SUBMITTED oleh PPL yang benar. Mulai dgn Batas = 1. Approve tidak bisa dibatalkan; "
                      "skrip meminta Anda mengetik YA.",
        "isian": [
            isian("target", "pilihan", "Sumber target", None, bawaan="audit",
                  opsi=[["audit", "Audit input (satu PML & satu PPL)"],
                        ["rencana", "File SQL Lab (banyak PML)"],
                        ["daftar", "Salinan tabel Data fasih-sm (banyak PML)"]]),
            isian("akun_pml", "teks", "Akun PML", "--akun-pml", wajib_jika={"target": ["audit"]},
                  bantuan="Mode file: kosong = semua PML di file; boleh beberapa dipisah koma."),
            isian("akun_ppl", "email", "Akun PPL (akun_login di audit)", "--akun-ppl",
                  tampil_jika={"target": ["audit"]}, wajib_jika={"target": ["audit"]}),
            isian("rencana", "berkas", "File SQL Lab", "--rencana", filter=XLSX_CSV,
                  tampil_jika={"target": ["rencana"]}, wajib_jika={"target": ["rencana"]}),
            isian("daftar", "berkas", "Salinan tabel Data fasih-sm", "--daftar", filter=XLSX_CSV,
                  tampil_jika={"target": ["daftar"]}, wajib_jika={"target": ["daftar"]}),
            isian("limit", "angka", "Batas dokumen PER PML", "--limit", bantuan="Mulai dgn 1."),
            isian("abaikan_audit_approve", "centang", "Cek ulang juga yang di audit sudah APPROVED",
                  "--abaikan-audit-approve", tampil_jika={"target": ["rencana", "daftar"]}),
            isian("termasuk_di_luar_audit", "centang", "Ikut proses dokumen list yang tidak tercatat di audit",
                  "--termasuk-di-luar-audit", tampil_jika={"target": ["audit"]}, lanjutan=True),
            _audit(),
            isian("login_manual", "centang", "Login manual di jendela browser", "--login-manual", lanjutan=True),
            isian("maks_error_beruntun", "angka", "Berhenti setelah N error beruntun", "--maks-error-beruntun",
                  lanjutan=True),
            _assignment(),
        ],
        "aksi": [
            aksi("cek", "Rencana saja (tanpa browser)", tambah=["--cek"]),
            aksi("dryrun", "Dry-run (periksa, TIDAK approve)", password=True),
            aksi("approve", "APPROVE (tidak bisa dibatalkan)", tambah=["--eksekusi"], jenis="bahaya", password=True),
        ],
        "keluaran": [
            keluaran("Buka audit_approve_pml.csv", "audit/audit_approve_pml.csv"),
            keluaran("Buka folder hasil", "approve_pml/hasil", jenis="folder"),
        ],
    },
    # ======================================================================== FASIH-SM & MITRA
    {
        "id": "ganti_moda", "grup": "fasihsm", "judul": "Ganti mode CAPI ↔ PAPI",
        "skrip": "fasih_sm/ganti_moda/ubah_moda.py", "petunjuk": "fasih_sm/ganti_moda/README.md",
        "keterangan": "Menyiapkan skrip Console untuk mengganti mode assignment di fasih-sm (Chrome biasa, akun "
                      "yang berhak Ganti Mode). Tempel skripnya di Console halaman Data survei; eksekusinya diatur di "
                      "Console (lihat Petunjuk). Jalur Playwright tetap lewat terminal.",
        "isian": [
            isian("target", "pilihan", "Target dari", None, bawaan="sumber",
                  opsi=[["sumber", "Sheet input usaha (1 PAPI per subsls)"],
                        ["daftar", "Daftar KODE IDENTITAS"],
                        ["subsls", "Daftar IDSUBSLS (semua assignment subsls)"]]),
            isian("sumber", "berkas", "Sheet input usaha", "--sumber", filter=XLSX_CSV,
                  tampil_jika={"target": ["sumber"]}, wajib_jika={"target": ["sumber"]}),
            isian("daftar", "berkas", "Daftar kode identitas (.xlsx/.csv/.txt)", "--daftar", filter=TXT_XLSX_CSV,
                  tampil_jika={"target": ["daftar"]}, wajib_jika={"target": ["daftar"]}),
            isian("subsls", "berkas", "Daftar idsubsls (berkas, atau ketik dipisah koma)", "--subsls",
                  filter=TXT_XLSX_CSV, tampil_jika={"target": ["subsls"]}, wajib_jika={"target": ["subsls"]}),
            isian("ke", "pilihan", "Mode tujuan", "--ke", opsi=[["", "bawaan (PAPI)"], ["PAPI", "PAPI"], ["CAPI", "CAPI"]],
                  wajib_jika={"target": ["subsls"]}),
            isian("cakupan", "pilihan", "Cakupan per subsls", "--cakupan", tampil_jika={"target": ["sumber"]},
                  opsi=[["", "bawaan (satu PAPI per subsls)"], ["satu", "satu"], ["semua", "semua CAPI"]]),
            isian("hanya_siap", "centang", "Hanya subsls yang punya baris SIAP input", "--hanya-siap",
                  tampil_jika={"target": ["sumber"]}),
            isian("idsubsls", "teks", "Batasi ke idsubsls (pisah koma)", "--idsubsls", lanjutan=True),
            isian("sheet", "teks", "Nama sheet (.xlsx daftar)", "--sheet", lanjutan=True),
            isian("lewati_selesai", "centang", "Lewati subsls yang sudah tuntas", "--lewati-selesai", lanjutan=True),
            _assignment(),
        ],
        "aksi": [
            aksi("cek", "Daftar target (tanpa browser)", tambah=["--cek"]),
            aksi("console", "Buat skrip Console", tambah=["--console"]),
        ],
        "keluaran": _console("ganti_moda", "fasih_sm/ganti_moda", "ubah_moda_console.siap.js"),
    },
    {
        "id": "buka_wilayah", "grup": "fasihsm", "judul": "Buka wilayah (Listing Selesai → Proses Listing)",
        "skrip": "fasih_sm/buka_wilayah/buka_wilayah.py", "petunjuk": "fasih_sm/buka_wilayah/README.md",
        "keterangan": "Menyiapkan skrip Console fasih-sm (akun admin) untuk membuka wilayah yang sudah "
                      "Listing Selesai. Eksekusi (tidak bisa dibatalkan) terjadi di Console.",
        "isian": [
            isian("cakupan", "pilihan", "Cakupan", None, bawaan="daftar",
                  opsi=[["daftar", "Daftar idsubsls (berkas teks)"], ["semua", "SEMUA subsls periode"]],
                  arg_nilai={"semua": ["--semua"]}),
            isian("daftar", "berkas", "Daftar idsubsls (satu per baris)", "--daftar", filter=TXT,
                  tampil_jika={"cakupan": ["daftar"]}, wajib_jika={"cakupan": ["daftar"]}),
        ],
        "aksi": [aksi("console", "Buat skrip Console", tambah=["--console"])],
        "keluaran": _console("buka_wilayah", "fasih_sm/buka_wilayah", "buka_wilayah_console.siap.js"),
    },
    {
        "id": "tandai_selesai", "grup": "fasihsm", "judul": "Tandai selesai listing",
        "skrip": "fasih_sm/tandai_selesai/tandai_selesai.py", "petunjuk": "fasih_sm/tandai_selesai/README.md",
        "keterangan": "Kebalikan Buka wilayah: skrip Console untuk menandai wilayah Selesai Listing (akun admin).",
        "isian": [
            isian("cakupan", "pilihan", "Cakupan", None, bawaan="daftar",
                  opsi=[["daftar", "Daftar idsubsls (berkas teks)"], ["semua", "SEMUA subsls periode"]],
                  arg_nilai={"semua": ["--semua"]}),
            isian("daftar", "berkas", "Daftar idsubsls (satu per baris)", "--daftar", filter=TXT,
                  tampil_jika={"cakupan": ["daftar"]}, wajib_jika={"cakupan": ["daftar"]}),
        ],
        "aksi": [aksi("console", "Buat skrip Console", tambah=["--console"])],
        "keluaran": _console("tandai_selesai", "fasih_sm/tandai_selesai", "tandai_selesai_console.siap.js"),
    },
    {
        "id": "pindah_wilayah", "grup": "fasihsm", "judul": "Pindah wilayah assignment",
        "skrip": "fasih_sm/pindah_wilayah/pindah_wilayah.py", "petunjuk": "fasih_sm/pindah_wilayah/README.md",
        "keterangan": "Memindahkan dokumen dari subsls wadah ke wilayah aslinya (fasih-sm, akun admin), sesudah "
                      "di-approve. Jangan jalankan selagi batch input akun yang sama berjalan.",
        "isian": [
            isian("sumber", "berkas_banyak", "Sheet input usaha", "--sumber", wajib=True, filter=XLSX_CSV),
            _audit(),
            isian("dari_approve", "centang_nilai", "Hanya dokumen yang sudah APPROVED (audit approve)",
                  "--dari-approve", jenis_nilai="berkas", filter=CSV, bawaan=True,
                  bantuan="Berkas boleh kosong (bawaan audit/audit_approve_pml.csv)."),
            isian("hanya_tercatat", "centang", "Hanya baris yang dokumennya tercatat di audit", "--hanya-tercatat"),
            isian("daftar_tujuan", "simpan", "Tulis daftar subsls tujuan ke (bahan Buka wilayah)",
                  "--daftar-tujuan", filter=TXT, ekstensi=".txt"),
            isian("subsls_asal", "teks_banyak", "Subsls asal tambahan", "--subsls-asal", lanjutan=True),
            _format(),
        ],
        "aksi": [
            aksi("rencana", "Rencana saja"),
            aksi("console", "Buat skrip Console", tambah=["--console"]),
        ],
        "keluaran": _console("pindah_wilayah", "fasih_sm/pindah_wilayah", "pindah_wilayah_console.siap.js"),
    },
    {
        "id": "hapus_ganda", "grup": "fasihsm", "judul": "Hapus dokumen ganda",
        "skrip": "fasih_sm/hapus_ganda/hapus_ganda.py", "petunjuk": "fasih_sm/hapus_ganda/README.md",
        "keterangan": "Skrip Console (akun ADMIN fasih-sm) untuk menghapus dokumen ganda dari audit. SESUDAH "
                      "menghapus, jalankan 'Catat ke audit' supaya audit menunjuk dokumen yang dipertahankan.",
        "isian": [
            _audit(),
            isian("akun", "teks_banyak", "Hanya grup yang punya dokumen akun ini", "--akun"),
            isian("semua_mode", "centang", "Ikutkan dokumen CAPI/CAWI (bawaan hanya PAPI)", "--semua-mode",
                  lanjutan=True),
            _list_json(),
            isian("keluaran", "simpan", "Simpan skrip Console ke", "--keluaran", lanjutan=True, filter=JS,
                  ekstensi=".js", aksi=["console"]),
        ],
        "aksi": [
            aksi("console", "Buat skrip Console"),
            aksi("catat", "Laporan catat hasil hapus", tambah=["--catat"]),
            aksi("catat_tulis", "Catat ke audit", tambah=["--catat", "--tulis"], jenis="tulis",
                 konfirmasi="Audit akan diarahkan ke dokumen yang dipertahankan (dari ganda_dihapus*.csv). Lanjut?"),
        ],
        "keluaran": [
            keluaran("Salin skrip Console", "fasih_sm/hapus_ganda/hasil/hapus_ganda_console.siap.js", jenis="salin",
                     aksi_=["console"], isian_="keluaran"),
            keluaran("Buka folder hasil", "fasih_sm/hapus_ganda/hasil", jenis="folder"),
        ],
    },
    {
        "id": "reset_mitra", "grup": "fasihsm", "judul": "Reset password akun PPL (manajemen-mitra)",
        "skrip": "reset_mitra/reset_mitra.py", "petunjuk": "reset_mitra/README.md",
        "keterangan": "Skrip Console halaman Akun Mitra untuk menyamakan password akun PPL. Password BARU = "
                      "password yang Anda ketik di GUI (sesi ini).",
        "isian": [
            isian("target", "pilihan", "Daftar email dari", None, bawaan="daftar",
                  opsi=[["daftar", "Berkas teks (satu email per baris)"], ["sumber", "Sheet input usaha (kolom Akun PPL)"]]),
            isian("daftar", "berkas", "Daftar email PPL", "--daftar", filter=TXT,
                  tampil_jika={"target": ["daftar"]}, wajib_jika={"target": ["daftar"]}),
            isian("sumber", "berkas", "Sheet input usaha", "--sumber", filter=XLSX_CSV,
                  tampil_jika={"target": ["sumber"]}, wajib_jika={"target": ["sumber"]}),
            isian("format", "pilihan", "Format sheet", "--format", lanjutan=True, tampil_jika={"target": ["sumber"]},
                  opsi=[["", "tahap2 (bawaan)"], ["agenda", "agenda (format lama)"]]),
            isian("email", "teks", "Batasi ke email (pisah koma)", "--email"),
        ],
        "aksi": [
            aksi("cek", "Daftar email", tambah=["--cek"]),
            aksi("console", "Buat skrip Console", tambah=["--console"], password=True),
        ],
        "keluaran": [
            keluaran("Salin skrip Console", "reset_mitra/hasil/reset_mitra_console.siap.js", jenis="salin",
                     aksi_=["console"]),
            keluaran("Buka target_reset_mitra.csv", "reset_mitra/hasil/target_reset_mitra.csv", aksi_=["cek"]),
        ],
    },
    # ======================================================================== ANTAR PC & KOORDINAT
    {
        "id": "koordinat", "grup": "antarpc", "judul": "Koordinat pengganti",
        "skrip": "koordinat/koordinat_pengganti.py", "petunjuk": "koordinat/README.md",
        "keterangan": "Merapikan koordinat sheet tahap 2 yang rusak / jauh dari subsls-nya. Hasilnya berkas BARU; "
                      "Latitude/Longitude hasilnya bisa langsung disalin ke sheet (nomor baris sama).",
        "isian": [
            isian("sumber", "berkas", "Sheet tahap 2", "--sumber", wajib=True, filter=XLSX),
            isian("peta", "berkas", "Peta poligon subsls (GeoJSON)", "--peta", filter=GEOJSON,
                  pengaturan="PETA_SLS_PATH", bantuan="Kosong = Pengaturan > Wilayah."),
            isian("listing", "berkas", "Titik listing (CSV)", "--listing", filter=CSV, pengaturan="TITIK_LISTING_PATH"),
            isian("jalan", "berkas", "Jaringan jalan (GeoJSON)", "--jalan", filter=GEOJSON, pengaturan="JALAN_PATH"),
            isian("batas_m", "desimal", "Batas di luar subsls (meter)", "--batas-m", contoh="500"),
            isian("jarak_jalan_m", "desimal", "'Dekat jalan' (meter)", "--jarak-jalan-m", lanjutan=True, contoh="50"),
            isian("unduh_jalan", "centang", "Unduh dulu jalan OpenStreetMap (butuh internet)", "--unduh-jalan",
                  lanjutan=True),
            isian("keluaran", "simpan", "Simpan hasil ke", "--keluaran", lanjutan=True, filter=XLSX, ekstensi=".xlsx"),
        ],
        "aksi": [aksi("jalan", "Buat koordinat pengganti")],
        "keluaran": [
            keluaran("Salin Latitude/Longitude", "koordinat/hasil/{stem:sumber}_koordinat.xlsx", jenis="koordinat",
                     isian_="keluaran"),
            keluaran("Buka hasil", "koordinat/hasil/{stem:sumber}_koordinat.xlsx", isian_="keluaran"),
        ],
    },
    {
        "id": "gabung_audit", "grup": "antarpc", "judul": "Gabung audit beberapa PC",
        "skrip": "antar_pc/gabung_audit.py", "petunjuk": "antar_pc/README.md",
        "keterangan": "Menyatukan audit_log_gabungan.csv dari beberapa PC + laporan progres. Tanpa 'Tulis' hanya "
                      "laporan. Hasil masuk <folder sumber>/hasil/.",
        "isian": [
            isian("sumber", "lokasi_banyak", "Audit tiap PC (berkas atau folder)", "--sumber", wajib=True),
            isian("sheet", "berkas", "Sheet sumber (utk menghitung yang belum dikerjakan)", "--sheet", filter=XLSX_CSV),
            isian("buang_akun", "teks_banyak", "Buang semua baris milik akun", "--buang-akun", lanjutan=True),
            isian("keluaran", "simpan", "Simpan audit gabungan ke", "--keluaran", lanjutan=True, filter=CSV,
                  ekstensi=".csv", bantuan="Kosong = <folder sumber>/hasil/audit_log_gabungan.csv."),
            isian("laporan", "simpan", "Laporan per dokumen", "--laporan", lanjutan=True, filter=CSV, ekstensi=".csv"),
            isian("agregat", "simpan", "Laporan rekap", "--agregat", lanjutan=True, filter=CSV, ekstensi=".csv"),
            isian("daftar_ganda", "simpan", "Daftar dokumen ganda", "--daftar-ganda", lanjutan=True, filter=CSV,
                  ekstensi=".csv"),
            _list_json(), _format(),
        ],
        "aksi": [
            aksi("laporan", "Laporan (tidak menulis)"),
            aksi("tulis", "Tulis audit gabungan", tambah=["--tulis"], jenis="tulis",
                 konfirmasi="Audit gabungan akan ditulis (audit lama di tujuan dicadangkan .bak). Tidak ada peringatan "
                            "bentrok di laporan?"),
        ],
        "keluaran": [],
    },
    {
        "id": "gabung_id", "grup": "antarpc", "judul": "Gabung kolom ID dokumen beberapa PC",
        "skrip": "antar_pc/gabung_id_sumber.py", "petunjuk": "antar_pc/README.md",
        "keterangan": "Menyatukan kolom 'ID Dokumen FASIH' dari salinan sheet PC lain (offline).",
        "isian": [
            isian("utama", "berkas", "Sheet utama", "--utama", wajib=True, filter=XLSX_CSV),
            isian("sumber", "lokasi_banyak", "Salinan sheet PC lain (berkas / folder)", "--sumber", wajib=True),
            isian("keluaran", "simpan", "Sheet hasil", "--keluaran", lanjutan=True, filter=XLSX, ekstensi=".xlsx",
                  bantuan="Kosong = <folder sumber>/hasil/<nama sheet utama>. Sama dgn sheet utama = isi langsung."),
            isian("laporan", "simpan", "Laporan CSV", "--laporan", lanjutan=True, filter=CSV, ekstensi=".csv"),
            _format(),
        ],
        "aksi": [
            aksi("laporan", "Laporan (tidak menulis)"),
            aksi("tulis", "Tulis sheet hasil", tambah=["--tulis"], jenis="tulis",
                 konfirmasi="Sheet hasil akan ditulis. Berkasnya sudah ditutup di Excel?"),
        ],
        "keluaran": [],
    },
    {
        "id": "pulihkan_excel", "grup": "antarpc", "judul": "Pulihkan audit yang rusak karena Excel",
        "skrip": "antar_pc/pulihkan_excel.py", "petunjuk": "antar_pc/README.md",
        "keterangan": "Memulihkan audit yang pernah dibuka lalu DISIMPAN Excel (kunci 1.40E+09, idsubsls "
                      "5.10806E+15). Nilai yang tidak pasti tidak ditulis.",
        "isian": [
            isian("audit", "berkas_banyak", "Audit yang dipulihkan", "--audit", filter=CSV,
                  bantuan="Kosong = audit_log_gabungan.csv & audit/pc/**/*.csv."),
            isian("rujukan", "berkas_banyak", "Audit UTUH tambahan sbg rujukan", "--rujukan", filter=CSV),
            isian("sheet", "berkas", "Sheet sumber (cadangan kunci)", "--sheet", filter=XLSX_CSV),
            _format(),
        ],
        "aksi": [
            aksi("rencana", "Rencana (tidak menulis)"),
            aksi("tulis", "Tulis hasil pulihan", tambah=["--tulis"], jenis="tulis",
                 konfirmasi="Audit akan ditulis ulang (berkas lama dicadangkan .bak). Lanjut?"),
        ],
        "keluaran": [],
    },
    {
        "id": "bungkus_pc", "grup": "antarpc", "judul": "Bungkus proyek utk PC lain (zip)",
        "skrip": "antar_pc/bungkus_pc.py", "petunjuk": "antar_pc/README.md",
        "keterangan": "Satu zip ringan utk PC lain. PC yang masih mengerjakan batch: centang 'Kode saja' supaya "
                      "audit & sheet-nya tidak tertimpa. Pengaturan GUI (gui/pengaturan.json) tidak ikut — pakai "
                      "Pengaturan > Ekspor.",
        "isian": [
            isian("kode_saja", "centang", "Kode saja (tanpa audit/, bahan/, config_lokal.py)", "--kode-saja"),
            isian("kecuali", "teks_banyak", "Buang juga folder/berkas", "--kecuali", contoh="bahan/lama, *.bak"),
            isian("rinci", "centang", "Cetak setiap berkas yang ikut", "--rinci", lanjutan=True),
            isian("keluaran", "simpan", "Simpan zip ke", "--keluaran", lanjutan=True, filter=ZIP, ekstensi=".zip",
                  aksi=["zip"]),
        ],
        "aksi": [
            aksi("daftar", "Lihat isi (tanpa membuat zip)", tambah=["--daftar"]),
            aksi("zip", "Buat zip"),
        ],
        "keluaran": [keluaran("Buka folder hasil", "antar_pc/hasil", jenis="folder", aksi_=["zip"])],
    },
    {
        "id": "pindah_struktur", "grup": "antarpc", "judul": "Pindah ke struktur folder baru",
        "skrip": "antar_pc/pindah_struktur.py", "petunjuk": "antar_pc/README.md",
        "keterangan": "Sekali per PC yang masih memakai struktur lama (audit di akar proyek). Tidak pernah "
                      "menghapus/menimpa berkas.",
        "isian": [
            isian("audit_lama_ke", "teks", "Folder tujuan audit LAMA", "--audit-lama-ke", lanjutan=True,
                  contoh="audit/batch21"),
        ],
        "aksi": [
            aksi("rencana", "Lihat rencana"),
            aksi("jalankan", "Pindahkan", tambah=["--jalankan"], jenis="tulis",
                 konfirmasi="Berkas akan DIPINDAH ke struktur baru (tidak ada yang dihapus). Tidak ada proses input "
                            "yang sedang berjalan?"),
        ],
        "keluaran": [],
    },
    # ======================================================================== KBLI (proyek terpisah)
    {
        "id": "kbli", "grup": "kbli", "judul": "Generate KBLI",
        "skrip": "@kbli/generate_kbli.py", "petunjuk": "@kbli/README.md",
        "keterangan": "Menebak kode KBLI 2025 dari 8b/13a/13f (proyek generate_kbli terpisah). Hasilnya disalin ke "
                      "clipboard sebagai Kode + Judul KBLI, urut baris sheet, siap ditempel.",
        "isian": [
            isian("berkas", "berkas", "Sheet input usaha", "@posisi", wajib=True, filter=XLSX),
            isian("lembar", "lembar", "Nama sheet (tab)", "--lembar", dari_berkas="berkas",
                  bantuan="Kosong = sheet yang aktif saat berkas terakhir disimpan."),
            isian("model", "pilihan", "Model", "--model",
                  opsi=[["", "besar (paling akurat, ±17 mnt / 1.800 baris)"], ["sedang", "sedang (±2 mnt)"],
                        ["kecil", "kecil (<1 mnt)"], ["tanpa", "tanpa model (kamus saja)"]]),
            isian("maks_baris", "angka", "Batasi jumlah baris (uji coba)", "--maks-baris"),
            isian("abaikan_kode_isian", "centang", "Abaikan kode KBLI yang ditulis petugas di isian",
                  "--abaikan-kode-isian"),
            isian("jumlah_alternatif", "angka", "Jumlah kandidat cadangan", "--jumlah-alternatif", lanjutan=True,
                  contoh="2"),
            isian("sertakan_isian", "centang", "Salin teks 8b/13a/13f ke hasil (utk memeriksa)", "--sertakan-isian",
                  lanjutan=True),
            isian("tanpa_penyesuaian", "centang", "Matikan tebakan kategori, grosir/eceran & syarat judul",
                  "--tanpa-penyesuaian", lanjutan=True),
            isian("kol_13a", "teks", "Kolom 13a (huruf)", "--kol-13a", lanjutan=True, pola=POLA_KOLOM,
                  bantuan="Kosong = dideteksi dari judul kolom."),
            isian("kol_13f", "teks", "Kolom 13f (huruf)", "--kol-13f", lanjutan=True, pola=POLA_KOLOM),
            isian("baris_awal", "angka", "Baris data pertama", "--baris-awal", lanjutan=True),
            isian("keluaran", "simpan", "Simpan hasil ke", "-o", lanjutan=True, filter=XLSX, ekstensi=".xlsx",
                  bantuan="Kosong = gui/hasil/kbli/<nama sheet>_kbli.xlsx."),
        ],
        "aksi": [aksi("jalan", "Generate KBLI")],
        "keluaran": [
            keluaran("Salin Kode + Judul KBLI", "gui/hasil/kbli/{stem:berkas}_kbli.xlsx", jenis="kbli",
                     isian_="keluaran"),
            keluaran("Buka hasil", "gui/hasil/kbli/{stem:berkas}_kbli.xlsx", isian_="keluaran"),
        ],
    },
]

ALAT_PER_ID = {a["id"]: a for a in ALAT}

# Pola prompt konfirmasi yang dicetak skrip lewat input(): mesin.py (Kirim), approve_pml.py (Approve),
# ubah_moda.py (Ganti Mode). GUI membuka dialog 'ketik YA' begitu baris terakhir output cocok.
POLA_PROMPT_YA = re.compile(r"Ketik\s+'YA'", re.IGNORECASE)


class IsianSalah(ValueError):
    """Isian formulir tidak valid; pesannya ditampilkan apa adanya di GUI."""


def _kosong(v) -> bool:
    return v is None or v is False or (isinstance(v, str) and not v.strip()) or v == []


def _daftar(v) -> list[str]:
    """Nilai 'banyak' -> list teks. Terima list, atau teks dipisah baris / koma / titik koma."""
    if isinstance(v, list):
        hasil = [str(x).strip() for x in v]
    else:
        hasil = [x.strip() for x in re.split(r"[\n;,]", str(v or ""))]
    return [x for x in hasil if x]


def _norm(v) -> str:
    """Nilai utk dibandingkan syarat: centang -> "1"/"0", kosong -> ""."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, dict):                        # centang_nilai
        return "1" if v.get("aktif") else "0"
    return "" if v is None else str(v)


def _cocok(syarat: dict | None, nilai: dict, isian_alat: list[dict]) -> bool:
    """tampil_jika / wajib_jika: {nama_isian: [nilai yang memenuhi]}; kunci "@aksi" =
    aksi yang sedang dijalankan. Centang dibandingkan sbg "1"/"0"."""
    if not syarat:
        return True
    bawaan = {i["nama"]: i.get("bawaan", False if i["jenis"] == "centang" else "") for i in isian_alat}
    for nama, boleh in syarat.items():
        v = nilai.get(nama, bawaan.get(nama, ""))
        if _norm(v) not in [_norm(b) for b in boleh]:
            return False
    return True


def isian_aktif(alat: dict, aksi_id: str, nilai: dict) -> list[dict]:
    """Isian yang tampil & diteruskan utk aksi ini."""
    return [i for i in alat["isian"]
            if (not i.get("aksi") or aksi_id in i["aksi"]) and _cocok(i.get("tampil_jika"), nilai, alat["isian"])]


def nilai_isian(i: dict, nilai: dict):
    v = nilai.get(i["nama"])
    if v is None:
        v = i.get("bawaan", "")
    return v


def butuh_password(alat: dict, aksi_: dict, nilai: dict) -> bool:
    p = aksi_.get("password")
    if isinstance(p, str) and p.startswith("kecuali:"):
        return _kosong(nilai.get(p.split(":", 1)[1]))
    return bool(p)


def cari_aksi(alat: dict, aksi_id: str) -> dict:
    for a in alat["aksi"]:
        if a["id"] == aksi_id:
            return a
    raise IsianSalah(f"Aksi '{aksi_id}' tidak dikenal utk {alat['judul']}.")


def susun_argumen(alat: dict, aksi_id: str, nilai: dict, efektif=lambda nama: "") -> list[str]:
    """Isian formulir -> daftar argumen CLI (tanpa python & skrip). `efektif(nama_config)`
    mengembalikan nilai pengaturan yang berlaku (utk isian ber-`pengaturan` yang dikosongkan).
    Melempar IsianSalah berisi SEMUA masalah sekaligus."""
    aksi_ = cari_aksi(alat, aksi_id)
    masalah: list[str] = []
    posisi: list[str] = []
    argumen: list[str] = []
    syarat_nilai = {**nilai, "@aksi": aksi_id}
    for i in isian_aktif(alat, aksi_id, nilai):
        v = nilai_isian(i, nilai)
        jenis, arg, label = i["jenis"], i.get("arg"), i["label"]
        wajib = bool(i.get("wajib") or (i.get("wajib_jika") and _cocok(i["wajib_jika"], syarat_nilai, alat["isian"])))
        if jenis in ("centang",):
            if v is True or v == "true":
                argumen.append(arg)
            continue
        if jenis == "centang_nilai":
            if isinstance(v, dict):
                aktif, isi = bool(v.get("aktif")), str(v.get("nilai") or "").strip()
            else:
                aktif, isi = bool(v), ""
            if aktif:
                argumen += [arg, isi] if isi else [arg]
            continue
        if jenis == "pilihan" and arg is None:
            argumen += i.get("arg_nilai", {}).get(str(v), [])
            continue
        if jenis in ("berkas_banyak", "lokasi_banyak", "teks_banyak"):
            daftar = _daftar(v)
            if not daftar and wajib:
                masalah.append(f"{label}: wajib diisi.")
            for x in daftar:
                argumen += [arg, x]
            continue
        teks = "" if _kosong(v) else str(v).strip()
        if not teks and i.get("pengaturan"):
            bawaan_cfg = str(efektif(i["pengaturan"]) or "").strip()
            if bawaan_cfg and not wajib:
                continue                   # skrip memakai config (yang sudah ditimpa pengaturan GUI)
            teks = bawaan_cfg              # wajib -> teruskan nilai pengaturan (kosong -> ditolak di bawah)
        if not teks:
            if wajib:
                masalah.append(f"{label}: wajib diisi.")
            continue
        pola = i.get("pola") or {"email": POLA_EMAIL, "subsls": POLA_SUBSLS}.get(jenis)
        if jenis == "angka" and not re.fullmatch(r"\d+", teks):
            masalah.append(f"{label}: harus bilangan bulat ≥ 0 (dapat '{teks}').")
            continue
        if jenis == "desimal" and not re.fullmatch(r"\d+([.,]\d+)?", teks):
            masalah.append(f"{label}: harus angka (dapat '{teks}').")
            continue
        if jenis == "desimal":
            teks = teks.replace(",", ".")
        if pola and not re.fullmatch(pola, teks):
            masalah.append(f"{label}: format tidak sesuai (dapat '{teks}').")
            continue
        if jenis == "pilihan":
            boleh = [str(o[0]) for o in i.get("opsi", [])]
            if teks not in boleh:
                masalah.append(f"{label}: pilihan '{teks}' tidak dikenal.")
                continue
        if arg == "@posisi":
            posisi.append(teks)
        else:
            argumen += [arg, teks]
    if masalah:
        raise IsianSalah("\n".join(masalah))
    return posisi + argumen + list(aksi_.get("tambah") or [])


def path_keluaran(k: dict, nilai: dict, akar: Path) -> Path:
    """Path keluaran sebuah tombol hasil: isian pengganti (kalau diisi) atau path bawaan."""
    ganti = str(nilai.get(k.get("isian") or "", "") or "").strip()
    if ganti:
        p = Path(ganti)
    else:
        def stem(m):
            return Path(str(nilai.get(m.group(1), "") or "x")).stem
        p = Path(re.sub(r"\{stem:(\w+)\}", stem, k["path"]))
    return p if p.is_absolute() else akar / p


def untuk_gui() -> dict:
    """Data alat yang dikirim ke halaman (semuanya bisa di-JSON-kan)."""
    return {"grup": GRUP, "alat": ALAT}
