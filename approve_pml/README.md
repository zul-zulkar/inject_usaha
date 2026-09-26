# approve_pml — approve dokumen oleh akun PML (fasih-web)

Sebagai **PML**, meng-approve dokumen yang sudah dikirim PPL — biasanya hasil `input_usaha`. Sama
dengan klik **Approve** di bar bawah dokumen → **Approve** di dialog "Konfirmasi Approve".
Playwright, login otomatis dengan `FIXED_PASSWORD`. Butuh VPN.

Per dokumen: status dibaca lewat API (harus `SUBMITTED BY Pencacah` & dibuat akun PPL yang diminta)
→ dokumen dibuka → Approve → **status server dibaca ulang sampai `APPROVED BY Pengawas`** (toast
bukan bukti). Ada yang janggal → seluruh run berhenti. ⚠️ Anggap approve tidak bisa dibatalkan.

## Pakai — dokumen satu PPL dari audit input (alur utama)

```bash
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL --cek              # rencana, tanpa browser
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL                    # dry-run (tidak ada yang diklik)
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL --eksekusi --limit 1
python approve_pml/approve_pml.py --akun-pml EMAIL_PML --akun-ppl EMAIL_PPL --eksekusi
```

Hanya sumber ini yang hasilnya bisa dipakai `fasih_sm/pindah_wilayah --dari-approve`. Batch dengan
audit sendiri: tambah `--audit audit/<batch>`.

**Banyak PML sekaligus:** `--rencana <csv/xlsx berkolom Email PML, Email PPL, assignment_id>`
(contoh: [`templates/rencana_approve.contoh.csv`](../templates/rencana_approve.contoh.csv)) atau
`--daftar <salinan tabel Data fasih-sm>` (dicari lewat kode identitas). Urutannya sama: `--cek` →
dry-run → `--eksekusi --limit 1` (per PML) → `--eksekusi`.

## Opsi

| Opsi | Guna |
| --- | --- |
| `--eksekusi` / `--ya` | sungguhan klik Approve (minta `YA`) / lewati pertanyaan `YA` |
| `--limit N` | maks dokumen per PML (yang dilewati tidak dihitung) |
| `--termasuk-di-luar-audit` | ikut dokumen list subsls PPL yang tidak tercatat di audit |
| `--abaikan-audit-approve` | cek ulang dokumen yang di audit approve sudah APPROVED |
| `--login-manual` | tunggu manusia login di jendela browser |
| `--audit` | audit input batch lain |

## Status

| Status | Arti / tindakan |
| --- | --- |
| `DRY_RUN_SIAP_APPROVE` | siap; boleh `--eksekusi` |
| `APPROVED_TERVERIFIKASI` / `SUDAH_APPROVED` | selesai |
| `SKIP_STATUS_…` | belum terkirim / di-reject — kirim dulu dari PPL |
| `SKIP_BUKAN_PPL` | dokumen milik PPL lain — tidak disentuh |
| `SKIP_TIDAK_ADA_AKSES` | server menolak (biasanya dokumen **CAPI**) — approve lewat aplikasi FASIH |
| `ERROR_FORM_TIDAK_MOUNT` / `ERROR_LOGIN_PML` | 504 / login gagal — jalankan lagi / cek password |
| ⛔ `STOP_DIALOG_TIDAK_MUNCUL`, `STOP_TOMBOL_AMBIGU`, `APPROVE_TIDAK_TERVERIFIKASI` | run berhenti — cek dokumen itu manual |

## Berkas

| Berkas | Isi |
| --- | --- |
| `audit/audit_approve_pml.csv` | catatan approve (ditambah tiap run; dibaca `pindah_wilayah --dari-approve`) |
| `approve_pml/hasil/` | screenshot kegagalan, sesi login `.sesi_fasih_web_<akun>.json` (berisi cookie) |
| `approve_pml.py` | seluruh alur: target dari audit/rencana/daftar, login per PML, `approve_satu` + verifikasi API |
| [`../inti/fasih_web.py`](../inti/fasih_web.py) | login SSO, verifikasi akun aktif |

Uji: `python tests/test_approve_pml.py`.
