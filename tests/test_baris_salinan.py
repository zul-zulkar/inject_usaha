"""Uji TAHAP2_BARIS_SALINAN (inti/tahap2_loader.tandai_salinan + periksa_semua_tahap2)."""
import os
import sys
from pathlib import Path

os.environ["FASIH_ABAIKAN_CONFIG_LOKAL"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inti import tahap2_loader as tl  # noqa: E402

GAGAL = []


def cek(nama, benar):
    print(("OK   " if benar else "FAIL ") + nama)
    if not benar:
        GAGAL.append(nama)


cek("urai rentang", tl.urai_salinan("220-221:214, 1679:1676") == {220: 214, 221: 215, 1679: 1676})
for salah in ("471-589", "300:400", "10-5:2"):
    try:
        tl.urai_salinan(salah)
        cek(f"format salah ditolak: {salah}", False)
    except ValueError:
        cek(f"format salah ditolak: {salah}", True)


class R:
    """Tiruan Tahap2Row secukupnya utk tandai_salinan."""
    def __init__(self, baris, nama, produk="GAS", keg="JUAL GAS"):
        self.baris, self.nama, self.salinan_dari = baris, nama, 0
        self.v = {"produk": produk, "keg_utama": keg}

    def __getitem__(self, k):
        return self.v[k]

    def _kunci_dasar(self):
        return self.nama.upper()


rows = [R(2, "warung a"), R(3, "warung b"), R(4, "warung a"), R(5, "warung b")]
tl.tandai_salinan(rows, "4-5:2")
cek("salinan ditandai persis", [r.salinan_dari for r in rows] == [0, 0, 2, 3])
rows = [R(2, "warung a"), R(3, "warung b"), R(4, "warung b"), R(5, "warung a")]
try:
    tl.tandai_salinan(rows, "4-5:2")
    cek("nomor baris bergeser -> berhenti", False)
except ValueError:
    cek("nomor baris bergeser -> berhenti", True)
rows = [R(2, "warung a"), R(3, "warung a", produk="BERAS")]
try:
    tl.tandai_salinan(rows, "3:2")
    cek("13f beda -> bukan salinan, berhenti", False)
except ValueError:
    cek("13f beda -> bukan salinan, berhenti", True)

print(f"\n{len(GAGAL)} gagal")
sys.exit(1 if GAGAL else 0)
