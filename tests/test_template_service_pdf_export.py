from __future__ import annotations

from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess

from jinja2 import Environment, FileSystemLoader

from core import schemas
from services.template_service import TemplateService, _normalize_windows_loader_path


def test_generate_pdf_with_browser_uses_ascii_temp_files(monkeypatch, tmp_path: Path):
    service = object.__new__(TemplateService)

    monkeypatch.setattr(service, "_find_browser_executable", lambda: r"C:\Browser\chrome.exe")

    commands: list[list[str]] = []

    def _fake_run(cmd, capture_output, timeout, check, text):
        assert capture_output is True
        assert timeout == 30
        assert check is False
        assert text is False
        commands.append(cmd)
        temp_pdf_arg = next(arg for arg in cmd if arg.startswith("--print-to-pdf="))
        temp_pdf_path = Path(temp_pdf_arg.split("=", 1)[1])
        temp_pdf_path.write_bytes(b"%PDF-1.4\nInvoice export\n%%EOF")
        return CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("services.template_service.subprocess.run", _fake_run)

    target_pdf = tmp_path / "HighTechnology - اعلانات_شهر_2_-_هاي_تك.pdf"
    result = service._generate_pdf_with_browser(
        "<html><body>Invoice</body></html>", str(target_pdf)
    )

    assert result == str(target_pdf)
    assert target_pdf.exists()
    assert target_pdf.read_bytes().startswith(b"%PDF-1.4")
    assert commands
    assert "هاي_تك" not in commands[0][-1]
    assert "هاي_تك" not in next(arg for arg in commands[0] if arg.startswith("--print-to-pdf="))
    assert commands[0][-1].endswith("/invoice.html")


def test_generate_pdf_with_browser_rejects_browser_shell_pdf(monkeypatch, tmp_path: Path):
    service = object.__new__(TemplateService)

    monkeypatch.setattr(service, "_find_browser_executable", lambda: r"C:\Browser\chrome.exe")

    def _fake_run(cmd, capture_output, timeout, check, text):
        temp_pdf_arg = next(arg for arg in cmd if arg.startswith("--print-to-pdf="))
        temp_pdf_path = Path(temp_pdf_arg.split("=", 1)[1])
        temp_pdf_path.write_bytes(
            b"%PDF-1.4\nchrome://new-tab-page\nSearch Google or type a URL\nNew Tab\n%%EOF"
        )
        return CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("services.template_service.subprocess.run", _fake_run)

    target_pdf = tmp_path / "broken_invoice.pdf"
    result = service._generate_pdf_with_browser(
        "<html><body>Invoice</body></html>", str(target_pdf)
    )

    assert result is None
    assert not target_pdf.exists()


def test_normalize_windows_loader_path_allows_jinja_to_load_template():
    templates_dir = Path(__file__).resolve().parents[1] / "assets" / "templates" / "invoices"
    prefixed_path = "\\\\?\\" + str(templates_dir)

    env = Environment(
        loader=FileSystemLoader(_normalize_windows_loader_path(prefixed_path)),
        autoescape=True,
    )

    assert env.get_template("final_invoice.html").name == "final_invoice.html"


def test_prepare_template_data_uses_project_currency_snapshot():
    service = object.__new__(TemplateService)
    service.repo = None
    service.settings_service = None

    project = schemas.Project(
        name="USD Project",
        client_id="client-1",
        currency="USD",
        exchange_rate_snapshot=50.0,
        items=[
            schemas.ProjectItem(
                service_id="svc-1",
                description="Website",
                quantity=1.0,
                unit_price=5000.0,
                discount_rate=0.0,
                discount_amount=0.0,
                total=5000.0,
            )
        ],
        start_date=datetime(2026, 3, 13),
        end_date=datetime(2026, 3, 20),
    )

    payload = service._prepare_template_data(
        project,
        {"name": "Client A", "phone": "", "email": "", "address": ""},
        payments=[
            {
                "date": "2026-03-13",
                "amount": 2500.0,
                "method": "Cash",
                "account_name": "Cash",
            }
        ],
    )

    assert payload["currency_code"] == "USD"
    assert payload["currency_suffix"] == "USD"
    assert payload["items"][0]["price"] == "100.00"
    assert payload["items"][0]["total"] == "100.00"
    assert payload["grand_total"] == "100.00"
    assert payload["total_paid"] == "50.00"
    assert payload["remaining_amount"] == "50.00"
