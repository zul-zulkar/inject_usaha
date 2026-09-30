/**
 * approve_capi_console.js — assignment CAPI "SUBMITTED BY Pencacah" -> ganti ke PAPI (supaya PML bisa
 * meng-approve lewat fasih-web: web-entry hanya membuka dokumen PAPI) -> sesudah APPROVED, kembalikan ke CAPI.
 * Dijalankan di Console fasih-sm akun ADMIN (Chrome biasa). Approve-nya sendiri oleh approve_capi.py
 * (memanggil approve_pml mode server, dibatasi ke ID yang diganti di sini).
 *
 * CARA PAKAI (tab halaman Data survei: …/app/surveys/<survei>/<periode>/data)
 * ---------------------------------------------------------------------------
 *   await approveCapi.periksa()               // READ-ONLY: daftar CAPI SUBMITTED, jumlah per PML
 *   await approveCapi.kePapi()                // ganti semua (ketik YA); {limit: N} opsional
 *   approveCapi.unduh()                       // CSV approve_capi_<waktu>.csv -> simpan di bahan/
 *   ... python approve_capi/approve_capi.py --daftar-pml <txt> --eksekusi   (approve per PML)
 *   await approveCapi.keCapi()                // kembalikan ke CAPI dokumen yang SUDAH APPROVED
 *   approveCapi.unduh()                       // bukti akhir
 * PARALEL (beberapa PC / tab): approve_capi.py --bagi N membagi daftar PML -> satu .siap.js per bagian; tiap
 * bagian hanya menyentuh PML-nya sendiri, catatan localStorage & CSV unduhan berlabel bagian.
 * Lain: approveCapi.unduhPerPml() (jumlah per PML, bahan --bagi --jumlah), approveCapi.ringkasan(), approveCapi.berhenti(), approveCapi.muatHasil(teksCsv) (pulihkan hasil
 * dari CSV unduhan kalau localStorage hilang / pindah browser).
 *
 * PENGAMAN
 * --------
 * - Daftar PML (DAFTAR_PML, disuntik approve_capi.py --console): hanya dokumen yang petugas saat ininya ada
 *   di daftar yang diganti; lainnya PML_TIDAK_DI_DAFTAR. Daftar kosong -> semua PML (ditanyakan dulu).
 * - Per dokumen, tepat sebelum diganti: detail SEGAR (get-by-assignment-id) harus SUBMITTED BY Pencacah & CAPI.
 *   Sesudahnya detail dibaca ulang: mode PAPI & status tetap -> DIGANTI_PAPI_TERVERIFIKASI.
 * - keCapi HANYA menyentuh dokumen yang tercatat diganti oleh alat ini (bukan dokumen yang aslinya PAPI),
 *   dan hanya yang sudah APPROVED (kecuali {termasukBelumApproved: true}).
 * - Konfirmasi ketik YA tiap run (tanpa gerbang limit 1 — ketetapan user 2026-09-29). Kejanggalan -> batch berhenti.
 *
 * API (terekam 2026-09-27, bukan tebakan): POST /assignment-submit/api/assignment/{id}/change-mode
 * body {modes:["PAPI"|"CAPI"]} -> {success, message:"Berhasil. "} (dipakai dialog "Ganti Mode" per baris).
 * Arah CAPI -> PAPI utk dokumen SUBMITTED BELUM pernah dicoba skrip: dokumen pertama yang gagal diverifikasi
 * menghentikan batch.
 */
(function (global) {
  "use strict";

  const DAFTAR_PML = /*__DAFTAR_PML__*/[];
  const LABEL = /*__LABEL__*/""; // ".bagian-K-dari-N" (approve_capi.py --bagi): catatan & unduhan terpisah per bagian

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_approve_capi_console.js
  // -------------------------------------------------------------------------
  const PANJANG_HALAMAN = 150; // datatable analytic menolak length > 150
  const BATAS_ULANG = 6;
  const HTTP_SIBUK = new Set([0, 429, 502, 503, 504]);
  const SUBMITTED = "SUBMITTED BY Pencacah";
  const ST = {
    PAPI_OK: "DIGANTI_PAPI_TERVERIFIKASI",
    PAPI_BELUM: "DIGANTI_PAPI_BELUM_TERVERIFIKASI",
    CAPI_OK: "DIKEMBALIKAN_CAPI_TERVERIFIKASI",
    CAPI_BELUM: "DIKEMBALIKAN_CAPI_BELUM_TERVERIFIKASI",
  };
  const KOLOM_CSV = ["id", "kode_identitas", "nama", "pml", "status", "status_dokumen", "mode", "diganti", "dikembalikan", "pesan"];
  // Status yang menghentikan batch (anomali: jangan diteruskan ke dokumen lain).
  const BERHENTI = new Set([ST.PAPI_BELUM, ST.CAPI_BELUM, "STATUS_BERUBAH", "GANTI_DITOLAK", "RESPONS_TIDAK_DIKENAL",
    "SESI_DITOLAK", "SERVER_SIBUK"]);

  const norm = (s) => String(s == null ? "" : s).trim().toLowerCase();

  function halamanData(path) {
    const m = /^\/app\/surveys\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? { survei: m[1], periode: m[2] } : null;
  }

  /** Mode dari objek (field bernama *mode*, string atau array) -> "CAPI" / "PAPI" / "CAPI+PAPI" / "". */
  function modeDari(d) {
    if (!d || typeof d !== "object") return "";
    const nilai = [];
    for (const [k, v] of Object.entries(d)) {
      if (!/mode/i.test(k)) continue;
      for (const x of [].concat(v)) if (typeof x === "string") nilai.push(x.trim().toUpperCase());
    }
    return [...new Set(nilai.filter((x) => ["CAPI", "PAPI", "CAWI"].includes(x)))].sort().join("+");
  }

  /** Body datatable: status (bawaan SUBMITTED BY Pencacah; null = semua) + mode, satu jendela tanggal dibuat (ISO penuh). */
  function bodyDaftar(periode, start, length, dari, sampai, mode, cari, status = SUBMITTED) {
    const extra = { surveyPeriodId: periode, assignmentErrorStatusType: -1, assignmentStatusAlias: status };
    if (mode) extra.mode = [mode];
    if (dari) extra.dateCreatedFrom = dari;
    if (sampai) extra.dateCreatedTo = sampai;
    return {
      draw: 1, start, length,
      columns: ["id", "codeIdentity", "data1", "data2", "data3", "data4", "data5", "data6", "data7", "data8", "data9", "data10"]
        .map((data) => ({ data, orderable: true })),
      order: [], search: { value: cari || "", regex: false }, assignmentExtraParam: extra,
    };
  }

  function bagiJendela(dari, sampai) {
    const m = new Date(Math.floor((Date.parse(dari) + Date.parse(sampai)) / 2)).toISOString();
    return [[dari, m], [m, sampai]];
  }

  function jedaUlang(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Item datatable -> kandidat {id, kode, nama, pml, peran, alias, mode}. */
  function kandidatDari(it) {
    if (!it || !it.id) return null;
    return {
      id: String(it.id), kode: String(it.codeIdentity || "").replace(/\s+/g, " ").trim(), nama: it.data1 || "",
      pml: norm(it.currentUserUsername), peran: String(it.currentUserSurveyRoleName || ""),
      alias: it.assignmentStatusAlias || "", mode: modeDari(it),
    };
  }

  /** Kandidat -> keputusan awal (sebelum detail): SIAP | TANPA_PML | PML_TIDAK_DI_DAFTAR | SUDAH_DIPROSES. */
  function putuskanKandidat(k, daftarPml, hasil) {
    const lama = hasil && hasil[k.id];
    if (lama && [ST.PAPI_OK, ST.PAPI_BELUM, ST.CAPI_OK, ST.CAPI_BELUM].includes(lama.status)) {
      return { status: "SUDAH_DIPROSES", pesan: `tercatat ${lama.status}` };
    }
    if (!k.pml) return { status: "TANPA_PML", pesan: "petugas saat ini kosong — tidak ada PML yang bisa meng-approve" };
    if (k.peran && !/pengawas/i.test(k.peran)) {
      return { status: "TANPA_PML", pesan: `petugas saat ini ${k.pml} berperan ${k.peran}, bukan Pengawas` };
    }
    if (daftarPml && daftarPml.length && !daftarPml.includes(k.pml)) {
      return { status: "PML_TIDAK_DI_DAFTAR", pesan: `PML ${k.pml} tidak ada di daftar PML` };
    }
    return { status: "SIAP", pesan: "" };
  }

  /** Respons detail {status, j} -> {ada, alias, mode, pml, kode, nama, pesan}. */
  function nilaiDetail(r) {
    const j = r && r.j;
    const d = r && r.status === 200 && j && j.success === true && j.data && typeof j.data === "object" ? j.data : null;
    if (!d) {
      const pesan = j && (j.message || j.error) ? String(j.message || j.error) : String((r && r.teks) || "").slice(0, 120);
      return { ada: false, alias: "", mode: "", pml: "", kode: "", nama: "", pesan: `HTTP ${r ? r.status : "?"} ${pesan}`.trim() };
    }
    return { ada: true, alias: d.assignment_status_alias || "", mode: modeDari(d), pml: norm(d.current_user_username),
      kode: String(d.code_identity || "").replace(/\s+/g, " ").trim(), nama: d.data1 || "", pesan: "" };
  }

  /** Detail sebelum ganti ke `ke` -> null (boleh) atau {status, pesan}. */
  function cegahSebelum(det, ke, opsi) {
    if (!det.ada) return { status: "TIDAK_TERBACA", pesan: det.pesan };
    const asal = ke === "PAPI" ? "CAPI" : "PAPI";
    if (det.mode === ke) return { status: ke === "PAPI" ? "SUDAH_PAPI" : "SUDAH_CAPI", pesan: `detail sudah ${ke}` };
    if (det.mode && det.mode !== asal) return { status: "MODE_LAIN", pesan: `mode ${det.mode}` };
    if (ke === "PAPI" && det.alias !== SUBMITTED) return { status: "BUKAN_SUBMITTED", pesan: `status ${det.alias || "-"}` };
    if (ke === "CAPI" && !/APPROVED/i.test(det.alias) && !(opsi && opsi.termasukBelumApproved)) {
      return { status: "BELUM_APPROVED", pesan: `status ${det.alias || "-"} — belum di-approve, tetap PAPI` };
    }
    return null;
  }

  function keCsv(baris) {
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    return "\ufeff" + [KOLOM_CSV.join(","), ...baris.map((b) => KOLOM_CSV.map((k) => kutip(b[k])).join(","))].join("\n");
  }

  /** CSV unduhan -> hasil {id: {...}} (utk muatHasil). Pemisah koma, sel dikutip. */
  function dariCsv(teks) {
    const baris = [];
    let sel = "", row = [], kutip = false;
    const s = String(teks || "").replace(/^\ufeff/, "");
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (kutip) {
        if (c === '"' && s[i + 1] === '"') { sel += '"'; i++; } else if (c === '"') kutip = false; else sel += c;
      } else if (c === '"') kutip = true;
      else if (c === ",") { row.push(sel); sel = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && s[i + 1] === "\n") i++;
        row.push(sel); baris.push(row); row = []; sel = "";
      } else sel += c;
    }
    if (sel || row.length) { row.push(sel); baris.push(row); }
    const [judul, ...isi] = baris.filter((r) => r.some((x) => x !== ""));
    if (!judul || !judul.includes("id") || !judul.includes("status")) throw new Error("bukan CSV approve_capi (kolom id/status tidak ada)");
    const hasil = {};
    for (const r of isi) {
      const o = Object.fromEntries(judul.map((k, i) => [k, r[i] || ""]));
      if (o.id) hasil[o.id] = { kode: o.kode_identitas, nama: o.nama, pml: o.pml, status: o.status, statusDok: o.status_dokumen,
        mode: o.mode, diganti: o.diganti, dikembalikan: o.dikembalikan, pesan: o.pesan };
    }
    return hasil;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { ST, SUBMITTED, KOLOM_CSV, BERHENTI, halamanData, modeDari, bodyDaftar, bagiJendela, jedaUlang,
      kandidatDari, putuskanKandidat, nilaiDetail, cegahSebelum, keCsv, dariCsv };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const API = "/app/api";
  const KUNCI_HASIL = `approveCapi.hasil.v1${LABEL}`; // per bagian: beberapa tab tidak saling menimpa
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (Math.max(a, b) - a + 1));
  const log = (...a) => console.log("%c[approveCapi]", "color:#b8541d;font-weight:bold", ...a);

  class Berhenti extends Error {
    constructor(kode, pesan) { super(pesan || kode); this.kode = kode; }
  }

  let berjalan = false;
  let hentikan = false;
  let requestTerakhir = 0;
  let kandidatTerakhir = null;

  const OPSI_BAWAAN = { dari: "2026-01-01T00:00:00.000Z", maksJendela: 900, jarakRequestMs: 800,
    jedaBacaMin: 1000, jedaBacaMaks: 2000, jedaTulisMin: 1500, jedaTulisMaks: 3000 };

  function bacaHasil() {
    try { return JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}") || {}; } catch (e) { return {}; }
  }
  function simpanHasil(h) {
    try { localStorage.setItem(KUNCI_HASIL, JSON.stringify(h)); } catch (e) { log("⚠️ localStorage gagal ditulis — unduh() sering-sering", e); }
  }
  function catat(id, isi) {
    const h = bacaHasil();
    h[id] = { ...(h[id] || {}), ...isi, waktu: new Date().toISOString() };
    simpanHasil(h);
  }

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "approveCapi.berhenti() dipanggil");
  }
  async function tidur(ms) {
    for (const akhir = Date.now() + ms; Date.now() < akhir;) {
      cekHenti();
      await sleep(Math.min(1000, akhir - Date.now()));
    }
  }
  function xsrf() {
    const c = document.cookie.split("; ").find((x) => x.startsWith("XSRF-TOKEN="));
    return c ? decodeURIComponent(c.slice("XSRF-TOKEN=".length)) : "";
  }

  /** Request mentah dgn jarak minimal. -> {status, j, teks, retryAfter}. */
  async function kirim(o, metode, path, body) {
    const tunggu = requestTerakhir + o.jarakRequestMs - Date.now();
    if (tunggu > 0) await sleep(tunggu);
    requestTerakhir = Date.now();
    let status = 0, teks = "", retryAfter = null;
    try {
      const res = await fetch(`${API}${path}`, {
        method: metode, credentials: "include",
        headers: { "Content-Type": "application/json", "X-XSRF-TOKEN": xsrf() },
        body: body == null ? undefined : JSON.stringify(body),
      });
      status = res.status;
      teks = await res.text();
      retryAfter = res.headers.get("Retry-After");
    } catch (e) {
      teks = `fetch gagal: ${e && e.message ? e.message : e}`;
    }
    let j = null;
    try { j = JSON.parse(teks); } catch (e) { /* bukan JSON */ }
    return { status, j, teks, retryAfter };
  }

  /** Request BACA: galat sementara ditunggu & diulang. */
  async function baca(o, metode, path, body) {
    for (let ke = 0; ; ke++) {
      const r = await kirim(o, metode, path, body);
      if (HTTP_SIBUK.has(r.status)) {
        if (ke >= BATAS_ULANG) throw new Berhenti("SERVER_SIBUK", `${path.split("?")[0]} masih HTTP ${r.status} setelah ${ke} kali menunggu`);
        const ms = jedaUlang(ke, r.retryAfter);
        log(`⏳ HTTP ${r.status || "gagal jaringan"} — tunggu ${Math.round(ms / 1000)} dtk (ulang ${ke + 1}/${BATAS_ULANG})`);
        await tidur(ms);
        continue;
      }
      if (r.status === 401) throw new Berhenti("SESI_DITOLAK", "HTTP 401 — login ulang fasih-sm, lalu jalankan lagi");
      return r;
    }
  }

  async function bacaDaftar(o, ctx, start, dari, sampai, mode, cari, status = SUBMITTED) {
    const r = await baca(o, "POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode",
      bodyDaftar(ctx.periode, start, PANJANG_HALAMAN, dari, sampai, mode, cari, status));
    if (r.status === 403) throw new Berhenti("SESI_DITOLAK", "HTTP 403 di datatable — login ulang fasih-sm");
    if (r.status !== 200 || !r.j || !Array.isArray(r.j.searchData) || typeof r.j.totalHit !== "number") {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${r.status}: ${r.teks.slice(0, 150)}`);
    }
    return r.j;
  }

  async function detail(o, id) {
    const r = await baca(o, "GET", `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${encodeURIComponent(id)}`);
    return nilaiDetail(r);
  }

  /** Mode dokumen kalau detail tidak memuatnya: tabel Data dicari dgn kode identitas (semua status & mode). */
  async function modeDariTabel(o, ctx, id, kode) {
    if (!kode) return "";
    try {
      const j = await bacaDaftar(o, ctx, 0, null, null, null, kode, null);
      const it = j.searchData.find((x) => String(x.id) === String(id));
      return it ? modeDari(it) : "";
    } catch (e) {
      if (e instanceof Berhenti && e.kode !== "RESPONS_TIDAK_DIKENAL") throw e;
      return "";
    }
  }

  async function detailLengkap(o, ctx, id, kode) {
    const det = await detail(o, id);
    if (det.ada && !det.mode) det.mode = await modeDariTabel(o, ctx, id, det.kode || kode);
    return det;
  }

  /** Semua CAPI SUBMITTED (per jendela tanggal dibuat, batas paging ±1.000). -> {items: Map, total, tidakUtuh}. */
  async function bacaSemuaCapi(o, ctx) {
    const dok = new Map();
    const tidakUtuh = [];
    const simpan = (items, ids) => {
      for (const it of items) {
        const k = kandidatDari(it);
        if (k) { dok.set(k.id, k); ids.add(k.id); }
      }
    };
    const semua = await bacaDaftar(o, ctx, 0, null, null, "CAPI");
    log(`READ-ONLY: membaca CAPI "${SUBMITTED}" (server menyebut ${semua.totalHit}${semua.totalHit >= 1000 ? "+ — bisa terpotong, dibaca per jendela" : ""})...`);
    const antre = [[o.dari, new Date(Date.now() + 3600 * 1000).toISOString()]];
    let jumlahJendela = 0;
    while (antre.length) {
      cekHenti();
      const [a, b] = antre.shift();
      await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
      const awal = await bacaDaftar(o, ctx, 0, a, b, "CAPI");
      if (awal.totalHit > o.maksJendela && Date.parse(b) - Date.parse(a) >= 60000) {
        antre.unshift(...bagiJendela(a, b));
        continue;
      }
      const ids = new Set();
      simpan(awal.searchData, ids);
      for (let start = PANJANG_HALAMAN; start < awal.totalHit; start += PANJANG_HALAMAN) {
        await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
        const j = await bacaDaftar(o, ctx, start, a, b, "CAPI");
        if (!j.searchData.length) break;
        simpan(j.searchData, ids);
      }
      if (ids.size < awal.totalHit) tidakUtuh.push(`${a}..${b}: ${ids.size}/${awal.totalHit}`);
      jumlahJendela += awal.totalHit;
    }
    return { dok, total: Math.max(semua.totalHit, jumlahJendela), tidakUtuh };
  }

  function daftarPmlAktif(o) {
    return (o.pml || DAFTAR_PML || []).map(norm).filter(Boolean);
  }

  async function periksa(opsi = {}) {
    const o = { ...OPSI_BAWAAN, ...opsi };
    const ctx = cekHalaman();
    if (!ctx || berjalan) return null;
    berjalan = true;
    hentikan = false;
    try {
      const r = await bacaSemuaCapi(o, ctx);
      const hasil = bacaHasil();
      const daftar = daftarPmlAktif(o);
      const per = {};
      const perPml = {};
      const siap = [];
      for (const k of r.dok.values()) {
        const p = putuskanKandidat(k, daftar, hasil);
        per[p.status] = (per[p.status] || 0) + 1;
        const kunci = k.pml || "(kosong)";
        perPml[kunci] = perPml[kunci] || { SIAP: 0, lain: 0, peran: k.peran || "" };
        perPml[kunci][p.status === "SIAP" ? "SIAP" : "lain"]++;
        if (p.status === "SIAP") siap.push(k);
      }
      siap.sort((a, b) => (a.pml + a.kode).localeCompare(b.pml + b.kode));
      kandidatTerakhir = { siap, semua: r.dok, waktu: Date.now(), perPml };
      log(`Terbaca ${r.dok.size}/${r.total} dokumen CAPI SUBMITTED. Keputusan:`, per);
      if (r.tidakUtuh.length) log(`⚠️ ${r.tidakUtuh.length} jendela tidak utuh: ${r.tidakUtuh.join("; ")} — jalankan periksa() lagi nanti`);
      console.table(perPml);
      if (!daftar.length) log("⚠️ DAFTAR PML kosong — semua PML ikut. Batasi: approveCapi.kePapi({pml: ['a@x', ...]}) atau tempel ulang berkas .siap.js dari approve_capi.py --console.");
      else {
        const tanpa = daftar.filter((p) => !perPml[p]);
        if (tanpa.length) log(`PML di daftar tanpa dokumen CAPI SUBMITTED: ${tanpa.join(", ")}`);
      }
      log(`SIAP diganti ke PAPI: ${siap.length}. Lanjut: await approveCapi.kePapi()`);
      return { terbaca: r.dok.size, total: r.total, siap: siap.length, per };
    } catch (e) {
      laporGalat(e);
      return null;
    } finally {
      berjalan = false;
    }
  }

  function cekHalaman() {
    const ctx = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !ctx) {
      log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
      return null;
    }
    if (berjalan) { log("Masih berjalan — tunggu selesai atau approveCapi.berhenti()."); return null; }
    return ctx;
  }

  function laporGalat(e) {
    const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
    log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
    if (!(e instanceof Berhenti)) console.error(e);
  }

  /** Ganti mode satu dokumen `ke` + verifikasi. -> status akhir. */
  async function gantiSatu(o, ctx, k, ke) {
    const det = await detailLengkap(o, ctx, k.id, k.kode);
    const cegah = cegahSebelum(det, ke, o);
    const dasar = { kode: det.kode || k.kode, nama: det.nama || k.nama, pml: det.pml || k.pml, statusDok: det.alias, mode: det.mode };
    if (cegah) {
      // Dokumen yang sudah PAPI sebelum alat ini menyentuhnya TIDAK dicatat sbg "diganti" (keCapi tak boleh menyentuhnya).
      if (ke === "CAPI" || cegah.status !== "SUDAH_PAPI") catat(k.id, { ...dasar, ...(ke === "CAPI" && cegah.status === "SUDAH_CAPI" ? { status: ST.CAPI_OK } : {}), pesan: `${cegah.status}: ${cegah.pesan}` });
      return cegah.status;
    }
    if (ke === "PAPI" && !det.mode) {
      catat(k.id, { ...dasar, pesan: "MODE_TIDAK_TERBACA: detail & tabel Data tidak memuat mode" });
      return "MODE_TIDAK_TERBACA";
    }
    if (ke === "CAPI" && det.mode !== "PAPI") {
      catat(k.id, { ...dasar, pesan: `MODE_TIDAK_TERBACA: mode '${det.mode || "-"}'` });
      return "MODE_TIDAK_TERBACA";
    }
    const statusSebelum = det.alias;
    const r = await kirim(o, "POST", `/assignment-submit/api/assignment/${encodeURIComponent(k.id)}/change-mode`, { modes: [ke] });
    const sementara = HTTP_SIBUK.has(r.status);
    if (!sementara && !(r.status === 200 && r.j && r.j.success === true)) {
      const pesan = `HTTP ${r.status} ${(r.j && (r.j.message || r.j.error)) || r.teks.slice(0, 150)}`;
      catat(k.id, { ...dasar, pesan: `GANTI_DITOLAK: ${pesan}` });
      if (r.status === 401 || r.status === 403) throw new Berhenti("SESI_DITOLAK", pesan);
      return "GANTI_DITOLAK";
    }
    if (sementara) log(`⏳ change-mode HTTP ${r.status || "gagal jaringan"} — TIDAK dikirim ulang; status dibaca dulu.`);
    // Verifikasi: detail segar sampai mode = tujuan (maks ±3x).
    let akhir = null;
    for (const ms of sementara ? [20000, 20000, 30000] : [1500, 4000, 8000]) {
      await tidur(ms);
      akhir = await detailLengkap(o, ctx, k.id, dasar.kode);
      if (akhir.ada && akhir.mode === ke) break;
    }
    const stOk = ke === "PAPI" ? ST.PAPI_OK : ST.CAPI_OK;
    const stBelum = ke === "PAPI" ? ST.PAPI_BELUM : ST.CAPI_BELUM;
    const cap = ke === "PAPI" ? { diganti: new Date().toISOString() } : { dikembalikan: new Date().toISOString() };
    if (akhir && akhir.ada && akhir.mode === ke) {
      if (akhir.alias !== statusSebelum) {
        catat(k.id, { ...dasar, ...cap, status: stOk, statusDok: akhir.alias, mode: ke,
          pesan: `STATUS_BERUBAH: ${statusSebelum} -> ${akhir.alias}` });
        return "STATUS_BERUBAH";
      }
      catat(k.id, { ...dasar, ...cap, status: stOk, statusDok: akhir.alias, mode: ke, pesan: sementara ? `respons HTTP ${r.status}, tapi mode terbukti ${ke}` : "" });
      return stOk;
    }
    if (sementara && akhir && akhir.ada && akhir.mode !== ke) {
      catat(k.id, { ...dasar, pesan: `SERVER_SIBUK: change-mode HTTP ${r.status}, mode tetap ${akhir.mode || "-"} — jalankan lagi nanti` });
      return "SERVER_SIBUK";
    }
    catat(k.id, { ...dasar, ...cap, status: stBelum, pesan: `server menjawab sukses, tapi mode terbaca '${akhir ? akhir.mode || "-" : "?"}' (${akhir ? akhir.pesan : ""})` });
    return stBelum;
  }

  async function jalankanArah(ke, opsi) {
    const o = { ...OPSI_BAWAAN, ...opsi };
    const ctx = cekHalaman();
    if (!ctx) return null;
    let daftar;
    if (ke === "PAPI") {
      if (!kandidatTerakhir || Date.now() - kandidatTerakhir.waktu > 30 * 60 * 1000) {
        log("Daftar CAPI belum dibaca / sudah > 30 mnt — membaca ulang...");
        const p = await periksa(opsi);
        if (!p) return null;
      }
      daftar = kandidatTerakhir.siap.filter((k) => putuskanKandidat(k, daftarPmlAktif(o), bacaHasil()).status === "SIAP");
    } else {
      const h = bacaHasil();
      daftar = Object.entries(h).filter(([, v]) => [ST.PAPI_OK, ST.PAPI_BELUM].includes(v.status))
        .map(([id, v]) => ({ id, kode: v.kode || "", nama: v.nama || "", pml: v.pml || "" }));
      if (o.pml) {
        const p = o.pml.map(norm);
        daftar = daftar.filter((k) => p.includes(norm(k.pml)));
      }
    }
    const limit = o.limit || daftar.length;
    log(`${ke === "PAPI" ? "🔁 CAPI -> PAPI" : "↩️ PAPI -> CAPI (hanya yang diganti alat ini & sudah APPROVED)"}: ${daftar.length} kandidat, limit ${limit}.`);
    if (!daftar.length) return { diproses: 0 };
    const n = Math.min(limit, daftar.length);
    if ((prompt(`Ketik YA utk mengganti mode ${n} dokumen ke ${ke}:`) || "").trim().toUpperCase() !== "YA") {
      log("Dibatalkan — tidak ada yang diubah.");
      return null;
    }
    berjalan = true;
    hentikan = false;
    const hitung = {};
    let dikirim = 0;
    try {
      for (const k of daftar) {
        cekHenti();
        if (dikirim >= limit) break;
        const st = await gantiSatu(o, ctx, k, ke);
        hitung[st] = (hitung[st] || 0) + 1;
        const n = Object.values(hitung).reduce((a, b) => a + b, 0);
        log(`[${n}] ${st.padEnd(38)} ${k.id.slice(0, 8)} ${k.pml || "-"} ${k.kode || k.nama}`);
        if ([ST.PAPI_OK, ST.CAPI_OK, ST.PAPI_BELUM, ST.CAPI_BELUM, "STATUS_BERUBAH", "GANTI_DITOLAK", "SERVER_SIBUK"].includes(st)) {
          dikirim++;
          if (!BERHENTI.has(st)) await tidur(acak(o.jedaTulisMin, o.jedaTulisMaks));
        }
        if (BERHENTI.has(st)) {
          log(`⛔ ${st} — batch DIHENTIKAN. Periksa dokumen ${k.id} di fasih-sm sebelum menjalankan lagi.`);
          break;
        }
      }
    } catch (e) {
      laporGalat(e);
    } finally {
      berjalan = false;
      log("Selesai:", hitung, ke === "PAPI"
        ? "Lanjut: approveCapi.unduh() -> simpan CSV di bahan/ -> python approve_capi/approve_capi.py --daftar-pml <txt> --cek"
        : "approveCapi.unduh() utk bukti.");
    }
    return hitung;
  }

  function ringkasan() {
    const per = {};
    for (const v of Object.values(bacaHasil())) per[v.status || "(belum)"] = (per[v.status || "(belum)"] || 0) + 1;
    console.table(per);
    return per;
  }

  function unduh() {
    const h = bacaHasil();
    const baris = Object.entries(h).map(([id, v]) => ({ id, kode_identitas: v.kode, nama: v.nama, pml: v.pml, status: v.status || "",
      status_dokumen: v.statusDok, mode: v.mode, diganti: v.diganti, dikembalikan: v.dikembalikan, pesan: v.pesan }));
    if (!baris.length) return log("Belum ada hasil.");
    const blob = new Blob([keCsv(baris)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `approve_capi${LABEL}_${new Date().toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-")}Z.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} dokumen) — pindahkan ke folder bahan/ proyek.`);
  }

  /** CSV jumlah dokumen per PML hasil periksa() terakhir -> approve_capi.py --bagi N --jumlah <csv>. */
  function unduhPerPml() {
    if (!kandidatTerakhir) return log("Jalankan dulu: await approveCapi.periksa()");
    const baris = Object.entries(kandidatTerakhir.perPml).filter(([p]) => p !== "(kosong)")
      .map(([pml, v]) => `"${pml}",${v.SIAP},${v.lain}`);
    const blob = new Blob(["\ufeffpml,siap,lain\n" + baris.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `jumlah_capi_per_pml${LABEL}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} PML) -> python approve_capi/approve_capi.py --daftar-pml <txt> --bagi N --jumlah <csv>`);
  }

  function muatHasil(teks) {
    const baru = dariCsv(teks);
    const h = bacaHasil();
    let n = 0;
    for (const [id, v] of Object.entries(baru)) {
      if (!h[id] || !h[id].status || (v.status === ST.CAPI_OK)) { h[id] = { ...(h[id] || {}), ...v }; n++; }
    }
    simpanHasil(h);
    log(`${n} catatan dimuat dari CSV.`);
    return ringkasan();
  }

  global.approveCapi = {
    periksa,
    kePapi: (opsi = {}) => jalankanArah("PAPI", opsi),
    keCapi: (opsi = {}) => jalankanArah("CAPI", opsi),
    ringkasan, unduh, unduhPerPml, muatHasil,
    berhenti() { hentikan = true; log("Akan berhenti di langkah berikutnya."); },
  };
  log(`Siap${LABEL ? " (" + LABEL.slice(1) + ")" : ""}. Daftar PML: ${DAFTAR_PML.length ? DAFTAR_PML.length + " akun" : "KOSONG (semua PML)"}. Mulai: await approveCapi.periksa()`);
})(typeof window !== "undefined" ? window : globalThis);
