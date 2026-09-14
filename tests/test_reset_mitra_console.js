// Uji logika murni reset_mitra_console.js — offline (Node).
// Jalankan: node tests/test_reset_mitra_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "reset_mitra", "reset_mitra_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

check("template: TARGET kosong", m.TARGET, []);
check("normEmail rapikan spasi & huruf", m.normEmail("  Budi.A@Gmail.com "), "budi.a@gmail.com");

const E = "ppl@gmail.com";
const row = (o) => ({ nama: "", username: "", email: "", teks: "", ...o });

check("email kosong", m.pilihMitra("", [row({})]).status, "EMAIL_KOSONG");
check("tidak ada kandidat", m.pilihMitra(E, []).status, "TIDAK_KETEMU");
check("username persis (beda huruf besar) -> COCOK",
  m.pilihMitra(E, [row({ nama: "Budi", username: "PPL@Gmail.com" })]).status, "COCOK");
check("email di kolom -> COCOK",
  m.pilihMitra(E, [row({ nama: "Budi", email: E })]).status, "COCOK");
check("dua mitra username persis -> GANDA",
  m.pilihMitra(E, [row({ username: E }), row({ username: E })]).status, "GANDA");
check("email hanya di teks baris, satu -> COCOK_TEKS",
  m.pilihMitra(E, [row({ nama: "Budi", teks: `Budi ${E} aktif` })]).status, "COCOK_TEKS");
check("email di teks dua baris -> GANDA",
  m.pilihMitra(E, [row({ teks: `a ${E}` }), row({ teks: `b ${E}` })]).status, "GANDA");
check("kandidat ada tapi tak memuat email -> TIDAK_KETEMU",
  m.pilihMitra(E, [row({ nama: "Lain", username: "lain@gmail.com", teks: "Lain" })]).status, "TIDAK_KETEMU");
const p = m.pilihMitra(E, [row({ nama: "Budi", username: E })]);
check("mitra terpilih dikembalikan", p.mitra.nama, "Budi");

check("tombol konfirmasi tunggal ('Reset')", m.pilihTombolKonfirmasi(["Batal", "Reset"]), 1);
check("'Tidak' bukan konfirmasi", m.pilihTombolKonfirmasi(["Tidak", "Ya"]), 1);
check("tanpa konfirmasi", m.pilihTombolKonfirmasi(["Batal", "Tutup"]), null);
check("dua kandidat -> ambigu", m.pilihTombolKonfirmasi(["Reset", "Simpan"]), null);

// --- pilihFieldPassword: dikunci thd dump dialog asli (user 2026-09-14, LUH PUTU
//     SUKMAYANTI): DUA input type=text placeholder "Password"; pembeda = value email ---
const inp = (type, placeholder, value) => ({ type, name: "", placeholder, aria: null, value });
check("dialog asli: field kosong=password (idx0), field ber-@=email (idx1) -> PILIH 0",
  m.pilihFieldPassword([inp("text", "Password", ""), inp("text", "Password", "ptsukma78@gmail.com")]),
  { status: "PILIH", indeks: 0 });
check("email di field pertama -> PILIH field kedua",
  m.pilihFieldPassword([inp("text", "Password", "a@b.com"), inp("text", "Password", "")]),
  { status: "PILIH", indeks: 1 });
check("satu field type=password -> PILIH itu",
  m.pilihFieldPassword([inp("password", "Password Baru", "")]), { status: "PILIH", indeks: 0 });
check("type=email dikecualikan walau value kosong",
  m.pilihFieldPassword([inp("text", "Password", ""), inp("email", "Email", "")]),
  { status: "PILIH", indeks: 0 });
check("belum render (0 input) -> KOSONG (polling ulang)",
  m.pilihFieldPassword([]), { status: "KOSONG", indeks: -1 });
check("hanya field email ter-render -> KOSONG (polling ulang)",
  m.pilihFieldPassword([inp("text", "Password", "x@y.com")]), { status: "KOSONG", indeks: -1 });
check("dua field non-email kosong -> GANDA (jangan tebak)",
  m.pilihFieldPassword([inp("text", "Password", ""), inp("text", "Konfirmasi", "")]),
  { status: "GANDA", indeks: -1 });

// --- putuskanStatus: akun GANDA dilewati (default), bukan menghentikan batch ---
check("GANDA live, default -> LEWATI", m.putuskanStatus("GANDA", { live: true }), "LEWATI");
check("GANDA live, lewatiGanda:false -> BERHENTI (perilaku lama)",
  m.putuskanStatus("GANDA", { live: true, lewatiGanda: false }), "BERHENTI");
check("GANDA mode cocok (tidak live) -> LEWATI", m.putuskanStatus("GANDA", { live: false }), "LEWATI");
check("galat dialog tetap BERHENTI walau lewatiGanda",
  m.putuskanStatus("FIELD_PASSWORD_TIDAK_ADA", { live: true, lewatiGanda: true }), "BERHENTI");
check("DIRESET_BELUM_TERVERIFIKASI tetap BERHENTI",
  m.putuskanStatus("DIRESET_BELUM_TERVERIFIKASI", { live: true }), "BERHENTI");
check("TIDAK_KETEMU live -> LANJUT", m.putuskanStatus("TIDAK_KETEMU", { live: true }), "LANJUT");
check("status berhenti di mode cocok -> LANJUT", m.putuskanStatus("KOTAK_CARI_TIDAK_ADA", { live: false }), "LANJUT");

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
