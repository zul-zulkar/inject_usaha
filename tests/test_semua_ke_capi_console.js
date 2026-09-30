// Uji fasih_sm/ganti_moda/semua_ke_capi_console.js — logika murni + simulasi alur browser thd server fasih-sm
// PALSU (jam virtual). Jalankan: node tests/test_semua_ke_capi_console.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const BERKAS = path.join(__dirname, "..", "fasih_sm", "ganti_moda", "semua_ke_capi_console.js");
const m = require(BERKAS);

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const SURVEI = "a0429e96-51a5-477b-a415-485f9c153004";
const PERIODE = "fd68e454-ba45-4b85-8205-f3bf777ded24";
const APP = "APPROVED BY Pengawas";
const SUB = "SUBMITTED BY Pencacah";

// ---------------- logika murni
check("body: saring PAPI, status TIDAK disaring server", m.bodyDaftar("p", 0, 150, "a", "b", "PAPI").assignmentExtraParam,
  { surveyPeriodId: "p", assignmentErrorStatusType: -1, mode: ["PAPI"], dateCreatedFrom: "a", dateCreatedTo: "b" });
check("approved: alias server", [m.approved(APP), m.approved(SUB), m.approved("")], [true, false, false]);
check("bagian: tanpa / 1/1 = null", [m.uraiBagian(undefined), m.uraiBagian("1/1")], [null, null]);
check("bagian: 2/3", m.uraiBagian(" 2 / 3 "), { k: 2, n: 3 });
let galat = "";
try { m.uraiBagian("4/3"); } catch (e) { galat = e.message; }
check("bagian: k > n ditolak", /tidak valid/.test(galat), true);
const ids = Array.from({ length: 300 }, (_, i) => `id-${i}-${(i * 7919).toString(16)}`);
const per3 = [1, 2, 3].map((k) => ids.filter((i) => m.bagianDari(i, 3) === k).length);
check("bagian: tiap id tepat satu bagian, pembagian tidak timpang", [per3.reduce((a, b) => a + b, 0), per3.every((x) => x > 70)], [300, true]);
check("bagian: stabil", m.bagianDari("abc", 5), m.bagianDari("abc", 5));
const det = (o) => ({ ada: true, alias: APP, mode: "PAPI", kode: "", nama: "", pesan: "", ...o });
check("sebelum: APPROVED + PAPI = boleh", m.cegahSebelum(det()), null);
check("sebelum: mode tak terbaca tetap boleh (list sudah menyaring PAPI)", m.cegahSebelum(det({ mode: "" })), null);
check("sebelum: sudah CAPI", m.cegahSebelum(det({ mode: "CAPI" })).status, "SUDAH_CAPI");
check("sebelum: SUBMITTED tetap PAPI", m.cegahSebelum(det({ alias: SUB })).status, "BUKAN_APPROVED");
check("sebelum: mode campuran", m.cegahSebelum(det({ mode: "CAPI+PAPI" })).status, "MODE_LAIN");
check("sebelum: detail tak terbaca", m.cegahSebelum({ ada: false, pesan: "HTTP 403" }).status, "TIDAK_TERBACA");
check("sesudah: OK", m.nilaiSesudah(det({ mode: "CAPI" }), APP), "OK");
check("sesudah: masih PAPI", m.nilaiSesudah(det(), APP), "BELUM");
check("sesudah: status berubah", m.nilaiSesudah(det({ mode: "CAPI", alias: SUB }), APP), "STATUS_BERUBAH");
check("jeda cek ulang", [0, 1, 2, 3, 4, 9].map(m.jedaCek), [20000, 40000, 60000, 120000, 180000, 180000]);

// ---------------- simulasi browser
const jam = { now: Date.parse("2026-09-29T12:00:00.000Z") };
const server = { docs: new Map(), gantiDitolak: new Set(), tidakDiterapkan: new Set(), gantiLog: [], gangguan: [429] };
let urut = 0;
const tambah = (id, o) => server.docs.set(id, { id, kode: `5108060006000224 - USAHA ${id}`, alias: APP, mode: "PAPI",
  dibuat: Date.parse("2026-09-20T00:00:00.000Z") + (urut++) * 60000, ...o });
tambah("a0", { tanpaModeDetail: true, lagTabelMs: 50000 }); // detail tanpa mode + tabel Data terlambat 50 dtk
tambah("a1", {});
tambah("a2", {});
tambah("r0", { aliasDetail: SUB });                         // list: APPROVED, detail segar: sudah di-revoke
tambah("s0", { alias: SUB });
tambah("d0", { alias: "DRAFT" });
tambah("c0", { mode: "CAPI" });

const json = (status, obj, retryAfter) => ({ status, text: async () => (typeof obj === "string" ? obj : JSON.stringify(obj)),
  headers: { get: (h) => (h === "Retry-After" ? retryAfter || null : null) } });
const modeTabel = (d) => (d.berubahPada != null && jam.now < d.berubahPada + (d.lagTabelMs || 0) ? d.modeLama : d.mode);
async function fetchPalsu(url, init) {
  const u = new URL(url, "https://fasih-sm.bps.go.id");
  const p = u.pathname.replace(/^\/app\/api/, "");
  if (!init.headers["X-XSRF-TOKEN"]) return json(403, "Invalid CSRF Token");
  if (p === "/analytic/api/v2/assignment/datatable-all-user-survey-periode") {
    const g = server.gangguan.shift();
    if (g) return json(g, { error: "RATE_LIMIT_EXCEEDED" });
    const b = JSON.parse(init.body);
    const x = b.assignmentExtraParam;
    const semua = [...server.docs.values()].filter((d) => (!x.mode || x.mode.includes(modeTabel(d)))
      && (!x.assignmentStatusAlias || d.alias === x.assignmentStatusAlias)
      && (!x.dateCreatedFrom || d.dibuat >= Date.parse(x.dateCreatedFrom)) && (!x.dateCreatedTo || d.dibuat <= Date.parse(x.dateCreatedTo))
      && (!b.search.value || d.kode.includes(b.search.value)));
    return json(200, { totalHit: semua.length, searchData: semua.slice(b.start, b.start + b.length).map((d) => ({ id: d.id,
      codeIdentity: d.kode, data1: `USAHA ${d.id}`, assignmentStatusAlias: d.alias, mode: [modeTabel(d)],
      dateCreated: new Date(d.dibuat).toISOString() })) });
  }
  if (p === "/assignment-general/api/assignment/get-by-assignment-id") {
    const d = server.docs.get(u.searchParams.get("assignmentId"));
    if (!d) return json(403, "");
    const data = { code_identity: d.kode, data1: `USAHA ${d.id}`, assignment_status_alias: d.aliasDetail || d.alias };
    if (!d.tanpaModeDetail) data.mode = [d.mode];
    return json(200, { success: true, data });
  }
  const mg = /^\/assignment-submit\/api\/assignment\/([^/]+)\/change-mode$/.exec(p);
  if (mg && init.method === "POST") {
    const d = server.docs.get(mg[1]);
    const ke = JSON.parse(init.body).modes[0];
    server.gantiLog.push({ id: mg[1], ke, t: jam.now });
    if (server.gantiDitolak.has(mg[1])) return json(200, { success: false, message: "Tidak bisa ganti mode" });
    if (!server.tidakDiterapkan.has(mg[1])) { d.modeLama = d.mode; d.mode = ke; d.berubahPada = jam.now; }
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
vm.runInContext(fs.readFileSync(BERKAS, "utf8"), sandbox);
const hasil = (label = "") => JSON.parse(penyimpanan.get(`semuaKeCapi.hasil.v1${label}`) || "{}");
const mode = (...i) => i.map((x) => `${server.docs.get(x).mode}/${server.docs.get(x).alias.split(" ")[0]}`);

(async () => {
  const s = sandbox.semuaKeCapi;
  check("tidak ada tahap periksa terpisah", typeof s.periksa, "undefined");
  jawabPrompt.push("tidak");
  check("langsung: daftar dibaca (429 ditunggu), bukan YA -> batal tanpa perubahan", [await s.jalankan(), server.gantiLog.length], [null, 0]);
  check("jumlah dicetak sebelum YA", log.some((l) => l.includes("APPROVED diganti ke CAPI: 4")), true);

  jawabPrompt.push("YA");
  const r1 = await s.jalankan();
  check("run 1: a0 lewat antrean, a1/a2 langsung, r0 (sudah di-revoke) dilewati", r1,
    { [m.ST.OK]: 3, BUKAN_APPROVED: 1 });
  check("run 1: yang dikirim hanya APPROVED menurut detail", server.gantiLog.map((g) => `${g.id}>${g.ke}`), ["a0>CAPI", "a1>CAPI", "a2>CAPI"]);
  check("tanpa menunggu bukti pertama: a1 dikirim sebelum a0 terbaca CAPI (tabel terlambat 50 dtk)",
    server.gantiLog[1].t - server.gantiLog[0].t < 50000, true);
  check("a0 terverifikasi lewat tabel Data", hasil().a0.status, m.ST.OK);
  check("mode akhir: APPROVED jadi CAPI, status lain tetap PAPI", mode("a0", "a1", "a2", "r0", "s0", "d0", "c0"),
    ["CAPI/APPROVED", "CAPI/APPROVED", "CAPI/APPROVED", "PAPI/APPROVED", "PAPI/SUBMITTED", "PAPI/DRAFT", "CAPI/APPROVED"]);

  s.unduh();
  check("CSV: 3 DIGANTI_CAPI_TERVERIFIKASI", unduhan[0].isi.split(m.ST.OK).length - 1, 3);

  // run 2: b0 dijawab sukses tapi tidak diterapkan, g0 ditolak server
  server.docs.get("r0").aliasDetail = undefined;
  server.docs.get("r0").alias = SUB;
  tambah("b0", {});
  tambah("b1", {});
  tambah("g0", {});
  server.tidakDiterapkan.add("b0");
  server.gantiDitolak.add("g0");
  jawabPrompt.push("YA");
  const r2 = await s.jalankan();
  check("run 2: daftar dibaca ulang; b0 diantre, b1 lanjut, g0 GANTI_DITOLAK -> berhenti", r2, { [m.ST.OK]: 1, GANTI_DITOLAK: 1 });
  check("run 2: b0 tercatat menunggu", hasil().b0.status, m.ST.MENUNGGU);

  // run 3: g0 dibetulkan; b0 dicek ulang (TIDAK dikirim lagi) lalu 15 mnt belum CAPI -> berhenti
  server.gantiDitolak.clear();
  const nKirim = server.gantiLog.length;
  jawabPrompt.push("YA");
  const r3 = await s.jalankan();
  check("run 3: g0 diganti, b0 tidak dikirim ulang", server.gantiLog.slice(nKirim).map((g) => g.id), ["g0"]);
  check("run 3: b0 15 mnt belum CAPI -> DIGANTI_CAPI_BELUM_TERVERIFIKASI", [r3, hasil().b0.status], [{ [m.ST.OK]: 1 }, m.ST.BELUM]);
  check("run 3: berhenti tercatat di log", log.some((l) => l.includes(m.ST.BELUM) && l.includes("b0")), true);

  // run 4: server dibetulkan, {ulangi: true} memaksa kirim ulang b0
  server.tidakDiterapkan.clear();
  jawabPrompt.push("YA");
  const r4 = await s.jalankan({ ulangi: true });
  check("run 4: ulangi -> b0 dikirim ulang & terverifikasi", [r4, hasil().b0.status, server.docs.get("b0").mode], [{ [m.ST.OK]: 1 }, m.ST.OK, "CAPI"]);

  // bagian paralel: hanya dokumen bagiannya, catatan per bagian
  const e = Array.from({ length: 12 }, (_, i) => `e${i}`);
  e.forEach((i) => tambah(i, {}));
  const e2 = e.filter((i) => m.bagianDari(i, 2) === 2);
  jawabPrompt.push("YA");
  const rb = await s.jalankan({ bagian: "2/2" });
  check("bagian 2/2: hanya dokumen bagiannya", [rb[m.ST.OK], Object.keys(hasil(".bagian-2-dari-2")).sort()], [e2.length, [...e2].sort()]);
  check("bagian 2/2: catatan bagian utama tidak bertambah", Object.keys(hasil()).length, 7);
  check("bagian 1/2 belum disentuh", e.filter((i) => server.docs.get(i).mode === "PAPI").length, e.length - e2.length);
  jawabPrompt.push("YA");
  const rb1 = await s.jalankan({ bagian: "1/2" });
  check("bagian 1/2: sisanya", [rb1[m.ST.OK], e.every((i) => server.docs.get(i).mode === "CAPI")], [e.length - e2.length, true]);

  sandbox.location.host = "contoh.lain";
  check("halaman salah ditolak", await s.jalankan(), null);

  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  process.exit(okAll ? 0 : 1);
})();
