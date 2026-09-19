// Uji logika murni pindah_wilayah_console.js — offline (Node).
// Jalankan: node tests/test_pindah_wilayah_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "pindah_wilayah", "pindah_wilayah_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

check("template: TARGET & ASAL kosong", [m.TARGET, m.ASAL], [[], []]);
check("halaman Data",
  m.halamanData("/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data"),
  { survei: "a0429e96-51a5-477b-a415-485f9c153004", periode: "fd68e454-ba45-4b85-8205-f3bf777ded24" });
check("bukan halaman Data", m.halamanData("/app/surveys"), null);
check("norm", m.norm("  pangkalan  gas (Wayan) "), "PANGKALAN GAS (WAYAN)");
check("approved", [m.approved("APPROVED BY Pengawas"), m.approved("SUBMITTED BY Pencacah"), m.approved("")], [true, false, false]);

// --- region: bentuk PERSIS respons asli (nama dipangkas) ---
const ASAL = "5108060014000403";
const TUJ = "5108060002000203";
const regionCamel = (kode) => ({ id: "r", groupId: "a45adac1-e711-4c15-b3f9-1f30fc151565", level1: { fullCode: "51",
  level2: { fullCode: "5108", level3: { fullCode: kode.slice(0, 7), level4: { fullCode: kode.slice(0, 10),
    level5: { fullCode: kode.slice(0, 14), level6: { fullCode: kode } } } } } } });
const regionSnake = (kode) => ({ _id: "r", group_id: "a45adac1-e711-4c15-b3f9-1f30fc151565", level_1: { full_code: "51",
  level_2: { full_code: "5108", level_3: { full_code: kode.slice(0, 7), level_4: { full_code: kode.slice(0, 10),
    level_5: { full_code: kode.slice(0, 14), level_6: { full_code: kode, level_7: null } } } } } } });
check("kode dari region datatable", m.kodeSubsls(regionCamel(ASAL)), ASAL);
check("kode dari region detail (level_7 null)", m.kodeSubsls(regionSnake(TUJ)), TUJ);
check("kode item tanpa region -> awalan codeIdentity", m.kodeItem({ codeIdentity: `${ASAL} - PANGKALAN GAS (X)` }), ASAL);

// --- item datatable ---
let seq = 0;
const item = (o) => ({ id: `id-${++seq}-0000-0000`, codeIdentity: `${ASAL} - ${o.data1 || "X"}`, data1: "X",
  assignmentStatusAlias: "APPROVED BY Pengawas", region: regionCamel(o.kode || ASAL), ...o });
const A = item({ data1: "PANGKALAN GAS (WAYAN SUMARTAWA)" });
const B = item({ data1: "PRAKTIK DOKTER (I MADE)", assignmentStatusAlias: "SUBMITTED BY Pencacah" });
const PRE = item({ data1: "APOTEK SEHAT", codeIdentity: `${ASAL} - UMK - 19` });
const C1 = item({ data1: "APOTEK KEMBAR" });
const C2 = item({ data1: "apotek  kembar" });
const D = item({ data1: "SUDAH PINDAH", kode: TUJ, codeIdentity: `${TUJ} - SUDAH PINDAH` });
const E = item({ data1: "DI TEMPAT LAIN", kode: "5108010010000105" });
const F = item({ data1: "DRAFT DAN APPROVED", assignmentStatusAlias: "DRAFT" });
const F2 = item({ data1: "DRAFT DAN APPROVED" });
const idx = m.indeksItem([A, B, PRE, C1, C2, D, E, F, F2, A]);
check("prelist tidak masuk indeks nama", idx.byNama["APOTEK SEHAT"], undefined);
check("prelist tetap bisa lewat id", !!idx.byId[PRE.id], true);

const asal = new Set([ASAL]);
const tgt = (o) => ({ k: "k", s: "Agenda.xlsx", b: 2, n: "X", t: TUJ, p: "ppl@gmail.com", ids: [], ...o });
const st = (o) => m.rencanakan(tgt(o), idx, asal);
check("cocok nama, APPROVED, di asal -> PERLU_PINDAH", [st({ n: A.data1 }).status, st({ n: A.data1 }).item.id], ["PERLU_PINDAH", A.id]);
check("cocok lewat ID audit walau nama beda", st({ n: "NAMA LAIN", ids: [A.id] }).status, "PERLU_PINDAH");
check("belum approved", st({ n: B.data1 }).status, "BELUM_APPROVED");
check("nama prelist tidak dicocokkan", st({ n: "APOTEK SEHAT" }).status, "DOKUMEN_TIDAK_DITEMUKAN");
check("dua dokumen APPROVED -> ganda", st({ n: "APOTEK KEMBAR" }).status, "DOKUMEN_GANDA");
check("sudah di tujuan", st({ n: "SUDAH PINDAH" }).status, "SUDAH_DI_TUJUAN");
check("di subsls lain", st({ n: "DI TEMPAT LAIN" }).status, "DI_SUBSLS_LAIN");
check("DRAFT + APPROVED -> yang APPROVED dipindah", [st({ n: "DRAFT DAN APPROVED" }).status, st({ n: "DRAFT DAN APPROVED" }).item.id],
  ["PERLU_PINDAH", F2.id]);
check("nama ganda di Agenda tanpa id -> tidak dicocokkan", st({ n: A.data1, g: 1 }).status, "NAMA_GANDA_DI_AGENDA");
check("nama ganda di Agenda dgn id -> tetap", st({ n: A.data1, g: 1, ids: [A.id] }).status, "PERLU_PINDAH");
check("tidak ditemukan", st({ n: "TIDAK ADA" }).status, "DOKUMEN_TIDAK_DITEMUKAN");
check("tujuan tidak valid", st({ n: A.data1, t: "5108" }).status, "TUJUAN_TIDAK_VALID");

const rencana = [st({ n: A.data1 }), st({ n: "SUDAH PINDAH" })];
check("tidak dikenali: APPROVED non-prelist di asal yg tak diklaim",
  m.tidakDikenali([A, B, PRE, C1, C2, D, E, F, F2], rencana, asal).map((x) => x.id), [C1.id, C2.id, F2.id]);

// --- detail get-by-assignment-id ---
const det = (kode, alias = "APPROVED BY Pengawas", o = {}) => ({ success: true, message: "OK",
  data: { _id: A.id, assignment_status_alias: alias, region: regionSnake(kode), current_user_username: "pml@gmail.com", ...o } });
check("detail siap", [m.nilaiDetail(det(ASAL), ASAL, TUJ).status, m.nilaiDetail(det(ASAL), ASAL, TUJ).groupId],
  ["SIAP", "a45adac1-e711-4c15-b3f9-1f30fc151565"]);
check("detail sudah di tujuan", m.nilaiDetail(det(TUJ), ASAL, TUJ).status, "SUDAH_DI_TUJUAN");
check("detail dipindah orang lain", m.nilaiDetail(det("5108010010000105"), ASAL, TUJ).status, "ASAL_BERUBAH");
check("detail tidak approved lagi", m.nilaiDetail(det(ASAL, "REJECTED BY Pengawas"), ASAL, TUJ).status, "BELUM_APPROVED");
check("detail gagal", m.nilaiDetail({ success: false, message: "x" }, ASAL, TUJ).status, "RESPONS_TIDAK_DIKENAL");
const tanpaGroup = det(ASAL);
delete tanpaGroup.data.region.group_id;
check("detail tanpa group_id", m.nilaiDetail(tanpaGroup, ASAL, TUJ).status, "RESPONS_TIDAK_DIKENAL");

// --- wilayah tujuan (bentuk item assignment-region/datatable) ---
const G = "a45adac1-e711-4c15-b3f9-1f30fc151565";
const w = (o) => ({ id: "w1", smallestRegionFullCode: TUJ, regionGroupId: G, doneListing: false, doneTarikSample: false, ...o });
check("tujuan terbuka", m.nilaiWilayahTujuan(TUJ, [w({ smallestRegionFullCode: "5108060002000204" }), w({})], G).status, "OK");
check("tujuan belum dibuka", m.nilaiWilayahTujuan(TUJ, [w({ doneListing: true })], G).status, "TUJUAN_BELUM_DIBUKA");
check("tujuan selesai diizinkan", m.nilaiWilayahTujuan(TUJ, [w({ doneListing: true })], G, { izinkanTujuanSelesai: true }).status, "OK");
check("tujuan tidak ada", m.nilaiWilayahTujuan(TUJ, [], G).status, "TUJUAN_TIDAK_ADA");
check("tujuan ganda", m.nilaiWilayahTujuan(TUJ, [w({}), w({})], G).status, "TUJUAN_GANDA");
check("group beda -> berhenti", m.nilaiWilayahTujuan(TUJ, [w({ regionGroupId: "lain" })], G).status, "RESPONS_TIDAK_DIKENAL");

// --- petugas user-region (bentuk respons asli, email disamarkan) ---
const ur = (o) => ({ id: "c78fee73", userId: "u1", username: "pml@gmail.com", email: "pml@gmail.com", smallestRegionCode: TUJ,
  allocationId: "f7b9c194", parentAllocationId: null, active: true, ...o });
check("pengawas tunggal", [m.pilihPetugas("Pengawas", [ur({})], TUJ).status, m.pilihPetugas("Pengawas", [ur({})], TUJ).petugas.id],
  ["OK", "c78fee73"]);
check("pengawas ganda", m.pilihPetugas("Pengawas", [ur({}), ur({ id: "x", email: "b@x" })], TUJ).status, "PETUGAS_TUJUAN_GANDA");
check("pengawas nonaktif diabaikan", m.pilihPetugas("Pengawas", [ur({}), ur({ id: "x", active: false })], TUJ).status, "OK");
check("alokasi level desa (awalan tujuan) diterima", m.pilihPetugas("Pengawas", [ur({ smallestRegionCode: TUJ.slice(0, 10) })], TUJ).status, "OK");
check("alokasi subsls lain ditolak", m.pilihPetugas("Pengawas", [ur({ smallestRegionCode: "5108060002000204" })], TUJ).status,
  "PETUGAS_TUJUAN_TIDAK_ADA");
check("pencacah harus berinduk pengawas terpilih",
  m.pilihPetugas("Pencacah", [ur({ id: "p1", parentAllocationId: "lain" })], TUJ, "f7b9c194").status, "PETUGAS_TUJUAN_TIDAK_ADA");
check("pencacah berinduk benar",
  m.pilihPetugas("Pencacah", [ur({ id: "p1", parentAllocationId: "f7b9c194" })], TUJ, "f7b9c194").status, "OK");
check("tanpa allocationId -> berhenti", m.pilihPetugas("Pengawas", [ur({ allocationId: null })], TUJ).status, "RESPONS_TIDAK_DIKENAL");
check("data bukan array", m.pilihPetugas("Pengawas", null, TUJ).status, "RESPONS_TIDAK_DIKENAL");

// --- peran Petugas (survey-roles asli: Pengawas seq 7, Pencacah seq 8) ---
const role = (id, sequence, grup, isPencacah) => ({ id, sequence, isPencacah, surveyRoleGroup: { name: grup } });
const roles = [role("adm", 6, "Admin", false), role("pcc", 8, "Petugas", true), role("pgw", 7, "Petugas", false)];
check("peran urut sequence", m.peranPetugas(roles).map((r) => r.id), ["pgw", "pcc"]);
check("peran bentuk lain -> null", m.peranPetugas([role("pgw", 7, "Petugas", false)]), null);

// --- body PUT: sama dgn mfe() halaman (USER_REGION -> userRegion.id, bukan allocationId) ---
check("body pindah", m.bodyPindah("a1", TUJ, G, { id: "c78fee73", allocationId: "f7b9c194" }, { id: "b73e4fbb", allocationId: "z" }),
  { assignmentIds: ["a1"], smallestLevelFullCode: TUJ, groupId: G, userRegionIds: ["c78fee73", "b73e4fbb"] });

// --- respons update-region-bulk ---
check("success true", m.nilaiRespons(200, '{"success":true,"message":"ok"}').status, "OK");
check("success false", m.nilaiRespons(200, '{"success":false,"message":"tidak boleh"}').status, "GAGAL_PINDAH");
check("403 CSRF", m.nilaiRespons(403, "Invalid CSRF Token").status, "SESI_DITOLAK");
check("200 bukan JSON", m.nilaiRespons(200, "<html>").status, "RESPONS_TIDAK_DIKENAL");
check("504 Gateway Time-out (teks asli run user) -> SERVER_SIBUK, bukan berhenti",
  m.nilaiRespons(504, "<html><body><h1>504 Gateway Time-out</h1>\nThe server didn't respond in time.\n</body></html>").status, "SERVER_SIBUK");
check("502/503/gagal jaringan -> SERVER_SIBUK", [502, 503, 0].map((s) => m.nilaiRespons(s, "x").status),
  ["SERVER_SIBUK", "SERVER_SIBUK", "SERVER_SIBUK"]);
check("jenis galat sementara", [429, 504, 502, 503, 0, 500, 404, 200].map(m.jenisSementara),
  ["RATE_LIMIT", "SERVER_SIBUK", "SERVER_SIBUK", "SERVER_SIBUK", "SERVER_SIBUK", null, null, null]);
check("SERVER_SIBUK tidak menghentikan seketika, tapi dihitung beruntun",
  [m.STATUS_BERHENTI_SEGERA.has("SERVER_SIBUK"), m.gagalDihitung("SERVER_SIBUK"), m.gagalDihitung("PENCARIAN_GAGAL"),
    m.gagalDihitung("ERROR_TAK_TERDUGA"), m.gagalDihitung("TUJUAN_BELUM_DIBUKA")], [false, true, true, true, false]);
check("429 (teks asli) -> RATE_LIMIT",
  m.nilaiRespons(429, '{"error":"RATE_LIMIT_EXCEEDED","message":"Rate limit exceeded","status":429}').status, "RATE_LIMIT");
check("RATE_LIMIT menghentikan batch", m.STATUS_BERHENTI_SEGERA.has("RATE_LIMIT"), true);

// --- jeda rate limit ---
check("tanpa Retry-After: 15s, 30s, 60s, 120s, maks 120s",
  [0, 1, 2, 3, 6].map((ke) => m.jedaRateLimit(ke, null)), [15000, 30000, 60000, 120000, 120000]);
check("Retry-After dihormati (min 5 dtk, maks 5 menit)",
  [m.jedaRateLimit(0, "40"), m.jedaRateLimit(3, "1"), m.jedaRateLimit(0, "9999")], [40000, 5000, 300000]);
check("Retry-After bukan angka (tanggal HTTP) -> backoff biasa", m.jedaRateLimit(1, "Wed, 21 Oct 2026 07:28:00 GMT"), 30000);

// --- item ringkas (cache cari nama) tetap dikenali ---
const ringkas = m.ringkasItem(D);
check("item ringkas", ringkas, { id: D.id, codeIdentity: D.codeIdentity, data1: "SUDAH PINDAH", assignmentStatusAlias: "APPROVED BY Pengawas", kode: TUJ });
check("item ringkas bisa direncanakan", m.rencanakan(tgt({ n: "SUDAH PINDAH" }), m.indeksItem([ringkas]), asal).status, "SUDAH_DI_TUJUAN");
check("status berhenti mencakup verifikasi & status berubah",
  ["SESI_DITOLAK", "DIPINDAH_BELUM_TERVERIFIKASI", "DIPINDAH_STATUS_BERUBAH", "RESPONS_TIDAK_DIKENAL"].every((s) => m.STATUS_BERHENTI_SEGERA.has(s)), true);

// --- penyaringan target ---
const T = [tgt({ k: "a", t: TUJ }), tgt({ k: "b", t: TUJ }), tgt({ k: "c", t: ASAL })];
const seb = { a: { jalan: "eksekusi", status: "DIPINDAH_TERVERIFIKASI" }, b: { jalan: "cek", status: "SUDAH_DI_TUJUAN" } };
const ks = (d) => d.map((t) => t.k);
check("lewati tuntas oleh eksekusi", ks(m.saringTarget(T, seb, { lewatiSelesai: true })), ["b", "c"]);
check("lewatiSelesai false", ks(m.saringTarget(T, seb, { lewatiSelesai: false })), ["a", "b", "c"]);
check("filter tujuan & kunci", ks(m.saringTarget(T, {}, { tujuan: [TUJ], kunci: ["b", "c"] })), ["b"]);

// --- peta dua tahap: petakan sekali, cek/eksekusi per ID ---
const W = "2026-09-15T09:00:00.000Z";
const tA = tgt({ k: "a", n: A.data1 });
const eA = m.entriPeta(tA, st({ n: A.data1 }), W);
check("entri peta PERLU_PINDAH", eA,
  { k: "a", id: A.id, asal: ASAL, t: TUJ, status: "PERLU_PINDAH", alias: "APPROVED BY Pengawas", pesan: `${ASAL} -> ${TUJ}`, waktu: W });
check("entri peta tanpa dokumen", m.entriPeta(tgt({ k: "x", n: "TIDAK ADA" }), st({ n: "TIDAK ADA" }), W).id, "");

const TP = [tA, tgt({ k: "b" }), tgt({ k: "c" }), tgt({ k: "d" }), tgt({ k: "e" }), tgt({ k: "f", t: "5108090010000503" })];
const peta = {
  a: eA,
  b: { k: "b", id: "id-b", asal: ASAL, t: TUJ, status: "BELUM_APPROVED", alias: "SUBMITTED BY Pencacah" },
  c: { k: "c", id: "", asal: "", t: TUJ, status: "DOKUMEN_TIDAK_DITEMUKAN" },
  d: { k: "d", id: "id-d", asal: ASAL, t: TUJ, status: "DOKUMEN_GANDA" },
  e: { k: "e", id: "id-e", asal: "5108010010000105", t: TUJ, status: "PERLU_PINDAH" },  // asal bukan ASAL skrip ini
  f: { k: "f", id: "id-f", asal: ASAL, t: TUJ, status: "PERLU_PINDAH" },                // tujuan Agenda sudah berubah
  z: { k: "z", id: "id-z", asal: ASAL, t: TUJ, status: "PERLU_PINDAH" },                // kunci tidak ada di TARGET
};
const kerja = m.kerjaDariPeta(peta, TP, {}, { lewatiSelesai: true }, asal);
check("kerja: PERLU_PINDAH + BELUM_APPROVED ber-ID, asal & tujuan cocok", kerja.map((x) => x.t.k), ["a", "b"]);
check("kerja: item dari peta dikenali asalnya", [m.kodeItem(kerja[0].r.item), kerja[0].r.item.id], [ASAL, A.id]);
check("kerja: lewati yang sudah dipindah + limit",
  m.kerjaDariPeta(peta, TP, { a: { jalan: "eksekusi", status: "DIPINDAH_TERVERIFIKASI" } }, { lewatiSelesai: true, limit: 5 }, asal)
    .map((x) => x.t.k), ["b"]);
check("kerja: tanpa peta -> kosong", m.kerjaDariPeta(null, TP, {}, {}, asal), []);
check("gabung peta: baru menimpa, kunci asing dibuang",
  Object.keys(m.gabungPeta({ a: { status: "DOKUMEN_TIDAK_DITEMUKAN" }, z: {} }, { a: eA, b: peta.b }, TP)).sort(), ["a", "b"]);
check("gabung peta: entri lama tetap kalau tidak dipetakan ulang",
  m.gabungPeta({ c: peta.c }, { a: eA }, TP).c.status, "DOKUMEN_TIDAK_DITEMUKAN");

// === ALUR SATUAN (mode cari / pindah) ===
// --- level wilayah provinsi..subsls ---
check("level wilayah tujuan", m.levelWilayah(TUJ).map((x) => `${x.nama}:${x.kode}`),
  ["provinsi:51", "kabupaten:5108", "kecamatan:5108060", "desa:5108060002", "sls:51080600020002", "subsls:5108060002000203"]);
check("level wilayah kode tidak valid", m.levelWilayah("5108"), null);
check("jalur level", m.jalurLevel(TUJ), "51 > 5108 > 5108060 > 5108060002 > 51080600020002 > 5108060002000203");
check("kode per level dari detail (level_7 null diabaikan)", m.kodeLevel(regionSnake(TUJ)),
  ["51", "5108", "5108060", "5108060002", "51080600020002", TUJ]);
check("kode per level dari datatable", m.kodeLevel(regionCamel(ASAL)).length, 6);
check("semua level cocok", m.bedaLevel(m.kodeLevel(regionSnake(TUJ)), TUJ), []);
const regionAneh = regionSnake(TUJ);
regionAneh.level_1.level_2.level_3.full_code = "5108010";
check("level kecamatan beda terdeteksi", m.bedaLevel(m.kodeLevel(regionAneh), TUJ), ["kecamatan 5108010 != 5108060"]);
check("level kosong", m.bedaLevel([], TUJ).length, 6);
check("level beda menghentikan batch", m.STATUS_BERHENTI_SEGERA.has("DIPINDAH_LEVEL_BEDA"), true);

// --- detail: asal bisa lebih dari satu, nama & level ikut terbaca ---
const ASAL2 = "5108010010000105";
check("detail: asal Set", m.nilaiDetail(det(ASAL2), new Set([ASAL, ASAL2]), TUJ).status, "SIAP");
check("detail: asal array", m.nilaiDetail(det(ASAL2), [ASAL, ASAL2], TUJ).status, "SIAP");
check("detail: di luar semua asal", m.nilaiDetail(det("5108090010000503"), new Set([ASAL, ASAL2]), TUJ).status, "ASAL_BERUBAH");
const detNama = m.nilaiDetail(det(ASAL, "APPROVED BY Pengawas", { code_identity: `${ASAL} - Pangkalan Gas (Wayan)` }), ASAL, TUJ);
check("detail: nama dari code_identity & level", [detNama.nama, detNama.level[2]], [["PANGKALAN GAS (WAYAN)"], "5108060"]);

// --- nama & istilah pencarian ---
check("nama dari kode identitas", m.namaDariKode(`${ASAL} -  Praktek Dokter (Made)`), "PRAKTEK DOKTER (MADE)");
check("nama tanpa awalan kode tetap", m.namaDariKode("apotek sehat"), "APOTEK SEHAT");
check("nama target + nama lama (unik)", m.namaTarget({ n: "PANGKALAN GAS (I PUTU ARYA)", na: ["pangkalan gas i putu arya (i putu arya)", "PANGKALAN GAS (I PUTU ARYA)"] }),
  ["PANGKALAN GAS (I PUTU ARYA)", "PANGKALAN GAS I PUTU ARYA (I PUTU ARYA)"]);
check("istilah cari: nama, nama lama, lalu kode identitas per asal",
  m.istilahCariDokumen({ n: "BARU", na: ["LAMA"], a: [ASAL, "123"] }),
  ["BARU", "LAMA", `${ASAL} - BARU`, `${ASAL} - LAMA`]);
check("istilah cari tanpa asal = nama saja", m.istilahCariDokumen({ n: "BARU" }), ["BARU"]);
check("asal per target menang, cadangan ASAL global", [[...m.asalUntuk({ a: [ASAL2] }, [ASAL])], [...m.asalUntuk({}, [ASAL])]],
  [[ASAL2], [ASAL]]);

// --- nilai pencarian ---
const cari = (o, items) => m.nilaiPencarian(tgt(o), items);
const A2 = item({ data1: A.data1, assignmentStatusAlias: "APPROVED BY Pengawas" });  // nama sama, ID lain
const r1 = cari({ n: A.data1, ids: [A.id] }, [C1, A, PRE]);
check("ID approve tampil -> KETEMU, nama cocok", [r1.status, r1.item.id, r1.namaCocok, r1.pesan], ["KETEMU", A.id, true, ""]);
const r2 = cari({ n: A.data1, ids: [A.id] }, [A2, A, A]);
check("ID approve + dokumen lain bernama sama -> tetap ID approve, yg lain dilaporkan",
  [r2.status, r2.item.id, r2.pesan.startsWith("dokumen lain bernama sama (TIDAK dipindah)")], ["KETEMU", A.id, true]);
check("ID approve tidak tampil (hanya nama sama) -> TIDAK_TAMPIL, bukan memilih yg lain",
  [cari({ n: A.data1, ids: [A.id] }, [A2]).status, cari({ n: A.data1, ids: [A.id] }, [A2]).item], ["TIDAK_TAMPIL", null]);
check("ID approve tampil tapi nama beda -> namaCocok false (dicek lagi di detail)",
  [cari({ n: "NAMA LAIN", ids: [A.id] }, [A]).status, cari({ n: "NAMA LAIN", ids: [A.id] }, [A]).namaCocok], ["KETEMU", false]);
check("hasil kosong", cari({ n: A.data1, ids: [A.id] }, []).status, "TIDAK_TAMPIL");
check("tanpa ID: nama lama cocok", cari({ n: "BARU", na: [C1.data1] }, [C1]).status, "KETEMU");
check("tanpa ID: dua APPROVED -> ganda", cari({ n: "APOTEK KEMBAR" }, [C1, C2]).status, "DOKUMEN_GANDA");
check("tanpa ID: belum approved", cari({ n: B.data1 }, [B]).status, "BELUM_APPROVED");
check("tanpa ID: prelist tidak dicocokkan", cari({ n: "APOTEK SEHAT" }, [PRE]).status, "TIDAK_TAMPIL");
check("tanpa ID: DRAFT + APPROVED -> yang APPROVED", cari({ n: "DRAFT DAN APPROVED" }, [F, F2]).item.id, F2.id);
check("tanpa ID: cocok lewat codeIdentity walau data1 kosong",
  cari({ n: "TOKO KODE" }, [item({ data1: "", codeIdentity: `${ASAL} - toko kode` })]).status, "KETEMU");

// --- jeda pencarian adaptif ---
check("faktor jeda naik x2 maks 8, turun x0,8 min 1",
  [m.faktorJeda(1, true), m.faktorJeda(8, true), m.faktorJeda(2, false), m.faktorJeda(1.1, false)], [2, 8, 1.6, 1]);

// --- lewati yang tuntas oleh mode pindah ---
check("lewati tuntas oleh mode pindah, bukan oleh mode cari",
  ks(m.saringTarget(T, { a: { jalan: "pindah", status: "DIPINDAH_TERVERIFIKASI" }, b: { jalan: "cari", status: "SUDAH_DI_TUJUAN" } },
    { lewatiSelesai: true })), ["b", "c"]);

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
