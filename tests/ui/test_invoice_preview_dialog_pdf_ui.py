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


def test_invoice_preview_print_uses_temp_pdf_pipeline(monkeypatch, qapp, tmp_path: Path):
    from ui import invoice_preview_dialog as preview_mod

    monkeypatch.setattr(preview_mod, "WEB_ENGINE_AVAILABLE", True, raising=True)
    monkeypatch.setattr(preview_mod, "QWebEngineView", _FakeWebEngineView, raising=True)

    info_calls = []
    warning_calls = []
    monkeypatch.setattr(
        preview_mod.QMessageBox,
        "information",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        preview_mod.QMessageBox,
        "warning",
        lambda *args, **kwargs: warning_calls.append((args, kwargs)),
        raising=False,
    )

    dialog = preview_mod.InvoicePreviewDialog(
        html_content="<html><body><h1>Invoice</h1></body></html>",
        title="Preview",
        exports_dir=tmp_path,
        file_basename="invoice_preview_test",
    )
    dialog.show()
    qapp.processEvents()

    fake_printer = object()
    temp_pdf_path = tmp_path / "invoice_preview_print.pdf"
    printed = {}

    monkeypatch.setattr(dialog, "_create_printer", lambda: fake_printer)
    monkeypatch.setattr(dialog, "_request_print_dialog", lambda printer: printer is fake_printer)
    monkeypatch.setattr(dialog, "_create_temp_print_pdf_path", lambda: temp_pdf_path)

    def _fake_print_pdf_file(pdf_path: Path, printer):
        printed["printer"] = printer
        printed["path"] = pdf_path
        printed["exists"] = pdf_path.exists()
        printed["bytes"] = pdf_path.read_bytes()

    monkeypatch.setattr(dialog, "_print_pdf_file", _fake_print_pdf_file)

    dialog._print_to_printer()
    qapp.processEvents()

    assert printed["printer"] is fake_printer
    assert printed["path"] == temp_pdf_path
    assert printed["exists"] is True
    assert printed["bytes"].startswith(b"%PDF-1.4")
    assert not temp_pdf_path.exists()
    assert info_calls
    assert not warning_calls

    dialog.reject()
