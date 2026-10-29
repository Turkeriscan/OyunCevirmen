"""
Kontrol paneli penceresi: cerceve + yan menu + sayfalar + ilk acilis rehberi.

Sayfalar ayarlari load(cfg)/save(cfg) ile okur/yazar; bu pencere hepsini
tek bir config sozlugunde (calisan programla paylasilan ayni nesne) toplar,
diske yazar ve gerekiyorsa kisayollari yeniden kaydeder.

Pencere kapatilinca (X) program KAPANMAZ, sistem tepsisine gizlenir.
"""
import base64
import contextlib
import logging
import subprocess
import threading
import time

from PyQt6 import QtCore, QtGui, QtWidgets

from app import config as config_mod
from app.ui import icons
from app.ui import theme as T
from app.ui.frame import FramelessWindow
from app.ui.onboarding import Onboarding
from app.ui.pages.advanced import AdvancedPage
from app.ui.pages.appearance import AppearancePage
from app.ui.pages.hotkeys import HotkeysPage
from app.ui.pages.log import LogPage
from app.ui.pages.scene import ScenePage, timecode
from app.ui.pages.translation import TranslationPage
from app.ui.theme import px
from app.ui.widgets import FadeStack, IconButton, hotkey_text, label, text_button

logger = logging.getLogger("OyunCevirmen.mainwindow")

CREATE_NO_WINDOW = 0x08000000
OCR_SHORT = {"windows": "Windows OCR", "easyocr": "EasyOCR", "paddle": "PaddleOCR"}
LANG_SHORT = {"auto": "otomatik dil", "en": "İngilizce", "de": "Almanca", "fr": "Fransızca",
              "es": "İspanyolca", "it": "İtalyanca", "pt": "Portekizce", "ru": "Rusça",
              "ja": "Japonca", "ko": "Korece", "zh-cn": "Çince"}

NAV = [
    ("scene", "Sahne"),
    ("translate", "Çeviri"),
    ("appearance", "Görünüm"),
    ("keyboard", "Kısayollar"),
    ("sliders", "Gelişmiş"),
    ("log", "Günlük"),
]
LOG_INDEX = 5


class RailButton(QtWidgets.QPushButton):
    def __init__(self, icon_name, text, parent=None):
        super().__init__("  " + text, parent)
        self.setObjectName("RailButton")
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setIcon(icons.icon(icon_name, T.MUTED, 18, T.PAPER))
        self.setIconSize(QtCore.QSize(px(18), px(18)))
        self.setAccessibleName(text)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.isChecked():
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(T.SUB))
            h = px(16)
            p.drawRoundedRect(QtCore.QRectF(px(10), (self.height() - h) / 2, px(3), h), 1.5, 1.5)
            p.end()


class _Bridge(QtCore.QObject):
    status = QtCore.pyqtSignal(dict)


class MainWindow(FramelessWindow):
    def __init__(self, config, orchestrator):
        super().__init__()
        T.load_fonts()
        T.init_scale()
        self.config = config  # canli, paylasilan config sozlugu (ayni referans)
        self.orchestrator = orchestrator
        self.started_at = getattr(orchestrator, "started_at", time.time())
        self._loading = 0
        self._status_busy = False
        self._hotkeys_paused = False

        self.setWindowTitle("Oyun Çevirmen")
        self.setWindowIcon(QtGui.QIcon(str(T.ASSET_DIR + "/icon.ico")))
        self.setMinimumSize(px(1040), px(680))
        self.setStyleSheet(T.stylesheet())

        self._bridge = _Bridge()
        self._bridge.status.connect(self._apply_status)
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._apply_and_save)

        self._build()
        self._restore_geometry()

        with self.loading():
            for page in self.settings_pages:
                page.load(self.config)
        self.translation.refresh_models()
        self.translation.refresh_model_recommendation()

        self._fast = QtCore.QTimer(self)
        self._fast.timeout.connect(self._refresh_fast)
        self._fast.start(250)
        self._slow = QtCore.QTimer(self)
        self._slow.timeout.connect(self.refresh_status)
        self._slow.start(3000)
        self._log_timer = QtCore.QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(2000)

        if not self.config.get("onboarding_done", False):
            self.show_onboarding()
        self._refresh_fast()

    # ============================================================ yapim
    def _build(self):
        tb = self.title_bar
        self.btn_mini = IconButton("pip", "Mini paneli göster / gizle", 17, checkable=True)
        self.btn_mini.clicked.connect(self._toggle_mini)
        tb.extra.addWidget(self.btn_mini)

        self.btn_big_subtitle = IconButton(
            "monitor", "Büyük altyazı penceresi (2. monitor, tam ekran oyunlar için)", 17,
            checkable=True)
        self.btn_big_subtitle.clicked.connect(self._toggle_big_subtitle)
        tb.extra.addWidget(self.btn_big_subtitle)

        for key, title in (("engine", "Çeviri"), ("ocr", "Okuma"), ("gpu", "Ekran kartı"), ("cache", "Hafıza")):
            self.credits.add_item(key, title)

        body = QtWidgets.QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        self.root_stack = QtWidgets.QStackedWidget()
        body.addWidget(self.root_stack)

        main = QtWidgets.QWidget()
        ml = QtWidgets.QHBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        ml.addWidget(self._build_rail())

        self.stack = FadeStack()
        self.scene = ScenePage(self)
        self.translation = TranslationPage(self)
        self.appearance = AppearancePage(self)
        self.hotkeys = HotkeysPage(self)
        self.advanced = AdvancedPage(self)
        self.log = LogPage(self)
        for page in (self.scene, self.translation, self.appearance, self.hotkeys, self.advanced, self.log):
            self.stack.addWidget(page)
        self.settings_pages = [self.translation, self.appearance, self.hotkeys, self.advanced]
        ml.addWidget(self.stack, 1)
        self.root_stack.addWidget(main)

        self.onboarding = Onboarding(self)
        self.onboarding.finished.connect(self._onboarding_done)
        self.root_stack.addWidget(self.onboarding)

        self.nav[0].setChecked(True)

    def _build_rail(self):
        rail = QtWidgets.QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(px(212))
        lay = QtWidgets.QVBoxLayout(rail)
        lay.setContentsMargins(0, px(18), 0, px(16))
        lay.setSpacing(px(2))

        self.nav_group = QtWidgets.QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav = []
        for i, (icon_name, text) in enumerate(NAV):
            b = RailButton(icon_name, text)
            self.nav_group.addButton(b, i)
            self.nav.append(b)
            lay.addWidget(b)
            if i == 0:
                lay.addSpacing(px(14))
                cap = label("Ayarlar", "RailFootnote")
                cap.setContentsMargins(px(24), 0, 0, px(4))
                lay.addWidget(cap)
        self.nav_group.idClicked.connect(self.go_to)
        lay.addStretch(1)

        foot = QtWidgets.QVBoxLayout()
        foot.setContentsMargins(px(14), 0, px(14), 0)
        foot.setSpacing(px(8))
        quit_btn = text_button("Programı kapat", "Quiet", "cross")
        quit_btn.setToolTip("Oyun Çevirmen tamamen kapanır; kısayollar da çalışmaz.")
        quit_btn.clicked.connect(self.orchestrator.request_quit)
        foot.addWidget(quit_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        note = label("Pencereyi kapatırsan program saatin yanında çalışmaya devam eder.", "RailFootnote", wrap=True)
        note.setContentsMargins(px(10), 0, 0, 0)
        foot.addWidget(note)
        lay.addLayout(foot)
        return rail

    def go_to(self, index):
        self.nav[index].setChecked(True)
        self.stack.fade_to(index)
        if index == LOG_INDEX:
            self.log.refresh()

    def keyPressEvent(self, e):
        # Ctrl+1..6 ile sayfalar arasinda gezinme
        if e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier and \
                QtCore.Qt.Key.Key_1 <= e.key() <= QtCore.Qt.Key.Key_6:
            self.go_to(e.key() - QtCore.Qt.Key.Key_1)
            return
        super().keyPressEvent(e)

    # ============================================================ rehber
    def show_onboarding(self):
        self.onboarding.restart()
        self.root_stack.setCurrentWidget(self.onboarding)

    def _onboarding_done(self):
        self.root_stack.setCurrentIndex(0)
        self.go_to(0)

    # ====================================================== ctx arayuzu
    @contextlib.contextmanager
    def loading(self):
        self._loading += 1
        try:
            yield
        finally:
            self._loading -= 1

    def is_loading(self):
        return self._loading > 0

    def schedule_save(self, *_):
        if self._loading:
            return
        self._save_timer.start(450)

    def apply_now(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._apply_and_save()

    def save_now(self):
        config_mod.save_config(self.config)

    def flash(self, text):
        self.credits.flash(text)

    def toggle_instant(self):
        self.orchestrator.toggle_instant()
        QtCore.QTimer.singleShot(120, self._refresh_fast)

    def toggle_live(self):
        self.orchestrator.toggle_live()
        QtCore.QTimer.singleShot(120, self._refresh_fast)

    def pause_hotkeys(self):
        try:
            self.orchestrator.hotkeys.stop()
            self._hotkeys_paused = True
        except Exception:
            pass

    def resume_hotkeys(self):
        if self._hotkeys_paused:
            self._hotkeys_paused = False
            try:
                self.orchestrator.hotkeys.start()
            except Exception as exc:
                logger.error("Kisayollar yeniden baslatilamadi: %s", exc)

    def clear_cache(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Çeviri hafızasını sil")
        box.setText("Kaydedilmiş tüm çeviriler silinecek; oyundaki yazılar yeniden çevrilecek.")
        box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Cancel)
        sil = box.addButton("Hafızayı sil", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        box.setStyleSheet(T.stylesheet("QMessageBox"))
        box.exec()
        if box.clickedButton() is not sil:
            return
        try:
            self.orchestrator.translator.cache.clear()
            self.flash("Çeviri hafızası silindi")
        except Exception as exc:
            logger.error("Onbellek temizlenemedi: %s", exc)
        self.refresh_status()

    def reset_defaults(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Varsayılana döndür")
        box.setText("Tüm ayarlar ilk kurulumdaki haline dönecek. Çeviri hafızan silinmez.")
        box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Cancel)
        ok = box.addButton("Varsayılana döndür", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        box.setStyleSheet(T.stylesheet("QMessageBox"))
        box.exec()
        if box.clickedButton() is not ok:
            return
        keep = {k: self.config.get(k) for k in ("onboarding_done", "window_geometry", "mini_panel_pos")}
        self.config.clear()
        self.config.update(config_mod.DEFAULT_CONFIG)
        self.config.update({k: v for k, v in keep.items() if v is not None})
        config_mod.save_config(self.config)
        with self.loading():
            for page in self.settings_pages:
                page.load(self.config)
        try:
            self.orchestrator.hotkeys.start()
        except Exception:
            pass
        try:
            self.orchestrator.reset_google_permission_prompt()
        except Exception:
            pass
        self.flash("Varsayılan ayarlara dönüldü")

    # ========================================================= kaydetme
    def _apply_and_save(self):
        cfg = self.config
        keys = ("hotkey_instant", "hotkey_live_toggle", "hotkey_quit")
        old = tuple(cfg.get(k) for k in keys)
        for page in self.settings_pages:
            page.save(cfg)
        config_mod.save_config(cfg)
        if tuple(cfg.get(k) for k in keys) != old and not self._hotkeys_paused:
            try:
                self.orchestrator.hotkeys.start()
                logger.info("Kisayollar yeniden kaydedildi: %s", [cfg.get(k) for k in keys])
            except Exception as exc:
                logger.error("Kisayollar yeniden kaydedilemedi: %s", exc)
        try:
            self.orchestrator.overlay.refresh()
        except Exception:
            pass
        self.flash("Kaydedildi")
        self.refresh_status()

    # ============================================================ durum
    def _refresh_fast(self):
        if not self.isVisible():
            return
        o = self.orchestrator
        mode = getattr(o, "mode", "none")
        hk_i = self.config.get("hotkey_instant", "f9")
        hk_l = self.config.get("hotkey_live_toggle", "f10")
        tb = self.title_bar
        if mode == "live":
            tb.lamp.set_state("rec")
            tb.state.setText("Canlı mod")
            start = getattr(o, "live_started_at", None)
            tb.timer.setText(timecode(time.time() - start, millis=False) if start else "")
        elif mode == "instant":
            tb.lamp.set_state("sub")
            tb.state.setText("Çeviriler ekranda")
            tb.timer.setText("")
        else:
            tb.lamp.set_state("off")
            tb.state.setText("Beklemede")
            tb.timer.setText("")
        tb.state.setToolTip(f"{hotkey_text(hk_i)}: anında tara    {hotkey_text(hk_l)}: canlı mod")
        mini = getattr(o, "mini_panel", None)
        self.btn_mini.setChecked(bool(mini and mini.is_visible()))
        big_subtitle = getattr(o, "big_subtitle", None)
        self.btn_big_subtitle.setChecked(bool(big_subtitle and big_subtitle.is_visible()))
        if self.stack.currentIndex() == 0:
            self.scene.refresh(mode, hk_i, hk_l)

    def refresh_status(self):
        if not self.isVisible() or self._status_busy:
            return
        self._status_busy = True
        threading.Thread(target=self._collect_status, daemon=True).start()

    def _collect_status(self):
        info = {}
        o = self.orchestrator
        try:
            info["ollama"] = bool(o.translator.ollama.is_available())
        except Exception:
            info["ollama"] = False
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                creationflags=CREATE_NO_WINDOW, timeout=3,
            ).decode("utf-8", "ignore").strip().splitlines()[0]
            name, used, total, util = [x.strip() for x in out.split(",")]
            info["gpu"] = (name.replace("NVIDIA ", "").replace("GeForce ", ""),
                           float(used), float(total), int(float(util)))
        except Exception:
            info["gpu"] = None
        try:
            info["cache"] = o.translator.cache.count()
        except Exception:
            info["cache"] = None
        self._bridge.status.emit(info)

    def _apply_status(self, info):
        self._status_busy = False
        cfg = self.config
        if cfg.get("translate_engine", "ollama") == "ollama":
            if info.get("ollama"):
                self.credits.set_item("engine", f"Ollama, {cfg.get('ollama_model', '')}", "ok",
                                      "Çeviriler bilgisayarında yapılıyor.")
            else:
                allowed = cfg.get("allow_google_fallback")
                if allowed is True:
                    self.credits.set_item("engine", "Google Translate (Ollama kapalı)", "sub",
                                          "Ollama çalışmadığı için yedek motor kullanılıyor.")
                elif allowed is False:
                    self.credits.set_item("engine", "Çeviri yapılamıyor", "bad",
                                          "Ollama kapalı ve Google Translate iznin yok. "
                                          "Çeviri sayfasından izin verebilirsin.")
                else:
                    self.credits.set_item("engine", "Çeviri yapılamıyor", "bad",
                                          "Ollama kapalı. Google Translate'e izin verip "
                                          "vermeyeceğin sorulacak.")
        else:
            self.credits.set_item("engine", "Google Translate", "ok", "İnternet bağlantısı gerekir.")
        self.credits.set_item("ocr", f"{OCR_SHORT.get(cfg.get('ocr_engine'), cfg.get('ocr_engine'))}, "
                                     f"{LANG_SHORT.get(cfg.get('source_lang', 'auto'), cfg.get('source_lang'))}",
                              "ok")
        gpu = info.get("gpu")
        if gpu:
            name, used, total, util = gpu
            self.credits.set_item("gpu", f"{name}, {f'{used / 1024:.1f}'.replace('.', ',')} / "
                                         f"{total / 1024:.0f} GB", "ok",
                                  f"Yük: %{util}")
        else:
            self.credits.set_item("gpu", "bilgi yok", "off", "NVIDIA sürücüsü bulunamadı.")
        n = info.get("cache")
        self.credits.set_item("cache", "?" if n is None else f"{n:,} çeviri".replace(",", "."),
                              "ok" if n else "off", "Tekrar gelen yazılar anında çevrilir.")
        self.advanced.set_cache_count(n)

    def _refresh_log(self):
        if self.isVisible() and self.stack.currentIndex() == LOG_INDEX:
            self.log.refresh()

    # ======================================================== mini panel
    def _toggle_mini(self):
        o = self.orchestrator
        if hasattr(o, "toggle_mini_panel"):
            o.toggle_mini_panel()
        QtCore.QTimer.singleShot(50, self._refresh_fast)

    # ================================================= buyuk altyazi (4.3)
    def _toggle_big_subtitle(self):
        o = self.orchestrator
        if hasattr(o, "toggle_big_subtitle"):
            o.toggle_big_subtitle()
        QtCore.QTimer.singleShot(50, self._refresh_fast)

    # ====================================================== pencere
    def _restore_geometry(self):
        raw = self.config.get("window_geometry")
        if raw:
            try:
                if self.restoreGeometry(QtCore.QByteArray(base64.b64decode(raw))):
                    return
            except Exception:
                pass
        self.resize(px(1200), px(760))
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center() - self.rect().center())

    def _remember_geometry(self):
        try:
            self.config["window_geometry"] = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
            config_mod.save_config(self.config)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_fast()
        self.refresh_status()

    def closeEvent(self, event):
        self.apply_now()
        self._remember_geometry()
        event.ignore()
        self.hide()
