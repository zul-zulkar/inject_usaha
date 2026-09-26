"""
sitecustomize.py — menerapkan PENGATURAN GUI ke inti.config di proses alat yang dijalankan GUI.

Folder ini (gui/sisip/) hanya masuk PYTHONPATH proses yang dijalankan gui/server.py, jadi
perintah terminal biasa TIDAK terpengaruh. Python mengimpor `sitecustomize` otomatis saat
start; di sini dipasang pengait impor yang, SESUDAH inti/config.py selesai dijalankan
(termasuk timpaan inti/config_lokal.py), menimpakan nilai dari berkas pengaturan GUI:

    FASIH_GUI_PENGATURAN = <berkas json>   {"timpa": {NAMA: nilai}, "tambah": {NAMA: {..}}}
    FASIH_PASSWORD       = password sesi GUI (tidak pernah ditulis ke disk oleh GUI)

"timpa" mengganti nilai; "tambah" MENGGABUNGKAN dict (kodepos/wilayah: entri GUI menang,
entri config_lokal/config.py yang lain tetap). Nilai {"__py__": "<literal>"} dibaca dgn
ast.literal_eval (tuple, set, dict berkunci tuple). Proses anak-cucu (mis. otomatis.py ->
jalankan.py) ikut karena variabel lingkungannya diwarisi.

Kode lama tidak diubah sama sekali: urutannya sama dgn config_lokal (semua modul lain
membaca `from inti.config import X` SESUDAH inti.config selesai dimuat).
"""

import os
import sys


def _nilai(v):
    if isinstance(v, dict) and set(v) == {"__py__"}:
        import ast
        return ast.literal_eval(v["__py__"])
    return v


def terapkan(modul, data: dict) -> None:
    for nama, v in (data.get("timpa") or {}).items():
        setattr(modul, nama, _nilai(v))
    for nama, v in (data.get("tambah") or {}).items():
        dasar = getattr(modul, nama, None)
        baru = dict(dasar) if isinstance(dasar, dict) else {}
        baru.update(_nilai(v) or {})
        setattr(modul, nama, baru)
    password = os.environ.get("FASIH_PASSWORD", "")
    if password:
        modul.FIXED_PASSWORD = password


def _pasang() -> None:
    path = os.environ.get("FASIH_GUI_PENGATURAN", "")
    if not path:
        return
    import importlib.abc
    import importlib.machinery
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    class _Pemuat(importlib.abc.Loader):
        def __init__(self, asli):
            self.asli = asli

        def create_module(self, spec):
            return self.asli.create_module(spec)

        def exec_module(self, modul):
            self.asli.exec_module(modul)
            terapkan(modul, data)

    class _Pencari(importlib.abc.MetaPathFinder):
        def find_spec(self, nama, jalur=None, target=None):
            if nama != "inti.config":
                return None
            spec = importlib.machinery.PathFinder.find_spec(nama, jalur)
            if spec is not None and spec.loader is not None:
                spec.loader = _Pemuat(spec.loader)
            return spec

    sys.meta_path.insert(0, _Pencari())


def _berantai() -> None:
    """Jalankan sitecustomize lain (mis. milik instalasi Python) yang tertutup berkas ini."""
    import importlib.machinery
    import importlib.util
    sini = os.path.dirname(os.path.abspath(__file__))
    jalur = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != sini]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", jalur)
    if spec is None or spec.loader is None or os.path.abspath(spec.origin or "") == os.path.abspath(__file__):
        return
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)


try:
    _pasang()
except Exception as e:  # noqa: BLE001
    # Gagal-tertutup: lebih baik alat tidak jalan drpd jalan dgn KODE_KAB/akun/aturan yang salah.
    # (Exception biasa di sini ditelan site.py, jadi keluar paksa.)
    print(f"⛔ [GUI] pengaturan GUI tidak bisa diterapkan, alat dihentikan: {e}", file=sys.stderr, flush=True)
    os._exit(3)
try:
    _berantai()
except Exception as e:  # noqa: BLE001
    print(f"⚠️ [GUI] sitecustomize lain gagal dijalankan: {e}", file=sys.stderr)
