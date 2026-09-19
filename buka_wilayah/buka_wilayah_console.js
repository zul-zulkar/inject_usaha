/**
 * buka_wilayah_console.js — "Buka Wilayah" (batal tandai Selesai Listing) massal
 * di fasih-sm dari DevTools Console Chrome BIASA (fasih-sm mendeteksi Playwright).
 * Kebalikan tandai_selesai_console.js.
 *
 * FILE INI TEMPLATE. Jangan ditempel langsung — buat versi berisi target:
 *     python buka_wilayah/buka_wilayah.py --semua --console                           # SEMUA subsls periode
 *     python buka_wilayah/buka_wilayah.py --daftar daftar_buka_wilayah.txt --console  # daftar idsubsls
 * -> buka_wilayah_console.siap.js
 *
 * CARA PAKAI
 * ----------
 * 1. Chrome biasa, VPN aktif, login fasih-sm dgn akun yang bisa melihat tombol
 *    "Progress Penyelesaian Wilayah" (pojok kanan atas halaman Data), buka:
 *    https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10
 * 2. F12 -> Console -> tempel SELURUH isi buka_wilayah_console.siap.js -> Enter.
 * 3. Jalankan:
 *      await bukaWilayah.jalankan({mode: "cek"})                 // (opsional) READ-ONLY: status semua target
 *      await bukaWilayah.jalankan({mode: "eksekusi"})            // buka semua yang Listing Selesai
 *      await bukaWilayah.jalankan({mode: "eksekusi", limit: 50}) // atau dicicil: 50 wilayah yg BENAR-BENAR dibuka
 *    Opsi: limit (eksekusi: jumlah wilayah yang benar-benar DIBUKA — yang ternyata sudah terbuka,
 *          Tarik Sampel, ditolak, dst. tidak dihitung; cek: jumlah subsls yang diperiksa),
 *          idsubsls: [...], kecuali: [...], izinkanTarikSampel,
 *          pindaiDulu (default true; wajib utk cakupan semua),
 *          sertakanSlsNol (default false; cakupan semua melewati kode …000000),
 *          panjangPindai (default 500 baris/request; otomatis diperkecil s.d. 50 kalau server lambat),
 *          jedaMin/jedaMaks (ms), maksGagalBeruntun (default 3)
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
 * - Sebelum membuka: pencarian segar harus menghasilkan TEPAT SATU wilayah dgn kode
 *   16 digit persis sama, dan doneListing === true. Sudah terbuka -> dilewati.
 * - Setelah membuka: dicari ulang; doneListing harus false (DIBUKA_TERVERIFIKASI).
 * - Wilayah yang sudah Tarik Sampel dilewati (SUDAH_TARIK_SAMPEL) kecuali opsi
 *   izinkanTarikSampel: true — halaman web sendiri tidak melarang, tapi dampaknya
 *   belum diketahui.
 * - Cakupan SEMUA: target = seluruh wilayah hasil pindai massal periode (kode di luar
 *   pola KODE_KAB+12 digit dilaporkan, tidak diproses; SLS nol …000000 dikeluarkan kecuali
 *   sertakanSlsNol). Pindai gagal -> berhenti (tidak ada daftar cadangan). Keputusan
 *   membuka tetap dari pencarian segar per subsls.
 * - Batch BERHENTI SEKETIKA kalau: sesi/CSRF ditolak, respons tidak dikenal, hasil tidak
 *   terverifikasi, atau server sibuk terus (429/5xx) setelah ditunggu. Penolakan server
 *   (success:false) maksGagalBeruntun kali beruntun juga menghentikan.
 * - Request BACA yang kena 429/502/503/504/jaringan putus ditunggu & diulang. Request
 *   `undone` yang kena galat itu TIDAK dikirim ulang buta: status dibaca dulu; sudah
 *   terbuka -> terverifikasi, belum -> SERVER_SIBUK (dicoba lagi di run berikut).
 * - PINDAI MASSAL (default): status seluruh wilayah dibaca dulu (request 500 baris,
 *   offset). Target yang terbaca doneListing === false langsung SUDAH_TERBUKA tanpa
 *   request per subsls. Hanya bukti positif itu yang dilewati. Kalau pindai berhasil,
 *   hasil lama di localStorage DIABAIKAN (status server segar yang menentukan), jadi
 *   wilayah yang ditandai selesai lagi setelah dibuka tetap terproses. Jeda panjang
 *   hanya setelah menulis.
 * - Tidak ada lagi tahap wajib `limit: 1` (dihapus atas permintaan user 2026-09-19: kalau target
 *   pertama ternyata sudah terbuka, run limit:1 tidak menghasilkan bukti & user harus mencari kode
 *   manual). Wilayah pertama yang dibuka di run mana pun menjadi percobaannya: tiap buka
 *   diverifikasi, dan DIBUKA_BELUM_TERVERIFIKASI langsung menghentikan batch.
 * - Hasil disimpan di localStorage (tahan reload).
 */
(function (global) {
  "use strict";

  const TARGET = /*__TARGET__*/[];
  const CAKUPAN = /*__CAKUPAN__*/"daftar";
  // Kode kabupaten 4 digit (awalan idsubsls) — disuntik dari inti/config.py (KODE_KAB).
  const KODE_KAB = /*__KODE_KAB__*/"5108";

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_buka_wilayah_console.js
  // -------------------------------------------------------------------------
  const STATUS_TUNTAS = new Set(["DIBUKA_TERVERIFIKASI", "SUDAH_TERBUKA"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL", "DIBUKA_BELUM_TERVERIFIKASI", "SERVER_SIBUK_TERUS", "HALAMAN_SALAH",
    "DIHENTIKAN_PENGGUNA",
  ]);

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  const KODE_VALID = new RegExp(`^${KODE_KAB}\\d{12}$`);
  // Teks asli penolakan server (endpoint done, run user 2026-09-15): "Anda tidak memiliki akses ke dalam survey".
  const POLA_TANPA_AKSES = /tidak memiliki akses/i;

  /** Apakah hasil satu wilayah dihitung sbg kegagalan beruntun. TIDAK_ADA_AKSES hanya dihitung
   *  selama belum ada bukti akun ini BISA membuka (DIBUKA_TERVERIFIKASI) — kalau sudah ada,
   *  penolakan itu milik wilayahnya (dilewati), bukan tanda akun tanpa akses. */
  function dihitungGagal(status, adaBuktiBisa) {
    if (status === "TIDAK_ADA_AKSES") return !adaBuktiBisa;
    return ["GAGAL_BUKA", "SERVER_SIBUK"].includes(status) || String(status).startsWith("ERROR_");
  }

  /** "/app/surveys/<survei>/<periode>/data" -> periode (null kalau bukan halaman itu). */
  function periodeDariPath(path) {
    const m = /^\/app\/surveys\/[0-9a-f-]{36}\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? m[1] : null;
  }

  /** HTTP yang layak ditunggu & dicoba lagi (rate limit, gateway, jaringan putus = 0). */
  function jenisSementara(httpStatus) {
    return httpStatus === 0 || httpStatus === 429 || httpStatus === 502 || httpStatus === 503 || httpStatus === 504;
  }

  /** Balasan datatable wilayah -> "OK" | "SEMENTARA" | "SESI" | "ANEH".
   *  HTTP 200 dgn `data: null` = server gagal diam-diam, bukan daftar kosong (run user
   *  2026-09-15 saat server lambat: {"draw":0,"recordsTotal":0,"recordsFiltered":0,"data":null}).
   *  opsi.wajibIsi (pindai tanpa kata kunci): recordsTotal 0 juga dianggap sementara —
   *  periode ini punya ±2.600 wilayah, jadi daftar kosong pasti galat. */
  function nilaiDatatable(httpStatus, j, opsi = {}) {
    if (jenisSementara(httpStatus)) return "SEMENTARA";
    if (httpStatus === 401 || httpStatus === 403) return "SESI";
    if (httpStatus !== 200 || !j || typeof j !== "object") return "ANEH";
    if (j.data === null) return "SEMENTARA";
    if (!Array.isArray(j.data)) return "ANEH";
    if (opsi.wajibIsi && j.recordsTotal === 0) return "SEMENTARA";
    return "OK";
  }

  /** Panjang halaman pindai berikutnya setelah satu ukuran gagal terus (null = sudah minimum). */
  function kecilkanHalaman(panjang, minimum = 50) {
    return panjang > minimum ? Math.max(minimum, Math.floor(panjang / 2)) : null;
  }

  /** Keputusan pindai setelah satu halaman -> "LANJUT" | "SELESAI" | "KOSONG_CURIGA" | "MACET".
   *  recordsTotal TIDAK dipakai sbg batas berhenti: run user 2026-09-19 (cakupan semua) hanya
   *  membaca 500 wilayah karena pindai lama berhenti di `start >= recordsTotal` — server diduga
   *  mengisi recordsTotal dgn panjang halaman. Berhenti hanya pada halaman kosong; recordsTotal
   *  terbesar yang pernah terlihat cuma dipakai utk mencurigai halaman kosong yang terlalu dini.
   *  Halaman tanpa satu pun kode baru = server mengulang halaman -> MACET (cegah loop tanpa akhir).
   *  Halaman tidak penuh (< panjang diminta) & tidak kurang dari recordsTotal = halaman terakhir ->
   *  SELESAI tanpa meminta halaman di luar jangkauan (balasan server utk offset itu belum diketahui). */
  function langkahPindai({ jumlahData, panjang, kodeBaru, terkumpul, totalMaks }) {
    if (!jumlahData) return terkumpul < (totalMaks || 0) ? "KOSONG_CURIGA" : "SELESAI";
    if (!kodeBaru) return "MACET";
    if (jumlahData < panjang && terkumpul >= (totalMaks || 0)) return "SELESAI";
    return "LANJUT";
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
    if (jenisSementara(httpStatus)) {
      return { ok: false, status: "SERVER_SIBUK", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
    }
    let j = null;
    try {
      j = JSON.parse(teks);
    } catch (e) {
      return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}, bukan JSON: ${String(teks || "").slice(0, 150)}` };
    }
    if (httpStatus >= 200 && httpStatus < 300 && j && j.success === true) return { ok: true, status: "OK", pesan: j.message || "" };
    if (j && j.success === false && POLA_TANPA_AKSES.test(j.message || "")) {
      return { ok: false, status: "TIDAK_ADA_AKSES", pesan: `HTTP ${httpStatus}: ${j.message}` };
    }
    if (j && j.success === false) return { ok: false, status: "GAGAL_BUKA", pesan: `HTTP ${httpStatus}: ${j.message || "(tanpa pesan)"}` };
    return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
  }

  /** Daftar target yang diproses, sesuai opsi & hasil sebelumnya. */
  function saringTarget(target, sebelumnya, o) {
    let daftar = target.filter((t) => (!o.idsubsls || o.idsubsls.includes(t.idsubsls))
      && !(o.kecuali && o.kecuali.includes(t.idsubsls)));
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

  /** Kode SLS + sub-SLS (6 digit terakhir) semuanya nol, mis. 5108020009000000. */
  const SLS_NOL = new RegExp(`^${KODE_KAB}\\d{6}000000$`);

  /** Cakupan SEMUA: peta pindai -> target urut kode. Kode di luar pola TIDAK diproses.
   *  Kode SLS nol juga dikeluarkan kecuali opsi sertakanSlsNol — sama dgn tandai selesai
   *  (5108020009000000 ditolak "tidak memiliki akses" di endpoint done, 2026-09-15);
   *  apakah undone ikut menolak belum pernah dicoba. */
  function targetDariPindai(peta, opsi = {}) {
    const kode = Object.keys(peta || {}).sort();
    const valid = kode.filter((k) => KODE_VALID.test(k));
    const slsNol = opsi.sertakanSlsNol ? [] : valid.filter((k) => SLS_NOL.test(k));
    return {
      target: valid.filter((k) => !slsNol.includes(k)).map((idsubsls) => ({ idsubsls })),
      tidakValid: kode.filter((k) => !KODE_VALID.test(k)),
      slsNol,
    };
  }

  /** Hitungan per kecamatan (7 digit) — ditampilkan sebelum konfirmasi YA. */
  function perKecamatan(daftar) {
    const hitung = {};
    for (const t of daftar) hitung[t.idsubsls.slice(0, 7)] = (hitung[t.idsubsls.slice(0, 7)] || 0) + 1;
    return hitung;
  }

  /** Apakah `limit` sudah tercapai. Eksekusi menghitung wilayah yang benar-benar DIKIRIMI
   *  permintaan buka (`dibuka`), jadi target yang ternyata sudah terbuka / Tarik Sampel / tidak
   *  ada tidak memakan jatah. Cek menghitung subsls yang diperiksa (`diproses`). */
  function batasTercapai(o, diproses, dibuka) {
    if (!o.limit) return false;
    return (o.mode === "eksekusi" ? dibuka : diproses) >= o.limit;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, CAKUPAN, STATUS_BERHENTI_SEGERA, batasTercapai, periodeDariPath, jenisSementara, nilaiDatatable, kecilkanHalaman, langkahPindai,
      dihitungGagal, rencanakan, nilaiRespons,
      saringTarget, bagiDariPindai, targetDariPindai, perKecamatan,
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
  let panjangPindaiBerhasil = null;

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "bukaWilayah.berhenti() dipanggil");
  }

  function xsrf() {
    const c = document.cookie.split("; ").find((x) => x.startsWith("XSRF-TOKEN="));
    return c ? decodeURIComponent(c.slice("XSRF-TOKEN=".length)) : "";
  }

  /** Jaringan putus -> status 0 (bukan exception), supaya ikut aturan galat sementara. */
  async function post(url, body) {
    try {
      const res = await fetch(url, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-XSRF-TOKEN": xsrf() },
        body: JSON.stringify(body),
      });
      return { status: res.status, teks: await res.text() };
    } catch (e) {
      return { status: 0, teks: String(e && e.message ? e.message : e) };
    }
  }

  /** `start` = OFFSET baris (dialog web keliru mengirim nomor halaman). BACA-SAJA ->
   *  galat sementara (HTTP 429/5xx/jaringan, atau 200 ber-`data: null`) ditunggu
   *  15 dtk x 2^ke (maks 2 menit), maks `maksUlang`x (default 6), lalu SERVER_SIBUK_TERUS. */
  async function datatable(periode, start, length, cari, opsi = {}) {
    const maksUlang = opsi.maksUlang == null ? 6 : opsi.maksUlang;
    for (let ke = 0; ; ke++) {
      cekHenti();
      const { status, teks } = await post(`${API}/datatable?periodeId=${encodeURIComponent(periode)}`,
        { start, length, search: { value: cari, regex: true }, order: [{ column: 0, dir: "asc" }] });
      let j = null;
      try {
        j = JSON.parse(teks);
      } catch (e) {
        j = null;
      }
      const jenis = nilaiDatatable(status, j, opsi);
      if (jenis === "OK") return j;
      if (jenis === "SESI") throw new Berhenti("SESI_DITOLAK", `datatable HTTP ${status}: ${teks.slice(0, 150)}`);
      if (jenis === "ANEH") {
        throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${status}${j ? "" : ", bukan JSON"}: ${teks.slice(0, 150)}`);
      }
      const ringkas = `HTTP ${status}${status === 200 ? " tanpa data" : ""}`;
      if (ke >= maksUlang) {
        throw new Berhenti("SERVER_SIBUK_TERUS", `datatable ${ringkas} setelah ${ke} kali ditunggu: ${teks.slice(0, 150)}`);
      }
      const tunggu = Math.min(15000 * 2 ** ke, 120000);
      log(`⏳ datatable ${ringkas} (${cari ? `cari ${cari}` : `baris ${start}+${length}`}) — tunggu ${Math.round(tunggu / 1000)} dtk lalu ulangi (${ke + 1}/${maksUlang})`);
      for (let t = 0; t < tunggu; t += 1000) {
        cekHenti();
        await sleep(1000);
      }
    }
  }

  async function cariWilayah(periode, kode) {
    return (await datatable(periode, 0, 10, kode)).data;
  }

  /** Status SELURUH wilayah periode (±6 request 500 baris) -> peta kode -> {doneListing, doneTarikSample}.
   *  Berhenti HANYA saat server membalas halaman kosong; `start` maju sebanyak baris yang
   *  BENAR-BENAR diterima (server boleh memotong `length`). recordsTotal tidak dipakai sbg batas
   *  (lihat `langkahPindai`). Server lambat: satu ukuran halaman yang gagal 2x (dgn jeda)
   *  diperkecil separuh s.d. 50 baris; di 50 baris baru dicoba sampai 6x. */
  async function pindaiSemua(periode, o = {}) {
    const peta = {};
    let totalMaks = 0;
    let curiga = 0;
    let start = 0;
    // Ukuran yang terakhir berhasil diingat selama tab tidak di-reload (run berikut tidak mulai dari 500 lagi).
    let panjang = o.panjangPindai || panjangPindaiBerhasil || 500;
    for (let hal = 1; hal <= 1000; hal++) {
      cekHenti();
      let j;
      try {
        // Daftar kosong hanya pasti galat di halaman PERTAMA; di belakang, halaman kosong = akhir daftar.
        j = await datatable(periode, start, panjang, "", { wajibIsi: start === 0, maksUlang: kecilkanHalaman(panjang) ? 1 : 6 });
      } catch (e) {
        const lebihKecil = e instanceof Berhenti && e.kode === "SERVER_SIBUK_TERUS" ? kecilkanHalaman(panjang) : null;
        if (!lebihKecil) throw e;
        log(`⚠️ Pindai ${panjang} baris gagal terus — dicoba ${lebihKecil} baris per request.`);
        panjang = lebihKecil;
        continue; // offset sama, halaman lebih kecil
      }
      if (typeof j.recordsTotal === "number") totalMaks = Math.max(totalMaks, j.recordsTotal);
      panjangPindaiBerhasil = panjang;
      const sebelum = Object.keys(peta).length;
      for (const d of j.data) {
        if (d && d.smallestRegionFullCode) peta[d.smallestRegionFullCode] = { doneListing: d.doneListing, doneTarikSample: d.doneTarikSample };
      }
      const terkumpul = Object.keys(peta).length;
      const langkah = langkahPindai({ jumlahData: j.data.length, panjang, kodeBaru: terkumpul - sebelum, terkumpul, totalMaks });
      log(`Pindai massal: ${terkumpul} wilayah terbaca (baris ${start}+${j.data.length}, recordsTotal ${j.recordsTotal})`);
      if (langkah === "LANJUT") {
        start += j.data.length;
        curiga = 0;
        continue;
      }
      if (langkah === "KOSONG_CURIGA" && ++curiga <= 3) {
        log(`⏳ Halaman kosong di baris ${start}, padahal baru ${terkumpul} dari recordsTotal ${totalMaks} — tunggu ${15 * curiga} dtk lalu ulangi (${curiga}/3)`);
        for (let t = 0; t < 15000 * curiga; t += 1000) {
          cekHenti();
          await sleep(1000);
        }
        continue;
      }
      if (langkah === "MACET") log(`⚠️ Pindai: baris ${start} tidak berisi kode baru (server mengulang halaman?) — berhenti membaca.`);
      break;
    }
    const terkumpul = Object.keys(peta).length;
    if (terkumpul < totalMaks) log(`⚠️ Pindai: hanya ${terkumpul} kode unik dari recordsTotal ${totalMaks}.`);
    log(`Pindai massal selesai: ${terkumpul} wilayah.`);
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

  /** Cari ulang maks 3x (jeda 1,5/3/4,5 dtk) -> true kalau doneListing sudah false. */
  async function verifikasiTerbuka(periode, kode) {
    for (let ke = 1; ke <= 3; ke++) {
      await sleep(1500 * ke);
      if (rencanakan(kode, await cariWilayah(periode, kode), { izinkanTarikSampel: true }).status === "SUDAH_TERBUKA") return true;
    }
    return false;
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
      // Mengubah status wilayah (bisa ditandai selesai lagi, tapi bukan oleh skrip ini).
      hasil.dikirim = true;
      const kirim = await post(`${API}/undone`, r.item);
      const n = nilaiRespons(kirim.status, kirim.teks);
      if (n.status === "SERVER_SIBUK") {
        // Jangan kirim ulang buta: bisa saja server sudah menerapkannya.
        log(`⏳ undone ${t.idsubsls} ${n.pesan} — tunggu 20 dtk lalu baca status`);
        await sleep(20000);
        const terbuka = await verifikasiTerbuka(periode, t.idsubsls);
        Object.assign(hasil, terbuka
          ? { status: "DIBUKA_TERVERIFIKASI", pesan: `respons ${n.pesan}, tapi status sudah Proses Listing` }
          : { status: "SERVER_SIBUK", pesan: `${n.pesan} | status masih Listing Selesai — dicoba lagi di run berikut` });
        return hasil;
      }
      if (!n.ok) {
        Object.assign(hasil, { status: n.status, pesan: n.pesan });
        return hasil;
      }
      const terbuka = await verifikasiTerbuka(periode, t.idsubsls);
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
    const o = { mode: "cek", limit: null, idsubsls: null, kecuali: null, lewatiSelesai: true, izinkanTarikSampel: false,
      sertakanSlsNol: false, pindaiDulu: true, jedaMin: 1500, jedaMaks: 3500, maksGagalBeruntun: 3, ...opsi };
    const semua = CAKUPAN === "semua";
    if (!["cek", "eksekusi"].includes(o.mode)) return log(`mode '${o.mode}' tidak dikenal (cek | eksekusi)`);
    if (berjalan) return log("Masih berjalan — tunggu selesai atau bukaWilayah.berhenti().");
    if (!semua && !TARGET.length) return log("TARGET kosong — tempel buka_wilayah_console.siap.js, bukan template.");
    const periode = periodeDariPath(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !periode) {
      return log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
    }

    const sebelumnya = muatHasil();
    let target = TARGET;
    let peta = null;
    if (o.pindaiDulu || semua) {
      berjalan = true;
      hentikan = false;
      try {
        peta = await pindaiSemua(periode, o);
      } catch (e) {
        if (semua || (e instanceof Berhenti && e.kode !== "RESPONS_TIDAK_DIKENAL")) {
          log(`⛔ Pindai massal gagal — ${e && e.kode ? e.kode + ": " : ""}${e && e.message ? e.message : e}`
            + (semua ? " (cakupan SEMUA butuh hasil pindai; tidak ada yang diproses)" : ""));
          return;
        }
        log(`⚠️ Pindai massal gagal (${e && e.message ? e.message : e}) — semua target dicek satu per satu.`);
      } finally {
        berjalan = false;
      }
    }
    if (semua) {
      const tp = targetDariPindai(peta, o);
      target = tp.target;
      log(`Cakupan SEMUA: ${target.length} subsls di periode ini.`);
      if (tp.tidakValid.length) log(`⚠️ ${tp.tidakValid.length} kode bukan idsubsls 16 digit — TIDAK diproses:`, tp.tidakValid.slice(0, 20));
      if (tp.slsNol.length) {
        const selesai = tp.slsNol.filter((k) => peta[k] && peta[k].doneListing === true).length;
        log(`${tp.slsNol.length} kode SLS nol (…000000, ${selesai} berstatus Listing Selesai) TIDAK diproses. `
          + "Opsi sertakanSlsNol: true utk tetap mencoba.");
      }
    }

    // Dgn pindai, status server yang segar menentukan yang dilewati (bukan hasil lama di browser).
    // limit eksekusi TIDAK memotong daftar — dihitung di loop per wilayah yang benar-benar dibuka (`batasTercapai`).
    let daftar = saringTarget(target, sebelumnya, { ...o, limit: null, lewatiSelesai: o.lewatiSelesai && !peta });
    let dilewati = [];
    if (peta) {
      const bagi = bagiDariPindai(daftar, peta);
      dilewati = bagi.lewati;
      daftar = bagi.proses;
      log(`${dilewati.length} subsls sudah terbuka (dilewati tanpa request), ${daftar.length} diproses satu per satu.`);
    }
    if (o.mode !== "eksekusi" && o.limit) daftar = daftar.slice(0, o.limit);
    if (!daftar.length && !dilewati.length) return log("Tidak ada subsls yang perlu diproses.");

    if (o.mode === "eksekusi" && daftar.length) {
      log("Kandidat dibuka per kecamatan (dicek ulang satu per satu sebelum dibuka):");
      console.table(perKecamatan(daftar));
      const judul = semua ? "SEMUA wilayah periode — termasuk yang ditandai selesai oleh orang lain" : "daftar";
      const maks = o.limit ? Math.min(o.limit, daftar.length) : daftar.length;
      if (prompt(`BUKA WILAYAH (batal Selesai Listing) SUNGGUHAN (${judul}) utk maks. ${maks} subsls.\n`
        + "Ketik YA untuk lanjut:") !== "YA") {
        return log("Dibatalkan.");
      }
    }

    berjalan = true;
    hentikan = false;
    const hitung = {};
    let gagalBeruntun = 0;
    let adaBuktiBisa = Object.values(sebelumnya).some((h) => h.status === "DIBUKA_TERVERIFIKASI");
    const tanpaAkses = [];
    let dibuka = 0;
    try {
      const waktuPindai = new Date().toISOString();
      for (const t of dilewati) {
        simpanHasil({ waktu: waktuPindai, jalan: o.mode, idsubsls: t.idsubsls, status: "SUDAH_TERBUKA",
          done_listing_awal: false, done_tarik_sampel: peta[t.idsubsls].doneTarikSample, id_wilayah: "",
          pesan: "status Proses Listing (pindai massal)" });
        hitung.SUDAH_TERBUKA = (hitung.SUDAH_TERBUKA || 0) + 1;
      }
      for (let i = 0; i < daftar.length; i++) {
        const t = daftar[i];
        const hasil = await prosesTarget(t, periode, o);
        simpanHasil(hasil);
        hitung[hasil.status] = (hitung[hasil.status] || 0) + 1;
        if (hasil.dikirim) dibuka++;
        const jatah = o.mode === "eksekusi" ? ` (dibuka ${dibuka}${o.limit ? "/" + o.limit : ""})` : "";
        log(`[${i + 1}/${daftar.length}]${jatah} ${t.idsubsls} -> ${hasil.status}`, hasil.pesan);
        if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
          log(`⛔ ${hasil.status} — batch DIHENTIKAN. Periksa sebelum menjalankan ulang.`);
          break;
        }
        if (hasil.status === "DIBUKA_TERVERIFIKASI") adaBuktiBisa = true;
        if (hasil.status === "TIDAK_ADA_AKSES") tanpaAkses.push(t.idsubsls);
        const gagal = dihitungGagal(hasil.status, adaBuktiBisa);
        gagalBeruntun = gagal ? gagalBeruntun + 1 : (hasil.status === "TIDAK_ADA_AKSES" ? gagalBeruntun : 0);
        if (gagalBeruntun >= o.maksGagalBeruntun) {
          log(`⛔ ${gagalBeruntun} kegagalan berturut-turut (terakhir ${hasil.status}) — batch DIHENTIKAN.`
            + (hasil.status === "TIDAK_ADA_AKSES" && !adaBuktiBisa
              ? " Akun ini belum pernah berhasil membuka — coba 1 subsls biasa yang Listing Selesai: "
                + '{mode: "eksekusi", idsubsls: ["<kode>"]}'
              : ""));
          break;
        }
        if (batasTercapai(o, i + 1, dibuka)) {
          log(`limit ${o.limit} tercapai — berhenti. Jalankan lagi utk melanjutkan.`);
          break;
        }
        // Jeda panjang hanya setelah request tulis; pencarian baca-saja cukup jeda pendek.
        if (i < daftar.length - 1) await sleep(hasil.dikirim ? acak(o.jedaMin, o.jedaMaks) : acak(300, 800));
      }
    } finally {
      berjalan = false;
      console.table(hitung);
      if (tanpaAkses.length) log(`${tanpaAkses.length} subsls ditolak "tidak memiliki akses" (dilewati):`, tanpaAkses);
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
    jalankan, ringkasan, unduh, target: TARGET, cakupan: CAKUPAN,
    berhenti() {
      hentikan = true;
      log("Akan berhenti di langkah berikutnya.");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil bukaWilayah yang tersimpan di browser ini?")) localStorage.removeItem(KUNCI_HASIL);
    },
  };
  log(CAKUPAN === "semua"
    ? 'Siap: cakupan SEMUA subsls periode (dibaca saat dijalankan). Mulai dgn: await bukaWilayah.jalankan({mode: "cek"})'
    : `Siap: ${TARGET.length} subsls. Mulai dgn: await bukaWilayah.jalankan({mode: "cek"})`);
})(typeof window !== "undefined" ? window : globalThis);
