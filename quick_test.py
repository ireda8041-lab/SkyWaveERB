from services.invoice_printing_service import InvoicePrintingService
from services.settings_service import SettingsService
from datetime import datetime
import random

settings_service = SettingsService()
printing_service = InvoicePrintingService(settings_service)

timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
random_suffix = random.randint(10, 99)

invoice_data = {
    "invoice_number": f"SW-{timestamp}{random_suffix}",
    "invoice_date": "2025-12-03",
    "due_date": "2026-01-02",
    "client_name": "رضا",
    "client_phone": "+201015249745",
    "client_address": "---",
    "project_name": "jhg",
    "items": [{"name": "اعلان ممول", "qty": "1.0", "price": "500", "discount": "0.0", "total": "500"}],
    "subtotal": "500",
    "grand_total": "500",
    "total_paid": "50",
    "remaining_amount": "450",
    "payments": [{"date": "2025-12-03", "amount": "50", "method": "نقدي", "account_name": "نقدي"}]
}

context = printing_service._prepare_context(invoice_data)
template = printing_service.env.get_template("final_invoice.html")
html = template.render(**context)

with open("test.html", 'w', encoding='utf-8') as f:
    f.write(html)

import webbrowser, os
webbrowser.open(f'file:///{os.path.abspath("test.html")}')
print("✅ تم فتح الفاتورة")
