"""
Overlay modulu: PyQt6 ile seffaf, her zaman ustte, tiklamalari gecirten
(click-through) bir pencere. Her ceviri, orijinal yazinin tam ustune cizilir.

Uc gorunum stili vardir (config "overlay_style"):
    box       Kutu     - yari saydam yuvarlak koseli kutu (varsayilan)
    subtitle  Altyazi  - kutu yok; sinema altyazisi gibi kenar cizgili, golgeli yazi
    band      Serit    - kenardan kenara koyu serit, solda ince vurgu cizgisi

Cizim mantigi paint_translation() fonksiyonundadir; kontrol panelindeki
onizleme de ayni fonksiyonu kullanir, boylece onizleme oyundakiyle birebir ayni.

Yeni gelen ceviriler kisa bir yumusak gecisle belirir, kapanirken soner
(Windows'ta "animasyon efektleri" kapaliysa gecis yapilmaz).

Onemli: SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) uygulanir, boylece
ekran kaydi / kendi ekran taramamiz bu pencereyi GORMEZ (hem gizlilik hem de
"kendi cevirisini tekrar okuma" sorununu onler).
"""
import ctypes
import logging
import os
import time

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

FADE_IN = 0.16   # saniye
FADE_OUT = 0.12

OVERLAY_STYLES = ("box", "subtitle", "band")
# config "overlay_font" -> tema yazi rolu
OVERLAY_FONTS = {
    "plex": "body_semibold",      # IBM Plex Sans (programla gelir)
    "segoe": None,                # Windows'un kendi yazi tipi
    "serif": "text_serif",        # Newsreader (sinema jenerigi havasi)
}


def exclude_from_capture(widget, clickthrough=False):
    """Pencereyi ekran yakalamalarindan gizler (Windows 10 2004+)."""
    if os.name != "nt":
        return False
    try:
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        if clickthrough:
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
    except Exception as exc:
        logger.error("Pencere ozellikleri uygulanamadi: %s", exc)
        return False


def _reduced_motion():
    try:
        from app.ui import theme
        return theme.reduced_motion()
    except Exception:
        return False


def overlay_font(cfg, size_pt):
    """Ayarlardaki yazi tipine gore QFont."""
    key = cfg.get("overlay_font", "plex")
    role = OVERLAY_FONTS.get(key, "body_semibold")
    if role:
        try:
            from app.ui import theme
            f = theme.font(role, size_pt)
            if key == "serif":
                f.setWeight(QtGui.QFont.Weight.Medium)
            return f
        except Exception:
            pass
    f = QtGui.QFont("Segoe UI", int(size_pt))
    f.setPointSizeF(size_pt)
    f.setBold(True)
    return f


def _fit_font(cfg, rect, text, flags):
    """Metni rect icine sigana kadar kucultur (en kucuk boyutun altina inmez)."""
    base = int(cfg.get("font_size", 18))
    minimum = int(cfg.get("min_font_size", 10))
    size = base
    while size > minimum:
        f = overlay_font(cfg, size)
        b = QtGui.QFontMetrics(f).boundingRect(rect, flags, text)
        if b.width() <= rect.width() and b.height() <= rect.height():
            return f
        size -= 1
    return overlay_font(cfg, max(minimum, 1))


def paint_translation(p, rect, text, cfg, alpha=1.0):
    """Tek bir ceviriyi verilen dikdortgene (QRect) cizer.

    p: aktif QPainter. rect: orijinal yazinin kapladigi alan.
    alpha: 0..1, gecis animasyonu icin genel saydamlik.
    """
    if rect.width() <= 0 or rect.height() <= 0 or not text:
        return
    style = cfg.get("overlay_style", "box")
    opacity = float(cfg.get("overlay_opacity", 0.72))
    bg = QtGui.QColor(cfg.get("overlay_bg_color", "#141414"))
    fg = QtGui.QColor(cfg.get("overlay_text_color", "#FFFFFF"))
    flags = int(QtCore.Qt.TextFlag.TextWordWrap | QtCore.Qt.AlignmentFlag.AlignCenter)

    p.save()
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
    p.setOpacity(max(0.0, min(1.0, alpha)))

    r = QtCore.QRect(rect)

    if style == "band":
        # Kenardan kenara serit: orijinal kutunun biraz disina tasar
        pad_x = max(6, r.height() // 3)
        band = r.adjusted(-pad_x, -2, pad_x, 2)
        c = QtGui.QColor(bg)
        c.setAlphaF(min(1.0, opacity + 0.12))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRect(band)
        accent = QtGui.QColor(fg)
        accent.setAlphaF(0.85)
        p.setBrush(accent)
        p.drawRect(QtCore.QRect(band.left(), band.top(), 3, band.height()))
        inner = band.adjusted(10, 3, -8, -3)
        p.setFont(_fit_font(cfg, inner, text, flags))
        p.setPen(fg)
        p.drawText(inner, flags, text)

    elif style == "subtitle":
        # Sinema altyazisi: kutu yok, kalin kenar + yumusak golge
        inner = r.adjusted(-6, -2, 6, 2)
        f = _fit_font(cfg, inner, text, flags)
        metrics = QtGui.QFontMetrics(f)
        path = QtGui.QPainterPath()
        # Satirlari tek tek ortala (QPainterPath.addText sarma yapmaz)
        lines = _wrap_lines(text, f, inner.width())
        line_h = metrics.height()
        total_h = line_h * len(lines)
        y = inner.center().y() - total_h / 2 + metrics.ascent()
        for line in lines:
            w = metrics.horizontalAdvance(line)
            path.addText(inner.center().x() - w / 2, y, f, line)
            y += line_h

        # Kenarlari yumusak golge zemini: kutu gibi gorunmez ama alttaki
        # orijinal oyun yazisini orter (Netflix altyazilarindaki gibi).
        text_box = path.boundingRect()
        plate = QtCore.QRectF(r).united(text_box).adjusted(-4, -2, 4, 2)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        layers = 6
        for i in range(layers, -1, -1):
            grow = i * 3.0
            c = QtGui.QColor(bg)
            core = min(1.0, opacity * 1.18)
            c.setAlphaF(core if i == 0 else core * 0.45 * (1.0 - i / (layers + 1)))
            p.setBrush(c)
            rr = plate.adjusted(-grow, -grow * 0.7, grow, grow * 0.7)
            p.drawRoundedRect(rr, 6 + grow, 6 + grow)

        outline = QtGui.QColor(bg)
        outline.setAlphaF(min(1.0, 0.35 + opacity))
        shadow = QtGui.QColor(0, 0, 0, int(150 * opacity))
        stroke_w = max(2.0, f.pointSizeF() * 0.22)

        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.translate(0, max(1.5, stroke_w * 0.5))
        p.setPen(QtGui.QPen(shadow, stroke_w * 1.6, QtCore.Qt.PenStyle.SolidLine,
                            QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.translate(0, -max(1.5, stroke_w * 0.5))
        p.setPen(QtGui.QPen(outline, stroke_w, QtCore.Qt.PenStyle.SolidLine,
                            QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(fg)
        p.drawPath(path)

    else:  # "box"
        c = QtGui.QColor(bg)
        c.setAlphaF(opacity)
        radius = min(6.0, r.height() / 3.0)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QtCore.QRectF(r), radius, radius)
        # cok ince ust parlama: kutu zeminden ayrissin
        edge = QtGui.QColor(255, 255, 255, int(22 * opacity))
        p.setPen(QtGui.QPen(edge, 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QtCore.QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        inner = r.adjusted(5, 3, -5, -3)
        if inner.width() <= 0 or inner.height() <= 0:
            inner = r
        p.setFont(_fit_font(cfg, inner, text, flags))
        p.setPen(fg)
        p.drawText(inner, flags, text)

    p.restore()


def _wrap_lines(text, font, width):
    metrics = QtGui.QFontMetrics(font)
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if metrics.horizontalAdvance(trial) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i: i + 2], 16) for i in (0, 2, 4))


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
        self._born = {}          # (metin, konum) -> belirme zamani
        self._fading_out = None  # kapanis basladigi zaman
        self._anim = QtCore.QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)
        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(self._virtual_desktop_geometry())

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
        if exclude_from_capture(self, clickthrough=True):
            logger.info("Overlay ekran yakalamadan haric tutuldu (WDA_EXCLUDEFROMCAPTURE).")
        elif os.name == "nt":
            logger.warning("SetWindowDisplayAffinity basarisiz oldu (eski Windows surumu olabilir).")

    # ---- Kutu yonetimi -------------------------------------------------
    @staticmethod
    def _key(box):
        r = box.rect
        # Kucuk titremeler (1-2 px) yeni kutu sayilmasin
        return (box.text, r.x() // 6, r.y() // 6)

    def set_boxes(self, boxes):
        """boxes: list[TranslationBox]"""
        now = time.monotonic()
        animate = not _reduced_motion()
        born = {}
        for b in boxes:
            k = self._key(b)
            born[k] = self._born.get(k, now if animate else 0.0)
        self._born = born
        self._boxes = boxes
        self._fading_out = None
        if animate:
            self._anim.start()
        self.update()

    def clear_boxes(self):
        self._boxes = []
        self._born = {}
        self._fading_out = None
        self._anim.stop()
        self.update()

    def temporarily_hide(self):
        """Tutma-ile-goster kisayolu (4.2) basili tutulurken: kutulari
        SILMEDEN aninda gizler - fade-out YOK, cunku kullanici orijinal
        yaziyi HEMEN gormek ister. restore_after_reveal() ile geri gelir."""
        self._anim.stop()
        self.hide()

    def restore_after_reveal(self):
        """temporarily_hide()'in simetrigi: tus birakilinca, SAKLANAN ayni
        kutular (yeniden tarama yapmadan) aninda geri gosterilir."""
        if self._boxes:
            self.show()
            self.update()

    def fade_out_and_hide(self):
        if not self.isVisible() or not self._boxes or _reduced_motion():
            self.clear_boxes()
            self.hide()
            return
        self._fading_out = time.monotonic()
        self._anim.start()

    def _tick(self):
        now = time.monotonic()
        if self._fading_out is not None:
            if now - self._fading_out >= FADE_OUT:
                self.clear_boxes()
                self.hide()
                return
        elif all(now - t >= FADE_IN for t in self._born.values()):
            self._anim.stop()
        self.update()

    # ---- Cizim -----------------------------------------------------------
    def paintEvent(self, event):
        if not self._boxes:
            return
        painter = QtGui.QPainter(self)
        now = time.monotonic()
        out = 1.0
        if self._fading_out is not None:
            out = max(0.0, 1.0 - (now - self._fading_out) / FADE_OUT)

        # Pencere sanal masaustunun sol-ust kosesinden baslayabilir (negatif koordinatlar),
        # kutular ekran (global) koordinatinda geldigi icin pencere origin'ine gore kaydiriyoruz.
        origin = self.geometry().topLeft()
        for box in self._boxes:
            rect = QtCore.QRect(box.rect)
            rect.translate(-origin.x(), -origin.y())
            t = self._born.get(self._key(box), 0.0)
            a = 1.0 if t == 0.0 else min(1.0, (now - t) / FADE_IN)
            a = 1 - (1 - a) ** 3  # yumusak yavaslama
            paint_translation(painter, rect, box.text, self.config, alpha=a * out)
        painter.end()


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
        self._bridge.temp_hide_signal.connect(self._on_temp_hide)
        self._bridge.restore_signal.connect(self._on_restore)

    def show_boxes_threadsafe(self, boxes):
        self._bridge.show_boxes_signal.emit(boxes)

    def hide_threadsafe(self):
        self._bridge.hide_signal.emit()

    def temporarily_hide_threadsafe(self):
        """Tutma-ile-goster kisayolu (4.2) basili tutulurken cagirilir -
        kisayol kancasi ayri bir thread'de calisir."""
        self._bridge.temp_hide_signal.emit()

    def restore_after_reveal_threadsafe(self):
        self._bridge.restore_signal.emit()

    def refresh(self):
        """Gorunum ayarlari degisince ekrandaki cevirileri yeniden ciz."""
        self.window.update()

    def _on_show_boxes(self, boxes):
        self.window.set_boxes(boxes)
        if not self.window.isVisible():
            self.window.show()

    def _on_hide(self):
        self.window.fade_out_and_hide()

    def _on_temp_hide(self):
        self.window.temporarily_hide()

    def _on_restore(self):
        self.window.restore_after_reveal()


class _OverlayBridge(QtCore.QObject):
    show_boxes_signal = QtCore.pyqtSignal(list)
    hide_signal = QtCore.pyqtSignal()
    temp_hide_signal = QtCore.pyqtSignal()
    restore_signal = QtCore.pyqtSignal()
