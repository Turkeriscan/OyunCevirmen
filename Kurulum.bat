@echo off
REM Oyun Cevirmen - Sifirdan Kurulum
REM Bu dosyaya cift tiklamaniz yeterli. Gerekli her seyi (Python, Git,
REM Ollama, ceviri modeli, kutuphaneler) otomatik kurar ve programi
REM kullanima hazir hale getirir. Yonetici izni isteyecektir, kabul edin.

chcp 65001 >nul
title Oyun Cevirmen - Kurulum

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kurulum.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Kurulum sirasinda bir sorun olustu. Yukaridaki mesajlara bakin.
    pause
)
