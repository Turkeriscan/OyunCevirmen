"""
Sahne: kontrol panelinin ana sayfasi.

Solda sinemaskop oranli (2.39:1) bir perde; oyunda yakalanan son ceviri,
gercek bir film altyazisi gibi burada belirir, orijinali altinda incelir.
Perdenin altinda iki "projektor" dugmesi: Aninda tara ve Canli mod.
Sagda akis: her ceviri, bir .srt altyazi dosyasindaki gibi numarasi ve
zaman koduyla listelenir.
"""
from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import theme as T
from app.ui.theme import px, pxf
from app.ui.widgets import Combo, IconButton, Keycaps, label, scroll_page, text_button


def timecode(seconds, millis=True):
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = int(seconds % 60)
    if millis:
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


# ================================================================= Perde
class Screen(QtWidgets.QWidget):
    RATIO = 2.39

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(px(220))
        self._cue = None          # (numara, zaman_kodu, ceviri, orijinal)
        self._prev = None
        self._t = 1.0             # gecis ilerlemesi
        self._idle = ("Perde hazır.", "")
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._on_anim)

    def sizeHint(self):
        return QtCore.QSize(px(720), int(px(720) / self.RATIO))

    def set_idle(self, title, hint):
        if self._idle != (title, hint):
            self._idle = (title, hint)
            if self._cue is None:
                self.update()

    def set_cue(self, cue):
        if cue == self._cue:
            return
        self._prev = self._cue
        self._cue = cue
        if T.reduced_motion() or self._prev is None and cue is None:
            self._t = 1.0
            self.update()
            return
        self._anim.stop()
        self._anim.start()

    def _on_anim(self, v):
        self._t = float(v)
        self.update()

    # ------------------------------------------------------------ cizim
    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        r = QtCore.QRectF(self.rect())
        radius = pxf(14)
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, radius, radius)
        p.setClipPath(clip)

        # Karanlik salon + projektorden gelen yumusak isik
        p.fillRect(r, QtGui.QColor("#0B0908"))
        beam = QtGui.QRadialGradient(QtCore.QPointF(r.center().x(), r.top() - r.height() * 0.15),
                                     r.width() * 0.62)
        beam.setColorAt(0.0, QtGui.QColor(255, 236, 200, 34))
        beam.setColorAt(0.55, QtGui.QColor(255, 226, 180, 10))
        beam.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(r, beam)
        vignette = QtGui.QRadialGradient(r.center(), r.width() * 0.7)
        vignette.setColorAt(0.6, QtGui.QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QtGui.QColor(0, 0, 0, 120))
        p.fillRect(r, vignette)

        # Film greni yerine ince tarama cizgileri (cok hafif)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 6), 1))
        y = r.top() + 2
        while y < r.bottom():
            p.drawLine(QtCore.QPointF(r.left(), y), QtCore.QPointF(r.right(), y))
            y += pxf(3)

        ease_in = 1 - (1 - self._t) ** 3
        if self._prev is not None and self._t < 1.0:
            out = max(0.0, 1.0 - self._t * 2.2)
            self._paint_cue(p, r, self._prev, out, -pxf(8) * self._t)
        if self._cue is not None:
            self._paint_cue(p, r, self._cue, ease_in, pxf(10) * (1 - ease_in))
        elif self._t >= 0.45 or self._prev is None:
            self._paint_idle(p, r, ease_in if self._prev is not None else 1.0)

        p.setClipping(False)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE_SOFT), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        p.end()

    def _paint_cue(self, p, r, cue, alpha, dy):
        number, tc, translated, original = cue
        p.save()
        p.setOpacity(alpha)
        pad = pxf(26)

        # Ust kosede SRT bilgisi: "014   00:03:12,400"
        p.setFont(T.font("mono", 8.5))
        p.setPen(QtGui.QColor(T.FAINT))
        p.drawText(QtCore.QRectF(r.left() + pad, r.top() + pxf(18), r.width() / 2, pxf(18)),
                   QtCore.Qt.AlignmentFlag.AlignLeft, f"{number:03d}    {tc}")

        # Altyazi: alt ucte, ortali, kenar cizgili
        width = r.width() - pad * 2
        f = T.font("body_semibold", 21)
        lines = _wrap(translated, f, width)
        while len(lines) > 2 and f.pointSizeF() > 13:
            f.setPointSizeF(f.pointSizeF() - 1.5)
            lines = _wrap(translated, f, width)
        lines = lines[:3]
        fm = QtGui.QFontMetricsF(f)
        orig_f = T.font("display_italic", 12.5)
        ofm = QtGui.QFontMetricsF(orig_f)
        orig_lines = _wrap(original, orig_f, width)[:2]
        block_h = fm.height() * len(lines) + pxf(10) + ofm.height() * len(orig_lines)
        y = r.bottom() - pxf(30) - block_h + dy

        path = QtGui.QPainterPath()
        for line in lines:
            w = fm.horizontalAdvance(line)
            path.addText(r.center().x() - w / 2, y + fm.ascent(), f, line)
            y += fm.height()
        stroke = QtGui.QPen(QtGui.QColor(0, 0, 0, 220), max(3.0, f.pointSizeF() * 0.2),
                            QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap,
                            QtCore.Qt.PenJoinStyle.RoundJoin)
        p.setPen(stroke)
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(T.PAPER))
        p.drawPath(path)

        y += pxf(10)
        p.setFont(orig_f)
        p.setPen(QtGui.QColor(T.MUTED))
        for line in orig_lines:
            p.drawText(QtCore.QRectF(r.left() + pad, y, width, ofm.height()),
                       QtCore.Qt.AlignmentFlag.AlignHCenter, line)
            y += ofm.height()
        p.restore()

    def _paint_idle(self, p, r, alpha):
        title, hint = self._idle
        p.save()
        p.setOpacity(alpha)
        f = T.font("display", 24)
        p.setFont(f)
        p.setPen(QtGui.QColor(T.PAPER))
        fm = QtGui.QFontMetricsF(f)
        hf = T.font("body", 10)
        hfm = QtGui.QFontMetricsF(hf)
        total = fm.height() + pxf(8) + hfm.height() * 2
        top = r.center().y() - total / 2 + pxf(6)
        p.drawText(QtCore.QRectF(r.left(), top, r.width(), fm.height()),
                   QtCore.Qt.AlignmentFlag.AlignHCenter, title)
        p.setFont(hf)
        p.setPen(QtGui.QColor(T.MUTED))
        p.drawText(QtCore.QRectF(r.left() + pxf(40), top + fm.height() + pxf(8), r.width() - pxf(80),
                                 hfm.height() * 2 + 2),
                   int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.TextFlag.TextWordWrap), hint)
        p.restore()


def _wrap(text, font, width):
    fm = QtGui.QFontMetricsF(font)
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fm.horizontalAdvance(trial) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ============================================================ Mod dugmesi
class ModeButton(QtWidgets.QAbstractButton):
    """Projektor dugmesi: lamba + ad + aciklama + tus kapagi."""

    def __init__(self, title, caption, lamp_color, parent=None):
        super().__init__(parent)
        self._title = title
        self._caption = caption
        self._lamp = QtGui.QColor(lamp_color)
        self._active = False
        self._state_text = ""
        self._hotkey = ""
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(px(100))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)
        self.caps = Keycaps("", "md", self)
        self._pulse = QtCore.QVariantAnimation(self)
        self._pulse.setDuration(1600)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(lambda _v: self.update())

    def sizeHint(self):
        return QtCore.QSize(px(300), px(100))

    def set_hotkey(self, value):
        self._hotkey = value
        self.caps.set_value(value)
        self.caps.adjustSize()
        self._place_caps()

    def set_active(self, active, state_text=""):
        changed = active != self._active or state_text != self._state_text
        self._active = active
        self._state_text = state_text
        self.caps.set_accent(active)
        if active and not T.reduced_motion():
            if self._pulse.state() != QtCore.QAbstractAnimation.State.Running:
                self._pulse.start()
        else:
            self._pulse.stop()
        if changed:
            self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_caps()

    def _place_caps(self):
        hint = self.caps.sizeHint()
        self.caps.setGeometry(self.width() - px(20) - hint.width(), (self.height() - hint.height()) // 2,
                              hint.width(), hint.height())

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, event):
        import math
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = pxf(12)
        if self._active:
            wash = QtGui.QColor(self._lamp)
            wash.setAlphaF(0.10)
            p.setBrush(wash)
            border = QtGui.QColor(self._lamp)
            border.setAlphaF(0.75)
        else:
            p.setBrush(QtGui.QColor(T.SURFACE if not self.isDown() else T.RAISED))
            border = QtGui.QColor(T.LINE if self.underMouse() else T.LINE_SOFT)
        p.setPen(QtGui.QPen(border, 1))
        p.drawRoundedRect(r, radius, radius)

        # Lamba
        cx, cy = r.left() + pxf(28), r.center().y()
        lamp = QtGui.QColor(self._lamp if self._active else T.FAINT)
        if self._active:
            k = 1.0
            if self._pulse.state() == QtCore.QAbstractAnimation.State.Running:
                k = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(float(self._pulse.currentValue()) * math.tau))
            glow = QtGui.QRadialGradient(QtCore.QPointF(cx, cy), pxf(16))
            g = QtGui.QColor(self._lamp)
            g.setAlphaF(0.45 * k)
            glow.setColorAt(0, g)
            g.setAlphaF(0)
            glow.setColorAt(1, g)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QtCore.QPointF(cx, cy), pxf(16), pxf(16))
        p.setPen(QtGui.QPen(QtGui.QColor("#0F0D0B"), 1.5))
        p.setBrush(lamp)
        p.drawEllipse(QtCore.QPointF(cx, cy), pxf(5.5), pxf(5.5))

        # Metin
        left = r.left() + pxf(52)
        right = self.caps.geometry().left() - pxf(16)
        tf = T.font("display_medium", 15)
        cf = T.font("body", 9)
        tfm = QtGui.QFontMetricsF(tf)
        cfm = QtGui.QFontMetricsF(cf)
        cap_rect = cfm.boundingRect(QtCore.QRectF(0, 0, max(1.0, right - left), 1000),
                                    int(QtCore.Qt.TextFlag.TextWordWrap), self._caption)
        cap_h = min(cap_rect.height(), cfm.height() * 3)
        block = tfm.height() + pxf(2) + cap_h
        top = r.center().y() - block / 2
        p.setFont(tf)
        p.setPen(QtGui.QColor(T.PAPER))
        title_w = tfm.horizontalAdvance(self._title)
        title = tfm.elidedText(self._title, QtCore.Qt.TextElideMode.ElideRight, right - left)
        p.drawText(QtCore.QRectF(left, top, right - left, tfm.height()),
                   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, title)
        sf = T.font("body_semibold", 8.5)
        sfm = QtGui.QFontMetricsF(sf)
        pill_w = sfm.horizontalAdvance(self._state_text) + pxf(16)
        # Yer yoksa durum etiketi dusurulur; lamba durumu zaten gosteriyor
        if self._active and self._state_text and left + title_w + pxf(10) + pill_w <= right:
            p.setFont(sf)
            pill = QtCore.QRectF(left + title_w + pxf(10), top + (tfm.height() - pxf(20)) / 2,
                                 pill_w, pxf(20))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(self._lamp)
            p.drawRoundedRect(pill, pxf(10), pxf(10))
            p.setPen(QtGui.QColor("#1A0F0B" if self._lamp == QtGui.QColor(T.REC) else T.SUB_INK))
            p.drawText(pill, QtCore.Qt.AlignmentFlag.AlignCenter, self._state_text)
        p.setFont(cf)
        p.setPen(QtGui.QColor(T.MUTED))
        p.drawText(QtCore.QRectF(left, top + tfm.height() + pxf(2), right - left, cap_h + 2),
                   int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.TextFlag.TextWordWrap), self._caption)

        if self.hasFocus():
            p.setPen(QtGui.QPen(QtGui.QColor(T.PAPER), 1, QtCore.Qt.PenStyle.DotLine))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(3, 3, -3, -3), radius - 2, radius - 2)
        p.end()


# ================================================================ Akis
class CueRow(QtWidgets.QWidget):
    def __init__(self, ctx, number, tc, translated, original, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._text = (translated, original)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(20), px(12), px(18), px(12))
        lay.setSpacing(px(3))
        meta = QtWidgets.QHBoxLayout()
        meta.setSpacing(px(14))
        n = label(f"{number:03d}", "CueMeta")
        t = label(tc, "CueMeta")
        meta.addWidget(n)
        meta.addWidget(t)
        meta.addStretch(1)
        lay.addLayout(meta)
        self.tr_label = label(translated, "CueText", wrap=True, selectable=True)
        lay.addWidget(self.tr_label)
        lay.addWidget(label(original, "CueOriginal", wrap=True, selectable=True))
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos):
        menu = QtWidgets.QMenu(self)
        a1 = menu.addAction("Çeviriyi kopyala")
        a2 = menu.addAction("Orijinali kopyala")
        menu.addSeparator()
        a3 = menu.addAction("Çeviriyi düzelt…")
        a4 = None
        orchestrator = getattr(self.ctx, "orchestrator", None)
        original = self._text[1]
        if orchestrator is not None and orchestrator.is_manually_corrected(original):
            a4 = menu.addAction("Düzeltmeyi geri al")
        act = menu.exec(self.mapToGlobal(pos))
        if act == a1:
            QtWidgets.QApplication.clipboard().setText(self._text[0])
        elif act == a2:
            QtWidgets.QApplication.clipboard().setText(self._text[1])
        elif act == a3:
            self._correct(original)
        elif a4 is not None and act == a4:
            self._undo(original)

    def _correct(self, original):
        orchestrator = getattr(self.ctx, "orchestrator", None)
        if orchestrator is None:
            return
        current = self.tr_label.text()
        new_text, ok = QtWidgets.QInputDialog.getText(
            self, "Çeviriyi düzelt", "Bu satırın çevirisi oyunda hemen kullanılır:",
            text=current,
        )
        if not ok:
            return
        if orchestrator.correct_translation(original, new_text):
            self.tr_label.setText(new_text.strip())
            self._text = (new_text.strip(), self._text[1])
            self.ctx.flash("Çeviri düzeltildi")

    def _undo(self, original):
        orchestrator = getattr(self.ctx, "orchestrator", None)
        if orchestrator is None:
            return
        orchestrator.undo_correction(original)
        self.ctx.flash("Düzeltme geri alındı")

    def paintEvent(self, e):
        if self.underMouse():
            p = QtGui.QPainter(self)
            p.fillRect(self.rect(), QtGui.QColor(255, 255, 255, 6))
            p.end()


class Transcript(QtWidgets.QFrame):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Transcript")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(px(20), px(22), px(12), px(12))
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(px(2))
        titles.addWidget(label("Akış", "SectionTitle"))
        self.count = label("Bu oturumda çeviri yok", "Faint")
        titles.addWidget(self.count)
        head.addLayout(titles)
        head.addStretch(1)
        self.btn_copy = IconButton("copy", "Tüm akışı kopyala", 17)
        head.addWidget(self.btn_copy, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)

        self.list_host = QtWidgets.QWidget()
        self.list = QtWidgets.QVBoxLayout(self.list_host)
        self.list.setContentsMargins(0, 0, 0, px(12))
        self.list.setSpacing(0)
        self.list.addStretch(1)
        lay.addWidget(scroll_page(self.list_host), 1)
        self._items = []

    def set_items(self, items, started_at):
        """items: [(zaman, orijinal, ceviri)] yeni -> eski"""
        self._items = items
        while self.list.count():
            it = self.list.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        total = len(items)
        self.count.setText(f"{total} satır, en yenisi üstte" if total else "Bu oturumda çeviri yok")
        self.btn_copy.setEnabled(bool(total))
        if not items:
            empty = label(
                "Oyunda çevrilen her yazı burada, bir altyazı dosyasındaki gibi "
                "numarası ve zamanıyla sıralanır.", "Faint", wrap=True)
            empty.setContentsMargins(px(20), px(6), px(20), 0)
            self.list.addWidget(empty)
            self.list.addStretch(1)
            return
        for i, (ts, orig, tr) in enumerate(items):
            if i:
                sep = QtWidgets.QFrame()
                sep.setObjectName("CueSep")
                sep.setFixedHeight(1)
                holder = QtWidgets.QWidget()
                hl = QtWidgets.QHBoxLayout(holder)
                hl.setContentsMargins(px(20), 0, px(18), 0)
                hl.addWidget(sep)
                self.list.addWidget(holder)
            self.list.addWidget(CueRow(self.ctx, total - i, timecode(ts - started_at), tr, orig))
        self.list.addStretch(1)

    def as_srt(self, started_at):
        """Akisi gercek bir .srt metni olarak dondurur (eski -> yeni)."""
        out = []
        items = list(reversed(self._items))
        for i, (ts, orig, tr) in enumerate(items, 1):
            start = ts - started_at
            out.append(f"{i}\n{timecode(start)} --> {timecode(start + 3)}\n{tr}\n")
        return "\n".join(out)


# ========================================================== Oyun profili
class ProfileBar(QtWidgets.QWidget):
    """Su an on plandaki oyunu gosterir; o oyun icin ayri bir profil
    (OCR motoru/dili, overlay stili, okuma bolgeleri, sozluk) kaydedip
    yonetmeyi saglar (4.1)."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(10))

        self.lbl = label("", "Faint", wrap=True)
        self.lbl.setMinimumWidth(px(120))
        lay.addWidget(self.lbl, 1)

        self.combo_enabled = Combo()
        self.combo_enabled.addItem("Profiller açık", True)
        self.combo_enabled.addItem("Profiller kapalı", False)
        self.combo_enabled.currentIndexChanged.connect(self._toggle_enabled)
        lay.addWidget(self.combo_enabled)

        self.btn_save = text_button("Profili kaydet")
        self.btn_save.clicked.connect(self._save)
        lay.addWidget(self.btn_save)

        self.btn_delete = text_button("Profili sil", "Danger")
        self.btn_delete.clicked.connect(self._delete)
        lay.addWidget(self.btn_delete)

    def _toggle_enabled(self):
        if self.ctx.is_loading():
            return
        self.ctx.orchestrator.set_game_profiles_enabled(bool(self.combo_enabled.currentData()))
        self.refresh()

    def _current_exe(self):
        return getattr(self.ctx.orchestrator, "_current_foreground_exe", None)

    def _save(self):
        exe = self._current_exe()
        if not exe:
            self.ctx.flash("Önce bir oyun penceresine geç")
            return
        self.ctx.orchestrator.save_current_as_profile(exe)
        self.ctx.flash(f"'{exe}' için profil kaydedildi")
        self.refresh()

    def _delete(self):
        exe = self._current_exe()
        if exe and self.ctx.orchestrator.delete_profile(exe):
            self.ctx.flash(f"'{exe}' için profil silindi")
        self.refresh()

    def refresh(self):
        o = self.ctx.orchestrator
        exe = self._current_exe()
        game_profiles = o.config.get("game_profiles", {})
        has_profile = bool(exe) and exe in game_profiles
        active = getattr(o, "_active_profile_exe", None)

        if not exe:
            self.lbl.setText("Oyun tespit edilemedi")
        elif has_profile and active == exe:
            self.lbl.setText(f"'{exe}' için profil uygulanıyor")
        elif has_profile:
            self.lbl.setText(f"'{exe}' için profil var (profiller kapalı)")
        else:
            self.lbl.setText(f"'{exe}' için profil yok, genel ayarlar kullanılıyor")

        self.combo_enabled.blockSignals(True)
        i = self.combo_enabled.findData(bool(o.config.get("game_profiles_enabled", True)))
        self.combo_enabled.setCurrentIndex(i if i >= 0 else 0)
        self.combo_enabled.blockSignals(False)

        self.btn_save.setText("Profili güncelle" if has_profile else "Profili kaydet")
        self.btn_save.setEnabled(bool(exe))
        self.btn_delete.setEnabled(has_profile)


# ================================================================ Sayfa
class ScenePage(QtWidgets.QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._version = -1
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(px(36), px(30), px(32), px(28))
        ll.setSpacing(px(16))

        head = QtWidgets.QHBoxLayout()
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(px(4))
        titles.addWidget(label("Sahne", "PageTitle"))
        self.lead = label("", "PageLead", wrap=True)
        titles.addWidget(self.lead)
        head.addLayout(titles, 1)
        ll.addLayout(head)

        self.profile_bar = ProfileBar(ctx)
        ll.addWidget(self.profile_bar)

        self.screen = Screen()
        ll.addWidget(self.screen, 1)

        modes = QtWidgets.QHBoxLayout()
        modes.setSpacing(px(14))
        self.btn_instant = ModeButton(
            "Anında tara", "Ekranı bir kez çevirir; tekrar basınca çeviriler kalkar.",
            T.SUB)
        self.btn_live = ModeButton(
            "Canlı mod", "Ekranı sürekli izler ve değişen yazıları çevirir.", T.REC)
        self.btn_instant.clicked.connect(ctx.toggle_instant)
        self.btn_live.clicked.connect(ctx.toggle_live)
        modes.addWidget(self.btn_instant, 1)
        modes.addWidget(self.btn_live, 1)
        ll.addLayout(modes)
        lay.addWidget(left, 1)

        self.transcript = Transcript(ctx)
        self.transcript.setFixedWidth(px(340))
        self._left = left
        self.transcript.btn_copy.clicked.connect(self._copy)
        lay.addWidget(self.transcript)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Dar pencerede akis paneli daralir, perde ve dugmeler yer kazanir
        self.transcript.setFixedWidth(max(px(272), min(px(360), int(self.width() * 0.3))))

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.transcript.as_srt(self.ctx.started_at))
        self.ctx.flash("Akış altyazı biçiminde panoya kopyalandı")

    def refresh(self, mode, hk_instant, hk_live):
        self.profile_bar.refresh()
        self.btn_instant.set_hotkey(hk_instant)
        self.btn_live.set_hotkey(hk_live)
        self.btn_instant.set_active(mode == "instant", "Ekranda")
        self.btn_live.set_active(mode == "live", "Kayıtta")
        from app.ui.widgets import hotkey_text
        hi, hl = hotkey_text(hk_instant), hotkey_text(hk_live)
        if mode == "live":
            self.lead.setText(f"Canlı mod açık; ekran izleniyor. Durdurmak için {hl}.")
            self.screen.set_idle("Ekran izleniyor.", "Oyunda yeni bir yazı belirdiğinde Türkçesi burada görünür.")
        elif mode == "instant":
            self.lead.setText(f"Çeviriler oyunun üstünde. Kaldırmak için tekrar {hi}.")
            self.screen.set_idle("Ekran tarandı.", "Bulunan yazılar oyunda çevrildi.")
        else:
            self.lead.setText("Oyunu kenarlıksız pencere modunda aç; çevirmek istediğinde tuşa bas.")
            self.screen.set_idle("Perde hazır.", f"Oyundayken {hi} ile ekranı bir kez çevir, "
                                                 f"{hl} ile sürekli izlet.")

        o = self.ctx.orchestrator
        version = getattr(o, "recent_version", 0)
        if version != self._version:
            self._version = version
            items = list(getattr(o, "recent", []))
            self.transcript.set_items(items, self.ctx.started_at)
            if items:
                ts, orig, tr = items[0]
                self.screen.set_cue((len(items), timecode(ts - self.ctx.started_at), tr, orig))
            else:
                self.screen.set_cue(None)
