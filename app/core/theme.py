"""
Kontrol paneli temasi: renkler, fontlar ve Qt stil sayfasi (QSS).

Fikir: Programin isi oyunlara "altyazi" koymak. Bu yuzden vurgu rengi
klasik film/oyun altyazisi sarisi; zemin ise gece oyun oynarken goz
yormayan koyu, hafif mavimsi bir arduvaz tonu.

Fontlar Windows 11'de hazir gelenlerdir:
    Bahnschrift      -> basliklar, tus kapaklari, buyuk sayilar
    Segoe UI Variable -> govde metni
"""
import os
import re

from PyQt6 import QtGui

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET_DIR = os.path.join(BASE_DIR, "app", "assets")

# ---------------------------------------------------------------- renkler
BG = "#181B25"          # pencere zemini
SIDEBAR = "#13161F"     # yan menu
SURFACE = "#20242F"     # kartlar
SURFACE_HI = "#282D3B"  # kart ustu alanlar, giris kutulari
LINE = "#343A4C"        # cizgiler
TEXT = "#ECEAF2"
MUTED = "#8D93A8"
FAINT = "#5D6378"
AMBER = "#F5C04A"       # altyazi sarisi
AMBER_INK = "#2A2110"   # sari ustune yazi
AMBER_SOFT = "#3A3220"
GREEN = "#63D297"
RED = "#EF6F64"

DISPLAY_FONT = "Bahnschrift"
BODY_FONTS = '"Segoe UI Variable Text", "Segoe UI", "Inter", sans-serif'


def display_font(size, weight=QtGui.QFont.Weight.DemiBold):
    f = QtGui.QFont(DISPLAY_FONT)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


# ------------------------------------------------------------ ok ikonlari
_CHEVRON_DOWN = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
    '<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
_CHEVRON_UP = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
    '<path d="M2.5 7.5 6 4l3.5 3.5" fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def _ensure_icons():
    os.makedirs(ASSET_DIR, exist_ok=True)
    paths = {}
    for name, tpl in (("chevron_down", _CHEVRON_DOWN), ("chevron_up", _CHEVRON_UP)):
        path = os.path.join(ASSET_DIR, f"{name}.svg")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(tpl.format(c=MUTED))
        except OSError:
            pass
        paths[name] = path.replace("\\", "/")
    return paths


def _scope(qss, root="#MainWindow"):
    """Her kurali '#MainWindow ...' altina alir. Boylece genel govde kurali
    ('#MainWindow QWidget') ozel kurallari (#PageTitle gibi) ezmez: Qt'de
    secici onceligi kimlik (#) sayisina gore belirlenir."""
    qss = re.sub(r"/\*.*?\*/", "", qss, flags=re.S)
    out = []
    for block in qss.split("}"):
        if "{" not in block:
            out.append(block)
            continue
        head, body = block.split("{", 1)
        selectors = []
        for sel in head.split(","):
            sel = sel.strip()
            if not sel or sel.startswith(root) or sel.startswith("QToolTip"):
                selectors.append(sel)
            else:
                selectors.append(f"{root} {sel}")
        out.append(",\n".join(selectors) + " {" + body)
    return "}".join(out)


def stylesheet():
    icons = _ensure_icons()
    down, up = icons["chevron_down"], icons["chevron_up"]
    return _scope(f"""
#MainWindow {{
    background: {BG};
}}
#MainWindow, #MainWindow QWidget {{
    font-family: {BODY_FONTS};
    font-size: 10pt;
    color: {TEXT};
}}
QToolTip {{
    background: {SURFACE_HI}; color: {TEXT}; border: 1px solid {LINE}; padding: 6px;
}}
QDialog {{ background: {BG}; }}

/* ---------- yan menu ---------- */
#Sidebar {{
    background: {SIDEBAR};
    border-right: 1px solid {LINE};
}}
#BrandName {{
    font-family: "{DISPLAY_FONT}"; font-size: 13pt; font-weight: 600; color: {TEXT};
}}
#BrandSub {{ color: {FAINT}; font-size: 9pt; }}
#NavButton {{
    text-align: left;
    padding: 10px 14px 10px 16px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    background: transparent;
    color: {MUTED};
    font-size: 10.5pt;
}}
#NavButton:hover {{ color: {TEXT}; background: {BG}; }}
#NavButton:checked {{
    color: {TEXT};
    background: {SURFACE};
    border-left: 3px solid {AMBER};
    font-weight: 600;
}}
#SavedLabel {{ color: {GREEN}; font-size: 9pt; }}

/* ---------- sayfa basliklari ---------- */
#PageTitle {{
    font-family: "{DISPLAY_FONT}"; font-size: 20pt; font-weight: 600; color: {TEXT};
}}
#PageLead {{ color: {MUTED}; font-size: 10pt; }}
#SectionTitle {{
    font-family: "{DISPLAY_FONT}"; font-size: 12pt; font-weight: 600; color: {TEXT};
}}
#Hint {{ color: {FAINT}; font-size: 9pt; }}
#Muted {{ color: {MUTED}; }}

/* ---------- kartlar ---------- */
#Card {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
#ModeCard {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 14px;
}}
#ModeCard:hover {{ border: 1px solid {FAINT}; }}
#ModeCard[active="true"] {{
    background: {AMBER_SOFT};
    border: 1px solid {AMBER};
}}
#ModeTitle {{
    font-family: "{DISPLAY_FONT}"; font-size: 16pt; font-weight: 600;
}}
#ModeState {{
    color: {MUTED}; font-size: 9pt; font-weight: 600;
    padding: 3px 9px; border-radius: 9px; background: {SURFACE_HI};
}}
#ModeState[active="true"] {{ color: {AMBER_INK}; background: {AMBER}; }}

#Keycap {{
    font-family: "{DISPLAY_FONT}"; font-size: 11pt; font-weight: 600;
    color: {TEXT};
    background: {SURFACE_HI};
    border: 1px solid {LINE};
    border-bottom: 3px solid {LINE};
    border-radius: 6px;
    padding: 3px 10px;
}}
#KeycapLarge {{
    font-family: "{DISPLAY_FONT}"; font-size: 14pt; font-weight: 600;
    color: {TEXT};
    background: {SURFACE_HI};
    border: 1px solid {LINE};
    border-bottom: 4px solid {LINE};
    border-radius: 8px;
    padding: 6px 16px;
}}

/* ---------- durum ---------- */
#StatLabel {{ color: {MUTED}; font-size: 9pt; }}
#StatValue {{
    font-family: "{DISPLAY_FONT}"; font-size: 12.5pt; font-weight: 600; color: {TEXT};
}}
#StatDetail {{ color: {FAINT}; font-size: 9pt; }}
#Dot {{ border-radius: 4px; background: {FAINT}; }}
#Dot[state="ok"] {{ background: {GREEN}; }}
#Dot[state="bad"] {{ background: {RED}; }}
#Dot[state="live"] {{ background: {AMBER}; }}

QProgressBar#Meter {{
    background: {SURFACE_HI}; border: none; border-radius: 3px; max-height: 6px;
}}
QProgressBar#Meter::chunk {{ background: {AMBER}; border-radius: 3px; }}

/* ---------- son ceviriler ---------- */
#FeedRow {{ border-bottom: 1px solid {LINE}; }}
#FeedOriginal {{ color: {MUTED}; font-size: 9pt; }}
#FeedTranslated {{ color: {TEXT}; font-size: 10.5pt; }}
#FeedTime {{ color: {FAINT}; font-size: 8.5pt; }}
#EmptyState {{ color: {MUTED}; padding: 24px; }}

/* ---------- butonlar ---------- */
QPushButton {{
    background: {SURFACE_HI};
    border: 1px solid {LINE};
    border-radius: 7px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ border-color: {FAINT}; }}
QPushButton:pressed {{ background: {LINE}; }}
QPushButton:focus {{ border-color: {AMBER}; }}
QPushButton#Primary {{
    background: {AMBER}; color: {AMBER_INK}; border: 1px solid {AMBER}; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: #FFD06A; }}
QPushButton#Danger {{ background: transparent; color: {RED}; border: 1px solid #5A3433; }}
QPushButton#Danger:hover {{ background: #2E2023; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#Ghost:hover {{ color: {TEXT}; border-color: {LINE}; }}
QPushButton#Chip {{
    padding: 5px 12px; border-radius: 14px; color: {MUTED}; background: transparent;
}}
QPushButton#Chip:checked {{ color: {AMBER_INK}; background: {AMBER}; border-color: {AMBER}; font-weight: 600; }}
QPushButton#Preset {{ padding: 6px 12px; border-radius: 7px; }}

/* ---------- giris alanlari ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE_HI};
    border: 1px solid {LINE};
    border-radius: 7px;
    padding: 6px 10px;
    min-height: 20px;
    selection-background-color: {AMBER};
    selection-color: {AMBER_INK};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {AMBER};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_HI}; border: 1px solid {LINE}; outline: none;
    selection-background-color: {AMBER_SOFT}; selection-color: {TEXT}; padding: 4px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none; width: 20px; background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}

QSlider::groove:horizontal {{ height: 6px; background: {SURFACE_HI}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {AMBER}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
}}

QPlainTextEdit#LogView {{
    background: {SIDEBAR}; border: 1px solid {LINE}; border-radius: 10px;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 9pt; color: #B9BED0;
    padding: 8px;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
""")
