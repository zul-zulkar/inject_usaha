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

// ---------------- simulasi browser
const jam = { now: Date.parse("2026-09-29T02:00:00.000Z") };
const PML = ["pml.satu@x.id", "pml.dua@x.id"];
const server = { docs: new Map(), gantiDitolak: new Set(), gantiLog: [], gangguan: [429] };
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
  if (p === "/analytic/api/v2/assignment/datatable-all-user-survey-periode") {
    const g = server.gangguan.shift();
    if (g) return json(g, { error: "RATE_LIMIT_EXCEEDED" });
    const b = JSON.parse(init.body);
    const x = b.assignmentExtraParam;
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
    if (server.gantiDitolak.has(mg[1])) return json(200, { success: false, message: "Tidak bisa ganti mode" });
    d.mode = ke;
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
const sandbox = {
  console: { log: (...a) => log.push(a.filter((x) => !String(x).startsWith("color:")).join(" ")), table: () => {}, error: (...a) => log.push(`ERR ${a.join(" ")}`) },
  Date: JamDate,
  setTimeout: (fn, ms) => { jam.now += Math.max(0, ms || 0); setImmediate(fn); },
  fetch: fetchPalsu,
  prompt: () => jawabPrompt.shift() || "",
  localStorage: { getItem: (k) => (penyimpanan.has(k) ? penyimpanan.get(k) : null), setItem: (k, v) => penyimpanan.set(k, String(v)) },
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
  check("c1 (detail tanpa mode) terverifikasi lewat tabel Data", JSON.parse(penyimpanan.get("approveCapi.hasil.v1")).c1.status, m.ST.PAPI_OK);
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

  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  process.exit(okAll ? 0 : 1);
})();
