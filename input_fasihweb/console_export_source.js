/**
 * console_export_source.js — Ekspor manual data BLOK II dari fasih-sm.bps.go.id
 * lewat DevTools Console, dipakai SAAT scraping otomatis (scrape_source.py)
 * kena deteksi bot. Ini bukan pengganti scrape_source.py secara permanen —
 * cuma jalan pintas sementara: kamu browsing manual pakai akun & browser
 * biasa (bukan Playwright), jadi tidak ada automation fingerprint sama
 * sekali. Satu kali jalan = satu assignment (row_id) di URL yang lagi
 * kebuka.
 *
 * CARA PAKAI
 * ----------
 * 1. Pastikan VPN kantor aktif, login manual biasa ke fasih-sm (bukan lewat
 *    script apapun).
 * 2. Buka URL assignment yang mau diambil:
 *        https://fasih-sm.bps.go.id/app/assignment/{survey_assignment_id}/{row_assignment_id}
 *    (survey_assignment_id dari kolom "link" di backlog CSV, row_assignment_id
 *    dari kolom "assignment_id" — lihat data_loader.py). Tunggu sampai teks
 *    "Loading Data..." hilang dan halaman benar-benar selesai render.
 * 3. F12 -> tab Console -> tempel SELURUH isi file ini -> Enter.
 * 4. Script akan:
 *      a. Cek apakah ada JSON state tertanam di halaman (paling akurat kalau
 *         ketemu — ini data mentah dari framework-nya, bukan tebakan DOM).
 *      b. Cari label field yang SUDAH diketahui polanya dari config.py/
 *         scrape_source.py punya (nama usaha, nama pengusaha, dst).
 *      c. Kumpulkan SEMUA pasangan label->value yang kelihatan di halaman
 *         (fallback kasar) + semua value <input>/<textarea>/<select> yang
 *         ke-render — buat cross-check manual kalau ada field yang salah
 *         pasang di langkah (b).
 *      d. Khusus rincian 24 (pekerja dibayar/tidak dibayar) — field ini
 *         BELUM ADA di scrape_source.py sama sekali (gap diketahui di
 *         CLAUDE.md), jadi TIDAK ditebak otomatis. Semua baris yang
 *         mengandung kata "dibayar"/"pekerja" dikumpulkan di
 *         `pekerja_candidates` biar kamu petakan manual sekali lihat.
 *      e. console.table hasil field utama (biar bisa dicek sekilas di layar)
 *         dan otomatis download 1 file .json (nama file = assignment id di
 *         URL + timestamp).
 * 5. Cross-check `fields` hasil download terhadap tampilan visual halaman.
 *    Field yang confidence-nya "tidak_ketemu" HARUS diisi manual dari layar,
 *    jangan dari raw_pairs mentah-mentah tanpa dicek (leaf-adjacency itu
 *    heuristik, bisa salah pasang kalau ada ikon/elemen dekoratif di antara
 *    label & value).
 * 6. Ulangi paste-and-run ini tiap ganti ke assignment lain (SPA biasanya
 *    tidak full-reload saat pindah halaman, jadi variabel lama bisa basi —
 *    lebih aman selalu jalankan ulang dari awal per assignment).
 *
 * CATATAN
 * -------
 * - Ini 100% read-only: cuma baca DOM & performance buffer yang SUDAH ada di
 *   browser, TIDAK mengirim request baru apapun. Aman dipakai berulang.
 * - Kalau `network_hints` di bawah nemu URL yang kelihatan kayak API
 *   (mengandung /api/ atau .json), buka tab Network manual, cari request itu,
 *   klik -> tab Response -> copy JSON-nya langsung dari situ. Itu jauh lebih
 *   akurat dari DOM-scrape karena field name-nya asli dari backend, bukan
 *   tebakan label teks. JANGAN fetch ulang URL itu dari console (menambah
 *   request baru bisa memicu deteksi bot lagi) — cukup baca response yang
 *   sudah ke-load.
 */
(function () {
  "use strict";

  const OUT = {
    exported_at: new Date().toISOString(),
    page_url: location.href,
    page_title: document.title,
    embedded_json_state: null,
    fields: {},
    fields_confidence: {},
    pekerja_candidates: [],
    form_values: [],
    raw_pairs: [],
    network_hints: [],
  };

  // --- 1. Cek JSON state tertanam (paling akurat kalau ketemu) ------------
  try {
    const jsonScripts = Array.from(
      document.querySelectorAll('script[type="application/json"], #__NEXT_DATA__, #__NUXT_DATA__')
    );
    const globalKeys = ["__NUXT__", "__INITIAL_STATE__", "__APOLLO_STATE__", "__PRELOADED_STATE__"];
    const found = {};
    for (const el of jsonScripts) {
      try {
        const parsed = JSON.parse(el.textContent);
        found[el.id || el.getAttribute("type") || "script"] = parsed;
      } catch (e) {
        /* bukan JSON valid, lewati */
      }
    }
    for (const key of globalKeys) {
      if (window[key]) found[key] = window[key];
    }
    if (Object.keys(found).length) OUT.embedded_json_state = found;
  } catch (e) {
    OUT.embedded_json_state_error = String(e);
  }

  // --- 2. Bangun daftar "leaf" (elemen tanpa child element, ada teks) -----
  // dipakai buat dua hal: pairing label->value umum, & pencarian label
  // spesifik di langkah 3.
  const leaves = Array.from(document.querySelectorAll("body *")).filter((el) => {
    if (el.children.length > 0) return false;
    const txt = (el.textContent || "").trim();
    return txt.length > 0 && txt.length < 300;
  });

  for (let i = 0; i < leaves.length; i++) {
    const label = leaves[i].textContent.trim();
    const value = leaves[i + 1] ? leaves[i + 1].textContent.trim() : "";
    OUT.raw_pairs.push({ label, value });
  }

  function findValueForLabel(labelSubstr) {
    const idx = leaves.findIndex((el) =>
      el.textContent.trim().toLowerCase().includes(labelSubstr.toLowerCase())
    );
    if (idx === -1) return "";
    for (let j = idx + 1; j < Math.min(idx + 4, leaves.length); j++) {
      const txt = leaves[j].textContent.trim();
      if (txt && txt.toLowerCase() !== labelSubstr.toLowerCase()) return txt;
    }
    return "";
  }

  // --- 3. Field yang polanya sudah diketahui (samakan dgn SourceBlok2 di
  // scrape_source.py) — tetap best-effort, cek confidence sebelum dipakai.
  const KNOWN_LABELS = {
    nama_komersial: "Nama Usaha",
    nama_pengusaha: "Nama Pengusaha",
    jenis_kelamin: "Jenis Kelamin",
    umur: "Umur",
    kegiatan_utama: "kegiatan utama",
    tempat_usaha: "tempat usaha",
    produk_utama: "produk utama",
    jaringan_usaha: "jaringan usaha",
    pakai_internet: "menggunakan internet",
    produk_ramah_lingkungan: "produk ramah lingkungan",
    input_ramah_lingkungan: "input ramah lingkungan",
    karya_seni_budaya: "karya seni",
    izin_edar_bpom: "izin edar",
    mitra_kdkmp: "KDKMP",
    program_mbg: "MBG",
    tahun_mulai_komersial: "tahun mulai",
    no_hp_wa: "No HP",
    rt: "RT",
    rw: "RW",
    // GAP diketahui (belum pernah ke-scrape sama sekali di scrape_source.py) —
    // label ini TEBAKAN dari config.py, verifikasi manual wajib:
    b1_produksi_lokasi: "memproduksi barang",
    b2_layanan_makan_minum: "layanan makan",
    b3_penjualan_barang: "penjualan barang",
  };

  for (const [attr, label] of Object.entries(KNOWN_LABELS)) {
    const val = findValueForLabel(label);
    OUT.fields[attr] = val;
    OUT.fields_confidence[attr] = val ? "ketemu" : "tidak_ketemu";
  }

  // --- 4. Rincian 24 (pekerja dibayar/tdk dibayar) — jangan ditebak,
  // kumpulkan semua kandidat baris buat dipetakan manual.
  OUT.pekerja_candidates = OUT.raw_pairs.filter((p) =>
    /dibayar|pekerja/i.test(p.label)
  );

  // --- 5. Semua value form yang ke-render sbg <input>/<textarea>/<select>
  OUT.form_values = Array.from(document.querySelectorAll("input, textarea, select"))
    .map((el) => ({
      name: el.name || el.id || el.getAttribute("aria-label") || "",
      type: el.tagName.toLowerCase(),
      value: el.value,
    }))
    .filter((x) => x.value);

  // --- 6. Petunjuk network (read-only, cuma baca buffer yang sudah ada) ---
  try {
    OUT.network_hints = performance
      .getEntriesByType("resource")
      .map((r) => r.name)
      .filter((u) => /\/api\/|\.json(\?|$)/i.test(u));
  } catch (e) {
    /* abaikan kalau performance API tidak tersedia */
  }

  // --- 7. Tampilkan ringkas di console + trigger download JSON lengkap ---
  console.log("=== HASIL EKSPOR (lengkap ada di file .json yang otomatis kedownload) ===");
  console.table(
    Object.entries(OUT.fields).map(([field, value]) => ({
      field,
      value,
      confidence: OUT.fields_confidence[field],
    }))
  );
  if (OUT.pekerja_candidates.length) {
    console.log("Kandidat field pekerja (petakan manual ke laki2/perempuan/tdk_dibayar):");
    console.table(OUT.pekerja_candidates);
  }
  if (OUT.network_hints.length) {
    console.log("Kemungkinan URL API (cek tab Network -> Response, JANGAN fetch ulang dari sini):", OUT.network_hints);
  }
  if (OUT.embedded_json_state) {
    console.log("Ketemu JSON state tertanam — ini kemungkinan besar lebih akurat dari fields di atas:", OUT.embedded_json_state);
  }

  window.__FASIH_SM_EXPORT__ = OUT; // tetap bisa diakses manual dari console kalau perlu

  const urlPart = (location.pathname.split("/").filter(Boolean).slice(-2).join("_")) || "unknown";
  const blob = new Blob([JSON.stringify(OUT, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `fasih-sm-export_${urlPart}_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();

  console.log("File JSON sudah didownload:", a.download);
})();
