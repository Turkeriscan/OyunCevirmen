# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller derleme tarifi (5.1). "onedir" modunda derlenir (tek bir .exe
degil) - cunku program config.json/glossary.json/onbellek/loglari KENDI
klasorunun icine yazar; "onefile" modu her acilista gecici bir klasore
acilip kapaniste SILERDI, bu da her acilista ayarlarin sifirlanmasina
yol acardi. onedir modunda bu klasor KALICI oldugu icin (kurulum
klasorunun kendisi) ayarlar dogru sekilde kalici olur.

Derleme: installer/ klasorunden calistirin:
    pyinstaller oyuncevirmen.spec --noconfirm
Cikti: installer/dist/OyunCevirmen/ (Inno Setup betigi - setup.iss -
bu klasoru paketler).
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

PROJECT_ROOT = os.path.dirname(SPECPATH)  # installer/ -> depo koku
APP_ASSETS = os.path.join(PROJECT_ROOT, "app", "assets")
ICON_PATH = os.path.join(APP_ASSETS, "icon.ico")

# winsdk (WinRT) ve pywin32 (win32com) alt modulleri PyInstaller'in
# statik analiziyle HER ZAMAN bulunamaz (dinamik COM/WinRT yukleme) -
# bu yuzden ACIKCA toplanirlar.
hidden_imports = (
    collect_submodules("winsdk")
    + collect_submodules("winocr")
    + ["win32com", "win32com.client", "win32timezone", "pythoncom", "pywintypes"]
)

datas = [(APP_ASSETS, "app/assets")]
datas += collect_data_files("winsdk")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "app", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OyunCevirmen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # pencereli program - konsol penceresi acilmaz
    icon=ICON_PATH,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="OyunCevirmen",
)
