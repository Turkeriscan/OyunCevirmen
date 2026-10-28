"""
Programa ozel cizilmis ikon seti.

Hepsi 24x24 izgarada, 1.6 kalinliginda yuvarlak uclu cizgilerle cizildi;
ayni dilde konusurlar. Renk cizim aninda verilir, boylece tek ikon hem
soluk (pasif) hem parlak (aktif) halde kullanilabilir.
"""
from PyQt6 import QtCore, QtGui, QtSvg

from app.ui import theme as T

_STROKE = (
    'fill="none" stroke="{c}" stroke-width="{w}" '
    'stroke-linecap="round" stroke-linejoin="round"'
)

# Yollar: {s} -> cizgi ozellikleri, {c} -> renk (dolgu gerekenler icin)
_PATHS = {
    # Sinema perdesi + altta iki altyazi satiri
    "scene": (
        '<rect x="2.8" y="4.5" width="18.4" height="15" rx="2.2" {s}/>'
        '<path d="M7.5 14.2h9M9.5 17h5" {s}/>'
    ),
    # Ust uste iki konusma balonu: kaynak dil -> Turkce
    "translate": (
        '<path d="M4 5.5h9a1.5 1.5 0 0 1 1.5 1.5v5a1.5 1.5 0 0 1-1.5 1.5H8.5L5.5 16v-2.5H4'
        'A1.5 1.5 0 0 1 2.5 12V7A1.5 1.5 0 0 1 4 5.5z" {s}/>'
        '<path d="M14.5 10h5.5A1.5 1.5 0 0 1 21.5 11.5v5A1.5 1.5 0 0 1 20 18h-1v2.5L16 18h-4.5'
        'A1.5 1.5 0 0 1 10 16.5v-3" {s}/>'
    ),
    # Altyazi kutusu + metin boyutu
    "appearance": (
        '<rect x="2.8" y="13" width="18.4" height="6.5" rx="1.6" {s}/>'
        '<path d="M6.5 4.5h7M10 4.5v6M15.5 7.5h4M17.5 7.5v3" {s}/>'
    ),
    "keyboard": (
        '<rect x="2.5" y="6" width="19" height="12" rx="2" {s}/>'
        '<path d="M6 9.5h.01M9.3 9.5h.01M12.6 9.5h.01M15.9 9.5h.01M18 9.5h.01'
        'M6.8 12.5h.01M10.1 12.5h.01M13.4 12.5h.01M16.7 12.5h.01M8 15.2h8" {s}/>'
    ),
    "sliders": (
        '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1" {s}/>'
        '<circle cx="15" cy="7" r="2" {s}/><circle cx="9" cy="12" r="2" {s}/>'
        '<circle cx="17" cy="17" r="2" {s}/>'
    ),
    "log": (
        '<path d="M6 3.5h8.5L19 8v11.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z" {s}/>'
        '<path d="M14 3.5V8.5h5M8.5 12.5h7M8.5 15.5h7M8.5 9.5h3" {s}/>'
    ),
    "pip": (
        '<rect x="2.8" y="4.5" width="18.4" height="15" rx="2.2" {s}/>'
        '<rect x="12" y="12" width="6.5" height="4.6" rx="1" {s}/>'
    ),
    "refresh": (
        '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" {s}/><path d="M19.6 4.5v3.8h-3.8" {s}/>'
    ),
    "copy": (
        '<rect x="8.5" y="8.5" width="11" height="11" rx="1.8" {s}/>'
        '<path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5" {s}/>'
    ),
    "folder": (
        '<path d="M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4l2 2.2h8A1.5 1.5 0 0 1 20.5 9.2V17.5A1.5 1.5 0 0 1 19 19H5'
        'a1.5 1.5 0 0 1-1.5-1.5z" {s}/>'
    ),
    "monitor": (
        '<rect x="3" y="4.5" width="18" height="12" rx="1.8" {s}/><path d="M9 20h6M12 16.5V20" {s}/>'
    ),
    "check": '<path d="M5 12.5l4.2 4.2L19 7" {s}/>',
    "cross": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11" {s}/>',
    "chevron_down": '<path d="M7 10l5 5 5-5" {s}/>',
    "chevron_right": '<path d="M10 7l5 5-5 5" {s}/>',
    "chevron_left": '<path d="M14 7l-5 5 5 5" {s}/>',
    "minus": '<path d="M6 12h12" {s}/>',
    "plus": '<path d="M12 6v12M6 12h12" {s}/>',
    "eye": (
        '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" {s}/>'
        '<circle cx="12" cy="12" r="2.8" {s}/>'
    ),
    "expand": '<path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5l-6 6M4.5 19.5l6-6" {s}/>',
    "reset": '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" {s}/><path d="M4.4 4.5v3.8h3.8" {s}/>',
    "gpu": (
        '<rect x="3" y="7" width="18" height="10" rx="1.6" {s}/>'
        '<circle cx="9" cy="12" r="2.4" {s}/><path d="M14.5 10.5h3.5M14.5 13.5h3.5M6 17v2.5M10 17v2.5" {s}/>'
    ),
    # Pencere dugmeleri: Windows 11 ile ayni ince cizgi
    "win_min": '<path d="M7 12h10" {s}/>',
    "win_max": '<rect x="7" y="7" width="10" height="10" rx="1.4" {s}/>',
    "win_restore": (
        '<rect x="7" y="9" width="8" height="8" rx="1.2" {s}/>'
        '<path d="M9.5 9V8.2A1.2 1.2 0 0 1 10.7 7H16a1 1 0 0 1 1 1v5.3a1.2 1.2 0 0 1-1.2 1.2H15" {s}/>'
    ),
    "win_close": '<path d="M7.5 7.5l9 9M16.5 7.5l-9 9" {s}/>',
}

_cache = {}


def svg(name, color, width=1.6):
    body = _PATHS[name].format(s=_STROKE.format(c=color, w=width), c=color)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'


def pixmap(name, color=T.MUTED, size=20, width=1.6):
    """Ikonu istenen piksel boyutunda, keskin (2x) cizer."""
    key = (name, color, size, width)
    if key in _cache:
        return _cache[key]
    ratio = 2.0
    pm = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg(name, color, width).encode("utf-8")))
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(ratio)
    _cache[key] = pm
    return pm


def icon(name, color=T.MUTED, size=20, active_color=None, width=1.6):
    """Normal / uzerine gelince / secili halleri olan QIcon."""
    ic = QtGui.QIcon()
    ic.addPixmap(pixmap(name, color, size, width), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
    hi = active_color or T.PAPER
    ic.addPixmap(pixmap(name, hi, size, width), QtGui.QIcon.Mode.Active, QtGui.QIcon.State.Off)
    ic.addPixmap(pixmap(name, hi, size, width), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
    ic.addPixmap(pixmap(name, hi, size, width), QtGui.QIcon.Mode.Active, QtGui.QIcon.State.On)
    ic.addPixmap(pixmap(name, T.FAINT, size, width), QtGui.QIcon.Mode.Disabled, QtGui.QIcon.State.Off)
    return ic
