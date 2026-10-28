"""
app/ui/widgets.py testleri: ValueSlider'in degisiklik basina TAM OLARAK
bir kez valueChanged yayinladigini dogrular (daha once degisen bir deger
icin IKI KEZ yayinlaniyordu - bkz. setValue).

Gercek ekran gerekmez: QApplication 'offscreen' platformda calisir
(bkz. conftest.py).
"""
from app.ui.widgets import ValueSlider


def test_value_slider_set_value_emits_once_when_value_changes(qapp):
    slider = ValueSlider(0.0, 1.0, 0.05, "{:.2f}")
    received = []
    slider.valueChanged.connect(received.append)

    slider.setValue(0.75)

    assert len(received) == 1
    assert abs(received[0] - 0.75) < 1e-9


def test_value_slider_set_value_same_value_does_not_emit_twice(qapp):
    slider = ValueSlider(0.0, 1.0, 0.05, "{:.2f}")
    slider.setValue(0.5)
    received = []
    slider.valueChanged.connect(received.append)

    slider.setValue(0.5)  # ayni deger - Qt hic yaymamali

    assert len(received) == 0


def test_value_slider_text_label_reflects_value(qapp):
    slider = ValueSlider(0.0, 1.0, 0.05, "{:.2f}")
    slider.setValue(0.45)
    assert slider.text.text() == "0.45"


def test_value_slider_multiple_changes_each_emit_once(qapp):
    slider = ValueSlider(0.0, 2.0, 0.1, "{:.1f}")
    received = []
    slider.valueChanged.connect(received.append)

    slider.setValue(0.5)
    slider.setValue(1.0)
    slider.setValue(1.5)

    assert len(received) == 3
