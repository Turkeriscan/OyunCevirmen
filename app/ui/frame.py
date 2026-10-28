"""
Ozel pencere cercevesi.

Ust ve alt bantlar sinema seridi (letterbox) gibi tasarlandi:
    Ust bant  -> logo, program adi, mod durumu + sure sayaci, pencere dugmeleri
    Alt bant  -> jenerik gibi akan durum bilgisi (ceviri motoru, okuma, ekran karti)

Windows'ta pencere cercevesiz cizilir ama isletim sisteminin pencere
davranislari korunur: kenarlardan boyutlandirma, ekran kenarina surukleyince
yapisma (Aero Snap), Win+Ok tuslari, gorev cubugu animasyonlari, golge ve
Windows 11'in yuvarlak koseleri. Bunun icin WM_NCCALCSIZE ile Windows'un
kendi baslik cubugu kaldirilir, WM_NCHITTEST ile kenarlar Windows'a bildirilir.
"""
import ctypes
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import icons, logo
from app.ui import theme as T
from app.ui.theme import px
from app.ui.widgets import IconButton, Lamp, label

IS_WIN = os.name == "nt"

# --- Win32 sabitleri
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x20
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
HTCLIENT, HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 1, 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34


if IS_WIN:
    from ctypes import wintypes

    class _MARGINS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

    class _NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


def _frame_thickness(hwnd, horizontal):
    """Ekran olcegine gore Windows'un boyutlandirma kenari kalinligi."""
    user32 = ctypes.windll.user32
    try:
        dpi = user32.GetDpiForWindow(hwnd)
        size = user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME if horizontal else SM_CYSIZEFRAME, dpi)
        pad = user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
    except Exception:
        size = user32.GetSystemMetrics(SM_CXSIZEFRAME if horizontal else SM_CYSIZEFRAME)
        pad = user32.GetSystemMetrics(SM_CXPADDEDBORDER)
    return size + pad


# ================================================================ Title bar
class TitleBar(QtWidgets.QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(px(46))

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(16), 0, 0, 0)
        lay.setSpacing(px(10))

        mark = QtWidgets.QLabel()
        mark.setPixmap(logo.mark_pixmap(px(22)))
        lay.addWidget(mark)
        self.name = label("Oyun Çevirmen", "AppName")
        lay.addWidget(self.name)
        lay.addSpacing(px(18))

        self.lamp = Lamp(7)
        lay.addWidget(self.lamp)
        self.state = label("Beklemede", "TitleState")
        lay.addWidget(self.state)
        self.timer = label("", "TitleTimer")
        lay.addWidget(self.timer)
        lay.addStretch(1)

        self.extra = QtWidgets.QHBoxLayout()
        self.extra.setSpacing(px(4))
        lay.addLayout(self.extra)
        lay.addSpacing(px(10))

        self.btn_min = self._win_button("win_min", "Simge durumuna küçült")
        self.btn_max = self._win_button("win_max", "Ekranı kapla")
        self.btn_close = self._win_button("win_close", "Kapat (program saatin yanında çalışmaya devam eder)")
        self.btn_close.setProperty("role", "close")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)

        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(window.toggle_maximized)
        self.btn_close.clicked.connect(window.close)

    def _win_button(self, name, tip):
        b = QtWidgets.QPushButton()
        b.setObjectName("WinButton")
        b.setIcon(icons.icon(name, T.MUTED, 16, T.PAPER, width=1.2))
        b.setIconSize(QtCore.QSize(px(16), px(16)))
        b.setToolTip(tip)
        b.setAccessibleName(tip)
        b.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        b.setFixedHeight(self.height())
        return b

    def set_maximized_icon(self, maximized):
        self.btn_max.setIcon(icons.icon("win_restore" if maximized else "win_max", T.MUTED, 16, T.PAPER, width=1.2))
        self.btn_max.setToolTip("Önceki boyuta dön" if maximized else "Ekranı kapla")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            handle = self.window_.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.window_.toggle_maximized()


# ============================================================== Credits bar
class CreditsBar(QtWidgets.QFrame):
    """Alt bant: 'Ceviri  Ollama, aya-expanse:8b' gibi jenerik satirlari."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CreditsBar")
        self.setFixedHeight(px(34))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(14), 0, px(12), 0)
        lay.setSpacing(0)
        self.items = QtWidgets.QHBoxLayout()
        self.items.setSpacing(px(6))
        lay.addLayout(self.items)
        lay.addStretch(1)
        self.toast = label("", "CreditValue")
        self.toast.setStyleSheet(f"color: {T.OK};")
        lay.addWidget(self.toast)
        if not IS_WIN:
            lay.addSpacing(px(6))
            lay.addWidget(QtWidgets.QSizeGrip(self), 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        self._items = {}
        self._toast_timer = QtCore.QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self.toast.setText(""))

    def add_item(self, key, title):
        if self._items:
            self.items.addSpacing(px(10))
            sep = QtWidgets.QFrame()
            sep.setObjectName("CreditSep")
            sep.setFixedSize(1, px(12))
            self.items.addWidget(sep, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.items.addSpacing(px(10))
        lamp = Lamp(6)
        t = label(title, "CreditLabel")
        v = label("…", "CreditValue")
        self.items.addWidget(lamp)
        self.items.addWidget(t)
        self.items.addSpacing(px(2))
        self.items.addWidget(v)
        self._items[key] = (lamp, t, v)

    def set_item(self, key, value, state="off", tooltip=""):
        lamp, t, v = self._items[key]
        v.setText(value)
        lamp.set_state(state)
        for w in (lamp, t, v):
            w.setToolTip(tooltip)

    def flash(self, text, ms=2600):
        self.toast.setText("✓  " + text)
        self._toast_timer.start(ms)


# =============================================================== Window
class FramelessWindow(QtWidgets.QWidget):
    RESIZE_BORDER = 7

    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._native_ready = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)
        self.body = QtWidgets.QWidget()
        root.addWidget(self.body, 1)
        self.credits = CreditsBar(self)
        root.addWidget(self.credits)

    # ---------------------------------------------------------- pencere
    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self.title_bar.set_maximized_icon(self.isMaximized())
        super().changeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if IS_WIN and not self._native_ready:
            self._native_ready = True
            self._setup_native_frame()

    def _setup_native_frame(self):
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            dwm = ctypes.windll.dwmapi
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            margins = _MARGINS(1, 1, 1, 1)
            dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
            on = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(on), 4)
            corner = ctypes.c_int(2)  # DWMWCP_ROUND
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner), 4)
            border = ctypes.c_uint(0x002C333A)  # 0x00BBGGRR -> #3A332C (LINE), koyu ince kenar
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), 4)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def nativeEvent(self, event_type, message):
        if not IS_WIN or not self._native_ready:
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0

        if msg.message == WM_NCCALCSIZE and msg.wParam:
            # Windows'un kendi baslik cubugunu ve kenarini kaldir: tum pencere bizim.
            if self.isMaximized():
                params = ctypes.cast(msg.lParam, ctypes.POINTER(_NCCALCSIZE_PARAMS)).contents
                rc = params.rgrc[0]
                tx = _frame_thickness(msg.hWnd, True)
                ty = _frame_thickness(msg.hWnd, False)
                rc.left += tx
                rc.right -= tx
                rc.top += ty
                rc.bottom -= ty
            return True, 0

        if msg.message == WM_NCHITTEST and not self.isMaximized() and not self.isFullScreen():
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            g = self.frameGeometry()
            b = px(self.RESIZE_BORDER)
            left = x < g.left() + b
            right = x > g.right() - b
            top = y < g.top() + b
            bottom = y > g.bottom() - b
            hit = None
            if top and left:
                hit = HTTOPLEFT
            elif top and right:
                hit = HTTOPRIGHT
            elif bottom and left:
                hit = HTBOTTOMLEFT
            elif bottom and right:
                hit = HTBOTTOMRIGHT
            elif left:
                hit = HTLEFT
            elif right:
                hit = HTRIGHT
            elif top:
                hit = HTTOP
            elif bottom:
                hit = HTBOTTOM
            if hit is not None:
                return True, hit
        return False, 0
