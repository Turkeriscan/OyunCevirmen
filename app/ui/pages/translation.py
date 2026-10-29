"""Ceviri sayfasi: yazi okuma ve ceviri motorlari, model, dil, deneme."""
import subprocess
import threading
import time

from PyQt6 import QtCore, QtWidgets

from app import config as config_mod
from app.core import ocr as ocr_mod
from app.ui.theme import px
from app.ui.widgets import (Combo, IconButton, Page, SettingsGroup, label, section_header,
                            text_button)

OCR_ENGINES = [
    ("windows", "Windows OCR", "Windows'la gelir, kurulum istemez."),
    ("easyocr", "EasyOCR (ekran kartı)", "Süslü oyun yazı tiplerinde daha isabetli."),
    ("rapidocr", "RapidOCR (hızlı, her ekran kartı)", "NVIDIA/AMD/Intel ekran kartlarında çalışır; "
                                                        "isteğe bağlı bir kurulum gerektirir."),
]
TRANSLATE_ENGINES = [
    ("ollama", "Ollama", "Bilgisayarında çalışır, internet gerekmez."),
    ("google", "Google Translate", "İnternet gerekir; Ollama yoksa yedek olarak da kullanılır."),
    ("argos", "Argos Translate (çevrimdışı)", "İnternet gerekmez; isteğe bağlı bir kurulum gerektirir "
                                               "(kurulu değilse otomatik atlanır)."),
    ("deepl", "DeepL", "İnternet ve ücretsiz bir API anahtarı gerekir (aşağıda girilir)."),
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
    recommendation = QtCore.pyqtSignal(str, str)
    download_progress = QtCore.pyqtSignal(str)
    download_done = QtCore.pyqtSignal(bool, str)


class TranslationPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("Çeviri", "Ekrandaki yazıyı neyin okuyacağını ve neyin çevireceğini seç. "
                                   "Değişiklikler anında uygulanır.")
        self.ctx = ctx
        self._recommended_model = None
        self._bridge = _Bridge()
        self._bridge.models.connect(self._fill_models)
        self._bridge.result.connect(self._show_result)
        self._bridge.recommendation.connect(self._on_recommendation)
        self._bridge.download_progress.connect(self._on_download_progress)
        self._bridge.download_done.connect(self._on_download_done)

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

        rec_box = QtWidgets.QHBoxLayout()
        rec_box.setSpacing(px(8))
        self.lbl_model_recommend = label("", "Faint", wrap=True)
        self.btn_model_download = text_button("Modeli indir")
        self.btn_model_download.clicked.connect(self.download_recommended_model)
        rec_box.addWidget(self.lbl_model_recommend, 1)
        rec_box.addWidget(self.btn_model_download)
        self.recommend_row = g.row(
            "Önerilen model", "Ekran kartının belleğine göre otomatik önerilir.", rec_box)

        self.combo_lang = Combo()
        for code, name in SOURCE_LANGS:
            self.combo_lang.addItem(name, code)
        self.lang_row = g.row("Oyunun dili", "", self.combo_lang)

        self.combo_google_perm = Combo()
        self.combo_google_perm.addItem("Sorulmadı", None)
        self.combo_google_perm.addItem("Açık", True)
        self.combo_google_perm.addItem("Kapalı", False)
        self.google_perm_row = g.row(
            "Ollama çalışmazsa Google'a gönder",
            "Ollama kapalıyken veya şüpheli bir çeviri üretirse, yedek olarak "
            "ekrandaki yazı internet üzerinden Google Translate'e gönderilir.",
            self.combo_google_perm,
        )

        self.edit_host = QtWidgets.QLineEdit()
        self.edit_host.setMinimumWidth(px(220))
        g.row("Ollama adresi", "Genelde değiştirmen gerekmez.", self.edit_host)

        self.edit_deepl_key = QtWidgets.QLineEdit()
        self.edit_deepl_key.setMinimumWidth(px(220))
        self.edit_deepl_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.deepl_row = g.row(
            "DeepL API anahtarı", "www.deepl.com/pro-api adresinden ücretsiz alınır.",
            self.edit_deepl_key,
        )
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

        self.body.addSpacing(px(12))
        self.body.addWidget(section_header(
            "Sözlük", "Karakter, yer ve eşya adları için kendi terimlerini tanımla; "
                      "motor bunları senin yazdığın gibi kullanır."))
        self._build_glossary_section()

        self.finish()

        self.combo_ocr.currentIndexChanged.connect(self._hints)
        self.combo_translate.currentIndexChanged.connect(self._hints)
        self.combo_lang.currentIndexChanged.connect(self._hints)
        for w in (self.combo_ocr, self.combo_translate, self.combo_lang):
            w.currentIndexChanged.connect(ctx.schedule_save)
        # allow_google_fallback uc durumlu (None=sorulmadi); genel kaydetme
        # akisina (save()) dahil EDILMEZ, aksi halde ilk ayar degisikliginde
        # "sorulmadi" durumu sessizce "Kapali"ya donusurdu. Degisiklik
        # dogrudan ve aninda yazilir.
        self.combo_google_perm.currentIndexChanged.connect(self._google_perm_changed)
        self.combo_model.currentIndexChanged.connect(ctx.schedule_save)
        self.combo_model.editTextChanged.connect(ctx.schedule_save)
        self.edit_host.editingFinished.connect(ctx.schedule_save)
        self.edit_deepl_key.editingFinished.connect(ctx.schedule_save)

    # ---------------------------------------------------------- ayarlar
    def load(self, cfg):
        _set(self.combo_ocr, cfg.get("ocr_engine", "windows"))
        _set(self.combo_translate, cfg.get("translate_engine", "ollama"))
        self.combo_model.setCurrentText(cfg.get("ollama_model", "aya-expanse:8b"))
        self.edit_host.setText(cfg.get("ollama_host", "http://127.0.0.1:11434"))
        self.edit_deepl_key.setText(cfg.get("deepl_api_key", ""))
        lang = cfg.get("source_lang", "auto")
        if self.combo_lang.findData(lang) < 0:
            self.combo_lang.addItem(lang, lang)
        _set(self.combo_lang, lang)
        # allow_google_fallback UC DURUMLU: None (sorulmadi/ilk ihtiyacta
        # sorar), True (acik), False (kapali). Kombo artik bu uc durumu
        # da DOGRUDAN gosterir (eskiden None gorsel olarak "Kapali" ile
        # karistirilip kullanici yanlislikla "zaten kapatmisim" sanabilirdi).
        allowed = cfg.get("allow_google_fallback")
        _set(self.combo_google_perm, allowed)
        self._hints()

    def save(self, cfg):
        cfg["ocr_engine"] = self.combo_ocr.currentData()
        cfg["translate_engine"] = self.combo_translate.currentData()
        cfg["ollama_model"] = self.combo_model.currentText().strip()
        cfg["ollama_host"] = self.edit_host.text().strip() or "http://127.0.0.1:11434"
        cfg["deepl_api_key"] = self.edit_deepl_key.text().strip()
        cfg["source_lang"] = self.combo_lang.currentData() or "auto"
        # allow_google_fallback BILEREK burada yazilmiyor; kendi ozel
        # degisim isleyicisi (_google_perm_changed) tarafindan aninda
        # yazilir, bkz. asagisi.

    def _google_perm_changed(self, *_):
        if self.ctx.is_loading():
            return
        value = self.combo_google_perm.currentData()  # None | True | False
        self.ctx.config["allow_google_fallback"] = value
        config_mod.save_config(self.ctx.config)
        if value is None:
            # Kullanici kararini bilerek geri aldi: "ilk ihtiyacta sorar"
            # durumuna donuldugu icin, bu oturumda daha once sorulmus
            # olsa bile tekrar sorulabilmesi saglanir.
            try:
                self.ctx.orchestrator.reset_google_permission_prompt()
            except Exception:
                pass
            self.ctx.flash("Google Translate izni sıfırlandı; ilk ihtiyaçta tekrar sorulacak")
        elif value:
            self.ctx.flash("Google Translate izni açıldı")
        else:
            self.ctx.flash("Google Translate izni kapatıldı")

    def _hints(self, *_):
        ocr = dict((k, h) for k, _n, h in OCR_ENGINES).get(self.combo_ocr.currentData(), "")
        tr = dict((k, h) for k, _n, h in TRANSLATE_ENGINES).get(self.combo_translate.currentData(), "")
        _set_hint(self.ocr_row, ocr)
        _set_hint(self.tr_row, tr)
        _set_hint(self.lang_row, self._lang_hint_text())
        self.model_row.setEnabled(self.combo_translate.currentData() == "ollama")
        is_google_primary = self.combo_translate.currentData() == "google"
        self.google_perm_row.setEnabled(not is_google_primary)
        _set_hint(
            self.google_perm_row,
            "Çeviri motoru olarak zaten Google Translate'i seçtin, bu ayar geçersiz."
            if is_google_primary else
            "Ollama kapalıyken veya şüpheli bir çeviri üretirse, yedek olarak "
            "ekrandaki yazı internet üzerinden Google Translate'e gönderilir.",
        )

    def _lang_hint_text(self):
        lang = self.combo_lang.currentData() or "auto"
        if lang == "auto":
            return ("Otomatik algılama pratikte Latin alfabeli dilleri (İngilizce, "
                    "Almanca, Fransızca, İspanyolca vb.) okur. Japonca, Korece, "
                    "Rusça veya Çince bir oyun için o dili doğrudan seç.")
        if self.combo_ocr.currentData() != "windows":
            return "Biliyorsan seç; otomatik algılamadan daha isabetli okur."
        if ocr_mod.is_windows_ocr_language_installed(lang):
            return "Biliyorsan seç; otomatik algılamadan daha isabetli okur."
        tag = ocr_mod.windows_ocr_tag_for(lang)
        return (f"Bu dilin Windows okuma paketi kurulu değil ({tag}). Ayarlar > Saat ve "
                f"Dil > Dil ve Bölge'den ekleyebilir, yönetici olarak "
                f"\"DISM /Online /Add-Capability /CapabilityName:Language.OCR~~~{tag}~0.0.1.0\" "
                f"komutunu çalıştırabilir, ya da yukarıdan EasyOCR'ı seçebilirsin.")

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

    # ------------------------------------------------- model onerisi/indirme
    def refresh_model_recommendation(self):
        def worker():
            from app.core import hardware
            model, vram = hardware.recommend_model_for_this_machine()
            if vram is not None:
                text = f"Ekran kartı belleğin ({vram / 1024:.1f} GB) için önerilen: {model}"
            else:
                text = f"NVIDIA ekran kartı bulunamadı; önerilen (CPU'da da çalışır): {model}"
            self._bridge.recommendation.emit(model, text)
        threading.Thread(target=worker, daemon=True).start()

    def download_recommended_model(self):
        model = self.combo_model.currentText().strip() or self._recommended_model or "aya-expanse:8b"
        self.btn_model_download.setEnabled(False)
        self.lbl_model_recommend.setText(f"İndiriliyor: {model}…")

        def worker():
            try:
                proc = subprocess.Popen(
                    ["ollama", "pull", model], creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                buf = b""
                while True:
                    chunk = proc.stdout.read(256)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\r" in buf or b"\n" in buf:
                        sep = min((i for i in (buf.find(b"\r"), buf.find(b"\n")) if i >= 0), default=-1)
                        if sep < 0:
                            break
                        line, buf = buf[:sep], buf[sep + 1:]
                        text = line.decode("utf-8", "ignore").strip()
                        if text:
                            self._bridge.download_progress.emit(text)
                code = proc.wait(timeout=600)
                if code == 0:
                    self._bridge.download_done.emit(True, model)
                else:
                    self._bridge.download_done.emit(False, f"ollama pull çıkış kodu {code}")
            except Exception as exc:
                self._bridge.download_done.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_recommendation(self, model, text):
        self._recommended_model = model
        self.lbl_model_recommend.setText(text)

    def _on_download_progress(self, text):
        self.lbl_model_recommend.setText(text[:80])

    def _on_download_done(self, ok, info):
        self.btn_model_download.setEnabled(True)
        if ok:
            self.lbl_model_recommend.setText(f"{info} indirildi.")
            self.ctx.flash(f"{info} indirildi")
            self.refresh_models()
        else:
            self.lbl_model_recommend.setText(f"İndirme başarısız: {info}")
            self.ctx.flash("Model indirilemedi; Günlük sayfasına bak")

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

    # --------------------------------------------------------------- sozluk
    def _build_glossary_section(self):
        g = SettingsGroup()
        holder = QtWidgets.QWidget()
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(px(20), px(16), px(20), px(16))
        hl.setSpacing(px(10))

        self.table_glossary = QtWidgets.QTableWidget(0, 3)
        self.table_glossary.setHorizontalHeaderLabels(["Kaynak", "Hedef", "Çevirme"])
        self.table_glossary.horizontalHeader().setStretchLastSection(False)
        self.table_glossary.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_glossary.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_glossary.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table_glossary.verticalHeader().setVisible(False)
        self.table_glossary.setMinimumHeight(px(160))
        self.table_glossary.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        hl.addWidget(self.table_glossary)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(px(8))
        self.btn_glossary_add = text_button("Satır ekle")
        self.btn_glossary_remove = text_button("Seçili satırı sil", "Danger")
        self.btn_glossary_import = text_button("İçe aktar (CSV)")
        self.btn_glossary_export = text_button("Dışa aktar (CSV)")
        for b in (self.btn_glossary_add, self.btn_glossary_remove,
                  self.btn_glossary_import, self.btn_glossary_export):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        hl.addLayout(btn_row)
        g.add(holder)
        self.body.addWidget(g)

        self.btn_glossary_add.clicked.connect(self._glossary_add_row)
        self.btn_glossary_remove.clicked.connect(self._glossary_remove_selected)
        self.btn_glossary_import.clicked.connect(self._glossary_import_csv)
        self.btn_glossary_export.clicked.connect(self._glossary_export_csv)
        self.table_glossary.itemChanged.connect(self._glossary_item_changed)

        self._glossary_loading = False
        self._reload_glossary_table()

    def _reload_glossary_table(self):
        from app.core import glossary as glossary_mod
        glossary_mod.reset_cache()
        entries = glossary_mod.load_glossary()
        self._glossary_loading = True
        try:
            self.table_glossary.setRowCount(0)
            for entry in entries:
                self._glossary_append_row(entry)
        finally:
            self._glossary_loading = False

    def _glossary_append_row(self, entry):
        row = self.table_glossary.rowCount()
        self.table_glossary.insertRow(row)
        self.table_glossary.setItem(row, 0, QtWidgets.QTableWidgetItem(entry.get("source", "")))
        self.table_glossary.setItem(row, 1, QtWidgets.QTableWidgetItem(entry.get("target", "")))
        check_item = QtWidgets.QTableWidgetItem()
        check_item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled
        )
        check_item.setCheckState(
            QtCore.Qt.CheckState.Checked if entry.get("no_translate") else QtCore.Qt.CheckState.Unchecked
        )
        self.table_glossary.setItem(row, 2, check_item)

    def _glossary_add_row(self):
        self._glossary_append_row({"source": "", "target": "", "no_translate": False})
        self.table_glossary.setCurrentCell(self.table_glossary.rowCount() - 1, 0)

    def _glossary_remove_selected(self):
        rows = sorted({i.row() for i in self.table_glossary.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.table_glossary.removeRow(row)
        self._glossary_save_from_table()

    def _glossary_item_changed(self, _item):
        if self._glossary_loading:
            return
        self._glossary_save_from_table()

    def _glossary_collect_entries(self):
        entries = []
        for row in range(self.table_glossary.rowCount()):
            source_item = self.table_glossary.item(row, 0)
            target_item = self.table_glossary.item(row, 1)
            check_item = self.table_glossary.item(row, 2)
            source = (source_item.text().strip() if source_item else "")
            if not source:
                continue
            no_translate = bool(check_item and check_item.checkState() == QtCore.Qt.CheckState.Checked)
            target = "" if no_translate else (target_item.text().strip() if target_item else "")
            entries.append({"source": source, "target": target, "no_translate": no_translate})
        return entries

    def _glossary_save_from_table(self):
        from app.core import glossary as glossary_mod
        glossary_mod.save_glossary(self._glossary_collect_entries())

    def _glossary_import_csv(self):
        path, _filt = QtWidgets.QFileDialog.getOpenFileName(
            self, "Sözlük içe aktar", "", "CSV dosyası (*.csv)")
        if not path:
            return
        import csv
        from app.core import glossary as glossary_mod
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                imported = []
                for row in reader:
                    source = (row.get("source") or row.get("Kaynak") or "").strip()
                    if not source:
                        continue
                    no_translate_raw = (row.get("no_translate") or row.get("Çevirme") or "").strip().lower()
                    no_translate = no_translate_raw in ("1", "true", "evet", "yes", "x")
                    target = (row.get("target") or row.get("Hedef") or "").strip()
                    imported.append({"source": source, "target": target, "no_translate": no_translate})
        except OSError as exc:
            self.ctx.flash(f"Sözlük içe aktarılamadı: {exc}")
            return
        existing = {e["source"].lower(): e for e in self._glossary_collect_entries()}
        for e in imported:
            existing[e["source"].lower()] = e
        glossary_mod.save_glossary(list(existing.values()))
        self._reload_glossary_table()
        self.ctx.flash(f"{len(imported)} terim içe aktarıldı")

    def _glossary_export_csv(self):
        path, _filt = QtWidgets.QFileDialog.getSaveFileName(
            self, "Sözlük dışa aktar", "sozluk.csv", "CSV dosyası (*.csv)")
        if not path:
            return
        import csv
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["source", "target", "no_translate"])
                writer.writeheader()
                for e in self._glossary_collect_entries():
                    writer.writerow({
                        "source": e["source"], "target": e["target"],
                        "no_translate": "1" if e["no_translate"] else "0",
                    })
        except OSError as exc:
            self.ctx.flash(f"Sözlük dışa aktarılamadı: {exc}")
            return
        self.ctx.flash("Sözlük CSV olarak kaydedildi")


def _set(combo, value):
    i = combo.findData(value)
    if i >= 0:
        combo.setCurrentIndex(i)


def _set_hint(row, text):
    for lbl in row.findChildren(QtWidgets.QLabel):
        if lbl.objectName() == "RowHint":
            lbl.setText(text)
            return
