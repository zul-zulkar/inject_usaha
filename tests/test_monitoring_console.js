// Uji monitoring_console.js — logika murni + simulasi alur browser terhadap server fasih-sm PALSU
// (Node, offline, jam virtual). Bentuk request/respons ditiru dari tests/test_pindah_wilayah_simulasi.js.
// Jalankan: node tests/test_monitoring_console.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const BERKAS = path.join(__dirname, "..", "monitoring", "monitoring_console.js");
const m = require(BERKAS);

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const SURVEI = "a0429e96-51a5-477b-a415-485f9c153004";
const PERIODE = "fd68e454-ba45-4b85-8205-f3bf777ded24";
const WADAH = "5108060006000224";
const regionCamel = (kode) => ({ id: "r", level1: { fullCode: "51", level2: { fullCode: "5108",
  level3: { fullCode: kode.slice(0, 7), level4: { fullCode: kode.slice(0, 10), level5: { fullCode: kode.slice(0, 14),
    level6: { fullCode: kode } } } } } } });

// ---------------- logika murni
check("halaman Data", m.halamanData(`/app/surveys/${SURVEI}/${PERIODE}/data`), { survei: SURVEI, periode: PERIODE });
check("bukan halaman Data", m.halamanData("/app/surveys"), null);
check("kode subsls datatable", m.kodeSubsls(regionCamel(WADAH)), WADAH);
check("kode subsls detail snake", m.kodeSubsls({ level_1: { full_code: "51", level_2: { full_code: "5108" } } }), "5108");
check("baris snapshot", m.barisSnapshot({ id: "a", codeIdentity: `${WADAH} - X (Y)`, data1: "X (Y)", assignmentStatusAlias: "DRAFT",
  mode: ["PAPI"], currentUserUsername: "ppl@x", currentUserSurveyRoleName: "Pencacah", sumError: 0, dateCreated: "d",
  dateModified: "e", region: regionCamel(WADAH) }),
{ id: "a", kode_identitas: `${WADAH} - X (Y)`, nama: "X (Y)", status: "DRAFT", mode: "PAPI", subsls: WADAH, petugas: "ppl@x",
  peran_petugas: "Pencacah", galat: 0, dibuat: "d", diubah: "e" });
check("baris tanpa id", m.barisSnapshot({}), null);
check("body: saring mode & tanggal", m.bodyDaftar("p", 150, 150, "a", "b", ["PAPI"]).assignmentExtraParam,
  { surveyPeriodId: "p", assignmentErrorStatusType: -1, assignmentStatusAlias: null, mode: ["PAPI"], dateCreatedFrom: "a", dateCreatedTo: "b" });
check("body: tanpa mode", "mode" in m.bodyDaftar("p", 0, 150, null, null, null).assignmentExtraParam, false);
check("belah jendela", m.bagiJendela("2026-01-01T00:00:00.000Z", "2026-01-03T00:00:00.000Z"),
  [["2026-01-01T00:00:00.000Z", "2026-01-02T00:00:00.000Z"], ["2026-01-02T00:00:00.000Z", "2026-01-03T00:00:00.000Z"]]);
check("jeda ulang", [m.jedaUlang(0), m.jedaUlang(1), m.jedaUlang(9), m.jedaUlang(0, "30")], [15000, 30000, 120000, 30000]);
const csv = m.keCsv([{ id: "a", nama: 'X "Y"', galat: 0 }]);
check("csv: BOM, judul, kutip ganda", [csv.charCodeAt(0), csv.split("\n")[0].slice(1), csv.split("\n")[1].slice(0, 12)],
  [0xfeff, m.KOLOM_CSV.join(","), '"a","","X ""']);

// ---------------- simulasi browser
const jam = { now: Date.parse("2026-09-29T02:00:00.000Z") };
const server = { docs: [], req: 0, tulis: 0, gangguan: [429, 504] };
for (let i = 0; i < 1100; i++) server.docs.push({ id: `a${i}`, dibuat: Date.parse("2026-09-24T02:00:00.000Z") + i * 3000, mode: "PAPI" });
for (let i = 0; i < 300; i++) server.docs.push({ id: `b${i}`, dibuat: Date.parse("2026-09-10T00:00:00.000Z") + i * 3600000, mode: "PAPI" });
for (let i = 0; i < 50; i++) server.docs.push({ id: `c${i}`, dibuat: Date.parse("2026-09-12T00:00:00.000Z"), mode: "CAPI" });

const json = (status, obj, retryAfter) => ({ status, text: async () => (typeof obj === "string" ? obj : JSON.stringify(obj)),
  headers: { get: (h) => (h === "Retry-After" ? retryAfter || null : null) } });
async function fetchPalsu(url, init) {
  server.req++;
  const p = new URL(url, "https://fasih-sm.bps.go.id").pathname.replace(/^\/app\/api/, "");
  if (init.method !== "POST" || p !== "/analytic/api/v2/assignment/datatable-all-user-survey-periode") {
    server.tulis++;
    return json(404, {});
  }
  if (!init.headers["X-XSRF-TOKEN"]) return json(403, "Invalid CSRF Token");
  const g = server.gangguan.shift();
  if (g) return json(g, g === 504 ? "<html>504</html>" : { error: "RATE_LIMIT_EXCEEDED" });
  const body = JSON.parse(init.body);
  if (body.length > 150) return json(400, { message: "Length restricted to 150" });
  const x = body.assignmentExtraParam;
  const semua = server.docs.filter((d) => (!x.mode || x.mode.includes(d.mode))
    && (!x.dateCreatedFrom || d.dibuat >= Date.parse(x.dateCreatedFrom)) && (!x.dateCreatedTo || d.dibuat <= Date.parse(x.dateCreatedTo)));
  // batas server asli: start + length > 1000 -> kosong, totalHit ikut dipotong 1.000 tanpa saring tanggal
  const hal = body.start + body.length > 1000 ? [] : semua.slice(body.start, body.start + body.length);
  const totalHit = x.dateCreatedFrom ? semua.length : Math.min(1000, semua.length);
  return json(200, { searchData: hal.map((d) => ({ id: d.id, codeIdentity: `${WADAH} - USAHA ${d.id}`, data1: `USAHA ${d.id}`,
    assignmentStatusAlias: "APPROVED BY Pengawas", mode: [d.mode], sumError: 0, dateCreated: new Date(d.dibuat).toISOString(),
    region: regionCamel(WADAH) })), totalHit });
}
class JamDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(jam.now); }
  static now() { return jam.now; }
}
const log = [];
const unduhan = [];
const blobs = new Map();
const sandbox = {
  console: { log: (...a) => log.push(a.filter((x) => !String(x).startsWith("color:")).join(" ")), table: () => {}, error: (...a) => log.push(`ERR ${a.join(" ")}`) },
  Date: JamDate,
  setTimeout: (fn, ms) => { jam.now += Math.max(0, ms || 0); setImmediate(fn); },
  fetch: fetchPalsu,
  location: { host: "fasih-sm.bps.go.id", pathname: `/app/surveys/${SURVEI}/${PERIODE}/data` },
  document: { cookie: "XSRF-TOKEN=abc%3D", body: { appendChild: () => {} },
    createElement: () => ({ click() { unduhan.push({ nama: this.download, isi: blobs.get(this.href) }); }, remove() {} }) },
  Blob: class { constructor(bagian) { this.isi = bagian.join(""); } },
  URL: { createObjectURL: (b) => { const k = `blob:${blobs.size}`; blobs.set(k, b.isi); return k; } },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(BERKAS, "utf8"), sandbox);

(async () => {
  const mon = sandbox.monitoring;
  mon.unduh();
  check("unduh sebelum jalan ditolak", [unduhan.length, log.some((l) => l.includes("Belum ada hasil"))], [0, true]);
  const r = await mon.jalankan();
  check("semua PAPI terbaca walau jendela > 1.000 & totalHit terpotong", r, { terbaca: 1400, total: 1400 });
  check("CAPI tidak ikut", [...mon.hasil.dok.keys()].some((id) => id.startsWith("c")), false);
  check("429 & 504 ditunggu lalu diulang", log.filter((l) => l.includes("⏳")).length, 2);
  check("tidak ada request selain datatable (read-only)", server.tulis, 0);
  mon.unduh();
  const baris = unduhan[0].isi.split("\n");
  check("CSV: nama berkas & jumlah baris", [/^snapshot_fasih_sm_\d{8}-\d{4}Z\.csv$/.test(unduhan[0].nama), baris.length], [true, 1401]);
  check("CSV: total_server tercatat", baris[1].endsWith(',"1400"'), true);

  sandbox.location.host = "contoh.lain";
  await mon.jalankan();
  check("halaman salah ditolak", log[log.length - 1].includes("Buka dulu halaman Data"), true);

  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  process.exit(okAll ? 0 : 1);
})();
