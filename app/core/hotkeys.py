"""
Global kisayol yonetimi. 'keyboard' kutuphanesi dusuk seviye klavye kancasi
kullandigi icin oyun pencere odakta olsa da (cogu oyunda) calisir.

F9  -> aninda mod (tetikle/kapat)
F10 -> canli mod ac/kapat
F11 -> programi kapat
"""
import logging
import threading

import keyboard

logger = logging.getLogger("OyunCevirmen.hotkeys")


class HotkeyManager:
    def __init__(self, config, on_instant, on_live_toggle, on_quit):
        self.config = config
        self.on_instant = on_instant
        self.on_live_toggle = on_live_toggle
        self.on_quit = on_quit
        self._hooks = []
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self._unregister_all()
            instant_key = self.config.get("hotkey_instant", "f9")
            live_key = self.config.get("hotkey_live_toggle", "f10")
            quit_key = self.config.get("hotkey_quit", "f11")

            self._hooks.append(keyboard.add_hotkey(instant_key, self._safe(self.on_instant)))
            self._hooks.append(keyboard.add_hotkey(live_key, self._safe(self.on_live_toggle)))
            self._hooks.append(keyboard.add_hotkey(quit_key, self._safe(self.on_quit)))
            logger.info(
                "Kisayollar aktif: aninda=%s canli=%s cikis=%s",
                instant_key, live_key, quit_key,
            )

    def _safe(self, fn):
        def wrapper():
            try:
                fn()
            except Exception as exc:
                logger.error("Kisayol islemi hata verdi: %s", exc)
        return wrapper

    def _unregister_all(self):
        for h in self._hooks:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        self._hooks = []

    def stop(self):
        with self._lock:
            self._unregister_all()
