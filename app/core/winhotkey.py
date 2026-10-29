"""
Win32 RegisterHotKey destek katmani (4.4).

'keyboard' kutuphanesi dusuk seviye bir klavye kancasi (WH_KEYBOARD_LL)
kullanir. Bu kanca, Windows'un Kullanici Arayuzu Ayricalik Yalitimi
(UIPI) kurallari yuzunden oyun YONETICI olarak calisirken (bu program
calismiyorsa) klavye olaylarini hic goremeyebilir; ayrica (bu oturumda
da gozlendigi gibi) baska bir programin kendi kancasiyla cakismasi gibi
sebeplerle de sessizce bozulabilir.

RegisterHotKey TAMAMEN FARKLI bir isletim sistemi mekanizmasidir (WM_HOTKEY
penceres mesaji) - ayni UIPI sinirlamasina tabi olsa da, farkli bir kod
yoluna dayandigi icin 'keyboard' calismadigi bazi durumlarda hala
calisabilir. Bu yuzden IKISI DE AYNI ANDA calistirilir (bkz. hotkeys.py'deki
tekrar-onleme/dedup katmani) - biri yetmezse diger bir sans saglar.

ONEMLI: Oyun Yonetici calisirken kisayollarin GUVENILIR sekilde calismasi
icin asil garanti bu PROGRAMIN DA Yonetici olarak calismasidir (bkz.
relaunch_as_admin). Bu modul sadece EK bir sans saglar, garanti vermez.
"""
import ctypes
import logging
import os
import sys

logger = logging.getLogger("OyunCevirmen.winhotkey")

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

_MOD_VK = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT}

VK_BY_NAME = {
    **{f"f{i}": 0x6F + i for i in range(1, 13)},  # VK_F1=0x70 ... VK_F12=0x7B
    **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"},
    **{d: ord(d) for d in "0123456789"},
    "insert": 0x2D, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22, "pause": 0x13, "scroll lock": 0x91,
    "space": 0x20, "tab": 0x09, "esc": 0x1B,
}


def parse_hotkey(value):
    """"ctrl+f9" gibi bir dizgeyi (mod_bayraklari, vk_kodu) ikilisine
    cevirir; taninmayan bir tus/bos dizge icin None doner. Saf fonksiyon -
    Windows API'sine ihtiyac duymaz, kolayca test edilir."""
    if not value:
        return None
    parts = [p.strip().lower() for p in value.split("+") if p.strip()]
    if not parts:
        return None
    vk = VK_BY_NAME.get(parts[-1])
    if vk is None:
        return None
    mods = 0
    for p in parts[:-1]:
        mod = _MOD_VK.get(p)
        if mod is None:
            return None
        mods |= mod
    return mods, vk


def relaunch_as_admin():
    """Programi Yonetici olarak (UAC istemiyle) yeniden baslatir.

    Oyun Yonetici calisirken kisayollarin GUVENILIR calismasinin tek
    gercek garantisi, bu programin DA en az o kadar yetkili calismasidir
    (Windows'un UIPI kurallari). Basarili olup olmadigini (True/False)
    dondurur; cagiran taraf True donerse MEVCUT sureci kapatmalidir -
    bu fonksiyon kendisi kapatmaz."""
    if os.name != "nt":
        return False
    try:
        # Dondurulmus (PyInstaller) bir .exe'de sys.executable ZATEN
        # sys.argv[0] ile aynidir - tekrar eklenirse parametre olarak
        # kendi yolunu ikinci kez alirdi. Gelistirme ortaminda (python -m
        # app.main) ise sys.executable yorumlayici, argv[0] betik yolu -
        # ikisi de gerekli.
        args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
        params = " ".join(f'"{a}"' for a in args)
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1)
        # ShellExecuteW basari durumunda 32'den BUYUK bir deger dondurur.
        return int(result) > 32
    except Exception as exc:
        logger.error("Yonetici olarak yeniden baslatma basarisiz: %s", exc)
        return False


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def _make_hotkey_window():
    """Yalnizca WM_HOTKEY mesajlarini yakalamaya yarayan, hic gorunmeyen
    bir QWidget olusturur. Qt ana olay dongusu zaten calistigi icin bu
    pencereye gelen native mesajlar otomatik islenir."""
    from PyQt6 import QtCore, QtWidgets

    class _HotkeyWindow(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            self.handlers = {}  # hotkey id -> callable (parametresiz)
            self.resize(1, 1)
            self.show()

        def nativeEvent(self, event_type, message):
            try:
                msg = _MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    handler = self.handlers.get(int(msg.wParam or 0))
                    if handler is not None:
                        handler()
            except Exception as exc:
                logger.error("WM_HOTKEY isleme hata verdi: %s", exc)
            return False, 0

    return _HotkeyWindow()


class Win32HotkeyBridge:
    """RegisterHotKey ile kaydedilen kisayollari yonetir. Herhangi bir
    adimda (Qt/ctypes/Windows disi platform) hata olursa sessizce devre
    disi kalir - 'keyboard' kutuphanesine dayanan ana mekanizmayi ASLA
    etkilemez."""

    def __init__(self):
        self._window = None
        self._next_id = 1

    def register(self, entries):
        """entries: [(ad, tus_dizgesi, handler), ...]. Basariyla
        kaydedilenlerin ["ad=tus", ...] listesini dondurur (loglama icin)."""
        self.unregister_all()
        if os.name != "nt":
            return []
        try:
            from PyQt6 import QtWidgets
            if QtWidgets.QApplication.instance() is None:
                return []
            self._window = _make_hotkey_window()
            hwnd = int(self._window.winId())
        except Exception as exc:
            logger.debug("Win32 kisayol penceresi olusturulamadi: %s", exc)
            self._window = None
            return []

        registered = []
        for name, key, handler in entries:
            parsed = parse_hotkey(key)
            if parsed is None:
                continue
            mods, vk = parsed
            hotkey_id = self._next_id
            self._next_id += 1
            try:
                ok = ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, mods | MOD_NOREPEAT, vk)
            except Exception as exc:
                logger.debug("RegisterHotKey hata verdi (%s=%r): %s", name, key, exc)
                continue
            if ok:
                self._window.handlers[hotkey_id] = handler
                registered.append(f"{name}={key}")
            else:
                # Genelde baska bir program AYNI kisayolu zaten almis
                # demektir - fatal degil, sadece bu EK kanal o tus icin
                # devre disi kalir.
                logger.debug("RegisterHotKey basarisiz (%s=%r) - baska bir program kullaniyor olabilir.",
                              name, key)
        return registered

    def unregister_all(self):
        if self._window is None:
            return
        try:
            hwnd = int(self._window.winId())
            for hotkey_id in list(self._window.handlers):
                try:
                    ctypes.windll.user32.UnregisterHotKey(hwnd, hotkey_id)
                except Exception:
                    pass
            self._window.deleteLater()
        except Exception as exc:
            logger.debug("Win32 kisayol penceresi kapatilirken hata: %s", exc)
        self._window = None
