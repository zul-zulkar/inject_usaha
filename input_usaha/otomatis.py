#!/usr/bin/env python3
"""
otomatis.py — jalankan input usaha (jalankan.py) sampai TUNTAS tanpa ditunggui
(dulu input_tahap2/jalankan_otomatis.py).

Yang ditangani otomatis:
  * Ketik 'YA' saat prompt konfirmasi kirim (sekali di awal tiap proses).
  * Proses berhenti/crash (gagal buat dokumen, VPN putus, error tak terduga) -> tunggu
    sebentar lalu jalankan ULANG dgn akun & rentang yang SAMA (--lewati-selesai membuat
    baris yang sudah selesai tidak diulang).
  * Kena limit permintaan ("too many request") -> PINDAH ke akun & subsls cadangan (kalau
    diberikan), lanjut rentang yang sama. Cadangan juga kena -> berhenti & lapor.
  * Tuntas (tidak ada sisa, tidak "BERHENTI di tengah") -> berhenti sendiri, lalu menyalin
    audit jadi audit_log_gabungan<LABEL>.csv supaya mudah dibedakan saat digabung.

CONTOH (PC pertama, baris 2-500, akun utama + cadangan):

    python input_usaha/otomatis.py --sumber bahan/input_usaha.xlsx --dari 2 --sampai 500 ^
        --akun ppl.contoh@mail.com --subsls 5108010010000105 ^
        --akun-cadangan ppl.kedua@mail.com --subsls-cadangan 5108010010000106 --label-pc _pc1

PC lain: rentang baris & --label-pc BEDA, akun BEDA. ⚠️ Satu akun hanya boleh dipakai satu
PC pada satu waktu — audit antar-PC tidak saling tahu, dokumen bisa terkirim GANDA.

Kalau wrapper ini sendiri berhenti (mis. PC restart), jalankan lagi perintah yang SAMA — status
di input_usaha/hasil/.status_otomatis<LABEL>.json melanjutkan dari akun yang terakhir dipakai.
Log lengkap: input_usaha/hasil/log_otomatis<LABEL>.txt.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Konsol Windows sering pakai cp1252 sbg default, sedangkan output bot (emoji,
# tanda "—" dsb) ada karakter yg tidak dikenal cp1252 -> UnicodeDecodeError/
# EncodeError bikin WRAPPER ini crash (bot aslinya baik-baik saja). Paksa
# stdout/stderr wrapper sendiri jadi UTF-8 dgn karakter tak dikenal diganti
# tanda '?' drpd bikin crash.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent  # akar proyek
sys.path.insert(0, str(ROOT))
from inti import lokasi  # noqa: E402

# Pola pesan yang menandakan "kena limit permintaan" — server/API menolak
# karena terlalu banyak request dalam waktu singkat. Silakan tambah pola lain
# di sini kalau ternyata ada teks lain yang muncul di lapangan.
# ⚠️ JANGAN pakai "429" polos: ID survei di SETIAP URL dokumen (a0429e96-…) memuatnya,
# sehingga (2026-09-25) semua run terbaca "kena limit" & pindah ke akun cadangan / berhenti.
# 429 hanya dihitung kalau didahului konteks HTTP/status/kode atau diikuti "Too Many".
POLA_RATE_LIMIT = re.compile(
    r"(too many requests?|terlalu banyak (?:permintaan|request)|rate[ _-]?limit|kuota\s*habis|"
    r"(?:request|limit)s?[ _]exceeded|melebihi\s*batas\s*permintaan|"
    r"\b(?:http|status|kode|code)\W{0,3}429\b|\b429\s+too many)",
    re.IGNORECASE,
)

# Baris penanda batch benar-benar tuntas (dicetak oleh mesin.py di akhir run).
POLA_SELESAI = re.compile(r"Selesai\. Audit:")
POLA_BERHENTI_TENGAH = re.compile(r"Run BERHENTI di tengah")
POLA_RINGKASAN = re.compile(
    r"Ringkasan run:\s*(\d+)\s*baris diproses,\s*(\d+)\s*dilewati,\s*(\d+)\s*belum sempat dikerjakan"
)


def file_status(label: str) -> Path:
    return lokasi.HASIL_INPUT / f".status_otomatis{label}.json"


def baca_status(label: str) -> dict:
    p = file_status(label)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def tulis_status(label: str, data: dict) -> None:
    lokasi.siapkan(file_status(label)).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def jalankan_sekali(sumber, audit_dir, dari, sampai, akun, subsls, log_path: Path) -> tuple[int, str]:
    """Jalankan jalankan.py sekali, kirim 'YA' otomatis, kembalikan (returncode, seluruh_output)."""
    cmd = [
        sys.executable, str(ROOT / "input_usaha" / "jalankan.py"),
        "--sumber", sumber,
        *(["--audit", audit_dir] if audit_dir else []),
        "--akun-tunggal", akun,
        "--subsls-tunggal", subsls,
        "--sinkron-dulu",
        "--lewati-selesai",
        "--izinkan-wilayah-beda",
        "--submit",
        "--dari", str(dari),
        "--sampai", str(sampai),
    ]
    print(f"\n{'='*70}\n>>> Menjalankan: {' '.join(cmd)}\n{'='*70}")

    import os
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    # Kirim konfirmasi 'YA' segera lalu tutup stdin (cuma ada 1 prompt di awal run).
    try:
        proc.stdin.write("YA\n")
        proc.stdin.flush()
        proc.stdin.close()
    except Exception:
        pass

    output_lines: list[str] = []
    with open(log_path, "a", encoding="utf-8") as logf:
        logf.write(f"\n\n===== RUN {time.strftime('%Y-%m-%d %H:%M:%S')} | akun={akun} subsls={subsls} "
                    f"dari={dari} sampai={sampai} =====\n")
        for line in proc.stdout:
            print(line, end="")
            logf.write(line)
            output_lines.append(line)
    proc.wait()
    return proc.returncode, "".join(output_lines)


POLA_AKUN_DIPAKAI = re.compile(r"sedang dipakai proses (?:input|main_gabungan) lain")
POLA_STOP_MANUSIA = re.compile(r"STOP_WILAYAH_DOKUMEN_BEDA|STOP_SUBSLS_TIDAK_BISA_DIPILIH")


# Rate limit hanya dicari di EKOR output: yang menghentikan run tercetak di akhir.
# Teks yang cocok di tengah run yang lalu jalan terus (mis. nama usaha, pesan server
# sesaat) bukan alasan pindah akun.
BARIS_EKOR_RATE_LIMIT = 60


def evaluasi_hasil(output: str) -> dict:
    tuntas = bool(POLA_SELESAI.search(output)) and not POLA_BERHENTI_TENGAH.search(output)
    sisa = None
    m = POLA_RINGKASAN.search(output)
    if m:
        sisa = int(m.group(3))
        if sisa and sisa > 0:
            tuntas = False
    ekor = output.splitlines()[-BARIS_EKOR_RATE_LIMIT:]
    bukti = next((b.strip() for b in ekor if POLA_RATE_LIMIT.search(b)), "")
    return {"tuntas": tuntas, "sisa": sisa, "rate_limited": bool(bukti), "bukti_rate_limit": bukti,
            "akun_dipakai": bool(POLA_AKUN_DIPAKAI.search(output)),
            "stop_manusia": bool(POLA_STOP_MANUSIA.search(output))}


def status_berlaku(status: dict, argumen: dict) -> tuple[dict, str]:
    """Status tersimpan dipakai HANYA kalau dibuat oleh perintah yang SAMA (akun, subsls,
    cadangan, rentang, sumber). -> (status yang dipakai, alasan kalau diabaikan).

    2026-09-25: pola rate limit lama menganggap "429" di ID survei (a0429e96-…) sbg limit ->
    wrapper pindah ke akun & subsls CADANGAN dan menyimpannya di status. Status itu lalu
    menimpa --akun/--subsls di SETIAP run berikutnya, termasuk perintah dgn akun lain ->
    "mencari subsls yang salah". Status format lama (tanpa `argumen`) = dari masa itu -> diabaikan."""
    if not status:
        return {}, ""
    if status.get("argumen") != argumen:
        lama = status.get("argumen")
        sebab = ("format lama (dari wrapper sebelum perbaikan deteksi limit)" if lama is None
                 else f"dibuat perintah lain {lama}")
        return {}, (f"status tersimpan diabaikan — {sebab}; tadinya akun aktif "
                    f"{status.get('akun_aktif')} / {status.get('subsls_aktif')}")
    pasangan = {(argumen["akun"], argumen["subsls"]),
                (argumen["akun_cadangan"], argumen["subsls_cadangan"])}
    if (status.get("akun_aktif"), status.get("subsls_aktif")) not in pasangan:
        return {}, (f"status tersimpan diabaikan — akun/subsls {status.get('akun_aktif')} / "
                    f"{status.get('subsls_aktif')} bukan pasangan utama maupun cadangan")
    return status, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", required=True)
    ap.add_argument("--audit", default="", help="berkas/folder audit (bawaan audit/audit_log_gabungan.csv)")
    ap.add_argument("--dari", type=int, required=True)
    ap.add_argument("--sampai", type=int, required=True)
    ap.add_argument("--akun", required=True, help="Akun utama (email PPL)")
    ap.add_argument("--subsls", required=True, help="Subsls 16 digit utk akun utama")
    ap.add_argument("--akun-cadangan", default=None, help="Akun dipakai kalau akun utama kena limit")
    ap.add_argument("--subsls-cadangan", default=None)
    ap.add_argument("--label-pc", default="_pst",
                     help="Akhiran nama file audit_log_gabungan salinan akhir, mis. _pst, _pc2, dst. "
                          "Dipakai supaya log dari PC berbeda tidak tertukar saat digabung.")
    ap.add_argument("--jeda-retry", type=int, default=30,
                     help="Detik tunggu sebelum mencoba lagi setelah error biasa (bukan rate limit).")
    ap.add_argument("--jeda-retry-maks", type=int, default=300,
                     help="Batas atas jeda retry (detik) — jeda naik bertahap tiap gagal berturut-turut.")
    args = ap.parse_args()
    lokasi.cek_struktur_lama()
    if bool(args.akun_cadangan) != bool(args.subsls_cadangan):
        ap.error("--akun-cadangan & --subsls-cadangan harus diisi BERSAMA (atau keduanya dikosongkan).")

    argumen = {"akun": args.akun, "subsls": args.subsls, "akun_cadangan": args.akun_cadangan,
               "subsls_cadangan": args.subsls_cadangan, "dari": args.dari, "sampai": args.sampai,
               "sumber": args.sumber}
    status, alasan = status_berlaku(baca_status(args.label_pc), argumen)
    if alasan:
        print(f"ℹ️ {alasan}. Mulai lagi dari akun utama {args.akun} / {args.subsls}.")
        file_status(args.label_pc).unlink(missing_ok=True)
    akun_aktif = status.get("akun_aktif", args.akun)
    subsls_aktif = status.get("subsls_aktif", args.subsls)
    pakai_cadangan = status.get("pakai_cadangan", False)
    percobaan_gagal_beruntun = 0

    log_path = lokasi.siapkan(lokasi.HASIL_INPUT / f"log_otomatis{args.label_pc}.txt")
    print(f"Log lengkap ditulis ke: {log_path}")
    if pakai_cadangan:
        print(f"(melanjutkan dari status sebelumnya: sudah memakai akun cadangan {akun_aktif})")

    while True:
        rc, output = jalankan_sekali(args.sumber, args.audit, args.dari, args.sampai,
                                      akun_aktif, subsls_aktif, log_path)
        hasil = evaluasi_hasil(output)
        print(f"\n--- Ringkasan percobaan: returncode={rc} tuntas={hasil['tuntas']} "
              f"sisa={hasil['sisa']} rate_limited={hasil['rate_limited']} ---")

        if hasil["tuntas"]:
            print("\n✅ Batch TUNTAS untuk rentang ini.")
            file_status(args.label_pc).unlink(missing_ok=True)
            asal = lokasi.jalur_audit(args.audit)
            if not asal.is_absolute():
                asal = ROOT / asal
            if asal.exists():
                tujuan = asal.with_name(f"audit_log_gabungan{args.label_pc}.csv")
                shutil.copy2(asal, tujuan)
                print(f"Salinan audit dibuat: {tujuan}")
            else:
                print(f"⚠️ Tidak menemukan audit {asal} — "
                      "salin manual kalau perlu.")
            return 0

        if hasil["akun_dipakai"]:
            print(f"\n⛔ Akun {akun_aktif} sedang dipakai proses bot lain di PC ini. Menjalankan dua "
                  "proses dgn akun sama = dokumen GANDA. Tutup proses itu dulu, lalu jalankan ulang wrapper.")
            return 2

        if hasil["stop_manusia"]:
            print("\n⛔ Bot berhenti karena STOP_WILAYAH_DOKUMEN_BEDA / STOP_SUBSLS_TIDAK_BISA_DIPILIH. "
                  "Ini bukan gangguan sesaat — kalau diulang otomatis hasilnya sama. Periksa baris yang "
                  "disebut di atas (dokumen yang wilayahnya salah biasanya perlu dihapus admin), lalu "
                  "jalankan ulang wrapper.")
            return 4

        if hasil["rate_limited"]:
            print(f"\nTeks yang dianggap limit permintaan: {hasil['bukti_rate_limit'][:200]!r}")
            if not pakai_cadangan and args.akun_cadangan and args.subsls_cadangan:
                print(f"\n⚠️ Terdeteksi kena limit permintaan pada akun {akun_aktif}. "
                      f"Pindah ke akun cadangan: {args.akun_cadangan} / {args.subsls_cadangan}")
                akun_aktif, subsls_aktif = args.akun_cadangan, args.subsls_cadangan
                pakai_cadangan = True
                percobaan_gagal_beruntun = 0
                tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                              "pakai_cadangan": pakai_cadangan, "argumen": argumen})
                time.sleep(5)
                continue
            else:
                print(f"\n⛔ Kena limit permintaan pada akun {akun_aktif}"
                      + (" (akun CADANGAN juga sudah kena)." if pakai_cadangan else
                         " dan tidak ada akun cadangan yang diberikan.") +
                      "\n   Berhenti — tunggu limitnya reset (biasanya beberapa jam) lalu jalankan ulang "
                      "command yang sama, atau berikan akun lain lewat --akun-cadangan/--subsls-cadangan.")
                tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                              "pakai_cadangan": pakai_cadangan, "argumen": argumen})
                return 3

        # Error biasa (gagal buat dokumen baru, VPN putus, crash, dll) -> retry akun yang sama.
        percobaan_gagal_beruntun += 1
        jeda = min(args.jeda_retry * percobaan_gagal_beruntun, args.jeda_retry_maks)
        print(f"\n↻ Proses berhenti/gagal (percobaan gagal ke-{percobaan_gagal_beruntun} berturut-turut "
              f"pada akun ini). Kemungkinan penyebab: gagal buat dokumen baru / VPN terputus / error "
              f"server sesaat. Tunggu {jeda} detik lalu coba lagi dgn akun & rentang yang sama.\n"
              f"  (Kalau ini terus berulang tanpa progres, cek VPN kantor & koneksi internet PC ini.)")
        tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                      "pakai_cadangan": pakai_cadangan, "argumen": argumen})
        time.sleep(jeda)


if __name__ == "__main__":
    sys.exit(main())
