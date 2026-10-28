"""
Arayuzun yapi taslari. Hepsi theme.py'deki renk/olcu/yazi rollerini kullanir;
hicbiri kendi rengini uydurmaz.
"""
import time

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import icons
from app.ui import theme as T
from app.ui.theme import px


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def label(text, name=None, wrap=False, selectable=False):
    lbl = QtWidgets.QLabel(text)
    if name:
        lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    if selectable:
        lbl.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def hline():
    line = QtWidgets.QFrame()
    line.setObjectName("Separator")
    line.setFixedHeight(1)
    return line


# =============================================================== Combo
class Combo(QtWidgets.QComboBox):
    """Kendi ok isaretini cizen acilir liste (Qt'nin varsayilan oku temaya uymuyor)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QtWidgets.QListView())
        self.view().setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(12)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        size = px(16)
        x = self.width() - px(12) - size
        y = (self.height() - size) // 2
        color = T.PAPER if self.hasFocus() or self.underMouse() else T.MUTED
        p.drawPixmap(x, y, icons.pixmap("chevron_down", color, size))
        p.end()

    def wheelEvent(self, event):
        # Sayfa kaydirilirken yanlislikla secim degismesin
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


# ============================================================ IconButton
class IconButton(QtWidgets.QPushButton):
    def __init__(self, name, tooltip="", size=18, color=T.MUTED, active=None, checkable=False, parent=None):
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIcon(icons.icon(name, color, size, active))
        self.setIconSize(QtCore.QSize(px(size), px(size)))
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCheckable(checkable)
        self.setFixedSize(px(size + 14), px(size + 14))


def text_button(text, name=None, icon_name=None, icon_color=T.MUTED):
    b = QtWidgets.QPushButton(text)
    if name:
        b.setObjectName(name)
    b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    if icon_name:
        b.setIcon(icons.icon(icon_name, icon_color, 16))
        b.setIconSize(QtCore.QSize(px(16), px(16)))
    return b


# ============================================================== Keycaps
KEY_NAMES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "space": "Boşluk",
             "windows": "Win", "esc": "Esc", "tab": "Tab"}


def hotkey_parts(value):
    parts = [p for p in (value or "").lower().split("+") if p]
    return [KEY_NAMES.get(p, p.upper() if len(p) <= 3 else p.capitalize()) for p in parts]


def hotkey_text(value):
    return " + ".join(hotkey_parts(value))


class Keycaps(QtWidgets.QWidget):
    """Bir tus kombinasyonunu gercek tus kapaklari gibi cizer: [Ctrl] + [F9]"""

    def __init__(self, value="", size="md", parent=None):
        super().__init__(parent)
        self._parts = hotkey_parts(value)
        self._size = size
        self._accent = False
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    def set_value(self, value):
        self._parts = hotkey_parts(value)
        self.updateGeometry()
        self.update()

    def set_accent(self, on):
        self._accent = on
        self.update()

    def _metrics(self):
        if self._size == "lg":
            return T.font("condensed", 13), px(40), px(12), px(8)
        if self._size == "sm":
            return T.font("body_semibold", 8.5), px(22), px(6), px(4)
        return T.font("condensed", 10.5), px(30), px(9), px(6)

    def sizeHint(self):
        f, h, pad, gap = self._metrics()
        fm = QtGui.QFontMetrics(f)
        w = 0
        for i, part in enumerate(self._parts):
            w += max(h, fm.horizontalAdvance(part) + pad * 2)
            if i < len(self._parts) - 1:
                w += gap * 2 + fm.horizontalAdvance("+")
        return QtCore.QSize(max(w, h), h + px(3))

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        f, h, pad, gap = self._metrics()
        fm = QtGui.QFontMetrics(f)
        p.setFont(f)
        x = 0.0
        radius = px(6) if self._size != "sm" else px(4)
        for i, part in enumerate(self._parts):
            w = max(h, fm.horizontalAdvance(part) + pad * 2)
            body = QtCore.QRectF(x, 0, w, h)
            # tusun alt kalinligi (3D his)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor("#0F0D0B"))
            p.drawRoundedRect(body.translated(0, px(3)), radius, radius)
            grad = QtGui.QLinearGradient(body.topLeft(), body.bottomLeft())
            if self._accent:
                grad.setColorAt(0, QtGui.QColor(T.SUB_HI))
                grad.setColorAt(1, QtGui.QColor(T.SUB))
            else:
                grad.setColorAt(0, QtGui.QColor("#3A332C"))
                grad.setColorAt(1, QtGui.QColor("#2C2621"))
            p.setBrush(grad)
            p.setPen(QtGui.QPen(QtGui.QColor("#4A4138" if not self._accent else T.SUB), 1))
            p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
            p.setPen(QtGui.QColor(T.SUB_INK if self._accent else T.PAPER))
            p.drawText(body, QtCore.Qt.AlignmentFlag.AlignCenter, part)
            x += w
            if i < len(self._parts) - 1:
                p.setPen(QtGui.QColor(T.FAINT))
                plus_w = fm.horizontalAdvance("+")
                p.drawText(QtCore.QRectF(x + gap, 0, plus_w, h), QtCore.Qt.AlignmentFlag.AlignCenter, "+")
                x += gap * 2 + plus_w
        p.end()


# ======================================================= HotkeyRecorder
_QT_TO_KEYBOARD = {
    **{getattr(QtCore.Qt.Key, f"Key_F{i}"): f"f{i}" for i in range(1, 13)},
    **{getattr(QtCore.Qt.Key, f"Key_{c}"): c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{getattr(QtCore.Qt.Key, f"Key_{d}"): d for d in "0123456789"},
    QtCore.Qt.Key.Key_Insert: "insert", QtCore.Qt.Key.Key_Home: "home",
    QtCore.Qt.Key.Key_End: "end", QtCore.Qt.Key.Key_PageUp: "page up",
    QtCore.Qt.Key.Key_PageDown: "page down", QtCore.Qt.Key.Key_Pause: "pause",
    QtCore.Qt.Key.Key_ScrollLock: "scroll lock",
}


class HotkeyRecorder(QtWidgets.QFrame):
    """Kisayolu tiklayip tusa basarak degistirmeyi saglar.

    Kayit sirasinda programin kendi global kisayollari durdurulur (yoksa
    F9'a basip atamaya calisirken tarama baslar); on_record_start/end bunun icin.
    """
    changed = QtCore.pyqtSignal(str)

    def __init__(self, value="f9", on_record_start=None, on_record_end=None, parent=None):
        super().__init__(parent)
        self._value = value
        self._recording = False
        self._on_start = on_record_start
        self._on_end = on_record_end
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(12))
        lay.addStretch(1)
        self.caps = Keycaps(value, "md")
        lay.addWidget(self.caps)
        self.prompt = label("", "Faint")
        self.prompt.hide()
        lay.addWidget(self.prompt)
        self.button = text_button("Değiştir", "Quiet")
        self.button.clicked.connect(self.start_recording)
        lay.addWidget(self.button)

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.caps.set_value(value)

    def start_recording(self):
        if self._recording:
            return
        self._recording = True
        if self._on_start:
            self._on_start()
        self.caps.hide()
        self.prompt.setText("Yeni tuşa bas.  Esc ile vazgeç.")
        self.prompt.setStyleSheet(f"color: {T.SUB};")
        self.prompt.show()
        self.button.setText("Vazgeç")
        self.button.clicked.disconnect()
        self.button.clicked.connect(self.cancel)
        self.setFocus()
        self.grabKeyboard()

    def _finish(self):
        self.releaseKeyboard()
        self._recording = False
        self.prompt.hide()
        self.caps.show()
        self.button.setText("Değiştir")
        self.button.clicked.disconnect()
        self.button.clicked.connect(self.start_recording)
        if self._on_end:
            self._on_end()

    def cancel(self):
        if self._recording:
            self._finish()

    def keyPressEvent(self, event):
        if not self._recording:
            return super().keyPressEvent(event)
        key = event.key()
        if key == QtCore.Qt.Key.Key_Escape:
            self.cancel()
            return
        if key in (QtCore.Qt.Key.Key_Control, QtCore.Qt.Key.Key_Shift,
                   QtCore.Qt.Key.Key_Alt, QtCore.Qt.Key.Key_Meta):
            mods = self._mods(event.modifiers())
            self.prompt.setText((" + ".join(KEY_NAMES[m] for m in mods) + " + …") if mods else "Yeni tuşa bas.")
            return
        name = _QT_TO_KEYBOARD.get(key)
        if not name:
            self.prompt.setText("Bu tuş kullanılamaz. F tuşları, harf veya rakam dene.")
            return
        mods = self._mods(event.modifiers())
        if len(name) == 1 and not mods:
            self.prompt.setText("Harf ve rakamlar oyunla çakışır; Ctrl, Alt veya Shift ile birlikte bas.")
            return
        self._value = "+".join(mods + [name])
        self.caps.set_value(self._value)
        self._finish()
        self.changed.emit(self._value)

    @staticmethod
    def _mods(m):
        out = []
        if m & QtCore.Qt.KeyboardModifier.ControlModifier:
            out.append("ctrl")
        if m & QtCore.Qt.KeyboardModifier.AltModifier:
            out.append("alt")
        if m & QtCore.Qt.KeyboardModifier.ShiftModifier:
            out.append("shift")
        return out

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self._recording:
            QtCore.QTimer.singleShot(0, self.cancel)


# ================================================================ Stepper
class Stepper(QtWidgets.QFrame):
    """[ - ]  6  [ + ]  — tam sayi ayarlari icin."""
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, minimum, maximum, step=1, suffix="", parent=None):
        super().__init__(parent)
        self.setObjectName("Stepper")
        self._min, self._max, self._step, self._suffix = minimum, maximum, step, suffix
        self._value = minimum
        self.setStyleSheet(
            f"#Stepper {{ background: {T.RAISED}; border: 1px solid {T.LINE}; border-radius: {px(7)}px; }}"
        )
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setFixedHeight(px(36))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(3), px(3), px(3), px(3))
        lay.setSpacing(0)
        self.minus = IconButton("minus", "Azalt", 14)
        self.plus = IconButton("plus", "Artır", 14)
        self.text = QtWidgets.QLabel()
        self.text.setObjectName("ValueLabel")
        self.text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.text.setMinimumWidth(px(64))
        lay.addWidget(self.minus)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.plus)
        self.minus.setAutoRepeat(True)
        self.plus.setAutoRepeat(True)
        self.minus.clicked.connect(lambda: self.setValue(self._value - self._step))
        self.plus.clicked.connect(lambda: self.setValue(self._value + self._step))
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._render()

    def value(self):
        return self._value

    def setValue(self, v, emit=True):
        v = max(self._min, min(self._max, int(v)))
        if v == self._value:
            self._render()
            return
        self._value = v
        self._render()
        if emit:
            self.valueChanged.emit(v)

    def _render(self):
        self.text.setText(f"{self._value:,}".replace(",", ".") + (f" {self._suffix}" if self._suffix else ""))
        self.minus.setEnabled(self._value > self._min)
        self.plus.setEnabled(self._value < self._max)

    def keyPressEvent(self, e):
        if e.key() in (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Plus):
            self.setValue(self._value + self._step)
        elif e.key() in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Minus):
            self.setValue(self._value - self._step)
        else:
            super().keyPressEvent(e)


# ============================================================ ValueSlider
class ValueSlider(QtWidgets.QWidget):
    """Kaydirici + sagda bicimlenmis deger. Ondalik degerler icin 'scale'."""
    valueChanged = QtCore.pyqtSignal(float)

    def __init__(self, minimum, maximum, step=1.0, fmt="{:.0f}", parent=None):
        super().__init__(parent)
        self._scale = 1.0 / step
        self._fmt = fmt
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(12))
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(int(round(minimum * self._scale)), int(round(maximum * self._scale)))
        self.slider.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.text = QtWidgets.QLabel()
        self.text.setObjectName("ValueLabel")
        self.text.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.text.setMinimumWidth(px(58))
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.text)
        self.slider.valueChanged.connect(self._changed)
        self._changed(self.slider.value())

    def value(self):
        return self.slider.value() / self._scale

    def setValue(self, v):
        self.slider.setValue(int(round(v * self._scale)))
        self._changed(self.slider.value())

    def _changed(self, raw):
        v = raw / self._scale
        self.text.setText(self._fmt.format(v))
        self.valueChanged.emit(v)


# =========================================================== ColorSwatch
class ColorSwatch(QtWidgets.QPushButton):
    changed = QtCore.pyqtSignal()

    def __init__(self, hex_color, title="Renk seç", parent=None):
        super().__init__(parent)
        self.setObjectName("Swatch")
        self._hex = hex_color
        self._title = title
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        self.setText(self._hex.upper())
        size = px(18)
        pm = QtGui.QPixmap(size * 2, size * 2)
        pm.setDevicePixelRatio(2)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtGui.QPen(QtGui.QColor("#5A5047"), 1))
        p.setBrush(QtGui.QColor(self._hex))
        p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, size - 1, size - 1), px(4), px(4))
        p.end()
        self.setIcon(QtGui.QIcon(pm))
        self.setIconSize(QtCore.QSize(size, size))

    def _pick(self):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self._hex), self, self._title)
        if color.isValid():
            self.set_hex(color.name())
            self.changed.emit()

    def set_hex(self, value):
        self._hex = value
        self._refresh()

    def hex(self):
        return self._hex


# =================================================================== Lamp
class Lamp(QtWidgets.QWidget):
    """Kucuk durum lambasi. 'rec' durumunda nefes alir gibi yanip soner."""
    COLORS = {"off": T.FAINT, "ok": T.OK, "sub": T.SUB, "rec": T.REC, "bad": T.REC}

    def __init__(self, size=8, parent=None):
        super().__init__(parent)
        self._state = "off"
        self._d = px(size)
        self.setFixedSize(self._d + px(8), self._d + px(8))
        self._t0 = time.monotonic()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.update)

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        if state == "rec" and not T.reduced_motion():
            self._t0 = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        import math
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        c = QtGui.QColor(self.COLORS.get(self._state, T.FAINT))
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        if self._state in ("ok", "sub", "rec", "bad"):
            k = 1.0
            if self._timer.isActive():
                k = 0.55 + 0.45 * (0.5 + 0.5 * math.sin((time.monotonic() - self._t0) * 3.2))
            glow = QtGui.QRadialGradient(center, self.width() / 2)
            g = QtGui.QColor(c)
            g.setAlphaF(0.45 * k)
            glow.setColorAt(0, g)
            g2 = QtGui.QColor(c)
            g2.setAlphaF(0)
            glow.setColorAt(1, g2)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(center, self.width() / 2, self.height() / 2)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(center, self._d / 2, self._d / 2)
        p.end()


# ============================================================ Settings
class SettingsGroup(QtWidgets.QFrame):
    """Yuvarlak koseli panel; icindeki satirlar ince cizgilerle ayrilir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsGroup")
        self.setStyleSheet(
            f"#SettingsGroup {{ background: {T.SURFACE}; border: 1px solid {T.LINE_SOFT};"
            f" border-radius: {px(12)}px; }}"
        )
        self._lay = QtWidgets.QVBoxLayout(self)
        self._lay.setContentsMargins(0, px(2), 0, px(2))
        self._lay.setSpacing(0)
        self._count = 0

    def add(self, widget):
        if self._count:
            sep = hline()
            wrap = QtWidgets.QWidget()
            wl = QtWidgets.QHBoxLayout(wrap)
            wl.setContentsMargins(px(20), 0, px(20), 0)
            wl.addWidget(sep)
            self._lay.addWidget(wrap)
        self._lay.addWidget(widget)
        self._count += 1
        return widget

    def row(self, title, hint=None, control=None, stretch_control=False):
        return self.add(SettingRow(title, hint, control, stretch_control))


class SettingRow(QtWidgets.QWidget):
    """Solda baslik + aciklama, sagda kontrol."""

    def __init__(self, title, hint=None, control=None, stretch_control=False, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(20), px(14), px(20), px(14))
        lay.setSpacing(px(24))
        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(px(3))
        texts.addWidget(label(title, "RowTitle"))
        if hint:
            texts.addWidget(label(hint, "RowHint", wrap=True))
        tw = QtWidgets.QWidget()
        tw.setLayout(texts)
        tw.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        lay.addWidget(tw, 5)
        self.control_holder = QtWidgets.QWidget()
        cl = QtWidgets.QHBoxLayout(self.control_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(px(8))
        if not stretch_control:
            cl.addStretch(1)
        if isinstance(control, QtWidgets.QLayout):
            cl.addLayout(control)
        elif control is not None:
            cl.addWidget(control, 1 if stretch_control else 0)
        lay.addWidget(self.control_holder, 4)


def section_header(title, lead=None):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(px(2), px(8), 0, px(2))
    lay.setSpacing(px(2))
    lay.addWidget(label(title, "SectionTitle"))
    if lead:
        lay.addWidget(label(lead, "SectionLead", wrap=True))
    return w


# ============================================================ StyleTile
class StyleTile(QtWidgets.QAbstractButton):
    """Gorsel secim karti: ustte kucuk resim, altta ad ve aciklama."""

    def __init__(self, title, caption, painter_fn, parent=None):
        super().__init__(parent)
        self._title = title
        self._caption = caption
        self._paint_art = painter_fn
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(px(150))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)

    def sizeHint(self):
        return QtCore.QSize(px(200), px(150))

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        checked = self.isChecked()
        hover = self.underMouse()
        p.setPen(QtGui.QPen(QtGui.QColor(T.SUB if checked else (T.LINE if hover else T.LINE_SOFT)),
                            1.5 if checked else 1))
        p.setBrush(QtGui.QColor(T.SURFACE))
        p.drawRoundedRect(r, px(12), px(12))

        art = QtCore.QRectF(r.x() + px(10), r.y() + px(10), r.width() - px(20), px(78))
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(art, px(8), px(8))
        p.save()
        p.setClipPath(clip)
        sky = QtGui.QLinearGradient(art.topLeft(), art.bottomLeft())
        sky.setColorAt(0, QtGui.QColor("#3B4560"))
        sky.setColorAt(1, QtGui.QColor("#8C6A63"))
        p.fillRect(art, sky)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(30, 26, 36, 230))
        hill = QtGui.QPolygonF([
            QtCore.QPointF(art.left(), art.bottom() - px(18)),
            QtCore.QPointF(art.left() + art.width() * 0.35, art.bottom() - px(34)),
            QtCore.QPointF(art.left() + art.width() * 0.7, art.bottom() - px(20)),
            QtCore.QPointF(art.right(), art.bottom() - px(30)),
            QtCore.QPointF(art.right(), art.bottom()), QtCore.QPointF(art.left(), art.bottom()),
        ])
        p.drawPolygon(hill)
        if self._paint_art:
            self._paint_art(p, art)
        p.restore()

        if checked:
            badge = QtCore.QRectF(art.right() - px(26), art.top() + px(6), px(20), px(20))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(T.SUB))
            p.drawEllipse(badge)
            p.drawPixmap(badge.adjusted(px(3), px(3), -px(3), -px(3)).toRect(),
                         icons.pixmap("check", T.SUB_INK, px(14), 2.4))

        p.setPen(QtGui.QColor(T.PAPER))
        p.setFont(T.font("body_semibold", 10))
        p.drawText(QtCore.QRectF(r.x() + px(14), art.bottom() + px(10), r.width() - px(28), px(20)),
                   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, self._title)
        p.setPen(QtGui.QColor(T.FAINT))
        p.setFont(T.font("body", 8.5))
        p.drawText(QtCore.QRectF(r.x() + px(14), art.bottom() + px(30), r.width() - px(28), px(18)),
                   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, self._caption)

        if self.hasFocus():
            p.setPen(QtGui.QPen(QtGui.QColor(T.PAPER), 1, QtCore.Qt.PenStyle.DotLine))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(3, 3, -3, -3), px(10), px(10))
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


# ============================================================ FadeStack
class FadeStack(QtWidgets.QStackedWidget):
    """Sayfa degisirken kisa bir capraz gecis yapar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = None

    def fade_to(self, index):
        if index == self.currentIndex():
            return
        if T.reduced_motion():
            self.setCurrentIndex(index)
            return
        self.setCurrentIndex(index)
        w = self.currentWidget()
        eff = QtWidgets.QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QtCore.QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        anim.start()
        self._anim = anim


def scroll_page(inner):
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    return area


class Page(QtWidgets.QWidget):
    """Standart sayfa iskeleti: baslik, giris cumlesi, icerik."""

    def __init__(self, title, lead=None, max_width=880, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.inner = QtWidgets.QWidget()
        self.inner.setMaximumWidth(px(max_width))
        center = QtWidgets.QHBoxLayout()
        center.setContentsMargins(px(40), px(34), px(40), px(40))
        center.addWidget(self.inner, 1)
        holder = QtWidgets.QWidget()
        holder.setLayout(center)
        outer.addWidget(scroll_page(holder))
        self.body = QtWidgets.QVBoxLayout(self.inner)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(px(14))
        head = QtWidgets.QVBoxLayout()
        head.setSpacing(px(6))
        head.addWidget(label(title, "PageTitle"))
        if lead:
            head.addWidget(label(lead, "PageLead", wrap=True))
        self.body.addLayout(head)
        self.body.addSpacing(px(10))

    def finish(self):
        self.body.addStretch(1)
