"""Ceviri sayfasi: yazi okuma ve ceviri motorlari, model, dil, deneme."""
import subprocess
import threading
import time

from PyQt6 import QtCore, QtWidgets

from app.ui import theme as T
from app.ui.theme import px
from app.ui.widgets import (Combo, IconButton, Page, SettingsGroup, label, section_header,
                            text_button)

OCR_ENGINES = [
    ("windows", "Windows OCR", "Windows'la gelir, kurulum istemez."),
    ("easyocr", "EasyOCR (ekran kartı)", "Süslü oyun yazı tiplerinde daha isabetli."),
]
TRANSLATE_ENGINES = [
    ("ollama", "Ollama", "Bilgisayarında çalışır, internet gerekmez."),
    ("google", "Google Translate", "İnternet gerekir; Ollama yoksa yedek olarak da kullanılır."),
]
SOURCE_LANGS = [
    ("auto", "Otomatik algıla"), ("en", "İngilizce"), ("de", "Almanca"),
    ("fr", "Fransızca"), ("es", "İspanyolca"), ("it", "İtalyanca"),
    ("pt", "Portekizce"), ("ru", "Rusça"), ("ja", "Japonca"),
    ("ko", "Korece"), ("zh-cn", "Çince (basitleştirilmiş)"),
]
CREATE_NO_WINDOW = 0x08000000


class _Bridge(QtCore.QObject):
    models = QtCore.pyqtSignal(list)
    result = QtCore.pyqtSignal(str, str, float)


class TranslationPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("Çeviri", "Ekrandaki yazıyı neyin okuyacağını ve neyin çevireceğini seç. "
                                   "Değişiklikler anında uygulanır.")
        self.ctx = ctx
        self._bridge = _Bridge()
        self._bridge.models.connect(self._fill_models)
        self._bridge.result.connect(self._show_result)

        self.body.addWidget(section_header("Motorlar"))
        g = SettingsGroup()

        self.combo_ocr = Combo()
        for key, name, _ in OCR_ENGINES:
            self.combo_ocr.addItem(name, key)
        self.ocr_row = g.row("Yazı okuma", OCR_ENGINES[0][2], self.combo_ocr)

        self.combo_translate = Combo()
        for key, name, _ in TRANSLATE_ENGINES:
            self.combo_translate.addItem(name, key)
        self.tr_row = g.row("Çeviri", TRANSLATE_ENGINES[0][2], self.combo_translate)

        model_box = QtWidgets.QHBoxLayout()
        model_box.setSpacing(px(6))
        self.combo_model = Combo()
        self.combo_model.setEditable(True)
        self.combo_model.setMinimumContentsLength(16)
        self.btn_models = IconButton("refresh", "Modelleri yeniden listele", 16)
        self.btn_models.clicked.connect(self.refresh_models)
        model_box.addWidget(self.combo_model, 1)
        model_box.addWidget(self.btn_models)
        self.model_row = g.row("Ollama modeli", "Bilgisayarında yüklü modeller listelenir.", model_box)

        self.combo_lang = Combo()
        for code, name in SOURCE_LANGS:
            self.combo_lang.addItem(name, code)
        g.row("Oyunun dili", "Biliyorsan seç; otomatik algılamadan daha isabetli okur.", self.combo_lang)

        self.edit_host = QtWidgets.QLineEdit()
        self.edit_host.setMinimumWidth(px(220))
        g.row("Ollama adresi", "Genelde değiştirmen gerekmez.", self.edit_host)
        self.body.addWidget(g)

        self.body.addSpacing(px(12))
        self.body.addWidget(section_header(
            "Dene", "Oyuna girmeden önce seçtiğin motorun nasıl çevirdiğini gör."))
        trial = SettingsGroup()
        holder = QtWidgets.QWidget()
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(px(20), px(16), px(20), px(18))
        hl.setSpacing(px(12))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(8))
        self.edit_trial = QtWidgets.QLineEdit("You need a rusty key to open this chest.")
        self.edit_trial.returnPressed.connect(self.run_trial)
        self.btn_trial = text_button("Çevir", "Primary")
        self.btn_trial.clicked.connect(self.run_trial)
        row.addWidget(self.edit_trial, 1)
        row.addWidget(self.btn_trial)
        hl.addLayout(row)

        self.strip = QtWidgets.QFrame()
        self.strip.setObjectName("TrialStrip")
        sl = QtWidgets.QVBoxLayout(self.strip)
        sl.setContentsMargins(px(20), px(16), px(20), px(14))
        sl.setSpacing(px(4))
        self.trial_text = label("Çeviri burada görünecek.", "TrialText", wrap=True, selectable=True)
        self.trial_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.trial_orig = label("", "TrialOriginal", wrap=True)
        self.trial_orig.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.trial_meta = label("", "TrialMeta")
        self.trial_meta.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self.trial_text)
        sl.addWidget(self.trial_orig)
        sl.addSpacing(px(4))
        sl.addWidget(self.trial_meta)
        hl.addWidget(self.strip)
        trial.add(holder)
        self.body.addWidget(trial)
        self.finish()

        self.combo_ocr.currentIndexChanged.connect(self._hints)
        self.combo_translate.currentIndexChanged.connect(self._hints)
        for w in (self.combo_ocr, self.combo_translate, self.combo_lang):
            w.currentIndexChanged.connect(ctx.schedule_save)
        self.combo_model.currentIndexChanged.connect(ctx.schedule_save)
        self.combo_model.editTextChanged.connect(ctx.schedule_save)
        self.edit_host.editingFinished.connect(ctx.schedule_save)

    # ---------------------------------------------------------- ayarlar
    def load(self, cfg):
        _set(self.combo_ocr, cfg.get("ocr_engine", "windows"))
        _set(self.combo_translate, cfg.get("translate_engine", "ollama"))
        self.combo_model.setCurrentText(cfg.get("ollama_model", "aya-expanse:8b"))
        self.edit_host.setText(cfg.get("ollama_host", "http://127.0.0.1:11434"))
        lang = cfg.get("source_lang", "auto")
        if self.combo_lang.findData(lang) < 0:
            self.combo_lang.addItem(lang, lang)
        _set(self.combo_lang, lang)
        self._hints()

    def save(self, cfg):
        cfg["ocr_engine"] = self.combo_ocr.currentData()
        cfg["translate_engine"] = self.combo_translate.currentData()
        cfg["ollama_model"] = self.combo_model.currentText().strip()
        cfg["ollama_host"] = self.edit_host.text().strip() or "http://127.0.0.1:11434"
        cfg["source_lang"] = self.combo_lang.currentData() or "auto"

    def _hints(self, *_):
        ocr = dict((k, h) for k, _n, h in OCR_ENGINES).get(self.combo_ocr.currentData(), "")
        tr = dict((k, h) for k, _n, h in TRANSLATE_ENGINES).get(self.combo_translate.currentData(), "")
        _set_hint(self.ocr_row, ocr)
        _set_hint(self.tr_row, tr)
        self.model_row.setEnabled(self.combo_translate.currentData() == "ollama")

    # ----------------------------------------------------------- modeller
    def refresh_models(self):
        def worker():
            try:
                out = subprocess.check_output(
                    ["ollama", "list"], creationflags=CREATE_NO_WINDOW, timeout=5
                ).decode("utf-8", "ignore").splitlines()
                names = [line.split()[0] for line in out[1:] if line.strip()]
            except Exception:
                names = []
            self._bridge.models.emit(names)
        threading.Thread(target=worker, daemon=True).start()

    def _fill_models(self, names):
        current = self.combo_model.currentText() or self.ctx.config.get("ollama_model", "")
        with self.ctx.loading():
            self.combo_model.clear()
            self.combo_model.addItems(names)
            self.combo_model.setCurrentText(current)

    # ------------------------------------------------------------ deneme
    def run_trial(self):
        text = self.edit_trial.text().strip()
        if not text:
            return
        self.ctx.apply_now()
        self.btn_trial.setEnabled(False)
        self.trial_text.setText("Çevriliyor…")
        self.trial_orig.setText(text)
        self.trial_meta.setText("")

        def worker():
            t0 = time.perf_counter()
            try:
                result = self.ctx.orchestrator.translator.translate(text)
            except Exception as exc:
                result = None
                self._bridge.result.emit(f"Çeviri yapılamadı: {exc}", text, -1.0)
                return
            self._bridge.result.emit(result or "", text, time.perf_counter() - t0)

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, result, original, seconds):
        self.btn_trial.setEnabled(True)
        if not result:
            self.trial_text.setText("Çeviri alınamadı.")
            self.trial_meta.setText("Ayrıntı için Günlük sayfasına bak.")
            return
        self.trial_text.setText(result)
        self.trial_orig.setText(original)
        engine = self.combo_translate.currentText()
        if seconds >= 0:
            speed = "hafızadan" if seconds < 0.02 else f"{seconds:.2f} sn"
            self.trial_meta.setText(f"{engine}, {speed}")


def _set(combo, value):
    i = combo.findData(value)
    if i >= 0:
        combo.setCurrentIndex(i)


def _set_hint(row, text):
    for lbl in row.findChildren(QtWidgets.QLabel):
        if lbl.objectName() == "RowHint":
            lbl.setText(text)
            return
