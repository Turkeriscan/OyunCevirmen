"""
_install_crash_handlers() testleri: pythonw.exe konsolsuz calistiginda
yakalanmamis hatalarin GUNLUGE yazildigini (sessizce kaybolmadigini)
dogrular.

Gercek bir hata/cokme olusturmaz; sys.excepthook ve threading.excepthook
yerlerine konan fonksiyonlari dogrudan cagirip logger.critical'in
cagrildigini kontrol eder. Test sonunda orijinal hook'lar geri yuklenir.
"""
import sys
import threading
import types
from unittest.mock import patch

from app import main as main_mod


def test_install_crash_handlers_sets_both_hooks():
    original_excepthook = sys.excepthook
    original_thread_excepthook = threading.excepthook
    try:
        main_mod._install_crash_handlers()
        assert sys.excepthook is not original_excepthook
        assert threading.excepthook is not original_thread_excepthook
    finally:
        sys.excepthook = original_excepthook
        threading.excepthook = original_thread_excepthook


def test_main_excepthook_logs_critical_without_raising():
    original_excepthook = sys.excepthook
    try:
        main_mod._install_crash_handlers()
        try:
            raise ValueError("test hatasi")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()

        with patch.object(main_mod.logger, "critical") as critical:
            sys.excepthook(exc_type, exc_value, exc_tb)  # cokmemeli

        critical.assert_called_once()
        assert "MainThread" in critical.call_args.args
    finally:
        sys.excepthook = original_excepthook


def test_thread_excepthook_logs_critical_with_thread_name():
    original_thread_excepthook = threading.excepthook
    try:
        main_mod._install_crash_handlers()
        try:
            raise RuntimeError("arka plan hatasi")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()

        fake_thread = types.SimpleNamespace(name="CeviriHavuzu-1")
        args = types.SimpleNamespace(
            exc_type=exc_type, exc_value=exc_value, exc_traceback=exc_tb, thread=fake_thread,
        )

        with patch.object(main_mod.logger, "critical") as critical:
            threading.excepthook(args)  # cokmemeli

        critical.assert_called_once()
        assert "CeviriHavuzu-1" in critical.call_args.args
    finally:
        threading.excepthook = original_thread_excepthook


def test_excepthook_passes_through_keyboard_interrupt():
    """Ctrl+C ile cikisi (KeyboardInterrupt) loglamamali, normal davranisa
    (sys.__excepthook__) birakmali - aksi halde Ctrl+C ile kapatma
    gunlukte 'hata' gibi gorunur ve stack trace gereksiz yere yazilir."""
    original_excepthook = sys.excepthook
    try:
        main_mod._install_crash_handlers()
        try:
            raise KeyboardInterrupt()
        except KeyboardInterrupt:
            exc_type, exc_value, exc_tb = sys.exc_info()

        with patch.object(main_mod.logger, "critical") as critical, \
             patch.object(sys, "__excepthook__") as default_hook:
            sys.excepthook(exc_type, exc_value, exc_tb)

        critical.assert_not_called()
        default_hook.assert_called_once_with(exc_type, exc_value, exc_tb)
    finally:
        sys.excepthook = original_excepthook
