@echo off
REM Oyun Cevirmen baslatma betigi.
REM Bu dosyayi cift tiklayarak (veya masaustu kisayolundan) programi baslatabilirsiniz.

chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "C:\OyunCevirmen"

REM Ollama servisi calismiyorsa, program kendi icinde otomatik baslatmaya calisir.
REM Burada da bir kez deneyelim ki ilk acilista model yuklenmeye baslasin.
where ollama >nul 2>nul
if %ERRORLEVEL%==0 (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >nul
    if not %ERRORLEVEL%==0 (
        start "" /min ollama serve
    )
)

"C:\OyunCevirmen\venv\Scripts\pythonw.exe" -m app.main

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Program bir hata ile kapandi. Ayrinti icin logs\oyuncevirmen.log dosyasina bakin.
    "C:\OyunCevirmen\venv\Scripts\python.exe" -m app.main
    pause
)
