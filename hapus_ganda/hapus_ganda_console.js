/*
 * hapus_ganda_console.js — hapus dokumen GANDA (satu baris sheet, >= 2 assignment) dari
 * DevTools Console Chrome, akun ADMIN fasih-sm, di halaman Data survei:
 *   https://fasih-sm.bps.go.id/app/surveys/<survei>/<periode>/data
 *
 * JANGAN tempel berkas ini langsung. Jalankan dulu (dari root proyek):
 *     python hapus_ganda/hapus_ganda.py
 * -> hapus_ganda_console.siap.js (TARGET = grup dari audit gabungan). Panduan langkah demi
 * langkah: docs/PANDUAN_HAPUS_GANDA.md.
 *
 * ALUR
 * ----
 * 1. hapusGanda.cek()          READ-ONLY. Detail SEGAR tiap dokumen tiap grup
 *                              (GET get-by-assignment-id) -> keputusan per dokumen:
 *                              PERTAHANKAN / HAPUS / PERIKSA / TIDAK_TERBACA.
 * 2. hapusGanda.rekam()        Endpoint "Hapus Assignment" BELUM dipetakan & tidak ditebak.
 *                              Skrip memasang penyadap, lalu ANDA menghapus SATU dokumen
 *                              ber-keputusan HAPUS lewat menu ⋮ -> "Hapus Assignment".
 *                              Request itu direkam jadi pola, penghapusannya dibuktikan lewat
 *                              detail (sebelum vs sesudah). Selama merekam, request ubah
 *                              (bukan GET) yang memuat id dokumen yang TIDAK boleh dihapus
 *                              DIBLOKIR — salah klik baris tidak akan menghapus yang benar.
 *                              Cadangan: hapusGanda.pakaiContoh(`<"Copy as fetch" dari Network>`).
 * 3. hapusGanda.jalankan({mode: "hapus", limit: 1})  lalu tanpa limit / limit besar.
 *
 * KESELAMATAN
 * -----------
 * - Hanya id di TARGET, dan (bawaan) hanya dokumen bermode PAPI — mode dibaca SEGAR dari detail,
 *   cadangannya tabel Data (datatable); mode tak terbaca / CAPI / CAWI -> BUKAN_PAPI, tidak
 *   disentuh & tidak ikut menentukan yang dipertahankan. {hanyaPapi: false} = semua mode.
 * - SATU dokumen per grup dipertahankan (ketetapan user 2026-09-24): status tertinggi
 *   (APPROVED > SUBMITTED > REJECTED > DRAFT) -> SUBMITTED+DRAFT: DRAFT dihapus;
 *   SUBMITTED+SUBMITTED: salah satu dihapus; DRAFT+DRAFT: yang ber-GALAT dihapus, keduanya
 *   bersih -> salah satu. Seri -> galat lebih sedikit, lalu yang ditunjuk audit, lalu jawaban
 *   bersih lebih banyak. DRAFT seri yang jumlah galatnya tidak terbaca -> PERIKSA. Yang dihapus
 *   harus bernama SAMA dgn yang dipertahankan. APPROVED TIDAK PERNAH dihapus;
 *   {izinkanHapusTerkirim: false} = SUBMITTED juga tidak. Dokumen di luar audit hanya dgn
 *   {izinkanLuarAudit: true}. Galat & jawaban bersih: detail, cadangan tabel Data.
 * - Tepat sebelum tiap hapus: detail dokumen yang dihapus & yang dipertahankan dibaca ulang.
 * - Sesudah tiap hapus: detail dibaca ulang & harus cocok dgn "tanda terhapus" hasil rekam,
 *   DAN dokumen yang dipertahankan harus masih terbaca (bukti sesi masih sah). Tidak cocok ->
 *   DIHAPUS_BELUM_TERVERIFIKASI -> batch berhenti.
 * - Mode hapus pertama kali dibatasi limit 1 sampai ada satu DIHAPUS_TERVERIFIKASI oleh skrip.
 * - Hasil di localStorage; hapusGanda.unduh() -> ganda_dihapus_<waktu>.csv. Taruh di folder
 *   proyek: gabung_audit.py tidak lagi mendaftar dokumen itu sbg ganda.
 */
(function () {
  "use strict";

  const TARGET = /*__TARGET__*/[];
  const SURVEI = /*__SURVEI__*/"";
  const PERIODE = /*__PERIODE__*/"";

  const STATUS_BERHENTI_SEGERA = new Set([
    "SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL", "DIHAPUS_BELUM_TERVERIFIKASI", "RATE_LIMIT", "SERVER_SIBUK_TERUS",
    "PEMBANDING_HILANG",
  ]);
  const HTTP_SIBUK = new Set([0, 502, 503, 504]);
  const POLA_ID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  // -------------------------------------------------------------------------
  // Logika murni (diuji tests/test_hapus_ganda_console.js)
  // -------------------------------------------------------------------------
  const norm = (s) => String(s == null ? "" : s).split(/\s+/).filter(Boolean).join(" ").toUpperCase();

  /** "5108060006000224 - WARUNG (MADE)" -> "WARUNG (MADE)" (dinormalkan). */
  const namaDariKode = (teks) => norm(String(teks == null ? "" : teks).replace(/^\s*\d{16}\s*-\s*/, ""));

  /** Status server -> peringkat (APPROVED 4 > SUBMITTED 3 > REJECTED 2 > lainnya 1 > kosong 0).
   *  Kembar Python: gabung_audit.peringkat_status(). */
  function peringkatStatus(alias) {
    const t = String(alias || "").trim().toUpperCase();
    if (!t) return 0;
    if (t.startsWith("APPROVED")) return 4;
    if (t.startsWith("SUBMITTED")) return 3;
    if (t.startsWith("REJECTED")) return 2;
    return 1;
  }

  /** "/app/surveys/<survei>/<periode>/data" -> {survei, periode}; null kalau bukan. */
  function halamanData(path) {
    const m = /^\/app\/surveys\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? { survei: m[1], periode: m[2] } : null;
  }

  function jenisSementara(httpStatus) {
    if (httpStatus === 429) return "RATE_LIMIT";
    return HTTP_SIBUK.has(httpStatus) ? "SERVER_SIBUK" : null;
  }

  function jedaRateLimit(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Mode pendataan dari detail/item datatable: field ber-nama "mode" (string atau array,
   *  mis. "mode":["PAPI"] di list API). "" kalau tidak ada; >1 mode -> digabung "CAPI+PAPI". */
  function modeDari(d) {
    if (!d || typeof d !== "object") return "";
    const nilai = [];
    for (const [k, v] of Object.entries(d)) {
      if (!/mode/i.test(k)) continue;
      for (const x of [].concat(v)) if (typeof x === "string") nilai.push(x.trim().toUpperCase());
    }
    return [...new Set(nilai.filter((x) => ["CAPI", "PAPI", "CAWI"].includes(x)))].sort().join("+");
  }

  /** Angka dari field yang namanya cocok `pola` (mis. /^sum_?error$/i); null kalau tidak ada. */
  function angkaDari(d, pola) {
    if (!d || typeof d !== "object") return null;
    const k = Object.keys(d).find((x) => pola.test(x));
    const n = k == null ? NaN : Number(d[k]);
    return Number.isFinite(n) ? n : null;
  }

  /** Respons detail get-by-assignment-id {status, j} -> {ada, alias, nama, kode, mode, galat, bersih, pengguna, data, pesan}.
   *  `ada` = dokumen masih terbaca normal (HTTP 200, success true, data berisi). */
  function nilaiDetail(r) {
    const j = r && r.j;
    const d = r && r.status === 200 && j && j.success === true && j.data && typeof j.data === "object" ? j.data : null;
    if (!d) {
      const pesan = j && (j.message || j.error) ? String(j.message || j.error) : String((r && r.teks) || "").slice(0, 120);
      return { ada: false, alias: "", nama: "", kode: "", mode: "", galat: null, bersih: null, pengguna: "", data: null,
        http: r ? r.status : 0, success: j ? j.success : undefined, pesan: `HTTP ${r ? r.status : "?"} ${pesan}`.trim() };
    }
    const kode = /^\s*(\d{16})\s*-/.exec(String(d.code_identity || "")) || [];
    return { ada: true, alias: d.assignment_status_alias || "", nama: namaDariKode(d.code_identity || d.data1 || ""),
      kode: kode[1] || "", mode: modeDari(d), galat: angkaDari(d, /^sum_?error$/i), bersih: angkaDari(d, /^sum_?clean$/i),
      pengguna: d.current_user_username || "", data: d, http: r.status, success: true, pesan: "" };
  }

  /** Keputusan per dokumen SATU grup, sejajar `dok`.
   *  dok: {id, ada, alias, nama, mode, galat, bersih (null = tidak diketahui), c (ditunjuk audit),
   *        l (di luar audit), x (URL diklaim baris lain)}
   *  opsi: {hanyaPapi, izinkanHapusTerkirim, izinkanLuarAudit}
   *  -> [{keputusan: PERTAHANKAN|HAPUS|PERIKSA|TIDAK_TERBACA|BUKAN_PAPI, alasan}]. Dokumen
   *  BUKAN_PAPI (hanyaPapi) tidak dihapus & tidak ikut menentukan yang dipertahankan.
   *  Kembar Python (tanpa nama & `ada`): gabung_audit.usulan_grup(). */
  function putuskanGrup(dok, opsi = {}) {
    const hasil = dok.map(() => null);
    const valid = [];
    dok.forEach((d, i) => {
      if (!d.ada) hasil[i] = { keputusan: "TIDAK_TERBACA", alasan: d.pesan || "detail tidak terbaca" };
      else if (opsi.hanyaPapi && d.mode !== "PAPI") {
        hasil[i] = { keputusan: "BUKAN_PAPI", alasan: d.mode ? `mode ${d.mode}` : "mode tidak terbaca (detail & tabel Data)" };
      } else if (peringkatStatus(d.alias) === 0) hasil[i] = { keputusan: "PERIKSA", alasan: "status kosong di detail" };
      else valid.push(i);
    });
    if (valid.length < 2) {
      valid.forEach((i) => { hasil[i] = { keputusan: "PERTAHANKAN", alasan: "tinggal satu dokumen terbaca di grup ini" }; });
      return hasil;
    }
    const hapusTerkirim = opsi.izinkanHapusTerkirim !== false;
    const kunci = (i) => [peringkatStatus(dok[i].alias), -(dok[i].galat || 0), dok[i].c ? 1 : 0, dok[i].bersih || 0,
      dok[i].l ? 0 : 1, -i];
    const lebih = (a, b) => { const ka = kunci(a), kb = kunci(b); for (let k = 0; k < ka.length; k++) { if (ka[k] !== kb[k]) return ka[k] > kb[k]; } return false; };
    const simpan = valid.reduce((a, b) => (lebih(b, a) ? b : a));
    const pSimpan = peringkatStatus(dok[simpan].alias);
    const S = dok[simpan];
    const keterangan = (d) => (d.galat != null ? `${d.galat} galat` : "galat ?") + (d.bersih != null ? `, ${d.bersih} bersih` : "");
    for (const i of valid) {
      const d = dok[i];
      const p = peringkatStatus(d.alias);
      if (i === simpan) hasil[i] = { keputusan: "PERTAHANKAN", alasan: `status tertinggi (${d.alias})` };
      else if (norm(d.nama) !== norm(dok[simpan].nama)) {
        hasil[i] = { keputusan: "PERIKSA", alasan: `nama beda dgn yang dipertahankan ('${d.nama}' vs '${dok[simpan].nama}')` };
      } else if (d.x) hasil[i] = { keputusan: "PERIKSA", alasan: "URL ini juga tercatat utk baris lain" };
      else if (d.l && !opsi.izinkanLuarAudit) {
        hasil[i] = { keputusan: "PERIKSA", alasan: "tidak tercatat di audit — pakai izinkanLuarAudit: true kalau yakin" };
      } else if (p >= 4) hasil[i] = { keputusan: "PERIKSA", alasan: "APPROVED — tidak pernah dihapus otomatis" };
      else if (p === 3 && !hapusTerkirim) {
        hasil[i] = { keputusan: "PERIKSA", alasan: "SUBMITTED — dimatikan dgn izinkanHapusTerkirim: false" };
      } else if (p > pSimpan) hasil[i] = { keputusan: "PERIKSA", alasan: "status lebih tinggi dari yang dipertahankan" };
      else if (p === 1 && pSimpan === 1 && (d.galat == null || S.galat == null)) {
        hasil[i] = { keputusan: "PERIKSA", alasan: "DRAFT ganda tapi jumlah galat tidak terbaca — tidak bisa memilih yang ber-galat" };
      } else if (p === pSimpan) {
        hasil[i] = { keputusan: "HAPUS", alasan: `${d.alias} ganda (${keterangan(d)}) — dipertahankan ${S.id.slice(0, 8)} (${keterangan(S)})` };
      } else hasil[i] = { keputusan: "HAPUS", alasan: `${d.alias} ganda dari ${S.id.slice(0, 8)} (${S.alias})` };
    }
    return hasil;
  }

  /** Id yang muncul di teks (dari himpunan `ids`, tanpa beda huruf besar). */
  function idDalam(teks, ids) {
    const ada = new Set(String(teks || "").toLowerCase().match(POLA_ID) || []);
    return [...ids].filter((id) => ada.has(String(id).toLowerCase()));
  }

  /** URL absolut/relatif -> path "/app/api/..." (null kalau bukan API fasih-sm yang sama). */
  function pathApi(url) {
    let u = String(url || "");
    const m = /^https?:\/\/([^/]+)(\/.*)$/i.exec(u);
    if (m) {
      if (!/(^|\.)fasih-sm\.bps\.go\.id$/i.test(m[1])) return null;
      u = m[2];
    }
    return u.startsWith("/app/api/") ? u : null;
  }

  /** Request yang direkam -> pola {method, url, body, contentType} dgn "{{ID}}" menggantikan `id`.
   *  Ditolak (Berhenti) kalau: GET, bukan API fasih-sm, id tidak muncul, atau memuat id lain dari
   *  `idLain` (mis. dokumen yang dipertahankan). */
  function templateDari(req, id, idLain = []) {
    const method = String(req.method || "GET").toUpperCase();
    if (method === "GET") throw new Berhenti("POLA_DITOLAK", "request GET bukan penghapusan");
    const path = pathApi(req.url);
    if (!path) throw new Berhenti("POLA_DITOLAK", `bukan API fasih-sm: ${String(req.url).slice(0, 120)}`);
    const body = req.body == null ? null : String(req.body);
    const gabung = `${path}\n${body || ""}`;
    if (!idDalam(gabung, [id]).length) throw new Berhenti("POLA_DITOLAK", `id ${id} tidak ada di request`);
    const lain = idDalam(gabung, idLain.filter((x) => x.toLowerCase() !== id.toLowerCase()));
    if (lain.length) throw new Berhenti("POLA_DITOLAK", `request juga memuat id lain ${lain.join(", ")}`);
    const ganti = (t) => t.replace(new RegExp(id, "gi"), "{{ID}}");
    return { method, url: ganti(path), body: body == null ? null : ganti(body), contentType: req.contentType || "" };
  }

  function isiTemplate(tpl, id) {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id || "")) {
      throw new Berhenti("POLA_DITOLAK", `id tidak sah: ${id}`);
    }
    if (!tpl || (!String(tpl.url).includes("{{ID}}") && !String(tpl.body || "").includes("{{ID}}"))) {
      throw new Berhenti("POLA_DITOLAK", "pola tidak memuat {{ID}}");
    }
    return { method: tpl.method, url: tpl.url.split("{{ID}}").join(id),
      body: tpl.body == null ? null : tpl.body.split("{{ID}}").join(id), contentType: tpl.contentType || "" };
  }

  /** Teks "Copy as fetch" (DevTools > Network > klik kanan request) -> {method, url, body, contentType}. */
  function uraiCopyAsFetch(teks) {
    const m = /fetch\(\s*("(?:[^"\\]|\\.)*")\s*,\s*(\{[\s\S]*\})\s*\)\s*;?\s*$/.exec(String(teks || "").trim());
    if (!m) throw new Berhenti("POLA_DITOLAK", "bukan teks 'Copy as fetch' (fetch(\"url\", {...}))");
    let url, o;
    try {
      url = JSON.parse(m[1]);
      o = JSON.parse(m[2]);
    } catch (e) {
      throw new Berhenti("POLA_DITOLAK", `teks 'Copy as fetch' tidak terbaca: ${e.message}`);
    }
    const h = o.headers || {};
    const ct = Object.keys(h).find((k) => k.toLowerCase() === "content-type");
    return { method: String(o.method || "GET").toUpperCase(), url, body: o.body == null ? null : String(o.body),
      contentType: ct ? h[ct] : "" };
  }

  /** Bukti terhapus dari detail SEBELUM (terbaca) & SESUDAH penghapusan manual:
   *  {cara: "HILANG"} = detail tidak lagi terbaca; {cara: "FIELD", kunci, nilai} = masih terbaca
   *  tapi ada penanda hapus/aktif/status yang berubah. null = tidak terbukti. */
  function sidikTerhapus(sebelum, sesudah) {
    if (!sebelum || !sebelum.ada || !sesudah) return null;
    if (!sesudah.ada) return { cara: "HILANG", http: sesudah.http };
    const a = sebelum.data || {}, b = sesudah.data || {};
    const berubah = Object.keys(b).filter((k) => /delet|hapus|activ|aktif|remov|status/i.test(k)
      && (b[k] === null || typeof b[k] !== "object") && JSON.stringify(a[k]) !== JSON.stringify(b[k]));
    if (!berubah.length) return null;
    const k = berubah.find((x) => /delet|hapus|remov/i.test(x)) || berubah[0];
    return { cara: "FIELD", kunci: k, nilai: b[k] };
  }

  function cocokTerhapus(sidik, sesudah) {
    if (!sidik || !sesudah) return false;
    if (sidik.cara === "HILANG") return !sesudah.ada;
    if (sidik.cara === "FIELD") return !!(sesudah.ada && sesudah.data && JSON.stringify(sesudah.data[sidik.kunci]) === JSON.stringify(sidik.nilai));
    return false;
  }

  /** Mode hapus pertama kali: limit wajib 1 sampai ada bukti penghapusan oleh skrip. */
  function limitDiizinkan(limit, adaBuktiSkrip) {
    return adaBuktiSkrip || limit === 1;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, SURVEI, PERIODE, STATUS_BERHENTI_SEGERA, norm, namaDariKode, peringkatStatus, halamanData, modeDari, angkaDari,
      jenisSementara, jedaRateLimit, nilaiDetail, putuskanGrup, idDalam, pathApi, templateDari, isiTemplate,
      uraiCopyAsFetch, sidikTerhapus, cocokTerhapus, limitDiizinkan, Berhenti,
    };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya di browser)
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "hapusGanda.hasil.v1";
  const KUNCI_POLA = "hapusGanda.pola.v1";
  const API = "/app/api";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const log = (...a) => console.log("%c[hapusGanda]", "color:#c62828;font-weight:bold", ...a);

  let hentikan = false;
  let berjalan = false;
  let keputusanTerakhir = [];     // hasil cek terakhir: [{g, b, n, id, keputusan, alasan, alias, nama}]
  let penyadap = null;

  const bacaLS = (k, awal) => { try { return JSON.parse(localStorage.getItem(k) || "null") || awal; } catch (e) { return awal; } };
  const tulisLS = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { log("⚠️ localStorage gagal — segera hapusGanda.unduh()", e); } };
  const hasil = () => bacaLS(KUNCI_HASIL, {});
  function catat(id, isi) {
    const h = hasil();
    h[id] = { ...(h[id] || {}), ...isi, waktu: new Date().toISOString() };
    tulisLS(KUNCI_HASIL, h);
  }
  const pola = () => bacaLS(KUNCI_POLA, null);

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "hapusGanda.berhenti() dipanggil");
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

  // fetch ASLI — disimpan sebelum penyadap dipasang, supaya request skrip sendiri tidak tersadap.
  const fetchAsli = window.fetch.bind(window);
  const JARAK_MIN_REQUEST_MS = 500;
  let requestTerakhir = 0;

  async function minta(method, url, body, contentType) {
    const tunggu = requestTerakhir + JARAK_MIN_REQUEST_MS - Date.now();
    if (tunggu > 0) await sleep(tunggu);
    requestTerakhir = Date.now();
    const init = { method, credentials: "include", headers: { "X-XSRF-TOKEN": xsrf() } };
    if (body != null) {
      init.headers["Content-Type"] = contentType || "application/json";
      init.body = body;
    }
    try {
      const res = await fetchAsli(url.startsWith("/app/") ? url : API + url, init);
      return { status: res.status, teks: await res.text(), retryAfter: res.headers.get("Retry-After") };
    } catch (e) {
      return { status: 0, teks: `fetch gagal: ${e && e.message ? e.message : e}`, retryAfter: null };
    }
  }

<<<<<<< HEAD
  /** Sesi admin masih hidup? Dibaca ulang detail dokumen lain yang terakhir terbaca, cadangan
   *  tabel Data (1 baris). Dipakai memisahkan 403 "dokumen ini" dari 403 "sesi habis". */
  let idTerbaca = "";
  async function sesiHidup(kecuali) {
    if (idTerbaca && idTerbaca !== kecuali) {
      const r = await minta("GET", `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${encodeURIComponent(idTerbaca)}`);
      let j = null;
      try { j = JSON.parse(r.teks); } catch (e) { /* bukan JSON */ }
      if (r.status === 200 && j && j.success === true) return true;
    }
    const r = await minta("POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode", JSON.stringify({
      draw: 1, start: 0, length: 1, columns: [{ data: "id", orderable: true }], order: [],
      search: { value: "", regex: false },
      assignmentExtraParam: { surveyPeriodId: PERIODE, assignmentErrorStatusType: -1, assignmentStatusAlias: null },
    }));
    return r.status === 200;
  }

  /** Detail satu dokumen; galat sementara ditunggu & diulang. 401 -> Berhenti SESI_DITOLAK.
   *  403 dua arti: dokumen SUDAH DIHAPUS / tak terjangkau (kejadian 2026-09-24: detail DRAFT
   *  ganda yang baru dihapus lewat rekam() dijawab 403) ATAU sesi/akses admin ditolak. Karena
   *  itu sesi dibuktikan dulu lewat dokumen/tabel lain: hidup -> dokumen ini "tidak ada"
   *  (ada:false, http 403 = tanda HILANG); mati -> Berhenti (jangan sampai SEMUA dokumen jadi
   *  TIDAK_TERBACA diam-diam). */
=======
  /** Detail satu dokumen; galat sementara ditunggu & diulang. 401 -> Berhenti (jelas: sesi habis).
   *  403 di get-by-assignment-id DUA ARTI berbeda (dibedakan dari body, dibuktikan 2026-09-24):
   *  - body ADA isi (mis. "Invalid CSRF Token", lihat buka_wilayah_console.js) -> sesi/CSRF
   *    beneran ditolak -> Berhenti, jangan lanjut menebak-nebak dokumen lain.
   *  - body KOSONG -> dokumen ini sendiri yang sudah tidak ada/di luar akses (mis. sudah
   *    dihapus manual duluan) -> BUKAN soal sesi; lolos ke nilaiDetail spt HTTP lain (ada:false,
   *    TIDAK_TERBACA), grup lain tetap diperiksa. Memperlakukan ini sbg Berhenti membuat cek()
   *    berhenti total di dokumen basi pertama dari daftar_ganda.csv yang belum disegarkan. */
>>>>>>> baa3a14a20ba4b2aeb65172acd924b76d0586a77
  async function bacaDetail(id) {
    const url = `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${encodeURIComponent(id)}`;
    for (let ke = 0; ; ke++) {
      const r = await minta("GET", url);
      const jenis = jenisSementara(r.status);
      if (jenis) {
        if (ke >= 6) throw new Berhenti(jenis === "RATE_LIMIT" ? "RATE_LIMIT" : "SERVER_SIBUK_TERUS", `detail ${id} masih HTTP ${r.status}`);
        const t = jedaRateLimit(ke, r.retryAfter);
        log(`⏳ detail HTTP ${r.status || "gagal jaringan"} — tunggu ${Math.round(t / 1000)} dtk (ulang ${ke + 1}/6)`);
        await tidur(t);
        continue;
      }
<<<<<<< HEAD
      if (r.status === 401 || (r.status === 403 && !(await sesiHidup(id)))) {
        throw new Berhenti("SESI_DITOLAK", `detail HTTP ${r.status} — login ulang fasih-sm (akun admin, XSRF-TOKEN segar)`);
=======
      if (r.status === 401 || (r.status === 403 && String(r.teks || "").trim())) {
        throw new Berhenti("SESI_DITOLAK", `detail HTTP ${r.status} — login ulang fasih-sm (akun admin, XSRF-TOKEN segar): ${String(r.teks || "").slice(0, 150)}`);
>>>>>>> baa3a14a20ba4b2aeb65172acd924b76d0586a77
      }
      if (r.status === 403) {
        return nilaiDetail({ status: 403, j: { success: false,
          message: "dokumen tidak bisa dibuka akun ini (sudah dihapus / di luar akses) — sesi admin masih aktif" }, teks: "" });
      }
      let j = null;
      try { j = JSON.parse(r.teks); } catch (e) { /* bukan JSON: dianggap tidak terbaca */ }
      const hasil = nilaiDetail({ status: r.status, j, teks: r.teks });
      if (hasil.ada) idTerbaca = id;
      return hasil;
    }
  }

  function pastikanHalaman() {
    const h = halamanData(location.pathname);
    if (!h) throw new Berhenti("HALAMAN_SALAH", "buka halaman Data survei: .../app/surveys/<survei>/<periode>/data");
    if ((SURVEI && h.survei !== SURVEI) || (PERIODE && h.periode !== PERIODE)) {
      throw new Berhenti("HALAMAN_SALAH", `halaman ini survei/periode ${h.survei}/${h.periode}, TARGET dibuat utk ${SURVEI}/${PERIODE}`);
    }
    if (!TARGET.length) throw new Berhenti("TARGET_KOSONG", "TARGET kosong — tempel hapus_ganda_console.siap.js, bukan template");
  }

  /** Cadangan kalau detail tidak memuat mode / galat / jawaban bersih: tabel Data (datatable
   *  analytic) dicari dgn nama dokumen -> {id: {mode, galat, bersih}}. {} kalau gagal. Satu
   *  pencarian per nama (di-cache), jarak antar-pencarian >= 1,5 dtk (rate limit datatable). */
  const cacheDaftar = new Map();
  let cariTerakhir = 0;
  async function infoDaftar(nama) {
    if (cacheDaftar.has(nama)) return cacheDaftar.get(nama);
    let info = {};
    try {
      for (let ke = 0; ke < 6; ke++) {
        const jeda = cariTerakhir + 1500 - Date.now();
        if (jeda > 0) await tidur(jeda);
        cariTerakhir = Date.now();
        const r = await minta("POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode", JSON.stringify({
          draw: 1, start: 0, length: 50,
          columns: ["id", "codeIdentity", "data1"].map((data) => ({ data, orderable: true })),
          order: [], search: { value: nama, regex: false },
          assignmentExtraParam: { surveyPeriodId: PERIODE, assignmentErrorStatusType: -1, assignmentStatusAlias: null },
        }));
        if (jenisSementara(r.status)) { await tidur(jedaRateLimit(ke, r.retryAfter)); continue; }
        if (r.status === 401) throw new Berhenti("SESI_DITOLAK", "datatable HTTP 401 — login ulang fasih-sm");
        for (const it of (JSON.parse(r.teks).searchData || [])) {
          if (it && it.id) info[String(it.id).toLowerCase()] = { mode: modeDari(it), galat: angkaDari(it, /^sum_?error$/i),
            bersih: angkaDari(it, /^sum_?clean$/i) };
        }
        break;
      }
    } catch (e) {
      if (e instanceof Berhenti) throw e;
      log(`⚠️ tabel Data utk '${nama}' tidak terbaca: ${e.message}`);
      info = {};
    }
    cacheDaftar.set(nama, info);
    return info;
  }

  /** Baca detail semua dokumen grup & putuskan. -> [{...dok, detail, keputusan, alasan}] */
  async function periksaGrup(g, opsi) {
    const dok = [];
    for (const d of g.d) {
      cekHenti();
      const det = await bacaDetail(d.id);
      dok.push({ id: d.id, a: d.a || "", c: !!d.c, l: !!d.l, x: !!d.x, ada: det.ada, alias: det.alias, nama: det.nama,
        kode: det.kode, mode: det.mode, galat: det.galat, bersih: det.bersih, pesan: det.pesan, detail: det });
    }
    const ada = dok.filter((x) => x.ada);
    if (ada.length >= 2 && ada.some((x) => (opsi.hanyaPapi && !x.mode) || x.galat == null || x.bersih == null)) {
      const info = await infoDaftar(ada[0].nama);
      for (const x of ada) {
        const i = info[x.id.toLowerCase()] || {};
        if (!x.mode && i.mode) x.mode = i.mode;
        if (x.galat == null && i.galat != null) x.galat = i.galat;
        if (x.bersih == null && i.bersih != null) x.bersih = i.bersih;
      }
    }
    const kep = putuskanGrup(dok, opsi);
    return dok.map((d, i) => ({ ...d, keputusan: kep[i].keputusan, alasan: kep[i].alasan }));
  }

  function barisRingkas(g, d) {
    return { baris: g.b, nama: (g.n || "").slice(0, 40), id: d.id.slice(0, 8), status: d.alias || "-", mode: d.mode || "-",
      galat: d.galat == null ? "?" : d.galat,
      keputusan: d.keputusan, alasan: d.alasan.slice(0, 70) };
  }

  const sudahDihapus = (id) => /DIHAPUS.*TERVERIFIKASI/.test((hasil()[id] || {}).status || "");

  async function cek(opsi = {}) {
    return jalankan({ ...opsi, mode: "cek" });
  }

  async function jalankan(opsi = {}) {
    if (berjalan) return log("⚠️ masih berjalan — tunggu, atau hapusGanda.berhenti()");
    opsi = { hanyaPapi: true, ...opsi };
    const mode = opsi.mode || "cek";
    const mulai = Math.max(0, (opsi.mulai || 1) - 1);
    const batasGrup = opsi.grup || Infinity;
    const limit = opsi.limit == null ? Infinity : opsi.limit;
    berjalan = true;
    hentikan = false;
    const ringkas = [];
    const hitung = {};
    let dihapus = 0, gagalBeruntun = 0;
    try {
      pastikanHalaman();
      let tpl = null;
      if (mode === "hapus") {
        tpl = pola();
        if (!tpl || !tpl.terbukti) throw new Berhenti("POLA_BELUM_ADA", "belum ada pola hapus yang terbukti — jalankan hapusGanda.rekam() dulu");
        const adaBukti = Object.values(hasil()).some((h) => h.status === "DIHAPUS_TERVERIFIKASI");
        if (!limitDiizinkan(limit, adaBukti)) {
          throw new Berhenti("LIMIT_PERTAMA", "penghapusan skrip pertama wajib {mode:'hapus', limit: 1} — periksa hasilnya dulu");
        }
      }
      const grup = TARGET.slice(mulai, mulai + batasGrup);
      log(`${mode === "hapus" ? "🗑️ HAPUS" : "🔎 CEK (read-only)"}: ${grup.length} grup mulai grup ${mulai + 1}`
        + (opsi.hanyaPapi ? ", hanya dokumen PAPI" : ", SEMUA mode")
        + (mode === "hapus" ? `, limit ${limit}` : ""));
      for (const [k, g] of grup.entries()) {
        cekHenti();
        if (dihapus >= limit) break;
        const sisa = g.d.filter((d) => !sudahDihapus(d.id));
        if (sisa.length < 2) continue;          // grup ini sudah beres
        const dok = await periksaGrup({ ...g, d: sisa }, opsi);
        for (const d of dok) {
          hitung[d.keputusan] = (hitung[d.keputusan] || 0) + 1;
          ringkas.push({ grup: mulai + k + 1, ...barisRingkas(g, d) });
          keputusanTerakhir = keputusanTerakhir.filter((x) => x.id !== d.id)
            .concat([{ g: g.g, b: g.b, n: g.n, id: d.id, keputusan: d.keputusan, alasan: d.alasan, alias: d.alias, nama: d.nama }]);
          if (mode === "cek") catat(d.id, { status: `CEK_${d.keputusan}`, grup: g.g, baris: g.b, nama: g.n, alias: d.alias, pesan: d.alasan });
        }
        if (mode !== "hapus") continue;
        const simpan = dok.find((d) => d.keputusan === "PERTAHANKAN");
        for (const d of dok.filter((x) => x.keputusan === "HAPUS")) {
          cekHenti();
          if (dihapus >= limit) break;
          const st = await hapusSatu(tpl, g, d, simpan, opsi);
          if (st === "DIHAPUS_TERVERIFIKASI") { dihapus++; gagalBeruntun = 0; }
          else if (st === "GAGAL_HAPUS" || st === "SERVER_SIBUK") {
            if (++gagalBeruntun >= (opsi.maksGagalBeruntun || 3)) throw new Berhenti("GAGAL_BERUNTUN", `${gagalBeruntun} penghapusan gagal beruntun`);
          }
          await tidur(acak(1500, 3000));
        }
      }
      log(`✅ selesai. Keputusan: ${JSON.stringify(hitung)}` + (mode === "hapus" ? ` | dihapus & terverifikasi: ${dihapus}` : ""));
    } catch (e) {
      if (e instanceof Berhenti) log(`⛔ BERHENTI ${e.kode}: ${e.message}`);
      else log("⛔ galat tak terduga", e);
    } finally {
      berjalan = false;
      if (ringkas.length) console.table(ringkas.slice(0, 300));
      if (mode === "cek") saranRekam();
    }
    return hitung;
  }

  async function hapusSatu(tpl, g, d, simpan, opsi) {
    // Baca ulang tepat sebelum menghapus: keputusan harus TETAP sama.
    const ulang = await periksaGrup({ ...g, d: g.d.filter((x) => !sudahDihapus(x.id)) }, opsi);   // opsi.hanyaPapi ikut
    const kini = ulang.find((x) => x.id === d.id);
    const simpanKini = ulang.find((x) => x.keputusan === "PERTAHANKAN");
    if (!kini || kini.keputusan !== "HAPUS" || !simpanKini || simpanKini.id !== simpan.id) {
      log(`⚠️ baris ${g.b} ${d.id.slice(0, 8)}: keputusan berubah saat dibaca ulang — DILEWATI`);
      catat(d.id, { status: "KEPUTUSAN_BERUBAH", grup: g.g, baris: g.b, nama: g.n, alias: kini ? kini.alias : "", pesan: kini ? kini.alasan : "" });
      return "KEPUTUSAN_BERUBAH";
    }
    const req = isiTemplate(tpl, d.id);
    const r = await minta(req.method, req.url, req.body, req.contentType);
    if (r.status === 401 || r.status === 403) throw new Berhenti("SESI_DITOLAK", `hapus HTTP ${r.status}: ${r.teks.slice(0, 150)}`);
    if (jenisSementara(r.status)) {
      // Request tulis TIDAK dikirim ulang buta: tunggu, lalu lihat apakah ternyata terhapus.
      log(`⏳ hapus ${d.id.slice(0, 8)} HTTP ${r.status || "gagal jaringan"} — tunggu 20 dtk lalu cek detail`);
      await tidur(20000);
    } else if (r.status < 200 || r.status >= 300) {
      catat(d.id, { status: "GAGAL_HAPUS", grup: g.g, baris: g.b, nama: g.n, alias: kini.alias, pesan: `HTTP ${r.status} ${r.teks.slice(0, 150)}` });
      log(`❌ baris ${g.b} ${d.id.slice(0, 8)}: HTTP ${r.status} ${r.teks.slice(0, 150)}`);
      return "GAGAL_HAPUS";
    }
    let sesudah = null;
    for (let ke = 0; ke < 3; ke++) {
      await tidur(2000);
      sesudah = await bacaDetail(d.id);
      if (cocokTerhapus(tpl.sidik, sesudah)) break;
    }
    const pembanding = await bacaDetail(simpan.id);
    if (!pembanding.ada) throw new Berhenti("PEMBANDING_HILANG", `dokumen yang dipertahankan ${simpan.id} ikut tidak terbaca — sesi/akses bermasalah?`);
    if (cocokTerhapus(tpl.sidik, sesudah)) {
      catat(d.id, { status: "DIHAPUS_TERVERIFIKASI", grup: g.g, baris: g.b, nama: g.n, alias: kini.alias,
        dipertahankan: simpanKini.id, alias_dipertahankan: simpanKini.alias, akun_dipertahankan: simpanKini.a,
        subsls_dipertahankan: simpanKini.kode, pesan: `HTTP ${r.status}` });
      log(`🗑️ baris ${g.b} ${d.id.slice(0, 8)} (${kini.alias}) dihapus & terverifikasi — dipertahankan ${simpan.id.slice(0, 8)} (${simpanKini.alias})`);
      return "DIHAPUS_TERVERIFIKASI";
    }
    if (jenisSementara(r.status)) {
      catat(d.id, { status: "SERVER_SIBUK", grup: g.g, baris: g.b, nama: g.n, alias: kini.alias, pesan: `HTTP ${r.status}, detail masih ada` });
      return "SERVER_SIBUK";
    }
    catat(d.id, { status: "DIHAPUS_BELUM_TERVERIFIKASI", grup: g.g, baris: g.b, nama: g.n, alias: kini.alias,
      pesan: `HTTP ${r.status}, detail sesudah: ${JSON.stringify(sesudah && { ada: sesudah.ada, alias: sesudah.alias, pesan: sesudah.pesan })}` });
    throw new Berhenti("DIHAPUS_BELUM_TERVERIFIKASI", `baris ${g.b} ${d.id}: server menjawab HTTP ${r.status} tapi detail tidak cocok dgn tanda terhapus`);
  }

  /** Kandidat utk rekam: grup dgn TEPAT satu HAPUS & statusnya beda dgn yang dipertahankan
   *  (bisa dibedakan dari kolom Status di tabel Data). */
  function kandidatRekam() {
    const perGrup = {};
    for (const x of keputusanTerakhir) (perGrup[x.g] = perGrup[x.g] || []).push(x);
    const out = [];
    for (const isi of Object.values(perGrup)) {
      const h = isi.filter((x) => x.keputusan === "HAPUS");
      const s = isi.find((x) => x.keputusan === "PERTAHANKAN");
      if (h.length === 1 && s && isi.length === 2 && peringkatStatus(h[0].alias) !== peringkatStatus(s.alias)) out.push({ hapus: h[0], simpan: s });
    }
    return out;
  }

  function saranRekam() {
    if (pola() && pola().terbukti) return;
    const k = kandidatRekam();
    if (!k.length) return;
    log(`Contoh utk hapusGanda.rekam() — cari NAMA ini di kotak Cari tabel Data, hapus baris yang STATUS-nya ${k[0].hapus.alias}:`);
    console.table(k.slice(0, 5).map((x) => ({ baris: x.hapus.b, cari: x.hapus.nama, hapus_status: x.hapus.alias,
      hapus_id: x.hapus.id.slice(0, 8), pertahankan_status: x.simpan.alias })));
  }

  // --- rekam: penyadap fetch & XHR -------------------------------------------------------
  function lepasPenyadap() {
    if (!penyadap) return;
    window.fetch = penyadap.fetchLama;
    XMLHttpRequest.prototype.open = penyadap.openLama;
    XMLHttpRequest.prototype.send = penyadap.sendLama;
    penyadap = null;
    log("penyadap dilepas");
  }

  function ambilHeader(h, nama) {
    if (!h) return "";
    if (typeof h.get === "function") return h.get(nama) || "";
    if (Array.isArray(h)) { const x = h.find(([k]) => String(k).toLowerCase() === nama.toLowerCase()); return x ? x[1] : ""; }
    const k = Object.keys(h).find((x) => x.toLowerCase() === nama.toLowerCase());
    return k ? h[k] : "";
  }

  /** Argumen fetch(input, init) -> {method, url, body (string|null), contentType}. */
  async function uraiRequest(input, init) {
    const req = typeof Request !== "undefined" && input instanceof Request ? input : null;
    const method = String((init && init.method) || (req && req.method) || "GET").toUpperCase();
    const url = req ? req.url : String(input);
    let body = init && init.body != null ? init.body : null;
    if (body == null && req && method !== "GET") body = await req.clone().text();
    const contentType = ambilHeader(init && init.headers, "Content-Type") || ambilHeader(req && req.headers, "Content-Type");
    return { method, url, body: typeof body === "string" ? body : null, contentType };
  }

  async function rekam(opsi = {}) {
    if (berjalan) return log("⚠️ masih berjalan — tunggu, atau hapusGanda.berhenti()");
    try {
      pastikanHalaman();
    } catch (e) {
      return log(`⛔ ${e.message}`);
    }
    if (!keputusanTerakhir.length) {
      log(`belum ada hasil cek di tab ini — cek ${opsi.grup || 20} grup pertama dulu...`);
      await jalankan({ ...opsi, mode: "cek", grup: opsi.grup || 20 });
    }
    const boleh = new Set(keputusanTerakhir.filter((x) => x.keputusan === "HAPUS").map((x) => x.id.toLowerCase()));
    const jaga = new Set(TARGET.flatMap((g) => g.d.map((d) => d.id.toLowerCase())).filter((id) => !boleh.has(id)));
    if (!boleh.size) return log("⛔ tidak ada dokumen ber-keputusan HAPUS di hasil cek — tidak ada yang bisa direkam");
    lepasPenyadap();
    const fetchLama = window.fetch, openLama = XMLHttpRequest.prototype.open, sendLama = XMLHttpRequest.prototype.send;
    penyadap = { fetchLama, openLama, sendLama };

    const periksa = (method, url, body) => {
      if (String(method || "GET").toUpperCase() === "GET") return { aksi: "LEWAT" };
      const teks = `${url}\n${typeof body === "string" ? body : ""}`;
      const dijaga = idDalam(teks, jaga);
      if (dijaga.length) return { aksi: "BLOKIR", id: dijaga[0] };
      const cocok = idDalam(teks, boleh);
      return cocok.length === 1 ? { aksi: "REKAM", id: cocok[0] } : { aksi: "LEWAT" };
    };
    const blokir = (id) => {
      const x = keputusanTerakhir.find((k) => k.id.toLowerCase() === id.toLowerCase());
      log(`🛑 DIBLOKIR: request ubah memuat dokumen ${id} (${x ? `${x.keputusan}: ${x.alasan}` : "tidak diputuskan HAPUS"}). Tidak dikirim.`);
    };
    const kepDari = (id) => keputusanTerakhir.find((k) => k.id.toLowerCase() === String(id).toLowerCase());
    const setelah = async (req, id, sebelum, httpStatus) => {
      if (httpStatus < 200 || httpStatus >= 300) return log(`⚠️ request hapus ${id} dijawab HTTP ${httpStatus} — pola tidak disimpan`);
      let sesudah = null, sidik = null;
      for (let ke = 0; ke < 4 && !sidik; ke++) {
        await sleep(2000);
        sesudah = await bacaDetail(id);
        sidik = sidikTerhapus(sebelum, sesudah);
      }
      const x = kepDari(id) || {};
      const simpan = keputusanTerakhir.find((k) => k.g === x.g && k.keputusan === "PERTAHANKAN");
      const pembanding = simpan ? await bacaDetail(simpan.id) : null;
      let tpl;
      try {
        tpl = templateDari(req, id, [...jaga]);
      } catch (e) {
        return log(`⛔ request tertangkap tapi tidak bisa dijadikan pola: ${e.message}`, req);
      }
      if (!sidik || !pembanding || !pembanding.ada) {
        tulisLS(KUNCI_POLA, { ...tpl, terbukti: false, sidik: null, waktu: new Date().toISOString() });
        log("⚠️ Request hapus terekam, tapi penghapusannya BELUM terbukti dari detail. Pola TIDAK dipakai. "
          + "Salin keluaran berikut ke Claude:", { req: tpl, sebelum: sebelum && sebelum.data, sesudah, pembanding: pembanding && pembanding.ada });
        return;
      }
      tulisLS(KUNCI_POLA, { ...tpl, terbukti: true, sidik, id_contoh: id, waktu: new Date().toISOString() });
      const dS = (TARGET.find((t) => t.g === x.g) || { d: [] }).d.find((t) => t.id === simpan.id) || {};
      catat(id, { status: "DIHAPUS_MANUAL_TERVERIFIKASI", grup: x.g, baris: x.b, nama: x.n, alias: sebelum.alias,
        dipertahankan: simpan.id, alias_dipertahankan: pembanding.alias, akun_dipertahankan: dS.a || "",
        subsls_dipertahankan: pembanding.kode, pesan: `rekam: ${tpl.method} ${tpl.url}` });
      log(`✅ Pola hapus terekam & terbukti (${tpl.method} ${tpl.url}, tanda terhapus: ${JSON.stringify(sidik)}).`
        + " Lanjut: hapusGanda.jalankan({mode: 'hapus', limit: 1})");
      lepasPenyadap();
    };
    const bacaAman = async (id) => {
      try { return await bacaDetail(id); } catch (e) { log(`⚠️ detail ${id} sebelum hapus tidak terbaca: ${e.message}`); return null; }
    };

    window.fetch = async function (input, init) {
      let info = null, p = { aksi: "LEWAT" };
      try {
        info = await uraiRequest(input, init);
        p = periksa(info.method, info.url, info.body);
      } catch (e) {
        log("⚠️ penyadap tidak bisa membaca request ini (diteruskan apa adanya)", e);
      }
      if (p.aksi === "BLOKIR") {
        blokir(p.id);
        throw new TypeError("diblokir hapusGanda: dokumen ini tidak boleh dihapus");
      }
      if (p.aksi !== "REKAM") return fetchLama.apply(this, arguments);
      const sebelum = await bacaAman(p.id);
      const res = await fetchLama.apply(this, arguments);      // dikirim TEPAT sekali
      setelah(info, p.id, sebelum, res.status).catch((e) => log("⚠️ pemeriksaan sesudah hapus galat", e));
      return res;
    };
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__hapusGanda = { method, url: String(url) };
      return openLama.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function (body) {
      const info = this.__hapusGanda;
      const p = info ? periksa(info.method, info.url, body) : { aksi: "LEWAT" };
      if (p.aksi === "BLOKIR") {
        blokir(p.id);
        throw new Error("diblokir hapusGanda: dokumen ini tidak boleh dihapus");
      }
      if (p.aksi !== "REKAM") return sendLama.apply(this, arguments);
      const xhr = this;
      xhr.addEventListener("loadend", () => setelah({ method: info.method, url: info.url,
        body: typeof body === "string" ? body : null, contentType: "application/json" }, p.id, xhr.__sebelum, xhr.status)
        .catch((e) => log("⚠️ pemeriksaan sesudah hapus galat", e)));
      bacaAman(p.id).then((d) => { xhr.__sebelum = d; }).finally(() => sendLama.call(xhr, body));
      return undefined;
    };
    log(`🎙️ MEREKAM. Hapus SATU dokumen ber-keputusan HAPUS lewat menu ⋮ -> "Hapus Assignment" (${boleh.size} dokumen boleh; `
      + `${jaga.size} dokumen lain di TARGET DIBLOKIR). Batal: hapusGanda.lepasPenyadap()`);
    saranRekam();
  }

  /** Cadangan kalau penyadap tidak menangkap apa pun: sesudah menghapus manual, DevTools > Network >
   *  klik kanan request hapus > Copy > Copy as fetch, lalu hapusGanda.pakaiContoh(`<tempel>`). */
  async function pakaiContoh(teks) {
    try {
      pastikanHalaman();
      const req = uraiCopyAsFetch(teks);
      const semua = TARGET.flatMap((g) => g.d.map((d) => d.id));
      const ids = idDalam(`${req.url}\n${req.body || ""}`, semua);
      if (ids.length !== 1) throw new Berhenti("POLA_DITOLAK", `request harus memuat tepat 1 id dari TARGET (terbaca ${ids.length})`);
      const id = ids[0];
      const g = TARGET.find((x) => x.d.some((d) => d.id.toLowerCase() === id.toLowerCase()));
      const tpl = templateDari(req, id, semua);
      const sesudah = await bacaDetail(id);
      const lain = g.d.filter((d) => d.id.toLowerCase() !== id.toLowerCase());
      const pembanding = [];
      for (const d of lain) pembanding.push(await bacaDetail(d.id));
      if (sesudah.ada || !pembanding.some((p) => p.ada)) {
        throw new Berhenti("POLA_BELUM_TERBUKTI", sesudah.ada
          ? `dokumen ${id} masih terbaca di detail — belum terhapus / penghapusannya tidak kelihatan dari detail`
          : "tidak ada dokumen lain di grupnya yang masih terbaca — sesi bermasalah?");
      }
      tulisLS(KUNCI_POLA, { ...tpl, terbukti: true, sidik: { cara: "HILANG", http: sesudah.http }, id_contoh: id,
        waktu: new Date().toISOString() });
      catat(id, { status: "DIHAPUS_MANUAL_TERVERIFIKASI", grup: g.g, baris: g.b, nama: g.n, alias: "", pesan: "pakaiContoh" });
      log(`✅ Pola dari 'Copy as fetch' disimpan (${tpl.method} ${tpl.url}). Lanjut: hapusGanda.jalankan({mode: 'hapus', limit: 1})`);
    } catch (e) {
      log(`⛔ ${e.kode || ""} ${e.message}`);
    }
  }

  function unduh() {
    const h = hasil();
    const kolom = ["id", "status", "grup", "baris", "nama", "alias", "dipertahankan", "alias_dipertahankan",
      "akun_dipertahankan", "subsls_dipertahankan", "pesan", "waktu"];
    const sel = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const csv = [kolom.join(",")].concat(Object.entries(h).map(([id, x]) => kolom.map((k) => sel(k === "id" ? id : x[k])).join(","))).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
    a.download = `ganda_dihapus_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "")}.csv`;
    a.click();
    log(`${Object.keys(h).length} baris diunduh -> ${a.download} (taruh di folder proyek sebelum gabung_audit.py)`);
  }

  window.hapusGanda = {
    cek, rekam, pakaiContoh, jalankan, unduh, lepasPenyadap,
    berhenti() { hentikan = true; log("akan berhenti setelah langkah ini"); },
    ringkasan() { console.table(keputusanTerakhir.map((x) => ({ baris: x.b, nama: (x.n || "").slice(0, 40), id: x.id.slice(0, 8), status: x.alias, keputusan: x.keputusan, alasan: x.alasan.slice(0, 70) }))); },
    hasil, pola,
    lupakanPola() { if (confirm("Hapus pola hapus yang tersimpan?")) localStorage.removeItem(KUNCI_POLA); },
    target: TARGET,
  };
  log(`siap: ${TARGET.length} grup ganda. Mulai: hapusGanda.cek() (read-only). Panduan: docs/PANDUAN_HAPUS_GANDA.md`);
})();
