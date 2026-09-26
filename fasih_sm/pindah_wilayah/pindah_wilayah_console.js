/**
 * pindah_wilayah_console.js — "Ubah Wilayah" (Change Region) assignment hasil suntik
 * mode satu subsls ke subsls aslinya, di fasih-sm dari DevTools Console Chrome BIASA
 * (fasih-sm mendeteksi Playwright).
 *
 * FILE INI TEMPLATE. Jangan ditempel langsung — buat versi berisi target:
 *     python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber input_usaha.xlsx --sumber input_usaha_2.xlsx \
 *         --console
 * -> pindah_wilayah_console.siap.js
 *
 * CARA PAKAI
 * ----------
 * 1. Chrome biasa, VPN aktif, login fasih-sm dgn akun yang punya menu
 *    "Aksi Lainnya -> Change Region by Selection" (Admin Kabupaten), buka TAB BARU:
 *    https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data?page=1&perPage=10
 * 2. F12 -> Console -> tempel SELURUH isi pindah_wilayah_console.siap.js -> Enter.
 * 3. ALUR SATUAN (disarankan; file siap dibuat dgn --dari-approve = dokumen yang sudah di-approve PML):
 *      await pindahWilayah.jalankan({mode: "cari", limit: 10})    // READ-ONLY per dokumen: cari -> detail -> tujuan & petugas
 *      await pindahWilayah.jalankan({mode: "pindah", limit: 1})   // pindah 1 dokumen, cek hasilnya di fasih-sm
 *      await pindahWilayah.jalankan({mode: "pindah"})             // sisanya, satu per satu
 *    Tiap dokumen diselesaikan UTUH sebelum dokumen berikutnya: cari lewat nama (lalu nama lama audit, lalu
 *    kode identitas "<subsls asal> - <nama>") -> cocokkan ID approve -> detail segar (nama cocok, masih di
 *    subsls asal, APPROVED) -> wilayah tujuan ada & dibuka + PML/PPL tujuan tepat 1+1 -> pindah -> detail dibaca
 *    ulang: SEMUA level (provinsi, kabupaten, kecamatan, desa, SLS, subsls) harus = awalan kode tujuan.
 *    Tanpa peta & tanpa cache: run yang terputus tinggal dijalankan lagi (yang sudah tuntas dilewati).
 *    Pencarian gagal (429/504 berulang) utk dokumen ber-ID approve -> lanjut lewat detail ID (nama tetap dicek).
 *    limit: mode cari = jumlah dokumen diperiksa; mode pindah = jumlah dokumen yang DIPINDAH.
 *    Opsi satuan: pakaiPencarian (default true), jedaCariMin/jedaCariMaks (ms antar-pencarian, default
 *    2500/4500, otomatis x2 s.d. x8 saat 429/504), ulangCari (default 2), tujuan, kunci, izinkanTujuanSelesai.
 *
 *    ALUR LAMA dua tahap (PETAKAN sekali, lalu kerjakan per ID tanpa mencari lagi):
 *      await pindahWilayah.jalankan({mode: "petakan"})            // READ-ONLY: cari semua dokumen -> peta disimpan
 *      await pindahWilayah.jalankan({mode: "cek", limit: 20})     // READ-ONLY per ID: detail, tujuan & petugas
 *      await pindahWilayah.jalankan({mode: "eksekusi", limit: 1}) // pindah 1 dokumen, cek hasilnya di fasih-sm
 *      await pindahWilayah.jalankan({mode: "eksekusi"})           // sisanya
 *    Petakan = pindai subsls asal (±12 request utk ~900 assignment) + cari nama HANYA utk baris
 *    yang tidak ada di sana. Cek/eksekusi hanya membaca peta: 1 detail per dokumen (sekaligus
 *    memastikan APPROVED) -> pindah. Entri BELUM_APPROVED ikut dicek ulang, jadi dokumen yang
 *    di-approve setelah dipetakan terpindah tanpa memetakan ulang.
 *    Opsi: limit (jumlah dokumen PERLU_PINDAH yang diproses), tujuan: [idsubsls...],
 *          kunci: [...], cariPerNama (default true), izinkanTujuanSelesai (default false),
 *          lewatiSelesai (default true), jedaMin/jedaMaks (ms, setelah pindah),
 *          jedaNamaMin/jedaNamaMaks (ms, antar-pencarian nama), umurCacheNamaJam (default 12)
 *    pindahWilayah.hapusCacheNama()  paksa pencarian nama diulang dari server
 *    pindahWilayah.berhenti()   hentikan di langkah berikutnya
 *    pindahWilayah.ringkasan()  hitungan status tersimpan
 *    pindahWilayah.unduh()      unduh hasil CSV
 *
 * CARA KERJA (dipetakan dari bundle halaman asli index-*.js, 2026-09-15)
 * ---------------------------------------------------------------------
 * Menu "Change Region by Selection" (butuh izin canChangeSample, maks 50 baris, semua
 * baris harus satu wilayah) membuka dialog "Change Region Assignment": pilih wilayah
 * sampai level terkecil + petugas per peran Petugas (urut sequence: Pengawas, lalu
 * Pencacah dgn induk = Pengawas terpilih). Submit ->
 *   PUT /app/api/assignment-general/api/assignment/update-region-bulk
 *   {assignmentIds, smallestLevelFullCode, groupId (= survey.regionGroupId),
 *    userRegionIds: [userRegion.id Pengawas, userRegion.id Pencacah]}  -> {success, message}
 * Petugas kosong = dipindah TANPA petugas; skrip ini SELALU mengisi keduanya
 * (ketetapan user 2026-09-15: PML+PPL subsls tujuan, masing-masing tepat 1 orang).
 * Daftar petugas: GET /app/api/survey-user/api/v1/user-region/region
 *   ?surveyPeriodId&surveyRoleId&regionCode[&parentAllocationId]  -> data[{id, allocationId,
 *   parentAllocationId, smallestRegionCode, email, username, active}]
 * Sumber dokumen: POST /app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode
 *   (length MAKS 150, start = offset) & detail primer
 *   GET /app/api/assignment-general/api/assignment/get-by-assignment-id?assignmentId=
 * ID assignment fasih-sm = segmen ID URL dokumen fasih-web (audit_log_gabungan.csv).
 *
 * KESELAMATAN
 * -----------
 * - Hanya dokumen yang cocok dgn baris input usaha (ID audit, atau nama dokumen persis & unik)
 *   dan berstatus APPROVED yang dipindah. Assignment prelist (UMK/DTSEN) tidak pernah
 *   dicocokkan lewat nama. >1 dokumen APPROVED utk satu baris -> DOKUMEN_GANDA (dilewati).
 * - Tepat sebelum memindah, detail dicek ulang: masih di subsls asal & masih APPROVED.
 * - Wilayah tujuan harus tepat 1 & sudah "Proses Listing" (dibuka) kecuali
 *   izinkanTujuanSelesai; Pengawas & Pencacah tujuan masing-masing harus TEPAT 1.
 * - Satu dokumen per request. Setelah pindah, detail dibaca ulang: subsls & setiap level wilayah
 *   (provinsi..subsls) harus = tujuan (DIPINDAH_TERVERIFIKASI) dan status tetap APPROVED — kalau
 *   tidak, batch BERHENTI.
 * - Galat SEMENTARA (HTTP 429, 502/503/504, jaringan putus) pada request baca ditunggu & diulang,
 *   bukan menghentikan batch (run user 2026-09-15: petakan berhenti di cari nama 150/260 karena 504
 *   Gateway Time-out). PUT yang kena galat sementara TIDAK dikirim ulang buta (detail dibaca dulu).
 * - Batch BERHENTI SEKETIKA kalau sesi/CSRF ditolak, respons tidak dikenal, atau hasil
 *   tidak terverifikasi. Kegagalan lain 3x beruntun juga menghentikan.
 * - RATE LIMIT (HTTP 429 "RATE_LIMIT_EXCEEDED"): request baca ditunggu & diulang (Retry-After
 *   atau 15 dtk x 2^ke, maks 6x) lalu RATE_LIMIT (berhenti). PUT yang kena 429 TIDAK langsung
 *   dikirim ulang: detail dibaca dulu, kirim ulang hanya kalau masih di asal. Pencarian nama
 *   disimpan di localStorage (12 jam) supaya run yang terputus melanjutkan, bukan mengulang.
 * - Eksekusi tanpa `limit` butuh minimal 1 DIPINDAH_TERVERIFIKASI di browser ini.
 * - Hasil disimpan di localStorage (tahan reload); dokumen tuntas dilewati saat diulang.
 */
(function (global) {
  "use strict";

  // [{k: kunci, s: sumber, b: baris, n: nama dokumen (norm), t: idsubsls tujuan,
  //   p: akun PPL sheet input usaha, ids: [id dokumen dari audit], g: nama dipakai >1 baris}]
  const TARGET = /*__TARGET__*/[];
  // idsubsls tempat dokumen disuntik (idsubsls_input audit / --subsls-asal)
  const ASAL = /*__ASAL__*/[];
  // Kode kabupaten 4 digit (awalan idsubsls) — disuntik dari inti/config.py (KODE_KAB).
  const KODE_KAB = /*__KODE_KAB__*/"5108";

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_pindah_wilayah_console.js
  // -------------------------------------------------------------------------
  const STATUS_TUNTAS = new Set(["DIPINDAH_TERVERIFIKASI", "SUDAH_DI_TUJUAN"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL", "DIPINDAH_BELUM_TERVERIFIKASI", "DIPINDAH_STATUS_BERUBAH",
    "DIPINDAH_LEVEL_BEDA", "HALAMAN_SALAH", "DIHENTIKAN_PENGGUNA", "RATE_LIMIT",
  ]);
  // HTTP 429 {"error":"RATE_LIMIT_EXCEEDED"} (run user 2026-09-15, pencarian nama beruntun
  // 0,3–0,8 dtk sambil buka wilayah berjalan). Ditunggu lalu diulang, maks sekian kali.
  const BATAS_ULANG_429 = 6;
  // Galat sementara yang ditunggu lalu diulang. 504 Gateway Time-out (HTML, bukan JSON) muncul di datatable
  // analytic tepat setelah 429 (run user 2026-09-15) — dulu dianggap RESPONS_TIDAK_DIKENAL & menghentikan petakan.
  const STATUS_SEMENTARA = new Set(["RATE_LIMIT", "SERVER_SIBUK"]);
  const HTTP_SIBUK = new Set([0, 502, 503, 504]); // 0 = fetch gagal (jaringan/VPN putus sesaat)
  const KODE_VALID = new RegExp(`^${KODE_KAB}\\d{12}$`);
  const POLA_PRELIST = / - [A-Z]+ - \d+$/;
  // Panjang kode wilayah kumulatif per level (region.level_1..level_6.full_code detail asli):
  // provinsi 51 | kabupaten 5108 | kecamatan 5108060 | desa 5108060002 | SLS 51080600020002 | subsls 5108060002000203
  const PANJANG_LEVEL = [2, 4, 7, 10, 14, 16];
  const NAMA_LEVEL = ["provinsi", "kabupaten", "kecamatan", "desa", "sls", "subsls"];
  // Jalan yang benar-benar menulis: hasil tuntasnya melewati baris itu di run berikutnya.
  const JALAN_TULIS = new Set(["eksekusi", "pindah"]);

  /** HTTP status -> "RATE_LIMIT" | "SERVER_SIBUK" (galat sementara, boleh ditunggu & diulang) | null. */
  function jenisSementara(httpStatus) {
    if (httpStatus === 429) return "RATE_LIMIT";
    return HTTP_SIBUK.has(httpStatus) ? "SERVER_SIBUK" : null;
  }

  /** Status yang dihitung sbg kegagalan beruntun (3x -> batch berhenti) tanpa menghentikan seketika. */
  function gagalDihitung(status) {
    return ["GAGAL_PINDAH", "SERVER_SIBUK", "PENCARIAN_GAGAL"].includes(status) || String(status).startsWith("ERROR_");
  }

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  /** "/app/surveys/<survei>/<periode>/data" -> {survei, periode} (null kalau bukan halaman itu). */
  function halamanData(path) {
    const m = /^\/app\/surveys\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/data\/?$/i.exec(path || "");
    return m ? { survei: m[1], periode: m[2] } : null;
  }

  const norm = (s) => String(s == null ? "" : s).split(/\s+/).filter(Boolean).join(" ").toUpperCase();
  const approved = (alias) => /^APPROVED\b/i.test(String(alias || "").trim());

  /** Kode wilayah terkecil dari objek region — datatable (level1.fullCode) maupun detail (level_1.full_code). */
  function kodeSubsls(region) {
    let node = region;
    let kode = "";
    for (let n = 1; n <= 10 && node; n++) {
      node = node[`level${n}`] || node[`level_${n}`];
      if (node && (node.fullCode || node.full_code)) kode = node.fullCode || node.full_code;
    }
    return kode;
  }

  /** Kode per level dari objek region (datatable camelCase / detail snake_case), urut level 1, 2, ... */
  function kodeLevel(region) {
    const hasil = [];
    let node = region;
    for (let n = 1; n <= 10 && node; n++) {
      node = node[`level${n}`] || node[`level_${n}`];
      if (node) hasil.push(String(node.fullCode || node.full_code || ""));
    }
    return hasil;
  }

  /** idsubsls 16 digit -> [{level, nama, kode}] dari provinsi sampai subsls; null kalau bukan kode valid. */
  function levelWilayah(kode) {
    if (!KODE_VALID.test(kode || "")) return null;
    return PANJANG_LEVEL.map((p, i) => ({ level: i + 1, nama: NAMA_LEVEL[i], kode: kode.slice(0, p) }));
  }

  /** "51 > 5108 > 5108060 > 5108060002 > 51080600020002 > 5108060002000203" (utk log). */
  function jalurLevel(kode) {
    const lv = levelWilayah(kode);
    return lv ? lv.map((x) => x.kode).join(" > ") : String(kode);
  }

  /** Level yang TIDAK sama dgn awalan tujuan -> ["kecamatan 5108010 != 5108060", ...]; [] = provinsi..subsls cocok. */
  function bedaLevel(level, tujuan) {
    const harap = levelWilayah(tujuan);
    if (!harap) return [`tujuan '${tujuan}' tidak valid`];
    const ada = level || [];
    return harap.filter((h) => ada[h.level - 1] !== h.kode).map((h) => `${h.nama} ${ada[h.level - 1] || "-"} != ${h.kode}`);
  }

  /** Lama menunggu sebelum mengulang request yang kena 429 (percobaan ke-0,1,..).
   *  Header Retry-After (detik) dihormati; tanpa itu 15 dtk x 2^ke, maks 2 menit. */
  function jedaRateLimit(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Item datatable -> bentuk ringkas utk cache pencarian nama (tanpa objek region besar). */
  function ringkasItem(it) {
    return { id: it.id, codeIdentity: it.codeIdentity || "", data1: it.data1 || "",
      assignmentStatusAlias: it.assignmentStatusAlias || "", kode: kodeItem(it) };
  }

  /** Kode subsls item datatable (atau item ringkas cache); cadangan awalan codeIdentity kalau region kosong. */
  function kodeItem(it) {
    if (it && it.kode) return it.kode;
    const k = kodeSubsls(it && it.region);
    if (k) return k;
    const m = /^(\d{16})\b/.exec((it && it.codeIdentity) || "");
    return m ? m[1] : "";
  }

  /** Item datatable -> indeks {byId, byNama}. Prelist tidak masuk indeks nama. */
  function indeksItem(items) {
    const byId = {};
    const byNama = {};
    for (const it of items || []) {
      if (!it || !it.id || byId[it.id]) continue;
      byId[it.id] = it;
      if (POLA_PRELIST.test(it.codeIdentity || "")) continue;
      const n = norm(it.data1);
      if (n) (byNama[n] = byNama[n] || []).push(it);
    }
    return { byId, byNama };
  }

  /** Satu baris input usaha -> {status, item, pesan}. `asal` = Set idsubsls asal. */
  function rencanakan(t, idx, asal) {
    if (!KODE_VALID.test((t && t.t) || "")) return { status: "TUJUAN_TIDAK_VALID", item: null, pesan: `tujuan '${t && t.t}'` };
    const viaId = (t.ids || []).map((id) => idx.byId[id]).filter(Boolean);
    const viaNama = t.g ? [] : (idx.byNama[t.n] || []);
    const kandidat = [...new Map([...viaId, ...viaNama].map((it) => [it.id, it])).values()];
    const ringkas = (arr) => arr.map((it) => `${it.id.slice(0, 8)} ${kodeItem(it)} ${it.assignmentStatusAlias || "?"}`).join("; ");
    if (!kandidat.length) {
      return t.g
        ? { status: "NAMA_GANDA_DI_AGENDA", item: null, pesan: "nama dokumen dipakai >1 baris input usaha & tidak ada ID audit" }
        : { status: "DOKUMEN_TIDAK_DITEMUKAN", item: null, pesan: "tidak ada dokumen dgn ID audit / nama ini" };
    }
    const diTujuan = kandidat.filter((it) => kodeItem(it) === t.t && approved(it.assignmentStatusAlias));
    if (diTujuan.length) {
      const lain = kandidat.filter((it) => !diTujuan.includes(it));
      return { status: "SUDAH_DI_TUJUAN", item: diTujuan[0], pesan: lain.length ? `dokumen lain utk baris ini: ${ringkas(lain)}` : "" };
    }
    const ok = kandidat.filter((it) => approved(it.assignmentStatusAlias));
    if (!ok.length) return { status: "BELUM_APPROVED", item: kandidat[0], pesan: ringkas(kandidat) };
    if (ok.length > 1) return { status: "DOKUMEN_GANDA", item: null, pesan: `${ok.length} dokumen APPROVED: ${ringkas(ok)}` };
    const it = ok[0];
    const lain = kandidat.filter((x) => x !== it);
    const catatan = lain.length ? ` | dokumen lain (bukan APPROVED): ${ringkas(lain)}` : "";
    if (!asal.has(kodeItem(it))) {
      return { status: "DI_SUBSLS_LAIN", item: it, pesan: `dokumen di ${kodeItem(it) || "?"}, bukan subsls asal${catatan}` };
    }
    return { status: "PERLU_PINDAH", item: it, pesan: `${kodeItem(it)} -> ${t.t}${catatan}` };
  }

  /** Item APPROVED non-prelist di subsls asal yang tidak diklaim baris input usaha mana pun. */
  function tidakDikenali(items, rencana, asal) {
    const diklaim = new Set(rencana.filter((r) => r.item).map((r) => r.item.id));
    return (items || []).filter((it) => it && asal.has(kodeItem(it)) && approved(it.assignmentStatusAlias)
      && !POLA_PRELIST.test(it.codeIdentity || "") && !diklaim.has(it.id));
  }

  /** Detail get-by-assignment-id (JSON) -> {status, kode, level, nama, groupId, alias, pesan}.
   *  `asal` = idsubsls asal (string) atau Set/array beberapa subsls asal. */
  function nilaiDetail(j, asal, tujuan) {
    const d = j && j.success === true ? j.data : null;
    if (!d || !d.region) return { status: "RESPONS_TIDAK_DIKENAL", pesan: `detail tidak terbaca: ${JSON.stringify(j).slice(0, 150)}` };
    const asalSet = asal instanceof Set ? asal : new Set([].concat(asal || []));
    const kode = kodeSubsls(d.region);
    const alias = d.assignment_status_alias || "";
    const groupId = d.region.group_id || "";
    const dasar = { kode, level: kodeLevel(d.region), nama: namaDetail(d), groupId, alias, pengguna: d.current_user_username || "" };
    if (!KODE_VALID.test(kode)) return { ...dasar, status: "RESPONS_TIDAK_DIKENAL", pesan: `kode wilayah detail '${kode}'` };
    if (kode === tujuan) return { ...dasar, status: "SUDAH_DI_TUJUAN", pesan: "detail: sudah di subsls tujuan" };
    if (!asalSet.has(kode)) return { ...dasar, status: "ASAL_BERUBAH", pesan: `detail di ${kode}, rencana dari ${[...asalSet].join("/") || "-"}` };
    if (!approved(alias)) return { ...dasar, status: "BELUM_APPROVED", pesan: `detail: ${alias || "-"}` };
    if (!groupId) return { ...dasar, status: "RESPONS_TIDAK_DIKENAL", pesan: "region.group_id kosong" };
    return { ...dasar, status: "SIAP", pesan: "" };
  }

  /** Hasil pencarian assignment-region utk tujuan -> {status, item, pesan}. */
  function nilaiWilayahTujuan(kode, data, groupId, opsi = {}) {
    if (!Array.isArray(data)) return { status: "RESPONS_TIDAK_DIKENAL", item: null, pesan: "data wilayah bukan array" };
    const cocok = data.filter((d) => d && d.smallestRegionFullCode === kode);
    if (!cocok.length) return { status: "TUJUAN_TIDAK_ADA", item: null, pesan: `wilayah ${kode} tidak ada di Progress Penyelesaian Wilayah` };
    if (cocok.length > 1) return { status: "TUJUAN_GANDA", item: null, pesan: `${cocok.length} wilayah berkode ${kode}` };
    const w = cocok[0];
    if (typeof w.doneListing !== "boolean") return { status: "RESPONS_TIDAK_DIKENAL", item: w, pesan: `doneListing=${JSON.stringify(w.doneListing)}` };
    if (groupId && w.regionGroupId && w.regionGroupId !== groupId) {
      return { status: "RESPONS_TIDAK_DIKENAL", item: w, pesan: `regionGroupId tujuan ${w.regionGroupId} != dokumen ${groupId}` };
    }
    if (w.doneListing && !opsi.izinkanTujuanSelesai) {
      return { status: "TUJUAN_BELUM_DIBUKA", item: w, pesan: "tujuan masih Listing Selesai — buka wilayah dulu (atau izinkanTujuanSelesai: true)" };
    }
    return { status: "OK", item: w, pesan: w.doneListing ? "tujuan Listing Selesai (diizinkan)" : "" };
  }

  /** Daftar user-region satu peran -> {status, petugas, pesan}. parentAllocationId utk Pencacah. */
  function pilihPetugas(peran, data, tujuan, parentAllocationId) {
    if (!Array.isArray(data)) return { status: "RESPONS_TIDAK_DIKENAL", petugas: null, pesan: `${peran}: data bukan array` };
    const valid = data.filter((x) => x && x.active !== false && x.smallestRegionCode && tujuan.startsWith(x.smallestRegionCode)
      && (parentAllocationId == null || x.parentAllocationId === parentAllocationId));
    const siapa = (x) => x.email || x.username || x.id;
    if (!valid.length) {
      return { status: "PETUGAS_TUJUAN_TIDAK_ADA", petugas: null,
        pesan: `${peran} tujuan tidak ada (${data.length} data user-region${parentAllocationId ? ", dgn induk Pengawas terpilih" : ""})` };
    }
    if (valid.length > 1) {
      return { status: "PETUGAS_TUJUAN_GANDA", petugas: null, pesan: `${valid.length} ${peran}: ${valid.map(siapa).join(", ")}` };
    }
    const p = valid[0];
    if (!p.id || !p.allocationId) return { status: "RESPONS_TIDAK_DIKENAL", petugas: null, pesan: `${peran} tanpa id/allocationId` };
    return { status: "OK", petugas: p, pesan: siapa(p) };
  }

  /** Peran Petugas dari survey-roles -> [Pengawas, Pencacah] (urut sequence) atau null kalau bentuknya lain. */
  function peranPetugas(roles) {
    const p = (roles || []).filter((r) => r && r.surveyRoleGroup && r.surveyRoleGroup.name === "Petugas")
      .sort((a, b) => a.sequence - b.sequence);
    return p.length === 2 && !p[0].isPencacah && p[1].isPencacah && p[0].id && p[1].id ? p : null;
  }

  function bodyPindah(id, tujuan, groupId, pengawas, pencacah) {
    return { assignmentIds: [id], smallestLevelFullCode: tujuan, groupId, userRegionIds: [pengawas.id, pencacah.id] };
  }

  /** Respons update-region-bulk -> {ok, status, pesan}. Halaman web menganggap gagal kalau !success. */
  function nilaiRespons(httpStatus, teks) {
    if (httpStatus === 401 || httpStatus === 403) {
      return { ok: false, status: "SESI_DITOLAK", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
    }
    const sementara = jenisSementara(httpStatus);
    if (sementara) {
      return { ok: false, status: sementara, pesan: `HTTP ${httpStatus || "gagal jaringan"}: ${String(teks || "").slice(0, 150)}` };
    }
    let j = null;
    try {
      j = JSON.parse(teks);
    } catch (e) {
      return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}, bukan JSON: ${String(teks || "").slice(0, 150)}` };
    }
    if (httpStatus >= 200 && httpStatus < 300 && j && j.success === true) return { ok: true, status: "OK", pesan: j.message || "" };
    if (j && j.success === false) return { ok: false, status: "GAGAL_PINDAH", pesan: `HTTP ${httpStatus}: ${j.message || "(tanpa pesan)"}` };
    return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}: ${String(teks || "").slice(0, 150)}` };
  }

  /** Target yang diproses: filter kunci/tujuan & lewati yang sudah tuntas oleh eksekusi. */
  function saringTarget(target, sebelumnya, o) {
    return target.filter((t) => (!o.kunci || o.kunci.includes(t.k)) && (!o.tujuan || o.tujuan.includes(t.t))
      && !(o.lewatiSelesai && sebelumnya[t.k] && JALAN_TULIS.has(sebelumnya[t.k].jalan) && STATUS_TUNTAS.has(sebelumnya[t.k].status)));
  }

  // Status peta yang dikerjakan cek/eksekusi. BELUM_APPROVED ikut: detail dicek ulang per ID, jadi
  // dokumen yang di-approve SETELAH petakan langsung terpindah tanpa memetakan ulang.
  const STATUS_PETA_DIKERJAKAN = new Set(["PERLU_PINDAH", "BELUM_APPROVED"]);

  /** Hasil rencanakan -> entri peta (disimpan; cukup utk eksekusi tanpa mencari lagi). */
  function entriPeta(t, r, waktu) {
    const it = r.item || {};
    return { k: t.k, id: it.id || "", asal: r.item ? kodeItem(it) : "", t: t.t, status: r.status,
      alias: it.assignmentStatusAlias || "", pesan: r.pesan || "", waktu };
  }

  /** Peta lama + hasil petakan baru; entri kunci yang tidak ada lagi di TARGET dibuang. */
  function gabungPeta(lama, baru, target) {
    const valid = new Set(target.map((t) => t.k));
    const hasil = {};
    for (const [k, e] of Object.entries({ ...(lama || {}), ...(baru || {}) })) if (valid.has(k)) hasil[k] = e;
    return hasil;
  }

  /** Peta -> daftar kerja [{t, r}] utk cek/eksekusi. Hanya entri ber-ID, di subsls asal & tujuan
   *  masih sama dgn TARGET sekarang (sheet input usaha bisa diekspor ulang). */
  function kerjaDariPeta(peta, target, sebelumnya, o, asal) {
    const hasil = [];
    for (const t of saringTarget(target, sebelumnya, o)) {
      const e = peta && peta[t.k];
      if (!e || !STATUS_PETA_DIKERJAKAN.has(e.status) || !e.id || !asal.has(e.asal) || e.t !== t.t) continue;
      hasil.push({ t, r: { status: e.status, pesan: e.pesan, item: { id: e.id, kode: e.asal, assignmentStatusAlias: e.alias } } });
    }
    return o.limit ? hasil.slice(0, o.limit) : hasil;
  }

  // ---- ALUR SATUAN (mode cari / pindah): per dokumen cari -> detail -> tujuan -> pindah -> verifikasi ----

  /** "5108060014000403 - Praktek Dokter (X)" -> "PRAKTEK DOKTER (X)" (awalan kode 16 digit dibuang, dinormalkan). */
  function namaDariKode(teks) {
    return norm(String(teks == null ? "" : teks).replace(/^\s*\d{16}\s*-\s*/, ""));
  }

  /** Nama yang sah utk satu target: nama dokumen sheet input usaha + nama lama di audit (`na`). */
  function namaTarget(t) {
    return [...new Set([t && t.n, ...((t && t.na) || [])].map(norm).filter(Boolean))];
  }

  /** Nama dokumen menurut item datatable (data1 & codeIdentity) atau detail (data1 & code_identity). */
  function namaItem(it) {
    return [...new Set([it && it.data1, it && (it.codeIdentity || it.code_identity)].filter(Boolean).map(namaDariKode).filter(Boolean))];
  }
  const namaDetail = namaItem;
  const namaCocok = (namaServer, namaSah) => (namaServer || []).some((n) => (namaSah || []).includes(n));

  /** Istilah pencarian, dicoba berurutan sampai dokumennya tampil: nama sheet, nama lama, lalu kode
   *  identitas "<subsls asal> - <nama>". */
  function istilahCariDokumen(t) {
    const nama = namaTarget(t);
    const kode = ((t && t.a) || []).filter((a) => KODE_VALID.test(a)).flatMap((a) => nama.map((n) => `${a} - ${n}`));
    return [...new Set([...nama, ...kode])];
  }

  /** Subsls asal satu target: `a` dari audit kalau ada, selain itu seluruh ASAL. */
  function asalUntuk(t, asalGlobal) {
    return new Set(t && t.a && t.a.length ? t.a : asalGlobal || []);
  }

  /** Satu hasil pencarian datatable -> {status: KETEMU | TIDAK_TAMPIL | BELUM_APPROVED | DOKUMEN_GANDA, item, namaCocok, pesan}.
   *  Target ber-ID (approve) dicocokkan HANYA lewat ID. Tanpa ID: nama persis (bukan prelist), tepat 1 APPROVED.
   *  Dokumen lain bernama sama cuma dilaporkan — tidak pernah dipilih. */
  function nilaiPencarian(t, items) {
    const nama = namaTarget(t);
    const ids = (t && t.ids) || [];
    const unik = [...new Map((items || []).filter((it) => it && it.id).map((it) => [it.id, it])).values()];
    const bernama = unik.filter((it) => !POLA_PRELIST.test(it.codeIdentity || "") && namaCocok(namaItem(it), nama));
    const ringkas = (arr) => arr.map((it) => `${it.id.slice(0, 8)} ${kodeItem(it) || "?"} ${it.assignmentStatusAlias || "?"}`).join("; ");
    if (ids.length) {
      const pilih = unik.filter((it) => ids.includes(it.id));
      const lain = bernama.filter((it) => !ids.includes(it.id));
      const pesan = lain.length ? `dokumen lain bernama sama (TIDAK dipindah): ${ringkas(lain)}` : "";
      if (!pilih.length) return { status: "TIDAK_TAMPIL", item: null, namaCocok: false, pesan };
      if (pilih.length > 1) return { status: "DOKUMEN_GANDA", item: null, namaCocok: false, pesan: `${pilih.length} ID target tampil: ${ringkas(pilih)}` };
      return { status: "KETEMU", item: pilih[0], namaCocok: namaCocok(namaItem(pilih[0]), nama), pesan };
    }
    if (!bernama.length) return { status: "TIDAK_TAMPIL", item: null, namaCocok: false, pesan: "" };
    const ok = bernama.filter((it) => approved(it.assignmentStatusAlias));
    if (!ok.length) return { status: "BELUM_APPROVED", item: bernama[0], namaCocok: true, pesan: ringkas(bernama) };
    if (ok.length > 1) return { status: "DOKUMEN_GANDA", item: null, namaCocok: true, pesan: `${ok.length} dokumen APPROVED: ${ringkas(ok)}` };
    const lain = bernama.filter((it) => it !== ok[0]);
    return { status: "KETEMU", item: ok[0], namaCocok: true, pesan: lain.length ? `dokumen lain (bukan APPROVED): ${ringkas(lain)}` : "" };
  }

  /** Pengali jeda pencarian: x2 tiap pencarian yang kena galat sementara (maks 8), x0,8 tiap sukses (min 1). */
  function faktorJeda(faktor, adaGalat) {
    return adaGalat ? Math.min(8, faktor * 2) : Math.max(1, Math.round(faktor * 800) / 1000);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, ASAL, STATUS_BERHENTI_SEGERA, STATUS_TUNTAS, STATUS_SEMENTARA, BATAS_ULANG_429, halamanData, norm, approved,
      jedaRateLimit, jenisSementara, gagalDihitung, ringkasItem, kodeSubsls, kodeItem, indeksItem,
      kodeLevel, levelWilayah, jalurLevel, bedaLevel,
      rencanakan, tidakDikenali, nilaiDetail, nilaiWilayahTujuan, pilihPetugas, peranPetugas, bodyPindah, nilaiRespons,
      saringTarget, STATUS_PETA_DIKERJAKAN, entriPeta, gabungPeta, kerjaDariPeta,
      namaDariKode, namaTarget, namaItem, namaCocok, istilahCariDokumen, asalUntuk, nilaiPencarian, faktorJeda,
    };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "pindahWilayah.hasil.v1";
  const KUNCI_CACHE_NAMA = "pindahWilayah.cariNama.v1";
  const KUNCI_PETA = "pindahWilayah.peta.v1";
  const API = "/app/api";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const log = (...a) => console.log("%c[pindahWilayah]", "color:#2e7d32;font-weight:bold", ...a);

  let hentikan = false;
  let berjalan = false;

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "pindahWilayah.berhenti() dipanggil");
  }

  /** sleep yang tetap bisa dihentikan pindahWilayah.berhenti() (dicek tiap detik). */
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

  // Jarak minimal antar-request skrip ini (di atas jeda per langkah) — rate limit fasih-sm.
  const JARAK_MIN_REQUEST_MS = 500;
  let requestTerakhir = 0;

  async function minta(method, url, body) {
    const tunggu = requestTerakhir + JARAK_MIN_REQUEST_MS - Date.now();
    if (tunggu > 0) await sleep(tunggu);
    requestTerakhir = Date.now();
    const init = { method, credentials: "include", headers: { "X-XSRF-TOKEN": xsrf() } };
    if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(API + url, init);
      return { status: res.status, teks: await res.text(), retryAfter: res.headers.get("Retry-After") };
    } catch (e) {
      // Jaringan/VPN putus sesaat -> status 0 = galat sementara (jenisSementara).
      return { status: 0, teks: `fetch gagal: ${e && e.message ? e.message : e}`, retryAfter: null };
    }
  }

  /** Request BACA: galat sementara (429, 502/503/504, jaringan) ditunggu & diulang (maks `opsi.ulang`,
   *  default BATAS_ULANG_429) lalu Berhenti RATE_LIMIT / SERVER_SIBUK; 401/403 & bukan-JSON -> Berhenti.
   *  `opsi.saatGalat(jenis)` dipanggil tiap galat sementara. Jangan dipakai utk request tulis. */
  async function bacaJson(method, url, body, opsi = {}) {
    const batas = opsi.ulang == null ? BATAS_ULANG_429 : opsi.ulang;
    const ujung = url.split("?")[0];
    let r;
    for (let ke = 0; ; ke++) {
      r = await minta(method, url, body);
      const jenis = jenisSementara(r.status);
      if (!jenis) break;
      if (opsi.saatGalat) opsi.saatGalat(jenis);
      const http = r.status ? `HTTP ${r.status}` : "gagal jaringan";
      if (ke >= batas) throw new Berhenti(jenis, `${ujung} masih ${http} setelah ${ke} kali menunggu — coba lagi nanti`);
      const tunggu = jedaRateLimit(ke, r.retryAfter);
      log(`⏳ ${http} (${jenis === "RATE_LIMIT" ? "rate limit" : "server sibuk"}) di ${ujung} — tunggu ${Math.round(tunggu / 1000)} dtk (ulang ${ke + 1}/${batas})`);
      await tidur(tunggu);
    }
    const { status, teks } = r;
    if (status === 401 || status === 403) throw new Berhenti("SESI_DITOLAK", `${ujung} HTTP ${status}: ${teks.slice(0, 150)}`);
    try {
      return { status, j: JSON.parse(teks) };
    } catch (e) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `${ujung} HTTP ${status}, bukan JSON: ${teks.slice(0, 150)}`);
    }
  }

  const qs = (o) => Object.entries(o).filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");

  async function datatableAssignment(periode, cari, start, length, opsi) {
    const { status, j } = await bacaJson("POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode", {
      draw: 1, start, length,
      columns: ["id", "codeIdentity", "data1", "data2", "data3", "data4", "data5", "data6", "data7", "data8", "data9", "data10"]
        .map((data) => ({ data, orderable: true })),
      order: [], search: { value: cari, regex: false },
      assignmentExtraParam: { surveyPeriodId: periode, assignmentErrorStatusType: -1, assignmentStatusAlias: null },
    }, opsi);
    if (status !== 200 || !j || !Array.isArray(j.searchData) || typeof j.totalHit !== "number") {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable assignment HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j;
  }

  /** Semua assignment di satu subsls (halaman 150, offset). Dibaca ulang sekali kalau jumlah id unik kurang. */
  async function pindaiSubsls(periode, kode) {
    let terbaik = new Map();
    let total = 0;
    for (let putaran = 1; putaran <= 2; putaran++) {
      const peta = new Map();
      for (let start = 0; ; start += 150) {
        cekHenti();
        const j = await datatableAssignment(periode, kode, start, 150);
        total = j.totalHit;
        for (const it of j.searchData) if (it && it.id && kodeItem(it) === kode) peta.set(it.id, it);
        if (!j.searchData.length || start + 150 >= total) break;
        await tidur(acak(700, 1400));
      }
      if (peta.size > terbaik.size) terbaik = peta;
      log(`Pindai ${kode}: ${peta.size} assignment (totalHit ${total}, putaran ${putaran})`);
      if (peta.size >= total) break;
    }
    return [...terbaik.values()];
  }

  function muatCacheNama(umurJam) {
    let c = {};
    try {
      c = JSON.parse(localStorage.getItem(KUNCI_CACHE_NAMA) || "{}");
    } catch (e) {
      c = {};
    }
    const batas = Date.now() - umurJam * 3600 * 1000;
    return Object.fromEntries(Object.entries(c).filter(([, v]) => v && v.waktu >= batas && Array.isArray(v.items)));
  }

  /** Pencarian nama -> item ringkas. Hasil (termasuk "tidak ada") disimpan supaya
   *  run berikutnya / run yang terputus 429 tidak mengulang dari awal. */
  async function cariNama(periode, nama, cache) {
    if (cache[nama]) return { items: cache[nama].items, dariCache: true };
    const items = (await datatableAssignment(periode, nama, 0, 50)).searchData
      .filter((it) => it && norm(it.data1) === nama).map(ringkasItem);
    cache[nama] = { waktu: Date.now(), items };
    try {
      localStorage.setItem(KUNCI_CACHE_NAMA, JSON.stringify(cache));
    } catch (e) {
      // cache hanya penghemat request; gagal simpan tidak fatal
    }
    return { items, dariCache: false };
  }

  async function detail(id) {
    return (await bacaJson("GET", `/assignment-general/api/assignment/get-by-assignment-id?${qs({ assignmentId: id })}`)).j;
  }

  async function wilayahTujuan(periode, kode) {
    const { status, j } = await bacaJson("POST", `/assignment-general/api/assignment-region/datatable?${qs({ periodeId: periode })}`,
      { start: 0, length: 10, search: { value: kode, regex: true }, order: [{ column: 0, dir: "asc" }] });
    if (status !== 200 || !j || !Array.isArray(j.data)) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable wilayah HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j.data;
  }

  async function userRegion(periode, peran, kode, parentAllocationId) {
    const { status, j } = await bacaJson("GET", `/survey-user/api/v1/user-region/region?${qs({
      surveyPeriodId: periode, surveyRoleId: peran.id, regionCode: kode, parentAllocationId })}`);
    if (status !== 200 || !j || j.success !== true) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `user-region HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j.data;
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
    const lama = semua[entri.kunci];
    // Bukti pindah sungguhan tidak boleh tertimpa hasil cek/rencana berikutnya.
    if (lama && lama.status === "DIPINDAH_TERVERIFIKASI" && entri.status !== "DIPINDAH_TERVERIFIKASI") return;
    semua[entri.kunci] = entri;
    try {
      localStorage.setItem(KUNCI_HASIL, JSON.stringify(semua));
    } catch (e) {
      log("⚠️ localStorage penuh/terkunci — segera pindahWilayah.unduh()", e);
    }
  }

  function muatPeta() {
    try {
      return JSON.parse(localStorage.getItem(KUNCI_PETA) || "null");
    } catch (e) {
      return null;
    }
  }

  function hasilDasar(t, r, mode) {
    const it = r.item || {};
    return { waktu: new Date().toISOString(), jalan: mode, kunci: t.k, sumber: t.s, baris: t.b, nama: t.n,
      id: it.id || "", status_server: it.assignmentStatusAlias || "", asal: r.item ? kodeItem(it) : "", tujuan: t.t,
      status: r.status, pengawas: "", pencacah: "", ppl_agenda: t.p || "", ppl_cocok_agenda: "", pesan: r.pesan || "" };
  }

  /** Cek tujuan & petugas sekali per subsls tujuan per run. */
  async function siapkanTujuan(cache, ctx, kode, groupId, o) {
    const kunciCache = `${kode}|${groupId}`;
    if (cache.has(kunciCache)) return cache.get(kunciCache);
    const w = nilaiWilayahTujuan(kode, await wilayahTujuan(ctx.periode, kode), groupId, o);
    let hasil = { status: w.status, pesan: w.pesan };
    if (w.status === "OK") {
      const pw = pilihPetugas("Pengawas", await userRegion(ctx.periode, ctx.peran[0], kode), kode);
      if (pw.status !== "OK") {
        hasil = pw;
      } else {
        const pc = pilihPetugas("Pencacah", await userRegion(ctx.periode, ctx.peran[1], kode, pw.petugas.allocationId), kode,
          pw.petugas.allocationId);
        hasil = pc.status !== "OK" ? pc
          : { status: "OK", pengawas: pw.petugas, pencacah: pc.petugas, pesan: [w.pesan, `PML ${pw.pesan}, PPL ${pc.pesan}`].filter(Boolean).join(" | ") };
      }
    }
    cache.set(kunciCache, hasil);
    return hasil;
  }

  async function prosesPindah(t, r, ctx, cache, o) {
    const hasil = hasilDasar(t, r, o.mode);
    const asal = hasil.asal;
    try {
      cekHenti();
      const d = nilaiDetail(await detail(r.item.id), asal, t.t);
      if (d.alias) hasil.status_server = d.alias;
      if (d.status !== "SIAP") return Object.assign(hasil, { status: d.status, pesan: d.pesan });

      const tj = await siapkanTujuan(cache, ctx, t.t, d.groupId, o);
      if (tj.status !== "OK") return Object.assign(hasil, { status: tj.status, pesan: tj.pesan });
      const siapa = (p) => p.email || p.username || p.id;
      Object.assign(hasil, { pengawas: siapa(tj.pengawas), pencacah: siapa(tj.pencacah), pesan: tj.pesan });
      hasil.ppl_cocok_agenda = t.p ? String(t.p === String(siapa(tj.pencacah)).toLowerCase() ? "YA" : "TIDAK") : "";
      if (o.mode === "cek") return Object.assign(hasil, { status: "CEK_SIAP_PINDAH" });

      cekHenti();
      hasil.dikirim = true;
      const k = await kirimDanVerifikasi(r.item.id, asal, t.t, d, tj);
      if (k.alias) hasil.status_server = k.alias;
      return Object.assign(hasil, { status: k.status, pesan: [k.pesan, hasil.pesan].filter(Boolean).join(" | ") });
    } catch (e) {
      hasil.status = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      hasil.pesan = `${hasil.pesan ? hasil.pesan + " | " : ""}${e && e.message ? e.message : e}`;
      if (!(e instanceof Berhenti)) console.error(e);
      return hasil;
    }
  }

  /** IRREVERSIBLE oleh skrip ini (bisa dipindah balik manual lewat menu yang sama).
   *  PUT update-region-bulk 1 dokumen -> detail dibaca ulang: subsls = tujuan, SEMUA level provinsi..subsls =
   *  awalan kode tujuan, status tetap APPROVED. Galat sementara (429/502/503/504/jaringan) TIDAK dikirim ulang
   *  buta: tunggu, baca detail, kirim ulang hanya kalau masih SIAP di asal. -> {status, pesan, alias}. */
  async function kirimDanVerifikasi(id, asal, tujuan, d, tj) {
    let n = null;
    for (let ke = 0; ; ke++) {
      const kirim = await minta("PUT", "/assignment-general/api/assignment/update-region-bulk",
        bodyPindah(id, tujuan, d.groupId, tj.pengawas, tj.pencacah));
      n = nilaiRespons(kirim.status, kirim.teks);
      if (!STATUS_SEMENTARA.has(n.status)) break;
      const tunggu = jedaRateLimit(ke, kirim.retryAfter);
      log(`⏳ ${n.pesan.slice(0, 40)} saat memindah ${id.slice(0, 8)} — tunggu ${Math.round(tunggu / 1000)} dtk, cek detail dulu`);
      await sleep(tunggu); // sengaja tidak bisa dihentikan: status dokumen harus diketahui dulu
      let ulang;
      try {
        ulang = nilaiDetail(await detail(id), asal, tujuan);
      } catch (e) {
        if (!(e instanceof Berhenti)) throw e;
        return { status: "DIPINDAH_BELUM_TERVERIFIKASI", pesan: `setelah ${n.status}: detail tidak terbaca (${e.kode}) — cek manual dokumen ini` };
      }
      if (ulang.status === "SUDAH_DI_TUJUAN") {
        n = { ok: true, status: "OK", pesan: `${n.status}, tapi detail sudah di tujuan` };
        break;
      }
      if (ulang.status !== "SIAP") return { status: ulang.status, pesan: `setelah ${n.status}: ${ulang.pesan}`, alias: ulang.alias };
      if (ke >= BATAS_ULANG_429) return { status: n.status, pesan: `${n.pesan} — dokumen masih di asal setelah ${ke + 1}x kirim` };
      cekHenti(); // dokumen terbukti masih di asal -> aman berhenti di sini
    }
    if (!n.ok) return { status: n.status, pesan: n.pesan };

    let v = null;
    for (let ke = 1; ke <= 3; ke++) {
      await sleep(1500 * ke);
      try {
        v = nilaiDetail(await detail(id), asal, tujuan);
      } catch (e) {
        if (!(e instanceof Berhenti)) throw e;
        v = { status: "TIDAK_TERBACA", kode: "", pesan: `${e.kode}: ${e.message}` };
      }
      if (v.status === "SUDAH_DI_TUJUAN") break;
    }
    if (v.status !== "SUDAH_DI_TUJUAN") {
      return { status: "DIPINDAH_BELUM_TERVERIFIKASI", alias: v.alias,
        pesan: `respons: ${n.pesan || "success"} | detail ${v.kode ? `masih ${v.kode}` : "tidak terbaca"} (${v.status}${v.kode ? "" : `: ${v.pesan}`}) setelah 3x cek` };
    }
    const beda = bedaLevel(v.level, tujuan);
    if (beda.length) {
      return { status: "DIPINDAH_LEVEL_BEDA", alias: v.alias, pesan: `subsls sudah = tujuan tapi level wilayah beda: ${beda.join("; ")} — cek manual` };
    }
    if (!approved(v.alias)) {
      return { status: "DIPINDAH_STATUS_BERUBAH", alias: v.alias,
        pesan: `pindah OK tapi status jadi '${v.alias}' (sebelumnya '${d.alias}') — cek dampaknya sebelum lanjut` };
    }
    return { status: "DIPINDAH_TERVERIFIKASI", alias: v.alias,
      pesan: `respons: ${n.pesan || "success"} | wilayah ${jalurLevel(tujuan)} terverifikasi | pengguna saat ini: ${v.pengguna || "-"}` };
  }

  // Jeda pencarian adaptif (datatable analytic paling rawan 429/504): pengali naik saat galat, turun saat sukses.
  let faktorCari = 1;
  let cariTerakhir = 0;

  /** Satu pencarian (satu istilah) -> searchData. Galat sementara diulang `o.ulangCari` kali lalu Berhenti. */
  async function cariDokumen(periode, istilah, o) {
    const tunggu = cariTerakhir + Math.round(acak(o.jedaCariMin, o.jedaCariMaks) * faktorCari) - Date.now();
    if (tunggu > 0) await tidur(tunggu);
    let adaGalat = false;
    try {
      return (await datatableAssignment(periode, istilah, 0, 50, { ulang: o.ulangCari, saatGalat: () => { adaGalat = true; } })).searchData;
    } finally {
      cariTerakhir = Date.now();
      const lama = faktorCari;
      faktorCari = faktorJeda(faktorCari, adaGalat);
      if (faktorCari > lama) log(`Jeda antar-pencarian dinaikkan jadi x${faktorCari} (server sibuk / rate limit)`);
    }
  }

  /** ALUR SATUAN — satu dokumen diselesaikan utuh sebelum dokumen berikutnya:
   *  1) CARI lewat nama, nama lama, lalu kode identitas "<asal> - <nama>" (berhenti di istilah pertama yang
   *     menampilkan dokumennya). Pencarian gagal sementara + ID approve diketahui -> lanjut lewat detail ID.
   *  2) DETAIL segar: nama cocok, masih di subsls asal, APPROVED.
   *  3) TUJUAN: wilayah provinsi..subsls ada & dibuka, PML+PPL tepat 1+1.   (mode "cari" berhenti di sini)
   *  4) PINDAH + verifikasi semua level wilayah (kirimDanVerifikasi). */
  async function prosesSatuan(t, ctx, cache, o) {
    const ids = t.ids || [];
    const hasil = { waktu: new Date().toISOString(), jalan: o.mode, kunci: t.k, sumber: t.s, baris: t.b, nama: t.n,
      id: ids.length === 1 ? ids[0] : "", status_server: "", asal: "", tujuan: t.t, status: "", pengawas: "", pencacah: "",
      ppl_agenda: t.p || "", ppl_cocok_agenda: "", cara: "", pesan: "" };
    const catatan = [];
    const selesai = (status, pesan) => {
      if (pesan) catatan.push(pesan);
      return Object.assign(hasil, { status, pesan: catatan.join(" | ") });
    };
    try {
      if (!KODE_VALID.test(t.t || "")) return selesai("TUJUAN_TIDAK_VALID", `tujuan '${t.t}'`);
      if (ids.length > 1) return selesai("DOKUMEN_GANDA", `${ids.length} id dokumen utk satu baris: ${ids.map((i) => i.slice(0, 8)).join(", ")}`);
      if (!ids.length && t.g) return selesai("NAMA_GANDA_DI_AGENDA", "nama dokumen dipakai >1 baris input usaha & tidak ada ID");

      // 1. CARI satu per satu
      const istilah = istilahCariDokumen(t);
      let temu = null;
      let galatCari = null;
      for (const q of o.pakaiPencarian ? istilah : []) {
        cekHenti();
        let items;
        try {
          items = await cariDokumen(ctx.periode, q, o);
        } catch (e) {
          if (!(e instanceof Berhenti && STATUS_SEMENTARA.has(e.kode))) throw e;
          galatCari = e;
          break;
        }
        const r = nilaiPencarian(t, items);
        if (r.pesan) catatan.push(`cari "${q}": ${r.pesan}`);
        if (r.status === "TIDAK_TAMPIL") continue;
        if (r.status !== "KETEMU") {
          if (r.item) Object.assign(hasil, { id: r.item.id, status_server: r.item.assignmentStatusAlias || "", asal: kodeItem(r.item) });
          return selesai(r.status);
        }
        temu = { ...r, q };
        break;
      }
      const id = temu ? temu.item.id : ids[0];
      if (!id) {
        return galatCari ? selesai("PENCARIAN_GAGAL", `${galatCari.kode}: ${galatCari.message}`)
          : selesai("DOKUMEN_TIDAK_DITEMUKAN", `tidak tampil di pencarian: ${istilah.join(" / ")}`);
      }
      hasil.id = id;
      hasil.cara = temu ? `cari: ${temu.q}` : galatCari ? `detail ID (pencarian ${galatCari.kode})`
        : o.pakaiPencarian ? "detail ID (tidak tampil di pencarian)" : "detail ID (tanpa pencarian)";

      // 2. DETAIL segar (sumber primer)
      cekHenti();
      const asal = asalUntuk(t, ASAL);
      const d = nilaiDetail(await detail(id), asal, t.t);
      if (d.alias) hasil.status_server = d.alias;
      if (d.kode) hasil.asal = d.kode;
      if (d.status === "RESPONS_TIDAK_DIKENAL") return selesai(d.status, d.pesan);
      if (!(temu && temu.namaCocok) && !namaCocok(d.nama, namaTarget(t))) {
        return selesai("NAMA_TIDAK_COCOK", `nama di server: ${(d.nama || []).join(" / ") || "-"} | sheet input usaha: ${namaTarget(t).join(" / ")}`);
      }
      if (d.status === "SUDAH_DI_TUJUAN") {
        const beda = bedaLevel(d.level, t.t);
        return beda.length ? selesai("RESPONS_TIDAK_DIKENAL", `subsls = tujuan tapi level wilayah beda: ${beda.join("; ")}`)
          : selesai(d.status, d.pesan);
      }
      if (d.status !== "SIAP") return selesai(d.status, d.pesan);

      // 3. TUJUAN provinsi..subsls + petugas
      const tj = await siapkanTujuan(cache, ctx, t.t, d.groupId, o);
      if (tj.status !== "OK") return selesai(tj.status, tj.pesan);
      const siapa = (p) => p.email || p.username || p.id;
      Object.assign(hasil, { pengawas: siapa(tj.pengawas), pencacah: siapa(tj.pencacah) });
      hasil.ppl_cocok_agenda = t.p ? (t.p === String(siapa(tj.pencacah)).toLowerCase() ? "YA" : "TIDAK") : "";
      catatan.push(tj.pesan);
      if (o.mode === "cari") return selesai("CEK_SIAP_PINDAH", `${d.kode} -> ${jalurLevel(t.t)}`);

      // 4. PINDAH + verifikasi
      cekHenti();
      hasil.dikirim = true;
      const k = await kirimDanVerifikasi(id, asal, t.t, d, tj);
      if (k.alias) hasil.status_server = k.alias;
      return selesai(k.status, k.pesan);
    } catch (e) {
      if (!(e instanceof Berhenti)) console.error(e);
      return selesai(e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA", e && e.message ? e.message : String(e));
    }
  }

  async function jalankanSatuan(ctx, daftar, sebelumnya, o, tambah) {
    if (o.mode === "pindah") {
      const adaBukti = Object.values(sebelumnya).some((h) => h.status === "DIPINDAH_TERVERIFIKASI");
      if (!o.limit && !adaBukti) {
        log("Pindah massal butuh minimal 1 DIPINDAH_TERVERIFIKASI dulu. Jalankan: "
          + 'await pindahWilayah.jalankan({mode: "pindah", limit: 1}) lalu cek dokumennya di fasih-sm.');
        return;
      }
      if (prompt(`PINDAH WILAYAH SUNGGUHAN, satu per satu: maks. ${o.limit || daftar.length} dokumen dipindah `
        + `(dari ${daftar.length} baris; petugas = PML+PPL subsls tujuan).\nKetik YA untuk lanjut:`) !== "YA") {
        log("Dibatalkan.");
        return;
      }
    }
    log(`${o.mode === "cari" ? "CARI (READ-ONLY)" : "PINDAH"} satu per satu: ${daftar.length} baris`
      + (o.limit ? `, berhenti setelah ${o.limit} dokumen ${o.mode === "cari" ? "diperiksa" : "dipindah"}` : ""));
    const cache = new Map();
    let gagalBeruntun = 0;
    let diperiksa = 0;
    let dikirim = 0;
    for (let i = 0; i < daftar.length; i++) {
      if (o.limit && (o.mode === "cari" ? diperiksa : dikirim) >= o.limit) break;
      const t = daftar[i];
      const hasil = await prosesSatuan(t, ctx, cache, o);
      diperiksa++;
      if (hasil.dikirim) dikirim++;
      simpanHasil(hasil);
      tambah(hasil.status);
      log(`[${i + 1}/${daftar.length}] ${t.s}:${t.b} ${String(hasil.id || "-").slice(0, 8)} ${hasil.asal || "?"} -> ${t.t} -> ${hasil.status}`
        + (hasil.cara ? ` (${hasil.cara})` : ""), hasil.pesan);
      if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
        log(`⛔ ${hasil.status} — batch DIHENTIKAN. Periksa sebelum menjalankan ulang.`);
        break;
      }
      gagalBeruntun = gagalDihitung(hasil.status) ? gagalBeruntun + 1 : 0;
      if (gagalBeruntun >= 3) {
        log(`⛔ 3 kegagalan berturut-turut (terakhir ${hasil.status}) — batch DIHENTIKAN. Jalankan lagi nanti; yang tuntas dilewati.`);
        break;
      }
      if (i < daftar.length - 1) await tidur(hasil.dikirim ? acak(o.jedaMin, o.jedaMaks) : acak(300, 800));
    }
  }

  /** Pindai subsls asal (+ cari per nama utk yang belum ketemu) -> rencana per target. */
  async function susunRencana(ctx, daftar, o) {
    const asal = new Set(ASAL);
    const items = [];
    for (const kode of ASAL) items.push(...await pindaiSubsls(ctx.periode, kode));
    let idx = indeksItem(items);
    let rencana = daftar.map((t) => ({ t, r: rencanakan(t, idx, asal) }));
    const sisa = rencana.filter((x) => x.r.status === "DOKUMEN_TIDAK_DITEMUKAN");
    if (o.cariPerNama && sisa.length) {
      const cache = muatCacheNama(o.umurCacheNamaJam);
      const baru = sisa.filter((x) => !cache[x.t.n]).length;
      log(`Mencari ${sisa.length} dokumen yang tidak ada di subsls asal lewat nama (${sisa.length - baru} dari cache, `
        + `${baru} request ±${Math.ceil(baru * 2.2 / 60)} menit)...`);
      let dicari = 0;
      try {
        for (let i = 0; i < sisa.length; i++) {
          cekHenti();
          const h = await cariNama(ctx.periode, sisa[i].t.n, cache);
          items.push(...h.items);
          if ((i + 1) % 25 === 0) log(`  cari nama ${i + 1}/${sisa.length}`);
          if (!h.dariCache) {
            dicari++;
            await tidur(acak(o.jedaNamaMin, o.jedaNamaMaks));
          }
        }
      } catch (e) {
        if (!(e instanceof Berhenti && STATUS_SEMENTARA.has(e.kode))) throw e;
        // Hanya baris yang belum dicari yang tetap DOKUMEN_TIDAK_DITEMUKAN; rencana baris lain tidak
        // terpengaruh (item hasil cari nama hanya cocok ke baris bernama sama, yang ditandai `g`).
        log(`⚠️ Pencarian nama dihentikan (${e.message}). ${dicari} nama tercari & tersimpan di cache; `
          + "sisanya tetap DOKUMEN_TIDAK_DITEMUKAN di run ini — jalankan lagi nanti utk melanjutkan.");
      }
      idx = indeksItem(items);
      rencana = daftar.map((t) => ({ t, r: rencanakan(t, idx, asal) }));
    }
    const asing = tidakDikenali(items, rencana.map((x) => x.r), asal);
    return { rencana, asing };
  }

  /** TAHAP 1 (READ-ONLY): pindai subsls asal + cari nama -> peta kunci -> {id, asal, tujuan, status}. */
  async function petakan(ctx, daftar, o, tambah) {
    log(`Memetakan ${daftar.length} baris input usaha dari ${ASAL.length} subsls asal...`);
    const { rencana, asing } = await susunRencana(ctx, daftar, o);
    global.pindahWilayah.rencanaTerakhir = rencana;
    global.pindahWilayah.tidakDikenali = asing;
    const waktu = new Date().toISOString();
    const baru = {};
    for (const { t, r } of rencana) {
      baru[t.k] = entriPeta(t, r, waktu);
      simpanHasil({ ...hasilDasar(t, r, "petakan"), waktu });
      tambah(r.status);
    }
    const lama = muatPeta();
    const peta = { waktu, entri: gabungPeta(lama && lama.entri, baru, TARGET) };
    try {
      localStorage.setItem(KUNCI_PETA, JSON.stringify(peta));
    } catch (e) {
      log("⚠️ Peta gagal disimpan di localStorage — cek/eksekusi tidak bisa memakainya", e);
    }
    const siap = Object.values(peta.entri).filter((e) => STATUS_PETA_DIKERJAKAN.has(e.status) && e.id).length;
    if (asing.length) {
      log(`⚠️ ${asing.length} dokumen APPROVED di subsls asal tidak cocok dgn baris input usaha mana pun (TIDAK dipindah): pindahWilayah.tidakDikenali`);
    }
    log(`Peta tersimpan: ${Object.keys(peta.entri).length} baris, ${siap} siap dikerjakan (PERLU_PINDAH + BELUM_APPROVED). `
      + 'Lanjut: await pindahWilayah.jalankan({mode: "cek", limit: 20})');
  }

  async function jalankan(opsi = {}) {
    const o = { mode: "cari", limit: null, tujuan: null, kunci: null, lewatiSelesai: true, cariPerNama: true,
      izinkanTujuanSelesai: false, jedaMin: 2000, jedaMaks: 4000, jedaNamaMin: 1500, jedaNamaMaks: 3000,
      umurCacheNamaJam: 12, pakaiPencarian: true, jedaCariMin: 2500, jedaCariMaks: 4500, ulangCari: 2, ...opsi };
    const MODE = ["cari", "pindah", "petakan", "cek", "eksekusi"];
    if (!MODE.includes(o.mode)) return log(`mode '${o.mode}' tidak dikenal (${MODE.join(" | ")})`);
    const satuan = o.mode === "cari" || o.mode === "pindah";
    if (berjalan) return log("Masih berjalan — tunggu selesai atau pindahWilayah.berhenti().");
    if (!TARGET.length || !ASAL.length) return log("TARGET/ASAL kosong — tempel pindah_wilayah_console.siap.js, bukan template.");
    const hal = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !hal) {
      return log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
    }

    const sebelumnya = muatHasil();
    let kerja = [];
    if (satuan) {
      kerja = saringTarget(TARGET, sebelumnya, o);
      if (!kerja.length) return log("Tidak ada baris yang perlu diproses (yang tuntas oleh mode pindah/eksekusi dilewati).");
    } else if (o.mode !== "petakan") {
      const peta = muatPeta();
      if (!peta || !peta.entri) return log('Belum ada peta di browser ini. Jalankan dulu: await pindahWilayah.jalankan({mode: "petakan"})');
      kerja = kerjaDariPeta(peta.entri, TARGET, sebelumnya, o, new Set(ASAL));
      const umurJam = (Date.now() - Date.parse(peta.waktu)) / 3600000;
      log(`Peta dari ${peta.waktu} (${umurJam.toFixed(1)} jam lalu): ${kerja.length} dokumen dikerjakan per ID, tanpa pencarian. `
        + "Baris yang belum ketemu saat dipetakan tidak ikut — petakan lagi utk memperbaruinya.");
      if (!kerja.length) return log("Tidak ada dokumen yang perlu diproses.");
    }

    berjalan = true;
    hentikan = false;
    const hitung = {};
    const tambah = (s) => { hitung[s] = (hitung[s] || 0) + 1; };
    try {
      if (o.mode === "petakan") {
        const daftar = saringTarget(TARGET, sebelumnya, o);
        if (!daftar.length) return log("Tidak ada baris input usaha yang perlu dipetakan.");
        await petakan(hal, daftar, o, tambah);
        return hitung;
      }
      const roles = await bacaJson("GET", `/survey/api/v1/survey-roles?${qs({ surveyId: hal.survei })}`);
      const peran = peranPetugas(roles.j && roles.j.data);
      if (!peran) throw new Berhenti("RESPONS_TIDAK_DIKENAL", "peran Petugas bukan tepat [Pengawas, Pencacah]");
      const ctx = { ...hal, peran };
      if (satuan) {
        await jalankanSatuan(ctx, kerja, sebelumnya, o, tambah);
        return hitung;
      }

      if (o.mode === "eksekusi" && kerja.length) {
        const adaBukti = Object.values(sebelumnya).some((h) => h.status === "DIPINDAH_TERVERIFIKASI");
        if (!o.limit && !adaBukti) {
          log("Eksekusi massal butuh minimal 1 DIPINDAH_TERVERIFIKASI dulu. Jalankan: "
            + 'await pindahWilayah.jalankan({mode: "eksekusi", limit: 1}) lalu cek dokumennya di fasih-sm.');
          return hitung;
        }
        if (prompt(`PINDAH WILAYAH SUNGGUHAN utk maks. ${kerja.length} dokumen (petugas = PML+PPL subsls tujuan).\nKetik YA untuk lanjut:`) !== "YA") {
          log("Dibatalkan.");
          return hitung;
        }
      }

      const cache = new Map();
      let gagalBeruntun = 0;
      for (let i = 0; i < kerja.length; i++) {
        const { t, r } = kerja[i];
        const hasil = await prosesPindah(t, r, ctx, cache, o);
        simpanHasil(hasil);
        tambah(hasil.status);
        log(`[${i + 1}/${kerja.length}] ${t.s}:${t.b} ${hasil.id.slice(0, 8)} ${hasil.asal} -> ${t.t} -> ${hasil.status}`, hasil.pesan);
        if (STATUS_BERHENTI_SEGERA.has(hasil.status)) {
          log(`⛔ ${hasil.status} — batch DIHENTIKAN. Periksa sebelum menjalankan ulang.`);
          break;
        }
        gagalBeruntun = gagalDihitung(hasil.status) ? gagalBeruntun + 1 : 0;
        if (gagalBeruntun >= 3) {
          log(`⛔ 3 kegagalan berturut-turut (terakhir ${hasil.status}) — batch DIHENTIKAN.`);
          break;
        }
        if (i < kerja.length - 1) await tidur(hasil.dikirim ? acak(o.jedaMin, o.jedaMaks) : acak(800, 1500));
      }
    } catch (e) {
      const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
      if (!(e instanceof Berhenti)) console.error(e);
    } finally {
      berjalan = false;
      console.table(hitung);
      log("Selesai. pindahWilayah.unduh() untuk menyimpan hasil sbg CSV.");
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
    const kolom = ["waktu", "jalan", "sumber", "baris", "kunci", "nama", "id", "status_server", "asal", "tujuan", "status",
      "pengawas", "pencacah", "ppl_agenda", "ppl_cocok_agenda", "cara", "pesan"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = Object.values(muatHasil()).map((h) => kolom.map((k) => kutip(h[k])).join(","));
    const blob = new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit_pindah_wilayah_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} baris)`);
  }

  global.pindahWilayah = {
    jalankan, ringkasan, unduh, target: TARGET, asal: ASAL, rencanaTerakhir: null, tidakDikenali: null,
    berhenti() {
      hentikan = true;
      log("Akan berhenti di langkah berikutnya.");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil pindahWilayah yang tersimpan di browser ini?")) localStorage.removeItem(KUNCI_HASIL);
    },
    hapusCacheNama() {
      localStorage.removeItem(KUNCI_CACHE_NAMA);
      log("Cache pencarian nama dihapus.");
    },
  };
  log(`Siap: ${TARGET.length} baris input usaha (${TARGET.filter((t) => (t.ids || []).length).length} ber-ID), asal ${ASAL.join(", ")}. `
    + 'Mulai dgn: await pindahWilayah.jalankan({mode: "cari", limit: 10})');
})(typeof window !== "undefined" ? window : globalThis);
