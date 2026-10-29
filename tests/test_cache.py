"""
TranslationCache testleri: temel bellek/disk onbellek davranisi ve
baglanti kapatildiktan sonra get()'in cokmeden None donmesi (set() bunu
zaten yapiyordu; get() icin de ayni koruma gerekliydi - bkz. close()'un
program kapanirken arka plandaki bir ceviri isiyle yarisabilecegi durum).
"""
import pytest

from app.core import cache as cache_mod
from app.core.cache import TranslationCache


@pytest.fixture
def cache(tmp_path):
    return TranslationCache(max_memory_items=10, db_path=str(tmp_path / "test.sqlite3"))


def test_set_then_get_returns_value(cache):
    cache.set("Hello", "en", "tr", "ollama", "Merhaba")
    assert cache.get("Hello", "en", "tr", "ollama") == "Merhaba"


def test_get_missing_returns_none(cache):
    assert cache.get("Yok", "en", "tr", "ollama") is None


def test_get_is_scoped_by_engine_and_langs(cache):
    cache.set("Hi", "en", "tr", "ollama", "Selam")
    assert cache.get("Hi", "en", "tr", "google") is None
    assert cache.get("Hi", "de", "tr", "ollama") is None


def test_memory_trim_respects_max_items(cache):
    for i in range(15):
        cache.set(f"text{i}", "en", "tr", "ollama", f"ceviri{i}")
    assert len(cache._mem) <= 10


def test_get_survives_closed_connection():
    """set() SQLite hatasini zaten sessizce yutuyordu; get() de ayni
    korumaya sahip olmali - aksi halde arka planda calisan bir ceviri
    isi, program kapanirken baglanti kapatilinca cokerdi."""
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "closed.sqlite3")
    c = TranslationCache(max_memory_items=10, db_path=path)
    c._conn.close()
    assert c.get("Hello", "en", "tr", "ollama") is None  # istisna firlatmamali


def test_set_survives_closed_connection():
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "closed2.sqlite3")
    c = TranslationCache(max_memory_items=10, db_path=path)
    c._conn.close()
    c.set("Hello", "en", "tr", "ollama", "Merhaba")  # istisna firlatmamali
    assert c.get("Hello", "en", "tr", "ollama") == "Merhaba"  # bellekten gelir


def test_clear_empties_memory_and_disk(cache):
    cache.set("Hi", "en", "tr", "ollama", "Selam")
    cache.clear()
    assert cache.get("Hi", "en", "tr", "ollama") is None
    assert cache.count() == 0


def test_count_reflects_disk_entries(cache):
    assert cache.count() == 0
    cache.set("Hi", "en", "tr", "ollama", "Selam")
    assert cache.count() == 1


# ---------------------------------------------- canli siniri degistirme
def test_set_max_memory_items_updates_limit(cache):
    cache.set_max_memory_items(3)
    assert cache.max_memory_items == 3


def test_set_max_memory_items_trims_existing_entries_immediately(cache):
    for i in range(10):
        cache.set(f"text{i}", "en", "tr", "ollama", f"ceviri{i}")
    assert len(cache._mem) == 10
    cache.set_max_memory_items(3)
    assert len(cache._mem) == 3


def test_set_max_memory_items_rejects_non_positive(cache):
    """Kullanici 0 veya negatif bir deger gonderse bile (beklenmeyen
    girdi) en az 1 olarak kabul edilmeli, sonsuz dongu/cokme olmamali."""
    cache.set_max_memory_items(0)
    assert cache.max_memory_items == 1
    cache.set_max_memory_items(-5)
    assert cache.max_memory_items == 1


# ------------------------------------------- yedek motor (is_fallback) + suresi dolma
def test_set_with_is_fallback_stores_flag(cache):
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)
    _, is_fallback, _, _ = cache._mem[cache_mod._make_key("Hi", "en", "tr", "ollama")]
    assert is_fallback is True


def test_set_default_is_not_fallback(cache):
    cache.set("Hi", "en", "tr", "ollama", "Selam")
    _, is_fallback, _, _ = cache._mem[cache_mod._make_key("Hi", "en", "tr", "ollama")]
    assert is_fallback is False


def test_fallback_entry_expires_after_ttl(cache):
    """Yedek motordan (orn. Google) gelen bir ceviri, TTL suresi dolunca
    "bulunamadi" sayilmali - boylece tercih edilen motor (orn. Ollama)
    duzelince ayni satira yeniden bir sans verilsin."""
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)
    key = cache_mod._make_key("Hi", "en", "tr", "ollama")
    # Hem bellekteki hem diskteki zaman damgasini (gercek yaslanmayla
    # tutarli sekilde, ikisi birden) gecmise tasiyarak "eskimis" simule et.
    text, is_fallback, _created, is_manual = cache._mem[key]
    cache._mem[key] = (text, is_fallback, _created - cache_mod.FALLBACK_TTL_SECONDS - 1, is_manual)
    cache._conn.execute(
        "UPDATE translations SET created_at = ? WHERE key = ?",
        ("2000-01-01 00:00:00", key),
    )
    cache._conn.commit()
    assert cache.get("Hi", "en", "tr", "ollama") is None


def test_fallback_entry_still_valid_before_ttl(cache):
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)
    assert cache.get("Hi", "en", "tr", "ollama") == "Selam"


def test_non_fallback_entry_never_expires(cache):
    """is_fallback=False (tercih edilen motorun kendi sonucu) oldugunca
    eski olsa da suresi dolmamali."""
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=False)
    key = cache_mod._make_key("Hi", "en", "tr", "ollama")
    text, is_fallback, _created, is_manual = cache._mem[key]
    cache._mem[key] = (text, is_fallback, _created - 10_000_000, is_manual)
    assert cache.get("Hi", "en", "tr", "ollama") == "Selam"


def test_fallback_expiry_applies_to_disk_rows_too(tmp_path):
    """Bellekteki kayit silinmis olsa bile (program yeniden baslamis gibi),
    diskten okunan yedek bir kayit da TTL'e tabi olmali."""
    path = str(tmp_path / "ttl.sqlite3")
    c = TranslationCache(max_memory_items=10, db_path=path)
    c.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)
    c._mem.clear()  # "yeniden baslatma" simulasyonu - sadece diskte kalsin
    old_timestamp = "2000-01-01 00:00:00"
    c._conn.execute(
        "UPDATE translations SET created_at = ? WHERE key = ?",
        (old_timestamp, cache_mod._make_key("Hi", "en", "tr", "ollama")),
    )
    c._conn.commit()
    assert c.get("Hi", "en", "tr", "ollama") is None


def test_rewriting_fallback_entry_resets_ttl_clock(cache):
    """Ollama hala cokukken ayni satir TEKRAR Google'a dusup yeniden
    yazilirsa, TTL saati sIfirlanmali (surekli taze yedek kalmali)."""
    key = cache_mod._make_key("Hi", "en", "tr", "ollama")
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)
    text, is_fallback, created, is_manual = cache._mem[key]
    cache._mem[key] = (text, is_fallback, created - cache_mod.FALLBACK_TTL_SECONDS + 5, is_manual)
    cache.set("Hi", "en", "tr", "ollama", "Selam", is_fallback=True)  # tekrar yazildi
    assert cache.get("Hi", "en", "tr", "ollama") == "Selam"


# ---------------------------------------------- elle duzeltme (set_manual)
def test_set_manual_marks_entry_as_manual(cache):
    cache.set_manual("Hi", "en", "tr", "ollama", "Selam (elle)")
    assert cache.get("Hi", "en", "tr", "ollama") == "Selam (elle)"
    assert cache.is_manual("Hi", "en", "tr", "ollama") is True


def test_normal_set_does_not_overwrite_manual_entry(cache):
    """Bir motor cevirisi, kullanicinin elle duzelttigi bir satirin
    UZERINE YAZAMAMALI."""
    cache.set_manual("Hi", "en", "tr", "ollama", "Selam (elle)")
    cache.set("Hi", "en", "tr", "ollama", "Motorun cevirisi")
    assert cache.get("Hi", "en", "tr", "ollama") == "Selam (elle)"


def test_normal_set_protects_manual_entry_not_yet_in_memory(tmp_path):
    """Manual isaret SADECE DISKTE olsa bile (bu surecte henuz get()
    cagrilip bellege yuklenmemis olsa da), bir motor yazisi onu
    EZMEMELI."""
    path = str(tmp_path / "manual_disk.sqlite3")
    c = TranslationCache(max_memory_items=10, db_path=path)
    c.set_manual("Hi", "en", "tr", "ollama", "Selam (elle)")
    c._mem.clear()  # "baska bir oturum" simulasyonu - sadece diskte kalsin

    c.set("Hi", "en", "tr", "ollama", "Motorun cevirisi")
    assert c.get("Hi", "en", "tr", "ollama") == "Selam (elle)"


def test_set_manual_overwrites_existing_normal_entry(cache):
    cache.set("Hi", "en", "tr", "ollama", "Normal ceviri")
    cache.set_manual("Hi", "en", "tr", "ollama", "Elle duzeltilmis")
    assert cache.get("Hi", "en", "tr", "ollama") == "Elle duzeltilmis"


def test_set_manual_clears_fallback_flag(cache):
    cache.set("Hi", "en", "tr", "ollama", "Yedekten", is_fallback=True)
    cache.set_manual("Hi", "en", "tr", "ollama", "Elle duzeltilmis")
    key = cache_mod._make_key("Hi", "en", "tr", "ollama")
    _text, is_fallback, _created, is_manual = cache._mem[key]
    assert is_fallback is False
    assert is_manual is True


def test_is_manual_false_for_unknown_entry(cache):
    assert cache.is_manual("Yok", "en", "tr", "ollama") is False


def test_clear_manual_undoes_protection_but_keeps_text(cache):
    cache.set_manual("Hi", "en", "tr", "ollama", "Elle duzeltilmis")
    cache.clear_manual("Hi", "en", "tr", "ollama")

    assert cache.is_manual("Hi", "en", "tr", "ollama") is False
    assert cache.get("Hi", "en", "tr", "ollama") == "Elle duzeltilmis"  # metin kaybolmadi

    cache.set("Hi", "en", "tr", "ollama", "Yeni motor cevirisi")
    assert cache.get("Hi", "en", "tr", "ollama") == "Yeni motor cevirisi"  # artik ezilebilir


def test_clear_manual_on_disk_only_entry(tmp_path):
    path = str(tmp_path / "manual_undo_disk.sqlite3")
    c = TranslationCache(max_memory_items=10, db_path=path)
    c.set_manual("Hi", "en", "tr", "ollama", "Elle duzeltilmis")
    c._mem.clear()

    c.clear_manual("Hi", "en", "tr", "ollama")
    assert c.is_manual("Hi", "en", "tr", "ollama") is False
