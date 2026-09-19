/**
 * reset_mitra_console.js — Reset password akun mitra (PPL) di
 * manajemen-mitra.bps.go.id dari DevTools Console Chrome BIASA.
 *
 * Kenapa Console, bukan Playwright: manajemen-mitra login-gated & kemungkinan
 * mendeteksi browser otomatis (seperti fasih-sm). Di sini yang bekerja hanya
 * tab Chrome milikmu yang sudah login, dgn jeda acak antar akun.
 *
 * FILE INI TEMPLATE. Buat versi berisi target:
 *     python reset_mitra/reset_mitra.py --sumber input_usaha.xlsx --console
 * -> reset_mitra_console.siap.js (berisi email PPL -> .gitignore).
 *
 * STRUKTUR akun-mitra (dipetakan 2026-09-14): tabel kolom [NIK, Email, Nama
 * Lengkap, Tanggal Terdaftar, Kelengkapan Data, Status SSO, Status Akun & Aksi];
 * kotak "Cari NIK, Email, Nama Lengkap, atau Sobat ID / Username (min. 5
 * karakter)" — gmail dicari lewat kolom Email; tombol "Reset PW" per baris.
 * Klik "Reset PW" -> panel 2 field: (1) password baru, (2) email yg SUDAH terisi
 * (JANGAN disentuh) -> tombol "Reset Password". Skrip isi field (1) = PASSWORD_BARU.
 *
 * ⚠️⚠️ BELUM diketahui password direset MENJADI apa (default? ditampilkan? dikirim?).
 * Karena itu:
 *   - mode "petakan" & "cocok" READ-ONLY: cari email, baca hasil. TIDAK klik reset.
 *   - mode "manual": manusia yang klik "Reset PW" + konfirmasi (skrip cuma
 *     menyorot tombol & memverifikasi). WAJIB dipakai lebih dulu utk >=1 akun,
 *     amati apa yang terjadi pada password, baru pertimbangkan "otomatis".
 *   - mode "otomatis": klik Reset PW + tombol konfirmasi tunggal; butuh >=1
 *     hasil manual terverifikasi + opsi sayaSudahMelihatDialog:true.
 * Reset password itu SENSITIF & sulit dibatalkan (mitra bisa terkunci) — jangan longgarkan penjagaan ini.
 *
 * CARA PAKAI
 * ----------
 * 1. Chrome biasa, login manajemen-mitra, buka /mitra/akun-mitra.
 * 2. F12 -> Console -> tempel SELURUH isi reset_mitra_console.siap.js -> Enter
 *    (pertama kali Chrome minta ketik: allow pasting).
 * 3. await resetMitra.jalankan({mode: "petakan"})   // 1 email: cari & dump struktur
 *    -> resetMitra.unduhDump()  simpan dump utk dikirim ke pengembang (biar
 *       selektor reset & dialog bisa diisi ke SELEKTOR_RESET).
 * 4. await resetMitra.jalankan({mode: "cocok"})      // cek SEMUA email ketemu 1 mitra (read-only)
 *    -> resetMitra.unduh()      simpan hasil cocok sbg CSV.
 * 5. (setelah SELEKTOR_RESET diisi & diverifikasi)
 *    await resetMitra.jalankan({mode: "manual", limit: 1})   // KAMU klik Reset + konfirmasi
 *    await resetMitra.jalankan({mode: "otomatis", sayaSudahMelihatDialog: true})  // opsional
 *
 * Akun GANDA (1 email -> >1 mitra) TIDAK direset & DILEWATI, batch lanjut (default
 * lewatiGanda:true). Daftarnya dicetak di akhir run. lewatiGanda:false = berhenti.
 *
 * resetMitra.berhenti() / .ringkasan() / .unduh() / .unduhDump() / .hapusHasil()
 */
(function (global) {
  "use strict";

  const TARGET = /*__TARGET__*/[];

  // ==========================================================================
  // SELEKTOR_RESET — diisi dari petakan halaman akun-mitra asli (2026-09-14):
  // tabel kolom [NIK, Email, Nama Lengkap, Tanggal Terdaftar, Kelengkapan Data,
  // Status SSO, Status Akun & Aksi], dgn tombol "Reset PW" per baris.
  //   cariReset(rowEl) -> tombol "Reset PW" di baris mitra yang cocok.
  //   polaDialog -> teks dialog konfirmasi setelah klik (BELUM terverifikasi
  //     bunyinya; default permisif — mode otomatis tetap butuh konfirmasi manusia dulu).
  // ⚠️ BELUM diketahui password direset MENJADI apa. Karena itu mode "manual"
  // (manusia klik "Reset PW" + konfirmasi, lalu baca hasilnya) WAJIB dipakai
  // lebih dulu utk >=1 akun sebelum "otomatis".
  // ==========================================================================
  const SELEKTOR_RESET = {
    cariReset: (rowEl) => {
      if (!rowEl) return null;
      const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      const norm = (t) => (t || "").replace(/\s+/g, " ").trim();
      return [...rowEl.querySelectorAll("button, a")].filter(vis).find((b) =>
        /reset\s*pw|reset\s*password|reset\s*kata\s*sandi/i.test(norm(b.innerText) + " " + (b.getAttribute("aria-label") || ""))) || null;
    },
    polaDialog: /reset|password|kata sandi|sandi/i,
  };

  // Password baru yang di-set ke SEMUA mitra (ketetapan user 2026-09-14; sama
  // dgn FIXED_PASSWORD fasih-web). Disuntikkan reset_mitra.py --console dari
  // inti/config_lokal.py — template ini SENGAJA kosong (ikut git). Bisa ditimpa:
  // jalankan({passwordBaru: "..."}). Kosong -> mode manual/otomatis menolak jalan.
  const PASSWORD_BARU = /*__PASSWORD_BARU__*/"";

  // Klik "Reset PW" TIDAK langsung mereset — membuka dialog berisi FIELD isian
  // password baru, lalu tombol simpan. (Temuan user 2026-09-14: "toast sukses"
  // versi lama false-positive karena label 'password baru' ikut kecocokan —
  // sudah diperbaiki di POLA_SUKSES: hanya toast pasca-simpan, bukan label field.)
  const POLA_SUKSES = /berhasil|sukses|tersimpan|diperbarui|diubah|ter-?update/i;

  // -------------------------------------------------------------------------
  // Logika murni — diuji: node tests/test_reset_mitra_console.js
  // -------------------------------------------------------------------------
  const POLA_TOMBOL_KONFIRMASI = /^\s*(ya|konfirmasi|reset|ubah|ganti|lanjut|lanjutkan|simpan|ok|oke|proses)\b/i;
  const POLA_TOMBOL_BATAL = /batal|tutup|cancel|kembali|^\s*tidak\b/i;

  const STATUS_TUNTAS_LIVE = new Set(["DIRESET_TERVERIFIKASI"]);
  const STATUS_TUNTAS_COCOK = new Set(["COCOK", "COCOK_TEKS", "DIRESET_TERVERIFIKASI"]);
  const STATUS_BERHENTI_SEGERA = new Set([
    "GANDA", "SELEKTOR_BELUM_DIISI", "RESET_TIDAK_ADA", "DIALOG_TIDAK_DIKENAL",
    "TOMBOL_KONFIRMASI_AMBIGU", "FIELD_PASSWORD_TIDAK_ADA", "DIRESET_BELUM_TERVERIFIKASI",
    "KOTAK_CARI_TIDAK_ADA", "DIHENTIKAN_PENGGUNA",
  ]);

  /** Status hasil -> "BERHENTI" (hentikan batch live) | "LEWATI" (akun dilewati,
   *  batch lanjut) | "LANJUT". GANDA (1 email -> >1 mitra) TIDAK pernah direset
   *  (prosesEmail cuma mereset COCOK), jadi melewatinya aman: default lewatiGanda
   *  = true (ketetapan user 2026-09-14) — akun itu dicatat utk ditelusuri manual.
   *  lewatiGanda:false = perilaku lama (batch berhenti di akun ganda pertama). */
  function putuskanStatus(status, { live = true, lewatiGanda = true } = {}) {
    if (status === "GANDA" && lewatiGanda) return "LEWATI";
    if (live && STATUS_BERHENTI_SEGERA.has(status)) return "BERHENTI";
    return "LANJUT";
  }

  class Berhenti extends Error {
    constructor(kode, pesan) {
      super(pesan || kode);
      this.kode = kode;
    }
  }

  const normEmail = (s) => String(s == null ? "" : s).trim().toLowerCase();
  const bersih = (t) => String(t == null ? "" : t).replace(/\s+/g, " ").trim();

  /** email + kandidat baris [{nama, username, email, teks}] -> keputusan.
   *  COCOK (username/email persis, tepat satu) dipakai otomatis; COCOK_TEKS
   *  (email cuma muncul di teks baris) perlu tinjau; GANDA/TIDAK_KETEMU -> stop/skip. */
  function pilihMitra(email, kandidat) {
    const e = normEmail(email);
    if (!e) return { status: "EMAIL_KOSONG", mitra: null, pesan: "email kosong" };
    if (!kandidat || !kandidat.length) return { status: "TIDAK_KETEMU", mitra: null, pesan: "pencarian tidak menemukan mitra" };
    const persis = kandidat.filter((k) => normEmail(k.username) === e || normEmail(k.email) === e);
    if (persis.length === 1) return { status: "COCOK", mitra: persis[0], pesan: "username/email persis" };
    if (persis.length > 1) return { status: "GANDA", mitra: null, pesan: `${persis.length} mitra username/email persis '${e}'` };
    const diTeks = kandidat.filter((k) => (k.teks || "").toLowerCase().includes(e));
    if (diTeks.length === 1) return { status: "COCOK_TEKS", mitra: diTeks[0], pesan: "email hanya muncul di teks baris — tinjau" };
    if (diTeks.length > 1) return { status: "GANDA", mitra: null, pesan: `${diTeks.length} baris memuat '${e}'` };
    return { status: "TIDAK_KETEMU", mitra: null, pesan: `${kandidat.length} baris hasil, tak satu pun memuat '${e}'` };
  }

  function pilihTombolKonfirmasi(teksTombol) {
    const kandidat = [];
    teksTombol.forEach((t, i) => {
      if (POLA_TOMBOL_KONFIRMASI.test(t || "") && !POLA_TOMBOL_BATAL.test(t || "")) kandidat.push(i);
    });
    return kandidat.length === 1 ? kandidat[0] : null;
  }

  /** Dari daftar input dialog "Reset PW" (deskriptor {type,name,placeholder,aria,
   *  value}), pilih field PASSWORD BARU yang harus diisi. Struktur asli (dump user
   *  2026-09-14, akun NAMA MITRA CONTOH): DUA input `type="text"`
   *  `placeholder="Password"` — pembeda satu-satunya = field EMAIL sudah terisi
   *  value ber-'@' (JANGAN disentuh), field password baru masih kosong.
   *  Field email dikecualikan (type email / bertanda email / value ber-'@'). -> {status, indeks}:
   *    PILIH  : tepat 1 kandidat (1 `type=password`, ATAU 0 password & 1 non-email).
   *    KOSONG : 0 kandidat — biasanya belum ter-render (balapan animasi) → polling ulang.
   *    GANDA  : >1 kandidat ambigu — BERHENTI, jangan tebak field mana. */
  function pilihFieldPassword(inputs) {
    const bukanEmail = (i) => {
      const t = ((i.type || "") + " " + (i.name || "") + " " + (i.placeholder || "") + " " + (i.aria || "")).toLowerCase();
      return (i.type || "") !== "email" && !/e-?mail/.test(t) && !/@/.test(i.value || "");
    };
    const nonEmail = inputs.map((i, k) => ({ i, k })).filter((x) => bukanEmail(x.i));
    const pw = nonEmail.filter((x) => (x.i.type || "") === "password");
    if (pw.length === 1) return { status: "PILIH", indeks: pw[0].k };
    if (pw.length > 1) return { status: "GANDA", indeks: -1 };
    if (nonEmail.length === 1) return { status: "PILIH", indeks: nonEmail[0].k };
    if (nonEmail.length === 0) return { status: "KOSONG", indeks: -1 };
    return { status: "GANDA", indeks: -1 };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { TARGET, Berhenti, normEmail, pilihMitra, pilihTombolKonfirmasi, pilihFieldPassword, putuskanStatus };
    return;
  }

  // -------------------------------------------------------------------------
  // Interaksi halaman
  // -------------------------------------------------------------------------
  const KUNCI_HASIL = "resetMitra.hasil.v1";
  const KUNCI_DUMP = "resetMitra.dump.v1";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acak = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const tampak = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const log = (...a) => console.log("%c[resetMitra]", "color:#0277bd;font-weight:bold", ...a);
  const tekanEscape = () => (document.activeElement || document.body).dispatchEvent(
    new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true, cancelable: true }));
  const dialogAktif = () => [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(tampak).pop() || null;
  const teksKontrol = (el) => bersih(el.innerText || el.value || el.getAttribute("aria-label") || "");
  // "Reset Password" ternyata bukan <button> polos (run user 2026-09-14: 0 <button>
  // di panel) — cakup juga <a> & [role=button] & input submit.
  const kontrolKlik = (root) => [...root.querySelectorAll('button, [role="button"], a, input[type="submit"], input[type="button"]')].filter(tampak);

  let hentikan = false;
  let berjalan = false;
  const cekHenti = () => { if (hentikan) throw new Berhenti("DIHENTIKAN_PENGGUNA", "resetMitra.berhenti() dipanggil"); };

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

  function kotakCari() {
    // Placeholder asli akun-mitra: "Cari NIK, Email, Nama Lengkap, atau Sobat ID
    // / Username (min. 5 karakter)...". Wajib memuat kata2 itu & BUKAN kotak
    // "Cari survei atau kegiatan..." di dashboard (mishap 2026-09-14).
    const cocok = (i) => {
      const t = ((i.placeholder || "") + " " + (i.getAttribute("aria-label") || "")).toLowerCase();
      return /(nik|email|sobat|username|nama lengkap)/.test(t) && !/survei|kegiatan/.test(t);
    };
    return [...document.querySelectorAll("input")].filter(tampak).find(cocok) || null;
  }

  function isiInputReact(el, nilai, tekanEnter = false) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    el.focus();
    setter.call(el, "");
    el.dispatchEvent(new Event("input", { bubbles: true }));
    setter.call(el, nilai);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    // Enter HANYA utk kotak cari (memicu filter). JANGAN di field password —
    // bisa men-submit form sebelum field konfirmasi terisi / tombol simpan diklik.
    if (tekanEnter) {
      const o = { key: "Enter", code: "Enter", keyCode: 13, bubbles: true, cancelable: true };
      el.dispatchEvent(new KeyboardEvent("keydown", o));
      el.dispatchEvent(new KeyboardEvent("keyup", o));
    }
  }

  const tandaKonten = () => {
    const t = document.querySelector("main") || document.body;
    return (t.innerText || "").slice(0, 4000);
  };

  async function tungguStabil(diamMs = 1200, batasMs = 12000) {
    let tanda = tandaKonten();
    let sejak = Date.now();
    const akhir = Date.now() + batasMs;
    while (Date.now() < akhir) {
      await sleep(300);
      cekHenti();
      const baru = tandaKonten();
      if (baru !== tanda) { tanda = baru; sejak = Date.now(); }
      else if (Date.now() - sejak >= diamMs) return;
    }
  }

  /** Baca kandidat baris hasil pencarian secara GENERIK (struktur akun-mitra
   *  belum dipetakan). Prioritas: baris <table>; kalau tak ada, elemen yang
   *  memuat email. Tiap kandidat: {nama, username, email, teks, el}. */
  function bacaHasil(email) {
    const e = normEmail(email);
    const out = [];
    const tabel = [...document.querySelectorAll("table")].filter(tampak)[0];
    if (tabel) {
      const head = [...tabel.querySelectorAll("thead th")].map((h) => bersih(h.innerText).toLowerCase());
      const iEmail = head.findIndex((h) => h.startsWith("email"));
      const iNama = head.findIndex((h) => h.includes("nama"));
      const iNik = head.findIndex((h) => h.startsWith("nik"));
      for (const tr of tabel.querySelectorAll("tbody tr")) {
        const teks = bersih(tr.innerText);
        if (!teks) continue;
        const sel = [...tr.querySelectorAll("td")].map((td) => bersih(td.innerText));
        const emailSel = (iEmail >= 0 ? sel[iEmail] : "") || sel.find((s) => /@/.test(s)) || "";
        const resetEl = SELEKTOR_RESET.cariReset(tr);
        out.push({
          nik: iNik >= 0 ? sel[iNik] : "", nama: iNama >= 0 ? sel[iNama] : (sel[0] || ""),
          username: emailSel, email: emailSel, teks, el: tr, punyaReset: !!resetEl,
        });
      }
      if (out.length) return out;
    }
    // Fallback: elemen "kartu" yang memuat email.
    const kartu = [...document.querySelectorAll('li, [role="row"], [class*="card"], [class*="item"], div')]
      .filter((el) => tampak(el) && (el.innerText || "").toLowerCase().includes(e)
        && el.querySelectorAll("*").length < 60);
    // ambil yang paling "kecil" (paling spesifik) memuat email
    kartu.sort((a, b) => a.innerText.length - b.innerText.length);
    for (const el of kartu.slice(0, 5)) {
      const teks = bersih(el.innerText);
      out.push({ nama: teks.slice(0, 40), username: "", email: e, teks, el });
    }
    return out;
  }

  async function cari(email) {
    await tutupKonfirmasiOK(0); // tutup panel "OK" sisa akun sebelumnya (kalau ada) biar tidak menutupi kotak cari
    const kotak = kotakCari();
    if (!kotak) throw new Berhenti("KOTAK_CARI_TIDAK_ADA", "kotak 'Cari NIK, Email, Nama Lengkap...' tidak ditemukan di halaman");
    const sebelum = tandaKonten();
    isiInputReact(kotak, email, true);
    await tunggu(() => tandaKonten() !== sebelum, 15000);
    await tungguStabil();
    return bacaHasil(email);
  }

  function dumpStruktur(email, kandidat) {
    const tampakTeks = (sel) => [...document.querySelectorAll(sel)].filter(tampak)
      .map((el) => bersih(el.innerText)).filter(Boolean);
    const dump = {
      waktu: new Date().toISOString(), email, url: location.href,
      kotak_cari: kotakCari() ? (kotakCari().placeholder || kotakCari().getAttribute("aria-label")) : null,
      jumlah_kandidat: kandidat.length,
      kandidat: kandidat.slice(0, 5).map((k) => ({ nama: k.nama, username: k.username, teks: (k.teks || "").slice(0, 300) })),
      tombol_terlihat: tampakTeks("button").slice(0, 40),
      menuitem_terlihat: tampakTeks('[role="menuitem"]').slice(0, 40),
      dialog: (function () { const d = [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(tampak).pop(); return d ? bersih(d.innerText).slice(0, 400) : null; })(),
      tabel_head: [...(document.querySelector("table") || {}).querySelectorAll ? document.querySelector("table").querySelectorAll("thead th") : []].map((h) => bersih(h.innerText)),
    };
    try { localStorage.setItem(KUNCI_DUMP, JSON.stringify(dump, null, 1)); } catch (e) { /* abaikan */ }
    log("DUMP struktur (kirim ke pengembang lewat resetMitra.unduhDump()):");
    console.log(JSON.stringify(dump, null, 1));
    return dump;
  }

  /** Panel konfirmasi "OK" muncul SETELAH reset berhasil (temuan user 2026-09-14).
   *  Harus ditutup, kalau tidak ia menutupi akun berikutnya & batch macet.
   *  tungguMs>0: tunggu panel muncul (dipakai pasca-reset); 0: cek langsung
   *  (dipakai defensif sebelum pencarian). */
  async function tutupKonfirmasiOK(tungguMs = 4000) {
    const dlg = tungguMs ? await tunggu(dialogAktif, tungguMs, 300) : dialogAktif();
    if (!dlg) return;
    const ok = kontrolKlik(dlg).find((b) => /^\s*(ok|oke|tutup|selesai|mengerti|iya)\s*$/i.test(teksKontrol(b)));
    if (ok) { log(`  tutup panel konfirmasi ('${teksKontrol(ok)}')`); ok.click(); }
    else { tekanEscape(); }
    await tunggu(() => !dialogAktif(), 5000);
  }

  /** Setelah klik "Reset PW": dialog punya 2 field — field password baru & field
   *  EMAIL yang sudah terisi (jangan disentuh, temuan user 2026-09-14). Isi HANYA
   *  field non-email dgn passwordBaru, lalu klik "Reset Password".
   *  IRREVERSIBLE. -> true kalau toast sukses. */
  async function resetDiDialog(passwordBaru) {
    const dlg = await tunggu(dialogAktif, 8000, 300);
    if (!dlg) throw new Berhenti("DIALOG_TIDAK_DIKENAL", "dialog Reset PW tidak muncul setelah klik");
    const teks = bersih(dlg.innerText);
    if (!SELEKTOR_RESET.polaDialog.test(teks)) throw new Berhenti("DIALOG_TIDAK_DIKENAL", `dialog: ${teks.slice(0, 200)}`);

    // Field di dialog bisa MOUNT sesaat SETELAH kontainer dialog muncul (animasi
    // buka): record ke-4 run user 2026-09-14 gagal FIELD_PASSWORD_TIDAK_ADA dgn 0
    // input, padahal akun 1-3 sukses — murni balapan render. Jadi TUNGGU sampai
    // ada field yang bisa diisi (logika pilihFieldPassword, diuji offline), baru
    // putuskan. Deskriptor input dipetakan tipis; keputusan ada di fungsi murni.
    const deskripsi = () => [...dlg.querySelectorAll("input")].filter(tampak)
      .map((el) => ({ el, type: el.type, name: el.name, placeholder: el.placeholder, aria: el.getAttribute("aria-label"), value: el.value }));
    const cariTarget = () => {
      const desk = deskripsi();
      const p = pilihFieldPassword(desk);
      return p.status === "PILIH" ? { target: desk[p.indeks].el, jml: desk.length } : null;
    };
    const dpt = await tunggu(cariTarget, 8000, 300);
    if (!dpt) {
      const desk = deskripsi();
      tekanEscape();
      throw new Berhenti("FIELD_PASSWORD_TIDAK_ADA",
        `field password tidak jelas (${pilihFieldPassword(desk).status}) — input di dialog: `
        + desk.map((i) => (i.type || "text") + "/" + (i.name || i.placeholder || "?") + (/@/.test(i.value || "") ? "=email" : "")).join(", "));
    }
    const { target, jml } = dpt;
    isiInputReact(target, passwordBaru); // HANYA satu field; field email dibiarkan
    await sleep(400);

    const EXACT = /^\s*reset\s*password\s*$/i;
    let tombol = kontrolKlik(dlg);
    let i = tombol.findIndex((b) => EXACT.test(teksKontrol(b)));
    if (i < 0) {
      // Footer aksi kadang dirender di luar node dialog. Cari "Reset Password"
      // persis di SELURUH halaman; pakai HANYA kalau tepat satu.
      const global = kontrolKlik(document).filter((b) => EXACT.test(teksKontrol(b)));
      if (global.length === 1) { tombol = global; i = 0; }
    }
    if (i < 0) { const k = pilihTombolKonfirmasi(tombol.map(teksKontrol)); i = k === null ? -1 : k; }
    if (i < 0) {
      tekanEscape();
      throw new Berhenti("TOMBOL_KONFIRMASI_AMBIGU",
        `kontrol di panel: ${kontrolKlik(dlg).map(teksKontrol)} | 'Reset Password' se-halaman: ${kontrolKlik(document).filter((b) => EXACT.test(teksKontrol(b))).length}`);
    }
    log(`  isi field password (1 dari ${jml} input; email dibiarkan), klik '${teksKontrol(tombol[i])}'`);
    tombol[i].click();
    const sukses = await tunggu(() => POLA_SUKSES.test(document.body.innerText || ""), 12000, 400);
    await tutupKonfirmasiOK(); // panel "OK" pasca-reset — tutup biar akun berikutnya bersih
    return !!sukses;
  }

  // --- penyimpanan hasil ------------------------------------------------------
  function muatHasil() { try { return JSON.parse(localStorage.getItem(KUNCI_HASIL) || "{}"); } catch (e) { return {}; } }
  function simpanHasil(entri) {
    const semua = muatHasil();
    semua[entri.email] = entri;
    try { localStorage.setItem(KUNCI_HASIL, JSON.stringify(semua)); }
    catch (e) { log("⚠️ localStorage penuh — segera resetMitra.unduh()", e); }
  }

  async function prosesEmail(t, o) {
    const hasil = { waktu: new Date().toISOString(), jalan: o.mode, email: t.email,
      baris_sheet: (t.baris || []).join(","), status: "", mitra: "", pesan: "" };
    try {
      const kandidat = await cari(t.email);
      if (o.mode === "petakan") dumpStruktur(t.email, kandidat);
      const p = pilihMitra(t.email, kandidat);
      hasil.status = p.status;
      hasil.mitra = p.mitra ? (p.mitra.nama || p.mitra.username || "") : "";
      hasil.pesan = p.pesan;
      if (p.mitra && p.mitra.punyaReset === false && (p.status === "COCOK" || p.status === "COCOK_TEKS")) {
        hasil.pesan += " | ⚠️ baris ini tanpa tombol Reset PW";
      }
      if (o.mode === "petakan" || o.mode === "cocok") return hasil;

      // --- mode manual/otomatis (butuh SELEKTOR_RESET) ---
      if (!SELEKTOR_RESET || typeof SELEKTOR_RESET.cariReset !== "function") {
        hasil.status = "SELEKTOR_BELUM_DIISI";
        hasil.pesan = "Isi SELEKTOR_RESET dari hasil petakan dulu (reset tidak ditebak).";
        return hasil;
      }
      if (p.status !== "COCOK") return hasil; // COCOK_TEKS/GANDA/TIDAK_KETEMU -> jangan reset
      const tombolReset = SELEKTOR_RESET.cariReset(p.mitra.el);
      if (!tombolReset) { hasil.status = "RESET_TIDAK_ADA"; hasil.pesan = "tombol 'Reset PW' tidak ketemu di baris mitra"; return hasil; }

      if (o.mode === "manual") {
        // Skrip TIDAK mengubah data. Manusia klik "Reset PW", isi password, simpan;
        // skrip menunggu & memverifikasi lewat toast sukses (bukan label field).
        tombolReset.style.outline = "3px solid #0277bd";
        tombolReset.scrollIntoView({ block: "center" });
        log(`👉 KLIK SENDIRI "Reset PW" utk ${t.email} (${hasil.mitra}); di panel: isi field pertama '${o.passwordBaru}', `
          + "biarkan field kedua (email), klik 'Reset Password'. Aku tunggu (maks 5 mnt) & verifikasi.");
        const sukses = await tunggu(() => POLA_SUKSES.test(document.body.innerText || ""), 5 * 60 * 1000, 500);
        hasil.status = sukses ? "DIRESET_TERVERIFIKASI" : "BELUM_BERUBAH";
        hasil.pesan += sukses ? " | toast sukses terdeteksi" : " | sukses TIDAK terdeteksi dlm 5 mnt — cek manual";
        return hasil;
      }

      // otomatis: klik "Reset PW" -> isi field password '{passwordBaru}' -> simpan. IRREVERSIBLE.
      tombolReset.click();
      const ok = await resetDiDialog(o.passwordBaru);
      hasil.status = ok ? "DIRESET_TERVERIFIKASI" : "DIRESET_BELUM_TERVERIFIKASI";
      hasil.pesan += ` | password -> '${o.passwordBaru}'` + (ok ? " | toast sukses" : " | sukses tak terverifikasi — CEK (mungkin sudah ter-reset tapi toast beda)");
      return hasil;
    } catch (e) {
      hasil.status = e instanceof Berhenti ? e.kode : "ERROR_TAK_TERDUGA";
      hasil.pesan = `${hasil.pesan ? hasil.pesan + " | " : ""}${e && e.message ? e.message : e}`;
      if (!(e instanceof Berhenti)) console.error(e);
      return hasil;
    }
  }

  async function jalankan(opsi = {}) {
    const o = { mode: "cocok", limit: null, email: null, lewatiSelesai: true, passwordBaru: PASSWORD_BARU,
      jedaMin: 2500, jedaMaks: 6000, sayaSudahMelihatDialog: false, lewatiGanda: true, ...opsi };
    if (!["petakan", "cocok", "manual", "otomatis"].includes(o.mode)) {
      log(`mode '${o.mode}' tidak dikenal (petakan | cocok | manual | otomatis)`); return;
    }
    if (berjalan) { log("Masih berjalan — tunggu selesai atau resetMitra.berhenti()."); return; }
    if (!TARGET.length) { log("TARGET kosong — tempel reset_mitra_console.siap.js (python reset_mitra/reset_mitra.py --console)."); return; }
    if (!location.pathname.includes("akun-mitra")) {
      log(`⛔ Bukan halaman akun-mitra (sekarang ${location.pathname}). Buka /mitra/akun-mitra dulu — jangan dashboard.`); return;
    }
    if (!kotakCari()) { log("Kotak 'Cari NIK, Email, Nama Lengkap...' belum tampil (pastikan sudah login & di akun-mitra)."); return; }

    const live = o.mode === "manual" || o.mode === "otomatis";
    if (live && (!SELEKTOR_RESET || typeof SELEKTOR_RESET.cariReset !== "function")) {
      log("⛔ SELEKTOR_RESET belum diisi. Jalankan mode 'petakan' dulu, kirim resetMitra.unduhDump() ke pengembang, "
        + "baru mode manual/otomatis bisa dipakai. (Reset password tidak ditebak.)");
      return;
    }
    if (live && !String(o.passwordBaru || "").trim()) {
      log("⛔ Password baru kosong. Isi FIXED_PASSWORD di inti/config_lokal.py lalu jalankan ulang "
        + "reset_mitra.py --console, atau beri jalankan({passwordBaru: \"...\"}).");
      return;
    }
    if (o.mode === "otomatis" && o.sayaSudahMelihatDialog !== true) {
      log("Mode otomatis butuh opsi sayaSudahMelihatDialog: true. WAJIB mulai dgn limit: 1, "
        + "lalu verifikasi mitra itu bisa login dgn password baru, SEBELUM membesarkan batch.");
      return;
    }

    let daftar = TARGET;
    if (o.email) { const ingin = new Set(o.email.map(normEmail)); daftar = daftar.filter((t) => ingin.has(normEmail(t.email))); }
    if (o.lewatiSelesai && o.mode !== "petakan") {
      const sebelumnya = muatHasil();
      const tuntas = live ? STATUS_TUNTAS_LIVE : STATUS_TUNTAS_COCOK;
      daftar = daftar.filter((t) => { const h = sebelumnya[t.email]; return !h || !tuntas.has(h.status); });
    }
    if (o.mode === "petakan") daftar = daftar.slice(0, 1);
    else if (o.limit) daftar = daftar.slice(0, o.limit);
    if (!daftar.length) { log("Tidak ada akun yang perlu diproses."); return; }

    if (live) {
      const pesan = `RESET PASSWORD ${daftar.length} akun mitra SUNGGUHAN jadi '${o.passwordBaru}' (mode ${o.mode}).`;
      if (o.mode === "otomatis") { if (prompt(`${pesan}\nKetik YA:`) !== "YA") return log("Dibatalkan."); }
      else if (!confirm(`${pesan}\nKamu yang klik "Reset PW", isi password & simpan per akun. Lanjut?`)) return log("Dibatalkan.");
    }

    berjalan = true; hentikan = false;
    const hitung = {}; let errorBeruntun = 0;
    const dilewatiGanda = [];
    try {
      for (let i = 0; i < daftar.length; i++) {
        const t = daftar[i];
        log(`=== [${i + 1}/${daftar.length}] ${t.email} (${o.mode}) ===`);
        const hasil = await prosesEmail(t, o);
        const keputusan = putuskanStatus(hasil.status, { live, lewatiGanda: o.lewatiGanda });
        if (keputusan === "LEWATI" && live) {
          hasil.pesan += " | DILEWATI (akun ganda, tidak direset) — telusuri manual";
          dilewatiGanda.push(t.email);
        }
        if (o.mode !== "petakan") simpanHasil(hasil);
        hitung[hasil.status] = (hitung[hasil.status] || 0) + 1;
        log(`  -> ${hasil.status}`, hasil.mitra ? `[${hasil.mitra}]` : "", hasil.pesan);
        if (keputusan === "BERHENTI") {
          log(`⛔ ${hasil.status} — batch DIHENTIKAN.` + (hasil.status === "GANDA" ? " (lewatiGanda:true utk melewatinya)" : ""));
          break;
        }
        errorBeruntun = hasil.status.startsWith("ERROR_") ? errorBeruntun + 1 : 0;
        if (errorBeruntun >= 3) { log("⛔ 3 error berturut-turut — batch DIHENTIKAN (sesi habis?)."); break; }
        if (i < daftar.length - 1) await sleep(acak(o.jedaMin, o.jedaMaks));
      }
    } finally {
      berjalan = false;
      console.table(hitung);
      if (dilewatiGanda.length) log(`⚠️ ${dilewatiGanda.length} akun GANDA dilewati (tidak direset):`, dilewatiGanda.join(", "));
      log(o.mode === "petakan" ? "Selesai petakan. resetMitra.unduhDump() lalu kirim ke pengembang."
        : "Selesai. resetMitra.unduh() untuk menyimpan hasil sbg CSV.");
    }
    return hitung;
  }

  function ringkasan() {
    const hitung = {};
    for (const h of Object.values(muatHasil())) hitung[`${h.jalan}:${h.status}`] = (hitung[`${h.jalan}:${h.status}`] || 0) + 1;
    console.table(hitung);
    return hitung;
  }

  function unduhTeks(nama, isi, tipe) {
    const blob = new Blob([isi], { type: tipe });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = nama;
    document.body.appendChild(a); a.click(); a.remove();
    log("Diunduh:", nama);
  }

  function unduh() {
    const kolom = ["waktu", "jalan", "email", "baris_sheet", "status", "mitra", "pesan"];
    const kutip = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    const baris = Object.values(muatHasil()).map((h) => kolom.map((k) => kutip(h[k])).join(","));
    unduhTeks(`audit_reset_mitra_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.csv`,
      "﻿" + [kolom.join(","), ...baris].join("\n"), "text/csv");
  }

  function unduhDump() {
    const d = localStorage.getItem(KUNCI_DUMP);
    if (!d) return log("Belum ada dump — jalankan mode 'petakan' dulu.");
    unduhTeks(`dump_akun_mitra_${Date.now()}.json`, d, "application/json");
  }

  /** Panggil saat SATU dialog "Reset PW" sedang terbuka: catat field & tombolnya
   *  (utk verifikasi/debug kalau otomatis gagal di FIELD_PASSWORD / TOMBOL). */
  function petakanDialog() {
    const dlg = dialogAktif();
    if (!dlg) { log("Buka dulu satu dialog 'Reset PW' (klik tombolnya di satu baris), lalu jalankan resetMitra.petakanDialog()."); return; }
    const info = {
      teks: bersih(dlg.innerText).slice(0, 500),
      inputs: [...dlg.querySelectorAll("input")].filter(tampak).map((i) => ({ type: i.type, name: i.name, placeholder: i.placeholder, aria: i.getAttribute("aria-label"), value: i.value })),
      kontrol: kontrolKlik(dlg).map((b) => ({ tag: b.tagName.toLowerCase(), role: b.getAttribute("role"), teks: teksKontrol(b) })),
      resetPassword_sehalaman: kontrolKlik(document).filter((b) => /^\s*reset\s*password\s*$/i.test(teksKontrol(b))).length,
    };
    console.log(JSON.stringify(info, null, 1));
    try { localStorage.setItem("resetMitra.dialog", JSON.stringify(info)); } catch (e) { /* abaikan */ }
    log("Struktur dialog dicatat. Kirim output di atas kalau otomatis berhenti di FIELD_PASSWORD/TOMBOL.");
    return info;
  }

  global.resetMitra = {
    jalankan, ringkasan, unduh, unduhDump, petakanDialog, target: TARGET, passwordBaru: PASSWORD_BARU,
    berhenti() { hentikan = true; log("Akan berhenti di langkah berikutnya."); },
    hapusHasil() { if (confirm("Hapus SELURUH hasil resetMitra di browser ini?")) localStorage.removeItem(KUNCI_HASIL); },
  };
  log(`Siap: ${TARGET.length} akun PPL. Password baru = '${PASSWORD_BARU}'. Mulai READ-ONLY: await resetMitra.jalankan({mode: "petakan"})`);
})(typeof window !== "undefined" ? window : globalThis);
