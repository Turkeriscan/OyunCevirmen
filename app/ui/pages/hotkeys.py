"""Kisayollar sayfasi: tiklayip yeni tusa basarak degistirme."""
from app.ui.theme import px
from app.ui.widgets import HotkeyRecorder, Page, SettingsGroup, hotkey_text, label, section_header

ACTIONS = [
    ("hotkey_instant", "Anında tara", "Ekranı bir kez çevir; tekrar basınca çeviriler kalkar.", "f9"),
    ("hotkey_live_toggle", "Canlı mod", "Ekranı sürekli izlemeyi başlat veya durdur.", "f10"),
    ("hotkey_quit", "Programı kapat", "Oyun Çevirmen'i tamamen kapatır.", "f11"),
    ("hotkey_region_select", "Bölge çiz", "Dışında bırakılacak/sadece okunacak bölgeleri çizmek "
     "için seçim ekranını açar.", "f8"),
    ("hotkey_hold_reveal", "Orijinali göster", "Basılı tuttuğun sürece çeviri kutularını gizler; "
     "orijinal yazıyı görmek için kullan.", "f6"),
]


class HotkeysPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__("Kısayollar", "Oyun açıkken de çalışırlar. Değiştirmek için tıkla ve yeni tuşa bas; "
                                       "oyunun kendi tuşlarıyla çakışıyorsa Ctrl, Alt veya Shift ekle.")
        self.ctx = ctx
        self.recorders = {}
        g = SettingsGroup()
        for key, title, hint, default in ACTIONS:
            rec = HotkeyRecorder(default, ctx.pause_hotkeys, ctx.resume_hotkeys)
            rec.setMinimumWidth(px(260))
            rec.changed.connect(lambda _v, k=key: self._changed(k))
            self.recorders[key] = rec
            g.row(title, hint, rec, True)
        self.body.addWidget(g)
        self.warning = label("", "RowHint", wrap=True)
        self.warning.setStyleSheet("color: #F08A78;")
        self.body.addWidget(self.warning)

        self.body.addSpacing(px(10))
        self.body.addWidget(section_header(
            "İpucu", "Bazı oyunlar F tuşlarını kendisi kullanır (F5 hızlı kayıt, F12 ekran görüntüsü gibi). "
                     "Bir şey olmuyorsa önce Ctrl + F9 gibi bir birleşim dene."))
        self.finish()

    def _changed(self, key):
        self._check_conflicts()
        self.ctx.schedule_save()

    def _check_conflicts(self):
        values = {}
        for key, rec in self.recorders.items():
            values.setdefault(rec.value(), []).append(key)
        dup = [v for v, ks in values.items() if len(ks) > 1]
        self.warning.setText(
            f"{hotkey_text(dup[0])} iki işe birden atanmış; birini değiştir." if dup else "")

    def load(self, cfg):
        for key, _t, _h, default in ACTIONS:
            self.recorders[key].set_value(cfg.get(key, default))
        self._check_conflicts()

    def save(self, cfg):
        for key, rec in self.recorders.items():
            cfg[key] = rec.value()
