/**
 * ubah_moda_console.js — Ganti mode assignment di fasih-sm (CAPI -> PAPI, atau
 * PAPI -> CAPI utk subsls/kode tertentu) dari DevTools Console Chrome BIASA.
 * Padanan ubah_moda.py TANPA Playwright: fasih-sm dilindungi anti-bot (F5/TSPD),
 * jadi di sini yang bekerja hanya tab Chrome milikmu sendiri yang login normal,
 * dgn jeda acak antar langkah.
 *
 * ARAH (mode tujuan) melekat pada target, bukan opsi jalankan:
 *   ke PAPI (bawaan) : list kode / sheet — seperti di bawah.
 *   ke CAPI          : python ganti_moda/ubah_moda.py --subsls daftar.txt --ke CAPI --console
 *                      atau ubahModa.muatDaftarSubsls(`<idsubsls per baris>`, {ke: "CAPI"})
 *                      -> SEMUA assignment PAPI tiap subsls (halaman tampil) diubah ke CAPI,
 *                      diulang per putaran sampai TIDAK_ADA_PAPI. List kode ke CAPI:
 *                      ubahModa.muatDaftarKode(`...`, {ke: "CAPI"}) / --daftar ... --ke CAPI.
 *                      Caranya PER BARIS spt manual user: ⋮ -> "Ganti Mode" -> dialog "Mode
 *                      Pendataan" -> CAPI -> "Ubah Mode Pendataan" (caraKlik "baris"; ke PAPI
 *                      tetap "massal" lewat "Aksi Lainnya"). Tab fasih-sm harus di DEPAN selama jalan.
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
 *    Opsi lain: cakupan: "satu"|"semua", idsubsls: [...], lewatiSelesai (default true),
 *    jedaMin/jedaMaks (ms), batasTungguMs (15 mnt), maksMenunggu (10), maksPerKlik (50),
 *    jarakCariMs (2000), klikUlang (false | true | ["kode", ...]), ke (pemeriksa arah),
 *    caraKlik ("baris" utk CAPI | "massal" utk PAPI). ubahModa.lewati() = lewati baris yg disorot (manual).
 *
 * VERIFIKASI TERTUNDA (run user 2026-09-15): mode baru TIDAK langsung terbaca. Setelah
 * konfirmasi -> DIUBAH_MENUNGGU, kode itu dicek ulang di sela target lain (30/45/60/90/120
 * dtk, lalu tiap 3 mnt) sampai terbaca mode tujuan (DIUBAH_TERVERIFIKASI) atau 15 mnt habis
 * (DIUBAH_BELUM_TERVERIFIKASI, berhenti). Kode yang sudah diklik TIDAK PERNAH diklik ulang
 * di run berikut (hanya diperiksa) kecuali klikUlang. Selama browser ini belum punya satu
 * perubahan terbukti ke arah itu: 1 baris per klik & kode berikutnya menunggu.
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
 *   klik yang IRREVERSIBLE dilakukan manusia. Skrip lalu memverifikasi mode tujuan.
 * - Mode "otomatis" (2026-09-15, tanpa syarat manual): ketik YA per batch; dialog
 *   yang tidak cocok dgn arahnya (mis. menyebut "ke PAPI" saat target ke CAPI) atau
 *   tombol konfirmasi yang ambigu -> berhenti.
 * - Batch BERHENTI SEKETIKA kalau: subsls tidak tampil di halaman hasil
 *   pencarian, kolom Mode/Petugas tidak tampil, baris yang tercentang di
 *   halaman != yang direncanakan, angka "(N)" di menu != jumlah dicentang,
 *   menu tidak mau tertutup, dialog/tombol tidak jelas, atau mode tidak
 *   terbaca berubah dlm batasTungguMs.
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
  const MODE = ["CAPI", "PAPI"];
  const POLA_TOMBOL_KONFIRMASI = /^\s*(ya|konfirmasi|ganti|ubah|lanjut|lanjutkan|simpan|ok|oke|proses)\b/i;
  const POLA_TOMBOL_BATAL = /batal|tutup|cancel|kembali|^\s*tidak\b/i;

  /** Arah target = mode TUJUAN. Target tanpa `ke` (siap.js lama, sheet) = "PAPI". */
  const keTarget = (t) => (String((t && t.ke) || "PAPI").toUpperCase() === "CAPI" ? "CAPI" : "PAPI");
  const lawanMode = (m) => (m === "CAPI" ? "PAPI" : "CAPI");
  /** Item massal di menu "Aksi Lainnya": "Ganti Mode (Ke PAPI) (N)" / "Ganti Mode (Ke CAPI) (N)". */
  const polaItemGantiMode = (ke) => new RegExp(`Ganti Mode\\s*\\(\\s*Ke ${ke}\\s*\\)`, "i");

  const STATUS_TUNTAS_LIVE = new Set(["DIUBAH_TERVERIFIKASI", "SUDAH_ADA_PAPI", "TIDAK_ADA_CAPI", "KODE_SUDAH_PAPI",
    "KODE_SUDAH_CAPI", "TIDAK_ADA_PAPI"]);
  const STATUS_TUNTAS_DRY = new Set([...STATUS_TUNTAS_LIVE, "DRY_RUN_AKAN_DIUBAH"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SUBSLS_TIDAK_TAMPIL", "PERLU_HALAMAN_LAIN", "KOLOM_TIDAK_ADA", "PER_PAGE_KECIL",
    "JUMLAH_TERCENTANG_BEDA", "CENTANG_TIDAK_SESUAI", "MENU_TIDAK_TERTUTUP",
    "TABEL_BERUBAH", "DIALOG_TIDAK_DIKENAL", "TOMBOL_KONFIRMASI_AMBIGU", "DIUBAH_BELUM_TERVERIFIKASI",
    "BELUM_BERUBAH", "CENTANG_GAGAL", "ITEM_MENU_TIDAK_ADA", "DIHENTIKAN_PENGGUNA",
    "PENCARIAN_TIDAK_MENYARING", "KODE_GANDA", "RATE_LIMIT",
    "MENU_BARIS_TIDAK_ADA", "OPSI_MODE_TIDAK_JELAS", "DIALOG_TIDAK_TERTUTUP",
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

  /** Daftar idsubsls (satu teks = satu baris file) -> {targets, tidakDikenali, ganda, kodeIdentitas}.
   *  Target subsls ber-arah `ke`; utk ke CAPI SEMUA assignment PAPI subsls itu yang tampil diubah.
   *  Hanya angka 16 digit UTUH yang dimuat. Baris berpola kode identitas ("<16 digit> - …") TIDAK
   *  dimuat (kodeIdentitas): list kode yang tertempel ke sini akan melebar jadi satu subsls penuh.
   *  Angka panjang lain (15/17 digit, notasi ilmiah Excel "5.10806E+15") dilaporkan, tidak ditebak. */
  function targetDariDaftarSubsls(barisTeks, ke) {
    const targets = [];
    const sudah = new Set();
    const tidakDikenali = [];
    const ganda = [];
    const kodeIdentitas = [];
    barisTeks.forEach((teks, i) => {
      const no = i + 1;
      const s = String(teks == null ? "" : teks);
      if (/\d{16}\s*-\s*\S/.test(s)) {
        kodeIdentitas.push([no, bersih(s).slice(0, 80)]);
        return;
      }
      for (const tok of s.split(/[\s,;]+/).filter(Boolean)) {
        if (/^\d{16}$/.test(tok)) {
          if (sudah.has(tok)) ganda.push([no, tok]);
          else {
            sudah.add(tok);
            targets.push({ idsubsls: tok, ke, baris: [no], ppl: [] });
          }
        } else if (tok.replace(/\D/g, "").length >= 10 || /^\d(\.\d+)?e\+?\d+$/i.test(tok)) {
          tidakDikenali.push([no, tok.slice(0, 80)]);
        }
      }
    });
    return { targets, tidakDikenali, ganda, kodeIdentitas };
  }

  /** Kunci hasil tersimpan: kode identitas (target list) atau idsubsls (target sheet/subsls).
   *  Arah CAPI diberi awalan "CAPI:" supaya hasil arah PAPI (mis. SUDAH_ADA_PAPI) tidak
   *  membuat subsls/kode yang sama dilewati saat dikembalikan ke CAPI. Kunci PAPI tetap. */
  const kunciTarget = (t) => (keTarget(t) === "CAPI" ? "CAPI:" : "") + (t.kode || t.idsubsls);

  /** Target subsls yang diulang per putaran sampai habis (cakupan "semua", atau arah CAPI):
   *  putaran berikutnya baru boleh dicari setelah yang diklik terbukti berubah. */
  const diulangPerSubsls = (t, cakupan) => !t.kode && (keTarget(t) === "CAPI" || cakupan === "semua");

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
    if (keTarget(target) === "CAPI") return rencanakanSubslsKeCapi(target, baris, adaHalamanLain);
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

  /** Target subsls arah CAPI (permintaan user 2026-09-22: "subsls tertentu saja, dari PAPI ke
   *  CAPI") -> SEMUA assignment PAPI subsls itu di halaman tampil (cakupan diabaikan). Baris
   *  subsls lain diabaikan. Paginasi tetap tidak dipindah: kalau hasil >1 halaman & tidak ada
   *  PAPI yang tampil, sisa PAPI (kalau ada) tidak terlihat -> CEK_HALAMAN_LAIN (lanjut, tidak
   *  tuntas; ubah lewat list kode identitas). */
  function rencanakanSubslsKeCapi(target, baris, adaHalamanLain = false) {
    const milik = baris.filter((b) => b.idsubsls === target.idsubsls);
    const nAsing = baris.length - milik.length;
    const catatan = (nAsing ? ` | ${nAsing} baris subsls lain diabaikan` : "")
      + (adaHalamanLain ? " | >1 halaman, hanya halaman tampil yang dibaca" : "");
    if (!milik.length) {
      if (nAsing || adaHalamanLain) {
        return { status: "SUBSLS_TIDAK_TAMPIL", pilih: [],
          pesan: `halaman hasil pencarian tidak memuat satu pun baris ${target.idsubsls} — pencarian tidak menyaring?${catatan}` };
      }
      return { status: "TIDAK_ADA_ASSIGNMENT", pilih: [], pesan: `tidak ada assignment subsls ini di hasil pencarian${catatan}` };
    }
    const aneh = [...new Set(milik.map((b) => b.mode).filter((m) => !MODE.includes(m.toUpperCase())))];
    if (aneh.length) return { status: "MODE_TIDAK_DIKENAL", pilih: [], pesan: `nilai kolom Mode: ${aneh}${catatan}` };
    const papi = milik.filter((b) => b.mode.toUpperCase() === "PAPI");
    const capi = milik.length - papi.length;
    if (papi.length) {
      return { status: "PERLU_DIUBAH", pilih: papi,
        pesan: `${papi.length} assignment PAPI yang tampil (${capi} sudah CAPI)${catatan}` };
    }
    if (adaHalamanLain) {
      return { status: "CEK_HALAMAN_LAIN", pilih: [],
        pesan: `tidak ada PAPI di halaman tampil (${capi} CAPI), tapi hasil pencarian >1 halaman — PAPI di halaman `
          + `lain (kalau ada) tidak terlihat; ubah lewat list kode identitas${catatan}` };
    }
    return { status: "TIDAK_ADA_PAPI", pilih: [], pesan: `${capi} assignment, semua sudah CAPI${catatan}` };
  }

  /** Target kode identitas (hasil pencarian KODE itu) -> HANYA baris kode itu yang
   *  diubah ke mode tujuannya (cakupan diabaikan). Baris lain yang ikut tampil (mis.
   *  "…- UMK - 41" saat mencari "…- UMK - 4") diabaikan. */
  function rencanakanKode(target, baris, adaHalamanLain = false) {
    const ke = keTarget(target);
    const asal = lawanMode(ke);
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
    if (mode === ke) return { status: `KODE_SUDAH_${ke}`, pilih: [], pesan: `sudah ${ke} (petugas ${b.petugas})${catatan}` };
    if (mode !== asal) return { status: "MODE_TIDAK_DIKENAL", pilih: [], pesan: `nilai kolom Mode: ${b.mode}${catatan}` };
    return { status: "PERLU_DIUBAH", pilih: [b], pesan: `${asal} (petugas ${b.petugas})${catatan}` };
  }

  /** Menu ⋮ per baris (cara manual user 2026-09-22: ⋮ -> "Ganti Mode" -> pilih CAPI): indeks SATU-SATUNYA
   *  item "Ganti Mode…" yang tidak menyebut mode lawan ("Ganti Mode", "Ganti Mode (Ke CAPI)"), atau null. */
  function pilihItemGantiModeBaris(teksItem, ke) {
    const lawan = new RegExp(`\\bKe\\s+${lawanMode(ke)}\\b`, "i");
    const kandidat = [];
    teksItem.forEach((t, i) => {
      const s = bersih(t);
      if (/^Ganti Mode\b/i.test(s) && !lawan.test(s)) kandidat.push(i);
    });
    return kandidat.length === 1 ? kandidat[0] : null;
  }

  /** Pilihan mode di submenu/dialog: indeks SATU-SATUNYA teks yang diawali mode tujuan ("CAPI",
   *  "Ke CAPI", "CAPI (Computer Assisted…)") & tidak menyebut mode lawan, atau null. */
  function pilihOpsiMode(teks, ke) {
    const awal = new RegExp(`^(?:ke\\s+)?${ke}\\b`, "i");
    const lawan = new RegExp(`\\b${lawanMode(ke)}\\b`, "i");
    const kandidat = [];
    teks.forEach((t, i) => {
      const s = bersih(t);
      if (awal.test(s) && !lawan.test(s)) kandidat.push(i);
    });
    return kandidat.length === 1 ? kandidat[0] : null;
  }

  /** Teks dialog konfirmasi cocok dgn arah `ke`? Frasa "ke/to/menjadi <MODE>" menentukan
   *  (semuanya harus = ke); tanpa frasa itu dialog harus menyebut `ke`, atau menyebut "mode"
   *  tanpa menyebut mode lawan. Dialog yang menyebut mode lawan saja = salah arah -> tidak diklik. */
  function dialogSesuai(teks, ke) {
    const t = String(teks || "");
    const tujuan = [...t.matchAll(/\b(?:ke|to|menjadi)\s+(CAPI|PAPI)\b/gi)].map((m) => m[1].toUpperCase());
    if (tujuan.length) return tujuan.every((m) => m === ke);
    if (new RegExp(`\\b${ke}\\b`, "i").test(t)) return true;
    return /mode/i.test(t) && !new RegExp(`\\b${lawanMode(ke)}\\b`, "i").test(t);
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

  /** {kode: mode terbaca} -> "TERVERIFIKASI" (semua = mode tujuan `ke`) | "MENUNGGU" |
   *  "BELUM_TERVERIFIKASI" (batas tunggu habis). Kode yang tidak tampil ("(hilang)") dianggap belum berubah. */
  function putuskanVerifikasi(mode, sejakKlikMs, batasMs = BATAS_TUNGGU_VERIFIKASI_MS, ke = "PAPI") {
    const nilai = Object.values(mode || {});
    if (nilai.length && nilai.every((m) => String(m).toUpperCase() === ke)) return "TERVERIFIKASI";
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

  /** Semua kode yang sudah diklik ke arah `ke` tapi belum terbukti berubah, dari SELURUH hasil
   *  tersimpan (lintas kunci: kode yang diklik lewat target subsls juga terlarang utk target
   *  list kode, dan sebaliknya). */
  function kodeDiklikSemua(semua, ke) {
    const out = [];
    for (const h of Object.values(semua || {})) {
      if (keTarget(h) === ke) out.push(...kodeSudahDiklik(h));
    }
    return out;
  }

  /** Browser ini sudah punya bukti ganti mode ke `ke` berhasil (run live, terverifikasi)? */
  const adaBukti = (semua, ke) => Object.values(semua || {}).some((h) => h && h.status === "DIUBAH_TERVERIFIKASI"
    && ["manual", "otomatis"].includes(h.jalan) && keTarget(h) === ke);

  /** Hasil lama `lama` target `t` masih tuntas? Tidak kalau statusnya bukan tuntas, atau kalau
   *  SESUDAHNYA ada klik ganti mode arah LAWAN di subsls yang sama (mis. subsls yang dulu
   *  SUDAH_ADA_PAPI lalu seluruh PAPI-nya dikembalikan ke CAPI -> harus diperiksa lagi).
   *  `klik_terakhir` = klik terakhir target itu (terbawa ke putaran akhir yang tidak mengklik). */
  function masihTuntas(lama, t, semua, tuntas) {
    if (!lama || !tuntas.has(lama.status)) return false;
    const sejak = Date.parse(lama.waktu || "");
    const lawan = lawanMode(keTarget(t));
    return !Object.values(semua || {}).some((h) => {
      if (!h || keTarget(h) !== lawan || h.idsubsls !== t.idsubsls) return false;
      const w = Date.parse(h.klik_terakhir || h.waktu_klik || "");
      return Number.isFinite(w) && (!Number.isFinite(sejak) || w > sejak);
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, Berhenti, barisDariTabel, rencanakan, angkaItemMenu, pilihTombolKonfirmasi,
      idsubslsDariKode, bacaHalaman, normalisasiKode, targetDariDaftarKode, targetDariDaftarSubsls, kunciTarget,
      istilahCari, cocokTarget, keTarget, polaItemGantiMode, dialogSesuai, diulangPerSubsls,
      pilihItemGantiModeBaris, pilihOpsiMode,
      jedaCekVerifikasi, putuskanVerifikasi, jedaRateLimit, kodeSudahDiklik, waktuKlikDari,
      kodeDiklikSemua, adaBukti, masihTuntas,
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

  // Menu/dialog Radix yang sudah ditutup bisa TERTINGGAL di DOM dgn data-state="closed" selama animasi
  // keluarnya belum selesai — di tab latar belakang animasi tidak jalan, jadi bisa lama sekali (terlihat
  // 2026-09-22). Yang begitu dianggap tertutup; ukuran elemennya tetap > 0 sehingga tampak() saja tertipu.
  const terbuka = (el) => tampak(el) && el.getAttribute("data-state") !== "closed";
  const menuTerbuka = () => [...document.querySelectorAll('[role="menu"]')].some(terbuka);
  const dialogTerbuka = () => [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(terbuka).pop() || null;

  function tekanEscape() {
    const o = { key: "Escape", code: "Escape", keyCode: 27, bubbles: true, cancelable: true };
    (document.activeElement || document.body).dispatchEvent(new KeyboardEvent("keydown", o));
  }

  /** Menu yang masih terbuka MENELAN klik berikutnya (terjadi saat pemetaan:
   *  klik ikon filter malah mengenai "Broadcast Status"). Wajib sebelum klik apa pun. */
  async function tutupMenu() {
    if (!menuTerbuka()) return;
    // Esc 2x: submenu (menu ⋮ baris -> "Ganti Mode") bisa hanya menutup satu tingkat per Esc.
    for (let ke = 0; ke < 2; ke++) {
      tekanEscape();
      if (await tunggu(() => !menuTerbuka(), 1500)) return;
    }
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

  const pointer = (jenis) => new PointerEvent(jenis,
    { bubbles: true, cancelable: true, button: 0, pointerType: "mouse", isPrimary: true });

  /** Buka pemicu menu Radix. Radix membuka dari pointerdown, bukan click — dicoba berurutan
   *  (pointerdown, click, Enter) sampai terbuka() bernilai. -> nilai terbuka() atau null. */
  async function bukaPemicu(el, terbuka) {
    const caraBuka = [
      () => el.dispatchEvent(pointer("pointerdown")),
      () => el.click(),
      () => {
        el.focus();
        el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true, cancelable: true }));
      },
    ];
    for (const buka of caraBuka) {
      buka();
      const v = await tunggu(terbuka, 2500);
      if (v) return v;
    }
    return null;
  }

  /** Buka "Aksi Lainnya" -> {item "Ganti Mode (Ke <ke>)", n, daftar teks item yang terlihat}.
   *  wajib=false (petakan): item yang tidak ada TIDAK menghentikan, menu ditutup & item=null. */
  async function bukaMenuGantiMode(ke, wajib = true) {
    await tutupMenu();
    const tombol = await tunggu(tombolAksiLainnya, 10000, 300);
    if (!tombol) {
      const terlihat = [...new Set([...document.querySelectorAll('button, [role="button"]')].filter(tampak)
        .map(teksTombol).filter((t) => t && t.length <= 40))].slice(0, 30);
      throw new Berhenti("TIDAK_ADA_AKSES",
        `tombol 'Aksi Lainnya' tidak tampil dlm 10 dtk. Tombol yang terlihat: ${JSON.stringify(terlihat)}`);
    }
    if (!(await bukaPemicu(tombol, menuTerbuka))) throw new Berhenti("ITEM_MENU_TIDAK_ADA", "menu 'Aksi Lainnya' tidak bisa dibuka");
    const pola = polaItemGantiMode(ke);
    const itemMenu = () => [...document.querySelectorAll('[role="menuitem"]')].filter(tampak);
    const item = await tunggu(() => itemMenu().find((m) => pola.test(bersih(m.innerText))), 5000);
    const daftar = itemMenu().map((m) => bersih(m.innerText)).slice(0, 30);
    if (!item) {
      await tutupMenu();
      if (!wajib) return { item: null, n: null, daftar };
      throw new Berhenti("ITEM_MENU_TIDAK_ADA",
        `item 'Ganti Mode (Ke ${ke})' tidak ada di menu 'Aksi Lainnya'. Item yang terlihat: ${JSON.stringify(daftar)}`);
    }
    return { item, n: angkaItemMenu(item.innerText), daftar };
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
  async function tungguKlikManusia(item, n, hasil, ke) {
    item.style.outline = "3px solid #e65100";
    item.scrollIntoView({ block: "nearest" });
    log(`👉 KLIK SENDIRI "Ganti Mode (Ke ${ke}) (${n})" lalu konfirmasi dialognya. `
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
  async function klikOtomatis(item, hasil, ke) {
    hasil.waktu_klik = new Date().toISOString();
    item.click();
    const dlg = await tunggu(dialogTerbuka, 8000, 300);
    if (!dlg) {
      log("Tidak ada dialog konfirmasi — diverifikasi lewat tabel.");
      return "TANPA_DIALOG";
    }
    const { teks, tombol } = catatDialog(dlg);
    if (!dialogSesuai(teks, ke)) {
      hasil.waktu_klik = "";
      tekanEscape();
      throw new Berhenti("DIALOG_TIDAK_DIKENAL", `dialog tidak cocok dgn arah ke ${ke}: ${teks.slice(0, 200)}`);
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

  // --- ganti mode PER BARIS lewat menu ⋮ ------------------------------------------
  // Cara manual user utk PAPI -> CAPI (2026-09-22): ⋮ di kanan baris -> "Ganti Mode" -> pilih CAPI.
  // Struktur DILIHAT LANGSUNG 2026-09-22 (Chrome user, baris PAPI, READ-ONLY — tidak ada yg dikirim):
  // - ⋮ = satu-satunya button[aria-haspopup="menu"] di baris (sel paling kanan); terbuka lewat pointerdown.
  // - Menu berisi item biasa (BUKAN submenu): Assign Petugas, Clear Petugas, …, Ganti Mode, Ganti Sampel,
  //   Ganti Wilayah, Reset Versi Data, Panel Logs, Hapus Assignment  <- "Ganti Mode" dicocokkan PERSIS.
  // - Klik "Ganti Mode" -> [role=dialog] "Ganti Mode": field "Mode Pendataan" = Radix Select
  //   (button[role=combobox], teks "Pilih mode yang tersedia" atau mode terpilih) + <select aria-hidden>
  //   bayangan berisi "", CAPI, CAWI, PAPI; tombol "Ubah Mode Pendataan" (type=submit, disabled sampai
  //   ada pilihan) & "Close". Daftar opsi (listbox) dirender di LUAR dialog. Pilihan awal bisa kosong
  //   atau sudah = mode baris sekarang.
  // - BELUM terlihat: apa yang terjadi SETELAH "Ubah Mode Pendataan" (tutup + toast? dialog konfirmasi?).
  //   Ditangani: dialog tertutup = terkirim; dialog konfirmasi baru -> dialogSesuai + satu tombol
  //   konfirmasi; dialog tetap terbuka -> DIALOG_TIDAK_TERTUTUP (berhenti).

  const menuTampak = () => [...document.querySelectorAll('[role="menu"]')].filter(terbuka);
  const listboxTerbuka = () => [...document.querySelectorAll('[role="listbox"]')].filter(terbuka).pop() || null;
  const itemDi = (menu) => [...menu.querySelectorAll('[role="menuitem"],[role="menuitemradio"],[role="menuitemcheckbox"]')]
    .filter(tampak);
  const teksEl = (el) => bersih(el.innerText || el.getAttribute("aria-label") || "");

  /** <tr> baris ber-kode persis `kode` di halaman tampil (urutan boleh berubah), atau null. */
  function trUntukKode(kode) {
    const t = tabel();
    if (!t) return null;
    const b = barisDariTabel(bacaTabelWajib()).find((x) => samaKode(x.kode, kode));
    return b ? t.querySelectorAll("tbody tr")[b.indeks] || null : null;
  }

  /** Tombol ⋮ baris: satu-satunya [aria-haspopup=menu] di baris, cadangan satu-satunya tombol
   *  (bukan checkbox) di sel paling kanan yang bertombol. null kalau tidak tepat satu. */
  function tombolMenuBaris(tr) {
    const popup = [...tr.querySelectorAll('[aria-haspopup="menu"]')].filter(tampak);
    if (popup.length === 1) return popup[0];
    if (popup.length > 1) return null;
    const sel = [...tr.querySelectorAll("td")].reverse()
      .map((td) => [...td.querySelectorAll('button,[role="button"]')].filter(tampak).filter((x) => x.getAttribute("role") !== "checkbox"))
      .find((arr) => arr.length);
    return sel && sel.length === 1 ? sel[0] : null;
  }

  /** Buka menu ⋮ baris `b` -> {items, iGanti}. Berhenti kalau tombol/menu tidak jelas. */
  async function bukaMenuBaris(b, ke) {
    await tutupMenu();
    const tr = trUntukKode(b.kode);
    if (!tr) throw new Berhenti("TABEL_BERUBAH", `baris '${b.kode}' tidak tampil lagi di tabel`);
    const pemicu = tombolMenuBaris(tr);
    if (!pemicu) {
      throw new Berhenti("MENU_BARIS_TIDAK_ADA", `tombol ⋮ baris '${b.kode}' tidak ditemukan tepat satu `
        + `(tombol di baris: ${JSON.stringify([...tr.querySelectorAll('button,[role="button"]')].filter(tampak).map(teksEl))})`);
    }
    const sebelum = new Set(menuTampak());
    const menu = await bukaPemicu(pemicu, () => menuTampak().find((m) => !sebelum.has(m)));
    if (!menu) {
      throw new Berhenti("MENU_BARIS_TIDAK_ADA", `menu ⋮ baris '${b.kode}' tidak terbuka `
        + "(tab fasih-sm harus tampil di depan selama skrip jalan)");
    }
    const items = await tunggu(() => { const x = itemDi(menu); return x.length ? x : null; }, 3000) || [];
    return { items, iGanti: pilihItemGantiModeBaris(items.map(teksEl), ke) };
  }

  /** Buka menu ⋮, klik item "Ganti Mode" (dicocokkan persis — satu menu dgn "Hapus Assignment"),
   *  tunggu dialog pilihan mode. -> dialog. Berhenti kalau item/dialog tidak jelas. */
  async function bukaDialogGantiMode(b, ke) {
    const { items, iGanti } = await bukaMenuBaris(b, ke);
    if (iGanti === null) {
      await tutupMenu();
      throw new Berhenti("ITEM_MENU_TIDAK_ADA", `menu ⋮ '${b.kode}' tidak punya tepat satu item 'Ganti Mode'. `
        + `Item: ${JSON.stringify(items.map(teksEl))}`);
    }
    const item = items[iGanti];
    if (!/^Ganti Mode\b/i.test(teksEl(item))) throw new Berhenti("TABEL_BERUBAH", "item menu berubah sebelum diklik");
    const sebelum = dialogTerbuka();
    item.click();
    const dlg = await tunggu(() => { const d = dialogTerbuka(); return d && d !== sebelum ? d : null; }, 8000, 250);
    if (!dlg) {
      await tutupMenu();
      throw new Berhenti("OPSI_MODE_TIDAK_JELAS", `dialog 'Ganti Mode' tidak muncul utk ${b.kode}`);
    }
    return dlg;
  }

  /** Bagian dialog "Ganti Mode": {cb: combobox Radix, sel: <select> bayangan, kirim: tombol
   *  "Ubah Mode Pendataan", tutup: tombol "Close"}. */
  function bagianDialog(dlg) {
    const tombol = [...dlg.querySelectorAll("button")].filter(tampak);
    const i = pilihTombolKonfirmasi(tombol.map((x) => (x.getAttribute("role") === "combobox" ? "" : bersih(x.innerText))));
    return {
      cb: dlg.querySelector('[role="combobox"]'),
      sel: dlg.querySelector("select"),
      kirim: i === null ? null : tombol[i],
      tutup: tombol.find((x) => /^(close|tutup|batal)$/i.test(bersih(x.innerText) || x.getAttribute("aria-label") || "")) || null,
    };
  }

  /** Mode yang sedang terpilih di dialog (teks combobox, cadangan nilai <select>). */
  const modeTerpilih = (p) => bersih((p.cb && p.cb.innerText) || (p.sel && p.sel.value) || "");

  /** Pilih <ke> di Radix Select dialog. Cara 1: <select> bayangan (Radix memasang onChange-nya utk
   *  autofill -> setValue); cara 2: buka combobox, fokus opsi, Enter. Hasil diverifikasi dari teks
   *  combobox. Tidak mengirim apa pun. -> true kalau terpilih. */
  async function pilihModeDiDialog(dlg, p, ke) {
    const sudah = () => pilihOpsiMode([modeTerpilih(p)], ke) === 0;
    if (sudah()) return true;
    if (p.sel) {
      const opt = [...p.sel.options].find((o) => pilihOpsiMode([o.value || o.text], ke) === 0);
      if (opt) {
        Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(p.sel, opt.value);
        p.sel.dispatchEvent(new Event("change", { bubbles: true }));
        if (await tunggu(sudah, 2000)) return true;
      }
    }
    if (p.cb) {
      const lb = await bukaPemicu(p.cb, listboxTerbuka);
      if (lb) {
        const opsi = [...lb.querySelectorAll('[role="option"]')].filter(tampak);
        const i = pilihOpsiMode(opsi.map(teksEl), ke);
        if (i !== null) {
          opsi[i].focus();
          opsi[i].dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true, cancelable: true }));
          await tunggu(sudah, 2000);
        }
        if (listboxTerbuka()) {
          (listboxTerbuka().querySelector('[role="option"]') || listboxTerbuka())
            .dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true, cancelable: true }));
          await tunggu(() => !listboxTerbuka(), 2000);
        }
      }
    }
    return sudah();
  }

  /** Tutup dialog "Ganti Mode" TANPA mengirim: tombol Close, cadangan Esc. */
  async function tutupDialog(dlg, p) {
    if (p.tutup) p.tutup.click();
    if (await tunggu(() => !terbuka(dlg), 3000)) return;
    tekanEscape();
    if (await tunggu(() => !terbuka(dlg), 3000)) return;
    throw new Berhenti("DIALOG_TIDAK_TERTUTUP", "dialog 'Ganti Mode' tidak mau ditutup — tutup manual");
  }

  /** Setelah "Ubah Mode Pendataan": dialog tertutup -> "DIKIRIM"; dialog konfirmasi baru -> diklik
   *  satu-satunya tombol konfirmasinya ("DIKONFIRMASI"); dialog tetap terbuka -> berhenti (pesannya
   *  dicatat). waktu_klik sudah diisi pemanggil — gagal-tertutup: kode tidak diklik ulang otomatis. */
  async function tungguSesudahKirim(dlg, p, ke) {
    const v = await tunggu(() => {
      const d = dialogTerbuka();
      if (d && d !== dlg) return { konfirmasi: d };
      return terbuka(dlg) ? null : { tutup: true };
    }, 20000, 300);
    if (v && v.tutup) return "DIKIRIM";
    if (v && v.konfirmasi) {
      const { teks, tombol } = catatDialog(v.konfirmasi);
      const i = dialogSesuai(teks, ke) ? pilihTombolKonfirmasi(tombol) : null;
      if (i === null) {
        // Konfirmasi dibatalkan; dialog "Ganti Mode" di bawahnya ikut ditutup TANPA dikirim ulang.
        tekanEscape();
        await tunggu(() => !terbuka(v.konfirmasi), 3000);
        if (terbuka(dlg)) await tutupDialog(dlg, p).catch(() => {});
        throw new Berhenti("DIALOG_TIDAK_DIKENAL", `dialog sesudah 'Ubah Mode Pendataan': ${teks.slice(0, 200)} | tombol ${JSON.stringify(tombol)}`);
      }
      [...v.konfirmasi.querySelectorAll("button")].filter(tampak)[i].click();
      if (!(await tunggu(() => !dialogTerbuka(), 20000))) {
        throw new Berhenti("DIALOG_TIDAK_TERTUTUP", `dialog masih terbuka sesudah konfirmasi: ${bersih(dialogTerbuka().innerText).slice(0, 200)}`);
      }
      return "DIKONFIRMASI";
    }
    throw new Berhenti("DIALOG_TIDAK_TERTUTUP", `dialog 'Ganti Mode' masih terbuka 20 dtk sesudah dikirim: ${bersih(dlg.innerText).slice(0, 200)}`);
  }

  /** Ganti mode SATU baris: ⋮ -> "Ganti Mode" -> pilih <ke> -> "Ubah Mode Pendataan". hasil.waktu_klik
   *  diisi SEBELUM klik kirim. uji=true (dryrun): <ke> dipilih di dialog lalu dialog DITUTUP tanpa
   *  dikirim (pilihan di formulir saja, tidak mengubah data). -> "DIKIRIM"|"DIKONFIRMASI"|"UJI_OK" */
  async function gantiModeBaris(b, ke, hasil, uji) {
    const dlg = await bukaDialogGantiMode(b, ke);
    const { teks } = catatDialog(dlg);
    const p = bagianDialog(dlg);
    const opsiSelect = p.sel ? [...p.sel.options].map((o) => o.value || o.text).filter(Boolean) : [];
    if (!/mode/i.test(teks) || !(p.cb || p.sel) || !p.kirim
      || (p.sel && pilihOpsiMode(opsiSelect, ke) === null)) {
      await tutupDialog(dlg, p);
      throw new Berhenti("OPSI_MODE_TIDAK_JELAS", `dialog 'Ganti Mode' tidak sesuai peta (pilihan mode + tombol `
        + `'Ubah Mode Pendataan'): ${teks.slice(0, 200)} | opsi ${JSON.stringify(opsiSelect)}`);
    }
    if (!(await pilihModeDiDialog(dlg, p, ke))) {
      const terbaca = modeTerpilih(p);
      await tutupDialog(dlg, p);
      throw new Berhenti("OPSI_MODE_TIDAK_JELAS", `${ke} tidak berhasil dipilih di dialog (terbaca '${terbaca}') — tidak dikirim`);
    }
    if (!(await tunggu(() => !p.kirim.disabled, 3000))) {
      await tutupDialog(dlg, p);
      throw new Berhenti("OPSI_MODE_TIDAK_JELAS", `tombol '${bersih(p.kirim.innerText)}' tetap nonaktif sesudah memilih ${ke}`);
    }
    if (uji) {
      log(`  dialog 'Ganti Mode' ${b.kode}: ${ke} terpilih, tombol '${bersih(p.kirim.innerText)}' aktif — ditutup TANPA dikirim.`);
      await tutupDialog(dlg, p);
      return "UJI_OK";
    }
    hasil.waktu_klik = new Date().toISOString();
    p.kirim.click();
    const cara = await tungguSesudahKirim(dlg, p, ke);
    await tutupMenu();
    await sleep(1500);
    return cara;
  }

  /** Target: ubah `pilih` satu per satu lewat menu ⋮. Setiap baris yang SUDAH diklik langsung
   *  dicatat (dipilih = yang benar-benar diklik, waktu_klik) & disimpan, supaya kegagalan di baris
   *  berikutnya tidak membuat baris sebelumnya diklik ulang. dryrun: alur diuji pada baris pertama. */
  async function ubahPerBaris(o, pilih, hasil, ke) {
    const centang = kodeTercentangDiHalaman();
    if (centang.length) {
      throw new Berhenti("CENTANG_TIDAK_SESUAI", `ada baris tercentang (${centang}) — lepas dulu; aksi per baris tidak memakai centang`);
    }
    if (o.mode === "dryrun") {
      await gantiModeBaris(pilih[0], ke, hasil, true);
      hasil.status = "DRY_RUN_AKAN_DIUBAH";
      hasil.pesan += ` | ⋮ -> Ganti Mode -> ${ke} teruji di ${pilih[0].kode} (tidak dikirim); ${pilih.length} baris akan diubah satu per satu`;
      return hasil;
    }
    const diklik = [];
    const cara = new Set();
    for (const b of pilih) {
      const k = { waktu_klik: "" };
      let c = null;
      try {
        if (o.mode === "manual") c = (await tungguManusiaBaris(b, ke, k)) ? "MANUAL" : null;
        else c = await gantiModeBaris(b, ke, k, false);
      } finally {
        if (k.waktu_klik) {
          diklik.push(b);
          Object.assign(hasil, {
            status: "DIUBAH_MENUNGGU", waktu_klik: hasil.waktu_klik || k.waktu_klik, klik_terakhir: k.waktu_klik,
            dipilih: diklik.map((x) => x.kode).join(" | "), petugas_dipilih: diklik.map((x) => x.petugas).join(" | "),
          });
          simpanHasil(hasil);
        }
      }
      if (c === null) {
        if (!diklik.length) throw new Berhenti("BELUM_BERUBAH", `${b.kode} dilewati (ubahModa.lewati())`);
        log(`  ${b.kode} dilewati — sisa baris putaran ini tidak dikerjakan.`);
        break;
      }
      cara.add(c);
      log(`  ✔ ${b.kode}: ⋮ -> Ganti Mode -> ${ke} (${c})`);
      await sleep(acak(600, 1200));
    }
    hasil.status = "DIUBAH_MENUNGGU";
    hasil.pesan += ` | per baris ${diklik.length}/${pilih.length}: ${[...cara].join(",")}`;
    return hasil;
  }

  let lewatiManusia = false;

  /** Mode manual per baris: tombol ⋮ disorot, MANUSIA yang klik ⋮ -> Ganti Mode -> <ke> (+ konfirmasi).
   *  Selesai = pernah ada menu/dialog terbuka lalu semuanya tertutup 2,5 dtk. Batal: ubahModa.lewati().
   *  Gagal-tertutup: selesai tanpa lewati() dianggap DIKLIK (tidak akan diklik ulang otomatis). */
  async function tungguManusiaBaris(b, ke, hasil) {
    const tr = trUntukKode(b.kode);
    const pemicu = tr && tombolMenuBaris(tr);
    if (pemicu) {
      pemicu.style.outline = "3px solid #e65100";
      pemicu.scrollIntoView({ block: "nearest" });
    }
    log(`👉 KLIK SENDIRI ⋮ di baris ${b.kode} -> Ganti Mode -> ${ke} (+ konfirmasi). `
      + "Kalau batal: ketik ubahModa.lewati() di Console.");
    lewatiManusia = false;
    const adaLapisan = () => menuTerbuka() || !!dialogTerbuka();
    await tunggu(() => lewatiManusia || adaLapisan(), 15 * 60 * 1000, 300);
    let diamSejak = 0;
    await tunggu(() => {
      if (lewatiManusia) return true;
      if (adaLapisan()) { diamSejak = 0; return false; }
      diamSejak = diamSejak || Date.now();
      return Date.now() - diamSejak >= 2500;
    }, 15 * 60 * 1000, 300);
    if (pemicu) pemicu.style.outline = "";
    if (lewatiManusia) return false;
    hasil.waktu_klik = hasil.waktu_klik || new Date().toISOString();
    return true;
  }

  // --- verifikasi tertunda ------------------------------------------------------
  // Mode baru TIDAK langsung terbaca di tabel (run user 2026-09-15). Kode yang sudah
  // dikonfirmasi masuk antrean (DIUBAH_MENUNGGU) & dicek ulang di sela target lain,
  // bukan ditunggu di tempat. Objek hasil dipakai bersama & ditimpa di tempat.

  /** {kode: mode} dari baris tabel; "(hilang)" kalau kode tidak tampil. */
  const modeKode = (baris, kode) => Object.fromEntries(kode.map((k) =>
    [k, (baris.find((b) => samaKode(b.kode, k)) || { mode: "(hilang)" }).mode]));

  const menit = (ms) => (Number.isFinite(ms) ? `${(ms / 60000).toFixed(1)} mnt` : "? mnt");

  // Target subsls: kode yang diklik tapi tidak tampil di halaman hasil pencarian subsls (mis.
  // urutan tabel berubah setelah mode berganti) dicari satu per satu — paling banyak sekian kode
  // per cek (tiap kode = 1 pencarian, rawan HTTP 429). Utk hasil >1 halaman, klik per putaran
  // juga dibatasi sebanyak ini (prosesTarget) supaya semua yang diklik tetap bisa diverifikasi.
  const MAKS_CARI_PER_KODE = 10;

  function entriAntrean(t, hasil) {
    const wk = waktuKlikDari(hasil);
    const waktuKlik = Number.isFinite(wk) ? wk : Date.now();
    return { t, hasil, kode: kodeSudahDiklik(hasil), waktuKlik, nCek: 0, gagal: 0,
      cekBerikut: Math.max(Date.now(), waktuKlik + jedaCekVerifikasi(0)) };
  }

  /** Satu kali cek ulang. Hasil tersimpan hanya ditimpa kalau keputusannya final (mode tujuan
   *  terbaca, atau batas tunggu habis). Cek yang gagal dijadwal ulang; 3x beruntun pada kode yang
   *  sama (atau galat penghenti) -> kode status yang menghentikan batch. -> null | kode status. */
  async function cekUlang(e, o) {
    const kunci = kunciTarget(e.t);
    const ke = keTarget(e.t);
    e.nCek += 1;
    try {
      const { baris } = await cari(e.t);
      const mode = modeKode(baris, e.kode);
      const hilang = e.kode.filter((k) => mode[k] === "(hilang)");
      if (!e.t.kode && hilang.length && hilang.length <= MAKS_CARI_PER_KODE) {
        for (const k of hilang) {
          const r = await cari({ kode: k, idsubsls: idsubslsDariKode(k), ke });
          mode[k] = modeKode(r.baris, [k])[k];
        }
      }
      e.gagal = 0;
      const sejak = Date.now() - e.waktuKlik;
      const v = putuskanVerifikasi(mode, sejak, o.batasTungguMs, ke);
      log(`Cek ulang ke-${e.nCek} ${kunci} (${menit(sejak)} sejak diklik):`, mode, `-> ${v}`);
      if (v === "MENUNGGU") {
        e.cekBerikut = Date.now() + jedaCekVerifikasi(e.nCek);
        return null;
      }
      if (v === "TERVERIFIKASI") {
        e.hasil.status = "DIUBAH_TERVERIFIKASI";
        e.hasil.pesan += ` | ${ke} terbaca ${menit(sejak)} setelah diklik (cek ke-${e.nCek})`;
      } else {
        e.hasil.status = "DIUBAH_BELUM_TERVERIFIKASI";
        e.hasil.pesan += ` | ${menit(sejak)} setelah diklik masih ${JSON.stringify(mode)} — cek di fasih-sm; `
          + "kalau memang belum berubah, ulangi dgn klikUlang";
      }
      simpanHasil(e.hasil);
      return STATUS_BERHENTI_SEGERA.has(e.hasil.status) ? e.hasil.status : null;
    } catch (err) {
      if (!(err instanceof Berhenti)) console.error(err);
      const kode = err instanceof Berhenti ? err.kode : "ERROR_TAK_TERDUGA";
      e.gagal += 1;
      log(`⚠️ cek ulang ${kunci} gagal (${e.gagal}/3): ${err && err.message ? err.message : err} `
        + "— tetap DIUBAH_MENUNGGU (tidak diklik ulang).");
      if (kode === "DIHENTIKAN_PENGGUNA" || STATUS_BERHENTI_SEGERA.has(kode) || e.gagal >= 3) return kode;
      e.cekBerikut = Date.now() + jedaCekVerifikasi(e.nCek);
      return null;
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
      log(`⏳ ${antrean.length} kode/target menunggu Mode terbaca berubah`
        + (sampai === "habis" ? "" : ` (batas ${batas()} — yang baru belum diklik)`)
        + ` — cek berikutnya ${Math.round(jeda / 1000)} dtk lagi.`);
      try {
        await tidur(jeda);
      } catch (err) {
        if (err instanceof Berhenti) return err.kode;
        throw err;
      }
    }
  }

  /** Tunggu SATU entri sampai final (dipakai target subsls yang diulang per putaran: putaran
   *  berikutnya baru boleh mencari setelah yang diklik terbaca berubah).
   *  -> null kalau terverifikasi, atau kode penghenti. */
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

  /** Satu putaran utk satu target: cari -> rencanakan -> (centang -> menu -> klik).
   *  k = {maksPerKlik, terlarang(kode)}: batas baris per klik & kode yang sudah diklik (belum
   *  terbukti berubah) sehingga TIDAK boleh diklik lagi. Setelah klik, hasil langsung disimpan
   *  sbg DIUBAH_MENUNGGU — verifikasinya lewat antrean (cekUlang), bukan di sini. */
  async function prosesTarget(t, o, k) {
    const ke = keTarget(t);
    const hasil = {
      waktu: new Date().toISOString(), jalan: o.mode, idsubsls: t.idsubsls, akun_ppl: (t.ppl || []).join(","),
      baris_sheet: (t.baris || []).join(","), status: "", jumlah_assignment: "", capi: "", papi: "",
      dipilih: "", petugas_dipilih: "", pesan: "", kode_target: t.kode || "", kunci: kunciTarget(t), ke,
    };
    let dicentang = [];
    try {
      const { baris, halaman } = await cari(t);
      const rencana = rencanakan(t, baris, o.cakupan, halaman[1] > 1);
      // Target kode: baris kode persis itu saja; target subsls/sheet: semua baris subsls-nya.
      const milik = baris.filter(cocokTarget(t));
      let pilih = rencana.pilih;
      let pesan = rencana.pesan;
      const dilarang = pilih.filter((b) => k.terlarang(b.kode));
      if (dilarang.length) {
        pilih = pilih.filter((b) => !k.terlarang(b.kode));
        pesan += ` | ${dilarang.length} kode sudah diklik & menunggu verifikasi, TIDAK diklik ulang `
          + `(mis. ${dilarang[0].kode})`;
      }
      // Hasil >1 halaman: baris yang diklik bisa pindah halaman setelah modenya berubah, lalu harus
      // diverifikasi satu per satu lewat pencarian kode -> per klik paling banyak MAKS_CARI_PER_KODE.
      const maks = halaman[1] > 1 ? Math.min(k.maksPerKlik, MAKS_CARI_PER_KODE) : k.maksPerKlik;
      if (pilih.length > maks) {
        pesan += ` | ${pilih.length - maks} sisanya di putaran berikutnya (maks ${maks} per klik)`;
        pilih = pilih.slice(0, maks);
      }
      Object.assign(hasil, {
        jumlah_assignment: milik.length,
        capi: milik.filter((b) => b.mode.toUpperCase() === "CAPI").length,
        papi: milik.filter((b) => b.mode.toUpperCase() === "PAPI").length,
        dipilih: pilih.map((b) => b.kode).join(" | "),
        petugas_dipilih: pilih.map((b) => b.petugas).join(" | "),
        pesan,
      });
      log(`${milik.length} ${t.kode ? "baris kode persis" : "assignment subsls ini"} tampil `
        + `(CAPI ${hasil.capi}, PAPI ${hasil.papi}; ${baris.length - milik.length} baris lain diabaikan) `
        + `-> ${rencana.status}${pilih.length ? `, ${pilih.length} akan diubah ke ${ke}` : ""}. 25 baris pertama:`);
      console.table(ringkasBaris(milik));
      if (pilih.length) console.table(ringkasBaris(pilih));

      if (o.mode === "petakan" && o.caraKlik === "baris") {
        // READ-ONLY: ⋮ -> "Ganti Mode" -> catat isi dialog -> Close. Tidak memilih & tidak mengirim.
        const contoh = pilih[0] || milik[0];
        let info = "tidak ada baris utk dicoba";
        if (contoh) {
          const dlg = await bukaDialogGantiMode(contoh, ke);
          const p = bagianDialog(dlg);
          info = `dialog 'Ganti Mode' ${contoh.kode}: ${bersih(dlg.innerText).slice(0, 160)} | terpilih '${modeTerpilih(p)}'`
            + ` | opsi ${JSON.stringify(p.sel ? [...p.sel.options].map((x) => x.value || x.text).filter(Boolean) : [])}`
            + ` | tombol kirim '${p.kirim ? bersih(p.kirim.innerText) : "(TIDAK ADA)"}'`;
          await tutupDialog(dlg, p);
        }
        hasil.status = `PETAKAN_${rencana.status}`;
        hasil.pesan += ` | ${info}`;
        return hasil;
      }
      if (o.mode === "petakan") {
        const menu = await bukaMenuGantiMode(ke, false);
        await tutupMenu();
        hasil.status = `PETAKAN_${rencana.status}`;
        hasil.pesan += ` | item menu (0 dicentang): ${JSON.stringify(menu.daftar)}`
          + (menu.item ? "" : ` — item 'Ganti Mode (Ke ${ke})' TIDAK tampil saat 0 dicentang`);
        return hasil;
      }
      if (rencana.status !== "PERLU_DIUBAH") {
        hasil.status = rencana.status;
        return hasil;
      }
      if (!pilih.length) {
        hasil.status = "SUDAH_DIKLIK_MENUNGGU";
        return hasil;
      }
      if (o.caraKlik === "baris") return await ubahPerBaris(o, pilih, hasil, ke);

      dicentang = pilih;
      await aturCentang(pilih, true);
      const harap = pilih.map((b) => b.kode).sort();
      const nyata = kodeTercentangDiHalaman();
      if (JSON.stringify(nyata) !== JSON.stringify(harap)) {
        throw new Berhenti("CENTANG_TIDAK_SESUAI", `tercentang di halaman: ${nyata}; seharusnya: ${harap}`);
      }
      const { item, n } = await bukaMenuGantiMode(ke);
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
      if (o.mode === "manual") {
        if (!(await tungguKlikManusia(item, n, hasil, ke))) {
          throw new Berhenti("BELUM_BERUBAH", "menu ditutup tanpa dialog konfirmasi — dianggap batal (tidak diklik)");
        }
      } else {
        cara = await klikOtomatis(item, hasil, ke);
      }
      // Klik sudah terjadi: simpan SEKARANG supaya berhenti/reload di bawah pun kodenya tidak diklik ulang.
      hasil.status = "DIUBAH_MENUNGGU";
      hasil.klik_terakhir = hasil.waktu_klik;
      hasil.pesan += ` | ${cara}`;
      simpanHasil(hasil);
      // Pilihan tabel bisa bertahan lintas pencarian — centang yang tertinggal
      // bisa ikut terkirim di aksi massal target berikutnya.
      await tutupMenu();
      await lepasCentang(t, pilih);
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
      // kode yang cuma dibaca (sudah berubah / tidak ada) memakai jeda pendek.
      lewatiSelesai: true, jedaMin: 1500, jedaMaks: 3000,
      batasTungguMs: BATAS_TUNGGU_VERIFIKASI_MS, maksMenunggu: 10, maksPerKlik: 50, jarakCariMs: 2000, klikUlang: false,
      ...opsi,
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
        + "atau muat list: ubahModa.muatDaftarKode(`...`) / ubahModa.muatDaftarSubsls(`...`, {ke: \"CAPI\"}).");
      return;
    }
    // Arah melekat pada TARGET (bukan opsi jalankan), supaya list yang dimuat utk CAPI tidak
    // pernah jalan ke PAPI karena opsi lupa ditulis. Opsi `ke` hanya pemeriksa.
    const arah = [...new Set(TARGET.map((t) => String((t && t.ke) || "PAPI").toUpperCase()))];
    if (arah.length !== 1 || !MODE.includes(arah[0])) {
      log(`⛔ arah target tidak jelas (${JSON.stringify(arah)}) — muat ulang daftarnya.`);
      return;
    }
    const ke = arah[0];
    if (opsi.ke && String(opsi.ke).toUpperCase() !== ke) {
      log(`⛔ jalankan({ke: "${opsi.ke}"}), tapi target yang dimuat berarah ke ${ke}. Muat ulang daftar dgn arah yang benar.`);
      return;
    }
    // Ke CAPI lewat menu ⋮ per baris (cara manual user, struktur dilihat 2026-09-22); ke PAPI lewat
    // "Aksi Lainnya" massal (terbukti di run live 2026-09-15). caraKlik menimpa.
    o.caraKlik = opsi.caraKlik || (ke === "CAPI" ? "baris" : "massal");
    if (!["baris", "massal"].includes(o.caraKlik)) {
      log(`caraKlik '${o.caraKlik}' tidak dikenal (baris | massal)`);
      return;
    }
    const perPage = Number(new URLSearchParams(location.search).get("perPage") || 0);
    if (perPage < 50) {
      log(`⛔ perPage=${perPage || "?"}. Skrip hanya membaca halaman yang tampil (paginasi tidak dipindah), `
        + "jadi makin sedikit baris per halaman makin banyak assignment yang tidak terlihat. "
        + `Buka URL ini, lalu TEMPEL ULANG skripnya:\n${location.origin}${location.pathname}?page=1&perPage=100`);
      return;
    }
    if (!tabel() || !kotakCari()) {
      log("Buka dulu halaman list assignment (tabel 'Kode Identitas' & kotak 'Cari...' harus tampil).");
      return;
    }
    jarakCariMs = Math.max(500, Number(o.jarakCariMs) || 2000);

    const semua = muatHasil();
    const live = o.mode === "manual" || o.mode === "otomatis";
    // Otomatis TIDAK mensyaratkan run manual dulu (permintaan user 2026-09-15). Penjaganya: ketik
    // YA per batch, dialog yang tidak cocok arahnya / tombol ambigu -> berhenti, angka menu harus =
    // jumlah dicentang, dan selama browser ini belum punya satu bukti berhasil ke arah ini, tiap klik
    // hanya 1 baris & kode berikutnya menunggu kode pertama terbukti berubah.

    let daftar = TARGET;
    if (o.idsubsls) {
      const ingin = new Set(o.idsubsls);
      daftar = daftar.filter((t) => ingin.has(t.idsubsls));
    }
    if (o.lewatiSelesai && o.mode !== "petakan") {
      const tuntas = live ? STATUS_TUNTAS_LIVE : STATUS_TUNTAS_DRY;
      daftar = daftar.filter((t) => {
        const h = semua[kunciTarget(t)];
        if (!masihTuntas(h, t, semua, tuntas)) return true;
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
      const cakupanTeks = satuan === "kode identitas" ? ""
        : ke === "CAPI" ? " — SEMUA assignment PAPI yang tampil di tiap subsls"
          : `, cakupan ${o.cakupan}`;
      const pesan = `MENGUBAH MODE assignment ke ${ke} SUNGGUHAN utk ${daftar.length} ${satuan}`
        + ` (mode ${o.mode}${cakupanTeks}${o.caraKlik === "baris" ? ", lewat menu ⋮ per baris" : ""}).`;
      if (o.mode === "otomatis") {
        if (prompt(`${pesan}\nKetik YA untuk lanjut:`) !== "YA") return log("Dibatalkan.");
      } else if (!confirm(`${pesan}\nKlik "Ganti Mode" & konfirmasi tetap KAMU yang lakukan per ${satuan}. Lanjut?`)) {
        return log("Dibatalkan.");
      }
    }

    berjalan = true;
    hentikan = false;
    const hitung = {};
    const tambah = (s, n = 1) => {
      hitung[s] = (hitung[s] || 0) + n;
      if (!hitung[s]) delete hitung[s];
    };
    const catat = (lama, baru) => {
      tambah(lama, -1);
      tambah(baru);
    };
    const antrean = [];
    let bukti = adaBukti(semua, ke);
    const batas = () => (bukti ? Math.max(1, Number(o.maksMenunggu) || 1) : 1);
    const izinUlang = (kode) => o.klikUlang === true
      || (Array.isArray(o.klikUlang) && o.klikUlang.some((x) => samaKode(x, kode)));
    // Kode yang sudah diklik (di run mana pun, lewat target mana pun) & belum terbukti berubah.
    // Dibaca ulang tiap putaran: klik & verifikasi run ini ikut terhitung.
    const buatTerlarang = () => {
      const set = new Set(kodeDiklikSemua(muatHasil(), ke).map((x) => bersih(x).toUpperCase()));
      return (kode) => !izinUlang(kode) && set.has(bersih(kode).toUpperCase());
    };
    const perluDicek = [];
    let stop = null;
    let errorBeruntun = 0;
    if (!bukti && live) {
      log(`Belum ada ganti mode ke ${ke} yang terbukti berhasil di browser ini -> klik pertama hanya 1 baris, `
        + "dan target berikutnya menunggu sampai itu terbukti.");
    }
    try {
      for (let i = 0; i < daftar.length; i++) {
        const t = daftar[i];
        if (live && antrean.length) {
          stop = await layaniAntrean(antrean, o, catat, "penuh", batas);
          bukti = bukti || adaBukti(muatHasil(), ke);
          if (stop) break;
        }
        log(`=== [${i + 1}/${daftar.length}] ${t.kode ? `kode ${t.kode}` : `subsls ${t.idsubsls}`
          + ((t.ppl || []).length ? ` — PPL ${t.ppl.join(", ")}` : "")} -> ${ke} (${o.mode}) ===`);
        const kunci = kunciTarget(t);
        const lama = muatHasil()[kunci];
        const diklik = kodeSudahDiklik(lama);
        // Non-live tidak boleh menimpa hasil yang mencatat klik (kodenya bisa diklik ulang nanti).
        const jagaKlik = !live && diklik.length > 0;
        const ulangi = diulangPerSubsls(t, o.cakupan);
        let hasil = null;
        let klikTerakhir = lama && (lama.klik_terakhir || lama.waktu_klik) || "";
        let diubah = 0;

        if (live && diklik.length && !diklik.every(izinUlang)) {
          // Sudah diklik di run sebelumnya — hanya DIPERIKSA, tidak diklik ulang.
          log(`  ${diklik.length} kode sudah diklik ${menit(Date.now() - waktuKlikDari(lama))} lalu `
            + `(status ${lama.status}) — hanya diperiksa, TIDAK diklik ulang.`);
          const e = entriAntrean(t, Object.assign({}, lama, { jalan: o.mode, status: "DIUBAH_MENUNGGU", ke }));
          if (!ulangi) {
            antrean.push(e);
            tambah("DIUBAH_MENUNGGU");
            continue;
          }
          stop = await tungguEntri(e, o);
          hasil = e.hasil;
          if (stop || hasil.status !== "DIUBAH_TERVERIFIKASI") {
            tambah(hasil.status);
            log(`  -> ${hasil.status}`, hasil.pesan);
            break;
          }
          bukti = true;
          diubah += e.kode.length;
          hasil = null; // lanjut ke putaran baru di bawah
        }

        for (let putaran = 1; ; putaran++) {
          const baru = await prosesTarget(t, o,
            { maksPerKlik: bukti ? Math.max(1, Number(o.maksPerKlik) || 1) : 1, terlarang: buatTerlarang() });
          if (!baru.klik_terakhir && klikTerakhir) baru.klik_terakhir = klikTerakhir;
          klikTerakhir = baru.klik_terakhir || klikTerakhir;
          hasil = baru;
          if (hasil.status !== "DIUBAH_MENUNGGU") break;
          const e = entriAntrean(t, hasil);
          if (!ulangi) {
            antrean.push(e);
            break;
          }
          // Target subsls diulang: putaran berikutnya baru dicari setelah yang diklik terbukti berubah.
          log(`  (putaran ${putaran}) ${e.kode.length} kode diklik — menunggu Mode terbaca ${ke} sebelum putaran berikutnya.`);
          stop = await tungguEntri(e, o);
          if (stop || hasil.status !== "DIUBAH_TERVERIFIKASI") break;
          bukti = true;
          diubah += e.kode.length;
          if (putaran >= 50) {
            hasil.pesan += " | berhenti setelah 50 putaran";
            break;
          }
          await sleep(acak(o.jedaMin, o.jedaMaks));
        }
        if (diubah) hasil.pesan += ` | total ${diubah} kode terbukti ${ke} di subsls ini`;
        if (!jagaKlik) simpanHasil(hasil);
        else log("  (hasil lama yang mencatat klik tidak ditimpa oleh run non-live)");
        tambah(hasil.status);
        log(`  -> ${hasil.status}`, hasil.pesan);
        if (["CEK_HALAMAN_LAIN", "SUDAH_DIKLIK_MENUNGGU"].includes(hasil.status)) perluDicek.push(hasil);
        if (stop) break;
        if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
          stop = hasil.status;
          break;
        }
        const gagal = hasil.status.startsWith("ERROR_") || STATUS_LANJUT_TAPI_HITUNG.has(hasil.status);
        errorBeruntun = gagal ? errorBeruntun + 1 : 0;
        if (errorBeruntun >= 3) {
          log(`⛔ 3 kegagalan berturut-turut (terakhir ${hasil.status}) — VPN/sesi habis? akun tanpa hak?`);
          stop = "GAGAL_BERUNTUN";
          break;
        }
        if (gagal) log(`⚠️ ${hasil.status} — lanjut ke target berikutnya (${errorBeruntun}/3 beruntun).`);
        if (i < daftar.length - 1) {
          const adaKlik = STATUS_SETELAH_KLIK.has(hasil.status) || diubah > 0;
          await sleep(adaKlik ? acak(o.jedaMin, o.jedaMaks) : acak(300, 800));
        }
      }
      if (live && !stop && antrean.length) {
        log(`Semua target sudah diproses; menunggu ${antrean.length} yang belum terbaca ${ke}...`);
        stop = await layaniAntrean(antrean, o, catat, "habis", batas);
      }
    } finally {
      berjalan = false;
      if (stop) log(`⛔ ${stop} — batch DIHENTIKAN. Periksa tabel/dialog di layar sebelum menjalankan ulang.`);
      if (antrean.length) {
        log(`⚠️ ${antrean.length} target masih DIUBAH_MENUNGGU (sudah diklik, belum terbaca ${ke}). `
          + "Jalankan ulang perintah yang sama nanti — kodenya hanya diperiksa, TIDAK diklik ulang:");
        console.table(antrean.map((e) => ({ kunci: kunciTarget(e.t), kode: e.kode.join(" | "),
          sejak_klik: menit(Date.now() - e.waktuKlik) })));
      }
      if (perluDicek.length) {
        log(`⚠️ ${perluDicek.length} target belum tuntas & perlu dicek (CEK_HALAMAN_LAIN / SUDAH_DIKLIK_MENUNGGU):`);
        console.table(perluDicek.map((h) => ({ kunci: h.kunci, status: h.status, pesan: h.pesan.slice(0, 160) })));
      }
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
      "capi", "papi", "dipilih", "petugas_dipilih", "pesan", "kode_target", "ke", "waktu_klik"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = Object.values(muatHasil()).map((h) => kolom.map((k) => kutip(h[k])).join(","));
    const blob = new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit_ubah_moda_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} target)`);
  }

  /** Arah dari opsi muat: {ke: "CAPI"|"PAPI"}; null kalau tidak valid. */
  function arahOpsi(opsi, bawaan) {
    const ke = String((opsi && opsi.ke) || bawaan || "").toUpperCase();
    return MODE.includes(ke) ? ke : null;
  }

  /** Ganti isi TARGET dgn list kode identitas yang ditempel (satu kode per baris;
   *  salinan kolom dari Excel juga bisa). Tanpa Python. Arah bawaan PAPI;
   *  kembalikan ke CAPI dgn muatDaftarKode(`...`, {ke: "CAPI"}). */
  function muatDaftarKode(teks, opsi = {}) {
    if (berjalan) return log("Masih berjalan — tunggu selesai atau ubahModa.berhenti().");
    const ke = arahOpsi(opsi, "PAPI");
    if (!ke) return log(`⛔ ke harus "PAPI" atau "CAPI" (terbaca: ${JSON.stringify(opsi.ke)}). Daftar TIDAK dimuat.`);
    const { targets, tidakDikenali, ganda } = targetDariDaftarKode(String(teks || "").split(/\r?\n/));
    targets.forEach((t) => { t.ke = ke; });
    TARGET.length = 0;
    TARGET.push(...targets);
    log(`Daftar kode dimuat: ${targets.length} kode identitas, diubah ke ${ke} (tiap kode dicari sendiri).`
      + (ganda.length ? ` ${ganda.length} kode ganda dilewati.` : ""));
    if (tidakDikenali.length) {
      log(`⚠️ ${tidakDikenali.length} baris berisi 16 digit tapi BUKAN kode identitas (tidak dimuat):`);
      console.table(tidakDikenali.map(([baris, isi]) => ({ baris, isi })));
    }
    return { kode: targets.length, ke, tidakDikenali, ganda };
  }

  /** Ganti isi TARGET dgn list idsubsls yang ditempel (satu atau lebih per baris; salinan
   *  kolom Excel juga bisa). Arah WAJIB ditulis: muatDaftarSubsls(`...`, {ke: "CAPI"}) =
   *  SEMUA assignment PAPI tiap subsls diubah ke CAPI. {ke: "PAPI"} = seperti alur sheet (cakupan). */
  function muatDaftarSubsls(teks, opsi = {}) {
    if (berjalan) return log("Masih berjalan — tunggu selesai atau ubahModa.berhenti().");
    const ke = arahOpsi(opsi, "");
    if (!ke) return log('⛔ tulis arahnya: ubahModa.muatDaftarSubsls(`...`, {ke: "CAPI"}). Daftar TIDAK dimuat.');
    const { targets, tidakDikenali, ganda, kodeIdentitas } = targetDariDaftarSubsls(String(teks || "").split(/\r?\n/), ke);
    TARGET.length = 0;
    TARGET.push(...targets);
    log(`Daftar subsls dimuat: ${targets.length} subsls, `
      + (ke === "CAPI" ? "SEMUA assignment PAPI yang tampil di tiap subsls diubah ke CAPI." : "diubah ke PAPI (cakupan).")
      + (ganda.length ? ` ${ganda.length} subsls ganda dilewati.` : "")
      + " Cocokkan dgn listmu: kolom idsubsls Excel yang berformat ANGKA kehilangan digit ke-16 (…0901 jadi …0900)"
      + " — salin dari kolom berformat Teks.");
    if (kodeIdentitas.length) {
      log(`⚠️ ${kodeIdentitas.length} baris berisi KODE IDENTITAS (bukan idsubsls) — TIDAK dimuat. `
        + "Kalau yang ingin diubah hanya kode itu, pakai muatDaftarKode:");
      console.table(kodeIdentitas.map(([baris, isi]) => ({ baris, isi })));
    }
    if (tidakDikenali.length) {
      log(`⚠️ ${tidakDikenali.length} angka panjang yang BUKAN idsubsls 16 digit (tidak dimuat; notasi ilmiah Excel?):`);
      console.table(tidakDikenali.map(([baris, isi]) => ({ baris, isi })));
    }
    return { subsls: targets.length, ke, tidakDikenali, ganda, kodeIdentitas };
  }

  global.ubahModa = {
    jalankan, ringkasan, unduh, petakanFilter, muatDaftarKode, muatDaftarSubsls, target: TARGET,
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
    /** Mode manual per baris: baris yang sedang disorot TIDAK jadi diubah. */
    lewati() {
      lewatiManusia = true;
      log("Baris yang disorot dilewati.");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil ubahModa yang tersimpan di browser ini? (unduh dulu kalau perlu)")) {
        localStorage.removeItem(KUNCI_HASIL);
      }
    },
  };
  log(`Siap: ${TARGET.length} ${TARGET.some((t) => t.kode) ? "kode identitas" : "subsls"}`
    + (TARGET.length ? ` -> ${[...new Set(TARGET.map(keTarget))].join("/")}` : "")
    + '. Mulai dgn: await ubahModa.jalankan({mode: "petakan"})');
})(typeof window !== "undefined" ? window : globalThis);
