/*
 * hapus_daftar_console.js — hapus (soft-delete) DAFTAR dokumen tertentu dari Console fasih-sm akun ADMIN.
 *
 * Dibangkitkan pindah_wilayah.py --sisa-wadah (dokumen KEMBAR yang tertinggal di subsls wadah sesudah
 * kembarannya dipindah ke tujuan; ketetapan user 2026-09-30: dihapus) -> hasil/hapus_daftar_console.siap.js.
 *
 * CARA PAKAI: Chrome biasa, VPN, login fasih-sm akun admin, halaman Data survei
 * (…/app/surveys/<survei>/<periode>/data) -> F12 -> Console -> tempel SELURUH isi .siap.js -> Enter.
 *     await hapusDaftar.jalankan()      // cek semua (read-only) -> ketik YA -> hapus per dokumen + verifikasi
 *     hapusDaftar.unduh()               // CSV hasil -> simpan di folder audit/
 *   Opsi jalankan({limit, jarakRequestMs}). hapusDaftar.berhenti() menghentikan di dokumen berikutnya.
 *
 * KESELAMATAN (per dokumen, dari detail SEGAR get-by-assignment-id):
 *   - dokumen masih ada, masih di subsls `wadah` yang tercatat, namanya cocok dgn daftar;
 *   - kalau berkembar: kembarannya MASIH ADA, id-nya beda, dan sudah di subsls `tujuan` (tidak pernah menghapus
 *     salinan terakhir sebuah usaha);
 *   - gagal cek -> dilewati (tidak dihapus). Sesudah hapus: detail wajib 403 dgn sesi hidup (HILANG) ->
 *     TERHAPUS_TERVERIFIKASI; selain itu batch BERHENTI.
 *   - Endpoint = pola yang terekam 2026-09-26 (Chrome user): POST /assignment-general/api/assignment/soft-delete/{ID}.
 */
(function (global) {
  "use strict";
  // [{id, nama: "NAMA A / NAMA B", wadah: subsls sekarang, kembar: id kembaran ("" = tanpa), tujuan: subsls kembaran}]
  const DAFTAR = /*__DAFTAR__*/[];
  const KONFIG = /*__KONFIG__*/{};
  const API = "/app/api";
  const KUNCI_HASIL = "hapusDaftar.hasil.v1";
  const POLA_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  // ---------------- logika murni (diuji: node tests/test_hapus_daftar_console.js)
  const norm = (s) => String(s == null ? "" : s).split(/\s+/).filter(Boolean).join(" ").toUpperCase();
  const namaDariKode = (t) => norm(String(t == null ? "" : t).replace(/^\s*\d{16}\s*-\s*/, ""));

  function kodeRegion(region) {
    const hasil = [];
    let node = region;
    for (let n = 1; n <= 10 && node; n++) {
      node = node[`level_${n}`] || node[`level${n}`];
      if (node) hasil.push(String(node.full_code || node.fullCode || ""));
    }
    return hasil.filter(Boolean).pop() || "";
  }

  /** Respons detail -> {ada, kode, nama, alias} | {ada:false} | null (bentuk tidak dikenal).
   *  {success:true, data:null} = dokumen TIDAK ADA (terbukti 2026-09-30: dokumen yang sudah dihapus dijawab begitu,
   *  bukan hanya 403 kosong seperti rekaman 2026-09-26). */
  function ringkasDetail(j) {
    if (j && j.success === true && j.data == null) return { ada: false };
    const d = j && j.success === true ? j.data : null;
    if (!d || !d.region) return null;
    return { ada: true, kode: kodeRegion(d.region), nama: namaDariKode(d.code_identity || d.codeIdentity || ""),
      alias: d.assignment_status_alias || d.assignmentStatusAlias || "" };
  }

  /** Keputusan cek sebelum hapus -> {ok, status, pesan}. `dok`/`kem` = ringkasDetail | {ada:false} . */
  function nilaiCek(e, dok, kem) {
    if (!POLA_ID.test(e.id || "")) return { ok: false, status: "ID_TIDAK_SAH", pesan: e.id };
    if (!dok || !dok.ada) return { ok: false, status: "SUDAH_TIDAK_ADA", pesan: "dokumen tidak ada lagi" };
    if (dok.kode !== e.wadah) return { ok: false, status: "PINDAH_TEMPAT", pesan: `di ${dok.kode}, bukan ${e.wadah}` };
    const sah = String(e.nama || "").split(" / ").map(norm).filter(Boolean);
    if (!sah.includes(dok.nama)) return { ok: false, status: "NAMA_BEDA", pesan: `server '${dok.nama}' vs daftar '${sah.join(" / ")}'` };
    if (e.kembar) {
      if (e.kembar.toLowerCase() === e.id.toLowerCase()) return { ok: false, status: "KEMBAR_SAMA", pesan: "kembaran = dirinya" };
      if (!kem || !kem.ada) return { ok: false, status: "KEMBARAN_TIDAK_ADA", pesan: `kembaran ${e.kembar.slice(0, 8)} tidak terbaca` };
      if (kem.kode !== e.tujuan) return { ok: false, status: "KEMBARAN_BELUM_DI_TUJUAN", pesan: `kembaran di ${kem.kode}, bukan ${e.tujuan}` };
    }
    return { ok: true, status: "SIAP_HAPUS", pesan: e.kembar ? `kembaran ${e.kembar.slice(0, 8)} di ${e.tujuan}` : "tanpa kembaran" };
  }

  // ---------------- browser
  const log = (...a) => console.log("%c[hapusDaftar]", "color:#b91c1c;font-weight:bold", ...a);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let hentikan = false;
  let berjalan = false;
  let akhir = 0;
  const xsrf = () => {
    const c = document.cookie.split("; ").find((x) => x.startsWith("XSRF-TOKEN="));
    return c ? decodeURIComponent(c.slice("XSRF-TOKEN=".length)) : "";
  };
  async function minta(o, method, url) {
    const tunggu = akhir + o.jarakRequestMs - Date.now();
    if (tunggu > 0) await sleep(tunggu);
    akhir = Date.now();
    for (let ke = 0; ; ke++) {
      let r;
      try {
        const res = await fetch(API + url, { method, credentials: "include", headers: { "X-XSRF-TOKEN": xsrf() } });
        r = { status: res.status, teks: await res.text() };
      } catch (e) {
        r = { status: 0, teks: String(e && e.message) };
      }
      if (![0, 429, 502, 503, 504].includes(r.status) || ke >= 5 || method !== "GET") return r;
      log(`⏳ HTTP ${r.status || "gagal jaringan"} di ${url.split("?")[0]} — tunggu ${15 * 2 ** ke} dtk`);
      await sleep(15000 * 2 ** ke);
    }
  }
  const json = (t) => { try { return JSON.parse(t); } catch (e) { return null; } };
  async function sesiHidup(o, survei) {
    return (await minta(o, "GET", `/survey/api/v1/survey-roles?surveyId=${survei}`)).status === 200;
  }
  async function detail(o, survei, id) {
    const r = await minta(o, "GET", `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${id}`);
    if (r.status === 403) {
      if (await sesiHidup(o, survei)) return { ada: false };
      throw new Error("SESI_DITOLAK: detail 403 & sesi mati — login ulang");
    }
    if (r.status === 401) throw new Error("SESI_DITOLAK: HTTP 401 — login ulang");
    const d = ringkasDetail(json(r.teks));
    if (!d) throw new Error(`RESPONS_TIDAK_DIKENAL: detail ${id.slice(0, 8)} HTTP ${r.status}: ${r.teks.slice(0, 120)}`);
    return d;
  }
  function muat() { try { return JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}"); } catch (e) { return {}; } }
  function catat(e, status, pesan) {
    const h = muat();
    h[e.id] = { w: new Date().toISOString().slice(0, 19), status, pesan: String(pesan || "").slice(0, 200) };
    try { localStorage.setItem(KUNCI_HASIL, JSON.stringify(h)); } catch (x) { /* tidak fatal */ }
  }

  async function jalankan(opsi = {}) {
    const o = { limit: null, jarakRequestMs: 300, ...(KONFIG.opsi || {}), ...opsi };
    const m = /^\/app\/surveys\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/data\/?$/i.exec(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !m) return log("⛔ Buka halaman Data survei fasih-sm dulu, lalu tempel ulang.");
    if (berjalan) return log("Masih berjalan.");
    berjalan = true;
    hentikan = false;
    const survei = m[1];
    const hitung = {};
    const tambah = (s) => { hitung[s] = (hitung[s] || 0) + 1; };
    try {
      const sudah = muat();
      const daftar = DAFTAR.filter((e) => !(sudah[e.id] && sudah[e.id].status === "TERHAPUS_TERVERIFIKASI"));
      log(`Cek ${daftar.length} dokumen (read-only)...`);
      const siap = [];
      for (const e of daftar) {
        if (hentikan) throw new Error("DIHENTIKAN_PENGGUNA");
        const dok = await detail(o, survei, e.id);
        const kem = e.kembar ? await detail(o, survei, e.kembar) : null;
        const c = nilaiCek(e, dok, kem);
        tambah(c.status);
        if (c.ok) siap.push(e);
        else { catat(e, c.status, c.pesan); log(`  lewati ${e.id.slice(0, 8)} ${e.nama.slice(0, 40)}: ${c.status} ${c.pesan}`); }
      }
      log("Hasil cek:", { ...hitung });
      const maks = o.limit ? Math.min(o.limit, siap.length) : siap.length;
      if (!maks) return log("Tidak ada yang siap dihapus.");
      if (prompt(`HAPUS ${maks} dokumen (soft-delete, hanya admin pusat yang bisa memulihkan). Ketik YA:`) !== "YA") {
        return log("Dibatalkan.");
      }
      let n = 0;
      for (const e of siap.slice(0, maks)) {
        if (hentikan) throw new Error("DIHENTIKAN_PENGGUNA");
        const r = await minta(o, "POST", `/assignment-general/api/assignment/soft-delete/${e.id}`);
        const j = json(r.teks);
        if (r.status < 200 || r.status >= 300 || (j && j.success === false)) {
          catat(e, "GAGAL_HAPUS", `HTTP ${r.status}: ${r.teks.slice(0, 150)}`);
          throw new Error(`GAGAL_HAPUS ${e.id.slice(0, 8)}: HTTP ${r.status} ${r.teks.slice(0, 150)}`);
        }
        const sesudah = await detail(o, survei, e.id);
        if (sesudah.ada) {
          catat(e, "HAPUS_TIDAK_TERVERIFIKASI", `masih terbaca (${sesudah.alias}, ${sesudah.kode})`);
          throw new Error(`HAPUS_TIDAK_TERVERIFIKASI ${e.id.slice(0, 8)}: detail masih terbaca`);
        }
        catat(e, "TERHAPUS_TERVERIFIKASI", e.kembar ? `kembaran ${e.kembar} dipertahankan` : "");
        n++;
        if (n % 10 === 0 || n === maks) log(`  ${n}/${maks} terhapus & terverifikasi`);
      }
      log(`✅ ${n} dokumen terhapus. hapusDaftar.unduh() -> simpan CSV di audit/.`);
    } catch (err) {
      log(`⛔ ${err && err.message ? err.message : err}`);
    } finally {
      berjalan = false;
    }
  }

  function unduh() {
    const h = muat();
    const kolom = ["waktu", "id", "nama", "wadah", "kembar", "tujuan_kembar", "status", "pesan"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = DAFTAR.filter((e) => h[e.id]).map((e) => [h[e.id].w, e.id, e.nama, e.wadah, e.kembar, e.tujuan,
      h[e.id].status, h[e.id].pesan].map(kutip).join(","));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" }));
    a.download = `hapus_daftar_${new Date().toISOString().slice(0, 19).replace(/[-:]/g, "").replace("T", "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} baris)`);
  }

  const murni = { norm, namaDariKode, kodeRegion, ringkasDetail, nilaiCek };
  if (typeof module !== "undefined" && module.exports) module.exports = murni;
  global.hapusDaftar = { jalankan, unduh, daftar: DAFTAR, _murni: murni,
    berhenti() { hentikan = true; log("Berhenti di dokumen berikutnya."); } };
  if (typeof document !== "undefined") {
    log(`Siap: ${DAFTAR.length} dokumen${KONFIG.dibuat ? ` (dibuat ${KONFIG.dibuat})` : ""}. Jalankan: await hapusDaftar.jalankan()`);
  }
})(typeof window !== "undefined" ? window : globalThis);
