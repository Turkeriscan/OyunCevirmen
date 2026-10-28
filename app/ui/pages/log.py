"""Gunluk sayfasi: renklendirilmis, suzulebilir kayit goruntuleyici."""
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from app.ui import theme as T
from app.ui.theme import px
from app.ui.widgets import label, text_button

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "oyuncevirmen.log")

FILTERS = [("all", "Tümü"), ("warn", "Uyarılar"), ("error", "Hatalar")]


class LogHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)

        def fmt(color, bold=False):
            f = QtGui.QTextCharFormat()
            f.setForeground(QtGui.QColor(color))
            if bold:
                f.setFontWeight(QtGui.QFont.Weight.DemiBold)
            return f

        self.f_time = fmt(T.FAINT)
        self.f_info = fmt("#BDB2A3")
        self.f_warn = fmt(T.SUB)
        self.f_error = fmt("#F08A78", True)
        self.f_name = fmt("#8C8172")

    def highlightBlock(self, text):
        if "[ERROR]" in text or "Traceback" in text:
            self.setFormat(0, len(text), self.f_error)
            return
        if "[WARNING]" in text:
            self.setFormat(0, len(text), self.f_warn)
            return
        i = text.find(" [")
        if i > 0:
            self.setFormat(0, i, self.f_time)
            j = text.find(":", text.find("]", i) + 1)
            if j > 0:
                self.setFormat(text.find("]", i) + 1, j - text.find("]", i), self.f_name)


class LogPage(QtWidgets.QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._filter = "all"
        self._raw = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(40), px(34), px(40), px(28))
        lay.setSpacing(px(14))
        lay.addWidget(label("Günlük", "PageTitle"))
        lay.addWidget(label("Programın yaptıkları. Bir şey ters giderse sebebi son satırlardadır.",
                            "PageLead", wrap=True))
        lay.addSpacing(px(4))

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(px(6))
        self.group = QtWidgets.QButtonGroup(self)
        for key, name in FILTERS:
            b = QtWidgets.QPushButton(name)
            b.setObjectName("Quiet")
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton:checked {{ background: {T.RAISED}; color: {T.PAPER};"
                            f" border: 1px solid {T.LINE}; }}")
            b.setChecked(key == "all")
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self.group.addButton(b)
            bar.addWidget(b)
        bar.addStretch(1)
        btn_copy = text_button("Kopyala", None, "copy")
        btn_copy.clicked.connect(self._copy)
        btn_open = text_button("Klasörü aç", None, "folder")
        btn_open.clicked.connect(self._open_folder)
        bar.addWidget(btn_copy)
        bar.addWidget(btn_open)
        lay.addLayout(bar)

        self.view = QtWidgets.QPlainTextEdit()
        self.view.setObjectName("LogView")
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setFont(T.font("mono", 9))
        self.highlighter = LogHighlighter(self.view.document())
        lay.addWidget(self.view, 1)

    def _set_filter(self, key):
        self._filter = key
        self._render(force=True)

    def refresh(self):
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 40000))
                data = f.read()
        except Exception:
            data = ""
        if data != self._raw:
            self._raw = data
            self._render()

    def _render(self, force=False):
        lines = (self._raw or "").splitlines()
        if self._filter == "warn":
            lines = [ln for ln in lines if "[WARNING]" in ln or "[ERROR]" in ln]
        elif self._filter == "error":
            lines = [ln for ln in lines if "[ERROR]" in ln or "Traceback" in ln]
        text = "\n".join(lines[-600:]) or {
            "all": "Henüz kayıt yok.", "warn": "Uyarı yok.", "error": "Hata yok."}[self._filter]
        bar = self.view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.view.setPlainText(text)
        if at_bottom or force:
            bar.setValue(bar.maximum())

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.view.toPlainText())
        self.ctx.flash("Günlük panoya kopyalandı")

    def _open_folder(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(LOG_DIR))
