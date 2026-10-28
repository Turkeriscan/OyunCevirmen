"""
Ilk acilis rehberi: dort adim.

    1 Hos geldin      - programin ne yaptigi, kucuk bir perde animasyonuyla
    2 Oyunu hazirla   - neden kenarliksiz pencere modu gerektigi
    3 Tuslar          - iki kisayol
    4 Kontrol         - Ollama, model, ekran karti, yazi okuma: canli kontrol

Gelismis > Karsilama rehberi'nden istenince yeniden acilabilir.
"""
import subprocess
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import icons
from app.ui import theme as T
from app.ui.theme import px, pxf
from app.ui.widgets import Keycaps, Lamp, label, text_button

CREATE_NO_WINDOW = 0x08000000

EXAMPLES = [
    ("Press E to open the ancient door", "Eski kapıyı açmak için E'ye bas"),
    ("Your inventory is full", "Envanterin dolu"),
    ("Quest updated: The Lost Caravan", "Görev güncellendi: Kayıp Kervan"),
]


# =========================================================== illustrations
class TranslateLoop(QtWidgets.QWidget):
    """Kucuk perde: Ingilizce satir belirir, yerini Turkcesine birakir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(px(150))
        self._i = 0
        self._phase = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._still = T.reduced_motion()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._still:
            self._timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

    def _tick(self):
        self._phase += 0.03 / 3.4  # bir ornek ~3.4 sn
        if self._phase >= 1.0:
            self._phase = 0.0
            self._i = (self._i + 1) % len(EXAMPLES)
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect())
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(r, pxf(12), pxf(12))
        p.setClipPath(clip)
        p.fillRect(r, QtGui.QColor("#0B0908"))
        beam = QtGui.QRadialGradient(QtCore.QPointF(r.center().x(), r.top() - r.height() * 0.3), r.width() * 0.6)
        beam.setColorAt(0, QtGui.QColor(255, 236, 200, 30))
        beam.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(r, beam)

        en, tr = EXAMPLES[self._i]
        ph = 0.75 if self._still else self._phase
        # 0-.35 Ingilizce, .35-.5 gecis, .5-.92 Turkce, sonra soner
        def seg(a, b):
            return max(0.0, min(1.0, (ph - a) / (b - a)))
        en_a = 1.0 - seg(0.30, 0.42)
        en_a *= seg(0.0, 0.08)
        tr_a = seg(0.38, 0.52) * (1.0 - seg(0.90, 1.0))

        f_en = T.font("display_italic", 15)
        f_tr = T.font("body_semibold", 17)
        base = r.bottom() - pxf(40)
        p.setFont(f_en)
        p.setPen(QtGui.QColor(241, 234, 219, int(200 * en_a)))
        p.drawText(QtCore.QRectF(r.left(), base - pxf(30) + pxf(6) * (1 - en_a), r.width(), pxf(30)),
                   QtCore.Qt.AlignmentFlag.AlignCenter, en)
        if tr_a > 0:
            path = QtGui.QPainterPath()
            fm = QtGui.QFontMetricsF(f_tr)
            w = fm.horizontalAdvance(tr)
            path.addText(r.center().x() - w / 2, base - pxf(8) + pxf(8) * (1 - tr_a), f_tr, tr)
            p.setOpacity(tr_a)
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 230), 3.4, QtCore.Qt.PenStyle.SolidLine,
                                QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(T.SUB))
            p.drawPath(path)
            p.setOpacity(1.0)
        p.setClipping(False)
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE_SOFT), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), pxf(12), pxf(12))
        p.end()


class ModeCompare(QtWidgets.QWidget):
    """Tam ekran (ceviri gorunmez) vs Kenarliksiz pencere (gorunur)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(px(170))

    def _monitor(self, p, r, ok, title):
        screen = QtCore.QRectF(r.x(), r.y(), r.width(), r.height() - pxf(46))
        p.setPen(QtGui.QPen(QtGui.QColor(T.LINE), 1.5))
        p.setBrush(QtGui.QColor("#0B0908"))
        p.drawRoundedRect(screen, pxf(8), pxf(8))
        inner = screen.adjusted(pxf(6), pxf(6), -pxf(6), -pxf(6))
        g = QtGui.QLinearGradient(inner.topLeft(), inner.bottomLeft())
        g.setColorAt(0, QtGui.QColor("#33405C"))
        g.setColorAt(1, QtGui.QColor("#9C7262"))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(inner, pxf(4), pxf(4))
        # oyun yazisi
        bar = QtCore.QRectF(inner.x() + inner.width() * 0.2, inner.bottom() - pxf(24), inner.width() * 0.6, pxf(14))
        p.setBrush(QtGui.QColor(0, 0, 0, 150))
        p.drawRoundedRect(bar, pxf(3), pxf(3))
        p.setBrush(QtGui.QColor(255, 255, 255, 120))
        p.drawRoundedRect(bar.adjusted(pxf(8), pxf(5), -pxf(8), -pxf(5)), 2, 2)
        if ok:
            p.setBrush(QtGui.QColor(T.SUB))
            p.drawRoundedRect(bar.adjusted(pxf(4), pxf(4), -pxf(4), -pxf(4)), 2, 2)
        # ayak
        p.setBrush(QtGui.QColor(T.LINE))
        p.drawRect(QtCore.QRectF(screen.center().x() - pxf(2), screen.bottom(), pxf(4), pxf(8)))
        p.drawRoundedRect(QtCore.QRectF(screen.center().x() - pxf(22), screen.bottom() + pxf(8), pxf(44), pxf(3)), 1, 1)
        # rozet + ad
        badge = QtCore.QRectF(r.x(), r.bottom() - pxf(22), pxf(20), pxf(20))
        p.setBrush(QtGui.QColor(T.OK_WASH if ok else T.REC_WASH))
        p.drawEllipse(badge)
        p.drawPixmap(badge.adjusted(pxf(3), pxf(3), -pxf(3), -pxf(3)).toRect(),
                     icons.pixmap("check" if ok else "cross", T.OK if ok else "#F08A78", px(14), 2.2))
        p.setPen(QtGui.QColor(T.PAPER if ok else T.MUTED))
        p.setFont(T.font("body_medium", 10))
        p.drawText(QtCore.QRectF(badge.right() + pxf(8), badge.y(), r.width(), badge.height()),
                   QtCore.Qt.AlignmentFlag.AlignVCenter, title)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w = (self.width() - pxf(32)) / 2
        h = self.height()
        self._monitor(p, QtCore.QRectF(0, 0, w, h), False, "Tam ekran")
        self._monitor(p, QtCore.QRectF(w + pxf(32), 0, w, h), True, "Kenarlıksız pencere")
        p.end()


# ============================================================ step indicator
class Steps(QtWidgets.QWidget):
    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.names = names
        self.current = 0
        self.setFixedHeight(px(40))

    def set_current(self, i):
        self.current = i
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        n = len(self.names)
        gap = pxf(8)
        w = (self.width() - gap * (n - 1)) / n
        for i, name in enumerate(self.names):
            x = i * (w + gap)
            done = i < self.current
            cur = i == self.current
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(T.SUB if (done or cur) else T.RAISED))
            p.drawRoundedRect(QtCore.QRectF(x, 0, w, pxf(3)), 1.5, 1.5)
            p.setFont(T.font("mono_medium" if cur else "mono", 8.5))
            p.setPen(QtGui.QColor(T.SUB if cur else T.FAINT))
            p.drawText(QtCore.QRectF(x, pxf(12), pxf(24), pxf(18)), QtCore.Qt.AlignmentFlag.AlignVCenter, f"{i + 1:02d}")
            p.setFont(T.font("body_semibold" if cur else "body_medium", 9))
            p.setPen(QtGui.QColor(T.PAPER if cur else (T.MUTED if done else T.FAINT)))
            p.drawText(QtCore.QRectF(x + pxf(26), pxf(12), w - pxf(26), pxf(18)),
                       QtCore.Qt.AlignmentFlag.AlignVCenter, name)
        p.end()


# ================================================================ checks
class CheckRow(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(px(18), px(12), px(18), px(12))
        lay.setSpacing(px(12))
        self.lamp = Lamp(9)
        lay.addWidget(self.lamp, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(px(2))
        self.title = label(title, "CheckTitle")
        self.hint = label("Kontrol ediliyor…", "CheckHint", wrap=True)
        texts.addWidget(self.title)
        texts.addWidget(self.hint)
        lay.addLayout(texts, 1)

    def set_result(self, state, hint):
        self.lamp.set_state(state)
        self.hint.setText(hint)


class _CheckBridge(QtCore.QObject):
    done = QtCore.pyqtSignal(str, str, str)


# ================================================================= page
class Onboarding(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._bridge = _CheckBridge()
        self._bridge.done.connect(self._check_done)

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(px(40), px(36), px(40), px(30))
        outer.addStretch(1)
        col = QtWidgets.QWidget()
        col.setMaximumWidth(px(760))
        col.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        outer.addWidget(col, 6)
        outer.addStretch(1)
        lay = QtWidgets.QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(18))

        self.steps = Steps(["Hoş geldin", "Oyunu hazırla", "Tuşlar", "Kontrol"])
        lay.addWidget(self.steps)
        lay.addSpacing(px(10))

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._step_welcome())
        self.stack.addWidget(self._step_mode())
        self.stack.addWidget(self._step_keys())
        self.stack.addWidget(self._step_check())
        lay.addWidget(self.stack, 1)

        nav = QtWidgets.QHBoxLayout()
        self.btn_skip = text_button("Rehberi atla", "Quiet")
        self.btn_skip.clicked.connect(self._finish)
        nav.addWidget(self.btn_skip)
        nav.addStretch(1)
        self.btn_back = text_button("Geri")
        self.btn_back.clicked.connect(lambda: self._go(self.stack.currentIndex() - 1))
        self.btn_next = text_button("Devam", "Primary")
        self.btn_next.setMinimumWidth(px(120))
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        lay.addLayout(nav)
        self._go(0)

    # ------------------------------------------------------------ steps
    def _text_block(self, title, lead):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(10))
        lay.addWidget(label(title, "OnbTitle", wrap=True))
        lay.addWidget(label(lead, "OnbLead", wrap=True))
        return w, lay

    def _step_welcome(self):
        w, lay = self._text_block(
            "Her oyun, Türkçe.",
            "Oyun Çevirmen ekrandaki yabancı yazıları okur, Türkçeye çevirir ve oyunun tam üstüne yazar. "
            "Oyuna hiçbir şey kurulmaz, oyunun dosyalarına dokunulmaz; program sadece ekrana bakar.")
        lay.addSpacing(px(14))
        lay.addWidget(TranslateLoop())
        lay.addStretch(1)
        return w

    def _step_mode(self):
        w, lay = self._text_block(
            "Oyunu kenarlıksız pencerede aç.",
            "Tam ekran modunda Windows, oyunun üstüne başka hiçbir şey çizdirmez; çeviriler görünmez. "
            "Oyunun görüntü ayarlarında Kenarlıksız pencere (Borderless veya Windowed Fullscreen) "
            "seçeneğini seç. Görüntü aynı kalır.")
        lay.addSpacing(px(18))
        lay.addWidget(ModeCompare())
        lay.addStretch(1)
        return w

    def _step_keys(self):
        w, lay = self._text_block(
            "İki tuş yeter.",
            "Oyun açıkken bu tuşlar her zaman çalışır. İstersen Kısayollar sayfasından değiştirebilirsin.")
        lay.addSpacing(px(16))
        self.keys_instant = Keycaps("f9", "lg")
        self.keys_live = Keycaps("f10", "lg")
        for caps, title, desc in (
            (self.keys_instant, "Anında tara",
             "Ekranı bir kez okur, bulduğu her yazının üstüne Türkçesini koyar. Menüler, envanter, "
             "görev ekranları için. Tekrar basınca çeviriler kalkar."),
            (self.keys_live, "Canlı mod",
             "Ekranı sürekli izler, değişen yerleri çevirir. Diyaloglar ve altyazılar için. "
             "Tekrar basınca durur."),
        ):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(px(20))
            holder = QtWidgets.QWidget()
            holder.setFixedWidth(px(112))
            hl = QtWidgets.QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(caps)
            hl.addStretch(1)
            row.addWidget(holder, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            texts = QtWidgets.QVBoxLayout()
            texts.setSpacing(px(3))
            texts.addWidget(label(title, "SectionTitle"))
            texts.addWidget(label(desc, "SectionLead", wrap=True))
            row.addLayout(texts, 1)
            lay.addLayout(row)
            lay.addSpacing(px(14))
        lay.addStretch(1)
        return w

    def _step_check(self):
        w, lay = self._text_block(
            "Her şey hazır mı?",
            "Gerekenleri senin için kontrol ediyorum. Eksik bir şey olsa bile başlayabilirsin; "
            "Ollama çalışmazsa çeviriler Google Translate ile yapılır.")
        lay.addSpacing(px(10))
        box = QtWidgets.QFrame()
        box.setObjectName("CheckBox")
        box.setStyleSheet(f"#CheckBox {{ background: {T.SURFACE}; border: 1px solid {T.LINE_SOFT};"
                          f" border-radius: {px(12)}px; }}")
        bl = QtWidgets.QVBoxLayout(box)
        bl.setContentsMargins(0, px(4), 0, px(4))
        bl.setSpacing(0)
        self.checks = {
            "ollama": CheckRow("Çeviri motoru (Ollama)"),
            "model": CheckRow("Çeviri modeli"),
            "gpu": CheckRow("Ekran kartı"),
            "ocr": CheckRow("Yazı okuma"),
        }
        for i, row in enumerate(self.checks.values()):
            if i:
                sep = QtWidgets.QFrame()
                sep.setObjectName("Separator")
                sep.setFixedHeight(1)
                bl.addWidget(sep)
            bl.addWidget(row)
        lay.addWidget(box)
        again = QtWidgets.QHBoxLayout()
        self.btn_recheck = text_button("Yeniden kontrol et", "Quiet", "refresh")
        self.btn_recheck.clicked.connect(self.run_checks)
        again.addWidget(self.btn_recheck)
        again.addStretch(1)
        lay.addLayout(again)
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------- nav
    def _go(self, i):
        i = max(0, min(self.stack.count() - 1, i))
        self.stack.setCurrentIndex(i)
        self.steps.set_current(i)
        self.btn_back.setVisible(i > 0)
        last = i == self.stack.count() - 1
        self.btn_next.setText("Başla" if last else "Devam")
        self.btn_skip.setVisible(not last)
        if i == 2:
            self.keys_instant.set_value(self.ctx.config.get("hotkey_instant", "f9"))
            self.keys_live.set_value(self.ctx.config.get("hotkey_live_toggle", "f10"))
        if last:
            self.run_checks()
        self.btn_next.setFocus()

    def _next(self):
        if self.stack.currentIndex() == self.stack.count() - 1:
            self._finish()
        else:
            self._go(self.stack.currentIndex() + 1)

    def keyPressEvent(self, e):
        if e.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._next()
        elif e.key() == QtCore.Qt.Key.Key_Escape and self.stack.currentIndex() > 0:
            self._go(self.stack.currentIndex() - 1)
        else:
            super().keyPressEvent(e)

    def restart(self):
        self._go(0)

    def _finish(self):
        self.ctx.config["onboarding_done"] = True
        self.ctx.save_now()
        self.finished.emit()

    # ----------------------------------------------------------- checks
    def run_checks(self):
        for row in self.checks.values():
            row.set_result("sub", "Kontrol ediliyor…")
        o = self.ctx.orchestrator
        cfg = self.ctx.config

        def ollama():
            try:
                ok = o.translator.ollama.is_available()
            except Exception:
                ok = False
            if ok:
                self._bridge.done.emit("ollama", "ok", "Çalışıyor.")
            else:
                self._bridge.done.emit("ollama", "bad", "Çalışmıyor. Ollama'yı başlat veya Kurulum.bat'ı "
                                                        "yeniden çalıştır. Bu arada Google Translate kullanılır.")

        def model():
            name = cfg.get("ollama_model", "")
            try:
                out = subprocess.check_output(["ollama", "list"], creationflags=CREATE_NO_WINDOW,
                                              timeout=6).decode("utf-8", "ignore")
                have = [ln.split()[0] for ln in out.splitlines()[1:] if ln.strip()]
            except Exception:
                have = []
            if name and any(h == name or h.split(":")[0] == name.split(":")[0] for h in have):
                self._bridge.done.emit("model", "ok", f"{name} yüklü.")
            elif have:
                self._bridge.done.emit("model", "bad", f"{name} bulunamadı. Çeviri sayfasından yüklü bir "
                                                       f"model seç: {', '.join(have[:3])}")
            else:
                self._bridge.done.emit("model", "bad", f"Model listesi alınamadı. Komut satırında "
                                                       f"\"ollama pull {name}\" ile indirebilirsin.")

        def gpu():
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                    creationflags=CREATE_NO_WINDOW, timeout=4).decode("utf-8", "ignore").strip().splitlines()[0]
                name, total = [x.strip() for x in out.split(",")]
                self._bridge.done.emit("gpu", "ok", f"{name.replace('NVIDIA ', '')}, "
                                                    f"{float(total) / 1024:.0f} GB bellek.")
            except Exception:
                self._bridge.done.emit("gpu", "off", "NVIDIA kart bulunamadı. Program çalışır ama "
                                                     "çeviriler daha yavaş olabilir.")

        def ocr():
            try:
                engine = o.ocr_manager.get_engine()
                ok = engine is not None
            except Exception:
                ok = False
            name = {"windows": "Windows OCR", "easyocr": "EasyOCR"}.get(cfg.get("ocr_engine"), "OCR")
            if ok:
                self._bridge.done.emit("ocr", "ok", f"{name} hazır.")
            else:
                self._bridge.done.emit("ocr", "bad", f"{name} başlatılamadı. Windows ayarlarından "
                                                     f"İngilizce dil paketini ekle veya Kurulum.bat'ı çalıştır.")

        for fn in (ollama, model, gpu, ocr):
            threading.Thread(target=fn, daemon=True).start()

    def _check_done(self, key, state, hint):
        self.checks[key].set_result(state, hint)
