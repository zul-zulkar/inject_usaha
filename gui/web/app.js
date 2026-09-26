"use strict";
/* GUI Inject Usaha SE2026 — halaman tunggal tanpa pustaka luar.
   Semua formulir dibangkitkan dari daftar alat di gui/alat.py (GET /api/awal). */

const TOKEN = document.querySelector('meta[name="token"]').content;
const $ = (s, el = document) => el.querySelector(s);

// ============================================================ utilitas
function h(tag, attrs, ...anak) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "style") el.style.cssText = v;
      else if (["value", "checked", "disabled", "hidden", "selected", "open", "readOnly", "type", "placeholder"].includes(k)) el[k] = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  for (const a of anak.flat(Infinity)) {
    if (a === null || a === undefined || a === false) continue;
    el.append(a instanceof Node ? a : document.createTextNode(String(a)));
  }
  return el;
}

async function api(path, data) {
  const opsi = { headers: { "X-Token": TOKEN } };
  if (data !== undefined) {
    opsi.method = "POST";
    opsi.headers["Content-Type"] = "application/json";
    opsi.body = JSON.stringify(data);
  }
  const r = await fetch(path, opsi);
  let j;
  try { j = await r.json(); } catch { throw new Error(`Server membalas HTTP ${r.status}`); }
  if (!r.ok || (j && j.galat)) throw new Error((j && j.galat) || `HTTP ${r.status}`);
  return j;
}

function toast(teks, lama = 3500) {
  const el = h("div", { class: "isi", text: teks });
  $("#toast").append(el);
  setTimeout(() => el.remove(), lama);
}

function salinObjek(o) { return JSON.parse(JSON.stringify(o)); }

function tampilNilai(v) {
  if (v === undefined) return "";
  if (v === null) return "None";
  if (typeof v === "object" && !Array.isArray(v)) {
    if ("__py__" in v) return v.__py__;
    if ("__tidak_bisa_diubah__" in v) return v.__tidak_bisa_diubah__;
    return pyRepr(v);
  }
  if (typeof v === "boolean") return v ? "True" : "False";
  return String(v);
}

function pyRepr(v) {
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(pyRepr).join(", ") + "]";
  return "{" + Object.entries(v).map(([k, x]) => `${JSON.stringify(k)}: ${pyRepr(x)}`).join(", ") + "}";
}

async function salinKeClipboard(teks, html) {
  if (html && window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/plain": new Blob([teks], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      })]);
      return "lengkap";
    } catch (e) { /* jatuh ke teks biasa */ }
  }
  try { await navigator.clipboard.writeText(teks); return "teks"; } catch (e) { /* cadangan terakhir */ }
  const ta = h("textarea", { style: "position:fixed;left:-9999px" });
  ta.value = teks;
  document.body.append(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  if (!ok) throw new Error("Browser menolak menyalin ke clipboard.");
  return "teks";
}

// ------------------------------------------------------------ dialog
let dialogAktif = null;
function bukaDialog(isi, kelas = "", { bisaDitutup = true } = {}) {
  tutupDialog();
  const d = h("div", { class: `dialog ${kelas}`, role: "dialog", "aria-modal": "true" }, isi);
  const lap = $("#lapisan");
  lap.append(d);
  dialogAktif = { el: d, bisaDitutup };
  const fokus = d.querySelector("input, textarea, select, button.utama, button");
  if (fokus) setTimeout(() => fokus.focus(), 30);
  return d;
}
function tutupDialog() {
  $("#lapisan").replaceChildren();
  dialogAktif = null;
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && dialogAktif && dialogAktif.bisaDitutup) tutupDialog();
});

function dialogKonfirmasi(judul, teks, jenis = "tulis") {
  return new Promise((selesai) => {
    const ya = h("button", { class: `tombol ${jenis === "bahaya" ? "bahaya" : "utama"}`, text: "Lanjut", onclick: () => { tutupDialog(); selesai(true); } });
    bukaDialog([
      h("h2", { text: judul }),
      h("p", { text: teks }),
      h("div", { class: "aksi" },
        h("button", { class: "tombol", text: "Batal", onclick: () => { tutupDialog(); selesai(false); } }), ya),
    ], jenis === "bahaya" ? "bahaya" : "");
  });
}

function dialogPesan(judul, isi, kelas = "") {
  bukaDialog([h("h2", { text: judul }), isi,
    h("div", { class: "aksi" }, h("button", { class: "tombol utama", text: "Tutup", onclick: tutupDialog }))], kelas);
}

// ------------------------------------------------------------ markdown sederhana (README)
function inlineMd(teks) {
  const frag = document.createDocumentFragment();
  const pola = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let akhir = 0;
  let m;
  while ((m = pola.exec(teks))) {
    if (m.index > akhir) frag.append(teks.slice(akhir, m.index));
    if (m[1]) frag.append(h("code", { text: m[1].slice(1, -1) }));
    else if (m[2]) frag.append(h("strong", { text: m[2].slice(2, -2) }));
    else if (/^https?:/.test(m[5])) frag.append(h("a", { href: m[5], target: "_blank", rel: "noopener", text: m[4] }));
    else frag.append(h("span", { text: m[4], title: m[5] }));
    akhir = pola.lastIndex;
  }
  if (akhir < teks.length) frag.append(teks.slice(akhir));
  return frag;
}

function md(teks) {
  const el = h("div", { class: "md" });
  const b = teks.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < b.length) {
    const s = b[i];
    if (s.startsWith("```")) {
      const isi = [];
      i++;
      while (i < b.length && !b[i].startsWith("```")) isi.push(b[i++]);
      i++;
      el.append(h("pre", {}, h("code", { text: isi.join("\n") })));
    } else if (/^#{1,6} /.test(s)) {
      const n = s.match(/^#+/)[0].length;
      el.append(h(`h${Math.min(n, 4)}`, {}, inlineMd(s.slice(n + 1))));
      i++;
    } else if (/^\s*\|/.test(s)) {
      const baris = [];
      while (i < b.length && /^\s*\|/.test(b[i])) baris.push(b[i++]);
      const sel = (x) => x.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const tabel = h("table");
      baris.filter((x) => !/^\s*\|[\s:|-]+\|\s*$/.test(x)).forEach((x, j) => {
        tabel.append(h("tr", {}, sel(x).map((c) => h(j === 0 ? "th" : "td", {}, inlineMd(c)))));
      });
      el.append(h("div", { class: "tabel-bungkus" }, tabel));
    } else if (/^\s*([-*]|\d+\.) /.test(s)) {
      const ol = /^\s*\d+\. /.test(s);
      const daftar = h(ol ? "ol" : "ul");
      while (i < b.length && /^\s*([-*]|\d+\.) /.test(b[i])) {
        let isi = b[i++].replace(/^\s*([-*]|\d+\.) /, "");
        while (i < b.length && /^\s{2,}\S/.test(b[i]) && !/^\s*([-*]|\d+\.) /.test(b[i])) isi += " " + b[i++].trim();
        daftar.append(h("li", {}, inlineMd(isi)));
      }
      el.append(daftar);
    } else if (s.startsWith(">")) {
      const isi = [];
      while (i < b.length && b[i].startsWith(">")) isi.push(b[i++].replace(/^>\s?/, "").replace(/^\[!\w+\]\s*/, ""));
      el.append(h("blockquote", {}, inlineMd(isi.join(" "))));
    } else if (!s.trim()) {
      i++;
    } else {
      const isi = [];
      while (i < b.length && b[i].trim() && !/^(#|```|>|\s*\||\s*([-*]|\d+\.) )/.test(b[i])) isi.push(b[i++].trim());
      el.append(h("p", {}, inlineMd(isi.join(" "))));
    }
  }
  return el;
}

async function bukaPetunjuk(path, judul) {
  if (path.startsWith("@kbli/")) path = S.awal.kbli.folder + "/" + path.slice(6);
  try {
    const r = await api("/api/baca", { path });
    bukaDialog([h("div", { class: "baris-flex" }, h("h2", { text: judul || r.path }),
      h("span", { class: "redup kecil", text: r.path }),
      h("button", { class: "tombol kecil", style: "margin-left:auto", text: "Tutup", onclick: tutupDialog })),
    md(r.teks)], "lebar");
  } catch (e) { toast(e.message, 6000); }
}

// ============================================================ keadaan
const MENU = [
  ["persiapan", "Persiapan"], ["input", "Input Usaha"], ["approve", "Approve PML"], ["fasihsm", "fasih-sm & Mitra"],
  ["antarpc", "Antar PC & Koordinat"], ["kbli", "Generate KBLI"], ["pengaturan", "Pengaturan"], ["proses", "Proses"],
];
const S = {
  awal: null, halaman: "persiapan", pilihAlat: {}, nilai: {}, proses: [], log: {}, panel: new Map(),
  fokus: {}, password: { tersedia: false, sesi: false }, tundaYa: {}, serverMati: false,
  kbli: { hasil: "", sumber: "", lembar: "", pertahankan: true, data: null }, prosesDipilih: null, draft: null,
  cfg: null,
};

function alat(id) { return S.awal.alat.alat.find((a) => a.id === id); }
function alatGrup(grup) { return S.awal.alat.alat.filter((a) => a.grup === grup); }

function nilaiBawaan(i) {
  if (i.jenis === "centang") return i.bawaan === true;
  if (i.jenis === "centang_nilai") return { aktif: i.bawaan === true, nilai: "" };
  if (i.jenis === "berkas_banyak" || i.jenis === "lokasi_banyak") return [];
  return i.bawaan ?? "";
}

function isiNilaiAwal() {
  const tersimpan = S.awal.isian || {};
  for (const a of S.awal.alat.alat) {
    const n = {};
    for (const i of a.isian) n[i.nama] = nilaiBawaan(i);
    const lama = tersimpan[a.id] || {};
    for (const i of a.isian) if (i.nama in lama) n[i.nama] = lama[i.nama];
    S.nilai[a.id] = n;
  }
}

function itemConfig(nama) {
  return ((S.cfg || S.awal.config).pengaturan || []).find((x) => x.nama === nama);
}

/** Nilai config yang berlaku (timpaan GUI > config_lokal > config.py) — sama dgn server.efektif. */
function efektif(nama) {
  const p = S.awal.pengaturan;
  if (p.timpa && nama in p.timpa) return p.timpa[nama];
  const it = itemConfig(nama);
  if (!it) return undefined;
  if (p.pakai_config_lokal && "lokal" in it) return it.lokal;
  return it.bawaan;
}

// ============================================================ kerangka & navigasi
function renderNav() {
  // Tombol dibuat SEKALI lalu hanya diperbarui: membangun ulang tiap poll bisa menelan klik pengguna.
  const nav = $("#nav");
  if (!nav.childElementCount) {
    nav.append(...MENU.map(([id, judul]) => h("button", { type: "button", "data-id": id, onclick: () => pindah(id) },
      h("span", { text: judul }), h("span", { class: "lencana", hidden: true }))));
  }
  const jalan = S.proses.filter((p) => p.status === "berjalan").length;
  const tunggu = S.proses.some((p) => p.menunggu_ya);
  for (const b of nav.children) {
    b.classList.toggle("aktif", b.dataset.id === S.halaman);
    if (b.dataset.id === "proses") {
      const l = b.lastElementChild;
      l.hidden = !jalan;
      l.className = `lencana ${tunggu ? "merah" : "biru"}`;
      l.textContent = tunggu ? `${jalan} · YA?` : String(jalan);
    }
  }
}

function pindah(halaman) {
  S.halaman = halaman;
  if (location.hash !== `#${halaman}`) history.replaceState(null, "", `#${halaman}`);
  renderNav();
  render();
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", () => {
  const id = location.hash.slice(1);
  if (MENU.some((m) => m[0] === id) && id !== S.halaman) pindah(id);
});

function render() {
  const isi = $("#isi");
  isi.replaceChildren();
  const hal = S.halaman;
  if (hal === "persiapan") return halamanPersiapan(isi);
  if (hal === "pengaturan") return halamanPengaturan(isi);
  if (hal === "proses") return halamanProses(isi);
  if (hal === "kbli") return halamanKbli(isi);
  return halamanGrup(isi, hal);
}

function perbaruiKepala() {
  const kab = efektif("KODE_KAB");
  $("#info-kab").textContent = kab ? `Kabupaten ${tampilNilai(kab)}` : "";
  const t = $("#tombol-password");
  t.textContent = S.password.sesi ? "Password: terisi (sesi)" : (S.password.tersedia ? "Password: dari config_lokal" : "Password: belum diisi");
  t.className = `tombol kecil ${S.password.tersedia ? "" : "tulis"}`;
}

// ------------------------------------------------------------ tema
function terapkanTema() {
  let t = null;
  try { t = localStorage.getItem("tema"); } catch { /* abaikan */ }
  if (t) document.documentElement.dataset.theme = t;
}
$("#tombol-tema").addEventListener("click", () => {
  const gelap = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const baru = gelap ? "light" : "dark";
  document.documentElement.dataset.theme = baru;
  try { localStorage.setItem("tema", baru); } catch { /* abaikan */ }
});

// ------------------------------------------------------------ password
$("#tombol-password").addEventListener("click", () => dialogPassword(false));

function dialogPassword(awal) {
  return new Promise((selesai) => {
    const input = h("input", { type: "password", autocomplete: "off", placeholder: "Password SSO akun PPL/PML" });
    const simpan = async () => {
      try {
        S.password = await api("/api/password", { password: input.value });
        perbaruiKepala();
        tutupDialog();
        toast(input.value ? "Password disimpan utk sesi ini." : "Password sesi dihapus.");
        selesai(S.password.tersedia);
      } catch (e) { toast(e.message, 6000); }
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") simpan(); });
    const lokal = S.awal.config.password_lokal_ada && S.awal.pengaturan.pakai_config_lokal;
    bukaDialog([
      h("h2", { text: "Password SSO" }),
      h("p", { class: "redup", text: "Password yang SAMA utk semua akun PPL/PML yang dipakai alat (diseragamkan lewat Reset password mitra). " +
        "Hanya disimpan di memori selama GUI terbuka — tidak pernah ditulis ke disk. Tutup GUI = ketik lagi." }),
      lokal ? h("p", { class: "pesan biru", text: "inti/config_lokal.py di PC ini sudah berisi password. Kosongkan kotak ini = password config_lokal yang dipakai." }) : null,
      input,
      h("div", { class: "aksi" },
        h("button", { class: "tombol", text: awal ? "Nanti saja" : "Batal", onclick: () => { tutupDialog(); selesai(S.password.tersedia); } }),
        S.password.sesi ? h("button", { class: "tombol", text: "Hapus password sesi", onclick: () => { input.value = ""; simpan(); } }) : null,
        h("button", { class: "tombol utama", text: "Simpan utk sesi ini", onclick: simpan })),
    ]);
  });
}

// ============================================================ proses: polling, panel log, dialog YA
async function pollProses() {
  if (S.sedangPoll) return;
  S.sedangPoll = true;
  try {
    const r = await api("/api/proses");
    const statusLama = Object.fromEntries(S.proses.map((p) => [p.id, p.status]));
    S.proses = r.proses;
    S.password = r.password;
    if (S.serverMati) { S.serverMati = false; $("#isi").querySelector(".server-mati")?.remove(); }
    perbaruiKepala();
    renderNav();
    for (const p of S.proses) {
      if (statusLama[p.id] === "berjalan" && p.status !== "berjalan") {
        toast(`#${p.id} ${p.judul}: ${p.status}${p.kode !== null ? ` (kode ${p.kode})` : ""}`, 6000);
        if (p.alat === "kbli" && p.status === "selesai") isiKbliDariProses(p, false);
      }
    }
    for (const [el, panel] of S.panel) {
      if (!el.isConnected) { S.panel.delete(el); continue; }
      const p = S.proses.find((x) => x.id === panel.id);
      if (p) panel.perbarui(p);
      const c = S.log[panel.id];
      if (p && (p.status === "berjalan" || !c || c.sampai < p.jumlah || c.status !== p.status)) ambilLog(panel.id);
    }
    cekYa();
  } catch (e) {
    if (!S.serverMati) {
      S.serverMati = true;
      $("#isi").prepend(h("div", { class: "pesan merah server-mati",
        text: "GUI tidak terhubung ke server. Kalau jendela hitam GUI tertutup, jalankan lagi gui\\buka_gui.bat lalu muat ulang halaman ini." }));
    }
  } finally { S.sedangPoll = false; }
}

/** Ambil daftar proses SEKARANG (tanpa menunggu giliran poll) — dipakai sesudah memulai/menghapus proses. */
async function segarkanProses() {
  try {
    const r = await api("/api/proses");
    S.proses = r.proses;
    S.password = r.password;
    renderNav();
  } catch (e) { /* poll berikutnya melaporkan */ }
}

async function ambilLog(id) {
  const c = S.log[id] || (S.log[id] = { baris: [], sampai: 0, sisa: "", sedang: false, status: "" });
  if (c.sedang) return;
  c.sedang = true;
  try {
    const r = await api(`/api/proses/${id}?dari=${c.sampai}`);
    if (r.dari > c.sampai && c.sampai > 0) c.baris.push(`… ${r.dari - c.sampai} baris tidak ditampilkan (lihat berkas log)`);
    for (const b of r.baris) c.baris.push(b);
    if (c.baris.length > 5000) c.baris.splice(0, c.baris.length - 5000);
    c.sampai = r.sampai;
    c.sisa = r.sisa;
    c.status = r.status;
  } catch (e) { /* proses dihapus / server mati */ } finally { c.sedang = false; }
  for (const [el, panel] of S.panel) if (el.isConnected && panel.id === id) panel.gambarLog();
}

function lencanaStatus(p) {
  if (p.menunggu_ya) return h("span", { class: "lencana merah", text: "menunggu YA" });
  const kelas = { berjalan: "biru", selesai: "ok", gagal: "merah", dihentikan: "kuning" }[p.status] || "";
  return h("span", { class: `lencana ${kelas}`, text: p.status + (p.kode !== null && p.status !== "berjalan" ? ` (${p.kode})` : "") });
}

function tombolKeluaran(p) {
  return (p.keluaran || []).map((k) => h("button", {
    class: `tombol kecil ${k.jenis === "kbli" || k.jenis === "koordinat" || k.jenis === "salin" ? "utama" : ""}`,
    text: k.label, disabled: !k.ada, title: k.ada ? k.tampil : `Belum ada: ${k.tampil}`,
    onclick: () => jalankanKeluaran(p, k),
  }));
}

async function jalankanKeluaran(p, k) {
  try {
    if (k.jenis === "salin") {
      const r = await api("/api/baca", { path: k.path });
      try {
        await salinKeClipboard(r.teks);
        dialogPesan("Skrip tersalin", h("div", {},
          h("p", { text: `${r.path} (${r.teks.length.toLocaleString("id")} karakter) sudah di clipboard.` }),
          h("ol", {},
            h("li", { text: "Buka halaman fasih-sm / manajemen-mitra yang dimaksud di Chrome biasa (sudah login)." }),
            h("li", { text: "Tekan F12 → tab Console → tempel (Ctrl+V) → Enter. Chrome kadang meminta mengetik 'allow pasting' dulu." }),
            h("li", { text: "Jalankan perintah Console sesuai Petunjuk alatnya (mulai dari mode cek / limit 1)." }))));
      } catch (e) {
        const ta = h("textarea", { rows: 10, readOnly: true, value: r.teks });
        dialogPesan("Salin manual", h("div", {}, h("p", { text: "Browser menolak menyalin otomatis — pilih semua (Ctrl+A) lalu Ctrl+C:" }), ta));
      }
    } else if (k.jenis === "kbli") {
      isiKbliDariProses(p, true);
    } else if (k.jenis === "koordinat") {
      const r = await api("/api/salin/koordinat", { hasil: k.path, sumber: (p.isian || {}).sumber || "" });
      dialogHasilSalin("Latitude / Longitude", r, "Latitude");
    } else {
      await api("/api/buka", { path: k.path });
    }
  } catch (e) { toast(e.message, 6000); }
}

function panelLog(id, { tinggi = 380 } = {}) {
  const pre = h("pre", { style: `height:${tinggi}px`, tabindex: "0" });
  const kepala = h("div", { class: "kepala" });
  const kaki = h("div", { class: "kaki" });
  const el = h("div", { class: "panel-log" }, kepala, pre, kaki);
  const panel = {
    id, el, statusTerakhir: "",
    perbarui(p) {
      const kunci = `${p.status}|${p.menunggu_ya}|${(p.keluaran || []).map((k) => k.ada).join()}`;
      if (kunci === this.statusTerakhir) return;
      this.statusTerakhir = kunci;
      kepala.replaceChildren(
        h("strong", { text: `#${p.id}` }), h("span", { text: p.judul }), lencanaStatus(p),
        h("span", { class: "redup kecil", text: `mulai ${p.mulai}${p.selesai ? ` · selesai ${p.selesai}` : ""}` }),
        h("span", { style: "margin-left:auto" }),
        h("button", { class: "tombol kecil", text: "Salin perintah", title: p.perintah,
          onclick: () => salinKeClipboard(p.perintah).then(() => toast("Perintah tersalin — bisa dijalankan di terminal.")) }),
        h("button", { class: "tombol kecil", text: "Buka log", onclick: () => api("/api/buka", { path: p.log }).catch((e) => toast(e.message)) }),
        p.status === "berjalan"
          ? h("button", { class: "tombol kecil tulis", text: "Hentikan", onclick: () => hentikan(p) })
          : h("button", { class: "tombol kecil polos", text: "Hapus dari daftar", onclick: () => hapusProses(p) }));
      const masukan = h("input", { type: "text", placeholder: "Ketik lalu Enter utk dikirim ke proses (mis. Enter saat diminta login manual)" });
      const kirim = async () => {
        try { await api(`/api/proses/${p.id}/masukan`, { teks: masukan.value }); masukan.value = ""; ambilLog(p.id); } catch (e) { toast(e.message); }
      };
      masukan.addEventListener("keydown", (e) => { if (e.key === "Enter") kirim(); });
      kaki.replaceChildren(
        ...(p.status === "berjalan" ? [masukan, h("button", { class: "tombol kecil", text: "Kirim", onclick: kirim })] : []),
        ...tombolKeluaran(p));
      kaki.hidden = !kaki.childElementCount;
    },
    gambarLog() {
      const c = S.log[id];
      if (!c) return;
      const diBawah = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
      pre.textContent = c.baris.join("\n") + (c.sisa ? `\n${c.sisa}` : "");
      if (diBawah) pre.scrollTop = pre.scrollHeight;
    },
  };
  S.panel.set(el, panel);
  const p = S.proses.find((x) => x.id === id);
  if (p) panel.perbarui(p);
  panel.gambarLog();
  ambilLog(id);
  return el;
}

async function hentikan(p) {
  const ok = await dialogKonfirmasi("Hentikan proses?",
    `#${p.id} ${p.judul} akan dihentikan paksa (sama seperti menutup terminal). Dokumen yang sedang diisi bisa tertinggal DRAFT; ` +
    "audit tetap mencatatnya dan run berikutnya membukanya lewat URL. Browser Playwright ikut ditutup.", "bahaya");
  if (!ok) return;
  try { await api(`/api/proses/${p.id}/hentikan`, {}); pollProses(); } catch (e) { toast(e.message); }
}

async function hapusProses(p) {
  try { await api(`/api/proses/${p.id}/hapus`, {}); await segarkanProses(); render(); } catch (e) { toast(e.message); }
}

function cekYa() {
  if (dialogAktif) return;
  const p = S.proses.find((x) => x.menunggu_ya && !((S.tundaYa[x.id] || 0) > Date.now()));
  if (p) dialogYaProses(p);
}

async function dialogYaProses(p) {
  await ambilLog(p.id);
  if (dialogAktif) return;
  const c = S.log[p.id] || { baris: [] };
  const input = h("input", { type: "text", class: "ketik-ya", autocomplete: "off", placeholder: "YA" });
  const kirim = h("button", { class: "tombol bahaya", text: "Kirim YA", disabled: true });
  input.addEventListener("input", () => { kirim.disabled = input.value !== "YA"; });
  const jawab = async (j) => {
    try { await api(`/api/proses/${p.id}/jawab`, { jawab: j }); } catch (e) { toast(e.message, 6000); }
    tutupDialog();
    pollProses();
  };
  kirim.addEventListener("click", () => jawab("YA"));
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && input.value === "YA") jawab("YA"); });
  bukaDialog([
    h("h2", { text: "Konfirmasi tindakan yang TIDAK BISA dibatalkan" }),
    h("p", {}, h("strong", { text: `#${p.id} ${p.judul}` })),
    h("p", { class: "redup", text: "Periksa ringkasan di bawah (jumlah dokumen, akun, subsls). Ketik YA (huruf besar) utk melanjutkan." }),
    h("pre", { class: "cuplikan", text: c.baris.slice(-30).join("\n") }),
    h("p", { class: "pesan kuning", text: p.prompt }),
    h("div", { class: "baris-flex" }, input),
    h("div", { class: "aksi" },
      h("button", { class: "tombol", text: "Lihat log dulu", onclick: () => {
        S.tundaYa[p.id] = Date.now() + 30000; tutupDialog(); S.prosesDipilih = p.id; pindah("proses");
      } }),
      h("button", { class: "tombol", text: "Batalkan (kirim TIDAK)", onclick: () => jawab("TIDAK") }),
      kirim),
  ], "bahaya", { bisaDitutup: false });
}

function dialogYaAwal(a, ak) {
  return new Promise((selesai) => {
    const input = h("input", { type: "text", class: "ketik-ya", autocomplete: "off", placeholder: "YA" });
    const mulai = h("button", { class: "tombol bahaya", text: "Mulai", disabled: true });
    input.addEventListener("input", () => { mulai.disabled = input.value !== "YA"; });
    const ok = () => { tutupDialog(); selesai("YA"); };
    mulai.addEventListener("click", ok);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && input.value === "YA") ok(); });
    const n = S.nilai[a.id];
    bukaDialog([
      h("h2", { text: `${a.judul}: ${ak.label}` }),
      h("p", { class: "pesan merah", text: "Skrip ini MENGIRIM dokumen tanpa ditunggui dan mengetik YA sendiri di setiap putaran. " +
        "Pastikan dry-run rentang yang sama sudah benar dan akun ini TIDAK sedang dipakai PC/proses lain." }),
      h("table", {}, ["sumber", "dari", "sampai", "akun", "subsls", "akun_cadangan", "subsls_cadangan", "audit"]
        .filter((k) => n[k]).map((k) => h("tr", {}, h("th", { text: k }), h("td", { class: "mono", text: String(n[k]) })))),
      h("p", { text: "Ketik YA utk mulai:" }), input,
      h("div", { class: "aksi" }, h("button", { class: "tombol", text: "Batal", onclick: () => { tutupDialog(); selesai(null); } }), mulai),
    ], "bahaya", { bisaDitutup: false });
  });
}

// ============================================================ formulir alat
function cocok(syarat, nilai, a, aksiId) {
  if (!syarat) return true;
  const norm = (v) => {
    if (typeof v === "boolean") return v ? "1" : "0";
    if (v && typeof v === "object" && !Array.isArray(v)) return v.aktif ? "1" : "0";
    return v === null || v === undefined ? "" : String(v);
  };
  for (const [k, boleh] of Object.entries(syarat)) {
    if (k === "@aksi") { if (aksiId !== undefined && !boleh.includes(aksiId)) return false; continue; }
    const i = a.isian.find((x) => x.nama === k);
    const v = k in nilai ? nilai[k] : (i ? nilaiBawaan(i) : "");
    if (!boleh.map(norm).includes(norm(v))) return false;
  }
  return true;
}

async function pilihDialog(jenis, i, awal) {
  try {
    const r = await api("/api/dialog", { jenis, judul: i.label, filter: i.filter || [], ekstensi: i.ekstensi || "",
      awal: awal || "", nama: i.nama_bawaan || "" });
    return r.path;
  } catch (e) { toast(e.message, 7000); return []; }
}

function placeholderIsian(i) {
  if (i.pengaturan) {
    const v = efektif(i.pengaturan);
    const t = tampilNilai(v);
    return t ? `bawaan dari Pengaturan: ${t}` : "(belum diatur di Pengaturan)";
  }
  if (i.jenis === "audit") return "bawaan: audit/";
  return i.contoh ? `mis. ${i.contoh}` : "";
}

function widgetIsian(a, i, ubah) {
  const n = S.nilai[a.id];
  const idEl = `f-${a.id}-${i.nama}`;
  const set = (v) => { n[i.nama] = v; ubah(); };
  const wajib = i.wajib || (i.wajib_jika && cocok(Object.fromEntries(Object.entries(i.wajib_jika).filter(([k]) => k !== "@aksi")), n, a));
  const label = h("label", { class: `judul ${wajib ? "wajib" : ""}`, for: idEl, text: i.label });
  let kontrol;
  const tombolPilih = (jenis, teks, tambah) => h("button", { class: "tombol", type: "button", text: teks, onclick: async () => {
    const awal = Array.isArray(n[i.nama]) ? n[i.nama][0] : (typeof n[i.nama] === "object" ? n[i.nama].nilai : n[i.nama]);
    const p = await pilihDialog(jenis, i, awal);
    if (!p.length) return;
    tambah(p);
  } });

  switch (i.jenis) {
    case "centang": {
      const c = h("input", { type: "checkbox", id: idEl, checked: !!n[i.nama], onchange: (e) => set(e.target.checked) });
      return h("div", { class: "isian" }, h("label", { class: "centang", for: idEl }, c, h("span", {}, i.label)),
        i.bantuan ? h("div", { class: "bantuan", text: i.bantuan }) : null, i.aksi ? h("div", { class: "bantuan", text: `Hanya utk: ${labelAksi(a, i.aksi)}` }) : null);
    }
    case "centang_nilai": {
      const v = typeof n[i.nama] === "object" && n[i.nama] ? n[i.nama] : { aktif: !!n[i.nama], nilai: "" };
      const teks = h("input", { type: "text", value: v.nilai || "", placeholder: "(boleh kosong = bawaan)",
        oninput: (e) => set({ aktif: true, nilai: e.target.value }) });
      const baris = h("div", { class: "dengan-tombol", hidden: !v.aktif }, teks,
        tombolPilih(i.jenis_nilai === "folder" ? "folder" : "buka", "Pilih…", (p) => { teks.value = p[0]; set({ aktif: true, nilai: p[0] }); }));
      const c = h("input", { type: "checkbox", id: idEl, checked: !!v.aktif, onchange: (e) => {
        baris.hidden = !e.target.checked; set({ aktif: e.target.checked, nilai: teks.value });
      } });
      return h("div", { class: "isian" }, h("label", { class: "centang", for: idEl }, c, h("span", {}, i.label)), baris,
        i.bantuan ? h("div", { class: "bantuan", text: i.bantuan }) : null);
    }
    case "pilihan": {
      kontrol = h("select", { id: idEl, onchange: (e) => set(e.target.value) },
        (i.opsi || []).map(([v, t]) => h("option", { value: v, text: t })));
      kontrol.value = n[i.nama] ?? "";
      break;
    }
    case "lembar": {
      kontrol = h("select", { id: idEl, onchange: (e) => set(e.target.value) }, h("option", { value: "", text: "(sheet aktif)" }));
      const muat = async () => {
        const path = n[i.dari_berkas];
        kontrol.replaceChildren(h("option", { value: "", text: "(sheet aktif)" }));
        if (!path) return;
        try {
          const r = await api("/api/lembar", { path });
          for (const l of r.lembar) kontrol.append(h("option", { value: l, text: l }));
          if (!n[i.nama] && r.lembar.includes("input_usaha")) n[i.nama] = "input_usaha";
        } catch (e) { /* berkas belum ada */ }
        kontrol.value = n[i.nama] || "";
        ubah();
      };
      kontrol.muatUlang = muat;
      setTimeout(muat, 0);
      break;
    }
    case "berkas_banyak":
    case "lokasi_banyak": {
      const ta = h("textarea", { id: idEl, rows: 2, placeholder: "satu berkas/folder per baris", value: (n[i.nama] || []).join("\n"),
        oninput: (e) => set(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean)) });
      const tambah = (p) => { const baru = [...(n[i.nama] || []), ...p]; ta.value = baru.join("\n"); set(baru); };
      kontrol = h("div", { class: "dengan-tombol" }, ta, h("div", { style: "display:grid;gap:4px;align-content:start" },
        tombolPilih("buka_banyak", i.jenis === "lokasi_banyak" ? "Berkas…" : "Tambah…", tambah),
        i.jenis === "lokasi_banyak" ? tombolPilih("folder", "Folder…", tambah) : null));
      break;
    }
    case "berkas":
    case "simpan":
    case "folder":
    case "audit": {
      const inp = h("input", { type: "text", id: idEl, value: n[i.nama] || "", placeholder: placeholderIsian(i),
        list: i.jenis === "audit" ? "daftar-audit" : null, oninput: (e) => set(e.target.value.trim()),
        onchange: () => { if (i.nama_lembar_pemicu) i.nama_lembar_pemicu(); } });
      const jenis = { berkas: "buka", simpan: "simpan", folder: "folder", audit: "folder" }[i.jenis];
      kontrol = h("div", { class: "dengan-tombol" }, inp, tombolPilih(jenis, "Pilih…", (p) => { inp.value = p[0]; set(p[0]); inp.dispatchEvent(new Event("change")); }));
      break;
    }
    default: {
      kontrol = h("input", { type: "text", id: idEl, value: n[i.nama] ?? "", placeholder: placeholderIsian(i),
        inputmode: i.jenis === "angka" ? "numeric" : null, oninput: (e) => set(e.target.value) });
    }
  }
  return h("div", { class: `isian ${i.jenis.endsWith("banyak") ? "lebar-penuh" : ""}` }, label, kontrol,
    i.bantuan ? h("div", { class: "bantuan", text: i.bantuan }) : null,
    i.aksi ? h("div", { class: "bantuan", text: `Hanya utk: ${labelAksi(a, i.aksi)}` }) : null);
}

function labelAksi(a, ids) {
  return ids.map((id) => (a.aksi.find((x) => x.id === id) || { label: id }).label).join(", ");
}

function formAlat(a) {
  const n = S.nilai[a.id];
  const baris = new Map();
  const utama = h("div", { class: "grid-isian" });
  const lanjut = h("div", { class: "grid-isian" });
  const pilihPratinjau = h("select", { class: "kecil", style: "width:auto" }, a.aksi.map((x) => h("option", { value: x.id, text: x.label })));
  const kodePratinjau = h("code", { text: "…" });
  const pesan = h("div", { class: "pesan merah", hidden: true });
  let tunda = null;
  const perbaruiPratinjau = () => {
    clearTimeout(tunda);
    tunda = setTimeout(async () => {
      try {
        const r = await api("/api/pratinjau", { alat: a.id, aksi: pilihPratinjau.value, isian: n });
        kodePratinjau.textContent = r.perintah ? (r.folder ? `(di folder ${r.folder})  ` : "") + r.perintah : `Belum lengkap:\n${r.masalah}`;
        kodePratinjau.style.opacity = r.perintah ? "1" : ".65";
      } catch (e) { kodePratinjau.textContent = e.message; }
    }, 250);
  };
  pilihPratinjau.addEventListener("change", perbaruiPratinjau);
  const perbaruiTampil = () => {
    for (const [i, el] of baris) el.hidden = !cocok(i.tampil_jika, n, a);
  };
  const ubah = () => { perbaruiTampil(); perbaruiPratinjau(); };
  for (const i of a.isian) {
    const el = widgetIsian(a, i, ubah);
    baris.set(i, el);
    (i.lanjutan ? lanjut : utama).append(el);
  }
  // sheet (lembar) ikut dimuat ulang begitu berkas sumbernya diganti
  for (const i of a.isian.filter((x) => x.jenis === "lembar")) {
    const elLembar = baris.get(i).querySelector("select");
    const elBerkas = baris.get(a.isian.find((x) => x.nama === i.dari_berkas))?.querySelector("input");
    if (elBerkas) elBerkas.addEventListener("change", () => { n[i.nama] = ""; elLembar.muatUlang(); });
  }
  perbaruiTampil();
  perbaruiPratinjau();

  const tombol = a.aksi.map((ak) => h("button", {
    class: `tombol ${ak.jenis === "bahaya" ? "bahaya" : ak.jenis === "tulis" ? "tulis" : "utama"}`, type: "button", text: ak.label,
    onclick: () => klikAksi(a, ak, pesan),
    onmouseenter: () => { if (pilihPratinjau.value !== ak.id) { pilihPratinjau.value = ak.id; perbaruiPratinjau(); } },
  }));
  const riwayat = h("div");
  const gambarRiwayat = () => {
    const daftar = S.proses.filter((p) => p.alat === a.id);
    riwayat.replaceChildren();
    if (!daftar.length) return;
    const fokus = daftar.find((p) => p.id === S.fokus[a.id]) || daftar[0];
    riwayat.append(panelLog(fokus.id, { tinggi: 320 }));
    const lain = daftar.filter((p) => p !== fokus).slice(0, 6);
    if (lain.length) {
      riwayat.append(h("div", { class: "proses-daftar jarak-atas" }, lain.map((p) => h("div", {
        class: "proses-baris", onclick: () => { S.fokus[a.id] = p.id; gambarRiwayat(); },
      }, h("span", { class: "redup", text: `#${p.id}` }), h("span", { class: "judul", text: p.judul }), lencanaStatus(p),
        h("span", { class: "redup kecil", text: p.mulai.slice(11) })))));
    }
  };
  gambarRiwayat();

  return h("section", { class: "kartu lebar" },
    h("header", {}, h("div", {}, h("h2", { text: a.judul })),
      h("div", { class: "kanan" }, a.petunjuk ? h("button", { class: "tombol kecil", text: "Petunjuk", onclick: () => bukaPetunjuk(a.petunjuk, a.judul) }) : null)),
    h("p", { class: "keterangan", text: a.keterangan }),
    utama,
    lanjut.childElementCount ? h("details", { class: "lanjutan" }, h("summary", { text: `Opsi lanjutan (${lanjut.childElementCount})` }), lanjut) : null,
    h("div", { class: "pratinjau" }, h("span", { class: "redup kecil", text: "Perintah:" }), kodePratinjau, pilihPratinjau),
    h("div", { class: "aksi" }, tombol),
    pesan,
    riwayat);
}

async function klikAksi(a, ak, pesan) {
  pesan.hidden = true;
  const isian = salinObjek(S.nilai[a.id]);
  const butuhPw = ak.password === true || (typeof ak.password === "string" && ak.password.startsWith("kecuali:") && !isian[ak.password.split(":")[1]]);
  if (butuhPw && !S.password.tersedia) {
    const ok = await dialogPassword(false);
    if (!ok) return;
  }
  if (ak.konfirmasi && !(await dialogKonfirmasi(ak.label, ak.konfirmasi, ak.jenis))) return;
  let konfirmasi_ya;
  if (ak.ya_dulu) {
    konfirmasi_ya = await dialogYaAwal(a, ak);
    if (konfirmasi_ya !== "YA") return;
  }
  try {
    const r = await api("/api/jalankan", { alat: a.id, aksi: ak.id, isian, konfirmasi_ya });
    S.fokus[a.id] = r.id;
    toast(`Proses #${r.id} dimulai: ${ak.label}`);
    await segarkanProses();
    render();
  } catch (e) {
    pesan.textContent = e.message;
    pesan.hidden = false;
  }
}

// ============================================================ halaman: grup alat
function halamanGrup(isi, grup) {
  const daftar = alatGrup(grup);
  if (!daftar.length) return;
  const pilih = alat(S.pilihAlat[grup]) && alat(S.pilihAlat[grup]).grup === grup ? alat(S.pilihAlat[grup]) : daftar[0];
  isi.append(h("datalist", { id: "daftar-audit" }, (S.awal.audit || []).map((x) => h("option", { value: x }))));
  if (daftar.length > 1) {
    isi.append(h("div", { class: "tab-alat" }, daftar.map((a) => h("button", {
      class: a === pilih ? "aktif" : "", type: "button", text: a.judul,
      onclick: () => { S.pilihAlat[grup] = a.id; render(); },
    }))));
  }
  if (grup === "input") {
    isi.append(h("div", { class: "pesan biru lebar", text: "Urutan aman: Periksa data → Dry-run 1 baris (Batas = 1) → cek dokumennya di fasih-web → KIRIM. " +
      "Satu akun hanya boleh dipakai SATU proses/PC pada satu waktu." }));
  }
  isi.append(formAlat(pilih));
}

// ============================================================ halaman: persiapan
async function halamanPersiapan(isi) {
  const kotak = h("div", { class: "daftar-cek" }, h("p", { class: "redup", text: "Memeriksa…" }));
  const vpn = h("div");
  isi.append(
    h("section", { class: "kartu lebar" },
      h("header", {}, h("h2", { text: "Persiapan PC ini" }),
        h("div", { class: "kanan" }, h("button", { class: "tombol kecil", text: "Periksa ulang", onclick: () => render() }))),
      h("p", { class: "keterangan", text: "Semua baris harus hijau sebelum input. Yang kuning opsional." }),
      kotak,
      h("div", { class: "aksi" },
        h("button", { class: "tombol", text: "Cek koneksi VPN", onclick: async (e) => {
          e.target.disabled = true;
          try {
            const r = await api("/api/persiapan/vpn", {});
            vpn.replaceChildren(...Object.entries(r).map(([host, x]) => h("div", { class: `pesan ${x.ok ? "hijau" : "merah"}`, text: `${host}: ${x.teks}` })));
          } catch (er) { toast(er.message); } finally { e.target.disabled = false; }
        } }),
        h("button", { class: "tombol", text: "Buat sheet input dari templat…", onclick: buatTemplat }),
        h("button", { class: "tombol polos", text: "Buka folder proyek", onclick: () => api("/api/buka", { path: S.awal.akar }) })),
      vpn),
    h("section", { class: "kartu lebar" },
      h("h2", { text: "Alur kerja" }),
      h("ol", {},
        h("li", {}, "Isi ", h("a", { href: "#pengaturan", text: "Pengaturan" }), " (kode kabupaten, kodepos desa, kotak koordinat, akun & subsls wadah)."),
        h("li", {}, "Samakan password akun PPL: ", h("a", { href: "#fasihsm", text: "fasih-sm & Mitra" }), " → Reset password."),
        h("li", {}, "Pastikan akun punya assignment PAPI di subsls wadah: fasih-sm & Mitra → Ganti mode."),
        h("li", {}, "Isi sheet dari templat; kode KBLI bisa ditebak lewat ", h("a", { href: "#kbli", text: "Generate KBLI" }), "."),
        h("li", {}, h("a", { href: "#input", text: "Input Usaha" }), ": Periksa data → Dry-run 1 baris → KIRIM."),
        h("li", {}, h("a", { href: "#approve", text: "Approve PML" }), " → Pindah wilayah → Tandai selesai (fasih-sm).")),
      h("button", { class: "tombol kecil", text: "Baca alur kerja lengkap", onclick: () => bukaPetunjuk("docs/ALUR_KERJA.md", "Alur kerja") })));
  try {
    const r = await api("/api/persiapan");
    kotak.replaceChildren(...r.cek.map((c) => h("div", { class: "item" },
      h("span", { class: `ikon-status ${c.ok ? "ok" : c.opsional ? "opsional" : "tidak"}`, text: c.ok ? "✓" : c.opsional ? "!" : "✕" }),
      h("div", {}, h("div", {}, h("strong", { text: c.nama }), c.teks ? h("span", { class: "redup", text: ` — ${c.teks}` }) : null),
        !c.ok && c.saran ? h("div", { class: "redup kecil", text: c.saran }) : null),
      !c.ok && c.pasang ? h("button", { class: "tombol kecil utama", text: "Pasang", onclick: () => pasang(c.pasang) }) : h("span"))));
    if (r.config_lokal_ada) {
      kotak.append(h("div", { class: "pesan biru", text: `inti/config_lokal.py ditemukan dan ${r.pakai_config_lokal ? "IKUT dipakai (pengaturan GUI menimpanya)" : "TIDAK dipakai"}. Ubah di Pengaturan > Aplikasi.` }));
    }
  } catch (e) { kotak.replaceChildren(h("div", { class: "pesan merah", text: e.message })); }
}

async function pasang(apa) {
  try {
    const r = await api("/api/persiapan/pasang", { apa });
    toast(`Proses #${r.id} dimulai`);
    S.prosesDipilih = r.id;
    await segarkanProses();
    pindah("proses");
  } catch (e) { toast(e.message, 6000); }
}

async function buatTemplat() {
  const p = await pilihDialog("simpan", { label: "Simpan sheet input usaha baru", filter: [["Excel", "*.xlsx"]], ekstensi: ".xlsx", nama_bawaan: "input_usaha.xlsx" }, "bahan");
  if (!p.length) return;
  try {
    const r = await api("/api/templat", { tujuan: p[0] });
    toast(`Templat disalin ke ${r.path}`);
    api("/api/buka", { path: r.path }).catch(() => {});
  } catch (e) { toast(e.message, 7000); }
}

// ============================================================ halaman: proses
async function halamanProses(isi) {
  const daftar = h("div", { class: "proses-daftar" });
  const kanan = h("div");
  const pilih = (id) => { S.prosesDipilih = id; gambar(); };
  const gambar = () => {
    daftar.replaceChildren(...(S.proses.length ? S.proses.map((p) => h("div", {
      class: `proses-baris ${p.id === S.prosesDipilih ? "aktif" : ""}`, onclick: () => pilih(p.id),
    }, h("span", { class: "redup", text: `#${p.id}` }), h("span", { class: "judul", text: p.judul, title: p.perintah }), lencanaStatus(p),
      h("span", { class: "redup kecil", text: p.mulai.slice(5, 16) }))) : [h("p", { class: "redup", text: "Belum ada proses di sesi GUI ini." })]));
    kanan.replaceChildren();
    if (S.prosesDipilih && S.proses.some((p) => p.id === S.prosesDipilih)) kanan.append(panelLog(S.prosesDipilih, { tinggi: 520 }));
  };
  if (!S.prosesDipilih && S.proses.length) S.prosesDipilih = S.proses[0].id;
  const riwayat = h("div", { class: "proses-daftar" });
  isi.append(h("section", { class: "kartu lebar" }, h("h2", { text: "Proses sesi ini" }),
    h("p", { class: "keterangan", text: "Proses tetap berjalan walau halaman ini ditutup — selama jendela hitam GUI tidak ditutup." }),
    daftar, kanan),
  h("section", { class: "kartu lebar" }, h("h3", { text: "Berkas log terakhir" }),
    h("p", { class: "keterangan", text: "Semua log tersimpan di gui/hasil/log/ (termasuk dari sesi GUI sebelumnya)." }), riwayat));
  gambar();
  const id = setInterval(() => { if (!daftar.isConnected) return clearInterval(id); const aktif = document.activeElement; if (!kanan.contains(aktif)) gambarDaftarSaja(); }, 3000);
  function gambarDaftarSaja() {
    daftar.replaceChildren(...S.proses.map((p) => h("div", { class: `proses-baris ${p.id === S.prosesDipilih ? "aktif" : ""}`, onclick: () => pilih(p.id) },
      h("span", { class: "redup", text: `#${p.id}` }), h("span", { class: "judul", text: p.judul, title: p.perintah }), lencanaStatus(p),
      h("span", { class: "redup kecil", text: p.mulai.slice(5, 16) }))));
  }
  try {
    const r = await api("/api/riwayat");
    riwayat.replaceChildren(...(r.log.length ? r.log.map((l) => h("div", { class: "proses-baris", onclick: () => api("/api/buka", { path: l.path }).catch((e) => toast(e.message)) },
      h("span", { class: "judul mono", text: l.nama }), h("span", { class: "redup kecil", text: `${l.waktu} · ${(l.ukuran / 1024).toFixed(0)} KB` }))) : [h("p", { class: "redup", text: "Belum ada." })]));
  } catch (e) { riwayat.replaceChildren(h("p", { class: "pesan merah", text: e.message })); }
}

// ============================================================ halaman: KBLI
function ambilKbliDariProses(p) {
  const k = (p.keluaran || []).find((x) => x.jenis === "kbli");
  if (!k) return false;
  S.kbli.hasil = k.path;
  S.kbli.sumber = (p.isian || {}).berkas || "";
  S.kbli.lembar = (p.isian || {}).lembar || "";
  S.kbli.data = null;
  return true;
}

function isiKbliDariProses(p, buka) {
  if (!ambilKbliDariProses(p)) return;
  if (buka) { pindah("kbli"); siapkanKbli(); } else if (S.halaman === "kbli") render();
}

function halamanKbli(isi) {
  const st = S.awal.kbli;
  const cek = (ok, teks, saran) => h("div", { class: "item" },
    h("span", { class: `ikon-status ${ok ? "ok" : "tidak"}`, text: ok ? "✓" : "✕" }),
    h("div", {}, h("strong", { text: teks }), !ok && saran ? h("div", { class: "redup kecil", text: saran }) : null), h("span"));
  const siap = st.ada && st.node && st.epapi_ada;
  isi.append(h("section", { class: "kartu lebar" },
    h("header", {}, h("h2", { text: "Generate KBLI — kesiapan" }),
      h("div", { class: "kanan" }, h("button", { class: "tombol kecil", text: "Periksa ulang", onclick: async () => {
        try { S.awal.kbli = await api("/api/kbli/status"); render(); } catch (e) { toast(e.message); }
      } }))),
    h("p", { class: "keterangan", text: `Proyek generate_kbli dipanggil dari ${st.folder} (ubah di Pengaturan > Aplikasi).` }),
    h("div", { class: "daftar-cek" },
      cek(st.ada, "generate_kbli.py ditemukan", "Salin/clone proyek generate_kbli ke sebelah folder proyek ini, atau atur foldernya di Pengaturan > Aplikasi."),
      cek(!!st.node, "Node.js terpasang", "Pasang Node.js dari nodejs.org."),
      cek(st.epapi_ada, `Folder epapi-se2026 (${st.epapi})`, "generate_kbli meminjam mesin leksikal dari proyek epapi-se2026."),
      h("div", { class: "item" },
        h("span", { class: `ikon-status ${st.model_ada ? "ok" : "opsional"}`, text: st.model_ada ? "✓" : "!" }),
        h("div", {}, h("strong", { text: "Model ONNX (±1,2 GB)" }),
          !st.model_ada ? h("div", { class: "redup kecil", text: "Tanpa model hanya pilihan Model = 'tanpa' yang bisa dipakai." }) : null),
        !st.model_ada && st.unduh_model_ada ? h("button", { class: "tombol kecil utama", text: "Unduh model", onclick: () => pasang("model_kbli") }) : h("span")))));
  if (siap) isi.append(formAlat(alat("kbli")));
  isi.append(kartuSalinKbli());
}

function kartuSalinKbli() {
  const k = S.kbli;
  if (!k.hasil) {
    const p = S.proses.find((x) => x.alat === "kbli" && x.status === "selesai");
    if (p) ambilKbliDariProses(p);
  }
  const hasil = h("div");
  const inputBerkas = (label, kunci, filter, jenis = "buka") => {
    const inp = h("input", { type: "text", value: k[kunci] || "", oninput: (e) => { k[kunci] = e.target.value.trim(); } });
    return h("div", { class: "isian" }, h("label", { class: "judul", text: label }),
      h("div", { class: "dengan-tombol" }, inp, h("button", { class: "tombol", text: "Pilih…", onclick: async () => {
        const p = await pilihDialog(jenis, { label, filter }, k[kunci]);
        if (p.length) { inp.value = p[0]; k[kunci] = p[0]; }
      } })));
  };
  const cekPertahankan = h("input", { type: "checkbox", checked: k.pertahankan, onchange: (e) => { k.pertahankan = e.target.checked; } });
  const kartu = h("section", { class: "kartu lebar" },
    h("h2", { text: "Salin hasil ke clipboard" }),
    h("p", { class: "keterangan", text: "Kode + Judul KBLI urut nomor baris sheet. Klik sel tujuan yang ditunjukkan (baris pertama data) lalu Ctrl+V. " +
      "Kode ditempel sbg TEKS supaya nol di depan (01464) tidak hilang di Excel." }),
    h("div", { class: "grid-isian" },
      inputBerkas("Berkas hasil generate KBLI (*_kbli.xlsx)", "hasil", [["Excel", "*.xlsx"]]),
      inputBerkas("Sheet asal (utk sel tujuan & kode yang sudah ada)", "sumber", [["Excel", "*.xlsx *.xlsm"]]),
      h("div", { class: "isian" }, h("label", { class: "judul", text: "Nama sheet asal" }),
        h("input", { type: "text", value: k.lembar, placeholder: "(sheet aktif)", oninput: (e) => { k.lembar = e.target.value.trim(); } })),
      h("div", { class: "isian" }, h("label", { class: "centang" }, cekPertahankan,
        h("span", { text: "Pertahankan kode KBLI yang SUDAH terisi di sheet (bedanya dilaporkan, tidak ditimpa)" })))),
    h("div", { class: "aksi" }, h("button", { class: "tombol utama", text: "Siapkan", onclick: siapkanKbli })),
    hasil);
  k.elHasil = hasil;
  if (k.data) gambarHasilKbli();
  return kartu;
}

async function siapkanKbli() {
  const k = S.kbli;
  if (!k.hasil) return toast("Pilih berkas hasil generate KBLI dulu.");
  try {
    k.data = await api("/api/salin/kbli", { hasil: k.hasil, sumber: k.sumber, lembar: k.lembar, pertahankan: k.pertahankan });
    gambarHasilKbli();
  } catch (e) {
    if (k.elHasil) k.elHasil.replaceChildren(h("div", { class: "pesan merah", text: e.message }));
    else toast(e.message, 6000);
  }
}

function tombolSalin(label, isi, tujuan) {
  return h("button", { class: "tombol utama", text: label, onclick: async () => {
    try {
      const cara = await salinKeClipboard(isi.teks, isi.html);
      toast(cara === "lengkap" ? `Tersalin${tujuan ? ` — klik sel ${tujuan} lalu Ctrl+V` : ""}` :
        "Tersalin sbg teks biasa — pastikan kolom tujuan berformat Teks supaya nol di depan tidak hilang.", 7000);
    } catch (e) { toast(e.message, 6000); }
  } });
}

function gambarHasilKbli() {
  const k = S.kbli;
  const d = k.data;
  if (!d || !k.elHasil) return;
  const r = d.ringkas;
  const tombol = d.salin.gabung
    ? [tombolSalin("Salin Kode + Judul", d.salin.gabung, d.tujuan.kode)]
    : [tombolSalin("Salin Kode KBLI", d.salin.kode, d.tujuan.kode), tombolSalin("Salin Judul KBLI", d.salin.judul, d.tujuan.judul)];
  const tabel = (judul, kolom, baris) => baris.length ? h("details", { class: "lanjutan", open: baris.length <= 30 },
    h("summary", { text: `${judul} (${baris.length})` }),
    h("div", { class: "tabel-bungkus", style: "max-height:420px" }, h("table", {},
      h("tr", {}, kolom.map(([, t]) => h("th", { text: t }))),
      baris.slice(0, 500).map((b) => h("tr", {}, kolom.map(([kk]) => h("td", { text: Array.isArray(b[kk]) ? b[kk].join(" | ") : String(b[kk] ?? "") }))))))) : null;
  k.elHasil.replaceChildren(
    h("div", { class: "pesan hijau", text: `Tempel di sel ${d.tujuan.kode || `kolom Kode KBLI baris ${d.mulai}`}` +
      (d.salin.gabung ? " (Judul KBLI ikut terisi di kolom kanannya)." : ".") }),
    h("div", { class: "baris-flex" },
      h("span", { class: "lencana", text: `${r.baris} baris` }), h("span", { class: "lencana ok", text: `${r.mesin} dari mesin` }),
      h("span", { class: "lencana biru", text: `${r.dipertahankan} dipertahankan` }), h("span", { class: "lencana", text: `${r.kosong} kosong` }),
      h("span", { class: `lencana ${r.periksa ? "kuning" : ""}`, text: `${r.periksa} bertanda PERIKSA` })),
    d.peringatan.map((p) => h("div", { class: "pesan kuning", text: p })),
    h("div", { class: "aksi" }, tombol),
    tabel("Baris bertanda PERIKSA — cek manual", [["baris", "Baris"], ["kode", "Kode"], ["judul", "Judul"], ["catatan", "Catatan"], ["alternatif", "Alternatif"]], d.periksa),
    tabel("Kode di sheet BEDA dgn saran mesin (sheet dipertahankan)", [["baris", "Baris"], ["kode_sheet", "Kode sheet"], ["kode_mesin", "Saran mesin"], ["judul_mesin", "Judul saran"]], d.beda));
}

function dialogHasilSalin(judul, d, namaKolom) {
  const r = d.ringkas;
  dialogPesan(`Salin ${judul}`, h("div", {},
    h("p", { text: `${r.baris} baris` + (r.berubah !== null && r.berubah !== undefined ? `, ${r.berubah} berubah` : "") +
      (r.dipertahankan ? `, ${r.dipertahankan} baris kosong di hasil diisi nilai asli sheet` : "") + "." }),
    h("div", { class: "pesan hijau", text: d.tujuan.kode ? `Tempel di sel ${d.tujuan.kode}.` : `Tempel di sel ${namaKolom} baris ${d.mulai}.` }),
    d.peringatan.map((p) => h("div", { class: "pesan kuning", text: p })),
    h("div", { class: "aksi" }, tombolSalin(`Salin ${judul}`, d.salin.gabung, d.tujuan.kode))));
}

// ============================================================ halaman: pengaturan
const DASAR = [
  ["KODE_KAB", "Kode kabupaten/kota (4 digit)", "teks"],
  ["GABUNGAN_AKUN_TUNGGAL", "Akun PPL pembuat dokumen (email)", "teks"],
  ["GABUNGAN_SUBSLS_TUNGGAL", "Subsls wadah dokumen (16 digit)", "teks"],
  ["GABUNGAN_BARIS_PER_SESI", "Login ulang tiap N baris", "int"],
  ["SURVEY_ID", "ID survei (segmen URL pertama fasih-web)", "teks"],
  ["ASSIGNMENT_ID_GABUNGAN", "ID periode (segmen URL list PENDATAAN)", "teks"],
];
const PATH_WILAYAH = [
  ["PETA_SLS_PATH", "Peta poligon subsls (GeoJSON)", [["GeoJSON / JSON", "*.json *.geojson"]]],
  ["TITIK_LISTING_PATH", "Titik geotag listing (CSV)", [["CSV", "*.csv"]]],
  ["JALAN_PATH", "Jaringan jalan (GeoJSON)", [["GeoJSON / JSON", "*.json *.geojson"]]],
];
const KHUSUS = new Set([...DASAR.map((x) => x[0]), ...PATH_WILAYAH.map((x) => x[0]), "TAHAP2_KOTAK_KOORDINAT",
  "KODEPOS_BY_DESA", "KODEPOS_BY_IDSUBSLS", "WILAYAH_BY_IDSUBSLS"]);
const KELOMPOK_ATURAN = [
  ["Aturan pengganti input tahap 2", /^TAHAP2_/],
  ["Jawaban bawaan kuesioner", /^(DEFAULT_|OPSI_|UMKM_|ISI_PILIH|KEPEMILIKAN|NAMA_PEMBERI|GALAT_13C|KBLI_DITOLAK)/],
  ["Batas & nilai minimal", /^(MINIMAL_|MIN_|BATAS_|POS_|LENGKAPI_)/],
  ["Format lama (Agenda)", /^GABUNGAN_/],
  ["Teknis", /^(DEFAULT_TIMEOUT|SAVE_|NAV_|BULAN_|KATA_|KATEGORI_)/],
  ["Lainnya", /./],
];

async function muatPengaturan() {
  const r = await api("/api/pengaturan");
  S.cfg = r.config;
  S.awal.config = r.config;
  S.awal.pengaturan = r.pengaturan;
  S.awal.kbli = r.kbli;
  S.draft = {
    timpa: salinObjek(r.pengaturan.timpa || {}), tambah: salinObjek(r.pengaturan.tambah || {}),
    pakai_config_lokal: r.pengaturan.pakai_config_lokal,
    gui: { kbli_folder: r.pengaturan.gui.kbli_folder || "", epapi_folder: r.pengaturan.gui.epapi_folder || "" },
  };
}

function berlakuTanpaGui(nama) {
  const it = itemConfig(nama);
  if (!it) return { nilai: undefined, asal: "" };
  if (S.draft.pakai_config_lokal && "lokal" in it) return { nilai: it.lokal, asal: "config_lokal.py" };
  return { nilai: it.bawaan, asal: "config.py" };
}

async function halamanPengaturan(isi) {
  isi.append(h("p", { class: "redup", text: "Memuat pengaturan…" }));
  try {
    if (!S.draft) await muatPengaturan();
  } catch (e) { isi.replaceChildren(h("div", { class: "pesan merah", text: e.message })); return; }
  isi.replaceChildren();
  const pesan = h("div", { class: "pesan merah", hidden: true });
  const simpan = async () => {
    pesan.hidden = true;
    try {
      const r = await api("/api/pengaturan", S.draft);
      S.awal.pengaturan = r.pengaturan;
      S.awal.kbli = r.kbli;
      S.draft = null;
      await muatPengaturan();
      toast("Pengaturan tersimpan (berlaku utk proses yang dijalankan sesudah ini).");
      perbaruiKepala();
      render();
    } catch (e) { pesan.textContent = e.message; pesan.hidden = false; window.scrollTo(0, 0); }
  };
  isi.append(h("section", { class: "kartu lebar", style: "position:sticky;top:60px;z-index:5" },
    h("div", { class: "baris-flex" },
      h("div", {}, h("h2", { text: "Pengaturan" }),
        h("div", { class: "redup kecil", text: "Disimpan di gui/pengaturan.json (tidak ikut git). Password TIDAK disimpan di sini." })),
      h("div", { style: "margin-left:auto", class: "baris-flex" },
        h("button", { class: "tombol", text: "Batalkan perubahan", onclick: async () => { S.draft = null; render(); } }),
        h("button", { class: "tombol utama", text: "Simpan pengaturan", onclick: simpan }))),
    pesan));
  isi.append(kartuDasar(), kartuWilayah(), kartuAturan(), kartuAplikasi());
}

function kartuDasar() {
  const d = S.draft;
  const baris = DASAR.map(([nama, label, jenis]) => {
    const b = berlakuTanpaGui(nama);
    const inp = h("input", { type: "text", value: nama in d.timpa ? tampilNilai(d.timpa[nama]) : "",
      placeholder: b.nilai !== undefined && tampilNilai(b.nilai) !== "" ? `${tampilNilai(b.nilai)}  (dari ${b.asal})` : "(kosong)",
      oninput: (e) => {
        const v = e.target.value.trim();
        if (!v) delete d.timpa[nama];
        else d.timpa[nama] = jenis === "int" && /^\d+$/.test(v) ? parseInt(v, 10) : v;
      } });
    return h("div", { class: "isian" }, h("label", { class: "judul", text: label }), inp,
      h("div", { class: "bantuan mono", text: nama }));
  });
  // kotak koordinat
  const bk = berlakuTanpaGui("TAHAP2_KOTAK_KOORDINAT");
  const sekarang = "TAHAP2_KOTAK_KOORDINAT" in d.timpa ? d.timpa.TAHAP2_KOTAK_KOORDINAT : undefined;
  const angka = sekarang && sekarang.__py__ ? sekarang.__py__.replace(/[()\s]/g, "").split(",") : ["", "", "", ""];
  const labelKotak = ["Lintang min", "Lintang maks", "Bujur min", "Bujur maks"];
  const inputKotak = labelKotak.map((l, j) => h("input", { type: "text", value: angka[j] || "", placeholder: l, "aria-label": l, oninput: () => ubahKotak() }));
  const tanpa = h("input", { type: "checkbox", checked: sekarang === null, onchange: () => ubahKotak() });
  function ubahKotak() {
    if (tanpa.checked) { d.timpa.TAHAP2_KOTAK_KOORDINAT = null; return; }
    const v = inputKotak.map((x) => x.value.trim().replace(",", "."));
    if (v.every((x) => !x)) delete d.timpa.TAHAP2_KOTAK_KOORDINAT;
    else d.timpa.TAHAP2_KOTAK_KOORDINAT = { __py__: `(${v.map((x) => x || "0").join(", ")})` };
  }
  const kotakEl = h("div", { class: "isian lebar-penuh" },
    h("label", { class: "judul", text: "Kotak koordinat kabupaten (utk memulihkan koordinat yang dirusak Excel)" }),
    h("div", { class: "grid-isian", style: "grid-template-columns:repeat(4,minmax(0,1fr));gap:6px" }, inputKotak),
    h("div", { class: "bantuan", text: `Berlaku sekarang: ${tampilNilai(bk.nilai)} (dari ${bk.asal}). Kosong = tidak diubah. ` +
      "Kotak bawaan = Kabupaten Buleleng — kabupaten lain WAJIB mengganti. Bisa dihitung dari peta SLS di bagian Wilayah." }),
    h("label", { class: "centang" }, tanpa, h("span", { text: "Jangan pulihkan koordinat rusak sama sekali (None)" })));
  return h("section", { class: "kartu lebar" }, h("h2", { text: "Dasar" }),
    h("p", { class: "keterangan", text: "Kosong = memakai nilai berlaku (abu-abu). Isi utk menimpa." }),
    h("div", { class: "grid-isian" }, baris, kotakEl));
}

function kartuWilayah() {
  const d = S.draft;
  const kab = String(tampilNilai(d.timpa.KODE_KAB ?? berlakuTanpaGui("KODE_KAB").nilai) || "");
  const dasarKp = berlakuTanpaGui("KODEPOS_BY_DESA").nilai || {};
  const guiKp = d.tambah.KODEPOS_BY_DESA || {};
  const cari = h("input", { type: "text", placeholder: "Cari kode desa…", style: "max-width:220px" });
  const tabel = h("div", { class: "tabel-bungkus", style: "max-height:320px" });
  const gambarTabel = () => {
    const q = cari.value.trim();
    const kode = [...new Set([...Object.keys(dasarKp).filter((x) => x.startsWith(kab)), ...Object.keys(guiKp)])].sort()
      .filter((x) => !q || x.includes(q));
    tabel.replaceChildren(h("table", {}, h("tr", {}, h("th", { text: "Kode desa (10 digit)" }), h("th", { text: "Kodepos" }), h("th", { text: "Sumber" }), h("th")),
      kode.slice(0, 400).map((x) => h("tr", {}, h("td", { class: "mono", text: x }), h("td", { class: "mono", text: guiKp[x] || dasarKp[x] }),
        h("td", { class: "redup", text: x in guiKp ? (x in dasarKp ? "GUI (menimpa config)" : "GUI") : "config" }),
        h("td", {}, x in guiKp ? h("button", { class: "tombol kecil polos", text: "Hapus", onclick: () => {
          delete guiKp[x]; d.tambah.KODEPOS_BY_DESA = guiKp; gambarTabel();
        } }) : null)))));
    jumlah.textContent = `${kode.length} desa${kode.length > 400 ? " (400 pertama ditampilkan)" : ""}`;
  };
  const jumlah = h("span", { class: "redup kecil" });
  cari.addEventListener("input", gambarTabel);
  const kodeBaru = h("input", { type: "text", placeholder: "kode desa 10 digit", style: "max-width:180px" });
  const kpBaru = h("input", { type: "text", placeholder: "kodepos", style: "max-width:110px" });
  const tambahSatu = () => {
    if (!/^\d{10}$/.test(kodeBaru.value.trim()) || !/^\d{5}$/.test(kpBaru.value.trim())) return toast("Kode desa 10 digit & kodepos 5 digit.");
    guiKp[kodeBaru.value.trim()] = kpBaru.value.trim();
    d.tambah.KODEPOS_BY_DESA = guiKp;
    kodeBaru.value = ""; kpBaru.value = "";
    gambarTabel();
  };
  gambarTabel();

  const itW = itemConfig("WILAYAH_BY_IDSUBSLS") || {};
  const nW = Object.keys(d.tambah.WILAYAH_BY_IDSUBSLS || {}).length;
  const nKpS = Object.keys(d.tambah.KODEPOS_BY_IDSUBSLS || {}).length;
  const paths = PATH_WILAYAH.map(([nama, label, filter]) => {
    const b = berlakuTanpaGui(nama);
    const inp = h("input", { type: "text", value: nama in d.timpa ? d.timpa[nama] : "",
      placeholder: b.nilai ? `${b.nilai}  (dari ${b.asal})` : "(belum diatur)",
      oninput: (e) => { const v = e.target.value.trim(); if (v) d.timpa[nama] = v; else delete d.timpa[nama]; } });
    return h("div", { class: "isian" }, h("label", { class: "judul", text: label }),
      h("div", { class: "dengan-tombol" }, inp, h("button", { class: "tombol", text: "Pilih…", onclick: async () => {
        const p = await pilihDialog("buka", { label, filter });
        if (p.length) { inp.value = p[0]; d.timpa[nama] = p[0]; }
      } })), h("div", { class: "bantuan mono", text: nama }));
  });

  return h("section", { class: "kartu lebar" }, h("h2", { text: "Wilayah" }),
    h("h3", { class: "jarak-atas", text: "Kodepos per desa" }),
    h("p", { class: "keterangan", text: `Sheet input tidak punya kolom kodepos; kodepos diambil per DESA (10 digit awal idsubsls). Desa yang tidak ada di sini ditolak ` +
      `(SKIP_DATA_KODEPOS_TIDAK_DIKETAHUI). Ditampilkan desa berawalan ${kab || "KODE_KAB"}.` }),
    h("div", { class: "baris-flex" }, cari, jumlah,
      h("button", { class: "tombol kecil", style: "margin-left:auto", text: "Impor dari Excel/CSV…", onclick: () => dialogImporTabel("kodepos") }),
      h("button", { class: "tombol kecil", text: "Susun dari sheet lama…", onclick: dialogKodeposLama })),
    tabel,
    h("div", { class: "baris-flex jarak-atas" }, kodeBaru, kpBaru, h("button", { class: "tombol kecil", text: "Tambah", onclick: tambahSatu })),
    nKpS ? h("p", { class: "redup kecil", text: `+ ${nKpS} kodepos per idsubsls dari GUI.` }) : null,
    h("h3", { class: "jarak-atas", text: "Nama wilayah per subsls (opsional)" }),
    h("p", { class: "keterangan", text: `Dipakai utk melengkapi alamat pendek & log. config: ${itW.jumlah ?? 0}` +
      (itW.jumlah_lokal !== undefined ? ` (config_lokal: ${itW.jumlah_lokal})` : "") + ` · tambahan GUI: ${nW} subsls.` }),
    h("div", { class: "baris-flex" },
      h("button", { class: "tombol kecil", text: "Impor dari peta SLS (GeoJSON)…", onclick: dialogImporPeta }),
      h("button", { class: "tombol kecil", text: "Impor dari Excel/CSV…", onclick: () => dialogImporTabel("wilayah") }),
      nW ? h("button", { class: "tombol kecil polos", text: "Hapus tambahan GUI", onclick: () => { delete d.tambah.WILAYAH_BY_IDSUBSLS; render(); } }) : null),
    h("h3", { class: "jarak-atas", text: "Berkas peta (utk Koordinat pengganti)" }),
    h("div", { class: "grid-isian" }, paths));
}

async function dialogImporTabel(jenis) {
  const p = await pilihDialog("buka", { label: "Pilih tabel", filter: [["Excel / CSV", "*.xlsx *.xlsm *.csv"]] });
  if (!p.length) return;
  let pra;
  let lembar = "";
  // Tebakan awal kolom dari judulnya (pola dicoba berurutan, yang ketat dulu) — pengguna tetap memeriksa & memilih.
  const peran = jenis === "kodepos"
    ? [["kode", "Kode desa (10 digit) ATAU idsubsls (16 digit)", [/^iddesa$/i, /kode ?desa/i, /^idsubsls$/i]], ["kodepos", "Kodepos", [/kode ?pos/i]]]
    : [["idsubsls", "idsubsls (16 digit)", [/^idsubsls$/i]], ["provinsi", "Nama provinsi", [/^nmprov$/i, /nama ?prov/i]],
      ["kabkota", "Nama kab/kota", [/^nmkab$/i, /nama ?kab/i]], ["kecamatan", "Nama kecamatan", [/^nmkec$/i, /nama ?kec/i]],
      ["desa", "Nama desa", [/^nmdesa$/i, /nama ?(desa|kel)/i]], ["sls", "Nama SLS", [/^nmsls$/i, /nama ?sls/i]],
      ["subsls", "Nama subsls", [/^nmsubsls$/i, /nama ?subsls/i, /^nmsls$/i]]];
  const tebak = (pola) => {
    for (const p of pola) { const i = pra.judul.findIndex((j) => p.test(String(j || "").trim())); if (i >= 0) return String(i); }
    return "";
  };
  const muat = async () => {
    pra = await api("/api/pengaturan/tabel", { path: p[0], lembar });
  };
  try { await muat(); } catch (e) { return toast(e.message, 7000); }
  const isi = h("div");
  const pilihan = {};
  const gambar = () => {
    const opsi = [h("option", { value: "", text: "(tidak ada)" }), ...pra.judul.map((j, idx) => h("option", { value: String(idx), text: `${idx + 1}. ${j || "(tanpa judul)"}` }))];
    isi.replaceChildren(
      pra.lembar.length > 1 ? h("div", { class: "isian" }, h("label", { class: "judul", text: "Sheet" }),
        (() => { const s = h("select", { onchange: async (e) => { lembar = e.target.value; await muat(); gambar(); } }, pra.lembar.map((l) => h("option", { value: l, text: l }))); s.value = lembar || pra.lembar[0]; return s; })()) : null,
      h("p", { class: "redup", text: `${pra.jumlah} baris data. Pilih kolom utk tiap isian (sudah ditebak dari judul — periksa!):` }),
      h("div", { class: "grid-isian" }, peran.map(([k, label, pola]) => {
        const s = h("select", { onchange: (e) => { pilihan[k] = e.target.value; } }, opsi.map((o) => o.cloneNode(true)));
        if (!(k in pilihan)) pilihan[k] = tebak(pola);
        s.value = pilihan[k];
        return h("div", { class: "isian" }, h("label", { class: "judul", text: label }), s);
      })),
      h("div", { class: "tabel-bungkus jarak-atas", style: "max-height:220px" }, h("table", {},
        h("tr", {}, pra.judul.map((j) => h("th", { text: j }))), pra.contoh.map((r) => h("tr", {}, r.map((c) => h("td", { text: c })))))));
  };
  gambar();
  bukaDialog([h("h2", { text: jenis === "kodepos" ? "Impor kodepos" : "Impor nama wilayah" }), h("p", { class: "mono kecil", text: p[0] }), isi,
    h("div", { class: "aksi" }, h("button", { class: "tombol", text: "Batal", onclick: tutupDialog }),
      h("button", { class: "tombol utama", text: "Impor", onclick: async () => {
        try {
          const r = await api("/api/pengaturan/impor-tabel", { path: p[0], lembar, jenis, kolom: pilihan });
          const d = S.draft;
          let teks;
          if (jenis === "kodepos") {
            d.tambah.KODEPOS_BY_DESA = { ...(d.tambah.KODEPOS_BY_DESA || {}), ...r.data.desa };
            d.tambah.KODEPOS_BY_IDSUBSLS = { ...(d.tambah.KODEPOS_BY_IDSUBSLS || {}), ...r.data.subsls };
            teks = `${Object.keys(r.data.desa).length} desa + ${Object.keys(r.data.subsls).length} idsubsls ditambahkan`;
          } else {
            d.tambah.WILAYAH_BY_IDSUBSLS = { ...(d.tambah.WILAYAH_BY_IDSUBSLS || {}), ...r.data };
            teks = `${Object.keys(r.data).length} subsls ditambahkan`;
          }
          tutupDialog();
          render();
          dialogPesan("Impor selesai", h("div", {}, h("p", { text: `${teks}. Klik 'Simpan pengaturan' utk menyimpan.` }),
            r.dilewati.length ? h("details", {}, h("summary", { text: `${r.dilewati.length} baris dilewati` }), h("pre", { class: "cuplikan", text: r.dilewati.slice(0, 300).join("\n") })) : null));
        } catch (e) { toast(e.message, 7000); }
      } }))], "lebar");
}

async function dialogKodeposLama() {
  const p = await pilihDialog("buka_banyak", { label: "Sheet lama berkolom kodepos (format agenda)", filter: [["Excel / CSV", "*.xlsx *.csv"]] });
  if (!p.length) return;
  toast("Menyusun kodepos…");
  try {
    const r = await api("/api/pengaturan/kodepos-lama", { dari: p });
    const n = Object.keys(r.pilih).length;
    const bentrok = Object.entries(r.bentrok);
    bukaDialog([h("h2", { text: "Kodepos dari sheet lama" }),
      h("p", { text: `${n} desa mendapat kodepos (suara terbanyak per desa; seri tidak dipilih).` }),
      bentrok.length ? h("details", {}, h("summary", { text: `${bentrok.length} desa bentrok (lebih dari satu kodepos)` }),
        h("pre", { class: "cuplikan", text: bentrok.map(([d, c]) => `${d}: ${Object.entries(c).map(([k, v]) => `${k}×${v}`).join(", ")}`).join("\n") })) : null,
      h("div", { class: "aksi" }, h("button", { class: "tombol", text: "Batal", onclick: tutupDialog }),
        h("button", { class: "tombol utama", text: `Tambahkan ${n} desa`, disabled: !n, onclick: () => {
          S.draft.tambah.KODEPOS_BY_DESA = { ...(S.draft.tambah.KODEPOS_BY_DESA || {}), ...r.pilih };
          tutupDialog(); render(); toast("Ditambahkan — klik 'Simpan pengaturan'.");
        } }))]);
  } catch (e) { toast(e.message, 7000); }
}

async function dialogImporPeta() {
  const d = S.draft;
  let path = d.timpa.PETA_SLS_PATH || berlakuTanpaGui("PETA_SLS_PATH").nilai || "";
  if (!path) {
    const p = await pilihDialog("buka", { label: "Peta poligon subsls", filter: [["GeoJSON / JSON", "*.json *.geojson"]] });
    if (!p.length) return;
    path = p[0];
  }
  const kab = String(tampilNilai(d.timpa.KODE_KAB ?? berlakuTanpaGui("KODE_KAB").nilai) || "");
  if (d.timpa.KODE_KAB && d.timpa.KODE_KAB !== efektif("KODE_KAB")) return toast("Simpan KODE_KAB baru dulu, lalu impor peta.", 6000);
  toast("Membaca peta (bisa ±1 menit)…");
  try {
    const r = await api("/api/pengaturan/impor-peta", { path, margin: 0.05 });
    const cekW = h("input", { type: "checkbox", checked: r.jumlah > 0 });
    const cekK = h("input", { type: "checkbox", checked: !!r.kotak });
    bukaDialog([h("h2", { text: "Impor dari peta SLS" }), h("p", { class: "mono kecil", text: path }),
      h("p", { text: `${r.jumlah} subsls kabupaten ${kab}` + (r.kab_lain ? ` (${r.kab_lain} subsls kabupaten lain dilewati)` : "") + "." }),
      r.kolom_kosong.length ? h("p", { class: "pesan kuning", text: `Kolom kosong di sebagian subsls: ${r.kolom_kosong.join(", ")}` }) : null,
      h("label", { class: "centang" }, cekW, h("span", { text: `Pakai nama wilayah ${r.jumlah} subsls` })),
      r.kotak ? h("label", { class: "centang" }, cekK, h("span", { text: `Pakai kotak koordinat ${JSON.stringify(r.kotak)} (batas poligon + 0,05°)` })) : null,
      h("div", { class: "aksi" }, h("button", { class: "tombol", text: "Batal", onclick: tutupDialog }),
        h("button", { class: "tombol utama", text: "Pakai", onclick: () => {
          if (cekW.checked) d.tambah.WILAYAH_BY_IDSUBSLS = { ...(d.tambah.WILAYAH_BY_IDSUBSLS || {}), ...r.wilayah };
          if (r.kotak && cekK.checked) d.timpa.TAHAP2_KOTAK_KOORDINAT = { __py__: `(${r.kotak.join(", ")})` };
          if (!d.timpa.PETA_SLS_PATH && !berlakuTanpaGui("PETA_SLS_PATH").nilai) d.timpa.PETA_SLS_PATH = path;
          tutupDialog(); render(); toast("Diterapkan ke draf — klik 'Simpan pengaturan'.");
        } }))]);
  } catch (e) { toast(e.message, 8000); }
}

function kartuAturan() {
  const d = S.draft;
  const cari = h("input", { type: "text", placeholder: "Cari nama / keterangan…", style: "max-width:320px" });
  const wadah = h("div");
  const semua = ((S.cfg || {}).pengaturan || []).filter((x) => !KHUSUS.has(x.nama));
  const gambar = () => {
    const q = cari.value.trim().toLowerCase();
    wadah.replaceChildren();
    const sudah = new Set();
    for (const [judul, pola] of KELOMPOK_ATURAN) {
      const anggota = semua.filter((x) => !sudah.has(x.nama) && pola.test(x.nama));
      anggota.forEach((x) => sudah.add(x.nama));
      const tampil = anggota.filter((x) => !q || x.nama.toLowerCase().includes(q) || (x.komentar || "").toLowerCase().includes(q));
      if (!tampil.length) continue;
      const diubah = tampil.filter((x) => x.nama in d.timpa).length;
      wadah.append(h("details", { class: "lanjutan", open: !!q || diubah > 0 },
        h("summary", { text: `${judul} (${tampil.length}${diubah ? `, ${diubah} diubah` : ""})` }),
        tampil.map(barisAturan)));
    }
  };
  cari.addEventListener("input", gambar);
  gambar();
  return h("section", { class: "kartu lebar" }, h("h2", { text: "Aturan pengisian (lanjutan)" }),
    h("p", { class: "keterangan", text: "Nilai pengganti & jawaban bawaan yang dipakai saat sheet kosong/rusak — semuanya ketetapan BPS Buleleng. " +
      "TINJAU sebelum mengirim data sungguhan; centang 'Ubah' utk menimpa. Keterangan diambil dari komentar inti/config.py." }),
    cari, wadah);
}

function barisAturan(it) {
  const d = S.draft;
  const b = berlakuTanpaGui(it.nama);
  const bisa = !(b.nilai && typeof b.nilai === "object" && "__tidak_bisa_diubah__" in b.nilai);
  const ubah = h("input", { type: "checkbox", checked: it.nama in d.timpa, disabled: !bisa });
  let editor;
  const awal = it.nama in d.timpa ? d.timpa[it.nama] : b.nilai;
  const setNilai = (v) => { d.timpa[it.nama] = v; };
  if (it.jenis === "bool") {
    editor = h("select", { onchange: (e) => setNilai(e.target.value === "1") }, h("option", { value: "1", text: "True (ya)" }), h("option", { value: "0", text: "False (tidak)" }));
    editor.value = awal ? "1" : "0";
  } else if (it.jenis === "int" || it.jenis === "float") {
    editor = h("input", { type: "text", inputmode: "decimal", value: String(awal ?? ""), oninput: (e) => {
      const v = e.target.value.trim().replace(",", ".");
      setNilai(it.jenis === "int" ? (/^-?\d+$/.test(v) ? parseInt(v, 10) : v) : (Number.isFinite(parseFloat(v)) ? parseFloat(v) : v));
    } });
  } else if (it.jenis === "str") {
    editor = h("input", { type: "text", value: awal ?? "", oninput: (e) => setNilai(e.target.value) });
  } else {
    editor = h("textarea", { rows: 3, class: "mono", value: tampilNilai(awal), oninput: (e) => setNilai({ __py__: e.target.value }) });
  }
  const wadahEditor = h("div", { hidden: !ubah.checked }, editor, h("div", { class: "bantuan", text: it.jenis === "str" || it.jenis === "bool" || it.jenis === "int" || it.jenis === "float" ? "" : "Tulis sbg nilai Python (tuple pakai kurung, True/False/None)." }));
  ubah.addEventListener("change", () => {
    wadahEditor.hidden = !ubah.checked;
    if (ubah.checked) editor.dispatchEvent(new Event(editor.tagName === "SELECT" ? "change" : "input"));
    else delete d.timpa[it.nama];
  });
  const komentar = it.komentar || "";
  return h("div", { class: "aturan" },
    h("div", {}, h("div", { class: "nama", text: it.nama }),
      komentar ? h("div", { class: "komentar", text: komentar.length > 420 ? komentar.slice(0, 420) + "…" : komentar, title: komentar }) : null),
    h("div", {}, h("div", { class: "kecil" }, h("span", { class: "redup", text: `Berlaku (${b.asal}): ` }),
      h("code", { text: tampilNilai(b.nilai).slice(0, 300) })),
    bisa ? h("label", { class: "centang jarak-atas" }, ubah, h("span", { text: "Ubah di GUI" })) : h("div", { class: "redup kecil", text: "Tidak bisa diubah dari GUI (ubah lewat inti/config_lokal.py)." }),
    wadahEditor));
}

function kartuAplikasi() {
  const d = S.draft;
  const st = S.awal.kbli;
  const cfg = S.cfg || {};
  const berkas = h("input", { type: "file", accept: ".json", hidden: true, onchange: async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const j = JSON.parse(await f.text());
      if (j.aplikasi !== "inject-usaha-gui" || typeof j.timpa !== "object") throw new Error("Bukan berkas ekspor pengaturan GUI.");
      d.timpa = j.timpa || {};
      d.tambah = j.tambah || {};
      if ("pakai_config_lokal" in j) d.pakai_config_lokal = !!j.pakai_config_lokal;
      render();
      toast("Pengaturan diimpor ke draf — tinjau lalu klik 'Simpan pengaturan'.", 7000);
    } catch (er) { toast(er.message, 7000); }
  } });
  const folder = (kunci, label, bawaan) => {
    const inp = h("input", { type: "text", value: d.gui[kunci], placeholder: bawaan, oninput: (e) => { d.gui[kunci] = e.target.value.trim(); } });
    return h("div", { class: "isian" }, h("label", { class: "judul", text: label }),
      h("div", { class: "dengan-tombol" }, inp, h("button", { class: "tombol", text: "Pilih…", onclick: async () => {
        const p = await pilihDialog("folder", { label });
        if (p.length) { inp.value = p[0]; d.gui[kunci] = p[0]; }
      } })));
  };
  const cekLokal = h("input", { type: "checkbox", checked: d.pakai_config_lokal, onchange: (e) => { d.pakai_config_lokal = e.target.checked; } });
  return h("section", { class: "kartu lebar" }, h("h2", { text: "Aplikasi" }),
    cfg.config_lokal_ada ? h("label", { class: "centang" }, cekLokal,
      h("span", { text: "Pakai juga inti/config_lokal.py PC ini sbg dasar (pengaturan GUI menimpanya)" })) :
      h("p", { class: "redup", text: "inti/config_lokal.py tidak ada di PC ini — semua pengaturan dari GUI." }),
    cfg.galat_config_lokal ? h("div", { class: "pesan merah", text: `config_lokal.py galat: ${cfg.galat_config_lokal}` }) : null,
    h("h3", { class: "jarak-atas", text: "Generate KBLI" }),
    h("div", { class: "grid-isian" },
      folder("kbli_folder", "Folder proyek generate_kbli", st.folder),
      folder("epapi_folder", "Folder proyek epapi-se2026", st.epapi)),
    h("h3", { class: "jarak-atas", text: "Ekspor / impor" }),
    h("p", { class: "keterangan", text: "Bagikan pengaturan kabupaten ke PC lain (tanpa password & tanpa isian formulir). Berkasnya memuat email akun — jangan diunggah ke tempat publik." }),
    h("div", { class: "baris-flex" },
      h("button", { class: "tombol", text: "Ekspor pengaturan (.json)", onclick: () => {
        const data = { aplikasi: "inject-usaha-gui", versi: 1, dibuat: new Date().toISOString(), pakai_config_lokal: d.pakai_config_lokal, timpa: d.timpa, tambah: d.tambah };
        const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" })),
          download: `pengaturan_gui_${tampilNilai(d.timpa.KODE_KAB ?? efektif("KODE_KAB")) || "kab"}.json` });
        document.body.append(a); a.click(); a.remove();
      } }),
      h("button", { class: "tombol", text: "Impor pengaturan…", onclick: () => berkas.click() }), berkas));
}

// ============================================================ mulai
async function mulai() {
  terapkanTema();
  try {
    S.awal = await api("/api/awal");
  } catch (e) {
    $("#isi").replaceChildren(h("div", { class: "pesan merah", text: `Gagal memuat GUI: ${e.message}` }));
    return;
  }
  S.password = S.awal.password;
  isiNilaiAwal();
  const hash = location.hash.slice(1);
  if (MENU.some((m) => m[0] === hash)) S.halaman = hash;
  perbaruiKepala();
  renderNav();
  render();
  setInterval(pollProses, 1500);
  pollProses();
  if (S.awal.peringatan) toast(S.awal.peringatan, 10000);
  if (!S.awal.password.tersedia) dialogPassword(true);
}
mulai();
