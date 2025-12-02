#!/usr/bin/env python3
"""
Test script to verify clean_invoice.html template works
"""

from services.smart_invoice_manager import SmartInvoiceManager
from datetime import datetime, timedelta

def test_clean_template():
    print("🧪 Testing clean_invoice.html template...")
    
    # Sample data
    test_data = {
        # معلومات الشركة
        'company_name': 'Sky Wave',
        'company_tagline': 'تسويق الكتروني',
        'company_address': 'القاهرة - دمياط الجديدة',
        'company_phone': '+201021965200 - +201067894321',
        'company_website': 'www.skywaveads.com',
        'logo_path': 'site logo.png',
        
        # معلومات الفاتورة
        'invoice_number': f"SW-TEST-{datetime.now().strftime('%Y%m%d%H%M')}",
        'date': datetime.now().strftime('%Y-%m-%d'),
        'due_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        'project_name': 'Test Project',
        
        # معلومات العميل
        'client_name': 'Test Client',
        'client_phone': '201234567890',
        'client_address': 'Test Address',
        'client_email': 'test@example.com',
        
        # البنود والإجماليات
        'items': [
            {
                'description': 'Test Service 1',
                'quantity': 2.0,
                'unit_price': 500.0,
                'discount': 0,
                'total': 1000.0
            },
            {
                'description': 'Test Service 2',
                'quantity': 1.0,
                'unit_price': 750.0,
                'discount': 0,
                'total': 750.0
            }
        ],
        'payments': [
            {
                'date': '2025-12-01',
                'amount': 800.0,
                'method': 'Cash'
            }
        ],
        'subtotal': 1750.0,
        'discount_amount': 0,
        'tax_amount': 0,
        'grand_total': 1750.0,
        'total_paid': 800.0,
        'remaining_amount': 950.0
    }
    
    try:
        manager = SmartInvoiceManager()
        
        # Test template rendering
        html_content = manager._render_template('clean_invoice.html', test_data)
        print(f"✅ Template rendered successfully, HTML size: {len(html_content)} chars")
        
        # Test PDF generation
        pdf_path = manager.generate_pdf_from_template('clean_invoice.html', test_data, 'test_clean')
        
        if pdf_path:
            print(f"✅ PDF generated successfully: {pdf_path}")
            return True
        else:
            print("❌ PDF generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            manager.cleanup()
        except:
            pass

if __name__ == "__main__":
    success = test_clean_template()
    print(f"\n{'✅ TEST PASSED' if success else '❌ TEST FAILED'}")