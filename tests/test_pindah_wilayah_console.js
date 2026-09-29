// Uji logika murni pindah_wilayah_console.js — offline (Node).
// Alur browser lengkap (server palsu): tests/test_pindah_wilayah_simulasi.js
// Jalankan: node tests/test_pindah_wilayah_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "fasih_sm", "pindah_wilayah", "pindah_wilayah_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

check("template: TARGET/SUMBER/ASAL kosong, KONFIG {}", [m.TARGET, m.SUMBER, m.ASAL, m.KONFIG], [[], [], [], {}]);
check("halaman Data",
  m.halamanData("/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data"),
  { survei: "a0429e96-51a5-477b-a415-485f9c153004", periode: "fd68e454-ba45-4b85-8205-f3bf777ded24" });
check("bukan halaman Data", m.halamanData("/app/surveys"), null);
check("norm", m.norm("  pangkalan  gas (Wayan) "), "PANGKALAN GAS (WAYAN)");
check("approved", [m.approved("APPROVED BY Pengawas"), m.approved("SUBMITTED BY Pencacah"), m.approved("")], [true, false, false]);

// --- region: bentuk PERSIS respons asli (nama dipangkas) ---
const WADAH = "5108060006000224";
const TUJ = "5108060002000203";
const GRUP = "a45adac1-e711-4c15-b3f9-1f30fc151565";
const regionCamel = (kode) => ({ id: "r", groupId: GRUP, level1: { fullCode: "51",
  level2: { fullCode: "5108", level3: { fullCode: kode.slice(0, 7), level4: { fullCode: kode.slice(0, 10),
    level5: { fullCode: kode.slice(0, 14), level6: { fullCode: kode } } } } } } });
const regionSnake = (kode) => ({ _id: "r", group_id: GRUP, level_1: { full_code: "51",
  level_2: { full_code: "5108", level_3: { full_code: kode.slice(0, 7), level_4: { full_code: kode.slice(0, 10),
    level_5: { full_code: kode.slice(0, 14), level_6: { full_code: kode, level_7: null } } } } } } });
check("kode dari region datatable", m.kodeSubsls(regionCamel(WADAH)), WADAH);
check("kode dari region detail (level_7 null)", m.kodeSubsls(regionSnake(TUJ)), TUJ);
check("kode per level", m.kodeLevel(regionSnake(TUJ)), ["51", "5108", "5108060", "5108060002", "51080600020002", TUJ]);
check("level wilayah tujuan", m.levelWilayah(TUJ).map((x) => `${x.nama}:${x.kode}`),
  ["provinsi:51", "kabupaten:5108", "kecamatan:5108060", "desa:5108060002", "sls:51080600020002", `subsls:${TUJ}`]);
check("level bukan kode valid", m.levelWilayah("5.10806E+15"), null);
check("bedaLevel cocok semua", m.bedaLevel(m.kodeLevel(regionSnake(TUJ)), TUJ), []);
check("bedaLevel desa beda", m.bedaLevel(["51", "5108", "5108060", "5108060009", "51080600020002", TUJ], TUJ),
  ["desa 5108060009 != 5108060002"]);
check("bedaLevel level hilang", m.bedaLevel(["51", "5108"], TUJ).length, 4);

// --- ringkas dokumen: datatable & detail -> bentuk sama ---
const ID = "11111111-2222-4333-8444-555555555555";
const itDt = { id: ID, codeIdentity: `${WADAH} - Warung Sembako (Wayan)`, data1: "WARUNG SEMBAKO (WAYAN)",
  assignmentStatusAlias: "APPROVED BY Pengawas", currentUserUsername: "pml@x", region: regionCamel(WADAH) };
check("ringkas datatable", m.ringkasDokumen(itDt), { id: ID, kode: WADAH, level: m.kodeLevel(regionCamel(WADAH)),
  alias: "APPROVED BY Pengawas", nama: ["WARUNG SEMBAKO (WAYAN)"], grup: GRUP, pengguna: "pml@x" });
const detail = { success: true, data: { code_identity: `${WADAH} - WARUNG SEMBAKO (WAYAN)`, assignment_status_alias: "APPROVED BY Pengawas",
  current_user_username: "pml@x", region: regionSnake(TUJ) } };
check("ringkas detail (id dari argumen)", m.ringkasDetail(detail, ID),
  { id: ID, kode: TUJ, level: m.kodeLevel(regionSnake(TUJ)), alias: "APPROVED BY Pengawas", nama: ["WARUNG SEMBAKO (WAYAN)"], grup: GRUP, pengguna: "pml@x" });
check("ringkas detail gagal", [m.ringkasDetail({ success: false }, ID), m.ringkasDetail({ success: true, data: {} }, ID)], [null, null]);
check("nama dari kode identitas", m.namaDariKode("5108060014000403 - Praktek Dokter (X)"), "PRAKTEK DOKTER (X)");
check("nama target + nama lama", m.namaTarget({ n: "A (B)", na: ["a  (b)", "LAMA"] }), ["A (B)", "LAMA"]);

// --- posisi & klasifikasi target ---
const asal = new Set([WADAH]);
const dok = (o) => ({ id: o.id, kode: o.kode || WADAH, level: m.kodeLevel(regionSnake(o.kode || WADAH)),
  alias: o.alias || "APPROVED BY Pengawas", nama: o.nama || ["X (Y)"], grup: GRUP, pengguna: "" });
check("posisi: di wadah & approved -> SIAP", m.nilaiPosisi(dok({ id: "a" }), TUJ, asal).status, "SIAP");
check("posisi: di tujuan", m.nilaiPosisi(dok({ id: "a", kode: TUJ }), TUJ, asal).status, "SUDAH_DI_TUJUAN");
check("posisi: di tujuan tapi level beda", m.nilaiPosisi({ ...dok({ id: "a", kode: TUJ }), level: ["51", "5108", "5108010"] }, TUJ, asal).status, "LEVEL_BEDA");
check("posisi: subsls lain", m.nilaiPosisi(dok({ id: "a", kode: "5108070001000101" }), TUJ, asal).status, "DI_SUBSLS_LAIN");
check("posisi: belum approved", m.nilaiPosisi(dok({ id: "a", alias: "SUBMITTED BY Pencacah" }), TUJ, asal).status, "BELUM_APPROVED");
check("posisi: kode rusak", m.nilaiPosisi({ id: "a", kode: "" }, TUJ, asal).status, "RESPONS_TIDAK_DIKENAL");

const peta = new Map([
  ["a", dok({ id: "a" })], ["b", dok({ id: "b", kode: TUJ })], ["h", { id: "h", hilang: true }],
  ["c", dok({ id: "c", nama: ["LAIN SAMA SEKALI"] })], ["d", dok({ id: "d", nama: ["NAMA LAMA (Y)"] })],
  ["e", dok({ id: "e" })], ["f", dok({ id: "f" })],
]);
const tg = (o) => ({ k: "k", s: 0, b: 2, n: "X (Y)", t: TUJ, ids: [], ...o });
const st = (o) => { const r = m.nilaiTarget(tg(o), peta, asal); return [r.status, r.dok ? r.dok.id : null]; };
check("target SIAP", st({ ids: ["a"] }), ["SIAP", "a"]);
check("target sudah di tujuan", st({ ids: ["b"] }), ["SUDAH_DI_TUJUAN", "b"]);
check("2 ID: satu terhapus, satu hidup -> pakai yang hidup", st({ ids: ["h", "a"] }), ["SIAP", "a"]);
check("2 ID hidup -> GANDA", st({ ids: ["e", "f"] }), ["DOKUMEN_GANDA", null]);
check("semua ID terhapus -> HILANG", st({ ids: ["h"] }), ["DOKUMEN_HILANG", null]);
check("ID belum terbaca -> TIDAK_TERBACA", st({ ids: ["zz"] }), ["TIDAK_TERBACA", null]);
check("satu hidup + satu belum terbaca -> TIDAK_TERBACA (ganda belum bisa disingkirkan)", st({ ids: ["a", "zz"] }), ["TIDAK_TERBACA", "a"]);
check("nama tidak cocok", st({ ids: ["c"] }), ["NAMA_TIDAK_COCOK", "c"]);
check("nama lama audit (na) cocok", st({ ids: ["d"], na: ["NAMA LAMA (Y)"] }), ["SIAP", "d"]);
check("tujuan tidak valid", st({ ids: ["a"], t: "5108" }), ["TUJUAN_TIDAK_VALID", null]);
check("tanpa ID", st({ ids: [] }), ["TIDAK_TERBACA", null]);
check("di tujuan tapi level beda -> RESPONS_TIDAK_DIKENAL",
  m.nilaiTarget(tg({ ids: ["x"] }), new Map([["x", { ...dok({ id: "x", kode: TUJ }), level: ["51"] }]]), asal).status, "RESPONS_TIDAK_DIKENAL");

// --- rombongan ---
const siap = (id, tujuan, kodeAsal = WADAH, grup = GRUP) => ({ t: tg({ t: tujuan, k: id }), r: { status: "SIAP", dok: { ...dok({ id, kode: kodeAsal }), grup } } });
const T2 = "5108010001000101";
const daftar = [];
for (let i = 0; i < 53; i++) daftar.push(siap(`t${i}`, TUJ));
daftar.push(siap("u1", T2), siap("w1", TUJ, "5108060006000116"), siap("u2", T2));
const rb = m.susunRombongan(daftar, 50);
check("rombongan: per (tujuan, asal), <= 50, urut tujuan",
  rb.map((r) => [r.tujuan, r.asal, r.anggota.length]),
  [[T2, WADAH, 2], [TUJ, "5108060006000116", 1], [TUJ, WADAH, 50], [TUJ, WADAH, 3]]);
check("rombongan: perKirim di luar 1-50 dipotong ke 50", m.susunRombongan(daftar, 500).length, 4);
check("rombongan: perKirim 20", m.susunRombongan(daftar, 20).map((r) => r.anggota.length), [2, 1, 20, 20, 13]);
check("rombongan: grup beda dipisah", m.susunRombongan([siap("g1", TUJ), siap("g2", TUJ, WADAH, "lain")], 50).length, 2);

check("sampel 3 dari 50", m.indeksSampel(50, 3), [0, 25, 49]);
check("sampel 3 dari 2", m.indeksSampel(2, 3), [0, 1]);
check("sampel 1", m.indeksSampel(10, 1), [0]);
check("sampel semua", m.indeksSampel(4, "semua"), [0, 1, 2, 3]);
check("sampel 0", m.indeksSampel(4, 0), []);

// --- respons update-region-bulk ---
const rp = (http, obj, n = 2) => m.nilaiResponsPindah(http, typeof obj === "string" ? obj : JSON.stringify(obj), n, TUJ);
check("OK dgn updatedCount & newRegionFullCode", rp(200, { success: true, message: "Berhasil", data: { updatedCount: 2, newRegionFullCode: TUJ } }).status, "OK");
check("OK tanpa data", rp(200, { success: true }).ok, true);
check("OK di akar objek", rp(200, { success: true, updatedCount: 2, newRegionFullCode: TUJ }).ok, true);
check("updatedCount beda -> DIPINDAH_JUMLAH_BEDA", rp(200, { success: true, data: { updatedCount: 1, newRegionFullCode: TUJ } }).status, "DIPINDAH_JUMLAH_BEDA");
check("newRegionFullCode beda -> RESPONS_TIDAK_DIKENAL", rp(200, { success: true, data: { updatedCount: 2, newRegionFullCode: WADAH } }).status, "RESPONS_TIDAK_DIKENAL");
check("errorCode 5 -> REGION_SAMA", rp(400, { success: false, message: "Region baru sama dengan region saat ini untuk assignment X, tidak ada perubahan", errorCode: 5 }).status, "REGION_SAMA");
check("pesan region sama tanpa errorCode -> REGION_SAMA", rp(200, { success: false, message: "Region baru sama dengan region saat ini" }).status, "REGION_SAMA");
check("gagal lain", rp(200, { success: false, message: "Petugas tidak valid", errorCode: 9 }).status, "GAGAL_PINDAH");
check("401/403 -> SESI_DITOLAK", [rp(401, "").status, rp(403, "x").status], ["SESI_DITOLAK", "SESI_DITOLAK"]);
check("429/504/0 -> sementara", [rp(429, "{}").status, rp(504, "<html>").status, rp(0, "").status], ["RATE_LIMIT", "SERVER_SIBUK", "SERVER_SIBUK"]);
check("bukan JSON -> RESPONS_TIDAK_DIKENAL", rp(200, "<html>").status, "RESPONS_TIDAK_DIKENAL");

check("jeda 429: Retry-After dihormati (min 5 dtk)", [m.jedaRateLimit(0, "30"), m.jedaRateLimit(0, "1")], [30000, 5000]);
check("jeda 429: 15 dtk x 2^ke, maks 2 menit", [m.jedaRateLimit(0, null), m.jedaRateLimit(2, null), m.jedaRateLimit(9, "")], [15000, 60000, 120000]);
check("faktor jeda naik x2 maks 8, turun x0,8 min 1", [m.faktorJeda(1, true), m.faktorJeda(8, true), m.faktorJeda(4, false), m.faktorJeda(1, false)], [2, 8, 3.2, 1]);
check("galat sementara", [m.jenisSementara(429), m.jenisSementara(504), m.jenisSementara(0), m.jenisSementara(200)], ["RATE_LIMIT", "SERVER_SIBUK", "SERVER_SIBUK", null]);
check("gagal dihitung", [m.gagalDihitung("GAGAL_PINDAH"), m.gagalDihitung("ERROR_X"), m.gagalDihitung("TUJUAN_BELUM_DIBUKA")], [true, true, false]);

// --- tujuan & petugas (bentuk respons asli) ---
const w = (o) => ({ smallestRegionFullCode: TUJ, doneListing: false, regionGroupId: GRUP, ...o });
check("tujuan OK", m.nilaiWilayahTujuan(TUJ, [w()], GRUP).status, "OK");
check("tujuan Listing Selesai", m.nilaiWilayahTujuan(TUJ, [w({ doneListing: true })], GRUP).status, "TUJUAN_BELUM_DIBUKA");
check("tujuan Listing Selesai diizinkan", m.nilaiWilayahTujuan(TUJ, [w({ doneListing: true })], GRUP, { izinkanTujuanSelesai: true }).status, "OK");
check("tujuan tidak ada / ganda", [m.nilaiWilayahTujuan(TUJ, [], GRUP).status, m.nilaiWilayahTujuan(TUJ, [w(), w()], GRUP).status], ["TUJUAN_TIDAK_ADA", "TUJUAN_GANDA"]);
check("tujuan grup beda", m.nilaiWilayahTujuan(TUJ, [w({ regionGroupId: "lain" })], GRUP).status, "RESPONS_TIDAK_DIKENAL");
const pml = { id: "ur1", allocationId: "al1", smallestRegionCode: TUJ, email: "pml@x", active: true };
const ppl = { id: "ur2", allocationId: "al2", parentAllocationId: "al1", smallestRegionCode: TUJ, email: "ppl@x" };
check("PML tepat 1", m.pilihPetugas("Pengawas", [pml, { ...pml, id: "x", active: false }], TUJ).status, "OK");
check("PPL harus anak PML terpilih", m.pilihPetugas("Pencacah", [ppl, { ...ppl, id: "y", parentAllocationId: "lain" }], TUJ, "al1").petugas.id, "ur2");
check("PPL ganda", m.pilihPetugas("Pencacah", [ppl, { ...ppl, id: "y", allocationId: "al3" }], TUJ, "al1").status, "PETUGAS_TUJUAN_GANDA");
check("petugas tidak ada", m.pilihPetugas("Pengawas", [], TUJ).status, "PETUGAS_TUJUAN_TIDAK_ADA");
const roles = [{ id: "r7", sequence: 7, isPencacah: false, surveyRoleGroup: { name: "Petugas" } },
  { id: "r8", sequence: 8, isPencacah: true, surveyRoleGroup: { name: "Petugas" } }, { id: "r1", surveyRoleGroup: { name: "Admin" } }];
check("peran petugas urut sequence", m.peranPetugas([roles[1], roles[2], roles[0]]).map((r) => r.id), ["r7", "r8"]);
check("peran bentuk lain -> null", m.peranPetugas([roles[0]]), null);
check("body pindah rombongan", m.bodyPindah(["a", "b"], TUJ, GRUP, pml, ppl),
  { assignmentIds: ["a", "b"], smallestLevelFullCode: TUJ, groupId: GRUP, userRegionIds: ["ur1", "ur2"] });

// --- daftar per jendela tanggal ---
const bd = m.bodyDaftar("per", 150, 150, "2026-09-15T16:00:00.000Z", "2026-09-16T00:00:00.000Z", ["PAPI"]);
check("body daftar: mode & tanggal ISO penuh", [bd.start, bd.length, bd.assignmentExtraParam],
  [150, 150, { surveyPeriodId: "per", assignmentErrorStatusType: -1, assignmentStatusAlias: null, mode: ["PAPI"],
    dateCreatedFrom: "2026-09-15T16:00:00.000Z", dateCreatedTo: "2026-09-16T00:00:00.000Z" }]);
check("body daftar tanpa saringan", Object.keys(m.bodyDaftar("per", 0, 150, null, null, null).assignmentExtraParam),
  ["surveyPeriodId", "assignmentErrorStatusType", "assignmentStatusAlias"]);
check("belah jendela", m.bagiJendela("2026-09-24T00:00:00.000Z", "2026-09-25T00:00:00.000Z"),
  [["2026-09-24T00:00:00.000Z", "2026-09-24T12:00:00.000Z"], ["2026-09-24T12:00:00.000Z", "2026-09-25T00:00:00.000Z"]]);
check("gabung jendela bersebelahan <= batas",
  m.gabungJendela([["c", "d", 300], ["2026-01-01T00:00:00.000Z", "2026-02-01T00:00:00.000Z", 100],
    ["2026-02-01T00:00:00.000Z", "2026-03-01T00:00:00.000Z", 400], ["2026-03-01T00:00:00.000Z", "2026-04-01T00:00:00.000Z", 300]]
    .filter((j) => j[0] !== "c"), 600),
  [["2026-01-01T00:00:00.000Z", "2026-03-01T00:00:00.000Z", 500], ["2026-03-01T00:00:00.000Z", "2026-04-01T00:00:00.000Z", 300]]);

// --- hasil tersimpan ---
const h = (st, j = "pindah") => ({ w: "2026-09-27T10:00:00", j, st, p: "" });
check("hasil baru biasa menimpa", m.gabungHasil(h("SIAP_PINDAH", "periksa"), h("BELUM_APPROVED", "periksa")).st, "BELUM_APPROVED");
check("SERVER_OK + periksa di tujuan -> TERVERIFIKASI", m.gabungHasil(h("DIPINDAH_SERVER_OK"), h("SUDAH_DI_TUJUAN", "periksa")).st, "DIPINDAH_TERVERIFIKASI");
check("SERVER_OK + periksa tidak di tujuan -> BELUM_TERVERIFIKASI", m.gabungHasil(h("DIPINDAH_SERVER_OK"), h("DIPINDAH_BELUM_TERVERIFIKASI", "periksa")).st, "DIPINDAH_BELUM_TERVERIFIKASI");
check("TERVERIFIKASI tidak tertimpa periksa", m.gabungHasil(h("DIPINDAH_TERVERIFIKASI"), h("SIAP_PINDAH", "periksa")).st, "DIPINDAH_TERVERIFIKASI");
check("SERVER_OK tidak tertimpa klasifikasi lain", m.gabungHasil(h("DIPINDAH_SERVER_OK"), h("BELUM_APPROVED", "periksa")).st, "DIPINDAH_SERVER_OK");
check("bukti pindah baru menimpa", m.gabungHasil(h("DIPINDAH_SERVER_OK"), h("DIPINDAH_TERVERIFIKASI")).st, "DIPINDAH_TERVERIFIKASI");

const T = [tg({ k: "k1", t: TUJ }), tg({ k: "k2", t: T2 }), tg({ k: "k3", t: TUJ })];
const simpan = { "0|k1": { st: "DIPINDAH_SERVER_OK" }, "0|k3": { st: "SUDAH_DI_TUJUAN" } };
check("kunci hasil = sumber|kunci", m.kunciHasil(T[0]), "0|k1");
check("saring: lewati yang sudah dipindah (bukan SUDAH_DI_TUJUAN)", m.saringTarget(T, simpan, { lewatiSelesai: true }).map((t) => t.k), ["k2", "k3"]);
check("saring: periksa tidak melewati", m.saringTarget(T, simpan, { lewatiSelesai: false }).length, 3);
check("saring: awalan tujuan", m.saringTarget(T, {}, { tujuan: ["510801"] }).map((t) => t.k), ["k2"]);
check("saring: kunci", m.saringTarget(T, {}, { kunci: ["k3"] }).map((t) => t.k), ["k3"]);

console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
process.exit(okAll ? 0 : 1);
