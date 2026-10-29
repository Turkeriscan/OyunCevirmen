"""
app/core/hardware.py testleri: VRAM'e gore model onerisi, nvidia-smi
cagrisinin basarisiz oldugunda (NVIDIA karti yok/surucu sorunu) sessizce
None donmesi. Gercek ekran karti gerekmez.
"""
from unittest.mock import patch

from app.core import hardware


def test_recommend_small_model_when_no_gpu():
    assert hardware.recommend_ollama_model(None) == hardware.RECOMMENDED_MODEL_SMALL


def test_recommend_small_model_for_low_vram():
    assert hardware.recommend_ollama_model(4000) == hardware.RECOMMENDED_MODEL_SMALL


def test_recommend_large_model_for_high_vram():
    assert hardware.recommend_ollama_model(12000) == hardware.RECOMMENDED_MODEL_LARGE


def test_recommend_model_boundary_at_6000mb():
    assert hardware.recommend_ollama_model(5999) == hardware.RECOMMENDED_MODEL_SMALL
    assert hardware.recommend_ollama_model(6000) == hardware.RECOMMENDED_MODEL_LARGE


def test_detect_gpu_vram_parses_nvidia_smi_output():
    with patch.object(hardware.subprocess, "check_output", return_value=b"12288\n"):
        assert hardware.detect_gpu_vram_mb() == 12288


def test_detect_gpu_vram_returns_none_when_nvidia_smi_missing():
    with patch.object(hardware.subprocess, "check_output", side_effect=FileNotFoundError()):
        assert hardware.detect_gpu_vram_mb() is None


def test_detect_gpu_vram_returns_none_on_garbage_output():
    with patch.object(hardware.subprocess, "check_output", return_value=b"bozuk cikti"):
        assert hardware.detect_gpu_vram_mb() is None


def test_recommend_model_for_this_machine_combines_both():
    with patch.object(hardware, "detect_gpu_vram_mb", return_value=10000):
        model, vram = hardware.recommend_model_for_this_machine()
    assert model == hardware.RECOMMENDED_MODEL_LARGE
    assert vram == 10000
