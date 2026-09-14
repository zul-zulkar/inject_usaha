// Uji logika murni ubah_moda_console.js — offline (Node), tanpa browser/VPN.
// Kasusnya sama dgn tests/test_ubah_moda.py supaya kedua implementasi tidak menyimpang.
// Jalankan: node tests/test_ubah_moda_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "ganti_moda", "ubah_moda_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const S = "5108070013000901";
const PPL = "ppl@gmail.com";
const T = { idsubsls: S, ppl: [PPL] };
const b = (no, mode = "CAPI", petugas = PPL, sub = S, indeks = 0) =>
  ({ kode: `${sub} - UMK - ${no}`, idsubsls: sub, mode, petugas, status: "", keterangan: "", indeks });

check("template: TARGET kosong", m.TARGET, []);

// --- tabel: judul & isi persis seperti terbaca di fasih-sm 2026-09-13 ---
const HEAD = ["", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist", "Nomor Urut Bangunan / IDSBR",
  "NIB / No. KK", "Email", "Skala Usaha / Jenis Prelist", "Jumlah Usaha", "Kode Pos", "Perubahan SLS",
  "IDSBR UMKM SLS Sama", "Status", "Mode", "Petugas Saat Ini", "Keterangan", ""];
const ROW = ["", "5108060003000402 - UMK - 4", "MUJIANTI HARDSTONE", "DSN DHARMAKERTI", "58 / 30300442",
  "2210220006818", "mujiantihardstone468@gmail.com", "UMK / OSS PERORANGAN", "", "81119", "", "",
  "approved by pengawas", "CAPI", "erlinaw26@gmail.com", "Pengawas", ""];
const hasil = m.barisDariTabel({ head: HEAD, rows: [ROW, ["Tidak ada data"]] });
check("parse tabel: 1 baris, baris pesan dilewati", hasil.length, 1);
check("parse kolom lewat judul", [hasil[0].idsubsls, hasil[0].mode, hasil[0].petugas, hasil[0].keterangan],
  ["5108060003000402", "CAPI", "erlinaw26@gmail.com", "Pengawas"]);
try {
  m.barisDariTabel({ head: HEAD.filter((h) => h !== "Mode"), rows: [] });
  check("kolom Mode disembunyikan -> berhenti", "tidak berhenti", "KOLOM_TIDAK_ADA");
} catch (e) {
  check("kolom Mode disembunyikan -> berhenti", e.kode, "KOLOM_TIDAK_ADA");
}

// --- rencanakan (cakupan satu) ---
const LAIN = "5108010009000202";
check("tanpa assignment", m.rencanakan(T, []).status, "TIDAK_ADA_ASSIGNMENT");
check("mode aneh", m.rencanakan(T, [b(1, "CAWI")]).status, "MODE_TIDAK_DIKENAL");
check("sudah ada PAPI milik PPL", m.rencanakan(T, [b(1, "PAPI"), b(2)]).status, "SUDAH_ADA_PAPI");
let r = m.rencanakan(T, [b(1, "CAPI", "lain@gmail.com"), b(2), b(3)]);
check("CAPI milik PPL didahulukan -> pilih tepat satu", [r.status, r.pilih.map((x) => x.kode)], ["PERLU_DIUBAH", [`${S} - UMK - 2`]]);
check("email petugas beda huruf besar tetap cocok",
  m.rencanakan(T, [b(1, "CAPI", "x@gmail.com"), b(2, "CAPI", "PPL@Gmail.com")]).pilih[0].kode, `${S} - UMK - 2`);
// Ketetapan user 2026-09-14: assignment MANA PUN di subsls itu boleh (dulu PETUGAS_BEDA / PAPI_ADA_PETUGAS_LAIN).
check("PAPI milik petugas lain sudah cukup",
  m.rencanakan(T, [b(1, "PAPI", "x@gmail.com"), b(2, "CAPI", "y@gmail.com")]).status, "SUDAH_ADA_PAPI");
r = m.rencanakan(T, [b(1, "CAPI", "x@gmail.com"), b(2, "CAPI", "y@gmail.com")]);
check("CAPI semua milik petugas lain -> tetap pilih satu", [r.status, r.pilih.map((x) => x.kode)],
  ["PERLU_DIUBAH", [`${S} - UMK - 1`]]);

// --- baris subsls lain di hasil pencarian (dryrun 2026-09-14) -> diabaikan, bukan berhenti ---
r = m.rencanakan(T, [b(1, "CAPI", PPL, LAIN), b(2, "CAPI", "x@gmail.com"), b(3, "PAPI", PPL, LAIN)]);
check("subsls lain diabaikan: pilih baris subsls target saja", [r.status, r.pilih.map((x) => x.kode)],
  ["PERLU_DIUBAH", [`${S} - UMK - 2`]]);
check("subsls lain dicatat di pesan", /2 baris subsls lain diabaikan/.test(r.pesan), true);
check("PAPI subsls lain tidak dihitung", m.rencanakan(T, [b(1, "PAPI", PPL, LAIN), b(2)]).status, "PERLU_DIUBAH");
check("hanya subsls lain di halaman -> berhenti (pencarian tidak menyaring)",
  m.rencanakan(T, [b(1, "CAPI", PPL, LAIN)]).status, "SUBSLS_TIDAK_TAMPIL");
check("halaman kosong tapi ada halaman lain -> berhenti", m.rencanakan(T, [], "satu", true).status, "SUBSLS_TIDAK_TAMPIL");

// --- paginasi TIDAK dipindah (temuan user 2026-09-14): hanya halaman tampil yang dibaca ---
r = m.rencanakan(T, [b(1)], "satu", true);
check("ada halaman lain tapi CAPI tampil -> tetap diubah, dicatat",
  [r.status, /hanya halaman tampil/.test(r.pesan)], ["PERLU_DIUBAH", true]);
check("ada halaman lain & PAPI tampil -> sudah cukup", m.rencanakan(T, [b(1), b(2, "PAPI")], "satu", true).status,
  "SUDAH_ADA_PAPI");

// --- rencanakan (cakupan semua) ---
r = m.rencanakan(T, [b(1), b(2, "PAPI"), b(3, "CAPI", "x@gmail.com"), b(4, "CAPI", PPL, LAIN)], "semua");
check("semua: seluruh CAPI subsls ini, PAPI & subsls lain dilewati", [r.status, r.pilih.length], ["PERLU_DIUBAH", 2]);
check("semua: sudah PAPI semua", m.rencanakan(T, [b(1, "PAPI")], "semua").status, "TIDAK_ADA_CAPI");
check("semua: tanpa CAPI tampil tapi ada halaman lain -> berhenti", m.rencanakan(T, [b(1, "PAPI")], "semua", true).status,
  "PERLU_HALAMAN_LAIN");

// --- menu & dialog ---
check("angka item menu (spasi)", m.angkaItemMenu("Ganti Mode (Ke PAPI) (3)"), 3);
check("angka item menu (rapat + baris baru)", m.angkaItemMenu("Ganti Mode (Ke PAPI)\n(0)"), 0);
check("angka item menu tidak ada", m.angkaItemMenu("Ganti Mode (Ke PAPI)"), null);
check("tombol konfirmasi tunggal", m.pilihTombolKonfirmasi(["Batal", "Ya, Ganti Mode"]), 1);
check("tombol 'Tidak' bukan konfirmasi", m.pilihTombolKonfirmasi(["Tidak", "Ya"]), 1);
check("tanpa tombol konfirmasi", m.pilihTombolKonfirmasi(["Batal", "Tutup"]), null);
check("dua kandidat -> ambigu", m.pilihTombolKonfirmasi(["Ya", "Simpan"]), null);

// --- penanda halaman (hanya DIBACA, paginasi tidak pernah diklik) ---
check("baca halaman", m.bacaHalaman("10 row(s) Rows per page 10 Page 1 of 33"), [1, 33]);
check("baca halaman beda baris", m.bacaHalaman("Page 4\nof 4"), [4, 4]);
check("tanpa paginasi", m.bacaHalaman("Tidak ada data"), null);

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
