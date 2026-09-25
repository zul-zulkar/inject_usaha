#!/usr/bin/env python3
"""
jalankan_otomatis.py — pembungkus main_tahap2.py yang menjalankan batch
input Tahap 2 sampai TUNTAS tanpa perlu diketik ulang manual.

Yang ditangani otomatis:
  * Ketik 'YA' saat prompt konfirmasi submit (dikirim ke stdin sekali di awal
    tiap kali proses dijalankan).
  * Proses berhenti/crash karena error apa pun (gagal buat dokumen, VPN
    putus, exception tak terduga, dsb) -> tunggu sebentar lalu jalankan ULANG
    dengan akun & rentang baris yang SAMA (--lewati-selesai membuat baris yang
    sudah selesai tidak diulang, jadi aman dijalankan ulang berkali-kali).
  * Proses berhenti karena kena limit permintaan (rate limit / "too many
    request") -> otomatis PINDAH ke akun & subsls cadangan (kalau diberikan),
    lalu lanjut dengan rentang baris yang SAMA.
  * Kalau akun cadangan JUGA kena limit -> berhenti & kasih tahu, tidak asal
    tebak lagi.
  * Kalau memang sudah tuntas (semua baris di rentang --dari..--sampai selesai
    diproses, tidak ada sisa, tidak "BERHENTI di tengah") -> berhenti sendiri,
    lalu menyalin audit_log_gabungan.csv jadi audit_log_gabungan<LABEL>.csv
    supaya gampang dibedakan log dari PC mana saat digabung/diupload.

CONTOH PAKAI (PC pertama, baris 11-200, akun utama + cadangan, label "_pst"):

    python input_tahap2/jalankan_otomatis.py ^
        --sumber bahan/input_tahap2_22.xlsx --audit audit/ ^
        --dari 11 --sampai 200 ^
        --akun suliyantiketut20@gmail.com --subsls 5108060006000224 ^
        --akun-cadangan windasariani1301@gmail.com --subsls-cadangan 5108060006000116 ^
        --label-pc _pst

CONTOH PAKAI DI PC LAIN (rentang baris beda supaya TIDAK tumpang tindih,
label beda supaya log tidak tertukar saat digabung):

    python input_tahap2/jalankan_otomatis.py ^
        --sumber bahan/input_tahap2_22.xlsx --audit audit/ ^
        --dari 201 --sampai 400 ^
        --akun <AKUN_LAIN> --subsls <SUBSLS_AKUN_ITU> ^
        --akun-cadangan <AKUN_CADANGAN_LAIN> --subsls-cadangan <SUBSLS_AKUN_ITU> ^
        --label-pc _pc2

⚠️ JANGAN pakai akun yang sama di dua PC pada waktu bersamaan. Kunci
anti-ganda bot hanya berlaku di satu PC; audit PC lain tidak saling tahu,
jadi dokumen bisa terkirim GANDA (kejadian nyata 2026-09-15).

Kalau proses ini sendiri berhenti (mis. PC restart), tinggal jalankan lagi
persis dengan command yang sama — dia baca file status (.status_otomatis_tahap2<LABEL>.json)
dan melanjutkan dari akun yang terakhir dipakai.
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

ROOT = Path(__file__).resolve().parent.parent  # root proyek (folder induk dari input_tahap2/)

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

# Baris penanda batch benar-benar tuntas (dicetak oleh main_gabungan.py di akhir run).
POLA_SELESAI = re.compile(r"Selesai\. Audit:")
POLA_BERHENTI_TENGAH = re.compile(r"Run BERHENTI di tengah")
POLA_RINGKASAN = re.compile(
    r"Ringkasan run:\s*(\d+)\s*baris diproses,\s*(\d+)\s*dilewati,\s*(\d+)\s*belum sempat dikerjakan"
)


def file_status(label: str) -> Path:
    return ROOT / f".status_otomatis_tahap2{label}.json"


def baca_status(label: str) -> dict:
    p = file_status(label)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def tulis_status(label: str, data: dict) -> None:
    file_status(label).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def jalankan_sekali(sumber, audit_dir, dari, sampai, akun, subsls, log_path: Path) -> tuple[int, str]:
    """Jalankan main_tahap2.py sekali, kirim 'YA' otomatis, kembalikan (returncode, seluruh_output)."""
    cmd = [
        sys.executable, str(ROOT / "input_tahap2" / "main_tahap2.py"),
        "--sumber", sumber,
        "--audit", audit_dir,
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


POLA_AKUN_DIPAKAI = re.compile(r"sedang dipakai proses main_gabungan lain")
POLA_STOP_MANUSIA = re.compile(r"STOP_WILAYAH_DOKUMEN_BEDA|STOP_SUBSLS_TIDAK_BISA_DIPILIH")


def evaluasi_hasil(output: str) -> dict:
    tuntas = bool(POLA_SELESAI.search(output)) and not POLA_BERHENTI_TENGAH.search(output)
    sisa = None
    m = POLA_RINGKASAN.search(output)
    if m:
        sisa = int(m.group(3))
        if sisa and sisa > 0:
            tuntas = False
    rate_limited = bool(POLA_RATE_LIMIT.search(output))
    return {"tuntas": tuntas, "sisa": sisa, "rate_limited": rate_limited,
            "akun_dipakai": bool(POLA_AKUN_DIPAKAI.search(output)),
            "stop_manusia": bool(POLA_STOP_MANUSIA.search(output))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", required=True)
    ap.add_argument("--audit", default="audit/")
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
    if bool(args.akun_cadangan) != bool(args.subsls_cadangan):
        ap.error("--akun-cadangan & --subsls-cadangan harus diisi BERSAMA (atau keduanya dikosongkan).")

    status = baca_status(args.label_pc)
    akun_aktif = status.get("akun_aktif", args.akun)
    subsls_aktif = status.get("subsls_aktif", args.subsls)
    pakai_cadangan = status.get("pakai_cadangan", False)
    percobaan_gagal_beruntun = 0

    log_path = ROOT / f"log_otomatis_tahap2{args.label_pc}.txt"
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
            sumber_csv = Path(args.audit) if Path(args.audit).is_absolute() else ROOT / args.audit
            asal = sumber_csv / "audit_log_gabungan.csv"
            if not asal.exists():
                asal = ROOT / "audit_log_gabungan.csv"
            if asal.exists():
                tujuan = asal.with_name(f"audit_log_gabungan{args.label_pc}.csv")
                shutil.copy2(asal, tujuan)
                print(f"Salinan audit dibuat: {tujuan}")
            else:
                print(f"⚠️ Tidak menemukan audit_log_gabungan.csv di {sumber_csv} atau {ROOT} — "
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
            if not pakai_cadangan and args.akun_cadangan and args.subsls_cadangan:
                print(f"\n⚠️ Terdeteksi kena limit permintaan pada akun {akun_aktif}. "
                      f"Pindah ke akun cadangan: {args.akun_cadangan} / {args.subsls_cadangan}")
                akun_aktif, subsls_aktif = args.akun_cadangan, args.subsls_cadangan
                pakai_cadangan = True
                percobaan_gagal_beruntun = 0
                tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                              "pakai_cadangan": pakai_cadangan})
                time.sleep(5)
                continue
            else:
                print(f"\n⛔ Kena limit permintaan pada akun {akun_aktif}"
                      + (" (akun CADANGAN juga sudah kena)." if pakai_cadangan else
                         " dan tidak ada akun cadangan yang diberikan.") +
                      "\n   Berhenti — tunggu limitnya reset (biasanya beberapa jam) lalu jalankan ulang "
                      "command yang sama, atau berikan akun lain lewat --akun-cadangan/--subsls-cadangan.")
                tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                              "pakai_cadangan": pakai_cadangan})
                return 3

        # Error biasa (gagal buat dokumen baru, VPN putus, crash, dll) -> retry akun yang sama.
        percobaan_gagal_beruntun += 1
        jeda = min(args.jeda_retry * percobaan_gagal_beruntun, args.jeda_retry_maks)
        print(f"\n↻ Proses berhenti/gagal (percobaan gagal ke-{percobaan_gagal_beruntun} berturut-turut "
              f"pada akun ini). Kemungkinan penyebab: gagal buat dokumen baru / VPN terputus / error "
              f"server sesaat. Tunggu {jeda} detik lalu coba lagi dgn akun & rentang yang sama.\n"
              f"  (Kalau ini terus berulang tanpa progres, cek VPN kantor & koneksi internet PC ini.)")
        tulis_status(args.label_pc, {"akun_aktif": akun_aktif, "subsls_aktif": subsls_aktif,
                                      "pakai_cadangan": pakai_cadangan})
        time.sleep(jeda)


if __name__ == "__main__":
    sys.exit(main())
