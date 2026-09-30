/**
 * semua_ke_capi_console.js — ganti SEMUA assignment PAPI yang sudah APPROVED ke CAPI (fasih-sm, akun ADMIN).
 * Tempel langsung di Console (tidak ada nilai yang disuntik Python).
 *
 * Ketetapan user 2026-09-29: cakupan APPROVED saja — DRAFT/SUBMITTED/REJECTED tetap PAPI, karena fasih-web
 * (web-entry: input_usaha/sisir, approve_pml, approve_capi) hanya bisa membuka dokumen PAPI. Semua subsls,
 * termasuk subsls wadah input. Aman dijalankan ulang kapan saja: yang sudah CAPI tidak ada lagi di daftar PAPI.
 *
 * CARA PAKAI (tab halaman Data survei: …/app/surveys/<survei>/<periode>/data)
 * ---------------------------------------------------------------------------
 *   await semuaKeCapi.jalankan()              // baca daftar PAPI segar -> jumlah per status -> ketik YA -> ganti
 *   semuaKeCapi.unduh()                       // CSV semua_ke_capi_<waktu>.csv (bukti)
 * Selain YA di prompt = batal (tidak ada yang diubah). {limit: N} opsional.
 * LANJUT SESUDAH TERPUTUS (401, tab ditutup): daftar kandidat disimpan per bagian; jalankan() lagi dgn bagian yang
 * sama melanjutkan sisanya TANPA membaca ulang daftar PAPI ({telusurUlang: true} memaksa baca ulang). Daftar yang
 * sudah tuntas -> run berikut otomatis membaca daftar baru (dokumen yang baru APPROVED).
 * PARALEL (beberapa tab/PC): tab 1 jalankan({bagian: "1/4"}), tab 2 {bagian: "2/4"}, … — dokumen dibagi lewat hash id,
 * tiap bagian lepas satu sama lain; catatan localStorage & nama CSV per bagian; unduh() di tiap tab = bagian tab itu.
 * Di browser yang sama, bagian yang sudah jalan di tab lain / pembagian berbeda / tanpa bagian ditolak.
 * Lain: semuaKeCapi.ringkasan(), semuaKeCapi.berhenti().
 *
 * PENGAMAN
 * --------
 * - Per dokumen, tepat sebelum diganti: detail SEGAR (get-by-assignment-id) harus APPROVED; mode kalau terbaca
 *   harus PAPI (sudah CAPI -> SUDAH_CAPI, tidak dikirim).
 * - Sesudahnya: status harus TETAP & mode CAPI (detail; detail tanpa mode -> tabel Data dicari dgn kode). Belum
 *   terbaca CAPI -> antrean cek ulang di sela dokumen lain s.d. 15 mnt (maks 20 dokumen menunggu); lewat -> BERHENTI.
 * - Konfirmasi ketik YA tiap run; langsung jalan, tanpa tahap periksa/percobaan 1 dokumen (ketetapan user).
 *   Kejanggalan -> batch berhenti.
 *
 * API (terekam 2026-09-27, 82 dokumen APPROVED -> CAPI, status & PML tetap): POST
 * /assignment-submit/api/assignment/{id}/change-mode body {modes:["CAPI"]} -> {success, message:"Berhasil. "}.
 */
(function (global) {
  "use strict";

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_semua_ke_capi_console.js
  // -------------------------------------------------------------------------
  const PANJANG_HALAMAN = 150; // datatable analytic menolak length > 150
  const BATAS_ULANG = 6;
  const HTTP_SIBUK = new Set([0, 429, 502, 503, 504]);
  const ST = {
    OK: "DIGANTI_CAPI_TERVERIFIKASI",
    MENUNGGU: "DIGANTI_CAPI_MENUNGGU",
    BELUM: "DIGANTI_CAPI_BELUM_TERVERIFIKASI",
  };
  const KOLOM_CSV = ["id", "kode_identitas", "nama", "status", "status_dokumen", "mode", "diganti", "pesan"];
  // Status yang menghentikan batch (anomali: jangan diteruskan ke dokumen lain).
  const BERHENTI = new Set([ST.BELUM, "STATUS_BERUBAH", "GANTI_DITOLAK", "SERVER_SIBUK"]);
  const MAKS_TIDAK_TERBACA = 5; // detail gagal beruntun -> sesi/server bermasalah, berhenti

  const norm = (s) => String(s == null ? "" : s).trim().toLowerCase();
  const approved = (alias) => /^APPROVED/i.test(String(alias || "").trim());

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

  /** Body datatable: mode (null = semua) + jendela tanggal dibuat (ISO penuh) + kata cari. Status TIDAK disaring
   *  di server (alias "APPROVED BY Pengawas" sbg saringan belum terbukti) — disaring dari item. */
  function bodyDaftar(periode, start, length, dari, sampai, mode, cari) {
    const extra = { surveyPeriodId: periode, assignmentErrorStatusType: -1 };
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

  /** "k/n" -> {k, n} (1 <= k <= n) atau null (tanpa bagian). Salah tulis -> Error. */
  function uraiBagian(b) {
    if (b == null || b === "") return null;
    const m = /^\s*(\d+)\s*\/\s*(\d+)\s*$/.exec(String(b));
    if (!m || +m[1] < 1 || +m[1] > +m[2]) throw new Error(`bagian "${b}" tidak valid — tulis mis. "1/3"`);
    return +m[2] === 1 ? null : { k: +m[1], n: +m[2] };
  }

  /** Hash FNV-1a 32-bit id -> bagian 1..n (stabil lintas tab/PC). */
  function bagianDari(id, n) {
    let h = 0x811c9dc5;
    for (const c of String(id)) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
    return (h % n) + 1;
  }

  /** Item datatable -> kandidat {id, kode, nama, alias, mode}. */
  function kandidatDari(it) {
    if (!it || !it.id) return null;
    return { id: String(it.id), kode: String(it.codeIdentity || "").replace(/\s+/g, " ").trim(), nama: it.data1 || "",
      alias: it.assignmentStatusAlias || "", mode: modeDari(it) };
  }

  /** Respons detail {status, j} -> {ada, alias, mode, kode, nama, pesan}. */
  function nilaiDetail(r) {
    const j = r && r.j;
    const d = r && r.status === 200 && j && j.success === true && j.data && typeof j.data === "object" ? j.data : null;
    if (!d) {
      const pesan = j && (j.message || j.error) ? String(j.message || j.error) : String((r && r.teks) || "").slice(0, 120);
      return { ada: false, alias: "", mode: "", kode: "", nama: "", pesan: `HTTP ${r ? r.status : "?"} ${pesan}`.trim() };
    }
    return { ada: true, alias: d.assignment_status_alias || "", mode: modeDari(d),
      kode: String(d.code_identity || "").replace(/\s+/g, " ").trim(), nama: d.data1 || "", pesan: "" };
  }

  /** Detail sebelum ganti -> null (boleh) atau {status, pesan}. */
  function cegahSebelum(det) {
    if (!det.ada) return { status: "TIDAK_TERBACA", pesan: det.pesan };
    if (det.mode === "CAPI") return { status: "SUDAH_CAPI", pesan: "detail sudah CAPI" };
    if (det.mode && det.mode !== "PAPI") return { status: "MODE_LAIN", pesan: `mode ${det.mode}` };
    if (!approved(det.alias)) return { status: "BUKAN_APPROVED", pesan: `status ${det.alias || "-"} — tetap PAPI` };
    return null;
  }

  /** Detail sesudah ganti vs status sebelum -> "OK" | "STATUS_BERUBAH" | "BELUM" (belum terbukti CAPI). */
  function nilaiSesudah(det, statusSebelum) {
    if (!det || !det.ada) return "BELUM";
    if (det.alias !== statusSebelum) return "STATUS_BERUBAH";
    return det.mode === "CAPI" ? "OK" : "BELUM";
  }

  /** Jeda cek ulang antrean (ke = 0, 1, ...): 20 dtk, 40, 60, 2 mnt, lalu tiap 3 mnt. */
  function jedaCek(ke) {
    return [20000, 40000, 60000, 120000][ke] || 180000;
  }

  function keCsv(baris) {
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    return "﻿" + [KOLOM_CSV.join(","), ...baris.map((b) => KOLOM_CSV.map((k) => kutip(b[k])).join(","))].join("\n");
  }

  // Catatan hasil per dokumen disimpan RINGKAS (localStorage ±5 juta karakter per situs, dipakai bersama alat lain;
  // format panjang ±290 karakter x 14 rb dokumen tidak muat): {s, k, a, m, g, p}. Format lama (sebelum 2026-09-30,
  // field `status`) tetap terbaca.
  const ALIAS_APPROVED = "APPROVED BY Pengawas";
  const SINGKAT = { [ST.OK]: "OK", [ST.MENUNGGU]: "M", [ST.BELUM]: "B" };
  const PANJANG = Object.fromEntries(Object.entries(SINGKAT).map(([a, s]) => [s, a]));
  // Sudah selesai utk daftar ini: tidak dikerjakan lagi saat MELANJUTKAN daftar tersimpan.
  const TUNTAS = new Set([ST.OK, "SUDAH_CAPI", "BUKAN_APPROVED", "MODE_LAIN"]);
  const namaDariKode = (kode) => String(kode || "").replace(/^\d{16}\s*-\s*/, "");

  /** Catatan lengkap {status, kode, nama, statusDok, mode, diganti, pesan} -> bentuk ringkas utk localStorage. */
  function padat(r) {
    const v = { s: SINGKAT[r.status] || r.status || "" };
    if (r.kode) v.k = r.kode;
    if (r.statusDok) v.a = r.statusDok === ALIAS_APPROVED ? "A" : r.statusDok;
    if (r.mode) v.m = r.mode;
    if (r.diganti && Number.isFinite(Date.parse(r.diganti))) v.g = Math.round(Date.parse(r.diganti) / 1000);
    if (r.pesan) v.p = r.pesan;
    return v;
  }

  /** Bentuk ringkas (atau format lama) -> catatan lengkap; null kalau tidak ada. */
  function urai(v) {
    if (!v || typeof v !== "object") return null;
    if (!("s" in v)) {
      return { status: v.status || "", kode: v.kode || "", nama: v.nama || namaDariKode(v.kode), statusDok: v.statusDok || "",
        mode: v.mode || "", diganti: v.diganti || "", pesan: v.pesan || "" };
    }
    return { status: PANJANG[v.s] || v.s, kode: v.k || "", nama: namaDariKode(v.k), statusDok: v.a === "A" ? ALIAS_APPROVED : (v.a || ""),
      mode: v.m || "", diganti: v.g ? new Date(v.g * 1000).toISOString() : "", pesan: v.p || "" };
  }

  /** ID daftar tersimpan yang belum tuntas menurut catatan hasil (urutan daftar dipertahankan). */
  function sisaDaftar(ids, hasil) {
    return (ids || []).filter((id) => {
      const r = urai(hasil && hasil[id]);
      return !r || !TUNTAS.has(r.status);
    });
  }

  /** Bagian yang sedang jalan di tab lain (["k/n" | "" = semua]) vs bagian ini (null = semua) -> alasan bentrok / "". */
  function bentrokBagian(lain, b) {
    for (const x of lain) {
      if (!x) return "tab lain sedang menjalankan SEMUA dokumen (tanpa bagian)";
      if (!b) return `bagian ${x} sedang berjalan di tab lain — tab ini juga wajib memakai {bagian: "k/${x.split("/")[1]}"}`;
      const y = uraiBagian(x);
      if (y.n !== b.n) return `tab lain memakai pembagian ${x} — semua tab wajib memakai jumlah bagian yang sama (/${y.n})`;
      if (y.k === b.k) return `bagian ${x} sudah berjalan di tab lain`;
    }
    return "";
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { ST, KOLOM_CSV, BERHENTI, halamanData, modeDari, bodyDaftar, bagiJendela, jedaUlang, uraiBagian,
      bagianDari, bentrokBagian, kandidatDari, nilaiDetail, cegahSebelum, nilaiSesudah, jedaCek, keCsv, approved,
      padat, urai, sisaDaftar, TUNTAS };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const API = "/app/api";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (Math.max(a, b) - a + 1));
  const log = (...a) => console.log("%c[semuaKeCapi]", "color:#1d6fb8;font-weight:bold", ...a);

  class Berhenti extends Error {
    constructor(kode, pesan) { super(pesan || kode); this.kode = kode; }
  }

  let berjalan = false;
  let hentikan = false;
  let requestTerakhir = 0;
  const KUNCI_JALAN = "semuaKeCapi.jalan.v1";
  const HIDUP_MS = 3 * 60 * 1000; // tanpa tanda hidup selama ini = tab itu dianggap sudah berhenti/ditutup
  const ID_TAB = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  let labelJalan = null; // "k/n" | "" (semua) selama jalankan() aktif di tab ini
  let detakTerakhir = 0;
  let bagianTab = null;  // bagian terakhir yang dijalankan tab ini -> bawaan unduh()/ringkasan()

  const OPSI_BAWAAN = { dari: "2026-01-01T00:00:00.000Z", maksJendela: 900, jarakRequestMs: 800,
    jedaBacaMin: 1000, jedaBacaMaks: 2000, jedaTulisMin: 500, jedaTulisMaks: 1500,
    maksMenunggu: 20, batasTungguMs: 15 * 60 * 1000 };

  const labelBagian = (b) => (b ? `.bagian-${b.k}-dari-${b.n}` : "");
  const kunciHasil = (b) => `semuaKeCapi.hasil.v1${labelBagian(b)}`; // per bagian: tab paralel tidak saling menimpa
  const kunciDaftar = (b) => `semuaKeCapi.daftar.v1${labelBagian(b)}`; // ID kandidat terakhir -> dilanjutkan tanpa baca ulang

  function bacaJson(kunci, bawaan) {
    try { return JSON.parse(localStorage.getItem(kunci) || "null") || bawaan; } catch (e) { return bawaan; }
  }
  /** -> true kalau tersimpan (false: localStorage penuh / diblokir). */
  function tulisJson(kunci, isi) {
    try { localStorage.setItem(kunci, JSON.stringify(isi)); return true; } catch (e) { return false; }
  }
  function catat(b, id, isi) {
    const h = bacaJson(kunciHasil(b), {});
    h[id] = padat({ ...(urai(h[id]) || {}), ...isi });
    if (!tulisJson(kunciHasil(b), h)) {
      throw new Berhenti("PENYIMPANAN_PENUH", `catatan dokumen ${id} tidak bisa disimpan di localStorage (penuh?) — `
        + "unduh() dulu; dokumen tanpa catatan diperiksa ulang lewat detail di run berikut");
    }
  }

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "semuaKeCapi.berhenti() dipanggil");
  }
  async function tidur(ms) {
    for (const akhir = Date.now() + ms; Date.now() < akhir;) {
      cekHenti();
      detak();
      await sleep(Math.min(1000, akhir - Date.now()));
    }
  }

  // Tab paralel di browser yang sama: tiap tab yang sedang jalan mencatat bagiannya + tanda hidup di localStorage,
  // supaya bagian yang sama / pembagian yang tumpang tindih tidak jalan dua kali.
  function tabLainJalan() {
    return Object.entries(bacaJson(KUNCI_JALAN, {}))
      .filter(([id, v]) => id !== ID_TAB && v && Date.now() - v.t < HIDUP_MS).map(([, v]) => v.bagian || "");
  }
  function detak(paksa) {
    if (labelJalan === null || (!paksa && Date.now() - detakTerakhir < 10000)) return;
    detakTerakhir = Date.now();
    const j = bacaJson(KUNCI_JALAN, {});
    for (const [id, v] of Object.entries(j)) if (!v || Date.now() - v.t >= HIDUP_MS) delete j[id];
    j[ID_TAB] = { bagian: labelJalan, t: Date.now() };
    tulisJson(KUNCI_JALAN, j);
  }
  function lepasJalan() {
    const j = bacaJson(KUNCI_JALAN, {});
    delete j[ID_TAB];
    tulisJson(KUNCI_JALAN, j);
  }
  // Tab dimuat ulang/ditutup di tengah jalan (mis. sesudah 401): tanda jalannya dilepas supaya bagian itu bisa
  // langsung dijalankan lagi, tanpa menunggu tanda hidupnya basi.
  if (typeof global.addEventListener === "function") {
    global.addEventListener("pagehide", () => { if (labelJalan !== null) lepasJalan(); });
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
    detak();
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
      if (r.status === 401) {
        throw new Berhenti("SESI_DITOLAK", "HTTP 401 — sesi habis: login ulang fasih-sm, muat ulang halaman Data, tempel skrip "
          + "lagi, lalu jalankan() dgn bagian yang SAMA — dilanjutkan dari daftar tersimpan, tanpa menelusuri ulang");
      }
      return r;
    }
  }

  async function bacaDaftar(o, ctx, start, dari, sampai, mode, cari) {
    const r = await baca(o, "POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode",
      bodyDaftar(ctx.periode, start, PANJANG_HALAMAN, dari, sampai, mode, cari));
    if (r.status === 403) throw new Berhenti("SESI_DITOLAK", "HTTP 403 di datatable — login ulang fasih-sm");
    if (r.status !== 200 || !r.j || !Array.isArray(r.j.searchData) || typeof r.j.totalHit !== "number") {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${r.status}: ${r.teks.slice(0, 150)}`);
    }
    return r.j;
  }

  /** Detail segar; mode tidak dimuat detail -> tabel Data dicari dgn kode identitas (item ber-id sama). */
  async function detailLengkap(o, ctx, id, kode) {
    const r = await baca(o, "GET", `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${encodeURIComponent(id)}`);
    const det = nilaiDetail(r);
    const cari = det.kode || kode;
    if (det.ada && !det.mode && cari) {
      try {
        const j = await bacaDaftar(o, ctx, 0, null, null, null, cari);
        const it = j.searchData.find((x) => String(x.id) === String(id));
        if (it) det.mode = modeDari(it);
      } catch (e) {
        if (e instanceof Berhenti && e.kode !== "RESPONS_TIDAK_DIKENAL") throw e;
      }
    }
    return det;
  }

  /** Semua PAPI (per jendela tanggal dibuat, batas paging ±1.000). -> {dok: Map, total, tidakUtuh}. */
  async function bacaSemuaPapi(o, ctx) {
    const dok = new Map();
    const tidakUtuh = [];
    const semua = await bacaDaftar(o, ctx, 0, null, null, "PAPI");
    log(`READ-ONLY: membaca semua PAPI (server menyebut ${semua.totalHit}${semua.totalHit >= 1000 ? " — dibaca per jendela tanggal dibuat" : ""})...`);
    const antre = [[o.dari, new Date(Date.now() + 3600 * 1000).toISOString()]];
    let jumlahJendela = 0;
    while (antre.length) {
      cekHenti();
      const [a, b] = antre.shift();
      await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
      const awal = await bacaDaftar(o, ctx, 0, a, b, "PAPI");
      if (awal.totalHit > o.maksJendela && Date.parse(b) - Date.parse(a) >= 60000) {
        antre.unshift(...bagiJendela(a, b));
        continue;
      }
      const ids = new Set();
      const simpan = (items) => {
        for (const it of items) {
          const k = kandidatDari(it);
          if (k) { dok.set(k.id, k); ids.add(k.id); }
        }
      };
      simpan(awal.searchData);
      for (let start = PANJANG_HALAMAN; start < awal.totalHit; start += PANJANG_HALAMAN) {
        await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
        const j = await bacaDaftar(o, ctx, start, a, b, "PAPI");
        if (!j.searchData.length) break;
        simpan(j.searchData);
      }
      if (ids.size < awal.totalHit) tidakUtuh.push(`${a}..${b}: ${ids.size}/${awal.totalHit}`);
      jumlahJendela += awal.totalHit;
    }
    return { dok, total: Math.max(semua.totalHit, jumlahJendela), tidakUtuh };
  }

  function cekHalaman() {
    const ctx = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !ctx) {
      log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
      return null;
    }
    if (berjalan) { log("Masih berjalan — tunggu selesai atau semuaKeCapi.berhenti()."); return null; }
    return ctx;
  }

  function laporGalat(e) {
    const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
    log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
    if (!(e instanceof Berhenti)) console.error(e);
    return kode;
  }

  /** Daftar PAPI SEGAR -> kandidat APPROVED (bagian ini), diurut kode. Dicetak jumlah per status. */
  async function bacaKandidat(o, ctx, b) {
    const r = await bacaSemuaPapi(o, ctx);
    const per = {};
    const siap = [];
    let bagianLain = 0;
    for (const k of r.dok.values()) {
      const st = approved(k.alias) ? "APPROVED" : (k.alias || "(tanpa status)");
      per[st] = (per[st] || 0) + 1;
      if (st !== "APPROVED") continue;
      if (b && bagianDari(k.id, b.n) !== b.k) { bagianLain++; continue; }
      siap.push(k);
    }
    siap.sort((x, y) => x.kode.localeCompare(y.kode));
    log(`Terbaca ${r.dok.size}/${r.total} dokumen PAPI. Per status:`);
    console.table(per);
    if (r.tidakUtuh.length) log(`⚠️ ${r.tidakUtuh.length} jendela tidak utuh: ${r.tidakUtuh.join("; ")} — sisanya terambil di run berikut`);
    log(`APPROVED diganti ke CAPI${b ? ` (bagian ${b.k}/${b.n}; ${bagianLain} milik bagian lain)` : ""}: ${siap.length}. Status lain tetap PAPI.`);
    return siap;
  }

  async function jalankan(opsi = {}) {
    const o = { ...OPSI_BAWAAN, ...opsi };
    let b;
    try { b = uraiBagian(o.bagian); } catch (e) { log(`⛔ ${e.message}`); return null; }
    const ctx = cekHalaman();
    if (!ctx) return null;
    const alasan = bentrokBagian(tabLainJalan(), b);
    if (alasan) {
      log(`⛔ ${alasan} — tidak dijalankan. (Tab yang sudah ditutup dianggap berhenti ${HIDUP_MS / 60000} mnt sesudah tanda hidup terakhirnya.)`);
      return null;
    }
    bagianTab = b;
    labelJalan = b ? `${b.k}/${b.n}` : "";
    detak(true);
    try {
      return await jalankanBagian(o, ctx, b);
    } finally {
      labelJalan = null;
      lepasJalan();
    }
  }

  async function jalankanBagian(o, ctx, b) {
    const labelB = b ? `${b.k}/${b.n}` : "";
    berjalan = true;
    hentikan = false;
    let daftar = null;
    // Lanjutkan daftar tersimpan (run sebelumnya terputus, mis. 401) — daftar PAPI TIDAK dibaca ulang dari server.
    const simpanan = bacaJson(kunciDaftar(b), null);
    if (!o.telusurUlang && simpanan && Array.isArray(simpanan.ids)) {
      const hasilLama = bacaJson(kunciHasil(b), {});
      const sisa = sisaDaftar(simpanan.ids, hasilLama);
      if (sisa.length) {
        daftar = sisa.map((id) => ({ id, kode: (urai(hasilLama[id]) || {}).kode || "", nama: "", alias: "" }));
        log(`▶️ Melanjutkan daftar tersimpan (${simpanan.waktu}${labelB ? `, bagian ${labelB}` : ""}): ${sisa.length} dari `
          + `${simpanan.ids.length} belum tuntas — daftar PAPI TIDAK dibaca ulang. {telusurUlang: true} = baca ulang dari server.`);
      } else {
        log(`Daftar tersimpan (${simpanan.waktu}) sudah tuntas — membaca daftar PAPI baru dari server...`);
      }
    }
    if (!daftar) {
      try {
        daftar = await bacaKandidat(o, ctx, b);
      } catch (e) {
        laporGalat(e);
        berjalan = false;
        return null;
      }
      if (!tulisJson(kunciDaftar(b), { waktu: new Date().toISOString(), bagian: labelB, ids: daftar.map((k) => k.id) })) {
        log("⚠️ Daftar kandidat tidak bisa disimpan (localStorage penuh?) — kalau run ini terputus, run berikut membaca ulang dari server.");
      }
    }
    berjalan = false;
    const limit = o.limit || daftar.length;
    const n = Math.min(limit, daftar.length);
    if (!daftar.length) return { diproses: 0 };
    if ((prompt(`Ketik YA utk mengganti mode ${n} dokumen PAPI yang sudah APPROVED ke CAPI${labelB ? ` (bagian ${labelB})` : ""}:`) || "").trim().toUpperCase() !== "YA") {
      log("Dibatalkan — tidak ada yang diubah.");
      return null;
    }
    berjalan = true;
    hentikan = false;
    const hitung = {};
    const tambah = (st) => { hitung[st] = (hitung[st] || 0) + 1; };
    const antre = []; // {k, alias, waktu, ke, berikut}
    let dikirim = 0;
    let tidakTerbaca = 0;

    /** Cek ulang antrean yang sudah jatuh tempo. Lewat batas tunggu / status berubah -> Berhenti. */
    async function layaniAntrean() {
      for (const a of [...antre]) {
        if (a.berikut > Date.now()) continue;
        cekHenti();
        const det = await detailLengkap(o, ctx, a.k.id, a.k.kode);
        const s = nilaiSesudah(det, a.alias);
        const menit = ((Date.now() - a.waktu) / 60000).toFixed(1);
        if (s === "OK") {
          antre.splice(antre.indexOf(a), 1);
          catat(b, a.k.id, { status: ST.OK, statusDok: det.alias, mode: "CAPI", pesan: `CAPI terbaca ${menit} mnt sesudah diganti` });
          tambah(ST.OK);
          log(`✅ ${a.k.id.slice(0, 8)} CAPI terbaca ${menit} mnt sesudah diganti`);
        } else if (s === "STATUS_BERUBAH") {
          catat(b, a.k.id, { status: ST.OK, statusDok: det.alias, mode: det.mode, pesan: `STATUS_BERUBAH: ${a.alias} -> ${det.alias}` });
          throw new Berhenti("STATUS_BERUBAH", `${a.k.id} status ${a.alias} -> ${det.alias} sesudah ganti mode`);
        } else if (Date.now() - a.waktu > o.batasTungguMs) {
          catat(b, a.k.id, { status: ST.BELUM, statusDok: det.alias, mode: det.mode,
            pesan: `${menit} mnt belum terbaca CAPI (mode '${det.mode || "-"}' ${det.pesan || ""})` });
          throw new Berhenti(ST.BELUM, `${a.k.id} ${menit} mnt belum terbaca CAPI — cek di fasih-sm sebelum menjalankan lagi`);
        } else {
          a.ke++;
          a.berikut = Date.now() + jedaCek(a.ke);
        }
      }
    }
    /** Tunggu sampai antrean < batas (0 = kosongkan). */
    async function tungguAntrean(batas) {
      while (antre.length > batas) {
        const paling = Math.min(...antre.map((a) => a.berikut));
        await tidur(Math.max(0, paling - Date.now()));
        await layaniAntrean();
      }
    }

    /** Ganti satu dokumen + verifikasi -> status. */
    async function gantiSatu(k) {
      const det = await detailLengkap(o, ctx, k.id, k.kode);
      const dasar = { kode: det.kode || k.kode, nama: det.nama || k.nama, statusDok: det.alias, mode: det.mode };
      k.kode = dasar.kode;
      const cegah = cegahSebelum(det);
      if (cegah) {
        catat(b, k.id, { ...dasar, status: cegah.status, pesan: cegah.pesan });
        return cegah.status;
      }
      const r = await kirim(o, "POST", `/assignment-submit/api/assignment/${encodeURIComponent(k.id)}/change-mode`, { modes: ["CAPI"] });
      const sementara = HTTP_SIBUK.has(r.status);
      if (!sementara && !(r.status === 200 && r.j && r.j.success === true)) {
        const pesan = `HTTP ${r.status} ${(r.j && (r.j.message || r.j.error)) || r.teks.slice(0, 150)}`;
        catat(b, k.id, { ...dasar, status: "GANTI_DITOLAK", pesan });
        if (r.status === 401 || r.status === 403) throw new Berhenti("SESI_DITOLAK", pesan);
        return "GANTI_DITOLAK";
      }
      const diganti = new Date().toISOString();
      // Dicatat SEBELUM verifikasi: kalau run terputus di sini (401, tab ditutup), run berikut mengecek dokumen ini
      // lewat antrean — tidak mengirim change-mode lagi.
      catat(b, k.id, { ...dasar, status: ST.MENUNGGU, diganti, pesan: "change-mode dikirim — belum diverifikasi" });
      if (sementara) log(`⏳ change-mode HTTP ${r.status || "gagal jaringan"} — TIDAK dikirim ulang; status dibaca dulu.`);
      let akhir = null;
      for (const ms of sementara ? [20000, 20000] : [1000, 3000]) {
        await tidur(ms);
        akhir = await detailLengkap(o, ctx, k.id, dasar.kode);
        if (nilaiSesudah(akhir, det.alias) !== "BELUM") break;
      }
      const s = nilaiSesudah(akhir, det.alias);
      if (s === "OK") {
        catat(b, k.id, { ...dasar, status: ST.OK, statusDok: akhir.alias, mode: "CAPI", diganti,
          pesan: sementara ? `respons HTTP ${r.status}, tapi mode terbukti CAPI` : "" });
        return ST.OK;
      }
      if (s === "STATUS_BERUBAH") {
        catat(b, k.id, { ...dasar, status: ST.OK, statusDok: akhir.alias, mode: akhir.mode, diganti,
          pesan: `STATUS_BERUBAH: ${det.alias} -> ${akhir.alias}` });
        return "STATUS_BERUBAH";
      }
      if (sementara) {
        catat(b, k.id, { ...dasar, status: "SERVER_SIBUK", diganti,
          pesan: `change-mode HTTP ${r.status}, mode belum CAPI ('${akhir && akhir.mode || "-"}') — jalankan lagi nanti` });
        return "SERVER_SIBUK";
      }
      // Server menjawab sukses tapi CAPI belum terbaca (mis. tabel Data terlambat) -> antrean cek ulang.
      antre.push({ k, alias: det.alias, waktu: Date.now(), ke: 0, berikut: Date.now() + jedaCek(0) });
      catat(b, k.id, { ...dasar, status: ST.MENUNGGU, diganti, pesan: `server sukses, mode terbaca '${akhir && akhir.mode || "-"}' — dicek ulang` });
      return ST.MENUNGGU;
    }

    const lama = bacaJson(kunciHasil(b), {});
    try {
      for (const k of daftar) {
        cekHenti();
        if (dikirim >= limit) break;
        await layaniAntrean();
        await tungguAntrean(o.maksMenunggu - 1);
        // Sudah pernah diganti tapi belum terbukti (run sebelumnya berhenti): cek ulang dulu, jangan kirim lagi.
        const rLama = urai(lama[k.id]);
        if (rLama && [ST.MENUNGGU, ST.BELUM].includes(rLama.status) && !o.ulangi) {
          antre.push({ k, alias: rLama.statusDok || k.alias, waktu: Date.now(), ke: 0, berikut: Date.now() });
          log(`[cek ulang] ${k.id.slice(0, 8)} tercatat ${rLama.status} di run sebelumnya — dicek, tidak dikirim ulang ({ulangi: true} utk memaksa)`);
          continue;
        }
        const st = await gantiSatu(k);
        if (st !== ST.MENUNGGU) tambah(st);
        const nomor = Object.values(hitung).reduce((x, y) => x + y, 0) + antre.length;
        log(`[${nomor}/${n}] ${st.padEnd(34)} ${k.id.slice(0, 8)} ${k.kode || k.nama}`);
        tidakTerbaca = st === "TIDAK_TERBACA" ? tidakTerbaca + 1 : 0;
        if (tidakTerbaca >= MAKS_TIDAK_TERBACA) throw new Berhenti("DETAIL_GAGAL_BERUNTUN", `${tidakTerbaca} detail beruntun tidak terbaca — sesi/server bermasalah?`);
        if (BERHENTI.has(st)) throw new Berhenti(st, `dokumen ${k.id} — periksa di fasih-sm sebelum menjalankan lagi`);
        if ([ST.OK, ST.MENUNGGU].includes(st)) {
          dikirim++;
          await tidur(acak(o.jedaTulisMin, o.jedaTulisMaks));
        }
      }
      if (antre.length) log(`Menunggu ${antre.length} dokumen yang belum terbukti CAPI (maks ${Math.round(o.batasTungguMs / 60000)} mnt)...`);
      await tungguAntrean(0);
    } catch (e) {
      const kode = laporGalat(e);
      if (kode !== "DIHENTIKAN_PENGGUNA") log("⛔ Batch DIHENTIKAN.");
      if (antre.length) log(`${antre.length} dokumen sudah dikirim tapi belum terbukti CAPI (tercatat ${ST.MENUNGGU}; run berikut mengeceknya dulu).`);
    } finally {
      berjalan = false;
      log("Selesai:", hitung, "— semuaKeCapi.unduh() utk bukti. Jalankan lagi kapan saja utk dokumen yang baru APPROVED.");
    }
    return hitung;
  }

  const bagianOpsi = (opsi) => (opsi.bagian != null ? uraiBagian(opsi.bagian) : bagianTab);

  function ringkasan(opsi = {}) {
    const per = {};
    for (const v of Object.values(bacaJson(kunciHasil(bagianOpsi(opsi)), {}))) {
      const st = (urai(v) || {}).status || "(belum)";
      per[st] = (per[st] || 0) + 1;
    }
    console.table(per);
    return per;
  }

  function unduh(opsi = {}) {
    const b = bagianOpsi(opsi);
    const baris = Object.entries(bacaJson(kunciHasil(b), {})).map(([id, v]) => ({ id, ...urai(v) }))
      .map((r) => ({ id: r.id, kode_identitas: r.kode, nama: r.nama, status: r.status, status_dokumen: r.statusDok,
        mode: r.mode, diganti: r.diganti, pesan: r.pesan }));
    if (!baris.length) return log("Belum ada hasil.");
    const blob = new Blob([keCsv(baris)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `semua_ke_capi${labelBagian(b)}_${new Date().toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-")}Z.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} dokumen).`);
  }

  global.semuaKeCapi = {
    jalankan, ringkasan, unduh,
    berhenti() { hentikan = true; log("Akan berhenti di langkah berikutnya."); },
  };
  log("Siap. Mulai: await semuaKeCapi.jalankan()  (paralel 4 tab: {bagian: \"1/4\"} … {bagian: \"4/4\"})");
})(typeof window !== "undefined" ? window : globalThis);
