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
import collections
import concurrent.futures
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
from app.ui import mainwindow as mainwindow_mod
from app.ui import theme as ui_theme
from app.ui.minipanel import MiniPanelController
from app import config as config_mod

from PyQt6 import QtCore, QtGui, QtWidgets

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
    toggle_mini_signal = QtCore.pyqtSignal()
    ask_google_permission_signal = QtCore.pyqtSignal()


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
        self.started_at = time.time()      # akistaki zaman kodlari buna gore
        self.live_started_at = None        # canli mod sure sayaci
        # Kontrol panelindeki "Son ceviriler" listesi icin: (zaman, orijinal, ceviri)
        self.recent = collections.deque(maxlen=40)
        self.recent_version = 0
        self._mode_lock = threading.Lock()
        self._live_stop_event = threading.Event()
        self._live_thread = None

        # ---- paralel ceviri (bkz. _translate_one / _submit_live_translation) ----
        max_workers = max(1, int(config.get("translate_parallel_workers", 3)))
        self._translate_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ceviri"
        )
        self._translate_inflight = set()       # su an cevrilmekte olan metinler
        self._translate_inflight_lock = threading.Lock()
        # Ollama'nin paralel istekleri iyi karsilamadigi gozlenirse (ardisik
        # hata/zaman asimi), gecici olarak tek tek (seri) cevirmeye donulur.
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()

        self.main_window = None

        # ---- Google Translate izni (bkz. _request_google_permission) ----
        self._google_prompt_shown = False   # bu oturumda zaten soruldu mu
        self._pending_google_prompt = False  # pencere kapaliyken istendi, acilinca sor
        self._google_prompt_lock = threading.Lock()
        self._quitting = False
        self.translator.on_google_permission_needed = self._request_google_permission

        self.bridge = AppBridge()
        self.bridge.quit_signal.connect(self._quit_on_gui_thread)
        self.bridge.show_window_signal.connect(self._show_window_on_gui_thread)
        self.bridge.toggle_mini_signal.connect(self._toggle_mini_on_gui_thread)
        self.bridge.ask_google_permission_signal.connect(self._ask_google_permission_on_gui_thread)
        self.mini_panel = MiniPanelController(config, self)

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
            on_toggle_mini=self.toggle_mini_panel,
        )

    def _status(self):
        return {
            "ocr_engine": self.config.get("ocr_engine"),
            "translate_engine": self.config.get("translate_engine"),
            "live_active": self.mode == self.MODE_LIVE,
            "mini_visible": self.mini_panel.is_visible(),
        }

    def start(self):
        self.hotkeys.start()
        self.tray.start()
        if self.config.get("mini_panel_enabled"):
            self.mini_panel.show()
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
            survivors = self._ocr_and_filter(frame, offset=self.capturer.get_origin())
            boxes, stats = self._translate_all_blocking(survivors)
            with self._mode_lock:
                if self.mode != self.MODE_INSTANT:
                    return  # bu arada kapatildi/mod degisti
            self.overlay.show_boxes_threadsafe(boxes)
            logger.info(
                "Anlik tarama tamamlandi: %d satir bulundu (%d onbellekten), "
                "ortalama ceviri suresi %.2f sn, %d kutu gosterildi.",
                stats["total"], stats["cache_hits"], stats["avg_seconds"], len(boxes),
            )
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
            self.live_started_at = time.time()
            self._live_stop_event.clear()
            self._live_thread = threading.Thread(target=self._live_loop, daemon=True)
            self._live_thread.start()
            logger.info("Canli mod acildi.")

    def _stop_live_locked(self):
        self._live_stop_event.set()
        self.mode = self.MODE_NONE
        self.live_started_at = None

    def _live_loop(self):
        interval = self.config.get("live_scan_interval", 0.45)
        cols = self.config.get("live_grid_cols", 6)
        rows = self.config.get("live_grid_rows", 4)
        padding = self.config.get("live_cell_padding", 220)

        prev_frame = None
        cell_signatures = {}
        cell_boxes = {}
        cell_lock = threading.Lock()
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
            tick_total = 0
            tick_cache_hits = 0
            tick_pending = 0
            context_lines = self._context_lines()
            source_lang = self.config.get("source_lang", "auto")
            target_lang = self.config.get("target_lang", "tr")
            engine_pref = self.config.get("translate_engine", "ollama")

            for idx, cell in enumerate(grid):
                # Degisim tespiti HUCRENIN KENDI sinirlariyla yapilir (ritim/performans
                # icin), ama OCR'a gonderilen kirpma bu sinirin disina da tasar
                # (padding). Boylece hucre sinirina denk gelen bir kelime
                # ("HELLO WORLD" gibi) ikiye bolunup anlamsiz parcalara ayrilmaz;
                # her iki komsu hucre de kelimenin TAMAMINI gorur.
                sig = capture_mod.cell_signature(frame, cell)
                prev_sig = cell_signatures.get(idx)
                if not capture_mod.signature_changed(prev_sig, sig):
                    continue
                any_change = True
                cell_signatures[idx] = sig
                l, t, r, b = cell
                pl = max(0, l - padding)
                pt = max(0, t - padding)
                pr = min(frame_w, r + padding)
                pb = min(frame_h, b + padding)
                sub = frame[pt:pb, pl:pr]
                mon_left, mon_top = self.capturer.get_origin()
                offset = (pl + mon_left, pt + mon_top)

                survivors = self._ocr_and_filter(sub, offset)
                tick_total += len(survivors)

                # Onbellekte olanlar HEMEN gosterilir (bu hucrenin kutu listesi);
                # olmayanlar arka planda (sinirli paralellikte) cevrilip hazir
                # olduklarinda overlay ayrica guncellenir - tarama dongusu
                # (bu for dongusu ve disaridaki while) onlari BEKLEMEZ.
                cached_boxes = []
                for res in survivors:
                    cached = self.translator.cache.get(res.text, source_lang, target_lang, engine_pref)
                    if cached is not None:
                        tick_cache_hits += 1
                        cached_boxes.append(self._make_box(res, cached))
                    else:
                        tick_pending += 1
                        self._submit_live_translation(res, idx, cell_boxes, cell_lock, context_lines)

                with cell_lock:
                    cell_boxes[idx] = cached_boxes

            prev_frame = frame

            if any_change:
                with cell_lock:
                    flat = _dedupe_boxes([b for lst in cell_boxes.values() for b in lst])
                self.overlay.show_boxes_threadsafe(flat)
                logger.info(
                    "Canli mod guncelleme: %d satir (%d onbellekten, %d arka planda "
                    "cevriliyor) -> %d kutu: %s",
                    tick_total, tick_cache_hits, tick_pending, len(flat),
                    [b.text for b in flat][:8],
                )

            self._sleep_remaining(t0, interval)

        logger.info("Canli mod dongusu sonlandi.")

    def _submit_live_translation(self, result, idx, cell_boxes, cell_lock, context_lines):
        """Bir satiri arka planda cevirir; bitince SADECE o hucrenin kutu
        listesine ekler ve overlay'i gunceller. Canli dongu bunu beklemez."""
        if not self._claim_inflight(result.text):
            return  # ayni metin zaten baska bir yerden cevriliyor

        def work():
            try:
                translated = self._translate_one(result.text, context_lines)
            finally:
                self._release_inflight(result.text)
            if not translated or self._live_stop_event.is_set():
                return
            self._remember(result.text, translated)
            box = self._make_box(result, translated)
            with cell_lock:
                cell_boxes.setdefault(idx, []).append(box)
                flat = _dedupe_boxes([b for lst in cell_boxes.values() for b in lst])
            if not self._live_stop_event.is_set():
                self.overlay.show_boxes_threadsafe(flat)

        self._translate_executor.submit(work)

    @staticmethod
    def _sleep_remaining(t0, interval):
        elapsed = time.time() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    # ------------------------------------------------------- yardimci
    def _ocr_and_filter(self, frame_bgr, offset):
        """OCR calistirir, paragraf satirlarini birlestirir ve cevrilmeye
        deger olmayanlari (cok kisa/sembol/dusuk guven/zaten Turkce) eler."""
        ocr_results = self.ocr_manager.recognize(frame_bgr, offset=offset)
        ocr_results = ocr_mod.merge_paragraph_lines(ocr_results)
        min_len = self.config.get("min_text_length", 2)
        min_conf = self.config.get("min_ocr_confidence", 0.45)
        source_lang = self.config.get("source_lang", "auto")
        return [
            r for r in ocr_results
            if textfilter.should_translate(
                r.text, r.confidence, min_length=min_len, min_confidence=min_conf,
                source_lang=source_lang,
            )
        ]

    @staticmethod
    def _make_box(result, translated_text):
        l, t, right, b = result.bbox
        rect = QtCore.QRect(int(l), int(t), int(right - l), int(b - t))
        return overlay_mod.TranslationBox(rect, translated_text)

    def _context_lines(self):
        """Son N cevrilmis satiri (en yeni once) modele baglam olarak
        verilecek (orijinal, ceviri) ciftleri halinde dondurur."""
        n = max(0, int(self.config.get("translate_context_lines", 4)))
        if n == 0:
            return []
        return [(orig, trans) for _, orig, trans in list(self.recent)[:n]]

    def _claim_inflight(self, text):
        """Ayni metin birden fazla yerden (orn. ortusen iki hucreden) ayni
        anda cevrilmeye calisiliyorsa, sadece ilkine izin verir."""
        with self._translate_inflight_lock:
            if text in self._translate_inflight:
                return False
            self._translate_inflight.add(text)
            return True

    def _release_inflight(self, text):
        with self._translate_inflight_lock:
            self._translate_inflight.discard(text)

    def _translate_one(self, text, context_lines):
        """Tek bir metni cevirir. Ollama ardisik hata/zaman asimi verirse
        (paralel istekleri iyi karsilamiyor olabilir), devre kesici devreye
        girer ve bir sureligine TEK TEK (seri) cevirmeye doner; ilk basari
        sayaci sifirlar."""
        degraded = self._translate_consecutive_failures >= 2
        if degraded:
            with self._translate_sequential_lock:
                translated = self.translator.translate(text, context_lines=context_lines)
        else:
            translated = self.translator.translate(text, context_lines=context_lines)

        with self._translate_fail_lock:
            if translated:
                self._translate_consecutive_failures = 0
            else:
                self._translate_consecutive_failures += 1
        return translated

    def _translate_all_blocking(self, results):
        """Verilen tum OCR sonuclarini cevirir (onbellek + sinirli
        paralellik), hepsi bitene kadar bekler - aninda mod (F9) tek seferlik
        bir tarama oldugu icin sonucu bekleyebilir. Canli mod ise bu
        fonksiyonu KULLANMAZ (bkz. _live_loop/_submit_live_translation);
        orada tarama dongusu cevirileri beklemeden devam eder."""
        context_lines = self._context_lines()
        source_lang = self.config.get("source_lang", "auto")
        target_lang = self.config.get("target_lang", "tr")
        engine_pref = self.config.get("translate_engine", "ollama")

        boxes = []
        cache_hits = 0
        durations = []

        pending = []
        for r in results:
            cached = self.translator.cache.get(r.text, source_lang, target_lang, engine_pref)
            if cached is not None:
                cache_hits += 1
                boxes.append(self._make_box(r, cached))
            else:
                pending.append(r)

        futures = {}
        for r in pending:
            if not self._claim_inflight(r.text):
                continue
            t0 = time.time()
            fut = self._translate_executor.submit(self._translate_one, r.text, context_lines)
            futures[fut] = (r, t0)

        for fut in concurrent.futures.as_completed(futures):
            r, t0 = futures[fut]
            try:
                translated = fut.result()
            except Exception as exc:
                logger.warning("Ceviri is parcacigi hata verdi: %s", exc)
                translated = None
            finally:
                self._release_inflight(r.text)
            durations.append(time.time() - t0)
            if translated:
                self._remember(r.text, translated)
                boxes.append(self._make_box(r, translated))

        stats = {
            "total": len(results),
            "cache_hits": cache_hits,
            "avg_seconds": (sum(durations) / len(durations)) if durations else 0.0,
        }
        return boxes, stats

    def _remember(self, original, translated):
        """Ayni cumle canli modda tekrar tekrar gelir; listede sadece bir kez
        (en ustte) dursun."""
        for item in list(self.recent):
            if item[1] == original:
                try:
                    self.recent.remove(item)
                except ValueError:
                    pass
                break
        self.recent.appendleft((time.time(), original, translated))
        self.recent_version += 1

    # ------------------------------------------------------- monitor secimi
    def change_monitor(self, index):
        """Yakalanacak monitoru calisirken degistirir (program yeniden
        baslatilmadan). Aktif bir mod varsa once guvenli sekilde durdurulur."""
        with self._mode_lock:
            if self.mode == self.MODE_LIVE:
                self._stop_live_locked()
                self.overlay.hide_threadsafe()
            elif self.mode == self.MODE_INSTANT:
                self.mode = self.MODE_NONE
                self.overlay.hide_threadsafe()

        try:
            new_capturer = capture_mod.ScreenCapturer(monitor_index=index)
        except Exception as exc:
            logger.error("Monitor degistirilemedi (%s): %s", index, exc)
            return False

        old_capturer = self.capturer
        self.capturer = new_capturer
        try:
            old_capturer.close()
        except Exception:
            pass

        self.config["capture_monitor_index"] = index
        config_mod.save_config(self.config)
        logger.info("Yakalanacak monitor degistirildi: %s", index)
        return True

    # --------------------------------------------------------------- F11
    def request_quit(self):
        logger.info("Cikis istendi, kapatiliyor...")
        self._quitting = True
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
        try:
            self._translate_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.bridge.quit_signal.emit()

    def _quit_on_gui_thread(self):
        self.overlay.hide_threadsafe()
        try:
            if self.mini_panel.panel is not None:
                self.mini_panel.panel.hide()
        except Exception:
            pass
        if self.main_window is not None:
            try:
                self.main_window.apply_now()
                self.main_window._remember_geometry()
            except Exception:
                pass
            self.main_window.hide()
        QtCore.QTimer.singleShot(150, self.app.quit)

    # ----------------------------------------------------------- mini panel
    def toggle_mini_panel(self):
        """Herhangi bir thread'den cagrilabilir (tepsi menusu ayri thread'de)."""
        self.bridge.toggle_mini_signal.emit()

    def _toggle_mini_on_gui_thread(self):
        self.mini_panel.toggle()
        try:
            self.tray.update_menu()
        except Exception:
            pass

    # ------------------------------------------------------- kontrol paneli
    def request_show_window(self):
        self.bridge.show_window_signal.emit()

    def _show_window_on_gui_thread(self):
        if self.main_window is None:
            self.main_window = mainwindow_mod.MainWindow(self.config, self)
        if self.main_window.isMinimized():
            self.main_window.showNormal()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        if self._pending_google_prompt:
            self._pending_google_prompt = False
            self._show_google_permission_dialog()

    # ------------------------------------------------- Google Translate izni
    def _request_google_permission(self):
        """Ceviri is parcaciklarindan (arka plan thread) cagrilir. Izin
        daha once hic sorulmadiysa, bu oturumda SADECE BIR KEZ sorulmasini
        saglar; pencere acik/gorunurse dogrudan soru penceresi, degilse
        tepsi bildirimi (ve pencere acilinca soru) gosterilir."""
        with self._google_prompt_lock:
            if self._google_prompt_shown:
                return
            self._google_prompt_shown = True
        self.bridge.ask_google_permission_signal.emit()

    def _ask_google_permission_on_gui_thread(self):
        if self._quitting:
            return  # program kapanirken yeni bir soru penceresi acmanin anlami yok
        if self.main_window is not None and self.main_window.isVisible():
            self._show_google_permission_dialog()
        else:
            self._pending_google_prompt = True
            try:
                self.tray.notify(
                    "Ollama çalışmıyor. Ekrandaki yazıları Google Translate ile "
                    "çevirmek için kontrol panelini açıp izin verebilirsin "
                    "(Çeviri sayfası).",
                    "Oyun Çevirmen",
                )
            except Exception:
                pass

    def _show_google_permission_dialog(self):
        try:
            answer = QtWidgets.QMessageBox.question(
                self.main_window, "Google Translate kullanılsın mı?",
                "Ollama çalışmıyor. Ekrandaki yazılar çeviri için Google'a "
                "(internete) gönderilsin mi?\n\nBu seçimi istediğin zaman "
                "Çeviri sayfasından değiştirebilirsin.",
            )
            if self._quitting:
                # Program kapanirken pencere zorla kapatildiysa Qt "Hayir"
                # donebilir; bu kullanicinin GERCEK cevabi degil, kaydetme.
                logger.info("Google izin penceresi kapanirken kesildi, cevap kaydedilmedi.")
                return
            allowed = answer == QtWidgets.QMessageBox.StandardButton.Yes
            self.config["allow_google_fallback"] = allowed
            config_mod.save_config(self.config)
            logger.info("Google Translate izni: %s", "verildi" if allowed else "verilmedi")
            if self.main_window is not None:
                with self.main_window.loading():
                    for page in self.main_window.settings_pages:
                        page.load(self.config)
                self.main_window.refresh_status()
        except Exception as exc:
            logger.error("Google izin penceresi gosterilemedi: %s", exc)

    def reset_google_permission_prompt(self):
        """Ayarlar 'varsayilana dondur' ile allow_google_fallback tekrar
        None (sorulmadi) yapildiginda, bu oturumda yeniden sorulabilmesi
        icin bayragi sifirlar."""
        with self._google_prompt_lock:
            self._google_prompt_shown = False
        self._pending_google_prompt = False


def _install_crash_handlers():
    """Yakalanmamis hatalarin HER ZAMAN gunluge yazilmasini saglar.

    Program genelde pythonw.exe ile (konsolsuz) calisir; varsayilan
    davranista yakalanmamis bir hata sessizce programi kapatir ve
    kullanici hicbir sey gormez/gunlukte hicbir iz kalmaz. Bu fonksiyon:
      - sys.excepthook: ana is parcacigindaki (PyQt slot'lari dahil,
        PyQt bu hook'u Python istisnalari icin kullanir) yakalanmamis
        hatalari loglar.
      - threading.excepthook: arka plan is parcaciklarindaki (canli mod
        dongusu, ceviri havuzu vb.) yakalanmamis hatalari loglar.
    """
    def _log_exception(exc_type, exc_value, exc_tb, thread_name="MainThread"):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "YAKALANMAMIS HATA (%s): %s", thread_name,
            "".join(__import__("traceback").format_exception(exc_type, exc_value, exc_tb)),
        )

    def _excepthook(exc_type, exc_value, exc_tb):
        _log_exception(exc_type, exc_value, exc_tb, "MainThread")

    def _thread_excepthook(args):
        _log_exception(args.exc_type, args.exc_value, args.exc_traceback,
                       getattr(args.thread, "name", "?"))

    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


def _set_process_dpi_awareness():
    """Islemi "monitor basina DPI farkinda" yapar. Bu olmadan, farkli
    olcekli (%100/%125/%150) monitorler arasinda mss/dxcam/Qt'nin
    rapor ettigi koordinatlar birbiriyle tutarsiz olabilir (bazisi
    fiziksel piksel, bazisi olceklenmis/mantiksal piksel dondurebilir),
    bu da cevirilerin yanlis yere cizilmesine yol acar. En erken,
    QApplication olusturulmadan once cagrilmalidir."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception as exc:
            logger.warning("Islem DPI farkindaligi ayarlanamadi: %s", exc)


def main():
    config = config_mod.load_config()
    setup_logging(config.get("log_level", "INFO"))
    _install_crash_handlers()
    logger.info("Oyun Cevirmen baslatiliyor...")

    try:
        _set_process_dpi_awareness()
        ensure_ollama_running(config.get("ollama_host", "http://127.0.0.1:11434"))

        if os.name == "nt":
            # Gorev cubugunda Python'un degil, programin kendi simgesi gorunsun
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OyunCevirmen.App")
            except Exception:
                pass

        app = QtWidgets.QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName("Oyun Çevirmen")
        ui_theme.load_fonts()
        ui_theme.init_scale(app)
        app.setFont(ui_theme.font("body", 10))
        app.setStyleSheet(ui_theme.app_stylesheet())
        app.setWindowIcon(QtGui.QIcon(os.path.join(BASE_DIR, "app", "assets", "icon.ico")))

        orchestrator = Orchestrator(app, config)
        orchestrator.start()
        orchestrator.request_show_window()

        exit_code = app.exec()
        logger.info("Oyun Cevirmen kapandi (kod=%s).", exit_code)
    except Exception:
        logger.critical("Baslangicta yakalanmamis hata, program kapatiliyor.", exc_info=True)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
