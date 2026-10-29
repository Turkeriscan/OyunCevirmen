"""
config.py saglamlik testleri: eksik/bozuk config.json dosyalari programi
cokertmeden calismaya devam etmeli.
"""
import json

import pytest

from app import config as config_mod


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Her test icin gercek config.json'a dokunmayan, temiz bir ortam."""
    path = tmp_path / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(path))
    monkeypatch.setattr(config_mod, "_cached", None)
    yield path
    monkeypatch.setattr(config_mod, "_cached", None)


def test_missing_file_creates_defaults(isolated_config):
    assert not isolated_config.exists()
    cfg = config_mod.load_config()
    assert cfg == config_mod.DEFAULT_CONFIG
    assert isolated_config.exists()  # otomatik olusturulmus olmali


def test_partial_legacy_config_keeps_missing_keys_as_default(isolated_config):
    """Eski bir surumden kalma, sadece birkac anahtar iceren config.json
    gecerli kalmali (geriye uyumluluk)."""
    isolated_config.write_text(json.dumps({"ocr_engine": "easyocr"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["ocr_engine"] == "easyocr"
    assert cfg["font_size"] == config_mod.DEFAULT_CONFIG["font_size"]
    assert cfg["allow_google_fallback"] is None


def test_corrupted_json_falls_back_to_defaults(isolated_config):
    isolated_config.write_text("{bu gecerli json degil!!!", encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg == config_mod.DEFAULT_CONFIG


def test_json_array_instead_of_object_falls_back(isolated_config):
    isolated_config.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg == config_mod.DEFAULT_CONFIG


def test_wrong_type_numeric_field_resets_to_default(isolated_config):
    """Elle bozulmus (sayi yerine metin) bir alan, O ALAN icin varsayilana
    donmeli; digerleri etkilenmemeli."""
    isolated_config.write_text(json.dumps({
        "font_size": "buyuk",
        "overlay_opacity": "yari saydam",
        "live_scan_interval": None,
        "ocr_engine": "easyocr",  # bu GECERLI, etkilenmemeli
    }), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["font_size"] == config_mod.DEFAULT_CONFIG["font_size"]
    assert cfg["overlay_opacity"] == config_mod.DEFAULT_CONFIG["overlay_opacity"]
    assert cfg["live_scan_interval"] == config_mod.DEFAULT_CONFIG["live_scan_interval"]
    assert cfg["ocr_engine"] == "easyocr"


def test_wrong_type_bool_field_resets_to_default(isolated_config):
    isolated_config.write_text(json.dumps({"ocr_upscale_small_text": "evet"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["ocr_upscale_small_text"] == config_mod.DEFAULT_CONFIG["ocr_upscale_small_text"]


def test_ocr_contrast_enhance_default_is_false():
    assert config_mod.DEFAULT_CONFIG["ocr_contrast_enhance"] is False


def test_ocr_contrast_enhance_accepts_bool(isolated_config):
    isolated_config.write_text(json.dumps({"ocr_contrast_enhance": True}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["ocr_contrast_enhance"] is True


def test_ocr_contrast_enhance_wrong_type_resets_to_default(isolated_config):
    isolated_config.write_text(json.dumps({"ocr_contrast_enhance": "evet"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["ocr_contrast_enhance"] is False


def test_live_auto_pause_enabled_default_is_true():
    assert config_mod.DEFAULT_CONFIG["live_auto_pause_enabled"] is True


def test_live_cutscene_skip_enabled_default_is_true():
    assert config_mod.DEFAULT_CONFIG["live_cutscene_skip_enabled"] is True


def test_live_auto_pause_enabled_wrong_type_resets_to_default(isolated_config):
    isolated_config.write_text(json.dumps({"live_auto_pause_enabled": "evet"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["live_auto_pause_enabled"] is True


def test_live_cutscene_skip_enabled_wrong_type_resets_to_default(isolated_config):
    isolated_config.write_text(json.dumps({"live_cutscene_skip_enabled": "evet"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["live_cutscene_skip_enabled"] is True


def test_hotkey_region_select_default():
    assert config_mod.DEFAULT_CONFIG["hotkey_region_select"] == "f8"


def test_exclude_regions_default_is_empty_list():
    assert config_mod.DEFAULT_CONFIG["exclude_regions"] == []
    assert config_mod.DEFAULT_CONFIG["include_regions"] == []


def test_exclude_regions_accepts_valid_region_list(isolated_config):
    region = {"left": 10, "top": 20, "width": 100, "height": 50}
    isolated_config.write_text(json.dumps({"exclude_regions": [region]}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["exclude_regions"] == [region]


def test_exclude_regions_rejects_non_list(isolated_config):
    isolated_config.write_text(json.dumps({"exclude_regions": "yanlis"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["exclude_regions"] == []


def test_exclude_regions_rejects_malformed_region(isolated_config):
    isolated_config.write_text(
        json.dumps({"exclude_regions": [{"left": 0, "top": 0}]}),  # width/height eksik
        encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["exclude_regions"] == []


def test_exclude_regions_rejects_non_int_fields(isolated_config):
    isolated_config.write_text(
        json.dumps({"exclude_regions": [{"left": "0", "top": 0, "width": 10, "height": 10}]}),
        encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["exclude_regions"] == []


def test_include_regions_accepts_valid_region_list(isolated_config):
    region = {"left": 0, "top": 0, "width": 10, "height": 10}
    isolated_config.write_text(json.dumps({"include_regions": [region]}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["include_regions"] == [region]


def test_wrong_type_string_field_resets_to_default(isolated_config):
    isolated_config.write_text(json.dumps({"ocr_engine": 42}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["ocr_engine"] == config_mod.DEFAULT_CONFIG["ocr_engine"]


def test_allow_google_fallback_accepts_none_and_bool(isolated_config):
    for value in (None, True, False):
        isolated_config.write_text(json.dumps({"allow_google_fallback": value}), encoding="utf-8")
        config_mod._cached = None
        cfg = config_mod.load_config()
        assert cfg["allow_google_fallback"] == value


def test_allow_google_fallback_garbage_resets_to_none(isolated_config):
    isolated_config.write_text(json.dumps({"allow_google_fallback": "kesinlikle"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["allow_google_fallback"] is None


def test_capture_monitor_identity_accepts_none(isolated_config):
    isolated_config.write_text(json.dumps({"capture_monitor_identity": None}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["capture_monitor_identity"] is None


def test_capture_monitor_identity_accepts_valid_dict(isolated_config):
    identity = {"left": 1920, "top": 0, "width": 1920, "height": 1080}
    isolated_config.write_text(json.dumps({"capture_monitor_identity": identity}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["capture_monitor_identity"] == identity


def test_capture_monitor_identity_rejects_missing_keys(isolated_config):
    isolated_config.write_text(
        json.dumps({"capture_monitor_identity": {"left": 0, "top": 0}}), encoding="utf-8"
    )
    cfg = config_mod.load_config()
    assert cfg["capture_monitor_identity"] is None


def test_capture_monitor_identity_rejects_non_dict(isolated_config):
    isolated_config.write_text(
        json.dumps({"capture_monitor_identity": "ekran 1"}), encoding="utf-8"
    )
    cfg = config_mod.load_config()
    assert cfg["capture_monitor_identity"] is None


def test_capture_monitor_identity_rejects_non_int_values(isolated_config):
    isolated_config.write_text(
        json.dumps({"capture_monitor_identity": {"left": "cok", "top": 0, "width": 1920, "height": 1080}}),
        encoding="utf-8",
    )
    cfg = config_mod.load_config()
    assert cfg["capture_monitor_identity"] is None


def test_bool_is_not_accepted_as_numeric():
    """Python'da bool, int'in alt sinifidir (True==1); numerik alanlara
    yanlislikla bool sizmasini engelleriz."""
    data = dict(config_mod.DEFAULT_CONFIG)
    data["font_size"] = True
    cleaned = config_mod._validate_config(data)
    assert cleaned["font_size"] == config_mod.DEFAULT_CONFIG["font_size"]


def test_unknown_keys_are_preserved(isolated_config):
    """Ileri bir surumden/yeni bir alandan kalma bilinmeyen anahtarlar
    silinmemeli (gelecekteki gecis icin)."""
    isolated_config.write_text(json.dumps({"gelecekteki_ayar": "deger"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg.get("gelecekteki_ayar") == "deger"


def test_save_and_reload_roundtrip(isolated_config):
    cfg = config_mod.load_config()
    cfg["font_size"] = 24
    cfg["ocr_engine"] = "easyocr"
    config_mod.save_config(cfg)
    config_mod._cached = None
    reloaded = config_mod.load_config()
    assert reloaded["font_size"] == 24
    assert reloaded["ocr_engine"] == "easyocr"


def test_fallback_order_accepts_list_of_strings(isolated_config):
    isolated_config.write_text(json.dumps({"fallback_order": ["ollama", "google"]}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["fallback_order"] == ["ollama", "google"]


def test_fallback_order_rejects_non_list(isolated_config):
    isolated_config.write_text(json.dumps({"fallback_order": "ollama,google"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["fallback_order"] == config_mod.DEFAULT_CONFIG["fallback_order"]


def test_fallback_order_rejects_non_string_items(isolated_config):
    isolated_config.write_text(json.dumps({"fallback_order": ["ollama", 42]}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["fallback_order"] == config_mod.DEFAULT_CONFIG["fallback_order"]


def test_deepl_api_key_accepts_string(isolated_config):
    isolated_config.write_text(json.dumps({"deepl_api_key": "abc123"}), encoding="utf-8")
    cfg = config_mod.load_config()
    assert cfg["deepl_api_key"] == "abc123"
