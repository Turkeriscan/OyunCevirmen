"""
Bolge secici (3.5): tam ekran, yari seffaf bir secim katmani. Kullanici
suruyerek dikdortgenler cizer; her dikdortgen "Dışında bırak" (bu bolge
hic okunmaz) veya "Sadece burayı oku" (sadece bu bolge(ler) okunur,
digeri yoksayilir) olarak isaretlenir. "Bitti" ile config'e kaydedilir.

Cok monitorlu kurulumlarda oyunun hangi ekranda oldugu onemli degildir:
katman TUM sanal masaustunu (virtualGeometry) kaplar.
"""
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import theme

logger = logging.getLogger("OyunCevirmen.regionoverlay")

MODE_EXCLUDE = "exclude"
MODE_INCLUDE = "include"
MIN_REGION_SIZE = 6  # bundan kucuk cizimler (yanlislikla tiklama) yoksayilir


def normalize_rect(x1, y1, x2, y2):
    """Surukleme baslangic/bitis noktalarindan (hangi yonde surulduyse)
    normallesitirilmis {"left","top","width","height"} dondurur."""
    left = min(x1, x2)
    top = min(y1, y2)
    return {
        "left": int(left),
        "top": int(top),
        "width": int(abs(x2 - x1)),
        "height": int(abs(y2 - y1)),
    }


def is_region_large_enough(region, min_size=MIN_REGION_SIZE):
    return region["width"] >= min_size and region["height"] >= min_size


def split_regions_by_mode(regions):
    """regions: [(region_dict, mode), ...] -> (exclude_list, include_list)."""
    exclude = [r for r, m in regions if m == MODE_EXCLUDE]
    include = [r for r, m in regions if m == MODE_INCLUDE]
    return exclude, include


class RegionSelectorOverlay(QtWidgets.QWidget):
    """on_done(exclude_regions, include_regions) kaydedilince cagrilir;
    vazgecilirse (Esc/Vazgec) HIC cagrilmaz."""

    def __init__(self, existing_exclude, existing_include, on_done, parent=None):
        super().__init__(parent)
        self.on_done = on_done
        self.mode = MODE_EXCLUDE
        self.regions = []
        for r in existing_exclude or []:
            self.regions.append((dict(r), MODE_EXCLUDE))
        for r in existing_include or []:
            self.regions.append((dict(r), MODE_INCLUDE))
        self._drag_start = None
        self._drag_current = None

        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        screen = QtWidgets.QApplication.primaryScreen()
        virtual_geo = screen.virtualGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        self.setGeometry(virtual_geo)

        self._build_toolbar(screen.geometry() if screen else virtual_geo, virtual_geo)

    # ------------------------------------------------------------- arayuz
    def _build_toolbar(self, primary_geo, virtual_geo):
        bar = QtWidgets.QFrame(self)
        bar.setObjectName("RegionToolbar")
        bar.setStyleSheet(
            f"#RegionToolbar {{ background: {theme.SURFACE}; border: 1px solid {theme.LINE}; "
            f"border-radius: {theme.px(8)}px; }}"
            f"QLabel {{ color: {theme.PAPER}; }}"
            f"QPushButton {{ color: {theme.PAPER}; background: {theme.RAISED}; "
            f"border: none; border-radius: {theme.px(6)}px; padding: {theme.px(6)}px {theme.px(12)}px; }}"
            f"QPushButton:checked {{ background: {theme.SUB_WASH}; color: {theme.SUB}; }}"
            f"QPushButton:hover {{ background: {theme.RAISED_HI}; }}"
        )
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(theme.px(12), theme.px(8), theme.px(12), theme.px(8))
        layout.setSpacing(theme.px(8))

        hint = QtWidgets.QLabel("Fare ile sürükleyerek bir bölge çiz:")
        layout.addWidget(hint)

        self.btn_exclude = QtWidgets.QPushButton("Dışında bırak")
        self.btn_exclude.setCheckable(True)
        self.btn_exclude.setChecked(True)
        self.btn_include = QtWidgets.QPushButton("Sadece burayı oku")
        self.btn_include.setCheckable(True)
        group = QtWidgets.QButtonGroup(self)
        group.addButton(self.btn_exclude)
        group.addButton(self.btn_include)
        self.btn_exclude.clicked.connect(lambda: self._set_mode(MODE_EXCLUDE))
        self.btn_include.clicked.connect(lambda: self._set_mode(MODE_INCLUDE))
        layout.addWidget(self.btn_exclude)
        layout.addWidget(self.btn_include)

        btn_undo = QtWidgets.QPushButton("Son çizileni sil")
        btn_undo.clicked.connect(self._undo_last)
        layout.addWidget(btn_undo)

        btn_clear = QtWidgets.QPushButton("Tümünü temizle")
        btn_clear.clicked.connect(self._clear_all)
        layout.addWidget(btn_clear)

        btn_cancel = QtWidgets.QPushButton("Vazgeç (Esc)")
        btn_cancel.clicked.connect(self.close)
        layout.addWidget(btn_cancel)

        btn_done = QtWidgets.QPushButton("Bitti, kaydet (Enter)")
        btn_done.clicked.connect(self._finish)
        layout.addWidget(btn_done)

        bar.adjustSize()
        local_x = primary_geo.x() - virtual_geo.x() + (primary_geo.width() - bar.sizeHint().width()) // 2
        local_y = primary_geo.y() - virtual_geo.y() + theme.px(24)
        bar.move(max(0, local_x), max(0, local_y))
        self._toolbar = bar

    def _set_mode(self, mode):
        self.mode = mode

    def _undo_last(self):
        if self.regions:
            self.regions.pop()
            self.update()

    def _clear_all(self):
        self.regions = []
        self.update()

    def _finish(self):
        exclude, include = split_regions_by_mode(self.regions)
        logger.info("Bolge secimi kaydedildi: %d disarida, %d sadece-oku.", len(exclude), len(include))
        self.on_done(exclude, include)
        self.close()

    # ------------------------------------------------------------- mouse/klavye
    def _in_toolbar(self, pos):
        return self._toolbar.geometry().contains(pos)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and not self._in_toolbar(event.pos()):
            self._drag_start = event.pos()
            self._drag_current = event.pos()

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._drag_current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_start is None:
            return
        local_region = normalize_rect(
            self._drag_start.x(), self._drag_start.y(), event.pos().x(), event.pos().y())
        self._drag_start = None
        self._drag_current = None
        if is_region_large_enough(local_region):
            top_left = self.mapToGlobal(QtCore.QPoint(local_region["left"], local_region["top"]))
            global_region = {
                "left": top_left.x(), "top": top_left.y(),
                "width": local_region["width"], "height": local_region["height"],
            }
            self.regions.append((global_region, self.mode))
        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._finish()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ cizim
    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 110))

        for region, mode in self.regions:
            self._paint_region(painter, self._global_region_to_local_rect(region), mode)

        if self._drag_start is not None and self._drag_current is not None:
            local_region = normalize_rect(
                self._drag_start.x(), self._drag_start.y(),
                self._drag_current.x(), self._drag_current.y())
            rect = QtCore.QRect(local_region["left"], local_region["top"],
                                 local_region["width"], local_region["height"])
            self._paint_region(painter, rect, self.mode)
        painter.end()

    def _global_region_to_local_rect(self, region):
        top_left_global = QtCore.QPoint(region["left"], region["top"])
        top_left_local = self.mapFromGlobal(top_left_global)
        return QtCore.QRect(top_left_local.x(), top_left_local.y(), region["width"], region["height"])

    def _paint_region(self, painter, rect, mode):
        color = QtGui.QColor(theme.REC) if mode == MODE_EXCLUDE else QtGui.QColor(theme.OK)
        fill = QtGui.QColor(color)
        fill.setAlpha(70)
        painter.fillRect(rect, fill)
        pen = QtGui.QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)
        label = "Dışında" if mode == MODE_EXCLUDE else "Sadece"
        painter.setPen(QtGui.QColor(theme.PAPER))
        painter.drawText(rect.adjusted(6, 4, -4, -4), QtCore.Qt.AlignmentFlag.AlignTop
                          | QtCore.Qt.AlignmentFlag.AlignLeft, label)
