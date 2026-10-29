"""
Gorunum sayfasi: cevirilerin oyunda nasil gorunecegi.

Ustteki onizleme, gercek overlay'in kullandigi paint_translation()
fonksiyonuyla cizilir; burada ne gorursen oyunda da o.
"Orijinali goster" dugmesi cevirileri gecici kaldirip alttaki oyun
yazisini gosterir: karsilastirma icin.
"""
from PyQt6 import QtCore, QtGui, QtWidgets

from app.core.overlay import paint_translation
from app.ui import theme as T
from app.ui.theme import px, pxf
from app.ui.widgets import (ColorSwatch, Combo, IconButton, Page, SettingsGroup, Stepper,
                            StyleTile, ValueSlider, label, section_header)

STYLES = [
    ("box", "Kutu", "Yarı saydam kutu; her oyunda okunur."),
    ("subtitle", "Altyazı", "Kutu yok; film altyazısı gibi kenarlı yazı."),
    ("band", "Şerit", "Kenardan kenara koyu şerit, solda ince çizgi."),
    ("bottom_strip", "Altyazı şeridi", "Orijinal yazının üzerine değil; tüm "
     "çeviriler ekranın en altında birleşik tek bir şeritte gösterilir."),
]
FONTS = [
    ("plex", "IBM Plex Sans", "Programla gelir; küçük boyutta bile net."),
    ("segoe", "Segoe UI", "Windows'un kendi yazı tipi."),
    ("serif", "Newsreader", "Tırnaklı; sinema jeneriği havası."),
]
PALETTES = [
    ("Gece", "#141414", "#FFFFFF", 0.72),
    ("Altyazı sarısı", "#0E0D0B", "#F2C14E", 0.78),
    ("Yüksek kontrast", "#000000", "#FFFFFF", 0.95),
    ("Kâğıt", "#F1EADB", "#1B1714", 0.92),
]


class GamePreview(QtWidgets.QWidget):
    """Kucuk bir oyun sahnesi: HUD, diyalog kutusu, etkilesim istemi."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.show_original = False
        self.setMinimumHeight(px(260))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return max(px(260), min(px(400), int(w / 2.2)))

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        r = QtCore.QRectF(self.rect())
        w, h = r.width(), r.height()
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, pxf(14), pxf(14))
        p.setClipPath(clip)

        # --- gokyuzu, gunes, daglar, orman
        sky = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        sky.setColorAt(0.0, QtGui.QColor("#1E2A44"))
        sky.setColorAt(0.45, QtGui.QColor("#5B4A66"))
        sky.setColorAt(0.75, QtGui.QColor("#C98366"))
        sky.setColorAt(1.0, QtGui.QColor("#E9B07A"))
        p.fillRect(r, sky)
        sun = QtGui.QRadialGradient(QtCore.QPointF(w * 0.7, h * 0.56), h * 0.5)
        sun.setColorAt(0.0, QtGui.QColor(255, 226, 170, 200))
        sun.setColorAt(0.12, QtGui.QColor(255, 210, 150, 120))
        sun.setColorAt(1.0, QtGui.QColor(255, 200, 140, 0))
        p.fillRect(r, sun)
        p.setPen(QtCore.Qt.PenStyle.NoPen)

        def ridge(color, pts):
            poly = QtGui.QPolygonF([QtCore.QPointF(w * x, h * y) for x, y in pts]
                                   + [QtCore.QPointF(w, h), QtCore.QPointF(0, h)])
            p.setBrush(QtGui.QColor(*color))
            p.drawPolygon(poly)

        ridge((86, 70, 96, 230), [(0, .58), (.12, .44), (.24, .52), (.38, .36), (.52, .50),
                                  (.63, .42), (.78, .55), (.9, .46), (1, .52)])
        ridge((52, 42, 64, 245), [(0, .70), (.15, .60), (.3, .68), (.46, .58), (.6, .70),
                                  (.76, .62), (.9, .69), (1, .64)])
        ridge((24, 20, 30, 255), [(0, .82), (.2, .76), (.42, .83), (.64, .77), (.84, .84), (1, .79)])
        # karakter silueti
        p.setBrush(QtGui.QColor(14, 11, 16))
        cx, base = w * 0.24, h * 0.79
        p.drawEllipse(QtCore.QPointF(cx, base - h * 0.205), h * 0.028, h * 0.028)
        body = QtGui.QPainterPath()
        body.moveTo(cx - h * 0.05, base)
        body.quadTo(cx - h * 0.045, base - h * 0.16, cx, base - h * 0.175)
        body.quadTo(cx + h * 0.045, base - h * 0.16, cx + h * 0.06, base)
        p.drawPath(body)

        # --- HUD (cevrilmez: sayi)
        p.setBrush(QtGui.QColor(0, 0, 0, 120))
        hud = QtCore.QRectF(pxf(16), pxf(14), pxf(150), pxf(10))
        p.drawRoundedRect(hud, pxf(5), pxf(5))
        p.setBrush(QtGui.QColor("#D9564A"))
        p.drawRoundedRect(QtCore.QRectF(hud.x(), hud.y(), hud.width() * 0.84, hud.height()), pxf(5), pxf(5))
        p.setPen(QtGui.QColor(255, 255, 255, 210))
        p.setFont(T.font("condensed", 8.5))
        p.drawText(QtCore.QRectF(hud.right() + pxf(8), hud.y() - pxf(4), pxf(60), pxf(18)),
                   QtCore.Qt.AlignmentFlag.AlignVCenter, "84 / 100")

        # --- oyunun diyalog kutusu
        dlg = QtCore.QRectF(w * 0.18, h * 0.66, w * 0.64, h * 0.24)
        p.setPen(QtGui.QPen(QtGui.QColor(230, 210, 170, 90), 1))
        p.setBrush(QtGui.QColor(12, 10, 14, 200))
        p.drawRoundedRect(dlg, pxf(6), pxf(6))
        name_r = QtCore.QRectF(dlg.x() + pxf(14), dlg.y() - pxf(11), pxf(78), pxf(22))
        p.setBrush(QtGui.QColor(40, 30, 22, 240))
        p.drawRoundedRect(name_r, pxf(4), pxf(4))
        p.setPen(QtGui.QColor("#E8C98A"))
        p.setFont(T.font("condensed", 9))
        p.drawText(name_r, QtCore.Qt.AlignmentFlag.AlignCenter, "Elara")
        line_r = QtCore.QRect(int(dlg.x() + pxf(24)), int(dlg.y() + pxf(20)),
                              int(dlg.width() - pxf(48)), int(dlg.height() - pxf(34)))
        p.setPen(QtGui.QColor(240, 232, 214))
        p.setFont(T.font("text_serif", 11))
        original = "The old mill hides a rusty key. Bring it before nightfall."
        p.drawText(line_r, int(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap),
                   original)

        # --- etkilesim istemi
        prompt_r = QtCore.QRect(int(w * 0.74), int(h * 0.42), int(w * 0.2), int(pxf(26)))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(0, 0, 0, 110))
        p.drawRoundedRect(QtCore.QRectF(prompt_r), pxf(4), pxf(4))
        p.setPen(QtGui.QColor(255, 255, 255, 230))
        p.setFont(T.font("condensed", 9.5))
        p.drawText(prompt_r, QtCore.Qt.AlignmentFlag.AlignCenter, "[E]  Open the chest")

        # --- bizim ceviriler (gercek overlay cizimi)
        if not self.show_original:
            paint_translation(p, line_r, "Eski değirmen paslı bir anahtar saklıyor. "
                                         "Hava kararmadan getir.", self.config)
            paint_translation(p, prompt_r, "[E]  Sandığı aç", self.config)

        p.setClipping(False)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE_SOFT), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), pxf(14), pxf(14))
        p.end()


def _tile_art(style_key, config):
    def paint(p, art):
        cfg = dict(config)
        cfg.update({"overlay_style": style_key, "font_size": 10, "min_font_size": 6})
        rect = QtCore.QRect(int(art.x() + art.width() * 0.12), int(art.bottom() - pxf(34)),
                            int(art.width() * 0.76), int(pxf(22)))
        paint_translation(p, rect, "Sandığı aç", cfg)
    return paint


class AppearancePage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("Görünüm", "Çevirilerin oyunda nasıl duracağını ayarla. "
                                    "Önizleme, oyundaki çizimin birebir aynısı.")
        self.ctx = ctx

        prev_head = QtWidgets.QHBoxLayout()
        prev_head.addStretch(1)
        self.btn_compare = IconButton("eye", "Basılı tutunca orijinal oyun yazısını gösterir", 17)
        self.btn_compare.pressed.connect(lambda: self._compare(True))
        self.btn_compare.released.connect(lambda: self._compare(False))
        hint = label("Karşılaştırmak için basılı tut", "Faint")
        prev_head.addWidget(hint)
        prev_head.addWidget(self.btn_compare)

        self.preview = GamePreview(ctx.config)
        self.body.addWidget(self.preview)
        self.body.addLayout(prev_head)

        self.body.addWidget(section_header("Stil"))
        tiles = QtWidgets.QHBoxLayout()
        tiles.setSpacing(px(12))
        self.tile_group = QtWidgets.QButtonGroup(self)
        self.tile_group.setExclusive(True)
        self.tiles = {}
        for key, title, caption in STYLES:
            t = StyleTile(title, caption, _tile_art(key, ctx.config))
            self.tile_group.addButton(t)
            self.tiles[key] = t
            tiles.addWidget(t, 1)
            t.toggled.connect(self._changed)
        self.body.addLayout(tiles)

        self.body.addSpacing(px(8))
        self.body.addWidget(section_header("Yazı ve renk"))
        g = SettingsGroup()
        self.combo_font = Combo()
        for key, name, _ in FONTS:
            self.combo_font.addItem(name, key)
        self.font_row = g.row("Yazı tipi", FONTS[0][2], self.combo_font)
        self.step_size = Stepper(8, 48, 1, "pt")
        g.row("Yazı boyutu", "Yazı kutuya sığmazsa otomatik küçülür.", self.step_size)
        self.step_min = Stepper(6, 30, 1, "pt")
        g.row("En küçük boyut", "Küçülme bunun altına inmez.", self.step_min)
        self.slider_opacity = ValueSlider(0, 100, 1, "%{:.0f}")
        self.slider_opacity.setMinimumWidth(px(240))
        g.row("Koyuluk", "Kutu ve kenar çizgisinin ne kadar örteceği.", self.slider_opacity, True)

        colors = QtWidgets.QHBoxLayout()
        colors.setSpacing(px(8))
        self.sw_bg = ColorSwatch("#141414", "Zemin rengi")
        self.sw_fg = ColorSwatch("#FFFFFF", "Yazı rengi")
        colors.addWidget(self.sw_bg)
        colors.addWidget(self.sw_fg)
        g.row("Zemin ve yazı rengi", "Kutu ve şeritte zemin; altyazı stilinde kenar çizgisi.", colors)

        presets = QtWidgets.QHBoxLayout()
        presets.setSpacing(px(6))
        for name, bg, fg, op in PALETTES:
            b = QtWidgets.QPushButton(name)
            b.setObjectName("Quiet")
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.setIcon(_palette_icon(bg, fg))
            b.setIconSize(QtCore.QSize(px(22), px(14)))
            b.clicked.connect(lambda _=False, bg=bg, fg=fg, op=op: self._preset(bg, fg, op))
            presets.addWidget(b)
        g.row("Hazır renkler", None, presets)
        self.body.addWidget(g)
        self.finish()

        self.combo_font.currentIndexChanged.connect(self._changed)
        self.step_size.valueChanged.connect(self._changed)
        self.step_min.valueChanged.connect(self._changed)
        self.slider_opacity.valueChanged.connect(self._changed)
        self.sw_bg.changed.connect(self._changed)
        self.sw_fg.changed.connect(self._changed)

    def _compare(self, on):
        self.preview.show_original = on
        self.preview.update()

    def _preset(self, bg, fg, op):
        with self.ctx.loading():
            self.sw_bg.set_hex(bg)
            self.sw_fg.set_hex(fg)
            self.slider_opacity.setValue(op * 100)
        self._changed()

    def _changed(self, *_):
        if self.ctx.is_loading():
            return
        # Onizleme kaydetmeyi beklemeden guncellensin
        self.save(self.ctx.config)
        self._refresh_visuals()
        self.ctx.schedule_save()

    def _refresh_visuals(self):
        key = self.combo_font.currentData()
        hint = dict((k, h) for k, _n, h in FONTS).get(key, "")
        for lbl in self.font_row.findChildren(QtWidgets.QLabel):
            if lbl.objectName() == "RowHint":
                lbl.setText(hint)
        self.preview.update()
        for t in self.tiles.values():
            t.update()
        try:
            self.ctx.orchestrator.overlay.refresh()
        except Exception:
            pass

    def load(self, cfg):
        style = cfg.get("overlay_style", "box")
        (self.tiles.get(style) or self.tiles["box"]).setChecked(True)
        i = self.combo_font.findData(cfg.get("overlay_font", "plex"))
        self.combo_font.setCurrentIndex(max(0, i))
        self.step_size.setValue(cfg.get("font_size", 18), emit=False)
        self.step_min.setValue(cfg.get("min_font_size", 10), emit=False)
        self.slider_opacity.setValue(cfg.get("overlay_opacity", 0.72) * 100)
        self.sw_bg.set_hex(cfg.get("overlay_bg_color", "#141414"))
        self.sw_fg.set_hex(cfg.get("overlay_text_color", "#FFFFFF"))
        self._refresh_visuals()

    def save(self, cfg):
        for key, t in self.tiles.items():
            if t.isChecked():
                cfg["overlay_style"] = key
        cfg["overlay_font"] = self.combo_font.currentData() or "plex"
        cfg["font_size"] = self.step_size.value()
        cfg["min_font_size"] = min(self.step_min.value(), self.step_size.value())
        cfg["overlay_opacity"] = round(self.slider_opacity.value() / 100.0, 2)
        cfg["overlay_bg_color"] = self.sw_bg.hex()
        cfg["overlay_text_color"] = self.sw_fg.hex()


def _palette_icon(bg, fg):
    w, h = px(22), px(14)
    pm = QtGui.QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setPen(QtGui.QPen(QtGui.QColor("#5A5047"), 1))
    p.setBrush(QtGui.QColor(bg))
    p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, w - 1, h - 1), px(3), px(3))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(fg))
    p.drawRoundedRect(QtCore.QRectF(w * 0.22, h * 0.42, w * 0.56, h * 0.18), 1, 1)
    p.end()
    return QtGui.QIcon(pm)
