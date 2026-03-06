from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget


class _FakePage:
    def printToPdf(self, callback):
        # يحاكي Overload الخاص بـ PyQt6: callback فقط.
        assert callable(callback)
        callback(bytearray(b"%PDF-1.4\n%fake-data\n"))


class _FakeWebEngineView(QWidget):
    loadFinished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._page = _FakePage()

    def page(self):
        return self._page

    def setHtml(self, _html, _base_url):
        # محاكاة اكتمال التحميل بشكل غير متزامن.
        QTimer.singleShot(0, lambda: self.loadFinished.emit(True))


def test_invoice_preview_save_pdf_uses_callback_overload(monkeypatch, qapp, tmp_path: Path):
    from ui import invoice_preview_dialog as preview_mod

    monkeypatch.setattr(preview_mod, "WEB_ENGINE_AVAILABLE", True, raising=True)
    monkeypatch.setattr(preview_mod, "QWebEngineView", _FakeWebEngineView, raising=True)

    dialog = preview_mod.InvoicePreviewDialog(
        html_content="<html><body><h1>Invoice</h1></body></html>",
        title="Preview",
        exports_dir=tmp_path,
        file_basename="invoice_preview_test",
    )
    dialog.show()
    qapp.processEvents()

    dialog._save_pdf()
    qapp.processEvents()

    pdf_path = tmp_path / "invoice_preview_test.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF-1.4")

    dialog.reject()
