/**
 * approve_capi_console.js — assignment CAPI "SUBMITTED BY Pencacah" -> ganti ke PAPI (supaya PML bisa
 * meng-approve lewat fasih-web: web-entry hanya membuka dokumen PAPI) -> sesudah APPROVED, kembalikan ke CAPI.
 * Dijalankan di Console fasih-sm akun ADMIN (Chrome biasa). Approve-nya sendiri oleh approve_capi.py
 * (memanggil approve_pml mode server, dibatasi ke ID yang diganti di sini).
 *
 * CARA PAKAI (tab halaman Data survei: …/app/surveys/<survei>/<periode>/data)
 * ---------------------------------------------------------------------------
 *   await approveCapi.periksa()               // READ-ONLY: daftar CAPI SUBMITTED, jumlah per PML
 *   await approveCapi.kePapi()                // ganti semua (ketik YA); {limit: N} opsional
 *   approveCapi.unduh()                       // CSV approve_capi_<waktu>.csv -> simpan di bahan/
 *   ... python approve_capi/approve_capi.py --daftar-pml <txt> --eksekusi   (approve per PML)
 *   await approveCapi.keCapi()                // kembalikan ke CAPI dokumen yang SUDAH APPROVED
 *   approveCapi.unduh()                       // bukti akhir
 * PARALEL DI SATU BROWSER (berkas .siap.js yang SAMA di beberapa tab/jendela): tab 1 kePapi({bagian: "1/4"}),
 * tab 2 {bagian: "2/4"}, … (dokumen dibagi lewat hash id, saling lepas). Daftar CAPI dibaca SATU tab; tab lain
 * menunggu lalu memakai daftar tersimpannya. keCapi({bagian}) sama. Bagian yang sudah jalan di tab lain / jumlah
 * bagian beda / tanpa bagian selagi bagian lain jalan -> ditolak. Tiap tab menulis ke kuncinya sendiri
 * (approveCapi.hasil.v1<LABEL>.tab-k-dari-n); unduh()/ringkasan() = GABUNGAN semua bagian.
 * PARALEL BEBERAPA PC: approve_capi.py --bagi N membagi daftar PML -> satu .siap.js per bagian; tiap
 * bagian hanya menyentuh PML-nya sendiri, catatan localStorage & CSV unduhan berlabel bagian.
 * Lain: approveCapi.unduhPerPml() (jumlah per PML, bahan --bagi --jumlah), approveCapi.ringkasan(), approveCapi.berhenti(), approveCapi.muatHasil(teksCsv) (pulihkan hasil
 * dari CSV unduhan kalau localStorage hilang / pindah browser).
 * 401 (sesi habis): TIDAK berhenti — menunggu login ulang (tab lain / tab penjaga userscript) TANPA BATAS (tungguLoginMs), lalu lanjut.
 * 429/5xx: jeda adaptif (x2 tiap tolak, maks x8; x0,9 tiap sukses); change-mode 429 -> cek status, kirim ulang (maks 5x);
 * SERVER_SIBUK -> ditunda ke akhir run; baru 3 dokumen sibuk beruntun yang menghentikan batch.
 * LANJUT SESUDAH TERPUTUS (401 lewat batas, tab dimuat ulang): kandidat periksa() disimpan; kePapi() lagi (berkas .siap.js
 * yang sama) melanjutkan sisanya TANPA membaca ulang daftar CAPI ({telusurUlang: true} memaksa baca ulang). Dokumen yang
 * change-mode-nya sudah terkirim sebelum putus (DIGANTI_PAPI_DIKIRIM) diakui PAPI_OK tanpa dikirim ulang.
 *
 * PENGAMAN
 * --------
 * - Daftar PML (DAFTAR_PML, disuntik approve_capi.py --console): hanya dokumen yang petugas saat ininya ada
 *   di daftar yang diganti; lainnya PML_TIDAK_DI_DAFTAR. Daftar kosong -> semua PML (ditanyakan dulu).
 * - Per dokumen, tepat sebelum diganti: detail SEGAR (get-by-assignment-id) harus SUBMITTED BY Pencacah & CAPI.
 *   Sesudahnya detail dibaca ulang: mode PAPI & status tetap -> DIGANTI_PAPI_TERVERIFIKASI.
 * - keCapi HANYA menyentuh dokumen yang tercatat diganti oleh alat ini (bukan dokumen yang aslinya PAPI),
 *   dan hanya yang sudah APPROVED (kecuali {termasukBelumApproved: true}).
 * - Konfirmasi ketik YA tiap run (tanpa gerbang limit 1 — ketetapan user 2026-09-29). Kejanggalan -> batch berhenti.
 * - Catatan hasil disimpan RINGKAS (±100 karakter/dokumen; format lama tetap terbaca). Gagal menyimpan (localStorage
 *   penuh) -> PENYIMPANAN_PENUH, batch berhenti (dulu diam-diam: dokumen jadi PAPI tanpa catatan).
 *
 * API (terekam 2026-09-27, bukan tebakan): POST /assignment-submit/api/assignment/{id}/change-mode
 * body {modes:["PAPI"|"CAPI"]} -> {success, message:"Berhasil. "} (dipakai dialog "Ganti Mode" per baris).
 * Arah CAPI -> PAPI utk dokumen SUBMITTED BELUM pernah dicoba skrip: dokumen pertama yang gagal diverifikasi
 * menghentikan batch.
 */
(function (global) {
  "use strict";

  const DAFTAR_PML = /*__DAFTAR_PML__*/[];
  const LABEL = /*__LABEL__*/""; // ".bagian-K-dari-N" (approve_capi.py --bagi): catatan & unduhan terpisah per bagian

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_approve_capi_console.js
  // -------------------------------------------------------------------------
  const PANJANG_HALAMAN = 150; // datatable analytic menolak length > 150
  const BATAS_ULANG = 10;         // request BACA yang 429/5xx diulang s.d. ini (±7 mnt total) sebelum SERVER_SIBUK
  const MAKS_SIBUK_BERUNTUN = 3;  // dokumen SERVER_SIBUK beruntun sebanyak ini -> batch berhenti (satu-dua = dilewati)
  const HTTP_SIBUK = new Set([0, 429, 502, 503, 504]);
  const SUBMITTED = "SUBMITTED BY Pencacah";
  const ST = {
    PAPI_OK: "DIGANTI_PAPI_TERVERIFIKASI",
    PAPI_BELUM: "DIGANTI_PAPI_BELUM_TERVERIFIKASI",
    // change-mode ke PAPI sudah dikirim, verifikasi belum selesai (run terputus: 401/tab ditutup). Run berikut yang
    // mendapati dokumen ini sudah PAPI mencatatnya PAPI_OK (tanpa kirim ulang) — tanpa tanda ini dokumen itu
    // dianggap "PAPI sejak awal" -> tidak di-approve approve_capi.py & tidak dikembalikan keCapi.
    PAPI_KIRIM: "DIGANTI_PAPI_DIKIRIM",
    CAPI_OK: "DIKEMBALIKAN_CAPI_TERVERIFIKASI",
    CAPI_BELUM: "DIKEMBALIKAN_CAPI_BELUM_TERVERIFIKASI",
  };
  // Hasil pemeriksaan awal yang membuat dokumen bukan kandidat lagi (dilewati saat MELANJUTKAN daftar tersimpan).
  const CEGAH_TUNTAS = ["BUKAN_SUBMITTED", "MODE_LAIN"];
  const KOLOM_CSV = ["id", "kode_identitas", "nama", "pml", "status", "status_dokumen", "mode", "diganti", "dikembalikan", "pesan"];
  // Status yang menghentikan batch (anomali: jangan diteruskan ke dokumen lain).
  // SERVER_SIBUK TIDAK di sini: dokumen itu dilewati & dicoba sekali lagi di akhir run; baru MAKS_SIBUK_BERUNTUN
  // dokumen sibuk berturut-turut yang menghentikan batch (dulu satu 429 saat change-mode = seluruh batch berhenti).
  const BERHENTI = new Set([ST.PAPI_BELUM, ST.CAPI_BELUM, "STATUS_BERUBAH", "GANTI_DITOLAK", "RESPONS_TIDAK_DIKENAL",
    "SESI_DITOLAK"]);

  const norm = (s) => String(s == null ? "" : s).trim().toLowerCase();

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

  /** Body datatable: status (bawaan SUBMITTED BY Pencacah; null = semua) + mode, satu jendela tanggal dibuat (ISO penuh). */
  function bodyDaftar(periode, start, length, dari, sampai, mode, cari, status = SUBMITTED) {
    const extra = { surveyPeriodId: periode, assignmentErrorStatusType: -1, assignmentStatusAlias: status };
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

  /** Tunggu sebelum mengulang request yang kena 429/5xx: Retry-After server, atau 5, 10, 20, 40, 60, 60, … dtk. */
  function jedaUlang(ke, retryAfter) {
    const detik = Number(retryAfter);
    if (retryAfter != null && retryAfter !== "" && Number.isFinite(detik) && detik >= 0) {
      return Math.min(Math.max(detik * 1000, 3000), 300000);
    }
    return Math.min(5000 * 2 ** ke, 60000);
  }

  /** Laju adaptif: semua jeda dikali faktor ini — x2 tiap 429/5xx/gagal jaringan (maks x8), x0,9 tiap sukses (min x1).
   *  Jadi jeda bawaan bisa kecil: melambat sendiri saat server menolak, cepat lagi saat lancar. */
  function faktorBaru(faktor, status) {
    if (HTTP_SIBUK.has(status)) return Math.min(8, faktor * 2);
    if (status >= 200 && status < 300) return Math.max(1, faktor * 0.9);
    return faktor;
  }

  /** Item datatable -> kandidat {id, kode, nama, pml, peran, alias, mode}. */
  function kandidatDari(it) {
    if (!it || !it.id) return null;
    return {
      id: String(it.id), kode: String(it.codeIdentity || "").replace(/\s+/g, " ").trim(), nama: it.data1 || "",
      pml: norm(it.currentUserUsername), peran: String(it.currentUserSurveyRoleName || ""),
      alias: it.assignmentStatusAlias || "", mode: modeDari(it),
    };
  }

  /** Kandidat -> keputusan awal (sebelum detail): SIAP | TANPA_PML | PML_TIDAK_DI_DAFTAR | SUDAH_DIPROSES. */
  function putuskanKandidat(k, daftarPml, hasil) {
    const lama = hasil && hasil[k.id];
    if (lama && [ST.PAPI_OK, ST.PAPI_BELUM, ST.CAPI_OK, ST.CAPI_BELUM].includes(lama.status)) {
      return { status: "SUDAH_DIPROSES", pesan: `tercatat ${lama.status}` };
    }
    if (!k.pml) return { status: "TANPA_PML", pesan: "petugas saat ini kosong — tidak ada PML yang bisa meng-approve" };
    if (k.peran && !/pengawas/i.test(k.peran)) {
      return { status: "TANPA_PML", pesan: `petugas saat ini ${k.pml} berperan ${k.peran}, bukan Pengawas` };
    }
    if (daftarPml && daftarPml.length && !daftarPml.includes(k.pml)) {
      return { status: "PML_TIDAK_DI_DAFTAR", pesan: `PML ${k.pml} tidak ada di daftar PML` };
    }
    return { status: "SIAP", pesan: "" };
  }

  /** Respons detail {status, j} -> {ada, alias, mode, pml, kode, nama, pesan}. */
  function nilaiDetail(r) {
    const j = r && r.j;
    const d = r && r.status === 200 && j && j.success === true && j.data && typeof j.data === "object" ? j.data : null;
    if (!d) {
      const pesan = j && (j.message || j.error) ? String(j.message || j.error) : String((r && r.teks) || "").slice(0, 120);
      return { ada: false, alias: "", mode: "", pml: "", kode: "", nama: "", pesan: `HTTP ${r ? r.status : "?"} ${pesan}`.trim() };
    }
    return { ada: true, alias: d.assignment_status_alias || "", mode: modeDari(d), pml: norm(d.current_user_username),
      kode: String(d.code_identity || "").replace(/\s+/g, " ").trim(), nama: d.data1 || "", pesan: "" };
  }

  /** Detail sebelum ganti ke `ke` -> null (boleh) atau {status, pesan}. */
  function cegahSebelum(det, ke, opsi) {
    if (!det.ada) return { status: "TIDAK_TERBACA", pesan: det.pesan };
    const asal = ke === "PAPI" ? "CAPI" : "PAPI";
    if (det.mode === ke) return { status: ke === "PAPI" ? "SUDAH_PAPI" : "SUDAH_CAPI", pesan: `detail sudah ${ke}` };
    if (det.mode && det.mode !== asal) return { status: "MODE_LAIN", pesan: `mode ${det.mode}` };
    if (ke === "PAPI" && det.alias !== SUBMITTED) return { status: "BUKAN_SUBMITTED", pesan: `status ${det.alias || "-"}` };
    if (ke === "CAPI" && !/APPROVED/i.test(det.alias) && !(opsi && opsi.termasukBelumApproved)) {
      return { status: "BELUM_APPROVED", pesan: `status ${det.alias || "-"} — belum di-approve, tetap PAPI` };
    }
    return null;
  }

  function keCsv(baris) {
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    return "\ufeff" + [KOLOM_CSV.join(","), ...baris.map((b) => KOLOM_CSV.map((k) => kutip(b[k])).join(","))].join("\n");
  }

  /** CSV unduhan -> hasil {id: {...}} (utk muatHasil). Pemisah koma, sel dikutip. */
  function dariCsv(teks) {
    const baris = [];
    let sel = "", row = [], kutip = false;
    const s = String(teks || "").replace(/^\ufeff/, "");
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (kutip) {
        if (c === '"' && s[i + 1] === '"') { sel += '"'; i++; } else if (c === '"') kutip = false; else sel += c;
      } else if (c === '"') kutip = true;
      else if (c === ",") { row.push(sel); sel = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && s[i + 1] === "\n") i++;
        row.push(sel); baris.push(row); row = []; sel = "";
      } else sel += c;
    }
    if (sel || row.length) { row.push(sel); baris.push(row); }
    const [judul, ...isi] = baris.filter((r) => r.some((x) => x !== ""));
    if (!judul || !judul.includes("id") || !judul.includes("status")) throw new Error("bukan CSV approve_capi (kolom id/status tidak ada)");
    const hasil = {};
    for (const r of isi) {
      const o = Object.fromEntries(judul.map((k, i) => [k, r[i] || ""]));
      if (o.id) hasil[o.id] = { kode: o.kode_identitas, nama: o.nama, pml: o.pml, status: o.status, statusDok: o.status_dokumen,
        mode: o.mode, diganti: o.diganti, dikembalikan: o.dikembalikan, pesan: o.pesan };
    }
    return hasil;
  }

  /** Kandidat SIAP hasil periksa() -> bentuk ringkas utk localStorage {waktu, pml: [..], d: [[id, indeks pml], ..]}. */
  function padatDaftar(siap, waktu) {
    const pml = [...new Set(siap.map((k) => k.pml))];
    const indeks = new Map(pml.map((p, i) => [p, i]));
    return { waktu, pml, d: siap.map((k) => [k.id, indeks.get(k.pml)]) };
  }

  /** Daftar tersimpan -> {waktu, kandidat} (kandidat berbentuk seperti kandidatDari), null kalau rusak/tidak ada. */
  function uraiDaftar(isi) {
    if (!isi || !Array.isArray(isi.d) || !Array.isArray(isi.pml)) return null;
    return { waktu: isi.waktu || "", kandidat: isi.d.filter((x) => Array.isArray(x) && x[0]).map(([id, i]) => ({
      id: String(id), kode: "", nama: "", pml: isi.pml[i] || "", peran: "", alias: SUBMITTED, mode: "CAPI" })) };
  }

  /** Kandidat daftar tersimpan yang masih perlu dikerjakan kePapi (belum diproses & tidak gugur di pemeriksaan awal). */
  function sisaTersimpan(kandidat, daftarPml, hasil) {
    return kandidat.filter((k) => {
      const lama = hasil && hasil[k.id];
      if (lama && !lama.status && CEGAH_TUNTAS.some((c) => String(lama.pesan || "").startsWith(`${c}:`))) return false;
      return putuskanKandidat(k, daftarPml, hasil).status === "SIAP";
    });
  }

  // ---- Pembagian paralel di Console: {bagian: "k/n"} -> dokumen dibagi lewat hash id (saling lepas, stabil).
  /** "k/n" -> {k, n} (1 <= k <= n) atau null (tanpa bagian). Salah tulis -> Error. */
  function uraiBagian(b) {
    if (b == null || b === "") return null;
    const m = /^\s*(\d+)\s*\/\s*(\d+)\s*$/.exec(String(b));
    if (!m || +m[1] < 1 || +m[1] > +m[2]) throw new Error(`bagian "${b}" tidak valid — tulis mis. "1/4"`);
    return +m[2] === 1 ? null : { k: +m[1], n: +m[2] };
  }
  /** Hash FNV-1a 32-bit id -> bagian 1..n. */
  function bagianDari(id, n) {
    let h = 0x811c9dc5;
    for (const c of String(id)) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
    return (h % n) + 1;
  }
  /** Label kunci localStorage/CSV bagian Console. SENGAJA beda dgn LABEL ".bagian-K-dari-N" dari approve_capi.py --bagi. */
  const labelTab = (b) => (b ? `.tab-${b.k}-dari-${b.n}` : "");
  /** Bagian yang sedang jalan di tab lain (["k/n" | "" = tanpa bagian]) vs bagian ini -> alasan bentrok / "". */
  function bentrokBagian(lain, b) {
    for (const x of lain) {
      if (!x) return "tab lain sedang berjalan TANPA bagian";
      if (!b) return `bagian ${x} sedang berjalan di tab lain — tab ini juga wajib memakai {bagian: "k/${x.split("/")[1]}"}`;
      const y = uraiBagian(x);
      if (y.n !== b.n) return `tab lain memakai pembagian ${x} — semua tab wajib memakai jumlah bagian yang sama (/${y.n})`;
      if (y.k === b.k) return `bagian ${x} sudah berjalan di tab lain`;
    }
    return "";
  }
  /** Kunci hasil milik berkas ini (LABEL sama): kunci dasar + kunci per bagian Console. */
  function kunciMilik(semua, dasar) {
    return semua.filter((x) => x === dasar || (x.startsWith(`${dasar}.tab-`) && /^\.tab-\d+-dari-\d+$/.test(x.slice(dasar.length))));
  }

  // ---- Catatan hasil RINGKAS (localStorage ±5 juta karakter per situs, dipakai bersama alat lain; format panjang
  // ±300 karakter x 22 rb dokumen tidak muat -> dulu gagal tulis DIAM-DIAM). Format lama tetap terbaca.
  const SINGKAT = { [ST.PAPI_OK]: "P", [ST.PAPI_BELUM]: "PB", [ST.PAPI_KIRIM]: "PK", [ST.CAPI_OK]: "C", [ST.CAPI_BELUM]: "CB" };
  const PANJANG = Object.fromEntries(Object.entries(SINGKAT).map(([a, s]) => [s, a]));
  const ALIAS_SINGKAT = { [SUBMITTED]: "S", "APPROVED BY Pengawas": "A" };
  const ALIAS_PANJANG = Object.fromEntries(Object.entries(ALIAS_SINGKAT).map(([a, s]) => [s, a]));
  const MODE_DARI_STATUS = { P: "PAPI", C: "CAPI" };
  const detik = (iso) => (iso && Number.isFinite(Date.parse(iso)) ? Math.round(Date.parse(iso) / 1000) : 0);
  const iso = (d) => (d ? new Date(d * 1000).toISOString() : "");
  const namaDariKode = (kode) => String(kode || "").replace(/^\d{16}\s*-\s*/, "");

  /** Catatan lengkap -> ringkas. Kode identitas hanya disimpan utk status yang bukan tuntas-OK (P/C cukup id). */
  function padatRekam(r) {
    const s = SINGKAT[r.status] || r.status || "";
    const v = {};
    if (s) v.s = s;
    if (r.kode && s !== "P" && s !== "C") v.k = r.kode;
    if (r.pml) v.u = r.pml;
    if (r.statusDok) v.a = ALIAS_SINGKAT[r.statusDok] || r.statusDok;
    if (r.mode && r.mode !== MODE_DARI_STATUS[s]) v.m = r.mode;
    if (detik(r.diganti)) v.g = detik(r.diganti);
    if (detik(r.dikembalikan)) v.c = detik(r.dikembalikan);
    if (r.pesan) v.e = r.pesan;
    if (detik(r.waktu)) v.w = detik(r.waktu);
    return v;
  }
  /** Ringkas (atau format lama) -> catatan lengkap {kode, nama, pml, status, statusDok, mode, diganti, dikembalikan, pesan, waktu}. */
  function uraiRekam(v) {
    if (!v || typeof v !== "object") return null;
    const lama = ["status", "kode", "pml", "statusDok", "pesan", "waktu", "diganti"].some((x) => x in v);
    if (lama) {
      return { kode: v.kode || "", nama: v.nama || namaDariKode(v.kode), pml: v.pml || "", status: v.status || "",
        statusDok: v.statusDok || "", mode: v.mode || "", diganti: v.diganti || "", dikembalikan: v.dikembalikan || "",
        pesan: v.pesan || "", waktu: v.waktu || "" };
    }
    const s = v.s || "";
    return { kode: v.k || "", nama: namaDariKode(v.k), pml: v.u || "", status: PANJANG[s] || s,
      statusDok: ALIAS_PANJANG[v.a] || v.a || "", mode: v.m || MODE_DARI_STATUS[s] || "", diganti: iso(v.g),
      dikembalikan: iso(v.c), pesan: v.e || "", waktu: iso(v.w) };
  }
  /** Beberapa kumpulan catatan (mentah) -> satu {id: catatan lengkap}; per id catatan dgn waktu TERBARU menang
   *  (seri -> kumpulan belakangan). */
  function gabungHasil(kumpulan) {
    const hasil = {};
    for (const isi of kumpulan) {
      for (const [id, v] of Object.entries(isi || {})) {
        const r = uraiRekam(v);
        if (!r) continue;
        if (!hasil[id] || (Date.parse(r.waktu) || 0) >= (Date.parse(hasil[id].waktu) || 0)) hasil[id] = r;
      }
    }
    return hasil;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { ST, SUBMITTED, KOLOM_CSV, BERHENTI, halamanData, modeDari, bodyDaftar, bagiJendela, jedaUlang,
      kandidatDari, putuskanKandidat, nilaiDetail, cegahSebelum, keCsv, dariCsv, padatDaftar, uraiDaftar, sisaTersimpan, faktorBaru,
      uraiBagian, bagianDari, labelTab, bentrokBagian, kunciMilik, padatRekam, uraiRekam, gabungHasil };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman (hanya berjalan di browser)
  // -------------------------------------------------------------------------
  const API = "/app/api";
  // Kunci per berkas .siap.js (LABEL dari --bagi) + per bagian Console (.tab-k-dari-n): tiap tab MENULIS ke kuncinya
  // sendiri, MEMBACA gabungan semua kunci berkas ini (catatan terbaru menang).
  const KUNCI_HASIL = `approveCapi.hasil.v1${LABEL}`;
  const KUNCI_DAFTAR = `approveCapi.daftar.v1${LABEL}`; // SEMUA kandidat periksa() terakhir (bersama utk semua bagian)
  const KUNCI_JALAN = `approveCapi.jalan.v1${LABEL}`;   // tab yang sedang kePapi/keCapi: {id tab: {bagian, t}}
  const KUNCI_MEMBACA = `approveCapi.membaca.v1${LABEL}`; // tab yang sedang membaca daftar CAPI: {tab, t}
  const HIDUP_MS = 3 * 60 * 1000; // tanpa tanda hidup selama ini = tab itu dianggap sudah berhenti/ditutup
  const ID_TAB = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (Math.max(a, b) - a + 1));
  const log = (...a) => console.log("%c[approveCapi]", "color:#b8541d;font-weight:bold", ...a);

  class Berhenti extends Error {
    constructor(kode, pesan) { super(pesan || kode); this.kode = kode; }
  }

  let berjalan = false;
  let hentikan = false;
  let requestTerakhir = 0;
  let kandidatTerakhir = null;
  let kunciTulis = KUNCI_HASIL; // kunci hasil run yang sedang jalan (per bagian)
  let labelJalan = null;        // "k/n" | "" selama kePapi/keCapi aktif di tab ini
  let sedangMembaca = false;    // tab ini sedang membaca daftar CAPI (tab lain menunggu hasilnya)
  let detakTerakhir = 0;

  let faktor = 1;       // laju adaptif (faktorBaru): jeda x1 s.d. x8
  let sesiHabisSejak = 0; // HTTP 401 pertama yang belum pulih (menunggu login ulang di tab lain)

  // Jeda bawaan kecil (user 2026-09-30: "waktu tunggu dipersingkat") — dikali `faktor`, jadi melambat sendiri saat 429.
  const OPSI_BAWAAN = { dari: "2026-01-01T00:00:00.000Z", maksJendela: 900, jarakRequestMs: 400,
    jedaBacaMin: 500, jedaBacaMaks: 1000, jedaTulisMin: 500, jedaTulisMaks: 1000,
    tungguLoginMs: Infinity, // 401: tunggu login ulang (tab lain / tab penjaga) TANPA BATAS; angka ms = batas; 0 = langsung berhenti
    ulangKirim429: 5 };            // change-mode yang dijawab 429: cek status, kirim ulang s.d. sekian kali

  function bacaJson(kunci, bawaan) {
    try { return JSON.parse(localStorage.getItem(kunci) || "null") || bawaan; } catch (e) { return bawaan; }
  }
  /** -> true kalau tersimpan (false: localStorage penuh / diblokir). */
  function tulisJson(kunci, isi) {
    try { localStorage.setItem(kunci, JSON.stringify(isi)); return true; } catch (e) { return false; }
  }
  function semuaKunci() {
    const k = [];
    try { for (let i = 0; i < localStorage.length; i++) k.push(localStorage.key(i)); } catch (e) { /* diblokir */ }
    return k;
  }
  /** Catatan hasil GABUNGAN semua bagian berkas ini: {id: catatan lengkap}. */
  function bacaHasil() {
    const kunci = [KUNCI_HASIL, ...kunciMilik(semuaKunci(), KUNCI_HASIL).filter((x) => x !== KUNCI_HASIL)];
    return gabungHasil(kunci.map((x) => bacaJson(x, {})));
  }
  function catat(id, isi) {
    const lama = bacaHasil()[id] || {};
    const h = bacaJson(kunciTulis, {});
    h[id] = padatRekam({ ...lama, ...isi, waktu: new Date().toISOString() });
    if (!tulisJson(kunciTulis, h)) {
      throw new Berhenti("PENYIMPANAN_PENUH", `catatan dokumen ${id} tidak bisa disimpan di localStorage (penuh?) — `
        + "approveCapi.unduh() SEKARANG (CSV = bukti & bahan approve); dokumen ini dicek ulang di run berikut");
    }
  }

  function cekHenti() {
    if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "approveCapi.berhenti() dipanggil");
  }
  async function tidur(ms) {
    for (const akhir = Date.now() + ms; Date.now() < akhir;) {
      cekHenti();
      detak();
      await sleep(Math.min(1000, akhir - Date.now()));
    }
  }

  // Tab paralel di browser yang sama: tanda jalan per tab (bagian + tanda hidup) supaya bagian yang sama /
  // pembagian yang tumpang tindih tidak jalan dua kali; tanda "membaca" supaya daftar CAPI dibaca SATU tab saja.
  const hidup = (v) => v && Date.now() - v.t < HIDUP_MS;
  function tabLainJalan() {
    return Object.entries(bacaJson(KUNCI_JALAN, {})).filter(([id, v]) => id !== ID_TAB && hidup(v)).map(([, v]) => v.bagian || "");
  }
  function detak(paksa) {
    if ((labelJalan === null && !sedangMembaca) || (!paksa && Date.now() - detakTerakhir < 10000)) return;
    detakTerakhir = Date.now();
    if (labelJalan !== null) {
      const j = bacaJson(KUNCI_JALAN, {});
      for (const [id, v] of Object.entries(j)) if (!hidup(v)) delete j[id];
      j[ID_TAB] = { bagian: labelJalan, t: Date.now() };
      tulisJson(KUNCI_JALAN, j);
    }
    if (sedangMembaca) tulisJson(KUNCI_MEMBACA, { tab: ID_TAB, t: Date.now() });
  }
  function lepasJalan() {
    const j = bacaJson(KUNCI_JALAN, {});
    delete j[ID_TAB];
    tulisJson(KUNCI_JALAN, j);
  }
  function lepasMembaca() {
    const m = bacaJson(KUNCI_MEMBACA, null);
    if (m && m.tab === ID_TAB) tulisJson(KUNCI_MEMBACA, null);
  }
  if (typeof global.addEventListener === "function") {
    global.addEventListener("pagehide", () => { if (labelJalan !== null) lepasJalan(); if (sedangMembaca) lepasMembaca(); });
  }
  /** Tab lain sedang membaca daftar CAPI -> tunggu sampai selesai (tanda hidupnya hilang). -> true kalau menunggu. */
  async function tungguPembacaLain() {
    const m = bacaJson(KUNCI_MEMBACA, null);
    if (!hidup(m) || m.tab === ID_TAB) return false;
    log("⏳ Tab lain sedang membaca daftar CAPI — menunggu hasilnya supaya daftar tidak dibaca dua kali...");
    for (let v = m; hidup(v) && v.tab !== ID_TAB; v = bacaJson(KUNCI_MEMBACA, null)) await tidur(5000);
    return true;
  }
  function xsrf() {
    const c = document.cookie.split("; ").find((x) => x.startsWith("XSRF-TOKEN="));
    return c ? decodeURIComponent(c.slice("XSRF-TOKEN=".length)) : "";
  }

  /** Request mentah dgn jarak minimal. -> {status, j, teks, retryAfter}. */
  async function kirim(o, metode, path, body) {
    for (;;) {
      const r = await kirimSekali(o, metode, path, body);
      if (r.status !== 401) {
        if (sesiHabisSejak) log(`✅ Sesi aktif lagi sesudah ${Math.round((Date.now() - sesiHabisSejak) / 60000)} mnt — lanjut.`);
        sesiHabisSejak = 0;
        return r;
      }
      // 401 = sesi habis, request DITOLAK (tidak diproses) -> aman diulang sesudah login ulang. Tab ini JANGAN dimuat
      // ulang; login di tab lain memperbarui cookie yang sama. Lewat batas -> dikembalikan ke pemanggil (SESI_DITOLAK).
      if (!sesiHabisSejak) {
        sesiHabisSejak = Date.now();
        if (o.tungguLoginMs > 0) {
          log(`🔑 HTTP 401 — sesi fasih-sm habis. Login ulang di TAB LAIN (tab ini JANGAN dimuat ulang), atau biarkan tab `
            + `penjaga (userscript fasih_login_otomatis) melakukannya; skrip lanjut sendiri begitu sesi aktif lagi `
            + `(menunggu ${Number.isFinite(o.tungguLoginMs) ? `s.d. ${Math.round(o.tungguLoginMs / 60000)} mnt` : "tanpa batas; berhenti: .berhenti()"}).`);
        }
      }
      // Sinyal utk tab penjaga (userscript fasih_sm/login_otomatis, origin sama): login ulang SEKARANG.
      try { localStorage.setItem("fasihSesi.minta.v1", JSON.stringify({ t: Date.now() })); } catch (e) { /* penuh/diblokir */ }
      if (Date.now() - sesiHabisSejak >= o.tungguLoginMs) return r;
      await tungguPulih(20000);
    }
  }

  let pulihTerpakai = 0; // sinyal pulih terakhir yang sudah membangunkan tab ini (tidak dipakai dua kali)
  /** Tunggu s.d. `ms`, tapi bangun SEGERA saat tab penjaga (userscript) menulis sinyal sesi pulih yang baru. */
  async function tungguPulih(ms) {
    for (const akhir = Date.now() + ms; Date.now() < akhir;) {
      await tidur(Math.min(1000, akhir - Date.now()));
      let p = null;
      try { p = JSON.parse(localStorage.getItem("fasihSesi.pulih.v1") || "null"); } catch (e) { /* rusak */ }
      if (p && p.t > Math.max(sesiHabisSejak, pulihTerpakai)) {
        pulihTerpakai = p.t;
        return;
      }
    }
  }

  async function kirimSekali(o, metode, path, body) {
    const tunggu = requestTerakhir + o.jarakRequestMs * faktor - Date.now();
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
    faktor = faktorBaru(faktor, status);
    let j = null;
    try { j = JSON.parse(teks); } catch (e) { /* bukan JSON */ }
    return { status, j, teks, retryAfter };
  }

  function sesiDitolak(o) {
    return new Berhenti("SESI_DITOLAK", `HTTP 401 — sesi habis${o.tungguLoginMs > 0 ? ` & tidak pulih dalam ${Math.round(o.tungguLoginMs / 60000)} mnt` : ""}: `
      + "login ulang fasih-sm, muat ulang halaman Data, tempel berkas .siap.js yang SAMA, lalu kePapi()/keCapi() lagi "
      + "(bagian yang sama) — dilanjutkan dari daftar tersimpan, yang sudah dipindah dilewati, tanpa menelusuri ulang");
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
      if (r.status === 401) throw sesiDitolak(o);
      return r;
    }
  }

  async function bacaDaftar(o, ctx, start, dari, sampai, mode, cari, status = SUBMITTED) {
    const r = await baca(o, "POST", "/analytic/api/v2/assignment/datatable-all-user-survey-periode",
      bodyDaftar(ctx.periode, start, PANJANG_HALAMAN, dari, sampai, mode, cari, status));
    if (r.status === 403) throw new Berhenti("SESI_DITOLAK", "HTTP 403 di datatable — login ulang fasih-sm");
    if (r.status !== 200 || !r.j || !Array.isArray(r.j.searchData) || typeof r.j.totalHit !== "number") {
      throw new Berhenti("RESPONS_TIDAK_DIKENAL", `datatable HTTP ${r.status}: ${r.teks.slice(0, 150)}`);
    }
    return r.j;
  }

  async function detail(o, id) {
    const r = await baca(o, "GET", `/assignment-general/api/assignment/get-by-assignment-id?assignmentId=${encodeURIComponent(id)}`);
    return nilaiDetail(r);
  }

  /** Mode dokumen kalau detail tidak memuatnya: tabel Data dicari dgn kode identitas (semua status & mode). */
  async function modeDariTabel(o, ctx, id, kode) {
    if (!kode) return "";
    try {
      const j = await bacaDaftar(o, ctx, 0, null, null, null, kode, null);
      const it = j.searchData.find((x) => String(x.id) === String(id));
      return it ? modeDari(it) : "";
    } catch (e) {
      if (e instanceof Berhenti && e.kode !== "RESPONS_TIDAK_DIKENAL") throw e;
      return "";
    }
  }

  async function detailLengkap(o, ctx, id, kode) {
    const det = await detail(o, id);
    if (det.ada && !det.mode) det.mode = await modeDariTabel(o, ctx, id, det.kode || kode);
    return det;
  }

  /** Semua CAPI SUBMITTED (per jendela tanggal dibuat, batas paging ±1.000). -> {items: Map, total, tidakUtuh}. */
  async function bacaSemuaCapi(o, ctx) {
    const dok = new Map();
    const tidakUtuh = [];
    const simpan = (items, ids) => {
      for (const it of items) {
        const k = kandidatDari(it);
        if (k) { dok.set(k.id, k); ids.add(k.id); }
      }
    };
    const semua = await bacaDaftar(o, ctx, 0, null, null, "CAPI");
    log(`READ-ONLY: membaca CAPI "${SUBMITTED}" (server menyebut ${semua.totalHit}${semua.totalHit >= 1000 ? "+ — bisa terpotong, dibaca per jendela" : ""})...`);
    const antre = [[o.dari, new Date(Date.now() + 3600 * 1000).toISOString()]];
    let jumlahJendela = 0;
    while (antre.length) {
      cekHenti();
      const [a, b] = antre.shift();
      await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks) * faktor);
      const awal = await bacaDaftar(o, ctx, 0, a, b, "CAPI");
      if (awal.totalHit > o.maksJendela && Date.parse(b) - Date.parse(a) >= 60000) {
        antre.unshift(...bagiJendela(a, b));
        continue;
      }
      const ids = new Set();
      simpan(awal.searchData, ids);
      for (let start = PANJANG_HALAMAN; start < awal.totalHit; start += PANJANG_HALAMAN) {
        await tidur(acak(o.jedaBacaMin, o.jedaBacaMaks) * faktor);
        const j = await bacaDaftar(o, ctx, start, a, b, "CAPI");
        if (!j.searchData.length) break;
        simpan(j.searchData, ids);
      }
      if (ids.size < awal.totalHit) tidakUtuh.push(`${a}..${b}: ${ids.size}/${awal.totalHit}`);
      jumlahJendela += awal.totalHit;
    }
    return { dok, total: Math.max(semua.totalHit, jumlahJendela), tidakUtuh };
  }

  function daftarPmlAktif(o) {
    return (o.pml || DAFTAR_PML || []).map(norm).filter(Boolean);
  }

  async function periksa(opsi = {}) {
    const o = { ...OPSI_BAWAAN, ...opsi };
    const ctx = cekHalaman();
    if (!ctx || berjalan) return null;
    berjalan = true;
    hentikan = false;
    sedangMembaca = true;
    detak(true);
    try {
      const r = await bacaSemuaCapi(o, ctx);
      const hasil = bacaHasil();
      const daftar = daftarPmlAktif(o);
      const per = {};
      const perPml = {};
      const siap = [];
      for (const k of r.dok.values()) {
        const p = putuskanKandidat(k, daftar, hasil);
        per[p.status] = (per[p.status] || 0) + 1;
        const kunci = k.pml || "(kosong)";
        perPml[kunci] = perPml[kunci] || { SIAP: 0, lain: 0, peran: k.peran || "" };
        perPml[kunci][p.status === "SIAP" ? "SIAP" : "lain"]++;
        if (p.status === "SIAP") siap.push(k);
      }
      siap.sort((a, b) => (a.pml + a.kode).localeCompare(b.pml + b.kode));
      kandidatTerakhir = { siap, semua: r.dok, waktu: Date.now(), perPml };
      try {
        localStorage.setItem(KUNCI_DAFTAR, JSON.stringify(padatDaftar(siap, new Date().toISOString())));
      } catch (e) {
        log("⚠️ Daftar kandidat tidak bisa disimpan (localStorage penuh?) — kalau kePapi terputus, run berikut membaca ulang dari server.");
      }
      log(`Terbaca ${r.dok.size}/${r.total} dokumen CAPI SUBMITTED. Keputusan:`, per);
      if (r.tidakUtuh.length) log(`⚠️ ${r.tidakUtuh.length} jendela tidak utuh: ${r.tidakUtuh.join("; ")} — jalankan periksa() lagi nanti`);
      console.table(perPml);
      if (!daftar.length) log("⚠️ DAFTAR PML kosong — semua PML ikut. Batasi: approveCapi.kePapi({pml: ['a@x', ...]}) atau tempel ulang berkas .siap.js dari approve_capi.py --console.");
      else {
        const tanpa = daftar.filter((p) => !perPml[p]);
        if (tanpa.length) log(`PML di daftar tanpa dokumen CAPI SUBMITTED: ${tanpa.join(", ")}`);
      }
      log(`SIAP diganti ke PAPI: ${siap.length}. Lanjut: await approveCapi.kePapi()  (paralel: kePapi({bagian: "1/4"}) … "4/4")`);
      return { terbaca: r.dok.size, total: r.total, siap: siap.length, per };
    } catch (e) {
      laporGalat(e);
      return null;
    } finally {
      berjalan = false;
      sedangMembaca = false;
      lepasMembaca();
    }
  }

  function cekHalaman() {
    const ctx = halamanData(location.pathname);
    if (location.host !== "fasih-sm.bps.go.id" || !ctx) {
      log("⛔ Buka dulu halaman Data survei di fasih-sm (…/app/surveys/<survei>/<periode>/data), lalu tempel ulang.");
      return null;
    }
    if (berjalan) { log("Masih berjalan — tunggu selesai atau approveCapi.berhenti()."); return null; }
    return ctx;
  }

  function laporGalat(e) {
    const kode = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
    log(`⛔ ${kode}: ${e && e.message ? e.message : e}`);
    if (!(e instanceof Berhenti)) console.error(e);
  }

  /** Ganti mode satu dokumen `ke` + verifikasi. -> status akhir. */
  async function gantiSatu(o, ctx, k, ke) {
    const det = await detailLengkap(o, ctx, k.id, k.kode);
    const cegah = cegahSebelum(det, ke, o);
    const dasar = { kode: det.kode || k.kode, nama: det.nama || k.nama, pml: det.pml || k.pml, statusDok: det.alias, mode: det.mode };
    k.kode = dasar.kode;
    if (cegah && ke === "PAPI" && cegah.status === "SUDAH_PAPI" && (bacaHasil()[k.id] || {}).status === ST.PAPI_KIRIM) {
      // change-mode alat ini sudah terkirim di run yang terputus -> sekarang terbukti PAPI (tanpa kirim ulang).
      catat(k.id, { ...dasar, status: ST.PAPI_OK, pesan: `PAPI terbukti saat melanjutkan run yang terputus (status ${det.alias || "-"})` });
      return ST.PAPI_OK;
    }
    if (cegah) {
      // Dokumen yang sudah PAPI sebelum alat ini menyentuhnya TIDAK dicatat sbg "diganti" (keCapi tak boleh menyentuhnya).
      if (ke === "CAPI" || cegah.status !== "SUDAH_PAPI") catat(k.id, { ...dasar, ...(ke === "CAPI" && cegah.status === "SUDAH_CAPI" ? { status: ST.CAPI_OK } : {}), pesan: `${cegah.status}: ${cegah.pesan}` });
      return cegah.status;
    }
    if (ke === "PAPI" && !det.mode) {
      catat(k.id, { ...dasar, pesan: "MODE_TIDAK_TERBACA: detail & tabel Data tidak memuat mode" });
      return "MODE_TIDAK_TERBACA";
    }
    if (ke === "CAPI" && det.mode !== "PAPI") {
      catat(k.id, { ...dasar, pesan: `MODE_TIDAK_TERBACA: mode '${det.mode || "-"}'` });
      return "MODE_TIDAK_TERBACA";
    }
    const statusSebelum = det.alias;
    const urlGanti = `/assignment-submit/api/assignment/${encodeURIComponent(k.id)}/change-mode`;
    let r = await kirim(o, "POST", urlGanti, { modes: [ke] });
    // 429 = ditolak pembatas laju (TIDAK diproses): tunggu, pastikan dokumen belum berubah, lalu kirim ulang.
    for (let u = 0; r.status === 429 && u < o.ulangKirim429; u++) {
      const ms = jedaUlang(u, r.retryAfter);
      log(`⏳ change-mode HTTP 429 — tunggu ${Math.round(ms / 1000)} dtk, cek status, kirim ulang (${u + 1}/${o.ulangKirim429})`);
      await tidur(ms);
      const cek = await detailLengkap(o, ctx, k.id, dasar.kode);
      if (cek.ada && cek.mode === ke) { r = { status: 200, j: { success: true }, teks: "", retryAfter: null }; break; }
      if (!cek.ada || cek.alias !== statusSebelum) break; // keadaan berubah -> jalur verifikasi di bawah yang memutuskan
      r = await kirim(o, "POST", urlGanti, { modes: [ke] });
    }
    if (r.status === 401) throw sesiDitolak(o);
    const sementara = HTTP_SIBUK.has(r.status);
    if (!sementara && !(r.status === 200 && r.j && r.j.success === true)) {
      const pesan = `HTTP ${r.status} ${(r.j && (r.j.message || r.j.error)) || r.teks.slice(0, 150)}`;
      if (r.status === 403) throw new Berhenti("SESI_DITOLAK", pesan);
      catat(k.id, { ...dasar, pesan: `GANTI_DITOLAK: ${pesan}` });
      return "GANTI_DITOLAK";
    }
    // Dicatat SEBELUM verifikasi: run yang terputus di sini (401, tab ditutup) tetap mengenali dokumen ini sbg
    // diganti alat ini (ST.PAPI_KIRIM) — lihat penanganan SUDAH_PAPI di atas.
    if (ke === "PAPI") catat(k.id, { ...dasar, status: ST.PAPI_KIRIM, diganti: new Date().toISOString(), pesan: "change-mode dikirim — belum diverifikasi" });
    if (sementara) log(`⏳ change-mode HTTP ${r.status || "gagal jaringan"} — TIDAK dikirim ulang; status dibaca dulu.`);
    // Verifikasi: detail segar sampai mode = tujuan (1, 2, 4, 8 dtk; sesudah 5xx/429 yang habis diulang: 10, 20, 30 dtk).
    let akhir = null;
    for (const ms of sementara ? [10000, 20000, 30000] : [1000, 2000, 4000, 8000]) {
      await tidur(ms);
      akhir = await detailLengkap(o, ctx, k.id, dasar.kode);
      if (akhir.ada && akhir.mode === ke) break;
    }
    const stOk = ke === "PAPI" ? ST.PAPI_OK : ST.CAPI_OK;
    const stBelum = ke === "PAPI" ? ST.PAPI_BELUM : ST.CAPI_BELUM;
    const cap = ke === "PAPI" ? { diganti: new Date().toISOString() } : { dikembalikan: new Date().toISOString() };
    if (akhir && akhir.ada && akhir.mode === ke) {
      if (akhir.alias !== statusSebelum) {
        catat(k.id, { ...dasar, ...cap, status: stOk, statusDok: akhir.alias, mode: ke,
          pesan: `STATUS_BERUBAH: ${statusSebelum} -> ${akhir.alias}` });
        return "STATUS_BERUBAH";
      }
      catat(k.id, { ...dasar, ...cap, status: stOk, statusDok: akhir.alias, mode: ke, pesan: sementara ? `respons HTTP ${r.status}, tapi mode terbukti ${ke}` : "" });
      return stOk;
    }
    if (sementara && akhir && akhir.ada && akhir.mode !== ke) {
      catat(k.id, { ...dasar, status: "", pesan: `SERVER_SIBUK: change-mode HTTP ${r.status}, mode tetap ${akhir.mode || "-"} — jalankan lagi nanti` });
      return "SERVER_SIBUK";
    }
    catat(k.id, { ...dasar, ...cap, status: stBelum, pesan: `server menjawab sukses, tapi mode terbaca '${akhir ? akhir.mode || "-" : "?"}' (${akhir ? akhir.pesan : ""})` });
    return stBelum;
  }

  async function jalankanArah(ke, opsi) {
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
    labelJalan = b ? `${b.k}/${b.n}` : "";
    kunciTulis = KUNCI_HASIL + labelTab(b);
    detak(true);
    try {
      return await jalankanBagian(ke, o, ctx, b);
    } finally {
      labelJalan = null;
      lepasJalan();
    }
  }

  async function jalankanBagian(ke, o, ctx, b) {
    const labelB = b ? `${b.k}/${b.n}` : "";
    const dalamBagian = (k) => !b || bagianDari(k.id, b.n) === b.k;
    const bacaSimpanan = () => {
      try { return uraiDaftar(JSON.parse(localStorage.getItem(KUNCI_DAFTAR) || "null")); } catch (e) { return null; }
    };
    const pilih = (kandidat) => sisaTersimpan(kandidat.filter(dalamBagian), daftarPmlAktif(o), bacaHasil());
    let daftar;
    if (ke === "PAPI") {
      if (kandidatTerakhir && Date.now() - kandidatTerakhir.waktu <= 30 * 60 * 1000 && !o.telusurUlang) {
        daftar = pilih(kandidatTerakhir.siap);
      } else {
        // Lanjutkan daftar tersimpan (run terputus: 401, tab dimuat ulang; atau dibaca tab lain) TANPA membaca ulang.
        let simpanan = o.telusurUlang ? null : bacaSimpanan();
        let sisa = simpanan ? pilih(simpanan.kandidat) : [];
        if (!sisa.length && !o.telusurUlang && await tungguPembacaLain()) {
          simpanan = bacaSimpanan();
          sisa = simpanan ? pilih(simpanan.kandidat) : [];
        }
        if (sisa.length) {
          log(`▶️ Melanjutkan daftar tersimpan (${simpanan.waktu}${labelB ? `, bagian ${labelB}` : ""}): ${sisa.length} dari `
            + `${simpanan.kandidat.length} kandidat belum diproses — daftar CAPI TIDAK dibaca ulang. {telusurUlang: true} = baca ulang dari server.`);
          daftar = sisa;
        } else {
          log(simpanan ? "Daftar tersimpan sudah tuntas — membaca daftar CAPI SUBMITTED baru..." : "Daftar CAPI belum dibaca — membaca...");
          const p = await periksa(o);
          if (!p) return null;
          daftar = pilih(kandidatTerakhir.siap);
        }
      }
    } else {
      daftar = Object.entries(bacaHasil()).filter(([, v]) => [ST.PAPI_OK, ST.PAPI_BELUM, ST.PAPI_KIRIM].includes(v.status))
        .map(([id, v]) => ({ id, kode: v.kode || "", nama: v.nama || "", pml: v.pml || "" })).filter(dalamBagian);
      if (o.pml) {
        const p = o.pml.map(norm);
        daftar = daftar.filter((k) => p.includes(norm(k.pml)));
      }
    }
    const limit = o.limit || daftar.length;
    log(`${ke === "PAPI" ? "🔁 CAPI -> PAPI" : "↩️ PAPI -> CAPI (hanya yang diganti alat ini & sudah APPROVED)"}`
      + `${labelB ? ` bagian ${labelB}` : ""}: ${daftar.length} kandidat, limit ${limit}.`);
    if (!daftar.length) return { diproses: 0 };
    const n = Math.min(limit, daftar.length);
    if ((prompt(`Ketik YA utk mengganti mode ${n} dokumen ke ${ke}${labelB ? ` (bagian ${labelB})` : ""}:`) || "").trim().toUpperCase() !== "YA") {
      log("Dibatalkan — tidak ada yang diubah.");
      return null;
    }
    berjalan = true;
    hentikan = false;
    const hitung = {};
    let dikirim = 0;
    let sibukBeruntun = 0;
    const antrian = [...daftar]; // dokumen SERVER_SIBUK ditaruh lagi di belakang (dicoba sekali lagi)
    try {
      for (let i = 0; i < antrian.length; i++) {
        const k = antrian[i];
        cekHenti();
        if (dikirim >= limit) break;
        const st = await gantiSatu(o, ctx, k, ke);
        sibukBeruntun = st === "SERVER_SIBUK" ? sibukBeruntun + 1 : 0;
        const tunda = st === "SERVER_SIBUK" && !k.ditunda && sibukBeruntun < MAKS_SIBUK_BERUNTUN;
        if (tunda) {
          k.ditunda = true;
          antrian.push(k);
        } else {
          hitung[st] = (hitung[st] || 0) + 1;
        }
        const n = Object.values(hitung).reduce((a, b) => a + b, 0);
        log(`[${n}] ${st.padEnd(38)} ${k.id.slice(0, 8)} ${k.pml || "-"} ${k.kode || k.nama}${tunda ? " — dicoba lagi di akhir run" : ""}`);
        const menulis = [ST.PAPI_OK, ST.CAPI_OK, ST.PAPI_BELUM, ST.CAPI_BELUM, "STATUS_BERUBAH", "GANTI_DITOLAK", "SERVER_SIBUK"].includes(st);
        if (menulis && !tunda) dikirim++;
        if (BERHENTI.has(st)) {
          log(`⛔ ${st} — batch DIHENTIKAN. Periksa dokumen ${k.id} di fasih-sm sebelum menjalankan lagi.`);
          break;
        }
        if (sibukBeruntun >= MAKS_SIBUK_BERUNTUN) {
          log(`⛔ ${sibukBeruntun} dokumen berturut-turut SERVER_SIBUK — batch DIHENTIKAN; jalankan lagi nanti (dilanjutkan dari daftar tersimpan).`);
          break;
        }
        if (menulis) await tidur(acak(o.jedaTulisMin, o.jedaTulisMaks) * faktor);
      }
    } catch (e) {
      laporGalat(e);
    } finally {
      berjalan = false;
      log("Selesai:", hitung, ke === "PAPI"
        ? "Lanjut: approveCapi.unduh() -> simpan CSV di bahan/ -> python approve_capi/approve_capi.py --daftar-pml <txt> --cek"
        : "approveCapi.unduh() utk bukti.");
    }
    return hitung;
  }

  function ringkasan() {
    const per = {};
    for (const v of Object.values(bacaHasil())) per[v.status || "(belum)"] = (per[v.status || "(belum)"] || 0) + 1;
    console.table(per);
    return per;
  }

  function unduh() {
    const h = bacaHasil();
    const baris = Object.entries(h).map(([id, v]) => ({ id, kode_identitas: v.kode, nama: v.nama, pml: v.pml, status: v.status || "",
      status_dokumen: v.statusDok, mode: v.mode, diganti: v.diganti, dikembalikan: v.dikembalikan, pesan: v.pesan }));
    if (!baris.length) return log("Belum ada hasil.");
    const blob = new Blob([keCsv(baris)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `approve_capi${LABEL}_${new Date().toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-")}Z.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} dokumen) — pindahkan ke folder bahan/ proyek.`);
  }

  /** CSV jumlah dokumen per PML hasil periksa() terakhir -> approve_capi.py --bagi N --jumlah <csv>. */
  function unduhPerPml() {
    if (!kandidatTerakhir) return log("Jalankan dulu: await approveCapi.periksa()");
    const baris = Object.entries(kandidatTerakhir.perPml).filter(([p]) => p !== "(kosong)")
      .map(([pml, v]) => `"${pml}",${v.SIAP},${v.lain}`);
    const blob = new Blob(["\ufeffpml,siap,lain\n" + baris.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `jumlah_capi_per_pml${LABEL}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    log(`Diunduh: ${a.download} (${baris.length} PML) -> python approve_capi/approve_capi.py --daftar-pml <txt> --bagi N --jumlah <csv>`);
  }

  function muatHasil(teks) {
    const baru = dariCsv(teks);
    const gabung = bacaHasil();
    const h = bacaJson(KUNCI_HASIL, {});
    const kini = new Date().toISOString();
    let n = 0;
    for (const [id, v] of Object.entries(baru)) {
      const ada = gabung[id];
      if (!ada || !ada.status || (v.status === ST.CAPI_OK)) { h[id] = padatRekam({ ...(ada || {}), ...v, waktu: kini }); n++; }
    }
    if (!tulisJson(KUNCI_HASIL, h)) return log("⛔ PENYIMPANAN_PENUH: catatan CSV tidak bisa disimpan di localStorage (penuh?).");
    log(`${n} catatan dimuat dari CSV.`);
    return ringkasan();
  }

  global.approveCapi = {
    periksa,
    kePapi: (opsi = {}) => jalankanArah("PAPI", opsi),
    keCapi: (opsi = {}) => jalankanArah("CAPI", opsi),
    ringkasan, unduh, unduhPerPml, muatHasil,
    berhenti() { hentikan = true; log("Akan berhenti di langkah berikutnya."); },
  };
  log(`Siap${LABEL ? " (" + LABEL.slice(1) + ")" : ""}. Daftar PML: ${DAFTAR_PML.length ? DAFTAR_PML.length + " akun" : "KOSONG (semua PML)"}. `
    + "Mulai: await approveCapi.kePapi()  (paralel: tab 1 kePapi({bagian: \"1/4\"}), tab 2 \"2/4\", …)");
})(typeof window !== "undefined" ? window : globalThis);
