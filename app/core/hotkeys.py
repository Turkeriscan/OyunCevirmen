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
    def __init__(self, config, on_instant, on_live_toggle, on_quit, on_region_select=None,
                 on_reveal_press=None, on_reveal_release=None):
        self.config = config
        self.on_instant = on_instant
        self.on_live_toggle = on_live_toggle
        self.on_quit = on_quit
        self.on_region_select = on_region_select
        # Tutma-ile-goster (4.2): basili TUTULDUKCA orijinal yaziyi gosterir,
        # birakinca geri cevirir. add_hotkey (tek tetikleme) yerine
        # on_press_key/on_release_key kullanilir - bkz. start().
        self.on_reveal_press = on_reveal_press
        self.on_reveal_release = on_reveal_release
        self._hooks = []
        self._key_hooks = []
        self._reveal_held = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self._unregister_all()
            instant_key = self.config.get("hotkey_instant", "f9")
            live_key = self.config.get("hotkey_live_toggle", "f10")
            quit_key = self.config.get("hotkey_quit", "f11")
            region_key = self.config.get("hotkey_region_select", "f8")
            reveal_key = self.config.get("hotkey_hold_reveal", "f6")

            entries = [
                ("aninda", instant_key, self.on_instant),
                ("canli", live_key, self.on_live_toggle),
                ("cikis", quit_key, self.on_quit),
            ]
            # Bolge secimi (3.5) ISTEGE BAGLI: Orchestrator her zaman bu
            # kisayolu saglamayabilir (orn. eski bir cagiran/test icin).
            if self.on_region_select is not None:
                entries.append(("bolge_sec", region_key, self.on_region_select))

            registered = []
            # Her kisayolu AYRI AYRI deneriz: config.json elle bozulup bir
            # tusu gecersiz bir dizgeye donusturulmus olsa bile (orn. bos
            # metin), DIGER kisayollar yine de calismaya devam etsin -
            # ozellikle F11 (cikis) her zaman en azindan denenmeli.
            for name, key, handler in entries:
                try:
                    self._hooks.append(keyboard.add_hotkey(key, self._safe(handler)))
                    registered.append(f"{name}={key}")
                except Exception as exc:
                    logger.error("Kisayol kaydedilemedi (%s=%r): %s", name, key, exc)

            if self.on_reveal_press is not None and self.on_reveal_release is not None:
                try:
                    self._key_hooks.append(
                        keyboard.on_press_key(reveal_key, self._safe_hold(self._on_reveal_press_once)))
                    self._key_hooks.append(
                        keyboard.on_release_key(reveal_key, self._safe_hold(self._on_reveal_release_once)))
                    registered.append(f"orijinali_goster={reveal_key}")
                except Exception as exc:
                    logger.error("Kisayol kaydedilemedi (orijinali_goster=%r): %s", reveal_key, exc)

            logger.info("Kisayollar aktif: %s", ", ".join(registered) if registered else "HICBIRI (hata)")

    def _on_reveal_press_once(self):
        # OS tus-tekrari yuzunden basili tutulurken press defalarca ates
        # alir - sadece "yeni basildi" gecisinde GERCEKTEN gizlemek icin.
        if not self._reveal_held:
            self._reveal_held = True
            self.on_reveal_press()

    def _on_reveal_release_once(self):
        if self._reveal_held:
            self._reveal_held = False
            self.on_reveal_release()

    def _safe(self, fn):
        def wrapper():
            try:
                fn()
            except Exception as exc:
                logger.error("Kisayol islemi hata verdi: %s", exc)
        return wrapper

    def _safe_hold(self, fn):
        def wrapper(_event):
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
        for h in self._key_hooks:
            try:
                keyboard.unhook(h)
            except (KeyError, ValueError):
                pass
        self._key_hooks = []
        self._reveal_held = False

    def stop(self):
        with self._lock:
            self._unregister_all()
