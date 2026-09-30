// Simulasi ALUR BROWSER pindah_wilayah_console.js terhadap server fasih-sm PALSU (Node, offline, jam virtual).
// Bentuk request/respons ditiru dari endpoint asli yang terdokumentasi di kepala skrip Console.
// Jalankan: node tests/test_pindah_wilayah_simulasi.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const SURVEI = "a0429e96-51a5-477b-a415-485f9c153004";
const PERIODE = "fd68e454-ba45-4b85-8205-f3bf777ded24";
const GRUP = "a45adac1-e711-4c15-b3f9-1f30fc151565";
const WADAH = "5108060006000224";
const T1 = "5108010002000101"; // 60 dokumen -> 2 rombongan
const T2 = "5108020003000203"; // satu anggota dipindah pihak lain tepat sebelum dikirim (REGION_SAMA)
const T3 = "5108030001000101"; // masih Listing Selesai
const T4 = "5108040001000101"; // 2 PPL
const T5 = "5108050001000101"; // PUT pertama 429 (tidak diterapkan) -> kirim ulang
const T6 = "5108060001000101"; // PUT pertama 504 TAPI diterapkan -> tidak dikirim ulang
const LAIN = "5108070001000101";
const TUJUAN_ADA = [T1, T2, T3, T4, T5, T6];

let seq = 0;
const uuid = () => { seq++; const h = seq.toString(16).padStart(12, "0"); return `${h.slice(4, 12)}-0000-4000-8000-${h}`; };
const regionCamel = (kode) => ({ id: "r", groupId: GRUP, level1: { fullCode: "51", level2: { fullCode: "5108",
  level3: { fullCode: kode.slice(0, 7), level4: { fullCode: kode.slice(0, 10), level5: { fullCode: kode.slice(0, 14),
    level6: { fullCode: kode } } } } } } });
const regionSnake = (kode) => ({ _id: "r", group_id: GRUP, level_1: { full_code: "51", level_2: { full_code: "5108",
  level_3: { full_code: kode.slice(0, 7), level_4: { full_code: kode.slice(0, 10), level_5: { full_code: kode.slice(0, 14),
    level_6: { full_code: kode, level_7: null } } } } } } });

// ---------------------------------------------------------------- server palsu
const jam = { now: Date.parse("2026-09-27T12:00:00.000Z") };
const server = {
  docs: new Map(), put: [], datatable: 0, detail: 0, gangguan: {}, abaikan: new Set(), lag: new Map(),
  sebelumPut: null,
};
let urut = 0;
function tambah(o) {
  const d = { id: uuid(), mode: "PAPI", alias: "APPROVED BY Pengawas", kode: WADAH, dibuat: Date.parse("2026-09-25T03:00:00.000Z"),
    nama: `USAHA ${seq}`, hapus: false, urut: urut++, ...o };
  server.docs.set(d.id, d);
  return d;
}
// 1.300 dokumen pengisi: 1.100 dibuat dalam SATU jam (jendela harus dibelah) + 200 menyebar
for (let i = 0; i < 1100; i++) tambah({ dibuat: Date.parse("2026-09-24T02:00:00.000Z") + i * 3000, kode: "5108090001000101" });
for (let i = 0; i < 200; i++) tambah({ dibuat: Date.parse("2026-09-15T00:00:00.000Z") + i * 3600000, kode: "5108090002000101" });

const target = [];
const T = (o, dokO) => {
  const d = dokO === null ? null : tambah({ ...dokO });
  const t = { k: `k${target.length}`, s: 0, b: target.length + 2, n: (d && d.namaSheet) || (d ? d.nama : "X"), t: o.t, ids: d ? [d.id] : [], ...o };
  delete t.dok;
  target.push(t);
  return { t, d };
};
const grupT1 = [];
for (let i = 0; i < 60; i++) grupT1.push(T({ t: T1 }, {}));
const bohong = grupT1[10].d;                                  // server bilang berhasil, dokumen ini tidak pindah (bukan sampel)
const belumApproved = T({ t: T1 }, { alias: "SUBMITTED BY Pencacah" });
const namaBeda = T({ t: T1, n: "NAMA DI SHEET (X)" }, { nama: "NAMA DI SERVER (Y)" });
const namaLama = T({ t: T1, n: "NAMA BARU (X)", na: ["NAMA LAMA (X)"] }, { nama: "NAMA LAMA (X)" });
const terhapus = tambah({ hapus: true });
const duaId = T({ t: T1 }, {});
duaId.t.ids = [terhapus.id, duaId.d.id].sort();
const gandaB = tambah({});
const ganda = T({ t: T1 }, {});
ganda.t.ids = [ganda.d.id, gandaB.id].sort();
gandaB.nama = ganda.d.nama;
const capi = T({ t: T1 }, { mode: "CAPI" });                  // tidak ada di daftar PAPI -> detail cadangan
const yatimWadah = [tambah({}), tambah({ alias: "SUBMITTED BY Pencacah" })];   // di wadah, bukan target -> sisaWadah
const subslsLain = T({ t: T1 }, { kode: LAIN });
const sudah = T({ t: T2 }, { kode: T2 });
const grupT2 = [];
for (let i = 0; i < 4; i++) grupT2.push(T({ t: T2 }, {}));
const diserobot = grupT2[1].d;
const grupT3 = [T({ t: T3 }, {}), T({ t: T3 }, {})];
const grupT4 = [T({ t: T4 }, {})];
const grupT5 = [T({ t: T5 }, {}), T({ t: T5 }, {}), T({ t: T5 }, {})];
const grupT6 = [T({ t: T6 }, {}), T({ t: T6 }, {})];

const itemDt = (d) => ({ id: d.id, codeIdentity: `${WADAH} - ${d.nama}`, data1: d.nama, assignmentStatusAlias: d.alias,
  currentUserUsername: "pml@x", mode: [d.mode], region: regionCamel(server.lag.has(d.id) ? server.lag.get(d.id) : d.kode) });
const json = (status, obj, retryAfter) => ({ status, text: async () => (typeof obj === "string" ? obj : JSON.stringify(obj)),
  headers: { get: (h) => (h === "Retry-After" ? retryAfter || null : null) } });

async function fetchPalsu(url, init) {
  const u = new URL(url, "https://fasih-sm.bps.go.id");
  const p = u.pathname.replace(/^\/app\/api/, "");
  const q = Object.fromEntries(u.searchParams);
  const body = init && init.body ? JSON.parse(init.body) : null;
  if (!init.headers["X-XSRF-TOKEN"]) return json(403, "Invalid CSRF Token");
  if (server.sesiMati) return json(401, "Unauthorized");
  if (p === "/survey/api/v1/survey-roles") {
    return json(200, { success: true, data: [
      { id: "r-ppl", sequence: 8, isPencacah: true, surveyRoleGroup: { name: "Petugas" } },
      { id: "r-pml", sequence: 7, isPencacah: false, surveyRoleGroup: { name: "Petugas" } },
      { id: "r-adm", sequence: 1, isPencacah: false, surveyRoleGroup: { name: "Admin" } }] });
  }
  if (p === "/analytic/api/v2/assignment/datatable-all-user-survey-periode") {
    server.datatable++;
    if (body.length > 150) return json(400, { message: "Length restricted to 150" });
    const x = body.assignmentExtraParam;
    const semua = [...server.docs.values()].filter((d) => !d.hapus && (!x.mode || x.mode.includes(d.mode))
      && (!x.dateCreatedFrom || d.dibuat >= Date.parse(x.dateCreatedFrom))
      && (!x.dateCreatedTo || d.dibuat <= Date.parse(x.dateCreatedTo))).sort((a, b) => a.urut - b.urut);
    // batas server asli: start + length > 1000 -> kosong
    const hal = body.start + body.length > 1000 ? [] : semua.slice(body.start, body.start + body.length);
    return json(200, { searchData: hal.map(itemDt), totalHit: semua.length });
  }
  if (p === "/assignment-general/api/assignment/get-by-assignment-id") {
    server.detail++;
    const d = server.docs.get(q.assignmentId);
    if (!d || d.hapus) return json(403, "");
    return json(200, { success: true, data: { code_identity: `${WADAH} - ${d.nama}`, assignment_status_alias: d.alias,
      current_user_username: "pml@x", region: regionSnake(d.kode) } });
  }
  if (p === "/assignment-general/api/assignment-region/datatable") {
    const kode = body.search.value;
    const data = TUJUAN_ADA.includes(kode) ? [{ smallestRegionFullCode: kode, doneListing: kode === T3, regionGroupId: GRUP }] : [];
    return json(200, { data, recordsTotal: data.length });
  }
  if (p === "/survey-user/api/v1/user-region/region") {
    const kode = q.regionCode;
    if (q.surveyRoleId === "r-pml") {
      return json(200, { success: true, data: [{ id: `ur-pml-${kode}`, allocationId: `al-pml-${kode}`, smallestRegionCode: kode, email: `pml.${kode.slice(-4)}@x`, active: true }] });
    }
    const ppl = [{ id: `ur-ppl-${kode}`, allocationId: `al-ppl-${kode}`, parentAllocationId: q.parentAllocationId, smallestRegionCode: kode, email: `ppl.${kode.slice(-4)}@x` }];
    if (kode === T4) ppl.push({ ...ppl[0], id: "ur-ppl-2", allocationId: "al-ppl-2", email: "ppl.dua@x" });
    return json(200, { success: true, data: ppl });
  }
  if (p === "/assignment-general/api/assignment/update-region-bulk" && init.method === "PUT") {
    server.put.push(body);
    if (server.sebelumPut) server.sebelumPut(body);
    const g = (server.gangguan[body.smallestLevelFullCode] || []).shift();
    const docs = body.assignmentIds.map((id) => server.docs.get(id));
    if (!g && docs.some((d) => d.kode === body.smallestLevelFullCode)) {
      return json(400, { success: false, message: "Region baru sama dengan region saat ini untuk assignment X, tidak ada perubahan", errorCode: 5 });
    }
    if (!g || g.terapkan) for (const d of docs) if (!server.abaikan.has(d.id)) d.kode = body.smallestLevelFullCode;
    if (g) return json(g.status, g.status === 504 ? "<html>504 Gateway Time-out</html>" : { error: "RATE_LIMIT_EXCEEDED" });
    return json(200, { success: true, message: "Berhasil", data: { updatedCount: body.assignmentIds.length, newRegionFullCode: body.smallestLevelFullCode } });
  }
  return json(404, { message: `tidak dikenal ${p}` });
}

// ---------------------------------------------------------------- browser palsu
class JamDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(jam.now); }
  static now() { return jam.now; }
}
const log = [];
const penyimpanan = new Map();
const unduhan = [];
const blobs = new Map();
let jawabPrompt = "YA";
const sandbox = {
  console: { log: (...a) => log.push(a.filter((x) => !String(x).startsWith("color:")).join(" ")), table: () => {}, error: (...a) => log.push(`ERR ${a.join(" ")}`) },
  Date: JamDate,
  setTimeout: (fn, ms) => { jam.now += Math.max(0, ms || 0); setImmediate(fn); },
  fetch: fetchPalsu,
  localStorage: { getItem: (k) => (penyimpanan.has(k) ? penyimpanan.get(k) : null), setItem: (k, v) => penyimpanan.set(k, String(v)), removeItem: (k) => penyimpanan.delete(k) },
  location: { host: "fasih-sm.bps.go.id", pathname: `/app/surveys/${SURVEI}/${PERIODE}/data` },
  document: { cookie: "XSRF-TOKEN=abc%3D", body: { appendChild: () => {} },
    createElement: () => ({ click() { unduhan.push({ nama: this.download, isi: blobs.get(this.href) }); }, remove() {} }) },
  Blob: class { constructor(bagian) { this.isi = bagian.join(""); } },
  URL: { createObjectURL: (b) => { const k = `blob:${blobs.size}`; blobs.set(k, b.isi); return k; } },
  prompt: () => jawabPrompt,
  confirm: () => true,
};
sandbox.window = sandbox;

let teks = fs.readFileSync(path.join(__dirname, "..", "fasih_sm", "pindah_wilayah", "pindah_wilayah_console.js"), "utf8");
teks = teks.replace("/*__TARGET__*/[]", JSON.stringify(target)).replace("/*__SUMBER__*/[]", JSON.stringify(["uji.xlsx"]))
  .replace("/*__ASAL__*/[]", JSON.stringify([WADAH]))
  .replace("/*__KONFIG__*/{}", JSON.stringify({ bagian: "1/2", dibuat: "uji", opsi: { perKirim: 50, cekSesudah: 3 } }));
vm.createContext(sandbox);
vm.runInContext(teks, sandbox);
const pw = sandbox.pindahWilayah;
const hasil = () => JSON.parse(penyimpanan.get("pindahWilayah.hasil.v2") || "{}");
const st = (x) => (hasil()[`uji.xlsx|${x.t.k}`] || {}).st;
const hitungStatus = () => {
  const c = {};
  for (const t of target) { const s = (hasil()[`uji.xlsx|${t.k}`] || {}).st || "-"; c[s] = (c[s] || 0) + 1; }
  return c;
};

(async () => {
  check("siap: target & bagian", [pw.target.length, pw.konfig.bagian], [target.length, "1/2"]);

  // ---------------- PERIKSA (read-only)
  await pw.jalankan({ mode: "periksa" });
  check("periksa: tidak ada PUT", server.put.length, 0);
  const papi = [...server.docs.values()].filter((d) => !d.hapus && d.mode === "PAPI").length;
  check("periksa: seluruh daftar PAPI terbaca (jendela > 900 dibelah)", log.some((l) => l.includes(`Daftar terbaca: ${papi}/${papi} dokumen`)), true);
  const jendela = JSON.parse(penyimpanan.get("pindahWilayah.jendela.v1"));
  check("periksa: batas jendela disimpan, tiap jendela <= 900", jendela.jendela.every((j) => j[2] <= 900) && jendela.jendela.length > 1, true);
  check("periksa: status tiap jenis target", [st(grupT1[0]), st(belumApproved), st(namaBeda), st(namaLama), st(duaId), st(ganda), st(capi),
    st(subslsLain), st(sudah), st(grupT3[0]), st(grupT4[0]), st(grupT5[0])],
  ["SIAP_PINDAH", "BELUM_APPROVED", "NAMA_TIDAK_COCOK", "SIAP_PINDAH", "SIAP_PINDAH", "DOKUMEN_GANDA", "SIAP_PINDAH",
    "DI_SUBSLS_LAIN", "SUDAH_DI_TUJUAN", "TUJUAN_BELUM_DIBUKA", "PETUGAS_TUJUAN_GANDA", "SIAP_PINDAH"]);
  check("periksa: daftar tujuan belum dibuka", pw.daftarTujuan("TUJUAN_BELUM_DIBUKA"), T3);
  const dtAwal = server.datatable;
  const idTarget = new Set(pw.target.flatMap((t) => t.ids || []));
  const sisa = pw.sisaWadah(undefined, { unduh: false });
  const harapSisa = [...server.docs.values()].filter((d) => !d.hapus && d.mode === "PAPI" && pw.asal.includes(d.kode) && !idTarget.has(d.id)).length;
  check("sisaWadah: dokumen wadah bukan target, tanpa request", [sisa.length, sisa.every((d) => !idTarget.has(d.id)), server.datatable],
    [harapSisa, true, dtAwal]);
  check("sisaWadah: memuat dokumen yatim di wadah", yatimWadah.every((y) => sisa.some((d) => d.id === y.id)), true);

  // ---------------- PINDAH tanpa YA -> batal (tanpa gerbang "limit 1 dulu")
  jawabPrompt = "tidak";
  await pw.jalankan({ mode: "pindah" });
  check("tanpa YA -> batal", [server.put.length, log.some((l) => l.includes("butuh minimal 1 DIPINDAH_TERVERIFIKASI"))], [0, false]);
  check("pindah memakai daftar yang masih segar (tanpa baca ulang)", server.datatable, dtAwal);

  // ---------------- PINDAH limit 1
  jawabPrompt = "YA";
  await pw.jalankan({ mode: "pindah", limit: 1 });
  check("limit 1: satu PUT berisi 1 dokumen ke T1", server.put.map((b) => [b.smallestLevelFullCode, b.assignmentIds.length]), [[T1, 1]]);
  check("limit 1: body petugas & grup", [server.put[0].groupId, server.put[0].userRegionIds], [GRUP, [`ur-pml-${T1}`, `ur-ppl-${T1}`]]);
  check("limit 1: DIPINDAH_TERVERIFIKASI", st(grupT1[0]), "DIPINDAH_TERVERIFIKASI");

  // ---------------- PINDAH semua (gangguan disiapkan)
  server.abaikan.add(bohong.id);
  server.gangguan[T5] = [{ status: 429, terapkan: false }];
  server.gangguan[T6] = [{ status: 504, terapkan: true }];
  server.sebelumPut = (b) => { if (b.smallestLevelFullCode === T2 && diserobot.kode === WADAH) diserobot.kode = T2; };
  const putAwal = server.put.length;
  await pw.jalankan({ mode: "pindah" });
  const put = server.put.slice(putAwal).map((b) => [b.smallestLevelFullCode, b.assignmentIds.length]);
  check("pindah: rombongan per tujuan, <= 50, kirim ulang hanya yang masih di wadah", put,
    [[T1, 50], [T1, 12], [T2, 4], [T2, 3], [T5, 3], [T5, 3], [T6, 2]]);
  check("pindah: tidak ada PUT ke tujuan Listing Selesai / PPL ganda", server.put.some((b) => [T3, T4].includes(b.smallestLevelFullCode)), false);
  check("pindah: dokumen tidak SIAP tidak pernah dikirim",
    server.put.flatMap((b) => b.assignmentIds).filter((id) => [belumApproved, namaBeda, ganda, subslsLain, sudah].some((x) => x.d.id === id)).length, 0);
  check("pindah: dokumen terhapus tidak dikirim, pasangannya dikirim",
    [server.put.flatMap((b) => b.assignmentIds).includes(terhapus.id), server.put.flatMap((b) => b.assignmentIds).includes(duaId.d.id)], [false, true]);
  check("REGION_SAMA: dokumen yang diserobot -> SUDAH_DI_TUJUAN, sisanya dipindah", [st(grupT2[1]), st(grupT2[0]), grupT2.map((x) => x.d.kode)],
    ["SUDAH_DI_TUJUAN", "DIPINDAH_TERVERIFIKASI", [T2, T2, T2, T2]]);
  check("429 tidak diterapkan -> dikirim ulang lalu pindah", grupT5.map((x) => [x.d.kode, st(x)]),
    grupT5.map(() => [T5, "DIPINDAH_TERVERIFIKASI"]));
  check("504 tapi diterapkan -> terverifikasi lewat detail, tidak dikirim ulang", grupT6.map((x) => [x.d.kode, st(x)]),
    grupT6.map(() => [T6, "DIPINDAH_TERVERIFIKASI"]));
  check("rombongan 50: 3 sampel terverifikasi, sisanya SERVER_OK",
    grupT1.slice(1, 51).map(st).filter((s) => s === "DIPINDAH_TERVERIFIKASI").length, 3);
  check("dokumen CAPI (detail cadangan) & nama lama ikut pindah", [capi.d.kode, namaLama.d.kode, duaId.d.kode], [T1, T1, T1]);
  check("pencacah & pengawas tujuan tercatat", [hasil()[`uji.xlsx|${grupT1[5].t.k}`].pc, hasil()[`uji.xlsx|${grupT1[5].t.k}`].pw],
    [`ppl.${T1.slice(-4)}@x`, `pml.${T1.slice(-4)}@x`]);

  // ---------------- PERIKSA ulang: indeks daftar terlambat utk 2 dokumen + 1 dokumen yang server "bohongi"
  server.lag.set(grupT1[40].d.id, WADAH);
  server.lag.set(grupT1[41].d.id, WADAH);
  const dtSebelum = server.datatable;
  const detailSebelum = server.detail;
  await pw.jalankan({ mode: "periksa" });
  check("periksa ulang memakai jendela tersimpan (lebih sedikit request daftar)", server.datatable - dtSebelum < dtAwal, true);
  check("indeks terlambat -> dicek lewat detail -> TERVERIFIKASI", [st(grupT1[40]), st(grupT1[41])], ["DIPINDAH_TERVERIFIKASI", "DIPINDAH_TERVERIFIKASI"]);
  check("server bilang berhasil tapi dokumen tidak pindah -> BELUM_TERVERIFIKASI", [bohong.kode, st(grupT1[10])], [WADAH, "DIPINDAH_BELUM_TERVERIFIKASI"]);
  check("detail hanya utk yang perlu (bukan semua dokumen)", server.detail - detailSebelum < 10, true);
  const c = hitungStatus();
  check("periksa ulang: semua yang dipindah kini TERVERIFIKASI", [c.DIPINDAH_TERVERIFIKASI, c.DIPINDAH_SERVER_OK || 0],
    [63 - 1 + 3 + 3 + 2, 0]);

  // ---------------- pindah lagi: hanya yang BELUM_TERVERIFIKASI (dokumen bohong) yang dikirim
  server.abaikan.clear();
  const putSebelum = server.put.length;
  await pw.jalankan({ mode: "pindah" });
  check("pindah ulang: hanya dokumen yang belum pindah", server.put.slice(putSebelum).map((b) => b.assignmentIds), [[bohong.id]]);
  check("pindah ulang: kini terverifikasi", [bohong.kode, st(grupT1[10])], [T1, "DIPINDAH_TERVERIFIKASI"]);

  // ---------------- unduh
  pw.unduh();
  const csv = unduhan[unduhan.length - 1];
  const baris = csv.isi.replace(/^﻿/, "").split("\n");
  check("unduh: nama berkas memuat bagian", /^audit_pindah_wilayah_bagian-1-dari-2_\d{8}-\d{6}\.csv$/.test(csv.nama), true);
  check("unduh: kolom", baris[0], "waktu,jalan,bagian,sumber,baris,kunci,nama,ids,id,status_server,asal,tujuan,status,pengawas,pencacah,pesan");
  check("unduh: satu baris per target", baris.length - 1, target.length);
  const dua = baris.find((b) => b.includes(`"${duaId.t.k}"`));
  check("unduh: kolom ids memuat kedua ID target", dua.includes(duaId.t.ids.join(";")), true);

  // ---------------- sesi habis: berhenti rapi, tidak ada yang ditulis
  server.sesiMati = true;
  const putSesi = server.put.length;
  await pw.jalankan({ mode: "pindah", pindaiUlang: true });
  check("sesi habis -> SESI_DITOLAK, tanpa PUT", [log.some((l) => l.includes("⛔ SESI_DITOLAK")), server.put.length], [true, putSesi]);
  server.sesiMati = false;

  const semuaHasil = JSON.parse(penyimpanan.get("pindahWilayah.hasil.v2"));
  check("hasil tersimpan ringkas (tanpa kolom kosong)", Object.values(semuaHasil).every((h) => !Object.values(h).some((v) => v === "")), true);
  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  if (!okAll) console.log(log.slice(-40).join("\n"));
  process.exit(okAll ? 0 : 1);
})().catch((e) => { console.error(e); console.log(log.slice(-40).join("\n")); process.exit(1); });
