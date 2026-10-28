@echo off
REM Oyun Cevirmen - Guncelleme
REM GitHub'da yeni bir surum yayinladiginizda bu dosyaya cift tiklayin.
REM Python/Git/Ollama'yi tekrar kurmaz; sadece kodu gunceller ve
REM gerekiyorsa yeni kutuphaneleri kurar. Yonetici izni gerekmez.

chcp 65001 >nul
title Oyun Cevirmen - Guncelleme

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0guncelle.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Guncelleme sirasinda bir sorun olustu. Yukaridaki mesajlara bakin.
    pause
)
