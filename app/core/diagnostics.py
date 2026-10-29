"""
Sorun bildirimi paketi (4.5): kullanicinin bir hata/sorunu bildirirken
gonderebilecegi tek bir .zip dosyasi olusturur - son loglar, ic yuzu
gizlenmis (redacted) config.json, ve sistem bilgisi (Windows surumu, GPU,
monitor duzeni, kurulu OCR dilleri, Ollama modelleri). Istege bagli
olarak bir ekran goruntusu de eklenebilir.

Hicbir adim diger adimlari ENGELLEMEZ: herhangi biri basarisiz olursa
(orn. nvidia-smi yok, Ollama kapali) o bolum "alinamadi" olarak
isaretlenir, paket yine de olusturulur.
"""
import json
import logging
import os
import platform
import subprocess
import time
import zipfile

from app.core import capture as capture_mod
from app.core import hardware as hardware_mod
from app.core import ocr as ocr_mod

logger = logging.getLogger("OyunCevirmen.diagnostics")

CREATE_NO_WINDOW = 0x08000000
REDACTED_CONFIG_KEYS = ("deepl_api_key",)
MAX_LOG_BYTES = 2_000_000  # log cok buyukse SADECE SON kismi eklenir


def redact_config(config):
    """config.json'un bir kopyasini, gizli/kisisel sayilabilecek alanlari
    (orn. API anahtari) maskeleyerek dondurur."""
    redacted = dict(config)
    for key in REDACTED_CONFIG_KEYS:
        if redacted.get(key):
            redacted[key] = "***gizlendi***"
    return redacted


def _detect_gpu_name():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            creationflags=CREATE_NO_WINDOW, timeout=5,
        ).decode("utf-8", "ignore").strip()
        return out.splitlines()[0].strip() if out else None
    except Exception as exc:
        logger.info("GPU adi alinamadi: %s", exc)
        return None


def list_ollama_models():
    try:
        out = subprocess.check_output(
            ["ollama", "list"], creationflags=CREATE_NO_WINDOW, timeout=5,
        ).decode("utf-8", "ignore").splitlines()
        return [line.split()[0] for line in out[1:] if line.strip()]
    except Exception as exc:
        logger.info("Ollama model listesi alinamadi: %s", exc)
        return []


def collect_system_info():
    """Teshis icin sistem bilgisi sozlugu toplar. Her alt-adim AYRI
    try/except ile korunur - biri patlarsa digerleri yine de toplanir."""
    info = {"toplanma_zamani": time.strftime("%Y-%m-%d %H:%M:%S")}

    try:
        info["windows_surumu"] = platform.platform()
    except Exception as exc:
        info["windows_surumu"] = f"alinamadi: {exc}"

    try:
        info["python_surumu"] = platform.python_version()
    except Exception as exc:
        info["python_surumu"] = f"alinamadi: {exc}"

    try:
        info["gpu_adi"] = _detect_gpu_name() or "tespit edilemedi (NVIDIA olmayabilir)"
        info["gpu_vram_mb"] = hardware_mod.detect_gpu_vram_mb()
    except Exception as exc:
        info["gpu_adi"] = f"alinamadi: {exc}"
        info["gpu_vram_mb"] = None

    try:
        info["monitorler"] = capture_mod.list_monitors()
    except Exception as exc:
        info["monitorler"] = f"alinamadi: {exc}"

    try:
        info["windows_ocr_dilleri"] = sorted(ocr_mod.windows_ocr_available_languages())
    except Exception as exc:
        info["windows_ocr_dilleri"] = f"alinamadi: {exc}"

    try:
        info["ollama_modelleri"] = list_ollama_models()
    except Exception as exc:
        info["ollama_modelleri"] = f"alinamadi: {exc}"

    return info


def _tail_file_bytes(path, max_bytes):
    """Dosyanin SON max_bytes kadarini okur (buyuk log dosyalari zip'i
    sismesin diye)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        return f.read()


def capture_screenshot_png_bytes():
    """Tum sanal masaustunun (coklu monitor dahil) PNG baytlarini dondurur;
    basarisiz olursa None. Qt ana thread'ine ihtiyac duymaz (mss dogrudan
    Windows API'sini kullanir) - arka plan is parcacigindan guvenle cagrilabilir."""
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            return mss.tools.to_png(shot.rgb, shot.size)
    except Exception as exc:
        logger.error("Ekran goruntusu alinamadi: %s", exc)
        return None


def default_output_path(desktop_dir=None):
    desktop_dir = desktop_dir or os.path.join(os.path.expanduser("~"), "Desktop")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(desktop_dir, f"OyunCevirmen_sorun_bildirimi_{stamp}.zip")


def build_diagnostics_zip(config, log_path, output_path, include_screenshot=False,
                          screenshot_bytes=None):
    """Teshis paketini olusturur ve output_path'e yazar; yazilan yolu
    dondurur. screenshot_bytes verilmisse (zaten alinmis bir PNG) onu
    kullanir - ekran goruntusu almak Qt/mss gerektirdigi icin bu
    fonksiyon bundan SORUMLU TUTULMAZ (cagiran taraf saglar)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        try:
            info = collect_system_info()
            zf.writestr("sistem_bilgisi.json", json.dumps(info, ensure_ascii=False, indent=2))
        except Exception as exc:
            logger.error("Sistem bilgisi pakete eklenemedi: %s", exc)

        try:
            zf.writestr("config_redacted.json",
                        json.dumps(redact_config(config), ensure_ascii=False, indent=2))
        except Exception as exc:
            logger.error("config.json pakete eklenemedi: %s", exc)

        try:
            if log_path and os.path.exists(log_path):
                zf.writestr("oyuncevirmen.log", _tail_file_bytes(log_path, MAX_LOG_BYTES))
        except Exception as exc:
            logger.error("Log dosyasi pakete eklenemedi: %s", exc)

        if include_screenshot and screenshot_bytes:
            try:
                zf.writestr("ekran_goruntusu.png", screenshot_bytes)
            except Exception as exc:
                logger.error("Ekran goruntusu pakete eklenemedi: %s", exc)

    logger.info("Sorun bildirimi paketi olusturuldu: %s", output_path)
    return output_path
