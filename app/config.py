"""
Ayarlar modülü.
config.json dosyasını okur/yazar. Dosya yoksa varsayılan ayarlarla oluşturur.
"""
import json
import logging
import os
import threading

from app.core import glossary as glossary_mod

logger = logging.getLogger("OyunCevirmen.config")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\OyunCevirmen
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    # OCR motoru: "windows" (varsayilan, kurulum gerektirmez) | "easyocr" (GPU/CUDA)
    # Not: "paddle" da desteklenir ama bu bilgisayardaki RTX 5070 (Blackwell, sm_120)
    # icin PaddlePaddle GPU derlemesi resmi olarak uyumlu degil (test edildi, yanlis
    # sonuc verdi) - bu yuzden GPU alternatifi olarak EasyOCR kullaniliyor.
    "ocr_engine": "windows",
    # Çeviri motoru: "ollama" | "google" | "argos" (çevrimdışı, isteğe bağlı
    # kurulum) | "deepl" (bulut, ücretsiz API anahtarı gerekir)
    "translate_engine": "ollama",
    "ollama_model": "aya-expanse:8b",
    "ollama_host": "http://127.0.0.1:11434",
    # Birincil motor basarisiz/suphesiz çevrilemezse hangi sırayla diger
    # motorlar denenir (örn. Ollama -> Argos -> Google). Kurulu/yapılandırılmış
    # olmayan bir motor (örn. Argos kurulu değilse) otomatik atlanır.
    "fallback_order": ["ollama", "argos", "google"],
    # DeepL ücretsiz API anahtarı (www.deepl.com/pro-api'den alınır). Boşsa
    # DeepL motoru hiç kullanılamaz.
    "deepl_api_key": "",
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
    "hotkey_region_select": "f8",
    # Basili TUTULDUKCA ceviri kutularini gizler (orijinal yaziyi gormek icin);
    # birakinca geri gelir.
    "hotkey_hold_reveal": "f6",
    # Canlı mod tarama sıklığı (saniye)
    "live_scan_interval": 0.45,
    # Canlı modda ekranın kaç sütun/satıra bölüneceği (değişen bölge tespiti için)
    "live_grid_cols": 6,
    "live_grid_rows": 4,
    # Hucreler kirpilirken sinirlarin disina tasan pay (piksel). Bir kelime
    # tam hucre sinirina denk gelirse ikiye bolunup yanlis okunmasini onler.
    "live_cell_padding": 220,
    # Harf harf beliren diyalog (typewriter efekti): bir metnin "buyudugu"
    # (onceki taramadakinin devami oldugu) gozlenirse, bu kadar milisaniye
    # DEGISMEDEN kalana kadar cevrilmez - ara durumlar bosa cevrilmesin.
    "live_typewriter_debounce_ms": 400,
    # Akıllı filtreleme eşikleri
    "min_text_length": 2,
    "min_ocr_confidence": 0.45,
    # Kucuk yazilari OCR'dan once 2 kat buyutup koordinatlari geri olcekler;
    # kucuk fontlu oyun ici yazilarda okuma isabetini artirir.
    "ocr_upscale_small_text": True,
    # CLAHE ile kontrasti artirir; acik-uzerine-acik (soluk) yazilar icin
    # OCR isabetini artirabilir ama her oyunda gerekli degildir, varsayilan kapali.
    "ocr_contrast_enhance": False,
    # Oyun arka plana alinirsa veya bilgisayar bosta kalirsa canli modu
    # gecici olarak duraklatir (kaynak tasarrufu).
    "live_auto_pause_enabled": True,
    # Ekranin cogu birden degisirse (sinematik/sahne gecisi) o kareyi
    # cevirmeye hic gondermez.
    "live_cutscene_skip_enabled": True,
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
    # Secili monitorun "kimligi" (konum+cozunurluk): ekran dizilimi
    # degisirse (yeni monitor eklenir/cikarilirsa) bile DOGRU fiziksel
    # ekranin bulunabilmesi icin salt sira numarasindan daha guvenilir bir
    # referans (bkz. app/core/capture.py resolve_monitor_index). Henuz
    # kaydedilmemisse None.
    "capture_monitor_identity": None,
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
    # Kullanicinin elle cizdigi bolgeler (3.5), masaustu MUTLAK piksel
    # koordinatinda: [{"left","top","width","height"}, ...]. exclude_regions
    # icindeki bolgeler HIC OKUNMAZ. include_regions BOS DEGILSE, SADECE o
    # bolgeler okunur (digeri yoksayilir, exclude_regions'un ustune de uygulanir).
    "exclude_regions": [],
    "include_regions": [],
    # Oyun bazli profiller (4.1): on plandaki .exe'ye gore OCR motoru/dili,
    # overlay stili, okuma bolgeleri ve sozluk otomatik degisir.
    "game_profiles_enabled": True,
    # {"oyun.exe": {"ocr_engine":..., "source_lang":..., "overlay_style":...,
    #               "exclude_regions":[...], "include_regions":[...], "glossary":[...]}}
    "game_profiles": {},
}

# Degeri None/esnek kalabilen anahtarlar: turu zorlanmaz, kullanildiklari
# yerlerde zaten savunmaci kontrol var (orn. _restore_geometry, MiniPanel.place).
_NULLABLE_KEYS = {
    "allow_google_fallback", "mini_panel_pos", "window_geometry", "capture_monitor_identity",
}
_MONITOR_IDENTITY_KEYS = ("left", "top", "width", "height")
_REGION_LIST_KEYS = {"exclude_regions", "include_regions"}
_REGION_KEYS = ("left", "top", "width", "height")


def _is_valid_game_profile(profile):
    if not isinstance(profile, dict):
        return False
    for key in ("ocr_engine", "source_lang", "overlay_style"):
        if key in profile and not isinstance(profile[key], str):
            return False
    for key in ("exclude_regions", "include_regions"):
        if key in profile:
            value = profile[key]
            if not (isinstance(value, list) and all(_is_valid_region(r) for r in value)):
                return False
    if "glossary" in profile and not isinstance(profile["glossary"], list):
        return False
    return True


def _is_valid_game_profiles(value):
    return (
        isinstance(value, dict)
        and all(isinstance(k, str) for k in value)
        and all(_is_valid_game_profile(p) for p in value.values())
    )


def _is_valid_region(region):
    return (
        isinstance(region, dict)
        and all(k in region for k in _REGION_KEYS)
        and all(isinstance(region[k], int) and not isinstance(region[k], bool)
                for k in _REGION_KEYS)
    )

_lock = threading.RLock()  # load_config() ilk calistirmada save_config()'u kilit tutarken cagirabilir
_cached = None


def _validate_config(data):
    """Kullanici config.json'u elle bozmus olabilir (orn. sayi yerine metin
    yazmis). Boyle bir anahtari SESSIZCE varsayilana dondurur, boylece
    bozuk bir deger programin derinlerinde (orn. overlay cizimi, int()
    donusumu) beklenmedik bir cokmeye yol acmaz. Bilinmeyen anahtarlar
    (ileri surumlerden kalma olabilir) oldugu gibi birakilir."""
    cleaned = dict(data)
    for key, default in DEFAULT_CONFIG.items():
        if key not in cleaned:
            continue
        value = cleaned[key]
        if key in _NULLABLE_KEYS:
            if key == "allow_google_fallback" and value not in (None, True, False):
                logger.warning("config.json: '%s' gecersiz (%r), sifirlaniyor.", key, value)
                cleaned[key] = None
            elif key == "capture_monitor_identity" and value is not None:
                valid = (
                    isinstance(value, dict)
                    and all(k in value for k in _MONITOR_IDENTITY_KEYS)
                    and all(isinstance(value[k], int) and not isinstance(value[k], bool)
                            for k in _MONITOR_IDENTITY_KEYS)
                )
                if not valid:
                    logger.warning("config.json: '%s' gecersiz (%r), sifirlaniyor.", key, value)
                    cleaned[key] = None
            continue
        if key in _REGION_LIST_KEYS:
            valid = isinstance(value, list) and all(_is_valid_region(r) for r in value)
            if not valid:
                logger.warning("config.json: '%s' gecersiz (%r), varsayilana donuluyor.", key, value)
                cleaned[key] = list(default)
            continue
        if key == "game_profiles":
            if not _is_valid_game_profiles(value):
                logger.warning("config.json: '%s' gecersiz, varsayilana donuluyor.", key)
                cleaned[key] = dict(default)
            continue
        if isinstance(default, bool):
            if not isinstance(value, bool):
                logger.warning("config.json: '%s' gecersiz (%r), varsayilana donuluyor.", key, value)
                cleaned[key] = default
        elif isinstance(default, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                logger.warning("config.json: '%s' gecersiz (%r), varsayilana donuluyor.", key, value)
                cleaned[key] = default
        elif isinstance(default, str):
            if not isinstance(value, str):
                logger.warning("config.json: '%s' gecersiz (%r), varsayilana donuluyor.", key, value)
                cleaned[key] = default
        elif isinstance(default, list):
            valid = (
                isinstance(value, list)
                and all(isinstance(v, str) for v in value)
            )
            if not valid:
                logger.warning("config.json: '%s' gecersiz (%r), varsayilana donuluyor.", key, value)
                cleaned[key] = list(default)
    return cleaned


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
            if not isinstance(data, dict):
                raise ValueError("config.json bir nesne (object) olmali")
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("config.json okunamadi (%s), varsayilanlarla devam ediliyor.", exc)
            data = {}
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        merged = _validate_config(merged)
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
