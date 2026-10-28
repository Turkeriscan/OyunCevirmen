"""
Ana kontrol penceresi (arayuz).

Bu pencere programin "yuzu"dur: durum bilgisini (Ollama/GPU/OCR/ceviri
motoru, canli mod) gosterir, F9/F10/F11 islemlerini butonlarla da sunar
ve tum ayarlari (config.json) sekmeli bir form uzerinden duzenlemeyi
saglar. Degisiklikler hem aninda calisan programa uygulanir (ayni config
sozlugu referansi paylasildigi icin) hem de diske yazilir.

Pencere kapatilinca (X) programi KAPATMAZ, sadece sistem tepsisine gizlenir
(gercek kapanis F11 / tepsi menusundeki "Cikis" ile olur).
"""
import logging
import os
import subprocess
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from app import config as config_mod

logger = logging.getLogger("OyunCevirmen.mainwindow")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON_PATH = os.path.join(BASE_DIR, "app", "assets", "icon.ico")
LOG_PATH = os.path.join(BASE_DIR, "logs", "oyuncevirmen.log")

CREATE_NO_WINDOW = 0x08000000

OCR_ENGINES = [("windows", "Windows OCR (varsayılan, kurulum gerektirmez)"),
               ("easyocr", "EasyOCR (GPU / CUDA)")]
TRANSLATE_ENGINES = [("ollama", "Ollama (yerel, GPU, internetsiz)"),
                     ("google", "Google Translate (internet gerekir)")]
SOURCE_LANGS = ["auto", "en", "de", "fr", "es", "it", "pt", "ru", "ja", "ko", "zh-cn"]
FUNCTION_KEYS = [f"f{i}" for i in range(1, 13)]


def _hex_to_qcolor(hexstr):
    try:
        return QtGui.QColor(hexstr)
    except Exception:
        return QtGui.QColor("#141414")


class _HotkeyCaptureBridge(QtCore.QObject):
    captured = QtCore.pyqtSignal(str, str)  # (field_key, hotkey_string)


class HotkeyRow(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()

    def __init__(self, field_key, initial_value, parent=None):
        super().__init__(parent)
        self.field_key = field_key
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chk_ctrl = QtWidgets.QCheckBox("Ctrl")
        self.chk_alt = QtWidgets.QCheckBox("Alt")
        self.chk_shift = QtWidgets.QCheckBox("Shift")
        self.combo_key = QtWidgets.QComboBox()
        self.combo_key.addItems(FUNCTION_KEYS)

        self._apply_value(initial_value)

        for w in (self.chk_ctrl, self.chk_alt, self.chk_shift):
            w.stateChanged.connect(self._emit_changed)
        self.combo_key.currentIndexChanged.connect(self._emit_changed)

        layout.addWidget(self.chk_ctrl)
        layout.addWidget(self.chk_alt)
        layout.addWidget(self.chk_shift)
        layout.addWidget(self.combo_key)
        layout.addStretch(1)

    def _apply_value(self, value):
        parts = (value or "f9").lower().split("+")
        base = parts[-1]
        mods = parts[:-1]
        self.chk_ctrl.setChecked("ctrl" in mods)
        self.chk_alt.setChecked("alt" in mods)
        self.chk_shift.setChecked("shift" in mods)
        if base in FUNCTION_KEYS:
            self.combo_key.setCurrentText(base)

    def _emit_changed(self, *_):
        self.changed.emit()

    def value(self):
        mods = []
        if self.chk_ctrl.isChecked():
            mods.append("ctrl")
        if self.chk_alt.isChecked():
            mods.append("alt")
        if self.chk_shift.isChecked():
            mods.append("shift")
        mods.append(self.combo_key.currentText())
        return "+".join(mods)


class ColorButton(QtWidgets.QPushButton):
    changed = QtCore.pyqtSignal()

    def __init__(self, hex_color, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self.setFixedWidth(90)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        self.setText(self._hex)
        self.setStyleSheet(
            f"background-color:{self._hex}; color:white; border:1px solid #555; padding:4px;"
        )

    def _pick(self):
        color = QtWidgets.QColorDialog.getColor(_hex_to_qcolor(self._hex), self, "Renk Seç")
        if color.isValid():
            self._hex = color.name()
            self._refresh()
            self.changed.emit()

    def hex(self):
        return self._hex


class MainWindow(QtWidgets.QWidget):
    def __init__(self, config, orchestrator):
        super().__init__()
        self.config = config  # canli, paylasilan config sozlugu (ayni referans)
        self.orchestrator = orchestrator

        self.setWindowTitle("Oyun Çevirmen")
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        self.resize(640, 560)

        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._apply_and_save)

        self._build_ui()
        self._load_from_config()
        self._wire_change_signals()

        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(3000)
        self._refresh_status()

    # ------------------------------------------------------------ arayuz
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        root.addWidget(self._build_status_bar())

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "Genel")
        self.tabs.addTab(self._build_appearance_tab(), "Görünüm")
        self.tabs.addTab(self._build_hotkeys_tab(), "Kısayollar")
        self.tabs.addTab(self._build_performance_tab(), "Performans")
        self.tabs.addTab(self._build_log_tab(), "Günlük")
        root.addWidget(self.tabs, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.lbl_saved = QtWidgets.QLabel("")
        self.lbl_saved.setStyleSheet("color: #2e9e4a;")
        bottom.addWidget(self.lbl_saved)
        bottom.addStretch(1)
        btn_defaults = QtWidgets.QPushButton("Varsayılanlara Dön")
        btn_defaults.clicked.connect(self._reset_defaults)
        bottom.addWidget(btn_defaults)
        root.addLayout(bottom)

    def _build_status_bar(self):
        box = QtWidgets.QGroupBox("Durum")
        layout = QtWidgets.QGridLayout(box)

        self.lbl_ollama = QtWidgets.QLabel("Ollama: ?")
        self.lbl_gpu = QtWidgets.QLabel("GPU: ?")
        self.lbl_mode = QtWidgets.QLabel("Mod: Kapalı")

        layout.addWidget(self.lbl_ollama, 0, 0)
        layout.addWidget(self.lbl_gpu, 0, 1)
        layout.addWidget(self.lbl_mode, 0, 2)

        btn_instant = QtWidgets.QPushButton("Anında Tara (F9)")
        btn_instant.clicked.connect(self.orchestrator.toggle_instant)
        btn_live = QtWidgets.QPushButton("Canlı Modu Aç/Kapat (F10)")
        btn_live.clicked.connect(self.orchestrator.toggle_live)
        btn_quit = QtWidgets.QPushButton("Programı Kapat (F11)")
        btn_quit.setStyleSheet("color:#b02a2a;")
        btn_quit.clicked.connect(self.orchestrator.request_quit)

        layout.addWidget(btn_instant, 1, 0)
        layout.addWidget(btn_live, 1, 1)
        layout.addWidget(btn_quit, 1, 2)
        return box

    def _build_general_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)

        self.combo_ocr = QtWidgets.QComboBox()
        for key, label in OCR_ENGINES:
            self.combo_ocr.addItem(label, userData=key)
        form.addRow("OCR motoru:", self.combo_ocr)

        self.combo_translate = QtWidgets.QComboBox()
        for key, label in TRANSLATE_ENGINES:
            self.combo_translate.addItem(label, userData=key)
        form.addRow("Çeviri motoru:", self.combo_translate)

        model_row = QtWidgets.QHBoxLayout()
        self.combo_model = QtWidgets.QComboBox()
        self.combo_model.setEditable(True)
        btn_refresh_models = QtWidgets.QPushButton("Yenile")
        btn_refresh_models.clicked.connect(self._refresh_ollama_models)
        model_row.addWidget(self.combo_model, 1)
        model_row.addWidget(btn_refresh_models)
        form.addRow("Ollama modeli:", model_row)

        self.edit_host = QtWidgets.QLineEdit()
        form.addRow("Ollama adresi:", self.edit_host)

        self.combo_source_lang = QtWidgets.QComboBox()
        self.combo_source_lang.setEditable(True)
        self.combo_source_lang.addItems(SOURCE_LANGS)
        form.addRow("Kaynak dil:", self.combo_source_lang)

        test_row = QtWidgets.QHBoxLayout()
        self.edit_test_input = QtWidgets.QLineEdit("Press E to open the door")
        btn_test = QtWidgets.QPushButton("Çeviriyi Test Et")
        btn_test.clicked.connect(self._run_translation_test)
        test_row.addWidget(self.edit_test_input, 1)
        test_row.addWidget(btn_test)
        form.addRow("Test cümlesi:", test_row)
        self.lbl_test_result = QtWidgets.QLabel("")
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setStyleSheet("color:#2e6fa0; font-weight:bold;")
        form.addRow("Sonuç:", self.lbl_test_result)

        self._refresh_ollama_models()
        return w

    def _build_appearance_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)

        self.spin_font = QtWidgets.QSpinBox()
        self.spin_font.setRange(6, 60)
        form.addRow("Font boyutu:", self.spin_font)

        self.spin_min_font = QtWidgets.QSpinBox()
        self.spin_min_font.setRange(6, 60)
        form.addRow("En küçük font boyutu:", self.spin_min_font)

        self.slider_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.lbl_opacity = QtWidgets.QLabel("72%")
        opacity_row = QtWidgets.QHBoxLayout()
        opacity_row.addWidget(self.slider_opacity, 1)
        opacity_row.addWidget(self.lbl_opacity)
        self.slider_opacity.valueChanged.connect(
            lambda v: self.lbl_opacity.setText(f"{v}%")
        )
        form.addRow("Kutu saydamlığı:", opacity_row)

        self.btn_bg_color = ColorButton("#141414")
        form.addRow("Arka plan rengi:", self.btn_bg_color)

        self.btn_text_color = ColorButton("#FFFFFF")
        form.addRow("Yazı rengi:", self.btn_text_color)

        return w

    def _build_hotkeys_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)

        self.row_instant = HotkeyRow("hotkey_instant", "f9")
        self.row_live = HotkeyRow("hotkey_live_toggle", "f10")
        self.row_quit = HotkeyRow("hotkey_quit", "f11")

        form.addRow("Anında mod:", self.row_instant)
        form.addRow("Canlı mod aç/kapat:", self.row_live)
        form.addRow("Programı kapat:", self.row_quit)

        note = QtWidgets.QLabel(
            "Kısayollar global'dir; oyun odakta olsa da çalışır. Değişiklik anında uygulanır."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#777;")
        form.addRow(note)
        return w

    def _build_performance_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)

        self.spin_interval = QtWidgets.QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 5.0)
        self.spin_interval.setSingleStep(0.05)
        self.spin_interval.setSuffix(" sn")
        form.addRow("Canlı mod tarama sıklığı:", self.spin_interval)

        self.spin_cols = QtWidgets.QSpinBox()
        self.spin_cols.setRange(1, 20)
        form.addRow("Canlı mod - sütun sayısı:", self.spin_cols)

        self.spin_rows = QtWidgets.QSpinBox()
        self.spin_rows.setRange(1, 20)
        form.addRow("Canlı mod - satır sayısı:", self.spin_rows)

        self.spin_padding = QtWidgets.QSpinBox()
        self.spin_padding.setRange(0, 300)
        self.spin_padding.setSuffix(" px")
        form.addRow("Canlı mod - hücre payı (padding):", self.spin_padding)

        self.spin_min_len = QtWidgets.QSpinBox()
        self.spin_min_len.setRange(1, 20)
        form.addRow("Min. metin uzunluğu:", self.spin_min_len)

        self.spin_min_conf = QtWidgets.QDoubleSpinBox()
        self.spin_min_conf.setRange(0.0, 1.0)
        self.spin_min_conf.setSingleStep(0.05)
        form.addRow("Min. OCR güven skoru:", self.spin_min_conf)

        self.spin_cache = QtWidgets.QSpinBox()
        self.spin_cache.setRange(100, 50000)
        self.spin_cache.setSingleStep(100)
        form.addRow("Bellek önbellek boyutu:", self.spin_cache)

        self.spin_monitor = QtWidgets.QSpinBox()
        self.spin_monitor.setRange(0, 8)
        monitor_row = QtWidgets.QHBoxLayout()
        monitor_row.addWidget(self.spin_monitor)
        lbl_restart = QtWidgets.QLabel("(* değişiklik için programı yeniden başlatın)")
        lbl_restart.setStyleSheet("color:#a06a2e;")
        monitor_row.addWidget(lbl_restart)
        monitor_row.addStretch(1)
        form.addRow("Yakalanacak monitör:", monitor_row)

        return w

    def _build_log_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QtGui.QFont("Consolas", 9))
        layout.addWidget(self.txt_log)

        self._log_timer = QtCore.QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(2000)
        self._refresh_log()
        return w

    # --------------------------------------------------------- yukleme
    def _load_from_config(self):
        cfg = self.config
        self._set_combo_data(self.combo_ocr, cfg.get("ocr_engine", "windows"))
        self._set_combo_data(self.combo_translate, cfg.get("translate_engine", "ollama"))
        self.combo_model.setCurrentText(cfg.get("ollama_model", "aya-expanse:8b"))
        self.edit_host.setText(cfg.get("ollama_host", "http://127.0.0.1:11434"))
        self.combo_source_lang.setCurrentText(cfg.get("source_lang", "auto"))

        self.spin_font.setValue(cfg.get("font_size", 18))
        self.spin_min_font.setValue(cfg.get("min_font_size", 10))
        self.slider_opacity.setValue(int(round(cfg.get("overlay_opacity", 0.72) * 100)))
        self.btn_bg_color._hex = cfg.get("overlay_bg_color", "#141414")
        self.btn_bg_color._refresh()
        self.btn_text_color._hex = cfg.get("overlay_text_color", "#FFFFFF")
        self.btn_text_color._refresh()

        self.row_instant._apply_value(cfg.get("hotkey_instant", "f9"))
        self.row_live._apply_value(cfg.get("hotkey_live_toggle", "f10"))
        self.row_quit._apply_value(cfg.get("hotkey_quit", "f11"))

        self.spin_interval.setValue(cfg.get("live_scan_interval", 0.45))
        self.spin_cols.setValue(cfg.get("live_grid_cols", 6))
        self.spin_rows.setValue(cfg.get("live_grid_rows", 4))
        self.spin_padding.setValue(cfg.get("live_cell_padding", 60))
        self.spin_min_len.setValue(cfg.get("min_text_length", 2))
        self.spin_min_conf.setValue(cfg.get("min_ocr_confidence", 0.45))
        self.spin_cache.setValue(cfg.get("max_cache_memory_items", 5000))
        self.spin_monitor.setValue(cfg.get("capture_monitor_index", 0))

    @staticmethod
    def _set_combo_data(combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _wire_change_signals(self):
        widgets_simple = [
            self.combo_ocr, self.combo_translate, self.combo_model, self.edit_host,
            self.combo_source_lang, self.spin_font, self.spin_min_font,
            self.slider_opacity, self.spin_interval, self.spin_cols, self.spin_rows,
            self.spin_min_len, self.spin_min_conf, self.spin_cache, self.spin_monitor,
            self.spin_padding,
        ]
        for widget in widgets_simple:
            if isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(self._schedule_save)
                widget.editTextChanged.connect(self._schedule_save)
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.editingFinished.connect(self._schedule_save)
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QSlider)):
                widget.valueChanged.connect(self._schedule_save)

        self.btn_bg_color.changed.connect(self._schedule_save)
        self.btn_text_color.changed.connect(self._schedule_save)
        self.row_instant.changed.connect(self._schedule_save)
        self.row_live.changed.connect(self._schedule_save)
        self.row_quit.changed.connect(self._schedule_save)

    def _schedule_save(self, *_):
        self.lbl_saved.setText("")
        self._save_timer.start(500)

    # ------------------------------------------------------ uygulama
    def _apply_and_save(self):
        cfg = self.config
        old_hotkeys = (
            cfg.get("hotkey_instant"), cfg.get("hotkey_live_toggle"), cfg.get("hotkey_quit")
        )

        cfg["ocr_engine"] = self.combo_ocr.currentData()
        cfg["translate_engine"] = self.combo_translate.currentData()
        cfg["ollama_model"] = self.combo_model.currentText().strip()
        cfg["ollama_host"] = self.edit_host.text().strip() or "http://127.0.0.1:11434"
        cfg["source_lang"] = self.combo_source_lang.currentText().strip() or "auto"

        cfg["font_size"] = self.spin_font.value()
        cfg["min_font_size"] = self.spin_min_font.value()
        cfg["overlay_opacity"] = round(self.slider_opacity.value() / 100.0, 2)
        cfg["overlay_bg_color"] = self.btn_bg_color.hex()
        cfg["overlay_text_color"] = self.btn_text_color.hex()

        cfg["hotkey_instant"] = self.row_instant.value()
        cfg["hotkey_live_toggle"] = self.row_live.value()
        cfg["hotkey_quit"] = self.row_quit.value()

        cfg["live_scan_interval"] = self.spin_interval.value()
        cfg["live_grid_cols"] = self.spin_cols.value()
        cfg["live_grid_rows"] = self.spin_rows.value()
        cfg["live_cell_padding"] = self.spin_padding.value()
        cfg["min_text_length"] = self.spin_min_len.value()
        cfg["min_ocr_confidence"] = round(self.spin_min_conf.value(), 2)
        cfg["max_cache_memory_items"] = self.spin_cache.value()
        cfg["capture_monitor_index"] = self.spin_monitor.value()

        config_mod.save_config(cfg)

        new_hotkeys = (
            cfg.get("hotkey_instant"), cfg.get("hotkey_live_toggle"), cfg.get("hotkey_quit")
        )
        if new_hotkeys != old_hotkeys:
            try:
                self.orchestrator.hotkeys.start()
                logger.info("Kisayollar yeniden kaydedildi: %s", new_hotkeys)
            except Exception as exc:
                logger.error("Kisayollar yeniden kaydedilemedi: %s", exc)

        self.lbl_saved.setText("Ayarlar kaydedildi ✓")
        QtCore.QTimer.singleShot(2500, lambda: self.lbl_saved.setText(""))

    def _reset_defaults(self):
        self.config.clear()
        self.config.update(config_mod.DEFAULT_CONFIG)
        config_mod.save_config(self.config)
        self._load_from_config()
        try:
            self.orchestrator.hotkeys.start()
        except Exception:
            pass
        self.lbl_saved.setText("Varsayılanlara dönüldü ✓")
        QtCore.QTimer.singleShot(2500, lambda: self.lbl_saved.setText(""))

    # --------------------------------------------------------- durum
    def _refresh_status(self):
        if not self.isVisible():
            return
        try:
            available = self.orchestrator.translator.ollama.is_available()
        except Exception:
            available = False
        self.lbl_ollama.setText(f"Ollama: {'Bağlı ✓' if available else 'Bağlı değil ✗'}")
        self.lbl_ollama.setStyleSheet(f"color:{'#2e9e4a' if available else '#b02a2a'};")

        mode = getattr(self.orchestrator, "mode", "none")
        mode_label = {"none": "Kapalı", "instant": "Anında (gösteriliyor)", "live": "Canlı"}.get(mode, mode)
        self.lbl_mode.setText(f"Mod: {mode_label}")

        threading.Thread(target=self._fetch_gpu_info, daemon=True).start()

    def _fetch_gpu_info(self):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader"],
                creationflags=CREATE_NO_WINDOW, timeout=3,
            ).decode("utf-8", "ignore").strip()
            name, used, total, util = [p.strip() for p in out.split(",")]
            text = f"GPU: {name} — {used}/{total} (%{util.replace('%','').strip()} kullanım)"
        except Exception:
            text = "GPU: bilgi alınamadı"
        QtCore.QMetaObject.invokeMethod(
            self.lbl_gpu, "setText", QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, text),
        )

    def _refresh_ollama_models(self):
        current = self.combo_model.currentText()
        self.combo_model.clear()
        try:
            out = subprocess.check_output(
                ["ollama", "list"], creationflags=CREATE_NO_WINDOW, timeout=5
            ).decode("utf-8", "ignore").splitlines()
            names = [line.split()[0] for line in out[1:] if line.strip()]
            self.combo_model.addItems(names)
        except Exception as exc:
            logger.warning("Ollama model listesi alinamadi: %s", exc)
        if current:
            self.combo_model.setCurrentText(current)
        elif self.combo_model.count() == 0:
            self.combo_model.addItem(self.config.get("ollama_model", "aya-expanse:8b"))

    def _run_translation_test(self):
        text = self.edit_test_input.text().strip()
        if not text:
            return
        self.lbl_test_result.setText("Çevriliyor...")

        def worker():
            try:
                result = self.orchestrator.translator.translate(text)
            except Exception as exc:
                result = f"[hata: {exc}]"
            QtCore.QMetaObject.invokeMethod(
                self.lbl_test_result, "setText", QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, result or "[çeviri alınamadı]"),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_log(self):
        if not self.isVisible():
            return
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 8000))
                data = f.read()
        except Exception:
            data = ""
        if data != self.txt_log.toPlainText():
            self.txt_log.setPlainText(data)
            self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    # --------------------------------------------------- pencere davranisi
    def closeEvent(self, event):
        event.ignore()
        self.hide()
