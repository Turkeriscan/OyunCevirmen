"""
Kaynak tasarrufu (3.4) icin yardimcilar: oyunun su an on planda olup
olmadigini ve sistemin bos (idle) olup olmadigini tespit eder. Sadece
Windows'ta calisir; herhangi bir hata/kurulumda (ornegin testlerde
ctypes.windll bulunmaz) sessizce "bilinmiyor" degerleri (None/0.0) doner -
cagiran taraf bunu GUVENLI TARAFTA kalarak ("duraklatma") yorumlar.
"""
import ctypes
import logging
import os
import sys

logger = logging.getLogger("OyunCevirmen.activity")

LIVE_IDLE_PAUSE_SECONDS = 120


def own_exe_name():
    """Bu surecin calistirdigi .exe'nin (kucuk harfli) adi - kullanici
    kendi ayar penceresine gecince canli mod yanlislikla duraklamasin diye."""
    try:
        return os.path.basename(sys.executable).lower()
    except Exception:
        return ""


def get_foreground_exe_name():
    """On plandaki pencerenin ait oldugu surecin .exe adini (kucuk harfle)
    dondurur; tespit edilemezse None doner."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid.value)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            if not ok:
                return None
            return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception as exc:
        logger.debug("On plandaki pencere tespit edilemedi: %s", exc)
        return None


def get_idle_seconds():
    """Son klavye/fare girdisinden bu yana gecen saniye; tespit edilemezse
    0.0 (yani 'bos degil' - sessizce yanlis duraklatmaya yol acmasin)."""
    try:
        class _LastInputInfo(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(_LastInputInfo)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick_count = ctypes.windll.kernel32.GetTickCount()
        millis_idle = tick_count - info.dwTime
        return max(0.0, millis_idle / 1000.0)
    except Exception as exc:
        logger.debug("Bosta kalma suresi tespit edilemedi: %s", exc)
        return 0.0


def should_pause_live(foreground_exe, idle_seconds, game_exe, own_exe, enabled,
                       idle_threshold_seconds=LIVE_IDLE_PAUSE_SECONDS):
    """Canli modun su an duraklatilip duraklatilmayacagina karar veren saf
    (test edilebilir) fonksiyon.

    Bilinmeyen durumlarda (foreground_exe veya game_exe tespit edilememisse)
    GUVENLI TARAFTA kalinir (duraklatilmaz) - yanlis pozitif yuzunden
    kullanicinin cevirisi bosu bosuna kesilmesin."""
    if not enabled:
        return False
    if idle_seconds >= idle_threshold_seconds:
        return True
    if not foreground_exe or not game_exe:
        return False
    if foreground_exe == game_exe or foreground_exe == own_exe:
        return False
    return True
