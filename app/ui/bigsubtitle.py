"""
Buyuk altyazi penceresi (4.3): bazi oyunlar TAM EKRAN (exclusive fullscreen)
modda calisirken, normal overlay penceresi (ayri bir ust pencere oldugu
icin) oyunun USTUNE CIKAMAZ - bu Windows'un kendi sinirlamasidir, program
hatasi degildir. Cozum: cevirileri BUYUK, okunakli bir pencerede IKINCI
bir monitore koymak - oyuncu goz ucuyla o ekrana bakar.

Surukleyerek tasinir, yeri hatirlanir (varsayilan: ikinci monitor varsa
oraya, yoksa birincil ekranin alt-ortasina konur).
"""
from PyQt6 import QtCore, QtGui, QtWidgets

from app.core.overlay import exclude_from_capture, paint_translation
from app.ui import theme as T
from app.ui.theme import px, pxf

DEFAULT_SIZE = (900, 220)


class BigSubtitlePanel(QtWidgets.QWidget):
    moved = QtCore.pyqtSignal(int, int)

    def __init__(self, config):
        super().__init__(None)
        self.config = config
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Oyun Çevirmen - Büyük altyazı")
        self.resize(px(DEFAULT_SIZE[0]), px(DEFAULT_SIZE[1]))
        self.setMinimumSize(px(360), px(110))
        self._drag = None
        self._text = ""

    def set_text(self, text):
        text = text or "Çeviri bekleniyor…"
        if text != self._text:
            self._text = text
            self.update()

    # ------------------------------------------------------------- konum
    def place(self):
        pos = self.config.get("big_subtitle_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            pt = QtCore.QPoint(int(pos[0]), int(pos[1]))
            if any(s.availableGeometry().contains(pt) for s in QtWidgets.QApplication.screens()):
                self.move(pt)
                return
        screens = QtWidgets.QApplication.screens()
        # Ikinci bir monitor varsa varsayilan olarak ORAYA konur - tam ekran
        # (exclusive fullscreen) oyunlarda birincil ekranin ustune cikilamaz.
        target = screens[1] if len(screens) > 1 else (screens[0] if screens else None)
        if target is None:
            return
        geo = target.availableGeometry()
        x = geo.center().x() - self.width() // 2
        y = geo.bottom() - self.height() - px(40)
        self.move(x, y)

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.moved.emit(self.x(), self.y())

    # ------------------------------------------------------------------ cizim
    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bg = QtGui.QColor(T.LETTERBOX)
        bg.setAlphaF(0.92)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, pxf(16), pxf(16))

        # Oyundaki gercek overlay stilinden BAGIMSIZ, hep "altyazi" gorunumu
        # kullanilir - bu pencerenin tek amaci buyuk/okunakli metin gostermek.
        cfg = dict(self.config)
        cfg["overlay_style"] = "subtitle"
        cfg["font_size"] = max(cfg.get("font_size", 18), 30)
        cfg["min_font_size"] = max(cfg.get("min_font_size", 10), 16)
        inner = self.rect().adjusted(px(24), px(16), -px(24), -px(16))
        paint_translation(p, inner, self._text or "Çeviri bekleniyor…", cfg)
        p.end()


class BigSubtitleController:
    """Buyuk altyazi penceresini olusturur, gosterir/gizler ve guncel tutar.
    Tum cagrilar Qt ana thread'inde yapilmalidir (Orchestrator bunu saglar)."""

    def __init__(self, config, orchestrator):
        self.config = config
        self.o = orchestrator
        self.panel = None
        self._timer = QtCore.QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._sync)

    def _ensure(self):
        if self.panel is None:
            self.panel = BigSubtitlePanel(self.config)
            self.panel.moved.connect(self._moved)
            self.panel.place()
        return self.panel

    def is_visible(self):
        return bool(self.panel and self.panel.isVisible())

    def show(self):
        p = self._ensure()
        self._sync()
        p.show()
        self._timer.start()
        self._remember(True)

    def hide(self):
        if self.panel:
            self.panel.hide()
        self._timer.stop()
        self._remember(False)

    def toggle(self):
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def _remember(self, visible):
        if self.config.get("big_subtitle_enabled") != visible:
            self.config["big_subtitle_enabled"] = visible
            self._save()

    def _moved(self, x, y):
        self.config["big_subtitle_pos"] = [x, y]
        self._save()

    def _save(self):
        try:
            from app import config as config_mod
            config_mod.save_config(self.config)
        except Exception:
            pass

    def _sync(self):
        if not self.panel:
            return
        recent = list(getattr(self.o, "recent", []))
        last = recent[0][2] if recent else ""
        self.panel.set_text(last)
