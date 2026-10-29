"""
app/core/diagnostics.py testleri (4.5): sorun bildirimi paketi - gizli
alanlarin maskelenmesi, sistem bilgisi toplama (her alt-adim AYRI
korunur), log kirpma, ve zip paketinin dogru icerikle olusturulmasi.

Gercek ekran/Windows API/Ollama gerektirmez.
"""
import json
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from app.core import diagnostics


# ------------------------------------------------------------------- redact_config
def test_redact_config_masks_deepl_key_when_present():
    cfg = {"deepl_api_key": "gizli-anahtar-123", "ocr_engine": "windows"}
    redacted = diagnostics.redact_config(cfg)
    assert redacted["deepl_api_key"] == "***gizlendi***"
    assert redacted["ocr_engine"] == "windows"


def test_redact_config_leaves_empty_key_untouched():
    cfg = {"deepl_api_key": "", "ocr_engine": "windows"}
    redacted = diagnostics.redact_config(cfg)
    assert redacted["deepl_api_key"] == ""


def test_redact_config_does_not_mutate_original():
    cfg = {"deepl_api_key": "secret"}
    diagnostics.redact_config(cfg)
    assert cfg["deepl_api_key"] == "secret"


# -------------------------------------------------------------- collect_system_info
def test_collect_system_info_includes_all_expected_keys():
    with patch.object(diagnostics, "_detect_gpu_name", return_value="RTX 5070"), \
         patch.object(diagnostics.hardware_mod, "detect_gpu_vram_mb", return_value=12288), \
         patch.object(diagnostics.capture_mod, "list_monitors", return_value=[{"index": 0}]), \
         patch.object(diagnostics.ocr_mod, "windows_ocr_available_languages", return_value={"en-us"}), \
         patch.object(diagnostics, "list_ollama_models", return_value=["aya-expanse:8b"]):
        info = diagnostics.collect_system_info()

    assert info["gpu_adi"] == "RTX 5070"
    assert info["gpu_vram_mb"] == 12288
    assert info["monitorler"] == [{"index": 0}]
    assert info["windows_ocr_dilleri"] == ["en-us"]
    assert info["ollama_modelleri"] == ["aya-expanse:8b"]
    assert "windows_surumu" in info
    assert "python_surumu" in info


def test_collect_system_info_survives_individual_failures():
    """Bir alt-adim (orn. GPU tespiti) patlarsa DIGER bilgiler yine de
    toplanmali - paket tamamen bos donmemeli."""
    with patch.object(diagnostics, "_detect_gpu_name", side_effect=RuntimeError("patlat")), \
         patch.object(diagnostics.capture_mod, "list_monitors", return_value=[{"index": 0}]):
        info = diagnostics.collect_system_info()

    assert "alinamadi" in info["gpu_adi"]
    assert info["monitorler"] == [{"index": 0}]


def test_list_ollama_models_returns_empty_on_failure():
    with patch.object(diagnostics.subprocess, "check_output", side_effect=FileNotFoundError()):
        assert diagnostics.list_ollama_models() == []


def test_list_ollama_models_parses_output():
    fake_output = b"NAME\tID\tSIZE\tMODIFIED\naya-expanse:8b\t\t\t1.2GB\ngemma2:2b\t\t2b\t\t\n"
    with patch.object(diagnostics.subprocess, "check_output", return_value=fake_output):
        models = diagnostics.list_ollama_models()
    assert models == ["aya-expanse:8b", "gemma2:2b"]


# -------------------------------------------------------------- capture_screenshot
def test_capture_screenshot_returns_none_on_failure():
    fake_mss_module = MagicMock()
    fake_mss_module.mss.side_effect = RuntimeError("ekran yok")
    with patch.dict("sys.modules", {"mss": fake_mss_module, "mss.tools": MagicMock()}):
        assert diagnostics.capture_screenshot_png_bytes() is None


# -------------------------------------------------------------------- _tail_file_bytes
def test_tail_file_bytes_returns_whole_file_when_small(tmp_path):
    p = tmp_path / "small.log"
    p.write_bytes(b"merhaba dunya")
    assert diagnostics._tail_file_bytes(str(p), max_bytes=1000) == b"merhaba dunya"


def test_tail_file_bytes_truncates_large_file(tmp_path):
    p = tmp_path / "big.log"
    p.write_bytes(b"a" * 100)
    tail = diagnostics._tail_file_bytes(str(p), max_bytes=10)
    assert tail == b"a" * 10


# ---------------------------------------------------------------- default_output_path
def test_default_output_path_uses_desktop_and_zip_extension(tmp_path):
    out = diagnostics.default_output_path(desktop_dir=str(tmp_path))
    assert out.startswith(str(tmp_path))
    assert out.endswith(".zip")
    assert "OyunCevirmen_sorun_bildirimi_" in out


# ------------------------------------------------------------- build_diagnostics_zip
def test_build_diagnostics_zip_contains_expected_members(tmp_path):
    log_path = tmp_path / "oyuncevirmen.log"
    log_path.write_bytes(b"gunluk satiri\n")
    output_path = str(tmp_path / "out.zip")
    config = {"deepl_api_key": "secret", "ocr_engine": "windows"}

    with patch.object(diagnostics, "collect_system_info", return_value={"windows_surumu": "11"}):
        result = diagnostics.build_diagnostics_zip(config, str(log_path), output_path)

    assert result == output_path
    assert os.path.exists(output_path)
    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert "sistem_bilgisi.json" in names
        assert "config_redacted.json" in names
        assert "oyuncevirmen.log" in names
        assert "ekran_goruntusu.png" not in names

        redacted = json.loads(zf.read("config_redacted.json"))
        assert redacted["deepl_api_key"] == "***gizlendi***"

        info = json.loads(zf.read("sistem_bilgisi.json"))
        assert info["windows_surumu"] == "11"

        assert zf.read("oyuncevirmen.log") == b"gunluk satiri\n"


def test_build_diagnostics_zip_includes_screenshot_when_provided(tmp_path):
    output_path = str(tmp_path / "out.zip")
    with patch.object(diagnostics, "collect_system_info", return_value={}):
        diagnostics.build_diagnostics_zip(
            {}, None, output_path, include_screenshot=True, screenshot_bytes=b"PNGDATA")

    with zipfile.ZipFile(output_path) as zf:
        assert zf.read("ekran_goruntusu.png") == b"PNGDATA"


def test_build_diagnostics_zip_omits_screenshot_when_bytes_missing(tmp_path):
    output_path = str(tmp_path / "out.zip")
    with patch.object(diagnostics, "collect_system_info", return_value={}):
        diagnostics.build_diagnostics_zip(
            {}, None, output_path, include_screenshot=True, screenshot_bytes=None)

    with zipfile.ZipFile(output_path) as zf:
        assert "ekran_goruntusu.png" not in zf.namelist()


def test_build_diagnostics_zip_handles_missing_log_file_gracefully(tmp_path):
    output_path = str(tmp_path / "out.zip")
    with patch.object(diagnostics, "collect_system_info", return_value={}):
        diagnostics.build_diagnostics_zip({}, str(tmp_path / "yok.log"), output_path)

    with zipfile.ZipFile(output_path) as zf:
        assert "oyuncevirmen.log" not in zf.namelist()
        assert "sistem_bilgisi.json" in zf.namelist()


def test_build_diagnostics_zip_creates_parent_directory(tmp_path):
    output_path = str(tmp_path / "alt_klasor" / "out.zip")
    with patch.object(diagnostics, "collect_system_info", return_value={}):
        diagnostics.build_diagnostics_zip({}, None, output_path)
    assert os.path.exists(output_path)


def test_redact_text_hides_home_folder_and_username():
    from app.core import diagnostics as d
    markers = ["C:\\Users\\Ahmet", "C:/Users/Ahmet", "Ahmet"]
    text = "Hata: C:\\Users\\Ahmet\\OyunCevirmen\\x.py ve c:/users/ahmet/a ve kullanici=Ahmet"
    out = d.redact_text(text, markers)
    assert "Ahmet" not in out and "ahmet" not in out
    assert "~\\OyunCevirmen\\x.py" in out and "<kullanici>" in out
