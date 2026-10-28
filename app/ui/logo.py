"""
Oyun Cevirmen logosu.

Karanlik bir sinema perdesi; alt ucte iki sari altyazi satiri. Alttaki
kisa satirdan sarkan kucuk kanca Turkcedeki "c"nin cedillasidir (c -> ç):
logo "Turkce altyazili perde" der. 16 pikselde bile okunacak kadar sade
tutuldu; koyu gorev cubugunda kaybolmasin diye ince bir kenari var.
"""
import os

from PyQt6 import QtCore, QtGui

from app.ui import theme as T


def paint_mark(p, rect, tile=True):
    """rect: QRectF (kare). tile=False ise perde cizilmez, sadece satirlar."""
    p.save()
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    s = rect.width() / 64.0
    x0, y0 = rect.x(), rect.y()

    def R(x, y, w, h):
        return QtCore.QRectF(x0 + x * s, y0 + y * s, w * s, h * s)

    if tile:
        screen = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        screen.setColorAt(0.0, QtGui.QColor("#2A241F"))
        screen.setColorAt(1.0, QtGui.QColor("#15120F"))
        p.setBrush(screen)
        edge = QtGui.QPen(QtGui.QColor("#4A4037"), max(1.0, 1.6 * s))
        p.setPen(edge)
        inset = edge.widthF() / 2
        p.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), 14 * s, 14 * s)

    sub = QtGui.QColor(T.SUB)
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(sub)
    p.drawRoundedRect(R(11, 29, 42, 8), 4 * s, 4 * s)
    p.drawRoundedRect(R(18.5, 40.5, 27, 8), 4 * s, 4 * s)

    pen = QtGui.QPen(sub, 3.6 * s)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    path = QtGui.QPainterPath()
    path.moveTo(x0 + 32 * s, y0 + 48 * s)
    path.lineTo(x0 + 32 * s, y0 + 50.6 * s)
    path.cubicTo(x0 + 35.6 * s, y0 + 50.8 * s,
                 x0 + 36 * s, y0 + 54.6 * s,
                 x0 + 32.8 * s, y0 + 55.4 * s)
    path.cubicTo(x0 + 31.6 * s, y0 + 55.7 * s,
                 x0 + 30.4 * s, y0 + 55.5 * s,
                 x0 + 29.4 * s, y0 + 55 * s)
    p.drawPath(path)
    p.restore()


def mark_pixmap(size, tile=True):
    ratio = 2
    pm = QtGui.QPixmap(size * ratio, size * ratio)
    pm.setDevicePixelRatio(ratio)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    paint_mark(p, QtCore.QRectF(0, 0, size, size), tile)
    p.end()
    return pm


def render_image(size):
    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    paint_mark(p, QtCore.QRectF(0, 0, size, size))
    p.end()
    return img


def write_assets(asset_dir=T.ASSET_DIR):
    """icon.png (tepsi simgesi) ve icon.ico (masaustu/gorev cubugu) uretir.
    Gelistirme sirasinda bir kez calistirilir; dosyalar repoda durur."""
    from PIL import Image  # pillow zaten bagimlilik listesinde

    os.makedirs(asset_dir, exist_ok=True)
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = []
    for sz in sizes:
        qimg = render_image(sz).convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        ptr = qimg.constBits()
        ptr.setsize(qimg.sizeInBytes())
        images.append(Image.frombuffer("RGBA", (sz, sz), bytes(ptr), "raw", "RGBA", 0, 1).copy())
    images[sizes.index(64)].save(os.path.join(asset_dir, "icon.png"))
    images[-1].save(os.path.join(asset_dir, "icon.ico"), sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
    return os.path.join(asset_dir, "icon.ico")
