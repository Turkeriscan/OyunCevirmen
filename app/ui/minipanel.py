"""
Mini panel: oyun oynarken ekranin kosesinde duran kucuk durum gostergesi.

- Surukleyerek tasinir, yeri hatirlanir.
- Lamba: sari = ceviriler ekranda, kirmizi = canli mod kayitta.
- Son ceviri tek satir olarak akar.
- Iki kucuk dugme: aninda tara, canli mod. Bir dugme: kontrol panelini ac.
- Ekran yakalamalarina GORUNMEZ (WDA_EXCLUDEFROMCAPTURE): programin kendi
  OCR'i paneli okuyup cevirmeye calismaz.
"""
from PyQt6 import QtCore, QtGui, QtWidgets

from app.core.overlay import exclude_from_capture
from app.ui import icons, logo
from app.ui import theme as T
from app.ui.theme import px, pxf
from app.ui.widgets import Lamp, hotkey_text


class _MiniButton(QtWidgets.QPushButton):
    def __init__(self, name, tip, parent=None):
        super().__init__(parent)
        self.setIcon(icons.icon(name, T.MUTED, 15, T.PAPER))
        self.setIconSize(QtCore.QSize(px(15), px(15)))
        self.setFixedSize(px(28), px(28))
        self.setToolTip(tip)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)


class _ModeChip(QtWidgets.QPushButton):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self._color = color
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(px(26))

    def restyle(self):
        c = self._color
        self.setStyleSheet(
            f"QPushButton {{ background: {T.RAISED}; color: {T.MUTED}; border: 1px solid {T.LINE};"
            f" border-radius: {px(13)}px; padding: 0 {px(10)}px;"
            f" font-family: \"{T.family('condensed')}\"; font-size: 8.5pt; font-weight: 600; }}"
            f"QPushButton:hover {{ color: {T.PAPER}; }}"
            f"QPushButton:checked {{ background: {c}; color: {'#1A0F0B' if c == T.REC else T.SUB_INK};"
            f" border-color: {c}; }}"
        )


class MiniPanel(QtWidgets.QWidget):
    moved = QtCore.pyqtSignal(int, int)

    def __init__(self, config, on_instant, on_live, on_open, on_hide):
        super().__init__(None)
        self.config = config
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint
                            | QtCore.Qt.WindowType.WindowStaysOnTopHint
                            | QtCore.Qt.WindowType.Tool)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Oyun Çevirmen mini panel")
        self.setFixedSize(px(320), px(84))
        self._drag = None
        self._line = ""

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(14), px(10), px(10), px(10))
        lay.setSpacing(px(6))

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(8))
        mark = QtWidgets.QLabel()
        mark.setPixmap(logo.mark_pixmap(px(16)))
        top.addWidget(mark)
        self.lamp = Lamp(6)
        top.addWidget(self.lamp)
        self.state = QtWidgets.QLabel("Beklemede")
        self.state.setStyleSheet(f"color: {T.PAPER}; font-family: \"{T.family('body_medium')}\";"
                                 f" font-size: 9pt; font-weight: 500;")
        top.addWidget(self.state)
        self.timer = QtWidgets.QLabel("")
        self.timer.setStyleSheet(f"color: {T.MUTED}; font-family: \"{T.family('mono')}\"; font-size: 8.5pt;")
        top.addWidget(self.timer)
        top.addStretch(1)
        self.chip_instant = _ModeChip("F9", T.SUB)
        self.chip_live = _ModeChip("F10", T.REC)
        self.chip_instant.clicked.connect(lambda: (on_instant(), self._resync_later()))
        self.chip_live.clicked.connect(lambda: (on_live(), self._resync_later()))
        top.addWidget(self.chip_instant)
        top.addWidget(self.chip_live)
        self.btn_open = _MiniButton("expand", "Kontrol panelini aç")
        self.btn_open.clicked.connect(on_open)
        self.btn_hide = _MiniButton("cross", "Mini paneli gizle")
        self.btn_hide.clicked.connect(on_hide)
        top.addWidget(self.btn_open)
        top.addWidget(self.btn_hide)
        lay.addLayout(top)

        self.line = QtWidgets.QLabel("")
        self.line.setStyleSheet(f"color: {T.MUTED}; font-family: \"{T.family('body')}\"; font-size: 9pt;")
        lay.addWidget(self.line)
        for b in (self.btn_open, self.btn_hide):
            b.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: {px(6)}px; }}"
                            f"QPushButton:hover {{ background: {T.RAISED}; }}")
        self._resync = None

    def _resync_later(self):
        if self._resync:
            QtCore.QTimer.singleShot(120, self._resync)

    # ------------------------------------------------------------ durum
    def update_state(self, mode, elapsed_text, last_line, hk_instant, hk_live):
        self.chip_instant.setText(hotkey_text(hk_instant))
        self.chip_live.setText(hotkey_text(hk_live))
        self.chip_instant.restyle()
        self.chip_live.restyle()
        self.chip_instant.setChecked(mode == "instant")
        self.chip_live.setChecked(mode == "live")
        if mode == "live":
            self.lamp.set_state("rec")
            self.state.setText("Canlı")
            self.timer.setText(elapsed_text)
        elif mode == "instant":
            self.lamp.set_state("sub")
            self.state.setText("Ekranda")
            self.timer.setText("")
        else:
            self.lamp.set_state("off")
            self.state.setText("Beklemede")
            self.timer.setText("")
        text = last_line or "Henüz çeviri yok."
        if text != self._line:
            self._line = text
            fm = QtGui.QFontMetrics(self.line.font())
            self.line.setText(fm.elidedText(text, QtCore.Qt.TextElideMode.ElideRight, self.width() - px(30)))
            self.line.setToolTip(text)

    # ------------------------------------------------------------- konum
    def place(self):
        pos = self.config.get("mini_panel_pos")
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            pt = QtCore.QPoint(int(pos[0]), int(pos[1]))
            if any(s.availableGeometry().contains(pt) for s in QtWidgets.QApplication.screens()):
                self.move(pt)
                return
        self.move(screen.right() - self.width() - px(24), screen.top() + px(24))

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

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bg = QtGui.QColor(T.LETTERBOX)
        bg.setAlphaF(0.94)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, pxf(12), pxf(12))
        # ust kenarda ince sari isik: perde hissi
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        g = QtGui.QLinearGradient(r.topLeft(), r.topRight())
        c = QtGui.QColor(T.SUB)
        c.setAlphaF(0.0)
        g.setColorAt(0, c)
        c.setAlphaF(0.55)
        g.setColorAt(0.5, c)
        c.setAlphaF(0.0)
        g.setColorAt(1, c)
        p.setBrush(g)
        p.drawRect(QtCore.QRectF(r.left() + pxf(24), r.top(), r.width() - pxf(48), 1.2))
        p.end()


class MiniPanelController:
    """Mini paneli olusturur, gosterir/gizler ve durumunu canli tutar.
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
            self.panel = MiniPanel(
                self.config,
                on_instant=self.o.toggle_instant,
                on_live=self.o.toggle_live,
                on_open=self.o.request_show_window,
                on_hide=self.hide,
            )
            self.panel._resync = self._sync
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
        if self.config.get("mini_panel_enabled") != visible:
            self.config["mini_panel_enabled"] = visible
            self._save()

    def _moved(self, x, y):
        self.config["mini_panel_pos"] = [x, y]
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
        import time
        from app.ui.pages.scene import timecode
        mode = getattr(self.o, "mode", "none")
        start = getattr(self.o, "live_started_at", None)
        elapsed = timecode(time.time() - start, millis=False) if (mode == "live" and start) else ""
        recent = list(getattr(self.o, "recent", []))
        last = recent[0][2] if recent else ""
        self.panel.update_state(mode, elapsed, last,
                                self.config.get("hotkey_instant", "f9"),
                                self.config.get("hotkey_live_toggle", "f10"))
