"""
Ayarlar modülü.
config.json dosyasını okur/yazar. Dosya yoksa varsayılan ayarlarla oluşturur.
"""
import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\OyunCevirmen
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    # OCR motoru: "windows" (varsayilan, kurulum gerektirmez) | "easyocr" (GPU/CUDA)
    # Not: "paddle" da desteklenir ama bu bilgisayardaki RTX 5070 (Blackwell, sm_120)
    # icin PaddlePaddle GPU derlemesi resmi olarak uyumlu degil (test edildi, yanlis
    # sonuc verdi) - bu yuzden GPU alternatifi olarak EasyOCR kullaniliyor.
    "ocr_engine": "windows",
    # Çeviri motoru: "ollama" | "google"
    "translate_engine": "ollama",
    "ollama_model": "aya-expanse:8b",
    "ollama_host": "http://127.0.0.1:11434",
    # Kaynak dil: "auto" tüm Latin alfabesi dillerini dener, OCR dili olarak kullanılır
    "source_lang": "auto",
    "target_lang": "tr",
    # Overlay görünümü
    "font_size": 18,
    "min_font_size": 10,
    "overlay_opacity": 0.72,
    "overlay_bg_color": "#141414",
    "overlay_text_color": "#FFFFFF",
    # Kısayollar (keyboard kütüphanesi formatında)
    "hotkey_instant": "f9",
    "hotkey_live_toggle": "f10",
    "hotkey_quit": "f11",
    # Canlı mod tarama sıklığı (saniye)
    "live_scan_interval": 0.45,
    # Canlı modda ekranın kaç sütun/satıra bölüneceği (değişen bölge tespiti için)
    "live_grid_cols": 6,
    "live_grid_rows": 4,
    # Hucreler kirpilirken sinirlarin disina tasan pay (piksel). Bir kelime
    # tam hucre sinirina denk gelirse ikiye bolunup yanlis okunmasini onler.
    "live_cell_padding": 220,
    # Akıllı filtreleme eşikleri
    "min_text_length": 2,
    "min_ocr_confidence": 0.45,
    # Kucuk yazilari OCR'dan once 2 kat buyutup koordinatlari geri olcekler;
    # kucuk fontlu oyun ici yazilarda okuma isabetini artirir.
    "ocr_upscale_small_text": True,
    # Canli modda onbellekte olmayan satirlar en fazla bu kadar is parcaciginda
    # AYNI ANDA cevrilir (Ollama'ya asiri paralel yuk binmesin diye sinirli).
    "translate_parallel_workers": 3,
    # Diyaloglarda zamir/hitap tutarliligi icin modele son kac satirin
    # cevirisi baglam olarak (cevrilmeden, sadece referans icin) verilsin.
    "translate_context_lines": 4,
    # Ollama calismadiginda/supheli ceviri uretirse YEDEK olarak Google
    # Translate'e (internete) metin gonderilsin mi? Uc durumlu:
    #   None  -> henuz sorulmadi (ilk ihtiyac aninda bir kez sorulur)
    #   True  -> izin verildi
    #   False -> izin verilmedi (ceviri yapilmaz, durum net gosterilir)
    # Kullanici ceviri motoru olarak BILEREK "google" secerse bu ayar
    # devreye girmez (zaten acikca onaylamis olur).
    "allow_google_fallback": None,
    # Performans
    "max_cache_memory_items": 5000,
    "capture_monitor_index": 0,
    # Ceviri kutularinin stili: "box" (kutu) | "subtitle" (altyazi) | "band" (serit)
    "overlay_style": "box",
    # Ceviri yazi tipi: "plex" (programla gelir) | "segoe" (Windows) | "serif" (Newsreader)
    "overlay_font": "plex",
    # Arayuz durumu
    "onboarding_done": False,
    "mini_panel_enabled": False,
    "mini_panel_pos": None,
    "window_geometry": None,
    # Log seviyesi
    "log_level": "INFO",
}

_lock = threading.RLock()  # load_config() ilk calistirmada save_config()'u kilit tutarken cagirabilir
_cached = None


def load_config():
    global _cached
    with _lock:
        if _cached is not None:
            return _cached
        if not os.path.exists(CONFIG_PATH):
            _cached = dict(DEFAULT_CONFIG)
            save_config(_cached)
            return _cached
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        _cached = merged
        return _cached


def save_config(cfg):
    global _cached
    with _lock:
        _cached = dict(cfg)
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CONFIG_PATH)


def update_config(**kwargs):
    cfg = load_config()
    cfg.update(kwargs)
    save_config(cfg)
    return cfg


def reload_config():
    global _cached
    with _lock:
        _cached = None
    return load_config()
