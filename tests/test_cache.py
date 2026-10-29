"""
TranslationCache testleri: temel bellek/disk onbellek davranisi ve
baglanti kapatildiktan sonra get()'in cokmeden None donmesi (set() bunu
zaten yapiyordu; get() icin de ayni koruma gerekliydi - bkz. close()'un
program kapanirken arka plandaki bir ceviri isiyle yarisabilecegi durum).
"""
import pytest

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
