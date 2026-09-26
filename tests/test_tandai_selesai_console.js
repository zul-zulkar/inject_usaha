// Uji logika murni tandai_selesai_console.js — offline (Node).
// Jalankan: node tests/test_tandai_selesai_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "fasih_sm", "tandai_selesai", "tandai_selesai_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

check("template: TARGET kosong", m.TARGET, []);
check("template: cakupan default daftar", m.CAKUPAN, "daftar");

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
check("Listing Selesai -> sudah selesai (tidak disentuh)", m.rencanakan(K, [item({ doneListing: true })]).status, "SUDAH_SELESAI");
const r = m.rencanakan(K, [item({ smallestRegionFullCode: "5108010001000204", doneListing: false }), item({ doneListing: false })]);
check("Proses Listing -> perlu ditandai, item persis yang cocok",
  [r.status, r.item && r.item.smallestRegionFullCode, r.item && r.item.id], ["PERLU_DITANDAI", K, "8af509f5-c269-4325-81b2-478f5aa65845"]);
check("sudah tarik sampel tapi Proses Listing -> tetap perlu ditandai",
  m.rencanakan(K, [item({ doneListing: false, doneTarikSample: true })]).status, "PERLU_DITANDAI");
check("doneListing bukan boolean -> berhenti", m.rencanakan(K, [item({ doneListing: "false" })]).status, "RESPONS_TIDAK_DIKENAL");
check("tanpa id -> berhenti", m.rencanakan(K, [item({ id: "" })]).status, "RESPONS_TIDAK_DIKENAL");

// --- respons endpoint done ---
check("success true", m.nilaiRespons(200, '{"success":true,"message":"ok"}').status, "OK");
check("success false", m.nilaiRespons(200, '{"success":false,"message":"tidak boleh"}').status, "GAGAL_TANDAI");
check("403 CSRF (teks asli)", m.nilaiRespons(403, "Invalid CSRF Token").status, "SESI_DITOLAK");
check("bukan JSON", m.nilaiRespons(200, "<html>").status, "RESPONS_TIDAK_DIKENAL");
check("200 tanpa field success", m.nilaiRespons(200, '{"data":1}').status, "RESPONS_TIDAK_DIKENAL");
check("500 dgn success false", m.nilaiRespons(500, '{"success":false,"message":"x"}').status, "GAGAL_TANDAI");
check("429 rate limit -> server sibuk (bukan dikirim ulang buta)",
  m.nilaiRespons(429, '{"error":"RATE_LIMIT_EXCEEDED"}').status, "SERVER_SIBUK");
check("504 HTML -> server sibuk", m.nilaiRespons(504, "<html>504 Gateway Time-out</html>").status, "SERVER_SIBUK");
check("jaringan putus (0) -> server sibuk", m.nilaiRespons(0, "Failed to fetch").status, "SERVER_SIBUK");
check("teks asli 'tidak memiliki akses' (run user 2026-09-15) -> TIDAK_ADA_AKSES",
  m.nilaiRespons(200, '{"success":false,"message":"Anda tidak memiliki akses ke dalam survey"}').status, "TIDAK_ADA_AKSES");
check("tanpa akses dihitung gagal selama belum ada bukti akun bisa menandai",
  [m.dihitungGagal("TIDAK_ADA_AKSES", false), m.dihitungGagal("TIDAK_ADA_AKSES", true)], [true, false]);
check("status lain dihitung gagal apa pun buktinya",
  ["GAGAL_TANDAI", "SERVER_SIBUK", "ERROR_TAK_TERDUGA", "DITANDAI_TERVERIFIKASI", "SUDAH_SELESAI", "WILAYAH_TIDAK_ADA"]
    .map((s) => m.dihitungGagal(s, true)), [true, true, true, false, false, false]);
// --- balasan datatable (teks asli run user 2026-09-15 saat server lambat) ---
const kosongGagal = JSON.parse('{"draw":0,"recordsTotal":0,"recordsFiltered":0,"data":null}');
check("200 data null -> sementara (bukan daftar kosong)", m.nilaiDatatable(200, kosongGagal), "SEMENTARA");
check("504 -> sementara", m.nilaiDatatable(504, null), "SEMENTARA");
check("403 -> sesi", m.nilaiDatatable(403, null), "SESI");
check("200 bukan JSON -> aneh", m.nilaiDatatable(200, null), "ANEH");
check("200 data bukan array -> aneh", m.nilaiDatatable(200, { data: "x" }), "ANEH");
check("pencarian kosong [] sah (kode memang tidak ada)", m.nilaiDatatable(200, { recordsTotal: 0, data: [] }), "OK");
check("pindai (wajibIsi) recordsTotal 0 -> sementara",
  m.nilaiDatatable(200, { recordsTotal: 0, data: [] }, { wajibIsi: true }), "SEMENTARA");
check("pindai normal -> ok", m.nilaiDatatable(200, { recordsTotal: 2614, data: [{}] }, { wajibIsi: true }), "OK");
check("halaman pindai diperkecil 500>250>125>62>50>berhenti",
  [500, 250, 125, 62, 50].map((n) => m.kecilkanHalaman(n)), [250, 125, 62, 50, null]);

// --- langkah pindai: recordsTotal BUKAN batas berhenti (run user 2026-09-19: semua = cuma 500 wilayah) ---
check("halaman penuh, recordsTotal = panjang halaman (500) -> tetap lanjut",
  m.langkahPindai({ jumlahData: 500, panjang: 500, kodeBaru: 500, terkumpul: 500, totalMaks: 500 }), "LANJUT");
check("halaman terakhir tidak penuh -> selesai tanpa minta halaman berikut",
  m.langkahPindai({ jumlahData: 114, panjang: 500, kodeBaru: 114, terkumpul: 2614, totalMaks: 2614 }), "SELESAI");
check("halaman tidak penuh tapi masih kurang dari recordsTotal (server memotong length) -> lanjut",
  m.langkahPindai({ jumlahData: 100, panjang: 500, kodeBaru: 100, terkumpul: 100, totalMaks: 2614 }), "LANJUT");
check("halaman kosong & sudah lengkap -> selesai",
  m.langkahPindai({ jumlahData: 0, panjang: 500, kodeBaru: 0, terkumpul: 2614, totalMaks: 500 }), "SELESAI");
check("halaman kosong padahal kurang dari recordsTotal -> curiga (diulang)",
  m.langkahPindai({ jumlahData: 0, panjang: 500, kodeBaru: 0, terkumpul: 500, totalMaks: 2614 }), "KOSONG_CURIGA");
check("halaman tanpa kode baru -> macet (cegah loop)",
  m.langkahPindai({ jumlahData: 500, panjang: 500, kodeBaru: 0, terkumpul: 500, totalMaks: 500 }), "MACET");
check("galat sementara", [0, 429, 502, 503, 504, 500, 400, 200].map(m.jenisSementara),
  [true, true, true, true, true, false, false, false]);
check("status berhenti mencakup sesi, verifikasi & sibuk terus",
  ["SESI_DITOLAK", "DITANDAI_BELUM_TERVERIFIKASI", "RESPONS_TIDAK_DIKENAL", "SERVER_SIBUK_TERUS"]
    .every((s) => m.STATUS_BERHENTI_SEGERA.has(s)), true);
check("SERVER_SIBUK per wilayah tidak menghentikan seketika", m.STATUS_BERHENTI_SEGERA.has("SERVER_SIBUK"), false);

// --- penyaringan target ---
const T = ["5108010001000203", "5108010001000302", "5108010001000303"].map((idsubsls) => ({ idsubsls }));
const seb = {
  "5108010001000203": { jalan: "eksekusi", status: "DITANDAI_TERVERIFIKASI" },
  "5108010001000302": { jalan: "cek", status: "SUDAH_SELESAI" },
};
const ids = (d) => d.map((t) => t.idsubsls);
check("eksekusi melewati yg tuntas oleh eksekusi saja",
  ids(m.saringTarget(T, seb, { mode: "eksekusi", lewatiSelesai: true })), ["5108010001000302", "5108010001000303"]);
check("lewatiSelesai false (pindai berhasil) -> hasil lama diabaikan",
  ids(m.saringTarget(T, seb, { mode: "eksekusi", lewatiSelesai: false })).length, 3);
check("cek tidak melewati apa pun", ids(m.saringTarget(T, seb, { mode: "cek", lewatiSelesai: true })).length, 3);
check("limit & idsubsls",
  ids(m.saringTarget(T, {}, { mode: "eksekusi", lewatiSelesai: true, idsubsls: ["5108010001000303", "5108010001000302"], limit: 1 })),
  ["5108010001000302"]);
check("kecuali", ids(m.saringTarget(T, {}, { mode: "eksekusi", kecuali: ["5108010001000302"] })),
  ["5108010001000203", "5108010001000303"]);

// --- pindai massal: hanya bukti positif "sudah selesai" yang dilewati ---
const peta = {
  "5108010001000203": { doneListing: true, doneTarikSample: false },   // Listing Selesai
  "5108010001000302": { doneListing: false, doneTarikSample: false },  // Proses Listing
  "5108010001000303": { doneListing: null },                            // nilai aneh
};
const T4 = [...T, { idsubsls: "5108090010000503" }];                    // tidak terbaca di pindai
const bagi = m.bagiDariPindai(T4, peta);
check("pindai: yang sudah selesai dilewati", ids(bagi.lewati), ["5108010001000203"]);
check("pindai: proses/aneh/tidak terbaca tetap diproses satu per satu",
  ids(bagi.proses), ["5108010001000302", "5108010001000303", "5108090010000503"]);
check("pindai gagal (peta kosong) -> semua diproses", m.bagiDariPindai(T, null).proses.length, 3);

// --- cakupan SEMUA: target dari peta pindai ---
const tp = m.targetDariPindai({ ...peta, "5108": { doneListing: false }, "5108010001000100": { doneListing: false } });
check("semua: kode valid urut", ids(tp.target),
  ["5108010001000100", "5108010001000203", "5108010001000302", "5108010001000303"]);
check("semua: kode di luar pola dilaporkan, tidak diproses", tp.tidakValid, ["5108"]);
check("semua: peta null -> kosong", m.targetDariPindai(null), { target: [], tidakValid: [], slsNol: [] });
// Run live 2026-09-15: 5108020009000000 ditolak "tidak memiliki akses", 5108060001000106 berhasil.
const petaNol = { "5108020009000000": { doneListing: false }, "5108020009000101": { doneListing: true },
  "5108060001000106": { doneListing: false }, "5108060001000100": { doneListing: false } };
const tpNol = m.targetDariPindai(petaNol);
check("semua: kode SLS nol dikeluarkan default", [ids(tpNol.target), tpNol.slsNol],
  [["5108020009000101", "5108060001000100", "5108060001000106"], ["5108020009000000"]]);
check("semua: sertakanSlsNol -> ikut diproses", ids(m.targetDariPindai(petaNol, { sertakanSlsNol: true }).target).length, 4);
check("hitungan per kecamatan", m.perKecamatan([...T, { idsubsls: "5108090010000503" }]), { 5108010: 3, 5108090: 1 });

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
