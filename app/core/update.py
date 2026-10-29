"""
Surum kontrolu (5.2): GitHub Releases'e bakip yeni bir surum var mi
kontrol eder. En fazla gunde bir kez (CHECK_INTERVAL_SECONDS) kontrol
eder - her acilista internete gitmez.

Internet yoksa / GitHub'a ulasilamazsa / henuz hic surum yayinlanmamissa
(404) sessizce "yeni surum yok" kabul edilir - program ASLA bu yuzden
cokmez veya kullaniciyi rahatsiz etmez.
"""
import logging
import re

import requests

logger = logging.getLogger("OyunCevirmen.update")

GITHUB_REPO = "Turkeriscan/OyunCevirmen"
CHECK_INTERVAL_SECONDS = 86400  # gunde bir


def parse_version(value):
    """"v2.1.0" ya da "2.1.0" gibi bir dizgeyi (2,1,0) tuple'ina cevirir;
    taninmayan bicimler icin None doner (saf, hic Qt/ag gerekmez)."""
    if not value:
        return None
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    return tuple(int(g) for g in match.groups())


def is_newer_version(current, latest):
    """latest, current'tan GERCEKTEN daha yeniyse True. Ikisinden biri
    ayristirilamazsa GUVENLI TARAFTA kalinir (False) - gecersiz bir
    surum dizgesi yuzunden kullaniciya yanlis "yeni surum var" uyarisi
    gosterilmesin."""
    cur = parse_version(current)
    new = parse_version(latest)
    if cur is None or new is None:
        return False
    return new > cur


def should_check_now(last_checked_at, now, interval_seconds=CHECK_INTERVAL_SECONDS):
    if last_checked_at is None:
        return True
    try:
        return (now - float(last_checked_at)) >= interval_seconds
    except (TypeError, ValueError):
        return True


def fetch_latest_release(repo=GITHUB_REPO, timeout=5):
    """GitHub'daki en son yayinlanan surumu {"tag_name","html_url"} olarak
    dondurur; herhangi bir sebeple (internet yok, henuz surum yok, API
    sinirlamasi) alinamazsa None doner."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        resp = requests.get(url, timeout=timeout, headers={"Accept": "application/vnd.github+json"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        tag = data.get("tag_name")
        if not tag:
            return None
        return {"tag_name": tag, "html_url": data.get("html_url", "")}
    except Exception as exc:
        logger.info("Surum kontrolu basarisiz (internet olmayabilir): %s", exc)
        return None


def check_for_update(current_version, last_checked_at, now, repo=GITHUB_REPO):
    """Gerekiyorsa (bkz. should_check_now) GitHub'a sorar.

    (yeni_surum_bilgisi_veya_None, yeni_last_checked_at) dondurur.
    - Kontrol zamani gelmediyse: (None, last_checked_at) - DEGISTIRMEDEN.
    - Kontrol edildi ama yeni surum yoksa/alinamadiysa: (None, now).
    - Gercekten daha yeni bir surum bulunduysa: (release_info, now)."""
    if not should_check_now(last_checked_at, now):
        return None, last_checked_at

    release = fetch_latest_release(repo=repo)
    if release is None or not is_newer_version(current_version, release["tag_name"]):
        return None, now
    return release, now
