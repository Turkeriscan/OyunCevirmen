"""
Oyun Cevirmen - ana orkestrasyon dosyasi.

Calistirma: C:\\OyunCevirmen klasorunde
    venv\\Scripts\\python.exe -m app.main

Kisayollar:
    F9  - Anlik mod: o anki ekrani tara, tum cevirileri goster. Tekrar basinca kapat.
    F10 - Canli mod ac/kapat: ekran parcalara bolunur, sadece degisen parcalar
          yeniden okunur ve cevrilir.
    F11 - Programi kapat.
"""
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core import capture as capture_mod
from app.core import ocr as ocr_mod
from app.core import translate as translate_mod
from app.core import overlay as overlay_mod
from app.core import hotkeys as hotkeys_mod
from app.core import tray as tray_mod
from app.core import textfilter
from app.core import mainwindow as mainwindow_mod
from app import config as config_mod

from PyQt6 import QtWidgets, QtCore

logger = logging.getLogger("OyunCevirmen")


def setup_logging(level="INFO"):
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "oyuncevirmen.log")

    root = logging.getLogger("OyunCevirmen")
    root.setLevel(getattr(logging, level, logging.INFO))

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def ensure_ollama_running(host, startup_wait=20):
    """Ollama servisi ayakta degilse baslatir. True/False basari durumu doner."""
    try:
        r = requests.get(f"{host}/api/tags", timeout=2)
        if r.status_code == 200:
            logger.info("Ollama zaten calisiyor.")
            return True
    except Exception:
        pass

    logger.info("Ollama calismiyor, baslatiliyor...")
    try:
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # PATH henuz guncel degilse tipik kurulum konumunu dene
        exe = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        try:
            subprocess.Popen(
                [exe, "serve"],
                creationflags=0x08000000,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.error("Ollama baslatilamadi: %s", exc)
            return False
    except Exception as exc:
        logger.error("Ollama baslatilamadi: %s", exc)
        return False

    for _ in range(startup_wait * 2):
        time.sleep(0.5)
        try:
            r = requests.get(f"{host}/api/tags", timeout=2)
            if r.status_code == 200:
                logger.info("Ollama basariyla baslatildi.")
                return True
        except Exception:
            continue
    logger.warning("Ollama %s saniye icinde baslamadi; Google Translate'e dusulecek.", startup_wait)
    return False


def _dedupe_boxes(boxes):
    """Komsu (ortusen) hucreler ayni yaziyi (bazen farkli uzunlukta kirpilmis
    parcalar halinde - orn. 'HELLO WORLD' / 'O WORLD') birden fazla kez
    bulabilir. Kutulari buyukten kucuge (daha uzun/eksiksiz metin once)
    sirala; zaten tutulan bir kutuyla fiziksel olarak ortusen her yeni
    kutu, metni farkli olsa bile elenir (ayni bolgenin eksik/yanlis okunmus
    kopyasi kabul edilir)."""
    ordered = sorted(boxes, key=lambda b: len(b.text), reverse=True)
    result = []
    for box in ordered:
        if not any(_rects_overlap(kept.rect, box.rect) for kept in result):
            result.append(box)
    return result


def _rects_overlap(rect_a, rect_b, threshold=0.4):
    inter = rect_a.intersected(rect_b)
    if inter.isEmpty():
        return False
    inter_area = inter.width() * inter.height()
    min_area = min(rect_a.width() * rect_a.height(), rect_b.width() * rect_b.height())
    if min_area <= 0:
        return False
    return (inter_area / min_area) >= threshold


class AppBridge(QtCore.QObject):
    quit_signal = QtCore.pyqtSignal()
    show_window_signal = QtCore.pyqtSignal()


class Orchestrator:
    MODE_NONE = "none"
    MODE_INSTANT = "instant"
    MODE_LIVE = "live"

    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.capturer = capture_mod.ScreenCapturer(
            monitor_index=config.get("capture_monitor_index", 0)
        )
        self.ocr_manager = ocr_mod.OCRManager(config)
        self.translator = translate_mod.TranslationManager(config)
        self.overlay = overlay_mod.OverlayController(app, config)

        self.mode = self.MODE_NONE
        self._mode_lock = threading.Lock()
        self._live_stop_event = threading.Event()
        self._live_thread = None

        self.main_window = None

        self.bridge = AppBridge()
        self.bridge.quit_signal.connect(self._quit_on_gui_thread)
        self.bridge.show_window_signal.connect(self._show_window_on_gui_thread)

        self.hotkeys = hotkeys_mod.HotkeyManager(
            config, self.toggle_instant, self.toggle_live, self.request_quit
        )
        self.tray = tray_mod.TrayApp(
            config,
            status_provider=self._status,
            on_toggle_live=self.toggle_live,
            on_instant=self.toggle_instant,
            on_quit=self.request_quit,
            on_open_window=self.request_show_window,
        )

    def _status(self):
        return {
            "ocr_engine": self.config.get("ocr_engine"),
            "translate_engine": self.config.get("translate_engine"),
            "live_active": self.mode == self.MODE_LIVE,
        }

    def start(self):
        self.hotkeys.start()
        self.tray.start()
        logger.info("Orkestrasyon basladi. F9=Anlik F10=Canli F11=Cikis")

    # ---------------------------------------------------------------- F9
    def toggle_instant(self):
        with self._mode_lock:
            if self.mode == self.MODE_INSTANT:
                self.mode = self.MODE_NONE
                self.overlay.hide_threadsafe()
                logger.info("Anlik mod kapatildi.")
                return
            if self.mode == self.MODE_LIVE:
                self._stop_live_locked()
            self.mode = self.MODE_INSTANT
        threading.Thread(target=self._run_instant_scan, daemon=True).start()

    def _run_instant_scan(self):
        logger.info("Anlik tarama basladi...")
        try:
            frame = self.capturer.grab_full()
            if frame is None:
                logger.warning("Ekran yakalanamadi.")
                return
            boxes = self._scan_and_translate(frame, offset=(0, 0))
            with self._mode_lock:
                if self.mode != self.MODE_INSTANT:
                    return  # bu arada kapatildi/mod degisti
            self.overlay.show_boxes_threadsafe(boxes)
            logger.info("Anlik tarama tamamlandi: %d kutu gosterildi.", len(boxes))
        except Exception as exc:
            logger.exception("Anlik tarama hatasi: %s", exc)

    # --------------------------------------------------------------- F10
    def toggle_live(self):
        with self._mode_lock:
            if self.mode == self.MODE_LIVE:
                self._stop_live_locked()
                self.overlay.hide_threadsafe()
                logger.info("Canli mod kapatildi.")
                return
            if self.mode == self.MODE_INSTANT:
                self.overlay.hide_threadsafe()
            self.mode = self.MODE_LIVE
            self._live_stop_event.clear()
            self._live_thread = threading.Thread(target=self._live_loop, daemon=True)
            self._live_thread.start()
            logger.info("Canli mod acildi.")

    def _stop_live_locked(self):
        self._live_stop_event.set()
        self.mode = self.MODE_NONE

    def _live_loop(self):
        interval = self.config.get("live_scan_interval", 0.45)
        cols = self.config.get("live_grid_cols", 6)
        rows = self.config.get("live_grid_rows", 4)
        padding = self.config.get("live_cell_padding", 220)

        prev_frame = None
        cell_signatures = {}
        cell_boxes = {}
        grid = None
        frame_h = frame_w = None

        while not self._live_stop_event.is_set():
            t0 = time.time()
            frame = self.capturer.grab_full()
            if frame is None:
                time.sleep(interval)
                continue

            h, w = frame.shape[:2]
            if grid is None:
                grid = capture_mod.build_grid(w, h, cols, rows)
                frame_h, frame_w = h, w

            if prev_frame is not None and capture_mod.frames_identical(prev_frame, frame):
                prev_frame = frame
                self._sleep_remaining(t0, interval)
                continue

            any_change = False
            for idx, cell in enumerate(grid):
                # Degisim tespiti HUCRENIN KENDI sinirlariyla yapilir (ritim/performans
                # icin), ama OCR'a gonderilen kirpma bu sinirin disina da tasar
                # (padding). Boylece hucre sinirina denk gelen bir kelime
                # ("HELLO WORLD" gibi) ikiye bolunup anlamsiz parcalara ayrilmaz;
                # her iki komsu hucre de kelimenin TAMAMINI gorur.
                sig = capture_mod.cell_signature(frame, cell)
                prev_sig = cell_signatures.get(idx)
                if capture_mod.signature_changed(prev_sig, sig):
                    any_change = True
                    cell_signatures[idx] = sig
                    l, t, r, b = cell
                    pl = max(0, l - padding)
                    pt = max(0, t - padding)
                    pr = min(frame_w, r + padding)
                    pb = min(frame_h, b + padding)
                    sub = frame[pt:pb, pl:pr]
                    boxes = self._scan_and_translate(sub, offset=(pl, pt))
                    cell_boxes[idx] = boxes

            prev_frame = frame

            if any_change:
                flat = _dedupe_boxes(
                    [b for lst in cell_boxes.values() for b in lst]
                )
                self.overlay.show_boxes_threadsafe(flat)
                logger.info(
                    "Canli mod guncelleme: %d kutu -> %s",
                    len(flat), [b.text for b in flat][:8],
                )

            self._sleep_remaining(t0, interval)

        logger.info("Canli mod dongusu sonlandi.")

    @staticmethod
    def _sleep_remaining(t0, interval):
        elapsed = time.time() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    # ------------------------------------------------------- yardimci
    def _scan_and_translate(self, frame_bgr, offset):
        ocr_results = self.ocr_manager.recognize(frame_bgr, offset=offset)
        ocr_results = ocr_mod.merge_paragraph_lines(ocr_results)
        boxes = []
        min_len = self.config.get("min_text_length", 2)
        min_conf = self.config.get("min_ocr_confidence", 0.45)

        for r in ocr_results:
            if not textfilter.should_translate(
                r.text, r.confidence, min_length=min_len, min_confidence=min_conf
            ):
                continue
            translated = self.translator.translate(r.text)
            logger.debug("OCR: %r (conf=%.2f) -> %r", r.text, r.confidence, translated)
            if not translated:
                continue
            l, t, right, b = r.bbox
            rect = QtCore.QRect(int(l), int(t), int(right - l), int(b - t))
            boxes.append(overlay_mod.TranslationBox(rect, translated))
        return boxes

    # --------------------------------------------------------------- F11
    def request_quit(self):
        logger.info("Cikis istendi, kapatiliyor...")
        with self._mode_lock:
            self._stop_live_locked()
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        self.bridge.quit_signal.emit()

    def _quit_on_gui_thread(self):
        self.overlay.hide_threadsafe()
        if self.main_window is not None:
            self.main_window.hide()
        QtCore.QTimer.singleShot(150, self.app.quit)

    # ------------------------------------------------------- kontrol paneli
    def request_show_window(self):
        self.bridge.show_window_signal.emit()

    def _show_window_on_gui_thread(self):
        if self.main_window is None:
            self.main_window = mainwindow_mod.MainWindow(self.config, self)
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()


def main():
    config = config_mod.load_config()
    setup_logging(config.get("log_level", "INFO"))
    logger.info("Oyun Cevirmen baslatiliyor...")

    ensure_ollama_running(config.get("ollama_host", "http://127.0.0.1:11434"))

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    orchestrator = Orchestrator(app, config)
    orchestrator.start()
    orchestrator.request_show_window()

    exit_code = app.exec()
    logger.info("Oyun Cevirmen kapandi (kod=%s).", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
