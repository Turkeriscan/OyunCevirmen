"""
Ana kontrol penceresi (arayuz).

Yerlesim:
    Sol yan menu  -> Ana sayfa / Ceviri / Gorunum / Kisayollar / Performans / Gunluk
    Sag alan      -> secili sayfa

Ana sayfa: iki buyuk mod karti (Aninda tara / Canli mod), durum kartlari
(Ollama, GPU, OCR, onbellek) ve oyunda yakalanan son cevirilerin listesi.
Gorunum sayfasi: ayar degistikce guncellenen canli altyazi onizlemesi.

Tum ayarlar eskisi gibi ayni config sozlugune yazilir; degisiklik hem calisan
programa aninda uygulanir hem diske kaydedilir.

Pencere kapatilinca (X) program KAPANMAZ, sistem tepsisine gizlenir.
"""
import ctypes
import datetime
import logging
import os
import subprocess
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from app import config as config_mod
from app.core import capture as capture_mod
from app.core import theme as T

logger = logging.getLogger("OyunCevirmen.mainwindow")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON_PATH = os.path.join(BASE_DIR, "app", "assets", "icon.ico")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "oyuncevirmen.log")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

OCR_ENGINES = [("windows", "Windows OCR (hazır gelir, kurulum gerekmez)"),
               ("easyocr", "EasyOCR (ekran kartıyla, süslü fontlarda daha iyi)")]
TRANSLATE_ENGINES = [("ollama", "Ollama (bilgisayarında, internetsiz)"),
                     ("google", "Google Translate (internet gerekir)")]
SOURCE_LANGS = [
    ("auto", "Otomatik algıla"), ("en", "İngilizce"), ("de", "Almanca"),
    ("fr", "Fransızca"), ("es", "İspanyolca"), ("it", "İtalyanca"),
    ("pt", "Portekizce"), ("ru", "Rusça"), ("ja", "Japonca"),
    ("ko", "Korece"), ("zh-cn", "Çince (basitleştirilmiş)"),
]
FUNCTION_KEYS = [f"f{i}" for i in range(1, 13)]

OCR_SHORT = {"windows": "Windows OCR", "easyocr": "EasyOCR", "paddle": "PaddleOCR"}
ENGINE_SHORT = {"ollama": "Ollama", "google": "Google Translate"}

# Gorunum hazir ayarlari: (ad, arka plan, yazi, saydamlik)
PRESETS = [
    ("Altyazı sarısı", "#101114", "#F5C04A", 0.78),
    ("Klasik koyu", "#141414", "#FFFFFF", 0.72),
    ("Yüksek kontrast", "#000000", "#FFFFFF", 0.95),
    ("Kâğıt", "#F3EEDF", "#1D1B16", 0.90),
]


def hotkey_label(value):
    """'ctrl+f9' -> 'Ctrl + F9'"""
    parts = (value or "").lower().split("+")
    nice = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift"}
    return " + ".join(nice.get(p, p.upper()) for p in parts if p)


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _apply_dark_titlebar(widget):
    """Windows 11'de pencerenin baslik cubugunu da koyu yapar."""
    if os.name != "nt":
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (yeni / eski)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
        # Windows 11: baslik cubugu rengini zemine esitle (0x00BBGGRR)
        caption = ctypes.c_int(0x00251B18)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption)
        )
    except Exception:
        pass


# ======================================================== kucuk bilesenler
def label(text, name=None, wrap=False):
    lbl = QtWidgets.QLabel(text)
    if name:
        lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


class Keycap(QtWidgets.QLabel):
    """Klavye tusu gibi gorunen etiket."""

    def __init__(self, text="", large=False, parent=None):
        super().__init__(text, parent)
        self.setObjectName("KeycapLarge" if large else "Keycap")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)


class StatusDot(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Dot")
        self.setFixedSize(8, 8)

    def set_state(self, state):
        if self.property("state") != state:
            self.setProperty("state", state)
            _repolish(self)


class Card(QtWidgets.QFrame):
    def __init__(self, parent=None, padding=18, spacing=10):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)


class Field(QtWidgets.QWidget):
    """Etiket + kontrol + altinda kisa aciklama."""

    def __init__(self, title, control, hint=None, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(label(title, "Muted"))
        if isinstance(control, QtWidgets.QLayout):
            lay.addLayout(control)
        else:
            lay.addWidget(control)
        if hint:
            lay.addWidget(label(hint, "Hint", wrap=True))
        lay.addStretch(1)


class ModeCard(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal()

    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeCard")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(150)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        self.keycap = Keycap("F9", large=True)
        top.addWidget(self.keycap)
        top.addStretch(1)
        self.state = label("Kapalı", "ModeState")
        top.addWidget(self.state, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addSpacing(6)
        lay.addWidget(label(title, "ModeTitle"))
        lay.addWidget(label(description, "Muted", wrap=True))
        lay.addStretch(1)

    def set_hotkey(self, value):
        self.keycap.setText(hotkey_label(value))

    def set_active(self, active, text_on="Açık", text_off="Kapalı"):
        val = "true" if active else "false"
        self.state.setText(text_on if active else text_off)
        if self.property("active") != val:
            self.setProperty("active", val)
            self.state.setProperty("active", val)
            _repolish(self)
            _repolish(self.state)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


class StatCard(Card):
    def __init__(self, title, parent=None):
        super().__init__(parent, padding=16, spacing=4)
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.dot = StatusDot()
        head.addWidget(self.dot)
        head.addWidget(label(title, "StatLabel"))
        head.addStretch(1)
        self.body.addLayout(head)
        self.value = label("…", "StatValue")
        self.body.addWidget(self.value)
        self.detail = label("", "StatDetail", wrap=True)
        self.body.addWidget(self.detail)
        self.meter = QtWidgets.QProgressBar()
        self.meter.setObjectName("Meter")
        self.meter.setTextVisible(False)
        self.meter.setRange(0, 100)
        self.meter.setFixedHeight(6)
        self.meter.hide()
        self.body.addWidget(self.meter)
        self.body.addStretch(1)


class HotkeyRow(QtWidgets.QWidget):
    """Ctrl / Alt / Shift secimleri + fonksiyon tusu. Sol tarafta tusun
    kendisi buyuk bir tus kapagi olarak gorunur."""
    changed = QtCore.pyqtSignal()

    def __init__(self, field_key, initial_value, parent=None):
        super().__init__(parent)
        self.field_key = field_key
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.preview = Keycap("", large=True)
        self.preview.setFixedSize(130, 46)
        layout.addWidget(self.preview)
        layout.addSpacing(10)

        self.chk_ctrl = self._chip("Ctrl")
        self.chk_alt = self._chip("Alt")
        self.chk_shift = self._chip("Shift")
        self.combo_key = QtWidgets.QComboBox()
        self.combo_key.addItems([k.upper() for k in FUNCTION_KEYS])
        self.combo_key.setFixedWidth(90)

        self._apply_value(initial_value)

        for w in (self.chk_ctrl, self.chk_alt, self.chk_shift):
            w.toggled.connect(self._emit_changed)
            layout.addWidget(w)
        self.combo_key.currentIndexChanged.connect(self._emit_changed)
        layout.addWidget(self.combo_key)
        layout.addStretch(1)

    @staticmethod
    def _chip(text):
        b = QtWidgets.QPushButton(text)
        b.setObjectName("Chip")
        b.setCheckable(True)
        b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return b

    def _apply_value(self, value):
        parts = (value or "f9").lower().split("+")
        base = parts[-1]
        mods = parts[:-1]
        for w in (self.chk_ctrl, self.chk_alt, self.chk_shift):
            w.blockSignals(True)
        self.combo_key.blockSignals(True)
        self.chk_ctrl.setChecked("ctrl" in mods)
        self.chk_alt.setChecked("alt" in mods)
        self.chk_shift.setChecked("shift" in mods)
        if base in FUNCTION_KEYS:
            self.combo_key.setCurrentText(base.upper())
        for w in (self.chk_ctrl, self.chk_alt, self.chk_shift):
            w.blockSignals(False)
        self.combo_key.blockSignals(False)
        self.preview.setText(hotkey_label(self.value()))

    def _emit_changed(self, *_):
        self.preview.setText(hotkey_label(self.value()))
        self.changed.emit()

    def value(self):
        mods = []
        if self.chk_ctrl.isChecked():
            mods.append("ctrl")
        if self.chk_alt.isChecked():
            mods.append("alt")
        if self.chk_shift.isChecked():
            mods.append("shift")
        mods.append(self.combo_key.currentText().lower())
        return "+".join(mods)


class ColorButton(QtWidgets.QPushButton):
    changed = QtCore.pyqtSignal()

    def __init__(self, hex_color, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self.setMinimumWidth(130)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        self.setText("  " + self._hex.upper())
        pix = QtGui.QPixmap(18, 18)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE), 1))
        p.setBrush(QtGui.QColor(self._hex))
        p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, 17, 17), 4, 4)
        p.end()
        self.setIcon(QtGui.QIcon(pix))
        self.setIconSize(QtCore.QSize(18, 18))

    def _pick(self):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self._hex), self, "Renk seç")
        if color.isValid():
            self.set_hex(color.name())
            self.changed.emit()

    def set_hex(self, value):
        self._hex = value
        self._refresh()

    def hex(self):
        return self._hex


class SubtitlePreview(QtWidgets.QWidget):
    """Overlay'in oyunda nasil gorunecegini gosteren kucuk sahne.
    Cizim mantigi overlay.py ile ayni (kutu + sigdirilan kalin yazi)."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setMinimumHeight(250)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Preferred)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, 12, 12)
        p.setClipPath(clip)

        # -- sahne: alacakaranlik gokyuzu, uzak daglar, zemin
        sky = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        sky.setColorAt(0.0, QtGui.QColor("#2B3A5C"))
        sky.setColorAt(0.55, QtGui.QColor("#7A5A6E"))
        sky.setColorAt(1.0, QtGui.QColor("#D99A6C"))
        p.fillRect(r, sky)

        w, h = r.width(), r.height()
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(255, 236, 200, 200))
        p.drawEllipse(QtCore.QPointF(w * 0.78, h * 0.34), 22, 22)

        far = QtGui.QPolygonF([
            QtCore.QPointF(0, h * 0.62), QtCore.QPointF(w * 0.18, h * 0.40),
            QtCore.QPointF(w * 0.33, h * 0.56), QtCore.QPointF(w * 0.52, h * 0.36),
            QtCore.QPointF(w * 0.70, h * 0.58), QtCore.QPointF(w * 0.86, h * 0.45),
            QtCore.QPointF(w, h * 0.60), QtCore.QPointF(w, h), QtCore.QPointF(0, h),
        ])
        p.setBrush(QtGui.QColor(58, 52, 78, 220))
        p.drawPolygon(far)
        near = QtGui.QPolygonF([
            QtCore.QPointF(0, h * 0.78), QtCore.QPointF(w * 0.25, h * 0.66),
            QtCore.QPointF(w * 0.55, h * 0.80), QtCore.QPointF(w * 0.80, h * 0.70),
            QtCore.QPointF(w, h * 0.77), QtCore.QPointF(w, h), QtCore.QPointF(0, h),
        ])
        p.setBrush(QtGui.QColor(28, 26, 40, 240))
        p.drawPolygon(near)

        # -- sol ustte kucuk HUD (cevrilmeyen kisim: sayi)
        p.setPen(QtGui.QColor(255, 255, 255, 170))
        hud = QtGui.QFont(T.DISPLAY_FONT, 9)
        hud.setBold(True)
        p.setFont(hud)
        p.drawText(QtCore.QRectF(14, 10, 200, 20), "HP 84 / 100")

        # -- oyunun kendi diyalog kutusu (orijinal yazi burada)
        box = QtCore.QRectF(w * 0.08, h * 0.70, w * 0.84, h * 0.20)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(10, 10, 16, 150))
        p.drawRoundedRect(box, 6, 6)

        # -- ustune bizim ceviri kutusu (overlay.py ile ayni kurallar)
        bg = QtGui.QColor(self.config.get("overlay_bg_color", "#141414"))
        bg.setAlphaF(float(self.config.get("overlay_opacity", 0.72)))
        text_color = QtGui.QColor(self.config.get("overlay_text_color", "#FFFFFF"))
        base_size = int(self.config.get("font_size", 18))
        min_size = int(self.config.get("min_font_size", 10))

        text_rect = box.adjusted(18, 10, -18, -10).toRect()
        p.setBrush(bg)
        p.drawRoundedRect(QtCore.QRectF(text_rect), 4, 4)

        text = "Eski kapıyı açmak için E'ye bas"
        inner = text_rect.adjusted(4, 4, -4, -4)
        font = QtGui.QFont("Segoe UI", base_size)
        font.setBold(True)
        flags = QtCore.Qt.TextFlag.TextWordWrap | QtCore.Qt.AlignmentFlag.AlignCenter
        size = base_size
        while size > min_size:
            font.setPointSize(size)
            b = QtGui.QFontMetrics(font).boundingRect(inner, flags, text)
            if b.width() <= inner.width() and b.height() <= inner.height():
                break
            size -= 1
        font.setPointSize(max(size, min_size))
        p.setFont(font)
        p.setPen(text_color)
        p.drawText(inner, flags, text)

        p.setClipping(False)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 12, 12)
        p.end()


class _StatusBridge(QtCore.QObject):
    status_ready = QtCore.pyqtSignal(dict)
    test_ready = QtCore.pyqtSignal(str)
    models_ready = QtCore.pyqtSignal(list)


# ============================================================ ana pencere
class MainWindow(QtWidgets.QWidget):
    PAGES = ["Ana sayfa", "Çeviri", "Görünüm", "Kısayollar", "Performans", "Günlük"]

    def __init__(self, config, orchestrator):
        super().__init__()
        self.config = config  # canli, paylasilan config sozlugu (ayni referans)
        self.orchestrator = orchestrator
        self._loading = False
        self._feed_version = -1
        self._status_busy = False

        self.setObjectName("MainWindow")
        self.setWindowTitle("Oyun Çevirmen")
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        self.resize(1040, 700)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(T.stylesheet())

        self._bridge = _StatusBridge()
        self._bridge.status_ready.connect(self._apply_status)
        self._bridge.test_ready.connect(self._show_test_result)
        self._bridge.models_ready.connect(self._fill_models)

        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._apply_and_save)

        self._build_ui()
        self._load_from_config()
        self._wire_change_signals()

        # Mod/son ceviriler: hafif, sik kontrol. Ollama/GPU: arka planda, seyrek.
        self._fast_timer = QtCore.QTimer(self)
        self._fast_timer.timeout.connect(self._refresh_fast)
        self._fast_timer.start(700)
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(3000)
        self._log_timer = QtCore.QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(2000)

        self._refresh_fast()
        self._refresh_status()
        self._refresh_ollama_models()

    def showEvent(self, event):
        super().showEvent(event)
        _apply_dark_titlebar(self)
        self._refresh_fast()
        self._refresh_status()

    # ------------------------------------------------------------ iskelet
    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.stack = QtWidgets.QStackedWidget()
        builders = [
            self._build_home_page, self._build_translation_page,
            self._build_appearance_page, self._build_hotkeys_page,
            self._build_performance_page, self._build_log_page,
        ]
        for build in builders:
            self.stack.addWidget(build())
        root.addWidget(self.stack, 1)

        self.nav_buttons[0].setChecked(True)

    def _build_sidebar(self):
        side = QtWidgets.QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(232)
        lay = QtWidgets.QVBoxLayout(side)
        lay.setContentsMargins(0, 22, 0, 18)
        lay.setSpacing(2)

        brand = QtWidgets.QHBoxLayout()
        brand.setContentsMargins(18, 0, 18, 0)
        brand.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo.setPixmap(self._logo_pixmap(34))
        brand.addWidget(logo)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("Oyun Çevirmen", "BrandName"))
        names.addWidget(label("Ekrandaki yazılar, Türkçe", "BrandSub"))
        brand.addLayout(names)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(26)

        self.nav_group = QtWidgets.QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        for i, name in enumerate(self.PAGES):
            b = QtWidgets.QPushButton(name)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(b, i)
            self.nav_buttons.append(b)
            lay.addWidget(b)
        self.nav_group.idClicked.connect(self._go_to_page)

        lay.addStretch(1)

        foot = QtWidgets.QVBoxLayout()
        foot.setContentsMargins(18, 0, 18, 0)
        foot.setSpacing(8)
        self.lbl_saved = label("", "SavedLabel")
        foot.addWidget(self.lbl_saved)
        btn_quit = QtWidgets.QPushButton("Programı kapat")
        btn_quit.setObjectName("Danger")
        btn_quit.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_quit.clicked.connect(self.orchestrator.request_quit)
        foot.addWidget(btn_quit)
        self.lbl_quit_hint = label("Pencereyi kapatırsan program saatin yanında çalışmaya devam eder.",
                                   "Hint", wrap=True)
        foot.addWidget(self.lbl_quit_hint)
        lay.addLayout(foot)
        return side

    @staticmethod
    def _logo_pixmap(size):
        """Sari zemin uzerinde altyazi satirlari: programin simgesi."""
        ratio = 2
        pix = QtGui.QPixmap(size * ratio, size * ratio)
        pix.setDevicePixelRatio(ratio)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(T.AMBER))
        p.drawRoundedRect(QtCore.QRectF(0, 0, size, size), size * 0.26, size * 0.26)
        p.setBrush(QtGui.QColor(T.AMBER_INK))
        s = size / 34.0
        p.drawRoundedRect(QtCore.QRectF(7 * s, 15 * s, 20 * s, 4 * s), 2 * s, 2 * s)
        p.drawRoundedRect(QtCore.QRectF(10 * s, 22 * s, 14 * s, 4 * s), 2 * s, 2 * s)
        p.end()
        return pix

    def _go_to_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 5:
            self._refresh_log(force=True)

    def _page(self, title, lead=None, scroll=True):
        """Sayfa iskeleti: baslik + aciklama + icerik yerlesimi."""
        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setContentsMargins(36, 30, 36, 30)
        lay.setSpacing(18)
        head = QtWidgets.QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(label(title, "PageTitle"))
        if lead:
            head.addWidget(label(lead, "PageLead", wrap=True))
        lay.addLayout(head)
        if not scroll:
            return content, lay
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        area.setWidget(content)
        return area, lay

    # ---------------------------------------------------------- ana sayfa
    def _build_home_page(self):
        page, lay = self._page("Ana sayfa")
        self.lbl_headline = label("", "PageLead", wrap=True)
        lay.itemAt(0).layout().addWidget(self.lbl_headline)

        modes = QtWidgets.QHBoxLayout()
        modes.setSpacing(16)
        self.card_instant = ModeCard(
            "Anında tara",
            "Ekranı bir kez tarar, bulduğu her yazının üstüne Türkçesini koyar. "
            "Tekrar basınca çeviriler kaybolur. Menü ve envanter için ideal.",
        )
        self.card_instant.clicked.connect(self._click_instant)
        self.card_live = ModeCard(
            "Canlı mod",
            "Ekranı sürekli izler, sadece değişen yerleri yeniden okur. "
            "Diyaloglar ve altyazılar için.",
        )
        self.card_live.clicked.connect(self._click_live)
        modes.addWidget(self.card_instant, 1)
        modes.addWidget(self.card_live, 1)
        lay.addLayout(modes)

        stats = QtWidgets.QGridLayout()
        stats.setSpacing(12)
        self.stat_ollama = StatCard("Çeviri motoru")
        self.stat_gpu = StatCard("Ekran kartı")
        self.stat_ocr = StatCard("Yazı okuma")
        self.stat_cache = StatCard("Hafızadaki çeviriler")
        for i, c in enumerate((self.stat_ollama, self.stat_gpu, self.stat_ocr, self.stat_cache)):
            stats.addWidget(c, 0, i)
            stats.setColumnStretch(i, 1)
        lay.addLayout(stats)

        feed_card = Card(padding=0, spacing=0)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(18, 16, 14, 10)
        head.addWidget(label("Son çeviriler", "SectionTitle"))
        head.addStretch(1)
        self.btn_copy_feed = QtWidgets.QPushButton("Listeyi kopyala")
        self.btn_copy_feed.setObjectName("Ghost")
        self.btn_copy_feed.clicked.connect(self._copy_feed)
        head.addWidget(self.btn_copy_feed)
        feed_card.body.addLayout(head)

        self.feed_container = QtWidgets.QWidget()
        self.feed_layout = QtWidgets.QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(0, 0, 0, 6)
        self.feed_layout.setSpacing(0)
        feed_card.body.addWidget(self.feed_container)
        lay.addWidget(feed_card)
        lay.addStretch(1)
        return page

    def _click_instant(self):
        self.orchestrator.toggle_instant()
        QtCore.QTimer.singleShot(150, self._refresh_fast)

    def _click_live(self):
        self.orchestrator.toggle_live()
        QtCore.QTimer.singleShot(150, self._refresh_fast)

    def _rebuild_feed(self, items):
        while self.feed_layout.count():
            it = self.feed_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if not items:
            hk = hotkey_label(self.config.get("hotkey_instant", "f9"))
            empty = label(
                f"Henüz çeviri yok. Bir oyunda {hk} tuşuna bas; "
                "ekranda bulunan yazılar ve Türkçeleri burada listelenir.",
                "EmptyState", wrap=True,
            )
            empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.feed_layout.addWidget(empty)
            self.btn_copy_feed.setEnabled(False)
            return

        self.btn_copy_feed.setEnabled(True)
        for ts, original, translated in items[:12]:
            row = QtWidgets.QFrame()
            row.setObjectName("FeedRow")
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(18, 10, 18, 10)
            rl.setSpacing(16)
            texts = QtWidgets.QVBoxLayout()
            texts.setSpacing(2)
            tr = label(translated, "FeedTranslated", wrap=True)
            tr.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            texts.addWidget(tr)
            texts.addWidget(label(original, "FeedOriginal", wrap=True))
            rl.addLayout(texts, 1)
            when = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            rl.addWidget(label(when, "FeedTime"), 0, QtCore.Qt.AlignmentFlag.AlignTop)
            self.feed_layout.addWidget(row)

    def _copy_feed(self):
        items = list(getattr(self.orchestrator, "recent", []))
        text = "\n".join(f"{o}\n→ {t}\n" for _, o, t in items)
        QtWidgets.QApplication.clipboard().setText(text)
        self._flash("Panoya kopyalandı")

    # -------------------------------------------------------- ceviri sayfasi
    def _build_translation_page(self):
        page, lay = self._page(
            "Çeviri",
            "Ekrandaki yazıyı neyin okuyacağını ve neyin çevireceğini seç. "
            "Değişiklikler anında uygulanır.",
        )

        engines = Card(spacing=16)
        engines.body.addWidget(label("Motorlar", "SectionTitle"))
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(16)

        self.combo_ocr = QtWidgets.QComboBox()
        for key, text in OCR_ENGINES:
            self.combo_ocr.addItem(text, userData=key)
        grid.addWidget(Field("Yazı okuma (OCR)", self.combo_ocr,
                             "Yazıları kaçırıyorsa EasyOCR'ı dene."), 0, 0)

        self.combo_translate = QtWidgets.QComboBox()
        for key, text in TRANSLATE_ENGINES:
            self.combo_translate.addItem(text, userData=key)
        grid.addWidget(Field("Çeviri", self.combo_translate,
                             "Ollama çalışmazsa program kendiliğinden Google'a geçer."), 0, 1)

        model_row = QtWidgets.QHBoxLayout()
        model_row.setSpacing(8)
        self.combo_model = QtWidgets.QComboBox()
        self.combo_model.setEditable(True)
        btn_refresh_models = QtWidgets.QPushButton("Yenile")
        btn_refresh_models.clicked.connect(self._refresh_ollama_models)
        model_row.addWidget(self.combo_model, 1)
        model_row.addWidget(btn_refresh_models)
        grid.addWidget(Field("Ollama modeli", model_row,
                             "Bilgisayarındaki modeller listelenir."), 1, 0)

        self.combo_source_lang = QtWidgets.QComboBox()
        for code, name in SOURCE_LANGS:
            self.combo_source_lang.addItem(name, userData=code)
        grid.addWidget(Field("Oyunun dili", self.combo_source_lang,
                             "Biliyorsan seç; otomatik algılamadan daha isabetli okur."), 1, 1)

        self.edit_host = QtWidgets.QLineEdit()
        grid.addWidget(Field("Ollama adresi", self.edit_host,
                             "Genelde değiştirmen gerekmez."), 2, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        engines.body.addLayout(grid)
        lay.addWidget(engines)

        test = Card(spacing=12)
        test.body.addWidget(label("Çeviriyi dene", "SectionTitle"))
        test.body.addWidget(label("Oyuna girmeden önce seçtiğin motorun nasıl çevirdiğine bak.",
                                  "Muted", wrap=True))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.edit_test_input = QtWidgets.QLineEdit("Press E to open the door")
        self.edit_test_input.returnPressed.connect(self._run_translation_test)
        self.btn_test = QtWidgets.QPushButton("Çevir")
        self.btn_test.setObjectName("Primary")
        self.btn_test.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_test.clicked.connect(self._run_translation_test)
        row.addWidget(self.edit_test_input, 1)
        row.addWidget(self.btn_test)
        test.body.addLayout(row)
        self.lbl_test_result = label("", "FeedTranslated", wrap=True)
        self.lbl_test_result.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        test.body.addWidget(self.lbl_test_result)
        lay.addWidget(test)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------ gorunum sayfasi
    def _build_appearance_page(self):
        page, lay = self._page(
            "Görünüm",
            "Çevirilerin oyunda nasıl duracağını ayarla. Önizleme ayarları değiştirdikçe güncellenir.",
        )

        self.preview = SubtitlePreview(self.config)
        lay.addWidget(self.preview)

        presets = QtWidgets.QHBoxLayout()
        presets.setSpacing(8)
        presets.addWidget(label("Hazır stiller", "Muted"))
        presets.addSpacing(6)
        for name, bg, fg, op in PRESETS:
            b = QtWidgets.QPushButton(name)
            b.setObjectName("Preset")
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, bg=bg, fg=fg, op=op: self._apply_preset(bg, fg, op))
            presets.addWidget(b)
        presets.addStretch(1)
        lay.addLayout(presets)

        card = Card(spacing=16)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(16)

        self.spin_font = QtWidgets.QSpinBox()
        self.spin_font.setRange(6, 60)
        self.spin_font.setSuffix(" pt")
        grid.addWidget(Field("Yazı boyutu", self.spin_font,
                             "Kutuya sığmazsa otomatik küçülür."), 0, 0)

        self.spin_min_font = QtWidgets.QSpinBox()
        self.spin_min_font.setRange(6, 60)
        self.spin_min_font.setSuffix(" pt")
        grid.addWidget(Field("En küçük yazı boyutu", self.spin_min_font,
                             "Küçülme bunun altına inmez."), 0, 1)

        self.slider_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.lbl_opacity = label("72%", "Muted")
        self.lbl_opacity.setFixedWidth(40)
        op_row = QtWidgets.QHBoxLayout()
        op_row.addWidget(self.slider_opacity, 1)
        op_row.addWidget(self.lbl_opacity)
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"{v}%"))
        grid.addWidget(Field("Kutu koyuluğu", op_row,
                             "Yükseldikçe arkadaki orijinal yazı daha az görünür."), 1, 0)

        colors = QtWidgets.QHBoxLayout()
        colors.setSpacing(10)
        self.btn_bg_color = ColorButton("#141414")
        self.btn_text_color = ColorButton("#FFFFFF")
        colors.addWidget(self.btn_bg_color)
        colors.addWidget(self.btn_text_color)
        colors.addStretch(1)
        grid.addWidget(Field("Kutu ve yazı rengi", colors), 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _apply_preset(self, bg, fg, opacity):
        self.btn_bg_color.set_hex(bg)
        self.btn_text_color.set_hex(fg)
        self.slider_opacity.setValue(int(round(opacity * 100)))
        self._schedule_save()

    # ----------------------------------------------------- kisayol sayfasi
    def _build_hotkeys_page(self):
        page, lay = self._page(
            "Kısayollar",
            "Oyun açıkken de çalışırlar. Oyunun kendi tuşlarıyla çakışıyorsa "
            "Ctrl, Alt veya Shift ekle.",
        )
        card = Card(spacing=0, padding=0)
        self.row_instant = HotkeyRow("hotkey_instant", "f9")
        self.row_live = HotkeyRow("hotkey_live_toggle", "f10")
        self.row_quit = HotkeyRow("hotkey_quit", "f11")
        rows = [
            ("Anında tara", "Ekranı bir kez çevir, tekrar basınca kapat.", self.row_instant),
            ("Canlı mod", "Sürekli izlemeyi aç veya kapat.", self.row_live),
            ("Programı kapat", "Oyun Çevirmen'i tamamen kapatır.", self.row_quit),
        ]
        for i, (title, desc, row) in enumerate(rows):
            wrap = QtWidgets.QFrame()
            if i < len(rows) - 1:
                wrap.setObjectName("FeedRow")
            wl = QtWidgets.QHBoxLayout(wrap)
            wl.setContentsMargins(20, 18, 20, 18)
            wl.setSpacing(20)
            texts = QtWidgets.QVBoxLayout()
            texts.setSpacing(2)
            texts.addWidget(label(title, "SectionTitle"))
            texts.addWidget(label(desc, "Hint", wrap=True))
            tw = QtWidgets.QWidget()
            tw.setLayout(texts)
            tw.setFixedWidth(220)
            wl.addWidget(tw)
            wl.addWidget(row, 1)
            card.body.addWidget(wrap)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    # -------------------------------------------------- performans sayfasi
    def _build_performance_page(self):
        page, lay = self._page(
            "Performans",
            "Varsayılanlar çoğu oyunda iyi çalışır. Oyun takılıyorsa tarama aralığını artır.",
        )

        live = Card(spacing=16)
        live.body.addWidget(label("Canlı mod", "SectionTitle"))
        g = QtWidgets.QGridLayout()
        g.setHorizontalSpacing(24)
        g.setVerticalSpacing(16)
        self.spin_interval = QtWidgets.QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 5.0)
        self.spin_interval.setSingleStep(0.05)
        self.spin_interval.setSuffix(" sn")
        g.addWidget(Field("Tarama aralığı", self.spin_interval,
                          "Düşük değer daha hızlı yakalar ama daha çok güç harcar."), 0, 0)
        self.spin_padding = QtWidgets.QSpinBox()
        self.spin_padding.setRange(0, 300)
        self.spin_padding.setSuffix(" px")
        g.addWidget(Field("Parça kenar payı", self.spin_padding,
                          "Kelimeler parça sınırında bölünüyorsa artır."), 0, 1)
        self.spin_cols = QtWidgets.QSpinBox()
        self.spin_cols.setRange(1, 20)
        g.addWidget(Field("Sütun sayısı", self.spin_cols,
                          "Ekran kaç dikey parçaya bölünsün."), 1, 0)
        self.spin_rows = QtWidgets.QSpinBox()
        self.spin_rows.setRange(1, 20)
        g.addWidget(Field("Satır sayısı", self.spin_rows,
                          "Ekran kaç yatay parçaya bölünsün."), 1, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        live.body.addLayout(g)
        lay.addWidget(live)

        filt = Card(spacing=16)
        filt.body.addWidget(label("Neyi çevirmesin", "SectionTitle"))
        g2 = QtWidgets.QGridLayout()
        g2.setHorizontalSpacing(24)
        g2.setVerticalSpacing(16)
        self.spin_min_len = QtWidgets.QSpinBox()
        self.spin_min_len.setRange(1, 20)
        self.spin_min_len.setSuffix(" harf")
        g2.addWidget(Field("En kısa metin", self.spin_min_len,
                           "Bundan kısa yazılar (HP, x3 gibi) atlanır."), 0, 0)
        self.spin_min_conf = QtWidgets.QDoubleSpinBox()
        self.spin_min_conf.setRange(0.0, 1.0)
        self.spin_min_conf.setSingleStep(0.05)
        g2.addWidget(Field("Okuma güveni eşiği", self.spin_min_conf,
                           "Yükseltirsen bulanık okunan yazılar elenir."), 0, 1)
        g2.setColumnStretch(0, 1)
        g2.setColumnStretch(1, 1)
        filt.body.addLayout(g2)
        lay.addWidget(filt)

        sysc = Card(spacing=16)
        sysc.body.addWidget(label("Hafıza ve ekran", "SectionTitle"))
        g3 = QtWidgets.QGridLayout()
        g3.setHorizontalSpacing(24)
        g3.setVerticalSpacing(16)
        self.spin_cache = QtWidgets.QSpinBox()
        self.spin_cache.setRange(100, 50000)
        self.spin_cache.setSingleStep(100)
        g3.addWidget(Field("Bellekte tutulacak çeviri", self.spin_cache,
                           "Tümü ayrıca diske kaydedilir; program kapanınca kaybolmaz."), 0, 0)
        monitor_row = QtWidgets.QHBoxLayout()
        monitor_row.setSpacing(8)
        self.combo_monitor = QtWidgets.QComboBox()
        btn_refresh_monitors = QtWidgets.QPushButton("Yenile")
        btn_refresh_monitors.clicked.connect(self._refresh_monitors)
        monitor_row.addWidget(self.combo_monitor, 1)
        monitor_row.addWidget(btn_refresh_monitors)
        g3.addWidget(Field("İzlenecek ekran", monitor_row,
                           "Oyunun açık olduğu ekranı seç. Değişiklik anında uygulanır."), 0, 1)
        cache_row = QtWidgets.QHBoxLayout()
        self.btn_clear_cache = QtWidgets.QPushButton("Çeviri hafızasını sil")
        self.btn_clear_cache.setObjectName("Danger")
        self.btn_clear_cache.clicked.connect(self._clear_cache)
        cache_row.addWidget(self.btn_clear_cache)
        cache_row.addStretch(1)
        g3.addWidget(Field("Hafızayı sıfırla", cache_row,
                           "Model değiştirdiysen eski çevirilerin yerine yenilerini görmek için."), 1, 0)
        g3.setColumnStretch(0, 1)
        g3.setColumnStretch(1, 1)
        sysc.body.addLayout(g3)
        lay.addWidget(sysc)

        reset_row = QtWidgets.QHBoxLayout()
        reset_row.addStretch(1)
        btn_defaults = QtWidgets.QPushButton("Tüm ayarları varsayılana döndür")
        btn_defaults.setObjectName("Ghost")
        btn_defaults.clicked.connect(self._reset_defaults)
        reset_row.addWidget(btn_defaults)
        lay.addLayout(reset_row)
        lay.addStretch(1)
        return page

    def _clear_cache(self):
        answer = QtWidgets.QMessageBox.question(
            self, "Çeviri hafızasını sil",
            "Kaydedilmiş tüm çeviriler silinecek ve yazılar yeniden çevrilecek. Devam edilsin mi?",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self.orchestrator.translator.cache.clear()
            self._flash("Çeviri hafızası silindi")
        except Exception as exc:
            logger.error("Onbellek temizlenemedi: %s", exc)
        self._refresh_status()

    # ------------------------------------------------------- monitor secimi
    def _refresh_monitors(self, select_index=None):
        if select_index is None:
            select_index = self.combo_monitor.currentData()

        self.combo_monitor.blockSignals(True)
        self.combo_monitor.clear()
        for mon in capture_mod.list_monitors():
            self.combo_monitor.addItem(mon["label"], userData=mon["index"])
        idx = self.combo_monitor.findData(select_index)
        self.combo_monitor.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_monitor.blockSignals(False)

    def _on_monitor_changed(self, *_):
        if self._loading:
            return
        new_index = self.combo_monitor.currentData()
        if new_index is None:
            return
        ok = self.orchestrator.change_monitor(new_index)
        if ok:
            self._flash("İzlenecek ekran değiştirildi")
        else:
            self._flash("Ekran değiştirilemedi, günlüğe bakın")
        self._refresh_status()

    # ------------------------------------------------------- gunluk sayfasi
    def _build_log_page(self):
        page, lay = self._page(
            "Günlük",
            "Programın yaptıkları. Bir sorun olursa buradaki son satırlar sebebini gösterir.",
            scroll=False,
        )
        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setObjectName("LogView")
        self.txt_log.setReadOnly(True)
        self.txt_log.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.txt_log, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        btn_open = QtWidgets.QPushButton("Günlük klasörünü aç")
        btn_open.clicked.connect(self._open_log_folder)
        row.addWidget(btn_open)
        lay.addLayout(row)
        return page

    def _open_log_folder(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(LOG_DIR))
        except Exception as exc:
            logger.error("Gunluk klasoru acilamadi: %s", exc)

    # --------------------------------------------------------- yukleme
    def _load_from_config(self):
        self._loading = True
        cfg = self.config
        self._set_combo_data(self.combo_ocr, cfg.get("ocr_engine", "windows"))
        self._set_combo_data(self.combo_translate, cfg.get("translate_engine", "ollama"))
        self.combo_model.setCurrentText(cfg.get("ollama_model", "aya-expanse:8b"))
        self.edit_host.setText(cfg.get("ollama_host", "http://127.0.0.1:11434"))
        src = cfg.get("source_lang", "auto")
        if self.combo_source_lang.findData(src) < 0:
            self.combo_source_lang.addItem(src, userData=src)
        self._set_combo_data(self.combo_source_lang, src)

        self.spin_font.setValue(cfg.get("font_size", 18))
        self.spin_min_font.setValue(cfg.get("min_font_size", 10))
        self.slider_opacity.setValue(int(round(cfg.get("overlay_opacity", 0.72) * 100)))
        self.btn_bg_color.set_hex(cfg.get("overlay_bg_color", "#141414"))
        self.btn_text_color.set_hex(cfg.get("overlay_text_color", "#FFFFFF"))

        self.row_instant._apply_value(cfg.get("hotkey_instant", "f9"))
        self.row_live._apply_value(cfg.get("hotkey_live_toggle", "f10"))
        self.row_quit._apply_value(cfg.get("hotkey_quit", "f11"))

        self.spin_interval.setValue(cfg.get("live_scan_interval", 0.45))
        self.spin_cols.setValue(cfg.get("live_grid_cols", 6))
        self.spin_rows.setValue(cfg.get("live_grid_rows", 4))
        self.spin_padding.setValue(cfg.get("live_cell_padding", 60))
        self.spin_min_len.setValue(cfg.get("min_text_length", 2))
        self.spin_min_conf.setValue(cfg.get("min_ocr_confidence", 0.45))
        self.spin_cache.setValue(cfg.get("max_cache_memory_items", 5000))
        self._refresh_monitors(select_index=cfg.get("capture_monitor_index", 0))
        self._loading = False
        self._sync_hotkey_labels()

    @staticmethod
    def _set_combo_data(combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _wire_change_signals(self):
        widgets_simple = [
            self.combo_ocr, self.combo_translate, self.combo_model, self.edit_host,
            self.combo_source_lang, self.spin_font, self.spin_min_font,
            self.slider_opacity, self.spin_interval, self.spin_cols, self.spin_rows,
            self.spin_min_len, self.spin_min_conf, self.spin_cache,
            self.spin_padding,
        ]
        for widget in widgets_simple:
            if isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(self._schedule_save)
                if widget.isEditable():
                    widget.editTextChanged.connect(self._schedule_save)
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.editingFinished.connect(self._schedule_save)
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QSlider)):
                widget.valueChanged.connect(self._schedule_save)

        self.btn_bg_color.changed.connect(self._schedule_save)
        self.btn_text_color.changed.connect(self._schedule_save)
        self.row_instant.changed.connect(self._schedule_save)
        self.row_live.changed.connect(self._schedule_save)
        self.row_quit.changed.connect(self._schedule_save)
        self.combo_monitor.currentIndexChanged.connect(self._on_monitor_changed)

        # Onizleme kaydetmeyi beklemeden aninda tepki versin
        for w in (self.spin_font, self.spin_min_font, self.slider_opacity):
            w.valueChanged.connect(self._update_preview_live)
        self.btn_bg_color.changed.connect(self._update_preview_live)
        self.btn_text_color.changed.connect(self._update_preview_live)

    def _update_preview_live(self, *_):
        if self._loading:
            return
        self.config["font_size"] = self.spin_font.value()
        self.config["min_font_size"] = self.spin_min_font.value()
        self.config["overlay_opacity"] = round(self.slider_opacity.value() / 100.0, 2)
        self.config["overlay_bg_color"] = self.btn_bg_color.hex()
        self.config["overlay_text_color"] = self.btn_text_color.hex()
        self.preview.update()

    def _schedule_save(self, *_):
        if self._loading:
            return
        self._save_timer.start(500)

    # ------------------------------------------------------ uygulama
    def _apply_and_save(self):
        cfg = self.config
        old_hotkeys = (
            cfg.get("hotkey_instant"), cfg.get("hotkey_live_toggle"), cfg.get("hotkey_quit")
        )

        cfg["ocr_engine"] = self.combo_ocr.currentData()
        cfg["translate_engine"] = self.combo_translate.currentData()
        cfg["ollama_model"] = self.combo_model.currentText().strip()
        cfg["ollama_host"] = self.edit_host.text().strip() or "http://127.0.0.1:11434"
        cfg["source_lang"] = self.combo_source_lang.currentData() or "auto"

        cfg["font_size"] = self.spin_font.value()
        cfg["min_font_size"] = self.spin_min_font.value()
        cfg["overlay_opacity"] = round(self.slider_opacity.value() / 100.0, 2)
        cfg["overlay_bg_color"] = self.btn_bg_color.hex()
        cfg["overlay_text_color"] = self.btn_text_color.hex()

        cfg["hotkey_instant"] = self.row_instant.value()
        cfg["hotkey_live_toggle"] = self.row_live.value()
        cfg["hotkey_quit"] = self.row_quit.value()

        cfg["live_scan_interval"] = self.spin_interval.value()
        cfg["live_grid_cols"] = self.spin_cols.value()
        cfg["live_grid_rows"] = self.spin_rows.value()
        cfg["live_cell_padding"] = self.spin_padding.value()
        cfg["min_text_length"] = self.spin_min_len.value()
        cfg["min_ocr_confidence"] = round(self.spin_min_conf.value(), 2)
        cfg["max_cache_memory_items"] = self.spin_cache.value()
        # capture_monitor_index _on_monitor_changed uzerinden ayri yonetiliyor
        # (secilir secilmez aninda uygulanmasi gerekiyor, "kaydet" dongusunu beklemez)

        config_mod.save_config(cfg)

        new_hotkeys = (
            cfg.get("hotkey_instant"), cfg.get("hotkey_live_toggle"), cfg.get("hotkey_quit")
        )
        if new_hotkeys != old_hotkeys:
            try:
                self.orchestrator.hotkeys.start()
                logger.info("Kisayollar yeniden kaydedildi: %s", new_hotkeys)
            except Exception as exc:
                logger.error("Kisayollar yeniden kaydedilemedi: %s", exc)
            self._sync_hotkey_labels()

        self.preview.update()
        self._flash("Ayarlar kaydedildi")
        self._refresh_status()

    def _reset_defaults(self):
        answer = QtWidgets.QMessageBox.question(
            self, "Varsayılana döndür",
            "Tüm ayarlar ilk kurulumdaki haline dönecek. Devam edilsin mi?",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.config.clear()
        self.config.update(config_mod.DEFAULT_CONFIG)
        config_mod.save_config(self.config)
        self._load_from_config()
        try:
            self.orchestrator.hotkeys.start()
        except Exception:
            pass
        self.preview.update()
        self._flash("Varsayılan ayarlara dönüldü")

    def _flash(self, text):
        self.lbl_saved.setText("✓  " + text)
        QtCore.QTimer.singleShot(2500, lambda: self.lbl_saved.setText(""))

    def _sync_hotkey_labels(self):
        self.card_instant.set_hotkey(self.config.get("hotkey_instant", "f9"))
        self.card_live.set_hotkey(self.config.get("hotkey_live_toggle", "f10"))
        self._feed_version = -1  # bos durum metnindeki tus adini da yenile

    # --------------------------------------------------------- durum
    def _refresh_fast(self):
        """Mod kartlari, ust satir ve son ceviriler. Hafif; sik calisir."""
        if not self.isVisible():
            return
        mode = getattr(self.orchestrator, "mode", "none")
        self.card_instant.set_active(mode == "instant", "Ekranda", "Kapalı")
        self.card_live.set_active(mode == "live", "İzleniyor", "Kapalı")

        hk_i = hotkey_label(self.config.get("hotkey_instant", "f9"))
        hk_l = hotkey_label(self.config.get("hotkey_live_toggle", "f10"))
        if mode == "live":
            text = f"Canlı mod açık, ekran izleniyor. Kapatmak için {hk_l}."
        elif mode == "instant":
            text = f"Çeviriler ekranda. Kaldırmak için tekrar {hk_i}."
        else:
            text = (f"Hazır. Oyunu kenarlıksız pencere modunda aç, "
                    f"çevirmek istediğinde {hk_i} tuşuna bas.")
        self.lbl_headline.setText(text)

        version = getattr(self.orchestrator, "recent_version", 0)
        if version != self._feed_version:
            self._feed_version = version
            self._rebuild_feed(list(getattr(self.orchestrator, "recent", [])))

    def _refresh_status(self):
        if not self.isVisible() or self._status_busy:
            return
        self._status_busy = True
        threading.Thread(target=self._collect_status, daemon=True).start()

    def _collect_status(self):
        info = {}
        try:
            info["ollama"] = bool(self.orchestrator.translator.ollama.is_available())
        except Exception:
            info["ollama"] = False
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                creationflags=CREATE_NO_WINDOW, timeout=3,
            ).decode("utf-8", "ignore").strip().splitlines()[0]
            name, used, total, util = [p.strip() for p in out.split(",")]
            info["gpu"] = (name.replace("NVIDIA ", "").replace("GeForce ", ""),
                           int(float(used)), int(float(total)), int(float(util)))
        except Exception:
            info["gpu"] = None
        try:
            info["cache"] = self.orchestrator.translator.cache.count()
        except Exception:
            info["cache"] = None
        self._bridge.status_ready.emit(info)

    def _apply_status(self, info):
        self._status_busy = False
        engine = self.config.get("translate_engine", "ollama")
        model = self.config.get("ollama_model", "")
        s = self.stat_ollama
        if engine == "ollama":
            if info.get("ollama"):
                s.dot.set_state("ok")
                s.value.setText("Ollama hazır")
                s.detail.setText(model)
            else:
                s.dot.set_state("bad")
                s.value.setText("Ollama kapalı")
                s.detail.setText("Şimdilik Google Translate kullanılıyor.")
        else:
            s.dot.set_state("ok")
            s.value.setText("Google Translate")
            s.detail.setText("İnternet bağlantısı gerekir.")

        g = self.stat_gpu
        gpu = info.get("gpu")
        if gpu:
            name, used, total, util = gpu
            g.dot.set_state("ok")
            g.value.setText(name)
            g.detail.setText(f"{used / 1024:.1f} / {total / 1024:.0f} GB bellek, %{util} yük")
            g.meter.setValue(int(used * 100 / max(total, 1)))
            g.meter.show()
        else:
            g.dot.set_state(None)
            g.value.setText("Bilgi yok")
            g.detail.setText("NVIDIA sürücüsü bulunamadı.")
            g.meter.hide()

        o = self.stat_ocr
        o.dot.set_state("ok")
        o.value.setText(OCR_SHORT.get(self.config.get("ocr_engine"), self.config.get("ocr_engine", "?")))
        lang = self.config.get("source_lang", "auto")
        o.detail.setText(dict(SOURCE_LANGS).get(lang, lang))

        c = self.stat_cache
        count = info.get("cache")
        c.dot.set_state("live" if count else None)
        c.value.setText(f"{count:,}".replace(",", ".") if count is not None else "?")
        c.detail.setText("Tekrar gelen yazılar anında çevrilir.")

    def _refresh_ollama_models(self):
        def worker():
            try:
                out = subprocess.check_output(
                    ["ollama", "list"], creationflags=CREATE_NO_WINDOW, timeout=5
                ).decode("utf-8", "ignore").splitlines()
                names = [line.split()[0] for line in out[1:] if line.strip()]
            except Exception as exc:
                logger.warning("Ollama model listesi alinamadi: %s", exc)
                names = []
            self._bridge.models_ready.emit(names)

        threading.Thread(target=worker, daemon=True).start()

    def _fill_models(self, names):
        current = self.combo_model.currentText() or self.config.get("ollama_model", "aya-expanse:8b")
        self._loading = True
        self.combo_model.clear()
        self.combo_model.addItems(names)
        self.combo_model.setCurrentText(current)
        self._loading = False

    def _run_translation_test(self):
        text = self.edit_test_input.text().strip()
        if not text:
            return
        self.lbl_test_result.setText("Çevriliyor…")
        self.btn_test.setEnabled(False)

        def worker():
            try:
                result = self.orchestrator.translator.translate(text)
            except Exception as exc:
                result = f"Çeviri yapılamadı: {exc}"
            self._bridge.test_ready.emit(result or "Çeviri alınamadı. Günlük sayfasına bak.")

        threading.Thread(target=worker, daemon=True).start()

    def _show_test_result(self, text):
        self.lbl_test_result.setText(text)
        self.btn_test.setEnabled(True)

    def _refresh_log(self, force=False):
        if not self.isVisible() or (not force and self.stack.currentIndex() != 5):
            return
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 12000))
                data = f.read()
        except Exception:
            data = "Henüz günlük kaydı yok."
        if data != self.txt_log.toPlainText():
            self.txt_log.setPlainText(data)
            bar = self.txt_log.verticalScrollBar()
            bar.setValue(bar.maximum())

    # --------------------------------------------------- pencere davranisi
    def closeEvent(self, event):
        event.ignore()
        self.hide()
