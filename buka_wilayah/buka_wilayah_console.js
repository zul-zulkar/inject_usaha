/**
 * buka_wilayah_console.js — "Buka Wilayah" (batal tandai Selesai Listing) massal
 * di fasih-sm dari DevTools Console Chrome BIASA (fasih-sm mendeteksi Playwright).
 *
 * FILE INI TEMPLATE. Jangan ditempel langsung — buat versi berisi target:
 *     python buka_wilayah/buka_wilayah.py --daftar daftar_buka_wilayah.txt --console
 * -> buka_wilayah_console.siap.js
 *
 * CARA PAKAI
 * ----------
 * 1. Chrome biasa, VPN aktif, login fasih-sm dgn akun yang bisa melihat tombol
 *    "Progress Penyelesaian Wilayah" (pojok kanan atas halaman Data), buka:
 *    https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10
 * 2. F12 -> Console -> tempel SELURUH isi buka_wilayah_console.siap.js -> Enter.
 * 3. Jalankan BERTAHAP:
 *      await bukaWilayah.jalankan({mode: "cek"})                // READ-ONLY: status semua target
 *      await bukaWilayah.jalankan({mode: "eksekusi", limit: 1}) // buka 1 wilayah, cek hasilnya di layar
 *      await bukaWilayah.jalankan({mode: "eksekusi"})           // sisanya
 *    Opsi: limit (jumlah subsls yang DIPROSES, setelah yang sudah terbuka dilewati),
 *          idsubsls: [...], izinkanTarikSampel, pindaiDulu (default true), jedaMin/jedaMaks (ms)
 *    bukaWilayah.berhenti()   hentikan di langkah berikutnya
 *    bukaWilayah.ringkasan()  hitungan status
 *    bukaWilayah.unduh()      unduh hasil CSV
 *
 * CARA KERJA (dipetakan dari halaman asli 2026-09-15)
 * ----------------------------------------------------
 * Dialog "Daftar Wilayah / Progress penyelesaian wilayah" memuat daftarnya dari
 *   POST /app/api/assignment-general/api/assignment-region/datatable?periodeId=<periode>
 *   body {start, length, search: {value, regex: true}, order: [{column: 0, dir: "asc"}]}
 *   -> {recordsTotal, data: [{id, surveyPeriodId, smallestRegionFullCode, region,
 *       regionId, regionGroupId, doneListing, doneTarikSample}]}
 * Kartu menampilkan "Listing Selesai" + tombol "Buka Wilayah" kalau doneListing
 * = true, atau "Proses Listing" + "Tandai Selesai Listing" kalau false. Tombol
 * "Buka Wilayah" -> popover "Ya, Buka Wilayah" -> kode halaman mengirim
 *   POST /app/api/assignment-general/api/assignment-region/undone
 *   body = ITEM WILAYAH APA ADANYA dari datatable -> {success, message}
 * Skrip ini mengirim permintaan yang PERSIS sama (lewat fetch halaman, cookie
 * sesi + header X-XSRF-TOKEN dari cookie XSRF-TOKEN — tanpa header itu 403
 * "Invalid CSRF Token"), bukan mengklik popover dgn event sintetis.
 * ⚠️ `start` di datatable = OFFSET baris; halaman web mengirim nomor halaman
 * sbg start (bug paginasi dialog) — jangan ditiru.
 *
 * KESELAMATAN
 * -----------
 * - Endpoint "done" (Tandai Selesai Listing) TIDAK PERNAH dipanggil.
 * - Sebelum membuka: pencarian harus menghasilkan TEPAT SATU wilayah dgn kode
 *   16 digit persis sama, dan doneListing === true. Sudah terbuka -> dilewati.
 * - Setelah membuka: dicari ulang; doneListing harus false (DIBUKA_TERVERIFIKASI).
 * - Wilayah yang sudah Tarik Sampel dilewati (SUDAH_TARIK_SAMPEL) kecuali opsi
 *   izinkanTarikSampel: true — halaman web sendiri tidak melarang, tapi dampaknya
 *   belum diketahui.
 * - Batch BERHENTI SEKETIKA kalau: sesi/CSRF ditolak, respons tidak dikenal,
 *   atau hasil tidak terverifikasi. Kegagalan lain 3x beruntun juga menghentikan.
 * - PINDAI MASSAL (default): status seluruh wilayah dibaca dulu (request 500 baris,
 *   offset). Target yang terbaca doneListing === false langsung SUDAH_TERBUKA tanpa
 *   request per subsls. Hanya bukti positif itu yang dilewati — sisanya tetap dicari
 *   ulang satu per satu TEPAT sebelum dibuka. Jeda panjang hanya setelah menulis.
 * - Eksekusi tanpa `limit` butuh minimal 1 DIBUKA_TERVERIFIKASI di browser ini.
 * - Hasil disimpan di localStorage (tahan reload); target tuntas dilewati saat
 *   dijalankan ulang.
 */
(function (global) {
  "use strict";

  const TARGET = /*__TARGET__*/[];

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_buka_wilayah_console.js
  // -------------------------------------------------------------------------
  const STATUS_TUNTAS = new Set(["DIBUKA_TERVERIFIKASI", "SUDAH_TERBUKA"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL", "DIBUKA_BELUM_TERVERIFIKASI", "HALAMAN_SALAH", "DIHENTIKAN_PENGGUNA",
  ]);

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  const KODE_VALID = /^5108\d{12}$/;

  /** "/app/surveys/<survei>/<periode>/data" -> periode (null kalau bukan halaman itu). */
  function periodeDariPath(path) {
    const m = /^\/app\/surveys\/[0-9a-f-]{36}\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? m[1] : null;
  }

  /** Hasil pencarian datatable (data[]) utk satu kode -> {status, item, pesan}. */
  function rencanakan(kode, data, opsi = {}) {
    if (!KODE_VALID.test(kode || "")) return { status: "KODE_TIDAK_VALID", item: null, pesan: `'${kode}' bukan idsubsls 16 digit` };
    if (!Array.isArray(data)) return { status: "RESPONS_TIDAK_DIKENAL", item: null, pesan: "data pencarian bukan array" };
    const cocok = data.filter((d) => d && d.smallestRegionFullCode === kode);
    if (!cocok.length) {
      return { status: "WILAYAH_TIDAK_ADA", item: null,
        pesan: `tidak ada wilayah ${kode} di daftar Progress Penyelesaian Wilayah (${data.length} hasil pencarian lain)` };
    }
    if (cocok.length > 1) return { status: "WILAYAH_GANDA", item: null, pesan: `${cocok.length} wilayah berkode ${kode}` };
    const item = cocok[0];
    if (typeof item.doneListing !== "boolean" || !item.id) {
      return { status: "RESPONS_TIDAK_DIKENAL", item: null,
        pesan: `doneListing=${JSON.stringify(item.doneListing)}, id=${JSON.stringify(item.id)}` };
    }
    if (!item.doneListing) return { status: "SUDAH_TERBUKA", item, pesan: "status Proses Listing" };
    if (item.doneTarikSample === true && !opsi.izinkanTarikSampel) {
      return { status: "SUDAH_TARIK_SAMPEL", item,
        pesan: "Listing Selesai & sudah Tarik Sampel — dilewati (opsi izinkanTarikSampel: true utk tetap membuka)" };
    }
    return { status: "PERLU_DIBUKA", item, pesan: "status Listing Selesai" };
  }

  /** Respons endpoint undone -> {ok, status, pesan}. Halaman web menganggap gagal kalau !success. */
  function nilaiRespons(httpStatus, teks) {
    if (httpStatus === 401 || httpStatus === 403) {
      return { ok: false, status: "SESI_DITOLAK", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
    }
    let j = null;
    try {
      j = JSON.parse(teks);
    } catch (e) {
      return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}, bukan JSON: ${String(teks || "").slice(0, 150)}` };
    }
    if (httpStatus >= 200 && httpStatus < 300 && j && j.success === true) return { ok: true, status: "OK", pesan: j.message || "" };
    if (j && j.success === false) return { ok: false, status: "GAGAL_BUKA", pesan: `HTTP ${httpStatus}: ${j.message || "(tanpa pesan)"}` };
    return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
  }

  /** Daftar target yang diproses, sesuai mode & hasil sebelumnya. */
  function saringTarget(target, sebelumnya, o) {
    let daftar = target.filter((t) => !o.idsubsls || o.idsubsls.includes(t.idsubsls));
    if (o.lewatiSelesai && o.mode === "eksekusi") {
      daftar = daftar.filter((t) => {
        const h = sebelumnya[t.idsubsls];
        return !(h && h.jalan === "eksekusi" && STATUS_TUNTAS.has(h.status));
      });
    }
    return o.limit ? daftar.slice(0, o.limit) : daftar;
  }

  /** Pisahkan target memakai hasil pindai massal (peta kode -> {doneListing, ...}).
   *  Yang dilewati HANYA kode yang terbaca doneListing === false (bukti positif sudah
   *  terbuka). Tidak terbaca / Listing Selesai / nilai aneh -> tetap diproses satu per
   *  satu, jadi keputusan membuka selalu dari pencarian segar. */
  function bagiDariPindai(daftar, peta) {
    const lewati = [];
    const proses = [];
    for (const t of daftar) {
      const r = peta && peta[t.idsubsls];
      (r && r.doneListing === false ? lewati : proses).push(t);
    }
    return { lewati, proses };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, STATUS_BERHENTI_SEGERA, periodeDariPath, rencanakan, nilaiRespons, saringTarget, bagiDariPindai,
    };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "bukaWilayah.hasil.v1";
  const API = "/app/api/assignment-general/api/assignment-region";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const log = (...a) => console.log("%c[bukaWilayah]", "color:#b8860b;font-weight:bold", ...a);

  let hentikan = false;
  let berjalan = false;

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "bukaWilayah.berhenti() dipanggil");
  }

  function xsrf() {
    const c = document.cookie.split("; ").find((x) => x.startsWith("XSRF-TOKEN="));
    return c ? decodeURIComponent(c.slice("XSRF-TOKEN=".length)) : "";
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-XSRF-TOKEN": xsrf() },
      body: JSON.stringify(body),
    });
    return { status: res.status, teks: await res.text() };
  }

  /** `start` = OFFSET baris (dialog web keliru mengirim nomor halaman). */
  async function datatable(periode, start, length, cari) {
    const { status, teks } = await post(`${API}/datatable?periodeId=${encodeURIComponent(periode)}`,
      { start, length, search: { value: cari, regex: true }, order: [{ column: 0, dir: "asc" }] });
    if (status === 401 || status === 403) throw new Berhenti("SESI_DITOLAK", `datatable HTTP ${status}: ${teks.slice(0, 150)}`);
    let j;
    try {
      j = JSON.parse(teks);
    } catch (e) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${status}, bukan JSON: ${teks.slice(0, 150)}`);
    }
    if (status !== 200 || !j || !Array.isArray(j.data)) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${status}: ${teks.slice(0, 150)}`);
    }
    return j;
  }

  async function cariWilayah(periode, kode) {
    return (await datatable(periode, 0, 10, kode)).data;
  }

  /** Status SELURUH wilayah periode (±6 request 500 baris) -> peta kode -> {doneListing, doneTarikSample}.
   *  `recordsFiltered` = panjang halaman (bukan jumlah hasil) -> batas pakai recordsTotal. */
  async function pindaiSemua(periode) {
    const peta = {};
    let total = null;
    for (let start = 0; total === null || start < total; start += 500) {
      cekHenti();
      const j = await datatable(periode, start, 500, "");
      if (typeof j.recordsTotal !== "number") throw new Berhenti("RESPONS_TIDAK_DIKENAL", "recordsTotal tidak ada");
      total = j.recordsTotal;
      for (const d of j.data) {
        if (d && d.smallestRegionFullCode) peta[d.smallestRegionFullCode] = { doneListing: d.doneListing, doneTarikSample: d.doneTarikSample };
      }
      log(`Pindai massal: ${Object.keys(peta).length}/${total} wilayah terbaca`);
      if (!j.data.length) break;
    }
    return peta;
  }

  function muatHasil() {
    try {
      return JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}");
    } catch (e) {
      return {};
    }
  }
  function simpanHasil(entri) {
    const semua = muatHasil();
    semua[entri.idsubsls] = entri;
    try {
      localStorage.setItem(KUNCI_HASIL, JSON.stringify(semua));
    } catch (e) {
      log("⚠️ localStorage penuh/terkunci — segera bukaWilayah.unduh()", e);
    }
  }

  async function prosesTarget(t, periode, o) {
    const hasil = { waktu: new Date().toISOString(), jalan: o.mode, idsubsls: t.idsubsls, status: "",
      done_listing_awal: "", done_tarik_sampel: "", id_wilayah: "", pesan: "" };
    try {
      const r = rencanakan(t.idsubsls, await cariWilayah(periode, t.idsubsls), o);
      Object.assign(hasil, { status: r.status, pesan: r.pesan });
      if (r.item) {
        Object.assign(hasil, { done_listing_awal: r.item.doneListing, done_tarik_sampel: r.item.doneTarikSample, id_wilayah: r.item.id });
      }
      if (r.status !== "PERLU_DIBUKA") return hasil;
      if (o.mode === "cek") {
        hasil.status = "CEK_PERLU_DIBUKA";
        return hasil;
      }

      cekHenti();
      // IRREVERSIBLE (bisa ditandai selesai lagi, tapi bukan oleh skrip ini).
      hasil.dikirim = true;
      const kirim = await post(`${API}/undone`, r.item);
      const n = nilaiRespons(kirim.status, kirim.teks);
      if (!n.ok) {
        Object.assign(hasil, { status: n.status, pesan: n.pesan });
        return hasil;
      }
      let terbuka = false;
      for (let ke = 1; ke <= 3 && !terbuka; ke++) {
        await sleep(1500 * ke);
        const v = rencanakan(t.idsubsls, await cariWilayah(periode, t.idsubsls), { izinkanTarikSampel: true });
        terbuka = v.status === "SUDAH_TERBUKA";
      }
      hasil.status = terbuka ? "DIBUKA_TERVERIFIKASI" : "DIBUKA_BELUM_TERVERIFIKASI";
      hasil.pesan = `respons: ${n.pesan || "success"}${terbuka ? "" : " | doneListing masih true setelah 3x cek"}`;
      return hasil;
    } catch (e) {
      hasil.status = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      hasil.pesan = `${hasil.pesan ? hasil.pesan + " | " : ""}${e && e.message ? e.message : e}`;
      if (!(e instanceof Berhenti)) console.error(e);
      return hasil;
    }
  }

  async function jalankan(opsi = {}) {
    const o = { mode: "cek", limit: null, idsubsls: null, lewatiSelesai: true, izinkanTarikSampel: false,
      pindaiDulu: true, jedaMin: 1500, jedaMaks: 3500, ...opsi };
    if (!["cek", "eksekusi"].includes(o.mode)) return log(`mode '${o.mode}' tidak dikenal (cek | eksekusi)`);
    if (berjalan) return log("Masih berjalan — tunggu selesai atau bukaWilayah.berhenti().");
    if (!TARGET.length) return log("TARGET kosong — tempel buka_wilayah_console.siap.js, bukan template.");
    const periode = periodeDariPath(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !periode) {
      return log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
    }

    const sebelumnya = muatHasil();
    // Dgn pindai, limit dihitung SETELAH yang sudah terbuka dilewati (limit:1 = 1 wilayah yg benar-benar diproses).
    let daftar = saringTarget(TARGET, sebelumnya, o.pindaiDulu ? { ...o, limit: null } : o);
    if (!daftar.length) return log("Tidak ada subsls yang perlu diproses.");
    let dilewati = [];
    if (o.pindaiDulu) {
      berjalan = true;
      hentikan = false;
      try {
        const bagi = bagiDariPindai(daftar, await pindaiSemua(periode));
        dilewati = bagi.lewati;
        daftar = o.limit ? bagi.proses.slice(0, o.limit) : bagi.proses;
        log(`${dilewati.length} subsls sudah terbuka (dilewati tanpa request), ${daftar.length} diproses satu per satu.`);
      } catch (e) {
        if (e instanceof Berhenti && e.kode !== "RESPONS_TIDAK_DIKENAL") {
          log(`⛔ ${e.kode}: ${e.message}`);
          return;
        }
        log(`⚠️ Pindai massal gagal (${e && e.message ? e.message : e}) — semua target dicek satu per satu.`);
        if (o.limit) daftar = daftar.slice(0, o.limit);
      } finally {
        berjalan = false;
      }
    }
    if (o.mode === "eksekusi" && daftar.length) {
      const adaBukti = Object.values(sebelumnya).some((h) => h.status === "DIBUKA_TERVERIFIKASI");
      if (!o.limit && !adaBukti) {
        return log("Eksekusi massal butuh minimal 1 DIBUKA_TERVERIFIKASI dulu. Jalankan: "
          + 'await bukaWilayah.jalankan({mode: "eksekusi", limit: 1}) lalu cek wilayahnya di dialog Progress Penyelesaian Wilayah.');
      }
      if (prompt(`BUKA WILAYAH (batal Selesai Listing) SUNGGUHAN utk maks. ${daftar.length} subsls.\nKetik YA untuk lanjut:`) !== "YA") {
        return log("Dibatalkan.");
      }
    }

    berjalan = true;
    hentikan = false;
    const hitung = {};
    let gagalBeruntun = 0;
    try {
      const waktuPindai = new Date().toISOString();
      for (const t of dilewati) {
        simpanHasil({ waktu: waktuPindai, jalan: o.mode, idsubsls: t.idsubsls, status: "SUDAH_TERBUKA",
          done_listing_awal: false, done_tarik_sampel: "", id_wilayah: "", pesan: "status Proses Listing (pindai massal)" });
        hitung.SUDAH_TERBUKA = (hitung.SUDAH_TERBUKA || 0) + 1;
      }
      for (let i = 0; i < daftar.length; i++) {
        const t = daftar[i];
        const hasil = await prosesTarget(t, periode, o);
        simpanHasil(hasil);
        hitung[hasil.status] = (hitung[hasil.status] || 0) + 1;
        log(`[${i + 1}/${daftar.length}] ${t.idsubsls} -> ${hasil.status}`, hasil.pesan);
        if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
          log(`⛔ ${hasil.status} — batch DIHENTIKAN. Periksa sebelum menjalankan ulang.`);
          break;
        }
        const gagal = hasil.status === "GAGAL_BUKA" || hasil.status.startsWith("ERROR_");
        gagalBeruntun = gagal ? gagalBeruntun + 1 : 0;
        if (gagalBeruntun >= 3) {
          log(`⛔ 3 kegagalan berturut-turut (terakhir ${hasil.status}) — batch DIHENTIKAN.`);
          break;
        }
        // Jeda panjang hanya setelah request tulis; pencarian baca-saja cukup jeda pendek.
        if (i < daftar.length - 1) await sleep(hasil.dikirim ? acak(o.jedaMin, o.jedaMaks) : acak(300, 800));
      }
    } finally {
      berjalan = false;
      console.table(hitung);
      log("Selesai. bukaWilayah.unduh() untuk menyimpan hasil sbg CSV.");
    }
    return hitung;
  }

  function ringkasan() {
    const hitung = {};
    for (const h of Object.values(muatHasil())) hitung[`${h.jalan}:${h.status}`] = (hitung[`${h.jalan}:${h.status}`] || 0) + 1;
    console.table(hitung);
    return hitung;
  }

  function unduh() {
    const kolom = ["waktu", "jalan", "idsubsls", "status", "done_listing_awal", "done_tarik_sampel", "id_wilayah", "pesan"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = Object.values(muatHasil()).map((h) => kolom.map((k) => kutip(h[k])).join(","));
    const blob = new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit_buka_wilayah_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} subsls)`);
  }

  global.bukaWilayah = {
    jalankan, ringkasan, unduh, target: TARGET,
    berhenti() {
      hentikan = true;
      log("Akan berhenti di langkah berikutnya.");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil bukaWilayah yang tersimpan di browser ini?")) localStorage.removeItem(KUNCI_HASIL);
    },
  };
  log(`Siap: ${TARGET.length} subsls. Mulai dgn: await bukaWilayah.jalankan({mode: "cek"})`);
})(typeof window !== "undefined" ? window : globalThis);
