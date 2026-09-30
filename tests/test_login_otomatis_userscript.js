// Uji fasih_sm/login_otomatis/fasih_login_otomatis.user.js — logika murni + simulasi halaman SSO & tab penjaga
// (DOM, Tampermonkey GM_*, storage, fetch PALSU). Jalankan: node tests/test_login_otomatis_userscript.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const BERKAS = path.join(__dirname, "..", "fasih_sm", "login_otomatis", "fasih_login_otomatis.user.js");
const m = require(BERKAS);

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

// ---------------- logika murni
const T = 1_790_000_000_000;
const dasar = { adaForm: true, redirectHost: "fasih-sm.bps.go.id", sekarang: T, mintaT: T - 10_000, adaPesanGagal: false,
  punyaAkun: true, dikirimUntuk: 0 };
check("SSO: diminta penjaga -> ISI", m.putuskanSso(dasar), "ISI");
check("SSO: tanpa form", m.putuskanSso({ ...dasar, adaForm: false }), "BUKAN_FORM");
check("SSO: login aplikasi lain (bukan fasih-sm) tidak disentuh", m.putuskanSso({ ...dasar, redirectHost: "fasih-web.bps.go.id" }), "BUKAN_FASIH");
check("SSO: tidak diminta penjaga", m.putuskanSso({ ...dasar, mintaT: 0 }), "TIDAK_DIMINTA");
check("SSO: permintaan kedaluwarsa (> 3 mnt)", m.putuskanSso({ ...dasar, mintaT: T - m.BATAS_MINTA_MS - 1 }), "TIDAK_DIMINTA");
check("SSO: pesan galat -> tidak diulang", m.putuskanSso({ ...dasar, adaPesanGagal: true }), "LOGIN_GAGAL");
check("SSO: akun belum diatur", m.putuskanSso({ ...dasar, punyaAkun: false }), "AKUN_BELUM_DIATUR");
check("SSO: form sudah dikirim di putaran ini -> tidak dikirim lagi", m.putuskanSso({ ...dasar, dikirimUntuk: dasar.mintaT }), "SUDAH_DIKIRIM");
check("SSO: kiriman putaran LAIN tidak menghalangi", m.putuskanSso({ ...dasar, dikirimUntuk: dasar.mintaT - 60_000 }), "ISI");
check("SSO: halaman sesudah kirim (tanpa redirect_uri) tetap boleh kalau diminta", m.putuskanSso({ ...dasar, redirectHost: "" }), "ISI");
check("jeda: 0 utk < 3 gagal berturut-turut, lalu jedaGagal (0 = tanpa jeda)",
  [m.jedaLogin(0, 30000), m.jedaLogin(2, 30000), m.jedaLogin(3, 30000), m.jedaLogin(9, 30000), m.jedaLogin(9, 0)], [0, 0, 30000, 30000, 0]);
check("penjaga: 200 aman, 401 langsung login, 429/5xx/0 bukan soal login", [m.putuskanPenjaga(200, {}, T, 30000),
  m.putuskanPenjaga(401, {}, T, 30000), m.putuskanPenjaga(429, {}, T, 30000), m.putuskanPenjaga(503, {}, T, 30000),
  m.putuskanPenjaga(0, {}, T, 30000)], ["AMAN", "LOGIN", "TIDAK_PASTI", "TIDAK_PASTI", "TIDAK_PASTI"]);
check("penjaga: login barusan BERHASIL (gagal 0) -> sesi habis lagi langsung login, tanpa jeda",
  m.putuskanPenjaga(401, { gagal: 0, terakhir: T - 1000 }, T, 30000), "LOGIN");
check("penjaga: 2 gagal berturut-turut masih langsung", m.putuskanPenjaga(401, { gagal: 2, terakhir: T - 1000 }, T, 30000), "LOGIN");
check("penjaga: 3 gagal berturut-turut -> jeda", m.putuskanPenjaga(401, { gagal: 3, terakhir: T - 1000 }, T, 30000), "JEDA");
check("penjaga: jeda lewat -> login lagi (tanpa batas jumlah)", m.putuskanPenjaga(401, { gagal: 50, terakhir: T - 31000 }, T, 30000), "LOGIN");
check("penjaga: jeda gagal 0 -> selalu langsung", m.putuskanPenjaga(401, { gagal: 50, terakhir: T - 1 }, T, 0), "LOGIN");
check("url login = tautan 'Lanjutkan dengan SSO'", m.urlLogin("https://fasih-sm.bps.go.id", "https://fasih-sm.bps.go.id/app", "pegawai"),
  "https://fasih-sm.bps.go.id/app/auth/login?redirect_to=https%3A%2F%2Ffasih-sm.bps.go.id%2Fapp");
check("url login eksternal", m.urlLogin("https://x", "https://x/app", "eksternal"), "https://x/app/auth/login?realms=eksternal&redirect_to=https%3A%2F%2Fx%2Fapp");
check("survei dari path Data", m.surveiDariPath("/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24/data"),
  "a0429e96-51a5-477b-a415-485f9c153004");

// ---------------- simulasi browser
const SURVEI = "a0429e96-51a5-477b-a415-485f9c153004";
const PERIODE = "fd68e454-ba45-4b85-8205-f3bf777ded24";
const teks = fs.readFileSync(BERKAS, "utf8");

function peta() {
  const d = new Map();
  return { d, getItem: (k) => (d.has(k) ? d.get(k) : null), setItem: (k, v) => d.set(k, String(v)), removeItem: (k) => d.delete(k) };
}
/** Satu pemuatan halaman: userscript dijalankan dgn DOM/GM/storage palsu. */
function muat(o) {
  const el = (id, x = {}) => ({ id, value: "", focus() {}, dispatchEvent() {}, click() { hasil.klik.push(id); }, textContent: "", ...x });
  const hasil = { klik: [], notif: [], navigasi: null, pendengar: {}, interval: [], timeout: [], ambil: [] };
  const elemen = new Map((o.elemen || []).map((e) => [e.id, el(e.id, e)]));
  const loc = { host: new URL(o.url).host, pathname: new URL(o.url).pathname, origin: new URL(o.url).origin, _href: o.url };
  Object.defineProperty(loc, "href", { get() { return this._href; }, set(v) { hasil.navigasi = v; } });
  const sb = {
    console: { log: () => {} }, URL, JSON, Date, Math, Promise,
    GM_getValue: (k, def) => (o.gm.has(k) ? o.gm.get(k) : def),
    GM_setValue: (k, v) => o.gm.set(k, v), GM_deleteValue: (k) => o.gm.delete(k),
    GM_registerMenuCommand: () => {}, GM_notification: (x) => hasil.notif.push(x.title),
    location: loc, sessionStorage: o.sesi, localStorage: o.lokal,
    document: { title: "Halaman", getElementById: (id) => elemen.get(id) || null,
      querySelector: () => (o.galat ? { textContent: o.galat } : null),
      createElement: () => ({ style: {}, textContent: "" }), body: { appendChild() {} }, documentElement: { appendChild() {} } },
    Event: class { constructor(t) { this.type = t; } },
    fetch: async (u) => { hasil.ambil.push(u); return { status: o.status }; },
    setTimeout: (fn) => hasil.timeout.push(fn), setInterval: (fn) => hasil.interval.push(fn),
    prompt: () => null, alert: () => {},
  };
  sb.window = sb;
  sb.addEventListener = (ev, fn) => { hasil.pendengar[ev] = fn; };
  vm.createContext(sb);
  vm.runInContext(teks, sb);
  hasil.elemen = elemen;
  return hasil;
}
const formSso = () => [{ id: "kc-form-login" }, { id: "username" }, { id: "password" }, { id: "kc-login" }];
const URL_SSO = "https://sso.bps.go.id/auth/realms/pegawai-bps/protocol/openid-connect/auth?response_type=code&client_id=klien-contoh"
  + "&redirect_uri=https://fasih-sm.bps.go.id/login/oauth2/code/klien-contoh";
const URL_DATA = `https://fasih-sm.bps.go.id/app/surveys/${SURVEI}/${PERIODE}/data`;
const tuntas = async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r)); };
const tabPenjaga = (x = {}) => {
  const s = peta();
  s.setItem("fasihPenjaga.v1", JSON.stringify({ survei: SURVEI, sejak: Date.now(), gagal: 0, terakhir: 0, total: 0, ...x }));
  return s;
};
const statusTab = (s) => JSON.parse(s.getItem("fasihPenjaga.v1"));

(async () => {
  const gm = new Map([["username", "admin.contoh"], ["password", "rahasia-fiktif"]]);

  // SSO tanpa permintaan penjaga -> tidak menyentuh apa pun
  let h = muat({ url: URL_SSO, gm, sesi: peta(), lokal: peta(), elemen: formSso() });
  h.timeout.forEach((f) => f());
  check("SSO tanpa permintaan: form tidak diisi, tidak diklik, tidak pindah", [h.elemen.get("password").value, h.klik, h.navigasi], ["", [], null]);

  // penjaga: sesi habis (401) -> LANGSUNG buka login SSO
  const sesi = tabPenjaga();
  const lokal = peta();
  h = muat({ url: URL_DATA, gm, sesi, lokal, status: 401 });
  check("penjaga: mendengar sinyal bot (storage) & cek berkala", [typeof h.pendengar.storage, h.interval.length], ["function", 1]);
  h.pendengar.storage({ key: "fasihSesi.minta.v1" });
  await tuntas();
  check("penjaga: cek sesi lewat survey-roles", h.ambil, [`/app/api/survey/api/v1/survey-roles?surveyId=${SURVEI}`]);
  check("penjaga: 401 -> langsung buka login SSO kembali ke halaman ini", h.navigasi,
    `https://fasih-sm.bps.go.id/app/auth/login?redirect_to=${encodeURIComponent(URL_DATA)}`);
  check("penjaga: putaran dicatat", [gm.has("mintaLogin"), statusTab(sesi).gagal, statusTab(sesi).total], [true, 1, 1]);

  // SSO dgn permintaan -> isi & klik Log In SEKALI utk putaran ini
  h = muat({ url: URL_SSO, gm, sesi: peta(), lokal: peta(), elemen: formSso() });
  h.timeout.forEach((f) => f());
  check("SSO diminta: username/password diisi & Log In diklik",
    [h.elemen.get("username").value, h.elemen.get("password").value, h.klik], ["admin.contoh", "rahasia-fiktif", ["kc-login"]]);
  check("SSO: kiriman ditandai utk putaran ini", gm.get("dikirimUntuk"), gm.get("mintaLogin"));
  // kembali lagi ke form di putaran yang sama -> tidak dikirim lagi, kembali ke fasih-sm (putaran baru)
  h = muat({ url: URL_SSO, gm, sesi: peta(), lokal: peta(), elemen: formSso() });
  h.timeout.forEach((f) => f());
  check("SSO putaran sama: tidak dikirim ulang, kembali ke fasih-sm", [h.klik, h.navigasi, gm.has("mintaLogin")],
    [[], "https://fasih-sm.bps.go.id/app", false]);

  // halaman SSO tanpa form di tengah putaran -> kembali; di luar putaran -> diam
  gm.set("mintaLogin", Date.now());
  h = muat({ url: "https://sso.bps.go.id/auth/realms/pegawai-bps/login-actions/authenticate", gm, sesi: peta(), lokal: peta(), elemen: [] });
  h.timeout.forEach((f) => f());
  check("SSO tanpa form di tengah putaran: kembali ke fasih-sm", h.navigasi, "https://fasih-sm.bps.go.id/app");
  h = muat({ url: "https://sso.bps.go.id/auth/realms/pegawai-bps/account", gm, sesi: peta(), lokal: peta(), elemen: [] });
  h.timeout.forEach((f) => f());
  check("SSO tanpa form, tanpa putaran: diam", h.navigasi, null);

  // password salah -> TIDAK diulang, notifikasi
  gm.set("mintaLogin", Date.now());
  h = muat({ url: "https://sso.bps.go.id/auth/realms/pegawai-bps/login-actions/authenticate?session_code=x", gm, sesi: peta(), lokal: peta(),
    elemen: formSso(), galat: "Invalid username or password." });
  h.timeout.forEach((f) => f());
  check("SSO galat: tidak diklik, tidak pindah, notifikasi, putaran dihapus", [h.klik, h.navigasi, h.notif.length, gm.has("mintaLogin")],
    [[], null, 1, false]);

  // kembali ke fasih-sm & sesi hidup -> hitungan gagal nol, sinyal pulih utk bot
  gm.set("mintaLogin", Date.now());
  gm.set("dikirimUntuk", gm.get("mintaLogin"));
  h = muat({ url: URL_DATA, gm, sesi, lokal, status: 200 });
  h.pendengar.storage({ key: "fasihSesi.minta.v1" });
  await tuntas();
  check("pulih: sinyal bot, gagal=0, catatan putaran dihapus, tidak pindah",
    [!!lokal.getItem("fasihSesi.pulih.v1"), statusTab(sesi).gagal, gm.has("mintaLogin"), gm.has("dikirimUntuk"), h.navigasi],
    [true, 0, false, false, null]);

  // sesi habis BERKALI-KALI (mis. tiap 3 mnt) & login selalu berhasil -> selalu langsung, tanpa jeda, tanpa batas
  let langsung = 0;
  for (let i = 0; i < 12; i++) {
    h = muat({ url: URL_DATA, gm, sesi, lokal, status: 401 });
    h.interval[0]();
    await tuntas();
    if (h.navigasi) langsung++;
    h = muat({ url: URL_DATA, gm, sesi, lokal, status: 200 }); // kembali sesudah login berhasil
    h.interval[0]();
    await tuntas();
  }
  check("12x sesi habis + login berhasil: 12x langsung login, tidak pernah jeda", [langsung, statusTab(sesi).gagal, statusTab(sesi).total],
    [12, 0, 13]);

  // 3 putaran berturut-turut TIDAK memulihkan sesi -> jeda (bawaan 30 dtk), satu notifikasi, satu jadwal
  const sesiGagal = tabPenjaga({ gagal: 3, terakhir: Date.now() });
  h = muat({ url: URL_DATA, gm, sesi: sesiGagal, lokal, status: 401 });
  h.interval[0]();
  await tuntas();
  h.pendengar.storage({ key: "fasihSesi.minta.v1" });
  await tuntas();
  check("3 gagal beruntun: jeda (tidak pindah), notifikasi & jadwal cek masing2 sekali", [h.navigasi, h.notif.length, h.timeout.length],
    [null, 1, 2]); // 2 = cek "halaman dimuat" + satu cek sesudah jeda
  // jeda gagal diset 0 lewat menu -> langsung
  gm.set("jedaGagalMs", 0);
  h = muat({ url: URL_DATA, gm, sesi: tabPenjaga({ gagal: 3, terakhir: Date.now() }), lokal, status: 401 });
  h.interval[0]();
  await tuntas();
  check("jeda gagal 0: tetap langsung login", !!h.navigasi, true);
  gm.delete("jedaGagalMs");

  // server 503 -> bukan urusan login
  h = muat({ url: URL_DATA, gm, sesi, lokal, status: 503 });
  h.interval[0]();
  await tuntas();
  check("penjaga: 503 tidak memicu login", h.navigasi, null);

  // tab bukan penjaga -> tidak ada cek sama sekali
  h = muat({ url: URL_DATA, gm, sesi: peta(), lokal, status: 401 });
  check("tab biasa (bukan penjaga): diam", [h.interval.length, h.pendengar.storage], [0, undefined]);

  console.log(okAll ? "\nSEMUA LULUS" : "\nADA YANG GAGAL");
  process.exit(okAll ? 0 : 1);
})();
