"""
Sistem tepsisi (saat yanindaki simgeler) modulu. Sag tik menusunde:
 - Durum bilgisi (OCR/ceviri motoru, canli mod durumu) - salt okunur
 - Ayarlar dosyasini ac (config.json, Notepad ile)
 - Canli modu ac/kapat
 - Cikis

pystray kendi native mesaj donguye sahip oldugu icin ayri bir thread'de
calistirilir.
"""
import logging
import os
import threading

import pystray
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("OyunCevirmen.tray")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON_PATH = os.path.join(BASE_DIR, "app", "assets", "icon.png")


def _ensure_icon():
    if os.path.exists(ICON_PATH):
        return ICON_PATH
    os.makedirs(os.path.dirname(ICON_PATH), exist_ok=True)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(20, 90, 200, 255))
    try:
        font = ImageFont.truetype("segoeuib.ttf", 34)
    except Exception:
        font = ImageFont.load_default()
    draw.text((32, 32), "Ç", fill=(255, 255, 255, 255), font=font, anchor="mm")
    img.save(ICON_PATH)
    return ICON_PATH


class TrayApp:
    def __init__(self, config, status_provider, on_toggle_live, on_instant, on_quit,
                 on_open_window=None, on_toggle_mini=None):
        """
        status_provider: () -> dict(ocr_engine, translate_engine, live_active)
        on_toggle_live, on_instant, on_quit, on_open_window: callback'ler (parametresiz)
        """
        self.config = config
        self.status_provider = status_provider
        self.on_toggle_live = on_toggle_live
        self.on_instant = on_instant
        self.on_quit = on_quit
        self.on_open_window = on_open_window
        self.on_toggle_mini = on_toggle_mini
        self._icon = None
        self._thread = None

    def _key(self, name, default):
        parts = (self.config.get(name, default) or default).split("+")
        return " + ".join(p.capitalize() if len(p) > 3 else p.upper() for p in parts)

    def _live_label(self, item):
        st = self.status_provider()
        verb = "Canlı modu durdur" if st.get("live_active") else "Canlı modu başlat"
        return f"{verb}    {self._key('hotkey_live_toggle', 'f10')}"

    def _instant_label(self, item):
        return f"Anında tara    {self._key('hotkey_instant', 'f9')}"

    def _quit_label(self, item):
        return f"Çıkış    {self._key('hotkey_quit', 'f11')}"

    def _status_label(self, item):
        st = self.status_provider()
        engines = {"ollama": "Ollama", "google": "Google Translate"}
        ocr = {"windows": "Windows OCR", "easyocr": "EasyOCR"}
        return (f"Çeviri: {engines.get(st.get('translate_engine'), st.get('translate_engine'))}   "
                f"Okuma: {ocr.get(st.get('ocr_engine'), st.get('ocr_engine'))}")

    def _open_window(self, icon=None, item=None):
        if self.on_open_window:
            self.on_open_window()

    def _mini_label(self, item):
        st = self.status_provider()
        return "Mini paneli gizle" if st.get("mini_visible") else "Mini paneli göster"

    def _toggle_mini(self, icon=None, item=None):
        if self.on_toggle_mini:
            self.on_toggle_mini()

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Kontrol panelini aç", self._open_window, default=True
            ),
            pystray.MenuItem(self._mini_label, self._toggle_mini),
            pystray.MenuItem(self._instant_label, lambda icon, item: self.on_instant()),
            pystray.MenuItem(self._live_label, lambda icon, item: self.on_toggle_live()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._quit_label, lambda icon, item: self.on_quit()),
        )

    def start(self):
        icon_path = _ensure_icon()
        image = Image.open(icon_path)
        self._icon = pystray.Icon(
            "OyunCevirmen", image, "Oyun Çevirmen", menu=self._build_menu()
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("Sistem tepsisi simgesi baslatildi.")

    def notify(self, message, title="Oyun Çevirmen"):
        try:
            if self._icon is not None:
                self._icon.notify(message, title)
        except Exception:
            pass

    def update_menu(self):
        if self._icon is not None:
            self._icon.update_menu()

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
