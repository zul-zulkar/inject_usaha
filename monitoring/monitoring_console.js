/**
 * monitoring_console.js — SNAPSHOT status dokumen dari fasih-sm (akun ADMIN), bahan monitoring/monitoring.py.
 * READ-ONLY: hanya membaca daftar (datatable analytic), tidak pernah mengubah apa pun di server.
 *
 * CARA PAKAI
 * ----------
 * Chrome biasa, VPN, login fasih-sm akun admin, buka halaman Data survei
 * (…/app/surveys/<survei>/<periode>/data) -> F12 -> Console -> tempel SELURUH isi berkas ini -> Enter.
 *     await monitoring.jalankan()                 // semua dokumen mode PAPI (dokumen input usaha)
 *     monitoring.unduh()                          // CSV snapshot_fasih_sm_<waktu>.csv -> simpan di bahan/
 *   lalu:  python monitoring/monitoring.py        (snapshot terbaru di bahan/ atau Downloads dipakai otomatis)
 *   Opsi jalankan: mode: ["PAPI"] (bawaan) | null (semua mode — CAPI lapangan bisa puluhan ribu),
 *     dari (ISO, bawaan "2026-01-01T00:00:00.000Z"), maksJendela (900), jarakRequestMs (800),
 *     jedaBacaMin/Maks (ms). monitoring.berhenti() menghentikan pembacaan; hasil yang sudah terbaca tetap
 *     bisa diunduh (CSV mencatat total server, jadi monitoring.py tahu snapshot-nya tidak lengkap).
 *
 * CARA KERJA
 * ----------
 * POST /analytic/api/v2/assignment/datatable-all-user-survey-periode (sama dgn tabel Data). Server tidak
 * memberi lebih dari ±1.000 baris per saringan, jadi daftar dipecah per JENDELA tanggal dibuat
 * (dateCreatedFrom/To, ISO penuh) berisi <= maksJendela dokumen, dibaca 150 per halaman; jumlah id unik
 * per jendela wajib = totalHit (tidak -> dibaca ulang / dibelah dua). Sama dgn pindah_wilayah_console.js.
 * 429/5xx/jaringan -> tunggu (Retry-After / 15 dtk x 2^n, maks 2 mnt) lalu ulang, maks 6x.
 */
(function (global) {
  "use strict";

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_monitoring_console.js
  // -------------------------------------------------------------------------
  const PANJANG_HALAMAN = 150; // datatable analytic menolak length > 150
  const BATAS_ULANG = 6;
  const HTTP_SIBUK = new Set([0, 429, 502, 503, 504]);
  const KOLOM_CSV = ["id", "kode_identitas", "nama", "status", "mode", "subsls", "petugas", "peran_petugas",
    "galat", "dibuat", "diubah", "diambil", "total_server"];

  /** "/app/surveys/<survei>/<periode>/data" -> {survei, periode} (null kalau bukan halaman itu). */
  function halamanData(path) {
    const m = /^\/app\/surveys\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? { survei: m[1], periode: m[2] } : null;
  }

  /** Kode wilayah terkecil dari region datatable (level1.fullCode ...) / detail (level_1.full_code). */
  function kodeSubsls(region) {
    let kode = "";
    let node = region;
    for (let n = 1; n <= 10 && node; n++) {
      node = node[`level${n}`] || node[`level_${n}`];
      if (node) kode = String(node.fullCode || node.full_code || kode);
    }
    return kode;
  }

  /** Item datatable -> baris snapshot (kolom KOLOM_CSV tanpa diambil/total_server); null kalau tanpa id. */
  function barisSnapshot(it) {
    if (!it || !it.id) return null;
    const mode = Array.isArray(it.mode) ? it.mode.join(",") : (it.mode || "");
    return {
      id: it.id, kode_identitas: it.codeIdentity || "", nama: it.data1 || "",
      status: it.assignmentStatusAlias || "", mode, subsls: kodeSubsls(it.region || {}),
      petugas: it.currentUserUsername || "", peran_petugas: it.currentUserSurveyRoleName || "",
      galat: it.sumError == null ? "" : it.sumError, dibuat: it.dateCreated || "", diubah: it.dateModified || "",
    };
  }

  /** Body datatable: semua dokumen satu jendela tanggal dibuat (ISO penuh; "2026-09-16" saja = 0 hasil diam-diam). */
  function bodyDaftar(periode, start, length, dari, sampai, mode) {
    const extra = { surveyPeriodId: periode, assignmentErrorStatusType: -1, assignmentStatusAlias: null };
    if (mode && mode.length) extra.mode = mode;
    if (dari) extra.dateCreatedFrom = dari;
    if (sampai) extra.dateCreatedTo = sampai;
    return {
      draw: 1, start, length,
      columns: ["id", "codeIdentity", "data1", "data2", "data3", "data4", "data5", "data6", "data7", "data8", "data9", "data10"]
        .map((data) => ({ data, orderable: true })),
      order: [], search: { value: "", regex: false }, assignmentExtraParam: extra,
    };
  }

  /** Jendela [dari, sampai] (ISO) dibelah dua di tengah waktunya. */
  function bagiJendela(dari, sampai) {
    const m = new Date(Math.floor((Date.parse(dari) + Date.parse(sampai)) / 2)).toISOString();
    return [[dari, m], [m, sampai]];
  }

  /** Lama menunggu sebelum mengulang (percobaan ke-0,1,..): Retry-After dihormati, else 15 dtk x 2^ke maks 2 mnt. */
  function jedaUlang(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Baris snapshot -> teks CSV (BOM utf-8, semua sel dikutip). */
  function keCsv(baris) {
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    return "﻿" + [KOLOM_CSV.join(","), ...baris.map((b) => KOLOM_CSV.map((k) => kutip(b[k])).join(","))].join("\n");
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { KOLOM_CSV, halamanData, kodeSubsls, barisSnapshot, bodyDaftar, bagiJendela, jedaUlang, keCsv };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const API = "/app/api";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (Math.max(a, b) - a + 1));
  const log = (...a) => console.log("%c[monitoring]", "color:#2a78d6;font-weight:bold", ...a);

  class Berhenti extends Error {
    constructor(kode, pesan) { super(pesan || kode); this.kode = kode; }
  }

  let berjalan = false;
  let hentikan = false;
  let requestTerakhir = 0;
  let hasil = null; // {dok: Map, diambil, total, info}

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "monitoring.berhenti() dipanggil");
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

  async function bacaDaftar(o, ctx, start, dari, sampai) {
    for (let ke = 0; ; ke++) {
      const tunggu = requestTerakhir + o.jarakRequestMs - Date.now();
      if (tunggu > 0) await sleep(tunggu);
      requestTerakhir = Date.now();
      let status = 0;
      let teks = "";
      let retryAfter = null;
      try {
        const res = await fetch(`${API}/analytic/api/v2/assignment/datatable-all-user-survey-periode`, {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json", "X-XSRF-TOKEN": xsrf() },
          body: JSON.stringify(bodyDaftar(ctx.periode, start, PANJANG_HALAMAN, dari, sampai, o.mode)),
        });
        status = res.status;
        teks = await res.text();
        retryAfter = res.headers.get("Retry-After");
      } catch (e) {
        teks = `fetch gagal: ${e && e.message ? e.message : e}`;
      }
      if (HTTP_SIBUK.has(status)) {
        if (ke >= BATAS_ULANG) throw new Berhenti("SERVER_SIBUK", `datatable masih HTTP ${status} setelah ${ke} kali menunggu`);
        const ms = jedaUlang(ke, retryAfter);
        log(`⏳ HTTP ${status || "gagal jaringan"} — tunggu ${Math.round(ms / 1000)} dtk (ulang ${ke + 1}/${BATAS_ULANG})`);
        await tidur(ms);
        continue;
      }
      if (status === 401 || status === 403) throw new Berhenti("SESI_DITOLAK", `HTTP ${status} — login ulang fasih-sm`);
      let j = null;
      try { j = JSON.parse(teks); } catch (e) { /* ditangani di bawah */ }
      if (status !== 200 || !j || !Array.isArray(j.searchData) || typeof j.totalHit !== "number") {
        throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${status}: ${teks.slice(0, 150)}`);
      }
      return j;
    }
  }

  async function bacaJendela(o, ctx, dari, sampai, awal, dok) {
    const ids = new Set();
    const simpan = (items) => {
      for (const it of items) {
        const b = barisSnapshot(it);
        if (b) { ids.add(b.id); dok.set(b.id, b); }
      }
    };
    simpan(awal.searchData);
    for (let start = PANJANG_HALAMAN; start < awal.totalHit; start += PANJANG_HALAMAN) {
      await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
      const j = await bacaDaftar(o, ctx, start, dari, sampai);
      if (!j.searchData.length) break;
      simpan(j.searchData);
    }
    return ids;
  }

  async function jalankan(opsi = {}) {
    const o = { mode: ["PAPI"], dari: "2026-01-01T00:00:00.000Z", maksJendela: 900, jarakRequestMs: 800,
      jedaBacaMin: 1200, jedaBacaMaks: 2500, ...opsi };
    if (berjalan) return log("Masih berjalan — tunggu selesai atau monitoring.berhenti().");
    const ctx = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !ctx) {
      return log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
    }
    berjalan = true;
    hentikan = false;
    const mulai = Date.now();
    const dok = new Map();
    const tidakUtuh = [];
    let total = 0;
    let jumlahJendela = 0; // totalHit tanpa saring tanggal bisa ikut terpotong ±1.000 -> jumlah per jendela juga dihitung
    try {
      const semua = await bacaDaftar(o, ctx, 0, null, null);
      total = semua.totalHit;
      log(`READ-ONLY: membaca ${total} dokumen ${(o.mode || []).join("/") || "semua mode"} per jendela tanggal dibuat...`);
      const antre = [[o.dari, new Date(Date.now() + 3600 * 1000).toISOString()]];
      let jendela = 0;
      while (antre.length) {
        cekHenti();
        const [a, b] = antre.shift();
        await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks));
        const awal = await bacaDaftar(o, ctx, 0, a, b);
        if (awal.totalHit > o.maksJendela && Date.parse(b) - Date.parse(a) >= 60000) {
          antre.unshift(...bagiJendela(a, b));
          continue;
        }
        let ids = await bacaJendela(o, ctx, a, b, awal, dok);
        if (ids.size < awal.totalHit) {
          const ulang = await bacaDaftar(o, ctx, 0, a, b);
          for (const id of await bacaJendela(o, ctx, a, b, ulang, dok)) ids.add(id);
          if (ids.size < awal.totalHit && awal.totalHit > PANJANG_HALAMAN && Date.parse(b) - Date.parse(a) >= 120000) {
            antre.unshift(...bagiJendela(a, b));
            continue;
          }
          if (ids.size < awal.totalHit) tidakUtuh.push(`${a}..${b}: ${ids.size}/${awal.totalHit}`);
        }
        jendela++;
        jumlahJendela += awal.totalHit;
        if (jendela % 5 === 0) log(`  ${dok.size}/${total} dokumen terbaca (${jendela} jendela)`);
      }
    } catch (e) {
      const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
      if (!(e instanceof Berhenti)) console.error(e);
    } finally {
      berjalan = false;
      total = Math.max(total, jumlahJendela);
      hasil = { dok, total, diambil: new Date(mulai).toISOString(), tidakUtuh };
      const status = {};
      for (const b of dok.values()) status[b.status || "(kosong)"] = (status[b.status || "(kosong)"] || 0) + 1;
      console.table(status);
      log(`Terbaca ${dok.size}/${total} dokumen dlm ${Math.round((Date.now() - mulai) / 1000)} dtk`
        + (tidakUtuh.length ? ` | ⚠️ ${tidakUtuh.length} jendela tidak utuh: ${tidakUtuh.join("; ")}` : "")
        + (dok.size < total ? " | ⚠️ snapshot TIDAK LENGKAP (monitoring.py tidak akan menganggap dokumen yang tak terbaca hilang)" : ""));
      log("Lanjut: monitoring.unduh() -> simpan CSV di folder bahan/ -> python monitoring/monitoring.py");
    }
    return hasil && { terbaca: hasil.dok.size, total: hasil.total };
  }

  function unduh() {
    if (!hasil || !hasil.dok.size) return log("Belum ada hasil — jalankan dulu: await monitoring.jalankan()");
    const baris = [...hasil.dok.values()].map((b) => ({ ...b, diambil: hasil.diambil, total_server: hasil.total }));
    const blob = new Blob([keCsv(baris)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `snapshot_fasih_sm_${hasil.diambil.slice(0, 16).replace(/[-:]/g, "").replace("T", "-")}Z.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} dokumen) — pindahkan ke folder bahan/ proyek.`);
  }

  global.monitoring = {
    jalankan, unduh,
    get hasil() { return hasil; },
    berhenti() { hentikan = true; log("Akan berhenti di langkah berikutnya."); },
  };
  log('Siap (READ-ONLY). Mulai: await monitoring.jalankan()  lalu  monitoring.unduh()');
})(typeof window !== "undefined" ? window : globalThis);
