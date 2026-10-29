"""
merge_paragraph_lines() testleri (app/core/ocr.py): OCR motorunun uzun
bir paragrafi (kitap, tabela, gorev metni) ayri satirlara bolmesi,
modelin baglamdan koparilmis tek satirlari halusinasyonla doldurmasina
yol aciyordu (bkz. onceki "paragraf fragmantasyonu" duzeltmesi). Bu
fonksiyon dikeyde yakin + sol kenari hizali ardisik satirlari tek bir
bloga birlestirir; alakasiz/uzak/hizasiz satirlari AYRI birakmasi da
en az merge etmesi kadar onemli (aksi halde menu/UI ogeleri yanlislikla
birbirine karisir).
"""
from app.core.ocr import OCRBoxResult, merge_paragraph_lines


def _r(text, l, t, r, b, conf=0.9):
    return OCRBoxResult(text, conf, (l, t, r, b))


def test_empty_list_returns_as_is():
    assert merge_paragraph_lines([]) == []


def test_single_line_unchanged():
    items = [_r("Press E to open", 10, 10, 150, 30)]
    result = merge_paragraph_lines(items)
    assert len(result) == 1
    assert result[0].text == "Press E to open"
    assert result[0].bbox == (10, 10, 150, 30)


def test_two_close_left_aligned_lines_merge_into_one():
    """Tipik paragraf satir araligi + sol kenar hizasi -> birlestirilmeli."""
    line1 = _r("This is the first line", 10, 10, 200, 30, conf=0.95)
    line2 = _r("and this is the second.", 10, 32, 210, 52, conf=0.80)
    result = merge_paragraph_lines([line1, line2])
    assert len(result) == 1
    assert result[0].text == "This is the first line and this is the second."


def test_merged_bbox_is_union_of_group():
    line1 = _r("abc", 10, 10, 200, 30)
    line2 = _r("def", 5, 32, 210, 52)
    result = merge_paragraph_lines([line1, line2])
    l, t, r, b = result[0].bbox
    assert (l, t, r, b) == (5, 10, 210, 52)


def test_merged_confidence_is_minimum_of_group():
    """Dusuk guvenli bir satir, birlestirilmis blogun GUVENINI de dusurmeli
    (en zayif halka mantigi - esik filtresi yanlislikla atlamasin)."""
    line1 = _r("abc", 10, 10, 200, 30, conf=0.95)
    line2 = _r("def", 10, 32, 200, 52, conf=0.40)
    result = merge_paragraph_lines([line1, line2])
    assert result[0].confidence == 0.40


def test_far_apart_lines_not_merged():
    """Aralarinda buyuk bosluk olan iki satir (ayri UI ogeleri olma
    ihtimali yuksek) birlestirilmemeli."""
    line1 = _r("Inventory", 10, 10, 150, 30)
    line2 = _r("Press E to open the door", 10, 400, 300, 420)
    result = merge_paragraph_lines([line1, line2])
    assert len(result) == 2


def test_same_row_different_columns_not_merged():
    """Ayni satirda (dikey ortusen), yan yana iki ayri yazi (orn. iki ayri
    menu ogesi) paragraf devami SAYILMAMALI."""
    left_item = _r("HP: 100", 10, 10, 80, 30)
    right_item = _r("MP: 50", 300, 10, 380, 30)
    result = merge_paragraph_lines([left_item, right_item])
    assert len(result) == 2


def test_misaligned_and_far_lines_not_merged():
    """Hem sol kenar hizasiz HEM de yatay ortusmesiz iki satir
    birlestirilmemeli (farkli hizali iki bagimsiz etiket)."""
    line1 = _r("Quest: Find the sword", 10, 10, 220, 30)
    line2 = _r("Gold: 500", 500, 32, 600, 52)
    result = merge_paragraph_lines([line1, line2])
    assert len(result) == 2


def test_hanging_indent_merges_via_horizontal_overlap():
    """Sol kenar tam hizali olmasa da (orn. ikinci satir girintili) yatay
    ortusme varsa yine de ayni paragrafin devami sayilmali."""
    line1 = _r("Lorem ipsum dolor sit amet consectetur", 10, 10, 300, 30)
    line2 = _r("adipiscing elit sed do eiusmod", 60, 32, 280, 52)
    result = merge_paragraph_lines([line1, line2])
    assert len(result) == 1


def test_three_line_paragraph_merges_regardless_of_input_order():
    """OCR satirlari karisik sirada dondurse bile (yukaridan asagi
    siralama fonksiyon icinde yapiliyor), uc satirlik bir paragraf tek
    bloka birlesmeli."""
    line1 = _r("First line of the paragraph", 10, 10, 250, 30)
    line2 = _r("second line continues here", 10, 32, 240, 52)
    line3 = _r("and the third line ends it.", 10, 54, 260, 74)
    result = merge_paragraph_lines([line3, line1, line2])  # kasitli karisik sira
    assert len(result) == 1
    assert result[0].text == (
        "First line of the paragraph second line continues here "
        "and the third line ends it."
    )


def test_does_not_mutate_input_list():
    items = [_r("abc", 10, 10, 200, 30), _r("def", 10, 32, 200, 52)]
    original_len = len(items)
    merge_paragraph_lines(items)
    assert len(items) == original_len


def test_empty_text_lines_excluded_from_joined_text():
    """Bos metinli bir kutu (orn. sadece bir cizgi/sembol OCR tarafindan
    bos string olarak donmus) birlesmis metne fazladan bosluk eklememeli."""
    line1 = _r("Hello", 10, 10, 200, 30)
    line2 = _r("", 10, 32, 200, 52)
    line3 = _r("world", 10, 54, 200, 74)
    result = merge_paragraph_lines([line1, line2, line3])
    assert len(result) == 1
    assert result[0].text == "Hello world"
