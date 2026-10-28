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

            registered = []
            # Her kisayolu AYRI AYRI deneriz: config.json elle bozulup bir
            # tusu gecersiz bir dizgeye donusturulmus olsa bile (orn. bos
            # metin), DIGER iki kisayol yine de calismaya devam etsin -
            # ozellikle F11 (cikis) her zaman en azindan denenmeli.
            for name, key, handler in (
                ("aninda", instant_key, self.on_instant),
                ("canli", live_key, self.on_live_toggle),
                ("cikis", quit_key, self.on_quit),
            ):
                try:
                    self._hooks.append(keyboard.add_hotkey(key, self._safe(handler)))
                    registered.append(f"{name}={key}")
                except Exception as exc:
                    logger.error("Kisayol kaydedilemedi (%s=%r): %s", name, key, exc)
            logger.info("Kisayollar aktif: %s", ", ".join(registered) if registered else "HICBIRI (hata)")

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
