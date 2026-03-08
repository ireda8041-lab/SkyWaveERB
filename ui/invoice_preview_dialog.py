from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QPainter
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from ui.styles import BUTTON_STYLES

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    WEB_ENGINE_AVAILABLE = True
except Exception:
    WEB_ENGINE_AVAILABLE = False
    QWebEngineView = None


class InvoicePreviewDialog(QDialog):
    def __init__(
        self,
        html_content: str,
        title: str,
        base_url: str | None = None,
        exports_dir: Path | None = None,
        file_basename: str | None = None,
        auto_print: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._auto_print = auto_print
        self._printed_once = False
        self._last_pdf_path: Path | None = None
        self._active_print_printer: QPrinter | None = None
        self._active_temp_print_pdf: Path | None = None
        self.exports_dir = exports_dir
        self.file_basename = file_basename
        self.base_url = base_url

        self.setWindowTitle(title)
        self.resize(1100, 720)

        layout = QVBoxLayout(self)

        if WEB_ENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            layout.addWidget(self.web_view, 1)

            base = QUrl.fromLocalFile(str(Path(base_url).resolve()) + "/") if base_url else QUrl()
            self.web_view.setHtml(html_content, base)
            self.web_view.loadFinished.connect(self._on_load_finished)
        else:
            self.web_view = None
            self.text_view = QTextEdit()
            self.text_view.setReadOnly(True)
            self.text_view.setHtml(html_content)
            layout.addWidget(self.text_view, 1)

        buttons_layout = QHBoxLayout()

        self.print_btn = QPushButton("🖨️ طباعة")
        self.print_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.print_btn.clicked.connect(self._print_to_printer)
        buttons_layout.addWidget(self.print_btn)

        self.save_pdf_btn = QPushButton("💾 حفظ PDF")
        self.save_pdf_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_pdf_btn.clicked.connect(self._save_pdf)
        buttons_layout.addWidget(self.save_pdf_btn)

        self.open_folder_btn = QPushButton("📂 فتح المجلد")
        self.open_folder_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.open_folder_btn.clicked.connect(self._open_exports_folder)
        buttons_layout.addWidget(self.open_folder_btn)

        close_btn = QPushButton("إغلاق")
        close_btn.setStyleSheet(BUTTON_STYLES["danger"])
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)

        layout.addLayout(buttons_layout)

        if not exports_dir:
            self.open_folder_btn.setEnabled(False)
        if not file_basename:
            self.save_pdf_btn.setEnabled(False)

    def _on_load_finished(self, ok: bool):
        if self._auto_print and ok and not self._printed_once:
            self._printed_once = True
            QTimer.singleShot(200, self._print_to_printer)

    def _print_to_printer(self):
        try:
            printer = self._create_printer()
            if not self._request_print_dialog(printer):
                return

            if WEB_ENGINE_AVAILABLE and self.web_view:
                temp_pdf_path = self._create_temp_print_pdf_path()
                self._active_print_printer = printer
                self._active_temp_print_pdf = temp_pdf_path
                self.web_view.page().printToPdf(
                    lambda pdf_data, target=temp_pdf_path, selected_printer=printer: self._on_print_pdf_data_ready(
                        pdf_data, target, selected_printer
                    )
                )
            else:
                self.text_view.document().print(printer)
                QMessageBox.information(self, "تم", "تم إرسال المستند للطابعة")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر الطباعة: {e}")

    def _create_printer(self) -> QPrinter:
        return QPrinter(QPrinter.PrinterMode.HighResolution)

    def _request_print_dialog(self, printer: QPrinter) -> bool:
        dialog = QPrintDialog(printer, self)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _create_temp_print_pdf_path(self) -> Path:
        base_name = self.file_basename or "invoice_preview_print"
        safe_base_name = "".join(
            char if char.isalnum() or char in ("_", "-") else "_" for char in str(base_name)
        ).strip("_")
        if not safe_base_name:
            safe_base_name = "invoice_preview_print"
        fd, temp_path = tempfile.mkstemp(prefix=f"{safe_base_name}_", suffix=".pdf")
        os.close(fd)
        return Path(temp_path)

    def _on_print_pdf_data_ready(self, pdf_data, pdf_path: Path, printer: QPrinter):
        try:
            pdf_bytes = bytes(pdf_data) if pdf_data is not None else b""
            if not pdf_bytes:
                self._on_print_finished(False)
                return

            pdf_path.write_bytes(pdf_bytes)
            self._print_pdf_file(pdf_path, printer)
            self._on_print_finished(True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Print failed: {e}")
        finally:
            self._cleanup_temp_print_pdf(pdf_path)

    def _cleanup_temp_print_pdf(self, pdf_path: Path):
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception:
            pass

        if self._active_temp_print_pdf == pdf_path:
            self._active_temp_print_pdf = None
        if self._active_print_printer is not None:
            self._active_print_printer = None

    def _print_pdf_file(self, pdf_path: Path, printer: QPrinter):
        from PyQt6.QtPdf import QPdfDocument

        document = QPdfDocument(self)
        load_error = document.load(str(pdf_path))
        if load_error != QPdfDocument.Error.None_:
            raise RuntimeError(f"Unable to load generated PDF ({load_error.name})")

        page_count = document.pageCount()
        if page_count <= 0:
            raise RuntimeError("Generated PDF has no printable pages")

        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("Unable to start printer painter")

        try:
            available_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            for page_index in range(page_count):
                image_size = self._build_pdf_render_size(document, page_index, available_rect)
                page_image = document.render(page_index, image_size)
                if page_image.isNull():
                    raise RuntimeError(f"Unable to render PDF page {page_index + 1}")

                target_rect = QRectF(
                    available_rect.x() + (available_rect.width() - page_image.width()) / 2.0,
                    available_rect.y() + (available_rect.height() - page_image.height()) / 2.0,
                    float(page_image.width()),
                    float(page_image.height()),
                )
                painter.drawImage(target_rect, page_image)
                if page_index < page_count - 1:
                    printer.newPage()
        finally:
            painter.end()
            document.close()

    def _build_pdf_render_size(self, document, page_index: int, available_rect: QRectF) -> QSize:
        page_size = document.pagePointSize(page_index)
        page_width = max(float(page_size.width()), 1.0)
        page_height = max(float(page_size.height()), 1.0)
        scale = min(available_rect.width() / page_width, available_rect.height() / page_height)
        return QSize(
            max(1, int(page_width * scale)),
            max(1, int(page_height * scale)),
        )

    def _on_print_finished(self, ok: bool):
        if ok:
            QMessageBox.information(self, "تم", "تم إرسال المستند للطابعة")
        else:
            QMessageBox.warning(self, "خطأ", "فشل إرسال المستند للطباعة")

    def _save_pdf(self):
        if not self.exports_dir or not self.file_basename:
            return

        try:
            pdf_path = Path(self.exports_dir) / f"{self.file_basename}.pdf"
            if WEB_ENGINE_AVAILABLE and self.web_view:
                # PyQt6 overload الصحيح: callback فقط، ثم نحفظ البيانات بأنفسنا.
                self.web_view.page().printToPdf(
                    lambda pdf_data, target=pdf_path: self._on_pdf_data_ready(pdf_data, target)
                )
            else:
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(str(pdf_path))
                self.text_view.document().print(printer)
                self._on_pdf_saved(True, pdf_path)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر حفظ PDF: {e}")

    def _on_pdf_data_ready(self, pdf_data, pdf_path: Path):
        try:
            pdf_bytes = bytes(pdf_data) if pdf_data is not None else b""
            if not pdf_bytes:
                self._on_pdf_saved(False, pdf_path)
                return

            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf_bytes)
            self._on_pdf_saved(True, pdf_path)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر حفظ PDF: {e}")

    def _on_pdf_saved(self, ok: bool, pdf_path: Path):
        if ok:
            self._last_pdf_path = pdf_path
            QMessageBox.information(self, "تم", f"تم حفظ PDF في:\n{pdf_path}")
        else:
            QMessageBox.warning(self, "خطأ", "فشل حفظ PDF")

    def _open_exports_folder(self):
        if not self.exports_dir:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.exports_dir)))
