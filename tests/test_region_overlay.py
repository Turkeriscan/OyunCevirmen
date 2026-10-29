"""
app/ui/regionoverlay.py testleri (3.5):

1) Saf yardimci fonksiyonlar (normalize_rect, is_region_large_enough,
   split_regions_by_mode) - surukleme/klavye etkilesimi GERCEK bir
   pencerede, elle test edilmelidir (bkz. KULLANIM.md); burada sadece
   geometriyi/is mantigini dogrularız.
2) RegionSelectorOverlay'in var olan bolgeleri yukleyip "Bitti" ile
   dogru sekilde geri cagirdigini (on_done) dogrulayan bir widget testi
   (gercek fare surumesi yapmadan, dogrudan ic metodu cagirarak).

Gercek ekran/fare etkilesimi gerektirmez (qapp offscreen fixture).
"""
from app.ui import regionoverlay as ro


# ---------------------------------------------------------------- normalize_rect
def test_normalize_rect_handles_any_drag_direction():
    assert ro.normalize_rect(10, 10, 50, 40) == {"left": 10, "top": 10, "width": 40, "height": 30}
    assert ro.normalize_rect(50, 40, 10, 10) == {"left": 10, "top": 10, "width": 40, "height": 30}
    assert ro.normalize_rect(50, 10, 10, 40) == {"left": 10, "top": 10, "width": 40, "height": 30}


def test_is_region_large_enough():
    assert ro.is_region_large_enough({"width": 10, "height": 10}) is True
    assert ro.is_region_large_enough({"width": 2, "height": 10}) is False
    assert ro.is_region_large_enough({"width": 10, "height": 2}) is False


def test_split_regions_by_mode():
    r1 = {"left": 0, "top": 0, "width": 10, "height": 10}
    r2 = {"left": 5, "top": 5, "width": 10, "height": 10}
    exclude, include = ro.split_regions_by_mode([(r1, ro.MODE_EXCLUDE), (r2, ro.MODE_INCLUDE)])
    assert exclude == [r1]
    assert include == [r2]


def test_split_regions_by_mode_empty():
    assert ro.split_regions_by_mode([]) == ([], [])


# -------------------------------------------------------- RegionSelectorOverlay
def test_overlay_loads_existing_regions(qapp):
    existing_exclude = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    existing_include = [{"left": 200, "top": 200, "width": 50, "height": 50}]
    widget = ro.RegionSelectorOverlay(existing_exclude, existing_include, on_done=lambda e, i: None)
    try:
        assert (existing_exclude[0], ro.MODE_EXCLUDE) in widget.regions
        assert (existing_include[0], ro.MODE_INCLUDE) in widget.regions
    finally:
        widget.close()
        widget.deleteLater()


def test_overlay_finish_calls_on_done_with_split_regions(qapp):
    captured = {}

    def on_done(exclude, include):
        captured["exclude"] = exclude
        captured["include"] = include

    widget = ro.RegionSelectorOverlay([], [], on_done=on_done)
    try:
        widget.regions = [
            ({"left": 0, "top": 0, "width": 10, "height": 10}, ro.MODE_EXCLUDE),
            ({"left": 20, "top": 20, "width": 10, "height": 10}, ro.MODE_INCLUDE),
        ]
        widget._finish()
    finally:
        widget.deleteLater()

    assert captured["exclude"] == [{"left": 0, "top": 0, "width": 10, "height": 10}]
    assert captured["include"] == [{"left": 20, "top": 20, "width": 10, "height": 10}]


def test_overlay_cancel_never_calls_on_done(qapp):
    on_done = lambda e, i: (_ for _ in ()).throw(AssertionError("cagrilmamali"))
    widget = ro.RegionSelectorOverlay([], [], on_done=on_done)
    try:
        widget.close()  # Vazgec/Esc yolu - on_done HIC cagrilmamali
    finally:
        widget.deleteLater()


def test_undo_last_removes_most_recent_region(qapp):
    widget = ro.RegionSelectorOverlay([], [], on_done=lambda e, i: None)
    try:
        widget.regions = [
            ({"left": 0, "top": 0, "width": 10, "height": 10}, ro.MODE_EXCLUDE),
            ({"left": 20, "top": 20, "width": 10, "height": 10}, ro.MODE_INCLUDE),
        ]
        widget._undo_last()
        assert len(widget.regions) == 1
        assert widget.regions[0][1] == ro.MODE_EXCLUDE
    finally:
        widget.deleteLater()


def test_clear_all_removes_every_region(qapp):
    widget = ro.RegionSelectorOverlay(
        [{"left": 0, "top": 0, "width": 10, "height": 10}], [], on_done=lambda e, i: None)
    try:
        widget._clear_all()
        assert widget.regions == []
    finally:
        widget.deleteLater()
