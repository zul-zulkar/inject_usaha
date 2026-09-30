// ==UserScript==
// @name         FASIH-SM — penjaga sesi & login ulang otomatis
// @namespace    split_usaha
// @version      1.1.0
// @description  Tab penjaga mengecek sesi fasih-sm; kalau habis (401), langsung login ulang lewat SSO BPS supaya bot Console di tab lain lanjut sendiri.
// @match        https://fasih-sm.bps.go.id/*
// @match        https://sso.bps.go.id/auth/realms/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @grant        GM_notification
// @run-at       document-idle
// @noframes
// ==/UserScript==
/**
 * fasih_login_otomatis.user.js — dipasang di Tampermonkey (Chrome). JANGAN menulis password di berkas ini (repo publik):
 * akun & password disimpan lewat menu Tampermonkey "🔑 Atur akun SSO" (penyimpanan ekstensi di PC ini saja).
 *
 * PERAN
 * - PENJAGA (hanya di tab yang dijadikan penjaga lewat menu, halaman Data survei fasih-sm): tiap 60 dtk mengecek sesi
 *   (GET survey-roles), dan SEGERA saat bot Console di tab lain kena 401 (sinyal localStorage "fasihSesi.minta.v1").
 *   Sesi habis -> LANGSUNG buka /app/auth/login?redirect_to=<halaman ini> (= tautan "Lanjutkan dengan SSO").
 * - PENGISI SSO (sso.bps.go.id, form Keycloak #kc-form-login): isi #username/#password lalu #kc-login — HANYA kalau
 *   penjaga memintanya < 3 mnt lalu, tujuan kembalinya fasih-sm, tidak ada pesan galat, & form belum dikirim di
 *   putaran login ini (maks 1 kiriman per putaran). Selain itu tidak menyentuh apa pun.
 * - Sesudah kembali ke fasih-sm & sesi terbukti hidup -> sinyal "fasihSesi.pulih.v1"; bot yang menunggu 401 langsung
 *   mengulang request-nya.
 *
 * JUMLAH & JEDA (user 2026-09-30: "jangan hanya 3 kali", "jangan 15 menit — sesi bisa habis tiap 3/5 mnt atau 1 jam",
 * "jangan kasih delay, kalau sesi habis langsung loginkan"): login ulang TIDAK dibatasi jumlahnya dan TANPA jeda.
 * Login yang berhasil tidak dihitung apa pun. Satu-satunya jeda: sesudah 3 putaran login BERTURUT-TURUT yang tidak
 * memulihkan sesi (SSO/fasih-sm bermasalah), putaran berikutnya diberi jeda "jedaGagal" (bawaan 30 dtk, menu ⏱️, 0 =
 * tanpa jeda) supaya tab tidak berputar menghantam server. Pesan GALAT SSO (password salah / akun terkunci) TIDAK
 * diulang — mengulang bisa memperpanjang kunci akun admin.
 *
 * Struktur halaman (dibaca langsung 2026-09-30, bukan tebakan): /app tanpa sesi = "Lanjutkan dengan SSO" ->
 * /app/auth/login?redirect_to=… (SSO Eksternal: + realms=eksternal) -> sso.bps.go.id/auth/realms/pegawai-bps/…/auth
 * (redirect_uri https://fasih-sm.bps.go.id/login/oauth2/code/…) dgn #kc-form-login #username #password #kc-login.
 * Uji logika: node tests/test_login_otomatis_userscript.js
 */
(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // Logika murni (diuji Node)
  // -------------------------------------------------------------------------
  const HOST_FASIH = "fasih-sm.bps.go.id";
  const BATAS_MINTA_MS = 3 * 60 * 1000;        // permintaan login dari penjaga berlaku selama ini (satu putaran)
  const GAGAL_TANPA_JEDA = 3;                   // putaran login gagal berturut-turut yang masih langsung diulang
  const JEDA_GAGAL_BAWAAN_MS = 30 * 1000;       // jeda sesudahnya (menu ⏱️; 0 = tanpa jeda)
  const KEMBALI_MS = 5000;                      // halaman SSO tak terduga di tengah putaran -> kembali ke fasih-sm
  const KUNCI_MINTA_BOT = "fasihSesi.minta.v1"; // localStorage fasih-sm: ditulis bot Console saat kena 401
  const KUNCI_PULIH = "fasihSesi.pulih.v1";     // localStorage fasih-sm: ditulis penjaga saat sesi pulih

  /** Halaman SSO -> "ISI" | "BUKAN_FORM" | "BUKAN_FASIH" | "TIDAK_DIMINTA" | "LOGIN_GAGAL" | "AKUN_BELUM_DIATUR" |
   *  "SUDAH_DIKIRIM" (form sudah dikirim di putaran ini tapi kembali ke login -> putaran baru dari fasih-sm). */
  function putuskanSso(k) {
    if (!k.adaForm) return "BUKAN_FORM";
    if (k.redirectHost && k.redirectHost !== HOST_FASIH) return "BUKAN_FASIH";
    if (!k.mintaT || k.sekarang - k.mintaT > BATAS_MINTA_MS) return "TIDAK_DIMINTA";
    if (k.adaPesanGagal) return "LOGIN_GAGAL";
    if (!k.punyaAkun) return "AKUN_BELUM_DIATUR";
    if (k.dikirimUntuk && k.dikirimUntuk === k.mintaT) return "SUDAH_DIKIRIM";
    return "ISI";
  }

  /** Jeda sebelum putaran login berikutnya, dari jumlah putaran gagal berturut-turut. */
  function jedaLogin(gagal, jedaGagalMs) {
    return gagal >= GAGAL_TANPA_JEDA ? Math.max(0, jedaGagalMs) : 0;
  }

  /** Penjaga: status cek sesi + {gagal, terakhir} -> "AMAN" | "LOGIN" | "JEDA" | "TIDAK_PASTI". */
  function putuskanPenjaga(status, st, sekarang, jedaGagalMs) {
    if (status >= 200 && status < 300) return "AMAN";
    if (status !== 401) return "TIDAK_PASTI"; // 429/5xx/jaringan: bukan urusan login
    const s = st || {};
    return sekarang < (s.terakhir || 0) + jedaLogin(s.gagal || 0, jedaGagalMs) ? "JEDA" : "LOGIN";
  }

  /** URL login fasih-sm (sama dgn tautan "Lanjutkan dengan SSO [Eksternal]"). */
  function urlLogin(asal, kembali, jenis) {
    return `${asal}/app/auth/login?${jenis === "eksternal" ? "realms=eksternal&" : ""}redirect_to=${encodeURIComponent(kembali)}`;
  }

  /** ID survei dari path halaman Data (/app/surveys/<survei>/<periode>/...). */
  function surveiDariPath(path) {
    const m = /^\/app\/surveys\/([0-9a-f-]{36})(?:\/|$)/i.exec(path || "");
    return m ? m[1] : "";
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { putuskanSso, jedaLogin, putuskanPenjaga, urlLogin, surveiDariPath, BATAS_MINTA_MS, GAGAL_TANPA_JEDA,
      JEDA_GAGAL_BAWAAN_MS, KEMBALI_MS, KUNCI_MINTA_BOT, KUNCI_PULIH };
    return;
  }

  // -------------------------------------------------------------------------
  // Browser (Tampermonkey)
  // -------------------------------------------------------------------------
  const KUNCI_TAB = "fasihPenjaga.v1"; // sessionStorage tab penjaga: {survei, sejak, gagal, terakhir, total}
  const log = (...a) => console.log("%c[penjaga-sesi]", "color:#2a7a2a;font-weight:bold", ...a);
  const akun = () => ({ user: GM_getValue("username", ""), pass: GM_getValue("password", ""), jenis: GM_getValue("jenis", "pegawai") });
  const jedaGagalMs = () => Number(GM_getValue("jedaGagalMs", JEDA_GAGAL_BAWAAN_MS)) || 0;
  const beritahu = (judul, teks) => {
    try { GM_notification({ title: judul, text: teks, timeout: 0 }); } catch (e) { /* notifikasi diblokir */ }
    log(`${judul} — ${teks}`);
  };

  GM_registerMenuCommand("🔑 Atur akun SSO (username & password)", () => {
    const user = prompt("Username SSO BPS akun admin fasih-sm:", GM_getValue("username", ""));
    if (user == null) return;
    const pass = prompt("Password SSO (disimpan di Tampermonkey PC ini saja; kosongkan = tidak diubah):", "");
    if (pass == null) return;
    const jenis = (prompt('Jenis SSO: "pegawai" (tombol "Lanjutkan dengan SSO") atau "eksternal":', GM_getValue("jenis", "pegawai")) || "pegawai")
      .trim().toLowerCase() === "eksternal" ? "eksternal" : "pegawai";
    GM_setValue("username", user.trim());
    if (pass) GM_setValue("password", pass);
    GM_setValue("jenis", jenis);
    alert(`Tersimpan: ${user.trim()} (${jenis})${GM_getValue("password", "") ? ", password ada" : ", PASSWORD BELUM ADA"}.`);
  });
  GM_registerMenuCommand("⏱️ Atur jeda login GAGAL berturut-turut", () => {
    const d = prompt(`Detik jeda sesudah ${GAGAL_TANPA_JEDA} login berturut-turut yang TIDAK memulihkan sesi (0 = tanpa jeda). `
      + "Login yang berhasil tidak pernah diberi jeda.", String(Math.round(jedaGagalMs() / 1000)));
    if (d == null) return;
    const n = Math.max(0, Number(String(d).replace(",", ".")) || 0);
    GM_setValue("jedaGagalMs", Math.round(n * 1000));
    alert(`Jeda login gagal: ${n} dtk.`);
  });
  GM_registerMenuCommand("🗑️ Hapus password tersimpan", () => {
    GM_deleteValue("password");
    alert("Password dihapus dari Tampermonkey.");
  });

  if (location.host === "sso.bps.go.id") jalankanSso();
  else if (location.host === HOST_FASIH) jalankanFasih();

  // ---- sso.bps.go.id: isi form hanya atas permintaan penjaga, maks sekali per putaran
  function jalankanSso() {
    const form = document.getElementById("kc-form-login");
    const u = document.getElementById("username");
    const p = document.getElementById("password");
    const tombol = document.getElementById("kc-login");
    let redirectHost = "";
    try {
      const r = new URL(location.href).searchParams.get("redirect_uri");
      if (r) redirectHost = new URL(r).host;
    } catch (e) { /* bukan URL */ }
    // Hanya penanda GALAT Keycloak (bukan .kc-feedback-text polos: itu juga dipakai pesan peringatan/info).
    const galat = document.querySelector("#input-error, .alert-error, .pf-m-danger");
    const a = akun();
    const mintaT = GM_getValue("mintaLogin", 0);
    const keputusan = putuskanSso({
      adaForm: !!(form && u && p && tombol), redirectHost, sekarang: Date.now(), mintaT,
      adaPesanGagal: !!(galat && galat.textContent.trim()), punyaAkun: !!(a.user && a.pass), dikirimUntuk: GM_getValue("dikirimUntuk", 0),
    });
    log(`SSO: ${keputusan}`);
    const alurPenjaga = mintaT && Date.now() - mintaT <= BATAS_MINTA_MS;
    // Kembali ke fasih-sm -> penjaga di tab ini (tandanya di sessionStorage fasih-sm) mengecek & memulai putaran baru.
    const kembaliKeFasih = (sebab) => {
      GM_deleteValue("mintaLogin");
      log(`${sebab} — kembali ke fasih-sm, penjaga memulai putaran login baru.`);
      setTimeout(() => { location.href = `https://${HOST_FASIH}/app`; }, KEMBALI_MS);
    };
    if (keputusan === "LOGIN_GAGAL") {
      GM_deleteValue("mintaLogin");
      beritahu("⚠️ Login SSO fasih-sm GAGAL", `${galat.textContent.trim()} — TIDAK diulang (akun bisa terkunci). `
        + "Periksa akun lewat menu Tampermonkey, lalu login manual di tab ini.");
      document.title = `⚠️ LOGIN GAGAL — ${document.title}`;
    } else if (keputusan === "AKUN_BELUM_DIATUR") {
      GM_deleteValue("mintaLogin");
      beritahu("⚠️ Login ulang fasih-sm perlu Anda", "Akun/password belum diatur (menu Tampermonkey \"🔑 Atur akun SSO\"). Login manual di tab ini.");
      document.title = `⚠️ LOGIN MANUAL — ${document.title}`;
    } else if (keputusan === "SUDAH_DIKIRIM") {
      kembaliKeFasih("form sudah dikirim di putaran ini tapi kembali ke halaman login");
    } else if (keputusan === "BUKAN_FORM" && alurPenjaga) {
      kembaliKeFasih("halaman SSO tanpa form login (galat server / sesi login kedaluwarsa)");
    } else if (keputusan === "ISI") {
      GM_setValue("dikirimUntuk", mintaT);
      const isi = (el, nilai) => {
        el.focus();
        el.value = nilai;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      };
      isi(u, a.user);
      isi(p, a.pass);
      log("Form SSO diisi — menekan Log In.");
      setTimeout(() => tombol.click(), 300);
    }
  }

  // ---- fasih-sm: penjaga (hanya tab yang ditandai) + menu
  function bacaTab() {
    try { return JSON.parse(sessionStorage.getItem(KUNCI_TAB) || "null"); } catch (e) { return null; }
  }
  function tulisTab(v) {
    if (v) sessionStorage.setItem(KUNCI_TAB, JSON.stringify(v)); else sessionStorage.removeItem(KUNCI_TAB);
  }

  function jalankanFasih() {
    GM_registerMenuCommand("🛡️ Jadikan tab ini PENJAGA sesi", () => {
      const survei = surveiDariPath(location.pathname) || (bacaTab() || {}).survei || "";
      if (!survei) {
        alert("Buka dulu halaman Data survei (…/app/surveys/<survei>/<periode>/data) di tab ini, lalu pilih menu ini lagi.");
        return;
      }
      tulisTab({ survei, sejak: Date.now(), gagal: 0, terakhir: 0, total: 0 });
      location.reload();
    });
    GM_registerMenuCommand("⏹️ Hentikan penjaga di tab ini", () => {
      tulisTab(null);
      location.reload();
    });
    const tab = bacaTab();
    if (!tab) return;
    penjaga(tab);
  }

  function penjaga(tab) {
    let sedang = false;
    let pindah = false;     // halaman sedang berpindah ke login
    let jedaTerjadwal = 0;  // waktu cek sesudah jeda yang sudah dijadwalkan (tidak dijadwalkan dobel)
    let diberitahu = false; // notifikasi "belum berhasil" sekali per rangkaian gagal
    const spanduk = document.createElement("div");
    spanduk.style.cssText = "position:fixed;bottom:8px;left:8px;z-index:2147483647;padding:6px 10px;border-radius:6px;"
      + "font:12px system-ui,sans-serif;color:#fff;background:#2a7a2a;box-shadow:0 2px 6px rgba(0,0,0,.3);pointer-events:none";
    const tampil = (teks, warna = "#2a7a2a") => {
      spanduk.textContent = `🛡️ Penjaga sesi — ${teks}`;
      spanduk.style.background = warna;
    };
    (document.body || document.documentElement).appendChild(spanduk);
    tampil("mulai");
    if (!document.title.startsWith("🛡️")) document.title = `🛡️ ${document.title}`;

    async function cek(alasan) {
      if (sedang || pindah) return;
      sedang = true;
      try {
        let status = 0;
        try {
          const r = await fetch(`/app/api/survey/api/v1/survey-roles?surveyId=${encodeURIComponent(tab.survei)}`,
            { credentials: "include", headers: { Accept: "application/json" } });
          status = r.status;
        } catch (e) { status = 0; }
        const t = { gagal: 0, terakhir: 0, total: 0, ...(bacaTab() || tab) };
        const jeda = jedaGagalMs();
        const kp = putuskanPenjaga(status, t, Date.now(), jeda);
        const jam = new Date().toLocaleTimeString();
        if (kp === "AMAN") {
          diberitahu = false;
          if (t.gagal || GM_getValue("mintaLogin", 0)) {
            // Putaran login berhasil: hitungan gagal kembali nol, bot yang menunggu 401 dibangunkan.
            tulisTab({ ...t, gagal: 0 });
            GM_deleteValue("mintaLogin");
            GM_deleteValue("dikirimUntuk");
            localStorage.setItem(KUNCI_PULIH, JSON.stringify({ t: Date.now() }));
            log("✅ Sesi pulih sesudah login ulang — bot di tab lain langsung lanjut.");
          }
          tampil(`sesi aktif (cek ${jam}${alasan ? `, ${alasan}` : ""}) · login ulang ${t.total}x`);
        } else if (kp === "LOGIN") {
          tulisTab({ ...t, gagal: t.gagal + 1, terakhir: Date.now(), total: t.total + 1 });
          GM_setValue("mintaLogin", Date.now());
          tampil("sesi habis — login ulang...", "#b8541d");
          log(`Sesi habis (${alasan || "cek berkala"}) — langsung login ulang (putaran ke-${t.total + 1}).`);
          pindah = true;
          location.href = urlLogin(location.origin, location.href, akun().jenis);
        } else if (kp === "JEDA") {
          const lagi = t.terakhir + jedaLogin(t.gagal, jeda);
          tampil(`login ${t.gagal}x berturut-turut tidak memulihkan sesi — coba lagi ${new Date(lagi).toLocaleTimeString()}`, "#b8541d");
          if (!diberitahu) {
            diberitahu = true;
            beritahu("⏸️ Login ulang fasih-sm belum berhasil", `${t.gagal}x berturut-turut; dicoba terus tiap ${Math.round(jeda / 1000)} dtk.`);
          }
          if (jedaTerjadwal !== lagi) {
            jedaTerjadwal = lagi;
            setTimeout(() => cek("sesudah jeda"), Math.max(1000, lagi - Date.now() + 500));
          }
        } else {
          tampil(`cek ${jam}: HTTP ${status || "gagal jaringan"} (bukan soal login, dicek lagi)`, "#8a6d00");
        }
      } finally {
        sedang = false;
      }
    }

    // Sinyal dari bot Console (tab lain, origin sama) -> cek SEGERA.
    window.addEventListener("storage", (e) => { if (e.key === KUNCI_MINTA_BOT) cek("bot kena 401"); });
    setInterval(() => cek(""), 60 * 1000);
    setTimeout(() => cek("halaman dimuat"), 1000);
  }
})();
