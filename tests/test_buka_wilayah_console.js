// Uji logika murni buka_wilayah_console.js — offline (Node).
// Jalankan: node tests/test_buka_wilayah_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "buka_wilayah", "buka_wilayah_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

check("template: TARGET kosong", m.TARGET, []);

// --- periode dari URL halaman Data (URL asli 2026-09-15) ---
check("periode dari path Data",
  m.periodeDariPath("/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data"),
  "fd68e454-ba45-4b85-8205-f3bf777ded24");
check("bukan halaman Data -> null", m.periodeDariPath("/app/surveys"), null);

// --- item wilayah: bentuk PERSIS respons datatable asli (region dipangkas) ---
const K = "5108010001000203";
const item = (o) => ({ id: "8af509f5-c269-4325-81b2-478f5aa65845", surveyPeriodId: "fd68e454-ba45-4b85-8205-f3bf777ded24",
  smallestRegionFullCode: K, region: {}, regionId: "b06deec5-6095-4bda-a047-b4cef50d2989",
  regionGroupId: "a45adac1-e711-4c15-b3f9-1f30fc151565", doneListing: false, doneTarikSample: false, ...o });

check("kode tidak valid", m.rencanakan("51080100010002", []).status, "KODE_TIDAK_VALID");
check("data bukan array", m.rencanakan(K, null).status, "RESPONS_TIDAK_DIKENAL");
check("tidak ada hasil", m.rencanakan(K, []).status, "WILAYAH_TIDAK_ADA");
check("hanya kode MIRIP (regex search) -> tidak ada",
  m.rencanakan(K, [item({ smallestRegionFullCode: "5108010001000204" })]).status, "WILAYAH_TIDAK_ADA");
check("dua wilayah kode sama -> ganda", m.rencanakan(K, [item({}), item({})]).status, "WILAYAH_GANDA");
check("Proses Listing -> sudah terbuka (tidak disentuh)", m.rencanakan(K, [item({ doneListing: false })]).status, "SUDAH_TERBUKA");
const r = m.rencanakan(K, [item({ smallestRegionFullCode: "5108010001000204" }), item({ doneListing: true })]);
check("Listing Selesai -> perlu dibuka, item persis yang cocok",
  [r.status, r.item && r.item.smallestRegionFullCode, r.item && r.item.id], ["PERLU_DIBUKA", K, "8af509f5-c269-4325-81b2-478f5aa65845"]);
check("sudah tarik sampel -> dilewati default",
  m.rencanakan(K, [item({ doneListing: true, doneTarikSample: true })]).status, "SUDAH_TARIK_SAMPEL");
check("sudah tarik sampel + izinkanTarikSampel -> perlu dibuka",
  m.rencanakan(K, [item({ doneListing: true, doneTarikSample: true })], { izinkanTarikSampel: true }).status, "PERLU_DIBUKA");
check("doneListing bukan boolean -> berhenti",
  m.rencanakan(K, [item({ doneListing: "true" })]).status, "RESPONS_TIDAK_DIKENAL");
check("tanpa id -> berhenti", m.rencanakan(K, [item({ doneListing: true, id: "" })]).status, "RESPONS_TIDAK_DIKENAL");

// --- respons endpoint undone ---
check("success true", m.nilaiRespons(200, '{"success":true,"message":"ok"}').status, "OK");
check("success false", m.nilaiRespons(200, '{"success":false,"message":"tidak boleh"}').status, "GAGAL_BUKA");
check("403 CSRF (teks asli)", m.nilaiRespons(403, "Invalid CSRF Token").status, "SESI_DITOLAK");
check("bukan JSON", m.nilaiRespons(200, "<html>").status, "RESPONS_TIDAK_DIKENAL");
check("200 tanpa field success", m.nilaiRespons(200, '{"data":1}').status, "RESPONS_TIDAK_DIKENAL");
check("500 dgn success false", m.nilaiRespons(500, '{"success":false,"message":"x"}').status, "GAGAL_BUKA");
check("status berhenti mencakup sesi & verifikasi",
  ["SESI_DITOLAK", "DIBUKA_BELUM_TERVERIFIKASI", "RESPONS_TIDAK_DIKENAL"].every((s) => m.STATUS_BERHENTI_SEGERA.has(s)), true);

// --- penyaringan target ---
const T = ["5108010001000203", "5108010001000302", "5108010001000303"].map((idsubsls) => ({ idsubsls }));
const seb = {
  "5108010001000203": { jalan: "eksekusi", status: "DIBUKA_TERVERIFIKASI" },
  "5108010001000302": { jalan: "cek", status: "SUDAH_TERBUKA" },
};
const ids = (d) => d.map((t) => t.idsubsls);
check("eksekusi melewati yg tuntas oleh eksekusi saja",
  ids(m.saringTarget(T, seb, { mode: "eksekusi", lewatiSelesai: true })), ["5108010001000302", "5108010001000303"]);
check("cek tidak melewati apa pun", ids(m.saringTarget(T, seb, { mode: "cek", lewatiSelesai: true })).length, 3);
check("limit & idsubsls",
  ids(m.saringTarget(T, {}, { mode: "eksekusi", lewatiSelesai: true, idsubsls: ["5108010001000303", "5108010001000302"], limit: 1 })),
  ["5108010001000302"]);

// --- pindai massal: hanya bukti positif "sudah terbuka" yang dilewati ---
const peta = {
  "5108010001000203": { doneListing: false, doneTarikSample: false },  // Proses Listing
  "5108010001000302": { doneListing: true, doneTarikSample: false },   // Listing Selesai
  "5108010001000303": { doneListing: null },                            // nilai aneh
};
const T4 = [...T, { idsubsls: "5108090010000503" }];                    // tidak terbaca di pindai
const bagi = m.bagiDariPindai(T4, peta);
check("pindai: yang terbuka dilewati", ids(bagi.lewati), ["5108010001000203"]);
check("pindai: selesai/aneh/tidak terbaca tetap diproses satu per satu",
  ids(bagi.proses), ["5108010001000302", "5108010001000303", "5108090010000503"]);
check("pindai gagal (peta kosong) -> semua diproses", m.bagiDariPindai(T, null).proses.length, 3);

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
