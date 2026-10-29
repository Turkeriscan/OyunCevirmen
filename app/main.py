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

from app.core import activity as activity_mod
from app.core import capture as capture_mod
from app.core import glossary as glossary_mod
from app.core import profiles as profiles_mod
from app.core import regions as regions_mod
from app.core import update as update_mod
from app.core import ocr as ocr_mod
from app.core import translate as translate_mod
from app.core import overlay as overlay_mod
from app.core import hotkeys as hotkeys_mod
from app.core import tray as tray_mod
from app.core import textfilter
from app.ui import mainwindow as mainwindow_mod
from app.ui import theme as ui_theme
from app.ui.bigsubtitle import BigSubtitleController
from app.ui.minipanel import MiniPanelController
from app import __version__ as APP_VERSION
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


def _typewriter_check(prev_state, text, now, debounce_seconds):
    """Harf harf beliren diyalog (typewriter efekti) icin: bir metin
    ONCEKI taramadakinin DEVAMIYSA (onceki metin, yenisinin basiyla
    AYNI), cevirmeyi metin en az debounce_seconds kadar DEGISMEDEN
    kalana kadar geciktirir - aksi halde "H", "He", "Hel", "Hello" gibi
    her ara durum ayri ayri (ve gereksiz yere) cevrilirdi.

    Hic buyume GOZLENMEMIS (statik/tek seferde beliren) bir metin HIC
    GECIKTIRILMEZ - sadece gercekten "buyudugu" gozlenen bir metin
    icin bu bekleme devreye girer.

    (defer, yeni_durum) dondurur: defer=True ise bu turda metni
    CEVIRME/ONBELLEGE BAKMA, yeni_durum'u sakla ve devam et."""
    if prev_state is not None and prev_state["text"] != text and text.startswith(prev_state["text"]):
        return True, {"text": text, "stable_since": now, "growing": True}
    if prev_state is not None and prev_state.get("growing") and prev_state["text"] == text:
        if now - prev_state["stable_since"] < debounce_seconds:
            return True, prev_state
        return False, {"text": text, "stable_since": prev_state["stable_since"], "growing": False}
    return False, {"text": text, "stable_since": now, "growing": False}


# ------------------------------------------- 3.4: kaynak tasarrufu (canli mod)
LIVE_CUTSCENE_CHANGE_RATIO = 0.6  # hucrelerin bu orandan fazlasi degisirse "sinematik" sayilir
LIVE_MAX_INTERVAL_SECONDS = 3.0
LIVE_INTERVAL_GROWTH_FACTOR = 1.5
LIVE_OVERRUN_STREAK_NEEDED = 3  # buyutmeden once gereken ardisik "yavas tur" sayisi


def _is_cutscene_like(changed_count, total_count, ratio=LIVE_CUTSCENE_CHANGE_RATIO):
    """Bir turda hucrelerin COGU birden degismisse (orn. sinematik/sahne
    gecisi), bu kare gercek diyalog degil buyuk olasilikla gorsel bir
    gecis olarak kabul edilip OCR/ceviriye hic gonderilmez - bosu bosuna
    GPU/Ollama yuku binmesin diye."""
    if total_count <= 0:
        return False
    return (changed_count / total_count) >= ratio


def _compute_next_interval(current_interval, elapsed, max_interval, overrun_streak,
                            streak_needed=LIVE_OVERRUN_STREAK_NEEDED,
                            growth_factor=LIVE_INTERVAL_GROWTH_FACTOR):
    """Bir taramanin suresi (elapsed) mevcut araligi (current_interval) asarsa
    ardisik asim sayisini (overrun_streak) bir arttirir; bu sayi
    streak_needed'e ulasinca aralik growth_factor ile buyutulur (max_interval'i
    asmaz) ve sayac sifirlanir - tek seferlik bir yavaslama (orn. gecici bir
    disk/GC takilmasi) yuzunden araligin hemen buyumesi istenmez.

    (yeni_aralik, yeni_overrun_streak, buyudu_mu) dondurur."""
    if elapsed > current_interval:
        overrun_streak += 1
        if overrun_streak >= streak_needed:
            new_interval = min(current_interval * growth_factor, max_interval)
            return new_interval, 0, new_interval > current_interval
        return current_interval, overrun_streak, False
    return current_interval, 0, False


class AppBridge(QtCore.QObject):
    quit_signal = QtCore.pyqtSignal()
    show_window_signal = QtCore.pyqtSignal()
    toggle_mini_signal = QtCore.pyqtSignal()
    ask_google_permission_signal = QtCore.pyqtSignal()
    open_region_selector_signal = QtCore.pyqtSignal()
    toggle_big_subtitle_signal = QtCore.pyqtSignal()
    update_available_signal = QtCore.pyqtSignal(str, str)


INFLIGHT_WAIT_TIMEOUT = 15.0  # bir baskasinin cevirisini bekleme ust siniri (sn)


class _InflightTranslation:
    """Su an surmekte olan tek bir ceviri isini temsil eder. Ayni metni
    bekleyen baska bir cagiran (bkz. Orchestrator._claim_or_join_inflight),
    bu is bitince event tetiklenir ve result alani okunabilir olur."""
    __slots__ = ("event", "result")

    def __init__(self):
        self.event = threading.Event()
        self.result = None


class Orchestrator:
    MODE_NONE = "none"
    MODE_INSTANT = "instant"
    MODE_LIVE = "live"

    def __init__(self, app, config):
        self.app = app
        self.config = config
        # Kaydedilmis MONITOR KIMLIGI (konum+cozunurluk), salt sira
        # numarasindan daha guvenilir: ekran dizilimi onceki oturumdan
        # sonra degismisse (yeni monitor eklenmis/cikarilmis) bile dogru
        # fiziksel ekran bulunur (bkz. capture_mod.resolve_monitor_index).
        resolved_index = capture_mod.resolve_monitor_index(config)
        identity_changed = resolved_index != config.get("capture_monitor_index", 0)
        if identity_changed:
            logger.info(
                "Ekran dizilimi degismis: monitor kimligine gore %s -> %s",
                config.get("capture_monitor_index", 0), resolved_index,
            )
            config["capture_monitor_index"] = resolved_index
        self.capturer = capture_mod.ScreenCapturer(monitor_index=resolved_index)
        new_identity = capture_mod.get_monitor_identity(resolved_index)
        if config.get("capture_monitor_identity") != new_identity:
            config["capture_monitor_identity"] = new_identity
            identity_changed = True
        if identity_changed:
            config_mod.save_config(config)
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
        self._translate_inflight = {}           # metin -> _InflightTranslation
        self._translate_inflight_lock = threading.Lock()
        # Ollama'nin paralel istekleri iyi karsilamadigi gozlenirse (ardisik
        # hata/zaman asimi), gecici olarak tek tek (seri) cevirmeye donulur.
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        # Ollama servisi oyun sirasinda coker/kapanirsa (surum guncellemesi,
        # bellek yetersizligi vb.) kullanici hicbir sey gormeden sessizce
        # cevrilmemeye baslar; bkz. _maybe_recover_ollama.
        self._ollama_recovery_attempted = False

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
        self.bridge.open_region_selector_signal.connect(self._open_region_selector_on_gui_thread)
        self.bridge.toggle_big_subtitle_signal.connect(self._toggle_big_subtitle_on_gui_thread)
        self.bridge.update_available_signal.connect(self._on_update_available_on_gui_thread)
        self.available_update = None  # {"tag_name","html_url"} ya da None
        self.mini_panel = MiniPanelController(config, self)
        self.big_subtitle = BigSubtitleController(config, self)
        self._region_selector = None  # acikken referansi canli tutar

        # ---- oyun bazli profiller (4.1, bkz. _sync_active_profile) ----
        self._active_profile_exe = None       # su an UYGULANMIS profilin exe'si
        self._profile_base_snapshot = None    # profilsiz/"genel" ayarlarin anlik goruntusu
        self._current_foreground_exe = None   # Sahne sayfasinin gosterdigi, on plandaki oyun
        self._profile_poll_stop = threading.Event()
        self._profile_poll_thread = None

        self.hotkeys = hotkeys_mod.HotkeyManager(
            config, self.toggle_instant, self.toggle_live, self.request_quit,
            on_region_select=self.request_open_region_selector,
            on_reveal_press=self.overlay.temporarily_hide_threadsafe,
            on_reveal_release=self.overlay.restore_after_reveal_threadsafe,
        )
        self.tray = tray_mod.TrayApp(
            config,
            status_provider=self._status,
            on_toggle_live=self.toggle_live,
            on_instant=self.toggle_instant,
            on_quit=self.request_quit,
            on_open_window=self.request_show_window,
            on_toggle_mini=self.toggle_mini_panel,
            on_toggle_big_subtitle=self.toggle_big_subtitle,
        )

    def _status(self):
        return {
            "ocr_engine": self.config.get("ocr_engine"),
            "translate_engine": self.config.get("translate_engine"),
            "live_active": self.mode == self.MODE_LIVE,
            "mini_visible": self.mini_panel.is_visible(),
            "big_subtitle_visible": self.big_subtitle.is_visible(),
        }

    def start(self):
        self.hotkeys.start()
        self.tray.start()
        if self.config.get("mini_panel_enabled"):
            self.mini_panel.show()
        if self.config.get("big_subtitle_enabled"):
            self.big_subtitle.show()
        self._profile_poll_thread = threading.Thread(target=self._profile_poll_loop, daemon=True)
        self._profile_poll_thread.start()
        threading.Thread(target=self._check_for_update, daemon=True).start()
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
        # Bir hucre YENIDEN OCR'landiginda (sinyali degistiginde) bir artar.
        # Arka planda suren bir ceviri bitince, bu sayi hala cevirinin
        # basladigi andaki degerle AYNIYSA sonuc ekrana konur; degismisse
        # (hucre bu arada tekrar degismis, YENI bir satir gelmis) eski
        # cevirinin ekrana gec gelip yeni yazinin ustune binmesi onlenir -
        # ama onbellege/akisa yazilmasi hep devam eder (bkz. _submit_live_translation).
        cell_generation = {}
        # Bir hucrede SON GORULEN metinler: ayni hucre ayni metni tekrar
        # tekrar bulursa (orn. komsu bir HUD ogesi titreyip sinyali
        # degistirdigi icin gercekte yazi degismedigi halde yeniden okunursa)
        # akisi (_remember) tekrar tekrar en uste tasimamak icin kullanilir.
        cell_last_texts = {}
        # Harf harf beliren diyalog (typewriter efekti) icin buyume takibi
        # (bkz. _typewriter_check): idx -> {"text","stable_since","growing"}.
        cell_growth = {}
        cell_lock = threading.Lock()
        grid = None
        frame_h = frame_w = None

        # ---- 3.4: kaynak tasarrufu ----
        auto_pause_enabled = self.config.get("live_auto_pause_enabled", True)
        cutscene_skip_enabled = self.config.get("live_cutscene_skip_enabled", True)
        # Oyunun .exe'si: canli mod ACILDIGI anda on planda olan pencereden
        # tahmin edilir (oyuncu F10'a basarken oyunun icinde oldugu varsayilir).
        # Henuz oyun bazli profil (bkz. 4.1) olmadigi icin en iyi tahmin bu.
        game_exe = activity_mod.get_foreground_exe_name()
        own_exe = activity_mod.own_exe_name()
        was_paused = False
        overrun_streak = 0

        while not self._live_stop_event.is_set():
            t0 = time.time()

            if auto_pause_enabled:
                fg_exe = activity_mod.get_foreground_exe_name()
                idle_seconds = activity_mod.get_idle_seconds()
                if activity_mod.should_pause_live(fg_exe, idle_seconds, game_exe, own_exe,
                                                   auto_pause_enabled):
                    if not was_paused:
                        logger.info(
                            "Canli mod duraklatildi (oyun arka planda ya da sistem bosta).")
                        was_paused = True
                    time.sleep(interval)
                    continue
                if was_paused:
                    logger.info("Canli mod devam ediyor.")
                    was_paused = False

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

            # Degisim tespiti HUCRENIN KENDI sinirlariyla yapilir (ritim/performans
            # icin), ama OCR'a gonderilen kirpma bu sinirin disina da tasar
            # (padding). Boylece hucre sinirina denk gelen bir kelime
            # ("HELLO WORLD" gibi) ikiye bolunup anlamsiz parcalara ayrilmaz;
            # her iki komsu hucre de kelimenin TAMAMINI gorur.
            changed_cells = []
            for idx, cell in enumerate(grid):
                sig = capture_mod.cell_signature(frame, cell)
                if capture_mod.signature_changed(cell_signatures.get(idx), sig):
                    changed_cells.append((idx, cell, sig))

            # "cell_signatures bos" ILK tur anlamina gelir (hucrelerin HEPSI
            # o an "degismis" sayilir, cunku henuz onceki bir referans yok) -
            # bu durumda sinematik atlamasi UYGULANMAZ, aksi halde canli mod
            # her acildiginda ilk kare hic OCR'lanmadan atlanirdi.
            if (cell_signatures and cutscene_skip_enabled
                    and _is_cutscene_like(len(changed_cells), len(grid))):
                # Hucrelerin COGU birden degismis - gercek diyalog degil buyuk
                # olasilikla sinematik/sahne gecisi. OCR/ceviriye hic
                # gonderme, ama imzalari guncelle ki gecis bitince normal
                # degisim tespiti dogru calissin.
                for idx, _cell, sig in changed_cells:
                    cell_signatures[idx] = sig
                prev_frame = frame
                logger.info(
                    "Buyuk ekran degisimi (sinematik olabilir), bu kare atlandi (%d/%d hucre degisti).",
                    len(changed_cells), len(grid),
                )
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

            for idx, cell, sig in changed_cells:
                any_change = True
                cell_signatures[idx] = sig
                generation = cell_generation.get(idx, 0) + 1
                cell_generation[idx] = generation
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

                cached_boxes, cache_hits, pending = self._live_process_cell(
                    idx, survivors, source_lang, target_lang, engine_pref,
                    context_lines, generation, cell_generation, cell_boxes,
                    cell_last_texts, cell_lock, cell_growth,
                )
                tick_cache_hits += cache_hits
                tick_pending += pending

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

            elapsed = time.time() - t0
            interval, overrun_streak, grew = _compute_next_interval(
                interval, elapsed, LIVE_MAX_INTERVAL_SECONDS, overrun_streak)
            if grew:
                logger.warning(
                    "Taramalar yavas kaliyor (%.2f sn), tarama araligi %.2f sn'ye buyutuldu.",
                    elapsed, interval,
                )
            self._sleep_remaining(t0, interval)

        logger.info("Canli mod dongusu sonlandi.")

    def _live_process_cell(self, idx, survivors, source_lang, target_lang, engine_pref,
                            context_lines, generation, cell_generation, cell_boxes,
                            cell_last_texts, cell_lock, cell_growth):
        """Bir hucrenin OCR sonuclarini isler: onbellekten bulunanlar hemen
        kutu listesine eklenir, bulunamayanlar arka planda cevrilmeye
        yollanir (bkz. _submit_live_translation). Donen deger:
        (cached_boxes, cache_hits, pending_count).

        Ayni hucre ayni metni ONCEDEN de gostermisse (orn. komsu bir HUD
        ogesi titreyip sinyali degistirdigi icin yazi degismedigi halde
        yeniden okunduysa), akis (_remember) tekrar tekrar en uste
        tasinmaz - zaman kodu sadece metin bu hucrede YENI belirdiginde
        guncellenir.

        Harf harf beliren diyalog (typewriter efekti) icin: metnin
        BUYUDUGU gozlenirse (bkz. _typewriter_check), metin en az
        "live_typewriter_debounce_ms" kadar DEGISMEDEN kalana kadar
        cevrilmez - ara durumlar ("H", "He", "Hel"...) bosa cevrilmez."""
        prev_texts = cell_last_texts.get(idx, set())
        cell_last_texts[idx] = {res.text for res in survivors}

        debounce_seconds = max(0, int(self.config.get("live_typewriter_debounce_ms", 400))) / 1000.0
        now = time.time()

        cached_boxes = []
        cache_hits = 0
        pending = 0
        for res in survivors:
            if debounce_seconds > 0:
                defer, new_state = _typewriter_check(cell_growth.get(idx), res.text, now, debounce_seconds)
                cell_growth[idx] = new_state
                if defer:
                    continue
            cached = self.translator.cache.get(res.text, source_lang, target_lang, engine_pref)
            if cached is not None:
                cache_hits += 1
                cached_boxes.append(self._make_box(res, cached))
                if res.text not in prev_texts:
                    self._remember(res.text, cached)
            else:
                pending += 1
                self._submit_live_translation(
                    res, idx, generation, cell_generation, cell_boxes, cell_lock, context_lines,
                )
        return cached_boxes, cache_hits, pending

    def _submit_live_translation(self, result, idx, generation, cell_generation,
                                  cell_boxes, cell_lock, context_lines):
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
            # Akisa (ve translate() icinde zaten onbellege) HER ZAMAN
            # yazilir - geciken bir ceviri bile olsa kullanicinin akista/
            # mini panelde goremedigi bir satir olmamali.
            self._remember(result.text, translated)
            if cell_generation.get(idx) != generation:
                # Bu hucre, bu ceviri surerken BASKA bir satiriyla tekrar
                # degisti; eski sonucu simdi ekrana koymak yeni yazinin
                # ustune binmesine yol acardi - sadece EKRANA koymaktan
                # vazgeciyoruz (akis/onbellek zaten yukarida guncellendi).
                return
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
        deger olmayanlari (cok kisa/sembol/dusuk guven/zaten Turkce/
        kullanicinin disarida tuttugu bolgede olan) eler."""
        ocr_results = self.ocr_manager.recognize(frame_bgr, offset=offset)
        ocr_results = ocr_mod.merge_paragraph_lines(ocr_results)
        exclude_regions = self.config.get("exclude_regions") or []
        include_regions = self.config.get("include_regions") or []
        if exclude_regions or include_regions:
            ocr_results = [
                r for r in ocr_results
                if not regions_mod.is_bbox_excluded(r.bbox, exclude_regions, include_regions)
            ]
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
        """Ayni metin birden fazla yerden (orn. ortusen iki hucreden, veya
        canli mod ile aninda tarama ayni anda) cevrilmeye calisiliyorsa,
        sadece ilkine (True) izin verir. Ikinci cagiran, bu cevirinin
        SONUCUNU _claim_or_join_inflight() uzerinden bekleyebilir (bkz.
        _translate_all_blocking); canli mod gibi bekleyemeyen cagiranlar
        sadece False'u gorup atlar."""
        owner, _task = self._claim_or_join_inflight(text)
        return owner

    def _claim_or_join_inflight(self, text):
        """Metin henuz cevrilmiyorsa sahipligi alir (True, gorev) doner;
        zaten cevriliyorsa VAROLAN gorevin dogrudan referansini (False,
        gorev) olarak doner - cagiran bu gorevin event'ini bekleyip
        sonucunu okuyabilir. Tek bir kilit altinda yapildigi icin
        "sahiplik kontrolu" ile "varolan gorevi alma" arasinda yarisa
        (baskasinin bu arada isi bitirip gorevi kaldirmasina) acik degildir."""
        with self._translate_inflight_lock:
            existing = self._translate_inflight.get(text)
            if existing is not None:
                return False, existing
            task = _InflightTranslation()
            self._translate_inflight[text] = task
            return True, task

    def _release_inflight(self, text, result=None):
        with self._translate_inflight_lock:
            task = self._translate_inflight.pop(text, None)
        if task is not None:
            task.result = result
            task.event.set()

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
                self._ollama_recovery_attempted = False
            else:
                self._translate_consecutive_failures += 1
                failures = self._translate_consecutive_failures
        if not translated:
            self._maybe_recover_ollama(failures)
        return translated

    def _maybe_recover_ollama(self, failures):
        """Ollama ardisik ~5 defa cevap vermezse (surecin kendisi coktu/
        kapandi varsayimiyla) arka planda bir kez yeniden baslatmayi dener.
        Kullanicinin oyunu birakip gelip programi yeniden baslatmasini
        beklemek yerine servisi kendisi ayaga kaldirmaya calisir."""
        if failures < 5 or self._quitting:
            return
        if self.config.get("translate_engine") != "ollama":
            return
        with self._translate_fail_lock:
            if self._ollama_recovery_attempted:
                return
            self._ollama_recovery_attempted = True

        def worker():
            logger.warning(
                "Ollama ust uste %d cevap vermedi, yeniden baslatilmaya calisiliyor...",
                failures,
            )
            if ensure_ollama_running(self.translator.ollama.host):
                logger.info("Ollama yeniden baslatildi.")
            else:
                logger.error("Ollama yeniden baslatilamadi; elle kontrol gerekebilir.")

        threading.Thread(target=worker, daemon=True).start()

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

        pending = []     # (result, task) - BIZ cevirecegiz
        joined = []       # (result, task) - BASKASI (orn. canli mod) zaten cevirmekte; sonucunu bekleyecegiz
        for r in results:
            cached = self.translator.cache.get(r.text, source_lang, target_lang, engine_pref)
            if cached is not None:
                cache_hits += 1
                boxes.append(self._make_box(r, cached))
                continue
            is_owner, task = self._claim_or_join_inflight(r.text)
            if is_owner:
                pending.append((r, task))
            else:
                joined.append((r, task))

        futures = {}
        for r, task in pending:
            t0 = time.time()
            fut = self._translate_executor.submit(self._translate_one, r.text, context_lines)
            futures[fut] = (r, task, t0)

        for fut in concurrent.futures.as_completed(futures):
            r, task, t0 = futures[fut]
            try:
                translated = fut.result()
            except Exception as exc:
                logger.warning("Ceviri is parcacigi hata verdi: %s", exc)
                translated = None
            finally:
                self._release_inflight(r.text, translated)
            durations.append(time.time() - t0)
            if translated:
                self._remember(r.text, translated)
                boxes.append(self._make_box(r, translated))

        # Baska bir yerden (tipik olarak canli mod) ayni anda cevrilmekte
        # olan satirlar: eskiden burada sessizce ATLANIYORDU (F9 aninda
        # taramasinda o satir hic gorunmuyordu). Artik o cevirinin
        # sonucunu bekleyip KULLANIYORUZ.
        for r, task in joined:
            t0 = time.time()
            if task.event.wait(timeout=INFLIGHT_WAIT_TIMEOUT):
                translated = task.result
                durations.append(time.time() - t0)
                if translated:
                    boxes.append(self._make_box(r, translated))
            else:
                logger.warning(
                    "Baska bir cevirinin bitmesi beklenirken zaman asimi: %r", r.text[:60],
                )

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

    # ------------------------------------------------ elle ceviri duzeltme
    def _cache_identity(self):
        """Onbellek anahtarinin dil/motor kismini (su anki ayarlara gore)
        dondurur - elle duzeltme de NORMAL cevirilerle AYNI anahtar
        semasini kullanmali ki get() onu dogru bulsun."""
        return (
            self.config.get("source_lang", "auto"),
            self.config.get("target_lang", "tr"),
            self.config.get("translate_engine", "ollama"),
        )

    def correct_translation(self, original, corrected):
        """Kullanicinin Sahne sayfasindaki akistan "Çeviriyi düzelt" ile
        elle girdigi ceviri. Onbellege KALICI olarak (hicbir motor
        tarafindan ezilmeyecek sekilde) yazilir ve akista hemen gorunur."""
        corrected = (corrected or "").strip()
        if not corrected:
            return False
        source_lang, target_lang, engine_pref = self._cache_identity()
        self.translator.cache.set_manual(original, source_lang, target_lang, engine_pref, corrected)
        self._remember(original, corrected)
        return True

    def undo_correction(self, original):
        """"Düzeltmeyi geri al": kullanicinin elle yazdigi metin akista
        kalir, ama bundan sonra motorlar bu satiri yeniden cevirip
        uzerine yazabilir."""
        source_lang, target_lang, engine_pref = self._cache_identity()
        self.translator.cache.clear_manual(original, source_lang, target_lang, engine_pref)

    def is_manually_corrected(self, original):
        source_lang, target_lang, engine_pref = self._cache_identity()
        return self.translator.cache.is_manual(original, source_lang, target_lang, engine_pref)

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
        self.config["capture_monitor_identity"] = capture_mod.get_monitor_identity(index)
        config_mod.save_config(self.config)
        logger.info("Yakalanacak monitor degistirildi: %s", index)
        return True

    # --------------------------------------------------------------- F11
    def request_quit(self):
        logger.info("Cikis istendi, kapatiliyor...")
        self._quitting = True
        with self._mode_lock:
            self._stop_live_locked()
        self._profile_poll_stop.set()
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
        try:
            self.capturer.close()
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
        try:
            if self.big_subtitle.panel is not None:
                self.big_subtitle.panel.hide()
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

    # ------------------------------------------------- buyuk altyazi (4.3)
    def toggle_big_subtitle(self):
        """Herhangi bir thread'den cagrilabilir (tepsi menusu ayri thread'de)."""
        self.bridge.toggle_big_subtitle_signal.emit()

    def _toggle_big_subtitle_on_gui_thread(self):
        self.big_subtitle.toggle()
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

    # --------------------------------------------------- bolge secimi (3.5)
    def request_open_region_selector(self):
        """Herhangi bir thread'den cagrilabilir (kisayol kancasi ayri
        thread'de calisir) - QWidget'lar sadece GUI thread'inde olusturulabilir."""
        self.bridge.open_region_selector_signal.emit()

    def _open_region_selector_on_gui_thread(self):
        if self._region_selector is not None:
            self._region_selector.raise_()
            self._region_selector.activateWindow()
            return
        from app.ui.regionoverlay import RegionSelectorOverlay
        self._region_selector = RegionSelectorOverlay(
            self.config.get("exclude_regions") or [],
            self.config.get("include_regions") or [],
            on_done=self._save_regions,
        )
        self._region_selector.destroyed.connect(self._clear_region_selector_ref)
        self._region_selector.showFullScreen()

    def _clear_region_selector_ref(self, *_):
        self._region_selector = None

    def _save_regions(self, exclude_regions, include_regions):
        self.config["exclude_regions"] = exclude_regions
        self.config["include_regions"] = include_regions
        config_mod.save_config(self.config)
        logger.info(
            "Okuma bolgeleri guncellendi: %d disarida tutulan, %d sadece-okunan bolge.",
            len(exclude_regions), len(include_regions),
        )

    # ------------------------------------------------------- oyun profilleri (4.1)
    def _profile_poll_loop(self):
        """Canli/aninda modun calisip calismadigindan BAGIMSIZ, duzenli
        araliklarla on plandaki pencereyi kontrol edip gerekirse profil
        degistirir - boylece F9/F10'a hic basilmasa da, oyunlar arasi
        gecis yapildiginda dogru profil hazir olur."""
        while not self._profile_poll_stop.is_set():
            try:
                fg_exe = activity_mod.get_foreground_exe_name()
                # Kullanici kendi kontrol paneline/mini panele gecince bu bir
                # "oyun degisimi" sayilmaz: son gorulen oyun ve onun profili
                # korunur (aksi halde "Profili kaydet" profili programin
                # kendisine kaydederdi ve panelde oyunun ayarlari gorunmezdi).
                if fg_exe and fg_exe != activity_mod.own_exe_name():
                    self._current_foreground_exe = fg_exe
                    self._sync_active_profile(fg_exe)
            except Exception as exc:
                logger.error("Oyun profili senkronizasyonu hata verdi: %s", exc)
            self._profile_poll_stop.wait(profiles_mod.POLL_INTERVAL_SECONDS)

    def _sync_active_profile(self, fg_exe):
        enabled = self.config.get("game_profiles_enabled", True)
        game_profiles = self.config.get("game_profiles", {})
        target_exe = profiles_mod.resolve_target_exe(fg_exe, game_profiles, enabled)
        live_snapshot = {k: self.config.get(k) for k in profiles_mod.PROFILE_KEYS}

        new_active, new_base, values = profiles_mod.compute_profile_sync(
            self._active_profile_exe, target_exe, game_profiles,
            self._profile_base_snapshot, live_snapshot,
        )
        self._active_profile_exe = new_active
        self._profile_base_snapshot = new_base
        if values is not None:
            self.config.update(values)
            raw_glossary = game_profiles.get(new_active, {}).get("glossary") if new_active else None
            self.translator.active_profile_glossary = (
                glossary_mod._validate_entries(raw_glossary) if raw_glossary else None
            )
            logger.info("Oyun profili degisti: %s", new_active or "(genel ayarlar)")

    def save_current_as_profile(self, exe_name):
        """Su anki (canli) OCR motoru/dili, overlay stili, okuma bolgeleri
        ve sozlugu bu oyun icin bir profil olarak kaydeder/gunceller."""
        if not exe_name:
            return False
        game_profiles = self.config.setdefault("game_profiles", {})
        current_glossary = self.translator.active_profile_glossary or glossary_mod.load_glossary()
        game_profiles[exe_name] = profiles_mod.build_profile_from_config(self.config, current_glossary)
        config_mod.save_config(self.config)
        logger.info("'%s' icin oyun profili kaydedildi.", exe_name)
        return True

    def delete_profile(self, exe_name):
        game_profiles = self.config.get("game_profiles", {})
        if exe_name not in game_profiles:
            return False
        del game_profiles[exe_name]
        config_mod.save_config(self.config)
        logger.info("'%s' icin oyun profili silindi.", exe_name)
        if self._active_profile_exe == exe_name:
            # game_profiles'tan silinmis olmasi, resolve_target_exe'nin bir
            # sonraki cagrida None donmesini (ve boylece compute_profile_sync'in
            # "genel ayarlara don" yolunu almasini) saglar - _active_profile_exe
            # BURADA elle None'a cekilMEZ, aksi halde "degisiklik yok" sanilip
            # degerler asla geri yuklenmezdi.
            self._sync_active_profile(self._current_foreground_exe)
        return True

    def set_game_profiles_enabled(self, enabled):
        self.config["game_profiles_enabled"] = bool(enabled)
        config_mod.save_config(self.config)
        self._sync_active_profile(self._current_foreground_exe)

    # --------------------------------------------------------- surum kontrolu (5.2)
    def _check_for_update(self):
        """Programin ACILISINDA bir kez (daemon thread, GUI'yi bloklamaz)
        cagrilir. GitHub Releases'e EN FAZLA gunde bir kez bakar (bkz.
        update_mod.should_check_now) - her acilista internete gitmez."""
        try:
            release, new_checked_at = update_mod.check_for_update(
                APP_VERSION, self.config.get("last_update_check_at"), time.time())
            if new_checked_at != self.config.get("last_update_check_at"):
                self.config["last_update_check_at"] = new_checked_at
                config_mod.save_config(self.config)
            if release:
                logger.info("Yeni surum bulundu: %s", release["tag_name"])
                self.available_update = release
                self.bridge.update_available_signal.emit(release["tag_name"], release["html_url"])
                try:
                    self.tray.notify(
                        f"Yeni surum mevcut: {release['tag_name']}", title="Oyun Çevirmen")
                except Exception:
                    pass
        except Exception as exc:
            logger.error("Surum kontrolu hata verdi: %s", exc)

    def _on_update_available_on_gui_thread(self, tag_name, html_url):
        if self.main_window is not None:
            self.main_window.show_update_available(tag_name, html_url)

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
