/**
 * pindah_wilayah_console.js — pindahkan dokumen input usaha dari subsls WADAH ke subsls aslinya
 * (kolom "5" sheet), di fasih-sm dari DevTools Console Chrome BIASA (fasih-sm menolak Playwright).
 *
 * FILE INI TEMPLATE. Jangan ditempel langsung — buat versi berisi target:
 *     python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber bahan/input_usaha.xlsx --console
 *     python fasih_sm/pindah_wilayah/pindah_wilayah.py --sumber ... --bagi 3 --console   (3 akun admin)
 * -> hasil/pindah_wilayah_console[.bagian-K-dari-N].siap.js
 *
 * CARA PAKAI (satu berkas = satu akun admin kabupaten = satu browser)
 * ------------------------------------------------------------------
 * Chrome biasa, VPN, login fasih-sm, halaman Data survei (…/app/surveys/<survei>/<periode>/data)
 * -> F12 -> Console -> tempel SELURUH isi berkas .siap.js -> Enter.
 *     await pindahWilayah.jalankan({mode: "periksa"})           // READ-ONLY: status semua target + cek tujuan
 *     await pindahWilayah.jalankan({mode: "pindah", limit: 1})  // pindah 1 dokumen, cek hasilnya di web
 *     await pindahWilayah.jalankan({mode: "pindah"})            // sisanya (atau limit: 200 mencicil)
 *     await pindahWilayah.jalankan({mode: "periksa"})           // pastikan semuanya sudah di tujuan
 *     pindahWilayah.unduh()                                     // CSV -> audit/, lalu pindah_wilayah.py --catat
 *   Opsi: limit (dokumen dipindah per run), tujuan: ["5108060", ...] (awalan kode tujuan), kunci: [...],
 *     perKirim (dokumen per request, maks 50), cekSesudah (dokumen diperiksa detailnya per request, angka
 *     atau "semua"), jarakRequestMs, jedaBacaMin/Maks, jedaKirimMin/Maks (ms), izinkanTujuanSelesai,
 *     cekTujuan (periksa: cek wilayah & petugas tujuan, bawaan true), pindaiUlang (paksa baca daftar ulang),
 *     pindaiDari (ISO), maksDetail (batas baca detail cadangan per run).
 *   pindahWilayah.berhenti() | ringkasan() | unduh() | daftarTujuan("TUJUAN_BELUM_DIBUKA") | hapusHasil()
 *
 * CARA KERJA — hemat request (rate limit 429 terjadi di datatable analytic)
 * -----------------------------------------------------------------------
 * 1. BACA DAFTAR sekali per run: POST /analytic/api/v2/assignment/datatable-all-user-survey-periode
 *    dgn assignmentExtraParam {mode: ["PAPI"], dateCreatedFrom/To (ISO penuh)}. Server tidak memberi
 *    lebih dari ±1.000 baris per saringan (start >= 1000 -> kosong), jadi daftar dipecah per JENDELA
 *    tanggal dibuat berisi <= maksJendela (900) dokumen; tiap jendela dibaca 150 per halaman dan jumlah id
 *    unik wajib = totalHit (tidak -> dibaca ulang / dipecah lagi). Batas jendela disimpan utk run berikutnya.
 *    Hasil: posisi (6 level wilayah), status, nama tiap dokumen tanpa satu pun pencarian nama.
 *    Target yang ID-nya tidak ada di daftar -> detail per ID (GET get-by-assignment-id), maks `maksDetail`.
 * 2. Per target (ID dari kolom "ID Dokumen FASIH" sheet + audit): tepat 1 dokumen hidup, nama cocok
 *    (nama sheet / nama lama audit), di subsls WADAH (ASAL), APPROVED -> SIAP. Sudah di tujuan -> tuntas.
 * 3. SIAP dikelompokkan per (asal, tujuan) -> wilayah tujuan dicek (ada, sudah dibuka) + petugas tujuan
 *    (Pengawas & Pencacah tepat 1+1) sekali per tujuan -> PUT update-region-bulk <= perKirim id sekaligus
 *    (terbukti 2026-09-27: 50 id/request, updatedCount selalu pas; server menolak SELURUH rombongan
 *    — errorCode 5 "Region baru sama dengan region saat ini" — kalau satu saja sudah di tujuan).
 * 4. Verifikasi: `cekSesudah` dokumen per rombongan (awal, tengah, akhir) dibaca detailnya: keenam level
 *    wilayah = awalan tujuan & tetap APPROVED -> DIPINDAH_TERVERIFIKASI; sisanya DIPINDAH_SERVER_OK
 *    (server menjawab berhasil utk seluruh rombongan) dan dipastikan oleh mode "periksa" berikutnya.
 *
 * KESELAMATAN
 * -----------
 * - Hanya dokumen ber-ID target (bukan pencarian nama), APPROVED, di subsls wadah, nama cocok. >1 dokumen
 *   hidup utk satu target -> DOKUMEN_GANDA (tidak dipindah).
 * - Petugas tujuan SELALU PML+PPL subsls tujuan (ketetapan user 2026-09-15), masing-masing tepat 1.
 * - PUT yang kena galat sementara (429/5xx/jaringan) TIDAK dikirim ulang buta: detail semua anggota
 *   dibaca dulu; hanya yang terbukti masih di wadah yang dikirim ulang.
 * - Batch BERHENTI kalau sesi ditolak, respons tidak dikenal, atau sampel verifikasi tidak cocok.
 * - Pindah tanpa `limit` butuh minimal 1 DIPINDAH_TERVERIFIKASI di browser ini. Ketik YA tiap run pindah.
 * - Beberapa akun: tiap akun menempel berkas BAGIAN-nya sendiri (target dibagi per subsls tujuan, tidak
 *   tumpang tindih). Jangan menempel bagian yang sama di dua browser.
 */
(function (global) {
  "use strict";

  // [{k: kunci baris, s: indeks SUMBER, b: baris sheet, n: nama dokumen (norm), na: [nama lama audit],
  //   t: idsubsls tujuan, ids: [id dokumen: kolom ID sheet + audit]}]
  const TARGET = /*__TARGET__*/[];
  // nama berkas sheet sumber (TARGET[i].s = indeks di sini)
  const SUMBER = /*__SUMBER__*/[];
  // subsls WADAH tempat dokumen boleh dipindah DARI (idsubsls_input audit + --subsls-asal)
  const ASAL = /*__ASAL__*/[];
  // bawaan opsi dari pindah_wilayah.py (--per-kirim, --jeda-kirim, ...) + label bagian
  const KONFIG = /*__KONFIG__*/{};
  // Kode kabupaten 4 digit (awalan idsubsls) — disuntik dari inti/config.py (KODE_KAB).
  const KODE_KAB = /*__KODE_KAB__*/"5108";

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_pindah_wilayah_console.js
  // -------------------------------------------------------------------------
  const STATUS_DIPINDAH = new Set(["DIPINDAH_TERVERIFIKASI", "DIPINDAH_SERVER_OK"]);
  const STATUS_TUNTAS = new Set([...STATUS_DIPINDAH, "SUDAH_DI_TUJUAN"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL", "DIPINDAH_BELUM_TERVERIFIKASI", "DIPINDAH_STATUS_BERUBAH",
    "DIPINDAH_LEVEL_BEDA", "DIPINDAH_JUMLAH_BEDA", "DIHENTIKAN_PENGGUNA", "RATE_LIMIT", "SERVER_SIBUK",
    "PINDAI_GAGAL",
  ]);
  const BATAS_ULANG_429 = 6;
  const HTTP_SIBUK = new Set([0, 502, 503, 504]); // 0 = fetch gagal (jaringan/VPN putus sesaat)
  const KODE_VALID = new RegExp(`^${KODE_KAB}\\d{12}$`);
  // Panjang kode wilayah kumulatif per level (region.level_1..level_6.full_code detail asli):
  // provinsi 51 | kabupaten 5108 | kecamatan 5108060 | desa 5108060002 | SLS 51080600020002 | subsls 5108060002000203
  const PANJANG_LEVEL = [2, 4, 7, 10, 14, 16];
  const NAMA_LEVEL = ["provinsi", "kabupaten", "kecamatan", "desa", "sls", "subsls"];
  const PANJANG_HALAMAN = 150; // datatable analytic menolak length > 150
  const MAKS_PER_KIRIM = 50;   // batas menu "Change Region by Selection"; 50 terbukti 2026-09-27

  /** HTTP status -> "RATE_LIMIT" | "SERVER_SIBUK" (galat sementara, boleh ditunggu & diulang) | null. */
  function jenisSementara(httpStatus) {
    if (httpStatus === 429) return "RATE_LIMIT";
    return HTTP_SIBUK.has(httpStatus) ? "SERVER_SIBUK" : null;
  }

  /** Status yang dihitung sbg kegagalan beruntun (3x -> batch berhenti) tanpa menghentikan seketika. */
  function gagalDihitung(status) {
    return status === "GAGAL_PINDAH" || String(status).startsWith("ERROR_");
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
    const lv = kodeLevel(region);
    return lv.filter(Boolean).pop() || "";
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

  /** "51 > 5108 > 5108060 > ..." (utk log). */
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

  /** Lama menunggu sebelum mengulang request yang kena galat sementara (percobaan ke-0,1,..).
   *  Header Retry-After (detik) dihormati; tanpa itu 15 dtk x 2^ke, maks 2 menit. */
  function jedaRateLimit(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 5000), 300000);
    }
    return Math.min(15000 * 2 ** ke, 120000);
  }

  /** Pengali semua jeda: x2 tiap galat sementara (maks 8), x0,8 tiap sukses (min 1). */
  function faktorJeda(faktor, adaGalat) {
    return adaGalat ? Math.min(8, faktor * 2) : Math.max(1, Math.round(faktor * 800) / 1000);
  }

  /** "5108060014000403 - Praktek Dokter (X)" -> "PRAKTEK DOKTER (X)" (awalan kode 16 digit dibuang, dinormalkan). */
  function namaDariKode(teks) {
    return norm(String(teks == null ? "" : teks).replace(/^\s*\d{16}\s*-\s*/, ""));
  }

  /** Nama yang sah utk satu target: nama dokumen sheet + nama lama di audit (`na`). */
  function namaTarget(t) {
    return [...new Set([t && t.n, ...((t && t.na) || [])].map(norm).filter(Boolean))];
  }

  const namaCocok = (namaServer, namaSah) => (namaServer || []).some((n) => (namaSah || []).includes(n));

  /** Item datatable ATAU data detail -> bentuk ringkas yang sama:
   *  {id, kode, level[], alias, nama[], grup, pengguna}. */
  function ringkasDokumen(it) {
    if (!it || !it.id) return null;
    const region = it.region || {};
    return {
      id: it.id,
      kode: kodeSubsls(region),
      level: kodeLevel(region),
      alias: it.assignmentStatusAlias || it.assignment_status_alias || "",
      nama: [...new Set([it.data1, it.codeIdentity || it.code_identity].filter(Boolean).map(namaDariKode).filter(Boolean))],
      grup: region.groupId || region.group_id || "",
      pengguna: it.currentUserUsername || it.current_user_username || "",
    };
  }

  /** Respons detail get-by-assignment-id (dokumen `id`) -> ringkas | null (bentuk tidak dikenal). */
  function ringkasDetail(j, id) {
    const d = j && j.success === true ? j.data : null;
    if (!d || !d.region) return null;
    return ringkasDokumen({ ...d, id: id || d.id || d._id });
  }

  /** Status satu dokumen thd tujuan & subsls wadah -> {status, pesan}. Dipakai klasifikasi & verifikasi. */
  function nilaiPosisi(d, tujuan, asal) {
    if (!d || !KODE_VALID.test(d.kode || "")) {
      return { status: "RESPONS_TIDAK_DIKENAL", pesan: `kode wilayah dokumen '${d && d.kode}'` };
    }
    if (d.kode === tujuan) {
      const beda = bedaLevel(d.level, tujuan);
      if (beda.length) return { status: "LEVEL_BEDA", pesan: `subsls = tujuan tapi level wilayah beda: ${beda.join("; ")}` };
      return { status: "SUDAH_DI_TUJUAN", pesan: approved(d.alias) ? "" : `status ${d.alias || "-"}` };
    }
    if (!asal.has(d.kode)) return { status: "DI_SUBSLS_LAIN", pesan: `dokumen di ${d.kode}, bukan subsls wadah` };
    if (!approved(d.alias)) return { status: "BELUM_APPROVED", pesan: `status ${d.alias || "-"}` };
    return { status: "SIAP", pesan: "" };
  }

  /** Satu target -> {status, dok, pesan}. `dok` = Map id -> ringkas (atau {hilang: true}).
   *  Status: SIAP | SUDAH_DI_TUJUAN | BELUM_APPROVED | DI_SUBSLS_LAIN | NAMA_TIDAK_COCOK | DOKUMEN_GANDA |
   *  DOKUMEN_HILANG | TIDAK_TERBACA | TUJUAN_TIDAK_VALID | RESPONS_TIDAK_DIKENAL. */
  function nilaiTarget(t, dok, asal) {
    if (!KODE_VALID.test((t && t.t) || "")) return { status: "TUJUAN_TIDAK_VALID", dok: null, pesan: `tujuan '${t && t.t}'` };
    const ids = (t && t.ids) || [];
    if (!ids.length) return { status: "TIDAK_TERBACA", dok: null, pesan: "target tanpa ID dokumen" };
    const belum = ids.filter((id) => !dok.has(id));
    const hidup = ids.map((id) => dok.get(id)).filter((d) => d && !d.hilang);
    const ringkas = (arr) => arr.map((d) => `${d.id.slice(0, 8)} ${d.kode || "?"} ${d.alias || "?"}`).join("; ");
    if (hidup.length > 1) return { status: "DOKUMEN_GANDA", dok: null, pesan: `${hidup.length} dokumen hidup: ${ringkas(hidup)}` };
    if (!hidup.length) {
      return belum.length ? { status: "TIDAK_TERBACA", dok: null, pesan: `ID ${belum.map((i) => i.slice(0, 8)).join(", ")} tidak terbaca` }
        : { status: "DOKUMEN_HILANG", dok: null, pesan: `ID ${ids.map((i) => i.slice(0, 8)).join(", ")} sudah tidak ada (dihapus?)` };
    }
    const d = hidup[0];
    if (belum.length) return { status: "TIDAK_TERBACA", dok: d, pesan: `ID lain ${belum.map((i) => i.slice(0, 8)).join(", ")} belum terbaca` };
    if (!namaCocok(d.nama, namaTarget(t))) {
      return { status: "NAMA_TIDAK_COCOK", dok: d, pesan: `server: ${d.nama.join(" / ") || "-"} | sheet: ${namaTarget(t).join(" / ")}` };
    }
    const p = nilaiPosisi(d, t.t, asal);
    return { status: p.status === "LEVEL_BEDA" ? "RESPONS_TIDAK_DIKENAL" : p.status, dok: d, pesan: p.pesan };
  }

  /** [{t, r}] berstatus SIAP -> rombongan [{asal, tujuan, grup, anggota: [{t, r}]}] (<= perKirim anggota,
   *  satu asal & satu tujuan per rombongan, seperti syarat menu "Change Region by Selection"). Urut tujuan. */
  function susunRombongan(daftar, perKirim) {
    const n = Math.max(1, Math.min(MAKS_PER_KIRIM, Math.floor(perKirim) || MAKS_PER_KIRIM));
    const kelompok = new Map();
    for (const x of daftar) {
      const kunci = `${x.t.t}|${x.r.dok.kode}|${x.r.dok.grup || ""}`;
      if (!kelompok.has(kunci)) kelompok.set(kunci, []);
      kelompok.get(kunci).push(x);
    }
    const hasil = [];
    for (const k of [...kelompok.keys()].sort()) {
      const semua = kelompok.get(k);
      for (let i = 0; i < semua.length; i += n) {
        const anggota = semua.slice(i, i + n);
        hasil.push({ tujuan: anggota[0].t.t, asal: anggota[0].r.dok.kode, grup: anggota[0].r.dok.grup || "", anggota });
      }
    }
    return hasil;
  }

  /** Indeks anggota yang diperiksa detailnya sesudah dipindah: awal, akhir, lalu merata. `k` = angka | "semua". */
  function indeksSampel(n, k) {
    if (k === "semua" || k >= n) return [...Array(n).keys()];
    const m = Math.max(0, Math.floor(Number(k) || 0));
    if (!m || !n) return [];
    if (m === 1) return [0];
    return [...new Set([...Array(m).keys()].map((i) => Math.round((i * (n - 1)) / (m - 1))))];
  }

  /** Respons update-region-bulk -> {ok, status, pesan}. status REGION_SAMA = server menolak seluruh rombongan
   *  karena ada anggota yang SUDAH di tujuan (errorCode 5, tidak ada perubahan sama sekali). */
  function nilaiResponsPindah(httpStatus, teks, jumlah, tujuan) {
    const cuplik = String(teks || "").slice(0, 200);
    if (httpStatus === 401 || httpStatus === 403) return { ok: false, status: "SESI_DITOLAK", pesan: `HTTP ${httpStatus}: ${cuplik}` };
    const sementara = jenisSementara(httpStatus);
    if (sementara) return { ok: false, status: sementara, pesan: `HTTP ${httpStatus || "gagal jaringan"}: ${cuplik}` };
    let j = null;
    try {
      j = JSON.parse(teks);
    } catch (e) {
      return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}, bukan JSON: ${cuplik}` };
    }
    if (httpStatus >= 200 && httpStatus < 300 && j && j.success === true) {
      const d = j.data && typeof j.data === "object" ? j.data : j;
      if (d.newRegionFullCode != null && d.newRegionFullCode !== tujuan) {
        return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `newRegionFullCode ${d.newRegionFullCode} != tujuan ${tujuan}` };
      }
      if (d.updatedCount != null && Number(d.updatedCount) !== jumlah) {
        return { ok: false, status: "DIPINDAH_JUMLAH_BEDA", pesan: `updatedCount ${d.updatedCount} != ${jumlah} dokumen dikirim` };
      }
      return { ok: true, status: "OK", pesan: [j.message, d.updatedCount != null ? `updatedCount ${d.updatedCount}` : ""].filter(Boolean).join(", ") };
    }
    if (j && j.success === false) {
      if (Number(j.errorCode) === 5 || /sama dengan region saat ini/i.test(j.message || "")) {
        return { ok: false, status: "REGION_SAMA", pesan: j.message || "errorCode 5" };
      }
      return { ok: false, status: "GAGAL_PINDAH", pesan: `HTTP ${httpStatus}: ${j.message || "(tanpa pesan)"}${j.errorCode != null ? ` (errorCode ${j.errorCode})` : ""}` };
    }
    return { ok: false, status: "RESPONS_TIDAK_DIKENAL", pesan: `HTTP ${httpStatus}: ${cuplik}` };
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

  function bodyPindah(ids, tujuan, groupId, pengawas, pencacah) {
    return { assignmentIds: ids, smallestLevelFullCode: tujuan, groupId, userRegionIds: [pengawas.id, pencacah.id] };
  }

  /** Body datatable analytic: semua dokumen satu jendela tanggal dibuat (ISO penuh; "2026-09-16" saja = 0 hasil). */
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
    const a = Date.parse(dari);
    const b = Date.parse(sampai);
    const m = new Date(Math.floor((a + b) / 2)).toISOString();
    return [[dari, m], [m, sampai]];
  }

  /** Jendela bersebelahan digabung selama jumlahnya <= batas (hemat request di run berikutnya). */
  function gabungJendela(jendela, batas) {
    const hasil = [];
    for (const [a, b, n] of [...jendela].sort((x, y) => Date.parse(x[0]) - Date.parse(y[0]))) {
      const akhir = hasil[hasil.length - 1];
      if (akhir && akhir[1] === a && akhir[2] + n <= batas) akhir.splice(1, 2, b, akhir[2] + n);
      else hasil.push([a, b, n]);
    }
    return hasil;
  }

  /** Hasil tersimpan lama + hasil baru -> yang disimpan. Bukti pindah tidak tertimpa hasil periksa/cek:
   *  DIPINDAH_SERVER_OK + periksa SUDAH_DI_TUJUAN -> DIPINDAH_TERVERIFIKASI; DIPINDAH_TERVERIFIKASI tetap. */
  function gabungHasil(lama, baru) {
    if (!lama || !STATUS_DIPINDAH.has(lama.st) || STATUS_DIPINDAH.has(baru.st)) return baru;
    if (lama.st === "DIPINDAH_SERVER_OK" && baru.st === "SUDAH_DI_TUJUAN") {
      return { ...lama, st: "DIPINDAH_TERVERIFIKASI", p: `${lama.p ? lama.p + " | " : ""}diverifikasi ${baru.j} ${baru.w}` };
    }
    if (lama.st === "DIPINDAH_SERVER_OK" && baru.st === "DIPINDAH_BELUM_TERVERIFIKASI") return baru;
    return lama;
  }

  const kunciHasil = (t) => `${SUMBER[t.s] != null ? SUMBER[t.s] : t.s}|${t.k}`;

  /** Target yang diproses: saring kunci/awalan tujuan; mode pindah melewati yang sudah dipindah. */
  function saringTarget(target, sebelumnya, o) {
    return target.filter((t) => (!o.kunci || o.kunci.includes(t.k))
      && (!o.tujuan || o.tujuan.some((p) => String(t.t).startsWith(String(p))))
      && !(o.lewatiSelesai && sebelumnya[kunciHasil(t)] && STATUS_DIPINDAH.has(sebelumnya[kunciHasil(t)].st)));
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      TARGET, SUMBER, ASAL, KONFIG, STATUS_BERHENTI_SEGERA, STATUS_TUNTAS, STATUS_DIPINDAH, BATAS_ULANG_429,
      halamanData, norm, approved, jenisSementara, gagalDihitung, kodeSubsls, kodeLevel, levelWilayah, jalurLevel,
      bedaLevel, jedaRateLimit, faktorJeda, namaDariKode, namaTarget, namaCocok, ringkasDokumen, ringkasDetail,
      nilaiPosisi, nilaiTarget, susunRombongan, indeksSampel, nilaiResponsPindah, nilaiWilayahTujuan, pilihPetugas,
      peranPetugas, bodyPindah, bodyDaftar, bagiJendela, gabungJendela, gabungHasil, kunciHasil, saringTarget,
    };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "pindahWilayah.hasil.v2";
  const KUNCI_JENDELA = "pindahWilayah.jendela.v1";
  const API = "/app/api";
  const BAGIAN = KONFIG.bagian || "";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (Math.max(a, b) - a + 1));
  const log = (...a) => console.log("%c[pindahWilayah]", "color:#2e7d32;font-weight:bold", ...a);
  const siapa = (p) => (p && (p.email || p.username || p.id)) || "";

  let hentikan = false;
  let berjalan = false;
  let faktor = 1;               // pengali semua jeda (naik saat 429/5xx)
  let requestTerakhir = 0;
  let pindaiTerakhir = null;    // {waktu, dok: Map, info}
  const cacheTujuan = new Map(); // "tujuan|grup" -> {waktu, run, hasil}
  let nomorRun = 0;
  let terakhir = { status: {} }; // ringkasan run terakhir (daftarTujuan)

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

  async function minta(o, method, url, body) {
    const tunggu = requestTerakhir + Math.round(o.jarakRequestMs * faktor) - Date.now();
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
      return { status: 0, teks: `fetch gagal: ${e && e.message ? e.message : e}`, retryAfter: null };
    }
  }

  function catatFaktor(adaGalat) {
    const lama = faktor;
    faktor = faktorJeda(faktor, adaGalat);
    if (faktor > lama) log(`Jeda dinaikkan jadi x${faktor} (server sibuk / rate limit)`);
  }

  /** Request BACA: galat sementara ditunggu & diulang (maks BATAS_ULANG_429) lalu Berhenti; 401 & bukan-JSON
   *  -> Berhenti. 403 -> Berhenti SESI_DITOLAK kecuali `boleh403` ({status: 403, j: null} dikembalikan). */
  async function bacaJson(o, method, url, body, boleh403) {
    const ujung = url.split("?")[0];
    let r;
    for (let ke = 0; ; ke++) {
      r = await minta(o, method, url, body);
      const jenis = jenisSementara(r.status);
      catatFaktor(!!jenis);
      if (!jenis) break;
      const http = r.status ? `HTTP ${r.status}` : "gagal jaringan";
      if (ke >= BATAS_ULANG_429) throw new Berhenti(jenis, `${ujung} masih ${http} setelah ${ke} kali menunggu — coba lagi nanti`);
      const tunggu = jedaRateLimit(ke, r.retryAfter);
      log(`⏳ ${http} (${jenis === "RATE_LIMIT" ? "rate limit" : "server sibuk"}) di ${ujung} — tunggu ${Math.round(tunggu / 1000)} dtk (ulang ${ke + 1}/${BATAS_ULANG_429})`);
      await tidur(tunggu);
    }
    const { status, teks } = r;
    if (status === 403 && boleh403) return { status, j: null };
    if (status === 401 || status === 403) throw new Berhenti("SESI_DITOLAK", `${ujung} HTTP ${status}: ${teks.slice(0, 150)}`);
    try {
      return { status, j: JSON.parse(teks) };
    } catch (e) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `${ujung} HTTP ${status}, bukan JSON: ${teks.slice(0, 150)}`);
    }
  }

  const qs = (o) => Object.entries(o).filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");

  async function halamanDaftar(ctx, o, start, dari, sampai) {
    const { status, j } = await bacaJson(o, "POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode",
      bodyDaftar(ctx.periode, start, PANJANG_HALAMAN, dari, sampai, o.modePindai));
    if (status !== 200 || !j || !Array.isArray(j.searchData) || typeof j.totalHit !== "number") {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable assignment HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j;
  }

  /** Satu jendela: semua halaman -> {ids: Set, total} (ringkas masuk `dok`). */
  async function bacaJendela(ctx, o, dari, sampai, dok, awal) {
    const ids = new Set();
    const simpan = (items) => {
      for (const it of items) {
        const d = ringkasDokumen(it);
        if (d) { ids.add(d.id); dok.set(d.id, d); }
      }
    };
    simpan(awal.searchData);
    for (let start = PANJANG_HALAMAN; start < awal.totalHit; start += PANJANG_HALAMAN) {
      cekHenti();
      await tidur(Math.round(acak(o.jedaBacaMin, o.jedaBacaMaks) * faktor));
      const j = await halamanDaftar(ctx, o, start, dari, sampai);
      if (!j.searchData.length) break;
      simpan(j.searchData);
    }
    return { ids, total: awal.totalHit };
  }

  function muatJendela(o) {
    try {
      const s = JSON.parse(localStorage.getItem(KUNCI_JENDELA) || "null");
      if (s && s.mode === JSON.stringify(o.modePindai) && s.dari === o.pindaiDari && Array.isArray(s.jendela)
        && Date.now() - s.waktu < 24 * 3600 * 1000 && s.jendela.length) return s.jendela.map((j) => j.slice(0, 2));
    } catch (e) {
      // jendela tersimpan hanya penghemat request
    }
    return null;
  }

  /** BACA DAFTAR: semua dokumen (mode PAPI) per jendela tanggal dibuat -> {dok: Map id -> ringkas, info}. */
  async function pindaiDaftar(ctx, o) {
    const mulai = Date.now();
    const semua = await halamanDaftar(ctx, { ...o }, 0, null, null);
    const totalSemua = semua.totalHit;
    const ujung = new Date(Date.now() + 3600 * 1000).toISOString();
    const tersimpan = muatJendela(o);
    const antre = tersimpan || [[o.pindaiDari, ujung]];
    antre[antre.length - 1][1] = ujung;
    log(`Membaca daftar ${totalSemua} dokumen ${(o.modePindai || []).join("/") || "semua mode"} per jendela tanggal dibuat`
      + (tersimpan ? ` (${tersimpan.length} jendela tersimpan)` : "") + "...");
    const dok = new Map();
    const selesai = [];
    const tidakUtuh = [];
    while (antre.length) {
      cekHenti();
      const [a, b] = antre.shift();
      await tidur(Math.round(acak(o.jedaBacaMin, o.jedaBacaMaks) * faktor));
      const awal = await halamanDaftar(ctx, o, 0, a, b);
      if (awal.totalHit > o.maksJendela) {
        if (Date.parse(b) - Date.parse(a) < 60000) {
          throw new Berhenti("PINDAI_GAGAL", `${awal.totalHit} dokumen dibuat dlm < 1 menit (${a}) — perkecil maksJendela tidak menolong`);
        }
        antre.unshift(...bagiJendela(a, b));
        continue;
      }
      let baca = await bacaJendela(ctx, o, a, b, dok, awal);
      if (baca.ids.size < baca.total) {
        log(`  jendela ${a.slice(0, 16)}..${b.slice(0, 16)}: ${baca.ids.size}/${baca.total} id — dibaca ulang`);
        const ulang = await halamanDaftar(ctx, o, 0, a, b);
        const kedua = await bacaJendela(ctx, o, a, b, dok, ulang);
        for (const id of kedua.ids) baca.ids.add(id);
        baca = { ids: baca.ids, total: Math.max(baca.total, kedua.total) };
        if (baca.ids.size < baca.total && baca.total > PANJANG_HALAMAN && Date.parse(b) - Date.parse(a) >= 120000) {
          antre.unshift(...bagiJendela(a, b));
          continue;
        }
        if (baca.ids.size < baca.total) tidakUtuh.push(`${a}..${b}: ${baca.ids.size}/${baca.total}`);
      }
      selesai.push([a, b, baca.total]);
      if (selesai.length % 5 === 0) log(`  ${dok.size}/${totalSemua} dokumen terbaca (${selesai.length} jendela)`);
    }
    try {
      localStorage.setItem(KUNCI_JENDELA, JSON.stringify({ waktu: Date.now(), mode: JSON.stringify(o.modePindai),
        dari: o.pindaiDari, jendela: gabungJendela(selesai, Math.floor(o.maksJendela * 0.7)) }));
    } catch (e) {
      // tidak fatal
    }
    const info = { total: totalSemua, terbaca: dok.size, jendela: selesai.length, tidakUtuh,
      detik: Math.round((Date.now() - mulai) / 1000) };
    log(`Daftar terbaca: ${dok.size}/${totalSemua} dokumen, ${selesai.length} jendela, ${info.detik} dtk`
      + (tidakUtuh.length ? ` | ⚠️ ${tidakUtuh.length} jendela tidak utuh: ${tidakUtuh.join("; ")}` : ""));
    if (dok.size < totalSemua) {
      log(`⚠️ ${totalSemua - dok.size} dokumen tidak terbaca (jendela tanggal mungkin tidak menutup semua / dokumen baru). `
        + "Target yang ID-nya tidak terbaca diperiksa lewat detail per ID.");
    }
    return { waktu: Date.now(), dok, info };
  }

  async function sesiHidup(ctx, o) {
    const r = await minta(o, "GET", `/survey/api/v1/survey-roles?${qs({ surveyId: ctx.survei })}`);
    return r.status === 200;
  }

  /** Detail satu dokumen -> ringkas | {id, hilang: true} (403 dgn sesi hidup = dokumen terhapus) | null. */
  async function detailDokumen(ctx, o, id) {
    const { status, j } = await bacaJson(o, "GET", `/assignment-general/api/assignment/get-by-assignment-id?${qs({ assignmentId: id })}`,
      undefined, true);
    if (status === 403) {
      if (await sesiHidup(ctx, o)) return { id, hilang: true };
      throw new Berhenti("SESI_DITOLAK", "detail HTTP 403 & sesi tidak hidup — login ulang");
    }
    return ringkasDetail(j, id);
  }

  async function wilayahTujuan(ctx, o, kode) {
    const { status, j } = await bacaJson(o, "POST", `/assignment-general/api/assignment-region/datatable?${qs({ periodeId: ctx.periode })}`,
      { start: 0, length: 10, search: { value: kode, regex: true }, order: [{ column: 0, dir: "asc" }] });
    if (status !== 200 || !j || !Array.isArray(j.data)) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable wilayah HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j.data;
  }

  async function userRegion(ctx, o, peran, kode, parentAllocationId) {
    const { status, j } = await bacaJson(o, "GET", `/survey-user/api/v1/user-region/region?${qs({
      surveyPeriodId: ctx.periode, surveyRoleId: peran.id, regionCode: kode, parentAllocationId })}`);
    if (status !== 200 || !j || j.success !== true) {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `user-region HTTP ${status}: ${JSON.stringify(j).slice(0, 150)}`);
    }
    return j.data;
  }

  /** Wilayah tujuan (ada, dibuka) + PML/PPL tujuan tepat 1+1. Yang OK diingat 60 menit per tab; yang gagal
   *  hanya selama run ini (sesudah buka wilayah / perbaikan petugas, run berikutnya memeriksa ulang). */
  async function siapkanTujuan(ctx, o, kode, groupId) {
    const kunci = `${kode}|${groupId}`;
    const c = cacheTujuan.get(kunci);
    if (c && (c.run === nomorRun || (c.hasil.status === "OK" && Date.now() - c.waktu < 3600 * 1000))) return c.hasil;
    const w = nilaiWilayahTujuan(kode, await wilayahTujuan(ctx, o, kode), groupId, o);
    let hasil = { status: w.status, pesan: w.pesan };
    if (w.status === "OK") {
      const pw = pilihPetugas("Pengawas", await userRegion(ctx, o, ctx.peran[0], kode), kode);
      if (pw.status !== "OK") {
        hasil = pw;
      } else {
        const pc = pilihPetugas("Pencacah", await userRegion(ctx, o, ctx.peran[1], kode, pw.petugas.allocationId), kode,
          pw.petugas.allocationId);
        hasil = pc.status !== "OK" ? pc
          : { status: "OK", pengawas: pw.petugas, pencacah: pc.petugas, pesan: [w.pesan, `PML ${pw.pesan}, PPL ${pc.pesan}`].filter(Boolean).join(" | ") };
      }
    }
    cacheTujuan.set(kunci, { waktu: Date.now(), run: nomorRun, hasil });
    return hasil;
  }

  // ---- hasil tersimpan (localStorage, ringkas; dikumpulkan di memori lalu ditulis sekaligus) ----
  let hasilMemori = null;
  let hasilKotor = false;
  function muatHasil() {
    if (!hasilMemori) {
      try {
        hasilMemori = JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}");
      } catch (e) {
        hasilMemori = {};
      }
    }
    return hasilMemori;
  }
  function catatHasil(t, entri) {
    const semua = muatHasil();
    const k = kunciHasil(t);
    const baru = { w: new Date().toISOString().slice(0, 19), ...entri, p: String(entri.p || "").slice(0, 160) };
    for (const kol of Object.keys(baru)) if (baru[kol] === "" || baru[kol] == null) delete baru[kol];
    semua[k] = gabungHasil(semua[k], baru);
    hasilKotor = true;
    return semua[k];
  }
  function tulisHasil() {
    if (!hasilKotor) return;
    try {
      localStorage.setItem(KUNCI_HASIL, JSON.stringify(hasilMemori));
      hasilKotor = false;
    } catch (e) {
      log("⚠️ Hasil gagal disimpan di localStorage (penuh?) — SEGERA pindahWilayah.unduh()", e);
    }
  }

  /** Daftar kerja: baca daftar (atau pakai yang masih segar) + detail cadangan -> [{t, r}]. */
  async function klasifikasi(ctx, o, daftar) {
    const segar = pindaiTerakhir && !o.pindaiUlang && o.mode === "pindah"
      && Date.now() - pindaiTerakhir.waktu < o.umurPindaiMenit * 60000;
    if (segar) log(`Memakai daftar yang dibaca ${Math.round((Date.now() - pindaiTerakhir.waktu) / 60000)} menit lalu (pindaiUlang: true utk membaca ulang).`);
    else pindaiTerakhir = await pindaiDaftar(ctx, o);
    const dok = pindaiTerakhir.dok;
    const asal = new Set(ASAL);
    const sebelumnya = muatHasil();
    // Detail cadangan: ID yang tidak ada di daftar, dan dokumen yang baru dipindah tapi daftar masih
    // menunjuk wadah (indeks daftar bisa terlambat beberapa menit dari data utama).
    const perluDetail = new Set();
    for (const t of daftar) {
      for (const id of t.ids || []) if (!dok.has(id)) perluDetail.add(id);
      const h = sebelumnya[kunciHasil(t)];
      const d = h && h.id && dok.get(h.id);
      if (h && STATUS_DIPINDAH.has(h.st) && d && d.kode !== t.t) perluDetail.add(h.id);
    }
    const ids = [...perluDetail];
    if (ids.length) log(`${ids.length} ID dibaca lewat detail (tidak ada di daftar / daftar belum diperbarui)`
      + (ids.length > o.maksDetail ? ` — dibatasi ${o.maksDetail} (maksDetail)` : ""));
    for (let i = 0; i < Math.min(ids.length, o.maksDetail); i++) {
      cekHenti();
      const d = await detailDokumen(ctx, o, ids[i]);
      if (d) dok.set(ids[i], d);
      if ((i + 1) % 50 === 0) log(`  detail ${i + 1}/${Math.min(ids.length, o.maksDetail)}`);
    }
    return daftar.map((t) => ({ t, r: nilaiTarget(t, dok, asal) }));
  }

  function simpanKlasifikasi(kerja, o) {
    const hitung = {};
    const sebelumnya = muatHasil();
    for (const { t, r } of kerja) {
      const d = r.dok || {};
      let st = r.status === "SIAP" ? "SIAP_PINDAH" : r.status;
      let p = r.pesan;
      const lama = sebelumnya[kunciHasil(t)];
      if (lama && lama.st === "DIPINDAH_SERVER_OK" && r.status !== "SUDAH_DI_TUJUAN") {
        // Server menjawab berhasil utk rombongannya, tapi dokumen ini TIDAK di tujuan (detail dibaca).
        p = `tercatat dipindah ${lama.w}, kini ${r.status} di ${d.kode || "?"}: ${r.pesan}`;
        st = "DIPINDAH_BELUM_TERVERIFIKASI";
      }
      const h = catatHasil(t, { j: o.mode, st, id: d.id || "", a: d.kode || "", ss: d.alias || "", p });
      hitung[h.st] = (hitung[h.st] || 0) + 1;
    }
    return hitung;
  }

  /** Baca detail semua anggota -> {pindah: [x], siap: [x], lain: [[x, status, pesan]]}. `sudahSebelum` = server
   *  menolak rombongan (region sama): yang di tujuan memang sudah di sana, status apa pun. */
  async function periksaAnggota(ctx, o, anggota, tujuan, sudahSebelum) {
    const asal = new Set(ASAL);
    const out = { pindah: [], siap: [], lain: [] };
    for (const x of anggota) {
      cekHenti();
      const d = await detailDokumen(ctx, o, x.r.dok.id);
      if (!d || d.hilang) {
        out.lain.push([x, "RESPONS_TIDAK_DIKENAL", d ? "dokumen hilang sesudah dikirim" : "detail tidak terbaca"]);
        continue;
      }
      x.r.dok = d;
      const p = nilaiPosisi(d, tujuan, asal);
      if (p.status === "SUDAH_DI_TUJUAN" && !sudahSebelum && !approved(d.alias)) {
        out.lain.push([x, "DIPINDAH_STATUS_BERUBAH", `di tujuan tapi status '${d.alias || "-"}'`]);
      } else if (p.status === "SUDAH_DI_TUJUAN") out.pindah.push(x);
      else if (p.status === "SIAP") out.siap.push(x);
      else out.lain.push([x, p.status === "LEVEL_BEDA" ? "DIPINDAH_LEVEL_BEDA" : p.status, p.pesan]);
    }
    return out;
  }

  /** Verifikasi SAMPEL sesudah server menjawab berhasil: detail dibaca (maks 3x) -> di tujuan, 6 level
   *  cocok, tetap APPROVED. -> null (semua cocok) | {status, pesan} penyebab berhenti. */
  async function verifikasiSampel(ctx, o, sampel, tujuan) {
    for (const x of sampel) {
      let d = null;
      for (let ke = 1; ke <= 3; ke++) {
        await sleep(1500 * ke);
        d = await detailDokumen(ctx, o, x.r.dok.id);
        if (d && !d.hilang && d.kode === tujuan) break;
      }
      const id8 = x.r.dok.id.slice(0, 8);
      if (!d || d.hilang || d.kode !== tujuan) {
        return { status: "DIPINDAH_BELUM_TERVERIFIKASI", pesan: `${id8}: detail ${d && d.kode ? `masih ${d.kode}` : "tidak terbaca"} setelah 3x cek` };
      }
      const beda = bedaLevel(d.level, tujuan);
      if (beda.length) return { status: "DIPINDAH_LEVEL_BEDA", pesan: `${id8}: ${beda.join("; ")}` };
      if (!approved(d.alias)) return { status: "DIPINDAH_STATUS_BERUBAH", pesan: `${id8}: status jadi '${d.alias}'` };
      x.r.dok = d;
    }
    return null;
  }

  /** IRREVERSIBLE oleh skrip (bisa dipindah balik manual lewat menu yang sama). Satu PUT utk <= perKirim
   *  anggota -> {dipindah, berhenti: {status, pesan} | null, gagal: bool}. Hasil per anggota dicatat. */
  async function kirimRombongan(ctx, o, rb, tj, catat) {
    let anggota = rb.anggota;
    const siapaPw = siapa(tj.pengawas);
    const siapaPc = siapa(tj.pencacah);
    const tulis = (x, st, p) => catat(x.t, { j: "pindah", st, id: x.r.dok.id, a: rb.asal, ss: x.r.dok.alias || "", pw: siapaPw, pc: siapaPc, p });
    let dipindah = 0;
    for (let ke = 0; anggota.length; ke++) {
      cekHenti();
      const ids = anggota.map((x) => x.r.dok.id);
      const r = await minta(o, "PUT", "/assignment-general/api/assignment/update-region-bulk",
        bodyPindah(ids, rb.tujuan, rb.grup, tj.pengawas, tj.pencacah));
      const n = nilaiResponsPindah(r.status, r.teks, ids.length, rb.tujuan);
      catatFaktor(n.status === "RATE_LIMIT" || n.status === "SERVER_SIBUK");
      if (n.ok) {
        const idx = new Set(indeksSampel(anggota.length, o.cekSesudah));
        const sampel = anggota.filter((_, i) => idx.has(i));
        const salah = await verifikasiSampel(ctx, o, sampel, rb.tujuan);
        if (salah) {
          for (const x of anggota) tulis(x, salah.status, `server: ${n.pesan} | verifikasi: ${salah.pesan}`);
          return { dipindah: dipindah + anggota.length, berhenti: salah };
        }
        for (const x of anggota) {
          tulis(x, idx.has(anggota.indexOf(x)) ? "DIPINDAH_TERVERIFIKASI" : "DIPINDAH_SERVER_OK",
            `${rb.asal} -> ${rb.tujuan} (${ids.length} dok/request; ${n.pesan})${idx.has(anggota.indexOf(x)) ? " | detail 6 level cocok" : ""}`);
        }
        return { dipindah: dipindah + anggota.length, berhenti: null };
      }
      if (["SESI_DITOLAK", "RESPONS_TIDAK_DIKENAL"].includes(n.status)) {
        for (const x of anggota) tulis(x, n.status, n.pesan);
        return { dipindah, berhenti: n };
      }
      if (n.status === "GAGAL_PINDAH") {
        for (const x of anggota) tulis(x, n.status, n.pesan);
        return { dipindah, berhenti: null, gagal: true };
      }
      // REGION_SAMA / galat sementara / jumlah beda: JANGAN kirim ulang buta — baca detail semua anggota dulu.
      if (n.status === "RATE_LIMIT" || n.status === "SERVER_SIBUK") {
        const tunggu = jedaRateLimit(ke, r.retryAfter);
        log(`⏳ ${n.pesan.slice(0, 60)} saat memindah ${ids.length} dokumen ke ${rb.tujuan} — tunggu ${Math.round(tunggu / 1000)} dtk, cek detail dulu`);
        await sleep(tunggu); // sengaja tidak bisa dihentikan: status dokumen harus diketahui dulu
      }
      log(`  ${n.status}: ${n.pesan} — detail ${anggota.length} dokumen dibaca`);
      const sudahSebelum = n.status === "REGION_SAMA";
      const cek = await periksaAnggota(ctx, o, anggota, rb.tujuan, sudahSebelum);
      for (const x of cek.pindah) {
        tulis(x, sudahSebelum ? "SUDAH_DI_TUJUAN" : "DIPINDAH_TERVERIFIKASI",
          sudahSebelum ? "sudah di tujuan sebelum dikirim (server menolak rombongan: region sama)" : `setelah ${n.status}: detail di tujuan`);
      }
      for (const [x, st, p] of cek.lain) tulis(x, st, p);
      if (!sudahSebelum) dipindah += cek.pindah.length;
      if (n.status === "DIPINDAH_JUMLAH_BEDA") {
        for (const x of cek.siap) tulis(x, "DIPINDAH_JUMLAH_BEDA", `${n.pesan}; dokumen masih di wadah`);
        return { dipindah, berhenti: n };
      }
      if (cek.lain.some(([, st]) => STATUS_BERHENTI_SEGERA.has(st))) {
        return { dipindah, berhenti: { status: "RESPONS_TIDAK_DIKENAL", pesan: "anggota rombongan dalam keadaan tak terduga — cek manual" } };
      }
      if (sudahSebelum && !cek.pindah.length) {
        for (const x of cek.siap) tulis(x, "RESPONS_TIDAK_DIKENAL", `server: ${n.pesan}, tapi tidak satu pun anggota di tujuan`);
        return { dipindah, berhenti: { status: "RESPONS_TIDAK_DIKENAL", pesan: `${n.pesan} — padahal tidak ada anggota yang sudah di tujuan` } };
      }
      if (!sudahSebelum && cek.pindah.length && cek.siap.length) {
        for (const x of cek.siap) tulis(x, "DIPINDAH_BELUM_TERVERIFIKASI", "sebagian rombongan pindah, sebagian tidak");
        return { dipindah, berhenti: { status: "DIPINDAH_BELUM_TERVERIFIKASI", pesan: `setelah ${n.status}: rombongan terpindah SEBAGIAN — cek manual` } };
      }
      if (ke >= BATAS_ULANG_429) {
        for (const x of cek.siap) tulis(x, n.status, `${n.pesan} — masih di wadah setelah ${ke + 1}x kirim`);
        return { dipindah, berhenti: { status: n.status, pesan: n.pesan } };
      }
      anggota = cek.siap; // hanya yang TERBUKTI masih di wadah & APPROVED yang dikirim ulang
    }
    return { dipindah, berhenti: null };
  }

  async function jalankanPindah(ctx, o, kerja, sebelumnya, hitung) {
    const siap = kerja.filter((x) => x.r.status === "SIAP");
    const adaBukti = Object.values(sebelumnya).some((h) => h.st === "DIPINDAH_TERVERIFIKASI");
    if (!siap.length) return log("Tidak ada dokumen SIAP dipindah.");
    if (!o.limit && !adaBukti) {
      return log("Pindah massal butuh minimal 1 DIPINDAH_TERVERIFIKASI di browser ini. Jalankan: "
        + 'await pindahWilayah.jalankan({mode: "pindah", limit: 1}) lalu cek dokumennya di fasih-sm.');
    }
    let rombongan = susunRombongan(siap, o.perKirim);
    const maks = o.limit ? Math.min(o.limit, siap.length) : siap.length;
    if (prompt(`PINDAH WILAYAH SUNGGUHAN${BAGIAN ? ` (bagian ${BAGIAN})` : ""}: maks. ${maks} dokumen, `
      + `${rombongan.length} rombongan <= ${o.perKirim} dokumen, ke ${new Set(siap.map((x) => x.t.t)).size} subsls tujuan.\n`
      + "Petugas = PML+PPL subsls tujuan. Ketik YA untuk lanjut:") !== "YA") {
      return log("Dibatalkan.");
    }
    let dipindah = 0;
    let gagalBeruntun = 0;
    const tambah = (s, n = 1) => { hitung[s] = (hitung[s] || 0) + n; };
    const catat = (t, e) => { const h = catatHasil(t, e); tambah(h.st); return h; };
    for (let i = 0; i < rombongan.length; i++) {
      if (dipindah >= maks) break;
      cekHenti();
      let rb = rombongan[i];
      if (dipindah + rb.anggota.length > maks) rb = { ...rb, anggota: rb.anggota.slice(0, maks - dipindah) };
      if (!rb.grup) {
        const d = await detailDokumen(ctx, o, rb.anggota[0].r.dok.id);
        rb.grup = (d && d.grup) || "";
        if (!rb.grup) throw new Berhenti("RESPONS_TIDAK_DIKENAL", "region.group_id dokumen tidak terbaca");
      }
      const tj = await siapkanTujuan(ctx, o, rb.tujuan, rb.grup);
      if (tj.status !== "OK") {
        for (const x of rb.anggota) catat(x.t, { j: "pindah", st: tj.status, id: x.r.dok.id, a: rb.asal, ss: x.r.dok.alias || "", p: tj.pesan });
        log(`[${i + 1}/${rombongan.length}] ${rb.tujuan}: ${rb.anggota.length} dokumen -> ${tj.status}`, tj.pesan);
        if (STATUS_BERHENTI_SEGERA.has(tj.status)) throw new Berhenti(tj.status, tj.pesan);
        continue;
      }
      const k = await kirimRombongan(ctx, o, rb, tj, catat);
      tulisHasil();
      dipindah += k.dipindah;
      log(`[${i + 1}/${rombongan.length}] ${rb.asal} -> ${rb.tujuan} (${jalurLevel(rb.tujuan)}): ${rb.anggota.length} dokumen, `
        + `${k.dipindah} dipindah | PML ${siapa(tj.pengawas)}, PPL ${siapa(tj.pencacah)} | total ${dipindah}/${maks}`);
      if (k.berhenti) throw new Berhenti(k.berhenti.status, k.berhenti.pesan);
      gagalBeruntun = k.gagal ? gagalBeruntun + 1 : 0;
      if (gagalBeruntun >= 3) throw new Berhenti("GAGAL_PINDAH", "3 rombongan gagal berturut-turut — periksa pesannya");
      if (i < rombongan.length - 1) await tidur(Math.round(acak(o.jedaKirimMin, o.jedaKirimMaks) * faktor));
    }
    log(`${dipindah} dokumen dipindah di run ini.`);
  }

  async function jalankanPeriksa(ctx, o, kerja, hitung) {
    Object.assign(hitung, simpanKlasifikasi(kerja, o));
    const siap = kerja.filter((x) => x.r.status === "SIAP");
    const perTujuan = new Map();
    for (const x of siap) perTujuan.set(x.t.t, [...(perTujuan.get(x.t.t) || []), x]);
    const tujuan = [...perTujuan.values()].map((a) => a[0]);
    if (o.cekTujuan && tujuan.length) {
      log(`Cek wilayah & petugas ${tujuan.length} subsls tujuan (±3 request per tujuan)...`);
      for (let i = 0; i < tujuan.length; i++) {
        cekHenti();
        const x = tujuan[i];
        let grup = x.r.dok.grup;
        if (!grup) grup = ((await detailDokumen(ctx, o, x.r.dok.id)) || {}).grup || "";
        const tj = await siapkanTujuan(ctx, o, x.t.t, grup);
        if (tj.status !== "OK") {
          for (const y of perTujuan.get(x.t.t)) {
            const lama = muatHasil()[kunciHasil(y.t)];
            hitung[lama.st]--;
            const h = catatHasil(y.t, { ...lama, st: tj.status, p: tj.pesan });
            hitung[h.st] = (hitung[h.st] || 0) + 1;
          }
        }
        if ((i + 1) % 25 === 0) log(`  tujuan ${i + 1}/${tujuan.length}`);
      }
    }
    for (const k of Object.keys(hitung)) if (!hitung[k]) delete hitung[k];
  }

  async function jalankan(opsi = {}) {
    const o = {
      mode: "periksa", limit: null, tujuan: null, kunci: null, lewatiSelesai: true, izinkanTujuanSelesai: false,
      perKirim: 50, cekSesudah: 3, jarakRequestMs: 800, jedaBacaMin: 1500, jedaBacaMaks: 3000,
      jedaKirimMin: 3000, jedaKirimMaks: 6000, maksJendela: 900, pindaiDari: "2026-01-01T00:00:00.000Z",
      modePindai: ["PAPI"], maksDetail: 300, cekTujuan: true, pindaiUlang: false, umurPindaiMenit: 30,
      ...KONFIG.opsi, ...opsi,
    };
    o.perKirim = Math.max(1, Math.min(MAKS_PER_KIRIM, Math.floor(o.perKirim) || MAKS_PER_KIRIM));
    if (!["periksa", "pindah"].includes(o.mode)) return log(`mode '${o.mode}' tidak dikenal (periksa | pindah)`);
    if (o.mode === "periksa") o.lewatiSelesai = false; // periksa = memastikan ulang semuanya
    if (berjalan) return log("Masih berjalan — tunggu selesai atau pindahWilayah.berhenti().");
    if (!TARGET.length || !ASAL.length) return log("TARGET/ASAL kosong — tempel pindah_wilayah_console*.siap.js, bukan template.");
    const hal = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !hal) {
      return log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
    }
    const sebelumnya = muatHasil();
    const daftar = saringTarget(TARGET, sebelumnya, o);
    if (!daftar.length) return log("Tidak ada target yang perlu diproses (yang sudah dipindah dilewati).");

    berjalan = true;
    hentikan = false;
    nomorRun++;
    const hitung = {};
    try {
      log(`${o.mode === "periksa" ? "PERIKSA (READ-ONLY)" : "PINDAH"}${BAGIAN ? ` bagian ${BAGIAN}` : ""}: ${daftar.length} target`);
      const roles = await bacaJson(o, "GET", `/survey/api/v1/survey-roles?${qs({ surveyId: hal.survei })}`);
      const peran = peranPetugas(roles.j && roles.j.data);
      if (!peran) throw new Berhenti("RESPONS_TIDAK_DIKENAL", "peran Petugas bukan tepat [Pengawas, Pencacah]");
      const ctx = { ...hal, peran };
      const kerja = await klasifikasi(ctx, o, daftar);
      if (o.mode === "periksa") await jalankanPeriksa(ctx, o, kerja, hitung);
      else {
        const awal = {};
        for (const { r } of kerja) awal[r.status] = (awal[r.status] || 0) + 1;
        log("Keadaan sebelum pindah:", awal);
        for (const x of kerja) if (x.r.status !== "SIAP") catatHasil(x.t, { j: "pindah", st: x.r.status, id: (x.r.dok || {}).id || "", a: (x.r.dok || {}).kode || "", ss: (x.r.dok || {}).alias || "", p: x.r.pesan });
        await jalankanPindah(ctx, o, kerja, sebelumnya, hitung);
      }
    } catch (e) {
      const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
      if (!(e instanceof Berhenti)) console.error(e);
    } finally {
      tulisHasil();
      berjalan = false;
      terakhir = { status: hitung };
      console.table(hitung);
      const belumDibuka = daftarTujuan("TUJUAN_BELUM_DIBUKA", true);
      if (belumDibuka.length) {
        log(`${belumDibuka.length} subsls tujuan masih Listing Selesai -> copy(pindahWilayah.daftarTujuan("TUJUAN_BELUM_DIBUKA")) `
          + "lalu simpan sbg .txt utk buka_wilayah.py --daftar");
      }
      log("Selesai. pindahWilayah.unduh() -> simpan CSV di folder audit/ -> python fasih_sm/pindah_wilayah/pindah_wilayah.py --catat ... --tulis");
    }
    return hitung;
  }

  /** Subsls tujuan unik yang target-nya berstatus `status` (teks satu per baris; `sbgArray` -> array). */
  function daftarTujuan(status, sbgArray) {
    const semua = muatHasil();
    const kode = [...new Set(TARGET.filter((t) => (semua[kunciHasil(t)] || {}).st === status).map((t) => t.t))].sort();
    return sbgArray ? kode : kode.join("\n");
  }

  function ringkasan() {
    const hitung = {};
    const semua = muatHasil();
    for (const t of TARGET) {
      const h = semua[kunciHasil(t)];
      const k = h ? h.st : "(belum diperiksa)";
      hitung[k] = (hitung[k] || 0) + 1;
    }
    console.table(hitung);
    return hitung;
  }

  function unduh() {
    const kolom = ["waktu", "jalan", "bagian", "sumber", "baris", "kunci", "nama", "ids", "id", "status_server", "asal",
      "tujuan", "status", "pengawas", "pencacah", "pesan"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const semua = muatHasil();
    const baris = [];
    for (const t of TARGET) {
      const h = semua[kunciHasil(t)];
      if (!h) continue;
      const isi = { waktu: h.w, jalan: h.j, bagian: BAGIAN, sumber: SUMBER[t.s] != null ? SUMBER[t.s] : t.s, baris: t.b,
        kunci: t.k, nama: t.n, ids: (t.ids || []).join(";"), id: h.id, status_server: h.ss, asal: h.a, tujuan: t.t,
        status: h.st, pengawas: h.pw, pencacah: h.pc, pesan: h.p };
      baris.push(kolom.map((k) => kutip(isi[k])).join(","));
    }
    const blob = new Blob(["﻿" + [kolom.join(","), ...baris].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const label = BAGIAN ? `_bagian-${BAGIAN.replace("/", "-dari-")}` : "";
    a.download = `audit_pindah_wilayah${label}_${new Date().toISOString().slice(0, 19).replace(/[-:]/g, "").replace("T", "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} baris) — pindahkan ke folder audit/ proyek.`);
  }

  global.pindahWilayah = {
    jalankan, ringkasan, unduh, daftarTujuan, target: TARGET, asal: ASAL, konfig: KONFIG,
    get terakhir() { return terakhir; },
    berhenti() {
      hentikan = true;
      log("Akan berhenti di langkah berikutnya (rombongan yang sedang dikirim diselesaikan dulu).");
    },
    hapusHasil() {
      if (confirm("Hapus SELURUH hasil pindahWilayah (v2) yang tersimpan di browser ini?")) {
        localStorage.removeItem(KUNCI_HASIL);
        hasilMemori = null;
      }
    },
  };
  log(`Siap${BAGIAN ? ` — BAGIAN ${BAGIAN}` : ""}${KONFIG.dibuat ? ` (dibuat ${KONFIG.dibuat})` : ""}: ${TARGET.length} target, `
    + `${new Set(TARGET.map((t) => t.t)).size} subsls tujuan, wadah ${ASAL.join(", ")}. `
    + 'Mulai dgn: await pindahWilayah.jalankan({mode: "periksa"})');
})(typeof window !== "undefined" ? window : globalThis);
