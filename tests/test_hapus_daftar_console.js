// Uji logika murni fasih_sm/hapus_ganda/hapus_daftar_console.js: node tests/test_hapus_daftar_console.js
const path = require("path");
const m = require(path.join(__dirname, "..", "fasih_sm", "hapus_ganda", "hapus_daftar_console.js"));

let gagal = 0;
function check(nama, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) gagal++;
  console.log(`${ok ? "PASS" : "FAIL"} | ${nama}: got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
}

const WADAH = "5108060006000224";
const TUJ = "5108020013000303";
const region = (kode) => ({ level_1: { full_code: "51", level_2: { full_code: "5108", level_3: { full_code: kode.slice(0, 7),
  level_4: { full_code: kode.slice(0, 10), level_5: { full_code: kode.slice(0, 14), level_6: { full_code: kode } } } } } } });
const det = (kode, nama) => m.ringkasDetail({ success: true, data: { region: region(kode), code_identity: `${kode} - ${nama}`,
  assignment_status_alias: "APPROVED BY Pengawas" } });

check("detail: kode subsls & nama tanpa awalan kode", det(WADAH, "Warung  Rokok (made taman)"),
  { ada: true, kode: WADAH, nama: "WARUNG ROKOK (MADE TAMAN)", alias: "APPROVED BY Pengawas" });
check("detail: bentuk lain -> null", [m.ringkasDetail({ success: false }), m.ringkasDetail({ success: true, data: {} })], [null, null]);
// live 2026-09-30: dokumen yang sudah dihapus -> {"success":true,"message":"Berhasil","data":null,"errorCode":null}
check("detail: success + data null -> tidak ada", m.ringkasDetail({ success: true, message: "Berhasil", data: null, errorCode: null }),
  { ada: false });

const e = { id: "11111111-1111-4111-8111-111111111111", nama: "WARUNG ROKOK (MADE TAMAN)", wadah: WADAH,
  kembar: "22222222-2222-4222-8222-222222222222", tujuan: TUJ };
const st = (x, dok, kem) => m.nilaiCek(x, dok, kem).status;
check("siap: di wadah, nama cocok, kembaran di tujuan", st(e, det(WADAH, e.nama), det(TUJ, e.nama)), "SIAP_HAPUS");
check("dokumen sudah tidak ada", st(e, { ada: false }, det(TUJ, e.nama)), "SUDAH_TIDAK_ADA");
check("dokumen sudah pindah dari wadah", st(e, det(TUJ, e.nama), det(TUJ, e.nama)), "PINDAH_TEMPAT");
check("nama beda", st(e, det(WADAH, "USAHA LAIN (X)"), det(TUJ, e.nama)), "NAMA_BEDA");
check("nama: salah satu dari 'A / B' cukup", st({ ...e, nama: `LAIN / ${e.nama}` }, det(WADAH, e.nama), det(TUJ, e.nama)), "SIAP_HAPUS");
check("kembaran hilang -> JANGAN hapus", st(e, det(WADAH, e.nama), { ada: false }), "KEMBARAN_TIDAK_ADA");
check("kembaran belum di tujuan -> JANGAN hapus", st(e, det(WADAH, e.nama), det(WADAH, e.nama)), "KEMBARAN_BELUM_DI_TUJUAN");
check("kembaran = dirinya", st({ ...e, kembar: e.id }, det(WADAH, e.nama), det(TUJ, e.nama)), "KEMBAR_SAMA");
check("tanpa kembaran (dokumen tak dikenal)", st({ ...e, kembar: "", tujuan: "" }, det(WADAH, e.nama), null), "SIAP_HAPUS");
check("id tidak sah", st({ ...e, id: "x" }, det(WADAH, e.nama), det(TUJ, e.nama)), "ID_TIDAK_SAH");

console.log(gagal ? `\n${gagal} GAGAL` : "\nSEMUA LULUS");
process.exit(gagal ? 1 : 0);
