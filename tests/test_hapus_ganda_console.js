// Uji logika murni hapus_ganda_console.js — offline (Node).
// Jalankan: node tests/test_hapus_ganda_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "hapus_ganda", "hapus_ganda_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}
function melempar(label, fn, kode) {
  let dapat = null;
  try { fn(); } catch (e) { dapat = e.kode || e.message; }
  check(label, dapat, kode);
}

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";
const C = "33333333-3333-4333-8333-333333333333";

check("template: TARGET kosong & penanda", [m.TARGET, m.SURVEI, m.PERIODE], [[], "", ""]);
check("halaman Data (query diabaikan pemanggil)",
  m.halamanData("/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data"),
  { survei: "a0429e96-51a5-477b-a415-485f9c153004", periode: "fd68e454-ba45-4b85-8205-f3bf777ded24" });
check("bukan halaman Data", m.halamanData("/app/surveys"), null);
check("peringkat status", ["APPROVED BY Pengawas", "SUBMITTED BY Pencacah", "REJECTED BY Pengawas", "DRAFT", "OPEN", ""].map(m.peringkatStatus),
  [4, 3, 2, 1, 1, 0]);
check("nama dari kode identitas", m.namaDariKode("5108060006000224 -  Warung  Beras (Made)"), "WARUNG BERAS (MADE)");

// --- detail ---
const det = (alias, kode = "5108060006000224 - WARUNG (MADE)", extra = {}) =>
  m.nilaiDetail({ status: 200, j: { success: true, data: { assignment_status_alias: alias, code_identity: kode, ...extra } } });
check("detail terbaca", (({ ada, alias, nama, kode }) => ({ ada, alias, nama, kode }))(det("DRAFT")),
  { ada: true, alias: "DRAFT", nama: "WARUNG (MADE)", kode: "5108060006000224" });
check("detail success false -> tidak ada", m.nilaiDetail({ status: 200, j: { success: false, message: "Data tidak ditemukan" } }).ada, false);
check("detail 404 bukan JSON -> tidak ada + pesan", m.nilaiDetail({ status: 404, j: null, teks: "Not Found" }).pesan, "HTTP 404 Not Found");

// --- putuskanGrup (kasus kembar dgn gabung_audit.usulan_grup, lihat tests/test_gabung_audit.py) ---
// Ketetapan user 2026-09-24: SUBMITTED+DRAFT -> DRAFT dihapus; SUBMITTED+SUBMITTED -> salah satu;
// DRAFT+DRAFT -> yang ber-galat, keduanya bersih -> salah satu.
const dk = (id, alias, o = {}) => ({ id, ada: true, alias, nama: "WARUNG (MADE)", galat: 0, bersih: 80, c: false, l: false, x: false, ...o });
const kep = (dok, opsi) => m.putuskanGrup(dok, opsi).map((x) => x.keputusan);
check("SUBMITTED + DRAFT -> DRAFT dihapus", kep([dk(A, "DRAFT"), dk(B, "SUBMITTED BY Pencacah")]), ["HAPUS", "PERTAHANKAN"]);
check("SUBMITTED + SUBMITTED -> salah satu dihapus (yang ditunjuk audit dipertahankan)",
  kep([dk(A, "SUBMITTED BY Pencacah", { c: true }), dk(B, "SUBMITTED BY Pencacah")]), ["PERTAHANKAN", "HAPUS"]);
check("SUBMITTED + SUBMITTED, galat tidak terbaca -> tetap salah satu dihapus",
  kep([dk(A, "SUBMITTED BY Pencacah", { galat: null }), dk(B, "SUBMITTED BY Pencacah", { galat: null, c: true })]), ["HAPUS", "PERTAHANKAN"]);
check("SUBMITTED dimatikan dgn izinkanHapusTerkirim: false",
  kep([dk(A, "SUBMITTED BY Pencacah", { c: true }), dk(B, "SUBMITTED BY Pencacah")], { izinkanHapusTerkirim: false }), ["PERTAHANKAN", "PERIKSA"]);
check("DRAFT + DRAFT: yang ber-galat dihapus walau ditunjuk audit",
  kep([dk(A, "DRAFT", { galat: 3, c: true }), dk(B, "DRAFT", { galat: 0 })]), ["HAPUS", "PERTAHANKAN"]);
check("DRAFT + DRAFT keduanya bersih -> yang ditunjuk audit dipertahankan",
  kep([dk(A, "DRAFT"), dk(B, "DRAFT", { c: true })]), ["HAPUS", "PERTAHANKAN"]);
check("DRAFT + DRAFT keduanya bersih, tanpa penunjuk -> jawaban lebih lengkap dipertahankan",
  kep([dk(A, "DRAFT", { bersih: 20 }), dk(B, "DRAFT", { bersih: 91 })]), ["HAPUS", "PERTAHANKAN"]);
check("DRAFT + DRAFT keduanya ber-galat -> galat lebih banyak dihapus",
  kep([dk(A, "DRAFT", { galat: 1 }), dk(B, "DRAFT", { galat: 5, c: true })]), ["PERTAHANKAN", "HAPUS"]);
check("DRAFT + DRAFT galat tidak terbaca -> PERIKSA",
  kep([dk(A, "DRAFT", { galat: null, c: true }), dk(B, "DRAFT", { galat: 2 })]), ["PERTAHANKAN", "PERIKSA"]);
check("APPROVED tidak pernah dihapus",
  kep([dk(A, "APPROVED BY Pengawas"), dk(B, "APPROVED BY Pengawas")]), ["PERTAHANKAN", "PERIKSA"]);
check("APPROVED + SUBMITTED -> SUBMITTED dihapus", kep([dk(A, "SUBMITTED BY Pencacah", { c: true }), dk(B, "APPROVED BY Pengawas")]),
  ["HAPUS", "PERTAHANKAN"]);
check("status tertinggi menang atas penunjuk audit",
  kep([dk(A, "DRAFT", { c: true }), dk(B, "SUBMITTED BY Pencacah", { galat: 2 })]), ["HAPUS", "PERTAHANKAN"]);
check("di luar audit -> PERIKSA tanpa izin", kep([dk(A, "SUBMITTED BY Pencacah"), dk(B, "DRAFT", { l: true })]), ["PERTAHANKAN", "PERIKSA"]);
check("di luar audit + izinkanLuarAudit -> HAPUS",
  kep([dk(A, "SUBMITTED BY Pencacah"), dk(B, "DRAFT", { l: true })], { izinkanLuarAudit: true }), ["PERTAHANKAN", "HAPUS"]);
check("URL diklaim baris lain -> PERIKSA", kep([dk(A, "SUBMITTED BY Pencacah"), dk(B, "DRAFT", { x: true })]), ["PERTAHANKAN", "PERIKSA"]);
check("nama beda -> PERIKSA", kep([dk(A, "SUBMITTED BY Pencacah"), dk(B, "DRAFT", { nama: "TOKO LAIN (X)" })]), ["PERTAHANKAN", "PERIKSA"]);
check("tiga dokumen: 2 DRAFT dihapus, SUBMITTED dipertahankan",
  kep([dk(A, "DRAFT"), dk(B, "SUBMITTED BY Pencacah"), dk(C, "DRAFT")]), ["HAPUS", "PERTAHANKAN", "HAPUS"]);
check("satu tidak terbaca -> sisanya tidak dihapus",
  kep([dk(A, "DRAFT", { ada: false }), dk(B, "SUBMITTED BY Pencacah")]), ["TIDAK_TERBACA", "PERTAHANKAN"]);
check("galat & jawaban bersih dari detail/tabel", [m.angkaDari({ sumError: 3 }, /^sum_?error$/i),
  m.angkaDari({ sum_clean: "88" }, /^sum_?clean$/i), m.angkaDari({}, /^sum_?error$/i)], [3, 88, null]);

// --- filter PAPI ---
check("mode dari list API (array)", m.modeDari({ mode: ["PAPI"] }), "PAPI");
check("mode dari field lain (string)", m.modeDari({ assignment_mode: "capi" }), "CAPI");
check("mode tidak ada", m.modeDari({ code_identity: "x" }), "");
check("detail membawa mode", m.nilaiDetail({ status: 200, j: { success: true, data: { assignment_status_alias: "DRAFT",
  code_identity: "5108060006000224 - W (M)", mode: ["PAPI"] } } }).mode, "PAPI");
const P = { hanyaPapi: true };
check("hanyaPapi: DRAFT PAPI vs SUBMITTED PAPI -> hapus",
  kep([dk(A, "DRAFT", { mode: "PAPI" }), dk(B, "SUBMITTED BY Pencacah", { mode: "PAPI" })], P), ["HAPUS", "PERTAHANKAN"]);
check("hanyaPapi: dokumen CAPI tidak disentuh & tidak jadi pembanding",
  kep([dk(A, "DRAFT", { mode: "PAPI" }), dk(B, "SUBMITTED BY Pencacah", { mode: "CAPI" })], P), ["PERTAHANKAN", "BUKAN_PAPI"]);
check("hanyaPapi: mode tidak terbaca -> BUKAN_PAPI",
  kep([dk(A, "DRAFT", { mode: "" }), dk(B, "SUBMITTED BY Pencacah", { mode: "PAPI" })], P), ["BUKAN_PAPI", "PERTAHANKAN"]);
check("tanpa hanyaPapi: mode diabaikan",
  kep([dk(A, "DRAFT", { mode: "CAPI" }), dk(B, "SUBMITTED BY Pencacah", { mode: "PAPI" })]), ["HAPUS", "PERTAHANKAN"]);

// --- pola request ---
const req = { method: "DELETE", url: `https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignment/${A}`, body: null };
check("pola dari request DELETE", m.templateDari(req, A, [B]),
  { method: "DELETE", url: "/app/api/assignment-general/api/assignment/{{ID}}", body: null, contentType: "" });
check("pola bulk di body", m.templateDari({ method: "POST", url: "/app/api/x/delete-bulk", body: `{"assignmentIds":["${A}"]}`,
  contentType: "application/json" }, A, [B]).body, '{"assignmentIds":["{{ID}}"]}');
melempar("pola memuat id yang dipertahankan -> ditolak",
  () => m.templateDari({ method: "POST", url: "/app/api/x", body: `["${A}","${B}"]` }, A, [B]), "POLA_DITOLAK");
melempar("GET bukan penghapusan", () => m.templateDari({ method: "GET", url: `/app/api/x/${A}` }, A, []), "POLA_DITOLAK");
melempar("domain lain ditolak", () => m.templateDari({ method: "DELETE", url: `https://contoh.com/app/api/x/${A}` }, A, []), "POLA_DITOLAK");
melempar("id tidak ada di request", () => m.templateDari({ method: "DELETE", url: "/app/api/x/1" }, A, []), "POLA_DITOLAK");
check("isi pola", m.isiTemplate({ method: "DELETE", url: "/app/api/x/{{ID}}", body: null }, C).url, `/app/api/x/${C}`);
melempar("isi pola dgn id tidak sah", () => m.isiTemplate({ method: "DELETE", url: "/app/api/x/{{ID}}" }, "abc"), "POLA_DITOLAK");

const salinan = `fetch("https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignment/delete", {
  "headers": { "accept": "application/json", "content-type": "application/json", "x-xsrf-token": "t" },
  "referrer": "https://fasih-sm.bps.go.id/app/surveys/x/y/data",
  "body": "{\\"id\\":\\"${A}\\"}",
  "method": "POST",
  "mode": "cors",
  "credentials": "include"
});`;
check("urai 'Copy as fetch'", m.uraiCopyAsFetch(salinan), {
  method: "POST", url: "https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignment/delete",
  body: `{"id":"${A}"}`, contentType: "application/json" });
melempar("bukan 'Copy as fetch'", () => m.uraiCopyAsFetch("curl https://x"), "POLA_DITOLAK");

// --- bukti terhapus ---
const hilang = m.nilaiDetail({ status: 200, j: { success: false, message: "tidak ditemukan" } });
check("detail hilang -> sidik HILANG", m.sidikTerhapus(det("DRAFT"), hilang).cara, "HILANG");
check("field is_deleted berubah -> sidik FIELD",
  m.sidikTerhapus(det("DRAFT", undefined, { is_deleted: false }), det("DRAFT", undefined, { is_deleted: true })),
  { cara: "FIELD", kunci: "is_deleted", nilai: true });
check("tidak ada perubahan -> tidak terbukti", m.sidikTerhapus(det("DRAFT"), det("DRAFT")), null);
check("cocok HILANG", [m.cocokTerhapus({ cara: "HILANG" }, hilang), m.cocokTerhapus({ cara: "HILANG" }, det("DRAFT"))], [true, false]);
check("cocok FIELD", m.cocokTerhapus({ cara: "FIELD", kunci: "is_deleted", nilai: true }, det("DRAFT", undefined, { is_deleted: true })), true);
check("id dalam teks", m.idDalam(`/x/${A.toUpperCase()}?y=${C}`, [A, B]), [A]);

check("limit pertama wajib 1", [m.limitDiizinkan(1, false), m.limitDiizinkan(Infinity, false), m.limitDiizinkan(50, true)], [true, false, true]);

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
