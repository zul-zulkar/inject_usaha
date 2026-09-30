// Uji approve_capi_console.js — logika murni + simulasi alur browser thd server fasih-sm PALSU (jam virtual).
// Jalankan: node tests/test_approve_capi_console.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const BERKAS = path.join(__dirname, "..", "approve_capi", "approve_capi_console.js");
const m = require(BERKAS);

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const SURVEI = "a0429e96-51a5-477b-a415-485f9c153004";
const PERIODE = "fd68e454-ba45-4b85-8205-f3bf777ded24";
const SUB = m.SUBMITTED;

// ---------------- logika murni
check("mode dari array", m.modeDari({ mode: ["CAPI"] }), "CAPI");
check("mode dari string snake", m.modeDari({ assignment_mode: "papi" }), "PAPI");
check("body: saring SUBMITTED + CAPI", m.bodyDaftar("p", 0, 150, "a", "b", "CAPI").assignmentExtraParam,
  { surveyPeriodId: "p", assignmentErrorStatusType: -1, assignmentStatusAlias: SUB, mode: ["CAPI"], dateCreatedFrom: "a", dateCreatedTo: "b" });
check("body: status null = semua", m.bodyDaftar("p", 0, 150, null, null, null, "K", null).assignmentExtraParam.assignmentStatusAlias, null);
const k = (o) => ({ id: "x", kode: "K", nama: "", pml: "pml.satu@x.id", peran: "Pengawas", alias: SUB, mode: "CAPI", ...o });
check("kandidat SIAP", m.putuskanKandidat(k(), ["pml.satu@x.id"], {}).status, "SIAP");
check("kandidat tanpa PML", m.putuskanKandidat(k({ pml: "" }), [], {}).status, "TANPA_PML");
check("kandidat dipegang Pencacah", m.putuskanKandidat(k({ peran: "Pencacah" }), [], {}).status, "TANPA_PML");
check("kandidat PML di luar daftar", m.putuskanKandidat(k({ pml: "lain@x.id" }), ["pml.satu@x.id"], {}).status, "PML_TIDAK_DI_DAFTAR");
check("daftar kosong = semua PML", m.putuskanKandidat(k({ pml: "lain@x.id" }), [], {}).status, "SIAP");
check("sudah diproses", m.putuskanKandidat(k(), [], { x: { status: m.ST.PAPI_OK } }).status, "SUDAH_DIPROSES");
const det = (o) => ({ ada: true, alias: SUB, mode: "CAPI", pml: "", kode: "", nama: "", pesan: "", ...o });
check("sebelum PAPI: boleh", m.cegahSebelum(det(), "PAPI"), null);
check("sebelum PAPI: bukan SUBMITTED", m.cegahSebelum(det({ alias: "APPROVED BY Pengawas" }), "PAPI").status, "BUKAN_SUBMITTED");
check("sebelum PAPI: sudah PAPI", m.cegahSebelum(det({ mode: "PAPI" }), "PAPI").status, "SUDAH_PAPI");
check("sebelum CAPI: belum approved", m.cegahSebelum(det({ mode: "PAPI" }), "CAPI").status, "BELUM_APPROVED");
check("sebelum CAPI: belum approved + termasukBelumApproved", m.cegahSebelum(det({ mode: "PAPI" }), "CAPI", { termasukBelumApproved: true }), null);
check("sebelum CAPI: approved", m.cegahSebelum(det({ mode: "PAPI", alias: "APPROVED BY Pengawas" }), "CAPI"), null);
const csv = m.keCsv([{ id: "a", nama: 'X "Y", Z', status: m.ST.PAPI_OK, pml: "p@x" }]);
check("CSV bolak-balik", m.dariCsv(csv).a, { kode: "", nama: 'X "Y", Z', pml: "p@x", status: m.ST.PAPI_OK, statusDok: "",
  mode: "", diganti: "", dikembalikan: "", pesan: "" });
const siapContoh = [k({ id: "x1" }), k({ id: "x2", pml: "pml.dua@x.id" }), k({ id: "x3" }), k({ id: "x4" }), k({ id: "x5" })];
const tersimpan = m.uraiDaftar(JSON.parse(JSON.stringify(m.padatDaftar(siapContoh, "2026-09-30T01:00:00.000Z"))));
check("daftar tersimpan: bolak-balik id + PML", tersimpan.kandidat.map((x) => `${x.id}:${x.pml}`),
  ["x1:pml.satu@x.id", "x2:pml.dua@x.id", "x3:pml.satu@x.id", "x4:pml.satu@x.id", "x5:pml.satu@x.id"]);
check("daftar tersimpan: rusak -> null", m.uraiDaftar({ waktu: "x" }), null);
check("sisa tersimpan: diproses/gugur/PML luar dibuang, DIKIRIM & gagal sementara tetap",
  m.sisaTersimpan(tersimpan.kandidat, ["pml.satu@x.id"], { x1: { status: m.ST.PAPI_OK }, x3: { status: m.ST.PAPI_KIRIM },
    x4: { pesan: "BUKAN_SUBMITTED: status APPROVED BY Pengawas" }, x5: { status: "", pesan: "SERVER_SIBUK: ..." } }).map((x) => x.id),
  ["x3", "x5"]);

// laju adaptif & jeda ulang (dipersingkat 2026-09-30)
check("faktor: 429 x2 (maks 8), sukses x0,9 (min 1), 404 tetap", [m.faktorBaru(1, 429), m.faktorBaru(8, 503), m.faktorBaru(2, 200),
  m.faktorBaru(1, 200), m.faktorBaru(3, 404)], [2, 8, 1.8, 1, 3]);
check("jeda ulang: 5,10,20,40,60,60 dtk", [0, 1, 2, 3, 4, 7].map((k) => m.jedaUlang(k)), [5000, 10000, 20000, 40000, 60000, 60000]);
check("jeda ulang: Retry-After dihormati (min 3 dtk)", [m.jedaUlang(0, "1"), m.jedaUlang(0, "12")], [3000, 12000]);

// bagian Console & catatan ringkas
check("bagian: 2/4", m.uraiBagian("2/4"), { k: 2, n: 4 });
check("bagian: label beda dgn LABEL --bagi", m.labelTab({ k: 2, n: 4 }), ".tab-2-dari-4");
check("bentrok: bagian sama / n beda / tanpa bagian", [m.bentrokBagian(["2/4"], { k: 1, n: 4 }), /sudah berjalan/.test(m.bentrokBagian(["1/4"], { k: 1, n: 4 })),
  /jumlah bagian yang sama/.test(m.bentrokBagian(["1/3"], { k: 1, n: 4 })), /k\/4/.test(m.bentrokBagian(["1/4"], null))], ["", true, true, true]);
const D = "approveCapi.hasil.v1";
check("kunci milik berkas: dasar + tab, bukan LABEL --bagi lain",
  m.kunciMilik([D, `${D}.tab-1-dari-4`, `${D}.bagian-1-dari-5`, `${D}.bagian-1-dari-5.tab-2-dari-4`, "lain"], D), [D, `${D}.tab-1-dari-4`]);
check("kunci milik berkas --bagi", m.kunciMilik([D, `${D}.bagian-1-dari-5`, `${D}.bagian-1-dari-5.tab-2-dari-4`], `${D}.bagian-1-dari-5`),
  [`${D}.bagian-1-dari-5`, `${D}.bagian-1-dari-5.tab-2-dari-4`]);
const rOk = { kode: "5108060006000224 - WARUNG X (I MADE)", nama: "WARUNG X (I MADE)", pml: "pml.satu@x.id", status: m.ST.PAPI_OK,
  statusDok: SUB, mode: "PAPI", diganti: "2026-09-30T02:00:00.000Z", dikembalikan: "", pesan: "", waktu: "2026-09-30T02:00:01.000Z" };
check("catatan ringkas: PAPI_OK tanpa kode (id cukup), sisanya bolak-balik", m.uraiRekam(m.padatRekam(rOk)),
  { ...rOk, kode: "", nama: "" });
check("catatan ringkas: anomali tetap bawa kode", m.uraiRekam(m.padatRekam({ ...rOk, status: "", pesan: "GANTI_DITOLAK: x" })).kode, rOk.kode);
check("catatan ringkas: < 40% panjang lama", JSON.stringify(m.padatRekam(rOk)).length < 0.4 * JSON.stringify(rOk).length, true);
check("catatan format lama terbaca", m.uraiRekam({ status: m.ST.CAPI_OK, pml: "p@x", kode: "K" }).status, m.ST.CAPI_OK);
check("gabung hasil: waktu terbaru menang, lintas kunci",
  Object.fromEntries(Object.entries(m.gabungHasil([{ a: m.padatRekam({ ...rOk, waktu: "2026-09-30T03:00:00.000Z" }), b: m.padatRekam(rOk) },
    { a: m.padatRekam({ ...rOk, status: m.ST.CAPI_OK, waktu: "2026-09-30T01:00:00.000Z" }), b: m.padatRekam({ ...rOk, status: m.ST.CAPI_OK }) }]))
    .map(([id, r]) => [id, r.status])), { a: m.ST.PAPI_OK, b: m.ST.CAPI_OK });

// ---------------- simulasi browser
const jam = { now: Date.parse("2026-09-29T02:00:00.000Z") };
const PML = ["pml.satu@x.id", "pml.dua@x.id"];
const server = { docs: new Map(), gantiDitolak: new Set(), gantiLog: [], gangguan: [429],
  sesiHabis: false, habisSesudahGanti: "", bacaDaftarCapi: 0, pulihSetelahMs: null, sesiHabisSejak: 0,
  tolak429: new Map(), selalu503: new Set() };
const tambah = (id, o) => server.docs.set(id, { id, kode: `5108060006000224 - USAHA ${id}`, alias: SUB, mode: "CAPI",
  pml: PML[0], peran: "Pengawas", dibuat: Date.parse("2026-09-20T00:00:00.000Z") + server.docs.size * 60000, ...o });
for (let i = 0; i < 5; i++) tambah(`c${i}`, {});
tambah("d0", { pml: PML[1] });
tambah("e0", { pml: "orang.lain@x.id" });
tambah("f0", { pml: "ppl@x.id", peran: "Pencacah" });
tambah("p0", { mode: "PAPI" });                                 // aslinya PAPI -> tidak pernah disentuh
tambah("s0", { alias: "APPROVED BY Pengawas" });                // CAPI approved -> bukan target

const json = (status, obj, retryAfter) => ({ status, text: async () => (typeof obj === "string" ? obj : JSON.stringify(obj)),
  headers: { get: (h) => (h === "Retry-After" ? retryAfter || null : null) } });
async function fetchPalsu(url, init) {
  const u = new URL(url, "https://fasih-sm.bps.go.id");
  const p = u.pathname.replace(/^\/app\/api/, "");
  if (!init.headers["X-XSRF-TOKEN"]) return json(403, "Invalid CSRF Token");
  if (server.sesiHabis) {
    if (server.pulihSetelahMs != null && jam.now - server.sesiHabisSejak >= server.pulihSetelahMs) server.sesiHabis = false;
    else return json(401, "");
  }
  if (p === "/analytic/api/v2/assignment/datatable-all-user-survey-periode") {
    const g = server.gangguan.shift();
    if (g) return json(g, { error: "RATE_LIMIT_EXCEEDED" });
    const b = JSON.parse(init.body);
    const x = b.assignmentExtraParam;
    if (x.mode && x.mode.includes("CAPI") && !b.search.value) server.bacaDaftarCapi++;
    const semua = [...server.docs.values()].filter((d) => (!x.mode || x.mode.includes(d.mode)) && (!x.assignmentStatusAlias || d.alias === x.assignmentStatusAlias)
      && (!x.dateCreatedFrom || d.dibuat >= Date.parse(x.dateCreatedFrom)) && (!x.dateCreatedTo || d.dibuat <= Date.parse(x.dateCreatedTo))
      && (!b.search.value || d.kode.includes(b.search.value)));
    return json(200, { totalHit: semua.length, searchData: semua.slice(b.start, b.start + b.length).map((d) => ({ id: d.id,
      codeIdentity: d.kode, data1: `USAHA ${d.id}`, assignmentStatusAlias: d.alias, mode: [d.mode], currentUserUsername: d.pml,
      currentUserSurveyRoleName: d.peran, dateCreated: new Date(d.dibuat).toISOString() })) });
  }
  if (p === "/assignment-general/api/assignment/get-by-assignment-id") {
    const d = server.docs.get(u.searchParams.get("assignmentId"));
    if (!d) return json(403, "");
    // detail asli belum terbukti memuat mode -> sebagian dokumen TANPA mode (cadangan tabel Data diuji)
    const data = { code_identity: d.kode, data1: `USAHA ${d.id}`, assignment_status_alias: d.alias, current_user_username: d.pml };
    if (d.id !== "c1") data.mode = [d.mode];
    return json(200, { success: true, data });
  }
  const mg = /^\/assignment-submit\/api\/assignment\/([^/]+)\/change-mode$/.exec(p);
  if (mg && init.method === "POST") {
    const d = server.docs.get(mg[1]);
    const ke = JSON.parse(init.body).modes[0];
    server.gantiLog.push(`${mg[1]}>${ke}`);
    if ((server.tolak429.get(mg[1]) || 0) > 0) {
      server.tolak429.set(mg[1], server.tolak429.get(mg[1]) - 1);
      return json(429, { error: "RATE_LIMIT_EXCEEDED" });
    }
    if (server.selalu503.has(mg[1])) return json(503, "Service Unavailable");
    if (server.gantiDitolak.has(mg[1])) return json(200, { success: false, message: "Tidak bisa ganti mode" });
    d.mode = ke;
    if (server.habisSesudahGanti === mg[1]) { server.sesiHabis = true; server.sesiHabisSejak = jam.now; } // sesi habis tepat sesudah change-mode diterapkan
    return json(200, { success: true, message: "Berhasil. " });
  }
  return json(404, {});
}
class JamDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(jam.now); }
  static now() { return jam.now; }
}
const log = [];
const unduhan = [];
const blobs = new Map();
const penyimpanan = new Map();
const jawabPrompt = [];
function buatTab() {
  const sandbox = {
    console: { log: (...a) => log.push(a.filter((x) => !String(x).startsWith("color:")).join(" ")), table: () => {}, error: (...a) => log.push(`ERR ${a.join(" ")}`) },
    Date: JamDate,
    setTimeout: (fn, ms) => { jam.now += Math.max(0, ms || 0); setImmediate(fn); },
    fetch: fetchPalsu,
    prompt: () => jawabPrompt.shift() || "",
    localStorage: { getItem: (k) => (penyimpanan.has(k) ? penyimpanan.get(k) : null), setItem: (k, v) => penyimpanan.set(k, String(v)),
      get length() { return penyimpanan.size; }, key: (i) => [...penyimpanan.keys()][i] ?? null },
    location: { host: "fasih-sm.bps.go.id", pathname: `/app/surveys/${SURVEI}/${PERIODE}/data` },
    document: { cookie: "XSRF-TOKEN=abc%3D", body: { appendChild: () => {} },
      createElement: () => ({ click() { unduhan.push({ nama: this.download, isi: blobs.get(this.href) }); }, remove() {} }) },
    Blob: class { constructor(bagian) { this.isi = bagian.join(""); } },
    URL: { createObjectURL: (b) => { const k2 = `blob:${blobs.size}`; blobs.set(k2, b.isi); return k2; } },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  const teks = fs.readFileSync(BERKAS, "utf8").replace("/*__DAFTAR_PML__*/[]", JSON.stringify(PML));
  vm.runInContext(teks, sandbox);
  return sandbox;
}
const sandbox = buatTab();
// catatan hasil semua kunci approveCapi.hasil.v1* (ringkas) -> {id: catatan lengkap}
const hasilGabung = () => m.gabungHasil([...penyimpanan.keys()].filter((x) => x.startsWith("approveCapi.hasil.v1"))
  .map((x) => JSON.parse(penyimpanan.get(x))));

(async () => {
  const a = sandbox.approveCapi;
  const p = await a.periksa();
  check("periksa: 8 CAPI SUBMITTED, 6 SIAP (2 PML daftar)", [p.terbaca, p.siap, p.per], [8, 6, { SIAP: 6, PML_TIDAK_DI_DAFTAR: 1, TANPA_PML: 1 }]);
  check("periksa read-only", server.gantiLog.length, 0);

  jawabPrompt.push("tidak");
  check("YA salah -> batal", [await a.kePapi(), server.gantiLog.length], [null, 0]);

  server.gantiDitolak.add("c3");
  jawabPrompt.push("YA");
  const r2 = await a.kePapi();
  check("tanpa gerbang limit 1, urut PML lalu kode, berhenti di GANTI_DITOLAK", [r2, server.gantiLog], [{ [m.ST.PAPI_OK]: 4, GANTI_DITOLAK: 1 }, ["d0>PAPI", "c0>PAPI", "c1>PAPI", "c2>PAPI", "c3>PAPI"]]);
  check("c1 (detail tanpa mode) terverifikasi lewat tabel Data", hasilGabung().c1.status, m.ST.PAPI_OK);
  server.gantiDitolak.clear();
  jawabPrompt.push("YA");
  const r3 = await a.kePapi();
  check("lanjutan: sisanya (c3 dicoba lagi, c4)", [r3, server.gantiLog.slice(5)], [{ [m.ST.PAPI_OK]: 2 }, ["c3>PAPI", "c4>PAPI"]]);
  check("dokumen di luar daftar/PAPI asli/approved tidak disentuh", ["e0", "f0", "p0", "s0"].map((i) => server.docs.get(i).mode), ["CAPI", "CAPI", "PAPI", "CAPI"]);

  a.unduh();
  const hasil = m.dariCsv(unduhan[0].isi);
  check("CSV: 6 dokumen DIGANTI_PAPI_TERVERIFIKASI", Object.values(hasil).filter((h) => h.status === m.ST.PAPI_OK).length, 6);

  // PML meng-approve sebagian
  for (const i of ["c0", "c1", "d0"]) server.docs.get(i).alias = "APPROVED BY Pengawas";
  server.docs.get("p0").alias = "APPROVED BY Pengawas";
  jawabPrompt.push("YA");
  const r6 = await a.keCapi();
  check("keCapi: approved dikembalikan, SUBMITTED dibiarkan PAPI", r6, { [m.ST.CAPI_OK]: 3, BELUM_APPROVED: 3 });
  check("mode akhir", ["c0", "c1", "d0", "c2", "p0"].map((i) => `${server.docs.get(i).mode}/${server.docs.get(i).alias.split(" ")[0]}`),
    ["CAPI/APPROVED", "CAPI/APPROVED", "CAPI/APPROVED", "PAPI/SUBMITTED", "PAPI/APPROVED"]);
  check("PAPI asli p0 tidak pernah diganti", server.gantiLog.filter((x) => x.startsWith("p0")).length, 0);

  // muatHasil di browser lain (localStorage kosong)
  penyimpanan.clear();
  a.muatHasil(unduhan[0].isi);
  check("muatHasil memulihkan catatan", Object.keys(JSON.parse(penyimpanan.get("approveCapi.hasil.v1"))).length, 6);

  sandbox.location.host = "contoh.lain";
  check("halaman salah ditolak", await a.periksa(), null);

  // sesi habis (401) di tengah kePapi -> tab dimuat ulang -> kePapi lagi: lanjut dari daftar tersimpan, tanpa baca ulang
  ["n0", "n1", "n2", "n3"].forEach((i) => tambah(i, {}));
  server.habisSesudahGanti = "n1";
  const tab1 = buatTab().approveCapi;
  const nKirim = server.gantiLog.length;
  jawabPrompt.push("YA");
  const rt1 = await tab1.kePapi({ tungguLoginMs: 0 }); // 0 = langsung berhenti (bawaan: tunggu tanpa batas)
  const hasilSkrg = hasilGabung;
  check("401: n0 selesai, n1 terkirim lalu sesi habis", [rt1, server.gantiLog.slice(nKirim)], [{ [m.ST.PAPI_OK]: 1 }, ["n0>PAPI", "n1>PAPI"]]);
  check("401: n1 tercatat DIKIRIM sebelum verifikasi", hasilSkrg().n1.status, m.ST.PAPI_KIRIM);
  check("401: pesan menyuruh lanjut tanpa menelusuri ulang", log.some((l) => l.includes("SESI_DITOLAK") && l.includes("tanpa menelusuri ulang")), true);
  server.sesiHabis = false;
  server.habisSesudahGanti = "";
  const tab2 = buatTab().approveCapi; // halaman dimuat ulang: kandidat di memori hilang
  const nBaca = server.bacaDaftarCapi;
  const nKirim2 = server.gantiLog.length;
  jawabPrompt.push("YA");
  const rt2 = await tab2.kePapi();
  check("lanjut: daftar CAPI TIDAK dibaca ulang", server.bacaDaftarCapi - nBaca, 0);
  check("lanjut: log melanjutkan", log.some((l) => l.includes("Melanjutkan daftar tersimpan") && l.includes("3 dari 4")), true);
  check("lanjut: n1 diakui PAPI_OK tanpa kirim ulang, n2/n3 diganti", [rt2, server.gantiLog.slice(nKirim2)],
    [{ [m.ST.PAPI_OK]: 3 }, ["n2>PAPI", "n3>PAPI"]]);
  check("lanjut: n1 ikut target approve (DIGANTI_PAPI_TERVERIFIKASI)", hasilSkrg().n1.status, m.ST.PAPI_OK);
  check("{telusurUlang: true} membaca ulang daftar CAPI (kandidat habis -> tanpa prompt)",
    [await tab2.kePapi({ telusurUlang: true }), server.bacaDaftarCapi - nBaca > 0], [{ diproses: 0 }, true]);
  check("prasyarat: antrean jawaban prompt kosong", jawabPrompt.length, 0);

  // 4 tab paralel kePapi({bagian}) — daftar CAPI dibaca SATU tab, tab lain menunggu & memakai hasilnya
  const dokP = Array.from({ length: 16 }, (_, i) => `p${String(i).padStart(2, "0")}`);
  dokP.forEach((i) => tambah(i, { pml: i < "p08" ? PML[0] : PML[1] }));
  const perBagian = [1, 2, 3, 4].map((k) => dokP.filter((i) => m.bagianDari(i, 4) === k).sort());
  check("prasyarat: tiap bagian punya dokumen", perBagian.every((x) => x.length > 0), true);
  const nLogBaca = log.filter((l) => l.includes("READ-ONLY: membaca CAPI")).length;
  const nKirimP = server.gantiLog.length;
  const tabs = [1, 2, 3, 4].map(() => buatTab().approveCapi);
  jawabPrompt.push("YA", "YA", "YA", "YA");
  const jalan = [tabs[0].kePapi({ bagian: "1/4" })];
  while (!JSON.parse(penyimpanan.get("approveCapi.membaca.v1") || "null")) await new Promise((r) => setImmediate(r));
  jalan.push(...[2, 3, 4].map((k) => tabs[k - 1].kePapi({ bagian: `${k}/4` })));
  const tabLain = buatTab().approveCapi;
  check("bagian yang sudah jalan ditolak", await tabLain.kePapi({ bagian: "3/4" }), null);
  check("tanpa bagian ditolak selama bagian lain jalan", await tabLain.keCapi(), null);
  const rp = await Promise.all(jalan);
  check("daftar CAPI hanya dibaca SATU tab", log.filter((l) => l.includes("READ-ONLY: membaca CAPI")).length - nLogBaca, 1);
  check("tab lain menunggu pembaca", log.some((l) => l.includes("Tab lain sedang membaca daftar CAPI")), true);
  check("4 bagian: tiap dokumen diganti tepat sekali", server.gantiLog.slice(nKirimP).map((g) => g.split(">")[0]).sort(), [...dokP].sort());
  check("4 bagian: jumlah per tab", rp.map((r) => r[m.ST.PAPI_OK]), perBagian.map((x) => x.length));
  check("4 bagian: tiap tab menulis ke kuncinya sendiri",
    [1, 2, 3, 4].map((k) => Object.keys(JSON.parse(penyimpanan.get(`approveCapi.hasil.v1.tab-${k}-dari-4`))).sort()), perBagian);
  check("tanda jalan & membaca dilepas", [JSON.parse(penyimpanan.get("approveCapi.jalan.v1")), JSON.parse(penyimpanan.get("approveCapi.membaca.v1"))], [{}, null]);
  const nUnduh = unduhan.length;
  tabs[1].unduh();
  const csvGabung = m.dariCsv(unduhan[nUnduh].isi);
  check("unduh() = gabungan semua bagian (bahan approve_capi.py)", dokP.every((i) => csvGabung[i] && csvGabung[i].status === m.ST.PAPI_OK), true);
  // PML meng-approve -> keCapi paralel per bagian
  dokP.forEach((i) => { server.docs.get(i).alias = "APPROVED BY Pengawas"; });
  jawabPrompt.push("YA", "YA", "YA", "YA");
  const rc = await Promise.all(tabs.map((t, i) => t.keCapi({ bagian: `${i + 1}/4` })));
  check("keCapi 4 bagian: semua kembali CAPI, tiap tab bagiannya", [dokP.every((i) => server.docs.get(i).mode === "CAPI"),
    rc.map((r) => r[m.ST.CAPI_OK])], [true, perBagian.map((x) => x.length)]);
  check("keCapi: status gabungan CAPI_OK", dokP.every((i) => hasilGabung()[i].status === m.ST.CAPI_OK), true);

  // 401 di tengah run, user login ulang di tab lain -> skrip menunggu & lanjut sendiri (tanpa jalankan ulang)
  ["q0", "q1", "q2"].forEach((i) => tambah(i, {}));
  server.habisSesudahGanti = "q0";
  server.pulihSetelahMs = 45 * 60 * 1000; // lebih lama dari batas lama 30 mnt: bawaan kini menunggu tanpa batas
  const tabQ = buatTab().approveCapi;
  const nKirimQ = server.gantiLog.length;
  jawabPrompt.push("YA");
  const rq = await tabQ.kePapi();
  check("401 lalu login ulang: TIDAK berhenti, semua selesai", [rq, server.gantiLog.slice(nKirimQ)],
    [{ [m.ST.PAPI_OK]: 3 }, ["q0>PAPI", "q1>PAPI", "q2>PAPI"]]);
  check("401: sinyal utk tab penjaga (userscript) ditulis", !!penyimpanan.get("fasihSesi.minta.v1"), true);
  check("401: petunjuk login di tab lain & 'sesi aktif lagi' dicetak",
    [log.some((l) => l.includes("Login ulang di TAB LAIN")), log.some((l) => l.includes("Sesi aktif lagi"))], [true, true]);
  server.habisSesudahGanti = "";
  server.pulihSetelahMs = null;

  // change-mode dijawab 429 -> cek status, kirim ulang (dulu: SERVER_SIBUK = seluruh batch berhenti)
  ["r0", "r1"].forEach((i) => tambah(i, {}));
  server.tolak429.set("r0", 2);
  const nKirimR = server.gantiLog.length;
  jawabPrompt.push("YA");
  const rr = await buatTab().approveCapi.kePapi();
  check("429 saat change-mode: dikirim ulang sampai berhasil, batch lanjut", [rr, server.gantiLog.slice(nKirimR)],
    [{ [m.ST.PAPI_OK]: 2 }, ["r0>PAPI", "r0>PAPI", "r0>PAPI", "r1>PAPI"]]);

  // server terus 503 utk satu dokumen -> ditunda ke akhir run, dicoba sekali lagi, batch TIDAK berhenti
  ["s1a", "s1b", "s1c"].forEach((i) => tambah(i, {}));
  server.selalu503.add("s1b");
  const nKirimS = server.gantiLog.length;
  jawabPrompt.push("YA");
  const rs = await buatTab().approveCapi.kePapi();
  check("SERVER_SIBUK: ditunda, dicoba lagi di akhir, dokumen lain jalan", [rs, server.gantiLog.slice(nKirimS)],
    [{ [m.ST.PAPI_OK]: 2, SERVER_SIBUK: 1 }, ["s1a>PAPI", "s1b>PAPI", "s1c>PAPI", "s1b>PAPI"]]);
  check("SERVER_SIBUK: tetap CAPI & tanpa status (dicoba lagi run berikut)", [server.docs.get("s1b").mode, hasilGabung().s1b.status], ["CAPI", ""]);
  // lanjutan tanpa baca ulang: hanya s1b (dokumen baru t* belum terlihat) -> t* butuh {telusurUlang: true}
  ["t0", "t1", "t2", "t3"].forEach((i) => { tambah(i, {}); server.selalu503.add(i); });
  const nKirimT = server.gantiLog.length;
  jawabPrompt.push("YA");
  await buatTab().approveCapi.kePapi();
  check("lanjutan: hanya sisa daftar tersimpan (s1b) yang dicoba", [...new Set(server.gantiLog.slice(nKirimT))], ["s1b>PAPI"]);
  // 3 dokumen sibuk berturut-turut -> berhenti (s1b, t0 ditunda; t1 = ke-3)
  const nKirimT2 = server.gantiLog.length;
  jawabPrompt.push("YA");
  await buatTab().approveCapi.kePapi({ telusurUlang: true });
  check("3 SERVER_SIBUK beruntun -> batch berhenti", [log.some((l) => l.includes("3 dokumen berturut-turut SERVER_SIBUK")),
    server.gantiLog.slice(nKirimT2)], [true, ["s1b>PAPI", "t0>PAPI", "t1>PAPI"]]);
  server.selalu503.clear();

  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  process.exit(okAll ? 0 : 1);
})();
