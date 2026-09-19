/**
 * ubah_moda_console.js — Ganti mode assignment CAPI -> PAPI di fasih-sm dari
 * DevTools Console Chrome BIASA. Padanan ubah_moda.py TANPA Playwright:
 * fasih-sm dilindungi anti-bot (F5/TSPD), jadi di sini yang bekerja hanya tab
 * Chrome milikmu sendiri yang login normal, dgn jeda acak antar langkah.
 *
 * FILE INI TEMPLATE. Target dimuat dgn salah satu cara:
 *   a) LIST KODE IDENTITAS milikmu ("5108060003000402 - UMK - 4", satu per baris):
 *        python ganti_moda/ubah_moda.py --daftar list.xlsx --console
 *      atau tanpa Python: tempel template ini, lalu
 *        ubahModa.muatDaftarKode(`<tempel kolom kode identitas di sini>`)
 *      Tiap kode diproses sendiri: KODE itu diketik di kotak "Cari...", baris
 *      yang kodenya PERSIS sama dicentang ("…- UMK - 4" bukan "…- UMK - 41"),
 *      "Ganti Mode (Ke PAPI) (1)", lalu kode itu dicari ulang utk verifikasi.
 *      Opsi cakupan diabaikan. Kode yang sudah PAPI dilewati (KODE_SUDAH_PAPI),
 *      kode yang tidak ada dilaporkan (KODE_TIDAK_ADA). Kalau hasil pencarian
 *      kode malah berisi subsls lain -> PENCARIAN_TIDAK_MENYARING (berhenti).
 *   b) Sheet input usaha (skrip memilih sendiri 1 CAPI per subsls):
 *        python ganti_moda/ubah_moda.py --sumber input_usaha.xlsx --console
 * -> ubah_moda_console.siap.js (berisi email PPL, sudah di .gitignore).
 *
 * CARA PAKAI
 * ----------
 * 1. Chrome biasa, VPN aktif, login manual ke fasih-sm dgn akun yang berhak
 *    "Ganti Mode". Buka list dgn perPage=100 (skrip menolak jalan kalau kurang
 *    dari 50 — makin banyak baris tampil, makin besar peluang PAPI terlihat).
 *    JANGAN pasang filter Mode (belum didukung — lihat petakanFilter di bawah):
 *    https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=100
 * 2. F12 -> Console -> tempel SELURUH isi ubah_moda_console.siap.js -> Enter.
 *    (Pertama kali, Chrome minta ketik: allow pasting)
 * 3. Jalankan:
 *      await ubahModa.jalankan({mode: "petakan"})             // 1 target: cari & baca tabel, TANPA centang
 *      await ubahModa.jalankan({mode: "otomatis", limit: 3})  // skrip klik Ganti Mode + konfirmasi (ketik YA)
 *      await ubahModa.jalankan({mode: "otomatis"})            // sisanya
 *    Opsional: mode "dryrun" (centang, cocokkan angka menu, lepas centang — tanpa klik)
 *    dan "manual" (KAMU yang klik Ganti Mode). Otomatis tidak mensyaratkan manual dulu.
 *    ubahModa.berhenti()      hentikan di langkah berikutnya
 *    ubahModa.ringkasan()     hitungan status
 *    ubahModa.unduh()         unduh hasil CSV (simpan sbg audit)
 *    ubahModa.dialogTerakhir() teks & tombol dialog konfirmasi terakhir yang terlihat
 *    ubahModa.petakanFilter() READ-ONLY: rekam struktur filter Mode (lihat bawah)
 *    Opsi lain: cakupan: "satu"|"semua", idsubsls: [...],
 *    lewatiSelesai (default true), jedaMin/jedaMaks (ms).
 *
 * ATURAN (ketetapan user 2026-09-14)
 * ----------------------------------
 * - Cukup SATU assignment PAPI mana pun per subsls. Petugasnya tidak harus PPL
 *   sheet; milik PPL sheet hanya didahulukan kalau ada.
 * - PAGINASI TIDAK PERNAH DIPINDAH. Halaman yang dipindah tidak memuat datanya
 *   dgn benar (kemungkinan besar penyebab subsls kedua pada dryrun pertama
 *   terbaca 100 baris subsls lain). Skrip hanya membaca halaman yang tampil
 *   setelah pencarian. Akibatnya PAPI yang ada di halaman 2 dst. tidak terlihat
 *   -> subsls itu bisa mendapat 1 PAPI tambahan (diizinkan user: "pilih
 *   terserah"); kolom pesan mencatat "N halaman, hanya halaman tampil dibaca".
 *   Filter Mode = PAPI bisa menutup celah itu, tapi struktur filternya belum
 *   dipetakan: buka filter secara MANUAL, jalankan ubahModa.petakanFilter()
 *   di tiap langkah (ikon filter terbuka, Mode dipilih, PAPI dipilih), kirim hasilnya.
 *
 * KESELAMATAN
 * -----------
 * - Baris subsls LAIN yang ikut tampil di hasil pencarian diabaikan — tidak
 *   pernah dipilih; kalau sampai tercentang, CENTANG_TIDAK_SESUAI menghentikan batch.
 * - Mode "petakan" & "dryrun" TIDAK PERNAH mengklik item "Ganti Mode".
 * - Mode "manual": skrip mencari, mencentang, membuka menu & menyorot item —
 *   klik yang IRREVERSIBLE dilakukan manusia. Skrip lalu memverifikasi Mode = PAPI.
 * - Mode "otomatis" (2026-09-15, tanpa syarat manual): ketik YA per batch; dialog
 *   yang tidak menyebut PAPI/mode atau tombol konfirmasi yang ambigu -> berhenti.
 * - Batch BERHENTI SEKETIKA kalau: subsls tidak tampil di halaman hasil
 *   pencarian, kolom Mode/Petugas tidak tampil, baris yang tercentang di
 *   halaman != yang direncanakan, angka "(N)" di menu != jumlah dicentang,
 *   menu tidak mau tertutup, dialog/tombol tidak jelas, atau mode tidak
 *   terverifikasi PAPI.
 * - Hasil disimpan di localStorage browser ini (tahan reload), jadi batch
 *   yang terputus bisa dilanjutkan dgn menempel ulang & jalankan lagi.
 *
 * Temuan halaman (dipetakan 2026-09-13) & alasan tiap penjagaan: lihat
 * docstring ubah_moda.py dan docs/PANDUAN_UBAH_MODA.md.
 */
(function (global) {
  "use strict";

  const TARGET = /*__TARGET__*/[];

  // -------------------------------------------------------------------------
  // Logika murni — sama dgn ubah_moda.py, diuji: node tests/test_ubah_moda_console.js
  // -------------------------------------------------------------------------
  const KOLOM_TABEL = {
    kode: "Kode Identitas", status: "Status", mode: "Mode",
    petugas: "Petugas Saat Ini", keterangan: "Keterangan",
  };
  const POLA_ITEM_GANTI_MODE = /Ganti Mode\s*\(\s*Ke PAPI\s*\)/i;
  const POLA_TOMBOL_KONFIRMASI = /^\s*(ya|konfirmasi|ganti|ubah|lanjut|lanjutkan|simpan|ok|oke|proses)\b/i;
  const POLA_TOMBOL_BATAL = /batal|tutup|cancel|kembali|^\s*tidak\b/i;

  const STATUS_TUNTAS_LIVE = new Set(["DIUBAH_TERVERIFIKASI", "SUDAH_ADA_PAPI", "TIDAK_ADA_CAPI", "KODE_SUDAH_PAPI"]);
  const STATUS_TUNTAS_DRY = new Set([...STATUS_TUNTAS_LIVE, "DRY_RUN_AKAN_DIUBAH"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SUBSLS_TIDAK_TAMPIL", "PERLU_HALAMAN_LAIN", "KOLOM_TIDAK_ADA", "PER_PAGE_KECIL",
    "JUMLAH_TERCENTANG_BEDA", "CENTANG_TIDAK_SESUAI", "MENU_TIDAK_TERTUTUP",
    "TABEL_BERUBAH", "DIALOG_TIDAK_DIKENAL", "TOMBOL_KONFIRMASI_AMBIGU", "DIUBAH_BELUM_TERVERIFIKASI",
    "BELUM_BERUBAH", "CENTANG_GAGAL", "ITEM_MENU_TIDAK_ADA", "DIHENTIKAN_PENGGUNA",
    "PENCARIAN_TIDAK_MENYARING", "KODE_GANDA", "RATE_LIMIT",
  ]);
  // Tidak menghentikan batch sekali muncul (permintaan user 2026-09-14: "tetap jalankan"),
  // tapi 3x berturut-turut = masalah sistematis (akun/tampilan) -> berhenti.
  // Aman: status ini muncul SEBELUM item "Ganti Mode" bisa diklik, dan centangnya dilepas.
  const STATUS_LANJUT_TAPI_HITUNG = new Set(["TIDAK_ADA_AKSES"]);
  // Status yang berarti item "Ganti Mode" sudah diklik (jeda panjang sesudahnya).
  const STATUS_SETELAH_KLIK = new Set(["DIUBAH_TERVERIFIKASI", "DIUBAH_MENUNGGU", "DIUBAH_BELUM_TERVERIFIKASI", "BELUM_BERUBAH"]);
  // Sudah diklik & dikonfirmasi tapi Mode belum terbaca PAPI -> JANGAN diklik ulang otomatis.
  const STATUS_SUDAH_DIKLIK = new Set(["DIUBAH_MENUNGGU", "DIUBAH_BELUM_TERVERIFIKASI"]);

  // Perubahan mode TIDAK langsung terbaca di tabel (run user 2026-09-15: 3x cari ulang
  // dlm ±10 dtk setelah konfirmasi tetap CAPI, dan cek beruntun itu memicu HTTP 429).
  // Jadwal cek ulang sejak diklik & batas tunggunya — HARUS sama dgn ubah_moda.py.
  const JADWAL_CEK_VERIFIKASI_MS = [30000, 45000, 60000, 90000, 120000];
  const JEDA_CEK_VERIFIKASI_MAKS_MS = 180000;
  const BATAS_TUNGGU_VERIFIKASI_MS = 15 * 60000;
  const BATAS_ULANG_429 = 6;

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  const bersih = (t) => String(t == null ? "" : t).replace(/\s+/g, " ").trim();

  function idsubslsDariKode(kode) {
    const m = /^\s*(\d{16})/.exec(kode || "");
    return m ? m[1] : "";
  }

  // Kode identitas = teks kolom "Kode Identitas" APA ADANYA: 16 digit idsubsls, "-",
  // lalu apa pun ("5108060029000101 - I KADEK CONTOH / NI KADEK CONTOH - 19 / - 0 - 2. Tidak").
  // Terbukti 2026-09-15: kolom code_identity list user = teks sel tabel fasih-sm
  // (10/10 cocok). Jadi TIDAK diurai/dipotong — dicari & dicocokkan utuh
  // (spasi dirapikan, huruf besar/kecil diabaikan).
  const POLA_KODE_IDENTITAS = /^\d{16}\s*-\s*\S/;

  /** Teks kode identitas yang dirapikan spasinya; "" kalau bukan kode. */
  function normalisasiKode(teks) {
    const s = bersih(teks);
    return POLA_KODE_IDENTITAS.test(s) ? s : "";
  }

  /** Pembanding kode: spasi dirapikan, huruf besar/kecil diabaikan. */
  const samaKode = (a, b) => bersih(a).toUpperCase() === bersih(b).toUpperCase();

  /** Daftar kode identitas milik user (satu teks = satu baris file, sel dipisah TAB)
   *  -> {targets, tidakDikenali, ganda}. SATU TARGET PER KODE: teks kode utuh yang
   *  diketik di kotak "Cari...". Sel lain (judul kolom, nama, nomor) diabaikan;
   *  baris tanpa kode yang berisi angka+"-" atau angka 16 digit dilaporkan. */
  function targetDariDaftarKode(barisTeks) {
    const targets = [];
    const sudah = new Set();
    const tidakDikenali = [];
    const ganda = [];
    barisTeks.forEach((teks, i) => {
      const no = i + 1;
      const sel = String(teks == null ? "" : teks).split("\t").map(bersih).filter(Boolean);
      const kode = sel.map(normalisasiKode).filter(Boolean);
      if (!kode.length) {
        const curiga = sel.find((s) => /^\d+\s*-/.test(s) || /^\d{16}$/.test(s));
        if (curiga) tidakDikenali.push([no, curiga.slice(0, 80)]);
        return;
      }
      for (const k of kode) {
        if (sudah.has(k.toUpperCase())) {
          ganda.push([no, k]);
          continue;
        }
        sudah.add(k.toUpperCase());
        targets.push({ kode: k, idsubsls: k.slice(0, 16), baris: [no], ppl: [] });
      }
    });
    return { targets, tidakDikenali, ganda };
  }

  /** Kunci hasil tersimpan: kode identitas (target list) atau idsubsls (target sheet). */
  const kunciTarget = (t) => t.kode || t.idsubsls;

  /** Teks yang diketik di kotak "Cari...". */
  const istilahCari = (t) => t.kode || t.idsubsls;

  /** Baris tabel yang dicari target ini: kode UTUH sama ("…- UMK - 4" bukan "…- UMK - 41"),
   *  atau semua baris subsls-nya utk target sheet. */
  const cocokTarget = (t) => (t.kode
    ? (b) => samaKode(b.kode, t.kode)
    : (b) => b.idsubsls === t.idsubsls);

  /** "Page 3 of 33" -> [3, 33]; null kalau tidak ada paginasi. */
  function bacaHalaman(teks) {
    const m = /Page\s+(\d+)\s+of\s+(\d+)/i.exec(teks || "");
    return m ? [Number(m[1]), Number(m[2])] : null;
  }

  /** {head, rows} dari tabel -> baris assignment, dipetakan lewat JUDUL kolom. */
  function barisDariTabel(data) {
    if (!data) throw new Berhenti("KOLOM_TIDAK_ADA", "tabel berjudul 'Kode Identitas' tidak ditemukan");
    const head = (data.head || []).map(bersih);
    const idx = {};
    for (const [key, judul] of Object.entries(KOLOM_TABEL)) {
      const i = head.findIndex((h) => h.toLowerCase() === judul.toLowerCase());
      if (i < 0) {
        if (key === "keterangan") continue;
        throw new Berhenti("KOLOM_TIDAK_ADA",
          `kolom '${judul}' tidak tampil (judul terbaca: ${JSON.stringify(head)}). Tampilkan lewat tombol 'Kolom'.`);
      }
      idx[key] = i;
    }
    const maks = Math.max(...Object.values(idx));
    const out = [];
    (data.rows || []).forEach((sel, indeks) => {
      if (sel.length <= maks) return; // baris pesan "tidak ada data" (colspan)
      const b = { indeks, keterangan: "" };
      for (const [key, i] of Object.entries(idx)) b[key] = bersih(sel[i]);
      b.idsubsls = idsubslsDariKode(b.kode);
      if (b.idsubsls) out.push(b);
    });
    return out;
  }

  /** target {idsubsls, ppl: [...]} + baris HALAMAN YANG TAMPIL -> {status, pilih, pesan}.
   *
   *  Cakupan "satu": cukup SATU assignment PAPI mana pun di subsls itu — petugasnya
   *  TIDAK harus PPL sheet (ketetapan user 2026-09-14). Milik PPL sheet hanya
   *  didahulukan. Baris subsls LAIN diabaikan (tidak pernah dipilih).
   *  adaHalamanLain = hasil pencarian > 1 halaman; halaman lain SENGAJA tidak
   *  dibaca (paginasi tidak dipindah), jadi PAPI di sana tidak terlihat. */
  function rencanakan(target, baris, cakupan = "satu", adaHalamanLain = false) {
    if (target.kode) return rencanakanKode(target, baris, adaHalamanLain);
    const milik = baris.filter((b) => b.idsubsls === target.idsubsls);
    const nAsing = baris.length - milik.length;
    const catatan = (nAsing ? ` | ${nAsing} baris subsls lain diabaikan` : "")
      + (adaHalamanLain ? " | >1 halaman, hanya halaman tampil yang dibaca" : "");
    if (!milik.length) {
      if (nAsing || adaHalamanLain) {
        return { status: "SUBSLS_TIDAK_TAMPIL", pilih: [],
          pesan: `halaman hasil pencarian tidak memuat satu pun baris ${target.idsubsls} — pencarian tidak menyaring?${catatan}` };
      }
      return { status: "TIDAK_ADA_ASSIGNMENT", pilih: [],
        pesan: `tidak ada assignment subsls ini di hasil pencarian — tidak bisa dibantu dgn ganti mode${catatan}` };
    }
    const aneh = [...new Set(milik.map((b) => b.mode).filter((m) => !["CAPI", "PAPI"].includes(m.toUpperCase())))];
    if (aneh.length) return { status: "MODE_TIDAK_DIKENAL", pilih: [], pesan: `nilai kolom Mode: ${aneh}${catatan}` };

    const capi = milik.filter((b) => b.mode.toUpperCase() === "CAPI");
    const papi = milik.filter((b) => b.mode.toUpperCase() === "PAPI");

    if (cakupan === "semua") {
      if (capi.length) return { status: "PERLU_DIUBAH", pilih: capi, pesan: `${capi.length} assignment CAPI yang tampil${catatan}` };
      if (adaHalamanLain) {
        return { status: "PERLU_HALAMAN_LAIN", pilih: [],
          pesan: `tidak ada CAPI di halaman tampil, sisa CAPI (kalau ada) di halaman lain — butuh filter Mode${catatan}` };
      }
      return { status: "TIDAK_ADA_CAPI", pilih: [], pesan: `${papi.length} assignment sudah PAPI${catatan}` };
    }
    if (papi.length) {
      return { status: "SUDAH_ADA_PAPI", pilih: [],
        pesan: `${papi.length} assignment sudah PAPI (mis. ${papi[0].kode}, petugas ${papi[0].petugas})${catatan}` };
    }
    const ppl = new Set((target.ppl || []).map((p) => p.toLowerCase()));
    const pilih = capi.find((b) => ppl.has(b.petugas.trim().toLowerCase())) || capi[0];
    const punyaPpl = ppl.has(pilih.petugas.trim().toLowerCase());
    return { status: "PERLU_DIUBAH", pilih: [pilih],
      pesan: `1 dari ${capi.length} assignment CAPI (petugas ${pilih.petugas}${punyaPpl ? " = PPL sheet" : ""})${catatan}` };
  }

  /** Target kode identitas (hasil pencarian KODE itu) -> HANYA baris kode itu yang
   *  diubah (cakupan diabaikan). Baris lain yang ikut tampil (mis. "…- UMK - 41"
   *  saat mencari "…- UMK - 4") diabaikan. */
  function rencanakanKode(target, baris, adaHalamanLain = false) {
    const cocok = baris.filter(cocokTarget(target));
    const nLain = baris.length - cocok.length;
    const catatan = nLain ? ` | ${nLain} baris kode lain ikut tampil, diabaikan` : "";
    if (cocok.length > 1) {
      return { status: "KODE_GANDA", pilih: [],
        pesan: `kode ${target.kode} tampil ${cocok.length}x di hasil pencarian — tidak dipilih${catatan}` };
    }
    if (!cocok.length) {
      const subslsLain = baris.filter((b) => b.idsubsls !== target.idsubsls).length;
      if (subslsLain) {
        return { status: "PENCARIAN_TIDAK_MENYARING", pilih: [],
          pesan: `hasil pencarian ${target.kode} memuat ${subslsLain} baris subsls lain & kode itu tidak ada — `
            + `kotak Cari tidak menyaring per kode identitas?${catatan}` };
      }
      if (adaHalamanLain) {
        return { status: "KODE_TIDAK_TAMPIL", pilih: [],
          pesan: `kode tidak ada di halaman tampil, hasil pencarian >1 halaman${catatan}` };
      }
      return { status: "KODE_TIDAK_ADA", pilih: [],
        pesan: `kode tidak ditemukan di fasih-sm — cek penulisan kode / periode survei${catatan}` };
    }
    const b = cocok[0];
    const mode = b.mode.toUpperCase();
    if (mode === "PAPI") return { status: "KODE_SUDAH_PAPI", pilih: [], pesan: `sudah PAPI (petugas ${b.petugas})${catatan}` };
    if (mode !== "CAPI") return { status: "MODE_TIDAK_DIKENAL", pilih: [], pesan: `nilai kolom Mode: ${b.mode}${catatan}` };
    return { status: "PERLU_DIUBAH", pilih: [b], pesan: `CAPI (petugas ${b.petugas})${catatan}` };
  }

  function angkaItemMenu(teks) {
    const m = /\(\s*(\d+)\s*\)\s*$/.exec(bersih(teks));
    return m ? Number(m[1]) : null;
  }

  function pilihTombolKonfirmasi(teksTombol) {
    const kandidat = [];
    teksTombol.forEach((t, i) => {
      if (POLA_TOMBOL_KONFIRMASI.test(t || "") && !POLA_TOMBOL_BATAL.test(t || "")) kandidat.push(i);
    });
    return kandidat.length === 1 ? kandidat[0] : null;
  }

  /** Jeda sebelum cek ulang berikutnya (ke = jumlah cek yang sudah dilakukan). */
  function jedaCekVerifikasi(ke) {
    return ke < JADWAL_CEK_VERIFIKASI_MS.length ? JADWAL_CEK_VERIFIKASI_MS[ke] : JEDA_CEK_VERIFIKASI_MAKS_MS;
  }

  /** {kode: mode terbaca} -> "TERVERIFIKASI" (semua PAPI) | "MENUNGGU" | "BELUM_TERVERIFIKASI"
   *  (batas tunggu habis). Kode yang tidak tampil ("(hilang)") dianggap belum berubah. */
  function putuskanVerifikasi(mode, sejakKlikMs, batasMs = BATAS_TUNGGU_VERIFIKASI_MS) {
    const nilai = Object.values(mode || {});
    if (nilai.length && nilai.every((m) => String(m).toUpperCase() === "PAPI")) return "TERVERIFIKASI";
    return sejakKlikMs >= batasMs ? "BELUM_TERVERIFIKASI" : "MENUNGGU";
  }

  /** Lama menunggu sebelum mengulang pencarian yang kena HTTP 429 (percobaan ke-0,1,..).
   *  Retry-After (detik) dihormati; tanpa itu 15 dtk x 2^ke, maks 2 menit. Sama dgn pindah_wilayah_console.js. */
  function jedaRateLimit(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Hasil tersimpan -> kode yang SUDAH diklik "Ganti Mode" tapi belum terbukti PAPI. Kode ini
   *  hanya DIPERIKSA di run berikut, tidak diklik ulang. `waktu_klik` ikut dihitung supaya
   *  kegagalan SETELAH klik (mis. gagal melepas centang) tidak membuat kodenya diklik lagi. */
  function kodeSudahDiklik(lama) {
    if (!lama || STATUS_TUNTAS_LIVE.has(lama.status)) return [];
    if (!STATUS_SUDAH_DIKLIK.has(lama.status) && !lama.waktu_klik) return [];
    return String(lama.dipilih || "").split(" | ").map(bersih).filter(Boolean);
  }

  /** Epoch ms saat diklik; hasil lama (sebelum ada waktu_klik) memakai waktu mulai proses. NaN kalau tidak ada. */
  const waktuKlikDari = (lama) => Date.parse((lama && (lama.waktu_klik || lama.waktu)) || "");

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, Berhenti, barisDariTabel, rencanakan, angkaItemMenu, pilihTombolKonfirmasi,
      idsubslsDariKode, bacaHalaman, normalisasiKode, targetDariDaftarKode, kunciTarget, istilahCari, cocokTarget,
      jedaCekVerifikasi, putuskanVerifikasi, jedaRateLimit, kodeSudahDiklik, waktuKlikDari,
      STATUS_TUNTAS_LIVE, STATUS_BERHENTI_SEGERA,
    };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "ubahModa.hasil.v1";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const tampak = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const log = (...a) => console.log("%c[ubahModa]", "color:#e65100;font-weight:bold", ...a);

  let hentikan = false;
  let berjalan = false;

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "ubahModa.berhenti() dipanggil");
  }

  async function tunggu(fn, batasMs, jedaMs = 250) {
    const akhir = Date.now() + batasMs;
    while (Date.now() < akhir) {
      const v = fn();
      if (v) return v;
      await sleep(jedaMs);
      cekHenti();
    }
    return null;
  }

  /** sleep panjang yang tetap bisa dihentikan ubahModa.berhenti() (dicek tiap detik). */
  async function tidur(ms) {
    for (const akhir = Date.now() + ms; Date.now() < akhir;) {
      cekHenti();
      await sleep(Math.min(1000, akhir - Date.now()));
    }
  }

  // --- rate limit (HTTP 429) ----------------------------------------------------
  // Request datatable dikirim HALAMAN (bukan skrip), jadi statusnya dibaca lewat
  // PerformanceObserver (responseStatus, Chrome >= 109). Waktu dicatat dgn jam
  // performance.now() yang sama dgn entri (Date.now() bisa bergeser saat laptop tidur).
  const POLA_URL_DATATABLE = /\/datatable-all-user-survey-periode\b/;
  const waktu429 = [];
  let pantau429 = false;
  try {
    if (global.__ubahModaPantau429) global.__ubahModaPantau429.disconnect(); // skrip ditempel ulang
    const obs = new PerformanceObserver((daftar) => {
      for (const en of daftar.getEntries()) {
        if (en.responseStatus === 429 && POLA_URL_DATATABLE.test(en.name)) waktu429.push(en.responseEnd);
      }
    });
    obs.observe({ type: "resource" });
    global.__ubahModaPantau429 = obs;
    pantau429 = typeof PerformanceResourceTiming !== "undefined" && "responseStatus" in PerformanceResourceTiming.prototype;
  } catch (e) {
    pantau429 = false;
  }
  const ada429Sejak = (mulai) => waktu429.some((w) => w >= mulai);

  function tabel() {
    return [...document.querySelectorAll("table")].filter(tampak).find((t) => /Kode Identitas/i.test(t.innerText)) || null;
  }

  function bacaTabel() {
    const t = tabel();
    if (!t) return null;
    const head = [...t.querySelectorAll("thead th")].map((h) => bersih(h.innerText));
    const rows = [...t.querySelectorAll("tbody tr")].map((tr) => [...tr.querySelectorAll("td")].map((td) => bersih(td.innerText)));
    return { head, rows, halaman: bacaHalaman(document.body.innerText) || [1, 1] };
  }

  function bacaTabelWajib() {
    const d = bacaTabel();
    if (!d) throw new Berhenti("KOLOM_TIDAK_ADA", "tabel 'Kode Identitas' hilang dari halaman");
    return d;
  }

  /** Baris tabel saat ini; [] kalau tabel belum/tidak terbaca (mis. sedang memuat). */
  function barisTerbaca() {
    try {
      return barisDariTabel(bacaTabel());
    } catch (e) {
      return [];
    }
  }

  const tandaTabel = () => {
    const d = bacaTabel();
    return d ? JSON.stringify(d.rows) : "";
  };

  async function tungguStabil(diamMs = 1500, batasMs = 15000) {
    let tanda = tandaTabel();
    let sejak = Date.now();
    const akhir = Date.now() + batasMs;
    while (Date.now() < akhir) {
      await sleep(300);
      cekHenti();
      const baru = tandaTabel();
      if (baru !== tanda) {
        tanda = baru;
        sejak = Date.now();
      } else if (Date.now() - sejak >= diamMs) {
        return;
      }
    }
  }

  const menuTerbuka = () => [...document.querySelectorAll('[role="menu"]')].some(tampak);
  const dialogTerbuka = () => [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(tampak).pop() || null;

  function tekanEscape() {
    const o = { key: "Escape", code: "Escape", keyCode: 27, bubbles: true, cancelable: true };
    (document.activeElement || document.body).dispatchEvent(new KeyboardEvent("keydown", o));
  }

  /** Menu yang masih terbuka MENELAN klik berikutnya (terjadi saat pemetaan:
   *  klik ikon filter malah mengenai "Broadcast Status"). Wajib sebelum klik apa pun. */
  async function tutupMenu() {
    if (!menuTerbuka()) return;
    tekanEscape();
    if (await tunggu(() => !menuTerbuka(), 3000)) return;
    const luar = [...document.querySelectorAll("h1,h2,h3")].find((h) => bersih(h.innerText) === "Data") || document.body;
    luar.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse", isPrimary: true }));
    if (await tunggu(() => !menuTerbuka(), 3000)) return;
    throw new Berhenti("MENU_TIDAK_TERTUTUP", "menu tetap terbuka — klik berikutnya bisa mengenai item menu");
  }

  function kotakCari() {
    return [...document.querySelectorAll('input[placeholder="Cari..."]')].filter(tampak).find((i) => !i.closest('[role="dialog"]')) || null;
  }

  /** Enter dikirim SETELAH jeda: kalau langsung, handler React bisa masih memegang
   *  isian lama (render belum jalan) -> pencarian terkirim dgn nilai lama & responsnya
   *  bisa tiba belakangan menimpa hasil (dugaan penyebab "belum tampak baris" 2026-09-15). */
  async function isiInputReact(el, nilai) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    el.focus();
    setter.call(el, nilai);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(400);
    const o = { key: "Enter", code: "Enter", keyCode: 13, bubbles: true, cancelable: true };
    el.dispatchEvent(new KeyboardEvent("keydown", o));
    el.dispatchEvent(new KeyboardEvent("keyup", o));
  }

  /** Tunggu sampai tabel memuat hasil pencarian INI (berubah dari `sebelum`, lalu diam):
   *  "KETEMU"   = baris yang dicari tampil;
   *  "TERSARING" = semua baris milik subsls target tapi baris yang dicari tidak ada;
   *  "KOSONG"   = tabel tanpa baris (kode/subsls tidak ada);
   *  null       = batas waktu habis, tabel masih berisi subsls lain / belum berubah,
   *               atau batal() bernilai true (pencarian kena HTTP 429). */
  async function tungguHasilCari(sebelum, t, batasMs = 20000, batal = () => false) {
    const target = cocokTarget(t);
    const milikSubsls = (b) => b.idsubsls === t.idsubsls;
    const baca = () => {
      const baris = barisTerbaca();
      if (baris.some(target)) return "KETEMU";
      if (baris.length && baris.every(milikSubsls)) return "TERSARING";
      if (!baris.length && tabel()) return "KOSONG";
      return null;
    };
    const akhir = Date.now() + batasMs;
    let berubah = false;
    while (Date.now() < akhir) {
      if (batal()) return null;
      berubah = berubah || tandaTabel() !== sebelum;
      const v = berubah && baca();
      if (v) {
        // Tabel kosong bisa juga berarti "sedang memuat" -> tunggu diam lebih lama.
        await tungguStabil(v === "KOSONG" ? 3000 : 1500);
        if (baca() === v) return v;
      }
      await sleep(300);
      cekHenti();
    }
    return null;
  }

  /** Saring lewat "Cari..." lalu baca HANYA halaman yang tampil. Paginasi TIDAK
   *  PERNAH dipindah: halaman yang dipindah tidak memuat datanya dgn benar
   *  (temuan user 2026-09-14). Baris lain tidak dibuang di sini — rencanakan()
   *  yang mengabaikannya. Target list kode dicari dgn KODE-nya, target sheet dgn
   *  idsubsls. -> {baris, halaman: [ke, dari]}
   *
   *  Pencarian yang kena HTTP 429 dibuang (tabelnya bisa masih milik pencarian
   *  sebelumnya): tunggu jedaRateLimit lalu ulangi, maks BATAS_ULANG_429 kali -> RATE_LIMIT. */
  async function cari(t) {
    const istilah = istilahCari(t);
    const target = cocokTarget(t);
    for (let ulang = 0; ; ulang++) {
      const mulai = performance.now();
      const kena429 = () => ada429Sejak(mulai);
      await tutupMenu();
      const kotak = kotakCari();
      if (!kotak) throw new Berhenti("KOLOM_TIDAK_ADA", "kotak 'Cari...' tidak ditemukan");
      // Kotak berisi istilah yg SAMA (verifikasi): kosongkan dulu supaya data dimuat
      // ulang, dan TUNGGU daftar tanpa-saring benar-benar tampil sebelum mengisi lagi
      // — kalau tidak, respons isian "" bisa tiba belakangan & menimpa hasil.
      // Kalau isinya istilah lain, langsung ditimpa.
      if (kotak.value === istilah) {
        const sebelum = tandaTabel();
        await kirimCari(kotak, "");
        await tunggu(() => kena429() || (tandaTabel() !== sebelum && barisTerbaca().some((b) => !target(b))), 20000);
        if (!kena429()) await tungguStabil();
      }
      // Maks 2x: kalau tabel belum tersaring (respons tertukar / pencarian tidak
      // terpicu), istilah diketik ulang sekali lagi sebelum tabel dibaca apa adanya.
      let hasilCari = null;
      for (let ke = 1; ke <= 2 && !hasilCari && !kena429(); ke++) {
        const sebelum = tandaTabel();
        await kirimCari(kotakCari() || kotak, istilah);
        hasilCari = await tungguHasilCari(sebelum, t, 20000, kena429);
        if (!hasilCari && ke === 1 && !kena429()) log(`⚠️ tabel belum tersaring utk "${istilah}" — pencarian diulang.`);
      }
      await sleep(500); // entri PerformanceObserver diserahkan asinkron
      if (kena429()) {
        if (ulang >= BATAS_ULANG_429) {
          throw new Berhenti("RATE_LIMIT",
            `pencarian "${istilah}" masih HTTP 429 setelah ${ulang} kali menunggu — tunggu beberapa menit lalu jalankan ulang`);
        }
        const jeda = jedaRateLimit(ulang);
        log(`⏳ HTTP 429 (rate limit) saat mencari "${istilah}" — isi tabel tidak dipakai. `
          + `Tunggu ${Math.round(jeda / 1000)} dtk lalu cari ulang (${ulang + 1}/${BATAS_ULANG_429}).`);
        await tidur(jeda);
        continue;
      }
      if (!hasilCari) log(`⚠️ tabel tetap belum tersaring utk "${istilah}" — dibaca apa adanya.`);
      const d = bacaTabelWajib();
      const baris = barisDariTabel(d).map((b) => ({ ...b, halaman: d.halaman[0] }));
      const nTarget = baris.filter(target).length;
      log(`Pencarian "${istilah}": halaman ${d.halaman[0]} dari ${d.halaman[1]}, ${baris.length} baris tampil `
        + `(${nTarget} ${t.kode ? "kode persis" : "milik subsls ini"}). Halaman lain tidak dibaca.`);
      if (d.halaman[1] > 1 && baris.length < 50) {
        throw new Berhenti("PER_PAGE_KECIL",
          `hanya ${baris.length} baris/halaman utk ${d.halaman[1]} halaman — buka list dgn perPage=100`);
      }
      return { baris, halaman: d.halaman };
    }
  }

  // Jarak minimal antar-pencarian yang dikirim skrip (rate limit fasih-sm); opsi jarakCariMs.
  let jarakCariMs = 2000;
  let cariTerakhir = 0;

  async function kirimCari(kotak, nilai) {
    const jeda = cariTerakhir + jarakCariMs - Date.now();
    if (jeda > 0) await tidur(jeda);
    cariTerakhir = Date.now();
    await isiInputReact(kotak, nilai);
  }

  // --- centang ----------------------------------------------------------------
  const tercentang = (cb) => (cb.matches("input") ? cb.checked
    : cb.getAttribute("aria-checked") === "true" || cb.getAttribute("data-state") === "checked");

  /** Checkbox baris `b`, setelah memastikan halaman & kode di indeks itu PERSIS
   *  sama ("…- UMK - 4" jangan sampai tertukar dgn "…- UMK - 41"). */
  function checkboxBaris(b) {
    const d = bacaTabelWajib();
    const tr = tabel().querySelectorAll("tbody tr")[b.indeks];
    const sekarang = barisDariTabel(d).find((x) => x.indeks === b.indeks);
    if (d.halaman[0] !== b.halaman || !tr || !sekarang || sekarang.kode !== b.kode) {
      throw new Berhenti("TABEL_BERUBAH", `halaman ${b.halaman} baris ke-${b.indeks} bukan lagi '${b.kode}'`);
    }
    const cb = tr.querySelector('[role="checkbox"], input[type="checkbox"]');
    if (!cb) throw new Berhenti("CENTANG_GAGAL", `checkbox '${b.kode}' tidak ada`);
    return cb;
  }

  async function aturCentang(daftar, centang) {
    for (const b of daftar) {
      await tutupMenu();
      if (tercentang(checkboxBaris(b)) !== centang) {
        checkboxBaris(b).click();
        await tunggu(() => tercentang(checkboxBaris(b)) === centang, 3000);
      }
      if (tercentang(checkboxBaris(b)) !== centang) {
        throw new Berhenti("CENTANG_GAGAL", `checkbox '${b.kode}' tidak berubah jadi ${centang}`);
      }
      log(`  ${centang ? "☑" : "☐"} ${b.kode} (${b.mode}, ${b.petugas})`);
      await sleep(acak(250, 700));
    }
  }

  function kodeTercentangDiHalaman() {
    const trs = tabel().querySelectorAll("tbody tr");
    return barisDariTabel(bacaTabelWajib())
      .filter((b) => {
        const cb = trs[b.indeks] && trs[b.indeks].querySelector('[role="checkbox"], input[type="checkbox"]');
        return cb && tercentang(cb);
      })
      .map((b) => b.kode)
      .sort();
  }

  /** Lepas centang. Kalau tabel sudah berubah (mis. setelah aksi), cari ulang
   *  lewat KODE — indeks lama tidak lagi bisa dipercaya. Kode yang tidak tampil
   *  lagi tidak bisa dilepas; sisa centang tertangkap di subsls berikutnya
   *  lewat CENTANG_TIDAK_SESUAI / JUMLAH_TERCENTANG_BEDA. */
  async function lepasCentang(t, pilih) {
    try {
      await aturCentang(pilih, false);
    } catch (e) {
      if (!(e instanceof Berhenti) || e.kode !== "TABEL_BERUBAH") throw e;
      const kode = pilih.map((b) => b.kode);
      const { baris } = await cari(t);
      await aturCentang(baris.filter((b) => kode.includes(b.kode)), false);
    }
  }

  // --- menu & dialog ----------------------------------------------------------
  const teksTombol = (b) => bersih(b.innerText || b.getAttribute("aria-label") || b.getAttribute("title") || "");

  /** Tombol "Aksi Lainnya". Dulu dicocokkan PERSIS & tanpa menunggu: saat dipetakan
   *  (0 baris dicentang) ketemu, tapi dryrun 2026-09-14 gagal TIDAK_ADA_AKSES tepat
   *  setelah 1 baris dicentang — teks tombol kemungkinan ikut berubah (mis.
   *  "Aksi Lainnya (1)") atau toolbar sedang render ulang. Sekarang cukup DIAWALI
   *  "Aksi Lainnya". */
  function tombolAksiLainnya() {
    return [...document.querySelectorAll('button, [role="button"]')].filter(tampak)
      .find((b) => /^Aksi Lainnya\b/i.test(teksTombol(b))) || null;
  }

  async function bukaMenuGantiMode() {
    await tutupMenu();
    const tombol = await tunggu(tombolAksiLainnya, 10000, 300);
    if (!tombol) {
      const terlihat = [...new Set([...document.querySelectorAll('button, [role="button"]')].filter(tampak)
        .map(teksTombol).filter((t) => t && t.length <= 40))].slice(0, 30);
      throw new Berhenti("TIDAK_ADA_AKSES",
        `tombol 'Aksi Lainnya' tidak tampil dlm 10 dtk. Tombol yang terlihat: ${JSON.stringify(terlihat)}`);
    }
    // Pemicu menu Radix membuka dari pointerdown, bukan click — dicoba berurutan.
    const caraBuka = [
      () => tombol.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerType: "mouse", isPrimary: true })),
      () => tombol.click(),
      () => {
        tombol.focus();
        tombol.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true, cancelable: true }));
      },
    ];
    for (const buka of caraBuka) {
      buka();
      if (await tunggu(menuTerbuka, 2500)) break;
    }
    if (!menuTerbuka()) throw new Berhenti("ITEM_MENU_TIDAK_ADA", "menu 'Aksi Lainnya' tidak bisa dibuka");
    const item = await tunggu(() => [...document.querySelectorAll('[role="menuitem"]')].filter(tampak)
      .find((m) => POLA_ITEM_GANTI_MODE.test(bersih(m.innerText))), 5000);
    if (!item) {
      await tutupMenu();
      throw new Berhenti("ITEM_MENU_TIDAK_ADA", "item 'Ganti Mode (Ke PAPI)' tidak ada di menu 'Aksi Lainnya'");
    }
    return { item, n: angkaItemMenu(item.innerText) };
  }

  function catatDialog(dlg) {
    const teks = bersih(dlg.innerText);
    const tombol = [...dlg.querySelectorAll("button")].filter(tampak).map((t) => bersih(t.innerText));
    log("Dialog muncul:", teks.slice(0, 300), "| tombol:", tombol);
    try {
      localStorage.setItem("ubahModa.dialogTerakhir", JSON.stringify({ waktu: new Date().toISOString(), teks, tombol }));
    } catch (e) { /* abaikan */ }
    return { teks, tombol };
  }

  /** Mode manual: manusia yang mengklik item & konfirmasi. -> true kalau dialog konfirmasi
   *  terlihat (dianggap diklik), false kalau menu ditutup tanpa dialog (Esc / batal). */
  async function tungguKlikManusia(item, n, hasil) {
    item.style.outline = "3px solid #e65100";
    item.scrollIntoView({ block: "nearest" });
    log(`👉 KLIK SENDIRI "Ganti Mode (Ke PAPI) (${n})" lalu konfirmasi dialognya. `
      + "Kalau batal: tekan Esc SEBELUM dialog muncul (kode ini tercatat BELUM_BERUBAH & batch berhenti).");
    await tunggu(() => !menuTerbuka(), 15 * 60 * 1000, 400);
    const dlg = await tunggu(dialogTerbuka, 4000, 300);
    if (!dlg) return false;
    // Gagal tertutup: dialog yang ditutup lewat Batal pun dicatat diklik -> tidak diklik ulang otomatis.
    hasil.waktu_klik = new Date().toISOString();
    catatDialog(dlg);
    await tunggu(() => !dialogTerbuka(), 15 * 60 * 1000, 400);
    await sleep(2500);
    return true;
  }

  /** Mode otomatis: klik item & satu-satunya tombol konfirmasi. IRREVERSIBLE.
   *  hasil.waktu_klik diisi SEBELUM klik yang bisa mengubah data (item tanpa dialog /
   *  tombol konfirmasi), supaya berhenti di tengah pun kodenya tidak diklik ulang. */
  async function klikOtomatis(item, hasil) {
    hasil.waktu_klik = new Date().toISOString();
    item.click();
    const dlg = await tunggu(dialogTerbuka, 8000, 300);
    if (!dlg) {
      log("Tidak ada dialog konfirmasi — diverifikasi lewat tabel.");
      return "TANPA_DIALOG";
    }
    const { teks, tombol } = catatDialog(dlg);
    if (!/papi|mode/i.test(teks)) {
      hasil.waktu_klik = "";
      tekanEscape();
      throw new Berhenti("DIALOG_TIDAK_DIKENAL", `dialog tidak menyebut PAPI/mode: ${teks.slice(0, 200)}`);
    }
    const i = pilihTombolKonfirmasi(tombol);
    if (i === null) {
      hasil.waktu_klik = "";
      tekanEscape();
      throw new Berhenti("TOMBOL_KONFIRMASI_AMBIGU", `tombol dialog: ${JSON.stringify(tombol)}`);
    }
    hasil.waktu_klik = new Date().toISOString();
    [...dlg.querySelectorAll("button")].filter(tampak)[i].click();
    await tunggu(() => !dialogTerbuka(), 20000);
    await sleep(2000);
    return "DIKONFIRMASI";
  }

  // --- verifikasi tertunda ------------------------------------------------------
  // Mode baru TIDAK langsung terbaca di tabel (run user 2026-09-15). Kode yang sudah
  // dikonfirmasi masuk antrean (DIUBAH_MENUNGGU) & dicek ulang di sela target lain,
  // bukan ditunggu di tempat. Objek hasil dipakai bersama & ditimpa di tempat.

  /** {kode: mode} dari baris tabel; "(hilang)" kalau kode tidak tampil. */
  const modeKode = (baris, kode) => Object.fromEntries(kode.map((k) =>
    [k, (baris.find((b) => samaKode(b.kode, k)) || { mode: "(hilang)" }).mode]));

  const menit = (ms) => (Number.isFinite(ms) ? `${(ms / 60000).toFixed(1)} mnt` : "? mnt");

  function entriAntrean(t, hasil) {
    const wk = waktuKlikDari(hasil);
    return { t, hasil, kode: kodeSudahDiklik(hasil), waktuKlik: Number.isFinite(wk) ? wk : Date.now(), ke: 0,
      cekBerikut: Date.now() + jedaCekVerifikasi(0) };
  }

  /** Satu kali cek ulang. Hasil tersimpan hanya ditimpa kalau keputusannya final (PAPI, atau
   *  batas tunggu habis). -> null, atau kode status yang menghentikan batch. */
  async function cekUlang(e, o) {
    const kunci = kunciTarget(e.t);
    e.ke += 1;
    try {
      const { baris } = await cari(e.t);
      const mode = modeKode(baris, e.kode);
      const sejak = Date.now() - e.waktuKlik;
      const v = putuskanVerifikasi(mode, sejak, o.batasTungguMs);
      log(`Cek ulang ke-${e.ke} ${kunci} (${menit(sejak)} sejak diklik):`, mode, `-> ${v}`);
      if (v === "MENUNGGU") {
        e.cekBerikut = Date.now() + jedaCekVerifikasi(e.ke);
        return null;
      }
      if (v === "TERVERIFIKASI") {
        e.hasil.status = "DIUBAH_TERVERIFIKASI";
        e.hasil.pesan += ` | PAPI terbaca ${menit(sejak)} setelah diklik (cek ke-${e.ke})`;
      } else {
        e.hasil.status = "DIUBAH_BELUM_TERVERIFIKASI";
        e.hasil.pesan += ` | ${menit(sejak)} setelah diklik masih ${JSON.stringify(mode)} — cek di fasih-sm; `
          + "kalau memang belum berubah, ulangi dgn klikUlang";
      }
      simpanHasil(e.hasil);
      return STATUS_BERHENTI_SEGERA.has(e.hasil.status) ? e.hasil.status : null;
    } catch (err) {
      if (!(err instanceof Berhenti)) console.error(err);
      log(`⚠️ cek ulang ${kunci} gagal: ${err && err.message ? err.message : err} — tetap DIUBAH_MENUNGGU (tidak diklik ulang).`);
      return err instanceof Berhenti ? err.kode : "ERROR_TAK_TERDUGA";
    }
  }

  /** Cek entri yang jatuh tempo. sampai "penuh": tunggu selama antrean >= batas();
   *  "habis": tunggu sampai antrean kosong. -> null, atau kode status penghenti batch. */
  async function layaniAntrean(antrean, o, catat, sampai, batas) {
    for (;;) {
      for (const e of antrean.filter((x) => x.cekBerikut <= Date.now())) {
        const stop = await cekUlang(e, o);
        if (e.hasil.status !== "DIUBAH_MENUNGGU") {
          antrean.splice(antrean.indexOf(e), 1);
          catat("DIUBAH_MENUNGGU", e.hasil.status);
          log(`  -> ${kunciTarget(e.t)}: ${e.hasil.status}`);
        }
        if (stop) return stop;
      }
      const tungguLagi = sampai === "habis" ? antrean.length > 0 : antrean.length >= batas();
      if (!tungguLagi) return null;
      const jeda = Math.max(1000, Math.min(...antrean.map((x) => x.cekBerikut)) - Date.now());
      log(`⏳ ${antrean.length} kode menunggu Mode terbaca PAPI`
        + (sampai === "habis" ? "" : ` (batas ${batas()} — kode baru belum diklik)`)
        + ` — cek berikutnya ${Math.round(jeda / 1000)} dtk lagi.`);
      try {
        await tidur(jeda);
      } catch (err) {
        if (err instanceof Berhenti) return err.kode;
        throw err;
      }
    }
  }

  /** Tunggu SATU entri sampai final (dipakai cakupan "semua": putaran berikutnya baru boleh
   *  mencari CAPI setelah yang diklik terbaca PAPI). -> null kalau terverifikasi, atau kode penghenti. */
  async function tungguEntri(e, o) {
    while (e.hasil.status === "DIUBAH_MENUNGGU") {
      try {
        await tidur(Math.max(0, e.cekBerikut - Date.now()));
      } catch (err) {
        if (err instanceof Berhenti) return err.kode;
        throw err;
      }
      const stop = await cekUlang(e, o);
      if (stop) return stop;
    }
    return null;
  }

  // --- pemetaan filter (READ-ONLY) -------------------------------------------
  /** Rekam struktur kontrol filter supaya filter Mode bisa diotomatiskan nanti.
   *  TIDAK mengklik apa pun. Panggil saat semuanya tertutup, lalu lagi SETELAH
   *  tiap klik manual (ikon filter terbuka, pilihan Mode tampil, PAPI dipilih,
   *  filter diterapkan). Setiap langkah disimpan -> ubahModa.petakanFilter.hasil(). */
  function petakanFilter(catatan = "") {
    const t = tabel();
    const desk = (el) => {
      const svg = el.querySelector && el.querySelector("svg");
      return {
        tag: el.tagName.toLowerCase(),
        teks: bersih(el.innerText || el.value || "").slice(0, 80),
        aria: el.getAttribute("aria-label"), title: el.getAttribute("title"), role: el.getAttribute("role"),
        tipe: el.getAttribute("type"), placeholder: el.getAttribute("placeholder"),
        state: el.getAttribute("data-state") || el.getAttribute("aria-checked") || el.getAttribute("aria-selected")
          || el.getAttribute("aria-expanded") || (el.checked ? "checked" : null),
        ikon: svg ? (svg.getAttribute("class") || "").slice(0, 80) : null,
        kelas: (el.getAttribute("class") || "").slice(0, 120),
      };
    };
    const SEL_KONTROL = 'button, [role="button"], [role="option"], [role="menuitem"], [role="menuitemcheckbox"], '
      + '[role="menuitemradio"], [role="checkbox"], [role="radio"], [role="combobox"], [role="tab"], input, select, label';
    const kontrol = (root) => [...root.querySelectorAll(SEL_KONTROL)].filter(tampak).map(desk);
    const atas = t ? t.getBoundingClientRect().top : Infinity;
    const toolbar = [...document.querySelectorAll(SEL_KONTROL)].filter(tampak)
      .filter((el) => !(t && t.contains(el)) && !el.closest('[role="dialog"],[role="menu"],[role="listbox"],[data-radix-popper-content-wrapper]'))
      .filter((el) => { const top = el.getBoundingClientRect().top; return top < atas && top > atas - 350; })
      .map(desk);
    const lapisan = [...document.querySelectorAll('[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],'
      + '[data-radix-popper-content-wrapper],[cmdk-root],[data-vaul-drawer]')].filter(tampak)
      .map((el) => ({ jenis: el.getAttribute("role") || el.tagName.toLowerCase(), teks: bersih(el.innerText).slice(0, 600),
        kontrol: kontrol(el).slice(0, 60) }));
    const baris = barisTerbaca();
    const hitungMode = {};
    baris.forEach((b) => { hitungMode[b.mode] = (hitungMode[b.mode] || 0) + 1; });
    const d = bacaTabel();
    const langkah = {
      waktu: new Date().toISOString(), catatan, url: location.href, halaman: d && d.halaman,
      kotak_cari: kotakCari() ? kotakCari().value : null, baris_tampil: baris.length, mode_tampil: hitungMode,
      kepala_tabel: t ? kontrol(t.querySelector("thead") || t).slice(0, 40) : [],
      toolbar, lapisan,
    };
    let semua = [];
    try {
      semua = JSON.parse(localStorage.getItem("ubahModa.petakanFilter") || "[]");
      semua.push(langkah);
      localStorage.setItem("ubahModa.petakanFilter", JSON.stringify(semua));
    } catch (e) { /* abaikan */ }
    log(`petakanFilter langkah ke-${semua.length || 1}${catatan ? ` (${catatan})` : ""}: `
      + `${toolbar.length} kontrol toolbar, ${lapisan.length} lapisan terbuka, mode tampil ${JSON.stringify(hitungMode)}`);
    return langkah;
  }
  petakanFilter.hasil = () => {
    let semua = [];
    try {
      semua = JSON.parse(localStorage.getItem("ubahModa.petakanFilter") || "[]");
    } catch (e) { /* abaikan */ }
    const teks = JSON.stringify(semua, null, 2);
    const blob = new Blob([teks], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `petakan_filter_fasih_sm_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${semua.length} langkah)`);
    return semua;
  };
  petakanFilter.hapus = () => {
    localStorage.removeItem("ubahModa.petakanFilter");
    log("Rekaman petakanFilter dihapus.");
  };

  // --- penyimpanan hasil ------------------------------------------------------
  function muatHasil() {
    try {
      return JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}");
    } catch (e) {
      return {};
    }
  }
  function simpanHasil(entri) {
    const semua = muatHasil();
    semua[entri.kunci || entri.idsubsls] = entri;
    try {
      localStorage.setItem(KUNCI_HASIL, JSON.stringify(semua));
    } catch (e) {
      log("⚠️ localStorage penuh/terkunci — segera ubahModa.unduh()", e);
    }
  }

  const ringkasBaris = (baris) => baris.slice(0, 25).map(({ kode, mode, status, petugas, keterangan }) =>
    ({ kode, mode, status, petugas, keterangan }));

  async function prosesTarget(t, o) {
    const hasil = {
      waktu: new Date().toISOString(), jalan: o.mode, idsubsls: t.idsubsls, akun_ppl: (t.ppl || []).join(","),
      baris_sheet: (t.baris || []).join(","), status: "", jumlah_assignment: "", capi: "", papi: "",
      dipilih: "", petugas_dipilih: "", pesan: "", kode_target: t.kode || "", kunci: kunciTarget(t),
    };
    let dicentang = [];
    try {
      const { baris, halaman } = await cari(t);
      const rencana = rencanakan(t, baris, o.cakupan, halaman[1] > 1);
      // Target kode: baris kode persis itu saja; target sheet: semua baris subsls-nya.
      const milik = baris.filter(cocokTarget(t));
      const pilih = rencana.pilih;
      Object.assign(hasil, {
        jumlah_assignment: milik.length,
        capi: milik.filter((b) => b.mode.toUpperCase() === "CAPI").length,
        papi: milik.filter((b) => b.mode.toUpperCase() === "PAPI").length,
        dipilih: pilih.map((b) => b.kode).join(" | "),
        petugas_dipilih: pilih.map((b) => b.petugas).join(" | "),
        pesan: rencana.pesan,
      });
      log(`${milik.length} ${t.kode ? "baris kode persis" : "assignment subsls ini"} tampil `
        + `(CAPI ${hasil.capi}, PAPI ${hasil.papi}; ${baris.length - milik.length} baris lain diabaikan) `
        + `-> ${rencana.status}. 25 baris pertama:`);
      console.table(ringkasBaris(milik));
      if (pilih.length) console.table(ringkasBaris(pilih));

      if (o.mode === "petakan") {
        const { n } = await bukaMenuGantiMode();
        await tutupMenu();
        hasil.status = `PETAKAN_${rencana.status}`;
        hasil.pesan += ` | angka menu saat 0 dicentang = ${n}`;
        return hasil;
      }
      if (rencana.status !== "PERLU_DIUBAH") {
        hasil.status = rencana.status;
        return hasil;
      }

      dicentang = pilih;
      await aturCentang(pilih, true);
      const harap = pilih.map((b) => b.kode).sort();
      const nyata = kodeTercentangDiHalaman();
      if (JSON.stringify(nyata) !== JSON.stringify(harap)) {
        throw new Berhenti("CENTANG_TIDAK_SESUAI", `tercentang di halaman: ${nyata}; seharusnya: ${harap}`);
      }
      const { item, n } = await bukaMenuGantiMode();
      if (n !== pilih.length) {
        throw new Berhenti("JUMLAH_TERCENTANG_BEDA", `menu menunjukkan (${n}), yang dicentang ${pilih.length}`);
      }
      if (o.mode === "dryrun") {
        await tutupMenu();
        await lepasCentang(t, pilih);
        dicentang = [];
        hasil.status = "DRY_RUN_AKAN_DIUBAH";
        return hasil;
      }

      let cara = "MANUAL";
      if (o.mode === "manual") await tungguKlikManusia(item, n);
      else cara = await klikOtomatis(item);
      const verif = await verifikasiPapi(t, harap);
      hasil.status = verif.ok ? "DIUBAH_TERVERIFIKASI" : (o.mode === "manual" ? "BELUM_BERUBAH" : "DIUBAH_BELUM_TERVERIFIKASI");
      hasil.pesan += ` | ${cara}`;
      // Pilihan tabel bisa bertahan lintas pencarian — centang yang tertinggal
      // bisa ikut terkirim di aksi massal subsls berikutnya.
      await tutupMenu();
      await aturCentang(verif.baris.filter((b) => harap.includes(b.kode)), false);
      dicentang = [];
      return hasil;
    } catch (e) {
      hasil.status = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      hasil.pesan = `${hasil.pesan ? hasil.pesan + " | " : ""}${e && e.message ? e.message : e}`;
      if (!(e instanceof Berhenti)) console.error(e);
    }
    if (dicentang.length) {
      const lama = hentikan;
      try {
        hentikan = false; // pembersihan tetap jalan walau pengguna menekan berhenti()
        await tutupMenu();
        await lepasCentang(t, dicentang);
      } catch (e) {
        hasil.pesan += ` | status asli ${hasil.status}; ⚠️ gagal melepas centang: ${e.message}`;
        hasil.status = "CENTANG_GAGAL";
      } finally {
        hentikan = lama;
      }
    }
    return hasil;
  }

  async function jalankan(opsi = {}) {
    const o = {
      mode: "dryrun", cakupan: "satu", limit: null, idsubsls: null,
      // Jeda acak jedaMin–jedaMaks hanya setelah benar-benar mengklik Ganti Mode;
      // kode yang cuma dibaca (sudah PAPI / tidak ada) memakai jeda pendek.
      lewatiSelesai: true, jedaMin: 1500, jedaMaks: 3000, ...opsi,
    };
    if (!["petakan", "dryrun", "manual", "otomatis"].includes(o.mode)) {
      log(`mode '${o.mode}' tidak dikenal (petakan | dryrun | manual | otomatis)`);
      return;
    }
    if (berjalan) {
      log("Masih berjalan — tunggu selesai atau ubahModa.berhenti().");
      return;
    }
    if (!TARGET.length) {
      log("TARGET kosong — tempel ubah_moda_console.siap.js (hasil `python ubah_moda.py --console`), "
        + "atau muat list kode: ubahModa.muatDaftarKode(`...`).");
      return;
    }
    const perPage = Number(new URLSearchParams(location.search).get("perPage") || 0);
    if (perPage < 50) {
      log(`⛔ perPage=${perPage || "?"}. Skrip hanya membaca halaman yang tampil (paginasi tidak dipindah), `
        + "jadi makin sedikit baris per halaman makin kecil peluang PAPI yang sudah ada terlihat. "
        + `Buka URL ini, lalu TEMPEL ULANG skripnya:\n${location.origin}${location.pathname}?page=1&perPage=100`);
      return;
    }
    if (!tabel() || !kotakCari()) {
      log("Buka dulu halaman list assignment (tabel 'Kode Identitas' & kotak 'Cari...' harus tampil).");
      return;
    }

    const sebelumnya = muatHasil();
    const live = o.mode === "manual" || o.mode === "otomatis";
    // Otomatis TIDAK lagi mensyaratkan run manual dulu (permintaan user 2026-09-15:
    // "langsung otomatis saja"). Penjaganya: ketik YA per batch, dialog yang tidak
    // menyebut PAPI/mode atau tombol ambigu -> berhenti, angka menu harus = jumlah
    // dicentang, dan setiap kode diverifikasi PAPI (gagal -> batch berhenti).

    let daftar = TARGET;
    if (o.idsubsls) {
      const ingin = new Set(o.idsubsls);
      daftar = daftar.filter((t) => ingin.has(t.idsubsls));
    }
    if (o.lewatiSelesai && o.mode !== "petakan") {
      const tuntas = live ? STATUS_TUNTAS_LIVE : STATUS_TUNTAS_DRY;
      daftar = daftar.filter((t) => {
        const h = sebelumnya[kunciTarget(t)];
        if (!h || !tuntas.has(h.status)) return true;
        return live && !["manual", "otomatis"].includes(h.jalan); // hasil dry-run tidak menuntaskan run live
      });
    }
    if (o.mode === "petakan") daftar = daftar.slice(0, 1);
    else if (o.limit) daftar = daftar.slice(0, o.limit);
    const satuan = daftar.some((t) => t.kode) ? "kode identitas" : "subsls";
    if (!daftar.length) {
      log("Tidak ada target yang perlu diproses.");
      return;
    }

    if (live) {
      const pesan = `MENGUBAH MODE assignment SUNGGUHAN utk ${daftar.length} ${satuan} `
        + `(mode ${o.mode}${satuan === "subsls" ? `, cakupan ${o.cakupan}` : ""}).`;
      if (o.mode === "otomatis") {
        if (prompt(`${pesan}\nKetik YA untuk lanjut:`) !== "YA") return log("Dibatalkan.");
      } else if (!confirm(`${pesan}\nKlik "Ganti Mode" & konfirmasi tetap KAMU yang lakukan per ${satuan}. Lanjut?`)) {
        return log("Dibatalkan.");
      }
    }

    berjalan = true;
    hentikan = false;
    const hitung = {};
    let errorBeruntun = 0;
    try {
      for (let i = 0; i < daftar.length; i++) {
        const t = daftar[i];
        log(`=== [${i + 1}/${daftar.length}] ${t.kode ? `kode ${t.kode}` : `${t.idsubsls} — PPL ${(t.ppl || []).join(", ")}`} (${o.mode}) ===`);
        let hasil = await prosesTarget(t, o);
        // Cakupan "semua": ulangi subsls ini selama masih ada CAPI di halaman tampil.
        // Target kode tidak diulang — satu kode, satu aksi.
        for (let ulang = 1; live && !t.kode && o.cakupan === "semua" && hasil.status === "DIUBAH_TERVERIFIKASI" && ulang <= 50; ulang++) {
          simpanHasil(hasil);
          log(`  (cakupan semua) putaran ${ulang + 1} utk ${t.idsubsls}`);
          await sleep(acak(o.jedaMin, o.jedaMaks));
          hasil = await prosesTarget(t, o);
        }
        simpanHasil(hasil);
        hitung[hasil.status] = (hitung[hasil.status] || 0) + 1;
        log(`  -> ${hasil.status}`, hasil.pesan);
        if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
          log(`⛔ ${hasil.status} — batch DIHENTIKAN. Periksa tabel/dialog di layar sebelum menjalankan ulang.`);
          break;
        }
        const gagal = hasil.status.startsWith("ERROR_") || STATUS_LANJUT_TAPI_HITUNG.has(hasil.status);
        errorBeruntun = gagal ? errorBeruntun + 1 : 0;
        if (errorBeruntun >= 3) {
          log(`⛔ 3 kegagalan berturut-turut (terakhir ${hasil.status}) — batch DIHENTIKAN (VPN/sesi habis? akun tanpa hak?).`);
          break;
        }
        if (gagal) log(`⚠️ ${hasil.status} — lanjut ke target berikutnya (${errorBeruntun}/3 beruntun).`);
        if (i < daftar.length - 1) {
          const adaKlik = STATUS_SETELAH_KLIK.has(hasil.status);
          await sleep(adaKlik ? acak(o.jedaMin, o.jedaMaks) : acak(300, 800));
        }
      }
    } finally {
      berjalan = false;
      console.table(hitung);
      log("Selesai. ubahModa.unduh() untuk menyimpan hasil sbg CSV.");
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
    const kolom = ["waktu", "jalan", "idsubsls", "akun_ppl", "baris_sheet", "status", "jumlah_assignment",
      "capi", "papi", "dipilih", "petugas_dipilih", "pesan", "kode_target"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = Object.values(muatHasil()).map((h) => kolom.map((k) => kutip(h[k])).join(","));
    const blob = new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit_ubah_moda_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} subsls)`);
  }

  /** Ganti isi TARGET dgn list kode identitas yang ditempel (satu kode per baris;
   *  salinan kolom dari Excel juga bisa). Tanpa Python. */
  function muatDaftarKode(teks) {
    if (berjalan) return log("Masih berjalan — tunggu selesai atau ubahModa.berhenti().");
    const { targets, tidakDikenali, ganda } = targetDariDaftarKode(String(teks || "").split(/\r?\n/));
    TARGET.length = 0;
    TARGET.push(...targets);
    log(`Daftar kode dimuat: ${targets.length} kode identitas (tiap kode dicari sendiri).`
      + (ganda.length ? ` ${ganda.length} kode ganda dilewati.` : ""));
    if (tidakDikenali.length) {
      log(`⚠️ ${tidakDikenali.length} baris berisi 16 digit tapi BUKAN kode identitas (tidak dimuat):`);
      console.table(tidakDikenali.map(([baris, isi]) => ({ baris, isi })));
    }
    return { kode: targets.length, tidakDikenali, ganda };
  }

  global.ubahModa = {
    jalankan, ringkasan, unduh, petakanFilter, muatDaftarKode, target: TARGET,
    dialogTerakhir() {
      try {
        const d = JSON.parse(localStorage.getItem("ubahModa.dialogTerakhir") || "null");
        log(d ? `Dialog terakhir (${d.waktu}): ${d.teks} | tombol: ${JSON.stringify(d.tombol)}` : "Belum ada dialog terekam.");
        return d;
      } catch (e) {
        return null;
      }
    },
    berhenti() {
      hentikan = true;
      log("Akan berhenti di langkah berikutnya.");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil ubahModa yang tersimpan di browser ini? (unduh dulu kalau perlu)")) {
        localStorage.removeItem(KUNCI_HASIL);
      }
    },
  };
  log(`Siap: ${TARGET.length} ${TARGET.some((t) => t.kode) ? "kode identitas" : "subsls"}. `
    + 'Mulai dgn: await ubahModa.jalankan({mode: "petakan"})');
})(typeof window !== "undefined" ? window : globalThis);
