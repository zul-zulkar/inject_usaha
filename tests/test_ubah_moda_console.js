// Uji logika murni ubah_moda_console.js — offline (Node), tanpa browser/VPN.
// Kasusnya sama dgn tests/test_ubah_moda.py supaya kedua implementasi tidak menyimpang.
// Jalankan: node tests/test_ubah_moda_console.js
"use strict";
const path = require("path");
const m = require(path.join(__dirname, "..", "fasih_sm", "ganti_moda", "ubah_moda_console.js"));

let okAll = true;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  okAll = okAll && ok;
  console.log(`${ok ? "PASS" : "FAIL"} | ${label}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const S = "5108070013000901";
const PPL = "ppl@gmail.com";
const T = { idsubsls: S, ppl: [PPL] };
const b = (no, mode = "CAPI", petugas = PPL, sub = S, indeks = 0) =>
  ({ kode: `${sub} - UMK - ${no}`, idsubsls: sub, mode, petugas, status: "", keterangan: "", indeks });

check("template: TARGET kosong", m.TARGET, []);

// --- tabel: judul & isi persis seperti terbaca di fasih-sm 2026-09-13 ---
const HEAD = ["", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist", "Nomor Urut Bangunan / IDSBR",
  "NIB / No. KK", "Email", "Skala Usaha / Jenis Prelist", "Jumlah Usaha", "Kode Pos", "Perubahan SLS",
  "IDSBR UMKM SLS Sama", "Status", "Mode", "Petugas Saat Ini", "Keterangan", ""];
const ROW = ["", "5108060003000402 - UMK - 4", "USAHA CONTOH", "DSN CONTOH", "58 / 00000000",
  "0000000000000", "usaha.contoh@gmail.com", "UMK / OSS PERORANGAN", "", "81119", "", "",
  "approved by pengawas", "CAPI", "pml.contoh@gmail.com", "Pengawas", ""];
const hasil = m.barisDariTabel({ head: HEAD, rows: [ROW, ["Tidak ada data"]] });
check("parse tabel: 1 baris, baris pesan dilewati", hasil.length, 1);
check("parse kolom lewat judul", [hasil[0].idsubsls, hasil[0].mode, hasil[0].petugas, hasil[0].keterangan],
  ["5108060003000402", "CAPI", "pml.contoh@gmail.com", "Pengawas"]);
try {
  m.barisDariTabel({ head: HEAD.filter((h) => h !== "Mode"), rows: [] });
  check("kolom Mode disembunyikan -> berhenti", "tidak berhenti", "KOLOM_TIDAK_ADA");
} catch (e) {
  check("kolom Mode disembunyikan -> berhenti", e.kode, "KOLOM_TIDAK_ADA");
}

// --- rencanakan (cakupan satu) ---
const LAIN = "5108010009000202";
check("tanpa assignment", m.rencanakan(T, []).status, "TIDAK_ADA_ASSIGNMENT");
check("mode aneh", m.rencanakan(T, [b(1, "CAWI")]).status, "MODE_TIDAK_DIKENAL");
check("sudah ada PAPI milik PPL", m.rencanakan(T, [b(1, "PAPI"), b(2)]).status, "SUDAH_ADA_PAPI");
let r = m.rencanakan(T, [b(1, "CAPI", "lain@gmail.com"), b(2), b(3)]);
check("CAPI milik PPL didahulukan -> pilih tepat satu", [r.status, r.pilih.map((x) => x.kode)], ["PERLU_DIUBAH", [`${S} - UMK - 2`]]);
check("email petugas beda huruf besar tetap cocok",
  m.rencanakan(T, [b(1, "CAPI", "x@gmail.com"), b(2, "CAPI", "PPL@Gmail.com")]).pilih[0].kode, `${S} - UMK - 2`);
// Ketetapan user 2026-09-14: assignment MANA PUN di subsls itu boleh (dulu PETUGAS_BEDA / PAPI_ADA_PETUGAS_LAIN).
check("PAPI milik petugas lain sudah cukup",
  m.rencanakan(T, [b(1, "PAPI", "x@gmail.com"), b(2, "CAPI", "y@gmail.com")]).status, "SUDAH_ADA_PAPI");
r = m.rencanakan(T, [b(1, "CAPI", "x@gmail.com"), b(2, "CAPI", "y@gmail.com")]);
check("CAPI semua milik petugas lain -> tetap pilih satu", [r.status, r.pilih.map((x) => x.kode)],
  ["PERLU_DIUBAH", [`${S} - UMK - 1`]]);

// --- baris subsls lain di hasil pencarian (dryrun 2026-09-14) -> diabaikan, bukan berhenti ---
r = m.rencanakan(T, [b(1, "CAPI", PPL, LAIN), b(2, "CAPI", "x@gmail.com"), b(3, "PAPI", PPL, LAIN)]);
check("subsls lain diabaikan: pilih baris subsls target saja", [r.status, r.pilih.map((x) => x.kode)],
  ["PERLU_DIUBAH", [`${S} - UMK - 2`]]);
check("subsls lain dicatat di pesan", /2 baris subsls lain diabaikan/.test(r.pesan), true);
check("PAPI subsls lain tidak dihitung", m.rencanakan(T, [b(1, "PAPI", PPL, LAIN), b(2)]).status, "PERLU_DIUBAH");
check("hanya subsls lain di halaman -> berhenti (pencarian tidak menyaring)",
  m.rencanakan(T, [b(1, "CAPI", PPL, LAIN)]).status, "SUBSLS_TIDAK_TAMPIL");
check("halaman kosong tapi ada halaman lain -> berhenti", m.rencanakan(T, [], "satu", true).status, "SUBSLS_TIDAK_TAMPIL");

// --- paginasi TIDAK dipindah (temuan user 2026-09-14): hanya halaman tampil yang dibaca ---
r = m.rencanakan(T, [b(1)], "satu", true);
check("ada halaman lain tapi CAPI tampil -> tetap diubah, dicatat",
  [r.status, /hanya halaman tampil/.test(r.pesan)], ["PERLU_DIUBAH", true]);
check("ada halaman lain & PAPI tampil -> sudah cukup", m.rencanakan(T, [b(1), b(2, "PAPI")], "satu", true).status,
  "SUDAH_ADA_PAPI");

// --- rencanakan (cakupan semua) ---
r = m.rencanakan(T, [b(1), b(2, "PAPI"), b(3, "CAPI", "x@gmail.com"), b(4, "CAPI", PPL, LAIN)], "semua");
check("semua: seluruh CAPI subsls ini, PAPI & subsls lain dilewati", [r.status, r.pilih.length], ["PERLU_DIUBAH", 2]);
check("semua: sudah PAPI semua", m.rencanakan(T, [b(1, "PAPI")], "semua").status, "TIDAK_ADA_CAPI");
check("semua: tanpa CAPI tampil tapi ada halaman lain -> berhenti", m.rencanakan(T, [b(1, "PAPI")], "semua", true).status,
  "PERLU_HALAMAN_LAIN");

// --- list kode identitas milik user (2026-09-15): HANYA kode itu yang diubah ---
check("normalisasi kode: spasi & huruf kecil & nol depan", m.normalisasiKode(`${S}-umk-04`), `${S} - UMK - 4`);
check("normalisasi kode: bukan kode", m.normalisasiKode(S), "");
check("normalisasi kode: 17 digit bukan idsubsls", m.normalisasiKode(`9${S} - UMK - 4`), "");
let dk = m.targetDariDaftarKode([
  "Kode Identitas\tNama",                       // judul: diabaikan diam-diam
  `${S} - UMK - 4\tWARUNG A`,
  `${S} - UMK - 41`,
  `${LAIN} - UMK - 2 ; ${S} - umk - 4`,         // dua kode sebaris, satu ganda
  "5108070013000999\tNIK tanpa kode",           // 16 digit bukan kode -> dilaporkan
  `${S} - WARUNG - BU SRI - 12`,                // " - " di tengah nama: tidak ditebak
  `${S} - NON-UMK - 3`,                         // "-" tanpa spasi boleh
]);
check("daftar kode: SATU target per kode, urutan list dipertahankan",
  dk.targets.map((t) => [t.kode, t.idsubsls, t.baris]),
  [[`${S} - UMK - 4`, S, [2]], [`${S} - UMK - 41`, S, [3]], [`${LAIN} - UMK - 2`, LAIN, [4]],
    [`${S} - NON-UMK - 3`, S, [7]]]);
check("daftar kode: ganda dilaporkan", dk.ganda, [[4, `${S} - UMK - 4`]]);
check("daftar kode: 16 digit tanpa pola kode dilaporkan", dk.tidakDikenali.map((x) => x[0]), [5, 6]);
// Bentuk nyata dari list user & tabel fasih-sm (2026-09-15)
check("kode nama keluarga dgn '/'", m.normalisasiKode("5108060029000102 - I KETUT CONTOH / I KOMANG AGUS CONTOH - 46"),
  "5108060029000102 - I KETUT CONTOH / I KOMANG AGUS CONTOH - 46");
check("kode nama diakhiri '/'", m.normalisasiKode("5108070005000601 - WAYAN CONTOH / - 21"),
  "5108070005000601 - WAYAN CONTOH / - 21");
check("kode nama berangka", m.normalisasiKode("5108020014000104 - MUH UMAR FARIDL / 1 - 48"),
  "5108020014000104 - MUH UMAR FARIDL / 1 - 48");
check("kode nama ber-apostrof & titik", m.normalisasiKode(`${S} - WR. MAK'E (BU TUT) - 9`), `${S} - WR. MAK'E (BU TUT) - 9`);
check("sel tabel berakhiran '/ - 81119'", m.normalisasiKode("5108060029000102 - BANGUNAN KOSONG - 6 / - 81119"),
  "5108060029000102 - BANGUNAN KOSONG - 6");
check("sel tabel berakhiran '/ - 0'", m.normalisasiKode("5108060029000102 - I KADEK RIKI CONTOH / KETUT CONTOH - 46 / - 0"),
  "5108060029000102 - I KADEK RIKI CONTOH / KETUT CONTOH - 46");
check("kode dari xlsx (tab + nama)", m.normalisasiKode(`${S} - DTSEN - 44\tNAMA`), `${S} - DTSEN - 44`);

// Pencarian memakai KODE itu sendiri; hasil pencarian "…- UMK - 4" bisa ikut memuat "- 41", "- 40", dst.
const TK = { kode: `${S} - UMK - 4`, idsubsls: S, ppl: [], baris: [2] };
check("kode: istilah cari = kode identitas", m.istilahCari(TK), `${S} - UMK - 4`);
check("sheet: istilah cari = idsubsls", m.istilahCari(T), S);
r = m.rencanakan(TK, [b(41), b(4, "CAPI", "x@gmail.com"), b(40)]);
check("kode: pilih PERSIS '- 4', bukan '- 41'/'- 40'", [r.status, r.pilih.map((x) => x.kode)],
  ["PERLU_DIUBAH", [`${S} - UMK - 4`]]);
check("kode: baris lain yg ikut tampil dicatat", /2 baris kode lain/.test(r.pesan), true);
check("kode: kode di tabel beda spasi/huruf tetap cocok",
  m.rencanakan(TK, [{ ...b(4), kode: `${S}-umk-4` }]).status, "PERLU_DIUBAH");
check("kode: PAPI lain di subsls TIDAK membuat kode ini dilewati", m.rencanakan(TK, [b(41, "PAPI"), b(4)]).status,
  "PERLU_DIUBAH");
check("kode: sudah PAPI", m.rencanakan(TK, [b(4, "PAPI")]).status, "KODE_SUDAH_PAPI");
check("kode: KODE_SUDAH_PAPI tuntas", m.STATUS_TUNTAS_LIVE.has("KODE_SUDAH_PAPI"), true);
check("kode: hasil kosong -> KODE_TIDAK_ADA (lanjut)", m.rencanakan(TK, []).status, "KODE_TIDAK_ADA");
check("kode: hanya kode lain subsls sama -> KODE_TIDAK_ADA", m.rencanakan(TK, [b(41)]).status, "KODE_TIDAK_ADA");
check("kode: tidak ada di halaman tampil tapi >1 halaman -> KODE_TIDAK_TAMPIL",
  m.rencanakan(TK, [b(41)], "satu", true).status, "KODE_TIDAK_TAMPIL");
check("kode: KODE_TIDAK_ADA/TIDAK_TAMPIL tidak tuntas & tidak menghentikan",
  ["KODE_TIDAK_ADA", "KODE_TIDAK_TAMPIL"].map((s) => m.STATUS_TUNTAS_LIVE.has(s) || m.STATUS_BERHENTI_SEGERA.has(s)),
  [false, false]);
r = m.rencanakan(TK, [b(1, "CAPI", PPL, LAIN), b(2, "CAPI", PPL, LAIN)]);
check("kode: hasil berisi subsls lain -> PENCARIAN_TIDAK_MENYARING (berhenti)",
  [r.status, m.STATUS_BERHENTI_SEGERA.has(r.status)], ["PENCARIAN_TIDAK_MENYARING", true]);
check("kode: kode sendiri tampil + subsls lain -> tetap kode itu saja",
  m.rencanakan(TK, [b(4), b(1, "CAPI", PPL, LAIN)]).pilih.map((x) => x.kode), [`${S} - UMK - 4`]);
r = m.rencanakan(TK, [b(4), b(4)]);
check("kode: tampil 2x -> KODE_GANDA (berhenti)", [r.status, m.STATUS_BERHENTI_SEGERA.has(r.status)], ["KODE_GANDA", true]);
check("kode: cakupan 'semua' diabaikan", m.rencanakan(TK, [b(4), b(41)], "semua").pilih.length, 1);
check("kode: mode aneh pada kode ini", m.rencanakan(TK, [b(4, "CAWI")]).status, "MODE_TIDAK_DIKENAL");
check("kode: mode aneh pada kode LAIN tidak menghalangi", m.rencanakan(TK, [b(41, "CAWI"), b(4)]).status, "PERLU_DIUBAH");
check("kunci: target sheet = idsubsls", m.kunciTarget(T), S);
check("kunci: target kode = kode identitas", m.kunciTarget(TK), `${S} - UMK - 4`);
check("cocokTarget kode: '- 41' bukan '- 4'", [b(4), b(41)].map(m.cocokTarget(TK)), [true, false]);
check("cocokTarget sheet: semua baris subsls", [b(4), b(41), b(1, "CAPI", PPL, LAIN)].map(m.cocokTarget(T)),
  [true, true, false]);

// --- menu & dialog ---
check("angka item menu (spasi)", m.angkaItemMenu("Ganti Mode (Ke PAPI) (3)"), 3);
check("angka item menu (rapat + baris baru)", m.angkaItemMenu("Ganti Mode (Ke PAPI)\n(0)"), 0);
check("angka item menu tidak ada", m.angkaItemMenu("Ganti Mode (Ke PAPI)"), null);
check("tombol konfirmasi tunggal", m.pilihTombolKonfirmasi(["Batal", "Ya, Ganti Mode"]), 1);
check("tombol 'Tidak' bukan konfirmasi", m.pilihTombolKonfirmasi(["Tidak", "Ya"]), 1);
check("tanpa tombol konfirmasi", m.pilihTombolKonfirmasi(["Batal", "Tutup"]), null);
check("dua kandidat -> ambigu", m.pilihTombolKonfirmasi(["Ya", "Simpan"]), null);

// --- verifikasi tertunda & rate limit (run user 2026-09-15: Mode baru terbaca belakangan,
//     cek beruntun memicu HTTP 429). Kasus kembar dgn tests/test_ubah_moda.py. ---
check("jadwal cek ulang", [0, 1, 4, 5, 40].map(m.jedaCekVerifikasi), [30000, 45000, 120000, 180000, 180000]);
check("verifikasi: semua PAPI (huruf kecil juga)", m.putuskanVerifikasi({ a: "PAPI", b: "papi" }, 1000, 60000), "TERVERIFIKASI");
check("verifikasi: PAPI setelah batas tetap terverifikasi", m.putuskanVerifikasi({ a: "PAPI" }, 999999, 60000), "TERVERIFIKASI");
check("verifikasi: masih CAPI sebelum batas -> menunggu", m.putuskanVerifikasi({ a: "CAPI" }, 59999, 60000), "MENUNGGU");
check("verifikasi: masih CAPI saat batas habis", m.putuskanVerifikasi({ a: "CAPI" }, 60000, 60000), "BELUM_TERVERIFIKASI");
check("verifikasi: sebagian PAPI -> menunggu", m.putuskanVerifikasi({ a: "PAPI", b: "CAPI" }, 1000, 60000), "MENUNGGU");
check("verifikasi: kode tidak tampil -> menunggu", m.putuskanVerifikasi({ a: "(hilang)" }, 1000, 60000), "MENUNGGU");
check("verifikasi: tanpa kode tidak pernah terverifikasi",
  [m.putuskanVerifikasi({}, 1000, 60000), m.putuskanVerifikasi({}, 60000, 60000)], ["MENUNGGU", "BELUM_TERVERIFIKASI"]);
check("verifikasi: waktu klik tak diketahui (Infinity) & masih CAPI", m.putuskanVerifikasi({ a: "CAPI" }, Infinity, 60000),
  "BELUM_TERVERIFIKASI");
check("429: 15 dtk x 2^ke, maks 2 mnt", [0, 1, 2, 3, 6].map((ke) => m.jedaRateLimit(ke)), [15000, 30000, 60000, 120000, 120000]);
check("429: Retry-After dihormati (5 dtk - 5 mnt)", ["20", "1", "999", "", "abc"].map((ra) => m.jedaRateLimit(0, ra)),
  [20000, 5000, 300000, 15000, 15000]);
check("RATE_LIMIT & DIUBAH_BELUM_TERVERIFIKASI menghentikan batch",
  ["RATE_LIMIT", "DIUBAH_BELUM_TERVERIFIKASI"].map((s) => m.STATUS_BERHENTI_SEGERA.has(s)), [true, true]);
check("DIUBAH_MENUNGGU: tidak tuntas & tidak menghentikan",
  [m.STATUS_TUNTAS_LIVE.has("DIUBAH_MENUNGGU"), m.STATUS_BERHENTI_SEGERA.has("DIUBAH_MENUNGGU")], [false, false]);
// Khusus Console (hasil tersimpan di localStorage): kode yang sudah diklik tidak diklik ulang di run berikut.
const K1 = `${S} - UMK - 4`;
const K2 = `${S} - UMK - 7`;
const WK = "2026-09-15T01:00:30.000Z";
check("sudah diklik: DIUBAH_MENUNGGU -> kodenya",
  m.kodeSudahDiklik({ status: "DIUBAH_MENUNGGU", dipilih: `${K1} | ${K2}`, waktu_klik: WK }), [K1, K2]);
check("sudah diklik: hasil lama DIUBAH_BELUM_TERVERIFIKASI tanpa waktu_klik",
  m.kodeSudahDiklik({ status: "DIUBAH_BELUM_TERVERIFIKASI", dipilih: K1 }), [K1]);
check("sudah diklik: gagal SETELAH klik (waktu_klik ada) tetap dianggap diklik",
  m.kodeSudahDiklik({ status: "CENTANG_GAGAL", dipilih: K1, waktu_klik: WK }), [K1]);
check("sudah diklik: gagal SEBELUM klik -> diproses biasa", m.kodeSudahDiklik({ status: "TABEL_BERUBAH", dipilih: K1 }), []);
check("sudah diklik: terverifikasi -> tidak", m.kodeSudahDiklik({ status: "DIUBAH_TERVERIFIKASI", dipilih: K1, waktu_klik: WK }), []);
check("sudah diklik: dry-run / belum pernah", [m.kodeSudahDiklik({ status: "DRY_RUN_AKAN_DIUBAH", dipilih: K1 }),
  m.kodeSudahDiklik(undefined)], [[], []]);
check("waktu klik: waktu_klik, cadangan waktu mulai proses",
  [m.waktuKlikDari({ waktu: "2026-09-15T01:00:00.000Z", waktu_klik: WK }), m.waktuKlikDari({ waktu: "2026-09-15T01:00:00.000Z" })],
  [Date.parse(WK), Date.parse("2026-09-15T01:00:00.000Z")]);

// --- arah balik PAPI -> CAPI utk subsls tertentu (permintaan user 2026-09-22). Kembar dgn test_ubah_moda.py ---
const TC = { idsubsls: S, ke: "CAPI", ppl: [], baris: [1] };
check("arah: target tanpa ke = PAPI", [m.keTarget(T), m.keTarget(TC), m.keTarget({ ke: "capi" })], ["PAPI", "CAPI", "CAPI"]);
check("kunci: arah CAPI berawalan, PAPI tetap", [m.kunciTarget(TC), m.kunciTarget({ ...TK, ke: "CAPI" }), m.kunciTarget(T)],
  [`CAPI:${S}`, `CAPI:${S} - UMK - 4`, S]);
check("pola item menu per arah", [m.polaItemGantiMode("CAPI").test("Ganti Mode (Ke CAPI) (3)"),
  m.polaItemGantiMode("CAPI").test("Ganti Mode (Ke PAPI) (3)"), m.polaItemGantiMode("PAPI").test("Ganti Mode ( Ke PAPI )")],
[true, false, true]);
const ds = m.targetDariDaftarSubsls([
  "idsubsls\tnama SLS",                      // judul: diabaikan
  `${S}\tBANJAR A`,
  `${LAIN}, 5108070013000902;5108070013000903`, // beberapa per baris
  `${S}`,                                     // ganda
  `${S} - UMK - 4`,                           // kode identitas -> TIDAK dimuat
  "5.10807E+15\t510807001300090",             // notasi ilmiah & 15 digit -> dilaporkan
  "3 orang",                                  // angka pendek: diabaikan
], "CAPI");
check("daftar subsls: dimuat berurutan, ber-arah", ds.targets.map((t) => [t.idsubsls, t.ke, t.baris]),
  [[S, "CAPI", [2]], [LAIN, "CAPI", [3]], ["5108070013000902", "CAPI", [3]], ["5108070013000903", "CAPI", [3]]]);
check("daftar subsls: ganda / kode identitas / tidak dikenali", [ds.ganda, ds.kodeIdentitas.map((x) => x[0]), ds.tidakDikenali],
  [[[4, S]], [5], [[6, "5.10807E+15"], [6, "510807001300090"]]]);
r = m.rencanakan(TC, [b(1, "PAPI"), b(2), b(3, "PAPI", "x@gmail.com"), b(4, "PAPI", PPL, LAIN)]);
check("CAPI subsls: SEMUA PAPI subsls ini (petugas siapa pun), subsls lain diabaikan",
  [r.status, r.pilih.map((x) => x.kode)], ["PERLU_DIUBAH", [`${S} - UMK - 1`, `${S} - UMK - 3`]]);
check("CAPI subsls: cakupan diabaikan", m.rencanakan(TC, [b(1, "PAPI"), b(2, "PAPI")], "satu").pilih.length, 2);
check("CAPI subsls: semua sudah CAPI -> TIDAK_ADA_PAPI (tuntas)",
  [m.rencanakan(TC, [b(1), b(2)]).status, m.STATUS_TUNTAS_LIVE.has("TIDAK_ADA_PAPI")], ["TIDAK_ADA_PAPI", true]);
r = m.rencanakan(TC, [b(1), b(2)], "satu", true);
check("CAPI subsls: >1 halaman tanpa PAPI tampil -> CEK_HALAMAN_LAIN (lanjut, tidak tuntas)",
  [r.status, m.STATUS_TUNTAS_LIVE.has(r.status), m.STATUS_BERHENTI_SEGERA.has(r.status)], ["CEK_HALAMAN_LAIN", false, false]);
check("CAPI subsls: >1 halaman & PAPI tampil -> tetap diubah", m.rencanakan(TC, [b(1, "PAPI")], "satu", true).status,
  "PERLU_DIUBAH");
check("CAPI subsls: hanya subsls lain -> SUBSLS_TIDAK_TAMPIL (berhenti)", m.rencanakan(TC, [b(1, "PAPI", PPL, LAIN)]).status,
  "SUBSLS_TIDAK_TAMPIL");
check("CAPI subsls: kosong -> TIDAK_ADA_ASSIGNMENT", m.rencanakan(TC, []).status, "TIDAK_ADA_ASSIGNMENT");
check("CAPI subsls: mode aneh", m.rencanakan(TC, [b(1, "CAWI")]).status, "MODE_TIDAK_DIKENAL");
const TKC = { ...TK, ke: "CAPI" };
r = m.rencanakan(TKC, [b(41, "PAPI"), b(4, "PAPI")]);
check("CAPI kode: PAPI persis -> diubah", [r.status, r.pilih.map((x) => x.kode)], ["PERLU_DIUBAH", [`${S} - UMK - 4`]]);
check("CAPI kode: sudah CAPI -> KODE_SUDAH_CAPI (tuntas)",
  [m.rencanakan(TKC, [b(4)]).status, m.STATUS_TUNTAS_LIVE.has("KODE_SUDAH_CAPI")], ["KODE_SUDAH_CAPI", true]);
check("diulang per subsls: CAPI subsls & cakupan semua saja",
  [m.diulangPerSubsls(TC, "satu"), m.diulangPerSubsls(T, "satu"), m.diulangPerSubsls(T, "semua"), m.diulangPerSubsls(TKC, "semua")],
  [true, false, true, false]);
check("verifikasi arah CAPI", [m.putuskanVerifikasi({ a: "CAPI" }, 1000, 60000, "CAPI"),
  m.putuskanVerifikasi({ a: "PAPI" }, 1000, 60000, "CAPI"), m.putuskanVerifikasi({ a: "CAPI" }, 1000, 60000)],
["TERVERIFIKASI", "MENUNGGU", "MENUNGGU"]);
check("dialog sesuai arah", [
  m.dialogSesuai("Apakah Anda yakin mengubah mode 3 assignment ke CAPI?", "CAPI"),
  m.dialogSesuai("Ubah mode ke PAPI?", "CAPI"),
  m.dialogSesuai("Ganti Mode (Ke PAPI)", "PAPI"),
  m.dialogSesuai("Ubah mode dari PAPI menjadi CAPI?", "CAPI"),
  m.dialogSesuai("Apakah Anda yakin mengganti mode assignment?", "CAPI"),
  m.dialogSesuai("Assignment PAPI akan diubah", "CAPI"),
  m.dialogSesuai("Hapus assignment?", "CAPI"),
], [true, false, true, true, true, false, false]);
// Menu ⋮ per baris (dilihat 2026-09-22): "Ganti Mode" dicocokkan persis, satu menu dgn "Hapus Assignment"
const MENU_BARIS = ["Assign Petugas", "Clear Petugas", "Pengaturan Email", "Broadcast Email", "Broadcast Receipt (BPE)",
  "Riwayat Broadcast", "Pengaturan Pesan", "Broadcast Pesan", "Ganti Mode", "Ganti Sampel", "Ganti Wilayah",
  "Reset Versi Data", "Panel Logs", "Hapus Assignment"];
check("menu ⋮: item Ganti Mode", [m.pilihItemGantiModeBaris(MENU_BARIS, "CAPI"), MENU_BARIS[m.pilihItemGantiModeBaris(MENU_BARIS, "CAPI")]],
  [8, "Ganti Mode"]);
check("menu ⋮: tanpa Ganti Mode / ganda / arah lawan", [
  m.pilihItemGantiModeBaris(MENU_BARIS.filter((x) => x !== "Ganti Mode"), "CAPI"),
  m.pilihItemGantiModeBaris(["Ganti Mode", "Ganti Mode (Ke CAPI)"], "CAPI"),
  m.pilihItemGantiModeBaris(["Ganti Mode (Ke PAPI)", "Hapus Assignment"], "CAPI"),
  m.pilihItemGantiModeBaris(["Ganti Mode (Ke CAPI) (1)"], "CAPI"),
  m.pilihItemGantiModeBaris(["Ganti Sampel", "Ganti Wilayah"], "CAPI"),
], [null, null, null, 0, null]);
check("opsi mode dialog (CAPI/CAWI/PAPI)", [m.pilihOpsiMode(["CAPI", "CAWI", "PAPI"], "CAPI"), m.pilihOpsiMode(["CAPI", "CAWI", "PAPI"], "PAPI"),
  m.pilihOpsiMode(["", "Pilih mode yang tersedia"], "CAPI"), m.pilihOpsiMode(["CAPI", "CAPI"], "CAPI"),
  m.pilihOpsiMode(["Ke CAPI"], "CAPI"), m.pilihOpsiMode(["CAPI ke PAPI"], "CAPI"), m.pilihOpsiMode(["CAWI"], "CAPI")],
[0, 2, null, null, 0, null, null]);
const WK2 = "2026-09-22T02:00:00.000Z";
const tersimpan = {
  [K1]: { status: "DIUBAH_MENUNGGU", dipilih: K1, waktu_klik: WK }, // arah PAPI (tanpa ke)
  [`CAPI:${S}`]: { status: "DIUBAH_MENUNGGU", ke: "CAPI", idsubsls: S, dipilih: `${K2}`, waktu_klik: WK2 },
  [`CAPI:${LAIN}`]: { status: "DIUBAH_TERVERIFIKASI", ke: "CAPI", jalan: "otomatis", idsubsls: LAIN, dipilih: "x", waktu_klik: WK2 },
};
check("kode sudah diklik per arah (lintas kunci)", [m.kodeDiklikSemua(tersimpan, "CAPI"), m.kodeDiklikSemua(tersimpan, "PAPI")],
  [[K2], [K1]]);
check("bukti per arah", [m.adaBukti(tersimpan, "CAPI"), m.adaBukti(tersimpan, "PAPI")], [true, false]);
// masihTuntas: SUDAH_ADA_PAPI jadi tidak tuntas kalau SESUDAHNYA ada klik ke CAPI di subsls yang sama
const lamaPapi = { status: "SUDAH_ADA_PAPI", jalan: "otomatis", idsubsls: S, waktu: "2026-09-22T01:00:00.000Z" };
const TUNTAS = m.STATUS_TUNTAS_LIVE;
check("masih tuntas: tanpa klik arah lawan", m.masihTuntas(lamaPapi, T, { [S]: lamaPapi }, TUNTAS), true);
check("masih tuntas: klik ke CAPI sesudahnya -> diperiksa lagi",
  m.masihTuntas(lamaPapi, T, { [S]: lamaPapi, [`CAPI:${S}`]: { ke: "CAPI", idsubsls: S, status: "TIDAK_ADA_PAPI", klik_terakhir: WK2 } }, TUNTAS),
  false);
check("masih tuntas: klik ke CAPI SEBELUMNYA tidak berpengaruh",
  m.masihTuntas(lamaPapi, T, { [S]: lamaPapi, [`CAPI:${S}`]: { ke: "CAPI", idsubsls: S, waktu_klik: "2026-09-22T00:00:00.000Z" } }, TUNTAS),
  true);
check("masih tuntas: klik ke CAPI di subsls LAIN tidak berpengaruh",
  m.masihTuntas(lamaPapi, T, { [S]: lamaPapi, [`CAPI:${LAIN}`]: { ke: "CAPI", idsubsls: LAIN, waktu_klik: WK2 } }, TUNTAS), true);
check("masih tuntas: status tidak tuntas / belum ada", [m.masihTuntas({ status: "KODE_TIDAK_ADA" }, T, {}, TUNTAS),
  m.masihTuntas(undefined, T, {}, TUNTAS)], [false, false]);

// --- penanda halaman (hanya DIBACA, paginasi tidak pernah diklik) ---
check("baca halaman", m.bacaHalaman("10 row(s) Rows per page 10 Page 1 of 33"), [1, 33]);
check("baca halaman beda baris", m.bacaHalaman("Page 4\nof 4"), [4, 4]);
check("tanpa paginasi", m.bacaHalaman("Tidak ada data"), null);

console.log(okAll ? "\nSEMUA PASS" : "\nADA YANG FAIL");
process.exit(okAll ? 0 : 1);
