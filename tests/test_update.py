"""
app/core/update.py testleri (5.2): surum karsilastirma (saf fonksiyonlar),
"gunde en fazla bir kez" kontrol kisitlamasi, ve GitHub API hatalarina
karsi dayaniklilik.

Gercek internet/GitHub API'sine ihtiyac duymaz (requests.get mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app.core import update


# --------------------------------------------------------------- parse_version
def test_parse_version_with_v_prefix():
    assert update.parse_version("v2.1.0") == (2, 1, 0)


def test_parse_version_without_prefix():
    assert update.parse_version("2.1.0") == (2, 1, 0)


def test_parse_version_handles_suffix():
    assert update.parse_version("2.1.0-beta") == (2, 1, 0)


def test_parse_version_rejects_malformed():
    assert update.parse_version("surum-yok") is None
    assert update.parse_version("") is None
    assert update.parse_version(None) is None


# ------------------------------------------------------------ is_newer_version
def test_is_newer_version_true_for_higher_patch():
    assert update.is_newer_version("2.1.0", "2.1.1") is True


def test_is_newer_version_true_for_higher_minor_or_major():
    assert update.is_newer_version("2.1.0", "2.2.0") is True
    assert update.is_newer_version("2.1.0", "3.0.0") is True


def test_is_newer_version_false_for_same_or_older():
    assert update.is_newer_version("2.1.0", "2.1.0") is False
    assert update.is_newer_version("2.1.0", "2.0.9") is False


def test_is_newer_version_false_when_unparseable():
    assert update.is_newer_version("2.1.0", "surum-yok") is False
    assert update.is_newer_version("surum-yok", "2.1.0") is False


# ----------------------------------------------------------- should_check_now
def test_should_check_now_true_when_never_checked():
    assert update.should_check_now(None, now=1000.0) is True


def test_should_check_now_false_within_interval():
    assert update.should_check_now(1000.0, now=1000.0 + 100, interval_seconds=86400) is False


def test_should_check_now_true_after_interval():
    assert update.should_check_now(1000.0, now=1000.0 + 86401, interval_seconds=86400) is True


def test_should_check_now_true_for_malformed_timestamp():
    assert update.should_check_now("gecersiz", now=1000.0) is True


# -------------------------------------------------------------- fetch_latest_release
def test_fetch_latest_release_returns_tag_and_url():
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {"tag_name": "v2.2.0", "html_url": "https://example.com/v2.2.0"}
    with patch.object(update.requests, "get", return_value=fake_resp):
        release = update.fetch_latest_release()
    assert release == {"tag_name": "v2.2.0", "html_url": "https://example.com/v2.2.0"}


def test_fetch_latest_release_returns_none_on_404():
    """Henuz hic surum yayinlanmamissa GitHub 404 doner - bu NORMAL bir
    durumdur, hataya YOL ACMAMALI."""
    fake_resp = MagicMock(status_code=404)
    with patch.object(update.requests, "get", return_value=fake_resp):
        assert update.fetch_latest_release() is None


def test_fetch_latest_release_returns_none_on_network_error():
    with patch.object(update.requests, "get", side_effect=OSError("internet yok")):
        assert update.fetch_latest_release() is None


def test_fetch_latest_release_returns_none_when_tag_missing():
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {}
    with patch.object(update.requests, "get", return_value=fake_resp):
        assert update.fetch_latest_release() is None


# -------------------------------------------------------------- check_for_update
def test_check_for_update_skips_when_too_soon():
    with patch.object(update, "fetch_latest_release") as fetch:
        release, checked_at = update.check_for_update("2.1.0", last_checked_at=1000.0, now=1000.0 + 10)
    fetch.assert_not_called()
    assert release is None
    assert checked_at == 1000.0


def test_check_for_update_returns_release_when_newer():
    with patch.object(update, "fetch_latest_release",
                       return_value={"tag_name": "v2.2.0", "html_url": "x"}):
        release, checked_at = update.check_for_update("2.1.0", last_checked_at=None, now=5000.0)
    assert release == {"tag_name": "v2.2.0", "html_url": "x"}
    assert checked_at == 5000.0


def test_check_for_update_returns_none_when_not_newer():
    with patch.object(update, "fetch_latest_release",
                       return_value={"tag_name": "v2.1.0", "html_url": "x"}):
        release, checked_at = update.check_for_update("2.1.0", last_checked_at=None, now=5000.0)
    assert release is None
    assert checked_at == 5000.0  # kontrol zamani yine de ilerletilmeli


def test_check_for_update_returns_none_when_fetch_fails():
    with patch.object(update, "fetch_latest_release", return_value=None):
        release, checked_at = update.check_for_update("2.1.0", last_checked_at=None, now=5000.0)
    assert release is None
    assert checked_at == 5000.0
