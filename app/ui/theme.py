"""
Tasarim sistemi: "Sinema altyazisi".

Program oyunlara altyazi koyuyor; arayuz de bir sinema perdesi gibi
dusunuldu. Pencerenin ustu ve alti sinema seridi (letterbox) gibi siyah
bantlardir, icerik "sahne" uzerinde durur, vurgu rengi klasik altyazi
sarisidir. Canli mod, cekim setlerindeki "kayitta" lambasi gibi kirmizi yanar.

Yazi tipleri (app/assets/fonts, SIL Open Font License):
    Newsreader Display  -> sayfa basliklari, buyuk altyazi perdesindeki orijinal satir
    IBM Plex Sans       -> arayuz metni, altyazilarin kendisi
    IBM Plex Mono       -> sadece zaman kodlari ve altyazi numaralari (SRT gibi)

Olcek: Qt'nin yuksek DPI olceklemesi programda kapali (overlay piksel
hassasiyeti icin). Bu yuzden piksel olculeri px() ile ekran DPI'sina gore
buyutulur; nokta (pt) cinsinden yazi boyutlarini Windows zaten olcekler.
"""
import os
import re

from PyQt6 import QtGui, QtWidgets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET_DIR = os.path.join(BASE_DIR, "app", "assets")
FONT_DIR = os.path.join(ASSET_DIR, "fonts")

# ------------------------------------------------------------------ renkler
LETTERBOX = "#0C0A08"    # ust/alt sinema bantlari
CURTAIN = "#14110E"      # yan menu
STAGE = "#1B1714"        # icerik zemini
SURFACE = "#231E1A"      # paneller
RAISED = "#2D2722"       # giris alanlari, butonlar
RAISED_HI = "#373029"    # uzerine gelince
LINE = "#3A332C"         # ayirici cizgiler
LINE_SOFT = "#2A2420"

PAPER = "#F1EADB"        # ana metin: perde beyazi
MUTED = "#AE9F8D"        # ikincil metin
FAINT = "#857868"        # ipuclari, etiketler

SUB = "#F2C14E"          # altyazi sarisi
SUB_HI = "#FFD675"
SUB_INK = "#211906"      # sari ustune yazi
SUB_WASH = "#372D16"     # sari tonlu zemin
REC = "#E5533C"          # canli mod / "kayitta" lambasi
REC_WASH = "#3A1F19"
OK = "#86C79A"
OK_WASH = "#1F2E23"

# ----------------------------------------------------------------- olcek
_scale = 1.0


def init_scale(app=None):
    """QApplication olustuktan sonra bir kez cagrilir."""
    global _scale
    try:
        screen = QtWidgets.QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        _scale = max(1.0, min(2.5, dpi / 96.0))
    except Exception:
        _scale = 1.0
    return _scale


def px(value):
    return int(round(value * _scale))


def pxf(value):
    return value * _scale


# ------------------------------------------------------------- yazi tipleri
# rol -> (dosya, agirlik, italik)
_FONT_FILES = {
    "display": ("Newsreader-Display-Regular.ttf", 400, False),
    "display_medium": ("Newsreader-Display-Medium.ttf", 500, False),
    "display_italic": ("Newsreader-Display-Italic.ttf", 400, True),
    "text_serif": ("Newsreader-Text-Regular.ttf", 400, False),
    "body": ("IBMPlexSans-Regular.ttf", 400, False),
    "body_medium": ("IBMPlexSans-Medium.ttf", 500, False),
    "body_semibold": ("IBMPlexSans-SemiBold.ttf", 600, False),
    "condensed": ("IBMPlexSansCondensed-SemiBold.ttf", 600, False),
    "mono": ("IBMPlexMono-Regular.ttf", 400, False),
    "mono_medium": ("IBMPlexMono-Medium.ttf", 500, False),
}
_FALLBACK = {
    "display": "Georgia", "display_medium": "Georgia", "display_italic": "Georgia",
    "text_serif": "Georgia", "body": "Segoe UI", "body_medium": "Segoe UI",
    "body_semibold": "Segoe UI", "condensed": "Bahnschrift", "mono": "Consolas",
    "mono_medium": "Consolas",
}
_families = {}
_loaded = False


def load_fonts():
    """Paketlenmis yazi tiplerini Qt'ye tanitir. Windows'ta bazi yazi
    tipleri her agirlik icin ayri aile adiyla kaydolur ("IBM Plex Sans Medm"
    gibi); bu yuzden her rol icin Qt'nin gercekten kaydettigi adi saklariz."""
    global _loaded
    if _loaded:
        return _families
    for role, (filename, _w, _i) in _FONT_FILES.items():
        path = os.path.join(FONT_DIR, filename)
        fam = None
        if os.path.exists(path):
            fid = QtGui.QFontDatabase.addApplicationFont(path)
            if fid >= 0:
                names = QtGui.QFontDatabase.applicationFontFamilies(fid)
                if names:
                    fam = names[0]
        _families[role] = fam or _FALLBACK[role]
    _loaded = True
    return _families


def family(role):
    if not _loaded:
        load_fonts()
    return _families.get(role, _FALLBACK.get(role, "Segoe UI"))


def font(role="body", size=10.0):
    """Rol + nokta boyutuyla QFont uretir."""
    _f, weight, italic = _FONT_FILES.get(role, ("", 400, False))
    f = QtGui.QFont(family(role))
    f.setPointSizeF(size)
    f.setWeight(QtGui.QFont.Weight(weight))
    f.setItalic(italic)
    f.setHintingPreference(QtGui.QFont.HintingPreference.PreferVerticalHinting)
    f.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    return f


def _css_font(role, size):
    _f, weight, italic = _FONT_FILES[role]
    style = "italic" if italic else "normal"
    return f'font-family: "{family(role)}"; font-size: {size}pt; font-weight: {weight}; font-style: {style};'


# ------------------------------------------------------------ hareket
def reduced_motion():
    """Windows'ta 'Animasyon efektleri' kapaliysa animasyon yapmayiz."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        value = ctypes.c_int(1)
        SPI_GETCLIENTAREAANIMATION = 0x1042
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0
        )
        return value.value == 0
    except Exception:
        return False


# ------------------------------------------------------------ stil sayfasi
def _scope(qss, root="#MainWindow"):
    """Tum kurallari pencere kimligi altina alir: Qt'de secici onceligi
    kimlik (#) sayisina gore oldugundan genel kurallar ozelleri ezmez."""
    qss = re.sub(r"/\*.*?\*/", "", qss, flags=re.S)
    out = []
    for block in qss.split("}"):
        if "{" not in block:
            out.append(block)
            continue
        head, body = block.split("{", 1)
        sels = []
        for sel in head.split(","):
            sel = sel.strip()
            if not sel or sel.startswith(root) or sel.startswith("QToolTip"):
                sels.append(sel)
            else:
                sels.append(f"{root} {sel}")
        out.append(",\n".join(sels) + " {" + body)
    return "}".join(out)


def stylesheet(root="#MainWindow"):
    r = px
    q = f"""
{root} {{ background: {STAGE}; }}
{root}, {root} QWidget {{
    {_css_font("body", 10)}
    color: {PAPER};
}}
QToolTip {{
    background: {LETTERBOX}; color: {PAPER}; border: 1px solid {LINE};
    padding: {r(6)}px {r(8)}px; {_css_font("body", 9)}
}}
QDialog, QMessageBox {{ background: {STAGE}; }}

/* ------------------------------------------------ cerceve */
#TitleBar, #CreditsBar {{ background: {LETTERBOX}; }}
#TitleBar {{ border-bottom: 1px solid {LINE_SOFT}; }}
#CreditsBar {{ border-top: 1px solid {LINE_SOFT}; }}
#AppName {{ {_css_font("display_medium", 13)} color: {PAPER}; }}
#TitleState {{ {_css_font("body_medium", 9.5)} color: {MUTED}; }}
#TitleTimer {{ {_css_font("mono", 9.5)} color: {MUTED}; }}
#CreditLabel {{ {_css_font("body", 8.5)} color: {FAINT}; }}
#CreditValue {{ {_css_font("body_medium", 9)} color: {MUTED}; }}
#CreditSep {{ background: {LINE}; }}

#WinButton {{
    background: transparent; border: none; border-radius: 0;
    min-width: {r(46)}px; max-width: {r(46)}px;
}}
#WinButton:hover {{ background: {RAISED}; }}
#WinButton:pressed {{ background: {RAISED_HI}; }}
#WinButton[role="close"]:hover {{ background: #C42B1C; }}
#WinButton[role="close"]:pressed {{ background: #A72518; }}

/* ------------------------------------------------ yan menu */
#Rail {{ background: {CURTAIN}; border-right: 1px solid {LINE_SOFT}; }}
#RailButton {{
    text-align: left; border: none; border-radius: {r(8)}px;
    padding: {r(9)}px {r(12)}px; margin: 0 {r(10)}px;
    background: transparent; color: {MUTED};
    {_css_font("body_medium", 10)}
}}
#RailButton:hover {{ background: {SURFACE}; color: {PAPER}; }}
#RailButton:checked {{ background: {SURFACE}; color: {PAPER}; }}
#RailButton:focus {{ outline: none; }}
#RailFootnote {{ {_css_font("body", 8.5)} color: {FAINT}; }}

/* ------------------------------------------------ sayfa tipografisi */
#PageTitle {{ {_css_font("display", 25)} color: {PAPER}; }}
#PageLead {{ {_css_font("body", 10)} color: {MUTED}; }}
#SectionTitle {{ {_css_font("display_medium", 15)} color: {PAPER}; }}
#SectionLead {{ {_css_font("body", 9.5)} color: {MUTED}; }}
#RowTitle {{ {_css_font("body_medium", 10)} color: {PAPER}; }}
#RowHint {{ {_css_font("body", 9)} color: {FAINT}; }}
#Muted {{ color: {MUTED}; }}
#Faint {{ color: {FAINT}; {_css_font("body", 9)} }}
#ValueLabel {{ {_css_font("mono", 9.5)} color: {MUTED}; }}
#Separator {{ background: {LINE_SOFT}; }}

/* ------------------------------------------------ akis (sahne sayfasi) */
#Transcript {{ background: {CURTAIN}; border-left: 1px solid {LINE_SOFT}; }}
#CueMeta {{ {_css_font("mono", 8)} color: {FAINT}; }}
#CueText {{ {_css_font("body", 10.5)} color: {PAPER}; }}
#CueOriginal {{ {_css_font("text_serif", 10)} font-style: italic; color: {MUTED}; }}
#CueSep {{ background: {LINE_SOFT}; }}

/* ------------------------------------------------ ceviri denemesi */
#TrialStrip {{ background: {LETTERBOX}; border: 1px solid {LINE_SOFT}; border-radius: {r(10)}px; }}
#TrialText {{ {_css_font("body_semibold", 14)} color: {PAPER}; }}
#TrialOriginal {{ {_css_font("text_serif", 10.5)} font-style: italic; color: {MUTED}; }}
#TrialMeta {{ {_css_font("mono", 8.5)} color: {FAINT}; }}

/* ------------------------------------------------ rehber */
#OnbTitle {{ {_css_font("display", 30)} color: {PAPER}; }}
#OnbLead {{ {_css_font("body", 11)} color: {MUTED}; }}
#OnbStep {{ {_css_font("body_medium", 9)} color: {FAINT}; }}
#OnbStepActive {{ {_css_font("body_semibold", 9)} color: {PAPER}; }}
#CheckTitle {{ {_css_font("body_medium", 10.5)} color: {PAPER}; }}
#CheckHint {{ {_css_font("body", 9)} color: {MUTED}; }}

/* ------------------------------------------------ butonlar */
QPushButton {{
    background: {RAISED}; color: {PAPER};
    border: 1px solid {LINE}; border-radius: {r(7)}px;
    padding: {r(7)}px {r(14)}px; {_css_font("body_medium", 9.5)}
}}
QPushButton:hover {{ background: {RAISED_HI}; }}
QPushButton:pressed {{ background: {LINE}; }}
QPushButton:focus {{ border-color: {SUB}; }}
QPushButton:disabled {{ color: {FAINT}; background: {SURFACE}; }}
QPushButton#Primary {{
    background: {SUB}; color: {SUB_INK}; border: 1px solid {SUB};
    {_css_font("body_semibold", 9.5)}
}}
QPushButton#Primary:hover {{ background: {SUB_HI}; border-color: {SUB_HI}; }}
QPushButton#Primary:focus {{ border: 1px solid {PAPER}; }}
QPushButton#Quiet {{ background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#Quiet:hover {{ background: {RAISED}; color: {PAPER}; }}
QPushButton#Danger {{ background: transparent; color: #F08A78; border: 1px solid #5A2E26; }}
QPushButton#Danger:hover {{ background: {REC_WASH}; }}
QPushButton#IconButton {{
    background: transparent; border: 1px solid transparent; border-radius: {r(6)}px; padding: {r(5)}px;
}}
QPushButton#IconButton:hover {{ background: {RAISED}; }}
QPushButton#IconButton:checked {{ background: {SUB_WASH}; }}
QPushButton#Swatch {{ padding: {r(5)}px {r(10)}px {r(5)}px {r(7)}px; {_css_font("mono", 9)} }}

/* ------------------------------------------------ giris alanlari */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {RAISED}; color: {PAPER};
    border: 1px solid {LINE}; border-radius: {r(7)}px;
    padding: {r(6)}px {r(10)}px; min-height: {r(20)}px;
    selection-background-color: {SUB}; selection-color: {SUB_INK};
}}
QLineEdit:hover, QComboBox:hover {{ border-color: #4A4138; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {SUB}; }}
QComboBox {{ padding-right: {r(30)}px; }}
QComboBox::drop-down {{ border: none; width: {r(28)}px; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {LINE}; outline: none;
    padding: {r(4)}px; selection-background-color: {RAISED_HI}; selection-color: {PAPER};
}}
QComboBox QAbstractItemView::item {{ min-height: {r(28)}px; padding: 0 {r(8)}px; border-radius: {r(5)}px; }}

QSlider {{ min-height: {r(22)}px; }}
QSlider::groove:horizontal {{ height: {r(4)}px; background: {RAISED_HI}; border-radius: {r(2)}px; }}
QSlider::sub-page:horizontal {{ background: {SUB}; border-radius: {r(2)}px; }}
QSlider::handle:horizontal {{
    background: {PAPER}; width: {r(16)}px; height: {r(16)}px;
    margin: -{r(6)}px 0; border-radius: {r(8)}px; border: {r(3)}px solid {STAGE};
}}
QSlider::handle:horizontal:hover {{ background: #FFFFFF; }}
QSlider:focus {{ outline: none; }}

QPlainTextEdit#LogView {{
    background: {LETTERBOX}; border: 1px solid {LINE_SOFT}; border-radius: {r(10)}px;
    {_css_font("mono", 9)} color: #BDB2A3; padding: {r(10)}px;
    selection-background-color: {SUB_WASH}; selection-color: {PAPER};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {r(10)}px; margin: {r(2)}px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: {r(3)}px; min-height: {r(36)}px; }}
QScrollBar::handle:vertical:hover {{ background: #4D443A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: {r(10)}px; margin: {r(2)}px; }}
QScrollBar::handle:horizontal {{ background: {LINE}; border-radius: {r(3)}px; min-width: {r(36)}px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QMenu {{
    background: {SURFACE}; border: 1px solid {LINE}; padding: {r(4)}px;
}}
QMenu::item {{ padding: {r(6)}px {r(18)}px; border-radius: {r(5)}px; }}
QMenu::item:selected {{ background: {RAISED_HI}; }}

/* ------------------------------------------------ tablo (sozluk vb.) */
QTableWidget {{
    background: {RAISED}; color: {PAPER}; border: 1px solid {LINE};
    border-radius: {r(8)}px; gridline-color: {LINE_SOFT};
    selection-background-color: {SUB_WASH}; selection-color: {PAPER};
    {_css_font("body", 9.5)}
}}
QTableWidget::item {{ padding: {r(4)}px {r(6)}px; }}
QHeaderView::section {{
    background: {SURFACE}; color: {MUTED}; border: none;
    border-bottom: 1px solid {LINE}; padding: {r(6)}px {r(8)}px;
    {_css_font("body_medium", 9)}
}}
QTableWidget QLineEdit {{ background: {RAISED_HI}; border: 1px solid {SUB}; }}
"""
    return _scope(q, root)


def app_stylesheet():
    """Uygulama geneli: ipuclari ve sag tik menuleri (bunlar ayri ust duzey
    pencereler oldugu icin ana pencerenin stilini almazlar)."""
    r = px
    return f"""
QToolTip {{
    background: {LETTERBOX}; color: {PAPER}; border: 1px solid {LINE};
    padding: {r(6)}px {r(8)}px; {_css_font("body", 9)}
}}
QMenu {{
    background: {SURFACE}; color: {PAPER}; border: 1px solid {LINE}; padding: {r(4)}px;
    {_css_font("body", 9.5)}
}}
QMenu::item {{ padding: {r(6)}px {r(18)}px; border-radius: {r(5)}px; }}
QMenu::item:selected {{ background: {RAISED_HI}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: {r(4)}px {r(6)}px; }}
"""
