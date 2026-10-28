"""
Overlay modulu: PyQt6 ile seffaf, her zaman ustte, tiklamalari gecirten
(click-through) bir pencere. Her ceviri, orijinal yazinin kutusunun tam
ustune yari saydam koyu bir arka planla cizilir; sigmazsa font kucultulur.

Onemli: SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) uygulanir, boylece
- Ekran kaydi / bazi oyunlarin capture'i / kendi ekran taramamiz bu pencereyi
  GORMEZ (hem gizlilik hem de "kendi cevirisini tekrar okuma" sorununu onler).
"""
import ctypes
import logging
import os

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("OyunCevirmen.overlay")

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


class TranslationBox:
    __slots__ = ("rect", "text", "orig_rect")

    def __init__(self, rect, text):
        self.rect = rect  # QRect, ekran (sanal masaustu) koordinatlarinda
        self.text = text


class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._boxes = []
        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            if hasattr(QtCore.Qt.WindowType, "X11BypassWindowManagerHint")
            else QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        geometry = self._virtual_desktop_geometry()
        self.setGeometry(geometry)

    def _virtual_desktop_geometry(self):
        screens = QtWidgets.QApplication.screens()
        if not screens:
            return QtCore.QRect(0, 0, 1920, 1080)
        rect = screens[0].geometry()
        for s in screens[1:]:
            rect = rect.united(s.geometry())
        return rect

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_native_clickthrough_and_capture_exclusion()

    def _apply_native_clickthrough_and_capture_exclusion(self):
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

            SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
            ok = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            if not ok:
                logger.warning("SetWindowDisplayAffinity basarisiz oldu (eski Windows surumu olabilir).")
            else:
                logger.info("Overlay ekran yakalamadan haric tutuldu (WDA_EXCLUDEFROMCAPTURE).")
        except Exception as exc:
            logger.error("Native pencere ozellikleri uygulanamadi: %s", exc)

    # ---- Kutu yonetimi -------------------------------------------------
    def set_boxes(self, boxes):
        """boxes: list[TranslationBox]"""
        self._boxes = boxes
        self.update()

    def clear_boxes(self):
        self._boxes = []
        self.update()

    # ---- Cizim -----------------------------------------------------------
    def paintEvent(self, event):
        if not self._boxes:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)

        bg_rgb = _hex_to_rgb(self.config.get("overlay_bg_color", "#141414"))
        opacity = self.config.get("overlay_opacity", 0.72)
        text_color = QtGui.QColor(self.config.get("overlay_text_color", "#FFFFFF"))
        base_font_size = self.config.get("font_size", 18)
        min_font_size = self.config.get("min_font_size", 10)

        # Pencere sanal masaustunun sol-ust kosesinden baslayabilir (negatif koordinatlar),
        # kutular ekran (global) koordinatinda geldigi icin pencere origin'ine gore kaydiriyoruz.
        origin = self.geometry().topLeft()

        for box in self._boxes:
            rect = QtCore.QRect(box.rect)
            rect.translate(-origin.x(), -origin.y())
            if rect.width() <= 0 or rect.height() <= 0:
                continue

            bg_color = QtGui.QColor(*bg_rgb)
            bg_color.setAlphaF(opacity)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(rect, 4, 4)

            self._draw_fitted_text(painter, rect, box.text, text_color, base_font_size, min_font_size)

        painter.end()

    def _draw_fitted_text(self, painter, rect, text, color, base_size, min_size):
        padding = 4
        inner = rect.adjusted(padding, padding, -padding, -padding)
        if inner.width() <= 0 or inner.height() <= 0:
            inner = rect

        font = QtGui.QFont("Segoe UI", base_size)
        font.setBold(True)

        size = base_size
        flags = (
            QtCore.Qt.TextFlag.TextWordWrap
            | QtCore.Qt.AlignmentFlag.AlignCenter
        )

        while size >= min_size:
            font.setPointSize(size)
            metrics = QtGui.QFontMetrics(font)
            bounding = metrics.boundingRect(inner, flags, text)
            if bounding.width() <= inner.width() and bounding.height() <= inner.height():
                break
            size -= 1
        else:
            size = min_size

        font.setPointSize(max(size, min_size))
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(inner, flags, text)


class OverlayController:
    """QApplication/overlay yasam dongusunu Qt main thread'inde yonetir.
    Diger thread'lerden show/update/hide cagrilari Qt sinyalleri uzerinden
    guvenli sekilde ana thread'e iletilir.
    """

    request_show_boxes = None  # alt siniflarda kullanilabilir

    def __init__(self, app, config):
        self.app = app
        self.window = OverlayWindow(config)
        self._bridge = _OverlayBridge()
        self._bridge.show_boxes_signal.connect(self._on_show_boxes)
        self._bridge.hide_signal.connect(self._on_hide)

    def show_boxes_threadsafe(self, boxes):
        self._bridge.show_boxes_signal.emit(boxes)

    def hide_threadsafe(self):
        self._bridge.hide_signal.emit()

    def _on_show_boxes(self, boxes):
        self.window.set_boxes(boxes)
        if not self.window.isVisible():
            self.window.show()

    def _on_hide(self):
        self.window.clear_boxes()
        self.window.hide()


class _OverlayBridge(QtCore.QObject):
    show_boxes_signal = QtCore.pyqtSignal(list)
    hide_signal = QtCore.pyqtSignal()
