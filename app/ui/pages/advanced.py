"""Gelismis sayfasi: canli mod, filtreler, ekran secimi, hafiza, sifirlama."""
from PyQt6 import QtWidgets

from app.core import capture as capture_mod
from app.ui.theme import px
from app.ui.widgets import (Combo, IconButton, Page, SettingsGroup, Stepper, ValueSlider, label,
                            section_header, text_button)


class AdvancedPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("Gelişmiş", "Varsayılanlar çoğu oyunda iyi çalışır. "
                                     "Oyun takılıyorsa tarama aralığını artır.")
        self.ctx = ctx

        self.body.addWidget(section_header("Canlı mod"))
        g = SettingsGroup()
        self.sl_interval = ValueSlider(0.1, 2.0, 0.05, "{:.2f} sn")
        self.sl_interval.setMinimumWidth(px(240))
        g.row("Tarama aralığı", "Kısaldıkça yazıları daha çabuk yakalar, ekran kartını daha çok çalıştırır.",
              self.sl_interval, True)
        grid = QtWidgets.QHBoxLayout()
        grid.setSpacing(px(8))
        self.st_cols = Stepper(1, 20, 1, "sütun")
        self.st_rows = Stepper(1, 20, 1, "satır")
        grid.addWidget(self.st_cols)
        grid.addWidget(label("×", "Faint"))
        grid.addWidget(self.st_rows)
        g.row("Ekran bölmesi", "Ekran bu kadar parçaya bölünür; sadece değişen parçalar yeniden okunur.", grid)
        self.st_padding = Stepper(0, 300, 10, "px")
        g.row("Parça kenar payı", "Kelimeler parça sınırında bölünüyorsa artır.", self.st_padding)
        self.st_typewriter = Stepper(0, 2000, 50, "ms")
        g.row("Harf harf beliren yazı bekleme süresi",
              "Diyalog harf harf beliren oyunlarda, yazı bu kadar süre değişmeden "
              "kalana kadar çevirmeyi geciktirir. 0 = kapalı.",
              self.st_typewriter)
        self.body.addWidget(g)

        self.body.addSpacing(px(10))
        self.body.addWidget(section_header("Neyi çevirmesin"))
        g2 = SettingsGroup()
        self.st_minlen = Stepper(1, 20, 1, "harf")
        g2.row("En kısa metin", "Bundan kısa yazılar (HP, x3 gibi) atlanır.", self.st_minlen)
        self.sl_conf = ValueSlider(0.0, 1.0, 0.05, "{:.2f}")
        self.sl_conf.setMinimumWidth(px(240))
        g2.row("Okuma güveni eşiği", "Yükseltirsen bulanık okunan yazılar elenir; çok yükseltirsen "
                                     "gerçek yazılar da kaçabilir.", self.sl_conf, True)
        self.combo_upscale = Combo()
        self.combo_upscale.addItem("Açık", True)
        self.combo_upscale.addItem("Kapalı", False)
        g2.row("Küçük yazıları büyüterek oku", "Okumadan önce görüntüyü 2 kat büyütür; "
               "küçük fontlu yazılarda isabeti artırır, çok büyük taramaları yavaşlatmaz.",
               self.combo_upscale)
        self.body.addWidget(g2)

        self.body.addSpacing(px(10))
        self.body.addWidget(section_header("Ekran ve hafıza"))
        g3 = SettingsGroup()
        mon = QtWidgets.QHBoxLayout()
        mon.setSpacing(px(6))
        self.combo_monitor = Combo()
        self.combo_monitor.setMinimumContentsLength(22)
        self.btn_monitors = IconButton("refresh", "Ekranları yeniden listele", 16)
        self.btn_monitors.clicked.connect(lambda: self.refresh_monitors())
        mon.addWidget(self.combo_monitor, 1)
        mon.addWidget(self.btn_monitors)
        g3.row("İzlenecek ekran", "Oyunun açık olduğu ekran. Değişiklik anında uygulanır.", mon, True)
        self.st_cache = Stepper(500, 50000, 500, "satır")
        g3.row("Bellekte tutulacak çeviri", "Hepsi ayrıca diske kaydedilir; program kapanınca kaybolmaz.",
               self.st_cache)
        cache = QtWidgets.QHBoxLayout()
        self.lbl_cache = label("", "ValueLabel")
        self.btn_clear = text_button("Hafızayı sil", "Danger")
        self.btn_clear.clicked.connect(ctx.clear_cache)
        cache.addWidget(self.lbl_cache)
        cache.addSpacing(px(10))
        cache.addWidget(self.btn_clear)
        g3.row("Çeviri hafızası", "Model değiştirdiysen eski çeviriler yerine yenilerini görmek için.", cache)
        self.body.addWidget(g3)

        self.body.addSpacing(px(10))
        self.body.addWidget(section_header("Başa dön"))
        g4 = SettingsGroup()
        b1 = text_button("Rehberi aç")
        b1.clicked.connect(ctx.show_onboarding)
        g4.row("Karşılama rehberi", "İlk açılıştaki adım adım kurulum ve sistem kontrolü.", b1)
        b2 = text_button("Varsayılana döndür", "Danger")
        b2.clicked.connect(ctx.reset_defaults)
        g4.row("Tüm ayarlar", "Her şey ilk kurulumdaki haline döner. Çeviri hafızası silinmez.", b2)
        self.body.addWidget(g4)
        self.finish()

        self.sl_interval.valueChanged.connect(ctx.schedule_save)
        self.sl_conf.valueChanged.connect(ctx.schedule_save)
        for s in (self.st_cols, self.st_rows, self.st_padding, self.st_minlen, self.st_cache,
                  self.st_typewriter):
            s.valueChanged.connect(ctx.schedule_save)
        self.combo_upscale.currentIndexChanged.connect(ctx.schedule_save)
        self.combo_monitor.currentIndexChanged.connect(self._monitor_changed)

    # --------------------------------------------------------- ekranlar
    def refresh_monitors(self, select_index=None):
        if select_index is None:
            select_index = self.combo_monitor.currentData()
        self.combo_monitor.blockSignals(True)
        self.combo_monitor.clear()
        for m in capture_mod.list_monitors():
            self.combo_monitor.addItem(m["label"], m["index"])
        i = self.combo_monitor.findData(select_index)
        self.combo_monitor.setCurrentIndex(i if i >= 0 else 0)
        self.combo_monitor.blockSignals(False)

    def _monitor_changed(self, *_):
        if self.ctx.is_loading():
            return
        index = self.combo_monitor.currentData()
        if index is None:
            return
        ok = self.ctx.orchestrator.change_monitor(index)
        self.ctx.flash("İzlenecek ekran değiştirildi" if ok else "Ekran değiştirilemedi; Günlük'e bak")
        self.ctx.refresh_status()

    def set_cache_count(self, n):
        self.lbl_cache.setText("?" if n is None else f"{n:,} çeviri".replace(",", "."))
        self.btn_clear.setEnabled(bool(n))

    # ---------------------------------------------------------- ayarlar
    def load(self, cfg):
        self.sl_interval.setValue(cfg.get("live_scan_interval", 0.45))
        self.st_cols.setValue(cfg.get("live_grid_cols", 6), emit=False)
        self.st_rows.setValue(cfg.get("live_grid_rows", 4), emit=False)
        self.st_padding.setValue(cfg.get("live_cell_padding", 220), emit=False)
        self.st_typewriter.setValue(cfg.get("live_typewriter_debounce_ms", 400), emit=False)
        self.st_minlen.setValue(cfg.get("min_text_length", 2), emit=False)
        self.sl_conf.setValue(cfg.get("min_ocr_confidence", 0.45))
        self.st_cache.setValue(cfg.get("max_cache_memory_items", 5000), emit=False)
        i = self.combo_upscale.findData(bool(cfg.get("ocr_upscale_small_text", True)))
        self.combo_upscale.setCurrentIndex(i if i >= 0 else 0)
        self.refresh_monitors(select_index=cfg.get("capture_monitor_index", 0))

    def save(self, cfg):
        cfg["live_scan_interval"] = round(self.sl_interval.value(), 2)
        cfg["live_grid_cols"] = self.st_cols.value()
        cfg["live_grid_rows"] = self.st_rows.value()
        cfg["live_cell_padding"] = self.st_padding.value()
        cfg["live_typewriter_debounce_ms"] = self.st_typewriter.value()
        cfg["min_text_length"] = self.st_minlen.value()
        cfg["min_ocr_confidence"] = round(self.sl_conf.value(), 2)
        cfg["max_cache_memory_items"] = self.st_cache.value()
        cfg["ocr_upscale_small_text"] = bool(self.combo_upscale.currentData())
        # capture_monitor_index: _monitor_changed -> orchestrator.change_monitor yonetir
